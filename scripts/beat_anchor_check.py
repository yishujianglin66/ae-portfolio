# -*- coding: utf-8 -*-
"""beat_anchor_check.py — 踩点质量硬核诊断（切点 vs stem 鼓点锚）

为什么需要它：
  `beat_hit_rate`（score_reference_gap 口径）把切点落在**任意 onset ±80ms**
  都算命中——包含 hihat/人声瞬态等弱拍位。统计上高分，听感上未必"踩上"。
  R-2026-0001 的教训正是："笼统 onset（含 hihat/人声瞬态）退出切点候选池"。

本脚本用 **stem 真值锚**（kick/snare/melody，带 strength）做判定：
  强锚命中 = 切点落在 strength≥0.5 的 kick/snare ±80ms 内 ← 听感意义上的"踩点"
  弱锚命中 = 落在任意 kick/snare（含弱击）
  旋律命中 = 落在 melody 锚（小提琴/主旋律音头）
  笼统命中 = 仅落普通 onset（hihat/瞬态），听感最弱

用法:
  python scripts/beat_anchor_check.py --video <成品.mp4> [--anchors <anchors.json>]
  python scripts/beat_anchor_check.py --compare A.mp4 B.mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ / "scripts"))

FFPROBE = shutil.which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"

TOL = 0.080          # ±80ms，与 beat_hit_rate 同口径
STRONG = 0.5         # 强锚阈值（与生产链一致）
DEFAULT_ANCHORS = PROJ / "cache" / "stems" / "9e00915a2a31" / "anchors.json"


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def scene_cuts(path: Path, thr: float = 0.30) -> list[float]:
    import re
    r = _run([FF, "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo",
              "-f", "null", "-"], timeout=1200)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    return sorted(set(float(m) for m in re.findall(r"pts_time:([0-9.]+)", txt)))


def load_anchors(path: Path) -> dict:
    a = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for k in ("kick", "snare", "melody"):
        pairs = a.get(f"{k}_onsets", [])
        out[k] = [(float(t), float(s)) for t, s in pairs]
    return out


def nearest_gap(t: float, arr: list[tuple[float, float]]) -> float:
    if not arr:
        return 1e9
    return min(abs(t - x[0]) for x in arr)


def analyze(video: Path, anchors_path: Path) -> dict:
    cuts = scene_cuts(video)
    anc = load_anchors(anchors_path)
    kick = anc["kick"]
    snare = anc["snare"]
    melody = anc["melody"]
    drum = kick + snare
    strong_drum = [(t, s) for t, s in drum if s >= STRONG]

    rows = []
    for t in cuts:
        g_kick = nearest_gap(t, kick)
        g_snare = nearest_gap(t, snare)
        g_drum = min(g_kick, g_snare)
        g_mel = nearest_gap(t, melody)
        # 命中最近的强锚距离
        g_strong = nearest_gap(t, strong_drum)
        rows.append({
            "t": round(t, 3),
            "gap_drum": round(g_drum, 4),
            "gap_strong": round(g_strong, 4),
            "gap_melody": round(g_mel, 4),
        })

    n = len(rows) or 1
    strong_hit = sum(1 for r in rows if r["gap_strong"] <= TOL)
    drum_hit = sum(1 for r in rows if r["gap_drum"] <= TOL)
    mel_hit = sum(1 for r in rows if r["gap_melody"] <= TOL)
    none_hit = sum(1 for r in rows
                   if r["gap_drum"] > TOL and r["gap_melody"] > TOL)
    gaps = [r["gap_drum"] for r in rows]
    return {
        "video": video.name,
        "n_cuts": len(rows),
        "strong_drum_hit": strong_hit,
        "strong_drum_rate": round(strong_hit / n, 4),
        "drum_hit": drum_hit,
        "drum_rate": round(drum_hit / n, 4),
        "melody_hit": mel_hit,
        "melody_rate": round(mel_hit / n, 4),
        "neither_rate": round(none_hit / n, 4),
        "gap_drum_median": round(float(np.median(gaps)), 4) if rows else None,
        "gap_drum_p90": round(float(np.percentile(gaps, 90)), 4) if rows else None,
        "per_cut": rows,
        "anchor_scale": {"kick": len(kick), "snare": len(snare),
                         "melody": len(melody), "strong_drum": len(strong_drum)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None)
    ap.add_argument("--compare", nargs=2, default=None)
    ap.add_argument("--anchors", default=str(DEFAULT_ANCHORS))
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    apath = Path(args.anchors)
    if not apath.exists():
        print(f"锚点缓存不存在: {apath}")
        return 1

    videos = args.compare if args.compare else (
        [args.video] if args.video else [])
    if not videos:
        ap.error("需要 --video 或 --compare")
    vids = [Path(v) for v in videos]
    for v in vids:
        if not v.exists():
            print(f"视频不存在: {v}")
            return 1

    results = [analyze(v, apath) for v in vids]
    for r in results:
        print(f"\n=== {r['video']} ===")
        print(f"  切点 {r['n_cuts']} 刀 | 锚点规模 {r['anchor_scale']}")
        print(f"  强锚命中(kick/snare≥0.5, ±80ms): "
              f"{r['strong_drum_hit']}/{r['n_cuts']} = {r['strong_drum_rate']}")
        print(f"  任意鼓锚命中:  {r['drum_hit']}/{r['n_cuts']} = {r['drum_rate']}")
        print(f"  旋律锚命中:    {r['melody_hit']}/{r['n_cuts']} = {r['melody_rate']}")
        print(f"  落空(既非鼓也非旋律): {r['neither_rate']}")
        print(f"  切点→最近鼓锚距离: 中位 {r['gap_drum_median']}s / "
              f"p90 {r['gap_drum_p90']}s")

    if len(results) == 2:
        a, b = results
        d = round(b["strong_drum_rate"] - a["strong_drum_rate"], 4)
        print(f"\nΔ强锚命中 = {d:+.4f}  "
              f"({'B 更好' if d > 0 else 'A 更好'})")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results if len(results) > 1 else results[0],
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
