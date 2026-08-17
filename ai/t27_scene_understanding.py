# -*- coding: utf-8 -*-
r"""T27: 细粒度场景/角色/情绪理解 — 统一分析管线。

输入帧 → [IP分类器(已有)] → IP标签
       → [场景分类器(新增)] → 场景类型
       → [情绪分类器(T12已有)] → 情绪标签
       → [构图分析器(规则引擎)] → 构图描述
       → 统一MaterialIntel结构

场景分类器: 基于VLM标注的场景标签训练轻量ResNet18分类头(8类)
情绪分类器: 复用T12已有模型
构图分析器: OpenCV规则引擎(显著性+色调+边缘密度)

产物:
  models/t27_scene_classifier.pt — 场景分类头
  reports/t27_scene_report.json — 训练报告
"""
from __future__ import annotations

import json
import sys
import time
import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F

MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")

# 场景类别定义
SCENE_TYPES = {
    "battle": ["战斗", "对决", "战争", "battle"],
    "daily": ["日常", "学校", "生活", "daily"],
    "dialog": ["对话", "交流", "会议", "dialog"],
    "flashback": ["回忆", "过去", "闪回", "flashback"],
    "landscape": ["风景", "自然", "城市", "landscape"],
    "ceremony": ["仪式", "典礼", "变身", "ceremony"],
    "emotional": ["情感", "告白", "离别", "emotional"],
    "comedy": ["搞笑", "吐槽", "日常喜剧", "comedy"],
}
SCENE_LABELS = list(SCENE_TYPES.keys())
SCENE_IDX = {s: i for i, s in enumerate(SCENE_LABELS)}

# 情绪类别
MOOD_TYPES = {
    "hot": ["热血", "激情", "激烈"],
    "warm": ["温馨", "温暖", "治愈"],
    "sad": ["悲伤", "感动", "催泪"],
    "tense": ["紧张", "悬疑", "惊悚"],
    "funny": ["搞笑", "欢乐", "幽默"],
}
MOOD_LABELS = list(MOOD_TYPES.keys())

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def _log(msg: str):
    print(f"[T27] {msg}", flush=True)


# ================================================================ 场景分类器
class SceneClassifier(nn.Module):
    """轻量场景分类头: ResNet18 → 8类场景"""
    
    def __init__(self, n_classes=8):
        super().__init__()
        from torchvision import models
        base = models.resnet18(weights=None)
        self.features = nn.Sequential(*list(base.children())[:-1])  # 去掉FC
        self.head = nn.Linear(512, n_classes)
    
    def forward(self, x):
        feat = self.features(x).flatten(1)
        return self.head(feat)


# ================================================================ 构图分析器(规则引擎)
class CompositionAnalyzer:
    """基于OpenCV的轻量构图分析(无需模型)"""
    
    @staticmethod
    def analyze(img_path: str) -> dict:
        """分析单帧构图"""
        try:
            import cv2
            img = cv2.imread(img_path)
            if img is None:
                return {"position": "unknown", "color_mood": "neutral", "depth": "medium"}
            
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # 1. 主体位置(基于显著性检测简化版: 用边缘密度热力图)
            edges = cv2.Canny(gray, 50, 150)
            # 分4象限统计边缘密度
            q_h, q_w = h // 2, w // 2
            densities = {
                "top_left": edges[:q_h, :q_w].mean(),
                "top_right": edges[:q_h, q_w:].mean(),
                "bottom_left": edges[q_h:, :q_w].mean(),
                "bottom_right": edges[q_h:, q_w:].mean(),
            }
            max_q = max(densities, key=densities.get)
            position_map = {
                "top_left": "upper-left", "top_right": "upper-right",
                "bottom_left": "lower-left", "bottom_right": "lower-right",
            }
            position = position_map[max_q]
            
            # 2. 色调分析(HSV)
            h_channel = hsv[:, :, 0]
            s_channel = hsv[:, :, 1]
            v_channel = hsv[:, :, 2]
            avg_h = h_channel.mean()
            avg_s = s_channel.mean()
            avg_v = v_channel.mean()
            
            # 色调分类
            if avg_s < 30:
                color_mood = "neutral"  # 低饱和度
            elif avg_v < 80:
                color_mood = "dark"  # 暗调
            elif avg_h < 15 or avg_h > 160:
                color_mood = "warm"  # 红/橙
            elif 15 <= avg_h < 40:
                color_mood = "warm"  # 黄
            elif 70 <= avg_h < 130:
                color_mood = "cool"  # 绿/蓝
            elif 130 <= avg_h <= 160:
                color_mood = "cool"  # 紫
            else:
                color_mood = "neutral"
            
            # 3. 景深估计(边缘密度)
            edge_density = edges.mean()
            if edge_density > 40:
                depth = "complex"  # 复杂/前景丰富
            elif edge_density > 15:
                depth = "medium"
            else:
                depth = "simple"  # 简洁/远景
            
            return {
                "position": position,
                "color_mood": color_mood,
                "depth": depth,
                "edge_density": round(float(edge_density), 2),
                "avg_brightness": round(float(avg_v), 1),
            }
        except Exception as e:
            return {"position": "unknown", "color_mood": "neutral", "depth": "medium", "error": str(e)}


