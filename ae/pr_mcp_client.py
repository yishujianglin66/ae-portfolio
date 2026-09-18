"""
Premiere Pro MCP 客户端封装
==========================

基于 Bridge 协议的 Premiere Pro MCP 客户端封装。

提供：
- 完整的类型注解与文档字符串
- 项目操作（新建、打开、保存、关闭）
- 序列操作（创建、列表、删除）
- 剪辑操作（导入素材、添加到序列、剪切、分割）
- 效果操作（应用效果、调整参数）
- 转场效果（30+转场类型，高级转场支持）
- 高级剪辑（拉镜、缩放、速度调整、关键帧动画）
- 渲染导出
- 自定义异常体系
- 连接状态监控与心跳检测

协议兼容：
- 基于 bridge_protocol.py BridgeClient v2.0
- 使用 file polling 机制
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

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
from ae.pr_advanced_editing import (
    AdvancedEditParam,
    DynamicZoomParam,
    EditMode,
    KeyframeAnimationParam,
    KeyframePoint,
    MotionDirection,
    PremiereAdvancedEditing,
    SpeedRampParam,
    WhipPanParam,
)
from ae.pr_transition_system import (
    PremiereTransitionSystem,
    TransitionDirection,
    TransitionParam,
    TransitionType,
)

# Bridge 默认目录收口到 core/paths.py（AEK_PR_BRIDGE_DIR 可覆盖）
try:
    from core.paths import pr_bridge_dir as _paths_pr_bridge
    _DEFAULT_BRIDGE_DIR = _paths_pr_bridge()
except ImportError:
    _DEFAULT_BRIDGE_DIR = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.premiere-mcp-bridge"

logger = logging.getLogger(__name__)


class PRError(Exception):
    """Premiere Pro 操作基础异常。"""

    def __init__(self, message: str = "PR 操作失败") -> None:
        super().__init__(message)


class PRMCPError(PRError):
    """Premiere Pro MCP 客户端基础异常。"""

    def __init__(
        self,
        message: str = "PR MCP 操作失败",
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


class PRConnectionError(PRMCPError):
    """Premiere Pro 连接异常。"""

    pass


class PRCommandError(PRMCPError):
    """Premiere Pro 命令执行异常。"""

    pass


class PRTimeoutError(PRMCPError):
    """Premiere Pro 命令超时异常。"""

    pass


class PRNotFoundError(PRMCPError):
    """Premiere Pro 资源不存在异常。"""

    pass


class PRInvalidArgumentError(PRMCPError):
    """Premiere Pro 参数无效异常。"""

    pass


class PRPermissionDeniedError(PRMCPError):
    """Premiere Pro 权限不足异常。"""

    pass


class PRServerError(PRMCPError):
    """Premiere Pro 服务器错误异常。"""

    pass


class PRUnknownError(PRMCPError):
    """Premiere Pro 未知错误异常。"""

    pass


_ERROR_CODE_TO_EXCEPTION: dict[ErrorCode, type[PRMCPError]] = {
    ErrorCode.AE_NOT_RUNNING: PRConnectionError,
    ErrorCode.AE_NOT_RESPONDING: PRConnectionError,
    ErrorCode.IO_ERROR: PRConnectionError,
    ErrorCode.NETWORK_ERROR: PRConnectionError,
    ErrorCode.LOCK_ACQUISITION_FAILED: PRConnectionError,
    ErrorCode.SCRIPT_TIMEOUT: PRTimeoutError,
    ErrorCode.PROJECT_NOT_OPEN: PRCommandError,
    ErrorCode.RESOURCE_NOT_FOUND: PRNotFoundError,
    ErrorCode.SCRIPT_EXECUTION_ERROR: PRCommandError,
    ErrorCode.INVALID_PARAMETER: PRInvalidArgumentError,
    ErrorCode.OPERATION_NOT_SUPPORTED: PRCommandError,
}

_DEFAULT_PROTOCOL_VERSION = "1.0"


def _raise_from_response_error(response: BridgeResponse) -> PRMCPError:
    error = response.error
    if not error:
        return PRMCPError("未知错误")
    exc_class = _ERROR_CODE_TO_EXCEPTION.get(error.code, PRMCPError)
    return exc_class(
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


@dataclass
class SequenceInfo:
    """序列信息。"""

    name: str
    duration: float
    width: int
    height: int
    fps: float


@dataclass
class ClipInfo:
    """剪辑信息。"""

    name: str
    start: float
    end: float
    duration: float
    track_index: int


@dataclass
class ProjectInfo:
    """项目信息。"""

    name: str
    path: str
    sequence_count: int


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


class PRMCP:
    """Premiere Pro MCP 客户端。

    基于 BridgeClient 的高级封装，提供完整的 Premiere Pro 操作能力。

    使用示例：
        client = PRMCP()
        client.ping()
        seqs = client.list_sequences()
    """

    DEFAULT_PROTOCOL_VERSION = "1.0"

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
    ) -> None:
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

    def _build_command(
        self, command: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return {
            "command": command,
            "params": params or {},
            "id": f"pr_cmd_{int(time.time() * 1000)}_{hash(command) % 10000}",
            "timestamp": time.time(),
        }

    def _extract_protocol_version(self, response: dict[str, Any]) -> str:
        return response.get("protocol_version", self.DEFAULT_PROTOCOL_VERSION)

    def _sanitize_log_text(self, text: str) -> str:
        import re
        text = re.sub(r"sk-[a-zA-Z0-9]+", "[REDACTED]", text)
        text = re.sub(r"Authorization:\s*Bearer\s+\S+", "Authorization: Bearer [REDACTED]", text)
        text = re.sub(r"api_key\s*=\s*\"?\S+\"?", 'api_key="[REDACTED]"', text)
        return text

    def _map_error(self, response: dict[str, Any]) -> PRMCPError:
        error_info = response.get("error", {})
        code = error_info.get("code", "UNKNOWN")
        message = error_info.get("message", "未知错误")

        error_map = {
            "NOT_FOUND": PRNotFoundError(message),
            "INVALID_ARGUMENT": PRInvalidArgumentError(message),
            "PERMISSION_DENIED": PRPermissionDeniedError(message),
            "SERVER_ERROR": PRServerError(message),
            "TIMEOUT": PRTimeoutError(message),
            "CONNECTION_ERROR": PRConnectionError(message),
        }

        return error_map.get(code, PRUnknownError(message))

    def _execute(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        ttl: int | None = None,
        priority: Priority | None = None,
        idempotency_key: str | None = None,
        metadata: BridgeMetadata | None = None,
        progress_callback: Any | None = None,
        raise_on_error: bool = True,
    ) -> dict[str, Any]:
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
            response = _bridge_handler(cmd_data)

            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(response.is_success, latency_ms)

            if response.is_success:
                return response.result or {}

            if raise_on_error:
                raise _raise_from_response_error(response)

            return {"error": response.error.model_dump() if response.error else "Unknown error"}

        except PRMCPError:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(False, latency_ms)
            raise PRCommandError(f"命令执行异常: {e}") from e

    def _update_stats(self, success: bool, latency_ms: float) -> None:
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

    def ping(self) -> dict[str, Any]:
        """检测 Premiere Pro 是否存活。"""
        try:
            result = self._execute("ping", {})
            self._last_heartbeat_time = time.time()
            return result
        except PRMCPError:
            self._last_heartbeat_time = None
            raise

    def is_alive(self) -> bool:
        """检查 Premiere Pro 是否存活。

        使用一段很短的 TTL 探测，避免在 PR 未运行时等待默认的 30s TTL，
        从而快速（毫秒级）返回 False。
        """
        try:
            self._execute("ping", {}, ttl=1000, raise_on_error=False)
            self._last_heartbeat_time = time.time()
            return True
        except Exception:
            return False

    def wait_for_pr(
        self,
        timeout: float = 60.0,
        check_interval: float = 2.0,
    ) -> bool:
        """等待 Premiere Pro 启动并就绪。"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_alive():
                return True
            time.sleep(check_interval)
        return False

    def get_project_info(self) -> ProjectInfo:
        """获取当前项目信息。"""
        result = self._execute("getProjectInfo")
        info = result.get("result", {})
        return ProjectInfo(
            name=info.get("name", "Untitled"),
            path=info.get("path", ""),
            sequence_count=info.get("sequenceCount", 0),
        )

    def list_sequences(self) -> list[SequenceInfo]:
        """列出项目中的所有序列。"""
        result = self._execute("listSequences")
        seqs = result.get("sequences", [])
        return [
            SequenceInfo(
                name=s.get("name", ""),
                duration=s.get("duration", 0.0),
                width=s.get("width", 0),
                height=s.get("height", 0),
                fps=s.get("fps", 0.0),
            )
            for s in seqs
        ]

    def create_sequence(
        self,
        name: str,
        width: int = 1920,
        height: int = 1080,
        fps: float = 25.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """创建新序列。

        Args:
            name: 序列名称
            width: 宽度（像素）
            height: 高度（像素）
            fps: 帧率

        Returns:
            新序列信息
        """
        params = {
            "name": name,
            "width": width,
            "height": height,
            "fps": fps,
        }
        params.update(kwargs)
        return self._execute("createSequence", params)

    def delete_sequence(self, sequence_name: str) -> dict[str, Any]:
        """删除序列。"""
        return self._execute("deleteSequence", {"name": sequence_name})

    def get_sequence_info(self, sequence_name: str) -> dict[str, Any]:
        """获取序列详细信息。"""
        return self._execute("getSequenceInfo", {"name": sequence_name})

    def import_media(
        self,
        files: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """导入素材到项目。

        Args:
            files: 素材文件路径列表

        Returns:
            导入结果
        """
        return self._execute("importMedia", {"files": files, **kwargs})

    def get_timeline_info(self) -> dict[str, Any]:
        """获取当前时间线信息。"""
        return self._execute("getTimelineInfo")

    def add_to_sequence(
        self,
        clip_name: str,
        track_index: int = 0,
        position: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """将素材添加到序列。

        Args:
            clip_name: 素材名称
            track_index: 轨道索引
            position: 时间位置（秒）

        Returns:
            操作结果
        """
        params = {
            "clip": clip_name,
            "track": track_index,
            "position": position,
        }
        params.update(kwargs)
        return self._execute("addToSequence", params)

    def add_clip_to_sequence(
        self,
        clip_name: str,
        track_index: int = 0,
        position: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """将素材添加到序列（别名）。"""
        return self.add_to_sequence(clip_name, track_index, position, **kwargs)

    def cut_clip(
        self,
        track_index: int,
        clip_index: int,
        cut_time: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """剪切剪辑。"""
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "time": cut_time,
        }
        params.update(kwargs)
        return self._execute("cutClip", params)

    def delete_clip(
        self,
        track_index: int,
        clip_index: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """删除剪辑。"""
        params = {
            "track": track_index,
            "clipIndex": clip_index,
        }
        params.update(kwargs)
        return self._execute("deleteClip", params)

    def move_clip(
        self,
        track_index: int,
        clip_index: int,
        new_position: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """移动剪辑。"""
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "newPosition": new_position,
        }
        params.update(kwargs)
        return self._execute("moveClip", params)

    def split_clip(
        self,
        track_index: int,
        clip_index: int,
        split_time: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """分割剪辑。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            split_time: 分割时间（秒）

        Returns:
            操作结果
        """
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "time": split_time,
        }
        params.update(kwargs)
        return self._execute("splitClip", params)

    def trim_clip(
        self,
        track_index: int,
        clip_index: int,
        new_start: float,
        new_end: float,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """修剪剪辑。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            new_start: 新的开始时间（秒）
            new_end: 新的结束时间（秒）

        Returns:
            操作结果
        """
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "newStart": new_start,
            "newEnd": new_end,
        }
        params.update(kwargs)
        return self._execute("trimClip", params)

    def apply_effect(
        self,
        clip_name: str,
        effect_name: str,
        settings: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """应用效果到剪辑。

        Args:
            clip_name: 剪辑名称
            effect_name: 效果名称
            settings: 效果参数

        Returns:
            操作结果
        """
        params = {
            "clip": clip_name,
            "effectName": effect_name,
            "settings": settings or {},
        }
        params.update(kwargs)
        return self._execute("applyEffect", params)

    def remove_effect(
        self,
        clip_name: str,
        effect_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """移除剪辑上的效果。"""
        params = {
            "clip": clip_name,
            "effectName": effect_name,
        }
        params.update(kwargs)
        return self._execute("removeEffect", params)

    def set_effect_param(
        self,
        clip_name: str,
        effect_name: str,
        param_name: str,
        value: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """设置效果参数。"""
        params = {
            "clip": clip_name,
            "effectName": effect_name,
            "paramName": param_name,
            "value": value,
        }
        params.update(kwargs)
        return self._execute("setEffectParam", params)

    def get_effect_params(
        self,
        clip_name: str,
        effect_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """获取效果参数。"""
        params = {
            "clip": clip_name,
            "effectName": effect_name,
        }
        params.update(kwargs)
        return self._execute("getEffectParams", params)

    def list_available_effects(self) -> dict[str, Any]:
        """列出可用效果。"""
        return self._execute("listAvailableEffects")

    def apply_transition(
        self,
        track_index: int = 0,
        clip_index: int = 0,
        transition_name: str = "Cross Dissolve",
        duration: float = 1.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """应用转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            transition_name: 转场名称
            duration: 转场时长（秒）

        Returns:
            操作结果
        """
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "name": transition_name,
            "duration": duration,
        }
        params.update(kwargs)
        return self._execute("applyTransition", params)

    def set_clip_property(
        self,
        track_index: int,
        clip_index: int,
        property_name: str,
        value: Any,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """设置剪辑属性。"""
        params = {
            "track": track_index,
            "clipIndex": clip_index,
            "propertyName": property_name,
            "value": value,
        }
        params.update(kwargs)
        return self._execute("setClipProperty", params)

    def export_sequence(
        self,
        output_path: str,
        preset: str = "H.264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """导出序列。

        Args:
            output_path: 输出路径
            preset: 导出预设

        Returns:
            导出结果
        """
        params = {
            "path": output_path,
            "preset": preset,
        }
        params.update(kwargs)
        return self._execute("exportSequence", params)

    def render_sequence(
        self,
        output_path: str,
        preset: str = "H.264",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """渲染序列（别名）。"""
        return self.export_sequence(output_path, preset, **kwargs)

    def get_render_status(self, render_id: str) -> dict[str, Any]:
        """获取渲染状态。"""
        return self._execute("getRenderStatus", {"renderId": render_id})

    def cancel_render(self, render_id: str) -> dict[str, Any]:
        """取消渲染。"""
        return self._execute("cancelRender", {"renderId": render_id})

    def save_project(self, path: str | None = None) -> dict[str, Any]:
        """保存项目。"""
        params = {"path": path} if path else {}
        return self._execute("saveProject", params)

    def open_project(self, path: str) -> dict[str, Any]:
        """打开项目。"""
        return self._execute("openProject", {"path": path})

    def create_project(self, name: str, path: str | None = None) -> dict[str, Any]:
        """创建新项目。"""
        params = {"name": name}
        if path:
            params["path"] = path
        return self._execute("createProject", params)

    def new_project(self, name: str, path: str | None = None) -> dict[str, Any]:
        """创建新项目（别名）。"""
        return self.create_project(name, path)

    def close_project(self) -> dict[str, Any]:
        """关闭项目。"""
        return self._execute("closeProject")

    def get_effects(self) -> dict[str, Any]:
        """获取可用效果列表。"""
        return self._execute("getEffects")

    def set_playback_position(self, position: float) -> dict[str, Any]:
        """设置播放位置。"""
        return self._execute("setPlaybackPosition", {"position": position})

    def execute_script(self, script: str) -> dict[str, Any]:
        """执行 ExtendScript 代码。"""
        return self._execute("executeScript", {"script": script})

    @property
    def stats(self) -> ClientStats:
        """获取客户端统计信息。"""
        with self._stats_lock:
            return ClientStats(**self._stats.__dict__)

    # ==================== 转场效果 API ====================

    def list_transitions(self) -> list[dict[str, Any]]:
        """列出所有可用转场效果。"""
        transition_system = PremiereTransitionSystem(self)
        return transition_system.list_transitions()

    def list_transition_categories(self) -> list[str]:
        """列出转场分类。"""
        transition_system = PremiereTransitionSystem(self)
        return transition_system.list_categories()

    def get_transitions_by_category(self, category: str) -> list[dict[str, Any]]:
        """按分类获取转场效果。"""
        transition_system = PremiereTransitionSystem(self)
        return transition_system.get_transitions_by_category(category)

    def get_transition_info(self, transition_type: Union[str, TransitionType]) -> dict[str, Any]:
        """获取转场效果信息。"""
        transition_system = PremiereTransitionSystem(self)
        if isinstance(transition_type, str):
            transition_type = TransitionType(transition_type)
        return transition_system.get_transition_info(transition_type)

    def apply_transition_effect(
        self,
        track_index: int,
        clip_index: int,
        transition_type: Union[str, TransitionType],
        duration: float = 1.0,
        direction: Union[str, TransitionDirection] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """应用转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            transition_type: 转场类型
            duration: 转场时长（秒）
            direction: 转场方向
            **kwargs: 其他参数

        Returns:
            操作结果
        """
        if isinstance(transition_type, str):
            transition_type = TransitionType(transition_type)
        if isinstance(direction, str):
            direction = TransitionDirection(direction)

        params = TransitionParam(
            transition_type=transition_type,
            duration=duration,
            direction=direction,
            **kwargs,
        )

        transition_system = PremiereTransitionSystem(self)
        return transition_system.apply_transition(track_index, clip_index, params)

    def apply_whip_pan(
        self,
        track_index: int,
        clip_index: int,
        direction: str = "right",
        speed: float = 2.0,
        blur_amount: float = 25.0,
        duration: float = 0.5,
    ) -> dict[str, Any]:
        """应用拉镜转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            direction: 方向（left/right）
            speed: 速度因子
            blur_amount: 模糊量
            duration: 转场时长

        Returns:
            操作结果
        """
        params = TransitionParam(
            transition_type=TransitionType.WHIP_PAN,
            duration=duration,
            direction=TransitionDirection(direction),
            blur_amount=blur_amount,
        )
        transition_system = PremiereTransitionSystem(self)
        return transition_system.apply_transition(track_index, clip_index, params)

    def apply_zoom_transition(
        self,
        track_index: int,
        clip_index: int,
        zoom_amount: float = 1.5,
        blur_amount: float = 20.0,
        duration: float = 1.0,
    ) -> dict[str, Any]:
        """应用缩放转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            zoom_amount: 缩放倍数
            blur_amount: 模糊量
            duration: 转场时长

        Returns:
            操作结果
        """
        params = TransitionParam(
            transition_type=TransitionType.ZOOM,
            duration=duration,
            zoom_amount=zoom_amount,
            blur_amount=blur_amount,
        )
        transition_system = PremiereTransitionSystem(self)
        return transition_system.apply_transition(track_index, clip_index, params)

    def apply_glitch_transition(
        self,
        track_index: int,
        clip_index: int,
        glitch_amount: float = 5.0,
        duration: float = 0.5,
    ) -> dict[str, Any]:
        """应用故障转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            glitch_amount: 故障强度
            duration: 转场时长

        Returns:
            操作结果
        """
        params = TransitionParam(
            transition_type=TransitionType.GLITCH,
            duration=duration,
            glitch_amount=glitch_amount,
        )
        transition_system = PremiereTransitionSystem(self)
        return transition_system.apply_transition(track_index, clip_index, params)

    # ==================== 高级剪辑 API ====================

    def list_edit_modes(self) -> list[dict[str, Any]]:
        """列出所有可用编辑模式。"""
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.list_edit_modes()

    def get_edit_mode_info(self, edit_mode: Union[str, EditMode]) -> dict[str, Any]:
        """获取编辑模式信息。"""
        editing_system = PremiereAdvancedEditing(self)
        if isinstance(edit_mode, str):
            edit_mode = EditMode(edit_mode)
        return editing_system.get_edit_mode_info(edit_mode)

    def apply_whip_pan_edit(
        self,
        track_index: int,
        clip_index: int,
        direction: str = "right",
        speed: float = 2.0,
        blur_amount: float = 25.0,
        duration: float = 0.5,
        overlap: float = 0.3,
    ) -> dict[str, Any]:
        """应用拉镜效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            direction: 运动方向（left/right/up/down）
            speed: 速度因子
            blur_amount: 模糊量
            duration: 效果时长
            overlap: 重叠比例

        Returns:
            操作结果
        """
        whip_params = WhipPanParam(
            direction=MotionDirection(direction),
            speed=speed,
            blur_amount=blur_amount,
            duration=duration,
            overlap=overlap,
        )
        params = AdvancedEditParam(edit_mode=EditMode.WHIP_PAN, whip_pan=whip_params)
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.apply_editing(track_index, clip_index, params)

    def apply_dynamic_zoom(
        self,
        track_index: int,
        clip_index: int,
        start_scale: float = 100.0,
        end_scale: float = 150.0,
        duration: float = 2.0,
        ease_type: str = "ease_in_out",
        focus_point: list[float] | None = None,
        blur_amount: float = 0.0,
    ) -> dict[str, Any]:
        """应用动态缩放效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            start_scale: 起始缩放比例
            end_scale: 结束缩放比例
            duration: 效果时长
            ease_type: 缓动类型
            focus_point: 焦点坐标 [x, y]（0-1范围）
            blur_amount: 模糊量

        Returns:
            操作结果
        """
        zoom_params = DynamicZoomParam(
            start_scale=start_scale,
            end_scale=end_scale,
            duration=duration,
            ease_type=ease_type,
            focus_point=focus_point,
            blur_amount=blur_amount,
        )
        params = AdvancedEditParam(edit_mode=EditMode.DYNAMIC_ZOOM, dynamic_zoom=zoom_params)
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.apply_editing(track_index, clip_index, params)

    def apply_speed_ramp(
        self,
        track_index: int,
        clip_index: int,
        start_speed: float = 100.0,
        end_speed: float = 200.0,
        ramp_duration: float = 1.0,
        ease_type: str = "ease_in_out",
        frame_blending: bool = True,
        preserve_audio: bool = False,
    ) -> dict[str, Any]:
        """应用速度调整效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            start_speed: 起始速度（%）
            end_speed: 结束速度（%）
            ramp_duration: 渐变时长
            ease_type: 缓动类型
            frame_blending: 是否启用帧混合
            preserve_audio: 是否保持音频不变

        Returns:
            操作结果
        """
        speed_params = SpeedRampParam(
            start_speed=start_speed,
            end_speed=end_speed,
            ramp_duration=ramp_duration,
            ease_type=ease_type,
            frame_blending=frame_blending,
            preserve_audio=preserve_audio,
        )
        params = AdvancedEditParam(edit_mode=EditMode.SPEED_RAMP, speed_ramp=speed_params)
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.apply_editing(track_index, clip_index, params)

    def apply_keyframe_animation(
        self,
        track_index: int,
        clip_index: int,
        property_name: str,
        keyframes: list[dict[str, Any]],
        easing: str = "ease_in_out",
    ) -> dict[str, Any]:
        """应用关键帧动画。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            property_name: 属性名称（如 "Position", "Scale", "Rotation"）
            keyframes: 关键帧列表，每个关键帧包含 time, value, interpolation
            easing: 缓动类型

        Returns:
            操作结果
        """
        kf_points = [
            KeyframePoint(
                time=kf["time"],
                value=kf["value"],
                interpolation=kf.get("interpolation", "linear"),
            )
            for kf in keyframes
        ]
        kf_params = KeyframeAnimationParam(
            property_name=property_name,
            keyframes=kf_points,
            easing=easing,
        )
        params = AdvancedEditParam(edit_mode=EditMode.KEYFRAME_ANIMATION, keyframe_animation=kf_params)
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.apply_editing(track_index, clip_index, params)

    def apply_batch_editing(self, edits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """批量应用高级编辑效果。

        Args:
            edits: 编辑操作列表，每个操作包含 edit_mode, track_index, clip_index 及对应参数

        Returns:
            操作结果列表
        """
        editing_system = PremiereAdvancedEditing(self)
        return editing_system.apply_batch_editing(edits)


__all__ = [
    "PRMCP",
    "PRError",
    "PRMCPError",
    "PRConnectionError",
    "PRCommandError",
    "PRTimeoutError",
    "PRNotFoundError",
    "PRInvalidArgumentError",
    "PRPermissionDeniedError",
    "PRServerError",
    "PRUnknownError",
    "SequenceInfo",
    "ClipInfo",
    "ProjectInfo",
    "ClientStats",
    "TransitionType",
    "TransitionDirection",
    "TransitionParam",
    "EditMode",
    "MotionDirection",
    "WhipPanParam",
    "DynamicZoomParam",
    "SpeedRampParam",
    "KeyframePoint",
    "KeyframeAnimationParam",
    "AdvancedEditParam",
]