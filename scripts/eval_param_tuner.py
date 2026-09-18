"""eval_param_tuner.py — GBDT 调参器精度评测

用 50 样本做留一交叉验证（LOOCV）: 每次留 1 样本, 用其余训练, 预测留出样本的
各维度评分, 与 qwen 实际评分对比。50 样本量 LOOCV 最稳（充分利用小数据）。

指标（每维度 + overall）:
  - MAE（平均绝对误差）
  - Spearman 相关系数（排序一致性, 调参器最关心"谁更好"而非绝对值）
  - 方向一致率（预测高低 vs 实际高低一致的比例）

结论判据:
  - texture/composition MAE 大 + 相关性低 → CNN 触发信号（视觉化维度, 参数数值表达不了）
  - dynamism/pacing MAE 小 → GBDT 已够用

用法:
  python scripts/eval_param_tuner.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.train_param_tuner import FEATURES, TARGETS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=str(PROJECT / "data" / "param_tuning" / "train_samples.jsonl"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in Path(args.samples).read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(rows) < 5:
        print(f"样本不足: {len(rows)}")
        return 1
    print(f"样本: {len(rows)} | 特征: {len(FEATURES)} | 目标: {len(TARGETS)}")

    X = np.array([[float(r.get(f, 0.0)) for f in FEATURES] for r in rows])
    Y = np.array([[float(r.get(t, 0.0)) for t in TARGETS] for r in rows])

    from scipy.stats import spearmanr
    from sklearn.ensemble import GradientBoostingRegressor

    n = len(rows)
    # LOOCV: 每目标独立
    print(f"\n{'目标':<24}{'MAE':>6}{'Spearman':>10}{'方向一致':>8}")
    print("-" * 52)
    summary = {}
    for ti, t in enumerate(TARGETS):
        preds = np.zeros(n)
        for i in range(n):
            mask = np.ones(n, bool)
            mask[i] = False
            m = GradientBoostingRegressor(n_estimators=20, max_depth=2, random_state=42)
            m.fit(X[mask], Y[mask, ti])
            preds[i] = m.predict(X[i:i + 1])[0]
        mae = float(np.mean(np.abs(preds - Y[:, ti])))
        # Spearman
        if len(set(Y[:, ti])) > 1 and len(set(preds)) > 1:
            rho, _ = spearmanr(Y[:, ti], preds)
        else:
            rho = float("nan")
        # 方向一致率: 对每对样本, 预测说谁分高, 实际谁分高
        agree = 0.0
        pairs = 0
        for a in range(n):
            for b in range(a + 1, n):
                if Y[a, ti] == Y[b, ti]:
                    continue
                pred_agree = (preds[a] > preds[b]) == (Y[a, ti] > Y[b, ti])
                agree += 1 if pred_agree else 0
                pairs += 1
        dir_acc = agree / pairs if pairs else float("nan")
        summary[t] = {"mae": mae, "spearman": rho, "dir_acc": dir_acc}
        print(f"{t:<24}{mae:>6.2f}{rho:>10.3f}{dir_acc:>8.2f}")

    # 结论
    print("\n=== 结论 ===")
    low = sorted(summary.items(), key=lambda x: x[1]["mae"])
    worst = low[-1][0]
    print(f"最佳维度: {low[0][0]} (MAE {low[0][1]['mae']:.2f})")
    print(f"最差维度: {worst} (MAE {low[-1][1]['mae']:.2f})")
    if summary[worst]["mae"] > 1.2 and (summary[worst]["spearman"] is None or summary[worst]["spearman"] < 0.3):
        print(f"⚠ {worst} 预测不准 → CNN 触发信号（视觉化维度, 参数数值表达不了）")
    else:
        print("GBDT 各维度可接受, 继续用 GBDT; 再积累样本")
    return 0


if __name__ == "__main__":
    sys.exit(main())
