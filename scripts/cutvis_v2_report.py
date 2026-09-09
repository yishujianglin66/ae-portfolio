# -*- coding: utf-8 -*-
"""cutvis_v2_report.py — v2 切点可见性汇总报告（2026-09-09）

把 `cut_visibility_v2.py` 的逐部缓存聚合成人类可读报告：
  - 全体分位数 + 按风格分层（跨风格不可混算，见 README 说明）
  - 冻结率分布（scene 检测假切点率）
  - 与 run61 本片的同口径对比

用法:
  python scripts/cutvis_v2_report.py --mine output/unified_run61/polish/master_hr.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
CACHE = PROJ / "reports" / "cutvis_v2_cache.json"
MANIFEST = PROJ / "data" / "reference_top" / "_manifest.json"
OUT = PROJ / "reports" / "cut_visibility_v2.json"


def pct(vals: list[float], q: float) -> float:
    return round(float(np.percentile(vals, q)), 4) if vals else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", default=None, help="本片（与参照集同口径对比）")
    args = ap.parse_args()

    if not CACHE.exists():
        print(f"缓存不存在: {CACHE}")
        return 1
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    tier_of: dict[str, str] = {}
    quality_of: dict[str, str] = {}
    if MANIFEST.exists():
        for it in json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]:
            tier_of[it["file"]] = it["tier"]
            quality_of[it["file"]] = it.get("quality", "unknown")

    ok = {k: v for k, v in cache.items() if v.get("n_cuts")}
    no_cut = [k for k, v in cache.items() if not v.get("n_cuts")]

    allv = [v["cut_visibility_v2"] for v in ok.values()]
    allf = [v["frozen_rate"] for v in ok.values()]

    # 分层
    groups: dict[str, list] = defaultdict(list)
    for k, v in ok.items():
        groups[tier_of.get(k, "unknown")].append(v)
    by_tier = {}
    for t, rows in groups.items():
        vs = [r["cut_visibility_v2"] for r in rows]
        fz = [r["frozen_rate"] for r in rows]
        by_tier[t] = {
            "n": len(rows),
            "v2_mean": round(float(np.mean(vs)), 4),
            "v2_p50": pct(vs, 50),
            "frozen_mean": round(float(np.mean(fz)), 4),
        }

    # 本片
    mine = None
    if args.mine:
        p = Path(args.mine)
        if p.exists():
            sys.path.insert(0, str(PROJ / "scripts"))
            from cut_visibility_v2 import analyze_video  # noqa: PLC0415
            r = analyze_video(p)
            percentile = round(float((np.array(allv) < r["cut_visibility_v2"]).mean() * 100), 1)
            mine = {
                "path": str(p),
                "v2": r["cut_visibility_v2"],
                "frozen_rate": r["frozen_rate"],
                "n_cuts": r["n_cuts"],
                "percentile_vs_all": percentile,
                "vs_burn": {
                    "burn_mean": by_tier.get("burn", {}).get("v2_mean"),
                    "burn_p50": by_tier.get("burn", {}).get("v2_p50"),
                },
            }

    summary = {
        "created": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "n_videos": len(ok),
        "n_excluded_no_cuts": len(no_cut),
        "excluded_note": "MMD/纸片人单镜头长片，scene 检测无切点，不参与统计",
        "cut_visibility_v2": {
            "mean": round(float(np.mean(allv)), 4),
            "p25": pct(allv, 25), "p50": pct(allv, 50),
            "p75": pct(allv, 75), "p90": pct(allv, 90),
            "min": round(float(np.min(allv)), 4),
            "max": round(float(np.max(allv)), 4),
        },
        "frozen_rate": {
            "mean": round(float(np.mean(allf)), 4),
            "p50": pct(allf, 50), "p75": pct(allf, 75),
        },
        "by_tier": by_tier,
        "mine": mine,
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"参照集 v2 统计（n={len(ok)}，排除 {len(no_cut)} 部无切点片）")
    print(f"  全体: mean={summary['cut_visibility_v2']['mean']} "
          f"p50={summary['cut_visibility_v2']['p50']} "
          f"p75={summary['cut_visibility_v2']['p75']} "
          f"p90={summary['cut_visibility_v2']['p90']}")
    print(f"  冻结率: mean={summary['frozen_rate']['mean']} "
          f"p50={summary['frozen_rate']['p50']}")
    print("\n按风格分层:")
    print(f"  {'tier':<12}{'n':>4}{'v2均值':>10}{'p50':>9}{'冻结率':>10}")
    for t, e in sorted(by_tier.items(), key=lambda x: -x[1]["n"]):
        print(f"  {t:<12}{e['n']:>4}{e['v2_mean']:>10.4f}{e['v2_p50']:>9.4f}"
              f"{e['frozen_mean']:>10.4f}")
    if mine:
        print(f"\n本片: {Path(mine['path']).name}")
        print(f"  v2 = {mine['v2']} | 冻结率 = {mine['frozen_rate']} "
              f"| {mine['n_cuts']} 刀")
        print(f"  参照集排名分位: {mine['percentile_vs_all']}%")
        b = mine["vs_burn"]
        print(f"  vs burn 层: 均值 {b['burn_mean']} / p50 {b['burn_p50']}")
    print(f"\n→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
