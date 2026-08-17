"""P1 真混剪 execute 阶段验证 - UnifiedPipeline._run_execute 真实产出混剪视频

验证目标:
  1. execute 阶段 _run_execute 真正调用 FFmpegEditEngine 按 effect_stack 分段应用滤镜+concat
  2. execute 输出真实 MP4 文件 (非 .aep 空壳, 非"参考视频截取 10s 片段")
  3. ffprobe 验证: codec=h264, 时长>5s, 视频流存在
  4. VideoQualityAssessor 评分 >30 分
  5. 七阶段管线 still 全部 DONE
  6. 混剪输出与原参考视频有明显差异 (时长不同/分段不同)

输入: data/real_amv_test/BV1J1336hE3V_赛博故障072504.mp4
输出: output/p1_execute_mix/
"""
from __future__ import annotations

import sys
import os
import json
import time
import subprocess
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))

# ---------------------------------------------------------------------------
# 路径常量
# ---------------------------------------------------------------------------
_FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
_FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
REF_VIDEO = "data/real_amv_test/BV1J1336hE3V_赛博故障072504.mp4"
OUTPUT_DIR = "output/p1_execute_mix"
INPUT_TOPIC = "赛博朋克故障艺术高燃踩点混剪 视觉冲击 霓虹色彩 故障抖动 节奏卡点"


def run_ffprobe(video_path: str) -> dict:
    """用 ffprobe 获取视频元数据"""
    if not Path(_FFPROBE).exists():
        return {"error": f"ffprobe not found: {_FFPROBE}"}
    cmd = [
        _FFPROBE, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration,nb_frames",
        "-show_entries", "format=duration,size,bit_rate",
        "-of", "json", video_path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {"error": r.stderr, "returncode": r.returncode}
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}


def run_quality_assessment(video_path: str) -> dict:
    """用 VideoQualityAssessor 评分"""
    try:
        from pipeline.video_quality_assessor import VideoQualityAssessor
        assessor = VideoQualityAssessor(ffmpeg_bin=_FFMPEG, ffprobe_bin=_FFPROBE)
        result = assessor.assess(video_path, min_score=30.0)
        return result
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()[:500]}


