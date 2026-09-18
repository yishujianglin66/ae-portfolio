"""
effect_knowledge_graph.py - Python版效果知识图谱
基于TypeScript版 effect-knowledge-graph.ts 移植
包含65个AE内置效果、效果关系、风格配方
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EffectParameter:
    name: str
    param_type: str  # number, color, enum, boolean, point
    min_val: float | None = None
    max_val: float | None = None
    default: Any = None
    intensity_scale: float = 0.0
    enum_values: list[str] | None = None


@dataclass
class EffectNode:
    match_name: str
    display_name: str
    category: str
    sub_category: str | None = None
    tags: list[str] = field(default_factory=list)
    parameters: list[EffectParameter] = field(default_factory=list)
    confidence: float = 0.8
    description: str = ""


@dataclass
class EffectRelation:
    effect_a: str
    effect_b: str
    relation_type: str  # synergy, mutex, prerequisite, post
    strength: float = 0.8
    description: str = ""


@dataclass
class StyleRecipeEffect:
    match_name: str
    settings: dict[str, Any] = field(default_factory=dict)
    intensity_param: str | None = None
    intensity_factor: float = 0.0


@dataclass
class StyleRecipe:
    name: str
    display_name: str
    category: str
    description: str
    keywords: list[str] = field(default_factory=list)
    intensity_range: list[float] = field(default_factory=lambda: [0.2, 1.5])
    effects: list[StyleRecipeEffect] = field(default_factory=list)


def _build_effect_knowledge_graph() -> dict[str, EffectNode]:
    """构建效果知识图谱"""
    graph = {}

    def add_effect(match_name, display_name, category, sub_category, tags, params, confidence, description):
        parameters = []
        for p in params:
            parameters.append(EffectParameter(
                name=p.get("name", ""),
                param_type=p.get("type", "number"),
                min_val=p.get("min"),
                max_val=p.get("max"),
                default=p.get("default"),
                intensity_scale=p.get("intensityScale", 0.0),
                enum_values=p.get("enumValues")
            ))
        graph[match_name] = EffectNode(
            match_name=match_name,
            display_name=display_name,
            category=category,
            sub_category=sub_category,
            tags=tags,
            parameters=parameters,
            confidence=confidence,
            description=description
        )

    # ===== 1. 模糊与锐化类 (10个) =====
    add_effect(
        "ADBE Gaussian Blur 2", "Gaussian Blur", "blur_sharpen", "blur",
        ["模糊", "柔化", "虚化", "gaussian", "blur", "高斯模糊"],
        [
            {"name": "Blurriness", "type": "number", "min": 0, "max": 1000, "default": 10, "intensityScale": 1.0},
            {"name": "Blur Dimensions", "type": "enum", "enumValues": ["Horizontal and Vertical", "Horizontal", "Vertical"], "default": "Horizontal and Vertical"},
        ],
        0.88, "高斯模糊，最常用的柔化效果"
    )

    add_effect(
        "ADBE Fast Box Blur", "Fast Box Blur", "blur_sharpen", "blur",
        ["快速模糊", "box blur", "方块模糊", "盒式模糊"],
        [
            {"name": "Blurriness", "type": "number", "min": 0, "max": 1000, "default": 10, "intensityScale": 1.0},
            {"name": "Blur Dimensions", "type": "enum", "enumValues": ["Horizontal and Vertical", "Horizontal", "Vertical"], "default": "Horizontal and Vertical"},
            {"name": "Repeat Edge Pixels", "type": "boolean", "default": True},
        ],
        0.75, "快速盒式模糊，性能优化的模糊效果"
    )

    add_effect(
        "ADBE Directional Blur", "Directional Blur", "blur_sharpen", "blur",
        ["方向模糊", "运动模糊", "motion blur", "拖尾", "拉丝"],
        [
            {"name": "Direction", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Blur Length", "type": "number", "min": 0, "max": 1000, "default": 20, "intensityScale": 1.0},
        ],
        0.85, "方向性模糊，模拟运动拖尾效果"
    )

    add_effect(
        "CC Radial Blur", "CC Radial Blur", "blur_sharpen", "blur",
        ["径向模糊", "放射模糊", "radial blur", "变焦模糊", "旋焦"],
        [
            {"name": "Type", "type": "enum", "enumValues": ["Zoom", "Rotate"], "default": "Zoom"},
            {"name": "Amount", "type": "number", "min": 0, "max": 200, "default": 30, "intensityScale": 1.0},
            {"name": "Quality", "type": "number", "min": 1, "max": 100, "default": 20},
        ],
        0.82, "径向模糊，放射状或旋转状模糊效果"
    )

    add_effect(
        "ADBE Camera Lens Blur", "Camera Lens Blur", "blur_sharpen", "blur",
        ["镜头模糊", "景深", "bokeh", "散景", "焦外成像"],
        [
            {"name": "Blur Amount", "type": "number", "min": 0, "max": 100, "default": 15, "intensityScale": 1.0},
            {"name": "Iris Shape", "type": "enum", "enumValues": ["Hexagon", "Pentagon", "Square", "Circle"], "default": "Hexagon"},
            {"name": "Iris Rotation", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Highlight Gain", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.80, "镜头模糊，模拟真实相机景深效果"
    )

    add_effect(
        "ADBE Bilateral Blur", "Bilateral Blur", "blur_sharpen", "blur",
        ["双边模糊", "保边模糊", "bilateral", "智能模糊", "表面模糊"],
        [
            {"name": "Radius", "type": "number", "min": 0, "max": 100, "default": 10, "intensityScale": 1.0},
            {"name": "Threshold", "type": "number", "min": 0, "max": 255, "default": 50},
        ],
        0.72, "双边模糊，保持边缘的同时柔化区域"
    )

    add_effect(
        "ADBE Compound Blur", "Compound Blur", "blur_sharpen", "blur",
        ["复合模糊", "区域模糊", "compound blur", "深度模糊"],
        [
            {"name": "Maximum Blur", "type": "number", "min": 0, "max": 200, "default": 20, "intensityScale": 1.0},
            {"name": "Blur Layer", "type": "enum", "enumValues": ["None"], "default": "None"},
        ],
        0.70, "复合模糊，基于图层亮度控制模糊程度"
    )

    add_effect(
        "ADBE Channel Blur", "Channel Blur", "blur_sharpen", "blur",
        ["通道模糊", "channel blur", "分通道模糊"],
        [
            {"name": "Red Blurriness", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Green Blurriness", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Blue Blurriness", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Alpha Blurriness", "type": "number", "min": 0, "max": 1000, "default": 0},
        ],
        0.68, "通道模糊，各通道独立模糊"
    )

    add_effect(
        "ADBE Unsharp Mask", "Unsharp Mask", "blur_sharpen", "sharpen",
        ["锐化", "sharpen", "非锐化蒙版", "usm"],
        [
            {"name": "Amount", "type": "number", "min": 0, "max": 500, "default": 50, "intensityScale": 1.0},
            {"name": "Radius", "type": "number", "min": 0.1, "max": 100, "default": 1.0},
            {"name": "Threshold", "type": "number", "min": 0, "max": 255, "default": 0},
        ],
        0.85, "非锐化蒙版，专业锐化效果"
    )

    add_effect(
        "CC Vector Blur", "CC Vector Blur", "blur_sharpen", "blur",
        ["矢量模糊", "vector blur", "向量模糊"],
        [
            {"name": "Amount", "type": "number", "min": 0, "max": 200, "default": 20, "intensityScale": 1.0},
            {"name": "Angle Offset", "type": "number", "min": 0, "max": 360, "default": 0},
        ],
        0.70, "矢量模糊，方向性柔化效果"
    )

    # ===== 2. 颜色校正类 (10个) =====
    add_effect(
        "ADBE Brightness & Contrast 2", "Brightness & Contrast", "color_correction", "basic",
        ["亮度", "对比度", "brightness", "contrast", "明暗"],
        [
            {"name": "Brightness", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Contrast", "type": "number", "min": -100, "max": 100, "default": 0, "intensityScale": 1.0},
            {"name": "Use Legacy", "type": "boolean", "default": False},
        ],
        0.90, "亮度对比度，最基础的颜色调整"
    )

    add_effect(
        "ADBE HUE SATURATION", "Hue/Saturation", "color_correction", "hsl",
        ["色相", "饱和度", "hue", "saturation", "hsl"],
        [
            {"name": "Channel Control", "type": "enum", "enumValues": ["Master", "Reds", "Yellows", "Greens", "Cyans", "Blues", "Magentas"], "default": "Master"},
            {"name": "Master Hue", "type": "number", "min": -180, "max": 180, "default": 0},
            {"name": "Master Saturation", "type": "number", "min": -100, "max": 100, "default": 0, "intensityScale": 1.0},
            {"name": "Master Lightness", "type": "number", "min": -100, "max": 100, "default": 0},
        ],
        0.88, "色相饱和度，调整颜色的基本属性"
    )

    add_effect(
        "ADBE Color Balance", "Color Balance", "color_correction", "color",
        ["色彩平衡", "color balance", "调色", "色偏"],
        [
            {"name": "Shadow Red Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Shadow Green Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Shadow Blue Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Midtone Red Balance", "type": "number", "min": -100, "max": 100, "default": 0, "intensityScale": 0.8},
            {"name": "Midtone Green Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Midtone Blue Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Hilight Red Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Hilight Green Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Hilight Blue Balance", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Preserve Luminosity", "type": "boolean", "default": True},
        ],
        0.85, "色彩平衡，分区调整色彩倾向"
    )

    add_effect(
        "ADBE Protractor2", "Curves", "color_correction", "tonal",
        ["曲线", "curves", "色调曲线", "色阶曲线"],
        [
            {"name": "Channel", "type": "enum", "enumValues": ["RGB", "Red", "Green", "Blue", "Alpha"], "default": "RGB"},
        ],
        0.82, "曲线调整，精确控制色调映射"
    )

    add_effect(
        "ADBE Black & White", "Black & White", "color_correction", "desaturate",
        ["黑白", "单色", "black white", "monochrome", "grayscale", "去色"],
        [
            {"name": "Red", "type": "number", "min": -200, "max": 200, "default": 40},
            {"name": "Yellow", "type": "number", "min": -200, "max": 200, "default": 60},
            {"name": "Green", "type": "number", "min": -200, "max": 200, "default": 30},
            {"name": "Cyan", "type": "number", "min": -200, "max": 200, "default": 60},
            {"name": "Blue", "type": "number", "min": -200, "max": 200, "default": 20},
            {"name": "Magenta", "type": "number", "min": -200, "max": 200, "default": 80},
            {"name": "Tint", "type": "boolean", "default": False},
        ],
        0.80, "黑白效果，专业黑白转换"
    )

    add_effect(
        "ADBE Photo Filter", "Photo Filter", "color_correction", "filter",
        ["照片滤镜", "photo filter", "色温滤镜", "变色镜"],
        [
            {"name": "Filter", "type": "enum", "enumValues": ["Warming Filter (85)", "Warming Filter (LBA)", "Cooling Filter (80)", "Cooling Filter (LBB)", "Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Violet", "Magenta", "Sepia", "Deep Red", "Deep Blue", "Deep Emerald", "Deep Yellow"], "default": "Warming Filter (85)"},
            {"name": "Density", "type": "number", "min": 0, "max": 100, "default": 25, "intensityScale": 1.0},
            {"name": "Preserve Luminosity", "type": "boolean", "default": True},
        ],
        0.78, "照片滤镜，模拟摄影滤镜效果"
    )

    add_effect(
        "ADBE Levels", "Levels", "color_correction", "tonal",
        ["色阶", "levels", "亮度色阶", "对比度调整"],
        [
            {"name": "Channel", "type": "enum", "enumValues": ["RGB", "Red", "Green", "Blue", "Alpha"], "default": "RGB"},
            {"name": "Input Black", "type": "number", "min": 0, "max": 255, "default": 0},
            {"name": "Input White", "type": "number", "min": 0, "max": 255, "default": 255},
            {"name": "Gamma", "type": "number", "min": 0.1, "max": 9.99, "default": 1.0, "intensityScale": 0.5},
            {"name": "Output Black", "type": "number", "min": 0, "max": 255, "default": 0},
            {"name": "Output White", "type": "number", "min": 0, "max": 255, "default": 255},
        ],
        0.83, "色阶调整，控制黑白场和伽马值"
    )

    add_effect(
        "ADBE Tint", "Tint", "color_correction", "tint",
        ["色调", "tint", "着色", "染色"],
        [
            {"name": "Map Black To", "type": "color", "default": [0, 0, 0]},
            {"name": "Map White To", "type": "color", "default": [1, 1, 1]},
            {"name": "Amount to Tint", "type": "number", "min": 0, "max": 100, "default": 100, "intensityScale": 1.0},
        ],
        0.75, "色调映射，将黑白映射到指定颜色"
    )

    add_effect(
        "ADBE Tritone", "Tritone", "color_correction", "tint",
        ["三色", "tritone", "三色调", "渐变映射"],
        [
            {"name": "Highlights", "type": "color", "default": [1, 1, 1]},
            {"name": "Midtones", "type": "color", "default": [0.5, 0.5, 0.5]},
            {"name": "Shadows", "type": "color", "default": [0, 0, 0]},
            {"name": "Blend With Original", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.72, "三色调，黑/灰/白分别映射到颜色"
    )

    add_effect(
        "ADBE Colorama", "Colorama", "color_correction", "special",
        ["彩光", "colorama", "渐变映射", "彩虹效果"],
        [
            {"name": "Input Phase", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Output Cycle", "type": "enum", "enumValues": ["Fire", "Water", "Rainbow", "Sunset", "Night"], "default": "Rainbow"},
            {"name": "Cycle Repetitions", "type": "number", "min": 1, "max": 100, "default": 1, "intensityScale": 0.5},
        ],
        0.65, "彩光效果，渐变映射创意效果"
    )

    # ===== 3. 发光与灯光类 (7个) =====
    add_effect(
        "ADBE Glo2", "Glow", "glow_light", "glow",
        ["发光", "辉光", "glow", "边缘光", "光晕"],
        [
            {"name": "Glow Threshold", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Glow Radius", "type": "number", "min": 0, "max": 200, "default": 20, "intensityScale": 1.0},
            {"name": "Glow Intensity", "type": "number", "min": 0, "max": 10, "default": 1.0, "intensityScale": 0.8},
            {"name": "Glow Colors", "type": "enum", "enumValues": ["Original Colors", "A & B Colors", "Arbitrary Map"], "default": "Original Colors"},
            {"name": "Glow Color A", "type": "color", "default": [1, 1, 1]},
            {"name": "Glow Color B", "type": "color", "default": [1, 0.5, 0]},
        ],
        0.88, "发光效果，最常用的辉光效果"
    )

    add_effect(
        "ADBE Starglow", "Starglow", "glow_light", "glow",
        ["星芒", "starglow", "十字星", "星爆"],
        [
            {"name": "Input Threshold", "type": "number", "min": 0, "max": 255, "default": 100},
            {"name": "Star Glow Length", "type": "number", "min": 0, "max": 100, "default": 20, "intensityScale": 1.0},
            {"name": "Boost Light", "type": "number", "min": 0, "max": 100, "default": 10},
        ],
        0.80, "星芒效果，星形射线发光"
    )

    add_effect(
        "CC Light Rays", "CC Light Rays", "glow_light", "light",
        ["体积光", "光柱", "god ray", "light rays", "光线", "光束"],
        [
            {"name": "Intensity", "type": "number", "min": 0, "max": 500, "default": 100, "intensityScale": 1.0},
            {"name": "Radius", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Warp", "type": "number", "min": 0, "max": 2, "default": 0.5},
        ],
        0.82, "体积光，丁达尔效应光束效果"
    )

    add_effect(
        "CC Glue Gun", "CC Glue Gun", "glow_light", "special",
        ["热熔胶", "glue gun", "发光描边"],
        [
            {"name": "Intensity", "type": "number", "min": 0, "max": 200, "default": 50, "intensityScale": 1.0},
            {"name": "Softness", "type": "number", "min": 0, "max": 50, "default": 10},
            {"name": "Color", "type": "color", "default": [1, 1, 0.8]},
        ],
        0.70, "热熔胶效果，发光描边效果"
    )

    add_effect(
        "ADBE Lens Flare", "Lens Flare", "glow_light", "flare",
        ["镜头光晕", "lens flare", "光斑", "耀斑"],
        [
            {"name": "Flare Center", "type": "point", "default": [0.5, 0.5]},
            {"name": "Flare Brightness", "type": "number", "min": 10, "max": 300, "default": 100, "intensityScale": 1.0},
            {"name": "Lens Type", "type": "enum", "enumValues": ["50-300mm Zoom", "35mm Prime", "105mm Prime"], "default": "50-300mm Zoom"},
            {"name": "Blend With Original", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.85, "镜头光晕，模拟相机镜头光斑"
    )

    add_effect(
        "CC Light Burst 2.5", "CC Light Burst", "glow_light", "burst",
        ["光爆", "light burst", "爆发光", "爆裂光"],
        [
            {"name": "Center", "type": "point", "default": [0.5, 0.5]},
            {"name": "Intensity", "type": "number", "min": 0, "max": 500, "default": 120, "intensityScale": 1.0},
            {"name": "Burst Length", "type": "number", "min": 0.1, "max": 2, "default": 0.8},
            {"name": "Amplitude", "type": "number", "min": 0, "max": 100, "default": 15},
        ],
        0.75, "光爆效果，放射状光线爆发"
    )

    add_effect(
        "ADBE Vegas", "Vegas", "glow_light", "stroke",
        ["维加斯", "vegas", "描边光", "流动光"],
        [
            {"name": "Stroke", "type": "enum", "enumValues": ["Image Contours", "Mask/Path", "Alpha Channel"], "default": "Image Contours"},
            {"name": "Color", "type": "color", "default": [1, 1, 0]},
            {"name": "Length", "type": "number", "min": 0, "max": 1, "default": 0.5, "intensityScale": 0.5},
            {"name": "Segments", "type": "number", "min": 1, "max": 100, "default": 6},
            {"name": "Rotation", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Width", "type": "number", "min": 0, "max": 50, "default": 3, "intensityScale": 0.5},
            {"name": "Hardness", "type": "number", "min": 0, "max": 1, "default": 0.5},
            {"name": "Start Point", "type": "point", "default": [0, 0.5]},
        ],
        0.72, "维加斯效果，描边发光动画"
    )

    # ===== 4. 扭曲类 (9个) =====
    add_effect(
        "ADBE Turbulent Displace", "Turbulent Displace", "distort", "displace",
        ["湍流置换", "turbulent", "流体扭曲", "热浪", "水波"],
        [
            {"name": "Displacement", "type": "enum", "enumValues": ["Turbulent", "Vertical", "Horizontal"], "default": "Turbulent"},
            {"name": "Amount", "type": "number", "min": 0, "max": 500, "default": 30, "intensityScale": 1.0},
            {"name": "Size", "type": "number", "min": 1, "max": 500, "default": 40},
            {"name": "Offset", "type": "point", "default": [0, 0]},
            {"name": "Complexity", "type": "number", "min": 1, "max": 10, "default": 3},
            {"name": "Evolution", "type": "number", "min": 0, "max": 360, "default": 0},
        ],
        0.85, "湍流置换，流体波动扭曲效果"
    )

    add_effect(
        "ADBE Wave Warp", "Wave Warp", "distort", "wave",
        ["波浪扭曲", "wave warp", "正弦波", "规律波动"],
        [
            {"name": "Wave Type", "type": "enum", "enumValues": ["Sine", "Square", "Triangle", "Sawtooth", "Circle"], "default": "Sine"},
            {"name": "Wave Height", "type": "number", "min": 0, "max": 500, "default": 50, "intensityScale": 1.0},
            {"name": "Wave Width", "type": "number", "min": 2, "max": 5000, "default": 200},
            {"name": "Direction", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Wave Speed", "type": "number", "min": -100, "max": 100, "default": 1},
            {"name": "Phase", "type": "number", "min": 0, "max": 360, "default": 0},
        ],
        0.82, "波浪扭曲，周期性波形变形"
    )

    add_effect(
        "CC Power Pin", "CC Power Pin", "distort", "perspective",
        ["四角变形", "power pin", "透视变形", "corner pin"],
        [
            {"name": "Top Left", "type": "point", "default": [0, 0]},
            {"name": "Top Right", "type": "point", "default": [1, 0]},
            {"name": "Bottom Left", "type": "point", "default": [0, 1]},
            {"name": "Bottom Right", "type": "point", "default": [1, 1]},
            {"name": "Perspective", "type": "number", "min": 0, "max": 100, "default": 50, "intensityScale": 0.5},
        ],
        0.80, "四角定位，透视变形控制"
    )

    add_effect(
        "CC Bender", "CC Bender", "distort", "bend",
        ["弯曲", "bender", "折弯", "卷曲"],
        [
            {"name": "Amount", "type": "number", "min": -180, "max": 180, "default": 30, "intensityScale": 1.0},
            {"name": "Axis", "type": "enum", "enumValues": ["Horizontal", "Vertical"], "default": "Horizontal"},
        ],
        0.72, "弯曲效果，图像折弯变形"
    )

    add_effect(
        "CC Bulge", "CC Bulge", "distort", "magnify",
        ["凸起", "bulge", "膨胀", "放大镜"],
        [
            {"name": "Radius", "type": "number", "min": 0, "max": 1000, "default": 100, "intensityScale": 0.5},
            {"name": "Bulge Height", "type": "number", "min": -100, "max": 100, "default": 50, "intensityScale": 1.0},
            {"name": "Taper Radius", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Antialiasing", "type": "enum", "enumValues": ["Low", "Medium", "High"], "default": "Medium"},
        ],
        0.75, "凸起效果，膨胀或凹陷变形"
    )

    add_effect(
        "ADBE Liquify", "Liquify", "distort", "liquify",
        ["液化", "liquify", "局部变形", "推挤变形"],
        [
            {"name": "Warp Tool Options", "type": "number", "min": 0, "max": 100, "default": 50, "intensityScale": 0.5},
        ],
        0.70, "液化效果，笔刷式局部变形"
    )

    add_effect(
        "CC Page Turn", "CC Page Turn", "distort", "page",
        ["翻页", "page turn", "卷页", "翻书效果"],
        [
            {"name": "Fold Direction", "type": "number", "min": 0, "max": 360, "default": 45},
            {"name": "Fold Amount", "type": "number", "min": 0, "max": 100, "default": 30, "intensityScale": 1.0},
            {"name": "Light Direction", "type": "number", "min": 0, "max": 360, "default": -45},
        ],
        0.78, "翻页效果，书页卷曲动画"
    )

    add_effect(
        "ADBE Mesh Warp", "Mesh Warp", "distort", "mesh",
        ["网格变形", "mesh warp", "格栅变形"],
        [
            {"name": "Rows", "type": "number", "min": 2, "max": 50, "default": 7},
            {"name": "Columns", "type": "number", "min": 2, "max": 50, "default": 7},
            {"name": "Quality", "type": "number", "min": 1, "max": 10, "default": 5, "intensityScale": 0.3},
        ],
        0.68, "网格变形，基于控制点的自由变形"
    )

    add_effect(
        "CC Lens", "CC Lens", "distort", "lens",
        ["镜头", "lens", "鱼眼", "广角"],
        [
            {"name": "Size", "type": "number", "min": 1, "max": 100, "default": 60, "intensityScale": 0.5},
            {"name": "Convergence", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Center", "type": "point", "default": [0.5, 0.5]},
        ],
        0.74, "镜头效果，鱼眼或广角畸变"
    )

    # ===== 5. 噪波与颗粒类 (6个) =====
    add_effect(
        "ADBE Fractal Noise", "Fractal Noise", "noise_grain", "fractal",
        ["分形噪波", "fractal noise", "噪波", "噪声", "分形噪声"],
        [
            {"name": "Fractal Type", "type": "enum", "enumValues": ["Smeary", "Turbulent Smooth", "Turbulent Basic", "Turbulent Sharp", "Dynamic Progressive", "Dynamic Twist", "Subtle", "Stringy", "Small", "Zigzag"], "default": "Turbulent Basic"},
            {"name": "Noise Type", "type": "enum", "enumValues": ["Soft Linear", "Linear", "Soft Spline", "Spline"], "default": "Soft Linear"},
            {"name": "Brightness", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Contrast", "type": "number", "min": 0, "max": 500, "default": 100, "intensityScale": 0.8},
            {"name": "Scale", "type": "number", "min": 1, "max": 5000, "default": 100},
            {"name": "Offset Turbulence", "type": "point", "default": [0, 0]},
            {"name": "Complexity", "type": "number", "min": 1, "max": 20, "default": 6},
            {"name": "Evolution", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Overflow", "type": "enum", "enumValues": ["Clip", "Wrap Back", "Wrap Around"], "default": "Clip"},
        ],
        0.90, "分形噪波，最强大的噪波生成器"
    )

    add_effect(
        "ADBE Noise", "Noise", "noise_grain", "noise",
        ["噪点", "noise", "颗粒", "颗粒感", "film grain"],
        [
            {"name": "Amount of Noise", "type": "number", "min": 0, "max": 100, "default": 10, "intensityScale": 1.0},
            {"name": "Noise Type", "type": "enum", "enumValues": ["Uniform", "Squared", "Gaussian", "Grain"], "default": "Grain"},
            {"name": "Clipping", "type": "boolean", "default": True},
        ],
        0.82, "噪点效果，添加胶片颗粒感"
    )

    add_effect(
        "ADBE Median", "Median", "noise_grain", "denoise",
        ["中间值", "median", "降噪", "去噪点", "平滑"],
        [
            {"name": "Radius", "type": "number", "min": 0, "max": 100, "default": 3, "intensityScale": 1.0},
            {"name": "Operator", "type": "enum", "enumValues": ["Median", "Minimum", "Maximum"], "default": "Median"},
            {"name": "Channel", "type": "enum", "enumValues": ["All", "Color", "Alpha"], "default": "All"},
        ],
        0.75, "中间值滤波，降噪和平滑"
    )

    add_effect(
        "ADBE Turbulent Noise", "Turbulent Noise", "noise_grain", "fractal",
        ["湍流噪波", "turbulent noise", "流动噪波", "动态噪波"],
        [
            {"name": "Noise Style", "type": "enum", "enumValues": ["Turbulent Smooth", "Turbulent Basic", "Turbulent Sharp", "Dynamic Progressive", "Dynamic Twist", "Subtle", "Stringy", "Small", "Zigzag", "Swirly", "Drifty", "Fizzy"], "default": "Turbulent Basic"},
            {"name": "Contrast", "type": "number", "min": 0, "max": 500, "default": 150, "intensityScale": 0.8},
            {"name": "Brightness", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Scale", "type": "number", "min": 1, "max": 5000, "default": 200},
            {"name": "Complexity", "type": "number", "min": 1, "max": 20, "default": 5},
            {"name": "Evolution", "type": "number", "min": 0, "max": 360, "default": 0},
        ],
        0.78, "湍流噪波，动态流动噪波效果"
    )

    add_effect(
        "ADBE Dust & Scratches", "Dust & Scratches", "noise_grain", "repair",
        ["蒙尘与划痕", "dust scratches", "去划痕", "修复"],
        [
            {"name": "Radius", "type": "number", "min": 1, "max": 100, "default": 5, "intensityScale": 1.0},
            {"name": "Threshold", "type": "number", "min": 0, "max": 255, "default": 10},
        ],
        0.70, "蒙尘与划痕，去除小瑕疵"
    )

    add_effect(
        "ADBE Noise Alpha", "Noise Alpha", "noise_grain", "noise",
        ["Alpha噪波", "noise alpha", "通道噪波", "杂色"],
        [
            {"name": "Amount", "type": "number", "min": 0, "max": 100, "default": 20, "intensityScale": 1.0},
            {"name": "Noise Type", "type": "enum", "enumValues": ["Uniform Random", "Squared Random", "Gaussian", "Grain"], "default": "Uniform Random"},
            {"name": "Overflow", "type": "enum", "enumValues": ["Clip", "Wrap"], "default": "Clip"},
        ],
        0.68, "Alpha通道噪波，透明通道加噪"
    )

    # ===== 6. 通道与键控类 (6个) =====
    add_effect(
        "ADBE Color Key", "Color Key", "channel_keying", "keying",
        ["颜色键控", "color key", "抠像", "色键", "抠图"],
        [
            {"name": "Key Color", "type": "color", "default": [0, 0, 1]},
            {"name": "Color Tolerance", "type": "number", "min": 0, "max": 255, "default": 50, "intensityScale": 1.0},
            {"name": "Edge Thin", "type": "number", "min": -100, "max": 100, "default": 0},
            {"name": "Edge Feather", "type": "number", "min": 0, "max": 100, "default": 5},
        ],
        0.85, "颜色键控，基础色键抠像"
    )

    add_effect(
        "ADBE Luma Key", "Luma Key", "channel_keying", "keying",
        ["亮度键控", "luma key", "亮度抠像", "明度键"],
        [
            {"name": "Key Type", "type": "enum", "enumValues": ["Key Out Brighter", "Key Out Darker", "Key Out Similar", "Key Out Dissimilar"], "default": "Key Out Brighter"},
            {"name": "Threshold", "type": "number", "min": 0, "max": 255, "default": 128, "intensityScale": 0.5},
            {"name": "Tolerance", "type": "number", "min": 0, "max": 255, "default": 50},
            {"name": "Edge Feather", "type": "number", "min": 0, "max": 100, "default": 2},
        ],
        0.80, "亮度键控，基于亮度抠像"
    )

    add_effect(
        "ADBE Set Matte", "Set Matte", "channel_keying", "matte",
        ["设置蒙版", "set matte", "轨道蒙版", "遮罩设置"],
        [
            {"name": "Take Matte From Layer", "type": "enum", "enumValues": ["None"], "default": "None"},
            {"name": "Use For Matte", "type": "enum", "enumValues": ["Luminance", "Alpha", "Red Channel", "Green Channel", "Blue Channel"], "default": "Luminance"},
            {"name": "Invert Matte", "type": "boolean", "default": False},
            {"name": "Stretch Matte to Fit", "type": "boolean", "default": True},
            {"name": "Composite Matte with Original", "type": "boolean", "default": False},
        ],
        0.75, "设置蒙版，使用图层作为遮罩"
    )

    add_effect(
        "ADBE Simple Choker", "Simple Choker", "channel_keying", "matte",
        ["简单阻塞", "simple choker", "边缘收缩", "蒙版收缩"],
        [
            {"name": "Choke Matte", "type": "number", "min": -100, "max": 100, "default": 5, "intensityScale": 1.0},
        ],
        0.78, "简单阻塞，收缩或扩展蒙版边缘"
    )

    add_effect(
        "ADBE Shift Channels", "Shift Channels", "channel_keying", "channel",
        ["通道转换", "shift channels", "rgb通道", "通道交换"],
        [
            {"name": "Take Alpha From", "type": "enum", "enumValues": ["Full On", "Full Off", "Luminance", "Alpha", "Red Channel", "Green Channel", "Blue Channel"], "default": "Alpha"},
            {"name": "Take Red From", "type": "enum", "enumValues": ["Luminance", "Alpha", "Red Channel", "Green Channel", "Blue Channel"], "default": "Red Channel"},
            {"name": "Take Green From", "type": "enum", "enumValues": ["Luminance", "Alpha", "Red Channel", "Green Channel", "Blue Channel"], "default": "Green Channel"},
            {"name": "Take Blue From", "type": "enum", "enumValues": ["Luminance", "Alpha", "Red Channel", "Green Channel", "Blue Channel"], "default": "Blue Channel"},
        ],
        0.72, "通道转换，通道重定向和交换"
    )

    add_effect(
        "ADBE Matte Choker", "Matte Choker", "channel_keying", "matte",
        ["蒙版阻塞", "matte choker", "高级收缩", "精细遮罩"],
        [
            {"name": "Geometric Softness", "type": "number", "min": 0, "max": 200, "default": 10, "intensityScale": 0.8},
            {"name": "Choke", "type": "number", "min": -100, "max": 100, "default": 5},
            {"name": "Gray Level Softness", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Iterations", "type": "number", "min": 1, "max": 20, "default": 5},
        ],
        0.70, "蒙版阻塞，高级遮罩边缘处理"
    )

    # ===== 7. 风格化类 (8个) =====
    add_effect(
        "ADBE Mosaic", "Mosaic", "stylize", "pixelate",
        ["马赛克", "mosaic", "打码", "像素化", "pixelate"],
        [
            {"name": "Horizontal Blocks", "type": "number", "min": 1, "max": 1000, "default": 50, "intensityScale": 1.0},
            {"name": "Vertical Blocks", "type": "number", "min": 1, "max": 1000, "default": 50},
            {"name": "Sharp Colors", "type": "boolean", "default": False},
        ],
        0.92, "马赛克，像素化效果"
    )

    add_effect(
        "ADBE Find Edges", "Find Edges", "stylize", "edge",
        ["查找边缘", "find edges", "线稿", "轮廓", "勾边", "描边"],
        [
            {"name": "Invert", "type": "boolean", "default": False},
            {"name": "Blend With Original", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.85, "查找边缘，边缘检测效果"
    )

    add_effect(
        "ADBE Cartoon", "Cartoon", "stylize", "artistic",
        ["卡通", "cartoon", "动画风格", "赛璐璐"],
        [
            {"name": "Render", "type": "enum", "enumValues": ["Fill", "Edges", "Fill & Edges"], "default": "Fill & Edges"},
            {"name": "Detail", "type": "number", "min": 0, "max": 100, "default": 12},
            {"name": "Edge Threshold", "type": "number", "min": 0, "max": 10, "default": 2.0, "intensityScale": 0.8},
            {"name": "Edge Width", "type": "number", "min": 0, "max": 10, "default": 4.0, "intensityScale": 0.5},
            {"name": "Smoothness", "type": "number", "min": 0, "max": 10, "default": 5.0},
        ],
        0.80, "卡通效果，动画风格渲染"
    )

    add_effect(
        "CC Vignette", "CC Vignette", "stylize", "vignette",
        ["暗角", "vignette", "晕映", "边角压暗", "暗角效果"],
        [
            {"name": "Amount", "type": "number", "min": -200, "max": 200, "default": -30, "intensityScale": 1.0},
            {"name": "Midpoint", "type": "number", "min": 0, "max": 100, "default": 70},
            {"name": "Roundness", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Softness", "type": "number", "min": 0, "max": 100, "default": 60},
        ],
        0.88, "暗角效果，晕映边框"
    )

    add_effect(
        "ADBE Roughen Edges", "Roughen Edges", "stylize", "edge",
        ["粗糙边缘", "roughen edges", "边缘粗糙", "风化效果", "破损边缘"],
        [
            {"name": "Edge Type", "type": "enum", "enumValues": ["Roughen", "Rusty", "Spiky", "Photocopy", "Rough Color"], "default": "Roughen"},
            {"name": "Border", "type": "number", "min": 0, "max": 200, "default": 10, "intensityScale": 1.0},
            {"name": "Edge Sharpness", "type": "number", "min": 0, "max": 10, "default": 3},
            {"name": "Fractal Influence", "type": "number", "min": 0, "max": 1, "default": 0.5},
            {"name": "Scale", "type": "number", "min": 10, "max": 5000, "default": 100},
            {"name": "Complexity", "type": "number", "min": 1, "max": 10, "default": 3},
            {"name": "Evolution", "type": "number", "min": 0, "max": 360, "default": 0},
        ],
        0.80, "粗糙边缘，边缘风化破损效果"
    )

    add_effect(
        "ADBE Emboss", "Emboss", "stylize", "emboss",
        ["浮雕", "emboss", "凹凸效果", "立体浮雕"],
        [
            {"name": "Direction", "type": "number", "min": 0, "max": 360, "default": 45},
            {"name": "Relief", "type": "number", "min": 0, "max": 100, "default": 5, "intensityScale": 1.0},
            {"name": "Contrast", "type": "number", "min": 0, "max": 100, "default": 50},
            {"name": "Blend With Original", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.75, "浮雕效果，凹凸立体效果"
    )

    add_effect(
        "ADBE Stamp", "Stamp", "stylize", "artistic",
        ["图章", "stamp", "印章效果", "木刻"],
        [
            {"name": "Light/Dark Balance", "type": "number", "min": 0, "max": 255, "default": 128},
            {"name": "Smoothness", "type": "number", "min": 0, "max": 100, "default": 5, "intensityScale": 0.5},
        ],
        0.70, "图章效果，木刻版画风格"
    )

    add_effect(
        "CC Kaleida", "CC Kaleida", "stylize", "kaleidoscope",
        ["万花筒", "kaleida", "镜像对称", "千变万化"],
        [
            {"name": "Size", "type": "number", "min": 0, "max": 200, "default": 50, "intensityScale": 0.5},
            {"name": "Sides", "type": "number", "min": 3, "max": 30, "default": 6},
            {"name": "Angle", "type": "number", "min": 0, "max": 360, "default": 0},
            {"name": "Mirror", "type": "boolean", "default": True},
        ],
        0.72, "万花筒效果，镜像对称"
    )

    # ===== 8. 透视与3D类 (6个) =====
    add_effect(
        "ADBE Drop Shadow", "Drop Shadow", "perspective_3d", "shadow",
        ["投影", "阴影", "drop shadow", "影子"],
        [
            {"name": "Shadow Color", "type": "color", "default": [0, 0, 0]},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 75},
            {"name": "Direction", "type": "number", "min": 0, "max": 360, "default": 135},
            {"name": "Distance", "type": "number", "min": 0, "max": 1000, "default": 12, "intensityScale": 0.8},
            {"name": "Softness", "type": "number", "min": 0, "max": 100, "default": 10},
        ],
        0.90, "投影效果，经典阴影"
    )

    add_effect(
        "ADBE Bevel Alpha", "Bevel Alpha", "perspective_3d", "bevel",
        ["倒角", "bevel alpha", "斜面", "立体边缘"],
        [
            {"name": "Edge Thickness", "type": "number", "min": 0, "max": 100, "default": 10, "intensityScale": 1.0},
            {"name": "Light Angle", "type": "number", "min": 0, "max": 360, "default": -45},
            {"name": "Light Color", "type": "color", "default": [1, 1, 1]},
            {"name": "Light Intensity", "type": "number", "min": 0, "max": 100, "default": 50},
        ],
        0.82, "倒角Alpha，立体边缘效果"
    )

    add_effect(
        "ADBE Basic 3D", "Basic 3D", "perspective_3d", "3d",
        ["基础3D", "basic 3d", "3d旋转", "三维旋转", "空间翻转"],
        [
            {"name": "Swivel", "type": "number", "min": -360, "max": 360, "default": 0},
            {"name": "Tilt", "type": "number", "min": -360, "max": 360, "default": 0},
            {"name": "Distance to Image", "type": "number", "min": 0, "max": 10000, "default": 0, "intensityScale": 0.3},
            {"name": "Specular Highlight", "type": "boolean", "default": False},
            {"name": "Preview", "type": "boolean", "default": False},
        ],
        0.80, "基础3D，简单三维旋转"
    )

    add_effect(
        "CC Sphere", "CC Sphere", "perspective_3d", "3d",
        ["球面", "sphere", "球体", "球形化"],
        [
            {"name": "Radius", "type": "number", "min": 0, "max": 500, "default": 100, "intensityScale": 1.0},
            {"name": "Rotation", "type": "number", "min": -360, "max": 360, "default": 0},
            {"name": "Light", "type": "number", "min": -180, "max": 180, "default": 45},
            {"name": "Light Height", "type": "number", "min": -90, "max": 90, "default": 45},
            {"name": "Shading", "type": "number", "min": 0, "max": 100, "default": 50},
        ],
        0.78, "球体效果，球面映射"
    )

    add_effect(
        "CC Cylinder", "CC Cylinder", "perspective_3d", "3d",
        ["圆柱", "cylinder", "柱面化"],
        [
            {"name": "Radius", "type": "number", "min": 0, "max": 500, "default": 100, "intensityScale": 1.0},
            {"name": "Rotation", "type": "number", "min": -360, "max": 360, "default": 0},
            {"name": "Light", "type": "number", "min": -180, "max": 180, "default": 45},
            {"name": "Light Height", "type": "number", "min": -90, "max": 90, "default": 45},
            {"name": "Shading", "type": "number", "min": 0, "max": 100, "default": 50},
        ],
        0.72, "圆柱效果，柱面映射"
    )

    add_effect(
        "ADBE Optics Compensation", "Optics Compensation", "perspective_3d", "distort",
        ["光学补偿", "optics compensation", "镜头畸变", "鱼眼", "桶形畸变"],
        [
            {"name": "Field of View", "type": "number", "min": 0, "max": 180, "default": 30, "intensityScale": 1.0},
            {"name": "Reverse Lens Distortion", "type": "boolean", "default": False},
            {"name": "View Center", "type": "point", "default": [0.5, 0.5]},
        ],
        0.75, "光学补偿，镜头畸变校正"
    )

    # ===== 9. 生成与绘制类 (7个) =====
    add_effect(
        "ADBE Fill", "Fill", "generate_draw", "fill",
        ["填充", "fill", "纯色填充", "颜色填充"],
        [
            {"name": "Color", "type": "color", "default": [1, 1, 1]},
            {"name": "Horizontal Feather", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Vertical Feather", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100, "intensityScale": 0.5},
        ],
        0.88, "填充效果，纯色填充图层"
    )

    add_effect(
        "ADBE Ramp", "Ramp", "generate_draw", "gradient",
        ["渐变", "ramp", "渐变色", "渐变填充", "过渡色"],
        [
            {"name": "Start of Ramp", "type": "point", "default": [0, 0]},
            {"name": "Start Color", "type": "color", "default": [1, 1, 1]},
            {"name": "End of Ramp", "type": "point", "default": [0, 1]},
            {"name": "End Color", "type": "color", "default": [0, 0, 0]},
            {"name": "Ramp Shape", "type": "enum", "enumValues": ["Linear Ramp", "Radial Ramp"], "default": "Linear Ramp"},
            {"name": "Ramp Scatter", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Blend With Original", "type": "number", "min": 0, "max": 100, "default": 0},
        ],
        0.85, "渐变效果，线性或径向渐变"
    )

    add_effect(
        "ADBE Stroke", "Stroke", "generate_draw", "stroke",
        ["描边", "stroke", "画线", "路径描边"],
        [
            {"name": "Path", "type": "enum", "enumValues": ["None"], "default": "None"},
            {"name": "Color", "type": "color", "default": [1, 1, 1]},
            {"name": "Brush Size", "type": "number", "min": 0, "max": 100, "default": 2, "intensityScale": 0.8},
            {"name": "Brush Hardness", "type": "number", "min": 0, "max": 100, "default": 100},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100},
            {"name": "Start", "type": "number", "min": 0, "max": 100, "default": 0},
            {"name": "End", "type": "number", "min": 0, "max": 100, "default": 100},
            {"name": "Spacing", "type": "number", "min": 0, "max": 500, "default": 1},
            {"name": "Paint On", "type": "enum", "enumValues": ["Original Image", "Transparent"], "default": "Original Image"},
        ],
        0.82, "描边效果，路径描边动画"
    )

    add_effect(
        "ADBE 4-Color Gradient", "4-Color Gradient", "generate_draw", "gradient",
        ["四色渐变", "4-color gradient", "四角渐变", "多色渐变"],
        [
            {"name": "Top Left", "type": "color", "default": [1, 0, 0]},
            {"name": "Top Right", "type": "color", "default": [0, 1, 0]},
            {"name": "Bottom Left", "type": "color", "default": [0, 0, 1]},
            {"name": "Bottom Right", "type": "color", "default": [1, 1, 0]},
            {"name": "Blend", "type": "number", "min": 0, "max": 100, "default": 50, "intensityScale": 0.5},
            {"name": "Jitter", "type": "number", "min": 0, "max": 100, "default": 0},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100},
        ],
        0.78, "四色渐变，四角颜色渐变"
    )

    add_effect(
        "ADBE Circle", "Circle", "generate_draw", "shape",
        ["圆形", "circle", "圆环", "生成圆形"],
        [
            {"name": "Center", "type": "point", "default": [0.5, 0.5]},
            {"name": "Radius", "type": "number", "min": 0, "max": 5000, "default": 100, "intensityScale": 1.0},
            {"name": "Edge", "type": "enum", "enumValues": ["None", "Edge Radius"], "default": "None"},
            {"name": "Thickness", "type": "number", "min": 0, "max": 100, "default": 10},
            {"name": "Feather", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Invert Circle", "type": "boolean", "default": False},
            {"name": "Color", "type": "color", "default": [1, 1, 1]},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100},
        ],
        0.80, "圆形，生成圆形或圆环"
    )

    add_effect(
        "ADBE Checkerboard", "Checkerboard", "generate_draw", "pattern",
        ["棋盘格", "checkerboard", "格子", "格纹"],
        [
            {"name": "Anchor", "type": "point", "default": [0, 0]},
            {"name": "Size From", "type": "enum", "enumValues": ["Corner", "Width", "Width & Height"], "default": "Corner"},
            {"name": "Corner", "type": "point", "default": [0.1, 0.1]},
            {"name": "Color 1", "type": "color", "default": [1, 1, 1]},
            {"name": "Color 2", "type": "color", "default": [0, 0, 0]},
            {"name": "Feather", "type": "number", "min": 0, "max": 1000, "default": 0},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100, "intensityScale": 0.3},
        ],
        0.75, "棋盘格，网格图案"
    )

    add_effect(
        "CC Particle World", "CC Particle World", "generate_draw", "particle",
        ["粒子世界", "particle world", "粒子系统", "粒子特效"],
        [
            {"name": "Birth Rate", "type": "number", "min": 0, "max": 1000, "default": 100, "intensityScale": 1.0},
            {"name": "Longevity", "type": "number", "min": 0.1, "max": 10, "default": 2.0},
            {"name": "Position X", "type": "number", "min": -1, "max": 2, "default": 0.5},
            {"name": "Position Y", "type": "number", "min": -1, "max": 2, "default": 0.5},
            {"name": "Position Z", "type": "number", "min": -1, "max": 1, "default": 0},
            {"name": "Velocity", "type": "number", "min": 0, "max": 500, "default": 50, "intensityScale": 0.8},
            {"name": "Gravity", "type": "number", "min": -200, "max": 200, "default": 0},
            {"name": "Particle Radius", "type": "number", "min": 0.1, "max": 100, "default": 5, "intensityScale": 0.6},
            {"name": "Opacity", "type": "number", "min": 0, "max": 100, "default": 100},
            {"name": "Red", "type": "number", "min": 0, "max": 1, "default": 1},
            {"name": "Green", "type": "number", "min": 0, "max": 1, "default": 1},
            {"name": "Blue", "type": "number", "min": 0, "max": 1, "default": 1},
        ],
        0.82, "CC粒子世界，专业的3D粒子效果"
    )

    return graph


def _build_effect_relations() -> list[EffectRelation]:
    """构建效果关系图谱"""
    relations = []

    def add_rel(a, b, rel_type, strength, desc):
        relations.append(EffectRelation(
            effect_a=a,
            effect_b=b,
            relation_type=rel_type,
            strength=strength,
            description=desc
        ))

    # 协同关系 (synergy) - 1+1>2
    add_rel("ADBE Glo2", "ADBE HUE SATURATION", "synergy", 0.85,
            "发光+色相饱和度：增强发光色彩表现")
    add_rel("ADBE Glo2", "ADBE Directional Blur", "synergy", 0.8,
            "发光+方向模糊：动态拖尾发光效果")
    add_rel("ADBE Drop Shadow", "ADBE Bevel Alpha", "synergy", 0.82,
            "投影+倒角：立体效果更真实")
    add_rel("ADBE Turbulent Displace", "ADBE Fractal Noise", "synergy", 0.75,
            "湍流置换+分形噪波：流体扭曲更自然")
    add_rel("ADBE Gaussian Blur 2", "ADBE Unsharp Mask", "synergy", 0.78,
            "高斯模糊+锐化：图像细节控制")
    add_rel("CC Vignette", "ADBE Brightness & Contrast 2", "synergy", 0.85,
            "暗角+对比度：电影感组合")
    add_rel("ADBE Color Balance", "ADBE Curves", "synergy", 0.88,
            "色彩平衡+曲线：专业调色黄金组合")
    add_rel("CC Light Rays", "ADBE Glo2", "synergy", 0.8,
            "体积光+发光：圣光效果增强")
    add_rel("ADBE Roughen Edges", "ADBE Find Edges", "synergy", 0.72,
            "粗糙边缘+查找边缘：手绘质感")
    add_rel("ADBE Fill", "ADBE Tint", "synergy", 0.7,
            "填充+色调：颜色组合效果")

    # 互斥关系 (mutex) - 不要同时用
    add_rel("ADBE Gaussian Blur 2", "ADBE Fast Box Blur", "mutex", 0.9,
            "高斯模糊和快速盒式模糊功能重复")
    add_rel("ADBE Color Key", "ADBE Luma Key", "mutex", 0.85,
            "颜色键和亮度键通常二选一")
    add_rel("ADBE Unsharp Mask", "ADBE Mosaic", "mutex", 0.95,
            "锐化和马赛克效果完全相反")
    add_rel("CC Sphere", "CC Cylinder", "mutex", 0.7,
            "球体和圆柱效果不兼容")
    add_rel("ADBE Fill", "ADBE 4-Color Gradient", "mutex", 0.8,
            "纯色填充和四色渐变功能重叠")

    # 前置关系 (prerequisite) - A应该在B之前
    add_rel("ADBE Color Key", "ADBE Simple Choker", "prerequisite", 0.85,
            "抠像后再收缩边缘")
    add_rel("ADBE Color Key", "ADBE Matte Choker", "prerequisite", 0.8,
            "抠像后再精细遮罩")
    add_rel("ADBE Set Matte", "ADBE Drop Shadow", "prerequisite", 0.75,
            "设置蒙版后再添加投影")
    add_rel("ADBE Gaussian Blur 2", "ADBE Unsharp Mask", "prerequisite", 0.7,
            "先模糊再锐化效果更好")

    # 后置关系 (post) - A之后加B效果更好
    add_rel("ADBE Glo2", "ADBE Brightness & Contrast 2", "post", 0.7,
            "发光后微调亮度对比度")
    add_rel("CC Particle World", "ADBE Glo2", "post", 0.82,
            "粒子之后加发光更炫")
    add_rel("ADBE Fill", "ADBE Glo2", "post", 0.75,
            "填充后加发光有辉光感")
    add_rel("ADBE Stroke", "ADBE Glo2", "post", 0.78,
            "描边后加发光有霓虹感")
    add_rel("ADBE Texturize", "ADBE Unsharp Mask", "post", 0.7,
            "纹理后加锐化增强质感")

    return relations


EFFECT_KNOWLEDGE_GRAPH: dict[str, EffectNode] = _build_effect_knowledge_graph()
EFFECT_RELATIONS: list[EffectRelation] = _build_effect_relations()

CATEGORIES = {
    "blur_sharpen": "模糊与锐化",
    "color_correction": "颜色校正",
    "glow_light": "发光与灯光",
    "distort": "扭曲",
    "noise_grain": "噪波与颗粒",
    "channel_keying": "通道与键控",
    "stylize": "风格化",
    "perspective_3d": "透视与3D",
    "generate_draw": "生成与绘制",
}


def get_effect_by_match_name(match_name: str) -> EffectNode | None:
    return EFFECT_KNOWLEDGE_GRAPH.get(match_name)


def get_effects_by_category(category: str) -> list[EffectNode]:
    return [e for e in EFFECT_KNOWLEDGE_GRAPH.values() if e.category == category]


def search_effects(keyword: str) -> list[EffectNode]:
    keyword_lower = keyword.lower()
    results = []
    for effect in EFFECT_KNOWLEDGE_GRAPH.values():
        if (keyword_lower in effect.display_name.lower() or
            keyword_lower in effect.match_name.lower() or
            any(keyword_lower in tag.lower() for tag in effect.tags) or
            keyword_lower in effect.description.lower()):
            results.append(effect)
    return results


def get_relations_for_effect(match_name: str) -> list[EffectRelation]:
    return [r for r in EFFECT_RELATIONS
            if r.effect_a == match_name or r.effect_b == match_name]


def get_synergy_effects(match_name: str) -> list[dict[str, Any]]:
    synergies = []
    for r in EFFECT_RELATIONS:
        if r.relation_type != "synergy":
            continue
        if r.effect_a == match_name:
            synergies.append({
                "match_name": r.effect_b,
                "strength": r.strength,
                "description": r.description,
            })
        elif r.effect_b == match_name:
            synergies.append({
                "match_name": r.effect_a,
                "strength": r.strength,
                "description": r.description,
            })
    synergies.sort(key=lambda x: x["strength"], reverse=True)
    return synergies


def get_effect_count() -> int:
    return len(EFFECT_KNOWLEDGE_GRAPH)


# ============================================================================
# LLM 增强版函数 — 与 TypeScript 端 effect-knowledge-graph.ts 对齐
# 策略：本地关键词搜索 → LLM 自然语言搜索 → 合并去重 → 记忆缓存
# 失败时自动降级为纯本地搜索
# ============================================================================

def search_effects_enhanced(description: str) -> list[EffectNode]:
    """
    LLM 增强版效果搜索 — 从关键词搜索升级为自然语言搜索
    失败时自动降级为纯本地搜索

    策略：
      1. 查记忆系统
      2. 本地关键词搜索
      3. LLM 不可用时返回本地结果
      4. LLM 自然语言搜索
      5. 合并去重 + 记录到记忆系统
    """
    import asyncio
    import json as _json
    import re as _re

    # 1. 本地关键词搜索
    local_results = search_effects(description)

    # 2. 尝试导入 LLM 网关和记忆系统
    try:
        from core.llm_gateway import TaskType, llm_gateway
        from core.memory_store import memory_store
    except ImportError:
        return local_results

    # 3. 查记忆系统
    experiences = memory_store.get_experience(
        category="effect_search",
        task_keyword=description[:50],
        limit=2,
    )
    if experiences and experiences[0].confidence > 0.85:
        exp = experiences[0]
        cached_names = exp.content.get("effect_names", [])
        if cached_names:
            cached_results = [
                EFFECT_KNOWLEDGE_GRAPH[name]
                for name in cached_names
                if name in EFFECT_KNOWLEDGE_GRAPH
            ]
            if cached_results:
                return cached_results

    # 4. LLM 不可用时降级
    if not llm_gateway.is_available():
        return local_results

    # 5. LLM 自然语言搜索
    try:
        # 收集所有效果名作为候选
        all_effects = [
            {"matchName": e.match_name, "displayName": e.display_name,
             "category": e.category, "tags": e.tags,
             "description": e.description}
            for e in EFFECT_KNOWLEDGE_GRAPH.values()
        ]

        result = asyncio.run(llm_gateway.chat_with_routing(
            message=(
                f"用户描述: {description}\n\n"
                f"可选效果列表:\n{_json.dumps(all_effects[:20], ensure_ascii=False)}\n\n"
                f"返回JSON: {{\"effects\":[\"matchName1\",\"matchName2\"]}}"
            ),
            task_type=TaskType.EFFECT_SEARCH,
            system_prompt=(
                "你是AE效果推荐专家。"
                "根据用户自然语言描述，从效果列表中推荐最匹配的效果。"
                "返回JSON格式: "
                '{"effects":["matchName1","matchName2"]}'
            ),
        ))

        if result.success and result.content:
            match = _re.search(r'\{[^{}]*"effects"[^{}]*\}', result.content, _re.DOTALL)
            if match:
                parsed = _json.loads(match.group(0))
                llm_names = parsed.get("effects", [])

                # 合并去重（LLM 结果优先）
                seen = set()
                merged = []
                for name in llm_names:
                    if name in EFFECT_KNOWLEDGE_GRAPH and name not in seen:
                        merged.append(EFFECT_KNOWLEDGE_GRAPH[name])
                        seen.add(name)
                for effect in local_results:
                    if effect.match_name not in seen:
                        merged.append(effect)
                        seen.add(effect.match_name)

                # 6. 记录到记忆系统
                memory_store.remember(
                    category="effect_search",
                    key=description[:50],
                    content={"effect_names": [e.match_name for e in merged]},
                    tags=[description[:20]],
                    confidence=0.8,
                )
                return merged
    except Exception:
        # LLM 增强失败，返回本地结果
        pass

    return local_results


def recommend_style_enhanced(description: str) -> StyleRecipe | None:
    """
    LLM 增强版风格配方推荐
    Python 端无内置风格配方数据，完全依赖 LLM 推荐
    LLM 不可用时返回 None

    策略：
      1. 查记忆系统
      2. LLM 不可用时返回 None
      3. LLM 推荐风格配方
      4. 记录到记忆系统
    """
    import asyncio
    import json as _json
    import re as _re

    try:
        from core.llm_gateway import TaskType, llm_gateway
        from core.memory_store import memory_store
    except ImportError:
        return None

    # 1. 查记忆系统
    experiences = memory_store.get_experience(
        category="style_recommend",
        task_keyword=description[:50],
        limit=2,
    )
    if experiences and experiences[0].confidence > 0.85:
        exp = experiences[0]
        cached = exp.content.get("style")
        if cached:
            return StyleRecipe(
                name=cached.get("name", ""),
                display_name=cached.get("display_name", ""),
                category=cached.get("category", ""),
                description=cached.get("description", ""),
                keywords=cached.get("keywords", []),
                intensity_range=cached.get("intensity_range", [0.2, 1.5]),
                effects=[],
            )

    # 2. LLM 不可用时降级
    if not llm_gateway.is_available():
        return None

    # 3. LLM 推荐风格配方
    try:
        result = asyncio.run(llm_gateway.chat_with_routing(
            message=(
                f"用户想要: {description}\n\n"
                f"请推荐一个AE效果风格配方。"
            ),
            task_type=TaskType.EFFECT_PLANNING,
            system_prompt=(
                "你是AE效果风格专家。"
                "根据用户描述推荐一个风格配方。"
                "返回JSON格式: "
                '{"name":"风格名","display_name":"显示名",'
                '"category":"类别","description":"描述",'
                '"keywords":["关键词"],"intensity_range":[0.2,1.5],'
                '"effects":[{"matchName":"ADBE Glo2",'
                '"settings":{"Glow Radius":30}}]}'
            ),
        ))

        if result.success and result.content:
            match = _re.search(r'\{[\s\S]*"effects"[\s\S]*\}', result.content)
            if match:
                parsed = _json.loads(match.group(0))
                recipe = StyleRecipe(
                    name=parsed.get("name", ""),
                    display_name=parsed.get("display_name", ""),
                    category=parsed.get("category", ""),
                    description=parsed.get("description", ""),
                    keywords=parsed.get("keywords", []),
                    intensity_range=parsed.get("intensity_range", [0.2, 1.5]),
                    effects=[
                        StyleRecipeEffect(
                            match_name=e.get("matchName", ""),
                            settings=e.get("settings", {}),
                        )
                        for e in parsed.get("effects", [])
                    ],
                )

                # 4. 记录到记忆系统
                memory_store.remember(
                    category="style_recommend",
                    key=description[:50],
                    content={
                        "style": {
                            "name": recipe.name,
                            "display_name": recipe.display_name,
                            "category": recipe.category,
                            "description": recipe.description,
                            "keywords": recipe.keywords,
                            "intensity_range": recipe.intensity_range,
                        }
                    },
                    tags=[recipe.name],
                    confidence=0.75,
                )
                return recipe
    except Exception:
        pass

    return None


def find_conflicts(effect_name: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """检测效果参数间的冲突关系"""
    conflicts = []
    effect = get_effect_by_match_name(effect_name)
    if not effect:
        return conflicts

    if effect_name == "ADBE Glo2":
        radius = settings.get("Glow Radius", 0)
        intensity = settings.get("Glow Intensity", 0)
        if radius > 50 and intensity > 1.5:
            conflicts.append({
                "param1": "Glow Radius",
                "param2": "Glow Intensity",
                "message": "发光半径过大且强度过高，可能导致画面过曝"
            })

    elif effect_name == "ADBE Gaussian Blur 2":
        blurriness = settings.get("Blurriness", 0)
        if blurriness > 100:
            conflicts.append({
                "param1": "Blurriness",
                "param2": None,
                "message": "模糊值过大，可能导致画面完全失焦"
            })

    elif effect_name == "ADBE Starglow":
        streak_length = settings.get("Streak Length", 0)
        boost_light = settings.get("Boost Light", 0)
        if streak_length > 50 and boost_light > 2.0:
            conflicts.append({
                "param1": "Streak Length",
                "param2": "Boost Light",
                "message": "星芒长度和亮度同时过高，可能产生视觉噪点"
            })

    return conflicts


def check_boundaries(effect_name: str, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """检测参数值是否接近边界"""
    issues = []
    effect = get_effect_by_match_name(effect_name)
    if not effect:
        return issues

    for param in effect.parameters:
        if param.name in settings:
            value = settings[param.name]
            if param.min_val is not None and value < param.min_val + (param.max_val - param.min_val) * 0.1:
                issues.append({
                    "param": param.name,
                    "value": value,
                    "boundary": f"min={param.min_val}",
                    "message": f"参数 {param.name} 值接近最小值"
                })
            if param.max_val is not None and value > param.max_val - (param.max_val - param.min_val) * 0.1:
                issues.append({
                    "param": param.name,
                    "value": value,
                    "boundary": f"max={param.max_val}",
                    "message": f"参数 {param.name} 值接近最大值"
                })

    return issues
