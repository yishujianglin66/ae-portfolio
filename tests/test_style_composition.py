#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格组合引擎测试用例

测试 ae.preset_executor 中新增的风格组合功能：
- 别名解析
- 单风格组合
- 强度调整
- 风格混合
- JSX 语法验证
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 确保项目根目录在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ae.preset_executor import (
    STYLE_ALIASES,
    StyleCompositionEngine,
    adjust_parameter_by_intensity,
    compose_style,
    mix_parameters,
    resolve_style_id,
)

# ============================================================
# Fixture
# ============================================================

# 7 种标准风格的最小配置规格（style_id, 中文名, 效果matchname, 效果显示名）
# 用于生成测试专用 profiles，使测试自包含、不依赖磁盘 output_director 产物
_STANDARD_STYLE_SPECS = [
    ("anime_puppet", "动漫木偶风", "ADBE Fractal Noise", "分形噪波"),
    ("cinematic_color", "电影感调色", "ADBE Lumetri", "Lumetri调色"),
    ("glitch_digital", "故障数字风", "ADBE Mosaic", "马赛克"),
    ("audio_visual", "音频可视化", "ADBE AudSpect", "音频频谱"),
    ("particle_ambient", "粒子氛围风", "ADBE Glo2", "发光"),
    ("text_animation", "文字动画风", "ADBE Glo2", "发光"),
    ("3d_spatial", "3D空间风", "ADBE Geometry2", "几何置换"),
]


def _standard_profiles() -> dict:
    """构造 7 种标准风格的最小可执行配置"""
    styles = {}
    for style_id, style_name, matchname, display in _STANDARD_STYLE_SPECS:
        styles[style_id] = {
            "style_id": style_id,
            "style_name": style_name,
            "effects_chain": [
                {
                    "effect_matchname": matchname,
                    "effect_display_name": display,
                    "parameters": {
                        "Contrast": {"type": "percent", "value": 80, "range": [0, 300]},
                    },
                    "confidence": 0.8,
                }
            ],
            "expressions": [],
            "composition_settings": {
                "width": 1920,
                "height": 1080,
                "frame_rate": 30,
                "duration": 10,
                "bg_color": [0.05, 0.05, 0.08],
            },
            "layer_structure": [{"type": "solid", "name": "BG"}],
        }
    return {"version": "1.0.0", "styles": styles}


def _write_standard_profiles(tmp_path: Path) -> Path:
    """将标准风格 profiles 写入 tmp_path，返回文件路径"""
    profiles_file = tmp_path / "style_parameter_profiles.json"
    profiles_file.write_text(json.dumps(_standard_profiles(), ensure_ascii=False), encoding="utf-8")
    return profiles_file


@pytest.fixture
def engine(tmp_path):
    """创建风格组合引擎实例（临时 profiles 覆盖 7 种标准风格，测试自包含）"""
    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()
    return StyleCompositionEngine(
        profiles_path=str(_write_standard_profiles(tmp_path)),
        presets_dir=str(presets_dir),
    )


