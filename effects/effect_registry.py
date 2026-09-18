"""
效果注册表（单一数据源）
========================

统一管理"关键词 -> ADBE 效果 matchName"的映射，消除 parameter_optimizer 与
effect_description_parser 之间的映射重复维护问题。

设计原则：
- 本模块是关键词->matchName 映射的权威来源
- parameter_optimizer.KEYWORD_TO_EFFECT_MAP 从本模块 re-export
- 新增效果时只需在此处更新一处
- 覆盖 VRS VISION 提示词中 60+ 效果类型（含第三方插件）

知识库集成（Phase D）：
- 硬编码映射作为 fallback
- 运行时从 kb_loader 动态加载知识库映射（1400+条目）
- 知识库映射优先，fallback 补充缺失条目
- 外部接口不变，向后兼容

向后兼容：保留 KEYWORD_TO_EFFECT_MAP 名称，现有 import 无需修改。
"""
from typing import Any, Dict, List, Optional

__all__ = [
    "KEYWORD_TO_EFFECT_MAP",
    "EFFECT_DISPLAY_NAMES",
    "EFFECT_PARAMS_DB",
    "EFFECT_CATEGORIES",
    "get_effect_matchname",
    "get_all_effect_keywords",
    "get_effect_params",
    "get_effects_by_category",
    "_KB_LOADED",
]


