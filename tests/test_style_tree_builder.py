# -*- coding: utf-8 -*-
"""StyleTreeBuilder 单元测试（M4 验收，[AE-sync]）

覆盖：
  1. 8 张风格卡 → 基础模板映射（真实 data/style_cards/ 数据）
  2. text_fx.action 显式优先于三旋钮推导
  3. 三旋钮单调性：motion→入场档、variance→特效激进、density→文案层数
  4. content 覆盖（title/colors/duration）与未知卡回退
  5. BeatGrid 预埋 beat_events（M3 联动）
  6. build() 自动分派（style_id vs prompt）
  7. prompt 入口：LLM mock 路径 + 关键词离线兜底（honest degradation）
  8. 所有构建产物通过 validate_composition_tree
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.beatlock import BeatGrid
from core.composition_tree import build_template, validate_composition_tree
from core.style_tree_builder import (
    _STYLE_TO_BASE,
    _TEXTFX_TO_ENTRANCE,
    BuildResult,
    StyleTreeBuilder,
)


def _builder(**kw):
    return StyleTreeBuilder(**kw)


# ── 1. 真实风格卡 → 基础模板 ─────────────────────────────────────────
@pytest.mark.parametrize("style_id,expected_base", [
    ("amv_highenergy", "amv"),
    ("hardcore_battle", "amv"),
    ("cyberpunk", "cyberpunk"),
    ("ambient_calm", "ambient"),
    ("emotional_lyric", "ambient"),
    ("high_key_bright", "ambient"),
    ("vintage_film", "ambient"),
    ("cinematic_film", "ambient"),
])
def test_real_cards_map_to_base(style_id, expected_base):
    result = _builder().build_from_card(style_id)
    assert result.base_template == expected_base
    assert result.style_id == style_id
    assert result.tree.style_card == expected_base
    assert result.offline
    res = validate_composition_tree(result.tree)
    assert res["ok"], res["errors"]


def test_real_cards_all_pass_validation():
    for style_id in _STYLE_TO_BASE:
        result = _builder().build_from_card(style_id)
        res = validate_composition_tree(result.tree)
        assert res["ok"], f"{style_id}: {res['errors']}"


# ── 2. text_fx 显式优先 ─────────────────────────────────────────────
def test_textfx_action_wins_over_knobs():
    # 低 motion(2) 本应 fade_in，但 text_fx impact 显式 → scale_bounce
    card = {"style_id": "amv_highenergy", "motion_intensity": 2,
            "visual_variance": 5, "information_density": 4,
            "text_fx": [{"engine": "textImpactMaster", "action": "impact"}]}
    result = _builder().build_from_card(card)
    texts = [l for l in result.tree.layers if l.type == "text"]
    assert texts and texts[0].animations["entrance"].preset == "scale_bounce"


def test_textfx_mapping_table():
    assert _TEXTFX_TO_ENTRANCE["impact"] == "scale_bounce"
    assert _TEXTFX_TO_ENTRANCE["glitch"] == "glitch_shake"
    assert _TEXTFX_TO_ENTRANCE["fade"] == "fade_in"


# ── 3. 三旋钮单调性 ─────────────────────────────────────────────────
def _synthetic_card(mi=5, vv=5, info=4):
    return {"style_id": "amv_highenergy", "motion_intensity": mi,
            "visual_variance": vv, "information_density": info}


def test_motion_intensity_tiers():
    low = _builder().build_from_card(_synthetic_card(mi=2))
    mid = _builder().build_from_card(_synthetic_card(mi=5))
    high = _builder().build_from_card(_synthetic_card(mi=9))
    p = lambda r: [l for l in r.tree.layers if l.type == "text"][0]
    assert p(low).animations["entrance"].preset == "fade_in"
    assert p(mid).animations["entrance"].preset == "slide_up"
    assert p(high).animations["entrance"].preset == "scale_bounce"
    assert p(low).animations["entrance"].duration_ms > \
           p(high).animations["entrance"].duration_ms


def test_visual_variance_gates_rgb_split():
    high = _builder().build_from_card(_synthetic_card(vv=9))
    low = _builder().build_from_card(_synthetic_card(vv=2))
    texts_h = [l for l in high.tree.layers if l.type == "text"]
    texts_l = [l for l in low.tree.layers if l.type == "text"]
    assert any(e.value == "rgb_split" for e in texts_h[0].effects)
    assert not any(e.value == "rgb_split" for e in texts_l[0].effects)
    # 低 variance 收敛：amv 标题的 neon_glow 被剥离
    assert not any(e.value == "neon_glow" for e in texts_l[0].effects)


def test_information_density_controls_subtitle():
    keep = _builder().build_from_card(_synthetic_card(info=5))
    drop = _builder().build_from_card(_synthetic_card(info=1))
    n_text = lambda r: len([l for l in r.tree.layers if l.type == "text"])
    assert n_text(keep) == 2       # amv 模板 title + sub 保留
    assert n_text(drop) == 1       # 低密度收敛为单文字层


def test_intensity_injected_to_combos():
    result = _builder().build_from_card("cyberpunk")   # mi=7 → intense
    texts = [l for l in result.tree.layers if l.type == "text"]
    cyber_glow = next(e for e in texts[0].effects if e.value == "cyber_glow")
    assert cyber_glow.params.get("intensity") == "intense"


# ── 4. content 覆盖与未知卡 ──────────────────────────────────────────
def test_content_overrides():
    result = _builder().build_from_card("amv_highenergy", {
        "title": "我的标题", "subtitle": "副标",
        "colors": {"main": "#123456", "glow": "#ABCDEF", "accent": "#FFFFFF"},
        "duration": 8.0,
    })
    tree = result.tree
    assert tree.duration == 8.0
    texts = sorted([l for l in tree.layers if l.type == "text"],
                   key=lambda l: l.z_index)
    assert texts[0].content["text"] == "我的标题"
    assert texts[1].content["text"] == "副标"
    assert texts[0].content["colors"]["main"] == "#123456"
    res = validate_composition_tree(tree)
    assert res["ok"], res["errors"]


def test_unknown_card_falls_back_ambient():
    result = _builder().build_from_card("no_such_card_xyz")
    assert result.base_template == "ambient"
    assert result.tree.style_card == "ambient"
    assert any("回退" in w for w in result.warnings)
    assert validate_composition_tree(result.tree)["ok"]


# ── 5. 节拍预埋 ─────────────────────────────────────────────────────
def test_grid_seed_beat_events():
    grid = BeatGrid(kick=[0.5, 1.5], strong=[1.0, 9.9])  # 9.9 越界
    result = _builder().build_from_card("amv_highenergy", grid=grid)
    evs = result.tree.beat_events
    kicks = [e for e in evs if e["beat_type"] == "kick"]
    strongs = [e for e in evs if e["beat_type"] == "strong"]
    assert len(kicks) >= 2 and len(strongs) >= 1
    # 越界拍点被丢弃
    assert all(e["time"] <= result.tree.duration for e in evs)
    # 锚定图层真实存在
    layer_ids = {l.id for l in result.tree.layers}
    assert all(e["layer_id"] in layer_ids for e in evs if e["layer_id"])
    assert any("beat_seed" in t for t in result.trace)


# ── 6. build() 自动分派 ─────────────────────────────────────────────
def test_build_auto_dispatch():
    # 下划线串 → 风格 id 路径
    r1 = _builder().build("amv_highenergy")
    assert r1.base_template == "amv"
    # 自然语言 → prompt 路径（llm 关闭 → 关键词兜底）
    r2 = _builder(llm_enabled=False).build("做一个赛博朋克风的标题动画")
    assert r2.base_template == "cyberpunk"
    assert r2.offline


# ── 7. prompt 双路径 ────────────────────────────────────────────────
def test_prompt_offline_keywords():
    b = _builder(llm_enabled=False)
    r = b.build_from_prompt("高燃战斗混剪片头，标题「FINAL CLASH」")
    assert r.style_id == "amv_highenergy"
    assert r.offline
    texts = sorted([l for l in r.tree.layers if l.type == "text"],
                   key=lambda l: l.z_index)
    assert texts[0].content["text"] == "FINAL CLASH"   # 引号短语提取
    assert any("offline" in w or "关键词" in w for w in r.warnings)


def test_prompt_llm_path_mocked():
    import core.llm_gateway as lg_mod

    async def fake_chat(**kwargs):
        return lg_mod.LLMResponse(
            success=True,
            content='{"style_id": "cyberpunk", "title": "霓虹之城", '
                    '"subtitle": "2077", "duration": 6, '
                    '"colors": {"main": "#00FFFF", "glow": "#00AAFF", "accent": "#FFFFFF"}}',
            model="fake-llm", provider="fake")

    original = lg_mod.llm_gateway.chat
    lg_mod.llm_gateway.chat = fake_chat
    try:
        r = _builder(llm_enabled=True).build_from_prompt("赛博城市标题")
        assert not r.offline
        assert r.style_id == "cyberpunk"
        assert r.tree.duration == 6.0
        texts = sorted([l for l in r.tree.layers if l.type == "text"],
                       key=lambda l: l.z_index)
        assert texts[0].content["text"] == "霓虹之城"
        assert texts[0].content["colors"]["main"] == "#00FFFF"
    finally:
        lg_mod.llm_gateway.chat = original


def test_prompt_llm_failure_falls_back():
    import core.llm_gateway as lg_mod

    async def broken_chat(**kwargs):
        return lg_mod.LLMResponse(success=False, error="no key")

    original = lg_mod.llm_gateway.chat
    lg_mod.llm_gateway.chat = broken_chat
    try:
        r = _builder(llm_enabled=True).build_from_prompt("做一个抒情慢节奏的片尾")
        assert r.offline
        assert r.style_id == "ambient_calm"
        assert any("兜底" in w for w in r.warnings)
    finally:
        lg_mod.llm_gateway.chat = original


# ── 8. 与 M1b/M3 链路的兼容性 ────────────────────────────────────────
def test_tree_feeds_orchestrator_and_beatlock():
    from core.beatlock import BeatLock
    from core.synthesis_orchestrator import JsxProjectBuilder
    result = _builder().build_from_card("amv_highenergy")
    jsx = JsxProjectBuilder().build(result.tree)
    assert "addComp" in jsx and 'status:"success"' in jsx
    # M3 可继续富化该树（BeatLock 只读新树的 beat_events）
    grid = BeatGrid(kick=[0.5], strong=[1.0])
    locked = BeatLock().apply(result.tree, grid)
    assert locked.tree is not result.tree
    assert validate_composition_tree(locked.tree)["ok"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
