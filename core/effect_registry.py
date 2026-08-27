"""effect_registry — AE 效果参数寻址统一注册表（2026-08-16 审计 P1 收口）

AE 效果的参数有两种寻址方式, 两种 JSX 生成器各用其一:

- PARAM_POSITION_INDEX: property(<int>) 整数位置索引
  （synthesis_orchestrator 用, 真机验证的常用效果小表）
- PARAM_AVID_INDEX:     property("ADBE xxx-0001") AVID 字符串
  （jsx_generator 用, 从 config/effect_presets.json 归纳）

同一效果两个维度并不完全对齐（位置随版本/语言可能漂移, AVID 稳定）,
因此**不合并值**——本模块只把分散在多个文件的同一知识收拢为一处,
并明确两种维度的边界。名称层注册表 data/fx_registry.json（matchName→
中文名, 2412 条）是第三维度, 保持为数据文件不被本模块硬编码。

用法:
    from core.effect_registry import PARAM_POSITION_INDEX, PARAM_AVID_INDEX
    pos = PARAM_POSITION_INDEX["ADBE Glo2"]          # {"threshold": 1, ...}
    avid = PARAM_AVID_INDEX["ADBE Glo2"]             # {"Glow Threshold": "ADBE Glo2-0001", ...}
"""
from __future__ import annotations

from typing import Dict


# 整数位置索引（property(N)）— 原 synthesis_orchestrator.MATCH_PARAM_MAP
PARAM_POSITION_INDEX: Dict[str, Dict[str, int]] = {
    "ADBE Glo2": {"threshold": 1, "radius": 2, "intensity": 3},
    "ADBE Gaussian Blur 2": {"blurriness": 1},
    "ADBE Grid": {"opacity": 13},
    "ADBE Ramp": {"start_color": 1, "end_color": 2},
    "ADBE Levels": {"white": 4},
    "ADBE HUE SATURATION": {"saturation": 1},
}

# AVID 字符串索引（property("ADBE xxx-000N")）— 原 jsx_generator._EFFECT_PARAM_INDEX
PARAM_AVID_INDEX: Dict[str, Dict[str, str]] = {
    "ADBE Glo2": {
        "Glow Threshold": "ADBE Glo2-0001",
        "Glow Radius": "ADBE Glo2-0002",
        "Glow Intensity": "ADBE Glo2-0003",
    },
    "ADBE Gaussian Blur 2": {
        "Blurriness": "ADBE Gaussian Blur 2-0001",
        "Blur Dimensions": "ADBE Gaussian Blur 2-0002",
    },
    "ADBE Lens Flare": {
        "Flare Brightness": "ADBE Lens Flare-0002",
    },
    "ADBE Lumetri": {
        "Exposure": "ADBE Lumetri-0001",
        "Contrast": "ADBE Lumetri-0002",
        "Saturation": "ADBE Lumetri-0003",
    },
    "ADBE Fractal Noise": {
        "Contrast": "ADBE Fractal Noise-0001",
        "Brightness": "ADBE Fractal Noise-0002",
    },
}

# AVID 兜底默认值 — 原 jsx_generator._EFFECT_DEFAULTS（无 config params 时使用）
AVID_DEFAULTS: Dict[str, Dict[str, float]] = {
    "ADBE Glo2": {"ADBE Glo2-0001": 50, "ADBE Glo2-0002": 15, "ADBE Glo2-0003": 1.0},
    "ADBE Gaussian Blur 2": {"ADBE Gaussian Blur 2-0001": 20, "ADBE Gaussian Blur 2-0002": 1},
    "ADBE Lens Flare": {"ADBE Lens Flare-0001": 50},
    "ADBE Lumetri": {"ADBE Lumetri-0001": 0, "ADBE Lumetri-0002": 50},
    "ADBE Fractal Noise": {"ADBE Fractal Noise-0001": 2.0, "ADBE Fractal Noise-0002": 10},
}


__all__ = ["PARAM_POSITION_INDEX", "PARAM_AVID_INDEX", "AVID_DEFAULTS"]
