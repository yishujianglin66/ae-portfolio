# -*- coding: utf-8 -*-
"""render_audit 纯函数测试——不落盘、不跑 ffmpeg、不碰真实规则库。"""
import json
from scripts.render_audit import (
    build_audit,
    camera_stats,
    cuts_stats,
    parse_gate_stdout,
    speed_stats,
)


def _segs():
    return [
        {"start_time": 1.0, "speed": 1.0, "zoompan_effect": "zoom_in"},
        {"start_time": 1.4, "speed": 1.5, "zoompan_effect": "static"},
        {"start_time": 2.0, "speed": 1.0, "zoompan_effect": "zoom_in"},
        {"start_time": 2.5, "speed": 0.55, "zoompan_effect": "push"},
    ]


def test_parse_gate_stdout():
    out = ("  [PASS] 无削波: 0.98\n"
           "  [FAIL] 切点可见: 3/5\n"
           "\n闸门: 1/2 通过 ❌ REJECT")
    g = parse_gate_stdout(out)
    assert g["pass"] == 1
    assert g["total"] == 2
    assert g["accepted"] is False
    assert g["detail"]["无削波"] == "0.98"


def test_parse_gate_stdout_accept():
    g = parse_gate_stdout("[PASS] a: x\n[PASS] b: y\nACCEPT")
    assert g["pass"] == 2 and g["total"] == 2 and g["accepted"] is True


def test_cuts_stats():
    c = cuts_stats(_segs())
    assert c["n"] == 4
    assert c["min_gap"] == 0.4 and c["max_gap"] == 0.6
    assert c["median_gap"] == 0.5


def test_speed_stats():
    s = speed_stats(_segs())
    assert s["jumps"] == 3          # 1.0->1.5, 1.5->1.0, 1.0->0.55 三处 >=0.4
    assert s["dist"]["1.0"] == 2


def test_camera_stats():
    cam = camera_stats(_segs(), {"a": {"motion": "zoom_in"},
                                 "b": {"motion": "zoom_in"}})
    assert cam["technique_dist"] == {"zoom_in": 2, "static": 1, "push": 1}
    assert cam["motion_label_dist"] == {"zoom_in": 2}


def test_build_audit_aggregates_without_gate(tmp_path):
    (tmp_path / "production_report.json").write_text(
        json.dumps({"render_success": True,
                    "script": {"segments": _segs()}}), encoding="utf-8")
    (tmp_path / "unified_report.json").write_text(
        json.dumps({"scores": {"score_overall": 7.3},
                    "elapsed_s": 100.0}), encoding="utf-8")
    rec = build_audit(tmp_path, "runX", run_gate=False)
    assert rec["schema"] == "render_audit_v1"
    assert rec["run_tag"] == "runX"
    assert rec["cuts"]["n"] == 4
    assert rec["score"]["score_overall"] == 7.3
    assert rec["meta"]["render_success"] is True
    assert rec["meta"]["elapsed_s"] == 100.0
    assert rec["gate"]["pass"] is None          # --no-gate
    assert isinstance(rec["rules"], list)


def test_build_audit_missing_artifacts_failsoft(tmp_path):
    rec = build_audit(tmp_path, "runY", run_gate=False)
    assert rec["cuts"]["n"] == 0
    assert rec["score"] == {}
    assert rec["meta"]["render_success"] is None
    assert isinstance(rec["rules"], list)