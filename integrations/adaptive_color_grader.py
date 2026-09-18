"""逐镜头自适应调色引擎 — 基于 ffmpeg signalstats 色彩分析，智能匹配调色风格。

核心能力：
1. analyze_shot_color()  — ffmpeg signalstats 提取亮度/色度/饱和度
2. select_best_style()   — 安全范围匹配打分，选出最优调色风格
3. compute_adaptive_params() — 冲突修正（暗场景不叠高饱和、冷色不叠暖色等）
4. build_per_shot_filter() — 生成逐镜头 ffmpeg filter graph（trim→grade→concat）
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ffmpeg 路径（项目约定）
_FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
_FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"


# ============================================================================
#  调色风格定义
# ============================================================================

@dataclass
class GradingStyle:
    """一种调色风格的完整参数。"""
    name: str
    saturation: float = 1.0        # hue=s=
    contrast: float = 1.0          # eq=contrast=
    brightness: float = 0.0        # eq=brightness=
    colorbalance: str = ""         # colorbalance= 参数串
    temperature: float = 0.0       # 色温偏移 (-0.1~0.1, 正=暖, 负=冷)
    gamma: float = 1.0             # eq=gamma=
    suitable_for: dict[str, Any] = field(default_factory=dict)
    # 适用条件: brightness_range, motion_range, color_temp_hint


# 7 种调色风格
GRADING_STYLES: dict[str, GradingStyle] = {
    "cinematic_warm": GradingStyle(
        name="cinematic_warm",
        saturation=1.15, contrast=1.05, brightness=0.01,
        colorbalance="rs=0.03:gs=0.01:bs=-0.02:rh=0.04:gh=0.02:bh=-0.03",
        temperature=0.04,
        suitable_for={"brightness_range": (0.3, 0.8), "mood": ["triumph", "nostalgia"]},
    ),
    "cinematic_cool": GradingStyle(
        name="cinematic_cool",
        saturation=1.10, contrast=1.05, brightness=0.0,
        colorbalance="rs=-0.03:gs=0.01:bs=0.04:rh=-0.02:gh=0.01:bh=0.03",
        temperature=-0.04,
        suitable_for={"brightness_range": (0.2, 0.7), "mood": ["tension", "melancholy"]},
    ),
    "desaturated": GradingStyle(
        name="desaturated",
        saturation=0.85, contrast=1.10, brightness=-0.02,
        colorbalance="rs=0.01:gs=0.01:bs=0.01",
        temperature=0.0,
        suitable_for={"brightness_range": (0.1, 0.5), "mood": ["grief", "horror"]},
    ),
    "high_contrast": GradingStyle(
        name="high_contrast",
        saturation=1.20, contrast=1.15, brightness=0.0,
        colorbalance="rs=0.02:gs=-0.01:bs=0.02:rh=0.03:gh=0.0:bh=-0.02",
        temperature=0.02,
        suitable_for={"brightness_range": (0.4, 0.9), "mood": ["rage", "triumph"]},
    ),
    "vintage_fade": GradingStyle(
        name="vintage_fade",
        saturation=0.90, contrast=0.95, brightness=0.03,
        colorbalance="rs=0.05:gs=0.03:bs=-0.02:rh=0.06:gh=0.04:bh=0.0",
        temperature=0.05,
        suitable_for={"brightness_range": (0.3, 0.7), "mood": ["nostalgia", "serenity"]},
    ),
    "neon_glow": GradingStyle(
        name="neon_glow",
        saturation=1.30, contrast=1.10, brightness=0.02,
        colorbalance="rs=-0.02:gs=0.02:bs=0.05:rh=0.03:gh=-0.01:bh=0.04",
        temperature=-0.03,
        suitable_for={"brightness_range": (0.1, 0.5), "mood": ["tension", "rage"]},
    ),
    "natural": GradingStyle(
        name="natural",
        saturation=1.05, contrast=1.02, brightness=0.0,
        colorbalance="rs=0.01:gs=0.01:bs=0.01",
        temperature=0.0,
        suitable_for={"brightness_range": (0.3, 0.7), "mood": ["serenity", "nostalgia"]},
    ),
}


# ============================================================================
#  色彩冲突规则
# ============================================================================

# 冲突规则：(条件, 禁止的风格)
# 条件键: src_dark (亮度<0.25), src_bright (亮度>0.65),
#         src_cool (色温<0), src_warm (色温>0),
#         src_high_sat (饱和度>140), src_low_sat (饱和度<100)
CONFLICT_RULES: list[dict[str, Any]] = [
    # 暗场景不用高饱和（会噪点爆炸）
    {"condition": "src_dark", "penalize": ["high_contrast", "neon_glow"], "weight": 0.3},
    # 冷色原片不叠暖色滤镜（色彩脏）
    {"condition": "src_cool", "penalize": ["cinematic_warm", "vintage_fade"], "weight": 0.25},
    # 暖色原片不叠冷色滤镜
    {"condition": "src_warm", "penalize": ["cinematic_cool", "neon_glow"], "weight": 0.25},
    # 高饱和原片不再加高饱和（过饱和）
    {"condition": "src_high_sat", "penalize": ["high_contrast", "neon_glow"], "weight": 0.2},
    # 低饱和场景不用去饱和风格
    {"condition": "src_low_sat", "penalize": ["desaturated", "vintage_fade"], "weight": 0.15},
    # 极亮场景不用高亮度提升
    {"condition": "src_bright", "penalize": ["vintage_fade"], "weight": 0.1},
]


# ============================================================================
#  镜头色彩分析数据结构
# ============================================================================

@dataclass
class ShotColorInfo:
    """单个镜头的色彩分析结果。"""
    shot_index: int
    start_time: float
    duration: float
    yavg: float = 0.0           # 亮度均值 (0~255)
    uavg: float = 0.0           # U 色度均值
    vavg: float = 0.0           # V 色度均值
    saturation: float = 0.0     # 估算饱和度
    color_temp_hint: float = 0.0  # 色温提示 (-1~1, 负=冷, 正=暖)
    motion: float = 0.0         # 运动强度

    @property
    def is_dark(self) -> bool:
        return self.yavg < 64  # ~0.25 * 255

    @property
    def is_bright(self) -> bool:
        return self.yavg > 166  # ~0.65 * 255

    @property
    def is_cool(self) -> bool:
        return self.color_temp_hint < -0.1

    @property
    def is_warm(self) -> bool:
        return self.color_temp_hint > 0.1

    @property
    def is_high_sat(self) -> bool:
        return self.saturation > 140

    @property
    def is_low_sat(self) -> bool:
        return self.saturation < 100


# ============================================================================
#  AdaptiveColorGrader 主类
# ============================================================================

class AdaptiveColorGrader:
    """逐镜头自适应调色引擎。

    用法：
        grader = AdaptiveColorGrader()
        # 分析每个镜头的色彩特征
        shots = grader.analyze_shots(shot_paths, cut_times)
        # 为每个镜头选择最佳调色风格并计算参数
        grades = grader.compute_grading_plan(shots)
        # 生成 ffmpeg filter graph
        vf = grader.build_per_shot_filter(grades, total_duration)
    """

    def __init__(self, ffmpeg_path: str = _FFMPEG, ffprobe_path: str = _FFPROBE):
        self._ffmpeg = ffmpeg_path
        self._ffprobe = ffprobe_path

    # ------------------------------------------------------------------
    #  1. 色彩分析
    # ------------------------------------------------------------------

    def analyze_shot_color(self, shot_path: str, shot_index: int = 0,
                           start_time: float = 0.0, duration: float = 0.0) -> ShotColorInfo:
        """用 ffmpeg signalstats 分析单个镜头的色彩特征。"""
        info = ShotColorInfo(shot_index=shot_index, start_time=start_time, duration=duration)
        if not os.path.exists(shot_path):
            logger.warning(f"镜头文件不存在: {shot_path}")
            return info
        try:
            cmd = [self._ffmpeg, "-ss", f"{start_time:.3f}", "-i", shot_path,
                   "-vframes", "3", "-vf", "signalstats,metadata=print",
                   "-f", "null", "-"]
            r = subprocess.run(cmd, capture_output=True,
                               encoding="utf-8", errors="ignore", timeout=30)
            # 提取 YAVG / UAVG / VAVG
            yvals = [float(v) for v in re.findall(r'YAVG=(\d+(?:\.\d+)?)', r.stderr)]
            uvals = [float(v) for v in re.findall(r'UAVG=(\d+(?:\.\d+)?)', r.stderr)]
            vvals = [float(v) for v in re.findall(r'VAVG=(\d+(?:\.\d+)?)', r.stderr)]
            if yvals:
                info.yavg = sum(yvals) / len(yvals)
            if uvals and vvals:
                info.uavg = sum(uvals) / len(uvals)
                info.vavg = sum(vvals) / len(vvals)
                # 色温提示：U/V 比值，高 U → 冷，高 V → 暖
                info.color_temp_hint = (info.vavg - info.uavg) / 30.0
                info.color_temp_hint = max(-1.0, min(1.0, info.color_temp_hint))
                # 估算饱和度：UV 偏离中心的距离
                info.saturation = ((info.uavg - 128) ** 2 + (info.vavg - 128) ** 2) ** 0.5
            logger.debug(f"  shot#{shot_index}: Y={info.yavg:.1f} U={info.uavg:.1f} "
                         f"V={info.vavg:.1f} sat={info.saturation:.1f} temp={info.color_temp_hint:.2f}")
        except Exception as e:
            logger.warning(f"镜头色彩分析失败 shot#{shot_index}: {e}")
        return info

    def analyze_shots(self, shot_paths: list[str], cut_times: list[float]) -> list[ShotColorInfo]:
        """批量分析多个镜头的色彩特征。"""
        results = []
        for i, path in enumerate(shot_paths):
            start = cut_times[i] if i < len(cut_times) else 0.0
            dur = (cut_times[i + 1] - start) if i + 1 < len(cut_times) else 5.0
            info = self.analyze_shot_color(path, i, start, dur)
            results.append(info)
        return results

    # ------------------------------------------------------------------
    #  2. 风格匹配
    # ------------------------------------------------------------------

    def select_best_style(self, shot: ShotColorInfo,
                          mood: str = "") -> tuple[str, float]:
        """为单个镜头选择最佳调色风格。

        基于镜头色彩特征 + 情绪标签，对每种风格打分，
        扣分项来自色彩冲突规则。

        Returns:
            (style_name, score) 最高分风格
        """
        best_name = "natural"
        best_score = -999.0

        for style_name, style in GRADING_STYLES.items():
            score = 0.5  # 基础分

            # 亮度匹配度
            br = style.suitable_for.get("brightness_range", (0, 1))
            norm_y = shot.yavg / 255.0
            if br[0] <= norm_y <= br[1]:
                score += 0.3
            else:
                score -= 0.2 * min(abs(norm_y - br[0]), abs(norm_y - br[1]))

            # 情绪匹配
            style_moods = style.suitable_for.get("mood", [])
            if mood and mood in style_moods:
                score += 0.4
            elif mood and style_moods:
                score -= 0.1

            # 色彩冲突惩罚
            for rule in CONFLICT_RULES:
                condition = rule["condition"]
                if condition == "src_dark" and shot.is_dark:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]
                elif condition == "src_bright" and shot.is_bright:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]
                elif condition == "src_cool" and shot.is_cool:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]
                elif condition == "src_warm" and shot.is_warm:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]
                elif condition == "src_high_sat" and shot.is_high_sat:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]
                elif condition == "src_low_sat" and shot.is_low_sat:
                    if style_name in rule["penalize"]:
                        score -= rule["weight"]

            if score > best_score:
                best_score = score
                best_name = style_name

        return best_name, best_score

    # ------------------------------------------------------------------
    #  3. 自适应参数计算（含冲突修正）
    # ------------------------------------------------------------------

    def compute_adaptive_params(self, shot: ShotColorInfo,
                                 style_name: str) -> dict[str, float]:
        """根据镜头特征和选定风格，计算最终调色参数。

        包含冲突修正：如果镜头特征与风格参数冲突，自动降低强度。

        Returns:
            {"saturation": float, "contrast": float, "brightness": float,
             "colorbalance": str, "temperature": float}
        """
        style = GRADING_STYLES.get(style_name, GRADING_STYLES["natural"])
        params = {
            "saturation": style.saturation,
            "contrast": style.contrast,
            "brightness": style.brightness,
            "colorbalance": style.colorbalance,
            "temperature": style.temperature,
        }

        # 冲突修正
        for rule in CONFLICT_RULES:
            cond = rule["condition"]
            triggered = False
            if cond == "src_dark" and shot.is_dark:
                triggered = True
            elif cond == "src_bright" and shot.is_bright:
                triggered = True
            elif cond == "src_cool" and shot.is_cool:
                triggered = True
            elif cond == "src_warm" and shot.is_warm:
                triggered = True
            elif cond == "src_high_sat" and shot.is_high_sat:
                triggered = True
            elif cond == "src_low_sat" and shot.is_low_sat:
                triggered = True

            if triggered and style_name in rule["penalize"]:
                # 降低冲突参数的强度（向 1.0 靠拢）
                dampen = 1.0 - rule["weight"]
                params["saturation"] = 1.0 + (params["saturation"] - 1.0) * dampen
                params["contrast"] = 1.0 + (params["contrast"] - 1.0) * dampen
                params["brightness"] *= dampen
                params["temperature"] *= dampen

        return params

    # ------------------------------------------------------------------
    #  4. 生成逐镜头 ffmpeg filter graph
    # ------------------------------------------------------------------

    def compute_grading_plan(self, shots: list[ShotColorInfo],
                              mood: str = "") -> list[dict[str, Any]]:
        """为所有镜头生成调色方案。

        Returns:
            [{"shot_index": int, "style": str, "params": dict, "score": float}, ...]
        """
        plan = []
        for shot in shots:
            style_name, score = self.select_best_style(shot, mood)
            params = self.compute_adaptive_params(shot, style_name)
            plan.append({
                "shot_index": shot.shot_index,
                "style": style_name,
                "params": params,
                "score": score,
                "start": shot.start_time,
                "duration": shot.duration,
            })
            logger.debug(f"  shot#{shot.shot_index}: style={style_name} score={score:.2f} "
                         f"sat={params['saturation']:.2f} contrast={params['contrast']:.2f}")
        return plan

    def build_per_shot_filter(self, plan: list[dict[str, Any]],
                               total_duration: float) -> str:
        """生成逐镜头 ffmpeg filter graph 字符串。

        如果所有镜头风格相同，退化为简单全片滤镜（性能最优）。
        如果风格不同，使用 trim+setpts+filter+concat 分段处理。

        Returns:
            ffmpeg -vf 参数字符串
        """
        if not plan:
            return "hue=s=1.15"

        # 检查是否所有镜头风格相同
        styles_used = set(p["style"] for p in plan)
        if len(styles_used) == 1:
            # 全片统一风格 → 简单滤镜
            p = plan[0]["params"]
            return self._params_to_vf(p)

        # 多风格 → 分段滤镜
        segments = []
        for i, entry in enumerate(plan):
            start = entry["start"]
            dur = entry["duration"]
            if dur < 0.1:
                continue
            end = start + dur
            p = entry["params"]
            vf = self._params_to_vf(p)
            segments.append(
                f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,{vf}[s{i}]"
            )

        if not segments:
            return "hue=s=1.15"

        # concat 所有分段
        concat_inputs = "".join(f"[s{i}]" for i in range(len(segments)))
        concat_n = len(segments)
        filter_str = ";".join(segments) + ";"
        filter_str += f"{concat_inputs}concat=n={concat_n}:v=1:a=0[outv]"

        return filter_str

    @staticmethod
    def _params_to_vf(params: dict[str, Any]) -> str:
        """将调色参数转换为 ffmpeg -vf 字符串。"""
        parts = []
        sat = params.get("saturation", 1.0)
        if abs(sat - 1.0) > 0.01:
            parts.append(f"hue=s={sat:.3f}")
        eq_parts = []
        con = params.get("contrast", 1.0)
        if abs(con - 1.0) > 0.01:
            eq_parts.append(f"contrast={con:.3f}")
        bri = params.get("brightness", 0.0)
        if abs(bri) > 0.001:
            eq_parts.append(f"brightness={bri:.4f}")
        if eq_parts:
            parts.append(f"eq={':'.join(eq_parts)}")
        cb = params.get("colorbalance", "")
        if cb:
            parts.append(f"colorbalance={cb}")
        if not parts:
            parts.append("null")
        return ",".join(parts)