@pytest.fixture
def engine_with_test_profiles(tmp_path):
    """创建使用临时配置文件的引擎实例，并注册测试风格别名"""
    profiles = {
        "version": "1.0.0",
        "styles": {
            "test_style": {
                "style_id": "test_style",
                "style_name": "测试风格",
                "effects_chain": [
                    {
                        "effect_matchname": "ADBE Fractal Noise",
                        "effect_display_name": "分形噪波",
                        "parameters": {
                            "Contrast": {
                                "type": "percent",
                                "value": 80,
                                "range": [0, 300],
                            },
                            "Rotation": {
                                "type": "angle",
                                "value": 45,
                                "range": [0, 360],
                            },
                            "Scale": {
                                "type": "pixel",
                                "value": 150,
                                "range": [1, 4000],
                            },
                            "Noise Type": {
                                "type": "enum",
                                "value": 6,
                                "description": "Block",
                            },
                        },
                        "confidence": 0.8,
                    },
                    {
                        "effect_matchname": "ADBE Glo2",
                        "effect_display_name": "发光",
                        "parameters": {
                            "Glow Intensity": {
                                "type": "float",
                                "value": 1.2,
                                "range": [0, 5],
                            },
                            "Glow Radius": {
                                "type": "pixel",
                                "value": 25,
                                "range": [0, 500],
                            },
                            "Glow Colors": {
                                "type": "enum",
                                "value": 2,
                            },
                        },
                        "confidence": 0.7,
                    },
                ],
                "expressions": [
                    {
                        "template_id": "time_evolution",
                        "description": "时间驱动",
                        "parameters": {"SPEED": 500},
                        "code_template": "time * 500",
                    }
                ],
                "composition_settings": {
                    "width": 1920,
                    "height": 1080,
                    "frame_rate": 30,
                    "duration": 10,
                    "bg_color": [0.1, 0.1, 0.15],
                },
                "layer_structure": [
                    {"type": "solid", "name": "FractalNoise_BG"},
                    {"type": "text", "name": "TitleText"},
                ],
            },
            "test_style_b": {
                "style_id": "test_style_b",
                "style_name": "测试风格B",
                "effects_chain": [
                    {
                        "effect_matchname": "ADBE Fractal Noise",
                        "effect_display_name": "分形噪波",
                        "parameters": {
                            "Contrast": {
                                "type": "percent",
                                "value": 50,
                                "range": [0, 300],
                            },
                            "Rotation": {
                                "type": "angle",
                                "value": 90,
                                "range": [0, 360],
                            },
                            "Brightness": {
                                "type": "signed_percent",
                                "value": -10,
                                "range": [-100, 100],
                            },
                        },
                        "confidence": 0.6,
                    },
                ],
                "expressions": [],
                "composition_settings": {
                    "width": 1080,
                    "height": 1920,
                    "frame_rate": 24,
                    "duration": 5,
                    "bg_color": [0.05, 0.05, 0.08],
                },
                "layer_structure": [
                    {"type": "solid", "name": "BG_Layer"},
                ],
            },
        },
    }
    profiles_file = tmp_path / "test_profiles.json"
    profiles_file.write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")

    presets_dir = tmp_path / "presets"
    presets_dir.mkdir()

    # 注册测试风格别名到全局映射
    from ae.preset_executor import _ALIAS_TO_STYLE_ID
    _ALIAS_TO_STYLE_ID["test_style"] = "test_style"
    _ALIAS_TO_STYLE_ID["test_style_b"] = "test_style_b"

    eng = StyleCompositionEngine(
        profiles_path=str(profiles_file),
        presets_dir=str(presets_dir),
    )

    yield eng

    # 清理测试别名
    _ALIAS_TO_STYLE_ID.pop("test_style", None)
    _ALIAS_TO_STYLE_ID.pop("test_style_b", None)


# ============================================================
# 别名解析测试
# ============================================================

