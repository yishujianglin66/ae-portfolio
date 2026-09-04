#!/usr/bin/env python3
"""
运镜分类器推理速度与资源优化脚本
针对2类CNN分类器进行性能优化
"""

import sys
import os
import time
import numpy as np
import cv2
import torch
from core.torch_runtime import infer_ctx
import psutil
from pathlib import Path
from typing import Tuple, List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def create_test_video(filename, duration=3, fps=8, width=128, height=128):
    """创建测试视频"""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    for i in range(duration * fps):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 创建一些动态图案
        color_val = int(100 + 50 * np.sin(i * 0.2))
        frame[:, :] = [color_val, color_val // 2, 255 - color_val]
        
        # 添加一些随机噪点
        noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)
        
        out.write(frame)
    
    out.release()

def benchmark_original_classifier(video_path: str, model_path: str) -> Tuple[float, float]:
    """基准测试：原始分类器性能"""
    from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class
    
    # 初始化分类器
    classifier = CameraClassifier2Class(
        model_path=model_path,
        device="cpu"
    )
    
    # 预热
    for _ in range(3):
        classifier.predict(video_path, use_cnn=True)
    
    # 性能测试
    times = []
    memory_usages = []
    
    for _ in range(10):
        # 记录内存使用
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        start_time = time.time()
        pred, conf, method = classifier.predict(video_path, use_cnn=True)
        elapsed = time.time() - start_time
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        
        times.append(elapsed)
        memory_usages.append(mem_after - mem_before)
    
    avg_time = np.mean(times)
    avg_memory = np.mean(memory_usages)
    
    return avg_time, avg_memory

def optimize_frame_extraction(video_path: str, n_frames: int = 8) -> List[np.ndarray]:
    """优化的帧提取方法"""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")
    
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # 如果视频太短，重复最后一帧
    if total_frames < n_frames:
        frames = []
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        while len(frames) < n_frames:
            frames.append(frames[-1])
        cap.release()
        return frames[:n_frames]
    
    # 优化的均匀采样
    indices = np.linspace(0, total_frames - 1, n_frames, dtype=int)
    frames = []
    
    # 按顺序读取，减少seek操作
    current_frame = 0
    for target_idx in sorted(set(indices)):
        while current_frame <= target_idx:
            ret, frame = cap.read()
            if not ret:
                break
            current_frame += 1
        
        if ret and current_frame - 1 == target_idx:
            frames.append(frame.copy())
    
    # 按原始顺序排列
    ordered_frames = []
    for orig_idx in indices:
        # 找到对应帧
        found_idx = np.where(sorted(set(indices)) == orig_idx)[0][0] if orig_idx in sorted(set(indices)) else -1
        if found_idx >= 0 and found_idx < len(frames):
            ordered_frames.append(frames[found_idx])
        else:
            # 如果找不到，使用最后一帧
            ordered_frames.append(frames[-1] if frames else frames[0])
    
    cap.release()
    return ordered_frames

