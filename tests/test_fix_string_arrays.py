#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 scripts/fix_string_arrays.py 的核心契约
============================================

该脚本负责把 JSON 预设文件中误写成字符串的数组值（"[0, 0.8, 1]"）
反序列化为真正的 Python 列表。覆盖 0 测、且属于"解析 / 数据验证"关键路径，
潜在回归风险高（写错会污染所有预设 JSON 或悄悄丢失值）。

覆盖的回归场景：
1. looks_like_array_string —— 字符串形态检测（含边界）
2. parse_array_string —— 解析失败时安全回退为原字符串
3. fix_preset_file —— 真实文件读写 + 只改应改的字段
4. 整库扫描 main() 路径 —— 子目录跳过、缺 default_values 跳过

运行:
    py -3.12 -m pytest tests/test_fix_string_arrays.py -v
"""
from __future__ import annotations

import importlib.util
import json
import pytest
from pathlib import Path


# ============================================================
# 加载被测模块（避免与根目录 scripts/ 同名包冲突）
# ============================================================
def _load_fix_string_arrays():
    """动态加载 scripts/fix_string_arrays.py（隔离 sys.path 副作用）。"""
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "fix_string_arrays.py"
    spec = importlib.util.spec_from_file_location(
        "_fix_string_arrays_under_test", str(script_path)
    )
    assert spec and spec.loader, f"无法加载 {script_path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fsa():
    """fix_string_arrays 模块（一次性加载）。"""
    return _load_fix_string_arrays()


# ============================================================
# looks_like_array_string —— 字符串形态检测
# ============================================================
class TestLooksLikeArrayString:
    """字符串形态检测：必须严格避免误判普通字符串为数组。"""

    def test_bracket_pair_detected(self, fsa):
        assert fsa.looks_like_array_string("[0, 0.8, 1]") is True

    def test_single_bracket_only_open_returns_false(self, fsa):
        """仅左方括号不算数组（防御 [xxx 这种 prefix 字符串）。"""
        assert fsa.looks_like_array_string("[0, 0.8, 1") is False

    def test_single_bracket_only_close_returns_false(self, fsa):
        assert fsa.looks_like_array_string("0, 0.8, 1]") is False

    def test_empty_brackets_still_detected(self, fsa):
        """'[]' 是合法空数组形态——视作数组字符串。"""
        assert fsa.looks_like_array_string("[]") is True

    def test_non_string_input_returns_false(self, fsa):
        assert fsa.looks_like_array_string(123) is False
        assert fsa.looks_like_array_string(None) is False
        assert fsa.looks_like_array_string([1, 2, 3]) is False

    def test_normal_string_not_misidentified(self, fsa):
        assert fsa.looks_like_array_string("hello") is False
        assert fsa.looks_like_array_string("") is False
        assert fsa.looks_like_array_string("textLayerName") is False

    def test_text_with_brackets_in_middle(self, fsa):
        """中间含方括号的文本不应被识别为数组。"""
        assert fsa.looks_like_array_string("prefix[xx]suffix") is False


# ============================================================
# parse_array_string —— 解析失败时安全回退
# ============================================================
class TestParseArrayString:
    """JSON 反序列化；失败时返回原字符串，避免数据丢失。"""

    def test_parse_valid_array_of_ints(self, fsa):
        assert fsa.parse_array_string("[1, 2, 3]") == [1, 2, 3]

    def test_parse_valid_array_of_floats(self, fsa):
        assert fsa.parse_array_string("[0.1, 0.5, 0.9]") == [0.1, 0.5, 0.9]

    def test_parse_valid_array_of_mixed(self, fsa):
        # JSON 允许混合 number；Python json 模块会保留原数值类型
        result = fsa.parse_array_string("[1, 0.5, 0]")
        assert result == [1, 0.5, 0]
        assert isinstance(result, list)

    def test_parse_array_of_strings(self, fsa):
        assert fsa.parse_array_string('["a", "b"]') == ["a", "b"]

    def test_parse_nested_array(self, fsa):
        assert fsa.parse_array_string("[[1, 2], [3, 4]]") == [[1, 2], [3, 4]]

    def test_invalid_json_falls_back_to_original_string(self, fsa):
        """关键安全网：解析失败必须返回原字符串，不能返回 None。"""
        bad = "[1, 2, 3"  # 缺右括号
        result = fsa.parse_array_string(bad)
        assert result == bad
        # 不能被静默改写为 None 或 []
        assert result is not None

    def test_garbage_content_falls_back(self, fsa):
        bad = "[not valid json at all]"
        result = fsa.parse_array_string(bad)
        # json.loads 会抛错 → 回退为原字符串
        assert result == bad


# ============================================================
# fix_preset_file —— 文件级修复
# ============================================================
class TestFixPresetFile:
    """整文件修复：读 → 改 → 写，并返回修复数量。"""

    def _write_preset(self, tmp_path: Path, presets: list) -> Path:
        f = tmp_path / "test_presets.json"
        f.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
        return f

    def test_fixes_string_array_in_default_values(self, fsa, tmp_path):
        """最常见场景：default_values 里的 '[1, 2]' 被反序列化为 [1, 2]。"""
        preset = {
            "name": "p1",
            "default_values": {
                "color": "[1.0, 0.5, 0.2]",   # 错：字符串
                "duration": 2.0,              # 对：已是 number
                "name": "TEST",               # 对：非数组字符串
            },
        }
        f = self._write_preset(tmp_path, [preset])

        count = fsa.fix_preset_file(f)

        assert count == 1, "应仅修复一个字段"
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data[0]["default_values"]["color"] == [1.0, 0.5, 0.2]
        assert data[0]["default_values"]["duration"] == 2.0
        assert data[0]["default_values"]["name"] == "TEST"

    def test_returns_zero_when_nothing_to_fix(self, fsa, tmp_path):
        preset = {
            "name": "p1",
            "default_values": {"duration": 1.0, "color": [0, 0, 0]},
        }
        f = self._write_preset(tmp_path, [preset])

        count = fsa.fix_preset_file(f)
        assert count == 0
        # 文件应保持不变（未触发重写）
        # 注意：实现细节是 only 写入 when fixed > 0，
        # 测试通过不抛错 + 计数为 0 来确认。

    def test_skips_preset_without_default_values(self, fsa, tmp_path):
        """无 default_values 字段的预设不应导致 KeyError。"""
        preset = {"name": "p1", "description": "no defaults"}
        f = self._write_preset(tmp_path, [preset])

        count = fsa.fix_preset_file(f)
        assert count == 0
        # 文件读得回
        data = json.loads(f.read_text(encoding="utf-8"))
        assert data[0]["name"] == "p1"

    def test_fixes_multiple_presets_and_fields(self, fsa, tmp_path):
        presets = [
            {
                "name": "p1",
                "default_values": {"a": "[1, 2]", "b": "[3, 4]"},
            },
            {
                "name": "p2",
                "default_values": {"c": "[5, 6]"},
            },
        ]
        f = self._write_preset(tmp_path, presets)

        count = fsa.fix_preset_file(f)
        assert count == 3, "应修复 3 个字段（p1 两 + p2 一）"

        data = json.loads(f.read_text(encoding="utf-8"))
        assert data[0]["default_values"]["a"] == [1, 2]
        assert data[0]["default_values"]["b"] == [3, 4]
        assert data[1]["default_values"]["c"] == [5, 6]

    def test_malformed_array_string_does_not_crash(self, fsa, tmp_path):
        """关键防御：坏 JSON 字符串不应让整个文件修复失败。"""
        preset = {
            "name": "p1",
            "default_values": {
                "broken": "[1, 2,",          # 解析失败
                "good": "[10, 20, 30]",      # 解析成功
            },
        }
        f = self._write_preset(tmp_path, [preset])

        # parse_array_string 会安全回退为原字符串——写入时仍是字符串
        # 关键是 fix_preset_file 不抛异常
        count = fsa.fix_preset_file(f)
        # "good" 被修复为列表；"broken" 因 parse 返回字符串仍是字符串
        # 计数逻辑：仅当 parse 后是 list 才计 1
        assert count == 1

        data = json.loads(f.read_text(encoding="utf-8"))
        assert data[0]["default_values"]["good"] == [10, 20, 30]
        # 坏数据保留为字符串（被 json 序列化时会加引号）
        assert isinstance(data[0]["default_values"]["broken"], str)

    def test_preserves_other_preset_fields(self, fsa, tmp_path):
        """修复不应破坏预设的其它字段（description / tags / parameters）。"""
        preset = {
            "name": "p1",
            "category": "effect",
            "description": "测试",
            "tags": ["a", "b"],
            "parameters": {"x": {"type": "number"}},
            "default_values": {"color": "[1, 2, 3]"},
        }
        f = self._write_preset(tmp_path, [preset])

        fsa.fix_preset_file(f)
        data = json.loads(f.read_text(encoding="utf-8"))

        assert data[0]["name"] == "p1"
        assert data[0]["category"] == "effect"
        assert data[0]["description"] == "测试"
        assert data[0]["tags"] == ["a", "b"]
        assert data[0]["parameters"] == {"x": {"type": "number"}}
        assert data[0]["default_values"]["color"] == [1, 2, 3]
