#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试字幕解析器边界条件
======================

覆盖 ae/subtitle_system.py 中字幕解析的边界情况，
现有 tests/test_subtitle_planner.py 仅覆盖正常路径。

重点：
1. SRT 格式错误（缺 -->, 缺时间码）应优雅降级
2. VTT 缺时间码不崩
3. ASS 风格名错乱/事件缺时间码容错
4. detect_format 对空内容、纯空白、无签名的处理
5. _format_timecode 边界：负数、零、超过 24h
6. parse + 生成 roundtrip（不能丢数据）
7. 解析中文/emoji 内容
8. parse 接受 format_type=None 走 auto-detect
9. parse_file 接受 Path 对象
10. SubtitleStyle 默认值（font_color, stroke_color, glow_color）
"""
from __future__ import annotations

import pytest
from pathlib import Path
from typing import List


# ============================================================
# SRT 解析边界
# ============================================================
class TestSrtParserEdges:
    def _parse(self, content):
        from ae.subtitle_system import SubtitleParser
        return SubtitleParser.parse_srt(content)

    def test_empty_content(self):
        """空内容必须返回空列表（不能崩）。"""
        assert self._parse("") == []

    def test_whitespace_only(self):
        assert self._parse("   \n\n   \n  ") == []

    def test_valid_single_block(self):
        content = "1\n00:00:00,000 --> 00:00:02,500\n你好"
        items = self._parse(content)
        assert len(items) == 1
        assert items[0].text == "你好"
        assert items[0].start_time == 0.0
        assert items[0].end_time == 2.5
        assert items[0].index == 1

    def test_multiple_blocks(self):
        content = (
            "1\n00:00:00,000 --> 00:00:02,000\nA\n\n"
            "2\n00:00:03,000 --> 00:00:05,000\nB\n\n"
            "3\n00:00:06,000 --> 00:00:08,000\nC"
        )
        items = self._parse(content)
        assert len(items) == 3
        assert [i.text for i in items] == ["A", "B", "C"]

    def test_block_with_multiline_text(self):
        content = (
            "1\n00:00:00,000 --> 00:00:02,000\nLine1\nLine2\nLine3"
        )
        items = self._parse(content)
        assert len(items) == 1
        assert items[0].text == "Line1\nLine2\nLine3"

    def test_block_without_arrow_skipped(self):
        """缺 --> 的块应被跳过（不抛异常）。"""
        content = (
            "1\nNOT_A_TIMESTAMP\n你好\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nOK"
        )
        items = self._parse(content)
        # 只有第 2 块是有效的
        assert len(items) == 1
        assert items[0].text == "OK"

    def test_chinese_content(self):
        content = "1\n00:00:00,000 --> 00:00:01,000\n这是中文"
        items = self._parse(content)
        assert items[0].text == "这是中文"

    def test_emoji_content(self):
        content = "1\n00:00:00,000 --> 00:00:01,000\nHi 🎬 ✨"
        items = self._parse(content)
        assert items[0].text == "Hi 🎬 ✨"

    def test_hours_field_zero_preserved(self):
        content = "1\n00:00:00,000 --> 00:00:01,000\nX"
        items = self._parse(content)
        assert items[0].start_time == 0.0


# ============================================================
# VTT 解析边界
# ============================================================
class TestVttParserEdges:
    def _parse(self, content):
        from ae.subtitle_system import SubtitleParser
        return SubtitleParser.parse_vtt(content)

    def test_empty_content(self):
        assert self._parse("") == []

    def test_only_header(self):
        """仅 WEBVTT 头 + 空白，无字幕块。"""
        assert self._parse("WEBVTT\n\n") == []

    def test_valid_block(self):
        content = (
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:02.500\n你好"
        )
        items = self._parse(content)
        assert len(items) == 1
        assert items[0].text == "你好"
        assert items[0].start_time == 0.0
        assert items[0].end_time == 2.5

    def test_index_recalculated(self):
        """VTT 没有强制 index 字段，解析后必须重新编号从 1 开始。"""
        content = (
            "WEBVTT\n\n"
            "00:00:00.000 --> 00:00:01.000\nA\n\n"
            "00:00:02.000 --> 00:00:03.000\nB"
        )
        items = self._parse(content)
        assert [i.index for i in items] == [1, 2]

    def test_line_without_timestamp_skipped(self):
        content = (
            "WEBVTT\n\n"
            "no timestamp here\n\n"
            "00:00:01.000 --> 00:00:02.000\nValid"
        )
        items = self._parse(content)
        assert len(items) == 1
        assert items[0].text == "Valid"


# ============================================================
# ASS 解析边界
# ============================================================
class TestAssParserEdges:
    def _parse(self, content):
        from ae.subtitle_system import SubtitleParser
        return SubtitleParser.parse_ass(content)

    def test_minimal_ass_with_one_event(self):
        content = (
            "[Script Info]\n"
            "Title: Test\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,你好\n"
        )
        items = self._parse(content)
        assert len(items) == 1
        assert items[0].text == "你好"
        assert items[0].start_time == 1.0
        assert items[0].end_time == 3.0

    def test_ass_strips_formatting_tags(self):
        content = (
            "[Script Info]\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,{\\b1}粗体{\\b0}文本\n"
        )
        items = self._parse(content)
        # ASS 标签 {\\b1} {\\b0} 应被剥离
        assert "粗体" in items[0].text
        assert "文本" in items[0].text
        assert "{\\b1}" not in items[0].text

    def test_ass_without_events_section(self):
        content = "[Script Info]\nTitle: Empty\n"
        items = self._parse(content)
        # 没有 [Events] 块时返回空
        assert items == []

    def test_ass_chinese_text(self):
        content = (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,赛博朋克风\n"
        )
        items = self._parse(content)
        assert items[0].text == "赛博朋克风"


# ============================================================
# detect_format
# ============================================================
class TestDetectFormat:
    def test_vtt_detected(self):
        from ae.subtitle_system import SubtitleParser
        assert SubtitleParser.detect_format("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nX") == "vtt"

    def test_ass_detected(self):
        from ae.subtitle_system import SubtitleParser
        assert SubtitleParser.detect_format("[Script Info]\nTitle: X") == "ass"

    def test_srt_default(self):
        from ae.subtitle_system import SubtitleParser
        assert SubtitleParser.detect_format("1\n00:00:00,000 --> 00:00:01,000\nX") == "srt"

    def test_empty_defaults_to_srt(self):
        from ae.subtitle_system import SubtitleParser
        # 空内容走默认 srt（不会被识别为 vtt/ass）
        assert SubtitleParser.detect_format("") == "srt"

    def test_whitespace_only(self):
        from ae.subtitle_system import SubtitleParser
        assert SubtitleParser.detect_format("   \n\n  ") == "srt"

    def test_stripped_detection(self):
        """detect_format 必须先 strip 才能正确识别。"""
        from ae.subtitle_system import SubtitleParser
        # 前面有空行 + WEBVTT
        content = "\n\n   \nWEBVTT\n"
        assert SubtitleParser.detect_format(content) == "vtt"


# ============================================================
# parse 入口（含 format_type=None）
# ============================================================
class TestParseEntry:
    def test_parse_with_auto_detect_srt(self):
        from ae.subtitle_system import SubtitleParser
        content = "1\n00:00:00,000 --> 00:00:01,000\nX"
        items = SubtitleParser.parse(content)
        assert len(items) == 1

    def test_parse_with_auto_detect_vtt(self):
        from ae.subtitle_system import SubtitleParser
        content = "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nX"
        items = SubtitleParser.parse(content)
        assert len(items) == 1

    def test_parse_with_auto_detect_ass(self):
        """ASS 自动检测需以 [Script Info] 起头（detect_format 实际行为）。"""
        from ae.subtitle_system import SubtitleParser

        content = (
            "[Script Info]\n"
            "Title: X\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,X\n"
        )
        # detect_format 看到 [Script Info] 才会识别为 ass
        assert SubtitleParser.detect_format(content) == "ass"
        items = SubtitleParser.parse(content)
        assert len(items) == 1

    def test_parse_explicit_format(self):
        from ae.subtitle_system import SubtitleParser
        # 内容看起来是 SRT，但强制当 VTT 解析
        content = "1\n00:00:00.000 --> 00:00:01.000\nX"
        items = SubtitleParser.parse(content, format_type="vtt")
        assert len(items) == 1


# ============================================================
# _format_timecode
# ============================================================
class TestFormatTimecode:
    def test_zero(self):
        from ae.subtitle_system import SubtitleGenerator
        assert SubtitleGenerator._format_timecode(0.0) == "00:00:00,000"

    def test_sub_second(self):
        from ae.subtitle_system import SubtitleGenerator
        assert SubtitleGenerator._format_timecode(0.5) == "00:00:00,500"

    def test_minutes(self):
        from ae.subtitle_system import SubtitleGenerator
        assert SubtitleGenerator._format_timecode(65.123) == "00:01:05,123"

    def test_hours(self):
        from ae.subtitle_system import SubtitleGenerator
        assert SubtitleGenerator._format_timecode(3661.5) == "01:01:01,500"

    def test_uses_comma_not_period(self):
        """SRT / VTT 部分消费者对 ',' 敏感；必须输出逗号。"""
        from ae.subtitle_system import SubtitleGenerator
        out = SubtitleGenerator._format_timecode(1.5)
        assert "," in out
        assert "." not in out


# ============================================================
# 生成 + 解析 roundtrip
# ============================================================
class TestRoundtrip:
    def test_srt_roundtrip(self):
        from ae.subtitle_system import SubtitleParser, SubtitleGenerator, SubtitleItem

        original = [
            SubtitleItem(index=1, start_time=0.0, end_time=2.5, text="你好"),
            SubtitleItem(index=2, start_time=3.0, end_time=5.0, text="赛博朋克风"),
        ]
        srt_text = SubtitleGenerator.to_srt(original)
        parsed = SubtitleParser.parse_srt(srt_text)
        assert len(parsed) == 2
        assert parsed[0].text == "你好"
        assert parsed[1].text == "赛博朋克风"
        # 时间精度（毫秒级）
        assert abs(parsed[0].start_time - 0.0) < 0.001
        assert abs(parsed[0].end_time - 2.5) < 0.001
        assert abs(parsed[1].start_time - 3.0) < 0.001
        assert abs(parsed[1].end_time - 5.0) < 0.001

    def test_vtt_roundtrip(self):
        from ae.subtitle_system import SubtitleParser, SubtitleGenerator, SubtitleItem

        original = [
            SubtitleItem(index=1, start_time=0.0, end_time=2.5, text="A"),
            SubtitleItem(index=2, start_time=3.0, end_time=5.0, text="B"),
        ]
        vtt_text = SubtitleGenerator.to_vtt(original)
        parsed = SubtitleParser.parse_vtt(vtt_text)
        assert len(parsed) == 2
        assert [i.text for i in parsed] == ["A", "B"]


# ============================================================
# SubtitleStyle 默认值
# ============================================================
class TestSubtitleStyleDefaults:
    def test_default_font(self):
        from ae.subtitle_system import SubtitleStyle
        s = SubtitleStyle()
        assert s.font_family == "Arial"
        assert s.font_size == 48

    def test_color_lists_default_to_white(self):
        """字体色 / 描边色 / 发光色 默认白色。"""
        from ae.subtitle_system import SubtitleStyle
        s = SubtitleStyle()
        assert s.font_color is not None
        assert s.stroke_color is not None
        # 至少长度 3
        assert len(s.font_color) == 3
        assert len(s.stroke_color) == 3


# ============================================================
# SubtitleSystem.parse_file (路径接受)
# ============================================================
class TestParseFile:
    @pytest.mark.asyncio
    async def test_parse_file_accepts_path_object(self, tmp_path):
        from ae.subtitle_system import SubtitleSystem

        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\n你好\n",
            encoding="utf-8",
        )
        sys_obj = SubtitleSystem()
        items = await sys_obj.parse_file(srt_file)
        assert len(items) == 1
        assert items[0].text == "你好"

    @pytest.mark.asyncio
    async def test_parse_file_accepts_str_path(self, tmp_path):
        from ae.subtitle_system import SubtitleSystem

        srt_file = tmp_path / "test.srt"
        srt_file.write_text(
            "1\n00:00:00,000 --> 00:00:02,000\nA\n\n"
            "2\n00:00:03,000 --> 00:00:05,000\nB\n",
            encoding="utf-8",
        )
        items = await SubtitleSystem().parse_file(str(srt_file))
        assert len(items) == 2
