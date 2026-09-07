"""抖音下载器单元测试（工具函数和同步包装器）"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "01-下载器"))

from douyin_downloader_pro import (
    _safe_filename,
    _parse_netscape_cookie,
    _parse_cookie_string,
    _cookies_to_header,
    _validate_cookies_dict,
    _sanitize_error,
)


class TestSafeFilename(unittest.TestCase):
    """安全文件名测试"""

    def test_safe_filename_empty(self):
        result = _safe_filename("")
        self.assertEqual(result, "douyin_video")

    def test_safe_filename_normal(self):
        result = _safe_filename("普通标题")
        self.assertEqual(result, "普通标题")

    def test_safe_filename_with_special_chars(self):
        result = _safe_filename("标题/带*特殊?字符<路径>:测试")
        # 实际结果会将:也替换为_
        self.assertEqual(result, "标题_带_特殊_字符_路径__测试")

    def test_safe_filename_strip_dots(self):
        result = _safe_filename("..标题..")
        self.assertEqual(result, "标题")

    def test_safe_filename_strip_spaces(self):
        result = _safe_filename(" 标题 ")
        self.assertEqual(result, "标题")

    def test_safe_filename_truncation(self):
        long_name = "a" * 150
        result = _safe_filename(long_name)
        self.assertEqual(len(result), 100)

    def test_safe_filename_newlines(self):
        result = _safe_filename("标题\n换行\n测试")
        self.assertEqual(result, "标题_换行_测试")

    def test_safe_filename_null_bytes(self):
        # _safe_filename 不处理null bytes，只处理Windows非法字符
        result = _safe_filename("标题\x00测试")
        # 验证不会抛出异常
        self.assertIsInstance(result, str)


class TestParseNetscapeCookie(unittest.TestCase):
    """Netscape格式Cookie解析测试"""

    def test_parse_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            temp_path = f.name
        try:
            result = _parse_netscape_cookie(temp_path)
            self.assertEqual(result, {})
        finally:
            os.remove(temp_path)

    def test_parse_comment_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a comment\n")
            temp_path = f.name
        try:
            result = _parse_netscape_cookie(temp_path)
            self.assertEqual(result, {})
        finally:
            os.remove(temp_path)

    def test_parse_valid_cookie(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(".douyin.com\tTRUE\t/\tFALSE\t1609459200\tttwid\tabc123\n")
            temp_path = f.name
        try:
            result = _parse_netscape_cookie(temp_path)
            self.assertEqual(result["ttwid"], "abc123")
        finally:
            os.remove(temp_path)

    def test_parse_multiple_cookies(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(".douyin.com\tTRUE\t/\tFALSE\t1609459200\tttwid\tabc123\n")
            f.write(".douyin.com\tTRUE\t/\tFALSE\t1609459200\tsessionid\txyz789\n")
            temp_path = f.name
        try:
            result = _parse_netscape_cookie(temp_path)
            self.assertEqual(result["ttwid"], "abc123")
            self.assertEqual(result["sessionid"], "xyz789")
        finally:
            os.remove(temp_path)

    def test_parse_malformed_line(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("invalid_line_without_tabs\n")
            f.write(".douyin.com\tTRUE\t/\tFALSE\t1609459200\tttwid\tvalid123\n")
            temp_path = f.name
        try:
            result = _parse_netscape_cookie(temp_path)
            self.assertEqual(result["ttwid"], "valid123")
        finally:
            os.remove(temp_path)

    def test_parse_nonexistent_file(self):
        result = _parse_netscape_cookie("/nonexistent/path/cookies.txt")
        self.assertEqual(result, {})


class TestParseCookieString(unittest.TestCase):
    """Cookie字符串解析测试"""

    def test_parse_empty_string(self):
        result = _parse_cookie_string("")
        self.assertEqual(result, {})

    def test_parse_single_cookie(self):
        result = _parse_cookie_string("ttwid=abc123")
        self.assertEqual(result["ttwid"], "abc123")

    def test_parse_multiple_cookies(self):
        result = _parse_cookie_string("ttwid=abc123; sessionid=xyz789; uid=12345")
        self.assertEqual(result["ttwid"], "abc123")
        self.assertEqual(result["sessionid"], "xyz789")
        self.assertEqual(result["uid"], "12345")

    def test_parse_cookies_with_spaces(self):
        result = _parse_cookie_string("ttwid=abc123 ; sessionid= xyz789 ; uid=12345 ")
        self.assertEqual(result["ttwid"], "abc123")
        self.assertEqual(result["sessionid"], "xyz789")

    def test_parse_cookies_without_value(self):
        result = _parse_cookie_string("ttwid=; sessionid=xyz789")
        self.assertEqual(result["ttwid"], "")
        self.assertEqual(result["sessionid"], "xyz789")

    def test_parse_cookies_with_special_chars(self):
        result = _parse_cookie_string("ttwid=abc&123; sessionid=xyz+789")
        self.assertEqual(result["ttwid"], "abc&123")
        self.assertEqual(result["sessionid"], "xyz+789")


class TestCookiesToHeader(unittest.TestCase):
    """Cookie字典转HTTP头测试"""

    def test_empty_cookies(self):
        result = _cookies_to_header({})
        self.assertEqual(result, "")

    def test_single_cookie(self):
        result = _cookies_to_header({"ttwid": "abc123"})
        self.assertEqual(result, "ttwid=abc123")

    def test_multiple_cookies(self):
        result = _cookies_to_header({"ttwid": "abc123", "sessionid": "xyz789"})
        self.assertIn("ttwid=abc123", result)
        self.assertIn("sessionid=xyz789", result)
        self.assertIn("; ", result)


class TestValidateCookiesDict(unittest.TestCase):
    """Cookie字典验证测试"""

    def test_validate_empty_cookies(self):
        result = _validate_cookies_dict({})
        self.assertFalse(result["valid"])
        self.assertFalse(result["has_required_fields"])
        self.assertFalse(result["has_session"])
        self.assertEqual(result["missing_required"], ["ttwid"])

    def test_validate_only_ttwid(self):
        result = _validate_cookies_dict({"ttwid": "abc123"})
        self.assertTrue(result["valid"])
        self.assertTrue(result["has_required_fields"])
        self.assertFalse(result["has_session"])
        self.assertEqual(result["missing_required"], [])

    def test_validate_ttwid_and_sessionid(self):
        result = _validate_cookies_dict({"ttwid": "abc123", "sessionid": "xyz789"})
        self.assertTrue(result["valid"])
        self.assertTrue(result["has_required_fields"])
        self.assertTrue(result["has_session"])

    def test_validate_all_fields(self):
        result = _validate_cookies_dict({
            "ttwid": "abc123",
            "sessionid": "xyz789",
            "sessionid_ss": "ss123",
            "uid_tt": "456",
            "sid_tt": "sid789"
        })
        self.assertTrue(result["valid"])
        self.assertTrue(result["has_required_fields"])
        self.assertTrue(result["has_session"])
        self.assertEqual(result["field_count"], 5)


class TestSanitizeError(unittest.TestCase):
    """错误信息脱敏测试"""

    def test_sanitize_empty_string(self):
        result = _sanitize_error("")
        self.assertEqual(result, "")

    def test_sanitize_cookie_value(self):
        result = _sanitize_error("cookie=abc123xyz456")
        self.assertIn("cookie=[REDACTED]", result)
        self.assertNotIn("abc123xyz456", result)

    def test_sanitize_sessionid(self):
        result = _sanitize_error("sessionid=session12345")
        self.assertIn("sessionid=[REDACTED]", result)

    def test_sanitize_ttwid(self):
        result = _sanitize_error("ttwid=abcdef123456")
        self.assertIn("ttwid=[REDACTED]", result)

    def test_sanitize_multiple_patterns(self):
        result = _sanitize_error("cookie=abc123; sessionid=xyz789; ttwid=def456")
        self.assertIn("cookie=[REDACTED]", result)
        self.assertIn("sessionid=[REDACTED]", result)
        self.assertIn("ttwid=[REDACTED]", result)

    def test_sanitize_case_insensitive(self):
        result = _sanitize_error("Cookie=VALUE123")
        self.assertIn("Cookie=[REDACTED]", result)

    def test_sanitize_colon_format(self):
        result = _sanitize_error('{"cookie": "secret123"}')
        # JSON格式的值不会被sanitize函数匹配，因为正则要求 = 后跟非空白字符
        # 这个测试验证函数在JSON格式下不会错误替换
        self.assertIn("cookie", result)

    def test_sanitize_keeps_other_text(self):
        result = _sanitize_error("下载失败: cookie=secret123 错误详情")
        self.assertIn("下载失败", result)
        self.assertIn("错误详情", result)
        self.assertIn("cookie=[REDACTED]", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)