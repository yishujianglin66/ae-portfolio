"""wa2_to_alpha.py — WA2 产物 → BiRefNet mixed 抠像 → alpha 序列 + 橙底预览

木偶动画线并入 MasterCut 主链的标准出口（2026-09-10 验证通过）：
  WA2 输出（云端/本机均可）→ BiRefNet(finetuned_anime_mixed, IoU 0.9756) 逐帧抠像
  → alpha mp4 + 橙底预览 mp4（交付 v14 同款标准）

实测性能（RTX 4060, torch 2.9.0+cu126）：720p 85 帧全程 33.9s（0.40s/帧，含合成）。

用法：
  python scripts/wa2_to_alpha.py <input.mp4> [--out-dir DIR] [--fps 16]
产物：
  <stem>_alpha.mp4            # 灰度 alpha 序列
  <stem>_orange_preview.mp4   # 橙底合成预览（v14 交付标准）

前置（2026-09-10 已验证的 venv 状态）：
  - torch cu126 GPU 版 + torchvision（.venv）
  - einops / kornia / timm（BiRefNet 远程代码依赖）
  - external/birefnet/ 含 config.json + BiRefNet_config.py + birefnet.py + handler.py
    （09-08 venv 重建后丢失，已从 hf-mirror 补回；权重 finetuned_anime_mixed.pth 在库）
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torchvision import transforms

from core.torch_runtime import infer_ctx

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "external" / "birefnet"
WEIGHT_CHAIN = [
    MODEL_DIR / "finetuned_anime_mixed.pth",   # 混合微调 IoU 0.9756（生产首选）
    MODEL_DIR / "finetuned_anime_fp16.pth",    # fp16 备份
]


def load_model():
    from transformers import AutoModelForImageSegmentation

    model = AutoModelForImageSegmentation.from_pretrained(
        str(MODEL_DIR), trust_remote_code=True, local_files_only=True).eval().cuda()
    for w in WEIGHT_CHAIN:
        if not w.exists():
            continue
        try:
            sd = torch.load(w, map_location="cpu")
            if isinstance(sd, dict) and "state_dict" in sd:
                sd = sd["state_dict"]
            model.load_state_dict(sd)
            print(f"[BiRefNet] 微调权重 {w.name}", file=sys.stderr)
            break
        except Exception as e:  # noqa: BLE001
            print(f"[BiRefNet] {w.name} 加载失败({e})，尝试下一个", file=sys.stderr)
    return model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="WA2 产物视频（mp4）")
    ap.add_argument("--out-dir", default=None, help="输出目录，默认与输入同目录")
    ap.add_argument("--fps", type=float, default=16.0)
    a = ap.parse_args()

    src = Path(a.input)
    out_dir = Path(a.out_dir) if a.out_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    model = load_model()
    tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Resize((1024, 1024)),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    cap = cv2.VideoCapture(str(src))
    frames_bgr = []
    while True:
        ret, f = cap.read()
        if not ret:
            break
        frames_bgr.append(f)
    cap.release()
    if not frames_bgr:
        print("no frames", file=sys.stderr)
        return 1
    n = len(frames_bgr)
    h, w = frames_bgr[0].shape[:2]
    print(f"{n} frames {w}x{h}", file=sys.stderr)

    alpha_path = out_dir / f"{src.stem}_alpha.mp4"
    prev_path = out_dir / f"{src.stem}_orange_preview.mp4"
    out_alpha = cv2.VideoWriter(str(alpha_path), cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (w, h))
    out_prev = cv2.VideoWriter(str(prev_path), cv2.VideoWriter_fourcc(*"mp4v"), a.fps, (w, h))

    areas = []
    t0 = time.time()
    with infer_ctx("cuda"):
        for bgr in frames_bgr:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            pil = tf(rgb).unsqueeze(0).half().cuda()
            pred = model(pil)[-1].sigmoid().cpu()[0].squeeze().float().numpy()
            m = cv2.resize((pred * 255).astype(np.uint8), (w, h), interpolation=cv2.INTER_LINEAR)
            areas.append(float(np.count_nonzero(m > 127)) / m.size)
            alpha = (m.astype(np.float32) / 255)[:, :, None]
            orange = np.full_like(bgr, (0, 165, 255))  # BGR 橙（v14 交付标准）
            comp = (bgr * alpha + orange * (1 - alpha)).astype(np.uint8)
            out_alpha.write(cv2.cvtColor(m, cv2.COLOR_GRAY2BGR))
            out_prev.write(comp)
    out_alpha.release()
    out_prev.release()

    dt = time.time() - t0
    areas_sorted = sorted(areas)
    print(f"全程 {dt:.1f}s = {dt/n:.2f}s/帧（含合成）")
    print(f"alpha>127 面积: min {areas_sorted[0]:.3f} max {areas_sorted[-1]:.3f} 中位 {areas_sorted[n//2]:.3f}")
    print(f"alpha:   {alpha_path}")
    print(f"preview: {prev_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
