#!/usr/bin/env python3
"""
模型接入管线集成测试

展示风格分类器如何被analyze阶段调用，参数优化器如何被plan阶段调用。

调用链路：
1. 输入视频特征 → StyleClassifier → 风格标签
2. 风格标签 + 基础参数 → ParamOptimizer → 优化参数
3. 优化参数 → AE Compiler → JSX脚本
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.model_service import model_service, classify_style, optimize_params


def extract_video_features(video_path: str) -> List[float]:
    """模拟：从视频提取特征
    
    实际应该调用：
    - analyze_video_vision.py 进行视觉分析
    - audio-analyzer.py 进行音频分析
    - video_effect_analyzer_v2.py 进行效果分析
    
    这里返回模拟的24维特征。
    """
    import random
    
    # 基础特征 (7维)
    brightness = random.uniform(0.3, 0.7)
    saturation = random.uniform(0.4, 0.8)
    warmth = random.uniform(0.3, 0.6)
    cut_rate = random.uniform(0.1, 0.9)  # 快剪vs慢剪
    avg_shot_duration = random.uniform(0.5, 10.0)
    resolution_width = random.choice([1920, 3840])
    resolution_height = random.choice([1080, 2160])
    
    # 漫剪专属特征 (7维)
    bpm = random.uniform(60, 180)
    zoom_intensity = random.uniform(0, 1)
    rotation_angle = random.uniform(-45, 45)
    shutter_angle = random.uniform(180, 360)
    motion_blur_enabled = random.choice([0, 1])
    dynamic_tile_enabled = random.choice([0, 1])
    beat_sync_strength = random.uniform(0, 1)
    
    # 高级特征 (6维)
    keyframes_density = random.uniform(0, 1)
    motion_trajectory_complexity = random.uniform(0, 1)
    color_vibrancy = random.uniform(0, 1)
    contrast_ratio = random.uniform(0.5, 1.5)
    edge_detection_strength = random.uniform(0, 1)
    depth_of_field = random.uniform(0, 1)
    
    # 时序特征 (4维)
    shot_transition_diversity = random.uniform(0, 1)
    rhythm_consistency = random.uniform(0, 1)
    frame_rate_variation = random.uniform(0, 1)
    visual_complexity = random.uniform(0, 1)
    
    return [
        brightness, saturation, warmth, cut_rate, avg_shot_duration,
        resolution_width / 3840, resolution_height / 2160,  # 归一化
        bpm / 180, zoom_intensity, rotation_angle / 45, shutter_angle / 360,
        motion_blur_enabled, dynamic_tile_enabled, beat_sync_strength,
        keyframes_density, motion_trajectory_complexity, color_vibrancy,
        contrast_ratio, edge_detection_strength, depth_of_field,
        shot_transition_diversity, rhythm_consistency, frame_rate_variation, visual_complexity,
    ]


def analyze_stage(video_path: str) -> Dict[str, Any]:
    """分析阶段：调用风格分类器"""
    print(f"\n[ANALYZE] 分析视频: {video_path}")
    
    start_time = time.time()
    
    # 1. 提取特征
    features = extract_video_features(video_path)
    print(f"  特征提取完成: {len(features)}维")
    
    # 2. 调用风格分类器
    result = classify_style(features)
    
    analyze_time = (time.time() - start_time) * 1000
    
    if result.get("error"):
        print(f"  风格分类失败: {result['error']}")
        return {"error": result["error"]}
    
    print(f"  预测风格: {result['label']}")
    print(f"  置信度: {result['confidence']:.4f}")
    print(f"  Top-3风格: {sorted(result['probabilities'].items(), key=lambda x: -x[1])[:3]}")
    print(f"  推理延迟: {result['latency_ms']:.2f}ms")
    print(f"  总耗时: {analyze_time:.2f}ms")
    
    return {
        "style": result["label"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
        "features": features,
        "latency_ms": result["latency_ms"],
        "total_ms": analyze_time,
    }


def plan_stage(analyze_result: Dict[str, Any]) -> Dict[str, Any]:
    """规划阶段：调用参数优化器"""
    print(f"\n[PLAN] 基于风格规划参数")
    
    start_time = time.time()
    
    style = analyze_result.get("style", "cinematic")
    
    # 基础参数（模拟）
    base_params = {
        "zoom_intensity": 0.5,
        "motion_blur": 0.3,
        "cut_rate": 0.5,
        "contrast": 1.0,
        "saturation": 1.0,
        "shake_intensity": 0.2,
        "bpm_sync": 0.5,
        "pulse_intensity": 0.3,
        "edge_intensity": 0.5,
        "color_shift": 0.1,
    }
    
    # 调用参数优化器
    result = optimize_params(style, base_params)
    
    plan_time = (time.time() - start_time) * 1000
    
    if result.get("error"):
        print(f"  参数优化失败: {result['error']}")
        return {"error": result["error"], "params": base_params}
    
    print(f"  输入风格: {style}")
    print(f"  优化参数: {result['optimized_params']}")
    print(f"  延迟: {result['latency_ms']:.2f}ms")
    print(f"  总耗时: {plan_time:.2f}ms")
    
    return {
        "style": style,
        "params": result["optimized_params"],
        "latency_ms": result["latency_ms"],
        "total_ms": plan_time,
    }


def execute_stage(plan_result: Dict[str, Any]) -> Dict[str, Any]:
    """执行阶段：生成AE脚本（未来可接入JSX生成器）"""
    print(f"\n[EXECUTE] 生成AE脚本")
    
    # 当前使用compiler原子编译器
    # 未来可接入JSX生成器
    style = plan_result.get("style", "cinematic")
    params = plan_result.get("params", {})
    
    # 生成简单的JSX片段
    jsx_snippet = f"""// 风格: {style}
