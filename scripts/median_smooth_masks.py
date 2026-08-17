"""时域中值滤波 mask 平滑（生产推荐，替代 SG15）
2026-08-14 实测: MED9 J500=2 (<3 达标) 且面积比 1.19 (SG15=2.74 轨迹涂抹)
中值滤波保留真实出现的像素值，不产生 SG 多项式拟合的过冲/斜坡涂抹。

用法:
  py -3.12 scripts/median_smooth_masks.py --maskdir <dir> --outdir <dir> --window 9
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--maskdir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--window", type=int, default=9, help="时域窗口帧数（奇数，默认 9）")
    args = ap.parse_args()

    src = Path(args.maskdir)
    dst = Path(args.outdir)
    masks = {}
    for p in sorted(src.glob("mask_*.png")):
        gi = int(p.stem.split("_")[-1])
        m = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if m is not None:
            masks[gi] = m.astype(np.float32)
    if not masks:
        print("no masks", file=sys.stderr)
        return 1
    gis = sorted(masks)
    stack = np.stack([masks[gi] for gi in gis])
    t0 = time.time()
    half = args.window // 2
    out = np.empty_like(stack)
    T = stack.shape[0]
    for i in range(T):
        lo, hi = max(0, i - half), min(T, i + half + 1)
        out[i] = np.median(stack[lo:hi], axis=0)
    out = out.astype(np.uint8)
    dst.mkdir(parents=True, exist_ok=True)
    for i, gi in enumerate(gis):
        ok, buf = cv2.imencode(".png", out[i])
        buf.tofile(str(dst / f"mask_{gi:05d}.png"))
    print(json.dumps({"ok": True, "frames": len(gis), "window": args.window,
                      "elapsed_s": round(time.time() - t0, 1), "outdir": str(dst)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
