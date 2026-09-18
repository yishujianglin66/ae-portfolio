#!/usr/bin/env python3
"""
parameter_mapper.py
Phase 4 - 参数映射引擎（Python 版）

对齐 TypeScript 端 compiler/src/phase4/parameter-mapper.ts。

核心职责：
  1. 将词汇引用(VocabRef)映射到具体的效果 matchName
  2. 根据强度、颜色等修饰词生成参数值
  3. 应用参数约束（范围 clamp）和默认值

输入：EffectDescription（从 effect_description_parser 解析得到）
输出：ParameterMapping 列表（matchName + settings + confidence）
"""

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from effect_description_parser import (
    ColorRef,
    EffectDescription,
    IntensityRef,
    VocabRef,
)

# ============================================================================
# 数据类
# ============================================================================

@dataclass
class ParameterMapping:
    """单个效果的参数映射结果。"""
    matchName: str
    settings: dict[str, Any]  # value: number | string | list[number]
    confidence: float


@dataclass
class MapperContext:
    """映射器上下文，提供合成环境信息。"""
    compWidth: int = 1920
    compHeight: int = 1080
    frameRate: int = 30
    duration: float = 10.0
    selectedLayer: str = ""


# ============================================================================
# 效果模板表
# 每个模板包含：matchName / defaultSettings / parameterRange / intensityScale
# ============================================================================

