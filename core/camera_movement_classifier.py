"""core/camera_movement_classifier.py - 运镜分类器 (T3 策略3)

零训练数据, 通过 Lucas-Kanade 稀疏光流跟踪, 对任意视频打运镜标签。
输出词汇与 ai/taste_contract.py 运镜池完全对齐。

方向约定 (关键! 与 vlm_annotate_camera.py 提示词及物理语义一致, 2026-08-15 修订):
  特征向右移动 (dx > 0) → 相机向左 → pan_left
  特征向左移动 (dx < 0) → 相机向右 → pan_right
  特征从中心向外扩散/画面放大 (radial > 0) → zoom_in (推近变焦)
  特征从外向中心收缩/画面缩小 (radial < 0) → zoom_out (拉远变焦)

  修订记录 (2026-08-15 复核队列 74 条分析):
  - 原约定 zoom 方向与 VLM 提示词/物理语义相反 (VLM: 放大→zoom_in),
    已翻转; 同步更新 tests/test_camera_classifier.py 合成 fixture。
  - LK 金字塔 maxLevel=4 在低纹理动漫帧上锁错周期性纹理, 产生
    -100px 级虚假位移 (相位相关/稠密光流对照验证), 参数收紧。

用法:
  from core.camera_movement_classifier import classify_video, batch_classify
  result = classify_video("素材.mp4")
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

CAMERA_LABELS: list[str] = [
    "static", "pan_left", "pan_right", "zoom_in", "zoom_out",
    "tilt_up", "tilt_down", "zoom_back", "diag_pan", "orbit",
    "push", "complex", "unknown",
]

# ── 参数 ─────────────────────────────────────────────────────────────
# 2026-08-15 调优依据 (见 docs/camera_classifier_precision_report.md):
#   LK 参数: 旧 (15,15)/maxLevel4 在动漫低纹理帧的金字塔粗层锁错周期性
#   纹理, 静态镜头实测产生 -100px/帧虚假位移; (31,31)/maxLevel3 与
#   相位相关/稠密光流一致 (scripts/lk_forensics.py)。
#   阈值: 网格搜索于 544 条 VLM 高置信分层抽样, 目标 VLM 置信加权精确
#   一致率 (scripts/tune_camera_thresholds.py, 加权一致 20.0%/族 32.8%,
#   旧阈值加权一致 ~19%, 见 models/output/camera_thresholds_tuned.json)。
_RESIZE_W = 320
_RESIZE_H = 240
_SAMPLE_FPS = 10
_MAX_FRAMES = 50
_MAX_TRACK_POINTS = 200
_LK_WIN_SIZE = (31, 31)          # 旧 (15,15): 大窗对低纹理更稳
_LK_MAX_LEVEL = 3                # 旧 4: 金字塔粗层(20x15)锁错纹理
_CUT_GUARD = 60.0                # 帧间平均灰度差 >60 → 判定为转场/闪光, 跳过该步
_MAX_STEP_DISP = 40.0            # 单步位移裁剪上限 (px), 抑制野值跟踪
_STATIC_DISP = 0.5               # 旧 1.0
_PAN_CONSISTENCY = 0.40          # 旧 0.55
_ZOOM_CONSISTENCY = 0.35         # 旧 0.40
_ZOOM_MIN_RADIAL = 0.2
_TILT_CONSISTENCY = 0.40         # 旧 0.50
_ENTROPY_COMPLEX = 0.80          # 旧 0.75
_FALLBACK_CONF = 0.10            # 旧 0.15


def _track_and_analyze(frames: list[np.ndarray]) -> dict[str, float]:
    """LK 稀疏光流跟踪 + 运动模式分析。支持特征点重检测。"""
    if len(frames) < 3:
        return _empty_stats()

    grays = []
    for f in frames:
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) if len(f.shape) == 3 else f
        g = cv2.resize(g, (_RESIZE_W, _RESIZE_H), interpolation=cv2.INTER_AREA)
        grays.append(g)

    h, w = _RESIZE_H, _RESIZE_W
    cx, cy = w / 2.0, h / 2.0
    feat_params = dict(maxCorners=_MAX_TRACK_POINTS, qualityLevel=0.01,
                       minDistance=7, blockSize=7)

    all_dx: list[float] = []
    all_dy: list[float] = []
    all_pos_x: list[float] = []
    all_pos_y: list[float] = []

    prev_gray = grays[0]
    p0 = cv2.goodFeaturesToTrack(prev_gray, mask=None, **feat_params)
    if p0 is None or len(p0) < 10:
        return _empty_stats()
    prev_pts = p0.reshape(-1, 1, 2).astype(np.float32)

    for i in range(1, len(grays)):
        next_gray = grays[i]
        # 转场/闪光守卫: 帧对内容巨变时 LK 匹配无意义且会锁错纹理
        # (实测静态镜头的硬切帧对产生 -100px 级虚假位移)
        frame_diff = float(np.mean(np.abs(
            next_gray.astype(np.int32) - prev_gray.astype(np.int32))))
        if frame_diff > _CUT_GUARD:
            prev_gray = next_gray
            new_pts = cv2.goodFeaturesToTrack(next_gray, mask=None, **feat_params)
            if new_pts is not None and len(new_pts) >= 10:
                prev_pts = new_pts.reshape(-1, 1, 2).astype(np.float32)
            continue

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, next_gray, prev_pts, None,
            winSize=_LK_WIN_SIZE, maxLevel=_LK_MAX_LEVEL,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
        )
        if next_pts is None:
            break

        good_mask = status.flatten() == 1
        n_good = int(good_mask.sum())

        if n_good < 5:
            new_pts = cv2.goodFeaturesToTrack(next_gray, mask=None, **feat_params)
            if new_pts is not None and len(new_pts) >= 10:
                prev_pts = new_pts.reshape(-1, 1, 2).astype(np.float32)
                prev_gray = next_gray
                continue
            break

        p0g = prev_pts[good_mask].reshape(-1, 2)
        p1g = next_pts[good_mask].reshape(-1, 2)
        dx = p1g[:, 0] - p0g[:, 0]
        dy = p1g[:, 1] - p0g[:, 1]
        # 野值裁剪: 12fps 采样下单步 >40px 几乎必为错误匹配 (跟踪锁错纹理)
        np.clip(dx, -_MAX_STEP_DISP, _MAX_STEP_DISP, out=dx)
        np.clip(dy, -_MAX_STEP_DISP, _MAX_STEP_DISP, out=dy)

        all_dx.extend(dx.tolist())
        all_dy.extend(dy.tolist())
        all_pos_x.extend(p0g[:, 0].tolist())
        all_pos_y.extend(p0g[:, 1].tolist())

        prev_gray = next_gray
        if n_good < _MAX_TRACK_POINTS // 2:
            mask = np.ones((h, w), dtype=np.uint8) * 255
            for pt in p1g:
                cv2.circle(mask, (int(pt[0]), int(pt[1])), 15, 0, -1)
            extra = cv2.goodFeaturesToTrack(next_gray, mask=mask, **feat_params)
            if extra is not None and len(extra) > 0:
                prev_pts = np.vstack([
                    p1g.reshape(-1, 1, 2).astype(np.float32),
                    extra.reshape(-1, 1, 2).astype(np.float32),
                ])
            else:
                prev_pts = p1g.reshape(-1, 1, 2).astype(np.float32)
        else:
            prev_pts = next_pts[good_mask].reshape(-1, 1, 2).astype(np.float32)

    if len(all_dx) < 10:
        return _empty_stats()

    dx_arr = np.array(all_dx)
    dy_arr = np.array(all_dy)
    px_arr = np.array(all_pos_x)
    py_arr = np.array(all_pos_y)

    mean_dx = float(np.mean(dx_arr))
    mean_dy = float(np.mean(dy_arr))
    total_disp = float(np.sqrt(mean_dx ** 2 + mean_dy ** 2))

    mean_abs_dx = float(np.mean(np.abs(dx_arr)))
    mean_abs_dy = float(np.mean(np.abs(dy_arr)))
    h_con = abs(mean_dx) / mean_abs_dx if mean_abs_dx > 0.1 else 0.0
    v_con = abs(mean_dy) / mean_abs_dy if mean_abs_dy > 0.1 else 0.0

    # 径向分析
    rel_x = px_arr - cx
    rel_y = py_arr - cy
    rel_mag = np.sqrt(rel_x ** 2 + rel_y ** 2)
    rel_mag[rel_mag < 1.0] = 1.0
    radial_disp = (dx_arr * rel_x + dy_arr * rel_y) / rel_mag
    mean_radial = float(np.mean(radial_disp))
    mean_abs_radial = float(np.mean(np.abs(radial_disp)))
    radial_con = abs(mean_radial) / mean_abs_radial if mean_abs_radial > 0.1 else 0.0

    # 方向熵
    angles = np.arctan2(dy_arr, dx_arr)
    n_bins = 8
    counts = np.zeros(n_bins)
    bins = np.clip(((angles + np.pi) / (2 * np.pi) * n_bins).astype(int), 0, n_bins - 1)
    for b in bins:
        counts[b] += 1
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    entropy = float(-np.sum(probs * np.log(probs)) / np.log(n_bins)) if len(probs) > 1 else 0.0

    return {
        "mean_dx": round(mean_dx, 4), "mean_dy": round(mean_dy, 4),
        "mean_radial": round(mean_radial, 4),
        "h_consistency": round(min(h_con, 1.0), 4),
        "v_consistency": round(min(v_con, 1.0), 4),
        "radial_consistency": round(min(radial_con, 1.0), 4),
        "total_disp": round(total_disp, 4),
        "direction_entropy": round(entropy, 4),
    }


def _empty_stats() -> dict[str, float]:
    return {
        "mean_dx": 0.0, "mean_dy": 0.0, "mean_radial": 0.0,
        "h_consistency": 0.0, "v_consistency": 0.0,
        "radial_consistency": 0.0, "total_disp": 0.0,
        "direction_entropy": 0.0,
    }


def _classify_from_stats(stats: dict[str, float]) -> tuple[str, float]:
    """从跟踪统计判定运镜类型。

    检测顺序 (关键!):
      1. zoom  → 径向一致性高 + 幅度大 (zoom 的 total_disp 天然很小,
         因为对称运动在 mean_dx/mean_dy 上抵消, 必须先于 static 检测)
      2. static → 无 zoom 且位移极小
      3. pan   → 水平一致性主导
      4. tilt  → 垂直一致性主导
      5. complex → 水平+径向同时强, 或高熵
      6. 兜底   → 取最强信号

    方向约定 (2026-08-15 修订, 与 VLM 提示词一致):
      radial > 0 (画面向外扩散/放大) → zoom_in
      radial < 0 (画面向中心收缩/缩小) → zoom_out
    """
    disp = stats["total_disp"]
    h_con = stats["h_consistency"]
    v_con = stats["v_consistency"]
    rad_con = stats["radial_consistency"]
    mean_rad = stats["mean_radial"]
    dx = stats["mean_dx"]
    dy = stats["mean_dy"]
    entropy = stats["direction_entropy"]

    # 1) 先查 zoom: zoom 的 total_disp 天然很小 (对称运动抵消),
    #    必须在 static 阈值之前检测
    if rad_con > _ZOOM_CONSISTENCY and abs(mean_rad) > _ZOOM_MIN_RADIAL:
        if rad_con >= h_con and rad_con >= v_con:
            label = "zoom_in" if mean_rad > 0 else "zoom_out"
            return label, round(min(rad_con, 1.0), 3)

    # 2) static: 无 zoom 且位移极小
    if disp < _STATIC_DISP:
        return "static", round(max(0.0, 1.0 - disp / _STATIC_DISP), 3)

    # 3) pan: 水平一致主导
    if h_con > _PAN_CONSISTENCY and h_con > v_con:
        label = "pan_left" if dx > 0 else "pan_right"
        return label, round(min(h_con, 1.0), 3)

    # 4) tilt: 垂直一致主导
    if v_con > _TILT_CONSISTENCY and v_con > h_con:
        label = "tilt_up" if dy > 0 else "tilt_down"
        return label, round(min(v_con, 1.0), 3)

    # 5) 水平+径向同时强 → 复合运动
    if h_con > _PAN_CONSISTENCY and rad_con > _ZOOM_CONSISTENCY:
        return "complex", round(min(max(h_con, rad_con), 1.0), 3)

    # 6) 高熵 → 复杂运动
    if entropy > _ENTROPY_COMPLEX:
        return "complex", round(min(entropy, 1.0), 3)

    # 7) 兜底: 取最强信号
    signals = {
        "pan_left": h_con if dx > 0 else 0.0,
        "pan_right": h_con if dx < 0 else 0.0,
        "zoom_in": rad_con if mean_rad > 0 else 0.0,
        "zoom_out": rad_con if mean_rad < 0 else 0.0,
        "tilt_up": v_con if dy > 0 else 0.0,
        "tilt_down": v_con if dy < 0 else 0.0,
    }
    best = max(signals, key=signals.get)  # type: ignore[arg-type]
    conf = signals[best]
    if conf > _FALLBACK_CONF:
        return best, round(conf, 3)

    return "complex", 0.3


def _sample_frames(cap, idx_start: int, idx_end: int, span_frames: int,
                   max_frames: int, target_fps: float,
                   fps: float) -> list[np.ndarray]:
    """顺序读取 [idx_start, idx_end) 帧并按步长采样缩放 — 两个读帧入口的公共实现。

    顺序 read + 跳帧: 4K 长 GOP 视频上 cap.set 随机 seek 每次都要解
    关键帧链(实测单素材 30s+), 顺序 read 丢弃不要的帧快一个数量级;
    _read_frames_range 因块小才允许起点 seek 一次。
    """
    frame_step = max(1, max(int(fps / target_fps), span_frames // max_frames))
    frames: list[np.ndarray] = []
    idx = idx_start
    keep_counter = frame_step
    while idx < idx_end and len(frames) < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if keep_counter >= frame_step:
            frames.append(cv2.resize(frame, (_RESIZE_W, _RESIZE_H), interpolation=cv2.INTER_AREA))
            keep_counter = 0
        keep_counter += 1
        idx += 1
    return frames


def _read_frames(video_path: str, max_frames: int = _MAX_FRAMES,
                 target_fps: float = _SAMPLE_FPS) -> list[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < 3:
        cap.release()
        return []
    try:
        return _sample_frames(cap, 0, total, total, max_frames, target_fps, fps)
    finally:
        cap.release()


def classify_segment(frames: list[np.ndarray]) -> dict[str, Any]:
    if len(frames) < 3:
        return {"label": "unknown", "confidence": 0.0, "flow_stats": _empty_stats()}
    stats = _track_and_analyze(frames)
    label, conf = _classify_from_stats(stats)
    return {"label": label, "confidence": conf, "flow_stats": stats}


def _aggregate_votes(per_segment: list[dict[str, Any]],
                     global_stats: dict[str, Any]) -> tuple[str, float]:
    """段落投票聚合 — classify_video 与 classify_video_cached 的唯一实现。

    平局守卫 (2026-08-15): 3 段投票 1/1/1 时 Counter.most_common 取首段,
    复核队列 74 条中 18 条平局, 标签近似随机。平局 → 用全局统计判定,
    置信度封顶 0.5 (复核队列分析结论)。
    """
    votes = Counter(s["label"] for s in per_segment)
    dominant, vc = votes.most_common(1)[0]
    tie = (len(votes) > 1 and vc == votes.most_common(2)[1][1])
    if tie:
        g_label, g_conf = _classify_from_stats(global_stats)
        avg_conf = np.mean([s["confidence"] for s in per_segment
                            if s["label"] == g_label] or [g_conf])
        final_conf = min(0.4 * (vc / len(per_segment)) + 0.4 * g_conf + 0.2 * avg_conf, 0.5)
        return g_label, final_conf
    avg_conf = np.mean([s["confidence"] for s in per_segment if s["label"] == dominant])
    final_conf = 0.6 * (vc / len(per_segment)) + 0.4 * avg_conf
    return dominant, final_conf


def classify_video(video_path: str, n_segments: int = 3) -> dict[str, Any]:
    path = Path(video_path)
    if not path.exists():
        return {"dominant": "unknown", "confidence": 0.0,
                "flow_stats": _empty_stats(), "per_segment": []}
    frames = _read_frames(video_path)
    if len(frames) < 3:
        return {"dominant": "unknown", "confidence": 0.0,
                "flow_stats": _empty_stats(), "per_segment": []}

    seg_len = len(frames) // max(n_segments, 1)
    segs = [frames[i * seg_len:(i + 1) * seg_len] for i in range(n_segments)] if seg_len >= 3 else [frames]
    per_segment = [classify_segment(s) for s in segs]
    global_stats = _track_and_analyze(frames)

    dominant, final_conf = _aggregate_votes(per_segment, global_stats)
    return {
        "dominant": dominant,
        "confidence": round(float(np.clip(final_conf, 0, 1)), 3),
        "flow_stats": global_stats,
        "per_segment": per_segment,
    }


def _read_frames_range(video_path: str, start_sec: float, end_sec: float,
                       max_frames: int = _MAX_FRAMES,
                       target_fps: float = _SAMPLE_FPS) -> list[np.ndarray]:
    """读时间范围内的帧 (块级读帧, 供分段缓存使用)。

    与 _read_frames 相同采样策略; seek 到范围起点后顺序读 (块小, seek 成本可控)。
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total < 3:
        cap.release()
        return []
    start_frame = max(0, int(start_sec * fps))
    end_frame = min(int(end_sec * fps), total)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    try:
        return _sample_frames(cap, start_frame, end_frame,
                              end_frame - start_frame, max_frames, target_fps, fps)
    finally:
        cap.release()


