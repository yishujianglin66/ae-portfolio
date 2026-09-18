#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Timeline IR (Intermediate Representation) — 方向3：时间线中间表示层
====================================================================

定义统一的时间线中间表示 Schema，实现：
- 多轨时间线结构的数据模型 (IRTrack / IRClip / IREffect / IRTransition)
- 严格的 Schema 校验 (validate_ir)
- 多目标导出：
  - → PR MCP JSON (add_to_timeline 兼容格式)
  - → AE JSX ExtendScript (合成创建脚本)
  - → AAF / FCPXML 占位 (后续扩展)

架构定位:
    感知层 (scene/beat/subtitle) → IR → 落轨层 (PR MCP / AE JSX)
    timeline_ir.py 处于感知层与落轨层之间的标准化数据层。

依赖:
    无外部依赖，仅使用 Python 标准库 dataclasses / typing / json / enum。
    与 timeline_composer.py 互补：timeline_composer 负责"编排"逻辑，
    本模块负责 IR 数据定义、校验与格式导出。

用法:
    from ae.timeline_ir import (
        IRTrack, IRClip, IREffect, IRTransition, IRSchema,
        validate_ir, export_to_pr_json, export_to_ae_jsx,
    )
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

# ================================================================
#  枚举定义
# ================================================================

class IRTrackType(str, Enum):
    """IR 轨道类型"""
    VIDEO = "video"          # 视频主轨
    AUDIO = "audio"          # 音频轨
    OVERLAY = "overlay"      # 覆盖轨 (画中画/贴纸)
    SUBTITLE = "subtitle"    # 字幕轨
    ADJUSTMENT = "adjustment"  # 调整图层


class IREffectCategory(str, Enum):
    """IR 特效分类"""
    COLOR = "color"          # 调色 / LUT
    BLUR = "blur"            # 模糊
    DISTORT = "distort"      # 扭曲
    STYLIZE = "stylize"      # 风格化
    LIGHT = "light"          # 光效
    PARTICLE = "particle"    # 粒子
    KEYING = "keying"        # 抠像
    AUDIOFX = "audiofx"      # 音频特效


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
    FIT = "fit"              # 等比缩放至适配画面 (保留黑边)
    FILL = "fill"            # 等比缩放至填满画面 (裁切溢出)
    STRETCH = "stretch"      # 拉伸至匹配画面 (不保留比例)
    NONE = "none"            # 原始尺寸


# ================================================================
#  核心数据结构
# ================================================================

