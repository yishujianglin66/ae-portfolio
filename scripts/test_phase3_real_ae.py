#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 3 AE实机验证脚本 - 编排层与反馈闭环

验证内容：
1. 风格效果组合验证（电影感风格）
2. 场景编排 + 转场验证
3. 节拍同步动画验证 (BPM=120)
4. 完整编排验证（风格+节拍→编译JSX）
5. 反馈闭环模拟

运行前置条件：
1. Adobe After Effects 2025 已启动
2. 在 AE 中运行 ae_mcp_listener.jsx（File -> Scripts -> Run Script File）
3. 关闭所有模态对话框

使用方法：
    python tests/test_phase3_real_ae.py
    python tests/test_phase3_real_ae.py --step 1
    python tests/test_phase3_real_ae.py --full
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline, PlanningResult

# ==================== 配置 ====================

OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_step(step_num, total, title):
    print(f"\n  [{step_num}/{total}] {title}")
    print("  " + "-" * 50)


def check_environment():
    """检查运行环境"""
    print_header("Phase 3 环境检查")

    issues = []

    pipeline = AEAgentPipeline()

    modules = [
        ("EffectComposer", pipeline.effect_composer),
        ("BeatOrchestrator", pipeline.beat_orchestrator),
        ("SceneOrchestrator", pipeline.scene_orchestrator),
        ("FeedbackLoopManager", pipeline.feedback_manager),
    ]

    for name, module in modules:
        if module is not None:
            print(f"  [OK] {name}已加载")
        else:
            print(f"  [FAIL] {name}未加载")
            issues.append(f"{name}未加载")

    if pipeline.ts_compiler:
        print("  [OK] TS编译器客户端已加载")
    else:
        print("  [WARN] TS编译器客户端未加载（Step 4将使用降级模式）")

    print(f"\n  环境检查: {'通过' if not issues else '发现 ' + str(len(issues)) + ' 个问题'}")
    return len(issues) == 0


def step1_style_effects_verification():
    """Step 1: 风格效果组合验证（电影感风格）"""
    print_step(1, 5, "风格效果组合验证（电影感风格）")

    pipeline = AEAgentPipeline()

    print("  生成电影感风格效果组合...")
    result = pipeline.compose_style_effects(
        style_name="cinematic",
        layer_name="Cinematic_Layer",
        intensity=1.0
    )

    if result and "effects" in result and len(result["effects"]) > 0:
        print(f"  [OK] 风格: {result.get('style_name', 'cinematic')}")
        print(f"  [OK] 强度: {result.get('intensity', 1.0)}")
        print(f"  [OK] 效果数量: {len(result['effects'])}")
        for i, effect in enumerate(result["effects"]):
            print(f"       {i+1}. {effect['effectName']}")
            print(f"          设置: {json.dumps(effect['settings'], ensure_ascii=False)}")
        return True
    else:
        print("  [FAIL] 风格效果生成失败")
        return False


def step2_scene_transition_verification():
    """Step 2: 场景编排 + 转场验证"""
    print_step(2, 5, "场景编排 + 转场验证")

    pipeline = AEAgentPipeline()

    scenes = [
        {"name": "Scene_Intro", "duration": 2.0},
        {"name": "Scene_Main", "duration": 3.0},
        {"name": "Scene_Outro", "duration": 1.5},
    ]

    print("  编排3个场景，使用crossfade转场...")
    result = pipeline.orchestrate_scenes(
        scenes=scenes,
        transition_type="crossfade",
        transition_duration=0.5
    )

    if result and result.get("scene_count") == 3:
        print(f"  [OK] 场景数量: {result['scene_count']}")
        print(f"  [OK] 总时长: {result['total_duration']:.2f}秒")
        print(f"  [OK] 转场数量: {len(result.get('transitions', []))}")
        print(f"  [OK] 时间线条目: {len(result.get('timeline', []))}")

        print("\n  场景时间线:")
        for item in result["timeline"]:
            if item["type"] == "scene":
                print(f"    场景: {item['name']} "
                      f"({item['startTime']:.2f}s - {item['endTime']:.2f}s)")
            elif item["type"] == "transition":
                print(f"    转场: {item['name']} "
                      f"({item['startTime']:.2f}s, 时长{item['duration']:.2f}s)")

        print("\n  测试镜头运动（推镜）...")
        camera_kfs = pipeline.apply_camera_move(
            layer_name="Scene_Main",
            move_type="push",
            duration=2.0,
            start_scale=100.0,
            end_scale=120.0
        )
        print(f"  [OK] 镜头运动关键帧数量: {len(camera_kfs)}")
        for kf in camera_kfs:
            print(f"       {kf['propertyName']} @ {kf['time']}s: {kf['value']}")

        return True
    else:
        print("  [FAIL] 场景编排失败")
        return False


