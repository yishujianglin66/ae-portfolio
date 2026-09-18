#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analyze_review_consistency.py - 复核队列 VLM vs LK 光流一致性分析

输入:
  D:/AE-Data/AnimeCamera/reviewed_results.jsonl  (74 条, VLM 低置信队列 + LK 重标注)
  D:/AE-Data/AnimeCamera/human_review_queue.jsonl (74 条原始队列)

输出: 控制台报告 + 可选 --json 落盘
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
REVIEWED = DATA_ROOT / "reviewed_results.jsonl"
QUEUE = DATA_ROOT / "human_review_queue.jsonl"

STAT_KEYS = ["mean_dx", "mean_dy", "mean_radial", "h_consistency",
             "v_consistency", "radial_consistency", "total_disp",
             "direction_entropy"]


def load(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fmt_pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100.0 * n / d:.1f}%)" if d else "-"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default="",
                    help="可选: 结果落盘 JSON 路径")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = load(REVIEWED)
    n = len(rows)
    report: dict[str, Any] = {"n": n}

    # ── 1. 标签分布 ──────────────────────────────────────────────
    vlm_dist = Counter(r["original_label"] for r in rows)
    flow_dist = Counter(r["reviewed_label"] for r in rows)
    print(f"样本总数: {n}")
    print("\n=== 1. 标签分布 (VLM原始 → LK光流重标注) ===")
    all_labels = sorted(set(vlm_dist) | set(flow_dist))
    print(f"{'label':<12} {'VLM':>8} {'LK':>8}")
    for lab in all_labels:
        print(f"{lab:<12} {vlm_dist.get(lab, 0):>8} {flow_dist.get(lab, 0):>8}")

    # ── 2. 混淆矩阵 ──────────────────────────────────────────────
    cm: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        cm[r["original_label"]][r["reviewed_label"]] += 1
    print("\n=== 2. 混淆矩阵 (行=VLM, 列=LK) ===")
    order = sorted(set(vlm_dist) | set(flow_dist))
    _col = "VLM\LK"
    print(f"{_col:<12} " + " ".join(f"{l:>12}" for l in order))
    for a in sorted(cm):
        row_str = " ".join(f"{cm[a].get(b, 0):>12}" for b in order)
        print(f"{a:<12} {row_str}")

    # 一致性
    agree = sum(1 for r in rows if not r["label_changed"])
    print(f"\n标签一致: {fmt_pct(agree, n)}; 标签变更: {fmt_pct(n - agree, n)}")

    # 同族一致 (方向翻转不算一致: zoom_in/zoom_out, pan_left/pan_right 等)
    fam = {"zoom_in": "zoom", "zoom_out": "zoom", "push": "zoom",
           "pan_left": "pan", "pan_right": "pan", "diag_pan": "pan",
           "tilt_up": "tilt", "tilt_down": "tilt"}
    fam_agree = sum(1 for r in rows
                    if fam.get(r["original_label"], r["original_label"])
                    == fam.get(r["reviewed_label"], r["reviewed_label"]))
    print(f"运动族一致 (方向可错): {fmt_pct(fam_agree, n)}")

    # ── 3. 置信度分布 ────────────────────────────────────────────
    vlm_confs = Counter(r["original_confidence"] for r in rows)
    flow_confs = Counter(round(r["reviewed_confidence"], 2) for r in rows)
    print("\n=== 3. 置信度分布 ===")
    print("VLM conf:", dict(sorted(vlm_confs.items())))
    print("LK  conf:", dict(sorted(flow_confs.items())))

    low = [r for r in rows if r["reviewed_confidence"] < 0.5]
    print(f"LK 低置信 (<0.5): {len(low)}")
    for r in low:
        print(f"  {r['shot_id']:<22} VLM={r['original_label']:<10} -> "
              f"LK={r['reviewed_label']:<10} conf={r['reviewed_confidence']:.2f}")

    # ── 4. 分段投票一致性 ────────────────────────────────────────
    print("\n=== 4. 分段投票一致性 (3段投票) ===")
    vote_shares = Counter()
    weak_votes = []
    for r in rows:
        segs = r.get("reviewed_per_segment", [])
        if not segs:
            continue
        votes = Counter(s["label"] for s in segs)
        top, top_n = votes.most_common(1)[0]
        share = top_n / len(segs)
        vote_shares[round(share, 2)] += 1
        if share < 2 / 3:
            weak_votes.append((r, top, votes))
    print("投票占比分布:", dict(sorted(vote_shares.items())))
    print(f"投票未过半 (主导标签占比<2/3): {len(weak_votes)}")
    for r, top, votes in weak_votes:
        print(f"  {r['shot_id']:<22} VLM={r['original_label']:<10} "
              f"LK最终={r['reviewed_label']:<10} 分段投票={dict(votes)}")

    # ── 5. 按 LK 标签看 flow_stats ───────────────────────────────
    print("\n=== 5. 各 LK 标签的全局 flow_stats 均值 (片段级) ===")
    per_label_stats: dict[str, list[dict[str, float]]] = defaultdict(list)
    for r in rows:
        for s in r.get("reviewed_per_segment", []):
            per_label_stats[s["label"]].append(s["flow_stats"])
    for lab in sorted(per_label_stats):
        lst = per_label_stats[lab]
        m = {k: sum(s.get(k, 0.0) for s in lst) / len(lst) for k in STAT_KEYS}
        print(f"  {lab:<10} n_seg={len(lst):>3} | disp={m['total_disp']:6.2f} "
              f"dx={m['mean_dx']:7.2f} dy={m['mean_dy']:7.2f} "
              f"rad={m['mean_radial']:7.2f} h_con={m['h_consistency']:.2f} "
              f"v_con={m['v_consistency']:.2f} rad_con={m['radial_consistency']:.2f} "
              f"entropy={m['direction_entropy']:.2f}")

    # ── 6. 方向翻转审计 ──────────────────────────────────────────
    print("\n=== 6. VLM vs LK 同族反向翻转 ===")
    flips = {"zoom_in": "zoom_out", "zoom_out": "zoom_in",
             "pan_left": "pan_right", "pan_right": "pan_left",
             "tilt_up": "tilt_down", "tilt_down": "tilt_up"}
    for r in rows:
        if flips.get(r["original_label"]) == r["reviewed_label"]:
            s0 = r["reviewed_per_segment"][0]["flow_stats"]
            print(f"  {r['shot_id']:<22} {r['original_label']}->{r['reviewed_label']} "
                  f"(rad={s0['mean_radial']:+.1f})")

    # ── 7. 弱决策审计: 兜底 complex(0.3) 与 低分标签 ──────────────
    print("\n=== 7. 弱决策审计 ===")
    fallback = [r for r in rows
                if r["reviewed_label"] == "complex" and r["reviewed_confidence"] < 0.4]
    print(f"兜底 complex (conf<0.4): {len(fallback)}")
    for r in fallback:
        print(f"  {r['shot_id']:<22} VLM={r['original_label']:<10} conf={r['reviewed_confidence']:.2f}")

    # VLM complex 但 LK 给了明确方向 → LK 更细
    vlm_complex = [r for r in rows if r["original_label"] == "complex"]
    print(f"\nVLM=complex 的样本: {len(vlm_complex)} -> LK 标签分布: "
          f"{dict(Counter(r['reviewed_label'] for r in vlm_complex))}")

    report.update({
        "vlm_dist": dict(vlm_dist), "flow_dist": dict(flow_dist),
        "agree": agree, "fam_agree": fam_agree,
        "flow_conf_dist": {str(k): v for k, v in flow_confs.items()},
        "weak_vote_count": len(weak_votes),
        "fallback_complex_count": len(fallback),
    })
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"\n报告已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
