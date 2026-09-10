# -*- coding: utf-8 -*-
"""rule_registry 状态机测试（§7.3 治理机制）——纯函数，不落盘不碰真实规则库。"""
from scripts.rule_registry import (
    DEMOTE_THRESHOLD,
    PROMOTE_THRESHOLD,
    RETIRE_THRESHOLD,
    evaluate_status,
    rule_applies,
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


# ── applicability 校验（2026-09-09 修复：此前从未被校验） ──────────────

def _rule_with_app(style=None, duration=None, structure=None):
    ap = {}
    if style:
        ap["style"] = style
    if duration:
        ap["duration_range"] = duration
    if structure:
        ap["bgm_structure"] = structure
    r = _rule(status="active")
    r["applicability"] = ap
    return r


def test_applies_no_context_is_permissive():
    """context=None → 一律放行（向后兼容旧调用）。"""
    r = _rule_with_app(style=["amv_highenergy"], duration=[15, 45])
    assert rule_applies(r, None) is True


def test_applies_empty_applicability_always_true():
    r = _rule(status="active")
    r["applicability"] = {}
    assert rule_applies(r, {"style": "anything", "duration": 999}) is True


def test_applies_style_match():
    r = _rule_with_app(style=["amv_highenergy", "燃向"])
    assert rule_applies(r, {"style": "amv_highenergy"}) is True
    assert rule_applies(r, {"style": "AMV_HIGHENERGY"}) is True   # 大小写不敏感


def test_applies_style_mismatch_rejects():
    r = _rule_with_app(style=["amv_highenergy"])
    assert rule_applies(r, {"style": "emotional_lyric"}) is False


def test_applies_duration_in_range():
    r = _rule_with_app(duration=[15, 45])
    assert rule_applies(r, {"duration": 30}) is True
    assert rule_applies(r, {"duration": 15}) is True   # 边界含
    assert rule_applies(r, {"duration": 45}) is True


def test_applies_duration_out_of_range_rejects():
    r = _rule_with_app(duration=[15, 45])
    assert rule_applies(r, {"duration": 60}) is False
    assert rule_applies(r, {"duration": 10}) is False


def test_applies_structure_intersection():
    r = _rule_with_app(structure=["intro", "build", "drop"])
    assert rule_applies(r, {"bgm_structure": "drop"}) is True
    assert rule_applies(r, {"bgm_structure": ["intro", "drop"]}) is True
    assert rule_applies(r, {"bgm_structure": "outro"}) is False


def test_applies_context_missing_dimension_skips():
    """context 未提供的维度不约束。"""
    r = _rule_with_app(style=["amv_highenergy"], duration=[15, 45])
    assert rule_applies(r, {"duration": 30}) is True   # 未给 style
    assert rule_applies(r, {"style": "x"}) is False     # 给了 style 且不匹配


def test_applies_malformed_duration_does_not_crash():
    r = _rule_with_app()
    r["applicability"] = {"duration_range": ["a", "b"]}
    assert rule_applies(r, {"duration": 30}) is True   # 声明不可解析 → 不约束