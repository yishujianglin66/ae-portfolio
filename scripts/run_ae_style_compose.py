"""M4 风格卡→合成→节拍→AE 真机链路（StyleTreeBuilder + BeatLock 集成）

用法:
  py -3.12 scripts/run_ae_style_compose.py [--card amv_highenergy]
      [--title "FINAL CLASH"] [--duration 8] [--intensity 1.0] [--dry]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, ".")
from core.ae_bridge_runner import BRIDGE, send_jsx_and_wait

from core.beatlock import BeatGrid, compose
from core.style_tree_builder import StyleTreeBuilder

AUDIOMAP = r"tmp/audiomap_52a283d2.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", default="amv_highenergy")
    ap.add_argument("--title", default="FINAL CLASH")
    ap.add_argument("--duration", type=float, default=8.0)
    ap.add_argument("--intensity", type=float, default=1.0)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    with open(AUDIOMAP, encoding="utf-8") as f:
        grid = BeatGrid.from_audiomap(json.load(f))
    print(f"[BeatGrid] kick={len(grid.kick)} strong={len(grid.strong)}")

    builder = StyleTreeBuilder()
    result = builder.build(args.card, {"title": args.title, "duration": args.duration},
                           grid=grid)
    tree = result.tree
    tree.comp_name = f"M4_Style_{args.card}"
    print(f"[StyleTree] style_id={result.style_id} base={result.base_template} "
          f"layers={len(tree.layers)} offline={result.offline}")
    for w in result.warnings[:6]:
        print(f"    [warn] {w}")
    for tr in result.trace[:6]:
        print(f"    [trace] {tr}")

    # 文字层起点拉满：避免节拍关键帧落在图层 inPoint 之前
    for layer in tree.layers:
        if layer.type == "text":
            layer.time_range[0] = 0.0

    merged, res = compose(tree, grid, fps=30, intensity=args.intensity)
    print(f"[BeatLock] anchors={len(res.anchors)} dropped={res.dropped} jsx={len(merged)} 字符")
    for a in res.anchors[:10]:
        print(f"    {a.time:6.2f}s {a.beat_type:9s} -> {a.action:6s} on {a.layer_id}")

    if args.dry:
        print("[dry] 仅生成，不执行真机")
        return 0

    rep = send_jsx_and_wait(merged, f"{BRIDGE}/_m4_style.txt", timeout=300)
    print("── AE 执行报告 ──")
    print(json.dumps(rep, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