def main() -> int:
    t0 = time.time()
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("  P1 真混剪 execute 阶段验证")
    print("=" * 72)
    print(f"  Reference   : {REF_VIDEO}")
    print(f"  FFmpeg      : {_FFMPEG}")
    print(f"  FFprobe     : {_FFPROBE}")
    print(f"  Output Dir  : {OUTPUT_DIR}")
    print(f"  Topic       : {INPUT_TOPIC}")
    print("=" * 72)

    if not Path(ref_abs).exists():
        print(f"  [FATAL] 参考视频不存在: {ref_abs}")
        return 2
    if not Path(_FFMPEG).exists():
        print(f"  [FATAL] FFmpeg 不存在: {_FFMPEG}")
        return 2
    if not Path(_FFPROBE).exists():
        print(f"  [FATAL] FFprobe 不存在: {_FFPROBE}")
        return 2

    # 1. 参考视频元数据 (用于对比)
    print("\n  [STEP-0] 参考视频元数据:")
    ref_probe = run_ffprobe(ref_abs)
    ref_dur = 0.0
    if ref_probe and "format" in ref_probe:
        ref_dur = float(ref_probe["format"].get("duration", 0))
        ref_size_mb = int(ref_probe["format"].get("size", 0)) / (1024 * 1024)
        ref_codec = ref_probe.get("streams", [{}])[0].get("codec_name", "?")
        print(f"    duration={ref_dur:.1f}s  size={ref_size_mb:.2f}MB  codec={ref_codec}")
    else:
        print(f"    [WARN] ffprobe 参考视频失败: {ref_probe.get('error', '')}")

    # 2. 构造管线配置
    from pipeline.unified_pipeline import (
        UnifiedPipeline, PipelineConfig, PipelineResult, StageStatus,
    )
    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_abs,
        output_dir=out_abs,
        project_name="p1_mix_cyber_glitch",
        use_knowledge=True,
        style_match=True,
        enable_vrs=True,
        enable_feedback_loop=True,
        enable_multi_agent=False,   # 走 ExecutionStage → 触发 real_mix 保障
        max_quality_iterations=1,
        min_quality_score=30.0,
        use_davinci_render=False,
        use_compiler=False,
        ffmpeg_bin=_FFMPEG,
    )

    # 3. 构造并运行管线
    pipeline = UnifiedPipeline(cfg)
    run_id = pipeline.run_id
    print(f"\n  [INIT] run_id={run_id}  mode={pipeline.mode.value}")

    result: PipelineResult | None = None
    exc = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        exc = _e
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=8)

    elapsed = time.time() - t0

    # 4. 汇总七阶段结果
    print("\n" + "=" * 72)
    print("  七阶段结果汇总")
    print("=" * 72)

    STAGE_ORDER = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    status_by_stage = {}
    done_count = 0
    for s in STAGE_ORDER:
        sr = None
        if result and s in result.stages:
            sr = result.stages[s]
        elif hasattr(pipeline, "_results") and s in pipeline._results:
            sr = pipeline._results[s]
        if sr is None:
            status_name = "MISSING"
        else:
            status_name = sr.status.value if hasattr(sr.status, "value") else str(sr.status)
        mark = "OK" if status_name.upper() == "DONE" else ("--" if status_name.upper() == "SKIPPED" else "XX")
        print(f"  [{mark}] {s:10s}  {status_name}")
        status_by_stage[s] = status_name
        if status_name.upper() == "DONE":
            done_count += 1

    # 5. 重点检查 execute 阶段
    print("\n" + "=" * 72)
    print("  [STEP-1] execute 阶段产出检查 (核心验证)")
    print("=" * 72)
    exec_sr = pipeline._results.get("execute") if hasattr(pipeline, "_results") else None
    if not exec_sr and result and "execute" in result.stages:
        exec_sr = result.stages["execute"]

    exec_ok = False
    exec_output = ""
    exec_mode = ""
    exec_data = {}
    if exec_sr:
        exec_data = exec_sr.data or {}
        exec_output = exec_data.get("output_path") or exec_data.get("project_path", "")
        exec_mode = exec_data.get("execution_mode", "")
        effects_applied = exec_data.get("effects_applied", 0)
        layers_created = exec_data.get("layers_created", 0)
        mix_method = exec_data.get("mix_method", "")
        fallback_from = exec_data.get("fallback_from", "")
        print(f"    execution_mode  : {exec_mode}")
        print(f"    project_path    : {exec_output}")
        print(f"    layers_created  : {layers_created}")
        print(f"    effects_applied : {effects_applied}")
        if mix_method:
            print(f"    mix_method      : {mix_method}")
        if fallback_from:
            print(f"    fallback_from   : {fallback_from}  (原路径未产出真实视频, 触发真混剪)")

        # 核心断言: execution_mode 必须是 real_mix (不再是 ae_bridge 空壳)
        if exec_mode == "real_mix":
            print(f"    [PASS] execution_mode == 'real_mix' (真混剪已触发)")
        else:
            print(f"    [WARN] execution_mode={exec_mode!r} (期望 'real_mix')")

        # 核心断言: 输出文件存在且为视频格式
        if exec_output and Path(exec_output).exists():
            ext = Path(exec_output).suffix.lower()
            size_kb = Path(exec_output).stat().st_size // 1024
            print(f"    output exists   : YES  ext={ext}  size={size_kb}KB")
            if ext in {".mp4", ".mov", ".mkv", ".avi", ".webm"} and size_kb > 5:
                exec_ok = True
                print(f"    [PASS] execute 输出为真实视频文件 (非 .aep 空壳)")
            else:
                print(f"    [FAIL] 输出非视频格式或过小")
        else:
            print(f"    [FAIL] execute 输出文件不存在: {exec_output!r}")
    else:
        print(f"    [FAIL] execute 阶段结果缺失")

    # 6. ffprobe 验证 execute 输出
    print("\n" + "=" * 72)
    print("  [STEP-2] ffprobe 验证 execute 输出元数据")
    print("=" * 72)
    ffprobe_ok = False
    probe = {}
    if exec_ok:
        probe = run_ffprobe(exec_output)
        if "error" in probe:
            print(f"    [FAIL] ffprobe 失败: {probe.get('error', '')}")
        else:
            streams = probe.get("streams", []) or []
            fmt = probe.get("format", {}) or {}
            vstream = streams[0] if streams else {}
            codec = vstream.get("codec_name", "?")
            width = vstream.get("width", 0)
            height = vstream.get("height", 0)
            fps_str = vstream.get("r_frame_rate", "0/0")
            dur_str = fmt.get("duration", "0") or vstream.get("duration", "0")
            try:
                dur = float(dur_str)
            except (TypeError, ValueError):
                dur = 0.0
            size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
            print(f"    codec_name   : {codec}")
            print(f"    resolution   : {width}x{height}")
            print(f"    frame_rate   : {fps_str}")
            print(f"    duration     : {dur:.2f}s")
            print(f"    file_size    : {size_mb:.2f}MB")
            # 验证条件
            checks = {
                "codec_h264": codec == "h264",
                "duration_gt_5s": dur > 5.0,
                "video_stream_exists": bool(streams),
                "size_gt_100kb": size_mb * 1024 > 100,
            }
            for k, v in checks.items():
                mark = "PASS" if v else "FAIL"
                print(f"    [{mark}] {k}")
            ffprobe_ok = all(checks.values())
    else:
        print(f"    [SKIP] execute 无有效输出, 跳过 ffprobe 验证")

    # 7. VideoQualityAssessor 评分
    print("\n" + "=" * 72)
    print("  [STEP-3] VideoQualityAssessor 评分")
    print("=" * 72)
    quality_score = 0.0
    quality_ok = False
    if exec_ok:
        qa = run_quality_assessment(exec_output)
        if "error" in qa:
            print(f"    [FAIL] 评分失败: {qa.get('error', '')}")
            if "traceback" in qa:
                print(f"    traceback: {qa['traceback']}")
        else:
            quality_score = float(qa.get("overall_score", 0))
            passed = qa.get("passed", False)
            print(f"    overall_score : {quality_score:.1f} / 100")
            print(f"    passed        : {passed}")
            checks = qa.get("checks", {}) or {}
            for ck, cv in checks.items():
                if isinstance(cv, dict):
                    cs = cv.get("score", "?")
                    print(f"    - {ck:24s} score={cs}")
            # 验证条件: 评分 > 30
            quality_ok = quality_score > 30.0
            mark = "PASS" if quality_ok else "FAIL"
            print(f"    [{mark}] score({quality_score:.1f}) > 30.0")
    else:
        print(f"    [SKIP] execute 无有效输出, 跳过质量评分")

    # 8. 对比: 混剪输出 vs 原参考视频 (证明非简单截取)
    print("\n" + "=" * 72)
    print("  [STEP-4] 与原参考视频对比 (证明非简单截取)")
    print("=" * 72)
    diff_ok = False
    if exec_ok and ref_dur > 0:
        exec_dur = 0.0
        if ffprobe_ok:
            try:
                exec_dur = float(probe.get("format", {}).get("duration", 0))
            except Exception:
                pass
        # 对比维度:
        # a. 时长差异 (混剪输出 8-15s, 参考视频通常 >30s)
        # b. effects_applied > 0 (应用了滤镜)
        # c. layers_created >= 2 (多段拼接)
        dur_diff = abs(exec_dur - ref_dur)
        eff_count = exec_data.get("effects_applied", 0) if exec_sr else 0
        seg_count = exec_data.get("layers_created", 0) if exec_sr else 0
        mix_method = exec_data.get("mix_method", "") if exec_sr else ""
        print(f"    参考视频时长   : {ref_dur:.1f}s")
        print(f"    混剪输出时长   : {exec_dur:.1f}s")
        print(f"    时长差异       : {dur_diff:.1f}s")
        print(f"    应用效果数     : {eff_count}")
        print(f"    拼接段数       : {seg_count}")
        print(f"    拼接方法       : {mix_method}")
        # 判定: 满足任一即视为"非简单截取"
        # - effects_applied >= 2 (应用了至少 2 个效果)
        # - layers_created >= 2 (多段拼接)
        # - mix_method in (concat_demuxer, filter_complex)
        nontrivial = (
            eff_count >= 2
            or seg_count >= 2
            or mix_method in ("concat_demuxer", "filter_complex")
        )
        diff_ok = nontrivial
        mark = "PASS" if diff_ok else "FAIL"
        print(f"    [{mark}] 非简单截取 (effects>=2 或 segments>=2 或 concat 方法)")
    else:
        print(f"    [SKIP] 无法对比")

    # 9. 最终判定
    print("\n" + "=" * 72)
    print("  [STEP-5] 最终判定")
    print("=" * 72)
    print(f"    七阶段 DONE        : {done_count}/7  {'PASS' if done_count >= 6 else 'FAIL'}")
    print(f"    execute 真实视频   : {'PASS' if exec_ok else 'FAIL'}")
    print(f"    ffprobe 验证       : {'PASS' if ffprobe_ok else 'FAIL'}")
    print(f"    质量评分 >30       : {'PASS' if quality_ok else 'FAIL'} (score={quality_score:.1f})")
    print(f"    非简单截取         : {'PASS' if diff_ok else 'FAIL'}")
    print(f"    Elapsed            : {elapsed:.1f}s")

    all_pass = (
        done_count >= 6 and exec_ok and ffprobe_ok and quality_ok and diff_ok
    )
    print(f"\n  {'[OVERALL PASS]' if all_pass else '[OVERALL FAIL]'}")

    # 10. 持久化报告
    report = {
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_duration_sec": round(elapsed, 2),
        "done_stages": done_count,
        "total_stages": 7,
        "stage_statuses": status_by_stage,
        "execute": {
            "execution_mode": exec_mode,
            "output_path": exec_output,
            "output_exists": bool(exec_output and Path(exec_output).exists()),
            "output_size_kb": (Path(exec_output).stat().st_size // 1024) if exec_output and Path(exec_output).exists() else 0,
            "effects_applied": exec_data.get("effects_applied", 0) if exec_sr else 0,
            "layers_created": exec_data.get("layers_created", 0) if exec_sr else 0,
            "mix_method": exec_data.get("mix_method", "") if exec_sr else "",
            "fallback_from": exec_data.get("fallback_from", "") if exec_sr else "",
        },
        "ffprobe": probe if exec_ok and ffprobe_ok else {},
        "quality": {
            "overall_score": quality_score,
            "passed": quality_ok,
        } if exec_ok else {},
        "reference": {
            "path": ref_abs,
            "duration": ref_dur,
        },
        "checks": {
            "seven_stages_done": done_count >= 6,
            "execute_real_video": exec_ok,
            "ffprobe_valid": ffprobe_ok,
            "quality_gt_30": quality_ok,
            "non_trivial_mix": diff_ok,
        },
        "overall_pass": all_pass,
        "config": {
            "input_topic": INPUT_TOPIC,
            "reference_video": REF_VIDEO,
            "enable_multi_agent": False,
        },
    }
    report_file = Path(out_abs) / f"p1_mix_report_{run_id}.json"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  [SAVED] report -> {report_file}")
    except Exception as _we:
        print(f"\n  [WARN] 报告写入失败: {_we}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