// 由模型服务层自动生成

var comp = app.project.activeItem;
if (comp) {{
    // 应用参数
    var zoomIntensity = {params.get('zoom_intensity', 0.5)};
    var motionBlur = {params.get('motion_blur', 0.3)};
    
    // TODO: 根据风格应用具体效果
}}
"""
    
    print(f"  生成JSX片段 ({len(jsx_snippet)}字节)")
    
    return {
        "jsx": jsx_snippet,
        "style": style,
        "params": params,
    }


def run_pipeline(video_path: str) -> Dict[str, Any]:
    """运行完整管线"""
    print("=" * 60)
    print("模型接入管线测试")
    print("=" * 60)
    
    pipeline_start = time.time()
    
    # 1. 分析阶段
    analyze_result = analyze_stage(video_path)
    if analyze_result.get("error"):
        return {"error": "分析阶段失败", "details": analyze_result}
    
    # 2. 规划阶段
    plan_result = plan_stage(analyze_result)
    if plan_result.get("error"):
        return {"error": "规划阶段失败", "details": plan_result}
    
    # 3. 执行阶段
    execute_result = execute_stage(plan_result)
    
    pipeline_time = (time.time() - pipeline_start) * 1000
    
    # 汇总
    print(f"\n{'='*60}")
    print("管线执行完成")
    print("=" * 60)
    print(f"  风格: {analyze_result['style']}")
    print(f"  置信度: {analyze_result['confidence']:.4f}")
    print(f"  总耗时: {pipeline_time:.2f}ms")
    
    # 模型服务统计
    stats = model_service.get_stats()
    print(f"\n模型服务统计:")
    print(f"  风格分类调用: {stats['style_classify_calls']}次")
    print(f"  参数优化调用: {stats['param_optim_calls']}次")
    print(f"  平均延迟(分类): {stats['style_classify_avg_ms']:.2f}ms")
    print(f"  平均延迟(优化): {stats['param_optim_avg_ms']:.2f}ms")
    
    return {
        "analyze": analyze_result,
        "plan": plan_result,
        "execute": execute_result,
        "pipeline_time_ms": pipeline_time,
    }


if __name__ == "__main__":
    # 测试多个视频
    test_videos = [
        "test_video_001.mp4",
        "test_video_002.mp4",
        "test_video_003.mp4",
    ]
    
    results = []
    for video in test_videos:
        result = run_pipeline(video)
        results.append(result)
        print()
    
    # 最终统计
    print("=" * 60)
    print("最终统计")
    print("=" * 60)
    final_stats = model_service.get_stats()
    for k, v in final_stats.items():
        print(f"  {k}: {v}")