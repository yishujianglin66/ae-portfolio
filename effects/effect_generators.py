#!/usr/bin/env python3
"""
effect_generators.py - Phase 4 效果智能参数生成器（Python 版）

对齐 TypeScript 端 compiler/src/phase4/effect-generators.ts。

为 20 个常用 AE 效果提供智能参数生成能力：
    1. Glow（发光）
    2. Color Key（颜色键控）
    3. CC Particle World（粒子世界）
    4. Fractal Noise（分形噪波）
    5. Ramp（渐变）
    6. Gaussian Blur（高斯模糊）
    7. Directional Blur（方向模糊）
    8. Hue/Saturation（色相/饱和度）
    9. Levels（色阶，替代 Curves）
   10. Color Balance（色彩平衡）
   11. Drop Shadow（投影）
   12. Fill（填充）
   13. Stroke（描边）
   14. Noise（噪波）
   15. Sharpen（锐化）
   16. Texturize（纹理化）
   17. Roughen Edges（粗糙边缘）
   18. CC Lens（CC 镜头）
   19. Optics Compensation（光学补偿）
   20. Simple Choker（简单抑制）

生成策略：
    - 根据自然语言描述中的修饰词（强度、颜色、风格）智能计算参数值
    - 应用参数约束（clamp）和最佳实践值
    - 支持多场景预设（如霓虹发光、柔和发光、强烈发光）

modifiers 字典格式：
    {"intensity": [...], "color": [...], "temporal": [...], "style": "neon"}
    - intensity_refs: [{"keyword": "强烈", "value": 1.5}]  value 为缩放系数
    - color_refs:    [{"keyword": "红色", "rgb": [1, 0, 0]}]
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from effect_knowledge_graph import (
    EFFECT_KNOWLEDGE_GRAPH,
    EffectNode,
    EffectParameter,
)

# ============================================================================
# 数据类
# ============================================================================


@dataclass
class EffectParams:
    """效果参数生成结果"""

    matchName: str
    displayName: str
    settings: dict[str, Any]  # value: number | string | list[number]
    confidence: float


@dataclass
class GeneratorContext:
    """生成器上下文（合成信息与选中图层）"""

    compWidth: int = 1920
    compHeight: int = 1080
    frameRate: int = 30
    duration: float = 10.0
    selectedLayerType: str = ""


# ============================================================================
# BaseGenerator 抽象基类
# ============================================================================


class BaseGenerator(ABC):
    """所有效果生成器的抽象基类"""

    def __init__(self, context: GeneratorContext = None):
        # 允许传入 None，内部统一保存为 GeneratorContext 实例
        self.context: GeneratorContext = context if context is not None else GeneratorContext()

    @abstractmethod
    def generate(self, modifiers: dict) -> EffectParams:
        """根据修饰词生成效果参数"""
        raise NotImplementedError

    def _get_intensity_scale(self, intensity_refs: list[dict]) -> float:
        """从强度修饰词列表计算总缩放系数（各 value 相乘）"""
        if not intensity_refs:
            return 1.0
        scale = 1.0
        for ref in intensity_refs:
            # 任务规定 value 字段为缩放系数，默认 1.0
            scale *= float(ref.get("value", 1.0))
        return scale

    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """将数值限制在 [min_val, max_val] 区间"""
        return max(min_val, min(max_val, value))


# ============================================================================
# 1. GlowGenerator — 发光（matchName: ADBE Glo2）
# ============================================================================


class GlowGenerator(BaseGenerator):
    """发光效果生成器，支持 neon/cyberpunk/soft/dreamy/strong 五种预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None

        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]

        settings: dict[str, Any] = {
            "Glow Threshold": self._clamp(preset["base"]["threshold"] * scale_factor, 0, 100),
            "Glow Radius": self._clamp(preset["base"]["radius"] * scale_factor, 0, 200),
            "Glow Intensity": self._clamp(preset["base"]["intensity"] * scale_factor, 0, 10),
            "Glow Colors": preset["base"]["colors"],
        }

        if color:
            rgb = color.get("rgb", [1, 1, 1])
            settings["Glow Color A"] = rgb
            settings["Glow Color B"] = [rgb[0] * 0.7, rgb[1] * 0.7, rgb[2] * 0.7]
        else:
            settings["Glow Color A"] = preset["colors"]["a"]
            settings["Glow Color B"] = preset["colors"]["b"]

        return EffectParams(
            matchName="ADBE Glo2",
            displayName="Glow",
            settings=settings,
            confidence=0.85,
        )

    def _get_preset(self, style: str) -> dict:
        # 中文风格名归一化为英文 key
        style_map = {
            "霓虹": "neon",
            "赛博朋克": "cyberpunk",
            "柔和": "soft",
            "梦幻": "dreamy",
            "强烈": "strong",
        }
        normalized = style_map.get(style, style or "")

        presets = {
            "neon": {
                "base": {"threshold": 30, "radius": 40, "intensity": 2.5, "colors": [1, 1, 1]},
                "colors": {"a": [0.2, 0.6, 1], "b": [0.6, 0.2, 1]},
                "scale": 1.5,
            },
            "cyberpunk": {
                "base": {"threshold": 25, "radius": 50, "intensity": 3.0, "colors": [1, 1, 1]},
                "colors": {"a": [0.1, 0.8, 1], "b": [1, 0.2, 0.8]},
                "scale": 1.6,
            },
            "soft": {
                "base": {"threshold": 70, "radius": 20, "intensity": 1.0, "colors": [1, 1, 1]},
                "colors": {"a": [1, 0.9, 0.8], "b": [0.9, 0.95, 1]},
                "scale": 0.6,
            },
            "dreamy": {
                "base": {"threshold": 60, "radius": 35, "intensity": 1.5, "colors": [1, 1, 1]},
                "colors": {"a": [1, 0.8, 0.9], "b": [0.8, 0.9, 1]},
                "scale": 0.8,
            },
            "strong": {
                "base": {"threshold": 20, "radius": 60, "intensity": 4.0, "colors": [1, 1, 1]},
                "colors": {"a": [1, 0.5, 0], "b": [1, 0.2, 0]},
                "scale": 1.8,
            },
        }

        normalized_lower = normalized.lower()
        for key, preset in presets.items():
            if key in normalized_lower:
                return preset

        # 默认预设
        return {
            "base": {"threshold": 40, "radius": 25, "intensity": 1.5, "colors": [1, 1, 1]},
            "colors": {"a": [1, 0.8, 0.2], "b": [0.2, 0.6, 1]},
            "scale": 1.0,
        }


