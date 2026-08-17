"""
M0 · Layer 0 运动分级 (motion_classifier.py)
============================================
Farneback 光流 → 每帧运动能量 (pixel/frame 位移中值) → 3 级标签 {static, mid, fast}

方案文档: 09-计划文件/2026-08-13_运动镜头抠像4层提升方案.md §2
CLI:
  py -3.12 scripts/motion_classifier.py --video <path> --start 2000 --frames 500 --outdir <dir>

输出:
  {outdir}/motion_levels.json        分级结果（能量序列 + 标签序列 + 统计 + 元信息）
  {outdir}/flow_cache/{fi:05d}.npy   每帧光流（1/4 分辨率, float32, H×W×2, 段内索引 0..N-1）
                                     flow_cache[fi] = flow(fi-1 → fi)，flow_cache[0] = 0
                                     （Layer 2A 时序稳定 warp 直接复用，不重复计算）

阈值（全分辨率像素位移中值, 可被 QC 回调校准）:
  < 5.0  → static
  5~20.0 → mid
  > 20.0 → fast

场景切换/闪切（PIT-1 补充，QC 2026-08-13 校准）:
  帧间灰度均差 > CUT_FRAME_DIFF(25) → 强制 fast
  —— 快切段绝对不要走 video 传播（SAM2 跨切必崩 area→0%）。
  原始能量在切点会有尖峰，但滑动中值平滑会把它抹掉，所以默认不做平滑
  （与方案 §2.3 逐帧中值口径一致），并用帧差检测兜底。
  校准记录：40 → 25（250-280 区间的 28-35 软切/闪切漏检导致传播崩溃）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# 3 级阈值（全分辨率像素位移中值）
THR_STATIC_MID = 5.0
THR_MID_FAST = 20.0
CUT_FRAME_DIFF = 25.0  # 灰度均差超过此值判定为场景切换/闪切（强制 fast）
                       # QC 校准：40 → 25（250-280 区间的 28-35 软切漏检导致传播崩溃）


def classify(energy: float) -> str:
    if energy < THR_STATIC_MID:
        return "static"
    if energy < THR_MID_FAST:
        return "mid"
    return "fast"


def smooth_median(x: list[float], w: int = 3) -> list[float]:
    """轻量滑动中值平滑（抑制单帧噪声导致的分级抖动，边缘用截断窗口）。"""
    if w <= 1:
        return list(x)
    arr = np.asarray(x, dtype=np.float64)
    n = len(arr)
    out = np.zeros_like(arr)
    half = w // 2
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        out[i] = float(np.median(arr[lo:hi]))
    return out.tolist()


def compute_motion_levels(
    video_path: str,
    start_frame: int,
    expected_frames: int,
    outdir: Path,
    scale: float = 0.25,
    winsize: int = 15,
    levels: int = 3,
    iterations: int = 3,
    poly_n: int = 5,
    poly_sigma: float = 1.2,
    smooth: int = 3,
) -> dict:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    flow_dir = outdir / "flow_cache"
    flow_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    if start_frame > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if total_frames <= 0:
        total_frames = expected_frames

    frames: list[np.ndarray] = []
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        frames.append(frame)
        if expected_frames and len(frames) >= expected_frames:
            break
    cap.release()
    N = len(frames)
    if N == 0:
        raise RuntimeError("no frames read from video segment")
    H, W = frames[0].shape[:2]
    w_s = max(1, int(round(W * scale)))
    h_s = max(1, int(round(H * scale)))
    print(f"[MOTION] read {N} frames {W}x{H}, farneback scale={scale} -> {w_s}x{h_s}", file=sys.stderr)

    motion_energy_raw: list[float] = [0.0] * N
    frame_diff: list[float] = [0.0] * N
    prev_gray = None
    for fi in range(N):
        gray = cv2.cvtColor(frames[fi], cv2.COLOR_BGR2GRAY)
        if fi == 0:
            flow = np.zeros((h_s, w_s, 2), dtype=np.float32)
        else:
            p = cv2.resize(prev_gray, (w_s, h_s))
            c = cv2.resize(gray, (w_s, h_s))
            flow = cv2.calcOpticalFlowFarneback(
                p, c, None,
                pyr_scale=0.5, levels=levels, winsize=winsize,
                iterations=iterations, poly_n=poly_n, poly_sigma=poly_sigma, flags=0,
            )
            mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
            # 小分辨率位移 → 全分辨率像素位移（除以 scale 即放大）
            motion_energy_raw[fi] = float(np.median(mag)) / scale
            # 帧间灰度均差（场景硬切检测，全分辨率）
            frame_diff[fi] = float(np.mean(np.abs(prev_gray.astype(np.int16) - gray.astype(np.int16))))
        np.save(flow_dir / f"{fi:05d}.npy", flow)
        prev_gray = gray

    # 默认不平滑（方案 §2.3 逐帧口径）；smooth>1 时可选轻量中值
    motion_energy = smooth_median(motion_energy_raw, smooth)
    motion_level = [classify(e) for e in motion_energy]
    # 场景硬切兜底：帧差 > 阈值 → 强制 fast（PIT-1: 快切绝不上 video 传播）
    scene_cuts: list[int] = []
    for fi in range(N):
        if frame_diff[fi] > CUT_FRAME_DIFF:
            scene_cuts.append(fi)
            motion_level[fi] = "fast"
    level_counts = {"static": 0, "mid": 0, "fast": 0}
    for lv in motion_level:
        level_counts[lv] += 1

    elapsed = time.time() - t0
    result = {
        "source_video": str(video_path),
        "start_frame": int(start_frame),
        "expected_frames": int(expected_frames),
        "actual_frames": N,
        "total_frames": total_frames,
        "resolution": f"{W}x{H}",
        "motion_energy": motion_energy,
        "motion_level": motion_level,
        "level_counts": level_counts,
        "scene_cuts": scene_cuts,
        "cut_frame_diff_threshold": CUT_FRAME_DIFF,
        "thresholds": {"static_mid": THR_STATIC_MID, "mid_fast": THR_MID_FAST},
        "window_sz_farneback": winsize,
        "scale_factor": scale,
        "smooth_window": smooth,
        "flow_cache_dir": str(flow_dir),
        "flow_cache_index": "segment_local 0..N-1, flow_cache[fi]=flow(fi-1->fi), [0]=zeros",
        "elapsed_s": round(elapsed, 2),
    }
    out_path = outdir / "motion_levels.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[MOTION] level_counts={level_counts}", file=sys.stderr)
    print(f"[MOTION] motion_levels.json -> {out_path}", file=sys.stderr)
    print(f"[MOTION] elapsed={elapsed:.1f}s", file=sys.stderr)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(
        description="M0 Layer 0 运动分级: Farneback 光流 → motion_levels.json + flow_cache/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--video", required=True, help="源视频路径")
    ap.add_argument("--start", type=int, default=0, help="起始全局帧号")
    ap.add_argument("--frames", type=int, default=0, help="段帧数（0=读到结尾）")
    ap.add_argument("--outdir", required=True, help="输出目录（motion_levels.json + flow_cache/）")
    ap.add_argument("--scale", type=float, default=0.25, help="Farneback 计算分辨率缩放（默认 0.25）")
    ap.add_argument("--winsize", type=int, default=15, help="Farneback winsize")
    ap.add_argument("--smooth", type=int, default=1, help="能量滑动中值平滑窗口（默认 1=不平滑，方案 §2.3 口径；>1 可选平滑）")
    args = ap.parse_args()

    res = compute_motion_levels(
        video_path=args.video,
        start_frame=args.start,
        expected_frames=args.frames,
        outdir=Path(args.outdir),
        scale=args.scale,
        winsize=args.winsize,
        smooth=args.smooth,
    )
    print(json.dumps(
        {k: res[k] for k in ("actual_frames", "level_counts", "elapsed_s", "resolution")},
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
