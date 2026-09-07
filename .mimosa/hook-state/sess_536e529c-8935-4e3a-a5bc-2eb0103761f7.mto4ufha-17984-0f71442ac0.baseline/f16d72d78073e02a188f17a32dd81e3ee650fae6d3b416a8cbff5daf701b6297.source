"""train_param_tuner.py — M2g 调参器训练

从 m2_auto_iterate 累积的 (参数,评分) 训练样本训 GBDT 回归器:
  输入: 参数特征（psize_scale/punch_amount/...）
  输出: 各维度评分预测 → 选预测最优的参数组合

当前阶段: 数据量小（每轮 1 样本），先训一个"评分→最优参数方向"的
回归器做演示，随数据积累精度提升。CPU 即可训练。

用法:
  # 默认: 用全量 140 样本训练（in-sample 乐观偏差参考）
  python scripts/train_param_tuner.py [--samples output/m2_iteration/train_samples.jsonl]
  # 去污染重训: 排除 50 黄金样本, 用剩余约 90 行重训 GBDT, 保存到 param_tuner_clean.pkl
  python scripts/train_param_tuner.py --exclude-gold
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

FEATURES = ["psize_scale", "punch_amount", "shake_amp", "chromatic_amount",
            "text_size", "text_opacity", "glow_intensity", "_pps_mult", "_glow_mult",
            "tint_color", "particle_template", "glow_radius"]
TARGETS = ["score_dynamism", "score_composition", "score_color_harmony",
           "score_text_read", "score_texture", "score_pacing", "score_overall"]
GOLD = PROJECT / "data" / "param_tuning" / "gold_set.jsonl"
TUNER_CLEAN = PROJECT / "models" / "output" / "param_tuner_clean.pkl"

# ── 分类参数编码 (字符串 ↔ 数值) ─────────────────────────────────────
# 扩展参数空间 (2026-08-17): 新增 tint_color / particle_template / glow_radius
# 分类参数需编码为数值才能喂给 GBDT; 推荐时用 *_REVMAP 转回字符串显示
# TODO: 实际渲染时如何把这三个参数接入 AE (LUT/Tint 效果、粒子层模板、Glow radius)
#       是后续工作, 当前仅扩展训练/推荐脚本的参数空间
TINT_MAP = {"none": 0, "warm": 1, "cool": 2, "teal_orange": 3, "noir": 4, "vintage": 5}
PARTICLE_MAP = {"spark": 0, "ember": 1, "snow": 2, "petal": 3, "dust": 4, "magic": 5}
TINT_REVMAP = {v: k for k, v in TINT_MAP.items()}
PARTICLE_REVMAP = {v: k for k, v in PARTICLE_MAP.items()}

# 新参数默认值 (训练样本缺这些字段时填充)
# glow_radius 默认 26 来自 grand_finale.py 的 EffectRef("match","ADBE Glo2",{"radius":26...})
TINT_DEFAULT = 0            # none (无配色偏移)
PARTICLE_DEFAULT = 0        # spark (现有粒子模板, 样本中全是 spark)
GLOW_RADIUS_DEFAULT = 26.0  # grand_finale.py Glow radius 默认值

# 分类特征 → (字符串→数值 MAP, 默认数值) 供 extract_feature_value 查表
_CATEGORICAL_FEATURES = {
    "tint_color": (TINT_MAP, TINT_DEFAULT),
    "particle_template": (PARTICLE_MAP, PARTICLE_DEFAULT),
}
# 数值特征默认值 (训练样本缺字段时填充, 非 0.0 的默认值)
_NUMERIC_DEFAULTS = {
    "glow_radius": GLOW_RADIUS_DEFAULT,
}


def extract_feature_value(row: dict, feat_name: str) -> float:
    """从训练样本行提取特征数值, 处理分类编码和默认值填充。

    - 分类特征 (tint_color/particle_template): 字符串 → 数值 via MAP;
      缺失或未知字符串 → 默认数值 (向后兼容旧样本)
    - glow_radius: 缺失 → 26.0 (grand_finale.py 默认值)
    - 其他特征: row.get(feat_name, 0.0)

    向后兼容: 旧样本无 tint_color/glow_radius 字段时用默认值填充,
    particle_template 在样本中全是 "spark" (编码 0)。这些新特征当前零方差
    → GBDT 零重要性 (符合预期, 实际方差待 AE 渲染接入后产生)。
    """
    if feat_name in _CATEGORICAL_FEATURES:
        mapping, default = _CATEGORICAL_FEATURES[feat_name]
        raw = row.get(feat_name)
        if raw is None:
            return float(default)
        if isinstance(raw, str):
            return float(mapping.get(raw, default))
        return float(raw)  # 已是数值 (预编码或旧 pkl)
    if feat_name in _NUMERIC_DEFAULTS:
        return float(row.get(feat_name, _NUMERIC_DEFAULTS[feat_name]))
    return float(row.get(feat_name, 0.0))


def _load_gold_frame_dirs():
    if not GOLD.exists():
        raise FileNotFoundError(f"无黄金集 {GOLD}")
    gold = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [g["frame_dir"] for g in gold]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", default=str(PROJECT / "data" / "param_tuning" / "train_samples.jsonl"))
    ap.add_argument("--exclude-gold", action="store_true",
                    help="排除 50 黄金样本后重训 GBDT, 保存到 param_tuner_clean.pkl "
                         "(out-of-sample 评测用, 保持 n_estimators=20/max_depth=2 不变)")
    args = ap.parse_args()

    samples_path = Path(args.samples)
    if not samples_path.exists():
        print(f"无训练样本: {samples_path}（先跑 m2_auto_iterate.py 累积）")
        return 1
    rows = [json.loads(l) for l in samples_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(rows) < 3:
        print(f"样本太少({len(rows)}), 至少 3 条才能训。继续累积迭代轮次。")
        return 1

    # 排除黄金样本（按 frame_dir 匹配）— 去污染用
    excluded_fds = []
    if args.exclude_gold:
        gold_fds = set(_load_gold_frame_dirs())
        excluded_fds = [r.get("frame_dir") for r in rows if r.get("frame_dir") in gold_fds]
        rows = [r for r in rows if r.get("frame_dir") not in gold_fds]
        print(f"[excl-gold] 排除 {len(excluded_fds)} 黄金样本, 剩余训练样本: {len(rows)}")
        if len(rows) < 3:
            print(f"排除后样本太少({len(rows)}), 至少 3 条才能训。")
            return 1

    # 构造特征矩阵 + 目标
    # 用 extract_feature_value 处理分类编码 (tint_color/particle_template)
    # 和默认值填充 (glow_radius 缺失 → 26), 兼容无新字段的旧样本
    import numpy as np
    X, y = [], []
    for r in rows:
        X.append([extract_feature_value(r, f) for f in FEATURES])
        y.append([float(r.get(t, 0.0)) for t in TARGETS])
    X, y = np.array(X), np.array(y)
    print(f"样本: {len(rows)} | 特征: {len(FEATURES)} | 目标: {len(TARGETS)}")

    from sklearn.ensemble import GradientBoostingRegressor

    # 训练 7 个单目标回归器（GBDT, 数据少时稳健）
    models = {}
    for i, t in enumerate(TARGETS):
        m = GradientBoostingRegressor(n_estimators=20, max_depth=2, random_state=42)
        m.fit(X, y[:, i])
        models[t] = m
        # 特征重要性
        imp = sorted(zip(FEATURES, m.feature_importances_), key=lambda x: -x[1])[:3]
        print(f"  {t}: 主要特征 {imp}")

    # 保存模型（pickle）
    import pickle
    if args.exclude_gold:
        out = TUNER_CLEAN
    else:
        out = PROJECT / "models" / "output" / "param_tuner.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"features": FEATURES, "targets": TARGETS, "models": models,
               "n_train": len(rows)}
    if args.exclude_gold:
        payload["excluded_frame_dirs"] = excluded_fds
    with open(out, "wb") as f:
        pickle.dump(payload, f)
    print(f"调参器已保存: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
