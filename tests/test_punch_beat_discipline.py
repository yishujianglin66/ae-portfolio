# -*- coding: utf-8 -*-
"""脉冲运镜撞击的踩点纪律单测 (2026-09-19)。

用户听感反馈「镜头动感拉镜不如之前踩点」的量化定位:

    版本        撞击   密度     强鼓占比   包络占空比
    run53 母版    3   0.10/s    33.3%        5%
    20s 集成版   22   1.10/s    18.2%       50%
    27s v4(吐槽) 54   2.00/s    31.5%       92%

包络占空比 = Σ(撞击次数 × 11 帧包络) / 总帧数。92% 意味着缩放几乎从不回落,
相邻撞击叠成持续晃动, 眼睛读不出离散"命中" → 听感"不踩点"。

根因: `seg.onset_times` 直接取自 `_onsets`(= 全部鼓锚, 无强度过滤 + 全部
旋律锚)。0-27s 该源 ~10 事件/秒, 而人耳感知的强拍(kick/snare ≥0.5)只有
1.07/s —— 三分之二的撞击打在弱鼓点或旋律音上。

修复: 撞击触发源收敛为强鼓锚 (PUNCH_STRENGTH_DEFAULT=0.5); 旋律锚按
2026-09-05 需求范围处理 (默认 off, 见 _punch_melody_allowed 文档);
相邻撞击最小间隔 4→8 帧, 让包络走完再下一次。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.production_director import (  # noqa: E402
    MELODY_PUNCH_STRENGTH_DEFAULT,
    PUNCH_ELIGIBLE_EFFECTS,
    PUNCH_ENVELOPE,
    PUNCH_STRENGTH_DEFAULT,
    ProductionDirector,
    punch_onsets_from_anchors,
)


def _events():
    return {
        "kick":  [(1.000, 0.90), (2.000, 0.30), (3.000, 0.50)],
        "snare": [(1.500, 0.80), (2.500, 0.49), (4.000, 0.65)],
    }


def test_strength_floor_filters_weak_hits():
    """默认 0.5: 弱鼓点(0.30/0.49)不进触发源, 边界值 0.50 进。"""
    got = punch_onsets_from_anchors(_events())
    assert got == [1.0, 1.5, 3.0, 4.0], got
    assert PUNCH_STRENGTH_DEFAULT == 0.5


def test_strength_floor_tunable():
    """阈值可调: 0.3 → 弱击纳入; 0.85 → 仅最强。"""
    assert punch_onsets_from_anchors(_events(), 0.30) == [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    assert punch_onsets_from_anchors(_events(), 0.85) == [1.0]


def test_kick_snare_simultaneous_deduped():
    """同刻 kick+snare 去重为单次触发 (避免一次重击触发两遍)。"""
    ev = {"kick": [(1.0, 0.9)], "snare": [(1.0, 0.9)]}
    assert punch_onsets_from_anchors(ev) == [1.0]


def test_missing_kind_tolerated():
    """缺 snare 键或空表不抛异常 (fail-safe)。"""
    assert punch_onsets_from_anchors({"kick": [(1.0, 0.9)]}) == [1.0]
    assert punch_onsets_from_anchors({}) == []


def _scope(mood: str, scope: str) -> bool:
    d = ProductionDirector.__new__(ProductionDirector)
    d._melody_punch_scope = scope
    return ProductionDirector._punch_melody_allowed(d, mood)


def test_melody_scope_off_available():
    """scope=off 仍可用 (纯打击乐; 上一轮行为), 但已不是默认。"""
    for mood in ("intro", "build", "drop", "climax", "outro"):
        assert _scope(mood, "off") is False


def test_melody_scope_drop_limits_to_climax():
    """scope=drop: 仅高潮段跟随小提琴 (2026-09-05 需求的原始范围)。"""
    assert _scope("drop", "drop") is True
    assert _scope("climax", "drop") is True
    assert _scope("build", "drop") is False


def test_melody_scope_default_is_segmented():
    """默认(未设 scope)是 **segmented**: 铺垫/蓄力段跟旋律重音，爆发段只落强鼓点。

    需求演变（都来自用户原话，记录以免来回摇摆）：
      2026-09-19 「不够, 没跟小提琴节奏变换, 视觉冲击力不到位」→ 默认改 all
      2026-09-24 「要纯, 能完美踩点」                          → 默认改 off
      2026-09-24 「铺垫段(前 14.5s)完全没撞击」                 → 默认改 **segmented**
        （这段 BGM 首个强鼓点在 14.5s，纯打击乐会让铺垫段 0 撞击；用户选铺垫段例外。）
    注意：旋律锚**仍全量驱动切点池**；本测试只锁撞击触发源，不涉及切点。
    """
    d = ProductionDirector.__new__(ProductionDirector)   # 不设 _melody_punch_scope
    assert ProductionDirector._punch_melody_allowed(d, "intro") is True
    assert ProductionDirector._punch_melody_allowed(d, "build") is True
    for mood in ("drop", "climax", "outro"):
        assert ProductionDirector._punch_melody_allowed(d, mood) is False, mood


def test_melody_scope_override_still_available():
    """裁决可回退：显式设 scope=off/all/drop 仍可切换（不改代码即可回退）"""
    d = ProductionDirector.__new__(ProductionDirector)
    d._melody_punch_scope = "all"
    assert ProductionDirector._punch_melody_allowed(d, "intro") is True
    d._melody_punch_scope = "off"
    for mood in ("intro", "drop", "climax"):
        assert ProductionDirector._punch_melody_allowed(d, mood) is False
    d._melody_punch_scope = "drop"
    assert ProductionDirector._punch_melody_allowed(d, "drop") is True
    assert ProductionDirector._punch_melody_allowed(d, "intro") is False


def test_melody_trigger_needs_strength_floor():
    """跟小提琴 ≠ 接全部旋律音: 全量旋律 4.4-5.9/s 与包络必然重叠。

    这是"精选重音/音变点"的量化依据 —— 取 P80≈0.87 后约 1 事件/秒,
    与 7 帧包络叠加后不重叠; 全量旋律则必然重叠。
    """
    fps, envelope = 24.0, PUNCH_ENVELOPE
    all_melody = 1.0 / 5.92      # 全量旋律锚在爆发段 5.92/s
    salient = 1.0 / 1.15         # 强度≥0.85 的精选旋律事件 ~1.15/s
    assert all_melody * fps < envelope       # 全量: 必然重叠 (所以不能全接)
    assert salient * fps > envelope          # 精选: 不重叠 (所以能跟小提琴)


def test_melody_strength_default_is_p80():
    """默认旋律门槛落在 P80 档 (0.85), 与"结构性重音"语义一致。"""
    assert MELODY_PUNCH_STRENGTH_DEFAULT == 0.85


def test_static_shots_can_carry_punch():
    """static 纳入可撞击类型: 落在静止镜头上的小提琴重音不该被忽略。"""
    assert "static" in PUNCH_ELIGIBLE_EFFECTS
    assert "push" in PUNCH_ELIGIBLE_EFFECTS and "zoom_in" in PUNCH_ELIGIBLE_EFFECTS
    # 平移类仍不承载撞击 (基础运镜与撞击叠加会互相干扰)
    for fx in ("pan_left", "pan_right", "diag_pan"):
        assert fx not in PUNCH_ELIGIBLE_EFFECTS
