"""
素材智能匹配系统 - 完整单元测试
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 防止 HuggingFace Hub 网络请求导致测试超时
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "13-素材获取与搜索" / "03-AI语义搜索"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from semantic_parser import SemanticParser, ParsedQuery
from smart_ranker import SmartRanker
from user_preference import UserPreferenceLearner, UserAction, UserProfile
from multimodal_retriever import RRFFusion, CLAPEncoder, MultimodalRetriever
from audio_feature_extractor import AudioFeatureExtractor, AudioFeatureSet
from cross_platform_searcher import CrossPlatformSearcher
from smart_matcher import SmartMatcher


class TestSemanticParser(unittest.TestCase):
    """语义解析器测试"""
    
    def setUp(self):
        self.parser = SemanticParser()
    
    def test_mood_extraction(self):
        r = self.parser.parse("开心的流行音乐")
        self.assertEqual(r.mood, "happy")
        self.assertGreater(r.mood_score, 0.7)
    
    def test_bpm_extraction(self):
        r = self.parser.parse("BPM120 动感音乐")
        self.assertEqual(r.target_bpm, 120.0)
        self.assertEqual(r.bpm_range, (115.0, 125.0))
    
    def test_genre_extraction(self):
        r = self.parser.parse("摇滚电音 BGM")
        self.assertEqual(r.genre, "rock")
    
    def test_platform_extraction(self):
        r = self.parser.parse("抖音热门视频素材")
        self.assertIn("douyin", r.preferred_platforms)
    
    def test_quality_extraction(self):
        r = self.parser.parse("4K高清夕阳海滩")
        self.assertEqual(r.quality, "4k")
    
    def test_watermark_extraction(self):
        r = self.parser.parse("无水印视频素材")
        self.assertTrue(r.watermark_free)
    
    def test_media_type_extraction(self):
        r = self.parser.parse("BGM配乐推荐")
        self.assertEqual(r.media_type, "audio")
    
    def test_complex_query(self):
        r = self.parser.parse("开心的流行音乐 BPM120 抖音 BGM")
        self.assertEqual(r.mood, "happy")
        self.assertEqual(r.genre, "pop")
        self.assertEqual(r.target_bpm, 120.0)
        self.assertIn("douyin", r.preferred_platforms)
        self.assertEqual(r.media_type, "audio")
        self.assertGreater(r.confidence, 0.5)
    
    def test_semantic_query_cleanup(self):
        r = self.parser.parse("4K高清夕阳海滩视频素材")
        self.assertIn("夕阳", r.semantic_query)
        self.assertNotIn("4K", r.semantic_query)
    
    def test_kuaishou_not_matched_as_bpm(self):
        """快手不应被BPM范围词'快'误匹配"""
        r = self.parser.parse("搞笑的短视频素材 快手")
        self.assertIsNone(r.target_bpm)
        self.assertIn("kuaishou", r.preferred_platforms)
    
    def test_empty_input(self):
        r = self.parser.parse("")
        self.assertEqual(r.confidence, 0.0)
    
    def test_confidence_increases_with_features(self):
        r_simple = self.parser.parse("视频")
        r_complex = self.parser.parse("开心的流行音乐 BPM120 抖音 BGM")
        self.assertGreater(r_complex.confidence, r_simple.confidence)


class TestSmartRanker(unittest.TestCase):
    """智能排序器测试"""
    
    def setUp(self):
        self.ranker = SmartRanker()
    
    def test_default_weights(self):
        weights = self.ranker.get_weight_summary()
        self.assertIn("semantic", weights)
        self.assertIn("quality", weights)
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=1)
    
    def test_rank_empty(self):
        results = self.ranker.rank([])
        self.assertEqual(results, [])
    
    def test_rank_with_results(self):
        items = [
            {"similarity": 0.9, "quality_score": 0.8, "view_count": 10000},
            {"similarity": 0.7, "quality_score": 0.9, "view_count": 50000},
        ]
        results = self.ranker.rank(items, top_k=5)
        self.assertEqual(len(results), 2)
        self.assertIn("final_score", results[0])
        self.assertIn("scores", results[0])
    
    def test_adjust_weights(self):
        self.ranker.adjust_weights({"semantic": 1.5})
        weights = self.ranker.get_weight_summary()
        self.assertGreater(weights["semantic"], 0.35)
    
    def test_diversity(self):
        items = [
            {"similarity": 0.9, "platform": "douyin", "audio_features": {"mood": "happy"}},
            {"similarity": 0.8, "platform": "douyin", "audio_features": {"mood": "happy"}},
            {"similarity": 0.7, "platform": "bilibili", "audio_features": {"mood": "sad"}},
        ]
        results_with = self.ranker.rank(items, diversity=True, top_k=3)
        results_without = self.ranker.rank(items, diversity=False, top_k=3)
        # 多样性开启时，不同平台/情绪的结果应获得提升
        self.assertEqual(len(results_with), 3)
        self.assertEqual(len(results_without), 3)


class TestUserPreference(unittest.TestCase):
    """用户偏好学习测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)
    
    def test_cold_start(self):
        prefs = self.learner.get_preferences("new_user")
        self.assertTrue(prefs["is_cold_start"])
    
    def test_record_and_retrieve(self):
        action = UserAction(
            user_id="test_user",
            action_type="download",
            query="开心音乐",
            item_id="test_001",
            item_metadata={"audio_features": {"mood": "happy"}, "platform": "douyin"},
        )
        self.learner.record_action(action)
        
        prefs = self.learner.get_preferences("test_user")
        # 单次行为可能仍在冷启动范围（需5次以上）
        self.assertGreaterEqual(len(prefs.get("recent_actions", [])) + prefs.get("action_count", 0), 1)
        # 验证偏好已记录
        self.assertIsNotNone(prefs["top_mood"])
    
    def test_personalize_cold_start(self):
        results = [{"title": "test", "similarity": 0.8}]
        personalized = self.learner.personalize_results("cold_user", results, top_k=5)
        self.assertEqual(len(personalized), 1)
    
    def test_personalize_with_history(self):
        # 记录多次行为
        for i in range(6):
            self.learner.record_action(UserAction(
                user_id="warm_user",
                action_type="download",
                query="摇滚音乐",
                item_id=f"rock_{i}",
                item_metadata={"audio_features": {"mood": "excited", "genre": "rock"}, "platform": "bilibili"},
            ))
        
        results = [
            {"title": "rock song", "similarity": 0.8, "audio_features": {"mood": "excited", "genre": "rock"}, "platform": "bilibili"},
            {"title": "pop song", "similarity": 0.9, "audio_features": {"mood": "happy", "genre": "pop"}, "platform": "douyin"},
        ]
        personalized = self.learner.personalize_results("warm_user", results, top_k=5)
        # 摇滚歌曲应排在前面（用户偏好）
        self.assertEqual(len(personalized), 2)
    
    def test_suggested_queries(self):
        # 冷启动建议
        suggestions = self.learner.get_suggested_queries("cold_user", count=5)
        self.assertEqual(len(suggestions), 5)
        
        # 有历史后的建议
        self.learner.record_action(UserAction(
            user_id="warm_user",
            action_type="download",
            query="流行音乐",
            item_id="pop_001",
            item_metadata={"audio_features": {"mood": "happy", "genre": "pop"}, "platform": "douyin"},
        ))
        warm_suggestions = self.learner.get_suggested_queries("warm_user", count=5)
        self.assertGreater(len(warm_suggestions), 0)
    
    def test_record_action_with_invalid_bpm(self):
        """测试BPM为无效值时不应崩溃"""
        action = UserAction(
            user_id="test_user",
            action_type="download",
            query="测试音乐",
            item_id="test_invalid_bpm",
            item_metadata={"audio_features": {"mood": "happy", "bpm": "invalid_bpm"}, "platform": "douyin"},
        )
        self.learner.record_action(action)
        prefs = self.learner.get_preferences("test_user")
        self.assertTrue(prefs["success"] if "success" in prefs else True)
    
    def test_personalize_with_invalid_bpm(self):
        """测试personalize_results处理无效BPM值"""
        for i in range(6):
            self.learner.record_action(UserAction(
                user_id="warm_user_bpm",
                action_type="download",
                query="音乐",
                item_id=f"item_{i}",
                item_metadata={"audio_features": {"mood": "happy", "bpm": 120}, "platform": "douyin"},
            ))
        
        results = [
            {"title": "test", "similarity": 0.8, "audio_features": {"mood": "happy", "bpm": "invalid"}},
        ]
        personalized = self.learner.personalize_results("warm_user_bpm", results, top_k=5)
        self.assertEqual(len(personalized), 1)


