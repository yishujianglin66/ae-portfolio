"""puppet_effects.face_puppet 单元测试 - 面部木偶化效果模块"""
import os
import sys
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from puppet_effects.face_puppet import (
    FacePuppetConfig,
    FacePuppetEffect,
)


class TestFacePuppetConfig:
    def test_default_config(self):
        cfg = FacePuppetConfig()
        assert cfg.style == "all"
        assert cfg.eye_style == "button"
        assert cfg.mouth_style == "stitched"
        assert cfg.skin_porcelain is True
        assert cfg.eye_scale == 1.0
        assert cfg.mouth_scale == 1.0
        assert cfg.eye_spacing == 1.0
        assert cfg.color == [0.2, 0.1, 0.05, 1.0]
        assert cfg.button_texture is True
        assert cfg.stitch_count == 8

    def test_custom_config(self):
        cfg = FacePuppetConfig(
            style="button_eyes",
            eye_style="googly",
            mouth_style="line",
            skin_porcelain=False,
            eye_scale=1.5,
            mouth_scale=0.8,
            eye_spacing=1.2,
            color=[1.0, 0.0, 0.0, 1.0],
            button_texture=False,
            stitch_count=12,
        )
        assert cfg.style == "button_eyes"
        assert cfg.eye_style == "googly"
        assert cfg.eye_scale == 1.5
        assert cfg.stitch_count == 12


class TestPresets:
    def test_get_presets_not_empty(self):
        presets = FacePuppetEffect.get_presets()
        assert isinstance(presets, dict)
        assert len(presets) >= 5

    def test_preset_names(self):
        presets = FacePuppetEffect.get_presets()
        expected_presets = [
            "classic_button",
            "rag_doll",
            "porcelain_doll",
            "wooden_marionette",
            "simple",
            "stitched",
        ]
        for name in expected_presets:
            assert name in presets, f"Missing preset: {name}"

    def test_get_single_preset(self):
        cfg = FacePuppetEffect.get_preset("classic_button")
        assert isinstance(cfg, FacePuppetConfig)
        assert cfg.style == "all"
        assert cfg.eye_style == "button"
        assert cfg.mouth_style == "stitched"

    def test_get_invalid_preset_raises(self):
        with pytest.raises(ValueError) as excinfo:
            FacePuppetEffect.get_preset("nonexistent_preset")
        assert "nonexistent_preset" in str(excinfo.value)

    def test_presets_are_face_puppet_config(self):
        presets = FacePuppetEffect.get_presets()
        for name, cfg in presets.items():
            assert isinstance(cfg, FacePuppetConfig), f"{name} is not FacePuppetConfig"

    def test_preset_caching(self):
        FacePuppetEffect._presets = None
        p1 = FacePuppetEffect.get_presets()
        p2 = FacePuppetEffect.get_presets()
        assert p1 is p2


class TestEstimateFaceFromBbox:
    def test_returns_all_features(self):
        bbox = {"x": 400, "y": 200, "width": 300, "height": 400}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)

        assert "left_eye" in face
        assert "right_eye" in face
        assert "mouth" in face
        assert "nose" in face
        assert "jaw" in face
        assert "face_bbox" in face

    def test_eye_positions(self):
        bbox = {"x": 100, "y": 100, "width": 200, "height": 300}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)

        cx = 100 + 200 / 2
        eye_spacing = 200 * 0.25
        assert face["left_eye"]["x"] == pytest.approx(cx - eye_spacing)
        assert face["right_eye"]["x"] == pytest.approx(cx + eye_spacing)
        assert face["left_eye"]["y"] == face["right_eye"]["y"]
        assert face["left_eye"]["y"] == pytest.approx(100 + 300 * 0.35)

    def test_mouth_position(self):
        bbox = {"x": 0, "y": 0, "width": 200, "height": 200}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)

        assert face["mouth"]["x"] == pytest.approx(100)
        assert face["mouth"]["y"] == pytest.approx(200 * 0.72)
        assert face["mouth"]["width"] == pytest.approx(200 * 0.35)
        assert face["mouth"]["height"] == pytest.approx(200 * 0.08)

    def test_nose_position(self):
        bbox = {"x": 0, "y": 0, "width": 100, "height": 200}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)
        assert face["nose"]["x"] == pytest.approx(50)
        assert face["nose"]["y"] == pytest.approx(200 * 0.55)

    def test_jaw_position(self):
        bbox = {"x": 0, "y": 0, "width": 100, "height": 200}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)
        assert face["jaw"]["x"] == pytest.approx(50)
        assert face["jaw"]["y"] == pytest.approx(200 * 0.92)

    def test_face_bbox_preserved(self):
        bbox = {"x": 10, "y": 20, "width": 100, "height": 200}
        face = FacePuppetEffect.estimate_face_from_bbox(bbox)
        assert face["face_bbox"]["x"] == 10
        assert face["face_bbox"]["y"] == 20
        assert face["face_bbox"]["width"] == 100
        assert face["face_bbox"]["height"] == 200

    def test_default_values(self):
        face = FacePuppetEffect.estimate_face_from_bbox({})
        assert face is not None
        assert "left_eye" in face


