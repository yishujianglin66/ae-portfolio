#!/usr/bin/env python3
"""
intent_to_report.py
Phase 4 → Phase 3 衔接层（Python 版）

把 NLU 层的 Intent + EffectDescription 转换为 Phase 3 的 AnalysisReport，
对齐 TypeScript 端 compiler/src/phase4/intent-to-report.ts。

输出格式严格匹配 Phase 3 的 report-to-ops.ts 中定义的 AnalysisReport schema，
让整个管线（自然语言 → NLU → 推理 → 编译 → MCP）能端到端运行。

字段说明：
  - effects[].effect_name: 用户友好的效果名（如 "Gaussian Blur"），会被 findByName 查找
  - parameters[].parameter: 参数名（如 "Blurriness"）
  - keyframes[].parameter: 关键帧属性名
  - keyframes[].keyframes: KeyframeSpec 数组，每个有 frame/value/easing/bezier
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import re

from effect_description_parser import (
    EffectDescription, VocabRef, IntensityRef, ColorRef, TemporalRef,
    get_style_recipe, VOCAB_EFFECTS,
)

# Intent 类型常量：优先从 nlu_parser 导入，失败时降级为本地常量（duck typing 兼容）
try:
    from nlu_parser import IntentType
except ImportError:
    class IntentType:
        ADD_EFFECT = "ADD_EFFECT"
        CREATE_ANIM = "CREATE_ANIM"
        ADJUST_PARAM = "ADJUST_PARAM"
        CREATE_LAYER = "CREATE_LAYER"
        STYLE_COMBO = "STYLE_COMBO"
        REVERSE_ANALYZE = "REVERSE_ANALYZE"
        UNKNOWN = "UNKNOWN"


# ============================================================================
# AnalysisReport 数据类（对齐 Phase3 的 report-to-ops.ts schema）
# ============================================================================

@dataclass
class KeyframeSpec:
    """关键帧规格"""
    frame: int
    value: Union[float, List[float]]
    easing: str = "linear"
    bezier: Optional[List[float]] = None  # [x1, y1, x2, y2]


@dataclass
class EffectEntry:
    """效果条目"""
    effect_id: str
    effect_name: str  # 用户友好英文名（如 "Gaussian Blur"）
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)


@dataclass
class ParameterEntry:
    """参数条目"""
    effect_id: str
    parameter: str
    value: Union[float, str, bool, List[float]]
    value_range: Optional[List[float]] = None  # [min, max]
    confidence: float = 0.0


@dataclass
class TimelineEntry:
    """时间轴条目"""
    effect_id: str
    start_frame: int
    end_frame: int
    duration_frames: Optional[int] = None
    duration_seconds: Optional[float] = None


@dataclass
class KeyframeEntry:
    """关键帧条目"""
    effect_id: str
    parameter: str
    keyframes: List[KeyframeSpec]
    keyframe_count: Optional[int] = None


@dataclass
class VisualFeature:
    """视觉特征"""
    term_id: str
    term_name: str
    time_range: Optional[List[float]] = None
    intensity: Optional[float] = None
    confidence: Optional[float] = None


@dataclass
class AnalysisReport:
    """分析报告（对齐 Phase3 report-to-ops.ts schema）"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    visual_features: List[VisualFeature] = field(default_factory=list)
    effects: List[EffectEntry] = field(default_factory=list)
    parameters: List[ParameterEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)
    keyframes: List[KeyframeEntry] = field(default_factory=list)
    confidence: Optional[Dict[str, Any]] = None


# ============================================================================
# 默认合成参数
# ============================================================================

_DEFAULT_COMP = {
    "width": 1920,
    "height": 1080,
    "frame_rate": 30,
    "duration": 10,
}


# ============================================================================
# matchName → 用户友好显示名映射
# ============================================================================

_MATCH_NAME_TO_DISPLAY: Dict[str, str] = {
    "ADBE Gaussian Blur 2": "Gaussian Blur",
    "ADBE Glo2": "Glow",
    "ADBE Directional Blur": "Directional Blur",
    "ADBE Fractal Noise": "Fractal Noise",
    "ADBE Ramp": "Ramp",
    "ADBE HUE SATURATION": "Hue/Saturation",
    "ADBE Protractor2": "Levels",
    "ADBE Color Balance": "Color Balance",
    "ADBE Drop Shadow": "Drop Shadow",
    "ADBE Fill": "Fill",
    "ADBE Stroke": "Stroke",
    "ADBE Noise": "Noise",
    "ADBE Sharpen": "Sharpen",
    "CC Particle World": "CC Particle World",
    "CC Lens": "CC Lens",
    "ADBE Optics Compensation": "Optics Compensation",
    "ADBE Simple Choker": "Simple Choker",
    "ADBE Roughen Edges": "Roughen Edges",
    "ADBE Texturize": "Texturize",
    "ADBE Color Key": "Color Key",
}