# ---------------------------------------------------------------------------
# 关键词 -> 效果 matchName 权威映射（覆盖 VRS VISION 60+ 效果类型）
# ---------------------------------------------------------------------------
KEYWORD_TO_EFFECT_MAP: dict[str, str] = {
    # ── blur 模糊类 ──────────────────────────────────────────
    "模糊": "ADBE Gaussian Blur 2",
    "blur": "ADBE Gaussian Blur 2",
    "高斯模糊": "ADBE Gaussian Blur 2",
    "gaussian blur": "ADBE Gaussian Blur 2",
    "景深模糊": "ADBE Camera Lens Blur",
    "lens blur": "ADBE Camera Lens Blur",
    "camera_lens": "ADBE Camera Lens Blur",
    "定向模糊": "ADBE Directional Blur",
    "directional blur": "ADBE Directional Blur",
    "directional": "ADBE Directional Blur",
    "径向模糊": "CC Radial Fast Blur",
    "radial blur": "CC Radial Fast Blur",
    "radial": "CC Radial Fast Blur",
    "方框模糊": "ADBE Box Blur",
    "box blur": "ADBE Box Blur",
    "复合模糊": "ADBE Compound Blur",
    "compound blur": "ADBE Compound Blur",

    # ── glow 发光类 ──────────────────────────────────────────
    "发光": "ADBE Glo2",
    "glow": "ADBE Glo2",
    "辉光": "ADBE Glo2",
    "边缘发光": "ADBE Glo2",
    "内发光": "ADBE Inner Glow",
    "inner glow": "ADBE Inner Glow",
    "星芒": "ADBE Starglow",
    "starglow": "ADBE Starglow",
    "deep_glow": "RB Deep Glow",
    "deep glow": "RB Deep Glow",
    "s_glow": "BCC S_Glow",
    "sapphire glow": "BCC S_Glow",
    "optical_flares": "VC Optical Flares",
    "optical flares": "VC Optical Flares",
    "镜头光斑": "VC Optical Flares",
    "saber": "VC SaberFX",
    "vc saber": "VC SaberFX",
    "能量剑": "VC SaberFX",
    "shine": "TC Shine",
    "trapcode shine": "TC Shine",
    "体积光": "TC Shine",

    # ── particle 粒子类 ──────────────────────────────────────
    "粒子": "ADBE Particle Playground",
    "particle": "ADBE Particle Playground",
    "particle playground": "ADBE Particle Playground",
    "particular": "TC Particular",
    "trapcode particular": "TC Particular",
    "form": "TC Form",
    "trapcode form": "TC Form",
    "cc_particle_world": "CC Particle World",
    "cc particle world": "CC Particle World",
    "cc_particle_systems": "CC Particle Systems II",
    "cc particle systems ii": "CC Particle Systems II",

    # ── distort 扭曲类 ───────────────────────────────────────
    "扭曲": "ADBE Turbulent Displace",
    "distort": "ADBE Turbulent Displace",
    "湍流置换": "ADBE Turbulent Displace",
    "turbulent displace": "ADBE Turbulent Displace",
    "turbulent": "ADBE Turbulent Displace",
    "波浪": "ADBE Wave Warp",
    "wave": "ADBE Wave Warp",
    "wave warp": "ADBE Wave Warp",
    "网格变形": "ADBE Mesh Warp",
    "mesh warp": "ADBE Mesh Warp",
    "液化": "ADBE Liquify",
    "liquify": "ADBE Liquify",
    "光学补偿": "ADBE Optics Compensation",
    "optics compensation": "ADBE Optics Compensation",
    "鱼眼": "ADBE Optics Compensation",
    "边角定位": "ADBE CC Power Pin",
    "cc power pin": "ADBE CC Power Pin",
    "corner pin": "ADBE CC Power Pin",

    # ── color 调色类 ─────────────────────────────────────────
    "色调": "ADBE Curves",
    "曲线": "ADBE Curves",
    "curves": "ADBE Curves",
    "lumetri": "ADBE Lumetri Color",
    "lumetri color": "ADBE Lumetri Color",
    "调色": "ADBE Lumetri Color",
    "色相饱和度": "ADBE HUE SATURATION",
    "hue saturation": "ADBE HUE SATURATION",
    "三色调": "ADBE Tritone",
    "tritone": "ADBE Tritone",
    "cc_toner": "ADBE CC Toner",
    "cc toner": "ADBE CC Toner",
    "lut": "ADBE ImportLUT",
    "import lut": "ADBE ImportLUT",
    "复古胶片": "ADBE Colorista",
    "colorista": "ADBE Colorista",
    "色彩平衡": "ADBE Color Balance",
    "color balance": "ADBE Color Balance",

    # ── transition 转场类 ────────────────────────────────────
    "线性擦除": "ADBE Linear Wipe",
    "linear wipe": "ADBE Linear Wipe",
    "径向擦除": "ADBE Radial Wipe",
    "radial wipe": "ADBE Radial Wipe",
    "卡片擦除": "ADBE Card Wipe",
    "card wipe": "ADBE Card Wipe",
    "像素方块": "CC Block Load",
    "cc_block_load": "CC Block Load",
    "块状加载": "CC Block Load",

    # ── stylize 风格化 ───────────────────────────────────────
    "查找边缘": "ADBE Find Edges",
    "find edges": "ADBE Find Edges",
    "线框": "ADBE Find Edges",
    "粗糙边缘": "ADBE Roughen Edges",
    "roughen edges": "ADBE Roughen Edges",
    "玻璃": "ADBE CC Glass",
    "cc glass": "ADBE CC Glass",

    # ── generate 生成类 ──────────────────────────────────────
    "光束": "ADBE CC Light Rays",
    "cc light rays": "ADBE CC Light Rays",
    "cc_light_rays": "ADBE CC Light Rays",
    "分形噪波纹理": "ADBE Fractal Noise",
    "fractal noise": "ADBE Fractal Noise",
    "单元格": "ADBE Cell Pattern",
    "cell pattern": "ADBE Cell Pattern",
    "渐变填充": "ADBE Ramp",
    "gradient": "ADBE Ramp",

    # ── text 文字动画 ─────────────────────────────────────────
    "文字动画": "ADBE Text Animator",
    "text animator": "ADBE Text Animator",
    "kinetic typography": "ADBE Text Animator",
    "动态排版": "ADBE Text Animator",

    # ── camera_3d 3D 摄像机 ──────────────────────────────────
    "摄像机追踪": "ADBE Camera Tracker",
    "camera tracker": "ADBE Camera Tracker",
    "3d解算": "ADBE Camera Tracker",
    "element_3d": "E3D",
    "element 3d": "E3D",
    "c4d_lite": "ADBE C4D",
    "cinema 4d": "ADBE C4D",

    # ── noise 噪点颗粒 ───────────────────────────────────────
    "添加颗粒": "ADBE Add Grain",
    "add grain": "ADBE Add Grain",
    "胶片颗粒": "ADBE Add Grain",
    "杂色": "ADBE Noise",
    "noise": "ADBE Noise",
    "噪波": "ADBE Fractal Noise",

    # ── matte 遮罩 ───────────────────────────────────────────
    "暗角": "ADBE Vignette",
    "vignette": "ADBE Vignette",
    "cc_vignette": "ADBE Vignette",

    # ── 混合模式（非效果，但用于图层合成） ───────────────────
    "滤色": "BLEND_SCREEN",
    "screen": "BLEND_SCREEN",
    "相乘": "BLEND_MULTIPLY",
    "multiply": "BLEND_MULTIPLY",
    "相加": "BLEND_ADD",
    "add": "BLEND_ADD",
    "叠加": "BLEND_OVERLAY",
    "overlay": "BLEND_OVERLAY",
    "柔光": "BLEND_SOFT_LIGHT",
    "soft light": "BLEND_SOFT_LIGHT",
    "强光": "BLEND_HARD_LIGHT",
    "hard light": "BLEND_HARD_LIGHT",
    "差值": "BLEND_DIFFERENCE",
    "difference": "BLEND_DIFFERENCE",

    # ── 抠像类 ───────────────────────────────────────────────
    "抠像": "ADBE Keylight",
    "keying": "ADBE Keylight",
    "颜色键": "ADBE Color Key",
    "color key": "ADBE Color Key",

    # ── 亮度/对比度 ──────────────────────────────────────────
    "亮度对比度": "ADBE Brightness & Contrast 2",
    "brightness": "ADBE Brightness & Contrast 2",
    "contrast": "ADBE Brightness & Contrast 2",
}

