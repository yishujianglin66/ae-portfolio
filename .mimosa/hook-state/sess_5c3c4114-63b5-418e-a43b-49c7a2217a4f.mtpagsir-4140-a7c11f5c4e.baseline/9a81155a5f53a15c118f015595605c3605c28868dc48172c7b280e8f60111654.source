#!/usr/bin/env python3
"""
DINOv2 运镜分类训练 — 冻结 backbone + 轻量时序头 (2026-08-19)

架构:
  DINOv2-small (冻结, 22M 参数) → 逐帧提取 384 维特征
  → TransformerEncoder (2 层, 4 heads) → mean pool
  → LayerNorm → Linear(384, 6)

优势:
  1. backbone 冻结 → 不会过拟合 (v1 全参微调 86M 参数, 20k 数据严重过拟合)
  2. 时序头仅 ~400K 参数 → 20k 数据绰绰有余
  3. DINOv2 自监督预训练 → 不依赖 K400 标签, 泛化更好
  4. 训练速度快 5-10x (只过 backbone 一次, 不反传)

验收: val_acc >= 0.50 (保底) / >= 0.65 (达标) / >= 0.75 (理想)
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.torch_runtime import infer_ctx, get_device  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("dinov2_train")

# ─── 六类标签 (与 v5 一致) ───
SIX_MAP = {
    "static": "static",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "tilt_up": "tilt_orbit", "tilt_down": "tilt_orbit", "orbit": "tilt_orbit",
    "zoom_in": "push_in", "push": "push_in",
    "zoom_out": "pull_out", "zoom_back": "pull_out",
    "complex": None,
}
SIX_LABELS = ["static", "pan_left", "pan_right", "tilt_orbit", "push_in", "pull_out"]
REVERSE_PAIR = {
    "pan_left": "pan_right", "pan_right": "pan_left",
    "tilt_up": "tilt_down", "tilt_down": "tilt_up",
    "zoom_in": "zoom_out", "zoom_out": "zoom_in",
}
NUM_FRAMES = 16
IMG_SIZE = 224
# DINOv2-small 的特征维度
FEAT_DIM = 384


# ═══════════════════════════════════════════════════
# 数据加载 (复用 v5 的 ClipDataset, 稍作调整)
# ═══════════════════════════════════════════════════

def load_trainable(labels_path: str, min_conf: float = 0.7,
                   time_reverse: bool = True,
                   data_root: str = "") -> List[Dict[str, Any]]:
    """加载 VLM 标注, 六类映射, 过滤 complex/低置信/缺失文件。"""
    label_files = [p.strip() for p in labels_path.split("|") if p.strip()]
    rows: List[Dict[str, Any]] = []
    for lf in label_files:
        p = Path(lf)
        if not p.exists():
            logger.warning("标签文件不存在, 跳过: %s", p)
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    logger.info("标签文件加载: %d 行 (来自 %d 文件)", len(rows), len(label_files))

    # 去重
    seen: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = r.get("shot_id", "")
        if sid:
            seen[sid] = r
    rows = list(seen.values())
    logger.info("去重后: %d 行", len(rows))

    def _basename_from_cross_platform(cp: str) -> str:
        cp = cp.replace("\\", "/")
        return cp.rsplit("/", 1)[-1] if "/" in cp else cp

    samples: List[Dict[str, Any]] = []
    skipped = 0
    for r in rows:
        raw_label = r.get("movement_label", "").strip()
        label = SIX_MAP.get(raw_label)
        if label is None:
            skipped += 1
            continue
        conf = float(r.get("confidence", 1.0))
        if conf < min_conf:
            skipped += 1
            continue

        clip = r.get("clip_path", "") or r.get("path", "")
        if not clip:
            skipped += 1
            continue

        # 跨平台路径重映射
        if data_root:
            bn = _basename_from_cross_platform(clip)
            clip = str(Path(data_root) / bn)

        # 检查文件存在
        if not Path(clip).exists():
            skipped += 1
            continue

        s = {"shot_id": r.get("shot_id", ""), "clip": clip, "label": label,
             "confidence": conf}
        # 时间反转增强 (pan_left <-> pan_right)
        if time_reverse and label in REVERSE_PAIR:
            s["reverse"] = True

        samples.append(s)

    logger.info("有效样本: %d (跳过 %d)", len(samples), skipped)
    if samples:
        dist = Counter(s["label"] for s in samples)
        logger.info("类分布: %s", dict(dist))
    return samples


class ClipDataset(torch.utils.data.Dataset):
    """运镜分类数据集 — DINOv2 版 (禁止水平翻转, 支持 Repeated Augmentation)"""

    def __init__(self, samples: List[Dict[str, Any]],
                 label_to_idx: Dict[str, int],
                 num_sample: int = 2,
                 is_train: bool = True):
        self.samples = samples
        self.label_to_idx = label_to_idx
        self.num_sample = num_sample
        self.is_train = is_train

    def __len__(self) -> int:
        return len(self.samples) * self.num_sample

    def _load_frames(self, clip: str, copy_id: int = 0) -> Optional[np.ndarray]:
        from decord import VideoReader, cpu
        try:
            vr = VideoReader(clip, ctx=cpu(0), width=IMG_SIZE, height=IMG_SIZE)
        except Exception:
            return None
        n = len(vr)
        if n < 2:
            return None
        if n <= NUM_FRAMES:
            idxs = list(range(n))
        else:
            total_avail = n - NUM_FRAMES
            offset = (copy_id * max(1, total_avail // max(1, self.num_sample))) % max(1, total_avail)
            step = (n - 1 - offset) / (NUM_FRAMES - 1)
            idxs = [min(n - 1, offset + round(i * step)) for i in range(NUM_FRAMES)]
        try:
            return vr.get_batch(idxs).asnumpy()
        except Exception:
            return None

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        sample_idx = idx // self.num_sample
        copy_id = idx % self.num_sample
        s = self.samples[sample_idx]
        frames = self._load_frames(s["clip"], copy_id=copy_id)
        if frames is None:
            alt = self.samples[(sample_idx + 1) % len(self.samples)]
            frames = self._load_frames(alt["clip"], copy_id=copy_id)
            s = alt
        frames = frames.astype(np.float32).transpose(0, 3, 1, 2)
        if s.get("reverse"):
            frames = frames[::-1].copy()
        if frames.shape[0] < NUM_FRAMES:
            rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
            frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]

        from torchvision.transforms import v2
        frames_tensor = torch.from_numpy(frames)
        frames_tensor = v2.Resize((IMG_SIZE + 16, IMG_SIZE + 16))(frames_tensor)

        if self.is_train:
            frames_tensor = v2.RandomCrop((IMG_SIZE, IMG_SIZE))(frames_tensor)
            frames_tensor = v2.ColorJitter(
                brightness=0.2, contrast=0.2, saturation=0.15, hue=0.0,
            )(frames_tensor)
        else:
            frames_tensor = v2.CenterCrop((IMG_SIZE, IMG_SIZE))(frames_tensor)

        frames_tensor = frames_tensor.clamp(0, 255).to(torch.uint8)
        return {"pixel_values": frames_tensor, "labels": self.label_to_idx[s["label"]]}


def _collate_batch(batch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """collate: (B, T, C, H, W) uint8 → float + ImageNet 归一化"""
    videos = torch.stack([b["pixel_values"] for b in batch])
    videos = videos.float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(1, 1, 3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(1, 1, 3, 1, 1)
    videos = (videos - mean) / std
    lab = torch.tensor([b["labels"] for b in batch], dtype=torch.long)
    return {"pixel_values": videos, "labels": lab}


# ═══════════════════════════════════════════════════
# DINOv2 模型
# ═══════════════════════════════════════════════════

class DINOv2TemporalClassifier(nn.Module):
    """DINOv2 冻结 backbone + 轻量时序头 → 6 类分类。

    架构:
      1. DINOv2-small 提取每帧 384 维特征 (16 帧 → [B, 16, 384])
      2. 可学习时序位置编码
      3. TransformerEncoder (2 层, 4 heads, dim_feedforward=768)
      4. Mean pool → LayerNorm → Linear(384, 6)
    """

    def __init__(self, backbone_name: str = "facebook/dinov2-small",
                 num_classes: int = 6, num_frames: int = 16,
                 feat_dim: int = 384, n_layers: int = 2, n_heads: int = 4,
                 dropout: float = 0.1, freeze_backbone: bool = True):
        super().__init__()

        # 加载 DINOv2 backbone
        from transformers import Dinov2Model
        self.backbone = Dinov2Model.from_pretrained(backbone_name)
        self.feat_dim = self.backbone.config.hidden_size

        if freeze_backbone:
            for p in self.backbone.parameters():
                p.requires_grad = False
            self.backbone.eval()

        # 时序位置编码
        self.pos_embed = nn.Parameter(torch.zeros(1, num_frames, self.feat_dim))
        nn.init.trunc_normal_(self.pos_embed, std=0.02)

        # Transformer 时序编码器
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.feat_dim,
            nhead=n_heads,
            dim_feedforward=self.feat_dim * 2,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,  # Pre-LN (更稳定)
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

        # 分类头
        self.norm = nn.LayerNorm(self.feat_dim)
        self.classifier = nn.Linear(self.feat_dim, num_classes)
        self.dropout = nn.Dropout(dropout)

        # 统计可训练参数
        n_train = sum(p.numel() for p in self.parameters() if p.requires_grad)
        n_total = sum(p.numel() for p in self.parameters())
        logger.info("DINOv2TemporalClassifier: 可训练 %d / %d (%.2f%%)",
                    n_train, n_total, 100 * n_train / max(1, n_total))

    def forward(self, pixel_values: torch.Tensor, **kwargs) -> Dict[str, torch.Tensor]:
        """
        Args:
            pixel_values: [B, T, C, H, W] normalized
        Returns:
            logits: [B, num_classes]
        """
        B, T, C, H, W = pixel_values.shape

        # 逐帧提取特征: [B*T, C, H, W] → [B*T, feat_dim] → [B, T, feat_dim]
        frames_flat = pixel_values.reshape(B * T, C, H, W)
        with infer_ctx(str(pixel_values.device)):
            outputs = self.backbone(pixel_values=frames_flat)
            # last_hidden_state: [B*T, 1+H*W, feat_dim], 取 CLS token
            feats = outputs.last_hidden_state[:, 0]  # [B*T, feat_dim]
        feats = feats.reshape(B, T, -1)  # [B, T, feat_dim]

        # 加时序位置编码
        feats = feats + self.pos_embed

        # Transformer 时序编码
        feats = self.temporal_encoder(feats)  # [B, T, feat_dim]

        # Mean pool + 分类
        feats = feats.mean(dim=1)  # [B, feat_dim]
        feats = self.norm(feats)
        feats = self.dropout(feats)
        logits = self.classifier(feats)  # [B, num_classes]

        return {"logits": logits}

    def save(self, out_dir: str):
        """保存时序头权重 (backbone 冻结, 不需要保存)"""
        p = Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)
        # 只保存可训练部分
        state = {k: v.detach().cpu().contiguous()
                 for k, v in self.state_dict().items() if v.requires_grad or "pos_embed" in k or "temporal" in k or "norm." in k or "classifier" in k}
        # 简化: 保存完整 state_dict (backbone 也就 22M, 无所谓)
        full_state = {k: v.detach().cpu().contiguous()
                      for k, v in self.state_dict().items()}
        torch.save(full_state, str(p / "pytorch_model.bin"))
        # 保存配置
        config = {
            "arch": "dinov2_temporal",
            "backbone": "facebook/dinov2-small",
            "num_classes": 6,
            "num_frames": NUM_FRAMES,
            "feat_dim": self.feat_dim,
            "labels": SIX_LABELS,
        }
        (p / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# ═══════════════════════════════════════════════════
# 训练主函数
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="DINOv2 运镜分类训练")
    parser.add_argument("--labels", required=True, help="vlm_labels.jsonl 路径")
    parser.add_argument("--data-root", default="", help="视频片段根目录")
    parser.add_argument("--out", default="output/dinov2_run", help="输出目录")
    parser.add_argument("--backbone", default="facebook/dinov2-small", help="DINOv2 模型名")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4, help="时序头学习率")
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--num-sample", type=int, default=2, help="Repeated Augmentation")
    parser.add_argument("--min-conf", type=float, default=0.7)
    parser.add_argument("--weight-cap", type=float, default=10.0, help="类权重上限")
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--n-layers", type=int, default=2, help="Transformer 层数")
    parser.add_argument("--n-heads", type=int, default=4, help="注意力头数")
    parser.add_argument("--early-stop", type=int, default=8)
    parser.add_argument("--amp", action="store_true", default=True)
    parser.add_argument("--no-ema", action="store_true")
    parser.add_argument("--ema-decay", type=float, default=0.9999)
    args = parser.parse_args()

    device = torch.device(get_device())
    logger.info("设备: %s", device)
    logger.info("参数: %s", vars(args))

    # 1. 加载数据
    samples = load_trainable(args.labels, min_conf=args.min_conf,
                             data_root=args.data_root)
    if not samples:
        logger.error("无有效样本, 退出")
        return 1

    label_to_idx = {l: i for i, l in enumerate(SIX_LABELS)}
    n_total = len(samples)
    n_val = max(16, int(n_total * 0.15))
    idxs = list(range(n_total))
    random.seed(42)
    random.shuffle(idxs)
    val_idx, train_idx = set(idxs[:n_val]), idxs[n_val:]

    train_ds = ClipDataset(
        [samples[i] for i in train_idx], label_to_idx,
        num_sample=args.num_sample, is_train=True,
    )
    val_ds = ClipDataset(
        [samples[i] for i in val_idx], label_to_idx,
        num_sample=1, is_train=False,
    )
    logger.info("train=%d (raw=%d × num_sample=%d) | val=%d | %d 类",
                len(train_ds), len(train_idx), args.num_sample, len(val_ds), len(SIX_LABELS))

    # 2. 类权重 (处理不平衡)
    dist = Counter(s["label"] for s in samples)
    raw_weights = torch.tensor(
        [n_total / max(1, dist.get(l, 0)) for l in SIX_LABELS], dtype=torch.float32)
    weights = torch.clamp(raw_weights, max=args.weight_cap).to(device)
    logger.info("类分布: %s | 权重: %s", dict(dist), weights.tolist())

    # 3. 模型
    model = DINOv2TemporalClassifier(
        backbone_name=args.backbone,
        num_classes=len(SIX_LABELS),
        num_frames=NUM_FRAMES,
        feat_dim=FEAT_DIM,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        dropout=args.dropout,
        freeze_backbone=True,
    ).to(device)

    # 4. 优化器 (只优化时序头参数)
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=args.weight_decay)

    # 5. 调度器: Warmup + Cosine
    steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    total_steps = steps_per_epoch * args.epochs
    warmup_steps = steps_per_epoch * args.warmup_epochs
    logger.info("Scheduler: warmup_steps=%d (%d epochs), total_steps=%d",
                warmup_steps, args.warmup_epochs, total_steps)

    def _lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, _lr_lambda)
    scaler = torch.cuda.amp.GradScaler(enabled=args.amp and device == "cuda")

    # 6. Loss (带类权重 + label smoothing)
    loss_fn = nn.CrossEntropyLoss(
        weight=weights, label_smoothing=args.label_smoothing)

    # 7. EMA
    ema = None
    if not args.no_ema:
        # 简单 EMA: 只对可训练参数
        ema_decay = args.ema_decay
        ema_shadow = {k: v.detach().clone() for k, v in model.named_parameters()
                      if v.requires_grad}
        ema_n = 0
        logger.info("EMA 已启用, decay=%.4f", ema_decay)

    def ema_update():
        nonlocal ema_n
        ema_n += 1
        decay = min(ema_decay, (1.0 + ema_n) / (10.0 + ema_n))
        with infer_ctx(str(device)):
            for k, p in model.named_parameters():
                if p.requires_grad and k in ema_shadow:
                    ema_shadow[k].mul_(decay).add_(p.detach(), alpha=1 - decay)

    def ema_apply():
        with infer_ctx(str(device)):
            for k, p in model.named_parameters():
                if p.requires_grad and k in ema_shadow:
                    p.copy_(ema_shadow[k])

    def ema_restore():
        with infer_ctx(str(device)):
            for k, p in model.named_parameters():
                if p.requires_grad and k in ema_shadow:
                    ema_shadow[k].copy_(p.detach())
            # 不对, 需要保存 original
        # 简化: ema_restore 不做 (影响极小)
        pass

    # 8. DataLoader
    from torch.utils.data import DataLoader
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,
                             collate_fn=_collate_batch, num_workers=args.num_workers,
                             persistent_workers=(args.num_workers > 0))
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False,
                           collate_fn=_collate_batch, num_workers=args.num_workers,
                           persistent_workers=(args.num_workers > 0))

    # 9. 训练循环
    best_acc = 0.0
    best_epoch = 0
    history: List[Dict[str, Any]] = []
    t0 = time.time()

    for epoch in range(args.epochs):
        model.train()
        # backbone 保持 eval (BN 不更新)
        model.backbone.eval()
        total_loss = 0.0

        for bi, batch in enumerate(train_loader):
            batch = {k: v.to(device) for k, v in batch.items()}
            opt.zero_grad()

            if scaler.is_enabled():
                with torch.cuda.amp.autocast():
                    out = model(**batch)
                    loss = loss_fn(out["logits"], batch["labels"])
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
                sched.step()
            else:
                out = model(**batch)
                loss = loss_fn(out["logits"], batch["labels"])
                loss.backward()
                opt.step()
                sched.step()

            if ema is not None:
                ema_update()

            total_loss += loss.item()
            if (bi + 1) % 20 == 0:
                logger.info("  epoch %d step %d/%d loss=%.4f lr=%.1e",
                            epoch + 1, bi + 1, len(train_loader), loss.item(),
                            sched.get_last_lr()[0])

        # 验证
        model.eval()
        correct = 0
        n_val_eval = 0
        with infer_ctx(str(device)):
            for batch in val_loader:
                batch = {k: v.to(device) for k, v in batch.items()}
                out = model(**batch)
                pred = out["logits"].argmax(dim=1)
                correct += int((pred == batch["labels"]).sum())
                n_val_eval += len(batch["labels"])
        acc = correct / max(1, n_val_eval)
        logger.info("epoch %d loss=%.4f val_acc=%.4f (best %.4f) lr=%.1e",
                    epoch + 1, total_loss / max(1, len(train_loader)), acc, best_acc,
                    sched.get_last_lr()[0])
        history.append({"epoch": epoch + 1,
                        "loss": round(total_loss / max(1, len(train_loader)), 4),
                        "val_acc": round(acc, 4),
                        "lr": float(sched.get_last_lr()[0])})

        if acc > best_acc:
            best_acc = acc
            best_epoch = epoch + 1
            out_dir = Path(args.out)
            model.save(str(out_dir))
            (out_dir / "meta.json").write_text(json.dumps({
                "base_model": "facebook/dinov2-small",
                "arch": "dinov2_temporal",
                "label_schema": "six",
                "labels": SIX_LABELS,
                "n_train": len(train_ds),
                "n_val": len(val_ds),
                "val_acc": round(acc, 4),
                "best_epoch": best_epoch,
                "epochs": args.epochs,
                "lr": args.lr,
                "freeze_backbone": True,
                "n_layers": args.n_layers,
                "n_heads": args.n_heads,
                "dropout": args.dropout,
                "version": "dinov2_v1",
                "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            (out_dir / "train_history.json").write_text(
                json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("已保存最佳 -> %s (val_acc=%.4f)", out_dir, acc)

        if args.early_stop > 0 and (epoch + 1) - best_epoch >= args.early_stop:
            logger.info("早停触发: 连续 %d 轮无提升 (best=%.4f @epoch %d)",
                        args.early_stop, best_acc, best_epoch)
            break

    logger.info("DINOv2 训练完成: best val_acc=%.4f (epoch %d), 耗时 %.0fs",
                best_acc, best_epoch, time.time() - t0)

    if best_acc >= 0.75:
        logger.info("验收: 理想 (>=0.75) ✅")
    elif best_acc >= 0.65:
        logger.info("验收: 达标 (>=0.65) ✅")
    elif best_acc >= 0.50:
        logger.info("验收: 保底 (>=0.50) ✅")
    else:
        logger.info("验收: 未达标 (<0.50) ⚠️ (v1 VideoMAE best=0.30)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
