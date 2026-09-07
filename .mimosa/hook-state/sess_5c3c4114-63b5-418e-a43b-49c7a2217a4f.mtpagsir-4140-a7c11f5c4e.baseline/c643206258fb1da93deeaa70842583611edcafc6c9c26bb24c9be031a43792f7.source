"""P1 转场库 E2E 验证: xfade 转场集成到 real_mix 管线

验证目标:
  1. _run_execute_real_mix 消费 transition_plan 数据
  2. 段间使用 xfade 转场而非简单 concat
  3. 输出为真实 MP4 (H.264, >=100KB, 时长合理)
  4. 转场类型/数量记录在输出元数据中

验证方法: 直接调用管线内部方法, 用真实素材执行, 检查真实产物。
"""
import pytest

import sys
import os
import json
import time
import subprocess
from pathlib import Path
pytestmark = pytest.mark.real_e2e


# 确保项目根目录在 path 中
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"


def get_video_info(path: str) -> dict:
    """获取视频基本信息"""
    cmd = [
        FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,codec_name,duration",
        "-show_entries", "format=duration,size",
        "-of", "json", path
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
    if r.returncode != 0:
        return {}
    return json.loads(r.stdout)


def find_test_videos(min_count=3, min_size_kb=50):
    """找到可用的测试视频"""
    data_dir = ROOT / "data" / "real_amv_test"
    if not data_dir.exists():
        return []
    vids = []
    for f in sorted(data_dir.glob("*.mp4")):
        if f.stat().st_size > min_size_kb * 1024:
            vids.append(str(f))
        if len(vids) >= min_count:
            break
    return vids


def test_xfade_transition_e2e():
    """P1 转场库 E2E: 真实素材 + xfade 转场 + 真实 MP4 输出"""
    print("=" * 70)
    print("P1 转场库 E2E 验证: xfade 转场 → real_mix 管线")
    print("=" * 70)

    # 1. 找测试素材
    videos = find_test_videos(min_count=3)
    if len(videos) < 2:
        print(f"[SKIP] 测试素材不足: 只找到 {len(videos)} 个视频")
        return False
    print(f"\n[1] 测试素材: {len(videos)} 个视频")
    for v in videos:
        info = get_video_info(v)
        dur = ""
        if info.get("format"):
            dur = f"{float(info['format'].get('duration', 0)):.1f}s"
        print(f"    {Path(v).name[:50]} ({Path(v).stat().st_size//1024}KB, {dur})")

    # 2. 构建管线配置 (带 transition_plan)
    from pipeline.unified_pipeline import UnifiedPipeline, PipelineConfig

    output_dir = str(ROOT / "output" / "p1_transition_test")
    config = PipelineConfig(
        input_topic="P1转场库验证",
        reference_video=videos[0],
        materials_dir=str(Path(videos[0]).parent),
        output_dir=output_dir,
        ffmpeg_bin=r"C:\ffmpeg\bin\ffmpeg.exe",
        enable_multi_agent=False,
        use_knowledge=False,
    )

    pipeline = UnifiedPipeline(config)

    # 3. 注入 plan 数据 (包含 transition_plan + effect_stack + shot_list)
    # 模拟 plan 阶段输出
    transition_plan = [
        {"from": 0, "to": 1, "type": "dissolve", "duration": 0.6},
        {"from": 1, "to": 2, "type": "wipeleft", "duration": 0.5},
        {"from": 2, "to": 3, "type": "fade", "duration": 0.5},
    ]
    effect_stack = [
        {"name": "neon_color_grade", "params": {"brightness": 0.05, "contrast": 1.2, "saturation": 1.4}},
        {"name": "sharpen_vignette", "params": {"sharpen_amount": 1.5, "vignette_angle": 4.0}},
        {"name": "cool_grade", "params": {"contrast": 1.15, "saturation": 1.2, "temperature": -0.5}},
        {"name": "warm_grade", "params": {"contrast": 1.1, "saturation": 1.3, "temperature": 0.5}},
    ]
    shot_list = []
    for i, v in enumerate(videos[:4]):
        shot_list.append({
            "source": v,
            "start_time": 0.0,
            "end_time": 3.0,
            "transition": transition_plan[i]["type"] if i < len(transition_plan) else "cut",
        })

    # 注入到管线的 _results 中 (模拟 plan 阶段完成)
    from pipeline.unified_pipeline import StageResult, StageStatus
    pipeline._results["plan"] = StageResult(
        stage="plan",
        status=StageStatus.DONE,
        data={
            "shot_list": shot_list,
            "transition_plan": transition_plan,
            "effect_stack": effect_stack,
        }
    )
    pipeline._results["perceive"] = StageResult(
        stage="perceive",
        status=StageStatus.DONE,
        data={"videos": [{"path": v} for v in videos]}
    )

    # 4. 调用 _run_execute_real_mix
    print(f"\n[2] 执行 _run_execute_real_mix (transition_plan={len(transition_plan)} transitions)...")
    t0 = time.time()
    result = pipeline._run_execute_real_mix()
    elapsed = time.time() - t0
    print(f"    耗时: {elapsed:.1f}s")

    # 5. 验证结果
    print(f"\n[3] 执行结果:")
    print(f"    execution_mode: {result.get('execution_mode')}")
    print(f"    mix_method: {result.get('mix_method')}")
    print(f"    output_path: {result.get('output_path', result.get('project_path', ''))}")
    print(f"    layers_created: {result.get('layers_created')}")
    print(f"    effects_applied: {result.get('effects_applied')}")
    print(f"    transitions_applied: {result.get('transitions_applied', [])}")
    print(f"    transition_count: {result.get('transition_count', 0)}")
    print(f"    file_size_mb: {result.get('file_size_mb', 0)}")
    print(f"    total_duration: {result.get('total_duration', 0)}")

    output_path = result.get("output_path") or result.get("project_path", "")

    # 验证条件
    checks = []

    # A. 执行模式正确
    ok_mode = result.get("execution_mode") == "real_mix"
    checks.append(("execution_mode == real_mix", ok_mode))

    # B. 有真实输出文件
    ok_file = bool(output_path) and Path(output_path).is_file()
    checks.append(("output file exists", ok_file))

    # C. 文件大小 >= 100KB (真实视频)
    file_size = Path(output_path).stat().st_size if ok_file else 0
    ok_size = file_size >= 100 * 1024
    checks.append((f"file_size >= 100KB (actual={file_size//1024}KB)", ok_size))

    # D. 转场方法包含 xfade
    mix_method = result.get("mix_method", "")
    ok_xfade = "xfade" in mix_method
    checks.append((f"mix_method contains xfade (actual={mix_method})", ok_xfade))

    # E. 转场数量 > 0
    trans_count = result.get("transition_count", 0)
    ok_trans = trans_count > 0
    checks.append((f"transition_count > 0 (actual={trans_count})", ok_trans))

    # F. 视频时长合理 (>= 5s, 多段拼接)
    total_dur = result.get("total_duration", 0)
    ok_dur = total_dur >= 5.0
    checks.append((f"total_duration >= 5s (actual={total_dur:.1f}s)", ok_dur))

    # G. 视频编码验证 (H.264)
    if ok_file:
        info = get_video_info(output_path)
        codec = ""
        if info.get("streams"):
            codec = info["streams"][0].get("codec_name", "")
        ok_codec = codec == "h264"
        checks.append((f"codec == h264 (actual={codec})", ok_codec))
    else:
        checks.append(("codec == h264", False))

    # 打印验证结果
    print(f"\n[4] 验证结果:")
    all_pass = True
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"    [{status}] {desc}")

    # 总结
    print(f"\n{'='*70}")
    if all_pass:
        print(f"[RESULT] P1 转场库 E2E 验证 PASS")
        print(f"  输出: {output_path}")
        print(f"  大小: {file_size//1024}KB, 时长: {total_dur:.1f}s")
        print(f"  转场: {result.get('transitions_applied', [])}")
        print(f"  方法: {mix_method}")
    else:
        print(f"[RESULT] P1 转场库 E2E 验证 FAIL")
        if result.get("error"):
            print(f"  错误: {result['error']}")
        if result.get("error_code"):
            print(f"  错误码: {result['error_code']}")
    print(f"{'='*70}")

    return all_pass


if __name__ == "__main__":
    success = test_xfade_transition_e2e()
    sys.exit(0 if success else 1)
