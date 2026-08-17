#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Subtitle Product — 方向5：字幕产品化管线 (阶段 B 骨架)
==========================================================

在现有 subtitle_system.py 之上构建产品级字幕管线：
- 字幕解析 (SRT/VTT/ASS) → 标准化中间格式
- 字幕样式推荐引擎 (基于内容风格)
- 多风格字幕预设 (抖音风/B站风/电影风/极简风)
- 字幕时间优化 (防重叠 / 最小间隔 / 速度自适应)
- 导出为 IR 字幕轨 (IRTrack + IRClip)

架构定位:
    承接 whisper_subtitle.py / subtitle_system.py 的输出，
    生成标准化的字幕 IR 数据，供 e2e_pipeline 和 timeline_ir 消费。

依赖:
    ae.timeline_ir       — IRTrack / IRClip / IRTrackType
    ae.subtitle_system   — SubtitleParser / SubtitleItem / SubtitleStyle
    ae.whisper_subtitle  — WhisperSubtitleEngine (可选)

用法:
    from ae.subtitle_product import SubtitlePipeline, SubtitleStyler
    pipeline = SubtitlePipeline()
    sub_track = pipeline.process_srt("subtitles.srt", style="bilibili")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple

from .timeline_ir import IRTrack, IRClip, IRTrackType


# ================================================================
#  枚举定义
# ================================================================

class SubtitlePresetName(str, Enum):
    """字幕预设名称"""
    DOUYIN = "douyin"        # 抖音风 — 大字号 / 描边 / 弹跳动画
    BILIBILI = "bilibili"    # B站风 — 中等字号 / 半透明背景 / 淡入
    CINEMATIC = "cinematic"  # 电影风 — 底部居中 / 细字体 / 淡入淡出
    MINIMAL = "minimal"      # 极简风 — 小字号 / 无描边 / 无动画
    GAMING = "gaming"        # 游戏风 — 粗体 / 霓虹边框 / 震动
    NEWS = "news"            # 新闻风 — 标准字号 / 底部对齐 / 无动画


class SubtitleLanguage(str, Enum):
    """字幕语言"""
    ZH = "zh"
    EN = "en"
    JA = "ja"
    KO = "ko"
    ZH_EN = "zh-en"  # 中英双语


# ================================================================
#  字幕样式定义
# ================================================================

@dataclass
class SubtitleStylePreset:
    """字幕样式预设模板"""
    name: str
    font_family: str = "Arial"
    font_size: int = 48
    font_color: List[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    stroke_color: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    stroke_width: float = 2.0
    background_enabled: bool = False
    background_color: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.6])
    background_padding: int = 10
    glow_enabled: bool = False
    glow_color: List[float] = field(default_factory=lambda: [0.0, 0.5, 1.0])
    glow_radius: float = 15.0
    position_y: float = 0.85
    alignment: str = "center"
    line_spacing: float = 1.5
    animation_in: str = "none"      # none / fade / slide_up / bounce
    animation_out: str = "none"
    animation_duration: float = 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "font_family": self.font_family,
            "font_size": self.font_size,
            "font_color": self.font_color,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
            "background_enabled": self.background_enabled,
            "background_color": self.background_color,
            "background_padding": self.background_padding,
            "glow_enabled": self.glow_enabled,
            "glow_color": self.glow_color,
            "glow_radius": self.glow_radius,
            "position_y": self.position_y,
            "alignment": self.alignment,
            "line_spacing": self.line_spacing,
            "animation_in": self.animation_in,
            "animation_out": self.animation_out,
            "animation_duration": self.animation_duration,
        }


# ================================================================
#  内置预设
# ================================================================

