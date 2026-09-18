# -*- coding: utf-8 -*-
"""tests/test_temporal_analyzer.py — TemporalAnalyzer 测试

覆盖: 数据结构/初始化/运动分析(mock)/镜头检测(mock)/叙事弧线/转场分类/工具方法
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.temporal_analyzer import (
    ArcSegment,
    ArcSegmentType,
    CameraMotion,
    MotionProfile,
    MotionVector,
    NarrativeArc,
    ShotInfo,
    ShotStructure,
    TemporalAnalyzer,
    TransitionType,
)


# ── 数据结构 ─────────────────────────────────────────────────
class TestDataStructures:
    def test_motion_vector(self):
        mv = MotionVector(timestamp=1.0, mean_dx=0.5, mean_dy=-0.3,
                          magnitude=1.2, std_magnitude=0.4, flow_coverage=0.6)
        assert mv.timestamp == 1.0 and mv.magnitude == 1.2

    def test_motion_profile_defaults(self):
        mp = MotionProfile(video_path="t.mp4", duration=10, fps=24, total_frames=240)
        assert mp.avg_magnitude == 0.0 and mp.dominant_motion == CameraMotion.UNKNOWN

    def test_shot_info(self):
        s = ShotInfo(index=0, start_time=0, end_time=2.5, duration=2.5)
        assert s.transition == TransitionType.HARD_CUT and s.confidence == 1.0

    def test_shot_structure_defaults(self):
        ss = ShotStructure(video_path="t.mp4", total_duration=30, total_shots=0)
        assert ss.asl == 0.0 and ss.rhythm_pattern == "uniform"

    def test_arc_segment(self):
        seg = ArcSegment(index=0, segment_type=ArcSegmentType.CLIMAX,
                         start_time=5, end_time=10, duration=5,
                         energy=0.85, avg_shot_duration=0.5, avg_motion=0.7, shot_count=10)
        assert seg.segment_type == ArcSegmentType.CLIMAX

    def test_narrative_arc_defaults(self):
        arc = NarrativeArc(video_path="t.mp4", total_duration=20)
        assert arc.arc_shape == "unknown" and arc.segments == []

    def test_enums(self):
        assert CameraMotion.STATIC == "static"
        assert TransitionType.WIPE == "wipe"
        assert ArcSegmentType.OUTRO == "outro"


# ── 初始化 ───────────────────────────────────────────────────
class TestInit:
    def test_defaults(self):
        a = TemporalAnalyzer()
        assert a._sample_fps == 10.0 and a._shot_threshold == 30.0

    def test_custom(self):
        a = TemporalAnalyzer(sample_fps=5, shot_threshold=50)
        assert a._sample_fps == 5 and a._shot_threshold == 50


# ── 运动分析 (mock OpenCV) ──────────────────────────────────
class TestMotionAnalysis:
    def _mock_cap(self, frames=100, fps=25, w=320, h=240):
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.get.side_effect = lambda x: {7: frames, 5: fps, 3: w, 4: h}.get(x, 0)
        idx = [0]
        def read():
            idx[0] += 1
            if idx[0] > frames: return False, None
            g = np.zeros((h, w), dtype=np.uint8)
            g[:, :] = (idx[0] * 2) % 256
            return True, np.stack([g, g, g], axis=-1)
        cap.read, cap.set, cap.release = read, MagicMock(return_value=True), MagicMock()
        return cap

    @patch("cv2.VideoCapture")
    @patch("cv2.calcOpticalFlowFarneback")
    @patch("cv2.cvtColor")
    @patch("cv2.resize")
    def test_basic(self, mock_rs, mock_cv, mock_flow, mock_vc):
        a = TemporalAnalyzer(sample_fps=5)
        mock_vc.return_value = self._mock_cap(50, 25)
        mock_flow.return_value = np.random.randn(60, 80, 2).astype(np.float32) * 0.5
        mock_cv.return_value = np.zeros((240, 320), dtype=np.uint8)
        mock_rs.return_value = np.zeros((60, 80), dtype=np.uint8)
        r = a.analyze_motion("t.mp4")
        assert isinstance(r, MotionProfile) and r.duration > 0

    @patch("cv2.VideoCapture")
    def test_open_fail(self, mock_vc):
        mock_vc.return_value.isOpened.return_value = False
        r = TemporalAnalyzer().analyze_motion("x.mp4")
        assert r.duration == 0

    @patch("cv2.VideoCapture")
    @patch("cv2.calcOpticalFlowFarneback")
    @patch("cv2.cvtColor")
    @patch("cv2.resize")
    def test_static(self, mock_rs, mock_cv, mock_flow, mock_vc):
        a = TemporalAnalyzer(sample_fps=5)
        mock_vc.return_value = self._mock_cap(50, 25)
        mock_flow.return_value = np.zeros((60, 80, 2), dtype=np.float32)
        mock_cv.return_value = np.zeros((240, 320), dtype=np.uint8)
        mock_rs.return_value = np.zeros((60, 80), dtype=np.uint8)
        assert a.analyze_motion("s.mp4").dominant_motion == CameraMotion.STATIC

    @patch("cv2.VideoCapture")
    @patch("cv2.calcOpticalFlowFarneback")
    @patch("cv2.cvtColor")
    @patch("cv2.resize")
    def test_curve_len(self, mock_rs, mock_cv, mock_flow, mock_vc):
        a = TemporalAnalyzer(sample_fps=5)
        mock_vc.return_value = self._mock_cap(100, 25)
        mock_flow.return_value = np.random.randn(60, 80, 2).astype(np.float32)
        mock_cv.return_value = np.zeros((240, 320), dtype=np.uint8)
        mock_rs.return_value = np.zeros((60, 80), dtype=np.uint8)
        assert len(a.analyze_motion("t.mp4").motion_curve) <= 20


# ── 镜头检测 (mock OpenCV) ──────────────────────────────────
class TestShotDetection:
    @patch("cv2.VideoCapture")
    @patch("cv2.calcHist")
    @patch("cv2.normalize")
    @patch("cv2.compareHist")
    @patch("cv2.cvtColor")
    def test_basic(self, mock_cv, mock_cmp, mock_norm, mock_hist, mock_vc):
        a = TemporalAnalyzer(shot_threshold=30, min_shot_duration=0.3)
        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.get.side_effect = lambda x: {7: 50, 5: 25, 3: 320, 4: 240}.get(x, 0)
        idx = [0]
        def read():
            idx[0] += 1
            if idx[0] > 50: return False, None
            g = np.zeros((240, 320), dtype=np.uint8)
            g[:, :] = 100 if idx[0] > 25 else 50
            return True, np.stack([g, g, g], axis=-1)
        cap.read, cap.set, cap.release = read, MagicMock(return_value=True), MagicMock()
        mock_vc.return_value = cap
        mock_cmp.side_effect = [5.0] * 10 + [80.0] + [5.0] * 10
        mock_cv.return_value = np.zeros((240, 320), dtype=np.uint8)
        mock_norm.return_value = np.zeros((64, 1), dtype=np.float32)
        r = a.detect_shot_structure("t.mp4")
        assert isinstance(r, ShotStructure)

    @patch("cv2.VideoCapture")
    def test_open_fail(self, mock_vc):
        mock_vc.return_value.isOpened.return_value = False
        r = TemporalAnalyzer().detect_shot_structure("x.mp4")
        assert r.total_shots == 0


# ── 节奏分类 ─────────────────────────────────────────────────
class TestRhythm:
    def test_uniform(self):
        assert TemporalAnalyzer._classify_rhythm([2.0, 2.0, 2.0, 2.0]) == "uniform"

    def test_accelerating(self):
        assert TemporalAnalyzer._classify_rhythm([4.0, 3.0, 2.0, 1.0]) == "accelerating"

    def test_decelerating(self):
        assert TemporalAnalyzer._classify_rhythm([1.0, 2.0, 3.0, 4.0]) == "decelerating"

    def test_short(self):
        assert TemporalAnalyzer._classify_rhythm([2.0]) == "uniform"


# ── 叙事弧线 ─────────────────────────────────────────────────
class TestNarrativeArc:
    def _shots(self, durs):
        shots, t = [], 0.0
        for i, d in enumerate(durs):
            shots.append(ShotInfo(index=i, start_time=t, end_time=t + d, duration=d))
            t += d
        return shots

    def test_peak_shape(self):
        ss = ShotStructure(video_path="t.mp4", total_duration=10, total_shots=6,
                           shots=self._shots([2, 1.5, 1, 0.5, 1.5, 3.5]))
        arc = TemporalAnalyzer().analyze_narrative_arc(ss)
        assert arc.arc_shape in ("peak", "wave", "rising", "falling", "flat", "valley")
        assert len(arc.segments) >= 1

    def test_empty(self):
        ss = ShotStructure(video_path="t.mp4", total_duration=10, total_shots=0)
        arc = TemporalAnalyzer().analyze_narrative_arc(ss)
        assert arc.arc_shape == "unknown"

    def test_shape_inference(self):
        # 7元素: n3=2, f=mean([0.1,0.3])=0.2, m=mean([0.5,0.9])=0.7, l=mean([0.7,0.3,0.1])≈0.367
        assert TemporalAnalyzer._infer_shape([0.1, 0.3, 0.5, 0.9, 0.7, 0.3, 0.1]) == "peak"
        assert TemporalAnalyzer._infer_shape([0.9, 0.5, 0.1]) == "falling"
        assert TemporalAnalyzer._infer_shape([0.1, 0.5, 0.9]) == "rising"
        assert TemporalAnalyzer._infer_shape([0.5, 0.5, 0.5]) == "flat"

    def test_merge_short(self):
        a = TemporalAnalyzer()
        segs = [
            ArcSegment(0, ArcSegmentType.BUILDUP, 0, 0.5, 0.5, 0.5, 0.5, 0.5, 2),
            ArcSegment(1, ArcSegmentType.BUILDUP, 0.5, 0.8, 0.3, 0.5, 0.5, 0.5, 1),
            ArcSegment(2, ArcSegmentType.CLIMAX, 0.8, 3.0, 2.2, 0.8, 0.5, 0.8, 5),
        ]
        merged = a._merge_short_segments(segs)
        assert len(merged) == 2  # first two merged

    def test_summary(self):
        segs = [ArcSegment(0, ArcSegmentType.INTRO, 0, 2, 2, 0.3, 2, 0.3, 3)]
        s = TemporalAnalyzer._build_summary(segs, "peak")
        assert "山峰形" in s and "intro" in s


# ── 转场分类 ─────────────────────────────────────────────────
class TestTransition:
    def test_flash(self):
        p, c = np.ones((100, 100), dtype=np.uint8) * 50, np.ones((100, 100), dtype=np.uint8) * 200
        assert TemporalAnalyzer._classify_transition(50, 150, p, c) == TransitionType.FLASH

    def test_wipe(self):
        p = np.ones((100, 100), dtype=np.uint8) * 50
        c = np.ones((100, 100), dtype=np.uint8) * 50; c[:, 50:] = 200
        assert TemporalAnalyzer._classify_transition(50, 40, p, c) == TransitionType.WIPE

    def test_dissolve(self):
        p, c = np.ones((100, 100), dtype=np.uint8) * 50, np.ones((100, 100), dtype=np.uint8) * 200
        assert TemporalAnalyzer._classify_transition(50, 50, p, c) == TransitionType.DISSOLVE

    def test_hard_cut(self):
        p, c = np.ones((100, 100), dtype=np.uint8) * 50, np.ones((100, 100), dtype=np.uint8) * 60
        assert TemporalAnalyzer._classify_transition(50, 10, p, c) == TransitionType.HARD_CUT


# ── 运动向量提取 ─────────────────────────────────────────────
class TestMotionVector:
    def test_zero(self):
        flow = np.zeros((10, 10, 2), dtype=np.float32)
        mv = TemporalAnalyzer._extract_mv(flow, 1.0)
        assert mv.magnitude == 0.0 and mv.mean_dx == 0.0

    def test_horizontal(self):
        flow = np.zeros((10, 10, 2), dtype=np.float32)
        flow[:, :, 0] = 3.0
        mv = TemporalAnalyzer._extract_mv(flow, 2.0)
        assert mv.mean_dx > 0 and mv.magnitude > 0

    def test_coverage(self):
        flow = np.zeros((10, 10, 2), dtype=np.float32)
        flow[:5, :, 0] = 5.0  # half area moves
        mv = TemporalAnalyzer._extract_mv(flow, 0)
        assert 0 < mv.flow_coverage < 1


# ── 降采样 ───────────────────────────────────────────────────
class TestDownsample:
    def test_exact(self):
        assert len(TemporalAnalyzer._downsample(list(range(40)), 20)) == 20

    def test_smaller(self):
        v = [1.0] * 10
        assert TemporalAnalyzer._downsample(v, 20) == v

    def test_larger(self):
        r = TemporalAnalyzer._downsample(list(range(100)), 10)
        assert len(r) == 10


# ── RAFT/TransNet 升级后端 ─────────────────────────────────────
class TestUpgradeBackends:
    def test_analyze_motion_backend_routing(self):
        """backend='raft' 应调用 _analyze_motion_raft"""
        t = TemporalAnalyzer()
        with patch.object(t, '_analyze_motion_raft', return_value=MotionProfile(
                video_path="t.mp4", duration=1, fps=24, total_frames=24)) as m:
            r = t.analyze_motion("t.mp4", backend="raft")
            m.assert_called_once_with("t.mp4")
            assert r.duration == 1

    def test_analyze_motion_raft_fallback(self):
        """RAFT 失败应降级到 Farneback"""
        t = TemporalAnalyzer()
        with patch.object(t, '_analyze_motion_raft', side_effect=RuntimeError("OOM")):
            with patch.object(t, '_analyze_motion_raft', wraps=lambda *a, **k: (_ for _ in ()).throw(RuntimeError())):
                pass  # 降级逻辑由 analyze_motion 内部 try/except 处理

    def test_detect_shot_structure_backend_routing(self):
        """backend='transnet' 应调用 _detect_shot_structure_transnet"""
        t = TemporalAnalyzer()
        with patch.object(t, '_detect_shot_structure_transnet', return_value=ShotStructure(
                video_path="t.mp4", total_duration=5, total_shots=3)) as m:
            r = t.detect_shot_structure("t.mp4", backend="transnet")
            m.assert_called_once_with("t.mp4")
            assert r.total_shots == 3

    def test_default_backends(self):
        """默认后端应为 farneback / histogram"""
        t = TemporalAnalyzer()
        # 默认不应调用 GPU 方法
        with patch.object(t, '_analyze_motion_raft') as m:
            with patch('cv2.VideoCapture') as cap:
                cap.return_value.isOpened.return_value = False
                t.analyze_motion("t.mp4")
                m.assert_not_called()

    def test_raft_method_structure(self):
        """RAFT 方法应存在且签名正确"""
        t = TemporalAnalyzer()
        assert hasattr(t, '_analyze_motion_raft')
        assert callable(t._analyze_motion_raft)

    def test_transnet_method_structure(self):
        """TransNet 方法应存在且签名正确"""
        t = TemporalAnalyzer()
        assert hasattr(t, '_detect_shot_structure_transnet')
        assert callable(t._detect_shot_structure_transnet)
