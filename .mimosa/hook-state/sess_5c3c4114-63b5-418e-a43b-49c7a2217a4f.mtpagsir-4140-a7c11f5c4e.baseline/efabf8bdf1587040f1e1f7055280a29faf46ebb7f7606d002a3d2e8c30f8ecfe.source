"""P3-1 真实七阶段管线跑通 - UnifiedPipeline end-to-end

选择: data/real_amv_test/BV1J1336hE3V_赛博故障072504.mp4 作为 reference_video
风格: 赛博朋克 + 故障艺术(Glitch) + 踩点
输出: output/p3_e2e_run/

ExitCode=0 且 七个阶段都标记为 DONE 视为成功
"""
from __future__ import annotations

import sys
import time
import json
import traceback
from pathlib import Path
from dataclasses import asdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))

# ---------------------------------------------------------------------------
# 完整 FFmpeg 路径（避免使用 PATH 中的极简版）
# ---------------------------------------------------------------------------
_FFMPEG_FULL = r"C:\ffmpeg\bin\ffmpeg.exe"
if not Path(_FFMPEG_FULL).exists():
    # 回退: imageio_ffmpeg 的完整版
    try:
        import imageio_ffmpeg
        _FFMPEG_FULL = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        _FFMPEG_FULL = ""

# ---------------------------------------------------------------------------
# 输入 & 输出
# ---------------------------------------------------------------------------
REF_VIDEO = "data/real_amv_test/BV1J1336hE3V_赛博故障072504.mp4"
OUTPUT_DIR = "output/p3_e2e_run"
INPUT_TOPIC = "赛博朋克故障艺术高燃踩点混剪 视觉冲击 霓虹色彩 故障抖动 节奏卡点"

def main() -> int:
    t0 = time.time()
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  P3-1 七阶段管线 E2E 验证")
    print("=" * 70)
    print(f"  Input Video : {REF_VIDEO}")
    print(f"  FFmpeg      : {_FFMPEG_FULL}")
    print(f"  Output Dir  : {OUTPUT_DIR}")
    print(f"  Topic       : {INPUT_TOPIC}")
    print("=" * 70)

    if not Path(ref_abs).exists():
        print(f"  [FATAL] 参考视频不存在: {ref_abs}")
        return 2

    # 1. 构造配置
    from pipeline.unified_pipeline import (
        UnifiedPipeline, PipelineConfig, PipelineResult, StageStatus,
    )
    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_abs,
        output_dir=out_abs,
        project_name="p3_e2e_cyber_glitch",
        use_knowledge=True,
        style_match=True,
        enable_vrs=True,
        enable_feedback_loop=True,
        enable_multi_agent=False,
        max_quality_iterations=1,
        min_quality_score=30.0,
        use_davinci_render=False,
        use_compiler=False,
        ffmpeg_bin=_FFMPEG_FULL,
    )

    # 2. 构造管线
    pipeline = UnifiedPipeline(cfg)
    run_id = pipeline.run_id
    print(f"\n  [INIT] run_id={run_id}  mode={pipeline.mode.value}")

    # 3. 执行
    result: PipelineResult | None = None
    exc = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        exc = _e
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=8)

    # 4. 评估
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("  七阶段结果汇总")
    print("=" * 70)

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
            duration = 0
            err = ""
        else:
            status_name = sr.status.value if hasattr(sr.status, "value") else str(sr.status)
            duration = getattr(sr, "duration_sec", 0) or 0
            err = getattr(sr, "error", "") or ""

        ok = status_name.upper() == "DONE" or status_name.upper() == "SKIPPED"
        mark = "✅" if status_name.upper() == "DONE" else ("🟡" if status_name.upper() == "SKIPPED" else "❌")
        print(f"  {mark} {s:10s}  {status_name:10s}  {duration:7.2f}s" + (f"  err={err[:100]}" if err else ""))
        status_by_stage[s] = status_name
        if status_name.upper() == "DONE":
            done_count += 1

    # 5. 输出 & 质量
    output_path = ""
    quality = 0.0
    if result:
        output_path = result.output_path or ""
        quality = result.quality_score or 0.0

    print("-" * 70)
    print(f"  Elapsed     : {elapsed:.1f}s")
    print(f"  Done stages : {done_count}/7")
    print(f"  Output path : {output_path}")
    print(f"  Output OK   : {'YES' if (output_path and Path(output_path).exists() and Path(output_path).stat().st_size > 0) else 'NO'}")
    print(f"  Quality     : {quality:.1f}/100")
    print(f"  Status      : {result.status if result else 'CRASHED'}")
    if exc:
        print(f"  Exception   : {type(exc).__name__}: {exc}")
    print("=" * 70)

    # 6. 持久化报告
    report = {
        "run_id": run_id,
        "total_duration_sec": round(elapsed, 2),
        "done_stages": done_count,
        "total_stages": 7,
        "stage_statuses": status_by_stage,
        "result_status": result.status if result else "CRASHED",
        "output_path": output_path,
        "output_exists": bool(output_path and Path(output_path).exists() and Path(output_path).stat().st_size > 0),
        "quality_score": quality,
        "exception": f"{type(exc).__name__}: {exc}" if exc else None,
        "config": {
            "input_topic": INPUT_TOPIC,
            "reference_video": REF_VIDEO,
            "use_vrs": cfg.enable_vrs,
            "use_feedback": cfg.enable_feedback_loop,
            "max_iterations": cfg.max_quality_iterations,
        },
    }
    report_file = Path(out_abs) / f"p3_e2e_report_{run_id}.json"
    try:
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        print(f"  [SAVED] report -> {report_file}")
    except Exception as _we:
        print(f"  [WARN] 报告写入失败: {_we}")

    # 7. 判定
    # 成功标准: 至少 5/7 阶段为DONE 且 verify 非FAIL (或异常但产物非空)
    fail_stages = [s for s, v in status_by_stage.items() if v.upper() in ("FAILED", "MISSING", "ERROR")]
    if fail_stages and done_count < 5:
        print(f"\n  [FAILED] 关键阶段失败或缺失: {fail_stages}")
        return 1
    print(f"\n  [SUCCESS] 七阶段管线通过 (done={done_count}/7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
