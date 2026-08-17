#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格评测指标脚本 — eval_style_metrics v1.0
============================================

《2026-08-10_风格复刻管线低成本开发方案.md》行动#2 / §0.3 量化指标体系的落地工具。

指标:
  SFD  风格特征距离 — 成片 vs 参考片 的风格特征余弦距离（0=完全一致）
  CBE  踩拍误差     — 成片切点到最近节拍的时间差中位数（ms，越小越好）
  TD   转场多样性   — 审计生产审计报告 production_report.json 中生效的非硬切转场数

两种 SFD 模式:
  --mode local  纯本地轻量特征（cut/色彩/运动/节拍8维，¥0，日常迭代用）
  --mode vrs    VRS 全链路 24 维特征（调 API 有成本，正式实验用）

用法:
  # 成片 vs 参考片（本地模式）
  python scripts/eval_style_metrics.py --output out.mp4 --reference ref.mp4

  # 附加踩拍误差（需提供成片使用的BGM）
  python scripts/eval_style_metrics.py --output out.mp4 --reference ref.mp4 \\
      --bgm bgm.mp3 --bgm-start 12.0

  # 转场多样性（指向含 production_report.json 的输出目录）
  python scripts/eval_style_metrics.py --report-dir output/xxx/

纯 CPU 实现，T32 训练期间可安全运行。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from core.style_spec_extractor import StyleSpecExtractor, StyleSpec


# ================================================================
#  SFD: 风格特征距离
# ================================================================

# local 模式各维度的合理范围（用于 minmax 归一化，与训练数据尺度一致）
_LOCAL_DIM_RANGES: List[Tuple[str, float, float]] = [
    ("cut_rate",            0.0,   4.0),
    ("avg_shot_duration",   0.2,   5.0),
    ("beat_sync_ratio",     0.0,   1.0),
    ("bpm",                60.0, 200.0),
    ("brightness",          0.0, 100.0),
    ("saturation",          0.0, 100.0),
    ("contrast",            0.0, 100.0),
    ("avg_motion",          0.0,  10.0),
]


def _spec_to_local_vector(spec: StyleSpec) -> List[float]:
    """StyleSpec → 8维本地特征向量（minmax归一化）"""
    raw = {
        "cut_rate": spec.cut_rate,
        "avg_shot_duration": spec.avg_shot_duration,
        "beat_sync_ratio": spec.beat_sync_ratio,
        "bpm": spec.bpm,
        "brightness": spec.color_profile.get("brightness", 50.0),
        "saturation": spec.color_profile.get("saturation", 50.0),
        "contrast": spec.color_profile.get("contrast", 50.0),
        "avg_motion": spec.avg_motion,
    }
    vec = []
    for name, lo, hi in _LOCAL_DIM_RANGES:
        v = float(raw.get(name, lo))
        vec.append(max(0.0, min(1.0, (v - lo) / (hi - lo))) if hi > lo else 0.0)
    return vec


