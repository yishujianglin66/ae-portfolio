#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试字幕系统和 AI 创意规划器的字幕功能
"""

import json
import pytest
from pathlib import Path
from typing import List, Dict, Any


class TestSubtitleSystem:
    """测试字幕系统"""

    def test_srt_parsing(self):
        """测试 SRT 字幕解析"""
        from ae.subtitle_system import SubtitleParser

        srt_content = """1
00:00:00,000 --> 00:00:02,000
第一句字幕

2
00:00:02,000 --> 00:00:04,000
第二句字幕

3
00:00:04,000 --> 00:00:06,500
第三句字幕内容
"""
        subtitles = SubtitleParser.parse_srt(srt_content)

        assert len(subtitles) == 3
        assert subtitles[0].text == "第一句字幕"
        assert subtitles[0].start_time == 0.0
        assert subtitles[0].end_time == 2.0
        assert subtitles[1].text == "第二句字幕"
        assert subtitles[2].text == "第三句字幕内容"
        assert subtitles[2].end_time == 6.5

    def test_srt_export(self):
        """测试 SRT 字幕导出"""
        from ae.subtitle_system import SubtitleGenerator, SubtitleItem

        subtitles = [
            SubtitleItem(index=1, start_time=0.0, end_time=2.0, text="测试字幕"),
            SubtitleItem(index=2, start_time=2.0, end_time=4.5, text="第二句"),
        ]

        srt_content = SubtitleGenerator.to_srt(subtitles)
        assert "1" in srt_content
        assert "00:00:00,000 --> 00:00:02,000" in srt_content
        assert "测试字幕" in srt_content
        assert "2" in srt_content
        assert "00:00:02,000 --> 00:00:04,500" in srt_content

    def test_vtt_parsing(self):
        """测试 VTT 字幕解析"""
        from ae.subtitle_system import SubtitleParser

        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000
第一句 VTT

00:00:02.000 --> 00:00:04.000
第二句 VTT
"""
        subtitles = SubtitleParser.parse_vtt(vtt_content)

        assert len(subtitles) == 2
        assert subtitles[0].text == "第一句 VTT"
        assert subtitles[1].text == "第二句 VTT"

    def test_ass_parsing(self):
        """测试 ASS 字幕解析"""
        from ae.subtitle_system import SubtitleParser

        ass_content = """[Script Info]
Title: Test
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,ASS字幕第一句
Dialogue: 0,0:00:02.00,0:00:04.00,Default,,0,0,0,,ASS字幕第二句
"""
        subtitles = SubtitleParser.parse_ass(ass_content)

        assert len(subtitles) == 2
        assert "ASS字幕第一句" in subtitles[0].text
        assert "ASS字幕第二句" in subtitles[1].text

    def test_subtitle_item_to_dict(self):
        """测试字幕项转字典"""
        from ae.subtitle_system import SubtitleItem
        from dataclasses import asdict

        item = SubtitleItem(index=1, start_time=0.0, end_time=2.0, text="测试")
        d = asdict(item)

        assert d["index"] == 1
        assert d["start_time"] == 0.0
        assert d["end_time"] == 2.0
        assert d["text"] == "测试"

    def test_subtitle_from_dict(self):
        """测试从字典创建字幕项"""
        from ae.subtitle_system import SubtitleItem

        d = {"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "测试"}
        item = SubtitleItem(**d)

        assert item.index == 1
        assert item.start_time == 0.0
        assert item.text == "测试"

    def test_subtitle_parser_detect_format(self):
        """测试自动检测字幕格式"""
        from ae.subtitle_system import SubtitleParser

        assert SubtitleParser.detect_format("WEBVTT\n") == "vtt"
        assert SubtitleParser.detect_format("[Script Info]\n") == "ass"
        assert SubtitleParser.detect_format("1\n00:00:00,000 -->\n") == "srt"


class TestAICreativePlannerSubtitles:
    """测试 AI 创意规划器的字幕功能"""

    def test_parse_subtitle_keywords(self):
        """测试解析字幕相关关键词"""
        from ae.ai_creative_planner import AICreativePlanner

        planner = AICreativePlanner(enable_presets=False, enable_subtitles=False)

        description = "为视频添加中文字幕，使用赛博朋克风格"
        result = planner.parse_creative_description(description)

        assert "subtitle" in result["analysis"]["patterns"]
        assert "字幕" in result["analysis"]["keywords"]

    def test_heuristic_subtitle_detection(self):
        """测试启发式字幕检测"""
        from ae.ai_creative_planner import AICreativePlanner

        planner = AICreativePlanner(enable_presets=False, enable_subtitles=False)

        test_cases = [
            "添加字幕",
            "subtitle",
            "生成对白字幕",
            "视频字幕",
        ]

        for desc in test_cases:
            result = planner.parse_creative_description(desc)
            assert result["analysis"]["task_type"] == "subtitle", f"Failed for: {desc}"

    def test_non_subtitle_description(self):
        """测试非字幕描述的处理"""
        from ae.ai_creative_planner import AICreativePlanner

        planner = AICreativePlanner(enable_presets=False, enable_subtitles=False)

        description = "创建一个赛博朋克风格的片头动画"
        result = planner.parse_creative_description(description)

        assert result["analysis"]["task_type"] == "creative"
        assert "subtitle" not in result["analysis"]["patterns"]

    def test_subtitle_task_graph_generation(self):
        """测试字幕任务图生成"""
        from ae.ai_creative_planner import AICreativePlanner

        planner = AICreativePlanner(enable_presets=False, enable_subtitles=False)

        params = {
            "text": "测试字幕",
            "duration": 30,
            "animation": "fade",
            "style": "default",
        }

        task_graph = planner._generate_subtitle_task_graph(params)

        assert task_graph["pattern"] == "subtitle"
        assert len(task_graph["tasks"]) == 1
        assert task_graph["tasks"][0]["script"] == "import_subtitles"
        assert task_graph["tasks"][0]["params"]["text"] == "测试字幕"

    def test_extract_keywords_with_subtitle(self):
        """测试提取字幕相关关键词"""
        from ae.ai_creative_planner import AICreativePlanner

        planner = AICreativePlanner(enable_presets=False, enable_subtitles=False)

        keywords = planner._extract_keywords("为视频添加赛博朋克风格的字幕")

        assert "字幕" in keywords
        assert "赛博朋克" in keywords

    def test_creative_patterns_expanded(self):
        """测试创意模式扩展"""
        from ae.creative_patterns import CREATIVE_PATTERNS

        pattern_names = [p.name for p in CREATIVE_PATTERNS]

        assert len(CREATIVE_PATTERNS) >= 12, f"Expected at least 12 patterns, got {len(CREATIVE_PATTERNS)}"

        new_patterns = [
            "text_bounce_in",
            "text_scale_in",
            "text_rotate_in",
            "text_slide_in",
            "text_per_char",
            "text_fade_in_out",
            "text_shock",
            "text_spiral",
        ]

        for pattern_name in new_patterns:
            assert pattern_name in pattern_names, f"Missing pattern: {pattern_name}"


class TestPromptTemplates:
    """测试提示词模板"""

    def test_subtitle_optimization_prompt_exists(self):
        """测试字幕优化提示词存在"""
        from ae.prompt_templates import PROMPT_TEMPLATES, build_subtitle_optimization_prompt

        assert "subtitle_optimization" in PROMPT_TEMPLATES

        subtitles = [
            {"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "测试字幕"}
        ]
        prompt = build_subtitle_optimization_prompt(subtitles, language="zh", style="cyberpunk")

        assert "system" in prompt
        assert "user" in prompt
        assert "测试字幕" in prompt["user"]
        assert "cyberpunk" in prompt["user"]


class TestNexrenderIntegration:
    """测试 nexrender 集成"""

    def test_config_creation(self):
        """测试配置创建"""
        from integrations.nexrender import NexrenderIntegration

        nexrender = NexrenderIntegration()

        config = nexrender.create_template_config(
            template_path="test.aep",
            output_path="output.mp4",
            data={
                "Title": "测试标题",
                "Subtitle": "测试副标题",
            },
        )

        assert config["template"]["src"] == "test.aep"
        assert config["output"]["src"] == "output.mp4"
        assert len(config["assets"]) == 2

    def test_subtitle_template_config(self):
        """测试字幕模板配置"""
        from integrations.nexrender import NexrenderIntegration

        nexrender = NexrenderIntegration()

        subtitles = [
            {"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "字幕1"},
            {"index": 2, "start_time": 2.0, "end_time": 4.0, "text": "字幕2"},
        ]

        config = nexrender.create_subtitle_template_config(
            template_path="subtitle_template.aep",
            output_path="output.mp4",
            subtitles=subtitles,
            font_family="Arial",
            font_size=48,
        )

        assert config["template"]["src"] == "subtitle_template.aep"
        assert "subtitles" in [a["layerName"] for a in config["assets"]]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