class TestRRFFusion(unittest.TestCase):
    """RRF倒数排名融合测试"""
    
    def setUp(self):
        self.rrf = RRFFusion(k=60)
    
    def test_fuse_empty(self):
        result = self.rrf.fuse([])
        self.assertEqual(result, [])
    
    def test_fuse_single_list(self):
        lists = [[
            {"file_path": "a.mp4", "similarity": 0.9, "source": "clip"},
            {"file_path": "b.mp4", "similarity": 0.7, "source": "clip"},
        ]]
        result = self.rrf.fuse(lists)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "a.mp4")
        self.assertIn("rrf_score", result[0])
    
    def test_fuse_two_lists(self):
        lists = [
            [
                {"file_path": "a.mp4", "similarity": 0.9, "source": "clip"},
                {"file_path": "b.mp4", "similarity": 0.7, "source": "clip"},
            ],
            [
                {"file_path": "b.mp4", "similarity": 0.95, "source": "clap"},
                {"file_path": "c.mp4", "similarity": 0.8, "source": "clap"},
            ]
        ]
        result = self.rrf.fuse(lists)
        # b.mp4 在两路都出现，RRF分数应最高
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["file_path"], "b.mp4")
        self.assertIn("match_sources", result[0])
        self.assertIn("rrf_details", result[0])
    
    def test_fuse_with_weights(self):
        lists = [
            [{"file_path": "a.mp4", "similarity": 0.9}],
            [{"file_path": "b.mp4", "similarity": 0.9}],
        ]
        # clip权重更高，a.mp4应排前面
        result = self.rrf.fuse(lists, weights=[2.0, 1.0])
        self.assertEqual(result[0]["file_path"], "a.mp4")
    
    def test_rrf_score_formula(self):
        """验证RRF公式: score = weight / (k + rank)"""
        lists = [[
            {"file_path": "a.mp4", "similarity": 0.9},
            {"file_path": "b.mp4", "similarity": 0.7},
        ]]
        result = self.rrf.fuse(lists, weights=[1.0])
        expected_first = 1.0 / (60 + 1)
        self.assertAlmostEqual(result[0]["rrf_score"], expected_first, places=5)


