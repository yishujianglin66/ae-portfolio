# -*- coding: utf-8 -*-
"""core/fx/particle_presets.py 单元测试。

注意：不触发真实 AE 下发（_send_raw 走 Bridge 会写文件并轮询），
仅验证元数据、JSX 组装、客户端实例化与调用历史持久化。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from core.fx.particle_presets import (
    ATMOSPHERE_MOODS,
    LAYERED_PRESETS,
    MATCHNAMES,
    PARTICLE_TYPES,
    ParticleFXClient,
    build_particle_jsx,
    get_particle_fx_client,
)


class TestMetadata:
    """粒子元数据表结构正确。"""

    def test_particle_types_structure(self) -> None:
        assert isinstance(PARTICLE_TYPES, dict)
        assert len(PARTICLE_TYPES) > 0
        for pid, meta in PARTICLE_TYPES.items():
            assert isinstance(meta, dict), f"{pid} 元数据必须是 dict"
            assert "desc" in meta and "engine" in meta and "blend" in meta

    def test_particle_types_engine_known(self) -> None:
        engines = {"cc_particle_world", "cc_particle_systems_2", "cc_rainfall", "cc_snowfall"}
        for meta in PARTICLE_TYPES.values():
            assert meta["engine"] in engines

    def test_layered_presets_structure(self) -> None:
        assert isinstance(LAYERED_PRESETS, dict)
        assert "amv_highenergy" in LAYERED_PRESETS
        assert all(isinstance(v, list) for v in LAYERED_PRESETS.values())

    def test_atmosphere_moods_structure(self) -> None:
        assert isinstance(ATMOSPHERE_MOODS, dict)
        assert "smoke" in ATMOSPHERE_MOODS

    def test_matchnames_has_effect_parade(self) -> None:
        assert MATCHNAMES["effect_parade"] == "ADBE Effect Parade"


class TestBuildJsx:
    """JSX 组装输出格式。"""

    def test_build_particle_jsx_returns_wrapped_string(self) -> None:
        jsx = build_particle_jsx("generate", compName="Comp 1", type="spark", options={})
        assert isinstance(jsx, str)
        # 应包裹为自执行函数并返回结果 JSON 字符串
        assert jsx.startswith("(function(){try{")
        assert "__aeAdditiveResult" in jsx

    def test_build_particle_jsx_contains_action(self) -> None:
        jsx = build_particle_jsx("layered", compName="Comp 1", preset="amv_highenergy")
        assert "layered" in jsx


class TestClientInstantiation:
    """客户端实例化与持久化读写。"""

    def test_instantiation_creates_history_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = str(Path(tmp) / "hist")
            client = ParticleFXClient(history_dir=history_dir)
            assert Path(history_dir).is_dir()

    def test_record_and_get_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = ParticleFXClient(history_dir=str(Path(tmp) / "hist"))
            client.record_call("generate", {"compName": "C", "type": "spark"},
                               {"status": "success"})
            client.record_call("layered", {"compName": "C", "preset": "amv_highenergy"},
                               {"status": "error"})
            history = client.get_history()
            assert len(history) == 2
            assert history[0]["action"] == "generate"
            assert history[0]["status"] == "success"
            assert history[1]["action"] == "layered"
            assert history[1]["status"] == "error"

    def test_get_history_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = ParticleFXClient(history_dir=str(Path(tmp) / "hist"))
            for i in range(5):
                client.record_call("atmosphere", {"compName": "C", "mood": "smoke"},
                                   {"status": "success"})
            history = client.get_history(limit=2)
            assert len(history) == 2

    def test_clear_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            client = ParticleFXClient(history_dir=str(Path(tmp) / "hist"))
            client.record_call("generate", {}, {"status": "success"})
            assert len(client.get_history()) == 1
            client.clear_history()
            assert client.get_history() == []
            # 清空后文件应不存在
            assert not (Path(tmp) / "hist" / "history.jsonl").exists()

    def test_persistence_roundtrip_across_instances(self) -> None:
        """写入后由新实例读回，验证真正的磁盘持久化。"""
        with tempfile.TemporaryDirectory() as tmp:
            history_dir = str(Path(tmp) / "hist")
            c1 = ParticleFXClient(history_dir=history_dir)
            c1.record_call("beat_burst", {"beats": [0.5, 1.0]}, {"status": "success"})
            c2 = ParticleFXClient(history_dir=history_dir)
            history = c2.get_history()
            assert len(history) == 1
            assert history[0]["action"] == "beat_burst"

    def test_generate_unknown_type_is_error(self) -> None:
        """未知粒子类型在不触发 Bridge 的情况下直接返回错误。"""
        with tempfile.TemporaryDirectory() as tmp:
            client = ParticleFXClient(history_dir=str(Path(tmp) / "hist"))
            result: Dict[str, Any] = client.generate("Comp 1", "not_a_real_type")
            assert result["status"] == "error"
            history = client.get_history()
            assert len(history) == 1
            assert history[0]["status"] == "error"


class TestSingleton:
    """全局单例入口。"""

    def test_get_particle_fx_client_returns_same_instance(self) -> None:
        a = get_particle_fx_client()
        b = get_particle_fx_client()
        assert a is b
        assert isinstance(a, ParticleFXClient)