# 硬编码 fallback（知识库加载失败时使用）
_HARDCODED_EFFECT_MAP: dict[str, str] = dict(KEYWORD_TO_EFFECT_MAP)

# ---------------------------------------------------------------------------
# 知识库集成：从 10-风格化剪辑知识库/ 动态加载效果映射
# 知识库映射优先，硬编码 fallback 补充缺失条目
# ---------------------------------------------------------------------------
_KB_RAW_MAP: dict[str, str] = {}
try:
    from knowledge_base.kb_loader import KnowledgeBaseLoader
    _kb_loader = KnowledgeBaseLoader.get_instance()
    _kb_effect_map = _kb_loader.get_effect_map(fallback=_HARDCODED_EFFECT_MAP)
    if _kb_effect_map:
        # 不直接写入注册表：知识库文档抽取数据含大量非 matchName 脏条目，
        # 待 EFFECT_DISPLAY_NAMES 定义后再双门控应用（见下方「知识库映射应用」）
        _KB_RAW_MAP = _kb_effect_map
except Exception:
    pass  # 知识库不可用时使用硬编码映射

# 关键映射保护：硬编码优先条目不被知识库覆盖
_CRITICAL_MAPPINGS = {
    "模糊": "ADBE Gaussian Blur 2",
    "blur": "ADBE Gaussian Blur 2",
    "发光": "ADBE Glo2",
    "glow": "ADBE Glo2",
    "粒子": "ADBE Particle Playground",
    "噪波": "ADBE Fractal Noise",
}
KEYWORD_TO_EFFECT_MAP.update(_CRITICAL_MAPPINGS)


