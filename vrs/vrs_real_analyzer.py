#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRS 真分析器 v1.0 - 纯 OpenCV/ffprobe 视频风格特征提取
========================================================

本模块不依赖 LLM，使用 OpenCV 抽帧 + ffprobe 元数据，输出结构化风格特征 JSON，
供 unified_pipeline 的 perceive/analyze/plan 阶段消费。

输出字段（兼容 unified_pipeline._inject_vrs_to_config 与 _run_analyze）：
    - source: "real_opencv_analysis"
    - success: bool
    - video_path: str
    - basic_info: {width, height, fps, duration, total_frames, codec}
    - color_palette: {
        avg_brightness: float [0,1],
        contrast: float [0,1],
        saturation: float [0,1],
        hue_distribution: list[float] (12 bins, 归一化),
        dominant_colors: list[{hex, ratio, rgb}] (前 3 主色),
        temperature: str ("warm" | "cool" | "neutral"),
      }
    - rhythm: {
        shot_count: int,
        scene_cuts: list[float] (秒),
        avg_shot_duration: float (秒),
        tempo: str ("fast" | "medium" | "slow"),
        frame_diff_mean: float [0,1],
      }
    - motion: {
        intensity: float [0,1],
        direction_distribution: list[float] (8 bins, 归一化),
        dominant_direction: str,
      }
    - transitions: list[{time, type, confidence}]
    - effects: list[{effect_name, category, intensity, confidence}]  (兼容字段)
    - color_grade: str  (兼容字段，如 "warm_high_contrast")
    - style: {name: str, tags: list[str]}  (兼容字段)
    - style_tags: list[str]
    - confidence: float [0,1]
    - errors: list[str]  (子分析降级记录)

