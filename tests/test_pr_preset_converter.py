#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 PR 预设转化器
================

验证 AE 预设到 PR 预设的转化逻辑。
"""

import json
from pathlib import Path

import pytest

from ae.pr_preset_converter import PRPresetConverter


class TestPRPresetConverterInitialization:
    """测试转化器初始化。"""

    def test_default_initialization(self):
        """验证默认初始化。"""
        converter = PRPresetConverter()
        assert converter.presets_dir.exists()
        assert len(converter._converted_cache) == 0

    def test_custom_presets_dir(self):
        """验证自定义预设目录。"""
        custom_dir = Path("/tmp/test_presets")
        converter = PRPresetConverter(presets_dir=custom_dir)
        assert converter.presets_dir == custom_dir


class TestEffectPresetConversion:
    """测试效果预设转化。"""

    def test_convert_energy_rings_preset(self):
        """验证能量环效果预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "energy_rings",
            "category": "effect",
            "subcategory": "motion",
            "description": "能量环特效",
            "tags": ["能量环", "energy"],
            "parameters": {
                "ringCount": {"type": "number", "min": 1, "max": 20},
                "ringSpeed": {"type": "number", "min": 0.5, "max": 5.0},
            },
            "default_values": {
                "ringCount": 5,
                "ringSpeed": 2.0,
            },
        }
        pr_preset = converter.convert_effect_preset(ae_preset)

        assert pr_preset["name"] == "energy_rings"
        assert pr_preset["category"] == "effect"
        assert pr_preset["source"] == "ae_converted"
        assert "compatibility" in pr_preset
        assert "pr" in pr_preset["compatibility"]
        assert len(pr_preset["effects"]) == 2

    def test_convert_blur_preset(self):
        """验证模糊效果预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "gaussian_blur",
            "category": "effect",
            "parameters": {
                "blurriness": {"type": "number", "min": 0, "max": 100},
            },
            "default_values": {
                "blurriness": 25.0,
            },
        }
        pr_preset = converter.convert_effect_preset(ae_preset)

        assert pr_preset["effects"][0]["effect_name"] == "Gaussian Blur"
        assert "Blurriness" in pr_preset["effects"][0]["parameters"]

    def test_convert_color_preset(self):
        """验证调色效果预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "brightness_adjust",
            "category": "effect",
            "parameters": {
                "brightness": {"type": "number", "min": -100, "max": 100},
                "contrast": {"type": "number", "min": -100, "max": 100},
            },
            "default_values": {
                "brightness": 10.0,
                "contrast": 5.0,
            },
        }
        pr_preset = converter.convert_effect_preset(ae_preset)

        assert pr_preset["effects"][0]["effect_name"] == "Lumetri Color"


class TestTransitionPresetConversion:
    """测试转场预设转化。"""

    def test_convert_glitch_transition(self):
        """验证故障转场预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "cyber_glitch_transition",
            "category": "transition",
            "subcategory": "cyberpunk",
            "description": "赛博朋克故障转场",
            "default_values": {
                "duration": 1.0,
                "glitchIntensity": 0.7,
                "rgbShiftAmount": 20,
            },
        }
        pr_preset = converter.convert_transition_preset(ae_preset)

        assert pr_preset["category"] == "transition"
        assert pr_preset["transition_name"] == "Glitch"
        assert pr_preset["parameters"]["glitch_amount"] == 0.7
        assert pr_preset["parameters"]["rgb_shift"] == 20

    def test_convert_whip_pan_transition(self):
        """验证拉镜转场预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "whip_pan_transition",
            "category": "transition",
            "default_values": {
                "duration": 0.5,
            },
        }
        pr_preset = converter.convert_transition_preset(ae_preset)

        assert pr_preset["transition_name"] == "Whip Pan"
        assert pr_preset["duration"] == 0.5

    def test_convert_unknown_transition_defaults(self):
        """验证未知转场类型默认处理。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "unknown_transition",
            "category": "transition",
            "default_values": {},
        }
        pr_preset = converter.convert_transition_preset(ae_preset)

        assert pr_preset["transition_name"] == "Cross Dissolve"


class TestColorGradingPresetConversion:
    """测试调色预设转化。"""

    def test_convert_cinematic_grade(self):
        """验证电影调色预设转化。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "cinematic_grade",
            "category": "color_grading",
            "subcategory": "cinematic",
            "default_values": {
                "brightness": 10.0,
                "contrast": 15.0,
                "saturation": -5.0,
            },
        }
        pr_preset = converter.convert_color_grading_preset(ae_preset)

        assert pr_preset["effect_name"] == "Lumetri Color"
        assert pr_preset["parameters"]["exposure"] == 0.1
        assert pr_preset["parameters"]["contrast"] == 15.0
        assert pr_preset["parameters"]["saturation"] == -5.0

    def test_convert_empty_color_preset(self):
        """验证空调色预设处理。"""
        converter = PRPresetConverter()
        ae_preset = {
            "name": "empty_grade",
            "category": "color_grading",
            "default_values": {},
        }
        pr_preset = converter.convert_color_grading_preset(ae_preset)

        assert pr_preset["effect_name"] == "Lumetri Color"
        assert len(pr_preset["parameters"]) == 0


class TestBatchConversion:
    """测试批量转化功能。"""

    def test_convert_preset_file(self, tmp_path):
        """验证文件级批量转化。"""
        converter = PRPresetConverter()

        # 创建测试预设文件
        presets = [
            {
                "name": "test_effect",
                "category": "effect",
                "parameters": {},
                "default_values": {},
            },
            {
                "name": "test_transition",
                "category": "transition",
                "default_values": {"duration": 1.0},
            },
        ]
        input_file = tmp_path / "test_presets.json"
        with open(input_file, "w", encoding="utf-8") as f:
            json.dump(presets, f)

        output_file = tmp_path / "pr_test_presets.json"
        result = converter.convert_preset_file(input_file, output_file)

        assert len(result) == 2
        assert output_file.exists()

        # 验证输出内容
        with open(output_file, "r", encoding="utf-8") as f:
            pr_presets = json.load(f)
        assert len(pr_presets) == 2
        assert pr_presets[0]["source"] == "ae_converted"

    def test_get_conversion_report(self):
        """验证转化报告。"""
        converter = PRPresetConverter()

        # 先转化一些预设
        ae_preset = {
            "name": "test_preset",
            "category": "effect",
            "parameters": {},
            "default_values": {},
        }
        converter.convert_effect_preset(ae_preset)

        report = converter.get_conversion_report()
        assert report["total_converted"] >= 1
        assert "effect_map_coverage" in report
        assert "transition_map_coverage" in report


class TestEffectMapping:
    """测试效果映射表完整性。"""

    def test_ae_to_pr_effect_map_not_empty(self):
        """验证效果映射表非空。"""
        converter = PRPresetConverter()
        assert len(converter.AE_TO_PR_EFFECT_MAP) > 0

    def test_ae_to_pr_transition_map_not_empty(self):
        """验证转场映射表非空。"""
        converter = PRPresetConverter()
        assert len(converter.AE_TO_PR_TRANSITION_MAP) > 0

    def test_infer_effect_name_coverage(self):
        """验证效果名推断逻辑。"""
        converter = PRPresetConverter()

        assert converter._infer_pr_effect_name("blurriness", {}) == "Gaussian Blur"
        assert converter._infer_pr_effect_name("brightness", {}) == "Lumetri Color"
        assert converter._infer_pr_effect_name("position", {}) == "Transform"
        assert converter._infer_pr_effect_name("unknown", {}) == "Transform"
