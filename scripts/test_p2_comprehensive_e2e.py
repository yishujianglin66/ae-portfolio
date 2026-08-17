"""P2 综合端到端验证 — 三项新能力在同一管线运行中同时生效且无回归

验证目标 (必须在同一次 UnifiedPipeline.run_all() 运行中同时生效):
  能力1 plan 消费 VRS (P2-1+P2-3):
    - plan.effect_stack 非空且 len>=2
    - plan.effect_stack_source ∈ {vrs_driven, vrs_injected}
    - plan.vrs_to_effects_mapping 非空
    - effect_stack 中至少 1 个条目 vrs_source 字段非空 (证明来自 VRS 映射)
  能力2 多素材混剪 (P2-2):
    - execute.source_count >= 2
    - execute.mix_mode == "multi_source"
    - 输出视频真实存在 size>50KB
    - ffprobe: codec=h264, duration>5s, 视频流存在
  能力3 VRS effects 与 effect_stack 一致性 (P2-3):
    - perceive.vrs_result.effects 中至少 1 个效果在 effect_stack 中有对应条目 (vrs_source 匹配)
  能力4 七阶段全 DONE:
    - perceive/analyze/plan/execute/render/verify/learn 全部 DONE
  能力5 物理输出视频验证:
    - 最终 MP4 存在, ffprobe: codec=h264, duration>5s, 视频流存在, size>50KB
  能力6 多轮自动优化不回归 (P1-3 防回归):
    - verify 必须返回 optimization_history 字段 (无论是否触发优化)

构造场景:
  - reference_video: output/p3_e2e_run/p3_e2e_cyber_glitch.mp4 (cyber 故障, 已知触发 VRS effects)
  - materials_dir  : 4 个 FFmpeg lavfi 生成的真正不同素材 (testsrc/smptebars/rgbtestsrc/yuvtestsrc)
  - enable_vrs=True, enable_multi_agent=False (走 _run_execute_real_mix), use_compiler=False (走 LLM+vrs_injected)
  - min_quality_score=30 (让 verify 直接通过, 不强制多轮), max_quality_iterations=1

输出: output/p2_comprehensive_e2e/
"""
from __future__ import annotations

import hashlib
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
OUTPUT_DIR = "output/p2_comprehensive_e2e"
MATERIALS_DIR = "output/p2_comprehensive_e2e/inputs"
INPUT_TOPIC = "赛博朋克故障艺术高燃踩点混剪 多素材拼接 霓虹色彩 故障抖动 节奏卡点"

MIN_VERIFY_SCORE = 30.0
MAX_QUALITY_ITERATIONS = 1

STAGE_ORDER = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]

# 真实视频素材切片 (从 p3_e2e_cyber_glitch.mp4 截取不同片段+不同色调, 像素内容真正不同)
# 不再使用 lavfi testsrc/smptebars 等低质量测试图案 (640x480)
# (文件名, 起始时间s, 时长s, 色调滤镜, 描述)
REAL_VIDEO_CLIPS = [
    ("src_clip_a.mp4", 0.0, 4.0, "hue=h=30:s=1.2",                                "片段A: 0-4s 暖色调"),
    ("src_clip_b.mp4", 4.0, 4.0, "hue=h=200:s=1.1",                               "片段B: 4-8s 冷色调"),
    ("src_clip_c.mp4", 8.0, 4.0, "eq=brightness=0.08:contrast=1.2:saturation=1.5", "片段C: 8-12s 高饱和"),
    ("src_clip_d.mp4", 2.0, 4.0, "hue=h=120:s=1.3",                                "片段D: 2-6s 绿色调"),
]


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


