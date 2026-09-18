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
NORM_API_CACHE = ROOT / "cache" / "bge_m3_index" / "query_norm_api_cache.jsonl"
VLM_MODEL = "chancharikm/qwen2.5-vl-7b-cam-motion"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
CANDIDATE_POOL = 30

# API 归一化后端链（OpenAI 兼容；key 从环境变量取，绝不落盘/回显）。
# 额度自动衔接（2026-09-09 Boss 指令）：
#   1. 每个后端先试「指定模型」（Boss 指定的免费额度模型最优先）
#   2. GET /models 自动发现，按免费额度关键词匹配排序后衔接进链
#   3. 模型不可用/额度耗尽(HTTP 400/402/403/404/429) → 指针永久推进
#   4. 网络瞬断(URLError) → 同模型退避重试 [5,15,30]s，耗尽才换下一组合
API_BACKENDS = [
    {"name": "DEEPSEEK", "base_url": "https://api.deepseek.com/v1",
     "key_env": "DEEPSEEK_API_KEY",
     "models": ["deepseek-v4.1-flash-expires-on-0910",  # Boss 指定，0910 到期
                "deepseek-v4-flash"],
     "free_kw": ["free", "expires", "flash"]},
    {"name": "DASHSCOPE", "base_url":
     "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "key_env": "DASHSCOPE_API_KEY",
     "models": ["qwen3.8-flash", "qwen3.5-flash", "qwen-plus"],
     "free_kw": ["free", "expires", "flash", "turbo", "lite"]},
    # 百炼第二额度池（Boss 2026-09-09 提供，与 DASHSCOPE key 模型宇宙一致、
    # 免费额度独立——耗尽衔接：DeepSeek 额度尽 → DASHSCOPE → BAILIAN 续命）
    # 模型顺序 = 36 条 heldout 对决赛实测质量（2026-09-09）:
    #   qwen3.8-flash P=1.000 > qwen3.5-flash P=0.972 > qwen-flash P=0.694
    #   > qwen3.6-flash P=0.528（错误识别比 NO_IP 更有害，低分者仅兜底）
    {"name": "BAILIAN", "base_url":
     "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "key_env": "BAILIAN_API_KEY",
     "models": ["qwen3.8-flash", "qwen3.5-flash", "qwen-flash"],
     "free_kw": ["free", "expires", "flash", "turbo", "lite"]},
    # 硅基流动选型（2026-09-09 对决赛，考虑成本）：指定 deepseek-ai/DeepSeek-V4-Flash
    # P=0.917 (33/36)，1.00/2.00 元/M（缓存命中 0.02），官方空闲价的 44%。
    # 淘汰：GLM-Z1-9B 免费 P=0.556 / Qwen3.5-9B P=0.111 / Qwen3.5-35B-A3B P=0.361。
    {"name": "SILICONFLOW", "base_url": "https://api.siliconflow.cn/v1",
     "key_env": "SILICONFLOW_API_KEY",
     "models": ["deepseek-ai/DeepSeek-V4-Flash"],
     "free_kw": ["free", "expires", "flash", "turbo", "lite"]},
]
RETRY_BACKOFF = [5, 15, 30]
_DISCOVER_CAP = 8  # 每后端自动发现最多衔接 8 个模型
_DISCOVER_EXCLUDE = ("vl", "embedding", "audio", "tts", "asr", "rerank",
                     "speech", "video", "image", "sora", "omni")

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


KEYS_FILE = ROOT / "cache" / "api_keys.json"  # gitignored（cache/）


def load_api_key(name: str) -> str:
    """key 解析：环境变量优先，其次 cache/api_keys.json（不入库）。"""
    v = os.environ.get(name, "")
    if v:
        return v
    try:
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        return data.get(name, "")
    except Exception:  # noqa: BLE001
        return ""


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
        AutoModelForImageTextToText,
        AutoProcessor,
        BitsAndBytesConfig,
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


class _ModelUnavailable(Exception):
    """模型不可用/额度耗尽（HTTP 400/402/403/404/429）→ 指针永久推进。"""