# 块级缓存条目结构版本 — 变更 entry 字段/算法时递增, 旧缓存自动失效
_BLOCK_CACHE_SCHEMA = 1


def classify_video_cached(video_path: str, seg_sec: float = 5.0) -> dict[str, Any]:
    """分段缓存版运镜分类 — 素材裁切后未变时间段复用 (2026-08-14)。

    块划分/指纹与 core.temporal_segment_cache 完全一致 (同一视频同样切块),
    块级 LK 光流结果存独立块池 cache/camera_segments/blocks/{fp}.pkl,
    裁切产物的未变块跨文件命中。

    聚合: 每块一票 (比整文件 3 等分投票更细粒度), confidence 公式与原版一致。
    """
    import hashlib
    import os
    import pickle as _pickle

    path = Path(video_path)
    if not path.exists():
        return {"dominant": "unknown", "confidence": 0.0,
                "flow_stats": _empty_stats(), "per_segment": []}

    try:
        from core.temporal_segment_cache import _scan_segments
        segments, fps, duration, total_frames = _scan_segments(video_path)
    except Exception as e:
        logger.warning("指纹扫描失败, 降级整文件分类: %s", e)
        return classify_video(video_path)

    # 独立块池 (内容结构与 temporal 不同)
    _cache_root = Path(__file__).resolve().parent.parent / "cache" / "camera_segments" / "blocks"
    os.makedirs(_cache_root, exist_ok=True)

    per_segment: list[dict[str, Any]] = []
    hit_blocks = 0
    for seg in segments:
        fp = seg["fp"]
        # 指纹 16 位 (旧 10 位在大素材库下有碰撞风险); 缓存条目带 schema 版本,
        # 旧条目/结构变更自动视为 miss 重算
        bfile = _cache_root / f"{fp[:16]}.pkl"
        entry = None
        if bfile.exists():
            try:
                with open(bfile, "rb") as _f:
                    entry = _pickle.load(_f)
                if not isinstance(entry, dict) or entry.get("_v") != _BLOCK_CACHE_SCHEMA:
                    entry = None
                else:
                    hit_blocks += 1
            except (OSError, _pickle.PickleError, EOFError):
                entry = None
        if entry is None:
            frames = _read_frames_range(
                video_path, seg["start"], seg["end"],
                max_frames=_MAX_FRAMES, target_fps=_SAMPLE_FPS)
            seg_result = classify_segment(frames)
            entry = {"_v": _BLOCK_CACHE_SCHEMA,
                     "label": seg_result["label"],
                     "confidence": seg_result["confidence"],
                     "flow_stats": seg_result["flow_stats"],
                     "start": seg["start"], "end": seg["end"], "fp": fp}
            try:
                with open(bfile, "wb") as _f:
                    _pickle.dump(entry, _f)
            except OSError:
                pass
        per_segment.append({"label": entry["label"],
                            "confidence": entry["confidence"],
                            "flow_stats": entry["flow_stats"]})

    if not per_segment:
        return {"dominant": "unknown", "confidence": 0.0,
                "flow_stats": _empty_stats(), "per_segment": []}

    # 全局 flow_stats: 各块统计的算术平均 (近似全帧统计, 可观测性用途)
    stat_keys = [k for k in per_segment[0]["flow_stats"]]
    global_stats: dict[str, float] = {}
    for k in stat_keys:
        vals = [s["flow_stats"].get(k, 0.0) for s in per_segment]
        global_stats[k] = round(float(np.mean(vals)), 4)

    # 投票聚合与 classify_video 同一实现 (含平局守卫, 置信封顶 0.5)
    dominant, final_conf = _aggregate_votes(per_segment, global_stats)

    if len(segments) > 1:
        logger.info("[CameraSegCache] %s: %d/%d blocks hit",
                    path.name, hit_blocks, len(segments))

    return {
        "dominant": dominant,
        "confidence": round(float(np.clip(final_conf, 0, 1)), 3),
        "flow_stats": global_stats,
        "per_segment": per_segment,
    }


def batch_classify(video_paths: Sequence[str]) -> list[dict[str, Any]]:
    results = []
    for vp in video_paths:
        r = classify_video(vp)
        r["video_path"] = vp
        results.append(r)
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: py -3.12 core/camera_movement_classifier.py <video> [...]")
        sys.exit(1)
    for vp in sys.argv[1:]:
        r = classify_video(vp)
        fs = r["flow_stats"]
        print(f"{vp}: {r['dominant']} (conf={r['confidence']:.2f}) "
              f"dx={fs['mean_dx']:.1f} dy={fs['mean_dy']:.1f} "
              f"rad={fs['mean_radial']:.1f} disp={fs['total_disp']:.1f}")
