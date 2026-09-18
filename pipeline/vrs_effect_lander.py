"""
VRS 效果落地器 — 将 VRS 分析结果通过 FFmpeg 滤镜实际渲染
============================================================

将 VideoReproducePipeline / VideoEffectAnalyzerV2 的分析结果
(effect list, transitions, style_tags, color_grading) 
映射为 FFmpeg 滤镜参数并执行。

核心映射:
- VRS effects (glow/blur/sharpen) → FFmpeg unsharp/boxblur/eq
- VRS transitions (fade/wipe/dissolve) → FFmpeg xfade
- VRS style_tags (高燃/电影感/赛博朋克) → 预设滤镜组合
- VRS color_grading → FFmpeg eq/curves/colorbalance

Author: AE-Knowledge-Vault Team
"""

import logging
import os
from typing import Any, Dict, List, Optional

from pipeline.ffmpeg_edit_engine import (
    BlurParams,
    ColorGradeParams,
    FFmpegEditEngine,
    FFmpegFilterBuilder,
    SharpenParams,
    TransitionEngine,
    VignetteParams,
)

logger = logging.getLogger(__name__)


# ============================================================
# 风格标签 → 预设滤镜组合
# ============================================================

STYLE_PRESETS = {
    "高燃": {
        "color": ColorGradeParams(contrast=1.25, saturation=1.2, gamma=0.95, temperature=0.1),
        "sharpen": SharpenParams(amount=1.5, radius=0.8),
        "vignette": VignetteParams(angle=3.0),
    },
    "赛博朋克": {
        "color": ColorGradeParams(contrast=1.3, saturation=1.4, gamma=0.9, temperature=-0.2, tint=0.15),
        "sharpen": SharpenParams(amount=1.0, radius=0.6),
        "vignette": VignetteParams(angle=4.0),
    },
    "霓虹": {
        "color": ColorGradeParams(contrast=1.2, saturation=1.5, gamma=0.95, tint=0.1),
        "sharpen": SharpenParams(amount=0.8, radius=0.5),
    },
    "电影感": {
        "color": ColorGradeParams(contrast=1.15, saturation=0.9, gamma=1.05, temperature=0.05),
        "vignette": VignetteParams(angle=2.5),
        "sharpen": SharpenParams(amount=0.6, radius=0.5),
    },
    "日漫风": {
        "color": ColorGradeParams(contrast=1.1, saturation=1.3, gamma=1.02),
        "sharpen": SharpenParams(amount=1.8, radius=0.7),
    },
    "美漫风": {
        "color": ColorGradeParams(contrast=1.3, saturation=1.1, gamma=0.95),
        "sharpen": SharpenParams(amount=1.2, radius=0.8),
    },
    "国风水墨": {
        "color": ColorGradeParams(contrast=1.1, saturation=0.6, gamma=1.1, brightness=0.05),
        "sharpen": SharpenParams(amount=0.5, radius=0.4),
    },
    "复古怀旧": {
        "color": ColorGradeParams(contrast=1.05, saturation=0.7, gamma=1.1, temperature=0.2),
        "vignette": VignetteParams(angle=3.5),
    },
    "暗调情绪": {
        "color": ColorGradeParams(contrast=1.2, saturation=0.8, gamma=0.85, brightness=-0.1),
        "vignette": VignetteParams(angle=4.0),
    },
    "清新日系": {
        "color": ColorGradeParams(contrast=1.05, saturation=1.1, gamma=1.1, brightness=0.08),
        "sharpen": SharpenParams(amount=0.5, radius=0.4),
    },
    "TVC广告感": {
        "color": ColorGradeParams(contrast=1.2, saturation=1.15, gamma=1.0),
        "sharpen": SharpenParams(amount=1.5, radius=0.8),
        "vignette": VignetteParams(angle=2.0),
    },
    "AMV特效流": {
        "color": ColorGradeParams(contrast=1.3, saturation=1.3, gamma=0.9),
        "sharpen": SharpenParams(amount=2.0, radius=1.0),
        "vignette": VignetteParams(angle=3.5),
    },
    "故障艺术": {
        "color": ColorGradeParams(contrast=1.4, saturation=1.2, gamma=0.9, tint=-0.1),
        "sharpen": SharpenParams(amount=1.0, radius=0.6),
    },
}

