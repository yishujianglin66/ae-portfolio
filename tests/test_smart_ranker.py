"""智能排序器单元测试"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from smart_ranker import SmartRanker


class TestSmartRankerBasic(unittest.TestCase):
    """智能排序器基础测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_rank_empty_results(self):
        result = self.ranker.rank([])
        self.assertEqual(result, [])

    def test_rank_single_result(self):
        results = [{"similarity": 0.9, "quality_score": 0.8}]
        result = self.ranker.rank(results)
        self.assertEqual(len(result), 1)
        self.assertIn("final_score", result[0])

    def test_rank_results_with_scores(self):
        results = [
            {"similarity": 0.9, "quality_score": 0.8},
            {"similarity": 0.8, "quality_score": 0.9},
        ]
        result = self.ranker.rank(results)
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIn("scores", item)
            self.assertIn("final_score", item)


class TestMultiDimensionScoring(unittest.TestCase):
    """多维度评分融合测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_score_semantic(self):
        results = [{"similarity": 0.9}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["semantic"], 0)

    def test_score_quality(self):
        results = [{"quality_score": 0.8}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["quality"], 0)

    def test_score_audio(self):
        results = [{"audio_match_score": 0.7}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["audio"], 0)

    def test_score_popularity(self):
        results = [{"view_count": 1000000, "like_count": 100000}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["popularity"], 0)

    def test_score_freshness(self):
        results = [{"metadata": {"upload_time": "2026-01-01T00:00:00Z"}}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["freshness"], 0)

    def test_score_freshness_no_timestamp(self):
        results = [{"metadata": {}}]
        scored = self.ranker._score_results(results, None, None, None)
        self.assertGreater(scored[0]["scores"]["freshness"], 0)
        self.assertLess(scored[0]["scores"]["freshness"], 0.1)


class TestMoodWeightAdjustments(unittest.TestCase):
    """情绪权重调整测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_mood_adjustment_happy(self):
        results = [{"similarity": 0.9, "audio_match_score": 0.8}]
        scored = self.ranker._score_results(results, "happy", None, None)
        semantic_score = scored[0]["scores"]["semantic"]
        audio_score = scored[0]["scores"]["audio"]
        
        baseline_ranker = SmartRanker()
        baseline_scored = baseline_ranker._score_results(results, None, None, None)
        baseline_semantic = baseline_scored[0]["scores"]["semantic"]
        baseline_audio = baseline_scored[0]["scores"]["audio"]
        
        self.assertGreater(semantic_score, baseline_semantic)
        self.assertGreater(audio_score, baseline_audio)

    def test_mood_adjustment_romantic(self):
        results = [{"similarity": 0.9, "audio_match_score": 0.8}]
        scored = self.ranker._score_results(results, "romantic", None, None)
        audio_score = scored[0]["scores"]["audio"]
        
        baseline_ranker = SmartRanker()
        baseline_scored = baseline_ranker._score_results(results, None, None, None)
        baseline_audio = baseline_scored[0]["scores"]["audio"]
        
        self.assertGreater(audio_score, baseline_audio)

    def test_mood_adjustment_unknown(self):
        results = [{"similarity": 0.9}]
        scored = self.ranker._score_results(results, "unknown_mood", None, None)
        self.assertIn("scores", scored[0])


