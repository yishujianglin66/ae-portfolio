#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timeline IR 数据存根 — 当 ae.timeline_ir 不可用时的最小回退实现
===================================================================

提供与 ae.timeline_ir 兼容的最小 IR 数据结构，确保 Premiere IR 模块
在 ae.timeline_ir 未安装或不可导入时仍能正常工作。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional


# ================================================================
#  枚举定义
# ================================================================

class IRTrackType(str, Enum):
    """IR 轨道类型"""
    VIDEO = "video"
    AUDIO = "audio"
    OVERLAY = "overlay"
    SUBTITLE = "subtitle"
    ADJUSTMENT = "adjustment"


class IREffectCategory(str, Enum):
    """IR 特效分类"""
    COLOR = "color"
    BLUR = "blur"
    DISTORT = "distort"
    STYLIZE = "stylize"
    LIGHT = "light"
    PARTICLE = "particle"
    KEYING = "keying"
    AUDIOFX = "audiofx"


class IRTransitionType(str, Enum):
    """IR 转场类型"""
    CUT = "cut"
    DISSOLVE = "dissolve"
    CROSS_DISSOLVE = "cross_dissolve"
    DIP_TO_BLACK = "dip_to_black"
    DIP_TO_WHITE = "dip_to_white"
    WIPE_LEFT = "wipe_left"
    WIPE_RIGHT = "wipe_right"
    WIPE_UP = "wipe_up"
    WIPE_DOWN = "wipe_down"
    WIPE_IRIS = "wipe_iris"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    WHIP_PAN_LEFT = "whip_pan_left"
    WHIP_PAN_RIGHT = "whip_pan_right"
    GLITCH = "glitch"
    FLASH = "flash"
    PUSH_LEFT = "push_left"
    PUSH_RIGHT = "push_right"
    SLIDE = "slide"


class IRScaleMode(str, Enum):
    """缩放适应模式"""
    FIT = "fit"
    FILL = "fill"
    STRETCH = "stretch"
    NONE = "none"


# ================================================================
#  核心数据结构
# ================================================================

@dataclass
class IREffect:
    """IR 特效 — 应用于一段 Clip 区间的视觉/音频效果"""
    name: str
    category: IREffectCategory = IREffectCategory.COLOR
    match_name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    keyframes: Optional[List[Dict[str, Any]]] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "category": self.category.value,
            "params": self.params,
            "enabled": self.enabled,
        }
        if self.match_name:
            d["match_name"] = self.match_name
        if self.keyframes:
            d["keyframes"] = self.keyframes
        return d


@dataclass
class IRTransition:
    """IR 转场 — 两个 Clip 之间的过渡效果"""
    type: IRTransitionType = IRTransitionType.CUT
    duration: float = 0.0
    alignment: str = "center"
    params: Dict[str, Any] = field(default_factory=dict)
    easing: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.type.value,
            "duration": self.duration,
            "alignment": self.alignment,
        }
        if self.params:
            d["params"] = self.params
        if self.easing:
            d["easing"] = self.easing
        return d


@dataclass
class IRMarker:
    """IR 标记 — 时间线上的标记点"""
    time_seconds: float = 0.0
    name: str = ""
    comment: str = ""
    duration_seconds: float = 0.0
    color: str = "blue"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_seconds": self.time_seconds,
            "name": self.name,
            "comment": self.comment,
            "duration_seconds": self.duration_seconds,
            "color": self.color,
        }


@dataclass
class IRClip:
    """IR Clip — 时间线中的单一素材片段"""
    id: str
    source_path: str

    source_start: float = 0.0
    source_end: Optional[float] = None
    timeline_in: float = 0.0
    timeline_out: Optional[float] = None

    scale: float = 1.0
    position_x: float = 0.5
    position_y: float = 0.5
    rotation: float = 0.0
    opacity: float = 1.0
    anchor_x: float = 0.5
    anchor_y: float = 0.5

    scale_mode: IRScaleMode = IRScaleMode.FIT

    speed: float = 1.0
    is_reversed: bool = False
    freeze_frame_at: Optional[float] = None

    transition_in: Optional[IRTransition] = None
    transition_out: Optional[IRTransition] = None

    effects: List[IREffect] = field(default_factory=list)

    track_index: int = 0
    track_type: IRTrackType = IRTrackType.VIDEO
    label: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    children: Optional[List[IRClip]] = None

    @property
    def duration(self) -> float:
        """计算片段在时间线上的有效时长"""
        if self.timeline_out is not None:
            return max(0.0, self.timeline_out - self.timeline_in)
        src_dur = (self.source_end or 0) - self.source_start
        return max(0.0, src_dur / max(self.speed, 0.01))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "source_path": self.source_path,
            "source_start": self.source_start,
            "timeline_in": self.timeline_in,
            "duration": self.duration,
            "scale": self.scale,
            "position_x": self.position_x,
            "position_y": self.position_y,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "speed": self.speed,
            "is_reversed": self.is_reversed,
            "track_index": self.track_index,
            "track_type": self.track_type.value,
        }
        if self.source_end is not None:
            d["source_end"] = self.source_end
        if self.timeline_out is not None:
            d["timeline_out"] = self.timeline_out
        if self.scale_mode != IRScaleMode.FIT:
            d["scale_mode"] = self.scale_mode.value
        if self.freeze_frame_at is not None:
            d["freeze_frame_at"] = self.freeze_frame_at
        if self.anchor_x != 0.5 or self.anchor_y != 0.5:
            d["anchor_x"] = self.anchor_x
            d["anchor_y"] = self.anchor_y
        if self.label:
            d["label"] = self.label
        if self.tags:
            d["tags"] = self.tags
        if self.transition_in:
            d["transition_in"] = self.transition_in.to_dict()
        if self.transition_out:
            d["transition_out"] = self.transition_out.to_dict()
        if self.effects:
            d["effects"] = [e.to_dict() for e in self.effects]
        if self.metadata:
            d["metadata"] = self.metadata
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d


