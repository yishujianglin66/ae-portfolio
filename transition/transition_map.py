"""
transition_map.py
Phase 3 - 抽象转场类型 → AE 可执行操作映射库

用途：将 ae_agent_pipeline._create_transitions 生成的 7 种抽象转场类型
      （crossfade/hard_cut/dissolve/wipe/zoom_blur/fade_to_black/dreamy_dissolve）
      转换为 AE 可执行的操作列表（addEffect / setKeyframe / addLayer）。

抽象转场类型不是 AE matchName，无法直接执行；本模块负责将其落地为
具体的 AE 效果、关键帧与额外图层操作。

数据来源：
  - ae_agent_pipeline.py _create_transitions 方法
  - AE ExtendScript API 原子级映射手册.md matchName 清单
  - effect_name_map.py 转场类效果

设计说明：
  - TRANSITION_MAP 中的时间为相对时间（0.0 = 转场起点，1.0 = 转场终点），
    由 transition_to_ae_ops 根据转场元数据的 startTime / duration 换算为绝对时间。
  - layerRef 使用符号引用："fromLayer" / "toLayer" 代表转场两侧图层，
    其他字符串代表本转场新建图层（layers 中定义）的 ref。
  - 输出操作字段命名对齐 compiler 原子操作规范
    （op / ref / layerRef / matchName / effectName / propertyPath / settings / keyframes）。

对齐文件: effect_name_map.py
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


__all__ = [
    "TransitionMapEntry",
    "TRANSITION_MAP",
    "EASE_TYPE_MAP",
    "transition_to_ae_ops",
    "get_all_transition_types",
]


# ---------------------------------------------------------------------------
# 缓动类型映射：pipeline 内部命名 → compiler EasingType
# ---------------------------------------------------------------------------
EASE_TYPE_MAP: Dict[str, str] = {
    "linear": "linear",
    "easeIn": "ease_in",
    "easeOut": "ease_out",
    "easeInOut": "ease_in_out",
    "hold": "hold",
    "bezier": "bezier",
}

# 符号引用常量
_FROM_LAYER = "fromLayer"
_TO_LAYER = "toLayer"


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class TransitionMapEntry:
    """单个抽象转场类型到 AE 操作的映射模板

    Attributes:
        ae_effects: 需要添加的 AE 效果列表，每项含
                    {layerRef, matchName, effectName, settings}
        keyframes:  需要添加的关键帧组列表，每项含
                    {layerRef, propertyPath, keyframes:[{time, value, easing?}]}
                    其中 time 为相对时间 0.0~1.0
        layers:     需要创建的额外图层列表，每项含
                    {ref, layerType, name, color, width, height, ...}
        description: 该转场的文字说明
    """
    ae_effects: List[Dict[str, Any]] = field(default_factory=list)
    keyframes: List[Dict[str, Any]] = field(default_factory=list)
    layers: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# 转场映射表（7 种抽象转场类型 → AE 操作模板）
# ---------------------------------------------------------------------------

TRANSITION_MAP: Dict[str, TransitionMapEntry] = {

    # 1. 交叉淡化：fromLayer 淡出 + toLayer 淡入
    "crossfade": TransitionMapEntry(
        description="图层 Opacity 关键帧交叉（fromLayer 淡出 + toLayer 淡入）",
        ae_effects=[],
        keyframes=[
            {
                "layerRef": _FROM_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 100},
                    {"time": 1.0, "value": 0},
                ],
            },
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 100},
                ],
            },
        ],
        layers=[],
    ),

    # 2. 硬切：无额外效果，仅时间点切割（由图层 in/out 点决定）
    "hard_cut": TransitionMapEntry(
        description="硬切：无额外效果，仅时间点切割",
        ae_effects=[],
        keyframes=[],
        layers=[],
    ),

    # 3. 溶解：ADBE Dissolve 效果 或 Opacity 关键帧
    "dissolve": TransitionMapEntry(
        description="溶解：ADBE Dissolve 效果 或 Opacity 关键帧",
        ae_effects=[
            {
                "layerRef": _TO_LAYER,
                "matchName": "ADBE Dissolve",
                "effectName": "Dissolve",
                "settings": {
                    "Transition Completion": 0,
                },
            },
        ],
        keyframes=[
            # Opacity 关键帧作为可靠实现（ADBE Dissolve 不可用时的回退方案）
            {
                "layerRef": _FROM_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 100},
                    {"time": 1.0, "value": 0},
                ],
            },
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 100},
                ],
            },
            # 驱动 ADBE Dissolve 的 Transition Completion 0 → 100
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Effects/Dissolve/Transition Completion",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 100},
                ],
            },
        ],
        layers=[],
    ),

    # 4. 擦除：ADBE Linear Wipe 效果
    "wipe": TransitionMapEntry(
        description="擦除：ADBE Linear Wipe 效果",
        ae_effects=[
            {
                "layerRef": _TO_LAYER,
                "matchName": "ADBE Linear Wipe",
                "effectName": "Linear Wipe",
                "settings": {
                    "Transition Completion": 0,
                    "Wipe Angle": 90,
                    "Feather": 5,
                },
            },
        ],
        keyframes=[
            # 擦除完成度 0 → 100
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Effects/Linear Wipe/Transition Completion",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 100},
                ],
            },
        ],
        layers=[],
    ),

    # 5. 缩放模糊：ADBE Zoom Blur 效果 + Scale 关键帧
    "zoom_blur": TransitionMapEntry(
        description="缩放模糊：ADBE Zoom Blur 效果 + Scale 关键帧",
        ae_effects=[
            {
                "layerRef": _TO_LAYER,
                "matchName": "ADBE Zoom Blur",
                "effectName": "Zoom Blur",
                "settings": {
                    "Blur Amount": 0,
                    "Center": [960, 540],
                },
            },
        ],
        keyframes=[
            # Zoom Blur 模糊量：0 → 高峰(中点) → 0
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Effects/Zoom Blur/Blur Amount",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 0.5, "value": 50},
                    {"time": 1.0, "value": 0},
                ],
            },
            # toLayer Scale 推进：100 → 120
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Transform/Scale",
                "keyframes": [
                    {"time": 0.0, "value": [100, 100]},
                    {"time": 1.0, "value": [120, 120]},
                ],
            },
            # fromLayer 同步淡出
            {
                "layerRef": _FROM_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 100},
                    {"time": 1.0, "value": 0},
                ],
            },
        ],
        layers=[],
    ),

    # 6. 黑场过渡：Solid 黑色层 Opacity 关键帧（0 → 100 → 0）
    "fade_to_black": TransitionMapEntry(
        description="黑场过渡：Solid 黑色层 Opacity 关键帧",
        ae_effects=[],
        keyframes=[
            # 黑色 Solid 层不透明度：0 → 100（中点）→ 0
            {
                "layerRef": "solid_fade_black",
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 0.5, "value": 100},
                    {"time": 1.0, "value": 0},
                ],
            },
        ],
        layers=[
            {
                "ref": "solid_fade_black",
                "layerType": "solid",
                "name": "Fade To Black Solid",
                "color": [0, 0, 0],
                "width": 1920,
                "height": 1080,
            },
        ],
    ),

    # 7. 梦幻溶解：ADBE Gaussian Blur + Opacity 关键帧组合
    "dreamy_dissolve": TransitionMapEntry(
        description="梦幻溶解：ADBE Gaussian Blur + Opacity 关键帧组合",
        ae_effects=[
            {
                "layerRef": _FROM_LAYER,
                "matchName": "ADBE Gaussian Blur 2",
                "effectName": "Gaussian Blur",
                "settings": {
                    "Blurriness": 0,
                    "Blur Dimensions": "Full",
                },
            },
            {
                "layerRef": _TO_LAYER,
                "matchName": "ADBE Gaussian Blur 2",
                "effectName": "Gaussian Blur",
                "settings": {
                    "Blurriness": 0,
                    "Blur Dimensions": "Full",
                },
            },
        ],
        keyframes=[
            # fromLayer 模糊量：0 → 60（淡出时逐渐模糊）
            {
                "layerRef": _FROM_LAYER,
                "propertyPath": "Effects/Gaussian Blur/Blurriness",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 60},
                ],
            },
            # toLayer 模糊量：60 → 0（从模糊到清晰）
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Effects/Gaussian Blur/Blurriness",
                "keyframes": [
                    {"time": 0.0, "value": 60},
                    {"time": 1.0, "value": 0},
                ],
            },
            # fromLayer 淡出
            {
                "layerRef": _FROM_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 100},
                    {"time": 1.0, "value": 0},
                ],
            },
            # toLayer 淡入
            {
                "layerRef": _TO_LAYER,
                "propertyPath": "Transform/Opacity",
                "keyframes": [
                    {"time": 0.0, "value": 0},
                    {"time": 1.0, "value": 100},
                ],
            },
        ],
        layers=[],
    ),
}


# ---------------------------------------------------------------------------
# 核心转换 API
# ---------------------------------------------------------------------------

def _resolve_ease(ease_type: Optional[str]) -> Optional[Dict[str, Any]]:
    """将 pipeline 缓动命名转换为 compiler EasingType 结构

    Args:
        ease_type: pipeline 内部缓动名（如 "easeInOut"）

    Returns:
        {"type": "ease_in_out"} 形式的结构，或 None
    """
    if not ease_type:
        return None
    mapped = EASE_TYPE_MAP.get(ease_type)
    if not mapped:
        return None
    return {"type": mapped}


def _abs_time(rel: float, start_time: float, duration: float) -> float:
    """相对时间(0.0~1.0) → 绝对时间(秒)"""
    return round(start_time + rel * duration, 4)


def transition_to_ae_ops(transition: dict) -> List[dict]:
    """将单条转场元数据转换为 AE 可执行操作列表

    转场元数据格式（来自 ae_agent_pipeline._create_transitions）：
        {
            "fromLayer":  str,    # 起始图层名
            "toLayer":    str,    # 目标图层名
            "type":       str,    # 抽象转场类型（7 种之一）
            "startTime":  float,  # 转场起始时间（秒）
            "duration":   float,  # 转场持续时间（秒）
            "easeType":   str,    # 缓动类型（如 "easeInOut"）
        }

    返回操作列表，每项为 AE 原子操作：
        - {"op": "addLayer",    ...}  新建额外图层（如黑色 Solid）
        - {"op": "addEffect",   ...}  添加 AE 效果
        - {"op": "setKeyframe", ...}  设置关键帧

    说明：
      - 所有相对时间(0.0~1.0)按 startTime/duration 换算为绝对时间；
      - layerRef 中的 "fromLayer"/"toLayer" 会被替换为实际图层名；
      - 引用新建图层的操作会附带 dependsOn 指向该图层 ref；
      - 输出未携带 compRef（转场元数据中无此信息），由调用方按需附加。
    """
    if not isinstance(transition, dict):
        raise TypeError("transition 必须是 dict")

    t_type = transition.get("type")
    if not t_type:
        raise ValueError("转场元数据缺少 'type' 字段")

    entry = TRANSITION_MAP.get(t_type)
    if entry is None:
        raise ValueError(
            f"未知的转场类型: '{t_type}'，"
            f"支持的类型: {get_all_transition_types()}"
        )

    from_layer = transition.get("fromLayer", "")
    to_layer = transition.get("toLayer", "")
    start_time = float(transition.get("startTime", 0.0))
    duration = float(transition.get("duration", 0.0))
    ease_type = transition.get("easeType")

    # 符号引用 → 实际图层名
    layer_ref_map: Dict[str, str] = {
        _FROM_LAYER: from_layer,
        _TO_LAYER: to_layer,
    }
    created_layer_refs: Dict[str, str] = {}  # ref → name（本转场新建的图层）

    ops: List[dict] = []

    # 1) 创建额外图层（如黑色 Solid）
    for layer_def in entry.layers:
        ref = layer_def.get("ref", "")
        name = layer_def.get("name", ref or "Solid")
        op: Dict[str, Any] = {
            "op": "addLayer",
            "ref": ref,
            "layerType": layer_def.get("layerType", "solid"),
            "name": name,
            # 黑色 Solid 需覆盖整个转场时段
            "startTime": start_time,
            "duration": duration if duration > 0 else 1.0,
        }
        if "color" in layer_def:
            op["color"] = layer_def["color"]
        if "width" in layer_def:
            op["width"] = layer_def["width"]
        if "height" in layer_def:
            op["height"] = layer_def["height"]
        ops.append(op)
        # 注册 ref → name，供后续 keyframe/effect 引用
        layer_ref_map[ref] = name
        created_layer_refs[ref] = name

    # 2) 添加 AE 效果
    for idx, effect_def in enumerate(entry.ae_effects):
        layer_ref = effect_def.get("layerRef", _TO_LAYER)
        target_layer = layer_ref_map.get(layer_ref, layer_ref)
        op = {
            "op": "addEffect",
            "ref": f"fx_{t_type}_{idx}",
            "layerRef": target_layer,
            "matchName": effect_def.get("matchName", ""),
            "effectName": effect_def.get("effectName", effect_def.get("matchName", "")),
        }
        if "settings" in effect_def:
            op["settings"] = effect_def["settings"]
        # 若作用于本转场新建图层，则声明依赖
        if layer_ref in created_layer_refs:
            op["dependsOn"] = [layer_ref]
        ops.append(op)

    # 3) 设置关键帧（相对时间 → 绝对时间）
    for kf_idx, kf_group in enumerate(entry.keyframes):
        layer_ref = kf_group.get("layerRef", _TO_LAYER)
        target_layer = layer_ref_map.get(layer_ref, layer_ref)
        property_path = kf_group.get("propertyPath", "")

        resolved_keyframes = []
        for kf in kf_group.get("keyframes", []):
            rel_time = float(kf.get("time", 0.0))
            resolved: Dict[str, Any] = {
                "time": _abs_time(rel_time, start_time, duration),
                "value": kf.get("value"),
            }
            # 优先使用关键帧自带缓动，否则回退到转场级 easeType
            easing = _resolve_ease(kf.get("easing")) or _resolve_ease(ease_type)
            if easing:
                resolved["easing"] = easing
            resolved_keyframes.append(resolved)

        op = {
            "op": "setKeyframe",
            "ref": f"kf_{t_type}_{kf_idx}",
            "layerRef": target_layer,
            "propertyPath": property_path,
            "keyframes": resolved_keyframes,
        }
        if layer_ref in created_layer_refs:
            op["dependsOn"] = [layer_ref]
        ops.append(op)

    return ops


def get_all_transition_types() -> List[str]:
    """获取所有支持的抽象转场类型"""
    return list(TRANSITION_MAP.keys())


# ---------------------------------------------------------------------------
# 模块自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[transition_map] 支持的转场类型 ({len(get_all_transition_types())}): "
          f"{get_all_transition_types()}")
    for t in get_all_transition_types():
        entry = TRANSITION_MAP[t]
        print(f"  - {t}: effects={len(entry.ae_effects)}, "
              f"keyframe组={len(entry.keyframes)}, layers={len(entry.layers)}")

    # 抽样验证：crossfade
    sample = {
        "fromLayer": "ClipA",
        "toLayer": "ClipB",
        "type": "crossfade",
        "startTime": 2.0,
        "duration": 0.5,
        "easeType": "easeInOut",
    }
    print(f"\n抽样转换 crossfade (start=2.0, dur=0.5):")
    for op in transition_to_ae_ops(sample):
        print(f"  {op}")

    # 抽样验证：fade_to_black（含新建图层 + dependsOn）
    sample_ftb = {
        "fromLayer": "ClipA",
        "toLayer": "ClipB",
        "type": "fade_to_black",
        "startTime": 5.0,
        "duration": 1.0,
        "easeType": "easeInOut",
    }
    print(f"\n抽样转换 fade_to_black (start=5.0, dur=1.0):")
    for op in transition_to_ae_ops(sample_ftb):
        print(f"  {op}")