# ================================================================ 统一分析管线
class SceneUnderstandingPipeline:
    """统一场景理解管线: IP + 场景 + 情绪 + 构图"""
    
    def __init__(self):
        self.composition = CompositionAnalyzer()
        self._scene_model = None
        self._scene_transform = None
        self._scene_classes = SCENE_LABELS
    
    def _load_scene_model(self):
        """加载场景分类模型(如果存在)"""
        model_path = MODEL_DIR / "scene_classifier_v1.pt"
        if model_path.exists():
            ckpt = torch.load(model_path, map_location=DEVICE, weights_only=False)
            config = ckpt.get("config", {})
            n_classes = config.get("n_classes", len(SCENE_LABELS))
            
            # 用与训练时相同的架构: torchvision ResNet18 + 自定义fc
            from torchvision import models
            base = models.resnet18(weights=None)
            base.fc = nn.Linear(base.fc.in_features, n_classes)
            base.load_state_dict(ckpt["model_state"])
            self._scene_model = base.eval().to(DEVICE)
            self._scene_classes = ckpt.get("scene_classes", SCENE_LABELS[:n_classes])
            
            from torchvision import transforms
            self._scene_transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225]),
            ])
            _log(f"场景分类模型已加载 ({n_classes}类: {self._scene_classes})")
        else:
            _log("场景分类模型不存在, 跳过场景分类(需要先用VLM标注数据训练)")
    
    def analyze_frame(self, img_path: str, ip_result: dict = None) -> dict:
        """分析单帧, 返回统一MaterialIntel结构"""
        result = {}
        
        # IP分类(已有结果或传入)
        if ip_result:
            result["ip"] = ip_result.get("ip", "")
            result["ip_confidence"] = ip_result.get("confidence", 0)
        
        # 构图分析(始终可用)
        comp = self.composition.analyze(img_path)
        result["composition"] = comp
        
        # 场景分类(需要训练好的模型)
        if self._scene_model is None:
            self._load_scene_model()
        
        if self._scene_model is not None:
            from PIL import Image
            img = Image.open(img_path).convert("RGB")
            tensor = self._scene_transform(img).unsqueeze(0).to(DEVICE)
            with torch.no_grad():
                logits = self._scene_model(tensor)
                probs = F.softmax(logits, dim=-1)[0]
                scene_idx = probs.argmax().item()
                result["scene_type"] = self._scene_classes[scene_idx]
                result["scene_confidence"] = round(float(probs[scene_idx]), 3)
        else:
            result["scene_type"] = "unknown"
            result["scene_confidence"] = 0
        
        # 情绪(复用T12如果可用)
        result["mood"] = "unknown"
        result["mood_confidence"] = 0
        try:
            from ai.t12_mood_scene import classify_mood
            mood_result = classify_mood(img_path)
            if mood_result:
                result["mood"] = mood_result.get("mood", "unknown")
                result["mood_confidence"] = mood_result.get("confidence", 0)
        except Exception:
            pass
        
        return result
    
    def analyze_batch(self, img_paths: List[str]) -> List[dict]:
        """批量分析"""
        results = []
        for i, path in enumerate(img_paths):
            r = self.analyze_frame(path)
            r["frame_path"] = path
            results.append(r)
            if (i + 1) % 100 == 0:
                _log(f"  已处理: {i+1}/{len(img_paths)}")
        return results


