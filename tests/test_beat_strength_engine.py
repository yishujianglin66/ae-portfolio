# -*- coding: utf-8 -*-
"""core.beat_strength_engine 单元测试 — 漫剪卡点铁律核心链路

覆盖重点（对应 montage-card-point-rules.md §2 变速 + §3 撞拍锚定）：
  1. 空输入边界：空 beats / 空 downbeats 不崩溃
  2. 拍级分级：downbeat + onset + 能量 三因子加权 → STRONG/MEDIUM/WEAK
  3. 阈值语义：score >= strong_threshold → STRONG；< medium_threshold → WEAK
  4. 查询方法：get_beat_at_time（最近回退，卡点铁律§2）、get_beats_in_range、statistics
  5. 素材分配：assign_materials → 强拍配高分段、弱拍配低分段
  6. 内部归一化：_normalize_onset / _normalize_energy 百分位归一 + 平坦曲线回退 0.5
  7. 插值：_interp_at_time 在 times 轴上正确线性插值
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from core.beat_strength_engine import (
    BeatClassificationResult,
    BeatInfo,
    BeatStrength,
    BeatStrengthEngine,
)


# ─────────────────────────────────────────────────────────────────────
# 1. 构造辅助
# ─────────────────────────────────────────────────────────────────────
def _make_engine(**overrides):
    """带显式权重的引擎，便于断言分数组成。"""
    kw = dict(strong_threshold=0.7, medium_threshold=0.4,
              downbeat_weight=0.4, onset_weight=0.35, energy_weight=0.25, fps=24)
    kw.update(overrides)
    return BeatStrengthEngine(**kw)


# ─────────────────────────────────────────────────────────────────────
# 2. 边界输入
# ─────────────────────────────────────────────────────────────────────
class TestEmptyInput:
    def test_empty_beats_returns_empty_result(self):
        eng = _make_engine()
        result = eng.classify_beats(
            beats_sec=np.array([]),
            downbeats_sec=np.array([0.0, 2.0]),
        )
        assert result.total_beats == 0
        assert result.beats == []
        assert result.strong_beats == [] and result.medium_beats == [] and result.weak_beats == []
        # 空序列 statistics 字段完整
        stats = result.statistics()
        assert stats["total"] == 0 and stats["strong"] == 0
        assert stats["bpm"] == 0.0

    def test_single_beat_no_downbeats(self):
        """孤立单拍 → 无 onset/rms 时 onset/energy 给 0.5，分数 = 0*0.4 + 0.5*0.35 + 0.5*0.25 = 0.3 < 0.4 → WEAK"""
        eng = _make_engine()
        result = eng.classify_beats(
            beats_sec=np.array([1.0]),
            downbeats_sec=np.array([]),
        )
        assert result.total_beats == 1
        b = result.beats[0]
        assert b.strength == BeatStrength.WEAK
        assert b.score == pytest.approx(0.3)
        assert b.is_downbeat is False
        assert b.frame == 24  # 1.0s × 24fps


# ─────────────────────────────────────────────────────────────────────
# 3. downbeat 识别 + 三因子评分
# ─────────────────────────────────────────────────────────────────────
class TestThreeFactorScoring:
    def test_downbeat_alone_boosts_to_medium(self):
        """仅 downbeat 加分: score = 1.0*0.4 + 0.5*0.35 + 0.5*0.25 = 0.7 → 刚好 STRONG 阈值"""
        eng = _make_engine()
        result = eng.classify_beats(
            beats_sec=np.array([0.0]),
            downbeats_sec=np.array([0.0]),  # 精确匹配
        )
        assert result.beats[0].strength == BeatStrength.STRONG
        assert result.beats[0].score == pytest.approx(0.7)
        assert result.beats[0].is_downbeat is True

    def test_downbeat_100ms_tolerance_match(self):
        """downbeat 集合匹配容差 <0.1s"""
        eng = _make_engine()
        # beat@0.5 vs downbeat@0.55 → 差 0.05s 命中
        r = eng.classify_beats(
            beats_sec=np.array([0.5]),
            downbeats_sec=np.array([0.55]),
        )
        assert r.beats[0].is_downbeat is True
        # beat@0.5 vs downbeat@0.62 → 差 0.12s 不命中
        r2 = eng.classify_beats(
            beats_sec=np.array([0.5]),
            downbeats_sec=np.array([0.62]),
        )
        assert r2.beats[0].is_downbeat is False

    def test_onset_and_energy_push_score(self):
        """高 onset + 高 energy 序列 (足够多样本过百分位归一化) → 非 downbeat 也能到 MEDIUM"""
        eng = _make_engine()
        n = 101
        times = np.linspace(0, 1.0, n)
        # 构造连续信号：余弦上升使 t=0.5 处达到峰值
        t_arr = times
        onset = 0.1 + 0.8 * np.exp(-((t_arr - 0.5) ** 2) / 0.01)  # 高斯峰在 0.5
        rms = 0.1 + 0.8 * np.exp(-((t_arr - 0.5) ** 2) / 0.015)
        result = eng.classify_beats(
            beats_sec=np.array([0.5]),
            downbeats_sec=np.array([]),
            onset_envelope=onset, rms_energy=rms, times=times,
        )
        b = result.beats[0]
        # t=0.5 处 onset 和 rms 都接近 P90 → onset_val≈1.0, energy_val≈1.0 → 0.35+0.25 = 0.6 → MEDIUM
        assert b.strength in (BeatStrength.MEDIUM, BeatStrength.STRONG)
        assert b.score >= 0.5

    def test_bpm_estimation_from_intervals(self):
        """BPM 由拍间隔中位数推导: 间隔 [0.5, 0.5, 0.5] → 中位 0.5 → 120"""
        eng = _make_engine()
        r = eng.classify_beats(
            beats_sec=np.array([0.0, 0.5, 1.0, 1.5]),
            downbeats_sec=np.array([0.0, 1.0]),
        )
        assert r.bpm == pytest.approx(120.0)
        assert r.bar_count == 1  # ceil(4/4) = 1


# ─────────────────────────────────────────────────────────────────────
# 4. 查询方法 + 最近回退（卡点铁律§2 "get_beat_at_time 失败时取最近"）
# ─────────────────────────────────────────────────────────────────────
class TestQueryMethods:
    @pytest.fixture()
    def result(self):
        eng = _make_engine()
        return eng.classify_beats(
            beats_sec=np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5]),
            downbeats_sec=np.array([0.0, 1.0, 2.0]),  # 每2拍一个重拍
        )

    def test_get_beat_at_time_exact(self, result):
        b = result.get_beat_at_time(1.0, tolerance=0.01)
        assert b is not None and b.time_sec == 1.0
        assert b.is_downbeat is True

    def test_get_beat_at_time_within_tolerance(self, result):
        # ±0.05 容差内命中
        b = result.get_beat_at_time(1.04, tolerance=0.05)
        assert b is not None and b.time_sec == 1.0

    def test_get_beat_at_time_outside_tolerance_returns_none(self, result):
        # 距最近拍 1.0 仍有 0.08，容差 0.05 → None
        assert result.get_beat_at_time(1.08, tolerance=0.05) is None

    def test_get_beats_in_range(self, result):
        in_range = result.get_beats_in_range(0.4, 1.6)
        ts = [b.time_sec for b in in_range]
        assert ts == [0.5, 1.0, 1.5]  # 左闭右开

    def test_statistics_shape(self, result):
        s = result.statistics()
        assert s["total"] == 6
        assert s["strong"] + s["medium"] + s["weak"] == 6
        assert s["bars"] == 2


# ─────────────────────────────────────────────────────────────────────
# 5. 素材分配 assign_materials
# ─────────────────────────────────────────────────────────────────────
class TestMaterialAssignment:
    class _Seg:
        def __init__(self, name, total):
            self.name = name
            self.total = total

    def _segs(self, n=20):
        return [self._Seg(f"s{i}", i) for i in range(n)]  # total 0..19 升序

    def test_empty_segments_returns_empty_per_level(self):
        eng = _make_engine()
        r = eng.classify_beats(np.array([1.0]), np.array([]))
        a = eng.assign_materials(r, [])
        assert all(a[lvl] == [] for lvl in BeatStrength)

    def test_strong_gets_top_twenty_pct(self):
        """n=20 → sorted_segs 按 total 降序；top_20 = max(3, 4) = 4；
        STRONG = 前 4 个 (16,17,18,19 升序 = [19,18,17,16] 降序切片结果 → sort 后 [16,17,18,19])
        mid_50 = max(3, 10) = 10 → 切片 [4:10] 降序 = total [15,14,13,12,11,10] → 升序 = [10,11,12,13,14,15]
        weak = [10:] 降序 = total [9..0] → 升序 = [0..9]"""
        eng = _make_engine()
        r = eng.classify_beats(np.array([1.0]), np.array([]))
        a = eng.assign_materials(r, self._segs(20))
        strong_totals = sorted(s.total for s in a[BeatStrength.STRONG])
        assert strong_totals == [16, 17, 18, 19]
        medium_totals = sorted(s.total for s in a[BeatStrength.MEDIUM])
        # mid_50 = max(3, 10) = 10 → sorted_segs[4:10] (降序 total 15..10) → 升序 10..15
        assert medium_totals == [10, 11, 12, 13, 14, 15]
        weak = sorted(s.total for s in a[BeatStrength.WEAK])
        assert weak == list(range(10))

    def test_min_segments_per_level_enforced(self):
        """n=5 → top_20 = max(3, 1) = 3；至少 3 段每级"""
        eng = _make_engine()
        r = eng.classify_beats(np.array([1.0]), np.array([]))
        a = eng.assign_materials(r, self._segs(5))
        assert len(a[BeatStrength.STRONG]) >= 3


# ─────────────────────────────────────────────────────────────────────
# 6. 内部归一化与插值
# ─────────────────────────────────────────────────────────────────────
class TestInternalNorm:
    def test_normalize_onset_flat_curve_returns_half(self):
        eng = _make_engine()
        times = np.arange(10, dtype=float)
        flat = np.ones(10) * 5.0  # 所有值相同
        norm = eng._normalize_onset(flat, times)
        assert norm.shape == (10,)
        assert np.allclose(norm, 0.5)

    def test_normalize_energy_percentile_clipping(self):
        eng = _make_engine()
        times = np.arange(100, dtype=float)
        arr = np.arange(100, dtype=float)  # 0..99 线性
        norm = eng._normalize_energy(arr, times)
        assert norm.min() >= 0.0 - 1e-6 and norm.max() <= 1.0 + 1e-6
        # np.percentile 默认 linear 插值: p10(arr) 约为 9.9, p90 约为 89.1
        # 因此在 lo≈9.9, hi≈89.1 的归一化下:
        #   arr[99]=99 → (99-89.1)/(89.1-9.9) ≈ 1.25 → clip → 1.0  (upper clip)
        #   arr[0]=0 → (0-9.9)/79.2 ≈ -0.125 → clip → 0.0  (lower clip)
        assert norm[0] == pytest.approx(0.0)  # 下界被 clip
        assert norm[99] == pytest.approx(1.0)  # 上界被 clip
        # 中段值在 [0,1] 内严格递增
        for i in range(50):
            assert norm[i + 1] >= norm[i] - 1e-9

    def test_interp_at_time_linear(self):
        eng = _make_engine()
        times = np.array([0.0, 1.0, 2.0])
        values = np.array([0.0, 1.0, 0.0])
        # 中点线性插值
        assert eng._interp_at_time(times, values, 0.5) == pytest.approx(0.5)
        assert eng._interp_at_time(times, values, 1.5) == pytest.approx(0.5)
        # 端点
        assert eng._interp_at_time(times, values, 0.0) == pytest.approx(0.0)
        assert eng._interp_at_time(times, values, 2.0) == pytest.approx(0.0)


# ─────────────────────────────────────────────────────────────────────
# 7. BeatInfo 属性快捷方法
# ─────────────────────────────────────────────────────────────────────
class TestBeatInfoProperties:
    @pytest.mark.parametrize("level,prop", [
        (BeatStrength.STRONG, "is_strong"),
        (BeatStrength.MEDIUM, "is_medium"),
        (BeatStrength.WEAK, "is_weak"),
    ])
    def test_strength_properties(self, level, prop):
        b = BeatInfo(time_sec=0.0, frame=0, strength=level, score=0.5)
        assert getattr(b, prop) is True
        for other in ("is_strong", "is_medium", "is_weak"):
            if other != prop:
                assert getattr(b, other) is False
