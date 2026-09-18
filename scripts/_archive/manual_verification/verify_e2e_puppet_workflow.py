#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端木偶视频化工作流集成测试

测试完整链路:
  PS材质生成 → AE木偶风格化合成 → Resolve调色输出

支持模式:
- full: 完整端到端测试
- ps_ae: 只测试 PS → AE 链路
- ae_resolve: 只测试 AE → Resolve 链路
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def create_test_video(output_path: str, duration: int = 3, width: int = 640, height: int = 360) -> bool:
    """使用 ffmpeg 创建测试视频"""
    ffmpeg = r"D:\app\FormatFactory\ffmpeg.exe"
    if not Path(ffmpeg).exists():
        print(f"[ERROR] ffmpeg 不存在: {ffmpeg}")
        return False

    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size={width}x{height}:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=60)
    return Path(output_path).exists() and Path(output_path).stat().st_size > 0


def step_log(step_num: int, total: int, title: str):
    print(f"\n{'='*60}")
    print(f"[步骤 {step_num}/{total}] {title}")
    print(f"{'='*60}")


def test_phase1_ps_materials(output_dir: Path, mode: str = "auto") -> dict:
    """Phase 1: PS 材质纹理生成"""
    from adobe_suite_integration import PhotoshopConfig, PhotoshopIntegrator

    result = {
        "phase": "PS材质生成",
        "mode": mode,
        "available": False,
        "materials": {},
        "success_count": 0,
        "total_count": 0,
        "real_mode_working": False,
    }

    materials = ["wood", "ceramic", "cloth", "metal"]
    result["total_count"] = len(materials)

    output_dir.mkdir(parents=True, exist_ok=True)

    current_mode = mode

    for i, mat in enumerate(materials, 1):
        print(f"  [{i}/{len(materials)}] 生成 {mat} 纹理 (模式: {current_mode})...")
        output_path = str(output_dir / f"{mat}_texture.png")

        ps_config = PhotoshopConfig(mode=current_mode)
        ps = PhotoshopIntegrator(ps_config)

        if i == 1:
            result["available"] = ps.is_available()

        mat_result = ps.generate_texture(
            material_type=mat,
            size=(512, 512),
            output_path=output_path,
        )

        result["materials"][mat] = {
            "success": mat_result.success,
            "mode": mat_result.mode,
            "duration": mat_result.duration,
            "error": mat_result.error,
            "output_files": mat_result.output_files,
        }

        if mat_result.success:
            result["success_count"] += 1
            for f in mat_result.output_files:
                if Path(f).exists():
                    print(f"    ✓ {mat}: {Path(f).name} ({Path(f).stat().st_size} bytes)")
                else:
                    print(f"    ✓ {mat}: 生成成功")
        else:
            print(f"    ✗ {mat}: {mat_result.error}")

        # 智能降级：第一个材质如果降级到 simulate，后续全部用 simulate
        if i == 1 and mat_result.mode == "simulate" and current_mode != "simulate":
            print("    💡 检测到 real 模式不可用，后续材质将使用 simulate 模式")
            current_mode = "simulate"
        elif i == 1 and mat_result.mode == "real":
            result["real_mode_working"] = True

    result["success"] = result["success_count"] > 0
    return result


def test_phase2_ae_style(input_video: str, output_dir: Path, style: str = "wooden_puppet") -> dict:
    """Phase 2: AE 木偶风格化合成

    生成 AE JSX 脚本，模拟合成效果
    """
    from puppet_style_engine import PuppetStyleConfig, PuppetStyleEngine

    engine = PuppetStyleEngine()

    result = {
        "phase": "AE风格化合成",
        "style": style,
        "effects_count": 0,
        "layers_count": 0,
        "keyframes_count": 0,
        "jsx_generated": False,
        "jsx_path": "",
    }

    # 生成风格化配置
    config = PuppetStyleConfig(
        style_type=style,
        intensity=1.0,
        material="wood",
        comp_width=640,
        comp_height=360,
        bbox={"x": 100, "y": 50, "width": 200, "height": 280},
    )

    # 应用风格
    style_result = engine.generate_style(config)

    result["effects_count"] = len(style_result.effects)
    result["layers_count"] = len(style_result.layers)
    result["keyframes_count"] = len(style_result.keyframes)
    result["adjustment_layers"] = len(style_result.adjustment_layers)

    # 生成简单的 AE JSX 脚本
    jsx_content = generate_puppet_jsx(
        input_video=input_video,
        style=style,
        style_result=style_result,
        comp_width=640,
        comp_height=360,
    )

    jsx_path = output_dir / f"puppet_{style}.jsx"
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx_content)

    result["jsx_generated"] = True
    result["jsx_path"] = str(jsx_path)
    result["jsx_size"] = jsx_path.stat().st_size
    result["success"] = True

    print(f"  ✓ 风格: {style}")
    print(f"    效果数: {result['effects_count']}")
    print(f"    图层数: {result['layers_count']}")
    print(f"    关键帧数: {result['keyframes_count']}")
    print(f"    JSX脚本: {jsx_path.name} ({result['jsx_size']} bytes)")

    return result