# ================================================================ 场景分类器训练(基于VLM标注)
def train_scene_classifier(vlm_labels_path: Path = None, epochs=10, batch_size=32):
    """用VLM标注数据训练场景分类头"""
    _log("=" * 60)
    _log("训练场景分类器")
    _log("=" * 60)
    
    # 数据来源: VLM标注结果 或 T20伪标签(无场景标签时用规则推断)
    if vlm_labels_path and vlm_labels_path.exists():
        vlm_data = json.loads(vlm_labels_path.read_text(encoding="utf-8"))
        _log(f"VLM标注数据: {len(vlm_data)}帧")
        
        # 过滤有场景标签的帧
        labeled = [d for d in vlm_data if d.get("scene_type") and d["scene_type"] in SCENE_IDX]
        _log(f"有场景标签: {len(labeled)}帧")
    else:
        _log("无VLM标注数据, 无法训练场景分类器")
        _log("请先运行 T26 VLM标注管线获取场景标签")
        return None
    
    if len(labeled) < 100:
        _log(f"样本不足({len(labeled)}帧, 需>=100), 跳过训练")
        return None
    
    # 统计分布
    dist = Counter(d["scene_type"] for d in labeled)
    _log(f"场景分布: {dict(dist)}")
    
    # 构建数据集
    from torchvision import transforms
    from torch.utils.data import Dataset, DataLoader
    from PIL import Image
    
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])
    
    class SceneDataset(Dataset):
        def __init__(self, data, transform_fn):
            self.data = data
            self.transform = transform_fn
        
        def __len__(self):
            return len(self.data)
        
        def __getitem__(self, idx):
            d = self.data[idx]
            try:
                img = Image.open(d["frame_path"]).convert("RGB")
            except Exception:
                img = Image.new("RGB", (224, 224))
            return self.transform(img), SCENE_IDX[d["scene_type"]]
    
    # 80/20分割
    random.shuffle(labeled)
    n_train = int(len(labeled) * 0.8)
    train_data = labeled[:n_train]
    test_data = labeled[n_train:]
    
    train_loader = DataLoader(SceneDataset(train_data, transform), batch_size=batch_size, shuffle=True, num_workers=0)
    test_loader = DataLoader(SceneDataset(test_data, transform), batch_size=batch_size, shuffle=False, num_workers=0)
    
    # 训练
    model = SceneClassifier(n_classes=len(SCENE_LABELS)).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        n_batches = 0
        for images, labels in train_loader:
            images, labels = images.to(DEVICE), labels.to(DEVICE)
            optimizer.zero_grad()
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            n_batches += 1
        scheduler.step()
        
        if (epoch + 1) % 5 == 0 or epoch == 0:
            # 验证
            model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for images, labels in test_loader:
                    images, labels = images.to(DEVICE), labels.to(DEVICE)
                    logits = model(images)
                    preds = logits.argmax(dim=-1)
                    correct += (preds == labels).sum().item()
                    total += len(labels)
            val_acc = correct / max(total, 1)
            _log(f"  Epoch {epoch+1}/{epochs} | loss={total_loss/max(n_batches,1):.4f} | val_acc={val_acc:.3f}")
    
    # 保存
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODEL_DIR / "t27_scene_classifier.pt"
    torch.save(model.state_dict(), model_path)
    _log(f"模型保存: {model_path}")
    
    return {"model_path": str(model_path), "n_train": n_train, "n_test": len(test_data), "n_classes": len(SCENE_LABELS)}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["train", "demo"], default="demo")
    args = parser.parse_args()
    
    if args.mode == "train":
        # 尝试用VLM标注数据训练
        vlm_path = Path(r"D:\aot_corpus\vlm_labels_sample.json")
        train_scene_classifier(vlm_path)
    else:
        # Demo: 对几帧做分析
        pipeline = SceneUnderstandingPipeline()
        
        # 取几个aot_corpus帧做demo
        frames_dir = Path(r"D:\aot_corpus\frames")
        if frames_dir.exists():
            demo_frames = list(frames_dir.glob("*.jpg"))[:5]
            for fp in demo_frames:
                result = pipeline.analyze_frame(str(fp))
                _log(f"\n{fp.name}:")
                _log(f"  构图: {result.get('composition', {})}")
                _log(f"  场景: {result.get('scene_type', 'unknown')} (conf={result.get('scene_confidence', 0)})")
                _log(f"  情绪: {result.get('mood', 'unknown')} (conf={result.get('mood_confidence', 0)})")
