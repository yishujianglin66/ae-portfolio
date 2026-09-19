"""tier_gap_report.py — tier 匹配的渲染后自动差值报告 (2026-09-19)

解决的问题:
  Boss 连续四轮"不好看/还是不行", 全靠主观感觉。参照集 (data/reference_top, 145 部)
  已在手边, 但 score_reference_gap.py 要手动跑、且把全部 tier 混在一起取均值 ——
  燃向片跟手书/剧情向比"强段占比"会得出"太吵"的错误结论。

做法:
  ① 按 manifest 的 tier 过滤参照集 (默认 burn+amv = 燃向/混剪同类)
  ② 复用 score_reference_gap 的 collect() 逐部跑 12 维指标
  ③ 本片 vs 同 tier 参照: 输出逐维差值 + 与上次报告的变化
  ④ 结果落盘 reports/tier_gap_<ver>.json, 供对比追踪

用法:
  python scripts/tier_gap_report.py --mine <成片.mp4> [--tiers burn amv] [--tag v52]
  python scripts/tier_gap_report.py --mine <成片.mp4> --tiers burn --tag v52 --max-refs 10
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))
sys.path.insert(0, str(PROJ / "scripts"))

REF_DIR = PROJ / "data" / "reference_top"
MANIFEST = REF_DIR / "_manifest.json"
REPORT_DIR = PROJ / "reports"

# 12 维: 6 信号 + 7 语义 (score_reference_gap 口径)
SIGNAL_KEYS = ["peak", "hf_energy", "onset_density", "cut_rate", "beat_hit_rate", "cut_visibility"]
SEMANTIC_KEYS = ["score_dynamism", "score_composition", "score_color_harmony",
                 "score_text_read", "score_texture", "score_pacing", "score_overall"]
# 方向: True=越高越好
DIRECTION = {
    "peak": False, "hf_energy": True, "onset_density": True, "cut_rate": True,
    "beat_hit_rate": True, "cut_visibility": True,
    **{k: True for k in SEMANTIC_KEYS},
}


def load_tier_refs(tiers: list[str], max_refs: int = 0) -> list[Path]:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = [REF_DIR / it["file"] for it in (m.get("items") or [])
             if it.get("tier") in tiers and (REF_DIR / it["file"]).exists()]
    if max_refs and len(files) > max_refs:
        files = files[:max_refs]
    return files


def score_one(path: Path) -> dict | None:
    from score_reference_gap import collect
    try:
        return collect(str(path), 0.30)
    except Exception as e:
        print(f"    [跳过] {path.name[:30]}: {type(e).__name__}")
        return None


def summarize(refs_data: list[dict]) -> dict:
    """参照集逐维: 中位 + p25-p75"""
    out = {}
    for key in SIGNAL_KEYS + SEMANTIC_KEYS:
        vals = []
        for d in refs_data:
            v = (d.get("signal") or {}).get(key)
            if v is None:
                v = (d.get("semantic") or {}).get(key)
            if v is not None and isinstance(v, (int, float)):
                vals.append(float(v))
        if vals:
            out[key] = {
                "median": round(float(np.median(vals)), 4),
                "p25": round(float(np.percentile(vals, 25)), 4),
                "p75": round(float(np.percentile(vals, 75)), 4),
                "n": len(vals),
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="tier_gap_report.py")
    ap.add_argument("--mine", required=True, help="本片成片路径")
    ap.add_argument("--tiers", nargs="+", default=["burn", "amv"],
                    help="参照集 tier 过滤 (默认 burn+amv = 燃向/混剪)")
    ap.add_argument("--tag", default=None, help="版本标签 (用于报告文件名与对比)")
    ap.add_argument("--max-refs", type=int, default=0, help="最多跑多少部参照 (0=全部)")
    ap.add_argument("--prev", default=None, help="上一版报告路径 (自动对比)")
    args = ap.parse_args()

    mine = Path(args.mine)
    if not mine.exists():
        print(f"[ERR] 本片不存在: {mine}")
        return 1

    refs = load_tier_refs(args.tiers, args.max_refs)
    if not refs:
        print(f"[ERR] tier={args.tiers} 无可用参照")
        return 1
    print(f"[tier_gap] tier={'+'.join(args.tiers)} 参照 {len(refs)} 部, 本片 {mine.name}")

    # 1) 跑参照集
    t0 = time.time()
    refs_data = []
    for p in refs:
        d = score_one(p)
        if d:
            refs_data.append(d)
    if not refs_data:
        print("[ERR] 参照集全部失败")
        return 2
    ref_summary = summarize(refs_data)
    print(f"[tier_gap] 参照分析完成 ({len(refs_data)} 部, {time.time()-t0:.0f}s)")

    # 2) 跑本片
    mine_data = score_one(mine)
    if not mine_data:
        print("[ERR] 本片分析失败")
        return 2

    # 3) 逐维差值
    print("\n" + "=" * 78)
    print(f"{'维度':<20} {'本片':>8} {'参照中位':>9} {'差值':>8} {'参照p25-p75':>14} 判读")
    print("-" * 78)
    deltas = {}
    for key in SIGNAL_KEYS + SEMANTIC_KEYS:
        my_v = (mine_data.get("signal") or {}).get(key) or (mine_data.get("semantic") or {}).get(key)
        ref = ref_summary.get(key)
        if my_v is None or ref is None:
            continue
        med = ref["median"]
        delta = round(float(my_v) - med, 4)
        # 归一化差值: 相对于参照的四分位距
        iqr = max(ref["p75"] - ref["p25"], 1e-6)
        z = round(delta / iqr, 2)
        deltas[key] = {"mine": round(float(my_v), 4), "ref_median": med,
                       "delta": delta, "z_vs_iqr": z,
                       "ref_p25": ref["p25"], "ref_p75": ref["p75"]}
        # 判读
        direction = DIRECTION.get(key, True)
        if direction:
            status = "优于参照" if z > 0.5 else ("持平" if abs(z) <= 0.5 else "低于参照")
        else:
            status = "优于参照" if z < -0.5 else ("持平" if abs(z) <= 0.5 else "高于参照(此维越低越好)")
        p_range = f"{ref['p25']:.3f}-{ref['p75']:.3f}"
        print(f"  {key:<20} {my_v:>8.4f} {med:>9.4f} {delta:>+8.4f} "
              f"{p_range:>14}  {status}")
    print("=" * 78)

    # 4) 与上一版对比
    prev_data = None
    prev_path = Path(args.prev) if args.prev else None
    if not prev_path and args.tag:
        # 自动找最近的上一版
        existing = sorted(REPORT_DIR.glob("tier_gap_*.json"))
        if existing:
            prev_path = existing[-1]
    if prev_path and prev_path.exists():
        try:
            prev_data = json.loads(prev_path.read_text(encoding="utf-8"))
            print(f"\n[对比] vs {prev_path.name}:")
            print(f"  {'维度':<20} {'上版':>8} {'本版':>8} {'变化':>8}")
            prev_deltas = prev_data.get("deltas") or {}
            for key in deltas:
                pv = prev_deltas.get(key, {}).get("mine")
                cv = deltas[key]["mine"]
                if pv is not None:
                    ch = cv - pv
                    print(f"  {key:<20} {pv:>8.4f} {cv:>8.4f} {ch:>+8.4f}")
        except Exception as e:
            print(f"  [对比失败] {e}")

    # 5) 落盘
    REPORT_DIR.mkdir(exist_ok=True)
    tag = args.tag or mine.stem
    out = REPORT_DIR / f"tier_gap_{tag}.json"
    out.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mine": str(mine),
        "tiers": args.tiers,
        "n_refs_scored": len(refs_data),
        "ref_summary": ref_summary,
        "mine_data": mine_data,
        "deltas": deltas,
        "prev_report": str(prev_path) if prev_path else None,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[tier_gap] 报告: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
