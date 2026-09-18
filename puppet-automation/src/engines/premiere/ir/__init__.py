"""
Timeline IR module for Premiere engine
========================================

提供统一的时间线中间表示 (IR) 数据结构和导出能力。
优先从 ae.timeline_ir 导入完整实现，不可用时回退到本地存根。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# 尝试从 ae.timeline_ir 导入完整实现
try:
    from ae.timeline_ir import (
        IRClip,
        IREffect,
        IREffectCategory,
        IRMarker,
        IRScaleMode,
        IRSequence,
        IRTrack,
        IRTrackType,
        IRTransition,
        IRTransitionType,
        IRValidationError,
        IRValidationResult,
        export_timeline_summary,
        export_to_ae_jsx,
        export_to_dict,
        export_to_json,
        export_to_pr_json,
        validate_ir,
    )
except ImportError:
    # 回退：使用本地存根
    from .stubs import (  # type: ignore[no-redef]
        IRClip,
        IREffect,
        IREffectCategory,
        IRMarker,
        IRScaleMode,
        IRSequence,
        IRTrack,
        IRTrackType,
        IRTransition,
        IRTransitionType,
        IRValidationError,
        IRValidationResult,
        export_to_ae_jsx,
        export_to_pr_json,
        validate_ir,
    )


__all__ = [
    "IRTrackType",
    "IREffectCategory",
    "IRTransitionType",
    "IRScaleMode",
    "IRTrack",
    "IRClip",
    "IREffect",
    "IRTransition",
    "IRMarker",
    "IRSequence",
    "IRValidationError",
    "IRValidationResult",
    "validate_ir",
    "export_to_pr_json",
    "export_to_ae_jsx",
]