# ============================================================================
# 2. ColorKeyGenerator — 颜色键控（matchName: ADBE Color Key）
# ============================================================================


class ColorKeyGenerator(BaseGenerator):
    """颜色键控生成器，支持绿幕/蓝幕/红幕"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        style = modifiers.get("style", "") or ""

        tolerance = self._clamp(20 * intensity_scale, 5, 80)
        edge_feather = self._clamp(1.0 * intensity_scale, 0, 10)

        settings: dict[str, Any] = {
            "Key Color": color.get("rgb", [0, 1, 0]) if color else [0, 1, 0],
            "Color Tolerance": tolerance,
            "Edge Feather": edge_feather,
            "Edge Thin": self._clamp(0.5 * intensity_scale, -5, 5),
            "Edge Contrast": self._clamp(10 * intensity_scale, 0, 100),
            "Smoothing": "None",
        }

        style_lower = style.lower()
        if "green" in style_lower:
            settings["Key Color"] = [0, 0.8, 0.2]
        elif "blue" in style_lower:
            settings["Key Color"] = [0.1, 0.3, 0.9]
        elif "red" in style_lower:
            settings["Key Color"] = [0.9, 0.1, 0.1]

        return EffectParams(
            matchName="ADBE Color Key",
            displayName="Color Key",
            settings=settings,
            confidence=0.80,
        )


# ============================================================================
# 3. CCParticleWorldGenerator — 粒子世界（matchName: CC Particle World）
# ============================================================================


class CCParticleWorldGenerator(BaseGenerator):
    """CC 粒子世界生成器，支持 fire/snow/sparkle/smoke/explosion 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None

        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Birth Rate": self._clamp(base["birthRate"] * scale_factor, 0, 1000),
            "Longevity": self._clamp(base["longevity"] / scale_factor if scale_factor else base["longevity"], 0.1, 10),
            "Position X": base["posX"],
            "Position Y": base["posY"],
            "Velocity": self._clamp(base["velocity"] * scale_factor, 0, 500),
            "Gravity": base["gravity"],
            "Particle Radius": self._clamp(base["radius"] * scale_factor, 0.1, 100),
            "Opacity": self._clamp(base["opacity"], 0, 100),
            "Red": color.get("rgb", [0, 0, 0])[0] if color else preset["colors"]["r"],
            "Green": color.get("rgb", [0, 0, 0])[1] if color else preset["colors"]["g"],
            "Blue": color.get("rgb", [0, 0, 0])[2] if color else preset["colors"]["b"],
        }

        return EffectParams(
            matchName="CC Particle World",
            displayName="CC Particle World",
            settings=settings,
            confidence=0.82,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "fire": {
                "base": {"birthRate": 150, "longevity": 1.5, "posX": 0.5, "posY": 0.8,
                         "velocity": 150, "gravity": -80, "radius": 8, "opacity": 100},
                "colors": {"r": 1, "g": 0.4, "b": 0.1},
                "scale": 1.5,
            },
            "snow": {
                "base": {"birthRate": 30, "longevity": 5.0, "posX": 0.5, "posY": 0.1,
                         "velocity": 20, "gravity": 30, "radius": 3, "opacity": 80},
                "colors": {"r": 1, "g": 1, "b": 1},
                "scale": 0.8,
            },
            "sparkle": {
                "base": {"birthRate": 80, "longevity": 1.0, "posX": 0.5, "posY": 0.5,
                         "velocity": 200, "gravity": -50, "radius": 2, "opacity": 100},
                "colors": {"r": 1, "g": 0.9, "b": 0.5},
                "scale": 1.2,
            },
            "smoke": {
                "base": {"birthRate": 20, "longevity": 4.0, "posX": 0.5, "posY": 0.8,
                         "velocity": 30, "gravity": -15, "radius": 25, "opacity": 60},
                "colors": {"r": 0.5, "g": 0.5, "b": 0.5},
                "scale": 0.6,
            },
            "explosion": {
                "base": {"birthRate": 500, "longevity": 0.8, "posX": 0.5, "posY": 0.5,
                         "velocity": 400, "gravity": 100, "radius": 15, "opacity": 100},
                "colors": {"r": 1, "g": 0.2, "b": 0},
                "scale": 2.0,
            },
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {
            "base": {"birthRate": 100, "longevity": 2.0, "posX": 0.5, "posY": 0.5,
                     "velocity": 100, "gravity": 50, "radius": 10, "opacity": 100},
            "colors": {"r": 1, "g": 0.5, "b": 0.2},
            "scale": 1.0,
        }


# ============================================================================
# 4. FractalNoiseGenerator — 分形噪波（matchName: ADBE Fractal Noise）
# ============================================================================


class FractalNoiseGenerator(BaseGenerator):
    """分形噪波生成器，支持 clouds/fire/water/electric/smoke 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        contrast = self._clamp(base["contrast"] * scale_factor, 0, 100)
        brightness = self._clamp(base["brightness"], -100, 100)

        settings: dict[str, Any] = {
            "Fractal Type": base["fractalType"],
            "Noise Type": base["noiseType"],
            "Contrast": contrast,
            "Brightness": brightness,
            "Scale": self._clamp(base["scale"] / scale_factor if scale_factor else base["scale"], 10, 2000),
            "Complexity": self._clamp(base["complexity"], 1, 10),
            "Evolution": 0,
            "Evolution Speed": self._clamp(base["evolutionSpeed"] * scale_factor, 0, 20),
        }

        # 若提供颜色，增强对比度与亮度
        if modifiers.get("color"):
            settings["Contrast"] = self._clamp(contrast + 20, 0, 100)
            settings["Brightness"] = self._clamp(brightness + 10, -100, 100)

        return EffectParams(
            matchName="ADBE Fractal Noise",
            displayName="Fractal Noise",
            settings=settings,
            confidence=0.78,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "clouds": {
                "base": {"fractalType": "Turbulence", "noiseType": "Soft Linear",
                         "contrast": 50, "brightness": 0, "scale": 300, "complexity": 4, "evolutionSpeed": 2},
                "scale": 0.8,
            },
            "fire": {
                "base": {"fractalType": "Turbulence", "noiseType": "Linear",
                         "contrast": 70, "brightness": 20, "scale": 100, "complexity": 6, "evolutionSpeed": 8},
                "scale": 1.4,
            },
            "water": {
                "base": {"fractalType": "Basic", "noiseType": "Soft Linear",
                         "contrast": 40, "brightness": -10, "scale": 200, "complexity": 3, "evolutionSpeed": 3},
                "scale": 0.9,
            },
            "electric": {
                "base": {"fractalType": "Turbulence", "noiseType": "Splatter",
                         "contrast": 90, "brightness": 30, "scale": 50, "complexity": 8, "evolutionSpeed": 15},
                "scale": 1.8,
            },
            "smoke": {
                "base": {"fractalType": "Turbulence", "noiseType": "Soft Linear",
                         "contrast": 30, "brightness": -20, "scale": 400, "complexity": 5, "evolutionSpeed": 1},
                "scale": 0.5,
            },
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {
            "base": {"fractalType": "Turbulence", "noiseType": "Soft Linear",
                     "contrast": 50, "brightness": 0, "scale": 200, "complexity": 5, "evolutionSpeed": 5},
            "scale": 1.0,
        }


# ============================================================================
# 5. RampGenerator — 渐变（matchName: ADBE Ramp）
# ============================================================================


class RampGenerator(BaseGenerator):
    """渐变生成器，支持 sunset/cyberpunk/gradient/radial/warmcool 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        color_refs = modifiers.get("color", [])
        color1 = color_refs[0] if len(color_refs) > 0 else None
        color2 = color_refs[1] if len(color_refs) > 1 else None

        preset = self._get_preset(modifiers.get("style", ""))
        base = preset["base"]

        settings: dict[str, Any] = {
            "Start of Ramp": base["startPoint"],
            "Start Color": color1.get("rgb", preset["colors"]["start"]) if color1 else preset["colors"]["start"],
            "End of Ramp": base["endPoint"],
            "End Color": color2.get("rgb", preset["colors"]["end"]) if color2 else preset["colors"]["end"],
            "Ramp Shape": base["shape"],
            "Ramp Scatter": base["scatter"],
        }

        return EffectParams(
            matchName="ADBE Ramp",
            displayName="Ramp",
            settings=settings,
            confidence=0.85,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "sunset": {
                "base": {"startPoint": [0.5, 0], "endPoint": [0.5, 1], "shape": "Linear Ramp", "scatter": 0},
                "colors": {"start": [1, 0.5, 0.2], "end": [0.2, 0.3, 0.6]},
            },
            "cyberpunk": {
                "base": {"startPoint": [0, 0.5], "endPoint": [1, 0.5], "shape": "Linear Ramp", "scatter": 10},
                "colors": {"start": [0, 0.5, 1], "end": [1, 0.2, 0.8]},
            },
            "gradient": {
                "base": {"startPoint": [0.5, 0], "endPoint": [0.5, 1], "shape": "Linear Ramp", "scatter": 0},
                "colors": {"start": [1, 1, 1], "end": [0.2, 0.2, 0.2]},
            },
            "radial": {
                "base": {"startPoint": [0.5, 0.5], "endPoint": [0.5, 1], "shape": "Radial Ramp", "scatter": 5},
                "colors": {"start": [1, 0.8, 0], "end": [0.1, 0.1, 0.1]},
            },
            "warmcool": {
                "base": {"startPoint": [0, 0.5], "endPoint": [1, 0.5], "shape": "Linear Ramp", "scatter": 0},
                "colors": {"start": [1, 0.7, 0.3], "end": [0.2, 0.6, 1]},
            },
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {
            "base": {"startPoint": [0.5, 0], "endPoint": [0.5, 1], "shape": "Linear Ramp", "scatter": 0},
            "colors": {"start": [1, 1, 1], "end": [0, 0, 0]},
        }


# ============================================================================
# 6. GaussianBlurGenerator — 高斯模糊（matchName: ADBE Gaussian Blur 2）
# ============================================================================


class GaussianBlurGenerator(BaseGenerator):
    """高斯模糊生成器，支持 soft/medium/strong/motionblur/horizontal/vertical 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Blurriness": self._clamp(base["blurriness"] * scale_factor, 0, 500),
            "Blur Dimensions": base["dimensions"],
        }

        return EffectParams(
            matchName="ADBE Gaussian Blur 2",
            displayName="Gaussian Blur",
            settings=settings,
            confidence=0.88,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "soft": {"base": {"blurriness": 3, "dimensions": 3}, "scale": 0.6},
            "medium": {"base": {"blurriness": 10, "dimensions": 3}, "scale": 1.0},
            "strong": {"base": {"blurriness": 30, "dimensions": 3}, "scale": 1.5},
            "motionblur": {"base": {"blurriness": 15, "dimensions": 1}, "scale": 1.2},
            "horizontal": {"base": {"blurriness": 12, "dimensions": 1}, "scale": 1.0},
            "vertical": {"base": {"blurriness": 12, "dimensions": 2}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"blurriness": 10, "dimensions": 3}, "scale": 1.0}


# ============================================================================
# 7. DirectionalBlurGenerator — 方向模糊（matchName: ADBE Directional Blur）
# ============================================================================


class DirectionalBlurGenerator(BaseGenerator):
    """方向模糊生成器，支持 horizontal/vertical/diagonal/motionblur 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Blur Length": self._clamp(base["blurLength"] * scale_factor, 0, 500),
            "Direction": base["direction"],
        }

        return EffectParams(
            matchName="ADBE Directional Blur",
            displayName="Directional Blur",
            settings=settings,
            confidence=0.86,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "horizontal": {"base": {"blurLength": 20, "direction": 90}, "scale": 1.0},
            "vertical": {"base": {"blurLength": 20, "direction": 0}, "scale": 1.0},
            "diagonal": {"base": {"blurLength": 18, "direction": 45}, "scale": 1.0},
            "motionblur": {"base": {"blurLength": 30, "direction": 90}, "scale": 1.4},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"blurLength": 15, "direction": 90}, "scale": 1.0}


