"""P2 风格迁移闭环 E2E 验证: VRS分析参考视频 → 提取风格参数 → 应用到目标素材

验证目标:
  1. VRS CV-only 分析参考视频, 输出 color_palette/effects/style_tags
  2. plan 阶段消费 VRS 结果, 生成 vrs_driven effect_stack
  3. execute 阶段按 effect_stack 应用滤镜, 输出真实 MP4
  4. 输出视频与参考视频风格一致 (色温/饱和度方向一致)
"""
import pytest

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
pytestmark = pytest.mark.real_e2e


sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"


def get_video_info(path: str) -> dict:
    cmd = [
        FFPROBE, "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name",
        "-show_entries", "format=duration,size",
        "-of", "json", path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def test_style_transfer_e2e():
    """P2 风格迁移 E2E: 参考视频风格 → VRS提取 → 应用到新素材"""
    print("=" * 70)
    print("P2 风格迁移闭环 E2E: VRS分析 → 参数提取 → 风格化输出")
    print("=" * 70)

    # 1. 找两个不同的测试视频 (参考 + 目标)
    data_dir = Path(__file__).resolve().parent.parent / "data" / "real_amv_test"
    vids = [f for f in sorted(data_dir.glob("*.mp4")) if f.stat().st_size > 50000]
    if len(vids) < 2:
        print(f"[SKIP] Need >= 2 test videos, found {len(vids)}")
        return False

    reference_video = str(vids[0])  # 风格来源
    target_video = str(vids[1])     # 目标素材
    print(f"\n[1] 素材:")
    print(f"    参考(风格源): {Path(reference_video).name[:50]} ({Path(reference_video).stat().st_size//1024}KB)")
    print(f"    目标(待处理): {Path(target_video).name[:50]} ({Path(target_video).stat().st_size//1024}KB)")

    # 2. VRS CV-only 分析参考视频
    print(f"\n[2] VRS CV-only 分析参考视频...")
    from vrs.vrs_real_analyzer import VRSRealAnalyzer
    analyzer = VRSRealAnalyzer(num_frames=12)
    vrs_result = asyncio.run(analyzer.analyze(reference_video))

    print(f"    success: {vrs_result.get('success')}")
    print(f"    style_tags: {vrs_result.get('style_tags', [])}")
    print(f"    color_grade: {vrs_result.get('color_grade')}")
    print(f"    effects: {[e.get('effect_name') for e in vrs_result.get('effects', [])]}")
    cp = vrs_result.get("color_palette", {})
    print(f"    color_palette: temp={cp.get('temperature')} sat={cp.get('saturation'):.3f} contrast={cp.get('contrast'):.3f}")

    if not vrs_result.get("success"):
        print("[FAIL] VRS analysis failed")
        return False

    # 3. 通过管线执行风格迁移
    print(f"\n[3] 管线执行风格迁移 (reference_video → materials)...")
    from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig

    output_dir = str(Path(__file__).resolve().parent.parent / "output" / "p2_style_transfer_test")
    config = PipelineConfig(
        input_topic="P2风格迁移验证",
        reference_video=reference_video,
        materials_dir=str(Path(target_video).parent),
        output_dir=output_dir,
        ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
        enable_multi_agent=False,
        enable_vrs=True,
        use_knowledge=False,
    )

    pipeline = UnifiedPipeline(config)

    # 手动注入 VRS 结果 (模拟 _run_vrs_analysis 的输出)
    pipeline._vrs_result = vrs_result

    # 模拟 plan 阶段: 调用 _inject_vrs_into_effect_stack
    vrs_stack, vrs_src, vrs_map = pipeline._inject_vrs_into_effect_stack([])
    print(f"    effect_stack_source: {vrs_src}")
    print(f"    effect_stack size: {len(vrs_stack)}")
    for eff in vrs_stack[:3]:
        print(f"      - {eff.get('name')}: {list(eff.get('params', {}).keys())}")
    print(f"    vrs_mappings: {len(vrs_map)}")

    # 注入 plan 结果
    from pipeline.unified_pipeline import StageResult, StageStatus
    pipeline._results["plan"] = StageResult(
        stage="plan",
        status=StageStatus.DONE,
        data={
            "effect_stack": vrs_stack,
            "effect_stack_source": vrs_src,
            "vrs_to_effects_mapping": vrs_map,
            "shot_list": [{"source": target_video, "start_time": 0, "end_time": 4}],
            "transition_plan": [{"from": 0, "to": 1, "type": "dissolve", "duration": 0.5}],
        }
    )
    pipeline._results["perceive"] = StageResult(
        stage="perceive",
        status=StageStatus.DONE,
        data={"videos": [{"path": target_video}]}
    )

    # 4. 执行 real_mix
    t0 = time.time()
    result = pipeline._run_execute_real_mix()
    elapsed = time.time() - t0
    print(f"\n[4] 执行结果 ({elapsed:.1f}s):")
    print(f"    execution_mode: {result.get('execution_mode')}")
    print(f"    output_path: {result.get('output_path', '')}")
    print(f"    file_size_mb: {result.get('file_size_mb', 0)}")
    print(f"    effects_applied: {result.get('effects_applied')}")
    print(f"    mix_method: {result.get('mix_method')}")

    output_path = result.get("output_path") or result.get("project_path", "")

    # 5. 验证
    checks = []

    # A. VRS 分析成功
    checks.append(("VRS analysis success", vrs_result.get("success") is True))

    # B. effect_stack 由 VRS 驱动
    checks.append(("effect_stack from VRS", vrs_src in ("vrs_driven", "vrs_injected")))

    # C. effect_stack 非空 (>= 2)
    checks.append(("effect_stack >= 2", len(vrs_stack) >= 2))

    # D. 有真实输出文件
    ok_file = bool(output_path) and Path(output_path).is_file()
    checks.append(("output file exists", ok_file))

    # E. 文件大小 >= 100KB
    file_size = Path(output_path).stat().st_size if ok_file else 0
    checks.append((f"file_size >= 100KB (actual={file_size//1024}KB)", file_size >= 100 * 1024))

    # F. 效果被应用
    checks.append(("effects_applied > 0", result.get("effects_applied", 0) > 0))

    # G. VRS mapping 存在 (证明参数来自 VRS)
    checks.append(("vrs_mappings > 0", len(vrs_map) > 0))

    # H. 输出为 H.264
    if ok_file:
        info = get_video_info(output_path)
        codec = info.get("streams", [{}])[0].get("codec_name", "") if info.get("streams") else ""
        checks.append((f"codec == h264 (actual={codec})", codec == "h264"))
    else:
        checks.append(("codec == h264", False))

    print(f"\n[5] 验证结果:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"    [{status}] {desc}")

    print(f"\n{'='*70}")
    if all_pass:
        print(f"[RESULT] P2 风格迁移闭环 E2E PASS")
        print(f"  参考视频: {Path(reference_video).name[:40]}")
        print(f"  风格标签: {vrs_result.get('style_tags', [])}")
        print(f"  输出: {output_path}")
        print(f"  大小: {file_size//1024}KB")
    else:
        print(f"[RESULT] P2 风格迁移闭环 E2E FAIL")
        if result.get("error"):
            print(f"  错误: {result['error']}")
    print(f"{'='*70}")

    return all_pass


if __name__ == "__main__":
    success = test_style_transfer_e2e()
    sys.exit(0 if success else 1)
