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

from ...config.settings import get_settings
from ..base import BaseEngine, EngineResult  # noqa: E402

# Bridge Client 在项目根目录，延迟导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class PremiereEngine(BaseEngine):
    """Adobe Premiere Pro engine via MCP Bridge / ExtendScript."""

    name = "premiere"

    def __init__(
        self,
        executable_path: Path | str | None = None,
    ):
        self._settings = get_settings()
        self.premiere_path = self._resolve_executable(executable_path)
        super().__init__(executable_path or self.premiere_path or "premiere")
        self._jsx_dir = Path(tempfile.gettempdir()) / "ae_kv_premiere_jsx"
        self._jsx_dir.mkdir(exist_ok=True)

        # 初始化 MCP Bridge Client（延迟导入，避免循环依赖）
        self._bridge_client = None
        self._bridge_available: bool | None = None  # None=未检测, True=在线, False=离线

    def _resolve_executable(self, explicit: Path | str | None) -> Path | None:
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
    def _find_premiere() -> Path | None:
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

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】handlers dict 分发；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        action = kwargs.pop("action", None) or kwargs.pop("task", "import_ae")
        handlers = {
            "import_ae": self.import_ae_comp,
            "import_ae_comp": self.import_ae_comp,
            "auto_edit": self.auto_edit_sequence,
            "auto_edit_sequence": self.auto_edit_sequence,
            "export": self.export_final,
            "export_final": self.export_final,
            "export_via_ffmpeg": self.export_via_ffmpeg,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action: {action}. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)

    async def export_via_ffmpeg(
        self,
        frames_dir: Path | str,
        output_path: Path | str,
        fps: float = 30.0,
        codec: str = "libx264",
        crf: int = 18,
        audio_path: Path | str | None = None,
        frame_pattern: str = "frame_%06d.png",
    ) -> EngineResult:
        """FFmpeg 拼接 AE 渲染的 PNG 帧序列为视频（绕过 AME 编码）。

        完全规避对 PR/AME 的调用依赖：AE 渲染 PNG 序列 → FFmpeg 合成视频。
        """
        from ..ffmpeg.engine import FFmpegEngine

        ff = FFmpegEngine()
        return await ff.image_sequence_to_video(
            frames_dir=frames_dir,
            output_path=output_path,
            fps=fps,
            codec=codec,
            crf=crf,
            audio_path=audio_path,
            frame_pattern=frame_pattern,
        )

    async def import_ae_comp(
        self,
        ae_project_path: Path | str,
        sequence_name: str,
        comp_names: list[str] | None = None,
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
        clips: list[dict[str, Any]],
        music_path: Path | str | None = None,
        music_bpm: float = 128.0,
        beat_drop_offsets: list[float] | None = None,
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

    async def ping(self, **kwargs) -> EngineResult:
        """测试 Premiere Bridge 是否在线。"""
        jsx = (
            "JSON.stringify({pong: true, appName: app.appName, "
            "appVersion: app.version, "
            "project: app.project ? app.project.name : null})"
        )
        return await self._execute_jsx(jsx, "ping")

    async def get_project_info(self, **kwargs) -> EngineResult:
        """获取当前 Premiere 项目信息。"""
        jsx = """
        (function() {
            var proj = app.project;
            if (!proj) return JSON.stringify({status: "error", message: "No project open"});
            var seqs = [];
            for (var i = 0; i < proj.sequences.numSequences; i++) {
                seqs.push(proj.sequences[i].name);
            }
            var bins = [];
            for (var j = 0; j < proj.rootItem.children.numItems; j++) {
                bins.push(proj.rootItem.children[j].name);
            }
            return JSON.stringify({
                name: proj.name,
                path: proj.path ? proj.path.fsName : "",
                sequences: seqs,
                rootItemCount: proj.rootItem.children.numItems
            });
        })();
        """
        return await self._execute_jsx(jsx, "get_project_info")

    async def list_sequences(self, **kwargs) -> EngineResult:
        """列出当前项目所有序列。"""
        jsx = """
        (function() {
            var proj = app.project;
            if (!proj) return JSON.stringify([]);
            var seqs = [];
            for (var i = 0; i < proj.sequences.numSequences; i++) {
                var s = proj.sequences[i];
                seqs.push({
                    name: s.name,
                    videoTracks: s.videoTracks.numTracks,
                    audioTracks: s.audioTracks.numTracks,
                    sequenceID: s.sequenceID
                });
            }
            return JSON.stringify(seqs);
        })();
        """
        return await self._execute_jsx(jsx, "list_sequences")

    async def execute_script(
        self,
        script_content: str,
        timeout: float | None = None,
        **kwargs,
    ) -> EngineResult:
        """直接执行任意 ExtendScript 代码（通过 Bridge）。

        注意：script_content 由调用方提供，不做转义（高阶 API 入口）。
        业务代码应优先使用封装好的方法（import_media/create_sequence 等），
        而非直接调用此方法。
        """
        return await self._execute_jsx(script_content, "execute_script")

    async def import_media(
        self,
        media_paths: list[Path | str],
        bin_name: str = "Imported",
        **kwargs,
    ) -> EngineResult:
        """导入媒体文件到 PR 项目素材箱。

        Args:
            media_paths: 媒体文件路径列表
            bin_name: 目标素材箱名称
        """
        # 安全转义所有路径和名称
        posix_paths = [Path(p).as_posix() for p in media_paths]
        paths_js = self._jsx_escape(posix_paths)
        bin_name_js = self._jsx_escape(bin_name)

        jsx = f"""
        (function() {{
            try {{
                var paths = {paths_js};
                var binName = {bin_name_js};
                var root = app.project.rootItem;
                var bin = root.createBin(binName);
                var imported = [];
                var notFound = [];
                for (var i = 0; i < paths.length; i++) {{
                    var file = new File(paths[i]);
                    if (file.exists) {{
                        app.project.importFiles([paths[i]], true, bin, false);
                        imported.push(paths[i]);
                    }} else {{
                        notFound.push(paths[i]);
                    }}
                }}
                return JSON.stringify({{
                    status: "success",
                    imported: imported,
                    not_found: notFound,
                    importCount: imported.length,
                    bin: binName
                }});
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.toString()
                }});
            }}
        }})();
        """
        return await self._execute_jsx(jsx, "import_media")

    async def create_sequence(
        self,
        name: str,
        preset_name: str = "HD 1080p 30",
        width: int = 1920,
        height: int = 1080,
        fps: float = 30.0,
        **kwargs,
    ) -> EngineResult:
        """创建新序列。

        Args:
            name: 序列名称
            preset_name: PR 序列预设名（如 "HD 1080p 30", "4K UHD 29.97"）
            width: 视频宽度（信息记录用）
            height: 视频高度（信息记录用）
            fps: 帧率（信息记录用）
        """
        name_js = self._jsx_escape(name)
        preset_js = self._jsx_escape(preset_name)

        jsx = f"""
        (function() {{
            try {{
                var seqName = {name_js};
                var preset = {preset_js};
                var seq = app.project.createNewSequence(seqName, preset);
                if (seq) {{
                    return JSON.stringify({{
                        status: "success",
                        sequence: seqName,
                        sequenceID: seq.sequenceID,
                        preset: preset
                    }});
                }}
                return JSON.stringify({{
                    status: "error",
                    message: "createNewSequence returned null"
                }});
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.toString()
                }});
            }}
        }})();
        """
        return await self._execute_jsx(jsx, "create_sequence")

    async def add_clip_to_timeline(
        self,
        media_path: Path | str,
        track_index: int = 0,
        start_time_ticks: int | None = None,
        start_time_seconds: float = 0.0,
        video_track: bool = True,
        audio_track: bool = True,
        **kwargs,
    ) -> EngineResult:
        """添加剪辑到时间轴。

        Args:
            media_path: 媒体文件路径（项目中已有或新导入）
            track_index: 轨道索引（0-based）
            start_time_ticks: 起始时间（ticks），优先级高于 start_time_seconds
            start_time_seconds: 起始时间（秒），默认 0
            video_track: 是否插入视频轨道
            audio_track: 是否插入音频轨道
        """
        path_posix = Path(media_path).as_posix()
        path_js = self._jsx_escape(path_posix)
        path_stem_js = self._jsx_escape(Path(media_path).stem)
        if start_time_ticks is None:
            start_time_ticks = int(start_time_seconds * self.TICKS_PER_SECOND)

        jsx = f"""
        (function() {{
            try {{
                var seq = app.project.activeSequence;
                if (!seq) {{
                    return JSON.stringify({{status: "error", message: "No active sequence"}});
                }}
                var filePath = {path_js};
                var fileStem = {path_stem_js};
                var file = new File(filePath);

                // 尝试在项目中找已导入的素材，否则导入
                var importedItem = null;
                function findItem(root) {{
                    for (var i = 0; i < root.children.numItems; i++) {{
                        var child = root.children[i];
                        if (child.type === ProjectItemType.CLIP && child.name.indexOf(fileStem) >= 0) {{
                            return child;
                        }}
                        if (child.type === ProjectItemType.BIN) {{
                            var found = findItem(child);
                            if (found) return found;
                        }}
                    }}
                    return null;
                }}
                importedItem = findItem(app.project.rootItem);
                if (!importedItem && file.exists) {{
                    app.project.importFiles([filePath], true, app.project.rootItem, false);
                    importedItem = findItem(app.project.rootItem);
                }}
                if (!importedItem) {{
                    return JSON.stringify({{status: "error", message: "Failed to find or import: " + filePath}});
                }}

                var vTrack = seq.videoTracks[{track_index}];
                var aTrack = seq.audioTracks[{track_index}];
                var t = {start_time_ticks};
                if (vTrack) {{
                    vTrack.insertClip(importedItem, t);
                }}
                // 音频轨道插入（PR 中视频和音频通常联动，这里保守处理）
                return JSON.stringify({{
                    status: "success",
                    clip: importedItem.name,
                    trackIndex: {track_index},
                    startTicks: t,
                    startSeconds: t / {self.TICKS_PER_SECOND}
                }});
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.toString()
                }});
            }}
        }})();
        """
        return await self._execute_jsx(jsx, "add_clip_to_timeline")

    async def apply_transition(
        self,
        track_index: int,
        clip_index: int,
        transition_name: str = "Cross Dissolve",
        duration_seconds: float = 1.0,
        transition_type: str = "video",  # "video" | "audio"
        **kwargs,
    ) -> EngineResult:
        """在剪辑端点应用转场效果。

        Args:
            track_index: 轨道索引
            clip_index: 剪辑索引
            transition_name: 转场名称（PR 内置："Cross Dissolve", "Dip to Black", "Film Dissolve" 等）
            duration_seconds: 转场时长（秒）
            transition_type: "video" 或 "audio"
        """
        trans_name_js = self._jsx_escape(transition_name)
        trans_type_js = self._jsx_escape(transition_type)
        duration_ticks = int(duration_seconds * self.TICKS_PER_SECOND)

        jsx = f"""
        (function() {{
            try {{
                var seq = app.project.activeSequence;
                if (!seq) return JSON.stringify({{status: "error", message: "No active sequence"}});
                var tracks = ({trans_type_js} === "audio") ? seq.audioTracks : seq.videoTracks;
                var track = tracks[{track_index}];
                if (!track) return JSON.stringify({{status: "error", message: "Track not found"}});
                var clip = track.clips[{clip_index}];
                if (!clip) return JSON.stringify({{status: "error", message: "Clip not found"}});

                var transName = {trans_name_js};
                var durTicks = {duration_ticks};

                // 在剪辑起点创建转场
                var trans = null;
                try {{
                    trans = clip.createTransition(transName, 0, durTicks, true);
                }} catch(e1) {{
                    // 起点失败尝试终点
                    try {{
                        trans = clip.createTransition(transName, 1, durTicks, true);
                    }} catch(e2) {{
                        return JSON.stringify({{status: "error", message: "createTransition failed: " + e2.toString()}});
                    }}
                }}
                if (trans) {{
                    return JSON.stringify({{
                        status: "success",
                        transition: transName,
                        durationTicks: durTicks,
                        durationSeconds: durTicks / {self.TICKS_PER_SECOND},
                        clipIndex: {clip_index}
                    }});
                }}
                return JSON.stringify({{status: "error", message: "applyTransition returned null"}});
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.toString()
                }});
            }}
        }})();
        """
        return await self._execute_jsx(jsx, "apply_transition")

    async def export_sequence(
        self,
        output_path: Path | str,
        sequence_name: str | None = None,
        preset_name: str = "H.264 Match Source - High bitrate",
        **kwargs,
    ) -> EngineResult:
        """使用 PR 内置 exportAsMediaDirect 导出当前序列或指定序列。

        Args:
            output_path: 输出文件路径
            sequence_name: 序列名（None = 当前活动序列）
            preset_name: 导出预设名
        """
        out_posix = Path(output_path).as_posix()
        out_js = self._jsx_escape(out_posix)
        preset_js = self._jsx_escape(preset_name)
        seq_name_js = self._jsx_escape(sequence_name) if sequence_name else None

        if sequence_name:
            seq_select_js = f"""
                var targetSeq = null;
                var sn = {seq_name_js};
                for (var i = 0; i < proj.sequences.numSequences; i++) {{
                    if (proj.sequences[i].name === sn) {{ targetSeq = proj.sequences[i]; break; }}
                }}
                if (!targetSeq) return JSON.stringify({{status: "error", message: "Sequence not found: " + sn}});
            """
            seq_var = "targetSeq"
        else:
            seq_select_js = """
                var targetSeq = app.project.activeSequence;
                if (!targetSeq) return JSON.stringify({status: "error", message: "No active sequence"});
            """
            seq_var = "targetSeq"

        jsx = f"""
        (function() {{
            try {{
                var proj = app.project;
                {seq_select_js}
                var outFile = new File({out_js});
                var preset = {preset_js};
                try {{
                    {seq_var}.exportAsMediaDirect(outFile.fsName, preset, 0);
                    return JSON.stringify({{
                        status: "success",
                        output: {out_js},
                        preset: preset,
                        sequence: {seq_var}.name
                    }});
                }} catch(e1) {{
                    // 兜底：Match Source
                    try {{
                        {seq_var}.exportAsMediaDirect(outFile.fsName, "Match Source - High bitrate", 0);
                        return JSON.stringify({{
                            status: "success",
                            output: {out_js},
                            preset: "Match Source - High bitrate (fallback)",
                            sequence: {seq_var}.name,
                            note: "Requested preset failed, used fallback: " + e1.toString()
                        }});
                    }} catch(e2) {{
                        return JSON.stringify({{status: "error", message: "Export failed: " + e2.toString()}});
                    }}
                }}
            }} catch (e) {{
                return JSON.stringify({{
                    status: "error",
                    message: e.toString()
                }});
            }}
        }})();
        """
        return await self._execute_jsx(jsx, "export_sequence")

    # ------------------------------------------------------------------
    # 高级工作流 API（从原 premiere/engine.py 合并 + 安全转义）
    # ------------------------------------------------------------------

    def _jsx_escape(self, value: Any) -> str:
        """将 Python 值安全地序列化为 JSX 字符串字面量。

        字符串经 json.dumps 转义（含引号、反斜杠、换行、Unicode）；
        数字/布尔/None 直接转换；列表/字典递归序列化为 JS 数组/对象字面量。
        这是防止 JSX 注入的核心防线，所有用户可控参数必须经过此函数。
        """
        return json.dumps(value, ensure_ascii=False)

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
        logger.info("[Premiere] Run manually: File > Scripts > Run Script File")

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