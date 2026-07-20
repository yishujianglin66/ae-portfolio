#!/usr/bin/env python3
"""
端到端集成测试 - AudioAnalysisService / SceneDetectionService / V4Agent

测试重点：
1. AudioAnalysisService 完整流程（Whisper 转写 + PyAnnote 说话人分离）
2. SceneDetectionService 完整流程（PySceneDetect + OpenCV 降级 + 关键帧提取）
3. V4Agent 完整流程（职场学习分析 + 对话历史 + 模型路由）

使用精细 Mock 策略：
- pyannote.audio 通过 patch.dict('sys.modules', ...) 精细 mock
- OpenCV 帧数据使用真实 numpy 数组（而非 MagicMock）
- V4Agent 通过 mock requests.post / _session.post 模拟 API 响应
"""

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

# 添加项目根目录和 puppet-automation 到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "puppet-automation"))

from src.services.audio_analysis import AudioAnalysisService
from src.services.scene_detection import SceneDetectionService


# ============================================================
# AudioAnalysisService 集成测试
# ============================================================

class TestAudioAnalysisIntegration(unittest.TestCase):
    """AudioAnalysisService 端到端集成测试"""

    def setUp(self):
        self.service = AudioAnalysisService()
        self.temp_dir = tempfile.mkdtemp()
        # 使用 numpy 数组生成假音频数据（16kHz, 1秒静音）
        audio_data = np.zeros(16000, dtype=np.float32)
        self.valid_audio = Path(self.temp_dir) / "test_audio.wav"
        self.valid_audio.write_bytes(audio_data.tobytes())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_transcribe_full_pipeline(self):
        """转写完整流程：文件读取 → 模型加载 → 结果格式化"""
        async def run_test():
            # Mock whisper 模型加载
            mock_model = MagicMock()
            mock_model.transcribe = MagicMock(return_value={
                "text": "Hello world, this is a test.",
                "segments": [
                    {"id": 0, "start": 0.0, "end": 1.5, "text": "Hello world,", "confidence": 0.95},
                    {"id": 1, "start": 1.5, "end": 3.0, "text": " this is a test.", "confidence": 0.92},
                ],
                "language": "en",
                "language_probability": 0.98,
                "duration": 3.0,
            })

            with patch('src.services.audio_analysis.whisper.load_model', return_value=mock_model):
                result = await self.service.transcribe(self.valid_audio)

            # 验证模型加载
            self.assertIsNotNone(self.service._model)

            # 验证结果格式化
            self.assertEqual(result["language"], "en")
            self.assertEqual(result["language_probability"], 0.98)
            self.assertEqual(result["duration"], 3.0)
            self.assertEqual(result["text"], "Hello world, this is a test.")
            self.assertEqual(result["word_count"], 6)

            # 验证 segments 格式化
            self.assertEqual(len(result["segments"]), 2)
            self.assertEqual(result["segments"][0]["id"], 0)
            self.assertEqual(result["segments"][0]["start"], 0.0)
            self.assertEqual(result["segments"][0]["end"], 1.5)
            self.assertEqual(result["segments"][0]["text"], "Hello world,")
            self.assertEqual(result["segments"][0]["confidence"], 0.95)
            self.assertEqual(result["segments"][1]["text"], "this is a test.")

        asyncio.run(run_test())

    def test_detect_speakers_with_pyannote(self):
        """说话人分离：精细 mock pyannote.audio 模块，验证聚合逻辑"""
        async def run_test():
            # Mock transcribe（detect_speakers 内部会调用 transcribe）
            self.service.transcribe = AsyncMock(return_value={
                "text": "Hello world",
                "language": "en",
                "language_probability": 0.95,
                "duration": 5.0,
                "segments": [],
                "word_count": 2,
            })

            # 创建 mock pyannote Pipeline
            mock_pipeline = MagicMock()
            mock_diarization = MagicMock()

            # 创建说话人片段（模拟 pyannote 的 itertracks 返回）
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
            # pipeline(audio_path) 返回 diarization 对象
            mock_pipeline.return_value = mock_diarization

            # 创建 mock pyannote.audio 模块
            mock_pyannote_module = MagicMock()
            mock_pyannote_module.Pipeline.from_pretrained.return_value = mock_pipeline

            # 使用 patch.dict 精细 mock pyannote.audio
            with patch.dict('sys.modules', {'pyannote.audio': mock_pyannote_module}):
                result = await self.service.detect_speakers(self.valid_audio)

            # 验证说话人聚合
            self.assertEqual(result["num_speakers"], 2)
            self.assertIn("SPEAKER_01", result["speakers"])
            self.assertIn("SPEAKER_02", result["speakers"])
            self.assertEqual(len(result["speaker_segments"]), 2)

            # 验证片段格式
            self.assertEqual(result["speaker_segments"][0]["speaker"], "SPEAKER_01")
            self.assertEqual(result["speaker_segments"][0]["start"], 0.0)
            self.assertEqual(result["speaker_segments"][0]["end"], 2.0)
            self.assertEqual(result["speaker_segments"][1]["speaker"], "SPEAKER_02")
            self.assertEqual(result["speaker_segments"][1]["start"], 2.0)
            self.assertEqual(result["speaker_segments"][1]["end"], 5.0)

            # 验证 transcribe 结果合并
            self.assertEqual(result["text"], "Hello world")
            self.assertEqual(result["language"], "en")

            # 验证 Pipeline.from_pretrained 调用
            mock_pyannote_module.Pipeline.from_pretrained.assert_called_once()

        asyncio.run(run_test())

    def test_detect_speakers_pyannote_import_error(self):
        """pyannote.audio 导入失败时应降级到 transcribe"""
        async def run_test():
            # Mock transcribe
            self.service.transcribe = AsyncMock(return_value={
                "text": "Fallback text",
                "language": "en",
                "language_probability": 0.9,
                "duration": 2.0,
                "segments": [],
                "word_count": 2,
            })

            # 模拟 pyannote.audio 导入失败
            with patch.dict('sys.modules', {'pyannote.audio': None}):
                result = await self.service.detect_speakers(self.valid_audio)

            # 应降级到 transcribe
            self.service.transcribe.assert_called_once_with(self.valid_audio)
            self.assertIn("text", result)
            self.assertEqual(result["text"], "Fallback text")
            # 不应包含说话人信息
            self.assertNotIn("num_speakers", result)

        asyncio.run(run_test())

    def test_analyze_audio_routing(self):
        """analyze_audio 应根据 detect_speakers 参数正确路由"""
        async def run_test():
            # Mock 两个方法
            self.service.detect_speakers = AsyncMock(return_value={
                "text": "with speakers",
                "num_speakers": 1,
                "speakers": ["SPEAKER_01"],
                "speaker_segments": [],
            })
            self.service.transcribe = AsyncMock(return_value={
                "text": "without speakers",
            })

            # detect_speakers=True 应调用 detect_speakers
            result_with = await self.service.analyze_audio(self.valid_audio, detect_speakers=True)
            self.service.detect_speakers.assert_called_once_with(self.valid_audio)
            self.service.transcribe.assert_not_called()
            self.assertEqual(result_with["text"], "with speakers")
            self.assertEqual(result_with["num_speakers"], 1)

            # 重置 mock
            self.service.detect_speakers.reset_mock()
            self.service.transcribe.reset_mock()

            # detect_speakers=False 应调用 transcribe
            result_without = await self.service.analyze_audio(self.valid_audio, detect_speakers=False)
            self.service.transcribe.assert_called_once_with(self.valid_audio)
            self.service.detect_speakers.assert_not_called()
            self.assertEqual(result_without["text"], "without speakers")

        asyncio.run(run_test())