# ---------------------------------------------------------------------------
# 效果显示名（用于 UI 展示）
# ---------------------------------------------------------------------------
EFFECT_DISPLAY_NAMES: dict[str, str] = {
    # blur 模糊类
    "ADBE Gaussian Blur 2": "高斯模糊",
    "ADBE Camera Lens Blur": "相机镜头模糊",
    "ADBE Directional Blur": "定向模糊",
    "CC Radial Fast Blur": "径向模糊",
    "ADBE Box Blur": "方框模糊",
    "ADBE Compound Blur": "复合模糊",
    # glow 发光类
    "ADBE Glo2": "发光",
    "ADBE Inner Glow": "内发光",
    "ADBE Starglow": "星芒",
    "RB Deep Glow": "Deep Glow",
    "BCC S_Glow": "Sapphire 发光",
    "VC Optical Flares": "镜头光斑",
    "VC SaberFX": "能量剑",
    "TC Shine": "体积光",
    # particle 粒子类
    "ADBE Particle Playground": "粒子游乐场",
    "TC Particular": "Trapcode Particular",
    "TC Form": "Trapcode Form",
    "CC Particle World": "CC 粒子世界",
    "CC Particle Systems II": "CC 粒子系统 II",
    # distort 扭曲类
    "ADBE Turbulent Displace": "湍流置换",
    "ADBE Wave Warp": "波浪变形",
    "ADBE Mesh Warp": "网格变形",
    "ADBE Liquify": "液化",
    "ADBE Optics Compensation": "光学补偿",
    "ADBE CC Power Pin": "边角定位",
    # color 调色类
    "ADBE Curves": "曲线",
    "ADBE Lumetri Color": "Lumetri 调色",
    "ADBE HUE SATURATION": "色相/饱和度",
    "ADBE Tritone": "三色调",
    "ADBE CC Toner": "CC 色调",
    "ADBE ImportLUT": "导入 LUT",
    "ADBE Colorista": "Colorista 调色",
    "ADBE Color Balance": "色彩平衡",
    "ADBE Brightness & Contrast 2": "亮度/对比度",
    "ADBE Fill": "填充",
    # transition 转场类
    "ADBE Linear Wipe": "线性擦除",
    "ADBE Radial Wipe": "径向擦除",
    "ADBE Card Wipe": "卡片擦除",
    "CC Block Load": "像素方块化",
    # stylize 风格化
    "ADBE Find Edges": "查找边缘",
    "ADBE Roughen Edges": "粗糙边缘",
    "ADBE CC Glass": "玻璃折射",
    # generate 生成类
    "ADBE CC Light Rays": "CC 光束",
    "ADBE Fractal Noise": "分形噪波",
    "ADBE Cell Pattern": "单元格图案",
    "ADBE Ramp": "渐变填充",
    # text 文字动画
    "ADBE Text Animator": "文字动画器",
    # camera_3d 3D
    "ADBE Camera Tracker": "摄像机追踪",
    "E3D": "Element 3D",
    "ADBE C4D": "Cinema 4D Lite",
    # noise 噪点
    "ADBE Add Grain": "添加颗粒",
    "ADBE Noise": "杂色",
    # matte 遮罩
    "ADBE Vignette": "暗角",
    # keying 抠像
    "ADBE Keylight": "Keylight 抠像",
    "ADBE Color Key": "颜色键",
    # blend 混合模式
    "BLEND_SCREEN": "滤色",
    "BLEND_MULTIPLY": "相乘",
    "BLEND_ADD": "相加",
    "BLEND_OVERLAY": "叠加",
    "BLEND_SOFT_LIGHT": "柔光",
    "BLEND_HARD_LIGHT": "强光",
    "BLEND_DIFFERENCE": "差值",
}


# ---------------------------------------------------------------------------
# 知识库映射应用（双门控，防止脏数据污染注册表）
# 1) matchName 必须匹配合法插件前缀；2) 必须有显示名映射（测试契约）；
# 3) 不覆盖硬编码映射与关键映射
# ---------------------------------------------------------------------------
import re as _re_gate

_KB_MATCHNAME_GATE_RE = _re_gate.compile(r'^(ADBE|CC|TC|RB|VC|BCC|E3D|BLEND)')
for _kb_kw, _kb_mn in list(_KB_RAW_MAP.items()):
    _kb_kw_l = _kb_kw.lower()
    if not isinstance(_kb_mn, str) or not _KB_MATCHNAME_GATE_RE.match(_kb_mn):
        continue
    if _kb_mn not in EFFECT_DISPLAY_NAMES:
        continue
    if _kb_kw_l in _HARDCODED_EFFECT_MAP:
        continue
    KEYWORD_TO_EFFECT_MAP.setdefault(_kb_kw_l, _kb_mn)