def generate_puppet_jsx(input_video: str, style: str, style_result, comp_width: int, comp_height: int) -> str:
    """生成木偶风格化 AE 脚本"""
    input_video_js = input_video.replace("\\", "/")

    effects_js = []
    for i, eff in enumerate(style_result.effects[:10]):
        name = eff.get("name", f"Effect_{i}")
        match_name = eff.get("matchName", "ADBE Effect")
        effects_js.append(f'    // {name}: {match_name}')

    layers_js = []
    for i, layer in enumerate(style_result.layers[:6]):
        name = layer.get("name", f"Layer_{i}")
        ltype = layer.get("type", "adjustment")
        layers_js.append(f'    // 图层: {name} ({ltype})')

    jsx = f"""// 木偶风格化 AE 合成脚本
// 风格: {style}
// 自动生成 - 端到端工作流测试
#target aftereffects

(function() {{
    app.beginUndoGroup("Puppet Style - {style}");

    try {{
        // 创建合成
        var comp = app.project.items.addComp(
            "Puppet_{style}",
            {comp_width}, {comp_height}, 1.0, 5.0, 30
        );

        // 导入视频素材
        var footageFile = new File("{input_video_js}");
        var footageItem = null;
        if (footageFile.exists) {{
            footageItem = app.project.importFile(new ImportOptions(footageFile));
            var videoLayer = comp.layers.add(footageItem);
            videoLayer.name = "视频层";
        }} else {{
            // 创建纯色层作为占位
            var solidLayer = comp.layers.addSolid(
                [0.3, 0.3, 0.4],
                "占位层",
                {comp_width}, {comp_height}, 1.0, 5.0
            );
        }}

        // 添加调整层
        var adjLayer = comp.layers.addSolid(
            [1, 1, 1],
            "风格化调整层",
            {comp_width}, {comp_height}, 1.0, 5.0
        );
        adjLayer.adjustmentLayer = true;

        // 添加风格效果
{chr(10).join(effects_js)}

        // 图层结构
{chr(10).join(layers_js)}

        // 添加基础效果（确保至少有可见效果）
        adjLayer.property("Effects").addProperty("ADBE_CC Toner");
        adjLayer.property("Effects").addProperty("ADBE_Lumetri_Color");
        adjLayer.property("Effects").addProperty("ADBE Fast Blur 2");

        app.endUndoGroup();
        return true;
    }} catch (e) {{
        app.endUndoGroup(false);
        return false;
    }}
}})();
"""
    return jsx


def test_phase3_resolve_grade(input_video: str, output_dir: Path, preset: str = "puppet_warm") -> dict:
    """Phase 3: DaVinci Resolve 调色"""
    from davinci_resolve_integration import (
        DavinciColorist,
        ResolveColorConfig,
    )

    result = {
        "phase": "Resolve调色",
        "preset": preset,
        "available": False,
        "mode": "simulate",
        "success": False,
    }

    try:
        config = ResolveColorConfig(
            mode="auto",
            input_path=input_video,
            output_path=str(output_dir / "graded_output.mp4"),
            color_preset=preset,
            output_format="mp4",
        )

        colorist = DavinciColorist(config)
        result["available"] = colorist.is_available()

        def progress_cb(p, m):
            pass

        grade_result = colorist.color_grade(
            input_path=input_video,
            output_path=str(output_dir / "graded_output.mp4"),
            callback=progress_cb,
        )

        result["mode"] = grade_result.mode
        result["success"] = grade_result.success
        result["nodes_count"] = grade_result.nodes_applied
        result["output_file"] = grade_result.output_path
        result["duration"] = grade_result.duration
        result["error"] = grade_result.error

        print(f"  ✓ 预设: {preset}")
        print(f"    模式: {grade_result.mode}")
        print(f"    节点数: {result['nodes_count']}")
        print(f"    输出: {Path(grade_result.output_path).name if grade_result.output_path else 'N/A'}")
        if grade_result.success and grade_result.output_path and Path(grade_result.output_path).exists():
            print(f"    文件大小: {Path(grade_result.output_path).stat().st_size} bytes")

    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        import traceback
        traceback.print_exc()
        print(f"  ✗ 调色失败: {e}")

    return result


