"""音频特征提取器单元测试"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索"))

# 只导入数据类，不导入提取器类避免加载模型
try:
    from audio_feature_extractor import AudioFeatureSet
except ImportError:
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "audio_feature_extractor",
        Path(__file__).resolve().parent.parent / "13-素材获取与搜索" / "03-AI语义搜索" / "audio_feature_extractor.py"
    )
    audio_module = importlib.util.module_from_spec(spec)
    # 不执行模块，只获取数据类
    spec.loader.exec_module(audio_module)
    AudioFeatureSet = audio_module.AudioFeatureSet


class TestAudioFeatureSet(unittest.TestCase):
    """音频特征集测试"""

    def test_default_init(self):
        features = AudioFeatureSet()
        self.assertEqual(features.file_path, "")
        self.assertEqual(features.duration, 0.0)
        self.assertEqual(features.bpm, 0.0)
        self.assertEqual(features.mood, "")

    def test_custom_init(self):
        features = AudioFeatureSet(
            file_path="/test/audio.mp3",
            duration=120.5,
            bpm=120.0,
            mood="happy",
            valence=0.5,
            arousal=0.8
        )
        self.assertEqual(features.file_path, "/test/audio.mp3")
        self.assertEqual(features.duration, 120.5)
        self.assertEqual(features.bpm, 120.0)
        self.assertEqual(features.mood, "happy")
        self.assertEqual(features.valence, 0.5)
        self.assertEqual(features.arousal, 0.8)

    def test_infer_mood_happy(self):
        features = AudioFeatureSet(valence=0.5, arousal=0.5)
        self.assertEqual(features.infer_mood(), "happy")

    def test_infer_mood_calm(self):
        features = AudioFeatureSet(valence=0.5, arousal=-0.5)
        self.assertEqual(features.infer_mood(), "calm")

    def test_infer_mood_angry(self):
        features = AudioFeatureSet(valence=-0.5, arousal=0.5)
        self.assertEqual(features.infer_mood(), "angry")

    def test_infer_mood_sad(self):
        features = AudioFeatureSet(valence=-0.5, arousal=-0.5)
        self.assertEqual(features.infer_mood(), "sad")

    def test_infer_mood_boundary_zero(self):
        features = AudioFeatureSet(valence=0.0, arousal=0.0)
        self.assertEqual(features.infer_mood(), "sad")

    def test_to_dict_default(self):
        features = AudioFeatureSet()
        result = features.to_dict()
        self.assertIn("file_path", result)
        self.assertIn("duration", result)
        self.assertIn("bpm", result)
        self.assertIn("mood", result)
        self.assertIn("valence", result)
        self.assertIn("arousal", result)

    def test_to_dict_custom(self):
        features = AudioFeatureSet(
            file_path="/test/audio.mp3",
            duration=120.5,
            bpm=120.0,
            mood="happy",
            valence=0.5,
            arousal=0.8,
            key="C",
            mode="major",
            loudness=-12.5
        )
        result = features.to_dict()
        self.assertEqual(result["file_path"], "/test/audio.mp3")
        self.assertEqual(result["duration"], 120.5)
        self.assertEqual(result["bpm"], 120.0)
        self.assertEqual(result["mood"], "happy")
        self.assertEqual(result["valence"], 0.5)
        self.assertEqual(result["arousal"], 0.8)
        self.assertEqual(result["key"], "C")
        self.assertEqual(result["mode"], "major")
        self.assertEqual(result["loudness"], -12.5)

    def test_to_dict_rounding(self):
        features = AudioFeatureSet(
            duration=120.54321,
            bpm=120.12345,
            valence=0.123456,
            arousal=-0.987654,
            spectral_flatness=0.123456789
        )
        result = features.to_dict()
        self.assertEqual(result["duration"], 120.54)
        self.assertEqual(result["bpm"], 120.1)
        self.assertEqual(result["valence"], 0.123)
        self.assertEqual(result["arousal"], -0.988)
        self.assertEqual(result["spectral_flatness"], 0.1235)

    def test_to_dict_mfccs_truncation(self):
        features = AudioFeatureSet(mfccs=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        result = features.to_dict()
        self.assertEqual(len(result["mfccs"]), 13)

    def test_to_dict_chroma_truncation(self):
        features = AudioFeatureSet(chroma=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0])
        result = features.to_dict()
        self.assertEqual(len(result["chroma"]), 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)