_BUILTIN_PRESETS: Dict[str, SubtitleStylePreset] = {
    "douyin": SubtitleStylePreset(
        name="抖音风",
        font_family="PingFang SC",
        font_size=56,
        font_color=[1.0, 1.0, 1.0],
        stroke_color=[0.0, 0.0, 0.0],
        stroke_width=4.0,
        animation_in="bounce",
        animation_out="fade",
        animation_duration=0.25,
    ),
    "bilibili": SubtitleStylePreset(
        name="B站风",
        font_family="PingFang SC",
        font_size=42,
        font_color=[1.0, 1.0, 1.0],
        stroke_color=[0.0, 0.0, 0.0],
        stroke_width=2.5,
        background_enabled=True,
        background_color=[0.0, 0.0, 0.0, 0.55],
        background_padding=8,
        animation_in="fade",
        animation_duration=0.2,
    ),
    "cinematic": SubtitleStylePreset(
        name="电影风",
        font_family="Noto Serif SC",
        font_size=38,
        font_color=[0.95, 0.95, 0.95],
        stroke_color=[0.1, 0.1, 0.1],
        stroke_width=1.5,
        position_y=0.88,
        animation_in="fade",
        animation_duration=0.5,
    ),
    "minimal": SubtitleStylePreset(
        name="极简风",
        font_family="Helvetica Neue",
        font_size=32,
        font_color=[0.9, 0.9, 0.9],
        stroke_width=0.0,
        position_y=0.90,
        animation_in="none",
    ),
    "gaming": SubtitleStylePreset(
        name="游戏风",
        font_family="Impact",
        font_size=52,
        font_color=[1.0, 0.9, 0.0],
        stroke_color=[0.0, 0.0, 0.0],
        stroke_width=5.0,
        glow_enabled=True,
        glow_color=[0.0, 0.8, 1.0],
        glow_radius=20.0,
        animation_in="slide_up",
        animation_duration=0.2,
    ),
    "news": SubtitleStylePreset(
        name="新闻风",
        font_family="PingFang SC",
        font_size=40,
        font_color=[1.0, 1.0, 1.0],
        stroke_color=[0.0, 0.0, 0.0],
        stroke_width=2.0,
        position_y=0.92,
        alignment="left",
        animation_in="none",
    ),
}


# ================================================================
#  字幕数据容器
# ================================================================

@dataclass
class SubtitleSegment:
    """标准化的字幕段"""
    index: int
    start_time: float
    end_time: float
    text: str
    translation: Optional[str] = None  # 翻译文本 (双语)
    speaker: Optional[str] = None      # 说话人
    confidence: float = 1.0


@dataclass
class SubtitleResult:
    """字幕处理结果"""
    segments: List[SubtitleSegment] = field(default_factory=list)
    style: SubtitleStylePreset = field(default_factory=lambda: _BUILTIN_PRESETS["bilibili"])
    language: str = "zh"
    total_duration: float = 0.0
    segment_count: int = 0

    @property
    def ir_track(self) -> IRTrack:
        """转换为 IR 字幕轨"""
        track = IRTrack(
            index=0,
            type=IRTrackType.SUBTITLE,
            name=f"Subtitles_{self.language}",
            target_language=self.language,
        )
        for seg in self.segments:
            track.clips.append(IRClip(
                id=f"sub_{seg.index:04d}",
                source_path="__subtitle__",
                timeline_in=seg.start_time,
                timeline_out=seg.end_time,
                label=seg.text,
                tags=["subtitle", self.language],
                metadata={
                    "text": seg.text,
                    "translation": seg.translation,
                    "speaker": seg.speaker,
                    "confidence": seg.confidence,
                    "style": self.style.to_dict(),
                },
            ))
        return track


# ================================================================
#  字幕样式推荐器
# ================================================================