# ============================================================================
# 8. HueSaturationGenerator — 色相/饱和度（matchName: ADBE HUE SATURATION）
# ============================================================================


class HueSaturationGenerator(BaseGenerator):
    """色相/饱和度生成器，支持 vibrant/desaturated/warmshift/coolshift 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Channel Control": base["channelControl"],
            "Master Hue": self._clamp(base["masterHue"] * scale_factor, 0, 360),
            "Master Saturation": self._clamp(base["masterSaturation"] * scale_factor, -100, 100),
            "Master Lightness": self._clamp(base["masterLightness"] * scale_factor, -100, 100),
        }

        return EffectParams(
            matchName="ADBE HUE SATURATION",
            displayName="Hue/Saturation",
            settings=settings,
            confidence=0.87,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "vibrant": {"base": {"channelControl": 0, "masterHue": 0,
                                 "masterSaturation": 30, "masterLightness": 0}, "scale": 1.0},
            "desaturated": {"base": {"channelControl": 0, "masterHue": 0,
                                     "masterSaturation": -50, "masterLightness": 0}, "scale": 1.0},
            "warmshift": {"base": {"channelControl": 0, "masterHue": 15,
                                   "masterSaturation": 10, "masterLightness": 0}, "scale": 1.0},
            "coolshift": {"base": {"channelControl": 0, "masterHue": -15,
                                  "masterSaturation": 5, "masterLightness": 0}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"channelControl": 0, "masterHue": 0,
                         "masterSaturation": 10, "masterLightness": 0}, "scale": 1.0}


# ============================================================================
# 9. LevelsGenerator — 色阶（matchName: ADBE Protractor2，替代 Curves）
# ============================================================================


class LevelsGenerator(BaseGenerator):
    """色阶生成器，支持 highcontrast/bright/dark/cinematic/fade 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Input Black": self._clamp(base["inputBlack"] * scale_factor, 0, 255),
            "Input White": self._clamp(base["inputWhite"], 0, 255),
            "Gamma": self._clamp(base["gamma"], 0.1, 10),
            "Output Black": self._clamp(base["outputBlack"], 0, 255),
            "Output White": self._clamp(base["outputWhite"], 0, 255),
        }

        return EffectParams(
            matchName="ADBE Protractor2",
            displayName="Levels",
            settings=settings,
            confidence=0.84,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "highcontrast": {"base": {"inputBlack": 20, "inputWhite": 235, "gamma": 1.0,
                                      "outputBlack": 0, "outputWhite": 255}, "scale": 1.0},
            "bright": {"base": {"inputBlack": 0, "inputWhite": 255, "gamma": 1.3,
                                "outputBlack": 0, "outputWhite": 255}, "scale": 1.0},
            "dark": {"base": {"inputBlack": 10, "inputWhite": 255, "gamma": 0.8,
                             "outputBlack": 0, "outputWhite": 240}, "scale": 1.0},
            "cinematic": {"base": {"inputBlack": 15, "inputWhite": 240, "gamma": 0.9,
                                  "outputBlack": 5, "outputWhite": 245}, "scale": 1.0},
            "fade": {"base": {"inputBlack": 0, "inputWhite": 255, "gamma": 1.0,
                             "outputBlack": 15, "outputWhite": 240}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"inputBlack": 0, "inputWhite": 255, "gamma": 1.0,
                         "outputBlack": 0, "outputWhite": 255}, "scale": 1.0}