def optimized_predict(video_path: str, model_path: str) -> Tuple[str, float, str]:
    """优化的预测函数"""
    from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class, SmallMotionCNN
    import torch.nn.functional as F
    
    # 加载模型
    device = torch.device('cpu')
    model = SmallMotionCNN().to(device)
    state_dict = torch.load(model_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    
    # 优化的帧提取
    frames = optimize_frame_extraction(video_path, n_frames=8)
    
    # 预处理
    processed = []
    for frame in frames:
        # 一次性resize和转换
        frame_resized = cv2.resize(frame, (128, 128))
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        frame_float = frame_rgb.astype(np.float32) / 255.0
        frame_normalized = (frame_float - 0.5) / 0.5
        frame_chw = np.transpose(frame_normalized, (2, 0, 1))
        processed.append(frame_chw)
    
    frames_tensor = np.stack(processed)
    
    # 计算帧差
    diffs = np.abs(frames_tensor[1:] - frames_tensor[:-1])
    avg_diff = diffs.mean(axis=0, keepdims=True)
    
    # 推理
    input_tensor = torch.from_numpy(avg_diff).float().to(device)
    
    with infer_ctx(device):
        output = model(input_tensor)
        probs = torch.softmax(output, dim=1)[0]
        pred_idx = probs.argmax().item()
        confidence = probs[pred_idx].item()
    
    labels = ['static', 'motion']
    return labels[pred_idx], confidence, 'optimized_cnn'

def benchmark_optimized_classifier(video_path: str, model_path: str) -> Tuple[float, float]:
    """基准测试：优化后分类器性能"""
    
    # 预热
    for _ in range(3):
        optimized_predict(video_path, model_path)
    
    # 性能测试
    times = []
    memory_usages = []
    
    for _ in range(10):
        # 记录内存使用
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        start_time = time.time()
        pred, conf, method = optimized_predict(video_path, model_path)
        elapsed = time.time() - start_time
        
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        
        times.append(elapsed)
        memory_usages.append(mem_after - mem_before)
    
    avg_time = np.mean(times)
    avg_memory = np.mean(memory_usages)
    
    return avg_time, avg_memory

def test_batch_inference(video_path: str, model_path: str, batch_sizes: List[int] = [1, 5, 10]):
    """测试批处理推理性能"""
    from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class
    import torch
    
    results = {}
    
    for batch_size in batch_sizes:
        print(f"Testing batch size: {batch_size}")
        
        # 创建批次视频（复制同一个视频）
        batch_video_paths = [video_path] * batch_size
        
        # 初始化分类器
        classifier = CameraClassifier2Class(
            model_path=model_path,
            device="cpu"
        )
        
        # 预热
        for _ in range(2):
            for path in batch_video_paths[:min(2, len(batch_video_paths))]:
                classifier.predict(path, use_cnn=True)
        
        # 测试批处理性能
        times = []
        for _ in range(5):  # 减少测试次数以节省时间
            start_time = time.time()
            for path in batch_video_paths:
                pred, conf, method = classifier.predict(path, use_cnn=True)
            elapsed = time.time() - start_time
            times.append(elapsed)
        
        avg_time = np.mean(times)
        avg_time_per_video = avg_time / batch_size
        
        results[batch_size] = {
            'total_time': avg_time,
            'time_per_video': avg_time_per_video,
            'throughput': batch_size / avg_time
        }
        
        print(f"  Batch {batch_size}: {avg_time_per_video:.3f}s per video, {results[batch_size]['throughput']:.1f} videos/sec")
    
    return results

def main():
    """主函数"""
    print("=" * 70)
    print("运镜分类器推理速度与资源优化测试")
    print("=" * 70)
    
    model_path = "models/camera_classifier/d2_cnn_2class_best.pt"
    
    # 创建测试视频
    print("\n1. Creating test video...")
    test_video = "perf_test_video.mp4"
    create_test_video(test_video, duration=3, fps=8)
    print(f"Test video created: {test_video}")
    
    try:
        # 原始性能基准测试
        print("\n2. Running original classifier benchmark...")
        orig_avg_time, orig_avg_memory = benchmark_original_classifier(test_video, model_path)
        print(f"Original classifier: {orig_avg_time:.3f}s avg, {orig_avg_memory:.1f}MB avg")
        
        # 优化后性能基准测试
        print("\n3. Running optimized classifier benchmark...")
        opt_avg_time, opt_avg_memory = benchmark_optimized_classifier(test_video, model_path)
        print(f"Optimized classifier: {opt_avg_time:.3f}s avg, {opt_avg_memory:.1f}MB avg")
        
        # 性能对比
        time_improvement = ((orig_avg_time - opt_avg_time) / orig_avg_time) * 100
        memory_improvement = ((orig_avg_memory - opt_avg_memory) / orig_avg_memory) * 100
        
        print(f"\nPerformance improvements:")
        print(f"  Time: {time_improvement:+.1f}% ({orig_avg_time:.3f}s → {opt_avg_time:.3f}s)")
        print(f"  Memory: {memory_improvement:+.1f}% ({orig_avg_memory:.1f}MB → {opt_avg_memory:.1f}MB)")
        
        # 批处理测试
        print("\n4. Running batch inference test...")
        batch_results = test_batch_inference(test_video, model_path, [1, 3, 5, 8])
        
        # 生成优化报告
        print("\n" + "=" * 50)
        print("优化结果报告")
        print("=" * 50)
        print(f"目标: <1秒/视频 (当前: {orig_avg_time:.3f}s → {opt_avg_time:.3f}s)")
        print(f"内存占用: <500MB (当前: {opt_avg_memory:.1f}MB)")
        print(f"批处理吞吐量: {batch_results[5]['throughput']:.1f} 视频/秒 (batch=5)")
        
        success_flags = {
            'time_target': bool(opt_avg_time < 1.0),
            'memory_target': bool(opt_avg_memory < 500.0),
            'improvement': bool(time_improvement > 0)
        }
        
        print(f"\n优化目标达成情况:")
        print(f"  时间目标(<1s): {'[OK]' if success_flags['time_target'] else '[FAIL]'}")
        print(f"  内存目标(<500MB): {'[OK]' if success_flags['memory_target'] else '[FAIL]'}")
        print(f"  性能提升: {'[OK]' if success_flags['improvement'] else '[FAIL]'}")
        
        if success_flags['time_target']:
            print(f"\n[OK] 推理速度优化成功：达到<1秒/视频的目标")
        else:
            print(f"\n[WARNING] 推理速度未达到<1秒目标")
        
        # 保存优化报告
        optimization_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'optimization_targets': {
                'target_time_per_video': '<1.0s',
                'target_memory_usage': '<500MB',
                'batch_throughput_goal': '>10 videos/sec'
            },
            'benchmark_results': {
                'original': {
                    'avg_time_per_video': orig_avg_time,
                    'avg_memory_usage_mb': orig_avg_memory
                },
                'optimized': {
                    'avg_time_per_video': opt_avg_time,
                    'avg_memory_usage_mb': opt_avg_memory
                }
            },
            'improvements': {
                'time_improvement_percent': time_improvement,
                'memory_improvement_percent': memory_improvement,
                'achieved_targets': success_flags
            },
            'batch_performance': batch_results,
            'recommendations': [
                "当前已优化：帧提取算法、预处理流程",
                "进一步优化建议：模型量化(INT8/FP16)、TensorRT加速",
                "批处理可提升吞吐量，适合大规模数据处理"
            ]
        }
        
        import json
        with open('optimization_report.json', 'w', encoding='utf-8') as f:
            json.dump(optimization_report, f, indent=2, ensure_ascii=False)
        
        print(f"\n优化报告已保存至 optimization_report.json")
        
        # 清理测试文件
        try:
            os.remove(test_video)
            print(f"Cleaned up test file: {test_video}")
        except:
            pass
        
        return optimization_report
        
    except Exception as e:
        print(f"优化测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main()