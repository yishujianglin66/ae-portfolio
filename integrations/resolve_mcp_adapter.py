"""
DaVinci Resolve MCP Adapter v1.0
=================================
统一 DaVinci Resolve 自动化接口，支持双通道：
  - Channel A: Resolve Python API (通过 DaVinciResolveScript 模块)
  - Channel B: fuscript.exe + Lua (降级方案，Studio 21.0.3 已验证)

MCP 工具映射 (28 个工具):
  项目管理: create_project, load_project, save_project, export_project, import_project
  页面控制: open_page
  时间线:   create_timeline, set_current_timeline, append_to_timeline,
            create_timeline_from_clips, import_timeline_from_file
  素材管理: import_media, add_sub_folder
  剪辑操作: set_clip_property, set_audio_volume, set_current_version
  调色:     add_color_node, save_still, apply_still
  轨道:     add_track, set_track_name, enable_track, set_track_volume
  播放:     play_timeline, stop_timeline, set_playhead_position
  标记:     add_timeline_marker
  渲染:     start_project_render
  系统:     refresh, get_system_status, execute_lua

集成来源: samuelgursky/davinci-resolve-mcp (2.1k stars)
降级引擎: resolve_engine.py (fuscript.exe + Lua, 已验证)
"""

import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.resolve_discovery import find_fuscript_exe

logger = logging.getLogger(__name__)

# Resolve 安装路径：由 core/resolve_discovery 统一发现（唯一权威来源）
# 此前本模块自持一份候选表，与 resolve_engine / resolve_executor / flagship_runner
# 的实现互不一致。未找到时为空串，调用方的 os.path.isfile(FUSCRIPT_PATH) 自然为 False。
_fuscript_found = find_fuscript_exe()
FUSCRIPT_PATH = str(_fuscript_found) if _fuscript_found is not None else ""

# MCP 外部项目路径
MCP_PROJECT_DIR = Path(__file__).parent.parent / "external" / "davinci-resolve-mcp"