def step3_beat_sync_verification():
    """Step 3: 节拍同步动画验证 (BPM=120)"""
    print_step(3, 5, "节拍同步动画验证 (BPM=120)")

    pipeline = AEAgentPipeline()

    bpm = 120.0
    duration = 5.0

    print(f"  生成 BPM={bpm} 的节拍同步动画...")
    result = pipeline.orchestrate_beat_show(
        layer_name="Beat_Layer",
        bpm=bpm,
        duration=duration,
        style="energetic",
        structure_template="short_hook"
    )

    if result and "keyframes" in result:
        print(f"  [OK] 图层: {result.get('layerName')}")
        print(f"  [OK] 风格: {result.get('style')}")
        print(f"  [OK] 时长: {result.get('duration')}秒")
        print(f"  [OK] 关键帧总数: {len(result['keyframes'])}")
        print(f"  [OK] 音乐段落数: {len(result.get('sections', []))}")

        print("\n  音乐段落结构:")
        for section in result["sections"]:
            print(f"    {section['type']}: "
                  f"{section['start_time']:.2f}s - {section['end_time']:.2f}s "
                  f"(能量: {section['energy']:.2f})")

        prop_counts = {}
        for kf in result["keyframes"]:
            prop = kf["propertyName"]
            prop_counts[prop] = prop_counts.get(prop, 0) + 1

        print("\n  各属性关键帧统计:")
        for prop, count in prop_counts.items():
            print(f"    {prop}: {count}个")

        return True
    else:
        print("  [FAIL] 节拍同步动画生成失败")
        return False


def step4_full_orchestration_compilation():
    """Step 4: 完整编排验证（风格+节拍→编译JSX）"""
    print_step(4, 5, "完整编排验证（风格+节拍→编译JSX）")

    pipeline = AEAgentPipeline()

    perception = {
        "audio": {
            "bpm": 120,
            "duration": 5.0,
        }
    }
    understanding = {
        "style": "cinematic",
        "keywords": ["movie", "film", "epic"],
    }

    print("  执行完整编排（风格效果 + 节拍动画）...")
    orch_result = pipeline.orchestrate_full(
        perception=perception,
        understanding=understanding,
        layer_name="Main_Layer",
    )

    if not orch_result:
        print("  [FAIL] 完整编排失败")
        return False

    print(f"  [OK] 风格: {orch_result['style']}")
    print(f"  [OK] BPM: {orch_result['bpm']}")
    print(f"  [OK] 效果数量: {orch_result['effect_count']}")
    print(f"  [OK] 关键帧数量: {orch_result['keyframe_count']}")

    planning = PlanningResult()
    planning.composition = {
        "name": "Phase3_E2E_Test",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
    }
    planning.layers = [
        {"name": "Main_Layer", "type": "solid", "duration": 5,
         "startTime": 0, "color": [0.2, 0.3, 0.5]},
    ]
    planning.effects = orch_result["effects"]
    planning.keyframes = orch_result["keyframes"]
    planning.transitions = []
    planning.timeline = []

    print("\n  编译为JSX...")
    compile_result = pipeline.compile_planning_to_jsx(planning)

    if compile_result.get("success"):
        jsx_code = compile_result["jsx_code"]
        print("  [OK] JSX编译成功")
        print(f"  [OK] JSX长度: {len(jsx_code)} 字符")
        print(f"  [OK] 编译方法: {compile_result.get('method')}")
        print(f"  [OK] 命令数量: {compile_result.get('command_count')}")

        jsx_path = os.path.join(OUTPUT_DIR, "phase3_e2e_compiled.jsx")
        with open(jsx_path, "w", encoding="utf-8") as f:
            f.write(jsx_code)
        print(f"  [OK] JSX文件已保存: {jsx_path}")
        print(f"\n  可在AE中执行: File -> Scripts -> Run Script File -> 选择 {os.path.basename(jsx_path)}")
        return True
    else:
        print(f"  [FAIL] JSX编译失败: {compile_result.get('error', 'unknown')}")
        return False


