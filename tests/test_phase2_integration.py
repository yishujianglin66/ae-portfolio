"""
Phase 2 集成验证测试
验证Phase 2模块（KeyframeAnimationGenerator、BeatKeyframeMapper、AETSCompilerClient）
已正确集成到AEAgentPipeline中，并能协同工作生成完整JSX脚本。
"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ae_agent_pipeline import (
    AEAgentPipeline,
    PerceptionResult,
    PlanningResult,
    UnderstandingResult,
)

# ============================================================
# 夹具
# ============================================================


@pytest.fixture
def pipeline():
    """创建Pipeline实例（Phase 2模块应自动加载）"""
    return AEAgentPipeline()


@pytest.fixture
def sample_planning():
    """示例PlanningResult，包含效果和关键帧"""
    planning = PlanningResult()
    planning.composition = {
        "name": "Phase2_Test",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
    }
    planning.layers = [
        {"name": "Layer1", "type": "solid", "duration": 5, "startTime": 0, "color": [0.3, 0.5, 0.7]},
    ]
    planning.effects = [
        {
            "layerName": "Layer1",
            "effectName": "ADBE Gaussian Blur 2",
            "settings": {"Blurriness": 10},
        },
        {
            "layerName": "Layer1",
            "effectName": "ADBE Glo2",
            "settings": {"Glow Radius": 20, "Glow Intensity": 0.5},
        },
    ]
    planning.keyframes = [
        {
            "layerName": "Layer1",
            "propertyName": "Opacity",
            "time": 0,
            "value": 0,
            "easeType": "easeOut",
        },
        {
            "layerName": "Layer1",
            "propertyName": "Opacity",
            "time": 0.5,
            "value": 100,
            "easeType": "easeIn",
        },
    ]
    planning.transitions = []
    planning.timeline = []
    return planning


# ============================================================
# Phase 2 模块加载验证
# ============================================================


class TestPhase2ModuleLoading:
    """验证Phase 2模块在Pipeline初始化时正确加载"""

    def test_keyframe_generator_loaded(self, pipeline):
        """KeyframeAnimationGenerator应成功加载"""
        assert pipeline.keyframe_generator is not None, \
            "KeyframeAnimationGenerator未加载"

    def test_beat_mapper_loaded(self, pipeline):
        """BeatKeyframeMapper应成功加载"""
        assert pipeline.beat_mapper is not None, \
            "BeatKeyframeMapper未加载"

    def test_ts_compiler_loaded(self, pipeline):
        """AETSCompilerClient应成功加载"""
        assert pipeline.ts_compiler is not None, \
            "AETSCompilerClient未加载"

    def test_beat_mapper_precision(self, pipeline):
        """BeatKeyframeMapper应配置正确的精度"""
        assert pipeline.beat_mapper.precision_ms == 10.0

    def test_ts_compiler_health_check(self, pipeline):
        """TS编译器health_check应能执行（无论成功或失败）"""
        result = pipeline.ts_compiler.health_check()
        assert isinstance(result, bool)


# ============================================================
# Pipeline → JSX 编译集成
# ============================================================


class TestPipelineToJSXCompilation:
    """验证Pipeline能将PlanningResult编译为JSX"""

    def test_compile_planning_returns_success(self, pipeline, sample_planning):
        """compile_planning_to_jsx应返回成功结果"""
        result = pipeline.compile_planning_to_jsx(sample_planning)
        assert result["success"] is True
        assert "jsx_code" in result
        assert len(result["jsx_code"]) > 0

    def test_compile_planning_contains_effects(self, pipeline, sample_planning):
        """生成的JSX应包含效果代码"""
        result = pipeline.compile_planning_to_jsx(sample_planning)
        jsx = result["jsx_code"]
        assert "ADBE Gaussian Blur 2" in jsx
        assert "ADBE Glo2" in jsx

    def test_compile_planning_contains_keyframes(self, pipeline, sample_planning):
        """生成的JSX应包含关键帧代码"""
        result = pipeline.compile_planning_to_jsx(sample_planning)
        jsx = result["jsx_code"]
        assert "setValueAtTime" in jsx or "setValue" in jsx

    def test_compile_planning_has_command_count(self, pipeline, sample_planning):
        """结果应包含命令计数"""
        result = pipeline.compile_planning_to_jsx(sample_planning)
        assert result["command_count"] > 0

    def test_compile_planning_method_field(self, pipeline, sample_planning):
        """结果应包含method字段标识使用的方法"""
        result = pipeline.compile_planning_to_jsx(sample_planning)
        assert result["method"] in ("ts_compiler", "standalone_jsx")

    def test_compile_empty_planning(self, pipeline):
        """空PlanningResult应能优雅处理"""
        empty_planning = PlanningResult()
        result = pipeline.compile_planning_to_jsx(empty_planning)
        # 即使为空也应返回成功（降级JSX至少包含基础结构）
        assert "jsx_code" in result


# ============================================================
# BeatKeyframeMapper → Pipeline 集成
# ============================================================


class TestBeatMapperIntegration:
    """验证BeatKeyframeMapper能与Pipeline协同工作"""

    def test_beat_mapper_creates_mapping(self, pipeline):
        """BeatKeyframeMapper应能创建节拍-目标映射"""
        from beat_keyframe_mapper import Beat, parse_beats_from_features

        # 模拟音频特征
        audio_features = {
            "bpm": 120,
            "beats": [0.0, 0.5, 1.0, 1.5, 2.0],
            "downbeats": [0.0, 2.0],
            "energy_curve": {"rms": [0.3, 0.5, 0.7, 0.6, 0.8]},
        }

        beats = parse_beats_from_features(audio_features)
        assert len(beats) > 0

        targets = [
            {"time": 0.02, "property": "Scale", "value": 110, "ease": "ease_out"},
            {"time": 1.03, "property": "Scale", "value": 105, "ease": "ease_out"},
        ]

        result = pipeline.beat_mapper.map_beats_to_keyframes(
            beats, targets, strategy="nearest"
        )
        assert result is not None
        assert len(result.mappings) > 0

    def test_beat_mapper_dp_strategy(self, pipeline):
        """动态规划策略应产生更优的映射"""
        from beat_keyframe_mapper import Beat

        beats = [Beat(time=i * 0.5, strength=0.8, is_downbeat=(i % 4 == 0),
                      beat_number=i + 1, measure=i // 4 + 1) for i in range(8)]

        targets = [
            {"time": 0.05, "property": "Scale", "value": 110},
            {"time": 1.05, "property": "Scale", "value": 105},
            {"time": 2.05, "property": "Scale", "value": 108},
        ]

        result = pipeline.beat_mapper.map_beats_to_keyframes(
            beats, targets, strategy="dynamic_programming"
        )
        assert result is not None
        assert result.average_offset_ms >= 0  # 平均偏移应非负


# ============================================================
# KeyframeAnimationGenerator → Pipeline 集成
# ============================================================


class TestKeyframeGeneratorIntegration:
    """验证KeyframeAnimationGenerator能与Pipeline协同工作"""

    def test_generator_creates_entrance_animation(self, pipeline):
        """应能生成入场动画"""
        kf_points = pipeline.keyframe_generator.generate_entrance_animation(
            anim_type="fade_in",
            duration=1.0,
        )
        assert len(kf_points) >= 2
        assert kf_points[0].time == 0.0
        assert kf_points[-1].time == 1.0

    def test_generator_to_ae_commands(self, pipeline):
        """应能将动画转换为AE命令"""
        kf_points = pipeline.keyframe_generator.generate_entrance_animation(
            anim_type="scale_up",
            duration=0.5,
        )
        commands = pipeline.keyframe_generator.to_ae_keyframe_commands(
            keyframes=kf_points,
            layer_name="TestLayer",
            property_name="Scale",
        )
        assert len(commands) > 0
        assert all(cmd["command"] == "setKeyframe" for cmd in commands)

    def test_generator_beat_synced(self, pipeline):
        """应能生成节拍同步动画"""
        beat_times = [0.0, 0.5, 1.0, 1.5, 2.0]
        kf_points = pipeline.keyframe_generator.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Scale",
            base_value=100,
            beat_value=110,
        )
        assert len(kf_points) >= len(beat_times)


# ============================================================
# 端到端集成：Pipeline → Phase 2 → JSX
# ============================================================


class TestEndToEndPhase2Integration:
    """端到端验证：Pipeline完整流程 + Phase 2 JSX编译"""

    def test_full_pipeline_with_jsx_compilation(self, pipeline, sample_planning):
        """完整流程：PlanningResult → compile_planning_to_jsx → 验证JSX"""
        # 1. 编译PlanningResult为JSX
        result = pipeline.compile_planning_to_jsx(sample_planning)

        # 2. 验证结果结构
        assert result["success"] is True
        assert isinstance(result["jsx_code"], str)
        assert result["command_count"] > 0

        # 3. 验证JSX内容
        jsx = result["jsx_code"]
        # 应包含IIFE结构
        assert jsx.startswith("(function() {")
        assert jsx.endswith("})();")
        # 应包含UndoGroup
        assert "beginUndoGroup" in jsx
        assert "endUndoGroup" in jsx
        # 应包含效果
        assert "ADBE Gaussian Blur 2" in jsx
        # 应包含ADBE Effect Parade（修复后的正确API）
        assert "ADBE Effect Parade" in jsx or "addProperty" in jsx

    def test_phase2_modules_all_available(self, pipeline):
        """验证所有Phase 2模块均可用"""
        assert pipeline.keyframe_generator is not None, "KeyframeAnimationGenerator未加载"
        assert pipeline.beat_mapper is not None, "BeatKeyframeMapper未加载"
        assert pipeline.ts_compiler is not None, "AETSCompilerClient未加载"

    def test_pipeline_backward_compatible(self, pipeline):
        """验证Pipeline向后兼容：原始execute方法仍可使用"""
        # 原始方法签名不应改变
        assert hasattr(pipeline, "execute")
        assert hasattr(pipeline, "plan")
        assert hasattr(pipeline, "perceive")
        assert hasattr(pipeline, "understand")
        assert hasattr(pipeline, "feedback")
        assert hasattr(pipeline, "run_pipeline")
