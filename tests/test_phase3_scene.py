import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scene_orchestrator import (
    CAMERA_MOVE_TYPES,
    TRANSITION_TYPES,
    CameraMove,
    Scene,
    SceneOrchestrator,
    Transition,
)


class TestSceneOrchestratorInitialization:
    def test_initialization(self):
        so = SceneOrchestrator(fps=24, comp_width=1280, comp_height=720)
        assert so.fps == 24
        assert so.comp_width == 1280
        assert so.comp_height == 720
        assert so.scenes == []
        assert so.transitions == []
        assert so._scene_counter == 0

    def test_initialization_defaults(self):
        so = SceneOrchestrator()
        assert so.fps == 30
        assert so.comp_width == 1920
        assert so.comp_height == 1080


class TestAddScene:
    def test_add_scene(self):
        so = SceneOrchestrator()
        scene = Scene(name="intro", duration=3.0)
        result = so.add_scene(scene)
        assert result is scene
        assert len(so.scenes) == 1
        assert so.scenes[0].name == "intro"
        assert so.scenes[0].start_time == 0.0
        assert so.scenes[0].layer_name == "Scene_01_intro"

    def test_add_multiple_scenes(self):
        so = SceneOrchestrator()
        scene1 = Scene(name="intro", duration=2.0)
        scene2 = Scene(name="main", duration=5.0)
        scene3 = Scene(name="outro", duration=3.0)

        so.add_scene(scene1)
        so.add_scene(scene2)
        so.add_scene(scene3)

        assert len(so.scenes) == 3
        assert so.scenes[0].start_time == 0.0
        assert so.scenes[1].start_time == 2.0
        assert so.scenes[2].start_time == 7.0
        assert so.total_duration == 10.0
        assert so.scenes[0].layer_name == "Scene_01_intro"
        assert so.scenes[1].layer_name == "Scene_02_main"
        assert so.scenes[2].layer_name == "Scene_03_outro"

    def test_add_scene_with_layer_name(self):
        so = SceneOrchestrator()
        scene = Scene(name="custom", duration=2.0, layer_name="MyLayer")
        so.add_scene(scene)
        assert scene.layer_name == "MyLayer"


class TestTransitions:
    def test_generate_transitions_default(self):
        so = SceneOrchestrator()
        so.add_scene(Scene(name="a", duration=2.0))
        so.add_scene(Scene(name="b", duration=2.0))
        so.add_scene(Scene(name="c", duration=2.0))

        transitions = so.generate_transitions("crossfade", duration=0.5)
        assert len(transitions) == 2
        assert transitions[0].type == "crossfade"
        assert transitions[0].duration == 0.5
        assert transitions[0].from_scene == "Scene_01_a"
        assert transitions[0].to_scene == "Scene_02_b"
        assert transitions[1].from_scene == "Scene_02_b"
        assert transitions[1].to_scene == "Scene_03_c"

    def test_generate_all_transition_types(self):
        transition_types = list(TRANSITION_TYPES.keys())
        assert len(transition_types) == 10

        for t_type in transition_types:
            so = SceneOrchestrator()
            so.add_scene(Scene(name="a", duration=2.0))
            so.add_scene(Scene(name="b", duration=2.0))
            transitions = so.generate_transitions(t_type, duration=0.5)
            assert len(transitions) == 1
            assert transitions[0].type == t_type

    def test_generate_transitions_invalid_type(self):
        so = SceneOrchestrator()
        so.add_scene(Scene(name="a", duration=2.0))
        so.add_scene(Scene(name="b", duration=2.0))
        with pytest.raises(ValueError, match="Unknown transition type"):
            so.generate_transitions("invalid_type")

    def test_generate_transitions_single_scene(self):
        so = SceneOrchestrator()
        so.add_scene(Scene(name="a", duration=2.0))
        transitions = so.generate_transitions("crossfade")
        assert len(transitions) == 0


class TestCameraMoves:
    def test_camera_move_push(self):
        so = SceneOrchestrator()
        scene = Scene(name="test", duration=3.0)
        so.add_scene(scene)

        move = CameraMove(
            type="push",
            duration=2.0,
            start_scale=100.0,
            end_scale=150.0,
        )
        keyframes = so.apply_camera_move(scene, move)
        assert len(keyframes) == 2
        assert keyframes[0]["propertyName"] == "Scale"
        assert keyframes[0]["value"] == [100.0, 100.0]
        assert keyframes[1]["propertyName"] == "Scale"
        assert keyframes[1]["value"] == [150.0, 150.0]

    def test_camera_move_pan(self):
        so = SceneOrchestrator()
        scene = Scene(name="test", duration=3.0)
        so.add_scene(scene)

        move = CameraMove(
            type="pan_left",
            duration=2.0,
            start_x=0.0,
            end_x=-200.0,
        )
        keyframes = so.apply_camera_move(scene, move)
        assert len(keyframes) == 2
        assert keyframes[0]["propertyName"] == "Position"
        assert keyframes[0]["value"][0] == 960.0
        assert keyframes[1]["value"][0] == 760.0

    def test_apply_camera_to_scene(self):
        so = SceneOrchestrator()
        scene = Scene(name="test", duration=3.0)
        so.add_scene(scene)

        move_shake = CameraMove(
            type="shake",
            duration=2.0,
            shake_amplitude=10.0,
            shake_frequency=5.0,
        )
        keyframes = so.apply_camera_move(scene, move_shake)
        assert len(keyframes) > 2
        for kf in keyframes:
            assert kf["propertyName"] == "Position"


class TestTimeline:
    def test_generate_scene_timeline(self):
        so = SceneOrchestrator()
        so.add_scene(Scene(name="intro", duration=2.0))
        so.add_scene(Scene(name="main", duration=3.0))

        timeline = so.generate_timeline()
        scene_items = [t for t in timeline if t["type"] == "scene"]
        assert len(scene_items) == 2
        assert scene_items[0]["name"] == "intro"
        assert scene_items[0]["startTime"] == 0.0
        assert scene_items[0]["duration"] == 2.0
        assert scene_items[1]["startTime"] == 2.0

    def test_generate_timeline_with_transitions(self):
        so = SceneOrchestrator()
        so.add_scene(Scene(name="a", duration=2.0))
        so.add_scene(Scene(name="b", duration=2.0))
        so.add_scene(Scene(name="c", duration=2.0))
        so.generate_transitions("crossfade", duration=0.5)

        timeline = so.generate_timeline()
        scene_items = [t for t in timeline if t["type"] == "scene"]
        transition_items = [t for t in timeline if t["type"] == "transition"]
        assert len(scene_items) == 3
        assert len(transition_items) == 2
        assert timeline[0]["type"] == "scene"
        assert all("startTime" in t for t in timeline)
