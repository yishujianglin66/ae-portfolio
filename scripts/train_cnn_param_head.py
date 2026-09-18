"""train_cnn_param_head.py — CNN 深度调参器评分头训练与评测

冻结 CLIP ViT-L-14 (open_clip) 编码帧 → 768 维嵌入 → 可训头 → 回归各维度评分。
与 GBDT 调参器完全同指标 LOOCV (MAE/Spearman/方向一致率) 直接对比,
回答: "看过渲染帧的视觉特征" 是否比 "只看参数数值" 预测更准。

两个可训头:
  1. 线性探针 (Ridge, 内层 LOOCV 选 alpha) — 100 样本小数据的稳健基线
  2. 小 MLP (768→128→1, dropout) — 学习非线性视觉关系

用法:
  # 默认: 100 样本 LOOCV 自评 (in-sample 乐观偏差参考)
  python scripts/train_cnn_param_head.py
  # 去污染重训: 排除 50 黄金样本, full-fit 训练 Ridge+MLP, 保存模型
  python scripts/train_cnn_param_head.py --exclude-gold
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

from core.torch_runtime import get_device, infer_ctx  # noqa: E402

EMB = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
GOLD = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"
HEAD_EXCL_GOLD = PROJECT / "models" / "output" / "cnn_param_head_excl_gold.pkl"
TARGETS = ["score_dynamism", "score_composition", "score_color_harmony",
           "score_text_read", "score_texture", "score_pacing", "score_overall"]
ALPHAS = np.logspace(-4, 4, 25)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray):
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


def load_data():
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    z = np.load(EMB)
    emb, sidx = z["emb"], z["sample_idx"]
    labels = np.zeros((len(emb), len(TARGETS)))
    for j, t in enumerate(TARGETS):
        labels[:, j] = [float(rows[i][t]) for i in sidx]
    return emb, labels


def _load_gold_frame_dirs():
    """读取 gold_set.jsonl 的全部 frame_dir（用于排除）。"""
    if not GOLD.exists():
        raise FileNotFoundError(f"无黄金集 {GOLD}")
    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [g["frame_dir"] for g in gold]


def load_data_excl_gold():
    """排除 50 黄金样本后的训练数据。

    同步过滤 CLIP 嵌入: 只保留 sample_idx 不在排除行号集合里的样本。
    返回 (emb, labels, excluded_row_indices, excluded_frame_dirs, sidx_remaining)。
    sidx_remaining 是过滤后保留的 sample_idx（原行号, 便于在 eval 时反向查找）。
    """
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    gold_fds = _load_gold_frame_dirs()
    excluded_row_idx = {i for i, r in enumerate(rows) if r.get("frame_dir") in gold_fds}

    z = np.load(EMB)
    emb_all, sidx_all = z["emb"], z["sample_idx"]
    keep_mask = np.array([int(i) not in excluded_row_idx for i in sidx_all])
    emb = emb_all[keep_mask]
    sidx = sidx_all[keep_mask]
    labels = np.zeros((len(emb), len(TARGETS)))
    for j, t in enumerate(TARGETS):
        labels[:, j] = [float(rows[i][t]) for i in sidx]
    excluded_fds = [r.get("frame_dir") for i, r in enumerate(rows) if i in excluded_row_idx]
    return emb, labels, sorted(excluded_row_idx), excluded_fds, sidx


def _mlp_full_fit(X: np.ndarray, y: np.ndarray, seed: int = 0):
    """full-fit 小 MLP（与 mlp_loocv 同结构/同超参, 但只训一次用于保存）。"""
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    dev = get_device()
    head = nn.Sequential(
        nn.Linear(X.shape[1], 128), nn.ReLU(), nn.Dropout(0.4),
        nn.Linear(128, 1),
    ).to(dev)
    opt = torch.optim.Adam(head.parameters(), lr=2e-3, weight_decay=1e-2)
    lossf = nn.MSELoss()
    Xt = torch.tensor(X, dtype=torch.float32, device=dev)
    yt = torch.tensor(y, dtype=torch.float32, device=dev)
    head.train()
    for _ in range(150):
        opt.zero_grad()
        out = head(Xt).squeeze(1)
        loss = lossf(out, yt)
        loss.backward()
        opt.step()
    head.eval()
    return head, dev


def _ridge_full_fit(X: np.ndarray, y: np.ndarray):
    """full-fit Ridge 多输出（与 core.cnn_scorer.train_head 同 alpha=1.0, 便于对比）。"""
    from sklearn.linear_model import Ridge
    m = Ridge(alpha=1.0)
    m.fit(X, y)
    return m


def train_and_save_excl_gold() -> Path:
    """排除黄金 50 条 → full-fit Ridge+MLP → 保存到 cnn_param_head_excl_gold.pkl。

    pickle 内容: {features, targets, ridge_model, mlp_state, mlp_dev,
                  excluded_frame_dirs, excluded_row_idx, sample_idx, n_train}
    """
    emb, labels, excl_row_idx, excl_fds, sidx = load_data_excl_gold()
    print(f"[excl-gold] 训练样本: {len(emb)} | 排除行号: {len(excl_row_idx)} | "
          f"排除 frame_dir 数: {len(excl_fds)}")

    ridge = _ridge_full_fit(emb, labels)
    # MLP 逐目标独立训（与 mlp_loocv 同结构, 7 个独立头）
    mlp_states = {}
    mlp_dev = "cpu"
    for j, t in enumerate(TARGETS):
        yj = labels[:, j]
        if len(set(yj)) < 2:
            continue
        head, dev = _mlp_full_fit(emb, yj)
        mlp_states[t] = {"state_dict": {k: v.cpu() for k, v in head.state_dict().items()},
                         "dev": dev}
        mlp_dev = dev

    HEAD_EXCL_GOLD.parent.mkdir(parents=True, exist_ok=True)
    with open(HEAD_EXCL_GOLD, "wb") as f:
        pickle.dump({
            "features": "clip_vitl14_emb",
            "targets": TARGETS,
            "ridge_model": ridge,
            "mlp_states": mlp_states,
            "mlp_dev": mlp_dev,
            "excluded_frame_dirs": excl_fds,
            "excluded_row_idx": excl_row_idx,
            "sample_idx": [int(i) for i in sidx],
            "n_train": len(emb),
        }, f)
    print(f"[excl-gold] Ridge+MLP 已保存: {HEAD_EXCL_GOLD}")
    return HEAD_EXCL_GOLD


def _solve_loocv(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    """严格 LOOCV: 每留 1 样本重拟合一次 (100 次解线性方程, 秒级)。

    X 已是 L2 归一化嵌入, alpha=1.0 固定 (内层选择在 100 样本+768 维下
    只会过拟合选参本身; 固定强正则更诚实)。
    """
    from sklearn.linear_model import Ridge
    n = len(y)
    preds = np.zeros(n)
    for i in range(n):
        mask = np.ones(n, bool)
        mask[i] = False
        m = Ridge(alpha=alpha)
        m.fit(X[mask], y[mask])
        preds[i] = m.predict(X[i:i + 1])[0]
    return preds


def ridge_loocv(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return _solve_loocv(X, y, alpha=1.0)


def mlp_loocv(X: np.ndarray, y: np.ndarray, seed: int = 0) -> np.ndarray:
    """LOOCV 小 MLP 头: 固定 150 轮 + 强正则 (100 样本量下早停信噪比低, 用固定预算)。"""
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    dev = get_device()
    n = len(y)
    preds = np.zeros(n)
    Xt = torch.tensor(X, dtype=torch.float32)
    for i in range(n):
        mask = np.ones(n, bool)
        mask[i] = False
        Xtr, ytr = Xt[mask], torch.tensor(y[mask], dtype=torch.float32)
        Xte = Xt[i:i + 1]
        head = nn.Sequential(
            nn.Linear(X.shape[1], 128), nn.ReLU(), nn.Dropout(0.4),
            nn.Linear(128, 1),
        ).to(dev)
        opt = torch.optim.Adam(head.parameters(), lr=2e-3, weight_decay=1e-2)
        lossf = nn.MSELoss()
        head.train()
        for _ in range(150):
            opt.zero_grad()
            out = head(Xtr.to(dev)).squeeze(1)
            loss = lossf(out, ytr.to(dev))
            loss.backward()
            opt.step()
        head.eval()
        with infer_ctx(dev):
            preds[i] = head(Xte.to(dev)).item()
    return preds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exclude-gold", action="store_true",
                    help="排除 50 黄金样本 → full-fit 训练 Ridge+MLP 并保存 "
                         "(out-of-sample 评测用, 不做 LOOCV)")
    args = ap.parse_args()

    if args.exclude_gold:
        train_and_save_excl_gold()
        return 0

    emb, labels = load_data()
    print(f"嵌入 {emb.shape} | 目标 {len(TARGETS)} | LOOCV n={len(emb)}")

    header = f"{'目标':<24}{'GBDT(100)':>12}{'Ridge':>9}{'MLP':>9}"
    print(f"\n{header}")
    print(f"{'':<24}{'MAE/Rho/Dir':>12}{'M/R/D':>9}{'M/R/D':>9}")
    print("-" * 66)
    summary = {"ridge": {}, "mlp": {}}
    for j, t in enumerate(TARGETS):
        y = labels[:, j]
        if len(set(y)) < 2:
            print(f"{t:<24} 无方差, 跳过")
            continue
        pr = ridge_loocv(emb, y)
        pm = mlp_loocv(emb, y)
        mr = _metrics(y, pr)
        mm = _metrics(y, pm)
        summary["ridge"][t] = mr
        summary["mlp"][t] = mm
        print(f"{t:<24}"
              f"{'(0.64/0.29/0.64)':>12}"
              f"{mr[0]:>4.2f}/{mr[1]:>4.2f}/{mr[2]:>4.2f}"
              f"{mm[0]:>6.2f}/{mm[1]:>4.2f}/{mm[2]:>4.2f}")

    # 与 GBDT 100 样本 LOOCV 对比 (2026-08-16 已测)
    print("\n=== GBDT(100样本) 对照 ===")
    gbdt = {"score_dynamism": (0.64, 0.289, 0.64), "score_overall": (0.29, 0.285, 0.61),
            "score_pacing": (0.53, 0.158, 0.56), "score_composition": (0.21, 0.117, 0.56),
            "score_text_read": (0.30, 0.127, 0.56), "score_texture": (0.48, 0.031, 0.51),
            "score_color_harmony": (0.41, -0.142, 0.44)}
    print(f"{'目标':<24}{'GBDT_M':>8}{'GBDT_Rho':>10}{'GBDT_Dir':>10}"
          f"{'Ridge_Dir':>11}{'MLP_Dir':>10}")
    for t in TARGETS:
        g = gbdt.get(t)
        r = summary["ridge"].get(t)
        m = summary["mlp"].get(t)
        if not g or not r:
            continue
        print(f"{t:<24}{g[0]:>8.2f}{g[1]:>10.3f}{g[2]:>10.2f}"
              f"{r[2]:>11.2f}{m[2]:>10.2f}")

    # 结论
    print("\n=== 结论 ===")
    for name in ("ridge", "mlp"):
        best = max(summary[name].items(), key=lambda kv: kv[1][2])
        print(f"{name}: 方向一致最佳 {best[0]} = {best[1][2]:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
