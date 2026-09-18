#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1 端到端流水线 - 实机验证脚本

运行前置条件：
1. Adobe After Effects 2025 已启动
2. 在 AE 中运行 ae_mcp_listener.jsx（File -> Scripts -> Run Script File）
3. 确保有测试素材（音乐和视频片段）

使用方法：
    python tests/test_phase1_real_ae.py
    python tests/test_phase1_real_ae.py --step 1
    python tests/test_phase1_real_ae.py --full
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_command_generator import AECommandGenerator
from ae_mcp_client import AECommandClient

from ae_agent_pipeline import AEAgentPipeline

# ==================== 配置 ====================

TEST_MUSIC_DIR = r"D:\AE-Work\音频素材库\BGM"
TEST_CLIP_DIR = r"D:\AE-Work\视频素材库"
OUTPUT_DIR = r"D:\AE-Work\输出"

# ============================================


def print_header(title):
    """打印标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def print_step(step_num, total, title):
    """打印步骤标题"""
    print(f"\n  [{step_num}/{total}] {title}")
    print("  " + "-"*50)


def check_environment():
    """检查运行环境"""
    print_header("环境检查")
    
    issues = []
    
    # 检查音乐目录
    if os.path.exists(TEST_MUSIC_DIR):
        music_files = [f for f in os.listdir(TEST_MUSIC_DIR) if f.endswith((".mp3", ".m4a", ".wav"))]
        print(f"  ✅ 音乐目录存在: {TEST_MUSIC_DIR}")
        print(f"     找到 {len(music_files)} 个音乐文件")
    else:
        print(f"  ❌ 音乐目录不存在: {TEST_MUSIC_DIR}")
        issues.append("音乐目录不存在")
        music_files = []
    
    # 检查视频目录
    if os.path.exists(TEST_CLIP_DIR):
        clip_files = [f for f in os.listdir(TEST_CLIP_DIR) if f.endswith((".mp4", ".mov", ".avi"))]
        print(f"  ✅ 视频目录存在: {TEST_CLIP_DIR}")
        print(f"     找到 {len(clip_files)} 个视频文件")
    else:
        print(f"  ❌ 视频目录不存在: {TEST_CLIP_DIR}")
        issues.append("视频目录不存在")
        clip_files = []
    
    # 检查命令文件目录
    cmd_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ae_command.json")
    res_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ae_result.json")
    print(f"  ℹ️  命令文件: {cmd_file}")
    print(f"  ℹ️  结果文件: {res_file}")
    
    # 检查签名密钥
    secret_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "mcp_secret")
    if os.path.exists(secret_file):
        print("  ✅ 签名密钥文件存在")
    else:
        print("  ⚠️  签名密钥文件不存在（测试将关闭签名验证）")
    
    print(f"\n  环境检查完成: {'通过' if not issues else '发现 ' + str(len(issues)) + ' 个问题'}")
    
    return music_files, clip_files


def step_test_create_comp(client, comp_name):
    """Step 1: 测试创建合成"""
    print_step(1, 6, "测试创建合成")
    
    result = client.send_command("createComposition", {
        "name": comp_name,
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
        "backgroundColor": [20, 20, 30]
    })
    
    success = result.get("success") or result.get("status") == "success"
    if success:
        print("  ✅ 合成创建成功")
        print(f"     消息: {result.get('message', '')}")
    else:
        print("  ❌ 合成创建失败")
        print(f"     错误: {result.get('message', result.get('error', 'Unknown'))}")
    
    return success


def step_test_import_footage(client, clip_files):
    """Step 2: 测试导入素材"""
    print_step(2, 6, "测试导入素材")
    
    if not clip_files:
        print("  ⚠️  无可用视频素材，跳过")
        return True, None
    
    clip_path = os.path.join(TEST_CLIP_DIR, clip_files[0])
    print(f"  导入文件: {clip_files[0]}")
    
    result = client.send_command("importFootage", {
        "filePath": clip_path
    })
    
    success = result.get("success") or result.get("status") == "success"
    if success:
        print("  ✅ 素材导入成功")
        print(f"     消息: {result.get('message', '')}")
    else:
        print("  ❌ 素材导入失败")
        print(f"     错误: {result.get('message', result.get('error', 'Unknown'))}")
    
    return success, clip_path


def step_test_place_footage(client, comp_name, clip_path):
    """Step 3: 测试放置素材"""
    print_step(3, 6, "测试放置素材到合成")
    
    result = client.send_command("placeFootageInComp", {
        "compName": comp_name,
        "layerName": "Test_Video",
        "footagePath": clip_path,
        "startTime": 0
    })
    
    success = result.get("success") or result.get("status") == "success"
    if success:
        print("  ✅ 素材放置成功")
        print(f"     消息: {result.get('message', '')}")
    else:
        print("  ❌ 素材放置失败")
        print(f"     错误: {result.get('message', result.get('error', 'Unknown'))}")
    
    return success


def step_test_apply_effect(client, comp_name):
    """Step 4: 测试应用效果"""
    print_step(4, 6, "测试应用效果")
    
    result = client.send_command("applyEffect", {
        "compName": comp_name,
        "layerName": "Test_Video",
        "effectMatchName": "ADBE Glo2",
        "effectSettings": {
            "Glow Radius": 50,
            "Glow Intensity": 2.0
        }
    })
    
    success = result.get("success") or result.get("status") == "success"
    if success:
        print("  ✅ 效果应用成功")
        print(f"     消息: {result.get('message', '')}")
    else:
        print("  ❌ 效果应用失败")
        print(f"     错误: {result.get('message', result.get('error', 'Unknown'))}")
    
    return success


def step_test_set_keyframe(client, comp_name):
    """Step 5: 测试设置关键帧"""
    print_step(5, 6, "测试设置关键帧")
    
    # 设置两个不透明度关键帧
    result1 = client.send_command("setLayerKeyframe", {
        "compName": comp_name,
        "layerName": "Test_Video",
        "propertyName": "Opacity",
        "timeInSeconds": 0,
        "value": 0,
        "easeType": "easeInOut"
    })
    
    client.clear_result()
    
    result2 = client.send_command("setLayerKeyframe", {
        "compName": comp_name,
        "layerName": "Test_Video",
        "propertyName": "Opacity",
        "timeInSeconds": 2,
        "value": 100,
        "easeType": "easeInOut"
    })
    
    success1 = result1.get("success") or result1.get("status") == "success"
    success2 = result2.get("success") or result2.get("status") == "success"
    success = success1 and success2
    
    if success:
        print("  ✅ 关键帧设置成功（2个关键帧）")
        print(f"     消息: {result2.get('message', '')}")
    else:
        print("  ❌ 关键帧设置失败")
        print(f"     KF1: {result1.get('message', result1.get('error', ''))}")
        print(f"     KF2: {result2.get('message', result2.get('error', ''))}")
    
    return success


def step_test_render(client, comp_name):
    """Step 6: 测试渲染"""
    print_step(6, 6, "测试渲染合成")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"phase1_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
    
    print(f"  输出路径: {output_path}")
    
    result = client.send_command("renderComposition", {
        "compName": comp_name,
        "outputPath": output_path,
        "format": "mp4",
        "quality": "high"
    })
    
    success = result.get("success") or result.get("status") == "success"
    if success:
        print("  ✅ 渲染已启动")
        print(f"     消息: {result.get('message', '')}")
    else:
        print("  ❌ 渲染启动失败")
        print(f"     错误: {result.get('message', result.get('error', 'Unknown'))}")
    
    return success


def run_step_by_step(music_files, clip_files):
    """分步运行测试"""
    print_header("分步测试模式")
    
    client = AECommandClient(signature_enabled=False)
    
    comp_name = f"Phase1_StepTest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    results = []
    
    # Step 1: 创建合成
    r = step_test_create_comp(client, comp_name)
    results.append(("创建合成", r))
    if not r:
        print("\n  ❌ 第一步失败，终止测试")
        return results
    client.clear_result()
    
    # Step 2: 导入素材
    if clip_files:
        r, clip_path = step_test_import_footage(client, clip_files)
        results.append(("导入素材", r))
        if not r:
            print("\n  ⚠️  素材导入失败，后续步骤可能受影响")
        client.clear_result()
    else:
        print("\n  ⚠️  无视频素材，跳过素材相关测试")
        results.append(("导入素材", None))
        clip_path = None
    
    # Step 3: 放置素材
    if clip_path:
        r = step_test_place_footage(client, comp_name, clip_path)
        results.append(("放置素材", r))
        client.clear_result()
    else:
        results.append(("放置素材", None))
    
    # Step 4: 应用效果
    if clip_path:
        r = step_test_apply_effect(client, comp_name)
        results.append(("应用效果", r))
        client.clear_result()
    else:
        results.append(("应用效果", None))
    
    # Step 5: 设置关键帧
    if clip_path:
        r = step_test_set_keyframe(client, comp_name)
        results.append(("设置关键帧", r))
        client.clear_result()
    else:
        results.append(("设置关键帧", None))
    
    # Step 6: 渲染
    r = step_test_render(client, comp_name)
    results.append(("渲染合成", r))
    
    # 总结
    print_header("测试总结")
    passed = sum(1 for _, r in results if r is True)
    total = sum(1 for _, r in results if r is not None)
    print(f"\n  通过: {passed}/{total}")
    for name, r in results:
        status = "✅ 通过" if r else ("❌ 失败" if r is False else "⏭️  跳过")
        print(f"    {status} - {name}")
    
    return results


def run_full_pipeline(music_files, clip_files):
    """运行完整流水线测试"""
    print_header("完整流水线测试")
    
    if not music_files:
        print("  ❌ 无音乐文件，无法运行完整流水线")
        return
    
    if not clip_files:
        print("  ❌ 无视频文件，无法运行完整流水线")
        return
    
    music_path = os.path.join(TEST_MUSIC_DIR, music_files[0])
    clip_paths = [os.path.join(TEST_CLIP_DIR, f) for f in clip_files[:min(3, len(clip_files))]]
    
    print(f"\n  🎵 音乐: {music_files[0]}")
    print(f"  📹 视频片段: {len(clip_paths)} 个")
    for i, p in enumerate(clip_paths):
        print(f"      {i+1}. {os.path.basename(p)}")
    
    print("\n  启动流水线...")
    start_time = time.time()
    
    pipeline = AEAgentPipeline()
    
    result = pipeline.run_pipeline(
        music_path=music_path,
        clip_paths=clip_paths,
        user_prompt="Create a dynamic and exciting video edit",
        style_preset="cinematic"
    )
    
    elapsed = time.time() - start_time
    
    # 输出结果
    print(f"\n  耗时: {elapsed:.2f} 秒")
    print(f"  总体: {'✅ 成功' if result.get('overall_success') else '❌ 失败'}")
    
    if result.get("execution"):
        exec_result = result["execution"]
        if hasattr(exec_result, 'output_path'):
            print(f"  输出: {exec_result.output_path}")
        if hasattr(exec_result, 'steps_completed'):
            print(f"  完成步骤: {exec_result.steps_completed}/{exec_result.total_steps}")
    
    # 保存详细结果
    output_file = os.path.join(
        OUTPUT_DIR,
        f"phase1_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 转换为可序列化格式
    serializable = {}
    for key, value in result.items():
        if hasattr(value, '__dict__'):
            serializable[key] = value.__dict__
        else:
            serializable[key] = str(value)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n  📄 详细结果已保存: {output_file}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Phase 1 实机验证脚本")
    parser.add_argument("--step", type=int, help="运行指定步骤（1-6）")
    parser.add_argument("--full", action="store_true", help="运行完整流水线测试")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    args = parser.parse_args()
    
    print_header("Phase 1 端到端流水线 - 实机验证")
    print(f"\n  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 环境检查
    music_files, clip_files = check_environment()
    
    if args.step:
        # 单步测试
        print(f"\n  运行单步测试: Step {args.step}")
        # 简化：直接运行分步模式
        run_step_by_step(music_files, clip_files)
    elif args.full:
        # 完整流水线
        run_full_pipeline(music_files, clip_files)
    elif args.all:
        # 全部测试
        run_step_by_step(music_files, clip_files)
        print("\n")
        run_full_pipeline(music_files, clip_files)
    else:
        # 默认：分步测试
        run_step_by_step(music_files, clip_files)
    
    print("\n" + "="*70)
    print("  测试完成")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
