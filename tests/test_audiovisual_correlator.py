# -*- coding: utf-8 -*-
"""tests/test_audiovisual_correlator.py — AudioVisualCorrelator 测试

覆盖: 数据结构/对齐/同步质量/脱拍段/切点建议/优化/集成场景
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.audiovisual_correlator import (
    AudioVisualCorrelator,
    BeatCutAlignment,
    CutSuggestion,
    OffBeatSegment,
    SyncAnalysisResult,
)


# ── 数据结构 ─────────────────────────────────────────────────
class TestDataStructures:
    def test_alignment(self):
        a = BeatCutAlignment(beat_time=1.0, nearest_cut_time=1.05,
                             deviation_ms=50, is_on_beat=True)
        assert a.deviation_ms == 50 and a.is_on_beat

    def test_off_beat(self):
        s = OffBeatSegment(start_time=5, end_time=8, duration=3,
                           avg_deviation_ms=200, severity="moderate")
        assert s.severity == "moderate"

    def test_suggestion(self):
        s = CutSuggestion(current_cut_time=1, suggested_time=1.05,
                           nearest_beat_time=1.05, shift_ms=50, reason="t")
        assert s.shift_ms == 50

    def test_result_defaults(self):
        r = SyncAnalysisResult()
        assert r.sync_score == 0.0 and r.sync_quality == "unknown"


# ── 初始化 ───────────────────────────────────────────────────
class TestInit:
    def test_defaults(self):
        c = AudioVisualCorrelator()
        assert c._tolerance_ms == 100 and c._tolerance_sec == 0.1

    def test_custom(self):
        c = AudioVisualCorrelator(tolerance_ms=50)
        assert c._tolerance_sec == 0.05


# ── 对齐测试 ─────────────────────────────────────────────────
class TestAlignment:
    def _c(self, tol=100):
        return AudioVisualCorrelator(tolerance_ms=tol)

    def test_perfect(self):
        r = self._c().analyze_sync([1, 2, 3], [1, 2, 3], duration=4)
        assert r.sync_score == 1.0 and r.on_beat_count == 3

    def test_within_tol(self):
        r = self._c().analyze_sync([1, 2, 3], [1.05, 2.08, 2.95], duration=4)
        assert r.sync_score == 1.0 and r.on_beat_count == 3

    def test_outside_tol(self):
        r = self._c().analyze_sync([1, 2, 3], [1.5, 2.5, 3.5], duration=4)
        assert r.sync_score == 0.0 and r.off_beat_count == 3

    def test_partial(self):
        r = self._c().analyze_sync([1, 2, 3, 4], [1.02, 2.5, 3.01, 4.5], duration=5)
        assert r.on_beat_count == 2 and r.off_beat_count == 2

    def test_more_beats(self):
        r = self._c().analyze_sync([1, 1.5, 2, 2.5, 3], [1, 2, 3], duration=4)
        assert r.total_beats == 5 and r.on_beat_count == 3

    def test_more_cuts(self):
        r = self._c().analyze_sync([1, 3], [0.5, 1, 1.5, 2, 2.5, 3, 3.5], duration=4)
        assert r.on_beat_count == 2

    def test_empty_beats(self):
        assert self._c().analyze_sync([], [1, 2], duration=3).sync_quality == "unknown"

    def test_empty_cuts(self):
        assert self._c().analyze_sync([1, 2], [], duration=3).sync_quality == "unknown"


# ── 同步质量分类 ─────────────────────────────────────────────
class TestSyncQuality:
    def test_excellent(self):
        assert AudioVisualCorrelator._classify(0.9, 30) == "excellent"

    def test_good(self):
        assert AudioVisualCorrelator._classify(0.7, 80) == "good"

    def test_fair(self):
        assert AudioVisualCorrelator._classify(0.5, 150) == "fair"

    def test_poor(self):
        assert AudioVisualCorrelator._classify(0.2, 300) == "poor"

    def test_boundaries(self):
        assert AudioVisualCorrelator._classify(0.8, 50) == "excellent"
        assert AudioVisualCorrelator._classify(0.6, 100) == "good"


# ── 脱拍段 ───────────────────────────────────────────────────
class TestOffBeat:
    def _c(self):
        return AudioVisualCorrelator(tolerance_ms=100, min_segment_duration=1)

    def test_none(self):
        r = self._c().analyze_sync([1, 2, 3], [1, 2, 3], duration=4)
        assert len(r.off_beat_segments) == 0

    def test_short_filtered(self):
        r = self._c().analyze_sync([1, 1.2, 3], [1.5, 1.7, 3], duration=4)
        assert len(r.off_beat_segments) == 0

    def test_long_detected(self):
        r = self._c().analyze_sync([1, 2, 3, 4, 5], [1.5, 2.5, 3.5, 4.5, 5.5], duration=6)
        assert len(r.off_beat_segments) >= 1
        assert r.off_beat_segments[0].severity == "severe"

    def test_severity(self):
        c = self._c()
        assert c._mk_off(0, 5, [100, 120, 130]).severity == "mild"
        assert c._mk_off(0, 5, [160, 180, 200]).severity == "moderate"
        assert c._mk_off(0, 5, [350, 400, 450]).severity == "severe"


# ── 切点建议 ─────────────────────────────────────────────────
class TestSuggestions:
    def _c(self):
        return AudioVisualCorrelator(tolerance_ms=100)

    def test_generated(self):
        r = self._c().analyze_sync([1, 2, 3], [1.3, 2.3, 3.3], duration=4)
        assert len(r.suggestions) == 3

    def test_none_when_aligned(self):
        r = self._c().analyze_sync([1, 2, 3], [1, 2, 3], duration=4)
        assert len(r.suggestions) == 0

    def test_shift_limit(self):
        r = self._c().analyze_sync([1], [2], duration=3)
        assert len(r.suggestions) == 0  # shift=1000ms > 500


# ── 切点优化 ─────────────────────────────────────────────────
class TestOptimization:
    def test_perfect(self):
        r = AudioVisualCorrelator().find_best_cut_times([1, 2, 3], [1, 2, 3])
        assert r == [1, 2, 3]

    def test_snap(self):
        r = AudioVisualCorrelator().find_best_cut_times([1, 2, 3], [1.1, 2.1], max_shift_ms=200)
        assert r == [1, 2]

    def test_beyond_limit(self):
        r = AudioVisualCorrelator().find_best_cut_times([1, 5], [3], max_shift_ms=200)
        assert r == [3]  # 3 is 2s from both beats

    def test_dedup(self):
        r = AudioVisualCorrelator().find_best_cut_times([1], [0.9, 1.1], max_shift_ms=200)
        assert len(r) == 1


# ── 快速接口 ─────────────────────────────────────────────────
class TestQuickMeasure:
    def test_basic(self):
        m = AudioVisualCorrelator().measure_sync_quality([1, 2, 3], [1, 2, 3])
        assert m["sync_score"] == 1.0 and m["on_beat_ratio"] == 1.0

    def test_poor(self):
        m = AudioVisualCorrelator().measure_sync_quality([1, 2, 3], [1.5, 2.5, 3.5])
        assert m["sync_score"] == 0.0


# ── 集成场景 ─────────────────────────────────────────────────
class TestIntegration:
    def test_amv_sync(self):
        beats = [0.23 * i for i in range(1, 20)]  # ~130 BPM
        cuts = [round(b + np.random.uniform(-0.05, 0.05), 4) for b in beats]
        r = AudioVisualCorrelator(tolerance_ms=100).analyze_sync(
            beats, cuts, duration=5)
        assert r.sync_score > 0.7
        assert r.sync_quality in ("excellent", "good")

    def test_empty(self):
        r = AudioVisualCorrelator().analyze_sync([], [], duration=0)
        assert r.sync_quality == "unknown"

    def test_single(self):
        r = AudioVisualCorrelator().analyze_sync([1.0], [1.0], duration=2)
        assert r.sync_score == 1.0


# ── beat_this 升级后端 ─────────────────────────────────────────
class TestBeatThisBackend:
    def test_detect_beats_lazy_init(self):
        """beat_this 模型应懒加载"""
        c = AudioVisualCorrelator()
        assert c._beat_model is None

    def test_detect_beats_mock(self):
        """mock beat_this 模型应返回节拍时间"""
        c = AudioVisualCorrelator()
        mock_model = MagicMock(return_value=(
            np.array([0.5, 1.0, 1.5]), np.array([0.5])))
        c._beat_model = mock_model
        with patch('librosa.load', return_value=(np.zeros(44100), 44100)):
            result = c.detect_beats("test.mp3")
        assert len(result["beats"]) == 3
        assert len(result["downbeats"]) == 1
        mock_model.assert_called_once()

    def test_detect_beats_return_type(self):
        """返回值应为 dict 含 beats/downbeats 列表"""
        c = AudioVisualCorrelator()
        c._beat_model = MagicMock(return_value=(np.array([]), np.array([])))
        with patch('librosa.load', return_value=(np.zeros(1000), 22050)):
            result = c.detect_beats("test.mp3", device="cpu")
        assert isinstance(result, dict)
        assert "beats" in result and "downbeats" in result