def _match_name_to_display_name(match_name: str) -> str:
    """matchName → 用户友好显示名（用于 findByName 查找）。

    例如 "ADBE Gaussian Blur 2" → "Gaussian Blur"。
    未命中映射表时返回 match_name 原值。
    """
    return _MATCH_NAME_TO_DISPLAY.get(match_name, match_name)


# ============================================================================
# VocabRef → EffectEntry 转换
# ============================================================================

def _vocab_ref_to_effect_entry(ref: VocabRef) -> EffectEntry:
    """把 VocabRef 转换为 EffectEntry。

    effect_name 字段会被 report-to-ops.ts 中的 findByName 查找，
    所以必须是用户友好的英文名（如 "Gaussian Blur"），而不是 matchName。
    """
    display_name = _match_name_to_display_name(ref.suggestedEffect or ref.name)
    return EffectEntry(
        effect_id=ref.id,
        effect_name=display_name,
        confidence=ref.confidence,
        evidence=[f"来自词汇: {ref.name} (matched: {ref.matchedKeyword})"],
    )


# ============================================================================
# 根据效果 matchName 推断默认参数
# ============================================================================

def _infer_default_params(ref: VocabRef, intensity_scale: float) -> List[dict]:
    """根据 ref.suggestedEffect 推断默认参数（参考 TS 端 inferDefaultParams）。

    返回字典列表，每项含 parameter / value / value_range。
    """
    params: List[dict] = []
    effect = ref.suggestedEffect

    if effect == "ADBE Gaussian Blur 2":
        params.append({"parameter": "Blurriness", "value": 25 * intensity_scale, "value_range": [5, 50]})
    elif effect == "ADBE Directional Blur":
        params.append({"parameter": "Blur Length", "value": 50 * intensity_scale, "value_range": [10, 100]})
        params.append({"parameter": "Direction", "value": 0, "value_range": [0, 360]})
    elif effect == "ADBE Glo2":
        params.append({"parameter": "Glow Threshold", "value": 40 * intensity_scale, "value_range": [20, 80]})
        params.append({"parameter": "Glow Radius", "value": 50 * intensity_scale, "value_range": [10, 100]})
        params.append({"parameter": "Glow Intensity", "value": 2 * intensity_scale, "value_range": [1, 8]})
    elif effect == "ADBE Fractal Noise":
        params.append({"parameter": "Complexity", "value": 4, "value_range": [1, 10]})
        params.append({"parameter": "Contrast", "value": 100, "value_range": [0, 255]})
        params.append({"parameter": "Brightness", "value": 0, "value_range": [-100, 100]})
    elif effect == "ADBE Ramp":
        params.append({"parameter": "Start of Ramp", "value": [0, 0]})
        params.append({"parameter": "Start Color", "value": [1, 0, 0]})
        params.append({"parameter": "End of Ramp", "value": [1920, 1080]})
        params.append({"parameter": "End Color", "value": [0, 0, 1]})
    elif effect == "ADBE HUE SATURATION":
        params.append({"parameter": "Master Hue", "value": 0, "value_range": [0, 360]})
        params.append({"parameter": "Master Saturation", "value": 10, "value_range": [-100, 100]})
        params.append({"parameter": "Master Lightness", "value": 0, "value_range": [-100, 100]})
    elif effect == "ADBE Protractor2":  # Levels
        params.append({"parameter": "Input Black", "value": 0, "value_range": [0, 254]})
        params.append({"parameter": "Input White", "value": 255, "value_range": [1, 255]})
        params.append({"parameter": "Gamma", "value": 1.0, "value_range": [0.1, 10]})
    elif effect == "ADBE Color Balance":
        # 简化，无参数
        pass
    elif effect == "ADBE Drop Shadow":
        params.append({"parameter": "Opacity", "value": 80 * intensity_scale, "value_range": [0, 100]})
        params.append({"parameter": "Distance", "value": 10 * intensity_scale, "value_range": [0, 50]})
        params.append({"parameter": "Softness", "value": 5 * intensity_scale, "value_range": [0, 30]})
    elif effect == "ADBE Fill":
        params.append({"parameter": "Color", "value": [1, 0, 0]})
    elif effect == "ADBE Stroke":
        params.append({"parameter": "Color", "value": [1, 1, 1]})
        params.append({"parameter": "Brush Size", "value": 3, "value_range": [1, 20]})
        params.append({"parameter": "Opacity", "value": 100, "value_range": [0, 100]})
    elif effect == "ADBE Noise":
        params.append({"parameter": "Amount", "value": 10 * intensity_scale, "value_range": [0, 100]})
    elif effect == "ADBE Sharpen":
        params.append({"parameter": "Sharpen Amount", "value": 50 * intensity_scale, "value_range": [0, 200]})
    elif effect == "CC Particle World":
        params.append({"parameter": "Birth Rate", "value": 1.5 * intensity_scale, "value_range": [0, 10]})
        params.append({"parameter": "Longevity", "value": 2, "value_range": [1, 15]})
        params.append({"parameter": "Velocity", "value": 0.5 * intensity_scale, "value_range": [0, 5]})
    elif effect == "CC Lens":
        params.append({"parameter": "Center", "value": [960, 540]})
        params.append({"parameter": "Size", "value": 80 * intensity_scale, "value_range": [0, 200]})
    elif effect == "ADBE Optics Compensation":
        params.append({"parameter": "Field of View", "value": 100 * intensity_scale, "value_range": [0, 200]})
        params.append({"parameter": "Reverse Lens Distortion", "value": 0})
    elif effect == "ADBE Simple Choker":
        params.append({"parameter": "Choke Matte", "value": 2 * intensity_scale, "value_range": [-100, 100]})
    elif effect == "ADBE Color Key":
        params.append({"parameter": "Key Color", "value": [0, 1, 0]})
        params.append({"parameter": "Color Tolerance", "value": 20, "value_range": [0, 100]})
        params.append({"parameter": "Edge Feather", "value": 1, "value_range": [0, 10]})

    return params


