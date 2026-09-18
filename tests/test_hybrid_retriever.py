"""联合检索器单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 防止 HuggingFace Hub 网络请求导致测试超时
os.environ["HF_HUB_OFFLINE"] = "1"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

from hybrid_retriever import HybridRetriever


class TestFilterByAudioFeatures(unittest.TestCase):
    """音频特征过滤测试"""

    def setUp(self):
        self.retriever = HybridRetriever()

    def test_filter_empty_items(self):
        items = []
        result = self.retriever.filter_by_audio_features(items)
        self.assertEqual(result, [])

    def test_filter_no_audio_features(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {}},
        ]
        result = self.retriever.filter_by_audio_features(items)
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIn("audio_match_score", item)
            self.assertEqual(item["audio_match_score"], 1.0)

    def test_filter_bpm_match(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {"audio_features": {"bpm": 120}}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {"audio_features": {"bpm": 60}}},
        ]
        result = self.retriever.filter_by_audio_features(items, target_bpm=120, bpm_range=(110, 130))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "test1.mp4")
        self.assertIn("BPM在范围内", result[0].get("match_reasons", []))

    def test_filter_mood_match(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {"audio_features": {"mood": "happy"}}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {"audio_features": {"mood": "sad"}}},
        ]
        result = self.retriever.filter_by_audio_features(items, mood="happy")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "test1.mp4")
        self.assertGreater(result[0]["audio_match_score"], result[1]["audio_match_score"])

    def test_filter_genre_match(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {"audio_features": {"genre": "pop"}}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {"audio_features": {"genre": "rock"}}},
        ]
        result = self.retriever.filter_by_audio_features(items, genre="pop")
        self.assertEqual(len(result), 2)
        self.assertGreater(result[0]["audio_match_score"], result[1]["audio_match_score"])

    def test_filter_duration_range(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {"duration": 30}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {"duration": 120}},
        ]
        result = self.retriever.filter_by_audio_features(items, duration_range=(20, 60))
        self.assertEqual(len(result), 2)
        self.assertGreater(result[0]["audio_match_score"], result[1]["audio_match_score"])

    def test_filter_combined(self):
        items = [
            {"file_path": "test1.mp4", "similarity": 0.9, "metadata": {"audio_features": {"bpm": 120, "mood": "happy", "genre": "pop"}, "duration": 30}},
            {"file_path": "test2.mp4", "similarity": 0.8, "metadata": {"audio_features": {"bpm": 60, "mood": "sad", "genre": "rock"}, "duration": 120}},
        ]
        result = self.retriever.filter_by_audio_features(
            items,
            target_bpm=120,
            bpm_range=(110, 130),
            mood="happy",
            genre="pop",
            duration_range=(20, 60)
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file_path"], "test1.mp4")
        self.assertGreater(result[0]["audio_match_score"], result[1]["audio_match_score"])


class TestHybridSearch(unittest.TestCase):
    """联合检索测试（mock模型避免HuggingFace下载）"""

    def setUp(self):
        self.retriever = HybridRetriever()

    def test_hybrid_search_empty_results(self):
        """不存在的索引文件应返回空列表"""
        with patch.object(self.retriever, '_ensure_model'):
            result = self.retriever.hybrid_search("test", "nonexistent.json")
            self.assertEqual(result, [])

    def test_hybrid_search_weights(self):
        """联合搜索应正确融合语义和音频权重"""
        import json

        import numpy as np

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "items": [
                    {"file_path": "/nonexistent/test.mp4", "vector": [0.1] * 512, "metadata": {"audio_features": {"bpm": 120, "mood": "happy", "genre": "pop"}}},
                ]
            }, f)
            temp_path = f.name

        try:
            mock_model = MagicMock()
            with patch.object(self.retriever, '_ensure_model'):
                self.retriever.model = mock_model
                with patch('hybrid_retriever.load_index') as mock_load, \
                     patch('hybrid_retriever.encode_text') as mock_encode, \
                     patch('hybrid_retriever.cosine_similarity') as mock_cosine, \
                     patch('os.path.exists', return_value=True):
                    mock_load.return_value = {
                        "items": [
                            {"file_path": "/nonexistent/test.mp4", "vector": [0.1] * 512, "metadata": {"audio_features": {"bpm": 120, "mood": "happy", "genre": "pop"}}},
                        ]
                    }
                    mock_encode.return_value = np.array([0.1] * 512)
                    mock_cosine.return_value = 0.85

                    result = self.retriever.hybrid_search(
                        "happy pop music",
                        temp_path,
                        top_k=1,
                        target_bpm=120,
                        mood="happy",
                        genre="pop",
                        semantic_weight=0.7,
                        audio_weight=0.3
                    )
                    for item in result:
                        self.assertIn("combined_score", item)
                        self.assertIn("semantic_weight", item)
                        self.assertIn("audio_weight", item)
        finally:
            os.unlink(temp_path)


class TestSemanticSearch(unittest.TestCase):
    """语义搜索测试（mock模型避免HuggingFace下载）"""

    def setUp(self):
        self.retriever = HybridRetriever()

    def test_semantic_search_empty_index(self):
        """不存在的索引文件应返回空列表"""
        with patch.object(self.retriever, '_ensure_model'):
            result = self.retriever.semantic_search("test", "nonexistent.json")
            self.assertEqual(result, [])

    def test_search_by_image_empty_index(self):
        """不存在的索引文件应返回空列表"""
        with patch.object(self.retriever, '_ensure_model'):
            result = self.retriever.search_by_image("/nonexistent/image.jpg", "nonexistent.json")
            self.assertEqual(result, [])

    def test_semantic_search_skips_invalid_vectors(self):
        """空向量或维度不匹配的项应被跳过，不引发 ValueError"""
        import numpy as np
        with patch.object(self.retriever, '_ensure_model'):
            self.retriever.model = MagicMock()
            with patch('hybrid_retriever.load_index') as mock_load, \
                 patch('hybrid_retriever.encode_text') as mock_encode, \
                 patch('hybrid_retriever.cosine_similarity') as mock_cosine, \
                 patch('os.path.exists', return_value=True):
                mock_load.return_value = {
                    "items": [
                        # 空向量
                        {"file_path": "/nonexistent/empty.mp4", "vector": [], "metadata": {}},
                        # 维度不匹配
                        {"file_path": "/nonexistent/wrong_dim.mp4", "vector": [0.1] * 100, "metadata": {}},
                        # 有效向量
                        {"file_path": "/nonexistent/valid.mp4", "vector": [0.1] * 512, "metadata": {}},
                    ]
                }
                mock_encode.return_value = np.array([0.1] * 512)
                mock_cosine.return_value = 0.85

                result = self.retriever.semantic_search("test", "fake.json")
                # 应仅返回有效向量对应的那一项
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["file_path"], "/nonexistent/valid.mp4")

    def test_semantic_search_cosine_exception_skipped(self):
        """cosine_similarity 抛出异常时该项应被跳过"""
        import numpy as np
        with patch.object(self.retriever, '_ensure_model'):
            self.retriever.model = MagicMock()
            with patch('hybrid_retriever.load_index') as mock_load, \
                 patch('hybrid_retriever.encode_text') as mock_encode, \
                 patch('hybrid_retriever.cosine_similarity') as mock_cosine, \
                 patch('os.path.exists', return_value=True):
                mock_load.return_value = {
                    "items": [
                        {"file_path": "/nonexistent/a.mp4", "vector": [0.1] * 512, "metadata": {}},
                        {"file_path": "/nonexistent/b.mp4", "vector": [0.2] * 512, "metadata": {}},
                    ]
                }
                mock_encode.return_value = np.array([0.1] * 512)
                # 第一项抛异常，第二项正常
                mock_cosine.side_effect = [ValueError("dim mismatch"), 0.9]

                result = self.retriever.semantic_search("test", "fake.json")
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["file_path"], "/nonexistent/b.mp4")


if __name__ == "__main__":
    unittest.main(verbosity=2)