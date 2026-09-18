"""下载器工具函数单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "01-下载器"))

from douyin_downloader_pro import (
    COOKIE_OPTIONAL_FIELDS,
    COOKIE_REQUIRED_FIELDS,
    _cookies_to_header,
    _get_env_or_default,
    _parse_cookie_string,
    _parse_netscape_cookie,
    _resolve_cookie_source,
    _safe_filename,
    _validate_cookies_dict,
)
from unified_downloader import detect_platform


class TestSafeFilename(unittest.TestCase):
    """文件名清理函数测试"""

    def test_empty_name(self):
        result = _safe_filename("")
        self.assertEqual(result, "douyin_video")

    def test_normal_name(self):
        result = _safe_filename("test video")
        self.assertEqual(result, "test video")

    def test_illegal_characters(self):
        result = _safe_filename('test/video"name*<>:|')
        self.assertEqual(result, "test_video_name_____")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertNotIn('"', result)
        self.assertNotIn("*", result)
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn(":", result)
        self.assertNotIn("|", result)

    def test_trim_whitespace(self):
        result = _safe_filename("  test  ")
        self.assertEqual(result, "test")

    def test_trim_dots(self):
        result = _safe_filename(".test.")
        self.assertEqual(result, "test")

    def test_length_limit(self):
        long_name = "a" * 200
        result = _safe_filename(long_name)
        self.assertEqual(len(result), 100)

    def test_unicode_filename(self):
        result = _safe_filename("测试视频标题")
        self.assertEqual(result, "测试视频标题")

    def test_filename_with_special_chars(self):
        result = _safe_filename("test\nvideo\rwith\ttabs")
        self.assertEqual(result, "test_video_with_tabs")


class TestCookieParsing(unittest.TestCase):
    """Cookie解析函数测试"""

    def test_parse_netscape_cookie_nonexistent(self):
        cookies = _parse_netscape_cookie("/nonexistent/path.txt")
        self.assertEqual(cookies, {})

    def test_parse_netscape_cookie_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("www.douyin.com\tTRUE\t/\tFALSE\t0\tttwid\tabc123\n")
            f.write("www.douyin.com\tTRUE\t/\tFALSE\t0\tsessionid\txyz789\n")
            temp_path = f.name

        try:
            cookies = _parse_netscape_cookie(temp_path)
            self.assertEqual(cookies["ttwid"], "abc123")
            self.assertEqual(cookies["sessionid"], "xyz789")
        finally:
            os.unlink(temp_path)

    def test_parse_netscape_cookie_skips_comments(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("# Comment line 1\n")
            f.write("# Comment line 2\n")
            f.write("www.test.com\tTRUE\t/\tFALSE\t0\tkey\tvalue\n")
            temp_path = f.name

        try:
            cookies = _parse_netscape_cookie(temp_path)
            self.assertEqual(cookies["key"], "value")
        finally:
            os.unlink(temp_path)

    def test_parse_cookie_string_empty(self):
        cookies = _parse_cookie_string("")
        self.assertEqual(cookies, {})

    def test_parse_cookie_string_single(self):
        cookies = _parse_cookie_string("key=value")
        self.assertEqual(cookies, {"key": "value"})

    def test_parse_cookie_string_multiple(self):
        cookies = _parse_cookie_string("ttwid=abc; sessionid=xyz; uid=123")
        self.assertEqual(cookies["ttwid"], "abc")
        self.assertEqual(cookies["sessionid"], "xyz")
        self.assertEqual(cookies["uid"], "123")

    def test_parse_cookie_string_with_whitespace(self):
        cookies = _parse_cookie_string("  ttwid=abc  ;  sessionid=xyz  ")
        self.assertEqual(cookies["ttwid"], "abc")
        self.assertEqual(cookies["sessionid"], "xyz")

    def test_parse_cookie_string_with_empty(self):
        cookies = _parse_cookie_string("ttwid=abc;;sessionid=xyz")
        self.assertEqual(cookies["ttwid"], "abc")
        self.assertEqual(cookies["sessionid"], "xyz")

    def test_cookies_to_header_empty(self):
        header = _cookies_to_header({})
        self.assertEqual(header, "")

    def test_cookies_to_header_single(self):
        header = _cookies_to_header({"key": "value"})
        self.assertEqual(header, "key=value")

    def test_cookies_to_header_multiple(self):
        header = _cookies_to_header({"a": "1", "b": "2", "c": "3"})
        self.assertIn("a=1", header)
        self.assertIn("b=2", header)
        self.assertIn("c=3", header)


class TestCookieResolution(unittest.TestCase):
    """Cookie来源解析测试"""

    def test_resolve_cookie_string(self):
        cookies, path = _resolve_cookie_source(cookie="ttwid=abc")
        self.assertEqual(cookies["ttwid"], "abc")
        self.assertIsNone(path)

    def test_resolve_cookie_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("www.test.com\tTRUE\t/\tFALSE\t0\tttwid\tfrom_file\n")
            temp_path = f.name

        try:
            cookies, path = _resolve_cookie_source(cookie_path=temp_path)
            self.assertEqual(cookies["ttwid"], "from_file")
            self.assertEqual(path, temp_path)
        finally:
            os.unlink(temp_path)

    def test_resolve_cookie_nonexistent_file(self):
        """不存在的cookie文件应回退到空结果（密闭隔离：环境变量/默认路径/项目内cookies回退全部失效）"""
        import unittest.mock as mock

        import douyin_downloader_pro as ddp
        with mock.patch.dict(os.environ, {"DOUYIN_COOKIE": "", "DOUYIN_COOKIE_PATH": ""}), \
             mock.patch.object(ddp, 'DEFAULT_COOKIE_PATH', '/nonexistent/default.txt'), \
             mock.patch('os.path.exists', return_value=False):
            cookies, path = _resolve_cookie_source(cookie_path="/nonexistent/file.txt")
            self.assertEqual(cookies, {})
            self.assertIsNone(path)

    def test_validate_cookies_has_required(self):
        cookies = {"ttwid": "test"}
        result = _validate_cookies_dict(cookies)
        self.assertTrue(result["valid"])
        self.assertTrue(result["has_required_fields"])
        self.assertEqual(result["missing_required"], [])

    def test_validate_cookies_missing_required(self):
        cookies = {"sessionid": "test"}
        result = _validate_cookies_dict(cookies)
        self.assertFalse(result["valid"])
        self.assertFalse(result["has_required_fields"])
        self.assertIn("ttwid", result["missing_required"])

    def test_validate_cookies_has_session(self):
        cookies = {"ttwid": "test", "sessionid": "abc"}
        result = _validate_cookies_dict(cookies)
        self.assertTrue(result["has_session"])

    def test_validate_cookies_no_session(self):
        cookies = {"ttwid": "test"}
        result = _validate_cookies_dict(cookies)
        self.assertFalse(result["has_session"])


class TestEnvOrDefault(unittest.TestCase):
    """环境变量获取函数测试"""

    def test_env_exists(self):
        os.environ["TEST_ENV_KEY_ABC"] = "test_value"
        try:
            result = _get_env_or_default("TEST_ENV_KEY_ABC", "default")
            self.assertEqual(result, "test_value")
        finally:
            del os.environ["TEST_ENV_KEY_ABC"]

    def test_env_not_exists(self):
        result = _get_env_or_default("NONEXISTENT_ENV_VAR", "default_value")
        self.assertEqual(result, "default_value")


class TestPlatformDetection(unittest.TestCase):
    """平台识别函数测试"""

    def test_detect_douyin_short_url(self):
        platform = detect_platform("https://v.douyin.com/xxx/")
        self.assertEqual(platform, "douyin")

    def test_detect_douyin_long_url(self):
        platform = detect_platform("https://www.douyin.com/video/12345")
        self.assertEqual(platform, "douyin")

    def test_detect_douyin_ies(self):
        platform = detect_platform("https://iesdouyin.com/share/xxx")
        self.assertEqual(platform, "douyin")

    def test_detect_bilibili(self):
        platform = detect_platform("https://www.bilibili.com/video/BVxxx")
        self.assertEqual(platform, "bilibili")

    def test_detect_bilibili_short(self):
        platform = detect_platform("https://b23.tv/xxx")
        self.assertEqual(platform, "bilibili")

    def test_detect_youtube(self):
        platform = detect_platform("https://www.youtube.com/watch?v=xxx")
        self.assertEqual(platform, "youtube")

    def test_detect_youtube_short(self):
        platform = detect_platform("https://youtu.be/xxx")
        self.assertEqual(platform, "youtube")

    def test_detect_kuaishou(self):
        platform = detect_platform("https://www.kuaishou.com/f/xxx")
        self.assertEqual(platform, "kuaishou")

    def test_detect_tiktok(self):
        platform = detect_platform("https://www.tiktok.com/@user/video/xxx")
        self.assertEqual(platform, "tiktok")

    def test_detect_unknown(self):
        platform = detect_platform("https://example.com/video")
        self.assertIsNone(platform)

    def test_detect_empty(self):
        platform = detect_platform("")
        self.assertIsNone(platform)

    def test_detect_none(self):
        platform = detect_platform(None)
        self.assertIsNone(platform)


if __name__ == "__main__":
    unittest.main(verbosity=2)