# ============================================================================
# 10. ColorBalanceGenerator — 色彩平衡（matchName: ADBE Color Balance）
# ============================================================================


class ColorBalanceGenerator(BaseGenerator):
    """色彩平衡生成器，支持 warm/cool/vintage/cinematic/tealorange 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Shadow Red Balance": self._clamp(base["shadowR"] * scale_factor, -100, 100),
            "Shadow Green Balance": self._clamp(base["shadowG"] * scale_factor, -100, 100),
            "Shadow Blue Balance": self._clamp(base["shadowB"] * scale_factor, -100, 100),
            "Midtone Red Balance": self._clamp(base["midR"] * scale_factor, -100, 100),
            "Midtone Green Balance": self._clamp(base["midG"] * scale_factor, -100, 100),
            "Midtone Blue Balance": self._clamp(base["midB"] * scale_factor, -100, 100),
            "Hilight Red Balance": self._clamp(base["hiR"] * scale_factor, -100, 100),
            "Hilight Green Balance": self._clamp(base["hiG"] * scale_factor, -100, 100),
            "Hilight Blue Balance": self._clamp(base["hiB"] * scale_factor, -100, 100),
        }

        return EffectParams(
            matchName="ADBE Color Balance",
            displayName="Color Balance",
            settings=settings,
            confidence=0.86,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "warm": {"base": {"shadowR": 20, "shadowG": 5, "shadowB": -10,
                              "midR": 5, "midG": 0, "midB": -5,
                              "hiR": 10, "hiG": 5, "hiB": -5}, "scale": 1.0},
            "cool": {"base": {"shadowR": -10, "shadowG": 0, "shadowB": 20,
                             "midR": -5, "midG": 0, "midB": 10,
                             "hiR": -5, "hiG": 5, "hiB": 15}, "scale": 1.0},
            "vintage": {"base": {"shadowR": 10, "shadowG": 10, "shadowB": -5,
                                "midR": 10, "midG": 10, "midB": -5,
                                "hiR": 5, "hiG": 0, "hiB": -5}, "scale": 1.0},
            "cinematic": {"base": {"shadowR": -5, "shadowG": -5, "shadowB": 15,
                                  "midR": 0, "midG": 0, "midB": 5,
                                  "hiR": 15, "hiG": 5, "hiB": -5}, "scale": 1.0},
            "tealorange": {"base": {"shadowR": -15, "shadowG": 5, "shadowB": 20,
                                   "midR": 0, "midG": 0, "midB": 5,
                                   "hiR": 20, "hiG": 5, "hiB": -15}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"shadowR": 0, "shadowG": 0, "shadowB": 0,
                         "midR": 0, "midG": 0, "midB": 0,
                         "hiR": 0, "hiG": 0, "hiB": 0}, "scale": 1.0}


# ============================================================================
# 11. DropShadowGenerator — 投影（matchName: ADBE Drop Shadow）
# ============================================================================


class DropShadowGenerator(BaseGenerator):
    """投影生成器，支持 subtle/medium/dramatic/neon 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Shadow Color": color.get("rgb", base["shadowColor"]) if color else base["shadowColor"],
            "Opacity": self._clamp(base["opacity"] * scale_factor, 0, 255),
            "Direction": base["direction"],
            "Distance": self._clamp(base["distance"] * scale_factor, 0, 3000),
            "Softness": self._clamp(base["softness"] * scale_factor, 0, 100),
        }

        return EffectParams(
            matchName="ADBE Drop Shadow",
            displayName="Drop Shadow",
            settings=settings,
            confidence=0.90,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "subtle": {"base": {"shadowColor": [0, 0, 0], "opacity": 80,
                                "direction": 135, "distance": 2, "softness": 5}, "scale": 0.5},
            "medium": {"base": {"shadowColor": [0, 0, 0], "opacity": 120,
                               "direction": 135, "distance": 5, "softness": 15}, "scale": 1.0},
            "dramatic": {"base": {"shadowColor": [0, 0, 0], "opacity": 180,
                                 "direction": 135, "distance": 10, "softness": 40}, "scale": 1.5},
            "neon": {"base": {"shadowColor": [0, 0.5, 1], "opacity": 200,
                             "direction": 135, "distance": 0, "softness": 30}, "scale": 1.2},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"shadowColor": [0, 0, 0], "opacity": 100,
                         "direction": 135, "distance": 5, "softness": 10}, "scale": 1.0}


