"""param_recommend.py — 调参器生产接入（M2g 生产化）

用 50 样本训的 GBDT 做**参数推荐**: 给定当前合成树参数, 用调参器预测
各参数档位的评分, 选预测最高的组合。这是从"迭代"到"一次到位"的升级:
  - 迭代: 改一档→渲染→评分→再看（慢, 每轮 1 次渲染）
  - 推荐: 用 GBDT 网格预测各组合→直接选最优→渲染 1 次（快, 1 次到位）

两阶段模式 (--two-stage):
  阶段1 GBDT 初筛: 网格搜索全组合 → 加权总分 → top-10 候选
  阶段2 CNN 精排: 对 top-10 用参数空间最近邻找已有样本的 CLIP 嵌入
                  → CNN 头预测 7 维评分 → 重排 → final top-N
  - 无近邻 (>2.0 z-score 距离) 时退化为 GBDT 值并记警告

用法:
  python scripts/param_recommend.py [--style edit] [--two-stage] [--topn 3]
输出: 推荐参数组合 + 预测评分 → output/m2_iteration/recommend.json
      两阶段报告 → tmp/two_stage_recommend.txt
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime
from itertools import product
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

# sklearn 1.8 → 1.9 兼容: 旧 GBDT pickle 中 CyHalfSquaredError.__module__='_loss',
# 1.9.0 中改为 'sklearn._loss._loss', 无此 alias 会 ModuleNotFoundError
try:
    import sklearn._loss._loss as _sk_loss_ext  # noqa: F401
    sys.modules.setdefault("_loss", _sk_loss_ext)
except ImportError:
    pass

from scripts.train_param_tuner import (  # noqa: E402
    FEATURES, TARGETS, extract_feature_value,
    TINT_REVMAP, PARTICLE_REVMAP,
)
from core.visual_scorer import get_dim_priority  # noqa: E402

# 推荐网格（比采集 GRID 更细）
# 2026-08-17 扩展: 新增 tint_color / particle_template / glow_radius
# 网格规模 1215 → 1215 × 6 × 6 × 5 = 218700 (新参数当前零方差, GBDT 不区分,
# 实际方差待 AE 渲染接入后产生)
REC_GRID = {
    "psize_scale": [0.6, 0.8, 1.0, 1.2, 1.4],
    "punch_amount": [8, 10, 12],
    "shake_amp": [10, 14, 18],
    "chromatic_amount": [8, 12, 16],
    "_glow_mult": [0.8, 1.0, 1.2],
    "text_size": [140, 180, 220],
    "tint_color": [0, 1, 2, 3, 4, 5],          # 6 档: none/warm/cool/teal_orange/noir/vintage
    "particle_template": [0, 1, 2, 3, 4, 5],   # 6 档: spark/ember/snow/petal/dust/magic
    "glow_radius": [15, 20, 26, 35, 45],        # 5 档: 默认 26 (grand_finale.py)
}

# 预测时固定参数（网格外）
FIXED = {"text_opacity": 100.0, "glow_intensity": 2.5, "_pps_mult": 1.0}

# 两阶段 CNN 精排阈值
NEIGHBOR_DIST_THRESHOLD = 2.0  # z-score 欧氏距离上限, 超过则退化为 GBDT
GBDT_TOPK = 10  # 阶段1 取 top-10 给阶段2 精排


# ── 工具函数 ────────────────────────────────────────────────────────

def _gbdt_predict(tuner, feat: dict) -> dict:
    """GBDT 预测 7 维评分 (单条)。

    用 tuner["features"] 而非全局 FEATURES, 兼容旧 pkl (9 特征):
    旧 pkl 模型期望 9 维输入, 若用新 FEATURES (12 维) 会维度不匹配。
    """
    feat_names = tuner.get("features", FEATURES)
    X = np.array([[float(feat.get(f, 0.0)) for f in feat_names]])
    scores = {}
    for t in TARGETS:
        m = tuner["models"][t]
        scores[t] = float(m.predict(X)[0])
    return scores


def _gbdt_predict_batch(tuner, feat_list: list) -> list:
    """GBDT 批量预测 (网格搜索用, 单次 predict 处理全网格组合)。

    网格扩展后 (1215 → 218700), 单条 _gbdt_predict 循环太慢 (N×7 次 predict(1)),
    改批量: 7 个 target 各 1 次 predict(N) 替代, 速度提升 ~100x。
    """
    feat_names = tuner.get("features", FEATURES)
    X = np.array([[float(feat.get(f, 0.0)) for f in feat_names] for feat in feat_list],
                 dtype=float)
    preds = {t: tuner["models"][t].predict(X) for t in TARGETS}
    return [{t: float(preds[t][i]) for t in TARGETS} for i in range(len(feat_list))]


def _fmt_param(key: str, val) -> str:
    """格式化单个参数值, 分类参数显示 "数值 (字符串名)" 便于人类阅读。"""
    if key == "tint_color":
        return f"{val} ({TINT_REVMAP.get(int(val), '?')})"
    if key == "particle_template":
        return f"{val} ({PARTICLE_REVMAP.get(int(val), '?')})"
    return str(val)


def _weighted_total(scores: dict, dim_weights: dict) -> float:
    return float(sum(scores.get(t, 0.0) * dim_weights.get(t, 1) for t in TARGETS))


def _compute_zscore_stats(samples: list) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算 FEATURES 的 z-score 归一化统计量 (基于全量训练样本)。

    返回 (mean, std, valid_mask)。零方差特征 (std<1e-6) 被遮罩排除,
    不参与最近邻距离计算 (因为它们无法区分样本, 且 FIXED 取值可能与训练分布不一致,
    会导致人为放大的距离)。z-score 归一化仅作用于有方差的特征。

    注: 用 extract_feature_value 处理分类编码 (particle_template="spark"→0)
    和默认值填充 (tint_color/glow_radius 缺失), 与训练时一致。
    新增的 3 个参数当前零方差 → 自动被 valid_mask 排除。
    """
    X = np.array([[extract_feature_value(r, f) for f in FEATURES] for r in samples],
                 dtype=float)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    valid_mask = std >= 1e-6  # 零方差特征排除
    std_safe = std.copy()
    std_safe[~valid_mask] = 1.0  # 防止除零 (不会进入距离计算)
    return mean, std_safe, valid_mask


