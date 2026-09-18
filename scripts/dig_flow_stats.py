#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dig_flow_stats.py — 分层评估明细的 flow_stats 深挖

回答:
  Q1: zoom 方向反转假说 — VLM zoom_in/zoom_out 样本的 mean_radial 符号分布
  Q2: VLM pan 样本为何大量变成 static/zoom_in — disp/h_con/rad_con 分布
  Q3: 分类器各分支触发情况 (回放 _classify_from_stats)
  Q4: 分段 vs 全局统计差异
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.camera_movement_classifier import _classify_from_stats  # noqa: E402

DETAIL = PROJECT_ROOT / "models" / "output" / "flow_vlm_eval.jsonl"


def qdist(vals: list[float], edges: list[float]) -> dict[str, int]:
    out = Counter()
    for v in vals:
        b = ">%.1f" % edges[-1]
        for lo, hi in zip(edges[:-1], edges[1:]):
            if lo <= v < hi:
                b = f"[{lo:.1f},{hi:.1f})"
                break
        if v < edges[0]:
            b = f"<{edges[0]:.1f}"
        out[b] += 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = [json.loads(l) for l in DETAIL.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"明细样本: {len(rows)}")

    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_label[r["vlm_label"]].append(r)

    # ── Q1: zoom 方向 ─────────────────────────────────────────
    print("\n===== Q1: zoom 方向符号 =====")
    print("VLM zoom_in:  mean_radial 符号分布 (radial>0=画面外扩/放大):")
    zin = [r["flow_stats"]["mean_radial"] for r in by_label["zoom_in"]]
    print(f"   n={len(zin)} | >0: {sum(1 for v in zin if v > 0)} "
          f"| <0: {sum(1 for v in zin if v < 0)} | mean={np.mean(zin):+.2f} med={np.median(zin):+.2f}")
    print("VLM zoom_out: mean_radial 符号分布:")
    zout = [r["flow_stats"]["mean_radial"] for r in by_label["zoom_out"]]
    print(f"   n={len(zout)} | >0: {sum(1 for v in zout if v > 0)} "
          f"| <0: {sum(1 for v in zout if v < 0)} | mean={np.mean(zout):+.2f} med={np.median(zout):+.2f}")

    # ── Q2: pan 样本 stats 分布 ───────────────────────────────
    print("\n===== Q2: VLM pan 样本的 flow stats =====")
    for lab in ("pan_left", "pan_right"):
        sub = by_label[lab]
        disp = [r["flow_stats"]["total_disp"] for r in sub]
        hcon = [r["flow_stats"]["h_consistency"] for r in sub]
        radcon = [r["flow_stats"]["radial_consistency"] for r in sub]
        mdx = [r["flow_stats"]["mean_dx"] for r in sub]
        mrad = [r["flow_stats"]["mean_radial"] for r in sub]
        print(f"\n  {lab} (n={len(sub)}):")
        print(f"    disp  分布: {qdist(disp, [0, 1, 2, 4, 8, 16, 32])}")
        print(f"    h_con 分布: {qdist(hcon, [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])}")
        print(f"    rad_con 分布: {qdist(radcon, [0.2, 0.3, 0.4, 0.5, 0.6, 0.7])}")
        print(f"    mean_dx 分布: {qdist(mdx, [-16, -8, -4, 0, 4, 8, 16])}")
        print(f"    mean_radial 分布: {qdist(mrad, [-16, -8, -4, 0, 4, 8, 16])}")

    # ── Q3: 回放当前分类器分支 ────────────────────────────────
    print("\n===== Q3: 回放当前规则, 各 VLM 标签 → 判定路径 =====")
    # 简化: 直接看 flow_label 与 VLM 的对照已在 eval; 这里按规则重算 global 标签核对
    mism = 0
    path_count = Counter()
    for r in rows:
        lab, conf = _classify_from_stats(r["flow_stats"])
        if lab != r["flow_label"]:
            mism += 1
        # 粗路径推断
        fs = r["flow_stats"]
        if fs["radial_consistency"] > 0.4 and abs(fs["mean_radial"]) > 0.3 \
                and fs["radial_consistency"] >= fs["h_consistency"] \
                and fs["radial_consistency"] >= fs["v_consistency"]:
            path_count["zoom-branch"] += 1
        elif fs["total_disp"] < 1.0:
            path_count["static-branch"] += 1
        elif fs["h_consistency"] > 0.55 and fs["h_consistency"] > fs["v_consistency"]:
            path_count["pan-branch"] += 1
        elif fs["v_consistency"] > 0.5 and fs["v_consistency"] > fs["h_consistency"]:
            path_count["tilt-branch"] += 1
        else:
            path_count["fallback/complex"] += 1
    print(f"  全局回放与文件 flow_label 不一致: {mism} (分类器投票聚合导致, 正常)")
    print("  分支触发:", dict(path_count))

    # ── Q4: 分段统计 vs 全局 ──────────────────────────────────
    print("\n===== Q4: 分段投票聚合影响 =====")
    tie = 0
    for r in rows:
        segs = r.get("per_segment", [])
        if len(segs) < 3:
            continue
        votes = Counter(s["label"] for s in segs)
        top_n = votes.most_common(1)[0][1]
        if top_n <= 1:
            tie += 1
    print(f"  3段投票平局 (1/1/1): {tie}/{len(rows)}")

    # ── Q5: VLM static 样本 disp ──────────────────────────────
    print("\n===== Q5: VLM static 样本 =====")
    sub = by_label["static"]
    disp = [r["flow_stats"]["total_disp"] for r in sub]
    print(f"   n={len(sub)} disp分布: {qdist(disp, [0, 1, 2, 4, 8, 16])}")
    print(f"   flow标签: {dict(Counter(r['flow_label'] for r in sub))}")

    # ── Q6: tilt 样本 ─────────────────────────────────────────
    print("\n===== Q6: VLM tilt 样本 =====")
    for lab in ("tilt_up", "tilt_down"):
        sub = by_label[lab]
        dy = [r["flow_stats"]["mean_dy"] for r in sub]
        vcon = [r["flow_stats"]["v_consistency"] for r in sub]
        disp = [r["flow_stats"]["total_disp"] for r in sub]
        print(f"   {lab} (n={len(sub)}): mean_dy 符号 >0:{sum(1 for v in dy if v>0)} "
              f"<0:{sum(1 for v in dy if v<0)} | v_con med={np.median(vcon):.2f} "
              f"| disp med={np.median(disp):.2f} | flow标签: "
              f"{dict(Counter(r['flow_label'] for r in sub))}")

    # ── Q7: 时长与一致率 ──────────────────────────────────────
    print("\n===== Q7: 一致率 vs 时长 =====")
    for lo, hi in [(0, 1.0), (1.0, 1.5), (1.5, 3.0), (3.0, 99)]:
        sub = [r for r in rows if lo <= r["duration_sec"] < hi]
        if sub:
            e = sum(1 for r in sub if r["flow_label"] == r["vlm_label"])
            print(f"   duration [{lo},{hi}): {e}/{len(sub)} ({100.0*e/len(sub):.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
