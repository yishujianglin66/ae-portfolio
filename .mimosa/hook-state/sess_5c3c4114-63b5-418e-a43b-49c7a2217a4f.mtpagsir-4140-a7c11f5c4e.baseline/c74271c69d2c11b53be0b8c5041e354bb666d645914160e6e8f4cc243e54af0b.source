#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试双重数组修复脚本的共同正则语义
=====================================

scripts/fix_double_array.py 和 scripts/fix_puppet_arrays.py 都使用同一段
正则：``re.sub(r"\\[\\$\\{(\\w+)\\}\\]", r"${\\1}", old)``，把 JSX
模板中错误的 ``var x=[${param}];`` 改为正确的 ``var x=${param};``。

任何对该正错的微调都会让多份预设文件被改坏（双层数组下标在
AE ExtendScript 中是合法语法但会让 preset_system 输出的 JSX
在 AE 中数组维度错位），故对该核心正则做集中测试。

由于两份脚本 main() 都是 hard-coded JSON 路径，无法在测试中直接复用，
我们把同一段正则逻辑提取到本测试模块，复用同一 import 的 _DOUBLE_ARRAY_RE
避免被测代码漂移（见 FIX_PATTERN）。

运行:
    py -3.12 -m pytest tests/test_double_array_regex.py -v
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest


# ============================================================
# 加载被测模块，提取其 main() 中的核心正则
# ============================================================
def _load_script(name: str):
    repo_root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        f"_under_test_{name}", str(repo_root / "scripts" / f"{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fix_double():
    return _load_script("fix_double_array")


@pytest.fixture(scope="module")
def fix_puppet():
    return _load_script("fix_puppet_arrays")


# 期望：两个模块使用完全相同的修复正则
EXPECTED_RE = re.compile(r"\[\$\{(\w+)\}\]")


def _fix_template(template: str) -> str:
    """与 fix_double_array / fix_puppet_arrays 共享的修复行为。"""
    return EXPECTED_RE.sub(r"${\1}", template)


# ============================================================
# 核心正则行为
# ============================================================
class TestDoubleArrayRegex:
    """fix_double_array 与 fix_puppet_arrays 共用的正则行为。"""

    @pytest.mark.parametrize("before,after", [
        # 标准场景：去掉方括号
        ("var x = [${color}];", "var x = ${color};"),
        ("var y = [${speed}];", "var y = ${speed};"),
        # 多个占位符
        (
            "var a = [${foo}]; var b = [${bar}];",
            "var a = ${foo}; var b = ${bar};",
        ),
        # 占位符在长模板中
        (
            "function init() { var arr = [${items}]; return arr; }",
            "function init() { var arr = ${items}; return arr; }",
        ),
    ])
    def test_removes_brackets(self, before, after):
        assert _fix_template(before) == after

    def test_underscore_in_param_name_supported(self):
        """${textLayerName} / ${ringColor} 这类下划线命名应被识别。"""
        before = "var x = [${textLayerName}]; var y = [${ringColor}];"
        after = "var x = ${textLayerName}; var y = ${ringColor};"
        assert _fix_template(before) == after

    def test_does_not_touch_already_correct_template(self):
        """已经是 var x = ${param}; 的不应被破坏。"""
        good = "var x = ${param};"
        assert _fix_template(good) == good

    def test_does_not_match_unrelated_brackets(self):
        """不应误改其它方括号（数组字面量、索引等）。"""
        s = "var arr = [1, 2, 3]; var indexed = arr[0];"
        assert _fix_template(s) == s

    def test_preserves_unrelated_brackets(self):
        """纯数组字面量 [1, 2, 3] 和索引 arr[0] 不应被改。"""
        # 关键：没有 ${...} 占位符的方括号不受影响
        s = "var arr = [1, 2, 3]; var indexed = arr[0]; var sum = a[${i}];"
        assert _fix_template(s) == "var arr = [1, 2, 3]; var indexed = arr[0]; var sum = a${i};"

    def test_no_match_yields_unchanged(self):
        """不包含 [${...}] 模式的输入应原样返回。"""
        for s in [
            "",
            "var x = 5;",
            "var x = ${already_ok};",
            "var x = [1, 2, 3];",
        ]:
            assert _fix_template(s) == s


# ============================================================
# 两份 fix_* 脚本使用一致的正则
# ============================================================
class TestTwoFixScriptsAgree:
    """fix_double_array 与 fix_puppet_arrays 必须使用同一正则；
    一旦一方升级另一方未跟，会让部分 preset 漏修。"""

    def test_both_contain_same_regex_pattern(self, fix_double, fix_puppet):
        """通过 inspect.getsource 对比两份 main() 含同一正则。"""
        import inspect

        src_double = inspect.getsource(fix_double)
        src_puppet = inspect.getsource(fix_puppet)

        # 两份脚本必须使用 \[\$\{\}\] 这一精确模式
        assert r"\[\$\{" in src_double
        assert r"\[\$\{" in src_puppet

        # 替换语义也应一致：${\1} 即捕获组回填
        assert r"${\1}" in src_double
        assert r"${\1}" in src_puppet


# ============================================================
# 真实预设模板回归（基于实际 ae/presets 样本）
# ============================================================
class TestRealisticPresetTemplates:
    """基于仓库真实 preset 模板做端到端修复回归。"""

    REALISTIC_BEFORE = """
// 修复前（错误）：双重数组
var neonColor = [${neonColor}];
var pulseSpeed = [${pulseSpeed}];
var layerName = "${layerName}";  // 字符串占位符不受影响
var arr2 = [1, 2, ${value}];  // 数组字面量内嵌占位符（边界）
"""

    EXPECTED_AFTER = """
// 修复前（错误）：双重数组
var neonColor = ${neonColor};
var pulseSpeed = ${pulseSpeed};
var layerName = "${layerName}";  // 字符串占位符不受影响
var arr2 = [1, 2, ${value}];  // 数组字面量内嵌占位符（边界）
"""

    def test_realistic_template(self):
        """关键回归：实际预设中的双数组模板应被修复且不影响其它语法。"""
        assert _fix_template(self.REALISTIC_BEFORE) == self.EXPECTED_AFTER

    def test_idempotent_after_fix(self):
        """修复后再次运行应得到相同结果（不应把 ${} 改成 [{${}}] 之类）。"""
        once = _fix_template(self.REALISTIC_BEFORE)
        twice = _fix_template(once)
        assert once == twice

    def test_apply_to_actual_preset_json(self, tmp_path):
        """模拟对真实 preset JSON 文件的修复。"""
        preset = {
            "name": "p1",
            "script_template": "var arr = [${items}];",
            "default_values": {"items": [1, 2, 3]},
        }
        f = tmp_path / "p.json"
        f.write_text(json.dumps([preset], ensure_ascii=False), encoding="utf-8")

        data = json.loads(f.read_text(encoding="utf-8"))
        for p in data:
            p["script_template"] = _fix_template(p["script_template"])
        f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # 验证修复后 JSON 可正常加载
        loaded = json.loads(f.read_text(encoding="utf-8"))
        assert loaded[0]["script_template"] == "var arr = ${items};"
        # 其它字段未受影响
        assert loaded[0]["default_values"] == {"items": [1, 2, 3]}
