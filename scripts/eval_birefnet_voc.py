"""BiRefNet 微调前后客观评估：VOC2012 SegmentationClass person 类 IoU / 边界 F1

VOC 是调色板索引 PNG（person=15），需 PIL 读原始索引（2026-08-15 云端实测根因）。
用作 COCO 不可用时的第二套评估集（项目文档 2026-08-15-cloud-datasets-integration.md 规划）。

用法（云端）:
  python eval_birefnet_voc.py --weights /path/finetuned_anime_mixed.pth --out eval_mixed.json
  python eval_birefnet_voc.py --out eval_base.json        # 不传 --weights = 基座
  python eval_birefnet_voc.py --weights A --out a.json    # 微调前/后各自跑, 再对比
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
from core.torch_runtime import infer_ctx, get_device
from torchvision import transforms
from transformers import AutoModelForImageSegmentation

VOC_ROOT = Path("/root/autodl-tmp/datasets/VOC2012")
SEG_DIR = VOC_ROOT / "SegmentationClass"
IMG_DIR = VOC_ROOT / "JPEGImages"
MODEL_DIR = "birefnet"
PERSON_VOC = 15
MIN_PERSON_PIXELS = 500

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
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="", help="微调权重路径; 空=基座")
    ap.add_argument("--out", default="eval_voc.json")
    ap.add_argument("--n", type=int, default=200, help="评估样本数")
    ap.add_argument("--voc-root", default=str(VOC_ROOT))
    ap.add_argument("--model-dir", default=MODEL_DIR)
    args = ap.parse_args()

    from PIL import Image
    seg_dir = Path(args.voc_root) / "SegmentationClass"
    img_dir = Path(args.voc_root) / "JPEGImages"
    if not seg_dir.exists():
        print(f"[skip] VOC 不存在: {seg_dir}", file=sys.stderr)
        return 1

    # 收集含 person 的样本
    cand = []
    for mp in sorted(seg_dir.glob("*.png")):
        im = Image.open(str(mp))
        m = np.array(im)
        if m.ndim == 3:
            m = m[..., 0]
        if int((m == PERSON_VOC).sum()) >= MIN_PERSON_PIXELS:
            cand.append(mp)
    random.seed(42)
    random.shuffle(cand)
    cand = cand[:args.n]
    print(f"person 样本: {len(cand)}", file=sys.stderr)

    model = AutoModelForImageSegmentation.from_pretrained(
        args.model_dir, trust_remote_code=True, local_files_only=True).cuda().half().eval()
    if args.weights:
        model.load_state_dict(torch.load(args.weights, map_location="cpu"))
        print(f"加载权重 {args.weights}", file=sys.stderr)

    ious, f1s = [], []
    t0 = time.time()
    for mp in cand:
        im = Image.open(str(mp))
        mask_idx = np.array(im)
        if mask_idx.ndim == 3:
            mask_idx = mask_idx[..., 0]
        gt = (mask_idx == PERSON_VOC).astype(np.uint8) * 255
        img_path = img_dir / f"{mp.stem}.jpg"
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        inp = tf(rgb).unsqueeze(0).half().cuda()
        with infer_ctx(get_device()):
            pred = model(inp)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
        pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
        pred_u8 = (pred * 255).astype(np.uint8)
        ious.append(compute_iou(pred_u8, gt))
        f1s.append(boundary_f1(pred_u8, gt))
        if len(ious) % 50 == 0:
            print(f"  {len(ious)}/{len(cand)} IoU均值 {np.mean(ious):.3f}", file=sys.stderr)

    result = {
        "weights": args.weights or "base",
        "dataset": "VOC2012-person",
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
