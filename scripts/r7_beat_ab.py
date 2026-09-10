# -*- coding: utf-8 -*-
"""r7_beat_ab.py — beat_this vs 现链 节拍检测 A/B（2026-09-07 方案 R7）

R7 目标：用 beat_this（CPJKU 2024）替换 madmom/librosa onset 链，精度更优。
本脚本做**同口径 A/B**，避免"换了但说不清好在哪"。

评测维度（三者互补，单一指标会误判）：
  1. 拍点一致性：两法拍点匹配率（±70ms 容差，等同 beat_hit_rate 口径）
  2. 节拍网格规整度：拍间隔的变异系数（CV，越小越稳）
  3. BPM 稳定性：分段 BPM 的标准差（越小越不易漂）
  4. 下拍可用性：现链 librosa 无下拍输出，beat_this 有 → 这是**结构性差异**

设计说明：
  - 两法都在**同一 BGM**上跑，避免素材差异。
  - 匹配用"最近邻 + 容差"，不做全局对齐（对齐会掩盖局部误差）。
  - 结论只描述实测，不预设谁更好。

用法: python scripts/r7_beat_ab.py [--bgm <path>] [--out reports/r7_beat_ab.json]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")

MATCH_TOL = 0.070          # 70ms，与 beat_hit_rate 的 ±80ms 略严
DEFAULT_BGMS = [
    r"D:/AE-Work/音频素材库/BGM/1_from10s.mp3",
    r"D:/AE-Work/音频素材库/BGM/2 [高质量].mp3",
    r"D:/AE-Work/音频素材库/BGM/DiorGoFlex_AllEyesOnMe_full.mp3",
]


def detect_current(bgm: str) -> dict:
    """现链：librosa.beat.beat_track（madmom 未装时的降级路径）。"""
    import librosa
    t0 = time.time()
    y, sr = librosa.load(bgm, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beats = librosa.frames_to_time(beat_frames, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    return {
        "method": "librosa.beat_track",
        "beats": [round(float(t), 4) for t in beats],
        "bpm": round(bpm, 2),
        "downbeats": [],          # 现链无下拍能力
        "elapsed_s": round(time.time() - t0, 2),
    }


def detect_beat_this(bgm: str) -> dict:
    """beat_this（CPJKU 2024）：拍点 + 下拍。"""
    from beat_this.inference import File2Beats
    t0 = time.time()
    f2b = File2Beats(checkpoint_path="final0", device="cuda", dbn=False)
    beats, downbeats = f2b(bgm)
    return {
        "method": "beat_this(final0)",
        "beats": [round(float(t), 4) for t in beats],
        "bpm": None,              # 由拍间隔推断
        "downbeats": [round(float(t), 4) for t in downbeats],
        "elapsed_s": round(time.time() - t0, 2),
    }


def match_rate(a: list[float], b: list[float], tol: float = MATCH_TOL) -> dict:
    """a 中能被 b 匹配的比例（最近邻 + 容差）。"""
    if not a or not b:
        return {"matched": 0, "total": len(a), "rate": 0.0}
    b_arr = np.asarray(b)
    hit = 0
    for t in a:
        if np.min(np.abs(b_arr - t)) <= tol:
            hit += 1
    return {"matched": hit, "total": len(a), "rate": round(hit / len(a), 4)}


def interval_stats(beats: list[float]) -> dict:
    """拍间隔统计：均值 / CV / 推断 BPM。"""
    if len(beats) < 3:
        return {"n": len(beats)}
    iv = np.diff(np.asarray(beats))
    iv = iv[iv > 0]
    if iv.size == 0:
        return {"n": len(beats)}
    mean = float(iv.mean())
    return {
        "n": len(beats),
        "interval_mean": round(mean, 4),
        "interval_cv": round(float(iv.std() / mean), 4) if mean else 0.0,
        "inferred_bpm": round(60.0 / mean, 2) if mean else 0.0,
        "interval_std": round(float(iv.std()), 4),
    }


def bpm_stability(beats: list[float], window: float = 10.0) -> dict:
    """分段 BPM 标准差（越小越稳）。"""
    if len(beats) < 8:
        return {"segments": 0, "bpm_std": None}
    bpms = []
    start = beats[0]
    seg = []
    for t in beats:
        if t - start > window:
            if len(seg) >= 4:
                iv = np.diff(seg)
                iv = iv[iv > 0]
                if iv.size:
                    bpms.append(60.0 / float(iv.mean()))
            seg = []
            start = t
        seg.append(t)
    if len(seg) >= 4:
        iv = np.diff(seg)
        iv = iv[iv > 0]
        if iv.size:
            bpms.append(60.0 / float(iv.mean()))
    if len(bpms) < 2:
        return {"segments": len(bpms), "bpm_std": None}
    return {"segments": len(bpms),
            "bpm_std": round(statistics.stdev(bpms), 3),
            "segment_bpms": [round(b, 2) for b in bpms]}


def evaluate(bgm: str) -> dict:
    print(f"\n=== {Path(bgm).name} ===")
    cur = detect_current(bgm)
    bt = detect_beat_this(bgm)
    print(f"  librosa   : {len(cur['beats'])} 拍, bpm={cur['bpm']}, "
          f"{cur['elapsed_s']}s")
    print(f"  beat_this : {len(bt['beats'])} 拍, {len(bt['downbeats'])} 下拍, "
          f"{bt['elapsed_s']}s")

    m_cur = match_rate(cur["beats"], bt["beats"])
    m_bt = match_rate(bt["beats"], cur["beats"])
    i_cur = interval_stats(cur["beats"])
    i_bt = interval_stats(bt["beats"])
    s_cur = bpm_stability(cur["beats"])
    s_bt = bpm_stability(bt["beats"])

    print(f"  互匹配率  : librosa→beat_this {m_cur['rate']} | "
          f"beat_this→librosa {m_bt['rate']}")
    print(f"  拍间隔 CV : librosa {i_cur.get('interval_cv')} | "
          f"beat_this {i_bt.get('interval_cv')}")
    print(f"  推断 BPM  : librosa {i_cur.get('inferred_bpm')} | "
          f"beat_this {i_bt.get('inferred_bpm')}")

    return {
        "bgm": bgm,
        "librosa": {**cur, "interval": i_cur, "stability": s_cur},
        "beat_this": {**bt, "interval": i_bt, "stability": s_bt},
        "cross_match": {"librosa_to_bt": m_cur, "bt_to_librosa": m_bt},
        "structural_diff": {
            "downbeats_librosa": 0,
            "downbeats_beat_this": len(bt["downbeats"]),
            "note": "现链无下拍输出；beat_this 提供 4/4 下拍，"
                    "是网格量化锚（R-2026-0002）的直接输入",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bgm", default=None, help="单个 BGM；缺省跑默认三首")
    ap.add_argument("--out", default="reports/r7_beat_ab.json")
    args = ap.parse_args()

    bgms = [args.bgm] if args.bgm else DEFAULT_BGMS
    results = [evaluate(b) for b in bgms if Path(b).exists()]
    if not results:
        print("无可评测 BGM")
        return 1

    # 汇总
    summary = {
        "n_bgms": len(results),
        "librosa_beats_mean": round(statistics.mean(
            len(r["librosa"]["beats"]) for r in results), 1),
        "beat_this_beats_mean": round(statistics.mean(
            len(r["beat_this"]["beats"]) for r in results), 1),
        "librosa_to_bt_rate_mean": round(statistics.mean(
            r["cross_match"]["librosa_to_bt"]["rate"] for r in results), 4),
        "librosa_cv_mean": round(statistics.mean(
            r["librosa"]["interval"].get("interval_cv", 0) for r in results), 4),
        "beat_this_cv_mean": round(statistics.mean(
            r["beat_this"]["interval"].get("interval_cv", 0) for r in results), 4),
        "librosa_total_s": round(sum(r["librosa"]["elapsed_s"] for r in results), 1),
        "beat_this_total_s": round(sum(r["beat_this"]["elapsed_s"] for r in results), 1),
        "downbeats_available": {
            "librosa": False,
            "beat_this": True,
        },
    }
    print("\n" + "=" * 60)
    print("汇总:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("=" * 60)

    out = PROJ / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "per_bgm": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
