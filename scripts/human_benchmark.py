"""human_benchmark.py — 人工作品质量标尺（10 套成品 vs 自动成片）

把 tutorials 的 10 套人工成品 .mp4 (每套含工程三件套, 人工卡点真值) 送进
评分器 (CNN 本地 + qwen), 建立"作品级质量标尺":
  - 人工成品分 vs 我们自动成片分 的差距 = 质量目标的量化
  - 分维度差距直接指出追赶方向 (dynamism 差多少/texture 差多少)

输出: output/m2_iteration/human_benchmark.json + 控制台对照表

用法:
  python scripts/human_benchmark.py [--scorer local]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.cnn_scorer import score_video_mode  # noqa: E402

TUTORIALS = Path(r"D:\AE-Work\resources\tutorials\AE教程10集")
OUT = PROJECT / "data" / "benchmarks" / "human_benchmark.json"
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]
# 自动成片代表 (我们当前最好输出)
OURS = [PROJECT / "output" / "grand_finale" / "finale.mp4"]   # 2026-08-17: round* 被计划清理, 换验收成片


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scorer", default="local", choices=["local", "hybrid", "qwen"])
    args = ap.parse_args()

    works = sorted(TUTORIALS.glob("*/成品.mp4"))
    print(f"人工成品 {len(works)} 部 | 评分器: {args.scorer}\n")

    rows = []
    for w in works:
        name = w.parent.name
        try:
            s = score_video_mode(str(w), args.scorer)
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: 评分失败 {e}")
            continue
        if s.get("error"):
            print(f"  {name}: {s['error'][:50]}")
            continue
        sc = {d: s["scores"].get(d, 0) for d in DIMS}
        rows.append({"work": name, "video": str(w), "scores": sc})
        print(f"  {name}: dyn={sc['score_dynamism']:.1f} tex={sc['score_texture']:.1f} "
              f"pac={sc['score_pacing']:.1f} ovr={sc['score_overall']:.1f}")

    if not rows:
        print("无成功评分")
        return 1

    # 人工均值
    avg = {d: sum(r["scores"][d] for r in rows) / len(rows) for d in DIMS}

    # 我们的自动成片
    ours_rows = []
    for v in OURS:
        if not v.exists():
            continue
        s = score_video_mode(str(v), args.scorer)
        if not s.get("error"):
            ours_rows.append({"work": v.name, "scores": {d: s["scores"].get(d, 0) for d in DIMS}})
    ours_avg = {d: sum(r["scores"][d] for r in ours_rows) / max(len(ours_rows), 1) for d in DIMS}

    print(f"\n=== 标尺对照 ({len(rows)} 人工 vs {len(ours_rows)} 自动) ===")
    print(f"{'维度':<16}{'人工均值':>8}{'自动均值':>8}{'差距':>8}")
    for d in DIMS:
        gap = ours_avg[d] - avg[d]
        print(f"{d.replace('score_', ''):<16}{avg[d]:>8.2f}{ours_avg[d]:>8.2f}{gap:>+8.2f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "human": rows, "human_avg": avg, "ours": ours_rows, "ours_avg": ours_avg,
        "scorer": args.scorer,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n落盘: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