def step5_feedback_loop_simulation():
    """Step 5: 反馈闭环模拟"""
    print_step(5, 5, "反馈闭环模拟")

    pipeline = AEAgentPipeline()

    print("  模拟成功执行的反馈闭环...")
    expected = {"settings": {"Blurriness": 10.0, "Glow Radius": 20.0}}

    def success_execute():
        return {
            "success": True,
            "result": {"settings": {"Blurriness": 10.0, "Glow Radius": 20.0}},
        }

    result1 = pipeline.run_with_feedback(
        user_input="add cinematic blur and glow",
        intent_type="effect_application",
        execute_fn=success_execute,
        expected=expected,
        base_confidence=0.7,
    )

    if result1 and result1["success"]:
        print(f"  [OK] 成功执行 - 验证通过: {result1['verification'].passed}")
        print(f"  [OK] 匹配度: {result1['verification'].match_score:.2%}")
        print(f"  [OK] 执行置信度: {result1['record'].confidence_before:.2f} "
              f"→ {result1['record'].confidence_after:.2f}")
    else:
        print("  [FAIL] 成功执行模拟失败")
        return False

    print("\n  模拟失败执行的反馈闭环...")
    expected_fail = {"settings": {"Blurriness": 10.0}}

    def fail_execute():
        return {
            "success": False,
            "error": "Effect not found in layer",
            "error_code": "EFFECT_NOT_FOUND",
        }

    result2 = pipeline.run_with_feedback(
        user_input="add non_existent_effect",
        intent_type="effect_application",
        execute_fn=fail_execute,
        expected=expected_fail,
        base_confidence=0.7,
    )

    if result2 and not result2["success"]:
        print("  [OK] 失败执行 - 已捕获错误")
        print(f"  [OK] 错误码: {result2['record'].error_code}")
        if result2["suggestion"]:
            print(f"  [OK] 恢复建议: {result2['suggestion']['default']}")
            print(f"  [OK] 建议动作数量: {len(result2['suggestion']['actions'])}")
    else:
        print("  [FAIL] 失败执行模拟异常")
        return False

    print("\n  获取学习摘要...")
    summary = pipeline.get_feedback_summary()
    print(f"  [OK] 总执行次数: {summary.get('total_executions', 0)}")
    print(f"  [OK] 成功率: {summary.get('success_rate', 0):.2%}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Phase 3 AE实机验证")
    parser.add_argument("--step", type=int, help="运行指定步骤 (1-5)")
    parser.add_argument("--full", action="store_true", help="运行全部步骤")
    args = parser.parse_args()

    print_header("Phase 3 AE实机验证 - 编排层与反馈闭环")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not check_environment():
        print("\n  环境检查未通过，请修复上述问题后重试")
        return 1

    steps = {
        1: ("风格效果组合验证", step1_style_effects_verification),
        2: ("场景编排 + 转场验证", step2_scene_transition_verification),
        3: ("节拍同步动画验证", step3_beat_sync_verification),
        4: ("完整编排→编译JSX", step4_full_orchestration_compilation),
        5: ("反馈闭环模拟", step5_feedback_loop_simulation),
    }

    if args.step:
        if args.step not in steps:
            print(f"  无效步骤: {args.step}，可选: {list(steps.keys())}")
            return 1
        title, func = steps[args.step]
        print_header(f"Step {args.step}: {title}")
        success = func()
        return 0 if success else 1

    if args.full or not args.step:
        results = {}
        for step_num, (title, func) in steps.items():
            print_header(f"Step {step_num}: {title}")
            try:
                results[step_num] = func()
            except Exception as e:
                print(f"  [ERROR] 异常: {str(e)}")
                import traceback
                traceback.print_exc()
                results[step_num] = False

        print_header("Phase 3 验证汇总")
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        for step_num, success in results.items():
            status = "[PASS]" if success else "[FAIL]"
            title = steps[step_num][0]
            print(f"  {status} Step {step_num}: {title}")
        print(f"\n  总计: {passed}/{total} 步骤通过")

        if passed == total:
            print("\n  *** Phase 3 实机验证全部通过! ***")
            return 0
        else:
            print(f"\n  {total - passed} 个步骤未通过，请检查上述日志")
            return 1


if __name__ == "__main__":
    sys.exit(main())
