"""
视频质量评估器 — 用 ffprobe + OpenCV 做真实的视频质量检测
==========================================================

取代不存在的 QualityAgent，输出真实可量化的质量分数。
评估维度:
  1. 编码合规性 (H.264/H.265/VP9, 帧率, 分辨率)
  2. 黑场检测 (开头/结尾/中间异常黑场)
  3. 锐度分析 (Laplacian variance)
  4. 亮度/对比度 (直方图统计)
  5. 色彩饱和度 (HSV S通道均值)
  6. 时间戳连续性 (ffprobe pts 检查)
  7. 文件大小/码率合理性

输出格式与 FeedbackExecutor.AdjustmentMapper 兼容:
  {
      "score": 0-100,
      "checks": {
          "visual_quality": {"score": ..., "sharpness": ..., "contrast": ...},
          "color_consistency": {"score": ..., "avg_brightness": ..., "avg_saturation": ...},
          "encoding_health": {"score": ..., "codec": ..., "width": ..., "height": ...},
          "temporal_stability": {"score": ..., "black_frames": ..., "pts_gaps": ...}
      },
      "suggestions": [...]
  }
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ffmpeg/ffprobe 默认路径收口到 core/paths.py（AEK_FFMPEG / AEK_FFPROBE 可覆盖）
try:
    from core.paths import ffmpeg_bin as _paths_ffmpeg
    from core.paths import ffprobe_bin as _paths_ffprobe
except ImportError:
    _paths_ffmpeg = lambda: r"C:\ffmpeg\bin\ffmpeg.exe"
    _paths_ffprobe = lambda: r"C:\ffmpeg\bin\ffprobe.exe"


class VideoQualityAssessor:
    """真实视频质量评估器 — ffprobe + OpenCV 双引擎"""

    def __init__(self, ffmpeg_bin: str = "", ffprobe_bin: str = ""):
        self.ffmpeg_bin = ffmpeg_bin or _paths_ffmpeg()
        self.ffprobe_bin = ffprobe_bin or _paths_ffprobe()
        if not Path(self.ffprobe_bin).exists():
            # 尝试同目录推断
            fdir = Path(self.ffmpeg_bin).parent if self.ffmpeg_bin else Path(_paths_ffmpeg()).parent
            candidate = fdir / "ffprobe.exe"
            if candidate.exists():
                self.ffprobe_bin = str(candidate)
            else:
                # imageio_ffmpeg 通常只带 ffmpeg 不带 ffprobe，保持空
                self.ffprobe_bin = ""

    # ------------------------------------------------------------------
    #  主入口
    # ------------------------------------------------------------------
    def assess(self, video_path: str, reference_path: str = "",
               min_score: float = 60.0) -> dict[str, Any]:
        """评估视频质量，返回结构化报告。

        Args:
            video_path: 待评估视频
            reference_path: 可选参考视频（用于对比）
            min_score: 最低合格分数

        Returns:
            {
                "passed": bool,
                "overall_score": float 0-100,
                "checks": {...},
                "recommendations": [...]
            }
        """
        if not video_path or not Path(video_path).exists():
            return self._error_result(f"视频文件不存在: {video_path}")

        # 1. ffprobe 元数据
        probe = self._ffprobe(video_path)
        if not probe:
            return self._error_result("ffprobe 分析失败")

        # 1.5 检查是否有视频流（空壳/损坏的 MP4 容器可能 nb_streams=0）
        streams = probe.get("streams", []) or []
        vstreams = [s for s in streams if s.get("codec_type") == "video"]
        if not vstreams:
            return self._error_result(
                f"无视频流（文件可能是空壳或损坏）: nb_streams={len(streams)}"
            )

        # 2. OpenCV 抽帧分析
        frame_metrics = self._opencv_analyze(video_path, max_frames=12)

        # 2.5 OpenCV 可用但视频打不开 → 文件损坏，直接判低分
        # （openable=None 表示 OpenCV 本身不可用，属另一情况，不在此处理）
        if frame_metrics.get("openable") is False:
            return self._error_result(
                "OpenCV 无法打开视频（文件损坏或编码不支持）"
            )

        # 2.6 【P3-C】评分梯度保障：无 OpenCV 时 signalstats 兜底实测 + 黑屏/静帧判定
        # 历史缺陷：① 无 OpenCV 时各分项固定 30/30/98 → 总分恒定 59.2；
        # ② 有 OpenCV 时黑屏/静帧视频仍拿中高分，评分无梯度。
        sig = self._signalstats_analyze(
            video_path,
            video_duration=float(probe.get("format", {}).get("duration", 0) or 0),
        )
        if frame_metrics.get("openable") is None and sig.get("valid"):
            frame_metrics["signalstats"] = sig
            frame_metrics["all_black"] = sig.get("yavg", 0.0) < 20.0
        elif frame_metrics.get("openable") is True and frame_metrics.get("frames", 0) > 0:
            # OpenCV 路径: 黑帧占比 >= 80% 视为全黑
            frame_metrics["all_black"] = (
                frame_metrics.get("black_frames", 0) / frame_metrics["frames"] >= 0.8
            )
        frame_metrics["static_video"] = bool(
            sig.get("freeze_ratio", 0.0) >= 0.8
            and float(probe.get("format", {}).get("duration", 0) or 0) >= 2.0
        )

        # 3. 各维度评分
        checks: dict[str, Any] = {}
        suggestions: list[str] = []

        # --- 编码健康度 ---
        enc = self._score_encoding(probe)
        checks["encoding_health"] = enc
        if enc["score"] < 70:
            suggestions.append(f"编码问题: {enc.get('issues', [])}")

        # --- 视觉质量 (锐度+对比度) ---
        vq = self._score_visual_quality(frame_metrics)
        checks["visual_quality"] = vq
        if vq["score"] < 60:
            if vq.get("sharpness", 100) < 30:
                suggestions.append("建议超分辨率或锐化增强")
            if vq.get("contrast", 0.5) < 0.2:
                suggestions.append("建议调色提升对比度")

        # --- 色彩一致性 ---
        cc = self._score_color_consistency(frame_metrics)
        checks["color_consistency"] = cc
        if cc["score"] < 60:
            suggestions.append("建议自动调色校正色彩")

        # --- 时间稳定性 (黑场+PTS) ---
        ts = self._score_temporal_stability(probe, frame_metrics)
        checks["temporal_stability"] = ts
        if ts.get("black_frames", 0) > 0:
            suggestions.append(f"检测到 {ts['black_frames']} 个黑场帧，建议检查")

        # 4. 综合分数 (加权)
        weights = {
            "encoding_health": 0.20,
            "visual_quality": 0.35,
            "color_consistency": 0.20,
            "temporal_stability": 0.25,
        }
        total_weight = sum(weights.values())
        overall = 0.0
        for k, w in weights.items():
            s = checks.get(k, {}).get("score", 50)
            try:
                s = float(s)
            except (TypeError, ValueError):
                s = 50.0
            overall += s * w
        overall = round(overall / total_weight, 1) if total_weight > 0 else 0.0

        # 4.5 【P3-C】黑屏/静帧惩罚：启发式兜底路径必须保证梯度
        if frame_metrics.get("all_black"):
            overall = min(overall, 15.0)
            suggestions.append("画面全黑 (YAVG<20)，判定为无效产出")
        elif frame_metrics.get("static_video"):
            overall = min(overall, 45.0)
            suggestions.append("视频几乎全为静帧，判定为静态内容")

        # 5. 参考视频对比 (可选, 不影响主分数)
        ref_info: dict[str, Any] = {}
        if reference_path and Path(reference_path).exists():
            ref_probe = self._ffprobe(reference_path)
            if ref_probe:
                ref_info = {
                    "reference_duration": ref_probe.get("format", {}).get("duration"),
                    "reference_streams": len(ref_probe.get("streams", [])),
                }

        # 6. recommendations (与 suggestions 同义, 兼容旧调用方)
        recommendations = list(suggestions)

        passed = overall >= min_score

        # 同时返回两套字段:
        #   - score / suggestions         (AdjustmentMapper 期望)
        #   - overall_score / recommendations / passed  (assess 文档承诺)
        return {
            "passed": passed,
            "score": overall,                # 兼容 AdjustmentMapper
            "overall_score": overall,
            "min_score": min_score,
            "checks": checks,
            "suggestions": suggestions,      # 兼容 AdjustmentMapper
            "recommendations": recommendations,
            "reference": ref_info,
        }

    # ------------------------------------------------------------------
    #  内部工具方法
    # ------------------------------------------------------------------
    def _error_result(self, msg: str) -> dict[str, Any]:
        """构造错误返回"""
        return {
            "passed": False,
            "score": 0.0,
            "overall_score": 0.0,
            "checks": {},
            "suggestions": [msg],
            "recommendations": [msg],
            "error": msg,
        }

    def _signalstats_analyze(self, video_path: str, duration_limit: float = 10.0,
                             video_duration: float = 0.0) -> dict[str, float]:
        """OpenCV 不可用时的兜底实测: ffmpeg signalstats(亮度/饱和度) + freezedetect(静帧)

        与 core/evolution/evaluator._measure_video_stats 同源方法。
        注意: signalstats 无 USTD/VSTD 键, 饱和度用 SATAVG。
        返回 {"yavg","ylow","yhigh","satavg","freeze_ratio","valid": bool}
        """
        if not self.ffmpeg_bin or not Path(self.ffmpeg_bin).exists():
            return {"valid": False}
        cmd = [
            self.ffmpeg_bin, "-hide_banner", "-i", video_path,
            "-t", str(duration_limit),
            "-vf", "signalstats,metadata=print,freezedetect=n=0.004:d=1",
            "-f", "null", "-",
        ]
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=120,
            )
        except Exception:
            return {"valid": False}
        out = (r.stderr or "") + (r.stdout or "")
        if not out:
            return {"valid": False}

        vals: dict[str, float] = {}
        cnt = 0
        for key in ("YAVG", "YLOW", "YHIGH", "SATAVG"):
            ms = re.findall(r"lavfi\.signalstats\." + key + r"=(\d+(?:\.\d+)?)", out)
            if key == "YAVG":
                cnt = len(ms)
            vals[key.lower()] = sum(float(x) for x in ms) / len(ms) if ms else 0.0

        # freezedetect 输出 freeze_duration 行；若只有 freeze_start 无 freeze_end
        # (冻结持续到视频结尾)，按 start 到分段末尾计冻结时长
        seg_dur = min(duration_limit, video_duration) if video_duration > 0 else duration_limit
        freeze_total = sum(
            float(x) for x in re.findall(r"freeze_duration:\s*(\d+(?:\.\d+)?)", out)
        )
        starts = [float(x) for x in re.findall(r"freeze_start:\s*(\d+(?:\.\d+)?)", out)]
        n_dur = len(re.findall(r"freeze_duration:\s*(\d+(?:\.\d+)?)", out))
        if starts and n_dur < len(starts):
            # 未闭合的冻结段: 持续到分段末尾
            freeze_total += max(0.0, seg_dur - min(starts))
        freeze_ratio = min(1.0, freeze_total / seg_dur) if seg_dur > 0 else 0.0

        return {
            "yavg": vals.get("yavg", 0.0),
            "ylow": vals.get("ylow", 0.0),
            "yhigh": vals.get("yhigh", 0.0),
            "satavg": vals.get("satavg", 0.0),
            "freeze_ratio": freeze_ratio,
            "valid": cnt > 0,
        }

    def _ffprobe(self, video_path: str) -> dict[str, Any]:
        """调用 ffprobe 获取视频元数据 (JSON)"""
        if not self.ffprobe_bin or not Path(self.ffprobe_bin).exists():
            return {}
        try:
            cmd = [
                self.ffprobe_bin, "-v", "error",
                "-show_entries",
                "format=duration,size,bit_rate,format_name:stream=codec_name,codec_type,width,height,r_frame_rate,avg_frame_rate,nb_frames,pix_fmt",
                "-of", "json", video_path,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=15)
            if r.returncode != 0 or not r.stdout.strip():
                return {}
            return json.loads(r.stdout)
        except Exception as e:
            logger.debug(f"_ffprobe 失败 {video_path}: {e}")
            return {}

    def _opencv_analyze(self, video_path: str, max_frames: int = 12) -> dict[str, Any]:
        """用 OpenCV 抽帧分析: 锐度(Laplacian方差), 亮度, 对比度, 饱和度, 黑场"""
        metrics: dict[str, Any] = {
            "frames": 0, "sharpness_list": [], "brightness_list": [],
            "contrast_list": [], "saturation_list": [], "black_frames": 0,
            # openable: None=OpenCV不可用未尝试, True=打开成功, False=视频打不开(损坏)
            "openable": None,
        }
        try:
            import cv2
            import numpy as np
        except ImportError:
            logger.warning("OpenCV/numpy 不可用, 跳过帧分析")
            return metrics

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"OpenCV 无法打开视频: {video_path}")
            metrics["openable"] = False
            return metrics
        metrics["openable"] = True

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total // max_frames) if total > max_frames else 1

        idx = 0
        while idx < total and metrics["frames"] < max_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                idx += step
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # 锐度: Laplacian 方差
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            sharp = float(lap.var())
            metrics["sharpness_list"].append(sharp)
            # 亮度: 均值 (0-255 → 0-1)
            mean_b = float(gray.mean()) / 255.0
            metrics["brightness_list"].append(mean_b)
            # 对比度: 标准差 (0-255 → 0-1)
            std_b = float(gray.std()) / 255.0
            metrics["contrast_list"].append(std_b)
            # 饱和度: HSV S 通道均值
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            sat = float(hsv[:, :, 1].mean()) / 255.0
            metrics["saturation_list"].append(sat)
            # 黑场: 亮度<10
            if mean_b < 0.04:
                metrics["black_frames"] += 1
            metrics["frames"] += 1
            idx += step

        cap.release()
        return metrics

    # -------- 评分维度 --------
    def _score_encoding(self, probe: dict[str, Any]) -> dict[str, Any]:
        """编码健康度评分"""
        streams = probe.get("streams", []) or []
        vstreams = [s for s in streams if s.get("codec_type") == "video"]
        fmt = probe.get("format", {}) or {}
        if not vstreams:
            return {"score": 20, "issues": ["无视频流"]}

        vs = vstreams[0]
        codec = vs.get("codec_name", "unknown")
        width = int(vs.get("width", 0) or 0)
        height = int(vs.get("height", 0) or 0)
        issues: list[str] = []

        # codec 评分
        codec_score = 100 if codec in ("h264", "hevc", "vp9", "av1") else 60
        if codec not in ("h264", "hevc", "vp9", "av1"):
            issues.append(f"非主流编码: {codec}")

        # 分辨率评分
        if width >= 1920 and height >= 1080:
            res_score = 100
        elif width >= 1280 and height >= 720:
            res_score = 90
        elif width >= 852 and height >= 480:
            res_score = 75
        elif width > 0:
            res_score = 55
            issues.append(f"分辨率偏低: {width}x{height}")
        else:
            res_score = 30
            issues.append("分辨率未知")

        # 帧率
        rfr = vs.get("r_frame_rate", "30/1")
        try:
            num, den = rfr.split("/")
            fps = float(num) / float(den) if float(den) != 0 else 30.0
        except Exception:
            fps = 30.0
        if 24 <= fps <= 60:
            fps_score = 100
        elif fps > 0:
            fps_score = 70
            issues.append(f"帧率异常: {fps}")
        else:
            fps_score = 50
            issues.append("帧率未知")

        # 码率 (bit_rate 来自 format)
        try:
            br = int(fmt.get("bit_rate", 0) or 0)
            if br > 2_000_000:
                br_score = 100
            elif br > 500_000:
                br_score = 80
            elif br > 0:
                br_score = 55
                issues.append(f"码率偏低: {br//1000}kbps")
            else:
                br_score = 60
        except Exception:
            br_score = 60

        score = round(0.35*codec_score + 0.25*res_score + 0.20*fps_score + 0.20*br_score, 1)
        return {
            "score": score, "codec": codec, "width": width, "height": height,
            "fps": fps, "bit_rate": fmt.get("bit_rate"), "issues": issues,
        }

    def _score_visual_quality(self, fm: dict[str, Any]) -> dict[str, Any]:
        """视觉质量: 锐度 + 对比度"""
        # OpenCV 不可用 (openable is None): 优先用 signalstats 兜底实测
        if fm.get("openable") is None:
            ss = fm.get("signalstats") or {}
            if not ss.get("valid"):
                return {
                    "score": 30, "sharpness": 0, "contrast": 0,
                    "inconclusive": True,
                    "warning": "OpenCV unavailable, visual analysis skipped",
                }
            if fm.get("all_black"):
                return {
                    "score": 5.0, "sharpness": 0, "contrast": 0,
                    "black_screen": True, "source": "signalstats",
                }
            # 无 OpenCV 拿不到锐度，用 Y 分布估算对比度，锐度给中性分
            contrast = max(0.0, (ss.get("yhigh", 0.0) - ss.get("ylow", 0.0)) / 255.0)
            if 0.15 <= contrast <= 0.55:
                contrast_score = 90
            elif 0.10 <= contrast < 0.15 or 0.55 < contrast <= 0.75:
                contrast_score = 75
            elif contrast < 0.10:
                contrast_score = 50
            else:
                contrast_score = 60
            score = round(0.6 * 60 + 0.4 * contrast_score, 1)
            return {
                "score": score, "sharpness": 0, "contrast": round(contrast, 3),
                "contrast_score": contrast_score, "source": "signalstats",
            }
        if fm.get("frames", 0) == 0:
            return {"score": 50, "sharpness": 0, "contrast": 0}

        sharp_list = fm["sharpness_list"]
        contrast_list = fm["contrast_list"]
        sharp = sum(sharp_list) / len(sharp_list)
        contrast = sum(contrast_list) / len(contrast_list)

        # 锐度评分: Laplacian 方差, 通常 100-1000 范围
        # <50 极模糊, 50-200 模糊, 200-500 一般, 500+ 清晰
        if sharp >= 500:
            sharp_score = 95
        elif sharp >= 300:
            sharp_score = 82
        elif sharp >= 150:
            sharp_score = 70
        elif sharp >= 80:
            sharp_score = 58
        elif sharp >= 40:
            sharp_score = 45
        else:
            sharp_score = 30

        # 对比度评分: std 0-1, 0.1-0.35 为佳
        if 0.15 <= contrast <= 0.35:
            contrast_score = 90
        elif 0.10 <= contrast < 0.15 or 0.35 < contrast <= 0.45:
            contrast_score = 75
        elif contrast < 0.10:
            contrast_score = 50  # 过于平淡
        else:
            contrast_score = 60  # 过强

        score = round(0.6 * sharp_score + 0.4 * contrast_score, 1)
        return {
            "score": score, "sharpness": round(sharp, 2),
            "contrast": round(contrast, 3),
            "sharpness_score": sharp_score, "contrast_score": contrast_score,
        }

    def _score_color_consistency(self, fm: dict[str, Any]) -> dict[str, Any]:
        """色彩一致性: 亮度稳定性 + 饱和度合理性"""
        # OpenCV 不可用 (openable is None): 优先用 signalstats 兜底实测
        if fm.get("openable") is None:
            ss = fm.get("signalstats") or {}
            if not ss.get("valid"):
                return {
                    "score": 30, "avg_brightness": 0, "avg_saturation": 0,
                    "inconclusive": True,
                    "warning": "OpenCV unavailable, visual analysis skipped",
                }
            if fm.get("all_black"):
                return {
                    "score": 5.0, "avg_brightness": 0, "avg_saturation": 0,
                    "black_screen": True, "source": "signalstats",
                }
            avg_b = ss.get("yavg", 0.0) / 255.0
            avg_s = ss.get("satavg", 0.0) / 255.0
            if 0.25 <= avg_b <= 0.65:
                b_score = 90
            elif 0.15 <= avg_b < 0.25 or 0.65 < avg_b <= 0.80:
                b_score = 70
            elif avg_b < 0.15:
                b_score = 45
            else:
                b_score = 50
            if 0.2 <= avg_s <= 0.6:
                sat_score = 90
            elif 0.1 <= avg_s < 0.2 or 0.6 < avg_s <= 0.8:
                sat_score = 70
            else:
                sat_score = 55
            # 无帧间方差数据，一致性给中性偏高分
            score = round(0.4 * b_score + 0.35 * 80 + 0.25 * sat_score, 1)
            return {
                "score": score, "avg_brightness": round(avg_b, 3),
                "avg_saturation": round(avg_s, 3), "source": "signalstats",
            }
        if fm.get("frames", 0) == 0:
            return {"score": 50, "avg_brightness": 0, "avg_saturation": 0}

        b_list = fm["brightness_list"]
        s_list = fm["saturation_list"]
        avg_b = sum(b_list) / len(b_list)
        avg_s = sum(s_list) / len(s_list)
        # 亮度方差越小越一致
        b_var = sum((b - avg_b) ** 2 for b in b_list) / len(b_list) if b_list else 0

        # 亮度评分: 0.25-0.65 为佳
        if 0.25 <= avg_b <= 0.65:
            b_score = 90
        elif 0.15 <= avg_b < 0.25 or 0.65 < avg_b <= 0.80:
            b_score = 70
        elif avg_b < 0.15:
            b_score = 45  # 过暗
        else:
            b_score = 50  # 过亮

        # 一致性评分: 方差越小越高
        if b_var < 0.005:
            cons_score = 95
        elif b_var < 0.02:
            cons_score = 80
        elif b_var < 0.05:
            cons_score = 65
        else:
            cons_score = 50

        # 饱和度评分: 0.2-0.6 为佳
        if 0.2 <= avg_s <= 0.6:
            sat_score = 90
        elif 0.1 <= avg_s < 0.2 or 0.6 < avg_s <= 0.8:
            sat_score = 70
        else:
            sat_score = 55

        score = round(0.4 * b_score + 0.35 * cons_score + 0.25 * sat_score, 1)
        return {
            "score": score, "avg_brightness": round(avg_b, 3),
            "avg_saturation": round(avg_s, 3), "brightness_variance": round(b_var, 4),
        }

    def _score_temporal_stability(self, probe: dict[str, Any], fm: dict[str, Any]) -> dict[str, Any]:
        """时间稳定性: 黑场 + PTS 连续性"""
        black = fm.get("black_frames", 0)
        # 黑场评分 (signalstats 兜底路径: 全黑视频直接 0 分)
        if fm.get("all_black"):
            bf_score = 0.0
            black = -1  # -1 = 全黑标记 (区别于具体黑帧数)
        elif black == 0:
            bf_score = 100
        elif black <= 1:
            bf_score = 80
        elif black <= 3:
            bf_score = 60
        else:
            bf_score = 35

        # PTS: 检查 duration 一致性 (简化, 用 ffprobe format.duration vs stream.nb_frames/fps)
        pts_gaps = 0
        streams = probe.get("streams", []) or []
        vstreams = [s for s in streams if s.get("codec_type") == "video"]
        if vstreams:
            vs = vstreams[0]
            try:
                fmt_dur = float(probe.get("format", {}).get("duration", 0) or 0)
                rfr = vs.get("r_frame_rate", "0/1")
                num, den = rfr.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 0
                nb = float(vs.get("nb_frames", 0) or 0)
                if fps > 0 and nb > 0:
                    expected = nb / fps
                    if expected > 0 and abs(expected - fmt_dur) > 0.5:
                        pts_gaps = 1
            except Exception:
                pass

        pts_score = 95 if pts_gaps == 0 else 65
        score = round(0.6 * bf_score + 0.4 * pts_score, 1)
        result: dict[str, Any] = {
            "score": score, "black_frames": black, "pts_gaps": pts_gaps,
        }
        if fm.get("all_black"):
            result["black_screen"] = True
            result["source"] = "signalstats"
        # OpenCV 不可用时黑场检测缺失, 标记不确定 (分数保持原逻辑)
        if fm.get("openable") is None and not fm.get("signalstats"):
            result["inconclusive"] = True
            result["warning"] = "OpenCV unavailable, visual analysis skipped"
        return result
