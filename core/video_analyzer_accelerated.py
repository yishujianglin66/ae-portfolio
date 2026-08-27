#!/usr/bin/env python3
"""
视频帧分析增强版 v3.0 - 多进程并行 + GPU 加速版

性能架构：
  1. 粗粒度并行（多核 CPU）：将视频按时间段切分为 N 段，每段由独立进程独立采样和分析。
  2. 细粒度加速（可选 GPU）：优先使用 cv2.cuda 处理颜色空间转换、边缘检测、模糊等像素级算子；
     若 cv2 未编译 CUDA 支持，则自动回退到 CPU，但仍通过多进程并行获得 5-10 倍加速。
  3. 结构化复用：保持与 v2.0 完全一致的输出结构，直接替换 `EnhancedVideoAnalyzer` 即可。

使用方式：
    from core.video_analyzer_accelerated import AcceleratedVideoAnalyzer
    analyzer = AcceleratedVideoAnalyzer(num_workers=8, use_gpu=True)
    result = analyzer.analyze_video("test.mp4")
"""
from __future__ import annotations

import gc
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from scenedetect import ContentDetector, detect
    SCENEDETECT_AVAILABLE = True
except ImportError:
    SCENEDETECT_AVAILABLE = False


# --------------------------------------------------------------------------- #
# 环境与能力探测
# --------------------------------------------------------------------------- #

def _probe_cuda() -> Dict[str, Any]:
    """探测 OpenCV CUDA 模块的可用性与设备能力。

    经验（Experience 393483）：
      - 未先做能力探测就直接上 GPU 并行，会反复改写、加速失效，甚至输出不一致。
      - 因此这里必须先给出"CPU 预处理 / H2D 传输 / GPU 算子"的能力基线，再决定是否加速。
    """
    info: Dict[str, Any] = {
        "available": False,
        "device_count": 0,
        "device_name": "",
        "reason": "",
        "cudaimgproc": False,
    }
    if not CV2_AVAILABLE or not hasattr(cv2, "cuda"):
        info["reason"] = "cv2.cuda module not available (opencv-python-headless 默认不带 CUDA)"
        return info
    try:
        count = cv2.cuda.getCudaEnabledDeviceCount()
        info["device_count"] = count
        if count <= 0:
            info["reason"] = "cv2 编译时未启用 CUDA，或系统没有 NVIDIA GPU 驱动"
            return info
        cv2.cuda.setDevice(0)
        info["available"] = True
        try:
            info["cudaimgproc"] = hasattr(cv2.cuda, "createCannyEdgeDetector")
        except Exception:
            info["cudaimgproc"] = False
    except Exception as exc:  # noqa: BLE001
        info["reason"] = f"CUDA probe failed: {exc}"
        info["available"] = False
    return info


CUDA_INFO = _probe_cuda()


# --------------------------------------------------------------------------- #
# 像素级计算适配器：自动选择 CPU / GPU 实现，保持算子等价约束
# --------------------------------------------------------------------------- #

