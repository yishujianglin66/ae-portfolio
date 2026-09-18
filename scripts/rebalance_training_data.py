"""
Phase 2.1: 训练数据再平衡

问题: 当前数据分布不均 (amv_pull_zoom 172 vs 基础风格 72, 比例 2.4:1)
方案: 
  - 低频类 (<130) 过采样至 140 (带参数抖动增强)
  - 高频类 (>150) 欠采样至 140
  - 目标: 所有类别在 130-150 之间, 最大最小比 < 1.2:1

输出: data/style_classify_dataset_balanced.jsonl
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = PROJECT_ROOT / "data" / "style_classify_dataset.jsonl"
OUTPUT_PATH = PROJECT_ROOT / "data" / "style_classify_dataset_balanced.jsonl"

TARGET_COUNT = 140  # 每类目标样本数
JITTER_STD = 0.05   # 过采样时的参数抖动标准差 (相对于特征值范围)
SEED = 42

# 需要跳过的特征 (不应被抖动)
SKIP_JITTER_FEATURES = {"resolution_width", "resolution_height"}


def load_dataset(path: Path) -> list:
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return samples


def augment_sample(sample: dict, aug_idx: int, feature_ranges: dict) -> dict:
    """对样本进行参数抖动增强"""
    new_sample = json.loads(json.dumps(sample))  # deep copy
    new_sample["sample_id"] = f"{sample['sample_id']}_bal_{aug_idx}"
    
    if "metadata" not in new_sample:
        new_sample["metadata"] = {}
    new_sample["metadata"]["augmentation"] = "rebalance_jitter"
    
    features = new_sample.get("features", {})
    for key, val in features.items():
        if key in SKIP_JITTER_FEATURES:
            continue
        if isinstance(val, (int, float)):
            # 计算抖动范围: 特征值范围的 5%
            feat_range = feature_ranges.get(key, 1.0)
            jitter = random.gauss(0, JITTER_STD * feat_range)
            new_val = val + jitter
            # 保持整数类型
            if isinstance(val, int):
                new_val = int(round(new_val))
            features[key] = new_val
    
    return new_sample


def compute_feature_ranges(samples_by_class: dict) -> dict:
    """计算每个特征的全局范围 (max - min)"""
    all_values = defaultdict(list)
    for class_samples in samples_by_class.values():
        for s in class_samples:
            for key, val in s.get("features", {}).items():
                if isinstance(val, (int, float)):
                    all_values[key].append(val)
    
    ranges = {}
    for key, vals in all_values.items():
        ranges[key] = max(vals) - min(vals) if len(vals) > 1 else 1.0
    return ranges


def main():
    random.seed(SEED)
    np.random.seed(SEED)
    
    print("=" * 60)
    print("Phase 2.1: 训练数据再平衡")
    print("=" * 60)
    
    # 加载数据
    samples = load_dataset(INPUT_PATH)
    print(f"原始样本数: {len(samples)}")
    
    # 按类别分组
    samples_by_class = defaultdict(list)
    for s in samples:
        label = s.get("label", "")
        if label:
            samples_by_class[label].append(s)
    
    # 统计
    print(f"类别数: {len(samples_by_class)}")
    counts = {k: len(v) for k, v in samples_by_class.items()}
    max_count = max(counts.values())
    min_count = min(counts.values())
    print(f"当前分布: max={max_count}, min={min_count}, ratio={max_count/min_count:.2f}:1")
    print()
    
    # 计算特征范围 (用于抖动)
    feature_ranges = compute_feature_ranges(samples_by_class)
    
    # 再平衡
    balanced_samples = []
    stats = []
    
    for label in sorted(samples_by_class.keys()):
        class_samples = samples_by_class[label]
        n = len(class_samples)
        
        if n >= TARGET_COUNT:
            # 欠采样: 随机选取 TARGET_COUNT 个
            selected = random.sample(class_samples, TARGET_COUNT)
            balanced_samples.extend(selected)
            action = f"欠采样 {n}→{TARGET_COUNT}"
        else:
            # 过采样: 保留原始 + 增强补充
            balanced_samples.extend(class_samples)
            need = TARGET_COUNT - n
            for i in range(need):
                # 从原始样本中随机选一个进行增强
                base = random.choice(class_samples)
                aug = augment_sample(base, i, feature_ranges)
                balanced_samples.append(aug)
            action = f"过采样 {n}→{TARGET_COUNT}"
        
        stats.append((label, n, TARGET_COUNT, action))
    
    # 打乱顺序
    random.shuffle(balanced_samples)
    
    # 输出
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for s in balanced_samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    
    # 打印统计
    print(f"{'类别':<25} {'原始':>6} {'目标':>6}  操作")
    print("-" * 60)
    for label, orig, target, action in stats:
        print(f"  {label:<23} {orig:>6} {target:>6}  {action}")
    
    print(f"\n{'=' * 60}")
    print("再平衡完成!")
    print(f"  输出: {OUTPUT_PATH}")
    print(f"  总样本数: {len(balanced_samples)}")
    
    # 验证新分布
    new_counts = Counter(s["label"] for s in balanced_samples)
    new_max = max(new_counts.values())
    new_min = min(new_counts.values())
    print(f"  新分布: max={new_max}, min={new_min}, ratio={new_max/new_min:.2f}:1")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