@dataclass
class IRTrack:
    """IR Track — 单条轨道"""
    index: int
    type: IRTrackType = IRTrackType.VIDEO
    name: str = ""
    clips: List[IRClip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    target_language: Optional[str] = None

    @property
    def total_duration(self) -> float:
        """轨道总时长"""
        if not self.clips:
            return 0.0
        return max(
            (c.timeline_out or (c.timeline_in + c.duration))
            for c in self.clips
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "type": self.type.value,
            "name": self.name or f"Track_{self.index}",
            "clips": [c.to_dict() for c in self.clips],
            "muted": self.muted,
            "locked": self.locked,
        }


@dataclass
class IRSequence:
    """IR Sequence — 完整的合成/序列"""
    name: str = "Untitled"
    width: int = 1920
    height: int = 1080
    frame_rate: float = 30.0
    pixel_aspect_ratio: float = 1.0
    sample_rate: int = 48000
    audio_channels: int = 2

    tracks: List[IRTrack] = field(default_factory=list)
    master_audio_track: Optional[IRTrack] = None

    markers: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> float:
        """序列总时长"""
        durations = [t.total_duration for t in self.tracks]
        if not durations:
            return 0.0
        return max(durations)

    def get_track(self, index: int, track_type: Optional[IRTrackType] = None) -> Optional[IRTrack]:
        """按索引/类型查找轨道"""
        for t in self.tracks:
            if t.index == index:
                if track_type is None or t.type == track_type:
                    return t
        return None

    def get_clips_by_type(self, track_type: IRTrackType) -> List[IRClip]:
        """获取某类型轨道中的所有片段"""
        clips: List[IRClip] = []
        for t in self.tracks:
            if t.type == track_type:
                clips.extend(t.clips)
        return clips

    def add_track(self, track: IRTrack) -> None:
        """添加轨道"""
        existing = [t.index for t in self.tracks]
        if track.index in existing:
            track.index = max(existing) + 1
        self.tracks.append(track)
        self.tracks.sort(key=lambda t: t.index)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "pixel_aspect_ratio": self.pixel_aspect_ratio,
            "sample_rate": self.sample_rate,
            "audio_channels": self.audio_channels,
            "tracks": [t.to_dict() for t in self.tracks],
            "total_duration": self.total_duration,
        }
        if self.master_audio_track:
            d["master_audio_track"] = self.master_audio_track.to_dict()
        if self.markers:
            d["markers"] = self.markers
        if self.metadata:
            d["metadata"] = self.metadata
        return d


# ================================================================
#  Schema 校验（存根）
# ================================================================

class IRValidationError(Exception):
    """IR Schema 校验错误"""
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(f"[{path}] {message}")


class IRValidationResult:
    """校验结果容器"""
    def __init__(self):
        self.errors: List[IRValidationError] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(IRValidationError(path, message))

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def raise_if_invalid(self) -> None:
        if self.errors:
            raise IRValidationError(
                "sequence",
                f"校验失败，{len(self.errors)} 个错误:\n"
                + "\n".join(f"  - [{e.path}] {e.message}" for e in self.errors)
            )

    def summary(self) -> str:
        lines: List[str] = []
        if self.is_valid:
            lines.append("IR 校验通过 ✓")
        else:
            lines.append(f"IR 校验失败 ✗ ({len(self.errors)} 错误)")
        for e in self.errors:
            lines.append(f"  ✗ [{e.path}] {e.message}")
        for w in self.warnings:
            lines.append(f"  ⚠ {w}")
        return "\n".join(lines)


