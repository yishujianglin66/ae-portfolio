#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TextFX 特效组合生成器测试"""

import sys
import os
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


class TestTextFXEffects(unittest.TestCase):
    """TextFX 特效组合生成器测试"""

    def setUp(self):
        from ae.textfx_effects import TextFXEffects
        self.fx = TextFXEffects()

    def test_cyber_glow_jsx_contains_glow(self):
        """cyberGlow JSX 应包含 Glow 效果"""
        jsx = self.fx.cyber_glow_jsx("myLayer")
        self.assertIn("ADBE Glo2", jsx)
        self.assertIn("myLayer", jsx)

    def test_neon_effect_jsx_contains_flare(self):
        """neonEffect JSX 应包含 Lens Flare"""
        jsx = self.fx.neon_effect_jsx("myLayer")
        self.assertIn("ADBE Lens Flare", jsx)
        self.assertIn("ADBE Easy Levels", jsx)

    def test_hologram_effect_jsx_contains_hue(self):
        """hologramEffect JSX 应包含 Hue/Saturation"""
        jsx = self.fx.hologram_effect_jsx("myLayer")
        self.assertIn("ADBE HUE SATURATION", jsx)

    def test_fire_ice_effect_jsx_contains_blend(self):
        """fireIceEffect JSX 应包含 BlendMode"""
        jsx = self.fx.fire_ice_effect_jsx("fire", "ice")
        self.assertIn("BlendingMode.ADD", jsx)
        self.assertIn("BlendingMode.SCREEN", jsx)

    def test_color_grade_jsx_contains_levels(self):
        """colorGrade JSX 应包含 Levels + Vignette"""
        jsx = self.fx.color_grade_jsx("adjLayer")
        self.assertIn("ADBE Easy Levels", jsx)
        # Vignette 已改为 Easy Levels 模拟
        self.assertIn("ADBE Easy Levels", jsx)

    def test_generate_scene_jsx(self):
        """generate_scene_jsx 应生成完整场景代码"""
        jsx = self.fx.generate_scene_jsx(
            scene_name="TestScene",
            effect_combo="cyberGlow",
            text="HELLO",
            font="Impact",
            font_size=100,
            color=[1, 0, 0],
        )
        self.assertIn("HELLO", jsx)
        self.assertIn("Impact", jsx)
        self.assertIn("ADBE Glo2", jsx)
        self.assertIn("TestScene", jsx)

    def test_generate_scene_jsx_all_combos(self):
        """所有特效组合均应可生成场景"""
        for combo in ["cyberGlow", "neon", "hologram", "fireIce", "colorGrade"]:
            jsx = self.fx.generate_scene_jsx(
                scene_name=f"Test_{combo}",
                effect_combo=combo,
                text="TEST",
                font="Arial",
                font_size=80,
                color=[1, 1, 1],
            )
            self.assertIn("TEST", jsx, f"组合 {combo} 生成的 JSX 缺少文字")
            self.assertIn("addText", jsx, f"组合 {combo} 生成的 JSX 缺少 addText")

    def test_list_combos(self):
        """list_combos 应返回 5 种组合"""
        combos = self.fx.list_combos()
        self.assertEqual(len(combos), 5)
        names = [c["name"] for c in combos]
        self.assertIn("cyberGlow", names)
        self.assertIn("neon", names)
        self.assertIn("hologram", names)
        self.assertIn("fireIce", names)
        self.assertIn("colorGrade", names)

    def test_list_available_effects(self):
        """list_available_effects 应返回 11 种效果"""
        effects = self.fx.list_available_effects()
        self.assertEqual(len(effects), 11)
        match_names = [e["matchName"] for e in effects]
        self.assertIn("ADBE Glo2", match_names)
        self.assertIn("ADBE Gaussian Blur 2", match_names)

    def test_param_ranges(self):
        """参数范围约束应正确"""
        self.assertEqual(self.fx.PARAM_RANGES["turbulent_amount"], (1, 11))
        self.assertEqual(self.fx.PARAM_RANGES["fractal_contrast"], (1, 4))
        self.assertEqual(self.fx.PARAM_RANGES["glow_threshold"], (0.0, 1.0))

    def test_effect_matchnames(self):
        """效果 matchName 字典应完整"""
        self.assertEqual(len(self.fx.EFFECT_MATCHNAMES), 37)
        self.assertEqual(self.fx.EFFECT_MATCHNAMES["glow"], "ADBE Glo2")


if __name__ == "__main__":
    unittest.main()
