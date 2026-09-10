# -*- coding: utf-8 -*-
"""cut_visibility_v3.py — 声明切点驱动的可见性度量（2026-09-10）

## 为什么必须有 v3（v2 的幸存者偏差缺陷）

v2 用 ffmpeg 场景检测（scene thr）自行发现切点，再只给"发现的切点"打分。
实测对比暴露致命问题：

    selfeval 声明切点      107 刀
    v2 场景检测发现         68 刀   ← 39 个声明切点在画面上无变化，直接被丢弃
    v2 报出的冻结率        2.94%    ← 分母只有 68，且全是"本来就合格"的切点

→ v2 天然自我表扬：坏切点不被计分，指标永远好看。run61 在 v2 下 1.0494/PASS，
  但同一支片子在 selfeval 下 76/107 = 69% 的切点是"切了个寂寞"。
  两个结论差 20 倍，不是误差，是口径错了。

## v3 口径

分母 = **EDL 声明切点全集**（不管画面对不对得上，声明了就要负责）。
每个声明切点独立计算：
  - vis      : 帧号对齐，frame(fn-1) vs frame(fn+1/+2/+3) 三对归一化帧差均值
  - hamming  : ahash(frame(fn-1), frame(fn+1))，<10 判 frozen
  - 取帧失败 : 计入 missing，分母不减（保守）

派生指标：
  - cut_visibility_v3 : 全部声明切点 vis 均值（missing 记 0）
  - frozen_rate       : frozen / n_declared
  - weak_rate         : vis < 0.20 的占比（"几乎看不见的切"）
  - coverage          : n_measured / n_declared（取帧成功率，<1 说明时序有问题）

## 与 selfeval 的关系

selfeval 的 frozen_cut 用 ahash/dhash 128bit，v3 用 ahash 64bit。
两者判据同源（Hamming < 10），v3 额外给出连续量 vis，可排序定位最差切点。

用法:
  python scripts/cut_visibility_v3.py <video> [--edl edl.json] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from scripts.cut_visibility_v2 import (  # noqa: E402
    ahash, frames_by_number, hamming, norm, probe_fps, safe_video,
)

FREEZE_HAMMING = 10
PAIR_OFFSETS = (1, 2, 3)
WEAK_VIS = 0.20


def find_edl_for(video: Path) -> Path | None:
    """按项目约定从视频路径反查 EDL：output/unified_<run>/edl.json"""
    for p in [video, *video.parents]:
        if p.is_dir():
            cand = p / "edl.json"
            if cand.is_file():
                return cand
    return None


def load_declared_cuts(edl: Path) -> list:
    """从 EDL 取声明切点；兼容 cut_points / cuts 两种结构。"""
    data = json.loads(edl.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if isinstance(data.get("cut_points"), list):
            return [float(t) for t in data["cut_points"]]
        cuts = data.get("cuts")
        if isinstance(cuts, list) and cuts:
            # 段边界（首段 start 不算切点）
            return [float(s["start_time"]) for s in cuts[1:]
                    if s.get("start_time") is not None]
    if isinstance(data, list):
        return [float(t) for t in data]
    return []


def analyze_declared(video: Path, cut_times: list,
                     freeze_hamming: int = FREEZE_HAMMING) -> dict:
    """按声明切点全集计算可见性。分母恒为 len(cut_times)。"""
    fps = probe_fps(video)
    n_declared = len(cut_times)
    if n_declared == 0:
        return {"video": str(video), "fps": fps, "n_declared": 0,
                "n_measured": 0, "cut_visibility_v3": 0.0,
                "frozen_rate": 0.0, "weak_rate": 0.0, "coverage": 0.0,
                "p25": 0.0, "p50": 0.0, "p75": 0.0, "min": 0.0,
                "cuts": []}

    needed = set()
    cut_fns = []
    for t in cut_times:
        fn = int(round(float(t) * fps))
        cut_fns.append(fn)
        needed.add(fn - 1)
        for off in PAIR_OFFSETS:
            needed.add(fn + off)
    frames = frames_by_number(video, sorted(needed))

    rows = []
    for t, fn in zip(cut_times, cut_fns):
        prev = frames.get(fn - 1)
        if prev is None:
            rows.append({"t": round(float(t), 3), "frame": fn,
                         "vis": None, "ahash_dist": None,
                         "status": "missing"})
            continue
        pn = norm(prev)
        diffs = [float(np.abs(pn - norm(frames[fn + o])).mean())
                 for o in PAIR_OFFSETS if (fn + o) in frames]
        nxt1 = frames.get(fn + 1)
        hd = hamming(ahash(prev), ahash(nxt1)) if nxt1 is not None else None
        frozen = hd is not None and hd < freeze_hamming
        rows.append({
            "t": round(float(t), 3), "frame": fn,
            "vis": round(float(np.mean(diffs)), 4) if diffs else None,
            "ahash_dist": hd, "frozen": bool(frozen),
            "status": "measured" if diffs else "missing",
        })

    vis_all = [r["vis"] if r["vis"] is not None else 0.0 for r in rows]
    measured = [v for v in vis_all if v > 0]
    frozen_n = sum(1 for r in rows if r.get("frozen"))
    weak_n = sum(1 for v in vis_all if v < WEAK_VIS)

    def pct(a, q):
        return round(float(np.percentile(a, q)), 4) if a else 0.0

    return {
        "video": str(video), "fps": fps,
        "n_declared": n_declared,
        "n_measured": len(measured),
        "coverage": round(len(measured) / n_declared, 4),
        "cut_visibility_v3": round(float(np.mean(vis_all)), 4) if vis_all else 0.0,
        "p25": pct(vis_all, 25), "p50": pct(vis_all, 50),
        "p75": pct(vis_all, 75),
        "min": round(float(np.min(vis_all)), 4) if vis_all else 0.0,
        "frozen_count": frozen_n,
        "frozen_rate": round(frozen_n / n_declared, 4),
        "weak_count": weak_n,
        "weak_rate": round(weak_n / n_declared, 4),
        "weak_vis_floor": WEAK_VIS,
        "freeze_hamming": freeze_hamming,
        "worst_cuts": sorted([r for r in rows if r["vis"] is not None],
                             key=lambda r: r["vis"])[:20],
        "frozen_cuts": [r for r in rows if r.get("frozen")],
        "cuts": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="切点可见性度量 v3（声明切点为分母）")
    ap.add_argument("video")
    ap.add_argument("--edl", default=None, help="EDL 路径（默认自动反查）")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    path = safe_video(args.video)
    if path is None:
        print(f"[v3] 非法视频路径: {args.video}")
        return 2

    edl = Path(args.edl) if args.edl else find_edl_for(path)
    if edl is None or not edl.is_file():
        print(f"[v3] 未找到 EDL，无法按声明切点度量: {path}")
        return 2
    cut_times = load_declared_cuts(edl)
    if not cut_times:
        print(f"[v3] EDL 无切点: {edl}")
        return 2

    m = analyze_declared(path, cut_times)
    print(f"[v3] {path.name}  声明 {m['n_declared']} 刀  "
          f"实测 {m['n_measured']} (覆盖 {m['coverage']:.1%})")
    print(f"     v3={m['cut_visibility_v3']:.4f}  p25={m['p25']:.4f}  "
          f"p50={m['p50']:.4f}  min={m['min']:.4f}")
    print(f"     冻结 {m['frozen_count']}/{m['n_declared']} "
          f"({m['frozen_rate']:.2%})   弱切 {m['weak_count']} "
          f"({m['weak_rate']:.2%}, vis<{WEAK_VIS})")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(m, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"     → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
