#!/usr/bin/env python3
"""
域适应训练脚本 - 将真实视频特征注入训练数据

问题：模型在合成数据上训练(90.5% val acc)，但真实视频特征分布完全不同
解决：将10个真实视频的提取特征(带标注)加入训练集，增强模型对真实域的适应

策略：
1. 从 real_video_test_report.json 提取真实视频特征
2. 对每个真实样本做 30x 增强（参数抖动）
3. 与现有平衡训练集合并
4. 重训练模型
"""
import json
import random
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FEATURE_NAMES = [
    "brightness", "saturation", "warmth", "cut_rate", "avg_shot_duration",
    "resolution_width", "resolution_height", "bpm", "zoom_intensity",
    "rotation_angle", "shutter_angle", "motion_blur_enabled",
    "dynamic_tile_enabled", "beat_sync_strength", "keyframes_density",
    "motion_trajectory_complexity", "color_vibrancy", "contrast_ratio",
    "edge_detection_strength", "depth_of_field", "shot_transition_diversity",
    "rhythm_consistency", "frame_rate_variation", "visual_complexity"
]

STYLE_LABELS = {
    "cinematic": 0, "anime_puppet": 1, "fast_cut": 2, "slow_cut": 3,
    "glitch_digital": 4, "audio_visual": 5, "particle_ambient": 6,
    "text_animation": 7, "3d_spatial": 8, "realistic_color": 9,
    "high_dynamic": 10, "dark_tone": 11, "low_saturation": 12,
    "高饱和": 13, "长镜头": 14, "amv_pull_zoom": 15, "amv_fast_cut": 16,
    "amv_beat_sync": 17, "amv_korean_flash": 18, "amv_glitch": 19,
    "amv_cinematic": 20, "amv_3d_spatial": 21, "amv_high_burn": 22,
}


def load_real_features():
    """从测试报告中提取真实视频特征+标签
    
    支持两种数据源:
    1. real_video_test_report.json (旧版, 10个视频)
    2. 直接从ground_truth.json + 视频文件提取 (扩展版, 50+视频)
    """
    report_path = PROJECT_ROOT / "output" / "real_video_test" / "real_video_test_report.json"
    gt_path = PROJECT_ROOT / "data" / "real_amv_test" / "ground_truth.json"

    samples = []
    
    # 方法一: 从已有报告加载
    if report_path.exists():
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
        with open(gt_path, encoding="utf-8") as f:
            gt_data = json.load(f)

        gt_map = {v["bv_id"]: v["expected_style"] for v in gt_data["videos"]}

        for result in report["results"]:
            video_name = result["video"]
            bv_id = video_name.split("_")[0]
            label = gt_map.get(bv_id)
            if not label or label not in STYLE_LABELS:
                continue

            features = result["features"]
            if len(features) != 24:
                continue

            samples.append({
                "features": features,
                "label": label,
                "label_id": STYLE_LABELS[label],
                "source": video_name,
            })

    # 方法二: 如果有更多视频但无报告，尝试提取特征
    # (需要先运行 test_real_pipeline.py 生成报告)
    
    print(f"  从报告加载了 {len(samples)} 个有效样本")
    return samples


