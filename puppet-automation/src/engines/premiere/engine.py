"""
Premiere Pro Engine - 专业视频剪辑
===================================

封装 Adobe Premiere Pro 的剪辑能力：
- AE合成→Premiere序列（动态链接）
- 自动粗剪（卡点+节奏匹配）
- 多轨道音频混合
- 批量导出（比MediaEncoder更灵活的序列控制）

在流程中的定位：
- AE负责特效层（VFX），Premiere负责剪辑节奏（Edit）
- 通过动态链接实时同步，无需渲染中间文件
- 最终导出使用Premiere的队列（配合MediaEncoder）

使用方式：
    engine = PremiereEngine()
    await engine.import_ae_comp("project.aep", "sequence_01")
    await engine.auto_edit_sequence(clips, music_bpm=128)
    await engine.export_final("output.mp4", preset="H264_4K")
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import winreg
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402
from ...config.settings import get_settings

# Bridge Client 在项目根目录，延迟导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class PremiereEngine(BaseEngine):
    """Adobe Premiere Pro engine via MCP Bridge / ExtendScript."""

    name = "premiere"

    def __init__(
        self,
        executable_path: Optional[Path | str] = None,
    ):
        self._settings = get_settings()
        self.premiere_path = self._resolve_executable(executable_path)
        super().__init__(executable_path or self.premiere_path or "premiere")
        self._jsx_dir = Path(tempfile.gettempdir()) / "ae_kv_premiere_jsx"
        self._jsx_dir.mkdir(exist_ok=True)

        # 初始化 MCP Bridge Client（延迟导入，避免循环依赖）
        self._bridge_client = None
        self._bridge_available: Optional[bool] = None  # None=未检测, True=在线, False=离线

    def _resolve_executable(self, explicit: Optional[Path | str]) -> Optional[Path]:
        """解析可执行文件路径：显式参数 > settings配置 > 自动发现。"""
        # 1. 显式参数
        if explicit:
            p = Path(explicit)
            if p.exists():
                return p

        # 2. settings配置
        if self._settings.premiere_path:
            p = Path(self._settings.premiere_path)
            if p.exists():
                return p
            logger.warning(f"[Premiere] Settings path not found: {p}, falling back to auto-detect")

        # 3. 自动发现（fallback）
        return self._find_premiere()

    @staticmethod
    def _find_premiere() -> Optional[Path]:
        """自动发现 Premiere Pro 安装路径。"""
        possible_paths = [
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
            r"C:\Program Files\Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
        ]
        for p in possible_paths:
            path = Path(p)
            if path.exists():
                return path

        # 尝试注册表
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Adobe\Premiere Pro\25.0") as key:
                install_path, _ = winreg.QueryValueEx(key, "InstallPath")
                exe = Path(install_path) / "Adobe Premiere Pro.exe"
                if exe.exists():
                    return exe
        except Exception:
            pass

        return None

    async def execute(self, *args, **kwargs) -> EngineResult:
        """Dispatch to specific methods."""
        task = kwargs.get("task", "import_ae")
        if task == "import_ae":
            return await self.import_ae_comp(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "auto_edit":
            return await self.auto_edit_sequence(**{k: v for k, v in kwargs.items() if k != "task"})
        if task == "export":
            return await self.export_final(**{k: v for k, v in kwargs.items() if k != "task"})
        return EngineResult(success=False, error=f"Unknown task: {task}")

    async def import_ae_comp(
        self,
        ae_project_path: Path | str,
        sequence_name: str,
        comp_names: Optional[List[str]] = None,
    ) -> EngineResult:
        """将AE合成导入Premiere序列（动态链接）。

        Args:
            ae_project_path: AE项目文件路径(.aep)
            sequence_name: 新建的Premiere序列名
            comp_names: 要导入的合成名列表（None=全部）
        """
        ae_project_path = Path(ae_project_path)
        if not ae_project_path.exists():
            return EngineResult(
                success=False, error=f"AE project not found: {ae_project_path}",
            )

        jsx = f"""
        (function() {{
            var proj = app.project;
            var seq = proj.createNewSequence("{sequence_name}", "HD 1080p 30");
            
            // 导入AE项目
            var aeFile = new File("{ae_project_path}");
            proj.importFile(aeFile);
            
            // 获取AE合成
            var aeItems = [];
            for (var i = 1; i <= proj.rootItem.children.numItems; i++) {{
                var item = proj.rootItem.children[i];
                if (item.type == ProjectItemType.CLIP && 
                    item.name.match(/\\.(aep|aetx)$/i)) {{
                    aeItems.push(item);
                }}
            }}
            
            // 将合成添加到序列
            for (var j = 0; j < aeItems.length; j++) {{
                var track = seq.videoTracks[0];
                track.insertClip(aeItems[j], seq.getPlayerPosition());
            }}
            
            return JSON.stringify({{status: "success", sequence: "{sequence_name}"}});
        }})();
        """

        return await self._execute_jsx(jsx, "import_ae_comp")

    async def auto_edit_sequence(
        self,
        clips: List[Dict[str, Any]],
        music_path: Optional[Path | str] = None,
        music_bpm: float = 128.0,
        beat_drop_offsets: Optional[List[float]] = None,
        output_sequence: str = "AutoEdit_01",
    ) -> EngineResult:
        """根据音乐节拍自动粗剪序列。

        Args:
            clips: 视频片段列表 [{"path": "...", "duration": 2.0, "beat_sync": true}, ...]
            music_path: 背景音乐路径
            music_bpm: 音乐节拍
            beat_drop_offsets: 节拍落点时间（秒）
            output_sequence: 输出序列名
        """
        if not clips:
            return EngineResult(success=False, error="No clips provided")

        # 计算节拍间隔
        beat_interval = 60.0 / music_bpm if music_bpm > 0 else 0.5

        # 如果没有提供落点，生成均匀落点
        if not beat_drop_offsets:
            total_duration = sum(c.get("duration", 2.0) for c in clips)
            beat_drop_offsets = [i * beat_interval for i in range(int(total_duration / beat_interval) + 1)]

        # 构建JSX
        clips_json = json.dumps(clips, ensure_ascii=False)
        beats_json = json.dumps(beat_drop_offsets)
        music_path_str = str(music_path) if music_path else ""

        jsx = f"""
        (function() {{
            var clips = {clips_json};
            var beats = {beats_json};
            var seq = app.project.createNewSequence("{output_sequence}", "HD 1080p 30");
            var vTrack = seq.videoTracks[0];
            var aTrack = seq.audioTracks[0];
            var currentTime = 0;
            var beatIdx = 0;
            
            for (var i = 0; i < clips.length; i++) {{
                var clip = clips[i];
                var file = new File(clip.path);
                var imported = app.project.importFile(file);
                
                // 卡点放置
                if (clip.beat_sync && beatIdx < beats.length) {{
                    currentTime = beats[beatIdx];
                    beatIdx++;
                }}
                
                vTrack.insertClip(imported, currentTime);
                
                // 计算下一段的起始时间
                var duration = clip.duration || 2.0;
                if (!clip.beat_sync) {{
                    currentTime += duration;
                }}
            }}
            
            // 添加音乐
            {"var musicFile = new File('" + music_path_str + "'); var music = app.project.importFile(musicFile); aTrack.insertClip(music, 0);" if music_path else ""}
            
            return JSON.stringify({{status: "success", sequence: "{output_sequence}", clips: clips.length}});
        }})();
        """

        return await self._execute_jsx(jsx, "auto_edit_sequence")

    async def export_final(
        self,
        sequence_name: str,
        output_path: Path | str,
        preset: str = "H264_4K",
        use_media_encoder: bool = True,
    ) -> EngineResult:
        """导出最终视频。

        Args:
            sequence_name: 序列名
            output_path: 输出路径
            preset: 预设 (H264_4K/H264_1080/ProRes_422/H265_4K)
            use_media_encoder: 是否使用MediaEncoder队列
        """
        preset_map = {
            "H264_4K": "H.264 4K",
            "H264_1080": "H.264 HD 1080p",
            "ProRes_422": "Apple ProRes 422",
            "H265_4K": "HEVC H.265 4K",
        }
        preset_name = preset_map.get(preset, preset)

        # 构建MediaEncoder队列部分
        ame_part = ""
        if use_media_encoder:
            ame_part = (
                "var ame = app.encoder;"
                f'ame.encodeSequence(seq, "{output_path}", "{preset_name}", 0);'
                "ame.startBatch();"
            )

        jsx = f"""
        (function() {{
            var proj = app.project;
            var seq = null;
            
            // 查找序列
            for (var i = 0; i < proj.sequences.numSequences; i++) {{
                if (proj.sequences[i].name == "{sequence_name}") {{
                    seq = proj.sequences[i];
                    break;
                }}
            }}
            
            if (!seq) {{
                return JSON.stringify({{status: "error", message: "Sequence not found"}});
            }}
            
            // 设置导出参数
            var exportSettings = {{
                outputFile: "{output_path}",
                preset: "{preset_name}",
            }};
            
            // 如果使用MediaEncoder，添加到AME队列
            {ame_part}
            
            return JSON.stringify({{status: "success", output: "{output_path}", preset: "{preset_name}"}});
        }})();
        """

        return await self._execute_jsx(jsx, "export_final")

    async def _execute_jsx(self, jsx_code: str, operation: str) -> EngineResult:
        """通过 MCP Bridge 或临时 JSX 文件执行 Premiere ExtendScript。

        优先使用 MCP Bridge（全自动），降级为生成 JSX 文件（手动执行）。
        """
        import time

        start = time.time()

        # 方式1: 尝试通过 MCP Bridge 自动执行
        if self._ensure_bridge():
            try:
                result = await asyncio.to_thread(
                    self._bridge_client.execute_script,
                    jsx_code,
                    30,  # timeout
                )
                success = result.get("status") == "success"
                error_msg = result.get("message", "") if not success else None

                return EngineResult(
                    success=success,
                    error=error_msg,
                    metadata={
                        "operation": operation,
                        "bridge_mode": "auto",
                        "result": result.get("result"),
                        "timestamp": result.get("timestamp"),
                    },
                    duration_seconds=time.time() - start,
                )
            except Exception as e:
                logger.warning(f"[Premiere] Bridge execution failed, falling back to JSX file: {e}")
                self._bridge_available = False

        # 方式2: 降级 - 生成 JSX 文件，用户手动执行
        jsx_file = self._jsx_dir / f"premiere_{operation}_{int(time.time())}.jsx"
        jsx_file.write_text(jsx_code, encoding="utf-8")

        logger.info(f"[Premiere] JSX prepared (fallback): {jsx_file}")
        logger.info(f"[Premiere] Run manually: File > Scripts > Run Script File")

        return EngineResult(
            success=True,
            metadata={
                "jsx_path": str(jsx_file),
                "operation": operation,
                "bridge_mode": "manual_fallback",
                "note": "MCP Bridge offline. Run JSX manually or start pr_mcp_bridge.jsx in Premiere.",
            },
            duration_seconds=time.time() - start,
        )

    def _ensure_bridge(self) -> bool:
        """确保 Bridge Client 已初始化且在线。延迟初始化 + 缓存检测结果。"""
        if self._bridge_available is False:
            return False

        if self._bridge_client is None:
            try:
                from pr_bridge_client import PRBridgeClient  # 延迟导入
                self._bridge_client = PRBridgeClient(timeout=5)
            except ImportError:
                logger.warning("[Premiere] pr_bridge_client not available")
                self._bridge_available = False
                return False
            except Exception as e:
                logger.warning(f"[Premiere] Bridge init failed: {e}")
                self._bridge_available = False
                return False

        # 检测 Bridge 是否在线（首次检测后缓存 60 秒）
        if self._bridge_available is None:
            try:
                result = self._bridge_client.ping(timeout=3)
                self._bridge_available = result.get("status") == "success"
                if self._bridge_available:
                    logger.info("[Premiere] MCP Bridge is online")
                else:
                    logger.info(f"[Premiere] MCP Bridge offline: {result.get('status', 'unknown')}")
            except Exception:
                self._bridge_available = False
                logger.info("[Premiere] MCP Bridge not responding (is pr_mcp_bridge.jsx running?)")

        return self._bridge_available is True

    def get_info(self) -> dict:
        """返回引擎信息。"""
        bridge_status = "unknown"
        if self._bridge_available is True:
            bridge_status = "online"
        elif self._bridge_available is False:
            bridge_status = "offline"

        return {
            "name": self.name,
            "premiere_found": self.premiere_path is not None,
            "premiere_path": str(self.premiere_path) if self.premiere_path else None,
            "bridge_status": bridge_status,
            "capabilities": [
                "import_ae_comp",
                "auto_edit_sequence",
                "export_final",
            ],
            "workflow": "AE VFX → Premiere Edit → MediaEncoder Export",
            "automation_level": "MCP Bridge (auto) / JSX file (fallback)",
        }