# -*- coding: utf-8 -*-
r"""R3 VLM caption 消费端评测（2026-09-08 深夜）。

前提: ai/r3_vlm_caption.py 已产出 cache/bge_m3_index/frame_captions.jsonl。

实验设计（对齐 doc_rewrite 实验口径，held-out 36 条 × B/D 臂）:
  E2a caption-only : description = VLM caption（纯信息增量）
  E2b caption+IP  : description = caption + "《IP》"（IP 锚保留，测关键词通道是否需要）
  对照基线（doc_rewrite 实验已测）: bag B=0.286 / D=0.394；sentence B=0.300 / D=0.372

证据落盘: output/evidence/r3_vlm_caption_20260908/
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

EVIDENCE_DIR = ROOT / "output" / "evidence" / "r3_vlm_caption_20260908"
CAPTION_CACHE = ROOT / "cache" / "bge_m3_index" / "frame_captions.jsonl"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30


def _log(msg: str):
    print(f"[R3-VLM] {msg}", flush=True)


def build_entries_variant(doc_format: str, captions: dict):
    """与 t11 enrich 同采样（seed42），描述替换为 caption 形态。

    doc_format: 'caption' | 'caption_ip' | 'bag_caption'（bag 成分+caption 融合）
    """
    import numpy as np

    from ai.t11_hybrid_search import (
        CHAR_TO_IP,
        IP_VISUAL_KW,
        load_intel_cache,
    )

    entries = load_intel_cache()
    pseudo = json.loads(Path(r"D:\aot_corpus\pseudolabels.json").read_text(encoding="utf-8"))
    ip_groups: dict = {}
    for p in pseudo:
        ip_groups.setdefault(p["ip"], []).append(p)

    ip_to_chars: dict = {}
    for char, ip in CHAR_TO_IP.items():
        ip_to_chars.setdefault(ip, []).append(char)

    n_hit = 0
    for ip, frames in ip_groups.items():
        if len(frames) < 10:
            continue
        np.random.seed(42)
        indices = np.random.choice(len(frames), min(50, len(frames)), replace=False)
        chars = ip_to_chars.get(ip, [])
        visual_kws = IP_VISUAL_KW.get(ip, [])
        for i, idx in enumerate(indices):
            frame = frames[idx]
            fh = f"frame_{ip}_{idx}"
            cap = captions.get(fh, "").strip()
            if not cap:
                continue  # caption 缺失的帧不入索引（保证各形态索引一致地只含已caption帧）
            fp = frame.get("frame_path", "")
            # bag 成分（与 t11/doc_rewrite 完全同口径）
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
            bag = ", ".join([ip] + picked_chars + picked_kws)

            if doc_format == "caption":
                desc = cap
            elif doc_format == "caption_ip":
                desc = f"{cap} 《{ip}》"
            else:  # bag_caption: IP 锚 + 场景语义融合
                desc = f"{bag}。{cap}"
            entries.append({
                "file_hash": fh,
                "filename": Path(fp).name if fp else fh,
                "description": desc,
                "ip_names": [ip],
                "mood": "",
                "scene_type": "",
                "primary_ip": ip,
                "source": "pseudolabel_vlm",
            })
            n_hit += 1
    _log(f"  {doc_format}: {n_hit} 条 caption 帧入索引")
    return entries


def _is_relevant(entry, expected_ip):
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


def _entry_text(e):
    parts = [e.get("description", ""), " ".join(e.get("ip_names", [])),
             e.get("mood", ""), e.get("scene_type", "")]
    return " ".join(p for p in parts if p).strip() or e.get("primary_ip", "")


def run_eval():
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
    from ai.t11_hybrid_search import semantic_search

    captions = {}
    for line in CAPTION_CACHE.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
            if d.get("caption"):
                captions[d["file_hash"]] = d["caption"]
        except Exception:
            continue
    if not captions:
        raise SystemExit(f"caption 缓存为空: {CAPTION_CACHE}")
    _log(f"caption 缓存: {len(captions)} 条有效")

    model = SentenceTransformer("BAAI/bge-m3")
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)

    results = {}
    for variant in ("caption", "caption_ip", "bag_caption"):
        _log(f"\n--- 文档形态: {variant} ---")
        entries = build_entries_variant(variant, captions)
        t0 = time.time()
        descs = [e["description"] or e["primary_ip"] for e in entries]
        embeddings = model.encode(descs, batch_size=32)
        _log(f"  编码 {time.time()-t0:.0f}s（GPU 加速后应明显快于 CPU 的 60s）")

        hash_to_entry = {e["file_hash"]: e for e in entries}
        rows = []
        for query, expected_ip in HELD_OUT_QUERIES:
            q_emb = model.encode([query])[0]
            b_hashes = semantic_search(embeddings, entries, q_emb, top_k=10)
            b_hits = [hash_to_entry[h] for h in b_hashes]
            pool_hashes = semantic_search(embeddings, entries, q_emb,
                                           top_k=CANDIDATE_POOL)
            pool = [hash_to_entry[h] for h in pool_hashes]
            pairs = [(query, _entry_text(e)) for e in pool]
            scores = reranker.predict(pairs)
            d_hits = [pool[i] for i in np.argsort(scores)[::-1]]

            rows.append({
                "query": query, "expected_ip": expected_ip,
                "B": {"R@10": round(_recall_at_k(b_hits, entries, expected_ip, 10), 3),
                      "nDCG@10": round(_ndcg_at_k(b_hits, expected_ip), 3),
                      "MRR@10": round(_mrr_at_k(b_hits, expected_ip), 3)},
                "D": {"R@10": round(_recall_at_k(d_hits, entries, expected_ip, 10), 3),
                      "nDCG@10": round(_ndcg_at_k(d_hits, expected_ip), 3),
                      "MRR@10": round(_mrr_at_k(d_hits, expected_ip), 3)},
            })
        results[variant] = {
            "n_entries": len(entries), "per_query": rows,
            "summary": {arm: {m: round(float(np.mean([r[arm][m] for r in rows])), 3)
                              for m in ("R@10", "nDCG@10", "MRR@10")}
                        for arm in ("B", "D")},
        }

    _log(f"\n{'='*60}")
    _log(f"  {'形态':<14}{'B-R@10':>8}{'B-nDCG':>8}{'D-R@10':>8}{'D-nDCG':>8}")
    _log(f"  {'bag(基线)':<14}{0.286:>8}{0.287:>8}{0.394:>8}{0.395:>8}")
    _log(f"  {'sentence(基线)':<14}{0.300:>8}{0.296:>8}{0.372:>8}{0.372:>8}")
    for v in ("caption", "caption_ip", "bag_caption"):
        s = results[v]["summary"]
        _log(f"  {v:<14}{s['B']['R@10']:>8.3f}{s['B']['nDCG@10']:>8.3f}"
             f"{s['D']['R@10']:>8.3f}{s['D']['nDCG@10']:>8.3f}")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": "R3 VLM caption 消费端评测（caption / caption+IP）",
        "baseline": {"bag": {"B_R@10": 0.286, "D_R@10": 0.394},
                     "sentence": {"B_R@10": 0.300, "D_R@10": 0.372}},
        "n_captions": len(captions),
        "summary": {v: results[v]["summary"] for v in results},
        "per_query": {v: results[v]["per_query"] for v in results},
    }
    report_path = EVIDENCE_DIR / "r3_vlm_caption_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    _log(f"\n  证据: {report_path}")
    return report


if __name__ == "__main__":
    run_eval()
