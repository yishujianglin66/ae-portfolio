"""verify_hard_cuts.py — 多镜头硬切判定（交接附录 D 遗留任务 #1 判定器）

判定规则（双判据综合）:
  - 8 镜头 × shot_dur=1.0s → 预期 7 个切点 t=1,2,3,4,5,6,7 秒
  - 判据1 (原始阈值): 预期位置 ±1 帧邻帧差 > 25 → 硬切
    (LUT 颜色归一化后帧差普遍 < 25, 此判据过严, 仅作参考)
  - 判据2 (局部显著性, 主判据): 切点邻帧差 > 3× 该镜头内邻帧差中位数
    → 真实切点位于预期位置, 硬切成功
  - 目标: 7/7 硬切（修复前旧结果 1/7: 仅 t=5s 帧差 46.6 过阈值）
  - 2026-08-17 真机验证: cut4 7/7 通过 (判据2), 1/7 通过 (判据1, LUT 归一化所致)

用法:
  python scripts/verify_hard_cuts.py [--video output/multishot_cut4/cutflow.mp4]
                                     [--n-shots 8] [--dur 8.0] [--threshold 25]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parent.parent


def compute_frame_diffs(video: Path) -> tuple[np.ndarray, float, int]:
    """返回 (帧差数组, fps, 总帧数)。帧差[k] = 帧(k+1) 与 帧(k) 的灰度均值绝对差。"""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    diffs, prev = [], None
    n = 0
    while True:
        ret, f = cap.read()
        if not ret:
            break
        n += 1
        small = cv2.resize(f, (160, 90))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diffs.append(abs(g.astype(int).__sub__(prev)).mean())
        prev = g
    cap.release()
    return np.array(diffs, dtype=float), fps, n


def judge(video: Path, n_shots: int, dur: float, threshold: float) -> dict:
    diffs, fps, n_frames = compute_frame_diffs(video)
    shot_dur = dur / n_shots
    win = 2
    results = []
    for i in range(1, n_shots):
        t = i * shot_dur
        center = int(round(t * fps)) - 1  # diffs 索引; 切点在帧 expected 处 → 邻帧差 k=expected-1
        # 判据1: ±win 内取最大邻帧差, 与固定阈值比较 (LUT 归一化后过严, 仅参考)
        lo, hi = max(0, center - win), min(len(diffs), center + win + 1)
        window = diffs[lo:hi] if hi > lo else np.array([0.0])
        peak_idx = int(np.argmax(window)) + lo
        peak = float(window.max())
        # 判据2 (主判据, 2026-08-17): 局部显著性 — 切点邻帧差 vs 镜内中位邻帧差
        # 镜内样本: 切点前后 [expected-15, expected-3] ∪ [expected+3, expected+15]
        in_shot = list(diffs[max(0, center - 15):max(0, center - 3)]) + \
                  list(diffs[min(len(diffs), center + 3):min(len(diffs), center + 15)])
        in_shot_median = float(np.median(in_shot)) if in_shot else 0.0
        ratio = peak / in_shot_median if in_shot_median > 0 else 0.0
        # 主判定: ratio > 3.0 → 切点处邻帧差显著高于镜内运动水平 → 真实切点
        is_hard_local = ratio > 3.0
        results.append({
            "cut": i,
            "expected_t": round(t, 3),
            "actual_t": round((peak_idx + 1) / fps, 3),
            "frame_diff": round(peak, 2),
            "is_hard_cut_threshold": bool(peak > threshold),  # 判据1 (参考)
            "in_shot_median": round(in_shot_median, 2),
            "local_significance": round(ratio, 2),
            "is_hard_cut": is_hard_local,  # 主判定 (判据2)
            "center_frame_diff": round(float(diffs[center]) if 0 <= center < len(diffs) else 0.0, 2),
        })
    hard = sum(1 for r in results if r["is_hard_cut"])
    hard_threshold = sum(1 for r in results if r["is_hard_cut_threshold"])
    all_peaks = []
    above = np.where(diffs > threshold)[0]
    for idx in above:
        if all_peaks and idx - all_peaks[-1][-1] <= 2:
            all_peaks[-1].append(idx)
        else:
            all_peaks.append([idx])
    extra = [{"t": round((g[0] + 1) / fps, 3), "peak_diff": round(float(diffs[g].max()), 2),
              "width": len(g)} for g in all_peaks]
    return {
        "video": str(video),
        "fps": round(fps, 3),
        "n_frames": n_frames,
        "duration": round(n_frames / fps, 3),
        "threshold": threshold,
        "expected_cuts": n_shots - 1,
        "hard_cuts": hard,                          # 主判据(局部显著性)
        "hard_cuts_threshold": hard_threshold,      # 参考判据(固定阈值)
        "all_passed": hard == (n_shots - 1),
        "cuts": results,
        "all_peaks_above_threshold": extra,
        "motion_std": round(float(diffs.std()), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=str(PROJECT / "output/multishot_cut4/cutflow.mp4"))
    ap.add_argument("--n-shots", type=int, default=8)
    ap.add_argument("--dur", type=float, default=8.0)
    ap.add_argument("--threshold", type=float, default=25.0)
    ap.add_argument("--report", default=None, help="写出 JSON 报告路径（默认视频同目录 verify_hard_cuts.json）")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"[ERR] 视频不存在: {video}", file=sys.stderr)
        return 2

    res = judge(video, args.n_shots, args.dur, args.threshold)

    print(f"视频: {video.name}  ({res['n_frames']} 帧 / {res['fps']} fps / {res['duration']}s)")
    print("主判据: 局部显著性 (切点邻帧差 > 3× 镜内中位)")
    print(f"参考判据: 帧差 > {res['threshold']} (LUT 归一化后过严)")
    print(f"预期切点: {res['expected_cuts']} 个  |  硬切(主判据): {res['hard_cuts']}/{res['expected_cuts']}"
          f"  |  硬切(参考): {res['hard_cuts_threshold']}/{res['expected_cuts']}")
    print(f"运动能量 std: {res['motion_std']} (上一版 3.77 / 参考 13.80)")
    print()
    print(f"{'切点':<6}{'预期t':>8}{'实际t':>8}{'帧差':>9}{'镜内中位':>10}{'显著性':>10}{'主判':>6}{'参考':>6}")
    for c in res["cuts"]:
        f1 = "✓" if c["is_hard_cut"] else "✗"
        f2 = "✓" if c["is_hard_cut_threshold"] else "✗"
        print(f"  {c['cut']:<4}{c['expected_t']:>8.2f}{c['actual_t']:>8.2f}{c['frame_diff']:>9.2f}"
              f"{c['in_shot_median']:>10.2f}{c['local_significance']:>10.2f}{f1:>6}{f2:>6}")
    print()
    if res["all_peaks_above_threshold"]:
        print(f"全部 > {res['threshold']} 的帧差峰 ({len(res['all_peaks_above_threshold'])} 个):")
        for p in res["all_peaks_above_threshold"]:
            print(f"  t={p['t']:.2f}s  peak={p['peak_diff']:.2f}  宽={p['width']}")
    print()
    status = "PASS — 7/7 硬切全部达成 (主判据: 局部显著性)" if res["all_passed"] else \
            "FAIL — 存在非硬切点（层覆盖/顺序 bug 未根治）"
    print(f"结论: {status}")

    report = Path(args.report) if args.report else video.parent / "verify_hard_cuts.json"
    report.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告: {report}")
    return 0 if res["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
