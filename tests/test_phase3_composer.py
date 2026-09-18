import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effect_composer import EffectComposer, EffectSettings, StyleTemplate


class TestEffectComposerInitialization:
    def test_initialization(self):
        ec = EffectComposer()
        assert hasattr(ec, 'templates')
        assert isinstance(ec.templates, dict)
        assert len(ec.templates) > 0


class TestTemplates:
    def test_all_templates_loaded(self):
        ec = EffectComposer()
        template_names = ec.list_templates()
        assert len(template_names) == 15
        expected_templates = [
            "cinematic", "cyberpunk", "dreamy", "horror", "vintage",
            "neon", "minimal", "drama", "warm", "cool",
            "grunge", "soft_glow", "high_energy", "noir", "pastel"
        ]
        for name in expected_templates:
            assert name in template_names

    def test_get_template(self):
        ec = EffectComposer()
        template = ec.get_template("cinematic")
        assert template is not None
        assert template.name == "cinematic"
        assert template.display_name == "电影感"
        assert template.category == "电影风格"
        assert len(template.effects) > 0
        assert isinstance(template.effects[0], EffectSettings)

    def test_get_template_not_found(self):
        ec = EffectComposer()
        template = ec.get_template("nonexistent_style")
        assert template is None


class TestCompose:
    def test_compose_effects_cinematic(self):
        ec = EffectComposer()
        result = ec.compose("cinematic", intensity=1.0, layer_name="test_layer")
        assert result["style_name"] == "cinematic"
        assert result["layer_name"] == "test_layer"
        assert result["intensity"] == 1.0
        assert len(result["effects"]) > 0
        for effect in result["effects"]:
            assert "effectName" in effect
            assert "settings" in effect

    def test_compose_with_intensity(self):
        ec = EffectComposer()
        result_low = ec.compose("cinematic", intensity=0.3)
        result_high = ec.compose("cinematic", intensity=1.5)
        assert result_low["intensity"] < result_high["intensity"]

    def test_compose_with_layer(self):
        ec = EffectComposer()
        result = ec.compose("cyberpunk", layer_name="my_custom_layer")
        assert result["layer_name"] == "my_custom_layer"

    def test_compose_invalid_style(self):
        ec = EffectComposer()
        with pytest.raises(ValueError, match="Style template '.*' not found"):
            ec.compose("nonexistent_style")

    def test_compose_intensity_clamped(self):
        ec = EffectComposer()
        template = ec.get_template("cinematic")
        min_int, max_int = template.intensity_range

        result_low = ec.compose("cinematic", intensity=min_int - 1.0)
        result_high = ec.compose("cinematic", intensity=max_int + 1.0)

        assert result_low["intensity"] == min_int
        assert result_high["intensity"] == max_int


class TestRecommendations:
    def test_recommend_by_keyword(self):
        ec = EffectComposer()
        results = ec.recommend_by_keywords(["电影", "胶片"])
        assert len(results) > 0
        assert results[0]["match_score"] > 0
        assert "name" in results[0]
        assert "display_name" in results[0]
        assert "category" in results[0]

    def test_recommend_by_keyword_empty(self):
        ec = EffectComposer()
        results = ec.recommend_by_keywords([])
        assert results == []

    def test_recommend_by_keyword_limit(self):
        ec = EffectComposer()
        results = ec.recommend_by_keywords(["暖色"], limit=3)
        assert len(results) <= 3


class TestMixStyles:
    def test_mix_styles(self):
        ec = EffectComposer()
        result = ec.mix_styles(
            ["cinematic", "warm"],
            ratios=[0.5, 0.5],
            layer_name="mixed_layer"
        )
        assert result["layer_name"] == "mixed_layer"
        assert len(result["style_names"]) == 2
        assert len(result["effects"]) > 0
        assert len(result["ratios"]) == 2
        assert sum(result["ratios"]) == pytest.approx(1.0)

    def test_mix_styles_default_ratios(self):
        ec = EffectComposer()
        result = ec.mix_styles(["cinematic", "warm", "soft_glow"])
        assert len(result["ratios"]) == 3
        assert sum(result["ratios"]) == pytest.approx(1.0)
        for r in result["ratios"]:
            assert r == pytest.approx(1.0 / 3)

    def test_mix_styles_invalid_style(self):
        ec = EffectComposer()
        with pytest.raises(ValueError, match="Style template '.*' not found"):
            ec.mix_styles(["cinematic", "nonexistent"])

    def test_mix_styles_empty(self):
        ec = EffectComposer()
        with pytest.raises(ValueError, match="At least one style name is required"):
            ec.mix_styles([])

    def test_mix_styles_mismatched_ratios(self):
        ec = EffectComposer()
        with pytest.raises(ValueError, match="Number of ratios must match number of style names"):
            ec.mix_styles(["cinematic", "warm"], ratios=[0.5, 0.3, 0.2])


class TestCategories:
    def test_list_categories(self):
        ec = EffectComposer()
        categories = ec.list_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "电影风格" in categories
        assert "色彩风格" in categories
        assert categories == sorted(categories)
