"""跨平台搜索器单元测试"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from cross_platform_searcher import CrossPlatformSearcher


class TestDeduplication(unittest.TestCase):
    """跨平台去重测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_deduplicate_empty_results(self):
        result = self.searcher.deduplicate([])
        self.assertEqual(result, [])

    def test_deduplicate_url_hash(self):
        results = [
            {"url": "https://example.com/video1", "title": "Video 1"},
            {"url": "https://example.com/video1", "title": "Video 1"},
        ]
        deduplicated = self.searcher.deduplicate(results)
        self.assertEqual(len(deduplicated), 1)

    def test_deduplicate_title_similarity(self):
        results = [
            {"url": "https://example.com/video1", "title": "beautiful sunset beach"},
            {"url": "https://example.com/video2", "title": "Beautiful Sunset Beach!"},
            {"url": "https://example.com/video3", "title": "ocean waves"},
        ]
        deduplicated = self.searcher.deduplicate(results)
        self.assertEqual(len(deduplicated), 2)

    def test_deduplicate_no_duplicates(self):
        results = [
            {"url": "https://example.com/video1", "title": "Video 1"},
            {"url": "https://example.com/video2", "title": "Video 2"},
            {"url": "https://example.com/video3", "title": "Video 3"},
        ]
        deduplicated = self.searcher.deduplicate(results)
        self.assertEqual(len(deduplicated), 3)


class TestTitleSimilarity(unittest.TestCase):
    """标题相似度测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_title_similarity_identical(self):
        score = self.searcher._title_similarity("test title", "test title")
        self.assertEqual(score, 1.0)

    def test_title_similarity_similar(self):
        score = self.searcher._title_similarity("beautiful sunset", "beautiful sunset")
        self.assertGreater(score, 0.9)

    def test_title_similarity_different(self):
        score = self.searcher._title_similarity("beautiful sunset", "ocean waves")
        self.assertLess(score, 0.5)

    def test_title_similarity_empty(self):
        score = self.searcher._title_similarity("", "")
        self.assertEqual(score, 1.0)

    def test_title_similarity_one_empty(self):
        score = self.searcher._title_similarity("test", "")
        self.assertEqual(score, 0.0)


class TestQualityEvaluation(unittest.TestCase):
    """质量评估测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_evaluate_quality_empty(self):
        result = self.searcher.evaluate_quality([])
        self.assertEqual(result, [])

    def test_evaluate_quality_4k(self):
        results = [{"quality": "4k", "watermark": False, "view_count": 2000000, "duration": 60}]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertGreater(evaluated[0]["quality_score"], 0.5)
        self.assertIn("4K画质", evaluated[0]["quality_factors"])
        self.assertIn("无水印", evaluated[0]["quality_factors"])

    def test_evaluate_quality_high_with_watermark(self):
        results = [{"quality": "high", "watermark": True, "view_count": 100000, "duration": 30}]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertGreater(evaluated[0]["quality_score"], 0.3)

    def test_evaluate_quality_medium(self):
        results = [{"quality": "medium", "watermark": True, "view_count": 1000, "duration": 10}]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertGreater(evaluated[0]["quality_score"], 0.0)
        self.assertLess(evaluated[0]["quality_score"], 0.5)

    def test_evaluate_quality_sorting(self):
        results = [
            {"quality": "medium", "watermark": True, "view_count": 1000},
            {"quality": "4k", "watermark": False, "view_count": 1000000},
            {"quality": "high", "watermark": False, "view_count": 100000},
        ]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertEqual(evaluated[0]["quality"], "4k")
        self.assertEqual(evaluated[1]["quality"], "high")
        self.assertEqual(evaluated[2]["quality"], "medium")

    def test_evaluate_quality_like_ratio(self):
        results = [
            {"quality": "medium", "view_count": 100000, "like_count": 15000},
            {"quality": "medium", "view_count": 100000, "like_count": 3000},
        ]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertGreater(evaluated[0]["quality_score"], evaluated[1]["quality_score"])


class TestResultMerging(unittest.TestCase):
    """结果合并测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_merge_results_empty(self):
        result = self.searcher.merge_results([], [])
        self.assertEqual(result, [])

    def test_merge_results_local_only(self):
        local_results = [{"similarity": 0.9, "file_path": "test1.mp4"}]
        merged = self.searcher.merge_results(local_results, [])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "local")

    def test_merge_results_remote_only(self):
        remote_results = [{"quality_score": 0.8, "url": "test_url"}]
        merged = self.searcher.merge_results([], remote_results)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source"], "remote")

    def test_merge_results_both(self):
        local_results = [{"similarity": 0.9, "file_path": "test1.mp4", "title": "local video"}]
        remote_results = [{"quality_score": 0.8, "url": "test_url", "title": "remote video"}]
        merged = self.searcher.merge_results(local_results, remote_results)
        self.assertEqual(len(merged), 2)

    def test_merge_results_weights(self):
        local_results = [{"similarity": 0.5, "file_path": "test1.mp4"}]
        remote_results = [{"quality_score": 1.0, "url": "test_url"}]
        
        merged_high_local = self.searcher.merge_results(local_results, remote_results, local_weight=0.9, remote_weight=0.1)
        merged_high_remote = self.searcher.merge_results(local_results, remote_results, local_weight=0.1, remote_weight=0.9)
        
        self.assertGreater(merged_high_local[0]["final_score"], merged_high_remote[0]["final_score"])

    def test_merge_results_deduplication(self):
        local_results = [{"similarity": 0.9, "title": "same video"}]
        remote_results = [{"quality_score": 0.8, "title": "same video"}]
        merged = self.searcher.merge_results(local_results, remote_results)
        self.assertEqual(len(merged), 1)


class TestSearch(unittest.TestCase):
    """搜索功能测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_search_empty_query(self):
        results = self.searcher.search("")
        self.assertEqual(results, [])

    def test_search_with_platforms(self):
        results = self.searcher.search("test query", platforms=["douyin"])
        self.assertIsInstance(results, list)

    def test_search_downloaders_unavailable(self):
        import unittest.mock as mock
        with mock.patch.object(sys.modules['cross_platform_searcher'], 'DOWNLOADERS_AVAILABLE', False):
            searcher = CrossPlatformSearcher()
            results = searcher.search("test")
            self.assertEqual(results, [])


class TestSearchResultConversion(unittest.TestCase):
    """搜索结果转换测试"""

    def setUp(self):
        self.searcher = CrossPlatformSearcher()

    def test_search_result_to_dict(self):
        from cross_platform_searcher import SearchResult
        
        result = SearchResult(
            url="https://example.com/video",
            title="Test Video",
            platform="douyin",
            duration=60,
            view_count=10000,
            like_count=500
        )
        
        result_dict = result.to_dict()
        self.assertEqual(result_dict["url"], "https://example.com/video")
        self.assertEqual(result_dict["title"], "Test Video")
        self.assertEqual(result_dict["platform"], "douyin")
        self.assertEqual(result_dict["duration"], 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)