class TestDiversityGuarantee(unittest.TestCase):
    """多样性保障测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_diversity_with_few_results(self):
        results = [
            {"similarity": 0.9, "platform": "douyin", "final_score": 0.9},
            {"similarity": 0.8, "platform": "douyin", "final_score": 0.8},
        ]
        adjusted = self.ranker._ensure_diversity(results)
        self.assertEqual(len(adjusted), 2)

    def test_diversity_penalty(self):
        results = [
            {"similarity": 0.9, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.9},
            {"similarity": 0.85, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.85},
            {"similarity": 0.8, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.8},
            {"similarity": 0.75, "platform": "bilibili", "audio_features": {"mood": "sad"}, "final_score": 0.75},
            {"similarity": 0.7, "platform": "youtube", "audio_features": {"mood": "excited"}, "final_score": 0.7},
            {"similarity": 0.65, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.65},
        ]
        adjusted = self.ranker._ensure_diversity(results)
        for item in adjusted:
            self.assertIn("diversity_penalty", item)
            self.assertIn("diversity_penalty_details", item)

    def test_diversity_adjusts_scores(self):
        results = [
            {"similarity": 0.9, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.9},
            {"similarity": 0.85, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.85},
            {"similarity": 0.8, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.8},
            {"similarity": 0.75, "platform": "bilibili", "audio_features": {"mood": "sad"}, "final_score": 0.75},
            {"similarity": 0.7, "platform": "youtube", "audio_features": {"mood": "excited"}, "final_score": 0.7},
            {"similarity": 0.65, "platform": "douyin", "audio_features": {"mood": "happy"}, "final_score": 0.65},
        ]
        adjusted = self.ranker._ensure_diversity(results)
        
        douyin_items = [item for item in adjusted if item["platform"] == "douyin"]
        bilibili_item = [item for item in adjusted if item["platform"] == "bilibili"][0]
        
        douyin_penalty = sum(item["diversity_penalty"] for item in douyin_items)
        self.assertGreater(douyin_penalty, bilibili_item["diversity_penalty"])


class TestWeightAdjustments(unittest.TestCase):
    """权重调整测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_adjust_weights_increase(self):
        original_weight = self.ranker.weights["semantic"]
        self.ranker.adjust_weights({"semantic": 1.2})
        self.assertGreater(self.ranker.weights["semantic"], original_weight)

    def test_adjust_weights_decrease(self):
        original_weight = self.ranker.weights["quality"]
        self.ranker.adjust_weights({"quality": 0.8})
        self.assertLess(self.ranker.weights["quality"], original_weight)

    def test_adjust_weights_clamping(self):
        self.ranker.adjust_weights({"semantic": 10.0})
        self.assertEqual(self.ranker.weights["semantic"], 0.99)
        
        self.ranker.adjust_weights({"semantic": 0.0})
        self.assertEqual(self.ranker.weights["semantic"], 0.01)

    def test_adjust_weights_invalid_key(self):
        self.ranker.adjust_weights({"invalid_key": 2.0})
        self.assertNotIn("invalid_key", self.ranker.weights)

    def test_get_weight_summary(self):
        summary = self.ranker.get_weight_summary()
        self.assertIn("semantic", summary)
        self.assertIn("quality", summary)
        self.assertIn("audio", summary)
        self.assertIn("popularity", summary)
        self.assertIn("freshness", summary)


class TestPopularityScoreCalculation(unittest.TestCase):
    """热度分数计算测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_calculate_popularity_score_high(self):
        result = {"view_count": 10000000, "like_count": 1000000, "download_count": 100000}
        score = self.ranker._calculate_popularity_score(result)
        self.assertGreaterEqual(score, 0.9)

    def test_calculate_popularity_score_medium(self):
        result = {"view_count": 100000, "like_count": 10000, "download_count": 1000}
        score = self.ranker._calculate_popularity_score(result)
        self.assertGreater(score, 0.0)
        self.assertLess(score, 0.5)

    def test_calculate_popularity_score_zero(self):
        result = {"view_count": 0, "like_count": 0, "download_count": 0}
        score = self.ranker._calculate_popularity_score(result)
        self.assertEqual(score, 0.0)


class TestFreshnessScoreCalculation(unittest.TestCase):
    """新鲜度分数计算测试"""

    def setUp(self):
        self.ranker = SmartRanker()

    def test_calculate_freshness_score_recent(self):
        from datetime import datetime, timedelta
        recent_time = (datetime.now() - timedelta(days=0)).isoformat()
        result = {"metadata": {"upload_time": recent_time}}
        score = self.ranker._calculate_freshness_score(result)
        self.assertEqual(score, 1.0)

    def test_calculate_freshness_score_30_days(self):
        from datetime import datetime, timedelta
        old_time = (datetime.now() - timedelta(days=15)).isoformat()
        result = {"metadata": {"upload_time": old_time}}
        score = self.ranker._calculate_freshness_score(result)
        self.assertEqual(score, 0.7)

    def test_calculate_freshness_score_no_metadata(self):
        result = {}
        score = self.ranker._calculate_freshness_score(result)
        self.assertEqual(score, 0.5)

    def test_calculate_freshness_score_invalid_date(self):
        result = {"metadata": {"upload_time": "invalid_date"}}
        score = self.ranker._calculate_freshness_score(result)
        self.assertEqual(score, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)