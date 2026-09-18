# -*- coding: utf-8 -*-
"""AudioVisualCorrelator — 音视频因果对齐引擎

节拍-切点对齐 / 踩拍率量化 / 脱拍段检测 / 切点优化建议。
纯 numpy，零 API 成本。输入 BeatInfo / ShotStructure / MotionProfile。
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── 数据结构 ─────────────────────────────────────────────────
@dataclass
class BeatCutAlignment:
    beat_time: float; nearest_cut_time: float
    deviation_ms: float; is_on_beat: bool; beat_strength: float = 1.0

@dataclass
class OffBeatSegment:
    start_time: float; end_time: float; duration: float
    avg_deviation_ms: float; severity: str  # mild/moderate/severe

@dataclass
class CutSuggestion:
    current_cut_time: float; suggested_time: float
    nearest_beat_time: float; shift_ms: float; reason: str

@dataclass
class SyncAnalysisResult:
    video_path: str = ""; audio_path: str = ""; duration: float = 0.0
    sync_score: float = 0.0; avg_deviation_ms: float = 0.0
    median_deviation_ms: float = 0.0; max_deviation_ms: float = 0.0
    alignments: list[BeatCutAlignment] = field(default_factory=list)
    on_beat_count: int = 0; off_beat_count: int = 0
    off_beat_segments: list[OffBeatSegment] = field(default_factory=list)
    suggestions: list[CutSuggestion] = field(default_factory=list)
    sync_quality: str = "unknown"  # excellent/good/fair/poor
    total_beats: int = 0; total_cuts: int = 0; tolerance_ms: float = 100.0


# ── 对齐器 ───────────────────────────────────────────────────
class AudioVisualCorrelator:
    """节拍-切点对齐 + 同步质量评分 + 脱拍段定位 + 优化建议"""

    def __init__(self, tolerance_ms=100.0, min_segment_duration=1.0):
        self._tolerance_ms = tolerance_ms
        self._tolerance_sec = tolerance_ms / 1000.0
        self._min_seg_dur = min_segment_duration
        self._beat_model = None  # beat_this 懒加载

    # ── 公开接口 ─────────────────────────────────────────────
    def analyze_sync(self, beat_times: list[float],
                     cut_times: list[float] | None = None,
                     shot_structure: Any | None = None,
                     motion_profile: Any | None = None,
                     video_path: str = "", audio_path: str = "",
                     duration: float = 0.0) -> SyncAnalysisResult:
        """分析音视频同步质量"""
        if cut_times is None and shot_structure is not None:
            cut_times = self._extract_cuts(shot_structure)
        if not cut_times or not beat_times:
            return SyncAnalysisResult(
                video_path=video_path, audio_path=audio_path, duration=duration,
                total_beats=len(beat_times), total_cuts=len(cut_times or []),
                sync_quality="unknown")
        if duration <= 0:
            duration = max(max(beat_times), max(cut_times))

        aligns = self._align(beat_times, cut_times)
        score, avg_d, med_d, max_d = self._metrics(aligns)
        off_segs = self._off_beat_segs(aligns, duration)
        sugs = self._suggestions(aligns, beat_times, cut_times)
        quality = self._classify(score, avg_d)
        on = sum(1 for a in aligns if a.is_on_beat)

        return SyncAnalysisResult(
            video_path=video_path, audio_path=audio_path,
            duration=round(duration, 3), sync_score=round(score, 4),
            avg_deviation_ms=round(avg_d, 2), median_deviation_ms=round(med_d, 2),
            max_deviation_ms=round(max_d, 2), alignments=aligns,
            on_beat_count=on, off_beat_count=len(aligns) - on,
            off_beat_segments=off_segs, suggestions=sugs,
            sync_quality=quality, total_beats=len(beat_times),
            total_cuts=len(cut_times), tolerance_ms=self._tolerance_ms)

    def measure_sync_quality(self, beat_times: list[float],
                             cut_times: list[float]) -> dict[str, float]:
        """快速同步质量 {sync_score, avg_deviation_ms, on_beat_ratio}"""
        aligns = self._align(beat_times, cut_times)
        score, avg_d, _, _ = self._metrics(aligns)
        on = sum(1 for a in aligns if a.is_on_beat)
        return {"sync_score": round(score, 4), "avg_deviation_ms": round(avg_d, 2),
                "on_beat_ratio": round(on / max(len(aligns), 1), 4)}

    def find_best_cut_times(self, beat_times: list[float],
                            current_cuts: list[float],
                            max_shift_ms=200.0) -> list[float]:
        """将切点吸附到最近节拍（max_shift_ms 范围内）"""
        mx = max_shift_ms / 1000.0
        opt = []
        for c in sorted(current_cuts):
            if not beat_times:
                opt.append(c); continue
            devs = [abs(c - b) for b in beat_times]
            nb = beat_times[int(np.argmin(devs))]
            opt.append(round(nb, 4) if abs(c - nb) <= mx else round(c, 4))
        return sorted(set(opt))

    # ── 内部 ─────────────────────────────────────────────────
    def _align(self, beats: list[float], cuts: list[float]) -> list[BeatCutAlignment]:
        ca = np.array(cuts)
        result = []
        for bt in beats:
            devs = np.abs(ca - bt)
            idx = int(np.argmin(devs))
            nc, d_ms = float(ca[idx]), abs(bt - float(ca[idx])) * 1000.0
            result.append(BeatCutAlignment(
                beat_time=round(bt, 4), nearest_cut_time=round(nc, 4),
                deviation_ms=round(d_ms, 2), is_on_beat=d_ms <= self._tolerance_ms))
        return result

    def _metrics(self, aligns: list[BeatCutAlignment]) -> tuple[float, float, float, float]:
        if not aligns:
            return 0.0, 0.0, 0.0, 0.0
        ds = np.array([a.deviation_ms for a in aligns])
        on = sum(1 for d in ds if d <= self._tolerance_ms)
        return on / len(aligns), float(np.mean(ds)), float(np.median(ds)), float(np.max(ds))

    def _off_beat_segs(self, aligns: list[BeatCutAlignment],
                       duration: float) -> list[OffBeatSegment]:
        offs = [a for a in aligns if not a.is_on_beat]
        if not offs:
            return []
        segs: list[OffBeatSegment] = []
        s0, devs = offs[0].beat_time, [offs[0].deviation_ms]
        for i in range(1, len(offs)):
            p, c = offs[i-1], offs[i]
            if c.beat_time - p.beat_time < 2.0:
                devs.append(c.deviation_ms)
            else:
                if p.beat_time - s0 >= self._min_seg_dur:
                    segs.append(self._mk_off(s0, p.beat_time, devs))
                s0, devs = c.beat_time, [c.deviation_ms]
        if offs[-1].beat_time - s0 >= self._min_seg_dur:
            segs.append(self._mk_off(s0, offs[-1].beat_time, devs))
        return segs

    @staticmethod
    def _mk_off(s: float, e: float, devs: list[float]) -> OffBeatSegment:
        avg = float(np.mean(devs))
        sev = "severe" if avg > 300 else "moderate" if avg > 150 else "mild"
        return OffBeatSegment(start_time=round(s, 3), end_time=round(e, 3),
                              duration=round(e - s, 3), avg_deviation_ms=round(avg, 2),
                              severity=sev)

    def _suggestions(self, aligns, beats, cuts) -> list[CutSuggestion]:
        sugs = []
        for c in cuts:
            devs = [(abs(c - b), b) for b in beats]
            if not devs:
                continue
            md, nb = min(devs, key=lambda x: x[0])
            shift = (nb - c) * 1000.0
            if md * 1000 > self._tolerance_ms and abs(shift) <= 500:
                sugs.append(CutSuggestion(
                    current_cut_time=round(c, 4), suggested_time=round(nb, 4),
                    nearest_beat_time=round(nb, 4), shift_ms=round(shift, 2),
                    reason=f"偏移 {abs(shift):.0f}ms，建议移至节拍 {nb:.3f}s"))
        return sugs

    @staticmethod
    def _classify(score: float, avg_dev: float) -> str:
        if score >= 0.8 and avg_dev <= 50: return "excellent"
        if score >= 0.6 and avg_dev <= 100: return "good"
        if score >= 0.4 and avg_dev <= 200: return "fair"
        return "poor"

    @staticmethod
    def _extract_cuts(ss: Any) -> list[float]:
        if not hasattr(ss, "shots"):
            return []
        return [s.start_time for s in ss.shots if hasattr(s, "start_time")]

    # ── beat_this GPU 节拍检测 ─────────────────────────────────
    def detect_beats(self, audio_path: str, device: str = "cuda") -> dict[str, list[float]]:
        """beat_this 神经网络节拍检测（精度远高于 librosa onset）

        Returns: {"beats": [...], "downbeats": [...]}
        """
        import librosa
        if self._beat_model is None:
            from beat_this.inference import Audio2Beats
            self._beat_model = Audio2Beats(device=device)
        y, sr = librosa.load(audio_path, sr=None, mono=True)
        beats, downbeats = self._beat_model(y, sr)
        return {"beats": beats.tolist(), "downbeats": downbeats.tolist()}
