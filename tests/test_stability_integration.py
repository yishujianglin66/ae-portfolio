"""Plan B P3 集成冒烟测试（非破坏性，全 stub，零真实 Adobe）。

目标：证明 P3 稳定性子系统在"真实管线运行"语境下确实接线生效——
  1. 真实 _ensure_ae_bridge_ready -> engine_watchdog.ensure_ready 跑通
     （配额双检锁 + 健康注册表写入），且全程 stub 进程/调度层、绝不真拉起 AE；
  2. 编排器在 run 收尾把 engine_health / resource_quota 写进 manifest
     （健康常态化进运行证据，fail-safe）。

固件视角：这是"上电自检 + watchdog reset 后无数据损坏"的离线等价验证——
用 stub 模拟引擎在线，断言注册表/配额/证据链一致，而非真去杀用户进程。
"""
import json
from pathlib import Path
from unittest import mock

import pytest

import core.engine_watchdog as ew
import pipeline.flagship_runner as fr
from core.engine_watchdog import EngineHealthRegistry, ResourceQuota


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """把旗舰管线输出根重定向到临时目录，避免污染真实 output/ 与 reports/。"""
    monkeypatch.setattr(fr, "PROJECT_ROOT", tmp_path)
    return tmp_path



class _FakeDispatcher:
    def __init__(self, available=True):
        self._available = available

    def is_available(self, force_check=False):
        return self._available


def _stub_stages(monkeypatch):
    """把全部真实阶段/素材/bridge 探测替换成确定性 stub（不触网、不触 Adobe）。"""
    calls = {}

    def s0(d):
        return {"healthy": True}

    def download_assets(d):
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        (p / "a.wav").write_bytes(b"x")
        return {"audio": p / "a.wav", "videos": []}

    def s1(d, assets):
        return {"audio": str(Path(d) / "audio.wav"), "videos": []}

    def s2(d, audio):
        (Path(d) / "beats.json").write_text("{}", encoding="utf-8")
        return {"beats_json": str(Path(d) / "beats.json")}

    def s3(d, sv):
        return {"renders": []}

    def s4(d, r, b):
        (Path(d) / "tl.xml").write_text("<x/>", encoding="utf-8")
        return {"timeline_xml": str(Path(d) / "tl.xml")}

    def s5(d, r):
        return {"graded_mov": str(Path(d) / "g.mov"), "nodes": 4, "has_lut": True}

    def s6(d, graded_mov, audio_path=None):
        (Path(d) / "final.mp4").write_text("x", encoding="utf-8")
        return {"final_mp4": str(Path(d) / "final.mp4")}

    def s7(d, mp4, beats, xml, meta, critic_reports=None):
        (Path(d) / "qg.json").write_text("{}", encoding="utf-8")
        return {"passed": True, "report": str(Path(d) / "qg.json")}

    monkeypatch.setattr(fr, "stage_s0_health", s0)
    monkeypatch.setattr(fr, "download_real_assets", download_assets)
    monkeypatch.setattr(fr, "stage_s1_normalize", s1)
    monkeypatch.setattr(fr, "stage_s2_beat", s2)
    monkeypatch.setattr(fr, "stage_s3_ae_composite", s3)
    monkeypatch.setattr(fr, "stage_s4_premiere", s4)
    monkeypatch.setattr(fr, "stage_s5_davinci", s5)
    monkeypatch.setattr(fr, "stage_s6_export", s6)
    monkeypatch.setattr(fr, "stage_s7_quality_gate", s7)

    # bridge 探测全部返回 True（不真实启动引擎）
    monkeypatch.setattr(fr, "_ensure_ae_bridge_ready", lambda timeout=0.0: True)
    monkeypatch.setattr(fr, "_ensure_pr_bridge_ready", lambda timeout=0.0: True)
    monkeypatch.setattr(fr, "_ensure_resolve_ready", lambda timeout=0.0: True)

    class _Verdict:
        decision = "pass"

    monkeypatch.setattr(fr, "critic_gate", lambda *a, **k: _Verdict())
    monkeypatch.setattr(fr, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(fr, "run_cmd", lambda *a, **k: None)
    monkeypatch.setattr(fr, "emit_event", lambda *a, **k: None)

    try:
        import core.experience_harvester as eh

        class _HR:
            total_records_extracted = 0
            total_sources_scanned = 0
            total_error_patterns = 0
            total_stage_experiences = 0

        class _H:
            def __init__(self, *a, **k):
                pass

            def harvest(self):
                return _HR()

        monkeypatch.setattr(eh, "ExperienceHarvester", _H)
    except Exception:
        pass
    return calls


def _reset_health_quota(monkeypatch):
    """隔离：每测试重置全局注册表/配额单例，避免跨测试污染。"""
    reg = EngineHealthRegistry()
    quota = ResourceQuota()
    monkeypatch.setattr(ew, "ENGINE_HEALTH", reg)
    monkeypatch.setattr(ew, "ENGINE_QUOTA", quota)
    return reg, quota


def test_real_ensure_ready_populates_registry_and_quota(tmp_project, monkeypatch):
    """真实 _ensure_ae_bridge_ready 跑通 engine_watchdog.ensure_ready：
    配额双检锁 + 健康注册表写入，且全程 stub、绝不真拉起 AE。"""
    _reset_health_quota(monkeypatch)
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", True)
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)

    # stub 进程层 + 调度层：模拟 AE 已运行且 Bridge 立即可用
    monkeypatch.setattr(ew, "is_process_running", lambda name: True)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    monkeypatch.setattr(fr, "get_dispatcher", lambda name: _FakeDispatcher(available=True))

    ok = fr._ensure_ae_bridge_ready(timeout=1.0)
    assert ok is True

    state = ew.ENGINE_HEALTH.get("after_effects")
    assert state["status"] == "healthy", state
    # 配额获取后必须在 finally 释放，避免占用泄漏（背压不误伤后续）
    assert ew.ENGINE_QUOTA.status()["active"] == 0, ew.ENGINE_QUOTA.status()


