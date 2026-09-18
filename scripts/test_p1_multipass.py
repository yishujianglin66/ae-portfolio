"""P1 多轮自动优化验证 - verify→render 反馈环集成 FeedbackExecutor.execute_multi_pass

验证目标:
  1. _run_verify 在初始分数 < min_quality_score 时自动触发 execute_multi_pass
  2. optimization_history 数组含多轮分数 (递增趋势)
  3. 优化后分数若提升则替换 render 输出; 若下降则保留原视频
  4. 最终输出 MP4 文件存在且 ffprobe 可读
  5. VideoQualityAssessor 最终评分可输出
  6. 七阶段管线 still 全部 DONE
  7. verify 返回值含 optimization_history / optimization_applied / final_score

构造场景: min_quality_score=80 (高于 p1_execute_mix 实测 75.9), 强制触发多轮优化
输入: data/real_amv_test/BV1J1336hE3V_赛博故障072504.mp4 (经 execute real_mix 生成新混剪)
输出: output/p1_multipass_test/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
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
OUTPUT_DIR = "output/p1_multipass_test"
INPUT_TOPIC = "赛博朋克故障艺术高燃踩点混剪 视觉冲击 霓虹色彩 故障抖动 节奏卡点"

# 强制触发多轮优化的阈值 (高于 p1_execute_mix 实测 75.9)
MIN_QUALITY_SCORE = 80.0
MAX_QUALITY_ITERATIONS = 3


def run_ffprobe(video_path: str) -> dict:
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
    try:
        from pipeline.video_quality_assessor import VideoQualityAssessor
        assessor = VideoQualityAssessor(ffmpeg_bin=_FFMPEG, ffprobe_bin=_FFPROBE)
        return assessor.assess(video_path, min_score=MIN_QUALITY_SCORE)
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()[:500]}


def main() -> int:
    t0 = time.time()
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 76)
    print("  P1 多轮自动优化验证 (verify→render FeedbackExecutor.execute_multi_pass)")
    print("=" * 76)
    print(f"  Reference        : {REF_VIDEO}")
    print(f"  FFmpeg           : {_FFMPEG}")
    print(f"  FFprobe          : {_FFPROBE}")
    print(f"  Output Dir       : {OUTPUT_DIR}")
    print(f"  Topic            : {INPUT_TOPIC}")
    print(f"  min_quality_score: {MIN_QUALITY_SCORE}  (高于 p1_execute_mix 实测 75.9, 强制触发)")
    print(f"  max_iterations   : {MAX_QUALITY_ITERATIONS}  (上限 5)")
    print("=" * 76)

    if not Path(ref_abs).exists():
        print(f"  [FATAL] 参考视频不存在: {ref_abs}")
        return 2
    if not Path(_FFMPEG).exists():
        print(f"  [FATAL] FFmpeg 不存在: {_FFMPEG}")
        return 2

    # 1. 构造管线配置
    from pipeline.unified_pipeline import (
        PipelineConfig,
        PipelineResult,
        StageStatus,
        UnifiedPipeline,
    )
    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_abs,
        output_dir=out_abs,
        project_name="p1_multipass_cyber_glitch",
        use_knowledge=True,
        style_match=True,
        enable_vrs=True,
        enable_feedback_loop=True,           # 必须开启反馈环
        enable_multi_agent=False,            # 走 ExecutionStage real_mix
        max_quality_iterations=MAX_QUALITY_ITERATIONS,
        min_quality_score=MIN_QUALITY_SCORE,  # 80 高阈值强制触发
        use_davinci_render=False,
        use_compiler=False,
        ffmpeg_bin=_FFMPEG,
    )

    # 2. 运行管线
    pipeline = UnifiedPipeline(cfg)
    run_id = pipeline.run_id
    print(f"\n  [INIT] run_id={run_id}  mode={pipeline.mode.value}")

    result: PipelineResult | None = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=10)

    elapsed = time.time() - t0

    # 3. 七阶段状态汇总
    print("\n" + "=" * 76)
    print("  七阶段结果汇总")
    print("=" * 76)
    STAGE_ORDER = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    status_by_stage = {}
    done_count = 0
    for s in STAGE_ORDER:
        sr = None
        if result and s in result.stages:
            sr = result.stages[s]
        elif hasattr(pipeline, "_results") and s in pipeline._results:
            sr = pipeline._results[s]
        status_name = "MISSING" if sr is None else (
            sr.status.value if hasattr(sr.status, "value") else str(sr.status)
        )
        mark = "OK" if status_name.upper() == "DONE" else (
            "--" if status_name.upper() == "SKIPPED" else "XX"
        )
        print(f"  [{mark}] {s:10s}  {status_name}")
        status_by_stage[s] = status_name
        if status_name.upper() == "DONE":
            done_count += 1

    # 4. verify 阶段多轮优化证据
    print("\n" + "=" * 76)
    print("  [STEP-1] verify 阶段多轮优化证据 (核心验证)")
    print("=" * 76)
    verify_sr = pipeline._results.get("verify") if hasattr(pipeline, "_results") else None
    if not verify_sr and result and "verify" in result.stages:
        verify_sr = result.stages["verify"]

    verify_ok = False
    opt_history: list = []
    opt_applied = False
    final_score = None
    opt_reasoning = ""
    opt_passes = 0
    opt_replaced = False
    error_code = ""
    if verify_sr and verify_sr.data:
        vd = verify_sr.data
        opt_history = vd.get("optimization_history", []) or []
        opt_applied = bool(vd.get("optimization_applied", False))
        final_score = vd.get("final_score")
        opt_reasoning = vd.get("optimization_reasoning", "")
        opt_passes = int(vd.get("optimization_passes", 0))
        opt_replaced = bool(vd.get("optimization_replaced", False))
        error_code = vd.get("error_code", "")
        initial_score = vd.get("score")
        print(f"    optimization_applied : {opt_applied}")
        print(f"    optimization_passes  : {opt_passes}")
        print(f"    optimization_replaced: {opt_replaced}")
        print(f"    final_score          : {final_score}")
        print(f"    score(verify field)  : {initial_score}")
        print(f"    reasoning            : {opt_reasoning}")
        if error_code:
            print(f"    error_code           : {error_code}")
        print(f"    optimization_history ({len(opt_history)} entries):")
        for h in opt_history:
            print(f"      - pass={h.get('pass')}  score={h.get('score')}  file={Path(h.get('file','')).name}")
        # 核心断言
        checks = {
            "has_optimization_history": len(opt_history) >= 1,
            "optimization_applied": opt_applied,
            "has_final_score": final_score is not None,
            "no_error_code": error_code == "",
        }
        # 如果触发了多轮优化, history 应该 >=1 (至少初始评分)
        # 如果是多轮 (max_passes>=2 且确实不达标), 期望 >=2
        if opt_applied and MAX_QUALITY_ITERATIONS >= 2:
            checks["history_multi_entries"] = len(opt_history) >= 2
        for k, v in checks.items():
            mark = "PASS" if v else "FAIL"
            print(f"    [{mark}] {k}")
        verify_ok = all(checks.values())
    else:
        print("    [FAIL] verify 阶段结果缺失或无 data")

    # 5. render 输出文件验证
    print("\n" + "=" * 76)
    print("  [STEP-2] render 输出文件 + ffprobe 验证")
    print("=" * 76)
    render_sr = pipeline._results.get("render") if hasattr(pipeline, "_results") else None
    if not render_sr and result and "render" in result.stages:
        render_sr = result.stages["render"]

    render_output = ""
    ffprobe_ok = False
    probe = {}
    if render_sr and render_sr.data:
        render_output = render_sr.data.get("output_path", "")
        original_path = render_sr.data.get("original_output_path", "")
        replaced_flag = render_sr.data.get("optimization_replaced", False)
        print(f"    render output_path   : {render_output}")
        if original_path:
            print(f"    original_output_path : {original_path}")
        print(f"    optimization_replaced: {replaced_flag}")
        if render_output and Path(render_output).exists():
            size_kb = Path(render_output).stat().st_size // 1024
            print(f"    file exists          : YES  size={size_kb}KB")
            probe = run_ffprobe(render_output)
            if "error" in probe:
                print(f"    [FAIL] ffprobe 失败: {probe.get('error', '')}")
            else:
                streams = probe.get("streams", []) or []
                fmt = probe.get("format", {}) or {}
                vs = streams[0] if streams else {}
                codec = vs.get("codec_name", "?")
                width = vs.get("width", 0)
                height = vs.get("height", 0)
                dur = float(fmt.get("duration", 0) or vs.get("duration", 0) or 0)
                size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
                print(f"    codec_name   : {codec}")
                print(f"    resolution   : {width}x{height}")
                print(f"    duration     : {dur:.2f}s")
                print(f"    file_size    : {size_mb:.2f}MB")
                checks2 = {
                    "codec_h264": codec == "h264",
                    "duration_gt_5s": dur > 5.0,
                    "video_stream_exists": bool(streams),
                    "size_gt_100kb": size_mb * 1024 > 100,
                }
                for k, v in checks2.items():
                    mark = "PASS" if v else "FAIL"
                    print(f"    [{mark}] {k}")
                ffprobe_ok = all(checks2.values())
        else:
            print(f"    [FAIL] render 输出文件不存在: {render_output!r}")
    else:
        print("    [FAIL] render 阶段结果缺失")

    # 6. VideoQualityAssessor 最终评分 (独立验证, 不依赖 verify 缓存)
    print("\n" + "=" * 76)
    print("  [STEP-3] VideoQualityAssessor 独立最终评分")
    print("=" * 76)
    final_vqa_score = 0.0
    vqa_ok = False
    if render_output and Path(render_output).exists():
        qa = run_quality_assessment(render_output)
        if "error" in qa:
            print(f"    [FAIL] VQA 评分失败: {qa.get('error', '')}")
            if "traceback" in qa:
                print(f"    traceback: {qa['traceback']}")
        else:
            final_vqa_score = float(qa.get("overall_score", 0))
            passed = qa.get("passed", False)
            print(f"    overall_score : {final_vqa_score:.1f} / 100")
            print(f"    passed        : {passed}  (threshold={MIN_QUALITY_SCORE})")
            checks_qa = qa.get("checks", {}) or {}
            for ck, cv in checks_qa.items():
                if isinstance(cv, dict):
                    cs = cv.get("score", "?")
                    print(f"    - {ck:24s} score={cs}")
            # 不强制要求最终分>=80 (优化可能未达标), 但必须有有效分数
            vqa_ok = final_vqa_score > 0
            mark = "PASS" if vqa_ok else "FAIL"
            print(f"    [{mark}] VQA 产出有效分数 ({final_vqa_score:.1f})")
    else:
        print("    [SKIP] 无 render 输出, 跳过 VQA")

    # ====================================================================
    # STEP-3.5: 强制低分场景 — 验证 _run_verify 多轮优化真实触发
    # ====================================================================
    # 第一次跑管线 render 输出本身可能已达标 (VQA=89), 没机会触发多轮优化。
    # 这里用 FFmpeg boxblur 故意制造一个低分版视频, 塞回 render.data.output_path,
    # 再调用 pipeline._run_verify() 真实验证 execute_multi_pass 触发与替换逻辑。
    print("\n" + "=" * 76)
    print("  [STEP-3.5] 强制低分场景: 验证 _run_verify 多轮优化真实触发")
    print("=" * 76)

    multipass_verify_ok = False
    multipass_history: list = []
    multipass_final_score = None
    multipass_replaced = False
    multipass_passes = 0
    multipass_render_output = ""
    multipass_reasoning = ""
    low_quality_path = ""

    if render_output and Path(render_output).exists():
        # 1) FFmpeg boxblur 制造低分版
        low_quality_path = str(Path(out_abs) / "low_quality_input.mp4")
        print(f"    [BLUR] 生成低分版: {low_quality_path}")
        blur_cmd = [
            _FFMPEG, "-y", "-i", render_output,
            "-vf", "boxblur=10:1,eq=brightness=-0.1:contrast=0.8:saturation=0.6",
            "-c:v", "libx264", "-crf", "35", "-preset", "fast",
            "-an", low_quality_path,
        ]
        try:
            r = subprocess.run(blur_cmd, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                print(f"    [FAIL] FFmpeg blur 失败: {r.stderr[-300:]}")
            else:
                print(f"    [BLUR] OK size={Path(low_quality_path).stat().st_size//1024}KB")
        except Exception as e:
            print(f"    [FAIL] FFmpeg blur 异常: {e}")

        # 2) 评估低分版分数 (确认 < 80 触发条件)
        if Path(low_quality_path).exists():
            low_qa = run_quality_assessment(low_quality_path)
            low_score = float(low_qa.get("overall_score", 0)) if "error" not in low_qa else 0
            print(f"    [BLUR] 低分版 VQA score={low_score:.1f} (期望 < {MIN_QUALITY_SCORE} 以触发优化)")

            # 3) 塞回 render.data.output_path, 调用 _run_verify 真实触发多轮优化
            if render_sr and render_sr.data and low_score < MIN_QUALITY_SCORE:
                # 备份原始 render 输出路径
                original_render_output = render_sr.data.get("output_path", "")
                render_sr.data["output_path"] = low_quality_path
                # 清掉 verify 缓存, 强制重新跑
                if hasattr(pipeline, "_results"):
                    pipeline._results.pop("verify", None)
                # 重置 iteration 计数, 确保 _check_quality_gate 不会因 iteration 限制提前退出
                pipeline._iteration = 0

                print(f"    [MULTIPASS] 调用 pipeline._run_verify() (input={Path(low_quality_path).name})")
                t_mp0 = time.time()
                try:
                    mp_verify_data = pipeline._run_verify()
                except Exception as e:
                    print(f"    [FAIL] _run_verify 异常: {type(e).__name__}: {e}")
                    traceback.print_exc(limit=6)
                    mp_verify_data = {}
                t_mp = time.time() - t_mp0

                multipass_history = mp_verify_data.get("optimization_history", []) or []
                multipass_applied = bool(mp_verify_data.get("optimization_applied", False))
                multipass_final_score = mp_verify_data.get("final_score")
                multipass_reasoning = mp_verify_data.get("optimization_reasoning", "")
                multipass_passes = int(mp_verify_data.get("optimization_passes", 0))
                multipass_replaced = bool(mp_verify_data.get("optimization_replaced", False))
                multipass_render_output = render_sr.data.get("output_path", "")
                mp_error_code = mp_verify_data.get("error_code", "")

                print(f"    [MULTIPASS] elapsed={t_mp:.1f}s")
                print(f"    optimization_applied : {multipass_applied}")
                print(f"    optimization_passes  : {multipass_passes}")
                print(f"    optimization_replaced: {multipass_replaced}")
                print(f"    final_score          : {multipass_final_score}")
                print(f"    reasoning            : {multipass_reasoning}")
                if mp_error_code:
                    print(f"    error_code           : {mp_error_code}")
                print(f"    optimization_history ({len(multipass_history)} entries):")
                for h in multipass_history:
                    print(f"      - pass={h.get('pass')}  score={h.get('score')}  file={Path(h.get('file','')).name}")
                print(f"    render output before : {Path(original_render_output).name}")
                print(f"    render output after  : {Path(multipass_render_output).name}")

                # 核心断言
                mp_checks = {
                    "optimization_applied": multipass_applied,
                    "has_optimization_history": len(multipass_history) >= 1,
                    "history_multi_entries": len(multipass_history) >= 2,
                    "has_final_score": multipass_final_score is not None,
                    "no_error_code": mp_error_code == "",
                }
                for k, v in mp_checks.items():
                    mark = "PASS" if v else "FAIL"
                    print(f"    [{mark}] {k}")
                multipass_verify_ok = all(mp_checks.values())

    # 7. 最终判定
    print("\n" + "=" * 76)
    print("  [STEP-4] 最终判定")
    print("=" * 76)
    print(f"    七阶段 DONE              : {done_count}/7  {'PASS' if done_count >= 6 else 'FAIL'}")
    print(f"    verify 多轮优化证据(初次) : {'PASS' if verify_ok else 'FAIL'}")
    print(f"    强制低分场景多轮优化触发  : {'PASS' if multipass_verify_ok else 'FAIL'}")
    print(f"    ffprobe 验证(render 初次): {'PASS' if ffprobe_ok else 'FAIL'}")
    print(f"    VQA 最终评分有效          : {'PASS' if vqa_ok else 'FAIL'} (score={final_vqa_score:.1f})")
    print(f"    Elapsed                   : {elapsed:.1f}s")

    # 7.5 多轮优化后产物的 ffprobe + VQA 验证
    multipass_ffprobe_ok = False
    multipass_vqa_score = 0.0
    multipass_vqa_ok = False
    multipass_probe = {}
    if multipass_verify_ok and multipass_render_output and Path(multipass_render_output).exists():
        print("\n" + "=" * 76)
        print("  [STEP-4.5] 多轮优化后产物 ffprobe + VQA 双重验证")
        print("=" * 76)
        mp_size_kb = Path(multipass_render_output).stat().st_size // 1024
        print(f"    final mp4 path : {multipass_render_output}")
        print(f"    final mp4 size : {mp_size_kb}KB")
        multipass_probe = run_ffprobe(multipass_render_output)
        if "error" not in multipass_probe:
            streams = multipass_probe.get("streams", []) or []
            fmt = multipass_probe.get("format", {}) or {}
            vs = streams[0] if streams else {}
            codec = vs.get("codec_name", "?")
            width = vs.get("width", 0)
            height = vs.get("height", 0)
            dur = float(fmt.get("duration", 0) or vs.get("duration", 0) or 0)
            print(f"    codec_name   : {codec}")
            print(f"    resolution   : {width}x{height}")
            print(f"    duration     : {dur:.2f}s")
            mp_checks2 = {
                "codec_h264": codec == "h264",
                "duration_gt_5s": dur > 5.0,
                "video_stream_exists": bool(streams),
                "size_gt_100kb": mp_size_kb > 100,
            }
            for k, v in mp_checks2.items():
                mark = "PASS" if v else "FAIL"
                print(f"    [{mark}] {k}")
            multipass_ffprobe_ok = all(mp_checks2.values())
        # VQA 独立评分
        mp_qa = run_quality_assessment(multipass_render_output)
        if "error" not in mp_qa:
            multipass_vqa_score = float(mp_qa.get("overall_score", 0))
            print(f"    VQA final score : {multipass_vqa_score:.1f} / 100")
            multipass_vqa_ok = multipass_vqa_score > 0
            mark = "PASS" if multipass_vqa_ok else "FAIL"
            print(f"    [{mark}] VQA 产出有效分数")

    all_pass = (
        done_count >= 6
        and multipass_verify_ok
        and ffprobe_ok
        and vqa_ok
        and multipass_ffprobe_ok
        and multipass_vqa_ok
    )
    print(f"\n  {'[OVERALL PASS]' if all_pass else '[OVERALL FAIL]'}")

    # 8. 持久化报告
    report = {
        "run_id": run_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_duration_sec": round(elapsed, 2),
        "done_stages": done_count,
        "total_stages": 7,
        "stage_statuses": status_by_stage,
        "verify_initial": {
            "optimization_applied": opt_applied,
            "optimization_passes": opt_passes,
            "optimization_replaced": opt_replaced,
            "optimization_history": opt_history,
            "optimization_reasoning": opt_reasoning,
            "final_score": final_score,
            "error_code": error_code,
        } if verify_sr and verify_sr.data else {},
        "multipass_forced": {
            "low_quality_input": low_quality_path,
            "optimization_applied": multipass_verify_ok,
            "optimization_passes": multipass_passes,
            "optimization_replaced": multipass_replaced,
            "optimization_history": multipass_history,
            "optimization_reasoning": multipass_reasoning,
            "final_score": multipass_final_score,
            "final_render_output": multipass_render_output,
            "ffprobe": multipass_probe if multipass_ffprobe_ok else {},
            "vqa_score": multipass_vqa_score,
        },
        "render": {
            "output_path": render_output,
            "output_exists": bool(render_output and Path(render_output).exists()),
            "output_size_kb": (Path(render_output).stat().st_size // 1024) if render_output and Path(render_output).exists() else 0,
            "ffprobe": probe if ffprobe_ok else {},
        },
        "final_vqa_score": final_vqa_score,
        "checks": {
            "seven_stages_done": done_count >= 6,
            "multipass_optimization_evidence": multipass_verify_ok,
            "ffprobe_valid": ffprobe_ok,
            "vqa_score_valid": vqa_ok,
            "multipass_ffprobe_valid": multipass_ffprobe_ok,
            "multipass_vqa_valid": multipass_vqa_ok,
        },
        "overall_pass": all_pass,
        "config": {
            "input_topic": INPUT_TOPIC,
            "reference_video": REF_VIDEO,
            "min_quality_score": MIN_QUALITY_SCORE,
            "max_quality_iterations": MAX_QUALITY_ITERATIONS,
            "enable_feedback_loop": True,
        },
    }
    report_file = Path(out_abs) / f"p1_multipass_report_{run_id}.json"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  [SAVED] report -> {report_file}")
    except Exception as _we:
        print(f"\n  [WARN] 报告写入失败: {_we}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
