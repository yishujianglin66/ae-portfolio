#!/usr/bin/env python3
"""
AudioAnalyzer 单元测试 - 覆盖纯函数分析逻辑
测试目标: _detect_key, _infer_mood, _infer_genre, _calculate_similarity, _calculate_mode_score
"""

import unittest
import sys
import os
import json
import importlib.util
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
sys.path.insert(0, PROJECT_ROOT)

# 文件名含连字符, 需用 importlib 加载
_audio_analyzer_spec = importlib.util.spec_from_file_location(
    "audio_analyzer", os.path.join(PROJECT_ROOT, "audio-analyzer.py")
)
audio_analyzer = importlib.util.module_from_spec(_audio_analyzer_spec)
sys.modules["audio_analyzer"] = audio_analyzer
_audio_analyzer_spec.loader.exec_module(audio_analyzer)
AudioAnalyzer = audio_analyzer.AudioAnalyzer

_ffmpeg_toolkit_spec = importlib.util.spec_from_file_location(
    "ffmpeg_toolkit", os.path.join(PROJECT_ROOT, "ffmpeg-toolkit.py")
)
ffmpeg_toolkit = importlib.util.module_from_spec(_ffmpeg_toolkit_spec)
sys.modules["ffmpeg_toolkit"] = ffmpeg_toolkit
_ffmpeg_toolkit_spec.loader.exec_module(ffmpeg_toolkit)
FFmpegToolkit = ffmpeg_toolkit.FFmpegToolkit

# 使用 mock 替代真实配置，避免依赖 D:\AE-Work 路径
MOCK_CONFIG = {
    "audio": {
        "default_sample_rate": 44100,
        "default_bitrate": "192k"
    },
    "download": {
        "audio_only_formats": ["m4a", "mp3", "wav"]
    }
}


