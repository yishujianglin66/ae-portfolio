# -*- coding: utf-8 -*-
"""单元测试: LLM 镜头设计计划校验器 (shot_design_llm)."""
import pytest

from ai.shot_design_llm import _clean_json, _validate_plan

_ARCS = [
    {"start": 0.0, "end": 13.5, "type": "intro"},
    {"start": 13.5, "end": 18.0, "type": "build"},
    {"start": 60.0, "end": 70.0, "type": "drop"},
    {"start": 75.0, "end": 85.0, "type": "drop"},
    {"start": 149.0, "end": 168.5, "type": "outro"},
]


def _good_plan():
    return {
        "global": {"punch_budget": 5, "punch_spacing_sec": 20},
        "arcs": [
            {"start": 0.0, "end": 13.5, "mood": "intro", "motion_per_10": 1,
             "cameras": ["static", "pan_left"], "punch_points": [], "notes": "铺垫"},
            {"start": 13.5, "end": 18.0, "mood": "build", "motion_per_10": 2,
             "cameras": ["static", "diag_pan"], "punch_points": [], "notes": "蓄力"},
            {"start": 60.0, "end": 70.0, "mood": "drop", "motion_per_10": 2,
             "cameras": ["static", "push"], "punch_points": [65.0], "notes": "爆发"},
            {"start": 75.0, "end": 85.0, "mood": "drop", "motion_per_10": 2,
             "cameras": ["static", "zoom_back"], "punch_points": [85.0],
             "notes": "再爆发"},            {"start": 149.0, "end": 168.5, "mood": "outro", "motion_per_10": 1,
             "cameras": ["static"], "punch_points": [], "notes": "收尾"},
        ],
    }


def test_clean_json_strips_fence():
    raw = '```json\n{"a": 1}\n```'
    assert _clean_json(raw) == {"a": 1}


def test_clean_json_handles_comment():
    raw = '{\n"a": 1 // comment\n}'
    assert _clean_json(raw) == {"a": 1}


def test_validate_good_plan_passes():
    assert _validate_plan(_good_plan(), _ARCS) is None


def test_validate_rejects_intro_punch():
    p = _good_plan()
    p["arcs"][0]["punch_points"] = [5.0]
    assert "不允许" in _validate_plan(p, _ARCS)


def test_validate_rejects_punch_spacing():
    p = _good_plan()
    p["arcs"][3]["punch_points"] = [76.0]  # 与 arc[2] 的 65.0 仅隔 11s
    assert "间隔" in _validate_plan(p, _ARCS)


def test_validate_rejects_missing_static_first():
    p = _good_plan()
    p["arcs"][0]["cameras"] = ["pan_left"]
    assert "static" in _validate_plan(p, _ARCS)


def test_validate_rejects_arc_count_mismatch():
    p = _good_plan()
    p["arcs"] = p["arcs"][:2]
    assert "数量" in _validate_plan(p, _ARCS)
