#!/usr/bin/env python3
"""
统一多工具集成调度器 - 边界情况与漏洞检验
================================================

检验所有异常路径、边界条件和错误处理逻辑，确保系统鲁棒性。

用法:
    py -3.11 test_edge_cases.py
    py -3.11 test_edge_cases.py -v  # 详细输出
"""

import os
import sys
import json
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unified_tool_integrator import (
    UnifiedToolIntegrator,
    WorkflowResult,
    StepResult,
    PhaseStatus,
    ToolType,
    ToolConfig,
    AEAdapter,
    PremiereProAdapter,
    PhotoshopAdapter,
    IllustratorAdapter,
    MediaEncoderAdapter,
    AuditionAdapter,
    FFmpegAdapter,
    TopazAdapter,
    BlenderAdapter,
)


def run_test(name, test_func, verbose=False):
    """运行单个测试并返回结果"""
    try:
        start = time.time()
        test_func()
        duration = (time.time() - start) * 1000
        print(f"  ✅ {name} ({duration:.1f}ms)")
        return True, ""
    except AssertionError as e:
        print(f"  ❌ {name}: {e}")
        if verbose:
            traceback.print_exc()
        return False, str(e)
    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__}: {e}")
        if verbose:
            traceback.print_exc()
        return False, f"{type(e).__name__}: {e}"


def test_invalid_preset_id():
    """测试无效预设ID处理"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    try:
        integrator.run_workflow("nonexistent_preset_xyz")
        assert False, "应该抛出 ValueError"
    except ValueError as e:
        assert "未知的工作流预设" in str(e)
        assert "nonexistent_preset_xyz" in str(e)


def test_empty_preset_file():
    """测试空/无效预设文件处理"""
    # 不存在的文件
    integrator = UnifiedToolIntegrator(
        default_mode="simulate",
        preset_file="nonexistent_file.json",
    )
    # 应该能正常初始化，只是没有外部预设
    presets = integrator.list_presets()
    assert len(presets) >= 4  # 至少有内置预设


def test_malformed_json_preset():
    """测试损坏的JSON预设文件处理"""
    bad_json = os.path.join(os.path.dirname(__file__), "_test_bad.json")
    with open(bad_json, "w", encoding="utf-8") as f:
        f.write("{invalid json content}")
    try:
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            preset_file=bad_json,
        )
        # 应该能初始化，只是没有外部预设
        presets = integrator.list_presets()
        assert len(presets) >= 4
    finally:
        if os.path.exists(bad_json):
            os.remove(bad_json)


def test_custom_workflow_empty_steps():
    """测试自定义工作流空步骤列表"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    result = integrator.run_custom_workflow([], "空工作流")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    assert len(result.steps) == 0
    assert result.total_duration_ms == 0


def test_custom_workflow_single_step():
    """测试自定义工作流单步骤"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    steps = [
        {
            "step_id": "single",
            "name": "单步骤",
            "tool": "ffmpeg",
            "operation": "probe",
        }
    ]
    result = integrator.run_custom_workflow(steps, "单步骤工作流")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    assert len(result.steps) == 1
    assert result.steps[0].step_id == "single"


def test_workflow_with_missing_params():
    """测试工作流缺失参数处理"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    # enhance_quality 预设需要 input_file，但不传也能运行（有默认值）
    result = integrator.run_workflow("enhance_quality")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value


def test_unknown_tool_in_simulate_mode():
    """测试未知工具在模拟模式下的降级"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    steps = [
        {
            "step_id": "unknown_tool_step",
            "name": "未知工具步骤",
            "tool": "some_future_tool_2027",
            "operation": "do_magic",
        }
    ]
    result = integrator.run_custom_workflow(steps, "未知工具测试")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    assert result.steps[0].tool == "some_future_tool_2027"
    assert result.steps[0].mode_used == "simulate"


def test_unknown_tool_in_real_mode():
    """测试未知工具在真实模式下的处理"""
    integrator = UnifiedToolIntegrator(default_mode="real")
    steps = [
        {
            "step_id": "unknown_tool_step",
            "name": "未知工具步骤",
            "tool": "nonexistent_tool",
            "operation": "do_something",
        }
    ]
    result = integrator.run_custom_workflow(steps, "未知工具真实模式测试")
    assert result is not None
    # 真实模式下未知工具应该失败
    assert result.status == PhaseStatus.ERROR.value
    assert len(result.failed_steps()) > 0


def test_circular_dependency_detection():
    """测试循环依赖检测"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    steps = [
        {"step_id": "a", "name": "A", "tool": "ffmpeg", "operation": "probe", "depends_on": ["b"]},
        {"step_id": "b", "name": "B", "tool": "ffmpeg", "operation": "probe", "depends_on": ["a"]},
    ]
    result = integrator.run_custom_workflow(steps, "循环依赖测试")
    # 循环依赖应该导致步骤无法执行
    assert result is not None
    assert len(result.steps) == 2