# ============================================================
# SceneDetectionService 集成测试
# ============================================================

class TestSceneDetectionIntegration(unittest.TestCase):
    """SceneDetectionService 端到端集成测试"""

    def setUp(self):
        self.service = SceneDetectionService()
        self.temp_dir = tempfile.mkdtemp()
        # 创建假视频文件
        self.fake_video = Path(self.temp_dir) / "test_video.mp4"
        self.fake_video.write_bytes(b"fake video data for testing")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_scenes_with_scenedetect(self):
        """使用 scenedetect 检测场景：mock 所有必要组件"""
        async def run_test():
            # 强制启用 scenedetect 路径
            with patch.object(self.service, '_scenedetect_available', True):
                # 构造 mock 场景列表
                mock_frame_start_1 = MagicMock()
                mock_frame_start_1.get_frames.return_value = 0
                mock_frame_start_1.get_seconds.return_value = 0.0
                mock_frame_end_1 = MagicMock()
                mock_frame_end_1.get_frames.return_value = 150
                mock_frame_end_1.get_seconds.return_value = 5.0

                mock_frame_start_2 = MagicMock()
                mock_frame_start_2.get_frames.return_value = 150
                mock_frame_start_2.get_seconds.return_value = 5.0
                mock_frame_end_2 = MagicMock()
                mock_frame_end_2.get_frames.return_value = 300
                mock_frame_end_2.get_seconds.return_value = 10.0

                mock_scene_list = [
                    (mock_frame_start_1, mock_frame_end_1),
                    (mock_frame_start_2, mock_frame_end_2),
                ]

                # 创建 mock scenedetect 模块
                mock_scenedetect = MagicMock()
                mock_scene_manager = MagicMock()
                mock_scene_manager.get_scene_list.return_value = mock_scene_list
                mock_scenedetect.SceneManager.return_value = mock_scene_manager
                mock_scenedetect.open_video.return_value = MagicMock()

                mock_scenedetect_detectors = MagicMock()
                mock_scenedetect_detectors.ContentDetector.return_value = MagicMock()

                with patch.dict('sys.modules', {
                    'scenedetect': mock_scenedetect,
                    'scenedetect.detectors': mock_scenedetect_detectors,
                }):
                    result = await self.service.detect_scenes(self.fake_video, threshold=30.0)

            # 验证结果结构
            self.assertEqual(result["total_scenes"], 2)
            self.assertEqual(result["method"], "py_scenedetect")
            self.assertEqual(result["threshold"], 30.0)
            self.assertEqual(len(result["scenes"]), 2)

            # 验证场景格式化
            self.assertEqual(result["scenes"][0]["id"], 1)
            self.assertEqual(result["scenes"][0]["start_frame"], 0)
            self.assertEqual(result["scenes"][0]["end_frame"], 150)
            self.assertEqual(result["scenes"][0]["start_time"], 0.0)
            self.assertEqual(result["scenes"][0]["end_time"], 5.0)
            self.assertEqual(result["scenes"][0]["duration"], 5.0)

            self.assertEqual(result["scenes"][1]["id"], 2)
            self.assertEqual(result["scenes"][1]["start_frame"], 150)
            self.assertEqual(result["scenes"][1]["end_frame"], 300)
            self.assertEqual(result["scenes"][1]["duration"], 5.0)

        asyncio.run(run_test())

    def test_detect_scenes_fallback_to_opencv(self):
        """scenedetect 不可用时降级到 OpenCV：使用真实 numpy 数组作为帧"""
        async def run_test():
            import cv2

            # 创建不同的 numpy 帧以触发场景切换
            frame_black = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame_white = np.ones((720, 1280, 3), dtype=np.uint8) * 255
            frame_gray = np.full((720, 1280, 3), 128, dtype=np.uint8)

            frames = [frame_black, frame_white, frame_gray]

            with patch.object(self.service, '_scenedetect_available', False):
                with patch('cv2.VideoCapture') as mock_cap_class:
                    mock_cap = MagicMock()
                    mock_cap.isOpened.return_value = True

                    def get_prop(prop):
                        if prop == cv2.CAP_PROP_FPS:
                            return 30.0
                        if prop == cv2.CAP_PROP_FRAME_COUNT:
                            return float(len(frames))
                        return 0.0

                    mock_cap.get.side_effect = get_prop
                    mock_cap.read.side_effect = [(True, f) for f in frames]
                    mock_cap_class.return_value = mock_cap

                    result = await self.service.detect_scenes(self.fake_video)

            # 验证使用了 OpenCV 降级路径
            self.assertEqual(result["method"], "opencv_basic")
            self.assertEqual(result["fps"], 30.0)
            self.assertGreaterEqual(result["total_scenes"], 1)

            # 验证场景结构
            for scene in result["scenes"]:
                self.assertIn("id", scene)
                self.assertIn("start_frame", scene)
                self.assertIn("end_frame", scene)
                self.assertIn("start_time", scene)
                self.assertIn("end_time", scene)
                self.assertIn("duration", scene)

        asyncio.run(run_test())

    def test_extract_keyframes_full_pipeline(self):
        """关键帧提取完整流程：mock detect_scenes 和 cv2"""
        async def run_test():
            import cv2

            # Mock detect_scenes 返回预定义场景
            self.service.detect_scenes = AsyncMock(return_value={
                "total_scenes": 2,
                "scenes": [
                    {"id": 1, "start_frame": 0, "end_frame": 100},
                    {"id": 2, "start_frame": 100, "end_frame": 200},
                ],
                "method": "py_scenedetect",
            })

            # 创建真实 numpy 帧用于关键帧提取
            mock_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

            with patch('cv2.VideoCapture') as mock_cap_class:
                mock_cap = MagicMock()
                mock_cap.isOpened.return_value = True
                mock_cap.get.return_value = 30.0  # fps
                mock_cap.set.return_value = True
                mock_cap.read.return_value = (True, mock_frame)
                mock_cap_class.return_value = mock_cap

                with patch('cv2.imwrite', return_value=True) as mock_imwrite:
                    result = await self.service.extract_keyframes(self.fake_video)

            # 验证关键帧提取结果
            self.assertEqual(result["total_keyframes"], 2)
            self.assertEqual(len(result["keyframes"]), 2)

            # 验证关键帧信息
            for kf in result["keyframes"]:
                self.assertIn("scene_id", kf)
                self.assertIn("frame_number", kf)
                self.assertIn("timestamp", kf)
                self.assertIn("path", kf)

            # 验证帧号计算（中点）
            self.assertEqual(result["keyframes"][0]["frame_number"], 50)   # (0+100)//2
            self.assertEqual(result["keyframes"][1]["frame_number"], 150)  # (100+200)//2

            # 验证 cv2.imwrite 被调用
            self.assertEqual(mock_imwrite.call_count, 2)

        asyncio.run(run_test())

    def test_end_to_end_scene_to_keyframe(self):
        """端到端：从场景检测到关键帧提取的完整链路"""
        async def run_test():
            import cv2

            # 使用真实 numpy 帧模拟视频
            frame_1 = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame_2 = np.ones((720, 1280, 3), dtype=np.uint8) * 255

            # 步骤1：使用 OpenCV 降级路径检测场景
            with patch.object(self.service, '_scenedetect_available', False):
                with patch('cv2.VideoCapture') as mock_cap_class:
                    mock_cap = MagicMock()
                    mock_cap.isOpened.return_value = True

                    def get_prop(prop):
                        if prop == cv2.CAP_PROP_FPS:
                            return 30.0
                        if prop == cv2.CAP_PROP_FRAME_COUNT:
                            return 2.0
                        return 0.0

                    mock_cap.get.side_effect = get_prop
                    mock_cap.read.side_effect = [(True, frame_1), (True, frame_2)]
                    mock_cap_class.return_value = mock_cap

                    scenes_result = await self.service.detect_scenes(self.fake_video)

            # 验证场景检测成功
            self.assertGreaterEqual(scenes_result["total_scenes"], 1)
            self.assertEqual(scenes_result["method"], "opencv_basic")

            # 步骤2：基于检测到的场景提取关键帧
            # Mock detect_scenes 返回步骤1的结果，避免重复检测
            self.service.detect_scenes = AsyncMock(return_value=scenes_result)

            keyframe_frame = np.zeros((720, 1280, 3), dtype=np.uint8)

            with patch('cv2.VideoCapture') as mock_cap_class:
                mock_cap = MagicMock()
                mock_cap.isOpened.return_value = True
                mock_cap.get.return_value = 30.0
                mock_cap.set.return_value = True
                mock_cap.read.return_value = (True, keyframe_frame)
                mock_cap_class.return_value = mock_cap

                with patch('cv2.imwrite', return_value=True):
                    keyframes_result = await self.service.extract_keyframes(self.fake_video)

            # 验证端到端链路完整性
            self.assertEqual(keyframes_result["total_keyframes"], len(scenes_result["scenes"]))
            self.assertEqual(keyframes_result["scenes"]["total_scenes"], scenes_result["total_scenes"])

            # 验证每个场景都有对应的关键帧
            scene_ids = {s["id"] for s in scenes_result["scenes"]}
            keyframe_scene_ids = {kf["scene_id"] for kf in keyframes_result["keyframes"]}
            self.assertEqual(scene_ids, keyframe_scene_ids)

        asyncio.run(run_test())


