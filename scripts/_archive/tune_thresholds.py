#!/usr/bin/env python3
"""
v1 LoRA 逐类阈值调优: 在 VLM 一致性抽样集上网格搜索每类 softmax 阈值,
取使总准确率最高的配置 (低于全部阈值 → 判 majority 类)。

用法: py -3.12 scripts/tune_thresholds.py
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
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 云上单文件执行

try:
    from scripts.train_anime_camera_lora import COARSE_LABELS, COARSE_MAP, NUM_FRAMES, IMG_SIZE  # noqa: E402
except ImportError:  # 云端单文件执行
    from train_anime_camera_lora import COARSE_LABELS, COARSE_MAP, NUM_FRAMES, IMG_SIZE  # noqa: E402

MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"
LORA_DIR = str(PROJECT_ROOT / "models" / "output" / "anime_camera_lora")
DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")


def load_frames(clip: str) -> np.ndarray:
    from decord import VideoReader, cpu
    vr = VideoReader(clip, ctx=cpu(0))
    n = len(vr)
    if n <= 1:
        return None
    if n <= NUM_FRAMES:
        idxs = list(range(n))
    else:
        step = (n - 1) / (NUM_FRAMES - 1)
        idxs = [round(i * step) for i in range(NUM_FRAMES)]
    frames = vr.get_batch(idxs).asnumpy().astype(np.float32).transpose(0, 3, 1, 2)
    # 先缩到目标尺寸再补齐 (避免在大图上 tile 撑爆内存)
    import torch
    from torchvision.transforms import v2
    frames = v2.Resize((IMG_SIZE, IMG_SIZE))(torch.from_numpy(frames)).numpy()
    if frames.shape[0] < NUM_FRAMES:
        rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
        frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
    return frames


def get_probs(model, clip: str, device) -> Optional[np.ndarray]:
    """手动归一化 (与训练一致, 绕开 processor 版本兼容问题)。"""
    import torch
    frames = load_frames(clip)  # (T,3,224,224) float32 0-255
    if frames is None:
        return None
    x = torch.from_numpy(frames).float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 3, 1, 1)
    x = (x - mean) / std
    x = x.unsqueeze(0).to(device)  # (1,T,3,224,224)
    with torch.no_grad():
        out = model(pixel_values=x)
    return torch.softmax(out.logits, dim=-1)[0].cpu().numpy()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="v1 LoRA 逐类阈值调优")
    parser.add_argument("--model-dir", default=MODEL_DIR)
    parser.add_argument("--lora-dir", default=LORA_DIR)
    parser.add_argument("--data-root", default=str(DATA_ROOT))
    parser.add_argument("--labels-name", default="vlm_labels.jsonl")
    args = parser.parse_args()

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    from transformers import VideoMAEForVideoClassification
    from peft import PeftModel
    base = VideoMAEForVideoClassification.from_pretrained(args.model_dir, local_files_only=True)
    base.to(device)
    model = PeftModel.from_pretrained(base, args.lora_dir)
    model.to(device)
    model.eval()

    labels = [json.loads(l) for l in
              (Path(args.data_root) / args.labels_name).read_text(encoding="utf-8").splitlines() if l.strip()]
    random.seed(42)
    samples = random.sample(labels, 300)
    print(f"调优集: {len(samples)} 条 (VLM 一致性)")

    probs_list: List[np.ndarray] = []
    truths: List[int] = []
    for s in samples:
        coarse = COARSE_MAP.get(s["movement_label"])
        if coarse is None:
            continue
        p = get_probs(model, s["clip_path"], device)
        if p is None:
            continue
        probs_list.append(p)
        truths.append(COARSE_LABELS.index(coarse))
    P = np.stack(probs_list)  # (n, 4)
    y = np.array(truths)
    print(f"有效: {len(y)} 条 | 类分布: {dict(zip(COARSE_LABELS, np.bincount(y, minlength=4).tolist()))}")

    # 基线: argmax
    argmax_pred = P.argmax(1)
    base_acc = float((argmax_pred == y).mean())
    print(f"基线 argmax acc: {base_acc:.4f}")

    # 网格搜索逐类阈值 (0.05-0.80, 步长 0.05)
    best = (base_acc, None, None)
    grid = np.arange(0.05, 0.81, 0.05)
    majority = int(np.bincount(y, minlength=4).argmax())
    import itertools
    for thresh in itertools.product(grid, repeat=4):
        preds = []
        for p in P:
            above = np.where(p >= np.array(thresh))[0]
            if len(above) == 0:
                preds.append(majority)
            else:
                preds.append(int(above[np.argmax(p[above])]))
        acc = float((np.array(preds) == y).mean())
        if acc > best[0]:
            best = (acc, thresh, np.array(preds))
    print(f"阈值调优后 acc: {best[0]:.4f} (阈值 {best[1]}, 提升 {best[0] - base_acc:+.4f})")

    # 保存阈值 (A5 接入用)
    out = Path(__file__).resolve().parent / "thresholds_tuned.json"
    out.write_text(json.dumps(
        {"coarse_labels": COARSE_LABELS,
         "thresholds": {COARSE_LABELS[i]: round(float(best[1][i]), 3) for i in range(4)},
         "majority_fallback": COARSE_LABELS[majority],
         "tuned_on": "300-sample VLM consistency",
         "argmax_acc": round(base_acc, 4),
         "tuned_acc": round(best[0], 4)}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"阈值已保存 -> {out}")

    # 每类精度 (调优后)
    preds = best[2]
    for i, l in enumerate(COARSE_LABELS):
        mask = y == i
        if mask.sum():
            print(f"  {l:8s} n={int(mask.sum()):3d} acc={float((preds[mask] == i).mean()):.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
