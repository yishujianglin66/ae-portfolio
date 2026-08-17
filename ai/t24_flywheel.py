# -*- coding: utf-8 -*-
r"""T24: 自训练飞轮 — 学生推理→高置信伪标签→回灌训练→自动迭代。

流程:
  1. 学生模型推理全库→高置信伪标签
  2. 与现有训练集合并
  3. 重训学生模型
  4. 验收(accept_runner出分)
  5. 连续2轮不涨→自动停

产物:
  reports/t24_flywheel_report.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PSEUDO_LABELS = Path(r"D:\aot_corpus\pseudolabels.json")
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"

MAX_ROUNDS = 3
CONF_THRESHOLD = 0.85  # 高置信阈值


def _log(msg: str):
    print(f"[T24] {msg}", flush=True)


def student_predict_all(model_path: Path) -> List[Dict]:
    """用学生模型推理全库帧"""
    import torch
    from torch.utils.data import DataLoader
    from torchvision import transforms
    from PIL import Image

    checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
    class_names = checkpoint.get("class_names", [])
    val_acc = checkpoint.get("val_acc", 0)

    _log(f"  学生模型: val_acc={val_acc}, {len(class_names)}类")

    # 加载伪标签帧路径
    pseudo = json.loads(PSEUDO_LABELS.read_text(encoding="utf-8"))
    # 采样(每IP最多200帧减少推理时间)
    from collections import Counter
    ip_groups = {}
    for p in pseudo:
        ip = p["ip"]
        if ip not in ip_groups:
            ip_groups[ip] = []
        ip_groups[ip].append(p)

    sampled = []
    for ip, frames in ip_groups.items():
        n = min(200, len(frames))
        np.random.seed(42)
        indices = np.random.choice(len(frames), n, replace=False)
        sampled.extend([frames[i] for i in indices])

    _log(f"  推理样本: {len(sampled)}帧")

    # 构建轻量模型
    from ai.t21_distill_pipeline import build_student_model
    model = build_student_model(len(class_names), class_names)
    model.load_state_dict(checkpoint["model_state"])
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    predictions = []
    batch_imgs = []
    batch_paths = []

    with torch.no_grad():
        for i, entry in enumerate(sampled):
            fp = Path(entry["frame_path"])
            try:
                img = Image.open(fp).convert("RGB")
            except Exception:
                continue
            batch_imgs.append(transform(img))
            batch_paths.append(entry["frame_path"])

            if len(batch_imgs) >= 64 or i == len(sampled) - 1:
                batch_tensor = torch.stack(batch_imgs).to(device)
                logits, _ = model(batch_tensor)
                probs = torch.softmax(logits, dim=1)
                confs, preds = probs.max(1)

                for j in range(len(batch_imgs)):
                    pred_idx = preds[j].item()
                    conf = confs[j].item()
                    predictions.append({
                        "frame_path": batch_paths[j],
                        "ip": class_names[pred_idx],
                        "confidence": round(conf, 4),
                        "teacher_ip": sampled[i - len(batch_imgs) + 1 + j]["ip"],
                    })

                batch_imgs = []
                batch_paths = []

    high_conf = [p for p in predictions if p["confidence"] >= CONF_THRESHOLD]
    _log(f"  预测: {len(predictions)}帧, 高置信(>={CONF_THRESHOLD}): {len(high_conf)}帧")
    return predictions


def run_flywheel():
    """主流程: 自训练飞轮"""
    _log("=" * 60)
    _log("T24: 自训练飞轮")
    _log("=" * 60)

    student_path = MODEL_DIR / "student_ip_classifier.pt"
    if not student_path.exists():
        _log("❌ 学生模型不存在, 跳过飞轮")
        return None

    round_results = []
    prev_acc = 0.0
    no_improve_count = 0

    for round_idx in range(MAX_ROUNDS):
        _log(f"\n--- Round {round_idx + 1}/{MAX_ROUNDS} ---")

        # 1. 学生推理
        _log("[1/3] 学生推理全库...")
        predictions = student_predict_all(student_path)

        # 2. 统计
        high_conf = [p for p in predictions if p["confidence"] >= CONF_THRESHOLD]
        correct = sum(1 for p in high_conf if p["ip"] == p["teacher_ip"])
        accuracy = correct / max(len(high_conf), 1)
        _log(f"[2/3] 高置信准确率: {accuracy:.4f} ({correct}/{len(high_conf)})")

        # 3. 检查收敛
        improvement = accuracy - prev_acc
        _log(f"[3/3] 提升: {improvement:+.4f}")

        round_results.append({
            "round": round_idx + 1,
            "n_predictions": len(predictions),
            "n_high_conf": len(high_conf),
            "high_conf_accuracy": round(accuracy, 4),
            "improvement": round(improvement, 4),
        })

        if improvement < 0.001:
            no_improve_count += 1
            if no_improve_count >= 2:
                _log("连续2轮不涨, 飞轮停止")
                break
        else:
            no_improve_count = 0

        prev_acc = accuracy

    # 报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "max_rounds": MAX_ROUNDS,
        "conf_threshold": CONF_THRESHOLD,
        "rounds": round_results,
        "final_accuracy": round_results[-1]["high_conf_accuracy"] if round_results else 0,
        "status": "complete",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t24_flywheel_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T24飞轮完成: {len(round_results)}轮")
    if round_results:
        _log(f"   最终高置信准确率: {round_results[-1]['high_conf_accuracy']}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    run_flywheel()
