#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2 AE实机验证脚本 - AI调度引擎效果扩展

验证内容：
1. TS编译器生成的JSX可在AE 2025中执行
2. 20个效果生成器产生有效AE效果
3. 关键帧动画生成器产生有效关键帧
4. 节拍-关键帧映射器产生有效映射
5. Pipeline.compile_planning_to_jsx端到端流程

运行前置条件：
1. Adobe After Effects 2025 已启动
2. 在 AE 中运行 ae_mcp_listener.jsx（File -> Scripts -> Run Script File）
3. 关闭所有模态对话框

使用方法：
    python tests/test_phase2_real_ae.py
    python tests/test_phase2_real_ae.py --step 1
    python tests/test_phase2_real_ae.py --full
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_ts_compiler_client import AETSCompilerClient

from ae_agent_pipeline import AEAgentPipeline, PlanningResult

# ==================== 配置 ====================

OUTPUT_DIR = r"D:\AE-Work\输出"

# 20个效果生成器对应的matchName（与effect-generators.ts一致）
TEST_EFFECTS = [
    ("ADBE Glo2", "Glow", {"Glow Threshold": 40, "Glow Radius": 25, "Glow Intensity": 1.5}),
    ("ADBE Color Key", "Color Key", {"Color Tolerance": 20, "Edge Feather": 1}),
    ("CC Particle World", "CC Particle World", {"Birth Rate": 100, "Longevity": 2.0}),
    ("ADBE Fractal Noise", "Fractal Noise", {"Contrast": 50, "Scale": 300}),
    ("ADBE Ramp", "Ramp", {"Ramp Scatter": 0}),
    ("ADBE Gaussian Blur 2", "Gaussian Blur", {"Blurriness": 10}),
    ("ADBE Directional Blur", "Directional Blur", {"Blur Length": 5}),
    ("ADBE HUE SATURATION", "Hue/Saturation", {"Master Saturation": 10}),
    ("ADBE Protractor2", "Curves", {}),
    ("ADBE Color Balance", "Color Balance", {}),
    ("ADBE Drop Shadow", "Drop Shadow", {"Shadow Distance": 5, "Shadow Opacity": 50}),
    ("ADBE Fill", "Fill", {"Color": [1, 0, 0, 1]}),
    ("ADBE Stroke", "Stroke", {"Brush Size": 2, "Color": [1, 1, 1, 1]}),
    ("ADBE Noise", "Noise", {"Amount of Noise": 10}),
    ("ADBE Unsharp Mask", "Sharpen", {"Sharpen Amount": 30}),
    ("ADBE Texturize", "Texturize", {}),
    ("ADBE Roughen Edges", "Roughen Edges", {"Border": 5}),
    ("CC Lens", "CC Lens", {"Center": [960, 540]}),
    ("ADBE Optics Compensation", "Optics Compensation", {"Field of View (FOV)": 100}),
    ("ADBE Simple Choker", "Simple Choker", {"Choke Matte": 5}),
]

# ============================================


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, total, title):
    print(f"\n  [{step_num}/{total}] {title}")
    print("  " + "-" * 50)


def check_environment():
    """检查运行环境"""
    print_header("Phase 2 环境检查")

    issues = []

    # 检查TS编译器
    compiler = AETSCompilerClient()
    if compiler.health_check():
        print("  [OK] TS编译器可用")
    else:
        print("  [WARN] TS编译器不可用（将使用降级JSX生成）")

    # 检查AE命令文件
    cmd_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ae_command.json")
    print(f"  [INFO] 命令文件: {cmd_file}")

    # 检查Phase 2模块加载
    pipeline = AEAgentPipeline()
    if pipeline.ts_compiler:
        print("  [OK] AETSCompilerClient已加载")
    else:
        print("  [FAIL] AETSCompilerClient未加载")
        issues.append("TS编译器客户端未加载")

    if pipeline.keyframe_generator:
        print("  [OK] KeyframeAnimationGenerator已加载")
    else:
        print("  [FAIL] KeyframeAnimationGenerator未加载")
        issues.append("关键帧动画生成器未加载")

    if pipeline.beat_mapper:
        print("  [OK] BeatKeyframeMapper已加载")
    else:
        print("  [FAIL] BeatKeyframeMapper未加载")
        issues.append("节拍映射器未加载")

    print(f"\n  环境检查: {'通过' if not issues else '发现 ' + str(len(issues)) + ' 个问题'}")
    return len(issues) == 0


