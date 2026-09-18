#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_matting_dataset.py — 抠像集成训练集构建 (person 类 GT mask)

从多公开数据集提取 person 类像素级 mask, 统一为 imgs/masks 二值 (0/255) 格式,
供 BiRefNet 混合微调 (动漫域 + 真实人像/场景域泛化 + 发丝边缘)。

数据源与类别 ID (均为语义分割 label 像素值):
  - anime (animeseg)        : 已有二值 mask, 直接链接 (1111 对)
  - VOC2012 SegmentationClass: person = 15
  - cityscapes gtFine labelIds: person = 24, rider = 25 (均归为人)
  - ADE20k annotations       : person = 12
  - (CelebA 无 GT mask, 由 gen_celeba_pseudo_mask.py 单独生成)

输出布局:
  <out>/
    imgs/<prefix>_<stem>.jpg    (BGR 原图, 保真)
    masks/<prefix>_<stem>.png   (二值 0/255)
    manifest.jsonl              (每行: 源/文件名/来源数据集)

用法 (云端, 数据已解压):
  python build_matting_dataset.py \
    --out /root/autodl-tmp/matting_dataset \
    --anime /root/autodl-tmp/animeseg/dataset \
    --voc /root/autodl-tmp/VOCdevkit/VOC2012 \
    --cityscapes /root/autodl-tmp/cityscapes \
    --ade /root/autodl-tmp/ADEChallengeData2016
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

PERSON_VOC = 15
PERSON_CITYSCAPES = {24, 25}   # person + rider
PERSON_ADE = 12

# person 像素最小面积 (低于此视为噪声/误检, 过滤)
# 注意: cityscapes 是 2048x1024 大图, 500px 仅 0.024% 面积 = 微小人物噪声,
# 对发丝级边缘训练零价值且教会模型输出极小前景 → 20000px (~1% 面积) 起步
MIN_PERSON_PIXELS = 20000

# 每源最多采样数 (None=不限)
DEFAULT_MAX = {"anime": None, "voc": 1500, "cityscapes": 1500, "ade": 1500}


def ensure_dirs(out: Path):
    (out / "imgs").mkdir(parents=True, exist_ok=True)
    (out / "masks").mkdir(parents=True, exist_ok=True)


