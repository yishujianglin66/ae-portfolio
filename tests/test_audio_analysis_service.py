#!/usr/bin/env python3
"""
AudioAnalysisService 单元测试 - Whisper + PyAnnote 服务

测试重点：
1. 文件验证和异常处理
2. 异步方法正确性
3. PyAnnote不可用时的降级路径
4. 边界条件处理
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import sys
import os

# 添加项目根目录和puppet-automation到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "puppet-automation"))

# 导入测试目标
from src.services.audio_analysis import AudioAnalysisService


class TestAudioAnalysisServiceInit(unittest.TestCase):
    """初始化和配置测试"""

    def test_default_model_name(self):
        """默认模型名应为 base"""
        service = AudioAnalysisService()
        self.assertEqual(service.model_name, "base")

    def test_custom_model_name(self):
        """应接受自定义模型名"""
        service = AudioAnalysisService(model_name="large")
        self.assertEqual(service.model_name, "large")

    def test_model_lazy_loading(self):
        """模型应延迟加载"""
        service = AudioAnalysisService()
        self.assertIsNone(service._model)


class TestAudioAnalysisServiceTranscribe(unittest.TestCase):
    """transcribe 方法测试"""

    def setUp(self):
        """每个测试前的设置"""
        self.service = AudioAnalysisService()
        # 创建临时测试文件
        self.temp_dir = tempfile.mkdtemp()
        self.valid_audio = Path(self.temp_dir) / "test.wav"
        self.valid_audio.write_bytes(b"fake audio data")

    def tearDown(self):
        """清理临时文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transcribe_file_not_found(self):
        """不存在的文件应抛出 FileNotFoundError"""
        async def run_test():
            with self.assertRaises(FileNotFoundError):
                await self.service.transcribe("/nonexistent/audio.mp3")
        
        asyncio.run(run_test())

    def test_transcribe_path_object(self):
        """应接受 Path 对象"""
        async def run_test():
            # Mock model
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "test",
                "segments": [],
                "language": "en",
                "duration": 1.0
            })
            
            # 验证 Path 对象被正确处理
            with self.assertRaises(FileNotFoundError):
                await self.service.transcribe(Path("/nonexistent/audio.mp3"))
        
        asyncio.run(run_test())

    def test_transcribe_empty_result(self):
        """空转写结果应正确处理"""
        async def run_test():
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "",
                "segments": [],
                "language": "en",
                "language_probability": 0.95,
                "duration": 0.0
            })
            
            result = await self.service.transcribe(self.valid_audio)
            
            self.assertEqual(result["text"], "")
            self.assertEqual(result["word_count"], 0)
            self.assertEqual(result["segments"], [])
        
        asyncio.run(run_test())

    def test_transcribe_segments_formatting(self):
        """segments 应正确格式化"""
        async def run_test():
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "Hello world",
                "segments": [
                    {"id": 0, "start": 0.0, "end": 1.0, "text": "Hello", "confidence": 0.9},
                    {"id": 1, "start": 1.0, "end": 2.0, "text": " world", "confidence": 0.85},
                ],
                "language": "en",
                "language_probability": 0.95,
                "duration": 2.0
            })
            
            result = await self.service.transcribe(self.valid_audio)
            
            self.assertEqual(len(result["segments"]), 2)
            # 验证格式化（小数精度）
            self.assertEqual(result["segments"][0]["start"], 0.0)
            self.assertEqual(result["segments"][1]["end"], 2.0)
            # 验证文本 strip
            self.assertEqual(result["segments"][0]["text"], "Hello")
        
        asyncio.run(run_test())