EFFECT_TEMPLATES: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # 发光类
    # ------------------------------------------------------------------
    "VT-101": {
        # 标准发光（Glow）
        "matchName": "ADBE Glo2",
        "defaultSettings": {
            "Glow Threshold": 40,
            "Glow Radius": 25,
            "Glow Intensity": 1.5,
            "Glow Colors": [1, 1, 1],
            "Glow Color A": [1, 0.8, 0.2],
            "Glow Color B": [0.2, 0.6, 1],
        },
        "parameterRange": {
            "Glow Threshold": {"min": 0, "max": 100},
            "Glow Radius": {"min": 0, "max": 200},
            "Glow Intensity": {"min": 0, "max": 10},
        },
        "intensityScale": {
            "Glow Radius": 1.0,
            "Glow Intensity": 1.0,
        },
    },
    "VT-102": {
        # 柔和发光（Glow，阈值更高）
        "matchName": "ADBE Glo2",
        "defaultSettings": {
            "Glow Threshold": 60,
            "Glow Radius": 50,
            "Glow Intensity": 2.0,
            "Glow Colors": [1, 1, 1],
            "Glow Color A": [1, 0.9, 0.5],
            "Glow Color B": [0.5, 0.8, 1],
        },
        "parameterRange": {
            "Glow Threshold": {"min": 0, "max": 100},
            "Glow Radius": {"min": 0, "max": 200},
            "Glow Intensity": {"min": 0, "max": 10},
        },
        "intensityScale": {
            "Glow Radius": 1.2,
            "Glow Intensity": 1.3,
        },
    },
    # ------------------------------------------------------------------
    # 模糊类
    # ------------------------------------------------------------------
    "VT-001": {
        # 高斯模糊
        "matchName": "ADBE Gaussian Blur 2",
        "defaultSettings": {
            "Blurriness": 25,
        },
        "parameterRange": {
            "Blurriness": {"min": 0, "max": 1000},
        },
        "intensityScale": {
            "Blurriness": 1.0,
        },
    },
    "VT-002": {
        # 方向模糊
        "matchName": "ADBE Directional Blur",
        "defaultSettings": {
            "Blurriness": 20,
            "Direction": 0,
        },
        "parameterRange": {
            "Blurriness": {"min": 0, "max": 100},
            "Direction": {"min": 0, "max": 360},
        },
        "intensityScale": {
            "Blurriness": 1.0,
        },
    },
    "VT-003": {
        # 快速方框模糊
        "matchName": "ADBE Fast Box Blur",
        "defaultSettings": {
            "Blurriness": 15,
            "Repeat Edge Pixels": 0,
        },
        "parameterRange": {
            "Blurriness": {"min": 0, "max": 1000},
            "Repeat Edge Pixels": {"min": 0, "max": 1},
        },
        "intensityScale": {
            "Blurriness": 1.0,
        },
    },
    # ------------------------------------------------------------------
    # 噪波类
    # ------------------------------------------------------------------
    "VT-201": {
        # 分形噪波
        "matchName": "ADBE Fractal Noise",
        "defaultSettings": {
            "Contrast": 100,
            "Brightness": 0,
            "Complexity": 4,
            "Scale": 100,
            "Evolution": 0,
        },
        "parameterRange": {
            "Contrast": {"min": 0, "max": 400},
            "Brightness": {"min": -100, "max": 100},
            "Complexity": {"min": 1, "max": 6},
            "Scale": {"min": 1, "max": 1000},
        },
        "intensityScale": {
            "Contrast": 1.0,
        },
    },
    "VT-202": {
        # 噪波
        "matchName": "ADBE Noise",
        "defaultSettings": {
            "Amount of Noise": 20,
        },
        "parameterRange": {
            "Amount of Noise": {"min": 0, "max": 100},
        },
        "intensityScale": {
            "Amount of Noise": 1.0,
        },
    },
    # ------------------------------------------------------------------
    # 渐变类
    # ------------------------------------------------------------------
    "VT-301": {
        # 渐变 / 梯度
        "matchName": "ADBE Ramp",
        "defaultSettings": {
            "Start of Ramp": [0, 0],
            "Start Color": [1, 0, 0],
            "End of Ramp": [1920, 1080],
            "End Color": [0, 0, 1],
            "Ramp Shape": 1,
            "Ramp Scatter": 0,
        },
        "parameterRange": {
            "Ramp Scatter": {"min": 0, "max": 100},
            "Ramp Shape": {"min": 1, "max": 2},
        },
        "intensityScale": {},
    },
    # ------------------------------------------------------------------
    # 色彩类
    # ------------------------------------------------------------------
    "VT-401": {
        # 色彩平衡
        "matchName": "ADBE Color Balance",
        "defaultSettings": {
            "Red Shadows": 5,
            "Green Shadows": -5,
            "Blue Shadows": -10,
            "Red Midtones": 10,
            "Green Midtones": 0,
            "Blue Midtones": -5,
            "Red Highlights": 15,
            "Green Highlights": 5,
            "Blue Highlights": -5,
        },
        "parameterRange": {
            "Red Shadows": {"min": -100, "max": 100},
            "Green Shadows": {"min": -100, "max": 100},
            "Blue Shadows": {"min": -100, "max": 100},
            "Red Midtones": {"min": -100, "max": 100},
            "Green Midtones": {"min": -100, "max": 100},
            "Blue Midtones": {"min": -100, "max": 100},
            "Red Highlights": {"min": -100, "max": 100},
            "Green Highlights": {"min": -100, "max": 100},
            "Blue Highlights": {"min": -100, "max": 100},
        },
        "intensityScale": {},
    },
    "VT-402": {
        # 色相 / 饱和度
        "matchName": "ADBE HUE SATURATION",
        "defaultSettings": {
            "Hue": 0,
            "Saturation": 0,
            "Lightness": 0,
        },
        "parameterRange": {
            "Hue": {"min": -180, "max": 180},
            "Saturation": {"min": -100, "max": 100},
            "Lightness": {"min": -100, "max": 100},
        },
        "intensityScale": {
            "Saturation": 1.0,
        },
    },
    "VT-403": {
        # 色阶
        "matchName": "ADBE Protractor2",
        "defaultSettings": {
            "Input Black": 0,
            "Input White": 255,
            "Gamma": 1.0,
            "Output Black": 0,
            "Output White": 255,
        },
        "parameterRange": {
            "Input Black": {"min": 0, "max": 255},
            "Input White": {"min": 0, "max": 255},
            "Gamma": {"min": 0.1, "max": 10},
            "Output Black": {"min": 0, "max": 255},
            "Output White": {"min": 0, "max": 255},
        },
        "intensityScale": {},
    },
    # ------------------------------------------------------------------
    # 粒子类
    # ------------------------------------------------------------------
    "VT-501": {
        # CC 粒子世界
        "matchName": "CC Particle World",
        "defaultSettings": {
            "Birth Rate": 100,
            "Longevity": 2.0,
            "Position X": 0.5,
            "Position Y": 0.5,
            "Velocity": 100,
            "Gravity": 50,
            "Particle Radius": 10,
            "Red": 1.0,
            "Green": 0.5,
            "Blue": 0.2,
            "Opacity": 100,
        },
        "parameterRange": {
            "Birth Rate": {"min": 0, "max": 1000},
            "Longevity": {"min": 0.1, "max": 10},
            "Position X": {"min": 0, "max": 1},
            "Position Y": {"min": 0, "max": 1},
            "Velocity": {"min": 0, "max": 500},
            "Gravity": {"min": -200, "max": 200},
            "Particle Radius": {"min": 0.1, "max": 100},
            "Opacity": {"min": 0, "max": 100},
        },
        "intensityScale": {
            "Birth Rate": 1.0,
            "Velocity": 1.0,
            "Particle Radius": 0.8,
        },
    },
    "VT-502": {
        # Trapcode Particular
        "matchName": "ACP Particular",
        "defaultSettings": {
            "Particles/sec": 100,
            "Life": 2.0,
            "Size": 5,
            "Speed": 100,
            "Opacity": 100,
            "Red": 1.0,
            "Green": 1.0,
            "Blue": 1.0,
        },
        "parameterRange": {
            "Particles/sec": {"min": 0, "max": 10000},
            "Life": {"min": 0, "max": 100},
            "Size": {"min": 0, "max": 100},
            "Speed": {"min": 0, "max": 1000},
            "Opacity": {"min": 0, "max": 100},
        },
        "intensityScale": {
            "Particles/sec": 1.0,
            "Speed": 1.0,
        },
    },
}


