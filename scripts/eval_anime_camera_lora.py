#!/usr/bin/env python3
"""
Step 4 A5 (评估部分): LoRA 微调模型 vs 基座 VideoMAE vs 光流规则 三方对照

盲评集 1 (人工复核): human_review_queue.jsonl 的 64 条 (用户肉眼复核, 运镜标签
  多数确认为正确 → 可当 human-confirmed 盲评集)
盲评集 2 (VLM 一致性): vlm_labels.jsonl 随机抽 N 条 (衡量模型是否学到了 VLM 的
  判定, 以及基座→LoRA 的提升幅度)

输出: models/output/anime_camera_eval.json
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.torch_runtime import get_device, infer_ctx  # noqa: E402
from scripts.train_anime_camera_lora import COARSE_LABELS, COARSE_MAP, IMG_SIZE, NUM_FRAMES  # noqa: E402

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
    if frames.shape[0] < NUM_FRAMES:
        rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
        frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
    return frames


def predict(model, processor, clip: str, device) -> int:
    import torch
    from torchvision.transforms import v2
    frames = load_frames(clip)
    if frames is None:
        return -1
    frames = v2.Resize((IMG_SIZE, IMG_SIZE))(torch.from_numpy(frames))
    inputs = processor([frames], return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with infer_ctx(device):
        out = model(**inputs)
    return int(out.logits.argmax(dim=1)[0].item())


def rule_predict(clip: str) -> int:
    """光流规则 → 粗 4 类索引 (规则 13 类映射)。"""
    from core.camera_movement_classifier import classify_video
    r = classify_video(clip)
    d = r.get("dominant", "unknown")
    coarse = COARSE_MAP.get(d, None)
    if coarse is None:
        return -1
    return COARSE_LABELS.index(coarse)


def eval_set(samples: list[dict[str, Any]], model, processor, device,
             use_rule: bool = False) -> dict[str, Any]:
    correct = 0
    n = 0
    cm = np.zeros((len(COARSE_LABELS), len(COARSE_LABELS)), dtype=int)
    skip = 0
    t0 = time.time()
    for s in samples:
        truth = COARSE_MAP.get(s["movement_label"])
        if truth is None:
            skip += 1
            continue
        truth_idx = COARSE_LABELS.index(truth)
        if use_rule:
            pred_idx = rule_predict(s["clip_path"])
        else:
            pred_idx = predict(model, processor, s["clip_path"], device)
        if pred_idx < 0:
            skip += 1
            continue
        if pred_idx == truth_idx:
            correct += 1
        cm[truth_idx, pred_idx] += 1
        n += 1
    per_class = {}
    for i, l in enumerate(COARSE_LABELS):
        total = int(cm[i].sum())
        per_class[l] = {
            "n": total,
            "acc": round(float(cm[i, i]) / total, 4) if total else None,
        }
    return {
        "n": n, "skip": skip,
        "acc": round(correct / n, 4) if n else 0.0,
        "per_class": per_class,
        "confusion": cm.tolist(),
        "elapsed_sec": round(time.time() - t0, 1),
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="A5 评估: LoRA vs 基座 vs 光流规则")
    parser.add_argument("--n-random", type=int, default=200, help="VLM 一致性盲评抽样数")
    parser.add_argument("--lora-dir", default=LORA_DIR, help="LoRA 适配器目录")
    parser.add_argument("--no-rule", action="store_true", help="跳过光流规则对照")
    args = parser.parse_args()

    import torch
    device = get_device()

    # 数据
    queue = [json.loads(l) for l in
             (DATA_ROOT / "human_review_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    labels = [json.loads(l) for l in
              (DATA_ROOT / "vlm_labels.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    random.seed(42)
    rand_sample = random.sample(labels, min(args.n_random, len(labels)))

    # 模型: 必须分开加载! PeftModel.from_pretrained(base,...) 会原地给 base 注入
    # 适配器, 导致 base 也变成 LoRA 模型 (上次评估 base==lora 的假对比就是这原因)
    from transformers import VideoMAEForVideoClassification, VideoMAEImageProcessor
    processor = VideoMAEImageProcessor.from_pretrained(MODEL_DIR, local_files_only=True)
    base = VideoMAEForVideoClassification.from_pretrained(MODEL_DIR, local_files_only=True)
    base.to(device)
    base.eval()

    # 先跑基座, 再单独加载一份做 LoRA
    report = {"coarse_labels": COARSE_LABELS}
    print("=== 盲评集 1: 人工复核 64 条 (注意: 60 条为 complex, 粗4类仅4条有效) ===")
    report["human_queue"] = {
        "base": eval_set(queue, base, processor, device),
    }
    if not args.no_rule:
        report["human_queue"]["rule"] = eval_set(queue, None, None, device, use_rule=True)
    for name, r in report["human_queue"].items():
        print(f"  {name:6s} acc={r['acc']:.4f} (n={r['n']}, skip={r['skip']}) "
              f"per_class={r['per_class']}")

    print(f"=== 盲评集 2: VLM 一致性抽样 {len(rand_sample)} 条 ===")
    report["vlm_sample"] = {
        "base": eval_set(rand_sample, base, processor, device),
    }
    if not args.no_rule:
        report["vlm_sample"]["rule"] = eval_set(rand_sample, None, None, device, use_rule=True)

    # LoRA: 新开一个独立模型实例加载适配器
    lora_base = VideoMAEForVideoClassification.from_pretrained(MODEL_DIR, local_files_only=True)
    lora_base.to(device)
    from peft import PeftModel
    lora = PeftModel.from_pretrained(lora_base, args.lora_dir)
    lora.to(device)
    lora.eval()
    report["human_queue"]["lora"] = eval_set(queue, lora, processor, device)
    report["vlm_sample"]["lora"] = eval_set(rand_sample, lora, processor, device)

    for section in ("human_queue", "vlm_sample"):
        print(f"--- {section} 完整对照 ---")
        for name, r in report[section].items():
            print(f"  {name:6s} acc={r['acc']:.4f} (n={r['n']}, skip={r['skip']}) "
                  f"per_class={r['per_class']}")

    out = PROJECT_ROOT / "models" / "output" / "anime_camera_eval.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告 -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
