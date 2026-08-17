"""
AE MCP 客户端封装 v1.0（自研 .ae-mcp-bridge 文件轮询协议栈）
====================================

注意：本模块为自研 .ae-mcp-bridge 协议栈的遗留客户端，AE MCP 已转向开源基线
（after-effects-mcp + 原版 mcp-bridge-auto.jsx）。模块仍被
``ae.adapters.mcp_adapter`` 等依赖方使用，故保留且不触发弃用告警；
新代码应优先迁移到开源基线，而非继续在此扩展。

原始功能说明：
基于 Bridge 协议的高质量 After Effects MCP 客户端封装。

提供：
- 完整的类型注解与文档字符串
- 40+ MCP 工具方法封装
- 流式构建接口（CompositionBuilder / LayerBuilder / EffectStack）
- 自定义异常体系
- 自动重试与降级策略
- 连接状态监控与心跳检测
- 调用统计与性能指标

协议兼容：
- 开源 after-effects-mcp 项目命令格式（camelCase）
- bridge_protocol.py BridgeClient v2.0

使用示例：
    from ae.ae_mcp_client import AEMCPClient, CompositionBuilder

    client = AEMCPClient(bridge_dir="C:/Users/.../ae-mcp-bridge")
    client.ping()

    # 流式构建合成
    comp = (
        CompositionBuilder(client, "MyComp")
        .size(1920, 1080)
        .duration(10)
        .fps(30)
        .add_text_layer("Hello", "Hello World")
        .build()
    )
"""

from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

from ae.archive.bridge_protocol import (
    BridgeClient,
    BridgeCommand,
    BridgeResponse,
    BridgeProgress,
    BridgeMetadata,
    CommandStatus,
    ErrorCode,
    Priority,
    DEFAULT_TTL_MS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_RETRIES,
)

from ae.archive.bridge_middleware import (
    MiddlewarePipeline,
    LoggingMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    ValidationMiddleware,
    RetryMiddleware,
)

# Bridge 默认目录收口到 core/paths.py（AEK_AE_BRIDGE_DIR 可覆盖）
try:
    from core.paths import ae_bridge_dir as _paths_ae_bridge
    _DEFAULT_BRIDGE_DIR = _paths_ae_bridge()
except ImportError:
    _DEFAULT_BRIDGE_DIR = r"C:\Users\Administrator\Documents\ae-mcp-bridge"

logger = logging.getLogger(__name__)


# ============================================================================
# 自定义异常体系
# ============================================================================


class AEMCPError(Exception):
    """AE MCP 客户端基础异常。

    所有 AE MCP 相关异常的基类。

    Attributes:
        message: 错误消息
        error_code: 错误码
        details: 详细错误信息
    """

    def __init__(
        self,
        message: str = "AE MCP 操作失败",
        error_code: Optional[ErrorCode] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.message]
        if self.error_code:
            parts.append(f"[错误码: {self.error_code.value}]")
        if self.details:
            parts.append(f"详情: {self.details}")
        return " ".join(parts)


class AEConnectionError(AEMCPError):
    """AE 连接异常。

    当无法连接到 After Effects 或桥接通信失败时抛出。
    """

    pass


class AECommandError(AEMCPError):
    """AE 命令执行异常。

    当 AE 端命令执行失败时抛出。
    """

    pass


class AETimeoutError(AEMCPError):
    """AE 命令超时异常。

    当命令执行超时时抛出。
    """

    pass


class AENotFoundError(AEMCPError):
    """AE 资源不存在异常。

    当合成、图层、效果等资源不存在时抛出。
    """

    pass


class AESecurityError(AEMCPError):
    """AE MCP 安全异常（签名校验失败 / 重放攻击）。

    响应签名验证失败或检测到重放攻击时由安全校验路径抛出。
    """

    pass


# ============================================================================
# 错误码到异常的映射
# ============================================================================

_ERROR_CODE_TO_EXCEPTION: Dict[ErrorCode, Type[AEMCPError]] = {
    ErrorCode.AE_NOT_RUNNING: AEConnectionError,
    ErrorCode.AE_NOT_RESPONDING: AEConnectionError,
    ErrorCode.IO_ERROR: AEConnectionError,
    ErrorCode.NETWORK_ERROR: AEConnectionError,
    ErrorCode.LOCK_ACQUISITION_FAILED: AEConnectionError,
    ErrorCode.SCRIPT_TIMEOUT: AETimeoutError,
    ErrorCode.COMPOSITION_NOT_FOUND: AENotFoundError,
    ErrorCode.LAYER_NOT_FOUND: AENotFoundError,
    ErrorCode.EFFECT_NOT_FOUND: AENotFoundError,
    ErrorCode.PROPERTY_NOT_FOUND: AENotFoundError,
    ErrorCode.RESOURCE_NOT_FOUND: AENotFoundError,
    ErrorCode.SCRIPT_EXECUTION_ERROR: AECommandError,
    ErrorCode.INVALID_PARAMETER: AECommandError,
    ErrorCode.IMPORT_FAILED: AECommandError,
    ErrorCode.RENDER_FAILED: AECommandError,
    ErrorCode.INVALID_LAYER_TYPE: AECommandError,
    ErrorCode.OPERATION_NOT_SUPPORTED: AECommandError,
}