# ============================================================================
# 时间位置 → 帧区间
# ============================================================================

def _temporal_to_frame_range(position: str, total_frames: int) -> tuple:
    """把时间位置（start/middle/end）映射为帧区间 [start_frame, end_frame]。"""
    if position == "start":
        return 0, max(1, total_frames // 3)
    elif position == "middle":
        third = max(1, total_frames // 3)
        return third, 2 * third
    elif position == "end":
        third = max(1, total_frames // 3)
        return 2 * third, total_frames
    # 未知位置：覆盖全程
    return 0, total_frames


# ============================================================================
# 根据动画类型推断关键帧（对齐 TS 端 inferKeyframesForAnim）
# ============================================================================

def _infer_keyframes_for_anim(anim_type: str, context: Optional[Dict]) -> Optional[KeyframeEntry]:
    """根据动画类型推断关键帧。

    返回 KeyframeEntry（parameter + keyframes），无法识别时返回 None。
    """
    if not anim_type:
        return None

    duration = (context or {}).get("duration", _DEFAULT_COMP["duration"])
    fps = (context or {}).get("frame_rate", _DEFAULT_COMP["frame_rate"])
    start_frame = 0
    end_frame = int(duration * fps)

    # 弹入动画
    if re.search(r"弹入|bounce|spring|回弹", anim_type, re.IGNORECASE):
        return KeyframeEntry(
            effect_id="ANIM",
            parameter="Scale",
            keyframes=[
                KeyframeSpec(frame=start_frame, value=0, easing="linear"),
                KeyframeSpec(frame=int(end_frame * 0.3), value=110, easing="ease_out", bezier=[0.34, 1.56, 0.64, 1]),
                KeyframeSpec(frame=int(end_frame * 0.5), value=95, easing="ease_in_out", bezier=[0.45, 0, 0.55, 1]),
                KeyframeSpec(frame=int(end_frame * 0.7), value=102, easing="ease_out", bezier=[0.34, 1.56, 0.64, 1]),
                KeyframeSpec(frame=end_frame, value=100, easing="ease_in_out", bezier=[0.45, 0, 0.55, 1]),
            ],
            keyframe_count=5,
        )

    # 淡入动画
    if re.search(r"淡入|fade|渐入", anim_type, re.IGNORECASE):
        return KeyframeEntry(
            effect_id="ANIM",
            parameter="Opacity",
            keyframes=[
                KeyframeSpec(frame=start_frame, value=0, easing="linear"),
                KeyframeSpec(frame=int(end_frame * 0.3), value=100, easing="ease_out", bezier=[0.33, 0, 0.67, 1]),
            ],
            keyframe_count=2,
        )

    # 滑入动画
    if re.search(r"滑入|slide|位移", anim_type, re.IGNORECASE):
        return KeyframeEntry(
            effect_id="ANIM",
            parameter="Position",
            keyframes=[
                KeyframeSpec(frame=start_frame, value=[-200, 540], easing="linear"),
                KeyframeSpec(frame=int(end_frame * 0.4), value=[960, 540], easing="ease_out", bezier=[0.22, 0.61, 0.36, 1]),
            ],
            keyframe_count=2,
        )

    # 缩放动画
    if re.search(r"缩放|scale", anim_type, re.IGNORECASE):
        return KeyframeEntry(
            effect_id="ANIM",
            parameter="Scale",
            keyframes=[
                KeyframeSpec(frame=start_frame, value=50, easing="linear"),
                KeyframeSpec(frame=int(end_frame * 0.4), value=100, easing="ease_out", bezier=[0.33, 0, 0.67, 1]),
            ],
            keyframe_count=2,
        )

    # 旋转动画
    if re.search(r"旋转|rotate|翻转", anim_type, re.IGNORECASE):
        return KeyframeEntry(
            effect_id="ANIM",
            parameter="Rotation",
            keyframes=[
                KeyframeSpec(frame=start_frame, value=0, easing="linear"),
                KeyframeSpec(frame=end_frame, value=360, easing="linear"),
            ],
            keyframe_count=2,
        )

    # 默认：透明度淡入
    return KeyframeEntry(
        effect_id="ANIM",
        parameter="Opacity",
        keyframes=[
            KeyframeSpec(frame=start_frame, value=0, easing="linear"),
            KeyframeSpec(frame=int(end_frame * 0.3), value=100, easing="ease_out", bezier=[0.33, 0, 0.67, 1]),
        ],
        keyframe_count=2,
    )


# ============================================================================
# 核心函数：Intent + EffectDescription → AnalysisReport
# ============================================================================

def intent_to_report(intent, description: EffectDescription,
                     context: Optional[Dict] = None) -> AnalysisReport:
    """Intent + EffectDescription → AnalysisReport。

    这是 Phase 4 → Phase 3 的关键转换。

    参数：
      intent: Intent 对象（从 nlu_parser.py），含 type / slots / confidence
      description: EffectDescription 对象（从 effect_description_parser.py），
                   含 effectKeywords / intensityKeywords / colorKeywords /
                   styleKeywords / temporalKeywords
      context: Optional[Dict] 含 video_file / duration / frame_rate / resolution

    返回：
      AnalysisReport
    """
    effects: List[EffectEntry] = []
    parameters: List[ParameterEntry] = []
    keyframes: List[KeyframeEntry] = []
    timeline: List[TimelineEntry] = []
    visual_features: List[VisualFeature] = []

    # 综合置信度
    total_confidence = intent.confidence

    # a. 提取强度因子（默认 1.0）
    intensity_scale = description.intensityKeywords[0].value if description.intensityKeywords else 1.0

    # b. 处理效果关键词
    # 注意：VT-6xx（文字动画）和 KF-xx（关键帧动画）是动画描述，不应作为效果添加
    # 只有 VT-001~VT-599 是真正的"效果"
    for ref in description.effectKeywords:
        # 跳过动画类词汇（VT-6xx 和 KF-xx）
        if ref.id.startswith("VT-6") or ref.id.startswith("KF-"):
            # 这些是动画描述，在后续步骤处理
            continue

        effects.append(_vocab_ref_to_effect_entry(ref))
        visual_features.append(VisualFeature(
            term_id=ref.id,
            term_name=ref.name,
            confidence=ref.confidence,
        ))

        # 推断默认参数
        if ref.suggestedEffect:
            params = _infer_default_params(ref, intensity_scale)
            for p in params:
                parameters.append(ParameterEntry(
                    effect_id=ref.id,
                    parameter=p["parameter"],
                    value=p["value"],
                    value_range=p.get("value_range"),
                    confidence=ref.confidence * 0.85,
                ))

        # 如果有颜色关键词，添加颜色参数
        if description.colorKeywords:
            color = description.colorKeywords[0]
            parameters.append(ParameterEntry(
                effect_id=ref.id,
                parameter="Color",
                value=color.rgb,
                confidence=0.75,
            ))

    # c. 处理风格关键词（如果是 STYLE_COMBO 意图）
    if intent.type == IntentType.STYLE_COMBO and getattr(intent.slots, "styleName", None):
        style_name = intent.slots.styleName
        recipe = get_style_recipe(style_name)
        if recipe:
            # 把配方中的效果也加入
            for vid in recipe.get("effectIds", []):
                # 跳过已存在的效果
                if any(e.effect_id == vid for e in effects):
                    continue
                ref = VocabRef(
                    id=vid,
                    name=vid,
                    matchedKeyword=style_name,
                    suggestedEffect=VOCAB_EFFECTS.get(vid),
                    confidence=0.75,
                )
                effects.append(_vocab_ref_to_effect_entry(ref))
                visual_features.append(VisualFeature(
                    term_id=vid,
                    term_name=vid,
                    confidence=0.75,
                ))

                if ref.suggestedEffect:
                    params = _infer_default_params(ref, intensity_scale)
                    for p in params:
                        parameters.append(ParameterEntry(
                            effect_id=ref.id,
                            parameter=p["parameter"],
                            value=p["value"],
                            value_range=p.get("value_range"),
                            confidence=0.65,
                        ))

    # d. 处理 temporalKeywords 生成 timeline 和 keyframes
    if description.temporalKeywords and effects:
        duration = (context or {}).get("duration", _DEFAULT_COMP["duration"])
        fps = (context or {}).get("frame_rate", _DEFAULT_COMP["frame_rate"])
        total_frames = int(duration * fps)

        # 用第一个时间关键词确定时间区间
        temporal = description.temporalKeywords[0]
        start_frame, end_frame = _temporal_to_frame_range(temporal.position, total_frames)
        seg_len = max(1, end_frame - start_frame)
        fade_len = max(1, seg_len // 5)

        for effect in effects:
            # 生成时间轴条目
            timeline.append(TimelineEntry(
                effect_id=effect.effect_id,
                start_frame=start_frame,
                end_frame=end_frame,
                duration_frames=seg_len,
                duration_seconds=seg_len / fps if fps else 0.0,
            ))
            # 生成淡入淡出关键帧
            keyframes.append(KeyframeEntry(
                effect_id=effect.effect_id,
                parameter="Opacity",
                keyframes=[
                    KeyframeSpec(frame=start_frame, value=0, easing="linear"),
                    KeyframeSpec(frame=start_frame + fade_len, value=100, easing="ease_out", bezier=[0.33, 0, 0.67, 1]),
                    KeyframeSpec(frame=end_frame - fade_len, value=100, easing="linear"),
                    KeyframeSpec(frame=end_frame, value=0, easing="ease_in", bezier=[0.67, 0, 0.33, 1]),
                ],
                keyframe_count=4,
            ))

    # 对齐 TS：处理 CREATE_ANIM 意图（根据动画类型推断关键帧）
    if intent.type == IntentType.CREATE_ANIM and getattr(intent.slots, "animType", None):
        kf = _infer_keyframes_for_anim(intent.slots.animType, context)
        if kf:
            keyframes.append(kf)
            total_confidence = max(total_confidence, 0.8)

    # 对齐 TS：处理 ADJUST_PARAM 意图（参数调整）
    if intent.type == IntentType.ADJUST_PARAM and getattr(intent.slots, "paramName", None):
        adjust_amount = getattr(intent.slots, "adjustAmount", None)
        adjust_direction = getattr(intent.slots, "adjustDirection", None)
        if adjust_amount:
            value = adjust_amount
        elif adjust_direction == "increase":
            value = 1.5
        else:
            value = 0.7
        parameters.append(ParameterEntry(
            effect_id="ADJUST",
            parameter=intent.slots.paramName,
            value=value,
            confidence=0.7,
        ))

    # e. 综合置信度计算
    if effects:
        avg_effect_confidence = sum(e.confidence for e in effects) / len(effects)
        total_confidence = (total_confidence + avg_effect_confidence) / 2
    else:
        avg_effect_confidence = 0.0

    # f. 构建 metadata
    duration = (context or {}).get("duration", _DEFAULT_COMP["duration"])
    frame_rate = (context or {}).get("frame_rate", _DEFAULT_COMP["frame_rate"])
    resolution = (context or {}).get("resolution",
                                     f"{_DEFAULT_COMP['width']}x{_DEFAULT_COMP['height']}")
    video_file = (context or {}).get("video_file", "nlu_input")

    metadata: Dict[str, Any] = {
        "video_file": video_file,
        "duration": f"{duration}s",
        "frame_rate": frame_rate,
        "resolution": resolution,
        "analysis_date": datetime.now().isoformat(),
        "analyzer_version": "phase4-nlu-v1",
        "source": f"nlu:{intent.type}",
        "confidence": min(0.95, total_confidence),
        "description": f"NLU解析: {getattr(intent, 'rawInput', '')}",
    }

    return AnalysisReport(
        metadata=metadata,
        visual_features=visual_features,
        effects=effects,
        parameters=parameters,
        timeline=timeline,
        keyframes=keyframes,
        confidence={
            "overall": min(0.95, total_confidence),
            "breakdown": {
                "intent": intent.confidence,
                "effects": avg_effect_confidence,
            },
        },
    )
