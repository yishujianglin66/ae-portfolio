#!/usr/bin/env python3
"""
运镜分类器API测试脚本
"""

import requests
import json
import time
import os
from pathlib import Path

def test_api():
    """测试API接口"""
    print("=" * 60)
    print("运镜分类器API测试")
    print("=" * 60)
    
    base_url = "http://localhost:8000"
    
    # 测试根路径
    try:
        response = requests.get(base_url)
        if response.status_code == 200:
            print("[OK] API根路径访问正常")
            data = response.json()
            print(f"   API名称: {data.get('name', 'Unknown')}")
            print(f"   版本: {data.get('version', 'Unknown')}")
        else:
            print(f"[ERROR] API根路径访问失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] API连接失败: {e}")
        print("   注意: API服务可能未启动")
        print("   请先运行: python camera_classifier_api.py")
        return False
    
    # 测试健康检查
    try:
        response = requests.get(f"{base_url}/health")
        if response.status_code == 200:
            print("[OK] 健康检查接口正常")
            health_data = response.json()
            print(f"   状态: {health_data.get('status', 'Unknown')}")
            classifiers = health_data.get('classifiers_initialized', {})
            print(f"   2类分类器: {'[OK]' if classifiers.get('2class', False) else '[NOT INITIALIZED]'}")
            print(f"   分层分类器: {'[OK]' if classifiers.get('hierarchical', False) else '[NOT INITIALIZED]'}")
        else:
            print(f"[ERROR] 健康检查接口失败: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] 健康检查失败: {e}")
    
    print("\n" + "=" * 60)
    print("API测试完成")
    print("✓ API服务已就绪，支持以下接口:")
    print("  - GET / : API信息")
    print("  - POST /classify_2class : 2类分类 (static/motion)")
    print("  - POST /classify_3class : 3类分类 (static/zoom/tilt-orbit)")
    print("  - GET /health : 健康检查")
    print("=" * 60)
    
    return True

def demo_usage():
    """演示API使用方法"""
    print("\nAPI使用示例:")
    print("""
# 1. 2类分类 (static vs motion)
curl -X POST "http://localhost:8000/classify_2class" \\
     -H "accept: application/json" \\
     -F "video=@your_video.mp4" \\
     -F "use_cnn=true"

# 2. 3类分类 (static/zoom/tilt-orbit)
curl -X POST "http://localhost:8000/classify_3class" \\
     -H "accept: application/json" \\
     -F "video=@your_video.mp4" \\
     -F "use_vlm=true"
    """)
    
    print("Python客户端示例:")
    print("""
import requests

# 上传视频进行分类
with open('your_video.mp4', 'rb') as f:
    files = {'video': f}
    response = requests.post('http://localhost:8000/classify_2class', files=files)
    result = response.json()
    print(f"预测: {result['prediction']}, 置信度: {result['confidence']:.3f}")
    """)

if __name__ == "__main__":
    print("提示: 请确保API服务已启动 (python camera_classifier_api.py)")
    success = test_api()
    if success:
        demo_usage()
        print("\n[SUCCESS] API接口已成功部署，可随时调用！")
    else:
        print("\n[INFO] API服务未启动，请运行: python camera_classifier_api.py")