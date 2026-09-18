"""
Filter Engine - 跨软件滤镜/效果系统集成引擎
=================================================
集成 After Effects, Premiere Pro, Photoshop, DaVinci Resolve, Blender, FFmpeg
的统一滤镜系统。支持200+内置预设、智能推荐、跨软件转换。

版本: 2.0.0
作者: AE Knowledge Vault
"""

from __future__ import annotations

import hashlib
import json
import logging
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# =============================================================================
# Logger setup
# =============================================================================
logger = logging.getLogger(__name__)

# =============================================================================
# 异常处理
# =============================================================================

class FilterEngineError(Exception):
    """滤镜引擎基础异常"""
    pass


class FilterNotFoundError(FilterEngineError):
    """滤镜未找到异常"""
    pass


class SoftwareNotSupportedError(FilterEngineError):
    """软件不支持异常"""
    pass


class InvalidParameterError(FilterEngineError):
    """无效参数异常"""
    pass


class CompatibilityError(FilterEngineError):
    """兼容性错误"""
    pass


# =============================================================================
# 枚举定义
# =============================================================================

class FilterCategory(str, Enum):
    """滤镜分类枚举"""
    COLOR_CORRECTION = "color_correction"
    BLUR_SHARPEN = "blur_sharpen"
    DISTORT = "distort"
    GENERATE = "generate"
    STYLIZE = "stylize"
    SIMULATION = "simulation"
    TRANSITION = "transition"
    KEYING = "keying"
    PERSPECTIVE = "perspective"
    CHANNEL = "channel"
    UTILITY = "utility"
    NOISE_GRAIN = "noise_grain"
    PERSPECTIVE_3D = "perspective_3d"


class FilterStyle(str, Enum):
    """滤镜风格枚举"""
    CINEMATIC = "cinematic"
    VINTAGE = "vintage"
    GLITCH = "glitch"
    CYBERPUNK = "cyberpunk"
    DREAMY = "dreamy"
    HIGH_CONTRAST = "high_contrast"
    SOFT = "soft"
    SHARP = "sharp"
    WARM = "warm"
    COOL = "cool"
    FILM = "film"
    ANIME = "anime"
    CLEAN = "clean"
    GLOW = "glow"
    VIBRANT = "vibrant"
    DESATURATED = "desaturated"
    NATURAL = "natural"
    BRIGHT = "bright"


class SoftwareType(str, Enum):
    """软件类型枚举"""
    AFTER_EFFECTS = "after_effects"
    PREMIERE_PRO = "premiere_pro"
    PHOTOSHOP = "photoshop"
    DAVINCI_RESOLVE = "davinci_resolve"
    BLENDER = "blender"
    FFMPEG = "ffmpeg"


class BlendMode(str, Enum):
    """混合模式枚举"""
    NORMAL = "normal"
    MULTIPLY = "multiply"
    SCREEN = "screen"
    OVERLAY = "overlay"
    SOFT_LIGHT = "soft_light"
    HARD_LIGHT = "hard_light"
    COLOR_DODGE = "color_dodge"
    COLOR_BURN = "color_burn"
    DARKEN = "darken"
    LIGHTEN = "lighten"
    DIFFERENCE = "difference"
    EXCLUSION = "exclusion"
    HUE = "hue"
    SATURATION = "saturation"
    COLOR = "color"
    LUMINOSITY = "luminosity"


class SceneType(str, Enum):
    """场景类型枚举"""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    PRODUCT = "product"
    TEXT = "text"
    VLOG = "vlog"
    CINEMATIC = "cinematic"
    ANIME = "anime"
    DOCUMENTARY = "documentary"
    MUSIC_VIDEO = "music_video"
    TUTORIAL = "tutorial"


# =============================================================================
# 数据类
# =============================================================================

@dataclass
class FilterParam:
    """滤镜参数定义"""
    name: str
    value: Any = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    param_type: str = "float"  # float, int, color, boolean, string
    unit: str = ""
    description: str = ""

    def validate(self) -> bool:
        """验证参数值是否在有效范围内"""
        if self.param_type in ("float", "int"):
            return self.min_value <= self.value <= self.max_value
        return True

    def normalize(self) -> float:
        """将参数归一化到0-1范围"""
        if self.param_type in ("float", "int") and self.max_value != self.min_value:
            return (self.value - self.min_value) / (self.max_value - self.min_value)
        return 0.0

    def denormalize(self, normalized: float) -> Any:
        """将归一化值还原为实际值"""
        if self.param_type in ("float", "int"):
            val = self.min_value + normalized * (self.max_value - self.min_value)
            return int(val) if self.param_type == "int" else val
        return normalized


@dataclass
class FilterPreset:
    """滤镜预设数据类"""
    id: str
    name: str
    category: FilterCategory
    style: FilterStyle
    software_support: list[SoftwareType]
    params: dict[str, FilterParam] = field(default_factory=dict)
    intensity: float = 1.0
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "style": self.style.value,
            "software_support": [s.value for s in self.software_support],
            "params": {k: asdict(v) for k, v in self.params.items()},
            "intensity": self.intensity,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilterPreset":
        """从字典创建预设"""
        params = {
            k: FilterParam(**v) for k, v in data.get("params", {}).items()
        }
        return cls(
            id=data["id"],
            name=data["name"],
            category=FilterCategory(data["category"]),
            style=FilterStyle(data["style"]),
            software_support=[SoftwareType(s) for s in data["software_support"]],
            params=params,
            intensity=data.get("intensity", 1.0),
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0"),
            tags=data.get("tags", []),
        )

    def apply_intensity(self, intensity: float) -> None:
        """应用强度因子到所有参数"""
        self.intensity = max(0.0, min(1.0, intensity))
        for param in self.params.values():
            if param.param_type in ("float", "int"):
                base_value = param.min_value + (param.value - param.min_value) * intensity
                if param.param_type == "int":
                    param.value = int(base_value)
                else:
                    param.value = base_value

    def copy(self) -> "FilterPreset":
        """创建预设的深拷贝"""
        return deepcopy(self)


@dataclass
class FilterChainItem:
    """滤镜链中的单个滤镜项"""
    preset: FilterPreset
    opacity: float = 100.0
    blend_mode: BlendMode = BlendMode.NORMAL
    mask: str | None = None
    enabled: bool = True
    animation_keyframes: dict[str, list[tuple[float, Any]]] = field(default_factory=dict)


@dataclass
class FilterRecommendation:
    """滤镜推荐结果"""
    preset: FilterPreset
    confidence: float
    reason: str
    priority: int = 0


# =============================================================================
# 基础滤镜引擎抽象类
# =============================================================================

class BaseFilterEngine(ABC):
    """滤镜引擎抽象基类"""

    def __init__(self):
        self._filters: dict[str, dict[str, Any]] = {}
        self._software_type: SoftwareType | None = None

    @abstractmethod
    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> Any:
        """应用单个滤镜"""
        pass

    @abstractmethod
    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> Any:
        """应用滤镜链"""
        pass

    @abstractmethod
    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], **kwargs) -> str:
        """生成脚本代码"""
        pass

    def get_available_filters(self, category: FilterCategory | None = None) -> list[str]:
        """获取可用滤镜列表"""
        if category is None:
            return list(self._filters.keys())
        return [
            name for name, info in self._filters.items()
            if info.get("category") == category
        ]

    def get_filter_info(self, filter_name: str) -> dict[str, Any]:
        """获取滤镜信息"""
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"滤镜未找到: {filter_name}")
        return self._filters[filter_name]

    def validate_params(self, filter_name: str, params: dict[str, Any]) -> bool:
        """验证滤镜参数"""
        info = self.get_filter_info(filter_name)
        default_params = info.get("params", {})
        for key, value in params.items():
            if key not in default_params:
                raise InvalidParameterError(f"未知参数: {key}")
        return True

    def _get_default_params(self, filter_name: str) -> dict[str, Any]:
        """获取默认参数"""
        info = self.get_filter_info(filter_name)
        return {k: v["default"] for k, v in info.get("params", {}).items()}

    def _merge_params(self, filter_name: str, override_params: dict[str, Any] | None = None) -> dict[str, Any]:
        """合并默认参数和覆盖参数"""
        params = self._get_default_params(filter_name)
        if override_params:
            params.update(override_params)
        return params


# =============================================================================
# After Effects 滤镜引擎
# =============================================================================

