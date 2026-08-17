r"""
M2 · Layer2A 光流 warp 时序稳定（独立版, stabilize_temporal.py）
================================================================
原理（方案 §4A）:
  Mask_N_stabilized = w_raw * Mask_N_raw + w_prev * Warp(Mask_{N-1} → N)
  Warp(Mask_{N-1}) 提供"边缘应在哪"的强先验，消除 SAM2 逐帧边缘抖动（F2）。

权重（按运动级别，方案 §4A.3）:
  static (0.5, 0.5) / mid (0.6, 0.4) / fast (0.75, 0.25)
  （fast 更偏本帧，防旧帧拖影）

光流来源: M0 的 flow_cache/{fi:05d}.npy（1/4 分辨率, flow_cache[fi]=flow(fi-1→fi)）
  → 使用前 cv2.resize 放大到 mask 分辨率，并乘以 (1/scale) 还原全分辨率像素位移。

CLI（需 torch+cuda，用 venv-sam2 python）:
  & D:\AE-Work\venv-sam2\Scripts\python.exe scripts/stabilize_temporal.py \
      --maskdir <raw_tier1_masks> --outdir <stabilized_dir> \
      [--levels <motion_levels.json>] [--flowcache <flow_cache_dir>] \
      [--scale 0.25] [--demo] [--device cuda]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "external" / "rife" / "model"))
from warplayer import warp  # noqa: E402

WEIGHTS = {"static": (0.5, 0.5), "mid": (0.6, 0.4), "fast": (0.75, 0.25)}


def imread_unicode(p: str) -> np.ndarray | None:
    if not Path(p).exists():
        return None
    buf = np.fromfile(p, dtype=np.uint8)
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)


def imwrite_unicode(p: str, img: np.ndarray) -> bool:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        return False
    buf.tofile(p)
    return True


def stabilize_frame(mask_raw: np.ndarray, prev_stab: np.ndarray | None,
                    flow_full: np.ndarray, level: str, device: str = "cuda") -> np.ndarray:
    """单帧稳定：warp 上一帧稳定 mask 与当前帧原始 mask 加权融合。"""
    if prev_stab is None:
        return mask_raw
    h, w = mask_raw.shape[:2]
    flow_t = torch.from_numpy(flow_full).permute(2, 0, 1).unsqueeze(0).float().to(device)
    prev_t = torch.from_numpy(prev_stab.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(device)
    with torch.no_grad():
        warped = warp(prev_t, flow_t).squeeze(0).squeeze(0).cpu().numpy()  # float, 0~255
    w_raw, w_prev = WEIGHTS.get(level, (0.6, 0.4))
    fused = np.clip(w_raw * mask_raw.astype(np.float32) + w_prev * warped, 0, 255)
    return fused.astype(np.uint8)


def load_levels(path: str) -> tuple[list[str], str]:
    """返回 (levels, flow_cache_dir)。"""
    with open(path, "r", encoding="utf-8") as f:
        ml = json.load(f)
    lv = ml.get("motion_level") or []
    fcd = ml.get("flow_cache_dir") or ""
    return [str(x) for x in lv], fcd


def load_raw_masks(maskdir: str) -> dict[int, np.ndarray]:
    d = Path(maskdir)
    masks: dict[int, np.ndarray] = {}
    for p in sorted(d.glob("mask_*.png")):
        try:
            gi = int(p.stem.split("_")[-1])
        except Exception:
            continue
        m = imread_unicode(str(p))
        if m is not None:
            masks[gi] = m
    return masks


def main() -> int:
    ap = argparse.ArgumentParser(description="M2 Layer 2A 光流 warp 时序稳定（独立版）")
    ap.add_argument("--maskdir", required=True, help="Tier1 原始 mask 目录（enable_edge_refine=false 输出）")
    ap.add_argument("--outdir", required=True, help="稳定后 mask 输出目录")
    ap.add_argument("--levels", default="", help="motion_levels.json（提供逐帧级别 + flow_cache_dir）")
    ap.add_argument("--flowcache", default="", help="flow_cache 目录（未给 levels 时用）")
    ap.add_argument("--scale", type=float, default=0.25, help="flow_cache 相对全分辨率的缩放（默认 0.25）")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--demo", action="store_true", help="仅处理前 3 帧验证流程")
    args = ap.parse_args()

    levels: list[str] = []
    flow_cache_dir = args.flowcache
    if args.levels and Path(args.levels).exists():
        levels, flow_cache_dir = load_levels(args.levels)

    masks = load_raw_masks(args.maskdir)
    if not masks:
        print("no raw masks found", file=sys.stderr)
        return 1
    gis = sorted(masks)
    if args.demo:
        gis = gis[:3]
    H, W = masks[gis[0]].shape[:2]
    w_s = max(1, int(round(W * args.scale)))
    h_s = max(1, int(round(H * args.scale)))
    print(f"[STAB] {len(gis)} frames {W}x{H}, flow_cache={flow_cache_dir} scale={args.scale}", file=sys.stderr)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    prev_stab: np.ndarray | None = None
    t0 = time.time()
    for gi in gis:
        lv = levels[gi - gis[0]] if gi - gis[0] < len(levels) else "mid"
        if lv == "fast":
            # 快运动/硬切帧不做 warp 融合（切点两侧内容无关，warp 先验失效）；链断裂
            # （M4 实证：fast 大 mask 经 0.5/0.5 融合拖入后续 static 帧 → 软 mask 直入 guided filter 塌缩 → 6 空帧）
            stab = masks[gi]
            prev_stab = None
        else:
            flow_path = Path(flow_cache_dir) / f"{gi - gis[0]:05d}.npy"
            if flow_path.exists():
                flow_small = np.load(str(flow_path))
                flow_full = cv2.resize(flow_small, (W, H), interpolation=cv2.INTER_LINEAR) * (1.0 / args.scale)
            else:
                flow_full = np.zeros((H, W, 2), dtype=np.float32)
            stab = stabilize_frame(masks[gi], prev_stab, flow_full, lv, device=args.device)
            prev_stab = stab
        imwrite_unicode(str(outdir / f"mask_{gi:05d}.png"), stab)
    elapsed = time.time() - t0
    print(f"[STAB] done {len(gis)} frames in {elapsed:.1f}s -> {outdir}", file=sys.stderr)
    print(json.dumps({"ok": True, "frames": len(gis), "elapsed_s": round(elapsed, 2),
                      "outdir": str(outdir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