class TestAudioAnalyzerPureFunctions(unittest.TestCase):
    """测试 AudioAnalyzer 中不依赖 librosa 的纯函数"""

    @classmethod
    def setUpClass(cls):
        """创建使用 mock 配置的 analyzer 实例"""
        # 写入临时配置
        cls.temp_config = Path(__file__).parent / "temp_test_config.json"
        with open(cls.temp_config, "w", encoding="utf-8") as f:
            json.dump(MOCK_CONFIG, f)
        cls.analyzer = AudioAnalyzer(config_path=cls.temp_config)

    @classmethod
    def tearDownClass(cls):
        """清理临时配置"""
        if cls.temp_config.exists():
            os.remove(cls.temp_config)

    # ============================================================
    # _detect_key 测试
    # ============================================================
    def test_detect_key_c_major(self):
        """C 大调检测: C 音最高"""
        chroma = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        key, mode = self.analyzer._detect_key(chroma)
        self.assertEqual(key, "C")

    def test_detect_key_a_minor(self):
        """A 音最高时应返回 A"""
        chroma = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]
        key, mode = self.analyzer._detect_key(chroma)
        self.assertEqual(key, "A")

    def test_detect_key_all_zero(self):
        """全零 chroma 返回 Unknown"""
        chroma = [0.0] * 12
        key, mode = self.analyzer._detect_key(chroma)
        self.assertEqual(key, "Unknown")
        self.assertEqual(mode, "unknown")

    def test_detect_key_f_sharp(self):
        """F# 音最高"""
        chroma = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        key, mode = self.analyzer._detect_key(chroma)
        self.assertEqual(key, "F#")

    def test_detect_key_f_natural(self):
        """F 音最高"""
        chroma = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        key, mode = self.analyzer._detect_key(chroma)
        self.assertEqual(key, "F")

    # ============================================================
    # _calculate_mode_score 测试
    # ============================================================
    def test_mode_score_major_higher(self):
        """大调和弦音高时应返回正数"""
        # C E G 强 → 大调
        chroma = [1.0, 0.0, 0.0, 0.0, 0.8, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0]
        score = self.analyzer._calculate_mode_score(chroma)
        self.assertGreater(score, 0)

    def test_mode_score_minor_lower(self):
        """小调和弦音高时应返回负数"""
        # C Eb G 强 → 小调
        chroma = [1.0, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0]
        score = self.analyzer._calculate_mode_score(chroma)
        self.assertLess(score, 0)

    # ============================================================
    # _infer_mood 测试
    # ============================================================
    def test_infer_mood_excited(self):
        """高 tempo + 高 energy → excited"""
        mood, score = self.analyzer._infer_mood(tempo=160, energy=0.4, spectral_centroid=3000)
        self.assertEqual(mood, "excited")
        self.assertGreater(score, 0)

    def test_infer_mood_calm(self):
        """低 tempo + 低 energy → calm"""
        mood, score = self.analyzer._infer_mood(tempo=60, energy=0.05, spectral_centroid=500)
        self.assertEqual(mood, "calm")
        self.assertGreater(score, 0)

    def test_infer_mood_epic(self):
        """中 tempo + 很高 energy → epic"""
        mood, score = self.analyzer._infer_mood(tempo=110, energy=0.45, spectral_centroid=2500)
        self.assertEqual(mood, "epic")

    def test_infer_mood_returns_valid_score(self):
        """所有 mood score 应在 0-1 范围"""
        for tempo in [60, 80, 100, 120, 140, 160]:
            for energy in [0.05, 0.1, 0.2, 0.3, 0.4]:
                for centroid in [500, 1000, 1500, 2000, 3000]:
                    mood, score = self.analyzer._infer_mood(tempo, energy, centroid)
                    self.assertGreaterEqual(score, 0)
                    self.assertLessEqual(score, 1.0)

    # ============================================================
    # _infer_genre 测试
    # ============================================================
    def test_infer_genre_rock(self):
        """tempo > 140 + energy > 0.25 → rock"""
        genre = self.analyzer._infer_genre(tempo=150, energy=0.3, key="C")
        self.assertEqual(genre, "rock")

    def test_infer_genre_pop(self):
        """tempo > 120 + energy > 0.2 → pop"""
        genre = self.analyzer._infer_genre(tempo=130, energy=0.25, key="C")
        self.assertEqual(genre, "pop")

    def test_infer_genre_ambient(self):
        """tempo < 80 + energy < 0.15 → ambient"""
        genre = self.analyzer._infer_genre(tempo=70, energy=0.1, key="C")
        self.assertEqual(genre, "ambient")

    def test_infer_genre_classical(self):
        """tempo < 90 + energy < 0.2 → classical"""
        genre = self.analyzer._infer_genre(tempo=85, energy=0.1, key="C")
        self.assertEqual(genre, "classical")

    def test_infer_genre_epic(self):
        """tempo > 90 + energy > 0.3 → epic"""
        genre = self.analyzer._infer_genre(tempo=100, energy=0.35, key="C")
        self.assertEqual(genre, "epic")

    def test_infer_genre_returns_string(self):
        """所有输入应返回有效字符串"""
        for tempo in [50, 100, 150]:
            for energy in [0.05, 0.2, 0.4]:
                genre = self.analyzer._infer_genre(tempo, energy, "C")
                self.assertIsInstance(genre, str)
                self.assertTrue(len(genre) > 0)

    # ============================================================
    # _calculate_similarity 测试
    # ============================================================
    def test_similarity_identical(self):
        """相同特征应获得高分"""
        features = {"tempo": 120, "mood": "happy", "duration": 30, "energy": 0.2, "key": "C"}
        score = self.analyzer._calculate_similarity(features, features)
        self.assertGreater(score, 0.8)

    def test_similarity_no_match(self):
        """完全不匹配应获得低分"""
        target = {"tempo": 180, "mood": "excited", "duration": 60, "energy": 0.5, "key": "C#"}
        candidate = {"tempo": 60, "mood": "calm", "duration": 5, "energy": 0.02, "key": "G"}
        score = self.analyzer._calculate_similarity(target, candidate)
        self.assertLess(score, 0.5)

    def test_similarity_partial_match(self):
        """部分匹配的分数介于极端值之间"""
        target = {"tempo": 120, "mood": "happy", "duration": 30, "energy": 0.2, "key": "C"}
        candidate = {"tempo": 120, "mood": "happy", "duration": 30, "energy": 0.4, "key": "G"}
        score = self.analyzer._calculate_similarity(target, candidate)
        self.assertGreater(score, 0.4)

    def test_similarity_empty_features(self):
        """空特征应返回 0"""
        score = self.analyzer._calculate_similarity({}, {})
        self.assertEqual(score, 0.0)

    def test_similarity_tempo_only(self):
        """仅 tempo 匹配时分数 <= 0.3"""
        target = {"tempo": 120}
        candidate = {"tempo": 120}
        score = self.analyzer._calculate_similarity(target, candidate)
        self.assertAlmostEqual(score, 0.3, places=2)

    # ============================================================
    # _detect_sections 测试
    # ============================================================
    def test_detect_sections_too_few_beats(self):
        """少于4个节拍返回空列表"""
        sections = self.analyzer._detect_sections([0.5, 1.0, 2.0], 5.0)
        self.assertEqual(sections, [])

    def test_detect_sections_basic(self):
        """正常节拍应返回分段"""
        beat_times = [i * 0.5 for i in range(16)]  # 8秒, 16拍
        sections = self.analyzer._detect_sections(beat_times, 8.0)
        self.assertGreater(len(sections), 0)
        # 每段应有 start_time, end_time, beat_count
        for section in sections:
            self.assertIn("start_time", section)
            self.assertIn("end_time", section)
            self.assertIn("beat_count", section)
            self.assertIn("section_number", section)
            self.assertIn("suggested_action", section)

    def test_get_section_action_cycle(self):
        """section action 应循环7种类型"""
        actions = set()
        for i in range(14):
            action = self.analyzer._get_section_action(i + 1)
            actions.add(action)
        self.assertGreaterEqual(len(actions), 7)


