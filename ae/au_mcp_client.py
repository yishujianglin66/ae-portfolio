"""
Audition MCP 客户端封装 v1.0
============================

基于 Bridge 协议的高质量 Adobe Audition MCP 客户端封装。

提供：
- 完整的类型注解与文档字符串
- 20+ MCP 工具方法封装（会话、轨道、剪辑、效果、导出）
- 自定义异常体系
- 连接状态监控与心跳检测
- 调用统计与性能指标

协议兼容：
- bridge_protocol.py BridgeClient v2.0
- 使用 file polling 机制

使用示例：
    from ae.au_mcp_client import AUMDPClient

    client = AUMDPClient()
    client.ping()
    client.create_session("MySession", 44100, 16, 2)
    client.export_session("output.wav")
"""
from __future__ import annotations

import time
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ae.archive.bridge_protocol import (
    BridgeClient,
    BridgeResponse,
    BridgeMetadata,
    CommandStatus,
    ErrorCode,
    Priority,
    DEFAULT_TTL_MS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_RETRIES,
)

# Bridge 默认目录收口到 core/paths.py（AEK_AU_BRIDGE_DIR 可覆盖）
try:
    from core.paths import au_bridge_dir as _paths_au_bridge
    _DEFAULT_BRIDGE_DIR = _paths_au_bridge()
except ImportError:
    _DEFAULT_BRIDGE_DIR = r"C:\Users\Administrator\Documents\au-mcp-bridge"

logger = logging.getLogger(__name__)