# ============================================================
# V4Agent 集成测试
# ============================================================

class TestV4AgentIntegration(unittest.TestCase):
    """V4Agent 端到端集成测试"""

    def setUp(self):
        os.environ["DEEPSEEK_API_KEY"] = "test-key-for-integration"
        from ai_agent import V4Agent
        self.agent = V4Agent()

    def tearDown(self):
        self.agent.clear_history()

    def test_career_analysis_full_flow(self):
        """职场学习分析完整流程：Mock ARK API 响应"""
        # 强制启用 ARK 路径
        with patch('ai_agent.ARK_AVAILABLE', True), \
             patch('ai_agent.ARK_API_KEY', 'ark-test-key'):
            with patch('ai_agent.requests.post') as mock_post:
                # Mock ARK API 响应
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{
                        "message": {
                            "content": "## 心理历程分析\n\n情绪积极，展现出强烈的学习意愿。"
                        }
                    }],
                    "usage": {
                        "prompt_tokens": 200,
                        "completion_tokens": 100,
                        "total_tokens": 300,
                    },
                }
                mock_post.return_value = mock_response

                result = self.agent.career_analysis(
                    "今天学习了锂电池维护流程，遇到了一些困难但最终解决了。"
                )

            # 验证 ARK API 被调用
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertIn("ark.cn-beijing.volces.com", call_args[0][0])

            # 验证请求载荷
            payload = call_args[1]["json"]
            self.assertIn("messages", payload)
            # 应使用职场学习系统提示词
            system_msg = payload["messages"][0]
            self.assertIn("职场学习", system_msg["content"])

            # 验证返回结果
            self.assertIn("心理历程", result)

    def test_ask_with_history(self):
        """多次对话后历史记录应正确累积"""
        with patch.object(self.agent, '_session') as mock_session:
            # 第一次对话
            mock_response_1 = MagicMock()
            mock_response_1.json.return_value = {
                "choices": [{"message": {"content": "第一个回答"}}],
                "usage": {"total_tokens": 100, "prompt_tokens": 50, "completion_tokens": 50},
            }
            mock_session.post.return_value = mock_response_1

            self.agent.ask("第一个问题")
            self.assertEqual(len(self.agent.history), 2)  # 1 user + 1 assistant
            self.assertEqual(self.agent.history[0]["role"], "user")
            self.assertEqual(self.agent.history[0]["content"], "第一个问题")
            self.assertEqual(self.agent.history[1]["role"], "assistant")
            self.assertEqual(self.agent.history[1]["content"], "第一个回答")

            # 第二次对话
            mock_response_2 = MagicMock()
            mock_response_2.json.return_value = {
                "choices": [{"message": {"content": "第二个回答"}}],
                "usage": {"total_tokens": 120, "prompt_tokens": 70, "completion_tokens": 50},
            }
            mock_session.post.return_value = mock_response_2

            self.agent.ask("第二个问题")
            self.assertEqual(len(self.agent.history), 4)  # 2 user + 2 assistant
            self.assertEqual(self.agent.history[2]["role"], "user")
            self.assertEqual(self.agent.history[2]["content"], "第二个问题")
            self.assertEqual(self.agent.history[3]["role"], "assistant")
            self.assertEqual(self.agent.history[3]["content"], "第二个回答")

            # 验证第二次请求包含历史记录
            second_call_payload = mock_session.post.call_args[1]["json"]
            messages = second_call_payload["messages"]
            # system + 2 history + 1 new = 4 messages
            self.assertEqual(len(messages), 4)
            self.assertEqual(messages[0]["role"], "system")
            self.assertEqual(messages[1]["content"], "第一个问题")
            self.assertEqual(messages[3]["content"], "第二个问题")

            # 验证 token 累积
            self.assertEqual(self.agent.total_tokens, 220)

    def test_model_routing_for_different_questions(self):
        """不同类型问题应路由到不同模型"""
        with patch.object(self.agent, 'ask') as mock_ask:
            mock_ask.return_value = "mocked response"

            # Pro 级问题（包含"分析"和"架构"）
            self.agent.qa("请分析项目架构设计")
            pro_call = mock_ask.call_args
            self.assertEqual(pro_call[1]["model"], "pro")

            # Flash 级问题（包含"翻译"和"总结"）
            self.agent.qa("请翻译并总结这段内容")
            flash_call = mock_ask.call_args
            self.assertEqual(flash_call[1]["model"], "flash")

            # 显式 use_flash
            self.agent.qa("简单问题", use_flash=True)
            explicit_flash_call = mock_ask.call_args
            self.assertEqual(explicit_flash_call[1]["model"], "flash")

            # 验证不同问题调用了不同模型
            models_used = [c[1]["model"] for c in mock_ask.call_args_list]
            self.assertIn("pro", models_used)
            self.assertIn("flash", models_used)


if __name__ == "__main__":
    unittest.main(verbosity=2)