# ---------------------------------------------------------------------------
# 效果参数数据库 — 每个效果的常用参数、范围、默认值
# 用于 EffectReproducer 参数映射和范围验证
# ---------------------------------------------------------------------------
EFFECT_PARAMS_DB: dict[str, dict[str, Any]] = {
    "ADBE Gaussian Blur 2": {
        "params": {
            "Blurriness": {"type": "number", "min": 0, "max": 1000, "default": 10},
            "Blur Dimensions": {"type": "enum", "values": ["Horizontal & Vertical", "Horizontal Only", "Vertical Only"], "default": "Horizontal & Vertical"},
            "Repeat Edge Pixels": {"type": "boolean", "default": False},
        },
        "category": "blur",
    },
    "ADBE Camera Lens Blur": {
        "params": {
            "Blur Radius": {"type": "number", "min": 0, "max": 1000, "default": 50},
            "Iris Shape": {"type": "enum", "values": ["Pentagon", "Hexagon", "Septagon", "Octagon"], "default": "Hexagon"},
            "Iris Rotation": {"type": "number", "min": -180, "max": 180, "default": 0},
        },
        "category": "blur",
    },
    "ADBE Directional Blur": {
        "params": {
            "Direction": {"type": "number", "min": -360, "max": 360, "default": 0},
            "Blur Length": {"type": "number", "min": 0, "max": 1000, "default": 30},
        },
        "category": "blur",
    },
    "ADBE Glo2": {
        "params": {
            "Glow Threshold": {"type": "number", "min": 0, "max": 100, "default": 50},
            "Glow Radius": {"type": "number", "min": 0, "max": 300, "default": 15},
            "Glow Intensity": {"type": "number", "min": 0, "max": 5, "default": 1.0},
            "Glow Colors": {"type": "enum", "values": ["Original Colors", "A & B Colors"], "default": "A & B Colors"},
            "Color A": {"type": "color", "default": [1.0, 0.8, 0.5, 1.0]},
            "Color B": {"type": "color", "default": [1.0, 0.6, 0.3, 1.0]},
            "Composite Original": {"type": "enum", "values": ["On Top", "Behind", "Screen", "Over Original"], "default": "On Top"},
        },
        "category": "glow",
    },
    "RB Deep Glow": {
        "params": {
            "Threshold": {"type": "number", "min": 0, "max": 100, "default": 50},
            "Radius": {"type": "number", "min": 0, "max": 500, "default": 100},
            "Intensity": {"type": "number", "min": 0, "max": 10, "default": 1.0},
            "Linear Glow": {"type": "boolean", "default": False},
        },
        "category": "glow",
    },
    "VC Optical Flares": {
        "params": {
            "Flare Position": {"type": "point", "default": [50, 50]},
            "Brightness": {"type": "number", "min": 0, "max": 200, "default": 100},
            "Preset": {"type": "enum", "values": ["Default", "Sun", "Lens Ring", "Star"], "default": "Default"},
        },
        "category": "glow",
    },
    "VC SaberFX": {
        "params": {
            "Glow Color": {"type": "color", "default": [1.0, 0.5, 0.0, 1.0]},
            "Core Color": {"type": "color", "default": [1.0, 1.0, 1.0, 1.0]},
            "Core Width": {"type": "number", "min": 0, "max": 100, "default": 5},
            "Glow Size": {"type": "number", "min": 0, "max": 200, "default": 30},
            "Blade Speed": {"type": "number", "min": 0, "max": 100, "default": 50},
        },
        "category": "glow",
    },
    "TC Shine": {
        "params": {
            "Source Center": {"type": "point", "default": [50, 50]},
            "Ray Length": {"type": "number", "min": 0, "max": 200, "default": 100},
            "Ray Density": {"type": "number", "min": 0, "max": 10, "default": 2.0},
            "Ray Color": {"type": "color", "default": [1.0, 0.9, 0.7, 1.0]},
        },
        "category": "glow",
    },
    "TC Particular": {
        "params": {
            "Particles/Sec": {"type": "number", "min": 0, "max": 10000, "default": 100},
            "Longevity": {"type": "number", "min": 0, "max": 60, "default": 5},
            "Size": {"type": "number", "min": 0, "max": 100, "default": 3},
            "Emitter Type": {"type": "enum", "values": ["Point", "Line", "Grid", "Box", "Sphere"], "default": "Point"},
            "Physics Time": {"type": "number", "min": 0, "max": 10, "default": 1},
            "Gravity": {"type": "number", "min": -1000, "max": 1000, "default": 50},
            "Resistance": {"type": "number", "min": 0, "max": 10, "default": 0.5},
        },
        "category": "particle",
    },
    "TC Form": {
        "params": {
            "Surface Type": {"type": "enum", "values": ["Grid", "Sphere", "Cube", "OBJ"], "default": "Grid"},
            "Grid Size": {"type": "point", "default": [10, 10]},
            "Scale": {"type": "number", "min": 0, "max": 1000, "default": 100},
            "Displacement": {"type": "number", "min": 0, "max": 100, "default": 10},
        },
        "category": "particle",
    },
    "ADBE Turbulent Displace": {
        "params": {
            "Amount": {"type": "number", "min": 0, "max": 10000, "default": 100},
            "Size": {"type": "number", "min": 0.1, "max": 1000, "default": 50},
            "Complexity": {"type": "number", "min": 1, "max": 10, "default": 3},
            "Evolution": {"type": "number", "min": 0, "max": 360, "default": 0},
            "Offset": {"type": "point", "default": [0, 0]},
        },
        "category": "distort",
    },
    "ADBE Wave Warp": {
        "params": {
            "Wave Type": {"type": "enum", "values": ["Sine", "Square", "Triangle", "Sawtooth", "Noise"], "default": "Sine"},
            "Height": {"type": "number", "min": 0, "max": 1000, "default": 20},
            "Width": {"type": "number", "min": 0, "max": 1000, "default": 200},
            "Direction": {"type": "number", "min": -360, "max": 360, "default": 0},
            "Wave Speed": {"type": "number", "min": -10, "max": 10, "default": 1},
        },
        "category": "distort",
    },
    "ADBE Optics Compensation": {
        "params": {
            "Field of View": {"type": "number", "min": 1, "max": 179, "default": 50},
            "Reverse Distortion": {"type": "boolean", "default": False},
        },
        "category": "distort",
    },
    "ADBE Lumetri Color": {
        "params": {
            "Temperature": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Tint": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Exposure": {"type": "number", "min": -5, "max": 5, "default": 0},
            "Contrast": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Highlights": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Shadows": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Whites": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Blacks": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Saturation": {"type": "number", "min": -100, "max": 100, "default": 0},
        },
        "category": "color",
    },
    "ADBE Curves": {
        "params": {
            "RGB Curve": {"type": "curve", "default": [[0, 0], [255, 255]]},
            "Red Curve": {"type": "curve", "default": [[0, 0], [255, 255]]},
            "Green Curve": {"type": "curve", "default": [[0, 0], [255, 255]]},
            "Blue Curve": {"type": "curve", "default": [[0, 0], [255, 255]]},
        },
        "category": "color",
    },
    "ADBE HUE SATURATION": {
        "params": {
            "Channel Control": {"type": "enum", "values": ["Master", "Reds", "Yellows", "Greens", "Cyans", "Blues", "Magentas"], "default": "Master"},
            "Hue": {"type": "number", "min": -180, "max": 180, "default": 0},
            "Saturation": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Lightness": {"type": "number", "min": -100, "max": 100, "default": 0},
        },
        "category": "color",
    },
    "ADBE Tritone": {
        "params": {
            "Shadows": {"type": "color", "default": [0.0, 0.0, 0.2, 1.0]},
            "Midtones": {"type": "color", "default": [0.5, 0.5, 0.5, 1.0]},
            "Highlights": {"type": "color", "default": [1.0, 0.9, 0.7, 1.0]},
            "Blend": {"type": "number", "min": 0, "max": 100, "default": 50},
        },
        "category": "color",
    },
    "ADBE Color Balance": {
        "params": {
            "Red Shadow Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Green Shadow Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Blue Shadow Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Red Midtone Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Green Midtone Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Blue Midtone Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Red Highlight Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Green Highlight Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Blue Highlight Level": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Preserve Luminosity": {"type": "boolean", "default": True},
        },
        "category": "color",
    },
    "ADBE Brightness & Contrast 2": {
        "params": {
            "Brightness": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Contrast": {"type": "number", "min": -100, "max": 100, "default": 0},
        },
        "category": "color",
    },
    "ADBE Linear Wipe": {
        "params": {
            "Transition Completion": {"type": "number", "min": 0, "max": 100, "default": 0},
            "Wipe Angle": {"type": "number", "min": -360, "max": 360, "default": 0},
            "Feather": {"type": "number", "min": 0, "max": 500, "default": 50},
        },
        "category": "transition",
    },
    "ADBE Radial Wipe": {
        "params": {
            "Transition Completion": {"type": "number", "min": 0, "max": 100, "default": 0},
            "Center": {"type": "point", "default": [50, 50]},
            "Start Angle": {"type": "number", "min": -360, "max": 360, "default": 0},
            "Feather": {"type": "number", "min": 0, "max": 500, "default": 50},
        },
        "category": "transition",
    },
    "ADBE Fractal Noise": {
        "params": {
            "Noise Type": {"type": "enum", "values": ["Soft Linear", "Linear", "Blocky", "Spline", "Refined Spline", "Thread", "Clouds", "Turbulent Smooth", "Turbulent", "Basic", "Basic Grid"], "default": "Soft Linear"},
            "Contrast": {"type": "number", "min": 0, "max": 500, "default": 100},
            "Brightness": {"type": "number", "min": -100, "max": 100, "default": 0},
            "Scale": {"type": "point", "default": [100, 100]},
            "Complexity": {"type": "number", "min": 1, "max": 10, "default": 3},
            "Evolution": {"type": "number", "min": 0, "max": 360, "default": 0},
        },
        "category": "generate",
    },
    "ADBE Add Grain": {
        "params": {
            "Amount": {"type": "number", "min": 0, "max": 100, "default": 20},
            "Size": {"type": "number", "min": 0.01, "max": 10, "default": 0.5},
            "Noise Type": {"type": "enum", "values": ["Film", "Video"], "default": "Film"},
        },
        "category": "noise",
    },
    "ADBE Vignette": {
        "params": {
            "Amount": {"type": "number", "min": -100, "max": 100, "default": 30},
            "Feather": {"type": "number", "min": 0, "max": 100, "default": 50},
        },
        "category": "matte",
    },
    "ADBE Find Edges": {
        "params": {
            "Blend With Original": {"type": "number", "min": 0, "max": 100, "default": 100},
            "Reverse": {"type": "boolean", "default": False},
        },
        "category": "stylize",
    },
    "ADBE Roughen Edges": {
        "params": {
            "Border": {"type": "number", "min": 0, "max": 100, "default": 10},
            "Edge Type": {"type": "enum", "values": ["Roughen", "Blur", "Roughen Color"], "default": "Roughen"},
            "Scale": {"type": "number", "min": 0, "max": 1000, "default": 25},
        },
        "category": "stylize",
    },
}


