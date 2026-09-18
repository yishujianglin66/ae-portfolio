"""
aep_analyzer/preset_generator.py - 逆向效果链 → JSX 预设自动生成

将 KnowledgeExtractor 提取的效果链模式转化为可执行的 JSX 预设模板，
直接兼容 text_animation_presets.json 的格式规范。

流水线：AEP 二进制扫描 → 效果链提取 → 参数推断 → JSX 模板生成 → 预设 JSON 入库
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# 效果参数知识库：从实机验证的 AE 效果参数范围（二进制提取 + 文档固化）
# ---------------------------------------------------------------------------

EFFECT_PARAM_KB: dict[str, dict[str, Any]] = {
    "ADBE Fractal Noise": {
        "display_name": "Fractal Noise",
        "params": {
            "noise_type": {"matchName": "ADBE Fractal Noise-0002", "default": 1,
                           "range": [1, 6], "desc": "Noise Type (1=Basic,3=Spline,6=Turbulent Smooth)"},
            "fractal_type": {"matchName": "ADBE Fractal Noise-0001", "default": 3,
                             "range": [1, 12], "desc": "Fractal Type (3=Dynamic)"},
            "size": {"matchName": "ADBE Fractal Noise-0005", "default": 25,
                     "range": [5, 50], "desc": "Size (纹理大小)"},
            "complexity": {"matchName": "ADBE Fractal Noise-0008", "default": 3,
                           "range": [1, 6], "desc": "Complexity (细节层次)"},
            "sub_influence": {"matchName": "ADBE Fractal Noise-0012", "default": 0.5,
                              "range": [0.3, 0.8], "desc": "Sub Influence"},
            "brightness": {"matchName": "ADBE Fractal Noise-0006", "default": 0,
                           "range": [-50, 50], "desc": "Brightness"},
            "evolution": {"matchName": "ADBE Fractal Noise-0007", "default": 0,
                          "range": [0, 360], "desc": "Evolution (度，可关键帧)"},
        },
        "blend_mode_default": "Overlay",
    },
    "ADBE Glo2": {
        "display_name": "Glow",
        "params": {
            "threshold": {"matchName": "ADBE Glo2-0001", "default": 50,
                          "range": [30, 70], "desc": "Glow Threshold (%)", "unit": "%"},
            "radius": {"matchName": "ADBE Glo2-0002", "default": 30,
                       "range": [10, 50], "desc": "Glow Radius"},
            "color_a": {"matchName": "ADBE Glo2-0004", "default": [0, 180, 255],
                        "desc": "Glow Colors A (青)"},
            "color_b": {"matchName": "ADBE Glo2-0005", "default": [255, 0, 180],
                        "desc": "Glow Colors B (品红)"},
            "blend_mode": {"matchName": "ADBE Glo2-0007", "default": 2,
                           "range": [1, 5], "desc": "Blend Mode (2=Screen,3=Add)"},
        },
    },
    "ADBE Exposure2": {
        "display_name": "Exposure",
        "params": {
            "exposure": {"matchName": "ADBE Exposure2-0002", "default": 0.5,
                         "range": [-3.0, 3.0], "desc": "Exposure (stops)"},
            "offset": {"matchName": "ADBE Exposure2-0003", "default": 0,
                       "range": [-1.0, 1.0], "desc": "Offset"},
            "gamma": {"matchName": "ADBE Exposure2-0004", "default": 1.0,
                      "range": [0.1, 5.0], "desc": "Gamma Correction"},
        },
    },
    "ADBE Tint": {
        "display_name": "Tint",
        "params": {
            "black_to": {"matchName": "ADBE Tint-0001", "default": [0, 0, 0],
                         "desc": "Map Black To"},
            "white_to": {"matchName": "ADBE Tint-0002", "default": [255, 255, 255],
                         "desc": "Map White To"},
            "amount": {"matchName": "ADBE Tint-0003", "default": 100,
                       "range": [0, 100], "desc": "Amount to Tint (%)", "unit": "%"},
        },
    },
    "ADBE Turbulent Displace": {
        "display_name": "Turbulent Displace",
        "params": {
            "amount": {"matchName": "ADBE Turbulent Displace-0001", "default": 20,
                       "range": [0, 100], "desc": "Amount"},
            "size": {"matchName": "ADBE Turbulent Displace-0002", "default": 20,
                     "range": [1, 200], "desc": "Size"},
            "complexity": {"matchName": "ADBE Turbulent Displace-0005", "default": 1,
                           "range": [1, 10], "desc": "Complexity"},
            "evolution": {"matchName": "ADBE Turbulent Displace-0003", "default": 0,
                          "range": [0, 360], "desc": "Evolution (度)"},
        },
    },
    "ADBE CM CrackedTiles": {
        "display_name": "Cracked Tiles",
        "params": {
            "crack_edge_width": {"matchName": "ADBE CM CrackedTiles-0001", "default": 10,
                                 "range": [0, 100], "desc": "Crack Edge Width"},
            "tile_edge_width": {"matchName": "ADBE CM CrackedTiles-0002", "default": 10,
                                "range": [0, 100], "desc": "Tile Edge Width"},
            "tile_depth": {"matchName": "ADBE CM CrackedTiles-0003", "default": 0,
                           "range": [-100, 100], "desc": "Tile Depth"},
        },
    },
    "ADBE Noise": {
        "display_name": "Noise",
        "params": {
            "amount": {"matchName": "ADBE Noise-0001", "default": 10,
                       "range": [0, 100], "desc": "Amount of Noise (%)", "unit": "%"},
            "use_color": {"matchName": "ADBE Noise-0002", "default": False,
                          "desc": "Use Color Noise"},
        },
    },
    "ADBE BoxBlur2": {
        "display_name": "Box Blur",
        "params": {
            "blurriness": {"matchName": "ADBE BoxBlur2-0001", "default": 5,
                           "range": [0, 100], "desc": "Blurriness"},
            "repeat_edge": {"matchName": "ADBE BoxBlur2-0002", "default": True,
                            "desc": "Repeat Edge Pixels"},
        },
    },
    "CSL BlackAndWhite": {
        "display_name": "Black & White (Color Suite)",
        "params": {},
    },
    "ADBE PhotoFilter": {
        "display_name": "Photo Filter",
        "params": {
            "color": {"matchName": "ADBE PhotoFilter-0001", "default": [255, 200, 100],
                      "desc": "Filter Color"},
            "density": {"matchName": "ADBE PhotoFilter-0002", "default": 25,
                        "range": [0, 100], "desc": "Density (%)", "unit": "%"},
            "preserve_lum": {"matchName": "ADBE PhotoFilter-0003", "default": True,
                             "desc": "Preserve Luminosity"},
        },
    },
    "ADBE Lumetri": {
        "display_name": "Lumetri Color",
        "params": {
            "exposure": {"matchName": "ADBE Lumetri-0001", "default": 0,
                         "range": [-4.0, 4.0], "desc": "Basic Correction > Exposure"},
            "contrast": {"matchName": "ADBE Lumetri-0002", "default": 0,
                         "range": [-100, 100], "desc": "Basic Correction > Contrast"},
            "saturation": {"matchName": "ADBE Lumetri-0004", "default": 0,
                           "range": [-100, 100], "desc": "Basic Correction > Saturation"},
        },
        "is_lumetri": True,
    },
}

# ---------------------------------------------------------------------------
# 风格模式配方（从 9 个 AEP 工程逆向提取的实机验证配方）
# ---------------------------------------------------------------------------

STYLE_RECIPES: dict[str, dict[str, Any]] = {
    "cyberpunk_neon": {
        "display_name": "赛博朋克/霓虹风格",
        "description": "Exposure + Lumetri调色 + Fractal Noise纹理 + Glow发光 + Turbulent Displace扭曲",
        "tags": ["赛博朋克", "霓虹", "暗调", "发光", "MV"],
        "effect_chain": [
            {"matchName": "ADBE Exposure2", "param_overrides": {"exposure": 0.8}},
            {"matchName": "ADBE Lumetri", "param_overrides": {"contrast": 20, "saturation": 15}},
            {"matchName": "ADBE Fractal Noise", "param_overrides": {"size": 30, "complexity": 4, "brightness": -20},
             "blend_mode": "Overlay", "opacity": 35},
            {"matchName": "ADBE Glo2", "param_overrides": {"threshold": 40, "radius": 35,
             "color_a": [0, 200, 255], "color_b": [255, 0, 200]}},
            {"matchName": "ADBE Turbulent Displace", "param_overrides": {"amount": 15, "size": 25}},
        ],
        "applies_to_layer": "any",
    },
    "anime_mashup": {
        "display_name": "动漫混剪风格",
        "description": "CrackedTiles碎裂转场 + Mocha跟踪 + Sapphire纹理叠加",
        "tags": ["动漫", "混剪", "转场", "跟踪"],
        "effect_chain": [
            {"matchName": "ADBE CM CrackedTiles", "param_overrides": {"crack_edge_width": 15, "tile_depth": 20}},
            {"matchName": "ADBE Fractal Noise", "param_overrides": {"size": 15, "complexity": 2},
             "blend_mode": "Overlay", "opacity": 25},
            {"matchName": "ADBE Noise", "param_overrides": {"amount": 8}},
            {"matchName": "ADBE Glo2", "param_overrides": {"threshold": 55, "radius": 20}},
        ],
        "applies_to_layer": "any",
    },
    "retro_film": {
        "display_name": "复古胶片风格",
        "description": "黑白 + 模糊 + 噪点 + 色调滤镜 + 柔光",
        "tags": ["复古", "胶片", "黑白", "噪点", "怀旧"],
        "effect_chain": [
            {"matchName": "CSL BlackAndWhite"},
            {"matchName": "ADBE BoxBlur2", "param_overrides": {"blurriness": 3}},
            {"matchName": "ADBE Noise", "param_overrides": {"amount": 12}},
            {"matchName": "ADBE PhotoFilter", "param_overrides": {"color": [255, 180, 80], "density": 30}},
            {"matchName": "ADBE Glo2", "param_overrides": {"threshold": 60, "radius": 15}},
        ],
        "applies_to_layer": "any",
    },
    "fresh_clean": {
        "display_name": "清新文艺风格",
        "description": "柔和曝光 + 轻微噪点 + 暖色调 + 柔光",
        "tags": ["清新", "文艺", "柔和", "暖色"],
        "effect_chain": [
            {"matchName": "ADBE Exposure2", "param_overrides": {"exposure": 0.3, "gamma": 1.1}},
            {"matchName": "ADBE Noise", "param_overrides": {"amount": 5}},
            {"matchName": "ADBE PhotoFilter", "param_overrides": {"color": [255, 220, 180], "density": 15}},
            {"matchName": "ADBE Glo2", "param_overrides": {"threshold": 65, "radius": 12}},
        ],
        "applies_to_layer": "any",
    },
    "audio_reactive": {
        "display_name": "音频响应风格",
        "description": "Audio Spectrum频谱 + LED点阵 + 光学变速",
        "tags": ["音频响应", "频谱", "可视化", "LED"],
        "effect_chain": [
            {"matchName": "ADBE Audiospectrum"},
        ],
        "applies_to_layer": "any",
        "requires_audio_layer": True,
    },
}


# ---------------------------------------------------------------------------
# JSX 模板生成器
# ---------------------------------------------------------------------------

def _js_value(val: Any) -> str:
    """将 Python 值转为 JSX 字面量字符串。"""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, (list, tuple)):
        return "[" + ", ".join(_js_value(v) for v in val) + "]"
    return f"'{val}'"


def _generate_effect_jsx(effect_def: dict[str, Any], layer_var: str = "L") -> str:
    """为单个效果生成 JSX 添加+设参代码。"""
    match_name = effect_def["matchName"]
    overrides = effect_def.get("param_overrides", {})
    kb = EFFECT_PARAM_KB.get(match_name, {})
    display = kb.get("display_name", match_name.split(" ")[-1] if " " in match_name else match_name)
    params = kb.get("params", {})

    lines: list[str] = []
    lines.append(f"// Effect: {display} ({match_name})")
    lines.append(f"var _ef = {layer_var}.property('ADBE Effect Parade').addProperty('{match_name}');")

    for param_key, override_val in overrides.items():
        param_def = params.get(param_key, {})
        mn = param_def.get("matchName", "")
        if mn:
            lines.append(f"_ef.property('{mn}').setValue({_js_value(override_val)});")

    # Blend mode (for overlay-style effects)
    blend_mode = effect_def.get("blend_mode")
    if blend_mode:
        bm_map = {"Normal": 0, "Screen": 5, "Overlay": 22, "Add": 1}
        bm_val = bm_map.get(blend_mode, 0)
        lines.append(f"{layer_var}.blendingMode = {bm_val}; // {blend_mode}")

    # Opacity
    opacity = effect_def.get("opacity")
    if opacity is not None:
        lines.append(f"{layer_var}.opacity.setValue({opacity});")

    return "\n".join(lines)


def generate_style_preset_jsx(
    recipe_key: str,
    target_layer_name: str = "{{targetLayerName}}",
) -> str:
    """根据风格配方生成完整 JSX 预设模板（IIFE 包装）。

    Args:
        recipe_key: STYLE_RECIPES 中的键名
        target_layer_name: 目标图层名占位符

    Returns:
        完整 JSX 代码字符串
    """
    recipe = STYLE_RECIPES.get(recipe_key)
    if not recipe:
        raise ValueError(f"Unknown recipe: {recipe_key}")

    effect_jsx_parts: list[str] = []
    for effect_def in recipe["effect_chain"]:
        effect_jsx_parts.append(_generate_effect_jsx(effect_def))

    effects_code = "\n".join(effect_jsx_parts)

    jsx = f"""(function(){{
var _r = {{}};
try {{
  var c = app.project.activeItem;
  if (!c || !(c instanceof CompItem)) {{
    _r = {{status: 'error', message: 'No active composition'}};
    return JSON.stringify(_r);
  }}
  var layerName = '{target_layer_name}';
  var L = null;
  for (var i = 1; i <= c.numLayers; i++) {{
    if (c.layer(i).name === layerName) {{ L = c.layer(i); break; }}
  }}
  if (!L) {{
    _r = {{status: 'error', message: 'Layer not found: ' + layerName}};
    return JSON.stringify(_r);
  }}
  // === Style: {recipe['display_name']} ===
  {effects_code}
  _r = {{status: 'success', preset: '{recipe_key}', layer: layerName}};
}} catch(e) {{
  _r = {{status: 'error', message: e.toString()}};
}}
return JSON.stringify(_r);
}})();"""
    return jsx


# ---------------------------------------------------------------------------
# 预设 JSON 生成（兼容 text_animation_presets.json 格式）
# ---------------------------------------------------------------------------

def generate_preset_entry(
    recipe_key: str,
    category: str = "style_reverse",
) -> dict[str, Any]:
    """生成单个预设条目（兼容 text_animation_presets.json 格式）。"""
    recipe = STYLE_RECIPES[recipe_key]
    jsx = generate_style_preset_jsx(recipe_key)

    return {
        "id": recipe_key,
        "name": recipe["display_name"],
        "name_en": recipe["display_name"],
        "description": recipe["description"],
        "tags": recipe["tags"],
        "difficulty": len(recipe["effect_chain"]),
        "duration_default": 2.0,
        "parameters": [
            {"name": "targetLayerName", "type": "string", "default": "目标图层",
             "description": "目标图层名称"},
        ],
        "applies": ["AnyLayer"],
        "jsx_template": jsx,
        "source": "reverse_engineered",
        "effect_chain": [e["matchName"] for e in recipe["effect_chain"]],
    }


def generate_full_preset_json(
    output_path: str = "",
    recipe_keys: list[str] | None = None,
) -> dict[str, Any]:
    """生成完整的风格预设 JSON（兼容 text_animation_presets.json 格式）。

    Args:
        output_path: 输出文件路径（可选）
        recipe_keys: 要包含的配方键名列表（默认全部）

    Returns:
        预设字典
    """
    if recipe_keys is None:
        recipe_keys = list(STYLE_RECIPES.keys())

    presets = [generate_preset_entry(k) for k in recipe_keys]

    result: dict[str, Any] = {
        "version": "1.0",
        "description": f"逆向工程提取的风格预设 ({len(presets)} 个)",
        "generated_at": datetime.now().isoformat(),
        "source": "aep_analyzer/preset_generator.py",
        "category": {
            "style_reverse": {
                "display_name": "逆向提取风格预设",
                "count": len(presets),
                "presets": presets,
            }
        },
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"Preset JSON saved to: {output_path}")

    return result


# ---------------------------------------------------------------------------
# 从 AEP 分析报告自动检测匹配的风格
# ---------------------------------------------------------------------------

def detect_matching_styles(
    effect_chain: list[str],
    threshold: float = 0.6,
) -> list[dict[str, Any]]:
    """根据效果链匹配最接近的风格配方。

    Args:
        effect_chain: 从 AEP 提取的效果 matchName 列表
        threshold: 匹配阈值（0-1）

    Returns:
        匹配的风格列表，按匹配度排序
    """
    chain_set = set(effect_chain)
    matches: list[dict[str, Any]] = []

    for key, recipe in STYLE_RECIPES.items():
        recipe_effects = {e["matchName"] for e in recipe["effect_chain"]}
        if not recipe_effects:
            continue
        overlap = chain_set & recipe_effects
        if not overlap:
            continue
        score = len(overlap) / max(len(recipe_effects), 1)
        if score >= threshold:
            matches.append({
                "style": key,
                "display_name": recipe["display_name"],
                "score": round(score, 2),
                "matched_effects": list(overlap),
                "missing_effects": list(recipe_effects - chain_set),
            })

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def main() -> None:
    """生成全部风格预设 JSON 并输出。"""
    output_path = str(_PROJECT_ROOT / "config" / "style_reverse_presets.json")
    result = generate_full_preset_json(output_path)
    n_presets = result["category"]["style_reverse"]["count"]
    print(f"Generated {n_presets} style presets -> {output_path}")

    # 演示：检测匹配
    sample_chain = ["ADBE Exposure2", "ADBE Fractal Noise", "ADBE Glo2", "ADBE Tint"]
    matches = detect_matching_styles(sample_chain)
    print(f"\nSample chain: {sample_chain}")
    for m in matches:
        print(f"  -> {m['display_name']} (score={m['score']}, matched={m['matched_effects']})")


if __name__ == "__main__":
    main()