# ============================================================================
# 12. FillGenerator — 填充（matchName: ADBE Fill）
# ============================================================================


class FillGenerator(BaseGenerator):
    """填充生成器，支持 red/green/blue/white/black/yellow 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        preset = self._get_preset(modifiers.get("style", ""))

        settings: dict[str, Any] = {
            "Color": color.get("rgb", preset["base"]["color"]) if color else preset["base"]["color"],
        }

        return EffectParams(
            matchName="ADBE Fill",
            displayName="Fill",
            settings=settings,
            confidence=0.92,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "red": {"base": {"color": [1, 0, 0]}},
            "green": {"base": {"color": [0, 0.8, 0.2]}},
            "blue": {"base": {"color": [0, 0.4, 1]}},
            "white": {"base": {"color": [1, 1, 1]}},
            "black": {"base": {"color": [0, 0, 0]}},
            "yellow": {"base": {"color": [1, 0.9, 0]}},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"color": [1, 1, 1]}}


# ============================================================================
# 13. StrokeGenerator — 描边（matchName: ADBE Stroke）
# ============================================================================


class StrokeGenerator(BaseGenerator):
    """描边生成器，支持 thin/thick/soft/animated 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Color": color.get("rgb", base["color"]) if color else base["color"],
            "Brush Size": self._clamp(base["brushSize"] * scale_factor, 1, 100),
            "Brush Hardness": self._clamp(base["brushHardness"], 0, 1),
            "Opacity": self._clamp(base["opacity"] * scale_factor, 0, 100),
            "Start": base["start"],
            "End": base["end"],
        }

        return EffectParams(
            matchName="ADBE Stroke",
            displayName="Stroke",
            settings=settings,
            confidence=0.84,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "thin": {"base": {"color": [1, 1, 1], "brushSize": 2, "brushHardness": 0.95,
                             "opacity": 100, "start": 0, "end": 100}, "scale": 0.5},
            "thick": {"base": {"color": [1, 1, 1], "brushSize": 10, "brushHardness": 0.8,
                              "opacity": 100, "start": 0, "end": 100}, "scale": 1.5},
            "soft": {"base": {"color": [1, 1, 1], "brushSize": 6, "brushHardness": 0.3,
                             "opacity": 70, "start": 0, "end": 100}, "scale": 1.0},
            "animated": {"base": {"color": [1, 1, 1], "brushSize": 4, "brushHardness": 0.9,
                                 "opacity": 100, "start": 0, "end": 0}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"color": [1, 1, 1], "brushSize": 4, "brushHardness": 0.9,
                         "opacity": 100, "start": 0, "end": 100}, "scale": 1.0}


# ============================================================================
# 14. NoiseGenerator — 噪波（matchName: ADBE Noise）
# ============================================================================


class NoiseGenerator(BaseGenerator):
    """噪波生成器，支持 filmgrain/heavy/interference/subtle 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Amount of Noise": self._clamp(base["amount"] * scale_factor, 0, 100),
            "Noise Type": base["noiseType"],
            "Clipping": base["clipping"],
        }

        return EffectParams(
            matchName="ADBE Noise",
            displayName="Noise",
            settings=settings,
            confidence=0.83,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "filmgrain": {"base": {"amount": 4, "noiseType": 1, "clipping": 0}, "scale": 0.6},
            "heavy": {"base": {"amount": 30, "noiseType": 0, "clipping": 0}, "scale": 1.5},
            "interference": {"base": {"amount": 50, "noiseType": 0, "clipping": 1}, "scale": 2.0},
            "subtle": {"base": {"amount": 2, "noiseType": 1, "clipping": 0}, "scale": 0.4},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"amount": 5, "noiseType": 0, "clipping": 0}, "scale": 1.0}


# ============================================================================
# 15. SharpenGenerator — 锐化（matchName: ADBE Sharpen）
# ============================================================================


class SharpenGenerator(BaseGenerator):
    """锐化生成器，支持 subtle/medium/strong/ultra 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Sharpen Amount": self._clamp(base["amount"] * scale_factor, 0, 100),
        }

        return EffectParams(
            matchName="ADBE Sharpen",
            displayName="Sharpen",
            settings=settings,
            confidence=0.85,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "subtle": {"base": {"amount": 10}, "scale": 0.5},
            "medium": {"base": {"amount": 25}, "scale": 1.0},
            "strong": {"base": {"amount": 50}, "scale": 1.5},
            "ultra": {"base": {"amount": 80}, "scale": 2.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"amount": 20}, "scale": 1.0}


