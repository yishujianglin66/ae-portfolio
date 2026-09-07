"""build_gold_set.py — 调参器黄金集筛选（OpenSeeker-v2 式"精选数据"落地）

方法论依据 (2026-08-16 技术路线参考):
  OpenSeeker-v2 "1万条精选数据 + SFT 击败 RL 巨头" → 高质量人工标注小数据集
  优于堆叠合成数据。本脚本从合成采样的调参器数据中**自动筛选高信息量样本**,
  产出黄金候选集供专家(用户)人工校准标签。

为什么需要黄金集:
  - 合成采样 112 样本中唯一参数组合仅 62 (50 条重复冗余, 对训练无增量)
  - qwen 自动评分是模型标签, 存在系统偏差; 参数-评分关系非单调
    (dynamism 8.5 同时出现在 psize 0.6 和 1.3), 模型吃不准的样本最需人工锚定
  - 黄金集 = 高质量人工标注锚点: 用于评测基准替代随机 LOOCV / 未来 SFT 种子

信息量指标 (四维加权):
  a. 评分极值: 标签落在维度高低两端 (方差贡献最大)
  b. 参数边界: psize/chroma 等关键参数取极值档
  c. 模型分歧: qwen 标签 vs CNN 预测 vs GBDT 预测的差距 (分歧 = 标签最需校准)
  d. 反直觉样本: 高分却用"理论上该降分"的参数组合 (非单调关系锚点)

输出:
  output/m2_iteration/gold_candidates.jsonl  按信息量排序的候选 (含三模型评分)
  output/m2_iteration/gold_candidates_summary.txt  审阅说明 + 帧路径

用法:
  python scripts/build_gold_set.py [--top 20]
  人工校准: 打开 gold_candidates.jsonl, 对每条审阅 qwen/CNN/GBDT 三方评分,
  在 "gold_label" 字段写入校准后的 7 维评分 → 存为 gold_set.jsonl
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

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
EMB = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
CLEAN_IDX = PROJECT / "data" / "param_tuning" / "clean_index.json"
CNN_HEAD = PROJECT / "models" / "output" / "cnn_param_head.pkl"
GBDT_TUNER = PROJECT / "models" / "output" / "param_tuner.pkl"

DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]
# 关键参数极值档 (参数边界覆盖)
EDGE_PARAMS = {"psize_scale": {0.6, 1.6}, "chromatic_amount": {6, 25},
               "punch_amount": {6, 14}, "shake_amp": {8, 20}}


def load_models():
    """加载 CNN Ridge 头 + GBDT 调参器"""
    cnn = None
    if CNN_HEAD.exists():
        with open(CNN_HEAD, "rb") as f:
            cnn = pickle.load(f)
    gbdt = None
    if GBDT_TUNER.exists():
        with open(GBDT_TUNER, "rb") as f:
            gbdt = pickle.load(f)
    return cnn, gbdt


def predict_cnn(cnn, emb):
    """CNN 头预测 7 维 (无嵌入时返回 None)"""
    if cnn is None:
        return None
    from sklearn.linear_model import Ridge  # noqa: F401  (确保 sklearn 已导入)
    pred = cnn["model"].predict(emb.reshape(1, -1))[0]
    return {t: float(v) for t, v in zip(cnn["targets"], pred)}


def predict_gbdt(gbdt, row):
    """GBDT 调参器预测 7 维"""
    if gbdt is None:
        return None
    feats = gbdt["features"]
    X = np.array([[float(row.get(f, 0.0)) for f in feats]])
    return {t: float(gbdt["models"][t].predict(X)[0]) for t in gbdt["targets"]}


def info_score(row, qwen, cnn_pred, gbdt_pred):
    """四维信息量加权"""
    s = 0.0
    # a. 评分极值贡献 (各维离中位数越远信息量越高)
    dim_vals = [row.get(d, 0) for d in DIMS]
    s += 0.3 * sum(abs(v - 5.5) for v in dim_vals) / len(DIMS)
    # b. 参数边界覆盖
    n_edge = sum(1 for k, edges in EDGE_PARAMS.items() if row.get(k) in edges)
    s += 0.2 * (n_edge / len(EDGE_PARAMS))
    # c. 模型分歧 (qwen vs CNN vs GBDT 三方距离)
    parties = [("qwen", qwen)]
    if cnn_pred:
        parties.append(("cnn", cnn_pred))
    if gbdt_pred:
        parties.append(("gbdt", gbdt_pred))
    if len(parties) >= 2:
        divs = []
        for a in range(len(parties)):
            for b in range(a + 1, len(parties)):
                _, pa = parties[a]
                _, pb = parties[b]
                div = sum(abs(pa.get(d, 0) - pb.get(d, 0)) for d in DIMS) / len(DIMS)
                divs.append(div)
        s += 0.35 * (sum(divs) / len(divs))
    # d. 反直觉: 高分却用"该降分"的极值参数 (dynamism 高 + psize 大 → 非单调锚点)
    dynamism = row.get("score_dynamism", 0)
    psize = row.get("psize_scale", 1.0)
    if dynamism >= 8 and psize >= 1.3:
        s += 0.5
    if row.get("score_texture", 0) <= 3 and psize <= 0.7:
        s += 0.3
    return round(s, 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20, help="输出候选数")
    ap.add_argument("--offset", type=int, default=0,
                    help="跳过已校准的 top N (增量筛选: 首轮 0, 二轮 20 筛 id 21-40)")
    ap.add_argument("--clean", action="store_true",
                    help="只筛干净对齐样本 (帧目录唯一, 读 clean_index.json); "
                         "共享帧目录样本已错位不可信")
    args = ap.parse_args()

    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.clean:
        clean_idx = set(json.loads(CLEAN_IDX.read_text(encoding="utf-8"))["clean_row_idx"])
        rows = [(i, r) for i, r in enumerate(rows) if i in clean_idx]  # (原始行号, 样本)
        print(f"[clean] 过滤为 {len(rows)} 个唯一对齐样本")
    else:
        rows = [(i, r) for i, r in enumerate(rows)]
    with_fd = [r for _, r in rows if r.get("frame_dir")]
    cnn, gbdt = load_models()
    emb_data = None
    if EMB.exists():
        emb_data = np.load(EMB)
        # 嵌入 → 原始 jsonl 行号映射
        row_of_emb = {int(i): idx for idx, i in enumerate(emb_data["sample_idx"])}
    print(f"样本 {len(rows)} (带帧 {len(with_fd)}) | CNN头 {'有' if cnn else '无'} | GBDT {'有' if gbdt else '无'}")

    scored = []
    for orig_idx, r in rows:
        qwen = {d: r.get(d, 0) for d in DIMS}
        cnn_pred = None
        if emb_data is not None and r.get("frame_dir"):
            # 嵌入按"原始 jsonl 行号"对齐 (与编码脚本 sample_idx 一致)
            if orig_idx in row_of_emb:
                cnn_pred = predict_cnn(cnn, emb_data["emb"][row_of_emb[orig_idx]])
        gbdt_pred = predict_gbdt(gbdt, r)
        score = info_score(r, qwen, cnn_pred, gbdt_pred)
        scored.append({
            "row": r,
            "info_score": score,
            "qwen": qwen,
            "cnn": cnn_pred,
            "gbdt": gbdt_pred,
        })
    scored.sort(key=lambda x: -x["info_score"])
    top = scored[args.offset:args.offset + args.top]
    out_cand = PROJECT / "output" / "m2_iteration" / "gold_candidates.jsonl"
    out_sum = PROJECT / "output" / "m2_iteration" / "gold_candidates_summary.txt"
    out_cand.parent.mkdir(parents=True, exist_ok=True)

    with open(out_cand, "w", encoding="utf-8") as f, open(out_sum, "w", encoding="utf-8") as s:
        s.write("调参器黄金集候选 — 人工校准说明\n" + "=" * 60 + "\n")
        s.write(f"从 {len(rows)} 合成样本筛出第 {args.offset + 1}-{args.offset + len(top)} 高信息量候选。\n")
        s.write("校准方法: 打开 gold_candidates.jsonl, 查看每条 frame_dir 的渲染帧,"
                "对照 qwen/cnn/gbdt 三方评分, 在 gold_label 字段写入你的 7 维校准评分。\n\n")
        for n, sc in enumerate(top, 1):
            cid = args.offset + n  # 全局候选 id (首轮 1-20, 二轮 21-40...)
            r = sc["row"]
            frame_dir = r.get("frame_dir", "(无帧)")
            s.write(f"[{cid:02d}] info={sc['info_score']} | frame: {frame_dir}\n")
            s.write(f"     参数: psize={r.get('psize_scale')} punch={r.get('punch_amount')} "
                    f"shake={r.get('shake_amp')} chroma={r.get('chromatic_amount')} "
                    f"text_size={r.get('text_size')} glow={r.get('_glow_mult')}\n")
            s.write(f"     qwen: {sc['qwen']}\n")
            if sc["cnn"]:
                s.write(f"     cnn : {sc['cnn']}\n")
            if sc["gbdt"]:
                s.write(f"     gbdt: {sc['gbdt']}\n")
            s.write("\n")
            rec = {
                "id": cid,
                "info_score": sc["info_score"],
                "params": {k: r.get(k) for k in ["psize_scale", "punch_amount", "shake_amp",
                                                 "chromatic_amount", "text_size", "_glow_mult"]},
                "frame_dir": frame_dir,
                "qwen": {d: round(sc["qwen"].get(d, 0), 2) for d in DIMS},
                "cnn": {d: round(sc["cnn"].get(d, 0), 2) for d in DIMS} if sc["cnn"] else None,
                "gbdt": {d: round(sc["gbdt"].get(d, 0), 2) for d in DIMS} if sc["gbdt"] else None,
                "gold_label": None,  # 专家校准: 写 7 维 {score_dynamism:..., ...}
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"黄金集候选: {out_cand}\n审阅说明: {out_sum}")
    print("校准后另存为 gold_set.jsonl, 即可作为评测基准/SFT 种子")
    return 0


if __name__ == "__main__":
    sys.exit(main())