def test_full_workflow(workflow_type: str = "full") -> dict:
    """执行完整工作流测试"""
    print("=" * 60)
    print("  🎭 木偶视频化 - 端到端工作流集成测试")
    print("  Puppet Video Style - E2E Workflow Test")
    print("=" * 60)
    print(f"\n测试类型: {workflow_type}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    output_base = PROJECT_ROOT / "output" / "e2e_test"
    output_base.mkdir(parents=True, exist_ok=True)

    # 创建测试视频
    test_video = str(output_base / "test_input.mp4")
    if not Path(test_video).exists():
        print("\n📌 创建测试视频...")
        if not create_test_video(test_video, duration=3, width=640, height=360):
            print("✗ 无法创建测试视频")
            return {"success": False, "error": "无法创建测试视频"}
        print(f"  ✓ 测试视频已创建: {Path(test_video).stat().st_size} bytes")

    results = {
        "workflow_type": workflow_type,
        "start_time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "test_video": test_video,
        "phases": {},
    }

    total_steps = 0
    current_step = 0

    if workflow_type in ("full", "ps_ae"):
        total_steps += 1
    if workflow_type in ("full", "ps_ae", "ae_only"):
        total_steps += 1
    if workflow_type in ("full", "ae_resolve"):
        total_steps += 1

    # Phase 1: PS 材质生成
    if workflow_type in ("full", "ps_ae"):
        current_step += 1
        step_log(current_step, total_steps, "PS 材质纹理生成")
        phase1_dir = output_base / "materials"
        results["phases"]["ps_materials"] = test_phase1_ps_materials(phase1_dir, mode="auto")

    # Phase 2: AE 风格化合成
    if workflow_type in ("full", "ps_ae", "ae_only", "ae_resolve"):
        current_step += 1
        step_log(current_step, total_steps, "AE 木偶风格化合成")
        phase2_dir = output_base / "ae_comps"
        results["phases"]["ae_style"] = test_phase2_ae_style(
            test_video, phase2_dir, style="wooden_puppet"
        )

    # Phase 3: Resolve 调色
    if workflow_type in ("full", "ae_resolve"):
        current_step += 1
        step_log(current_step, total_steps, "DaVinci Resolve 调色")
        phase3_dir = output_base / "graded"
        results["phases"]["resolve_grade"] = test_phase3_resolve_grade(
            test_video, phase3_dir, preset="puppet_warm"
        )

    # 汇总
    results["end_time"] = time.strftime('%Y-%m-%d %H:%M:%S')

    # 计算整体成功
    all_success = all(
        p.get("success", False) for p in results["phases"].values()
    )
    results["overall_success"] = all_success

    # 保存报告
    report_path = output_base / f"e2e_report_{workflow_type}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    # 打印汇总
    print(f"\n{'='*60}")
    print("  📊 测试结果汇总")
    print(f"{'='*60}")

    for phase_name, phase_result in results["phases"].items():
        status = "✓ 通过" if phase_result.get("success") else "✗ 失败"
        mode = phase_result.get("mode", "N/A")
        print(f"  {status}  {phase_name:20s}  模式: {mode}")

    overall = "✅ 全部通过" if all_success else "❌ 存在失败"
    print(f"\n  整体状态: {overall}")
    print(f"  报告文件: {report_path}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="端到端木偶视频化工作流测试")
    parser.add_argument(
        "--type", "-t",
        choices=["full", "ps_ae", "ae_resolve", "ae_only"],
        default="full",
        help="工作流测试类型 (default: full)",
    )
    args = parser.parse_args()

    result = test_full_workflow(args.type)
    sys.exit(0 if result.get("overall_success") else 1)


if __name__ == "__main__":
    main()
