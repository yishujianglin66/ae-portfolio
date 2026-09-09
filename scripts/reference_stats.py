# -*- coding: utf-8 -*-
"""reference_stats.py — 参照集逐部指标 + 分位数统计（2026-09-08）

解决的问题：
  1. score_reference_gap.py 只输出均值/最小/最大，**没有分位数**——评估报告引用的
     "参照前三分位 0.8193" 在磁盘上无产出物支撑，证据链不闭合；
  2. 串行跑 60 部参照视频太慢（每部一次全片 ffmpeg 场景检测）。

做法：复用 score_reference_gap 的指标函数，多进程并行逐部计算，结果落盘缓存
（二次运行直接复用），最后输出逐部表 + 分位数 + 与本片的对比。

用法:
  python scripts/reference_stats.py --refs data/reference_top --mine output/unified_run61/polish/master_hr.mp4
  python scripts/reference_stats.py --refs data/reference_top --workers 6 --no-cache
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))

from score_reference_gap import (  # noqa: E402
    SIGNAL_DIR, SEMANTIC_DIMS, _scene_cuts, _signal, _semantic,
)

CACHE = PROJ / "reports" / "ref_metrics_cache.json"


def metrics_for(path_str: str, thr: float, with_semantic: bool) -> dict:
    """单部视频的全部指标（供子进程调用）。"""
    p = Path(path_str)
    try:
        cuts = _scene_cuts(p, thr)
        sig = _signal(p, cuts)
    except Exception as e:  # 单部失败不拖垮整批
        return {"file": p.name, "error": f"{type(e).__name__}: {e}"}
    sem = {}
    if with_semantic:
        sem = _semantic(p) or {}
    return {"file": p.name, "path": str(p), "signal": sig, "semantic": sem}


def pct(vals: list[float], q: float) -> float | None:
    return round(float(np.percentile(vals, q)), 4) if vals else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", required=True, help="参照视频目录或文件列表")
    ap.add_argument("--mine", default=None, help="可选：要对比的本片")
    ap.add_argument("--thr", type=float, default=0.30)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--with-semantic", action="store_true",
                    help="同时跑语义 7 维（需 open_clip，较慢）")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="reports/reference_stats.json")
    args = ap.parse_args()

    refs: list[Path] = []
    for p in [args.refs]:
        pp = Path(p)
        if pp.is_dir():
            refs += sorted(pp.glob("*.mp4"))
        elif pp.exists():
            refs.append(pp)
    if not refs:
        print("无有效参照视频")
        return 1

    cache: dict = {}
    if CACHE.exists() and not args.no_cache:
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    cache.setdefault("signal", {})

    todo = [r for r in refs if r.name not in cache["signal"]]
    print(f"参照 {len(refs)} 部 | 缓存命中 {len(refs) - len(todo)} | 待算 {len(todo)} "
          f"| workers={args.workers}")

    if todo:
        t0 = time.time()
        done = 0
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(metrics_for, str(r), args.thr, args.with_semantic): r
                    for r in todo}
            for fut in as_completed(futs):
                res = fut.result()
                done += 1
                if "error" in res:
                    print(f"  [{done}/{len(todo)}] FAIL {res['file'][:44]}: {res['error'][:80]}")
                    continue
                cache["signal"][res["file"]] = res
                if res.get("semantic"):
                    cache.setdefault("semantic", {})[res["file"]] = res["semantic"]
                if done % 10 == 0 or done == len(todo):
                    print(f"  [{done}/{len(todo)}] 已算 {time.time() - t0:.0f}s", flush=True)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print(f"缓存已写: {CACHE}（{len(cache['signal'])} 部）")

    ok = [v for v in cache["signal"].values() if "signal" in v]
    print(f"\n有效样本: {len(ok)} 部")

    # 逐部分位数
    print("\n信号指标分位数（n={}）:".format(len(ok)))
    print(f"  {'指标':<16}{'均值':>9}{'p25':>9}{'p50':>9}{'p75':>9}{'p90':>9}{'min':>9}{'max':>9}")
    stats = {}
    for k, better in SIGNAL_DIR.items():
        vals = [d["signal"][k] for d in ok if d["signal"].get(k) is not None]
        stats[k] = {
            "mean": round(float(np.mean(vals)), 4),
            "p25": pct(vals, 25), "p50": pct(vals, 50),
            "p75": pct(vals, 75), "p90": pct(vals, 90),
            "min": round(float(np.min(vals)), 4), "max": round(float(np.max(vals)), 4),
            "better": better, "n": len(vals),
        }
        s = stats[k]
        print(f"  {k:<16}{s['mean']:>9}{s['p25']:>9}{s['p50']:>9}"
              f"{s['p75']:>9}{s['p90']:>9}{s['min']:>9}{s['max']:>9}")

    # 与本片对比
    mine = None
    if args.mine and Path(args.mine).exists():
        mine = metrics_for(args.mine, args.thr, args.with_semantic)
        if "error" not in mine:
            print(f"\n本片 vs 参照分布（{Path(args.mine).name}）:")
            print(f"  {'指标':<16}{'本片':>9}{'均值':>9}{'p75':>9}{'判定':>12}")
            for k in SIGNAL_DIR:
                mv = mine["signal"][k]
                s = stats[k]
                if s["better"]:
                    verdict = "超 p75" if mv > s["p75"] else (
                        "超均值" if mv > s["mean"] else "低于均值")
                else:
                    verdict = "优于均值" if mv < s["mean"] else "劣于均值"
                print(f"  {k:<16}{mv:>9}{s['mean']:>9}{s['p75']:>9}{verdict:>12}")

    # 按风格分层统计——跨风格混算均值会失真（木偶/手书的 cut_visibility 天然远低于燃向）
    tier_stats: dict[str, dict] = {}
    manifest = PROJ / "data" / "reference_top" / "_manifest.json"
    if manifest.exists():
        try:
            tier_of = {i["file"]: i["tier"]
                       for i in json.loads(manifest.read_text(encoding="utf-8"))["items"]}
            groups: dict[str, list] = {}
            for fname, v in cache["signal"].items():
                if "signal" not in v:
                    continue
                groups.setdefault(tier_of.get(fname, "unknown"), []).append(v["signal"])
            print("\n按风格分层（均值）:")
            print(f"  {'tier':<12}{'n':>4}{'beat_hit':>10}{'cut_vis':>10}{'cut_rate':>10}{'hf':>9}")
            for t, rows in sorted(groups.items(), key=lambda x: -len(x[1])):
                n = len(rows)
                entry = {
                    "n": n,
                    "beat_hit_rate": round(float(np.mean([r["beat_hit_rate"] for r in rows])), 4),
                    "cut_visibility": round(float(np.mean([r["cut_visibility"] for r in rows])), 4),
                    "cut_rate": round(float(np.mean([r["cut_rate"] for r in rows])), 4),
                    "hf_energy": round(float(np.mean([r["hf_energy"] for r in rows])), 1),
                }
                tier_stats[t] = entry
                print(f"  {t:<12}{n:>4}{entry['beat_hit_rate']:>10.4f}"
                      f"{entry['cut_visibility']:>10.4f}{entry['cut_rate']:>10.3f}"
                      f"{entry['hf_energy']:>9.1f}")
        except Exception as e:
            print(f"  [分层统计跳过] {e}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_refs": len(ok),
        "percentiles": stats,
        "by_tier": tier_stats,
        "mine": mine,
        "per_ref": {k: v["signal"] for k, v in cache["signal"].items()
                    if "signal" in v},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
