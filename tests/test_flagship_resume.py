"""P2 断点续跑 单元测试（manifest 驱动的崩溃恢复，规格 Plan B）。

运行：pytest tests/test_flagship_resume.py -v

策略：把全部真实引擎/素材阶段 stub 为轻量函数（落盘确定性产物），
     第一次运行在 S4 抛异常模拟"崩溃"，第二次以同一 run_id 续跑，
     断言 S0–S3 未被重跑（调用计数保持 1）而 S4–S7 执行；同时覆盖
     显式 resume_from 覆盖、全新 run 无续跑字段、缺失 run_id 报错。

设计要点（嵌入式稳定性视角）：
- 模拟固件 crash-recovery：manifest 即"非易失状态镜像"，崩溃后从镜像重建
- 复用既有 write_manifest_safe 落盘语义，仅验证调度层 skip/restore 正确性
- 全程离线（stub 不触网），满足 conftest 网络围栏
"""
import json
from pathlib import Path
from unittest import mock

import pytest

import pipeline.flagship_runner as fr


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """把旗舰管线输出根重定向到临时目录，避免污染真实 output/ 与 reports/。"""
    monkeypatch.setattr(fr, "PROJECT_ROOT", tmp_path)
    return tmp_path


class _FixedClock:
    """固定时钟，使 run_id = f"flagship_{int(time.time())}" 确定可控。"""

    def __init__(self, t: float):
        self._t = t

    def time(self) -> float:
        return self._t

    def sleep(self, *_a, **_k):
        pass


def _new_calls() -> dict:
    return {"s0": 0, "s1": 0, "s2": 0, "s3": 0,
            "s4": 0, "s5": 0, "s6": 0, "s7": 0, "assets": 0}


