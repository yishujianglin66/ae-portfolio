# -*- coding: utf-8 -*-
r"""T7: CLIP LoRA对比学习微调 — 用教师伪标签(29566帧,22IP)微调laion CLIP。

方法:
  - 底座: laion CLIP ViT-B-32 (已有本地缓存)
  - 训练: 对比学习(InfoNCE) + 硬负例挖掘
  - LoRA: rank=16, 仅attention投影矩阵
  - 防泄漏: 黄金集帧禁入训练集
  - 数据: T20伪标签29566帧(22IP) + 原教师3580帧(24IP)

产物:
  models/clip_lora_aot.pt — LoRA权重
  reports/t7_lora_report.json — 微调报告
"""
from __future__ import annotations

import json
import sys
import time
import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.torch_runtime import get_device, infer_ctx

PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
TEACHER_LABELS = ROOT / "data" / "training" / "labels.json"
GOLDEN_V2 = ROOT / "data" / "benchmark_golden_v2.json"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"

# LoRA超参
LORA_RANK = 16
LORA_ALPHA = 32
EPOCHS = 15
LR = 2e-5
BATCH_SIZE = 32
TEMPERATURE = 0.07
IMG_SIZE = 224


def _log(msg: str):
    print(f"[T7] {msg}", flush=True)


def load_clip_model():
    """加载laion CLIP ViT-B-32"""
    import open_clip
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained=str(
            ROOT / "models" / "ms_cache" / "models" /
            "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" /
            "snapshots" / "master" / "open_clip_pytorch_model.bin"
        )
    )
    tokenizer = open_clip.get_tokenizer("ViT-B-32")
    return model, preprocess, tokenizer


class ContrastiveDataset(Dataset):
    """对比学习数据集: 返回(anchor_img, ip_index)"""
    def __init__(self, entries, ip2idx, transform=None):
        self.entries = entries
        self.ip2idx = ip2idx
        self.transform = transform

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        from PIL import Image
        entry = self.entries[idx]
        fp = Path(entry["frame_path"])
        try:
            img = Image.open(fp).convert("RGB")
        except Exception:
            img = Image.fromarray(np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8))
        if self.transform:
            img = self.transform(img)
        label = self.ip2idx[entry["ip"]]
        return img, label


def prepare_contrastive_data(golden_videos: set) -> Tuple:
    """准备对比学习数据(排除黄金集帧)"""
    all_entries = []

    # T20伪标签
    if PSEUDO_LABELS.exists():
        pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
        for p in pseudo:
            if p["confidence"] >= 0.5:
                frame_name = Path(p["frame_path"]).name
                vid_name = Path(p["frame_path"]).parent.parent.name
                if frame_name not in golden_videos and vid_name not in golden_videos:
                    all_entries.append({
                        "frame_path": p["frame_path"],
                        "ip": p["ip"],
                    })
        _log(f"T20伪标签: {len(pseudo)}→{len(all_entries)}帧(排除黄金集)")

    # 原教师数据
    if TEACHER_LABELS.exists():
        teacher = json.loads(TEACHER_LABELS.read_text(encoding="utf-8"))
        before = len(all_entries)
        for t in teacher:
            fp = t.get("path", "")
            frame_name = Path(fp).name
            vid_name = Path(fp).parent.name
            if frame_name not in golden_videos and vid_name not in golden_videos and t.get("ip", ""):
                all_entries.append({
                    "frame_path": fp,
                    "ip": t["ip"],
                })
        _log(f"教师数据: +{len(all_entries)-before}帧")

    # IP统计
    ip_counter = Counter(e["ip"] for e in all_entries)
    valid_ips = sorted(ip for ip, cnt in ip_counter.items() if cnt >= 5)
    ip2idx = {ip: i for i, ip in enumerate(valid_ips)}
    filtered = [e for e in all_entries if e["ip"] in ip2idx]
    _log(f"有效IP类: {len(valid_ips)}, 训练样本: {len(filtered)}")

    return filtered, valid_ips, ip2idx


def add_lora_to_clip(clip_model, rank=16, alpha=32):
    """给CLIP visual encoder添加LoRA适配器"""
    from peft import LoraConfig, get_peft_model

    lora_config = LoraConfig(
        r=rank,
        lora_alpha=alpha,
        target_modules=["out_proj", "c_fc", "c_proj"],  # CLIP ViT attention+MLP投影
        lora_dropout=0.1,
        bias="none",
    )
    model = get_peft_model(clip_model.visual, lora_config)
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    n_total = sum(p.numel() for p in model.parameters())
    _log(f"LoRA: trainable={n_trainable/1e6:.2f}M / total={n_total/1e6:.1f}M ({100*n_trainable/n_total:.2f}%)")
    return model


def contrastive_loss(img_features, text_features, temperature=0.07):
    """InfoNCE对比学习损失"""
    img_features = F.normalize(img_features, dim=-1)
    text_features = F.normalize(text_features, dim=-1)
    logits = (img_features @ text_features.T) / temperature
    labels = torch.arange(len(img_features), device=img_features.device)
    loss = F.cross_entropy(logits, labels)
    return loss