def generate_materials(materials_abs: str, ref_video_abs: str = "") -> list:
    """用真实视频 (p3_e2e_cyber_glitch.mp4) 切片+不同色调生成 4 个不同素材。

    不再使用 lavfi testsrc/smptebars (640x480 低质量测试图案)。
    每个片段从真实视频不同时间段截取 + 应用不同色调滤镜, 像素内容真正不同。
    返回 [(path, desc), ...]。
    """
    Path(materials_abs).mkdir(parents=True, exist_ok=True)
    src_video = ref_video_abs or str(PROJECT_ROOT / REF_VIDEO)
    if not Path(src_video).exists():
        print(f"    [FATAL] 真实源视频不存在: {src_video}")
        return []
    generated = []
    for fname, start, dur, color_filter, desc in REAL_VIDEO_CLIPS:
        out_path = str(Path(materials_abs) / fname)
        if Path(out_path).exists() and Path(out_path).stat().st_size > 10240:
            print(f"    [SKIP-EXISTS] {fname} ({Path(out_path).stat().st_size // 1024}KB)")
            generated.append((out_path, desc))
            continue
        # 用真实视频作为输入, 截取不同时间段 + 应用不同色调滤镜
        cmd = [
            _FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start:.3f}",
            "-i", src_video,
            "-t", f"{dur:.3f}",
            "-vf", color_filter,
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-b:v", "4M", "-maxrate", "8M", "-bufsize", "16M",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            out_path,
        ]
        print(f"    [GEN] {fname} <= real:{Path(src_video).name}[{start:.1f}-{start+dur:.1f}s] {color_filter}")
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not Path(out_path).exists():
            print(f"    [GEN FAIL] {fname}: rc={r.returncode} stderr={r.stderr[-300:]}")
            continue
        size_kb = Path(out_path).stat().st_size // 1024
        print(f"    [GEN OK]  {fname} ({size_kb}KB) - {desc}")
        generated.append((out_path, desc))
    return generated


