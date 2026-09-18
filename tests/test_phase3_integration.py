import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ae_agent_pipeline import AEAgentPipeline, PlanningResult


@pytest.fixture
def pipeline():
    return AEAgentPipeline()


class TestPhase3ModuleLoading:
    def test_pipeline_phase3_modules_loaded(self, pipeline):
        assert pipeline.scene_orchestrator is not None, "SceneOrchestrator未加载"
        assert pipeline.beat_orchestrator is not None, "BeatOrchestrator未加载"
        assert pipeline.effect_composer is not None, "EffectComposer未加载"
        assert pipeline.feedback_manager is not None, "FeedbackLoopManager未加载"


class TestEffectComposerIntegration:
    def test_compose_style_effects(self, pipeline):
        result = pipeline.compose_style_effects(
            style_name="cinematic",
            layer_name="test_layer",
            intensity=1.0
        )
        assert result is not None
        assert "effects" in result
        assert len(result["effects"]) > 0
        assert "style_name" in result
        assert result["style_name"] == "cinematic"
        for effect in result["effects"]:
            assert "effectName" in effect
            assert "settings" in effect

    def test_recommend_styles(self, pipeline):
        keywords = ["cinematic", "film", "movie"]
        recommendations = pipeline.recommend_styles(keywords, limit=5)
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5
        if recommendations:
            for rec in recommendations:
                assert "name" in rec
                assert "display_name" in rec
                assert "match_score" in rec


class TestBeatOrchestratorIntegration:
    def test_orchestrate_beat_show(self, pipeline):
        result = pipeline.orchestrate_beat_show(
            layer_name="beat_layer",
            bpm=120.0,
            duration=5.0,
            style="energetic",
            structure_template="short_hook"
        )
        assert result is not None
        assert "layerName" in result
        assert result["layerName"] == "beat_layer"
        assert "keyframes" in result
        assert len(result["keyframes"]) > 0
        assert "sections" in result
        assert len(result["sections"]) > 0
        assert "style" in result
        assert result["style"] == "energetic"


class TestSceneOrchestratorIntegration:
    def test_orchestrate_multi_scene(self, pipeline):
        scenes = [
            {"name": "intro", "duration": 2.0},
            {"name": "main", "duration": 3.0},
            {"name": "outro", "duration": 1.5},
        ]
        result = pipeline.orchestrate_scenes(
            scenes=scenes,
            transition_type="crossfade",
            transition_duration=0.5
        )
        assert result is not None
        assert result["scene_count"] == 3
        assert "total_duration" in result
        assert result["total_duration"] > 0
        assert "timeline" in result
        assert len(result["timeline"]) > 0
        assert "transitions" in result
        assert len(result["transitions"]) == 2

    def test_apply_camera_move(self, pipeline):
        keyframes = pipeline.apply_camera_move(
            layer_name="camera_layer",
            move_type="push",
            duration=2.0,
            start_scale=100.0,
            end_scale=120.0
        )
        assert isinstance(keyframes, list)
        assert len(keyframes) >= 2
        for kf in keyframes:
            assert "layerName" in kf
            assert "propertyName" in kf
            assert "time" in kf
            assert "value" in kf


class TestFeedbackLoopIntegration:
    def test_run_with_feedback_success(self, pipeline):
        def success_fn():
            return {
                "success": True,
                "result": {"settings": {"Blurriness": 10.0}},
            }

        expected = {"settings": {"Blurriness": 10.0}}

        result = pipeline.run_with_feedback(
            user_input="add blur effect",
            intent_type="effect_application",
            execute_fn=success_fn,
            expected=expected,
            base_confidence=0.7,
        )
        assert result is not None
        assert result["success"] is True
        assert "record" in result
        assert result["record"] is not None
        assert result["record"].success is True
        assert "verification" in result
        assert result["verification"] is not None
        assert result["suggestion"] is None


class TestFullOrchestration:
    def test_orchestrate_full(self, pipeline):
        perception = {
            "audio": {
                "bpm": 120,
                "duration": 5.0,
            }
        }
        understanding = {
            "style": "cinematic",
            "keywords": ["movie", "film"],
        }
        result = pipeline.orchestrate_full(
            perception=perception,
            understanding=understanding,
            layer_name="main_layer",
        )
        assert result is not None
        assert "style" in result
        assert result["style"] == "cinematic"
        assert "bpm" in result
        assert result["bpm"] == 120
        assert "duration" in result
        assert result["duration"] == 5.0
        assert "effects" in result
        assert len(result["effects"]) > 0
        assert "keyframes" in result
        assert len(result["keyframes"]) > 0
        assert "effect_count" in result
        assert result["effect_count"] > 0
        assert "keyframe_count" in result
        assert result["keyframe_count"] > 0
