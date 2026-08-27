#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端木偶风格化自动识别测试脚本

测试完整链路:
1. 生成测试视频（模拟人物场景）
2. MediaPipe 人物检测与姿态估计
3. PuppetStyleEngine 风格化效果生成
4. JSX 脚本生成（可直接在 AE 中执行）
5. 生成测试报告

支持模式:
- demo: 使用模拟数据跑全流程（无需真实视频）
- test: 使用真实测试视频（需要 ffmpeg）
- full: 完整端到端测试（包含所有步骤）
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def step_log(step_num: int, total: int, title: str, emoji: str = "📌"):
    """步骤日志打印"""
    print(f"\n{'='*60}")
    print(f"{emoji} [步骤 {step_num}/{total}] {title}")
    print(f"{'='*60}")


def generate_test_report(report_data: Dict, output_path: str):
    """生成测试报告"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_name": "木偶风格化自动识别端到端测试",
        "version": "1.0",
        "summary": {
            "total_steps": report_data.get("total_steps", 0),
            "completed_steps": report_data.get("completed_steps", 0),
            "success": report_data.get("success", False),
            "total_duration": report_data.get("total_duration", 0),
        },
        "steps": report_data.get("steps", []),
        "modules": report_data.get("modules", {}),
        "artifacts": report_data.get("artifacts", []),
        "errors": report_data.get("errors", []),
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 测试报告已生成: {output_path}")
    return report


def test_step1_generate_video(output_dir: str) -> Dict:
    """步骤1: 生成测试视频"""
    start_time = time.time()
    
    result = {
        "step": "生成测试视频",
        "success": False,
        "duration": 0,
        "videos": [],
        "error": "",
    }
    
    try:
        from test_video_generator import TestVideoGenerator
        
        generator = TestVideoGenerator()
        
        if not generator.is_ffmpeg_available():
            result["error"] = "ffmpeg 不可用，跳过视频生成"
            result["success"] = True
            result["duration"] = time.time() - start_time
            return result
        
        videos_dir = os.path.join(output_dir, "test_videos")
        batch_result = generator.generate_test_batch(videos_dir, styles=["simple", "animated"])
        
        result["success"] = batch_result["success"]
        result["videos"] = batch_result.get("generated", [])
        
        if not result["success"]:
            result["error"] = f"视频生成失败: {batch_result.get('failed', [])}"
        
    except ImportError as e:
        result["error"] = f"导入失败: {e}"
    except Exception as e:
        result["error"] = f"未知错误: {e}"
    
    result["duration"] = round(time.time() - start_time, 2)
    return result


def test_step2_mediapipe_detection(video_path: str, mode: str = "simulate") -> Dict:
    """步骤2: MediaPipe 人物检测"""
    start_time = time.time()
    
    result = {
        "step": "MediaPipe人物检测",
        "success": False,
        "mode": mode,
        "duration": 0,
        "detection": None,
        "error": "",
    }
    
    try:
        from mediapipe_integration import MediaPipeIntegrator, MediaPipeConfig
        
        config = MediaPipeConfig(
            mode=mode,
            detect_pose=True,
            detect_face=True,
            detect_hands=False,
            confidence_threshold=0.5,
            max_num_persons=1,
            sample_interval=5,
        )
        
        integrator = MediaPipeIntegrator(config)
        
        if not integrator.is_available():
            result["mode"] = "simulate"
            print(f"  ⚠️ MediaPipe 不可用，使用模拟模式")
        
        mp_result = integrator.process_video(video_path)
        
        if mp_result.success:
            puppet_format = integrator.convert_to_puppet_format(mp_result)
            result["detection"] = {
                "mode": mp_result.mode,
                "width": mp_result.width,
                "height": mp_result.height,
                "fps": mp_result.fps,
                "duration": mp_result.duration,
                "bbox": puppet_format.get("bbox"),
                "joint_data": puppet_format.get("joint_data", []),
                "face_data": puppet_format.get("face_data"),
                "detection_count": len(mp_result.detections),
            }
            result["success"] = True
        else:
            result["error"] = mp_result.error
        
    except ImportError as e:
        result["error"] = f"导入失败: {e}"
    except Exception as e:
        result["error"] = f"未知错误: {e}"
    
    result["duration"] = round(time.time() - start_time, 2)
    return result


def test_step3_style_generation(detection_data: Dict, style_type: str = "wooden_puppet") -> Dict:
    """步骤3: 木偶风格化效果生成"""
    start_time = time.time()
    
    result = {
        "step": f"风格化生成 ({style_type})",
        "success": False,
        "style_type": style_type,
        "duration": 0,
        "style_result": None,
        "error": "",
    }
    
    try:
        from puppet_style_engine import PuppetStyleEngine, PuppetStyleConfig
        
        engine = PuppetStyleEngine()
        
        width = detection_data.get("width", 1920)
        height = detection_data.get("height", 1080)
        duration = detection_data.get("duration", 5.0)
        bbox = detection_data.get("bbox")
        joint_data = detection_data.get("joint_data")
        face_data = detection_data.get("face_data")
        
        config = PuppetStyleConfig(
            style_type=style_type,
            intensity=1.0,
            comp_width=width,
            comp_height=height,
            bbox=bbox,
            enable_face_puppet=True,
            face_data=face_data,
            joint_data=joint_data,
        )
        
        style_result = engine.generate_style(
            config,
            layer_name="PuppetLayer",
            duration=duration,
        )
        
        if style_result:
            result["style_result"] = {
                "effects_count": len(style_result.effects),
                "keyframes_count": len(style_result.keyframes),
                "layers_count": len(style_result.layers),
                "expressions_count": len(style_result.expressions),
                "adjustment_layers_count": len(style_result.adjustment_layers),
                "face_effects_count": len(style_result.face_effects),
            }
            result["success"] = True
            result["raw_result"] = style_result
        
    except ImportError as e:
        result["error"] = f"导入失败: {e}"
    except Exception as e:
        result["error"] = f"未知错误: {e}"
    
    result["duration"] = round(time.time() - start_time, 2)
    return result


def test_step4_jsx_generation(style_result: Any, video_path: str,
                               output_dir: str, style_type: str) -> Dict:
    """步骤4: 生成 AE JSX 脚本"""
    start_time = time.time()
    
    result = {
        "step": "JSX脚本生成",
        "success": False,
        "duration": 0,
        "jsx_path": "",
        "error": "",
    }
    
    try:
        from puppet_auto_processor import PuppetAutoProcessor
        
        processor = PuppetAutoProcessor(mediapipe_mode="simulate")
        
        jsx_content = processor._generate_jsx(
            video_path=video_path,
            style_type=style_type,
            style_result=style_result,
            width=1920,
            height=1080,
            duration=5.0,
            bbox=None,
        )
        
        jsx_path = os.path.join(output_dir, f"puppet_{style_type}.jsx")
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_content)
        
        result["jsx_path"] = jsx_path
        result["success"] = True
        
    except ImportError as e:
        result["error"] = f"导入失败: {e}"
    except Exception as e:
        result["error"] = f"未知错误: {e}"
    
    result["duration"] = round(time.time() - start_time, 2)
    return result


def test_demo_mode(output_dir: str) -> Dict:
    """演示模式 - 使用模拟数据跑全流程"""
    report_data = {
        "total_steps": 4,
        "completed_steps": 0,
        "success": False,
        "total_duration": 0,
        "steps": [],
        "modules": {},
        "artifacts": [],
        "errors": [],
    }
    
    start_time = time.time()
    
    print("\n" + "=" * 60)
    print("🎭 木偶风格化自动识别 - 演示模式")
    print("=" * 60)
    print("说明: 使用模拟数据测试完整流程")
    print("=" * 60)
    
    # 步骤1: 模拟视频生成（跳过真实生成）
    step_log(1, 4, "模拟视频生成", "📹")
    print("  使用模拟视频路径（无需真实文件）")
    step1_result = {
        "step": "模拟视频生成",
        "success": True,
        "duration": 0.01,
        "videos": [{"style": "simulated", "path": "simulated_video.mp4", "size": 0}],
        "error": "",
    }
    report_data["steps"].append(step1_result)
    report_data["completed_steps"] += 1
    print(f"  ✅ 完成 ({step1_result['duration']}s)")
    
    # 步骤2: MediaPipe 检测
    step_log(2, 4, "MediaPipe人物检测", "🔍")
    step2_result = test_step2_mediapipe_detection("simulated_video.mp4", mode="simulate")
    report_data["steps"].append(step2_result)
    report_data["completed_steps"] += 1
    
    if step2_result["success"]:
        det = step2_result["detection"]
        print(f"  ✅ 完成 ({step2_result['duration']}s)")
        print(f"  模式: {det['mode']}")
        print(f"  视频: {det['width']}x{det['height']}, {det['fps']}fps")
        print(f"  关节数据: {len(det['joint_data'])} 帧")
        print(f"  面部数据: {'有' if det['face_data'] else '无'}")
        print(f"  边界框: {'有' if det['bbox'] else '无'}")
    else:
        print(f"  ❌ 失败: {step2_result['error']}")
        report_data["errors"].append(step2_result["error"])
    
    # 步骤3: 风格化生成（测试多种风格）
    styles_to_test = ["wooden_puppet", "ceramic_puppet", "marionette"]
    step_log(3, 4, f"风格化生成 ({', '.join(styles_to_test)})", "🎨")
    
    style_results = []
    for style in styles_to_test:
        if step2_result["success"]:
            step3_result = test_step3_style_generation(step2_result["detection"], style_type=style)
        else:
            step3_result = test_step3_style_generation({}, style_type=style)
        
        style_results.append(step3_result)
        report_data["steps"].append(step3_result)
        
        if step3_result["success"]:
            sr = step3_result["style_result"]
            print(f"  ✅ {style}: {sr['effects_count']}效果, {sr['keyframes_count']}关键帧")
        else:
            print(f"  ❌ {style}: {step3_result['error']}")
            report_data["errors"].append(f"{style}: {step3_result['error']}")
    
    report_data["completed_steps"] += 1
    
    # 步骤4: JSX脚本生成
    step_log(4, 4, "JSX脚本生成", "📝")
    
    jsx_results = []
    for i, style in enumerate(styles_to_test):
        if style_results[i]["success"] and style_results[i].get("raw_result"):
            step4_result = test_step4_jsx_generation(
                style_results[i]["raw_result"],
                "simulated_video.mp4",
                output_dir,
                style,
            )
            jsx_results.append(step4_result)
            report_data["steps"].append(step4_result)
            
            if step4_result["success"]:
                size = os.path.getsize(step4_result["jsx_path"]) if os.path.exists(step4_result["jsx_path"]) else 0
                print(f"  ✅ {style}: {os.path.basename(step4_result['jsx_path'])} ({size} bytes)")
                report_data["artifacts"].append({
                    "type": "jsx_script",
                    "style": style,
                    "path": step4_result["jsx_path"],
                    "size": size,
                })
            else:
                print(f"  ❌ {style}: {step4_result['error']}")
                report_data["errors"].append(f"{style} JSX: {step4_result['error']}")
    
    report_data["completed_steps"] += 1
    
    report_data["total_duration"] = round(time.time() - start_time, 2)
    report_data["success"] = len(report_data["errors"]) == 0
    
    return report_data


def test_full_mode(output_dir: str) -> Dict:
    """完整模式 - 使用真实测试视频"""
    report_data = {
        "total_steps": 5,
        "completed_steps": 0,
        "success": False,
        "total_duration": 0,
        "steps": [],
        "modules": {},
        "artifacts": [],
        "errors": [],
    }
    
    start_time = time.time()
    
    print("\n" + "=" * 60)
    print("🎭 木偶风格化自动识别 - 完整模式")
    print("=" * 60)
    print("说明: 使用真实测试视频测试完整流程")
    print("=" * 60)
    
    # 步骤1: 生成测试视频
    step_log(1, 5, "生成测试视频", "📹")
    step1_result = test_step1_generate_video(output_dir)
    report_data["steps"].append(step1_result)
    report_data["completed_steps"] += 1
    
    if step1_result["success"]:
        if step1_result["videos"]:
            print(f"  ✅ 完成 ({step1_result['duration']}s)")
            for vid in step1_result["videos"]:
                print(f"  - {vid['style']}: {os.path.basename(vid['path'])} ({vid['size']} bytes)")
        else:
            print(f"  ⚠️ ffmpeg 不可用，使用模拟数据")
    else:
        print(f"  ❌ 失败: {step1_result['error']}")
        report_data["errors"].append(step1_result["error"])
    
    # 获取测试视频路径
    video_path = "test_video.mp4"
    if step1_result["videos"]:
        video_path = step1_result["videos"][0]["path"]
    
    # 步骤2: MediaPipe 检测
    step_log(2, 5, "MediaPipe人物检测", "🔍")
    step2_result = test_step2_mediapipe_detection(video_path, mode="auto")
    report_data["steps"].append(step2_result)
    report_data["completed_steps"] += 1
    
    if step2_result["success"]:
        det = step2_result["detection"]
        print(f"  ✅ 完成 ({step2_result['duration']}s)")
        print(f"  模式: {det['mode']}")
        print(f"  视频: {det['width']}x{det['height']}, {det['fps']}fps")
        print(f"  关节数据: {len(det['joint_data'])} 帧")
        print(f"  面部数据: {'有' if det['face_data'] else '无'}")
        print(f"  边界框: {'有' if det['bbox'] else '无'}")
    else:
        print(f"  ❌ 失败: {step2_result['error']}")
        report_data["errors"].append(step2_result["error"])
    
    # 步骤3: 风格化生成（测试多种风格）
    styles_to_test = ["wooden_puppet", "ceramic_puppet", "marionette", "cloth_puppet"]
    step_log(3, 5, f"风格化生成 ({', '.join(styles_to_test)})", "🎨")
    
    style_results = []
    for style in styles_to_test:
        if step2_result["success"]:
            step3_result = test_step3_style_generation(step2_result["detection"], style_type=style)
        else:
            step3_result = test_step3_style_generation({}, style_type=style)
        
        style_results.append(step3_result)
        report_data["steps"].append(step3_result)
        
        if step3_result["success"]:
            sr = step3_result["style_result"]
            print(f"  ✅ {style}: {sr['effects_count']}效果, {sr['keyframes_count']}关键帧")
        else:
            print(f"  ❌ {style}: {step3_result['error']}")
            report_data["errors"].append(f"{style}: {step3_result['error']}")
    
    report_data["completed_steps"] += 1
    
    # 步骤4: JSX脚本生成
    step_log(4, 5, "JSX脚本生成", "📝")
    
    jsx_results = []
    for i, style in enumerate(styles_to_test):
        if style_results[i]["success"] and style_results[i].get("raw_result"):
            step4_result = test_step4_jsx_generation(
                style_results[i]["raw_result"],
                video_path,
                output_dir,
                style,
            )
            jsx_results.append(step4_result)
            report_data["steps"].append(step4_result)
            
            if step4_result["success"]:
                size = os.path.getsize(step4_result["jsx_path"]) if os.path.exists(step4_result["jsx_path"]) else 0
                print(f"  ✅ {style}: {os.path.basename(step4_result['jsx_path'])} ({size} bytes)")
                report_data["artifacts"].append({
                    "type": "jsx_script",
                    "style": style,
                    "path": step4_result["jsx_path"],
                    "size": size,
                })
            else:
                print(f"  ❌ {style}: {step4_result['error']}")
                report_data["errors"].append(f"{style} JSX: {step4_result['error']}")
    
    report_data["completed_steps"] += 1
    
    # 步骤5: 保存检测结果
    step_log(5, 5, "保存检测结果", "💾")
    
    try:
        if step2_result["success"] and step2_result["detection"]:
            det_path = os.path.join(output_dir, "detection_result.json")
            with open(det_path, "w", encoding="utf-8") as f:
                json.dump(step2_result["detection"], f, indent=2, ensure_ascii=False, default=str)
            
            report_data["artifacts"].append({
                "type": "detection_result",
                "path": det_path,
            })
            print(f"  ✅ 检测结果已保存")
        else:
            print(f"  ⚠️ 无检测结果可保存")
        
        report_data["steps"].append({
            "step": "保存检测结果",
            "success": True,
            "duration": 0.01,
        })
    except Exception as e:
        report_data["steps"].append({
            "step": "保存检测结果",
            "success": False,
            "error": str(e),
            "duration": 0.01,
        })
        report_data["errors"].append(f"保存检测结果: {e}")
        print(f"  ❌ 失败: {e}")
    
    report_data["completed_steps"] += 1
    
    report_data["total_duration"] = round(time.time() - start_time, 2)
    report_data["success"] = len(report_data["errors"]) == 0
    
    return report_data


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="端到端木偶风格化自动识别测试")
    parser.add_argument(
        "--mode", "-m",
        choices=["demo", "test", "full"],
        default="demo",
        help="测试模式",
    )
    parser.add_argument(
        "--output", "-o",
        default=str(PROJECT_ROOT / "output" / "puppet_auto_test"),
        help="输出目录",
    )
    parser.add_argument(
        "--video", "-v",
        help="测试视频路径（test模式）",
    )
    
    args = parser.parse_args()
    
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)
    
    if args.mode == "demo":
        report_data = test_demo_mode(output_dir)
    elif args.mode == "test":
        report_data = test_full_mode(output_dir)
    elif args.mode == "full":
        report_data = test_full_mode(output_dir)
    
    report_path = os.path.join(output_dir, "test_report.json")
    report = generate_test_report(report_data, report_path)
    
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"  总步骤: {report['summary']['total_steps']}")
    print(f"  完成步骤: {report['summary']['completed_steps']}")
    print(f"  成功率: {'100%' if report['summary']['success'] else '部分失败'}")
    print(f"  总耗时: {report['summary']['total_duration']}秒")
    
    if report["errors"]:
        print(f"\n  ❌ 错误列表:")
        for err in report["errors"]:
            print(f"    - {err}")
    
    if report["artifacts"]:
        print(f"\n  📦 生成的文件:")
        for art in report["artifacts"]:
            size_info = f" ({art.get('size', 0)} bytes)" if "size" in art else ""
            print(f"    - {art['type']}: {os.path.basename(art['path'])}{size_info}")
    
    print(f"\n  📄 报告路径: {report_path}")
    
    if not report["summary"]["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
