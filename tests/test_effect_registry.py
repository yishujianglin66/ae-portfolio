"""
test_effect_registry.py - 效果注册表单元测试
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effect_registry import (
    EFFECT_DISPLAY_NAMES,
    KEYWORD_TO_EFFECT_MAP,
    get_all_effect_keywords,
    get_effect_matchname,
)


class TestEffectRegistryData:
    """注册表数据完整性测试。"""

    def test_keyword_map_not_empty(self):
        assert len(KEYWORD_TO_EFFECT_MAP) > 0

    def test_keyword_map_minimum_size(self):
        """至少覆盖 9 类效果中的常见关键词。"""
        assert len(KEYWORD_TO_EFFECT_MAP) >= 20

    def test_display_names_not_empty(self):
        assert len(EFFECT_DISPLAY_NAMES) > 0

    def test_all_matchnames_have_display(self):
        """所有 matchName 值都应有显示名映射。"""
        matchnames = set(KEYWORD_TO_EFFECT_MAP.values())
        for mn in matchnames:
            assert mn in EFFECT_DISPLAY_NAMES, f"{mn} 缺少显示名"

    def test_no_empty_values(self):
        for kw, mn in KEYWORD_TO_EFFECT_MAP.items():
            assert kw, "关键词不能为空"
            assert mn, "matchName 不能为空"
            assert isinstance(kw, str)
            assert isinstance(mn, str)


class TestGetEffectMatchname:
    """get_effect_matchname 函数测试。"""

    def test_chinese_keyword(self):
        assert get_effect_matchname("发光") == "ADBE Glo2"

    def test_english_keyword(self):
        assert get_effect_matchname("glow") == "ADBE Glo2"

    def test_case_insensitive_lower(self):
        assert get_effect_matchname("blur") == "ADBE Gaussian Blur 2"

    def test_case_insensitive_upper(self):
        assert get_effect_matchname("BLUR") == "ADBE Gaussian Blur 2"

    def test_case_insensitive_mixed(self):
        assert get_effect_matchname("Glow") == "ADBE Glo2"

    def test_unknown_keyword_returns_empty(self):
        assert get_effect_matchname("不存在的效果") == ""

    def test_empty_string_returns_empty(self):
        assert get_effect_matchname("") == ""

    def test_chinese_keyword_blur(self):
        assert get_effect_matchname("模糊") == "ADBE Gaussian Blur 2"

    def test_particle_keyword(self):
        assert get_effect_matchname("粒子") == "ADBE Particle Playground"

    def test_noise_keyword(self):
        assert get_effect_matchname("噪波") == "ADBE Fractal Noise"


class TestGetAllEffectKeywords:
    """get_all_effect_keywords 函数测试。"""

    def test_returns_list(self):
        result = get_all_effect_keywords()
        assert isinstance(result, list)

    def test_length_matches(self):
        result = get_all_effect_keywords()
        assert len(result) == len(KEYWORD_TO_EFFECT_MAP)

    def test_all_strings(self):
        result = get_all_effect_keywords()
        for kw in result:
            assert isinstance(kw, str)


class TestBackwardCompatibility:
    """向后兼容测试（parameter_optimizer 从 effect_registry 导入）。"""

    def test_parameter_optimizer_imports_map(self):
        """parameter_optimizer 应能从 effect_registry 导入 KEYWORD_TO_EFFECT_MAP。"""
        from parameter_optimizer import KEYWORD_TO_EFFECT_MAP as PO_MAP
        assert PO_MAP is KEYWORD_TO_EFFECT_MAP

    def test_parameter_optimizer_resolve_works(self):
        """ParameterOptimizer 的 _resolve_effect_name 应正常工作。"""
        from parameter_optimizer import ParameterContext, ParameterOptimizer
        optimizer = ParameterOptimizer()
        ctx = ParameterContext(effect_name="发光", intensity=0.5)
        result = optimizer.optimize(ctx)
        assert result.effect_name == "ADBE Glo2"
        assert result.confidence > 0