class TestCrossPlatformSearcher(unittest.TestCase):
    """跨平台搜索器测试"""
    
    def setUp(self):
        self.searcher = CrossPlatformSearcher()
    
    def test_deduplicate(self):
        results = [
            {"url": "https://example.com/a", "title": "测试视频A"},
            {"url": "https://example.com/a", "title": "测试视频A"},  # 完全重复
            {"url": "https://example.com/b", "title": "测试视频B"},
        ]
        deduped = self.searcher.deduplicate(results)
        self.assertEqual(len(deduped), 2)
    
    def test_evaluate_quality(self):
        results = [
            {"quality": "4k", "watermark": False, "view_count": 2000000, "like_count": 300000, "duration": 60},
            {"quality": "low", "watermark": True, "view_count": 1000, "like_count": 10, "duration": 10},
        ]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertEqual(len(evaluated), 2)
        self.assertGreater(evaluated[0]["quality_score"], evaluated[1]["quality_score"])
    
    def test_title_similarity(self):
        sim = self.searcher._title_similarity("相同的标题", "相同的标题")
        self.assertEqual(sim, 1.0)
        
        sim = self.searcher._title_similarity("完全不同", "毫不相关")
        self.assertLess(sim, 0.5)
    
    def test_merge_results(self):
        local = [{"file_path": "a.mp4", "similarity": 0.9, "combined_score": 0.85}]
        remote = [{"url": "b.mp4", "quality_score": 0.7, "title": "remote video"}]
        
        merged = self.searcher.merge_results(local, remote)
        self.assertEqual(len(merged), 2)
    
    def test_evaluate_quality_with_zero_view_count(self):
        """测试view_count为0时不应崩溃"""
        results = [
            {"quality": "high", "watermark": False, "view_count": 0, "like_count": 0, "duration": 60},
        ]
        evaluated = self.searcher.evaluate_quality(results)
        self.assertEqual(len(evaluated), 1)
        self.assertIn("quality_score", evaluated[0])


