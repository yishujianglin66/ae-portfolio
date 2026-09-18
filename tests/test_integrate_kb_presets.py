#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 scripts/integrate_kb_presets.py 的核心契约
================================================

把知识库提取的现代风格预设转换为标准 JSON 格式时，
参数类型 / 元数据推断 (min/max/description) 的逻辑直接决定
后续 PresetSystem 能否正常加载。覆盖 0 测、且属于"解析 / 数据验证"
关键路径。

覆盖的回归场景：
1. _infer_param_type —— Python 类型与字符串数字的双重识别
2. _infer_param_meta —— description / min / max 推断（含 desc_map 与 range_map）
3. convert_kb_preset_to_standard —— 端到端转换
   - 清理无效参数名 (------, "")
   - 数值字符串转 number
   - subcategory 推断 (kt_/cp_/ci_/sm_)
   - 完整输出字段校验
4. 边界：未知 key、未列出 range、含负号字符串

运行:
    py -3.12 -m pytest tests/test_integrate_kb_presets.py -v
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


# ============================================================
# 加载被测模块
# ============================================================
def _load_integrate_kb_presets():
    """动态加载 scripts/integrate_kb_presets.py（隔离 sys.path 副作用）。"""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "integrate_kb_presets.py"
    spec = importlib.util.spec_from_file_location(
        "_integrate_kb_presets_under_test", str(script_path)
    )
    assert spec and spec.loader, f"无法加载 {script_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ikp():
    return _load_integrate_kb_presets()


# ============================================================
# _infer_param_type —— 基础类型推断
# ============================================================
class TestInferParamType:
    """类型推断：必须覆盖 5 种 Python 原生类型 + 数字字符串。"""

    @pytest.mark.parametrize("value,expected", [
        (True, "boolean"),
        (False, "boolean"),
        (42, "integer"),
        (-1, "integer"),
        (0, "integer"),
        (3.14, "number"),
        (0.0, "number"),
        ([1, 2, 3], "array"),
        ([], "array"),
        ("123", "number"),
        ("1.5", "number"),
        ("-0.5", "number"),
        ("hello", "string"),
        ("", "string"),
    ])
    def test_type_inference(self, ikp, value, expected):
        """关键：数字字符串（含负数/小数）必须归为 number，
        否则 preset_system.validate_params 拿不到 min/max 校验能力。"""
        assert ikp._infer_param_type("anyKey", value) == expected

    def test_double_dot_numeric_string_is_number(self, ikp):
        """已记录的行为：'3.14.15' 这种带两个小数点的字符串
        会被识别为 number（因 .replace('.', '').isdigit() 通过）。

        这是该函数 over-permissive 行为，刻意保留以向后兼容
        知识库解析过程中的脏数据——不应在此 PR 中修复。
        """
        # 文档化当前行为，防止未来误改
        assert ikp._infer_param_type("anyKey", "3.14.15") == "number"

    def test_bool_not_misidentified_as_int(self, ikp):
        """True/False 在 Python 里是 int 子类——必须显式优先匹配 boolean。

        若该顺序写反，所有 boolean 都会被识别为 integer，
        validate_params 的 min/max 校验就会作用于 True/False。
        """
        assert ikp._infer_param_type("flag", True) == "boolean"
        assert ikp._infer_param_type("flag", False) == "boolean"


# ============================================================
# _infer_param_meta —— description / min / max
# ============================================================
class TestInferParamMeta:
    """元数据推断：description 与 range_map 缺一不可。"""

    def test_returns_full_meta_for_known_key(self, ikp):
        """已知 key（fallHeight）应同时返回 type/description/min/max。"""
        meta = ikp._infer_param_meta("fallHeight", 200, "p1")
        assert meta["type"] == "integer"
        assert meta["description"] == "下落距离 (px)"
        assert meta["min"] == 50
        assert meta["max"] == 1000

    def test_known_key_without_range_skips_min_max(self, ikp):
        """textLayerName 在 desc_map 里但不在 range_map 里——只填 description。"""
        meta = ikp._infer_param_meta("textLayerName", "Layer1", "p1")
        assert meta["type"] == "string"
        assert meta["description"] == "目标文字图层名"
        assert "min" not in meta
        assert "max" not in meta

    def test_unknown_key_uses_key_as_description(self, ikp):
        """未知 key：description 退回 key 本身（不抛错）。"""
        meta = ikp._infer_param_meta("totally_made_up_param", 5, "p1")
        assert meta["description"] == "totally_made_up_param"
        assert "min" not in meta

    def test_range_keys_have_correct_min_lt_max(self, ikp):
        """data integrity: range_map 中所有 range 都应 min < max。"""
        # 通过重复调用一些已知 key 触发范围
        for key, expected_range in [
            ("bpm", (60, 200)),
            ("shineAngle", (0, 360)),
            ("bounceScale", (110, 200)),
            ("yPosition", (0, 1080)),
        ]:
            meta = ikp._infer_param_meta(key, 0, "p1")
            assert meta["min"] == expected_range[0]
            assert meta["max"] == expected_range[1]
            assert meta["min"] < meta["max"]

    def test_color_keys_marked_with_bracket_notation(self, ikp):
        """所有颜色 key 描述应包含 '[R,G,B]' 以提示用户输入格式。"""
        for color_key in ("neonColor", "holoColor", "matrixColor", "metalColor", "rayColor", "flareColor"):
            meta = ikp._infer_param_meta(color_key, [0, 0, 0], "p1")
            assert "R,G,B" in meta["description"], (
                f"{color_key} 描述应包含 [R,G,B] 格式提示"
            )