def _raise_from_response_error(response: BridgeResponse) -> AEMCPError:
    """从 BridgeResponse 创建对应的异常。

    Args:
        response: 失败的响应对象

    Returns:
        对应的 AEMCPError 子类实例
    """
    error = response.error
    if not error:
        return AEMCPError("未知错误")

    exc_class = _ERROR_CODE_TO_EXCEPTION.get(error.code, AEMCPError)
    return exc_class(
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


# ============================================================================
# 数据结构定义
# ============================================================================


@dataclass
class CompositionInfo:
    """合成信息。"""

    id: int
    name: str
    duration: float
    frame_rate: float
    width: int
    height: int
    num_layers: int


@dataclass
class LayerInfo:
    """图层信息。"""

    index: int
    name: str
    type: str
    duration: float
    start_time: float
    enabled: bool
    solo: bool
    locked: bool
    shy: bool


@dataclass
class EffectInfo:
    """效果信息。"""

    name: str
    match_name: str
    index: int
    enabled: bool


@dataclass
class KeyframeInfo:
    """关键帧信息。"""

    time: float
    value: Any
    ease_in: Optional[List[float]] = None
    ease_out: Optional[List[float]] = None


@dataclass
class ClientStats:
    """客户端统计信息。"""

    total_calls: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    last_call_time: Optional[float] = None


# ============================================================================
# BlendMode 枚举
# ============================================================================


class BlendMode(str, Enum):
    """图层混合模式。"""

    NORMAL = "NORMAL"
    ADD = "ADD"
    MULTIPLY = "MULTIPLY"
    SCREEN = "SCREEN"
    OVERLAY = "OVERLAY"
    DARKEN = "DARKEN"
    LIGHTEN = "LIGHTEN"
    COLOR_DODGE = "COLORDODGE"
    COLOR_BURN = "COLORBURN"
    HARD_LIGHT = "HARDLIGHT"
    SOFT_LIGHT = "SOFTLIGHT"
    DIFFERENCE = "DIFFERENCE"
    EXCLUSION = "EXCLUSION"
    HUE = "HUE"
    SATURATION = "SATURATION"
    COLOR = "COLOR"
    LUMINOSITY = "LUMINOSITY"
    SILHOUETTE_ALPHA = "SILHOUETTE_ALPHA"
    SILHOUETTE_LUMA = "SILHOUETTE_LUMA"
    STENCIL_ALPHA = "STENCIL_ALPHA"
    STENCIL_LUMA = "STENCIL_LUMA"


class TrackMatteType(str, Enum):
    """轨道遮罩类型。"""

    NO_TRACK_MATTE = "NO_TRACK_MATTE"
    ALPHA = "ALPHA"
    ALPHA_INVERTED = "ALPHA_INVERTED"
    LUMA = "LUMA"
    LUMA_INVERTED = "LUMA_INVERTED"


class EasingType(str, Enum):
    """关键帧缓动类型。"""

    LINEAR = "linear"
    EASE_IN = "easeIn"
    EASE_OUT = "easeOut"
    EASE_IN_OUT = "easeInOut"


# ============================================================================
# AEMCPClient 主类
# ============================================================================


class AEMCPClient:
    """AE MCP 客户端。

    基于 BridgeClient 的高级封装，提供：
    - 自动检测 AE 运行状态
    - 连接状态监控
    - 自动重试与降级
    - 40+ MCP 工具方法
    - 流式构建接口
    - 中间件管道支持（日志、指标、限流、验证、重试）
    - 安全机制（HMAC-SHA256 响应签名验证、重放攻击防护、命令注入防护）

    示例：
        client = AEMCPClient(bridge_dir="C:/path/to/bridge")
        client.ping()
        comps = client.list_compositions()

    中间件管道配置：
        client = AEMCPClient(
            bridge_dir="C:/path/to/bridge",
            enable_middleware=True,
            max_requests_per_minute=60,
        )
        # 自定义中间件
        client.add_middleware(MyCustomMiddleware())

    安全配置：
        client = AEMCPClient(
            bridge_dir="C:/path/to/bridge",
            signature_enabled=True,
            enforce_response_signature=True,  # 强制验证响应签名
            anti_replay_window_seconds=300,  # 5分钟重放窗口
        )
    """

    def __init__(
        self,
        bridge_dir: str = _DEFAULT_BRIDGE_DIR,
        signature_enabled: bool = True,
        secret: Optional[str] = None,
        secret_file: Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay_ms: float = 100,
        max_delay_ms: float = 10000,
        backoff_factor: float = 2.0,
        retry_jitter: bool = True,
        use_queue_mode: bool = False,
        default_ttl_ms: int = DEFAULT_TTL_MS,
        enable_middleware: bool = True,
        max_requests_per_minute: int = 100,
        middleware_pipeline: Optional[MiddlewarePipeline] = None,
        enforce_response_signature: bool = False,
        anti_replay_window_seconds: int = 300,
    ) -> None:
        """初始化 AE MCP 客户端。

        Args:
            bridge_dir: 桥接目录路径
            signature_enabled: 是否启用签名验证
            secret: 签名密钥
            secret_file: 签名密钥文件路径
            poll_interval: 轮询间隔（秒）
            max_retries: 最大重试次数
            base_delay_ms: 基础重试延迟（毫秒）
            max_delay_ms: 最大重试延迟（毫秒）
            backoff_factor: 指数退避因子
            retry_jitter: 是否启用重试抖动
            use_queue_mode: 是否使用队列模式
            default_ttl_ms: 默认命令超时时间（毫秒）
            enable_middleware: 是否启用中间件管道
            max_requests_per_minute: 每分钟最大请求数（限流）
            middleware_pipeline: 自定义中间件管道（覆盖默认）
            enforce_response_signature: 是否强制验证响应签名
            anti_replay_window_seconds: 重放攻击防护窗口（秒），0 表示禁用
        """
        self._bridge = BridgeClient(
            bridge_dir=bridge_dir,
            signature_enabled=signature_enabled,
            secret=secret,
            secret_file=secret_file,
            poll_interval=poll_interval,
            max_retries=max_retries,
            base_delay_ms=base_delay_ms,
            max_delay_ms=max_delay_ms,
            backoff_factor=backoff_factor,
            retry_jitter=retry_jitter,
            use_queue_mode=use_queue_mode,
        )
        self._default_ttl_ms = default_ttl_ms
        self._stats = ClientStats()
        self._stats_lock = threading.Lock()
        self._last_heartbeat_time: Optional[float] = None
        self._heartbeat_interval: float = 30.0

        self._middleware_enabled = enable_middleware
        self._metrics_middleware: Optional[MetricsMiddleware] = None

        if enable_middleware:
            if middleware_pipeline is not None:
                self._pipeline = middleware_pipeline
            else:
                self._pipeline = self._create_default_pipeline(max_requests_per_minute)
        else:
            self._pipeline = None

        self._enforce_response_signature = enforce_response_signature
        self._anti_replay_window = anti_replay_window_seconds
        self._seen_command_ids: Dict[str, float] = {}
        self._anti_replay_lock = threading.Lock()

    # ------------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------------

    def _create_default_pipeline(self, max_requests_per_minute: int) -> MiddlewarePipeline:
        """创建默认中间件管道。

        管道顺序（按执行顺序）：
        1. LoggingMiddleware - 命令日志记录
        2. RateLimitMiddleware - 速率限制（防止 AE 过载）
        3. ValidationMiddleware - 参数校验
        4. RetryMiddleware - 自动重试
        5. MetricsMiddleware - 指标收集

        Args:
            max_requests_per_minute: 每分钟最大请求数

        Returns:
            配置好的中间件管道
        """
        pipeline = MiddlewarePipeline()
        pipeline.add(LoggingMiddleware())
        pipeline.add(RateLimitMiddleware(max_requests=max_requests_per_minute, window_seconds=60))
        pipeline.add(ValidationMiddleware())
        pipeline.add(RetryMiddleware(max_retries=2, base_delay_ms=100, max_delay_ms=3000))

        self._metrics_middleware = MetricsMiddleware()
        pipeline.add(self._metrics_middleware)

        return pipeline

    # ------------------------------------------------------------------------
    # 安全机制
    # ------------------------------------------------------------------------

    def _verify_response_signature(self, response: BridgeResponse) -> bool:
        """验证响应签名。

        使用 HMAC-SHA256 验证响应完整性，防止中间人攻击和数据篡改。

        Args:
            response: BridgeResponse 对象

        Returns:
            签名是否有效

        Raises:
            AESecurityError: 签名验证失败且 enforce_response_signature=True
        """
        if not self._enforce_response_signature:
            return True

        secret = self._bridge._secret
        if not secret:
            if self._enforce_response_signature:
                raise AESecurityError("响应签名验证已启用，但未配置密钥")
            return True

        if not response.signature:
            if self._enforce_response_signature:
                raise AESecurityError("响应缺少签名")
            return False

        import hashlib
        import hmac

        message = f"{response.command_id}{response.status}{response.error}{response.result}"
        expected_signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(response.signature, expected_signature):
            if self._enforce_response_signature:
                raise AESecurityError("响应签名验证失败")
            return False

        return True

    def _check_replay_attack(self, command_id: str) -> bool:
        """检查是否为重放攻击。

        在时间窗口内记录已处理的命令ID，防止相同命令被重复执行。

        Args:
            command_id: 命令ID

        Returns:
            是否为重放攻击

        Raises:
            AESecurityError: 检测到重放攻击
        """
        if self._anti_replay_window <= 0:
            return False

        now = time.time()

        with self._anti_replay_lock:
            if command_id in self._seen_command_ids:
                timestamp = self._seen_command_ids[command_id]
                if now - timestamp < self._anti_replay_window:
                    raise AESecurityError(f"检测到重放攻击: {command_id}")

            self._seen_command_ids[command_id] = now

            expired_ids = [
                cmd_id for cmd_id, ts in self._seen_command_ids.items()
                if now - ts >= self._anti_replay_window
            ]
            for cmd_id in expired_ids:
                del self._seen_command_ids[cmd_id]

        return False

    def _execute(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        priority: Optional[Priority] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[BridgeMetadata] = None,
        progress_callback: Optional[Callable[[BridgeProgress], None]] = None,
        raise_on_error: bool = True,
    ) -> Dict[str, Any]:
        """执行命令并返回结果。

        Args:
            command: 命令名称（snake_case，自动转换为camelCase）
            params: 命令参数
            ttl: 超时时间（毫秒）
            priority: 优先级
            idempotency_key: 幂等键
            metadata: 元数据
            progress_callback: 进度回调
            raise_on_error: 是否在错误时抛出异常

        Returns:
            命令结果字典

        Raises:
            AEMCPError: 命令执行失败且 raise_on_error=True
            AESecurityError: 安全验证失败
        """
        start_time = time.time()

        cmd_data = {
            "command": command,
            "params": params or {},
            "ttl": ttl or self._default_ttl_ms,
            "priority": priority,
            "idempotency_key": idempotency_key,
        }

        def _bridge_handler(cmd: Dict[str, Any]) -> BridgeResponse:
            return self._bridge.send_command(
                command=cmd["command"],
                params=cmd["params"],
                ttl=cmd["ttl"],
                priority=cmd["priority"],
                idempotency_key=cmd["idempotency_key"],
                metadata=metadata,
                progress_callback=progress_callback,
            )

        try:
            if self._pipeline is not None:
                response = self._pipeline.process_command(cmd_data, _bridge_handler)
            else:
                response = _bridge_handler(cmd_data)

            self._check_replay_attack(response.command_id)
            self._verify_response_signature(response)

            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(response.is_success, latency_ms)

            if response.is_success:
                return response.result or {}

            if raise_on_error:
                raise _raise_from_response_error(response)

            return {"error": response.error.model_dump() if response.error else "Unknown error"}

        except AEMCPError:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(False, latency_ms)
            raise AECommandError(f"命令执行异常: {e}") from e

    def _update_stats(self, success: bool, latency_ms: float) -> None:
        """更新调用统计。

        Args:
            success: 是否成功
            latency_ms: 延迟（毫秒）
        """
        with self._stats_lock:
            self._stats.total_calls += 1
            if success:
                self._stats.success_count += 1
            else:
                self._stats.failure_count += 1

            self._stats.total_latency_ms += latency_ms
            self._stats.avg_latency_ms = (
                self._stats.total_latency_ms / self._stats.total_calls
            )

            if self._stats.min_latency_ms == 0 or latency_ms < self._stats.min_latency_ms:
                self._stats.min_latency_ms = latency_ms
            if latency_ms > self._stats.max_latency_ms:
                self._stats.max_latency_ms = latency_ms

            self._stats.last_call_time = time.time()

    # ------------------------------------------------------------------------
    # 连接状态与心跳
    # ------------------------------------------------------------------------

    def ping(self) -> Dict[str, Any]:
        """检测 AE 是否存活。

        Returns:
            包含 pong 状态和 AE 版本信息的字典

        Raises:
            AEConnectionError: AE 未运行或无响应
        """
        try:
            result = self._execute("ping", {})
            self._last_heartbeat_time = time.time()
            return result
        except AEMCPError:
            self._last_heartbeat_time = None
            raise

    def is_alive(self) -> bool:
        """检查 AE 是否存活（心跳检测）。

        使用一段很短的 TTL 探测，避免在 AE 未运行时等待默认的 30s TTL，
        从而快速（毫秒级）返回 False。

        Returns:
            AE 是否运行中且响应正常
        """
        try:
            self._execute("ping", {}, ttl=1000, raise_on_error=False)
            self._last_heartbeat_time = time.time()
            return True
        except Exception:
            return False

    def wait_for_ae(
        self,
        timeout: float = 60.0,
        check_interval: float = 2.0,
    ) -> bool:
        """等待 AE 启动并就绪。

        Args:
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            AE 是否在超时前就绪
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_alive():
                return True
            time.sleep(check_interval)
        return False

    # ------------------------------------------------------------------------
    # 查询类方法
    # ------------------------------------------------------------------------

    def get_project_info(self) -> Dict[str, Any]:
        """获取当前项目信息。

        Returns:
            包含项目名称、路径、项目条目数等信息
        """
        return self._execute("getProjectInfo")

    def list_compositions(self) -> List[CompositionInfo]:
        """列出项目中的所有合成。

        Returns:
            合成信息列表
        """
        result = self._execute("listCompositions")
        comps = result.get("compositions", [])
        return [
            CompositionInfo(
                id=c["id"],
                name=c["name"],
                duration=c["duration"],
                frame_rate=c["frameRate"],
                width=c["width"],
                height=c["height"],
                num_layers=c["numLayers"],
            )
            for c in comps
        ]

    def get_layer_info(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
    ) -> Union[LayerInfo, List[LayerInfo]]:
        """获取图层信息。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称（None 时返回所有图层）

        Returns:
            单个或多个图层信息
        """
        params = {"compName": comp_name}
        if layer_name:
            params["layerName"] = layer_name

        result = self._execute("getLayerInfo", params)

        if layer_name:
            layer = result.get("layer", {})
            return LayerInfo(
                index=layer.get("index", 0),
                name=layer.get("name", ""),
                type=layer.get("type", ""),
                duration=layer.get("duration", 0),
                start_time=layer.get("startTime", 0),
                enabled=layer.get("enabled", True),
                solo=layer.get("solo", False),
                locked=layer.get("locked", False),
                shy=layer.get("shy", False),
            )
        else:
            layers = result.get("layers", [])
            return [
                LayerInfo(
                    index=l.get("index", 0),
                    name=l.get("name", ""),
                    type=l.get("type", ""),
                    duration=l.get("duration", 0),
                    start_time=l.get("startTime", 0),
                    enabled=l.get("enabled", True),
                    solo=l.get("solo", False),
                    locked=l.get("locked", False),
                    shy=l.get("shy", False),
                )
                for l in layers
            ]

    def list_effects(
        self,
        comp_name: str,
        layer_name: str,
    ) -> List[EffectInfo]:
        """列出图层上的所有效果。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称

        Returns:
            效果信息列表
        """
        result = self._execute(
            "listEffects",
            {"compName": comp_name, "layerName": layer_name},
        )
        effects = result.get("effects", [])
        return [
            EffectInfo(
                name=e["name"],
                match_name=e.get("matchName", ""),
                index=e.get("index", 0),
                enabled=e.get("enabled", True),
            )
            for e in effects
        ]

    def get_effect_properties(
        self,
        comp_name: str,
        layer_name: str,
        effect_name: str,
    ) -> Dict[str, Any]:
        """获取效果的属性列表。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            effect_name: 效果名称

        Returns:
            效果属性字典
        """
        return self._execute(
            "getEffectProperties",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "effectName": effect_name,
            },
        )

    # ------------------------------------------------------------------------
    # 合成管理
    # ------------------------------------------------------------------------

    def create_composition(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        duration: float = 10.0,
        frame_rate: float = 30.0,
        bg_color: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """创建新合成。

        Args:
            name: 合成名称
            width: 宽度（像素）
            height: 高度（像素）
            duration: 时长（秒）
            frame_rate: 帧率
            bg_color: 背景色 [r, g, b]，0-1 范围

        Returns:
            新合成信息
        """
        params = {
            "name": name,
            "width": width,
            "height": height,
            "duration": duration,
            "frameRate": frame_rate,
        }
        if bg_color is not None:
            params["bgColor"] = bg_color
        return self._execute("createComposition", params)

    def delete_composition(self, comp_name: str) -> Dict[str, Any]:
        """删除合成。

        Args:
            comp_name: 合成名称

        Returns:
            操作结果
        """
        return self._execute("deleteComposition", {"compName": comp_name})

    def duplicate_composition(
        self,
        source_comp: str,
        new_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """复制合成。

        Args:
            source_comp: 源合成名称
            new_name: 新合成名称

        Returns:
            新合成信息
        """
        params = {"sourceComp": source_comp}
        if new_name:
            params["newName"] = new_name
        return self._execute("duplicateComposition", params)

    def set_composition_settings(
        self,
        comp_name: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[float] = None,
        frame_rate: Optional[float] = None,
        bg_color: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """修改合成设置。

        Args:
            comp_name: 合成名称
            width: 新宽度
            height: 新高度
            duration: 新时长
            frame_rate: 新帧率
            bg_color: 新背景色

        Returns:
            更新后的合成信息
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if width is not None:
            params["width"] = width
        if height is not None:
            params["height"] = height
        if duration is not None:
            params["duration"] = duration
        if frame_rate is not None:
            params["frameRate"] = frame_rate
        if bg_color is not None:
            params["bgColor"] = bg_color
        return self._execute("setCompositionSettings", params)

    # ------------------------------------------------------------------------
    # 图层创建
    # ------------------------------------------------------------------------

    def create_text_layer(
        self,
        comp_name: str,
        text: str,
        layer_name: Optional[str] = None,
        font_family: Optional[str] = None,
        font_size: Optional[float] = None,
        fill_color: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """创建文字图层。

        Args:
            comp_name: 合成名称
            text: 文字内容
            layer_name: 图层名称
            font_family: 字体族
            font_size: 字体大小
            fill_color: 填充色 [r, g, b]
            position: 位置 [x, y]

        Returns:
            新建图层信息
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "text": text,
        }
        if layer_name:
            params["layerName"] = layer_name
        if font_family:
            params["fontFamily"] = font_family
        if font_size is not None:
            params["fontSize"] = font_size
        if fill_color is not None:
            params["fillColor"] = fill_color
        if position is not None:
            params["position"] = position
        return self._execute("createTextLayer", params)

    def create_shape_layer(
        self,
        comp_name: str,
        shape_type: str = "rect",
        layer_name: Optional[str] = None,
        fill_color: Optional[List[float]] = None,
        stroke_color: Optional[List[float]] = None,
        stroke_width: Optional[float] = None,
        size: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """创建形状图层。

        Args:
            comp_name: 合成名称
            shape_type: 形状类型 "rect" | "ellipse" | "polygon" | "star"
            layer_name: 图层名称
            fill_color: 填充色
            stroke_color: 描边色
            stroke_width: 描边宽度
            size: 尺寸 [width, height]
            position: 位置 [x, y]

        Returns:
            新建图层信息
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "shapeType": shape_type,
        }
        if layer_name:
            params["layerName"] = layer_name
        if fill_color is not None:
            params["fillColor"] = fill_color
        if stroke_color is not None:
            params["strokeColor"] = stroke_color
        if stroke_width is not None:
            params["strokeWidth"] = stroke_width
        if size is not None:
            params["size"] = size
        if position is not None:
            params["position"] = position
        return self._execute("createShapeLayer", params)

    def create_solid_layer(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
        color: Optional[List[float]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        """创建固态层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            color: 固态层颜色 [r, g, b]
            width: 宽度
            height: 高度

        Returns:
            新建图层信息
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if layer_name:
            params["layerName"] = layer_name
        if color is not None:
            params["color"] = color
        if width is not None:
            params["width"] = width
        if height is not None:
            params["height"] = height
        return self._execute("createSolidLayer", params)

    def add_adjustment_layer(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加调整图层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称

        Returns:
            新建图层信息
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if layer_name:
            params["layerName"] = layer_name
        return self._execute("addAdjustmentLayer", params)

    def create_null_layer(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建空对象图层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称

        Returns:
            新建图层信息
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if layer_name:
            params["layerName"] = layer_name
        return self._execute("createNullLayer", params)

    def create_camera(
        self,
        comp_name: str,
        layer_name: Optional[str] = None,
        preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建摄像机。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            preset: 摄像机预设

        Returns:
            新建摄像机信息
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if layer_name:
            params["layerName"] = layer_name
        if preset:
            params["preset"] = preset
        return self._execute("createCamera", params)

    def create_light(
        self,
        comp_name: str,
        light_type: str = "point",
        layer_name: Optional[str] = None,
        intensity: Optional[float] = None,
        color: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """创建灯光。

        Args:
            comp_name: 合成名称
            light_type: 灯光类型 "point" | "spot" | "parallel" | "ambient"
            layer_name: 图层名称
            intensity: 强度
            color: 灯光颜色

        Returns:
            新建灯光信息
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "lightType": light_type,
        }
        if layer_name:
            params["layerName"] = layer_name
        if intensity is not None:
            params["intensity"] = intensity
        if color is not None:
            params["color"] = color
        return self._execute("createLight", params)

    def delete_layer(
        self,
        comp_name: str,
        layer_name: str,
    ) -> Dict[str, Any]:
        """删除图层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称

        Returns:
            操作结果
        """
        return self._execute(
            "deleteLayer",
            {"compName": comp_name, "layerName": layer_name},
        )

    def duplicate_layer(
        self,
        comp_name: str,
        layer_name: str,
        new_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """复制图层。

        Args:
            comp_name: 合成名称
            layer_name: 源图层名称
            new_name: 新图层名称

        Returns:
            新图层信息
        """
        params = {
            "compName": comp_name,
            "layerName": layer_name,
        }
        if new_name:
            params["newName"] = new_name
        return self._execute("duplicateLayer", params)

    # ------------------------------------------------------------------------
    # 图层属性
    # ------------------------------------------------------------------------

    def set_layer_properties(
        self,
        comp_name: str,
        layer_name: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """设置图层属性。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            properties: 属性字典，支持的键：
                - position: [x, y] 或 [x, y, z]
                - anchorPoint: [x, y]
                - scale: [x, y] 百分比
                - rotation: 旋转角度
                - opacity: 不透明度 0-100
                - startTime: 开始时间
                - enabled: 是否启用
                - solo: 是否独奏
                - locked: 是否锁定

        Returns:
            操作结果
        """
        return self._execute(
            "setLayerProperties",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "properties": properties,
            },
        )

    def set_blend_mode(
        self,
        comp_name: str,
        layer_name: str,
        blend_mode: Union[BlendMode, str],
    ) -> Dict[str, Any]:
        """设置图层混合模式。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            blend_mode: 混合模式

        Returns:
            操作结果
        """
        mode = blend_mode.value if isinstance(blend_mode, BlendMode) else blend_mode
        return self._execute(
            "setBlendingMode",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "blendingMode": mode,
            },
        )

    def set_track_matte(
        self,
        comp_name: str,
        target_layer: str,
        matte_layer: str,
        matte_type: Union[TrackMatteType, str] = TrackMatteType.ALPHA,
    ) -> Dict[str, Any]:
        """设置轨道遮罩。

        Args:
            comp_name: 合成名称
            target_layer: 目标图层名称（被遮罩的图层）
            matte_layer: 遮罩图层名称
            matte_type: 遮罩类型

        Returns:
            操作结果
        """
        mtype = matte_type.value if isinstance(matte_type, TrackMatteType) else matte_type
        return self._execute(
            "setTrackMatte",
            {
                "compName": comp_name,
                "targetLayer": target_layer,
                "matteLayer": matte_layer,
                "matteType": mtype,
            },
        )

    def set_parent_layer(
        self,
        comp_name: str,
        child_layer: str,
        parent_layer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """设置父子图层关系。

        Args:
            comp_name: 合成名称
            child_layer: 子图层名称
            parent_layer: 父图层名称（None 表示解除父子关系）

        Returns:
            操作结果
        """
        params = {
            "compName": comp_name,
            "childLayer": child_layer,
        }
        if parent_layer:
            params["parentLayer"] = parent_layer
        return self._execute("setParentLayer", params)

    def set_motion_blur(
        self,
        comp_name: str,
        layer_name: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """设置运动模糊。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            enabled: 是否启用运动模糊

        Returns:
            操作结果
        """
        return self._execute(
            "setMotionBlur",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "enabled": enabled,
            },
        )

    def set_layer_time_remap(
        self,
        comp_name: str,
        layer_name: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """启用/禁用时间重映射。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            enabled: 是否启用时间重映射

        Returns:
            操作结果
        """
        return self._execute(
            "setTimeRemap",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "enabled": enabled,
            },
        )

    # ------------------------------------------------------------------------
    # 动画与关键帧
    # ------------------------------------------------------------------------

    def set_layer_keyframe(
        self,
        comp_name: str,
        layer_name: str,
        property_name: str,
        time: float,
        value: Any,
        easing: Optional[Union[EasingType, str]] = None,
    ) -> Dict[str, Any]:
        """设置图层属性关键帧。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            property_name: 属性名称（如 "Position", "Scale", "Rotation", "Opacity"）
            time: 时间（秒）
            value: 属性值
            easing: 缓动类型

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "layerName": layer_name,
            "propertyName": property_name,
            "time": time,
            "value": value,
        }
        if easing:
            params["easing"] = easing.value if isinstance(easing, EasingType) else easing
        return self._execute("setLayerKeyframe", params)

    def set_keyframe_easing(
        self,
        comp_name: str,
        layer_name: str,
        property_name: str,
        keyframe_index: int,
        ease_in: Optional[List[float]] = None,
        ease_out: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """设置关键帧缓动曲线。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            property_name: 属性名称
            keyframe_index: 关键帧索引（从 0 开始）
            ease_in: 缓入曲线 [influence, speed]
            ease_out: 缓出曲线 [influence, speed]

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "layerName": layer_name,
            "propertyName": property_name,
            "keyframeIndex": keyframe_index,
        }
        if ease_in is not None:
            params["easeIn"] = ease_in
        if ease_out is not None:
            params["easeOut"] = ease_out
        return self._execute("setKeyframeEasing", params)

    def set_layer_expression(
        self,
        comp_name: str,
        layer_name: str,
        property_name: str,
        expression: str,
    ) -> Dict[str, Any]:
        """设置图层属性表达式。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            property_name: 属性名称
            expression: 表达式字符串

        Returns:
            操作结果
        """
        return self._execute(
            "setExpression",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "propertyName": property_name,
                "expressionText": expression,
            },
        )

    def set_keyframe_batch(
        self,
        comp_name: str,
        layer_name: str,
        keyframes: List[Dict[str, Any]],
        expressions: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """批量设置关键帧。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            keyframes: 关键帧列表，每项包含：
                - property: 属性名
                - time: 时间（秒）
                - value: 属性值
                - easeType: 缓动类型
            expressions: 表达式映射 {属性名: 表达式}

        Returns:
            操作结果
        """
        params = {
            "compName": comp_name,
            "layerName": layer_name,
            "keyframes": keyframes,
            "expressions": expressions or {},
        }
        return self._execute("setKeyframeBatch", params)

    # ------------------------------------------------------------------------
    # 效果与预设
    # ------------------------------------------------------------------------

    def apply_effect(
        self,
        comp_name: str,
        layer_name: str,
        effect_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """应用效果到图层。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            effect_name: 效果名称
            properties: 效果属性初始值

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "layerName": layer_name,
            "effectName": effect_name,
        }
        if properties:
            params["properties"] = properties
        return self._execute("applyEffect", params)

    def batch_add_effects(
        self,
        comp_name: str,
        layer_name: str,
        effects: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """批量添加效果。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            effects: 效果列表，每项包含：
                - name: 效果名称
                - properties: 属性字典（可选）

        Returns:
            操作结果
        """
        return self._execute(
            "batchAddEffects",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "effects": effects,
            },
        )

    def apply_effect_template(
        self,
        comp_name: str,
        layer_name: str,
        template_name: str,
    ) -> Dict[str, Any]:
        """应用效果预设模板。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            template_name: 模板名称

        Returns:
            操作结果
        """
        return self._execute(
            "applyEffectTemplate",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "templateName": template_name,
            },
        )

    def remove_effect(
        self,
        comp_name: str,
        layer_name: str,
        effect_name: str,
    ) -> Dict[str, Any]:
        """移除效果。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            effect_name: 效果名称

        Returns:
            操作结果
        """
        return self._execute(
            "removeEffect",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "effectName": effect_name,
            },
        )

    def set_effect_property(
        self,
        comp_name: str,
        layer_name: str,
        effect_name: str,
        property_name: str,
        value: Any,
    ) -> Dict[str, Any]:
        """设置效果属性值。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            effect_name: 效果名称
            property_name: 属性名称
            value: 属性值

        Returns:
            操作结果
        """
        return self._execute(
            "setEffectProperty",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "effectName": effect_name,
                "propertyName": property_name,
                "value": value,
            },
        )

    # ------------------------------------------------------------------------
    # 遮罩与路径
    # ------------------------------------------------------------------------

    def create_mask(
        self,
        comp_name: str,
        layer_name: str,
        mask_name: Optional[str] = None,
        mask_path: Optional[List[List[float]]] = None,
        mask_mode: str = "add",
    ) -> Dict[str, Any]:
        """创建遮罩。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            mask_name: 遮罩名称
            mask_path: 遮罩路径点列表 [[x,y], ...]
            mask_mode: 遮罩模式 "add" | "subtract" | "intersect" | "lighten" | "darken" | "difference"

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "layerName": layer_name,
        }
        if mask_name:
            params["maskName"] = mask_name
        if mask_path is not None:
            params["maskPath"] = mask_path
        if mask_mode:
            params["maskMode"] = mask_mode
        return self._execute("createMask", params)

    def set_mask_property(
        self,
        comp_name: str,
        layer_name: str,
        mask_name: str,
        property_name: str,
        value: Any,
    ) -> Dict[str, Any]:
        """设置遮罩属性。

        Args:
            comp_name: 合成名称
            layer_name: 图层名称
            mask_name: 遮罩名称
            property_name: 属性名称
            value: 属性值

        Returns:
            操作结果
        """
        return self._execute(
            "setMaskProperty",
            {
                "compName": comp_name,
                "layerName": layer_name,
                "maskName": mask_name,
                "propertyName": property_name,
                "value": value,
            },
        )

    # ------------------------------------------------------------------------
    # 预合成
    # ------------------------------------------------------------------------

    def precompose(
        self,
        comp_name: str,
        layer_names: List[str],
        precomp_name: str = "Precomp",
        move_all_attributes: bool = True,
    ) -> Dict[str, Any]:
        """预合成所选图层。

        Args:
            comp_name: 合成名称
            layer_names: 要预合成的图层名称列表
            precomp_name: 预合成名称
            move_all_attributes: 是否移动所有属性

        Returns:
            操作结果
        """
        return self._execute(
            "precompose",
            {
                "compName": comp_name,
                "layerNames": layer_names,
                "precompName": precomp_name,
                "moveAllAttrs": move_all_attributes,
            },
        )

    # ------------------------------------------------------------------------
    # 素材管理
    # ------------------------------------------------------------------------

    def import_footage(
        self,
        file_path: str,
        name: Optional[str] = None,
        as_sequence: bool = False,
    ) -> Dict[str, Any]:
        """导入素材。

        Args:
            file_path: 素材文件路径
            name: 项目面板中的名称
            as_sequence: 是否作为序列帧导入

        Returns:
            导入结果
        """
        params: Dict[str, Any] = {
            "filePath": file_path,
            "importAsSequence": as_sequence,
        }
        if name:
            params["name"] = name
        return self._execute("importFootage", params)

    def add_layer_to_comp(
        self,
        comp_name: str,
        footage_name: str,
        layer_name: Optional[str] = None,
        start_time: float = 0.0,
    ) -> Dict[str, Any]:
        """将素材添加到合成。

        Args:
            comp_name: 合成名称
            footage_name: 素材名称
            layer_name: 图层名称
            start_time: 开始时间

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {
            "compName": comp_name,
            "footageName": footage_name,
        }
        if layer_name:
            params["layerName"] = layer_name
        if start_time != 0:
            params["startTime"] = start_time
        return self._execute("addLayerToComp", params)

    def replace_footage(
        self,
        old_footage_name: str,
        new_file_path: str,
    ) -> Dict[str, Any]:
        """替换素材。

        Args:
            old_footage_name: 旧素材名称
            new_file_path: 新文件路径

        Returns:
            操作结果
        """
        return self._execute(
            "replaceFootage",
            {
                "oldFootageName": old_footage_name,
                "newFilePath": new_file_path,
            },
        )

    # ------------------------------------------------------------------------
    # 脚本执行
    # ------------------------------------------------------------------------

    def execute_atom_script(self, script_content: str) -> Dict[str, Any]:
        """执行原子脚本（ExtendScript）。

        Args:
            script_content: JSX/ExtendScript 脚本内容

        Returns:
            脚本执行结果
        """
        return self._execute(
            "executeAtomScript",
            {"scriptContent": script_content},
            ttl=60000,
        )

    def run_script(self, script_path: str) -> Dict[str, Any]:
        """运行脚本文件。

        Args:
            script_path: 脚本文件路径

        Returns:
            脚本执行结果
        """
        return self._execute(
            "runScript",
            {"scriptPath": script_path},
            ttl=60000,
        )

    def execute_jsx(self, jsx_code: str) -> Any:
        """执行 JSX 代码并返回结果。

        与 execute_atom_script 类似，但自动包装为函数并解析返回值。

        Args:
            jsx_code: JSX 代码

        Returns:
            解析后的结果
        """
        wrapped = (
            "(function() {\n"
            "  try {\n"
            f"    var _result = {jsx_code};\n"
            "    return JSON.stringify({status: 'success', result: _result});\n"
            "  } catch (e) {\n"
            "    return JSON.stringify({status: 'error', message: e.toString()});\n"
            "  }\n"
            "})();"
        )
        return self.execute_atom_script(wrapped)

    # ------------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------------

    def add_to_render_queue(
        self,
        comp_name: str,
        output_path: Optional[str] = None,
        output_module: Optional[str] = None,
        render_settings: Optional[str] = None,
    ) -> Dict[str, Any]:
        """添加合成到渲染队列。

        Args:
            comp_name: 合成名称
            output_path: 输出路径
            output_module: 输出模块预设
            render_settings: 渲染设置预设

        Returns:
            操作结果
        """
        params: Dict[str, Any] = {"compName": comp_name}
        if output_path:
            params["outputPath"] = output_path
        if output_module:
            params["outputModule"] = output_module
        if render_settings:
            params["renderSettings"] = render_settings
        return self._execute("addToRenderQueue", params, ttl=120000)

    def start_render(self) -> Dict[str, Any]:
        """开始渲染队列。

        Returns:
            操作结果
        """
        return self._execute("startRender", {}, ttl=3600000)

    # ------------------------------------------------------------------------
    # 撤销/重做
    # ------------------------------------------------------------------------

    def undo(self) -> Dict[str, Any]:
        """撤销上一步操作。

        Returns:
            操作结果
        """
        return self._execute("undo")

    def redo(self) -> Dict[str, Any]:
        """重做上一步操作。

        Returns:
            操作结果
        """
        return self._execute("redo")

    # ------------------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------------------

    def get_stats(self) -> ClientStats:
        """获取客户端调用统计。

        Returns:
            统计信息对象
        """
        with self._stats_lock:
            return ClientStats(
                total_calls=self._stats.total_calls,
                success_count=self._stats.success_count,
                failure_count=self._stats.failure_count,
                total_latency_ms=self._stats.total_latency_ms,
                avg_latency_ms=self._stats.avg_latency_ms,
                min_latency_ms=self._stats.min_latency_ms,
                max_latency_ms=self._stats.max_latency_ms,
                last_call_time=self._stats.last_call_time,
            )

    def reset_stats(self) -> None:
        """重置统计信息。"""
        with self._stats_lock:
            self._stats = ClientStats()

    # ------------------------------------------------------------------------
    # 异步命令
    # ------------------------------------------------------------------------

    def send_command_async(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        priority: Optional[Priority] = None,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """异步发送命令，不等待结果。

        Args:
            command: 命令名称
            params: 命令参数
            ttl: 超时时间
            priority: 优先级
            idempotency_key: 幂等键

        Returns:
            command_id 命令ID
        """
        return self._bridge.send_command_async(
            command=command,
            params=params or {},
            ttl=ttl or self._default_ttl_ms,
            priority=priority,
            idempotency_key=idempotency_key,
        )

    def get_result(self, command_id: str) -> Optional[Dict[str, Any]]:
        """获取异步命令结果。

        Args:
            command_id: 命令ID

        Returns:
            结果字典，或 None 如果结果未就绪
        """
        response = self._bridge.get_result(command_id)
        if response is None:
            return None
        if response.is_success:
            return response.result or {}
        raise _raise_from_response_error(response)

    def wait_for_completion(
        self,
        command_id: str,
        timeout_ms: Optional[int] = None,
        progress_callback: Optional[Callable[[BridgeProgress], None]] = None,
    ) -> Dict[str, Any]:
        """等待异步命令完成。

        Args:
            command_id: 命令ID
            timeout_ms: 超时时间（毫秒）
            progress_callback: 进度回调

        Returns:
            命令结果

        Raises:
            AEMCPError: 命令执行失败
        """
        response = self._bridge.wait_for_result(
            command_id=command_id,
            timeout_ms=timeout_ms,
            progress_callback=progress_callback,
        )
        if response.is_success:
            return response.result or {}
        raise _raise_from_response_error(response)

    # ------------------------------------------------------------------------
    # 中间件管理
    # ------------------------------------------------------------------------

    def add_middleware(self, middleware) -> None:
        """添加自定义中间件到管道。

        Args:
            middleware: 中间件实例，需继承 Middleware 基类
        """
        if self._pipeline is None:
            self._pipeline = MiddlewarePipeline()
        self._pipeline.add(middleware)

    def remove_middleware(self, middleware_type: type) -> bool:
        """移除指定类型的中间件。

        Args:
            middleware_type: 中间件类型

        Returns:
            是否成功移除
        """
        if self._pipeline is None:
            return False
        return self._pipeline.remove(middleware_type)

    def disable_middleware(self) -> None:
        """禁用中间件管道。"""
        self._middleware_enabled = False
        self._pipeline = None

    def enable_middleware(self, max_requests_per_minute: int = 100) -> None:
        """启用中间件管道。

        Args:
            max_requests_per_minute: 每分钟最大请求数（限流）
        """
        self._middleware_enabled = True
        self._pipeline = self._create_default_pipeline(max_requests_per_minute)

    def export_metrics(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        """导出中间件收集的指标数据。

        Args:
            output_path: 可选输出文件路径

        Returns:
            指标数据字典
        """
        if self._metrics_middleware is not None:
            return self._metrics_middleware.export_metrics(output_path)
        return {
            "error": "Metrics middleware not available",
            "client_stats": self.get_stats().__dict__,
        }

    # ------------------------------------------------------------------------
    # 属性访问
    # ------------------------------------------------------------------------

    @property
    def bridge(self) -> BridgeClient:
        """底层 BridgeClient 实例。"""
        return self._bridge

    @property
    def bridge_dir(self) -> Path:
        """桥接目录路径。"""
        return self._bridge.bridge_dir

    @property
    def middleware_enabled(self) -> bool:
        """中间件管道是否启用。"""
        return self._middleware_enabled


# ============================================================================
# 流式构建接口
# ============================================================================


class CompositionBuilder:
    """合成流式构建器。

    使用链式调用构建完整的合成结构。

    示例：
        builder = CompositionBuilder(client, "MyComp")
        comp = (
            builder
            .size(1920, 1080)
            .duration(10)
            .fps(30)
            .bg_color([0, 0, 0])
            .add_text_layer("Title", "Hello World")
            .add_solid_layer("BG", [0.2, 0.2, 0.2])
            .build()
        )
    """

    def __init__(
        self,
        client: AEMCPClient,
        name: str,
    ) -> None:
        """初始化合成构建器。

        Args:
            client: AE MCP 客户端实例
            name: 合成名称
        """
        self._client = client
        self._name = name
        self._width: int = 1920
        self._height: int = 1080
        self._duration: float = 10.0
        self._fps: float = 30.0
        self._bg_color: List[float] = [0.0, 0.0, 0.0]
        self._layers: List[Tuple[str, Dict[str, Any]]] = []
        self._effects: List[Tuple[str, str, Dict[str, Any]]] = []

    def size(self, width: int, height: int) -> "CompositionBuilder":
        """设置合成尺寸。

        Args:
            width: 宽度
            height: 高度

        Returns:
            self
        """
        self._width = width
        self._height = height
        return self

    def duration(self, duration: float) -> "CompositionBuilder":
        """设置合成时长。

        Args:
            duration: 时长（秒）

        Returns:
            self
        """
        self._duration = duration
        return self

    def fps(self, fps: float) -> "CompositionBuilder":
        """设置合成帧率。

        Args:
            fps: 帧率

        Returns:
            self
        """
        self._fps = fps
        return self

    def bg_color(self, color: List[float]) -> "CompositionBuilder":
        """设置背景色。

        Args:
            color: 背景色 [r, g, b]

        Returns:
            self
        """
        self._bg_color = color
        return self

    def add_text_layer(
        self,
        name: str,
        text: str,
        font_family: Optional[str] = None,
        font_size: Optional[float] = None,
        fill_color: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
    ) -> "CompositionBuilder":
        """添加文字图层。

        Args:
            name: 图层名称
            text: 文字内容
            font_family: 字体族
            font_size: 字体大小
            fill_color: 填充色
            position: 位置

        Returns:
            self
        """
        params: Dict[str, Any] = {"text": text}
        if font_family:
            params["fontFamily"] = font_family
        if font_size is not None:
            params["fontSize"] = font_size
        if fill_color is not None:
            params["fillColor"] = fill_color
        if position is not None:
            params["position"] = position
        self._layers.append(("text", {"layer_name": name, **params}))
        return self

    def add_shape_layer(
        self,
        name: str,
        shape_type: str = "rect",
        fill_color: Optional[List[float]] = None,
        stroke_color: Optional[List[float]] = None,
        stroke_width: Optional[float] = None,
        size: Optional[List[float]] = None,
        position: Optional[List[float]] = None,
    ) -> "CompositionBuilder":
        """添加形状图层。

        Args:
            name: 图层名称
            shape_type: 形状类型
            fill_color: 填充色
            stroke_color: 描边色
            stroke_width: 描边宽度
            size: 尺寸
            position: 位置

        Returns:
            self
        """
        params: Dict[str, Any] = {"shapeType": shape_type}
        if fill_color is not None:
            params["fillColor"] = fill_color
        if stroke_color is not None:
            params["strokeColor"] = stroke_color
        if stroke_width is not None:
            params["strokeWidth"] = stroke_width
        if size is not None:
            params["size"] = size
        if position is not None:
            params["position"] = position
        self._layers.append(("shape", {"layer_name": name, **params}))
        return self

    def add_solid_layer(
        self,
        name: str,
        color: Optional[List[float]] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> "CompositionBuilder":
        """添加固态层。

        Args:
            name: 图层名称
            color: 颜色
            width: 宽度
            height: 高度

        Returns:
            self
        """
        params: Dict[str, Any] = {}
        if color is not None:
            params["color"] = color
        if width is not None:
            params["width"] = width
        if height is not None:
            params["height"] = height
        self._layers.append(("solid", {"layer_name": name, **params}))
        return self

    def add_adjustment_layer(self, name: str) -> "CompositionBuilder":
        """添加调整图层。

        Args:
            name: 图层名称

        Returns:
            self
        """
        self._layers.append(("adjustment", {"layer_name": name}))
        return self

    def add_null_layer(self, name: str) -> "CompositionBuilder":
        """添加空对象图层。

        Args:
            name: 图层名称

        Returns:
            self
        """
        self._layers.append(("null", {"layer_name": name}))
        return self

    def build(self) -> Dict[str, Any]:
        """执行构建，创建合成及所有图层。

        Returns:
            包含合成信息和图层信息的字典
        """
        comp_result = self._client.create_composition(
            name=self._name,
            width=self._width,
            height=self._height,
            duration=self._duration,
            frame_rate=self._fps,
            bg_color=self._bg_color,
        )

        layer_results = []
        for layer_type, params in self._layers:
            try:
                if layer_type == "text":
                    result = self._client.create_text_layer(
                        comp_name=self._name,
                        text=params.pop("text"),
                        **params,
                    )
                elif layer_type == "shape":
                    result = self._client.create_shape_layer(
                        comp_name=self._name,
                        shape_type=params.pop("shapeType"),
                        **params,
                    )
                elif layer_type == "solid":
                    result = self._client.create_solid_layer(
                        comp_name=self._name,
                        **params,
                    )
                elif layer_type == "adjustment":
                    result = self._client.add_adjustment_layer(
                        comp_name=self._name,
                        **params,
                    )
                elif layer_type == "null":
                    result = self._client.create_null_layer(
                        comp_name=self._name,
                        **params,
                    )
                else:
                    continue
                layer_results.append(result)
            except Exception as e:
                logger.warning(f"创建图层 {params.get('layer_name', 'unknown')} 失败: {e}")
                layer_results.append({"error": str(e)})

        return {
            "composition": comp_result,
            "layers": layer_results,
        }


class LayerBuilder:
    """图层流式构建器。

    使用链式调用配置图层属性、动画、效果等。

    示例：
        builder = LayerBuilder(client, "MyComp", "Text Layer")
        result = (
            builder
            .position([960, 540])
            .scale([100, 100])
            .opacity(100)
            .blend_mode(BlendMode.NORMAL)
            .keyframe("Position", 0, [0, 540])
            .keyframe("Position", 2, [1920, 540], easing=EasingType.EASE_IN_OUT)
            .expression("Rotation", "time * 50")
            .apply_effect("高斯模糊", {"Blurriness": 10})
            .build()
        )
    """

    def __init__(
        self,
        client: AEMCPClient,
        comp_name: str,
        layer_name: str,
    ) -> None:
        """初始化图层构建器。

        Args:
            client: AE MCP 客户端
            comp_name: 合成名称
            layer_name: 图层名称
        """
        self._client = client
        self._comp_name = comp_name
        self._layer_name = layer_name
        self._properties: Dict[str, Any] = {}
        self._blend_mode: Optional[Union[BlendMode, str]] = None
        self._keyframes: List[Dict[str, Any]] = []
        self._expressions: Dict[str, str] = {}
        self._effects: List[Dict[str, Any]] = []
        self._parent: Optional[str] = None
        self._track_matte: Optional[Tuple[str, TrackMatteType]] = None
        self._motion_blur: Optional[bool] = None

    def position(self, value: List[float]) -> "LayerBuilder":
        """设置位置。

        Args:
            value: 位置 [x, y] 或 [x, y, z]

        Returns:
            self
        """
        self._properties["position"] = value
        return self

    def anchor_point(self, value: List[float]) -> "LayerBuilder":
        """设置锚点。

        Args:
            value: 锚点 [x, y]

        Returns:
            self
        """
        self._properties["anchorPoint"] = value
        return self

    def scale(self, value: List[float]) -> "LayerBuilder":
        """设置缩放。

        Args:
            value: 缩放 [x, y] 百分比

        Returns:
            self
        """
        self._properties["scale"] = value
        return self

    def rotation(self, value: float) -> "LayerBuilder":
        """设置旋转。

        Args:
            value: 旋转角度

        Returns:
            self
        """
        self._properties["rotation"] = value
        return self

    def opacity(self, value: float) -> "LayerBuilder":
        """设置不透明度。

        Args:
            value: 不透明度 0-100

        Returns:
            self
        """
        self._properties["opacity"] = value
        return self

    def start_time(self, value: float) -> "LayerBuilder":
        """设置开始时间。

        Args:
            value: 开始时间（秒）

        Returns:
            self
        """
        self._properties["startTime"] = value
        return self

    def enabled(self, value: bool) -> "LayerBuilder":
        """设置是否启用。

        Args:
            value: 是否启用

        Returns:
            self
        """
        self._properties["enabled"] = value
        return self

    def blend_mode(self, mode: Union[BlendMode, str]) -> "LayerBuilder":
        """设置混合模式。

        Args:
            mode: 混合模式

        Returns:
            self
        """
        self._blend_mode = mode
        return self

    def parent(self, parent_layer: str) -> "LayerBuilder":
        """设置父图层。

        Args:
            parent_layer: 父图层名称

        Returns:
            self
        """
        self._parent = parent_layer
        return self

    def track_matte(
        self,
        matte_layer: str,
        matte_type: Union[TrackMatteType, str] = TrackMatteType.ALPHA,
    ) -> "LayerBuilder":
        """设置轨道遮罩。

        Args:
            matte_layer: 遮罩图层
            matte_type: 遮罩类型

        Returns:
            self
        """
        self._track_matte = (matte_layer, matte_type)
        return self

    def motion_blur(self, enabled: bool = True) -> "LayerBuilder":
        """设置运动模糊。

        Args:
            enabled: 是否启用

        Returns:
            self
        """
        self._motion_blur = enabled
        return self

    def keyframe(
        self,
        property_name: str,
        time: float,
        value: Any,
        easing: Optional[Union[EasingType, str]] = None,
    ) -> "LayerBuilder":
        """添加关键帧。

        Args:
            property_name: 属性名称
            time: 时间（秒）
            value: 属性值
            easing: 缓动类型

        Returns:
            self
        """
        kf: Dict[str, Any] = {
            "property": property_name,
            "time": time,
            "value": value,
        }
        if easing:
            kf["easeType"] = easing.value if isinstance(easing, EasingType) else easing
        self._keyframes.append(kf)
        return self

    def expression(self, property_name: str, expression: str) -> "LayerBuilder":
        """添加表达式。

        Args:
            property_name: 属性名称
            expression: 表达式字符串

        Returns:
            self
        """
        self._expressions[property_name] = expression
        return self

    def apply_effect(
        self,
        effect_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> "LayerBuilder":
        """应用效果。

        Args:
            effect_name: 效果名称
            properties: 效果属性

        Returns:
            self
        """
        self._effects.append({"name": effect_name, "properties": properties or {}})
        return self

    def build(self) -> Dict[str, Any]:
        """执行构建，应用所有配置。

        Returns:
            包含所有操作结果的字典
        """
        results: Dict[str, Any] = {}

        if self._properties:
            results["properties"] = self._client.set_layer_properties(
                comp_name=self._comp_name,
                layer_name=self._layer_name,
                properties=self._properties,
            )

        if self._blend_mode is not None:
            results["blend_mode"] = self._client.set_blend_mode(
                comp_name=self._comp_name,
                layer_name=self._layer_name,
                blend_mode=self._blend_mode,
            )

        if self._parent is not None:
            results["parent"] = self._client.set_parent_layer(
                comp_name=self._comp_name,
                child_layer=self._layer_name,
                parent_layer=self._parent,
            )

        if self._track_matte is not None:
            matte_layer, matte_type = self._track_matte
            results["track_matte"] = self._client.set_track_matte(
                comp_name=self._comp_name,
                target_layer=self._layer_name,
                matte_layer=matte_layer,
                matte_type=matte_type,
            )

        if self._motion_blur is not None:
            results["motion_blur"] = self._client.set_motion_blur(
                comp_name=self._comp_name,
                layer_name=self._layer_name,
                enabled=self._motion_blur,
            )

        if self._keyframes or self._expressions:
            results["keyframes"] = self._client.set_keyframe_batch(
                comp_name=self._comp_name,
                layer_name=self._layer_name,
                keyframes=self._keyframes,
                expressions=self._expressions,
            )

        if self._effects:
            results["effects"] = []
            for effect in self._effects:
                try:
                    result = self._client.apply_effect(
                        comp_name=self._comp_name,
                        layer_name=self._layer_name,
                        effect_name=effect["name"],
                        properties=effect.get("properties"),
                    )
                    results["effects"].append(result)
                except Exception as e:
                    results["effects"].append({"error": str(e)})

        return results


class EffectStack:
    """效果栈管理器。

    管理图层上的多个效果，支持链式添加效果。

    示例：
        stack = EffectStack(client, "MyComp", "MyLayer")
        result = (
            stack
            .add("高斯模糊", {"Blurriness": 5})
            .add("色阶", {"Input Black": 10})
            .add("曲线")
            .apply()
        )
    """

    def __init__(
        self,
        client: AEMCPClient,
        comp_name: str,
        layer_name: str,
    ) -> None:
        """初始化效果栈。

        Args:
            client: AE MCP 客户端
            comp_name: 合成名称
            layer_name: 图层名称
        """
        self._client = client
        self._comp_name = comp_name
        self._layer_name = layer_name
        self._effects: List[Dict[str, Any]] = []

    def add(
        self,
        effect_name: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> "EffectStack":
        """添加效果到栈。

        Args:
            effect_name: 效果名称
            properties: 效果属性

        Returns:
            self
        """
        effect: Dict[str, Any] = {"name": effect_name}
        if properties:
            effect["properties"] = properties
        self._effects.append(effect)
        return self

    def remove(self, effect_name: str) -> "EffectStack":
        """移除指定名称的效果（从栈中移除，不执行）。

        Args:
            effect_name: 效果名称

        Returns:
            self
        """
        self._effects = [e for e in self._effects if e["name"] != effect_name]
        return self

    def clear(self) -> "EffectStack":
        """清空效果栈。

        Returns:
            self
        """
        self._effects.clear()
        return self

    def apply(self) -> Dict[str, Any]:
        """批量应用所有效果到图层。

        Returns:
            操作结果
        """
        return self._client.batch_add_effects(
            comp_name=self._comp_name,
            layer_name=self._layer_name,
            effects=self._effects,
        )

    def list_effects(self) -> List[EffectInfo]:
        """列出当前图层上的所有效果。

        Returns:
            效果信息列表
        """
        return self._client.list_effects(self._comp_name, self._layer_name)


# ============================================================================
# 便捷函数
# ============================================================================


def create_client(
    bridge_dir: Optional[str] = None,
    **kwargs: Any,
) -> AEMCPClient:
    """创建 AE MCP 客户端的便捷函数。

    Args:
        bridge_dir: 桥接目录，默认使用标准路径
        **kwargs: 传递给 AEMCPClient 的其他参数

    Returns:
        AEMCPClient 实例
    """
    if bridge_dir is None:
        bridge_dir = _DEFAULT_BRIDGE_DIR
    return AEMCPClient(bridge_dir=bridge_dir, **kwargs)


__all__ = [
    "AEMCPClient",
    "AEMCPError",
    "AEConnectionError",
    "AECommandError",
    "AETimeoutError",
    "AENotFoundError",
    "CompositionBuilder",
    "LayerBuilder",
    "EffectStack",
    "BlendMode",
    "TrackMatteType",
    "EasingType",
    "CompositionInfo",
    "LayerInfo",
    "EffectInfo",
    "KeyframeInfo",
    "ClientStats",
    "create_client",
]
