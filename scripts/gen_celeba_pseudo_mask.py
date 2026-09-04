#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_celeba_pseudo_mask.py — CelebA 人像 BiRefNet 自标注伪 mask

CelebA 只有 bbox+landmark 无像素级 mask。用 BiRefNet 原版 (base) 对对齐人脸
逐张推理生成伪 mask, 阈值化 (sigmoid > 0.5) 得二值前景, 补足"人像发丝"训练集。

输出与 build_matting_dataset.py 一致的 imgs/masks 二值格式:
  <out>/imgs/celeba_<stem>.jpg
  <out>/masks/celeba_<stem>.png

用法 (云端, 需 torch/transformers + BiRefNet 代码):
  python gen_celeba_pseudo_mask.py \
    --celeba /root/autodl-tmp/celeba/img_align_celeba \
    --model-dir /root/autodl-tmp/birefnet \
    --out /root/autodl-tmp/matting_dataset \
    --n 4000 --batch 8
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import List

import cv2
import numpy as np
import torch
from core.torch_runtime import infer_ctx, get_device
from torchvision import transforms

MIN_AREA_RATIO = 0.02  # 前景面积占比下限 (过滤全黑/噪声)
MAX_AREA_RATIO = 0.85  # 前景面积占比上限 (过滤 BiRefNet 全图误判: 纯色背景+肤色接近时输出>85%前景)

tf = transforms.Compose([
    transforms.ToTensor(),
    transforms.Resize((1024, 1024)),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="CelebA BiRefNet 自标注伪 mask")
    ap.add_argument("--celeba", required=True, help="img_align_celeba 解压目录")
    ap.add_argument("--model-dir", required=True, help="BiRefNet 模型目录 (含 config/birefnet.py)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=4000)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    celeba = Path(args.celeba)
    out = Path(args.out)
    (out / "imgs").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(parents=True, exist_ok=True)

    files = sorted(celeba.glob("*.jpg"))
    if not files:
        print(f"CelebA 目录无图: {celeba}", file=sys.stderr)
        return 1
    random.seed(42)
    files = random.sample(files, min(args.n, len(files)))
    print(f"抽样 {len(files)} 张对齐人脸", file=sys.stderr)

    from transformers import AutoModelForImageSegmentation
    model = AutoModelForImageSegmentation.from_pretrained(
        args.model_dir, trust_remote_code=True, local_files_only=True).cuda().half().eval()

    manifest: List[dict] = []
    t0 = time.time()
    for i in range(0, len(files), args.batch):
        batch = files[i:i + args.batch]
        imgs = []
        metas = []
        for f in batch:
            img = cv2.imread(str(f))
            if img is None:
                continue
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = img.shape[:2]
            imgs.append(rgb)
            metas.append((f, img, h, w))
        if not imgs:
            continue
        inp = torch.stack([tf(x) for x in imgs]).half().cuda()
        with infer_ctx(get_device()):
            preds = model(inp)[-1].sigmoid().cpu().float().numpy()
        for k, (f, img_bgr, h, w) in enumerate(metas):
            pred = preds[k][0]
            pred = cv2.resize(pred, (w, h), interpolation=cv2.INTER_LINEAR)
            bin_mask = (pred > 0.5).astype(np.uint8)
            area_ratio = bin_mask.sum() / (h * w)
            if area_ratio < MIN_AREA_RATIO:
                continue  # 前景过小 → 噪声
            if area_ratio > MAX_AREA_RATIO:
                continue  # 前景过大 → BiRefNet 全图误判 (纯色背景/肤色接近)
            name = f"celeba_{f.stem}"
            cv2.imwrite(str(out / "imgs" / f"{name}.jpg"), img_bgr,
                        [cv2.IMWRITE_JPEG_QUALITY, 95])
            cv2.imwrite(str(out / "masks" / f"{name}.png"), bin_mask * 255)
            manifest.append({"name": name, "source": "celeba_pseudo", "h": h, "w": w})
        done = i + len(metas)
        if done % 200 < args.batch:
            print(f"  {done}/{len(files)} ({time.time() - t0:.0f}s)", file=sys.stderr)

    (out / "celeba_manifest.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n",
        encoding="utf-8")
    print(f"CelebA 伪 mask: {len(manifest)} 张 -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
