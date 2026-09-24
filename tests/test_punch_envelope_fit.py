# -*- coding: utf-8 -*-
"""`fit_punch_envelope` 契约测试（2026-09-23）。

背景：POC 实测发现 v9 计划 45 次撞击里 9 次根本不触发、进入渲染的 36 次仅 11 次
完整播完包络（切走时镜头仍压在峰上，"闪回"没播出来）。用户裁决为 "(c)+(a) 分段处置"：
  · 短段承认"急推入切"风格，不动排程
  · 中长段把装不下的 onset 前移到可容纳帧，前移超限则丢弃

本文件只测**纯函数**，不触发渲染、不写盘。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ai.production_director import (  # noqa: E402
    PUNCH_ADAPTIVE_ENVELOPE,
    PUNCH_ATTACK_FRAMES,
    PUNCH_ENVELOPE,
    PUNCH_MAX_SHIFT_FRAMES,
    PUNCH_MIN_GAP_FRAMES,
    PUNCH_RELEASE_FRAMES,
    PUNCH_SHORT_SEGMENT_FRAMES,
    effective_punch_envelope,
    fit_punch_envelope,
)


class TestShortSegmentAccepted:
    """短段（≤ PUNCH_SHORT_SEGMENT_FRAMES）承认风格：不做"前移/丢弃"，但间隔门照旧。

    注意 min_gap(=7) 比短段本身还大，故短段内两个 onset 必然被合并成一个 ——
    这与重构前的行为一致（当时间隔门在调用方无条件跑）。
    """

    @pytest.mark.parametrize("n", [4, 5, 6, 7, PUNCH_SHORT_SEGMENT_FRAMES])
    def test_short_segment_not_shifted_or_dropped(self, n):
        out, shifted, dropped = fit_punch_envelope([0], n)
        assert out == [0]
        assert (shifted, dropped) == (0, 0)

    def test_short_segment_merges_punches_within_min_gap(self):
        out, shifted, dropped = fit_punch_envelope([0, PUNCH_MIN_GAP_FRAMES - 2], 6)
        assert out == [0], "间距不足的两个 onset 应合并且不算作前移/丢弃"
        assert (shifted, dropped) == (0, 0)

    def test_short_segment_keeps_unfittable_onset(self):
        """段比包络还短时不做任何裁剪——这正是 v9 里 76% 截断的成因"""
        out, shifted, dropped = fit_punch_envelope([0], PUNCH_ENVELOPE - 3)
        assert out == [0]
        assert (shifted, dropped) == (0, 0)


class TestLongSegmentFitted:
    def test_fits_in_place_when_room_enough(self):
        n = 20
        out, shifted, dropped = fit_punch_envelope([2, 12], n)
        assert out == [2, 12]
        assert (shifted, dropped) == (0, 0)

    def test_exact_fit_is_not_shifted(self):
        """onset + envelope == n 恰好装得下，不该被前移"""
        n = 10
        f = n - PUNCH_ENVELOPE
        out, shifted, dropped = fit_punch_envelope([f], n)
        assert out == [f]
        assert (shifted, dropped) == (0, 0)

    def test_shifts_back_within_limit(self):
        """装不下但缺口在上限内 → 前移到可容纳帧"""
        n = 12
        latest = n - PUNCH_ENVELOPE
        f = latest + PUNCH_MAX_SHIFT_FRAMES      # 缺口恰在上限
        out, shifted, dropped = fit_punch_envelope([f], n)
        assert out == [latest]
        assert (shifted, dropped) == (1, 0)

    def test_drops_when_shift_exceeds_limit(self):
        """缺口超过上限 → 丢弃（再往前就偏离重音了）"""
        n = 12
        latest = n - PUNCH_ENVELOPE
        f = latest + PUNCH_MAX_SHIFT_FRAMES + 1
        out, shifted, dropped = fit_punch_envelope([f], n)
        assert out == []
        assert (shifted, dropped) == (0, 1)

    def test_never_firing_onset_is_dropped_not_clamped_to_negative(self):
        """onset 帧 ≥ 段帧数（历史上"根本不触发"的那批）在中长段被丢弃"""
        n = 10
        out, shifted, dropped = fit_punch_envelope([n + 1], n)
        assert out == []
        assert dropped == 1


class TestNonOverlapPreserved:
    def test_shifted_punch_is_merged_if_it_lands_too_close(self):
        """前移可能把点挤近 → 归一时须重跑间隔门，否则包络叠成糊。

        逐步追踪（段 12 帧、envelope=7、min_gap=7 → latest=5）：
          输入 [0, 7] → 间隔门: 7-0=7 ≥ 7 通过 → [0, 7]
          fit: 0 ≤ 5 保留；7 缺口=2 ≤ max_shift → 前移到 5
          refit: 5-0=5 < 7 → 合并 ⇒ 输出 [0]
        """
        out, shifted, dropped = fit_punch_envelope([0, PUNCH_ENVELOPE], 12)
        assert out == [0], "前移后的点与前一帧间距不足，应被合并"
        assert shifted == 1 and dropped == 0

    def test_min_gap_is_idempotent(self):
        """间隔门幂等：先滤过再传进来，结果不变（调用方不必关心顺序）"""
        n = 40
        once, _, _ = fit_punch_envelope([0, 3, 20], n)
        twice, _, _ = fit_punch_envelope(once, n)
        assert once == twice

    def test_min_gap_uses_project_constant(self):
        n = 30
        base = 2
        out, _, _ = fit_punch_envelope([base, base + PUNCH_MIN_GAP_FRAMES - 1], n)
        assert out == [base]


class TestReturnContract:
    def test_empty_input(self):
        assert fit_punch_envelope([], 20) == ([], 0, 0)

    def test_counts_are_consistent_with_output(self):
        """逐步追踪（段 12 帧、envelope=7、min_gap=7 → latest=5）：
          输入 [0, 7, 104]
          间隔门: 0 | 7-0=7 通过 | 104-7 通过      → [0, 7, 104]
          fit:    0 ≤5 保留 | 7 缺口2→前移到5 | 104 缺口99 超限→丢弃
          refit:  5-0=5 <7 → 合并               → 输出 [0]
         计数: shifted=1, dropped=1, 净减 2（1 丢弃 + 1 因前移被合并）
        """
        out, shifted, dropped = fit_punch_envelope([0, PUNCH_ENVELOPE, 104], 12)
        assert out == [0]
        assert shifted == 1
        assert dropped == 1

    def test_invariant_all_kept_frames_fit_and_do_not_overlap(self):
        """归一后的两个硬不变量（这才是这个函数存在的理由）：
        ① 每个保留的 onset 都能容纳完整包络：f + envelope <= n
        ② 相邻 onset 间距 >= min_gap，包络不叠成糊
        """
        n = 25
        frames = [0, 3, 11, 18, 19, 24]
        out, _, _ = fit_punch_envelope(frames, n)
        assert out, "不该被清空"
        for f in out:
            assert f + PUNCH_ENVELOPE <= n, f"帧 {f} 装不下包络"
        for a, b in zip(out, out[1:]):
            assert b - a >= PUNCH_MIN_GAP_FRAMES, f"{a}->{b} 间距不足"

    def test_invariant_holds_for_short_segments_too(self):
        """短段不做前移，但仍须保证间距不叠（不变量 ② 无例外）"""
        n = 6
        out, _, _ = fit_punch_envelope([0, 2, 9], n)
        for a, b in zip(out, out[1:]):
            assert b - a >= PUNCH_MIN_GAP_FRAMES


class TestEffectiveEnvelopeDefaultOff:
    """默认（自适应关闭）时必须**逐字不变**——这是"不改默认"的硬保证。"""

    def test_env_flag_defaults_off(self):
        assert PUNCH_ADAPTIVE_ENVELOPE is False, (
            "自适应包络属用户裁决项，默认必须关闭；"
            "只有显式设 AEKV_PUNCH_ADAPTIVE_ENVELOPE=1 才启用")

    @pytest.mark.parametrize("seg,last", [(4, 0), (5, 0), (6, 2), (7, 6), (20, 3)])
    def test_returns_default_when_disabled(self, seg, last):
        assert effective_punch_envelope(seg, last, adaptive=False) == (
            PUNCH_ATTACK_FRAMES, PUNCH_RELEASE_FRAMES)

    def test_default_matches_module_constants(self):
        assert effective_punch_envelope(4, 0) == (
            PUNCH_ATTACK_FRAMES, PUNCH_RELEASE_FRAMES)


class TestEffectiveEnvelopeAdaptive:
    """开启自适应时：按最后一个 onset 之后的剩余帧数把包络压到刚好装下。"""

    @pytest.mark.parametrize("room,expect", [
        (7, (2, 5)),   # 装得下 → 不压缩
        (8, (2, 5)),
        (6, (2, 4)),
        (5, (1, 4)),
        (4, (1, 3)),
        (3, (1, 2)),
        (2, (1, 1)),   # 最简可读撞击：1 帧冲 + 1 帧弹
    ])
    def test_compression_curve(self, room, expect):
        seg, last = room + 1, 0          # seg - 1 - last == room
        assert effective_punch_envelope(seg, last, adaptive=True) == expect

    def test_too_short_returns_zero_zero(self):
        """连 1 冲 1 弹都塞不进 → (0,0)，调用方据此退回默认包络"""
        assert effective_punch_envelope(3, 2, adaptive=True) == (0, 0)

    def test_never_exceeds_available_room(self):
        for seg in range(3, 30):
            for last in range(0, seg):
                a, r = effective_punch_envelope(seg, last, adaptive=True)
                if a == 0:
                    continue
                assert a + r <= seg - 1 - last, (seg, last, a, r)
                assert a >= 1 and r >= 1

    def test_room_uses_last_onset_not_first(self):
        """约束来自**最后一个** onset —— 它后面的空间最小，是真正的瓶颈"""
        assert effective_punch_envelope(12, 9, adaptive=True) == (1, 1)
        assert effective_punch_envelope(12, 3, adaptive=True) == (2, 5)

    def test_sorted_and_deduped(self):
        out, _, _ = fit_punch_envelope([9, 2, 9], 40)
        assert out == [2, 9]
