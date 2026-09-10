# -*- coding: utf-8 -*-
"""R1 第四轮根因单测: 全局去重 fresh_start 把切点顶到素材最后一帧。

背景
----
r1_fixed_v4 残留 12 个冻结切点，v2/v3/v4 三轮时间戳完全相同（一动没动）。
映射到 EDL 后发现 source_start 精确等于 `素材时长 - 片段时长`：

    seg38 v0300     ss=18.13  = 18.34 - 0.21
    seg43 nagi2     ss=60.02  ≈ 60.22 - 0.21
    seg51 Nagi      ss=67.55  = 67.80 - 0.25
    seg52 alya      ss=67.73  = 67.98 - 0.25
    seg57 独自升级5  ss=232.13 = 232.34 - 0.21

源头是 `_enforce_global_source_uniqueness._fresh_start`:
`usable = dur - win` → 最大候选点就是 dur-win（贴素材最后一帧），
且该函数运行在规划侧 `_TAIL_MARGIN` 钳制**之后**，把前三轮修复全部绕过。

修复: `usable = dur - win - _TAIL_MARGIN`，且 win 乘 speed（实际读取窗口）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TAIL_MARGIN = 1.5


def _fresh_start_max(dur, win, tail_margin):
    """复刻 fresh_start 的候选点上限（不依赖已用点，取最大可行 c）。"""
    usable = dur - win - tail_margin
    if usable <= 0:
        return None
    lo = min(2.0, max(0.0, usable - 0.5)) if usable > 2.0 else 0.0
    cands = [lo + k * (usable - lo) / 12.0 for k in range(13)]
    cands += [lo + k * 0.5 for k in range(int((usable - lo) / 0.5) + 1)]
    ok = [c for c in sorted(set(cands)) if c + win <= dur + 1e-6]
    return max(ok) if ok else None


# ── 1. 旧行为：切点精确贴在素材最后一帧 ────────────────────────────

def test_old_fresh_start_hugs_source_tail():
    """旧逻辑 usable = dur-win → 最大候选 = dur-win，距尾 0。"""
    for dur, win in ((67.80, 0.25), (67.98, 0.25), (18.34, 0.21),
                     (60.22, 0.21), (232.34, 0.21)):
        got = _fresh_start_max(dur, win, tail_margin=0.0)
        assert got is not None
        # 距素材尾仅剩 win（即片段播完素材也用完）
        assert abs((dur - got) - win) < 0.02, (dur, win, got)


def test_old_logic_reproduces_observed_bad_source_starts():
    """旧逻辑复现 r1_fixed_v4 实测的 5 个贴尾 source_start。"""
    observed = [
        (18.34, 0.21, 18.13, "v0300"),
        (60.22, 0.21, 60.02, "nagi2"),
        (67.80, 0.25, 67.55, "Nagi"),
        (67.98, 0.25, 67.73, "alya"),
        (232.34, 0.21, 232.13, "独自升级5"),
    ]
    for dur, win, ss, name in observed:
        got = _fresh_start_max(dur, win, tail_margin=0.0)
        assert abs(got - ss) < 0.03, f"{name}: 算得 {got:.2f} vs 实测 {ss}"


# ── 2. 新行为：尾部留 _TAIL_MARGIN ─────────────────────────────────

def test_new_fresh_start_leaves_tail_margin():
    for dur, win in ((67.80, 0.25), (67.98, 0.25), (18.34, 0.21),
                     (60.22, 0.21), (232.34, 0.21)):
        got = _fresh_start_max(dur, win, tail_margin=TAIL_MARGIN)
        assert got is not None
        assert dur - (got + win) >= TAIL_MARGIN - 0.02, (dur, win, got)


def test_new_logic_moves_all_five_bad_cuts():
    """修复后 5 个坏刀的选点全部离开素材尾（位移 ≥ _TAIL_MARGIN）。"""
    observed = [
        (18.34, 0.21, 18.13), (60.22, 0.21, 60.02), (67.80, 0.25, 67.55),
        (67.98, 0.25, 67.73), (232.34, 0.21, 232.13),
    ]
    for dur, win, old_ss in observed:
        new_ss = _fresh_start_max(dur, win, tail_margin=TAIL_MARGIN)
        assert old_ss - new_ss >= TAIL_MARGIN - 0.05, (dur, win, old_ss, new_ss)


# ── 3. win 必须乘 speed（快放时实际读取窗口更长）──────────────────

def test_win_is_speed_aware():
    """快放 speed=1.5 时 0.21s 片段实际要读 0.315s 素材。"""
    duration, speed = 0.21, 1.5
    win_old = max(duration, 0.05)
    win_new = max(duration * speed, 0.05)
    assert abs(win_old - 0.21) < 1e-9
    assert abs(win_new - 0.315) < 1e-9
    # 快放不修正 → 读超素材（v4 实测 4 刀尾部余量为负）
    dur = 60.22
    ss = 60.02
    # 旧判据 c+win<=dur 在边界上（差 0.01s），素材时长缓存稍有误差就放过贴尾点
    assert abs((ss + win_old) - dur) < 0.02
    assert ss + win_new > dur + 0.1        # 实际超读 0.115s


def test_speed_aware_window_prevents_overread():
    dur, duration, speed = 60.22, 0.21, 1.5
    win = max(duration * speed, 0.05)
    got = _fresh_start_max(dur, win, tail_margin=TAIL_MARGIN)
    assert got is not None
    assert got + win + TAIL_MARGIN <= dur + 1e-6


# ── 4. 素材过短时返回 None（交给换源，不硬贴尾）──────────────────

def test_source_too_short_returns_none():
    assert _fresh_start_max(1.0, 0.5, tail_margin=TAIL_MARGIN) is None
    assert _fresh_start_max(1.5, 0.21, tail_margin=TAIL_MARGIN) is None
    # 刚够放下一个片段但仍无尾部余量 → None
    assert _fresh_start_max(1.71, 0.21, tail_margin=TAIL_MARGIN) is None


def test_tail_margin_constant_reasonable():
    """1.5s 尾部余量：大于最长片段(0.38s)，小于最短素材(16.87s)。"""
    assert 0.5 <= TAIL_MARGIN <= 3.0
    assert TAIL_MARGIN > 0.38          # 覆盖实测最长超短片段
    assert TAIL_MARGIN < 16.87         # 远小于最短素材，不会耗尽可用区间
