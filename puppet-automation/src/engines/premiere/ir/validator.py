#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IR 校验模块 — Premiere 时间线 IR 数据的完整性与合规性检查
============================================================

对 IRSequence 进行全面的校验，涵盖：
- 序列基本参数合理性
- 轨道索引连续性和唯一性
- Clip 时间区间合法性（重叠、边界、正时长）
- 源文件存在性检查
- 转场时长与对齐合法性
- 标记时间边界
- FPS 一致性

用法:
    from engine.premiere.ir import IRSequence
    from engine.premiere.ir.validator import validate_ir

    issues = validate_ir(sequence)
    for issue in issues:
        print(f"[{issue['severity']}] {issue['code']}: {issue['message']}")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

# 尝试从 IR 模块导入，优先从 ae.timeline_ir 取
try:
    from ae.timeline_ir import (
        IRSequence, IRTrack, IRClip, IRTransition,
        IRTrackType, IRTransitionType,
    )
except ImportError:
    from .stubs import (
        IRSequence, IRTrack, IRClip, IRTransition,
        IRTrackType, IRTransitionType,
    )


# ================================================================
#  校验问题定义
# ================================================================

class ValidationIssue:
    """单个校验问题。

    Attributes:
        severity: 严重级别 ("error" | "warning")
        code: 错误码（如 "TIME_OVERLAP", "CLIP_DURATION_ZERO"）
        message: 人类可读的描述
        location: 问题位置信息字典
    """

    def __init__(
        self,
        severity: str,
        code: str,
        message: str,
        location: Optional[Dict[str, Any]] = None,
    ):
        self.severity = severity
        self.code = code
        self.message = message
        self.location = location or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }

    def __repr__(self) -> str:
        return f"[{self.severity.upper()}] {self.code}: {self.message}"


# ================================================================
#  校验函数
# ================================================================

def _check_sequence_params(seq: IRSequence, issues: List[ValidationIssue]) -> None:
    """检查序列基本参数。"""
    if not seq.name or not seq.name.strip():
        issues.append(ValidationIssue(
            severity="error",
            code="SEQUENCE_NAME_EMPTY",
            message="序列名称不能为空",
            location={"field": "sequence.name"},
        ))
    if seq.width <= 0 or seq.width > 16384:
        issues.append(ValidationIssue(
            severity="error",
            code="SEQUENCE_WIDTH_INVALID",
            message=f"序列宽度不合法: {seq.width}（有效范围: 1-16384）",
            location={"field": "sequence.width", "value": seq.width},
        ))
    if seq.height <= 0 or seq.height > 16384:
        issues.append(ValidationIssue(
            severity="error",
            code="SEQUENCE_HEIGHT_INVALID",
            message=f"序列高度不合法: {seq.height}（有效范围: 1-16384）",
            location={"field": "sequence.height", "value": seq.height},
        ))
    if seq.frame_rate <= 0 or seq.frame_rate > 240:
        issues.append(ValidationIssue(
            severity="error",
            code="SEQUENCE_FPS_INVALID",
            message=f"序列帧率不合法: {seq.frame_rate}（有效范围: 1-240）",
            location={"field": "sequence.frame_rate", "value": seq.frame_rate},
        ))
    if not seq.tracks:
        issues.append(ValidationIssue(
            severity="warning",
            code="SEQUENCE_NO_TRACKS",
            message="序列没有任何轨道",
            location={"field": "sequence.tracks"},
        ))


def _check_track_indices(seq: IRSequence, issues: List[ValidationIssue]) -> None:
    """检查轨道索引的唯一性和连续性。"""
    seen_indices: Dict[int, str] = {}
    for track in seq.tracks:
        if track.index in seen_indices:
            issues.append(ValidationIssue(
                severity="error",
                code="TRACK_INDEX_DUPLICATE",
                message=f"轨道索引 {track.index} 重复: "
                        f"与 '{seen_indices[track.index]}' 冲突",
                location={
                    "track_index": track.index,
                    "track_name": track.name,
                    "conflict_with": seen_indices[track.index],
                },
            ))
        else:
            seen_indices[track.index] = track.name or str(track.index)

    # 检查索引连续性（仅当有多个轨道时）
    if len(seq.tracks) > 1:
        sorted_indices = sorted(seen_indices.keys())
        for i in range(len(sorted_indices) - 1):
            if sorted_indices[i + 1] - sorted_indices[i] > 1:
                issues.append(ValidationIssue(
                    severity="warning",
                    code="TRACK_INDEX_GAP",
                    message=f"轨道索引不连续: 从 {sorted_indices[i]} 跳至 {sorted_indices[i + 1]}",
                    location={
                        "from_index": sorted_indices[i],
                        "to_index": sorted_indices[i + 1],
                    },
                ))