def test_manifest_carries_health_and_quota(tmp_project, monkeypatch):
    """编排器 run 收尾把 engine_health / resource_quota 写进 manifest
    （健康常态化进运行证据），且从真实就绪路径看 after_effects=healthy。"""
    _reset_health_quota(monkeypatch)
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", True)
    monkeypatch.delenv("AEKV_WATCHDOG", raising=False)
    monkeypatch.setattr(ew, "is_process_running", lambda name: True)
    monkeypatch.setattr(ew, "launch_engine", lambda *a, **k: True)
    monkeypatch.setattr(fr, "get_dispatcher", lambda name: _FakeDispatcher(available=True))

    # 先经真实就绪路径把 after_effects 标记 healthy（写进注册表）
    assert fr._ensure_ae_bridge_ready(timeout=1.0) is True

    # 再跑完整管线（bridge 探测 stub 为 True，不改动注册表）
    _stub_stages(monkeypatch)
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", False)  # 还原为稳定默认，避免 critic gate 触真 disp
    monkeypatch.setattr(fr, "time", mock.Mock(time=lambda: 1700000300))
    run_id = "flagship_1700000300"
    run_dir = tmp_project / "output" / run_id

    fr.run_flagship_pipeline()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "engine_health" in manifest, manifest.keys()
    assert "resource_quota" in manifest, manifest.keys()
    assert manifest["engine_health"]["after_effects"]["status"] == "healthy", manifest["engine_health"]
    assert manifest["resource_quota"]["max_concurrent"] == 2, manifest["resource_quota"]


def test_manifest_health_quota_written_even_when_no_engine_touched(tmp_project, monkeypatch):
    """即便没有任何引擎被标记就绪，编排器仍应写入 engine_health / resource_quota
    （保证证据结构一致，观测层永远有数据）。"""
    _reset_health_quota(monkeypatch)
    _stub_stages(monkeypatch)
    monkeypatch.setattr(fr, "_DISPATCHER_AVAILABLE", False)
    monkeypatch.setattr(fr, "time", mock.Mock(time=lambda: 1700000400))
    run_id = "flagship_1700000400"
    run_dir = tmp_project / "output" / run_id

    fr.run_flagship_pipeline()

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert isinstance(manifest["engine_health"], dict)
    assert manifest["resource_quota"]["max_concurrent"] == 2
    assert manifest["resource_quota"]["active"] == 0