# VRS 效果名 → FFmpeg 映射
EFFECT_NAME_MAP = {
    # 发光类
    "glow": {"type": "eq", "params": {"brightness": 0.05, "gamma": 1.1}},
    "deep_glow": {"type": "eq", "params": {"brightness": 0.08, "gamma": 1.15}},
    "bloom": {"type": "eq", "params": {"brightness": 0.06, "gamma": 1.12}},
    "发光": {"type": "eq", "params": {"brightness": 0.05, "gamma": 1.1}},
    "发光晕染": {"type": "eq", "params": {"brightness": 0.07, "gamma": 1.13}},
    # 锐化/清晰
    "sharpen": {"type": "sharpen", "params": {"amount": 1.5, "radius": 0.8}},
    "锐化": {"type": "sharpen", "params": {"amount": 1.5, "radius": 0.8}},
    "清晰": {"type": "sharpen", "params": {"amount": 1.2, "radius": 0.6}},
    # 模糊
    "blur": {"type": "blur", "params": {"radius_x": 2.0, "radius_y": 2.0}},
    "gaussian_blur": {"type": "blur", "params": {"radius_x": 3.0, "radius_y": 3.0}},
    "模糊": {"type": "blur", "params": {"radius_x": 2.0, "radius_y": 2.0}},
    "运动模糊": {"type": "eq", "params": {}},  # FFmpeg无直接运动模糊，跳过
    # 暗角
    "vignette": {"type": "vignette", "params": {"angle": 3.0}},
    "暗角": {"type": "vignette", "params": {"angle": 3.0}},
    # 调色
    "color_grade": {"type": "color", "params": {"contrast": 1.15, "saturation": 1.1}},
    "调色": {"type": "color", "params": {"contrast": 1.15, "saturation": 1.1}},
    "暖色调": {"type": "color", "params": {"temperature": 0.2, "gamma": 1.05}},
    "冷色调": {"type": "color", "params": {"temperature": -0.2, "gamma": 1.05}},
}

# VRS 转场类型 → FFmpeg xfade
TRANSITION_MAP = {
    "fade": "fade",
    "crossfade": "fade",
    "淡入淡出": "fade",
    "wipe": "wipeleft",
    "擦除": "wipeleft",
    "dissolve": "dissolve",
    "溶解": "dissolve",
    "wipeleft": "wipeleft",
    "wiperight": "wiperight",
    "wipeup": "wipeup",
    "wipedown": "wipedown",
    "smoothleft": "smoothleft",
    "smoothright": "smoothright",
    "radial": "radial",
    "circlecrop": "circlecrop",
    "硬切": "fade",  # 硬切用极短fade
    "cut": "fade",
}


