"""tests/test_evidence_gate_compliance.py — 证据闸门合规自检工具链单元测试"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evidence_gate_compliance_audit import (  # noqa: E402
    AuditSpec,
    _sha256,
    gate1_existence,
    gate2_first_line,
    gate3_alignment,
    gate4_snapshot,
    gate5_manifest,
    run_audit,
)


def _write_jsonl(path: Path, labels):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for lb in labels:
            f.write(json.dumps({"shot_id": f"s{lb}", "label": lb},
                               ensure_ascii=False) + "\n")


@pytest.fixture
def label_file(tmp_path):
    p = tmp_path / "labels.jsonl"
    _write_jsonl(p, ["meta-static"] * 3 + ["meta-zoom"] * 5)
    return p


# ── 闸门1 存在性 ──────────────────────────────────────────────
def test_gate1_all_files_exist(tmp_path):
    f = tmp_path / "a.jsonl"
    _write_jsonl(f, ["x"])
    spec = AuditSpec(files=[str(f)])
    r = gate1_existence(spec)
    assert r.passed
    assert r.checks[0]["status"] == "OK"
    assert r.checks[0]["lines"] == 1


def test_gate1_missing_file_fails(tmp_path):
    spec = AuditSpec(files=[str(tmp_path / "ghost.jsonl")])
    r = gate1_existence(spec)
    assert not r.passed
    assert r.checks[0]["status"] == "MISS"


def test_gate1_no_files_declared_skips():
    r = gate1_existence(AuditSpec(files=[]))
    assert r.passed
    assert r.checks[0]["status"] == "SKIP"


# ── 闸门2 首行证据 ────────────────────────────────────────────
def test_gate2_captures_first_line_and_distribution(label_file):
    spec = AuditSpec(label_file=str(label_file), label_field="label")
    r = gate2_first_line(spec)
    assert r.passed
    c = r.checks[0]
    assert c["n_rows"] == 8
    assert c["distribution"]["meta-zoom"]["count"] == 5
    assert "shot_id" in c["first_line"]
    assert "label" in c["fields"]


def test_gate2_empty_file_fails(tmp_path):
    p = tmp_path / "empty.jsonl"
    p.write_text("", encoding="utf-8")
    r = gate2_first_line(AuditSpec(label_file=str(p)))
    assert not r.passed


def test_gate2_no_label_file_skips():
    r = gate2_first_line(AuditSpec())
    assert r.passed
    assert r.checks[0]["status"] == "SKIP"


# ── 闸门3 三对齐 ─────────────────────────────────────────────
def test_gate3_aligned(label_file):
    spec = AuditSpec(label_file=str(label_file),
                     expected_classes=["meta-static", "meta-zoom"],
                     num_classes=2)
    r = gate3_alignment(spec)
    assert r.passed
    assert any("CHECK" in str(c.get("status", "")) for c in r.checks)


def test_gate3_class_mismatch_fails(label_file):
    spec = AuditSpec(label_file=str(label_file),
                     expected_classes=["meta-static", "meta-pan"],
                     num_classes=2)
    r = gate3_alignment(spec)
    assert not r.passed
    assert any("CROSS" in str(c.get("status", "")) for c in r.checks)


def test_gate3_num_classes_mismatch_fails(label_file):
    spec = AuditSpec(label_file=str(label_file),
                     expected_classes=["meta-static", "meta-zoom"],
                     num_classes=4)   # 与类名清单长度不符
    r = gate3_alignment(spec)
    assert not r.passed


# ── 闸门4 快照失效 ────────────────────────────────────────────
def test_gate4_baseline_then_fresh_and_stale(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"v1")
    out = tmp_path / "out"
    spec = AuditSpec(files=[str(f)])

    # 首次: 基线
    r1 = gate4_snapshot(spec, out, None)
    assert r1.passed
    assert r1.checks[-1]["status"] == "BASELINE"
    prev = json.loads((out / "snapshot.json").read_text(encoding="utf-8"))
    assert prev["hashes"]["data.bin"] == _sha256(f)

    # 未变化: FRESH
    r2 = gate4_snapshot(spec, out, prev)
    assert r2.passed
    assert r2.checks[-1]["status"] == "FRESH"

    # 产物变化: STALE + 待重测
    f.write_bytes(b"v2-changed")
    r3 = gate4_snapshot(spec, out, prev)
    assert r3.passed
    last = r3.checks[-1]
    assert last["status"] == "STALE"
    assert "data.bin" in last["changed_files"]
    assert "待重测" in last["action"]


# ── 闸门5 PLAN/READY 分级 ─────────────────────────────────────
def test_gate5_valid_levels(tmp_path):
    f = tmp_path / "ready.txt"
    f.write_text("ok", encoding="utf-8")
    spec = AuditSpec(manifest=[
        {"item": "已验证产物", "level": "READY", "file": str(f)},
        {"item": "计划中", "level": "PLAN"},
    ])
    r = gate5_manifest(spec)
    assert r.passed


def test_gate5_invalid_level_fails():
    spec = AuditSpec(manifest=[{"item": "x", "level": "DONE"}])
    r = gate5_manifest(spec)
    assert not r.passed


def test_gate5_ready_missing_file_fails(tmp_path):
    spec = AuditSpec(manifest=[
        {"item": "声称已验证", "level": "READY",
         "file": str(tmp_path / "nope.bin")},
    ])
    r = gate5_manifest(spec)
    assert not r.passed


# ── 端到端 ───────────────────────────────────────────────────
def test_run_audit_writes_reports(tmp_path, label_file):
    spec = AuditSpec(
        title="单元测试审计",
        files=[str(label_file)],
        label_file=str(label_file),
        expected_classes=["meta-static", "meta-zoom"],
        num_classes=2,
        manifest=[{"item": "标签集", "level": "READY", "file": str(label_file)}],
    )
    out = tmp_path / "reports"
    report = run_audit(spec, out)
    assert report["overall"] == "PASS"
    assert (out / "compliance_report.json").exists()
    md = (out / "compliance_report.md").read_text(encoding="utf-8")
    assert "GB/T 47507-2026" in md
    assert "GB/T 45652-2025" in md
    assert "PASS" in md


def test_run_audit_fails_on_missing_file(tmp_path, label_file):
    spec = AuditSpec(
        files=[str(label_file), str(tmp_path / "ghost.jsonl")],
        label_file=str(label_file),
    )
    report = run_audit(spec, tmp_path / "reports")
    assert report["overall"] == "FAIL"
    gate1 = report["gates"][0]
    assert not gate1["passed"]


def test_audit_spec_from_dict_ignores_unknown_fields():
    spec = AuditSpec.from_dict({"title": "t", "bogus_field": 1})
    assert spec.title == "t"
    assert not hasattr(spec, "bogus_field")
