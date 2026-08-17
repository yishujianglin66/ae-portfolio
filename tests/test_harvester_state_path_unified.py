"""learning 状态模块路径统一测试。

验证 core/experience_harvester.py 的 ExperienceInjector 在注入/持久化各
learning 状态模块时，传入的 data_dir 统一基于 project_root 构造（绝对路径），
消除 "data/xxx" 相对路径依赖 CWD 导致的多入口路径来源不一致。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.experience_harvester import ExperienceInjector


class _FakeEngine:
    """模拟状态模块实例，记录传入的 data_dir。"""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir else None

    def _save_state(self):
        return None

    def get_statistics(self):
        return {}

    def _shared_predictor(self):
        return None


class TestInjectorStatePathUnified:
    """Injector 注入各状态模块时，data_dir 必须基于 project_root 构造。"""

    def _make_injector(self, tmp_path) -> ExperienceInjector:
        return ExperienceInjector(data_dir=str(tmp_path / "data"))

    def test_state_dir_is_absolute_and_under_root(self, tmp_path):
        inj = self._make_injector(tmp_path)
        d = inj._state_dir("digital_twin")
        assert isinstance(d, str)
        assert Path(d).is_absolute()
        assert Path(d) == tmp_path / "data" / "digital_twin"

    def test_persist_causal_uses_root_based_dir(self, tmp_path, monkeypatch):
        captured = {}

        def fake_causal(data_dir=None):
            captured["causal"] = data_dir
            return _FakeEngine(data_dir)

        monkeypatch.setattr("core.causal_engine.get_causal_engine", fake_causal)
        inj = self._make_injector(tmp_path)
        inj._persist_module_states()
        assert captured["causal"] is not None
        assert Path(captured["causal"]).is_absolute()
        assert str(captured["causal"]).startswith(str(tmp_path))

    def test_persist_bayesian_uses_root_based_dir(self, tmp_path, monkeypatch):
        captured = {}

        def fake_optimizer(data_dir=None):
            captured["bayesian"] = data_dir
            return _FakeEngine(data_dir)

        monkeypatch.setattr("core.bayesian_optimizer.get_optimizer", fake_optimizer)
        inj = self._make_injector(tmp_path)
        inj._persist_module_states()
        assert captured["bayesian"] is not None
        assert Path(captured["bayesian"]).is_absolute()
        assert str(captured["bayesian"]).startswith(str(tmp_path))

    def test_inject_causal_uses_root_based_dir(self, tmp_path, monkeypatch):
        captured = {}

        def fake_causal(data_dir=None):
            captured["causal"] = data_dir
            return _FakeEngine(data_dir)

        monkeypatch.setattr("core.causal_engine.get_causal_engine", fake_causal)
        inj = self._make_injector(tmp_path)
        inj._inject_causal([])
        assert captured["causal"] is not None
        assert Path(captured["causal"]).is_absolute()

    def test_inject_twin_uses_root_based_dir(self, tmp_path, monkeypatch):
        captured = {}

        def fake_twin(data_dir=None):
            captured["twin"] = data_dir
            return _FakeEngine(data_dir)

        monkeypatch.setattr("core.pipeline_digital_twin.get_digital_twin", fake_twin)
        inj = self._make_injector(tmp_path)
        inj._inject_twin([])
        assert captured["twin"] is not None
        assert Path(captured["twin"]).is_absolute()