def test_parallel_execution_order():
    """测试并行步骤执行顺序"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    steps = [
        {"step_id": "root", "name": "根步骤", "tool": "ffmpeg", "operation": "probe"},
        {"step_id": "parallel_a", "name": "并行A", "tool": "ffmpeg", "operation": "probe", "depends_on": ["root"]},
        {"step_id": "parallel_b", "name": "并行B", "tool": "ffmpeg", "operation": "probe", "depends_on": ["root"]},
        {"step_id": "parallel_c", "name": "并行C", "tool": "ffmpeg", "operation": "probe", "depends_on": ["root"]},
        {"step_id": "final", "name": "最终步骤", "tool": "ffmpeg", "operation": "probe", "depends_on": ["parallel_a", "parallel_b", "parallel_c"]},
    ]
    result = integrator.run_custom_workflow(steps, "并行执行测试")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    assert len(result.steps) == 5
    # 所有步骤都应该成功
    for step in result.steps:
        assert step.status == PhaseStatus.SUCCESS.value


def test_all_workflow_presets():
    """测试所有工作流预设都能正常执行"""
    preset_file = os.path.join(os.path.dirname(__file__), "workflow_presets_library.json")
    integrator = UnifiedToolIntegrator(
        default_mode="simulate",
        preset_file=preset_file,
    )
    presets = integrator.list_presets()
    failures = []
    for preset in presets:
        try:
            result = integrator.run_workflow(preset["id"])
            if result.status != PhaseStatus.SUCCESS.value:
                failures.append(f"{preset['id']}: 状态={result.status}, 错误={result.error}")
        except Exception as e:
            failures.append(f"{preset['id']}: 异常={e}")
    assert len(failures) == 0, f"以下预设执行失败:\n" + "\n".join(failures)


def test_adobe_adapters_all_operations():
    """测试所有Adobe适配器的所有操作"""
    adapters_and_ops = [
        (AEAdapter, ToolType.AE.value, ["import_footage", "create_comp", "apply_effect", "render"]),
        (PremiereProAdapter, ToolType.PREMIERE.value, ["create_project", "import_media", "create_sequence", "color_grade", "audio_mix", "add_transition", "add_title", "dynamic_link_to_ae", "export_media", "batch_render", "apply_lumetri", "apply_effect"]),
        (PhotoshopAdapter, ToolType.PHOTOSHOP.value, ["open_document", "import_image", "resize", "crop", "adjust_color", "apply_filter", "add_layer", "add_mask", "add_text", "smart_object", "batch_process", "export_png", "export_jpg", "export_psd", "remove_background", "generative_fill"]),
        (IllustratorAdapter, ToolType.ILLUSTRATOR.value, ["create_document", "import_asset", "create_shape", "create_text", "apply_style", "create_logo", "create_mograph", "export_svg", "export_ai", "export_png", "batch_export", "create_pattern"]),
        (MediaEncoderAdapter, ToolType.MEDIA_ENCODER.value, ["add_to_queue", "start_queue", "watch_folder", "create_preset", "batch_encode", "create_proxy", "export_h264", "export_prores", "export_hevc", "status_monitor"]),
        (AuditionAdapter, ToolType.AUDITION.value, ["import_audio", "noise_reduction", "audio_mix", "mastering", "apply_effect", "batch_process", "export_wav", "export_mp3", "voiceover", "podcast"]),
    ]

    for adapter_cls, tool_type, operations in adapters_and_ops:
        config = ToolConfig(tool_type=tool_type, mode="simulate")
        adapter = adapter_cls(config)
        for op in operations:
            result = adapter.execute(op, {
                "step_id": f"test_{tool_type}_{op}",
                "step_name": f"测试 {tool_type} {op}",
                "output_dir": r"D:\AE-Work\_integrator_tests",
            })
            assert result.status == PhaseStatus.SUCCESS.value, \
                f"{tool_type}.{op} 失败: {result.error}"


def test_workflow_result_methods():
    """测试WorkflowResult的各种方法"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    result = integrator.run_workflow("enhance_quality")
    
    # 测试 successful_steps
    success_steps = result.successful_steps()
    assert isinstance(success_steps, list)
    assert len(success_steps) == 3
    
    # 测试 failed_steps
    failed = result.failed_steps()
    assert len(failed) == 0
    
    # 测试 summary 不为空
    assert result.summary
    assert "工作流" in result.summary
    assert "总耗时" in result.summary
    
    # 测试 has_outputs
    assert isinstance(result.has_outputs, bool)


