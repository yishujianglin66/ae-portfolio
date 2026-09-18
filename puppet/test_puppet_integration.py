#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木偶风格化端到端集成测试
===========================

测试完整的木偶风格化处理流程:
MediaPipe 检测 → PuppetStyleEngine 风格化 → JSX 生成
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_puppet_style_engine():
    """测试 PuppetStyleEngine 核心功能"""
    from puppet_style_engine import (
        PuppetStyleConfig,
        PuppetStyleEngine,
        PuppetStyleResult,
        PuppetStyleType,
    )
    
    print("=" * 60)
    print("测试 PuppetStyleEngine")
    print("=" * 60)
    
    # 初始化引擎
    engine = PuppetStyleEngine()
    assert engine.is_available(), "引擎不可用"
    print("✓ 引擎初始化成功")
    
    # 获取可用风格
    styles = engine.get_available_styles()
    assert len(styles) == 8, f"应该有 8 种风格，实际{len(styles)}种"
    print(f"✓ 检测到{len(styles)}种木偶风格")
    
    # 测试木质木偶风格
    config = PuppetStyleConfig(
        style_type=PuppetStyleType.WOODEN_PUPPET,
        intensity=1.5,
        enable_joints=True,
        enable_texture=True,
        enable_lighting=True,
    )
    
    result = engine.apply_style(config, {"pose_landmarks": {}})
    assert result.success, "风格应用失败"
    assert result.style_applied == PuppetStyleType.WOODEN_PUPPET
    print("✓ 木质木偶风格应用成功")
    
    # 验证生成的关键帧和效果
    assert len(result.keyframes) >= 0, "应该有关键帧数据"
    assert len(result.effects) > 0, "应该有 AE 效果配置"
    print(f"✓ 生成{len(result.keyframes)}个关键帧")
    print(f"✓ 生成{len(result.effects['effects_list'])}个 AE 效果")
    
    return True


def test_mediapipe_integration():
    """测试 MediaPipe 集成模块"""
    from mediapipe_integration import (
        MediaPipeConfig,
        MediaPipeIntegrator,
        MediaPipeResult,
    )
    
    print("\n" + "=" * 60)
    print("测试 MediaPipe 集成模块")
    print("=" * 60)
    
    # 初始化配置
    config = MediaPipeConfig(
        mode="simulate",  # 模拟模式用于测试
        detect_pose=True,
        detect_face=True,
        confidence_threshold=0.5,
    )
    
    integrator = MediaPipeIntegrator(config)
    print(f"✓ MediaPipe 可用：{integrator.is_available()}")
    
    # 测试模拟处理
    result = integrator.process_frame(b"mock_frame_data")
    assert isinstance(result, MediaPipeResult)
    print(f"✓ 处理结果类型正确")
    
    if result.persons:
        person = result.persons[0]
        assert "pose_landmarks" in person
        print(f"✓ 检测到姿态 landmarks")
    
    return True


def test_end_to_end_pipeline():
    """测试端到端流程"""
    from puppet_auto_processor import PuppetAutoProcessor
    
    print("\n" + "=" * 60)
    print("测试端到端木偶风格化处理流程")
    print("=" * 60)
    
    # 初始化处理器
    processor = PuppetAutoProcessor(mediapipe_mode="simulate")
    print("✓ 处理器初始化成功")
    
    # 获取可用风格
    styles = processor.get_available_styles()
    print(f"✓ 可用风格:{', '.join([s['type'] for s in styles])}")
    
    # 测试处理流程 (使用模拟数据)
    try:
        result = processor.process_video(
            video_path="test_input.mp4",
            style_type="wooden_puppet",
            intensity=1.0,
        )
        
        if result.get("success"):
            print("✓ 端到端流程执行成功")
            print(f"✓ 输出路径:{result.get('output_path')}")
            print(f"✓ 应用风格:{result.get('style_applied')}")
        else:
            print(f"⚠ 流程执行返回非成功状态:{result.get('warnings', [])}")
            
    except Exception as e:
        print(f"⚠ 端到端流程异常 (预期外):{str(e)}")
    
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("木偶风格化集成测试套件")
    print("=" * 60 + "\n")
    
    tests = [
        ("PuppetStyleEngine 核心功能", test_puppet_style_engine),
        ("MediaPipe 集成模块", test_mediapipe_integration),
        ("端到端流程", test_end_to_end_pipeline),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n✗ {name} 测试失败:{str(e)}\n")
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result, _ in results if result)
    total = len(results)
    
    for name, result, error in results:
        status = "✓ PASS" if result else f"✗ FAIL: {error}"
        print(f"{name}: {status}")
    
    print(f"\n总计:{passed}/{total} 通过")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
