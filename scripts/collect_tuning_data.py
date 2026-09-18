"""collect_tuning_data.py — 调参器批量数据采集（参数网格采样）

目标: 为 M2g 调参器积累多样化的 (参数, 评分) 训练样本。
核心: 主动探索参数空间（网格/随机采样）而非 AI 单方向迭代——
  多样化的样本比同质样本有用得多（AI 迭代只会朝一个方向走）。

策略:
  1. 参数网格: psize_scale / chromatic_amount / punch_amount / glow 等
     关键参数取多档值, 随机组合采样（避免全遍历组合爆炸）
  2. 短段渲染: 2 秒合成（评分只需节拍窗口, 比 5 秒快 2.5x）
  3. 每组合: 改参数 → 渲染 → qwen 评分 → 落盘 train_samples.jsonl

用法:
  python scripts/collect_tuning_data.py [--n 20] [--seed 42]

输出: output/m2_iteration/train_samples.jsonl（追加, 每行 {参数特征, 评分标签}）
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.visual_scorer import _CACHE_DIR, score_video  # noqa: E402
from scripts.m2_auto_iterate import _param_snapshot, render_tree  # noqa: E402

OUT_DIR = PROJECT / "output" / "m2_iteration"
SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"  # 2026-08-17 迁 data/: 计划清理只扫 output
FRAME_ROOT = PROJECT / "data" / "param_tuning" / "frames"   # CNN 深度调参器帧库
DUR = 2.0  # 短段: 评分只需节拍窗口

# 关键参数网格（每档真实落树, 采样多样参数空间）
GRID = {
    "psize_scale": [0.6, 0.8, 1.0, 1.3, 1.6],          # 粒子尺寸倍率
    "chromatic_amount": [6, 10, 15, 20, 25],            # 色差幅度
    "punch_amount": [6, 10, 14],                        # 推拉力度
    "shake_amp": [8, 14, 20],                           # 抖动幅度
    "glow_mult": [0.6, 1.0, 1.5],                       # Glow 强度倍率
    "text_size": [120, 170, 220],                       # 主标题字号
    "lut_theme": ["none", "好莱坞 _ Hollywood", "复古电影 _ Vintage Film",
                  "冷色调 _ Cool_Look", "夏日光辉 _ Summer Glow",
                  "创意 _ Creative", "寂静 _ Silence"],   # LUT 风格主题 (none=不挂)
    "lut_strength": [0.4, 0.7, 1.0],                   # LUT 混合强度
}


def pick_lut(rng, theme: str = None) -> dict:
    """从采样池选 LUT, 返回渲染层 lut dict + 样本记录字段。

    theme: 指定主题 (来自 combo.lut_theme); 缺省随机选非 none 主题。
    """
    from core.lut_pipeline import load_sampling, lut_md5
    theme = theme or rng.choice([t for t in GRID["lut_theme"] if t != "none"])
    pool = load_sampling().get(theme, [])
    if not pool:
        return {"cube": None, "theme": theme}
    cube = rng.choice(pool)
    return {"cube": cube, "theme": theme, "md5": lut_md5(cube)}


def build_tree_with_params(combo: dict):
    """按参数组合构建合成树（短段 2s）。"""
    from core.composition_tree import CompositionTree, EffectRef, LayerSpec
    FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
    tree = CompositionTree(
        comp_name="Edit_Tuning", style_card="edit", duration=DUR,
        layers=[
            LayerSpec(id="clip", type="footage", name="FATE", z_index=0,
                      time_range=[0, DUR],
                      content={"path": str(PROJECT / FOOTAGE), "matting_mode": "rgba",
                               "fit": "cover", "source_dur": 16.37,
                               "edit_fx": {"punch": {"amount": combo["punch_amount"]},
                                           "shake": {"amp": combo["shake_amp"]}}}),
            LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                      time_range=[0, DUR],
                      content={"template": "spark", "t_hit": 0.8,
                               "psize_scale": combo["psize_scale"],
                               "_glow_mult": combo["glow_mult"],
                               "_pps_mult": 1.0}),
            LayerSpec(id="title", type="text", name="Title", z_index=2,
                      time_range=[0.2, DUR - 0.2],
                      content={"text": "CLASH", "size": combo["text_size"],
                               "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                               "font": "auto",
                               "edit_fx": {"punch": {"amount": combo["punch_amount"]},
                                           "rgb_burst": {"max_amount": combo["chromatic_amount"]}}}),
            LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                      time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 9}),
        ],
        beat_events=[{"time": 0.8, "beat_type": "kick", "layer_id": "title"}],
    )
    return tree


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20, help="采样组合数")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # 已采集组合去重
    done_keys = set()
    if SAMPLES.exists():
        for line in SAMPLES.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done_keys.add(tuple(sorted((k, r[k]) for k in GRID if k in r)))

    rng = random.Random(args.seed)
    # 随机采样网格（避免全遍历组合爆炸）
    all_combos = []
    keys = list(GRID)
    for _ in range(args.n * 3):
        combo = {k: rng.choice(GRID[k]) for k in keys}
        ck = tuple(sorted(combo.items()))
        if ck not in done_keys:
            all_combos.append(combo)
            done_keys.add(ck)
        if len(all_combos) >= args.n:
            break

    if not all_combos:
        print("所有采样组合已采集过, 调整 GRID 或 n")
        return 0
    print(f"本次采样 {len(all_combos)} 组合 (已有 {len(done_keys) - len(all_combos)} 去重)")

    t0 = time.time()
    n_ok = 0
    run_id = time.strftime("%H%M%S")  # 唯一运行 ID, 防帧目录/成片跨运行覆盖
    for i, combo in enumerate(all_combos):
        print(f"\n=== [{i+1}/{len(all_combos)}] combo={combo}")
        tree = build_tree_with_params(combo)
        tag = f"t{run_id}_{i:03d}"
        # LUT 选择 (theme != none 时从采样池抽 cube; 帧内容哈希防路径移动错位)
        lut_render = None
        if combo.get("lut_theme", "none") != "none":
            sel = pick_lut(rng, theme=combo["lut_theme"])
            if sel.get("cube"):
                lut_render = {"cube": sel["cube"],
                              "strength": float(combo.get("lut_strength", 1.0))}
                combo["lut_file"] = sel["cube"]
                combo["lut_md5"] = sel.get("md5", "")
                print(f"  LUT: {sel['theme']} | strength={lut_render['strength']}")
        # 短段渲染 (唯一文件名, 防 avi 句柄泄漏后固定名冲突)
        out_mp4 = OUT_DIR / f"{tag}.mp4"
        if not render_tree(tree, str(out_mp4), f"tune_{i:03d}.aep", lut=lut_render):
            print("  渲染失败, 跳过")
            continue
        # 评分（节拍窗口时序评分 + 全帧）
        score = score_video(str(out_mp4), n_frames=4)
        if score.get("error"):
            print(f"  评分失败: {score['error']}")
            out_mp4.unlink(missing_ok=True)
            continue
        # 帧留存（CNN 深度调参器地基, 2026-08-16）:
        # 渲染帧是未来"帧→评分"训练的唯一输入, 此前被丢弃 = 数据断流
        # 2026-08-16 修复: sample_{n_ok} 跨运行 n_ok 重置 → 目录被覆盖写,
        #   48 样本共享 6 帧目录 → 帧↔参数错位。改含 run_id 的唯一命名 + 存在断言。
        frame_dir = FRAME_ROOT / f"{run_id}_{n_ok:03d}"
        if frame_dir.exists():
            raise RuntimeError(f"帧目录已存在 {frame_dir} — run_id 冲突, 中止防错位")
        frame_dir.mkdir(parents=True, exist_ok=True)
        import cv2 as _cv2
        _cap = _cv2.VideoCapture(str(out_mp4))
        _total = int(_cap.get(_cv2.CAP_PROP_FRAME_COUNT))
        _n = min(4, max(_total, 1))
        for _fi in range(_n):
            _gi = int(_fi * (_total - 1) / max(_n - 1, 1)) if _total > 1 else 0
            _cap.set(_cv2.CAP_PROP_POS_FRAMES, _gi)
            _ret, _f = _cap.read()
            if _ret:
                _cv2.imwrite(str(frame_dir / f"frame_{_fi:02d}.jpg"), _f,
                             [_cv2.IMWRITE_JPEG_QUALITY, 85])
        _cap.release()
        # 落盘: 参数特征 + 评分标签 + 帧目录 (+ LUT 记录, 数据卫生: 文件级字段进样本行)
        row = _param_snapshot(tree)
        row.update({f"score_{k}": v for k, v in score.get("scores", {}).items()})
        row["score_overall"] = score.get("overall", 0)
        row["frame_dir"] = str(frame_dir)
        for lk in ("lut_theme", "lut_strength", "lut_file", "lut_md5"):
            if lk in combo:
                row[lk] = combo[lk]
        with open(SAMPLES, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        n_ok += 1
        # 清理短段成片（帧已留存, 只留样本数据）
        out_mp4.unlink(missing_ok=True)
        print(f"  样本落盘: overall={row['score_overall']} | "
              f"{time.time()-t0:.0f}s 累计")

    print(f"\n完成: {n_ok}/{len(all_combos)} 样本 → {SAMPLES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
