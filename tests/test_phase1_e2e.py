import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import (
    AEAgentPipeline,
    PerceptionResult,
    UnderstandingResult,
    PlanningResult,
    ExecutionResult
)


class TestPhase1EndToEnd:
    """Phase 1 端到端集成测试"""

    def test_full_pipeline_flow_with_mock_audio(self):
        """测试完整流水线：感知(模拟音频) → 理解 → 规划 → 执行(模拟AE)"""
        pipeline = AEAgentPipeline()
        
        # 模拟音频分析结果
        mock_audio_result = {
            "success": True,
            "features": {
                "bpm": 128,
                "duration": 10,
                "mood": "excited",
                "beats": [0.47, 0.94, 1.41, 1.88, 2.35, 2.82, 3.29, 3.76],
                "downbeats": [0.0, 0.94, 1.88, 2.82, 3.76],
                "energy_curve": {
                    "rms": [0.3, 0.5, 0.7, 0.6, 0.8],
                    "peaks": [1.41, 3.29]
                },
                "segments": [
                    {"start": 0, "end": 5, "label": "intro"},
                    {"start": 5, "end": 10, "label": "verse"}
                ]
            }
        }
        
        # 模拟视频分析结果
        mock_video_result = {
            "success": True,
            "features": {
                "duration": 5.0,
                "fps": 30,
                "scene_count": 3,
                "avg_motion": 25.5,
                "dominant_color": [100, 150, 200],
                "brightness": 0.6
            }
        }
        
        # 模拟MCP客户端
        mock_client = Mock()
        mock_client.send_command.return_value = {"success": True, "status": "success"}
        mock_client.clear_result = Mock()
        
        # 保存原始的os.path.exists
        original_path_exists = os.path.exists
        
        # Patch os.path.exists 让假路径通过检查
        def mock_path_exists(path):
            if "fake" in path:
                return True
            return original_path_exists(path)
        
        # Patch 音频分析器
        with patch.object(pipeline.audio_analyzer, 'analyze_audio', return_value=mock_audio_result):
            # Patch 视频分析器
            with patch.object(pipeline.video_analyzer, 'analyze_video', return_value=mock_video_result):
                # Patch MCP客户端
                with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
                    with patch('os.path.exists', side_effect=mock_path_exists):
                        # 运行完整流水线
                        result = pipeline.run_pipeline(
                            music_path="/fake/path/music.mp3",
                            clip_paths=["/fake/path/clip1.mp4", "/fake/path/clip2.mp4"],
                            user_prompt="Create an exciting cinematic video",
                            style_preset="cinematic"
                        )
        
        # 验证结果结构
        assert "perception" in result
        assert "understanding" in result
        assert "planning" in result
        assert "execution" in result
        assert "overall_success" in result
        
        # 验证各层都有输出
        assert result["perception"] is not None
        assert result["understanding"] is not None
        assert result["planning"] is not None
        assert result["execution"] is not None
        
        # 验证规划结果包含必要字段
        planning = result["planning"]
        assert hasattr(planning, 'composition')
        assert hasattr(planning, 'layers')
        assert hasattr(planning, 'effects')
        assert hasattr(planning, 'keyframes')
        
        # 验证执行结果
        execution = result["execution"]
        assert hasattr(execution, 'success')
        assert execution.success is True

    def test_perception_to_understanding_flow(self):
        """测试感知层到理解层的数据流"""
        pipeline = AEAgentPipeline()
        
        perception = PerceptionResult(
            music_features={
                "bpm": 100,
                "duration": 8,
                "mood": "calm",
                "beats": [0.6, 1.2, 1.8, 2.4, 3.0],
                "downbeats": [0.0, 1.2, 2.4],
                "energy_curve": {"peaks": []},
                "segments": []
            },
            clip_features=[
                {"video_path": "/path/clip1.mp4", "basic_info": {"duration": 4.0}, "motion_features": {"avg_motion": 15}},
                {"video_path": "/path/clip2.mp4", "basic_info": {"duration": 4.0}, "motion_features": {"avg_motion": 20}}
            ]
        )
        
        understanding = pipeline.understand(perception)
        
        assert isinstance(understanding, UnderstandingResult)
        assert understanding.mood is not None
        assert understanding.tempo > 0
        assert understanding.duration > 0
        assert len(understanding.keywords) >= 0

    def test_understanding_to_planning_flow(self):
        """测试理解层到规划层的数据流"""
        pipeline = AEAgentPipeline()
        
        understanding = UnderstandingResult(
            intent="video_editing",
            mood="energetic",
            mood_score=0.8,
            style="dynamic",
            tempo=140,
            duration=10,
            keywords=["energetic", "fast", "dynamic"]
        )
        
        perception = PerceptionResult(
            music_features={
                "bpm": 140,
                "duration": 10,
                "mood": "energetic",
                "beats": [0.43, 0.86, 1.29, 1.72, 2.15, 2.58, 3.01, 3.44],
                "downbeats": [0.0, 0.86, 1.72, 2.58, 3.44],
                "energy_curve": {"peaks": [1.29, 3.01]},
                "segments": [
                    {"start": 0, "end": 5, "label": "build_up"},
                    {"start": 5, "end": 10, "label": "drop"}
                ]
            },
            clip_features=[
                {"video_path": "/path/clip1.mp4", "basic_info": {"duration": 3.0}, "motion_features": {"avg_motion": 30}},
                {"video_path": "/path/clip2.mp4", "basic_info": {"duration": 3.0}, "motion_features": {"avg_motion": 40}},
                {"video_path": "/path/clip3.mp4", "basic_info": {"duration": 4.0}, "motion_features": {"avg_motion": 35}}
            ]
        )
        
        planning = pipeline.plan(understanding, perception)
        
        assert isinstance(planning, PlanningResult)
        assert planning.composition is not None
        assert len(planning.layers) >= 3
        assert len(planning.effects) > 0
        assert len(planning.keyframes) > 0
        assert len(planning.execution_order) > 0

    def test_planning_to_execution_flow(self):
        """测试规划层到执行层的数据流"""
        pipeline = AEAgentPipeline()
        
        planning = PlanningResult()
        planning.composition = {
            "name": "E2E_Test_Comp",
            "width": 1920,
            "height": 1080,
            "duration": 5,
            "frameRate": 30
        }
        planning.layers = [
            {"name": "Clip1", "type": "footage", "source": "/path/clip1.mp4", "startTime": 0, "duration": 2.5},
            {"name": "Clip2", "type": "footage", "source": "/path/clip2.mp4", "startTime": 2.5, "duration": 2.5},
            {"name": "Audio1", "type": "audio", "source": "/path/music.mp3", "startTime": 0, "duration": 5}
        ]
        planning.effects = [
            {"layerName": "Clip1", "effectName": "ADBE Glo2", "settings": {"Glow Radius": 30}},
            {"layerName": "Clip2", "effectName": "ADBE Glo2", "settings": {"Glow Radius": 50}}
        ]
        planning.keyframes = [
            {"layerName": "Clip1", "propertyName": "Opacity", "time": 0, "value": 0, "easeType": "easeInOut"},
            {"layerName": "Clip1", "propertyName": "Opacity", "time": 0.5, "value": 100, "easeType": "easeInOut"},
            {"layerName": "Clip2", "propertyName": "Opacity", "time": 2.5, "value": 0, "easeType": "easeInOut"},
            {"layerName": "Clip2", "propertyName": "Opacity", "time": 3.0, "value": 100, "easeType": "easeInOut"}
        ]
        planning.transitions = []
        planning.execution_order = [
            "createComposition", "importFootage", "placeFootageInComp",
            "applyEffects", "setKeyframes", "renderVideo"
        ]
        
        mock_client = Mock()
        mock_client.send_command.return_value = {"success": True, "status": "success"}
        mock_client.clear_result = Mock()
        
        with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
            execution = pipeline.execute(planning)
        
        assert isinstance(execution, ExecutionResult)
        assert execution.success is True
        assert execution.steps_completed > 0
        assert execution.total_steps > 0
        
        # 验证send_command被调用了合理次数
        # 1 create + 3 import + 3 place + 2 effects + 4 keyframes + 1 render = 14次
        assert mock_client.send_command.call_count >= 10

    def test_pipeline_error_handling_propagation(self):
        """测试错误在各层之间的正确传递"""
        pipeline = AEAgentPipeline()
        
        planning = PlanningResult()
        planning.composition = {"name": "ErrorTest", "width": 1920, "height": 1080, "duration": 5, "frameRate": 30}
        planning.layers = []
        planning.effects = []
        planning.keyframes = []
        planning.transitions = []
        planning.execution_order = ["createComposition"]
        
        # 模拟AE执行失败
        mock_client = Mock()
        mock_client.send_command.return_value = {"success": False, "status": "error", "message": "Simulated AE error"}
        mock_client.clear_result = Mock()
        
        with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
            execution = pipeline.execute(planning)
        
        assert execution.success is False
        assert execution.error_message is not None
        assert "Simulated AE error" in execution.error_message
        assert execution.steps_completed >= 1

    def test_command_generator_integration_with_pipeline(self):
        """测试命令生成器与pipeline的集成"""
        from ae_command_generator import AECommandGenerator
        
        gen = AECommandGenerator()
        
        # 模拟规划结果结构
        planning_data = {
            "composition": {
                "name": "IntegrationTest",
                "width": 1280,
                "height": 720,
                "duration": 8,
                "frameRate": 24
            },
            "layers": [
                {"name": "Video1", "type": "footage", "source": "/test/v1.mp4", "startTime": 0, "duration": 4},
                {"name": "Video2", "type": "footage", "source": "/test/v2.mp4", "startTime": 4, "duration": 4},
                {"name": "BGM", "type": "audio", "source": "/test/bgm.mp3", "startTime": 0, "duration": 8}
            ],
            "effects": [
                {"layerName": "Video1", "effectName": "ADBE Glo2", "settings": {"Radius": 20, "Intensity": 1.5}}
            ],
            "keyframes": [
                {"layerName": "Video1", "propertyName": "Position", "time": 0, "value": [640, 360], "easeType": "linear"},
                {"layerName": "Video1", "propertyName": "Position", "time": 4, "value": [640, 400], "easeType": "easeInOut"}
            ],
            "transitions": []
        }
        
        commands = gen.generate_from_planning_result(planning_data)
        
        # 验证命令数量
        assert len(commands) >= 9  # 1 create + 3 import + 3 place + 1 effect + 2 keyframes
        
        # 验证命令顺序
        op_types = [cmd["op"] for cmd in commands]
        assert op_types[0] == "createComposition"
        assert "importFootage" in op_types
        assert "placeFootageInComp" in op_types
        assert "applyEffect" in op_types
        assert "setLayerKeyframe" in op_types
        
        # 验证每个命令都有必要字段
        for cmd in commands:
            assert "op" in cmd
            assert "params" in cmd
            assert isinstance(cmd["params"], dict)