def _cosine_distance(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


def compute_sfd_local(extractor: StyleSpecExtractor,
                      output_video: str, reference_video: str) -> Dict:
    """本地模式 SFD — 两条视频各提一份 StyleSpec 后算余弦距离"""
    print(f"[SFD-local] 分析成片: {Path(output_video).name}")
    spec_out = extractor.extract(output_video, analyze_motion=True)
    print(f"[SFD-local] 分析参考片: {Path(reference_video).name}")
    spec_ref = extractor.extract(reference_video, analyze_motion=True)

    vec_out = _spec_to_local_vector(spec_out)
    vec_ref = _spec_to_local_vector(spec_ref)
    sfd = _cosine_distance(vec_out, vec_ref)

    dims = {name: round(abs(vo - vr), 3)
            for (name, _, _), vo, vr in zip(_LOCAL_DIM_RANGES, vec_out, vec_ref)}
    return {
        "mode": "local",
        "sfd": round(sfd, 4),
        "dim_gap_normalized": dims,
        "output_vector": {n: round(v, 3) for (n, _, _), v in zip(_LOCAL_DIM_RANGES, vec_out)},
        "reference_vector": {n: round(v, 3) for (n, _, _), v in zip(_LOCAL_DIM_RANGES, vec_ref)},
    }


def compute_sfd_vrs(output_video: str, reference_video: str) -> Dict:
    """VRS 全链路 SFD — 24维特征余弦距离（注意：会消耗 VLM API 配额）"""
    from core.style_pipeline import analyze_video_style_sync

    print("[SFD-vrs] VRS分析成片（消耗API配额）...")
    res_out = analyze_video_style_sync(output_video)
    print("[SFD-vrs] VRS分析参考片（消耗API配额）...")
    res_ref = analyze_video_style_sync(reference_video)

    if not res_out.get("success") or not res_ref.get("success"):
        return {"mode": "vrs", "sfd": None,
                "error": "VRS 分析失败（mock 降级已 fail-closed，请检查分析链路）"}

    from core.style_feature_extractor import extract_style_features
    vec_out = extract_style_features(res_out)
    vec_ref = extract_style_features(res_ref)
    sfd = _cosine_distance(vec_out, vec_ref)
    return {"mode": "vrs", "sfd": round(sfd, 4), "dim_count": len(vec_out)}


# ================================================================
#  CBE: 踩拍误差
# ================================================================

def compute_cbe(extractor: StyleSpecExtractor, output_video: str,
                bgm_path: str, bgm_start_sec: float = 0.0,
                window_ms: float = 250.0) -> Dict:
    """成片切点 vs BGM 节拍的踩拍误差。

    切点：scdet 检测成片实际切点。
    节拍：BeatDetector 检测 BGM，时间轴平移 bgm_start_sec（成片从BGM该位置开始用）。
    """
    from ae.beat_detector import BeatDetector

    cut_times = extractor._detect_cuts(output_video, threshold=5.0)
    if not cut_times:
        return {"cbe_median_ms": None, "error": "成片未检测到切点"}

    detector = BeatDetector()
    beats = detector.detect_beats(bgm_path)
    if not beats:
        return {"cbe_median_ms": None, "error": "BGM 未检测到节拍"}

    # 成片时间轴 t → BGM 时间轴 t + bgm_start_sec
    beat_times = sorted(b.time - bgm_start_sec for b in beats)
    beat_times = [t for t in beat_times if t >= -0.5]

    diffs = []
    for ct in cut_times:
        nearest = min(beat_times, key=lambda bt: abs(bt - ct)) if beat_times else None
        if nearest is not None:
            diffs.append(abs(ct - nearest) * 1000.0)
    if not diffs:
        return {"cbe_median_ms": None, "error": "无有效切点-节拍配对"}

    diffs.sort()
    median = diffs[len(diffs) // 2]
    avg = sum(diffs) / len(diffs)
    on_beat = sum(1 for d in diffs if d <= 80.0) / len(diffs)

    return {
        "cbe_median_ms": round(median, 1),
        "cbe_avg_ms": round(avg, 1),
        "cbe_max_ms": round(diffs[-1], 1),
        "on_beat_ratio_80ms": round(on_beat, 3),
        "cut_count": len(cut_times),
        "beat_count": len(beat_times),
    }


# ================================================================
#  TD: 转场多样性（审计 production_report.json）
# ================================================================

def compute_td(report_dir: str) -> Dict:
    report_path = Path(report_dir) / "production_report.json"
    if not report_path.exists():
        return {"td": None, "error": f"未找到审计报告: {report_path}"}
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"td": None, "error": f"报告解析失败: {e}"}

    transitions = []
    for seg in report.get("script", {}).get("segments", []):
        t = seg.get("transition") or seg.get("transition_params", {}).get("type")
        if t:
            transitions.append(str(t))
    non_cut = [t for t in transitions if t != "cut"]
    types = sorted(set(non_cut))
    return {
        "td": len(types),
        "transition_types": types,
        "non_cut_count": len(non_cut),
        "total_segments": len(transitions),
    }


# ================================================================
#  KL: 颜色分布 KL 散度（补充 SFD 的辅助指标）
# ================================================================

def compute_color_kl(output_video: str, reference_video: str,
                     sample_frames: int = 60) -> Dict:
    """颜色分布 KL 散度 — 衡量成片与参考片的 HSV 直方图差异。

    比 SFD 的单点饱和度/亮度值更细粒度：直接比较颜色分布形状。
    KL(P||Q) = Σ P(i) * log(P(i)/Q(i))，越小越相似。
    """
    import subprocess, tempfile, os
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"kl_divergence": None, "error": "需要 opencv-python (cv2)"}

    def _extract_frames(video_path, n_frames):
        """均匀抽取 n_frames 帧，返回 HSV numpy array list"""
        dur_cmd = ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                   "-of", "csv=p=0", video_path]
        r = subprocess.run(dur_cmd, capture_output=True, text=True, timeout=10)
        try:
            dur = float(r.stdout.strip())
        except (ValueError, AttributeError):
            dur = 10.0
        interval = max(dur / (n_frames + 1), 0.1)
        frames = []
        with tempfile.TemporaryDirectory() as td:
            for i in range(n_frames):
                t = interval * (i + 1)
                out_png = os.path.join(td, f"f{i:04d}.png")
                cmd = ["ffmpeg", "-y", "-ss", f"{t:.2f}", "-i", video_path,
                       "-vframes", "1", "-vf", "scale=160:120", out_png]
                subprocess.run(cmd, capture_output=True, timeout=10)
                if os.path.exists(out_png) and os.path.getsize(out_png) > 0:
                    img = cv2.imread(out_png)
                    if img is not None:
                        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                        frames.append(hsv)
        return frames

    def _compute_histograms(frames, bins=16):
        """计算 HSV 三通道直方图并平均"""
        h_hist_avg = np.zeros(bins, dtype=np.float64)
        s_hist_avg = np.zeros(bins, dtype=np.float64)
        v_hist_avg = np.zeros(bins, dtype=np.float64)
        for hsv in frames:
            h_hist = cv2.calcHist([hsv], [0], None, [bins], [0, 180]).flatten()
            s_hist = cv2.calcHist([hsv], [1], None, [bins], [0, 256]).flatten()
            v_hist = cv2.calcHist([hsv], [2], None, [bins], [0, 256]).flatten()
            h_hist_avg += h_hist / (h_hist.sum() + 1e-10)
            s_hist_avg += s_hist / (s_hist.sum() + 1e-10)
            v_hist_avg += v_hist / (v_hist.sum() + 1e-10)
        n = max(len(frames), 1)
        return h_hist_avg / n, s_hist_avg / n, v_hist_avg / n

    def _kl_divergence(p, q, eps=1e-10):
        """KL(P||Q) 对称化版本: (KL(P||Q) + KL(Q||P)) / 2"""
        p = p + eps
        q = q + eps
        p = p / p.sum()
        q = q / q.sum()
        kl_pq = np.sum(p * np.log(p / q))
        kl_qp = np.sum(q * np.log(q / p))
        return float((kl_pq + kl_qp) / 2)

    print(f"[KL] 采样成片帧...")
    frames_out = _extract_frames(output_video, sample_frames)
    print(f"[KL] 采样参考片帧...")
    frames_ref = _extract_frames(reference_video, sample_frames)

    if not frames_out or not frames_ref:
        return {"kl_divergence": None, "error": "帧抽取失败"}

    h_out, s_out, v_out = _compute_histograms(frames_out)
    h_ref, s_ref, v_ref = _compute_histograms(frames_ref)

    kl_h = _kl_divergence(h_out, h_ref)
    kl_s = _kl_divergence(s_out, s_ref)
    kl_v = _kl_divergence(v_out, v_ref)
    kl_total = (kl_h + kl_s + kl_v) / 3

    return {
        "kl_divergence": round(kl_total, 4),
        "kl_hue": round(kl_h, 4),
        "kl_saturation": round(kl_s, 4),
        "kl_value": round(kl_v, 4),
        "frames_output": len(frames_out),
        "frames_reference": len(frames_ref),
        "interpretation": "越小越相似 (<0.1=高度一致, 0.1~0.3=相似, >0.3=差异显著)",
    }