降级策略：每个子分析（color/rhythm/motion/transitions）独立 try/except，
任一失败记录到 errors 但不中断整体；最终 confidence 按完成度折算。
"""
from __future__ import annotations

import asyncio
import json
import math
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from loguru import logger


# 默认 ffprobe 路径（Windows 常见路径 + PATH 兜底）
_DEFAULT_FFPROBE_CANDIDATES = [
    "ffprobe",
    r"C:\ffmpeg\bin\ffprobe.exe",
    "/usr/bin/ffprobe",
    "/opt/homebrew/bin/ffprobe",
]


def _resolve_ffprobe() -> str:
    """从候选路径找到可用的 ffprobe。"""
    for cand in _DEFAULT_FFPROBE_CANDIDATES:
        try:
            r = subprocess.run(
                [cand, "-version"],
                capture_output=True, text=True, timeout=5,
                encoding='utf-8', errors='replace',
            )
            if r.returncode == 0:
                return cand
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    return "ffprobe"  # 兜底，让后续报错自然抛出


class VRSRealAnalyzer:
    """真 VRS 分析器 - OpenCV 抽帧 + ffprobe 元数据，输出结构化风格特征。

    不依赖 LLM 网关，确保稳定可用。
    """

    VERSION: str = "1.1"

    def __init__(
        self,
        num_frames: int = 72,
        ffprobe_path: Optional[str] = None,
        scene_diff_threshold: float = 0.12,
    ) -> None:
        """
        Args:
            num_frames: 抽帧数量 (8-120, 默认 72)。
                        旧版默认 18 太稀疏，无法识别踩点节奏；
                        v1.1 提升到 72 帧，对 60s 视频约每 0.8s 一帧，能覆盖踩点切换。
            ffprobe_path: ffprobe 可执行路径，None 则自动解析
            scene_diff_threshold: 场景切换帧差分阈值 (0-1)。
                                  旧版默认 0.30 太严，导致 26/28 GT 样本 shot_count<5；
                                  v1.1 降到 0.12，能识别轻度切换。
        """
        self.num_frames = max(8, min(120, int(num_frames)))
        self.ffprobe_path = ffprobe_path or _resolve_ffprobe()
        self.scene_diff_threshold = float(scene_diff_threshold)
        self._logger = logger.bind(module="VRS.RealAnalyzer")

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    async def analyze(self, video_path: str) -> Dict[str, Any]:
        """分析视频，输出结构化风格特征 JSON。

        Args:
            video_path: 视频文件路径

        Returns:
            见模块文档字符串的输出字段说明。失败时返回 success=False 但不抛异常。
        """
        video_path = str(video_path)
        if not Path(video_path).exists():
            return {
                "success": False,
                "source": "real_opencv_analysis",
                "error": f"video not found: {video_path}",
                "video_path": video_path,
            }

        self._logger.info(f"VRSRealAnalyzer 开始分析: {video_path} (frames={self.num_frames})")
        errors: List[str] = []
        result: Dict[str, Any] = {
            "source": "real_opencv_analysis",
            "success": True,
            "video_path": video_path,
            "analyzer_version": self.VERSION,
            "errors": errors,
        }

        # 1. ffprobe 元数据
        basic_info = await self._probe_video(video_path, errors)
        result["basic_info"] = basic_info

        # 2. OpenCV 抽帧
        frames, frame_times = await self._sample_frames(video_path, basic_info, errors)
        if not frames:
            result["success"] = False
            result["error"] = "OpenCV 抽帧失败，无法继续分析"
            result["confidence"] = 0.0
            self._logger.error("OpenCV 抽帧失败")
            return result

        self._logger.info(f"抽帧成功: {len(frames)} 帧")

        # 3. 色彩特征
        try:
            color_palette = self._analyze_color(frames)
            result["color_palette"] = color_palette
        except Exception as e:
            errors.append(f"color_palette: {e}")
            self._logger.warning(f"色彩分析失败: {e}")
            color_palette = {}

        # 4. 节奏特征（需要帧间差分）
        try:
            rhythm, frame_diffs = self._analyze_rhythm(frames, frame_times, basic_info)
            result["rhythm"] = rhythm
        except Exception as e:
            errors.append(f"rhythm: {e}")
            self._logger.warning(f"节奏分析失败: {e}")
            rhythm = {}
            frame_diffs = []

        # 5. 运动特征
        try:
            motion = self._analyze_motion(frames)
            result["motion"] = motion
        except Exception as e:
            errors.append(f"motion: {e}")
            self._logger.warning(f"运动分析失败: {e}")
            motion = {}

        # 6. 转场特征
        try:
            transitions = self._detect_transitions(
                frames, frame_times, frame_diffs, basic_info
            )
            result["transitions"] = transitions
        except Exception as e:
            errors.append(f"transitions: {e}")
            self._logger.warning(f"转场分析失败: {e}")
            transitions = []

        # 7. 风格分类 + 兼容字段
        style_tags = self._classify_style(color_palette, rhythm, motion, transitions)
        result["style_tags"] = style_tags
        result["effects"] = self._build_effects_list(color_palette, motion, transitions)
        result["color_grade"] = self._build_color_grade(color_palette)
        result["style"] = self._build_style(style_tags)

        # 8. 置信度（按完成度折算）
        completed = sum(1 for k in ("color_palette", "rhythm", "motion", "transitions")
                        if result.get(k))
        result["confidence"] = round(0.5 + 0.125 * completed, 3)

        self._logger.info(
            f"VRSRealAnalyzer 完成: confidence={result['confidence']}, "
            f"tags={style_tags}, errors={len(errors)}"
        )
        return result

    # ------------------------------------------------------------------
    # ffprobe 元数据
    # ------------------------------------------------------------------

    async def _probe_video(self, video_path: str, errors: List[str]) -> Dict[str, Any]:
        """用 ffprobe 提取视频基本信息。"""
        try:
            cmd = [
                self.ffprobe_path, "-v", "error",
                "-print_format", "json",
                "-show_format", "-show_streams",
                video_path,
            ]
            proc = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=15,
                encoding='utf-8', errors='replace',
            )
            if proc.returncode != 0:
                errors.append(f"ffprobe rc={proc.returncode}: {proc.stderr[:200]}")
                return {}
            info = json.loads(proc.stdout)
            fmt = info.get("format", {})
            duration = float(fmt.get("duration", 0))
            for s in info.get("streams", []):
                if s.get("codec_type") == "video":
                    fps_num, fps_den = s.get("r_frame_rate", "0/1").split("/")
                    fps = float(fps_num) / max(float(fps_den), 1e-6)
                    return {
                        "width": int(s.get("width", 0)),
                        "height": int(s.get("height", 0)),
                        "fps": round(fps, 3),
                        "duration": round(duration, 3),
                        "total_frames": int(s.get("nb_frames", 0) or round(duration * fps)),
                        "codec": s.get("codec_name", ""),
                    }
            errors.append("ffprobe: no video stream found")
        except Exception as e:
            errors.append(f"ffprobe exception: {e}")
            self._logger.warning(f"ffprobe 失败: {e}")
        return {}

    # ------------------------------------------------------------------
    # OpenCV 抽帧
    # ------------------------------------------------------------------

    async def _sample_frames(
        self,
        video_path: str,
        basic_info: Dict[str, Any],
        errors: List[str],
    ) -> Tuple[List[np.ndarray], List[float]]:
        """均匀采样 N 帧，返回 (frames, frame_times_sec)。"""
        def _do_sample() -> Tuple[List[np.ndarray], List[float]]:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                errors.append("OpenCV: VideoCapture.open failed")
                return [], []
            try:
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS) or basic_info.get("fps", 30.0)
                if total <= 0:
                    total = max(self.num_frames, int(basic_info.get("total_frames", 0)))

                # 均匀采样位置（避开首尾各 5%）
                if total > self.num_frames * 2:
                    start = max(1, int(total * 0.05))
                    end = max(start + 1, int(total * 0.95))
                    positions = np.linspace(start, end, self.num_frames).astype(int)
                else:
                    positions = np.linspace(0, max(total - 1, 0), self.num_frames).astype(int)

                frames: List[np.ndarray] = []
                times: List[float] = []
                for pos in positions:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(pos))
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        continue
                    # 缩放到 480p 宽度以内，加速分析
                    h, w = frame.shape[:2]
                    if w > 480:
                        scale = 480.0 / w
                        frame = cv2.resize(
                            frame, (480, int(h * scale)),
                            interpolation=cv2.INTER_AREA,
                        )
                    frames.append(frame)
                    times.append(round(float(pos) / max(fps, 1e-6), 3))
                return frames, times
            finally:
                cap.release()

        return await asyncio.to_thread(_do_sample)

    # ------------------------------------------------------------------
    # 色彩分析
    # ------------------------------------------------------------------

    def _analyze_color(self, frames: List[np.ndarray]) -> Dict[str, Any]:
        """色彩特征：亮度/对比度/饱和度/色相分布/主色调。"""
        if not frames:
            return {}

        brightness_vals: List[float] = []
        contrast_vals: List[float] = []
        sat_vals: List[float] = []
        hue_hist = np.zeros(12, dtype=np.float64)
        all_pixels: List[np.ndarray] = []

        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_vals.append(float(gray.mean()) / 255.0)
            contrast_vals.append(float(gray.std()) / 255.0)

            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            sat_vals.append(float(hsv[:, :, 1].mean()) / 255.0)
            # 色相直方图（OpenCV H 范围 0-179，映射到 12 bin）
            h_channel = hsv[:, :, 0].flatten()
            hist, _ = np.histogram(h_channel, bins=12, range=(0, 180))
            hue_hist += hist

            # 收集像素用于主色调聚类（每帧采样 200 像素）
            flat = frame.reshape(-1, 3)
            idx = np.random.choice(flat.shape[0], size=min(200, flat.shape[0]), replace=False)
            all_pixels.append(flat[idx])

        avg_brightness = float(np.mean(brightness_vals))
        contrast = float(np.mean(contrast_vals))
        saturation = float(np.mean(sat_vals))

        # 色相分布归一化
        hue_total = float(hue_hist.sum()) or 1.0
        hue_distribution = [round(float(h) / hue_total, 4) for h in hue_hist]

        # 主色调（k-means，k=3）
        dominant_colors = self._kmeans_dominant_colors(np.vstack(all_pixels), k=3)

        # 色温判断：暖色（红/橙/黄 = bin 0-3）vs 冷色（蓝/青 = bin 7-9）
        warm_ratio = sum(hue_distribution[0:4])
        cool_ratio = sum(hue_distribution[6:10])
        if warm_ratio > cool_ratio + 0.1:
            temperature = "warm"
        elif cool_ratio > warm_ratio + 0.1:
            temperature = "cool"
        else:
            temperature = "neutral"

        return {
            "avg_brightness": round(avg_brightness, 4),
            "contrast": round(contrast, 4),
            "saturation": round(saturation, 4),
            "hue_distribution": hue_distribution,
            "dominant_colors": dominant_colors,
            "temperature": temperature,
            "warm_ratio": round(warm_ratio, 4),
            "cool_ratio": round(cool_ratio, 4),
        }

    def _kmeans_dominant_colors(
        self, pixels: np.ndarray, k: int = 3
    ) -> List[Dict[str, Any]]:
        """对像素做 k-means 聚类，返回前 k 个主色。"""
        pixels = np.float32(pixels)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
        try:
            _, labels, centers = cv2.kmeans(
                pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS
            )
        except cv2.error:
            return []

        total = len(labels) or 1
        result: List[Dict[str, Any]] = []
        for i, center in enumerate(centers):
            ratio = float(np.sum(labels == i)) / total
            b, g, r = int(center[0]), int(center[1]), int(center[2])
            hex_color = f"#{r:02X}{g:02X}{b:02X}"
            result.append({
                "hex": hex_color,
                "rgb": [r, g, b],
                "ratio": round(ratio, 4),
            })
        result.sort(key=lambda x: x["ratio"], reverse=True)
        return result

    # ------------------------------------------------------------------
    # 节奏分析
    # ------------------------------------------------------------------

    def _analyze_rhythm(
        self,
        frames: List[np.ndarray],
        frame_times: List[float],
        basic_info: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[float]]:
        """节奏特征：场景切换点、平均镜头时长、节奏快慢。

        Returns:
            (rhythm_dict, frame_diffs) - frame_diffs[i] = frame[i+1]-frame[i] 的归一化差分
        """
        if len(frames) < 2:
            return {
                "shot_count": 0,
                "scene_cuts": [],
                "avg_shot_duration": float(basic_info.get("duration", 0)),
                "tempo": "unknown",
                "frame_diff_mean": 0.0,
            }, []

        # 帧间归一化差分（灰度 MSE / 255^2）
        frame_diffs: List[float] = []
        for i in range(len(frames) - 1):
            g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
            diff = np.mean((g1.astype(np.float64) - g2.astype(np.float64)) ** 2)
            frame_diffs.append(float(diff) / (255.0 ** 2))

        # 场景切换点：差分超过阈值的位置
        scene_cuts: List[float] = []
        for i, d in enumerate(frame_diffs):
            if d > self.scene_diff_threshold:
                # 切换时间取相邻两帧的中点
                t = (frame_times[i] + frame_times[i + 1]) / 2.0
                scene_cuts.append(round(t, 3))

        shot_count = len(scene_cuts)
        duration = float(basic_info.get("duration", 0)) or max(frame_times[-1], 1e-6)
        avg_shot_duration = duration / max(shot_count + 1, 1)

        if avg_shot_duration < 1.5:
            tempo = "fast"
        elif avg_shot_duration < 4.0:
            tempo = "medium"
        else:
            tempo = "slow"

        # v1.1 兜底: 当 shot_count 因阈值失败时，用帧间差分均值兜底判断节奏。
        # 26/28 GT 样本因抽帧太稀疏+阈值过严导致 shot_count<5，tempo 全部误判为 slow。
        # frame_diff_mean 反映相邻帧的视觉变化幅度，能间接反映踩点节奏。
        frame_diff_mean = float(np.mean(frame_diffs)) if frame_diffs else 0.0
        if shot_count == 0:
            # 无显式切换点时，用帧间差分均值兜底
            # 经验阈值: >0.05 视为快节奏（踩点/快切），>0.02 视为中节奏
            if frame_diff_mean > 0.05:
                tempo = "fast"
            elif frame_diff_mean > 0.02:
                tempo = "medium"
            # 否则保持 slow

        rhythm = {
            "shot_count": shot_count,
            "scene_cuts": scene_cuts,
            "avg_shot_duration": round(avg_shot_duration, 3),
            "tempo": tempo,
            "frame_diff_mean": round(float(np.mean(frame_diffs)) if frame_diffs else 0.0, 4),
            "frame_diff_max": round(float(np.max(frame_diffs)) if frame_diffs else 0.0, 4),
        }
        return rhythm, frame_diffs

    # ------------------------------------------------------------------
    # 运动分析
    # ------------------------------------------------------------------

    def _analyze_motion(self, frames: List[np.ndarray]) -> Dict[str, Any]:
        """运动特征：运动强度 + 方向分布（光流）。"""
        if len(frames) < 2:
            return {"intensity": 0.0, "direction_distribution": [], "dominant_direction": "static"}

        magnitudes: List[float] = []
        direction_bins = np.zeros(8, dtype=np.float64)  # 8 个方向 bin

        for i in range(len(frames) - 1):
            g1 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            g2 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
            # Farneback 光流
            flow = cv2.calcOpticalFlowFarneback(
                g1, g2, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
            )
            fx = flow[:, :, 0]
            fy = flow[:, :, 1]
            mag = np.sqrt(fx * fx + fy * fy)
            magnitudes.append(float(mag.mean()))

            # 方向直方图（8 bin，每 bin 45 度）
            angle = np.arctan2(fy, fx)
            # angle 范围 -pi~pi，映射到 0~2pi 再分 8 bin
            angle_norm = (angle + np.pi) / (2 * np.pi)
            hist, _ = np.histogram(angle_norm, bins=8, range=(0, 1), weights=mag)
            direction_bins += hist

        intensity = float(np.mean(magnitudes)) / 20.0  # 经验归一化（典型 mag 0-20）
        intensity = min(max(intensity, 0.0), 1.0)

        total_dir = float(direction_bins.sum()) or 1.0
        direction_distribution = [round(float(b) / total_dir, 4) for b in direction_bins]

        dir_names = ["→", "↘", "↓", "↙", "←", "↖", "↑", "↗"]
        dom_idx = int(np.argmax(direction_bins))
        dominant_direction = dir_names[dom_idx] if magnitudes and max(magnitudes) > 0.5 else "static"

        return {
            "intensity": round(intensity, 4),
            "direction_distribution": direction_distribution,
            "dominant_direction": dominant_direction,
            "magnitude_mean": round(float(np.mean(magnitudes)), 4),
            "magnitude_max": round(float(np.max(magnitudes)), 4),
        }

    # ------------------------------------------------------------------
    # 转场检测
    # ------------------------------------------------------------------

    def _detect_transitions(
        self,
        frames: List[np.ndarray],
        frame_times: List[float],
        frame_diffs: List[float],
        basic_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """转场检测：硬切/淡入淡出/溶解。

        判定逻辑：
        - 硬切：单帧差分 > 0.5，且前后邻帧差分 < 0.15
        - 淡入淡出：连续 3+ 帧亮度单调变化，且差分中等 (0.1-0.3)
        - 溶解：连续 3+ 帧差分中等 (0.15-0.4)，亮度非单调
        """
        if len(frames) < 3 or not frame_diffs:
            return []

        transitions: List[Dict[str, Any]] = []
        # 亮度序列
        brightness = [
            float(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).mean()) / 255.0
            for f in frames
        ]

        used_indices: set = set()
        for i, d in enumerate(frame_diffs):
            if i in used_indices:
                continue
            t = (frame_times[i] + frame_times[i + 1]) / 2.0

            # 硬切
            if d > 0.5:
                prev_d = frame_diffs[i - 1] if i > 0 else 0.0
                next_d = frame_diffs[i + 1] if i + 1 < len(frame_diffs) else 0.0
                if prev_d < 0.15 and next_d < 0.15:
                    transitions.append({
                        "time": round(t, 3),
                        "type": "hard_cut",
                        "confidence": round(min(d / 0.8, 1.0), 3),
                        "frame_diff": round(d, 4),
                    })
                    used_indices.add(i)
                    continue

            # 淡入淡出 / 溶解：连续 3 帧中等差分
            if 0.10 <= d <= 0.40 and i + 2 < len(frame_diffs):
                d2 = frame_diffs[i + 1]
                d3 = frame_diffs[i + 2]
                if 0.10 <= d2 <= 0.40 and 0.10 <= d3 <= 0.40:
                    # 检查亮度单调性
                    b_seq = brightness[i:i + 4]
                    diffs_b = [b_seq[j + 1] - b_seq[j] for j in range(len(b_seq) - 1)]
                    all_inc = all(x > 0.005 for x in diffs_b)
                    all_dec = all(x < -0.005 for x in diffs_b)
                    avg_d = (d + d2 + d3) / 3.0
                    if all_inc or all_dec:
                        ttype = "fade"
                        conf = 0.7 + min(avg_d, 0.3) / 0.3 * 0.2
                    else:
                        ttype = "dissolve"
                        conf = 0.6 + min(avg_d, 0.4) / 0.4 * 0.3
                    transitions.append({
                        "time": round(t, 3),
                        "type": ttype,
                        "confidence": round(conf, 3),
                        "frame_diff": round(avg_d, 4),
                        "span_frames": 3,
                    })
                    used_indices.update([i, i + 1, i + 2])

        transitions.sort(key=lambda x: x["time"])
        return transitions

    # ------------------------------------------------------------------
    # 风格分类
    # ------------------------------------------------------------------

    def _classify_style(
        self,
        color: Dict[str, Any],
        rhythm: Dict[str, Any],
        motion: Dict[str, Any],
        transitions: List[Dict[str, Any]],
    ) -> List[str]:
        """基于特征推断风格标签。"""
        tags: List[str] = []

        # 色彩维度
        brightness = color.get("avg_brightness", 0.5)
        contrast = color.get("contrast", 0.2)
        saturation = color.get("saturation", 0.4)
        temperature = color.get("temperature", "neutral")

        if brightness >= 0.6:
            tags.append("bright")
        elif brightness <= 0.3:
            tags.append("dark")

        if contrast >= 0.30:
            tags.append("high_contrast")
        elif contrast <= 0.15:
            tags.append("low_contrast")

        if saturation >= 0.50:
            tags.append("vibrant")
        elif saturation <= 0.20:
            tags.append("desaturated")

        if temperature == "warm":
            tags.append("warm_tone")
        elif temperature == "cool":
            tags.append("cool_tone")

        # 节奏维度
        tempo = rhythm.get("tempo", "unknown")
        if tempo == "fast":
            tags.append("fast_paced")
        elif tempo == "slow":
            tags.append("slow_paced")

        shot_count = rhythm.get("shot_count", 0)
        if shot_count >= 5:
            tags.append("multicut")

        # 运动维度
        motion_intensity = motion.get("intensity", 0.0)
        if motion_intensity >= 0.30:
            tags.append("high_motion")
        elif motion_intensity <= 0.05:
            tags.append("static")

        dom_dir = motion.get("dominant_direction", "static")
        if dom_dir not in ("static", "→"):
            tags.append(f"motion_{dom_dir}")

        # 转场维度
        if transitions:
            types = {t.get("type") for t in transitions}
            if "hard_cut" in types:
                tags.append("has_hard_cuts")
            if "fade" in types:
                tags.append("has_fades")
            if "dissolve" in types:
                tags.append("has_dissolves")

        return tags

    # ------------------------------------------------------------------
    # 兼容字段构造
    # ------------------------------------------------------------------

    def _build_effects_list(
        self,
        color: Dict[str, Any],
        motion: Dict[str, Any],
        transitions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构造 effects 列表（兼容 unified_pipeline._run_analyze 读取）。"""
        effects: List[Dict[str, Any]] = []

        # 转场效果
        for tr in transitions:
            effects.append({
                "effect_name": f"transition_{tr.get('type', 'unknown')}",
                "category": "transition",
                "intensity": tr.get("frame_diff", 0.0),
                "confidence": tr.get("confidence", 0.5),
                "time": tr.get("time"),
            })

        # 调色效果
        temperature = color.get("temperature", "neutral")
        if temperature != "neutral":
            effects.append({
                "effect_name": f"color_grade_{temperature}",
                "category": "color",
                "intensity": color.get("warm_ratio" if temperature == "warm" else "cool_ratio", 0.0),
                "confidence": 0.7,
            })

        saturation = color.get("saturation", 0.0)
        if saturation >= 0.50:
            effects.append({
                "effect_name": "saturation_boost",
                "category": "color",
                "intensity": saturation,
                "confidence": 0.6,
            })

        contrast = color.get("contrast", 0.0)
        if contrast >= 0.30:
            effects.append({
                "effect_name": "high_contrast_grade",
                "category": "color",
                "intensity": contrast,
                "confidence": 0.6,
            })

        # 运动效果
        motion_intensity = motion.get("intensity", 0.0)
        if motion_intensity >= 0.30:
            effects.append({
                "effect_name": "motion_energy",
                "category": "motion",
                "intensity": motion_intensity,
                "confidence": 0.7,
            })

        return effects

    def _build_color_grade(self, color: Dict[str, Any]) -> str:
        """构造 color_grade 字符串标签（兼容 _run_analyze 读取）。"""
        if not color:
            return ""
        temp = color.get("temperature", "neutral")
        contrast = color.get("contrast", 0.0)
        sat = color.get("saturation", 0.0)

        parts: List[str] = []
        if temp != "neutral":
            parts.append(temp)
        if sat >= 0.50:
            parts.append("saturated")
        elif sat <= 0.20:
            parts.append("desaturated")
        if contrast >= 0.30:
            parts.append("high_contrast")
        elif contrast <= 0.15:
            parts.append("low_contrast")
        return "_".join(parts) if parts else "neutral"

    def _build_style(self, style_tags: List[str]) -> Dict[str, Any]:
        """构造 style 字典（兼容 _inject_vrs_to_config 读取 style.name）。"""
        # 选一个主风格名
        if "fast_paced" in style_tags and "high_contrast" in style_tags:
            name = "action_cyber"
        elif "slow_paced" in style_tags:
            name = "cinematic_slow"
        elif "vibrant" in style_tags:
            name = "vibrant_pop"
        elif "dark" in style_tags:
            name = "moody_dark"
        else:
            name = "general"

        return {
            "name": name,
            "tags": style_tags,
        }


# =============================================================================
# CLI 入口（可独立运行验证）
# =============================================================================

async def _cli(video_path: str, num_frames: int = 18) -> None:
    analyzer = VRSRealAnalyzer(num_frames=num_frames)
    result = await analyzer.analyze(video_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VRS Real Analyzer (pure OpenCV/ffprobe)")
    parser.add_argument("video", help="video file path")
    parser.add_argument("--frames", type=int, default=18, help="sample frames (8-32)")
    args = parser.parse_args()
    asyncio.run(_cli(args.video, num_frames=args.frames))
