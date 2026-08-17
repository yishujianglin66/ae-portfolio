#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_review_runs.py — 旧/新分类器对复核队列结果的对照分析"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLD = Path(r"D:\AE-Data\AnimeCamera\reviewed_results.jsonl")
NEW = PROJECT_ROOT / "models" / "output" / "reviewed_results_v2.jsonl"


def load(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    old = load(OLD)
    new = load(NEW)
    old_by = {r["shot_id"]: r for r in old}
    n = len(new)
    print(f"样本: 旧 {len(old)} / 新 {n}")

    # 标签分布对比
    print("\n=== 标签分布 (VLM → 旧LK → 新LK) ===")
    vlm_d = Counter(r["original_label"] for r in new)
    old_d = Counter(old_by[s]["reviewed_label"] for s in old_by)
    new_d = Counter(r["reviewed_label"] for r in new)
    labels = sorted(set(vlm_d) | set(old_d) | set(new_d))
    print(f"{'label':<12} {'VLM':>6} {'旧LK':>6} {'新LK':>6}")
    for lab in labels:
        print(f"{lab:<12} {vlm_d.get(lab, 0):>6} {old_d.get(lab, 0):>6} {new_d.get(lab, 0):>6}")

    changed_old = sum(1 for r in old if r["label_changed"])
    changed_new = sum(1 for r in new if r["label_changed"])
    print(f"\n标签变更率: 旧 {changed_old}/{n} ({100.0 * changed_old / n:.1f}%)  "
          f"新 {changed_new}/{n} ({100.0 * changed_new / n:.1f}%)")

    # 新旧分类器自身一致性 (同一素材两次分类)
    same = sum(1 for r in new if old_by[r["shot_id"]]["reviewed_label"] == r["reviewed_label"])
    print(f"新旧分类器对同一素材标签一致: {same}/{n} ({100.0 * same / n:.1f}%)")
    print("\n新旧标签变更的样本 (旧 → 新):")
    for r in new:
        o = old_by[r["shot_id"]]
        if o["reviewed_label"] != r["reviewed_label"]:
            print(f"  {r['shot_id']:<22} VLM={r['original_label']:<9} "
                  f"旧={o['reviewed_label']:<10} (conf {o['reviewed_confidence']:.2f}) → "
                  f"新={r['reviewed_label']:<10} (conf {r['reviewed_confidence']:.2f})")

    # 平局统计 (新)
    tie = 0
    for r in new:
        segs = r.get("reviewed_per_segment", [])
        if len(segs) == 3:
            votes = Counter(s["label"] for s in segs)
            if votes.most_common(1)[0][1] == 1:
                tie += 1
    print(f"\n新结果 3 段投票平局数: {tie} (旧为 18)")

    # 置信度分布
    confs = Counter(round(r["reviewed_confidence"], 1) for r in new)
    print("新结果置信度分布:", dict(sorted(confs.items())))
    low = [r for r in new if r["reviewed_confidence"] < 0.5]
    print(f"新结果低置信 (<0.5): {len(low)}")
    for r in low:
        print(f"  {r['shot_id']:<22} VLM={r['original_label']:<9} → "
              f"{r['reviewed_label']:<10} conf={r['reviewed_confidence']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