# ================================================================
#  CLI
# ================================================================

def main():
    parser = argparse.ArgumentParser(description="风格评测指标（SFD/CBE/TD，纯CPU）")
    parser.add_argument("--output", default="", help="成片视频路径")
    parser.add_argument("--reference", default="", help="参考视频路径")
    parser.add_argument("--mode", choices=["local", "vrs"], default="local",
                        help="SFD 模式：local=纯本地(默认)，vrs=VRS全链路(耗API)")
    parser.add_argument("--bgm", default="", help="成片使用的BGM（计算CBE需要）")
    parser.add_argument("--bgm-start", type=float, default=0.0,
                        help="成片从BGM的哪个秒位开始")
    parser.add_argument("--report-dir", default="",
                        help="含 production_report.json 的输出目录（计算TD）")
    parser.add_argument("--out-json", default="", help="结果保存JSON路径")
    args = parser.parse_args()

    result: Dict = {"metrics": {}}
    extractor = StyleSpecExtractor()

    if args.output and args.reference:
        if args.mode == "local":
            result["metrics"]["SFD"] = compute_sfd_local(extractor, args.output, args.reference)
        else:
            result["metrics"]["SFD"] = compute_sfd_vrs(args.output, args.reference)
        # KL 散度作为 SFD 的补充指标
        result["metrics"]["KL"] = compute_color_kl(args.output, args.reference)
        if args.bgm:
            result["metrics"]["CBE"] = compute_cbe(
                extractor, args.output, args.bgm, args.bgm_start)
    elif args.bgm and args.output:
        result["metrics"]["CBE"] = compute_cbe(
            extractor, args.output, args.bgm, args.bgm_start)

    if args.report_dir:
        result["metrics"]["TD"] = compute_td(args.report_dir)

    if not result["metrics"]:
        parser.print_help()
        sys.exit(1)

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print("\n========== 评测结果 ==========")
    print(text)
    if args.out_json:
        Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out_json).write_text(text, encoding="utf-8")
        print(f"已保存: {args.out_json}")


if __name__ == "__main__":
    main()
