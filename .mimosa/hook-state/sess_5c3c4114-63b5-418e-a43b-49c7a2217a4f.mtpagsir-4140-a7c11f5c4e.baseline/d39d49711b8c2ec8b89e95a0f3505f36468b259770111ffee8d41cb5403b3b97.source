#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tune_camera_thresholds.py — 阈值网格搜索 (离线回放)

输入: models/output/flow_vlm_eval.jsonl (新管线逐条 flow_stats + per_segment)
方法: 对 (static_disp, pan_con, tilt_con, zoom_con, zoom_min_radial,
      entropy, fallback_conf) 网格, 逐段回放判定 + 投票聚合 (平局→全局),
      与 VLM 标签对照, 按 VLM 置信度加权打分。
输出: models/output/camera_thresholds_tuned.json (最终阈值 + 诊断)
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"
OUT = PROJECT_ROOT / "models" / "output" / "camera_thresholds_tuned.json"

FAMILY = {"zoom_in": "zoom", "zoom_out": "zoom", "push": "zoom",
          "pan_left": "pan", "pan_right": "pan",
          "tilt_up": "tilt", "tilt_down": "tilt",
          "static": "static", "orbit": "orbit", "complex": "complex"}

GRID = {
    "static_disp": [0.5, 1.0, 1.5, 2.0],
    "pan_con": [0.40, 0.45, 0.50, 0.55],
    "tilt_con": [0.40, 0.45, 0.50, 0.55],
    "zoom_con": [0.20, 0.25, 0.30, 0.35, 0.40],
    "zoom_min_radial": [0.2, 0.3, 0.5],
    "entropy": [0.70, 0.75, 0.80],
    "fallback_conf": [0.10, 0.15, 0.20],
}


def classify(stats: Dict[str, float], th: Dict[str, float]) -> Tuple[str, float]:
    disp = stats["total_disp"]
    h_con = stats["h_consistency"]
    v_con = stats["v_consistency"]
    rad_con = stats["radial_consistency"]
    mean_rad = stats["mean_radial"]
    dx = stats["mean_dx"]
    dy = stats["mean_dy"]
    entropy = stats["direction_entropy"]

    if rad_con > th["zoom_con"] and abs(mean_rad) > th["zoom_min_radial"]:
        if rad_con >= h_con and rad_con >= v_con:
            return ("zoom_in" if mean_rad > 0 else "zoom_out"), min(rad_con, 1.0)
    if disp < th["static_disp"]:
        return "static", max(0.0, 1.0 - disp / th["static_disp"])
    if h_con > th["pan_con"] and h_con > v_con:
        return ("pan_left" if dx > 0 else "pan_right"), min(h_con, 1.0)
    if v_con > th["tilt_con"] and v_con > h_con:
        return ("tilt_up" if dy > 0 else "tilt_down"), min(v_con, 1.0)
    if h_con > th["pan_con"] and rad_con > th["zoom_con"]:
        return "complex", min(max(h_con, rad_con), 1.0)
    if entropy > th["entropy"]:
        return "complex", min(entropy, 1.0)
    signals = {
        "pan_left": h_con if dx > 0 else 0.0,
        "pan_right": h_con if dx < 0 else 0.0,
        "zoom_in": rad_con if mean_rad > 0 else 0.0,
        "zoom_out": rad_con if mean_rad < 0 else 0.0,
        "tilt_up": v_con if dy > 0 else 0.0,
        "tilt_down": v_con if dy < 0 else 0.0,
    }
    best = max(signals, key=signals.get)
    if signals[best] > th["fallback_conf"]:
        return best, signals[best]
    return "complex", 0.3


def clip_label(segs: List[Dict[str, Any]], global_stats: Dict[str, float],
               th: Dict[str, float]) -> str:
    """3段投票 + 平局→全局判定 (与分类器 classify_video 一致)。"""
    per = [classify(s["flow_stats"], th)[0] for s in segs]
    votes = Counter(per)
    if len(votes) == 1:
        return per[0]
    top2 = votes.most_common(2)
    if len(top2) > 1 and top2[0][1] == top2[1][1]:
        return classify(global_stats, th)[0]  # 平局 → 全局
    return top2[0][0]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(l) for l in DETAIL.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"调优集: {len(rows)} 条")

    keys = list(GRID)
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    print(f"网格组合: {len(combos)}")

    best: List[Tuple[float, Dict[str, float]]] = []
    for combo in combos:
        th = dict(zip(keys, combo))
        exact = fam = 0
        w_sum = 0.0
        for r in rows:
            segs = r.get("per_segment") or []
            if not segs:
                continue
            pred = clip_label(segs, r["flow_stats"], th)
            vlm = r["vlm_label"]
            w = {0.95: 2.0, 0.92: 1.5, 0.85: 1.0}.get(r["vlm_confidence"], 1.0)
            w_sum += w
            if pred == vlm:
                exact += w
            if FAMILY.get(pred, pred) == FAMILY.get(vlm, vlm):
                fam += w
        score = exact
        best.append((score, th, fam, w_sum))
        if len(best) > 400:
            best.sort(key=lambda x: -x[0])
            best = best[:200]

    best.sort(key=lambda x: (-x[0], -x[2]))
    print("\nTop 12 (按加权精确一致):")
    for i, (score, th, fam, w_sum) in enumerate(best[:12]):
        print(f"  {i + 1}. exact={score / w_sum:.4f} fam={fam / w_sum:.4f} | "
              + " ".join(f"{k}={v}" for k, v in th.items()))

    winner = best[0][1]
    # 用胜者阈值做逐类诊断
    n = 0
    cm: Dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        segs = r.get("per_segment") or []
        if not segs:
            continue
        n += 1
        pred = clip_label(segs, r["flow_stats"], winner)
        cm[r["vlm_label"]][pred] += 1
    report: Dict[str, Any] = {
        "tuned_on": "flow_vlm_eval.jsonl (544 条 VLM 高置信分层抽样)",
        "objective": "VLM 置信度加权精确一致率 (0.95x2 / 0.92x1.5 / 0.85x1)",
        "thresholds": winner,
        "exact_rate": round(best[0][0] / best[0][3], 4),
        "family_rate": round(best[0][2] / best[0][3], 4),
        "confusion": {k: dict(v) for k, v in cm.items()},
        "n": n,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n胜者阈值: {winner}")
    print(f"加权精确一致: {best[0][0] / best[0][3]:.4f} | 运动族一致: {best[0][2] / best[0][3]:.4f}")
    print(f"\n=== 胜者阈值混淆矩阵 (行=VLM, 列=光流) ===")
    order = sorted(set(cm) | {p for c in cm.values() for p in c})
    corner = "VLM\\FLOW"  # f-string 表达式内不能含反斜杠 (Py3.11 SyntaxError)
    print(f"{corner:<10} " + " ".join(f"{l:>10}" for l in order))
    for a in order:
        row = cm[a]
        print(f"{a:<10} " + " ".join(f"{row.get(b, 0):>10}" for b in order))
    print(f"报告 -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