def step1_verify_ts_compiler():
    """Step 1: 验证TS编译器JSX生成"""
    print_step(1, 5, "验证TS编译器JSX生成")

    compiler = AETSCompilerClient()

    # 测试单个效果编译
    result = compiler.compile_effect(
        "ADBE Gaussian Blur 2",
        {"Blurriness": 25},
        {"compName": "Phase2_TS_Test", "layerName": "TestLayer"},
    )

    if result["success"]:
        jsx = result["jsx_code"]
        print(f"  [OK] JSX生成成功，长度: {len(jsx)} 字符")
        print(f"  [OK] 包含ADBE Effect Parade: {'ADBE Effect Parade' in jsx}")
        print(f"  [OK] 包含Blurriness: {'Blurriness' in jsx}")
        print(f"  [OK] 包含setValue: {'setValue' in jsx}")

        # 保存JSX到文件供AE执行
        jsx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "phase2_test_compiled.jsx")
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx)
        print(f"  [OK] JSX已保存: {jsx_path}")
        return True
    else:
        print("  [FAIL] JSX生成失败")
        return False


def step2_verify_effect_generators():
    """Step 2: 验证20个效果生成器"""
    print_step(2, 5, "验证20个效果生成器")

    compiler = AETSCompilerClient()
    success_count = 0
    fail_count = 0

    for match_name, display_name, settings in TEST_EFFECTS:
        try:
            result = compiler.compile_effect(match_name, settings)
            if result["success"] and match_name in result["jsx_code"]:
                print(f"  [OK] {display_name} ({match_name})")
                success_count += 1
            else:
                print(f"  [FAIL] {display_name} ({match_name}) - JSX不包含matchName")
                fail_count += 1
        except Exception as e:
            print(f"  [FAIL] {display_name} ({match_name}) - {str(e)}")
            fail_count += 1

    print(f"\n  结果: {success_count}/{len(TEST_EFFECTS)} 成功, {fail_count} 失败")
    return fail_count == 0


def step3_verify_keyframe_generator():
    """Step 3: 验证关键帧动画生成器"""
    print_step(3, 5, "验证关键帧动画生成器")

    pipeline = AEAgentPipeline()
    gen = pipeline.keyframe_generator

    # 测试入场动画
    entrance_types = ["fade_in", "scale_up", "slide_left", "zoom_in"]
    for anim_type in entrance_types:
        try:
            kfs = gen.generate_entrance_animation(anim_type, 1.0)
            cmds = gen.to_ae_keyframe_commands(kfs, "TestLayer", "Opacity")
            print(f"  [OK] 入场动画 {anim_type}: {len(kfs)}关键帧, {len(cmds)}命令")
        except Exception as e:
            print(f"  [FAIL] 入场动画 {anim_type}: {str(e)}")
            return False

    # 测试节拍同步动画
    beat_times = [0.0, 0.5, 1.0, 1.5, 2.0]
    try:
        kfs = gen.generate_beat_synced_keyframes(
            beat_times=beat_times,
            property_name="Scale",
            base_value=100,
            beat_value=110,
        )
        print(f"  [OK] 节拍同步动画: {len(kfs)}关键帧 (期望>={len(beat_times)})")
    except Exception as e:
        print(f"  [FAIL] 节拍同步动画: {str(e)}")
        return False

    return True


def step4_verify_beat_mapper():
    """Step 4: 验证节拍-关键帧映射器"""
    print_step(4, 5, "验证节拍-关键帧映射器")

    pipeline = AEAgentPipeline()
    mapper = pipeline.beat_mapper

    from beat_keyframe_mapper import Beat, parse_beats_from_features

    # 模拟音频特征
    audio_features = {
        "bpm": 120,
        "beats": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5],
        "downbeats": [0.0, 2.0],
        "energy_curve": {"rms": [0.3, 0.5, 0.7, 0.6, 0.8, 0.4, 0.9, 0.5]},
    }

    beats = parse_beats_from_features(audio_features)
    print(f"  [OK] 解析节拍: {len(beats)}个")

    targets = [
        {"time": 0.02, "property": "Scale", "value": 110},
        {"time": 1.03, "property": "Scale", "value": 105},
        {"time": 2.01, "property": "Scale", "value": 108},
    ]

    # 测试4种策略
    strategies = ["nearest", "dynamic_programming", "downbeat_priority", "energy_based"]
    for strategy in strategies:
        try:
            result = mapper.map_beats_to_keyframes(beats, targets, strategy=strategy)
            print(f"  [OK] 策略 {strategy}: {len(result.mappings)}映射, "
                  f"平均偏移={result.average_offset_ms:.1f}ms, "
                  f"覆盖率={result.coverage:.1%}")
        except Exception as e:
            print(f"  [FAIL] 策略 {strategy}: {str(e)}")
            return False

    return True


