"""EDL v1.1 三轨(effects/text_events/overlays) + lint L7 + 双兼容 回归测试。

对应补丁: 09-计划文件/patches/Step0_EDL_v1.1_补丁草案.md
设计: 纯追加 + FORWARD/BACKWARD 双兼容 —— 旧调用/旧 1.0 文件零回归。
"""
import json
from pathlib import Path

import pytest

from scripts.edl import (
    EDL_SCHEMA_VERSION,
    SUPPORTED_EDL_SCHEMA_VERSIONS,
    build_edl,
    lint_edl,
    load_edl,
    save_edl,
)


def _mk_pr(tmp_path: Path, segs=None) -> Path:
    """造一个最小 production_report.json（build_edl 的输入）。"""
    segs = segs if segs is not None else [
        {"index": 0, "start_time": 0.0, "end_time": 2.0,
         "source_file": None, "source_start": 0.0, "speed": 1.0,
         "transition": "cut", "mood": "intro", "energy": 0.3},
        {"index": 1, "start_time": 2.0, "end_time": 4.0,
         "source_file": None, "source_start": 5.0, "speed": 1.0,
         "transition": "cut", "mood": "drop", "energy": 0.9},
    ]
    pr = tmp_path / "production_report.json"
    pr.write_text(json.dumps({"script": {"segments": segs}}), encoding="utf-8")
    return pr


def test_version_bump():
    assert EDL_SCHEMA_VERSION == "1.1"
    assert "1.0" in SUPPORTED_EDL_SCHEMA_VERSIONS  # BACKWARD


def test_backward_compat_no_new_tracks(tmp_path):
    """不传新参 → 输出无 effects/text_events/overlays 键（旧调用最小惊讶）。"""
    edl = build_edl(_mk_pr(tmp_path))
    assert "effects" not in edl
    assert "text_events" not in edl
    assert "overlays" not in edl
    assert lint_edl(edl) == []          # L1-L7 全过


def test_lint_accepts_legacy_1_0(tmp_path):
    edl = build_edl(_mk_pr(tmp_path))
    edl["schema_version"] = "1.0"        # 模拟旧文件
    assert not any(e.startswith("L1") for e in lint_edl(edl))


def test_forward_new_tracks_present_and_valid(tmp_path):
    edl = build_edl(
        _mk_pr(tmp_path),
        effects=[{"effect_id": "b1", "effect_type": "bloom",
                  "time_range": {"start_sec": 2.0, "end_sec": 3.0},
                  "parameters": {}, "envelope": {"enabled": False},
                  "evidence_chain": {"skill_id": "bloom_drop"}}],
        text_events=[{"t_in": 2.0, "t_out": 3.5, "word": "最強",
                      "style_id": "drop_impact", "skill_id": "text_style_contrast"}],
        overlays=[{"file": "fx/wa2_alpha.mp4", "start_in_output": 1.0,
                   "duration": 2.0, "source_skill_id": "puppet_alpha"}],
    )
    assert edl["effects"] and edl["text_events"] and edl["overlays"]
    assert lint_edl(edl) == []


def test_l7_overlay_exceeds_timeline(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    overlays=[{"file": "x.mp4", "start_in_output": 3.0, "duration": 5.0}])
    assert any("overlay#0 exceeds timeline" in e for e in lint_edl(edl))


def test_l7_overlay_missing_file(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    overlays=[{"start_in_output": 0.5, "duration": 1.0}])
    assert any("overlay#0 missing file" in e for e in lint_edl(edl))


def test_l7_effect_bad_range_and_missing_skill(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), effects=[
        {"effect_id": "e", "effect_type": "bloom",
         "time_range": {"start_sec": 3.0, "end_sec": 1.0},   # 逆序
         "parameters": {}, "evidence_chain": {}},            # 无 skill_id
    ])
    errs = lint_edl(edl)
    assert any("effect#0 invalid time_range" in e for e in errs)
    assert any("effect#0 missing evidence_chain.skill_id" in e for e in errs)


def test_l7_text_event_out_of_bounds(tmp_path):
    edl = build_edl(_mk_pr(tmp_path),
                    text_events=[{"t_in": 3.0, "t_out": 99.0, "word": "x"}])
    assert any("text_event#0 t_out 99.0 exceeds timeline" in e for e in lint_edl(edl))


def test_save_reload_roundtrip(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), overlays=[
        {"file": "a.mp4", "start_in_output": 0.0, "duration": 1.0}])
    p = save_edl(edl, tmp_path / "edl.json")
    back = json.loads(p.read_text(encoding="utf-8"))
    assert back["overlays"] == edl["overlays"]
    assert lint_edl(back) == []


# --- load_edl 契约闸门(Step1: AE 链消费 EDL 的 fail-fast 入口) ---

def test_load_edl_gate_passes_valid(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), overlays=[
        {"file": "a.mp4", "start_in_output": 0.0, "duration": 1.0}])
    p = save_edl(edl, tmp_path / "edl.json")
    got = load_edl(p)                    # lint 通过 → 返回 dict
    assert got["overlays"] == edl["overlays"]


def test_load_edl_gate_raises_on_lint_fail(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), overlays=[
        {"file": "x.mp4", "start_in_output": 3.0, "duration": 99.0}])  # 越界 → L7
    p = save_edl(edl, tmp_path / "edl.json")
    with pytest.raises(ValueError):
        load_edl(p)                      # 违约不向下游传播


def test_load_edl_run_lint_false_bypasses(tmp_path):
    edl = build_edl(_mk_pr(tmp_path), overlays=[
        {"file": "x.mp4", "start_in_output": 3.0, "duration": 99.0}])  # 越界
    p = save_edl(edl, tmp_path / "edl.json")
    got = load_edl(p, run_lint=False)    # 调试/迁移通道：跳过闸门不抛
    assert got["overlays"]
