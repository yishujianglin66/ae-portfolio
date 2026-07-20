"""统一搜索单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "02-免费素材API"))

from unified_search import (
    UnifiedSearch,
    _load_api_keys,
    _normalize_title_similarity,
    _dedup_results,
    _safe_call,
    SUPPORTED_MEDIA_TYPES,
    SUPPORTED_PLATFORMS,
    InvalidPlatformError,
)


class TestTitleSimilarity(unittest.TestCase):
    """标题相似度测试"""

    def test_identical_titles(self):
        sim = _normalize_title_similarity("same title", "same title")
        self.assertEqual(sim, 1.0)

    def test_completely_different(self):
        sim = _normalize_title_similarity("completely different", "totally unrelated")
        self.assertLess(sim, 0.5)

    def test_partial_match(self):
        sim = _normalize_title_similarity("beautiful sunset beach", "sunset beach landscape")
        self.assertGreater(sim, 0.5)

    def test_empty_title(self):
        sim = _normalize_title_similarity("", "")
        self.assertEqual(sim, 0.0)

    def test_one_empty_title(self):
        sim = _normalize_title_similarity("test", "")
        self.assertEqual(sim, 0.0)

    def test_case_insensitive(self):
        sim = _normalize_title_similarity("Sunset Beach", "sunset beach")
        self.assertEqual(sim, 1.0)

    def test_punctuation_stripped(self):
        sim = _normalize_title_similarity("beach, sunset!", "beach sunset")
        self.assertEqual(sim, 1.0)


class TestDedupResults(unittest.TestCase):
    """去重逻辑测试"""

    def test_no_duplicates(self):
        results = [
            {"title": "sunset beach landscape ocean"},
            {"title": "mountain forest hiking trail"},
            {"title": "city night lights urban"},
        ]
        deduped = _dedup_results(results)
        self.assertEqual(len(deduped), 3)

    def test_exact_duplicates(self):
        results = [
            {"title": "same video"},
            {"title": "same video"},
            {"title": "different video"},
        ]
        deduped = _dedup_results(results)
        self.assertEqual(len(deduped), 2)

    def test_similar_duplicates(self):
        results = [
            {"title": "beautiful sunset beach"},
            {"title": "Beautiful Sunset Beach!"},
            {"title": "ocean waves"},
        ]
        deduped = _dedup_results(results)
        self.assertEqual(len(deduped), 2)

    def test_empty_results(self):
        results = []
        deduped = _dedup_results(results)
        self.assertEqual(deduped, [])

    def test_results_without_title(self):
        results = [
            {"title": "video 1"},
            {},
            {"title": "video 1"},
        ]
        deduped = _dedup_results(results)
        self.assertEqual(len(deduped), 2)


class TestAPIKeyLoading(unittest.TestCase):
    """API Key加载测试"""

    def test_env_var_priority(self):
        os.environ["PIXABAY_API_KEY"] = "env_test_key"
        try:
            keys = _load_api_keys()
            self.assertEqual(keys["pixabay_api_key"], "env_test_key")
        finally:
            del os.environ["PIXABAY_API_KEY"]

    def test_default_empty_keys(self):
        keys = _load_api_keys()
        self.assertIn("pixabay_api_key", keys)
        self.assertIn("pexels_api_key", keys)
        self.assertIn("jamendo_client_id", keys)


class TestSafeCall(unittest.TestCase):
    """安全调用测试"""

    def test_safe_call_success(self):
        def success_fn():
            return {"success": True, "data": "test"}

        result = _safe_call(success_fn)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], "test")

    def test_safe_call_exception(self):
        def error_fn():
            raise ValueError("test error")

        result = _safe_call(error_fn)
        self.assertFalse(result["success"])
        self.assertIn("test error", result.get("error", ""))

    def test_safe_call_timeout_returns_quickly(self):
        """超时应快速返回错误，不被 with 语句的 shutdown(wait=True) 阻塞"""
        import time
        def slow_fn():
            time.sleep(5)
            return {"success": True}

        start = time.time()
        result = _safe_call(slow_fn, timeout=0.5)
        elapsed = time.time() - start
        # 应在 3 秒内返回（超时 0.5s + 容差），证明 shutdown(wait=False) 生效
        self.assertLess(elapsed, 3.0)
        self.assertFalse(result["success"])
        self.assertIn("超时", result.get("error", ""))


class TestUnifiedSearchValidation(unittest.TestCase):
    """统一搜索参数校验测试"""

    def setUp(self):
        self.search = UnifiedSearch(api_keys={})

    def test_invalid_media_type(self):
        with self.assertRaises(ValueError):
            self.search.search_all("test", media_type="invalid")

    def test_empty_query(self):
        with self.assertRaises(ValueError):
            self.search.search_all("")

    def test_query_not_string(self):
        with self.assertRaises(ValueError):
            self.search.search_all(123)

    def test_per_page_too_small(self):
        with self.assertRaises(ValueError):
            self.search.search_all("test", per_page=0)

    def test_per_page_too_large(self):
        with self.assertRaises(ValueError):
            self.search.search_all("test", per_page=201)

    def test_no_api_keys(self):
        result = self.search.search_all("test")
        self.assertFalse(result["success"])
        self.assertIn("未配置", result.get("error", ""))

    def test_search_videos_shortcut(self):
        result = self.search.search_videos("test")
        self.assertFalse(result["success"])

    def test_search_images_shortcut(self):
        result = self.search.search_images("test")
        self.assertFalse(result["success"])

    def test_search_music_shortcut(self):
        result = self.search.search_music("test")
        self.assertFalse(result["success"])


class TestDownloadMediaValidation(unittest.TestCase):
    """下载媒体参数校验测试"""

    def setUp(self):
        self.search = UnifiedSearch(api_keys={})

    def test_invalid_platform(self):
        with self.assertRaises(InvalidPlatformError):
            self.search.download_media("invalid", "123", "/tmp")

    def test_empty_media_id(self):
        with self.assertRaises(ValueError):
            self.search.download_media("pixabay", "", "/tmp")

    def test_empty_output_dir(self):
        with self.assertRaises(ValueError):
            self.search.download_media("pixabay", "123", "")


class TestSupportedConstants(unittest.TestCase):
    """支持常量测试"""

    def test_supported_media_types(self):
        self.assertIn("all", SUPPORTED_MEDIA_TYPES)
        self.assertIn("videos", SUPPORTED_MEDIA_TYPES)
        self.assertIn("images", SUPPORTED_MEDIA_TYPES)
        self.assertIn("music", SUPPORTED_MEDIA_TYPES)

    def test_supported_platforms(self):
        self.assertIn("pixabay", SUPPORTED_PLATFORMS)
        self.assertIn("pexels", SUPPORTED_PLATFORMS)
        self.assertIn("jamendo", SUPPORTED_PLATFORMS)


if __name__ == "__main__":
    unittest.main(verbosity=2)