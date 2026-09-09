# -*- coding: utf-8 -*-
"""cut_visibility_diag.py — 逐切点可见性诊断（2026-09-09）

为什么需要它：
  `score_reference_gap.py` 的 cut_visibility 只输出一个均值（采样 ≤12 个切点），
  无法回答"哪些切点弱、弱在哪"。R1 要求"每提升 1pp 留 evidence"，
  必须先有逐切点台账才能定位与验证。

度量口径（与 score_reference_gap 完全一致，避免自证偏差）：
  切点 t 的可见性 = mean(|norm(frame(t-1/24)) - norm(frame(t+3/24))|)
  其中 norm(x) = (x - mean) / std —— 零均值单位方差归一化，
  **亮度/闪白类变化会被归一化消掉**，因此该指标只反映"结构性内容变化"。

输出：
  - 逐切点表（时间、可见性、前后帧结构差、是否被官方采样命中）
  - 官方采样口径的均值（应与 score_reference_gap 的 cut_visibility 一致）
  - 最弱 N 个切点（定位用）

用法:
  python scripts/cut_visibility_diag.py --video output/unified_run61/polish/master_hr.mp4
  python scripts/cut_visibility_diag.py --video X --thr 0.30 --json reports/cutvis_run61.json
  python scripts/cut_visibility_diag.py --compare A.mp4 B.mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"
ALLOWED_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
SAMPLE_MAX = 12          # 与 score_reference_gap 一致：最多采样 12 个切点


def safe_video(raw: str | Path) -> Path | None:
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return p


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def scene_cuts(path: Path, thr: float) -> list[float]:
    """与 score_reference_gap._scene_cuts 同口径（ffmpeg select+scene）。"""
    cmd = [FF, "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo",
           "-f", "null", "-"]
    r = _run(cmd, timeout=1200)
    import re
    txt = (r.stderr or b"").decode("utf-8", "replace")
    cuts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", txt)]
    return sorted(set(cuts))


def frame_norm(path: Path, t: float, w: int = 48, h: int = 27) -> np.ndarray | None:
    """取一帧 → 灰度 → 缩放 → 零均值单位方差归一化（与官方口径一致）。"""
    cmd = [FF, "-ss", f"{max(t, 0):.3f}", "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={w}:{h},normalize", "-f", "rawvideo",
           "-pix_fmt", "gray", "-"]
    r = _run(cmd, timeout=120)
    v = np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)
    if v.size == 0:
        return None
    return (v - v.mean()) / (v.std() + 1e-6)


def per_cut(path: Path, thr: float) -> dict:
    cuts = scene_cuts(path, thr)
    n = len(cuts)
    rows = []
    for t in cuts:
        a = frame_norm(path, max(0.0, t - 1 / 24))
        b = frame_norm(path, t + 3 / 24)
        if a is None or b is None or a.shape != b.shape:
            continue
        rows.append({"t": round(t, 3), "vis": round(float(np.abs(a - b).mean()), 4)})
    # 官方采样口径：cuts[::max(1, n//12)][:12]
    sampled_idx = list(range(0, n, max(1, n // SAMPLE_MAX)))[:SAMPLE_MAX] if n else []
    sampled = [rows[i]["vis"] for i in sampled_idx if i < len(rows)]
    return {
        "video": str(path),
        "n_cuts": n,
        "n_measured": len(rows),
        "cut_visibility_official": round(float(np.mean(sampled)), 4) if sampled else 0.0,
        "cut_visibility_all": round(float(np.mean([r["vis"] for r in rows])), 4) if rows else 0.0,
        "sampled_indices": sampled_idx,
        "cuts": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None)
    ap.add_argument("--compare", nargs=2, default=None, help="对比两个视频")
    ap.add_argument("--thr", type=float, default=0.30)
    ap.add_argument("--weakest", type=int, default=15, help="列出最弱 N 个切点")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    if not args.video and not args.compare:
        ap.error("需要 --video 或 --compare")

    if args.compare:
        out = {}
        for v in args.compare:
            p = safe_video(v)
            if p is None:
                print(f"[跳过] {v}")
                continue
            r = per_cut(p, args.thr)
            out[p.name] = r
            print(f"{p.name}: 官方口径 {r['cut_visibility_official']} | "
                  f"全切点均值 {r['cut_visibility_all']} | {r['n_cuts']} cuts")
        if len(out) == 2:
            a, b = out.values()
            d = round(b["cut_visibility_official"] - a["cut_visibility_official"], 4)
            print(f"\nΔ(官方口径) = {d:+.4f}  {'✓ 提升' if d > 0 else '✗ 未提升'}")
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
        return 0

    p = safe_video(args.video)
    if p is None:
        print(f"无效视频: {args.video}")
        return 1
    r = per_cut(p, args.thr)
    print(f"视频: {p.name}")
    print(f"切点总数: {r['n_cuts']} | 成功测量: {r['n_measured']}")
    print(f"官方采样口径 cut_visibility = {r['cut_visibility_official']}")
    print(f"全切点均值               = {r['cut_visibility_all']}")
    print(f"官方采样索引: {r['sampled_indices']}")
    print(f"\n最弱 {args.weakest} 个切点:")
    print(f"  {'t(s)':>8}{'可见性':>10}  官方采样")
    weakest = sorted(r["cuts"], key=lambda x: x["vis"])[:args.weakest]
    idx_set = set(r["sampled_indices"])
    t_to_i = {round(c["t"], 3): i for i, c in enumerate(r["cuts"])}
    for c in weakest:
        hit = "★" if t_to_i.get(c["t"]) in idx_set else ""
        print(f"  {c['t']:>8.3f}{c['vis']:>10.4f}  {hit}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
        print(f"\nJSON → {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
