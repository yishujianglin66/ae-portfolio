"""
report_to_ops.py - 决策树解析报告 → 编译器输入 转换层
转换流程：解析报告 → 效果映射 → 参数映射 → 关键帧转换 → 编译器操作列表

对齐 TS: compiler/src/phase3/report-to-ops.ts
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
from effect_name_map import find_by_name


__all__ = [
    "VisualFeature",
    "EffectEntry",
    "ParameterEntry",
    "TimelineEntry",
    "KeyframeSpec",
    "KeyframeEntry",
    "AnalysisReport",
    "ReportToOpsOptions",
    "ReportStats",
    "CompilerInput",
    "CompilerMetadata",
    "report_to_ops",
    "analyze_report",
]


# ---------------------------------------------------------------------------
# 数据类定义（对应 8.1 解析报告 YAML Schema）
# ---------------------------------------------------------------------------

@dataclass
class VisualFeature:
    """视觉特征条目"""
    term_id: str
    term_name: str
    time_range: Optional[Tuple[float, float]] = None
    intensity: Optional[float] = None
    confidence: Optional[float] = None


@dataclass
class EffectEntry:
    """效果识别条目"""
    effect_id: str
    effect_name: str
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    confidence: Optional[float] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class ParameterEntry:
    """参数条目"""
    effect_id: str
    parameter: str
    value: Union[float, str, bool, List[float]] = 0.0
    value_range: Optional[Tuple[float, float]] = None
    confidence: Optional[float] = None


@dataclass
class TimelineEntry:
    """时间轴条目"""
    effect_id: str
    start_frame: int = 0
    end_frame: int = 0
    duration_frames: Optional[int] = None
    duration_seconds: Optional[float] = None


@dataclass
class KeyframeSpec:
    """关键帧规格"""
    frame: int
    value: Union[float, List[float]] = 0.0
    easing: str = "linear"
    bezier: Optional[Tuple[float, float, float, float]] = None


@dataclass
class KeyframeEntry:
    """关键帧条目"""
    effect_id: str
    parameter: str
    keyframes: List[KeyframeSpec] = field(default_factory=list)
    keyframe_count: Optional[int] = None


@dataclass
class AnalysisReport:
    """分析报告（对应 8.1 解析报告 YAML Schema）"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    visual_features: List[VisualFeature] = field(default_factory=list)
    effects: List[EffectEntry] = field(default_factory=list)
    parameters: List[ParameterEntry] = field(default_factory=list)
    timeline: List[TimelineEntry] = field(default_factory=list)
    keyframes: List[KeyframeEntry] = field(default_factory=list)
    confidence: Optional[Dict[str, Any]] = None


@dataclass
class ReportToOpsOptions:
    """转换选项（全部 Optional，使用 ?? 语义应用默认值）"""
    comp_name: Optional[str] = None
    comp_width: Optional[int] = None
    comp_height: Optional[int] = None
    comp_duration: Optional[float] = None
    comp_frame_rate: Optional[float] = None
    target_layer_ref: Optional[str] = None
    min_confidence: Optional[float] = None
    generate_set_property: Optional[bool] = None
    generate_set_keyframe: Optional[bool] = None
    default_layer_type: Optional[str] = None
    default_layer_name: Optional[str] = None


@dataclass
class ReportStats:
    """报告统计信息"""
    total_effects: int = 0
    mapped_effects: int = 0
    unknown_effects: List[str] = field(default_factory=list)
    total_parameters: int = 0
    total_keyframes: int = 0
    avg_confidence: float = 0.0
    generated_ops: int = 0
    ops_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class CompilerMetadata:
    """编译器元数据"""
    source: str = ""
    confidence: float = 0.8
    timestamp: str = ""
    description: str = ""


