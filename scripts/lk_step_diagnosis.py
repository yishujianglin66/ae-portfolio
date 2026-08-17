#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lk_step_diagnosis.py — 极端样本的稀疏LK逐步位移诊断

打印每个采样步的 mean_dx/dy、跟踪点数、重检测事件, 并与
首末帧单对稠密/稀疏位移对照, 定位稀疏管线大位移来源。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import _read_frames, _RESIZE_W, _RESIZE_H  # noqa: E402

DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"
CLIPS = ["BV1GC4y1U79F_108", "BV14t411t7KQ_073", "BV1aD4y1j7E7_076"]


def diagnose(clip: str) -> None:
    frames = _read_frames(clip, max_frames=50, target_fps=10)
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    print(f"\n===== {clip} (采样帧数 {len(grays)}) =====")

    # 首末帧对照
    g0, gN = grays[0], grays[-1]
    dense = cv2.calcOpticalFlowFarneback(g0, gN, None, 0.5, 4, 25, 3, 7, 1.5, 0)
    print(f"首末帧 dense: dx={np.mean(dense[...,0]):+.2f} dy={np.mean(dense[...,1]):+.2f}")

    pts = cv2.goodFeaturesToTrack(g0, maxCorners=200, qualityLevel=0.01,
                                  minDistance=7, blockSize=7)
    if pts is not None:
        nxt, st, _ = cv2.calcOpticalFlowPyrLK(g0, gN, pts, None,
                                              winSize=(15, 15), maxLevel=4,
                                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        good = st.flatten() == 1
        d = nxt[good].reshape(-1, 2) - pts[good].reshape(-1, 2)
        print(f"首末帧 sparse 单对: dx={np.mean(d[:,0]):+.2f} dy={np.mean(d[:,1]):+.2f} "
              f"(n={int(good.sum())})")

    # 逐步追踪 (复刻分类器逻辑)
    prev_gray = grays[0]
    p0 = cv2.goodFeaturesToTrack(prev_gray, mask=None, maxCorners=200,
                                 qualityLevel=0.01, minDistance=7, blockSize=7)
    prev_pts = p0.reshape(-1, 1, 2).astype(np.float32)
    print(f"{'step':>4} {'n_track':>8} {'mean_dx':>8} {'mean_dy':>8} "
          f"{'med_dx':>8} {'med_dy':>8} 重检测")
    for i in range(1, len(grays)):
        next_gray = grays[i]
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, next_gray, prev_pts, None, winSize=(15, 15), maxLevel=4,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        gm = status.flatten() == 1
        n_good = int(gm.sum())
        if n_good < 5:
            print(f"{i:>4} {n_good:>8}  <-- 跟踪丢失, 重检测")
            new_pts = cv2.goodFeaturesToTrack(next_gray, mask=None, maxCorners=200,
                                              qualityLevel=0.01, minDistance=7, blockSize=7)
            if new_pts is not None and len(new_pts) >= 10:
                prev_pts = new_pts.reshape(-1, 1, 2).astype(np.float32)
                prev_gray = next_gray
            continue
        p0g = prev_pts[gm].reshape(-1, 2)
        p1g = nxt[gm].reshape(-1, 2)
        dx = p1g[:, 0] - p0g[:, 0]
        dy = p1g[:, 1] - p0g[:, 1]
        redet = n_good < 100
        print(f"{i:>4} {n_good:>8} {np.mean(dx):+8.2f} {np.mean(dy):+8.2f} "
              f"{np.median(dx):+8.2f} {np.median(dy):+8.2f} "
              f"{'是' if redet else ''}")
        prev_gray = next_gray
        if redet:
            mask = np.ones((_RESIZE_H, _RESIZE_W), dtype=np.uint8) * 255
            for pt in p1g:
                cv2.circle(mask, (int(pt[0]), int(pt[1])), 15, 0, -1)
            extra = cv2.goodFeaturesToTrack(next_gray, mask=mask, maxCorners=200,
                                            qualityLevel=0.01, minDistance=7, blockSize=7)
            if extra is not None and len(extra) > 0:
                prev_pts = np.vstack([p1g.reshape(-1, 1, 2).astype(np.float32),
                                      extra.reshape(-1, 1, 2).astype(np.float32)])
            else:
                prev_pts = p1g.reshape(-1, 1, 2).astype(np.float32)
        else:
            prev_pts = nxt[gm].reshape(-1, 1, 2).astype(np.float32)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = {r["shot_id"]: r for r in
            (json.loads(l) for l in DETAIL.read_text(encoding="utf-8").splitlines() if l.strip())}
    for sid in CLIPS:
        r = rows[sid]
        print(f"VLM={r['vlm_label']}  flow={r['flow_label']} "
              f"sparse_stats: dx={r['flow_stats']['mean_dx']:.1f} "
              f"dy={r['flow_stats']['mean_dy']:.1f} "
              f"rad={r['flow_stats']['mean_radial']:.1f}")
        diagnose(r["clip_path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
