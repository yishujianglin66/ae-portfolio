"""
effect_name_map.py
Phase 3 - 效果名 → matchName 映射库

用途：将决策树输出的 effect_name（人类可读名称）转换为
      AE 的 matchName（程序唯一标识）

数据来源：
  - 解析词汇表与推理决策树.md 第三章 效果识别词汇库
  - AE ExtendScript API 原子级映射手册.md 第一章 matchName 完整清单
  - 参数-效果原子级映射库.md

对齐 TS: compiler/src/phase3/effect-name-map.ts
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "EffectMapEntry",
    "EFFECT_MAP",
    "find_by_name",
    "find_by_match_name",
    "get_all_effect_names",
    "get_by_category",
    "get_stats",
]


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class EffectMapEntry:
    """效果名到 matchName 的映射条目"""
    match_name: str
    display_name: str
    category: str  # blur|glow|distort|color|particle|transition|text|3d|light
    source: str    # native|sapphire|boris|trapcode|vc|other
    aliases: list[str] = field(default_factory=list)
    param_map: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 完整的效果映射表（与决策树章节对应）
# ---------------------------------------------------------------------------

EFFECT_MAP: dict[str, EffectMapEntry] = {
    # ========== 模糊类（EI-001 ~ EI-099） ==========
    "Gaussian Blur": EffectMapEntry(
        match_name="ADBE Gaussian Blur 2",
        display_name="Gaussian Blur",
        category="blur",
        source="native",
        aliases=["高斯模糊", "Gaussian", "高斯"],
        param_map={"Blurriness": "Blurriness", "Blur Dimensions": "Blur Dimensions"},
    ),
    "Fast Box Blur": EffectMapEntry(
        match_name="ADBE Box Blur",
        display_name="Fast Box Blur",
        category="blur",
        source="native",
        aliases=["方块模糊", "Box Blur", "Fast Box"],
        param_map={"Blur Radius": "Blur Radius", "Iterations": "Iterations"},
    ),
    "Directional Blur": EffectMapEntry(
        match_name="ADBE Directional Blur",
        display_name="Directional Blur",
        category="blur",
        source="native",
        aliases=["方向模糊", "Directional", "运动模糊"],
        param_map={"Blur Length": "Blur Length", "Direction": "Direction"},
    ),
    "Camera Lens Blur": EffectMapEntry(
        match_name="ADBE Camera Lens Blur",
        display_name="Camera Lens Blur",
        category="blur",
        source="native",
        aliases=["镜头模糊", "Camera Lens", "光圈模糊"],
        param_map={
            "Blur Radius": "Blur Radius",
            "Iris Shape": "Iris Shape",
            "Highlight Gain": "Highlight Gain",
        },
    ),
    "Compound Blur": EffectMapEntry(
        match_name="ADBE Compound Blur",
        display_name="Compound Blur",
        category="blur",
        source="native",
        aliases=["混合模糊", "Compound", "亮度驱动模糊"],
        param_map={"Blur Layer": "Blur Layer", "Maximum Blur": "Maximum Blur"},
    ),
    "CC Radial Blur (Zoom)": EffectMapEntry(
        match_name="CC Radial Blur",
        display_name="CC Radial Blur - Zoom",
        category="blur",
        source="native",
        aliases=["放射模糊", "Radial Zoom", "CC Radial Zoom"],
        param_map={"Amount": "Amount", "Center": "Center", "Type": "Type"},
    ),
    "CC Radial Blur (Spin)": EffectMapEntry(
        match_name="CC Radial Blur",
        display_name="CC Radial Blur - Spin",
        category="blur",
        source="native",
        aliases=["旋转模糊", "Radial Spin", "CC Radial Spin"],
        param_map={"Amount": "Amount", "Center": "Center", "Type": "Type"},
    ),
    "CC Cross Blur": EffectMapEntry(
        match_name="CC Cross Blur",
        display_name="CC Cross Blur",
        category="blur",
        source="native",
        aliases=["十字模糊"],
        param_map={"Amount": "Amount"},
    ),
    "S_GaussianBlur (Sapphire)": EffectMapEntry(
        match_name="S_GaussianBlur",
        display_name="S_GaussianBlur",
        category="blur",
        source="sapphire",
        aliases=["Sapphire 高斯", "S_Gaussian"],
        param_map={"Blur": "Blur", "Blur V": "Blur V"},
    ),

    # ========== 发光类（EI-100 ~ EI-199） ==========
    "Glow": EffectMapEntry(
        match_name="ADBE Glo2",
        display_name="Glow",
        category="glow",
        source="native",
        aliases=["发光", "AE Glow", "AE原生发光"],
        param_map={
            "Glow Threshold": "Glow Threshold",
            "Glow Radius": "Glow Radius",
            "Glow Intensity": "Glow Intensity",
        },
    ),
    "Deep Glow": EffectMapEntry(
        match_name="ADBE Deep Glow",
        display_name="Deep Glow",
        category="glow",
        source="native",
        aliases=["深度发光", "DeepGlow"],
        param_map={
            "Glow Radius": "Glow Radius",
            "Glow Intensity": "Glow Intensity",
            "Glow Threshold": "Glow Threshold",
        },
    ),
    "Starglow": EffectMapEntry(
        match_name="ADBE Starglow",
        display_name="Starglow",
        category="glow",
        source="native",
        aliases=["星光", "星辉", "Star Glow"],
        param_map={
            "Threshold": "Threshold",
            "Streak Length": "Streak Length",
            "Boost": "Boost",
            "Colormap": "Colormap",
        },
    ),
    "S_Glow (Sapphire)": EffectMapEntry(
        match_name="S_Glow",
        display_name="S_Glow",
        category="glow",
        source="sapphire",
        aliases=["Sapphire Glow", "Sapphire发光"],
        param_map={
            "Threshold": "Threshold",
            "Width": "Width",
            "Brightness": "Brightness",
        },
    ),
    "Optical Flares": EffectMapEntry(
        match_name="ACP Optical Flares",
        display_name="Optical Flares",
        category="glow",
        source="vc",
        aliases=["光斑", "镜头光晕", "OF"],
        param_map={
            "Brightness": "Brightness",
            "Scale": "Scale",
            "Position": "Position XY",
            "Color": "Tint Color",
        },
    ),
    "Lens Flare": EffectMapEntry(
        match_name="ADBE Lens Flare",
        display_name="Lens Flare",
        category="glow",
        source="native",
        aliases=["镜头光晕", "AE Lens Flare"],
        param_map={
            "Flare Center": "Flare Center",
            "Flare Brightness": "Flare Brightness",
            "Lens Type": "Lens Type",
        },
    ),
    "Trapcode Shine": EffectMapEntry(
        match_name="TC Shine",
        display_name="Shine",
        category="glow",
        source="trapcode",
        aliases=["体积光", "光柱", "Shine"],
        param_map={
            "Ray Length": "Ray Length",
            "Boost Light": "Boost Light",
            "Shimmer Amount": "Shimmer Amount",
            "Source Point": "Source Point",
        },
    ),
    "CC Light Rays": EffectMapEntry(
        match_name="CC Light Rays",
        display_name="CC Light Rays",
        category="glow",
        source="native",
        aliases=["CC 光线", "CC LightRays"],
        param_map={
            "Intensity": "Intensity",
            "Radius": "Radius",
            "Warp": "Warp",
            "Center": "Center",
        },
    ),

    # ========== 扭曲类（EI-200 ~ EI-299） ==========
    "CC Bend It": EffectMapEntry(
        match_name="CC Bend It",
        display_name="CC Bend It",
        category="distort",
        source="native",
        aliases=["弯曲", "Bend"],
        param_map={"Bend": "Bend", "Start": "Start", "End": "End"},
    ),
    "Optics Compensation": EffectMapEntry(
        match_name="ADBE Optics Compensation",
        display_name="Optics Compensation",
        category="distort",
        source="native",
        aliases=["镜头畸变", "Optics"],
        param_map={
            "Field of View (FOV)": "Field of View (FOV)",
            "Reverse Lens Distortion": "Reverse Lens Distortion",
        },
    ),
    "Bezier Warp": EffectMapEntry(
        match_name="ADBE Bezier Warp",
        display_name="Bezier Warp",
        category="distort",
        source="native",
        aliases=["贝塞尔扭曲", "Bezier"],
        param_map={"Top Left Vertex": "Top Left Vertex"},
    ),
    "Mesh Warp": EffectMapEntry(
        match_name="ADBE Mesh Warp",
        display_name="Mesh Warp",
        category="distort",
        source="native",
        aliases=["网格扭曲", "Mesh"],
        param_map={"Rows": "Rows", "Columns": "Columns"},
    ),
    "S_Distort (Sapphire)": EffectMapEntry(
        match_name="S_Distort",
        display_name="S_Distort",
        category="distort",
        source="sapphire",
        aliases=["Sapphire Distort"],
        param_map={"Distort": "Distort"},
    ),
    "CC Page Turn": EffectMapEntry(
        match_name="CC Page Turn",
        display_name="CC Page Turn",
        category="distort",
        source="native",
        aliases=["翻页", "Page Turn"],
        param_map={"Fold Position": "Fold Position", "Angle": "Angle"},
    ),

    # ========== 色彩类（EI-300 ~ EI-399） ==========
    "Curves": EffectMapEntry(
        match_name="ADBE CurvesCustom",
        display_name="Curves",
        category="color",
        source="native",
        aliases=["曲线", "Color Curves"],
        param_map={"Channel": "Channel"},
    ),
    "Hue/Saturation": EffectMapEntry(
        match_name="ADBE HUE SATURATION",
        display_name="Hue/Saturation",
        category="color",
        source="native",
        aliases=["色相/饱和度", "Hue Sat", "色相饱和"],
        param_map={
            "Master Hue": "Master Hue",
            "Master Saturation": "Master Saturation",
            "Master Lightness": "Master Lightness",
        },
    ),
    "Vibrance": EffectMapEntry(
        match_name="ADBE Vibrance",
        display_name="Vibrance",
        category="color",
        source="native",
        aliases=["自然饱和度", "Vibrance"],
        param_map={"Vibrance": "Vibrance", "Saturation": "Saturation"},
    ),
    "Color Balance": EffectMapEntry(
        match_name="ADBE Color Balance",
        display_name="Color Balance",
        category="color",
        source="native",
        aliases=["色彩平衡", "Color Balance"],
        param_map={
            "Shadow Red Balance": "Shadow Red Balance",
            "Midtone Red Balance": "Midtone Red Balance",
            "Hilight Red Balance": "Hilight Red Balance",
        },
    ),
    "Brightness & Contrast": EffectMapEntry(
        match_name="ADBE Brightness & Contrast 2",
        display_name="Brightness & Contrast",
        category="color",
        source="native",
        aliases=["亮度对比度", "Brightness Contrast"],
        param_map={"Brightness": "Brightness", "Contrast": "Contrast"},
    ),
    "S_ColorBalance (Sapphire)": EffectMapEntry(
        match_name="S_ColorBalance",
        display_name="S_ColorBalance",
        category="color",
        source="sapphire",
        aliases=["Sapphire色彩平衡"],
        param_map={"Red": "Red", "Green": "Green", "Blue": "Blue"},
    ),

    # ========== 粒子类（EI-400 ~ EI-499） ==========
    "Particular": EffectMapEntry(
        match_name="ACP Particular",
        display_name="Particular",
        category="particle",
        source="trapcode",
        aliases=["粒子", "Trapcode Particular", "TC Particular"],
        param_map={
            "Emitter X": "Emitter X",
            "Emitter Y": "Emitter Y",
            "Emitter Z": "Emitter Z",
            "Particles/sec": "Particles/sec",
            "Velocity": "Velocity",
            "Life": "Life",
            "Size": "Size",
            "Color": "Color",
        },
    ),
    "CC Particle World": EffectMapEntry(
        match_name="CC Particle World",
        display_name="CC Particle World",
        category="particle",
        source="native",
        aliases=["CC粒子", "ParticleWorld"],
        param_map={
            "Producer X": "Producer X",
            "Producer Y": "Producer Y",
            "Producer Z": "Producer Z",
            "Velocity": "Velocity",
        },
    ),
    "CC Star Burst": EffectMapEntry(
        match_name="CC Star Burst",
        display_name="CC Star Burst",
        category="particle",
        source="native",
        aliases=["星爆", "StarBurst"],
        param_map={"Speed": "Speed", "Phase": "Phase"},
    ),
    "Plexus": EffectMapEntry(
        match_name="ACP Plexus",
        display_name="Plexus",
        category="particle",
        source="trapcode",
        aliases=["网状粒子", "Plexus 3D"],
        param_map={"Points": "Points"},
    ),

    # ========== 转场类（EI-500 ~ EI-599） ==========
    "CC Glass Wipe": EffectMapEntry(
        match_name="CC Glass Wipe",
        display_name="CC Glass Wipe",
        category="transition",
        source="native",
        aliases=["玻璃擦除", "Glass Wipe"],
        param_map={"Transition Completion": "Transition Completion"},
    ),
    "CC Grid Wipe": EffectMapEntry(
        match_name="CC Grid Wipe",
        display_name="CC Grid Wipe",
        category="transition",
        source="native",
        aliases=["网格擦除", "Grid Wipe"],
        param_map={"Transition Completion": "Transition Completion"},
    ),
    "Linear Wipe": EffectMapEntry(
        match_name="ADBE Linear Wipe",
        display_name="Linear Wipe",
        category="transition",
        source="native",
        aliases=["线性擦除", "Linear"],
        param_map={
            "Transition Completion": "Transition Completion",
            "Wipe Angle": "Wipe Angle",
            "Feather": "Feather",
        },
    ),
    "Venetian Blinds": EffectMapEntry(
        match_name="ADBE Venetian Blinds",
        display_name="Venetian Blinds",
        category="transition",
        source="native",
        aliases=["百叶窗", "Venetian"],
        param_map={
            "Transition Completion": "Transition Completion",
            "Direction": "Direction",
            "Width": "Width",
            "Feather": "Feather",
        },
    ),

    # ========== 文字类（EI-600 ~ EI-699） ==========
    "CC Typewriter": EffectMapEntry(
        match_name="CC Typewriter",
        display_name="CC Typewriter",
        category="text",
        source="native",
        aliases=["打字机", "Typewriter"],
        param_map={},
    ),
    "S_AnimTitle (Sapphire)": EffectMapEntry(
        match_name="S_AnimTitle",
        display_name="S_AnimTitle",
        category="text",
        source="sapphire",
        aliases=["Sapphire动画标题"],
        param_map={},
    ),

    # ========== 3D 类 ==========
    "Element 3D": EffectMapEntry(
        match_name="ACP Element",
        display_name="Element 3D",
        category="3d",
        source="vc",
        aliases=["E3D", "3D元素"],
        param_map={
            "Group 1 Model": "Group 1 Model",
            "Position": "Group 1 Position XY",
            "Scale": "Group 1 Scale",
        },
    ),

    # ========== 通用辅助效果 ==========
    "Vignette": EffectMapEntry(
        match_name="ADBE Vignette",
        display_name="Vignette",
        category="color",
        source="native",
        aliases=["暗角", "晕影"],
        param_map={"Amount": "Amount", "Softness": "Softness"},
    ),
    "Shadow": EffectMapEntry(
        match_name="ADBE Drop Shadow",
        display_name="Drop Shadow",
        category="color",
        source="native",
        aliases=["投影", "Drop Shadow"],
        param_map={
            "Shadow Color": "Shadow Color",
            "Opacity": "Opacity",
            "Direction": "Direction",
            "Distance": "Distance",
            "Softness": "Softness",
        },
    ),
}


# ---------------------------------------------------------------------------
# 查询 API
# ---------------------------------------------------------------------------

def find_by_name(name: str) -> EffectMapEntry | None:
    """通过显示名查找效果映射

    Args:
        name: 效果显示名（如 "Gaussian Blur"）

    Returns:
        EffectMapEntry 或 None
    """
    if not name:
        return None
    # 直接查找
    if name in EFFECT_MAP:
        return EFFECT_MAP[name]
    # 在别名中查找（不区分大小写）
    lower_name = name.lower()
    for entry in EFFECT_MAP.values():
        if entry.display_name.lower() == lower_name:
            return entry
        for alias in entry.aliases:
            if alias.lower() == lower_name:
                return entry
    return None


def find_by_match_name(match_name: str) -> EffectMapEntry | None:
    """通过 matchName 查找效果映射"""
    if not match_name:
        return None
    for entry in EFFECT_MAP.values():
        if entry.match_name == match_name:
            return entry
    return None


def get_all_effect_names() -> list[str]:
    """获取所有效果名列表"""
    return list(EFFECT_MAP.keys())


def get_by_category(category: str) -> list[EffectMapEntry]:
    """获取指定类别的所有效果"""
    return [entry for entry in EFFECT_MAP.values() if entry.category == category]


def get_stats() -> dict[str, Any]:
    """统计信息"""
    by_category: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for entry in EFFECT_MAP.values():
        by_category[entry.category] = by_category.get(entry.category, 0) + 1
        by_source[entry.source] = by_source.get(entry.source, 0) + 1
    return {
        "total": len(EFFECT_MAP),
        "byCategory": by_category,
        "bySource": by_source,
    }


# ---------------------------------------------------------------------------
# 模块自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    stats = get_stats()
    print(f"[effect_name_map] 总效果数: {stats['total']}")
    print(f"  按类别: {stats['byCategory']}")
    print(f"  按来源: {stats['bySource']}")
    # 抽样验证
    glow = find_by_name("Glow")
    print(f"\n抽样查找 'Glow': {glow.match_name if glow else 'NOT FOUND'}")
    cn_glow = find_by_name("发光")
    print(f"抽样查找 '发光': {cn_glow.match_name if cn_glow else 'NOT FOUND'}")
    by_match = find_by_match_name("ADBE Gaussian Blur 2")
    print(f"matchName 查找 'ADBE Gaussian Blur 2': "
          f"{by_match.display_name if by_match else 'NOT FOUND'}")
    blur_list = get_by_category("blur")
    print(f"模糊类效果数: {len(blur_list)}")