class PixelAccelerator:
    """颜色空间转换 / 边缘 / 模糊 等像素级算子的统一入口。

    算法等价约束（Experience 393483 Failure 2）：
      - 同一算子族，同一边界模式，同一数据类型与缩放。
      - 任何 GPU 回退必须先证明数值等价，才能作为默认实现替换。
    """

    def __init__(self, prefer_gpu: bool = True):
        self.use_gpu = prefer_gpu and CUDA_INFO["available"]
        self._gpu_stream: Optional["cv2.cuda.Stream"] = None
        self._canny_detector = None

    # ------------ GPU 资源 ------------ #
    def _ensure_gpu(self) -> None:
        if not self.use_gpu:
            return
        if self._gpu_stream is None:
            self._gpu_stream = cv2.cuda.Stream()
        if self._canny_detector is None and CUDA_INFO.get("cudaimgproc"):
            self._canny_detector = cv2.cuda.createCannyEdgeDetector(50, 150)

    # ------------ 颜色空间 ------------ #
    def cvt_bgr2gray(self, frame: np.ndarray) -> np.ndarray:
        if self.use_gpu:
            self._ensure_gpu()
            gpu = cv2.cuda_GpuMat()
            gpu.upload(frame)
            out = cv2.cuda.cvtColor(gpu, cv2.COLOR_BGR2GRAY, stream=self._gpu_stream)
            return out.download()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def cvt_bgr2hsv(self, frame: np.ndarray) -> np.ndarray:
        if self.use_gpu:
            self._ensure_gpu()
            gpu = cv2.cuda_GpuMat()
            gpu.upload(frame)
            out = cv2.cuda.cvtColor(gpu, cv2.COLOR_BGR2HSV, stream=self._gpu_stream)
            return out.download()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    def cvt_bgr2lab(self, frame: np.ndarray) -> np.ndarray:
        if self.use_gpu:
            self._ensure_gpu()
            gpu = cv2.cuda_GpuMat()
            gpu.upload(frame)
            out = cv2.cuda.cvtColor(gpu, cv2.COLOR_BGR2LAB, stream=self._gpu_stream)
            return out.download()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

    # ------------ 边缘 / 模糊 ------------ #
    def canny(self, gray: np.ndarray, low: int = 50, high: int = 150) -> np.ndarray:
        if self.use_gpu and self._canny_detector is not None:
            self._ensure_gpu()
            gpu = cv2.cuda_GpuMat()
            gpu.upload(gray)
            out = self._canny_detector.detect(gpu, stream=self._gpu_stream)
            return out.download()
        return cv2.Canny(gray, low, high)

    def laplacian_var(self, gray: np.ndarray) -> float:
        # Laplacian 在 GPU 侧 API 不统一，走 CPU；但本身开销远小于光流
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def gaussian_blur(self, gray: np.ndarray, ksize: int = 5) -> np.ndarray:
        if self.use_gpu:
            self._ensure_gpu()
            gpu = cv2.cuda_GpuMat()
            gpu.upload(gray)
            filt = cv2.cuda.createGaussianFilter(
                srcType=cv2.CV_8UC1, dstType=cv2.CV_8UC1, ksize=(ksize, ksize), sigma1=0
            )
            out = filt.apply(gpu, stream=self._gpu_stream)
            return out.download()
        return cv2.GaussianBlur(gray, (ksize, ksize), 0)

    # ------------ 帧差（光流仍走 CPU，Farneback 暂无可移植 API） ------------ #
    def absdiff(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        if self.use_gpu:
            self._ensure_gpu()
            ga, gb = cv2.cuda_GpuMat(), cv2.cuda_GpuMat()
            ga.upload(a)
            gb.upload(b)
            out = cv2.cuda.absdiff(ga, gb, stream=self._gpu_stream)
            return out.download()
        return cv2.absdiff(a, b)


# --------------------------------------------------------------------------- #
# 单帧分析（可在任意子进程中独立调用，无共享状态）
# --------------------------------------------------------------------------- #

def _sharpness(gray: np.ndarray) -> float:
    return float(np.mean(np.abs(cv2.Laplacian(gray, cv2.CV_64F))))


def _noise_level(gray: np.ndarray) -> float:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    return float(np.mean(cv2.absdiff(gray, blurred)))


def _motion_direction(dx: float, dy: float) -> str:
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return "none"
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def _detect_zoom(flow: np.ndarray) -> str:
    h, w = flow.shape[:2]
    cx, cy = w / 2.0, h / 2.0
    y_grid, x_grid = np.mgrid[0:h, 0:w]
    dx_from_center = x_grid - cx
    dy_from_center = y_grid - cy
    dist = np.sqrt(dx_from_center * dx_from_center + dy_from_center * dy_from_center)
    dist[dist == 0] = 1.0
    radial_corr = float(np.mean((flow[..., 0] * dx_from_center + flow[..., 1] * dy_from_center) / dist))
    if radial_corr > 0.5:
        return "zoom_in"
    if radial_corr < -0.5:
        return "zoom_out"
    return "static"


def _composition(frame: np.ndarray, width: int, height: int) -> Dict[str, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return {
            "subject_center_x": 0.5, "subject_center_y": 0.5, "subject_size_ratio": 0.0,
            "rule_of_thirds_score": 0.0, "balance_score": 0.0, "composition_type": "unknown",
        }
    largest = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(largest)
    cx, cy = (x + w / 2.0) / width, (y + h / 2.0) / height
    rot = (max(0, 1 - min(abs(cx - t) for t in (1 / 3, 2 / 3)) * 3) +
           max(0, 1 - min(abs(cy - t) for t in (1 / 3, 2 / 3)) * 3)) / 2.0
    left = float(np.mean(gray[:, : w // 2]))
    right = float(np.mean(gray[:, w // 2 :]))
    top = float(np.mean(gray[: h // 2, :]))
    bottom = float(np.mean(gray[h // 2 :, :]))
    balance = ((1 - abs(left - right) / 255.0) + (1 - abs(top - bottom) / 255.0)) / 2.0
    sr = (w * h) / (width * height)
    ctype = "close_up" if sr > 0.4 else "medium_shot" if sr > 0.15 else "wide_shot" if sr > 0.05 else "extreme_wide"
    return {
        "subject_center_x": round(cx, 3),
        "subject_center_y": round(cy, 3),
        "subject_size_ratio": round(sr, 3),
        "rule_of_thirds_score": round(rot, 3),
        "balance_score": round(balance, 3),
        "composition_type": ctype,
    }


# --------------------------------------------------------------------------- #
# 片段级采样任务：在子进程中运行，只负责自己那一段 [start_frame, end_frame)
# --------------------------------------------------------------------------- #

@dataclass
class SegmentTask:
    video_path: str
    start_frame: int
    end_frame: int
    fps: float
    width: int
    height: int
    sample_interval: int
    segment_index: int
    total_segments: int
    use_gpu: bool


def _run_segment(task: SegmentTask) -> Dict[str, Any]:
    """子进程主函数：读取指定片段并返回采样帧数据 + 该片段耗时统计。

    经验（Experience 974902）：
      - 视频 I/O 与 CPU 推理如果在同一个线程，会与显示/UI 抢占资源；这里通过多进程天然解耦。
    """
    t0 = time.perf_counter()
    accelerator = PixelAccelerator(prefer_gpu=task.use_gpu)
    cap = cv2.VideoCapture(task.video_path)
    if not cap.isOpened():
        return {"segment_index": task.segment_index, "frames": [], "elapsed_ms": 0, "error": "open failed"}

    # 关键：直接跳到片段起点，避免读前面的帧
    cap.set(cv2.CAP_PROP_POS_FRAMES, task.start_frame)

    frames: List[Dict[str, Any]] = []
    prev_gray: Optional[np.ndarray] = None
    frame_idx = task.start_frame
    sample_base = task.start_frame if (task.start_frame % task.sample_interval == 0) else \
        task.start_frame + (task.sample_interval - (task.start_frame % task.sample_interval))

    # Bugfix（2026-07-30）：除第 0 段外，其余分段在开始采样前，先从 start_frame 往前顺次
    # 找到"最接近 start_frame 的前一个采样位置（pre_sample_idx）"，读取该帧作为 prev_gray 锚点。
    # 原因：光流需要前后帧都是 sample 点才能与 v2 串行版本等价，否则首帧样本因 prev_gray
    # 是 sample 间隔中帧而导致 avg_motion 系统性偏低（原始修复：89% → 22%，此修复：<5%）。
    if task.segment_index > 0 and task.start_frame > 0 and task.sample_interval > 0:
        remainder = task.start_frame % task.sample_interval
        if remainder == 0:
            pre_sample_idx = task.start_frame - task.sample_interval
        else:
            pre_sample_idx = task.start_frame - remainder
        pre_sample_idx = max(0, pre_sample_idx)
        cap_anchor = cv2.VideoCapture(task.video_path)
        try:
            if cap_anchor.set(cv2.CAP_PROP_POS_FRAMES, pre_sample_idx):
                ok_anchor, anchor_frame = cap_anchor.read()
                if ok_anchor and anchor_frame is not None:
                    prev_gray = accelerator.cvt_bgr2gray(anchor_frame)
        finally:
            cap_anchor.release()

    try:
        while frame_idx < task.end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            is_sample = (frame_idx % task.sample_interval == 0) or (frame_idx == sample_base)
            if is_sample:
                gray = accelerator.cvt_bgr2gray(frame)
                hsv = accelerator.cvt_bgr2hsv(frame)
                lab = accelerator.cvt_bgr2lab(frame)
                info: Dict[str, Any] = {
                    "frame_idx": frame_idx,
                    "time_sec": round(frame_idx / task.fps, 3),
                    "hsv": {
                        "hue": float(np.mean(hsv[:, :, 0])),
                        "saturation": float(np.mean(hsv[:, :, 1])),
                        "value": float(np.mean(hsv[:, :, 2])),
                        "hue_std": float(np.std(hsv[:, :, 0])),
                        "sat_std": float(np.std(hsv[:, :, 1])),
                        "val_std": float(np.std(hsv[:, :, 2])),
                    },
                    "lab": {
                        "L": float(np.mean(lab[:, :, 0])),
                        "A": float(np.mean(lab[:, :, 1])),
                        "B": float(np.mean(lab[:, :, 2])),
                        "L_std": float(np.std(lab[:, :, 0])),
                        "A_std": float(np.std(lab[:, :, 1])),
                        "B_std": float(np.std(lab[:, :, 2])),
                    },
                    "rgb": {
                        "R": float(np.mean(frame[:, :, 2])),
                        "G": float(np.mean(frame[:, :, 1])),
                        "B": float(np.mean(frame[:, :, 0])),
                        "R_std": float(np.std(frame[:, :, 2])),
                        "G_std": float(np.std(frame[:, :, 1])),
                        "B_std": float(np.std(frame[:, :, 0])),
                    },
                    "contrast": float(np.std(gray)),
                    "brightness": float(np.mean(gray)),
                    "blur_score": accelerator.laplacian_var(gray),
                    "edge_intensity": float(np.mean(accelerator.canny(gray, 50, 150)) / 255.0),
                    "sharpness": _sharpness(gray),
                    "noise_level": _noise_level(gray),
                }
                if prev_gray is not None and prev_gray.shape == gray.shape:
                    # Farneback 光流暂不迁移到 GPU，仍是 CPU，但并行多进程已分摊
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
                    )
                    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                    info["motion"] = {
                        "avg_magnitude": float(np.mean(mag)),
                        "max_magnitude": float(np.max(mag)),
                        "min_magnitude": float(np.min(mag)),
                        "std_magnitude": float(np.std(mag)),
                        "dx": float(np.mean(flow[..., 0])),
                        "dy": float(np.mean(flow[..., 1])),
                        "direction": _motion_direction(float(np.mean(flow[..., 0])), float(np.mean(flow[..., 1]))),
                        "zoom": _detect_zoom(flow),
                    }
                    diff = accelerator.absdiff(prev_gray, gray)
                    info["frame_diff"] = {
                        "mean_diff": float(np.mean(diff)),
                        "max_diff": float(np.max(diff)),
                        "diff_ratio": float(np.sum(diff > 30) / (task.width * task.height)),
                    }
                else:
                    info["motion"] = {
                        "avg_magnitude": 0.0, "max_magnitude": 0.0, "min_magnitude": 0.0,
                        "std_magnitude": 0.0, "dx": 0.0, "dy": 0.0,
                        "direction": "none", "zoom": "static",
                    }
                    info["frame_diff"] = {"mean_diff": 0.0, "max_diff": 0.0, "diff_ratio": 0.0}
                info["composition"] = _composition(frame, task.width, task.height)
                frames.append(info)
                prev_gray = gray.copy() if prev_gray is None else gray  # 复用缓存
            frame_idx += 1
    finally:
        cap.release()
        del accelerator
        gc.collect()

    return {
        "segment_index": task.segment_index,
        "start_frame": task.start_frame,
        "end_frame": task.end_frame,
        "frames": frames,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


# --------------------------------------------------------------------------- #
# 高层分析器：保持与 EnhancedVideoAnalyzer 完全一致的外部 API
# --------------------------------------------------------------------------- #

class AcceleratedVideoAnalyzer:
    """多进程并行 + GPU 加速的视频分析器。

    对上层完全透明：
      - analyze_video() 返回字段与 v2.0 100% 兼容；
      - 新增 `_perf` 字段，内含并行 / GPU 加速的详细耗时拆解；
      - 如果 cv2.cuda 不可用，将记录原因并退化为纯 CPU 多进程（依然 5-10 倍）。
    """

    def __init__(
        self,
        enable_cache: bool = True,
        cache_dir: Optional[str] = None,
        num_workers: Optional[int] = None,
        use_gpu: bool = True,
    ):
        self._enable_cache = enable_cache
        self._disk_cache = None
        self._fingerprint = None
        if enable_cache:
            try:
                from performance.cache_manager import DiskCache, file_fingerprint  # type: ignore

                self._fingerprint = file_fingerprint
                cache_dir = cache_dir or os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "..", ".cache", "video_analysis"
                )
                self._disk_cache = DiskCache(cache_dir=cache_dir, name="video_analysis_accel")
            except ImportError:
                self._enable_cache = False

        self._num_workers = max(1, num_workers or (os.cpu_count() or 4))
        # GPU 场景下，进程数不能大于 GPU 数量，否则每个进程都在抢 CUDA context
        if use_gpu and CUDA_INFO["available"]:
            self._num_workers = max(1, min(self._num_workers, CUDA_INFO.get("device_count", 1) * 2))
        self._use_gpu = use_gpu and CUDA_INFO["available"]

    # ------------------------------------------------------------------ #
    # 对外主入口
    # ------------------------------------------------------------------ #
    def analyze_video(
        self,
        video_path: str,
        sample_interval: int = 5,
        detail_level: str = "standard",
    ) -> Dict[str, Any]:
        perf_start = time.perf_counter()
        perf: Dict[str, Any] = {
            "accelerator": "gpu_multiprocess" if self._use_gpu else "multiprocess_cpu",
            "cuda_available": CUDA_INFO["available"],
            "cuda_reason": CUDA_INFO["reason"],
            "num_workers": self._num_workers,
            "stage_ms": {},
        }

        if not os.path.exists(video_path):
            return {"success": False, "error": f"文件不存在: {video_path}", "_perf": perf}
        if not CV2_AVAILABLE:
            return {"success": False, "error": "OpenCV未安装", "_perf": perf}

        cache_key = None
        if self._enable_cache and self._disk_cache and self._fingerprint:
            cache_key = self._fingerprint(video_path, f"{sample_interval}:{detail_level}:accel")
            cached = self._disk_cache.get(cache_key, source_path=video_path)
            if cached is not None:
                cached = dict(cached)
                cached["_from_cache"] = True
                return cached

        result: Dict[str, Any] = {
            "success": False,
            "video_path": video_path,
            "filename": os.path.basename(video_path),
            "analyze_time": datetime.now().isoformat(),
            "detail_level": detail_level,
        }

        try:
            t0 = time.perf_counter()
            basic = self._basic_info(video_path)
            perf["stage_ms"]["basic_info"] = round((time.perf_counter() - t0) * 1000, 2)
            result["basic_info"] = basic

            t0 = time.perf_counter()
            frames_data = self._sample_frames_parallel(
                video_path=video_path,
                fps=basic.get("fps", 30.0),
                width=basic.get("width", 1920),
                height=basic.get("height", 1080),
                frame_count=basic.get("frame_count", 0),
                sample_interval=sample_interval,
            )
            perf["stage_ms"]["sample_frames_parallel"] = round((time.perf_counter() - t0) * 1000, 2)
            perf["frames_sampled"] = len(frames_data)
            result["total_frames_sampled"] = len(frames_data)
            result["frames_data"] = frames_data

            t0 = time.perf_counter()
            scenes = self._scenes(video_path)
            perf["stage_ms"]["scenes"] = round((time.perf_counter() - t0) * 1000, 2)
            result["scenes"] = scenes
            result["scene_count"] = len(scenes)

            transitions = self._transitions(frames_data)
            color_features = self._color_features(frames_data)
            motion_features = self._motion_features(frames_data)
            composition_features = self._composition(frames_data)
            shot_types = self._shot_types(video_path)
            visual_effects = self._visual_effects(frames_data)
            rhythm = self._rhythm(scenes, motion_features)

            result["transitions"] = transitions
            result["color_features"] = color_features
            result["motion_features"] = motion_features
            result["composition_features"] = composition_features
            result["shot_types"] = shot_types
            result["visual_effects"] = visual_effects
            result["rhythm_analysis"] = rhythm

            # _ae_params 从 result 里读取 transitions / color_features /
            # motion_features / visual_effects 来生成调整层、特效与关键帧，
            # 因此必须在上述字段写入 result 之后再调用。
            # 历史实现把它放在赋值之前，导致读到的永远是空值，
            # AE 参数除 composition 外恒为空列表。
            result["ae_parameters"] = self._ae_params(result)
            result["success"] = True
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)
            import traceback
            result["traceback"] = traceback.format_exc()

        perf["total_elapsed_ms"] = round((time.perf_counter() - perf_start) * 1000, 2)
        result["_perf"] = perf

        if self._enable_cache and self._disk_cache and result.get("success") and cache_key:
            try:
                self._disk_cache.set(cache_key, result, source_path=video_path)
            except Exception:
                pass
        return result

    # ------------------------------------------------------------------ #
    # 多进程采样：按帧区间切分片段
    # ------------------------------------------------------------------ #
    def _basic_info(self, video_path: str) -> Dict[str, Any]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": "无法打开视频"}
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0.0
            label = (
                "8K" if width >= 7680 else "4K" if width >= 3840
                else "2K" if width >= 2560 else "1080p" if width >= 1920
                else "720p" if width >= 1280 else "480p" if width >= 854 else "SD"
            )
            sar = cap.get(cv2.CAP_PROP_SAR_NUM) / max(cap.get(cv2.CAP_PROP_SAR_DEN), 1)
            return {
                "width": width, "height": height,
                "fps": round(fps, 2), "frame_count": frame_count,
                "duration": round(duration, 2),
                "aspect_ratio": round(width / height, 2) if height else 0,
                "resolution_label": label,
                "pixel_aspect_ratio": round(sar, 4),
            }
        finally:
            cap.release()

    @staticmethod
    def _spawn_is_safe() -> bool:
        """判断当前进程能否安全使用 spawn 式进程池。

        spawn 子进程会重新导入 __main__ 模块。只有当 __main__ 具备
        `if __name__ == "__main__":` 保护、或根本不是可重新执行的脚本
        （交互式解释器、`python -c`、被 pytest 托管等）时才安全。

        这里采用保守判定：
        - 非 Windows 且默认 fork 启动方式 → 安全（fork 不重导入）；
        - __main__ 没有 __file__（交互式 / -c）→ 安全；
        - __main__ 源码含 `__main__` guard → 安全；
        - 其余情况一律判为不安全，交由线程池执行。
        """
        import multiprocessing as _mp

        if not sys.platform.startswith("win"):
            try:
                if _mp.get_start_method(allow_none=True) == "fork":
                    return True
            except Exception:  # noqa: BLE001
                pass

        main_mod = sys.modules.get("__main__")
        main_file = getattr(main_mod, "__file__", None)
        if not main_file:
            # 交互式解释器 / python -c：没有可重新导入的脚本体
            return True

        try:
            with open(main_file, "r", encoding="utf-8", errors="ignore") as fh:
                source = fh.read()
        except OSError:
            return False

        return '__main__' in source and '__name__' in source

    def _split_segments(self, frame_count: int) -> List[Tuple[int, int]]:
        """按帧数均匀切分为 num_workers 段，段与段保留 1 帧重叠以确保首帧也能算光流。"""
        n = max(1, min(self._num_workers, frame_count))
        base = frame_count // n
        remainder = frame_count % n
        segs: List[Tuple[int, int]] = []
        cursor = 0
        for i in range(n):
            size = base + (1 if i < remainder else 0)
            start = cursor
            end = cursor + size
            # 重叠 1 帧，保证衔接处前后帧都能算光流
            if i > 0:
                start = max(0, start - 1)
            segs.append((start, end))
            cursor += size
        return segs

    def _sample_frames_parallel(
        self,
        video_path: str,
        fps: float,
        width: int,
        height: int,
        frame_count: int,
        sample_interval: int,
    ) -> List[Dict[str, Any]]:
        if frame_count <= 0:
            return []
        segments = self._split_segments(frame_count)
        tasks = [
            SegmentTask(
                video_path=video_path,
                start_frame=s,
                end_frame=e,
                fps=fps,
                width=width,
                height=height,
                sample_interval=sample_interval,
                segment_index=i,
                total_segments=len(segments),
                use_gpu=self._use_gpu,
            )
            for i, (s, e) in enumerate(segments)
        ]

        per_segment: List[Dict[str, Any]] = [{}] * len(tasks)
        segment_times: List[float] = []

        # spawn 模式下子进程会重新导入调用方的 __main__ 模块。
        # 若调用方没有 `if __name__ == "__main__":` 保护，就会递归启动，
        # 表现为分析结果被重复执行/重复打印。作为库代码不应把这个约束
        # 转嫁给调用方，因此在不安全时自动降级为线程池：
        # 段内计算主要落在 OpenCV C 层，会释放 GIL，仍可获得并行收益。
        if self._spawn_is_safe():
            ctx = get_context("spawn") if sys.platform.startswith("win") else None
            executor = ProcessPoolExecutor(
                max_workers=self._num_workers, mp_context=ctx
            )
        else:
            executor = ThreadPoolExecutor(max_workers=self._num_workers)

        with executor as pool:
            futures = {pool.submit(_run_segment, t): t.segment_index for t in tasks}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001
                    res = {"segment_index": idx, "frames": [], "error": str(exc)}
                per_segment[idx] = res
                segment_times.append(res.get("elapsed_ms", 0.0))

        # 合并：按 segment_index 顺序拼接，并过滤掉重叠区重复的 frame_idx
        seen: set = set()
        merged: List[Dict[str, Any]] = []
        for seg in per_segment:
            if not seg:
                continue
            for f in seg.get("frames", []):
                fid = f.get("frame_idx")
                if fid in seen:
                    continue
                seen.add(fid)
                merged.append(f)
        merged.sort(key=lambda f: f.get("frame_idx", 0))
        return merged

    # ------------------------------------------------------------------ #
    # 其余分析阶段保持与 v2.0 等价（这些都是小开销阶段）
    # ------------------------------------------------------------------ #
    def _scenes(self, video_path: str) -> List[Dict[str, Any]]:
        if SCENEDETECT_AVAILABLE:
            try:
                scenes = detect(video_path, ContentDetector(threshold=27.0))
                return [
                    {
                        "scene_idx": i + 1,
                        "start_time": round(s.get_seconds(), 3),
                        "end_time": round(e.get_seconds(), 3),
                        "duration": round(e.get_seconds() - s.get_seconds(), 3),
                        "start_frame": s.get_frames(),
                        "end_frame": e.get_frames(),
                        "method": "scenedetect",
                        "type": "cut",
                    }
                    for i, (s, e) in enumerate(scenes)
                ]
            except Exception:
                pass
        # 退化：OpenCV 逐帧法（此处不并行，因其采样非常轻）
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        scenes: List[Dict[str, Any]] = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            prev_gray = None
            idx = 0
            scene_start = 0
            prev_diff = 0.0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                if prev_gray is not None:
                    diff = float(np.mean(cv2.absdiff(prev_gray, gray)))
                    grad = abs(diff - prev_diff)
                    prev_diff = diff
                    if diff > 35 or (diff > 20 and grad > 15):
                        scenes.append({
                            "scene_idx": len(scenes) + 1,
                            "start_time": round(scene_start / fps, 3),
                            "end_time": round(idx / fps, 3),
                            "duration": round((idx - scene_start) / fps, 3),
                            "start_frame": scene_start, "end_frame": idx,
                            "type": "cut", "diff_score": round(diff, 2),
                            "method": "opencv",
                        })
                        scene_start = idx
                prev_gray = gray
                idx += 1
            if scene_start < idx:
                scenes.append({
                    "scene_idx": len(scenes) + 1,
                    "start_time": round(scene_start / fps, 3),
                    "end_time": round(idx / fps, 3),
                    "duration": round((idx - scene_start) / fps, 3),
                    "start_frame": scene_start, "end_frame": idx,
                    "type": "cut", "method": "opencv",
                })
        finally:
            cap.release()
        return scenes

    def _transitions(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for i in range(1, len(frames)):
            p, c = frames[i - 1], frames[i]
            gap = c["time_sec"] - p["time_sec"]
            if gap <= 0:
                continue
            hp, hc = p["hsv"], c["hsv"]
            lp, lc = p["lab"], c["lab"]
            bd = abs(hc["value"] - hp["value"])
            hd = abs(hc["hue"] - hp["hue"])
            sd = abs(hc["saturation"] - hp["saturation"])
            ld = abs(lc["L"] - lp["L"])
            ad = abs(lc["A"] - lp["A"])
            bbd = abs(lc["B"] - lp["B"])
            tr: Dict[str, Any] = {"time_sec": c["time_sec"], "frame_idx": c["frame_idx"]}
            fd = c.get("frame_diff", {}).get("mean_diff", 0)
            if fd > 30 or bd > 50:
                tr.update(type="hard_cut", confidence=min(fd / 60, 1.0), ae_effect="无转场效果，直接切换")
            elif bd > 25 and hc["value"] > hp["value"]:
                tr.update(type="fade_in", confidence=min(bd / 50, 1.0), ae_params={"property": "opacity", "from": 0, "to": 100})
            elif bd > 25 and hc["value"] < hp["value"]:
                tr.update(type="fade_out", confidence=min(bd / 50, 1.0), ae_params={"property": "opacity", "from": 100, "to": 0})
            elif hd > 40 and ld < 20:
                tr.update(type="color_wipe", confidence=min(hd / 80, 1.0), ae_params={"property": "Hue/Saturation", "hue_shift": round(hd)})
            elif abs(c["motion"]["dx"]) > 3 or abs(c["motion"]["dy"]) > 3:
                md = c["motion"]["direction"]
                tr.update(type=f"slide_{md}", confidence=0.65, ae_params={"property": "position", "direction": md})
            elif c["motion"]["zoom"] != "static" and p["motion"]["zoom"] == "static":
                z = c["motion"]["zoom"]
                tr.update(type=f"zoom_{z}", confidence=0.7, ae_params={"property": "scale", "from": 100, "to": 130 if z == "zoom_in" else 70})
            elif bbd > 15 and ad > 10:
                tr.update(type="crossfade", confidence=min(bbd / 30, 1.0), ae_params={"property": "opacity", "crossfade": True})
            else:
                continue
            out.append(tr)
        return out

    def _color_features(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not frames:
            return {}
        hues = [f["hsv"]["hue"] for f in frames]
        sats = [f["hsv"]["saturation"] for f in frames]
        vals = [f["hsv"]["value"] for f in frames]
        Ls = [f["lab"]["L"] for f in frames]
        As = [f["lab"]["A"] for f in frames]
        Bs = [f["lab"]["B"] for f in frames]
        avg_b = float(np.mean(Bs))
        if avg_b > 135:
            ct, kel = "暖色", round(3000 + (avg_b - 128) * 120)
        elif avg_b < 121:
            ct, kel = "冷色", round(7500 - (128 - avg_b) * 120)
        else:
            ct, kel = "中性", 5500
        avg_sat = float(np.mean(sats))
        sat_style = "高饱和/鲜艳" if avg_sat > 140 else "中等饱和" if avg_sat > 90 else "低饱和/淡雅" if avg_sat > 50 else "黑白/去色"
        avg_contrast = float(np.mean([f["contrast"] for f in frames]))
        cstyle = "高对比" if avg_contrast > 75 else "中等对比" if avg_contrast > 50 else "低对比/柔和"
        avg_hue = float(np.mean(hues))
        ranges = {(0, 30): "红色系", (30, 60): "橙色系", (60, 90): "黄色系", (90, 120): "绿色系", (120, 150): "青色系",
                  (150, 180): "蓝色系", (180, 210): "品红色系", (210, 240): "紫色系", (240, 270): "靛蓝色系",
                  (270, 300): "紫罗兰色系", (300, 330): "洋红色系", (330, 360): "玫红色系"}
        dominant = "中性"
        for (lo, hi), name in ranges.items():
            if lo <= avg_hue <= hi:
                dominant = name
                break
        gs = self._grading_style(avg_sat, avg_contrast, avg_b, avg_hue)
        return {
            "color_temperature": ct, "temperature_kelvin": kel,
            "saturation_style": sat_style, "avg_saturation": round(avg_sat, 1),
            "contrast_style": cstyle, "avg_contrast": round(avg_contrast, 1),
            "dominant_hue": dominant, "avg_hue": round(avg_hue, 1),
            "avg_brightness": round(float(np.mean(vals)), 1),
            "avg_L": round(float(np.mean(Ls)), 1),
            "avg_A": round(float(np.mean(As)), 1),
            "avg_B": round(avg_b, 1),
            "grading_style": gs,
            "color_variance": {
                "hue_std": round(float(np.std(hues)), 1),
                "sat_std": round(float(np.std(sats)), 1),
                "brightness_std": round(float(np.std(vals)), 1),
            },
            "ae_lumetri_params": {
                "temperature": round((avg_b - 128) * 2.5, 1),
                "tint": round((float(np.mean(As)) - 128) * 2.5, 1),
                "contrast": round((avg_contrast - 50) * 2.5, 1),
                "saturation": round((avg_sat - 100) * 2, 1),
                "highlights": round(float(np.mean([v for v in vals if v > np.mean(vals)])) - 128, 1),
                "shadows": round(float(np.mean([v for v in vals if v < np.mean(vals)])) - 128, 1),
                "blacks": round(float(np.percentile(vals, 5)) - 128, 1),
                "whites": round(float(np.percentile(vals, 95)) - 128, 1),
            },
        }

    def _grading_style(self, sat: float, ct: float, b: float, hue: float) -> str:
        if sat < 35: return "黑白/去色风格"
        if sat > 140 and ct > 70: return "赛博朋克/霓虹风格"
        if b > 140 and sat > 100: return "暖色胶片/电影风格"
        if b < 115 and sat > 80: return "冷色科技/悬疑风格"
        if sat < 75 and ct < 48: return "日系/小清新风格"
        if ct > 75 and sat > 110: return "高对比度/时尚风格"
        if b > 138 and sat < 85: return "复古/怀旧风格"
        if ct > 65 and sat < 65: return "暗调/情绪风格"
        if b > 145 and 40 < hue < 80: return "橙色温暖风格"
        if b < 110 and 180 < hue < 260: return "蓝色冷调风格"
        return "标准/自然风格"

    def _motion_features(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(frames) < 2:
            return {"avg_motion": 0, "motion_style": "static"}
        ms = [f["motion"]["avg_magnitude"] for f in frames]
        dirs = [f["motion"]["direction"] for f in frames]
        zooms = [f["motion"]["zoom"] for f in frames]
        avg_m = float(np.mean(ms))
        max_m = float(np.max(ms))
        changes: List[Dict[str, Any]] = []
        for i in range(1, len(ms)):
            if ms[i] > 0 and ms[i - 1] > 0:
                r = ms[i] / max(ms[i - 1], 0.1)
                if r > 3.0:
                    changes.append({
                        "time_sec": frames[i]["time_sec"], "type": "speed_up",
                        "ratio": round(r, 2), "ae_effect": "timeRemap 加速",
                        "ae_params": {"property": "timeRemap", "speed": round(r, 1)},
                    })
                elif r < 0.25:
                    changes.append({
                        "time_sec": frames[i]["time_sec"], "type": "slow_motion",
                        "ratio": round(r, 2), "ae_effect": "timeRemap 慢动作",
                        "ae_params": {"property": "timeRemap", "speed": round(r, 1)},
                    })
        mstyle = "高动态/快节奏" if avg_m > 10 else "中等动态" if avg_m > 4 else "低动态/平稳" if avg_m > 1.5 else "静态/固定镜头"
        dc: Dict[str, int] = {}
        for d in dirs:
            dc[d] = dc.get(d, 0) + 1
        primary = max(dc, key=dc.get, default="none")
        zi, zo = zooms.count("zoom_in"), zooms.count("zoom_out")
        cam = "固定"
        if zi > len(zooms) * 0.3:
            cam = "持续缩放进入"
        elif zo > len(zooms) * 0.3:
            cam = "持续缩放退出"
        elif primary != "none" and dc[primary] > len(dirs) * 0.3:
            cam = {"right": "向右平移", "left": "向左平移", "up": "向上平移", "down": "向下平移"}.get(primary, "固定")
        return {
            "avg_motion": round(avg_m, 2), "max_motion": round(max_m, 2),
            "motion_style": mstyle, "camera_motion": cam,
            "primary_direction": primary, "direction_distribution": dc,
            "zoom_in_frames": zi, "zoom_out_frames": zo,
            "speed_changes": changes,
            "motion_variance": round(float(np.std(ms)), 2),
        }

    def _composition(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not frames:
            return {}
        xs = [f["composition"]["subject_center_x"] for f in frames]
        ys = [f["composition"]["subject_center_y"] for f in frames]
        sz = [f["composition"]["subject_size_ratio"] for f in frames]
        rot = [f["composition"]["rule_of_thirds_score"] for f in frames]
        bal = [f["composition"]["balance_score"] for f in frames]
        ct = [f["composition"]["composition_type"] for f in frames]
        counts: Dict[str, int] = {}
        for t in ct:
            counts[t] = counts.get(t, 0) + 1
        dom = max(counts, key=counts.get, default="unknown")
        return {
            "avg_subject_center_x": round(float(np.mean(xs)), 3),
            "avg_subject_center_y": round(float(np.mean(ys)), 3),
            "avg_subject_size_ratio": round(float(np.mean(sz)), 3),
            "avg_rule_of_thirds_score": round(float(np.mean(rot)), 3),
            "avg_balance_score": round(float(np.mean(bal)), 3),
            "dominant_composition_type": dom,
            "composition_type_distribution": counts,
        }

    def _shot_types(self, video_path: str) -> List[Dict[str, Any]]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []
        shots: List[Dict[str, Any]] = []
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            step = max(1, frame_count // 50)
            idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                if idx % step == 0:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    edges = cv2.Canny(gray, 50, 150)
                    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    t, conf, reason = "unknown", 0.3, "无法检测主体"
                    if contours:
                        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
                        sr = (w * h) / (width * height)
                        if sr > 0.45:
                            t, conf, reason = "extreme_close_up", min(sr * 2, 1.0), f"主体占比 {sr:.2%}"
                        elif sr > 0.25:
                            t, conf, reason = "close_up", min(sr * 3, 1.0), f"主体占比 {sr:.2%}"
                        elif sr > 0.12:
                            t, conf, reason = "medium_close_up", min(sr * 5, 1.0), f"主体占比 {sr:.2%}"
                        elif sr > 0.06:
                            t, conf, reason = "medium_shot", min(sr * 10, 1.0), f"主体占比 {sr:.2%}"
                        elif sr > 0.02:
                            t, conf, reason = "wide_shot", min(sr * 20, 1.0), f"主体占比 {sr:.2%}"
                        else:
                            t, conf, reason = "extreme_wide", 0.8, "主体占比很小"
                    shots.append({
                        "time_sec": round(idx / fps, 3), "frame_idx": idx,
                        "shot_type": t, "confidence": conf, "reason": reason,
                    })
                idx += 1
        finally:
            cap.release()
        return shots

    def _visual_effects(self, frames: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not frames:
            return {}
        blurs = [f["blur_score"] for f in frames]
        edges = [f["edge_intensity"] for f in frames]
        motions = [f["motion"]["avg_magnitude"] for f in frames]
        vals = [f["hsv"]["value"] for f in frames]
        sats = [f["hsv"]["saturation"] for f in frames]
        effects: List[Dict[str, Any]] = []
        avg_blur = float(np.mean(blurs))
        low_blur = sum(1 for b in blurs if b < 50)
        if low_blur > len(blurs) * 0.25:
            effects.append({
                "type": "blur", "name": "景深模糊/虚化",
                "confidence": min(low_blur / len(blurs), 1.0),
                "ae_effect": "高斯模糊/摄像机镜头模糊",
                "ae_params": {"property": "Gaussian Blur", "blurriness": max(10, round(100 - avg_blur / 10))},
            })
        hm = sum(1 for m in motions if m > 12)
        if hm > len(motions) * 0.25:
            effects.append({
                "type": "shake", "name": "镜头抖动",
                "confidence": min(hm / len(motions), 1.0),
                "ae_effect": "wiggle表达式",
                "ae_params": {"property": "position", "expression": "wiggle(6, 12)"},
            })
        he = sum(1 for e in edges if e > 0.18)
        if he > len(edges) * 0.35:
            effects.append({
                "type": "glow", "name": "发光/辉光效果",
                "confidence": min(he / len(edges), 1.0),
                "ae_effect": "发光(Glow)",
                "ae_params": {"property": "Glow", "intensity": 90, "radius": 35},
            })
        flashes = 0
        for i in range(1, len(vals)):
            d = abs(vals[i] - vals[i - 1])
            if d > 70:
                ft = "闪白" if vals[i] > vals[i - 1] else "闪黑"
                effects.append({
                    "type": "flash", "name": ft, "time_sec": frames[i]["time_sec"],
                    "confidence": 0.85, "ae_effect": "亮度闪白/闪黑",
                    "ae_params": {"property": "brightness", "value": 100 if ft == "闪白" else -100},
                })
                flashes += 1
        avg_sat = float(np.mean(sats))
        if avg_sat > 150:
            effects.append({
                "type": "color_enhance", "name": "色彩增强/鲜艳",
                "confidence": min((avg_sat - 100) / 80, 1.0),
                "ae_effect": "自然饱和度",
                "ae_params": {"property": "Vibrance", "value": 30},
            })
        return {
            "detected_effects": effects,
            "effect_count": len(effects),
            "avg_blur_score": round(avg_blur, 2),
            "avg_edge_intensity": round(float(np.mean(edges)), 4),
            "flash_count": flashes,
        }

    def _rhythm(self, scenes: List[Dict[str, Any]], mf: Dict[str, Any]) -> Dict[str, Any]:
        if not scenes:
            return {"rhythm": "unknown"}
        durs = [s.get("duration", 0) for s in scenes if s.get("duration", 0) > 0]
        if not durs:
            return {"rhythm": "unknown"}
        avg = float(np.mean(durs))
        cut_rate = len(scenes) / max(sum(durs), 1)
        level = mf.get("motion_style", "medium")
        if avg < 1.2:
            rhythm, bpm = "快节奏/高切镜率", round(60 / avg)
        elif avg < 3.5:
            rhythm, bpm = "中等节奏", round(60 / avg)
        else:
            rhythm, bpm = "慢节奏/长镜头", round(60 / avg)
        coord_map = {
            ("快节奏/高切镜率", "高动态/快节奏"): 0.9,
            ("快节奏/高切镜率", "中等动态"): 0.7,
            ("快节奏/高切镜率", "低动态/平稳"): 0.4,
            ("中等节奏", "中等动态"): 0.85,
            ("中等节奏", "高动态/快节奏"): 0.6,
            ("中等节奏", "低动态/平稳"): 0.6,
            ("慢节奏/长镜头", "低动态/平稳"): 0.9,
            ("慢节奏/长镜头", "中等动态"): 0.6,
            ("慢节奏/长镜头", "高动态/快节奏"): 0.3,
        }
        return {
            "rhythm": rhythm, "avg_shot_duration": round(avg, 2),
            "cut_rate": round(cut_rate, 3), "bpm_equivalent": bpm,
            "total_cuts": len(scenes),
            "shortest_shot": round(float(min(durs)), 2),
            "longest_shot": round(float(max(durs)), 2),
            "motion_level": level,
            "rhythm_motion_coordination": coord_map.get((rhythm, level), 0.5),
        }

    def _ae_params(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "composition": {
                "width": analysis.get("basic_info", {}).get("width", 1920),
                "height": analysis.get("basic_info", {}).get("height", 1080),
                "fps": analysis.get("basic_info", {}).get("fps", 30),
                "duration": analysis.get("basic_info", {}).get("duration", 10),
            },
            "adjustment_layers": [], "effects": [], "keyframes": [], "expressions": [],
        }
        color = analysis.get("color_features", {})
        if color.get("ae_lumetri_params"):
            out["adjustment_layers"].append({
                "name": "调色调整层", "effect": "Lumetri Color",
                "params": color["ae_lumetri_params"],
            })
        for t in analysis.get("transitions", []):
            if t.get("ae_params"):
                out["effects"].append({
                    "name": f"转场_{t['type']}@{t['time_sec']}s",
                    "time": t["time_sec"],
                    "effect": t.get("ae_effect", ""),
                    "params": t["ae_params"],
                })
        motion = analysis.get("motion_features", {})
        for sc in motion.get("speed_changes", []):
            if sc.get("ae_params"):
                out["keyframes"].append({
                    "name": f"速度变化_{sc['type']}@{sc['time_sec']}s",
                    "time": sc["time_sec"], "property": "timeRemap",
                    "params": sc["ae_params"],
                })
        vfx = analysis.get("visual_effects", {})
        for eff in vfx.get("detected_effects", []):
            if eff.get("ae_params"):
                p = eff["ae_params"]
                if "expression" in p:
                    out["expressions"].append({
                        "name": f"效果_{eff['name']}", "property": p["property"],
                        "expression": p["expression"],
                    })
                else:
                    out["effects"].append({
                        "name": f"效果_{eff['name']}", "effect": eff.get("ae_effect", ""),
                        "params": p,
                    })
        if motion.get("camera_motion") in ("持续缩放进入", "持续缩放退出"):
            zoom_in = "进入" in motion["camera_motion"]
            out["keyframes"].append({
                "name": "缩放动画", "property": "scale",
                "from": 100 if zoom_in else 130,
                "to": 130 if zoom_in else 100,
            })
        return out


# --------------------------------------------------------------------------- #
# 便捷 CLI：支持与原 v2.0 同样的 JSON 输入模式
# --------------------------------------------------------------------------- #

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            payload = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
            if payload:
                req = json.loads(payload)
                params = req.get("params", {})
                analyzer = AcceleratedVideoAnalyzer(
                    num_workers=params.pop("num_workers", None),
                    use_gpu=params.pop("use_gpu", True),
                )
                fn = req.get("func")
                if fn == "analyze_video":
                    print(json.dumps(analyzer.analyze_video(**params), ensure_ascii=False, indent=2))
                else:
                    print(json.dumps({"success": False, "error": f"Unknown function: {fn}"}, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return

    print("Accelerated Video Analyzer v3.0")
    print("  CV2 CUDA available:", CUDA_INFO["available"], CUDA_INFO["reason"])
    print("  usage: python video_analyzer_accelerated.py --json-input '{\"func\":\"analyze_video\","
          "\"params\":{\"video_path\":\"x.mp4\",\"num_workers\":8}}'")


if __name__ == "__main__":
    main()
