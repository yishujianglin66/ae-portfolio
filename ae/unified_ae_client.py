"""AE 操作通道统一融合层（Unified AE Client）。

为 AE Knowledge Vault 项目提供**单一 API**，自动在两套 AE 操作通道之间调度：

1. **puppet-automation 引擎**（puppet 通道）
   - Python 通过 ``aerender`` CLI 直接调用
   - 无界面，10+ 高层 API
   - 适合：渲染、长任务、批处理

2. **MCP 桥接**（mcp 通道）
   - Python → bridge.json → AE 面板 → ExtendScript
   - 40+ 工具，需要 AE 启动
   - 适合：交互式编辑、原子操作、原子脚本

设计原则：
- **API 兼容性**：方法签名同时兼容两套通道。
- **透明切换**：业务代码不关心实际使用哪个通道。
- **自动降级**：主通道失败自动降级。
- **统计透明**：记录每个通道的成功/失败/延迟。
- **线程安全**：内部使用 RLock 保护共享状态。
- **异步优先**：同步/异步双 API 支持。
- **可观测**：集成事件总线，发布操作事件。

典型用法：
    >>> from ae.unified_ae_client import UnifiedAEClient, AEChannel
    >>> client = UnifiedAEClient()  # 自动加载两个通道
    >>> result = client.create_composition("MyComp", 1920, 1080)
    >>> print(client.get_stats())

    # 异步 API
    >>> async_result = await client.acreate_composition("MyComp", 1920, 1080)
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

try:
    from core.event_bus import publish_ae_event
    _EVENT_BUS_AVAILABLE = True
except ImportError:
    _EVENT_BUS_AVAILABLE = False

try:
    from core.ae_tracer import start_ae_operation, end_ae_operation, ae_tracer
    _TRACER_AVAILABLE = True
except ImportError:
    _TRACER_AVAILABLE = False


# ============================================================================
# 枚举与数据结构
# ============================================================================


class AEChannel(str, Enum):
    """AE 操作通道枚举。"""

    PUPPET = "puppet"
    MCP = "mcp"
    AUTO = "auto"


@dataclass
class AEOperation:
    """AE 操作请求。

    用于在 UnifiedAEClient 内部统一表达一次 AE 操作请求。
    支持：通道偏好、GUI 要求、估算耗时、幂等标记、降级链。

    Attributes:
        name: 操作名称（如 ``"create_composition"``）
        channel: 通道偏好（PUPPET / MCP / AUTO）
        method: 适配器方法名（与 AEOperation.name 通常相同，可省略）
        params: 传递给适配器方法的参数字典
        requires_gui: 是否需要 AE 界面
        estimated_duration: 估算耗时（秒）
        is_idempotent: 是否幂等（失败可安全重试）
        fallback: 降级链（主通道失败后切换到 fallback 指定的通道）
    """

    name: str
    channel: AEChannel = AEChannel.AUTO
    method: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    requires_gui: bool = False
    estimated_duration: float = 1.0
    is_idempotent: bool = False
    fallback: Optional["AEOperation"] = None

    def __post_init__(self) -> None:
        if not self.method:
            self.method = self.name


@dataclass
class AEChannelStats:
    """单通道调用统计。"""

    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    last_call_time: Optional[float] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0

    def record(self, success: bool, latency_ms: float, error: Optional[str] = None) -> None:
        """记录一次调用结果。"""
        self.total_calls += 1
        self.total_latency_ms += latency_ms
        self.last_call_time = time.time()
        if success:
            self.success_count += 1
            self.consecutive_failures = 0
        else:
            self.failure_count += 1
            self.consecutive_failures += 1
            self.last_error = error

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.success_count / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_call_time": self.last_call_time,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
        }


# ============================================================================
# 通道选择策略
# ============================================================================


class ChannelSelector:
    """通道选择策略。

    根据操作类型、运行时上下文、通道健康度选择最优通道。
    静态规则 + 动态调整相结合。

    选择优先级（自上而下）：
    1. 操作固定规则（``RULES``）
    2. GUI 要求（``GUI_REQUIRED``）
    3. 通道健康度（连续失败次数）
    4. 通道平均延迟
    5. 兜底：PUPPET（无界面可用性更高）

    Attributes:
        RULES: 操作名 → 通道偏好的静态映射
        GUI_REQUIRED: 强制要求 GUI 的操作集合
        FAILURE_THRESHOLD: 连续失败多少次认为通道不健康
    """

    RULES: Dict[str, AEChannel] = {
        # 渲染：puppet 通道最稳（aerender 无界面）
        "render": AEChannel.PUPPET,
        "render_segment": AEChannel.PUPPET,
        # 表达式、原子脚本：MCP 通道在 GUI 环境下更灵活
        "execute_atom_script": AEChannel.MCP,
        "set_layer_expression": AEChannel.MCP,
        "set_keyframe_easing": AEChannel.MCP,
        "apply_effect_template": AEChannel.MCP,
        # 其它通用操作：AUTO（按健康度选）
    }

    GUI_REQUIRED: Set[str] = {
        "execute_atom_script",
        "set_layer_expression",
    }

    FAILURE_THRESHOLD: int = 3

    @classmethod
    def select(
        cls,
        op_name: str,
        context: Optional[Dict[str, Any]] = None,
        stats: Optional[Dict[AEChannel, AEChannelStats]] = None,
    ) -> AEChannel:
        """选择最合适的通道。

        Args:
            op_name: 操作名称
            context: 运行时上下文（``{"force_channel": ..., "project_path": ...}``）
            stats: 各通道的统计信息（用于健康度判断）

        Returns:
            选中的通道。
        """
        ctx = context or {}

        # 0. 用户强制指定
        forced = ctx.get("force_channel")
        if forced:
            try:
                return AEChannel(forced) if not isinstance(forced, AEChannel) else forced
            except ValueError:
                logger.warning("未知通道 %s，回退到 AUTO", forced)

        # 1. 静态规则
        if op_name in cls.RULES:
            rule_channel = cls.RULES[op_name]
            if rule_channel != AEChannel.AUTO:
                # 检查该通道是否健康
                if stats and not cls._is_healthy(rule_channel, stats):
                    logger.info(
                        "通道 %s 健康度不足，操作 %s 尝试降级",
                        rule_channel.value,
                        op_name,
                    )
                    return cls._fallback_channel(rule_channel, stats)
                return rule_channel

        # 2. GUI 要求
        if op_name in cls.GUI_REQUIRED or ctx.get("requires_gui"):
            return AEChannel.MCP

        # 3. 健康度选择
        if stats:
            puppet_healthy = cls._is_healthy(AEChannel.PUPPET, stats)
            mcp_healthy = cls._is_healthy(AEChannel.MCP, stats)
            if puppet_healthy and not mcp_healthy:
                return AEChannel.PUPPET
            if mcp_healthy and not puppet_healthy:
                return AEChannel.MCP
            if puppet_healthy and mcp_healthy:
                # 选择平均延迟较低的
                puppet_avg = stats.get(AEChannel.PUPPET, AEChannelStats()).avg_latency_ms
                mcp_avg = stats.get(AEChannel.MCP, AEChannelStats()).avg_latency_ms
                if puppet_avg == 0 and mcp_avg == 0:
                    return AEChannel.PUPPET
                return AEChannel.PUPPET if puppet_avg <= mcp_avg else AEChannel.MCP

        # 4. 兜底
        return AEChannel.PUPPET

    @classmethod
    def _is_healthy(cls, channel: AEChannel, stats: Dict[AEChannel, AEChannelStats]) -> bool:
        """通道是否健康（连续失败未超阈值）。"""
        s = stats.get(channel)
        if s is None:
            return True  # 没有数据默认健康
        return s.consecutive_failures < cls.FAILURE_THRESHOLD

    @classmethod
    def _fallback_channel(
        cls, current: AEChannel, stats: Dict[AEChannel, AEChannelStats]
    ) -> AEChannel:
        """从当前通道选一个备选。"""
        candidates = [c for c in (AEChannel.PUPPET, AEChannel.MCP) if c != current]
        for c in candidates:
            if cls._is_healthy(c, stats):
                return c
        return candidates[0] if candidates else current


# ============================================================================
# 异常体系
# ============================================================================


class UnifiedAEError(Exception):
    """UnifiedAEClient 基础异常。"""

    def __init__(self, message: str, channel: Optional[str] = None) -> None:
        self.message = message
        self.channel = channel
        super().__init__(message)

    def __str__(self) -> str:
        if self.channel:
            return f"[{self.channel}] {self.message}"
        return self.message


class AllChannelsFailedError(UnifiedAEError):
    """所有通道均失败时抛出。"""

    def __init__(self, op_name: str, errors: List[Tuple[str, str]]) -> None:
        self.op_name = op_name
        self.errors = errors
        msg = f"操作 {op_name} 所有通道均失败: " + "; ".join(
            f"[{ch}] {err}" for ch, err in errors
        )
        super().__init__(msg)


# ============================================================================
# UnifiedAEClient
# ============================================================================


class UnifiedAEClient:
    """AE 操作通道统一融合层。

    维护两个 AE 通道（puppet / mcp），对外提供一致的高层 API。
    内部根据 ``ChannelSelector`` 自动选择通道，失败时自动降级。

    Attributes:
        default_channel: 默认通道偏好
        enable_fallback: 是否启用自动降级
        stats_enabled: 是否启用统计
    """

    def __init__(
        self,
        puppet_engine: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
        default_channel: AEChannel = AEChannel.AUTO,
        enable_fallback: bool = True,
        stats_enabled: bool = True,
        puppet_adapter_factory: Optional[Callable[..., Any]] = None,
        mcp_adapter_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        """初始化统一客户端。

        Args:
            puppet_engine: puppet 引擎实例（None 时按需构造）
            mcp_client: MCP 客户端实例（None 时按需构造）
            default_channel: 默认通道
            enable_fallback: 失败时自动降级
            stats_enabled: 启用统计
            puppet_adapter_factory: 自定义 puppet 适配器工厂（测试用）
            mcp_adapter_factory: 自定义 MCP 适配器工厂（测试用）
        """
        self.default_channel = default_channel
        self.enable_fallback = enable_fallback
        self.stats_enabled = stats_enabled

        # 通道实例（懒加载）
        self._puppet: Optional[Any] = None
        self._mcp: Optional[Any] = None
        self._puppet_ready: Optional[bool] = None
        self._mcp_ready: Optional[bool] = None

        # 注入 / 工厂
        self._puppet_inject = puppet_engine
        self._mcp_inject = mcp_client
        self._puppet_factory = puppet_adapter_factory
        self._mcp_factory = mcp_adapter_factory

        # 统计
        self._stats: Dict[AEChannel, AEChannelStats] = {
            AEChannel.PUPPET: AEChannelStats(),
            AEChannel.MCP: AEChannelStats(),
        }
        self._lock = threading.RLock()

    # ==================================================================
    # 通道初始化
    # ==================================================================

    def _get_puppet(self) -> Any:
        """获取 puppet 适配器（懒加载）。"""
        with self._lock:
            if self._puppet is not None:
                return self._puppet
            if self._puppet_inject is not None:
                self._puppet = self._puppet_inject
            elif self._puppet_factory is not None:
                self._puppet = self._puppet_factory()
            else:
                from ae.adapters.puppet_adapter import PuppetEngineAdapter
                self._puppet = PuppetEngineAdapter()
            return self._puppet

    def _get_mcp(self) -> Any:
        """获取 MCP 适配器（懒加载）。"""
        with self._lock:
            if self._mcp is not None:
                return self._mcp
            if self._mcp_inject is not None:
                self._mcp = self._mcp_inject
            elif self._mcp_factory is not None:
                self._mcp = self._mcp_factory()
            else:
                from ae.adapters.mcp_adapter import MCPClientAdapter
                self._mcp = MCPClientAdapter()
            return self._mcp

    def is_puppet_available(self) -> bool:
        """puppet 通道是否可用。"""
        with self._lock:
            if self._puppet_ready is not None:
                return self._puppet_ready
        try:
            adapter = self._get_puppet()
            ok = bool(adapter.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.debug("puppet 通道检测失败: %s", exc)
            ok = False
        with self._lock:
            self._puppet_ready = ok
        return ok

    def is_mcp_available(self) -> bool:
        """MCP 通道是否可用。"""
        with self._lock:
            if self._mcp_ready is not None:
                return self._mcp_ready
        try:
            adapter = self._get_mcp()
            ok = bool(adapter.is_available())
        except Exception as exc:  # noqa: BLE001
            logger.debug("MCP 通道检测失败: %s", exc)
            ok = False
        with self._lock:
            self._mcp_ready = ok
        return ok

    # ==================================================================
    # 通道选择 & 执行
    # ==================================================================

    def _select_channel(self, op: AEOperation) -> AEChannel:
        """为给定操作选择通道。"""
        # 1. 显式指定
        if op.channel != AEChannel.AUTO:
            return op.channel
        # 2. 默认通道
        if self.default_channel != AEChannel.AUTO:
            return self.default_channel
        # 3. 选择器
        return ChannelSelector.select(
            op.name,
            context={"requires_gui": op.requires_gui},
            stats=self._stats if self.stats_enabled else None,
        )

    def _execute_puppet(self, op: AEOperation) -> Dict[str, Any]:
        """在 puppet 通道上执行操作。"""
        adapter = self._get_puppet()
        method = getattr(adapter, op.method, None)
        if method is None:
            return {
                "success": False,
                "error": f"puppet 适配器缺少方法: {op.method}",
                "channel": "puppet",
            }
        result = method(**op.params)
        if not isinstance(result, dict):
            result = {"success": True, "data": result, "channel": "puppet"}
        return result

    def _execute_mcp(self, op: AEOperation) -> Dict[str, Any]:
        """在 MCP 通道上执行操作。"""
        # 快速失败：MCP 通道不可用时不要走真实连接等待 30s TTL
        if not self.is_mcp_available():
            return {
                "success": False,
                "error": "MCP 通道不可用",
                "channel": "mcp",
            }
        adapter = self._get_mcp()
        method = getattr(adapter, op.method, None)
        if method is None:
            return {
                "success": False,
                "error": f"MCP 适配器缺少方法: {op.method}",
                "channel": "mcp",
            }
        result = method(**op.params)
        if not isinstance(result, dict):
            result = {"success": True, "data": result, "channel": "mcp"}
        return result

    def _execute_with_fallback(self, op: AEOperation) -> Dict[str, Any]:
        """执行操作，支持降级。

        流程：
        1. 选择主通道。
        2. 调主通道。
        3. 失败且 ``enable_fallback`` 开启 → 调降级通道。
        4. 全部失败 → 抛 ``AllChannelsFailedError``。
        """
        primary = self._select_channel(op)
        tried: List[Tuple[str, str]] = []
        
        span = None
        if _TRACER_AVAILABLE:
            span = start_ae_operation(
                op.name,
                channel=primary.value,
                requires_gui=op.requires_gui,
                estimated_duration=op.estimated_duration,
            )
        else:
            span = None

        try:
            for attempt_channel in self._iter_channels(primary, op):
                start = time.time()
                channel_name = attempt_channel.value

                if _TRACER_AVAILABLE and span:
                    span.set_attribute("attempt_channel", channel_name)

                try:
                    if attempt_channel == AEChannel.PUPPET:
                        result = self._execute_puppet(op)
                    else:
                        result = self._execute_mcp(op)
                    latency_ms = (time.time() - start) * 1000.0
                    success = bool(result.get("success"))
                    if self.stats_enabled:
                        self._stats[attempt_channel].record(
                            success, latency_ms, result.get("error")
                        )
                    if success:
                        result.setdefault("channel_used", channel_name)
                        if _TRACER_AVAILABLE and span:
                            span.channel = channel_name
                            span.set_attribute("latency_ms", latency_ms)
                            end_ae_operation(span, "success")
                        self._publish_operation_event(
                            op, "success", channel=channel_name, latency_ms=latency_ms
                        )
                        return result
                    tried.append((channel_name, str(result.get("error", "unknown"))))
                    logger.warning(
                        "通道 %s 执行 %s 失败: %s",
                        channel_name,
                        op.name,
                        result.get("error"),
                    )
                except Exception as exc:  # noqa: BLE001
                    latency_ms = (time.time() - start) * 1000.0
                    err = f"{type(exc).__name__}: {exc}"
                    if self.stats_enabled:
                        self._stats[attempt_channel].record(False, latency_ms, err)
                    tried.append((channel_name, err))
                    logger.error("通道 %s 执行 %s 异常: %s", channel_name, op.name, err)
                    logger.debug(traceback.format_exc())

            # 全部失败
            self._publish_operation_event(op, "failed", channels=tried)
            if _TRACER_AVAILABLE and span:
                span.record_failure(str(tried))
                end_ae_operation(span, "failed")
            raise AllChannelsFailedError(op.name, tried)
        except Exception as exc:
            if _TRACER_AVAILABLE and span:
                span.record_failure(str(exc))
                end_ae_operation(span, "failed")
            raise

    def _iter_channels(
        self, primary: AEChannel, op: AEOperation
    ) -> List[AEChannel]:
        """生成执行通道顺序（含降级链）。"""
        order: List[AEChannel] = []
        # 用户在 op.fallback 中显式声明的降级链优先
        cur: Optional[AEOperation] = op
        while cur is not None:
            if cur.channel not in (AEChannel.AUTO,):
                order.append(cur.channel)
            cur = cur.fallback

        if not order:
            order.append(primary)

        # 如果启用降级，追加其它通道
        if self.enable_fallback and len(order) < 2:
            other = AEChannel.MCP if primary == AEChannel.PUPPET else AEChannel.PUPPET
            if other not in order:
                order.append(other)

        # 去重保序
        seen: Set[AEChannel] = set()
        deduped: List[AEChannel] = []
        for c in order:
            if c not in seen:
                deduped.append(c)
                seen.add(c)
        return deduped

    # ==================================================================
    # 高层操作 API（同步）
    # ==================================================================

    # -- 合成管理 --

    def create_composition(
        self,
        name: str,
        width: int,
        height: int,
        fps: float = 30.0,
        duration: float = 10.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建合成。"""
        op = AEOperation(
            name="create_composition",
            channel=AEChannel.AUTO,
            params={
                "name": name,
                "width": int(width),
                "height": int(height),
                "fps": float(fps),
                "duration": float(duration),
                **kwargs,
            },
            estimated_duration=2.0,
            is_idempotent=False,
        )
        return self._execute_with_fallback(op)

    def list_compositions(self) -> List[Dict[str, Any]]:
        """列出所有合成。"""
        op = AEOperation(
            name="list_compositions",
            channel=AEChannel.MCP,  # 列表查询 GUI 模式下更稳
            params={},
            requires_gui=True,
            estimated_duration=1.0,
            is_idempotent=True,
        )
        # 列表方法在失败时返回空列表，不抛异常
        try:
            result = self._execute_with_fallback(op)
            if isinstance(result, list):
                return result
            return result.get("compositions", []) if isinstance(result, dict) else []
        except AllChannelsFailedError:
            return []

    # -- 图层创建 --

    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建文字图层。"""
        op = AEOperation(
            name="create_text_layer",
            params={"comp_name": comp_name, "text": text, **kwargs},
            requires_gui=True,
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    def create_solid_layer(
        self,
        comp_name: str,
        color: List[float],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建固态层。"""
        op = AEOperation(
            name="create_solid_layer",
            params={"comp_name": comp_name, "color": color, **kwargs},
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    def create_shape_layer(
        self,
        comp_name: str,
        shape_type: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="create_shape_layer",
            params={"comp_name": comp_name, "shape_type": shape_type, **kwargs},
            requires_gui=True,
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    def add_adjustment_layer(
        self,
        comp_name: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="add_adjustment_layer",
            params={"comp_name": comp_name, **kwargs},
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    # -- 图层属性 --

    def set_layer_properties(
        self,
        comp_name: str,
        layer_index: int,
        **properties: Any,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_layer_properties",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                **properties,
            },
            requires_gui=True,
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    def set_blend_mode(
        self,
        comp_name: str,
        layer_index: int,
        blend_mode: str,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_blend_mode",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "blend_mode": blend_mode,
            },
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    def set_track_matte(
        self,
        comp_name: str,
        layer_index: int,
        matte_type: str,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_track_matte",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "matte_type": matte_type,
            },
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    def set_parent_layer(
        self,
        comp_name: str,
        layer_index: int,
        parent_index: int,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_parent_layer",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "parent_index": int(parent_index),
            },
            requires_gui=True,
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    # -- 动画 --

    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        time: float,
        value: Any,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_layer_keyframe",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "property_name": property_name,
                "time": float(time),
                "value": value,
            },
            requires_gui=True,
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_index: int,
        property_path: str,
        key_index: int,
        easing_type: str,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_keyframe_easing",
            channel=AEChannel.MCP,
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "property_path": property_path,
                "key_index": int(key_index),
                "easing_type": easing_type,
            },
            requires_gui=True,
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    def set_layer_expression(
        self,
        comp_name: str,
        layer_index: int,
        property_name: str,
        expression: str,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_layer_expression",
            channel=AEChannel.MCP,
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "property_name": property_name,
                "expression": expression,
            },
            requires_gui=True,
            estimated_duration=0.5,
        )
        return self._execute_with_fallback(op)

    # -- 效果 --

    def apply_effect(
        self,
        comp_name: str,
        layer_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="apply_effect",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "effect_name": effect_name,
                "settings": settings or {},
            },
            requires_gui=True,
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    def apply_effect_template(
        self,
        comp_name: str,
        layer_index: int,
        template_name: str,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="apply_effect_template",
            channel=AEChannel.MCP,
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "template_name": template_name,
            },
            requires_gui=True,
            estimated_duration=2.0,
        )
        return self._execute_with_fallback(op)

    def batch_add_effects(
        self,
        comp_name: str,
        layer_index: int,
        effects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="batch_add_effects",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                "effects": effects or [],
            },
            requires_gui=True,
            estimated_duration=5.0,
        )
        return self._execute_with_fallback(op)

    # -- 蒙版 --

    def set_layer_mask(
        self,
        comp_name: str,
        layer_index: int,
        **mask_params: Any,
    ) -> Dict[str, Any]:
        op = AEOperation(
            name="set_layer_mask",
            params={
                "comp_name": comp_name,
                "layer_index": int(layer_index),
                **mask_params,
            },
            requires_gui=True,
            estimated_duration=1.0,
        )
        return self._execute_with_fallback(op)

    # -- 渲染 --

    def render(
        self,
        comp_name: str,
        output_path: str,
        format: str = "h264",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """渲染合成（默认走 puppet 通道，aerender CLI 渲染）。"""
        op = AEOperation(
            name="render",
            channel=AEChannel.PUPPET,
            params={
                "comp_name": comp_name,
                "output_path": output_path,
                "format": format,
                **kwargs,
            },
            estimated_duration=60.0,
        )
        return self._execute_with_fallback(op)

    # -- 高级 --

    def execute_atom_script(
        self,
        script: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """执行原子脚本（默认走 MCP 通道）。"""
        op = AEOperation(
            name="execute_atom_script",
            channel=AEChannel.MCP,
            params={"script": script, "dry_run": dry_run},
            requires_gui=True,
            estimated_duration=2.0,
        )
        return self._execute_with_fallback(op)

    # ==================================================================
    # 异步 API（a 前缀）
    # ==================================================================

    async def acreate_composition(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.create_composition, **kwargs)

    async def alist_compositions(self) -> List[Dict[str, Any]]:
        return await asyncio.to_thread(self.list_compositions)

    async def acreate_text_layer(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.create_text_layer, **kwargs)

    async def acreate_solid_layer(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.create_solid_layer, **kwargs)

    async def acreate_shape_layer(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.create_shape_layer, **kwargs)

    async def aadd_adjustment_layer(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.add_adjustment_layer, **kwargs)

    async def aset_layer_properties(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_layer_properties, **kwargs)

    async def aset_blend_mode(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_blend_mode, **kwargs)

    async def aset_track_matte(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_track_matte, **kwargs)

    async def aset_parent_layer(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_parent_layer, **kwargs)

    async def aset_layer_keyframe(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_layer_keyframe, **kwargs)

    async def aset_keyframe_easing(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_keyframe_easing, **kwargs)

    async def aset_layer_expression(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_layer_expression, **kwargs)

    async def aapply_effect(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.apply_effect, **kwargs)

    async def aapply_effect_template(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.apply_effect_template, **kwargs)

    async def abatch_add_effects(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.batch_add_effects, **kwargs)

    async def aset_layer_mask(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.set_layer_mask, **kwargs)

    async def arender(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.render, **kwargs)

    async def aexecute_atom_script(self, **kwargs) -> Dict[str, Any]:
        return await asyncio.to_thread(self.execute_atom_script, **kwargs)

    # ==================================================================
    # 事件发布辅助方法
    # ==================================================================

    def _publish_operation_event(self, op: AEOperation, status: str, **kwargs) -> None:
        """发布操作事件到事件总线。"""
        if not _EVENT_BUS_AVAILABLE:
            return
        try:
            trace_id = kwargs.pop("trace_id", None)
            if trace_id is None and _TRACER_AVAILABLE:
                trace_id = ae_tracer.current_trace_id
            
            payload = {
                "operation": op.name,
                "channel": op.channel.value,
                "requires_gui": op.requires_gui,
                "estimated_duration": op.estimated_duration,
                "is_idempotent": op.is_idempotent,
                "trace_id": trace_id,
                **kwargs,
            }
            publish_ae_event(f"operation.{status}", payload=payload)
        except Exception as e:
            logger.debug("事件发布失败: %s", e)

    # ==================================================================
    # 统计
    # ==================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计。"""
        with self._lock:
            return {
                "puppet": self._stats[AEChannel.PUPPET].to_dict(),
                "mcp": self._stats[AEChannel.MCP].to_dict(),
                "channels_available": {
                    "puppet": self.is_puppet_available(),
                    "mcp": self.is_mcp_available(),
                },
                "default_channel": self.default_channel.value,
                "fallback_enabled": self.enable_fallback,
            }

    def reset_stats(self) -> None:
        """重置统计。"""
        with self._lock:
            for s in self._stats.values():
                s.total_calls = 0
                s.success_count = 0
                s.failure_count = 0
                s.total_latency_ms = 0.0
                s.last_call_time = None
                s.last_error = None
                s.consecutive_failures = 0


__all__ = [
    "AEChannel",
    "AEOperation",
    "AEChannelStats",
    "ChannelSelector",
    "UnifiedAEError",
    "AllChannelsFailedError",
    "UnifiedAEClient",
]
