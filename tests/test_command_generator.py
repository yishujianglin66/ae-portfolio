"""AE 命令生成器单元测试"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_command_generator import AECommandGenerator


def test_generate_create_comp():
    gen = AECommandGenerator()
    commands = gen.generate_create_comp("Test_Comp", 1920, 1080, 5, 30)
    assert len(commands) == 1
    assert commands[0]["op"] == "createComposition"
    assert commands[0]["params"]["name"] == "Test_Comp"
    assert commands[0]["params"]["width"] == 1920
    assert commands[0]["params"]["height"] == 1080
    assert commands[0]["params"]["duration"] == 5
    assert commands[0]["params"]["frameRate"] == 30


def test_generate_create_comp_with_bg_color():
    gen = AECommandGenerator()
    commands = gen.generate_create_comp("Test", 1920, 1080, 5, 30, [255, 0, 0])
    assert commands[0]["params"]["backgroundColor"] == [255, 0, 0]


def test_generate_import_footage_single():
    gen = AECommandGenerator()
    commands = gen.generate_import_footage(["/path/to/video.mp4"])
    assert len(commands) == 1
    assert commands[0]["op"] == "importFootage"
    assert commands[0]["params"]["filePath"] == "/path/to/video.mp4"


def test_generate_import_footage_multiple():
    gen = AECommandGenerator()
    commands = gen.generate_import_footage(["/path/a.mp4", "/path/b.mp4", "/path/c.mp4"])
    assert len(commands) == 3
    assert commands[0]["params"]["filePath"] == "/path/a.mp4"
    assert commands[1]["params"]["filePath"] == "/path/b.mp4"
    assert commands[2]["params"]["filePath"] == "/path/c.mp4"


def test_generate_place_footage():
    gen = AECommandGenerator()
    commands = gen.generate_place_footage("MyComp", "Layer1", "/path/video.mp4", 1.5)
    assert len(commands) == 1
    assert commands[0]["op"] == "placeFootageInComp"
    assert commands[0]["params"]["compName"] == "MyComp"
    assert commands[0]["params"]["layerName"] == "Layer1"
    assert commands[0]["params"]["footagePath"] == "/path/video.mp4"
    assert commands[0]["params"]["startTime"] == 1.5


def test_generate_apply_effect():
    gen = AECommandGenerator()
    commands = gen.generate_apply_effect("Layer1", "ADBE Glo2", {"Glow Radius": 50})
    assert len(commands) == 1
    assert commands[0]["op"] == "applyEffect"
    assert commands[0]["params"]["layerName"] == "Layer1"
    assert commands[0]["params"]["effectMatchName"] == "ADBE Glo2"
    assert commands[0]["params"]["effectSettings"]["Glow Radius"] == 50


def test_generate_apply_effect_with_comp():
    gen = AECommandGenerator()
    commands = gen.generate_apply_effect("Layer1", "ADBE Glo2", {"Radius": 10}, "Comp1")
    assert commands[0]["params"]["compName"] == "Comp1"


def test_generate_set_keyframe():
    gen = AECommandGenerator()
    commands = gen.generate_set_keyframe("Layer1", "Position", 1.0, [960, 540], "linear")
    assert len(commands) == 1
    assert commands[0]["op"] == "setLayerKeyframe"
    assert commands[0]["params"]["layerName"] == "Layer1"
    assert commands[0]["params"]["propertyName"] == "Position"
    assert commands[0]["params"]["timeInSeconds"] == 1.0
    assert commands[0]["params"]["value"] == [960, 540]
    assert commands[0]["params"]["easeType"] == "linear"


def test_generate_render():
    gen = AECommandGenerator()
    commands = gen.generate_render("MyComp", "/output/video.mp4", "mp4", "high")
    assert len(commands) == 1
    assert commands[0]["op"] == "renderComposition"
    assert commands[0]["params"]["compName"] == "MyComp"
    assert commands[0]["params"]["outputPath"] == "/output/video.mp4"
    assert commands[0]["params"]["format"] == "mp4"


def test_generate_from_planning_result():
    gen = AECommandGenerator()
    planning_result = {
        "composition": {
            "name": "Test_Comp",
            "width": 1920,
            "height": 1080,
            "duration": 5,
            "frameRate": 30
        },
        "layers": [
            {"name": "Video1", "type": "footage", "source": "/path/to/video.mp4", "startTime": 0, "duration": 5},
            {"name": "Audio1", "type": "audio", "source": "/path/to/audio.mp3", "startTime": 0, "duration": 5}
        ],
        "effects": [
            {"layerName": "Video1", "effectName": "ADBE Glo2", "settings": {"Radius": 50}}
        ],
        "keyframes": [
            {"layerName": "Video1", "propertyName": "Opacity", "time": 0, "value": 0, "easeType": "easeInOut"},
            {"layerName": "Video1", "propertyName": "Opacity", "time": 1, "value": 100, "easeType": "easeInOut"}
        ],
        "transitions": []
    }
    commands = gen.generate_from_planning_result(planning_result)

    op_types = [cmd["op"] for cmd in commands]
    assert "createComposition" in op_types
    assert "importFootage" in op_types
    assert "placeFootageInComp" in op_types
    assert "applyEffect" in op_types
    assert "setLayerKeyframe" in op_types
    assert len(commands) >= 8  # 1 create + 2 import + 2 place + 1 effect + 2 keyframes


def test_generate_from_planning_result_empty():
    gen = AECommandGenerator()
    planning_result = {
        "composition": {"name": "Empty", "width": 1920, "height": 1080, "duration": 3, "frameRate": 30},
        "layers": [],
        "effects": [],
        "keyframes": [],
        "transitions": []
    }
    commands = gen.generate_from_planning_result(planning_result)
    assert len(commands) == 1  # only createComposition
    assert commands[0]["op"] == "createComposition"


def test_generate_from_planning_result_default_name():
    gen = AECommandGenerator()
    planning_result = {
        "composition": {},
        "layers": [],
        "effects": [],
        "keyframes": [],
        "transitions": []
    }
    commands = gen.generate_from_planning_result(planning_result)
    assert len(commands) == 1
    assert commands[0]["params"]["name"] == "AI_Generated"
