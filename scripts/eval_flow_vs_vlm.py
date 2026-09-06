#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""eval_flow_vs_vlm.py — 光流分类器 vs VLM 标注 大规模分层一致性评估

从 vlm_labels.jsonl 按 (标签 × 置信度档) 分层抽样, 对每条样本跑 LK 光流
分类器, 输出:
  models/output/flow_vlm_eval.jsonl   逐条明细 (含 flow_stats, 供阈值回放调优)
  models/output/flow_vlm_eval_report.json  汇总

用法:
  py -3.12 scripts/eval_flow_vs_vlm.py --per-cell 30
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import classify_video  # noqa: E402

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
LABELS_FILE = DATA_ROOT / "vlm_labels.jsonl"
OUT_DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"
OUT_REPORT = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval_report.json"

EVAL_LABELS = ["zoom_in", "zoom_out", "pan_left", "pan_right",
               "tilt_up", "tilt_down", "static", "push", "orbit"]
CONF_TIERS = [0.95, 0.92, 0.85]

FAMILY = {"zoom_in": "zoom", "zoom_out": "zoom", "push": "zoom",
          "pan_left": "pan", "pan_right": "pan",
          "tilt_up": "tilt", "tilt_down": "tilt",
          "static": "static", "orbit": "orbit"}
FLIPS = {"zoom_in": "zoom_out", "zoom_out": "zoom_in",
         "pan_left": "pan_right", "pan_right": "pan_left",
         "tilt_up": "tilt_down", "tilt_down": "tilt_up"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-cell", type=int, default=30,
                    help="每 (标签×置信档) 抽样上限")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = [json.loads(l) for l in LABELS_FILE.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    print(f"VLM 标注总量: {len(rows)}")

    # 分层抽样
    rng = random.Random(args.seed)
    cells: Dict[tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        lab = r.get("movement_label")
        if lab not in EVAL_LABELS:
            continue
        tier = next((t for t in CONF_TIERS if r.get("confidence", 0) >= t), None)
        if tier is None:
            continue
        cells[(lab, tier)].append(r)
    sample: List[Dict[str, Any]] = []
    for (lab, tier), lst in sorted(cells.items()):
        pick = rng.sample(lst, min(args.per_cell, len(lst)))
        sample.extend(pick)
        print(f"  {lab:<10} conf>={tier}: 抽 {len(pick)}/{len(lst)}")
    print(f"抽样总计: {len(sample)}")

    # 跑光流分类器
    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for i, s in enumerate(sample):
        clip = s["clip_path"]
        try:
            r = classify_video(clip)
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}] 失败 {clip}: {exc}")
            continue
        results.append({
            "shot_id": s["shot_id"], "clip_path": clip,
            "vlm_label": s["movement_label"], "vlm_confidence": s["confidence"],
            "duration_sec": s.get("duration_sec", 0),
            "flow_label": r["dominant"], "flow_confidence": r["confidence"],
            "flow_stats": r["flow_stats"],
            "per_segment": r.get("per_segment", []),
        })
        if (i + 1) % 50 == 0:
            print(f"  [{i + 1}/{len(sample)}] elapsed={time.time() - t0:.0f}s")

    with OUT_DETAIL.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ── 汇总 ──────────────────────────────────────────────────
    n = len(results)
    exact = sum(1 for r in results if r["flow_label"] == r["vlm_label"])
    fam = sum(1 for r in results
              if FAMILY.get(r["flow_label"], r["flow_label"])
              == FAMILY.get(r["vlm_label"], r["vlm_label"]))
    flip = sum(1 for r in results if FLIPS.get(r["vlm_label"]) == r["flow_label"])
    print(f"\n评估完成: n={n} 用时={time.time() - t0:.0f}s")
    print(f"精确一致: {exact}/{n} ({100.0 * exact / n:.1f}%)")
    print(f"运动族一致: {fam}/{n} ({100.0 * fam / n:.1f}%)")
    print(f"同族反向翻转: {flip}/{n} ({100.0 * flip / n:.1f}%)")

    # 每类 precision/recall (以 VLM 为参照)
    cm: Dict[str, Counter] = defaultdict(Counter)
    for r in results:
        cm[r["vlm_label"]][r["flow_label"]] += 1
    print("\n混淆矩阵 (行=VLM, 列=光流):")
    order = sorted(set(r["vlm_label"] for r in results)
                   | set(r["flow_label"] for r in results))
    _col = "VLM\FLOW"
    print(f"{_col:<10} " + " ".join(f"{l:>10}" for l in order))
    per_class: Dict[str, Any] = {}
    for a in order:
        row = cm[a]
        total = sum(row.values())
        correct = row[a]
        prec_denom = sum(cm[b][a] for b in order)
        per_class[a] = {
            "n": total,
            "recall": round(correct / total, 4) if total else None,
            "precision": round(correct / prec_denom, 4) if prec_denom else None,
        }
        print(f"{a:<10} " + " ".join(f"{row.get(b, 0):>10}" for b in order))
    print("\nper-class (VLM为参照):")
    for a, v in per_class.items():
        print(f"  {a:<10} n={v['n']:>3} recall={v['recall']} precision={v['precision']}")

    # 按 VLM 置信档
    print("\n按 VLM 置信档一致率:")
    for tier in CONF_TIERS:
        sub = [r for r in results if r["vlm_confidence"] >= tier]
        if not sub:
            continue
        e = sum(1 for r in sub if r["flow_label"] == r["vlm_label"])
        print(f"  conf>={tier}: {e}/{len(sub)} ({100.0 * e / len(sub):.1f}%)")

    report = {
        "n": n, "exact": exact, "family": fam, "flips": flip,
        "exact_rate": round(exact / n, 4) if n else 0.0,
        "confusion": {a: dict(cm[a]) for a in order},
        "per_class": per_class,
        "detail_path": str(OUT_DETAIL),
    }
    OUT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(f"\n明细 -> {OUT_DETAIL}\n汇总 -> {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