class SubtitleStyler:
    """
    字幕样式推荐器 (Phase B 骨架)。

    根据创意描述、内容风格推荐最合适的字幕预设。
    后续阶段可扩展为 LLM 驱动的样式选择。
    """

    # 关键词 → 预设映射
    KEYWORD_PRESET_MAP: Dict[str, str] = {
        "抖音": "douyin",
        "短视频": "douyin",
        "douyin": "douyin",
        "tiktok": "douyin",

        "b站": "bilibili",
        "bilibili": "bilibili",
        "弹幕": "bilibili",
        "up主": "bilibili",

        "电影": "cinematic",
        "纪录片": "cinematic",
        "cinematic": "cinematic",
        "文艺": "cinematic",

        "极简": "minimal",
        "minimal": "minimal",
        "简约": "minimal",

        "游戏": "gaming",
        "电竞": "gaming",
        "gaming": "gaming",
        "直播": "gaming",

        "新闻": "news",
        "news": "news",
        "采访": "news",
    }

    def recommend_style(
        self,
        creative_desc: str = "",
        platform: Optional[str] = None,
        language: str = "zh",
    ) -> Dict[str, Any]:
        """
        推荐字幕样式。

        Args:
            creative_desc: 创意描述
            platform: 目标平台 (douyin/bilibili/youtube)
            language: 语言

        Returns:
            样式字典
        """
        preset_name = "bilibili"  # 默认

        # 平台直接指定
        if platform:
            platform_lower = platform.lower()
            if platform_lower in self.KEYWORD_PRESET_MAP:
                preset_name = self.KEYWORD_PRESET_MAP[platform_lower]

        # 关键词匹配
        if creative_desc:
            desc_lower = creative_desc.lower()
            for keyword, preset in self.KEYWORD_PRESET_MAP.items():
                if keyword.lower() in desc_lower:
                    preset_name = preset
                    break

        preset = _BUILTIN_PRESETS.get(preset_name, _BUILTIN_PRESETS["bilibili"])

        # 语言适配
        if language == "en":
            preset = SubtitleStylePreset(
                **{**preset.__dict__,
                   "font_family": "Helvetica Neue",
                   "font_size": preset.font_size - 4}
            )
        elif language == "ja":
            preset = SubtitleStylePreset(
                **{**preset.__dict__,
                   "font_family": "Hiragino Sans",
                   "font_size": preset.font_size}
            )
        elif language == "zh-en":
            preset = SubtitleStylePreset(
                **{**preset.__dict__,
                   "font_size": preset.font_size - 6}
            )

        return preset.to_dict()

    def get_preset(self, name: str) -> Optional[SubtitleStylePreset]:
        """获取预设"""
        return _BUILTIN_PRESETS.get(name)

    def list_presets(self) -> List[str]:
        """列出所有预设名"""
        return list(_BUILTIN_PRESETS.keys())

    def register_preset(self, name: str, preset: SubtitleStylePreset) -> None:
        """注册自定义预设"""
        _BUILTIN_PRESETS[name] = preset


# ================================================================
#  字幕处理管线
# ================================================================