def save_pair(out: Path, prefix: str, img: np.ndarray, mask_bin: np.ndarray,
              stem: str, src: str, manifest: list[dict]):
    """mask_bin: bool/HxW (True=前景). 保真写原图 + 二值 mask."""
    assert mask_bin.ndim == 2, \
        f"mask 必须 2D, 实际 {mask_bin.shape} (3D 会写出三通道 mask 污染训练集)"
    h, w = img.shape[:2]
    mask_u8 = (mask_bin.astype(np.uint8) * 255)
    if mask_bin.shape[:2] != (h, w):
        mask_u8 = cv2.resize(mask_u8, (w, h), interpolation=cv2.INTER_NEAREST)
    name = f"{prefix}_{stem}"
    cv2.imwrite(str(out / "imgs" / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    cv2.imwrite(str(out / "masks" / f"{name}.png"), mask_u8)
    manifest.append({"name": name, "source": src, "h": h, "w": w})


def extract_voc(voc: Path, out: Path, manifest: list[dict], max_n: int | None):
    # 路径探测 (2026-08-15): 兼容 <root>/VOC2012 与 <root>/VOCdevkit/VOC2012
    for cand in (voc, voc / "VOC2012", voc / "VOCdevkit" / "VOC2012"):
        if (cand / "SegmentationClass").exists() and (cand / "JPEGImages").exists():
            voc = cand
            break
    seg_dir = voc / "SegmentationClass"
    img_dir = voc / "JPEGImages"
    if not seg_dir.exists():
        print(f"  [skip] VOC 目录不存在: {seg_dir}", file=sys.stderr)
        return 0
    n = 0
    for mp in sorted(seg_dir.glob("*.png")):
        if max_n is not None and n >= max_n:
            break
        # VOC SegmentationClass 是调色板索引 PNG (mode P, 类ID=索引值, person=15)。
        # OpenCV(尤其 5.x) 读不出调色板索引(会量化成 0/128/192/224 颜色) → 用 PIL
        # 读原始索引。（2026-08-15 云端实测根因: cv2 读 VOC person 恒为 0）
        mask = None
        try:
            from PIL import Image
            im = Image.open(str(mp))
            if im.mode == "P":
                mask = np.array(im)  # 调色板 PNG: 像素值=类索引 (2D)
            # 非 P 模式(RGB 衍生)不取: 索引→调色板颜色映射不可知,
            # 直接 np.array 会得到 HxWx3 → person=mask==15 变 3D bool,
            # save_pair 写出三通道 mask 污染训练集 (2026-09-10 修复)。
            # 留 None 走 cv2 兜底, 取不到可靠索引的样本自然被面积阈值过滤。
        except Exception:
            pass
        if mask is None:  # 兜底: PIL 不可用/非调色板时退回 cv2 单通道
            _m = cv2.imread(str(mp), cv2.IMREAD_UNCHANGED)
            if _m is None:
                continue
            mask = _m[..., 0] if _m.ndim == 3 else _m
        if mask.ndim != 2:  # 双保险: 任何路径都不得带 3D mask 进 save_pair
            continue
        person = mask == PERSON_VOC
        if int(person.sum()) < MIN_PERSON_PIXELS:
            continue
        img_path = img_dir / f"{mp.stem}.jpg"
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        save_pair(out, "voc", img, person, mp.stem, "voc2012", manifest)
        n += 1
    print(f"  VOC2012 person: {n}", file=sys.stderr)
    return n


def extract_cityscapes(cs: Path, out: Path, manifest: list[dict], max_n: int | None):
    n = 0
    # 路径探测 (2026-08-15): 兼容两种云端布局
    #   A. --cityscapes 传数据集根: <root>/gtFine, <root>/leftImg8bit
    #   B. --cityscapes 传挂载父目录: <root>/cityscapes/gtFine, ... (autodl-pub 常见)
    for cand in (cs, cs / "cityscapes"):
        if (cand / "gtFine").exists() and (cand / "leftImg8bit").exists():
            cs = cand
            break
    gt_root = cs / "gtFine"
    img_root = cs / "leftImg8bit"
    if not gt_root.exists():
        print(f"  [skip] cityscapes gtFine 不存在: {gt_root}", file=sys.stderr)
        return 0
    for split in ("train", "val"):
        gt_split = gt_root / split
        if not gt_split.exists():
            continue
        for mp in sorted(gt_split.rglob("*_gtFine_labelIds.png")):
            if max_n is not None and n >= max_n:
                break
            mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                continue
            person = np.isin(mask, list(PERSON_CITYSCAPES))
            if int(person.sum()) < MIN_PERSON_PIXELS:
                continue
            # 原图: {stem}_leftImg8bit.png  (去掉 _gtFine_labelIds 后缀)
            stem = mp.name[:-len("_gtFine_labelIds.png")]
            img_path = img_root / split / mp.parent.name / f"{stem}_leftImg8bit.png"
            if not img_path.exists():
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            save_pair(out, "cs", img, person, stem, "cityscapes", manifest)
            n += 1
    print(f"  cityscapes person: {n}", file=sys.stderr)
    return n


def extract_ade(ade: Path, out: Path, manifest: list[dict], max_n: int | None):
    # 路径探测 (2026-08-15): 兼容 <root>/ADEChallengeData2016 与 <root>/ADE20K_2016_2017
    for cand in (ade, ade / "ADEChallengeData2016"):
        if (cand / "annotations" / "training").exists():
            ade = cand
            break
    ann_dir = ade / "annotations" / "training"
    img_dir = ade / "images" / "training"
    if not ann_dir.exists():
        print(f"  [skip] ADE annotations 不存在: {ann_dir}", file=sys.stderr)
        return 0
    n = 0
    for mp in sorted(ann_dir.glob("ADE_train_*.png")):
        if max_n is not None and n >= max_n:
            break
        mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
        person = mask == PERSON_ADE
        if int(person.sum()) < MIN_PERSON_PIXELS:
            continue
        img_path = img_dir / f"{mp.stem}.jpg"
        if not img_path.exists():
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        save_pair(out, "ade", img, person, mp.stem, "ade20k", manifest)
        n += 1
    print(f"  ADE20k person: {n}", file=sys.stderr)
    return n


def link_anime(anime: Path, out: Path, manifest: list[dict], max_n: int | None):
    imgs_dir = anime / "imgs"
    masks_dir = anime / "masks"
    if not imgs_dir.exists():
        print(f"  [skip] anime 目录不存在: {imgs_dir}", file=sys.stderr)
        return 0
    n = 0
    for ip in sorted(list(imgs_dir.glob("*.jpg")) + list(imgs_dir.glob("*.png"))):
        if max_n is not None and n >= max_n:
            break
        mp = masks_dir / f"{ip.stem}.png"
        if not mp.exists():
            mp = masks_dir / f"{ip.stem}.jpg"
        if not mp.exists():
            continue
        img = cv2.imread(str(ip))
        mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
        if img is None or mask is None:
            continue
        save_pair(out, "anime", img, mask > 127, ip.stem, "animeseg", manifest)
        n += 1
    print(f"  anime: {n}", file=sys.stderr)
    return n


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="抠像集成训练集构建 (GT mask 数据源)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--anime", default="")
    ap.add_argument("--voc", default="")
    ap.add_argument("--cityscapes", default="")
    ap.add_argument("--ade", default="")
    ap.add_argument("--max-anime", type=int, default=-1, help="-1=不限")
    ap.add_argument("--max-voc", type=int, default=1500)
    ap.add_argument("--max-cityscapes", type=int, default=1500)
    ap.add_argument("--max-ade", type=int, default=1500)
    args = ap.parse_args()

    out = Path(args.out)
    ensure_dirs(out)
    manifest: list[dict] = []
    total = 0

    if args.anime:
        total += link_anime(Path(args.anime), out, manifest,
                            None if args.max_anime < 0 else args.max_anime)
    if args.voc:
        total += extract_voc(Path(args.voc), out, manifest, args.max_voc)
    if args.cityscapes:
        total += extract_cityscapes(Path(args.cityscapes), out, manifest, args.max_cityscapes)
    if args.ade:
        total += extract_ade(Path(args.ade), out, manifest, args.max_ade)

    (out / "manifest.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in manifest) + "\n",
        encoding="utf-8")
    print(f"集成训练集: {total} 对 -> {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
