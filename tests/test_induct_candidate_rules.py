# -*- coding: utf-8 -*-
"""R8③ 候选规则归纳契约测试 (2026-09-19)。

R8③（DSPy GEPA 归纳路径）的首轮落地。本测试锁死三条设计红线 —— 它们是
"归纳产物不得污染治理"的关键，退化会让规则库变成不可信的黑盒：

  1. 候选**不得**绕过 `rule_registry` 的 schema 闸门：带实测证据的候选必须能通过
     `validate_schema`；无证据的候选必须**没有** gate_score_delta（防止拿空字符串
     骗过闸门）。
  2. 无证据的候选必须显式给出"该测什么指标 + 怎么测"（evidence_gap），
     否则它只是一句无法验证的口号。
  3. 每条候选都要有日志证据链（source_runs / n_evidence），不能在无凭据时凭空产出。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "induct_candidate_rules", PROJECT / "scripts" / "induct_candidate_rules.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def built():
    m = _mod()
    cands, blocked = m.build_candidates()
    return m, cands, blocked


def test_candidates_have_evidence_chain(built):
    """每条候选都要有证据链，不能凭空产出。"""
    _, cands, _ = built
    assert cands, "应至少归纳出一条候选"
    for c in cands:
        assert c["evidence"]["n_evidence"] >= 1, c["rule_id"]
        assert c["rule_id"].startswith("R-"), c["rule_id"]


def test_measured_candidates_pass_registry_schema(built):
    """带实测 delta 的候选必须是 schema 合法的 —— 否则交给投票也转不了正。"""
    _, cands, _ = built
    from scripts.rule_registry import validate_schema
    measured = [c for c in cands if c["evidence"].get("gate_score_delta")]
    assert measured, "本轮应至少有 1 条带实测证据的候选"
    for c in measured:
        errs = validate_schema(c)
        assert not errs, f"{c['rule_id']} schema 不过: {errs}"


def test_blocked_candidates_have_no_gate_delta(built):
    """无证据/实测反例的候选不得携带 gate_score_delta（否则会骗过 schema 闸门转 active）。

    blocked 有两种合法形态:
      blocked_pending_measurement — 还没测 (只有指标与命令)
      failed_threshold            — 测了但不满足陈述 (数值留在 failed_measurement)
    两者都必须过不了闸门 —— 这正是"不许转正"的机制保证。
    """
    _, cands, blocked = built
    assert blocked, "本轮应有待测量/反例候选（诚实标注）"
    from scripts.rule_registry import validate_schema
    for c in blocked:
        assert not c["evidence"].get("gate_score_delta"), c["rule_id"]
        assert c["evidence_gap"]["status"] in (
            "blocked_pending_measurement", "failed_threshold"), c["rule_id"]
        assert validate_schema(c), f"{c['rule_id']} 竟通过了闸门（不应）"


def test_failed_threshold_keeps_measurement(built):
    """实测反例必须保留数值与阈值 —— 测出反例却不留档等于白测。"""
    _, cands, blocked = built
    failed = [c for c in blocked
              if c["evidence_gap"]["status"] == "failed_threshold"]
    assert failed, "source_repeat 主题应有一条实测反例 (单源占比 10% > 8%)"
    for c in failed:
        gap = c["evidence_gap"]
        assert gap.get("failed_measurement"), c["rule_id"]
        assert gap.get("evidence_path"), c["rule_id"]


def test_blocked_candidates_state_metric_and_command(built):
    """待测量候选必须写明指标与测量命令。"""
    _, _, blocked = built
    for c in blocked:
        gap = c["evidence_gap"]
        assert gap.get("metric"), c["rule_id"]
        assert gap.get("measure_cmd"), c["rule_id"]
        assert gap.get("why"), c["rule_id"]


def test_covered_theme_is_marked(built):
    """已被在库规则覆盖的主题必须标 covered_by（避免一题两规）。"""
    _, cands, _ = built
    by_theme = {c["induction"]["theme_id"]: c for c in cands}
    assert by_theme["cut_soft"]["induction"]["covered_by"], \
        "切点主题应被 R-2026-000x 覆盖"


def test_every_candidate_carries_sample_verdicts(built):
    """候选要能回溯到日志原话（人可审计）。"""
    _, cands, _ = built
    for c in cands:
        assert c["induction"]["sample_verdicts"], c["rule_id"]


def test_acceptance_log_meets_gepa_threshold():
    """GEPA 数据前置：acceptance_log ≥30 条，且追加通道可用。"""
    m = _mod()
    rows = m._log_rows()
    assert len(rows) >= 30, f"acceptance_log 仅 {len(rows)} 条 (<30)"


def test_log_acceptance_append_is_dedup_safe(tmp_path, monkeypatch):
    """追加通道必须幂等：同 run_tag+verdict+notes 重复提交不落双份。"""
    spec = importlib.util.spec_from_file_location(
        "log_acceptance", PROJECT / "scripts" / "log_acceptance.py")
    la = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(la)
    monkeypatch.setattr(la, "LOG", tmp_path / "acc.jsonl")
    kw = dict(run_tag="t1", verdict="v1", notes="n1", kind="user_hearing",
              source="test")
    r1 = la.append_record(**kw)
    r2 = la.append_record(**kw)
    assert r1["written"] and not r2["written"]
    assert r2["total"] == 1
    # kind 白名单
    r3 = la.append_record(run_tag="t2", verdict="v", notes="n", kind="bogus")
    assert not r3["written"]
