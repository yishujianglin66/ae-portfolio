#!/usr/bin/env python3
"""
对比基准：v2 (单进程CPU) vs v3 (多进程并行 + 可选GPU)。

用法：
    python tests/benchmark_video_analyzer.py <video_path> [--workers 8]

输出：
    - 两者的总耗时 / 采样耗时 / 场景检测耗时
    - 关键特征字段一致性校验 (brightness, saturation, avg_motion 等)
    - 理论加速比
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# 避免 v2 和 v3 的相对 import 冲突，使用绝对 import 路径注入
sys.path.insert(0, str(ROOT / "scripts" / "archive"))


def _pick_fields(analysis: dict) -> dict:
    return {
        "frames": analysis.get("total_frames_sampled", 0),
        "scenes": analysis.get("scene_count", 0),
        "avg_brightness": analysis.get("color_features", {}).get("avg_brightness"),
        "avg_saturation": analysis.get("color_features", {}).get("avg_saturation"),
        "avg_contrast": analysis.get("color_features", {}).get("avg_contrast"),
        "grading_style": analysis.get("color_features", {}).get("grading_style"),
        "avg_motion": analysis.get("motion_features", {}).get("avg_motion"),
        "motion_style": analysis.get("motion_features", {}).get("motion_style"),
        "rhythm": analysis.get("rhythm_analysis", {}).get("rhythm"),
        "bpm": analysis.get("rhythm_analysis", {}).get("bpm_equivalent"),
        "vfx_count": analysis.get("visual_effects", {}).get("effect_count"),
    }


def _consistency_check(a: dict, b: dict) -> list[str]:
    issues: list[str] = []
    fa, fb = _pick_fields(a), _pick_fields(b)

    # 标量相对误差 < 8% 视为一致（不同采样重叠帧 + 光流首帧差异会引入小幅漂移）
    for k in ("avg_brightness", "avg_saturation", "avg_contrast", "avg_motion", "bpm"):
        va, vb = fa.get(k), fb.get(k)
        if va is None or vb is None or va == 0:
            continue
        rel = abs(va - vb) / abs(va)
        if rel > 0.08:
            issues.append(f"字段 {k}: v2={va:.2f} vs v3={vb:.2f} (差 {rel:.1%})")
    for k in ("grading_style", "motion_style", "rhythm"):
        if fa.get(k) != fb.get(k):
            issues.append(f"标签 {k}: v2={fa.get(k)!r} vs v3={fb.get(k)!r}")
    diff_frames = abs(fa["frames"] - fb["frames"])
    if diff_frames > max(2, fa["frames"] * 0.02):
        issues.append(f"采样帧数差较大: v2={fa['frames']} v3={fb['frames']}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=str, help="待分析视频路径")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--skip-v2", action="store_true", help="跳过 v2 基准（仅验证 v3 能跑完）")
    parser.add_argument("--sample-interval", type=int, default=5)
    args = parser.parse_args()

    vp = Path(args.video)
    if not vp.exists():
        print(f"视频不存在: {vp}")
        return 2

    print(f"[准备] 视频: {vp}")
    print(f"[准备] sample_interval={args.sample_interval}  workers={args.workers}")
    print()

    v2_result = None
    if not args.skip_v2:
        try:
            from video_analyzer_enhanced import EnhancedVideoAnalyzer  # type: ignore
        except Exception as exc:  # noqa: BLE001
            print(f"[v2] 加载失败: {exc}")
        else:
            v2 = EnhancedVideoAnalyzer(enable_cache=False)
            t0 = time.perf_counter()
            v2_result = v2.analyze_video(str(vp), sample_interval=args.sample_interval)
            v2_ms = (time.perf_counter() - t0) * 1000
            print(f"[v2] 完成: 总耗时 {v2_ms:.0f}ms  采样帧数 {v2_result.get('total_frames_sampled')}  场景 {v2_result.get('scene_count')}")
    else:
        v2_ms = None
        print("[v2] 已跳过基准")

    from core.video_analyzer_accelerated import AcceleratedVideoAnalyzer

    v3 = AcceleratedVideoAnalyzer(enable_cache=False, num_workers=args.workers, use_gpu=True)
    t0 = time.perf_counter()
    v3_result = v3.analyze_video(str(vp), sample_interval=args.sample_interval)
    v3_ms = (time.perf_counter() - t0) * 1000
    perf = v3_result.get("_perf", {})
    print(f"[v3] 完成: 总耗时 {v3_ms:.0f}ms  采样帧数 {v3_result.get('total_frames_sampled')}  场景 {v3_result.get('scene_count')}")
    print(f"[v3] 加速模式: {perf.get('accelerator')}  workers={perf.get('num_workers')}  cuda={perf.get('cuda_available')} ({perf.get('cuda_reason')})")
    print(f"[v3] 分阶段耗时(ms): {json.dumps(perf.get('stage_ms', {}), ensure_ascii=False)}")

    if v2_result is not None and v2_result.get("success") and v3_result.get("success"):
        speedup = v2_ms / max(v3_ms, 1)
        print()
        print(f"[对比] 加速比: {speedup:.2f}x  (v2 {v2_ms:.0f}ms → v3 {v3_ms:.0f}ms)")
        issues = _consistency_check(v2_result, v3_result)
        if issues:
            print("[一致性] ⚠ 发现差异:")
            for it in issues:
                print("   -", it)
        else:
            print("[一致性] ✅ 关键特征 & 标签通过一致性校验")
        print("[对比] 关键特征:")
        for k, v2v in _pick_fields(v2_result).items():
            v3v = _pick_fields(v3_result).get(k)
            marker = "" if k in ("frames", "scenes", "vfx_count") else " "
            print(f"   {k:>18s}: v2={v2v!r}{marker} vs  v3={v3v!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
