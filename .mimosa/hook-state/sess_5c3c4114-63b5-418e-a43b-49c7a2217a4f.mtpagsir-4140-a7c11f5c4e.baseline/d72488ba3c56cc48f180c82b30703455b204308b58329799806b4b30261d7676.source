#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lk_forensics.py — 相位相关裁决 + LK 参数敏感性

对 BV1aD4y1j7E7_076 (疑似 LK 失效样本) 的帧对做:
  1. cv2.phaseCorrelate 全局位移 (鲁棒基准)
  2. 稠密 Farneback (多参数)
  3. 稀疏 LK (多参数: maxLevel 0/2/3/4, winSize 15/21/31)
判定稀疏 LK 的 -92px 步位移是否为跟踪失效。
"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import _read_frames  # noqa: E402

CLIP = r"D:\AE-Data\AnimeCamera\shots\BV1aD4y1j7E7_076.mp4"


def lk_pair(g0: np.ndarray, g1: np.ndarray, win: tuple, max_level: int,
            max_corners: int = 200) -> str:
    pts = cv2.goodFeaturesToTrack(g0, maxCorners=max_corners, qualityLevel=0.01,
                                  minDistance=7, blockSize=7)
    if pts is None or len(pts) < 5:
        return "无特征点"
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts, None, winSize=win, maxLevel=max_level,
                                          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
    gm = st.flatten() == 1
    d = nxt[gm].reshape(-1, 2) - pts[gm].reshape(-1, 2)
    return (f"n={int(gm.sum()):>3} mean=({np.mean(d[:, 0]):+7.2f},{np.mean(d[:, 1]):+7.2f}) "
            f"med=({np.median(d[:, 0]):+7.2f},{np.median(d[:, 1]):+7.2f})")


def dense_pair(g0: np.ndarray, g1: np.ndarray, tag: str) -> None:
    for pyr in (0.5,):
        for lv in (4, 5):
            fl = cv2.calcOpticalFlowFarneback(g0, g1, None, pyr, lv, 25, 3, 7, 1.5, 0)
            print(f"  dense[{tag}] pyr={pyr} lv={lv}: "
                  f"dx={np.mean(fl[..., 0]):+7.2f} dy={np.mean(fl[..., 1]):+7.2f}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    frames = _read_frames(CLIP, max_frames=50, target_fps=10)
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    print(f"采样帧数: {len(grays)}, 帧索引 (原始): 0..{len(grays)-1}")
    # 帧间灰度差 (检测是否重复帧/闪烁)
    for i in range(1, len(grays)):
        diff = float(np.mean(np.abs(grays[i].astype(int) - grays[i - 1].astype(int))))
        print(f"  帧{i-1}->{i} 平均灰度差: {diff:.2f}")

    pairs = [(0, 1), (0, 2), (0, 3), (1, 2)]
    for a, b in pairs:
        print(f"\n===== 帧对 ({a} -> {b}) =====")
        # 相位相关
        try:
            shift, resp = cv2.phaseCorrelate(
                grays[a].astype(np.float32), grays[b].astype(np.float32))
            print(f"  phaseCorrelate: shift=({shift[0]:+.2f},{shift[1]:+.2f}) "
                  f"resp={resp:.3f}")
        except cv2.error as e:
            print(f"  phaseCorrelate 失败: {e}")
        dense_pair(grays[a], grays[b], f"{a}->{b}")
        for win, lv in [((15, 15), 4), ((15, 15), 0), ((21, 21), 4), ((21, 21), 3),
                        ((31, 31), 3), ((15, 15), 3)]:
            print(f"  LK win={win} lv={lv}: {lk_pair(grays[a], grays[b], win, lv)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
