"""Vimeo-90k 时序指标基准化：把 J500/帧间IoU 放到标准连续序列上验证
（补齐"所有时序结论基于单支素材"的方法学短板）
用法（云端，Vimeo-90k 已挂载）:
  python eval_vimeo_temporal.py --n 20 --out vimeo_temporal.json
指标: 对每组连续 7 帧序列逐帧抠像 → 帧间非空率差>0.5 计数(J7) + 帧间IoU均值
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

VIMEO = Path("/root/autodl-pub/Vimeo-90k")
SEQ_DIR = VIMEO / "vimeo_septuplet" / "sequences"  # 每组 7 帧

tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="评估序列组数")
    ap.add_argument("--out", default="vimeo_temporal.json")
    args = ap.parse_args()

    seqs = sorted(SEQ_DIR.glob("*/*"))[:500] if SEQ_DIR.exists() else []
    if not seqs:
        # 备用路径探测
        for cand in (VIMEO, VIMEO / "vimeo_septuplet"):
            if (cand / "sequences").exists():
                seqs = sorted((cand / "sequences").glob("*/*"))
                break
    if not seqs:
        print("Vimeo-90k 路径未找到，请确认挂载", file=sys.stderr)
        return 1
    random.seed(42)
    random.shuffle(seqs)
    seqs = seqs[:args.n]

    model = AutoModelForImageSegmentation.from_pretrained(
        "external/birefnet", trust_remote_code=True, local_files_only=True).cuda().half().eval()

    j_counts = []      # 每组序列的帧间跳变次数（7帧=6个帧间对）
    iou_means = []
    t0 = time.time()
    for si, seq in enumerate(seqs):
        frames = sorted(seq.glob("im*.png"))
        if len(frames) < 4:
            continue
        areas = []
        prev_mask = None
        pair_ious = []
        for f in frames[:7]:
            img = cv2.imread(str(f))
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            inp = tf(rgb).unsqueeze(0).half().cuda()
            with infer_ctx(get_device()):
                pred = model(inp)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
            h, w = img.shape[:2]
            pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
            mask = (pred * 255).astype(np.uint8)
            area = np.count_nonzero(mask > 127) / (h * w)
            areas.append(area)
            binm = (mask > 127).astype(np.uint8)
            if prev_mask is not None:
                inter = np.count_nonzero(np.logical_and(binm, prev_mask))
                union = np.count_nonzero(np.logical_or(binm, prev_mask))
                pair_ious.append(inter / union if union else 0.0)
            prev_mask = binm
        jumps = sum(1 for i in range(1, len(areas)) if abs(areas[i] - areas[i - 1]) > 0.5)
        j_counts.append(jumps)
        if pair_ious:
            iou_means.append(float(np.mean(pair_ious)))
        if (si + 1) % 5 == 0:
            print(f"  {si + 1}/{len(seqs)} 组", file=sys.stderr)

    result = {
        "sequences": len(j_counts),
        "J_mean_per_seq": round(float(np.mean(j_counts)), 3),
        "J_total": int(sum(j_counts)),
        "pairwise_IoU_mean": round(float(np.mean(iou_means)), 4),
        "elapsed_s": round(time.time() - t0, 1),
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