# ---------------------------------------------------------------------------
# 效果分类索引
# ---------------------------------------------------------------------------
EFFECT_CATEGORIES: dict[str, list[str]] = {
    "blur": ["ADBE Gaussian Blur 2", "ADBE Camera Lens Blur", "ADBE Directional Blur",
             "CC Radial Fast Blur", "ADBE Box Blur", "ADBE Compound Blur"],
    "glow": ["ADBE Glo2", "ADBE Inner Glow", "ADBE Starglow", "RB Deep Glow",
             "BCC S_Glow", "VC Optical Flares", "VC SaberFX", "TC Shine"],
    "particle": ["ADBE Particle Playground", "TC Particular", "TC Form",
                 "CC Particle World", "CC Particle Systems II"],
    "distort": ["ADBE Turbulent Displace", "ADBE Wave Warp", "ADBE Mesh Warp",
                "ADBE Liquify", "ADBE Optics Compensation", "ADBE CC Power Pin"],
    "color": ["ADBE Curves", "ADBE Lumetri Color", "ADBE HUE SATURATION",
              "ADBE Tritone", "ADBE CC Toner", "ADBE ImportLUT",
              "ADBE Colorista", "ADBE Color Balance", "ADBE Brightness & Contrast 2"],
    "transition": ["ADBE Linear Wipe", "ADBE Radial Wipe", "ADBE Card Wipe", "CC Block Load"],
    "stylize": ["ADBE Find Edges", "ADBE Roughen Edges", "ADBE CC Glass"],
    "generate": ["ADBE CC Light Rays", "ADBE Fractal Noise", "ADBE Cell Pattern", "ADBE Ramp"],
    "text": ["ADBE Text Animator"],
    "camera_3d": ["ADBE Camera Tracker", "E3D", "ADBE C4D"],
    "noise": ["ADBE Add Grain", "ADBE Noise", "ADBE Fractal Noise"],
    "matte": ["ADBE Vignette"],
    "keying": ["ADBE Keylight", "ADBE Color Key"],
}


