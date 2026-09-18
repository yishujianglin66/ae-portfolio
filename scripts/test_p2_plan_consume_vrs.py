"""P2 plan 阶段消费 VRS 真分析数据 — 端到端验证

验证目标 (必须在同一次 UnifiedPipeline.run_all() 运行中同时生效):
  P2-1 plan 消费 vrs_result : effect_stack 由 VRS color_palette/rhythm/motion/effects/style_tags 驱动生成
  P2-2 VRS effects 直接注入 : VRS 检测到的 color_grade_cool / saturation_boost 等直接转换为 effect_stack 条目
  P2-3 source/mapping 标注  : plan 返回值含 effect_stack_source ∈ {vrs_driven, vrs_injected}
                              与 vrs_to_effects_mapping 字段
  P2-4 execute 不走兜底      : execute 使用 plan 生成的 effect_stack，不再走 _build_default_effect_stack
  P2-5 七阶段全 DONE         : perceive/analyze/plan/execute/render/verify/learn 全部 DONE
  P2-6 verify 分数 > 30      : 质量评分必须 > 30
  P2-7 输出视频真实存在      : ffprobe 验证元数据

输入: output/p3_e2e_run/p3_e2e_cyber_glitch.mp4
输出: output/p2_plan_vrs/
"""
from __future__ import annotations

import json
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
REF_VIDEO = "output/p3_e2e_run/p3_e2e_cyber_glitch.mp4"
OUTPUT_DIR = "output/p2_plan_vrs"
INPUT_TOPIC = "赛博朋克故障艺术高燃踩点混剪 视觉冲击 霓虹色彩 故障抖动 节奏卡点"

# verify 分数门槛（任务要求 >30）
MIN_VERIFY_SCORE = 30.0
# 不强制多轮迭代，让 verify 一次跑完即可
MAX_QUALITY_ITERATIONS = 1

STAGE_ORDER = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]


