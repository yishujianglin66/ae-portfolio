"""
Photoshop MCP 客户端封装 v1.0
============================

基于 Bridge 协议的高质量 Photoshop MCP 客户端封装。

提供：
- 完整的类型注解与文档字符串
- 20+ MCP 工具方法封装
- 自定义异常体系
- 自动重试与降级策略
- 连接状态监控与心跳检测
- 调用统计与性能指标

协议兼容：
- 开源 photoshop-mcp 项目命令格式（camelCase）
- bridge_protocol.py BridgeClient v2.0

使用示例：
    from ae.ps_mcp_client import PSMDPClient, DocumentInfo

    client = PSMDPClient(bridge_dir="C:/Users/.../ps-mcp-bridge")
    client.ping()

    # 创建文档
    doc = client.create_document("MyDoc", 1920, 1080)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

from ae.archive.bridge_middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    MiddlewarePipeline,
    RateLimitMiddleware,
    RetryMiddleware,
    ValidationMiddleware,
)
from ae.archive.bridge_protocol import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TTL_MS,
    BridgeClient,
    BridgeCommand,
    BridgeMetadata,
    BridgeProgress,
    BridgeResponse,
    CommandStatus,
    ErrorCode,
    Priority,
)

# Bridge 默认目录收口到 core/paths.py（AEK_PS_BRIDGE_DIR 可覆盖）
try:
    from core.paths import ps_bridge_dir as _paths_ps_bridge
    _DEFAULT_BRIDGE_DIR = _paths_ps_bridge()
except ImportError:
    _DEFAULT_BRIDGE_DIR = r"C:\Users\Administrator\Documents\ps-mcp-bridge"

logger = logging.getLogger(__name__)


# ============================================================================
# 自定义异常体系
# ============================================================================


class PSMCPError(Exception):
    """PS MCP 客户端基础异常。

    Attributes:
        message: 错误消息
        error_code: 错误码
        details: 详细错误信息
    """

    def __init__(
        self,
        message: str = "PS MCP 操作失败",
        error_code: ErrorCode | None = None,
        details: dict[str, Any] | None = None,
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


class PSConnectionError(PSMCPError):
    """PS 连接异常。

    当无法连接到 Photoshop 或桥接通信失败时抛出。
    """

    pass


class PSCommandError(PSMCPError):
    """PS 命令执行异常。

    当 PS 端命令执行失败时抛出。
    """

    pass


class PSTimeoutError(PSMCPError):
    """PS 命令超时异常。

    当命令执行超时时抛出。
    """

    pass


class PSNotFoundError(PSMCPError):
    """PS 资源不存在异常。

    当文档、图层等资源不存在时抛出。
    """

    pass


# ============================================================================
# 错误码到异常的映射
# ============================================================================

_ERROR_CODE_TO_EXCEPTION: dict[ErrorCode, type[PSMCPError]] = {
    ErrorCode.AE_NOT_RUNNING: PSConnectionError,
    ErrorCode.AE_NOT_RESPONDING: PSConnectionError,
    ErrorCode.IO_ERROR: PSConnectionError,
    ErrorCode.NETWORK_ERROR: PSConnectionError,
    ErrorCode.LOCK_ACQUISITION_FAILED: PSConnectionError,
    ErrorCode.SCRIPT_TIMEOUT: PSTimeoutError,
    ErrorCode.RESOURCE_NOT_FOUND: PSNotFoundError,
    ErrorCode.SCRIPT_EXECUTION_ERROR: PSCommandError,
    ErrorCode.INVALID_PARAMETER: PSCommandError,
    ErrorCode.OPERATION_NOT_SUPPORTED: PSCommandError,
}


def _raise_from_response_error(response: BridgeResponse) -> PSMCPError:
    """从 BridgeResponse 创建对应的异常。

    Args:
        response: 失败的响应对象

    Returns:
        对应的 PSMCPError 子类实例
    """
    error = response.error
    if not error:
        return PSMCPError("未知错误")

    exc_class = _ERROR_CODE_TO_EXCEPTION.get(error.code, PSMCPError)
    return exc_class(
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


# ============================================================================
# 数据结构定义
# ============================================================================


@dataclass
class DocumentInfo:
    """文档信息。"""

    id: int
    name: str
    width: int
    height: int
    resolution: float
    color_mode: str
    num_layers: int


@dataclass
class LayerInfo:
    """图层信息。"""

    index: int
    name: str
    type: str
    visible: bool
    locked: bool
    opacity: int


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
    last_call_time: float | None = None


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


class ColorMode(str, Enum):
    """颜色模式。"""

    RGB = "RGB"
    CMYK = "CMYK"
    LAB = "LAB"
    GRAYSCALE = "GRAYSCALE"
    BITMAP = "BITMAP"
    INDEXED = "INDEXED"


# ============================================================================
# PSMDPClient 主类
# ============================================================================


class PSMDPClient:
    """Photoshop MCP 客户端。

    基于 BridgeClient 的高级封装，提供：
    - 自动检测 PS 运行状态
    - 连接状态监控
    - 自动重试与降级
    - 20+ MCP 工具方法
    - 中间件管道支持（日志、指标、限流、验证、重试）
    - 安全机制（HMAC-SHA256 响应签名验证、重放攻击防护、命令注入防护）

    示例：
        client = PSMDPClient(bridge_dir="C:/path/to/bridge")
        client.ping()
        docs = client.list_documents()
    """

    def __init__(
        self,
        bridge_dir: str = _DEFAULT_BRIDGE_DIR,
        signature_enabled: bool = True,
        secret: str | None = None,
        secret_file: str | None = None,
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
        middleware_pipeline: MiddlewarePipeline | None = None,
        enforce_response_signature: bool = False,
        anti_replay_window_seconds: int = 300,
    ) -> None:
        """初始化 PS MCP 客户端。

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
        self._last_heartbeat_time: float | None = None
        self._heartbeat_interval: float = 30.0

        self._middleware_enabled = enable_middleware
        self._metrics_middleware: MetricsMiddleware | None = None

        if enable_middleware:
            if middleware_pipeline is not None:
                self._pipeline = middleware_pipeline
            else:
                self._pipeline = self._create_default_pipeline(max_requests_per_minute)
        else:
            self._pipeline = None

        self._enforce_response_signature = enforce_response_signature
        self._anti_replay_window = anti_replay_window_seconds
        self._seen_command_ids: dict[str, float] = {}
        self._anti_replay_lock = threading.Lock()

    def _create_default_pipeline(self, max_requests_per_minute: int) -> MiddlewarePipeline:
        """创建默认中间件管道。"""
        pipeline = MiddlewarePipeline()
        pipeline.add(LoggingMiddleware())
        pipeline.add(RateLimitMiddleware(max_requests=max_requests_per_minute, window_seconds=60))
        pipeline.add(ValidationMiddleware())
        pipeline.add(RetryMiddleware(max_retries=2, base_delay_ms=100, max_delay_ms=3000))

        self._metrics_middleware = MetricsMiddleware()
        pipeline.add(self._metrics_middleware)

        return pipeline

    def _verify_response_signature(self, response: BridgeResponse) -> bool:
        """验证响应签名。"""
        if not self._enforce_response_signature:
            return True

        secret = self._bridge._secret
        if not secret:
            if self._enforce_response_signature:
                raise PSMCPError("响应签名验证已启用，但未配置密钥")
            return True

        if not response.signature:
            if self._enforce_response_signature:
                raise PSMCPError("响应缺少签名")
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
                raise PSMCPError("响应签名验证失败")
            return False

        return True

    def _check_replay_attack(self, command_id: str) -> bool:
        """检查是否为重放攻击。"""
        if self._anti_replay_window <= 0:
            return False

        now = time.time()

        with self._anti_replay_lock:
            if command_id in self._seen_command_ids:
                timestamp = self._seen_command_ids[command_id]
                if now - timestamp < self._anti_replay_window:
                    raise PSMCPError(f"检测到重放攻击: {command_id}")

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
        params: dict[str, Any] | None = None,
        ttl: int | None = None,
        priority: Priority | None = None,
        idempotency_key: str | None = None,
        metadata: BridgeMetadata | None = None,
        progress_callback: Callable[[BridgeProgress], None] | None = None,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
        """执行命令并返回结果。"""
        start_time = time.time()

        cmd_data = {
            "command": command,
            "params": params or {},
            "ttl": ttl or self._default_ttl_ms,
            "priority": priority,
            "idempotency_key": idempotency_key,
        }

        def _bridge_handler(cmd: dict[str, Any]) -> BridgeResponse:
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

        except PSMCPError:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(False, latency_ms)
            raise PSCommandError(f"命令执行异常: {e}") from e

    def _update_stats(self, success: bool, latency_ms: float) -> None:
        """更新调用统计。"""
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

    def ping(self) -> dict[str, Any]:
        """检测 PS 是否存活。

        Returns:
            包含 pong 状态和 PS 版本信息的字典

        Raises:
            PSConnectionError: PS 未运行或无响应
        """
        try:
            result = self._execute("ping", {})
            self._last_heartbeat_time = time.time()
            return result
        except PSMCPError:
            self._last_heartbeat_time = None
            raise

    def is_alive(self) -> bool:
        """检查 PS 是否存活（心跳检测）。

        使用一段很短的 TTL 探测，避免在 PS 未运行时等待默认的 30s TTL，
        从而快速（毫秒级）返回 False。

        Returns:
            PS 是否运行中且响应正常
        """
        try:
            self._execute("ping", {}, ttl=1000, raise_on_error=False)
            self._last_heartbeat_time = time.time()
            return True
        except Exception:
            return False

    def wait_for_ps(
        self,
        timeout: float = 60.0,
        check_interval: float = 2.0,
    ) -> bool:
        """等待 PS 启动并就绪。

        Args:
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            PS 是否在超时前就绪
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

    def get_document_info(self) -> dict[str, Any]:
        """获取当前文档信息。

        Returns:
            包含文档名称、尺寸、分辨率等信息
        """
        return self._execute("getDocumentInfo")

    def list_documents(self) -> list[DocumentInfo]:
        """列出所有打开的文档。

        Returns:
            文档信息列表
        """
        result = self._execute("listDocuments")
        docs = result.get("documents", [])
        return [
            DocumentInfo(
                id=d["id"],
                name=d["name"],
                width=d["width"],
                height=d["height"],
                resolution=d["resolution"],
                color_mode=d["colorMode"],
                num_layers=d["numLayers"],
            )
            for d in docs
        ]

    def get_layer_info(
        self,
        document_name: str,
        layer_name: str | None = None,
    ) -> Union[LayerInfo, list[LayerInfo]]:
        """获取图层信息。

        Args:
            document_name: 文档名称
            layer_name: 图层名称（None 时返回所有图层）

        Returns:
            单个或多个图层信息
        """
        params = {"documentName": document_name}
        if layer_name:
            params["layerName"] = layer_name

        result = self._execute("getLayerInfo", params)

        if layer_name:
            layer = result.get("layer", {})
            return LayerInfo(
                index=layer.get("index", 0),
                name=layer.get("name", ""),
                type=layer.get("type", ""),
                visible=layer.get("visible", True),
                locked=layer.get("locked", False),
                opacity=layer.get("opacity", 100),
            )
        else:
            layers = result.get("layers", [])
            return [
                LayerInfo(
                    index=l.get("index", 0),
                    name=l.get("name", ""),
                    type=l.get("type", ""),
                    visible=l.get("visible", True),
                    locked=l.get("locked", False),
                    opacity=l.get("opacity", 100),
                )
                for l in layers
            ]

    # ------------------------------------------------------------------------
    # 文档管理
    # ------------------------------------------------------------------------

    def create_document(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        resolution: float = 72.0,
        color_mode: str = "RGB",
        background_color: list[float] | None = None,
    ) -> dict[str, Any]:
        """创建新文档。

        Args:
            name: 文档名称
            width: 宽度（像素）
            height: 高度（像素）
            resolution: 分辨率（dpi）
            color_mode: 颜色模式（RGB/CMYK/LAB/GRAYSCALE）
            background_color: 背景色 [r, g, b]，0-1 范围

        Returns:
            新文档信息
        """
        params = {
            "name": name,
            "width": width,
            "height": height,
            "resolution": resolution,
            "colorMode": color_mode,
        }
        if background_color is not None:
            params["backgroundColor"] = background_color
        return self._execute("createDocument", params)

    def open_document(self, file_path: str) -> dict[str, Any]:
        """打开文档。

        Args:
            file_path: 文件路径

        Returns:
            文档信息
        """
        return self._execute("openDocument", {"filePath": file_path})

    def close_document(self, document_name: str, save_changes: bool = False) -> dict[str, Any]:
        """关闭文档。

        Args:
            document_name: 文档名称
            save_changes: 是否保存更改

        Returns:
            操作结果
        """
        return self._execute(
            "closeDocument",
            {"documentName": document_name, "saveChanges": save_changes},
        )

    def save_document(self, document_name: str, file_path: str | None = None) -> dict[str, Any]:
        """保存文档。

        Args:
            document_name: 文档名称
            file_path: 保存路径（None 时保存到原路径）

        Returns:
            操作结果
        """
        params: dict[str, Any] = {"documentName": document_name}
        if file_path:
            params["filePath"] = file_path
        return self._execute("saveDocument", params)

    def export_document(
        self,
        document_name: str,
        file_path: str,
        format: str = "PNG",
        quality: int = 100,
    ) -> dict[str, Any]:
        """导出文档。

        Args:
            document_name: 文档名称
            file_path: 输出路径
            format: 导出格式（PNG/JPEG/PSD/PDF/SVG）
            quality: 导出质量（0-100）

        Returns:
            导出结果
        """
        return self._execute(
            "exportDocument",
            {
                "documentName": document_name,
                "filePath": file_path,
                "format": format,
                "quality": quality,
            },
        )

    # ------------------------------------------------------------------------
    # 图层操作
    # ------------------------------------------------------------------------

    def create_layer(
        self,
        document_name: str,
        layer_name: str | None = None,
        layer_type: str = "pixel",
    ) -> dict[str, Any]:
        """创建图层。

        Args:
            document_name: 文档名称
            layer_name: 图层名称
            layer_type: 图层类型（pixel/shape/text/adjustment/smart_object）

        Returns:
            新建图层信息
        """
        params: dict[str, Any] = {
            "documentName": document_name,
            "layerType": layer_type,
        }
        if layer_name:
            params["layerName"] = layer_name
        return self._execute("createLayer", params)

    def delete_layer(self, document_name: str, layer_name: str) -> dict[str, Any]:
        """删除图层。

        Args:
            document_name: 文档名称
            layer_name: 图层名称

        Returns:
            操作结果
        """
        return self._execute(
            "deleteLayer",
            {"documentName": document_name, "layerName": layer_name},
        )

    def duplicate_layer(
        self,
        document_name: str,
        layer_name: str,
        new_name: str | None = None,
    ) -> dict[str, Any]:
        """复制图层。

        Args:
            document_name: 文档名称
            layer_name: 源图层名称
            new_name: 新图层名称

        Returns:
            新图层信息
        """
        params = {
            "documentName": document_name,
            "layerName": layer_name,
        }
        if new_name:
            params["newName"] = new_name
        return self._execute("duplicateLayer", params)

    def set_layer_properties(
        self,
        document_name: str,
        layer_name: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """设置图层属性。

        Args:
            document_name: 文档名称
            layer_name: 图层名称
            properties: 属性字典，支持的键：
                - position: [x, y]
                - opacity: 不透明度 0-100
                - visible: 是否可见
                - locked: 是否锁定

        Returns:
            操作结果
        """
        return self._execute(
            "setLayerProperties",
            {
                "documentName": document_name,
                "layerName": layer_name,
                "properties": properties,
            },
        )

    def set_blend_mode(
        self,
        document_name: str,
        layer_name: str,
        blend_mode: Union[BlendMode, str],
    ) -> dict[str, Any]:
        """设置图层混合模式。

        Args:
            document_name: 文档名称
            layer_name: 图层名称
            blend_mode: 混合模式

        Returns:
            操作结果
        """
        mode = blend_mode.value if isinstance(blend_mode, BlendMode) else blend_mode
        return self._execute(
            "setBlendMode",
            {
                "documentName": document_name,
                "layerName": layer_name,
                "blendMode": mode,
            },
        )

    # ------------------------------------------------------------------------
    # 滤镜应用
    # ------------------------------------------------------------------------

    def apply_filter(
        self,
        document_name: str,
        layer_name: str,
        filter_name: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """应用滤镜。

        Args:
            document_name: 文档名称
            layer_name: 图层名称
            filter_name: 滤镜名称
            properties: 滤镜属性初始值

        Returns:
            操作结果
        """
        params: dict[str, Any] = {
            "documentName": document_name,
            "layerName": layer_name,
            "filterName": filter_name,
        }
        if properties:
            params["properties"] = properties
        return self._execute("applyFilter", params)

    def remove_filter(self, document_name: str, layer_name: str, filter_name: str) -> dict[str, Any]:
        """移除滤镜。

        Args:
            document_name: 文档名称
            layer_name: 图层名称
            filter_name: 滤镜名称

        Returns:
            操作结果
        """
        return self._execute(
            "removeFilter",
            {
                "documentName": document_name,
                "layerName": layer_name,
                "filterName": filter_name,
            },
        )

    # ------------------------------------------------------------------------
    # 选区与填充
    # ------------------------------------------------------------------------

    def create_selection(
        self,
        document_name: str,
        top: int = 0,
        left: int = 0,
        width: int = 100,
        height: int = 100,
    ) -> dict[str, Any]:
        """创建选区。

        Args:
            document_name: 文档名称
            top: 选区顶部位置
            left: 选区左侧位置
            width: 选区宽度
            height: 选区高度

        Returns:
            操作结果
        """
        return self._execute(
            "createSelection",
            {
                "documentName": document_name,
                "top": top,
                "left": left,
                "width": width,
                "height": height,
            },
        )

    def fill_selection(
        self,
        document_name: str,
        color: list[float],
        blend_mode: str = "NORMAL",
        opacity: int = 100,
    ) -> dict[str, Any]:
        """填充选区。

        Args:
            document_name: 文档名称
            color: 填充颜色 [r, g, b]，0-1 范围
            blend_mode: 混合模式
            opacity: 不透明度 0-100

        Returns:
            操作结果
        """
        return self._execute(
            "fillSelection",
            {
                "documentName": document_name,
                "color": color,
                "blendMode": blend_mode,
                "opacity": opacity,
            },
        )

    # ------------------------------------------------------------------------
    # 撤销/重做
    # ------------------------------------------------------------------------

    def undo(self) -> dict[str, Any]:
        """撤销上一步操作。"""
        return self._execute("undo", {})

    def redo(self) -> dict[str, Any]:
        """重做上一步操作。"""
        return self._execute("redo", {})

    # ------------------------------------------------------------------------
    # 脚本执行
    # ------------------------------------------------------------------------

    def execute_script(self, script_content: str) -> dict[str, Any]:
        """执行 ExtendScript 脚本。

        Args:
            script_content: JavaScript 脚本内容

        Returns:
            脚本执行结果
        """
        return self._execute("executeScript", {"scriptContent": script_content})

    # ------------------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------------------

    @property
    def stats(self) -> ClientStats:
        """客户端统计信息。"""
        with self._stats_lock:
            return self._stats

    def get_stats_dict(self) -> dict[str, Any]:
        """获取统计信息字典。"""
        s = self.stats
        return {
            "total_calls": s.total_calls,
            "success_count": s.success_count,
            "failure_count": s.failure_count,
            "success_rate": s.success_count / s.total_calls if s.total_calls > 0 else 0,
            "avg_latency_ms": round(s.avg_latency_ms, 2),
            "min_latency_ms": round(s.min_latency_ms, 2),
            "max_latency_ms": round(s.max_latency_ms, 2),
            "last_call_time": s.last_call_time,
        }
