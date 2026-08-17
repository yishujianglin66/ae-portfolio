#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P1 VRS 真分析验证脚本
=====================

验证目标：
1. VRSOrchestrator.analyze 真实执行 OpenCV/ffprobe 分析（不降级到 basic analysis）
2. 输出结构化 JSON，包含 color_palette/rhythm/motion/transitions/style_tags/confidence
3. 每个字段都有真实数值（非 None/0/空）
4. 与 P0 basic analysis 对比，证明是真分析

用法：
    C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe \\
        scripts/test_p1_vrs_real.py

    # 指定视频
    C:\\Users\\Administrator\\AppData\\Local\\Programs\\Python\\Python312\\python.exe \\
        scripts/test_p1_vrs_real.py --video path/to/video.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

# 项目根目录加入 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PROJECT_ROOT / "vrs") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "vrs"))


PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"

# 默认测试视频候选
DEFAULT_VIDEO_CANDIDATES = [
    _PROJECT_ROOT / "output" / "p3_e2e_run" / "p3_e2e_cyber_glitch.mp4",
    _PROJECT_ROOT / "output" / "p1_execute_mix" / "p1_mix_cyber_glitch.mp4",
    _PROJECT_ROOT / "output" / "p3_e2e_run" / "p3_e2e_cyber_glitch_final.mp4",
]

OUTPUT_DIR = _PROJECT_ROOT / "output" / "p1_vrs_test"


def log(msg: str, level: str = "INFO") -> None:
    print(f"[{level}] {msg}", flush=True)