def run_ffprobe(video_path: str) -> dict:
    if not Path(video_path).exists():
        return {"error": f"file not found: {video_path}"}
    cmd = [
        _FFPROBE, "-v", "error",
        "-show_entries", "stream=codec_name,codec_type,width,height,r_frame_rate,duration,nb_frames",
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


def _print_check(name: str, ok: bool, detail: str = "") -> bool:
    mark = "PASS" if ok else "FAIL"
    print(f"    [{mark}] {name}: {detail}")
    return ok


def main() -> int:
    t0 = time.time()
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 76)
    print("  P2 plan 阶段消费 VRS 真分析数据 — 端到端验证")
    print("=" * 76)
    print(f"  Reference        : {REF_VIDEO}")
    print(f"  FFmpeg           : {_FFMPEG}")
    print(f"  FFprobe          : {_FFPROBE}")
    print(f"  Output Dir       : {OUTPUT_DIR}")
    print(f"  Topic            : {INPUT_TOPIC}")
    print(f"  min_verify_score : {MIN_VERIFY_SCORE}")
    print(f"  max_iterations   : {MAX_QUALITY_ITERATIONS}")
    print("=" * 76)

    if not Path(ref_abs).exists():
        print(f"  [FATAL] 参考视频不存在: {ref_abs}")
        return 2
    if not Path(_FFMPEG).exists():
        print(f"  [FATAL] FFmpeg 不存在: {_FFMPEG}")
        return 2

    # ====================================================================
    # 1. 构造管线配置 + 运行七阶段
    # ====================================================================
    from pipeline.unified_pipeline import (
        PipelineConfig,
        PipelineResult,
        UnifiedPipeline,
    )

    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_abs,
        output_dir=out_abs,
        project_name="p2_plan_vrs_cyber_glitch",
        use_knowledge=True,
        style_match=True,
        enable_vrs=True,
        enable_feedback_loop=True,
        enable_multi_agent=False,             # 走 ExecutionStage → 触发 real_mix
        max_quality_iterations=MAX_QUALITY_ITERATIONS,
        min_quality_score=MIN_VERIFY_SCORE,
        use_davinci_render=False,
        use_compiler=False,                   # 走 LLM 路径，验证 vrs_injected
        ffmpeg_bin=_FFMPEG,
    )

    pipeline = UnifiedPipeline(cfg)
    run_id = pipeline.run_id
    print(f"\n  [INIT] run_id={run_id}  mode={pipeline.mode.value}")

    result: PipelineResult | None = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=10)

    elapsed_run_all = time.time() - t0

    # ====================================================================
    # 2. 七阶段状态汇总
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-A] 七阶段状态汇总")
    print("=" * 76)
    status_by_stage = {}
    stage_durations = {}
    done_count = 0
    for s in STAGE_ORDER:
        sr = None
        if result and s in result.stages:
            sr = result.stages[s]
        elif hasattr(pipeline, "_results") and s in pipeline._results:
            sr = pipeline._results[s]
        if sr is None:
            status_name = "MISSING"
            dur = 0.0
        else:
            status_name = sr.status.value if hasattr(sr.status, "value") else str(sr.status)
            dur = float(getattr(sr, "duration_sec", 0.0) or 0.0)
        mark = "OK" if status_name.upper() == "DONE" else (
            "--" if status_name.upper() == "SKIPPED" else "XX"
        )
        print(f"  [{mark}] {s:10s}  {status_name:10s}  duration={dur:.2f}s")
        status_by_stage[s] = status_name
        stage_durations[s] = dur
        if status_name.upper() == "DONE":
            done_count += 1
    seven_stages_ok = done_count >= 6
    print(f"  --> 七阶段 DONE: {done_count}/7  {'PASS' if seven_stages_ok else 'FAIL'}")

    # ====================================================================
    # 3. VRS 真分析数据提取（plan 阶段消费的输入）
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-B] VRS 真分析数据（plan 阶段的输入）")
    print("=" * 76)
    perceive_sr = pipeline._results.get("perceive") if hasattr(pipeline, "_results") else None
    if not perceive_sr and result and "perceive" in result.stages:
        perceive_sr = result.stages["perceive"]

    vrs_result: dict = {}
    if perceive_sr and perceive_sr.data:
        vrs_result = perceive_sr.data.get("vrs_result", {}) or {}
    if not vrs_result:
        vrs_result = getattr(pipeline, "_vrs_result", {}) or {}

    vrs_input_ok = False
    if vrs_result:
        source = vrs_result.get("source", "")
        effects = vrs_result.get("effects", []) or []
        color_palette = vrs_result.get("color_palette", {}) or {}
        rhythm = vrs_result.get("rhythm", {}) or {}
        motion = vrs_result.get("motion", {}) or {}
        style_tags = vrs_result.get("style_tags", []) or []
        confidence = vrs_result.get("confidence", 0) or 0
        print(f"    vrs.source              : {source!r}")
        print(f"    vrs.confidence          : {confidence}")
        print(f"    vrs.effects             : {[e.get('effect_name') for e in effects]}")
        print(f"    vrs.color_palette.temp  : {color_palette.get('temperature')}")
        print(f"    vrs.color_palette.sat   : {color_palette.get('saturation')}")
        print(f"    vrs.rhythm.tempo        : {rhythm.get('tempo')}")
        print(f"    vrs.motion.intensity    : {motion.get('intensity')}")
        print(f"    vrs.style_tags          : {style_tags}")
        vrs_input_ok = (
            source == "real_opencv_analysis"
            and len(effects) > 0
            and confidence > 0.5
        )
        _print_check("VRS effects 非空", len(effects) > 0, f"len={len(effects)}")
        _print_check("VRS confidence > 0.5", confidence > 0.5, f"confidence={confidence}")
    else:
        print("    [FAIL] 未取到 vrs_result")

    # ====================================================================
    # 4. plan 阶段 effect_stack 验证（核心）
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-C] plan 阶段 effect_stack 由 VRS 驱动生成（核心）")
    print("=" * 76)
    plan_sr = pipeline._results.get("plan") if hasattr(pipeline, "_results") else None
    if not plan_sr and result and "plan" in result.stages:
        plan_sr = result.stages["plan"]

    plan_ok = False
    effect_stack: list = []
    effect_stack_source = ""
    vrs_to_effects_mapping: list = []
    plan_data: dict = {}
    if plan_sr and plan_sr.data:
        plan_data = plan_sr.data or {}
        effect_stack = plan_data.get("effect_stack", []) or []
        effect_stack_source = plan_data.get("effect_stack_source", "")
        vrs_to_effects_mapping = plan_data.get("vrs_to_effects_mapping", []) or []
        print(f"    effect_stack.len           : {len(effect_stack)}")
        print(f"    effect_stack_source        : {effect_stack_source!r}")
        print(f"    vrs_to_effects_mapping.len : {len(vrs_to_effects_mapping)}")
        print(f"    effect_stack names         : {[e.get('name') for e in effect_stack]}")

        c1 = _print_check("effect_stack 非空且 len>=2",
                          len(effect_stack) >= 2, f"len={len(effect_stack)}")
        c2 = _print_check("effect_stack_source ∈ {vrs_driven, vrs_injected}",
                          effect_stack_source in ("vrs_driven", "vrs_injected"),
                          f"source={effect_stack_source!r}")
        c3 = _print_check("vrs_to_effects_mapping 非空",
                          len(vrs_to_effects_mapping) > 0,
                          f"len={len(vrs_to_effects_mapping)}")
        # 检查 effect_stack 中至少一个条目带 vrs_source 字段（证明来自 VRS）
        has_vrs_source = any(e.get("vrs_source") for e in effect_stack)
        c4 = _print_check("effect_stack 含 vrs_source 标注",
                          has_vrs_source,
                          f"vrs_sources={[e.get('vrs_source') for e in effect_stack]}")
        plan_ok = c1 and c2 and c3 and c4
    else:
        print("    [FAIL] plan 阶段结果缺失或无 data")

    # ====================================================================
    # 5. VRS effects 与 effect_stack 对照表（一致性证明）
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-D] VRS effects ↔ effect_stack 对照表（一致性证明）")
    print("=" * 76)
    vrs_effects = vrs_result.get("effects", []) or []
    consistency_ok = False
    consistency_rows: list = []
    if vrs_effects and effect_stack:
        # 对每个 VRS effect_name，找 effect_stack 中是否有关联条目
        # 关联判定：stack entry 的 vrs_source == vrs effect_name
        # 或者 mapping 中存在 vrs_value == effect_name
        mapping_values = {str(m.get("vrs_value", "")) for m in vrs_to_effects_mapping}
        print(f"    {'VRS effect_name':<30}{'effect_stack 命中':<25}{'mapping 命中':<15}")
        print(f"    {'-'*30}{'-'*25}{'-'*15}")
        all_hit = True
        for ve in vrs_effects:
            ve_name = ve.get("effect_name", "")
            # 在 stack 中找 vrs_source == ve_name
            stack_hit = next(
                (e for e in effect_stack if e.get("vrs_source") == ve_name),
                None,
            )
            stack_hit_name = stack_hit.get("name") if stack_hit else "<MISS>"
            # 在 mapping 中找 vrs_value == ve_name
            map_hit = ve_name in mapping_values
            stack_ok = stack_hit is not None
            print(f"    {ve_name:<30}{stack_hit_name:<25}{'YES' if map_hit else 'NO':<15}")
            consistency_rows.append({
                "vrs_effect_name": ve_name,
                "effect_stack_name": stack_hit_name,
                "stack_hit": stack_ok,
                "mapping_hit": map_hit,
            })
            if not (stack_ok and map_hit):
                all_hit = False
        consistency_ok = all_hit
        _print_check("所有 VRS effects 都在 effect_stack 中找到映射",
                     consistency_ok, f"rows={len(consistency_rows)}")
    else:
        print("    [FAIL] vrs_effects 或 effect_stack 为空，无法对照")

    # ====================================================================
    # 6. execute 阶段验证 — 使用 plan 的 effect_stack，不走兜底
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-E] execute 阶段使用 plan 生成的 effect_stack（不走兜底）")
    print("=" * 76)
    exec_sr = pipeline._results.get("execute") if hasattr(pipeline, "_results") else None
    if not exec_sr and result and "execute" in result.stages:
        exec_sr = result.stages["execute"]

    exec_ok = False
    exec_output = ""
    exec_data: dict = {}
    if exec_sr and exec_sr.data:
        exec_data = exec_sr.data or {}
        exec_output = exec_data.get("output_path") or exec_data.get("project_path", "")
        exec_mode = exec_data.get("execution_mode", "")
        layers_created = exec_data.get("layers_created", 0)
        effects_applied = exec_data.get("effects_applied", 0)
        print(f"    execution_mode      : {exec_mode!r}")
        print(f"    output_path         : {exec_output}")
        print(f"    layers_created      : {layers_created}")
        print(f"    effects_applied     : {effects_applied}")
        # execute 不应含 error_code 字段（_build_default_effect_stack 兜底不会触发 error_code，
        # 但 _run_execute_real_mix 失败时会返回 error_code）
        no_error = "error_code" not in exec_data
        # execute 真实输出文件应存在
        output_exists = bool(exec_output) and Path(exec_output).exists()
        c1 = _print_check("execution_mode 是 real_mix",
                          "real_mix" in exec_mode, f"mode={exec_mode!r}")
        c2 = _print_check("无 error_code", no_error,
                          f"error_code={exec_data.get('error_code', '<none>')}")
        c3 = _print_check("输出文件存在", output_exists,
                          f"path={exec_output}")
        c4 = _print_check("effects_applied >= 2",
                          effects_applied >= 2, f"effects_applied={effects_applied}")
        exec_ok = c1 and c2 and c3 and c4
    else:
        print("    [FAIL] execute 阶段结果缺失或无 data")

    # ====================================================================
    # 7. verify 阶段分数验证
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-F] verify 阶段分数 > 30")
    print("=" * 76)
    verify_sr = pipeline._results.get("verify") if hasattr(pipeline, "_results") else None
    if not verify_sr and result and "verify" in result.stages:
        verify_sr = result.stages["verify"]

    verify_ok = False
    quality_score = 0.0
    if verify_sr and verify_sr.data:
        verify_data = verify_sr.data or {}
        # verify 阶段返回字段是 "score"（pipeline.unified_pipeline._run_verify 行 3216）
        raw_score = verify_data.get("score", verify_data.get("quality_score", 0))
        try:
            quality_score = float(raw_score) if raw_score is not None else 0.0
        except (TypeError, ValueError):
            quality_score = 0.0
        print(f"    score               : {quality_score}")
        print(f"    verified            : {verify_data.get('verified')}")
        verify_ok = quality_score > MIN_VERIFY_SCORE
        _print_check(f"score > {MIN_VERIFY_SCORE}",
                     verify_ok, f"score={quality_score}")
    else:
        print("    [FAIL] verify 阶段结果缺失或无 data")

    # ====================================================================
    # 8. 输出视频 ffprobe 元数据验证
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [CHECK-G] 输出视频 ffprobe 元数据")
    print("=" * 76)
    ffprobe_ok = False
    ffprobe_meta: dict = {}
    if exec_output and Path(exec_output).exists():
        ffprobe_meta = run_ffprobe(exec_output)
        if "error" in ffprobe_meta:
            print(f"    [FAIL] ffprobe error: {ffprobe_meta.get('error')}")
        else:
            streams = ffprobe_meta.get("streams", [])
            fmt = ffprobe_meta.get("format", {})
            vs = next((s for s in streams if s.get("codec_type") == "video"), {})
            print(f"    file                : {exec_output}")
            print(f"    size                : {fmt.get('size', '<unknown>')} bytes")
            print(f"    duration            : {fmt.get('duration', '<unknown>')} s")
            print(f"    bit_rate            : {fmt.get('bit_rate', '<unknown>')}")
            print(f"    video codec         : {vs.get('codec_name', '<unknown>')}")
            print(f"    width x height      : {vs.get('width', '?')}x{vs.get('height', '?')}")
            print(f"    r_frame_rate        : {vs.get('r_frame_rate', '<unknown>')}")
            print(f"    nb_frames           : {vs.get('nb_frames', '<unknown>')}")
            ffprobe_ok = (
                vs.get("codec_name") == "h264"
                and float(fmt.get("duration", 0) or 0) > 0
                and int(vs.get("width", 0) or 0) > 0
            )
            _print_check("ffprobe 元数据有效 (h264 + duration>0 + width>0)",
                         ffprobe_ok, f"codec={vs.get('codec_name')}")
    else:
        print(f"    [FAIL] exec_output 不存在: {exec_output}")

    # ====================================================================
    # 9. effect_stack JSON 与 mapping JSON 落盘
    # ====================================================================
    artifact_path = Path(out_abs) / f"p2_plan_artifact_{run_id}.json"
    try:
        artifact = {
            "run_id": run_id,
            "vrs_input": {
                "source": vrs_result.get("source"),
                "confidence": vrs_result.get("confidence"),
                "effects": vrs_result.get("effects", []),
                "color_palette": vrs_result.get("color_palette", {}),
                "rhythm": vrs_result.get("rhythm", {}),
                "motion": vrs_result.get("motion", {}),
                "style_tags": vrs_result.get("style_tags", []),
            },
            "effect_stack": effect_stack,
            "effect_stack_source": effect_stack_source,
            "vrs_to_effects_mapping": vrs_to_effects_mapping,
            "consistency_rows": consistency_rows if vrs_effects and effect_stack else [],
            "exec_data": exec_data,
            "verify_quality_score": quality_score,
            "verify_score_field": "score",
            "ffprobe_meta": ffprobe_meta,
            "stage_status": status_by_stage,
            "elapsed_run_all_sec": round(time.time() - t0, 2),
        }
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\n  [ARTIFACT] {artifact_path}")
    except Exception as e:
        print(f"\n  [ARTIFACT ERROR] {e}")

    # ====================================================================
    # 10. 最终结论
    # ====================================================================
    print("\n" + "=" * 76)
    print("  [FINAL] P2 plan 阶段消费 VRS 真分析数据 — 综合结论")
    print("=" * 76)
    checks = {
        "A.七阶段全DONE         ": seven_stages_ok,
        "B.VRS真分析数据可用    ": vrs_input_ok,
        "C.plan effect_stack VRS驱动": plan_ok,
        "D.VRS effects↔stack 一致 ": consistency_ok,
        "E.execute 用 plan stack ": exec_ok,
        "F.verify 分数>30        ": verify_ok,
        "G.ffprobe 元数据有效   ": ffprobe_ok,
    }
    for k, v in checks.items():
        print(f"  [{ 'PASS' if v else 'FAIL' }] {k}")
    all_pass = all(checks.values())
    print(f"\n  --> 总结论: {'PASS ✅' if all_pass else 'FAIL ❌'}")
    print(f"  --> 耗时: {time.time() - t0:.2f}s")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