# ============================================================================
# 参数映射器
# ============================================================================

class ParameterMapper:
    """参数映射器：将 EffectDescription 映射为具体效果参数。"""

    def __init__(self, context: MapperContext = None):
        """初始化映射器，可传入自定义上下文。"""
        self.context = context if context is not None else MapperContext()

    def map(self, description: EffectDescription) -> list[ParameterMapping]:
        """
        将 EffectDescription 中的效果/风格关键词映射为具体参数。

        流程：
          1. 遍历 effectKeywords，查模板表，复制默认参数并应用修饰词
          2. 按 matchName 去重
          3. 同样处理 styleKeywords
        """
        mappings: list[ParameterMapping] = []
        seen_match_names: set[str] = set()

        # 处理效果关键词
        for vocab_ref in description.effectKeywords:
            template = EFFECT_TEMPLATES.get(vocab_ref.id)
            if not template:
                continue

            match_name = template["matchName"]
            if match_name in seen_match_names:
                continue
            seen_match_names.add(match_name)

            settings = self._apply_modifiers(
                template["defaultSettings"],
                description.intensityKeywords,
                description.colorKeywords,
                template["intensityScale"],
                template["parameterRange"],
            )

            mappings.append(ParameterMapping(
                matchName=match_name,
                settings=settings,
                confidence=vocab_ref.confidence,
            ))

        # 处理风格关键词（与效果关键词共用去重集合）
        for vocab_ref in description.styleKeywords:
            template = EFFECT_TEMPLATES.get(vocab_ref.id)
            if not template:
                continue

            match_name = template["matchName"]
            if match_name in seen_match_names:
                continue
            seen_match_names.add(match_name)

            settings = self._apply_modifiers(
                template["defaultSettings"],
                description.intensityKeywords,
                description.colorKeywords,
                template["intensityScale"],
                template["parameterRange"],
            )

            mappings.append(ParameterMapping(
                matchName=match_name,
                settings=settings,
                confidence=vocab_ref.confidence,
            ))

        return mappings

    def _apply_modifiers(
        self,
        settings: dict[str, Any],
        intensity_keywords: list[IntensityRef],
        color_keywords: list[ColorRef],
        intensity_scale: dict[str, float],
        parameter_range: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        """
        应用全部修饰词：强度 → 颜色 → 范围约束。

        深拷贝输入 settings，确保不修改模板原始数据。
        """
        result = copy.deepcopy(settings)

        self._apply_intensity(result, intensity_keywords, intensity_scale)
        self._apply_color(result, color_keywords)
        self._apply_range(result, parameter_range)

        return result

    def _apply_intensity(
        self,
        settings: dict[str, Any],
        intensity_keywords: list[IntensityRef],
        intensity_scale: dict[str, float],
    ) -> None:
        """
        对 intensityScale 中列出的参数，乘以总强度系数。

        总强度系数 = 所有 IntensityRef.value 的乘积；
        每个参数最终值 = 原值 × 总强度系数 × 该参数的 scale 因子。
        仅对数值型参数生效，跳过列表/字符串。
        """
        # 计算总强度系数（多个强度关键词累乘）
        overall_scale = 1.0
        for ref in intensity_keywords:
            overall_scale *= ref.value

        # 对 intensityScale 中列出的参数应用强度缩放
        for param_name, scale_factor in intensity_scale.items():
            if param_name in settings and isinstance(settings[param_name], (int, float)):
                settings[param_name] = settings[param_name] * overall_scale * scale_factor

    def _apply_color(
        self,
        settings: dict[str, Any],
        color_keywords: list[ColorRef],
    ) -> None:
        """
        根据颜色关键词设置相关颜色参数。

        处理规则：
          - "Glow Color A"（列表）：直接替换为颜色关键词 RGB
          - "Glow Color B"（列表）：与原色混合（70% 原色 + 30% 新色）
          - "Red"/"Green"/"Blue"（数值）：分别设置为 RGB 通道值
        """
        for color_ref in color_keywords:
            # Glow Color A — 直接替换
            if "Glow Color A" in settings and isinstance(settings["Glow Color A"], list):
                settings["Glow Color A"] = list(color_ref.rgb)

            # Glow Color B — 与基色混合
            if "Glow Color B" in settings and isinstance(settings["Glow Color B"], list):
                base_rgb = settings["Glow Color B"]
                settings["Glow Color B"] = [
                    base_rgb[0] * 0.7 + color_ref.rgb[0] * 0.3,
                    base_rgb[1] * 0.7 + color_ref.rgb[1] * 0.3,
                    base_rgb[2] * 0.7 + color_ref.rgb[2] * 0.3,
                ]

            # 粒子等效果的独立 RGB 通道
            if "Red" in settings and isinstance(settings["Red"], (int, float)):
                settings["Red"] = color_ref.rgb[0]
            if "Green" in settings and isinstance(settings["Green"], (int, float)):
                settings["Green"] = color_ref.rgb[1]
            if "Blue" in settings and isinstance(settings["Blue"], (int, float)):
                settings["Blue"] = color_ref.rgb[2]

    def _apply_range(
        self,
        settings: dict[str, Any],
        parameter_range: dict[str, dict[str, float]],
    ) -> None:
        """
        对 parameterRange 中列出的参数，clamp 到 [min, max] 区间。

        仅对数值型参数生效，跳过列表/字符串。
        """
        for param_name, range_info in parameter_range.items():
            if param_name in settings and isinstance(settings[param_name], (int, float)):
                min_val = range_info["min"]
                max_val = range_info["max"]
                settings[param_name] = self._clamp(
                    settings[param_name], min_val, max_val
                )

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        """将 value 限制在 [min_val, max_val] 区间内。"""
        return max(min_val, min(max_val, value))

    def set_context(self, context: MapperContext) -> None:
        """更新映射器上下文。"""
        self.context = context
