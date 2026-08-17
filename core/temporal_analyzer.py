# -*- coding: utf-8 -*-
"""TemporalAnalyzer — 时间维度视频理解 (光流/镜头结构/叙事弧线)

纯本地 OpenCV+numpy，零 API 成本。缺失鲁棒：任意分析失败时降级。
输出兼容 MultimodalEmbedding / DirectorSegment。
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────
class CameraMotion(str, Enum):
    STATIC = "static"; PAN_LEFT = "pan_left"; PAN_RIGHT = "pan_right"
    TILT_UP = "tilt_up"; TILT_DOWN = "tilt_down"
    ZOOM_IN = "zoom_in"; ZOOM_OUT = "zoom_out"
    HANDHELD = "handheld"; TRACKING = "tracking"; COMPLEX = "complex"
    UNKNOWN = "unknown"

class TransitionType(str, Enum):
    HARD_CUT = "hard_cut"; FADE = "fade"; DISSOLVE = "dissolve"
    WIPE = "wipe"; FLASH = "flash"; UNKNOWN = "unknown"

class ArcSegmentType(str, Enum):
    INTRO = "intro"; BUILDUP = "buildup"; CLIMAX = "climax"
    RELEASE = "release"; BREATH = "breath"; OUTRO = "outro"
    UNKNOWN = "unknown"


# ── 数据结构 ─────────────────────────────────────────────────
@dataclass
class MotionVector:
    timestamp: float; mean_dx: float; mean_dy: float
    magnitude: float; std_magnitude: float; flow_coverage: float

@dataclass
class MotionProfile:
    video_path: str; duration: float; fps: float; total_frames: int
    avg_magnitude: float = 0.0; max_magnitude: float = 0.0
    motion_variance: float = 0.0
    dominant_motion: CameraMotion = CameraMotion.UNKNOWN
    motion_segments: List[Dict[str, Any]] = field(default_factory=list)
    shake_score: float = 0.0
    shake_segments: List[Dict] = field(default_factory=list)
    motion_curve: List[float] = field(default_factory=list)

@dataclass
class ShotInfo:
    index: int; start_time: float; end_time: float; duration: float
    transition: TransitionType = TransitionType.HARD_CUT
    confidence: float = 1.0

@dataclass
class ShotStructure:
    video_path: str; total_duration: float; total_shots: int
    shots: List[ShotInfo] = field(default_factory=list)
    asl: float = 0.0; cut_rate: float = 0.0; shot_duration_std: float = 0.0
    transition_distribution: Dict[str, int] = field(default_factory=dict)
    rhythm_pattern: str = "uniform"

@dataclass
class ArcSegment:
    index: int; segment_type: ArcSegmentType
    start_time: float; end_time: float; duration: float
    energy: float; avg_shot_duration: float; avg_motion: float
    shot_count: int; description: str = ""

@dataclass
class NarrativeArc:
    video_path: str; total_duration: float
    segments: List[ArcSegment] = field(default_factory=list)
    overall_energy: float = 0.0
    energy_range: Tuple[float, float] = (0.0, 0.0)
    arc_shape: str = "unknown"
    structure_summary: str = ""


# ── 分析器 ───────────────────────────────────────────────────
class TemporalAnalyzer:
    """光流运镜分类 + 直方图切点检测 + 叙事弧线推断"""

    def __init__(self, sample_fps=10.0, shot_threshold=30.0,
                 min_shot_duration=0.3, flow_scale=0.25):
        self._sample_fps = sample_fps
        self._shot_threshold = shot_threshold
        self._min_shot_duration = min_shot_duration
        self._flow_scale = flow_scale

    # ── 公开接口 ─────────────────────────────────────────────
    def analyze_motion(self, video_path: str, backend: str = "farneback") -> MotionProfile:
        """光流运动分析 — farneback(CPU) 或 raft(GPU)"""
        if backend == "raft":
            try:
                return self._analyze_motion_raft(video_path)
            except Exception as e:
                logger.warning(f"RAFT 失败，降级 Farneback: {e}")
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"无法打开视频: {video_path}")
            return MotionProfile(video_path=video_path, duration=0, fps=0, total_frames=0)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        sw, sh = int(w * self._flow_scale), int(h * self._flow_scale)
        step = max(1, int(fps / self._sample_fps))

        prev_gray = None
        vectors: List[MotionVector] = []
        timestamps: List[float] = []

        # 顺序读取 + 跳帧: cap.set 随机 seek 在 4K 长 GOP 视频上每次都要
        # 解关键帧链(实测单素材 300s+), 顺序 read 丢弃不要帧快一个数量级
        idx = 0
        keep_counter = step
        while idx < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if keep_counter >= step:
                gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (sw, sh))
                if prev_gray is not None:
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None,
                        pyr_scale=0.5, levels=3, winsize=15,
                        iterations=3, poly_n=5, poly_sigma=1.2, flags=0)
                    vectors.append(self._extract_mv(flow, idx / fps))
                    timestamps.append(idx / fps)
                prev_gray = gray
                keep_counter = 0
            keep_counter += 1
            idx += 1
        cap.release()

        if not vectors:
            return MotionProfile(video_path=video_path, duration=duration,
                                 fps=fps, total_frames=total_frames)

        return self.build_motion_profile(
            video_path, duration, fps, total_frames, vectors, timestamps)

    def build_motion_profile(self, video_path: str, duration: float, fps: float,
                             total_frames: int, vectors: List[MotionVector],
                             timestamps: List[float]) -> MotionProfile:
        """从光流向量序列聚合出 MotionProfile。

        独立 helper：整文件分析与分段缓存合并共用同一聚合逻辑，
        保证两条路径输出完全一致。
        """
        if not vectors:
            return MotionProfile(video_path=video_path, duration=duration,
                                 fps=fps, total_frames=total_frames)

        mags = [v.magnitude for v in vectors]
        avg_mag, max_mag = float(np.mean(mags)), float(np.max(mags))
        shake = min(1.0, float(np.std(mags)) / max(avg_mag, 0.01) / 3.0)

        return MotionProfile(
            video_path=video_path, duration=duration, fps=fps,
            total_frames=total_frames,
            avg_magnitude=round(avg_mag, 4), max_magnitude=round(max_mag, 4),
            motion_variance=round(float(np.var(mags)), 4),
            dominant_motion=self._classify_motion(vectors),
            motion_segments=self._segment_motion(vectors, timestamps),
            shake_score=round(shake, 4),
            shake_segments=self._detect_shake_segs(vectors, timestamps),
            motion_curve=[round(v, 4) for v in self._downsample(mags)],
        )

    def detect_shot_structure(self, video_path: str, backend: str = "histogram") -> ShotStructure:
        """镜头切点检测 — histogram(CPU) 或 transnet(GPU)"""
        if backend == "transnet":
            try:
                return self._detect_shot_structure_transnet(video_path)
            except Exception as e:
                logger.warning(f"TransNet 失败，降级 histogram: {e}")
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return ShotStructure(video_path=video_path, total_duration=0, total_shots=0)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        sample_step = max(1, int(fps / 5.0))

        prev_hist, prev_frame = None, None
        boundaries: List[Tuple[float, float, str]] = []

        # 顺序读取 + 跳帧 (同 analyze_motion: 避免 4K 随机 seek 解关键帧链)
        idx = 0
        keep_counter = sample_step
        while idx < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if keep_counter >= sample_step:
                # 下采样到固定小尺寸: 直方图对分辨率不敏感, 4K 全幅 calcHist
                # + 逐像素差分(两个 3840×2160 float 数组)是性能杀手(单素材数十秒)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (480, 270), interpolation=cv2.INTER_AREA)
                hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                                     None).flatten()
                t = idx / fps
                if prev_hist is not None:
                    hd = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR))
                    pd = float(np.mean(np.abs(gray.astype(float) - prev_frame.astype(float)))) \
                        if prev_frame is not None else 0.0
                    if hd > self._shot_threshold:
                        tt = self._classify_transition(hd, pd, prev_frame, gray)
                        boundaries.append((t, min(hd / 100.0, 1.0), tt))
                prev_hist = hist
                prev_frame = gray.copy()
                keep_counter = 0
            keep_counter += 1
            idx += 1
        cap.release()

        return self.build_shot_structure(video_path, duration, boundaries)

    def build_shot_structure(self, video_path: str, duration: float,
                             boundaries: List[Tuple[float, float, str]]) -> ShotStructure:
        """从镜头边界列表聚合出 ShotStructure（整文件与分段缓存共用）。"""
        shots = self._build_shots(boundaries, duration)
        durs = [s.duration for s in shots]
        asl = float(np.mean(durs)) if durs else duration
        dist: Dict[str, int] = {}
        for s in shots:
            dist[s.transition.value] = dist.get(s.transition.value, 0) + 1

        return ShotStructure(
            video_path=video_path, total_duration=duration,
            total_shots=len(shots), shots=shots,
            asl=round(asl, 3), cut_rate=round(len(shots) / max(duration, 0.001), 3),
            shot_duration_std=round(float(np.std(durs)), 3) if len(durs) > 1 else 0.0,
            transition_distribution=dist,
            rhythm_pattern=self._classify_rhythm(durs))

    def analyze_narrative_arc(self, ss: ShotStructure,
                              motion: Optional[MotionProfile] = None,
                              beat_times: Optional[List[float]] = None) -> NarrativeArc:
        """镜头结构+运动 → 叙事段落/弧线形状"""
        if not ss.shots:
            return NarrativeArc(video_path=ss.video_path, total_duration=ss.total_duration)

        segs = self._segment_narrative(ss.shots, motion)
        energies = [s.energy for s in segs]
        shape = self._infer_shape(energies)
        summary = self._build_summary(segs, shape)

        return NarrativeArc(
            video_path=ss.video_path, total_duration=ss.total_duration,
            segments=segs,
            overall_energy=round(float(np.mean(energies)), 3) if energies else 0.5,
            energy_range=(round(float(np.min(energies)), 3) if energies else 0.0,
                          round(float(np.max(energies)), 3) if energies else 1.0),
            arc_shape=shape, structure_summary=summary)

    # ── 运动分析内部 ─────────────────────────────────────────
    @staticmethod
    def _extract_mv(flow: np.ndarray, ts: float) -> MotionVector:
        dx, dy = flow[:, :, 0], flow[:, :, 1]
        mag = np.sqrt(dx**2 + dy**2)
        return MotionVector(
            timestamp=round(ts, 4), mean_dx=round(float(np.mean(dx)), 4),
            mean_dy=round(float(np.mean(dy)), 4),
            magnitude=round(float(np.mean(mag)), 4),
            std_magnitude=round(float(np.std(mag)), 4),
            flow_coverage=round(float(np.mean(mag > 1.0)), 4))

    def _classify_motion(self, vecs: List[MotionVector]) -> CameraMotion:
        if not vecs:
            return CameraMotion.UNKNOWN
        dxs, dys, mags = [v.mean_dx for v in vecs], [v.mean_dy for v in vecs], \
                         [v.magnitude for v in vecs]
        avg_dx, avg_dy, avg_mag = np.mean(dxs), np.mean(dys), np.mean(mags)
        avg_std = np.mean([v.std_magnitude for v in vecs])

        if avg_mag < 0.5:
            return CameraMotion.STATIC
        if avg_std > avg_mag * 1.5 and avg_mag > 1.0:
            return CameraMotion.HANDHELD
        rx, ry = avg_dx / max(avg_mag, 0.01), avg_dy / max(avg_mag, 0.01)
        if abs(rx) > 0.6:
            return CameraMotion.PAN_LEFT if rx < 0 else CameraMotion.PAN_RIGHT
        if abs(ry) > 0.6:
            return CameraMotion.TILT_UP if ry < 0 else CameraMotion.TILT_DOWN
        cov = np.mean([v.flow_coverage for v in vecs])
        if cov > 0.7 and avg_mag > 2.0:
            pos, neg = sum(1 for d in dxs if d > 0), sum(1 for d in dxs if d < 0)
            if abs(pos - neg) < len(dxs) * 0.2:
                return CameraMotion.ZOOM_IN if avg_mag > np.median(mags) * 1.3 \
                    else CameraMotion.ZOOM_OUT
        con = max(abs(np.mean(np.sign(dxs))), abs(np.mean(np.sign(dys))))
        if con > 0.5 and 0.5 < avg_mag < 5.0:
            return CameraMotion.TRACKING
        return CameraMotion.COMPLEX if avg_mag > 3.0 else CameraMotion.UNKNOWN

    def _segment_motion(self, vecs: List[MotionVector],
                        ts: List[float]) -> List[Dict[str, Any]]:
        if len(vecs) < 3:
            return []
        mags = [v.magnitude for v in vecs]
        med = np.median(mags)
        segs, start, state = [], 0, "low" if mags[0] < med else "high"
        for i in range(1, len(mags)):
            ns = "low" if mags[i] < med else "high"
            if ns != state:
                t = CameraMotion.STATIC if state == "low" else CameraMotion.COMPLEX
                segs.append({"start": round(ts[start], 3), "end": round(ts[i-1], 3),
                             "type": t.value,
                             "avg_magnitude": round(float(np.mean(mags[start:i])), 4)})
                start, state = i, ns
        t = CameraMotion.STATIC if state == "low" else CameraMotion.COMPLEX
        segs.append({"start": round(ts[start], 3), "end": round(ts[-1], 3),
                     "type": t.value,
                     "avg_magnitude": round(float(np.mean(mags[start:])), 4)})
        return segs

    def _detect_shake_segs(self, vecs: List[MotionVector],
                           ts: List[float]) -> List[Dict]:
        if len(vecs) < 5:
            return []
        stds = [v.std_magnitude for v in vecs]
        thr = np.mean(stds) + 2 * np.std(stds)
        segs, in_s, s0 = [], False, 0
        for i, s in enumerate(stds):
            if s > thr and not in_s:
                in_s, s0 = True, i
            elif s <= thr and in_s:
                in_s = False
                segs.append({"start": round(ts[s0], 3), "end": round(ts[i-1], 3),
                             "avg_std": round(float(np.mean(stds[s0:i])), 4)})
        if in_s:
            segs.append({"start": round(ts[s0], 3), "end": round(ts[-1], 3),
                         "avg_std": round(float(np.mean(stds[s0:])), 4)})
        return segs

    # ── 镜头检测内部 ─────────────────────────────────────────
    @staticmethod
    def _classify_transition(hd: float, pd: float,
                             prev: np.ndarray, curr: np.ndarray) -> TransitionType:
        if pd > 100:
            return TransitionType.FLASH
        # 划变优先：方向性差异
        if pd > 30:
            dm = np.abs(curr.astype(float) - prev.astype(float))
            h, w = dm.shape
            if abs(np.mean(dm[:, :w//2]) - np.mean(dm[:, w//2:])) > 20:
                return TransitionType.WIPE
        if 20 < pd <= 100 and hd > 30:
            return TransitionType.DISSOLVE
        return TransitionType.HARD_CUT

    def _build_shots(self, boundaries, duration) -> List[ShotInfo]:
        shots, prev_t = [], 0.0
        for t, conf, tt in boundaries:
            d = t - prev_t
            if d >= self._min_shot_duration:
                shots.append(ShotInfo(
                    index=len(shots), start_time=round(prev_t, 3),
                    end_time=round(t, 3), duration=round(d, 3),
                    transition=TransitionType(tt) if tt in [e.value for e in TransitionType]
                    else TransitionType.HARD_CUT, confidence=round(conf, 3)))
            prev_t = t
        if duration - prev_t >= self._min_shot_duration:
            shots.append(ShotInfo(
                index=len(shots), start_time=round(prev_t, 3),
                end_time=round(duration, 3), duration=round(duration - prev_t, 3)))
        for i, s in enumerate(shots):
            s.index = i
        return shots

    @staticmethod
    def _classify_rhythm(durs: List[float]) -> str:
        if len(durs) < 3:
            return "uniform"
        mid = len(durs) // 2
        r = np.mean(durs[mid:]) / max(np.mean(durs[:mid]), 0.001)
        if r < 0.7:
            return "accelerating"
        if r > 1.4:
            return "decelerating"
        return "uniform" if np.std(durs) / max(np.mean(durs), 0.001) < 0.3 else "irregular"

    # ── 叙事弧线内部 ─────────────────────────────────────────
    def _segment_narrative(self, shots: List[ShotInfo],
                           motion: Optional[MotionProfile]) -> List[ArcSegment]:
        energies = []
        for s in shots:
            e = 1.0 / max(s.duration, 0.1)
            if motion and motion.motion_curve:
                ci = min(int((s.start_time + s.end_time) / 2 / motion.duration
                             * len(motion.motion_curve)),
                         len(motion.motion_curve) - 1)
                e += motion.motion_curve[ci] * 0.5
            energies.append(e)
        mx = max(energies) or 1.0
        energies = [e / mx for e in energies]

        segs: List[ArcSegment] = []
        s0, ct = 0, self._energy_type(energies[0], 0)
        _LABELS = {ArcSegmentType.INTRO: "开场引入", ArcSegmentType.BUILDUP: "情绪积累",
                   ArcSegmentType.CLIMAX: "高潮段落", ArcSegmentType.RELEASE: "情绪释放",
                   ArcSegmentType.BREATH: "呼吸过渡", ArcSegmentType.OUTRO: "收尾段落",
                   ArcSegmentType.UNKNOWN: "未分类段落"}

        def _mk(si, ei, stype):
            ss = shots[si:ei]
            dur = ss[-1].end_time - ss[0].start_time
            lbl = _LABELS.get(stype, "未知段落")
            return ArcSegment(
                index=len(segs), segment_type=stype,
                start_time=round(ss[0].start_time, 3),
                end_time=round(ss[-1].end_time, 3),
                duration=round(dur, 3),
                energy=round(float(np.mean(energies[si:ei])), 3),
                avg_shot_duration=round(float(np.mean([s.duration for s in ss])), 3),
                avg_motion=round(float(np.mean(energies[si:ei])), 3),
                shot_count=len(ss), description=f"{lbl}（{len(ss)} 个镜头）")

        for i in range(1, len(energies)):
            nt = self._energy_type(energies[i], i / len(energies))
            if nt != ct and i - s0 >= 2:
                segs.append(_mk(s0, i, ct))
                s0, ct = i, nt
        segs.append(_mk(s0, len(shots), ct))

        # 合并过短同类型段
        if len(segs) > 1:
            merged = [segs[0]]
            for seg in segs[1:]:
                p = merged[-1]
                if seg.duration < 1.0 and seg.segment_type == p.segment_type:
                    p.end_time, p.duration = seg.end_time, seg.end_time - p.start_time
                    p.shot_count += seg.shot_count
                    lbl = _LABELS.get(p.segment_type, "未知段落")
                    p.description = f"{lbl}（{p.shot_count} 个镜头）"
                else:
                    merged.append(seg)
            segs = merged
        return segs

    def _merge_short_segments(self, segments: List[ArcSegment]) -> List[ArcSegment]:
        """合并过短同类型相邻段"""
        if len(segments) <= 1:
            return segments
        _L = {ArcSegmentType.INTRO: "开场引入", ArcSegmentType.BUILDUP: "情绪积累",
              ArcSegmentType.CLIMAX: "高潮段落", ArcSegmentType.RELEASE: "情绪释放",
              ArcSegmentType.BREATH: "呼吸过渡", ArcSegmentType.OUTRO: "收尾段落",
              ArcSegmentType.UNKNOWN: "未知段落"}
        merged = [segments[0]]
        for seg in segments[1:]:
            p = merged[-1]
            if seg.duration < 1.0 and seg.segment_type == p.segment_type:
                p.end_time, p.duration = seg.end_time, seg.end_time - p.start_time
                p.shot_count += seg.shot_count
                p.description = f"{_L.get(p.segment_type, '未知段落')}（{p.shot_count} 个镜头）"
            else:
                merged.append(seg)
        return merged

    @staticmethod
    def _energy_type(energy: float, pos: float) -> ArcSegmentType:
        if pos < 0.1: return ArcSegmentType.INTRO
        if pos > 0.9: return ArcSegmentType.OUTRO
        if energy > 0.75: return ArcSegmentType.CLIMAX
        if energy > 0.5: return ArcSegmentType.BUILDUP
        if energy < 0.2: return ArcSegmentType.BREATH
        return ArcSegmentType.RELEASE

    @staticmethod
    def _infer_shape(energies: List[float]) -> str:
        if len(energies) < 3:
            return "flat"
        n3 = len(energies) // 3
        f, m, l = np.mean(energies[:n3]), np.mean(energies[n3:2*n3]), np.mean(energies[2*n3:])
        if m > f and m > l: return "peak"
        if m < f and m < l: return "valley"
        if l > f: return "rising"
        if l < f: return "falling"
        if abs(f - l) < 0.1 and abs(m - f) > 0.15: return "wave"
        return "flat"

    @staticmethod
    def _build_summary(segs: List[ArcSegment], shape: str) -> str:
        if not segs:
            return "无有效段落"
        labels = {"peak": "山峰形（中间高潮）", "valley": "山谷形（中间平缓）",
                  "rising": "上升形（渐入高潮）", "falling": "下降形（渐弱收尾）",
                  "wave": "波动形（多次起伏）", "flat": "平坦形（能量均匀）",
                  "unknown": "未知形状"}
        desc = labels.get(shape, shape)
        parts = " → ".join(f"{s.segment_type.value}({s.duration:.1f}s)" for s in segs)
        return f"{desc}，共 {len(segs)} 段：" + parts

    @staticmethod
    def _downsample(values: List[float], n: int = 20) -> List[float]:
        if len(values) <= n:
            return values
        chunk = len(values) / n
        return [float(np.mean(values[int(i*chunk):int((i+1)*chunk)])) for i in range(n)]

    # ── RAFT GPU 光流 ──────────────────────────────────────────
    def _analyze_motion_raft(self, video_path: str) -> MotionProfile:
        """RAFT 大模型 GPU 光流 → 运镜分类（精度远高于 Farneback）"""
        import cv2, torch
        from PIL import Image
        from torchvision.models.optical_flow import raft_large, Raft_Large_Weights
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = raft_large(weights=Raft_Large_Weights.DEFAULT, progress=False)
        model = model.to(device).eval()
        transforms = Raft_Large_Weights.DEFAULT.transforms()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return MotionProfile(video_path=video_path, duration=0, fps=0, total_frames=0)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        step = max(1, int(fps / self._sample_fps))
        prev_pil, vectors, timestamps = None, [], []
        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret: break
            pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            if prev_pil is not None:
                with torch.no_grad():
                    img1, img2 = transforms(prev_pil, pil)
                    img1 = img1.unsqueeze(0).to(device)
                    img2 = img2.unsqueeze(0).to(device)
                    flow = model(img1, img2)[-1][0]
                f = flow.cpu().numpy().transpose(1, 2, 0)
                f[:, :, 0] *= w / f.shape[1]
                f[:, :, 1] *= h / f.shape[0]
                vectors.append(self._extract_mv(f, i / fps))
                timestamps.append(i / fps)
            prev_pil = pil
        cap.release()
        if not vectors:
            return MotionProfile(video_path=video_path, duration=duration,
                                 fps=fps, total_frames=total_frames)
        mags = [v.magnitude for v in vectors]
        avg_mag, max_mag = float(np.mean(mags)), float(np.max(mags))
        shake = min(1.0, float(np.std(mags)) / max(avg_mag, 0.01) / 3.0)
        return MotionProfile(
            video_path=video_path, duration=duration, fps=fps,
            total_frames=total_frames,
            avg_magnitude=round(avg_mag, 4), max_magnitude=round(max_mag, 4),
            motion_variance=round(float(np.var(mags)), 4),
            dominant_motion=self._classify_motion(vectors),
            motion_segments=self._segment_motion(vectors, timestamps),
            shake_score=round(shake, 4),
            shake_segments=self._detect_shake_segs(vectors, timestamps),
            motion_curve=[round(v, 4) for v in self._downsample(mags)])

    # ── TransNetV2 镜头检测 ────────────────────────────────────
    def _detect_shot_structure_transnet(self, video_path: str) -> ShotStructure:
        """TransNetV2 神经网络镜头检测（精度远高于直方图差异）"""
        from transnetv2_pytorch import TransNetV2
        import cv2
        device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
        model = TransNetV2(device=device)
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        cap.release()
        frames, single_pred, _ = model.predict_video(video_path)
        pred_np = np.asarray(single_pred.cpu() if hasattr(single_pred, 'cpu') else single_pred)
        # 阈值 0.3 (而非 TransNetV2 默认 0.5): 短视频硬切/闪帧召回不足
        # (AutoShot 基准 TransNetV2 recall 仅 0.716@0.5, 最佳阈值 0.296; 与本项目
        #  ae/ai_scene_detector.py 的 confidence_threshold=0.3 保持一致)
        scenes = model.predictions_to_scenes(pred_np, threshold=0.3)
        boundaries = []
        for idx in range(1, len(scenes)):
            bf = int(scenes[idx, 0])
            t = bf / fps
            prev_frame = np.asarray(frames[bf - 1].cpu() if hasattr(frames[bf - 1], 'cpu') else frames[bf - 1])
            curr_frame = np.asarray(frames[min(bf, len(frames)-1)].cpu() if hasattr(frames[min(bf, len(frames)-1)], 'cpu') else frames[min(bf, len(frames)-1)])
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_RGB2GRAY)
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_RGB2GRAY)
            hd = float(cv2.compareHist(
                cv2.normalize(cv2.calcHist([prev_gray], [0], None, [64], [0, 256]), None).flatten(),
                cv2.normalize(cv2.calcHist([curr_gray], [0], None, [64], [0, 256]), None).flatten(),
                cv2.HISTCMP_CHISQR))
            pd = float(np.mean(np.abs(curr_gray.astype(float) - prev_gray.astype(float))))
            tt = self._classify_transition(hd, pd, prev_gray, curr_gray)
            boundaries.append((t, min(hd / 100.0, 1.0), tt))
        shots = self._build_shots(boundaries, duration)
        durs = [s.duration for s in shots]
        asl = float(np.mean(durs)) if durs else duration
        dist: Dict[str, int] = {}
        for s in shots:
            dist[s.transition.value] = dist.get(s.transition.value, 0) + 1
        return ShotStructure(
            video_path=video_path, total_duration=duration,
            total_shots=len(shots), shots=shots,
            asl=round(asl, 3), cut_rate=round(len(shots) / max(duration, 0.001), 3),
            shot_duration_std=round(float(np.std(durs)), 3) if len(durs) > 1 else 0.0,
            transition_distribution=dist,
            rhythm_pattern=self._classify_rhythm(durs))
