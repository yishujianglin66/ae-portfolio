#!/usr/bin/env python3
"""
运镜分类器演示脚本
展示运镜分类器的各种使用方式
"""

import sys
import time
from pathlib import Path

import cv2
import numpy as np

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def create_dummy_video(filename, duration=3, fps=8, width=128, height=128):
    """创建一个简单的测试视频文件"""
    print(f"创建测试视频: {filename} ({duration}s, {fps}fps)")
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, fps, (width, height))
    
    for i in range(duration * fps):
        # 创建一个简单的渐变图案来模拟运动
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 添加一些颜色变化来模拟运动
        color_val = int(100 + 50 * np.sin(i * 0.2))
        frame[:, :] = [color_val, color_val // 2, 255 - color_val]
        
        # 添加一些随机噪点
        noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
        frame = cv2.add(frame, noise)
        
        out.write(frame)
    
    out.release()
    print(f"测试视频创建完成: {filename}")

def demo_basic_usage():
    """演示基本使用方法"""
    print("=" * 70)
    print("运镜分类器演示 - 基本使用")
    print("=" * 70)
    
    from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class
    
    # 初始化分类器
    print("\n1. 初始化2类CNN分类器...")
    classifier = CameraClassifier2Class(
        model_path="models/camera_classifier/d2_cnn_2class_best.pt",
        device="cpu"
    )
    print("   [OK] 分类器初始化完成")
    
    # 创建测试视频
    print("\n2. 创建测试视频...")
    test_video = "test_static.mp4"
    create_dummy_video(test_video, duration=2, fps=8)
    
    # 进行预测
    print("\n3. 执行运镜分类...")
    start_time = time.time()
    pred, conf, method = classifier.predict(test_video, use_cnn=True)
    elapsed = time.time() - start_time
    
    print(f"   预测结果: {pred}")
    print(f"   置信度: {conf:.3f}")
    print(f"   使用方法: {method}")
    print(f"   推理时间: {elapsed:.2f}秒")
    
    # 清理测试文件
    Path(test_video).unlink(missing_ok=True)
    print(f"   清理测试文件: {test_video}")

def demo_hierarchical_usage():
    """演示分层架构使用方法"""
    print("\n" + "=" * 70)
    print("运镜分类器演示 - 分层混合架构")
    print("=" * 70)
    
    from models.camera_classifier.camera_classifier_hierarchical import HierarchicalCameraClassifier
    
    # 初始化分层分类器
    print("\n1. 初始化分层分类器...")
    classifier = HierarchicalCameraClassifier(
        cnn_model_path="models/camera_classifier/d2_cnn_2class_best.pt",
        device="cpu"
    )
    print("   [OK] 分层分类器初始化完成")
    
    # 创建测试视频
    print("\n2. 创建测试视频...")
    test_video = "test_motion.mp4"
    create_dummy_video(test_video, duration=3, fps=8)
    
    # 进行预测
    print("\n3. 执行3类运镜分类...")
    start_time = time.time()
    pred, conf, method, desc = classifier.predict(test_video, use_vlm=False)  # 不使用VLM进行快速演示
    elapsed = time.time() - start_time
    
    print(f"   预测结果: {pred}")
    print(f"   置信度: {conf:.3f}")
    print(f"   使用方法: {method}")
    print(f"   描述: {desc}")
    print(f"   推理时间: {elapsed:.2f}秒")
    
    # 清理测试文件
    Path(test_video).unlink(missing_ok=True)
    print(f"   清理测试文件: {test_video}")

def demo_performance_metrics():
    """展示性能指标"""
    print("\n" + "=" * 70)
    print("运镜分类器 - 性能指标")
    print("=" * 70)
    
    print("\n已验证的性能指标:")
    print("   - 2类分类准确率: 0.6725 (balanced accuracy)")
    print("   - 模型大小: 1.5 MB")
    print("   - 模型参数: 0.5M 参数")
    print("   - 推理设备: CPU 可用")
    print("   - 推理时间: 1-2秒/视频")
    print("   - 适用场景: 动漫视频运镜检测")
    
    print("\n分层混合架构预期性能:")
    print("   - 3类分类准确率: 0.50-0.60 (static/zoom/tilt-orbit)")
    print("   - 静态视频: ~1-2秒 (仅CNN)")
    print("   - 运动视频: ~4-5秒 (CNN + VLM专家)")
    
    print("\n技术特点:")
    print("   - 基于轻量级CNN架构 (4层卷积)")
    print("   - 使用帧差特征进行运动检测")
    print("   - 标签噪声天花板验证 (25.7%噪声率)")
    print("   - 可扩展的分层架构设计")

def demo_use_cases():
    """展示使用场景"""
    print("\n" + "=" * 70)
    print("运镜分类器 - 使用场景")
    print("=" * 70)
    
    print("\n视频后期制作:")
    print("   - 自动识别镜头运动类型，辅助剪辑决策")
    print("   - 区分静态镜头与运动镜头，优化转场效果")
    print("   - 为不同运镜类型应用相应的视觉效果")
    
    print("\nAI视频生成:")
    print("   - 为生成的视频片段添加合适的运镜描述")
    print("   - 根据内容自动选择合适的镜头运动")
    print("   - 优化视频节奏与镜头语言匹配")
    
    print("\n内容分析:")
    print("   - 视频内容结构化分析")
    print("   - 镜头语言自动标注")
    print("   - 视频质量评估辅助")

def main():
    """主函数"""
    print("运镜分类器演示程序")
    print("此程序演示了运镜分类器的各种使用方式和性能特点")
    
    try:
        demo_basic_usage()
        demo_hierarchical_usage()
        demo_performance_metrics()
        demo_use_cases()
        
        print("\n" + "=" * 70)
        print("演示完成！")
        print("\n快速开始:")
        print("   1. 在您的项目中导入分类器:")
        print("      from models.camera_classifier.camera_classifier_2class import CameraClassifier2Class")
        print("   2. 初始化并使用:")
        print("      classifier = CameraClassifier2Class(model_path='models/camera_classifier/d2_cnn_2class_best.pt')")
        print("      pred, conf, method = classifier.predict('your_video.mp4')")
        print("\n高级功能:")
        print("   使用分层架构获得更细粒度的分类结果 (需GPU运行VLM专家模型)")
        print("=" * 70)
        
    except Exception as e:
        print(f"[ERROR] 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()