class SubtitlePipeline:
    """
    字幕产品化管线 (Phase B 骨架)。

    流程: 解析 → 校验 → 优化 → 样式 → IR 输出
    """

    def __init__(
        self,
        min_gap: float = 0.05,       # 字幕最小间隔 (秒)
        max_chars_per_line: int = 30,  # 单行最大字数
        auto_merge: bool = True,       # 自动合并过短字幕
        auto_split: bool = True,       # 自动拆分过长字幕
    ):
        self.min_gap = min_gap
        self.max_chars_per_line = max_chars_per_line
        self.auto_merge = auto_merge
        self.auto_split = auto_split
        self.styler = SubtitleStyler()

    # ----------------------------------------------------------
    #  SRT 处理
    # ----------------------------------------------------------

    def process_srt(
        self,
        srt_path: str,
        style: str = "bilibili",
        language: str = "zh",
    ) -> SubtitleResult:
        """
        处理 SRT 字幕文件。

        Args:
            srt_path: SRT 文件路径
            style: 字幕样式预设名
            language: 语言

        Returns:
            SubtitleResult
        """
        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.process_srt_content(content, style, language)

    def process_srt_content(
        self,
        srt_content: str,
        style: str = "bilibili",
        language: str = "zh",
    ) -> SubtitleResult:
        """
        处理 SRT 文本内容。

        Args:
            srt_content: SRT 文本
            style: 字幕样式预设名
            language: 语言

        Returns:
            SubtitleResult
        """
        # 尝试使用现有解析器
        segments = self._parse_srt(srt_content)

        # 优化
        segments = self._optimize_segments(segments)

        # 样式
        style_preset = _BUILTIN_PRESETS.get(style, _BUILTIN_PRESETS["bilibili"])

        total_dur = max((s.end_time for s in segments), default=0.0)

        return SubtitleResult(
            segments=segments,
            style=style_preset,
            language=language,
            total_duration=total_dur,
            segment_count=len(segments),
        )

    # ----------------------------------------------------------
    #  字幕文本处理 (无文件)
    # ----------------------------------------------------------

    def process_segments(
        self,
        segments: List[Dict[str, Any]],
        style: str = "bilibili",
        language: str = "zh",
    ) -> SubtitleResult:
        """
        处理字幕段列表 (字典格式)。

        Args:
            segments: [{start, end, text, ...}, ...]
            style: 字幕样式预设名
            language: 语言

        Returns:
            SubtitleResult
        """
        parsed = []
        for i, seg in enumerate(segments):
            parsed.append(SubtitleSegment(
                index=i + 1,
                start_time=seg.get("start", 0.0),
                end_time=seg.get("end", 0.0),
                text=seg.get("text", ""),
                translation=seg.get("translation"),
                speaker=seg.get("speaker"),
                confidence=seg.get("confidence", 1.0),
            ))

        parsed = self._optimize_segments(parsed)
        style_preset = _BUILTIN_PRESETS.get(style, _BUILTIN_PRESETS["bilibili"])
        total_dur = max((s.end_time for s in parsed), default=0.0)

        return SubtitleResult(
            segments=parsed,
            style=style_preset,
            language=language,
            total_duration=total_dur,
            segment_count=len(parsed),
        )

    # ----------------------------------------------------------
    #  IR 导出
    # ----------------------------------------------------------

    def to_ir_track(
        self,
        result: SubtitleResult,
        track_index: int = 2,
    ) -> IRTrack:
        """
        将 SubtitleResult 转换为 IR 字幕轨。

        Args:
            result: 字幕结果
            track_index: IR 轨道索引

        Returns:
            IRTrack (SUBTITLE 类型)
        """
        track = result.ir_track
        track.index = track_index
        return track

    # ----------------------------------------------------------
    #  内部：SRT 解析
    # ----------------------------------------------------------

    @staticmethod
    def _parse_srt(content: str) -> List[SubtitleSegment]:
        """解析 SRT 文本"""
        segments = []
        blocks = content.strip().split("\n\n")
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            if len(lines) < 3:
                continue
            try:
                index = int(lines[0].strip())
                time_range = lines[1].strip()
                text = "\n".join(lines[2:]).strip()
                if "-->" in time_range:
                    start_str, end_str = time_range.split("-->")
                    start_time = SubtitlePipeline._parse_timecode(start_str.strip())
                    end_time = SubtitlePipeline._parse_timecode(end_str.strip())
                    segments.append(SubtitleSegment(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text,
                    ))
            except (ValueError, IndexError):
                continue
        return segments

    @staticmethod
    def _parse_timecode(tc: str) -> float:
        """解析时间码 HH:MM:SS,mmm 或 HH:MM:SS.mmm"""
        tc = tc.strip()
        # 处理逗号格式 (SRT 标准)
        tc = tc.replace(",", ".")
        parts = tc.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0

    # ----------------------------------------------------------
    #  内部：字幕优化
    # ----------------------------------------------------------

    def _optimize_segments(
        self, segments: List[SubtitleSegment]
    ) -> List[SubtitleSegment]:
        """字幕优化管道"""
        segments = self._fix_overlaps(segments)
        if self.auto_merge:
            segments = self._merge_short_segments(segments)
        if self.auto_split:
            segments = self._split_long_segments(segments)
        return segments

    def _fix_overlaps(
        self, segments: List[SubtitleSegment]
    ) -> List[SubtitleSegment]:
        """修复时间重叠"""
        if not segments:
            return segments
        result = [segments[0]]
        for i in range(1, len(segments)):
            prev = result[-1]
            curr = segments[i]
            if curr.start_time < prev.end_time + self.min_gap:
                # 重叠或间隔过近 — 调整当前开始时间
                curr = SubtitleSegment(
                    index=curr.index,
                    start_time=prev.end_time + self.min_gap,
                    end_time=max(curr.end_time, prev.end_time + self.min_gap + 0.5),
                    text=curr.text,
                    translation=curr.translation,
                    speaker=curr.speaker,
                    confidence=curr.confidence,
                )
            result.append(curr)
        return result

    def _merge_short_segments(
        self, segments: List[SubtitleSegment]
    ) -> List[SubtitleSegment]:
        """合并过短的字幕 (duration < 0.3s 且相邻)"""
        if len(segments) <= 1:
            return segments
        result = []
        i = 0
        while i < len(segments):
            curr = segments[i]
            if i + 1 < len(segments):
                nxt = segments[i + 1]
                curr_dur = curr.end_time - curr.start_time
                next_dur = nxt.end_time - nxt.start_time
                gap = nxt.start_time - curr.end_time
                # 当前过短 且 间隔近 且 合并后不超长
                combined_text = curr.text + " " + nxt.text
                if (curr_dur < 0.3 and gap < 0.1
                        and len(combined_text) <= self.max_chars_per_line * 2):
                    curr = SubtitleSegment(
                        index=curr.index,
                        start_time=curr.start_time,
                        end_time=nxt.end_time,
                        text=combined_text,
                        translation=(curr.translation or "") + " " + (nxt.translation or "") if curr.translation or nxt.translation else None,
                        speaker=curr.speaker or nxt.speaker,
                        confidence=min(curr.confidence, nxt.confidence),
                    )
                    i += 2
                    result.append(curr)
                    continue
            result.append(curr)
            i += 1
        return result

    def _split_long_segments(
        self, segments: List[SubtitleSegment]
    ) -> List[SubtitleSegment]:
        """拆分过长字幕 (>max_chars_per_line)"""
        result = []
        for seg in segments:
            if len(seg.text) <= self.max_chars_per_line or "\n" in seg.text:
                result.append(seg)
                continue
            # 按字数等分
            text = seg.text
            dur = seg.end_time - seg.start_time
            chunk_size = self.max_chars_per_line
            chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            chunk_dur = dur / len(chunks)
            for j, chunk in enumerate(chunks):
                result.append(SubtitleSegment(
                    index=seg.index + j,
                    start_time=seg.start_time + j * chunk_dur,
                    end_time=seg.start_time + (j + 1) * chunk_dur,
                    text=chunk.strip(),
                    translation=seg.translation,
                    speaker=seg.speaker,
                    confidence=seg.confidence,
                ))
        return result


# ================================================================
#  便捷函数
# ================================================================

def quick_subtitle_track(
    srt_path: str,
    style: str = "bilibili",
    language: str = "zh",
    track_index: int = 2,
) -> IRTrack:
    """
    快速从 SRT 文件生成 IR 字幕轨。

    Args:
        srt_path: SRT 文件路径
        style: 字幕样式
        language: 语言
        track_index: 轨道索引

    Returns:
        IRTrack (SUBTITLE)
    """
    pipeline = SubtitlePipeline()
    result = pipeline.process_srt(srt_path, style, language)
    return pipeline.to_ir_track(result, track_index)


def get_builtin_styles() -> Dict[str, Dict[str, Any]]:
    """获取所有内置样式预设"""
    return {name: preset.to_dict() for name, preset in _BUILTIN_PRESETS.items()}
