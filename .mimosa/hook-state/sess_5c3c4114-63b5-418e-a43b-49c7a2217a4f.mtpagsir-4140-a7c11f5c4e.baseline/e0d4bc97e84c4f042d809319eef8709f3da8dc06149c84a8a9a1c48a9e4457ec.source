"""
pipeline/stages/perception.py - 感知阶段
=========================================
收集素材信息：扫描文件、提取元数据、基础帧分析
"""
from __future__ import annotations

import os
import glob
import time
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".psd", ".webp"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"}


class PerceptionStage:
    """感知阶段：扫描素材、提取元数据"""

    def __init__(self, config):
        self.config = config

    def run(self, previous_data: Dict) -> Dict:
        """执行感知阶段"""
        result = {
            "materials": [],
            "videos": [],
            "images": [],
            "audios": [],
            "total_files": 0,
            "scan_time": time.time(),
        }

        # 1. 扫描素材目录
        if self.config.materials_dir and os.path.isdir(self.config.materials_dir):
            files = self._scan_directory(self.config.materials_dir)
            result["materials"] = files
            result["total_files"] = len(files)

            for f in files:
                ext = os.path.splitext(f["path"])[1].lower()
                if ext in VIDEO_EXTS:
                    result["videos"].append(f)
                elif ext in IMAGE_EXTS:
                    result["images"].append(f)
                elif ext in AUDIO_EXTS:
                    result["audios"].append(f)

        # 2. 处理单个参考视频
        if self.config.reference_video and os.path.isfile(self.config.reference_video):
            result["videos"].append({
                "path": self.config.reference_video,
                "name": os.path.basename(self.config.reference_video),
                "type": "reference",
            })
            result["total_files"] += 1

        # 3. 尝试提取视频元数据（如果有ffprobe）
        for v in result["videos"]:
            meta = self._probe_video(v["path"])
            if meta:
                v.update(meta)

        # 4. 尝试基础视觉分析
        for v in result["videos"][:3]:  # 最多分析3个视频
            analysis = self._quick_analyze(v["path"])
            if analysis:
                v["quick_analysis"] = analysis

        return result

    def _scan_directory(self, directory: str) -> List[Dict]:
        """扫描目录下所有媒体文件"""
        files = []
        for root, dirs, filenames in os.walk(directory):
            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS:
                    fpath = os.path.join(root, fname)
                    size_mb = os.path.getsize(fpath) / (1024 * 1024)
                    files.append({
                        "path": fpath,
                        "name": fname,
                        "ext": ext,
                        "size_mb": round(size_mb, 2),
                        "modified": os.path.getmtime(fpath),
                    })
        return files

    def _probe_video(self, path: str) -> Dict:
        """用ffprobe提取视频元数据"""
        try:
            import subprocess
            from pipeline.stages import resolve_ffprobe
            ffprobe = resolve_ffprobe(self.config)
            cmd = [
                ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                path
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
            if r.returncode == 0:
                import json
                info = json.loads(r.stdout)
                fmt = info.get("format", {})
                duration = float(fmt.get("duration", 0))
                # 找视频流
                for s in info.get("streams", []):
                    if s.get("codec_type") == "video":
                        rfr = s.get("r_frame_rate", "0/1")
                        try:
                            num, den = rfr.split("/")
                            fps = float(num) / float(den) if float(den) != 0 else 0.0
                        except (ValueError, ZeroDivisionError):
                            fps = 0.0
                        return {
                            "duration_sec": round(duration, 2),
                            "width": s.get("width", 0),
                            "height": s.get("height", 0),
                            "fps": fps,
                            "codec": s.get("codec_name", ""),
                        }
        except Exception:
            pass
        return {}

    def _quick_analyze(self, path: str) -> Dict:
        """快速视觉分析（采样几帧）"""
        try:
            from analysis.visual_content_analyzer import VisualContentAnalyzer
            analyzer = VisualContentAnalyzer()
            return analyzer.analyze(path, num_frames=5)
        except Exception:
            pass
        return {}
