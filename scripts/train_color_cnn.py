"""train_color_cnn.py — color_harmony CNN 评分头（P2 触发, 2026-08-16）

GBDT 在 color_harmony 上 Spearman 0.128 ≈ 0（评分有 5 档区分度但学不会）
→ 纯视觉维度, 参数数值表达不了, 必须看帧。用 CLIP 编码帧 + MLP 回归。

架构:
  渲染帧(4张, sample) → CLIP ViT-B/32(冻结, laion) → 4×512 平均 → 512 视觉特征
  concat 参数特征(9维) → MLP[521→64→1] → color_harmony 回归

训练: 38 带帧样本, 留一交叉验证(LOOCV) 报告 Spearman/MAE/方向一致,
     与 GBDT(0.128/56%) 对比。CLIP 冻结只训 MLP(小数据防过拟合)。

用法:
  python scripts/train_color_cnn.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.train_param_tuner import FEATURES  # noqa: E402


def load_frame_samples() -> list:
    """带帧样本: {feat, frames[], color_harmony}"""
    rows = [json.loads(l) for l in
            (PROJECT / "data" / "param_tuning" / "train_samples.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        fd = r.get("frame_dir", "")
        if not fd or not Path(fd).exists():
            continue
        frames = sorted(Path(fd).glob("frame_*.jpg"))
        if not frames:
            continue
        out.append({
            "feat": [float(r.get(f, 0.0)) for f in FEATURES],
            "frames": [str(f) for f in frames],
            "color": float(r.get("score_color_harmony", 5.0)),
        })
    return out


def encode_frames(bb, frame_paths: list) -> np.ndarray:
    """CLIP 编码多帧 → 平均池化 → 512 维视觉特征。"""
    embs = [bb.encode_images([p]) for p in frame_paths]
    return np.mean(np.vstack(embs), axis=0)


def main() -> int:
    import torch
    import torch.nn as nn

    from ai.clip_backbones import BackboneRegistry
    bb = BackboneRegistry().get("laion")

    samples = load_frame_samples()
    n = len(samples)
    if n < 5:
        print(f"带帧样本不足: {n}")
        return 1
    print(f"带帧样本: {n}")

    # 预编码全部帧（CLIP 冻结, 一次性编码省重复前向）
    print("CLIP 编码帧...")
    for s in samples:
        s["vis"] = encode_frames(bb, s["frames"])
    print("编码完成")

    DEV = "cuda" if torch.cuda.is_available() else "cpu"
    D_vis, D_param = 512, len(FEATURES)

    class MLPHead(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(D_vis + D_param, 64), nn.ReLU(), nn.Dropout(0.2),
                nn.Linear(64, 1),
            )

        def forward(self, vis, param):
            return self.net(torch.cat([vis, param], dim=-1)).squeeze(-1)

    # LOOCV
    preds = np.zeros(n)
    for i in range(n):
        model = MLPHead().to(DEV)
        opt = torch.optim.Adam(model.parameters(), lr=1e-3)
        lossf = nn.MSELoss()
        train_idx = [j for j in range(n) if j != i]
        Xv = torch.tensor(np.array([samples[j]["vis"] for j in train_idx]),
                          dtype=torch.float32, device=DEV)
        Xp = torch.tensor(np.array([samples[j]["feat"] for j in train_idx]),
                          dtype=torch.float32, device=DEV)
        Y = torch.tensor(np.array([samples[j]["color"] for j in train_idx]),
                         dtype=torch.float32, device=DEV)
        model.train()
        for _ in range(200):
            opt.zero_grad()
            loss = lossf(model(Xv, Xp), Y)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            xv = torch.tensor(samples[i]["vis"], dtype=torch.float32, device=DEV).unsqueeze(0)
            xp = torch.tensor(samples[i]["feat"], dtype=torch.float32, device=DEV).unsqueeze(0)
            preds[i] = model(xv, xp).item()

    true = np.array([s["color"] for s in samples])
    mae = float(np.mean(np.abs(preds - true)))
    from scipy.stats import spearmanr
    if len(set(true)) > 1 and len(set(preds)) > 1:
        rho, _ = spearmanr(true, preds)
    else:
        rho = float("nan")
    agree = 0.0
    pairs = 0
    for a in range(n):
        for b in range(a + 1, n):
            if true[a] == true[b]:
                continue
            agree += 1 if (preds[a] > preds[b]) == (true[a] > true[b]) else 0
            pairs += 1
    dir_acc = agree / pairs if pairs else float("nan")

    print(f"\n=== color_harmony CNN 评分头 (LOOCV, {n} 样本) ===")
    print(f"MAE: {mae:.3f} | Spearman: {rho:.3f} | 方向一致: {dir_acc:.2f}")
    print(f"\n对比 GBDT:   MAE 0.84 | Spearman 0.128 | 方向一致 0.56")
    print(f"提升: Spearman {0.128:.3f}→{rho:.3f}, 方向一致 {0.56:.2f}→{dir_acc:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