class VRSEffectLander:
    """
    VRS 效果落地器 — 将 VRS 分析结果渲染为真实视频
    
    用法:
        lander = VRSEffectLander()
        result = lander.apply(
            input_video="input.mp4",
            vrs_analysis={
                "effects": [{"name": "glow", "intensity": 0.8, "confidence": 0.9}],
                "transitions": [{"type": "fade", "duration": 0.5}],
                "style_tags": ["高燃", "电影感"],
                "color_grading": {"temperature": "warm", "contrast": "high"}
            },
            output="output.mp4"
        )
    """

    def __init__(self, ffmpeg_bin: str = ""):
        self.engine = FFmpegEditEngine(ffmpeg_bin)

    def apply(self, input_video: str, vrs_analysis: dict,
              output: str = "") -> dict:
        """
        将 VRS 分析结果应用到视频
        
        Args:
            input_video: 输入视频
            vrs_analysis: VRS 分析结果
            output: 输出路径
        """
        if not os.path.isfile(input_video):
            return {"success": False, "error": f"输入不存在: {input_video}"}
        if not output:
            base, ext = os.path.splitext(input_video)
            output = f"{base}_vrs{ext}"

        fb = FFmpegFilterBuilder()
        applied = []

        # === 1. 风格标签 → 预设滤镜 ===
        style_tags = vrs_analysis.get("style_tags", [])
        for tag in style_tags:
            if tag in STYLE_PRESETS:
                preset = STYLE_PRESETS[tag]
                if "color" in preset:
                    fb.color_grade(preset["color"])
                    applied.append(f"style_color:{tag}")
                if "sharpen" in preset:
                    fb.sharpen(preset["sharpen"])
                    applied.append(f"style_sharpen:{tag}")
                if "vignette" in preset:
                    fb.vignette(preset["vignette"])
                    applied.append(f"style_vignette:{tag}")
                break  # 只应用第一个匹配的风格预设

        # === 2. 效果列表 → FFmpeg 滤镜 ===
        effects = vrs_analysis.get("effects", [])
        for fx in effects:
            name = fx.get("name", "").lower()
            intensity = fx.get("intensity", 1.0)
            confidence = fx.get("confidence", 0.5)
            if confidence < 0.3:
                continue  # 低置信度跳过

            mapping = EFFECT_NAME_MAP.get(name)
            if not mapping:
                # 模糊匹配
                for key, val in EFFECT_NAME_MAP.items():
                    if key in name or name in key:
                        mapping = val
                        break
            if not mapping:
                continue

            fx_type = mapping["type"]
            params = dict(mapping["params"])

            # 根据 intensity 调整参数
            if fx_type == "sharpen" and "amount" in params:
                params["amount"] *= intensity
            elif fx_type == "blur":
                params["radius_x"] *= intensity
                params["radius_y"] *= intensity

            if fx_type == "color":
                fb.color_grade(ColorGradeParams(**params))
                applied.append(f"effect_color:{name}(i={intensity:.1f})")
            elif fx_type == "sharpen":
                fb.sharpen(SharpenParams(**params))
                applied.append(f"effect_sharpen:{name}(i={intensity:.1f})")
            elif fx_type == "blur":
                fb.blur(BlurParams(**params))
                applied.append(f"effect_blur:{name}(i={intensity:.1f})")
            elif fx_type == "vignette":
                fb.vignette(VignetteParams(**params))
                applied.append(f"effect_vignette:{name}(i={intensity:.1f})")

        # === 3. 色彩信息 → 调色 ===
        color_info = vrs_analysis.get("color_grading", {})
        if color_info and not any("color" in a for a in applied):
            temp = color_info.get("temperature", "")
            if temp == "warm":
                fb.color_grade(ColorGradeParams(temperature=0.15, gamma=1.03))
                applied.append("color_grade:warm")
            elif temp == "cool":
                fb.color_grade(ColorGradeParams(temperature=-0.15, gamma=1.03))
                applied.append("color_grade:cool")
            
            contrast = color_info.get("contrast", "")
            if contrast == "high":
                fb.color_grade(ColorGradeParams(contrast=1.15))
                applied.append("color_grade:high_contrast")

        # === 4. 执行滤镜 ===
        filter_chain = fb.build()
        if not filter_chain:
            # 无滤镜可应用
            import shutil
            shutil.copy2(input_video, output)
            return {
                "success": True,
                "output": output,
                "applied": [],
                "filter_chain": "",
                "reasoning": "VRS分析无可映射效果"
            }

        total_dur = self.engine._get_duration(input_video)
        success = self.engine.apply_filters(input_video, output, fb, total_dur)

        return {
            "success": success,
            "output": output if success else input_video,
            "applied": applied,
            "filter_chain": filter_chain,
            "style_tags_processed": style_tags,
            "effects_processed": len(effects),
            "reasoning": f"应用{len(applied)}个效果: {', '.join(applied)}"
        }

    def apply_transitions(self, clips: list[str], output: str,
                          vrs_transitions: list[dict]) -> bool:
        """
        将 VRS 转场信息应用到多片段拼接
        
        Args:
            clips: 视频片段列表
            output: 输出路径
            vrs_transitions: VRS 转场列表 [{"type": "fade", "duration": 0.5, ...}]
        """
        if len(clips) < 2:
            if clips:
                import shutil
                shutil.copy2(clips[0], output)
                return True
            return False

        # 映射转场类型
        mapped_types = []
        mapped_durations = []
        for trans in vrs_transitions:
            vrs_type = trans.get("type", "fade")
            duration = trans.get("duration", 0.5)
            ff_type = TRANSITION_MAP.get(vrs_type, "fade")
            if vrs_type == "硬切" or vrs_type == "cut":
                duration = 0.01  # 极短
            mapped_types.append(ff_type)
            mapped_durations.append(duration)

        # 补齐数量
        n = len(clips) - 1
        while len(mapped_types) < n:
            mapped_types.append("fade")
            mapped_durations.append(0.5)

        return self.engine.concat_with_transitions(
            clips, output, mapped_types[:n], mapped_durations[:n]
        )

    def get_style_preset(self, style_tag: str) -> dict | None:
        """获取风格预设信息"""
        return STYLE_PRESETS.get(style_tag)

    def list_available_styles(self) -> list[str]:
        """列出所有可用风格"""
        return list(STYLE_PRESETS.keys())
