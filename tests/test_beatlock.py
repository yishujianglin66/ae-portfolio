# -*- coding: utf-8 -*-
"""BeatLock 单元测试（M3 验收，[AE-sync]）

覆盖：
  1. audiomap 解析（kick/strong/weak、hihat 排除铁律、rolls/moments/hard_stops、BPM 估算）
  2. from_mapping / from_beat_strength 构造
  3. 风格自适应动作表（amv 冲击 / ambient 柔化）
  4. 模板 beat_events 提示锚定（kick→title、snare→strong 对齐）
  5. 时间钳制与事件去重；原 tree 不可变
  6. JSX 片段生成（图层索引合法性）与契约注入 merge_jsx
  7. compose() 与 JsxProjectBuilder 合并端到端
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from core.beatlock import (
    ACTION_TYPES,
    BeatAnchor,
    BeatGrid,
    BeatLock,
    BeatLockResult,
    compose,
)
from core.composition_tree import build_template, validate_composition_tree
from core.synthesis_orchestrator import JsxProjectBuilder


# ── 1. audiomap 解析 ─────────────────────────────────────────────────
def _audiomap():
    return {
        "events": [
            {"t": 0.5, "drum": "kick", "grid": "strong"},
            {"t": 1.0, "drum": "kick", "grid": "weak"},
            {"t": 1.5, "drum": "hihat", "grid": "strong"},   # 铁律：排除
            {"t": 2.0, "drum": "hihat", "grid": "weak"},     # 铁律：排除
            {"t": 2.5, "drum": "snare", "grid": "strong"},
            {"t": 3.0, "drum": "clap", "grid": "weak"},
            {"t": 3.5, "drum": "kick", "grid": "strong"},
        ],
        "rolls": [{"start": 4.0, "end": 4.8}],
        "key_moments": [{"t": 5.0, "label": "climax"}],
        "hard_stops": [6.0, 6.0],
    }


def test_from_audiomap_parsing():
    g = BeatGrid.from_audiomap(_audiomap())
    assert g.kick == [0.5, 1.0, 3.5]
    # kick 落在 strong/weak 网格 → 同时计入（与 production_director 语义一致）
    assert g.strong == [0.5, 2.5, 3.5]
    assert g.weak == [1.0, 3.0]       # hihat 的 weak 被排除
    assert len(g.rolls) == 1 and g.rolls[0]["start"] == 4.0
    assert len(g.moments) == 1
    assert g.hard_stops == [6.0]       # 去重
    # BPM 由 kick 间隔中位数估算：gaps [0.5, 2.5] → 中位 1.5 → 40
    assert g.bpm == pytest.approx(40.0)


def test_from_mapping_and_beat_strength():
    g = BeatGrid.from_mapping({
        "kick": [1.0, 2.0], "strong": [2.0, 3.0], "weak": [4.0],
        "rolls": [], "moments": [], "hard_stops": [], "bpm": 120.0,
    })
    assert g.kick == [1.0, 2.0] and g.bpm == 120.0

    class _FakeBS:
        strong_beats = []
        medium_beats = []
        weak_beats = []
        bpm = 0.0
    _FakeBS.strong_beats = [_T(1.0), _T(3.0)]
    _FakeBS.medium_beats = [_T(2.0)]
    _FakeBS.weak_beats = [_T(4.0)]
    _FakeBS.bpm = 100.0
    g2 = BeatGrid.from_beat_strength(_FakeBS())
    assert g2.strong == [1.0, 3.0]
    assert sorted(g2.weak) == [2.0, 4.0]
    assert g2.bpm == 100.0


class _T:
    def __init__(self, t):
        self.time_sec = t


# ── 2. 风格自适应动作 ───────────────────────────────────────────────
def test_style_action_map():
    grid = BeatGrid(kick=[0.5], strong=[1.0], weak=[2.0])
    amv = build_template("amv")
    lock = BeatLock()
    anchors = lock.plan(amv, grid)
    by_type = {a.beat_type: a.action for a in anchors}
    assert by_type["kick"] == "punch"
    assert by_type["strong"] == "flash"
    assert by_type["weak"] == "pulse"
    assert all(a.action in ACTION_TYPES for a in anchors)

    ambient = build_template("ambient")
    anchors2 = lock.plan(ambient, grid)
    assert all(a.action == "pulse" for a in anchors2 if a.beat_type != "weak")
    # ambient 弱拍跳过（无 weak 锚点）
    assert not any(a.beat_type == "weak" for a in anchors2)


# ── 3. 模板提示锚定 ─────────────────────────────────────────────────
def test_template_hint_anchoring():
    grid = BeatGrid(kick=[0.21], strong=[0.99])
    amv = build_template("amv")
    lock = BeatLock()
    anchors = lock.plan(amv, grid)
    # 模板: kick@0.2→title；snare@1.0→fx_impact（snare 对齐 strong）
    kick_a = next(a for a in anchors if a.beat_type == "kick")
    strong_a = next(a for a in anchors if a.beat_type == "strong")
    assert kick_a.layer_id == "title"
    assert strong_a.layer_id == "fx_impact"


def test_layer_index_bounds():
    grid = BeatGrid(kick=[0.21], strong=[1.0], weak=[2.0], hard_stops=[3.0])
    amv = build_template("amv")
    anchors = BeatLock().plan(amv, grid)
    n = len(amv.layers)
    assert all(1 <= a.layer_index <= n for a in anchors)
    # 模板提示 kick@0.2 → title（z=1，4 层中自顶向下第 3 层）
    title_a = next(a for a in anchors if a.layer_id == "title")
    assert title_a.layer_index == 3
    # weak 默认锚定 bg（z=0 → 底层 → 索引 4 = n）
    weak_a = next(a for a in anchors if a.beat_type == "weak")
    assert weak_a.layer_id == "bg" and weak_a.layer_index == n


# ── 4. apply：树不可变 + 事件合并 ────────────────────────────────────
def test_apply_immutable_and_merge():
    grid = BeatGrid(kick=[0.5, 1.5], strong=[1.0], hard_stops=[3.0])
    amv = build_template("amv")
    n_original = len(amv.beat_events)
    original_events = [dict(e) for e in amv.beat_events]

    result = BeatLock().apply(amv, grid)
    # 原树不变
    assert len(amv.beat_events) == n_original
    assert [dict(e) for e in amv.beat_events] == original_events
    # 富化副本通过校验且事件只增不减
    assert result.tree is not amv
    res = validate_composition_tree(result.tree)
    assert res["ok"], res["errors"]
    assert len(result.tree.beat_events) >= n_original + 3
    # hard_stop 警告
    assert any("hard_stop" in w for w in result.warnings)
    # 锚点与片段非空
    assert result.anchors and result.jsx_fragment


def test_clamp_and_dedupe():
    grid = BeatGrid(kick=[0.5, 0.51, 99.0])  # 0.51 与 0.5 去重；99 越界
    amv = build_template("amv")
    result = BeatLock().apply(amv, grid)
    times = [e["time"] for e in result.tree.beat_events if e["beat_type"] == "kick"]
    assert 0.5 in times
    # 0.51 与 0.5 同类型且容差内 → 去重，不产生独立事件
    assert all(abs(t - 0.51) > 0.001 for t in times)
    # 越界拍点不进 anchor（99.0s 超出 5s 合成时长）
    assert len(result.anchors) == 2


# ── 5. JSX 生成与契约注入 ───────────────────────────────────────────
def test_emit_jsx_content():
    grid = BeatGrid(kick=[1.0])
    amv = build_template("amv")
    result = BeatLock().apply(amv, grid)
    frag = result.jsx_fragment
    assert "BeatLock" in frag
    assert "setValueAtTime" in frag
    assert "comp.layer(" in frag
    assert "ADBE Scale" in frag  # punch 是缩放冲击


def test_merge_jsx_contract():
    grid = BeatGrid(kick=[1.0])
    amv = build_template("amv")
    result = BeatLock().apply(amv, grid)
    base = JsxProjectBuilder().build(amv)
    merged = BeatLock.merge_jsx(base, result.jsx_fragment)
    # 片段在 status 赋值之前注入
    assert merged.index("BeatLock") < merged.index('_result = {status:"success"')
    # 主脚本结构未破坏
    assert "addComp" in merged and "JSON.stringify(_result)" in merged
    # 非 JsxProjectBuilder 输出 → 拒绝注入
    with pytest.raises(ValueError):
        BeatLock.merge_jsx("var x = 1;", result.jsx_fragment)


def test_compose_end_to_end():
    grid = BeatGrid(kick=[0.5], strong=[1.2])
    amv = build_template("amv")
    merged, result = compose(amv, grid)
    assert "BeatLock 节拍锚定关键帧" in merged
    assert 'addComp("AMV_HighEnergy"' in merged
    assert len(result.anchors) == 2
    assert all(a.action in ACTION_TYPES for a in result.anchors)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