def _check_clip_duration(clip: IRClip, prefix: str, issues: List[ValidationIssue]) -> None:
    """检查片段时长合法性。"""
    duration = clip.duration
    if duration <= 0:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_DURATION_ZERO",
            message=f"片段 '{clip.id}' 时长为 {duration:.3f}s，必须为正数",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.duration",
                "value": duration,
            },
        ))


def _check_clip_time(clip: IRClip, prefix: str, issues: List[ValidationIssue]) -> None:
    """检查片段时间属性合法性。"""
    if clip.timeline_in < 0:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_TIME_IN_NEGATIVE",
            message=f"片段 '{clip.id}' 入点 {clip.timeline_in}s 不能为负",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.timeline_in",
                "value": clip.timeline_in,
            },
        ))
    if clip.timeline_out is not None and clip.timeline_out <= clip.timeline_in:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_TIME_OUT_BEFORE_IN",
            message=f"片段 '{clip.id}' 出点 {clip.timeline_out}s 必须大于入点 {clip.timeline_in}s",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.timeline_out",
                "timeline_in": clip.timeline_in,
                "timeline_out": clip.timeline_out,
            },
        ))
    if clip.source_start < 0:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_SOURCE_START_NEGATIVE",
            message=f"片段 '{clip.id}' 源入点 {clip.source_start}s 不能为负",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.source_start",
                "value": clip.source_start,
            },
        ))
    if clip.source_end is not None and clip.source_end <= clip.source_start:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_SOURCE_END_BEFORE_START",
            message=f"片段 '{clip.id}' 源出点 {clip.source_end}s 必须大于源入点 {clip.source_start}s",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.source_end",
                "source_start": clip.source_start,
                "source_end": clip.source_end,
            },
        ))


def _check_clip_source_file(clip: IRClip, prefix: str, issues: List[ValidationIssue]) -> None:
    """检查源文件存在性。"""
    if not clip.source_path or not clip.source_path.strip():
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_SOURCE_PATH_EMPTY",
            message=f"片段 '{clip.id}' 源路径为空",
            location={"clip_id": clip.id, "field": f"{prefix}.source_path"},
        ))
        return

    source = Path(clip.source_path)
    if not source.exists():
        issues.append(ValidationIssue(
            severity="warning",
            code="CLIP_SOURCE_FILE_NOT_FOUND",
            message=f"片段 '{clip.id}' 源文件不存在: {clip.source_path}",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.source_path",
                "path": clip.source_path,
            },
        ))


def _check_clip_transform(clip: IRClip, prefix: str, issues: List[ValidationIssue]) -> None:
    """检查片段变换属性合法性。"""
    if clip.speed <= 0:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_SPEED_NEGATIVE",
            message=f"片段 '{clip.id}' 变速倍率 {clip.speed} 必须为正",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.speed",
                "value": clip.speed,
            },
        ))
    if clip.speed > 100:
        issues.append(ValidationIssue(
            severity="warning",
            code="CLIP_SPEED_EXTREME",
            message=f"片段 '{clip.id}' 变速倍率 {clip.speed}x 极高",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.speed",
                "value": clip.speed,
            },
        ))
    if not (0.0 <= clip.opacity <= 1.0):
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_OPACITY_OUT_OF_RANGE",
            message=f"片段 '{clip.id}' 不透明度 {clip.opacity} 超出 [0, 1] 范围",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.opacity",
                "value": clip.opacity,
            },
        ))
    if clip.scale <= 0:
        issues.append(ValidationIssue(
            severity="error",
            code="CLIP_SCALE_NEGATIVE",
            message=f"片段 '{clip.id}' 缩放 {clip.scale} 必须为正",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.scale",
                "value": clip.scale,
            },
        ))
    if not (0.0 <= clip.position_x <= 1.0):
        issues.append(ValidationIssue(
            severity="warning",
            code="CLIP_POSITION_X_OUT_OF_RANGE",
            message=f"片段 '{clip.id}' 位置X {clip.position_x} 超出归一化范围 [0, 1]",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.position_x",
                "value": clip.position_x,
            },
        ))
    if not (0.0 <= clip.position_y <= 1.0):
        issues.append(ValidationIssue(
            severity="warning",
            code="CLIP_POSITION_Y_OUT_OF_RANGE",
            message=f"片段 '{clip.id}' 位置Y {clip.position_y} 超出归一化范围 [0, 1]",
            location={
                "clip_id": clip.id,
                "field": f"{prefix}.position_y",
                "value": clip.position_y,
            },
        ))


