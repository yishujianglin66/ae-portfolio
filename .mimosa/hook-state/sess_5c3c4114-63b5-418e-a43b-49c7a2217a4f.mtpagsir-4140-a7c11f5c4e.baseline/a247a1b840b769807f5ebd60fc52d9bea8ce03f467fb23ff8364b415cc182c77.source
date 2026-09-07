"""校准黄金候选 → gold_set.jsonl（签名匹配版, 防排序漂移错位）

2026-08-16 事故: 重筛(新 CNN 头/新样本池)改变 info_score 排名, 但黄金标签按
排名 id 绑定 → 标签贴到错误样本。修复: 标签按稳定签名匹配 —
  (params 六元组 + qwen 七维分数) 在 train_samples.jsonl 中唯一定位样本,
  与排名无关。qwen 分数参与匹配以区分重复参数组合。

用法:
  python scripts/calibrate_gold_set.py
  直接从 train_samples.jsonl + 当前模型预测重建 gold_set.jsonl (50 条)
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
EMB = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
CNN_HEAD = PROJECT / "models" / "output" / "cnn_param_head.pkl"
GBDT_TUNER = PROJECT / "models" / "output" / "param_tuner.pkl"
GOLD_SET = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"

DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]
PK = ["psize_scale", "punch_amount", "shake_amp", "chromatic_amount", "text_size", "_glow_mult"]

# 签名: (ps, pn, sh, ch, ts, gl) → (7维黄金标签, qwen七维, 校准依据)
GOLD = {
    # ── 第一批 (2026-08-16 首轮) ──
    (0.6, 6, 20, 25, 170, 1.0): ([8.0, 7.0, 6.5, 8.8, 5.0, 7.8, 7.2],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.5),
        "psize0.6+shake20 强动态 → dyn 8.0 (qwen 8.5 天花板偏置); chroma25 色差 → col 6.5/tex 5.0"),
    (0.6, 6, 8, 25, 170, 1.5): ([7.8, 7.0, 6.5, 8.8, 5.0, 7.5, 7.1],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.5),
        "shake8 弱抖动 → dyn 7.8 (非 qwen 8.5)"),
    (0.6, 14, 20, 25, 170, 1.0): ([8.2, 7.0, 6.5, 8.8, 5.0, 7.8, 7.3],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.3),
        "punch14+shake20 双强动态 → dyn 8.2"),
    (0.6, 6, 8, 6, 170, 0.6): ([7.8, 7.0, 6.8, 8.8, 5.3, 7.5, 7.2],
        (8.5, 7.0, 6.8, 9.0, 5.5, 7.8, 7.3),
        "chroma6 低色差 → col 6.8/tex 5.3; shake8 → dyn 7.8"),
    (0.6, 6, 20, 15, 120, 1.0): ([8.0, 7.0, 6.8, 8.5, 5.5, 7.5, 7.2],
        (8.5, 7.0, 6.8, 9.0, 6.0, 7.5, 7.3),
        "txt120 小字 → text_read 8.5 (qwen 9.0 偏高); chroma15 适中 → tex 5.5"),
    (0.6, 6, 20, 15, 170, 1.5): ([8.0, 7.0, 6.5, 8.8, 5.0, 7.8, 7.2],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.3),
        "glow1.5 强光晕 → tex 不升 (层次被光晕融合)"),
    (0.6, 14, 20, 15, 120, 1.5): ([8.2, 7.0, 6.5, 8.5, 5.0, 7.8, 7.2],
        (8.5, 7.0, 6.5, 9.0, 5.0, 7.5, 7.3),
        "punch14+shake20 → dyn 8.2; txt120 → text_read 8.5"),
    (0.6, 14, 14, 20, 170, 0.6): ([8.0, 7.0, 6.5, 8.8, 5.0, 7.8, 7.2],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.3),
        "punch14+shake14 → dyn 8.0; chroma20 → col 6.5/tex 5.0"),
    (0.6, 10, 14, 6, 120, 1.5): ([7.8, 7.0, 6.8, 8.5, 5.3, 7.5, 7.1],
        (8.5, 7.0, 6.5, 9.0, 5.0, 8.0, 7.3),
        "chroma6 → col 6.8/tex 5.3; punch10 中等 → dyn 7.8"),
    (0.8, 6, 20, 25, 220, 1.5): ([7.8, 6.9, 6.3, 8.3, 4.8, 7.5, 7.0],
        (8.5, 7.0, 6.5, 8.0, 5.0, 7.5, 7.2),
        "psize0.8 + chroma25 + glow1.5 → tex 4.8; txt220 大字 → text_read 8.3"),
    (0.6, 14, 20, 25, 120, 1.0): ([8.0, 7.0, 6.5, 8.2, 5.0, 7.8, 7.1],
        (7.5, 6.8, 7.0, 8.2, 5.9, 7.3, 7.1),
        "punch14+shake20+chroma25 → dyn 8.0/col 6.5; txt120 → text_read 8.2"),
    (0.6, 6, 8, 20, 170, 1.5): ([7.8, 7.0, 6.5, 8.5, 5.0, 7.5, 7.1],
        (8.5, 7.0, 6.5, 8.0, 5.0, 7.5, 7.3),
        "shake8+glow1.5 → dyn 7.8; chroma20 → col 6.5/tex 5.0"),
    (1.3, 6, 8, 25, 170, 1.5): ([7.2, 6.6, 6.8, 8.3, 5.3, 7.0, 6.9],
        (7.5, 6.8, 7.0, 8.5, 6.0, 7.2, 7.1),
        "psize1.3 大粒子 → dyn 7.2/cmp 6.6 (edge 最低遮挡); tex 5.3 (qwen 6.0 偏高)"),
    (1.6, 14, 8, 25, 120, 1.5): ([6.5, 6.0, 6.8, 8.0, 4.3, 6.3, 6.2],
        (6.5, 5.8, 7.0, 8.2, 4.3, 6.0, 6.1),
        "psize1.6 最大粒子 → dyn 6.5/cmp 6.0/tex 4.3 (遮挡最重, qwen 与客观一致)"),
    (1.0, 14, 14, 6, 220, 0.6): ([7.5, 6.8, 7.0, 8.5, 5.0, 7.3, 7.0],
        (7.5, 6.8, 7.0, 8.5, 5.0, 7.3, 7.1),
        "psize1.0 + chroma6 → col 7.0; punch14 → dyn 7.5; txt220 → text_read 8.5"),
    (1.0, 14, 20, 25, 220, 1.0): ([7.5, 6.8, 6.3, 8.3, 4.8, 7.3, 6.8],
        (7.5, 6.8, 6.2, 8.0, 4.5, 7.0, 6.7),
        "psize1.0 + chroma25 → col 6.3/tex 4.8 (色差糊)"),
    (0.6, 6, 14, 15, 170, 0.6): ([7.8, 7.0, 7.0, 8.5, 5.2, 7.3, 7.1],
        (7.5, 6.8, 7.0, 8.5, 5.0, 7.3, 7.1),
        "chroma15 → col 7.0; glow0.6 弱光晕 → tex 5.2 (细节保留); shake14 → dyn 7.8"),
    (1.0, 14, 8, 10, 170, 1.0): ([7.3, 6.8, 7.0, 8.5, 5.0, 7.2, 6.9],
        (7.5, 6.8, 7.0, 8.5, 5.0, 7.2, 7.1),
        "chroma10 → col 7.0; shake8 弱抖动 → dyn 7.3"),
    (1.0, 6, 20, 20, 220, 1.5): ([7.5, 6.8, 6.5, 8.3, 4.8, 7.5, 7.0],
        (7.5, 6.8, 7.0, 8.5, 5.0, 7.2, 7.1),
        "chroma20 + glow1.5 → col 6.5/tex 4.8; txt220 → text_read 8.3"),
    (1.6, 6, 14, 6, 170, 0.6): ([6.5, 6.0, 7.0, 8.2, 4.3, 6.5, 6.3],
        (6.5, 5.8, 7.0, 8.2, 4.3, 6.7, 6.2),
        "psize1.6 → dyn 6.5/cmp 6.0/tex 4.3 (edge 最低); chroma6 → col 7.0"),
    # ── 第二批 (增量扩集) ──
    (0.8, 10, 20, 15, 120, 1.5): ([7.5, 6.8, 6.6, 8.2, 5.3, 7.3, 7.0],
        (7.5, 6.8, 7.0, 8.5, 6.0, 7.3, 7.2),
        "psize0.8+shake20 → dyn 7.5; chroma15+glow1.5 → tex 5.3 (qwen 6.0 高)"),
    (1.3, 14, 8, 25, 170, 1.0): ([7.0, 6.6, 6.3, 8.3, 5.0, 7.0, 6.8],
        (6.5, 7.0, 6.8, 8.0, 5.5, 7.2, 6.9),
        "psize1.3+punch14 → dyn 7.0; chroma25 → col 6.3 (qwen cmp 7.0 高, 遮挡重)"),
    (1.6, 14, 14, 25, 120, 0.6): ([6.5, 6.0, 6.5, 8.0, 4.3, 6.5, 6.3],
        (6.5, 5.8, 7.0, 8.0, 4.2, 6.3, 6.1),
        "psize1.6+chroma25 → 遮挡最重; col 6.5 (色差大)"),
    (0.8, 14, 14, 20, 120, 1.0): ([7.5, 6.8, 6.5, 8.2, 5.0, 7.3, 7.0],
        (7.5, 6.8, 7.0, 8.5, 6.0, 7.2, 7.1),
        "psize0.8+punch14+shake14 → dyn 7.5; chroma20 → col 6.5/tex 5.0 (qwen tex 6.0 高)"),
    (0.8, 10, 14, 6, 220, 1.0): ([7.5, 6.8, 6.8, 8.2, 5.3, 7.2, 7.0],
        (7.5, 6.8, 7.0, 8.2, 5.9, 7.3, 7.1),
        "chroma6 → col 6.8/tex 5.3 (qwen tex 5.9 高); txt220 → text_read 8.2"),
    (1.6, 14, 14, 25, 220, 1.0): ([6.5, 6.0, 6.3, 8.2, 4.3, 6.3, 6.3],
        (6.5, 5.8, 7.0, 8.2, 4.3, 6.0, 6.2),
        "psize1.6+chroma25 → dyn 6.5/cmp 6.0/tex 4.3; col 6.3"),
    (0.8, 14, 20, 25, 220, 1.0): ([7.8, 6.8, 6.3, 8.3, 4.8, 7.5, 7.0],
        (6.5, 7.0, 6.0, 8.5, 5.0, 7.0, 6.8),
        "psize0.8+punch14+shake20 → dyn 7.8 (qwen 6.5 明显偏低, 0.8 粒子不抢画面)"),
    (1.3, 6, 8, 15, 170, 1.0): ([7.0, 6.6, 6.6, 8.3, 5.0, 7.0, 6.8],
        (6.5, 7.0, 6.0, 8.5, 4.0, 6.0, 6.3),
        "psize1.3+弱抖 → dyn 7.0 (qwen 6.5 偏低); tex 5.0 (qwen 4.0 低, 大粒子细节可见)"),
    (1.0, 6, 8, 20, 120, 0.6): ([7.3, 6.8, 6.5, 8.0, 5.0, 7.1, 6.8],
        (7.5, 6.8, 7.0, 8.2, 5.3, 7.1, 6.9),
        "psize1.0+弱抖 → dyn 7.3; chroma20 → col 6.5; txt120 → text_read 8.0"),
    (1.3, 6, 20, 10, 220, 0.6): ([7.2, 6.6, 6.7, 8.3, 5.0, 7.3, 6.9],
        (6.5, 7.0, 6.0, 8.5, 5.0, 7.5, 6.8),
        "psize1.3+shake20 → dyn 7.2 (qwen 6.5 偏低); chroma10 → col 6.7"),
    (1.0, 10, 14, 10, 120, 1.0): ([7.3, 6.8, 6.7, 8.2, 5.2, 7.2, 6.9],
        (7.5, 6.8, 7.0, 8.5, 6.0, 7.3, 7.2),
        "psize1.0+chroma10 → col 6.7/tex 5.2 (qwen tex 6.0 高)"),
    (1.6, 14, 14, 20, 120, 0.6): ([6.5, 6.0, 6.5, 8.0, 4.3, 6.5, 6.3],
        (6.5, 5.8, 7.0, 8.2, 4.1, 6.3, 6.1),
        "psize1.6+chroma20 → dyn 6.5/cmp 6.0/tex 4.3"),
    (1.6, 6, 14, 10, 170, 1.0): ([6.5, 6.0, 6.7, 8.2, 4.3, 6.3, 6.3],
        (6.5, 5.8, 7.0, 8.2, 4.1, 6.3, 6.2),
        "psize1.6 → 遮挡最重; chroma10 → col 6.7"),
    (0.8, 14, 8, 15, 120, 1.5): ([7.5, 6.8, 6.6, 8.0, 5.1, 7.2, 6.9],
        (7.5, 6.8, 6.2, 8.0, 5.0, 7.3, 6.9),
        "psize0.8+punch14 → dyn 7.5; chroma15+glow1.5 → col 6.6 (qwen col 6.2 低)"),
    (1.6, 10, 20, 25, 220, 0.6): ([6.8, 6.0, 6.3, 8.3, 4.3, 6.5, 6.4],
        (6.5, 7.0, 6.0, 8.5, 5.0, 6.0, 6.5),
        "psize1.6+shake20 → dyn 6.8 (大粒子但强抖); cmp 6.0 (qwen 7.0 高, 遮挡重)"),
    (1.6, 6, 20, 15, 120, 1.5): ([6.8, 6.0, 6.5, 8.0, 4.3, 6.3, 6.3],
        (6.5, 7.0, 6.8, 8.0, 5.5, 6.0, 6.7),
        "psize1.6+shake20 → dyn 6.8; tex 4.3 (qwen 5.5 高)"),
    (1.0, 14, 8, 10, 170, 0.6): ([7.3, 6.8, 6.7, 8.3, 5.2, 7.0, 6.9],
        (7.5, 6.8, 6.0, 8.5, 5.2, 7.0, 6.9),
        "psize1.0+punch14 → dyn 7.3; chroma10+glow0.6 → col 6.7 (qwen col 6.0 低)"),
    (1.0, 6, 14, 15, 170, 1.5): ([7.3, 6.8, 6.6, 8.3, 5.0, 7.0, 6.9],
        (6.5, 7.0, 6.0, 8.5, 4.0, 6.0, 6.3),
        "psize1.0+shake14 → dyn 7.3 (qwen 6.5 偏低); col 6.6 (qwen 6.0 低); tex 5.0 (qwen 4.0 低)"),
    (1.3, 6, 20, 10, 120, 1.0): ([7.0, 6.6, 6.7, 8.0, 5.0, 7.2, 6.8],
        (7.0, 6.5, 6.8, 8.0, 5.5, 7.2, 6.9),
        "psize1.3+shake20 → dyn 7.0; chroma10 → col 6.7; txt120 → text_read 8.0"),
    (1.0, 10, 20, 10, 220, 1.5): ([7.5, 6.8, 6.7, 8.3, 5.0, 7.2, 7.0],
        (7.5, 6.8, 7.0, 8.2, 5.3, 7.0, 7.1),
        "psize1.0+shake20 → dyn 7.5; chroma10 → col 6.7; glow1.5 → tex 5.0"),
    (1.0, 10, 20, 10, 220, 0.6): ([7.5, 6.8, 6.7, 8.3, 5.2, 7.2, 7.0],
        (7.5, 6.8, 7.0, 8.2, 5.3, 7.0, 7.1),
        "同上组合但 glow0.6 弱光晕 → tex 5.2 (细节保留)"),
    (1.3, 6, 14, 20, 220, 1.0): ([7.0, 6.6, 6.5, 8.3, 4.8, 6.8, 6.8],
        (6.5, 7.0, 6.0, 8.5, 4.0, 6.0, 6.3),
        "psize1.3+shake14 → dyn 7.0 (qwen 6.5 偏低); chroma20 → col 6.5/tex 4.8 (qwen tex 4.0 低)"),
    (1.0, 10, 20, 20, 170, 0.6): ([7.5, 6.8, 6.5, 8.3, 5.0, 7.3, 7.0],
        (7.5, 6.8, 7.0, 8.2, 5.3, 7.1, 6.9),
        "psize1.0+punch10+shake20 → dyn 7.5; chroma20 → col 6.5 (qwen 7.0 高)"),
    (1.3, 6, 20, 20, 220, 0.6): ([7.2, 6.6, 6.5, 8.3, 4.8, 7.0, 6.8],
        (6.5, 7.0, 6.0, 8.5, 5.0, 6.5, 6.7),
        "psize1.3+shake20 → dyn 7.2 (qwen 6.5 偏低); chroma20 → col 6.5/tex 4.8"),
    (1.3, 10, 8, 20, 220, 1.5): ([7.0, 6.6, 6.5, 8.3, 4.8, 7.0, 6.8],
        (7.5, 6.8, 7.0, 8.2, 5.3, 7.0, 6.9),
        "psize1.3+punch10 → dyn 7.0 (qwen 7.5 偏高); chroma20+glow1.5 → col 6.5/tex 4.8"),
    (1.3, 10, 8, 6, 170, 1.0): ([7.0, 6.6, 6.8, 8.3, 5.0, 6.8, 6.8],
        (6.5, 7.0, 6.0, 8.5, 5.0, 6.0, 6.5),
        "psize1.3+punch10 → dyn 7.0; chroma6 → col 6.8 (qwen 6.0 低)"),
    (1.3, 6, 8, 10, 120, 1.5): ([6.8, 6.6, 6.7, 8.0, 5.0, 6.8, 6.8],
        (6.5, 7.0, 6.8, 8.0, 5.5, 6.0, 6.7),
        "psize1.3+弱抖 → dyn 6.8; chroma10+glow1.5 → col 6.7/tex 5.0 (qwen tex 5.5 高)"),
    (1.6, 10, 14, 20, 220, 1.0): ([6.5, 6.0, 6.5, 8.2, 4.3, 6.5, 6.3],
        (6.5, 5.8, 7.0, 8.2, 4.3, 6.7, 6.2),
        "psize1.6+chroma20 → dyn 6.5/cmp 6.0/tex 4.3; txt220 → text_read 8.2"),
    (1.0, 10, 14, 15, 220, 1.5): ([7.3, 6.8, 6.6, 8.3, 5.0, 7.0, 6.9],
        (6.5, 7.0, 6.0, 8.5, 4.0, 6.0, 6.3),
        "psize1.0+punch10+shake14 → dyn 7.3 (qwen 6.5 偏低); tex 5.0 (qwen 4.0 低)"),
    (1.3, 14, 14, 15, 120, 1.5): ([7.2, 6.6, 6.6, 8.0, 5.0, 7.0, 6.8],
        (6.5, 7.0, 6.8, 8.5, 5.0, 6.0, 6.7),
        "psize1.3+punch14+shake14 → dyn 7.2 (qwen 6.5 偏低); chroma15 → col 6.6"),
}


def main() -> int:
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    # 模型预测 (当前生产头)
    cnn_head = gbdt = None
    if CNN_HEAD.exists():
        with open(CNN_HEAD, "rb") as f:
            cnn_head = pickle.load(f)
    if GBDT_TUNER.exists():
        with open(GBDT_TUNER, "rb") as f:
            gbdt = pickle.load(f)
    z = np.load(EMB) if EMB.exists() else None
    row_of_emb = {int(i): idx for idx, i in enumerate(z["sample_idx"])} if z is not None else {}

    # 索引: 签名 → 行 (params + qwen 七维)
    sig_index = {}
    for i, r in enumerate(rows):
        if not r.get("frame_dir") or not Path(r["frame_dir"]).exists():
            continue
        if Path(r["frame_dir"]).name.startswith("sample_"):
            continue  # 污染样本
        try:
            pk = tuple(float(r.get(k, 0)) for k in PK)
            qs = tuple(round(float(r.get(d, 0)), 1) for d in DIMS)
        except (TypeError, ValueError):
            continue
        sig_index.setdefault((pk, qs), []).append(i)

    # 参数六元组索引 (降级匹配: qwen 重评分数会漂移, 参数组合唯一性足够高)
    pk_index = {}
    for (pk, qs), idxs in sig_index.items():
        pk_index.setdefault(pk, []).extend(idxs)

    out_rows = []
    used = set()
    unmatched = []
    for n, (pk, (label, qwen_sig, note)) in enumerate(
            sorted(GOLD.items(), key=lambda kv: [float(x) for x in kv[0]]), 1):
        hits = [i for i in sig_index.get((pk, qwen_sig), []) if i not in used]
        if not hits:  # 精确签名未命中 → 降级: 仅参数六元组
            hits = [i for i in pk_index.get(pk, []) if i not in used]
        if len(hits) != 1:
            unmatched.append((pk, qwen_sig, len(hits)))
            if not hits:
                continue
        i = hits[0]
        used.add(i)
        r = rows[i]
        # qwen 实际分数 (样本行内)
        qwen = {d: float(r.get(d, 0)) for d in DIMS}
        # 当前模型预测
        cnn_pred = None
        if cnn_head is not None and i in row_of_emb:
            p = cnn_head["model"].predict(z["emb"][row_of_emb[i]].reshape(1, -1))[0]
            cnn_pred = {d: round(float(v), 2) for d, v in zip(cnn_head["targets"], p)}
        gbdt_pred = None
        if gbdt is not None:
            X = np.array([[float(r.get(f, 0.0)) for f in gbdt["features"]]])
            gbdt_pred = {d: round(float(gbdt["models"][d].predict(X)[0]), 2) for d in gbdt["targets"]}
        out_rows.append({
            "id": n,
            "frame_dir": r["frame_dir"],
            "params": {k: r.get(k) for k in PK},
            "qwen": qwen,
            "cnn": cnn_pred,
            "gbdt": gbdt_pred,
            "gold_label": {d: v for d, v in zip(DIMS, label)},
            "gold_note": note,
        })

    if unmatched:
        print(f"⚠ {len(unmatched)} 条签名未唯一匹配:")
        for pk, qs, nh in unmatched:
            print(f"   {pk} → {nh} 命中")
    with open(GOLD_SET, "w", encoding="utf-8") as f:
        f.write("\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows) + "\n")
    print(f"黄金集已重建(签名匹配): {GOLD_SET} | {len(out_rows)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
