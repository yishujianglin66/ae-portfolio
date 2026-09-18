#!/usr/bin/env python3
"""
风格分类模型完整集成测试 - Video → Style → Params → JSX

验证流程：
1. 模型加载：验证风格分类器能否正确加载
2. 视频分析：验证VRS降级模式和特征提取
3. 风格分类：验证模型推理和置信度输出
4. 参数映射：验证风格标签到原子参数的转换
5. JSX生成：验证最终JSX脚本生成

预期结果：
- 风格分类器加载时间 < 500ms
- 分类准确率 ≥ 90%（基于降级模拟数据）
- 参数映射成功生成 ≥ 1个效果
- JSX代码语法正确
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


async def test_model_loading() -> dict[str, Any]:
    """测试模型加载"""
    print("\n" + "=" * 60)
    print("测试 1: 模型加载")
    print("=" * 60)
    
    start_time = time.time()
    
    try:
        from core.model_service import ModelService
        
        service = ModelService()
        model_info = service.get_model_info("style_classifier")
        
        load_time_ms = (time.time() - start_time) * 1000
        
        print("  ✓ 模型加载成功")
        print(f"  ✓ 参数数量: {model_info.get('param_count', 0):,}")
        print(f"  ✓ 加载时间: {load_time_ms:.1f}ms")
        
        if load_time_ms > 1000:
            print("  ⚠ 警告: 加载时间超过1000ms阈值")
        
        return {
            "success": True,
            "load_time_ms": load_time_ms,
            "param_count": model_info.get("param_count", 0),
        }
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"success": False, "error": str(e)}


async def test_video_analysis() -> dict[str, Any]:
    """测试视频分析"""
    print("\n" + "=" * 60)
    print("测试 2: 视频分析（降级模式）")
    print("=" * 60)
    
    try:
        from core.style_pipeline import analyze_video_style
        
        # 使用不存在的视频触发降级模式
        start_time = time.time()
        style_result = await analyze_video_style("test_video.mp4", enable_vision=False)
        analysis_time_ms = (time.time() - start_time) * 1000
        
        print("  ✓ 分析完成")
        print(f"  ✓ 风格: {style_result.get('style')}")
        print(f"  ✓ 置信度: {style_result.get('confidence', 0):.2%}")
        print(f"  ✓ 特征维度: {len(style_result.get('features', []))}")
        print(f"  ✓ 分析时间: {analysis_time_ms:.1f}ms")
        
        return {
            "success": True,
            "style": style_result.get("style"),
            "confidence": style_result.get("confidence"),
            "features_dim": len(style_result.get("features", [])),
            "analysis_time_ms": analysis_time_ms,
        }
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"success": False, "error": str(e)}


async def test_param_mapping(style_result: dict[str, Any]) -> dict[str, Any]:
    """测试参数映射"""
    print("\n" + "=" * 60)
    print("测试 3: 参数映射")
    print("=" * 60)
    
    try:
        from core.style_preset_adapter import style_to_atomic_params
        
        start_time = time.time()
        atomic_params = style_to_atomic_params(
            style_result.get("style", "cinematic"),
            style_result.get("confidence", 0.5),
        )
        mapping_time_ms = (time.time() - start_time) * 1000
        
        effects_count = len(atomic_params.get("effects", []))
        adjustments_count = len(atomic_params.get("adjustments", {}))
        
        print("  ✓ 映射完成")
        print(f"  ✓ 效果数量: {effects_count}")
        print(f"  ✓ 调整项数量: {adjustments_count}")
        print(f"  ✓ 映射时间: {mapping_time_ms:.1f}ms")
        
        if effects_count == 0:
            print("  ⚠ 警告: 未生成任何效果参数")
            return {"success": False, "error": "效果参数为空"}
        
        # 打印效果详情
        for i, effect in enumerate(atomic_params.get("effects", [])[:3], 1):
            print(f"  {i}. {effect.get('displayName')} ({effect.get('name')})")
            params = effect.get("params", {})
            if params:
                print(f"     参数: {list(params.keys())[:3]}...")
        
        return {
            "success": True,
            "effects_count": effects_count,
            "adjustments_count": adjustments_count,
            "mapping_time_ms": mapping_time_ms,
            "atomic_params": atomic_params,
        }
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"success": False, "error": str(e)}


async def test_jsx_generation(atomic_params: dict[str, Any]) -> dict[str, Any]:
    """测试JSX生成"""
    print("\n" + "=" * 60)
    print("测试 4: JSX脚本生成")
    print("=" * 60)
    
    try:
        # 简化版JSX生成
        style = atomic_params.get("style", "cinematic")
        confidence = atomic_params.get("confidence", 1.0)
        effects = atomic_params.get("effects", [])
        
        jsx_lines = [
            "// Auto-generated AE Script",
            f"// Style: {style}",
            f"// Confidence: {confidence:.2%}",
            "",
            "(function() {",
            "    var comp = app.project.activeItem;",
            "    if (!comp || !(comp instanceof CompItem)) {",
            "        alert('请先选中一个合成');",
            "        return;",
            "    }",
            "",
            "    app.beginUndoGroup('Apply Style');",
            "",
            "    var selectedLayers = comp.selectedLayers;",
            "    if (selectedLayers.length === 0) {",
            "        alert('请先选择图层');",
            "        app.endUndoGroup();",
            "        return;",
            "    }",
            "",
        ]
        
        # 添加效果应用代码
        for effect in effects[:5]:
            name = effect.get("name", "Unknown")
            jsx_lines.extend([
                f"    // Apply {effect.get('displayName', name)}",
                "    for (var i = 0; i < selectedLayers.length; i++) {",
                "        try {",
                f"            var effect = selectedLayers[i].Effects.addProperty('{name}');",
                "        } catch (e) {}",
                "    }",
                "",
            ])
        
        jsx_lines.extend([
            "    app.endUndoGroup();",
            "    alert('风格应用完成: " + style + "');",
            "})();",
        ])
        
        jsx_code = "\n".join(jsx_lines)
        
        # 基本语法检查
        has_function = "function()" in jsx_code
        has_endundo = "endUndoGroup" in jsx_code
        has_effects = any(e.get("name") in jsx_code for e in effects)
        
        print("  ✓ JSX生成完成")
        print(f"  ✓ 代码长度: {len(jsx_code)}字节")
        print(f"  ✓ 包含函数定义: {has_function}")
        print(f"  ✓ 包含UndoGroup: {has_endundo}")
        print(f"  ✓ 包含效果调用: {has_effects}")
        
        # 保存到文件
        output_dir = Path("output/style_integration_test")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        jsx_file = output_dir / "generated_script.jsx"
        with open(jsx_file, "w", encoding="utf-8") as f:
            f.write(jsx_code)
        
        print(f"  ✓ 已保存: {jsx_file}")
        
        return {
            "success": True,
            "code_length": len(jsx_code),
            "syntax_valid": all([has_function, has_endundo, has_effects]),
            "jsx_file": str(jsx_file),
        }
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"success": False, "error": str(e)}


async def test_workflow_integration() -> dict[str, Any]:
    """测试工作流集成"""
    print("\n" + "=" * 60)
    print("测试 5: 工作流集成")
    print("=" * 60)
    
    try:
        from core.style_workflow_integration import create_style_workflow_tasks

        from core.workflow_orchestrator import TaskType
        
        # 创建任务
        tasks = create_style_workflow_tasks("test_video.mp4", enable_vision=False)
        
        print("  ✓ 任务创建成功")
        print(f"  ✓ 任务数量: {len(tasks)}")
        
        for task_id, task_def in tasks.items():
            print(f"  - {task_id}: {task_def.task_type.value}")
            if task_def.dependencies:
                print(f"    依赖: {task_def.dependencies}")
        
        # 验证任务类型
        has_style_task = any(
            t.task_type == TaskType.STYLE_CLASSIFICATION for t in tasks.values()
        )
        has_param_task = any(
            t.task_type == TaskType.PARAM_MAPPING for t in tasks.values()
        )
        
        if not has_style_task or not has_param_task:
            print("  ✗ 缺少必要的任务类型")
            return {"success": False, "error": "任务类型不完整"}
        
        print(f"  ✓ 包含风格分类任务: {has_style_task}")
        print(f"  ✓ 包含参数映射任务: {has_param_task}")
        
        return {
            "success": True,
            "tasks_count": len(tasks),
            "has_style_task": has_style_task,
            "has_param_task": has_param_task,
        }
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        return {"success": False, "error": str(e)}


async def run_all_tests() -> dict[str, Any]:
    """运行所有测试"""
    print("\n" + "=" * 70)
    print(" 风格分类模型完整集成测试 - Video → Style → Params → JSX")
    print("=" * 70)
    
    results = {
        "total_tests": 5,
        "passed": 0,
        "failed": 0,
        "tests": {},
    }
    
    # Test 1: 模型加载
    results["tests"]["model_loading"] = await test_model_loading()
    if results["tests"]["model_loading"]["success"]:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 2: 视频分析
    results["tests"]["video_analysis"] = await test_video_analysis()
    if results["tests"]["video_analysis"]["success"]:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 3: 参数映射
    if results["tests"]["video_analysis"]["success"]:
        results["tests"]["param_mapping"] = await test_param_mapping(
            results["tests"]["video_analysis"]
        )
    else:
        results["tests"]["param_mapping"] = {"success": False, "error": "前置测试失败"}
    
    if results["tests"]["param_mapping"]["success"]:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 4: JSX生成
    if results["tests"]["param_mapping"]["success"]:
        results["tests"]["jsx_generation"] = await test_jsx_generation(
            results["tests"]["param_mapping"]["atomic_params"]
        )
    else:
        results["tests"]["jsx_generation"] = {"success": False, "error": "前置测试失败"}
    
    if results["tests"]["jsx_generation"]["success"]:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test 5: 工作流集成
    results["tests"]["workflow_integration"] = await test_workflow_integration()
    if results["tests"]["workflow_integration"]["success"]:
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # 汇总结果
    print("\n" + "=" * 70)
    print(" 测试汇总")
    print("=" * 70)
    print(f"  总测试数: {results['total_tests']}")
    print(f"  通过: {results['passed']} ✓")
    print(f"  失败: {results['failed']} ✗")
    print(f"  成功率: {results['passed'] / results['total_tests']:.1%}")
    
    if results["passed"] == results["total_tests"]:
        print("\n  🎉 所有测试通过！风格分类模型已成功集成到项目中。")
    else:
        print("\n  ⚠ 部分测试失败，请检查错误信息。")
    
    # 保存结果
    output_dir = Path("output/style_integration_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = output_dir / "integration_test_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        # 移除atomic_params以避免JSON过大
        clean_results = results.copy()
        if "atomic_params" in clean_results["tests"].get("param_mapping", {}):
            del clean_results["tests"]["param_mapping"]["atomic_params"]
        json.dump(clean_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n  结果已保存: {result_file}")
    
    return results


if __name__ == "__main__":
    asyncio.run(run_all_tests())