@dataclass
class IREffect:
    """IR 特效 — 应用于一段 Clip 区间的视觉/音频效果"""
    name: str                          # 效果名称 (如 "Lens Flare", "Gaussian Blur")
    category: IREffectCategory = IREffectCategory.COLOR
    match_name: str | None = None   # AE match_name (如 "ADBE Lens Flare")
    params: dict[str, Any] = field(default_factory=dict)
    keyframes: list[dict[str, Any]] | None = None  # 关键帧动画
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        d = {
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
    duration: float = 0.0             # 转场时长 (秒)
    alignment: str = "center"         # center / start / end
    params: dict[str, Any] = field(default_factory=dict)
    easing: str | None = None      # 缓动函数

    def to_dict(self) -> dict[str, Any]:
        d = {
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
class IRClip:
    """IR Clip — 时间线中的单一素材片段"""
    id: str                            # 唯一标识符
    source_path: str                   # 源文件路径 (或占位符)

    # 时间属性
    source_start: float = 0.0          # 源入点 (秒)
    source_end: float | None = None  # 源出点 (秒)
    timeline_in: float = 0.0           # 时间线入点 (秒)
    timeline_out: float | None = None  # 时间线出点 (秒)

    # 变换属性 (归一化坐标，范围 0.0-1.0)
    scale: float = 1.0
    position_x: float = 0.5
    position_y: float = 0.5
    rotation: float = 0.0
    opacity: float = 1.0
    anchor_x: float = 0.5
    anchor_y: float = 0.5

    scale_mode: IRScaleMode = IRScaleMode.FIT

    # 时间效果
    speed: float = 1.0                 # 变速倍率
    is_reversed: bool = False
    freeze_frame_at: float | None = None  # 定格帧时间

    # 转场
    transition_in: IRTransition | None = None
    transition_out: IRTransition | None = None

    # 特效栈
    effects: list[IREffect] = field(default_factory=list)

    # 元数据
    track_index: int = 0
    track_type: IRTrackType = IRTrackType.VIDEO
    label: str | None = None         # 可读标签
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 子合成 (嵌套序列)
    children: list[IRClip] | None = None

    @property
    def duration(self) -> float:
        """计算片段在时间线上的有效时长"""
        if self.timeline_out is not None:
            return max(0.0, self.timeline_out - self.timeline_in)
        src_dur = (self.source_end or 0) - self.source_start
        return max(0.0, src_dur / max(self.speed, 0.01))

    def to_dict(self) -> dict[str, Any]:
        d = {
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IRClip:
        """从字典重建 IRClip"""
        d = deepcopy(data)
        if "track_type" in d and isinstance(d["track_type"], str):
            d["track_type"] = IRTrackType(d["track_type"])
        if "scale_mode" in d and isinstance(d["scale_mode"], str):
            d["scale_mode"] = IRScaleMode(d["scale_mode"])
        if "transition_in" in d and isinstance(d["transition_in"], dict):
            d["transition_in"] = IRTransition(
                type=IRTransitionType(d["transition_in"].get("type", "cut")),
                duration=d["transition_in"].get("duration", 0.0),
                alignment=d["transition_in"].get("alignment", "center"),
                params=d["transition_in"].get("params", {}),
                easing=d["transition_in"].get("easing"),
            )
        if "transition_out" in d and isinstance(d["transition_out"], dict):
            d["transition_out"] = IRTransition(
                type=IRTransitionType(d["transition_out"].get("type", "cut")),
                duration=d["transition_out"].get("duration", 0.0),
                alignment=d["transition_out"].get("alignment", "center"),
                params=d["transition_out"].get("params", {}),
                easing=d["transition_out"].get("easing"),
            )
        if "effects" in d:
            effects = []
            for e in d["effects"]:
                if isinstance(e, dict):
                    effects.append(IREffect(
                        name=e.get("name", ""),
                        category=IREffectCategory(e.get("category", "color")),
                        match_name=e.get("match_name"),
                        params=e.get("params", {}),
                        keyframes=e.get("keyframes"),
                        enabled=e.get("enabled", True),
                    ))
                else:
                    effects.append(e)
            d["effects"] = effects
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class IRTrack:
    """IR Track — 单条轨道"""
    index: int
    type: IRTrackType = IRTrackType.VIDEO
    name: str = ""
    clips: list[IRClip] = field(default_factory=list)
    muted: bool = False
    locked: bool = False
    target_language: str | None = None  # 字幕轨专用

    @property
    def total_duration(self) -> float:
        """轨道总时长"""
        if not self.clips:
            return 0.0
        return max(
            (c.timeline_out or (c.timeline_in + c.duration))
            for c in self.clips
        )

    def to_dict(self) -> dict[str, Any]:
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

    tracks: list[IRTrack] = field(default_factory=list)
    master_audio_track: IRTrack | None = None

    markers: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_duration(self) -> float:
        """序列总时长"""
        durations = [t.total_duration for t in self.tracks]
        if not durations:
            return 0.0
        return max(durations)

    def get_track(self, index: int, track_type: IRTrackType | None = None) -> IRTrack | None:
        """按索引/类型查找轨道"""
        for t in self.tracks:
            if t.index == index:
                if track_type is None or t.type == track_type:
                    return t
        return None

    def get_clips_by_type(self, track_type: IRTrackType) -> list[IRClip]:
        """获取某类型轨道中的所有片段"""
        clips = []
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

    def to_dict(self) -> dict[str, Any]:
        d = {
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IRSequence:
        """从字典重建 IRSequence"""
        d = deepcopy(data)
        if "tracks" in d:
            tracks = []
            for t in d["tracks"]:
                if isinstance(t, dict):
                    track_data = deepcopy(t)
                    if isinstance(track_data.get("type"), str):
                        track_data["type"] = IRTrackType(track_data["type"])
                    if "clips" in track_data:
                        track_data["clips"] = [
                            IRClip.from_dict(c) if isinstance(c, dict) else c
                            for c in track_data["clips"]
                        ]
                    tracks.append(IRTrack(**{
                        k: v for k, v in track_data.items()
                        if k in IRTrack.__dataclass_fields__
                    }))
                else:
                    tracks.append(t)
            d["tracks"] = tracks
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ================================================================
#  Schema 校验
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
        self.errors: list[IRValidationError] = []
        self.warnings: list[str] = []

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
                f"校验失败，{len(self.errors)} 个错误:\n" +
                "\n".join(f"  - [{e.path}] {e.message}" for e in self.errors)
            )

    def summary(self) -> str:
        lines = []
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
    校验 IRSequence 的完整性与合规性。

    检查项:
    - 序列基本参数合理性
    - 轨道索引无重复
    - Clip 时间区间有效 (timeline_in >= 0, timeline_out > timeline_in)
    - source_path 不为空
    - 转场时长不超过 Clip 时长
    - 特效参数合法性

    Args:
        sequence: 待校验的 IRSequence

    Returns:
        IRValidationResult 校验结果
    """
    result = IRValidationResult()

    # --- 序列级别检查 ---
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

    # --- 轨道级别检查 ---
    seen_indices: dict[int, str] = {}
    for track in sequence.tracks:
        if track.index in seen_indices:
            result.add_error(
                f"track[{track.index}]",
                f"轨道索引重复: 与 track[{seen_indices[track.index]}] 冲突"
            )
        else:
            seen_indices[track.index] = track.name or str(track.index)

        # --- Clip 级别检查 ---
        for i, clip in enumerate(track.clips):
            prefix = f"track[{track.index}].clips[{i}]"

            # 必填字段
            if not clip.id:
                result.add_error(f"{prefix}.id", "Clip ID 不能为空")
            if not clip.source_path or not clip.source_path.strip():
                result.add_error(f"{prefix}.source_path", "源路径不能为空")

            # 时间合法性
            if clip.timeline_in < 0:
                result.add_error(
                    f"{prefix}.timeline_in",
                    f"时间线入点不能为负: {clip.timeline_in}"
                )
            if clip.timeline_out is not None and clip.timeline_out <= clip.timeline_in:
                result.add_error(
                    f"{prefix}",
                    f"时间线出点 ({clip.timeline_out}) 必须大于入点 ({clip.timeline_in})"
                )

            # 变速合法性
            if clip.speed <= 0:
                result.add_error(f"{prefix}.speed", f"变速倍率必须为正: {clip.speed}")
            if clip.speed > 100:
                result.add_warning(f"{prefix}.speed 很高 ({clip.speed}x)")

            # 变换合法性
            if not (0.0 <= clip.opacity <= 1.0):
                result.add_error(f"{prefix}.opacity", f"不透明度必须在 [0, 1] 区间: {clip.opacity}")
            if clip.scale <= 0:
                result.add_error(f"{prefix}.scale", f"缩放必须为正: {clip.scale}")

            # 转场时长检查
            clip_dur = clip.duration
            if clip.transition_in and clip.transition_in.duration > clip_dur:
                result.add_error(
                    f"{prefix}.transition_in",
                    f"入转场时长 ({clip.transition_in.duration}s) 超过 Clip 时长 ({clip_dur}s)"
                )
            if clip.transition_out and clip.transition_out.duration > clip_dur:
                result.add_error(
                    f"{prefix}.transition_out",
                    f"出转场时长 ({clip.transition_out.duration}s) 超过 Clip 时长 ({clip_dur}s)"
                )

            # 子合成递推检查
            if clip.children:
                for j, child in enumerate(clip.children):
                    child_prefix = f"{prefix}.children[{j}]"
                    if not child.id:
                        result.add_error(f"{child_prefix}.id", "子 Clip ID 不能为空")

    return result


# ================================================================
#  导出器
# ================================================================

def export_to_pr_json(sequence: IRSequence, sequence_name: str | None = None) -> dict[str, Any]:
    """
    将 IRSequence 导出为 Premiere Pro MCP add_to_timeline 兼容格式。

    Args:
        sequence: IR 序列
        sequence_name: PR 序列名称 (默认取 sequence.name)

    Returns:
        PR MCP 兼容的 JSON dict
    """
    name = sequence_name or sequence.name or "IR_Sequence"

    def _clip_to_pr(c: IRClip) -> dict[str, Any]:
        item: dict[str, Any] = {
            "media_path": c.source_path,
            "track_index": c.track_index + 1,  # PR 轨索引从 1 开始
            "timeline_in": round(c.timeline_in, 3),
            "duration": round(c.duration, 3),
        }
        if c.source_start > 0:
            item["source_in"] = round(c.source_start, 3)
        if c.speed != 1.0:
            item["speed"] = c.speed
        if c.is_reversed:
            item["reversed"] = True
        if c.opacity < 1.0:
            item["opacity"] = round(c.opacity, 3)
        if c.scale != 1.0:
            item["scale"] = round(c.scale, 3)
        if c.position_x != 0.5 or c.position_y != 0.5:
            item["position"] = [round(c.position_x, 3), round(c.position_y, 3)]
        if c.transition_in and c.transition_in.type != IRTransitionType.CUT:
            item["transition_in"] = c.transition_in.to_dict()
        if c.transition_out and c.transition_out.type != IRTransitionType.CUT:
            item["transition_out"] = c.transition_out.to_dict()
        if c.effects:
            item["effects"] = [e.to_dict() for e in c.effects]
        if c.label:
            item["label"] = c.label
        return item

    clips: list[dict[str, Any]] = []
    audio_clips: list[dict[str, Any]] = []
    for track in sequence.tracks:
        for clip in track.clips:
            if track.type == IRTrackType.AUDIO:
                audio_clips.append(_clip_to_pr(clip))
            else:
                clips.append(_clip_to_pr(clip))

    payload: dict[str, Any] = {
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
    将 IRSequence 导出为 AE ExtendScript (.jsx)，用于在 AE 中创建合成。

    Args:
        sequence: IR 序列

    Returns:
        ExtendScript 源码字符串
    """
    lines: list[str] = []
    lines.append("// Auto-generated by AE-Knowledge-Vault Timeline IR Exporter")
    lines.append(f"// Sequence: {sequence.name}")
    lines.append(f"// Resolution: {sequence.width}x{sequence.height} @ {sequence.frame_rate}fps")
    lines.append(f"// Duration: {sequence.total_duration:.2f}s")
    lines.append("")

    # 创建工程
    lines.append("(function() {")
    lines.append('    app.beginUndoGroup("Import IR Sequence");')
    lines.append("")
    lines.append(f'    var comp = app.project.items.addComp("{sequence.name}",')
    lines.append(f"        {sequence.width}, {sequence.height}, {sequence.pixel_aspect_ratio},")
    lines.append(f"        {sequence.total_duration}, {int(sequence.frame_rate)});")
    lines.append("")

    # 创建轨道图层
    for track in sequence.tracks:
        lines.append(f"    // --- Track {track.index}: {track.type.value} ---")
        for clip in track.clips:
            var_name = f"layer_{clip.id.replace('-', '_').replace('.', '_')}"
            lines.append(f"    // Clip: {clip.id}")
            if clip.source_path:
                escaped_path = clip.source_path.replace("\\", "\\\\")
                lines.append(
                    f'    var {var_name} = comp.layers.add('
                    f'app.project.importFile(new ImportOptions(File("{escaped_path}"))));'
                )
            else:
                # 纯色占位
                lines.append(
                    f'    var {var_name} = comp.layers.addSolid('
                    f'[1.0, 1.0, 1.0], "Placeholder_{clip.id}", '
                    f'{sequence.width}, {sequence.height}, 1.0);'
                )

            # 时间属性
            lines.append(f"    {var_name}.startTime = {clip.timeline_in:.3f};")
            lines.append(f"    {var_name}.outPoint = {(clip.timeline_in + clip.duration):.3f};")

            # 变换属性
            lines.append(f"    {var_name}.transform.position.setValue(["
                         f"{clip.position_x * sequence.width:.1f}, "
                         f"{clip.position_y * sequence.height:.1f}]);")
            lines.append(f"    {var_name}.transform.scale.setValue(["
                         f"{clip.scale * 100:.1f}, {clip.scale * 100:.1f}]);")
            lines.append(f"    {var_name}.transform.rotation.setValue({clip.rotation});")
            lines.append(f"    {var_name}.transform.opacity.setValue({clip.opacity * 100:.0f});")

            # 变速
            if clip.speed != 1.0:
                lines.append(f"    {var_name}.stretch = {100 / clip.speed:.1f};")

            # 反转
            if clip.is_reversed:
                lines.append(f"    {var_name}.timeRemapEnabled = true;")
                src_end = clip.source_end if clip.source_end is not None else clip.source_start + clip.duration * max(clip.speed, 0.01)
                lines.append(f"    var {var_name}_remap = {var_name}.timeRemap;")
                lines.append(f"    {var_name}_remap.setValueAtTime({var_name}.startTime, {src_end:.3f});")
                lines.append(f"    {var_name}_remap.setValueAtTime({var_name}.startTime + {var_name}.duration, {clip.source_start:.3f});")

            lines.append("")

    lines.append("    app.endUndoGroup();")
    lines.append("})();")
    return "\n".join(lines)


def export_to_dict(sequence: IRSequence) -> dict[str, Any]:
    """导出为标准 JSON 字典"""
    return sequence.to_dict()


def export_to_json(sequence: IRSequence, indent: int = 2) -> str:
    """导出为标准 JSON 字符串"""
    return json.dumps(sequence.to_dict(), ensure_ascii=False, indent=indent)


def export_timeline_summary(sequence: IRSequence) -> str:
    """生成人类可读的时间线摘要"""
    lines = [
        f"序列: {sequence.name}",
        f"分辨率: {sequence.width}x{sequence.height} @ {sequence.frame_rate}fps",
        f"总时长: {sequence.total_duration:.2f}s",
        f"轨道数: {len(sequence.tracks)}",
    ]
    total_clips = 0
    for track in sequence.tracks:
        clips = track.clips
        total_clips += len(clips)
        dur = track.total_duration
        lines.append(f"  Track[{track.index}] {track.type.value}: {len(clips)} clips, {dur:.2f}s")
        for clip in clips:
            fx = f" ({len(clip.effects)} fx)" if clip.effects else ""
            trans = ""
            if clip.transition_in and clip.transition_in.type != IRTransitionType.CUT:
                trans += f" <{clip.transition_in.type.value}"
            if clip.transition_out and clip.transition_out.type != IRTransitionType.CUT:
                trans += f" >{clip.transition_out.type.value}"
            lines.append(
                f"    [{clip.id}] {clip.source_path} "
                f"@{clip.timeline_in:.1f}s dur={clip.duration:.1f}s"
                f"{fx}{trans}"
            )
    lines.append(f"总片段数: {total_clips}")
    return "\n".join(lines)
