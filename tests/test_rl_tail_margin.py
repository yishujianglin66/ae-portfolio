# -*- coding: utf-8 -*-
"""test_rl_tail_margin.py — 素材尾部安全余量 + 死区避让

回归 R1 第三轮根因 (2026-09-10 r1_fixed_v2 实测):
  _extract_clip 边界保护把 start_time 推回 src_dur - read_dur，紧贴素材
  末尾。而素材末尾通常是黑场/片尾字幕/静止画面（死区），多段被推到各自
  尾部后画面全是黑的 → 切点两侧同画面 → frozen_cut。

r1_fixed_v2 实测证据（11 个残留冻结切点全在末 4.6s）:
  独自升级5.mp4  ss=232.13 / 全长 232.3s  → 距尾 0.17s
  猫1.mp4        ss=117.68 / 全长 117.9s  → 距尾 0.22s
  Nagi.mp4       ss=67.55  / 全长 67.8s   → 距尾 0.25s
  alya-twix.mp4  ss=67.73  / 全长 68.0s   → 距尾 0.27s
"""
import sys
from pathlib import Path

import pytest

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

# 与 production_director 保持一致
_TAIL_MARGIN = 1.5


def _push_back(src_dur, read_dur, start_time, with_fix=True):
    """模拟 _extract_clip 的边界保护推回"""
    if start_time + read_dur <= src_dur:
        return start_time, False
    if with_fix:
        pushed = max(0.0, src_dur - read_dur - _TAIL_MARGIN)
    else:
        pushed = max(0.0, src_dur - read_dur)
    return pushed, True


def test_old_push_hugs_source_tail():
    """旧逻辑: 推回后紧贴素材末尾 (距尾 < 0.5s)"""
    cases = [
        # (src_dur, read_dur, start_time, 描述)
        (232.3, 0.25, 300.0, "独自升级5"),
        (117.9, 0.25, 200.0, "猫1"),
        (67.8, 0.25, 100.0, "Nagi"),
        (68.0, 0.25, 100.0, "alya-twix"),
    ]
    for src_dur, read_dur, start_time, name in cases:
        pushed, did = _push_back(src_dur, read_dur, start_time, with_fix=False)
        assert did, f"{name} 应触发推回"
        dist_to_tail = src_dur - (pushed + read_dur)
        assert dist_to_tail < 0.5, \
            f"{name} 旧逻辑应紧贴末尾, 距尾 {dist_to_tail:.2f}s"
        print(f"  {name}: 旧推回 ss={pushed:.2f}, 距尾 {dist_to_tail:.2f}s")


def test_new_push_leaves_tail_margin():
    """新逻辑: 推回后保留 _TAIL_MARGIN 安全余量"""
    cases = [
        (232.3, 0.25, 300.0, "独自升级5"),
        (117.9, 0.25, 200.0, "猫1"),
        (67.8, 0.25, 100.0, "Nagi"),
        (68.0, 0.25, 100.0, "alya-twix"),
    ]
    for src_dur, read_dur, start_time, name in cases:
        pushed, did = _push_back(src_dur, read_dur, start_time, with_fix=True)
        assert did, f"{name} 应触发推回"
        dist_to_tail = src_dur - (pushed + read_dur)
        assert dist_to_tail >= _TAIL_MARGIN - 1e-6, \
            f"{name} 新逻辑应留 >= {_TAIL_MARGIN}s 余量, 实际 {dist_to_tail:.2f}s"
        print(f"  {name}: 新推回 ss={pushed:.2f}, 距尾 {dist_to_tail:.2f}s")


def test_no_push_when_range_fits():
    """范围没超时不触发推回, start_time 原样保留"""
    pushed, did = _push_back(100.0, 0.3, 50.0, with_fix=True)
    assert not did and pushed == 50.0, "未超范围不应改动"


def test_tail_margin_constant_reasonable():
    """_TAIL_MARGIN 应在 1-3s 之间: 够躲开片尾, 又不至于浪费素材"""
    assert 1.0 <= _TAIL_MARGIN <= 3.0, f"_TAIL_MARGIN={_TAIL_MARGIN} 不合理"
    print(f"  _TAIL_MARGIN = {_TAIL_MARGIN}s")

def test_planner_tail_clamp_symmetric_with_head():
    """规划侧: 片尾钳制应与片头钳制对称 (片头已有 min(2.0, ...))

    r1_fixed_v3 残留冻结中 5 个的 source_start 距尾仅 0.2-0.3s,
    因为规划阶段只有片头钳制没有片尾钳制。
    """
    cases = [
        # (src_dur, seg_dur, source_start, 描述)
        (67.8, 0.375, 67.55, "Nagi"),
        (60.2, 0.375, 60.02, "nagi2"),
        (68.0, 0.333, 67.73, "alya-twix"),
        (16.9, 0.25, 16.70, "五条悟第二季2"),
        (18.3, 0.25, 18.13, "v0300fg"),
    ]
    for src_dur, seg_dur, source_start, name in cases:
        # 片头钳制（既有）
        _min_ss = min(2.0, max(0.0, src_dur - seg_dur - 0.5))
        clamped = max(_min_ss, source_start)
        # 片尾钳制（新增）
        _max_ss = max(0.0, src_dur - seg_dur - _TAIL_MARGIN)
        clamped = min(_max_ss, clamped)
        dist_to_tail = src_dur - (clamped + seg_dur)
        assert dist_to_tail >= _TAIL_MARGIN - 1e-6, \
            f"{name} 片尾钳制后应留 >= {_TAIL_MARGIN}s, 实际 {dist_to_tail:.2f}s"
        assert clamped >= 0, f"{name} 起点不应为负"
        print(f"  {name}: ss {source_start:.2f} → {clamped:.2f}, "
              f"距尾 {dist_to_tail:.2f}s")


def test_head_clamp_still_works():
    """片头钳制未被破坏"""
    src_dur, seg_dur = 100.0, 0.3
    _min_ss = min(2.0, max(0.0, src_dur - seg_dur - 0.5))
    assert _min_ss == 2.0, f"片头应钳到 2.0s, got {_min_ss}"
    # 短素材不应钳成负数
    _min_ss_short = min(2.0, max(0.0, 1.0 - 0.3 - 0.5))
    assert abs(_min_ss_short - 0.2) < 1e-9, \
        f"短素材片头钳制应 0.2, got {_min_ss_short}"
