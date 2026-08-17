"""tests/test_transition_taxonomy.py — EBU SKOS 对齐的转场类型分类法测试"""
from __future__ import annotations

import pytest


def test_taxonomy_has_quantified_schema():
    """每个转场都有 kind/default_dur/rhythm_fit 量化字段 (修复'无量化 schema'缺口)"""
    from knowledge.transition_taxonomy import TRANSITION_TAXONOMY
    assert len(TRANSITION_TAXONOMY) >= 12
    for t in TRANSITION_TAXONOMY:
        assert t.code and t.name_zh
        assert t.kind in {"cut", "dissolve", "wipe", "motion", "stylize"}
        assert t.default_dur >= 0.0
        assert t.rhythm_fit, f"{t.code} 缺 rhythm_fit"


def test_get_transition_case_insensitive():
    from knowledge.transition_taxonomy import get_transition
    assert get_transition("fade_white") is get_transition("FADE_WHITE")
    assert get_transition("cut").name_zh == "硬切"
    assert get_transition("NOPE") is None


def test_cut_has_no_xfade():
    from knowledge.transition_taxonomy import get_transition
    assert get_transition("CUT").xfade is None
    assert get_transition("CUT").default_dur == 0.0


def test_list_for_rhythm():
    from knowledge.transition_taxonomy import list_for_rhythm
    beat = {t.code for t in list_for_rhythm("beat")}
    assert "CUT" in beat
    impact = {t.code for t in list_for_rhythm("impact")}
    assert "FADE_WHITE" in impact or "ZOOM_UP" in impact
    structural = {t.code for t in list_for_rhythm("structural")}
    assert "FADE_BLACK" in structural


def test_consistency_with_production_xfade_map():
    """分类法的滤镜名/时长必须与 production_director.XFADE_MAP 一致"""
    from ai.production_director import XFADE_MAP
    from knowledge.transition_taxonomy import validate_xfade_consistency
    problems = validate_xfade_consistency(XFADE_MAP)
    assert problems == [], f"分类法与 XFADE_MAP 不一致: {problems}"


def test_cross_dissolve_is_true_fade():
    """真·叠化必须映射到 ffmpeg fade 滤镜 (不是 fadeblack 淡黑)"""
    from ai.production_director import XFADE_MAP
    from knowledge.transition_taxonomy import get_transition
    cd = get_transition("CROSS_DISSOLVE")
    assert cd.xfade == "fade"
    assert XFADE_MAP["cross_dissolve"] == ("fade", 0.30)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