def verify_video_readable(video_path: Path) -> dict:
    """用 ffprobe 验证视频可读，返回基本信息。"""
    log(f"ffprobe 验证视频可读: {video_path}")
    if not video_path.exists():
        log(f"视频不存在: {video_path}", "ERROR")
        sys.exit(1)

    cmd = [
        FFPROBE, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(video_path),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            log(f"ffprobe 失败 (rc={r.returncode}): {r.stderr}", "ERROR")
            sys.exit(1)
        info = json.loads(r.stdout)
        fmt = info.get("format", {})
        duration = float(fmt.get("duration", 0))
        size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
        vstream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
        basic = {
            "path": str(video_path),
            "size_mb": round(size_mb, 2),
            "duration_sec": round(duration, 3),
            "width": vstream.get("width", 0),
            "height": vstream.get("height", 0),
            "codec": vstream.get("codec_name", ""),
            "fps_raw": vstream.get("r_frame_rate", ""),
        }
        log(f"  → {basic['width']}x{basic['height']} {basic['codec']} "
            f"{basic['duration_sec']}s {basic['size_mb']}MB fps={basic['fps_raw']}")
        return basic
    except Exception as e:
        log(f"ffprobe 异常: {e}", "ERROR")
        sys.exit(1)


def get_p0_basic_analysis_sample() -> dict:
    """返回 P0 basic analysis 的典型输出结构（作为对比基准）。

    来源: data/pipeline_runs/run_20260730_173045_1d8998/analyze.json 的 vrs_analysis 字段。
    """
    return {
        "source": "basic_analysis",
        "video_path": "<reference_video>",
        "format": {"duration": "15.100000"},
        "streams": [
            {"codec_name": "h264", "width": 852, "height": 480, "r_frame_rate": "30/1"},
            {"codec_name": "aac", "r_frame_rate": "0/0"},
        ],
        "effects_detected": [],
        "transitions_detected": [],
        "color_grade_detected": "",
        "vrs_segments": [{
            "index": 0, "start_time": 0, "end_time": 10.0, "duration": 10.0,
            "mood": "neutral", "camera_motion": "static", "effects": [],
            "confidence": 0.0,
        }],
    }


async def run_vrs_analyze(video_path: Path) -> dict:
    """调用 VRSOrchestrator.analyze 真实执行。"""
    log("=" * 70)
    log("步骤 1: 调用 VRSOrchestrator.analyze (真 OpenCV/ffprobe 分析)")
    log("=" * 70)

    from vrs.vrs_orchestrator import VRSOrchestrator
    vrs = VRSOrchestrator()

    start = time.time()
    result = await vrs.analyze(str(video_path), options={"detail_level": "standard"})
    elapsed = time.time() - start

    log(f"VRSOrchestrator.analyze 完成，耗时 {elapsed:.2f}s")
    log(f"  success={result.get('success')}")
    log(f"  source={result.get('source')}")
    log(f"  confidence={result.get('confidence')}")
    log(f"  style_tags={result.get('style_tags', [])}")
    return result


def validate_result(result: dict) -> dict:
    """验证结果字段完整性，返回校验报告。"""
    log("=" * 70)
    log("步骤 2: 验证输出字段完整性")
    log("=" * 70)

    checks = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        checks.append({"name": name, "ok": ok, "detail": detail})
        log(f"  [{status}] {name}: {detail}")

    # 顶层字段
    check("source == real_opencv_analysis",
          result.get("source") == "real_opencv_analysis",
          f"source={result.get('source')}")
    check("success == True", result.get("success") is True,
          f"success={result.get('success')}")

    # basic_info
    bi = result.get("basic_info", {})
    check("basic_info.width > 0", bi.get("width", 0) > 0, f"width={bi.get('width')}")
    check("basic_info.height > 0", bi.get("height", 0) > 0, f"height={bi.get('height')}")
    check("basic_info.fps > 0", bi.get("fps", 0) > 0, f"fps={bi.get('fps')}")
    check("basic_info.duration > 0", bi.get("duration", 0) > 0, f"duration={bi.get('duration')}")

    # color_palette
    cp = result.get("color_palette", {})
    check("color_palette 非空", bool(cp), f"keys={list(cp.keys())}")
    if cp:
        check("avg_brightness in [0,1]",
              0 <= cp.get("avg_brightness", -1) <= 1,
              f"avg_brightness={cp.get('avg_brightness')}")
        check("contrast in [0,1]",
              0 <= cp.get("contrast", -1) <= 1,
              f"contrast={cp.get('contrast')}")
        check("saturation in [0,1]",
              0 <= cp.get("saturation", -1) <= 1,
              f"saturation={cp.get('saturation')}")
        check("hue_distribution 长度=12",
              len(cp.get("hue_distribution", [])) == 12,
              f"len={len(cp.get('hue_distribution', []))}")
        check("dominant_colors 非空",
              len(cp.get("dominant_colors", [])) > 0,
              f"count={len(cp.get('dominant_colors', []))}")
        check("temperature in {warm,cool,neutral}",
              cp.get("temperature") in ("warm", "cool", "neutral"),
              f"temperature={cp.get('temperature')}")

    # rhythm
    rh = result.get("rhythm", {})
    check("rhythm 非空", bool(rh), f"keys={list(rh.keys())}")
    if rh:
        check("rhythm.shot_count >= 0",
              rh.get("shot_count", -1) >= 0,
              f"shot_count={rh.get('shot_count')}")
        check("rhythm.avg_shot_duration > 0",
              rh.get("avg_shot_duration", 0) > 0,
              f"avg_shot_duration={rh.get('avg_shot_duration')}")
        check("rhythm.tempo in {fast,medium,slow,unknown}",
              rh.get("tempo") in ("fast", "medium", "slow", "unknown"),
              f"tempo={rh.get('tempo')}")
        check("rhythm.frame_diff_mean >= 0",
              rh.get("frame_diff_mean", -1) >= 0,
              f"frame_diff_mean={rh.get('frame_diff_mean')}")

    # motion
    mo = result.get("motion", {})
    check("motion 非空", bool(mo), f"keys={list(mo.keys())}")
    if mo:
        check("motion.intensity in [0,1]",
              0 <= mo.get("intensity", -1) <= 1,
              f"intensity={mo.get('intensity')}")
        check("motion.direction_distribution 长度=8",
              len(mo.get("direction_distribution", [])) == 8,
              f"len={len(mo.get('direction_distribution', []))}")
        check("motion.dominant_direction 非空",
              bool(mo.get("dominant_direction")),
              f"dominant_direction={mo.get('dominant_direction')}")

    # transitions
    tr = result.get("transitions", [])
    check("transitions 是 list", isinstance(tr, list), f"type={type(tr).__name__}")
    if tr:
        sample = tr[0]
        check("transition.time 是数字",
              isinstance(sample.get("time"), (int, float)),
              f"time={sample.get('time')}")
        check("transition.type 非空",
              bool(sample.get("type")),
              f"type={sample.get('type')}")
        check("transition.confidence in [0,1]",
              0 <= sample.get("confidence", -1) <= 1,
              f"confidence={sample.get('confidence')}")

    # 兼容字段
    check("effects 是 list", isinstance(result.get("effects"), list),
          f"len={len(result.get('effects', []))}")
    check("color_grade 是非空字符串",
          isinstance(result.get("color_grade"), str) and bool(result.get("color_grade")),
          f"color_grade={result.get('color_grade')}")
    style = result.get("style", {})
    check("style.name 非空",
          bool(style.get("name")),
          f"style.name={style.get('name')}")
    check("style_tags 是非空 list",
          isinstance(result.get("style_tags"), list) and len(result.get("style_tags", [])) > 0,
          f"style_tags={result.get('style_tags')}")
    check("confidence > 0",
          result.get("confidence", 0) > 0,
          f"confidence={result.get('confidence')}")

    passed = sum(1 for c in checks if c["ok"])
    total = len(checks)
    log(f"\n字段校验汇总: {passed}/{total} PASS")
    return {"passed": passed, "total": total, "checks": checks, "all_ok": passed == total}


def compare_with_p0(result: dict) -> dict:
    """与 P0 basic analysis 对比。"""
    log("=" * 70)
    log("步骤 3: 与 P0 basic analysis 对比")
    log("=" * 70)

    p0 = get_p0_basic_analysis_sample()

    comparison = {
        "p0_basic_analysis": {
            "source": p0["source"],
            "has_color_palette": False,
            "has_rhythm": False,
            "has_motion": False,
            "has_transitions": False,
            "effects_count": 0,
            "color_grade": "",
            "confidence": 0.0,
        },
        "p1_real_analysis": {
            "source": result.get("source"),
            "has_color_palette": bool(result.get("color_palette")),
            "has_rhythm": bool(result.get("rhythm")),
            "has_motion": bool(result.get("motion")),
            "has_transitions": isinstance(result.get("transitions"), list)
                              and len(result.get("transitions", [])) > 0,
            "effects_count": len(result.get("effects", [])),
            "color_grade": result.get("color_grade", ""),
            "confidence": result.get("confidence", 0.0),
            "style_tags_count": len(result.get("style_tags", [])),
        },
    }

    log("对比表:")
    log(f"  {'指标':<25} {'P0 basic':<20} {'P1 real':<25}")
    log(f"  {'-'*70}")
    log(f"  {'source':<25} {p0['source']:<20} {result.get('source', ''):<25}")
    log(f"  {'has_color_palette':<25} {'False':<20} {comparison['p1_real_analysis']['has_color_palette']:<25}")
    log(f"  {'has_rhythm':<25} {'False':<20} {comparison['p1_real_analysis']['has_rhythm']:<25}")
    log(f"  {'has_motion':<25} {'False':<20} {comparison['p1_real_analysis']['has_motion']:<25}")
    log(f"  {'has_transitions':<25} {'False':<20} {comparison['p1_real_analysis']['has_transitions']:<25}")
    log(f"  {'effects_count':<25} {'0':<20} {comparison['p1_real_analysis']['effects_count']:<25}")
    log(f"  {'color_grade':<25} {'(empty)':<20} {comparison['p1_real_analysis']['color_grade']:<25}")
    log(f"  {'confidence':<25} {'0.0':<20} {comparison['p1_real_analysis']['confidence']:<25}")

    p1 = comparison["p1_real_analysis"]
    improvement = (
        p1["has_color_palette"] and p1["has_rhythm"] and p1["has_motion"]
        and p1["effects_count"] > 0 and p1["confidence"] > 0
    )
    log(f"\n对比结论: {'PASS - P1 真分析显著优于 P0 basic' if improvement else 'FAIL - 未达预期'}")
    comparison["improvement"] = improvement
    return comparison


async def main_async(video_path: Path) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 0. ffprobe 验证视频可读
    log("=" * 70)
    log("步骤 0: ffprobe 验证输入视频可读")
    log("=" * 70)
    basic = verify_video_readable(video_path)

    # 1. 调用 VRSOrchestrator.analyze
    result = await run_vrs_analyze(video_path)

    # 2. 字段校验
    validation = validate_result(result)

    # 3. 与 P0 对比
    comparison = compare_with_p0(result)

    # 4. 保存完整 JSON
    log("=" * 70)
    log("步骤 4: 保存完整 JSON 输出")
    log("=" * 70)
    out_json = OUTPUT_DIR / "vrs_real_analysis.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    log(f"已保存: {out_json}")

    # 5. 保存校验报告
    report = {
        "video": basic,
        "validation": validation,
        "comparison": comparison,
        "output_json": str(out_json),
    }
    report_path = OUTPUT_DIR / "vrs_validation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    log(f"已保存: {report_path}")

    # 6. 最终结论
    log("=" * 70)
    log("最终结论")
    log("=" * 70)
    overall_pass = (
        validation["all_ok"]
        and comparison["improvement"]
        and result.get("source") == "real_opencv_analysis"
        and result.get("success") is True
    )
    log(f"  字段校验: {validation['passed']}/{validation['total']} PASS")
    log(f"  P0对比改进: {'是' if comparison['improvement'] else '否'}")
    log(f"  整体结论: {'PASS' if overall_pass else 'FAIL'}")

    print("\n" + "=" * 70)
    print("VRS 真分析输出 JSON（格式化展示）")
    print("=" * 70)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    return 0 if overall_pass else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="P1 VRS 真分析验证脚本")
    parser.add_argument("--video", type=str, default="", help="测试视频路径（默认自动选择）")
    args = parser.parse_args()

    if args.video:
        video_path = Path(args.video)
    else:
        video_path = None
        for cand in DEFAULT_VIDEO_CANDIDATES:
            if cand.exists():
                video_path = cand
                break
        if video_path is None:
            log(f"未找到默认测试视频，候选: {[str(c) for c in DEFAULT_VIDEO_CANDIDATES]}", "ERROR")
            sys.exit(1)

    log(f"测试视频: {video_path}")
    rc = asyncio.run(main_async(video_path))
    sys.exit(rc)


if __name__ == "__main__":
    main()