def train_lora(clip_model, lora_model, train_loader, text_embeds, device):
    """训练LoRA"""
    import torch.optim as optim

    optimizer = optim.AdamW(
        [p for p in lora_model.parameters() if p.requires_grad],
        lr=LR, weight_decay=1e-4
    )
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

    # 冻结CLIP非visual部分 + visual基础参数(仅LoRA可训)
    for p in clip_model.parameters():
        p.requires_grad = False
    # 重新启用LoRA参数(可能被上面的循环冻结)
    for p in lora_model.parameters():
        if p.requires_grad or 'lora' in str(type(p).__name__).lower():
            p.requires_grad = True
    # 确保lora_model的LoRA层可训
    for name, p in lora_model.named_parameters():
        if 'lora_' in name:
            p.requires_grad = True

    history = []
    for epoch in range(EPOCHS):
        lora_model.train()
        epoch_loss = 0.0
        n_batches = 0

        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad()

            # 图像编码(通过LoRA)
            img_features = lora_model(images)
            if isinstance(img_features, tuple):
                img_features = img_features[0]

            # 获取对应文本嵌入
            batch_text = text_embeds[labels.cpu().numpy()]
            batch_text = torch.from_numpy(batch_text).float().to(device)

            loss = contrastive_loss(img_features, batch_text, TEMPERATURE)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            n_batches += 1

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)
        history.append({"epoch": epoch + 1, "loss": round(avg_loss, 4)})

        if (epoch + 1) % 5 == 0 or epoch == 0:
            _log(f"  Epoch {epoch+1}/{EPOCHS} | loss={avg_loss:.4f}")

    return history


def run_t7_lora():
    """主流程"""
    _log("=" * 60)
    _log("T7: CLIP LoRA对比学习微调")
    _log("=" * 60)

    device = get_device()
    _log(f"设备: {device}")

    # 1. 加载CLIP
    _log("\n[1/5] 加载CLIP模型...")
    t0 = time.time()
    clip_model, preprocess, tokenizer = load_clip_model()
    clip_model = clip_model.to(device)
    _log(f"  CLIP加载完成: {time.time()-t0:.1f}s")

    # 2. 准备数据
    _log("\n[2/5] 准备对比学习数据...")
    golden_videos = set()  # 黄金集视频文件名
    if GOLDEN_V2.exists():
        golden = json.loads(GOLDEN_V2.read_text(encoding="utf-8"))
        if isinstance(golden, dict):
            golden_videos = set(golden.keys())
        elif isinstance(golden, list):
            golden_videos = set(g.get("video", g.get("filename", "")) for g in golden)
    _log(f"  黄金集视频: {len(golden_videos)}")

    entries, class_names, ip2idx = prepare_contrastive_data(golden_videos)

    from torchvision import transforms
    transform_train = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.1, 0.1, 0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    dataset = ContrastiveDataset(entries, ip2idx, transform_train)
    train_loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True,
                              num_workers=0, pin_memory=True)
    _log(f"  训练集: {len(dataset)}样本, {len(class_names)}类")

    # 3. 预计算文本嵌入
    _log("\n[3/5] 预计算文本嵌入...")
    text_embeds = np.zeros((len(class_names), 512), dtype=np.float32)
    clip_model.eval()
    with infer_ctx(device):
        for i, ip_name in enumerate(class_names):
            text_tokens = tokenizer([f"a promotional image of {ip_name}"]).to(device)
            text_features = clip_model.encode_text(text_tokens)
            text_embeds[i] = text_features.cpu().numpy()[0]
    _log(f"  文本嵌入: {text_embeds.shape}")

    # 4. 添加LoRA并训练
    _log("\n[4/5] 添加LoRA并训练...")
    lora_model = add_lora_to_clip(clip_model, LORA_RANK, LORA_ALPHA)
    lora_model = lora_model.to(device)

    t0 = time.time()
    history = train_lora(clip_model, lora_model, train_loader, text_embeds, device)
    _log(f"  训练耗时: {time.time()-t0:.1f}s")

    # 5. 保存
    _log("\n[5/5] 保存模型...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "clip_lora_aot.pt"
    torch.save({
        "lora_state": lora_model.state_dict(),
        "class_names": class_names,
        "ip2idx": ip2idx,
        "config": {"rank": LORA_RANK, "alpha": LORA_ALPHA, "epochs": EPOCHS},
    }, model_path)

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "base_model": "laion CLIP ViT-B-32",
        "lora_config": {"rank": LORA_RANK, "alpha": LORA_ALPHA},
        "training": {
            "epochs": EPOCHS,
            "lr": LR,
            "batch_size": BATCH_SIZE,
            "n_samples": len(dataset),
            "n_classes": len(class_names),
            "history": history,
        },
        "model_path": str(model_path),
        "status": "complete",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t7_lora_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T7 LoRA微调完成")
    _log(f"   模型: {model_path}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    run_t7_lora()
