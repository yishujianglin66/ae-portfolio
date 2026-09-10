# -*- coding: utf-8 -*-
"""core.music_dynamics 单元测试 — 漫剪卡点铁律 §1 切点密度 + §2 变速

覆盖重点：
  1. analyze() 空/平坦曲线 → 不分段崩溃（返回 mid 中性段）
  2. analyze() 能量阶梯曲线 → high/mid/low 三级分段正确
  3. analyze() 过短段合并（min_section_dur 铁律），短段并入更长邻居
  4. level_at / section_at 时间点查询，含段外回退
  5. plan_cuts() 高密度段 high=onset+beat 全切，mid=beat，low=仅 downbeat
  6. plan_cuts() low 段重拍稀疏时自动补 beat（防 >5s 死镜头）
  7. plan_cuts() min_shot_dur 约束 + 拍点邻近性偏好取点
  8. speed_for_shot() 9 格变速矩阵（low+强拍→0.55 slowmo, high→1.0 pulse）
  9. summarize() 统计输出字段完整性
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest

from core.music_dynamics import (
    DynamicSection,
    MusicDynamicsAnalyzer,
)


# ─────────────────────────────────────────────────────────────────────
# 1. 辅助
# ─────────────────────────────────────────────────────────────────────
def _analyzer(**kw):
    defaults = dict(min_section_dur=0.5, smooth_frames=3,
                    high_quantile=0.75, low_quantile=0.25)
    defaults.update(kw)
    return MusicDynamicsAnalyzer(**defaults)


def _stepped_rms(total_dur: float, sr_hz: float = 20):
    """构造 0→t1: low, t1→t2: mid, t2→end: high 的阶梯能量。"""
    n = int(total_dur * sr_hz)
    times = np.arange(n) / sr_hz
    t1, t2 = total_dur * 0.33, total_dur * 0.66
    rms = np.zeros(n)
    rms[times < t1] = 0.1
    rms[(times >= t1) & (times < t2)] = 0.5
    rms[times >= t2] = 0.95
    return rms, times


# ─────────────────────────────────────────────────────────────────────
# 2. 空 / 平坦输入边界
# ─────────────────────────────────────────────────────────────────────
class TestAnalyzeEdgeCases:
    def test_flat_curve_single_mid_section(self):
        """RMS 全常数 → _norm01 回退 0.5 → 强度全 0.5 → 过平时强制拉开阈值
        结果：单一 mid 段（或 high/mid/low 三段但都很平），不崩溃。"""
        a = _analyzer()
        total = 4.0
        n = int(total * 20)
        rms = np.ones(n) * 0.5
        times = np.arange(n) / 20.0
        sections = a.analyze(rms, times, total_duration=total)
        # 至少 1 段；首段 start=0，尾段 end=total
        assert len(sections) >= 1
        assert sections[0].start == 0.0
        assert sections[-1].end == total
        # 所有段级别在 high/mid/low 集合内
        assert all(s.level in {"high", "mid", "low"} for s in sections)

    def test_empty_rms_uses_neutral(self):
        a = _analyzer()
        # rms/times 空，beats/onsets 都无 → density 用 1.0 中性
        sections = a.analyze(
            rms=np.array([]), times=np.array([]), total_duration=3.0,
        )
        assert len(sections) >= 1
        assert sections[0].start == 0.0 and sections[-1].end == 3.0


# ─────────────────────────────────────────────────────────────────────
# 3. 阶梯曲线三级分段
# ─────────────────────────────────────────────────────────────────────
class TestSteppedSegmentation:
    def test_three_tier_segments_ordered(self):
        a = _analyzer(min_section_dur=0.2)  # 放宽合并以显式出现三段
        total = 6.0
        rms, times = _stepped_rms(total, sr_hz=40)
        sections = a.analyze(rms, times, total_duration=total)
        # 段按时间升序且首尾衔接
        for i in range(1, len(sections)):
            assert sections[i].start >= sections[i - 1].end - 1e-6
        levels = [s.level for s in sections]
        # 阶梯：低能(0-2s) → mid/low；中能(2-4s) → mid；高能(4-6s) → high
        # 首段必须是 low 或 mid（低能）；尾段是 high（高能）
        assert levels[0] in ("low", "mid")
        assert levels[-1] == "high"

    def test_short_sections_merged_into_longer_neighbor(self):
        """过短段 (< min_section_dur) 并入更长邻居；同级别直接合并。"""
        a = _analyzer(min_section_dur=1.5)  # 强制合并所有短于 1.5s 段
        total = 3.0
        rms, times = _stepped_rms(total, sr_hz=40)
        sections = a.analyze(rms, times, total_duration=total)
        # 段数应 < bin 数 (不产生微碎片)
        assert len(sections) <= 6
        # 每段时长至少 ≥ min_section_dur 的大部分（首段可例外）
        for s in sections[1:-1]:
            assert s.duration >= 0.4  # 不会无限碎片化


# ─────────────────────────────────────────────────────────────────────
# 4. 查询方法
# ─────────────────────────────────────────────────────────────────────
class TestLookupMethods:
    @pytest.fixture()
    def sections(self):
        return [
            DynamicSection(0.0, 1.0, "low", 0.1),
            DynamicSection(1.0, 3.0, "mid", 0.5),
            DynamicSection(3.0, 5.0, "high", 0.9),
        ]

    def test_level_at_mid(self, sections):
        a = _analyzer()
        assert a.level_at(sections, 2.0) == "mid"
        assert a.level_at(sections, 0.5) == "low"
        assert a.level_at(sections, 4.5) == "high"

    def test_level_at_boundary_uses_ge_start_lt_end(self, sections):
        # DynamicSection.contains: start <= t < end
        a = _analyzer()
        assert a.level_at(sections, 1.0) == "mid"  # 段2 左闭
        assert a.level_at(sections, 3.0) == "high"  # 段3 左闭
        assert a.level_at(sections, 5.0) == "mid"   # 段3 开区间 → 回退默认 mid

    def test_section_at_returns_object(self, sections):
        a = _analyzer()
        s = a.section_at(sections, 2.0)
        assert s is not None and s.level == "mid" and s.duration == 2.0

    def test_section_at_past_end_falls_back(self, sections):
        a = _analyzer()
        # t=10.0 不在任何段内 → 返回最后段
        s = a.section_at(sections, 10.0)
        assert s is sections[-1]


# ─────────────────────────────────────────────────────────────────────
# 5. plan_cuts 切点密度
# ─────────────────────────────────────────────────────────────────────
class TestPlanCuts:
    def _sections(self):
        # 三段式: low(0-2s), mid(2-4s), high(4-6s)
        return [
            DynamicSection(0.0, 2.0, "low", 0.1),
            DynamicSection(2.0, 4.0, "mid", 0.5),
            DynamicSection(4.0, 6.0, "high", 0.9),
        ]

    def test_high_section_includes_both_onset_and_beat(self):
        a = _analyzer()
        secs = self._sections()
        # high 段内: beat@4.5, onset@4.2,4.8 → 三者全取
        beats = np.array([0.5, 1.0, 2.5, 3.0, 4.5, 5.0, 5.5])
        dbs = np.array([0.0, 2.0, 4.0])
        onsets = np.array([0.7, 2.7, 4.2, 4.8, 5.2])
        cuts = a.plan_cuts(secs, beats, dbs, onsets, min_shot_dur=0.01)
        # high 段 onset@4.2,4.8,5.2 + beat@4.5,5.0,5.5 → 全部出现
        for t in [4.2, 4.5, 4.8, 5.0, 5.2, 5.5]:
            assert any(abs(c - t) < 1e-6 for c in cuts), f"high 段缺失切点 t={t}"

    def test_low_section_only_downbeats_when_dense(self):
        a = _analyzer()
        secs = [DynamicSection(0.0, 4.0, "low", 0.1)]
        # low 段: downbeats@0,2,4 间隔 2s < 5s → 仅取重拍
        beats = np.arange(0.25, 4.0, 0.25)  # 密集普通拍
        dbs = np.array([0.0, 2.0, 4.0])
        onsets = np.array([0.5, 1.0, 1.5])  # low 段 onset 不取
        cuts = a.plan_cuts(secs, beats, dbs, onsets, min_shot_dur=0.01)
        # 仅重拍在 low 段切点中
        assert 0.5 not in cuts and 1.5 not in cuts
        assert 0.0 in cuts or 2.0 in cuts  # 重拍出现（注意 cuts[0]>0.01 过滤，所以 0.0 可能被跳过）

    def test_low_section_sparse_downbeats_fill_with_beats(self):
        """low 段重拍间隔 >5s → 自动补普通拍（防死镜头铁律）。
        注意: 合并逻辑 `if p - pts[-1] > 4.0: pts.append(p)` → 允许 gap 略 >4s (如 4.5s
        在 p=4.5 时不触发, 下一个 p=5.0 差 4.5>4 才触发 → gap=4.5 ≤ 5.0 仍合理)。"""
        a = _analyzer()
        secs = [DynamicSection(0.0, 10.0, "low", 0.1)]
        beats = np.arange(0.0, 10.0, 0.5)  # 每 0.5s 一拍
        dbs = np.array([0.0, 10.0])  # 仅首尾重拍
        onsets = np.array([])
        cuts = a.plan_cuts(secs, beats, dbs, onsets, min_shot_dur=0.01)
        # 至少 >1 刀（不是只有 1 个点死段）
        assert len(cuts) >= 2
        # 最大 gap ≤ 5.0s (阈值 4.0 允许 1s 余量, 仍满足不 >5s 死镜头)
        gaps = np.diff(cuts)
        assert max(gaps) <= 5.0 + 1e-3

    def test_min_shot_dur_constraint_beat_preference(self):
        """过近切点冲突 → 保留离拍更近者（卡点铁律 §1 边界吸附到拍）"""
        a = _analyzer()
        secs = [DynamicSection(0.0, 5.0, "high", 0.9)]
        # 普通拍@1.0；onset@0.95 和 1.02 都离 1.0 很近（< min_shot_dur=0.1）
        beats = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        dbs = np.array([0.0, 2.0, 4.0])
        onsets = np.array([0.95, 1.02])  # 两个都离 1.0 近
        cuts = a.plan_cuts(secs, beats, dbs, onsets, min_shot_dur=0.1)
        # 0.95 与 1.02 间距仅 0.07 → 只保留一个，且优先 1.02 (离 beat@1.0 更近 d=0.02 vs 0.05)
        # 注意 cuts 中还可能含 beat@1.0 自身，所以断言：0.95 不在最终 cuts 中
        assert 0.95 not in cuts

    def test_section_boundaries_are_forced_cuts(self):
        """动态切换处必须切（段边界强制切点）"""
        a = _analyzer()
        secs = self._sections()  # 边界 2.0 / 4.0
        beats = np.array([1.0, 3.0, 5.0])
        dbs = np.array([0.0])
        onsets = np.array([])
        cuts = a.plan_cuts(secs, beats, dbs, onsets, min_shot_dur=0.01)
        assert 2.0 in cuts
        assert 4.0 in cuts


# ─────────────────────────────────────────────────────────────────────
# 6. speed_for_shot 变速矩阵（漫剪卡点铁律 §2 逐镜头动态决策）
# ─────────────────────────────────────────────────────────────────────
class TestSpeedForShot:
    @pytest.mark.parametrize("level,bs,db,exp_speed,exp_tech", [
        # low 段: 强拍/重拍 → 0.55 slowmo
        ("low", "strong", False, 0.55, "slowmo"),
        ("low", "weak", True, 0.55, "slowmo"),
        # low 段: 普通 → 0.7 slowmo
        ("low", "weak", False, 0.7, "slowmo"),
        ("low", "medium", False, 0.7, "slowmo"),
        # high 段: 全部 1.3 fast_pan（2026-09-02 用户语法：重鼓点=快切撞击，
        # pulse 缩放移到镜头内特效层，速度层全部给撞击——core/music_dynamics.py）
        ("high", "strong", True, 1.3, "fast_pan"),
        ("high", "weak", False, 1.3, "fast_pan"),
        ("high", "medium", False, 1.3, "fast_pan"),
        # mid 段（2026-09-02 节拍-镜头语法）: 小节重音(强拍+downbeat)→0.55 慢镜落点；
        # 普通强拍/重拍→0.9 zoom_back（慢镜/缩放交替）；普通→1.0 static
        ("mid", "strong", True, 0.55, "slowmo"),
        ("mid", "strong", False, 0.9, "zoom_back"),
        ("mid", "weak", False, 1.0, "static"),
        ("mid", "medium", True, 0.9, "zoom_back"),
    ])
    def test_speed_matrix(self, level, bs, db, exp_speed, exp_tech):
        a = _analyzer()
        speed, tech = a.speed_for_shot(level, bs, 0.5, db)
        assert speed == exp_speed
        assert tech == exp_tech


# ─────────────────────────────────────────────────────────────────────
# 7. summarize 统计
# ─────────────────────────────────────────────────────────────────────
class TestSummarize:
    def test_summarize_fields_complete(self):
        sections = [
            DynamicSection(0.0, 1.0, "low", 0.1),
            DynamicSection(1.0, 2.5, "mid", 0.5),
            DynamicSection(2.5, 3.5, "high", 0.9),
            DynamicSection(3.5, 5.0, "mid", 0.4),
        ]
        s = MusicDynamicsAnalyzer.summarize(sections)
        assert s["total_sections"] == 4
        assert s["low_count"] == 1 and s["low_dur"] == pytest.approx(1.0)
        assert s["mid_count"] == 2 and s["mid_dur"] == pytest.approx(1.5 + 1.5)
        assert s["high_count"] == 1 and s["high_dur"] == pytest.approx(1.0)