# ============================================================================
# 16. TexturizeGenerator — 纹理化（matchName: ADBE Texturize）
# ============================================================================


class TexturizeGenerator(BaseGenerator):
    """纹理化生成器，支持 subtle/medium/strong/grunge 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Texture Layer": base["textureLayer"],
            "Texture Placement": base["texturePlacement"],
            "Texture Contrast": self._clamp(base["contrast"] * scale_factor, 0, 200),
            "Texture Brightness": self._clamp(base["brightness"], -100, 100),
            "Composite Operation": base["compositeOp"],
        }

        return EffectParams(
            matchName="ADBE Texturize",
            displayName="Texturize",
            settings=settings,
            confidence=0.75,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "subtle": {"base": {"textureLayer": 1, "texturePlacement": 0, "contrast": 50,
                               "brightness": 0, "compositeOp": 1}, "scale": 0.5},
            "medium": {"base": {"textureLayer": 1, "texturePlacement": 0, "contrast": 100,
                               "brightness": 0, "compositeOp": 1}, "scale": 1.0},
            "strong": {"base": {"textureLayer": 1, "texturePlacement": 0, "contrast": 150,
                               "brightness": 10, "compositeOp": 2}, "scale": 1.5},
            "grunge": {"base": {"textureLayer": 1, "texturePlacement": 1, "contrast": 180,
                               "brightness": -20, "compositeOp": 3}, "scale": 2.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"textureLayer": 1, "texturePlacement": 0, "contrast": 100,
                         "brightness": 0, "compositeOp": 1}, "scale": 1.0}


# ============================================================================
# 17. RoughenEdgesGenerator — 粗糙边缘（matchName: ADBE Roughen Edges）
# ============================================================================


class RoughenEdgesGenerator(BaseGenerator):
    """粗糙边缘生成器，支持 rough/spiky/rusty/organic 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Edge Type": base["edgeType"],
            "Edge Color": color.get("rgb", base["edgeColor"]) if color else base["edgeColor"],
            "Border": self._clamp(base["border"] * scale_factor, 0, 200),
            "Edge Sharpness": self._clamp(base["edgeSharpness"], 0, 10),
            "Fractal Influence": self._clamp(base["fractalInfluence"], 0, 1),
            "Scale": self._clamp(base["scale"], 10, 5000),
            "Complexity": self._clamp(base["complexity"], 1, 10),
            "Evolution": base["evolution"],
        }

        return EffectParams(
            matchName="ADBE Roughen Edges",
            displayName="Roughen Edges",
            settings=settings,
            confidence=0.80,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "rough": {"base": {"edgeType": 1, "edgeColor": [0.5, 0.5, 0.5], "border": 20,
                              "edgeSharpness": 1, "fractalInfluence": 0.5, "scale": 100,
                              "complexity": 3, "evolution": 0}, "scale": 1.0},
            "spiky": {"base": {"edgeType": 2, "edgeColor": [0.3, 0.3, 0.3], "border": 30,
                              "edgeSharpness": 5, "fractalInfluence": 0.8, "scale": 50,
                              "complexity": 6, "evolution": 0}, "scale": 1.3},
            "rusty": {"base": {"edgeType": 3, "edgeColor": [0.6, 0.3, 0.1], "border": 40,
                              "edgeSharpness": 2, "fractalInfluence": 0.6, "scale": 80,
                              "complexity": 5, "evolution": 0}, "scale": 1.2},
            "organic": {"base": {"edgeType": 4, "edgeColor": [0.4, 0.5, 0.2], "border": 15,
                                "edgeSharpness": 3, "fractalInfluence": 0.7, "scale": 200,
                                "complexity": 4, "evolution": 0}, "scale": 0.8},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"edgeType": 1, "edgeColor": [0.5, 0.5, 0.5], "border": 15,
                         "edgeSharpness": 2, "fractalInfluence": 0.5, "scale": 100,
                         "complexity": 3, "evolution": 0}, "scale": 1.0}


# ============================================================================
# 18. CCLensGenerator — CC 镜头（matchName: CC Lens）
# ============================================================================


class CCLensGenerator(BaseGenerator):
    """CC 镜头生成器，支持 fisheye/wideangle/barrel/pincushion 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Size": self._clamp(base["size"] * scale_factor, 0, 300),
            "Curvature": self._clamp(base["curvature"] * scale_factor, -100, 100),
        }

        return EffectParams(
            matchName="CC Lens",
            displayName="CC Lens",
            settings=settings,
            confidence=0.82,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "fisheye": {"base": {"size": 100, "curvature": 80}, "scale": 1.0},
            "wideangle": {"base": {"size": 120, "curvature": 40}, "scale": 0.8},
            "barrel": {"base": {"size": 80, "curvature": 50}, "scale": 1.0},
            "pincushion": {"base": {"size": 80, "curvature": -50}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"size": 100, "curvature": 30}, "scale": 1.0}


# ============================================================================
# 19. OpticsCompensationGenerator — 光学补偿（matchName: ADBE Optics Compensation）
# ============================================================================


class OpticsCompensationGenerator(BaseGenerator):
    """光学补偿生成器，支持 mild/moderate/strong/reverse 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Field of View (FOV)": self._clamp(base["fov"] * scale_factor, 1, 200),
            "Reverse Lens Distortion": base["reverseLens"],
            "FOV Orientation": base["fovOrientation"],
        }

        return EffectParams(
            matchName="ADBE Optics Compensation",
            displayName="Optics Compensation",
            settings=settings,
            confidence=0.83,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "mild": {"base": {"fov": 15, "reverseLens": 0, "fovOrientation": 0}, "scale": 0.5},
            "moderate": {"base": {"fov": 30, "reverseLens": 0, "fovOrientation": 0}, "scale": 1.0},
            "strong": {"base": {"fov": 60, "reverseLens": 0, "fovOrientation": 0}, "scale": 1.5},
            "reverse": {"base": {"fov": 30, "reverseLens": 1, "fovOrientation": 0}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"fov": 20, "reverseLens": 0, "fovOrientation": 0}, "scale": 1.0}


