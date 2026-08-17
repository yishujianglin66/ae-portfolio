# -*- coding: utf-8 -*-
"""T12: mood/scene_type本地MLP兜底分类头。

从VLM缓存+规则启发式生成训练标签，CLIP帧嵌入→轻量MLP→mood/scene_type预测。
验收: VLM缺席时两字段非空率100%，置信上限0.6。
"""
import json, os, sys, time
from pathlib import Path
from collections import Counter
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

VLM_CACHE = ROOT / "cache" / "material_intel"
OUT_DIR = ROOT / "models"

# mood/scene_type 类别定义
MOOD_CLASSES = ["calm", "building", "intense", "climax", "melancholy"]
SCENE_CLASSES = ["battle", "action", "closeup", "landscape", "indoor", "dialogue"]


def extract_vlm_labels():
    """从VLM缓存提取mood/scene_type标签"""
    labels = []
    for f in sorted(VLM_CACHE.glob("*.json")):
        if f.name == "test_results.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        content = data.get("content", {})
        mood = content.get("mood", "unknown")
        scene = content.get("scene_type", "unknown")
        if mood != "unknown" and scene != "unknown":
            labels.append({
                "video": data.get("filename", ""),
                "mood": mood,
                "scene_type": scene,
                "file_hash": data.get("file_hash", ""),
            })
    return labels


def generate_heuristic_labels():
    """用规则启发式从训练标签生成mood/scene_type伪标签。

    规则:
    - IP=进击的巨人 + action描述 → mood=intense, scene=battle
    - 根据视频文件名中的关键词推断
    """
    labels_path = ROOT / "data" / "training" / "labels.json"
    if not labels_path.exists():
        return []

    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    # IP→默认mood/scene映射
    ip_mood_map = {
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
    }

    generated = []
    for l in labels:
        ip = l.get("ip", "")
        if ip in ip_mood_map:
            mood, scene = ip_mood_map[ip]
            generated.append({
                "path": l.get("path", ""),
                "ip": ip,
                "mood": mood,
                "scene_type": scene,
                "source": "heuristic",
            })

    return generated


def build_t12_classifier():
    """构建T12 mood/scene_type本地MLP分类头"""
    import torch
    import torch.nn as nn

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

    model = MoodSceneClassifier()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[T12] 模型参数: {n_params/1e3:.1f}K")
    return model


def main():
    print("=" * 60)
    print("T12: mood/scene_type本地MLP兜底分类头")
    print("=" * 60)

    # 1. 提取VLM标签
    print("\n[1/4] 提取VLM缓存标签...")
    vlm_labels = extract_vlm_labels()
    print(f"  VLM标签: {len(vlm_labels)}条")
    mood_dist = Counter(l["mood"] for l in vlm_labels)
    scene_dist = Counter(l["scene_type"] for l in vlm_labels)
    print(f"  mood分布: {dict(mood_dist)}")
    print(f"  scene分布: {dict(scene_dist)}")

    # 2. 生成启发式标签
    print("\n[2/4] 生成启发式标签...")
    heur_labels = generate_heuristic_labels()
    print(f"  启发式标签: {len(heur_labels)}条")
    heur_mood = Counter(l["mood"] for l in heur_labels)
    heur_scene = Counter(l["scene_type"] for l in heur_labels)
    print(f"  mood分布: {dict(heur_mood)}")
    print(f"  scene分布: {dict(heur_scene)}")

    # 3. 构建分类器
    print("\n[3/4] 构建MLP分类器...")
    model = build_t12_classifier()

    # 4. 训练(简化: 用启发式标签训练, VLM标签作验证)
    print("\n[4/4] 训练(使用CLIP嵌入+启发式标签)...")

    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"  设备: {device}")

    # 由于没有实际CLIP嵌入缓存, 先用随机嵌入验证模型结构
    # 实际训练在T20伪标签完成后, 结合真实CLIP嵌入进行
    model = model.to(device)

    # 模拟训练验证模型可跑通
    dummy_input = torch.randn(32, 512).to(device)
    mood_out, scene_out = model(dummy_input)
    print(f"  输出shape: mood={mood_out.shape}, scene={scene_out.shape}")
    print(f"  mood类数: {mood_out.shape[1]}, scene类数: {scene_out.shape[1]}")

    # 保存模型
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_path = OUT_DIR / "t12_mood_scene_classifier.pt"
    torch.save({
        "model_state": model.state_dict(),
        "mood_classes": MOOD_CLASSES,
        "scene_classes": SCENE_CLASSES,
        "n_vlm_labels": len(vlm_labels),
        "n_heuristic_labels": len(heur_labels),
    }, model_path)

    # 生成报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "MoodSceneClassifier(512→128→64→双头)",
        "mood_classes": MOOD_CLASSES,
        "scene_classes": SCENE_CLASSES,
        "vlm_labels": len(vlm_labels),
        "heuristic_labels": len(heur_labels),
        "model_path": str(model_path),
        "confidence_cap": 0.6,  # 仲裁链规则4: 本地头置信上限0.6
        "status": "structure_verified",
        "note": "实际训练需T20伪标签完成+CLIP嵌入就绪后执行",
    }
    report_path = ROOT / "reports" / "t12_mood_scene_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"✅ T12结构验证通过")
    print(f"   VLM标签: {len(vlm_labels)}")
    print(f"   启发式标签: {len(heur_labels)}")
    print(f"   模型: {model_path}")
    print(f"   报告: {report_path}")
    print(f"{'='*60}")

    return report


if __name__ == "__main__":
    main()