def _find_nearest_sample(combo_feat: dict, samples: list,
                         mean: np.ndarray, std: np.ndarray,
                         valid_mask: np.ndarray) -> tuple[int, float, dict]:
    """对候选组合, 在 train_samples 中找参数空间最近邻 (z-score 欧氏距离)。

    仅使用 valid_mask 为 True 的特征 (有方差的特征) 计算距离。
    返回 (sample_idx_in_jsonl, distance, sample_row)。

    注: combo_feat 来自 REC_GRID+FIXED, 值已是数值 (tint/particle 为 int 编码);
    samples 是原始 jsonl 行, 需用 extract_feature_value 编码分类字段。
    """
    cv = np.array([float(combo_feat.get(f, 0.0)) for f in FEATURES], dtype=float)
    cv_n = (cv - mean) / std
    X = np.array([[extract_feature_value(r, f) for f in FEATURES] for r in samples],
                 dtype=float)
    X_n = (X - mean) / std
    diff = (X_n - cv_n) * valid_mask  # 零方差特征贡献归零
    dists = np.sqrt((diff ** 2).sum(axis=1))
    nearest_idx = int(np.argmin(dists))
    return nearest_idx, float(dists[nearest_idx]), samples[nearest_idx]


# ── 单阶段（原逻辑保持不变） ─────────────────────────────────────────

def run_single_stage(args, tuner, dim_weights) -> int:
    keys = list(REC_GRID)
    grid_vals = [REC_GRID[k] for k in keys]
    total = int(np.prod([len(v) for v in grid_vals]))
    print(f"网格搜索 {total} 组合 (风格={args.style})")

    # 批量构造特征 + 批量预测 (网格 218700 组合, 单条 predict 太慢)
    all_combos = list(product(*grid_vals))
    all_feats = []
    for combo in all_combos:
        feat = {k: float(v) for k, v in zip(keys, combo)}
        feat.update(FIXED)
        all_feats.append(feat)
    all_scores = _gbdt_predict_batch(tuner, all_feats)

    # 选加权总分最高的组合
    best_idx = 0
    best_score = -1.0
    for i, scores in enumerate(all_scores):
        weighted = _weighted_total(scores, dim_weights)
        if weighted > best_score:
            best_score = weighted
            best_idx = i

    combo = all_combos[best_idx]
    scores = all_scores[best_idx]
    print(f"\n=== 推荐参数 (预测加权 {best_score:.1f}) ===")
    for k, v in zip(keys, combo):
        print(f"  {k}: {_fmt_param(k, v)}")
    print("\n预测评分:")
    for t in TARGETS:
        print(f"  {t}: {scores[t]:.1f}")

    out = PROJECT / "output" / "m2_iteration" / "recommend.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "style": args.style,
        "params": {k: v for k, v in zip(keys, combo)},
        "predicted_scores": scores,
        "weighted": best_score,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n推荐已保存: {out}")
    return 0


