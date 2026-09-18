#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dense_flow_audit.py — 稠密光流 vs 稀疏LK 对照审计

对真实片段: 用稠密 Farneback 光流 (首/末采样帧之间) 计算逐区域运动方向,
与分类器稀疏 LK 的 mean_dx/mean_dy/mean_radial 对照, 检验:
  1. 稀疏 pipeline 是否有系统性符号/幅值偏置
  2. VLM zoom_in/zoom_out 样本的真实径向流方向 (谁的方向约定正确)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import _read_frames  # noqa: E402

DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"
W, H = 320, 240


def dense_flow(clip: str) -> dict[str, float]:
    frames = _read_frames(clip, max_frames=50, target_fps=10)
    if len(frames) < 3:
        return {"n_frames": 0}
    g0 = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
    g1 = cv2.cvtColor(frames[-1], cv2.COLOR_BGR2GRAY)
    flow = cv2.calcOpticalFlowFarneback(g0, g1, None, 0.5, 4, 25, 3, 7, 1.5, 0)
    fx = flow[..., 0].astype(np.float64)
    fy = flow[..., 1].astype(np.float64)
    ys, xs = np.mgrid[0:H, 0:W]
    relx = xs - W / 2.0
    rely = ys - H / 2.0
    mag = np.sqrt(relx ** 2 + rely ** 2)
    mag[mag < 1] = 1
    rad = (fx * relx + fy * rely) / mag
    # 全图 + 3x3 区域
    grid = []
    for gy in range(3):
        for gx in range(3):
            x0, x1 = gx * W // 3, (gx + 1) * W // 3
            y0, y1 = gy * H // 3, (gy + 1) * H // 3
            grid.append((float(np.mean(fx[y0:y1, x0:x1])),
                         float(np.mean(fy[y0:y1, x0:x1]))))
    return {
        "n_frames": len(frames),
        "mean_dx": float(np.mean(fx)), "mean_dy": float(np.mean(fy)),
        "mean_radial": float(np.mean(rad)),
        "grid": grid,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(l) for l in DETAIL.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_label: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_label.setdefault(r["vlm_label"], []).append(r)

    # 每类取 12 条
    picks: list[dict[str, Any]] = []
    for lab in ("zoom_in", "zoom_out", "pan_left", "pan_right", "static"):
        picks.extend(by_label.get(lab, [])[:12])

    print(f"{'shot':<20} {'VLM':<10} | {'sparse dx/dy/rad':>28} | {'dense dx/dy/rad':>28} | 3x3区域符号")
    n = 0
    dense_rad_sign = Counter()
    sparse_rad_sign = Counter()
    for r in picks:
        clip = r["clip_path"]
        d = dense_flow(clip)
        if not d.get("n_frames"):
            continue
        s = r["flow_stats"]
        n += 1
        dense_rad_sign[(r["vlm_label"], ">0" if d["mean_radial"] > 0 else "<0")] += 1
        sparse_rad_sign[(r["vlm_label"], ">0" if s["mean_radial"] > 0 else "<0")] += 1
        grid_s = " ".join(
            f"({'+' if dx > 0 else '-'}{'+' if dy > 0 else '-'})" for dx, dy in d["grid"])
        print(f"{r['shot_id']:<20} {r['vlm_label']:<10} | "
              f"{s['mean_dx']:8.1f}{s['mean_dy']:8.1f}{s['mean_radial']:8.1f} | "
              f"{d['mean_dx']:8.1f}{d['mean_dy']:8.1f}{d['mean_radial']:8.1f} | {grid_s}")

    print(f"\n稀疏 radial 符号 (按VLM标签): {dict(sorted(sparse_rad_sign.items()))}")
    print(f"稠密 radial 符号 (按VLM标签): {dict(sorted(dense_rad_sign.items()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