class TestGenerateButtonEye:
    def test_button_eye_style(self):
        cfg = FacePuppetConfig(eye_style="button", eye_scale=1.0)
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "left"
        )
        assert len(effects) > 0

        effect_names = [e["displayName"] for e in effects]
        assert any("ButtonEye_left_Base" in n for n in effect_names)
        assert any("ButtonEye_left_Hole" in n for n in effect_names)
        assert any("ButtonEye_left_Highlight" in n for n in effect_names)

    def test_button_eye_with_texture(self):
        cfg = FacePuppetConfig(eye_style="button", button_texture=True)
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "right"
        )
        effect_names = [e["displayName"] for e in effects]
        assert any("Rim" in n for n in effect_names)

    def test_button_eye_without_texture(self):
        cfg = FacePuppetConfig(eye_style="button", button_texture=False)
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "right"
        )
        effect_names = [e["displayName"] for e in effects]
        assert not any("Rim" in n for n in effect_names)

    def test_googly_eye_style(self):
        cfg = FacePuppetConfig(eye_style="googly")
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "left"
        )
        effect_names = [e["displayName"] for e in effects]
        assert any("GooglyEye" in n for n in effect_names)

    def test_painted_eye_style(self):
        cfg = FacePuppetConfig(eye_style="painted")
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "left"
        )
        effect_names = [e["displayName"] for e in effects]
        assert any("PaintedEye" in n for n in effect_names)

    def test_dot_eye_style(self):
        cfg = FacePuppetConfig(eye_style="dot")
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "left"
        )
        assert len(effects) == 1
        assert "DotEye" in effects[0]["displayName"]

    def test_eye_scale(self):
        cfg_small = FacePuppetConfig(eye_style="button", eye_scale=0.5)
        cfg_large = FacePuppetConfig(eye_style="button", eye_scale=2.0)

        effects_small = FacePuppetEffect._generate_button_eye(
            cfg_small, {"x": 500, "y": 300}, "left"
        )
        effects_large = FacePuppetEffect._generate_button_eye(
            cfg_large, {"x": 500, "y": 300}, "left"
        )

        base_small = next(e for e in effects_small if "Base" in e["displayName"])
        base_large = next(e for e in effects_large if "Base" in e["displayName"])

        assert base_large["settings"]["Radius"] > base_small["settings"]["Radius"]

    def test_button_eye_holes_count(self):
        cfg = FacePuppetConfig(eye_style="button")
        effects = FacePuppetEffect._generate_button_eye(
            cfg, {"x": 500, "y": 300}, "left"
        )
        hole_effects = [e for e in effects if "Hole" in e["displayName"]]
        assert len(hole_effects) == 4


