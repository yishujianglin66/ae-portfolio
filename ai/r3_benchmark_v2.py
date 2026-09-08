# -*- coding: utf-8 -*-
r"""R3 检索基准 v2（硬化版，2026-09-08 晚）。

动机（档1 实测教训，output/evidence/r3_tier1_rerank_20260908/CONCLUSION.md）:
  T11 旧基准在伪标签扩充索引（1075 条）下饱和——关键词通道的别名映射+2-gram
  模糊匹配使 recall 恒为 1.000，任何模型改动都测不出差异。

硬化设计:
  1. HELD_OUT_QUERIES: 措辞刻意避开 CHAR_TO_IP 键、IP_VISUAL_KW 值与 IP 名本身，
     用场景描述/特征白描迫使语义通道工作；关键词通道在这些查询上预期 miss
     （脚本逐查询输出 keyword_hits 诊断验证这一点）。
  2. 指标升级: recall@5/@10（沿用 T11 口径）+ nDCG@10（binary gain）+ MRR@10。
  3. 四臂对照:
     A = 生产链路 hybrid（关键词+语义 RRF）top10
     B = 纯语义 top10（测 BGE-M3 裸分辨力）
     C = hybrid 候选池30 + bge-reranker-v2-m3 重排（档1 配置）
     D = 纯语义候选池30 + reranker 重排（重排器净效应）
  4. 混淆天然存在: 伪标签条目含跨 IP 同关键词（"战斗""火焰"在多 IP 描述中），
     索引 1075 条、每 IP ≈50 条，top10 分辨直接反映在 recall/nDCG 上。

证据落盘: output/evidence/r3_benchmark_v2_20260908/
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")

EVIDENCE_DIR = ROOT / "output" / "evidence" / "r3_benchmark_v2_20260908"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30

# ---------------------------------------------------------------------------
# Held-out 查询集（35 条）：措辞避开别名表与 IP 名，场景白描为主。
# 每条经过人工核对：不含 CHAR_TO_IP 任何键、不含该 IP 的 IP_VISUAL_KW 值。
# ---------------------------------------------------------------------------
HELD_OUT_QUERIES = [
    # 进击的巨人（避开: 巨人/战斗/立体机动装置/城墙/变身/热血/艾伦/利威尔/兵长/调查兵团等）
    ("高墙之内的人类反抗被吃的命运", "进击的巨人"),
    ("喷气管索在楼宇之间高速飞跃", "进击的巨人"),
    # 无限滑板（避开: 滑板/SK8/运动/青春）
    ("踩着带轮的板子冲下盘山公路", "无限滑板"),
    ("街头轮上竞速的少年对决", "无限滑板"),
    # 海贼王（别名表无此 IP，任何白描都靠语义）
    ("草帽船长的橡胶伸缩拳", "海贼王"),
    ("三刀流剑士咬刀冲锋", "海贼王"),
    ("要当上海上之王的男人", "海贼王"),
    # 灼眼的夏娜
    ("红发红瞳少女挥舞太刀", "灼眼的夏娜"),
    ("炎发灼眼的讨伐者", "灼眼的夏娜"),
    # 黑岩射手
    ("蓝焰眼眸的黑衣双马尾少女", "黑岩射手"),
    ("扛巨型岩炮射击的少女", "黑岩射手"),
    # FATE
    ("召唤英灵争夺圣杯的战争", "FATE"),
    ("金发骑士王高举圣剑", "FATE"),
    ("魔术师与从者缔结契约", "FATE"),
    # 时光代理人
    ("钻进照片里改变过去", "时光代理人"),
    ("照相馆 duo 穿越影像完成委托", "时光代理人"),
    # 赛博朋克：边缘行者
    ("夜之城义体改造雇佣兵", "赛博朋克：边缘行者"),
    ("霓虹都市底层少年的义肢强化", "赛博朋克：边缘行者"),
    # 咒术回战
    ("蒙眼教师摘下眼罩的瞬间", "咒术回战"),
    ("吞下诅咒手指的少年", "咒术回战"),
    ("领域展开结界内对决", "咒术回战"),
    # 火影忍者（避开: 忍者/查克拉/螺旋丸/写轮眼）
    ("体内封印九尾妖狐的孤儿", "火影忍者"),
    ("拉面店常客的金发护额少年", "火影忍者"),
    # 地缚少年花子君
    ("旧校舍女厕的幽灵少年", "地缚少年花子君"),
    ("校园七大不可思议实现愿望", "地缚少年花子君"),
    # 龙族
    ("身负屠龙血脉的少年入学", "龙族"),
    ("言灵之力在雨夜觉醒", "龙族"),
    # 斩·赤红之瞳（避开: 赤瞳/暗杀/暗杀者/暗杀组织/剑/血/战斗/悲伤）
    ("帝具使之间的生死对决", "斩·赤红之瞳"),
    ("夜袭杀手集团的粉发狙击手", "斩·赤红之瞳"),
    # 某科学的超电磁炮（避开: 御坂美琴/超能力/电击/常盘台/蓝/能量/冰晶）
    ("学园都市抛硬币当炮弹的少女", "某科学的超电磁炮"),
    ("电磁之力操纵铁砂", "某科学的超电磁炮"),
    # 鬼灭之刃（避开: 柱/呼吸法/鬼杀队/火焰/日轮刀/呼吸/剑/鬼/和风）
    ("背着木箱卖炭少年的救妹之旅", "鬼灭之刃"),
    ("水面斩击泛起波纹的刀光", "鬼灭之刃"),
    # K
    ("红蓝双王对峙达摩克利斯高悬", "K"),
    # 浪客行
    ("二刀流浪人的悟道之旅", "浪客行"),
    # JOJO（避开: 替身/替身使者/纳兰迦/航空史密斯/Stand/姿势/肌肉）
    ("黄金之风黑帮少年的秧歌梦", "JOJO的奇妙冒险"),
]


def _log(msg: str):
    print(f"[R3-V2] {msg}", flush=True)


def _is_relevant(entry: dict, expected_ip: str) -> bool:
    return (expected_ip in entry.get("ip_names", []) or
            expected_ip in entry.get("primary_ip", ""))


def _recall_at_k(hits: list, entries: list, expected_ip: str, k: int) -> float:
    n_expected = max(1, sum(1 for e in entries if _is_relevant(e, expected_ip)))
    ip_hits = sum(1 for h in hits[:k] if _is_relevant(h, expected_ip))
    return ip_hits / min(k, n_expected)


def _ndcg_at_k(hits: list, expected_ip: str, k: int = 10) -> float:
    dcg = sum((1.0 if _is_relevant(h, expected_ip) else 0.0) / math.log2(i + 2)
              for i, h in enumerate(hits[:k]))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(k))
    return dcg / idcg if idcg > 0 else 0.0


def _mrr_at_k(hits: list, expected_ip: str, k: int = 10) -> float:
    for i, h in enumerate(hits[:k]):
        if _is_relevant(h, expected_ip):
            return 1.0 / (i + 1)
    return 0.0


def _entry_text(e: dict) -> str:
    parts = [e.get("description", ""), " ".join(e.get("ip_names", [])),
             e.get("mood", ""), e.get("scene_type", "")]
    return " ".join(p for p in parts if p).strip() or e.get("primary_ip", "")


def run_eval():
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from ai.t11_hybrid_search import (
        TEST_QUERIES, build_semantic_index, enrich_with_pseudolabels,
        hybrid_search, keyword_search, load_intel_cache, semantic_search,
    )

    _log("=" * 60)
    _log("R3 检索基准 v2（硬化版）：held-out 查询 + nDCG/MRR + 四臂对照")
    _log("=" * 60)

    _log("\n[1/4] 加载模型...")
    t0 = time.time()
    model = SentenceTransformer("BAAI/bge-m3")
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    _log(f"  双模型加载 {time.time()-t0:.1f}s")

    _log("\n[2/4] 构建索引（与 T11 同口径）...")
    entries = load_intel_cache()
    entries = enrich_with_pseudolabels(entries, max_per_ip=50)
    _log(f"  条目: {len(entries)}")
    embeddings = build_semantic_index(entries, model)

    hash_to_entry = {e["file_hash"]: e for e in entries}

    def arm_a(query, top_k=10):  # 生产 hybrid
        return hybrid_search(entries, embeddings, model, query, top_k=top_k)

    def arm_b(query, top_k=10):  # 纯语义
        q_emb = model.encode([query])[0]
        hashes = semantic_search(embeddings, entries, q_emb, top_k=top_k)
        return [hash_to_entry[h] for h in hashes]

    def _rerank(query, pool):
        if not pool:
            return []
        pairs = [(query, _entry_text(e)) for e in pool]
        scores = reranker.predict(pairs)
        order = np.argsort(scores)[::-1]
        return [pool[i] for i in order]

    def arm_c(query):  # hybrid 池 + 重排（档1 配置）
        return _rerank(query, arm_a(query, top_k=CANDIDATE_POOL))

    def arm_d(query):  # 纯语义池 + 重排（净效应）
        return _rerank(query, arm_b(query, top_k=CANDIDATE_POOL))

    arms = {"A_hybrid": arm_a, "B_semantic": arm_b,
            "C_hybrid_rerank": arm_c, "D_semantic_rerank": arm_d}

    # ------------------------------------------------------------------
    _log(f"\n[3/4] 四臂评测：held-out {len(HELD_OUT_QUERIES)} 条 + legacy {len(TEST_QUERIES)} 条")
    per_query = []
    for qset_name, qset in (("heldout", HELD_OUT_QUERIES), ("legacy", TEST_QUERIES)):
        for query, expected_ip in qset:
            kw_hits = len(keyword_search(entries, query))  # 关键词通道诊断
            row = {"set": qset_name, "query": query, "expected_ip": expected_ip,
                   "keyword_channel_hits": kw_hits}
            for arm_name, arm_fn in arms.items():
                hits = arm_fn(query)
                row[arm_name] = {
                    "recall@5": round(_recall_at_k(hits, entries, expected_ip, 5), 3),
                    "recall@10": round(_recall_at_k(hits, entries, expected_ip, 10), 3),
                    "nDCG@10": round(_ndcg_at_k(hits, expected_ip, 10), 3),
                    "MRR@10": round(_mrr_at_k(hits, expected_ip, 10), 3),
                }
            per_query.append(row)

    # ------------------------------------------------------------------
    _log("\n[4/4] 汇总")
    summary = {}
    for qset_name in ("heldout", "legacy"):
        rows = [r for r in per_query if r["set"] == qset_name]
        if not rows:
            continue
        summary[qset_name] = {"n_queries": len(rows)}
        for arm_name in arms:
            summary[qset_name][arm_name] = {
                m: round(float(np.mean([r[arm_name][m] for r in rows])), 3)
                for m in ("recall@5", "recall@10", "nDCG@10", "MRR@10")
            }
        summary[qset_name]["keyword_channel_hits_avg"] = round(
            float(np.mean([r["keyword_channel_hits"] for r in rows])), 1)

    # 打印汇总表
    for qset_name, s in summary.items():
        _log(f"\n  == {qset_name}（{s['n_queries']} 条，关键词通道平均命中 {s['keyword_channel_hits_avg']} 条）==")
        _log(f"  {'臂':<20}{'R@5':>7}{'R@10':>7}{'nDCG@10':>9}{'MRR@10':>8}")
        for arm_name in arms:
            m = s[arm_name]
            _log(f"  {arm_name:<20}{m['recall@5']:>7.3f}{m['recall@10']:>7.3f}"
                 f"{m['nDCG@10']:>9.3f}{m['MRR@10']:>8.3f}")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": "R3 检索基准 v2（硬化版）",
        "hardening": [
            "held-out 查询：措辞避开 CHAR_TO_IP/IP_VISUAL_KW/IP 名（35 条）",
            "指标：recall@5/@10 + nDCG@10(binary) + MRR@10",
            "四臂：A生产hybrid / B纯语义 / C档1配置 / D语义池+重排净效应",
        ],
        "retriever": "BAAI/bge-m3", "reranker": RERANKER_MODEL,
        "candidate_pool": CANDIDATE_POOL, "n_entries": len(entries),
        "summary": summary, "per_query": per_query,
    }
    report_path = EVIDENCE_DIR / "r3_benchmark_v2_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    _log(f"\n  证据: {report_path}")
    return report


if __name__ == "__main__":
    run_eval()
