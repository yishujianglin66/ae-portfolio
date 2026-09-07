#!/usr/bin/env python3
"""
v3 fine-10 类评估: 300 条 VLM 一致性抽样 + 逐类精度 + 与 v1 粗分类对比。

用法 (v3 适配器下载后, 本机或云端):
  py -3.12 scripts/eval_fine_lora.py --lora-dir models/output/anime_camera_lora_v3 \
      --data-root D:\\AE-Data\\AnimeCamera --labels-name vlm_labels_merged.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.torch_runtime import infer_ctx, get_device  # noqa: E402

try:
    from scripts.train_anime_camera_lora import FINE_LABELS, NUM_FRAMES, IMG_SIZE  # noqa: E402
except ImportError:
    from train_anime_camera_lora import FINE_LABELS, NUM_FRAMES, IMG_SIZE  # noqa: E402

MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"


def load_frames(clip: str) -> Optional[np.ndarray]:
    from decord import VideoReader, cpu
    try:
        vr = VideoReader(clip, ctx=cpu(0))
    except Exception:  # noqa: BLE001
        return None
    n = len(vr)
    if n < 2:
        return None
    if n <= NUM_FRAMES:
        idxs = list(range(n))
    else:
        step = (n - 1) / (NUM_FRAMES - 1)
        idxs = [round(i * step) for i in range(NUM_FRAMES)]
    try:
        frames = vr.get_batch(idxs).asnumpy().astype(np.float32).transpose(0, 3, 1, 2)
    except Exception:  # noqa: BLE001
        return None
    if frames.shape[0] < NUM_FRAMES:
        rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
        frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
    return frames


def predict(model, clip: str, device) -> int:
    import torch
    frames = load_frames(clip)
    if frames is None:
        return -1
    from torchvision.transforms import v2
    x = v2.Resize((IMG_SIZE, IMG_SIZE))(torch.from_numpy(frames)).float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    x = ((x - mean) / std).unsqueeze(0).to(device)
    with infer_ctx(device):
        logits = model(pixel_values=x).logits[0]
    return int(logits.argmax().item())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="v3 fine-10 类评估")
    parser.add_argument("--lora-dir", required=True)
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--data-root", default=r"D:\AE-Data\AnimeCamera")
    parser.add_argument("--labels-name", default="vlm_labels_merged.jsonl")
    parser.add_argument("--n-eval", type=int, default=300)
    args = parser.parse_args()

    import torch
    device = get_device()
    from transformers import VideoMAEForVideoClassification
    from peft import PeftModel
    # v3 修复: fine schema 的 classifier 是 num_labels 重建的头 (不在基座 ckpt),
    # 训练脚本用 modules_to_save=["classifier"] 存进 adapter; 评估必须同样
    # 以 num_labels=10 重建 base, 否则 4 类头与 10 类 adapter 不匹配 (v3 首次评估坑)
    base = VideoMAEForVideoClassification.from_pretrained(
        args.model_dir, local_files_only=True, num_labels=len(FINE_LABELS),
        ignore_mismatched_sizes=True)
    base.to(device)
    model = PeftModel.from_pretrained(base, args.lora_dir)
    model.to(device)
    model.eval()

    labels = [json.loads(l) for l in
              (Path(args.data_root) / args.labels_name).read_text(encoding="utf-8").splitlines()
              if l.strip()]
    random.seed(42)
    samples = random.sample(labels, min(args.n_eval, len(labels)))

    label_to_idx = {l: i for i, l in enumerate(FINE_LABELS)}
    cm = np.zeros((10, 10), dtype=int)
    n = 0
    for s in samples:
        d = s.get("movement_label", "")
        if d not in label_to_idx:
            continue
        pred = predict(model, s["clip_path"], device)
        if pred < 0:
            continue
        cm[label_to_idx[d], pred] += 1
        n += 1

    acc = float(np.trace(cm) / n) if n else 0.0
    print(f"=== v3 fine-10 类评估 (n={n}) === 总准确率: {acc:.4f}")
    for i, l in enumerate(FINE_LABELS):
        total = int(cm[i].sum())
        if total:
            print(f"  {l:12s} n={total:4d} acc={cm[i, i] / total:.4f}")
    # 粗类映射 (与 v1 对比口径)
    coarse_map = {"static": "Static", "pan_left": "Motion", "pan_right": "Motion",
                  "tilt_up": "Motion", "tilt_down": "Motion", "orbit": "Motion",
                  "zoom_in": "Push", "push": "Push", "zoom_out": "Pull", "zoom_back": "Pull"}
    coarse_cm = np.zeros((4, 4), dtype=int)
    coarse_labels = ["Static", "Motion", "Pull", "Push"]
    for i, l in enumerate(FINE_LABELS):
        for j, p in enumerate(FINE_LABELS):
            coarse_cm[coarse_labels.index(coarse_map[l]),
                      coarse_labels.index(coarse_map[p])] += cm[i, j]
    coarse_acc = float(np.trace(coarse_cm) / n) if n else 0.0
    print(f"=== 映射到粗 4 类口径: {coarse_acc:.4f} (v1 71.72% 对比) ===")
    for i, l in enumerate(coarse_labels):
        total = int(coarse_cm[i].sum())
        if total:
            print(f"  {l:8s} n={total:4d} acc={coarse_cm[i, i] / total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
