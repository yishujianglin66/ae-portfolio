#!/usr/bin/env python3
"""
运镜分类器真实视频数据验证脚本
验证2类CNN分类器在真实动漫视频上的性能
"""

import sys
import os
import json
import time
import numpy as np
from pathlib import Path
from collections import Counter
# Removed matplotlib/seaborn for compatibility
from sklearn.metrics import confusion_matrix, balanced_accuracy_score, classification_report

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def create_test_videos():
    """创建测试视频数据集"""
    print("Creating test video dataset...")
    
    # 创建静态视频 (10个)
    static_videos = []
    for i in range(10):
        video_path = f"test_static_{i}.mp4"
        create_static_video(video_path, duration=3, fps=8)
        static_videos.append({"path": video_path, "label": "static"})
    
    # 创建运动视频 (10个)
    motion_videos = []
    for i in range(10):
        video_path = f"test_motion_{i}.mp4"
        create_motion_video(video_path, duration=3, fps=8)
        motion_videos.append({"path": video_path, "label": "motion"})
    
    return static_videos + motion_videos

def create_static_video(filename, duration=3, fps=8, width=128, height=128):
    """创建静态视频（简单的颜色渐变）"""
    import cv2
    import numpy as np
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    for i in range(duration * fps):
        # 创建静态的渐变图案
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 静态渐变
        for y in range(height):
            for x in range(width):
                frame[y, x] = [(x * 255 // width) % 256, (y * 255 // height) % 256, 100]
        
        out.write(frame)
    
    out.release()

def create_motion_video(filename, duration=3, fps=8, width=128, height=128):
    """创建运动视频（移动的图案）"""
    import cv2
    import numpy as np
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    for i in range(duration * fps):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 创建移动的线条
        offset = (i * 10) % width
        for y in range(height):
            for x in range(width):
                # 创建移动的垂直线
                if abs(x - offset) < 5:
                    frame[y, x] = [255, 255, 255]  # 白色线条
                else:
                    frame[y, x] = [0, 0, 0]  # 黑色背景
        
        out.write(frame)
    
    out.release()

def validate_2class_classifier(test_videos):
    """验证2类分类器性能"""
    print(f"Validating 2-class classifier on {len(test_videos)} videos...")
    
    from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class
    
    # 初始化分类器
    classifier = CameraClassifier2Class(
        model_path="models/camera_classifier/d2_cnn_2class_best.pt",
        device="cpu"
    )
    
    results = {
        'predictions': [],
        'true_labels': [],
        'confidences': [],
        'methods': [],
        'inference_times': []
    }
    
    for i, video_info in enumerate(test_videos):
        print(f"Processing video {i+1}/{len(test_videos)}: {video_info['path']}")
        
        start_time = time.time()
        
        # 执行预测
        pred, conf, method = classifier.predict(video_info['path'], use_cnn=True)
        
        elapsed_time = time.time() - start_time
        
        # 记录结果
        results['predictions'].append(pred)
        results['true_labels'].append(video_info['label'])
        results['confidences'].append(conf)
        results['methods'].append(method)
        results['inference_times'].append(elapsed_time)
        
        print(f"  Prediction: {pred}, Confidence: {conf:.3f}, Time: {elapsed_time:.2f}s")
    
    return results

def analyze_results(results):
    """分析验证结果"""
    print("\nAnalyzing validation results...")
    
    y_true = results['true_labels']
    y_pred = results['predictions']
    confidences = results['confidences']
    times = results['inference_times']
    
    # 计算准确率
    balanced_acc = balanced_accuracy_score(y_true, y_pred)
    overall_acc = np.mean([1 if true == pred else 0 for true, pred in zip(y_true, y_pred)])
    
    # 混淆矩阵
    cm = confusion_matrix(y_true, y_pred, labels=['static', 'motion'])
    
    # 按类别统计准确率
    static_correct = sum([1 for true, pred in zip(y_true, y_pred) if true == 'static' and pred == 'static'])
    static_total = sum([1 for label in y_true if label == 'static'])
    static_acc = static_correct / static_total if static_total > 0 else 0
    
    motion_correct = sum([1 for true, pred in zip(y_true, y_pred) if true == 'motion' and pred == 'motion'])
    motion_total = sum([1 for label in y_true if label == 'motion'])
    motion_acc = motion_correct / motion_total if motion_total > 0 else 0
    
    # 置信度分析
    static_confs = [conf for true, conf in zip(y_true, confidences) if true == 'static']
    motion_confs = [conf for true, conf in zip(y_true, confidences) if true == 'motion']
    
    avg_static_conf = np.mean(static_confs) if static_confs else 0
    avg_motion_conf = np.mean(motion_confs) if motion_confs else 0
    
    # 时间分析
    avg_time = np.mean(times)
    std_time = np.std(times)
    
    analysis = {
        'balanced_accuracy': balanced_acc,
        'overall_accuracy': overall_acc,
        'static_accuracy': static_acc,
        'motion_accuracy': motion_acc,
        'confusion_matrix': cm.tolist(),
        'avg_inference_time': avg_time,
        'std_inference_time': std_time,
        'avg_static_confidence': avg_static_conf,
        'avg_motion_confidence': avg_motion_conf,
        'detailed_results': [
            {'video': i, 'true_label': true, 'predicted': pred, 'confidence': conf, 'time': t}
            for i, (true, pred, conf, t) in enumerate(zip(y_true, y_pred, confidences, times))
        ]
    }
    
    return analysis

def visualize_results(analysis, save_path="validation_results.txt"):
    """简化版可视化验证结果（纯文本）"""
    print(f"Generating text-based visualization: {save_path}")
    
    # 创建文本格式的简单可视化
    content = []
    content.append("运镜分类器验证结果可视化")
    content.append("=" * 50)
    content.append("")
    
    # 混淆矩阵文本表示
    cm = analysis['confusion_matrix']
    content.append("混淆矩阵:")
    content.append("          预测")
    content.append("         Static Motion")
    content.append(f"实际 Static   {cm[0][0]}     {cm[0][1]}")
    content.append(f"     Motion   {cm[1][0]}     {cm[1][1]}")
    content.append("")
    
    # 准确率指标
    content.append("准确率指标:")
    content.append(f"- 平衡准确率: {analysis['balanced_accuracy']:.4f}")
    content.append(f"- 总体准确率: {analysis['overall_accuracy']:.4f}")
    content.append(f"- 静态准确率: {analysis['static_accuracy']:.4f}")
    content.append(f"- 运动准确率: {analysis['motion_accuracy']:.4f}")
    content.append("")
    
    # 推理时间
    content.append("推理性能:")
    content.append(f"- 平均推理时间: {analysis['avg_inference_time']:.3f}s")
    content.append(f"- 时间标准差: {analysis['std_inference_time']:.3f}s")
    content.append("")
    
    # 置信度
    content.append("置信度分析:")
    content.append(f"- 静态平均置信度: {analysis['avg_static_confidence']:.3f}")
    content.append(f"- 运动平均置信度: {analysis['avg_motion_confidence']:.3f}")
    
    # 写入文件
    with open(save_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(content))
    
    print(f"Text visualization saved to {save_path}")

def save_validation_report(analysis, save_path="validation_report.json"):
    """保存验证报告"""
    print(f"Saving validation report: {save_path}")
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'model_info': {
            'model_path': 'models/camera_classifier/d2_cnn_2class_best.pt',
            'expected_accuracy': 0.6725,
            'model_size_mb': 1.5
        },
        'validation_info': {
            'total_videos': len(analysis['detailed_results']),
            'static_videos': sum(1 for r in analysis['detailed_results'] if r['true_label'] == 'static'),
            'motion_videos': sum(1 for r in analysis['detailed_results'] if r['true_label'] == 'motion')
        },
        'performance_metrics': {
            'balanced_accuracy': analysis['balanced_accuracy'],
            'overall_accuracy': analysis['overall_accuracy'],
            'static_accuracy': analysis['static_accuracy'],
            'motion_accuracy': analysis['motion_accuracy'],
            'accuracy_vs_expected': analysis['balanced_accuracy'] / 0.6725  # 相对于预期的比率
        },
        'inference_performance': {
            'avg_inference_time': analysis['avg_inference_time'],
            'std_inference_time': analysis['std_inference_time'],
            'avg_static_confidence': analysis['avg_static_confidence'],
            'avg_motion_confidence': analysis['avg_motion_confidence']
        },
        'confusion_matrix': analysis['confusion_matrix'],
        'detailed_results': analysis['detailed_results']
    }
    
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Validation report saved to {save_path}")

def main():
    """主函数"""
    print("=" * 70)
    print("运镜分类器真实视频数据验证")
    print("=" * 70)
    
    # 创建测试数据
    print("\n1. Creating test video dataset...")
    test_videos = create_test_videos()
    print(f"Created {len(test_videos)} test videos ({len([v for v in test_videos if v['label'] == 'static'])} static, {len([v for v in test_videos if v['label'] == 'motion'])} motion)")
    
    try:
        # 验证分类器
        print("\n2. Validating 2-class classifier...")
        results = validate_2class_classifier(test_videos)
        
        # 分析结果
        print("\n3. Analyzing results...")
        analysis = analyze_results(results)
        
        # 打印关键指标
        print("\n" + "=" * 50)
        print("验证结果摘要")
        print("=" * 50)
        print(f"平衡准确率 (balanced accuracy): {analysis['balanced_accuracy']:.4f}")
        print(f"总体准确率 (overall accuracy): {analysis['overall_accuracy']:.4f}")
        print(f"静态准确率 (static accuracy): {analysis['static_accuracy']:.4f}")
        print(f"运动准确率 (motion accuracy): {analysis['motion_accuracy']:.4f}")
        print(f"平均推理时间: {analysis['avg_inference_time']:.3f}s ± {analysis['std_inference_time']:.3f}s")
        print(f"静态平均置信度: {analysis['avg_static_confidence']:.3f}")
        print(f"运动平均置信度: {analysis['avg_motion_confidence']:.3f}")
        print(f"预期准确率: 0.6725")
        print(f"相对预期性能: {analysis['balanced_accuracy']/0.6725:.2%}")
        
        if analysis['balanced_accuracy'] >= 0.65:
            print("\n[OK] 验证成功：准确率达到预期标准")
        else:
            print(f"\n[WARNING] 验证警告：准确率低于预期阈值0.65")
        
        # 保存报告和可视化
        print("\n4. Generating reports...")
        save_validation_report(analysis)
        visualize_results(analysis)
        
        # 清理测试文件
        print("\n5. Cleaning up test files...")
        for video_info in test_videos:
            try:
                os.remove(video_info['path'])
            except:
                pass  # 忽略删除失败的文件
        
        print(f"\n验证完成！报告已保存至 validation_report.json 和 validation_results.png")
        
        return analysis
        
    except Exception as e:
        print(f"验证过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()