def get_effect_matchname(keyword: str) -> str:
    """根据关键词查询效果的 matchName。

    大小写不敏感。未找到返回空字符串。
    """
    return KEYWORD_TO_EFFECT_MAP.get(keyword.lower(), KEYWORD_TO_EFFECT_MAP.get(keyword, ""))


def get_all_effect_keywords() -> list:
    """返回所有已注册的效果关键词（用于自动补全等）。"""
    return list(KEYWORD_TO_EFFECT_MAP.keys())


def get_effect_params(match_name: str) -> dict[str, Any] | None:
    """根据 matchName 获取效果参数定义。

    Returns:
        参数字典或 None（未注册时）
    """
    return EFFECT_PARAMS_DB.get(match_name)


def get_effects_by_category(category: str) -> list[str]:
    """返回指定分类下的所有效果 matchName 列表。"""
    return EFFECT_CATEGORIES.get(category, [])


# ---------------------------------------------------------------------------
# 知识库集成：动态加载（模块导入时自动执行）
# ---------------------------------------------------------------------------
_KB_LOADED = False

# matchName 合法前缀规则
import re as _re

_VALID_MATCHNAME_RE = _re.compile(r'^(ADBE|CC|TC|RB|VC|BCC|E3D|BLEND)')

def _load_knowledge_base():
    """从知识库动态加载效果映射（带质量门控）

    质量门控规则：
    1. matchName 必须符合合法前缀规则，否则拒绝加载
    2. 与硬编码映射冲突时保留硬编码版本并记录 warning
    3. 加载后重新应用 _CRITICAL_MAPPINGS 保护
    """
    global _KB_LOADED
    if _KB_LOADED:
        return

    try:
        import sys
        sys.path.insert(0, str(__file__).rsplit("\\", 2)[0])
        try:
            from knowledge.kb_loader import KBLoader
        except ImportError:
            from kb_loader import KBLoader
        loader = KBLoader()
        kb_effect_map = loader.get_effect_map()

        added = 0
        rejected_format = 0
        rejected_conflict = 0
        for kw, mn in kb_effect_map.items():
            kw_lower = kw.lower()
            # 门控 1: matchName 格式校验；门控 1.5: 必须有显示名映射（测试契约）
            if not _VALID_MATCHNAME_RE.match(mn) or mn not in EFFECT_DISPLAY_NAMES:
                rejected_format += 1
                continue
            # 门控 2: 不与硬编码映射冲突
            if kw_lower in _HARDCODED_EFFECT_MAP:
                if _HARDCODED_EFFECT_MAP[kw_lower] != mn:
                    rejected_conflict += 1
                continue
            # 通过门控，加载
            if kw_lower not in KEYWORD_TO_EFFECT_MAP:
                KEYWORD_TO_EFFECT_MAP[kw_lower] = mn
                added += 1

        # 门控 3: 重新应用关键映射保护
        KEYWORD_TO_EFFECT_MAP.update(_CRITICAL_MAPPINGS)

        if rejected_format or rejected_conflict:
            print(f"[effect_registry] KB门控: 拒绝 {rejected_format} 格式非法 + {rejected_conflict} 冲突")
        print(f"[effect_registry] 知识库加载: 新增 {added} 个效果映射，总计 {len(KEYWORD_TO_EFFECT_MAP)}")
        _KB_LOADED = True
    except Exception as e:
        print(f"[effect_registry] 知识库加载失败(非致命): {e}")


_load_knowledge_base()
