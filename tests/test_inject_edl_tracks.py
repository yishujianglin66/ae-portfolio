"""inject_edl_tracks 测试（Step2 事后回填）。零副作用：全用 tmp_path 夹具，不碰 output/。

覆盖: dry-run 不写盘 / text_events+effects 注入 / 幂等(覆盖非追加) /
      effects 权威源解析优先级(显式>pr>自动探测; 多候选告警不猜) / 缺 edl 跳过 / lint 闸门。
"""
import json
from pathlib import Path

from scripts.edl import build_edl, save_edl
from scripts.inject_edl_tracks import inject_edl_tracks

_SEGS = [
    {"index": 0, "start_time": 0.0, "end_time": 2.0, "source_file": None,
     "source_start": 0.0, "speed": 1.0, "transition": "cut", "mood": "intro", "energy": 0.3},
    {"index": 1, "start_time": 2.0, "end_time": 4.0, "source_file": None,
     "source_start": 5.0, "speed": 1.0, "transition": "cut", "mood": "drop", "energy": 0.9},
]
_EFFECT = [{"effect_id": "b1", "effect_type": "bloom",
            "time_range": {"start_sec": 0.5, "end_sec": 1.5},
            "parameters": {"threshold": 0.8}, "envelope": {"enabled": False},
            "evidence_chain": {"skill_id": "test-skill"}}]
_EVENTS = [{"id": 1, "t_in": 0.0, "t_out": 1.5, "word": "A", "hold": 1.5},
           {"id": 2, "t_in": 2.0, "t_out": 3.5, "word": "B", "hold": 1.5}]


def _mk_run(tmp_path: Path, *, n_effects_files=1, events=True, effects_source=None) -> Path:
    """造最小 run 目录: edl.json(cuts) + production_report + text_overlay/events.json + effects 文件。"""
    run = tmp_path / "run"
    run.mkdir()
    pr = {"script": {"segments": _SEGS}}
    if effects_source:
        pr["effects_source"] = effects_source
    (run / "production_report.json").write_text(json.dumps(pr), encoding="utf-8")
    save_edl(build_edl(run / "production_report.json"), run / "edl.json")  # duration 自动=4.0
    if events:
        (run / "text_overlay").mkdir()
        (run / "text_overlay" / "events.json").write_text(
            json.dumps({"events": _EVENTS}), encoding="utf-8")
    for i in range(n_effects_files):
        name = "run_effects.json" if n_effects_files == 1 else f"run_effects_{i}.json"
        (run / name).write_text(json.dumps(_EFFECT), encoding="utf-8")
    return run


def test_dry_run_does_not_write(tmp_path):
    run = _mk_run(tmp_path)
    before = (run / "edl.json").read_text(encoding="utf-8")
    rep = inject_edl_tracks(run, dry_run=True)
    assert (run / "edl.json").read_text(encoding="utf-8") == before   # 未写盘
    assert rep["saved"] is None
    assert rep["text_events_injected"] == 2                          # 但报告了将注入什么


def test_inject_text_events_and_effects(tmp_path):
    run = _mk_run(tmp_path)
    rep = inject_edl_tracks(run)                                     # 真实写
    assert rep["text_events_injected"] == 2
    assert rep["effects_injected"] == 1
    assert rep["lint_errors"] == []                                  # 回填后过闸门
    edl = json.loads((run / "edl.json").read_text(encoding="utf-8"))
    assert len(edl["text_events"]) == 2 and len(edl["effects"]) == 1
    assert edl["schema_version"] == "1.1"


def test_idempotent_no_doubling(tmp_path):
    run = _mk_run(tmp_path)
    inject_edl_tracks(run)
    inject_edl_tracks(run)                                           # 再跑一次
    edl = json.loads((run / "edl.json").read_text(encoding="utf-8"))
    assert len(edl["effects"]) == 1                                  # 覆盖非追加
    assert len(edl["text_events"]) == 2


def test_effects_ambiguous_warns_and_skips(tmp_path):
    run = _mk_run(tmp_path, n_effects_files=3)                       # 3 候选 → 歧义
    rep = inject_edl_tracks(run, dry_run=True)
    assert rep["effects_injected"] == 0                              # 不猜, 跳过 effects
    assert any("[WARN]" in n for n in rep["notes"])
    assert rep["text_events_injected"] == 2                          # text_events 仍注入


def test_effects_explicit_resolves_ambiguity(tmp_path):
    run = _mk_run(tmp_path, n_effects_files=3)
    rep = inject_edl_tracks(run, effects_file=str(run / "run_effects_1.json"), dry_run=True)
    assert rep["effects_injected"] == 1                              # 显式指定 → 消歧义


def test_effects_from_production_report_source(tmp_path):
    run = _mk_run(tmp_path, n_effects_files=2, effects_source="run_effects_0.json")
    rep = inject_edl_tracks(run, dry_run=True)
    assert rep["effects_injected"] == 1                              # pr.effects_source 优先于自动探测
    assert any("effects_source" in n for n in rep["notes"])


def test_missing_edl_skips(tmp_path):
    run = tmp_path / "empty"
    run.mkdir()
    rep = inject_edl_tracks(run, dry_run=True)
    assert rep["effects_injected"] == 0 and rep["text_events_injected"] == 0
    assert any("[SKIP]" in n and "edl.json" in n for n in rep["notes"])
