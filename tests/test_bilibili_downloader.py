"""B站下载器纯函数单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "01-下载器"))

from bilibili_downloader import (
    _safe_filename,
    _parse_yt_dlp_info,
    _sanitize_error,
    QUALITY_MAP,
)


class TestSafeFilename(unittest.TestCase):
    """安全文件名测试"""

    def test_safe_filename_empty(self):
        result = _safe_filename("")
        self.assertEqual(result, "bilibili_video")

    def test_safe_filename_normal(self):
        result = _safe_filename("普通视频标题")
        self.assertEqual(result, "普通视频标题")

    def test_safe_filename_with_path_separators(self):
        result = _safe_filename("标题/带\\路径/分隔符")
        self.assertEqual(result, "标题_带_路径_分隔符")

    def test_safe_filename_with_colon(self):
        result = _safe_filename("标题:带冒号")
        self.assertEqual(result, "标题_带冒号")

    def test_safe_filename_with_special_chars(self):
        result = _safe_filename('标题*带?特殊"<字符>|测试')
        self.assertNotIn("*", result)
        self.assertNotIn("?", result)
        self.assertNotIn('"', result)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn("|", result)
        self.assertIn("标题", result)
        self.assertIn("带", result)
        self.assertIn("特殊", result)
        self.assertIn("字符", result)
        self.assertIn("测试", result)

    def test_safe_filename_strip_dots(self):
        result = _safe_filename("..标题..")
        self.assertEqual(result, "标题")

    def test_safe_filename_strip_spaces(self):
        result = _safe_filename("  标题  ")
        self.assertEqual(result, "标题")

    def test_safe_filename_truncation(self):
        long_name = "a" * 150
        result = _safe_filename(long_name)
        self.assertEqual(len(result), 100)

    def test_safe_filename_newlines(self):
        result = _safe_filename("标题\n换行\r\n测试")
        self.assertNotIn("\n", result)
        self.assertNotIn("\r", result)
        self.assertIn("标题", result)
        self.assertIn("换行", result)
        self.assertIn("测试", result)

    def test_safe_filename_custom_max_length(self):
        long_name = "a" * 100
        result = _safe_filename(long_name, max_length=50)
        self.assertEqual(len(result), 50)

    def test_safe_filename_unicode(self):
        result = _safe_filename("🎉 标题 with emoji 😀")
        self.assertIn("标题", result)
        self.assertIn("emoji", result)


class TestParseYtDlpInfo(unittest.TestCase):
    """yt-dlp信息解析测试"""

    def test_parse_full_info(self):
        info = {
            "id": "BV1xx411c7mD",
            "title": "测试视频标题",
            "uploader": "UP主名称",
            "channel": "频道名称",
            "duration": 120,
            "view_count": 10000,
            "like_count": 500,
            "comment_count": 100,
            "upload_date": "20240101",
            "description": "这是视频描述",
            "webpage_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "original_url": "https://www.bilibili.com/video/BV1xx411c7mD",
            "thumbnail": "https://example.com/thumb.jpg",
        }
        result = _parse_yt_dlp_info(info)
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "BV1xx411c7mD")
        self.assertEqual(result["title"], "测试视频标题")
        self.assertEqual(result["author"], "UP主名称")
        self.assertEqual(result["duration"], 120.0)
        self.assertEqual(result["view_count"], 10000)
        self.assertEqual(result["like_count"], 500)
        self.assertEqual(result["comment_count"], 100)
        self.assertEqual(result["upload_date"], "20240101")
        self.assertEqual(result["description"], "这是视频描述")
        self.assertEqual(result["webpage_url"], "https://www.bilibili.com/video/BV1xx411c7mD")
        self.assertEqual(result["thumbnail"], "https://example.com/thumb.jpg")
        self.assertEqual(result["platform"], "bilibili")

    def test_parse_empty_info(self):
        info = {}
        result = _parse_yt_dlp_info(info)
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["author"], "")
        self.assertEqual(result["duration"], 0.0)
        self.assertEqual(result["view_count"], 0)
        self.assertEqual(result["like_count"], 0)
        self.assertEqual(result["comment_count"], 0)

    def test_parse_none_values(self):
        info = {
            "id": None,
            "title": None,
            "duration": None,
            "view_count": None,
            "like_count": None,
            "comment_count": None,
            "description": None,
        }
        result = _parse_yt_dlp_info(info)
        self.assertTrue(result["success"])
        self.assertEqual(result["duration"], 0.0)
        self.assertEqual(result["view_count"], 0)
        self.assertEqual(result["like_count"], 0)
        self.assertEqual(result["comment_count"], 0)
        self.assertEqual(result["description"], "")

    def test_parse_author_fallback_chain(self):
        info_with_uploader = {"uploader": "uploader_name"}
        result = _parse_yt_dlp_info(info_with_uploader)
        self.assertEqual(result["author"], "uploader_name")

        info_with_channel = {"channel": "channel_name"}
        result = _parse_yt_dlp_info(info_with_channel)
        self.assertEqual(result["author"], "channel_name")

        info_with_uploader_id = {"uploader_id": "uploader_id_name"}
        result = _parse_yt_dlp_info(info_with_uploader_id)
        self.assertEqual(result["author"], "uploader_id_name")

    def test_parse_webpage_url_fallback(self):
        info_with_original = {"original_url": "https://original.url"}
        result = _parse_yt_dlp_info(info_with_original)
        self.assertEqual(result["webpage_url"], "https://original.url")

    def test_parse_description_truncation(self):
        long_desc = "a" * 600
        info = {"description": long_desc}
        result = _parse_yt_dlp_info(info)
        self.assertEqual(len(result["description"]), 500)

    def test_parse_string_duration(self):
        info = {"duration": "120"}
        result = _parse_yt_dlp_info(info)
        self.assertEqual(result["duration"], 120.0)

    def test_parse_string_view_count(self):
        info = {"view_count": "1000"}
        result = _parse_yt_dlp_info(info)
        self.assertEqual(result["view_count"], 1000)


class TestQualityMap(unittest.TestCase):
    """画质映射表测试"""

    def test_quality_map_contains_standard_qualities(self):
        self.assertIn("360p", QUALITY_MAP)
        self.assertIn("480p", QUALITY_MAP)
        self.assertIn("720p", QUALITY_MAP)
        self.assertIn("1080p", QUALITY_MAP)
        self.assertIn("1080p+", QUALITY_MAP)
        self.assertIn("4k", QUALITY_MAP)

    def test_quality_map_values_are_strings(self):
        for key, value in QUALITY_MAP.items():
            self.assertIsInstance(value, str, f"{key} 的值应为字符串")

    def test_quality_map_increasing(self):
        qualities_order = ["360p", "480p", "720p", "1080p", "1080p+", "4k"]
        values = [int(QUALITY_MAP[q]) for q in qualities_order]
        for i in range(len(values) - 1):
            self.assertLess(values[i], values[i + 1],
                            f"{qualities_order[i]} 应小于 {qualities_order[i+1]}")


class TestSanitizeError(unittest.TestCase):
    """错误信息脱敏测试"""

    def test_sanitize_empty_string(self):
        result = _sanitize_error("")
        self.assertEqual(result, "")

    def test_sanitize_cookie_value(self):
        result = _sanitize_error("cookie=abc123secret")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("abc123secret", result)

    def test_sanitize_SESSDATA(self):
        # SESSDATA 不在敏感模式列表中，不会被替换
        result = _sanitize_error("SESSDATA=mytokensecret")
        self.assertEqual(result, "SESSDATA=mytokensecret")

    def test_sanitize_token(self):
        # token 在敏感模式列表中，会被替换
        result = _sanitize_error("token=secret123")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret123", result)

    def test_sanitize_bili_jct(self):
        result = _sanitize_error("bili_jct=csrfsecret123")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("csrfsecret123", result)

    def test_sanitize_multiple_patterns(self):
        # SESSDATA不在列表中，只有 cookie 和 bili_jct 会被替换
        result = _sanitize_error("cookie=secret1; SESSDATA=secret2; bili_jct=secret3")
        self.assertEqual(result.count("[REDACTED]"), 2)
        self.assertNotIn("secret1", result)
        self.assertIn("secret2", result)
        self.assertNotIn("secret3", result)

    def test_sanitize_case_insensitive(self):
        result = _sanitize_error("Cookie=VALUE123")
        self.assertIn("[REDACTED]", result)

    def test_sanitize_preserves_other_text(self):
        result = _sanitize_error("下载失败: cookie=secret 错误详情: 网络超时")
        self.assertIn("下载失败", result)
        self.assertIn("网络超时", result)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("secret", result)

    def test_sanitize_long_cookie_value(self):
        long_value = "a" * 100
        result = _sanitize_error(f"cookie={long_value}")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn(long_value, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)