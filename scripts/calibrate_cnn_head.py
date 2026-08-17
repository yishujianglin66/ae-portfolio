"""calibrate_cnn_head.py — CNN 评分头黄金标定

基准评测 (eval_gold_benchmark) 发现: cnn 方向一致 0.81 (与 qwen 并列) 但
绝对值 MAE 0.28 偏 (qwen 0.18)。原因: Ridge 头在 52 样本上拟合, 学习率/正则
导致整体偏置。用 20 条黄金标签 (专家标准答案) 对每维做线性标定:
  gold ≈ slope * cnn_pred + intercept

标定参数 LOOCV 验证 (19 条 fit → 留出条应用), 有效才写入 head pickle,
推理时自动应用 (core/cnn_scorer._pred_to_scores)。

用法:
  python scripts/calibrate_cnn_head.py [--write]
  --write: LOOCV 验证有效后把标定参数写入 models/output/cnn_param_head.pkl
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

GOLD = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"
HEAD = PROJECT / "models" / "output" / "cnn_param_head.pkl"
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]


def fit_calibration(cnn_pred: np.ndarray, gold: np.ndarray) -> tuple:
    """最小二乘: gold = slope * cnn + intercept (每维独立)"""
    n = len(gold)
    A = np.vstack([cnn_pred, np.ones(n)]).T
    sol, *_ = np.linalg.lstsq(A, gold, rcond=None)
    return sol[0], sol[1]  # slope, intercept


def apply_cal(pred: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    return np.clip(slope * pred + intercept, 0, 10)


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(np.array(y_true) - np.array(y_pred))))


def main() -> int:
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--write", action="store_true", help="验证有效后写入 head")
    args = ap.parse_args()

    gold_rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(gold_rows) < 5:
        print(f"黄金样本不足: {len(gold_rows)}")
        return 1

    cnn_raw = np.array([[g["cnn"][d] for d in DIMS] for g in gold_rows])
    gold = np.array([[g["gold_label"][d] for d in DIMS] for g in gold_rows])
    n = len(gold_rows)

    print(f"黄金标定: {n} 条 | LOOCV 验证 (每维)\n")
    print(f"{'维度':<16}{'标定前MAE':>10}{'标定后MAE':>10}{'改善':>8}  标定参数 slope/intercept")
    print("-" * 72)

    calibration = {}
    improvements = []
    for j, d in enumerate(DIMS):
        before = []
        after = []
        for i in range(n):
            mask = np.ones(n, bool)
            mask[i] = False
            sl, ic = fit_calibration(cnn_raw[mask, j], gold[mask, j])
            before.append(abs(cnn_raw[i, j] - gold[i, j]))
            after.append(abs(apply_cal(cnn_raw[i, j], sl, ic) - gold[i, j]))
        mae_b, mae_a = mae([0], before), mae([0], after)
        imp = (mae_b - mae_a) / mae_b if mae_b > 0 else 0
        improvements.append(imp)
        # 全量标定参数 (生产用, 用全部黄金条 fit)
        sl, ic = fit_calibration(cnn_raw[:, j], gold[:, j])
        # 2026-08-17: 斜率<0.5 的维跳过 — LUT 后 color_harmony 语义演化,
        # 旧标签与新分布负相关, 负 slope 标定会反转预测 (回归守卫捕获此案)
        if sl < 0.5:
            print(f"{d.replace('score_', ''):<16}{mae_b:>10.3f}{mae_a:>10.3f}{imp:>7.1%}"
                  f"   {sl:+.2f} / {ic:+.2f}  ⚠ 斜率<0.5 跳过 (语义演化)")
            continue
        calibration[d] = {"slope": round(float(sl), 3), "intercept": round(float(ic), 3)}
        print(f"{d.replace('score_', ''):<16}{mae_b:>10.3f}{mae_a:>10.3f}{imp:>7.1%}"
              f"   {sl:+.2f} / {ic:+.2f}")

    avg_imp = np.mean(improvements)
    print(f"\n平均改善: {avg_imp:.1%} | 有效阈值: ≥10%")

    if args.write and avg_imp >= 0.10:
        with open(HEAD, "rb") as f:
            head = pickle.load(f)
        head["calibration"] = calibration
        head["calibration_n"] = n
        with open(HEAD, "wb") as f:
            pickle.dump(head, f)
        print(f"✅ 标定已写入: {HEAD} (推理自动应用)")
    elif args.write:
        print("❌ 标定无效 (改善 <10%), 未写入 — 保持原预测")
    elif avg_imp >= 0.10:
        print("✅ LOOCV 验证有效, 加 --write 写入生产头")
    return 0


if __name__ == "__main__":
    sys.exit(main())
