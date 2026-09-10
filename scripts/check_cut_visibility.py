# -*- coding: utf-8 -*-
"""check_cut_visibility.py — R1 切点可见性验收（v2 口径，2026-09-10）

为什么不用 v1（score_reference_gap 的 cut_visibility）：
  v1 用 `-ss t±1/24` 取帧，ffmpeg 在帧时间戳前 ~0.5ms 内会回退上一帧，
  实测 ±0.5ms 微扰即让 run61 在 0.3511 ↔ 1.1360 间跳变（3 倍波动），
  且官方只采样 12 点（全切点均值 0.6909 vs 采样值 0.8698）。
  证据：`03-阶段报\u544a/cut_visibility根因诊断报告_2026-09-09.md` §四。

v2 口径（确定性：连跑 3 次 1.0737/1.0737/1.0737，波动 0.000000）：
  帧号对齐 select=eq(n,fn) + 多帧对均值(fn-1 vs fn+1/+2/+3) + 全切点统计
  + ahash 冻结率（双指标并用，冻结率抓"切了但画面没变"）。

验收线：按风格分层（跨风格混算会失真——手书 0.2367 vs 燃向 0.8738）。
阈值取自参照集重算 n=137 的 tier p50（见报告 §6.3），run61 类燃向片
对标 seed/narrative/burn 层，默认 burn。

用法:
  python scripts/check_cut_visibility.py <video> [--tier burn]
  python scripts/check_cut_visibility.py <video> --json reports/r1_accept.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from scripts.cut_visibility_v2 import analyze_video, safe_video  # noqa: E402

# tier → (v2_min, frozen_max, p25_min)
# v2_min 取该层参照集 p50（达到即"达到同类中位以上"）；
# frozen_max=0.10：run61 实测 0.9%，参照集均值 38.6%，10% 是明显优于均值的线；
# p25_min=0.60：弱尾控制——四分之一的切点也不能塌到 0.6 以下。
TIER_THRESHOLDS = {
    "seed":      (0.95, 0.10, 0.60),
    "narrative": (0.92, 0.10, 0.60),
    "burn":      (0.88, 0.10, 0.60),
    "creator":   (0.78, 0.20, 0.50),
    "master_lens": (0.60, 0.30, 0.40),
    "amv":       (0.58, 0.30, 0.40),
    "creator_cn": (0.54, 0.30, 0.40),
    "puppet":    (0.40, 0.40, 0.30),
    "contest":   (0.40, 0.40, 0.30),
    "handdrawn": (0.24, 0.50, 0.20),
}
DEFAULT_TIER = "burn"
WARN_RATIO = 0.80  # v2 达线 80% 或冻结率翻倍内 → WARN 而非 FAIL


def judge(metrics: dict, tier: str = DEFAULT_TIER) -> dict:
    """按 v2 口径判定。metrics 需含 cut_visibility_v2 / frozen_rate / p25。"""
    v2_min, frozen_max, p25_min = TIER_THRESHOLDS.get(
        tier, TIER_THRESHOLDS[DEFAULT_TIER])
    v2 = float(metrics.get("cut_visibility_v2", 0.0) or 0.0)
    frozen = float(metrics.get("frozen_rate", 1.0) or 0.0)
    p25 = float(metrics.get("p25", 0.0) or 0.0)
    n_cuts = int(metrics.get("n_cuts", 0) or 0)

    if n_cuts == 0:
        return {"verdict": "SKIP", "tier": tier,
                "reason": "无切点（单镜头长片），不参与切点可见性验收",
                "thresholds": {"v2_min": v2_min, "frozen_max": frozen_max,
                               "p25_min": p25_min}}

    checks = {
        "v2": (v2 >= v2_min, f"v2={v2:.4f} ≥ {v2_min}"),
        "frozen_rate": (frozen <= frozen_max,
                        f"冻结率={frozen:.2%} ≤ {frozen_max:.0%}"),
        "p25": (p25 >= p25_min, f"p25={p25:.4f} ≥ {p25_min}"),
    }
    failed = [k for k, (ok, _) in checks.items() if not ok]

    if not failed:
        verdict = "PASS"
    elif (v2 >= v2_min * WARN_RATIO or frozen <= frozen_max * 2.0):
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "tier": tier,
        "n_cuts": n_cuts,
        "metrics": {"v2": round(v2, 4),
                    "frozen_rate": round(frozen, 4),
                    "p25": round(p25, 4),
                    "p50": round(float(metrics.get("p50", 0.0) or 0.0), 4),
                    "min": round(float(metrics.get("min", 0.0) or 0.0), 4)},
        "thresholds": {"v2_min": v2_min, "frozen_max": frozen_max,
                       "p25_min": p25_min},
        "failed_checks": failed,
        "checks": {k: {"ok": ok, "detail": d} for k, (ok, d) in checks.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="R1 切点可见性验收（v2 口径）")
    ap.add_argument("video", nargs="?", default=None)
    ap.add_argument("--tier", default=DEFAULT_TIER,
                    choices=sorted(TIER_THRESHOLDS))
    ap.add_argument("--thr", type=float, default=0.30,
                    help="场景检测阈值（与 v2 同口径）")
    ap.add_argument("--json", default=None, help="结果 JSON 落盘路径")
    args = ap.parse_args()

    if not args.video:
        ap.error("需要指定视频路径")

    path = safe_video(args.video)
    if path is None:
        print(f"[R1] 非法视频路径: {args.video}")
        return 2

    t0 = time.time()
    m = analyze_video(path, thr=args.thr)  # 冻结率恒算（freeze_hamming 默认 10）
    m["_elapsed_sec"] = round(time.time() - t0, 1)
    result = judge(m, args.tier)
    result["video"] = str(path)
    result["elapsed_sec"] = m["_elapsed_sec"]

    v = result["verdict"]
    print(f"[R1] 切点可见性验收: {v}  (tier={result['tier']}, "
          f"{m['_elapsed_sec']}s)")
    if v == "SKIP":
        print("     " + result["reason"])
    else:
        mm = result["metrics"]
        print(f"     v2={mm['v2']:.4f}  p25={mm['p25']:.4f}  "
              f"p50={mm['p50']:.4f}  min={mm['min']:.4f}  "
              f"冻结率={mm['frozen_rate']:.2%}  ({result['n_cuts']} 刀)")
        print(f"     阈值: v2≥{result['thresholds']['v2_min']}  "
              f"冻结率≤{result['thresholds']['frozen_max']:.0%}  "
              f"p25≥{result['thresholds']['p25_min']}")
        for k in result["failed_checks"]:
            print(f"     未达标: {result['checks'][k]['detail']}")

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"     → {out}")

    return 0 if v in ("PASS", "SKIP", "WARN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
