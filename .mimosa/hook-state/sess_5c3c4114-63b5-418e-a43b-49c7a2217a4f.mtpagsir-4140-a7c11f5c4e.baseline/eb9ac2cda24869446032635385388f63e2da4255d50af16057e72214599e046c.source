"""
DaVinci Resolve Color 页面内置调色预设库。

提供 6+ 套专业调色预设，覆盖电影感、复古、高调、暗调、音乐 MV、
黑白经典、暖色肖像、冷色科幻等主流风格。所有预设均采用
``ColorGradingPreset`` 数据结构，可直接用于 ``ColorGrader.apply_preset``。

可通过以下方式访问::

    from integrations.color_presets import BUILTIN_PRESETS, get_preset, list_presets

预设既可在 Python 内存中使用，也支持落盘为 JSON 便于在团队中分发。
JSON 落盘位置默认为本 ``__init__.py`` 同级目录的 ``*.json`` 文件，
``load_preset_from_file`` / ``save_preset_to_file`` 会自动按预设名匹配。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from integrations.davinci_color_grading import (
    ColorGradingPreset,
    ColorWheelValues,
)


# 预设库所在目录
PRESETS_DIR: Path = Path(__file__).resolve().parent


# ============================================================================
# 内置预设库（BUILTIN_PRESETS）
# ============================================================================

BUILTIN_PRESETS: Dict[str, ColorGradingPreset] = {
    "cinematic_teal_orange": ColorGradingPreset(
        name="Cinematic Teal & Orange",
        description="经典电影感青橙调色，阴影偏青、高光偏暖，对应好莱坞主流调色。",
        lift=ColorWheelValues(red=-0.02, green=0.01, blue=0.04, master=-0.02),
        gamma=ColorWheelValues(red=0.05, green=-0.01, blue=-0.04),
        gain=ColorWheelValues(red=0.08, green=0.02, blue=-0.05, master=0.02),
        offset=ColorWheelValues(red=0.0, green=0.0, blue=0.0),
        saturation=1.15,
        contrast=1.10,
        pivot=0.435,
        highlight_saturation=1.10,
        shadow_saturation=1.20,
        blend_opacity=1.0,
        tags=["cinematic", "warm-cool", "teal-orange", "hollywood", "popular"],
    ),
    "vintage_film": ColorGradingPreset(
        name="Vintage Film",
        description="复古胶片感，整体偏暖黄、阴影偏褐、对比柔和，模拟 70 年代胶片。",
        lift=ColorWheelValues(red=0.04, green=0.02, blue=-0.01, master=0.02),
        gamma=ColorWheelValues(red=0.02, green=0.0, blue=-0.03),
        gain=ColorWheelValues(red=0.05, green=0.03, blue=-0.02, master=0.01),
        offset=ColorWheelValues(red=0.01, green=0.0, blue=-0.01),
        saturation=0.85,
        contrast=0.95,
        pivot=0.45,
        highlight_saturation=0.80,
        shadow_saturation=1.10,
        blend_opacity=1.0,
        tags=["vintage", "film", "warm", "retro", "70s"],
    ),
    "high_key_bright": ColorGradingPreset(
        name="High Key Bright",
        description="高调明亮风格，提升整体曝光、降低对比、保持中性色调，适合时尚/美容。",
        lift=ColorWheelValues(red=0.03, green=0.03, blue=0.03, master=0.03),
        gamma=ColorWheelValues(red=0.02, green=0.02, blue=0.02),
        gain=ColorWheelValues(red=0.04, green=0.04, blue=0.04, master=0.03),
        offset=ColorWheelValues(red=0.0, green=0.0, blue=0.0),
        saturation=1.05,
        contrast=0.90,
        pivot=0.40,
        highlight_saturation=1.0,
        shadow_saturation=1.0,
        blend_opacity=1.0,
        tags=["high-key", "bright", "fashion", "beauty", "clean"],
    ),
    "low_key_dark": ColorGradingPreset(
        name="Low Key Dark",
        description="低调暗调风格，压低阴影、突出主体、保留高光细节，适合悬疑/惊悚。",
        lift=ColorWheelValues(red=-0.05, green=-0.04, blue=-0.02, master=-0.05),
        gamma=ColorWheelValues(red=-0.02, green=-0.01, blue=0.01),
        gain=ColorWheelValues(red=0.02, green=0.01, blue=-0.01),
        offset=ColorWheelValues(red=-0.01, green=-0.01, blue=0.0),
        saturation=0.90,
        contrast=1.25,
        pivot=0.50,
        highlight_saturation=0.85,
        shadow_saturation=1.30,
        blend_opacity=1.0,
        tags=["low-key", "dark", "thriller", "noir", "moody"],
    ),
    "music_video_punch": ColorGradingPreset(
        name="Music Video Punch",
        description="音乐 MV 高对比冲击感，饱和度高、对比强烈、色彩分离明显。",
        lift=ColorWheelValues(red=-0.03, green=0.02, blue=0.03, master=-0.02),
        gamma=ColorWheelValues(red=0.04, green=0.0, blue=-0.04),
        gain=ColorWheelValues(red=0.06, green=0.04, blue=-0.03, master=0.03),
        offset=ColorWheelValues(red=0.0, green=0.0, blue=0.0),
        saturation=1.30,
        contrast=1.20,
        pivot=0.45,
        highlight_saturation=1.15,
        shadow_saturation=1.25,
        blend_opacity=1.0,
        tags=["music-video", "punch", "high-contrast", "vibrant", "pop"],
    ),
    "black_and_white_classic": ColorGradingPreset(
        name="Black & White Classic",
        description="黑白经典风格，去除饱和、提升对比、保留丰富灰阶过渡，致敬经典胶片。",
        lift=ColorWheelValues(red=0.0, green=0.0, blue=0.0, master=0.0),
        gamma=ColorWheelValues(red=0.0, green=0.0, blue=0.0),
        gain=ColorWheelValues(red=0.0, green=0.0, blue=0.0, master=0.0),
        offset=ColorWheelValues(red=0.0, green=0.0, blue=0.0),
        saturation=0.0,
        contrast=1.15,
        pivot=0.435,
        highlight_saturation=1.0,
        shadow_saturation=1.0,
        blend_opacity=1.0,
        tags=["black-and-white", "bw", "classic", "monochrome", "noir"],
    ),
    "warm_portrait": ColorGradingPreset(
        name="Warm Portrait",
        description="暖色肖像，皮肤友好，暖色调高光、柔和阴影，适合人像写真。",
        lift=ColorWheelValues(red=0.03, green=0.01, blue=-0.01, master=0.02),
        gamma=ColorWheelValues(red=0.04, green=0.02, blue=0.0),
        gain=ColorWheelValues(red=0.05, green=0.03, blue=0.0, master=0.02),
        offset=ColorWheelValues(red=0.01, green=0.0, blue=0.0),
        saturation=1.05,
        contrast=1.0,
        pivot=0.42,
        highlight_saturation=1.05,
        shadow_saturation=1.10,
        blend_opacity=1.0,
        tags=["portrait", "warm", "skin", "soft", "wedding"],
    ),
    "cold_scifi": ColorGradingPreset(
        name="Cold Sci-Fi",
        description="冷色科幻，整体偏青蓝、对比强烈、饱和度略降，未来感强烈。",
        lift=ColorWheelValues(red=-0.02, green=0.0, blue=0.04, master=-0.02),
        gamma=ColorWheelValues(red=-0.03, green=0.0, blue=0.04),
        gain=ColorWheelValues(red=-0.02, green=0.02, blue=0.06, master=0.02),
        offset=ColorWheelValues(red=0.0, green=0.0, blue=0.01),
        saturation=0.90,
        contrast=1.15,
        pivot=0.45,
        highlight_saturation=0.85,
        shadow_saturation=1.20,
        blend_opacity=1.0,
        tags=["sci-fi", "cold", "blue", "future", "tech"],
    ),
}


# ============================================================================
# 访问器函数
# ============================================================================

def get_preset(name: str) -> Optional[ColorGradingPreset]:
    """按预设名获取内存中的内置预设。

    Args:
        name: 预设键名（见 :data:`BUILTIN_PRESETS` 的键）。

    Returns:
        命中的 ``ColorGradingPreset``，未命中则返回 None。
    """
    return BUILTIN_PRESETS.get(name)


def list_preset_names() -> List[str]:
    """返回所有内置预设的键名列表。"""
    return list(BUILTIN_PRESETS.keys())


def list_presets() -> List[ColorGradingPreset]:
    """返回所有内置预设对象列表。"""
    return list(BUILTIN_PRESETS.values())


def presets_by_tag(tag: str) -> List[ColorGradingPreset]:
    """按标签筛选预设。

    Args:
        tag: 标签名（如 "cinematic"、"bw"），大小写不敏感。

    Returns:
        命中标签的预设列表。
    """
    tag_lower = tag.lower()
    return [p for p in BUILTIN_PRESETS.values() if any(t.lower() == tag_lower for t in p.tags)]


def get_preset_file_path(name: str) -> Optional[Path]:
    """获取预设对应 JSON 落盘文件的预期路径（不要求文件已存在）。"""
    candidate = PRESETS_DIR / f"{name}.json"
    return candidate if candidate.exists() else None


def load_preset_from_file(file_path: str | Path) -> ColorGradingPreset:
    """从 JSON 文件加载预设。"""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Preset file not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        data: Dict[str, Any] = json.load(f)
    return ColorGradingPreset.from_dict(data)


def save_preset_to_file(preset: ColorGradingPreset, file_path: str | Path) -> Path:
    """将预设保存为 JSON 文件。返回写入路径。"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)
    return file_path


def export_all_builtin_presets(target_dir: str | Path | None = None) -> List[Path]:
    """将所有内置预设导出为 JSON 文件。返回写入路径列表。"""
    target = Path(target_dir) if target_dir else PRESETS_DIR
    target.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for key, preset in BUILTIN_PRESETS.items():
        path = target / f"{key}.json"
        save_preset_to_file(preset, path)
        written.append(path)
    return written


__all__ = [
    "BUILTIN_PRESETS",
    "PRESETS_DIR",
    "get_preset",
    "list_preset_names",
    "list_presets",
    "presets_by_tag",
    "get_preset_file_path",
    "load_preset_from_file",
    "save_preset_to_file",
    "export_all_builtin_presets",
]
