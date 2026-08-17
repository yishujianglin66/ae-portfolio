# -*- coding: utf-8 -*-
"""core/fx/text_impact.py 单元测试。

不触发真实 AE 下发（_build_jsx 组装后走 _send_raw），
仅验证能力元数据、JSX 组装、客户端实例化、空参校验与调用历史持久化。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from core.fx.text_impact import (
    IMPACT_CAPABILITIES,
    TextImpactClient,
    _build_jsx,
    get_text_impact_client,
)


class TestCapabilities:
    """打击感能力元数据。"""

    def test_capabilities_structure(self) -> None:
        assert isinstance(IMPACT_CAPABILITIES, dict)
        assert {"impact", "beat_sync", "rgb_glitch"} <= set(IMPACT_CAPABILITIES)
        for name, meta in IMPACT_CAPABILITIES.items():
            assert "desc" in meta and "key_params" in meta


class TestBuildJsx:
    """JSX 组装输出格式。"""

    def test_build_jsx_returns_wrapped_string(self) -> None:
        jsx = _build_jsx("impact", compName="Comp 1", layerName="Title",
                         time=0.5, startScale=160, flash=True)
        assert isinstance(jsx, str)
        assert jsx.startswith("(function(){try{")
        assert "__aeAdditiveResult" in jsx

    def test_build_jsx_contains_action(self) -> None:
        jsx = _build_jsx("rgb_glitch", compName="Comp 1", layerName="Title",
                         glitchKeys=10, offsetMax=12)
        assert "rgb_glitch" in jsx


class TestClientInstantiation:
    """客户端实例化与持久化读写。"""

    def test_instantiation_creates_history_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = str(Path(tmp) / "hist")
            TextImpactClient(history_dir=history_dir)
            assert Path(history_dir).is_dir()

    def test_record_and_get_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = TextImpactClient(history_dir=str(Path(tmp) / "hist"))
            client.record_call("impact", {"compName": "C"}, {"status": "success"})
            client.record_call("rgb_glitch", {"compName": "C"}, {"status": "error"})
            history = client.get_history()
            assert len(history) == 2
            assert history[0]["action"] == "impact"
            assert history[1]["action"] == "rgb_glitch"

    def test_clear_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = TextImpactClient(history_dir=str(Path(tmp) / "hist"))
            client.record_call("impact", {}, {"status": "success"})
            assert len(client.get_history()) == 1
            client.clear_history()
            assert client.get_history() == []

    def test_persistence_roundtrip_across_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = str(Path(tmp) / "hist")
            TextImpactClient(history_dir=history_dir).record_call(
                "beat_sync", {"beats": [0.5, 1.0]}, {"status": "success"})
            c2 = TextImpactClient(history_dir=history_dir)
            assert len(c2.get_history()) == 1
            assert c2.get_history()[0]["action"] == "beat_sync"

    def test_beat_sync_empty_beats_returns_error(self) -> None:
        """空 beats 在不触发 Bridge 的情况下直接返回错误并记录。"""
        with tempfile.TemporaryDirectory() as tmp:
            client = TextImpactClient(history_dir=str(Path(tmp) / "hist"))
            result: Dict[str, Any] = client.beat_sync("Comp 1", "Title", [])
            assert result["status"] == "error"
            assert "不能为空" in result["message"]
            assert len(client.get_history()) == 1
            assert client.get_history()[0]["status"] == "error"


class TestSingleton:
    """全局单例入口。"""

    def test_get_text_impact_client_returns_same_instance(self) -> None:
        a = get_text_impact_client()
        b = get_text_impact_client()
        assert a is b
        assert isinstance(a, TextImpactClient)