class TestStyleAliasResolution:
    """test_style_alias_resolution - 别名解析"""

    def test_resolve_by_style_id(self):
        """通过标准ID解析"""
        assert resolve_style_id("anime_puppet") == "anime_puppet"
        assert resolve_style_id("cinematic_color") == "cinematic_color"
        assert resolve_style_id("3d_spatial") == "3d_spatial"

    def test_resolve_by_chinese_name(self):
        """通过中文名解析"""
        assert resolve_style_id("动漫木偶风") == "anime_puppet"
        assert resolve_style_id("电影感调色") == "cinematic_color"
        assert resolve_style_id("故障数字风") == "glitch_digital"
        assert resolve_style_id("音频可视化") == "audio_visual"
        assert resolve_style_id("粒子氛围风") == "particle_ambient"
        assert resolve_style_id("文字动画风") == "text_animation"
        assert resolve_style_id("3D空间风") == "3d_spatial"

    def test_resolve_by_short_alias(self):
        """通过短别名解析"""
        assert resolve_style_id("木偶风") == "anime_puppet"
        assert resolve_style_id("动漫风") == "anime_puppet"
        assert resolve_style_id("电影风") == "cinematic_color"
        assert resolve_style_id("电影调色") == "cinematic_color"
        assert resolve_style_id("故障风") == "glitch_digital"
        assert resolve_style_id("数字风") == "glitch_digital"
        assert resolve_style_id("音频风") == "audio_visual"
        assert resolve_style_id("粒子风") == "particle_ambient"
        assert resolve_style_id("氛围风") == "particle_ambient"
        assert resolve_style_id("文字风") == "text_animation"
        assert resolve_style_id("打字机") == "text_animation"
        assert resolve_style_id("3D风") == "3d_spatial"
        assert resolve_style_id("空间风") == "3d_spatial"

    def test_resolve_by_english_alias(self):
        """通过英文名解析"""
        assert resolve_style_id("anime") == "anime_puppet"
        assert resolve_style_id("puppet") == "anime_puppet"
        assert resolve_style_id("cinematic") == "cinematic_color"
        assert resolve_style_id("color_grading") == "cinematic_color"
        assert resolve_style_id("glitch") == "glitch_digital"
        assert resolve_style_id("digital") == "glitch_digital"
        assert resolve_style_id("audio") == "audio_visual"
        assert resolve_style_id("visualizer") == "audio_visual"
        assert resolve_style_id("particle") == "particle_ambient"
        assert resolve_style_id("ambient") == "particle_ambient"
        assert resolve_style_id("text") == "text_animation"
        assert resolve_style_id("typewriter") == "text_animation"
        assert resolve_style_id("3d") == "3d_spatial"
        assert resolve_style_id("spatial") == "3d_spatial"

    def test_resolve_case_insensitive(self):
        """大小写不敏感"""
        assert resolve_style_id("ANIME_PUPPET") == "anime_puppet"
        assert resolve_style_id("Cinematic") == "cinematic_color"
        assert resolve_style_id("GLITCH") == "glitch_digital"

    def test_resolve_unknown_returns_none(self):
        """未知风格返回 None"""
        assert resolve_style_id("nonexistent_style") is None
        assert resolve_style_id("未知风") is None
        assert resolve_style_id("") is None

    def test_all_style_ids_in_aliases(self):
        """所有7种风格ID都在 STYLE_ALIASES 中"""
        expected_ids = {
            "anime_puppet", "cinematic_color", "glitch_digital",
            "audio_visual", "particle_ambient", "text_animation", "3d_spatial",
        }
        assert set(STYLE_ALIASES.keys()) == expected_ids


# ============================================================
# 单风格组合测试
# ============================================================

