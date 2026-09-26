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


# ============================================================
#  integrations/mediapipe_integration.py（F3-3 闭单，审计 R21）
# ============================================================
class TestMediaPipeContract:
    def test_bare_result_neither_claim_real_nor_simulate(self):
        from integrations.mediapipe_integration import MediaPipeResult
        r = MediaPipeResult()
        assert r.mode == "" and r.is_simulated is False

    def test_auto_without_deps_fails_explicitly_no_fake_landmarks(self, monkeypatch, tmp_path):
        """旧行为：依赖缺失 auto→simulate，正弦假关键点以 success=True 流出驱动骨架。"""
        monkeypatch.setattr("integrations.mediapipe_integration._MEDIAPIPE_AVAILABLE", False)
        from integrations.mediapipe_integration import MediaPipeConfig, MediaPipeIntegrator
        vid = tmp_path / "v.mp4"
        vid.write_bytes(b"\x00" * 1024)
        integ = MediaPipeIntegrator(MediaPipeConfig(mode="auto"))
        assert integ.get_mode() == "real", "auto 不得静默换轨 simulate"
        res = integ.process_video(str(vid))
        assert res.success is False
        assert res.detections == [], "绝不再伪造正弦假关键点入池"
        assert "simulate" in res.error or "未安装" in res.error

    def test_explicit_simulate_still_works_but_marked(self, tmp_path):
        """显式 simulate 保留（离线联调价值），但 is_simulated 硬标记必在。"""
        from integrations.mediapipe_integration import MediaPipeConfig, MediaPipeIntegrator
        vid = tmp_path / "v.mp4"
        vid.write_bytes(b"\x00" * 1024)
        integ = MediaPipeIntegrator(MediaPipeConfig(mode="simulate"))
        res = integ.process_video(str(vid))
        assert res.success is True
        assert res.is_simulated is True and res.mode == "simulate"
        assert len(res.detections) > 0  # 演示能力未丢

    def test_detector_init_error_recorded_not_silent_simulate(self, monkeypatch, tmp_path):
        """走生产 _init_detectors 真实 except 路径（mediapipe 未装→名字未定义报错）：
        必须记 _init_error 并在 process_video 显式失败，不得把 mode 改写为 simulate。"""
        monkeypatch.setattr("integrations.mediapipe_integration._MEDIAPIPE_AVAILABLE", True)
        monkeypatch.setattr("integrations.mediapipe_integration.CV2_AVAILABLE", True)
        from integrations.mediapipe_integration import MediaPipeConfig, MediaPipeIntegrator
        integ = MediaPipeIntegrator(MediaPipeConfig(mode="auto"))
        assert integ.get_mode() == "real", "初始化爆炸后不得静默换轨 simulate（旧 L264 行为）"
        assert integ._init_error, "生产 except 路径必须记账 _init_error"
        vid = tmp_path / "v.mp4"
        vid.write_bytes(b"\x00" * 1024)
        res = integ.process_video(str(vid))
        assert res.success is False and res.detections == []
        assert "初始化失败" in res.error