# ============================================================================
# 20. SimpleChokerGenerator — 简单抑制（matchName: ADBE Simple Choker）
# ============================================================================


class SimpleChokerGenerator(BaseGenerator):
    """简单抑制生成器，支持 shrink/expand/tight/loose/subtle 预设"""

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        preset = self._get_preset(modifiers.get("style", ""))
        scale_factor = intensity_scale * preset["scale"]
        base = preset["base"]

        settings: dict[str, Any] = {
            "Choke Matte": self._clamp(base["chokeMatte"] * scale_factor, -200, 200),
        }

        return EffectParams(
            matchName="ADBE Simple Choker",
            displayName="Simple Choker",
            settings=settings,
            confidence=0.88,
        )

    def _get_preset(self, style: str) -> dict:
        presets = {
            "shrink": {"base": {"chokeMatte": 5}, "scale": 1.0},
            "expand": {"base": {"chokeMatte": -5}, "scale": 1.0},
            "tight": {"base": {"chokeMatte": 15}, "scale": 1.0},
            "loose": {"base": {"chokeMatte": -15}, "scale": 1.0},
            "subtle": {"base": {"chokeMatte": 2}, "scale": 1.0},
        }

        style_lower = (style or "").lower()
        for key, preset in presets.items():
            if key in style_lower:
                return preset

        return {"base": {"chokeMatte": 0}, "scale": 1.0}


# ============================================================================
# UniversalEffectGenerator - 通用效果生成器
# 当没有专用生成器时使用，从 EffectKnowledgeGraph 读取默认参数
# ============================================================================


class UniversalEffectGenerator(BaseGenerator):
    """通用效果生成器，基于知识图谱自动生成任意效果的参数"""

    def __init__(self, match_name: str, context: GeneratorContext = None):
        super().__init__(context)
        self.match_name = match_name
        node = EFFECT_KNOWLEDGE_GRAPH.get(match_name)
        if node is None:
            raise ValueError(f"Effect not found in knowledge graph: {match_name}")
        self.effect_node: EffectNode = node

    def generate(self, modifiers: dict) -> EffectParams:
        intensity_scale = self._get_intensity_scale(modifiers.get("intensity", []))
        color_refs = modifiers.get("color", [])
        color = color_refs[0] if color_refs else None
        style = modifiers.get("style", "") or ""

        settings: dict[str, Any] = {}
        for param in self.effect_node.parameters:
            settings[param.name] = self._generate_param_value(param, intensity_scale, color, style)

        self._apply_style_overrides(settings, style, intensity_scale, color)

        return EffectParams(
            matchName=self.match_name,
            displayName=self.effect_node.display_name,
            settings=settings,
            confidence=self.effect_node.confidence,
        )

    def _generate_param_value(
        self,
        param: EffectParameter,
        intensity_scale: float,
        color: dict | None,
        style: str,
    ) -> Any:
        """根据参数类型生成单个参数值"""
        param_type = param.param_type

        if param_type == "number":
            base_value = float(param.default) if param.default is not None else 0.0
            scale = param.intensity_scale or 0.0
            if scale > 0 and intensity_scale != 1.0:
                scaled = base_value * (1 + (intensity_scale - 1) * scale)
                min_v = param.min_val if param.min_val is not None else float("-inf")
                max_v = param.max_val if param.max_val is not None else float("inf")
                return self._clamp(scaled, min_v, max_v)
            return base_value

        if param_type == "color":
            if color and self._is_color_param_sensitive(param.name):
                return color.get("rgb", [1, 1, 1])
            return param.default if param.default is not None else [1, 1, 1]

        if param_type == "enum":
            enum_override = self._get_enum_override(param.name, style)
            if enum_override and param.enum_values and enum_override in param.enum_values:
                return enum_override
            if param.default is not None:
                return param.default
            return param.enum_values[0] if param.enum_values else ""

        if param_type == "boolean":
            return 1 if param.default is True else 0

        if param_type == "point":
            return param.default if param.default is not None else [0.5, 0.5]

        return param.default if param.default is not None else 0

    def _is_color_param_sensitive(self, param_name: str) -> bool:
        """判断参数是否对颜色修饰词敏感"""
        color_keywords = ["color", "tint", "tone", "hue", "glow color", "shadow color"]
        lower_name = param_name.lower()
        return any(kw in lower_name for kw in color_keywords)

    def _get_enum_override(self, param_name: str, style: str) -> str | None:
        """根据风格覆盖枚举值"""
        style_lower = style.lower()
        param_lower = param_name.lower()

        if "blur dimensions" in param_lower or "dimensions" in param_lower:
            if "horizontal" in style_lower:
                return "Horizontal"
            if "vertical" in style_lower:
                return "Vertical"

        if "ramp shape" in param_lower or "shape" in param_lower:
            if "radial" in style_lower:
                return "Radial Ramp"
            if "linear" in style_lower:
                return "Linear Ramp"

        if "render" in param_lower:
            if "fill" in style_lower:
                return "Fill"
            if "edge" in style_lower:
                return "Edges"

        return None

    def _apply_style_overrides(
        self,
        settings: dict[str, Any],
        style: str,
        intensity_scale: float,
        color: dict | None,
    ) -> None:
        """根据风格整体缩放数值参数"""
        style_lower = style.lower()

        if "subtle" in style_lower or "mild" in style_lower or "轻微" in style:
            self._scale_all_number_params(settings, 0.5)
        elif "strong" in style_lower or "intense" in style_lower or "强烈" in style:
            self._scale_all_number_params(settings, 1.5)
        elif "extreme" in style_lower or "massive" in style_lower or "极端" in style:
            self._scale_all_number_params(settings, 2.0)

    def _scale_all_number_params(self, settings: dict[str, Any], factor: float) -> None:
        """对所有带 intensity_scale 的数值参数按因子缩放"""
        for param in self.effect_node.parameters:
            if param.param_type == "number" and param.intensity_scale and param.intensity_scale > 0:
                current = settings.get(param.name, 0)
                if not isinstance(current, (int, float)):
                    continue
                base_value = float(param.default) if param.default is not None else 0.0
                diff = current - base_value
                min_v = param.min_val if param.min_val is not None else float("-inf")
                max_v = param.max_val if param.max_val is not None else float("inf")
                settings[param.name] = self._clamp(base_value + diff * factor, min_v, max_v)


