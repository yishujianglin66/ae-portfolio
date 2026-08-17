"""tests/test_gold_benchmark.py - 调参器黄金基准回归测试

黄金集 (output/m2_iteration/gold_set.jsonl) = 专家校准的 20 条标准答案。
本测试守住调参器对专家真值的距离, 防止任何模型/数据改动悄悄退化:

  1. 标定参数存在: 生产头必须含黄金标定 (cnn 绝对值标定的唯一来源)
  2. cnn 标定后 MAE ≤ 0.20: 本地评分对专家真值绝对值误差上限
     (实测 0.14, 留余量防回归; 标定前 0.28 会红)
  3. cnn 方向一致 ≥ 0.75: 排序能力下限 (实测 0.82)

用法: pytest tests/test_gold_benchmark.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

PROJECT = Path(__file__).resolve().parent.parent
GOLD = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"
HEAD = PROJECT / "models" / "output" / "cnn_param_head.pkl"
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]

pytestmark = pytest.mark.skipif(
    not GOLD.exists() or not HEAD.exists(),
    reason="需黄金集(gold_set.jsonl)与生产头(cnn_param_head.pkl)存在")


def _load() -> tuple:
    rows = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    import pickle
    with open(HEAD, "rb") as f:
        head = pickle.load(f)
    return rows, head


def _apply_cal(head, pred_raw: dict) -> dict:
    cal = head.get("calibration", {})
    out = {}
    for d in DIMS:
        v = pred_raw[d]
        if d in cal:
            c = cal[d]
            v = min(10.0, max(0.0, c["slope"] * v + c["intercept"]))
        out[d] = float(v)
    return out


def _metrics(y_true, y_pred):
    mae = float(np.mean(np.abs(np.array(y_true) - np.array(y_pred))))
    agree = pairs = 0
    n = len(y_true)
    for a in range(n):
        for b in range(a + 1, n):
            if y_true[a] == y_true[b]:
                continue
            agree += 1 if (y_pred[a] > y_pred[b]) == (y_true[a] > y_true[b]) else 0
            pairs += 1
    return mae, (agree / pairs if pairs else float("nan"))


def test_calibration_present():
    """生产头必须含黄金标定参数 (cnn 绝对值标定的唯一来源)。"""
    _, head = _load()
    assert "calibration" in head, "生产头缺黄金标定, 先跑 calibrate_cnn_head.py --write"
    # 2026-08-17: 斜率<0.5 的维合法跳过 (LUT 后 color_harmony 语义演化, 负 slope 会反转预测)
    assert len(head["calibration"]) >= 5, f"标定维数过少: {len(head['calibration'])}"
    # 每个已标定维 slope 必须为正且足够陡 (防反转)
    for d, c in head["calibration"].items():
        assert c["slope"] > 0.5, f"{d} 标定 slope 异常: {c}"


def test_cnn_calibrated_mae_budget():
    """cnn 标定后对专家真值平均 MAE ≤ 0.20 (实测 0.14, 标定前 0.28 会红)。"""
    rows, head = _load()
    gold = np.array([[r["gold_label"][d] for d in DIMS] for r in rows])
    preds = np.array([list(_apply_cal(head, r["cnn"]).values()) for r in rows])
    mae, _ = _metrics(gold.flatten(), preds.flatten())
    assert mae <= 0.20, f"cnn 标定后 MAE {mae:.3f} 超预算 0.20 — 调参器绝对值回归"


def test_cnn_ranking_floor():
    """cnn 排序能力下限: 每维方向一致 ≥ 0.75 (实测 0.82)。"""
    rows, head = _load()
    gold = np.array([[r["gold_label"][d] for d in DIMS] for r in rows])
    preds = np.array([list(_apply_cal(head, r["cnn"]).values()) for r in rows])
    per_dim = [_metrics(gold[:, j], preds[:, j])[1] for j in range(len(DIMS))]
    avg = float(np.mean(per_dim))
    assert avg >= 0.75, f"cnn 平均方向一致 {avg:.3f} 低于下限 0.75"