class TestAudioAnalysisServiceDetectSpeakers(unittest.TestCase):
    """detect_speakers 方法测试"""

    def setUp(self):
        self.service = AudioAnalysisService()
        self.temp_dir = tempfile.mkdtemp()
        self.valid_audio = Path(self.temp_dir) / "test.wav"
        self.valid_audio.write_bytes(b"fake audio data")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_speakers_file_not_found(self):
        """不存在的文件应抛出 FileNotFoundError"""
        async def run_test():
            with self.assertRaises(FileNotFoundError):
                await self.service.detect_speakers("/nonexistent/audio.mp3")
        
        asyncio.run(run_test())

    def test_pyannote_fallback_to_transcribe(self):
        """PyAnnote 不可用时应降级到 transcribe"""
        async def run_test():
            # Mock transcribe
            self.service.transcribe = AsyncMock(return_value={
                "text": "test",
                "language": "en",
                "duration": 1.0
            })

            # Mock PyAnnote import failure by setting sys.modules entry to None,
            # which makes `from pyannote.audio import Pipeline` raise ImportError.
            # (Pipeline is imported inside the function, not at module level.)
            with patch.dict('sys.modules', {'pyannote.audio': None}):
                result = await self.service.detect_speakers(self.valid_audio)

                # 应调用 transcribe
                self.service.transcribe.assert_called_once()
                self.assertIn("text", result)

        asyncio.run(run_test())

    def test_speaker_segments_aggregation(self):
        """说话人片段应正确聚合"""
        async def run_test():
            import numpy as np
            # Mock transcribe
            self.service.transcribe = AsyncMock(return_value={
                "text": "Hello world",
                "language": "en",
                "duration": 5.0,
                "segments": []
            })

            # 创建 mock pyannote 模块
            mock_pipeline = MagicMock()
            mock_diarization = MagicMock()
            mock_segment_1 = MagicMock()
            mock_segment_1.start = 0.0
            mock_segment_1.end = 2.0
            mock_segment_2 = MagicMock()
            mock_segment_2.start = 2.0
            mock_segment_2.end = 5.0
            mock_diarization.itertracks.return_value = [
                (mock_segment_1, None, "SPEAKER_01"),
                (mock_segment_2, None, "SPEAKER_02"),
            ]
            mock_pipeline.return_value = mock_diarization

            mock_pyannote_module = MagicMock()
            mock_pyannote_module.Pipeline.from_pretrained.return_value = mock_pipeline

            with patch.dict('sys.modules', {'pyannote.audio': mock_pyannote_module}):
                result = await self.service.detect_speakers(self.valid_audio)

                self.assertEqual(result["num_speakers"], 2)
                self.assertIn("SPEAKER_01", result["speakers"])
                self.assertIn("SPEAKER_02", result["speakers"])
                self.assertEqual(len(result["speaker_segments"]), 2)

        asyncio.run(run_test())


class TestAudioAnalysisServiceAnalyzeAudio(unittest.TestCase):
    """analyze_audio 方法测试"""

    def setUp(self):
        self.service = AudioAnalysisService()
        self.temp_dir = tempfile.mkdtemp()
        self.valid_audio = Path(self.temp_dir) / "test.wav"
        self.valid_audio.write_bytes(b"fake audio data")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_with_speaker_detection(self):
        """应调用 detect_speakers"""
        async def run_test():
            self.service.detect_speakers = AsyncMock(return_value={"text": "test"})
            
            result = await self.service.analyze_audio(self.valid_audio, detect_speakers=True)
            
            self.service.detect_speakers.assert_called_once()
        
        asyncio.run(run_test())

    def test_analyze_without_speaker_detection(self):
        """应调用 transcribe"""
        async def run_test():
            self.service.transcribe = AsyncMock(return_value={"text": "test"})
            
            result = await self.service.analyze_audio(self.valid_audio, detect_speakers=False)
            
            self.service.transcribe.assert_called_once()
        
        asyncio.run(run_test())


class TestAudioAnalysisServiceEdgeCases(unittest.TestCase):
    """边界条件测试"""

    def setUp(self):
        self.service = AudioAnalysisService()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_file(self):
        """空文件应正确处理"""
        async def run_test():
            empty_file = Path(self.temp_dir) / "empty.wav"
            empty_file.touch()
            
            # Mock model to handle empty file
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "",
                "segments": [],
                "language": "en",
                "duration": 0.0
            })
            
            result = await self.service.transcribe(empty_file)
            self.assertEqual(result["word_count"], 0)
        
        asyncio.run(run_test())

    def test_special_characters_in_path(self):
        """特殊字符路径应正确处理"""
        async def run_test():
            special_file = Path(self.temp_dir) / "音频 测试 [2024].wav"
            special_file.write_bytes(b"fake audio data")
            
            # 验证路径处理
            self.assertTrue(special_file.exists())
            
            # Mock model
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "test",
                "segments": [],
                "language": "zh",
                "duration": 1.0
            })
            
            result = await self.service.transcribe(special_file)
            self.assertIn("language", result)
        
        asyncio.run(run_test())

    def test_confidence_missing_in_segment(self):
        """segment 缺少 confidence 时应正确处理"""
        async def run_test():
            audio_file = Path(self.temp_dir) / "test.wav"
            audio_file.write_bytes(b"fake audio")
            
            self.service._model = MagicMock()
            self.service._model.transcribe = MagicMock(return_value={
                "text": "test",
                "segments": [
                    {"id": 0, "start": 0.0, "end": 1.0, "text": "test"}
                    # 缺少 confidence 字段
                ],
                "language": "en",
                "duration": 1.0
            })
            
            result = await self.service.transcribe(audio_file)
            
            # confidence 应为 None
            self.assertIsNone(result["segments"][0]["confidence"])
        
        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main(verbosity=2)