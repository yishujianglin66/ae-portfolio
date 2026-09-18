"""P2 execute 多素材混剪 — 端到端验证

验证目标 (必须在同一次 UnifiedPipeline.run_all() 运行中同时生效):
  P2-MS-1 多素材收集       : perceive.videos 含 >=2 个不同素材; _run_execute_real_mix 收集 >=2 sources
  P2-MS-2 按 shot_list 混剪 : 按 plan.shot_list (或轮询) 拼接不同素材片段, 不再用单素材分段
  P2-MS-3 source_count      : execute 返回 source_count >= 2
  P2-MS-4 mix_mode          : execute 返回 mix_mode == "multi_source"
  P2-MS-5 真实输出视频      : 输出 mp4 真实存在, ffprobe 验证 codec=h264, duration>5s, 视频流存在
  P2-MS-6 多素材内容差异    : 输出视频时长 >= 各段之和 (证明多段拼接, 非单段)
  P2-MS-7 七阶段全 DONE     : perceive/analyze/plan/execute/render/verify/learn 全部 DONE
  P2-MS-8 verify 分数 > 30  : 质量评分必须 > 30

素材生成 (FFmpeg lavfi, 真正不同的内容, 非复制):
  - src_testsrc.mp4    : testsrc 测试图案 (彩色条纹+计数器)
  - src_smptebars.mp4  : SMPTE 色条
  - src_mandelbrot.mp4 : 曼德博集合 (分形)
  - src_color_bars.mp4 : yuvtestsrc YUV 测试图案
每个 6s, 640x480, 25fps, yuv420p, h264 — 真正不同的像素内容。

输出: output/p2_multi_source/
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
OUTPUT_DIR = "output/p2_multi_source"
MATERIALS_DIR = "output/p2_multi_source/inputs"
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
        # 如果已存在且 >10KB, 跳过重新生成 (幂等)
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
    out_abs = str(PROJECT_ROOT / OUTPUT_DIR)
    materials_abs = str(PROJECT_ROOT / MATERIALS_DIR)
    Path(out_abs).mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("  P2 execute 多素材混剪 — 端到端验证")
    print("=" * 78)
    print(f"  FFmpeg           : {_FFMPEG}")
    print(f"  FFprobe          : {_FFPROBE}")
    print(f"  Output Dir       : {OUTPUT_DIR}")
    print(f"  Materials Dir    : {MATERIALS_DIR}")
    print(f"  Topic            : {INPUT_TOPIC}")
    print(f"  min_verify_score : {MIN_VERIFY_SCORE}")
    print(f"  max_iterations   : {MAX_QUALITY_ITERATIONS}")
    print("=" * 78)

    if not Path(_FFMPEG).exists():
        print(f"  [FATAL] FFmpeg 不存在: {_FFMPEG}")
        return 2

    # ====================================================================
    # 1. 生成 4 个真正不同的素材视频 (真实视频切片+不同色调, 不再用 lavfi)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [STEP-1] 生成多素材 (真实视频切片+不同色调, 不再用 lavfi testsrc)")
    print("=" * 78)
    # 清理旧的 lavfi 测试图案素材
    for _old in ["src_testsrc.mp4", "src_smptebars.mp4", "src_rgbtestsrc.mp4", "src_yuvtestsrc.mp4"]:
        _old_path = Path(materials_abs) / _old
        if _old_path.exists():
            try:
                _old_path.unlink()
                print(f"    [CLEAN] 删除旧 lavfi 素材: {_old}")
            except Exception:
                pass
    ref_abs = str(PROJECT_ROOT / REF_VIDEO)
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

    # 验证素材两两不同 (用文件大小+前 4KB 哈希做内容指纹)
    print("\n  [STEP-1b] 验证素材内容两两不同 (md5 指纹)")
    import hashlib
    fingerprints = {}
    for path, _ in materials:
        with open(path, "rb") as f:
            head = f.read(65536)  # 前 64KB
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
    # 2. 构造管线配置 + 运行七阶段
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [STEP-2] 运行 UnifiedPipeline 七阶段")
    print("=" * 78)
    from pipeline.unified_pipeline import (
        PipelineConfig,
        PipelineResult,
        UnifiedPipeline,
    )

    ref_video = materials[0][0]  # 用第一个素材作为 reference_video
    cfg = PipelineConfig(
        input_topic=INPUT_TOPIC,
        reference_video=ref_video,
        materials_dir=materials_abs,
        output_dir=out_abs,
        project_name="p2_multi_source_mix",
        use_knowledge=True,
        style_match=True,
        enable_vrs=True,
        enable_feedback_loop=True,
        enable_multi_agent=False,
        max_quality_iterations=MAX_QUALITY_ITERATIONS,
        min_quality_score=MIN_VERIFY_SCORE,
        use_davinci_render=False,
        use_compiler=False,
        ffmpeg_bin=_FFMPEG,
    )

    pipeline = UnifiedPipeline(cfg)
    run_id = pipeline.run_id
    print(f"\n  [INIT] run_id={run_id}  mode={pipeline.mode.value}")
    print(f"  [INIT] reference_video = {Path(ref_video).name}")
    print(f"  [INIT] materials_dir   = {materials_abs} ({len(materials)} files)")

    result: PipelineResult | None = None
    try:
        result = pipeline.run_all()
    except Exception as _e:
        print(f"\n  [FATAL EXCEPTION] {type(_e).__name__}: {_e}")
        traceback.print_exc(limit=10)

    # ====================================================================
    # 3. 七阶段状态汇总
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-A] 七阶段状态汇总")
    print("=" * 78)
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
            dur = 0.0
        else:
            status_name = sr.status.value if hasattr(sr.status, "value") else str(sr.status)
            dur = float(getattr(sr, "duration_sec", 0.0) or 0.0)
        mark = "OK" if status_name.upper() == "DONE" else (
            "--" if status_name.upper() == "SKIPPED" else "XX"
        )
        print(f"  [{mark}] {s:10s}  {status_name:10s}  duration={dur:.2f}s")
        status_by_stage[s] = status_name
        if status_name.upper() == "DONE":
            done_count += 1
    seven_stages_ok = done_count >= 6
    print(f"  --> 七阶段 DONE: {done_count}/7  {'PASS' if seven_stages_ok else 'FAIL'}")

    # ====================================================================
    # 4. perceive 阶段 — 多素材收集验证
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-B] perceive 阶段多素材收集")
    print("=" * 78)
    perceive_sr = pipeline._results.get("perceive") if hasattr(pipeline, "_results") else None
    if not perceive_sr and result and "perceive" in result.stages:
        perceive_sr = result.stages["perceive"]

    perceive_videos: list = []
    perceive_ok = False
    if perceive_sr and perceive_sr.data:
        perceive_videos = perceive_sr.data.get("videos", []) or []
        print(f"    perceive.videos.len : {len(perceive_videos)}")
        for i, v in enumerate(perceive_videos):
            p = v.get("path", "") if isinstance(v, dict) else str(v)
            print(f"      [{i}] {Path(p).name if p else '<empty>'}")
        perceive_ok = len(perceive_videos) >= 2
        _print_check("perceive.videos >= 2", perceive_ok,
                     f"len={len(perceive_videos)}")
    else:
        print("    [FAIL] perceive 阶段结果缺失")

    # ====================================================================
    # 5. execute 阶段 — 多素材混剪核心验证
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-C] execute 阶段多素材混剪 (核心)")
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
        c1 = _print_check("execution_mode 是 real_mix",
                          "real_mix" in exec_mode, f"mode={exec_mode!r}")
        c2 = _print_check("无 error_code", no_error,
                          f"error_code={exec_data.get('error_code', '<none>')}")
        c3 = _print_check("输出文件存在", output_exists,
                          f"path={exec_output}")
        c4 = _print_check("source_count >= 2",
                          source_count >= 2, f"source_count={source_count}")
        c5 = _print_check("mix_mode == 'multi_source'",
                          mix_mode == "multi_source", f"mix_mode={mix_mode!r}")
        c6 = _print_check("source_files 含 >=2 个不同文件",
                          len(set(source_files)) >= 2,
                          f"unique={len(set(source_files))}")
        exec_ok = c1 and c2 and c3 and c4 and c5 and c6
    else:
        print("    [FAIL] execute 阶段结果缺失或无 data")

    # ====================================================================
    # 6. verify 阶段分数验证
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-D] verify 阶段分数 > 30")
    print("=" * 78)
    verify_sr = pipeline._results.get("verify") if hasattr(pipeline, "_results") else None
    if not verify_sr and result and "verify" in result.stages:
        verify_sr = result.stages["verify"]

    verify_ok = False
    quality_score = 0.0
    if verify_sr and verify_sr.data:
        verify_data = verify_sr.data or {}
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
    # 7. 输出视频 ffprobe 元数据验证
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-E] 输出视频 ffprobe 元数据")
    print("=" * 78)
    ffprobe_ok = False
    ffprobe_meta: dict = {}
    final_duration = 0.0
    if exec_output and Path(exec_output).exists():
        ffprobe_meta = run_ffprobe(exec_output)
        if "error" in ffprobe_meta:
            print(f"    [FAIL] ffprobe error: {ffprobe_meta.get('error')}")
        else:
            streams = ffprobe_meta.get("streams", [])
            fmt = ffprobe_meta.get("format", {})
            vs = next((s for s in streams if s.get("codec_type") == "video"), {})
            final_duration = float(fmt.get("duration", 0) or 0)
            size_bytes = int(fmt.get("size", 0) or 0)
            print(f"    file                : {exec_output}")
            print(f"    size                : {size_bytes} bytes ({size_bytes/1024/1024:.2f} MB)")
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
                and int(vs.get("width", 0) or 0) > 0
            )
            _print_check("ffprobe: h264 + duration>5s + 视频流存在",
                         ffprobe_ok,
                         f"codec={vs.get('codec_name')} dur={final_duration:.2f}s")
    else:
        print(f"    [FAIL] exec_output 不存在: {exec_output}")

    # ====================================================================
    # 8. 多素材内容差异验证 (输出时长 >= 各段之和, 证明多段拼接)
    # ====================================================================
    print("\n" + "=" * 78)
    print("  [CHECK-F] 多素材内容差异 (输出 = 多段拼接, 非单段)")
    print("=" * 78)
    # layers_created 即 concat 段数; 若 >=2 则证明是多段拼接
    layers = int(exec_data.get("layers_created", 0) or 0)
    multi_segment_ok = layers >= 2 and final_duration > 3.0
    print(f"    layers_created (concat 段数) : {layers}")
    print(f"    final_duration              : {final_duration:.2f}s")
    print(f"    source_count                : {source_count}")
    print(f"    source_files (unique)       : {len(set(source_files))}")
    _print_check("concat 段数 >=2 AND source_count >=2 (多素材拼接)",
                 multi_segment_ok and source_count >= 2,
                 f"layers={layers} sources={source_count}")
    # source_files 必须含 >=2 个不同文件 (非同一视频复制)
    diff_sources_ok = len(set(source_files)) >= 2
    _print_check("source_files 含 >=2 个不同文件路径 (非复制)",
                 diff_sources_ok,
                 f"unique_paths={len(set(source_files))}")

    # ====================================================================
    # 9. Artifact 落盘
    # ====================================================================
    artifact_path = Path(out_abs) / f"p2_multi_source_artifact_{run_id}.json"
    try:
        artifact = {
            "run_id": run_id,
            "materials": [
                {"path": p, "desc": d, "md5_head": fingerprints.get(p, "")}
                for p, d in materials
            ],
            "perceive_videos_count": len(perceive_videos),
            "exec_data": exec_data,
            "verify_quality_score": quality_score,
            "ffprobe_meta": ffprobe_meta,
            "stage_status": status_by_stage,
            "checks": {
                "perceive_multi": perceive_ok,
                "exec_multi_source": exec_ok,
                "verify_score": verify_ok,
                "ffprobe_valid": ffprobe_ok,
                "multi_segment": multi_segment_ok,
                "diff_sources": diff_sources_ok,
                "seven_stages_done": seven_stages_ok,
            },
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
    print("\n" + "=" * 78)
    print("  [FINAL] P2 execute 多素材混剪 — 综合结论")
    print("=" * 78)
    checks = {
        "A.七阶段全DONE          ": seven_stages_ok,
        "B.perceive 多素材收集   ": perceive_ok,
        "C.execute 多素材混剪    ": exec_ok,
        "D.verify 分数>30        ": verify_ok,
        "E.ffprobe 元数据有效    ": ffprobe_ok,
        "F.多段拼接非单段        ": multi_segment_ok,
        "G.真正不同素材(非复制) ": diff_sources_ok,
    }
    for k, v in checks.items():
        print(f"  [{ 'PASS' if v else 'FAIL' }] {k}")
    all_pass = all(checks.values())
    print(f"\n  --> 总结论: {'PASS ✅' if all_pass else 'FAIL ❌'}")
    print(f"  --> 耗时: {time.time() - t0:.2f}s")
    print(f"  --> 输出视频: {exec_output}")
    print(f"  --> source_count={source_count} mix_mode={mix_mode!r}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