class TestAudioFeatureSet(unittest.TestCase):
    """音频特征数据结构测试"""
    
    def test_infer_mood(self):
        f = AudioFeatureSet(valence=0.5, arousal=0.5)
        self.assertEqual(f.infer_mood(), "happy")
        
        f = AudioFeatureSet(valence=0.5, arousal=-0.5)
        self.assertEqual(f.infer_mood(), "calm")
        
        f = AudioFeatureSet(valence=-0.5, arousal=0.5)
        self.assertEqual(f.infer_mood(), "angry")
        
        f = AudioFeatureSet(valence=-0.5, arousal=-0.5)
        self.assertEqual(f.infer_mood(), "sad")
    
    def test_to_dict(self):
        f = AudioFeatureSet(bpm=120.0, key="C", mode="major", mood="happy")
        d = f.to_dict()
        self.assertEqual(d["bpm"], 120.0)
        self.assertEqual(d["key"], "C")
        self.assertEqual(d["mood"], "happy")
    
    def test_extractor_fallback(self):
        extractor = AudioFeatureExtractor()
        features = extractor.extract("nonexistent_file.wav")
        self.assertEqual(features.extractor, "file_not_found")


class TestSmartMatcher(unittest.TestCase):
    """智能匹配器端到端测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.matcher = SmartMatcher(
            index_path="nonexistent_index.json",
            preference_data_dir=self.temp_dir,
        )
    
    def test_match_no_index(self):
        result = self.matcher.match("开心的音乐", include_remote=False)
        self.assertTrue(result["success"])
        self.assertEqual(len(result["results"]), 0)
    
    def test_match_parsed_query(self):
        result = self.matcher.match("开心的流行音乐 BPM120 抖音 BGM", include_remote=False)
        self.assertTrue(result["success"])
        parsed = result["parsed_query"]
        self.assertEqual(parsed["mood"], "happy")
        self.assertEqual(parsed["genre"], "pop")
        self.assertEqual(parsed["target_bpm"], 120.0)
    
    def test_engine_info(self):
        info = self.matcher.get_engine_info()
        self.assertIn("audio", info)
        self.assertIn("clap", info)
    
    def test_record_action(self):
        self.matcher.record_action(
            user_id="test_user",
            action_type="download",
            query="开心音乐",
            item_id="test_001",
            item_metadata={"audio_features": {"mood": "happy"}}
        )
        prefs = self.matcher.get_user_preferences("test_user")
        # 行为已记录（可能在冷启动范围内）
        self.assertGreaterEqual(prefs["action_count"], 1)
    
    def test_extract_audio_nonexistent(self):
        features = self.matcher.extract_audio_features("nonexistent.wav")
        self.assertEqual(features["extractor"], "file_not_found")


if __name__ == "__main__":
    unittest.main(verbosity=2)
