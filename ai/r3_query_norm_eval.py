# -*- coding: utf-8 -*-
r"""R3 查询侧 LLM 归一化实验（2026-09-09，文本路线收官步）。

动机（三夜实验链终局结论）：held-out 基准本质是"从隐晦措辞识别 IP"的知识任务，
嵌入模型干不了，得交给 LLM。本实验在检索前置一层 LLM 归一化：

  查询 → LLM（已知 IP 清单，闭集分类 + 查询扩展）→ 扩展查询走关键词锚定链路
       → 无法识别（NO_IP）→ 回退 D 臂（纯语义 + bge-reranker 重排）

模型: qwen2.5-vl-7b-cam-motion 4bit（文本-only 使用，中文 ACG 知识 >> Phi-3-mini）
显存: 两阶段分载——Phase1 VLM(≈6.5G) 归一化全部查询并落缓存；Phase2 释放后载
     BGE-M3 + reranker(≈4G) 做检索。避免 10G+ 同时载入 8GB 卡。
评测: held-out 36 条（IP 识别准确率 + 检索 recall）+ legacy 20 条（回归保护）。
基线: D 臂 bag = R@10 0.394 / A 臂 legacy = 1.000。
证据: output/evidence/r3_query_norm_20260909/
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

EVIDENCE_DIR = ROOT / "output" / "evidence" / "r3_query_norm_20260909"
NORM_CACHE = ROOT / "cache" / "bge_m3_index" / "query_norm_cache.jsonl"
VLM_MODEL = "chancharikm/qwen2.5-vl-7b-cam-motion"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30

# IP 闭集 = 伪标签语料的全部 IP（生产索引的 manifest，不是泄漏）
IP_UNIVERSE = [
    "地缚少年花子君", "无限滑板", "进击的巨人", "海贼王", "灼眼的夏娜",
    "黑岩射手", "某科学的超电磁炮", "FATE", "斩·赤红之瞳", "浪客行",
    "K", "时光代理人", "赛博朋克：边缘行者", "咒术回战", "火影忍者",
    "Move", "JOJO的奇妙冒险", "龙族", "链锯人", "鬼灭之刃", "灵笼",
    "抽烟猫", "猫和老鼠",
]

SYSTEM_PROMPT = (
    "你是动画素材检索系统的查询归一化器。用户会用各种口语/剧情白描/角色特征"
    "来描述想找的动画画面。你的任务：\n"
    f"1. 判断查询最可能指向以下 IP 中的哪一个（闭集，只能从中选）：\n"
    f"{IP_UNIVERSE}\n"
    "2. 生成扩展检索查询 = 原查询 + IP名 + 2-4 个相关同义关键词。\n"
    "3. 若确实无法判断（查询与任何 IP 都无关），输出 NO_IP。\n"
    "输出严格一行 JSON：{\"ip\": \"IP名或NO_IP\", \"expanded\": \"扩展查询\"}\n\n"
    "示例：\n"
    "查询：银发的士兵飞速穿梭斩杀巨人 => {\"ip\": \"进击的巨人\", "
    "\"expanded\": \"进击的巨人 利威尔 兵长 巨人 战斗 立体机动 高速斩杀\"}\n"
    "查询：想找福尔摩斯式推理的名场面 => {\"ip\": \"NO_IP\", "
    "\"expanded\": \"福尔摩斯式推理 名场面\"}"
)


def _log(msg: str):
    print(f"[R3-QN] {msg}", flush=True)


def load_norm_cache() -> dict:
    cache = {}
    if NORM_CACHE.exists():
        for line in NORM_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                cache[d["query"]] = d
            except Exception:
                continue
    return cache


def run_norm(queries: list):
    """Phase 1: VLM 4bit 文本-only 归一化（断点续传缓存）。"""
    import torch
    from transformers import (
        AutoModelForImageTextToText, AutoProcessor, BitsAndBytesConfig,
    )

    cache = load_norm_cache()
    todo = [q for q in queries if q not in cache]
    _log(f"Phase1 查询归一化: 共 {len(queries)}，缓存 {len(cache)}，待做 {len(todo)}")
    if not todo:
        return cache

    t0 = time.time()
    qconfig = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_quant_type="nf4",
    )
    model = AutoModelForImageTextToText.from_pretrained(
        VLM_MODEL, quantization_config=qconfig, device_map="cuda")
    model.eval()
    processor = AutoProcessor.from_pretrained(VLM_MODEL)
    _log(f"  VLM 加载 {time.time()-t0:.0f}s")

    t0 = time.time()
    with open(NORM_CACHE, "a", encoding="utf-8") as f:
        for q in todo:
            messages = [{"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": q}]
            try:
                text = processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True)
                inputs = processor(text=[text], return_tensors="pt").to("cuda")
                with torch.inference_mode():
                    out = model.generate(**inputs, max_new_tokens=100,
                                         do_sample=False, temperature=1.0)
                gen = out[:, inputs["input_ids"].shape[1]:]
                raw = processor.batch_decode(
                    gen, skip_special_tokens=True,
                    clean_up_tokenization_spaces=False)[0].strip()
                # 防御性解析：截取首个 {...} JSON
                js = raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else ""
                try:
                    d = json.loads(js)
                    ip = d.get("ip", "NO_IP")
                    expanded = d.get("expanded", q)
                except Exception:
                    ip, expanded = "NO_IP", q
                if ip != "NO_IP" and ip not in IP_UNIVERSE:
                    ip = "NO_IP"  # 幻觉出闭集外的 IP 一律回退
            except Exception as e:  # noqa: BLE001
                _log(f"  [WARN] {q[:20]}: {type(e).__name__} {e}")
                ip, expanded, raw = "NO_IP", q, ""
            f.write(json.dumps({"query": q, "ip": ip, "expanded": expanded,
                                "raw": raw[:200]},
                               ensure_ascii=False) + "\n")
            cache[q] = {"query": q, "ip": ip, "expanded": expanded}
    _log(f"  归一化完成 {len(todo)} 条，{time.time()-t0:.0f}s -> {NORM_CACHE}")
    return cache


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


def run_retrieval(norm: dict):
    """Phase 2: 释放 VLM 后，BGE-M3 + reranker 检索评测。"""
    import numpy as np
    from sentence_transformers import CrossEncoder, SentenceTransformer

    from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
    from ai.t11_hybrid_search import (
        TEST_QUERIES, build_semantic_index, enrich_with_pseudolabels,
        semantic_rerank_search,
    )

    def _entry_text_f(e):
        parts = [e.get("description", ""), " ".join(e.get("ip_names", [])),
                 e.get("mood", ""), e.get("scene_type", "")]
        return " ".join(p for p in parts if p).strip() or e.get("primary_ip", "")

    model = SentenceTransformer("BAAI/bge-m3")
    reranker = CrossEncoder(RERANKER_MODEL, max_length=512)

    entries = enrich_with_pseudolabels(load_cache_entries(), max_per_ip=50)
    embeddings = build_semantic_index(entries, model)
    _log(f"Phase2 索引: {len(entries)} 条")

    per_query = []
    for qset_name, qset in (("heldout", HELD_OUT_QUERIES),
                            ("legacy", TEST_QUERIES)):
        for query, expected_ip in qset:
            d = norm[query]
            # 架构 v3（v1 替换式 / v2 等权融合均已证伪）:
            #   IP 过滤臂: 识别出 IP → 候选限定该 IP（结构上保证命中）
            #             + 原查询 D 臂 RRF 融合保底（识别错时 D 臂兜住）
            route = "D_only"
            lists = []
            if d["ip"] != "NO_IP":
                route = "filter_only"
                # IP 过滤臂: 该 IP 的全部条目 + 原查询语义排序 + 重排（纯路由，不融合）
                sub = [e for e in entries
                       if d["ip"] in e.get("ip_names", []) or
                       d["ip"] in e.get("primary_ip", "")]
                sub_emb = model.encode(
                    [e["description"] or e["primary_ip"] for e in sub])
                q_emb = model.encode([query])[0]
                sims = (sub_emb / np.linalg.norm(sub_emb, axis=1, keepdims=True)) @ \
                    (q_emb / np.linalg.norm(q_emb))
                order = np.argsort(sims)[::-1][:CANDIDATE_POOL]
                pool = [sub[i] for i in order]
                pairs = [(query, _entry_text_f(e)) for e in pool]
                scores = reranker.predict(pairs)
                pool = [pool[i] for i in np.argsort(scores)[::-1]]
                lists.append([e["file_hash"] for e in pool[:10]])
            else:
                # 原查询 D 臂（NO_IP 兜底）
                lists.append([e["file_hash"] for e in semantic_rerank_search(
                    entries, embeddings, model, query, top_k=10)])
            rrf = {}
            for lst in lists:
                for rank, h in enumerate(lst):
                    rrf[h] = rrf.get(h, 0.0) + 1.0 / (20 + rank + 1)
            hash_to_entry = {e["file_hash"]: e for e in entries}
            hits = [hash_to_entry[h] for h in
                    sorted(rrf, key=rrf.get, reverse=True)[:10]
                    if h in hash_to_entry]
            per_query.append({
                "set": qset_name, "query": query, "expected_ip": expected_ip,
                "norm_ip": d["ip"], "route": route,
                "ip_correct": d["ip"] == expected_ip,
                "recall@10": round(_recall_at_k(hits, entries, expected_ip, 10), 3),
                "nDCG@10": round(_ndcg_at_k(hits, expected_ip), 3),
                "MRR@10": round(_mrr_at_k(hits, expected_ip), 3),
            })

    summary = {}
    for qset_name in ("heldout", "legacy"):
        rows = [r for r in per_query if r["set"] == qset_name]
        if not rows:
            continue
        summary[qset_name] = {
            "n": len(rows),
            "ip_identification_acc": round(
                float(np.mean([r["ip_correct"] for r in rows])), 3),
            "recall@10": round(float(np.mean([r["recall@10"] for r in rows])), 3),
            "nDCG@10": round(float(np.mean([r["nDCG@10"] for r in rows])), 3),
            "MRR@10": round(float(np.mean([r["MRR@10"] for r in rows])), 3),
            "route_dist": {
                rt: sum(1 for r in rows if r["route"] == rt)
                for rt in ("filter_only", "D_only")},
        }

    _log(f"\n{'='*60}")
    for qset_name, s in summary.items():
        _log(f"  [{qset_name}] n={s['n']}  IP识别率={s['ip_identification_acc']}"
             f"  R@10={s['recall@10']}  nDCG={s['nDCG@10']}  MRR={s['MRR@10']}"
             f"  路由={s['route_dist']}")
    _log(f"  基线对照: heldout D臂 bag R@10=0.394 / legacy A臂 R@10=1.000")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": "R3 查询侧 LLM 归一化（qwen2.5-vl-7b 4bit 文本-only）",
        "baseline": {"heldout_D_bag_R@10": 0.394, "legacy_A_R@10": 1.000},
        "norm_cache": str(NORM_CACHE),
        "summary": summary, "per_query": per_query,
    }
    rp = EVIDENCE_DIR / "r3_query_norm_report.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                  encoding="utf-8")
    _log(f"  证据: {rp}")
    return report


def load_cache_entries():
    from ai.t11_hybrid_search import load_intel_cache
    return load_intel_cache()


def main():
    from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
    from ai.t11_hybrid_search import TEST_QUERIES

    all_queries = [q for q, _ in HELD_OUT_QUERIES] + [q for q, _ in TEST_QUERIES]
    norm = run_norm(all_queries)
    run_retrieval(norm)


if __name__ == "__main__":
    main()
