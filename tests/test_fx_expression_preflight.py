# -*- coding: utf-8 -*-
"""core/fx/expression_preflight.py 单元测试。

不触发真实 Bridge（preflight/apply 会走 _send_raw），
仅验证表达式生成、路径归一化、ExpressionGate 实例化与日志持久化。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from core.fx.expression_preflight import (
    EXPRESSION_KINDS,
    ExpressionGate,
    _normalize_path,
    generate_expression,
    get_expression_gate,
)


class TestGenerateExpression:
    """表达式生成。"""

    def test_each_kind_returns_string(self) -> None:
        for kind in EXPRESSION_KINDS:
            expr = generate_expression(kind)
            assert isinstance(expr, str)
            assert len(expr.strip()) > 0

    def test_shake_embeds_params(self) -> None:
        expr = generate_expression("shake", start=1.0, amp=30.0, freq=8.0, decay=3.0)
        assert "t0=1" in expr
        assert "amp=30" in expr

    def test_pulse_returns_scale_expression(self) -> None:
        expr = generate_expression("pulse", base=100.0, amp=12.0, freq=2.0)
        assert "[s,s]" in expr

    def test_wiggle_uses_wiggle_function(self) -> None:
        expr = generate_expression("wiggle", amp=20.0, freq=2.0)
        assert expr.startswith("wiggle(")

    def test_unknown_kind_raises(self) -> None:
        with pytest.raises(KeyError):
            generate_expression("not_a_kind")


class TestNormalizePath:
    """属性路径归一化。"""

    def test_string_path_splits(self) -> None:
        segs = _normalize_path("Transform/Position")
        assert segs == ["Transform", "Position"]

    def test_list_path_preserves_order(self) -> None:
        segs = _normalize_path(["ADBE Transform", "ADBE Position"])
        assert segs == ["ADBE Transform", "ADBE Position"]

    def test_empty_path_raises(self) -> None:
        with pytest.raises(ValueError):
            _normalize_path("")


class TestGateInstantiation:
    """ExpressionGate 实例化与日志持久化。"""

    def test_instantiation_creates_log_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = str(Path(tmp) / "logs")
            ExpressionGate(log_dir=log_dir)
            assert Path(log_dir).is_dir()

    def test_generate_method(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gate = ExpressionGate(log_dir=str(Path(tmp) / "logs"))
            assert gate.generate("pulse") == generate_expression("pulse")

    def test_record_and_get_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gate = ExpressionGate(log_dir=str(Path(tmp) / "logs"))
            gate.record("preflight", "Comp 1", 1, ["Transform", "Position"],
                        {"ok": True}, expression="value;")
            gate.record("apply", "Comp 1", 1, ["Transform", "Position"],
                        {"ok": False, "error_type": "set_failed"}, expression="value;")
            log = gate.get_log()
            assert len(log) == 2
            assert log[0]["kind"] == "preflight"
            assert log[0]["ok"] is True
            assert log[1]["kind"] == "apply"
            assert log[1]["ok"] is False
            assert log[1]["error_type"] == "set_failed"

    def test_clear_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            gate = ExpressionGate(log_dir=str(Path(tmp) / "logs"))
            gate.record("preflight", "Comp 1", 1, ["P"], {"ok": True})
            assert len(gate.get_log()) == 1
            gate.clear_log()
            assert gate.get_log() == []

    def test_persistence_roundtrip_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = str(Path(tmp) / "logs")
            ExpressionGate(log_dir=log_dir).record(
                "apply", "Comp 1", "Title", ["Transform", "Position"],
                {"ok": True}, expression="wiggle(2,10);")
            gate2 = ExpressionGate(log_dir=log_dir)
            log = gate2.get_log()
            assert len(log) == 1
            assert log[0]["property"] == "['Transform', 'Position']"


class TestSingleton:
    """全局单例入口。"""

    def test_get_expression_gate_returns_same_instance(self) -> None:
        a = get_expression_gate()
        b = get_expression_gate()
        assert a is b
        assert isinstance(a, ExpressionGate)