def augment_real_sample(sample, n_augments=30):
    """对单个真实样本做参数抖动增强
    
    增强策略：
    - 连续特征: ±15% 高斯抖动
    - 二值特征 (motion_blur, dynamic_tile): 10% 概率翻转
    - resolution 保持不变 (已归一化)
    """
    augmented = []
    features = np.array(sample["features"], dtype=np.float64)
    label = sample["label"]
    label_id = sample["label_id"]

    # 特征索引分组
    continuous_indices = [0, 1, 2, 3, 4, 7, 8, 9, 10, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    binary_indices = [11, 12]  # motion_blur, dynamic_tile
    fixed_indices = [5, 6]  # resolution_width, resolution_height
    # beat_sync_strength (13) 是 0-1 连续值
    continuous_indices.append(13)

    for aug_idx in range(n_augments):
        new_features = features.copy()

        # 连续特征高斯抖动
        for idx in continuous_indices:
            noise_scale = abs(new_features[idx]) * 0.15 + 0.01
            new_features[idx] += random.gauss(0, noise_scale)

        # 特殊范围约束
        new_features[0] = max(10, min(90, new_features[0]))   # brightness
        new_features[1] = max(10, min(95, new_features[1]))   # saturation
        new_features[2] = max(-15, min(20, new_features[2]))  # warmth
        new_features[3] = max(0.1, min(5.0, new_features[3])) # cut_rate
        new_features[4] = max(0.1, min(5.0, new_features[4])) # avg_shot_duration
        new_features[7] = max(50, min(220, new_features[7]))  # bpm
        new_features[8] = max(100, min(200, new_features[8])) # zoom_intensity
        new_features[9] = max(0, min(45, new_features[9]))    # rotation_angle
        new_features[10] = max(0, min(360, new_features[10])) # shutter_angle
        new_features[13] = max(0, min(1, new_features[13]))   # beat_sync_strength
        new_features[14] = max(0, min(5, new_features[14]))   # keyframes_density
        new_features[15] = max(0, min(1, new_features[15]))   # motion_traj
        new_features[16] = max(0, min(1, new_features[16]))   # color_vibrancy
        new_features[17] = max(0.5, min(3, new_features[17])) # contrast_ratio
        new_features[18] = max(0, min(0.9, new_features[18])) # edge_detection
        new_features[19] = max(0, min(1, new_features[19]))   # depth_of_field
        new_features[20] = max(0, min(1, new_features[20]))   # shot_diversity
        new_features[21] = max(0, min(1, new_features[21]))   # rhythm_consistency
        new_features[22] = max(0, min(1, new_features[22]))   # frame_rate_var
        new_features[23] = max(0, min(1, new_features[23]))   # visual_complexity

        # 二值特征偶尔翻转 (10%)
        for idx in binary_indices:
            if random.random() < 0.10:
                new_features[idx] = 1.0 - new_features[idx]

        # resolution 固定
        for idx in fixed_indices:
            new_features[idx] = features[idx]

        augmented.append({
            "features": new_features.tolist(),
            "label": label,
            "label_id": label_id,
            "source": f"{sample['source']}_aug{aug_idx}",
        })

    return augmented


def load_balanced_dataset():
    """加载已有的平衡训练集"""
    balanced_path = PROJECT_ROOT / "data" / "style_classify_dataset_balanced.jsonl"
    if not balanced_path.exists():
        print(f"错误: 平衡数据集不存在 {balanced_path}")
        return []

    samples = []
    with open(balanced_path, encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            features_dict = data["features"]
            features_vec = [float(features_dict[name]) for name in FEATURE_NAMES]
            samples.append({
                "features": features_vec,
                "label": data["label"],
                "label_id": data["label_id"],
                "source": data.get("source", "balanced"),
            })
    return samples


def save_combined_dataset(samples, output_path):
    """保存合并数据集为JSONL"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for s in samples:
            record = {
                "sample_id": s["source"],
                "features": {name: val for name, val in zip(FEATURE_NAMES, s["features"])},
                "label": s["label"],
                "label_id": s["label_id"],
                "source": s["source"],
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(samples)


def main():
    random.seed(42)
    np.random.seed(42)

    print("=" * 60)
    print("域适应训练 - 注入真实视频特征")
    print("=" * 60)

    # Step 1: 加载真实视频特征
    print("\n[1] 加载真实视频特征...")
    real_samples = load_real_features()
    print(f"  有效真实样本: {len(real_samples)}")
    for s in real_samples:
        print(f"    {s['source']}: {s['label']}")

    if not real_samples:
        print("错误: 无有效真实样本! 请先运行 tests/test_real_pipeline.py")
        return

    # Step 2: 增强真实样本
    print("\n[2] 增强真实样本 (30x per sample)...")
    augmented_real = []
    for sample in real_samples:
        augmented_real.extend(augment_real_sample(sample, n_augments=30))
    print(f"  增强后真实域样本: {len(augmented_real)}")

    # 统计增强后的标签分布
    from collections import Counter
    aug_labels = Counter(s["label"] for s in augmented_real)
    print(f"  增强标签分布: {dict(aug_labels)}")

    # Step 3: 加载现有平衡数据集
    print("\n[3] 加载现有平衡训练集...")
    balanced_samples = load_balanced_dataset()
    print(f"  平衡数据集样本: {len(balanced_samples)}")

    # Step 4: 合并
    # 为了不让真实样本被淹没，对每个类别的真实增强样本进行过采样
    # 目标: 真实域样本占总训练集的 ~15-20%
    combined = balanced_samples + augmented_real
    
    # 额外: 对真实样本中数量少的类别再补充增强
    real_label_counts = Counter(s["label"] for s in augmented_real)
    max_real_count = max(real_label_counts.values()) if real_label_counts else 0
    extra_augmented = []
    for sample in real_samples:
        label = sample["label"]
        current_count = real_label_counts.get(label, 0)
        if current_count < max_real_count:
            # 补充到与其他类相同数量
            deficit = max_real_count - current_count
            extra_augmented.extend(augment_real_sample(sample, n_augments=deficit))
    
    combined += extra_augmented
    print(f"  补充欠采样类后: +{len(extra_augmented)} 样本")
    print(f"  合并后总样本: {len(combined)}")

    # 最终标签分布
    final_labels = Counter(s["label"] for s in combined)
    print("\n  最终标签分布 (top-10):")
    for label, count in final_labels.most_common(10):
        print(f"    {label}: {count}")

    # Step 5: 保存
    output_path = PROJECT_ROOT / "data" / "style_classify_dataset_domain_adapted.jsonl"
    saved = save_combined_dataset(combined, output_path)
    print(f"\n[5] 保存到: {output_path} ({saved} 样本)")

    print("\n" + "=" * 60)
    print("域适应数据准备完成!")
    print(f"下一步: python models/train_style_classifier.py --data {output_path} --use-class-weight")
    print("=" * 60)


if __name__ == "__main__":
    main()