def _stub_all(monkeypatch, calls: dict, fail_at: str = None):
    """把全部真实阶段/引擎入口替换成确定性 stub，并共享同一 calls 计数器。"""

    def stage_s0(run_dir):
        calls["s0"] += 1
        return {"healthy": True}

    def download_assets(d):
        calls["assets"] += 1
        p = Path(d)
        p.mkdir(parents=True, exist_ok=True)
        (p / "a.wav").write_bytes(b"x")
        return {"audio": p / "a.wav", "videos": []}

    def stage_s1(run_dir, assets_dir):
        calls["s1"] += 1
        p = Path(run_dir) / "audio.wav"
        p.write_bytes(b"x")
        return {"audio": str(p), "videos": []}

    def stage_s2(run_dir, audio_path):
        calls["s2"] += 1
        p = Path(run_dir) / "beats.json"
        p.write_text("{}", encoding="utf-8")
        return {"beats_json": str(p)}

    def stage_s3(run_dir, source_videos):
        calls["s3"] += 1
        return {"renders": []}

    def stage_s4(run_dir, renders, beats_json):
        calls["s4"] += 1
        if fail_at == "S4":
            raise RuntimeError("boom at S4 (simulated crash)")
        p = Path(run_dir) / "tl.xml"
        p.write_text("<x/>", encoding="utf-8")
        return {"timeline_xml": str(p)}

    def stage_s5(run_dir, renders):
        calls["s5"] += 1
        p = Path(run_dir) / "g.mov"
        p.write_text("x", encoding="utf-8")
        return {"graded_mov": str(p), "nodes": 4, "has_lut": True}

    def stage_s6(run_dir, graded_mov, audio_path=None):
        calls["s6"] += 1
        p = Path(run_dir) / "final.mp4"
        p.write_text("x", encoding="utf-8")
        return {"final_mp4": str(p)}

    def stage_s7(run_dir, mp4, beats, xml, meta, critic_reports=None):
        calls["s7"] += 1
        p = Path(run_dir) / "qg.json"
        p.write_text("{}", encoding="utf-8")
        return {"passed": True, "report": str(p)}

    monkeypatch.setattr(fr, "stage_s0_health", stage_s0)
    monkeypatch.setattr(fr, "download_real_assets", download_assets)
    monkeypatch.setattr(fr, "stage_s1_normalize", stage_s1)
    monkeypatch.setattr(fr, "stage_s2_beat", stage_s2)
    monkeypatch.setattr(fr, "stage_s3_ae_composite", stage_s3)
    monkeypatch.setattr(fr, "stage_s4_premiere", stage_s4)
    monkeypatch.setattr(fr, "stage_s5_davinci", stage_s5)
    monkeypatch.setattr(fr, "stage_s6_export", stage_s6)
    monkeypatch.setattr(fr, "stage_s7_quality_gate", stage_s7)

    # 引擎就绪探测全部返回 True（不真实启动 AE/PR/Resolve）
    monkeypatch.setattr(fr, "_ensure_ae_bridge_ready", lambda timeout=0.0: True)
    monkeypatch.setattr(fr, "_ensure_pr_bridge_ready", lambda timeout=0.0: True)
    monkeypatch.setattr(fr, "_ensure_resolve_ready", lambda timeout=0.0: True)

    # StageCritic 边界自评：默认放行（decision="pass"）
    class _Verdict:
        decision = "pass"

    monkeypatch.setattr(fr, "critic_gate", lambda *a, **k: _Verdict())

    # 故障注入/ffmpeg/事件流 全部 no-op
    monkeypatch.setattr(fr, "resolve_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(fr, "run_cmd", lambda *a, **k: None)
    monkeypatch.setattr(fr, "emit_event", lambda *a, **k: None)

    # 经验回灌：patch 真实模块符号，避免导入阶段触网
    try:
        import core.experience_harvester as eh

        class _HarvestReport:
            total_records_extracted = 0
            total_sources_scanned = 0
            total_error_patterns = 0
            total_stage_experiences = 0

        class _Harvester:
            def __init__(self, *a, **k):
                pass

            def harvest(self):
                return _HarvestReport()

        monkeypatch.setattr(eh, "ExperienceHarvester", _Harvester)
    except Exception:
        pass


def _read_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def test_resume_skips_completed_stages(tmp_project, monkeypatch):
    """第一次崩在 S4，同一 run_id 续跑：S0–S3 跳过，S4–S7 执行。"""
    calls = _new_calls()
    _stub_all(monkeypatch, calls, fail_at="S4")
    monkeypatch.setattr(fr, "time", _FixedClock(1700000000))
    run_id = "flagship_1700000000"
    run_dir = tmp_project / "output" / run_id

    # 第一次运行（全新 run，固定时钟 -> run_id 可预期）：S4 崩溃
    with pytest.raises(RuntimeError):
        fr.run_flagship_pipeline()

    m1 = _read_manifest(run_dir)
    assert set(m1["stages"].keys()) == {"S0", "S1", "S2", "S3"}, m1["stages"].keys()
    assert m1["status"] == "failed"

    # 第二次运行：同一 run_id 续跑（fail_at=None -> S4 不再抛）
    _stub_all(monkeypatch, calls, fail_at=None)
    fr.run_flagship_pipeline(run_id=run_id)

    # 已完成阶段必须被复用，而非重跑
    assert calls["s0"] == 1, calls
    assert calls["s1"] == 1, calls
    assert calls["s2"] == 1, calls
    assert calls["s3"] == 1, calls
    assert calls["s4"] == 2, calls  # 第一次尝试 + 第二次成功
    assert calls["s5"] == 1, calls
    assert calls["s6"] == 1, calls
    assert calls["s7"] == 1, calls

    m2 = _read_manifest(run_dir)
    assert set(m2["stages"].keys()) >= {f"S{i}" for i in range(8)}, m2["stages"].keys()
    assert m2["status"] == "completed"
    assert m2.get("resumed_from") is None


def test_resume_from_explicit_stage(tmp_project, monkeypatch):
    """显式 resume_from='S5'：S0–S4 跳过，仅 S5–S7 执行。"""
    calls = _new_calls()
    _stub_all(monkeypatch, calls, fail_at=None)
    monkeypatch.setattr(fr, "time", _FixedClock(1700000100))
    run_id = "flagship_1700000100"
    run_dir = tmp_project / "output" / run_id

    # 先跑完整一次（全新 run，固定时钟 -> run_id 可预期）建立 manifest S0–S7
    fr.run_flagship_pipeline()
    m = _read_manifest(run_dir)
    assert set(m["stages"].keys()) == {f"S{i}" for i in range(8)}, m["stages"].keys()

    # 重置计数，模拟"S5 之前已落盘、需从 S5 续"
    calls.clear()
    calls.update(_new_calls())
    _stub_all(monkeypatch, calls, fail_at=None)
    fr.run_flagship_pipeline(run_id=run_id, resume_from="S5")

    for s in ("s0", "s1", "s2", "s3", "s4"):
        assert calls[s] == 0, (s, calls)
    for s in ("s5", "s6", "s7"):
        assert calls[s] == 1, (s, calls)

    m2 = _read_manifest(run_dir)
    assert m2.get("resumed_from") == "S5"


def test_fresh_run_no_resume(tmp_project, monkeypatch):
    """全新 run（run_id=None）：全 8 阶段执行，无续跑字段。"""
    calls = _new_calls()
    _stub_all(monkeypatch, calls, fail_at=None)
    monkeypatch.setattr(fr, "time", _FixedClock(1700000200))
    run_id = "flagship_1700000200"
    run_dir = tmp_project / "output" / run_id

    fr.run_flagship_pipeline()  # 不传 run_id -> 新建时间戳 run（固定时钟 => 确定）

    m = _read_manifest(run_dir)
    assert set(m["stages"].keys()) == {f"S{i}" for i in range(8)}, m["stages"].keys()
    assert "resumed_from" not in m or m.get("resumed_from") is None
    for s in ("s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7"):
        assert calls[s] == 1, (s, calls)


def test_resume_missing_run_raises(tmp_project, monkeypatch):
    """续跑目标 run 不存在：应抛 FileNotFoundError（不触碰任何阶段）。"""
    calls = _new_calls()
    _stub_all(monkeypatch, calls, fail_at=None)
    with pytest.raises(FileNotFoundError):
        fr.run_flagship_pipeline(run_id="flagship_does_not_exist")
    # 任何阶段都不应执行
    assert sum(calls.values()) == 0, calls
