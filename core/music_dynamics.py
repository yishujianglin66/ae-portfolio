# -*- coding: utf-8 -*-
"""MusicDynamicsAnalyzer — 音乐动态分段引擎 (v21c P0)

借鉴 ai-montage-agent beat_sync_engine / optimize_for_energy 设计:
  高能量部分 → 短镜头、快节奏 (密切)
  低能量部分 → 长镜头、慢节奏 (慢放变速)

能力:
  1. RMS能量曲线计算与平滑
  2. 动态分段: high / mid / low 三级 (基于能量分位数 + 最短段长约束)
  3. 切点密度规划: high=onset+beat密切, mid=beat逐拍, low=重拍长镜头
  4. 变速映射: 低能段慢放 / 高能段加速, 强拍落点卡拍

用法:
    from core.music_dynamics import MusicDynamicsAnalyzer
    analyzer = MusicDynamicsAnalyzer()
    sections = analyzer.analyze(rms, times, downbeats_sec, beats_sec, onsets_sec)
    cuts = analyzer.plan_cuts(sections, beats_sec, downbeats_sec, onsets_sec)
    speed = analyzer.speed_for_shot(section_level, beat_strength, energy_norm)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger("music_dynamics")


@dataclass
class DynamicSection:
    """音乐动态段"""
    start: float
    end: float
    level: str              # "high" / "mid" / "low"
    energy_mean: float      # 段内平均能量(归一化 0~1)

    @property
    def duration(self) -> float:
        return self.end - self.start

    def contains(self, t: float) -> bool:
        return self.start <= t < self.end


class MusicDynamicsAnalyzer:
    """音乐动态分段引擎

    Args:
        min_section_dur: 最短段长(秒), 过短段并入邻段
        smooth_frames: 能量曲线平滑窗口(帧数)
        high_quantile: 高能量分位数阈值 (默认75分位)
        low_quantile: 低能量分位数阈值 (默认35分位)
    """

    def __init__(self,
                 min_section_dur: float = 1.2,
                 smooth_frames: int = 15,
                 high_quantile: float = 0.75,
                 low_quantile: float = 0.35):
        self.min_section_dur = min_section_dur
        self.smooth_frames = smooth_frames
        self.high_quantile = high_quantile
        self.low_quantile = low_quantile

    # ------------------------------------------------------------------
    # 1. 动态分段 (onset密度 + 局部能量 双因子)
    # ------------------------------------------------------------------
    def analyze(self, rms: np.ndarray, times: np.ndarray,
                total_duration: float,
                beats_sec: np.ndarray | None = None,
                onsets_sec: np.ndarray | None = None) -> list[DynamicSection]:
        """将音乐分段为 high/mid/low 动态段

        双因子节奏强度曲线 (对短BGM鲁棒):
          intensity(t) = 0.7 * norm(local_rms)      (响度起伏主导)
                       + 0.3 * norm(onset_density)  (打击密度辅助)
        分位数三级分类(75/25): 渐强曲只把真正高潮定high, 前奏低处定low,
        中间渐强部分保持mid — 避免宽阈值把整曲二元化。
        归一化采用p2-p98分位数+平坦检测, 防止平坦曲线噪声被放大成全幅信号。

        Args:
            rms: librosa rms 能量序列(未归一化)
            times: 对应时间轴
            total_duration: BGM总时长
            beats_sec: 拍点(用于onset密度统计, 与onsets合并)
            onsets_sec: onset时间点
        """
        # ── 因子1: 事件密度曲线 (1.0s滑动窗口) ──
        events = []
        if onsets_sec is not None:
            events.extend(float(o) for o in onsets_sec)
        if beats_sec is not None:
            events.extend(float(b) for b in beats_sec)

        n_bins = max(2, int(total_duration * 4))  # 0.25s分辨率
        bin_t = total_duration / n_bins
        density = np.zeros(n_bins)
        if events:
            for e in events:
                idx = int(e / bin_t)
                if 0 <= idx < n_bins:
                    density[idx] += 1.0
            # 1.0s窗口 = 4bin 滑动平均
            k = 4
            if n_bins >= k:
                density = np.convolve(density, np.ones(k) / k, mode="same")
        else:
            density[:] = 1.0

        # ── 因子2: RMS能量曲线 (轻度平滑, 保留段落起伏) ──
        if len(rms) > 0 and len(times) > 0:
            lo, hi = np.percentile(rms, 5), np.percentile(rms, 95)
            rng = max(hi - lo, 1e-9)
            norm_e = np.clip((rms - lo) / rng, 0.0, 1.0)
            k2 = max(1, min(self.smooth_frames, len(norm_e) // 4 or 1))
            if len(norm_e) >= k2 and k2 > 1:
                norm_e = np.convolve(norm_e, np.ones(k2) / k2, mode="same")
            # 重采样到统一网格
            e_grid = np.interp(
                (np.arange(n_bins) + 0.5) * total_duration / n_bins,
                times, norm_e)
        else:
            e_grid = np.full(n_bins, 0.5)

        # ── 合成强度曲线并归一化 ──
        def _norm01(x):
            # 分位数鲁棒归一: min-max会把平坦曲线上的数值噪声放大成全幅信号
            x = np.asarray(x, dtype=float)
            lo, hi = float(np.percentile(x, 2)), float(np.percentile(x, 98))
            if hi - lo < 1e-6:  # 曲线平坦 → 中性值, 不放大噪声
                return np.full_like(x, 0.5)
            return np.clip((x - lo) / (hi - lo), 0.0, 1.0)

        # 双因子: 能量主导(0.7, 反映听感响度起伏) + onset密度辅助(0.3, 反映打击密集)
        intensity = 0.3 * _norm01(density) + 0.7 * _norm01(e_grid)

        # 全局再归一
        intensity = _norm01(intensity)

        # ── 分位数三级分类 (25/50/25, 适合渐强型曲目) ──
        # 渐强曲的强度曲线单调上升: 宽阈值(60/30)会把大部分归为high/low,
        # 窄阈值(75/25)保留中间大部分为mid, 只把真正的高潮/前奏定级
        i_hi = np.percentile(intensity, 75)
        i_lo = np.percentile(intensity, 25)
        if i_hi - i_lo < 0.08:  # 曲线过平 → 拉开阈值强制分段
            i_mid = float(np.mean(intensity))
            i_hi, i_lo = i_mid + 0.06, i_mid - 0.06
        labels = np.where(intensity >= i_hi, "high",
                          np.where(intensity <= i_lo, "low", "mid"))

        # 游程编码 → 段
        raw_sections: list[tuple[float, float, str]] = []
        seg_start_idx = 0
        for i in range(1, n_bins):
            if labels[i] != labels[seg_start_idx]:
                raw_sections.append((seg_start_idx * bin_t, i * bin_t,
                                     str(labels[seg_start_idx])))
                seg_start_idx = i
        raw_sections.append((seg_start_idx * bin_t, total_duration,
                             str(labels[-1])))

        # 过短段并入邻段 (同级别直接合并; 短段并入更长邻居)
        merged: list[list] = []
        for start, end, level in raw_sections:
            if end - start < 1e-3:
                continue
            if merged:
                p_start, p_end, p_level = merged[-1]
                if p_level == level or (end - start) < self.min_section_dur:
                    merged[-1] = [p_start, end, p_level if p_level == level else
                                  (p_level if p_end - p_start >= end - start else level)]
                    continue
            merged.append([start, end, level])

        # 计算段内平均能量 → DynamicSection
        sections: list[DynamicSection] = []
        for start, end, level in merged:
            b0 = int(start / bin_t)
            b1 = min(n_bins, max(b0 + 1, int(end / bin_t)))
            e_mean = float(intensity[b0:b1].mean()) if b1 > b0 else 0.5
            sections.append(DynamicSection(start, end, level, e_mean))

        # 首尾补全到 0 / total_duration
        if sections:
            sections[0].start = 0.0
            sections[-1].end = total_duration

        logger.info(f"动态分段: {len(sections)}段 "
                    f"{[f'{s.level}:{s.duration:.1f}s' for s in sections]}")
        return sections

    def level_at(self, sections: list[DynamicSection], t: float) -> str:
        """查询时间点的动态级别"""
        for s in sections:
            if s.contains(t):
                return s.level
        return "mid"

    def section_at(self, sections: list[DynamicSection], t: float) -> DynamicSection | None:
        for s in sections:
            if s.contains(t):
                return s
        return sections[-1] if sections else None

    # ------------------------------------------------------------------
    # 2. 切点密度规划 (快段密切 / 慢段少切)
    # ------------------------------------------------------------------
    def plan_cuts(self, sections: list[DynamicSection],
                  beats_sec: np.ndarray,
                  downbeats_sec: np.ndarray,
                  onsets_sec: np.ndarray,
                  min_shot_dur: float = 0.18) -> list[float]:
        """按动态级别规划切点网格

        策略 (借鉴 ai-montage-agent: 高潮0.3s密切 / 平静2s长镜头):
          high 段: onset ∪ beat 全部切点 (密切, 最小镜头0.18s)
          mid  段: beat 逐拍切点
          low  段: 仅 downbeat 切点 (长镜头), 重拍间隔>4s时补充beat
        """
        beats = sorted(float(b) for b in beats_sec)
        downbeats = sorted(float(d) for d in downbeats_sec)
        onsets = sorted(float(o) for o in onsets_sec)

        cut_set = set()
        for s in sections:
            if s.level == "high":
                pts = [p for p in onsets + beats if s.start <= p <= s.end]
            elif s.level == "low":
                pts = [p for p in downbeats if s.start <= p <= s.end]
                # 重拍间隔过大时补充普通拍 (防止>5s无切点的死镜头)
                gaps_ok = all(
                    pts[i + 1] - pts[i] <= 5.0 for i in range(len(pts) - 1))
                if not gaps_ok or not pts:
                    filler = [p for p in beats if s.start <= p <= s.end]
                    merged_low = sorted(set(pts + filler))
                    pts = [merged_low[0]]
                    for p in merged_low[1:]:
                        if p - pts[-1] > 4.0:
                            pts.append(p)
            else:  # mid
                pts = [p for p in beats if s.start <= p <= s.end]
            cut_set.update(pts)

        # 段边界也是切点 (动态切换处必须有镜头切换)
        for s in sections[1:]:
            cut_set.add(s.start)

        cuts = sorted(c for c in cut_set if 0.01 < c)

        # 最小镜头时长约束 (过近切点取拍点优先)
        filtered = [cuts[0]] if cuts else []
        for c in cuts[1:]:
            if c - filtered[-1] >= min_shot_dur:
                filtered.append(c)
            else:
                # 保留更接近拍点的那个
                prev = filtered[-1]
                d_prev = min((abs(prev - b) for b in beats), default=9)
                d_curr = min((abs(c - b) for b in beats), default=9)
                if d_curr < d_prev - 1e-3:
                    filtered[-1] = c

        return filtered

    # ------------------------------------------------------------------
    # 3. 变速映射 (随BGM卡点变速 — 用户核心诉求)
    # ------------------------------------------------------------------
    def speed_for_shot(self, level: str, beat_strength: str,
                       energy_norm: float, is_downbeat: bool) -> tuple[float, str]:
        """镜头级变速决策 — 变速跟随音乐动态

        铁律 (漫剪卡点铁律 §2, v22 已验证):
          low段(铺垫)   → 强拍0.55x慢放落点 / 普通0.7x
          mid段(蓄力)   → 强拍0.9x zoom_back / 普通1.0x static
          high段(爆发)  → 强拍1.0x pulse / 普通1.3x fast_pan

        Returns:
            (speed, technique) — 速度系数与对应技巧标签
        """
        if level == "low":
            if beat_strength == "strong" or is_downbeat:
                return 0.55, "slowmo"
            return 0.7, "slowmo"
        if level == "mid":
            if beat_strength == "strong" or is_downbeat:
                # 2026-09-02 节拍-镜头语法: 小节重音(强拍+downbeat)→0.55 慢镜落点,
                # 普通强拍→0.9 zoom_back (慢镜/缩放交替, 避免整段单一速度)
                if is_downbeat and beat_strength == "strong":
                    return 0.55, "slowmo"
                return 0.9, "zoom_back"
            return 1.0, "static"
        # high 段(爆发): 2026-09-02 用户语法——重鼓点=快切(1.3)+撞拍双切(见 _plan)。
        # 旧规则强拍 1.0 pulse 无速度变化, 在鼓点上没有"踩"感;
        # pulse 缩放效果保留在镜头内特效层, 速度层全部给撞击。
        return 1.3, "fast_pan"

    # ------------------------------------------------------------------
    # 4. 统计输出
    # ------------------------------------------------------------------
    @staticmethod
    def summarize(sections: list[DynamicSection]) -> dict[str, float]:
        """分段统计"""
        out: dict[str, float] = {"total_sections": len(sections)}
        for lvl in ("high", "mid", "low"):
            ss = [s for s in sections if s.level == lvl]
            out[f"{lvl}_count"] = len(ss)
            out[f"{lvl}_dur"] = round(sum(s.duration for s in ss), 2)
        return out