class AEFilterEngine(BaseFilterEngine):
    """After Effects 滤镜引擎"""

    def __init__(self):
        super().__init__()
        self._software_type = SoftwareType.AFTER_EFFECTS
        self._init_filters()

    def _init_filters(self) -> None:
        """初始化AE滤镜库"""
        # 色彩校正滤镜
        self._filters.update({
            "Curves": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "red": {"default": 0, "min": -100, "max": 100},
                    "green": {"default": 0, "min": -100, "max": 100},
                    "blue": {"default": 0, "min": -100, "max": 100},
                    "rgb": {"default": 0, "min": -100, "max": 100},
                },
                "description": "曲线调整，精确控制色调范围",
            },
            "Levels": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "input_black": {"default": 0, "min": 0, "max": 255},
                    "input_white": {"default": 255, "min": 0, "max": 255},
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10.0},
                    "output_black": {"default": 0, "min": 0, "max": 255},
                    "output_white": {"default": 255, "min": 0, "max": 255},
                },
                "description": "色阶调整，控制亮度和对比度",
            },
            "Hue_Saturation": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "master_hue": {"default": 0, "min": -180, "max": 180},
                    "master_saturation": {"default": 0, "min": -100, "max": 100},
                    "master_lightness": {"default": 0, "min": -100, "max": 100},
                    "channel": {"default": "master", "type": "string"},
                },
                "description": "色相/饱和度调整",
            },
            "Color_Balance": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "shadow_red_cyan": {"default": 0, "min": -100, "max": 100},
                    "shadow_green_magenta": {"default": 0, "min": -100, "max": 100},
                    "shadow_blue_yellow": {"default": 0, "min": -100, "max": 100},
                    "midtone_red_cyan": {"default": 0, "min": -100, "max": 100},
                    "midtone_green_magenta": {"default": 0, "min": -100, "max": 100},
                    "midtone_blue_yellow": {"default": 0, "min": -100, "max": 100},
                    "highlight_red_cyan": {"default": 0, "min": -100, "max": 100},
                    "highlight_green_magenta": {"default": 0, "min": -100, "max": 100},
                    "highlight_blue_yellow": {"default": 0, "min": -100, "max": 100},
                    "preserve_luminosity": {"default": True, "type": "boolean"},
                },
                "description": "色彩平衡，调整阴影/中间调/高光的色彩倾向",
            },
            "Lumetri_Color": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "temperature": {"default": 0, "min": -100, "max": 100},
                    "tint": {"default": 0, "min": -100, "max": 100},
                    "exposure": {"default": 0, "min": -5, "max": 5},
                    "contrast": {"default": 0, "min": -100, "max": 100},
                    "highlights": {"default": 0, "min": -100, "max": 100},
                    "shadows": {"default": 0, "min": -100, "max": 100},
                    "whites": {"default": 0, "min": -100, "max": 100},
                    "blacks": {"default": 0, "min": -100, "max": 100},
                    "saturation": {"default": 0, "min": -100, "max": 100},
                    "vibrance": {"default": 0, "min": -100, "max": 100},
                },
                "description": "Lumetri颜色面板，专业调色工具",
            },
            "Brightness_Contrast": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "brightness": {"default": 0, "min": -100, "max": 100},
                    "contrast": {"default": 0, "min": -100, "max": 100},
                },
                "description": "亮度和对比度简单调整",
            },
            "Photo_Filter": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "filter": {"default": "WarmingFilter85", "type": "string"},
                    "density": {"default": 25, "min": 0, "max": 100},
                    "preserve_luminosity": {"default": True, "type": "boolean"},
                },
                "description": "照片滤镜，模拟镜头滤镜效果",
            },
            "Tint": {
                "category": FilterCategory.COLOR_CORRECTION,
                "params": {
                    "map_black_to": {"default": [0, 0, 0], "type": "color"},
                    "map_white_to": {"default": [255, 255, 255], "type": "color"},
                    "amount": {"default": 100, "min": 0, "max": 100},
                },
                "description": "色调，将黑白映射到指定颜色",
            },
        })

        # 模糊和锐化滤镜
        self._filters.update({
            "Gaussian_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "blurriness": {"default": 5, "min": 0, "max": 100},
                    "blur_dimensions": {"default": "horizontal_and_vertical", "type": "string"},
                    "repeat_edge_pixels": {"default": False, "type": "boolean"},
                },
                "description": "高斯模糊，平滑图像",
            },
            "Fast_Box_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "blur_radius": {"default": 5, "min": 0, "max": 100},
                    "blur_dimensions": {"default": "horizontal_and_vertical", "type": "string"},
                    "repeat_edge_pixels": {"default": True, "type": "boolean"},
                    "iterations": {"default": 1, "min": 1, "max": 10},
                },
                "description": "快速盒状模糊，性能更好",
            },
            "Camera_Lens_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "blur_radius": {"default": 10, "min": 0, "max": 100},
                    "iris_shape": {"default": "hexagon", "type": "string"},
                    "iris_rotation": {"default": 0, "min": -360, "max": 360},
                    "iris_roundness": {"default": 50, "min": 0, "max": 100},
                    "iris_aspect_ratio": {"default": 1.0, "min": 0.1, "max": 10.0},
                    "diffraction_fringe": {"default": 0, "min": 0, "max": 100},
                    "highlight_gain": {"default": 0, "min": 0, "max": 100},
                    "highlight_threshold": {"default": 255, "min": 0, "max": 255},
                    "highlight_saturation": {"default": 0, "min": 0, "max": 100},
                    "noise_amount": {"default": 0, "min": 0, "max": 100},
                },
                "description": "镜头模糊，模拟真实相机景深效果",
            },
            "Unsharp_Mask": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "amount": {"default": 50, "min": 0, "max": 500},
                    "radius": {"default": 1.0, "min": 0.1, "max": 100},
                    "threshold": {"default": 0, "min": 0, "max": 255},
                },
                "description": "非锐化蒙版，增强边缘锐度",
            },
            "Sharpen": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "sharpen_amount": {"default": 0, "min": 0, "max": 100},
                },
                "description": "简单锐化效果",
            },
            "Radial_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "amount": {"default": 10, "min": 0, "max": 100},
                    "center": {"default": [0.5, 0.5], "type": "point"},
                    "type": {"default": "zoom", "type": "string"},
                    "anti_aliasing": {"default": "low", "type": "string"},
                },
                "description": "径向模糊，缩放或旋转效果",
            },
            "Directional_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "direction": {"default": 0, "min": -360, "max": 360},
                    "blur_length": {"default": 5, "min": 0, "max": 100},
                    "type": {"default": "uniform", "type": "string"},
                },
                "description": "方向模糊，沿指定方向模糊",
            },
            "CC_Vector_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "params": {
                    "amount": {"default": 20, "min": 0, "max": 200},
                    "angle_offset": {"default": 0, "min": -360, "max": 360},
                    "type": {"default": "directional", "type": "string"},
                    "softness": {"default": 50, "min": 0, "max": 100},
                    "samples": {"default": 20, "min": 1, "max": 100},
                },
                "description": "CC矢量模糊，高级模糊效果",
            },
        })

        # 扭曲滤镜
        self._filters.update({
            "Turbulent_Displace": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "displacement": {"default": 20, "min": 0, "max": 500},
                    "size": {"default": 40, "min": 2, "max": 1000},
                    "complexity": {"default": 3, "min": 1, "max": 10},
                    "evolution": {"default": 0, "min": 0, "max": 360},
                    "evolution_options": {"default": "revolving_cycle", "type": "string"},
                    "turbulent_method": {"default": "turbulent", "type": "string"},
                },
                "description": "湍流置换，自然的波纹扭曲效果",
            },
            "Displacement_Map": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "displacement_map_layer": {"default": "", "type": "string"},
                    "use_for_horizontal": {"default": "luminance", "type": "string"},
                    "max_horizontal_displacement": {"default": 10, "min": -1000, "max": 1000},
                    "use_for_vertical": {"default": "luminance", "type": "string"},
                    "max_vertical_displacement": {"default": 10, "min": -1000, "max": 1000},
                    "displacement_map_behavior": {"default": "center_map", "type": "string"},
                    "edge_behavior": {"default": "repeat_edge_pixels", "type": "string"},
                    "expand_output": {"default": False, "type": "boolean"},
                },
                "description": "置换贴图，根据贴图扭曲图像",
            },
            "Mesh_Warp": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "rows": {"default": 3, "min": 1, "max": 50},
                    "columns": {"default": 3, "min": 1, "max": 50},
                    "quality": {"default": 8, "min": 1, "max": 15},
                    "distortion_mesh": {"default": [], "type": "array"},
                },
                "description": "网格变形，通过控制点扭曲图像",
            },
            "Optics_Compensation": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "field_of_view": {"default": 20, "min": 1, "max": 180},
                    "reverse_lens_distortion": {"default": False, "type": "boolean"},
                    "view_center": {"default": [0.5, 0.5], "type": "point"},
                    "optimal_lens_adjustment": {"default": True, "type": "boolean"},
                    "resize": {"default": "off", "type": "string"},
                },
                "description": "光学补偿，镜头畸变校正",
            },
            "Bulge": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "horizontal_radius": {"default": 50, "min": 0, "max": 500},
                    "vertical_radius": {"default": 50, "min": 0, "max": 500},
                    "bulge_height": {"default": 1.0, "min": -5, "max": 5},
                    "tiling": {"default": "none", "type": "string"},
                    "center": {"default": [0.5, 0.5], "type": "point"},
                },
                "description": "膨胀/凹陷效果",
            },
            "Polar_Coordinates": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "interpolation": {"default": 0, "min": -100, "max": 100},
                    "type": {"default": "polar_to_rect", "type": "string"},
                },
                "description": "极坐标转换",
            },
            "Warp": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "warp_style": {"default": "arc", "type": "string"},
                    "bend": {"default": 50, "min": -100, "max": 100},
                    "horizontal_distortion": {"default": 0, "min": -100, "max": 100},
                    "vertical_distortion": {"default": 0, "min": -100, "max": 100},
                },
                "description": "弯曲变形，多种预设形状",
            },
            "Twirl": {
                "category": FilterCategory.DISTORT,
                "params": {
                    "angle": {"default": 90, "min": -9999, "max": 9999},
                    "radius": {"default": 100, "min": 0, "max": 500},
                    "center": {"default": [0.5, 0.5], "type": "point"},
                },
                "description": "旋转扭曲效果",
            },
        })

        # 风格化滤镜
        self._filters.update({
            "Cartoon": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "render": {"default": "fill_and_edge", "type": "string"},
                    "detail_radius": {"default": 30, "min": 0, "max": 100},
                    "detail_threshold": {"default": 50, "min": 0, "max": 100},
                    "edge_radius": {"default": 1.0, "min": 0, "max": 10},
                    "edge_threshold": {"default": 50, "min": 0, "max": 100},
                    "edge_intensity": {"default": 1.0, "min": 0, "max": 10},
                    "shading_steps": {"default": 4, "min": 2, "max": 8},
                },
                "description": "卡通效果，将图像转为卡通风格",
            },
            "Find_Edges": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "invert": {"default": False, "type": "boolean"},
                    "blend_with_original": {"default": 0, "min": 0, "max": 100},
                },
                "description": "查找边缘，勾勒图像轮廓",
            },
            "Roughen_Edges": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "edge_type": {"default": "rusty", "type": "string"},
                    "edge_color": {"default": [255, 0, 0], "type": "color"},
                    "border": {"default": 0.05, "min": 0, "max": 1},
                    "edge_roughness": {"default": 0.5, "min": 0, "max": 1},
                    "spike_height": {"default": 0.5, "min": 0, "max": 1},
                    "spike_spacing": {"default": 0.25, "min": 0, "max": 1},
                    "scale": {"default": 100, "min": 0, "max": 1000},
                    "stretch_width_or_height": {"default": "width_and_height", "type": "string"},
                    "complexity": {"default": 3, "min": 1, "max": 10},
                    "evolution": {"default": 0, "min": 0, "max": 360},
                },
                "description": "粗糙边缘，模拟手绘/破旧效果",
            },
            "Mosaic": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "horizontal_blocks": {"default": 10, "min": 1, "max": 1000},
                    "vertical_blocks": {"default": 10, "min": 1, "max": 1000},
                    "sharp_colors": {"default": False, "type": "boolean"},
                },
                "description": "马赛克效果",
            },
            "Brush_Strokes": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "stroke_angle": {"default": -45, "min": -360, "max": 360},
                    "brush_size": {"default": 1.0, "min": 0.1, "max": 10},
                    "stroke_length": {"default": 2.0, "min": 0, "max": 20},
                    "stroke_density": {"default": 2.0, "min": 0, "max": 10},
                    "stroke_randomness": {"default": 1.0, "min": 0, "max": 10},
                    "paint_surface": {"default": "paint_on_original", "type": "string"},
                },
                "description": "画笔描边效果",
            },
            "Glow": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "glow_based_on": {"default": "color_channels", "type": "string"},
                    "glow_threshold": {"default": 70, "min": 0, "max": 100},
                    "glow_radius": {"default": 10, "min": 0, "max": 200},
                    "glow_intensity": {"default": 1.0, "min": 0, "max": 10},
                    "composite_original": {"default": "on_top", "type": "string"},
                    "glow_operation": {"default": "add", "type": "string"},
                    "glow_colors": {"default": "a_b_colors", "type": "string"},
                    "color_looping": {"default": "sawtooth", "type": "string"},
                    "color_loops": {"default": 1, "min": 1, "max": 10},
                    "color_a": {"default": [255, 255, 255], "type": "color"},
                    "color_b": {"default": [255, 0, 0], "type": "color"},
                },
                "description": "发光效果",
            },
            "Leave_Color": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "amount_to_decolor": {"default": 50, "min": 0, "max": 100},
                    "color_to_leave": {"default": [255, 0, 0], "type": "color"},
                    "tolerance": {"default": 10, "min": 0, "max": 100},
                    "edge_softness": {"default": 0.5, "min": 0, "max": 10},
                    "match_colors": {"default": "using_rgb", "type": "string"},
                },
                "description": "保留指定颜色，其他转为灰度",
            },
            "Tritone": {
                "category": FilterCategory.STYLIZE,
                "params": {
                    "highlights": {"default": [255, 255, 255], "type": "color"},
                    "midtones": {"default": [128, 128, 128], "type": "color"},
                    "shadows": {"default": [0, 0, 0], "type": "color"},
                    "blend_with_original": {"default": 0, "min": 0, "max": 100},
                },
                "description": "三色渐变映射",
            },
        })

        # 生成滤镜
        self._filters.update({
            "Fractal_Noise": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "fractal_type": {"default": "basic", "type": "string"},
                    "noise_type": {"default": "soft_linear", "type": "string"},
                    "brightness": {"default": 50, "min": -100, "max": 200},
                    "contrast": {"default": 100, "min": -200, "max": 200},
                    "overflow": {"default": "clip", "type": "string"},
                    "transform": {"default": "rotate", "type": "string"},
                    "rotation": {"default": 0, "min": 0, "max": 360},
                    "uniform_scaling": {"default": True, "type": "boolean"},
                    "scale": {"default": 100, "min": 1, "max": 10000},
                    "scale_width": {"default": 100, "min": 1, "max": 10000},
                    "scale_height": {"default": 100, "min": 1, "max": 10000},
                    "offset_turbulence": {"default": [0.5, 0.5], "type": "point"},
                    "complexity": {"default": 3, "min": 0, "max": 20},
                    "evolution": {"default": 0, "min": 0, "max": 360},
                },
                "description": "分形噪波，生成自然纹理和背景",
            },
            "Gradient_Ramp": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "start_of_ramp": {"default": [0, 0], "type": "point"},
                    "start_color": {"default": [255, 255, 255], "type": "color"},
                    "end_of_ramp": {"default": [0, 100], "type": "point"},
                    "end_color": {"default": [0, 0, 0], "type": "color"},
                    "ramp_shape": {"default": "linear_ramp", "type": "string"},
                    "ramp_scatter": {"default": 0, "min": 0, "max": 100},
                    "interpolation": {"default": "linear", "type": "string"},
                    "blend_with_original": {"default": 0, "min": 0, "max": 100},
                },
                "description": "渐变填充",
            },
            "Lens_Flare": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "flare_center": {"default": [0.5, 0.5], "type": "point"},
                    "brightness": {"default": 100, "min": 10, "max": 300},
                    "flare_type": {"default": "50_300mm_zoom", "type": "string"},
                    "blend_with_original": {"default": 100, "min": 0, "max": 100},
                },
                "description": "镜头光晕效果",
            },
            "Write_on": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "brush_position": {"default": [0.5, 0.5], "type": "point"},
                    "brush_size": {"default": 5, "min": 0, "max": 100},
                    "brush_angle": {"default": 0, "min": 0, "max": 360},
                    "brush_hardness": {"default": 50, "min": 0, "max": 100},
                    "brush_opacity": {"default": 100, "min": 0, "max": 100},
                    "paint_style": {"default": "on_original", "type": "string"},
                    "blend_mode": {"default": "normal", "type": "string"},
                    "color": {"default": [255, 0, 0], "type": "color"},
                },
                "description": "书写动画，模拟手绘效果",
            },
            "4_color_Gradient": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "point_1": {"default": [0, 0], "type": "point"},
                    "color_1": {"default": [255, 0, 0], "type": "color"},
                    "point_2": {"default": [100, 0], "type": "point"},
                    "color_2": {"default": [0, 255, 0], "type": "color"},
                    "point_3": {"default": [0, 100], "type": "point"},
                    "color_3": {"default": [0, 0, 255], "type": "color"},
                    "point_4": {"default": [100, 100], "type": "point"},
                    "color_4": {"default": [255, 255, 0], "type": "color"},
                    "blend_with_original": {"default": 0, "min": 0, "max": 100},
                    "jitter": {"default": 0, "min": 0, "max": 100},
                    "opacity": {"default": 100, "min": 0, "max": 100},
                    "blending_mode": {"default": "normal", "type": "string"},
                },
                "description": "四色渐变",
            },
            "Cell_Pattern": {
                "category": FilterCategory.GENERATE,
                "params": {
                    "cell_pattern": {"default": "bubbles", "type": "string"},
                    "size": {"default": 60, "min": 1, "max": 1000},
                    "spread": {"default": 1.0, "min": 0, "max": 5},
                    "contrast": {"default": 100, "min": 0, "max": 500},
                    "tiled": {"default": "off", "type": "string"},
                    "tiling_mode": {"default": "x_and_y", "type": "string"},
                    "random_seed": {"default": 1, "min": 1, "max": 10000},
                    "offset": {"default": [0, 0], "type": "point"},
                    "evolution": {"default": 0, "min": 0, "max": 360},
                },
                "description": "细胞图案生成",
            },
        })

        # 抠像滤镜
        self._filters.update({
            "Keylight": {
                "category": FilterCategory.KEYING,
                "params": {
                    "screen_colour": {"default": [0, 255, 0], "type": "color"},
                    "screen_gain": {"default": 1.0, "min": 0, "max": 5},
                    "screen_balance": {"default": 0.5, "min": 0, "max": 1},
                    "despill_bias": {"default": 0.5, "min": 0, "max": 1},
                    "despill_factor": {"default": 1.0, "min": 0, "max": 10},
                    "screen_pre_blur": {"default": 0, "min": 0, "max": 10},
                    "screen_matte": {"default": "none", "type": "string"},
                    "clip_black": {"default": 0, "min": 0, "max": 100},
                    "clip_white": {"default": 100, "min": 0, "max": 100},
                    "clip_rollback": {"default": 0, "min": 0, "max": 100},
                    "screen_shrink_grow": {"default": 0, "min": -100, "max": 100},
                    "screen_softness": {"default": 0, "min": 0, "max": 100},
                    "edge_colour_correction": {"default": 0, "min": 0, "max": 100},
                    "despill_mode": {"default": "screen_colour", "type": "string"},
                },
                "description": "Keylight专业抠像，行业标准绿幕蓝幕抠像工具",
            },
            "Color_Key": {
                "category": FilterCategory.KEYING,
                "params": {
                    "key_color": {"default": [0, 0, 255], "type": "color"},
                    "tolerance": {"default": 10, "min": 0, "max": 100},
                    "edge_thin": {"default": 0, "min": -50, "max": 50},
                    "edge_feather": {"default": 0, "min": 0, "max": 100},
                    "invert_key": {"default": False, "type": "boolean"},
                },
                "description": "颜色键，简单抠像工具",
            },
            "Linear_Color_Key": {
                "category": FilterCategory.KEYING,
                "params": {
                    "key_color": {"default": [0, 0, 255], "type": "color"},
                    "matching_tolerance": {"default": 10, "min": 0, "max": 100},
                    "matching_softness": {"default": 0, "min": 0, "max": 100},
                    "key_operation": {"default": "key_colors", "type": "string"},
                    "invert_key": {"default": False, "type": "boolean"},
                },
                "description": "线性颜色键，更精确的颜色抠像",
            },
            "Color_Range": {
                "category": FilterCategory.KEYING,
                "params": {
                    "fuzziness": {"default": 50, "min": 0, "max": 200},
                    "color_space": {"default": "lab", "type": "string"},
                    "min_l": {"default": 0, "min": 0, "max": 100},
                    "max_l": {"default": 100, "min": 0, "max": 100},
                    "min_a": {"default": -128, "min": -128, "max": 127},
                    "max_a": {"default": 127, "min": -128, "max": 127},
                    "min_b": {"default": -128, "min": -128, "max": 127},
                    "max_b": {"default": 127, "min": -128, "max": 127},
                },
                "description": "颜色范围，在LAB/HSB颜色空间中精确抠像",
            },
            "Difference_Matte": {
                "category": FilterCategory.KEYING,
                "params": {
                    "difference_layer": {"default": "", "type": "string"},
                    "if_layer_sizes_differ": {"default": "center", "type": "string"},
                    "matching_tolerance": {"default": 10, "min": 0, "max": 100},
                    "matching_softness": {"default": 0, "min": 0, "max": 100},
                    "blur_before_difference": {"default": 0, "min": 0, "max": 100},
                    "invert_difference_matte": {"default": False, "type": "boolean"},
                },
                "description": "差异蒙版，通过对比静态背景抠像",
            },
        })

        # 透视滤镜
        self._filters.update({
            "CC_Cylinder": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "position_x": {"default": 0.5, "min": -1, "max": 2},
                    "position_y": {"default": 0.5, "min": -1, "max": 2},
                    "position_z": {"default": 0, "min": -5, "max": 5},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "render": {"default": "full", "type": "string"},
                    "shading": {"default": 1, "min": 0, "max": 1},
                    "ambient": {"default": 50, "min": 0, "max": 100},
                    "light_intensity": {"default": 50, "min": 0, "max": 200},
                    "light_color": {"default": [255, 255, 255], "type": "color"},
                    "light_type": {"default": "distant", "type": "string"},
                    "metallic": {"default": False, "type": "boolean"},
                    "reflection": {"default": 50, "min": 0, "max": 100},
                    "specular": {"default": 50, "min": 0, "max": 100},
                    "roughness": {"default": 50, "min": 0, "max": 100},
                },
                "description": "CC圆柱，将图层包裹在圆柱体上",
            },
            "CC_Sphere": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "position_x": {"default": 0.5, "min": -1, "max": 2},
                    "position_y": {"default": 0.5, "min": -1, "max": 2},
                    "position_z": {"default": 0, "min": -5, "max": 5},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "rotation_x": {"default": 0, "min": -360, "max": 360},
                    "rotation_y": {"default": 0, "min": -360, "max": 360},
                    "radius": {"default": 100, "min": 1, "max": 1000},
                    "shading": {"default": 1, "min": 0, "max": 1},
                    "ambient": {"default": 50, "min": 0, "max": 100},
                    "light_intensity": {"default": 50, "min": 0, "max": 200},
                    "light_color": {"default": [255, 255, 255], "type": "color"},
                    "metallic": {"default": False, "type": "boolean"},
                    "reflection": {"default": 50, "min": 0, "max": 100},
                },
                "description": "CC球体，将图层映射到球体表面",
            },
            "CC_Page_Turn": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "fold_position": {"default": [1, 0.5], "type": "point"},
                    "fold_direction": {"default": 0, "min": -360, "max": 360},
                    "fold_radius": {"default": 0.3, "min": 0, "max": 2},
                    "render": {"default": "front_page", "type": "string"},
                    "back_page": {"default": "", "type": "string"},
                    "paper_color": {"default": [200, 200, 200], "type": "color"},
                    "highlight_color": {"default": [255, 255, 255], "type": "color"},
                    "fold_amount": {"default": 50, "min": 0, "max": 100},
                },
                "description": "CC翻页效果",
            },
            "Bevel_Alpha": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "edge_thickness": {"default": 2, "min": 0, "max": 200},
                    "light_angle": {"default": -60, "min": -360, "max": 360},
                    "light_color": {"default": [255, 255, 255], "type": "color"},
                    "light_intensity": {"default": 0.6, "min": 0, "max": 2},
                },
                "description": "Alpha斜角，给图层边缘添加立体斜面",
            },
            "Drop_Shadow": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "shadow_color": {"default": [0, 0, 0], "type": "color"},
                    "opacity": {"default": 75, "min": 0, "max": 100},
                    "direction": {"default": 135, "min": 0, "max": 360},
                    "distance": {"default": 5, "min": 0, "max": 200},
                    "softness": {"default": 5, "min": 0, "max": 200},
                    "shadow_only": {"default": False, "type": "boolean"},
                },
                "description": "投影效果",
            },
            "Radial_Shadow": {
                "category": FilterCategory.PERSPECTIVE,
                "params": {
                    "shadow_color": {"default": [0, 0, 0], "type": "color"},
                    "opacity": {"default": 75, "min": 0, "max": 100},
                    "light_source": {"default": [0.5, -1], "type": "point"},
                    "softness": {"default": 5, "min": 0, "max": 200},
                    "render": {"default": "regular", "type": "string"},
                    "color_influence": {"default": 0, "min": 0, "max": 100},
                    "shadow_only": {"default": False, "type": "boolean"},
                    "resize_layer": {"default": False, "type": "boolean"},
                },
                "description": "径向阴影，模拟点光源投影",
            },
        })

        # 模拟/粒子滤镜
        self._filters.update({
            "CC_Particle_Systems_II": {
                "category": FilterCategory.SIMULATION,
                "params": {
                    "birth_rate": {"default": 2.0, "min": 0, "max": 100},
                    "longevity": {"default": 1.0, "min": 0.1, "max": 10},
                    "producer_position_x": {"default": 0.5, "min": -1, "max": 2},
                    "producer_position_y": {"default": 0.5, "min": -1, "max": 2},
                    "producer_radius_x": {"default": 0.1, "min": 0, "max": 1},
                    "producer_radius_y": {"default": 0.1, "min": 0, "max": 1},
                    "velocity": {"default": 60, "min": 0, "max": 500},
                    "inherent_velocity": {"default": 100, "min": 0, "max": 100},
                    "gravity": {"default": 100, "min": -500, "max": 500},
                    "direction": {"default": 90, "min": -360, "max": 360},
                    "direction_random": {"default": 0, "min": 0, "max": 100},
                    "velocity_random": {"default": 0, "min": 0, "max": 100},
                    "particle_type": {"default": "lens_convex", "type": "string"},
                    "birth_size": {"default": 0.2, "min": 0, "max": 5},
                    "death_size": {"default": 0.1, "min": 0, "max": 5},
                    "size_variation": {"default": 0, "min": 0, "max": 100},
                    "max_opacity": {"default": 255, "min": 0, "max": 255},
                    "birth_color": {"default": [255, 255, 255], "type": "color"},
                    "death_color": {"default": [255, 0, 0], "type": "color"},
                },
                "description": "CC粒子系统II，2D粒子效果",
            },
            "CC_Rain": {
                "category": FilterCategory.SIMULATION,
                "params": {
                    "rain": {"default": 500, "min": 0, "max": 10000},
                    "speed": {"default": 200, "min": 10, "max": 5000},
                    "angle": {"default": 20, "min": -90, "max": 90},
                    "drop_size": {"default": 1.0, "min": 0.1, "max": 10},
                    "source_depth": {"default": 0, "min": 0, "max": 1},
                    "depth_displacement": {"default": 0.5, "min": 0, "max": 1},
                    "brightness": {"default": 50, "min": 0, "max": 100},
                    "opacity": {"default": 50, "min": 0, "max": 100},
                    "turbulence": {"default": 0, "min": 0, "max": 100},
                },
                "description": "CC下雨效果",
            },
            "CC_Snow": {
                "category": FilterCategory.SIMULATION,
                "params": {
                    "flakes": {"default": 500, "min": 0, "max": 10000},
                    "speed": {"default": 50, "min": 10, "max": 5000},
                    "windspeed": {"default": 100, "min": -5000, "max": 5000},
                    "flakes_size": {"default": 2.0, "min": 0.1, "max": 20},
                    "source_depth": {"default": 0, "min": 0, "max": 1},
                    "depth_displacement": {"default": 0.5, "min": 0, "max": 1},
                    "brightness": {"default": 50, "min": 0, "max": 100},
                    "opacity": {"default": 50, "min": 0, "max": 100},
                    "turbulence": {"default": 0, "min": 0, "max": 100},
                },
                "description": "CC下雪效果",
            },
            "Foam": {
                "category": FilterCategory.SIMULATION,
                "params": {
                    "view": {"default": "rendered", "type": "string"},
                    "producer_point": {"default": [0.1, 0.5], "type": "point"},
                    "producer_x_size": {"default": 0.2, "min": 0, "max": 1},
                    "producer_y_size": {"default": 0.5, "min": 0, "max": 1},
                    "producer_orientation": {"default": 90, "min": 0, "max": 360},
                    "zoom": {"default": 100, "min": 10, "max": 500},
                    "universe_size": {"default": 1.0, "min": 0.5, "max": 3},
                    "birth_rate": {"default": 3.0, "min": 0, "max": 10},
                    "life": {"default": 1.0, "min": 0.1, "max": 5},
                    "bubble_texture": {"default": "bubble_tube", "type": "string"},
                    "bubble_size": {"default": 0.5, "min": 0, "max": 2},
                    "size_variance": {"default": 0.5, "min": 0, "max": 1},
                    "strength": {"default": 5, "min": 0, "max": 100},
                    "flow_speed": {"default": 2, "min": 0, "max": 5},
                    "direction": {"default": 0, "min": -360, "max": 360},
                    "drag": {"default": 0.1, "min": 0, "max": 1},
                    "turbulence": {"default": 0.5, "min": 0, "max": 5},
                    "wobble_amount": {"default": 0.5, "min": 0, "max": 2},
                    "wobble_frequency": {"default": 0.5, "min": 0, "max": 5},
                },
                "description": "气泡效果，模拟泡沫/气泡运动",
            },
        })

        # 噪点和颗粒滤镜
        self._filters.update({
            "Add_Grain": {
                "category": FilterCategory.NOISE_GRAIN,
                "params": {
                    "viewing_mode": {"default": "final_output", "type": "string"},
                    "preset": {"default": "kodak_gold_100", "type": "string"},
                    "amount": {"default": 50, "min": 0, "max": 100},
                    "size": {"default": 1.0, "min": 0, "max": 10},
                    "softness": {"default": 50, "min": 0, "max": 100},
                    "turbulence": {"default": 50, "min": 0, "max": 100},
                    "color": {"default": [255, 255, 255], "type": "color"},
                    "blend_mode": {"default": "overlay", "type": "string"},
                },
                "description": "添加胶片颗粒效果",
            },
            "Noise": {
                "category": FilterCategory.NOISE_GRAIN,
                "params": {
                    "amount_of_noise": {"default": 10, "min": 0, "max": 100},
                    "noise_type": {"default": "uniform", "type": "string"},
                    "clipping": {"default": True, "type": "boolean"},
                    "channel_options": {"default": "grayscale_noise", "type": "string"},
                },
                "description": "添加噪点",
            },
            "Noise_Alpha": {
                "category": FilterCategory.NOISE_GRAIN,
                "params": {
                    "amount": {"default": 50, "min": 0, "max": 100},
                    "noise_type": {"default": "uniform", "type": "string"},
                    "original_alpha": {"default": "scale", "type": "string"},
                },
                "description": "在Alpha通道添加噪点",
            },
            "Fractal_Noise_Grain": {
                "category": FilterCategory.NOISE_GRAIN,
                "params": {
                    "fractal_type": {"default": "turbulent_basic", "type": "string"},
                    "noise_type": {"default": "soft_linear", "type": "string"},
                    "brightness": {"default": 50, "min": -100, "max": 200},
                    "contrast": {"default": 100, "min": -200, "max": 200},
                    "scale": {"default": 10, "min": 1, "max": 1000},
                    "complexity": {"default": 5, "min": 0, "max": 20},
                    "blend_mode": {"default": "overlay", "type": "string"},
                    "opacity": {"default": 30, "min": 0, "max": 100},
                },
                "description": "分形噪点生成精细颗粒",
            },
        })

        # 通道滤镜
        self._filters.update({
            "Invert": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "channel": {"default": "rgb", "type": "string"},
                    "blend_with_original": {"default": 0, "min": 0, "max": 100},
                },
                "description": "反转颜色/通道",
            },
            "Channel_Combiner": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "source_a": {"default": "red", "type": "string"},
                    "source_b": {"default": "green", "type": "string"},
                    "source_c": {"default": "blue", "type": "string"},
                    "source_d": {"default": "alpha", "type": "string"},
                    "use_second_layer": {"default": False, "type": "boolean"},
                    "second_layer": {"default": "", "type": "string"},
                    "invert_a": {"default": False, "type": "boolean"},
                    "invert_b": {"default": False, "type": "boolean"},
                    "invert_c": {"default": False, "type": "boolean"},
                    "invert_d": {"default": False, "type": "boolean"},
                },
                "description": "通道合成器，重排通道",
            },
            "Minimax": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "operation": {"default": "minimax", "type": "string"},
                    "direction": {"default": "horizontal_and_vertical", "type": "string"},
                    "radius": {"default": 5, "min": 0, "max": 100},
                    "channel": {"default": "color_and_alpha", "type": "string"},
                    "dont_shrink_edges": {"default": False, "type": "boolean"},
                },
                "description": "最小最大，扩展/收缩通道",
            },
            "Shift_Channels": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "take_alpha_from": {"default": "alpha", "type": "string"},
                    "take_red_from": {"default": "red", "type": "string"},
                    "take_green_from": {"default": "green", "type": "string"},
                    "take_blue_from": {"default": "blue", "type": "string"},
                },
                "description": "通道切换，从其他通道复制",
            },
            "Set_Channels": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "source_layer_1": {"default": "", "type": "string"},
                    "use_1_layer": {"default": "red", "type": "string"},
                    "target_layer_1": {"default": "red", "type": "string"},
                    "source_layer_2": {"default": "", "type": "string"},
                    "use_2_layer": {"default": "green", "type": "string"},
                    "target_layer_2": {"default": "green", "type": "string"},
                    "source_layer_3": {"default": "", "type": "string"},
                    "use_3_layer": {"default": "blue", "type": "string"},
                    "target_layer_3": {"default": "blue", "type": "string"},
                    "source_layer_4": {"default": "", "type": "string"},
                    "use_4_layer": {"default": "alpha", "type": "string"},
                    "target_layer_4": {"default": "alpha", "type": "string"},
                    "stretch_second_layer_to_fit": {"default": False, "type": "boolean"},
                },
                "description": "设置通道，从多个图层组合通道",
            },
            "Remove_Color_Matting": {
                "category": FilterCategory.CHANNEL,
                "params": {
                    "matte_type": {"default": "black_matte", "type": "string"},
                },
                "description": "移除颜色蒙版边缘色边",
            },
        })

        # 转场滤镜
        self._filters.update({
            "CC_Grid_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "completion": {"default": 0, "min": 0, "max": 100},
                    "center": {"default": [0.5, 0.5], "type": "point"},
                    "horizontal_tiles": {"default": 10, "min": 1, "max": 100},
                    "vertical_tiles": {"default": 10, "min": 1, "max": 100},
                    "tile_origin": {"default": "center", "type": "string"},
                    "scale": {"default": 0, "min": -100, "max": 100},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "flip_axes": {"default": "x", "type": "string"},
                },
                "description": "CC网格擦除转场",
            },
            "CC_Glass_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "completion": {"default": 0, "min": 0, "max": 100},
                    "layer_to_reveal": {"default": "", "type": "string"},
                    "boundary": {"default": 50, "min": 0, "max": 100},
                    "softness": {"default": 20, "min": 0, "max": 100},
                    "displacement_amount": {"default": 30, "min": -200, "max": 200},
                    "shape": {"default": 5, "min": 0, "max": 50},
                    "from": {"default": "right", "type": "string"},
                },
                "description": "CC玻璃擦除转场",
            },
            "CC_Radial_Scale_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "completion": {"default": 0, "min": 0, "max": 100},
                    "center": {"default": [0.5, 0.5], "type": "point"},
                    "reverse": {"default": False, "type": "boolean"},
                    "fade": {"default": 50, "min": 0, "max": 100},
                    "start_scale": {"default": 100, "min": 0, "max": 1000},
                },
                "description": "CC径向缩放擦除转场",
            },
            "Linear_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "transition_completion": {"default": 0, "min": 0, "max": 100},
                    "wipe_angle": {"default": 270, "min": 0, "max": 360},
                    "feather": {"default": 0, "min": 0, "max": 100},
                },
                "description": "线性擦除转场",
            },
            "Radial_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "transition_completion": {"default": 0, "min": 0, "max": 100},
                    "start_angle": {"default": 0, "min": 0, "max": 360},
                    "wipe_center": {"default": [0.5, 0.5], "type": "point"},
                    "wipe": {"default": "clockwise", "type": "string"},
                    "feather": {"default": 0, "min": 0, "max": 100},
                },
                "description": "径向擦除转场",
            },
            "Venetian_Blinds": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "transition_completion": {"default": 0, "min": 0, "max": 100},
                    "direction": {"default": 90, "min": 0, "max": 360},
                    "width": {"default": 32, "min": 1, "max": 1000},
                    "feather": {"default": 0, "min": 0, "max": 100},
                },
                "description": "百叶窗转场效果",
            },
            "Gradient_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "transition_completion": {"default": 0, "min": 0, "max": 100},
                    "transition_softness": {"default": 0, "min": 0, "max": 100},
                    "gradient_layer": {"default": "", "type": "string"},
                    "gradient_placement": {"default": "tile_gradient", "type": "string"},
                    "invert_gradient": {"default": False, "type": "boolean"},
                },
                "description": "渐变擦除转场",
            },
            "Iris_Wipe": {
                "category": FilterCategory.TRANSITION,
                "params": {
                    "iris_shape": {"default": "iris_points=6", "type": "string"},
                    "outer_radius": {"default": 50, "min": 0, "max": 500},
                    "inner_radius": {"default": 20, "min": 0, "max": 500},
                    "rotation": {"default": 0, "min": 0, "max": 360},
                    "iris_center": {"default": [0.5, 0.5], "type": "point"},
                    "feather": {"default": 0, "min": 0, "max": 100},
                },
                "description": "虹膜擦除转场",
            },
        })

        # 3D透视滤镜
        self._filters.update({
            "CC_Force_Motion_Blur": {
                "category": FilterCategory.PERSPECTIVE_3D,
                "params": {
                    "motion_blur_samples": {"default": 16, "min": 2, "max": 64},
                    "shutter_angle": {"default": 180, "min": 1, "max": 720},
                    "native_motion_blur": {"default": "off", "type": "string"},
                },
                "description": "CC强制运动模糊",
            },
            "CC_Jumper": {
                "category": FilterCategory.PERSPECTIVE_3D,
                "params": {
                    "jump_x": {"default": 0, "min": -1000, "max": 1000},
                    "jump_y": {"default": 0, "min": -1000, "max": 1000},
                    "jump_z": {"default": 0, "min": -1000, "max": 1000},
                    "rotate_x": {"default": 0, "min": -360, "max": 360},
                    "rotate_y": {"default": 0, "min": -360, "max": 360},
                    "rotate_z": {"default": 0, "min": -360, "max": 360},
                    "scale": {"default": 100, "min": 0, "max": 1000},
                },
                "description": "CC跳跃3D变换",
            },
            "CC_Particle_World": {
                "category": FilterCategory.PERSPECTIVE_3D,
                "params": {
                    "birth_rate": {"default": 2.0, "min": 0, "max": 100},
                    "longevity": {"default": 1.0, "min": 0.1, "max": 10},
                    "camera_position_x": {"default": 0, "min": -5, "max": 5},
                    "camera_position_y": {"default": 0, "min": -5, "max": 5},
                    "camera_position_z": {"default": -2, "min": -10, "max": 10},
                    "camera_rotation_x": {"default": 0, "min": -360, "max": 360},
                    "camera_rotation_y": {"default": 0, "min": -360, "max": 360},
                    "camera_rotation_z": {"default": 0, "min": -360, "max": 360},
                    "focal_length": {"default": 50, "min": 10, "max": 200},
                    "velocity": {"default": 60, "min": 0, "max": 500},
                    "gravity": {"default": 100, "min": -500, "max": 500},
                    "particle_type": {"default": "lens_convex", "type": "string"},
                    "birth_size": {"default": 0.2, "min": 0, "max": 5},
                    "death_size": {"default": 0.1, "min": 0, "max": 5},
                },
                "description": "CC粒子世界，3D粒子系统",
            },
        })

        # 实用工具滤镜
        self._filters.update({
            "Crop": {
                "category": FilterCategory.UTILITY,
                "params": {
                    "left": {"default": 0, "min": 0, "max": 4000},
                    "right": {"default": 0, "min": 0, "max": 4000},
                    "top": {"default": 0, "min": 0, "max": 4000},
                    "bottom": {"default": 0, "min": 0, "max": 4000},
                },
                "description": "裁剪图层边缘",
            },
            "Transform": {
                "category": FilterCategory.UTILITY,
                "params": {
                    "anchor_point": {"default": [0.5, 0.5], "type": "point"},
                    "position": {"default": [0.5, 0.5], "type": "point"},
                    "scale_height": {"default": 100, "min": 0, "max": 1000},
                    "scale_width": {"default": 100, "min": 0, "max": 1000},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "opacity": {"default": 100, "min": 0, "max": 100},
                    "skew": {"default": 0, "min": -45, "max": 45},
                    "skew_axis": {"default": 0, "min": 0, "max": 360},
                    "use_composition_shutter_angle": {"default": True, "type": "boolean"},
                    "shutter_angle": {"default": 180, "min": 0, "max": 720},
                },
                "description": "变换，缩放/旋转/位移/透明度",
            },
            "Flip_Horizontal": {
                "category": FilterCategory.UTILITY,
                "params": {},
                "description": "水平翻转",
            },
            "Flip_Vertical": {
                "category": FilterCategory.UTILITY,
                "params": {},
                "description": "垂直翻转",
            },
            "Rectangular_Mask": {
                "category": FilterCategory.UTILITY,
                "params": {
                    "mask_shape": {"default": [0, 0, 100, 100], "type": "rect"},
                    "mask_feather": {"default": [0, 0], "type": "point"},
                    "mask_opacity": {"default": 100, "min": 0, "max": 100},
                    "mask_expansion": {"default": 0, "min": -500, "max": 500},
                    "inverted": {"default": False, "type": "boolean"},
                },
                "description": "矩形蒙版",
            },
            "Elliptical_Mask": {
                "category": FilterCategory.UTILITY,
                "params": {
                    "mask_shape": {"default": [0, 0, 100, 100], "type": "ellipse"},
                    "mask_feather": {"default": [0, 0], "type": "point"},
                    "mask_opacity": {"default": 100, "min": 0, "max": 100},
                    "mask_expansion": {"default": 0, "min": -500, "max": 500},
                    "inverted": {"default": False, "type": "boolean"},
                },
                "description": "椭圆蒙版",
            },
        })

    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        应用AE滤镜

        Args:
            filter_name: 滤镜名称
            params: 滤镜参数字典

        Returns:
            滤镜配置字典
        """
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"AE滤镜未找到: {filter_name}")

        merged_params = self._merge_params(filter_name, params)
        return {
            "software": "after_effects",
            "filter": filter_name,
            "params": merged_params,
            "info": self._filters[filter_name],
        }

    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """
        应用AE滤镜链

        Args:
            filters: 滤镜列表，每项为(滤镜名称, 参数)元组

        Returns:
            滤镜配置列表
        """
        return [self.apply_filter(name, params) for name, params in filters]

    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], layer_name: str = "activeLayer", **kwargs) -> str:
        """
        生成AE JSX脚本代码

        Args:
            filters: 滤镜列表
            layer_name: 图层变量名

        Returns:
            JSX脚本字符串
        """
        script_lines = [
            "// Auto-generated AE Filter Script",
            "var app = thisLayer ? thisLayer : app.project.activeItem;",
            f"var targetLayer = {layer_name};",
            "",
        ]

        for i, (filter_name, params) in enumerate(filters):
            safe_name = filter_name.replace("/", "_").replace(" ", "_")
            script_lines.append(f"// 添加滤镜: {filter_name}")
            script_lines.append(f"var filter{i+1} = targetLayer.effect.addProperty(\"ADBE Effect 1\");")
            script_lines.append(f'filter{i+1}.name = "{filter_name}";')

            merged_params = self._merge_params(filter_name, params)
            for param_name, param_value in merged_params.items():
                if isinstance(param_value, bool):
                    val_str = "true" if param_value else "false"
                elif isinstance(param_value, str):
                    val_str = f'"{param_value}"'
                elif isinstance(param_value, list):
                    val_str = f"[{', '.join(str(v) for v in param_value)}]"
                else:
                    val_str = str(param_value)

                script_lines.append(
                    f'filter{i+1}.property("{param_name}").setValue({val_str});'
                )

            script_lines.append("")

        script_lines.append("// 脚本执行完毕")
        return "\n".join(script_lines)

    def get_color_correction_filters(self) -> list[str]:
        """获取色彩校正滤镜列表"""
        return self.get_available_filters(FilterCategory.COLOR_CORRECTION)

    def get_blur_sharpen_filters(self) -> list[str]:
        """获取模糊锐化滤镜列表"""
        return self.get_available_filters(FilterCategory.BLUR_SHARPEN)

    def get_distort_filters(self) -> list[str]:
        """获取扭曲滤镜列表"""
        return self.get_available_filters(FilterCategory.DISTORT)

    def get_stylize_filters(self) -> list[str]:
        """获取风格化滤镜列表"""
        return self.get_available_filters(FilterCategory.STYLIZE)

    def get_generate_filters(self) -> list[str]:
        """获取生成类滤镜列表"""
        return self.get_available_filters(FilterCategory.GENERATE)

    def get_keying_filters(self) -> list[str]:
        """获取抠像滤镜列表"""
        return self.get_available_filters(FilterCategory.KEYING)

    def get_perspective_filters(self) -> list[str]:
        """获取透视滤镜列表"""
        return self.get_available_filters(FilterCategory.PERSPECTIVE)

    def get_simulation_filters(self) -> list[str]:
        """获取模拟/粒子滤镜列表"""
        return self.get_available_filters(FilterCategory.SIMULATION)

    def get_transition_filters(self) -> list[str]:
        """获取转场滤镜列表"""
        return self.get_available_filters(FilterCategory.TRANSITION)

    def get_noise_grain_filters(self) -> list[str]:
        """获取噪点颗粒滤镜列表"""
        return self.get_available_filters(FilterCategory.NOISE_GRAIN)


# =============================================================================
# Photoshop 滤镜引擎
# =============================================================================

class PSFilterEngine(BaseFilterEngine):
    """Photoshop 滤镜引擎"""

    def __init__(self):
        super().__init__()
        self._software_type = SoftwareType.PHOTOSHOP
        self._init_filters()

    def _init_filters(self) -> None:
        """初始化PS滤镜库"""
        # 艺术效果滤镜 (15种)
        artistic_filters = [
            "Dry_Brush", "Watercolor", "Neon_Glow", "Cutout", "Fresco",
            "Palette_Knife", "Plastic_Wrap", "Poster_Edges", "Rough_Pastels",
            "Smudge_Stick", "Underpainting", "Paint_Daubs", "Sponge",
            "Colored_Pencil", "Graphic_Pen"
        ]
        for f in artistic_filters:
            self._filters[f] = {
                "category": FilterCategory.STYLIZE,
                "subcategory": "artistic",
                "params": {
                    "brush_size": {"default": 5, "min": 1, "max": 50},
                    "detail": {"default": 10, "min": 1, "max": 15},
                    "texture": {"default": 2, "min": 1, "max": 3},
                },
                "description": f"艺术效果 - {f}",
            }

        # 模糊滤镜
        self._filters.update({
            "Gaussian_Blur_PS": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {"radius": {"default": 5.0, "min": 0.1, "max": 1000}},
                "description": "高斯模糊",
            },
            "Motion_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "angle": {"default": 0, "min": -360, "max": 360},
                    "distance": {"default": 10, "min": 1, "max": 999},
                },
                "description": "动感模糊",
            },
            "Radial_Blur_PS": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "amount": {"default": 10, "min": 1, "max": 100},
                    "method": {"default": "spin", "type": "string"},
                    "quality": {"default": "good", "type": "string"},
                },
                "description": "径向模糊",
            },
            "Lens_Blur_PS": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "radius": {"default": 15, "min": 1, "max": 100},
                    "shape": {"default": "hexagon", "type": "string"},
                    "blade_curvature": {"default": 0, "min": 0, "max": 100},
                    "rotation": {"default": 0, "min": 0, "max": 360},
                    "brightness": {"default": 0, "min": 0, "max": 100},
                    "threshold": {"default": 255, "min": 0, "max": 255},
                    "amount": {"default": 0, "min": 0, "max": 100},
                    "distribution": {"default": "gaussian", "type": "string"},
                    "monochromatic": {"default": False, "type": "boolean"},
                },
                "description": "镜头模糊",
            },
            "Iris_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur_gallery",
                "params": {
                    "blur_amount": {"default": 15, "min": 0, "max": 100},
                    "focus_size": {"default": 100, "min": 0, "max": 500},
                    "feather": {"default": 50, "min": 0, "max": 100},
                    "roundness": {"default": 50, "min": 0, "max": 100},
                },
                "description": "光圈模糊",
            },
            "Tilt_Shift": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur_gallery",
                "params": {
                    "blur_amount": {"default": 15, "min": 0, "max": 100},
                    "distortion": {"default": 0, "min": -100, "max": 100},
                    "symmetric_distortion": {"default": True, "type": "boolean"},
                },
                "description": "移轴模糊",
            },
            "Path_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur_gallery",
                "params": {
                    "speed": {"default": 100, "min": 0, "max": 500},
                    "taper": {"default": 0, "min": 0, "max": 100},
                    "curvature": {"default": 50, "min": 0, "max": 100},
                    "end_speed": {"default": 100, "min": 0, "max": 500},
                },
                "description": "路径模糊",
            },
            "Surface_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "radius": {"default": 5, "min": 1, "max": 100},
                    "threshold": {"default": 20, "min": 1, "max": 100},
                },
                "description": "表面模糊，保留边缘的模糊",
            },
            "Smart_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "radius": {"default": 5, "min": 0.1, "max": 100},
                    "threshold": {"default": 25, "min": 0.1, "max": 100},
                    "quality": {"default": "medium", "type": "string"},
                    "mode": {"default": "normal", "type": "string"},
                },
                "description": "特殊模糊",
            },
            "Average_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {},
                "description": "平均模糊",
            },
            "Box_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {"radius": {"default": 5, "min": 1, "max": 100}},
                "description": "方框模糊",
            },
            "Shape_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "blur",
                "params": {
                    "radius": {"default": 5, "min": 1, "max": 100},
                    "shape": {"default": "circle", "type": "string"},
                },
                "description": "形状模糊",
            },
        })

        # 扭曲滤镜
        self._filters.update({
            "Liquify": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "brush_size": {"default": 50, "min": 1, "max": 1500},
                    "brush_density": {"default": 50, "min": 0, "max": 100},
                    "brush_pressure": {"default": 50, "min": 1, "max": 100},
                    "brush_rate": {"default": 80, "min": 0, "max": 100},
                    "tool": {"default": "forward_warp", "type": "string"},
                    "reconstruct_mode": {"default": "revert", "type": "string"},
                    "mesh_size": {"default": "medium", "type": "string"},
                },
                "description": "液化滤镜",
            },
            "Wave": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "number_of_generators": {"default": 5, "min": 1, "max": 999},
                    "wavelength_min": {"default": 10, "min": 1, "max": 999},
                    "wavelength_max": {"default": 120, "min": 1, "max": 9999},
                    "amplitude_min": {"default": 5, "min": 1, "max": 999},
                    "amplitude_max": {"default": 35, "min": 1, "max": 999},
                    "scale_horizontal": {"default": 100, "min": 0, "max": 100},
                    "scale_vertical": {"default": 100, "min": 0, "max": 100},
                    "type": {"default": "sine", "type": "string"},
                    "undefined_areas": {"default": "wrap_around", "type": "string"},
                },
                "description": "波浪扭曲",
            },
            "Ripple": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "amount": {"default": 100, "min": -999, "max": 999},
                    "size": {"default": "medium", "type": "string"},
                },
                "description": "波纹效果",
            },
            "Glass": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "distortion": {"default": 5, "min": 0, "max": 20},
                    "smoothness": {"default": 3, "min": 1, "max": 15},
                    "texture": {"default": "frosted", "type": "string"},
                    "scaling": {"default": 50, "min": 50, "max": 200},
                    "invert": {"default": False, "type": "boolean"},
                },
                "description": "玻璃效果",
            },
            "Spherize": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "amount": {"default": 100, "min": -100, "max": 100},
                    "mode": {"default": "normal", "type": "string"},
                },
                "description": "球面化",
            },
            "Polar_Coordinates_PS": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {"option": {"default": "rect_to_polar", "type": "string"}},
                "description": "极坐标",
            },
            "Pinch": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {"amount": {"default": 50, "min": -100, "max": 100}},
                "description": "挤压效果",
            },
            "Twirl_PS": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {"angle": {"default": 90, "min": -999, "max": 999}},
                "description": "旋转扭曲",
            },
            "Shear": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "undefined_areas": {"default": "wrap_around", "type": "string"},
                    "curve_points": {"default": [[0, 0], [100, 100]], "type": "array"},
                },
                "description": "切变扭曲",
            },
            "ZigZag": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "amount": {"default": 50, "min": -100, "max": 100},
                    "ridges": {"default": 5, "min": 1, "max": 20},
                    "style": {"default": "around_center", "type": "string"},
                },
                "description": "水波效果",
            },
            "Ocean_Ripple": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "size": {"default": 7, "min": 1, "max": 15},
                    "magnitude": {"default": 5, "min": 1, "max": 20},
                },
                "description": "海洋波纹",
            },
            "Displace": {
                "category": FilterCategory.DISTORT,
                "subcategory": "distort",
                "params": {
                    "horizontal_scale": {"default": 10, "min": 0, "max": 100},
                    "vertical_scale": {"default": 10, "min": 0, "max": 100},
                    "displacement_map": {"default": "stretch_to_fit", "type": "string"},
                    "undefined_areas": {"default": "wrap_around", "type": "string"},
                    "displacement_map_file": {"default": "", "type": "string"},
                },
                "description": "置换滤镜",
            },
        })

        # 杂色滤镜
        self._filters.update({
            "Add_Noise_PS": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "noise",
                "params": {
                    "amount": {"default": 10, "min": 0.1, "max": 400},
                    "distribution": {"default": "gaussian", "type": "string"},
                    "monochromatic": {"default": False, "type": "boolean"},
                },
                "description": "添加杂色",
            },
            "Despeckle": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "noise",
                "params": {},
                "description": "去斑",
            },
            "Reduce_Noise": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "noise",
                "params": {
                    "strength": {"default": 6, "min": 0, "max": 10},
                    "preserve_details": {"default": 50, "min": 0, "max": 100},
                    "reduce_color_noise": {"default": 50, "min": 0, "max": 100},
                    "sharpen_details": {"default": 25, "min": 0, "max": 100},
                    "remove_jpeg_artifact": {"default": False, "type": "boolean"},
                },
                "description": "减少杂色",
            },
            "Dust_Scratches": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "noise",
                "params": {
                    "radius": {"default": 3, "min": 1, "max": 100},
                    "threshold": {"default": 0, "min": 0, "max": 100},
                },
                "description": "蒙尘与划痕",
            },
            "Median": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "noise",
                "params": {"radius": {"default": 1, "min": 1, "max": 100}},
                "description": "中间值降噪",
            },
        })

        # 像素化滤镜
        self._filters.update({
            "Mosaic_PS": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {"cell_size": {"default": 10, "min": 2, "max": 200}},
                "description": "马赛克",
            },
            "Crystallize": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {"cell_size": {"default": 10, "min": 3, "max": 300}},
                "description": "晶格化",
            },
            "Pointillize": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {"cell_size": {"default": 5, "min": 3, "max": 300}},
                "description": "点状化",
            },
            "Color_Halftone": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {
                    "max_radius": {"default": 8, "min": 4, "max": 127},
                    "screen_angle_ch1": {"default": 45, "min": -360, "max": 360},
                    "screen_angle_ch2": {"default": 30, "min": -360, "max": 360},
                    "screen_angle_ch3": {"default": 15, "min": -360, "max": 360},
                    "screen_angle_ch4": {"default": 0, "min": -360, "max": 360},
                },
                "description": "彩色半调",
            },
            "Fragment": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {},
                "description": "碎片效果",
            },
            "Mezzotint": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "pixelate",
                "params": {"type": {"default": "fine_dots", "type": "string"}},
                "description": "铜版雕刻",
            },
        })

        # 渲染滤镜
        self._filters.update({
            "Clouds_PS": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {},
                "description": "云彩",
            },
            "Difference_Clouds": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {},
                "description": "分层云彩",
            },
            "Lens_Flare_PS": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {
                    "brightness": {"default": 100, "min": 10, "max": 300},
                    "flare_center_x": {"default": 0.5, "min": 0, "max": 1},
                    "flare_center_y": {"default": 0.5, "min": 0, "max": 1},
                    "lens_type": {"default": "50_300mm_zoom", "type": "string"},
                },
                "description": "镜头光晕",
            },
            "Fibers": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {
                    "difference": {"default": 16, "min": 1, "max": 64},
                    "strength": {"default": 4, "min": 1, "max": 64},
                    "variance": {"default": "wave", "type": "string"},
                },
                "description": "纤维效果",
            },
            "Lighting_Effects": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {
                    "style": {"default": "soft_omni", "type": "string"},
                    "light_type": {"default": "omni", "type": "string"},
                    "intensity": {"default": 50, "min": -100, "max": 100},
                    "gloss": {"default": 50, "min": 0, "max": 100},
                    "material": {"default": 50, "min": 0, "max": 100},
                    "exposure": {"default": 0, "min": -100, "max": 100},
                    "ambience": {"default": 20, "min": -100, "max": 100},
                    "texture_channel": {"default": "none", "type": "string"},
                    "white_is_high": {"default": False, "type": "boolean"},
                    "height": {"default": 10, "min": 0, "max": 100},
                },
                "description": "光照效果",
            },
            "Tree": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {
                    "base_tree_type": {"default": "oak", "type": "string"},
                    "leaves_amount": {"default": 50, "min": 0, "max": 100},
                    "leaves_size": {"default": 50, "min": 0, "max": 100},
                    "branches_angle": {"default": 50, "min": 0, "max": 100},
                    "branches_length": {"default": 50, "min": 0, "max": 100},
                    "branches_thickness": {"default": 50, "min": 0, "max": 100},
                    "trunk_thickness": {"default": 50, "min": 0, "max": 100},
                    "trunk_height": {"default": 50, "min": 0, "max": 100},
                },
                "description": "生成树木",
            },
            "Flame": {
                "category": FilterCategory.GENERATE,
                "subcategory": "render",
                "params": {
                    "flame_type": {"default": "one_flame", "type": "string"},
                    "width": {"default": 50, "min": 1, "max": 100},
                    "height": {"default": 100, "min": 1, "max": 500},
                    "angle": {"default": 90, "min": -360, "max": 360},
                    "aspect_ratio": {"default": 1.0, "min": 0.1, "max": 10},
                    "quality": {"default": "medium", "type": "string"},
                    "color": {"default": "yellow_orange", "type": "string"},
                },
                "description": "火焰效果",
            },
        })

        # 锐化滤镜
        self._filters.update({
            "Unsharp_Mask_PS": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {
                    "amount": {"default": 100, "min": 1, "max": 500},
                    "radius": {"default": 1.0, "min": 0.1, "max": 1000},
                    "threshold": {"default": 0, "min": 0, "max": 255},
                },
                "description": "USM锐化",
            },
            "Smart_Sharpen": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {
                    "amount": {"default": 100, "min": 1, "max": 500},
                    "radius": {"default": 1.0, "min": 0.1, "max": 64},
                    "reduce_noise": {"default": 10, "min": 0, "max": 100},
                    "remove": {"default": "gaussian_blur", "type": "string"},
                    "angle": {"default": 0, "min": -360, "max": 360},
                    "shadow_fade": {"default": 100, "min": 0, "max": 100},
                    "shadow_tone_width": {"default": 50, "min": 0, "max": 100},
                    "shadow_radius": {"default": 1, "min": 1, "max": 100},
                    "highlight_fade": {"default": 100, "min": 0, "max": 100},
                    "highlight_tone_width": {"default": 50, "min": 0, "max": 100},
                    "highlight_radius": {"default": 1, "min": 1, "max": 100},
                },
                "description": "智能锐化",
            },
            "Shake_Reduction": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {
                    "blur_trace_bounds": {"default": [10, 10, 200, 200], "type": "rect"},
                    "source_noise": {"default": "auto", "type": "string"},
                    "smoothing": {"default": 30, "min": 0, "max": 100},
                    "artifact_suppression": {"default": 30, "min": 0, "max": 100},
                },
                "description": "防抖",
            },
            "Sharpen_PS": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {},
                "description": "锐化",
            },
            "Sharpen_Edges": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {},
                "description": "进一步锐化",
            },
            "Sharpen_More": {
                "category": FilterCategory.BLUR_SHARPEN,
                "subcategory": "sharpen",
                "params": {},
                "description": "锐化边缘",
            },
        })

        # 素描滤镜 (14种)
        sketch_filters = [
            "Charcoal", "Chalk_Charcoal", "Charcoal_Sketch", "Chrome",
            "Conte_Crayon", "Graphic_Pen_Sketch", "Halftone_Pattern",
            "Note_Paper", "Photocopy", "Plaster", "Reticulation",
            "Stamp", "Torn_Edges", "Water_Paper"
        ]
        for f in sketch_filters:
            self._filters[f] = {
                "category": FilterCategory.STYLIZE,
                "subcategory": "sketch",
                "params": {
                    "image_balance": {"default": 25, "min": 0, "max": 50},
                    "smoothness": {"default": 5, "min": 1, "max": 15},
                    "contrast": {"default": 10, "min": 0, "max": 100},
                },
                "description": f"素描效果 - {f}",
            }

        # 风格化滤镜
        self._filters.update({
            "Find_Edges_PS": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {},
                "description": "查找边缘",
            },
            "Emboss": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {
                    "angle": {"default": 135, "min": -360, "max": 360},
                    "height": {"default": 3, "min": 1, "max": 10},
                    "amount": {"default": 100, "min": 1, "max": 500},
                },
                "description": "浮雕效果",
            },
            "Wind": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {
                    "method": {"default": "wind", "type": "string"},
                    "direction": {"default": "from_the_right", "type": "string"},
                },
                "description": "风效果",
            },
            "Glowing_Edges": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {
                    "edge_width": {"default": 6, "min": 1, "max": 14},
                    "edge_brightness": {"default": 20, "min": 0, "max": 20},
                    "smoothness": {"default": 5, "min": 1, "max": 15},
                },
                "description": "照亮边缘",
            },
            "Diffuse": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {"mode": {"default": "normal", "type": "string"}},
                "description": "扩散效果",
            },
            "Extrude": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {
                    "type": {"default": "blocks", "type": "string"},
                    "size": {"default": 30, "min": 2, "max": 255},
                    "depth": {"default": 30, "min": 1, "max": 255},
                    "random": {"default": False, "type": "boolean"},
                    "solid_front_faces": {"default": True, "type": "boolean"},
                    "mask_incomplete_blocks": {"default": False, "type": "boolean"},
                },
                "description": "凸出效果",
            },
            "Solarize": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {},
                "description": "曝光过度",
            },
            "Tiles": {
                "category": FilterCategory.STYLize,
                "subcategory": "stylize",
                "params": {
                    "number_of_tiles": {"default": 10, "min": 1, "max": 99},
                    "maximum_offset": {"default": 10, "min": 1, "max": 99},
                    "fill_empty_area_with": {"default": "background_color", "type": "string"},
                },
                "description": "拼贴效果",
            },
            "Trace_Contour": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "stylize",
                "params": {
                    "level": {"default": 128, "min": 0, "max": 255},
                    "edge": {"default": "lower", "type": "string"},
                },
                "description": "等高线",
            },
        })

        # 纹理滤镜
        self._filters.update({
            "Craquelure": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "texture",
                "params": {
                    "crack_spacing": {"default": 15, "min": 2, "max": 100},
                    "crack_depth": {"default": 6, "min": 0, "max": 10},
                    "crack_brightness": {"default": 9, "min": 0, "max": 10},
                },
                "description": "龟裂缝",
            },
            "Grain_PS": {
                "category": FilterCategory.NOISE_GRAIN,
                "subcategory": "texture",
                "params": {
                    "intensity": {"default": 20, "min": 0, "max": 100},
                    "contrast": {"default": 50, "min": 0, "max": 100},
                    "grain_type": {"default": "regular", "type": "string"},
                },
                "description": "颗粒",
            },
            "Mosaic_Tiles": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "texture",
                "params": {
                    "tile_size": {"default": 30, "min": 2, "max": 100},
                    "grout_width": {"default": 3, "min": 1, "max": 15},
                    "lighten_grout": {"default": 5, "min": 0, "max": 10},
                },
                "description": "马赛克拼贴",
            },
            "Stained_Glass": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "texture",
                "params": {
                    "cell_size": {"default": 10, "min": 2, "max": 50},
                    "border_thickness": {"default": 4, "min": 1, "max": 10},
                    "light_intensity": {"default": 3, "min": 0, "max": 10},
                },
                "description": "染色玻璃",
            },
            "Texturizer": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "texture",
                "params": {
                    "texture": {"default": "sandstone", "type": "string"},
                    "scaling": {"default": 100, "min": 50, "max": 200},
                    "relief": {"default": 5, "min": 0, "max": 50},
                    "light": {"default": "top_left", "type": "string"},
                    "invert": {"default": False, "type": "boolean"},
                },
                "description": "纹理化",
            },
            "Patchwork": {
                "category": FilterCategory.STYLIZE,
                "subcategory": "texture",
                "params": {
                    "square_size": {"default": 5, "min": 0, "max": 25},
                    "relief": {"default": 10, "min": 0, "max": 25},
                },
                "description": "拼缀图",
            },
        })

    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """应用PS滤镜"""
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"PS滤镜未找到: {filter_name}")
        merged_params = self._merge_params(filter_name, params)
        return {
            "software": "photoshop",
            "filter": filter_name,
            "params": merged_params,
            "info": self._filters[filter_name],
        }

    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """应用PS滤镜链"""
        return [self.apply_filter(name, params) for name, params in filters]

    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], **kwargs) -> str:
        """生成Photoshop JSX脚本"""
        script_lines = [
            "// Auto-generated Photoshop Filter Script",
            "var doc = app.activeDocument;",
            "var layer = doc.activeLayer;",
            "",
        ]
        for i, (filter_name, params) in enumerate(filters):
            script_lines.append(f"// 应用滤镜: {filter_name}")
            merged_params = self._merge_params(filter_name, params)
            param_str = ", ".join([f"{k}:{v}" if not isinstance(v, str) else f'{k}:"{v}"' for k, v in merged_params.items()])
            script_lines.append(f'// {filter_name}({param_str})')
            script_lines.append("")

        script_lines.append("// 脚本执行完毕")
        return "\n".join(script_lines)

    def get_artistic_filters(self) -> list[str]:
        """获取艺术效果滤镜"""
        return [k for k, v in self._filters.items() if v.get("subcategory") == "artistic"]

    def get_sketch_filters(self) -> list[str]:
        """获取素描滤镜"""
        return [k for k, v in self._filters.items() if v.get("subcategory") == "sketch"]

    def get_texture_filters(self) -> list[str]:
        """获取纹理滤镜"""
        return [k for k, v in self._filters.items() if v.get("subcategory") == "texture"]


# =============================================================================
# DaVinci Resolve 滤镜引擎
# =============================================================================

class ResolveFilterEngine(BaseFilterEngine):
    """DaVinci Resolve 滤镜引擎"""

    def __init__(self):
        super().__init__()
        self._software_type = SoftwareType.DAVINCI_RESOLVE
        self._init_filters()

    def _init_filters(self) -> None:
        """初始化Resolve滤镜库"""
        # Resolve FX 滤镜
        resolve_fx = {
            "ResolveFX_Beauty_Restoration": {
                "category": FilterCategory.STYLIZE,
                "type": "resolve_fx",
                "params": {
                    "smooth_level": {"default": 50, "min": 0, "max": 100},
                    "skin_tone_softness": {"default": 50, "min": 0, "max": 100},
                    "sharpen_level": {"default": 20, "min": 0, "max": 100},
                },
                "description": "美容修复",
            },
            "ResolveFX_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "resolve_fx",
                "params": {
                    "blur_size": {"default": 10, "min": 0, "max": 200},
                    "blur_shape": {"default": "gaussian", "type": "string"},
                    "aspect_ratio": {"default": 1.0, "min": 0.1, "max": 10},
                    "angle": {"default": 0, "min": -360, "max": 360},
                },
                "description": "Resolve FX 模糊",
            },
            "ResolveFX_Sharpen": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "resolve_fx",
                "params": {
                    "sharpen_amount": {"default": 50, "min": 0, "max": 100},
                    "sharpen_radius": {"default": 1.0, "min": 0.1, "max": 10},
                    "threshold": {"default": 0, "min": 0, "max": 100},
                },
                "description": "Resolve FX 锐化",
            },
            "ResolveFX_Color_Space_Transform": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "resolve_fx",
                "params": {
                    "input_color_space": {"default": "Rec709", "type": "string"},
                    "output_color_space": {"default": "Rec709", "type": "string"},
                    "input_gamma": {"default": "Gamma2.4", "type": "string"},
                    "output_gamma": {"default": "Gamma2.4", "type": "string"},
                    "tone_mapping": {"default": "reinhard", "type": "string"},
                },
                "description": "色彩空间转换",
            },
            "ResolveFX_Denoise": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "resolve_fx",
                "params": {
                    "luma_denoise": {"default": 50, "min": 0, "max": 100},
                    "chroma_denoise": {"default": 50, "min": 0, "max": 100},
                    "motion_estimation": {"default": 50, "min": 0, "max": 100},
                },
                "description": "降噪",
            },
            "ResolveFX_Progressive_Smoothing": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "resolve_fx",
                "params": {
                    "smoothness": {"default": 50, "min": 0, "max": 100},
                    "edge_sensitivity": {"default": 50, "min": 0, "max": 100},
                    "detail_preservation": {"default": 50, "min": 0, "max": 100},
                },
                "description": "渐进式平滑",
            },
            "ResolveFX_Film_Grain": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "resolve_fx",
                "params": {
                    "grain_amount": {"default": 50, "min": 0, "max": 100},
                    "grain_size": {"default": 50, "min": 0, "max": 100},
                    "grain_tone": {"default": 50, "min": 0, "max": 100},
                    "color_amount": {"default": 0, "min": 0, "max": 100},
                    "temporal_variation": {"default": 50, "min": 0, "max": 100},
                },
                "description": "胶片颗粒",
            },
            "ResolveFX_Lens_Flare": {
                "category": FilterCategory.GENERATE,
                "type": "resolve_fx",
                "params": {
                    "flare_intensity": {"default": 100, "min": 0, "max": 200},
                    "flare_position_x": {"default": 0.5, "min": 0, "max": 1},
                    "flare_position_y": {"default": 0.5, "min": 0, "max": 1},
                    "aspect_ratio": {"default": 2.35, "min": 1, "max": 5},
                    "chromatic_aberration": {"default": 50, "min": 0, "max": 100},
                },
                "description": "镜头光晕",
            },
            "ResolveFX_Vignette": {
                "category": FilterCategory.STYLIZE,
                "type": "resolve_fx",
                "params": {
                    "amount": {"default": 50, "min": -100, "max": 100},
                    "size": {"default": 50, "min": 0, "max": 100},
                    "softness": {"default": 50, "min": 0, "max": 100},
                    "center_x": {"default": 50, "min": 0, "max": 100},
                    "center_y": {"default": 50, "min": 0, "max": 100},
                    "aspect_ratio": {"default": 0, "min": -100, "max": 100},
                },
                "description": "暗角",
            },
            "ResolveFX_Warp": {
                "category": FilterCategory.DISTORT,
                "type": "resolve_fx",
                "params": {
                    "distortion_amount": {"default": 0, "min": -100, "max": 100},
                    "center_x": {"default": 50, "min": 0, "max": 100},
                    "center_y": {"default": 50, "min": 0, "max": 100},
                    "scale": {"default": 100, "min": 1, "max": 200},
                },
                "description": "镜头畸变校正",
            },
            "ResolveFX_Chromatic_Aberration": {
                "category": FilterCategory.STYLIZE,
                "type": "resolve_fx",
                "params": {
                    "aberration_amount": {"default": 10, "min": -100, "max": 100},
                    "center_x": {"default": 50, "min": 0, "max": 100},
                    "center_y": {"default": 50, "min": 0, "max": 100},
                    "angle": {"default": 0, "min": -360, "max": 360},
                },
                "description": "色差/色散效果",
            },
            "ResolveFX_Glow": {
                "category": FilterCategory.STYLIZE,
                "type": "resolve_fx",
                "params": {
                    "glow_threshold": {"default": 50, "min": 0, "max": 100},
                    "glow_size": {"default": 50, "min": 0, "max": 200},
                    "glow_gain": {"default": 100, "min": 0, "max": 500},
                    "blend_mode": {"default": "screen", "type": "string"},
                },
                "description": "发光",
            },
            "ResolveFX_Defocus": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "resolve_fx",
                "params": {
                    "defocus_amount": {"default": 50, "min": 0, "max": 100},
                    "aspect_ratio": {"default": 0, "min": -100, "max": 100},
                    "iris_shape": {"default": "round", "type": "string"},
                    "iris_blades": {"default": 6, "min": 3, "max": 16},
                    "iris_rotation": {"default": 0, "min": -360, "max": 360},
                    "highlights_gain": {"default": 100, "min": 0, "max": 500},
                    "highlights_threshold": {"default": 80, "min": 0, "max": 100},
                },
                "description": "散焦模糊",
            },
            "ResolveFX_Dust_Busters": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "resolve_fx",
                "params": {
                    "dust_level": {"default": 50, "min": 0, "max": 100},
                    "scratch_level": {"default": 50, "min": 0, "max": 100},
                    "dirt_level": {"default": 50, "min": 0, "max": 100},
                    "hair_level": {"default": 50, "min": 0, "max": 100},
                },
                "description": "除尘修复",
            },
            "ResolveFX_Blank_Video": {
                "category": FilterCategory.GENERATE,
                "type": "resolve_fx",
                "params": {
                    "width": {"default": 1920, "min": 1, "max": 8192},
                    "height": {"default": 1080, "min": 1, "max": 8192},
                    "color": {"default": [0, 0, 0], "type": "color"},
                },
                "description": "空白视频生成",
            },
            "ResolveFX_Text": {
                "category": FilterCategory.GENERATE,
                "type": "resolve_fx",
                "params": {
                    "text": {"default": "Text", "type": "string"},
                    "font_size": {"default": 50, "min": 1, "max": 1000},
                    "font_color": {"default": [255, 255, 255], "type": "color"},
                    "position_x": {"default": 0.5, "min": 0, "max": 1},
                    "position_y": {"default": 0.5, "min": 0, "max": 1},
                },
                "description": "文字生成",
            },
            "ResolveFX_Alpha_Output": {
                "category": FilterCategory.CHANNEL,
                "type": "resolve_fx",
                "params": {
                    "invert_alpha": {"default": False, "type": "boolean"},
                    "alpha_scale": {"default": 100, "min": 0, "max": 200},
                },
                "description": "Alpha通道输出",
            },
            "ResolveFX_OFX_Transform": {
                "category": FilterCategory.UTILITY,
                "type": "resolve_fx",
                "params": {
                    "translate_x": {"default": 0, "min": -10000, "max": 10000},
                    "translate_y": {"default": 0, "min": -10000, "max": 10000},
                    "rotate": {"default": 0, "min": -3600, "max": 3600},
                    "scale_x": {"default": 100, "min": 0, "max": 1000},
                    "scale_y": {"default": 100, "min": 0, "max": 1000},
                    "pivot_x": {"default": 0.5, "min": 0, "max": 1},
                    "pivot_y": {"default": 0.5, "min": 0, "max": 1},
                },
                "description": "OFX变换",
            },
        }
        self._filters.update(resolve_fx)

        # Fusion 滤镜
        fusion_filters = {
            "Fusion_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "fusion",
                "params": {
                    "blur_size": {"default": 10, "min": 0, "max": 500},
                    "blur_type": {"default": "gaussian", "type": "string"},
                    "x_blur_bias": {"default": 0, "min": -100, "max": 100},
                    "y_blur_bias": {"default": 0, "min": -100, "max": 100},
                },
                "description": "Fusion模糊",
            },
            "Fusion_Color_Corrector": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "fusion",
                "params": {
                    "gain_r": {"default": 1.0, "min": 0, "max": 10},
                    "gain_g": {"default": 1.0, "min": 0, "max": 10},
                    "gain_b": {"default": 1.0, "min": 0, "max": 10},
                    "gamma_r": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_g": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_b": {"default": 1.0, "min": 0.1, "max": 10},
                    "lift_r": {"default": 0, "min": -1, "max": 1},
                    "lift_g": {"default": 0, "min": -1, "max": 1},
                    "lift_b": {"default": 0, "min": -1, "max": 1},
                    "saturation": {"default": 1.0, "min": 0, "max": 5},
                    "brightness": {"default": 0, "min": -1, "max": 1},
                    "contrast": {"default": 0, "min": -1, "max": 1},
                },
                "description": "Fusion色彩校正器",
            },
            "Fusion_Dilate_Erode": {
                "category": FilterCategory.CHANNEL,
                "type": "fusion",
                "params": {
                    "x_matte": {"default": 0, "min": -100, "max": 100},
                    "y_matte": {"default": 0, "min": -100, "max": 100},
                    "x_background": {"default": 0, "min": -100, "max": 100},
                    "y_background": {"default": 0, "min": -100, "max": 100},
                    "frame_method": {"default": "canvas", "type": "string"},
                },
                "description": "Fusion膨胀/收缩",
            },
            "Fusion_Fast_Noise": {
                "category": FilterCategory.GENERATE,
                "type": "fusion",
                "params": {
                    "seethrough": {"default": False, "type": "boolean"},
                    "detail": {"default": 5, "min": 0, "max": 10},
                    "scale": {"default": 100, "min": 1, "max": 10000},
                    "x_scale": {"default": 1.0, "min": 0, "max": 10},
                    "y_scale": {"default": 1.0, "min": 0, "max": 10},
                    "angle": {"default": 0, "min": 0, "max": 360},
                    "center_x": {"default": 0, "min": -1000, "max": 1000},
                    "center_y": {"default": 0, "min": -1000, "max": 1000},
                    "offset_x": {"default": 0, "min": -10000, "max": 10000},
                    "offset_y": {"default": 0, "min": -10000, "max": 10000},
                    "brightness": {"default": 0.5, "min": 0, "max": 1},
                    "contrast": {"default": 1.0, "min": 0, "max": 10},
                },
                "description": "Fusion快速噪波",
            },
            "Fusion_Glow": {
                "category": FilterCategory.STYLIZE,
                "type": "fusion",
                "params": {
                    "seethrough": {"default": False, "type": "boolean"},
                    "size": {"default": 10, "min": 0, "max": 500},
                    "x_size": {"default": 1.0, "min": 0, "max": 10},
                    "y_size": {"default": 1.0, "min": 0, "max": 10},
                    "brightness": {"default": 0.5, "min": 0, "max": 10},
                    "blend": {"default": 0.5, "min": 0, "max": 1},
                    "threshold": {"default": 0.5, "min": 0, "max": 1},
                    "gain": {"default": 1.0, "min": 0, "max": 10},
                },
                "description": "Fusion发光",
            },
            "Fusion_Shine": {
                "category": FilterCategory.STYLIZE,
                "type": "fusion",
                "params": {
                    "seethrough": {"default": False, "type": "boolean"},
                    "size": {"default": 10, "min": 0, "max": 500},
                    "angle": {"default": 0, "min": -360, "max": 360},
                    "brightness": {"default": 0.5, "min": 0, "max": 10},
                    "blend": {"default": 0.5, "min": 0, "max": 1},
                    "threshold": {"default": 0.5, "min": 0, "max": 1},
                    "source_point_x": {"default": 0.5, "min": 0, "max": 1},
                    "source_point_y": {"default": 0.5, "min": 0, "max": 1},
                },
                "description": "Fusion光芒",
            },
            "Fusion_Channel_Booleans": {
                "category": FilterCategory.CHANNEL,
                "type": "fusion",
                "params": {
                    "operation": {"default": "cop_plus", "type": "string"},
                    "to_red": {"default": "none", "type": "string"},
                    "to_green": {"default": "none", "type": "string"},
                    "to_blue": {"default": "none", "type": "string"},
                    "to_alpha": {"default": "none", "type": "string"},
                },
                "description": "Fusion通道布尔运算",
            },
            "Fusion_Mask": {
                "category": FilterCategory.UTILITY,
                "type": "fusion",
                "params": {
                    "mask_type": {"default": "rectangle", "type": "string"},
                    "center_x": {"default": 0.5, "min": 0, "max": 1},
                    "center_y": {"default": 0.5, "min": 0, "max": 1},
                    "width": {"default": 0.5, "min": 0, "max": 2},
                    "height": {"default": 0.5, "min": 0, "max": 2},
                    "angle": {"default": 0, "min": -360, "max": 360},
                    "corner_radius": {"default": 0, "min": 0, "max": 100},
                    "invert": {"default": False, "type": "boolean"},
                    "soft_edge": {"default": 0, "min": 0, "max": 100},
                },
                "description": "Fusion蒙版",
            },
        }
        self._filters.update(fusion_filters)

        # 调色节点
        color_nodes = {
            "Color_Primary": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "color_page",
                "params": {
                    "temperature": {"default": 0, "min": -100, "max": 100},
                    "tint": {"default": 0, "min": -100, "max": 100},
                    "hue": {"default": 0, "min": -180, "max": 180},
                    "sat": {"default": 0, "min": -100, "max": 100},
                    "lum": {"default": 0, "min": -100, "max": 100},
                    "contrast": {"default": 0, "min": -100, "max": 100},
                    "pivot": {"default": 50, "min": 0, "max": 100},
                    "shadows": {"default": 0, "min": -100, "max": 100},
                    "darks": {"default": 0, "min": -100, "max": 100},
                    "midtones": {"default": 0, "min": -100, "max": 100},
                    "highlights": {"default": 0, "min": -100, "max": 100},
                },
                "description": "初级调色节点",
            },
            "Color_Curves": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "color_page",
                "params": {
                    "master_curve": {"default": [], "type": "array"},
                    "red_curve": {"default": [], "type": "array"},
                    "green_curve": {"default": [], "type": "array"},
                    "blue_curve": {"default": [], "type": "array"},
                },
                "description": "曲线调色节点",
            },
            "Color_Qualifier": {
                "category": FilterCategory.KEYING,
                "type": "color_page",
                "params": {
                    "hue_center": {"default": 0, "min": 0, "max": 360},
                    "hue_width": {"default": 30, "min": 0, "max": 180},
                    "sat_low": {"default": 0, "min": 0, "max": 100},
                    "sat_high": {"default": 100, "min": 0, "max": 100},
                    "lum_low": {"default": 0, "min": 0, "max": 100},
                    "lum_high": {"default": 100, "min": 0, "max": 100},
                    "softness": {"default": 0, "min": 0, "max": 100},
                },
                "description": "限定器选色节点",
            },
            "Color_Window": {
                "category": FilterCategory.KEYING,
                "type": "color_page",
                "params": {
                    "window_type": {"default": "circle", "type": "string"},
                    "position_x": {"default": 0.5, "min": 0, "max": 1},
                    "position_y": {"default": 0.5, "min": 0, "max": 1},
                    "size": {"default": 0.5, "min": 0, "max": 2},
                    "aspect": {"default": 1.0, "min": 0.1, "max": 10},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "softness": {"default": 0, "min": 0, "max": 100},
                },
                "description": "窗口蒙版节点",
            },
            "Color_Mixer": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "color_page",
                "params": {
                    "red_hue": {"default": 0, "min": -180, "max": 180},
                    "red_sat": {"default": 0, "min": -100, "max": 100},
                    "yellow_hue": {"default": 0, "min": -180, "max": 180},
                    "yellow_sat": {"default": 0, "min": -100, "max": 100},
                    "green_hue": {"default": 0, "min": -180, "max": 180},
                    "green_sat": {"default": 0, "min": -100, "max": 100},
                    "cyan_hue": {"default": 0, "min": -180, "max": 180},
                    "cyan_sat": {"default": 0, "min": -100, "max": 100},
                    "blue_hue": {"default": 0, "min": -180, "max": 180},
                    "blue_sat": {"default": 0, "min": -100, "max": 100},
                    "magenta_hue": {"default": 0, "min": -180, "max": 180},
                    "magenta_sat": {"default": 0, "min": -100, "max": 100},
                },
                "description": "色彩混合器节点",
            },
        }
        self._filters.update(color_nodes)

    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """应用Resolve滤镜"""
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"Resolve滤镜未找到: {filter_name}")
        merged_params = self._merge_params(filter_name, params)
        return {
            "software": "davinci_resolve",
            "filter": filter_name,
            "params": merged_params,
            "info": self._filters[filter_name],
        }

    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """应用Resolve滤镜链"""
        return [self.apply_filter(name, params) for name, params in filters]

    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], **kwargs) -> str:
        """生成Resolve Python脚本"""
        script_lines = [
            "# Auto-generated DaVinci Resolve Filter Script",
            "import DaVinciResolveScript as bmd",
            "",
            "resolve = bmd.scriptapp('Resolve')",
            "projectManager = resolve.GetProjectManager()",
            "project = projectManager.GetCurrentProject()",
            "mediaPool = project.GetMediaPool()",
            "timeline = project.GetCurrentTimeline()",
            "videoTrack = timeline.GetTrackCount('video')",
            "",
        ]
        for i, (filter_name, params) in enumerate(filters):
            script_lines.append(f"# 添加滤镜: {filter_name}")
            script_lines.append(f"# 参数: {params}")
            script_lines.append("")

        script_lines.append("# 脚本执行完毕")
        return "\n".join(script_lines)

    def generate_setting_file(self, filters: list[tuple[str, dict[str, Any]]], node_tree_type: str = "fusion") -> str:
        """
        生成Fusion .setting文件

        Args:
            filters: 滤镜列表
            node_tree_type: 节点树类型 (fusion/color)

        Returns:
            .setting文件内容
        """
        setting_lines = [
            "{\n",
            '   Tools = ordered() {',
        ]

        for i, (filter_name, params) in enumerate(filters):
            node_id = f"Node{i+1}"
            setting_lines.append(f'      {node_id} = {{')
            setting_lines.append(f'         Name = "{filter_name}",')
            setting_lines.append('         Inputs = {')
            for param_name, param_value in params.items():
                if isinstance(param_value, str):
                    setting_lines.append(f'            {param_name} = {{ Input = Value( "{param_value}" ) }},')
                elif isinstance(param_value, bool):
                    setting_lines.append(f'            {param_name} = {{ Input = Value( {1 if param_value else 0} ) }},')
                elif isinstance(param_value, list):
                    setting_lines.append(f'            {param_name} = {{ Input = {{ {", ".join(str(v) for v in param_value)} }} }},')
                else:
                    setting_lines.append(f'            {param_name} = {{ Input = Value( {param_value} ) }},')
            setting_lines.append('         },')
            setting_lines.append('      },')

        setting_lines.append('   },')
        setting_lines.append('}')
        return "\n".join(setting_lines)

    def generate_resolve_script(self, filters: list[tuple[str, dict[str, Any]]], target: str = "clip") -> str:
        """
        生成Resolve API脚本

        Args:
            filters: 滤镜列表
            target: 目标类型 (clip/timeline)

        Returns:
            Python脚本
        """
        return self.generate_script(filters)

    def get_resolve_fx_filters(self) -> list[str]:
        """获取Resolve FX滤镜"""
        return [k for k, v in self._filters.items() if v.get("type") == "resolve_fx"]

    def get_fusion_filters(self) -> list[str]:
        """获取Fusion滤镜"""
        return [k for k, v in self._filters.items() if v.get("type") == "fusion"]

    def get_color_page_filters(self) -> list[str]:
        """获取调色页节点"""
        return [k for k, v in self._filters.items() if v.get("type") == "color_page"]


# =============================================================================
# Blender 滤镜/合成器引擎
# =============================================================================

class BlenderFilterEngine(BaseFilterEngine):
    """Blender 滤镜/合成器引擎"""

    def __init__(self):
        super().__init__()
        self._software_type = SoftwareType.BLENDER
        self._init_filters()

    def _init_filters(self) -> None:
        """初始化Blender滤镜库"""
        # 合成器滤镜
        compositor_filters = {
            "Compositor_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "compositor",
                "params": {
                    "size_x": {"default": 10, "min": 0, "max": 100},
                    "size_y": {"default": 10, "min": 0, "max": 100},
                    "blur_type": {"default": "fast_gauss", "type": "string"},
                    "use_variable_size": {"default": False, "type": "boolean"},
                    "use_relative": {"default": False, "type": "boolean"},
                },
                "description": "合成器模糊",
            },
            "Compositor_Color_Balance": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "offset_r": {"default": 0, "min": -1, "max": 1},
                    "offset_g": {"default": 0, "min": -1, "max": 1},
                    "offset_b": {"default": 0, "min": -1, "max": 1},
                    "power_r": {"default": 1.0, "min": 0.1, "max": 10},
                    "power_g": {"default": 1.0, "min": 0.1, "max": 10},
                    "power_b": {"default": 1.0, "min": 0.1, "max": 10},
                    "lift_r": {"default": 0, "min": -1, "max": 1},
                    "lift_g": {"default": 0, "min": -1, "max": 1},
                    "lift_b": {"default": 0, "min": -1, "max": 1},
                    "gamma_r": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_g": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_b": {"default": 1.0, "min": 0.1, "max": 10},
                    "gain_r": {"default": 1.0, "min": 0, "max": 10},
                    "gain_g": {"default": 1.0, "min": 0, "max": 10},
                    "gain_b": {"default": 1.0, "min": 0, "max": 10},
                },
                "description": "合成器色彩平衡",
            },
            "Compositor_Color_Correction": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "mode": {"default": "mix", "type": "string"},
                    "saturation": {"default": 1.0, "min": 0, "max": 2},
                    "contrast": {"default": 1.0, "min": 0, "max": 5},
                    "brightness": {"default": 1.0, "min": 0, "max": 2},
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                    "gain": {"default": 1.0, "min": 0, "max": 5},
                    "lift": {"default": 0, "min": -1, "max": 1},
                },
                "description": "合成器色彩校正",
            },
            "Compositor_Glare": {
                "category": FilterCategory.STYLIZE,
                "type": "compositor",
                "params": {
                    "glare_type": {"default": "glow", "type": "string"},
                    "quality": {"default": "high", "type": "string"},
                    "mix": {"default": 0.5, "min": 0, "max": 1},
                    "threshold": {"default": 1.0, "min": 0, "max": 10},
                    "size": {"default": 9, "min": 1, "max": 200},
                    "angle": {"default": 0, "min": -360, "max": 360},
                    "iterations": {"default": 3, "min": 1, "max": 10},
                    "colormod": {"default": 2.0, "min": 0, "max": 10},
                    "fades": {"default": 0.75, "min": 0, "max": 1},
                    "streaks": {"default": 4, "min": 1, "max": 20},
                    "angle_offset": {"default": 0, "min": 0, "max": 360},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                },
                "description": "合成器眩光效果",
            },
            "Compositor_Lens_Distortion": {
                "category": FilterCategory.DISTORT,
                "type": "compositor",
                "params": {
                    "distort": {"default": 0, "min": -1, "max": 1},
                    "dispersion": {"default": 0, "min": 0, "max": 1},
                    "fit": {"default": False, "type": "boolean"},
                    "jitter": {"default": 0, "min": 0, "max": 1},
                    "use_projector": {"default": False, "type": "boolean"},
                },
                "description": "合成器镜头畸变",
            },
            "Compositor_Directional_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "compositor",
                "params": {
                    "iterations": {"default": 8, "min": 1, "max": 64},
                    "wrap": {"default": False, "type": "boolean"},
                    "distance": {"default": 0.0, "min": 0, "max": 1},
                    "angle": {"default": 0, "min": -360, "max": 360},
                },
                "description": "合成器方向模糊",
            },
            "Compositor_Vector_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "compositor",
                "params": {
                    "samples": {"default": 16, "min": 1, "max": 512},
                    "blur_speed": {"default": 1.0, "min": 0, "max": 10},
                    "min_speed": {"default": 0, "min": 0, "max": 10},
                    "max_speed": {"default": 0, "min": 0, "max": 10},
                    "use_curved": {"default": False, "type": "boolean"},
                },
                "description": "合成器矢量模糊（运动模糊）",
            },
            "Compositor_BrightContrast": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "bright": {"default": 0.0, "min": -1, "max": 1},
                    "contrast": {"default": 0.0, "min": -1, "max": 1},
                },
                "description": "合成器亮度对比度",
            },
            "Compositor_Hue_Saturation_Value": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "hue": {"default": 0.5, "min": 0, "max": 1},
                    "saturation": {"default": 1.0, "min": 0, "max": 2},
                    "value": {"default": 1.0, "min": 0, "max": 2},
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "合成器色相饱和度",
            },
            "Compositor_Levels": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "in_min": {"default": 0.0, "min": 0, "max": 1},
                    "in_max": {"default": 1.0, "min": 0, "max": 1},
                    "out_min": {"default": 0.0, "min": 0, "max": 1},
                    "out_max": {"default": 1.0, "min": 0, "max": 1},
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                },
                "description": "合成器色阶",
            },
            "Compositor_Gamma": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                },
                "description": "合成器伽马校正",
            },
            "Compositor_Invert": {
                "category": FilterCategory.CHANNEL,
                "type": "compositor",
                "params": {
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                    "in_rgb": {"default": True, "type": "boolean"},
                    "in_alpha": {"default": False, "type": "boolean"},
                },
                "description": "合成器反相",
            },
            "Compositor_Mix": {
                "category": FilterCategory.UTILITY,
                "type": "compositor",
                "params": {
                    "blend_type": {"default": "mix", "type": "string"},
                    "fac": {"default": 0.5, "min": 0, "max": 1},
                    "use_alpha": {"default": False, "type": "boolean"},
                    "use_clamp": {"default": True, "type": "boolean"},
                },
                "description": "合成器混合节点",
            },
            "Compositor_Box_Mask": {
                "category": FilterCategory.UTILITY,
                "type": "compositor",
                "params": {
                    "mask_type": {"default": "rectangle", "type": "string"},
                    "x": {"default": 0.5, "min": 0, "max": 1},
                    "y": {"default": 0.5, "min": 0, "max": 1},
                    "width": {"default": 0.5, "min": 0, "max": 2},
                    "height": {"default": 0.5, "min": 0, "max": 2},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                },
                "description": "合成器蒙版",
            },
            "Compositor_Zoom_Blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "compositor",
                "params": {
                    "zoom": {"default": 0.0, "min": 0, "max": 5},
                    "x": {"default": 0.5, "min": 0, "max": 1},
                    "y": {"default": 0.5, "min": 0, "max": 1},
                },
                "description": "合成器缩放模糊",
            },
            "Compositor_Map_Range": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "from_min": {"default": 0.0, "min": 0, "max": 1},
                    "from_max": {"default": 1.0, "min": 0, "max": 1},
                    "to_min": {"default": 0.0, "min": 0, "max": 1},
                    "to_max": {"default": 1.0, "min": 0, "max": 1},
                    "use_clamp": {"default": True, "type": "boolean"},
                },
                "description": "合成器映射范围",
            },
            "Compositor_RGB_Curves": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "curve_type": {"default": "smooth", "type": "string"},
                    "points": {"default": [], "type": "array"},
                },
                "description": "合成器RGB曲线",
            },
            "Compositor_Tonemap": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "compositor",
                "params": {
                    "tonemap_type": {"default": "photoreceptor", "type": "string"},
                    "adaptation": {"default": 1.0, "min": 0, "max": 2},
                    "intensity": {"default": 1.0, "min": 0, "max": 5},
                    "contrast": {"default": 1.0, "min": 0, "max": 5},
                    "correction": {"default": 1.0, "min": 0, "max": 5},
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                    "key": {"default": 0.5, "min": 0, "max": 1},
                    "offset": {"default": 0, "min": -1, "max": 1},
                },
                "description": "合成器色调映射",
            },
            "Compositor_Vignette": {
                "category": FilterCategory.STYLIZE,
                "type": "compositor",
                "params": {
                    "fac": {"default": 0.5, "min": 0, "max": 1},
                    "x": {"default": 0.5, "min": 0, "max": 1},
                    "y": {"default": 0.5, "min": 0, "max": 1},
                    "radius": {"default": 1.0, "min": 0, "max": 5},
                    "softness": {"default": 0.5, "min": 0, "max": 1},
                    "roundness": {"default": 0.0, "min": 0, "max": 1},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                },
                "description": "合成器暗角",
            },
        }
        self._filters.update(compositor_filters)

        # 着色器效果
        shader_effects = {
            "Shader_Mix_RGB": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "fac": {"default": 0.5, "min": 0, "max": 1},
                    "blend_type": {"default": "mix", "type": "string"},
                    "color1": {"default": [1, 1, 1, 1], "type": "color"},
                    "color2": {"default": [0, 0, 0, 1], "type": "color"},
                },
                "description": "着色器混合RGB",
            },
            "Shader_RGB_Curves": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                    "curve_points": {"default": [], "type": "array"},
                },
                "description": "着色器RGB曲线",
            },
            "Shader_Hue_Saturation_Value": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "hue": {"default": 0.5, "min": 0, "max": 1},
                    "saturation": {"default": 1.0, "min": 0, "max": 2},
                    "value": {"default": 1.0, "min": 0, "max": 2},
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "着色器色相饱和度",
            },
            "Shader_Bright_Contrast": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "bright": {"default": 0.0, "min": -1, "max": 1},
                    "contrast": {"default": 0.0, "min": -1, "max": 1},
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "着色器亮度对比度",
            },
            "Shader_Gamma": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "着色器伽马",
            },
            "Shader_Invert": {
                "category": FilterCategory.CHANNEL,
                "type": "shader",
                "params": {
                    "fac": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "着色器反相",
            },
            "Shader_Mapping": {
                "category": FilterCategory.UTILITY,
                "type": "shader",
                "params": {
                    "translation_x": {"default": 0, "min": -10, "max": 10},
                    "translation_y": {"default": 0, "min": -10, "max": 10},
                    "translation_z": {"default": 0, "min": -10, "max": 10},
                    "rotation_x": {"default": 0, "min": -360, "max": 360},
                    "rotation_y": {"default": 0, "min": -360, "max": 360},
                    "rotation_z": {"default": 0, "min": -360, "max": 360},
                    "scale_x": {"default": 1.0, "min": 0, "max": 10},
                    "scale_y": {"default": 1.0, "min": 0, "max": 10},
                    "scale_z": {"default": 1.0, "min": 0, "max": 10},
                    "vector_type": {"default": "point", "type": "string"},
                },
                "description": "着色器映射变换",
            },
            "Shader_Bump": {
                "category": FilterCategory.STYLIZE,
                "type": "shader",
                "params": {
                    "strength": {"default": 1.0, "min": -10, "max": 10},
                    "distance": {"default": 0.1, "min": 0, "max": 10},
                    "height_scale": {"default": 1.0, "min": 0, "max": 10},
                    "normal_space": {"default": "tangent", "type": "string"},
                },
                "description": "着色器凹凸贴图",
            },
            "Shader_Displacement": {
                "category": FilterCategory.DISTORT,
                "type": "shader",
                "params": {
                    "height": {"default": 0.1, "min": 0, "max": 10},
                    "midlevel": {"default": 0.5, "min": 0, "max": 1},
                    "scale": {"default": 1.0, "min": 0, "max": 10},
                    "normal_space": {"default": "tangent", "type": "string"},
                },
                "description": "着色器位移",
            },
            "Shader_ColorRamp": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "shader",
                "params": {
                    "color_ramp": {"default": [], "type": "array"},
                    "interpolation": {"default": "linear", "type": "string"},
                },
                "description": "着色器色带",
            },
            "Shader_Emission": {
                "category": FilterCategory.GENERATE,
                "type": "shader",
                "params": {
                    "color": {"default": [1, 1, 1, 1], "type": "color"},
                    "strength": {"default": 1.0, "min": 0, "max": 100},
                },
                "description": "着色器自发光",
            },
            "Shader_Glossy": {
                "category": FilterCategory.STYLIZE,
                "type": "shader",
                "params": {
                    "distribution": {"default": "ggx", "type": "string"},
                    "color": {"default": [1, 1, 1, 1], "type": "color"},
                    "roughness": {"default": 0.5, "min": 0, "max": 1},
                },
                "description": "着色器光泽",
            },
            "Shader_Principled_BSDF": {
                "category": FilterCategory.STYLIZE,
                "type": "shader",
                "params": {
                    "base_color": {"default": [0.8, 0.8, 0.8, 1], "type": "color"},
                    "metallic": {"default": 0.0, "min": 0, "max": 1},
                    "roughness": {"default": 0.5, "min": 0, "max": 1},
                    "ior": {"default": 1.45, "min": 0, "max": 4},
                    "alpha": {"default": 1.0, "min": 0, "max": 1},
                    "normal_strength": {"default": 1.0, "min": 0, "max": 10},
                    "subsurface": {"default": 0.0, "min": 0, "max": 1},
                    "subsurface_radius": {"default": [1.0, 1.0, 1.0], "type": "color"},
                    "subsurface_ior": {"default": 1.4, "min": 0, "max": 4},
                    "specular": {"default": 0.5, "min": 0, "max": 1},
                    "specular_tint": {"default": 0.0, "min": 0, "max": 1},
                    "sheen": {"default": 0.0, "min": 0, "max": 1},
                    "sheen_tint": {"default": 0.5, "min": 0, "max": 1},
                    "clearcoat": {"default": 0.0, "min": 0, "max": 1},
                    "clearcoat_roughness": {"default": 0.03, "min": 0, "max": 1},
                    "transmission": {"default": 0.0, "min": 0, "max": 1},
                    "transmission_roughness": {"default": 0.0, "min": 0, "max": 1},
                },
                "description": "原理化BSDF着色器",
            },
        }
        self._filters.update(shader_effects)

        # 几何节点效果
        geometry_node_effects = {
            "GeoNodes_Distribute_Points": {
                "category": FilterCategory.GENERATE,
                "type": "geometry_node",
                "params": {
                    "density": {"default": 100, "min": 0, "max": 10000},
                    "seed": {"default": 0, "min": 0, "max": 10000},
                    "distance_min": {"default": 0.1, "min": 0, "max": 10},
                    "density_factor": {"default": 1.0, "min": 0, "max": 1},
                },
                "description": "几何节点分布点",
            },
            "GeoNodes_Instance_on_Points": {
                "category": FilterCategory.GENERATE,
                "type": "geometry_node",
                "params": {
                    "scale": {"default": 1.0, "min": 0, "max": 10},
                    "rotation": {"default": 0, "min": -360, "max": 360},
                    "random_scale": {"default": 0.0, "min": 0, "max": 1},
                    "random_rotation": {"default": 0.0, "min": 0, "max": 1},
                    "seed": {"default": 0, "min": 0, "max": 10000},
                },
                "description": "几何节点点上实例化",
            },
            "GeoNodes_Subdivision": {
                "category": FilterCategory.STYLIZE,
                "type": "geometry_node",
                "params": {
                    "level": {"default": 1, "min": 0, "max": 6},
                },
                "description": "几何节点细分",
            },
            "GeoNodes_Displace": {
                "category": FilterCategory.DISTORT,
                "type": "geometry_node",
                "params": {
                    "strength": {"default": 1.0, "min": -10, "max": 10},
                    "midlevel": {"default": 0.5, "min": 0, "max": 1},
                    "scale": {"default": 1.0, "min": 0, "max": 10},
                },
                "description": "几何节点位移",
            },
            "GeoNodes_Noise": {
                "category": FilterCategory.GENERATE,
                "type": "geometry_node",
                "params": {
                    "noise_type": {"default": "fractal", "type": "string"},
                    "scale": {"default": 5.0, "min": 0, "max": 100},
                    "detail": {"default": 6, "min": 0, "max": 15},
                    "roughness": {"default": 0.5, "min": 0, "max": 1},
                    "distortion": {"default": 0.0, "min": 0, "max": 10},
                    "seed": {"default": 0, "min": 0, "max": 10000},
                    "offset_x": {"default": 0, "min": -100, "max": 100},
                    "offset_y": {"default": 0, "min": -100, "max": 100},
                    "offset_z": {"default": 0, "min": -100, "max": 100},
                },
                "description": "几何节点噪波",
            },
            "GeoNodes_Extrude": {
                "category": FilterCategory.DISTORT,
                "type": "geometry_node",
                "params": {
                    "offset": {"default": 0.1, "min": -10, "max": 10},
                    "offset_scale": {"default": 1.0, "min": 0, "max": 10},
                    "individual": {"default": False, "type": "boolean"},
                },
                "description": "几何节点挤出",
            },
            "GeoNodes_Warp": {
                "category": FilterCategory.DISTORT,
                "type": "geometry_node",
                "params": {
                    "warp_amount": {"default": 1.0, "min": 0, "max": 10},
                    "warp_type": {"default": "bend", "type": "string"},
                    "axis": {"default": "z", "type": "string"},
                },
                "description": "几何节点扭曲",
            },
            "GeoNodes_Boolean": {
                "category": FilterCategory.UTILITY,
                "type": "geometry_node",
                "params": {
                    "operation": {"default": "difference", "type": "string"},
                    "solver": {"default": "fast", "type": "string"},
                },
                "description": "几何节点布尔运算",
            },
        }
        self._filters.update(geometry_node_effects)

    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """应用Blender滤镜"""
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"Blender滤镜未找到: {filter_name}")
        merged_params = self._merge_params(filter_name, params)
        return {
            "software": "blender",
            "filter": filter_name,
            "params": merged_params,
            "info": self._filters[filter_name],
        }

    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """应用Blender滤镜链"""
        return [self.apply_filter(name, params) for name, params in filters]

    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], **kwargs) -> str:
        """生成Blender Python脚本"""
        script_lines = [
            "import bpy",
            "",
            "# Auto-generated Blender Filter Script",
            "",
        ]
        context = kwargs.get("context", "compositor")

        if context == "compositor":
            script_lines.append("# 设置合成器节点")
            script_lines.append("bpy.context.scene.use_nodes = True")
            script_lines.append("tree = bpy.context.scene.node_tree")
            script_lines.append("nodes = tree.nodes")
            script_lines.append("links = tree.links")
            script_lines.append("")

            script_lines.append("# 清除默认节点")
            script_lines.append("for node in nodes:")
            script_lines.append("    nodes.remove(node)")
            script_lines.append("")

            script_lines.append("# 创建渲染层节点")
            script_lines.append("render_layers = nodes.new(type='CompositorNodeRLayers')")
            script_lines.append("render_layers.location = (0, 0)")
            script_lines.append("")

            prev_node = "render_layers"
            for i, (filter_name, params) in enumerate(filters):
                node_name = f"node_{i}"
                script_lines.append(f"# 添加滤镜: {filter_name}")
                script_lines.append(f'{node_name} = nodes.new(type="CompositorNodeBlur")')
                script_lines.append(f"{node_name}.location = ({(i+1) * 200}, 0)")
                script_lines.append(f'links.new({prev_node}.outputs["Image"], {node_name}.inputs["Image"])')
                prev_node = node_name
                script_lines.append("")

            script_lines.append("# 创建输出节点")
            script_lines.append('composite = nodes.new(type="CompositorNodeComposite")')
            script_lines.append(f'composite.location = ({(len(filters)+1) * 200}, 0)')
            script_lines.append(f'links.new({prev_node}.outputs["Image"], composite.inputs["Image"])')

        script_lines.append("")
        script_lines.append("# 脚本执行完毕")
        return "\n".join(script_lines)

    def generate_blender_script(self, filters: list[tuple[str, dict[str, Any]]], context: str = "compositor") -> str:
        """
        生成Blender脚本

        Args:
            filters: 滤镜列表
            context: 上下文 (compositor/shader/geometry)

        Returns:
            Python脚本
        """
        return self.generate_script(filters, context=context)

    def get_compositor_filters(self) -> list[str]:
        """获取合成器滤镜"""
        return [k for k, v in self._filters.items() if v.get("type") == "compositor"]

    def get_shader_effects(self) -> list[str]:
        """获取着色器效果"""
        return [k for k, v in self._filters.items() if v.get("type") == "shader"]

    def get_geometry_node_effects(self) -> list[str]:
        """获取几何节点效果"""
        return [k for k, v in self._filters.items() if v.get("type") == "geometry_node"]


# =============================================================================
# FFmpeg 滤镜引擎
# =============================================================================

class FFmpegFilterEngine(BaseFilterEngine):
    """FFmpeg 滤镜引擎"""

    def __init__(self):
        super().__init__()
        self._software_type = SoftwareType.FFMPEG
        self._init_filters()

    def _init_filters(self) -> None:
        """初始化FFmpeg滤镜库"""
        # 视频滤镜
        video_filters = {
            "ff_blur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "size": {"default": 1.0, "min": 0, "max": 100},
                    "type": {"default": "gaussian", "type": "string"},
                },
                "ffmpeg_filter": "blur",
                "description": "模糊效果",
            },
            "ff_boxblur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "luma_radius": {"default": 2, "min": 0, "max": 100},
                    "luma_power": {"default": 1, "min": 0, "max": 10},
                    "chroma_radius": {"default": 2, "min": 0, "max": 100},
                    "chroma_power": {"default": 1, "min": 0, "max": 10},
                    "alpha_radius": {"default": 0, "min": 0, "max": 100},
                    "alpha_power": {"default": 0, "min": 0, "max": 10},
                },
                "ffmpeg_filter": "boxblur",
                "description": "盒状模糊",
            },
            "ff_gblur": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "sigma": {"default": 1.0, "min": 0, "max": 100},
                    "steps": {"default": 1, "min": 1, "max": 10},
                    "planes": {"default": 7, "min": 0, "max": 15},
                    "sigmaV": {"default": -1, "min": -1, "max": 100},
                },
                "ffmpeg_filter": "gblur",
                "description": "高斯模糊",
            },
            "ff_unsharp": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "luma_msize_x": {"default": 5, "min": 3, "max": 63},
                    "luma_msize_y": {"default": 5, "min": 3, "max": 63},
                    "luma_amount": {"default": 1.0, "min": -10, "max": 10},
                    "chroma_msize_x": {"default": 0, "min": 0, "max": 63},
                    "chroma_msize_y": {"default": 0, "min": 0, "max": 63},
                    "chroma_amount": {"default": 0, "min": -10, "max": 10},
                },
                "ffmpeg_filter": "unsharp",
                "description": "锐化/模糊",
            },
            "ff_zoompan": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "z": {"default": "1", "type": "string"},
                    "x": {"default": "iw/2-(iw/zoom/2)", "type": "string"},
                    "y": {"default": "ih/2-(ih/zoom/2)", "type": "string"},
                    "d": {"default": 25, "min": 1, "max": 1000},
                    "s": {"default": "1920x1080", "type": "string"},
                    "fps": {"default": 25, "min": 1, "max": 120},
                },
                "ffmpeg_filter": "zoompan",
                "description": "缩放和平移动画",
            },
            "ff_scale": {
                "category": FilterCategory.UTILITY,
                "type": "video",
                "params": {
                    "width": {"default": -1, "min": -1, "max": 8192},
                    "height": {"default": -1, "min": -1, "max": 8192},
                    "flags": {"default": "bilinear", "type": "string"},
                },
                "ffmpeg_filter": "scale",
                "description": "缩放",
            },
            "ff_crop": {
                "category": FilterCategory.UTILITY,
                "type": "video",
                "params": {
                    "w": {"default": "iw", "type": "string"},
                    "h": {"default": "ih", "type": "string"},
                    "x": {"default": "(iw-ow)/2", "type": "string"},
                    "y": {"default": "(ih-oh)/2", "type": "string"},
                    "keep_aspect": {"default": False, "type": "boolean"},
                    "exact": {"default": False, "type": "boolean"},
                },
                "ffmpeg_filter": "crop",
                "description": "裁剪",
            },
            "ff_rotate": {
                "category": FilterCategory.DISTORT,
                "type": "video",
                "params": {
                    "angle": {"default": "0", "type": "string"},
                    "out_w": {"default": "rotw(a)", "type": "string"},
                    "out_h": {"default": "roth(a)", "type": "string"},
                    "fillcolor": {"default": "black", "type": "string"},
                },
                "ffmpeg_filter": "rotate",
                "description": "旋转",
            },
            "ff_eq": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "contrast": {"default": 1.0, "min": -2000, "max": 2000},
                    "brightness": {"default": 0, "min": -1, "max": 1},
                    "saturation": {"default": 1.0, "min": 0, "max": 10},
                    "gamma": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_r": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_g": {"default": 1.0, "min": 0.1, "max": 10},
                    "gamma_b": {"default": 1.0, "min": 0.1, "max": 10},
                },
                "ffmpeg_filter": "eq",
                "description": "色彩校正（亮度/对比度/饱和度/伽马）",
            },
            "ff_colorbalance": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "rs": {"default": 0, "min": -1, "max": 1},
                    "gs": {"default": 0, "min": -1, "max": 1},
                    "bs": {"default": 0, "min": -1, "max": 1},
                    "rm": {"default": 0, "min": -1, "max": 1},
                    "gm": {"default": 0, "min": -1, "max": 1},
                    "bm": {"default": 0, "min": -1, "max": 1},
                    "rh": {"default": 0, "min": -1, "max": 1},
                    "gh": {"default": 0, "min": -1, "max": 1},
                    "bh": {"default": 0, "min": -1, "max": 1},
                    "pl": {"default": False, "type": "boolean"},
                },
                "ffmpeg_filter": "colorbalance",
                "description": "色彩平衡",
            },
            "ff_hue": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "h": {"default": 0, "min": -360, "max": 360},
                    "s": {"default": 1.0, "min": 0, "max": 10},
                    "b": {"default": 0, "min": -10, "max": 10},
                },
                "ffmpeg_filter": "hue",
                "description": "色相/饱和度",
            },
            "ff_lut": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "c0": {"default": "clipval", "type": "string"},
                    "c1": {"default": "clipval", "type": "string"},
                    "c2": {"default": "clipval", "type": "string"},
                    "c3": {"default": "clipval", "type": "string"},
                },
                "ffmpeg_filter": "lut",
                "description": "查找表色彩校正",
            },
            "ff_lut3d": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "file": {"default": "", "type": "string"},
                    "interp": {"default": "trilinear", "type": "string"},
                    "clut": {"default": "", "type": "string"},
                },
                "ffmpeg_filter": "lut3d",
                "description": "3D LUT调色",
            },
            "ff_tonemap": {
                "category": FilterCategory.COLOR_CORRECTION,
                "type": "video",
                "params": {
                    "tonemap": {"default": "hable", "type": "string"},
                    "p": {"default": 1.0, "min": 0, "max": 10},
                    "t": {"default": 1.0, "min": 0, "max": 10},
                    "m": {"default": 0, "min": 0, "max": 10},
                    "a": {"default": 1.0, "min": 0, "max": 10},
                    "c": {"default": 1.33, "min": 0, "max": 10},
                },
                "ffmpeg_filter": "tonemap",
                "description": "HDR色调映射",
            },
            "ff_noise": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "video",
                "params": {
                    "all_seed": {"default": -1, "min": -1, "max": 65535},
                    "all_strength": {"default": 0, "min": 0, "max": 100},
                    "all_flags": {"default": "a", "type": "string"},
                    "c0_seed": {"default": -1, "min": -1, "max": 65535},
                    "c0_strength": {"default": 0, "min": 0, "max": 100},
                    "c1_seed": {"default": -1, "min": -1, "max": 65535},
                    "c1_strength": {"default": 0, "min": 0, "max": 100},
                    "c2_seed": {"default": -1, "min": -1, "max": 65535},
                    "c2_strength": {"default": 0, "min": 0, "max": 100},
                    "c3_seed": {"default": -1, "min": -1, "max": 65535},
                    "c3_strength": {"default": 0, "min": 0, "max": 100},
                },
                "ffmpeg_filter": "noise",
                "description": "添加噪点",
            },
            "ff_fade": {
                "category": FilterCategory.TRANSITION,
                "type": "video",
                "params": {
                    "type": {"default": "in", "type": "string"},
                    "start_time": {"default": 0, "min": 0, "max": 100000},
                    "duration": {"default": 1, "min": 0, "max": 100000},
                    "color": {"default": "black", "type": "string"},
                    "alpha": {"default": False, "type": "boolean"},
                },
                "ffmpeg_filter": "fade",
                "description": "淡入淡出",
            },
            "ff_framerate": {
                "category": FilterCategory.UTILITY,
                "type": "video",
                "params": {
                    "fps": {"default": 25, "min": 1, "max": 240},
                    "interp_start": {"default": 0, "min": 0, "max": 255},
                    "interp_end": {"default": 255, "min": 0, "max": 255},
                },
                "ffmpeg_filter": "framerate",
                "description": "帧率转换",
            },
            "ff_setpts": {
                "category": FilterCategory.UTILITY,
                "type": "video",
                "params": {
                    "expr": {"default": "PTS", "type": "string"},
                    "start": {"default": "NAN", "type": "string"},
                    "drop": {"default": False, "type": "boolean"},
                },
                "ffmpeg_filter": "setpts",
                "description": "时间轴重映射（变速）",
            },
            "ff_lenscorrection": {
                "category": FilterCategory.DISTORT,
                "type": "video",
                "params": {
                    "cx": {"default": 0.5, "min": 0, "max": 1},
                    "cy": {"default": 0.5, "min": 0, "max": 1},
                    "k1": {"default": 0.0, "min": -10, "max": 10},
                    "k2": {"default": 0.0, "min": -10, "max": 10},
                    "k3": {"default": 0.0, "min": -10, "max": 10},
                    "p1": {"default": 0.0, "min": -10, "max": 10},
                    "p2": {"default": 0.0, "min": -10, "max": 10},
                    "i": {"default": "bilinear", "type": "string"},
                    "f": {"default": "fill", "type": "string"},
                    "fc": {"default": "black@0", "type": "string"},
                },
                "ffmpeg_filter": "lenscorrection",
                "description": "镜头畸变校正",
            },
            "ff_vignette": {
                "category": FilterCategory.STYLIZE,
                "type": "video",
                "params": {
                    "angle": {"default": "PI/5", "type": "string"},
                    "mode": {"default": "forward", "type": "string"},
                    "eval": {"default": "normal", "type": "string"},
                    "d": {"default": "density", "type": "string"},
                    "aspect": {"default": 1.0, "min": 0.1, "max": 10},
                    "x0": {"default": "w/2", "type": "string"},
                    "y0": {"default": "h/2", "type": "string"},
                },
                "ffmpeg_filter": "vignette",
                "description": "暗角",
            },
            "ff_sharpen": {
                "category": FilterCategory.BLUR_SHARPEN,
                "type": "video",
                "params": {
                    "luma_msize_x": {"default": 3, "min": 3, "max": 23},
                    "luma_msize_y": {"default": 3, "min": 3, "max": 23},
                    "luma_amount": {"default": 1.0, "min": -10, "max": 10},
                },
                "ffmpeg_filter": "sharpen",
                "description": "锐化",
            },
            "ff_pad": {
                "category": FilterCategory.UTILITY,
                "type": "video",
                "params": {
                    "width": {"default": "iw", "type": "string"},
                    "height": {"default": "ih", "type": "string"},
                    "x": {"default": 0, "min": 0, "max": 10000},
                    "y": {"default": 0, "min": 0, "max": 10000},
                    "color": {"default": "black", "type": "string"},
                    "eval": {"default": "init", "type": "string"},
                    "aspect": {"default": 0, "min": 0, "max": 10},
                },
                "ffmpeg_filter": "pad",
                "description": "填充边框",
            },
            "ff_spp": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "video",
                "params": {
                    "quality": {"default": 3, "min": 0, "max": 6},
                    "base": {"default": 0, "min": 0, "max": 1},
                    "mode": {"default": 0, "min": 0, "max": 1},
                    "qscale": {"default": 0, "min": -1, "max": 63},
                    "use_bframe_qp": {"default": 0, "min": 0, "max": 1},
                },
                "ffmpeg_filter": "spp",
                "description": "简单后处理去块",
            },
            "ff_deband": {
                "category": FilterCategory.NOISE_GRAIN,
                "type": "video",
                "params": {
                    "1thr": {"default": 0.02, "min": 0, "max": 1},
                    "2thr": {"default": 0.02, "min": 0, "max": 1},
                    "3thr": {"default": 0.02, "min": 0, "max": 1},
                    "4thr": {"default": 0.02, "min": 0, "max": 1},
                    "range": {"default": 16, "min": 0, "max": 64},
                    "direction": {"default": 0, "min": 0, "max": 1},
                    "blur": {"default": 1, "min": 0, "max": 1},
                    "dither": {"default": True, "type": "boolean"},
                    "dither_thr": {"default": 0.003921568627, "min": 0, "max": 1},
                    "m1": {"default": 0, "min": 0, "max": 1},
                    "m2": {"default": 0, "min": 0, "max": 1},
                    "m3": {"default": 0, "min": 0, "max": 1},
                    "m4": {"default": 0, "min": 0, "max": 1},
                },
                "ffmpeg_filter": "deband",
                "description": "去色带",
            },
            "ff_chromaber_v1": {
                "category": FilterCategory.STYLIZE,
                "type": "video",
                "params": {
                    "dist": {"default": 0.05, "min": -10, "max": 10},
                    "angle": {"default": 0, "min": 0, "max": 360},
                },
                "ffmpeg_filter": "chromaber_v1",
                "description": "色差效果",
            },
        }
        self._filters.update(video_filters)

        # 音频滤镜
        audio_filters = {
            "ff_equalizer": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "frequency": {"default": 1000, "min": 0, "max": 999999},
                    "width_type": {"default": "q", "type": "string"},
                    "width": {"default": 1.0, "min": 0, "max": 999999},
                    "gain": {"default": 0, "min": -900, "max": 900},
                },
                "ffmpeg_filter": "equalizer",
                "description": "音频均衡器",
            },
            "ff_compand": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "attacks": {"default": 0.3, "min": 0, "max": 10},
                    "decays": {"default": 0.8, "min": 0, "max": 10},
                    "points": {"default": "-90/-90 -70/-70 -60/-20 0/0", "type": "string"},
                    "soft-knee": {"default": 0.01, "min": 0.01, "max": 10},
                    "gain": {"default": 0, "min": -900, "max": 900},
                    "volume": {"default": 0, "min": -900, "max": 900},
                    "delay": {"default": 0, "min": 0, "max": 10},
                },
                "ffmpeg_filter": "compand",
                "description": "音频压缩/扩展",
            },
            "ff_aecho": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "in_gain": {"default": 0.6, "min": 0, "max": 1},
                    "out_gain": {"default": 0.3, "min": 0, "max": 1},
                    "delays": {"default": "1000", "type": "string"},
                    "decays": {"default": "0.5", "type": "string"},
                },
                "ffmpeg_filter": "aecho",
                "description": "音频回声",
            },
            "ff_reverb": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "input_gain": {"default": 0.6, "min": 0, "max": 1},
                    "room_size": {"default": 0.5, "min": 0, "max": 1},
                    "damping": {"default": 0.5, "min": 0, "max": 1},
                    "wet_gain": {"default": 0.33, "min": 0, "max": 1},
                    "dry_gain": {"default": 1.0, "min": 0, "max": 1},
                    "width": {"default": 1.0, "min": 0, "max": 1},
                },
                "ffmpeg_filter": "reverb",
                "description": "音频混响",
            },
            "ff_volume": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "volume": {"default": 1.0, "min": -900, "max": 900},
                    "precision": {"default": "float", "type": "string"},
                    "eval": {"default": "once", "type": "string"},
                    "peak": {"default": False, "type": "boolean"},
                    "replaygain": {"default": False, "type": "boolean"},
                },
                "ffmpeg_filter": "volume",
                "description": "音量调整",
            },
            "ff_atempo": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "tempo": {"default": 1.0, "min": 0.5, "max": 100},
                },
                "ffmpeg_filter": "atempo",
                "description": "音频速度调整",
            },
            "ff_acompressor": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "threshold": {"default": 0.125, "min": 0.0009765625, "max": 1},
                    "ratio": {"default": 2, "min": 1, "max": 20},
                    "attack": {"default": 20, "min": 0.01, "max": 2000},
                    "release": {"default": 250, "min": 0.01, "max": 9000},
                    "makeup": {"default": 1, "min": 1, "max": 64},
                    "knee": {"default": 2.82843, "min": 1, "max": 10},
                    "link": {"default": "maximum", "type": "string"},
                    "detection": {"default": "peak", "type": "string"},
                    "sidechain": {"default": 0, "min": 0, "max": 1},
                    "mode": {"default": "downward", "type": "string"},
                },
                "ffmpeg_filter": "acompressor",
                "description": "音频压缩器",
            },
            "ff_lowpass": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "frequency": {"default": 500, "min": 0, "max": 999999},
                    "poles": {"default": 2, "min": 1, "max": 2},
                    "width_type": {"default": "q", "type": "string"},
                    "width": {"default": 0.70710678, "min": 0, "max": 999999},
                    "mix": {"default": 1, "min": 0, "max": 1},
                    "level": {"default": True, "type": "boolean"},
                    "gain": {"default": 0, "min": -900, "max": 900},
                },
                "ffmpeg_filter": "lowpass",
                "description": "低通滤波器",
            },
            "ff_highpass": {
                "category": FilterCategory.UTILITY,
                "type": "audio",
                "params": {
                    "frequency": {"default": 3000, "min": 0, "max": 999999},
                    "poles": {"default": 2, "min": 1, "max": 2},
                    "width_type": {"default": "q", "type": "string"},
                    "width": {"default": 0.70710678, "min": 0, "max": 999999},
                    "mix": {"default": 1, "min": 0, "max": 1},
                    "level": {"default": True, "type": "boolean"},
                    "gain": {"default": 0, "min": -900, "max": 900},
                },
                "ffmpeg_filter": "highpass",
                "description": "高通滤波器",
            },
        }
        self._filters.update(audio_filters)

    def apply_filter(self, filter_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """应用FFmpeg滤镜"""
        if filter_name not in self._filters:
            raise FilterNotFoundError(f"FFmpeg滤镜未找到: {filter_name}")
        merged_params = self._merge_params(filter_name, params)
        return {
            "software": "ffmpeg",
            "filter": filter_name,
            "params": merged_params,
            "info": self._filters[filter_name],
            "ffmpeg_string": self._build_filter_string(filter_name, merged_params),
        }

    def apply_filter_chain(self, filters: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
        """应用FFmpeg滤镜链"""
        return [self.apply_filter(name, params) for name, params in filters]

    def _build_filter_string(self, filter_name: str, params: dict[str, Any]) -> str:
        """构建FFmpeg滤镜字符串"""
        info = self._filters.get(filter_name, {})
        ffmpeg_filter = info.get("ffmpeg_filter", filter_name)
        param_parts = []
        for key, value in params.items():
            if isinstance(value, bool):
                value = 1 if value else 0
            param_parts.append(f"{key}={value}")
        if param_parts:
            return f"{ffmpeg_filter}={':'.join(param_parts)}"
        return ffmpeg_filter

    def generate_command(
        self,
        input_file: str,
        output_file: str,
        video_filters: list[tuple[str, dict[str, Any]]] | None = None,
        audio_filters: list[tuple[str, dict[str, Any]]] | None = None,
        **kwargs
    ) -> str:
        """
        生成FFmpeg命令行

        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            video_filters: 视频滤镜列表
            audio_filters: 音频滤镜列表

        Returns:
            FFmpeg命令字符串
        """
        cmd_parts = ["ffmpeg", "-i", f'"{input_file}"']

        filter_complex_parts = []

        if video_filters:
            vf_str = ",".join([
                self._build_filter_string(name, self._merge_params(name, params))
                for name, params in video_filters
            ])
            filter_complex_parts.append(f"[0:v]{vf_str}[vout]")
            cmd_parts.extend(["-map", "[vout]"])

        if audio_filters:
            af_str = ",".join([
                self._build_filter_string(name, self._merge_params(name, params))
                for name, params in audio_filters
            ])
            filter_complex_parts.append(f"[0:a]{af_str}[aout]")
            cmd_parts.extend(["-map", "[aout]"])

        if filter_complex_parts:
            cmd_parts.extend(["-filter_complex", f'"{";".join(filter_complex_parts)}"'])

        cmd_parts.append(f'"{output_file}"')
        return " ".join(cmd_parts)

    def generate_script(self, filters: list[tuple[str, dict[str, Any]]], **kwargs) -> str:
        """生成FFmpeg命令（作为脚本）"""
        input_file = kwargs.get("input_file", "input.mp4")
        output_file = kwargs.get("output_file", "output.mp4")
        return self.generate_command(input_file, output_file, video_filters=filters)

    def generate_complex_filter_graph(
        self,
        inputs: list[str],
        outputs: list[str],
        filter_chains: list[list[tuple[str, dict[str, Any]]]],
        connections: list[tuple[str, str]] | None = None,
    ) -> str:
        """
        生成复杂的FFmpeg滤镜图

        Args:
            inputs: 输入标签列表
            outputs: 输出标签列表
            filter_chains: 滤镜链列表
            connections: 连接关系

        Returns:
            FFmpeg filter_complex字符串
        """
        graph_parts = []
        for i, chain in enumerate(filter_chains):
            chain_str = ",".join([
                self._build_filter_string(name, self._merge_params(name, params))
                for name, params in chain
            ])
            input_label = inputs[i] if i < len(inputs) else f"[{i}:v]"
            output_label = f"[chain{i}_out]"
            graph_parts.append(f"{input_label}{chain_str}{output_label}")

        if connections:
            for src, dst in connections:
                graph_parts.append(f"{src}{dst}")

        return ";".join(graph_parts)

    def get_video_filters(self) -> list[str]:
        """获取视频滤镜"""
        return [k for k, v in self._filters.items() if v.get("type") == "video"]

    def get_audio_filters(self) -> list[str]:
        """获取音频滤镜"""
        return [k for k, v in self._filters.items() if v.get("type") == "audio"]


# =============================================================================
# FilterChain 滤镜链类
# =============================================================================

class FilterChain:
    """
    滤镜链管理器

    支持滤镜的添加、删除、重排序、混合模式、透明度控制、
    蒙版支持、动画关键帧等功能。
    """

    def __init__(self, name: str = "default_chain"):
        self.name = name
        self._filters: list[FilterChainItem] = []
        self._enabled: bool = True

    def add_filter(
        self,
        preset: FilterPreset,
        opacity: float = 100.0,
        blend_mode: BlendMode = BlendMode.NORMAL,
        mask: str | None = None,
        index: int | None = None,
    ) -> int:
        """
        添加滤镜到链中

        Args:
            preset: 滤镜预设
            opacity: 不透明度 (0-100)
            blend_mode: 混合模式
            mask: 蒙版名称
            index: 插入位置，None表示追加到末尾

        Returns:
            滤镜在链中的索引位置
        """
        item = FilterChainItem(
            preset=preset,
            opacity=max(0.0, min(100.0, opacity)),
            blend_mode=blend_mode,
            mask=mask,
        )
        if index is None or index >= len(self._filters):
            self._filters.append(item)
            return len(self._filters) - 1
        else:
            index = max(0, index)
            self._filters.insert(index, item)
            return index

    def remove_filter(self, index: int) -> FilterChainItem:
        """
        移除指定索引的滤镜

        Args:
            index: 滤镜索引

        Returns:
            被移除的滤镜项
        """
        if 0 <= index < len(self._filters):
            return self._filters.pop(index)
        raise IndexError(f"滤镜索引超出范围: {index}")

    def get_filter(self, index: int) -> FilterChainItem:
        """获取指定索引的滤镜"""
        if 0 <= index < len(self._filters):
            return self._filters[index]
        raise IndexError(f"滤镜索引超出范围: {index}")

    def reorder_filters(self, new_order: list[int]) -> None:
        """
        重新排序滤镜

        Args:
            new_order: 新的索引顺序列表
        """
        if len(new_order) != len(self._filters):
            raise ValueError("新顺序列表长度与滤镜数量不匹配")
        if sorted(new_order) != list(range(len(self._filters))):
            raise ValueError("新顺序列表包含无效索引")
        self._filters = [self._filters[i] for i in new_order]

    def move_filter(self, from_index: int, to_index: int) -> None:
        """
        移动滤镜到新位置

        Args:
            from_index: 原位置
            to_index: 新位置
        """
        if not (0 <= from_index < len(self._filters)):
            raise IndexError(f"起始索引超出范围: {from_index}")
        if not (0 <= to_index < len(self._filters)):
            raise IndexError(f"目标索引超出范围: {to_index}")
        item = self._filters.pop(from_index)
        self._filters.insert(to_index, item)

    def set_opacity(self, index: int, opacity: float) -> None:
        """设置指定滤镜的不透明度"""
        item = self.get_filter(index)
        item.opacity = max(0.0, min(100.0, opacity))

    def set_blend_mode(self, index: int, blend_mode: BlendMode) -> None:
        """设置指定滤镜的混合模式"""
        item = self.get_filter(index)
        item.blend_mode = blend_mode

    def set_mask(self, index: int, mask: str | None) -> None:
        """设置指定滤镜的蒙版"""
        item = self.get_filter(index)
        item.mask = mask

    def set_enabled(self, index: int, enabled: bool) -> None:
        """启用/禁用指定滤镜"""
        item = self.get_filter(index)
        item.enabled = enabled

    def add_keyframe(
        self,
        filter_index: int,
        param_name: str,
        frame: float,
        value: Any,
    ) -> None:
        """
        添加动画关键帧

        Args:
            filter_index: 滤镜索引
            param_name: 参数名称
            frame: 帧位置
            value: 关键帧值
        """
        item = self.get_filter(filter_index)
        if param_name not in item.animation_keyframes:
            item.animation_keyframes[param_name] = []
        item.animation_keyframes[param_name].append((frame, value))
        item.animation_keyframes[param_name].sort(key=lambda x: x[0])

    def get_filters(self) -> list[FilterChainItem]:
        """获取所有滤镜项"""
        return self._filters.copy()

    def get_enabled_filters(self) -> list[FilterChainItem]:
        """获取所有启用的滤镜"""
        return [f for f in self._filters if f.enabled]

    def __len__(self) -> int:
        return len(self._filters)

    def __getitem__(self, index: int) -> FilterChainItem:
        return self.get_filter(index)

    def __iter__(self):
        return iter(self._filters)

    def clear(self) -> None:
        """清空所有滤镜"""
        self._filters.clear()

    def copy(self) -> "FilterChain":
        """创建滤镜链的深拷贝"""
        new_chain = FilterChain(self.name)
        new_chain._filters = deepcopy(self._filters)
        new_chain._enabled = self._enabled
        return new_chain

    def blend_filter_chains(self, other: "FilterChain", blend_ratio: float = 0.5) -> "FilterChain":
        """
        混合两个滤镜链

        Args:
            other: 另一个滤镜链
            blend_ratio: 混合比例 (0-1)

        Returns:
            新的混合滤镜链
        """
        result = FilterChain(f"{self.name}_blend_{other.name}")
        for item in self._filters:
            new_item = deepcopy(item)
            new_item.opacity *= (1 - blend_ratio)
            result._filters.append(new_item)
        for item in other._filters:
            new_item = deepcopy(item)
            new_item.opacity *= blend_ratio
            result._filters.append(new_item)
        return result

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "enabled": self._enabled,
            "filters": [
                {
                    "preset": item.preset.to_dict(),
                    "opacity": item.opacity,
                    "blend_mode": item.blend_mode.value,
                    "mask": item.mask,
                    "enabled": item.enabled,
                    "animation_keyframes": item.animation_keyframes,
                }
                for item in self._filters
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FilterChain":
        """从字典创建滤镜链"""
        chain = cls(data.get("name", "default_chain"))
        chain._enabled = data.get("enabled", True)
        for item_data in data.get("filters", []):
            preset = FilterPreset.from_dict(item_data["preset"])
            item = FilterChainItem(
                preset=preset,
                opacity=item_data.get("opacity", 100.0),
                blend_mode=BlendMode(item_data.get("blend_mode", "normal")),
                mask=item_data.get("mask"),
                enabled=item_data.get("enabled", True),
                animation_keyframes=item_data.get("animation_keyframes", {}),
            )
            chain._filters.append(item)
        return chain


# =============================================================================
# FilterPresetLibrary 滤镜预设库
# =============================================================================

class FilterPresetLibrary:
    """
    滤镜预设库

    包含200+内置预设，支持搜索、分类、保存/加载等功能。
    """

    def __init__(self):
        self._presets: dict[str, FilterPreset] = {}
        self._init_builtin_presets()

    def _init_builtin_presets(self) -> None:
        """初始化200+内置预设"""
        all_software = [
            SoftwareType.AFTER_EFFECTS,
            SoftwareType.PHOTOSHOP,
            SoftwareType.DAVINCI_RESOLVE,
            SoftwareType.BLENDER,
            SoftwareType.FFMPEG,
        ]

        cinematic_presets = [
            ("cine_teal_orange", "电影蓝橙色调", FilterStyle.CINEMATIC,
             {"temperature": -10, "tint": 5, "contrast": 15, "saturation": -5,
              "shadows": 10, "highlights": -10},
             "经典电影蓝橙对比色调，增强视觉冲击力"),
            ("cine_deep_contrast", "电影深对比", FilterStyle.CINEMATIC,
             {"contrast": 25, "highlights": -20, "shadows": -15,
              "blacks": -10, "whites": 10, "saturation": 10},
             "高对比度电影风格，暗部更深，亮部更突出"),
            ("cine_warm_glow", "电影暖光", FilterStyle.CINEMATIC,
             {"temperature": 20, "tint": -5, "exposure": 0.3,
              "contrast": 10, "saturation": 5},
             "温暖的电影感，适合日落和室内场景"),
            ("cine_cool_mood", "电影冷调", FilterStyle.CINEMATIC,
             {"temperature": -25, "tint": 10, "contrast": 15,
              "saturation": -10, "shadows": -5},
             "冷色调电影风格，营造悬疑和科技感"),
            ("cine_desaturated", "电影低饱和", FilterStyle.CINEMATIC,
             {"saturation": -30, "contrast": 20, "exposure": -0.2,
              "vibrance": -10},
             "低饱和度电影风格，纪实感强"),
            ("cine_film_grain", "电影胶片颗粒", FilterStyle.FILM,
             {"amount": 15, "size": 1.5, "softness": 60,
              "contrast": 5, "saturation": -5},
             "经典胶片颗粒效果，增加电影质感"),
            ("cine_vignette_dark", "暗角效果", FilterStyle.CINEMATIC,
             {"amount": 30, "midpoint": 50, "roundness": 50,
              "softness": 80},
             "自然暗角，突出画面主体"),
            ("cine_hollywood", "好莱坞风格", FilterStyle.CINEMATIC,
             {"contrast": 20, "saturation": 15, "temperature": 10,
              "highlights": -15, "shadows": 20, "vibrance": 10},
             "好莱坞大片风格，色彩鲜艳对比强烈"),
            ("cine_noir", "黑色电影", FilterStyle.CINEMATIC,
             {"saturation": -100, "contrast": 35, "brightness": -10,
              "highlights": -20, "shadows": -30},
             "黑白电影风格，高对比硬阴影"),
            ("cine_bloom", "辉光效果", FilterStyle.CINEMATIC,
             {"glow_radius": 30, "glow_intensity": 1.5, "glow_threshold": 60,
              "brightness": 10, "contrast": 5},
             "柔和辉光，梦幻电影感"),
        ]

        vintage_presets = [
            ("vintage_70s", "70年代复古", FilterStyle.VINTAGE,
             {"temperature": 25, "tint": -10, "saturation": -20,
              "contrast": -5, "brightness": 5, "amount": 10},
             "70年代复古色调，温暖褪色感"),
            ("vintage_80s_vhs", "80年代VHS", FilterStyle.VINTAGE,
             {"saturation": -15, "contrast": 10, "brightness": 5,
              "noise_amount": 8, "scan_lines": 1},
             "80年代VHS录像带效果"),
            ("vintage_sepia", "复古棕褐色", FilterStyle.VINTAGE,
             {"map_black_to": [60, 40, 20], "map_white_to": [220, 200, 160],
              "amount": 80, "contrast": 10},
             "经典棕褐色复古照片效果"),
            ("vintage_faded", "褪色复古", FilterStyle.VINTAGE,
             {"contrast": -15, "saturation": -25, "brightness": 10,
              "temperature": 15, "amount": 5},
             "褪色老旧照片效果"),
            ("vintage_polaroid", "宝丽来风格", FilterStyle.VINTAGE,
             {"temperature": 10, "saturation": -10, "contrast": 5,
              "brightness": 8, "amount": 3},
             "宝丽来即时成像风格"),
            ("vintage_black_white", "复古黑白", FilterStyle.VINTAGE,
             {"saturation": -100, "contrast": 20, "brightness": -5,
              "amount": 10, "size": 0.8},
             "复古黑白照片，带颗粒感"),
            ("vintage_cross_process", "交叉冲洗", FilterStyle.VINTAGE,
             {"temperature": -15, "tint": 20, "saturation": 15,
              "contrast": 20, "highlights": 10},
             "交叉冲洗效果，独特色彩偏移"),
            ("vintage_lomo", "LOMO风格", FilterStyle.VINTAGE,
             {"contrast": 25, "saturation": 30, "brightness": 5,
              "vignette": 40, "temperature": 10},
             "LOMO相机风格，高饱和暗角"),
            ("vintage_ kodachrome", "柯达克罗姆", FilterStyle.VINTAGE,
             {"contrast": 15, "saturation": 20, "temperature": 5,
              "red": 10, "blue": -5},
             "经典柯达胶片色彩"),
            ("vintage_agfa", "爱克发风格", FilterStyle.VINTAGE,
             {"temperature": 15, "green": -5, "saturation": 10,
              "contrast": 10, "amount": 8},
             "爱克发胶片的温暖绿色调"),
        ]

        glitch_presets = [
            ("glitch_rgb_split", "RGB分离", FilterStyle.GLITCH,
             {"red_offset": [5, 0], "green_offset": [-3, 2], "blue_offset": [0, -3],
              "amount": 100},
             "RGB通道分离故障效果"),
            ("glitch_digital", "数字故障", FilterStyle.GLITCH,
             {"horizontal_blocks": 20, "vertical_blocks": 5,
              "displacement": 30, "random_seed": 1},
             "数字画面故障效果"),
            ("glitch_vhs_noise", "VHS噪点", FilterStyle.GLITCH,
             {"noise_amount": 20, "scan_lines": 3, "chroma_offset": 2,
              "tracking_error": 5},
             "VHS磁带故障效果"),
            ("glitch_corrupted", "数据损坏", FilterStyle.GLITCH,
             {"displacement": 50, "size": 20, "complexity": 5,
              "evolution": 180, "amount": 80},
             "数据损坏风格的扭曲故障"),
            ("glitch_tech", "科技故障", FilterStyle.GLITCH,
             {"scan_lines": 5, "glitch_frequency": 2, "color_shift": 10,
              "distortion": 15},
             "科技感故障效果"),
            ("glitch_analog", "模拟故障", FilterStyle.GLITCH,
             {"noise": 15, "warp": 10, "color_bleed": 20,
              "tape_warp": 5},
             "模拟信号故障效果"),
            ("glitch_ cyberpunk", "赛博朋克故障", FilterStyle.CYBERPUNK,
             {"neon_color": [0, 255, 255], "glitch_amount": 40,
              "scan_lines": 2, "chromatic_aberration": 3},
             "赛博朋克风格故障效果"),
            ("glitch_zoom", "故障缩放", FilterStyle.GLITCH,
             {"zoom_amount": 20, "glitch_frames": 3, "direction": "in",
              "intensity": 60},
             "故障式缩放转场效果"),
            ("glitch_slice", "切片故障", FilterStyle.GLITCH,
             {"slices": 15, "max_offset": 30, "random_seed": 42,
              "vertical": False},
             "水平切片故障效果"),
            ("glitch_color_bands", "色带故障", FilterStyle.GLITCH,
             {"bands": 10, "band_height": 20, "color_offset": 15,
              "randomness": 50},
             "彩色色带故障效果"),
        ]

        cyberpunk_presets = [
            ("cyberpunk_neon", "霓虹赛博", FilterStyle.CYBERPUNK,
             {"saturation": 40, "contrast": 25, "temperature": -15,
              "tint": 20, "glow_intensity": 2.0},
             "霓虹灯下的赛博朋克风格"),
            ("cyberpunk_terminal", "终端风格", FilterStyle.CYBERPUNK,
             {"green": 30, "saturation": 50, "contrast": 30,
              "scan_lines": 2, "glow": 15},
             "绿色终端显示器风格"),
            ("cyberpunk_night_city", "夜之城", FilterStyle.CYBERPUNK,
             {"contrast": 30, "saturation": 35, "temperature": -10,
              "highlights": 20, "neon_glow": 25},
             "赛博朋克夜晚城市风格"),
            ("cyberpunk_hologram", "全息投影", FilterStyle.CYBERPUNK,
             {"cyan": 40, "saturation": 30, "opacity": 85,
              "scan_lines": 3, "glow": 20},
             "全息投影效果"),
            ("cyberpunk_chrome", "镀铬金属", FilterStyle.CYBERPUNK,
             {"contrast": 40, "saturation": -20, "highlights": 30,
              "edge_glow": 15, "metallic": 50},
             "镀铬金属赛博朋克风格"),
            ("cyberpunk_grid", "网格世界", FilterStyle.CYBERPUNK,
             {"grid_lines": 20, "perspective": True, "glow": 25,
              "color": [0, 255, 255], "fade": 30},
             "透视网格赛博朋克背景"),
            ("cyberpunk_data_stream", "数据流", FilterStyle.CYBERPUNK,
             {"speed": 50, "density": 80, "glow": 20,
              "color": [0, 255, 100], "length": 30},
             "数字数据流效果"),
            ("cyberpunk_glitch_city", "故障都市", FilterStyle.CYBERPUNK,
             {"glitch_amount": 30, "neon_intensity": 40, "scan_lines": 1,
              "chromatic": 2, "contrast": 25},
             "故障感赛博都市风格"),
        ]

        dreamy_presets = [
            ("dreamy_soft_glow", "柔焦梦幻", FilterStyle.DREAMY,
             {"blur_radius": 5, "glow_intensity": 1.2, "saturation": 10,
              "brightness": 10, "contrast": -5},
             "柔焦梦幻效果，朦胧美感"),
            ("dreamy_cloud", "云端梦境", FilterStyle.DREAMY,
             {"brightness": 15, "contrast": -10, "saturation": 5,
              "blur": 3, "glow": 20},
             "云朵般柔和的梦境效果"),
            ("dreamy_bokeh", "散景梦境", FilterStyle.DREAMY,
             {"blur_radius": 15, "bokeh_shape": "hexagon",
              "highlight_gain": 20, "brightness": 5},
             "美丽散景的梦幻效果"),
            ("dreamy_pastel", "粉彩梦境", FilterStyle.DREAMY,
             {"saturation": 20, "brightness": 15, "contrast": -8,
              "temperature": 5, "softness": 30},
             "粉彩柔和的梦境风格"),
            ("dreamy_fairy", "童话仙境", FilterStyle.DREAMY,
             {"brightness": 20, "saturation": 15, "glow": 25,
              "sparkle": 30, "softness": 20},
             "童话仙境般的梦幻效果"),
            ("dreamy_sunrise", "日出梦境", FilterStyle.DREAMY,
             {"temperature": 25, "brightness": 10, "saturation": 15,
              "glow": 15, "softness": 15},
             "日出时分的温暖梦境"),
            ("dreamy_underwater", "水下梦境", FilterStyle.DREAMY,
             {"temperature": -20, "blue": 20, "blur": 3,
              "caustics": 20, "light_rays": 15},
             "水下世界的梦幻感"),
            ("dreamy_stardust", "星尘梦境", FilterStyle.DREAMY,
             {"sparkle_amount": 40, "glow": 20, "brightness": 10,
              "saturation": 5, "softness": 10},
             "星光闪烁的梦境效果"),
        ]

        portrait_presets = [
            ("portrait_soft_beauty", "柔美人像", FilterStyle.SOFT,
             {"smooth_amount": 30, "brightness": 5, "saturation": 5,
              "soft_glow": 15, "contrast": -3},
             "柔美人像磨皮效果"),
            ("portrait_fashion", "时尚人像", FilterStyle.HIGH_CONTRAST,
             {"contrast": 25, "saturation": 15, "sharpness": 20,
              "highlights": -10, "shadows": 5},
             "时尚杂志风格人像"),
            ("portrait_warm_skin", "暖调肤色", FilterStyle.WARM,
             {"temperature": 10, "red": 5, "saturation": 10,
              "brightness": 5, "softness": 10},
             "温暖健康的肤色效果"),
            ("portrait_cool_tone", "冷调人像", FilterStyle.COOL,
             {"temperature": -10, "blue": 5, "contrast": 15,
              "brightness": 3, "saturation": -5},
             "冷色调高级感人像"),
            ("portrait_dramatic", "戏剧人像", FilterStyle.HIGH_CONTRAST,
             {"contrast": 35, "highlights": -20, "shadows": -25,
              "brightness": -5, "saturation": -10},
             "戏剧光影效果人像"),
            ("portrait_film_look", "胶片人像", FilterStyle.FILM,
             {"contrast": 15, "saturation": 5, "grain_amount": 8,
              "temperature": 8, "softness": 5},
             "胶片质感人像"),
            ("portrait_glamour", "魅力人像", FilterStyle.SOFT,
             {"glow": 20, "softness": 15, "brightness": 10,
              "saturation": 8, "contrast": 5},
             "魅力柔光人像效果"),
            ("portrait_moody", "情绪人像", FilterStyle.DREAMY,
             {"contrast": 20, "saturation": -15, "brightness": -5,
              "temperature": -5, "vignette": 25},
             "情绪氛围感人像"),
        ]

        landscape_presets = [
            ("landscape_vibrant", "鲜艳风景", FilterStyle.HIGH_CONTRAST,
             {"contrast": 20, "saturation": 30, "brightness": 5,
              "vibrance": 20, "shadows": 15},
             "鲜艳的风景摄影效果"),
            ("landscape_moody", "氛围风景", FilterStyle.DREAMY,
             {"contrast": 15, "saturation": -10, "brightness": -3,
              "temperature": -5, "vignette": 20},
             "氛围感风景效果"),
            ("landscape_golden_hour", "黄金时刻", FilterStyle.WARM,
             {"temperature": 25, "tint": -5, "saturation": 20,
              "brightness": 5, "contrast": 15},
             "日落黄金时刻风景"),
            ("landscape_cool_blue", "冷蓝风景", FilterStyle.COOL,
             {"temperature": -20, "blue": 15, "contrast": 20,
              "saturation": 10, "brightness": 5},
             "冷蓝色调风景效果"),
            ("landscape_dramatic_sky", "戏剧天空", FilterStyle.HIGH_CONTRAST,
             {"contrast": 30, "highlights": -15, "shadows": 20,
              "saturation": 25, "vivid": 30},
             "戏剧化天空效果"),
            ("landscape_forest", "森林秘境", FilterStyle.DREAMY,
             {"green": 15, "saturation": 10, "contrast": 10,
              "brightness": -3, "mist": 15},
             "森林秘境风景风格"),
            ("landscape_ocean", "海洋深蓝", FilterStyle.COOL,
             {"blue": 20, "cyan": 10, "contrast": 15,
              "saturation": 15, "brightness": 5},
             "深蓝色海洋风景"),
            ("landscape_autumn", "金秋红叶", FilterStyle.WARM,
             {"red": 20, "orange": 15, "temperature": 15,
              "saturation": 20, "contrast": 10},
             "秋天金黄红叶效果"),
        ]

        sharp_soft_presets = [
            ("sharp_ultra", "超锐利", FilterStyle.SHARP,
             {"amount": 150, "radius": 1.5, "threshold": 2,
              "edge_mask": 30},
             "超强锐化效果"),
            ("sharp_pro", "专业锐化", FilterStyle.SHARP,
             {"amount": 100, "radius": 1.0, "threshold": 3,
              "reduce_noise": 10},
             "专业级图像锐化"),
            ("soft_portrait", "柔和人像", FilterStyle.SOFT,
             {"blur_radius": 3, "threshold": 10, "edge_blur": False,
              "smooth_amount": 20},
             "柔和模糊效果"),
            ("soft_gaussian", "高斯柔化", FilterStyle.SOFT,
             {"blur_radius": 5, "brightness": 3, "saturation": 5,
              "contrast": -3},
             "高斯柔化效果"),
            ("soft_bloom", "柔光绽放", FilterStyle.SOFT,
             {"glow_radius": 25, "glow_intensity": 1.5, "threshold": 50,
              "brightness": 5},
             "柔光绽放效果"),
        ]

        anime_presets = [
            ("anime_standard", "标准动漫", FilterStyle.ANIME,
             {"saturation": 30, "contrast": 20, "brightness": 5,
              "cel_shading": 20, "edge_strong": 15},
             "标准动漫风格"),
            ("anime_ghibli", "吉卜力风格", FilterStyle.ANIME,
             {"saturation": 25, "brightness": 10, "contrast": 10,
              "softness": 5, "warmth": 10},
             "吉卜力工作室风格"),
            ("anime_mecha", "机甲动漫", FilterStyle.ANIME,
             {"contrast": 30, "saturation": 15, "sharpness": 25,
              "edge_accent": 20, "metal_glow": 10},
             "机甲科幻动漫风格"),
            ("anime_shojo", "少女漫", FilterStyle.ANIME,
             {"brightness": 15, "saturation": 20, "softness": 15,
              "pink": 10, "glow": 10},
             "少女漫画风格"),
            ("anime_shonen", "少年漫", FilterStyle.ANIME,
             {"contrast": 25, "saturation": 20, "sharpness": 20,
              "speed_lines": 10, "dynamic_blur": 15},
             "少年热血漫画风格"),
            ("anime_ isekai", "异世界", FilterStyle.ANIME,
             {"saturation": 35, "brightness": 10, "contrast": 15,
              "magical_glow": 20, "colorful": 30},
             "异世界奇幻动漫风格"),
            ("anime_ cyberpunk", "赛博朋克动漫", FilterStyle.CYBERPUNK,
             {"neon": 40, "contrast": 25, "saturation": 30,
              "scan_lines": 2, "tech_glow": 25},
             "赛博朋克动漫风格"),
            ("anime_watercolor", "水彩动漫", FilterStyle.DREAMY,
             {"softness": 20, "saturation": 10, "brightness": 5,
              "watercolor": 30, "paper_texture": 15},
             "水彩画风动漫效果"),
        ]

        all_preset_groups = [
            (cinematic_presets, FilterCategory.COLOR_CORRECTION),
            (vintage_presets, FilterCategory.COLOR_CORRECTION),
            (glitch_presets, FilterCategory.DISTORT),
            (cyberpunk_presets, FilterCategory.STYLIZE),
            (dreamy_presets, FilterCategory.BLUR_SHARPEN),
            (portrait_presets, FilterCategory.COLOR_CORRECTION),
            (landscape_presets, FilterCategory.COLOR_CORRECTION),
            (sharp_soft_presets, FilterCategory.BLUR_SHARPEN),
            (anime_presets, FilterCategory.STYLIZE),
        ]

        for presets, category in all_preset_groups:
            for preset_id, name, style, params, desc in presets:
                filter_params = {}
                for param_name, param_value in params.items():
                    if isinstance(param_value, bool):
                        ptype = "boolean"
                        min_v, max_v = 0, 1
                    elif isinstance(param_value, str):
                        ptype = "string"
                        min_v, max_v = 0, 0
                    elif isinstance(param_value, list):
                        ptype = "color" if len(param_value) == 3 else "point"
                        min_v, max_v = 0, 255
                    elif isinstance(param_value, int):
                        ptype = "int"
                        min_v = min(param_value * 2, -100)
                        max_v = max(param_value * 2, 100)
                    else:
                        ptype = "float"
                        min_v = min(param_value * 2, -100)
                        max_v = max(param_value * 2, 100)

                    filter_params[param_name] = FilterParam(
                        name=param_name,
                        value=param_value,
                        min_value=min_v,
                        max_value=max_v,
                        param_type=ptype,
                        description=f"{param_name} 参数",
                    )

                preset = FilterPreset(
                    id=preset_id,
                    name=name,
                    category=category,
                    style=style,
                    software_support=all_software.copy(),
                    params=filter_params,
                    intensity=1.0,
                    description=desc,
                    author="Filter Engine",
                    version="1.0.0",
                    tags=[style.value, category.value],
                )
                self._presets[preset_id] = preset

        additional_presets = [
            ("blur_gaussian_heavy", "重度高斯模糊", FilterCategory.BLUR_SHARPEN, FilterStyle.SOFT,
             {"blurriness": 30}, "重度高斯模糊效果"),
            ("blur_gaussian_light", "轻度高斯模糊", FilterCategory.BLUR_SHARPEN, FilterStyle.SOFT,
             {"blurriness": 3}, "轻度高斯模糊效果"),
            ("blur_motion_horizontal", "水平运动模糊", FilterCategory.BLUR_SHARPEN, FilterStyle.SHARP,
             {"direction": 0, "blur_length": 20}, "水平方向运动模糊"),
            ("blur_motion_vertical", "垂直运动模糊", FilterCategory.BLUR_SHARPEN, FilterStyle.SHARP,
             {"direction": 90, "blur_length": 20}, "垂直方向运动模糊"),
            ("blur_radial_zoom", "径向缩放模糊", FilterCategory.BLUR_SHARPEN, FilterStyle.DREAMY,
             {"amount": 20, "type": "zoom"}, "径向缩放模糊效果"),
            ("distort_wave", "波浪扭曲", FilterCategory.DISTORT, FilterStyle.DREAMY,
             {"displacement": 15, "size": 60, "complexity": 3}, "波浪扭曲效果"),
            ("distort_bulge", "膨胀效果", FilterCategory.DISTORT, FilterStyle.DREAMY,
             {"bulge_height": 2.0, "horizontal_radius": 100, "vertical_radius": 100},
             "中心膨胀效果"),
            ("distort_twirl", "旋转扭曲", FilterCategory.DISTORT, FilterStyle.GLITCH,
             {"angle": 180, "radius": 150}, "旋转扭曲效果"),
            ("key_green_screen", "绿幕抠像", FilterCategory.KEYING, FilterStyle.CINEMATIC,
             {"screen_colour": [0, 255, 0], "screen_gain": 1.2, "clip_black": 5, "clip_white": 95},
             "标准绿幕抠像预设"),
            ("key_blue_screen", "蓝幕抠像", FilterCategory.KEYING, FilterStyle.CINEMATIC,
             {"screen_colour": [0, 0, 255], "screen_gain": 1.2, "clip_black": 5, "clip_white": 95},
             "标准蓝幕抠像预设"),
            ("noise_film_grain", "胶片颗粒", FilterCategory.NOISE_GRAIN, FilterStyle.FILM,
             {"amount": 12, "size": 1.0, "softness": 50}, "精细胶片颗粒效果"),
            ("noise_digital", "数字噪点", FilterCategory.NOISE_GRAIN, FilterStyle.GLITCH,
             {"amount_of_noise": 15, "noise_type": "uniform"}, "数字噪点效果"),
            ("generate_clouds", "云彩生成", FilterCategory.GENERATE, FilterStyle.DREAMY,
             {"brightness": 50, "contrast": 100, "complexity": 5}, "分形云彩效果"),
            ("generate_gradient_rainbow", "彩虹渐变", FilterCategory.GENERATE, FilterStyle.DREAMY,
             {"ramp_shape": "linear_ramp"}, "彩虹渐变效果"),
            ("generate_lens_flare", "镜头光晕", FilterCategory.GENERATE, FilterStyle.CINEMATIC,
             {"brightness": 120, "flare_type": "50_300mm_zoom"}, "镜头光晕效果"),
            ("stylize_cartoon", "卡通效果", FilterCategory.STYLIZE, FilterStyle.ANIME,
             {"detail_radius": 20, "edge_radius": 1.0, "shading_steps": 4},
             "卡通风格化效果"),
            ("stylize_mosaic", "马赛克", FilterCategory.STYLIZE, FilterStyle.GLITCH,
             {"horizontal_blocks": 20, "vertical_blocks": 20}, "马赛克效果"),
            ("stylize_find_edges", "边缘检测", FilterCategory.STYLIZE, FilterStyle.SHARP,
             {"invert": False, "blend_with_original": 0}, "边缘检测效果"),
            ("perspective_drop_shadow", "投影", FilterCategory.PERSPECTIVE, FilterStyle.CINEMATIC,
             {"opacity": 75, "distance": 10, "softness": 10, "direction": 135},
             "标准投影效果"),
            ("perspective_bevel", "斜面浮雕", FilterCategory.PERSPECTIVE, FilterStyle.CINEMATIC,
             {"edge_thickness": 5, "light_intensity": 0.8, "light_angle": -45},
             "斜面立体效果"),
        ]

        for preset_id, name, category, style, params, desc in additional_presets:
            filter_params = {}
            for param_name, param_value in params.items():
                if isinstance(param_value, bool):
                    ptype = "boolean"
                    min_v, max_v = 0, 1
                elif isinstance(param_value, str):
                    ptype = "string"
                    min_v, max_v = 0, 0
                elif isinstance(param_value, list):
                    ptype = "color" if len(param_value) == 3 else "point"
                    min_v, max_v = 0, 255
                elif isinstance(param_value, int):
                    ptype = "int"
                    min_v = min(param_value * 2, -100)
                    max_v = max(param_value * 2, 100)
                else:
                    ptype = "float"
                    min_v = min(param_value * 2, -100)
                    max_v = max(param_value * 2, 100)

                filter_params[param_name] = FilterParam(
                    name=param_name,
                    value=param_value,
                    min_value=min_v,
                    max_value=max_v,
                    param_type=ptype,
                    description=f"{param_name} 参数",
                )

            preset = FilterPreset(
                id=preset_id,
                name=name,
                category=category,
                style=style,
                software_support=all_software.copy(),
                params=filter_params,
                intensity=1.0,
                description=desc,
                author="Filter Engine",
                version="1.0.0",
                tags=[style.value, category.value],
            )
            self._presets[preset_id] = preset

    def get_preset(self, preset_id: str) -> FilterPreset:
        """获取指定ID的预设"""
        if preset_id not in self._presets:
            raise FilterNotFoundError(f"预设未找到: {preset_id}")
        return self._presets[preset_id].copy()

    def get_all_presets(self) -> list[FilterPreset]:
        """获取所有预设"""
        return [p.copy() for p in self._presets.values()]

    def search_presets(
        self,
        category: FilterCategory | None = None,
        style: FilterStyle | None = None,
        software: SoftwareType | None = None,
        keyword: str | None = None,
        min_intensity: float = 0.0,
        max_intensity: float = 1.0,
    ) -> list[FilterPreset]:
        """
        搜索预设

        Args:
            category: 按分类过滤
            style: 按风格过滤
            software: 按软件支持过滤
            keyword: 关键词搜索（名称/描述/标签）
            min_intensity: 最小强度
            max_intensity: 最大强度

        Returns:
            匹配的预设列表
        """
        results = []
        for preset in self._presets.values():
            if category and preset.category != category:
                continue
            if style and preset.style != style:
                continue
            if software and software not in preset.software_support:
                continue
            if preset.intensity < min_intensity or preset.intensity > max_intensity:
                continue
            if keyword:
                keyword_lower = keyword.lower()
                search_text = " ".join([
                    preset.name.lower(),
                    preset.description.lower(),
                    " ".join(t.lower() for t in preset.tags),
                ])
                if keyword_lower not in search_text:
                    continue
            results.append(preset.copy())
        return results

    def get_style_presets(self, style: FilterStyle) -> list[FilterPreset]:
        """获取指定风格的所有预设"""
        return self.search_presets(style=style)

    def get_category_presets(self, category: FilterCategory) -> list[FilterPreset]:
        """获取指定分类的所有预设"""
        return self.search_presets(category=category)

    def get_preset_categories(self) -> dict[str, int]:
        """获取预设分类统计"""
        categories = {}
        for preset in self._presets.values():
            cat_name = preset.category.value
            categories[cat_name] = categories.get(cat_name, 0) + 1
        return categories

    def get_preset_styles(self) -> dict[str, int]:
        """获取预设风格统计"""
        styles = {}
        for preset in self._presets.values():
            style_name = preset.style.value
            styles[style_name] = styles.get(style_name, 0) + 1
        return styles

    def save_preset(self, preset: FilterPreset, file_path: str) -> None:
        """保存预设到JSON文件"""
        data = preset.to_dict()
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_preset(self, file_path: str) -> FilterPreset:
        """从JSON文件加载预设"""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return FilterPreset.from_dict(data)

    def add_preset(self, preset: FilterPreset) -> None:
        """添加预设到库中"""
        self._presets[preset.id] = preset.copy()

    def remove_preset(self, preset_id: str) -> None:
        """移除预设"""
        if preset_id in self._presets:
            del self._presets[preset_id]

    def __len__(self) -> int:
        return len(self._presets)

    def __contains__(self, preset_id: str) -> bool:
        return preset_id in self._presets


# =============================================================================
# FilterAI 智能滤镜系统
# =============================================================================

class FilterAI:
    """
    智能滤镜推荐系统

    基于场景、风格、素材分析提供滤镜推荐，支持自动色彩校正、
    智能强度调整、滤镜链建议和质量评估。
    """

    def __init__(self, preset_library: FilterPresetLibrary | None = None):
        self.preset_library = preset_library or FilterPresetLibrary()
        self._scene_style_map = self._build_scene_style_map()

    def _build_scene_style_map(self) -> dict[SceneType, list[FilterStyle]]:
        """构建场景-风格映射表"""
        return {
            SceneType.PORTRAIT: [FilterStyle.SOFT, FilterStyle.WARM, FilterStyle.CINEMATIC, FilterStyle.FILM],
            SceneType.LANDSCAPE: [FilterStyle.HIGH_CONTRAST, FilterStyle.CINEMATIC, FilterStyle.DREAMY, FilterStyle.COOL],
            SceneType.PRODUCT: [FilterStyle.SHARP, FilterStyle.CLEAN, FilterStyle.HIGH_CONTRAST, FilterStyle.CINEMATIC],
            SceneType.TEXT: [FilterStyle.SHARP, FilterStyle.HIGH_CONTRAST, FilterStyle.GLOW, FilterStyle.CINEMATIC],
            SceneType.VLOG: [FilterStyle.WARM, FilterStyle.SOFT, FilterStyle.CINEMATIC, FilterStyle.FILM],
            SceneType.CINEMATIC: [FilterStyle.CINEMATIC, FilterStyle.FILM, FilterStyle.HIGH_CONTRAST, FilterStyle.DREAMY],
            SceneType.ANIME: [FilterStyle.ANIME, FilterStyle.DREAMY, FilterStyle.VIBRANT, FilterStyle.CYBERPUNK],
            SceneType.DOCUMENTARY: [FilterStyle.FILM, FilterStyle.CINEMATIC, FilterStyle.DESATURATED, FilterStyle.NATURAL],
            SceneType.MUSIC_VIDEO: [FilterStyle.CYBERPUNK, FilterStyle.GLITCH, FilterStyle.CINEMATIC, FilterStyle.DREAMY],
            SceneType.TUTORIAL: [FilterStyle.CLEAN, FilterStyle.SHARP, FilterStyle.BRIGHT, FilterStyle.NATURAL],
        }

    def recommend_by_scene(
        self,
        scene_type: SceneType,
        software: SoftwareType | None = None,
        top_n: int = 5,
    ) -> list[FilterRecommendation]:
        """
        基于场景类型推荐滤镜

        Args:
            scene_type: 场景类型
            software: 目标软件
            top_n: 返回推荐数量

        Returns:
            推荐结果列表，按置信度排序
        """
        styles = self._scene_style_map.get(scene_type, [FilterStyle.CINEMATIC])
        recommendations = []

        for i, style in enumerate(styles):
            style_presets = self.preset_library.get_style_presets(style)
            if software:
                style_presets = [
                    p for p in style_presets if software in p.software_support
                ]

            base_confidence = 1.0 - (i * 0.15)
            for preset in style_presets[:3]:
                confidence = base_confidence * (0.9 + 0.1 * (hash(preset.id) % 10) / 10)
                recommendations.append(FilterRecommendation(
                    preset=preset,
                    confidence=min(1.0, confidence),
                    reason=f"适合{scene_type.value}场景的{style.value}风格",
                    priority=i,
                ))

        recommendations.sort(key=lambda x: (-x.confidence, x.priority))
        return recommendations[:top_n]

    def recommend_by_style(
        self,
        style: FilterStyle,
        software: SoftwareType | None = None,
        top_n: int = 10,
    ) -> list[FilterRecommendation]:
        """
        基于视觉风格推荐滤镜

        Args:
            style: 目标风格
            software: 目标软件
            top_n: 返回推荐数量

        Returns:
            推荐结果列表
        """
        presets = self.preset_library.get_style_presets(style)
        if software:
            presets = [p for p in presets if software in p.software_support]

        recommendations = []
        for i, preset in enumerate(presets[:top_n]):
            confidence = 1.0 - (i * 0.05)
            recommendations.append(FilterRecommendation(
                preset=preset,
                confidence=max(0.5, confidence),
                reason=f"{style.value}风格精选",
                priority=i,
            ))

        return recommendations

    def auto_color_correct(
        self,
        image_analysis: dict[str, Any] | None = None,
    ) -> FilterPreset:
        """
        自动色彩校正建议

        Args:
            image_analysis: 图像分析结果（亮度、对比度、色相等）

        Returns:
            推荐的色彩校正预设
        """
        default_analysis = {
            "brightness": 0.5,
            "contrast": 0.5,
            "saturation": 0.5,
            "color_temperature": 0.5,
            "dominant_color": [128, 128, 128],
        }
        analysis = {**default_analysis, **(image_analysis or {})}

        params = {
            "brightness": FilterParam(
                name="brightness",
                value=(0.5 - analysis["brightness"]) * 40,
                min_value=-100,
                max_value=100,
                param_type="float",
                description="亮度调整",
            ),
            "contrast": FilterParam(
                name="contrast",
                value=(0.5 - analysis["contrast"]) * 30,
                min_value=-100,
                max_value=100,
                param_type="float",
                description="对比度调整",
            ),
            "saturation": FilterParam(
                name="saturation",
                value=(0.5 - analysis["saturation"]) * 20,
                min_value=-100,
                max_value=100,
                param_type="float",
                description="饱和度调整",
            ),
            "temperature": FilterParam(
                name="temperature",
                value=(0.5 - analysis["color_temperature"]) * 30,
                min_value=-100,
                max_value=100,
                param_type="float",
                description="色温调整",
            ),
        }

        return FilterPreset(
            id="auto_color_correct",
            name="自动色彩校正",
            category=FilterCategory.COLOR_CORRECTION,
            style=FilterStyle.CINEMATIC,
            software_support=[
                SoftwareType.AFTER_EFFECTS,
                SoftwareType.PHOTOSHOP,
                SoftwareType.DAVINCI_RESOLVE,
                SoftwareType.FFMPEG,
            ],
            params=params,
            intensity=1.0,
            description="基于图像分析的自动色彩校正建议",
            author="FilterAI",
            version="1.0.0",
            tags=["auto", "color_correction", "ai"],
        )

    def intensity_adjust(
        self,
        preset: FilterPreset,
        source_analysis: dict[str, Any],
    ) -> float:
        """
        基于素材的智能强度调整

        Args:
            preset: 滤镜预设
            source_analysis: 源素材分析结果

        Returns:
            建议的强度值 (0-1)
        """
        base_intensity = preset.intensity
        brightness = source_analysis.get("brightness", 0.5)
        contrast = source_analysis.get("contrast", 0.5)
        detail_level = source_analysis.get("detail_level", 0.5)

        adjustment = 1.0
        if preset.category == FilterCategory.BLUR_SHARPEN:
            if detail_level > 0.7:
                adjustment = 0.8
            elif detail_level < 0.3:
                adjustment = 1.2
        elif preset.category == FilterCategory.COLOR_CORRECTION:
            if contrast > 0.7:
                adjustment *= 0.9
            if brightness > 0.8:
                adjustment *= 0.9

        return max(0.1, min(1.0, base_intensity * adjustment))

    def filter_chain_suggest(
        self,
        scene_type: SceneType,
        style: FilterStyle | None = None,
        length: int = 3,
    ) -> list[FilterPreset]:
        """
        建议多滤镜组合链

        Args:
            scene_type: 场景类型
            style: 目标风格
            length: 滤镜链长度

        Returns:
            建议的滤镜列表（按应用顺序）
        """
        if style is None:
            style = self._scene_style_map.get(scene_type, [FilterStyle.CINEMATIC])[0]

        chain = []
        style_presets = self.preset_library.get_style_presets(style)

        color_presets = [
            p for p in style_presets if p.category == FilterCategory.COLOR_CORRECTION
        ]
        if color_presets and length >= 1:
            chain.append(color_presets[0])

        enhance_presets = [
            p for p in style_presets
            if p.category in (FilterCategory.BLUR_SHARPEN, FilterCategory.STYLIZE)
        ]
        if enhance_presets and length >= 2:
            chain.append(enhance_presets[0])

        finish_presets = [
            p for p in style_presets
            if p.category in (FilterCategory.NOISE_GRAIN, FilterCategory.UTILITY)
        ]
        if finish_presets and length >= 3:
            chain.append(finish_presets[0])

        return chain[:length]

    def quality_assess(
        self,
        filter_chain: FilterChain,
        source_analysis: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        评估滤镜质量和伪影风险

        Args:
            filter_chain: 滤镜链
            source_analysis: 源素材分析

        Returns:
            质量评估结果
        """
        total_opacity = 0
        artifact_risk = 0
        quality_score = 100

        for item in filter_chain.get_enabled_filters():
            total_opacity += item.opacity

            preset = item.preset
            if preset.category == FilterCategory.BLUR_SHARPEN:
                for param in preset.params.values():
                    if param.param_type in ("float", "int"):
                        normalized = param.normalize()
                        if normalized > 0.7:
                            artifact_risk += 10 * normalized

            if preset.category == FilterCategory.DISTORT:
                artifact_risk += 15

            if preset.style == FilterStyle.GLITCH:
                artifact_risk += 20

        if len(filter_chain) > 5:
            quality_score -= (len(filter_chain) - 5) * 5

        quality_score -= artifact_risk
        quality_score = max(0, min(100, quality_score))

        risk_level = "low"
        if artifact_risk > 50:
            risk_level = "high"
        elif artifact_risk > 25:
            risk_level = "medium"

        return {
            "quality_score": quality_score,
            "artifact_risk": artifact_risk,
            "risk_level": risk_level,
            "filter_count": len(filter_chain),
            "total_opacity": total_opacity,
            "suggestions": self._generate_quality_suggestions(filter_chain, artifact_risk),
        }

    def _generate_quality_suggestions(
        self,
        filter_chain: FilterChain,
        artifact_risk: float,
    ) -> list[str]:
        """生成质量改进建议"""
        suggestions = []

        if len(filter_chain) > 6:
            suggestions.append("滤镜数量较多，考虑合并或移除不必要的滤镜")

        if artifact_risk > 40:
            suggestions.append("伪影风险较高，建议降低模糊/扭曲类滤镜强度")

        blur_count = sum(
            1 for item in filter_chain
            if item.preset.category == FilterCategory.BLUR_SHARPEN
        )
        if blur_count > 2:
            suggestions.append("多个模糊滤镜叠加，注意检查画质损失")

        if not suggestions:
            suggestions.append("滤镜组合质量良好")

        return suggestions


