"""core.font_manager 单元测试 - FontManager 字体管理器核心逻辑"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.font_manager import FontManager, get_font_manager

# ============ 测试用配置数据 ============

SAMPLE_CONFIG = {
    "version": "1.7",
    "installed_count": 3038,
    "categories": {
        "cn_impact": {
            "fonts": [
                {
                    "key": "sub_cn_impact",
                    "name": "方正兰亭粗黑_GBK",
                    "postscript": "FZLanTingHeiS-GB-Heavy",
                    "color": "#FFFFFF",
                    "stroke": "#000000",
                    "stroke_w": 2.0,
                    "tag": "暴力粗黑",
                },
            ],
        },
        "en_impact": {
            "fonts": [
                {
                    "key": "sub_en_impact",
                    "name": "Impact",
                    "postscript": "Impact",
                    "color": "#00FFFF",
                    "stroke": "#000000",
                    "stroke_w": 1.5,
                    "tag": "极粗冲击",
                },
                {
                    "key": "sub_en_bebas",
                    "name": "Bebas Neue",
                    "postscript": "BebasNeueRegular",
                    "color": "#FF6600",
                    "stroke": "#111111",
                    "stroke_w": 1.0,
                    "tag": "极粗标题",
                },
            ],
        },
        "serif": {
            "fonts": [
                {
                    "key": "sub_cn_serif",
                    "name": "SourceHanSerifSC-ExtraLight",
                    "postscript": "SourceHanSerifSC-ExtraLight",
                    "color": "#E0E0E0",
                    "stroke": "#222222",
                    "stroke_w": 0.5,
                    "tag": "诗意衬线",
                },
            ],
        },
    },
    "scene_font_mapping": {
        "intro_hero": "sub_cn_impact",
        "drop_battle_cn": "sub_cn_impact",
        "build_emotion": "sub_cn_serif",
        "break_quote": "sub_cn_serif",
        "data_panel": "sub_en_impact",
    },
    "animation_recipes": {
        "bounce_in": {
            "keyframes": [
                {"t": 0.0, "scale": [0, 0], "opacity": 0},
                {"t": 0.15, "scale": [110, 110], "opacity": 100},
                {"t": 0.3, "scale": [95, 95]},
                {"t": 0.45, "scale": [100, 100]},
            ],
        },
        "kinetic_smash": {
            "keyframes": [
                {"t": 0.0, "scale": [300, 300], "opacity": 0},
                {"t": 0.08, "scale": [100, 100], "opacity": 100},
                {"t": 0.15, "x_shift": -30, "rotation": -5},
                {"t": 0.25, "x_shift": 0, "rotation": 0},
            ],
        },
        "tracking_fade": {
            "expression": "var t=time-inPoint;var d=0.5;t<d?lerp(150,0,t/d):0",
        },
    },
}


# ============ Fixtures ============


@pytest.fixture
def font_config_path(tmp_path):
    """创建临时字体配置文件"""
    config_file = tmp_path / "font_presets.json"
    config_file.write_text(json.dumps(SAMPLE_CONFIG, ensure_ascii=False), encoding="utf-8")
    return config_file


@pytest.fixture
def font_manager(font_config_path):
    """基于临时配置的 FontManager 实例"""
    return FontManager(config_path=font_config_path)


@pytest.fixture
def installed_fonts_file(tmp_path):
    """创建临时已安装字体列表"""
    fonts_file = tmp_path / "installed_fonts.txt"
    fonts_file.write_text(
        "Impact.ttf\n"
        "Bebas Neue.ttf\n"
        "FZLanTingHeiS-GB-Heavy.otf\n"
        "SourceHanSerifSC-ExtraLight.otf\n"
        "04b_30.ttf\n"
        "Consolas.ttf\n",
        encoding="utf-8",
    )
    return fonts_file


# ============ FontManager.__init__ ============


class TestFontManagerInit:
    def test_loads_config_successfully(self, font_config_path):
        fm = FontManager(config_path=font_config_path)
        assert fm._config["version"] == "1.7"
        assert fm._config["installed_count"] == 3038

    def test_raises_file_not_found_when_missing(self, tmp_path):
        missing_path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError, match="字体配置不存在"):
            FontManager(config_path=missing_path)

    def test_config_path_stored(self, font_config_path):
        fm = FontManager(config_path=font_config_path)
        assert fm._config_path == font_config_path

    def test_installed_cache_init_none(self, font_config_path):
        fm = FontManager(config_path=font_config_path)
        assert fm._installed_cache is None


# ============ FontManager 基础查询 ============


class TestFontManagerProperties:
    def test_version(self, font_manager):
        assert font_manager.version == "1.7"

    def test_installed_count(self, font_manager):
        assert font_manager.installed_count == 3038

    def test_categories(self, font_manager):
        cats = font_manager.categories()
        assert set(cats) == {"cn_impact", "en_impact", "serif"}


# ============ FontManager.get_preset ============


class TestGetPreset:
    def test_found_preset(self, font_manager):
        preset = font_manager.get_preset("sub_cn_impact")
        assert preset is not None
        assert preset["name"] == "方正兰亭粗黑_GBK"
        assert preset["tag"] == "暴力粗黑"

    def test_found_en_preset(self, font_manager):
        preset = font_manager.get_preset("sub_en_bebas")
        assert preset is not None
        assert preset["name"] == "Bebas Neue"

    def test_unknown_key_returns_none(self, font_manager):
        assert font_manager.get_preset("nonexistent_key") is None

    def test_empty_key_returns_none(self, font_manager):
        assert font_manager.get_preset("") is None


# ============ FontManager.get_scene_font ============


class TestGetSceneFont:
    def test_mapped_scene(self, font_manager):
        result = font_manager.get_scene_font("intro_hero")
        assert result is not None
        assert result["key"] == "sub_cn_impact"

    def test_serif_scene(self, font_manager):
        result = font_manager.get_scene_font("build_emotion")
        assert result is not None
        assert result["key"] == "sub_cn_serif"

    def test_unknown_scene_returns_none(self, font_manager):
        assert font_manager.get_scene_font("unknown_scene") is None

    def test_empty_scene_returns_none(self, font_manager):
        assert font_manager.get_scene_font("") is None


# ============ FontManager.list_presets ============


class TestListPresets:
    def test_all_presets(self, font_manager):
        presets = font_manager.list_presets()
        assert len(presets) == 4  # cn_impact(1) + en_impact(2) + serif(1)
        keys = {p["key"] for p in presets}
        assert keys == {"sub_cn_impact", "sub_en_impact", "sub_en_bebas", "sub_cn_serif"}

    def test_filter_by_category(self, font_manager):
        presets = font_manager.list_presets("en_impact")
        assert len(presets) == 2
        assert all(p["key"].startswith("sub_en_") for p in presets)

    def test_filter_by_single_category(self, font_manager):
        presets = font_manager.list_presets("cn_impact")
        assert len(presets) == 1
        assert presets[0]["key"] == "sub_cn_impact"

    def test_nonexistent_category_returns_empty(self, font_manager):
        presets = font_manager.list_presets("nonexistent")
        assert presets == []

    def test_none_category_returns_all(self, font_manager):
        presets = font_manager.list_presets(None)
        assert len(presets) == 4


# ============ FontManager.is_font_installed ============


class TestIsFontInstalled:
    def _make_manager_with_installed(self, font_config_path, installed_fonts_file):
        """创建使用临时已安装字体列表的 FontManager"""
        fm = FontManager(config_path=font_config_path)
        return fm

    def test_exact_name_match(self, font_config_path, installed_fonts_file):
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            assert fm.is_font_installed("Impact") is True

    def test_compact_name_match(self, font_config_path, installed_fonts_file):
        """bebasneue 应匹配 'Bebas Neue'（紧凑匹配：去空格）"""
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            assert fm.is_font_installed("bebasneue") is True

    def test_prefix_bidirectional_match(self, font_config_path, installed_fonts_file):
        """前缀双向匹配：短名前缀匹配已安装字体"""
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            # "BebasNeueRegular" 以 "bebasn" 开头，installed 中 "bebasneue" 也以 "bebasn" 开头
            assert fm.is_font_installed("BebasNeueRegular") is True

    def test_postscript_match(self, font_config_path, installed_fonts_file):
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            assert fm.is_font_installed("unknown", postscript="FZLanTingHeiS-GB-Heavy") is True

    def test_not_installed(self, font_config_path, installed_fonts_file):
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            assert fm.is_font_installed("Arial") is False

    def test_empty_installed_list(self, font_config_path, tmp_path):
        """空已安装字体列表"""
        empty_file = tmp_path / "empty_fonts.txt"
        empty_file.write_text("", encoding="utf-8")
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", empty_file):
            fm._installed_cache = None
            assert fm.is_font_installed("Impact") is False

    def test_nonexistent_installed_file(self, font_config_path, tmp_path):
        """已安装字体列表文件不存在"""
        missing = tmp_path / "missing_fonts.txt"
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", missing):
            fm._installed_cache = None
            assert fm.is_font_installed("Impact") is False

    def test_cache_reuse(self, font_config_path, installed_fonts_file):
        """第二次调用应使用缓存"""
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            fm.is_font_installed("Impact")
            cache = fm._installed_cache
            assert cache is not None
            # 第二次调用，缓存应不变
            fm.is_font_installed("Bebas Neue")
            assert fm._installed_cache is cache


# ============ FontManager.validate_all_presets ============


class TestValidateAllPresets:
    def test_validate_with_installed(self, font_config_path, installed_fonts_file):
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            results = fm.validate_all_presets()
        assert len(results) == 4
        for r in results:
            assert "key" in r
            assert "name" in r
            assert "installed" in r
            assert "tag" in r

    def test_validate_result_structure(self, font_config_path, installed_fonts_file):
        fm = FontManager(config_path=font_config_path)
        with patch("core.font_manager._INSTALLED_FONTS_LIST", installed_fonts_file):
            fm._installed_cache = None
            results = fm.validate_all_presets()
        impact_result = next(r for r in results if r["key"] == "sub_en_impact")
        assert impact_result["installed"] is True


# ============ FontManager.normalize_postscript ============


class TestNormalizePostscript:
    def test_strip_ttf(self):
        assert FontManager.normalize_postscript("MyFont.ttf") == "MyFont"

    def test_strip_otf(self):
        assert FontManager.normalize_postscript("MyFont.otf") == "MyFont"

    def test_strip_ttc(self):
        assert FontManager.normalize_postscript("MyFont.ttc") == "MyFont"

    def test_strip_fon(self):
        assert FontManager.normalize_postscript("MyFont.fon") == "MyFont"

    def test_case_insensitive_extension(self):
        assert FontManager.normalize_postscript("MyFont.TTF") == "MyFont"
        assert FontManager.normalize_postscript("MyFont.Otf") == "MyFont"

    def test_no_extension(self):
        assert FontManager.normalize_postscript("BebasNeueRegular") == "BebasNeueRegular"

    def test_strip_whitespace(self):
        assert FontManager.normalize_postscript("  MyFont  ") == "MyFont"

    def test_chinese_name_preserved(self):
        assert FontManager.normalize_postscript("方正兰亭粗黑.ttf") == "方正兰亭粗黑"

    def test_empty_string(self):
        assert FontManager.normalize_postscript("") == ""


# ============ FontManager._parse_color ============


class TestParseColor:
    def test_white(self):
        assert FontManager._parse_color("#FFFFFF") == "[1.000,1.000,1.000]"

    def test_black(self):
        assert FontManager._parse_color("#000000") == "[0.000,0.000,0.000]"

    def test_red(self):
        assert FontManager._parse_color("#FF0000") == "[1.000,0.000,0.000]"

    def test_cyan(self):
        assert FontManager._parse_color("#00FFFF") == "[0.000,1.000,1.000]"

    def test_without_hash(self):
        assert FontManager._parse_color("FF6600") == "[1.000,0.400,0.000]"

    def test_lowercase_hex(self):
        assert FontManager._parse_color("#ff6600") == "[1.000,0.400,0.000]"

    def test_invalid_returns_white(self):
        assert FontManager._parse_color("invalid") == "[1,1,1]"

    def test_empty_returns_white(self):
        assert FontManager._parse_color("") == "[1,1,1]"

    def test_partial_hex_returns_white(self):
        assert FontManager._parse_color("#FFF") == "[1,1,1]"

    def test_too_long_returns_white(self):
        assert FontManager._parse_color("#FFFFFF00") == "[1,1,1]"


# ============ FontManager._escape_jsx_str ============


class TestEscapeJsxStr:
    def test_no_escape_needed(self):
        assert FontManager._escape_jsx_str("hello") == "hello"

    def test_escape_backslash(self):
        assert FontManager._escape_jsx_str("a\\b") == "a\\\\b"

    def test_escape_double_quote(self):
        assert FontManager._escape_jsx_str('a"b') == 'a\\"b'

    def test_escape_newline(self):
        assert FontManager._escape_jsx_str("a\nb") == "a\\nb"

    def test_combined_escapes(self):
        assert FontManager._escape_jsx_str('a\\b"c\nd') == 'a\\\\b\\"c\\nd'

    def test_empty_string(self):
        assert FontManager._escape_jsx_str("") == ""

    def test_chinese_no_escape(self):
        assert FontManager._escape_jsx_str("战吼") == "战吼"


# ============ FontManager._build_anim_keyframes ============


class TestBuildAnimKeyframes:
    def test_known_recipe_bounce_in(self, font_manager):
        result = font_manager._build_anim_keyframes("bounce_in", 5.0, 10.0)
        assert "tl.scale.setValueAtTime" in result
        assert "tl.opacity.setValueAtTime" in result

    def test_known_recipe_kinetic_smash(self, font_manager):
        result = font_manager._build_anim_keyframes("kinetic_smash", 0.0, 5.0)
        assert "tl.scale.setValueAtTime" in result
        assert "tl.rotation.setValueAtTime" in result
        assert "tl.position.setValueAtTime" in result

    def test_expression_recipe(self, font_manager):
        result = font_manager._build_anim_keyframes("tracking_fade", 0.0, 5.0)
        assert "expression=" in result
        assert "lerp" in result

    def test_unknown_recipe_returns_empty(self, font_manager):
        result = font_manager._build_anim_keyframes("nonexistent_anim", 0.0, 5.0)
        assert result == ""

    def test_keyframe_time_offset(self, font_manager):
        """关键帧时间应基于 start_t 偏移"""
        result = font_manager._build_anim_keyframes("bounce_in", 9.0, 15.0)
        # bounce_in 第一个关键帧 t=0.0 → 实际时间 9.0
        assert "9.0" in result


# ============ FontManager.generate_apply_jsx ============


class TestGenerateApplyJsx:
    def test_basic_generation(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 9.0, 9.5
        )
        assert isinstance(jsx, str)
        assert len(jsx) > 0

    def test_iife_structure(self, font_manager):
        """生成结果应是 IIFE 格式"""
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 9.0, 9.5
        )
        assert jsx.startswith("(function(){")
        assert jsx.endswith("})();")

    def test_no_arrow_functions(self, font_manager):
        """ExtendScript ES3 不支持箭头函数"""
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 9.0, 9.5
        )
        assert "=>" not in jsx

    def test_no_template_literals(self, font_manager):
        """ExtendScript ES3 不支持模板字符串"""
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 9.0, 9.5
        )
        assert "`" not in jsx

    def test_contains_font_name(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 9.0, 9.5
        )
        assert "FZLanTingHeiS-GB-Heavy" in jsx

    def test_contains_text_content(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_en_impact", "BOOM", 80, 0.0, 3.0
        )
        assert "BOOM" in jsx

    def test_contains_font_size(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 120, 0.0, 3.0
        )
        assert "120" in jsx

    def test_contains_time_values(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 5.5, 8.0
        )
        assert "5.5" in jsx
        assert "8.0" in jsx

    def test_unknown_preset_raises_value_error(self, font_manager):
        with pytest.raises(ValueError, match="未找到字体预设"):
            font_manager.generate_apply_jsx("nonexistent", "战", 100, 0.0, 1.0)

    def test_special_characters_escaped(self, font_manager):
        """特殊字符应被正确转义"""
        jsx = font_manager.generate_apply_jsx(
            "sub_en_impact", 'He said "hello"\nback\\slash', 80, 0.0, 3.0
        )
        # 不应包含未转义的换行或引号
        assert '\\"' in jsx
        assert "\\n" in jsx
        assert "\\\\" in jsx

    def test_color_applied(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_en_impact", "X", 80, 0.0, 3.0
        )
        # sub_en_impact color=#00FFFF → [0.000,1.000,1.000]
        assert "[0.000,1.000,1.000]" in jsx

    def test_stroke_applied(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_en_impact", "X", 80, 0.0, 3.0
        )
        # stroke=#000000 → [0.000,0.000,0.000]
        assert "[0.000,0.000,0.000]" in jsx

    def test_animation_keyframes_included(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 0.0, 5.0, anim="bounce_in"
        )
        assert "tl.scale.setValueAtTime" in jsx

    def test_custom_y_pos(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 0.0, 3.0, y_pos=500.0
        )
        assert "525" in jsx  # y_pos + 25 = 525

    def test_custom_x_center(self, font_manager):
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "战", 100, 0.0, 3.0, x_center=960.0
        )
        assert "960" in jsx


# ============ FontManager.get_styling_guide ============


class TestGetStylingGuide:
    def test_returns_dict(self, font_manager):
        guide = font_manager.get_styling_guide()
        assert isinstance(guide, dict)

    def test_required_keys(self, font_manager):
        guide = font_manager.get_styling_guide()
        expected_keys = {"scene_to_font", "font_pairing", "color_rule", "tracking_rule", "es3_pitfall"}
        assert set(guide.keys()) == expected_keys

    def test_values_are_strings(self, font_manager):
        guide = font_manager.get_styling_guide()
        for v in guide.values():
            assert isinstance(v, str)
            assert len(v) > 0

    def test_es3_pitfall_content(self, font_manager):
        guide = font_manager.get_styling_guide()
        assert "ES3" in guide["es3_pitfall"]
        assert "PostScript" in guide["es3_pitfall"]


# ============ get_font_manager 单例 ============


class TestGetFontManager:
    def test_singleton_behavior(self):
        """get_font_manager 应返回单例（需能找到真实配置或使用 mock）"""
        # 由于单例使用模块全局变量，需重置
        import core.font_manager as fm_mod
        original = fm_mod._default_manager
        try:
            fm_mod._default_manager = None
            # 使用 mock 避免依赖真实配置文件
            with patch.object(FontManager, "__init__", lambda self, **kw: None):
                m1 = get_font_manager()
                m2 = get_font_manager()
                assert m1 is m2
        finally:
            fm_mod._default_manager = original

    def test_singleton_reset_on_none(self):
        import core.font_manager as fm_mod
        original = fm_mod._default_manager
        try:
            fm_mod._default_manager = None
            # 第一次调用创建实例
            with patch.object(FontManager, "__init__", lambda self, **kw: None):
                m = get_font_manager()
                assert fm_mod._default_manager is m
        finally:
            fm_mod._default_manager = original


# ============ 边界与集成测试 ============


class TestEdgeCases:
    def test_config_with_empty_categories(self, tmp_path):
        """空分类配置"""
        config = {"version": "1.0", "categories": {}}
        config_file = tmp_path / "empty_cats.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        fm = FontManager(config_path=config_file)
        assert fm.list_presets() == []
        assert fm.get_preset("any_key") is None
        assert fm.categories() == []

    def test_config_with_no_scene_mapping(self, tmp_path):
        """无场景映射配置"""
        config = {"version": "1.0", "categories": {}, "scene_font_mapping": {}}
        config_file = tmp_path / "no_mapping.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        fm = FontManager(config_path=config_file)
        assert fm.get_scene_font("intro_hero") is None

    def test_config_missing_optional_fields(self, tmp_path):
        """缺少可选字段的预设"""
        config = {
            "categories": {
                "test": {
                    "fonts": [
                        {"key": "minimal", "name": "MinFont", "postscript": "MinFontPS"},
                    ],
                },
            },
        }
        config_file = tmp_path / "minimal.json"
        config_file.write_text(json.dumps(config), encoding="utf-8")
        fm = FontManager(config_path=config_file)
        # color/stroke 缺失时应回退到默认值 #FFFFFF / #000000
        jsx = fm.generate_apply_jsx("minimal", "test", 50, 0.0, 1.0)
        assert "[1.000,1.000,1.000]" in jsx  # 默认白色

    def test_normalize_postscript_preserves_dot_in_name(self):
        """文件名中间有点号但不是扩展名"""
        # 只有末尾的 .ttf/.otf 等才会被去除
        assert FontManager.normalize_postscript("04b_30.ttf") == "04b_30"

    def test_parse_color_mixed_case(self):
        result = FontManager._parse_color("#AaBbCc")
        assert result == "[0.667,0.733,0.800]"

    def test_escape_jsx_multiple_backslashes(self):
        assert FontManager._escape_jsx_str("a\\\\b") == "a\\\\\\\\b"

    def test_generate_jsx_with_expression_anim(self, font_manager):
        """使用 expression 动画配方生成 JSX"""
        jsx = font_manager.generate_apply_jsx(
            "sub_cn_impact", "X", 80, 0.0, 5.0, anim="tracking_fade"
        )
        assert "expression=" in jsx
        # ES3 兼容性：不应有箭头函数
        assert "=>" not in jsx
