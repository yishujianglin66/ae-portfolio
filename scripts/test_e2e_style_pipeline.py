#!/usr/bin/env python3
"""
端到端集成测试 - 视频 → 风格 → 参数 → JSX

完整调用链路：
1. 视频分析：VRS → 分析结果
2. 特征提取：分析结果 → 24维特征
3. 风格分类：特征 → 风格标签
4. 参数映射：风格 → 原子参数
5. 脚本生成：参数 → JSX（可选，需compiler）
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


async def run_e2e_test(video_path: str, output_dir: str = "output/e2e_test") -> dict[str, Any]:
    """运行端到端测试
    
    Args:
        video_path: 视频路径
        output_dir: 输出目录
        
    Returns:
        Dict: 完整结果
    """
    # 添加项目根目录到sys.path
    import sys
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    result = {
        "video_path": video_path,
        "stages": {},
        "final_output": None,
        "total_time_ms": 0,
        "errors": [],
    }
    
    start_time = time.time()
    
    # ========== Stage 1: 风格分析 ==========
    print("\n" + "=" * 60)
    print("Stage 1: 风格分析")
    print("=" * 60)
    
    stage1_start = time.time()
    
    try:
        from core.style_pipeline import analyze_video_style
        
        style_result = await analyze_video_style(video_path, enable_vision=False)
        
        result["stages"]["style_analysis"] = {
            "style": style_result.get("style"),
            "confidence": style_result.get("confidence"),
            "latency_ms": style_result.get("latency_ms"),
            "features_dim": len(style_result.get("features", [])),
        }
        
        print(f"  风格: {style_result.get('style')}")
        print(f"  置信度: {style_result.get('confidence', 0):.2%}")
        print(f"  延迟: {style_result.get('latency_ms', 0):.1f}ms")
        
        if style_result.get("error"):
            result["errors"].append(f"Stage 1: {style_result['error']}")
        
    except Exception as e:
        logger.error(f"Stage 1 失败: {e}")
        result["errors"].append(f"Stage 1: {str(e)}")
        style_result = {"style": "cinematic", "confidence": 0.5, "features": []}
    
    stage1_time = (time.time() - stage1_start) * 1000
    print(f"  耗时: {stage1_time:.1f}ms")
    
    # ========== Stage 2: 参数映射 ==========
    print("\n" + "=" * 60)
    print("Stage 2: 参数映射")
    print("=" * 60)
    
    stage2_start = time.time()
    
    try:
        from core.style_preset_adapter import generate_compiler_input, style_to_atomic_params
        
        # 生成原子参数（核心输出）
        atomic_params = style_to_atomic_params(
            style_result.get("style", "cinematic"),
            style_result.get("confidence", 0.5),
        )
        
        # 使用同一个atomic_params生成compiler输入
        compiler_input = generate_compiler_input(style_result)
        compiler_input["atomicParams"] = atomic_params  # 确保使用同一个实例
        
        result["stages"]["param_mapping"] = {
            "effects_count": len(atomic_params.get("effects", [])),
            "adjustments": list(atomic_params.get("adjustments", {}).keys()),
            "latency_ms": (time.time() - stage2_start) * 1000,
        }
        
        print(f"  效果数量: {len(atomic_params.get('effects', []))}")
        print(f"  调整项: {list(atomic_params.get('adjustments', {}).keys())}")
        
        # 保存参数
        params_file = output_path / "atomic_params.json"
        with open(params_file, "w", encoding="utf-8") as f:
            json.dump(atomic_params, f, indent=2, ensure_ascii=False)
        print(f"  参数已保存: {params_file}")
        
    except Exception as e:
        logger.error(f"Stage 2 失败: {e}")
        result["errors"].append(f"Stage 2: {str(e)}")
        atomic_params = {}
    
    stage2_time = (time.time() - stage2_start) * 1000
    print(f"  耗时: {stage2_time:.1f}ms")
    
    # ========== Stage 3: JSX生成（模拟） ==========
    print("\n" + "=" * 60)
    print("Stage 3: JSX生成")
    print("=" * 60)
    
    stage3_start = time.time()
    
    try:
        jsx_code = generate_demo_jsx(style_result, atomic_params)
        
        result["stages"]["jsx_generation"] = {
            "code_length": len(jsx_code),
            "latency_ms": (time.time() - stage3_start) * 1000,
        }
        
        print(f"  代码长度: {len(jsx_code)}字节")
        
        # 保存JSX
        jsx_file = output_path / "output.jsx"
        with open(jsx_file, "w", encoding="utf-8") as f:
            f.write(jsx_code)
        print(f"  JSX已保存: {jsx_file}")
        
        result["final_output"] = str(jsx_file)
        
    except Exception as e:
        logger.error(f"Stage 3 失败: {e}")
        result["errors"].append(f"Stage 3: {str(e)}")
    
    stage3_time = (time.time() - stage3_start) * 1000
    print(f"  耗时: {stage3_time:.1f}ms")
    
    # ========== 汇总 ==========
    total_time = (time.time() - start_time) * 1000
    result["total_time_ms"] = total_time
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print(f"  总耗时: {total_time:.1f}ms")
    print(f"  错误数: {len(result['errors'])}")
    print(f"  输出目录: {output_path}")
    
    # 保存完整结果
    result_file = output_path / "e2e_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  结果已保存: {result_file}")
    
    return result


def generate_demo_jsx(style_result: dict[str, Any], params: dict[str, Any]) -> str:
    """生成演示JSX代码"""
    style = style_result.get("style", "cinematic")
    confidence = style_result.get("confidence", 0)
    effects = params.get("effects", [])
    adjustments = params.get("adjustments", {})
    
    jsx = f"""// Auto-generated AE Script
// Style: {style}
// Confidence: {confidence:.2%}
// Generated by: AE Knowledge Vault Style Pipeline

(function() {{
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) {{
        alert("请先选中一个合成");
        return;
    }}

    app.beginUndoGroup("Apply {style} Style");

    // Get selected layers
    var selectedLayers = comp.selectedLayers;
    if (selectedLayers.length === 0) {{
        alert("请先选择图层");
        app.endUndoGroup();
        return;
    }}

    // Apply effects
    var effectList = [
"""

    # 添加效果列表
    for effect in effects[:5]:  # 限制数量
        name = effect.get("name", "Unknown")
        jsx += f'        "{{matchName: "{name}", name: "{effect.get("displayName", name)}"}}",\n'
    
    jsx += """    ];

    for (var i = 0; i < selectedLayers.length; i++) {
        var layer = selectedLayers[i];
        
        for (var j = 0; j < effectList.length; j++) {
            try {
                var effect = layer.Effects.addProperty(effectList[j].matchName);
                effect.name = effectList[j].name;
            } catch (e) {
                // Effect may not exist
            }
        }
"""

    # 添加调整参数
    if adjustments:
        jsx += "\n        // Apply adjustments\n"
        for key, value in adjustments.items():
            if isinstance(value, bool):
                jsx += f"        // {key}: {value}\n"
            else:
                jsx += f"        // {key}: {value}\n"

    jsx += """    }

    app.endUndoGroup();
    alert("风格应用完成: " + "{style}");
}})();
"""
    
    return jsx


async def main():
    """主函数"""
    import sys
    
    video_path = sys.argv[1] if len(sys.argv) > 1 else "test_video.mp4"
    
    result = await run_e2e_test(video_path)
    
    print("\n" + "=" * 60)
    print("最终结果摘要")
    print("=" * 60)
    for stage_name, stage_data in result["stages"].items():
        print(f"\n{stage_name}:")
        for key, value in stage_data.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())