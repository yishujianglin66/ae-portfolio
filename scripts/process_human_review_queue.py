#!/usr/bin/env python3
"""
批量处理人工复核队列 - 用 LK 光流分类器重新标注低置信度样本
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.camera_movement_classifier import classify_video


def process_review_queue():
    """处理人工复核队列"""
    queue_path = Path(r"D:\AE-Data\AnimeCamera\human_review_queue.jsonl")
    output_path = Path(r"D:\AE-Data\AnimeCamera\reviewed_results.jsonl")
    
    if not queue_path.exists():
        print(f"❌ 队列文件不存在: {queue_path}")
        return
    
    # 读取队列
    samples = []
    with open(queue_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"📋 读取 {len(samples)} 条待复核样本")
    
    results = []
    processed = 0
    errors = 0
    
    for i, sample in enumerate(samples):
        clip_path = Path(sample['clip_path'])
        
        if not clip_path.exists():
            print(f"  ⚠️  [{i+1}/{len(samples)}] 文件不存在: {clip_path}")
            errors += 1
            continue
        
        try:
            # 使用分类器重新分析
            result = classify_video(str(clip_path))
            
            # 合并结果
            reviewed = {
                **sample,
                'reviewed_at': datetime.now().isoformat(),
                'reviewed_label': result['dominant'],
                'reviewed_confidence': result['confidence'],
                'reviewed_per_segment': result.get('per_segment', []),
                'original_label': sample['movement_label'],
                'original_confidence': sample['confidence'],
                'label_changed': result['dominant'] != sample['movement_label']
            }
            
            results.append(reviewed)
            processed += 1
            
            # 进度显示
            if (i + 1) % 10 == 0 or i == len(samples) - 1:
                changed = sum(1 for r in results if r['label_changed'])
                print(f"  ✅ [{i+1}/{len(samples)}] 已处理 {processed} 条，标签变更 {changed} 条")
                
        except Exception as e:
            print(f"  ❌ [{i+1}/{len(samples)}] 处理失败 {clip_path.name}: {e}")
            errors += 1
    
    # 写入结果
    with open(output_path, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    
    # 统计
    changed = sum(1 for r in results if r['label_changed'])
    
    print(f"\n{'='*60}")
    print("✅ 处理完成")
    print(f"   总样本: {len(samples)}")
    print(f"   成功: {processed}")
    print(f"   失败: {errors}")
    print(f"   标签变更: {changed} ({changed/processed*100:.1f}%)")
    print(f"   结果文件: {output_path}")
    print(f"{'='*60}")
    
    # 输出标签分布
    from collections import Counter
    label_dist = Counter(r['reviewed_label'] for r in results)
    print("\n📊 标签分布:")
    for label, count in sorted(label_dist.items(), key=lambda x: -x[1]):
        print(f"   {label}: {count} ({count/processed*100:.1f}%)")

if __name__ == '__main__':
    process_review_queue()
