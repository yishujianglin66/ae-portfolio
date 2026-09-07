# -*- coding: utf-8 -*-
"""rule_registry 状态机测试（§7.3 治理机制）——纯函数，不落盘不碰真实规则库。"""
from scripts.rule_registry import (
    DEMOTE_THRESHOLD,
    PROMOTE_THRESHOLD,
    RETIRE_THRESHOLD,
    evaluate_status,
    validate_schema,
)


def _rule(status="standby", up=0, down=0, with_evidence=True):
    return {
        "rule_id": "R-2026-0009",
        "statement": "测试规则",
        "form": "constraint",
        "inject_point": "cut_anchor",
        "status": status,
        "votes": {"up": up, "down": down},
        "evidence": {"gate_score_delta": "+0.01 beat_hit_rate"}
        if with_evidence else {},
    }


def test_promote_standby_to_active_when_support_leads_and_evidence_present():
    r = _rule(status="standby", up=PROMOTE_THRESHOLD + 1, down=1)
    status, reason = evaluate_status(r)
    assert status == "active"
    assert reason


def test_no_promote_without_evidence():
    r = _rule(status="standby", up=PROMOTE_THRESHOLD + 1, down=1, with_evidence=False)
    status, _ = evaluate_status(r)
    assert status == "standby"


def test_demote_active_to_standby_when_downvote_overtakes():
    r = _rule(status="active", up=1, down=1 + DEMOTE_THRESHOLD)
    status, _ = evaluate_status(r)
    assert status == "standby"


def test_retire_standby_after_sustained_downvotes():
    r = _rule(status="standby", up=1, down=1 + RETIRE_THRESHOLD)
    status, _ = evaluate_status(r)
    assert status == "retired"


def test_retired_is_terminal():
    r = _rule(status="retired", up=10, down=0)
    status, _ = evaluate_status(r)
    assert status == "retired"


def test_active_demotes_gradually_not_direct_retire():
    # active 一次性拿到远超退役阈值的反对票 → 先降级 standby，而非跳级 retired
    r = _rule(status="active", up=0, down=RETIRE_THRESHOLD + 3)
    status, _ = evaluate_status(r)
    assert status == "standby"


def test_stays_put_below_threshold():
    r = _rule(status="active", up=5, down=5)
    status, _ = evaluate_status(r)
    assert status == "active"


def test_validate_schema_requires_quantified_evidence():
    errs = validate_schema(_rule(with_evidence=False))
    assert any("gate_score_delta" in e for e in errs)