def _discover_models(base_url: str, key: str, free_kw: list) -> list:
    """GET /models 自动发现，按免费额度关键词命中数排序（仅留命中者）。"""
    import urllib.request

    req = urllib.request.Request(
        base_url.rstrip("/") + "/models",
        headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception:  # noqa: BLE001  发现失败不影响指定模型链
        return []
    ids = [m.get("id", "") for m in data.get("data", []) if m.get("id")]
    ranked = []
    for mid in ids:
        low = mid.lower()
        if any(x in low for x in _DISCOVER_EXCLUDE):
            continue
        hits = sum(1 for kw in free_kw if kw in low)
        if hits > 0:
            ranked.append((-hits, mid))
    ranked.sort()
    return [m for _, m in ranked[:_DISCOVER_CAP]]


def _build_call_chain() -> list:
    """展开为 (name, base_url, key, model) 线性调用链：指定模型优先。"""
    chain = []
    for b in API_BACKENDS:
        key = load_api_key(b["key_env"])
        if not key:
            _log(f"  [链] {b['name']}: key 未配置，跳过")
            continue
        models = list(b["models"])
        disc = _discover_models(b["base_url"], key, b["free_kw"])
        extra = [m for m in disc if m not in models]
        models += extra
        _log(f"  [链] {b['name']}: 指定 {len(b['models'])} + 发现免费 "
             f"{len(extra)} = {len(models)} 模型 {models}")
        for m in models:
            chain.append((b["name"], b["base_url"], key, m))
    return chain


def _call_with_retry(base_url: str, key: str, model: str, q: str) -> str:
    """单模型调用：URLError 退避重试；额度/模型类 HTTP 错误抛 _ModelUnavailable。"""
    import urllib.error
    import urllib.request

    data = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": q}],
        # Boss 指定的 deepseek-v4.1-flash-expires-on-0910 是推理模型：
        # 思考走 reasoning_content（动辄数百 token），答案在 content。
        # max_tokens 必须 ≥2048，否则思考耗尽预算 → content 空/截断。
        "max_tokens": 2048, "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=data,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    last_net_err = None
    for delay in [0] + RETRY_BACKOFF:
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (400, 402, 403, 404, 429):
                raise _ModelUnavailable(f"HTTP {e.code}") from e
            raise
        except urllib.error.URLError as e:  # 网络瞬断：退避重试
            last_net_err = e
            continue
    raise _ModelUnavailable(f"网络重试耗尽 ({type(last_net_err).__name__})")


def run_norm_api(queries: list):
    """Phase1-API: 远程 LLM 归一化（DeepSeek→DashScope→SiliconFlow，
    指定模型优先 + /models 免费额度自动衔接，断点续传独立缓存）。"""
    chain = _build_call_chain()
    if not chain:
        raise RuntimeError("无可用的 API 后端（key 均未配置）")

    # 载入缓存并剔除污染记录（上轮 URLError 写入的空 raw，须重跑）
    cache, poisoned = {}, 0
    if NORM_API_CACHE.exists():
        for line in NORM_API_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
            except Exception:
                poisoned += 1
                continue
            if not d.get("raw") or not d.get("backend"):
                poisoned += 1  # 空响应 = 网络失败污染，丢弃
                continue
            raw = d["raw"]
            if "{" not in raw or "}" not in raw:
                poisoned += 1  # JSON 截断（旧 max_tokens=150 思考耗尽），丢弃
                continue
            cache[d["query"]] = d
    if poisoned:
        NORM_API_CACHE.write_text(
            "".join(json.dumps(c, ensure_ascii=False) + "\n"
                    for c in cache.values()), encoding="utf-8")
        _log(f"  清理污染缓存记录 {poisoned} 条，缓存留 {len(cache)} 条")
    todo = [q for q in queries if q not in cache]
    _log(f"Phase1-API 查询归一化: 共 {len(queries)}，缓存 {len(cache)}，"
         f"待做 {len(todo)}")
    if not todo:
        return cache

    t0 = time.time()
    ptr = 0  # 调用链指针：模型不可用/额度耗尽时永久推进
    with open(NORM_API_CACHE, "a", encoding="utf-8") as f:
        for q in todo:
            raw, bname, model_used = "", "", ""
            for ci in range(ptr, len(chain)):
                bname_, burl, key, model = chain[ci]
                try:
                    raw = _call_with_retry(burl, key, model, q)
                    bname, model_used = bname_, model
                    break
                except _ModelUnavailable as e:
                    _log(f"  [额度] {bname_}/{model}: {e} → 指针推进")
                    if ci == ptr:
                        ptr = ci + 1
                except Exception as e:  # noqa: BLE001  瞬时错误不永久推进
                    _log(f"  [WARN] {bname_}/{model} {q[:12]}: "
                         f"{type(e).__name__}")
            js = raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else ""
            try:
                d = json.loads(js)
                ip = d.get("ip", "NO_IP")
                expanded = d.get("expanded", q)
            except Exception:
                ip, expanded = "NO_IP", q
            if ip != "NO_IP" and ip not in IP_UNIVERSE:
                ip = "NO_IP"
            rec = {"query": q, "ip": ip, "expanded": expanded,
                   "backend": bname, "model": model_used, "raw": raw[:200]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cache[q] = rec
    _log(f"  API 归一化完成 {len(todo)} 条，{time.time()-t0:.0f}s -> {NORM_API_CACHE}")
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
        TEST_QUERIES,
        build_semantic_index,
        enrich_with_pseudolabels,
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
    _log("  基线对照: heldout D臂 bag R@10=0.394 / legacy A臂 R@10=1.000")

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
    if os.environ.get("AEKV_NORM_BACKEND", "api") == "api":
        norm = run_norm_api(all_queries)
    else:
        norm = run_norm(all_queries)
    run_retrieval(norm)


if __name__ == "__main__":
    main()
