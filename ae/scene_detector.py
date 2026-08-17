"""
Scene Detector — 智能场景分割引擎
==================================
基于 PySceneDetect (https://github.com/Breakthrough/PySceneDetect) 开源项目，
提供内容感知的场景检测与切割能力。

核心能力:
- 内容感知检测 (Content-Aware Detection) — 色彩直方图变化
- 自适应阈值检测 — 暗场景/快节奏场景自动适配
- 时间码输出 — 直接对接 PR/AE 时间线 (SMPTE/帧号)
- 批量视频分析
- 场景元数据提取（平均亮度、色彩分布、运动量）

依赖:
    pip install scenedetect opencv-python

用法:
    detector = SceneDetector()
    cuts = detector.detect("input.mp4")
    # cuts = [(0.0, 5.2, {...}), (5.2, 12.8, {...}), ...]
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))

if TYPE_CHECKING:
    # 仅用于类型注解（运行时不导入，避免与 analysis.scene_detector 循环导入）
    from analysis.scene_detector import SceneDetectResult


# ================================================================
#  数据结构
# ================================================================
class DetectionMethod(Enum):
    """检测方法"""
    CONTENT = "content"        # 内容感知（HSV直方图差异）
    THRESHOLD = "threshold"    # 自适应阈值（亮度突变）
    ADAPTIVE = "adaptive"      # 自适应检测（综合多种指标）
    HASH = "hash"              # 感知哈希（快速粗检测）


@dataclass
class SceneCut:
    """场景切割点"""
    index: int                     # 场景序号
    start_time: float              # 起始时间（秒）
    end_time: float                # 结束时间（秒）
    duration: float                # 时长（秒）
    start_frame: int               # 起始帧
    end_frame: int                 # 结束帧
    frame_count: int               # 帧数
    thumbnail_frame: int = 0       # 缩略图帧号
    metadata: Dict[str, Any] = field(default_factory=dict)  # 场景元数据

    @property
    def start_tc(self) -> str:
        """SMPTE 时间码（起始）"""
        return self._frame_to_tc(self.start_frame)

    @property
    def end_tc(self) -> str:
        """SMPTE 时间码（结束）"""
        return self._frame_to_tc(self.end_frame)

    def _frame_to_tc(self, frame: int, fps: int = 30) -> str:
        total_seconds = frame / fps
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = int(total_seconds % 60)
        f = int((total_seconds - int(total_seconds)) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "frame_count": self.frame_count,
            "start_tc": self.start_tc,
            "end_tc": self.end_tc,
            "metadata": self.metadata,
        }


@dataclass
class SceneMetadata:
    """场景元数据"""
    avg_brightness: float = 0.0
    avg_saturation: float = 0.0
    color_histogram: Optional[List[float]] = None
    motion_level: float = 0.0
    edge_density: float = 0.0
    blur_score: float = 0.0
    dominant_colors: Optional[List[Tuple[int, int, int]]] = None
    is_dark_scene: bool = False
    is_fast_motion: bool = False
    sentiment_hint: str = "neutral"


# ================================================================
#  场景检测引擎
# ================================================================
class SceneDetector:
    """基于 PySceneDetect 的场景检测器"""

    def __init__(
        self,
        method: DetectionMethod = DetectionMethod.ADAPTIVE,
        min_scene_length: float = 0.5,     # 最小场景时长（秒）
        threshold: float = 27.0,            # 检测阈值
        fps: int = 30,
        extract_metadata: bool = True,
    ):
        self.method = method
        self.min_scene_length = min_scene_length
        self.threshold = threshold
        self.fps = fps
        self.extract_metadata = extract_metadata

    def detect(self, video_path: str) -> List[SceneCut]:
        """
        检测视频中的所有场景切割点。

        Args:
            video_path: 视频文件路径

        Returns:
            场景切割点列表
        """
        try:
            from scenedetect import detect, ContentDetector, AdaptiveDetector
            from scenedetect import split_video_ffmpeg

            # 根据方法选择检测器
            if self.method == DetectionMethod.CONTENT:
                detector = ContentDetector(threshold=self.threshold, min_scene_len=int(self.min_scene_length * self.fps))
            elif self.method == DetectionMethod.ADAPTIVE:
                detector = AdaptiveDetector(
                    adaptive_threshold=3.0,
                    min_scene_len=int(self.min_scene_length * self.fps),
                    window_width=2,
                )
            else:
                detector = ContentDetector(threshold=self.threshold, min_scene_len=int(self.min_scene_length * self.fps))

            # 执行检测
            scene_list = detect(video_path, detector)

            # 转换为 SceneCut 对象
            cuts = []
            for i, (start_tc, end_tc) in enumerate(scene_list):
                start_sec = start_tc.get_seconds()
                end_sec = end_tc.get_seconds()
                cut = SceneCut(
                    index=i,
                    start_time=round(start_sec, 3),
                    end_time=round(end_sec, 3),
                    duration=round(end_sec - start_sec, 3),
                    start_frame=int(start_tc.get_frames()),
                    end_frame=int(end_tc.get_frames()),
                    frame_count=int(end_tc.get_frames() - start_tc.get_frames()),
                    thumbnail_frame=int(start_tc.get_frames()) + int((end_tc.get_frames() - start_tc.get_frames()) * 0.3),
                )

                if self.extract_metadata:
                    cut.metadata = self._extract_scene_metadata(video_path, cut).__dict__

                cuts.append(cut)

            return cuts

        except ImportError:
            return self._fallback_detect(video_path)
        except Exception as e:
            print(f"[SceneDetector] PySceneDetect error: {e}, falling back to OpenCV")
            return self._fallback_detect(video_path)

    def _fallback_detect(self, video_path: str) -> List[SceneCut]:
        """OpenCV 回退方案：基于直方图差异的简单场景检测"""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        if actual_fps <= 0:
            actual_fps = self.fps

        prev_hist = None
        cuts = []
        frame_idx = 0
        min_frames = int(self.min_scene_length * actual_fps)

        scene_start = 0
        scene_frames = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # 计算 HSV 直方图
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            if prev_hist is not None and (frame_idx - scene_start) >= min_frames:
                # 计算直方图差异（相关性比较）
                diff = cv2.compareHist(prev_hist.reshape(50, 60), hist.reshape(50, 60), cv2.HISTCMP_BHATTACHARYYA)

                if diff > self.threshold / 100.0:  # 阈值转换
                    # 场景切换
                    cuts.append(SceneCut(
                        index=len(cuts),
                        start_time=round(scene_start / actual_fps, 3),
                        end_time=round(frame_idx / actual_fps, 3),
                        duration=round((frame_idx - scene_start) / actual_fps, 3),
                        start_frame=scene_start,
                        end_frame=frame_idx,
                        frame_count=frame_idx - scene_start,
                        thumbnail_frame=scene_start + int((frame_idx - scene_start) * 0.3),
                    ))
                    scene_start = frame_idx

            prev_hist = hist
            frame_idx += 1
            scene_frames.append(frame)

        # 最后一个场景
        if scene_start < frame_idx:
            cuts.append(SceneCut(
                index=len(cuts),
                start_time=round(scene_start / actual_fps, 3),
                end_time=round(frame_idx / actual_fps, 3),
                duration=round((frame_idx - scene_start) / actual_fps, 3),
                start_frame=scene_start,
                end_frame=frame_idx,
                frame_count=frame_idx - scene_start,
                thumbnail_frame=scene_start + int((frame_idx - scene_start) * 0.3),
            ))

        cap.release()

        # 元数据提取
        if self.extract_metadata:
            for cut in cuts:
                cut.metadata = self._extract_scene_metadata_scene_frames(scene_frames, cut).__dict__

        return cuts

    def _extract_scene_metadata(self, video_path: str, cut: SceneCut) -> SceneMetadata:
        """提取场景元数据"""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return SceneMetadata()

        actual_fps = cap.get(cv2.CAP_PROP_FPS) or self.fps
        cap.set(cv2.CAP_PROP_POS_FRAMES, cut.start_frame)

        brightnesses = []
        saturations = []
        edges = []
        laplacians = []

        sample_interval = max(1, cut.frame_count // 60)  # 最多采样60帧
        samples = 0

        for i in range(0, cut.frame_count, sample_interval):
            cap.set(cv2.CAP_PROP_POS_FRAMES, cut.start_frame + i)
            ret, frame = cap.read()
            if not ret:
                break
            samples += 1

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            brightnesses.append(np.mean(gray))
            saturations.append(np.mean(hsv[:, :, 1]))
            edges.append(np.mean(cv2.Canny(gray, 50, 150)) / 255.0)
            laplacians.append(cv2.Laplacian(gray, cv2.CV_64F).var())

        cap.release()

        if samples == 0:
            return SceneMetadata()

        avg_brightness = np.mean(brightnesses)
        avg_sat = np.mean(saturations)
        edge_density = np.mean(edges)
        blur_score = np.mean(laplacians)

        # 运动估计（相邻采样帧之间的差异）
        motion = 0.0
        if samples >= 2:
            prev_b = brightnesses[0]
            for b in brightnesses[1:]:
                motion += abs(b - prev_b) / 255.0
                prev_b = b
            motion /= (samples - 1)

        return SceneMetadata(
            avg_brightness=round(float(avg_brightness), 2),
            avg_saturation=round(float(avg_sat), 2),
            motion_level=round(float(motion), 4),
            edge_density=round(float(edge_density), 4),
            blur_score=round(float(blur_score), 2),
            is_dark_scene=avg_brightness < 30,
            is_fast_motion=motion > 0.05,
        )

    def _extract_scene_metadata_scene_frames(self, frames: list, cut: SceneCut) -> SceneMetadata:
        """从已缓存的帧列表中提取元数据"""
        import cv2
        import numpy as np

        scene_frames = frames[cut.start_frame:cut.end_frame]
        if not scene_frames:
            return SceneMetadata()

        sample_interval = max(1, len(scene_frames) // 60)
        brightnesses, saturations, edges, laplacians = [], [], [], []

        for i in range(0, len(scene_frames), sample_interval):
            frame = scene_frames[i]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            brightnesses.append(np.mean(gray))
            saturations.append(np.mean(hsv[:, :, 1]))
            edges.append(np.mean(cv2.Canny(gray, 50, 150)) / 255.0)
            laplacians.append(cv2.Laplacian(gray, cv2.CV_64F).var())

        return SceneMetadata(
            avg_brightness=round(float(np.mean(brightnesses)), 2),
            avg_saturation=round(float(np.mean(saturations)), 2),
            motion_level=0.0,
            edge_density=round(float(np.mean(edges)), 4),
            blur_score=round(float(np.mean(laplacians)), 2),
            is_dark_scene=bool(np.mean(brightnesses) < 30),
            is_fast_motion=False,
        )

    def detect_with_timestamps(self, video_path: str) -> List[Dict[str, Any]]:
        """检测并返回时间码格式结果（直接对接 PR 时间线）"""
        cuts = self.detect(video_path)
        return [
            {
                "scene_id": cut.index,
                "in_point": cut.start_tc,
                "out_point": cut.end_tc,
                "in_seconds": cut.start_time,
                "out_seconds": cut.end_time,
                "duration_seconds": cut.duration,
                "in_frame": cut.start_frame,
                "out_frame": cut.end_frame,
                "thumbnail_frame": cut.thumbnail_frame,
                "metadata": cut.metadata,
            }
            for cut in cuts
        ]

    def export_edl(self, video_path: str, output_path: str) -> str:
        """导出 EDL (Edit Decision List) 格式"""
        cuts = self.detect(video_path)
        edl_lines = [
            f'TITLE: Scene Detection EDL - {Path(video_path).name}',
            f'FCM: NON-DROP FRAME',
            ''
        ]

        for i, cut in enumerate(cuts, 1):
            edl_lines.append(f'{i:03d}  AX       V     C        {cut.start_tc} {cut.end_tc} {cut.start_tc} {cut.end_tc}')
            edl_lines.append(f'* FROM CLIP NAME:  Scene_{i:03d}')
            edl_lines.append('')

        content = '\n'.join(edl_lines)
        Path(output_path).write_text(content, encoding='utf-8')
        return output_path

    def export_timeline_json(self, video_path: str, output_path: str) -> str:
        """导出 JSON 格式时间线（对接 PR MCP）"""
        cuts = self.detect_with_timestamps(video_path)
        timeline = {
            "source": str(Path(video_path).absolute()),
            "fps": self.fps,
            "total_duration": round(sum(c["duration_seconds"] for c in cuts), 3),
            "scene_count": len(cuts),
            "scenes": cuts,
        }
        Path(output_path).write_text(json.dumps(timeline, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_path

    def get_highlight_scenes(
        self,
        video_path: str,
        top_k: int = 5,
        criteria: str = "motion",
    ) -> List[SceneCut]:
        """
        自动识别高光场景。

        Args:
            video_path: 视频路径
            top_k: 返回 Top K 个高光场景
            criteria: 高光标准 ("motion"=运动量, "brightness"=明亮度, "contrast"=对比度)

        Returns:
            高光场景列表
        """
        cuts = self.detect(video_path)

        if criteria == "motion":
            scores = [c.metadata.get("motion_level", 0) for c in cuts]
        elif criteria == "brightness":
            scores = [c.metadata.get("avg_brightness", 0) for c in cuts]
        elif criteria == "contrast":
            scores = [c.metadata.get("edge_density", 0) for c in cuts]
        else:
            scores = [c.metadata.get("motion_level", 0) for c in cuts]

        # 排序取 Top K
        ranked = sorted(zip(cuts, scores), key=lambda x: x[1], reverse=True)
        return [c for c, _ in ranked[:top_k]]

    def detect_with_result(self, video_path: str) -> "SceneDetectResult":
        """IR 适配层：将 detect() 结果包装为 SceneDetectResult 格式。

        使期望 SceneDetectResult 的消费方（如 ae_agent_pipeline 的
        _enhance_perception_with_phase2）也能复用 ae.scene_detector.SceneDetector。

        字段映射（SceneCut → SceneSegment）：
            index / start_time / end_time / duration /
            start_frame / end_frame / frame_count 直接对应；
            thumbnail_frame / metadata 不映射（SceneSegment 无此字段）。

        Args:
            video_path: 视频文件路径

        Returns:
            SceneDetectResult；若 analysis.scene_detector 不可达则抛 ImportError。
        """
        # 延迟导入避免与 analysis.scene_detector 形成模块级循环
        from analysis.scene_detector import SceneDetectResult, SceneSegment

        try:
            cuts = self.detect(video_path)
        except Exception as e:
            return SceneDetectResult(
                success=False,
                error=f"{type(e).__name__}: {e}",
                video_path=video_path,
                detector_type=self.method.value,
            )

        segments = [
            SceneSegment(
                index=cut.index,
                start_time=cut.start_time,
                end_time=cut.end_time,
                duration=cut.duration,
                start_frame=cut.start_frame,
                end_frame=cut.end_frame,
                frame_count=cut.frame_count,
            )
            for cut in cuts
        ]

        total_duration = cuts[-1].end_time if cuts else 0.0

        return SceneDetectResult(
            success=True,
            video_path=video_path,
            detector_type=self.method.value,
            scene_count=len(segments),
            total_duration=total_duration,
            segments=segments,
            fps=float(self.fps),
        )


__all__ = [
    "SceneDetector",
    "SceneCut",
    "SceneMetadata",
    "DetectionMethod",
]
