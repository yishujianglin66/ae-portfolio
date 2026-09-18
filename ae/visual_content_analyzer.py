"""
Visual Content Analyzer — 视频素材内容识别引擎
=============================================
对视频素材进行帧采样分析，生成素材标签索引。

核心能力:
- 颜色直方图分析（场景色调识别）
- 边缘密度检测（场景复杂度）
- 运动向量分析（运动强度）
- 人脸检测（角色存在性）
- 素材标签生成与索引

依赖:
    pip install opencv-python numpy

用法:
    analyzer = VisualContentAnalyzer()
    tags = analyzer.analyze_video("levi_amv.mp4")
    # tags = {"source": "attack_on_titan", "scene_type": "battle", ...}
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================

class SceneType(str, Enum):
    """场景类型"""
    BATTLE = "battle"           # 战斗场景
    CLOSEUP = "closeup"         # 特写镜头
    LANDSCAPE = "landscape"     # 风景/全景
    INDOOR = "indoor"           # 室内场景
    ACTION = "action"           # 动作场景
    DIALOGUE = "dialogue"       # 对话场景
    UNKNOWN = "unknown"


class MotionIntensity(str, Enum):
    """运动强度"""
    HIGH = "high"       # 高运动（快速动作）
    MEDIUM = "medium"   # 中等运动
    LOW = "low"         # 低运动（静态场景）


@dataclass
class FrameAnalysis:
    """单帧分析结果"""
    timestamp: float                    # 时间戳（秒）
    color_histogram: list[float]        # 颜色直方图（简化为 8 bin）
    dominant_color: tuple[int, int, int]  # 主色调 (B, G, R)
    edge_density: float                 # 边缘密度 (0-1)
    brightness: float                   # 亮度 (0-255)
    motion_magnitude: float             # 运动幅度
    has_face: bool                      # 是否检测到人脸
    face_count: int                     # 人脸数量
    features: dict[str, float]          # 其他特征


@dataclass
class MaterialTag:
    """素材标签"""
    video_path: str                     # 视频路径
    duration: float                     # 时长（秒）
    fps: float                          # 帧率
    resolution: tuple[int, int]         # 分辨率 (width, height)
    
    # 内容标签
    scene_type: str                     # 场景类型
    motion_intensity: str               # 运动强度
    has_character: bool                 # 是否有角色
    color_tone: str                     # 色调（warm/cool/neutral）
    
    # 统计特征
    avg_brightness: float               # 平均亮度
    avg_edge_density: float             # 平均边缘密度
    avg_motion: float                   # 平均运动幅度
    dominant_colors: list[tuple[int, int, int]]  # 主色调列表
    
    # 时间线特征
    scene_changes: list[float]          # 场景切换时间点
    high_motion_regions: list[dict]     # 高运动区域
    
    # 元数据
    confidence: float                   # 置信度 (0-1)
    analysis_time: float                # 分析耗时（秒）


# ================================================================
#  素材内容分析引擎
# ================================================================

class VisualContentAnalyzer:
    """视频素材内容分析器"""

    def __init__(
        self,
        sample_fps: float = 1.0,        # 采样帧率（每秒取几帧）
        max_samples: int = 300,          # 最大采样数
        face_detect_confidence: float = 0.5,
    ):
        self.sample_fps = sample_fps
        self.max_samples = max_samples
        self.face_detect_confidence = face_detect_confidence
        
        # 延迟加载的模型
        self._face_cascade = None
        self._cv2 = None

    def _ensure_cv2(self):
        """确保 OpenCV 已加载"""
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
            except ImportError:
                raise ImportError("需要安装 opencv-python: pip install opencv-python")

    def _get_face_detector(self):
        """获取人脸检测器"""
        if self._face_cascade is None:
            self._ensure_cv2()
            try:
                cascade_path = self._cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._face_cascade = self._cv2.CascadeClassifier(cascade_path)
                if self._face_cascade.empty():
                    self._face_cascade = None
            except Exception:
                # 人脸检测器不可用，跳过
                self._face_cascade = None
        return self._face_cascade

    def analyze_video(
        self, 
        video_path: str,
        output_json: str | None = None,
    ) -> MaterialTag:
        """
        分析视频素材，生成内容标签。

        Args:
            video_path: 视频文件路径
            output_json: 可选，输出 JSON 路径

        Returns:
            MaterialTag 素材标签
        """
        import time

        import numpy as np
        
        self._ensure_cv2()
        start_time = time.time()

        # 打开视频
        cap = self._cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开视频: {video_path}")

        # 获取视频信息
        fps = cap.get(self._cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(self._cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(self._cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        # 计算采样间隔
        sample_interval = max(1, int(fps / self.sample_fps))
        max_samples = min(self.max_samples, total_frames // sample_interval)

        # 采样分析
        frame_analyses: list[FrameAnalysis] = []
        prev_frame = None
        sample_count = 0

        for frame_idx in range(0, total_frames, sample_interval):
            if sample_count >= max_samples:
                break
            
            cap.set(self._cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            timestamp = frame_idx / fps
            analysis = self._analyze_frame(frame, prev_frame, timestamp)
            frame_analyses.append(analysis)
            prev_frame = frame
            sample_count += 1

        cap.release()

        # 汇总统计
        tag = self._aggregate_analysis(
            frame_analyses, video_path, duration, fps, (width, height)
        )
        tag.analysis_time = time.time() - start_time

        # 输出 JSON
        if output_json:
            self._export_tag_json(tag, output_json)

        return tag

    def _analyze_frame(
        self, 
        frame, 
        prev_frame,
        timestamp: float,
    ) -> FrameAnalysis:
        """分析单帧"""
        import numpy as np
        
        cv2 = self._cv2
        
        # 颜色直方图
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        hist = hist.flatten()
        hist = (hist / (hist.sum() + 1e-6)).tolist()

        # 主色调
        dominant_color = self._get_dominant_color(frame)

        # 边缘密度
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = edges.sum() / (edges.shape[0] * edges.shape[1] * 255)

        # 亮度
        brightness = gray.mean()

        # 运动分析
        motion_magnitude = 0.0
        if prev_frame is not None:
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
            )
            motion_magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2).mean()

        # 人脸检测
        face_detector = self._get_face_detector()
        if face_detector is not None:
            faces = face_detector.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            has_face = len(faces) > 0
            face_count = len(faces)
        else:
            has_face = False
            face_count = 0

        return FrameAnalysis(
            timestamp=timestamp,
            color_histogram=hist,
            dominant_color=dominant_color,
            edge_density=edge_density,
            brightness=brightness,
            motion_magnitude=motion_magnitude,
            has_face=has_face,
            face_count=face_count,
            features={
                "saturation": hsv[..., 1].mean(),
                "value": hsv[..., 2].mean(),
            }
        )

    def _get_dominant_color(self, frame) -> tuple[int, int, int]:
        """获取主色调"""
        import numpy as np
        
        cv2 = self._cv2
        # 简化：使用 K-means 聚类
        pixels = frame.reshape(-1, 3).astype(np.float32)
        
        # 快速采样
        if len(pixels) > 1000:
            indices = np.random.choice(len(pixels), 1000, replace=False)
            pixels = pixels[indices]
        
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        flags = cv2.KMEANS_PP_CENTERS
        compactness, labels, centers = cv2.kmeans(
            pixels, 3, None, criteria, 5, flags
        )
        
        # 返回最大聚类的颜色
        counts = np.bincount(labels.flatten())
        dominant_idx = counts.argmax()
        b, g, r = centers[dominant_idx].astype(int)
        return (int(b), int(g), int(r))

    def _aggregate_analysis(
        self,
        analyses: list[FrameAnalysis],
        video_path: str,
        duration: float,
        fps: float,
        resolution: tuple[int, int],
    ) -> MaterialTag:
        """汇总分析结果"""
        import numpy as np
        
        if not analyses:
            return MaterialTag(
                video_path=video_path,
                duration=duration,
                fps=fps,
                resolution=resolution,
                scene_type=SceneType.UNKNOWN.value,
                motion_intensity=MotionIntensity.LOW.value,
                has_character=False,
                color_tone="neutral",
                avg_brightness=0,
                avg_edge_density=0,
                avg_motion=0,
                dominant_colors=[],
                scene_changes=[],
                high_motion_regions=[],
                confidence=0,
                analysis_time=0,
            )

        # 统计特征
        avg_brightness = np.mean([a.brightness for a in analyses])
        avg_edge_density = np.mean([a.edge_density for a in analyses])
        avg_motion = np.mean([a.motion_magnitude for a in analyses])
        
        # 人脸统计
        face_ratio = sum(1 for a in analyses if a.has_face) / len(analyses)
        has_character = face_ratio > 0.3

        # 运动强度分类
        if avg_motion > 10:
            motion_intensity = MotionIntensity.HIGH.value
        elif avg_motion > 3:
            motion_intensity = MotionIntensity.MEDIUM.value
        else:
            motion_intensity = MotionIntensity.LOW.value

        # 场景类型推断
        scene_type = self._infer_scene_type(analyses, avg_edge_density, avg_motion, has_character)

        # 色调分类
        color_tone = self._classify_color_tone(analyses)

        # 主色调列表
        dominant_colors = [a.dominant_color for a in analyses[::max(1, len(analyses)//5)]]

        # 场景切换检测
        scene_changes = self._detect_scene_changes(analyses)

        # 高运动区域
        high_motion_regions = self._find_high_motion_regions(analyses)

        # 置信度
        confidence = min(1.0, len(analyses) / 50)

        return MaterialTag(
            video_path=video_path,
            duration=duration,
            fps=fps,
            resolution=resolution,
            scene_type=scene_type,
            motion_intensity=motion_intensity,
            has_character=has_character,
            color_tone=color_tone,
            avg_brightness=float(avg_brightness),
            avg_edge_density=float(avg_edge_density),
            avg_motion=float(avg_motion),
            dominant_colors=dominant_colors,
            scene_changes=scene_changes,
            high_motion_regions=high_motion_regions,
            confidence=confidence,
            analysis_time=0,
        )

    def _infer_scene_type(
        self,
        analyses: list[FrameAnalysis],
        avg_edge_density: float,
        avg_motion: float,
        has_character: bool,
    ) -> str:
        """推断场景类型"""
        # 基于特征的简单规则
        if avg_motion > 15 and avg_edge_density > 0.1:
            return SceneType.BATTLE.value
        elif avg_motion > 10:
            return SceneType.ACTION.value
        elif has_character and avg_edge_density < 0.05:
            return SceneType.CLOSEUP.value
        elif avg_edge_density < 0.03 and avg_motion < 2:
            return SceneType.LANDSCAPE.value
        elif has_character:
            return SceneType.DIALOGUE.value
        else:
            return SceneType.UNKNOWN.value

    def _classify_color_tone(self, analyses: list[FrameAnalysis]) -> str:
        """分类色调"""
        import numpy as np
        
        # 分析 HSV 中的色调分布
        warm_count = 0
        cool_count = 0
        
        for a in analyses:
            # 简化：基于主色调的 R-B 差值
            b, g, r = a.dominant_color
            if r > b + 20:
                warm_count += 1
            elif b > r + 20:
                cool_count += 1
        
        total = len(analyses)
        if warm_count > total * 0.6:
            return "warm"
        elif cool_count > total * 0.6:
            return "cool"
        else:
            return "neutral"

    def _detect_scene_changes(self, analyses: list[FrameAnalysis]) -> list[float]:
        """检测场景切换点"""
        import numpy as np
        
        if len(analyses) < 2:
            return []
        
        changes = []
        prev_hist = np.array(analyses[0].color_histogram)
        
        for i, a in enumerate(analyses[1:], 1):
            curr_hist = np.array(a.color_histogram)
            # 直方图差异
            diff = np.sum(np.abs(curr_hist - prev_hist))
            if diff > 0.5:  # 阈值
                changes.append(a.timestamp)
            prev_hist = curr_hist
        
        return changes

    def _find_high_motion_regions(
        self, 
        analyses: list[FrameAnalysis],
        threshold: float = 10.0,
    ) -> list[dict]:
        """查找高运动区域"""
        regions = []
        start = None
        
        for a in analyses:
            if a.motion_magnitude > threshold:
                if start is None:
                    start = a.timestamp
            else:
                if start is not None:
                    regions.append({
                        "start": start,
                        "end": a.timestamp,
                        "duration": a.timestamp - start,
                    })
                    start = None
        
        if start is not None:
            regions.append({
                "start": start,
                "end": analyses[-1].timestamp,
                "duration": analyses[-1].timestamp - start,
            })
        
        return regions

    def _export_tag_json(self, tag: MaterialTag, output_path: str) -> None:
        """导出标签为 JSON"""
        data = asdict(tag)
        Path(output_path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def build_material_index(
        self,
        video_paths: list[str],
        output_json: str,
    ) -> dict[str, MaterialTag]:
        """
        批量分析视频素材，构建素材索引。

        Args:
            video_paths: 视频路径列表
            output_json: 输出索引 JSON 路径

        Returns:
            {video_path: MaterialTag} 索引字典
        """
        index = {}
        for path in video_paths:
            try:
                tag = self.analyze_video(path)
                index[path] = tag
                print(f"[OK] {Path(path).name}: {tag.scene_type}, {tag.motion_intensity}")
            except Exception as e:
                print(f"[ERROR] {Path(path).name}: {e}")
        
        # 导出索引
        data = {path: asdict(tag) for path, tag in index.items()}
        Path(output_json).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\n[OK] 素材索引已保存: {output_json}")
        
        return index


# ================================================================
#  便捷函数
# ================================================================

def analyze_material(video_path: str) -> MaterialTag:
    """快速分析单个素材"""
    analyzer = VisualContentAnalyzer()
    return analyzer.analyze_video(video_path)


def build_material_index(video_paths: list[str], output_json: str) -> dict[str, MaterialTag]:
    """批量构建素材索引"""
    analyzer = VisualContentAnalyzer()
    return analyzer.build_material_index(video_paths, output_json)


__all__ = [
    "VisualContentAnalyzer",
    "MaterialTag",
    "FrameAnalysis",
    "SceneType",
    "MotionIntensity",
    "analyze_material",
    "build_material_index",
]


# ================================================================
#  自测入口
# ================================================================

if __name__ == "__main__":
    import sys
    
    # 测试素材路径
    test_videos = [
        r"data\real_amv_test\BV1A64y1u78E.mp4",  # 利威尔 AMV
    ]
    
    # 过滤存在的文件
    existing = [v for v in test_videos if Path(v).exists()]
    
    if not existing:
        print("[WARN] 没有可测试的视频文件")
        sys.exit(0)
    
    print("=" * 60)
    print("VisualContentAnalyzer 自测")
    print("=" * 60)
    
    analyzer = VisualContentAnalyzer(sample_fps=1.0, max_samples=100)
    
    for video in existing:
        print(f"\n分析: {video}")
        try:
            tag = analyzer.analyze_video(video)
            print(f"  场景类型: {tag.scene_type}")
            print(f"  运动强度: {tag.motion_intensity}")
            print(f"  有角色: {tag.has_character}")
            print(f"  色调: {tag.color_tone}")
            print(f"  平均亮度: {tag.avg_brightness:.1f}")
            print(f"  平均运动: {tag.avg_motion:.2f}")
            print(f"  场景切换: {len(tag.scene_changes)} 次")
            print(f"  分析耗时: {tag.analysis_time:.2f}s")
        except Exception as e:
            print(f"  [ERROR] {e}")
