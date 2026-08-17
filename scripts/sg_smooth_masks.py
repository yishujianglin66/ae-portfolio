"""M2-B (P3): SG 时域滤波压全链路 J500 — 对 refine 后 mask 沿时间轴 Savitzky-Golay 平滑"""
import sys, time
from pathlib import Path
import numpy as np
import cv2

try:
    from scipy.signal import savgol_filter
except Exception as e:
    print("scipy 不可用:", e, file=sys.stderr)
    sys.exit(2)

SRC = Path("output/step2_locator/m4_full_chain")
DST = Path("output/step2_locator/m4_full_chain_sg")
WINDOW = 5  # 5 帧 SG
POLY = 2

masks = {}
for p in sorted(SRC.glob("mask_*.png")):
    gi = int(p.stem.split("_")[-1])
    img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is not None:
        masks[gi] = img.astype(np.float32)

gis = sorted(masks)
print(f"loaded {len(gis)} masks", file=sys.stderr)
t0 = time.time()
stack = np.stack([masks[gi] for gi in gis])  # (T,H,W)
smoothed = savgol_filter(stack, WINDOW, POLY, axis=0, mode="interp")
smoothed = np.clip(smoothed, 0, 255).astype(np.uint8)
DST.mkdir(parents=True, exist_ok=True)
for i, gi in enumerate(gis):
    ok, buf = cv2.imencode(".png", smoothed[i])
    buf.tofile(str(DST / f"mask_{gi:05d}.png"))
print(f"done {len(gis)} frames in {time.time()-t0:.1f}s -> {DST}", file=sys.stderr)
print("OK")
