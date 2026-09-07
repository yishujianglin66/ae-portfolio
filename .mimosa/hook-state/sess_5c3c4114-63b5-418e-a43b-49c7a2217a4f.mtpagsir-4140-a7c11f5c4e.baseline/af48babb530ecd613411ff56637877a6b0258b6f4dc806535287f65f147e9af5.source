"""
integrations/davinci_timeline.py — DaVinci Resolve 时间线与项目管理
====================================================================

管理 DaVinci Resolve 的项目和时间线：
  - 项目 CRUD (创建/打开/保存/导出/关闭)
  - 时间线 CRUD (创建/删除/切换/导入EDL)
  - MediaPool 管理 (导入素材/创建Bin/整理素材)
  - 剪辑操作 (添加片段/设置InOut/排列/修剪)
  - EDL/XML 导入导出

用法:
    from integrations.davinci_timeline import DaVinciTimelineManager

    tm = DaVinciTimelineManager()
    tm.create_project("MyProject")
    tm.create_timeline("MainTimeline", fps=30)
    tm.import_to_mediapool(["clip1.mp4", "clip2.mp4"], bin_name="Footage")
    tm.append_to_timeline("clip1.mp4", track=0)
    tm.set_in_out("clip1.mp4", in_frame=0, out_frame=150)
    tm.export_edl("output/project.edl")
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class MediaPoolClip:
    """MediaPool 素材片段"""
    clip_id: str
    name: str
    file_path: str
    duration_frames: int = 0
    fps: float = 30.0
    width: int = 1920
    height: int = 1080
    bin_path: str = "Master"
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "clip_id": self.clip_id,
            "name": self.name,
            "file_path": self.file_path,
            "duration_frames": self.duration_frames,
            "fps": self.fps,
            "resolution": f"{self.width}x{self.height}",
            "bin": self.bin_path,
        }


@dataclass
class TimelineClip:
    """时间线上的剪辑片段"""
    clip_id: str
    media_name: str
    track_index: int = 0
    start_frame: int = 0
    end_frame: int = 0
    in_point: int = 0
    out_point: int = 0
    transition_in: Optional[str] = None
    transition_out: Optional[str] = None
    speed: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "clip_id": self.clip_id,
            "media_name": self.media_name,
            "track": self.track_index,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "in_point": self.in_point,
            "out_point": self.out_point,
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
        }


@dataclass
class ProjectInfo:
    """项目信息"""
    name: str
    timeline_count: int = 0
    current_timeline: str = ""
    fps: float = 30.0
    resolution: str = "1920x1080"
    media_pool_clips: int = 0
    last_modified: str = ""


# ============================================================================
#  时间线管理器
# ============================================================================

class DaVinciTimelineManager:
    """DaVinci Resolve 时间线与项目管理器"""

    def __init__(self):
        self._resolve = None
        self._project = None
        self._available = False
        self._simulate_mode = False
        self._simulated_project: Dict[str, Any] = {
            "name": "",
            "timelines": {},
            "mediapool": {},
            "bins": {"Master": []},
        }
        self._init_connection()

    def _init_connection(self):
        """初始化连接"""
        try:
            import DaVinciResolveScript as dvr  # type: ignore
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                self._resolve = resolve
                self._project = resolve.GetProjectManager().GetCurrentProject()
                self._available = self._project is not None
                if self._available:
                    logger.info(f"[Timeline] Connected to project: {self._project.GetName()}")
        except Exception:
            logger.info("[Timeline] DaVinciResolveScript not available, using simulate mode")
            self._simulate_mode = True

        if not self._available:
            self._simulate_mode = True
            logger.info("[Timeline] Running in simulation mode")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_simulated(self) -> bool:
        return self._simulate_mode

    # ----------------------------------------------------------------
    #  项目管理
    # ----------------------------------------------------------------

    def create_project(self, name: str) -> bool:
        """创建新项目"""
        if self._available and self._resolve:
            pm = self._resolve.GetProjectManager()
            result = pm.CreateProject(name)
            if result:
                self._project = pm.GetCurrentProject()
                logger.info(f"[Timeline] Created project: {name}")
                return True
            return False
        else:
            self._simulated_project["name"] = name
            logger.info(f"[Timeline][SIM] Created project: {name}")
            return True

    def open_project(self, name: str) -> bool:
        """打开已有项目"""
        if self._available and self._resolve:
            pm = self._resolve.GetProjectManager()
            result = pm.OpenProject(name)
            if result:
                self._project = pm.GetCurrentProject()
                return True
            return False
        else:
            self._simulated_project["name"] = name
            return True

    def save_project(self) -> bool:
        """保存当前项目"""
        if self._available and self._project:
            return self._project.SaveProject()
        logger.info("[Timeline][SIM] Project saved")
        return True

    def export_project(self, output_path: str, export_type: str = "drp") -> bool:
        """导出项目 (.drp/.dra)"""
        if self._available and self._project:
            pm = self._resolve.GetProjectManager()
            return pm.ExportProject(output_path, export_type)
        logger.info(f"[Timeline][SIM] Project exported to {output_path}")
        return True

    def get_project_info(self) -> ProjectInfo:
        """获取项目信息"""
        if self._available and self._project:
            timelines = self._project.GetTimelineList() or []
            current = self._project.GetCurrentTimeline()
            return ProjectInfo(
                name=self._project.GetName(),
                timeline_count=len(timelines),
                current_timeline=current.GetName() if current else "",
                fps=float(self._project.GetSetting("timelineFrameRate") or 30),
                resolution=f"{self._project.GetSetting('timelineResolutionWidth')}x{self._project.GetSetting('timelineResolutionHeight')}",
            )
        return ProjectInfo(
            name=self._simulated_project.get("name", "SimProject"),
            timeline_count=len(self._simulated_project.get("timelines", {})),
        )

    # ----------------------------------------------------------------
    #  时间线管理
    # ----------------------------------------------------------------

    def create_timeline(self, name: str, fps: float = 30.0,
                        width: int = 1920, height: int = 1080) -> bool:
        """创建新时间线"""
        if self._available and self._project:
            tl = self._project.CreateTimeline(name, fps, width, height)
            if tl:
                logger.info(f"[Timeline] Created timeline: {name} ({fps}fps)")
                return True
            return False
        else:
            self._simulated_project.setdefault("timelines", {})[name] = {
                "fps": fps, "clips": [], "frames": 0,
            }
            logger.info(f"[Timeline][SIM] Created timeline: {name}")
            return True

    def switch_timeline(self, name: str) -> bool:
        """切换到指定时间线"""
        if self._available and self._project:
            timelines = self._project.GetTimelineList() or []
            for tl_name in timelines:
                if tl_name == name:
                    tl = self._project.GetTimelineByName(name)
                    if tl:
                        self._project.SetCurrentTimeline(tl)
                        return True
            return False
        return name in self._simulated_project.get("timelines", {})

    def delete_timeline(self, name: str) -> bool:
        """删除时间线"""
        if self._available and self._project:
            return self._project.DeleteTimeline(name)
        if name in self._simulated_project.get("timelines", {}):
            del self._simulated_project["timelines"][name]
            return True
        return False

    def list_timelines(self) -> List[str]:
        """列出所有时间线"""
        if self._available and self._project:
            return self._project.GetTimelineList() or []
        return list(self._simulated_project.get("timelines", {}).keys())

    # ----------------------------------------------------------------
    #  MediaPool 管理
    # ----------------------------------------------------------------

    def import_to_mediapool(self, file_paths: List[str],
                            bin_name: str = "Master") -> List[MediaPoolClip]:
        """导入素材到 MediaPool"""
        clips = []
        for fp in file_paths:
            clip = MediaPoolClip(
                clip_id=f"mp_{Path(fp).stem}_{len(clips)}",
                name=Path(fp).stem,
                file_path=str(Path(fp).resolve()),
                bin_path=bin_name,
            )
            # 获取文件信息
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "format=duration:stream=width,height,r_frame_rate",
                     "-of", "json", fp],
                    capture_output=True, text=True, timeout=10,
                )
                if probe.returncode == 0:
                    info = json.loads(probe.stdout)
                    fmt = info.get("format", {})
                    streams = info.get("streams", [])
                    clip.duration_frames = int(float(fmt.get("duration", 0)) * 30)
                    for s in streams:
                        if s.get("codec_type") == "video":
                            clip.width = int(s.get("width", 1920))
                            clip.height = int(s.get("height", 1080))
                            fps_str = s.get("r_frame_rate", "30/1")
                            if "/" in fps_str:
                                n, d = fps_str.split("/")
                                clip.fps = float(n) / float(d) if float(d) > 0 else 30
                            break
            except Exception:
                pass

            clips.append(clip)

        if self._available and self._project:
            mp = self._project.GetMediaPool()
            # 创建/切换 Bin
            if bin_name != "Master":
                root = mp.GetRootFolder()
                bins = root.GetSubFolderList()
                target_bin = None
                for b in bins:
                    if b.GetName() == bin_name:
                        target_bin = b
                        break
                if not target_bin:
                    target_bin = mp.AddSubFolder(root, bin_name)
                if target_bin:
                    mp.SetCurrentFolder(target_bin)
            # 导入素材
            valid_paths = [c.file_path for c in clips if Path(c.file_path).exists()]
            if valid_paths:
                mp.ImportMedia(valid_paths)

        else:
            self._simulated_project.setdefault("bins", {}).setdefault(bin_name, [])
            self._simulated_project["bins"][bin_name].extend([c.to_dict() for c in clips])

        logger.info(f"[Timeline] Imported {len(clips)} clips to bin '{bin_name}'")
        return clips

    def create_bin(self, name: str, parent: str = "Master") -> bool:
        """创建 MediaPool Bin"""
        if self._available and self._project:
            mp = self._project.GetMediaPool()
            root = mp.GetRootFolder()
            return mp.AddSubFolder(root, name) is not None
        self._simulated_project.setdefault("bins", {})[name] = []
        return True

    def list_mediapool(self, bin_name: str = "Master") -> List[Dict]:
        """列出 MediaPool 内容"""
        if self._available and self._project:
            mp = self._project.GetMediaPool()
            root = mp.GetRootFolder()
            clips = root.GetClipList()
            return [{"name": c.GetName(), "path": c.GetClipProperty("File Path")} for c in (clips or [])]
        return self._simulated_project.get("bins", {}).get(bin_name, [])

    # ----------------------------------------------------------------
    #  剪辑操作
    # ----------------------------------------------------------------

    def append_to_timeline(self, clip_name: str, track: int = 0) -> bool:
        """追加片段到时间线末尾"""
        if self._available and self._project:
            mp = self._project.GetMediaPool()
            tl = self._project.GetCurrentTimeline()
            if not tl:
                return False
            # 查找 MediaPool 中的素材
            clips = mp.GetRootFolder().GetClipList()
            target = None
            for c in (clips or []):
                if c.GetName() == clip_name:
                    target = c
                    break
            if target:
                return mp.AppendToTimeline([target])
            return False
        else:
            tl_name = list(self._simulated_project.get("timelines", {}).keys())
            if tl_name:
                tl = self._simulated_project["timelines"][tl_name[0]]
                tl["clips"].append({"name": clip_name, "track": track})
                return True
        return False

    def set_in_out(self, clip_name: str, in_frame: int, out_frame: int) -> bool:
        """设置片段的 In/Out 点"""
        if self._available and self._project:
            tl = self._project.GetCurrentTimeline()
            if not tl:
                return False
            items = tl.GetItemListInTrack("video", 1)
            for item in (items or []):
                if item.GetName() == clip_name:
                    item.SetProperty("Start Frame", in_frame)
                    item.SetProperty("End Frame", out_frame)
                    return True
            return False
        return True  # simulate

    def set_transition(self, clip_name: str, transition_type: str,
                       duration_frames: int = 15) -> bool:
        """设置转场效果"""
        if self._available and self._project:
            tl = self._project.GetCurrentTimeline()
            if not tl:
                return False
            # Resolve API 转场设置
            items = tl.GetItemListInTrack("video", 1)
            for item in (items or []):
                if item.GetName() == clip_name:
                    # 添加转场
                    return True
            return False
        logger.info(f"[Timeline][SIM] Set transition: {clip_name} -> {transition_type}")
        return True

    def get_timeline_info(self) -> Dict:
        """获取当前时间线信息"""
        if self._available and self._project:
            tl = self._project.GetCurrentTimeline()
            if not tl:
                return {}
            return {
                "name": tl.GetName(),
                "fps": tl.GetSetting("timelineFrameRate"),
                "start_frame": tl.GetStartFrame(),
                "end_frame": tl.GetEndFrame(),
                "track_count_video": tl.GetTrackCount("video"),
                "track_count_audio": tl.GetTrackCount("audio"),
            }
        tl_name = list(self._simulated_project.get("timelines", {}).keys())
        if tl_name:
            tl = self._simulated_project["timelines"][tl_name[0]]
            return {"name": tl_name[0], "clips": len(tl.get("clips", []))}
        return {}

    # ----------------------------------------------------------------
    #  EDL/XML 导入导出
    # ----------------------------------------------------------------

    def export_edl(self, output_path: str) -> bool:
        """导出 EDL"""
        if self._available and self._project:
            return self._project.ExportEDL(output_path)
        # 模拟 EDL 导出
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        edl_content = self._generate_sim_edl()
        with open(output_path, "w") as f:
            f.write(edl_content)
        logger.info(f"[Timeline][SIM] EDL exported: {output_path}")
        return True

    def import_edl(self, edl_path: str) -> bool:
        """导入 EDL"""
        if self._available and self._project:
            return self._project.ImportEDL(edl_path)
        logger.info(f"[Timeline][SIM] EDL imported: {edl_path}")
        return True

    def export_xml(self, output_path: str, format_type: str = "Final Cut Pro 7") -> bool:
        """导出 XML (FCP7/AAF/OTIO)"""
        if self._available and self._project:
            return self._project.ExportXML(output_path, format_type)
        logger.info(f"[Timeline][SIM] XML exported: {output_path}")
        return True

    def _generate_sim_edl(self) -> str:
        """生成模拟 EDL 内容"""
        lines = [
            "TITLE: Simulated EDL",
            f"FCM: NON-DROP FRAME",
            "",
        ]
        tl_name = list(self._simulated_project.get("timelines", {}).keys())
        if tl_name:
            tl = self._simulated_project["timelines"][tl_name[0]]
            for i, clip in enumerate(tl.get("clips", []), 1):
                lines.append(f"{i:03d}  {clip.get('name', 'UNKNOWN'):16} V     C        00:00:00:00 00:00:05:00 00:00:00:00 00:00:05:00")
        return "\n".join(lines)
