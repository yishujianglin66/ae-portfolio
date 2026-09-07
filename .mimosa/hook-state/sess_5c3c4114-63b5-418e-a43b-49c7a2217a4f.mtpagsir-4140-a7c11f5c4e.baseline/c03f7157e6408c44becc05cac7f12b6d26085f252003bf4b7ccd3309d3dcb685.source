#!/usr/bin/env python3
"""MiniMax H3接入全量smoke：语法编译、import循环、实例化。"""
from __future__ import annotations

import importlib
import py_compile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 本轮修改过的源码文件
MODS = [
    "core.security",
    "core.config",
    "core.llm_gateway",
    "core.workflow_orchestrator",
    "core.formal_spec",
    "pipeline.unified_pipeline",
]

FILES = [
    ROOT / "core" / "security.py",
    ROOT / "core" / "config.py",
    ROOT / "core" / "llm_gateway.py",
    ROOT / "core" / "workflow_orchestrator.py",
    ROOT / "core" / "formal_spec.py",
    ROOT / "pipeline" / "unified_pipeline.py",
]


class TestPyCompile:
    """6 个修改的源码文件必须字节码编译通过。"""

    @pytest.mark.parametrize("fp", FILES, ids=[f.name for f in FILES])
    def test_file_py_compile_ok(self, fp):
        # 不产生 __pycache__；d 则 True 不会抛
        py_compile.compile(str(fp), doraise=True)


class TestImportNoCycle:
    """6 模块 import 不循环、不崩。"""

    @pytest.mark.parametrize("mod", MODS)
    def test_import_module_once(self, mod):
        m = importlib.import_module(mod)
        assert m is not None


class TestKeyInstances:
    """关键类实例化无异常。"""

    def test_config_manager_and_validator(self):
        from core.config import ConfigManager, ConfigValidator
        mgr = ConfigManager(auto_load=False)
        assert mgr is not None
        v = ConfigValidator(strict=False)
        assert v is not None

    def test_security_riskassessor(self):
        from core.security import RiskAssessor
        a = RiskAssessor()
        # 至少能 assess 一下新旧映射都在
        for t in ("video_generation", "perception", "runway_generate"):
            r = a.assess(t, {})
            assert r is not None

    def test_sandbox_executor(self, tmp_path):
        from core.security import SandboxPolicy
        ex = SandboxPolicy(workspace_root=tmp_path)
        assert len(ex._allowed_roots) >= 5

    def test_llm_gateway(self):
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        assert g is not None
        # _stats 新字段齐全
        for k in ("total_video_seconds", "total_images_generated", "total_modality_cost_usd"):
            assert k in g._stats
        # Provider 健康表 minimax_h3 可注册
        g._provider_health.clear()
        from core.llm_gateway import ProviderHealth
        g._provider_health["minimax_h3"] = ProviderHealth(name="minimax_h3")
        assert g._provider_health["minimax_h3"].total_video_seconds == 0.0

    def test_formal_spec_has_h3video(self):
        from core.formal_spec import H3VideoSpec, FORMAL_INVARIANTS
        inv = H3VideoSpec()
        assert inv.name == "H3VideoSpec"
        # 至少 1 个不变量
        assert any(isinstance(x, H3VideoSpec) for x in FORMAL_INVARIANTS)

    def test_pipeline_selector(self):
        from pipeline.unified_pipeline import AdaptiveFallbackSelector
        sel = AdaptiveFallbackSelector()
        chains = AdaptiveFallbackSelector.DEFAULT_FALLBACK_CHAINS
        # 5 条链：perceive/analyze/plan/execute/render + 本轮 新增 postproduction + generative = 至少 7
        assert len(chains) >= 7
        for key in ("execute", "render", "postproduction", "generative"):
            assert key in chains


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider"])