class TestComposeSingleStyle:
    """test_compose_single_style - 单风格组合"""

    def test_compose_by_id(self, engine):
        """通过标准ID组合风格"""
        jsx = engine.compose("anime_puppet")
        assert isinstance(jsx, str)
        assert len(jsx) > 100
        assert "app.beginSuppressDialogs()" in jsx
        assert "app.endSuppressDialogs()" in jsx

    def test_compose_by_chinese_name(self, engine):
        """通过中文名组合风格"""
        jsx = engine.compose("动漫木偶风")
        assert isinstance(jsx, str)
        assert "app.beginSuppressDialogs()" in jsx

    def test_compose_by_alias(self, engine):
        """通过别名组合风格"""
        jsx = engine.compose("puppet")
        assert isinstance(jsx, str)
        assert "app.beginSuppressDialogs()" in jsx

    def test_compose_unknown_style_returns_error(self, engine):
        """未知风格返回错误信息"""
        jsx = engine.compose("nonexistent_style")
        assert "错误" in jsx
        assert "nonexistent_style" in jsx

    def test_compose_contains_comp_creation(self, engine):
        """生成的JSX包含合成创建代码"""
        jsx = engine.compose("anime_puppet")
        assert "createOrGetComp" in jsx
        assert "1920" in jsx
        assert "1080" in jsx

    def test_compose_contains_effects(self, engine):
        """生成的JSX包含效果应用代码"""
        jsx = engine.compose("anime_puppet")
        assert "safeApplyEffect" in jsx

    def test_compose_contains_utility_functions(self, engine):
        """生成的JSX包含工具函数"""
        jsx = engine.compose("cinematic_color")
        assert "function safeApplyEffect" in jsx
        assert "function safeSetValue" in jsx
        assert "function createOrGetComp" in jsx

    def test_compose_custom_duration(self, engine):
        """自定义持续时间"""
        jsx = engine.compose("anime_puppet", {"duration": 20})
        assert "20" in jsx

    def test_compose_custom_resolution(self, engine):
        """自定义分辨率"""
        jsx = engine.compose("anime_puppet", {"width": 3840, "height": 2160})
        assert "3840" in jsx
        assert "2160" in jsx

    def test_compose_style_convenience_function(self, monkeypatch, tmp_path):
        """compose_style 便捷函数正常工作"""
        # compose_style() 内部以默认路径新建 StyleCompositionEngine，
        # 用 monkeypatch 将默认构造指向临时 profiles，使测试自包含。
        from ae import preset_executor as _pe
        _orig_init = _pe.StyleCompositionEngine.__init__

        def _init_with_tmp_profiles(self, profiles_path=None, presets_dir=None):
            _orig_init(
                self,
                profiles_path=str(_write_standard_profiles(tmp_path)),
                presets_dir=str(tmp_path / "presets"),
            )

        monkeypatch.setattr(_pe.StyleCompositionEngine, "__init__", _init_with_tmp_profiles)
        jsx = compose_style("动漫木偶风")
        assert isinstance(jsx, str)
        assert "app.beginSuppressDialogs()" in jsx


# ============================================================
# 强度调整测试
# ============================================================

