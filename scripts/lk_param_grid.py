#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lk_param_grid.py — LK 参数网格 × 稳健统计 筛选

基准: 稠密 Farneback 的全局 (mean_dx, mean_dy) 作为方向参照 (与相位相关
一致, 已在 forensics 验证)。对 40 个真实片段, 比较各参数组合下稀疏 LK
的 mean/median dx,dy 与稠密参照的符号一致率、幅值相关性。

候选组合: (winSize, maxLevel) × 统计量(mean/median/trimmed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import _read_frames  # noqa: E402

DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"

COMBOS = [
    ((15, 15), 4),   # 现状
    ((15, 15), 0),
    ((15, 15), 1),
    ((21, 21), 2),
    ((31, 31), 2),
    ((31, 31), 3),
]


def sparse_step(g0: np.ndarray, g1: np.ndarray, win: Tuple[int, int], lv: int,
                pts: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(
        g0, g1, pts, None, winSize=win, maxLevel=lv,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    gm = st.flatten() == 1
    if int(gm.sum()) < 5:
        return np.zeros((0, 2)), np.zeros((0, 2))
    p0 = pts[gm].reshape(-1, 2)
    p1 = nxt[gm].reshape(-1, 2)
    return p1 - p0, p0


def analyze_clip(clip: str, win: Tuple[int, int], lv: int,
                 stats: str) -> Tuple[float, float]:
    frames = _read_frames(clip, max_frames=50, target_fps=10)
    if len(frames) < 3:
        return 0.0, 0.0
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    dxs: List[float] = []
    dys: List[float] = []
    for i in range(1, len(grays)):
        pts = cv2.goodFeaturesToTrack(grays[i - 1], maxCorners=200, qualityLevel=0.01,
                                      minDistance=7, blockSize=7)
        if pts is None or len(pts) < 10:
            continue
        d, p0 = sparse_step(grays[i - 1], grays[i], win, lv, pts)
        if len(d) < 5:
            continue
        dxs.extend(d[:, 0].tolist())
        dys.extend(d[:, 1].tolist())
    if not dxs:
        return 0.0, 0.0
    if stats == "mean":
        return float(np.mean(dxs)), float(np.mean(dys))
    if stats == "median":
        return float(np.median(dxs)), float(np.median(dys))
    # trimmed mean 30%
    dx = np.array(dxs); dy = np.array(dys)
    lo, hi = np.percentile(dx, [15, 85]); m = (dx >= lo) & (dx <= hi)
    return float(np.mean(dx[m])), float(np.mean(dy[m]))
    # unreachable for stats types not listed


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(l) for l in DETAIL.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = np.random.RandomState(7)
    picks = rng.choice(rows, 40, replace=False)
    print(f"抽样 {len(picks)} 片段")

    # 稠密基准
    dense_ref: List[Tuple[float, float]] = []
    clips = []
    for r in picks:
        frames = _read_frames(r["clip_path"], max_frames=50, target_fps=10)
        if len(frames) < 3:
            continue
        g0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        gN = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)
        fl = cv2.calcOpticalFlowFarneback(g0, gN, None, 0.5, 4, 25, 3, 7, 1.5, 0)
        dense_ref.append((float(np.mean(fl[..., 0])), float(np.mean(fl[..., 1]))))
        clips.append(r["clip_path"])
    print(f"有效 {len(clips)}")

    print(f"\n{'组合':<24} {'统计':<8} {'dx符号一致':>10} {'dy符号一致':>10} "
          f"{'方向符号一致(大位移)':>18} {'|dx|相关':>8}")
    for win, lv in COMBOS:
        for stats in ("mean", "median", "trimmed"):
            agree_x = agree_y = agree_big = 0
            corrs = []
            for clip, (rdx, rdy) in zip(clips, dense_ref):
                dx, dy = analyze_clip(clip, win, lv, stats)
                mag = np.hypot(rdx, rdy)
                if mag > 2.0:  # 只统计有实际位移的片段
                    if np.sign(dx) == np.sign(rdx):
                        agree_big += 1
                if np.sign(dx) == np.sign(rdx):
                    agree_x += 1
                if np.sign(dy) == np.sign(rdy):
                    agree_y += 1
            n_big = sum(1 for rdx, rdy in dense_ref if np.hypot(rdx, rdy) > 2.0)
            print(f"win={win} lv={lv:<8} {stats:<8} {agree_x:>9}/{len(clips)} "
                  f"{agree_y:>9}/{len(clips)} {agree_big:>9}/{n_big}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
