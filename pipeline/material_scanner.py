"""
素材扫描器 - MaterialScanner
============================

扫描指定目录下的所有媒体素材(视频/音频/图片)，
通过 ffprobe 提取结构化元数据，供管线各阶段消费。

核心能力:
- 递归扫描目录, 识别视频/音频/图片
- ffprobe 提取: 时长/分辨率/编码/帧率/音频流
- 按质量/时长/分辨率排序和过滤
- 输出结构化 JSON 供 plan/execute 阶段使用

Author: AE-Knowledge-Vault Team
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging
logger = logging.getLogger(__name__)

# 支持的媒体文件扩展名
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts", ".flv"}
AUDIO_EXTS = {".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a", ".wma"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp", ".gif"}


@dataclass
class MediaInfo:
    """单个媒体文件的结构化元数据"""
    path: str
    filename: str
    media_type: str  # "video" | "audio" | "image"
    size_bytes: int = 0
    size_mb: float = 0.0
    # 视频/音频通用
    duration: float = 0.0
    codec: str = ""
    # 视频专有
    width: int = 0
    height: int = 0
    fps: float = 0.0
    has_audio: bool = False
    video_codec: str = ""
    audio_codec: str = ""
    # 质量评分 (0-1)
    quality_score: float = 0.0


@dataclass
class ScanResult:
    """扫描结果"""
    directory: str
    total_files: int = 0
    videos: List[MediaInfo] = field(default_factory=list)
    audios: List[MediaInfo] = field(default_factory=list)
    images: List[MediaInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    scan_time_sec: float = 0.0

    @property
    def video_paths(self) -> List[str]:
        return [v.path for v in self.videos]

    @property
    def total_video_duration(self) -> float:
        return sum(v.duration for v in self.videos)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "directory": self.directory,
            "total_files": self.total_files,
            "video_count": len(self.videos),
            "audio_count": len(self.audios),
            "image_count": len(self.images),
            "total_video_duration": round(self.total_video_duration, 1),
            "videos": [asdict(v) for v in self.videos[:20]],  # 限制输出量
            "audios": [asdict(a) for a in self.audios[:10]],
            "errors": self.errors[:10],
            "scan_time_sec": round(self.scan_time_sec, 2),
        }


class MaterialScanner:
    """素材扫描器 - 递归扫描目录, 提取媒体元数据, 输出结构化结果。

    Usage:
        scanner = MaterialScanner()
        result = scanner.scan("data/materials")
        for video in result.videos:
            print(f"{video.filename}: {video.duration:.1f}s {video.width}x{video.height}")
    """

    def __init__(
        self,
        ffprobe_bin: str = "",
        min_video_duration: float = 1.0,
        min_file_size_kb: float = 10.0,
        max_files: int = 100,
    ):
        """
        Args:
            ffprobe_bin: ffprobe 路径, 空则自动解析
            min_video_duration: 最短视频时长(秒), 低于此值被过滤
            min_file_size_kb: 最小文件大小(KB), 低于此值被过滤
            max_files: 最大扫描文件数
        """
        self.ffprobe_bin = ffprobe_bin or self._resolve_ffprobe()
        self.min_video_duration = min_video_duration
        self.min_file_size_kb = min_file_size_kb
        self.max_files = max_files

    @staticmethod
    def _resolve_ffprobe() -> str:
        """解析 ffprobe 路径（env 覆盖 AEK_FFPROBE 优先）"""
        try:
            from core.paths import ffprobe_bin as _env_ffprobe
        except ImportError:
            _env_ffprobe = lambda: ""
        candidates = [
            _env_ffprobe(),
            r"C:\ffmpeg\bin\ffprobe.exe",
            r"C:\ffmpeg-tmp\bin\ffprobe.exe",
            "/usr/bin/ffprobe",
            "/opt/homebrew/bin/ffprobe",
        ]
        for c in candidates:
            if c and os.path.isfile(c):
                return c
        import shutil
        return shutil.which("ffprobe") or "ffprobe"

    def scan(self, directory: str, recursive: bool = True) -> ScanResult:
        """扫描目录, 返回结构化结果。

        Args:
            directory: 目标目录
            recursive: 是否递归子目录

        Returns:
            ScanResult 包含所有发现的媒体文件及其元数据
        """
        import time
        t0 = time.time()

        dir_path = Path(directory)
        result = ScanResult(directory=str(dir_path))

        if not dir_path.exists():
            result.errors.append(f"directory not found: {directory}")
            return result

        # 收集所有文件
        pattern = "**/*" if recursive else "*"
        files_scanned = 0
        for f in sorted(dir_path.glob(pattern)):
            if not f.is_file():
                continue
            if files_scanned >= self.max_files:
                break

            ext = f.suffix.lower()
            size_bytes = f.stat().st_size
            size_kb = size_bytes / 1024

            # 过滤小文件
            if size_kb < self.min_file_size_kb:
                continue

            files_scanned += 1

            if ext in VIDEO_EXTS:
                info = self._probe_video(f)
                if info and info.duration >= self.min_video_duration:
                    result.videos.append(info)
                elif info:
                    result.errors.append(
                        f"filtered (too short): {f.name} ({info.duration:.1f}s)"
                    )
            elif ext in AUDIO_EXTS:
                info = self._probe_audio(f)
                if info:
                    result.audios.append(info)
            elif ext in IMAGE_EXTS:
                info = MediaInfo(
                    path=str(f),
                    filename=f.name,
                    media_type="image",
                    size_bytes=size_bytes,
                    size_mb=round(size_bytes / (1024 * 1024), 2),
                )
                result.images.append(info)

        result.total_files = files_scanned

        # 按质量评分排序 (高质量优先)
        result.videos.sort(key=lambda v: v.quality_score, reverse=True)
        result.audios.sort(key=lambda a: a.duration, reverse=True)

        result.scan_time_sec = time.time() - t0
        logger.info(
            f"MaterialScanner: {result.total_files} files, "
            f"{len(result.videos)} videos, {len(result.audios)} audios, "
            f"{len(result.images)} images ({result.scan_time_sec:.1f}s)"
        )
        return result

    def _probe_video(self, filepath: Path) -> Optional[MediaInfo]:
        """用 ffprobe 提取视频元数据"""
        try:
            cmd = [
                self.ffprobe_bin, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name,r_frame_rate,duration",
                "-show_entries", "format=duration,size",
                "-of", "json", str(filepath)
            ]
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=15
            )
            if r.returncode != 0:
                return None

            data = json.loads(r.stdout)
            stream = (data.get("streams") or [{}])[0]
            fmt = data.get("format", {})

            # 解析帧率
            fps_str = stream.get("r_frame_rate", "30/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / max(float(den), 1)
            except (ValueError, ZeroDivisionError):
                fps = 30.0

            duration = float(fmt.get("duration", stream.get("duration", 0)) or 0)
            width = int(stream.get("width", 0) or 0)
            height = int(stream.get("height", 0) or 0)
            size_bytes = int(fmt.get("size", filepath.stat().st_size) or 0)

            # 检测音频流
            has_audio = self._has_audio_stream(str(filepath))

            info = MediaInfo(
                path=str(filepath),
                filename=filepath.name,
                media_type="video",
                size_bytes=size_bytes,
                size_mb=round(size_bytes / (1024 * 1024), 2),
                duration=duration,
                codec=stream.get("codec_name", ""),
                width=width,
                height=height,
                fps=round(fps, 2),
                has_audio=has_audio,
                video_codec=stream.get("codec_name", ""),
            )

            # 计算质量评分
            info.quality_score = self._compute_quality_score(info)
            return info

        except Exception as e:
            logger.debug(f"ffprobe failed for {filepath.name}: {e}")
            return None

    def _probe_audio(self, filepath: Path) -> Optional[MediaInfo]:
        """用 ffprobe 提取音频元数据"""
        try:
            cmd = [
                self.ffprobe_bin, "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels",
                "-show_entries", "format=duration,size",
                "-of", "json", str(filepath)
            ]
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=10
            )
            if r.returncode != 0:
                return None

            data = json.loads(r.stdout)
            stream = (data.get("streams") or [{}])[0]
            fmt = data.get("format", {})

            duration = float(fmt.get("duration", 0) or 0)
            size_bytes = int(fmt.get("size", filepath.stat().st_size) or 0)

            return MediaInfo(
                path=str(filepath),
                filename=filepath.name,
                media_type="audio",
                size_bytes=size_bytes,
                size_mb=round(size_bytes / (1024 * 1024), 2),
                duration=duration,
                codec=stream.get("codec_name", ""),
                audio_codec=stream.get("codec_name", ""),
            )
        except Exception:
            return None

    def _has_audio_stream(self, filepath: str) -> bool:
        """检测视频是否含音频流"""
        try:
            cmd = [
                self.ffprobe_bin, "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0", filepath
            ]
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=10
            )
            return "audio" in (r.stdout or "")
        except Exception:
            return False

    @staticmethod
    def _compute_quality_score(info: MediaInfo) -> float:
        """计算视频质量评分 (0-1)

        评分维度:
          - 分辨率: 1080p=1.0, 720p=0.7, 480p=0.4
          - 时长: 5-60s=1.0, 2-5s=0.6, >60s=0.8
          - 编码: h264/h265=1.0, 其他=0.5
          - 有音频: +0.1
        """
        score = 0.0

        # 分辨率评分
        pixels = info.width * info.height
        if pixels >= 1920 * 1080:
            score += 0.4
        elif pixels >= 1280 * 720:
            score += 0.3
        elif pixels >= 640 * 480:
            score += 0.2
        else:
            score += 0.1

        # 时长评分
        if 5.0 <= info.duration <= 60.0:
            score += 0.3
        elif 2.0 <= info.duration < 5.0:
            score += 0.2
        elif info.duration > 60.0:
            score += 0.25
        else:
            score += 0.1

        # 编码评分
        if info.codec in ("h264", "hevc", "h265", "vp9", "av1"):
            score += 0.2
        else:
            score += 0.1

        # 音频加分
        if info.has_audio:
            score += 0.1

        return min(1.0, round(score, 3))

    def get_best_videos(self, result: ScanResult, count: int = 5) -> List[MediaInfo]:
        """获取质量最好的 N 个视频"""
        return result.videos[:count]

    def get_plan_materials(self, result: ScanResult) -> Dict[str, Any]:
        """生成供 plan 阶段消费的素材摘要"""
        videos = result.videos
        return {
            "available_videos": len(videos),
            "total_duration": round(result.total_video_duration, 1),
            "best_resolution": f"{videos[0].width}x{videos[0].height}" if videos else "",
            "avg_duration": round(
                sum(v.duration for v in videos) / max(len(videos), 1), 1
            ),
            "has_audio_videos": sum(1 for v in videos if v.has_audio),
            "recommended_segments": min(len(videos), 6),
            "top_videos": [
                {
                    "path": v.path,
                    "duration": round(v.duration, 1),
                    "resolution": f"{v.width}x{v.height}",
                    "quality": v.quality_score,
                }
                for v in videos[:5]
            ],
        }
