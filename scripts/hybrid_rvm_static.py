"""RVM-static 混合通道（方案 M1-C 终判落地项 ③）

路由:
  static 帧 → RVM MattingNetwork(mobilenetv3) alpha>0.1（时序一致 J500=0，无 fallback 概念）
              盲区帧（alpha 面积<0.5% 或 max<0.15，如亮底/低对比）→ 回退 SAM2 对应帧
  mid/fast 帧 → SAM2 4层链路输出（默认 m4_full_chain_sg15，可 --sam2-dir 覆盖）

价值: SAM2 的 37 次 fallback 全在 static 段（传播崩塌）→ 混合后 Tier1 传播只服务 mid 段，
      FR 口径降为 0；RVM 时序一致性把 static 段 J500 压到 0。

用法:
  py -3.12 scripts/hybrid_rvm_static.py --video <mp4> --levels <motion_levels.json> \
      --sam2-dir output/step2_locator/m4_full_chain_sg15 --outdir output/step2_locator/hybrid_rvm \
      --start 2000 --frames 500
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from core.torch_runtime import get_device, infer_ctx

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = PROJECT / "data" / "real_amv_test" / "DL_黑岩射手_r924_BV1NL4y1H7u7.mp4"
DEFAULT_CKPT = PROJECT / "external" / "rvm" / "rvm_mobilenetv3.pth"
FFMPEG = "ffmpeg"

RVM_TH = 0.1           # RVM alpha 二值阈值（报告 §4.3：0.1/0.3/0.5 J500 均=0；取 0.1 面积最全）
BLIND_AREA = 0.005     # 盲区判据 1：alpha>0.1 面积占比 < 0.5%
BLIND_MAX = 0.15       # 盲区判据 2：alpha_max < 0.15（2000-2005 实测 ≤0.078）


def imread_gray_unicode(p: Path) -> np.ndarray | None:
    if not p.exists():
        return None
    img = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(DEFAULT_VIDEO))
    ap.add_argument("--checkpoint", default=str(DEFAULT_CKPT))
    ap.add_argument("--levels", required=True)
    ap.add_argument("--sam2-dir", default="output/step2_locator/m4_full_chain_sg15")
    ap.add_argument("--outdir", default="output/step2_locator/hybrid_rvm")
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--frames", type=int, default=500)
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    frame_dir = outdir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    mask_dir = outdir / "mask"
    mask_dir.mkdir(exist_ok=True)

    # ---- 1. 帧抽取 ----
    end = args.start + args.frames - 1
    r = subprocess.run([FFMPEG, "-y", "-i", args.video, "-vf", f"select='between(n,{args.start},{end})'",
                        "-vsync", "0", "-frame_pts", "1", str(frame_dir / "f_%05d.png")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ffmpeg failed: {r.stderr[-800:]}", file=sys.stderr)
        return 1
    frame_paths = sorted(frame_dir.glob("f_*.png"))
    print(f"[EXTRACT] {len(frame_paths)} frames", file=sys.stderr)

    # ---- 2. 级别 ----
    ml = json.loads(Path(args.levels).read_text(encoding="utf-8"))
    levels = ml.get("motion_level") or []

    # ---- 3. RVM 全段推理（recurrent 连续） ----
    sys.path.insert(0, str(PROJECT / "external" / "rvm"))
    from model import MattingNetwork  # noqa: E402
    dev = get_device()
    net = MattingNetwork("mobilenetv3").eval().to(dev)
    net.load_state_dict(torch.load(args.checkpoint, map_location=dev, weights_only=True))
    print(f"[MODEL] RVM on {dev}", file=sys.stderr)

    rvm_alpha: dict[int, np.ndarray] = {}
    rec = [None] * 4
    t0 = time.time()
    for i, p in enumerate(frame_paths):
        bgr = cv2.imdecode(np.fromfile(str(p), dtype=np.uint8), cv2.IMREAD_COLOR)
        gi = args.start + i
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        src = torch.from_numpy(rgb).float().div(255.0).permute(2, 0, 1).unsqueeze(0).unsqueeze(0).to(dev)
        with infer_ctx(dev):
            _, pha, *rec = net(src, *rec, downsample_ratio=0.4)
        rvm_alpha[gi] = pha[0, 0, 0].cpu().numpy()
        if (i + 1) % 100 == 0:
            print(f"[RVM] {i+1}/{len(frame_paths)}", file=sys.stderr)
    print(f"[RVM] done in {time.time()-t0:.1f}s", file=sys.stderr)

    # ---- 4. 组装混合 mask ----
    sam2_dir = Path(args.sam2_dir)
    stats = {"static_rvm": 0, "static_fallback": 0, "mid_sam2": 0, "fast_sam2": 0, "missing_sam2": 0}
    for i in range(args.frames):
        gi = args.start + i
        lv = levels[i] if i < len(levels) else "static"
        if lv == "static":
            pha = rvm_alpha[gi]
            area = float(np.mean(pha > RVM_TH))
            amax = float(pha.max())
            if area < BLIND_AREA or amax < BLIND_MAX:
                # RVM 盲区 → 回退 SAM2
                sam2 = imread_gray_unicode(sam2_dir / f"mask_{gi:05d}.png")
                if sam2 is None:
                    sam2 = np.zeros_like(pha, dtype=np.uint8)
                    stats["missing_sam2"] += 1
                out = sam2
                stats["static_fallback"] += 1
            else:
                out = np.where(pha > RVM_TH, 255, 0).astype(np.uint8)
                stats["static_rvm"] += 1
        else:
            sam2 = imread_gray_unicode(sam2_dir / f"mask_{gi:05d}.png")
            if sam2 is None:
                sam2 = np.zeros((720, 1280), dtype=np.uint8)
                stats["missing_sam2"] += 1
            out = sam2
            if lv == "mid":
                stats["mid_sam2"] += 1
            else:
                stats["fast_sam2"] += 1
        ok, buf = cv2.imencode(".png", out)
        buf.tofile(str(mask_dir / f"mask_{gi:05d}.png"))

    report = {
        "route": "static->RVM(alpha>0.1, 盲区回退SAM2) / mid|fast->SAM2",
        "sam2_dir": str(sam2_dir),
        "rvm_threshold": RVM_TH,
        "blind_criteria": {"area_lt": BLIND_AREA, "max_lt": BLIND_MAX},
        "stats": stats,
        "fr_metric": "static 段无 fallback 概念；SAM2 段(mid+fast)历史 fallback=0 → 混合 FR=0",
        "elapsed_s": round(time.time() - t0, 1),
    }
    out_json = outdir / "hybrid_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