@dataclass
class CompilerInput:
    """编译器输入"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    operations: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 内部辅助函数
# ---------------------------------------------------------------------------

def _map_easing_string(easing: str) -> str:
    """将缓动字符串映射为标准 EasingType"""
    if not easing:
        return "linear"
    lower = easing.lower()
    easing_map: Dict[str, str] = {
        "linear": "linear",
        "ease_in": "ease_in",
        "easein": "ease_in",
        "ease_out": "ease_out",
        "easeout": "ease_out",
        "ease_in_out": "ease_in_out",
        "easeinout": "ease_in_out",
        "bezier": "bezier",
        "hold": "hold",
        "cubic": "ease_in_out",
        "quintic": "ease_in_out",
        "quartic": "ease_in_out",
    }
    return easing_map.get(lower, "linear")


def _frame_to_time(frame: int, fps: float) -> float:
    """帧号转时间（秒）"""
    if not fps or fps <= 0:
        fps = 30
    return frame / fps


def _bezier_to_ease_params(
    bezier: Optional[Tuple[float, float, float, float]]
) -> Tuple[float, float]:
    """贝塞尔曲线转缓动参数 (speed, influence)"""
    if not bezier or len(bezier) != 4:
        return (0.0, 33.0)
    x2 = bezier[2]
    y2 = bezier[3]
    speed = max(0.0, min(100.0, (1 - y2) * 100))
    influence = max(0.0, min(100.0, x2 * 100))
    return (speed, influence)


def _pick_value_in_range(
    value: Any,
    value_range: Optional[Tuple[float, float]]
) -> Any:
    """选择值，若 value 为空则取范围中点"""
    if value is not None:
        return value
    if value_range and len(value_range) == 2:
        return (value_range[0] + value_range[1]) / 2
    return 0


# ---------------------------------------------------------------------------
# 主转换函数
# ---------------------------------------------------------------------------

def report_to_ops(
    report: AnalysisReport,
    options: Optional[ReportToOpsOptions] = None
) -> CompilerInput:
    """将分析报告转换为编译器操作列表

    Args:
        report: 分析报告对象
        options: 转换选项

    Returns:
        CompilerInput 编译器输入
    """
    opts = options or ReportToOpsOptions()
    # 应用默认值（使用 ?? 语义：仅 None 时取默认值）
    comp_name = (
        opts.comp_name if opts.comp_name is not None else "Phase3 Output"
    )
    comp_width = opts.comp_width if opts.comp_width is not None else 1920
    comp_height = opts.comp_height if opts.comp_height is not None else 1080
    comp_duration = (
        opts.comp_duration if opts.comp_duration is not None else 10
    )
    # 帧率：选项 → 报告元数据 → 默认 30
    report_fps = (report.metadata or {}).get("frame_rate")
    if opts.comp_frame_rate is not None:
        comp_frame_rate = opts.comp_frame_rate
    elif report_fps is not None:
        comp_frame_rate = report_fps
    else:
        comp_frame_rate = 30
    target_layer_ref = (
        opts.target_layer_ref if opts.target_layer_ref is not None else ""
    )
    min_confidence = (
        opts.min_confidence if opts.min_confidence is not None else 0.5
    )
    generate_set_property = (
        opts.generate_set_property
        if opts.generate_set_property is not None else True
    )
    generate_set_keyframe = (
        opts.generate_set_keyframe
        if opts.generate_set_keyframe is not None else True
    )
    default_layer_type = (
        opts.default_layer_type
        if opts.default_layer_type is not None else "solid"
    )
    default_layer_name = (
        opts.default_layer_name
        if opts.default_layer_name is not None else "Target Layer"
    )

    operations: List[Dict[str, Any]] = []
    ref_counter = {
        "comp": 0, "layer": 0, "fx": 0, "kf": 0, "prop": 0,
        "expr": 0, "mask": 0, "blend": 0, "parent": 0, "matte": 0,
    }
    effect_id_to_ref_map: Dict[str, Dict[str, Any]] = {}

    # 1. 创建合成
    comp_ref = "comp_main"
    operations.append({
        "op": "createComp",
        "ref": comp_ref,
        "name": comp_name,
        "width": comp_width,
        "height": comp_height,
        "pixelAspect": 1,
        "duration": comp_duration,
        "frameRate": comp_frame_rate,
        "bgColor": [0, 0, 0],
    })
    ref_counter["comp"] += 1

    # 2. 创建目标图层（如果未指定）
    if not target_layer_ref:
        ref_counter["layer"] += 1
        target_layer_ref = f"layer_{str(ref_counter['layer']).zfill(3)}"
        add_layer_op: Dict[str, Any] = {
            "op": "addLayer",
            "ref": target_layer_ref,
            "compRef": comp_ref,
            "layerType": default_layer_type,
            "name": default_layer_name,
            "duration": comp_duration,
        }
        if default_layer_type == "solid":
            add_layer_op["color"] = [0.5, 0.5, 0.5]
        elif default_layer_type == "adjustment":
            add_layer_op["color"] = [1, 1, 1]
        operations.append(add_layer_op)

    # 3. 过滤低置信度效果
    effects = [
        e for e in (report.effects or [])
        if (e.confidence if e.confidence is not None else 1.0)
        >= min_confidence
    ]

    # 4. 为每个效果创建 addEffect 操作
    for effect in effects:
        map_entry = find_by_name(effect.effect_name)
        if not map_entry:
            print(f"[Phase3] 未知效果名: {effect.effect_name}")
            continue
        ref_counter["fx"] += 1
        effect_ref = f"fx_{str(ref_counter['fx']).zfill(3)}"
        operations.append({
            "op": "addEffect",
            "ref": effect_ref,
            "layerRef": target_layer_ref,
            "compRef": comp_ref,
            "matchName": map_entry.match_name,
            "effectName": map_entry.display_name,
        })
        effect_id_to_ref_map[effect.effect_id] = {
            "effectRef": effect_ref,
            "layerRef": target_layer_ref,
            "matchName": map_entry.match_name,
            "paramMap": map_entry.param_map,
        }

    # 5. 生成 setProperty 操作
    if generate_set_property:
        parameters = [
            p for p in (report.parameters or [])
            if p.effect_id in effect_id_to_ref_map
            and (
                p.confidence if p.confidence is not None else 1.0
            ) >= min_confidence
        ]
        for param in parameters:
            effect_map = effect_id_to_ref_map[param.effect_id]
            prop_name = (
                effect_map["paramMap"].get(param.parameter)
                or param.parameter
            )
            value = _pick_value_in_range(param.value, param.value_range)
            ref_counter["prop"] += 1
            operations.append({
                "op": "setProperty",
                "ref": f"prop_{str(ref_counter['prop']).zfill(3)}",
                "layerRef": effect_map["layerRef"],
                "compRef": comp_ref,
                "propertyPath": (
                    f"Effects/{effect_map['effectRef']}/{prop_name}"
                ),
                "value": value,
            })

    # 6. 生成 setKeyframe 操作
    if generate_set_keyframe and report.keyframes:
        for kf_entry in report.keyframes:
            effect_map = effect_id_to_ref_map.get(kf_entry.effect_id)
            is_layer_anim = kf_entry.effect_id in ("ANIM", "LAYER")
            if not effect_map and not is_layer_anim:
                continue

            if effect_map:
                prop_name = (
                    effect_map["paramMap"].get(kf_entry.parameter)
                    or kf_entry.parameter
                )
                property_path = (
                    f"Effects/{effect_map['effectRef']}/{prop_name}"
                )
                layer_ref = effect_map["layerRef"]
            else:
                # 图层动画：参数首字母大写，路径为 Transform/<Property>
                transform_param = (
                    kf_entry.parameter[0].upper()
                    + kf_entry.parameter[1:]
                )
                property_path = f"Transform/{transform_param}"
                layer_ref = target_layer_ref

            keyframes = []
            for kf in (kf_entry.keyframes or []):
                time = _frame_to_time(kf.frame, comp_frame_rate)
                easing_type = _map_easing_string(kf.easing)
                ease_speed, ease_influence = _bezier_to_ease_params(
                    kf.bezier
                )
                keyframes.append({
                    "time": time,
                    "value": kf.value,
                    "easing": {
                        "type": easing_type,
                        "inSpeed": ease_speed,
                        "inInfluence": ease_influence,
                        "outSpeed": ease_speed,
                        "outInfluence": ease_influence,
                    },
                })
            if not keyframes:
                continue

            ref_counter["kf"] += 1
            operations.append({
                "op": "setKeyframe",
                "ref": f"kf_{str(ref_counter['kf']).zfill(3)}",
                "layerRef": layer_ref,
                "compRef": comp_ref,
                "propertyPath": property_path,
                "keyframes": keyframes,
            })

    # 7. 生成 setExpression 操作（如果报告中包含表达式数据）
    expressions = (report.metadata or {}).get("expressions", []) or []
    for expr_data in expressions:
        ref_counter["expr"] += 1
        operations.append({
            "op": "setExpression",
            "ref": f"expr_{str(ref_counter['expr']).zfill(3)}",
            "layerRef": expr_data.get("layerRef", target_layer_ref),
            "compRef": comp_ref,
            "propertyPath": expr_data.get("propertyPath", ""),
            "expression": expr_data.get("expression", ""),
        })

    # 8. 生成 addMask 操作（如果报告中包含遮罩数据）
    masks = (report.metadata or {}).get("masks", []) or []
    for mask_data in masks:
        ref_counter["mask"] += 1
        operations.append({
            "op": "addMask",
            "ref": f"mask_{str(ref_counter['mask']).zfill(3)}",
            "layerRef": mask_data.get("layerRef", target_layer_ref),
            "compRef": comp_ref,
            "maskPath": mask_data.get("maskPath", []),
            "maskName": mask_data.get("maskName", "Mask 1"),
        })

    # 9. 生成 setBlendMode 操作（如果报告中包含混合模式数据）
    blend_modes = (report.metadata or {}).get("blendModes", []) or []
    for blend_data in blend_modes:
        ref_counter["blend"] += 1
        operations.append({
            "op": "setBlendMode",
            "ref": f"blend_{str(ref_counter['blend']).zfill(3)}",
            "layerRef": blend_data.get("layerRef", target_layer_ref),
            "compRef": comp_ref,
            "blendMode": blend_data.get("blendMode", "normal"),
        })

    # 10. 生成 setParent 操作（如果报告中包含父级图层数据）
    parents = (report.metadata or {}).get("parents", []) or []
    for parent_data in parents:
        ref_counter["parent"] += 1
        operations.append({
            "op": "setParent",
            "ref": f"parent_{str(ref_counter['parent']).zfill(3)}",
            "layerRef": parent_data.get("layerRef", target_layer_ref),
            "compRef": comp_ref,
            "parentLayerRef": parent_data.get("parentLayerRef", ""),
        })

    # 11. 生成 setTrackMatte 操作（如果报告中包含轨道遮罩数据）
    track_mattes = (report.metadata or {}).get("trackMattes", []) or []
    for matte_data in track_mattes:
        ref_counter["matte"] += 1
        operations.append({
            "op": "setTrackMatte",
            "ref": f"matte_{str(ref_counter['matte']).zfill(3)}",
            "layerRef": matte_data.get("layerRef", target_layer_ref),
            "compRef": comp_ref,
            "matteLayerRef": matte_data.get("matteLayerRef", ""),
            "matteType": matte_data.get("matteType", "alpha"),
        })

    # 12. 构建 CompilerInput
    report_conf = report.confidence or {}
    overall_conf = report_conf.get("overall", 0.8)
    video_file = (report.metadata or {}).get("video_file", "unknown")
    metadata = {
        "source": "phase3-tree-to-compiler",
        "confidence": overall_conf,
        "timestamp": datetime.now().isoformat(),
        "description": (
            f"Auto-generated from analysis report (video: {video_file})"
        ),
    }
    return CompilerInput(metadata=metadata, operations=operations)


# ---------------------------------------------------------------------------
# 统计与诊断函数
# ---------------------------------------------------------------------------

def analyze_report(report: AnalysisReport) -> ReportStats:
    """分析报告统计信息

    Args:
        report: 分析报告对象

    Returns:
        ReportStats 统计结果
    """
    effects = report.effects or []
    parameters = report.parameters or []
    keyframes = report.keyframes or []

    mapped_effects = 0
    unknown_effects: List[str] = []
    for e in effects:
        entry = find_by_name(e.effect_name)
        if entry:
            mapped_effects += 1
        else:
            unknown_effects.append(f"{e.effect_id}: {e.effect_name}")

    total_kf = sum(len(kf.keyframes or []) for kf in keyframes)
    confidences = [
        (e.confidence if e.confidence is not None else 1.0)
        for e in effects
        if (e.confidence if e.confidence is not None else 1.0) > 0
    ]
    avg_confidence = (
        sum(confidences) / len(confidences) if confidences else 0.0
    )

    return ReportStats(
        total_effects=len(effects),
        mapped_effects=mapped_effects,
        unknown_effects=unknown_effects,
        total_parameters=len(parameters),
        total_keyframes=total_kf,
        avg_confidence=avg_confidence,
        generated_ops=0,
        ops_by_type={},
    )


# ---------------------------------------------------------------------------
# 模块自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 构造最小测试用报告：Glow 效果 + 参数 + 关键帧
    test_report = AnalysisReport(
        metadata={
            "video_file": "test_sample.mp4",
            "duration": "00:00:10",
            "frame_rate": 30,
            "resolution": "1920x1080",
        },
        effects=[
            EffectEntry(
                effect_id="fx_001",
                effect_name="Glow",
                start_frame=0,
                end_frame=300,
                confidence=0.9,
            ),
        ],
        parameters=[
            ParameterEntry(
                effect_id="fx_001",
                parameter="Glow Radius",
                value=25.0,
                confidence=0.85,
            ),
        ],
        keyframes=[
            KeyframeEntry(
                effect_id="fx_001",
                parameter="Glow Intensity",
                keyframes=[
                    KeyframeSpec(
                        frame=0, value=0.0, easing="ease_in_out"
                    ),
                    KeyframeSpec(
                        frame=60, value=1.5, easing="bezier",
                        bezier=(0.42, 0.0, 0.58, 1.0),
                    ),
                ],
            ),
        ],
        confidence={"overall": 0.88},
    )

    print("=" * 60)
    print("[report_to_ops] 自检开始")
    print("=" * 60)

    result = report_to_ops(test_report)
    print(f"生成操作数: {len(result.operations)}")
    op_types = [op["op"] for op in result.operations]
    print(f"操作类型: {op_types}")
    print(f"元数据: {result.metadata}")
    print()

    stats = analyze_report(test_report)
    print("报告统计:")
    print(f"  总效果数: {stats.total_effects}")
    print(f"  已映射效果: {stats.mapped_effects}")
    print(f"  未知效果: {stats.unknown_effects}")
    print(f"  总参数数: {stats.total_parameters}")
    print(f"  总关键帧数: {stats.total_keyframes}")
    print(f"  平均置信度: {stats.avg_confidence:.2f}")
    print()
    print("[report_to_ops] 自检完成")
