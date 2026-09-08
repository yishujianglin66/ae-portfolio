# -*- coding: utf-8 -*-
r"""R3 描述改写实验（2026-09-08 晚）：词袋 vs 自然语言句子，单变量 A/B。

假设（基准 v2 结论 3）：BGE-M3 裸语义只有 0.286 的主因是文档侧为
"IP, 角色, 关键词"词袋，与自然语言查询存在分布鸿沟。
本实验不改查询、不改模型、不改采样（同 seed 42），只改文档形态：

  E0 词袋（现状）:   "进击的巨人, 艾伦, 巨人, 战斗"
  E1 句子（模板）:   "《进击的巨人》的动画画面。场景中出现艾伦。画面包含巨人、战斗等元素。"

臂（对齐基准 v2 口径，仅 held-out 36 条，legacy 不受文档形态影响故跳过）:
  B  = 纯语义 top10
  D  = 纯语义池30 + bge-reranker-v2-m3 重排（当前最优配置）

判定: E1 相对 E0 在 B/D 两臂的 R@10 / nDCG@10 差值 = 语义鸿沟的可回收量。

证据落盘: output/evidence/r3_doc_rewrite_20260908/
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

EVIDENCE_DIR = ROOT / "output" / "evidence" / "r3_doc_rewrite_20260908"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30


def _log(msg: str):
    print(f"[R3-DOC] {msg}", flush=True)


def build_entries_variant(doc_format: str):
    """与 t11 enrich_with_pseudolabels 同采样（seed 42），仅描述形态不同。

    doc_format: 'bag'（现状词袋）| 'sentence'（自然语言模板句）
    """
    import numpy as np

    from ai.t11_hybrid_search import (
        CHAR_TO_IP, IP_VISUAL_KW, load_intel_cache,
    )

    entries = load_intel_cache()
    pseudo_path = Path(r"D:\aot_corpus\pseudolabels.json")
    pseudo = json.loads(pseudo_path.read_text(encoding="utf-8"))

    ip_groups: dict = {}
    for p in pseudo:
        ip_groups.setdefault(p["ip"], []).append(p)

    ip_to_chars: dict = {}
    for char, ip in CHAR_TO_IP.items():
        ip_to_chars.setdefault(ip, []).append(char)

    max_per_ip = 50
    for ip, frames in ip_groups.items():
        if len(frames) < 10:
            continue
        np.random.seed(42)  # 与 t11 一致，保证条目集合相同
        n_sample = min(max_per_ip, len(frames))
        indices = np.random.choice(len(frames), n_sample, replace=False)
        chars = ip_to_chars.get(ip, [])
        visual_kws = IP_VISUAL_KW.get(ip, [])
        for i, idx in enumerate(indices):
            frame = frames[idx]
            frame_path = frame.get("frame_path", "")
            frame_name = Path(frame_path).name if frame_path else f"frame_{idx}"
            # 与 t11 相同的成分选择
            picked_chars = []
            if chars:
                picked_chars.append(chars[i % len(chars)])
                if len(chars) > 2:
                    picked_chars.append(chars[(i + 1) % len(chars)])
            picked_kws = []
            if visual_kws:
                picked_kws.append(visual_kws[i % len(visual_kws)])
                if len(visual_kws) > 2:
                    picked_kws.append(visual_kws[(i + 1) % len(visual_kws)])

            if doc_format == "bag":
                desc = ", ".join([ip] + picked_chars + picked_kws)
            else:  # sentence
                s = f"《{ip}》的动画画面。"
                if picked_chars:
                    s += f"场景中出现{'、'.join(picked_chars)}。"
                if picked_kws:
                    s += f"画面包含{'、'.join(picked_kws)}等元素。"
                desc = s

            entries.append({
                "file_hash": f"frame_{ip}_{idx}",
                "filename": frame_name,
                "description": desc,
                "ip_names": [ip],
                "mood": "",
                "scene_type": "",
                "primary_ip": ip,
                "source": "pseudolabel",
            })
    return entries


def _is_relevant(entry: dict, expected_ip: str) -> bool:
    return (expected_ip in entry.get("ip_names", []) or
            expected_ip in entry.get("primary_ip", ""))


def _recall_at_k(hits, entries, expected_ip, k):
    n_expected = max(1, sum(1 for e in entries if _is_relevant(e, expected_ip)))
    ip_hits = sum(1 for h in hits[:k] if _is_relevant(h, expected_ip))
    return ip_hits / min(k, n_expected)


def _ndcg_at_k(hits, expected_ip, k=10):
    dcg = sum((1.0 if _is_relevant(h, expected_ip) else 0.0) / math.log2(i + 2)
              for i, h in enumerate(hits[:k]))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(k))
    return dcg / idcg if idcg > 0 else 0.0


def _mrr_at_k(hits, expected_ip, k=10):
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

    from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
    from ai.t11_hybrid_search import semantic_search

    _log("=" * 60)
    _log("R3 描述改写实验：词袋(E0) vs 句子(E1)，held-out 36 条 × [B, D] 臂")
    _log("=" * 60)

    model = SentenceTransformer("BAAI/bge-m3")
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)

    results = {}
    for variant in ("bag", "sentence"):
        _log(f"\n--- 文档形态: {variant} ---")
        entries = build_entries_variant(variant)
        _log(f"  条目: {len(entries)}（样例: {entries[-1]['description'][:60]}…）")
        t0 = time.time()
        descs = [e["description"] or e["primary_ip"] for e in entries]
        embeddings = model.encode(descs, batch_size=32)
        _log(f"  编码 {time.time()-t0:.0f}s")

        hash_to_entry = {e["file_hash"]: e for e in entries}
        rows = []
        for query, expected_ip in HELD_OUT_QUERIES:
            q_emb = model.encode([query])[0]
            # B 臂：纯语义
            b_hashes = semantic_search(embeddings, entries, q_emb, top_k=10)
            b_hits = [hash_to_entry[h] for h in b_hashes]
            # D 臂：语义池30 + 重排
            pool_hashes = semantic_search(embeddings, entries, q_emb,
                                          top_k=CANDIDATE_POOL)
            pool = [hash_to_entry[h] for h in pool_hashes]
            pairs = [(query, _entry_text(e)) for e in pool]
            scores = reranker.predict(pairs)
            d_hits = [pool[i] for i in np.argsort(scores)[::-1]]

            rows.append({
                "query": query, "expected_ip": expected_ip,
                "B": {m: round(f(b_hits), 3) for m, f in {
                    "R@10": lambda h: _recall_at_k(h, entries, expected_ip, 10),
                    "nDCG@10": lambda h: _ndcg_at_k(h, expected_ip),
                    "MRR@10": lambda h: _mrr_at_k(h, expected_ip)}.items()},
                "D": {m: round(f(d_hits), 3) for m, f in {
                    "R@10": lambda h: _recall_at_k(h, entries, expected_ip, 10),
                    "nDCG@10": lambda h: _ndcg_at_k(h, expected_ip),
                    "MRR@10": lambda h: _mrr_at_k(h, expected_ip)}.items()},
            })

        results[variant] = {
            "n_entries": len(entries),
            "per_query": rows,
            "summary": {
                arm: {m: round(float(np.mean([r[arm][m] for r in rows])), 3)
                      for m in ("R@10", "nDCG@10", "MRR@10")}
                for arm in ("B", "D")
            },
        }

    # 汇总对照
    _log(f"\n{'='*60}")
    _log(f"  {'形态':<10}{'B-R@10':>8}{'B-nDCG':>8}{'B-MRR':>8}"
         f"{'D-R@10':>8}{'D-nDCG':>8}{'D-MRR':>8}")
    for variant in ("bag", "sentence"):
        s = results[variant]["summary"]
        _log(f"  {variant:<10}{s['B']['R@10']:>8.3f}{s['B']['nDCG@10']:>8.3f}"
             f"{s['B']['MRR@10']:>8.3f}{s['D']['R@10']:>8.3f}"
             f"{s['D']['nDCG@10']:>8.3f}{s['D']['MRR@10']:>8.3f}")
    delta = {arm: {m: round(results["sentence"]["summary"][arm][m] -
                            results["bag"]["summary"][arm][m], 3)
                   for m in ("R@10", "nDCG@10", "MRR@10")}
             for arm in ("B", "D")}
    _log(f"  Δ(句-袋): {delta}")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": "R3 描述改写实验：词袋 vs 自然语言句子（单变量）",
        "controls": "同查询(held-out 36)/同模型/同采样seed42/同成分选择，仅文档形态不同",
        "summary": {v: results[v]["summary"] for v in results},
        "delta_sentence_minus_bag": delta,
        "per_query": {v: results[v]["per_query"] for v in results},
    }
    report_path = EVIDENCE_DIR / "r3_doc_rewrite_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    _log(f"\n  证据: {report_path}")
    return report


if __name__ == "__main__":
    run_eval()