def validate_ir(sequence: IRSequence) -> IRValidationResult:
    """
    校验 IRSequence 的完整性与合规性（存根实现）。

    仅检查基本参数，完整校验见 ae.timeline_ir.validate_ir。

    Args:
        sequence: 待校验的 IRSequence

    Returns:
        IRValidationResult 校验结果
    """
    result = IRValidationResult()

    if not sequence.name or not sequence.name.strip():
        result.add_error("sequence.name", "序列名不能为空")
    if sequence.width <= 0 or sequence.width > 16384:
        result.add_error("sequence.width", f"分辨率宽度不合法: {sequence.width}")
    if sequence.height <= 0 or sequence.height > 16384:
        result.add_error("sequence.height", f"分辨率高度不合法: {sequence.height}")
    if sequence.frame_rate <= 0 or sequence.frame_rate > 240:
        result.add_error("sequence.frame_rate", f"帧率不合法: {sequence.frame_rate}")
    if not sequence.tracks:
        result.add_warning("序列没有轨道")

    seen_indices: Dict[int, str] = {}
    for track in sequence.tracks:
        if track.index in seen_indices:
            result.add_error(
                f"track[{track.index}]",
                f"轨道索引重复: 与 track[{seen_indices[track.index]}] 冲突"
            )
        else:
            seen_indices[track.index] = track.name or str(track.index)

        for i, clip in enumerate(track.clips):
            prefix = f"track[{track.index}].clips[{i}]"
            if not clip.id:
                result.add_error(f"{prefix}.id", "Clip ID 不能为空")
            if not clip.source_path or not clip.source_path.strip():
                result.add_error(f"{prefix}.source_path", "源路径不能为空")
            if clip.timeline_in < 0:
                result.add_error(f"{prefix}.timeline_in", f"时间线入点不能为负: {clip.timeline_in}")
            if clip.timeline_out is not None and clip.timeline_out <= clip.timeline_in:
                result.add_error(
                    f"{prefix}",
                    f"时间线出点 ({clip.timeline_out}) 必须大于入点 ({clip.timeline_in})"
                )
            if clip.speed <= 0:
                result.add_error(f"{prefix}.speed", f"变速倍率必须为正: {clip.speed}")
            if not (0.0 <= clip.opacity <= 1.0):
                result.add_error(f"{prefix}.opacity", f"不透明度必须在 [0, 1] 区间: {clip.opacity}")

    return result


def export_to_pr_json(sequence: IRSequence, sequence_name: Optional[str] = None) -> Dict[str, Any]:
    """
    将 IRSequence 导出为 Premiere Pro MCP 兼容格式（存根实现）。

    Args:
        sequence: IR 序列
        sequence_name: PR 序列名称

    Returns:
        PR MCP 兼容的 JSON dict
    """
    name = sequence_name or sequence.name or "IR_Sequence"

    clips: List[Dict[str, Any]] = []
    audio_clips: List[Dict[str, Any]] = []

    for track in sequence.tracks:
        for c in track.clips:
            item: Dict[str, Any] = {
                "media_path": c.source_path,
                "track_index": c.track_index + 1,
                "timeline_in": round(c.timeline_in, 3),
                "duration": round(c.duration, 3),
            }
            if c.source_start > 0:
                item["source_in"] = round(c.source_start, 3)
            if c.speed != 1.0:
                item["speed"] = c.speed
            if c.opacity < 1.0:
                item["opacity"] = round(c.opacity, 3)

            if track.type == IRTrackType.AUDIO:
                audio_clips.append(item)
            else:
                clips.append(item)

    payload: Dict[str, Any] = {
        "sequence_name": name,
        "width": sequence.width,
        "height": sequence.height,
        "frame_rate": sequence.frame_rate,
        "clips": clips,
    }
    if audio_clips:
        payload["audio_clips"] = audio_clips
    return payload


def export_to_ae_jsx(sequence: IRSequence) -> str:
    """
    将 IRSequence 导出为 AE ExtendScript（存根实现）。

    Args:
        sequence: IR 序列

    Returns:
        ExtendScript 源码字符串
    """
    lines: List[str] = []
    lines.append("// Auto-generated by Premiere IR Stubs (ae.timeline_ir not available)")
    lines.append(f"// Sequence: {sequence.name}")
    lines.append("")
    lines.append("(function() {")
    lines.append(f'    var comp = app.project.items.addComp("{sequence.name}",')
    lines.append(f"        {sequence.width}, {sequence.height}, {sequence.pixel_aspect_ratio},")
    lines.append(f"        {sequence.total_duration}, {int(sequence.frame_rate)});")
    lines.append("")
    lines.append("    app.endUndoGroup();")
    lines.append("})();")
    return "\n".join(lines)