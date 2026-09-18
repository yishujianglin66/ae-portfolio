"""eval_gold_benchmark.py — 黄金集基准评测（模型 vs 专家标签）

gold_set.jsonl = 专家校准的 50 条黄金标签（标准答案）。
评测 qwen / cnn(Ridge) / gbdt 三方离真值多远（与 LOOCV 同指标）:
  MAE / Spearman / 方向一致率 — 这是调参器可信度的最终裁定:
  LOOCV 是"模型间自评"(训练集留一), 黄金基准是"对专家标准答案"的绝对距离。

用法:
  # 默认: 用生产头 (140 样本训练, 含黄金标定) + 缓存 gbdt 预测
  python scripts/eval_gold_benchmark.py
  # out-of-sample: 加载排除黄金 50 条后训练的 CNN 头 (90 样本)
  python scripts/eval_gold_benchmark.py --head excl_gold
  # out-of-sample: 加载排除黄金 50 条后训练的 GBDT (90 样本)
  python scripts/eval_gold_benchmark.py --gbdt clean
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

GOLD = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]
HEAD_EXCL_GOLD = PROJECT / "models" / "output" / "cnn_param_head_excl_gold.pkl"
TUNER_CLEAN = PROJECT / "models" / "output" / "param_tuner_clean.pkl"
# GBDT 特征（与 train_param_tuner.py 同步, 用于 clean GBDT 推理）
GBDT_FEATURES = ["psize_scale", "punch_amount", "shake_amp", "chromatic_amount",
                 "text_size", "text_opacity", "glow_intensity", "_pps_mult", "_glow_mult"]


def metrics(y_true, y_pred):
    from scipy.stats import spearmanr
    mae = float(np.mean(np.abs(y_true - y_pred)))
    if len(set(y_true)) > 1 and len(set(y_pred)) > 1:
        rho = float(spearmanr(y_true, y_pred).statistic)
    else:
        rho = float("nan")
    agree = pairs = 0
    n = len(y_true)
    for a in range(n):
        for b in range(a + 1, n):
            if y_true[a] == y_true[b]:
                continue
            agree += 1 if (y_pred[a] > y_pred[b]) == (y_true[a] > y_true[b]) else 0
            pairs += 1
    dir_acc = agree / pairs if pairs else float("nan")
    return mae, rho, dir_acc


def _load_train_rows():
    """读 train_samples.jsonl 全量行（黄金样本帧目录定位用）。"""
    samples = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
    return [json.loads(l) for l in samples.read_text(encoding="utf-8").splitlines() if l.strip()]


def _row_of_emb_idx():
    """返回 {train_samples 行号: 嵌入数组下标} 映射, 用于按 frame_dir 定位嵌入。"""
    emb_path = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
    z = np.load(emb_path)
    return {int(i): idx for idx, i in enumerate(z["sample_idx"])}, z["emb"]


def _cnn_pred_production(gold, rows, row_of_emb, emb_arr):
    """生产头预测（含黄金标定, in-sample 乐观偏差参考）。"""
    from core.cnn_scorer import _pred_to_scores, load_head  # noqa: F401
    _ = load_head()  # 触发加载, 与原行为一致
    n = len(gold)
    out = np.zeros((n, len(DIMS)))
    for k, g in enumerate(gold):
        fd = g["frame_dir"]
        ridx = next((i for i, r in enumerate(rows) if r.get("frame_dir") == fd), None)
        if ridx is None or ridx not in row_of_emb:
            raise ValueError(f"黄金样本帧目录不在嵌入中: {fd}")
        emb = emb_arr[row_of_emb[ridx]]
        s = _pred_to_scores(emb)
        out[k] = [s[d] for d in DIMS]
    return out


def _cnn_pred_excl_gold(gold, rows, row_of_emb, emb_arr):
    """排除黄金 50 条后训练的 Ridge 头预测（无标定, raw out-of-sample）。"""
    if not HEAD_EXCL_GOLD.exists():
        raise FileNotFoundError(f"无 excl_gold 头: {HEAD_EXCL_GOLD}"
                                 f"（先 py -3.12 scripts/train_cnn_param_head.py --exclude-gold）")
    with open(HEAD_EXCL_GOLD, "rb") as f:
        head = pickle.load(f)
    ridge = head["ridge_model"]
    targets = head["targets"]
    n = len(gold)
    out = np.zeros((n, len(DIMS)))
    for k, g in enumerate(gold):
        fd = g["frame_dir"]
        ridx = next((i for i, r in enumerate(rows) if r.get("frame_dir") == fd), None)
        if ridx is None or ridx not in row_of_emb:
            raise ValueError(f"黄金样本帧目录不在嵌入中: {fd}")
        emb = emb_arr[row_of_emb[ridx]]
        pred = ridge.predict(emb.reshape(1, -1))[0]
        # targets 顺序与 DIMS 一致; 但保险起见按名映射
        scores = {t: float(v) for t, v in zip(targets, pred)}
        out[k] = [scores[d] for d in DIMS]
    return out


def _gbdt_pred_clean(gold, rows):
    """排除黄金 50 条后训练的 GBDT 预测（从 frame_dir 提取 FEATURES）。"""
    if not TUNER_CLEAN.exists():
        raise FileNotFoundError(f"无 clean GBDT: {TUNER_CLEAN}"
                                 f"（先 py -3.12 scripts/train_param_tuner.py --exclude-gold）")
    with open(TUNER_CLEAN, "rb") as f:
        bundle = pickle.load(f)
    models = bundle["models"]
    feats = bundle["features"]
    n = len(gold)
    out = np.zeros((n, len(DIMS)))
    for k, g in enumerate(gold):
        fd = g["frame_dir"]
        r = next((r for r in rows if r.get("frame_dir") == fd), None)
        if r is None:
            raise ValueError(f"黄金样本帧目录不在 train_samples: {fd}")
        x = np.array([[float(r.get(f, 0.0)) for f in feats]])
        for j, d in enumerate(DIMS):
            out[k, j] = float(models[d].predict(x)[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--head", default="production", choices=["production", "excl_gold"],
                    help="CNN 评分头: production=生产头(140训, 含标定); "
                         "excl_gold=排除黄金 50 条后训练头(90训, 无标定)")
    ap.add_argument("--gbdt", default="production", choices=["production", "clean"],
                    help="GBDT 调参器: production=gold_set 缓存预测; "
                         "clean=排除黄金 50 条后重训 GBDT(90训) 实时预测")
    args = ap.parse_args()

    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    n = len(gold)
    print(f"黄金基准: {n} 条专家标签 | head={args.head} | gbdt={args.gbdt}\n")

    y_gold = np.array([[g["gold_label"][d] for d in DIMS] for g in gold])
    rows = _load_train_rows()
    row_of_emb, emb_arr = _row_of_emb_idx()

    # CNN 头预测分派
    if args.head == "excl_gold":
        cnn_live = _cnn_pred_excl_gold(gold, rows, row_of_emb, emb_arr)
        cnn_label = "cnn(excl_gold)"
    else:
        cnn_live = _cnn_pred_production(gold, rows, row_of_emb, emb_arr)
        cnn_label = "cnn(标定后)"

    # GBDT 预测分派
    if args.gbdt == "clean":
        gbdt_pred = _gbdt_pred_clean(gold, rows)
        gbdt_label = "gbdt(clean)"
    else:
        gbdt_pred = np.array([[g["gbdt"][d] for d in DIMS] for g in gold])
        gbdt_label = "gbdt"

    preds = {"qwen": np.array([[g["qwen"][d] for d in DIMS] for g in gold]),
             cnn_label: cnn_live,
             gbdt_label: gbdt_pred}

    # 每模型 × 每维度
    header = f"{'':<22}" + "".join(f"{m:>14}" for m in preds)
    print(header)
    print("-" * len(header))
    summary = {m: {} for m in preds}
    for j, d in enumerate(DIMS):
        yt = y_gold[:, j]
        row = f"{d.replace('score_', ''):<22}"
        for m, P in preds.items():
            mae, rho, dir_acc = metrics(yt, P[:, j])
            summary[m][d] = {"mae": mae, "rho": rho, "dir_acc": dir_acc}
            row += f"{mae:>10.2f}/{dir_acc:>5.2f}"
        print(row)

    # 总评: 平均 MAE + 平均方向一致
    print(f"\n=== 总评 ({n} 条黄金标签 | head={args.head} gbdt={args.gbdt}) ===")
    for m in preds:
        avg_mae = np.mean([summary[m][d]["mae"] for d in DIMS])
        avg_dir = np.mean([summary[m][d]["dir_acc"] for d in DIMS])
        print(f"  {m:<18} 平均 MAE {avg_mae:.3f} | 平均方向一致 {avg_dir:.3f}")

    # 结论
    print("\n=== 结论 ===")
    for d in DIMS:
        best = min(preds, key=lambda m: summary[m][d]["mae"])
        worst = max(preds, key=lambda m: summary[m][d]["mae"])
        print(f"  {d.replace('score_', ''):<14} 最近真值: {best:<18} 最远: {worst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