def _check_transition(clip: IRClip, prefix: str, issues: List[ValidationIssue]) -> None:
    """检查转场合法性。"""
    duration = clip.duration

    if clip.transition_in and clip.transition_in.type != IRTransitionType.CUT:
        trans = clip.transition_in
        if trans.duration <= 0:
            issues.append(ValidationIssue(
                severity="error",
                code="TRANSITION_IN_DURATION_ZERO",
                message=f"片段 '{clip.id}' 入转场时长必须为正（当前: {trans.duration}s）",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_in.duration",
                    "value": trans.duration,
                },
            ))
        if trans.duration > duration:
            issues.append(ValidationIssue(
                severity="error",
                code="TRANSITION_IN_DURATION_EXCEEDS_CLIP",
                message=f"片段 '{clip.id}' 入转场时长 {trans.duration}s 超过片段时长 {duration}s",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_in.duration",
                    "transition_duration": trans.duration,
                    "clip_duration": duration,
                },
            ))
        if trans.alignment not in ("center", "start", "end"):
            issues.append(ValidationIssue(
                severity="warning",
                code="TRANSITION_ALIGNMENT_INVALID",
                message=f"片段 '{clip.id}' 入转场对齐方式 '{trans.alignment}' 无效"
                        f"（有效值: center/start/end）",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_in.alignment",
                    "value": trans.alignment,
                },
            ))

    if clip.transition_out and clip.transition_out.type != IRTransitionType.CUT:
        trans = clip.transition_out
        if trans.duration <= 0:
            issues.append(ValidationIssue(
                severity="error",
                code="TRANSITION_OUT_DURATION_ZERO",
                message=f"片段 '{clip.id}' 出转场时长必须为正（当前: {trans.duration}s）",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_out.duration",
                    "value": trans.duration,
                },
            ))
        if trans.duration > duration:
            issues.append(ValidationIssue(
                severity="error",
                code="TRANSITION_OUT_DURATION_EXCEEDS_CLIP",
                message=f"片段 '{clip.id}' 出转场时长 {trans.duration}s 超过片段时长 {duration}s",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_out.duration",
                    "transition_duration": trans.duration,
                    "clip_duration": duration,
                },
            ))
        if trans.alignment not in ("center", "start", "end"):
            issues.append(ValidationIssue(
                severity="warning",
                code="TRANSITION_ALIGNMENT_INVALID",
                message=f"片段 '{clip.id}' 出转场对齐方式 '{trans.alignment}' 无效"
                        f"（有效值: center/start/end）",
                location={
                    "clip_id": clip.id,
                    "field": f"{prefix}.transition_out.alignment",
                    "value": trans.alignment,
                },
            ))


def _check_time_overlap(seq: IRSequence, issues: List[ValidationIssue]) -> None:
    """检查同一轨道内片段的时间重叠"""
    for track in seq.tracks:
        clips_sorted = sorted(track.clips, key=lambda c: c.timeline_in)
        for i in range(len(clips_sorted) - 1):
            c1 = clips_sorted[i]
            c2 = clips_sorted[i + 1]
            c1_end = c1.timeline_out or (c1.timeline_in + c1.duration)
            c2_start = c2.timeline_in
            overlap = c1_end - c2_start
            if overlap > 0.01:
                issues.append(ValidationIssue(
                    severity="warning" if overlap < 0.1 else "error",
                    code="CLIP_TIME_OVERLAP",
                    message=f"轨道[{track.index}] 片段 '{c1.id}' 和 '{c2.id}' "
                            f"时间重叠 {overlap:.3f}s",
                    location={
                        "track_index": track.index,
                        "clip_a": c1.id,
                        "clip_b": c2.id,
                        "overlap_seconds": round(overlap, 3),
                        "clip_a_end": round(c1_end, 3),
                        "clip_b_start": round(c2_start, 3),
                    },
                ))
            gap = c2_start - c1_end
            if gap > 0.01:
                issues.append(ValidationIssue(
                    severity="info",
                    code="CLIP_TIME_GAP",
                    message=f"轨道[{track.index}] 片段 '{c1.id}' 和 '{c2.id}' "
                            f"之间有空隙 {gap:.3f}s",
                    location={
                        "track_index": track.index,
                        "clip_a": c1.id,
                        "clip_b": c2.id,
                        "gap_seconds": round(gap, 3),
                        "clip_a_end": round(c1_end, 3),
                        "clip_b_start": round(c2_start, 3),
                    },
                ))


def _check_markers(seq: IRSequence, issues: List[ValidationIssue]) -> None:
    """检查标记时间边界。"""
    total_duration = seq.total_duration
    for i, marker in enumerate(seq.markers):
        time_seconds = marker.get("time_seconds", 0.0)
        if time_seconds < 0:
            issues.append(ValidationIssue(
                severity="error",
                code="MARKER_TIME_NEGATIVE",
                message=f"标记[{i}] 时间 {time_seconds}s 不能为负",
                location={"marker_index": i, "time_seconds": time_seconds},
            ))
        if total_duration > 0 and time_seconds > total_duration:
            issues.append(ValidationIssue(
                severity="warning",
                code="MARKER_TIME_BEYOND_SEQUENCE",
                message=f"标记[{i}] 时间 {time_seconds}s 超出序列总时长 {total_duration}s",
                location={
                    "marker_index": i,
                    "time_seconds": time_seconds,
                    "sequence_duration": total_duration,
                },
            ))


