# -*- coding: utf-8 -*-
r"""T12: mood/scene_type本地MLP兜底分类头 — 实际训练。

用laion CLIP编码语料帧→512维嵌入, 结合T20伪标签的IP→mood/scene映射训练双头MLP。
验收: VLM缺席时两字段非空率100%, 置信上限0.6。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.torch_runtime import get_device, infer_ctx

PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
EMB_CACHE = ROOT / "cache" / "t12_clip_embs"

MOOD_CLASSES = ["calm", "building", "intense", "climax", "melancholy"]
SCENE_CLASSES = ["battle", "action", "closeup", "landscape", "indoor", "dialogue"]

# IP→mood/scene映射(从VLM缓存统计)
IP_MOOD_MAP = {
    "进击的巨人": ("intense", "battle"),
    "火影忍者": ("intense", "battle"),
    "JOJO的奇妙冒险": ("intense", "action"),
    "FATE": ("intense", "battle"),
    "鬼灭之刃": ("intense", "battle"),
    "咒术回战": ("intense", "battle"),
    "海贼王": ("building", "action"),
    "无限滑板": ("calm", "action"),
    "某科学的超电磁炮": ("building", "action"),
    "斩·赤红之瞳": ("intense", "battle"),
    "黑岩射手": ("building", "action"),
    "地缚少年花子君": ("calm", "indoor"),
    "猫和老鼠": ("calm", "action"),
    "EVA": ("melancholy", "indoor"),
    "K": ("building", "action"),
    "浪客剑心": ("intense", "battle"),
    "反复的蔷薇花瓣": ("melancholy", "landscape"),
    "犬夜叉": ("building", "action"),
    "全职猎人": ("intense", "battle"),
    "移动迷宫": ("building", "action"),
}

EPOCHS = 20
LR = 1e-3
BATCH_SIZE = 256


def _log(msg: str):
    print(f"[T12] {msg}", flush=True)


class MoodSceneClassifier(nn.Module):
    """双头MLP: CLIP嵌入(512)→共享骨干→mood(5类)+scene(6类)"""
    def __init__(self, input_dim=512, n_mood=5, n_scene=6):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.ReLU(),
        )
        self.mood_head = nn.Linear(64, n_mood)
        self.scene_head = nn.Linear(64, n_scene)

    def forward(self, x):
        feat = self.shared(x)
        return self.mood_head(feat), self.scene_head(feat)


class EmbeddingDataset(Dataset):
    def __init__(self, embeddings, mood_labels, scene_labels):
        self.embeddings = embeddings
        self.mood_labels = mood_labels
        self.scene_labels = scene_labels

    def __len__(self):
        return len(self.mood_labels)

    def __getitem__(self, idx):
        return self.embeddings[idx], self.mood_labels[idx], self.scene_labels[idx]


def compute_clip_embeddings():
    """用laion CLIP编码语料帧(采样)→512维嵌入"""
    import open_clip
    from PIL import Image
    from torchvision import transforms

    _log("加载CLIP模型...")
    ckpt_path = str(
        ROOT / "models" / "ms_cache" / "models" /
        "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" /
        "snapshots" / "master" / "open_clip_pytorch_model.bin"
    )
    model, _, preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained=ckpt_path)
    device = get_device()
    model = model.to(device)
    model.eval()

    # 加载伪标签
    pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
    _log(f"伪标签: {len(pseudo)}帧")

    # 采样(每IP最多500帧, 减少编码时间)
    ip_groups = {}
    for p in pseudo:
        ip = p["ip"]
        if ip not in ip_groups:
            ip_groups[ip] = []
        ip_groups[ip].append(p)

    sampled = []
    for ip, frames in ip_groups.items():
        np.random.seed(42)
        n = min(500, len(frames))
        indices = np.random.choice(len(frames), n, replace=False)
        sampled.extend([frames[i] for i in indices])
    _log(f"采样: {len(sampled)}帧")

    # 检查缓存
    EMB_CACHE.mkdir(parents=True, exist_ok=True)
    cache_path = EMB_CACHE / "clip_embs.npy"
    cache_meta = EMB_CACHE / "meta.json"

    if cache_path.exists():
        _log("从缓存加载嵌入...")
        data = np.load(str(cache_path))
        return data, sampled

    # 编码
    transform = transforms.Compose([
        transforms.Resize(224),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    embeddings = []
    batch_imgs = []
    t0 = time.time()

    for i, entry in enumerate(sampled):
        fp = Path(entry["frame_path"])
        try:
            img = Image.open(fp).convert("RGB")
        except Exception:
            continue
        batch_imgs.append(transform(img))

        if len(batch_imgs) >= 64 or i == len(sampled) - 1:
            batch_tensor = torch.stack(batch_imgs).to(device)
            with infer_ctx(device):
                features = model.encode_image(batch_tensor)
                features = features / features.norm(dim=-1, keepdim=True)
            embeddings.extend(features.cpu().numpy())
            batch_imgs = []

        if (i + 1) % 500 == 0:
            _log(f"  编码进度: {i+1}/{len(sampled)}, 耗时{time.time()-t0:.1f}s")

    embeddings = np.array(embeddings[:len(sampled)], dtype=np.float32)
    _log(f"编码完成: {embeddings.shape}, 耗时{time.time()-t0:.1f}s")

    np.save(str(cache_path), embeddings)
    cache_meta.write_text(json.dumps({
        "n_frames": len(sampled),
        "dim": embeddings.shape[1],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return embeddings, sampled


def train_t12(embeddings, entries):
    """训练mood/scene分类头"""
    _log("\n[2/3] 训练mood/scene分类头...")

    mood2idx = {m: i for i, m in enumerate(MOOD_CLASSES)}
    scene2idx = {s: i for i, s in enumerate(SCENE_CLASSES)}

    mood_labels = []
    scene_labels = []
    valid_indices = []

    for i, entry in enumerate(entries):
        ip = entry["ip"]
        if ip in IP_MOOD_MAP:
            mood, scene = IP_MOOD_MAP[ip]
            mood_labels.append(mood2idx[mood])
            scene_labels.append(scene2idx[scene])
            valid_indices.append(i)

    _log(f"  有效训练样本: {len(valid_indices)}/{len(entries)}")

    emb_valid = embeddings[valid_indices]
    mood_arr = np.array(mood_labels, dtype=np.int64)
    scene_arr = np.array(scene_labels, dtype=np.int64)

    # 划分训练/验证
    n = len(valid_indices)
    perm = np.random.permutation(n)
    n_val = int(n * 0.15)
    val_idx = set(perm[:n_val].tolist())

    train_mask = np.array([i not in val_idx for i in range(n)])
    val_mask = ~train_mask

    train_ds = EmbeddingDataset(
        torch.from_numpy(emb_valid[train_mask]),
        torch.from_numpy(mood_arr[train_mask]),
        torch.from_numpy(scene_arr[train_mask]),
    )
    val_ds = EmbeddingDataset(
        torch.from_numpy(emb_valid[val_mask]),
        torch.from_numpy(mood_arr[val_mask]),
        torch.from_numpy(scene_arr[val_mask]),
    )

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False)

    device = get_device()
    model = MoodSceneClassifier().to(device)
    n_params = sum(p.numel() for p in model.parameters())
    _log(f"  模型参数: {n_params/1e3:.1f}K")

    optimizer = optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = 0.0
    history = []

    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0.0
        train_mood_correct = 0
        train_scene_correct = 0
        train_total = 0

        for embs, mood_lbl, scene_lbl in train_loader:
            embs = embs.to(device)
            mood_lbl = mood_lbl.to(device)
            scene_lbl = scene_lbl.to(device)

            optimizer.zero_grad()
            mood_out, scene_out = model(embs)
            loss = criterion(mood_out, mood_lbl) + criterion(scene_out, scene_lbl)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * embs.size(0)
            _, mood_pred = mood_out.max(1)
            _, scene_pred = scene_out.max(1)
            train_total += embs.size(0)
            train_mood_correct += mood_pred.eq(mood_lbl).sum().item()
            train_scene_correct += scene_pred.eq(scene_lbl).sum().item()

        scheduler.step()

        # 验证
        model.eval()
        val_mood_correct = 0
        val_scene_correct = 0
        val_total = 0
        with infer_ctx(device):
            for embs, mood_lbl, scene_lbl in val_loader:
                embs = embs.to(device)
                mood_lbl = mood_lbl.to(device)
                scene_lbl = scene_lbl.to(device)
                mood_out, scene_out = model(embs)
                _, mood_pred = mood_out.max(1)
                _, scene_pred = scene_out.max(1)
                val_total += embs.size(0)
                val_mood_correct += mood_pred.eq(mood_lbl).sum().item()
                val_scene_correct += scene_pred.eq(scene_lbl).sum().item()

        train_mood_acc = train_mood_correct / max(train_total, 1)
        train_scene_acc = train_scene_correct / max(train_total, 1)
        val_mood_acc = val_mood_correct / max(val_total, 1)
        val_scene_acc = val_scene_correct / max(val_total, 1)
        val_avg = (val_mood_acc + val_scene_acc) / 2

        if val_avg > best_val_acc:
            best_val_acc = val_avg
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": model.state_dict(),
                "mood_classes": MOOD_CLASSES,
                "scene_classes": SCENE_CLASSES,
                "val_mood_acc": val_mood_acc,
                "val_scene_acc": val_scene_acc,
                "epoch": epoch,
            }, MODEL_DIR / "t12_mood_scene_classifier.pt")

        history.append({
            "epoch": epoch + 1,
            "train_mood_acc": round(train_mood_acc, 4),
            "train_scene_acc": round(train_scene_acc, 4),
            "val_mood_acc": round(val_mood_acc, 4),
            "val_scene_acc": round(val_scene_acc, 4),
        })

        if (epoch + 1) % 5 == 0 or epoch == 0:
            _log(f"  Epoch {epoch+1}/{EPOCHS} | "
                 f"mood: train={train_mood_acc:.4f} val={val_mood_acc:.4f} | "
                 f"scene: train={train_scene_acc:.4f} val={val_scene_acc:.4f}")

    return {
        "best_val_avg": round(best_val_acc, 4),
        "history": history,
        "epochs": EPOCHS,
        "n_train": len(train_ds),
        "n_val": len(val_ds),
    }


def main():
    _log("=" * 60)
    _log("T12: mood/scene_type本地MLP兜底分类头(实际训练)")
    _log("=" * 60)

    # 1. 计算CLIP嵌入
    _log("\n[1/3] 计算CLIP嵌入...")
    t0 = time.time()
    embeddings, entries = compute_clip_embeddings()
    _log(f"  嵌入: {embeddings.shape}, 耗时{time.time()-t0:.1f}s")

    # 2. 训练
    t0 = time.time()
    result = train_t12(embeddings, entries)
    _log(f"  训练耗时: {time.time()-t0:.1f}s")

    # 3. 报告
    _log("\n[3/3] 生成报告...")
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "MoodSceneClassifier(512→128→64→双头)",
        "mood_classes": MOOD_CLASSES,
        "scene_classes": SCENE_CLASSES,
        "training": result,
        "model_path": str(MODEL_DIR / "t12_mood_scene_classifier.pt"),
        "confidence_cap": 0.6,
        "status": "complete",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t12_mood_scene_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T12训练完成")
    _log(f"   最佳验证: mood+scene avg={result['best_val_avg']}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    main()
