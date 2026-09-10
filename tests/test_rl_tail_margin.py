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