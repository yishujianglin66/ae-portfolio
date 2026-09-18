import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def pipeline():
    from ae_agent_pipeline import AEAgentPipeline
    return AEAgentPipeline()


class TestPuppetStyleEngine:
    def test_engine_import(self):
        from puppet_style_engine import PuppetStyleEngine
        engine = PuppetStyleEngine()
        assert engine is not None

    def test_available_styles(self):
        from puppet_style_engine import PuppetStyleEngine
        engine = PuppetStyleEngine()
        styles = engine.get_available_styles()
        assert isinstance(styles, list)
        assert len(styles) >= 8
        style_names = [s["name"] for s in styles]
        assert "wooden_puppet" in style_names
        assert "ceramic_puppet" in style_names
        assert "cloth_puppet" in style_names
        assert "clay_puppet" in style_names
        assert "metal_puppet" in style_names
        assert "stop_motion_basic" in style_names
        assert "marionette" in style_names
        assert "shadow_puppet" in style_names

    def test_wooden_puppet_style(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine
        engine = PuppetStyleEngine()
        config = PuppetStyleConfig(
            style_type="wooden_puppet",
            intensity=1.0,
            comp_width=1920,
            comp_height=1080,
        )
        result = engine.generate_style(config, "test_layer", 5.0)
        assert result is not None
        assert len(result.effects) > 0
        assert isinstance(result.keyframes, list)
        assert isinstance(result.layers, list)

    def test_style_intensity_scaling(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine
        engine = PuppetStyleEngine()
        config_low = PuppetStyleConfig(style_type="wooden_puppet", intensity=0.5)
        config_high = PuppetStyleConfig(style_type="wooden_puppet", intensity=2.0)
        result_low = engine.generate_style(config_low, "layer", 5.0)
        result_high = engine.generate_style(config_high, "layer", 5.0)
        assert len(result_low.effects) == len(result_high.effects)

    def test_marionette_with_strings(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine
        engine = PuppetStyleEngine()
        config = PuppetStyleConfig(style_type="marionette", intensity=1.0)
        result = engine.generate_style(config, "marionette_layer", 3.0)
        assert result is not None
        assert len(result.effects) > 0


class TestMaterialEffects:
    def test_wooden_puppet_effects(self):
        from puppet_effects.material_effects import MaterialEffects
        effects = MaterialEffects.wooden_puppet(1.0, "test")
        assert isinstance(effects, list)
        assert len(effects) >= 3

    def test_ceramic_puppet_effects(self):
        from puppet_effects.material_effects import MaterialEffects
        effects = MaterialEffects.ceramic_puppet(1.0, "test")
        assert isinstance(effects, list)
        assert len(effects) >= 3

    def test_all_materials(self):
        from puppet_effects.material_effects import MaterialEffects
        materials = ["wooden", "ceramic", "cloth", "clay", "metal"]
        for mat in materials:
            method = getattr(MaterialEffects, f"{mat}_puppet")
            effects = method(1.0, "test")
            assert isinstance(effects, list)
            assert len(effects) > 0


class TestStopMotion:
    def test_stop_motion_presets(self):
        from puppet_effects.stop_motion import StopMotionEffect
        presets = StopMotionEffect.get_presets()
        assert isinstance(presets, dict)
        assert "8fps_classic" in presets
        assert "12fps_smooth" in presets
        assert "15fps_modern" in presets
        assert "handheld_shaky" in presets

    def test_generate_effects(self):
        from puppet_effects.stop_motion import StopMotionConfig, StopMotionEffect
        config = StopMotionConfig(fps=12, jitter_amount=2.0, flicker_amount=5.0, camera_shake=1.0)
        result = StopMotionEffect.generate_effects(config, "layer", 5.0)
        assert isinstance(result, dict)
        assert "effects" in result
        assert "keyframes" in result
        assert "expressions" in result


class TestJointSystem:
    def test_joint_presets(self):
        from puppet_effects.joint_system import JointSystem
        presets = ["human_17point", "human_upper_body", "marionette_basic", "simple_puppet"]
        for p in presets:
            config = JointSystem.get_standard_joint_preset(p)
            assert config is not None
            assert len(config.joint_points) > 0

    def test_generate_joint_effects(self):
        from puppet_effects.joint_system import JointConfig, JointPoint, JointSystem
        joints = [
            JointPoint(name="head", x=960, y=200),
            JointPoint(name="left_shoulder", x=860, y=350, side="left"),
            JointPoint(name="right_shoulder", x=1060, y=350, side="right"),
        ]
        config = JointConfig(joint_points=joints, show_joint_seams=True)
        result = JointSystem.generate_joint_effects(config, "layer", 3.0)
        assert isinstance(result, dict)
        assert "effects" in result

    def test_bbox_estimation(self):
        from puppet_effects.joint_system import JointSystem
        bbox = {"x": 800, "y": 100, "width": 320, "height": 800}
        joints = JointSystem.estimate_joints_from_bbox(bbox, "human")
        assert len(joints) == 17


class TestMiniScene:
    def test_mini_scene_presets(self):
        from puppet_effects.mini_scene import MiniSceneEffect
        presets = MiniSceneEffect.get_presets()
        assert isinstance(presets, dict)
        assert "theater_stage" in presets
        assert "toy_table" in presets
        assert "miniature_city" in presets
        assert "shadow_puppet" in presets
        assert "marionette_stage" in presets

    def test_generate_mini_scene(self):
        from puppet_effects.mini_scene import MiniSceneConfig, MiniSceneEffect
        config = MiniSceneConfig(
            tilt_shift=True,
            stage_lighting=True,
            vignette=True,
            floor_shadow=True,
        )
        result = MiniSceneEffect.generate_mini_scene(config, "scene", 1920, 1080, 5.0)
        assert isinstance(result, dict)
        assert "effects" in result
        assert "adjustment_layers" in result


class TestSilhouettePuppetExtension:
    def test_joint_track_preset_exists(self):
        from silhouette_executor import PRESET_CONFIGS
        assert "joint_track_17point" in PRESET_CONFIGS
        assert "face_track_basic" in PRESET_CONFIGS
        assert "face_track_expression" in PRESET_CONFIGS

    def test_joint_track_command_registered(self):
        from silhouette_executor import SilhouetteExecutor
        executor = SilhouetteExecutor(mode="simulate")
        result = executor.execute({
            "command": "silhouette_joint_track",
            "params": {
                "source_path": "test.mp4",
                "joint_points": [
                    {"name": "head", "x": 100, "y": 100, "frame": 0},
                ],
                "track_mode": "point",
            },
        })
        assert result is not None
        assert "status" in result
        assert "unknown command" not in str(result.get("error", "")).lower()

    def test_face_track_command_registered(self):
        from silhouette_executor import SilhouetteExecutor
        executor = SilhouetteExecutor(mode="simulate")
        result = executor.execute({
            "command": "silhouette_face_track",
            "params": {
                "source_path": "test.mp4",
                "face_landmarks": [
                    {"name": "left_eye", "x": 100, "y": 100, "frame": 0},
                ],
                "expression_mode": "basic",
            },
        })
        assert result is not None
        assert "status" in result
        assert "unknown command" not in str(result.get("error", "")).lower()


class TestPipelinePuppetIntegration:
    def test_puppet_keyword_detection(self, pipeline):
        from ae_agent_pipeline import UnderstandingResult
        understanding = UnderstandingResult()
        pipeline._detect_silhouette_intent(understanding, "把这段视频变成木偶风格")
        assert understanding.style == "wooden_puppet"
        assert understanding.route_type == "hybrid"

    def test_puppet_roto_operation_generation(self, pipeline):
        from ae_agent_pipeline import PerceptionResult, UnderstandingResult
        understanding = UnderstandingResult()
        understanding.silhouette_task = "puppet_roto"
        perception = PerceptionResult()
        ops = pipeline._generate_silhouette_operations(understanding, perception)
        assert len(ops) > 0
        assert ops[0]["command"] == "silhouette_roto"

    def test_puppet_style_enhancement_runs(self, pipeline):
        from ae_agent_pipeline import PlanningResult, UnderstandingResult
        plan = PlanningResult()
        plan.layers = [{"name": "Video Layer", "type": "video"}]
        plan.effects = []
        plan.keyframes = []
        understanding = UnderstandingResult()
        understanding.style = "wooden_puppet"
        understanding.intensity = 1.0
        try:
            pipeline._enhance_with_puppet_style(plan, understanding)
            assert True
        except Exception:
            pytest.fail("_enhance_with_puppet_style raised exception")

    def test_plan_with_puppet_style(self, pipeline):
        from ae_agent_pipeline import PerceptionResult, UnderstandingResult
        understanding = UnderstandingResult()
        understanding.style = "wooden_puppet"
        understanding.intensity = 1.0
        understanding.duration = 5.0
        understanding.route_type = "ae_only"
        perception = PerceptionResult()
        try:
            plan = pipeline.plan(understanding, perception)
            assert plan is not None
        except Exception as e:
            import traceback
            traceback.print_exc()
            pytest.fail(f"plan() with puppet style raised: {type(e).__name__}: {e}")


class TestRegressionBugs:
    def test_mediapipe_simulate_no_math_random_crash(self):
        from mediapipe_integration import MediaPipeConfig, MediaPipeIntegrator, MediaPipeResult
        config = MediaPipeConfig(mode="simulate", detect_pose=True, detect_face=True)
        integrator = MediaPipeIntegrator(config)
        result = MediaPipeResult()
        result.width = 1280
        result.height = 720
        result.fps = 30.0
        result.duration = 2.0
        try:
            detections = integrator._generate_simulated_detections(result)
            assert len(detections) > 0
            assert detections[0]["persons"][0]["confidence"] >= 0.85
            assert detections[0]["persons"][0]["confidence"] <= 0.95
        except AttributeError as e:
            if "math" in str(e) and "random" in str(e):
                pytest.fail(f"math.random() crash regression: {e}")
            raise

    def test_mini_scene_preset_not_mutated(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine

        from puppet_effects.mini_scene import MiniSceneEffect
        engine = PuppetStyleEngine()
        presets_before = MiniSceneEffect.get_presets()
        theater_before = presets_before["theater_stage"]
        tilt_blur_before = theater_before.tilt_blur
        dof_blur_before = theater_before.dof_blur
        config = PuppetStyleConfig(
            style_type="wooden_puppet",
            intensity=2.0,
            comp_width=1920,
            comp_height=1080,
        )
        for _ in range(3):
            engine.generate_style(config, "test_layer", 5.0)
        presets_after = MiniSceneEffect.get_presets()
        theater_after = presets_after["theater_stage"]
        assert theater_after.tilt_blur == tilt_blur_before, \
            f"MiniScene preset tilt_blur mutated: {tilt_blur_before} -> {theater_after.tilt_blur}"
        assert theater_after.dof_blur == dof_blur_before, \
            f"MiniScene preset dof_blur mutated: {dof_blur_before} -> {theater_after.dof_blur}"

    def test_joint_preset_not_mutated(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine

        from puppet_effects.joint_system import JointSystem
        engine = PuppetStyleEngine()
        preset_before = JointSystem.get_standard_joint_preset("simple_puppet")
        seam_radius_before = preset_before.seam_radius
        joint_gap_before = preset_before.joint_gap
        config = PuppetStyleConfig(
            style_type="wooden_puppet",
            intensity=1.0,
            comp_width=1920,
            comp_height=1080,
            joint_system={"seam_radius": 20.0, "joint_gap": 10.0},
        )
        engine.generate_style(config, "test_layer", 5.0)
        preset_after = JointSystem.get_standard_joint_preset("simple_puppet")
        assert preset_after.seam_radius == seam_radius_before, \
            f"Joint preset seam_radius mutated: {seam_radius_before} -> {preset_after.seam_radius}"
        assert preset_after.joint_gap == joint_gap_before, \
            f"Joint preset joint_gap mutated: {joint_gap_before} -> {preset_after.joint_gap}"

    def test_multiple_intensity_calls_consistent(self):
        from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine

        from puppet_effects.mini_scene import MiniSceneEffect
        engine = PuppetStyleEngine()
        presets = MiniSceneEffect.get_presets()
        base_tilt_blur = presets["theater_stage"].tilt_blur
        config_half = PuppetStyleConfig(
            style_type="wooden_puppet", intensity=0.5,
            comp_width=1920, comp_height=1080,
        )
        config_full = PuppetStyleConfig(
            style_type="wooden_puppet", intensity=1.0,
            comp_width=1920, comp_height=1080,
        )
        result_half_1 = engine.generate_style(config_half, "layer1", 3.0)
        result_full_1 = engine.generate_style(config_full, "layer2", 3.0)
        result_half_2 = engine.generate_style(config_half, "layer3", 3.0)
        presets_after = MiniSceneEffect.get_presets()
        assert presets_after["theater_stage"].tilt_blur == base_tilt_blur