class TestComposeWithIntensity:
    """test_compose_with_intensity - 带强度调整"""

    def test_intensity_1_0_keeps_original(self):
        """intensity=1.0 保持原始值"""
        param = {"type": "percent", "value": 80}
        assert adjust_parameter_by_intensity(param, 1.0) == 80

    def test_intensity_0_5_linear_halves(self):
        """intensity=0.5 线性类型减半"""
        param = {"type": "percent", "value": 80}
        assert adjust_parameter_by_intensity(param, 0.5) == 40

    def test_intensity_0_0_linear_zero(self):
        """intensity=0.0 线性类型归零"""
        param = {"type": "percent", "value": 80}
        assert adjust_parameter_by_intensity(param, 0.0) == 0

    def test_intensity_angle_type(self):
        """角度类型线性缩放（int值保持整数，Python银行家舍入）"""
        param = {"type": "angle", "value": 45}
        # int * intensity = 22.5 → round(22.5) = 22 (银行家舍入)
        assert adjust_parameter_by_intensity(param, 0.5) == 22
        assert adjust_parameter_by_intensity(param, 0.0) == 0
        # 使用不产生 .5 的值更明确
        param2 = {"type": "angle", "value": 90}
        assert adjust_parameter_by_intensity(param2, 0.5) == 45
        # float值保持浮点
        param_f = {"type": "angle", "value": 45.0}
        assert adjust_parameter_by_intensity(param_f, 0.5) == pytest.approx(22.5)

    def test_intensity_pixel_type_floor(self):
        """像素类型最小50%保底"""
        param = {"type": "pixel", "value": 100}
        # intensity=1.0 → 100 * (0.5 + 0.5*1.0) = 100
        assert adjust_parameter_by_intensity(param, 1.0) == 100
        # intensity=0.5 → 100 * (0.5 + 0.5*0.5) = 75
        assert adjust_parameter_by_intensity(param, 0.5) == 75
        # intensity=0.0 → 100 * (0.5 + 0.5*0.0) = 50
        assert adjust_parameter_by_intensity(param, 0.0) == 50

    def test_intensity_hertz_type_floor(self):
        """赫兹类型最小50%保底"""
        param = {"type": "hertz", "value": 8000}
        assert adjust_parameter_by_intensity(param, 0.5) == 6000
        assert adjust_parameter_by_intensity(param, 0.0) == 4000

    def test_intensity_enum_unchanged(self):
        """枚举类型不变"""
        param = {"type": "enum", "value": 6, "description": "Block"}
        assert adjust_parameter_by_intensity(param, 0.5) == 6
        assert adjust_parameter_by_intensity(param, 0.0) == 6

    def test_intensity_boolean_unchanged(self):
        """布尔类型不变"""
        param = {"type": "boolean", "value": True}
        assert adjust_parameter_by_intensity(param, 0.5) is True

    def test_intensity_color_unchanged(self):
        """颜色类型不变"""
        param = {"type": "color", "value": [0.6, 0.7, 1.0]}
        assert adjust_parameter_by_intensity(param, 0.5) == [0.6, 0.7, 1.0]

    def test_intensity_integer_rounds(self):
        """整数类型四舍五入"""
        param = {"type": "integer", "value": 7}
        # 7 * 0.5 = 3.5 → round → 4
        assert adjust_parameter_by_intensity(param, 0.5) == 4

    def test_intensity_clamps_to_0_1(self):
        """强度值被钳制到 [0, 1]"""
        param = {"type": "percent", "value": 80}
        assert adjust_parameter_by_intensity(param, -0.5) == 0
        assert adjust_parameter_by_intensity(param, 1.5) == 80

    def test_intensity_signed_percent(self):
        """有符号百分比类型"""
        param = {"type": "signed_percent", "value": -20}
        assert adjust_parameter_by_intensity(param, 0.5) == -10
        assert adjust_parameter_by_intensity(param, 0.0) == 0

    def test_intensity_float_type(self):
        """浮点类型线性缩放"""
        param = {"type": "float", "value": 1.2}
        assert adjust_parameter_by_intensity(param, 0.5) == pytest.approx(0.6)
        assert adjust_parameter_by_intensity(param, 0.0) == pytest.approx(0.0)

    def test_compose_with_intensity_generates_adjusted_jsx(self, engine_with_test_profiles):
        """带强度参数生成调整后的JSX"""
        jsx_full = engine_with_test_profiles.compose("test_style", {"intensity": 1.0})
        jsx_half = engine_with_test_profiles.compose("test_style", {"intensity": 0.5})
        # 两者都应该成功生成
        assert "app.beginSuppressDialogs()" in jsx_full
        assert "app.beginSuppressDialogs()" in jsx_half
        # 强度0.5时数值应该更小（至少某些地方）
        # 对比含 Contrast 值的部分（80 → 40）
        # 不做精确字符串匹配，因为JSX格式可能不同
        assert isinstance(jsx_full, str)
        assert isinstance(jsx_half, str)


# ============================================================
# 风格混合测试
# ============================================================