class TestGenerateStitchedMouth:
    def test_stitched_mouth_style(self):
        cfg = FacePuppetConfig(mouth_style="stitched", stitch_count=8)
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 120, "height": 30}
        )
        effect_names = [e["displayName"] for e in effects]
        stitch_effects = [e for e in effect_names if "Stitch" in e]
        assert len(stitch_effects) == 8 + 2  # 8 stitches + 2 knots

    def test_line_mouth_style(self):
        cfg = FacePuppetConfig(mouth_style="line")
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 120, "height": 30}
        )
        assert len(effects) == 1
        assert "LineMouth" in effects[0]["displayName"]

    def test_painted_mouth_style(self):
        cfg = FacePuppetConfig(mouth_style="painted")
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 120, "height": 30}
        )
        assert any("PaintedMouth" in e["displayName"] for e in effects)

    def test_button_mouth_style(self):
        cfg = FacePuppetConfig(mouth_style="button")
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 80, "height": 30}
        )
        effect_names = [e["displayName"] for e in effects]
        assert any("ButtonMouth_Base" in n for n in effect_names)
        assert any("ButtonMouth_Hole" in n for n in effect_names)

    def test_mouth_scale(self):
        cfg_small = FacePuppetConfig(mouth_style="line", mouth_scale=0.5)
        cfg_large = FacePuppetConfig(mouth_style="line", mouth_scale=2.0)

        # For line style, check width via Starting/Ending points
        mouth_small = {"x": 600, "y": 500, "width": 100, "height": 30}
        mouth_large = {"x": 600, "y": 500, "width": 100, "height": 30}

        effects_small = FacePuppetEffect._generate_stitched_mouth(cfg_small, mouth_small)
        effects_large = FacePuppetEffect._generate_stitched_mouth(cfg_large, mouth_large)

        start_small = effects_small[0]["settings"]["Starting Point"]
        end_small = effects_small[0]["settings"]["Ending Point"]
        width_small = end_small[0] - start_small[0]

        start_large = effects_large[0]["settings"]["Starting Point"]
        end_large = effects_large[0]["settings"]["Ending Point"]
        width_large = end_large[0] - start_large[0]

        assert width_large > width_small

    def test_stitch_count(self):
        cfg = FacePuppetConfig(mouth_style="stitched", stitch_count=12)
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 200, "height": 30}
        )
        stitch_effects = [e for e in effects if "StitchMouth_Stitch" in e["displayName"]]
        assert len(stitch_effects) == 12

    def test_stitch_sin_curve(self):
        cfg = FacePuppetConfig(mouth_style="stitched", stitch_count=8)
        effects = FacePuppetEffect._generate_stitched_mouth(
            cfg, {"x": 600, "y": 500, "width": 200, "height": 40}
        )
        stitch_effects = [e for e in effects if "StitchMouth_Stitch" in e["displayName"]]

        y_positions = []
        for e in stitch_effects:
            start = e["settings"]["Starting Point"]
            end = e["settings"]["Ending Point"]
            avg_y = (start[1] + end[1]) / 2
            y_positions.append(avg_y)

        first_y = y_positions[0]
        middle_y = y_positions[len(y_positions) // 2]
        last_y = y_positions[-1]

        assert first_y == pytest.approx(last_y, abs=5.0)


class TestGeneratePorcelainSkin:
    def test_porcelain_skin_effects(self):
        cfg = FacePuppetConfig(skin_porcelain=True)
        effects = FacePuppetEffect._generate_porcelain_skin(
            cfg, {"x": 400, "y": 200, "width": 400, "height": 500}
        )
        assert len(effects) == 5

        effect_names = [e["displayName"] for e in effects]
        assert "PorcelainSkin_Smooth" in effect_names
        assert "PorcelainSkin_Tint" in effect_names
        assert "PorcelainSkin_Glow" in effect_names
        assert "PorcelainSkin_Reflection" in effect_names
        assert "PorcelainSkin_Curves" in effect_names

    def test_porcelain_skin_has_correct_effect_types(self):
        cfg = FacePuppetConfig(skin_porcelain=True)
        effects = FacePuppetEffect._generate_porcelain_skin(
            cfg, {"x": 400, "y": 200, "width": 400, "height": 500}
        )
        match_names = [e["matchName"] for e in effects]
        assert "ADBE Gaussian Blur 2" in match_names
        assert "ADBE Tint 2" in match_names
        assert "ADBE Glo2" in match_names
        assert "ADBE Ramp" in match_names
        assert "ADBE CurvesCustom" in match_names


class TestGenerateFaceJoints:
    def test_face_joints_effects(self):
        cfg = FacePuppetConfig()
        face_data = {
            "jaw": {"x": 600, "y": 650},
            "nose": {"x": 600, "y": 450},
            "left_eye": {"x": 500, "y": 350},
            "right_eye": {"x": 700, "y": 350},
            "face_bbox": {"x": 400, "y": 200, "width": 400, "height": 500},
        }
        effects = FacePuppetEffect._generate_face_joints(cfg, face_data)
        assert len(effects) == 3

        effect_names = [e["displayName"] for e in effects]
        assert "FaceJoint_Jaw" in effect_names
        assert "FaceJoint_TempleLeft" in effect_names
        assert "FaceJoint_TempleRight" in effect_names

    def test_jaw_joint_position(self):
        cfg = FacePuppetConfig()
        face_data = {
            "jaw": {"x": 600, "y": 700},
            "nose": {"x": 600, "y": 400},
            "left_eye": {"x": 500, "y": 300},
            "right_eye": {"x": 700, "y": 300},
            "face_bbox": {"x": 400, "y": 200, "width": 400, "height": 600},
        }
        effects = FacePuppetEffect._generate_face_joints(cfg, face_data)
        jaw_effect = next(e for e in effects if "Jaw" in e["displayName"])

        expected_y = 400 + (700 - 400) * 0.3
        assert jaw_effect["settings"]["Center"][0] == 600
        assert jaw_effect["settings"]["Center"][1] == pytest.approx(expected_y)


class TestGenerateExpressionLimits:
    def test_expression_limits(self):
        cfg = FacePuppetConfig()
        face_data = {
            "left_eye": {"x": 500, "y": 350},
            "right_eye": {"x": 700, "y": 350},
            "mouth": {"x": 600, "y": 500, "width": 100, "height": 30},
        }
        expressions = FacePuppetEffect._generate_expression_limits(
            cfg, "FaceLayer", face_data
        )
        assert len(expressions) == 2

        expr_types = [e["property"] for e in expressions]
        assert any("MouthOpen" in e for e in expr_types)
        assert any("Blink" in e for e in expr_types)

    def test_expressions_have_clamp(self):
        cfg = FacePuppetConfig()
        expressions = FacePuppetEffect._generate_expression_limits(
            cfg, "Layer", {}
        )
        for expr in expressions:
            assert "clamp" in expr["expression"]

    def test_expression_descriptions(self):
        cfg = FacePuppetConfig()
        expressions = FacePuppetEffect._generate_expression_limits(
            cfg, "Layer", {}
        )
        for expr in expressions:
            assert "description" in expr
            assert len(expr["description"]) > 0


class TestGenerateFacePuppet:
    def test_full_face_puppet_all_style(self):
        cfg = FacePuppetEffect.get_preset("classic_button")
        face_data = FacePuppetEffect.estimate_face_from_bbox({
            "x": 400, "y": 200, "width": 400, "height": 500,
        })
        result = FacePuppetEffect.generate_face_puppet(
            cfg, "FaceLayer", face_data, duration=5.0
        )

        assert result["layer_name"] == "FaceLayer"
        assert result["duration"] == 5.0
        assert isinstance(result["effects"], list)
        assert isinstance(result["keyframes"], list)
        assert isinstance(result["layers"], list)
        assert isinstance(result["expressions"], list)
        assert len(result["effects"]) > 0

    def test_button_eyes_only_style(self):
        cfg = FacePuppetConfig(style="button_eyes", eye_style="button")
        result = FacePuppetEffect.generate_face_puppet(cfg, "TestLayer")
        assert len(result["effects"]) > 0
        assert len(result["expressions"]) == 0

    def test_stitched_mouth_only_style(self):
        cfg = FacePuppetConfig(style="stitched_mouth", mouth_style="stitched")
        result = FacePuppetEffect.generate_face_puppet(cfg, "TestLayer")
        assert len(result["effects"]) > 0

    def test_porcelain_skin_only_style(self):
        cfg = FacePuppetConfig(style="porcelain_skin", skin_porcelain=True)
        result = FacePuppetEffect.generate_face_puppet(cfg, "TestLayer")
        assert len(result["effects"]) > 0

    def test_no_face_data_provided(self):
        cfg = FacePuppetConfig(style="all")
        result = FacePuppetEffect.generate_face_puppet(cfg, "TestLayer", None)
        assert len(result["effects"]) > 0

    def test_eye_spacing_offset(self):
        cfg_close = FacePuppetConfig(
            style="button_eyes", eye_style="button", eye_spacing=0.5
        )
        cfg_wide = FacePuppetConfig(
            style="button_eyes", eye_style="button", eye_spacing=2.0
        )
        face_data = FacePuppetEffect.estimate_face_from_bbox({
            "x": 0, "y": 0, "width": 400, "height": 500,
        })

        result_close = FacePuppetEffect.generate_face_puppet(
            cfg_close, "Layer", face_data
        )
        result_wide = FacePuppetEffect.generate_face_puppet(
            cfg_wide, "Layer", face_data
        )

        left_close = next(
            e for e in result_close["effects"]
            if "ButtonEye_left_Base" in e["displayName"]
        )
        left_wide = next(
            e for e in result_wide["effects"]
            if "ButtonEye_left_Base" in e["displayName"]
        )

        assert left_wide["settings"]["Center"][0] < left_close["settings"]["Center"][0]

    def test_all_presets_generate_valid_output(self):
        presets = FacePuppetEffect.get_presets()
        for name, cfg in presets.items():
            result = FacePuppetEffect.generate_face_puppet(cfg, f"Layer_{name}")
            assert isinstance(result["effects"], list), f"{name} effects not list"
            assert isinstance(result["expressions"], list), f"{name} expressions not list"