def _check_fps_consistency(seq: IRSequence, issues: List[ValidationIssue]) -> None:
    """检查各轨道的帧率一致性（基于 timeline_in 的帧对齐）。"""
    # 使用序列帧率作为基准
    fps = seq.frame_rate
    if fps <= 0:
        return

    frame_duration = 1.0 / fps
    for track in seq.tracks:
        for clip in track.clips:
            # 检查 timeline_in 是否对齐到帧边界
            frame_offset = clip.timeline_in / frame_duration
            if abs(frame_offset - round(frame_offset)) > 0.001:
                issues.append(ValidationIssue(
                    severity="warning",
                    code="CLIP_TIME_NOT_FRAME_ALIGNED",
                    message=f"片段 '{clip.id}' 入点 {clip.timeline_in}s "
                            f"未对齐到帧边界（{fps}fps，帧时长 {frame_duration:.4f}s）",
                    location={
                        "clip_id": clip.id,
                        "timeline_in": clip.timeline_in,
                        "frame_rate": fps,
                        "frame_duration": frame_duration,
                    },
                ))
                break


# ================================================================
#  公共 API
# ================================================================

def validate_ir(sequence: IRSequence) -> List[Dict[str, Any]]:
    """校验 IRSequence 的完整性与合规性。

    返回一个包含所有发现问题的问题字典列表，每个问题包含：
    - severity: "error" | "warning" | "info"
    - code: 唯一错误码
    - message: 人类可读的描述
    - location: 问题位置信息

    校验项:
    - SEQUENCE_NAME_EMPTY: 序列名称为空
    - SEQUENCE_WIDTH_INVALID: 序列宽度超出范围
    - SEQUENCE_HEIGHT_INVALID: 序列高度超出范围
    - SEQUENCE_FPS_INVALID: 帧率超出范围
    - SEQUENCE_NO_TRACKS: 没有轨道
    - TRACK_INDEX_DUPLICATE: 轨道索引重复
    - TRACK_INDEX_GAP: 轨道索引不连续
    - CLIP_DURATION_ZERO: 片段时长为零或负
    - CLIP_TIME_IN_NEGATIVE: 入点为负
    - CLIP_TIME_OUT_BEFORE_IN: 出点小于入点
    - CLIP_SOURCE_PATH_EMPTY: 源路径为空
    - CLIP_SOURCE_FILE_NOT_FOUND: 源文件不存在
    - CLIP_SPEED_NEGATIVE: 变速倍率为负
    - CLIP_OPACITY_OUT_OF_RANGE: 不透明度超出范围
    - CLIP_SCALE_NEGATIVE: 缩放为负
    - CLIP_TIME_OVERLAP: 片段时间重叠
    - CLIP_TIME_GAP: 片段之间存在空隙
    - TRANSITION_IN_DURATION_ZERO: 入转场时长为零
    - TRANSITION_IN_DURATION_EXCEEDS_CLIP: 入转场超过片段时长
    - TRANSITION_OUT_DURATION_ZERO: 出转场时长为零
    - TRANSITION_OUT_DURATION_EXCEEDS_CLIP: 出转场超过片段时长
    - TRANSITION_ALIGNMENT_INVALID: 转场对齐方式无效
    - MARKER_TIME_NEGATIVE: 标记时间为负
    - MARKER_TIME_BEYOND_SEQUENCE: 标记超出序列时长
    - CLIP_TIME_NOT_FRAME_ALIGNED: 时间未对齐到帧边界

    Args:
        sequence: 待校验的 IRSequence

    Returns:
        问题字典列表，按 severity 排序（error > warning > info）
    """
    issues: List[ValidationIssue] = []

    # 序列级别检查
    _check_sequence_params(sequence, issues)

    # 轨道索引检查
    _check_track_indices(sequence, issues)

    # 轨道/片段级别检查
    for track in sequence.tracks:
        for i, clip in enumerate(track.clips):
            prefix = f"track[{track.index}].clips[{i}]"

            _check_clip_duration(clip, prefix, issues)
            _check_clip_time(clip, prefix, issues)
            _check_clip_source_file(clip, prefix, issues)
            _check_clip_transform(clip, prefix, issues)
            _check_transition(clip, prefix, issues)

    # 时间重叠检查
    _check_time_overlap(sequence, issues)

    # 标记检查
    _check_markers(sequence, issues)

    # FPS 一致性检查
    _check_fps_consistency(sequence, issues)

    # 按 severity 排序
    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda x: severity_order.get(x.severity, 99))

    return [issue.to_dict() for issue in issues]