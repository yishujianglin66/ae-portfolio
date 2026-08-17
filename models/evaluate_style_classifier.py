#!/usr/bin/env python3
"""
评估风格分类模型 - 使用完整数据集进行多维度评估
"""
import sys
import json
import math
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from train_style_classifier import (
    STYLE_LABELS,
    FEATURE_NAMES,
    load_dataset,
    preprocess_features,
    normalize_features,
    StyleClassifier,
    load_model,
)


def calculate_metrics(predictions: List[int], labels: List[int], num_classes: int) -> Dict:
    """计算多维度评估指标"""
    metrics = {}
    
    correct = sum(1 for p, r in zip(predictions, labels) if p == r)
    metrics['accuracy'] = correct / len(labels) if labels else 0.0
    
    all_labels = set(labels) | set(predictions)
    
    precisions = []
    recalls = []
    f1s = []
    
    label_counts = {}
    for label in labels:
        label_counts[label] = label_counts.get(label, 0) + 1
    
    total = len(labels)
    
    weighted_precision = 0.0
    weighted_recall = 0.0
    weighted_f1 = 0.0
    
    per_class = {}
    
    for label in all_labels:
        tp = sum(1 for p, r in zip(predictions, labels) if p == label and r == label)
        fp = sum(1 for p, r in zip(predictions, labels) if p == label and r != label)
        fn = sum(1 for p, r in zip(predictions, labels) if p != label and r == label)
        tn = sum(1 for p, r in zip(predictions, labels) if p != label and r != label)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(f1)
        
        weight = label_counts.get(label, 0) / total if total > 0 else 0.0
        weighted_precision += precision * weight
        weighted_recall += recall * weight
        weighted_f1 += f1 * weight
        
        per_class[STYLE_LABELS[label]] = {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'specificity': specificity,
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'tn': tn,
            'support': label_counts.get(label, 0),
        }
    
    metrics['precision_macro'] = sum(precisions) / len(precisions) if precisions else 0.0
    metrics['recall_macro'] = sum(recalls) / len(recalls) if recalls else 0.0
    metrics['f1_macro'] = sum(f1s) / len(f1s) if f1s else 0.0
    
    metrics['precision_weighted'] = weighted_precision
    metrics['recall_weighted'] = weighted_recall
    metrics['f1_weighted'] = weighted_f1
    
    return metrics, per_class


def build_confusion_matrix(predictions: List[int], labels: List[int], num_classes: int) -> Dict:
    """构建混淆矩阵"""
    matrix = {}
    for i in range(num_classes):
        matrix[STYLE_LABELS[i]] = {STYLE_LABELS[j]: 0 for j in range(num_classes)}
    
    for pred, ref in zip(predictions, labels):
        if STYLE_LABELS[ref] in matrix and STYLE_LABELS[pred] in matrix[STYLE_LABELS[ref]]:
            matrix[STYLE_LABELS[ref]][STYLE_LABELS[pred]] += 1
    
    return matrix


def main():
    print("=" * 70)
    print("风格分类模型多维度评估 - AE Knowledge Vault")
    print("=" * 70)
    
    model_path = "models/output/style-classifier"
    data_path = "../data/style_classify_dataset.jsonl"
    
    print(f"\n[1] 加载模型: {model_path}")
    model, means, stds = load_model(model_path)
    print(f"  模型配置: {model.input_dim} → {model.hidden_dim}×{model.hidden_layers} → {model.output_dim}")
    print(f"  参数量: {model.get_params_count():,}")
    
    print(f"\n[2] 加载数据集: {data_path}")
    samples = load_dataset(data_path)
    print(f"  样本数: {len(samples)}")
    
    features, labels, _ = preprocess_features(samples)
    features, _, _ = normalize_features(features)
    print(f"  特征维度: {len(features[0]) if features else 0}")
    print(f"  类别数: {len(STYLE_LABELS)}")
    
    print("\n[3] 执行预测...")
    predictions = []
    prediction_probs = []
    
    for feat in features:
        pred = model.predict(feat)
        probs = model.predict_probs(feat)
        predictions.append(pred)
        prediction_probs.append(probs)
    
    print(f"  预测完成: {len(predictions)} 个样本")
    
    print("\n[4] 计算评估指标...")
    metrics, per_class = calculate_metrics(predictions, labels, len(STYLE_LABELS))
    
    print(f"\n{'='*60}")
    print("综合评估指标")
    print("="*60)
    print(f"  准确率 (Accuracy):        {metrics['accuracy']:.4f}")
    print(f"  宏平均精确率 (Precision): {metrics['precision_macro']:.4f}")
    print(f"  宏平均召回率 (Recall):    {metrics['recall_macro']:.4f}")
    print(f"  宏平均 F1:                {metrics['f1_macro']:.4f}")
    print(f"  加权精确率:               {metrics['precision_weighted']:.4f}")
    print(f"  加权召回率:               {metrics['recall_weighted']:.4f}")
    print(f"  加权 F1:                  {metrics['f1_weighted']:.4f}")
    
    print(f"\n{'='*60}")
    print("各风格类别详细指标")
    print("="*60)
    print(f"{'类别':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-"*60)
    
    amv_labels = [l for l in STYLE_LABELS if l.startswith('amv_')]
    other_labels = [l for l in STYLE_LABELS if not l.startswith('amv_')]
    
    for label in other_labels + amv_labels:
        if label in per_class:
            pc = per_class[label]
            print(f"{label:<20} {pc['precision']:>10.4f} {pc['recall']:>10.4f} {pc['f1']:>10.4f} {pc['support']:>10}")
    
    amv_perf = [per_class[l]['f1'] for l in amv_labels if l in per_class]
    other_perf = [per_class[l]['f1'] for l in other_labels if l in per_class]
    
    print(f"\n{'='*60}")
    print("分类性能对比")
    print("="*60)
    print(f"  通用风格 (13类) F1均值: {sum(other_perf)/len(other_perf):.4f}" if other_perf else "  通用风格: 无数据")
    print(f"  漫剪风格 (8类) F1均值: {sum(amv_perf)/len(amv_perf):.4f}" if amv_perf else "  漫剪风格: 无数据")
    
    print(f"\n{'='*60}")
    print("评估完成！")
    print("="*60)


if __name__ == "__main__":
    main()
