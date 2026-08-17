"""build_style_visual_anchor.py — references → 风格卡视觉锚（CLIP 嵌入质心）

从 D:\\AE-Work\\resources\\references 采样参考图, CLIP ViT-L-14 编码
(复用 cnn_scorer 编码管线), 按简单颜色/亮度启发式粗分 4 组,
每组算嵌入质心 → data/style_cards_visual_anchor.json。

用途: 风格自检 (style_card_compliance) 可对比"渲染帧嵌入 vs 风格锚质心"
的余弦距离, 给出风格贴近度 (视觉证据而非仅评分)。

用法:
  python scripts/build_style_visual_anchor.py [--n 120]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

REF_ROOT = PROJECT / "data" / "real_amv_test"   # 真实动漫素材视频 (references 为小图标, 弃用)
OUT = PROJECT / "data" / "style_cards_visual_anchor.json"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# 粗分组启发式 (饱和度/亮度 → 风格方向)
GROUPS = {
    "vivid":    "高饱和 (amv/hardcore 方向)",
    "muted":    "低饱和 (ambient/emotional 方向)",
    "dark":     "暗调 (cinematic/cyberpunk 方向)",
    "bright":   "亮调 (high_key 方向)",
}


def hue_stat(img_bgr):
    import cv2
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    return float(hsv[:, :, 1].mean()), float(hsv[:, :, 2].mean())


def group_of(sat, bri):
    if bri < 90:
        return "dark"
    if sat > 110:
        return "vivid"
    if bri > 170:
        return "bright"
    return "muted"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    args = ap.parse_args()

    if not REF_ROOT.exists():
        print(f"参考图目录不存在: {REF_ROOT}")
        return 1
    import cv2 as _cv2
    vids = sorted(REF_ROOT.glob("*.mp4"))
    print(f"素材视频 {len(vids)} 个, 抽帧采样 {args.n} 张")
    rng = random.Random(2026)
    picks = []
    with __import__('tempfile').TemporaryDirectory() as td:
        for vi, v in enumerate(vids):
            if len(picks) >= args.n:
                break
            cap = _cv2.VideoCapture(str(v))
            total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT))
            for k in range(3):  # 每视频 3 帧
                cap.set(_cv2.CAP_PROP_POS_FRAMES, int(total * (k + 1) / 4))
                ret, fr = cap.read()
                if not ret:
                    continue
                fp = Path(td) / f"v{vi:03d}_{k}.jpg"
                _cv2.imwrite(str(fp), fr, [_cv2.IMWRITE_JPEG_QUALITY, 88])
                picks.append(fp)
            cap.release()
        # 快照到持久目录 (临时目录会删)
        keep = PROJECT / "data" / "style_anchor_frames"
        keep.mkdir(parents=True, exist_ok=True)
        import shutil
        for i, src in enumerate(picks):
            shutil.copy(src, keep / f"anchor_{i:03d}.jpg")
        picks = sorted(keep.glob("*.jpg"))

    import cv2
    from core.cnn_scorer import encode_frames
    groups: dict = {}
    embs = {}
    from core.cnn_scorer import _load_clip
    import torch
    model, preprocess = _load_clip()
    from PIL import Image

    for f in picks:
        img = cv2.imread(str(f))
        if img is None or img.size == 0:
            continue
        # PIL 预验证 (cv2 对部分假 png 返回空矩阵)
        try:
            from PIL import Image
            with Image.open(f) as im:
                im.convert("RGB")
        except Exception:
            continue
        small = cv2.resize(img, (160, 90))
        sat, bri = hue_stat(small)
        g = group_of(sat, bri)
        groups.setdefault(g, []).append(str(f))

    # 每组编码质心
    anchors = {}
    for g, files in groups.items():
        vecs = []
        with torch.no_grad():
            for fp in files[:30]:
                try:
                    t = preprocess(Image.open(fp).convert("RGB")).unsqueeze(0).to(
                        next(model.parameters()).device)
                    v = model.encode_image(t)
                    v = v / v.norm(dim=-1, keepdim=True).clamp_min(1e-8)
                    vecs.append(v.cpu().numpy()[0])
                except Exception:
                    continue
        if len(vecs) >= 3:
            c = np.mean(vecs, axis=0)
            c = c / (np.linalg.norm(c) + 1e-8)
            anchors[g] = {
                "desc": GROUPS[g], "n_images": len(files),
                "centroid": [round(float(x), 5) for x in c],
            }
            print(f"  {g}: {len(files)} 张 → 质心 {len(anchors[g]['centroid'])} 维")

    OUT.write_text(json.dumps({
        "source": str(REF_ROOT), "sampled": len(picks),
        "groups": anchors,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"视觉锚: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
