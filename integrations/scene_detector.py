"""
integrations/scene_detector.py - 场景检测器 v1.0
=================================================

检测视频场景边界并分类场景类型，为智能调色提供分段依据。

后端优先级:
1. PySceneDetect（ContentDetector + ThresholdDetector）
2. FFmpeg scene filter（回退）
3. 固定间隔分割（最终回退）

用法:
    from integrations.scene_detector import SceneDetector

    detector = SceneDetector()
    scenes = detector.detect("video.mp4")
    # [{"start": 0.0, "end": 12.5, "type": "action", "confidence": 0.85}, ...]
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 场景类型常量
SCENE_TYPES = ["action", "dialogue", "landscape", "closeup", "transition", "montage"]


@dataclass
class SceneSegment:
    """单个场景片段"""
    index: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    start_frame: int = 0
    end_frame: int = 0
    frame_count: int = 0
    scene_type: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "frame_count": self.frame_count,
            "scene_type": self.scene_type,
            "confidence": self.confidence,
        }


@dataclass
class SceneDetectResult:
    """场景检测结果"""
    success: bool = False
    error: str = ""
    video_path: str = ""
    detector_type: str = ""
    scene_count: int = 0
    total_duration: float = 0.0
    segments: List[SceneSegment] = field(default_factory=list)
    fps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "video_path": self.video_path,
            "detector_type": self.detector_type,
            "scene_count": self.scene_count,
            "total_duration": self.total_duration,
            "segments": [s.to_dict() for s in self.segments],
            "fps": self.fps,
        }


def detect_scenes(video_path: str, threshold: float = 27.0, min_scene_len: int = 15) -> SceneDetectResult:
    """便捷函数：检测视频场景并返回结构化结果"""
    detector = SceneDetector(threshold=threshold, min_scene_len=min_scene_len)
    try:
        raw = detector.detect(video_path)
        segments = [
            SceneSegment(
                index=s.get("index", i),
                start_time=s.get("start", 0.0),
                end_time=s.get("end", 0.0),
                duration=s.get("end", 0.0) - s.get("start", 0.0),
                scene_type=s.get("type", ""),
                confidence=s.get("confidence", 0.0),
            )
            for i, s in enumerate(raw)
        ]
        return SceneDetectResult(
            success=True,
            video_path=video_path,
            detector_type="content",
            scene_count=len(segments),
            segments=segments,
        )
    except Exception as e:
        return SceneDetectResult(success=False, error=str(e), video_path=video_path)


class SceneDetector:
    """视频场景检测器"""

    def __init__(self, threshold: float = 27.0, min_scene_len: int = 15):
        """
        Args:
            threshold: 场景切换检测阈值（ContentDetector）
            min_scene_len: 最小场景长度（帧数）
        """
        self.threshold = threshold
        self.min_scene_len = min_scene_len

    def detect(self, video_path: str) -> List[Dict[str, Any]]:
        """检测视频场景

        Args:
            video_path: 视频文件路径

        Returns:
            场景列表，每项包含:
            - start: 起始时间（秒）
            - end: 结束时间（秒）
            - type: 场景类型 (action/dialogue/landscape/closeup/transition/montage)
            - confidence: 检测置信度 (0-1)
            - index: 场景序号
        """
        if not os.path.isfile(video_path):
            logger.warning(f"SceneDetector: file not found: {video_path}")
            return []

        # 尝试 PySceneDetect
        scenes = self._detect_pyscenedetect(video_path)
        if scenes:
            return scenes

        # 回退到 FFmpeg
        scenes = self._detect_ffmpeg(video_path)
        if scenes:
            return scenes

        # 最终回退：固定间隔分割
        return self._detect_fixed_split(video_path)

    def _detect_pyscenedetect(self, video_path: str) -> List[Dict[str, Any]]:
        """使用 PySceneDetect 检测"""
        try:
            from scenedetect import open_video, SceneManager
            from scenedetect.detectors import ContentDetector
        except ImportError:
            logger.debug("SceneDetector: PySceneDetect not available")
            return []

        try:
            video = open_video(video_path)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector(threshold=self.threshold,
                                                       min_scene_len=self.min_scene_len))
            scene_manager.detect_scenes(video)
            scene_list = scene_manager.get_scene_list()

            if not scene_list:
                return []

            fps = video.frame_rate or 24.0
            scenes = []
            for i, (start, end) in enumerate(scene_list):
                start_sec = start.get_seconds()
                end_sec = end.get_seconds()
                duration = end_sec - start_sec

                # 基于时长和位置推断场景类型
                scene_type = self._classify_scene_type(duration, i, len(scene_list))

                scenes.append({
                    "start": round(start_sec, 2),
                    "end": round(end_sec, 2),
                    "duration": round(duration, 2),
                    "type": scene_type,
                    "confidence": 0.8,
                    "index": i,
                    "start_frame": int(start_sec * fps),
                    "end_frame": int(end_sec * fps),
                })

            logger.info(f"SceneDetector [PySceneDetect]: {len(scenes)} scenes detected")
            return scenes

        except Exception as e:
            logger.warning(f"SceneDetector [PySceneDetect] failed: {e}")
            return []

    def _detect_ffmpeg(self, video_path: str) -> List[Dict[str, Any]]:
        """使用 FFmpeg scene filter 检测"""
        import subprocess
        import shutil

        ffmpeg = shutil.which("ffmpeg") or r"C:\ffmpeg\bin\ffmpeg.exe"
        if not os.path.isfile(ffmpeg):
            return []

        try:
            threshold_norm = self.threshold / 100.0  # 归一化到 0-1
            cmd = [
                ffmpeg, "-i", video_path,
                "-vf", f"select='gt(scene,{threshold_norm})',showinfo",
                "-f", "null", "-"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            # 解析 showinfo 输出提取时间戳
            timestamps = [0.0]  # 第一场景从 0 开始
            for line in result.stderr.split("\n"):
                if "pts_time:" in line:
                    try:
                        pts = float(line.split("pts_time:")[1].split()[0])
                        timestamps.append(pts)
                    except (ValueError, IndexError):
                        pass

            if len(timestamps) < 2:
                return []

            # 获取视频总时长
            total_dur = self._get_duration(video_path)
            if total_dur > 0:
                timestamps.append(total_dur)

            scenes = []
            for i in range(len(timestamps) - 1):
                start = timestamps[i]
                end = timestamps[i + 1]
                duration = end - start
                scene_type = self._classify_scene_type(duration, i, len(timestamps) - 1)
                scenes.append({
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "duration": round(duration, 2),
                    "type": scene_type,
                    "confidence": 0.6,
                    "index": i,
                })

            logger.info(f"SceneDetector [FFmpeg]: {len(scenes)} scenes detected")
            return scenes

        except Exception as e:
            logger.warning(f"SceneDetector [FFmpeg] failed: {e}")
            return []

    def _detect_fixed_split(self, video_path: str) -> List[Dict[str, Any]]:
        """固定间隔分割（最终回退）"""
        total_dur = self._get_duration(video_path)
        if total_dur <= 0:
            return []

        # 每 10 秒一个场景
        split_interval = 10.0
        scenes = []
        t = 0.0
        i = 0
        while t < total_dur:
            end = min(t + split_interval, total_dur)
            scenes.append({
                "start": round(t, 2),
                "end": round(end, 2),
                "duration": round(end - t, 2),
                "type": self._classify_scene_type(end - t, i, max(1, int(total_dur / split_interval))),
                "confidence": 0.3,
                "index": i,
            })
            t = end
            i += 1

        logger.info(f"SceneDetector [fixed]: {len(scenes)} segments (fallback)")
        return scenes

    def _classify_scene_type(self, duration: float, index: int, total: int) -> str:
        """基于时长和位置推断场景类型"""
        # 短镜头 → action 或 transition
        if duration < 2.0:
            return "transition" if index == 0 or index == total - 1 else "action"
        # 中等镜头 → dialogue 或 closeup
        if duration < 6.0:
            return "dialogue" if index % 2 == 0 else "closeup"
        # 长镜头 → landscape 或 montage
        return "landscape" if duration > 15.0 else "montage"

    @staticmethod
    def _get_duration(video_path: str) -> float:
        """获取视频时长（秒）"""
        import subprocess
        import shutil

        ffprobe = shutil.which("ffprobe") or r"C:\ffmpeg\bin\ffprobe.exe"
        if not os.path.isfile(ffprobe):
            return 0.0

        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0