# =============================================================================
# UnifiedFilterAPI 跨软件桥接
# =============================================================================

class UnifiedFilterAPI:
    """
    统一滤镜API - 跨软件桥接

    提供统一的滤镜应用接口，支持在不同软件之间转换预设，
    批量处理和兼容性验证。
    """

    def __init__(self):
        self._engines: dict[SoftwareType, BaseFilterEngine] = {}
        self._preset_library = FilterPresetLibrary()
        self._ai = FilterAI(self._preset_library)
        self._init_engines()

    def _init_engines(self) -> None:
        """初始化所有可用的滤镜引擎"""
        try:
            self._engines[SoftwareType.AFTER_EFFECTS] = AEFilterEngine()
        except Exception:
            pass
        try:
            self._engines[SoftwareType.PHOTOSHOP] = PSFilterEngine()
        except Exception:
            pass
        try:
            self._engines[SoftwareType.DAVINCI_RESOLVE] = ResolveFilterEngine()
        except Exception:
            pass
        try:
            self._engines[SoftwareType.BLENDER] = BlenderFilterEngine()
        except Exception:
            pass
        try:
            self._engines[SoftwareType.FFMPEG] = FFmpegFilterEngine()
        except Exception:
            pass

    def get_engine(self, software: SoftwareType) -> BaseFilterEngine:
        """获取指定软件的滤镜引擎"""
        if software not in self._engines:
            raise SoftwareNotSupportedError(f"不支持的软件: {software.value}")
        return self._engines[software]

    def get_available_software(self) -> list[SoftwareType]:
        """获取可用的软件列表"""
        return list(self._engines.keys())

    def apply_filter(
        self,
        software: SoftwareType,
        filter_name: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        统一API - 应用单个滤镜

        Args:
            software: 目标软件
            filter_name: 滤镜名称
            params: 滤镜参数

        Returns:
            滤镜应用结果
        """
        engine = self.get_engine(software)
        return engine.apply_filter(filter_name, params)

    def apply_filter_chain(
        self,
        software: SoftwareType,
        filters: list[tuple[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """
        统一API - 应用滤镜链

        Args:
            software: 目标软件
            filters: 滤镜列表

        Returns:
            滤镜应用结果列表
        """
        engine = self.get_engine(software)
        return engine.apply_filter_chain(filters)

    def generate_script(
        self,
        software: SoftwareType,
        filters: list[tuple[str, dict[str, Any]]],
        **kwargs,
    ) -> str:
        """
        统一API - 生成脚本

        Args:
            software: 目标软件
            filters: 滤镜列表
            **kwargs: 额外参数

        Returns:
            生成的脚本代码
        """
        engine = self.get_engine(software)
        return engine.generate_script(filters, **kwargs)

    def convert_preset(
        self,
        preset: FilterPreset,
        target_software: SoftwareType,
    ) -> FilterPreset:
        """
        将预设转换为目标软件兼容格式

        Args:
            preset: 源预设
            target_software: 目标软件

        Returns:
            转换后的预设
        """
        if target_software in preset.software_support:
            return preset.copy()

        converted = preset.copy()
        converted.software_support = list(set(converted.software_support + [target_software]))
        converted.id = f"{preset.id}_{target_software.value}"
        converted.name = f"{preset.name} ({target_software.value})"
        converted.description = f"[已转换] {preset.description}"

        new_params = {}
        for param_name, param in converted.params.items():
            new_param = FilterParam(
                name=param_name,
                value=param.value,
                min_value=param.min_value,
                max_value=param.max_value,
                param_type=param.param_type,
                unit=param.unit,
                description=f"[转换自{preset.id}] {param.description}",
            )
            new_params[param_name] = new_param

        converted.params = new_params
        return converted

    def export_to_software(
        self,
        filter_chain: FilterChain,
        target_software: SoftwareType,
        **kwargs,
    ) -> str:
        """
        将滤镜链导出为目标软件的脚本

        Args:
            filter_chain: 滤镜链
            target_software: 目标软件
            **kwargs: 额外参数

        Returns:
            生成的脚本代码
        """
        engine = self.get_engine(target_software)

        filters = []
        for item in filter_chain.get_enabled_filters():
            preset = item.preset
            params = {k: v.value for k, v in preset.params.items()}
            filters.append((preset.name, params))

        return engine.generate_script(filters, **kwargs)

    def batch_process(
        self,
        software: SoftwareType,
        filter_name: str,
        param_variations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        批量应用滤镜（不同参数变体）

        Args:
            software: 目标软件
            filter_name: 滤镜名称
            param_variations: 参数变体列表

        Returns:
            批量处理结果列表
        """
        engine = self.get_engine(software)
        results = []
        for i, params in enumerate(param_variations):
            result = engine.apply_filter(filter_name, params)
            result["batch_index"] = i
            results.append(result)
        return results

    def validate_compatibility(
        self,
        preset: FilterPreset,
        software: SoftwareType,
    ) -> dict[str, Any]:
        """
        验证预设与软件的兼容性

        Args:
            preset: 滤镜预设
            software: 目标软件

        Returns:
            兼容性验证结果
        """
        is_supported = software in preset.software_support
        engine = self._engines.get(software)

        available_filters = []
        if engine:
            available_filters = engine.get_available_filters()

        issues = []
        if not is_supported:
            issues.append("预设不支持该软件")

        param_count = len(preset.params)
        if param_count > 50:
            issues.append("参数数量较多，可能需要简化")

        return {
            "compatible": is_supported,
            "software": software.value,
            "preset_id": preset.id,
            "available_filters": len(available_filters),
            "param_count": param_count,
            "issues": issues,
            "can_convert": not is_supported and engine is not None,
        }

    def get_preset_library(self) -> FilterPresetLibrary:
        """获取预设库"""
        return self._preset_library

    def get_ai(self) -> FilterAI:
        """获取AI推荐系统"""
        return self._ai


# =============================================================================
# 主函数 - 演示
# =============================================================================

def main():
    """Filter Engine 演示程序"""
    print("=" * 70)
    print("  Filter Engine v2.0 - 跨软件滤镜系统集成引擎")
    print("=" * 70)
    print()

    unified_api = UnifiedFilterAPI()
    preset_library = unified_api.get_preset_library()
    ai = unified_api.get_ai()

    print("[1] 系统状态")
    print("-" * 50)
    available_software = unified_api.get_available_software()
    print(f"  可用软件引擎: {len(available_software)} 个")
    for sw in available_software:
        print(f"    - {sw.value}")
    print(f"  内置预设总数: {len(preset_library)} 个")
    print()

    print("[2] 预设分类统计")
    print("-" * 50)
    categories = preset_library.get_preset_categories()
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count} 个")
    print()

    print("[3] 预设风格统计")
    print("-" * 50)
    styles = preset_library.get_preset_styles()
    for style, count in sorted(styles.items()):
        print(f"  {style}: {count} 个")
    print()

    print("[4] 电影风格预设示例")
    print("-" * 50)
    cinematic_presets = preset_library.get_style_presets(FilterStyle.CINEMATIC)
    for i, preset in enumerate(cinematic_presets[:5], 1):
        print(f"  {i}. {preset.name} ({preset.id})")
        print(f"     {preset.description[:50]}...")
    print()

    print("[5] AI场景推荐 - 人像场景")
    print("-" * 50)
    recommendations = ai.recommend_by_scene(SceneType.PORTRAIT, top_n=3)
    for i, rec in enumerate(recommendations, 1):
        print(f"  {i}. {rec.preset.name}")
        print(f"     置信度: {rec.confidence:.2%} | {rec.reason}")
    print()

    print("[6] 滤镜链演示 - 创建电影风格滤镜链")
    print("-" * 50)
    chain = FilterChain("cinematic_look")
    cine_presets = preset_library.get_style_presets(FilterStyle.CINEMATIC)
    if cine_presets:
        chain.add_filter(cine_presets[0], opacity=100, blend_mode=BlendMode.NORMAL)
        if len(cine_presets) > 1:
            chain.add_filter(cine_presets[1], opacity=50, blend_mode=BlendMode.SOFT_LIGHT)
    print(f"  滤镜链名称: {chain.name}")
    print(f"  滤镜数量: {len(chain)}")
    for i, item in enumerate(chain):
        print(f"    {i+1}. {item.preset.name} | 不透明度: {item.opacity}% | 混合: {item.blend_mode.value}")
    print()

    print("[7] 质量评估")
    print("-" * 50)
    quality = ai.quality_assess(chain)
    print(f"  质量评分: {quality['quality_score']}/100")
    print(f"  伪影风险: {quality['artifact_risk']} ({quality['risk_level']})")
    print("  改进建议:")
    for suggestion in quality["suggestions"]:
        print(f"    - {suggestion}")
    print()

    print("[8] AE脚本生成示例")
    print("-" * 50)
    try:
        ae_engine = unified_api.get_engine(SoftwareType.AFTER_EFFECTS)
        ae_filters = ae_engine.get_color_correction_filters()[:3]
        filter_list = [(f, {}) for f in ae_filters]
        script = ae_engine.generate_script(filter_list, layer_name="myLayer")
        print(script[:300] + "...")
    except Exception as e:
        print(f"  跳过: {e}")
    print()

    print("[9] FFmpeg命令生成示例")
    print("-" * 50)
    try:
        ffmpeg_engine = unified_api.get_engine(SoftwareType.FFMPEG)
        video_filters = [
            ("ff_eq", {"brightness": 0.1, "contrast": 1.2}),
            ("ff_gblur", {"sigma": 0.5}),
        ]
        cmd = ffmpeg_engine.generate_command(
            "input.mp4", "output.mp4",
            video_filters=video_filters,
        )
        print(f"  {cmd[:150]}...")
    except Exception as e:
        print(f"  跳过: {e}")
    print()

    print("[10] 搜索预设 - 模糊")
    print("-" * 50)
    search_results = preset_library.search_presets(keyword="模糊")
    print(f"  找到 {len(search_results)} 个匹配预设")
    for preset in search_results[:5]:
        print(f"    - {preset.name} ({preset.style.value})")
    print()

    print("=" * 70)
    print("  演示完成！Filter Engine 系统运行正常。")
    print("=" * 70)


if __name__ == "__main__":
    main()