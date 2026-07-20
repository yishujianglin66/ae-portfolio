"""用户偏好学习模块单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from user_preference import UserPreferenceLearner, UserAction


class TestUserPreferenceBasic(unittest.TestCase):
    """用户偏好基础测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_action_empty(self):
        action = UserAction(user_id="test_user", action_type="search")
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["user_id"], "test_user")
        self.assertTrue(preferences["is_cold_start"])

    def test_record_action_search(self):
        action = UserAction(
            user_id="test_user",
            action_type="search",
            query="happy pop music",
            item_metadata={"audio_features": {"mood": "happy", "genre": "pop"}}
        )
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(len(preferences["preferences"]), 2)

    def test_record_action_download(self):
        action = UserAction(
            user_id="test_user",
            action_type="download",
            item_id="test_video",
            item_metadata={
                "audio_features": {"mood": "excited", "genre": "electronic", "bpm": 128},
                "platform": "douyin",
                "quality": "high"
            }
        )
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertIn("mood_excited", preferences["preferences"])
        self.assertIn("genre_electronic", preferences["preferences"])


class TestPreferenceLearning(unittest.TestCase):
    """偏好学习测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_learn_mood_preference(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"mood": "happy"}}
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["top_mood"], "happy")

    def test_learn_genre_preference(self):
        for i in range(3):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"genre": "pop"}}
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["top_genre"], "pop")

    def test_learn_platform_preference(self):
        for i in range(4):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"platform": "bilibili"}
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["top_platform"], "bilibili")

    def test_learn_bpm_preference(self):
        for i in range(3):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"bpm": 125}}
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["top_bpm_range"], "120-130")

    def test_preference_normalization(self):
        action1 = UserAction(
            user_id="test_user",
            action_type="download",
            item_metadata={"audio_features": {"mood": "happy"}}
        )
        action2 = UserAction(
            user_id="test_user",
            action_type="download",
            item_metadata={"audio_features": {"mood": "sad"}}
        )
        self.learner.record_action(action1)
        self.learner.record_action(action2)
        
        preferences = self.learner.get_preferences("test_user")
        mood_happy = preferences["preferences"].get("mood_happy", 0)
        mood_sad = preferences["preferences"].get("mood_sad", 0)
        self.assertAlmostEqual(mood_happy + mood_sad, 1.0, places=2)


class TestColdStartHandling(unittest.TestCase):
    """冷启动处理测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cold_start_true(self):
        for i in range(4):
            action = UserAction(
                user_id="test_user",
                action_type="search",
                query="music"
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertTrue(preferences["is_cold_start"])

    def test_cold_start_false(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"mood": "happy"}}
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertFalse(preferences["is_cold_start"])

    def test_personalize_results_cold_start(self):
        for i in range(3):
            action = UserAction(
                user_id="test_user",
                action_type="search",
                query="music"
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.9},
            {"similarity": 0.8},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(len(personalized), 2)


class TestPersonalizedRecommendation(unittest.TestCase):
    """个性化推荐测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_personalize_results_mood_match(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"mood": "happy"}}
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.8, "audio_features": {"mood": "happy"}},
            {"similarity": 0.9, "audio_features": {"mood": "sad"}},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(len(personalized), 2)
        self.assertEqual(personalized[0]["audio_features"]["mood"], "happy")

    def test_personalize_results_genre_match(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"genre": "pop"}}
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.8, "audio_features": {"genre": "pop"}},
            {"similarity": 0.9, "audio_features": {"genre": "rock"}},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(personalized[0]["audio_features"]["genre"], "pop")

    def test_personalize_results_platform_match(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"platform": "douyin"}
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.8, "platform": "douyin"},
            {"similarity": 0.9, "platform": "bilibili"},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(personalized[0]["platform"], "douyin")

    def test_personalize_results_bpm_match(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"bpm": 125}}
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.8, "audio_features": {"bpm": 128}},
            {"similarity": 0.9, "audio_features": {"bpm": 85}},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(personalized[0]["audio_features"]["bpm"], 128)

    def test_personalize_results_quality_match(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"quality": "high"}
            )
            self.learner.record_action(action)
        
        results = [
            {"similarity": 0.8, "quality": "high"},
            {"similarity": 0.9, "quality": "medium"},
        ]
        
        personalized = self.learner.personalize_results("test_user", results)
        self.assertEqual(personalized[0]["quality"], "high")


class TestSuggestedQueries(unittest.TestCase):
    """建议搜索词测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_suggested_queries_cold_start(self):
        suggestions = self.learner.get_suggested_queries("new_user")
        self.assertEqual(len(suggestions), 5)
        self.assertIn("欢快的背景音乐", suggestions)

    def test_get_suggested_queries_with_preferences(self):
        for i in range(5):
            action = UserAction(
                user_id="test_user",
                action_type="download",
                item_metadata={"audio_features": {"mood": "happy", "genre": "pop"}, "platform": "douyin"}
            )
            self.learner.record_action(action)
        
        suggestions = self.learner.get_suggested_queries("test_user")
        self.assertGreater(len(suggestions), 0)

    def test_get_suggested_queries_count(self):
        suggestions = self.learner.get_suggested_queries("test_user", count=3)
        self.assertEqual(len(suggestions), 3)


class TestActionWeights(unittest.TestCase):
    """行为权重测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_action_weights_download(self):
        action = UserAction(
            user_id="test_user",
            action_type="download",
            item_metadata={"audio_features": {"mood": "happy"}}
        )
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["preferences"].get("mood_happy"), 1.0)

    def test_action_weights_like(self):
        action = UserAction(
            user_id="test_user",
            action_type="like",
            item_metadata={"audio_features": {"mood": "happy"}}
        )
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["preferences"].get("mood_happy"), 1.0)

    def test_action_weights_skip(self):
        action = UserAction(
            user_id="test_user",
            action_type="skip",
            item_metadata={"audio_features": {"mood": "sad"}}
        )
        self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["preferences"].get("mood_sad"), 1.0)


class TestRecentActionsLimit(unittest.TestCase):
    """最近行为限制测试"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.learner = UserPreferenceLearner(data_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recent_actions_limit(self):
        for i in range(110):
            action = UserAction(
                user_id="test_user",
                action_type="search",
                query=f"query_{i}"
            )
            self.learner.record_action(action)
        
        preferences = self.learner.get_preferences("test_user")
        self.assertEqual(preferences["action_count"], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)