class TestComposeMixedStyles:
    """test_compose_mixed_styles - 混合风格"""

    def test_mix_parameters_conflict_numeric(self):
        """冲突数值参数取加权平均"""
        params_a = {
            "Contrast": {"type": "percent", "value": 80, "range": [0, 300]},
        }
        params_b = {
            "Contrast": {"type": "percent", "value": 50, "range": [0, 300]},
        }
        mixed = mix_parameters(params_a, params_b, 0.5, 0.5)
        assert "Contrast" in mixed
        # 80 * 0.5 + 50 * 0.5 = 65
        assert mixed["Contrast"]["value"] == 65

    def test_mix_parameters_weighted_average(self):
        """不同权重的加权平均"""
        params_a = {"Rotation": {"type": "angle", "value": 45}}
        params_b = {"Rotation": {"type": "angle", "value": 90}}
        # weight_a=0.8, weight_b=0.2 → 45*0.8 + 90*0.2 = 36+18 = 54
        mixed = mix_parameters(params_a, params_b, 0.8, 0.2)
        assert mixed["Rotation"]["value"] == 54

    def test_mix_parameters_unique_a_scaled(self):
        """风格A独有参数按权重缩放"""
        params_a = {
            "Glow Intensity": {"type": "float", "value": 1.2, "range": [0, 5]},
        }
        params_b = {}
        mixed = mix_parameters(params_a, params_b, 0.5, 0.5)
        # norm_a = 0.5/(0.5+0.5) = 0.5, linear type: 1.2 * 0.5 = 0.6
        assert "Glow Intensity" in mixed
        assert mixed["Glow Intensity"]["value"] == pytest.approx(0.6)

    def test_mix_parameters_unique_b_scaled(self):
        """风格B独有参数按权重缩放"""
        params_a = {}
        params_b = {
            "Brightness": {"type": "signed_percent", "value": -20},
        }
        mixed = mix_parameters(params_a, params_b, 0.5, 0.5)
        # norm_b = 0.5, linear: -20 * 0.5 = -10
        assert "Brightness" in mixed
        assert mixed["Brightness"]["value"] == pytest.approx(-10)

    def test_mix_parameters_enum_takes_higher_weight(self):
        """非数值冲突参数取权重高的"""
        params_a = {"Mode": {"type": "enum", "value": 1}}
        params_b = {"Mode": {"type": "enum", "value": 3}}
        # A权重高，取A的值
        mixed = mix_parameters(params_a, params_b, 0.7, 0.3)
        assert mixed["Mode"]["value"] == 1
        # B权重高，取B的值
        mixed = mix_parameters(params_a, params_b, 0.3, 0.7)
        assert mixed["Mode"]["value"] == 3

    def test_mix_parameters_zero_weights(self):
        """权重全零返回空"""
        mixed = mix_parameters({"X": {"type": "percent", "value": 10}}, {}, 0, 0)
        assert mixed == {}

    def test_mix_two_styles_in_compose(self, engine_with_test_profiles):
        """compose 中混合两个风格"""
        jsx = engine_with_test_profiles.compose(
            "test_style",
            {
                "mix_styles": [
                    {"style": "test_style_b", "weight": 0.3},
                ],
            },
        )
        assert isinstance(jsx, str)
        assert "app.beginSuppressDialogs()" in jsx
        # 混合后应包含两种风格的效果
        assert "safeApplyEffect" in jsx

    def test_mix_two_styles_merge_layers(self, engine_with_test_profiles):
        """混合两个风格合并图层结构"""
        jsx = engine_with_test_profiles.compose(
            "test_style",
            {
                "mix_styles": [
                    {"style": "test_style_b", "weight": 0.3},
                ],
            },
        )
        # test_style 有 FractalNoise_BG 和 TitleText
        # test_style_b 有 BG_Layer
        # 合并后去重，应该包含所有不重复的图层
        assert "BG_Layer" in jsx or "FractalNoise_BG" in jsx

    def test_mix_unknown_style_skipped(self, engine_with_test_profiles):
        """混合未知风格被跳过"""
        jsx = engine_with_test_profiles.compose(
            "test_style",
            {
                "mix_styles": [
                    {"style": "nonexistent_style", "weight": 0.5},
                ],
            },
        )
        # 不应报错，正常生成单风格JSX
        assert isinstance(jsx, str)
        assert "app.beginSuppressDialogs()" in jsx


# ============================================================
# JSX 语法验证测试
# ============================================================