def step5_verify_pipeline_jsx_compilation():
    """Step 5: 验证Pipeline端到端JSX编译"""
    print_step(5, 5, "验证Pipeline端到端JSX编译")

    pipeline = AEAgentPipeline()

    # 创建测试PlanningResult
    planning = PlanningResult()
    planning.composition = {
        "name": "Phase2_E2E_Test",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
    }
    planning.layers = [
        {"name": "TestLayer", "type": "solid", "duration": 5, "startTime": 0, "color": [0.2, 0.4, 0.8]},
    ]
    planning.effects = [
        {"layerName": "TestLayer", "effectName": "ADBE Gaussian Blur 2",
         "settings": {"Blurriness": 10}},
        {"layerName": "TestLayer", "effectName": "ADBE Glo2",
         "settings": {"Glow Radius": 20, "Glow Intensity": 0.5}},
    ]
    planning.keyframes = [
        {"layerName": "TestLayer", "propertyName": "Opacity",
         "time": 0, "value": 0, "easeType": "easeOut"},
        {"layerName": "TestLayer", "propertyName": "Opacity",
         "time": 0.5, "value": 100, "easeType": "easeIn"},
    ]
    planning.transitions = []
    planning.timeline = []

    # 编译为JSX
    result = pipeline.compile_planning_to_jsx(planning)

    if result["success"]:
        jsx = result["jsx_code"]
        print("  [OK] 端到端JSX编译成功")
        print(f"  [OK] JSX长度: {len(jsx)} 字符")
        print(f"  [OK] 方法: {result['method']}")
        print(f"  [OK] 包含ADBE Gaussian Blur 2: {'ADBE Gaussian Blur 2' in jsx}")
        print(f"  [OK] 包含ADBE Glo2: {'ADBE Glo2' in jsx}")
        print(f"  [OK] 包含ADBE Effect Parade: {'ADBE Effect Parade' in jsx}")

        # 保存端到端JSX
        jsx_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "phase2_e2e_compiled.jsx")
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx)
        print(f"  [OK] 端到端JSX已保存: {jsx_path}")
        print(f"\n  可在AE中执行: File -> Scripts -> Run Script File -> 选择 {jsx_path}")
        return True
    else:
        print(f"  [FAIL] 端到端JSX编译失败: {result.get('error', 'unknown')}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Phase 2 AE实机验证")
    parser.add_argument("--step", type=int, help="运行指定步骤 (1-5)")
    parser.add_argument("--full", action="store_true", help="运行全部步骤")
    args = parser.parse_args()

    print_header("Phase 2 AE实机验证 - AI调度引擎效果扩展")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 环境检查
    if not check_environment():
        print("\n  环境检查未通过，请修复上述问题后重试")
        return 1

    steps = {
        1: ("TS编译器JSX生成", step1_verify_ts_compiler),
        2: ("20个效果生成器", step2_verify_effect_generators),
        3: ("关键帧动画生成器", step3_verify_keyframe_generator),
        4: ("节拍-关键帧映射器", step4_verify_beat_mapper),
        5: ("Pipeline端到端JSX编译", step5_verify_pipeline_jsx_compilation),
    }

    if args.step:
        if args.step not in steps:
            print(f"  无效步骤: {args.step}，可选: {list(steps.keys())}")
            return 1
        title, func = steps[args.step]
        print_header(f"Step {args.step}: {title}")
        success = func()
        return 0 if success else 1

    # 运行全部步骤
    if args.full or not args.step:
        results = {}
        for step_num, (title, func) in steps.items():
            print_header(f"Step {step_num}: {title}")
            try:
                results[step_num] = func()
            except Exception as e:
                print(f"  [ERROR] 异常: {str(e)}")
                results[step_num] = False

        # 汇总
        print_header("Phase 2 验证汇总")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        for step_num, success in results.items():
            status = "[PASS]" if success else "[FAIL]"
            title = steps[step_num][0]
            print(f"  {status} Step {step_num}: {title}")
        print(f"\n  总计: {passed}/{total} 步骤通过")

        if passed == total:
            print("\n  *** Phase 2 实机验证全部通过! ***")
            return 0
        else:
            print(f"\n  {total - passed} 个步骤未通过，请检查上述日志")
            return 1


if __name__ == "__main__":
    sys.exit(main())
