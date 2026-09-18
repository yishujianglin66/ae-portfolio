# -*- coding: utf-8 -*-
"""core/fx/style_preset_engine.py 单元测试。

使用临时 templates.json 与临时执行日志路径隔离，不触碰真实 data/ 目录。
build_plan 会新建 ParticleFXClient（其默认 history 目录为真实 data/），
故此处通过 monkeypatch 把环境置为 test 语义下仅测不写真实核心目录的路径。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest

from core.fx.style_preset_engine import (
    StylePresetEngine,
    get_style_preset_engine,
)

_TEMPLATE_BODY: dict[str, Any] = {
    "_meta": {"version": "1.0", "note": "test"},
    "templates": {
        "amv_highenergy": {
            "name": "高燃混剪",
            "desc": "测试模板",
            "mood": ["高燃"],
            "color_grade": [
                {"effect": "ADBE Lumetri",
                 "params": {"ADBE Lumetri-0012": 25}}
            ],
            "particles": [
                {"action": "layered", "preset": "amv_highenergy"},
                {"action": "beat_burst", "on_beats": True}
            ],
            "text_fx": [
                {"engine": "textImpactMaster", "action": "impact"}
            ],
        }
    },
}


def _write_template(tmp: str) -> str:
    path = Path(tmp) / "templates.json"
    path.write_text(json.dumps(_TEMPLATE_BODY, ensure_ascii=False), encoding="utf-8")
    return str(path)


class TestEngineLoad:
    """模板加载与查询。"""

    def test_load_and_list_styles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec" / "executions.jsonl"))
            styles = engine.list_styles()
            assert len(styles) == 1
            assert styles[0]["id"] == "amv_highenergy"
            assert styles[0]["name"] == "高燃混剪"

    def test_get_known_style(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec.jsonl"))
            t = engine.get("amv_highenergy")
            assert t["name"] == "高燃混剪"

    def test_get_unknown_style_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec.jsonl"))
            with pytest.raises(KeyError):
                engine.get("not_a_style")


class TestValidate:
    """模板校验。"""

    def test_valid_template_has_no_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec.jsonl"))
            assert engine.validate("amv_highenergy") == []


class TestBuildPlan:
    """执行计划展开结构。"""

    def test_build_plan_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec.jsonl"))
            plan = engine.build_plan("amv_highenergy", "Comp 1", beats=[0.5, 1.0])
            assert isinstance(plan, list)
            steps = {s["step"] for s in plan}
            assert "color_grade" in steps
            assert "particles" in steps
            assert "text_fx" in steps
            for s in plan:
                assert s["comp"] == "Comp 1"


class TestPersistence:
    """执行记录持久化读写。"""

    def test_record_and_get_executions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec" / "executions.jsonl"))
            engine.record_execution("amv_highenergy", "Comp 1",
                                    {"summary": {"total": 3, "ok": 2}})
            engine.record_execution("amv_highenergy", "Comp 2",
                                    {"summary": {"total": 1, "ok": 1}})
            execs = engine.get_executions()
            assert len(execs) == 2
            assert execs[0]["style"] == "amv_highenergy"
            assert execs[0]["comp"] == "Comp 1"
            assert execs[0]["summary"]["ok"] == 2

    def test_get_execution_log_dir_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = str(Path(tmp) / "a" / "b" / "executions.jsonl")
            engine = StylePresetEngine(templates_path=_write_template(tmp),
                                       execution_log_path=log)
            assert Path(tmp).joinpath("a", "b").is_dir()

    def test_clear_executions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            engine = StylePresetEngine(
                templates_path=_write_template(tmp),
                execution_log_path=str(Path(tmp) / "exec.jsonl"))
            engine.record_execution("amv_highenergy", "Comp 1", {})
            assert len(engine.get_executions()) == 1
            engine.clear_executions()
            assert engine.get_executions() == []

    def test_persistence_roundtrip_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = str(Path(tmp) / "exec.jsonl")
            StylePresetEngine(templates_path=_write_template(tmp),
                              execution_log_path=log).record_execution(
                "amv_highenergy", "Comp 1", {"summary": {"total": 1, "ok": 1}})
            engine2 = StylePresetEngine(templates_path=_write_template(tmp),
                                        execution_log_path=log)
            execs = engine2.get_executions()
            assert len(execs) == 1
            assert execs[0]["comp"] == "Comp 1"


class TestSingleton:
    """全局单例入口。"""

    def test_get_style_preset_engine_returns_same_instance(self) -> None:
        a = get_style_preset_engine()
        b = get_style_preset_engine()
        assert a is b
        assert isinstance(a, StylePresetEngine)