#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase B3/B4 完整测试 — 转场规则引擎 + 字幕产品化
====================================================

覆盖:
- B3: 7 风格 × 6 内容关系 = 42 条转场规则验证
- B4: 6 种字幕预设 + 样式推荐 + SRT 解析 + 优化 + IR 导出
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


# ================================================================
#  B3: 转场规则引擎测试
# ================================================================

class TestTransitionSelector(unittest.TestCase):
    """B3 转场智能选择器测试"""

    def setUp(self):
        from ae.transition_selector import ContentRelation, StyleCategory, TransitionRule, TransitionSelector
        self.selector = TransitionSelector(seed=42)
        self.StyleCategory = StyleCategory
        self.ContentRelation = ContentRelation

    # --- 规则完整性 ---

    def test_default_rules_count_is_42(self):
        """默认规则表应包含 7 风格 × 6 关系 = 42 条规则"""
        self.assertEqual(len(self.selector.rules), 42)

    def test_all_styles_covered(self):
        """所有 7 种风格均应有规则"""
        styles_in_rules = set(r.style for r in self.selector.rules)
        expected = set(self.StyleCategory)
        self.assertEqual(styles_in_rules, expected)

    def test_all_relations_covered(self):
        """所有 6 种内容关系均应有规则"""
        relations_in_rules = set(r.relation for r in self.selector.rules)
        expected = set(self.ContentRelation)
        self.assertEqual(relations_in_rules, expected)

    def test_each_style_has_6_rules(self):
        """每种风格应恰好有 6 条规则（对应 6 种关系）"""
        for style in self.StyleCategory:
            style_rules = [r for r in self.selector.rules if r.style == style]
            self.assertEqual(
                len(style_rules), 6,
                f"风格 {style.value} 应有 6 条规则，实际 {len(style_rules)} 条"
            )

    def test_each_style_relation_pair_unique(self):
        """每个 (风格, 关系) 对应有且仅有一条规则"""
        pairs = [(r.style, r.relation) for r in self.selector.rules]
        self.assertEqual(len(pairs), len(set(pairs)))

    # --- 选择逻辑 ---

    def test_select_for_sequence_returns_map(self):
        """select_for_sequence 应返回 {clip: transition_type} 映射"""
        clips = ["a.mp4", "b.mp4", "c.mp4"]
        result = self.selector.select_for_sequence(clips, style="dynamic_cut")
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["a.mp4"], "cut")  # 首片段固定 cut

    def test_select_for_sequence_single_clip(self):
        """单片段应返回 cut"""
        result = self.selector.select_for_sequence(["only.mp4"])
        self.assertEqual(result, {"only.mp4": "cut"})

    def test_select_for_sequence_empty(self):
        """空列表应返回空字典"""
        result = self.selector.select_for_sequence([])
        self.assertEqual(result, {})

    def test_select_single_returns_valid_type(self):
        """select_single 应返回有效的 IRTransitionType"""
        from ae.timeline_ir import IRTransitionType
        valid_values = set(t.value for t in IRTransitionType)
        for style in ["dynamic_cut", "smooth_flow", "slow_cinematic",
                       "glitch_style", "vlog", "retro", "minimal"]:
            for rel in self.ContentRelation:
                result = self.selector.select_single(style, rel)
                self.assertIn(
                    result.value, valid_values,
                    f"select_single({style}, {rel.value}) 返回 {result.value} 不在有效范围"
                )

    def test_select_with_duration_returns_tuple(self):
        """select_with_duration 应返回 (类型, 时长) 元组"""
        from ae.timeline_ir import IRTransitionType
        trans, dur = self.selector.select_with_duration("dynamic_cut", self.ContentRelation.CONTINUOUS)
        self.assertIsInstance(trans, IRTransitionType)
        self.assertIsInstance(dur, float)
        self.assertGreaterEqual(dur, 0.0)

    def test_cut_duration_is_zero(self):
        """CUT 转场时长应为 0"""
        from ae.timeline_ir import IRTransitionType
        from ae.transition_selector import TransitionSelector
        selector = TransitionSelector(seed=0)
        # 强制选择 CUT：dynamic + continuous 的 primary 是 CUT
        trans, dur = selector.select_with_duration("dynamic_cut", self.ContentRelation.CONTINUOUS)
        # 由于加权随机，primary 有 3/4 概率被选中
        # 多次采样验证 CUT 时长为 0
        for _ in range(20):
            t, d = selector.select_with_duration("dynamic_cut", self.ContentRelation.CONTINUOUS)
            if t == IRTransitionType.CUT:
                self.assertEqual(d, 0.0)

    # --- PR 映射 ---

    def test_to_pr_transition_mapping(self):
        """to_pr_transition 应正确映射所有已知类型"""
        from ae.timeline_ir import IRTransitionType
        mapped = self.selector.to_pr_transition(IRTransitionType.CROSS_DISSOLVE)
        self.assertEqual(mapped, "cross_dissolve")
        mapped = self.selector.to_pr_transition(IRTransitionType.GLITCH)
        self.assertEqual(mapped, "glitch")

    # --- 规则管理 ---

    def test_add_rule(self):
        """动态添加规则应生效"""
        from ae.transition_selector import TransitionRule
        initial_count = len(self.selector.rules)
        new_rule = TransitionRule(
            self.StyleCategory.DYNAMIC,
            self.ContentRelation.CONTINUOUS,
            self.selector.rules[0].primary,
        )
        self.selector.add_rule(new_rule)
        self.assertEqual(len(self.selector.rules), initial_count + 1)

    def test_get_rules_for_style(self):
        """get_rules_for_style 应返回对应风格的所有规则"""
        rules = self.selector.get_rules_for_style("dynamic_cut")
        self.assertEqual(len(rules), 6)
        self.assertTrue(all(r.style == self.StyleCategory.DYNAMIC for r in rules))

    def test_list_available_transitions(self):
        """list_available_transitions 应返回非空列表"""
        all_trans = self.selector.list_available_transitions()
        self.assertGreater(len(all_trans), 0)
        self.assertIn("cut", all_trans)

    def test_reproducible_with_seed(self):
        """相同 seed 应产生相同结果"""
        from ae.transition_selector import TransitionSelector
        s1 = TransitionSelector(seed=123)
        s2 = TransitionSelector(seed=123)
        clips = ["a.mp4", "b.mp4", "c.mp4", "d.mp4"]
        r1 = s1.select_for_sequence(clips, style="dynamic_cut")
        r2 = s2.select_for_sequence(clips, style="dynamic_cut")
        self.assertEqual(r1, r2)


