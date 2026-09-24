# -*- coding: utf-8 -*-
"""执行阶段的 JSX 构造器特征化测试（2026-09-20）。

背景：覆盖率快照里 `pipeline/stages/execution.py` 是 **0.00%**（628 语句），
而它包含两个**纯字符串构造器** —— `_build_jsx_for_command` / `_build_jsx_for_op`
—— 把外部参数拼进要在 AE 里 eval 的 ExtendScript。这类代码的安全性是真实的：
参数里一个未转义的引号就能改写脚本内容（JSX 注入），而这层此前零测试。

本文件锁住：转义正确性（引号/反斜杠/换行/Unicode）、合成定位前缀的双分支、
各命令的必需片段、未知命令返回空、以及 `_send_atom_script` 的 eval 包裹方式。
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from pipeline.stages.execution import ExecutionStage  # noqa: E402


# ---------------------------------------------------------------------------
# 转义（安全核心）
# ---------------------------------------------------------------------------

class TestEscaping:
    @pytest.mark.parametrize("evil", [
        'name"); app.project.close(); ("',          # 引号注入
        "back\\slash",                               # 反斜杠
        "line\nbreak",                               # 换行
        "中文图层名",                                 # Unicode 正常通过
        "tab\there",
    ])
    def test_text_layer_name_is_jsx_escaped(self, evil):
        """参数必须经 JSON 转义后插入，原始引号不得出现在字面量之外。

        判据：注入串被 `json.dumps` 转义后，脚本里出现的必须是转义形式
        （`\\"` / `\\\\` / `\\n`），而不是裸引号。
        """
        jsx = ExecutionStage._build_jsx_for_command("createTextLayer",
                                                    {"text": evil})
        assert json.dumps(evil) in jsx, "未使用 JSON 转义插入参数"
        # 注入串原文不得整体出现在脚本里（原文含未转义引号）
        if '"' in evil:
            assert evil not in jsx

    def test_composition_name_escaped(self):
        jsx = ExecutionStage._build_jsx_for_command(
            "createComposition", {"name": 'a"b'})
        assert json.dumps('a"b') in jsx

    def test_footage_path_backslashes_normalized(self):
        """Windows 路径统一成正斜杠（ExtendScript File() 的兼容写法）。

        断言用**同一字面量的 json 转义形式**比对 —— 直接查原文会被
        ensure_ascii 的 \\uXXXX 转义干扰（本轮踩过）。
        """
        jsx = ExecutionStage._build_jsx_for_command(
            "importFootage", {"path": r"D:\AE-Work\素材\a.mp4"})
        assert json.dumps("D:/AE-Work/素材/a.mp4") in jsx, "反斜杠未被规范化"
        assert json.dumps(r"D:\AE-Work\素材\a.mp4") not in jsx, "原始反斜杠路径不应出现"


# ---------------------------------------------------------------------------
# 合成定位前缀（compName 双分支）
# ---------------------------------------------------------------------------

class TestCompPrefix:
    def test_without_comp_name_uses_active_item(self):
        jsx = ExecutionStage._build_jsx_for_command("createShapeLayer", {})
        assert "app.project.activeItem" in jsx
        assert "__gc(" not in jsx

    def test_with_comp_name_uses_named_lookup(self):
        """按名查找避免 activeItem 被导入素材劫持（导入会改变 activeItem）。"""
        jsx = ExecutionStage._build_jsx_for_command(
            "createShapeLayer", {"compName": "主合成"})
        assert "function __gc(n)" in jsx
        assert json.dumps("主合成") in jsx
        assert "activeItem" not in jsx

    def test_named_lookup_guards_non_comp(self):
        jsx = ExecutionStage._build_jsx_for_command(
            "createTextLayer", {"text": "t", "compName": "C"})
        assert 'if(!c||!(c instanceof CompItem))' in jsx


# ---------------------------------------------------------------------------
# 各命令的必要片段
# ---------------------------------------------------------------------------

class TestCommandBuilders:
    def test_create_composition_contains_params(self):
        jsx = ExecutionStage._build_jsx_for_command(
            "createComposition",
            {"name": "C1", "width": 1280, "height": 720,
             "frameRate": 24, "duration": 3})
        assert "items.addComp(" in jsx
        assert "1280" in jsx and "720" in jsx and "24" in jsx and "3" in jsx
        assert "success:true" in jsx and "catch(e)" in jsx

    def test_import_footage_has_existence_check(self):
        jsx = ExecutionStage._build_jsx_for_command(
            "importFootage", {"path": "C:/a.mp4"})
        assert "new File(" in jsx and "!f.exists" in jsx and "importFile(" in jsx

    def test_text_and_shape_layers_add_layers(self):
        assert ".layers.addText(" in ExecutionStage._build_jsx_for_command(
            "createTextLayer", {"text": "hi"})
        assert ".layers.addShape(" in ExecutionStage._build_jsx_for_command(
            "createShapeLayer", {})

    def test_text_layer_defaults_name_to_text(self):
        jsx = ExecutionStage._build_jsx_for_command("createTextLayer",
                                                    {"text": "标题"})
        assert jsx.count(json.dumps("标题")) >= 2      # text 与 name 都用它

    def test_unknown_command_returns_empty(self):
        assert ExecutionStage._build_jsx_for_command("no_such_cmd", {}) == ""

    def test_every_built_script_is_iife_with_try_catch(self):
        """所有命令脚本都是 IIFE + try/catch，保证异常被转成 JSON 结果。"""
        for cmd in ("createComposition", "importFootage", "createTextLayer",
                    "createShapeLayer"):
            jsx = ExecutionStage._build_jsx_for_command(cmd, {})
            assert jsx.startswith("(function(){try{"), cmd
            assert jsx.endswith("})();"), cmd
            assert "catch(e)" in jsx, cmd


# ---------------------------------------------------------------------------
# _build_jsx_for_op（未映射命令的兜底构造）
# ---------------------------------------------------------------------------

class TestOpBuilders:
    def test_import_footage_op(self):
        jsx = ExecutionStage._build_jsx_for_op("importFootage", {"path": r"C:\x\y.mp4"})
        assert "new File(" in jsx and "C:/x/y.mp4" in jsx

    def test_analyze_project_lists_comps(self):
        jsx = ExecutionStage._build_jsx_for_op("analyzeProject", {})
        assert "CompItem" in jsx and "JSON.stringify" in jsx

    def test_add_effect_with_keyframes_escapes_effect_name(self):
        evil = 'x"); bad(); ("'
        jsx = ExecutionStage._build_jsx_for_op(
            "addEffectWithKeyframes", {"effectName": evil, "layerIndex": 2})
        assert json.dumps(evil) in jsx, "效果名未按 JSON 转义插入"
        assert "comp.layer(2)" in jsx

    def test_unknown_op_returns_empty(self):
        assert ExecutionStage._build_jsx_for_op("nope", {}) == ""


# ---------------------------------------------------------------------------
# _send_atom_script 的包裹方式
# ---------------------------------------------------------------------------

class TestSendAtomScript:
    def _stage(self):
        class _Cfg:
            pass
        return ExecutionStage(_Cfg())

    def test_unsupported_op_reports_error(self, monkeypatch):
        st = self._stage()
        sent = {}
        monkeypatch.setattr(st, "_send_bridge_command",
                            lambda *a, **k: sent.setdefault("called", True))
        res = st._send_atom_script("no_such_op", {})
        assert res["success"] is False and "Unsupported op" in res["message"]
        assert not sent, "未知 op 不应发桥命令"

    def test_body_is_json_quoted_inside_eval(self, monkeypatch):
        """脚本体必须经 json.dumps 引号化后交给 eval —— 防注入的关键一步。"""
        st = self._stage()
        captured = {}

        def _fake(cmd, args, timeout=15.0):
            captured["cmd"] = cmd
            captured["args"] = args
            return {"success": True}

        monkeypatch.setattr(st, "_send_bridge_command", _fake)
        st._send_atom_script("importFootage", {"path": "C:/a.mp4"})
        assert captured["cmd"] == "executeAtomScript"
        body = captured["args"]["script"]
        assert body.startswith("return eval(")
        inner = body[len("return eval("):-2]
        assert json.loads(inner)          # 内层是合法 JSON 字符串
        assert "new File(" in json.loads(inner)


# ---------------------------------------------------------------------------
# 构造与桥锁
# ---------------------------------------------------------------------------

class TestStageConstruction:
    def test_init_holds_config_and_lazy_client(self):
        cfg = object()
        st = ExecutionStage(cfg)
        assert st.config is cfg
        assert st._client is None and st._ae_ready is False

    def test_bridge_lock_is_class_level(self):
        """Bridge 是单文件轮询协议，并发会互相覆盖 → 锁必须是类级共享。"""
        a, b = ExecutionStage(object()), ExecutionStage(object())
        assert a._bridge_lock is b._bridge_lock
