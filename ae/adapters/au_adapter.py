"""
Audition 适配器层
==================

提供 Adobe Audition 的统一抽象接口，支持多种连接方式（MCP、Puppet Engine 等）。

设计模式：适配器模式 + 策略模式

使用示例：
    from ae.adapters.au_adapter import MCPClientAUAdapter, BaseAUAdapter

    adapter = MCPClientAUAdapter()
    adapter.create_session("MySession", 44100, 16, 2)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ae.au_mcp_client import AUMDPClient, SessionInfo, TrackInfo, ClipInfo

logger = logging.getLogger(__name__)


class BaseAUAdapter(ABC):
    """Audition 适配器抽象基类。

    定义 Audition 操作的统一接口，所有具体适配器必须实现这些方法。
    """

    name: str = "au_base"
    supports_gui: bool = True
    requires_gui: bool = True

    @abstractmethod
    def create_session(
        self,
        name: str,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        num_tracks: int = 2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """创建新会话。"""
        pass

    @abstractmethod
    def open_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """打开会话文件。"""
        pass

    @abstractmethod
    def close_session(self, save_changes: bool = False) -> Dict[str, Any]:
        """关闭当前会话。"""
        pass

    @abstractmethod
    def save_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """保存会话。"""
        pass

    @abstractmethod
    def import_audio(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        """导入音频文件。"""
        pass

    @abstractmethod
    def create_track(self, name: str, track_type: str = "audio", **kwargs: Any) -> Dict[str, Any]:
        """创建轨道。"""
        pass

    @abstractmethod
    def delete_track(self, track_index: int) -> Dict[str, Any]:
        """删除轨道。"""
        pass

    @abstractmethod
    def set_track_properties(self, track_index: int, properties: Dict[str, Any]) -> Dict[str, Any]:
        """设置轨道属性。"""
        pass

    @abstractmethod
    def list_tracks(self) -> List[TrackInfo]:
        """列出所有轨道。"""
        pass

    @abstractmethod
    def list_clips(self, track_index: int) -> List[ClipInfo]:
        """列出轨道上的所有剪辑。"""
        pass

    @abstractmethod
    def add_clip(self, track_index: int, file_path: str, start_time: float = 0.0, **kwargs: Any) -> Dict[str, Any]:
        """添加音频剪辑到轨道。"""
        pass

    @abstractmethod
    def remove_clip(self, track_index: int, clip_index: int) -> Dict[str, Any]:
        """移除剪辑。"""
        pass

    @abstractmethod
    def split_clip(self, track_index: int, clip_index: int, split_time: float) -> Dict[str, Any]:
        """分割剪辑。"""
        pass

    @abstractmethod
    def trim_clip(self, track_index: int, clip_index: int, new_start: float, new_end: float) -> Dict[str, Any]:
        """修剪剪辑。"""
        pass

    @abstractmethod
    def apply_effect(
        self,
        track_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """应用效果到轨道。"""
        pass

    @abstractmethod
    def remove_effect(self, track_index: int, effect_name: str) -> Dict[str, Any]:
        """移除轨道上的效果。"""
        pass

    @abstractmethod
    def apply_normalization(self, track_index: int, target_db: float = -0.1) -> Dict[str, Any]:
        """应用音频归一化。"""
        pass

    @abstractmethod
    def apply_fade_in(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        """应用淡入效果。"""
        pass

    @abstractmethod
    def apply_fade_out(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        """应用淡出效果。"""
        pass

    @abstractmethod
    def adjust_volume(self, track_index: int, clip_index: int, gain_db: float) -> Dict[str, Any]:
        """调整剪辑音量。"""
        pass

    @abstractmethod
    def remove_silence(self, track_index: int, clip_index: int, threshold_db: float = -60.0, min_duration: float = 0.1) -> Dict[str, Any]:
        """移除剪辑中的静音部分。"""
        pass

    @abstractmethod
    def export_session(
        self,
        output_path: str,
        format: str = "wav",
        sample_rate: int = 44100,
        bit_depth: int = 16,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """导出会话。"""
        pass

    @abstractmethod
    def export_range(
        self,
        output_path: str,
        start_time: float,
        end_time: float,
        format: str = "wav",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """导出时间范围。"""
        pass

    @abstractmethod
    def get_session_info(self) -> SessionInfo:
        """获取当前会话信息。"""
        pass

    @abstractmethod
    def ping(self) -> Dict[str, Any]:
        """检测 Audition 是否存活。"""
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        """检查 Audition 是否存活。"""
        pass

    @abstractmethod
    def execute_script(self, script_content: str) -> Dict[str, Any]:
        """执行 ExtendScript 脚本。"""
        pass

    @abstractmethod
    def undo(self) -> Dict[str, Any]:
        """撤销上一步操作。"""
        pass

    @abstractmethod
    def redo(self) -> Dict[str, Any]:
        """重做上一步操作。"""
        pass


class MCPClientAUAdapter(BaseAUAdapter):
    """基于 MCP 客户端的 Audition 适配器。

    使用 file polling 机制与 Audition 通信，支持所有核心 Audition 操作。
    """

    name = "au_mcp"

    def __init__(self, client: Optional[AUMDPClient] = None, **client_kwargs) -> None:
        """初始化 MCP 客户端适配器。

        Args:
            client: 已初始化的 AUMDPClient 实例
            client_kwargs: 创建 AUMDPClient 时的参数
        """
        self._client: Optional[AUMDPClient] = client
        self._client_kwargs = client_kwargs

    def _ensure_client(self) -> AUMDPClient:
        """确保客户端已初始化。"""
        if self._client is None:
            self._client = AUMDPClient(**self._client_kwargs)
        return self._client

    def create_session(
        self,
        name: str,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        num_tracks: int = 2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_client().create_session(
            name=name,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            num_tracks=num_tracks,
            **kwargs,
        )

    def open_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_client().open_session(file_path, **kwargs)

    def close_session(self, save_changes: bool = False) -> Dict[str, Any]:
        return self._ensure_client().close_session(save_changes)

    def save_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_client().save_session(file_path, **kwargs)

    def import_audio(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_client().import_audio(file_path, **kwargs)

    def create_track(self, name: str, track_type: str = "audio", **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_client().create_track(name, track_type, **kwargs)

    def delete_track(self, track_index: int) -> Dict[str, Any]:
        return self._ensure_client().delete_track(track_index)

    def set_track_properties(self, track_index: int, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._ensure_client().set_track_properties(track_index, properties)

    def list_tracks(self) -> List[TrackInfo]:
        return self._ensure_client().list_tracks()

    def list_clips(self, track_index: int) -> List[ClipInfo]:
        return self._ensure_client().list_clips(track_index)

    def add_clip(self, track_index: int, file_path: str, start_time: float = 0.0, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_client().add_clip(track_index, file_path, start_time, **kwargs)

    def remove_clip(self, track_index: int, clip_index: int) -> Dict[str, Any]:
        return self._ensure_client().remove_clip(track_index, clip_index)

    def split_clip(self, track_index: int, clip_index: int, split_time: float) -> Dict[str, Any]:
        return self._ensure_client().split_clip(track_index, clip_index, split_time)

    def trim_clip(self, track_index: int, clip_index: int, new_start: float, new_end: float) -> Dict[str, Any]:
        return self._ensure_client().trim_clip(track_index, clip_index, new_start, new_end)

    def apply_effect(
        self,
        track_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_client().apply_effect(track_index, effect_name, settings, **kwargs)

    def remove_effect(self, track_index: int, effect_name: str) -> Dict[str, Any]:
        return self._ensure_client().remove_effect(track_index, effect_name)

    def apply_normalization(self, track_index: int, target_db: float = -0.1) -> Dict[str, Any]:
        return self._ensure_client().apply_normalization(track_index, target_db)

    def apply_fade_in(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        return self._ensure_client().apply_fade_in(track_index, clip_index, duration)

    def apply_fade_out(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        return self._ensure_client().apply_fade_out(track_index, clip_index, duration)

    def adjust_volume(self, track_index: int, clip_index: int, gain_db: float) -> Dict[str, Any]:
        return self._ensure_client().adjust_volume(track_index, clip_index, gain_db)

    def remove_silence(self, track_index: int, clip_index: int, threshold_db: float = -60.0, min_duration: float = 0.1) -> Dict[str, Any]:
        return self._ensure_client().remove_silence(track_index, clip_index, threshold_db, min_duration)

    def export_session(
        self,
        output_path: str,
        format: str = "wav",
        sample_rate: int = 44100,
        bit_depth: int = 16,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_client().export_session(
            output_path=output_path,
            format=format,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            **kwargs,
        )

    def export_range(
        self,
        output_path: str,
        start_time: float,
        end_time: float,
        format: str = "wav",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_client().export_range(
            output_path=output_path,
            start_time=start_time,
            end_time=end_time,
            format=format,
            **kwargs,
        )

    def get_session_info(self) -> SessionInfo:
        return self._ensure_client().get_session_info()

    def ping(self) -> Dict[str, Any]:
        return self._ensure_client().ping()

    def is_alive(self) -> bool:
        return self._ensure_client().is_alive()

    def execute_script(self, script_content: str) -> Dict[str, Any]:
        return self._ensure_client().execute_script(script_content)

    def undo(self) -> Dict[str, Any]:
        return self._ensure_client().undo()

    def redo(self) -> Dict[str, Any]:
        return self._ensure_client().redo()

    @property
    def client(self) -> AUMDPClient:
        """底层 MCP 客户端实例。"""
        return self._ensure_client()


class PuppetEngineAUAdapter(BaseAUAdapter):
    """基于 Puppet Engine 的 Audition 适配器。

    通过 puppet-automation 引擎层与 Audition 通信。
    """

    name = "au_puppet"

    def __init__(self, engine=None) -> None:
        self._engine = engine

    def _ensure_engine(self):
        if self._engine is None:
            try:
                import sys
                import importlib.machinery
                import importlib.util
                from pathlib import Path
                _project_root = Path(__file__).resolve().parent.parent.parent
                _pa_dir = _project_root / "puppet-automation"
                _src_dir = _pa_dir / "src"
                if "puppet_automation" not in sys.modules:
                    _pkg = importlib.util.module_from_spec(
                        importlib.machinery.ModuleSpec(
                            "puppet_automation", loader=None, is_package=True
                        )
                    )
                    _pkg.__path__ = [str(_pa_dir)]
                    sys.modules["puppet_automation"] = _pkg
                if "puppet_automation.src" not in sys.modules:
                    _src_init = _src_dir / "__init__.py"
                    if _src_init.exists():
                        _spec = importlib.util.spec_from_file_location(
                            "puppet_automation.src", _src_init,
                            submodule_search_locations=[str(_src_dir)]
                        )
                    else:
                        _spec = importlib.machinery.ModuleSpec(
                            "puppet_automation.src", loader=None, is_package=True
                        )
                        _spec.submodule_search_locations = [str(_src_dir)]
                    _src_pkg = importlib.util.module_from_spec(_spec)
                    sys.modules["puppet_automation.src"] = _src_pkg
                    if _spec.loader is not None:
                        _spec.loader.exec_module(_src_pkg)
                # 注意: 历史上曾使用 puppet_automation.src.engines.au_engine.AUEngine
                # 现已重命名为 engines.audition.AuditionEngine (包路径:
                # puppet_automation.src.engines.audition)
                from puppet_automation.src.engines.audition import AuditionEngine
                self._engine = AuditionEngine()
            except ImportError:
                raise RuntimeError("Puppet Engine not available")
        return self._engine

    def create_session(
        self,
        name: str,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        num_tracks: int = 2,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="create_session",
            name=name,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            num_tracks=num_tracks,
            **kwargs,
        )

    def open_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="open_session", file_path=file_path, **kwargs)

    def close_session(self, save_changes: bool = False) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="close_session", save_changes=save_changes)

    def save_session(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="save_session", file_path=file_path, **kwargs)

    def import_audio(self, file_path: str, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="import_audio", file_path=file_path, **kwargs)

    def create_track(self, name: str, track_type: str = "audio", **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="create_track", name=name, track_type=track_type, **kwargs)

    def delete_track(self, track_index: int) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="delete_track", track_index=track_index)

    def set_track_properties(self, track_index: int, properties: Dict[str, Any]) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="set_track_properties", track_index=track_index, properties=properties)

    def list_tracks(self) -> List[TrackInfo]:
        result = self._ensure_engine().execute(action="list_tracks")
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

    def list_clips(self, track_index: int) -> List[ClipInfo]:
        result = self._ensure_engine().execute(action="list_clips", track_index=track_index)
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

    def add_clip(self, track_index: int, file_path: str, start_time: float = 0.0, **kwargs: Any) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="add_clip",
            track_index=track_index,
            file_path=file_path,
            start_time=start_time,
            **kwargs,
        )

    def remove_clip(self, track_index: int, clip_index: int) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="remove_clip", track_index=track_index, clip_index=clip_index)

    def split_clip(self, track_index: int, clip_index: int, split_time: float) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="split_clip",
            track_index=track_index,
            clip_index=clip_index,
            split_time=split_time,
        )

    def trim_clip(self, track_index: int, clip_index: int, new_start: float, new_end: float) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="trim_clip",
            track_index=track_index,
            clip_index=clip_index,
            new_start=new_start,
            new_end=new_end,
        )

    def apply_effect(
        self,
        track_index: int,
        effect_name: str,
        settings: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="apply_effect",
            track_index=track_index,
            effect_name=effect_name,
            settings=settings or {},
            **kwargs,
        )

    def remove_effect(self, track_index: int, effect_name: str) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="remove_effect", track_index=track_index, effect_name=effect_name)

    def apply_normalization(self, track_index: int, target_db: float = -0.1) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="apply_normalization", track_index=track_index, target_db=target_db)

    def apply_fade_in(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="apply_fade_in",
            track_index=track_index,
            clip_index=clip_index,
            duration=duration,
        )

    def apply_fade_out(self, track_index: int, clip_index: int, duration: float = 1.0) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="apply_fade_out",
            track_index=track_index,
            clip_index=clip_index,
            duration=duration,
        )

    def adjust_volume(self, track_index: int, clip_index: int, gain_db: float) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="adjust_volume",
            track_index=track_index,
            clip_index=clip_index,
            gain_db=gain_db,
        )

    def remove_silence(self, track_index: int, clip_index: int, threshold_db: float = -60.0, min_duration: float = 0.1) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="remove_silence",
            track_index=track_index,
            clip_index=clip_index,
            threshold_db=threshold_db,
            min_duration=min_duration,
        )

    def export_session(
        self,
        output_path: str,
        format: str = "wav",
        sample_rate: int = 44100,
        bit_depth: int = 16,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="export_session",
            output_path=output_path,
            format=format,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            **kwargs,
        )

    def export_range(
        self,
        output_path: str,
        start_time: float,
        end_time: float,
        format: str = "wav",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        return self._ensure_engine().execute(
            action="export_range",
            output_path=output_path,
            start_time=start_time,
            end_time=end_time,
            format=format,
            **kwargs,
        )

    def get_session_info(self) -> SessionInfo:
        result = self._ensure_engine().execute(action="get_session_info")
        info = result.get("result", {})
        return SessionInfo(
            name=info.get("name", "Untitled"),
            sample_rate=info.get("sampleRate", 44100),
            bit_depth=info.get("bitDepth", 16),
            num_tracks=info.get("numTracks", 0),
            duration=info.get("duration", 0.0),
        )

    def ping(self) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="ping")

    def is_alive(self) -> bool:
        try:
            self.ping()
            return True
        except Exception:
            return False

    def execute_script(self, script_content: str) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="execute_script", script_content=script_content)

    def undo(self) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="undo")

    def redo(self) -> Dict[str, Any]:
        return self._ensure_engine().execute(action="redo")

    @property
    def engine(self):
        """底层 Puppet Engine 实例。"""
        return self._ensure_engine()


class AUAdapterFactory:
    """Audition 适配器工厂。

    根据配置创建合适的适配器实例。
    """

    @staticmethod
    def create(
        adapter_type: str = "mcp",
        **kwargs,
    ) -> BaseAUAdapter:
        """创建 Audition 适配器。

        Args:
            adapter_type: 适配器类型 "mcp" | "puppet"
            kwargs: 适配器初始化参数

        Returns:
            适配的 BaseAUAdapter 实例
        """
        adapter_type = adapter_type.lower()

        if adapter_type == "mcp":
            return MCPClientAUAdapter(**kwargs)
        elif adapter_type == "puppet":
            return PuppetEngineAUAdapter(**kwargs)
        else:
            raise ValueError(f"Unknown adapter type: {adapter_type}")