class TestAudioAnalyzerEdgeCases(unittest.TestCase):
    """边界条件测试"""

    @classmethod
    def setUpClass(cls):
        cls.temp_config = Path(__file__).parent / "temp_test_config2.json"
        with open(cls.temp_config, "w", encoding="utf-8") as f:
            json.dump(MOCK_CONFIG, f)
        cls.analyzer = AudioAnalyzer(config_path=cls.temp_config)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_config.exists():
            os.remove(cls.temp_config)

    def test_analyze_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.analyzer.analyze_audio("/nonexistent/file.mp3")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_find_best_bgm_nonexistent_dir(self):
        """不存在的目录返回空列表"""
        result = self.analyzer.find_best_bgm_match({}, "/nonexistent/dir")
        self.assertEqual(result, [])

    def test_similarity_score_bounded(self):
        """相似度分数始终在 0-1 范围"""
        for t1 in [60, 120, 180]:
            for t2 in [60, 120, 180]:
                score = self.analyzer._calculate_similarity(
                    {"tempo": t1, "mood": "calm", "duration": 30, "energy": 0.2, "key": "C"},
                    {"tempo": t2, "mood": "excited", "duration": 60, "energy": 0.5, "key": "G"}
                )
                self.assertGreaterEqual(score, 0)
                self.assertLessEqual(score, 1.0)

    def test_detect_key_12_chroma_values(self):
        """所有12个调名都能被正确识别"""
        expected_keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        for i, expected in enumerate(expected_keys):
            chroma = [0.0] * 12
            chroma[i] = 1.0
            key, mode = self.analyzer._detect_key(chroma)
            self.assertEqual(key, expected, f"chroma[{i}]=1.0 应检测为 {expected}")


class TestFFmpegToolkitPureFunctions(unittest.TestCase):
    """测试 FFmpegToolkit 中的纯函数"""

    @classmethod
    def setUpClass(cls):
        cls.temp_config = Path(__file__).parent / "temp_test_config3.json"
        with open(cls.temp_config, "w", encoding="utf-8") as f:
            json.dump({
                "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
                "audio": {"default_bitrate": "192k"}
            }, f)
        cls.toolkit = FFmpegToolkit(config_path=cls.temp_config)

    @classmethod
    def tearDownClass(cls):
        if cls.temp_config.exists():
            os.remove(cls.temp_config)

    def test_get_audio_codec_mp3(self):
        self.assertEqual(self.toolkit._get_audio_codec("mp3"), "libmp3lame")

    def test_get_audio_codec_wav(self):
        self.assertEqual(self.toolkit._get_audio_codec("wav"), "pcm_s16le")

    def test_get_audio_codec_m4a(self):
        self.assertEqual(self.toolkit._get_audio_codec("m4a"), "aac")

    def test_get_audio_codec_flac(self):
        self.assertEqual(self.toolkit._get_audio_codec("flac"), "flac")

    def test_get_audio_codec_ogg(self):
        self.assertEqual(self.toolkit._get_audio_codec("ogg"), "libvorbis")

    def test_get_audio_codec_unknown(self):
        """未知格式默认返回 libmp3lame"""
        self.assertEqual(self.toolkit._get_audio_codec("xyz"), "libmp3lame")

    def test_extract_audio_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.toolkit.extract_audio("/nonexistent/video.mp4")
        self.assertFalse(result["success"])

    def test_get_media_info_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.toolkit.get_media_info("/nonexistent/video.mp4")
        self.assertFalse(result["success"])

    def test_extract_video_segment_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.toolkit.extract_video_segment("/nonexistent/video.mp4", 0, 10)
        self.assertFalse(result["success"])

    def test_extract_audio_segment_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.toolkit.extract_audio_segment("/nonexistent/audio.mp3", 0, 10)
        self.assertFalse(result["success"])

    def test_convert_video_format_nonexistent_file(self):
        """不存在的文件返回错误"""
        result = self.toolkit.convert_video_format("/nonexistent/video.mp4", "/tmp/out.mp4")
        self.assertFalse(result["success"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