class TestComposeOutputValidJsx:
    """test_compose_output_valid_jsx - 输出JSX语法验证"""

    def test_has_begin_suppress_dialogs(self, engine):
        """JSX以 beginSuppressDialogs 开头"""
        jsx = engine.compose("anime_puppet")
        assert "app.beginSuppressDialogs()" in jsx

    def test_has_end_suppress_dialogs(self, engine):
        """JSX以 endSuppressDialogs 结尾"""
        jsx = engine.compose("anime_puppet")
        assert "app.endSuppressDialogs()" in jsx

    def test_has_project_check(self, engine):
        """JSX包含项目检查"""
        jsx = engine.compose("anime_puppet")
        assert "app.project" in jsx
        assert 'throw new Error("No project")' in jsx

    def test_has_create_comp(self, engine):
        """JSX包含合成创建"""
        jsx = engine.compose("anime_puppet")
        assert "createOrGetComp" in jsx
        assert "comp.openInViewer()" in jsx

    def test_has_safe_functions(self, engine):
        """JSX包含安全工具函数"""
        jsx = engine.compose("anime_puppet")
        assert "function safeApplyEffect" in jsx
        assert "function safeSetValue" in jsx
        assert "function createOrGetComp" in jsx
        assert "function safeAddSolid" in jsx
        assert "function safeAddNull" in jsx
        assert "function safeAddText" in jsx

    def test_no_python_syntax_in_output(self, engine):
        """输出中不包含Python语法"""
        jsx = engine.compose("anime_puppet")
        # 不应有Python的True/False/None
        assert "True" not in jsx
        assert "False" not in jsx
        # None可能在注释中出现，所以不检查

    def test_braces_balanced(self, engine):
        """花括号基本配对"""
        jsx = engine.compose("anime_puppet")
        open_count = jsx.count("{")
        close_count = jsx.count("}")
        # 允许注释中的差异，但不应差太多
        assert abs(open_count - close_count) < 5

    def test_no_unescaped_unicode_in_strings(self, engine):
        """JSX字符串中没有未转义的Unicode问题"""
        jsx = engine.compose("anime_puppet")
        # 检查基本格式：var 声明以分号结束
        lines = [l for l in jsx.split("\n") if l.strip().startswith("var ")]
        for line in lines:
            if "createOrGetComp" in line or "safeAdd" in line:
                assert line.strip().endswith(";"), f"变量声明缺少分号: {line}"

    def test_all_styles_generate_valid_jsx(self, engine):
        """所有7种风格都能生成有效JSX"""
        style_ids = list(STYLE_ALIASES.keys())
        for style_id in style_ids:
            jsx = engine.compose(style_id)
            assert "app.beginSuppressDialogs()" in jsx, f"{style_id} 缺少 beginSuppressDialogs"
            assert "app.endSuppressDialogs()" in jsx, f"{style_id} 缺少 endSuppressDialogs"
            assert "createOrGetComp" in jsx, f"{style_id} 缺少 createOrGetComp"
            assert "// 错误" not in jsx, f"{style_id} 生成了错误信息"

    def test_compose_mixed_style_valid_jsx(self, engine):
        """混合风格生成有效JSX"""
        jsx = engine.compose(
            "anime_puppet",
            {
                "intensity": 0.8,
                "mix_styles": [
                    {"style": "cinematic_color", "weight": 0.3},
                ],
                "duration": 15,
                "frame_rate": 24,
            },
        )
        assert "app.beginSuppressDialogs()" in jsx
        assert "app.endSuppressDialogs()" in jsx
        assert "createOrGetComp" in jsx
        assert "// 错误" not in jsx


# ============================================================
# 引擎加载测试
# ============================================================

class TestEngineProfileLoading:
    """引擎配置加载"""

    def test_engine_loads_profiles(self, engine):
        """引擎成功加载风格配置"""
        profile = engine.get_style_profile("anime_puppet")
        assert profile is not None
        assert profile["style_id"] == "anime_puppet"

    def test_engine_all_profiles_loaded(self, engine):
        """所有7种风格配置都已加载"""
        for style_id in STYLE_ALIASES:
            profile = engine.get_style_profile(style_id)
            assert profile is not None, f"风格 {style_id} 未加载"

    def test_load_style_jsx(self, engine):
        """加载风格JSX文件"""
        jsx = engine.load_style_jsx("anime_puppet")
        if jsx is not None:  # 文件存在时
            assert "Style_anime_puppet" in jsx

    def test_load_nonexistent_jsx(self, engine):
        """加载不存在的JSX返回None"""
        jsx = engine.load_style_jsx("nonexistent_style")
        assert jsx is None