def main() -> int:
    t0 = time.time()
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    materials_abs = str(PROJECT_ROOT / MATERIALS_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("  P2 综合端到端验证 — 三项新能力同时生效且无回归")
    print("=" * 78)
    print(f"  Reference        : {REF_VIDEO}")
    print(f"  FFmpeg           : {_FFMPEG}")
    print(f"  FFprobe          : {_FFPROBE}")
    print(f"  Output Dir       : {OUTPUT_DIR}")
    print(f"  Materials Dir    : {MATERIALS_DIR}")
    print(f"  Topic            : {INPUT_TOPIC}")
    print(f"  min_verify_score : {MIN_VERIFY_SCORE}")
    print(f"  max_iterations   : {MAX_QUALITY_ITERATIONS}")
    print("=" * 78)

    if not Path(ref_abs).exists():
        print(f"  [FATAL] 参考视频不存在: {ref_abs}")
        return 2
    if not Path(_FFMPEG).exists():
        print(f"  [FATAL] FFmpeg 不存在: {_FFMPEG}")
        return 2

    # ====================================================================
    # STEP-1: 生成 4 个真正不同的素材视频 (真实视频切片+不同色调, 不再用 lavfi)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [STEP-1] 生成多素材 (真实视频切片+不同色调, 不再用 lavfi testsrc)")
    print("=" * 78)
    # 清理旧的 lavfi 测试图案素材 (src_testsrc/smptebars/rgbtestsrc/yuvtestsrc)
    for _old in ["src_testsrc.mp4", "src_smptebars.mp4", "src_rgbtestsrc.mp4", "src_yuvtestsrc.mp4"]:
        _old_path = Path(materials_abs) / _old
        if _old_path.exists():
            try:
                _old_path.unlink()
                print(f"    [CLEAN] 删除旧 lavfi 素材: {_old}")
            except Exception:
                pass
    materials = generate_materials(materials_abs, ref_video_abs=ref_abs)
    if len(materials) < 2:
        print(f"  [FATAL] 生成的素材不足 2 个, 实际 {len(materials)} 个")
        return 2
    print(f"\n  --> 生成 {len(materials)} 个素材:")
    for path, desc in materials:
        meta = run_ffprobe(path)
        dur = "?"
        if "format" in meta:
            dur = meta["format"].get("duration", "?")
        print(f"      - {Path(path).name:24s} dur={dur}s  ({desc})")

    # 验证素材两两不同 (md5 指纹)
    print("\n  [STEP-1b] 验证素材内容两两不同 (md5 指纹)")
    fingerprints = {}
    for path, _ in materials:
        with open(path, "rb") as f:
            head = f.read(65536)
        fp = hashlib.md5(head).hexdigest()
        fingerprints[path] = fp
        print(f"      {Path(path).name:24s} md5_head={fp}")
    unique_fps = set(fingerprints.values())
    materials_unique = len(unique_fps) == len(materials)
    _print_check("素材 md5 指纹两两不同", materials_unique,
                 f"unique={len(unique_fps)}/{len(materials)}")
    if not materials_unique:
        print("  [FATAL] 素材内容重复, 不满足'真正不同'要求")
        return 2

    # ====================================================================
    # STEP-2: 构造管线配置 + 运行七阶段
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [STEP-2] 运行 UnifiedPipeline 七阶段 (三项能力同时生效)")
    print("=" * 78)
    from pipeline.unified_pipeline import (
        UnifiedPipeline, PipelineConfig, PipelineResult,
    )

    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_abs,
        materials_dir=materials_abs,
        output_dir=out_abs,
        project_name="p2_comprehensive_e2e",
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
    print(f"  [INIT] reference_video = {Path(ref_abs).name}")
    print(f"  [INIT] materials_dir   = {materials_abs} ({len(materials)} files)")

    result: PipelineResult | None = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=10)

    elapsed_run_all = time.time() - t0

    # ====================================================================
    # CHECK-A: 七阶段状态汇总
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-A] 七阶段状态汇总")
    print("=" * 78)
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
    seven_stages_ok = done_count >= 7
    print(f"  --> 七阶段 DONE: {done_count}/7  {'PASS' if seven_stages_ok else 'FAIL'}")

    # ====================================================================
    # CHECK-B: VRS 真分析数据 (plan 阶段的输入)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-B] VRS 真分析数据 (plan 阶段的输入)")
    print("=" * 78)
    perceive_sr = pipeline._results.get("perceive") if hasattr(pipeline, "_results") else None
    if not perceive_sr and result and "perceive" in result.stages:
        perceive_sr = result.stages["perceive"]

    vrs_result: dict = {}
    if perceive_sr and perceive_sr.data:
        vrs_result = perceive_sr.data.get("vrs_result", {}) or {}
    if not vrs_result:
        vrs_result = getattr(pipeline, "_vrs_result", {}) or {}

    vrs_input_ok = False
    vrs_effects: list = []
    if vrs_result:
        source = vrs_result.get("source", "")
        vrs_effects = vrs_result.get("effects", []) or []
        color_palette = vrs_result.get("color_palette", {}) or {}
        rhythm = vrs_result.get("rhythm", {}) or {}
        motion = vrs_result.get("motion", {}) or {}
        style_tags = vrs_result.get("style_tags", []) or []
        confidence = vrs_result.get("confidence", 0) or 0
        print(f"    vrs.source              : {source!r}")
        print(f"    vrs.confidence          : {confidence}")
        print(f"    vrs.effects             : {[e.get('effect_name') for e in vrs_effects]}")
        print(f"    vrs.color_palette.temp  : {color_palette.get('temperature')}")
        print(f"    vrs.color_palette.sat   : {color_palette.get('saturation')}")
        print(f"    vrs.rhythm.tempo        : {rhythm.get('tempo')}")
        print(f"    vrs.motion.intensity    : {motion.get('intensity')}")
        print(f"    vrs.style_tags          : {style_tags}")
        vrs_input_ok = (
            source == "real_opencv_analysis"
            and len(vrs_effects) > 0
            and confidence > 0.5
        )
        _print_check("VRS effects 非空", len(vrs_effects) > 0, f"len={len(vrs_effects)}")
        _print_check("VRS confidence > 0.5", confidence > 0.5, f"confidence={confidence}")
    else:
        print(f"    [FAIL] 未取到 vrs_result")

    # ====================================================================
    # CHECK-C: 能力1 plan 消费 VRS (P2-1+P2-3 核心)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-C] 能力1: plan 消费 VRS — effect_stack 由 VRS 驱动生成")
    print("=" * 78)
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
        print(f"    effect_stack vrs_sources   : {[e.get('vrs_source') for e in effect_stack]}")

        c1 = _print_check("effect_stack 非空且 len>=2",
                          len(effect_stack) >= 2, f"len={len(effect_stack)}")
        c2 = _print_check("effect_stack_source ∈ {vrs_driven, vrs_injected}",
                          effect_stack_source in ("vrs_driven", "vrs_injected"),
                          f"source={effect_stack_source!r}")
        c3 = _print_check("vrs_to_effects_mapping 非空",
                          len(vrs_to_effects_mapping) > 0,
                          f"len={len(vrs_to_effects_mapping)}")
        has_vrs_source = any(e.get("vrs_source") for e in effect_stack)
        c4 = _print_check("effect_stack 含 vrs_source 标注 (证明来自 VRS 映射)",
                          has_vrs_source,
                          f"vrs_sources={[e.get('vrs_source') for e in effect_stack]}")
        plan_ok = c1 and c2 and c3 and c4
    else:
        print(f"    [FAIL] plan 阶段结果缺失或无 data")

    # ====================================================================
    # CHECK-D: 能力3 VRS effects 与 effect_stack 一致性 (P2-3)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-D] 能力3: VRS effects ↔ effect_stack 一致性")
    print("=" * 78)
    consistency_ok = False
    consistency_rows: list = []
    if vrs_effects and effect_stack:
        mapping_values = {str(m.get("vrs_value", "")) for m in vrs_to_effects_mapping}
        print(f"    {'VRS effect_name':<30}{'effect_stack 命中':<25}{'mapping 命中':<15}")
        print(f"    {'-'*30}{'-'*25}{'-'*15}")
        any_hit = False
        for ve in vrs_effects:
            ve_name = ve.get("effect_name", "")
            stack_hit = next(
                (e for e in effect_stack if e.get("vrs_source") == ve_name),
                None,
            )
            stack_hit_name = stack_hit.get("name") if stack_hit else "<MISS>"
            map_hit = ve_name in mapping_values
            stack_ok = stack_hit is not None
            print(f"    {ve_name:<30}{stack_hit_name:<25}{'YES' if map_hit else 'NO':<15}")
            consistency_rows.append({
                "vrs_effect_name": ve_name,
                "effect_stack_name": stack_hit_name,
                "stack_hit": stack_ok,
                "mapping_hit": map_hit,
            })
            if stack_ok:
                any_hit = True
        # 至少 1 个 VRS 检测的效果在 effect_stack 中有对应条目
        consistency_ok = any_hit
        _print_check("至少 1 个 VRS 效果在 effect_stack 中有对应条目 (vrs_source 匹配)",
                     consistency_ok, f"hit_count={sum(1 for r in consistency_rows if r['stack_hit'])}")
    else:
        print(f"    [FAIL] vrs_effects 或 effect_stack 为空，无法对照")

    # ====================================================================
    # CHECK-E: 能力2 多素材混剪 (P2-2 核心)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-E] 能力2: 多素材混剪 — execute.source_count>=2, mix_mode=multi_source")
    print("=" * 78)
    exec_sr = pipeline._results.get("execute") if hasattr(pipeline, "_results") else None
    if not exec_sr and result and "execute" in result.stages:
        exec_sr = result.stages["execute"]

    exec_ok = False
    exec_output = ""
    exec_data: dict = {}
    source_count = 0
    mix_mode = ""
    source_files: list = []
    if exec_sr and exec_sr.data:
        exec_data = exec_sr.data or {}
        exec_output = exec_data.get("output_path") or exec_data.get("project_path", "")
        exec_mode = exec_data.get("execution_mode", "")
        source_count = int(exec_data.get("source_count", 0) or 0)
        mix_mode = exec_data.get("mix_mode", "") or ""
        source_files = exec_data.get("source_files", []) or []
        layers_created = exec_data.get("layers_created", 0)
        effects_applied = exec_data.get("effects_applied", 0)
        print(f"    execution_mode      : {exec_mode!r}")
        print(f"    output_path         : {exec_output}")
        print(f"    source_count        : {source_count}")
        print(f"    mix_mode            : {mix_mode!r}")
        print(f"    source_files        : {[Path(s).name for s in source_files]}")
        print(f"    layers_created      : {layers_created}")
        print(f"    effects_applied     : {effects_applied}")
        print(f"    total_duration      : {exec_data.get('total_duration', '?')}s")
        print(f"    file_size_mb        : {exec_data.get('file_size_mb', '?')}")

        no_error = "error_code" not in exec_data
        output_exists = bool(exec_output) and Path(exec_output).exists()
        output_size_ok = output_exists and Path(exec_output).stat().st_size > 50 * 1024
        c1 = _print_check("execution_mode 是 real_mix",
                          "real_mix" in exec_mode, f"mode={exec_mode!r}")
        c2 = _print_check("无 error_code", no_error,
                          f"error_code={exec_data.get('error_code', '<none>')}")
        c3 = _print_check("输出文件存在", output_exists, f"path={exec_output}")
        c4 = _print_check("输出文件 size > 50KB", output_size_ok,
                          f"size={Path(exec_output).stat().st_size if output_exists else 0} bytes")
        c5 = _print_check("source_count >= 2",
                          source_count >= 2, f"source_count={source_count}")
        c6 = _print_check("mix_mode == 'multi_source'",
                          mix_mode == "multi_source", f"mix_mode={mix_mode!r}")
        c7 = _print_check("source_files 含 >=2 个不同文件",
                          len(set(source_files)) >= 2,
                          f"unique={len(set(source_files))}")
        exec_ok = c1 and c2 and c3 and c4 and c5 and c6 and c7
    else:
        print(f"    [FAIL] execute 阶段结果缺失或无 data")

    # ====================================================================
    # CHECK-F: 能力4 七阶段全 DONE (已在 CHECK-A 汇总)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-F] 能力4: 七阶段全 DONE")
    print("=" * 78)
    _print_check("七阶段全部 DONE (7/7)", seven_stages_ok,
                 f"done={done_count}/7")
    print(f"    各阶段耗时:")
    for s in STAGE_ORDER:
        print(f"      {s:10s}: {stage_durations.get(s, 0.0):.2f}s  [{status_by_stage.get(s, 'MISSING')}]")
    print(f"    总耗时 (run_all): {elapsed_run_all:.2f}s")

    # ====================================================================
    # CHECK-G: 能力5 物理输出视频 ffprobe 元数据验证
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-G] 能力5: 物理输出视频 ffprobe 元数据")
    print("=" * 78)
    ffprobe_ok = False
    ffprobe_meta: dict = {}
    final_duration = 0.0
    final_size_bytes = 0
    if exec_output and Path(exec_output).exists():
        ffprobe_meta = run_ffprobe(exec_output)
        if "error" in ffprobe_meta:
            print(f"    [FAIL] ffprobe error: {ffprobe_meta.get('error')}")
        else:
            streams = ffprobe_meta.get("streams", [])
            fmt = ffprobe_meta.get("format", {})
            vs = next((s for s in streams if s.get("codec_type") == "video"), {})
            final_duration = float(fmt.get("duration", 0) or 0)
            final_size_bytes = int(fmt.get("size", 0) or 0)
            print(f"    file                : {exec_output}")
            print(f"    size                : {final_size_bytes} bytes ({final_size_bytes/1024/1024:.2f} MB)")
            print(f"    duration            : {final_duration:.2f} s")
            print(f"    bit_rate            : {fmt.get('bit_rate', '<unknown>')}")
            print(f"    video codec         : {vs.get('codec_name', '<unknown>')}")
            print(f"    width x height      : {vs.get('width', '?')}x{vs.get('height', '?')}")
            print(f"    r_frame_rate        : {vs.get('r_frame_rate', '<unknown>')}")
            print(f"    nb_frames           : {vs.get('nb_frames', '<unknown>')}")
            has_video_stream = vs.get("codec_type") == "video"
            ffprobe_ok = (
                vs.get("codec_name") == "h264"
                and final_duration > 5.0
                and has_video_stream
                and final_size_bytes > 50 * 1024
            )
            _print_check("ffprobe: h264 + duration>5s + 视频流存在 + size>50KB",
                         ffprobe_ok,
                         f"codec={vs.get('codec_name')} dur={final_duration:.2f}s size={final_size_bytes}B")
    else:
        print(f"    [FAIL] exec_output 不存在: {exec_output}")

    # ====================================================================
    # CHECK-H: 能力6 多轮自动优化不回归 (P1-3 防回归)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-H] 能力6: 多轮自动优化不回归 (verify.optimization_history)")
    print("=" * 78)
    verify_sr = pipeline._results.get("verify") if hasattr(pipeline, "_results") else None
    if not verify_sr and result and "verify" in result.stages:
        verify_sr = result.stages["verify"]

    verify_ok = False
    quality_score = 0.0
    optimization_history: list = []
    optimization_applied = False
    if verify_sr and verify_sr.data:
        verify_data = verify_sr.data or {}
        raw_score = verify_data.get("score", verify_data.get("quality_score", 0))
        try:
            quality_score = float(raw_score) if raw_score is not None else 0.0
        except (TypeError, ValueError):
            quality_score = 0.0
        optimization_history = verify_data.get("optimization_history", []) or []
        optimization_applied = bool(verify_data.get("optimization_applied", False))
        print(f"    score               : {quality_score}")
        print(f"    verified            : {verify_data.get('verified')}")
        print(f"    optimization_applied: {optimization_applied}")
        print(f"    optimization_history.len : {len(optimization_history)}")
        print(f"    final_score         : {verify_data.get('final_score')}")
        print(f"    optimization_reasoning : {verify_data.get('optimization_reasoning')}")
        # P1-3 防回归: verify 必须返回 optimization_history 字段 (无论是否触发优化)
        has_opt_field = "optimization_history" in verify_data
        score_ok = quality_score > MIN_VERIFY_SCORE
        _print_check("verify 含 optimization_history 字段 (P1-3 防回归)",
                     has_opt_field, f"field_present={has_opt_field}")
        _print_check(f"verify score > {MIN_VERIFY_SCORE}",
                     score_ok, f"score={quality_score}")
        verify_ok = has_opt_field and score_ok
    else:
        print(f"    [FAIL] verify 阶段结果缺失或无 data")

    # ====================================================================
    # CHECK-I: 多素材内容差异 (输出 = 多段拼接, 非单段)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-I] 多素材内容差异 (输出 = 多段拼接, 非单段)")
    print("=" * 78)
    layers = int(exec_data.get("layers_created", 0) or 0)
    multi_segment_ok = layers >= 2 and final_duration > 3.0
    print(f"    layers_created (concat 段数) : {layers}")
    print(f"    final_duration              : {final_duration:.2f}s")
    print(f"    source_count                : {source_count}")
    print(f"    source_files (unique)       : {len(set(source_files))}")
    _print_check("concat 段数 >=2 AND source_count >=2 (多素材拼接)",
                 multi_segment_ok and source_count >= 2,
                 f"layers={layers} sources={source_count}")
    diff_sources_ok = len(set(source_files)) >= 2
    _print_check("source_files 含 >=2 个不同文件路径 (非复制)",
                 diff_sources_ok,
                 f"unique_paths={len(set(source_files))}")

    # ====================================================================
    # Artifact 落盘
    # ====================================================================
    artifact_path = Path(out_abs) / f"p2_comprehensive_artifact_{run_id}.json"
    try:
        artifact = {
            "run_id": run_id,
            "materials": [
                {"path": p, "desc": d, "md5_head": fingerprints.get(p, "")}
                for p, d in materials
            ],
            "reference_video": ref_abs,
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
            "consistency_rows": consistency_rows,
            "exec_data": exec_data,
            "verify_quality_score": quality_score,
            "verify_optimization_history": optimization_history,
            "verify_optimization_applied": optimization_applied,
            "ffprobe_meta": ffprobe_meta,
            "stage_status": status_by_stage,
            "stage_durations": stage_durations,
            "checks": {
                "A.seven_stages_done": seven_stages_ok,
                "B.vrs_real_analysis": vrs_input_ok,
                "C.plan_consume_vrs": plan_ok,
                "D.vrs_effects_consistency": consistency_ok,
                "E.multi_source_mix": exec_ok,
                "F.ffprobe_valid": ffprobe_ok,
                "G.verify_optimization_no_regression": verify_ok,
                "H.multi_segment": multi_segment_ok,
                "I.diff_sources": diff_sources_ok,
            },
            "elapsed_run_all_sec": round(elapsed_run_all, 2),
        }
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\n  [ARTIFACT] {artifact_path}")
    except Exception as e:
        print(f"\n  [ARTIFACT ERROR] {e}")

    # ====================================================================
    # 最终结论
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [FINAL] P2 综合端到端验证 — 三项能力同时生效且无回归")
    print("=" * 78)
    checks = {
        "A.七阶段全DONE (7/7)             ": seven_stages_ok,
        "B.VRS真分析数据可用              ": vrs_input_ok,
        "C.能力1 plan消费VRS (P2-1+P2-3)  ": plan_ok,
        "D.能力3 VRS effects↔stack一致    ": consistency_ok,
        "E.能力2 多素材混剪 (P2-2)        ": exec_ok,
        "F.能力5 ffprobe元数据有效        ": ffprobe_ok,
        "G.能力6 多轮优化不回归 (P1-3)    ": verify_ok,
        "H.多段拼接非单段                 ": multi_segment_ok,
        "I.真正不同素材(非复制)          ": diff_sources_ok,
    }
    for k, v in checks.items():
        print(f"  [{ 'PASS' if v else 'FAIL' }] {k}")
    all_pass = all(checks.values())
    print(f"\n  --> 总结论: {'PASS ✅' if all_pass else 'FAIL ❌'}")
    print(f"  --> 耗时: {elapsed_run_all:.2f}s")
    print(f"  --> 输出视频: {exec_output}")
    print(f"  --> source_count={source_count} mix_mode={mix_mode!r}")
    print(f"  --> effect_stack_source={effect_stack_source!r} vrs_mappings={len(vrs_to_effects_mapping)}")
    print(f"  --> verify.score={quality_score} optimization_history.len={len(optimization_history)}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
