"""
scene_detector.py
Phase 2-1 感知层增强 — 基于 PySceneDetect 的镜头分割模块

用途：
    对输入视频进行镜头分割，输出结构化的 SceneSegment 列表，
    供理解层在场景描述、转场规划、节拍匹配中使用。

设计原则：
    1. 优雅降级：PySceneDetect/OpenCV 未安装时返回 success=False，
       不抛 ImportError，保证主流程可继续。
    2. 多检测器：ContentDetector(默认)/AdaptiveDetector/ThresholdDetector，
       通过 detector_type 参数切换。
    3. 结构化输出：SceneSegment dataclass，含 to_dict() 便于注入 PerceptionResult。
    4. 与 video_analyzer_enhanced.py 互补：本模块专注镜头分割，
       EnhancedVideoAnalyzer 偏向综合特征；本模块输出可直接用于转场规划。

对齐文件: ae_agent_pipeline.py perceive() / transition_map.py
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from performance.cache_manager import DiskCache, file_fingerprint
    _scene_cache = DiskCache(name="scene_detect", cache_dir=".cache/scene")
except ImportError:
    _scene_cache = None

__all__ = [
    "SceneSegment",
    "SceneDetectResult",
    "SceneDetector",
    "detect_scenes",
]

# 检测依赖可用性（不抛异常）
try:
    from scenedetect import detect, ContentDetector, SceneManager, open_video
    from scenedetect.detectors import AdaptiveDetector, ThresholdDetector
    _SCENEDETECT_AVAILABLE = True
except ImportError:  # pragma: no cover - 依赖未安装的路径
    _SCENEDETECT_AVAILABLE = False
    detect = None
    ContentDetector = None
    AdaptiveDetector = None
    ThresholdDetector = None
    SceneManager = None
    open_video = None

try:
    import cv2  # noqa: F401 - PySceneDetect 部分后端依赖 cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class SceneSegment:
    """单个镜头片段

    Attributes:
        index: 片段序号（从 0 开始）
        start_time: 起始时间（秒）
        end_time: 结束时间（秒）
        duration: 时长（秒）
        start_frame: 起始帧号
        end_frame: 结束帧号
        frame_count: 帧数
    """
    index: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    start_frame: int = 0
    end_frame: int = 0
    frame_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "start_time": round(self.start_time, 4),
            "end_time": round(self.end_time, 4),
            "duration": round(self.duration, 4),
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "frame_count": self.frame_count,
        }


@dataclass
class SceneDetectResult:
    """镜头分割结果

    Attributes:
        success: 是否成功
        error: 错误信息
        video_path: 视频路径
        detector_type: 检测器类型
        scene_count: 镜头数
        total_duration: 总时长（秒）
        segments: 镜头片段列表
        fps: 视频帧率
        from_cache: 是否来自缓存
    """
    success: bool = False
    error: str = ""
    video_path: str = ""
    detector_type: str = ""
    scene_count: int = 0
    total_duration: float = 0.0
    segments: List[SceneSegment] = field(default_factory=list)
    fps: float = 0.0
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "video_path": self.video_path,
            "detector_type": self.detector_type,
            "scene_count": self.scene_count,
            "total_duration": round(self.total_duration, 4),
            "segments": [s.to_dict() for s in self.segments],
            "fps": round(self.fps, 4),
            "from_cache": self.from_cache,
        }


# ---------------------------------------------------------------------------
# 检测器
# ---------------------------------------------------------------------------

class SceneDetector:
    """镜头分割器（封装 PySceneDetect）

    Usage:
        detector = SceneDetector(detector_type="content", threshold=27.0)
        result = detector.detect("video.mp4")
        if result.success:
            for seg in result.segments:
                print(seg.index, seg.start_time, seg.end_time)
    """

    # 支持的检测器类型
    DETECTOR_TYPES = ("content", "adaptive", "threshold")

    def __init__(
        self,
        detector_type: str = "content",
        threshold: float = 27.0,
        min_scene_len: int = 15,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
    ):
        """
        Args:
            detector_type: 检测器类型，content/adaptive/threshold
            threshold: 检测阈值
                      - content: 内容变化阈值（默认 27.0）
                      - adaptive: 自适应阈值（默认 3.0）
                      - threshold: 亮度阈值（默认 12.0）
            min_scene_len: 最小镜头长度（帧）
            enable_cache: 是否启用磁盘缓存
            cache_dir: 缓存目录（默认 .cache/scene_detect）
        """
        if detector_type not in self.DETECTOR_TYPES:
            raise ValueError(
                f"不支持的检测器类型: {detector_type}，"
                f"可选: {self.DETECTOR_TYPES}"
            )
        self.detector_type = detector_type
        self.threshold = threshold
        self.min_scene_len = min_scene_len
        self._enable_cache = enable_cache
        self._cache_dir = cache_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            ".cache", "scene_detect"
        )
        # 缓存管理（可选）
        self._disk_cache = None
        self._fingerprint = None
        if enable_cache:
            try:
                from performance.cache_manager import DiskCache, file_fingerprint
                self._disk_cache = DiskCache(
                    cache_dir=self._cache_dir, name="scene_detect"
                )
                self._fingerprint = file_fingerprint
            except ImportError:
                # performance 模块不可用时降级为无缓存
                self._enable_cache = False

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def detect(self, video_path: str) -> SceneDetectResult:
        """对单个视频执行镜头分割

        Args:
            video_path: 视频文件路径

        Returns:
            SceneDetectResult，失败时 success=False 并填入 error
        """
        if not _SCENEDETECT_AVAILABLE:
            return SceneDetectResult(
                success=False,
                error="PySceneDetect 未安装，请执行 pip install 'scenedetect[opencv]'",
                video_path=video_path,
                detector_type=self.detector_type,
            )

        if not os.path.exists(video_path):
            return SceneDetectResult(
                success=False,
                error=f"视频文件不存在: {video_path}",
                video_path=video_path,
                detector_type=self.detector_type,
            )

        # 缓存命中检查
        cache_key = None
        if self._enable_cache and self._disk_cache is not None:
            fp_extra = f"{self.detector_type}:{self.threshold}:{self.min_scene_len}"
            cache_key = self._fingerprint(video_path, fp_extra)
            cached = self._disk_cache.get(cache_key, source_path=video_path)
            if cached is not None:
                # 重建 SceneSegment 列表
                segments = [
                    SceneSegment(**seg) if isinstance(seg, dict) else seg
                    for seg in cached.get("segments", [])
                ]
                return SceneDetectResult(
                    success=True,
                    video_path=video_path,
                    detector_type=self.detector_type,
                    scene_count=len(segments),
                    total_duration=cached.get("total_duration", 0.0),
                    segments=segments,
                    fps=cached.get("fps", 0.0),
                    from_cache=True,
                )

        # 执行检测
        try:
            scene_list, fps = self._run_detect(video_path)
        except Exception as e:
            return SceneDetectResult(
                success=False,
                error=f"镜头分割失败: {type(e).__name__}: {e}",
                video_path=video_path,
                detector_type=self.detector_type,
            )

        # 转换为 SceneSegment 列表
        segments: List[SceneSegment] = []
        for idx, (start, end) in enumerate(scene_list):
            start_time = start.get_seconds()
            end_time = end.get_seconds()
            start_frame = start.get_frames()
            end_frame = end.get_frames()
            segments.append(SceneSegment(
                index=idx,
                start_time=start_time,
                end_time=end_time,
                duration=round(end_time - start_time, 4),
                start_frame=start_frame,
                end_frame=end_frame,
                frame_count=end_frame - start_frame,
            ))

        total_duration = segments[-1].end_time if segments else 0.0

        result = SceneDetectResult(
            success=True,
            video_path=video_path,
            detector_type=self.detector_type,
            scene_count=len(segments),
            total_duration=total_duration,
            segments=segments,
            fps=fps,
        )

        # 写入缓存
        if self._enable_cache and self._disk_cache is not None and cache_key:
            try:
                self._disk_cache.set(
                    cache_key,
                    result.to_dict(),
                    source_path=video_path,
                )
            except Exception:
                pass  # 缓存写入失败不影响主流程

        return result

    def detect_batch(
        self, video_paths: List[str], max_workers: Optional[int] = None
    ) -> Dict[str, SceneDetectResult]:
        """批量镜头分割

        Args:
            video_paths: 视频路径列表
            max_workers: 最大并发数（默认 min(len, cpu_count)）

        Returns:
            {video_path: SceneDetectResult}
        """
        if max_workers is None:
            import multiprocessing
            max_workers = min(len(video_paths), multiprocessing.cpu_count())

        if max_workers <= 1 or len(video_paths) <= 1:
            return {p: self.detect(p) for p in video_paths}

        import concurrent.futures
        results: Dict[str, SceneDetectResult] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
            future_to_path = {
                exe.submit(self.detect, p): p for p in video_paths
            }
            for fut in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[fut]
                try:
                    results[path] = fut.result()
                except Exception as e:
                    results[path] = SceneDetectResult(
                        success=False,
                        error=f"{type(e).__name__}: {e}",
                        video_path=path,
                        detector_type=self.detector_type,
                    )
        return results

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _make_detector(self):
        """根据 detector_type 创建检测器实例"""
        if self.detector_type == "content":
            return ContentDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len,
            )
        if self.detector_type == "adaptive":
            return AdaptiveDetector(
                adaptive_threshold=self.threshold,
                min_scene_len=self.min_scene_len,
            )
        if self.detector_type == "threshold":
            return ThresholdDetector(
                threshold=self.threshold,
                min_scene_len=self.min_scene_len,
            )
        raise ValueError(f"未知检测器类型: {self.detector_type}")

    def _run_detect(self, video_path: str):
        """执行 PySceneDetect 检测

        Returns:
            (scene_list, fps) — scene_list 为 [(FrameTimecode, FrameTimecode), ...]
        """
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(self._make_detector())
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()
        fps = video.frame_rate if hasattr(video, "frame_rate") else 0.0
        return scene_list, fps


# ---------------------------------------------------------------------------
# 模块级便捷 API
# ---------------------------------------------------------------------------

def detect_scenes(
    video_path: str,
    detector_type: str = "content",
    threshold: float = 27.0,
    min_scene_len: int = 15,
) -> SceneDetectResult:
    """便捷 API：对单个视频执行镜头分割

    Args:
        video_path: 视频文件路径
        detector_type: 检测器类型 content/adaptive/threshold
        threshold: 检测阈值
        min_scene_len: 最小镜头长度（帧）

    Returns:
        SceneDetectResult
    """
    # 磁盘缓存：同一视频+参数组合不重复分析
    if _scene_cache and os.path.exists(video_path):
        cache_key = file_fingerprint(
            video_path,
            extra=f"{detector_type}:{threshold}:{min_scene_len}",
        )
        cached = _scene_cache.get(cache_key)
        if cached is not None:
            return cached

    detector = SceneDetector(
        detector_type=detector_type,
        threshold=threshold,
        min_scene_len=min_scene_len,
        enable_cache=False,
    )
    result = detector.detect(video_path)

    # 缓存成功结果
    if _scene_cache and result.success and os.path.exists(video_path):
        cache_key = file_fingerprint(
            video_path,
            extra=f"{detector_type}:{threshold}:{min_scene_len}",
        )
        _scene_cache.set(cache_key, result)

    return result


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print(f"PySceneDetect available: {_SCENEDETECT_AVAILABLE}")
    print(f"OpenCV available: {_CV2_AVAILABLE}")
    print(f"Supported detector types: {SceneDetector.DETECTOR_TYPES}")
    if len(sys.argv) > 1:
        result = detect_scenes(sys.argv[1])
        print(f"\n视频: {sys.argv[1]}")
        print(f"成功: {result.success}")
        if result.success:
            print(f"镜头数: {result.scene_count}")
            print(f"总时长: {result.total_duration:.2f}s")
            print(f"帧率: {result.fps:.2f}fps")
            for seg in result.segments[:5]:
                print(f"  [{seg.index}] {seg.start_time:.2f}s -> "
                      f"{seg.end_time:.2f}s (dur={seg.duration:.2f}s, "
                      f"frames={seg.frame_count})")
            if result.scene_count > 5:
                print(f"  ... 共 {result.scene_count} 个片段")
        else:
            print(f"错误: {result.error}")
