# -*- coding: utf-8 -*-
"""
FIX-03 契约闸门测试：simulate 默认值 / 静默降级 / 假产物占期望路径 —— 禁回涨
================================================================================
出处：09-计划文件/2026-09-26_全量问题修复执行方案.md FIX-03（审计 F3 + §3.3b①②③ + A 类形态）
契约：docs/execution_result_contract.md §1/§2.1/§3

逐文件闭单追加参数化用例：
  topaz(F3-2) → mediapipe → blender_3d → davinci → adobe×3 → silhouette → ai_video_generator
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ============================================================
#  integrations/topaz_integration.py（F3-2 闭单）
# ============================================================
class TestTopazContract:
    @pytest.fixture()
    def enh(self, monkeypatch, tmp_path):
        from integrations.topaz_integration import TopazEnhancer
        e = TopazEnhancer()
        # 本测试考"模式语义"不考媒体探测：桩掉真实探测与耗时估算
        monkeypatch.setattr(e, "_get_video_info",
                            lambda p: {"width": 640, "height": 360, "fps": 24.0})
        monkeypatch.setattr(e, "estimate_duration", lambda p, c: 1.0)
        return e

    def test_bare_result_does_not_claim_simulate(self):
        from integrations.topaz_integration import TopazResult
        assert TopazResult().mode == "", \
            "裸结果不得预填任何执行模式（旧默认 simulate=谎称已仿真执行）"

    def test_auto_failure_never_falls_back_to_simulate(self, enh, monkeypatch, tmp_path):
        from integrations.topaz_integration import TopazConfig, TopazResult
        src = tmp_path / "in.mp4"
        src.write_bytes(b"\x00" * 2048)

        def fake_real(input_path, output_path, config, callback=None):
            return TopazResult(success=False, input_path=input_path,
                               output_path=output_path, mode="real",
                               error="forced failure")

        def forbidden_sim(*a, **k):
            raise AssertionError("auto/real 失败不得转 simulate（FIX-03/契约 §3）")

        monkeypatch.setattr(enh, "_run_real_mode", fake_real)
        monkeypatch.setattr(enh, "_run_simulate_mode", forbidden_sim)
        cfg = TopazConfig(mode="auto", output_dir=str(tmp_path / "out"))
        res = enh.enhance_video(str(src), config=cfg)
        assert res.success is False
        assert res.mode == "real"

    def test_explicit_simulate_goes_to_simulated_dir(self, enh, tmp_path):
        """契约 §2.1：仿真产物禁止占用期望路径（A 类"exists() 骗过取证"根治）。"""
        from integrations.topaz_integration import TopazConfig
        src = tmp_path / "in.mp4"
        src.write_bytes(b"\x00" * 2048)
        cfg = TopazConfig(mode="simulate", output_dir=str(tmp_path / "out"))
        res = enh.enhance_video(str(src), config=cfg)
        assert res.success is True and res.mode == "simulate"
        produced = Path(res.output_path)
        assert "simulated" in produced.parts, f"仿真产物必须落 simulated/ 子目录: {produced}"
        out_root = tmp_path / "out"
        assert not (out_root / produced.name).exists(), "期望路径上不得出现仿真文件"
        meta = Path(str(produced) + ".meta.json")
        assert meta.exists()
        assert json.loads(meta.read_text(encoding="utf-8"))["execution_path"] == "simulated"

    def test_config_default_mode_not_silent_simulate(self):
        from integrations.topaz_integration import TopazConfig
        assert TopazConfig().mode in ("real", "auto"), \
            "配置默认值不得是 simulate（契约 §3）"
