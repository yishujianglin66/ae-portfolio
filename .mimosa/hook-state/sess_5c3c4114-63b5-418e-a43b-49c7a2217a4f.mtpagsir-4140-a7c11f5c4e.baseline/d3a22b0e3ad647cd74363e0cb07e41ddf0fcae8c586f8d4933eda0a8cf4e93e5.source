"""语义解析器单元测试"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from semantic_parser import SemanticParser


class TestSemanticParser(unittest.TestCase):
    """语义解析器测试"""

    def setUp(self):
        self.parser = SemanticParser()

    def test_parse_empty_input(self):
        result = self.parser.parse("")
        self.assertEqual(result.raw_input, "")
        self.assertEqual(result.semantic_query, "")
        self.assertEqual(result.confidence, 0.0)

    def test_parse_bpm_exact_value(self):
        result = self.parser.parse("开心的音乐 BPM120")
        self.assertEqual(result.target_bpm, 120.0)
        self.assertEqual(result.bpm_range, (115, 125))

    def test_parse_bpm_lowercase(self):
        result = self.parser.parse("放松的音乐 bpm90")
        self.assertEqual(result.target_bpm, 90.0)
        self.assertEqual(result.bpm_range, (85, 95))

    def test_parse_bpm_range_keyword(self):
        result = self.parser.parse("动感的音乐")
        self.assertEqual(result.target_bpm, 135.0)
        self.assertEqual(result.bpm_range, (120, 150))

    def test_parse_mood_happy(self):
        result = self.parser.parse("开心的流行音乐")
        self.assertEqual(result.mood, "happy")
        self.assertGreater(result.mood_score, 0.8)

    def test_parse_mood_sad(self):
        result = self.parser.parse("悲伤的钢琴曲")
        self.assertEqual(result.mood, "sad")
        self.assertGreater(result.mood_score, 0.7)

    def test_parse_mood_excited(self):
        result = self.parser.parse("兴奋的电子音乐")
        self.assertEqual(result.mood, "excited")

    def test_parse_genre_pop(self):
        result = self.parser.parse("流行音乐 BPM120")
        self.assertEqual(result.genre, "pop")

    def test_parse_genre_rock(self):
        result = self.parser.parse("摇滚音乐")
        self.assertEqual(result.genre, "rock")

    def test_parse_genre_chinese_folk(self):
        result = self.parser.parse("国风音乐")
        self.assertEqual(result.genre, "chinese_folk")

    def test_parse_media_type_audio(self):
        result = self.parser.parse("欢快的BGM")
        self.assertEqual(result.media_type, "audio")

    def test_parse_media_type_video(self):
        result = self.parser.parse("高清视频素材")
        self.assertEqual(result.media_type, "video")

    def test_parse_media_type_image(self):
        result = self.parser.parse("风景图片")
        self.assertEqual(result.media_type, "image")

    def test_parse_quality_high(self):
        result = self.parser.parse("4K高清视频")
        self.assertEqual(result.quality, "4k")

    def test_parse_quality_bluray(self):
        result = self.parser.parse("蓝光画质素材")
        self.assertEqual(result.quality, "high")

    def test_parse_watermark_free(self):
        result = self.parser.parse("无水印视频素材")
        self.assertTrue(result.watermark_free)

    def test_parse_watermark_free_other(self):
        result = self.parser.parse("去水印高清素材")
        self.assertTrue(result.watermark_free)

    def test_parse_platform_douyin(self):
        result = self.parser.parse("抖音热门BGM")
        self.assertEqual(result.preferred_platforms, ["douyin"])

    def test_parse_platform_multiple(self):
        result = self.parser.parse("抖音B站素材")
        self.assertIn("douyin", result.preferred_platforms)
        self.assertIn("bilibili", result.preferred_platforms)

    def test_parse_semantic_query_cleaning(self):
        result = self.parser.parse("美丽的海边风景 BPM120 4K高清")
        self.assertNotIn("120", result.semantic_query)

    def test_parse_combined_query(self):
        result = self.parser.parse("开心的流行音乐 BPM120 抖音 BGM 4K高清 无水印")
        self.assertEqual(result.mood, "happy")
        self.assertEqual(result.genre, "pop")
        self.assertEqual(result.target_bpm, 120.0)
        self.assertIn("douyin", result.preferred_platforms)
        self.assertEqual(result.media_type, "audio")
        self.assertEqual(result.quality, "4k")
        self.assertTrue(result.watermark_free)
        self.assertGreater(result.confidence, 0.5)

    def test_parse_tags_extraction(self):
        result = self.parser.parse("开心的流行音乐")
        self.assertIn("开心", result.tags)
        self.assertIn("流行", result.tags)

    def test_parse_confidence_calculation(self):
        result = self.parser.parse("简单查询")
        self.assertGreater(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)


class TestSemanticQueryExtraction(unittest.TestCase):
    """语义查询提取测试"""

    def setUp(self):
        self.parser = SemanticParser()

    def test_extract_semantic_query_preserves_meaning(self):
        query = "夕阳下海滩风景"
        result = self.parser.parse(query)
        self.assertEqual(result.semantic_query, query)

    def test_extract_semantic_query_removes_keywords(self):
        query = "夕阳下的海滩 4K高清 抖音"
        result = self.parser.parse(query)
        self.assertNotIn("4K", result.semantic_query)
        self.assertNotIn("高清", result.semantic_query)
        self.assertNotIn("抖音", result.semantic_query)

    def test_extract_semantic_query_short_text_preserved(self):
        query = "开心"
        result = self.parser.parse(query)
        self.assertEqual(result.semantic_query, query)

    def test_extract_semantic_query_over_cleaning_protection(self):
        query = "开心的音乐"
        result = self.parser.parse(query)
        self.assertGreater(len(result.semantic_query), 0)


class TestBPMExtraction(unittest.TestCase):
    """BPM提取测试"""

    def setUp(self):
        self.parser = SemanticParser()

    def test_extract_bpm_exact(self):
        result = self.parser.parse("BPM120 音乐")
        self.assertEqual(result.target_bpm, 120.0)

    def test_extract_bpm_with_spaces(self):
        result = self.parser.parse("音乐 BPM 140")
        self.assertEqual(result.target_bpm, 140.0)

    def test_extract_bpm_range_keyword_slow(self):
        result = self.parser.parse("舒缓的音乐")
        self.assertEqual(result.bpm_range, (60, 90))
        self.assertEqual(result.target_bpm, 75.0)

    def test_extract_bpm_range_keyword_fast(self):
        result = self.parser.parse("极速的音乐")
        self.assertEqual(result.bpm_range, (150, 200))
        self.assertEqual(result.target_bpm, 175.0)


class TestPlatformKeywordsUniqueness(unittest.TestCase):
    """平台关键词唯一性测试"""

    def test_platform_keywords_no_duplicates(self):
        """验证PLATFORM_KEYWORDS字典中没有重复键"""
        keywords = SemanticParser.PLATFORM_KEYWORDS
        seen = set()
        duplicates = []
        for kw in keywords:
            if kw in seen:
                duplicates.append(kw)
            seen.add(kw)
        self.assertEqual(len(duplicates), 0, f"发现重复平台关键词: {duplicates}")

    def test_platform_keywords_contains_common_platforms(self):
        """验证PLATFORM_KEYWORDS包含常见平台"""
        keywords = SemanticParser.PLATFORM_KEYWORDS
        common_platforms = ["抖音", "B站", "YouTube", "TikTok", "小红书", "微博"]
        for platform in common_platforms:
            self.assertIn(platform, keywords, f"缺少常见平台关键词: {platform}")


if __name__ == "__main__":
    unittest.main(verbosity=2)