# ================================================================
#  B4: 字幕产品化测试
# ================================================================

class TestSubtitlePresets(unittest.TestCase):
    """B4 字幕预设完整性测试"""

    def setUp(self):
        from ae.subtitle_product import _BUILTIN_PRESETS, SubtitleStylePreset, SubtitleStyler
        self.styler = SubtitleStyler()
        self.presets = _BUILTIN_PRESETS

    def test_six_presets_exist(self):
        """应存在 6 种内置预设"""
        expected = {"douyin", "bilibili", "cinematic", "minimal", "gaming", "news"}
        self.assertEqual(set(self.presets.keys()), expected)

    def test_each_preset_has_valid_fields(self):
        """每个预设应有完整字段"""
        for name, preset in self.presets.items():
            self.assertIsInstance(preset.font_family, str, f"{name} font_family 应为 str")
            self.assertGreater(preset.font_size, 0, f"{name} font_size 应 > 0")
            self.assertEqual(len(preset.font_color), 3, f"{name} font_color 应为 [R,G,B]")
            self.assertIn(preset.animation_in,
                          {"none", "fade", "slide_up", "bounce"},
                          f"{name} animation_in 不合法")

    def test_preset_to_dict(self):
        """to_dict 应返回完整字典"""
        d = self.presets["douyin"].to_dict()
        self.assertIn("name", d)
        self.assertIn("font_family", d)
        self.assertIn("font_size", d)
        self.assertEqual(d["name"], "抖音风")


class TestSubtitleStyler(unittest.TestCase):
    """B4 字幕样式推荐器测试"""

    def setUp(self):
        from ae.subtitle_product import SubtitleStyler
        self.styler = SubtitleStyler()

    def test_recommend_by_platform(self):
        """按平台推荐样式"""
        r = self.styler.recommend_style(platform="douyin")
        self.assertEqual(r["name"], "抖音风")
        r = self.styler.recommend_style(platform="bilibili")
        self.assertEqual(r["name"], "B站风")

    def test_recommend_by_keyword(self):
        """按关键词推荐样式"""
        r = self.styler.recommend_style(creative_desc="这是一个电影风格的视频")
        self.assertEqual(r["name"], "电影风")
        r = self.styler.recommend_style(creative_desc="游戏直播精彩集锦")
        self.assertEqual(r["name"], "游戏风")

    def test_recommend_default_is_bilibili(self):
        """无关键词/平台时默认 B站风"""
        r = self.styler.recommend_style()
        self.assertEqual(r["name"], "B站风")

    def test_language_adaptation_en(self):
        """英文语言适配"""
        r = self.styler.recommend_style(language="en")
        self.assertEqual(r["font_family"], "Helvetica Neue")

    def test_language_adaptation_ja(self):
        """日文语言适配"""
        r = self.styler.recommend_style(language="ja")
        self.assertEqual(r["font_family"], "Hiragino Sans")

    def test_list_presets(self):
        """list_presets 应返回 6 个预设名"""
        presets = self.styler.list_presets()
        self.assertEqual(len(presets), 6)

    def test_get_preset(self):
        """get_preset 应返回有效预设"""
        p = self.styler.get_preset("cinematic")
        self.assertIsNotNone(p)
        self.assertEqual(p.name, "电影风")

    def test_get_preset_nonexistent(self):
        """get_preset 不存在应返回 None"""
        p = self.styler.get_preset("nonexistent")
        self.assertIsNone(p)