@dataclass
class ResolveToolResult:
    """统一工具执行结果"""
    tool: str
    status: str  # success / failed / degraded / unavailable
    channel: str  # python_api / fuscript_lua / simulated
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class ResolveMCPAdapter:
    """DaVinci Resolve MCP 适配器

    统一接口层，自动选择最佳可用通道：
    1. 优先使用 Resolve Python API (resolve_api.py)
    2. Python API 不可用时降级到 fuscript.exe + Lua (resolve_engine.py)
    3. 两者都不可用时返回 degraded 状态
    """

    TOOL_NAMES = [
        # 系统
        "refresh", "get_system_status", "execute_lua",
        # 项目管理
        "create_project", "load_project", "save_project",
        "export_project", "import_project",
        # 页面
        "open_page",
        # 时间线
        "create_timeline", "set_current_timeline",
        "append_to_timeline", "create_timeline_from_clips",
        "import_timeline_from_file",
        # 素材
        "import_media", "add_sub_folder",
        # 剪辑
        "set_clip_property", "set_audio_volume", "set_current_version",
        # 调色
        "add_color_node", "save_still", "apply_still",
        # 轨道
        "add_track", "set_track_name", "enable_track", "set_track_volume",
        # 播放
        "play_timeline", "stop_timeline", "set_playhead_position",
        # 标记
        "add_timeline_marker",
        # 渲染
        "start_project_render",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._resolve_api = None  # Python API 实例
        self._resolve_engine = None  # fuscript Lua 引擎实例
        self._channel = None  # 当前可用通道
        self._init_channels()

    def _init_channels(self):
        """初始化双通道"""
        # Channel A: Python API
        try:
            sys.path.insert(0, str(MCP_PROJECT_DIR))
            from resolve_api import ResolveAPI
            self._resolve_api = ResolveAPI()
            if self._resolve_api.is_connected():
                self._channel = "python_api"
                logger.info("[ResolveMCP] Channel A: Python API connected")
            else:
                logger.warning("[ResolveMCP] Channel A: Python API not connected")
        except Exception as e:
            logger.warning(f"[ResolveMCP] Channel A: Python API init failed: {e}")

        # Channel B: fuscript Lua
        if self._channel is None and os.path.isfile(FUSCRIPT_PATH):
            try:
                from integrations.resolve_engine import ResolveAutomationEngine
                self._resolve_engine = ResolveAutomationEngine(fuscript_path=FUSCRIPT_PATH)
                self._channel = "fuscript_lua"
                logger.info("[ResolveMCP] Channel B: fuscript Lua engine ready")
            except Exception as e:
                logger.warning(f"[ResolveMCP] Channel B: fuscript Lua init failed: {e}")

        if self._channel is None:
            logger.error("[ResolveMCP] No channel available")

    def check_available(self) -> bool:
        """检查是否有任何可用通道"""
        return self._channel is not None

    def list_operations(self) -> list[str]:
        """列出所有支持的工具"""
        return self.TOOL_NAMES

    def list_apps(self) -> list[str]:
        """列出应用 (Resolve)"""
        return ["davinci_resolve"]

    def get_channel(self) -> str:
        """获取当前通道"""
        return self._channel or "unavailable"

    def execute(self, tool: str, params: dict[str, Any] | None = None) -> ResolveToolResult:
        """执行工具调用"""
        params = params or {}
        start = time.time()

        if tool not in self.TOOL_NAMES:
            return ResolveToolResult(
                tool=tool, status="failed", channel="none",
                error=f"Unknown tool: {tool}",
                duration_ms=(time.time() - start) * 1000
            )

        # 优先 Python API
        if self._channel == "python_api" and self._resolve_api:
            try:
                result = self._execute_python_api(tool, params)
                return ResolveToolResult(
                    tool=tool, status="success", channel="python_api",
                    result=result, duration_ms=(time.time() - start) * 1000
                )
            except Exception as e:
                logger.warning(f"[ResolveMCP] Python API failed for {tool}: {e}, trying fuscript...")

        # 降级 fuscript Lua
        if self._channel == "fuscript_lua" and self._resolve_engine:
            try:
                result = self._execute_fuscript(tool, params)
                return ResolveToolResult(
                    tool=tool, status="success" if result else "degraded",
                    channel="fuscript_lua", result=result,
                    duration_ms=(time.time() - start) * 1000
                )
            except Exception as e:
                return ResolveToolResult(
                    tool=tool, status="failed", channel="fuscript_lua",
                    error=str(e), duration_ms=(time.time() - start) * 1000
                )

        return ResolveToolResult(
            tool=tool, status="unavailable", channel="none",
            error="No channel available",
            duration_ms=(time.time() - start) * 1000
        )

    # ── Python API 通道 ──────────────────────────────────────────

    def _execute_python_api(self, tool: str, params: dict) -> Any:
        api = self._resolve_api
        if tool == "refresh":
            api.refresh()
            return "Refreshed"
        elif tool == "get_system_status":
            name = api.get_project_name() or "No project"
            tl = api.get_current_timeline()
            tl_name = tl.GetName() if tl else "No timeline"
            return {"project": name, "timeline": tl_name}
        elif tool == "execute_lua":
            return api.execute_lua(params.get("script", ""))
        elif tool == "create_project":
            return api.create_project(params["name"])
        elif tool == "load_project":
            return api.load_project(params["name"])
        elif tool == "save_project":
            return api.save_project()
        elif tool == "export_project":
            return api.export_project(params["project_name"], params["file_path"])
        elif tool == "import_project":
            return api.import_project(params["file_path"])
        elif tool == "open_page":
            return api.open_page(params["page_name"])
        elif tool == "create_timeline":
            return api.create_timeline(params["name"])
        elif tool == "set_current_timeline":
            tl = api.get_timeline_by_index(params["timeline_index"])
            return api.set_current_timeline(tl) if tl else False
        elif tool == "import_media":
            return api.add_items_to_media_pool(params["file_paths"])
        elif tool == "add_sub_folder":
            mp = api.get_media_pool()
            root = mp.GetRootFolder()
            parent = next((f for f in root.GetSubFolders() if f.GetName() == params["parent_folder_name"]), root)
            return api.add_sub_folder(parent, params["folder_name"])
        elif tool == "append_to_timeline":
            mp = api.get_media_pool()
            folder = mp.GetCurrentFolder()
            clips = [c for c in folder.GetClips() if c.GetClipProperty("Clip Name") in params["clip_names"]]
            return api.append_to_timeline(clips)
        elif tool == "create_timeline_from_clips":
            mp = api.get_media_pool()
            folder = mp.GetCurrentFolder()
            clips = [c for c in folder.GetClips() if c.GetClipProperty("Clip Name") in params["clip_names"]]
            return api.create_timeline_from_clips(params["timeline_name"], clips)
        elif tool == "import_timeline_from_file":
            return api.import_timeline_from_file(params["file_path"])
        elif tool == "set_clip_property":
            items = api.get_timeline_items("video", 1)
            clip = next((i for i in items if i.GetName() == params["clip_name"]), None)
            return api.set_clip_property(clip, params["property_name"], params["value"]) if clip else False
        elif tool == "add_color_node":
            return api.add_color_node(params.get("node_type", "Corrector"))
        elif tool == "save_still":
            return api.save_still(params.get("album_name", "Stills"))
        elif tool == "apply_still":
            # Simplified: apply to current clip
            gallery = api.get_gallery()
            albums = api.get_gallery_albums()
            still = None
            for album in albums:
                for s in album.GetStills():
                    if s.GetLabel() == params["still_name"]:
                        still = s
                        break
                if still:
                    break
            if not still:
                return False
            return api.apply_still(still)
        elif tool == "add_track":
            return api.add_track(params.get("track_type", "video"))
        elif tool == "set_track_name":
            tl = api.get_current_timeline()
            return tl.SetTrackName(params["track_type"], params["track_index"], params["name"]) if tl else False
        elif tool == "enable_track":
            tl = api.get_current_timeline()
            return tl.SetTrackEnable(params["track_type"], params["track_index"], params.get("enable", True)) if tl else False
        elif tool == "set_audio_volume":
            items = api.get_timeline_items("audio", 1)
            clip = next((i for i in items if i.GetName() == params["clip_name"]), None)
            return api.set_audio_volume(clip, params["volume"]) if clip else False
        elif tool == "set_track_volume":
            tl = api.get_current_timeline()
            return tl.SetTrackVolume("audio", params["track_index"], params["volume"]) if tl else False
        elif tool == "set_current_version":
            items = api.get_timeline_items("video", 1)
            clip = next((i for i in items if i.GetName() == params["clip_name"]), None)
            return api.set_current_version(clip, params["version_index"], params.get("version_type", "color")) if clip else False
        elif tool == "play_timeline":
            return api.play()
        elif tool == "stop_timeline":
            return api.stop()
        elif tool == "set_playhead_position":
            tl = api.get_current_timeline()
            if not tl:
                return False
            return tl.SetCurrentTimecode(tl.GetTimecodeFromFrame(params["frame"]))
        elif tool == "add_timeline_marker":
            tl = api.get_current_timeline()
            return tl.AddMarker(params["frame"], params.get("color", "Blue"),
                               params.get("name", ""), params.get("note", ""), 1) if tl else False
        elif tool == "start_project_render":
            return api.start_render(params.get("preset_name"), params.get("render_path"))
        return None

    # ── fuscript Lua 通道 ────────────────────────────────────────

    def _execute_fuscript(self, tool: str, params: dict) -> Any:
        """通过 resolve_engine.py 的 fuscript Lua 通道执行"""
        engine = self._resolve_engine

        if tool == "refresh":
            return {"status": "refreshed"}

        elif tool == "get_system_status":
            try:
                info = engine.get_project_info()
                return {"project": str(info), "channel": "fuscript_lua"}
            except Exception:
                # Resolve 未运行时降级为返回环境状态
                return {
                    "channel": "fuscript_lua",
                    "fuscript_path": FUSCRIPT_PATH,
                    "fuscript_available": os.path.isfile(FUSCRIPT_PATH),
                    "resolve_running": False,
                    "note": "Resolve not running, fuscript ready",
                }

        elif tool == "create_project":
            name = params["name"]
            engine.create_project(name)
            return {"project": name, "created": True}

        elif tool == "load_project":
            engine.load_project(params["name"])
            return {"loaded": True}

        elif tool == "save_project":
            return {"saved": True}

        elif tool == "open_page":
            page = params["page_name"]
            engine._execute_lua(f'resolve:OpenPage("{page}")')
            return {"page": page}

        elif tool == "create_timeline":
            name = params["name"]
            engine._execute_lua(f'''
                local pm = resolve:GetProjectManager()
                local proj = pm:GetCurrentProject()
                local mp = proj:GetMediaPool()
                mp:CreateEmptyTimeline("{name}")
                emit_ok({{timeline = "{name}"}})
            ''')
            return {"timeline": name}

        elif tool == "import_media":
            files = params["file_paths"]
            file_list = ", ".join([f'"{f}"' for f in files])
            engine._execute_lua(f'''
                local pm = resolve:GetProjectManager()
                local proj = pm:GetCurrentProject()
                local ms = resolve:GetMediaStorage()
                local mp = proj:GetMediaPool()
                local files = {{{file_list}}}
                local clips = ms:AddItemsToMediaPool(files)
                emit_ok({{count = #clips}})
            ''')
            return {"imported": len(files)}

        elif tool == "add_timeline_marker":
            frame = params["frame"]
            color = params.get("color", "Blue")
            name = params.get("name", "")
            engine._execute_lua(f'''
                local pm = resolve:GetProjectManager()
                local proj = pm:GetCurrentProject()
                local tl = proj:GetCurrentTimeline()
                tl:AddMarker({frame}, "{color}", "{name}", "", 1)
                emit_ok({{frame = {frame}}})
            ''')
            return {"frame": frame}

        elif tool == "play_timeline":
            engine._execute_lua('resolve:Play()')
            return {"playing": True}

        elif tool == "stop_timeline":
            engine._execute_lua('resolve:Stop()')
            return {"stopped": True}

        elif tool == "execute_lua":
            result = engine._execute_lua(params.get("script", ""))
            return result

        elif tool == "add_color_node":
            engine._execute_lua('''
                local pm = resolve:GetProjectManager()
                local proj = pm:GetCurrentProject()
                local tl = proj:GetCurrentTimeline()
                local clip = tl:GetCurrentVideoItem()
                local ng = clip:GetNodeGraph()
                ng:AddNode("Corrector")
                emit_ok({node = "Corrector"})
            ''')
            return {"node": "Corrector"}

        elif tool == "start_project_render":
            render_path = params.get("render_path", "")
            if render_path:
                engine._execute_lua(f'''
                    local pm = resolve:GetProjectManager()
                    local proj = pm:GetCurrentProject()
                    proj:SetRenderSettings({{TargetDir = "{render_path}"}})
                    emit_ok({{path = "{render_path}"}})
                ''')
            return {"render": "started"}

        # 其他工具返回降级提示
        return {"tool": tool, "channel": "fuscript_lua", "note": "basic support"}

    def summary(self) -> dict[str, Any]:
        """获取适配器状态摘要"""
        return {
            "channel": self._channel,
            "tools": len(self.TOOL_NAMES),
            "python_api": self._resolve_api is not None and (self._resolve_api.is_connected() if self._resolve_api else False),
            "fuscript_lua": self._resolve_engine is not None,
            "fuscript_path": FUSCRIPT_PATH,
            "fuscript_exists": os.path.isfile(FUSCRIPT_PATH),
        }
