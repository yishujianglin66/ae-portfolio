"""collect_color_samples.py — 色彩控制变量样本采集（CNN color_harmony 专用）

CNN color_harmony 失败的根因是采集时多参数混杂（粒子尺寸/色差/glow/文字
同时变, 色彩被稀释）。本脚本做控制变量: 固定其他参数, 只变色彩相关变量:
  1. chromatic_amount  色差幅度 (6/10/15/20/25)
  2. particle_color    粒子主色 (金/白/紫/蓝)
  3. bg_color          背景色 (深蓝/纯黑/暖棕)

→ 纯净色彩样本 → qwen 评分 color_harmony → 积累可靠色彩标签。

输出: output/m2_iteration/train_samples.jsonl 追加 (含 frame_dir)
用法: python scripts/collect_color_samples.py [--n 12]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.visual_scorer import score_video  # noqa: E402
from scripts.m2_auto_iterate import render_tree  # noqa: E402

OUT_DIR = PROJECT / "output" / "m2_iteration"
SAMPLES = OUT_DIR / "train_samples.jsonl"
FRAME_ROOT = PROJECT / "data" / "param_tuning" / "frames"
DUR = 2.0

# 色彩控制变量网格（tint 需 4 元素带 alpha, 2026-08-16: 3 元素被 AE 静默拒绝
# 导致粒子仍渲染原贴图色, 色彩样本无区分度）
CHROMATIC = [6, 10, 15, 20, 25]
PARTICLE_COLORS = {  # BGR→RGBA (黑→深色, 白→主色)
    "gold": {"tint_black": [0.28, 0.12, 0.05, 1.0], "tint_white": [1.0, 0.72, 0.15, 1.0]},
    "white": {"tint_black": [0.3, 0.3, 0.3, 1.0], "tint_white": [1.0, 1.0, 1.0, 1.0]},
    "purple": {"tint_black": [0.2, 0.05, 0.3, 1.0], "tint_white": [0.8, 0.3, 1.0, 1.0]},
    "cyan": {"tint_black": [0.05, 0.15, 0.3, 1.0], "tint_white": [0.2, 0.9, 1.0, 1.0]},
}
BG_COLORS = {
    "deepblue": [5, 5, 30],
    "black": [0, 0, 0],
    "warm": [20, 15, 10],
}


def build_color_tree(combo: dict):
    """色彩控制变量树: 固定粒子尺寸/文字/节奏, 只变色彩。"""
    from core.composition_tree import CompositionTree, LayerSpec
    pc = PARTICLE_COLORS[combo["pcolor"]]
    bg = BG_COLORS[combo["bg"]]
    tree = CompositionTree(
        comp_name="Edit_ColorCtrl", style_card="edit", duration=DUR,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG", z_index=0,
                      time_range=[0, DUR], content={"color": bg}),
            LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                      time_range=[0, DUR],
                      content={"template": "spark", "t_hit": 0.8,
                               "psize_scale": 0.8,          # 固定
                               "tint_black": pc["tint_black"],
                               "tint_white": pc["tint_white"],
                               "bg_color": list(bg)}),       # 粒子染色感知背景
            LayerSpec(id="title", type="text", name="Title", z_index=2,
                      time_range=[0.2, DUR - 0.2],
                      content={"text": "COLOR", "size": 150,   # 固定字号
                               "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                               "font": "auto",
                               "edit_fx": {"rgb_burst": {"max_amount": combo["chromatic"]}}}),
        ],
        beat_events=[{"time": 0.8, "beat_type": "kick", "layer_id": "title"}],
    )
    return tree


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="采集组合数")
    ap.add_argument("--seed", type=int, default=99)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 已采组合去重
    done = set()
    if SAMPLES.exists():
        for line in SAMPLES.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "pcolor" in r:
                    done.add((r["pcolor"], r["bg"], r["chromatic_amount"]))

    rng = random.Random(args.seed)
    combos = []
    seen = set(done)
    for _ in range(args.n * 4):
        c = {"chromatic": rng.choice(CHROMATIC),
             "pcolor": rng.choice(list(PARTICLE_COLORS)),
             "bg": rng.choice(list(BG_COLORS))}
        key = (c["pcolor"], c["bg"], c["chromatic"])
        if key not in seen:
            combos.append(c)
            seen.add(key)
        if len(combos) >= args.n:
            break
    if not combos:
        print("色彩组合已采完")
        return 0
    print(f"采集 {len(combos)} 色彩组合")

    t0 = time.time()
    n_ok = 0
    for i, combo in enumerate(combos):
        print(f"\n[{i+1}/{len(combos)}] 色差{combo['chromatic']} 粒子{combo['pcolor']} 背景{combo['bg']}")
        tree = build_color_tree(combo)
        out_mp4 = OUT_DIR / f"color_{i:03d}.mp4"
        if not render_tree(tree, str(out_mp4), f"color_{i:03d}.aep"):
            print("  渲染失败")
            continue
        score = score_video(str(out_mp4), n_frames=4)
        if score.get("error"):
            print(f"  评分失败: {score['error']}")
            out_mp4.unlink(missing_ok=True)
            continue
        # 帧留存
        frame_dir = FRAME_ROOT / f"color_{n_ok:03d}"
        frame_dir.mkdir(parents=True, exist_ok=True)
        cap = cv2.VideoCapture(str(out_mp4))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        for fi in range(min(4, max(total, 1))):
            gi = int(fi * (total - 1) / max(min(4, total) - 1, 1)) if total > 1 else 0
            cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
            ret, f = cap.read()
            if ret:
                cv2.imwrite(str(frame_dir / f"frame_{fi:02d}.jpg"), f)
        cap.release()
        # 落盘
        row = {
            "style": "edit", "chromatic_amount": combo["chromatic"],
            "pcolor": combo["pcolor"], "bg": combo["bg"],
            "psize_scale": 0.8,
            "score_color_harmony": score.get("scores", {}).get("color_harmony", 5),
            "score_overall": score.get("overall", 0),
            "frame_dir": str(frame_dir),
        }
        with open(SAMPLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_ok += 1
        out_mp4.unlink(missing_ok=True)
        print(f"  样本: color_harmony={row['score_color_harmony']} | "
              f"{time.time()-t0:.0f}s")

    print(f"\n完成: {n_ok}/{len(combos)} 色彩样本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