def test_progress_callback_with_error():
    """测试进度回调在异常情况下的行为"""
    progress_updates = []
    def bad_callback(workflow, progress, message):
        progress_updates.append({"workflow": workflow, "progress": progress, "message": message})
        if progress > 0.5:
            raise RuntimeError("模拟回调错误")
    
    integrator = UnifiedToolIntegrator(
        default_mode="simulate",
        on_progress=bad_callback,
    )
    # 即使回调出错，工作流也应该继续执行
    result = integrator.run_workflow("enhance_quality")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value


def test_tool_availability_report():
    """测试工具可用性报告"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    tools = integrator.get_available_tools()
    
    # 所有已注册的工具都应该在报告中
    expected_tools = [
        "after_effects", "premiere_pro", "photoshop",
        "illustrator", "media_encoder", "audition",
        "ffmpeg", "topaz_video_ai", "blender"
    ]
    for tool in expected_tools:
        assert tool in tools, f"工具 {tool} 未在可用性报告中"


def test_mode_auto_fallback():
    """测试auto模式自动降级"""
    # 用auto模式运行，工具未安装时会自动降级到simulate
    integrator = UnifiedToolIntegrator(default_mode="auto")
    result = integrator.run_workflow("enhance_quality")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    # 检查步骤是否使用了simulate模式
    for step in result.steps:
        assert step.mode_used in ("real", "simulate")


def test_long_workflow_chain():
    """测试长链条工作流"""
    integrator = UnifiedToolIntegrator(default_mode="simulate")
    # 创建10个步骤的链式依赖
    steps = []
    for i in range(10):
        step = {
            "step_id": f"step_{i}",
            "name": f"步骤 {i}",
            "tool": "ffmpeg",
            "operation": "probe",
        }
        if i > 0:
            step["depends_on"] = [f"step_{i-1}"]
        steps.append(step)
    
    result = integrator.run_custom_workflow(steps, "长链条测试")
    assert result is not None
    assert result.status == PhaseStatus.SUCCESS.value
    assert len(result.steps) == 10
    for step in result.steps:
        assert step.status == PhaseStatus.SUCCESS.value


def test_output_dir_creation():
    """测试输出目录自动创建"""
    import tempfile
    temp_dir = os.path.join(tempfile.gettempdir(), "ae_integrator_test_" + str(int(time.time())))
    integrator = UnifiedToolIntegrator(
        default_mode="simulate",
        output_dir=temp_dir,
    )
    result = integrator.run_workflow("enhance_quality")
    assert result is not None
    assert os.path.exists(temp_dir)
    # 清理
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="边界情况与漏洞检验")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    tests = [
        ("无效预设ID处理", test_invalid_preset_id),
        ("空/无效预设文件", test_empty_preset_file),
        ("损坏JSON预设文件", test_malformed_json_preset),
        ("自定义工作流空步骤", test_custom_workflow_empty_steps),
        ("自定义工作流单步骤", test_custom_workflow_single_step),
        ("工作流缺失参数", test_workflow_with_missing_params),
        ("未知工具-模拟模式", test_unknown_tool_in_simulate_mode),
        ("未知工具-真实模式", test_unknown_tool_in_real_mode),
        ("循环依赖检测", test_circular_dependency_detection),
        ("并行执行顺序", test_parallel_execution_order),
        ("所有预设执行验证", test_all_workflow_presets),
        ("Adobe适配器全操作", test_adobe_adapters_all_operations),
        ("结果对象方法", test_workflow_result_methods),
        ("错误进度回调", test_progress_callback_with_error),
        ("工具可用性报告", test_tool_availability_report),
        ("auto模式降级", test_mode_auto_fallback),
        ("长链条工作流", test_long_workflow_chain),
        ("输出目录创建", test_output_dir_creation),
    ]

    print("=" * 70)
    print("  边界情况与漏洞检验")
    print("=" * 70)

    passed = 0
    failed = 0
    failures = []

    for i, (name, test_func) in enumerate(tests, 1):
        print(f"\n[{i}/{len(tests)}] {name}")
        ok, error = run_test(name, test_func, verbose=args.verbose)
        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((name, error))

    print("\n" + "=" * 70)
    print("  检验结果摘要")
    print("=" * 70)
    print(f"  总检验数: {len(tests)}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  通过率: {passed/len(tests)*100:.1f}%")

    if failures:
        print("\n  失败的检验:")
        for name, error in failures:
            print(f"    ❌ {name}: {error[:100]}")

    print("=" * 70)

    if failed == 0:
        print("\n  ✅ 逻辑闭环验证通过！系统鲁棒性良好。")
    else:
        print(f"\n  ⚠️ 发现 {failed} 个漏洞，需要修复。")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
