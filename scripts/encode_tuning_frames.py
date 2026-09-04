"""encode_tuning_frames.py — 调参器帧库 → CLIP 嵌入固化

CNN 深度调参器数据地基: 把 data/param_tuning/frames/{sample}/frame_*.jpg
用冻结的 open_clip ViT-L-14 编码成 768 维嵌入, 存 .npz 供评分头训练/推理复用
(编码一次, 训练/推理都不要再碰视觉模型)。

输入: output/m2_iteration/train_samples.jsonl (带 frame_dir 的行)
输出: data/param_tuning/clip_vitl14_emb.npz
  emb      [N, 768]   每样本 4 帧嵌入的均值 (L2 归一化)
  sample_idx [N]      对应 jsonl 中带帧样本的行号 (用于对齐评分标签)

用法:
  python scripts/encode_tuning_frames.py [--clean]
  --clean: 只编码"帧↔参数唯一对齐"的干净样本 (读 data/param_tuning/clean_index.json),
           排除旧批次覆盖写导致的共享帧目录样本 (帧↔参数错位, 2026-08-16 审计发现)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.torch_runtime import infer_ctx, get_device  # noqa: E402

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
OUT = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
CLEAN_IDX = PROJECT / "data" / "param_tuning" / "clean_index.json"
CKPT = (Path.home() / ".cache/huggingface/hub/models--timm--vit_large_patch14_clip_224.openai"
        / "snapshots" / "18d0535469bb561bf468d76c1d73aa35156c922b" / "open_clip_model.safetensors")
BATCH = 16


def main() -> int:
    import open_clip

    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", action="store_true",
                    help="只编码干净对齐样本 (帧目录唯一)")
    args = ap.parse_args()

    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    idx_frames = [(i, r) for i, r in enumerate(rows) if r.get("frame_dir")]
    if args.clean:
        clean_idx = set(json.loads(CLEAN_IDX.read_text(encoding="utf-8"))["clean_row_idx"])
        idx_frames = [(i, r) for i, r in idx_frames if i in clean_idx]
        print(f"[clean] 过滤为 {len(idx_frames)} 个唯一对齐样本", file=sys.stderr)
    if not idx_frames:
        print("无带帧样本, 先跑 collect_tuning_data.py")
        return 1
    print(f"带帧样本 {len(idx_frames)} / 总 {len(rows)}")

    dev = get_device()
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-L-14", pretrained=str(CKPT), device=dev)
    model.eval()

    embs = np.zeros((len(idx_frames), model.visual.output_dim), dtype=np.float32)
    sample_idx = np.zeros(len(idx_frames), dtype=np.int64)

    for bi in range(0, len(idx_frames), BATCH):
        chunk = idx_frames[bi:bi + BATCH]
        tensors = []
        for _, r in chunk:
            frame_dir = Path(r["frame_dir"])
            fps = sorted(frame_dir.glob("frame_*.jpg"))
            if not fps:
                raise FileNotFoundError(f"帧目录为空: {frame_dir}")
            # 4 帧全部编码后取均值 (评分时 qwen 也是看 4 帧)
            for fp in fps:
                from PIL import Image
                tensors.append(preprocess(Image.open(fp).convert("RGB")))
        xs = torch.stack(tensors).to(dev)
        with infer_ctx(dev):
            feats = model.encode_image(xs)          # [chunk*4, 768]
            feats = feats / feats.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        # 每样本 4 帧均值 + 归一化
        per = feats.cpu().numpy().reshape(len(chunk), -1, feats.shape[1]).mean(axis=1)
        per = per / (np.linalg.norm(per, axis=1, keepdims=True) + 1e-8)
        embs[bi:bi + len(chunk)] = per
        sample_idx[bi:bi + len(chunk)] = [i for i, _ in chunk]
        print(f"  编码 {min(bi + BATCH, len(idx_frames))}/{len(idx_frames)}", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez(OUT, emb=embs, sample_idx=sample_idx)
    print(f"嵌入已固化: {OUT} | {embs.shape} (L2 归一化均值)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