# ============================================================================
# SPECIALIZED_GENERATORS - 专用效果生成器映射（20 个）
# ============================================================================

SPECIALIZED_GENERATORS: dict[str, type] = {
    "ADBE Glo2": GlowGenerator,
    "ADBE Color Key": ColorKeyGenerator,
    "CC Particle World": CCParticleWorldGenerator,
    "ADBE Fractal Noise": FractalNoiseGenerator,
    "ADBE Ramp": RampGenerator,
    "ADBE Gaussian Blur 2": GaussianBlurGenerator,
    "ADBE Directional Blur": DirectionalBlurGenerator,
    "ADBE HUE SATURATION": HueSaturationGenerator,
    "ADBE Protractor2": LevelsGenerator,
    "ADBE Color Balance": ColorBalanceGenerator,
    "ADBE Drop Shadow": DropShadowGenerator,
    "ADBE Fill": FillGenerator,
    "ADBE Stroke": StrokeGenerator,
    "ADBE Noise": NoiseGenerator,
    "ADBE Sharpen": SharpenGenerator,
    "ADBE Texturize": TexturizeGenerator,
    "ADBE Roughen Edges": RoughenEdgesGenerator,
    "CC Lens": CCLensGenerator,
    "ADBE Optics Compensation": OpticsCompensationGenerator,
    "ADBE Simple Choker": SimpleChokerGenerator,
}

# ============================================================================
# ALL_EFFECT_MATCHNAMES - 所有 20 个专用效果的 matchName
# ============================================================================

ALL_EFFECT_MATCHNAMES: list[str] = list(SPECIALIZED_GENERATORS.keys())


def _get_generator_class(match_name: str) -> type:
    """根据 matchName 获取生成器类：优先专用，否则通用"""
    specialized = SPECIALIZED_GENERATORS.get(match_name)
    if specialized is not None:
        return specialized
    if match_name in EFFECT_KNOWLEDGE_GRAPH:
        # 动态构造通用生成器子类，绑定 matchName
        return _build_universal_subclass(match_name)
    raise ValueError(f"Effect not found: {match_name}")


def _build_universal_subclass(match_name: str) -> type:
    """为指定 matchName 构造一个 UniversalEffectGenerator 子类"""
    return type(
        "_Universal_" + re.sub(r"[^A-Za-z0-9]", "_", match_name),
        (UniversalEffectGenerator,),
        {"__init__": lambda self, context=None, _mn=match_name: UniversalEffectGenerator.__init__(self, _mn, context)},
    )


# ============================================================================
# GENERATOR_REGISTRY - 所有效果的生成器类映射
# 专用生成器优先；知识图谱中的其余效果使用通用生成器
# ============================================================================

GENERATOR_REGISTRY: dict[str, type] = {}
for _match_name in EFFECT_KNOWLEDGE_GRAPH.keys():
    GENERATOR_REGISTRY[_match_name] = _get_generator_class(_match_name)


# ============================================================================
# EffectGeneratorFactory - 效果生成器工厂
# ============================================================================


class EffectGeneratorFactory:
    """效果生成器工厂：管理所有生成器实例，按名称或 matchName 生成效果参数"""

    def __init__(self, context: GeneratorContext = None):
        self.context: GeneratorContext = context if context is not None else GeneratorContext()
        # 生成器实例缓存：规范化名称 -> BaseGenerator
        self._generators: dict[str, BaseGenerator] = {}
        self._init_all_generators()

    def _init_all_generators(self) -> None:
        """初始化所有可用生成器（专用 + 通用），按 matchName 与 displayName 双重索引"""
        for match_name in EFFECT_KNOWLEDGE_GRAPH.keys():
            generator = self._create_generator(match_name)
            # 以 matchName 规范化作为主键
            self._generators[self._normalize_name(match_name)] = generator
            # 同时以 displayName 规范化作为别名
            display_name = EFFECT_KNOWLEDGE_GRAPH[match_name].display_name
            self._generators[self._normalize_name(display_name)] = generator

    def _create_generator(self, match_name: str) -> BaseGenerator:
        """创建单个生成器实例"""
        generator_class = _get_generator_class(match_name)
        return generator_class(self.context)

    @staticmethod
    def _normalize_name(name: str) -> str:
        """将名称归一化为小写无符号字符串，用于查找"""
        return re.sub(r"[^a-z0-9]", "", name.lower())

    def get_generator(self, effect_name: str) -> BaseGenerator:
        """根据效果名（matchName 或 displayName）获取生成器实例"""
        key = self._normalize_name(effect_name)
        generator = self._generators.get(key)
        if generator is None:
            raise ValueError(f"Generator not found for effect: {effect_name}")
        return generator

    def get_generator_by_match_name(self, match_name: str) -> BaseGenerator:
        """根据 matchName 获取生成器实例"""
        return self.get_generator(match_name)

    def list_available_generators(self) -> list[str]:
        """列出所有可用效果的 matchName"""
        return list(EFFECT_KNOWLEDGE_GRAPH.keys())

    def get_effect_count(self) -> int:
        """返回可用效果总数"""
        return len(EFFECT_KNOWLEDGE_GRAPH)

    def get_effects_by_category(self, category: str) -> list[str]:
        """按类别筛选效果 matchName 列表"""
        return [
            name for name, node in EFFECT_KNOWLEDGE_GRAPH.items()
            if node.category == category
        ]

    def generate_effect(self, effect_name: str, modifiers: dict) -> EffectParams:
        """根据效果名生成效果参数"""
        return self.get_generator(effect_name).generate(modifiers)

    def generate_effect_by_match_name(self, match_name: str, modifiers: dict) -> EffectParams:
        """根据 matchName 生成效果参数"""
        return self.get_generator_by_match_name(match_name).generate(modifiers)

    def set_context(self, context: GeneratorContext) -> None:
        """更新上下文，并同步到所有已缓存的生成器实例"""
        self.context = context
        for generator in self._generators.values():
            generator.context = context


# 模块级默认工厂实例（对齐 TS 端 effectGeneratorFactory）
effect_generator_factory = EffectGeneratorFactory()
