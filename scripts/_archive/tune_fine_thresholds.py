#!/usr/bin/env python3
"""
v3 fine-10 类逐类阈值调优 (同 tune_thresholds.py 逻辑, 10 类版)。

用法:
  py -3.12 scripts/tune_fine_thresholds.py --lora-dir models/output/anime_camera_lora_v3
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root: _archive 迁移后 core.* 导入用

from core.torch_runtime import get_device, infer_ctx  # noqa: E402

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


def get_probs(model, clip: str, device) -> Optional[np.ndarray]:
    import torch
    frames = load_frames(clip)
    if frames is None:
        return None
    from torchvision.transforms import v2
    x = v2.Resize((IMG_SIZE, IMG_SIZE))(torch.from_numpy(frames)).float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
    x = ((x - mean) / std).unsqueeze(0).to(device)
    with infer_ctx(device):
        logits = model(pixel_values=x).logits[0]
    return torch.softmax(logits, dim=-1).cpu().numpy()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="fine-10 类阈值调优")
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
    # v3 修复: 同 eval_fine_lora.py — base 需 num_labels=10 重建头
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
    probs_list: List[np.ndarray] = []
    truths: List[int] = []
    for s in samples:
        d = s.get("movement_label", "")
        if d not in label_to_idx:
            continue
        p = get_probs(model, s["clip_path"], device)
        if p is None:
            continue
        probs_list.append(p)
        truths.append(label_to_idx[d])
    P = np.stack(probs_list)
    y = np.array(truths)
    print(f"有效: {len(y)} 条")

    argmax_pred = P.argmax(1)
    base_acc = float((argmax_pred == y).mean())
    print(f"argmax 基线: {base_acc:.4f}")

    # 两阶段 (10类穷举网格 12^10 不可行):
    # 阶段1: 全局统一阈值扫描 → 阶段2: 逐类微调 (2 轮)
    grid = np.arange(0.05, 0.61, 0.05)
    majority = int(np.bincount(y, minlength=10).argmax())

    def apply_thresholds(thresh_arr: np.ndarray) -> np.ndarray:
        preds = []
        for p in P:
            above = np.where(p >= thresh_arr)[0]
            if len(above) == 0:
                preds.append(majority)
            else:
                preds.append(int(above[np.argmax(p[above])]))
        return np.array(preds)

    # 阶段1: 全局阈值
    best_tau, best_acc = 0.1, 0.0
    for tau in grid:
        preds = apply_thresholds(np.full(10, tau))
        acc = float((preds == y).mean())
        if acc > best_acc:
            best_tau, best_acc = tau, acc
    thresh_arr = np.full(10, best_tau)
    print(f"阶段1 全局阈值 {best_tau:.2f}: {best_acc:.4f}")

    # 阶段2: 逐类微调 2 轮
    for _round in range(2):
        for ci in range(10):
            cur = thresh_arr[ci]
            for tau in grid:
                t2 = thresh_arr.copy()
                t2[ci] = tau
                acc = float((apply_thresholds(t2) == y).mean())
                if acc > best_acc:
                    best_acc = acc
                    thresh_arr = t2
    print(f"阶段2 逐类微调后: {best_acc:.4f} (提升 {best_acc - base_acc:+.4f})")

    out = Path(args.lora_dir) / "thresholds_tuned.json"
    out.write_text(json.dumps({
        "labels": FINE_LABELS,
        "thresholds": {FINE_LABELS[i]: round(float(thresh_arr[i]), 3) for i in range(10)},
        "majority_fallback": FINE_LABELS[majority],
        "argmax_acc": round(base_acc, 4),
        "tuned_acc": round(best_acc, 4),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"阈值已存 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
