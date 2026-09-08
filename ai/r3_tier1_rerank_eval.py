# -*- coding: utf-8 -*-
r"""R3 档1: bge-reranker-v2-m3 二阶段重排评测（2026-09-08 修正方案 §三-R3 档1）。

架构（在 T11 混合检索之上加重排级）:
  候选池: T11 原链路（关键词 + BGE-M3 语义 → RRF 融合）取 top_N（默认 30）
  重排级: BAAI/bge-reranker-v2-m3 CrossEncoder 对 (query, description) 打分重排
  输出:   重排后 top_k

评测口径:
  - 与 T11 同一 TEST_QUERIES（20 条跨措辞查询）、同一 recall 定义
    recall@K = 命中期望IP数 / min(K, 该IP条目总数)
  - 双臂对照: 原链路 top_k vs 重排后 top_k（K=5 与 K=10 各报一次）
  - 验收线（档1）: recall@10 ≥ 0.70

证据落盘: output/evidence/r3_tier1_rerank_20260908/

铁律: 接入即蒸馏 —— 本脚本只做评测，不改 T11 生产链路；
     若验收通过，重排级以配置开关接入（默认关闭）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# HF 缓存指向 D 盘（bge-m3 / bge-reranker-v2-m3 均缓存于此）
os.environ.setdefault("HF_HUB_CACHE", r"D:\hf_cache\hub")

EVIDENCE_DIR = ROOT / "output" / "evidence" / "r3_tier1_rerank_20260908"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30  # 重排候选池大小


def _log(msg: str):
    print(f"[R3-T1] {msg}", flush=True)


def _entry_text(e: dict) -> str:
    """喂给重排器的文档文本：与索引语义内容对齐。"""
    parts = [e.get("description", ""), " ".join(e.get("ip_names", [])),
             e.get("mood", ""), e.get("scene_type", "")]
    return " ".join(p for p in parts if p).strip() or e.get("primary_ip", "")


def _recall_at_k(hits: list, entries: list, expected_ip: str, k: int) -> float:
    n_expected = max(1, sum(1 for e in entries
                            if expected_ip in e.get("ip_names", []) or
                            expected_ip in e.get("primary_ip", "")))
    ip_hits = sum(1 for h in hits[:k]
                  if expected_ip in h.get("ip_names", []) or
                  expected_ip in h.get("primary_ip", ""))
    return ip_hits / min(k, n_expected)


def run_eval():
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from ai.t11_hybrid_search import (
        TEST_QUERIES, build_semantic_index, enrich_with_pseudolabels,
        hybrid_search, load_intel_cache,
    )

    _log("=" * 60)
    _log("R3 档1: bge-reranker-v2-m3 二阶段重排评测")
    _log("=" * 60)

    # 1. 模型
    _log("\n[1/5] 加载 BGE-M3（检索臂）...")
    t0 = time.time()
    model = SentenceTransformer("BAAI/bge-m3")
    _log(f"  加载 {time.time()-t0:.1f}s")

    _log("[2/5] 加载 bge-reranker-v2-m3（重排臂）...")
    t0 = time.time()
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
    _log(f"  加载 {time.time()-t0:.1f}s")

    # 2. 索引（与 T11 同口径：material_intel + 伪标签扩充，内存构建不落盘）
    _log("\n[3/5] 构建语义索引（与 T11 同口径，内存重建）...")
    entries = load_intel_cache()
    _log(f"  material_intel: {len(entries)}条")
    entries = enrich_with_pseudolabels(entries, max_per_ip=50)
    _log(f"  扩充后: {len(entries)}条")
    embeddings = build_semantic_index(entries, model)

    # 3. 双臂评测
    _log(f"\n[4/5] 双臂评测（{len(TEST_QUERIES)} 条查询 × [原链路, 重排]）...")
    per_query = []
    for query, expected_ip in TEST_QUERIES:
        # 臂A：原 T11 链路 top10（内部 RRF_K 默认）
        arm_a = hybrid_search(entries, embeddings, model, query, top_k=10)

        # 臂B：候选池 top_N → CrossEncoder 重排
        pool = hybrid_search(entries, embeddings, model, query, top_k=CANDIDATE_POOL)
        if pool:
            pairs = [(query, _entry_text(e)) for e in pool]
            scores = reranker.predict(pairs)
            order = np.argsort(scores)[::-1]
            arm_b = [pool[i] for i in order]
        else:
            arm_b = []

        per_query.append({
            "query": query,
            "expected_ip": expected_ip,
            "baseline": {
                "recall@5": round(_recall_at_k(arm_a, entries, expected_ip, 5), 3),
                "recall@10": round(_recall_at_k(arm_a, entries, expected_ip, 10), 3),
                "n_hits": len(arm_a),
            },
            "reranked": {
                "recall@5": round(_recall_at_k(arm_b, entries, expected_ip, 5), 3),
                "recall@10": round(_recall_at_k(arm_b, entries, expected_ip, 10), 3),
                "n_hits": len(arm_b),
            },
        })

    # 4. 汇总
    def _avg(arm: str, metric: str) -> float:
        return round(float(np.mean([q[arm][metric] for q in per_query])), 3)

    summary = {
        "baseline_recall@5": _avg("baseline", "recall@5"),
        "baseline_recall@10": _avg("baseline", "recall@10"),
        "reranked_recall@5": _avg("reranked", "recall@5"),
        "reranked_recall@10": _avg("reranked", "recall@10"),
    }
    summary["pass_tier1_gate"] = summary["reranked_recall@10"] >= 0.70

    # 5. 证据落盘
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": "R3 档1: bge-reranker-v2-m3 二阶段重排",
        "retriever": "BAAI/bge-m3 (T11 原链路, RRF_K=20)",
        "reranker": RERANKER_MODEL,
        "candidate_pool": CANDIDATE_POOL,
        "n_entries": len(entries),
        "n_queries": len(TEST_QUERIES),
        "recall_definition": "ip_hits / min(K, n_expected)，与 T11 同口径",
        "summary": summary,
        "per_query": per_query,
    }
    report_path = EVIDENCE_DIR / "r3_tier1_rerank_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"原链路  : recall@5={summary['baseline_recall@5']:.3f}  recall@10={summary['baseline_recall@10']:.3f}")
    _log(f"重排后  : recall@5={summary['reranked_recall@5']:.3f}  recall@10={summary['reranked_recall@10']:.3f}")
    _log(f"档1验收线 recall@10 ≥ 0.70: {'✅ 通过' if summary['pass_tier1_gate'] else '❌ 未过线'}")
    _log(f"证据: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    run_eval()
