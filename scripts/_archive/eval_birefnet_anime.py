"""BiRefNet 动漫域 A/B 评估: base / 旧动漫微调 / 新混合微调 (本地 animeseg GT)

用 external/animeseg/dataset 的 1111 对动漫 GT mask 评估 IoU / 边界 F1,
对比三个权重的动漫域精度 (混合微调是否损害动漫域 - 域漂移检验)。

用法:
  py -3.12 scripts/eval_birefnet_anime.py --weights external/birefnet/finetuned_anime_mixed.pth --out eval_mixed.json
  py -3.12 scripts/eval_birefnet_anime.py --out eval_base.json   # 不传 = base
  py -3.12 scripts/eval_birefnet_anime.py --weights external/birefnet/finetuned_anime_old.pth --out eval_old.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root: _archive 迁移后 core.* 导入用

from core.torch_runtime import infer_ctx  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "external" / "animeseg" / "dataset"
IMGS = DATA / "imgs"
MASKS = DATA / "masks"
MODEL_DIR = str(PROJECT / "external" / "birefnet")

tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def compute_iou(pred, gt):
    inter = np.count_nonzero((pred > 127) & (gt > 127))
    union = np.count_nonzero((pred > 127) | (gt > 127))
    return inter / union if union else 0.0


def boundary_f1(pred, gt):
    k = np.ones((5, 5), np.uint8)
    p_b = (pred > 127).astype(np.uint8)
    g_b = (gt > 127).astype(np.uint8)
    p_band = cv2.dilate(p_b, k) - cv2.erode(p_b, k)
    g_band = cv2.dilate(g_b, k) - cv2.erode(g_b, k)
    band = (p_band | g_band) > 0
    if not band.any():
        return 1.0
    tp = np.count_nonzero((p_b == g_b)[band])
    return tp / np.count_nonzero(band)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="")
    ap.add_argument("--out", default="eval_anime.json")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--model-dir", default=MODEL_DIR)
    args = ap.parse_args()

    pairs = []
    for ip in sorted(list(IMGS.glob("*.jpg")) + list(IMGS.glob("*.png"))):
        mp = MASKS / f"{ip.stem}.png"
        if not mp.exists():
            mp = MASKS / f"{ip.stem}.jpg"
        if mp.exists():
            pairs.append((ip, mp))
    random.seed(42)
    pairs = random.sample(pairs, min(args.n, len(pairs)))
    print(f"动漫域评估: {len(pairs)} 对 (权重: {args.weights or 'base'})", file=sys.stderr)

    model = AutoModelForImageSegmentation.from_pretrained(
        args.model_dir, trust_remote_code=True, local_files_only=True).cuda().half().eval()
    if args.weights:
        model.load_state_dict(torch.load(args.weights, map_location="cpu"))
        print(f"加载权重 {args.weights}", file=sys.stderr)

    ious, f1s = [], []
    t0 = time.time()
    for i, (ip, mp) in enumerate(pairs):
        img = cv2.imread(str(ip))
        gt = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        if img is None or gt is None:
            continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        inp = tf(rgb).unsqueeze(0).half().cuda()
        with infer_ctx():
            pred = model(inp)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
        pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
        pred_u8 = (pred * 255).astype(np.uint8)
        ious.append(compute_iou(pred_u8, gt))
        f1s.append(boundary_f1(pred_u8, gt))
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(pairs)} IoU均值 {np.mean(ious):.3f}", file=sys.stderr)

    result = {
        "weights": args.weights or "base",
        "n": len(ious),
        "IoU_mean": round(float(np.mean(ious)), 4),
        "IoU_median": round(float(np.median(ious)), 4),
        "boundaryF1_mean": round(float(np.mean(f1s)), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