class AUMCPError(Exception):
    """Audition MCP 客户端基础异常。"""

    def __init__(
        self,
        message: str = "Audition MCP 操作失败",
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


class AUConnectionError(AUMCPError):
    """Audition 连接异常。"""

    pass


class AUCommandError(AUMCPError):
    """Audition 命令执行异常。"""

    pass


class AUTimeoutError(AUMCPError):
    """Audition 命令超时异常。"""

    pass


class AUNotFoundError(AUMCPError):
    """Audition 资源不存在异常。"""

    pass


_ERROR_CODE_TO_EXCEPTION: Dict[ErrorCode, type[AUMCPError]] = {
    ErrorCode.AE_NOT_RUNNING: AUConnectionError,
    ErrorCode.AE_NOT_RESPONDING: AUConnectionError,
    ErrorCode.IO_ERROR: AUConnectionError,
    ErrorCode.NETWORK_ERROR: AUConnectionError,
    ErrorCode.LOCK_ACQUISITION_FAILED: AUConnectionError,
    ErrorCode.SCRIPT_TIMEOUT: AUTimeoutError,
    ErrorCode.RESOURCE_NOT_FOUND: AUNotFoundError,
    ErrorCode.SCRIPT_EXECUTION_ERROR: AUCommandError,
    ErrorCode.INVALID_PARAMETER: AUCommandError,
    ErrorCode.OPERATION_NOT_SUPPORTED: AUCommandError,
}


def _raise_from_response_error(response: BridgeResponse) -> AUMCPError:
    error = response.error
    if not error:
        return AUMCPError("未知错误")
    exc_class = _ERROR_CODE_TO_EXCEPTION.get(error.code, AUMCPError)
    return exc_class(
        message=error.message,
        error_code=error.code,
        details=error.details,
    )


@dataclass
class SessionInfo:
    """会话信息。"""

    name: str
    sample_rate: int
    bit_depth: int
    num_tracks: int
    duration: float


@dataclass
class TrackInfo:
    """轨道信息。"""

    name: str
    type: str
    index: int
    solo: bool
    mute: bool
    volume: float


@dataclass
class ClipInfo:
    """剪辑信息。"""

    name: str
    track_index: int
    start_time: float
    end_time: float
    duration: float


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


class AUMDPClient:
    """Audition MCP 客户端。

    基于 BridgeClient 的高级封装，提供完整的 Audition 操作能力。

    使用示例：
        client = AUMDPClient()
        client.ping()
        client.create_session("MySession", 44100, 16, 2)
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
        self._last_heartbeat_time: Optional[float] = None

    def _execute(
        self,
        command: str,
        params: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
        priority: Optional[Priority] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[BridgeMetadata] = None,
        progress_callback: Optional[Any] = None,
        raise_on_error: bool = True,
    ) -> Dict[str, Any]:
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
            response = _bridge_handler(cmd_data)

            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(response.is_success, latency_ms)

            if response.is_success:
                return response.result or {}

            if raise_on_error:
                raise _raise_from_response_error(response)

            return {"error": response.error.model_dump() if response.error else "Unknown error"}

        except AUMCPError:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._update_stats(False, latency_ms)
            raise AUCommandError(f"命令执行异常: {e}") from e

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

    def ping(self) -> Dict[str, Any]:
        """检测 Audition 是否存活。"""
        try:
            result = self._execute("ping", {})
            self._last_heartbeat_time = time.time()
            return result
        except AUMCPError:
            self._last_heartbeat_time = None
            raise

    def is_alive(self) -> bool:
        """检查 Audition 是否存活。

        使用一段很短的 TTL 探测，避免在 AU 未运行时等待默认的 30s TTL，
        从而快速（毫秒级）返回 False。
        """
        try:
            self._execute("ping", {}, ttl=1000, raise_on_error=False)
            self._last_heartbeat_time = time.time()
            return True
        except Exception:
            return False

    def wait_for_au(
        self,
        timeout: float = 60.0,
        check_interval: float = 2.0,
    ) -> bool:
        """等待 Audition 启动并就绪。"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_alive():
                return True
            time.sleep(check_interval)
        return False

    def get_session_info(self) -> SessionInfo:
        """获取当前会话信息。"""
        result = self._execute("getSessionInfo")
        info = result.get("result", {})
        return SessionInfo(
            name=info.get("name", "Untitled"),
            sample_rate=info.get("sampleRate", 44100),
            bit_depth=info.get("bitDepth", 16),
            num_tracks=info.get("numTracks", 0),
            duration=info.get("duration", 0.0),
        )

    def create_session(
        self,
        name: str,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        num_tracks: int = 2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建新会话。

        Args:
            name: 会话名称
            sample_rate: 采样率（44100/48000/96000）
            bit_depth: 位深度（16/24/32）
            num_tracks: 轨道数量

        Returns:
            新会话信息
        """
        params = {
            "name": name,
            "sampleRate": sample_rate,
            "bitDepth": bit_depth,
            "numTracks": num_tracks,
        }
        params.update(kwargs)
        return self._execute("createSession", params)

    def open_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """打开会话文件。

        Args:
            file_path: 文件路径（.sesx）

        Returns:
            操作结果
        """
        return self._execute("openSession", {"filePath": file_path, **kwargs})

    def close_session(self, save_changes: bool = False) -> Dict[str, Any]:
        """关闭当前会话。

        Args:
            save_changes: 是否保存更改

        Returns:
            操作结果
        """
        return self._execute("closeSession", {"saveChanges": save_changes})

    def save_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """保存会话。

        Args:
            file_path: 保存路径

        Returns:
            操作结果
        """
        return self._execute("saveSession", {"filePath": file_path, **kwargs})

    def import_audio(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """导入音频文件。

        Args:
            file_path: 音频文件路径

        Returns:
            导入结果
        """
        return self._execute("importAudio", {"filePath": file_path, **kwargs})

    def list_tracks(self) -> List[TrackInfo]:
        """列出所有轨道。"""
        result = self._execute("listTracks")
        tracks = result.get("tracks", [])
        return [
            TrackInfo(
                name=t.get("name", ""),
                type=t.get("type", ""),
                index=t.get("index", 0),
                solo=t.get("solo", False),
                mute=t.get("mute", False),
                volume=t.get("volume", 1.0),
            )
            for t in tracks
        ]

    def create_track(
        self,
        name: str,
        track_type: str = "audio",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建轨道。

        Args:
            name: 轨道名称
            track_type: 轨道类型（audio/midi/master）

        Returns:
            新轨道信息
        """
        params = {
            "name": name,
            "trackType": track_type,
        }
        params.update(kwargs)
        return self._execute("createTrack", params)

    def delete_track(self, track_index: int) -> Dict[str, Any]:
        """删除轨道。

        Args:
            track_index: 轨道索引

        Returns:
            操作结果
        """
        return self._execute("deleteTrack", {"trackIndex": track_index})

    def set_track_properties(
        self,
        track_index: int,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """设置轨道属性。

        Args:
            track_index: 轨道索引
            properties: 属性字典，支持：
                - solo: 是否独奏
                - mute: 是否静音
                - volume: 音量 0-1
                - pan: 声相 -1 到 1

        Returns:
            操作结果
        """
        return self._execute(
            "setTrackProperties",
            {"trackIndex": track_index, "properties": properties},
        )

    def list_clips(self, track_index: int) -> List[ClipInfo]:
        """列出轨道上的所有剪辑。

        Args:
            track_index: 轨道索引

        Returns:
            剪辑列表
        """
        result = self._execute("listClips", {"trackIndex": track_index})
        clips = result.get("clips", [])
        return [
            ClipInfo(
                name=c.get("name", ""),
                track_index=c.get("trackIndex", track_index),
                start_time=c.get("startTime", 0.0),
                end_time=c.get("endTime", 0.0),
                duration=c.get("duration", 0.0),
            )
            for c in clips
        ]

    def add_clip(
        self,
        track_index: int,
        file_path: str,
        start_time: float = 0.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """添加音频剪辑到轨道。

        Args:
            track_index: 轨道索引
            file_path: 音频文件路径
            start_time: 开始时间（秒）

        Returns:
            操作结果
        """
        params = {
            "trackIndex": track_index,
            "filePath": file_path,
            "startTime": start_time,
        }
        params.update(kwargs)
        return self._execute("addClip", params)

    def remove_clip(self, track_index: int, clip_index: int) -> Dict[str, Any]:
        """移除剪辑。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引

        Returns:
            操作结果
        """
        return self._execute("removeClip", {"trackIndex": track_index, "clipIndex": clip_index})

    def split_clip(self, track_index: int, clip_index: int, split_time: float) -> Dict[str, Any]:
        """分割剪辑。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            split_time: 分割时间（秒）

        Returns:
            操作结果
        """
        return self._execute(
            "splitClip",
            {"trackIndex": track_index, "clipIndex": clip_index, "splitTime": split_time},
        )

    def trim_clip(
        self,
        track_index: int,
        clip_index: int,
        new_start: float,
        new_end: float,
    ) -> Dict[str, Any]:
        """修剪剪辑。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            new_start: 新开始时间（秒）
            new_end: 新结束时间（秒）

        Returns:
            操作结果
        """
        return self._execute(
            "trimClip",
            {"trackIndex": track_index, "clipIndex": clip_index, "newStart": new_start, "newEnd": new_end},
        )

    def apply_effect(
        self,
        track_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """应用效果到轨道。

        Args:
            track_index: 轨道索引
            effect_name: 效果名称（如 Equalizer, Compressor, Reverb）
            settings: 效果参数

        Returns:
            操作结果
        """
        params = {
            "trackIndex": track_index,
            "effectName": effect_name,
            "settings": settings or {},
        }
        params.update(kwargs)
        return self._execute("applyEffect", params)

    def remove_effect(self, track_index: int, effect_name: str) -> Dict[str, Any]:
        """移除轨道上的效果。

        Args:
            track_index: 轨道索引
            effect_name: 效果名称

        Returns:
            操作结果
        """
        return self._execute("removeEffect", {"trackIndex": track_index, "effectName": effect_name})

    def apply_normalization(self, track_index: int, target_db: float = -0.1) -> Dict[str, Any]:
        """应用音频归一化。

        Args:
            track_index: 轨道索引
            target_db: 目标电平（dB）

        Returns:
            操作结果
        """
        return self._execute("applyNormalization", {"trackIndex": track_index, "targetDb": target_db})

    def apply_fade_in(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        """应用淡入效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            duration: 淡入时长（秒）

        Returns:
            操作结果
        """
        return self._execute(
            "applyFadeIn",
            {"trackIndex": track_index, "clipIndex": clip_index, "duration": duration},
        )

    def apply_fade_out(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        """应用淡出效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            duration: 淡出时长（秒）

        Returns:
            操作结果
        """
        return self._execute(
            "applyFadeOut",
            {"trackIndex": track_index, "clipIndex": clip_index, "duration": duration},
        )

    def adjust_volume(
        self,
        track_index: int,
        clip_index: int,
        gain_db: float,
    ) -> Dict[str, Any]:
        """调整剪辑音量。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            gain_db: 增益（dB）

        Returns:
            操作结果
        """
        return self._execute(
            "adjustVolume",
            {"trackIndex": track_index, "clipIndex": clip_index, "gainDb": gain_db},
        )

    def remove_silence(
        self,
        track_index: int,
        clip_index: int,
        threshold_db: float = -60.0,
        min_duration: float = 0.1,
    ) -> Dict[str, Any]:
        """移除剪辑中的静音部分。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            threshold_db: 静音阈值（dB）
            min_duration: 最小静音时长（秒）

        Returns:
            操作结果
        """
        return self._execute(
            "removeSilence",
            {"trackIndex": track_index, "clipIndex": clip_index, "thresholdDb": threshold_db, "minDuration": min_duration},
        )

    def export_session(
        self,
        output_path: str,
        format: str = "wav",
        sample_rate: int = 44100,
        bit_depth: int = 16,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """导出会话。

        Args:
            output_path: 输出路径
            format: 导出格式（wav/mp3/aiff/flac/ogg）
            sample_rate: 采样率
            bit_depth: 位深度

        Returns:
            导出结果
        """
        params = {
            "outputPath": output_path,
            "format": format,
            "sampleRate": sample_rate,
            "bitDepth": bit_depth,
        }
        params.update(kwargs)
        return self._execute("exportSession", params)

    def export_range(
        self,
        output_path: str,
        start_time: float,
        end_time: float,
        format: str = "wav",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """导出时间范围。

        Args:
            output_path: 输出路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            format: 导出格式

        Returns:
            导出结果
        """
        params = {
            "outputPath": output_path,
            "startTime": start_time,
            "endTime": end_time,
            "format": format,
        }
        params.update(kwargs)
        return self._execute("exportRange", params)

    def set_cursor_position(self, time: float) -> Dict[str, Any]:
        """设置播放头位置。

        Args:
            time: 时间位置（秒）

        Returns:
            操作结果
        """
        return self._execute("setCursorPosition", {"time": time})

    def get_cursor_position(self) -> Dict[str, Any]:
        """获取播放头位置。"""
        return self._execute("getCursorPosition")

    def play(self) -> Dict[str, Any]:
        """开始播放。"""
        return self._execute("play")

    def pause(self) -> Dict[str, Any]:
        """暂停播放。"""
        return self._execute("pause")

    def stop(self) -> Dict[str, Any]:
        """停止播放。"""
        return self._execute("stop")

    def undo(self) -> Dict[str, Any]:
        """撤销。"""
        return self._execute("undo")

    def redo(self) -> Dict[str, Any]:
        """重做。"""
        return self._execute("redo")

    def execute_script(self, script: str) -> Dict[str, Any]:
        """执行 ES 脚本代码。

        Args:
            script: ES 脚本代码字符串

        Returns:
            执行结果
        """
        return self._execute("executeScript", {"script": script})

    @property
    def stats(self) -> ClientStats:
        """获取客户端统计信息。"""
        with self._stats_lock:
            return ClientStats(**self._stats.__dict__)


__all__ = [
    "AUMDPClient",
    "AUMCPError",
    "AUConnectionError",
    "AUCommandError",
    "AUTimeoutError",
    "AUNotFoundError",
    "SessionInfo",
    "TrackInfo",
    "ClipInfo",
    "ClientStats",
]