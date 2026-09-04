# -*- coding: utf-8 -*-
r"""T27b: 场景分类器训练 — 基于VLM标注数据训练ResNet18场景分类头。

8类场景: battle/daily/dialog/flashback/landscape/ceremony/emotional/comedy
使用VLM标注的scene_type字段作为标签, ResNet18预训练骨干 + 自定义分类头。

产物:
  models/scene_classifier_v1.pt
  reports/t27b_scene_report.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms, models
from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.torch_runtime import get_device, infer_ctx

# === 路径配置 ===
VLM_FULL_DIR = Path(r"D:\aot_corpus\vlm_full")
VLM_RESULTS = VLM_FULL_DIR / "results.jsonl"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"

# === 训练配置 ===
SCENE_CLASSES = ["battle", "daily", "dialog", "flashback", "landscape", "ceremony", "emotional", "comedy"]
SCENE2IDX = {s: i for i, s in enumerate(SCENE_CLASSES)}
IMG_SIZE = 224
BATCH_SIZE = 64
EPOCHS = 30
LR = 1e-4
MIN_SAMPLES_PER_CLASS = 20  # 每类最少样本数


def _log(msg):
    print(f"[T27b] {msg}", flush=True)


class SceneDataset(Dataset):
    def __init__(self, entries, transform):
        self.entries = entries
        self.transform = transform
    
    def __len__(self):
        return len(self.entries)
    
    def __getitem__(self, idx):
        e = self.entries[idx]
        img = Image.open(e["frame_path"]).convert("RGB")
        img = self.transform(img)
        return img, e["label_idx"]


def load_vlm_scene_data():
    """从VLM标注结果加载场景数据"""
    if not VLM_RESULTS.exists():
        _log(f"错误: VLM标注结果不存在 {VLM_RESULTS}")
        return []
    
    entries = []
    scene_counter = Counter()
    
    with open(VLM_RESULTS, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            
            scene = r.get("scene_type", "").strip().lower()
            if scene not in SCENE2IDX:
                continue
            
            frame_path = r.get("frame_path", "")
            if not Path(frame_path).exists():
                continue
            
            entries.append({
                "frame_path": frame_path,
                "scene": scene,
                "label_idx": SCENE2IDX[scene],
            })
            scene_counter[scene] += 1
    
    _log(f"VLM场景数据: {len(entries)}帧")
    _log(f"场景分布: {dict(scene_counter.most_common())}")
    
    # 过滤样本过少的类
    valid_classes = [s for s, c in scene_counter.items() if c >= MIN_SAMPLES_PER_CLASS]
    _log(f"有效场景类(>={MIN_SAMPLES_PER_CLASS}样本): {valid_classes}")
    
    filtered = [e for e in entries if e["scene"] in valid_classes]
    _log(f"过滤后: {len(filtered)}帧")
    
    # 重新映射标签索引到 0..N-1（避免过滤后索引越界）
    remap = {s: i for i, s in enumerate(valid_classes)}
    for e in filtered:
        e["label_idx"] = remap[e["scene"]]
    
    return filtered, remap


def train_scene_classifier():
    """训练场景分类器"""
    _log("=" * 60)
    _log("T27b: 场景分类器训练 (ResNet18)")
    _log("=" * 60)
    
    device = get_device()
    _log(f"设备: {device}")
    
    # 1. 加载数据
    _log("\n[1/4] 加载VLM场景数据...")
    entries, remap = load_vlm_scene_data()
    if len(entries) < 100:
        _log("数据不足, 跳过训练")
        return None
    
    # 2. 分层分割 80/20
    _log("[2/4] 分割训练/验证集...")
    from collections import defaultdict
    scene_groups = defaultdict(list)
    for e in entries:
        scene_groups[e["scene"]].append(e)
    
    train_entries = []
    val_entries = []
    np.random.seed(42)
    for scene, group in scene_groups.items():
        np.random.shuffle(group)
        split = max(1, int(len(group) * 0.8))
        train_entries.extend(group[:split])
        val_entries.extend(group[split:])
    
    _log(f"  训练集: {len(train_entries)}, 验证集: {len(val_entries)}")
    
    # 3. 构建模型
    _log("[3/4] 构建ResNet18场景分类器...")
    transform_train = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(0.1, 0.1, 0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])
    transform_val = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])
    
    train_ds = SceneDataset(train_entries, transform_train)
    val_ds = SceneDataset(val_entries, transform_val)
    
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0, pin_memory=True)
    
    # ResNet18预训练 + 自定义分类头
    resnet = models.resnet18(pretrained=True)
    n_classes = len(set(e["label_idx"] for e in entries))
    resnet.fc = nn.Linear(resnet.fc.in_features, n_classes)
    resnet = resnet.to(device)
    
    _log(f"  有效分类: {list(remap.keys())}")
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(resnet.parameters(), lr=LR, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    
    _log(f"  参数量: {sum(p.numel() for p in resnet.parameters())/1e6:.2f}M")
    _log(f"  分类数: {n_classes}")
    
    # 4. 训练
    _log("[4/4] 开始训练...")
    best_val_acc = 0.0
    history = []
    t0 = time.time()
    
    for epoch in range(EPOCHS):
        # 训练
        resnet.train()
        train_loss = 0.0
        train_correct = 0
        train_total = 0
        
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = resnet(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            train_total += labels.size(0)
            train_correct += predicted.eq(labels).sum().item()
        
        scheduler.step()
        
        # 验证
        resnet.eval()
        val_correct = 0
        val_total = 0
        with infer_ctx(device):
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = resnet(images)
                _, predicted = outputs.max(1)
                val_total += labels.size(0)
                val_correct += predicted.eq(labels).sum().item()
        
        train_acc = train_correct / max(train_total, 1)
        val_acc = val_correct / max(val_total, 1)
        avg_loss = train_loss / max(len(train_loader), 1)
        
        history.append({
            "epoch": epoch + 1,
            "train_loss": round(avg_loss, 4),
            "train_acc": round(train_acc, 4),
            "val_acc": round(val_acc, 4),
        })
        
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            # 保存最佳模型
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state": resnet.state_dict(),
                "scene_classes": list(remap.keys()),
                "scene2idx": remap,
                "config": {
                    "img_size": IMG_SIZE,
                    "n_classes": n_classes,
                    "backbone": "ResNet18",
                },
            }, MODEL_DIR / "scene_classifier_v1.pt")
        
        if (epoch + 1) % 5 == 0 or epoch == 0:
            _log(f"  Epoch {epoch+1}/{EPOCHS} | loss={avg_loss:.4f} | train_acc={train_acc:.4f} | val_acc={val_acc:.4f} | best={best_val_acc:.4f}")
    
    elapsed = time.time() - t0
    _log(f"\n训练完成! 耗时: {elapsed/60:.1f}min")
    _log(f"最佳验证精度: {best_val_acc:.4f} ({best_val_acc*100:.2f}%)")
    
    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "ResNet18 Scene Classifier",
        "n_classes": n_classes,
        "classes": list(remap.keys()),
        "train_samples": len(train_entries),
        "val_samples": len(val_entries),
        "best_val_acc": round(best_val_acc, 4),
        "epochs": EPOCHS,
        "elapsed_min": round(elapsed / 60, 1),
        "history": history,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "t27b_scene_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"报告保存: {REPORT_DIR / 't27b_scene_report.json'}")
    
    return report


if __name__ == "__main__":
    train_scene_classifier()