# ============================================================
# convert_kb_preset_to_standard —— 端到端
# ============================================================
class TestConvertKbPresetToStandard:
    """标准格式转换。"""

    def _kb_preset(self, **overrides) -> dict:
        base = {
            "name": "kt_kinetic_demo",
            "preset_id": "kt_kinetic_demo",
            "category": "text_animation",
            "description": "测试预设",
            "tags": ["动感", "kinetic"],
            "parameters": {
                "textLayerName": "Layer1",
                "duration": 2.0,
            },
            "script_template": "// ${textLayerName}",
        }
        base.update(overrides)
        return base

    def test_basic_structure(self, ikp):
        """输出必须包含所有必需字段。"""
        out = ikp.convert_kb_preset_to_standard(self._kb_preset())
        for key in (
            "name", "category", "subcategory", "description", "tags",
            "parameters", "default_values", "script_template", "compatibility",
        ):
            assert key in out, f"输出缺少字段 {key}"

    def test_drops_invalid_param_keys(self, ikp):
        """'------' 和 '' 是从知识库 Markdown 解析时遗留的占位符，
        必须从 parameters / default_values 双重清理。"""
        kb = self._kb_preset(parameters={
            "textLayerName": "L1",
            "------": "skip me",
            "": "skip me too",
            "duration": 1.5,
        })
        out = ikp.convert_kb_preset_to_standard(kb)
        assert "------" not in out["parameters"]
        assert "" not in out["parameters"]
        assert "------" not in out["default_values"]
        assert "" not in out["default_values"]
        # 正常字段保留
        assert "textLayerName" in out["parameters"]
        assert "duration" in out["parameters"]

    def test_numeric_strings_coerced_in_default_values(self, ikp):
        """'2.5' 应被识别为 float，'30' 为 int，普通字符串保留。"""
        kb = self._kb_preset(parameters={
            "duration": "2.5",
            "frame": "30",
            "label": "TITLE",
        })
        out = ikp.convert_kb_preset_to_standard(kb)
        assert out["default_values"]["duration"] == 2.5
        assert isinstance(out["default_values"]["duration"], float)
        assert out["default_values"]["frame"] == 30
        assert isinstance(out["default_values"]["frame"], int)
        assert out["default_values"]["label"] == "TITLE"

    def test_list_values_pass_through(self, ikp):
        """数组值（如颜色 [0.1, 0.5, 0.9]）保持为 list。"""
        kb = self._kb_preset(parameters={"neonColor": [0.1, 0.5, 0.9]})
        out = ikp.convert_kb_preset_to_standard(kb)
        assert out["default_values"]["neonColor"] == [0.1, 0.5, 0.9]

    def test_subcategory_inferred_from_preset_id(self, ikp):
        """subcategory 根据 preset_id 前缀推断——驱动 PresetSystem 分类展示。"""
        cases = [
            ("kt_abc", "kinetic_typography"),
            ("cp_xyz", "cyberpunk"),
            ("ci_holo", "cinematic"),
            ("sm_tiktok", "social_media"),
            ("random_id", "general"),  # 未知前缀回退
        ]
        for preset_id, expected_sub in cases:
            kb = self._kb_preset(preset_id=preset_id, name=preset_id)
            out = ikp.convert_kb_preset_to_standard(kb)
            assert out["subcategory"] == expected_sub, (
                f"preset_id={preset_id} 应映射到 {expected_sub}"
            )

    def test_compatibility_lists_ae_versions(self, ikp):
        """compatibility 字段必须列出支持的 AE 版本（与 PresetSystem 加载兼容）。"""
        out = ikp.convert_kb_preset_to_standard(self._kb_preset())
        assert "ae" in out["compatibility"]
        assert "2024" in out["compatibility"]["ae"]
        assert "2025" in out["compatibility"]["ae"]
        assert "platform" in out["compatibility"]

    def test_parameters_meta_built_for_each_key(self, ikp):
        """parameters 字典的每个 value 都必须包含 type 字段。"""
        kb = self._kb_preset(parameters={
            "duration": 2.0,
            "textLayerName": "L1",
            "freq": 8,
        })
        out = ikp.convert_kb_preset_to_standard(kb)
        for key in ("duration", "textLayerName", "freq"):
            assert "type" in out["parameters"][key], f"{key} 缺 type"
        assert out["parameters"]["duration"]["type"] == "number"
        assert out["parameters"]["freq"]["type"] == "integer"
        assert out["parameters"]["textLayerName"]["type"] == "string"

    def test_preset_name_preserved(self, ikp):
        out = ikp.convert_kb_preset_to_standard(self._kb_preset(name="my_preset"))
        assert out["name"] == "my_preset"

    def test_no_param_keys_at_all_yields_empty_dicts(self, ikp):
        """防御：空 parameters 不应导致异常。"""
        kb = self._kb_preset(parameters={})
        out = ikp.convert_kb_preset_to_standard(kb)
        assert out["parameters"] == {}
        assert out["default_values"] == {}

    def test_negative_numeric_string(self, ikp):
        """'-0.5' 这类带负号的数字串应被识别为 float。"""
        kb = self._kb_preset(parameters={"offset": "-0.5"})
        out = ikp.convert_kb_preset_to_standard(kb)
        assert out["default_values"]["offset"] == -0.5
        assert out["parameters"]["offset"]["type"] == "number"
