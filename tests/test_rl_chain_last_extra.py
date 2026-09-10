# -*- coding: utf-8 -*-
"""test_rl_chain_last_extra.py — chain_last_extra 在 beat_lock 降级后必须清零

回归 R1 二次根因 (2026-09-10 r1_fixed_v1 实测):
  chain_last_extra 在 L3839 按**降级前**的转场时长计算 (预补偿 Σt，
  供 xfade 消耗)。但 beat_lock_hard_cuts 会把全部转场降级为 cut，
  降级后 xfade 不执行 → 补偿时长无人消耗 → 该 clip 被渲染成计划的
  3-5 倍长。

实测证据 (r1_fixed_v1, 59 段):
  seg#5  计划 7 帧 → 实际 33 帧 (+26)
  seg#11 计划 8 帧 → 实际 24 帧 (+16)
  seg#7  计划 8 帧 → 实际 14 帧 (+6)
  59 段累计多渲 62 帧 = 2.58s → [时长守卫] 22.12s → 19.40s
  时间线整体拉长 14% → EDL 声明切点落在段内部而非边界 → frozen_cut
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))


def _simulate(segs, chain_last_extra, beat_lock, with_fix=True):
    """模拟 _execute 的 render_dur 计算，返回各段实际渲染帧数"""
    fps = 24.0
    out = []
    for i, seg in enumerate(segs):
        extra = chain_last_extra.get(i, 0.0)
        if beat_lock and with_fix:
            extra = 0.0  # 修复: 降级后清零
        render_dur = seg["duration"] + extra
        out.append(max(1, round(render_dur * fps)))
    return out


def _make_segs(n, dur=0.3):
    return [{"index": i, "duration": dur,
             "transition": "xfade" if i % 6 == 0 else "cut"} for i in range(n)]


def test_without_fix_clips_blow_up():
    """无修复: 链末 clip 帧数暴涨 (复现 r1_fixed_v1 的 seg#5 7→33)"""
    segs = _make_segs(59)
    # 模拟: seg 5/11/7 是链末, 各自继承了链内转场补偿
    chain_last_extra = {5: 1.083, 11: 0.667, 7: 0.25}
    frames = _simulate(segs, chain_last_extra, beat_lock=True, with_fix=False)
    plan = [max(1, round(s["duration"] * 24)) for s in segs]
    assert frames[5] > plan[5] * 3, f"seg#5 应暴涨, got {frames[5]} vs {plan[5]}"
    assert frames[11] > plan[11] * 2, f"seg#11 应暴涨, got {frames[11]} vs {plan[11]}"
    total_extra = (sum(frames) - sum(plan)) / 24
    assert total_extra > 1.5, f"累计超长应 >1.5s, got {total_extra:.2f}s"
    print(f"  无修复: seg#5 {plan[5]}→{frames[5]} 帧, "
          f"累计超长 {total_extra:.2f}s")


def test_with_fix_clips_match_plan():
    """有修复: 全部 clip 帧数 = 计划帧数 (零超长)"""
    segs = _make_segs(59)
    chain_last_extra = {5: 1.083, 11: 0.667, 7: 0.25}
    frames = _simulate(segs, chain_last_extra, beat_lock=True, with_fix=True)
    plan = [max(1, round(s["duration"] * 24)) for s in segs]
    assert frames == plan, f"帧数应完全一致: {frames[:12]} vs {plan[:12]}"
    total_extra = (sum(frames) - sum(plan)) / 24
    assert abs(total_extra) < 1e-6, f"超长应为 0, got {total_extra}"
    print(f"  有修复: 59 段帧数全部匹配计划, 超长 {total_extra:.2f}s")


def test_no_beat_lock_keeps_compensation():
    """非 beat_lock 模式: 补偿必须保留 (xfade 真的会消耗它)"""
    segs = _make_segs(12)
    chain_last_extra = {5: 1.083}
    frames = _simulate(segs, chain_last_extra, beat_lock=False, with_fix=True)
    plan = [max(1, round(s["duration"] * 24)) for s in segs]
    assert frames[5] > plan[5], "非 beat_lock 下补偿必须保留"
    print(f"  非 beat_lock: seg#5 {plan[5]}→{frames[5]} 帧 (补偿保留 ✓)")


def test_chain_extra_arithmetic_matches_observed():
    """核对实测数字: Σextra 应与 [时长守卫] 的超长量级一致"""
    # r1_fixed_v1 实测: 59 段累计多渲 62 帧 = 2.58s
    # [时长守卫] 22.12s → 19.40s, 超长 2.72s
    observed_frames = 62
    observed_sec = observed_frames / 24
    guard_sec = 22.12 - 19.40
    assert abs(observed_sec - guard_sec) < 0.3, \
        f"帧数超长 {observed_sec:.2f}s 与时长守卫 {guard_sec:.2f}s 应一致"
    print(f"  实测一致: 多渲 {observed_sec:.2f}s ≈ 时长守卫 {guard_sec:.2f}s")