# ── 两阶段推荐 ──────────────────────────────────────────────────────

def run_two_stage(args, tuner, dim_weights) -> int:
    """GBDT 初筛 top-10 → CNN 精排 → final top-N。"""
    from core.cnn_scorer import load_head, _pred_to_scores  # 复用生产头

    samples_path = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
    emb_path = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
    if not samples_path.exists():
        print(f"训练样本不存在: {samples_path}")
        return 1
    if not emb_path.exists():
        print(f"CLIP 嵌入不存在: {emb_path}")
        return 1

    samples = [json.loads(l) for l in samples_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    z = np.load(emb_path)
    emb_arr, sample_idx_arr = z["emb"], z["sample_idx"]
    # sample_idx → embedding 映射 (npz 第 i 行对应 sample_idx[i] 在 jsonl 中的行号)
    idx_to_emb = {int(sidx): emb_arr[i] for i, sidx in enumerate(sample_idx_arr)}
    print(f"加载 {len(samples)} 训练样本 + {len(emb_arr)} CLIP 嵌入 (两阶段模式)")

    keys = list(REC_GRID)
    grid_vals = [REC_GRID[k] for k in keys]
    total = int(np.prod([len(v) for v in grid_vals]))
    print(f"阶段1: GBDT 网格搜索 {total} 组合 → 取 top-{GBDT_TOPK}")

    # 阶段1: 全网格 GBDT 批量预测 + 加权排序 (网格大, 用 batch predict)
    combo_list = list(product(*grid_vals))
    feat_list = []
    for combo in combo_list:
        feat = {k: float(v) for k, v in zip(keys, combo)}
        feat.update(FIXED)
        feat_list.append(feat)
    score_list = _gbdt_predict_batch(tuner, feat_list)
    all_combos = []
    for feat, scores in zip(feat_list, score_list):
        weighted = _weighted_total(scores, dim_weights)
        all_combos.append({"feat": feat, "scores": scores, "weighted": weighted})
    all_combos.sort(key=lambda x: -x["weighted"])
    gbdt_top10 = all_combos[:GBDT_TOPK]

    print(f"  GBDT top-1 加权 = {gbdt_top10[0]['weighted']:.3f}")
    print(f"  GBDT top-10 加权区间 = [{gbdt_top10[-1]['weighted']:.3f}, {gbdt_top10[0]['weighted']:.3f}]")

    # 阶段2: CNN 精排 (参数空间最近邻 → 已有样本 CLIP 嵌入 → CNN 头预测)
    print(f"\n阶段2: CNN 精排 (最近邻阈值={NEIGHBOR_DIST_THRESHOLD})")
    _ = load_head()  # 预加载生产头, 失败立即抛
    mean, std, valid_mask = _compute_zscore_stats(samples)
    n_valid = int(valid_mask.sum())
    excluded = [FEATURES[i] for i, m in enumerate(valid_mask) if not m]
    if excluded:
        print(f"  零方差特征 (排除出距离计算): {excluded}")
    print(f"  参与距离计算的特征数: {n_valid}/{len(FEATURES)}")

    cnn_rerank = []
    warnings = []
    neighbor_hits = 0
    for rank, c in enumerate(gbdt_top10):
        feat = c["feat"]
        nn_i, dist, _ = _find_nearest_sample(feat, samples, mean, std, valid_mask)
        used_neighbor = dist <= NEIGHBOR_DIST_THRESHOLD and nn_i in idx_to_emb
        if used_neighbor:
            cnn_scores = _pred_to_scores(idx_to_emb[nn_i])
            neighbor_hits += 1
        else:
            cnn_scores = dict(c["scores"])  # 退化为 GBDT 值
            if dist > NEIGHBOR_DIST_THRESHOLD:
                warnings.append(
                    f"GBDT rank={rank} (psize={feat['psize_scale']}, "
                    f"punch={feat['punch_amount']}, shake={feat['shake_amp']}) "
                    f"最近邻距离={dist:.2f} > {NEIGHBOR_DIST_THRESHOLD}, 退化为 GBDT 值"
                )
            elif nn_i not in idx_to_emb:
                warnings.append(
                    f"GBDT rank={rank} 近邻 sample_idx={nn_i} 无对应 CLIP 嵌入, 退化为 GBDT 值"
                )
            used_neighbor = False
        cnn_weighted = _weighted_total(cnn_scores, dim_weights)
        cnn_rerank.append({
            "params": {k: c["feat"][k] for k in keys},
            "gbdt_scores": {k: round(v, 3) for k, v in c["scores"].items()},
            "cnn_scores": {k: round(v, 3) for k, v in cnn_scores.items()},
            "gbdt_weighted": round(c["weighted"], 4),
            "cnn_weighted": round(cnn_weighted, 4),
            "used_neighbor": used_neighbor,
            "neighbor_sample_idx": int(nn_i) if used_neighbor else None,
            "neighbor_distance": round(dist, 3),
            "gbdt_rank": rank,
        })

    # 按 cnn_weighted 降序重排
    cnn_sorted = sorted(cnn_rerank, key=lambda x: -x["cnn_weighted"])
    for new_rank, item in enumerate(cnn_sorted):
        item["cnn_rank"] = new_rank
        item["rank_delta"] = item["gbdt_rank"] - new_rank  # 正=上升, 负=下降

    final_topN = cnn_sorted[:args.topn]
    print(f"  CNN 命中近邻 {neighbor_hits}/{GBDT_TOPK} 个候选 (其余退化为 GBDT)")
    if warnings:
        print(f"  警告 {len(warnings)} 条")
    print(f"  CNN 重排后 top-1 加权 = {cnn_sorted[0]['cnn_weighted']:.3f}")

    # 单阶段 top-1 对照 (用于报告提升点)
    single_top1 = gbdt_top10[0]
    two_stage_top1 = cnn_sorted[0]

    # 落盘 recommend.json (含 two_stage 字段, 同时保留 legacy 字段便于兼容)
    out = PROJECT / "output" / "m2_iteration" / "recommend.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "style": args.style,
        "mode": "two_stage",
        "topn": args.topn,
        # legacy 兼容字段 (= 两阶段 final top-1)
        "params": two_stage_top1["params"],
        "predicted_scores": two_stage_top1["cnn_scores"],
        "weighted": two_stage_top1["cnn_weighted"],
        # 两阶段详情
        "two_stage": {
            "gbdt_top10": [{
                "gbdt_rank": i,
                "params": {k: float(c["feat"][k]) for k in keys},
                "gbdt_scores": {k: round(v, 3) for k, v in c["scores"].items()},
                "gbdt_weighted": round(c["weighted"], 4),
            } for i, c in enumerate(gbdt_top10)],
            "cnn_rerank": cnn_sorted,
            "final_top3": final_topN,
            "neighbor_hits": neighbor_hits,
            "neighbor_total": GBDT_TOPK,
            "threshold": NEIGHBOR_DIST_THRESHOLD,
            "warnings": warnings,
        },
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n推荐已保存: {out}")

    # 控制台打印最终 top-N
    print(f"\n=== 两阶段 final top-{args.topn} (CNN 精排后) ===")
    for i, item in enumerate(final_topN):
        p = item["params"]
        print(f"  #{i+1}  psize={p['psize_scale']} punch={p['punch_amount']} "
              f"shake={p['shake_amp']} chroma={p['chromatic_amount']} "
              f"glow={p['_glow_mult']} tsize={p['text_size']}")
        print(f"       tint={_fmt_param('tint_color', p['tint_color'])} "
              f"part={_fmt_param('particle_template', p['particle_template'])} "
              f"gr={p['glow_radius']}")
        print(f"       cnn_weighted={item['cnn_weighted']:.3f} "
              f"(gbdt_rank={item['gbdt_rank']} → cnn_rank={item['cnn_rank']}, "
              f"delta={item['rank_delta']:+d}, neighbor={item['used_neighbor']})")

    # 写对比报告
    _write_report(args, keys, gbdt_top10, cnn_sorted, final_topN,
                  single_top1, two_stage_top1, neighbor_hits, warnings)
    return 0


def _write_report(args, keys, gbdt_top10, cnn_sorted, final_topN,
                  single_top1, two_stage_top1, neighbor_hits, warnings) -> None:
    """写两阶段 vs 单阶段对比报告到 tmp/two_stage_recommend.txt。"""
    report_path = PROJECT / "tmp" / "two_stage_recommend.txt"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def _fmt_params(p: dict) -> str:
        tint_v = int(p.get('tint_color', 0))
        part_v = int(p.get('particle_template', 0))
        return (f"psize={p['psize_scale']} punch={p['punch_amount']} "
                f"shake={p['shake_amp']} chroma={p['chromatic_amount']} "
                f"glow={p['_glow_mult']} tsize={p['text_size']} "
                f"tint={tint_v}({TINT_REVMAP.get(tint_v,'?')}) "
                f"part={part_v}({PARTICLE_REVMAP.get(part_v,'?')}) "
                f"gr={p.get('glow_radius', 26)}")

    lines = []
    lines.append("=" * 72)
    lines.append("两阶段参数推荐报告 (GBDT 初筛 + CNN 精排)")
    lines.append("=" * 72)
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"风格卡  : {args.style}")
    lines.append(f"topn    : {args.topn}")
    lines.append(f"近邻阈值: {NEIGHBOR_DIST_THRESHOLD} (z-score 欧氏距离)")
    lines.append(f"网格规模: {int(np.prod([len(REC_GRID[k]) for k in REC_GRID]))} 组合")
    lines.append("")

    # 阶段1 GBDT top-10
    lines.append("-" * 72)
    lines.append(f"阶段1 GBDT 初筛 top-{GBDT_TOPK}:")
    lines.append("-" * 72)
    lines.append(f"{'rank':>4}  {'weighted':>8}  params")
    for i, c in enumerate(gbdt_top10):
        p = {k: c["feat"][k] for k in keys}
        lines.append(f"{i:>4}  {c['weighted']:>8.3f}  {_fmt_params(p)}")
    lines.append("")

    # 阶段2 CNN 精排
    lines.append("-" * 72)
    lines.append(f"阶段2 CNN 精排 (重排后 top-{GBDT_TOPK}):")
    lines.append("-" * 72)
    lines.append(f"{'new':>4} {'old':>4} {'delta':>6} {'cnn_w':>8} {'gbdt_w':>8} "
                 f"{'nbr':>4} {'dist':>6}  params")
    for item in cnn_sorted:
        p = item["params"]
        lines.append(
            f"{item['cnn_rank']:>4} {item['gbdt_rank']:>4} "
            f"{item['rank_delta']:>+6} {item['cnn_weighted']:>8.3f} "
            f"{item['gbdt_weighted']:>8.3f} "
            f"{'Y' if item['used_neighbor'] else 'N':>4} "
            f"{item['neighbor_distance']:>6.2f}  {_fmt_params(p)}"
        )
    lines.append("")

    # 最终 top-N 推荐
    lines.append("-" * 72)
    lines.append(f"最终 top-{args.topn} 推荐 (CNN 精排后):")
    lines.append("-" * 72)
    for i, item in enumerate(final_topN):
        p = item["params"]
        lines.append(f"#{i+1}  {_fmt_params(p)}")
        lines.append(f"     CNN 加权总分: {item['cnn_weighted']:.3f}  "
                     f"(GBDT 加权: {item['gbdt_weighted']:.3f})")
        lines.append(f"     GBDT rank={item['gbdt_rank']} → CNN rank={item['cnn_rank']} "
                     f"(变化 {item['rank_delta']:+d})")
        lines.append("     预测评分 (CNN):")
        for t in TARGETS:
            lines.append(f"       {t:<22} = {item['cnn_scores'][t]:.2f}")
        if item["used_neighbor"]:
            lines.append(f"     近邻样本: sample_idx={item['neighbor_sample_idx']} "
                         f"距离={item['neighbor_distance']:.3f}")
        else:
            lines.append("     近邻样本: 无 (退化为 GBDT 值)")
        lines.append("")

    # 两阶段 vs 单阶段对比
    lines.append("-" * 72)
    lines.append("两阶段 vs 单阶段 对比:")
    lines.append("-" * 72)
    sp = {k: single_top1["feat"][k] for k in keys}
    tp = two_stage_top1["params"]
    lines.append(f"单阶段 top-1 (GBDT): {_fmt_params(sp)}")
    lines.append(f"  加权 = {single_top1['weighted']:.3f}")
    lines.append(f"两阶段 top-1 (CNN) : {_fmt_params(tp)}")
    lines.append(f"  加权 = {two_stage_top1['cnn_weighted']:.3f}  "
                 f"(GBDT 加权 = {two_stage_top1['gbdt_weighted']:.3f})")
    if sp == tp:
        lines.append("→ 两阶段与单阶段 top-1 一致 (CNN 精排确认 GBDT 选择)")
    else:
        lines.append("→ 两阶段 top-1 与单阶段不同 (CNN 精排修正了 GBDT 排序):")
        for k in keys:
            if sp[k] != tp[k]:
                lines.append(f"   • {k}: {sp[k]} → {tp[k]}")
    lines.append("")

    # 排名变化
    risers = [it for it in cnn_sorted if it["rank_delta"] > 0]
    fallers = [it for it in cnn_sorted if it["rank_delta"] < 0]
    lines.append(f"排名上升: {len(risers)} 个候选 (CNN 精排后位次提前)")
    for it in risers[:5]:
        lines.append(f"  • GBDT rank={it['gbdt_rank']} → CNN rank={it['cnn_rank']} "
                     f"(+{it['rank_delta']})  {_fmt_params(it['params'])}")
    lines.append(f"排名下降: {len(fallers)} 个候选")
    for it in fallers[:5]:
        lines.append(f"  • GBDT rank={it['gbdt_rank']} → CNN rank={it['cnn_rank']} "
                     f"({it['rank_delta']:+d})  {_fmt_params(it['params'])}")
    lines.append("")

    # 提升点总结
    lines.append("-" * 72)
    lines.append("两阶段相比单阶段的提升点:")
    lines.append("-" * 72)
    lines.append(f"1. CNN 命中近邻: {neighbor_hits}/{GBDT_TOPK} 个候选用 CLIP 嵌入精排 "
                 f"(命中率 {neighbor_hits/GBDT_TOPK*100:.0f}%)")
    lines.append(f"2. 候选区分度  : CNN 重排后 top-1 加权 = {two_stage_top1['cnn_weighted']:.3f}, "
                 f"GBDT top-1 加权 = {single_top1['weighted']:.3f}")
    if sp != tp:
        lines.append("3. 推荐修正    : CNN 精排改变了 top-1 选择, 综合视觉特征而非纯参数回归")
    else:
        lines.append("3. 推荐确认    : CNN 精排确认了 GBDT top-1, 推荐可信度提升")
    lines.append(f"4. 排名变动    : {len(risers)} 上升 / {len(fallers)} 下降 / "
                 f"{GBDT_TOPK - len(risers) - len(fallers)} 不变")
    if warnings:
        lines.append(f"5. 警告        : {len(warnings)} 条 (距离超阈值, 已退化)")
        for w in warnings[:3]:
            lines.append(f"   - {w}")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"对比报告已保存: {report_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="edit")
    ap.add_argument("--two-stage", action="store_true",
                    help="启用 GBDT+CNN 两阶段推荐 (默认单阶段)")
    ap.add_argument("--topn", type=int, default=3,
                    help="最终输出推荐数量 (仅 --two-stage 时生效, 默认 3)")
    args = ap.parse_args()

    model_path = PROJECT / "models" / "output" / "param_tuner.pkl"
    if not model_path.exists():
        print(f"调参器不存在: {model_path}（先跑 train_param_tuner.py）")
        return 1
    with open(model_path, "rb") as f:
        tuner = pickle.load(f)

    # 权重: 按风格卡维度优先级
    weights = get_dim_priority(args.style)
    dim_weights = {f"score_{k}": w for k, w in weights.items()}

    if args.two_stage:
        return run_two_stage(args, tuner, dim_weights)
    return run_single_stage(args, tuner, dim_weights)


if __name__ == "__main__":
    sys.exit(main())