class TestSubtitlePipeline(unittest.TestCase):
    """B4 字幕处理管线测试"""

    def setUp(self):
        from ae.subtitle_product import SubtitlePipeline
        self.pipeline = SubtitlePipeline()

    # --- SRT 解析 ---

    def test_parse_srt_content(self):
        """SRT 内容解析"""
        srt = """1
00:00:01,000 --> 00:00:03,000
你好世界

2
00:00:04,000 --> 00:00:06,500
这是第二行字幕"""
        result = self.pipeline.process_srt_content(srt)
        self.assertEqual(result.segment_count, 2)
        self.assertEqual(result.segments[0].text, "你好世界")
        self.assertAlmostEqual(result.segments[0].start_time, 1.0, places=1)
        self.assertAlmostEqual(result.segments[0].end_time, 3.0, places=1)

    def test_parse_empty_srt(self):
        """空 SRT 内容"""
        result = self.pipeline.process_srt_content("")
        self.assertEqual(result.segment_count, 0)

    # --- 优化 ---

    def test_fix_overlaps(self):
        """修复时间重叠"""
        segments = [
            {"start": 0.0, "end": 2.0, "text": "第一段"},
            {"start": 1.5, "end": 4.0, "text": "第二段（与第一段重叠）"},
        ]
        result = self.pipeline.process_segments(segments)
        self.assertEqual(result.segment_count, 2)
        self.assertGreater(result.segments[1].start_time, result.segments[0].end_time)

    def test_merge_short_segments(self):
        """合并过短字幕"""
        segments = [
            {"start": 0.0, "end": 0.2, "text": "短"},
            {"start": 0.25, "end": 2.0, "text": "内容"},
        ]
        result = self.pipeline.process_segments(segments)
        # 应合并为 1 段
        self.assertEqual(result.segment_count, 1)
        self.assertIn("短", result.segments[0].text)
        self.assertIn("内容", result.segments[0].text)

    def test_split_long_segments(self):
        """拆分过长字幕"""
        long_text = "A" * 60  # 超过 max_chars_per_line=30
        segments = [{"start": 0.0, "end": 3.0, "text": long_text}]
        result = self.pipeline.process_segments(segments)
        self.assertGreater(result.segment_count, 1)

    # --- IR 导出 ---

    def test_ir_track_export(self):
        """IR 字幕轨导出"""
        from ae.timeline_ir import IRTrackType
        srt = """1
00:00:01,000 --> 00:00:03,000
测试字幕"""
        result = self.pipeline.process_srt_content(srt, style="cinematic")
        track = self.pipeline.to_ir_track(result, track_index=3)
        self.assertEqual(track.type, IRTrackType.SUBTITLE)
        self.assertEqual(track.index, 3)
        self.assertEqual(len(track.clips), 1)
        self.assertEqual(track.clips[0].label, "测试字幕")

    # --- 样式应用 ---

    def test_style_applied_to_result(self):
        """样式应正确应用到结果"""
        srt = """1
00:00:01,000 --> 00:00:03,000
测试"""
        for style_name in ["douyin", "bilibili", "cinematic", "minimal", "gaming", "news"]:
            result = self.pipeline.process_srt_content(srt, style=style_name)
            self.assertEqual(result.style.name, self.pipeline.styler.get_preset(style_name).name)


# ================================================================
#  集成测试
# ================================================================

class TestB3B4Integration(unittest.TestCase):
    """B3/B4 集成测试"""

    def test_transition_and_subtitle_coexist(self):
        """转场选择器和字幕管线可同时实例化"""
        from ae.subtitle_product import SubtitlePipeline
        from ae.transition_selector import TransitionSelector
        selector = TransitionSelector()
        pipeline = SubtitlePipeline()
        self.assertIsNotNone(selector)
        self.assertIsNotNone(pipeline)

    def test_e2e_pipeline_imports(self):
        """e2e_pipeline 应能成功导入 B3/B4 模块"""
        from ae.e2e_pipeline import E2EPipeline
        pipeline = E2EPipeline()
        self.assertIsNotNone(pipeline)


if __name__ == "__main__":
    unittest.main()
