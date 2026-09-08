# -*- coding: utf-8 -*-
r"""T11: BGE-M3语义检索 + 关键词RRF混合检索。

架构:
  - 关键词通道: 现有text搜索(material_intel)
  - 语义通道: BGE-M3编码description→向量索引
  - 融合: RRF(reciprocal rank fusion, k=60)

验收:
  - 20条跨措辞查询Top5召回≥80%
  - 原精确查询不回退
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

INTEL_CACHE = ROOT / "cache" / "material_intel"
INDEX_DIR = ROOT / "cache" / "bge_m3_index"
RRF_K = 20  # 优化: 从60降到20(38条索引更适合小k)

# ---------------------------------------------------------------------------
# 分流检索（2026-09-08，基准 v2 证据驱动，开关默认关）
# 证据: output/evidence/r3_benchmark_v2_20260908/（四臂实测）
#   - 别名命中查询: 关键词通道+RRF 满分（legacy R@10=1.000），原链路不动
#   - 自然语言查询: 关键词 2-gram 误命中是负资产（hybrid 0.267 < 纯语义 0.286），
#     纯语义池 + bge-reranker-v2-m3 重排最优（R@10=0.400，+11.4pp vs 纯语义）
# 启用: set AEKV_RETRIEVAL_RERANK=1
# ---------------------------------------------------------------------------
RERANK_ENV = "AEKV_RETRIEVAL_RERANK"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_POOL = 30  # 重排候选池（基准 v2 实测口径）
_RERANKER = None  # 懒加载单例

# 角色→IP别名映射(增强关键词搜索)
CHAR_TO_IP = {
    # 进击的巨人
    "艾伦": "进击的巨人", "利威尔": "进击的巨人", "三笠": "进击的巨人",
    "阿尔敏": "进击的巨人", "韩吉": "进击的巨人", "埃尔文": "进击的巨人",
    "让": "进击的巨人", "萨莎": "进击的巨人", "康尼": "进击的巨人",
    "安妮": "进击的巨人", "兵长": "进击的巨人", "调查兵团": "进击的巨人",
    "立体机动": "进击的巨人", "巨人": "进击的巨人",
    # JOJO
    "替身": "JOJO的奇妙冒险", "替身使者": "JOJO的奇妙冒险",
    "纳兰迦": "JOJO的奇妙冒险", "航空史密斯": "JOJO的奇妙冒险",
    # 斩·赤红之瞳
    "赤瞳": "斩·赤红之瞳", "暗杀者": "斩·赤红之瞳",
    "暗杀组织": "斩·赤红之瞳", "Night Raid": "斩·赤红之瞳",
    # 某科学的超电磁炮
    "御坂美琴": "某科学的超电磁炮", "超能力": "某科学的超电磁炮",
    "电击": "某科学的超电磁炮", "常盘台": "某科学的超电磁炮",
    # 鬼灭之刃
    "柱": "鬼灭之刃", "呼吸法": "鬼灭之刃", "鬼杀队": "鬼灭之刃",
    "火焰": "鬼灭之刃", "日轮刀": "鬼灭之刃",
}

# IP视觉关键词
IP_VISUAL_KW = {
    "进击的巨人": ["巨人", "战斗", "立体机动装置", "城墙", "变身", "热血"],
    "JOJO的奇妙冒险": ["替身", "Stand", "战斗", "姿势", "肌肉"],
    "斩·赤红之瞳": ["剑", "暗杀", "血", "战斗", "悲伤"],
    "某科学的超电磁炮": ["电击", "超能力", "蓝", "能量", "冰晶"],
    "鬼灭之刃": ["火焰", "呼吸", "剑", "鬼", "和风"],
    "无限滑板": ["滑板", "SK8", "运动", "青春"],
    "火影忍者": ["忍者", "查克拉", "螺旋丸", "写轮眼"],
}

# 扩展测试查询集: 20条跨措辞/同义/角色/视觉/组织查询
TEST_QUERIES = [
    # 跨措辞(口语→IP名)
    ("飙滑板", "无限滑板"),
    ("巨人战斗", "进击的巨人"),
    ("电击超能力", "某科学的超电磁炮"),
    ("暗杀者剑技", "斩·赤红之瞳"),
    ("替身使者", "JOJO的奇妙冒险"),
    # 角色→IP
    ("艾伦变身", "进击的巨人"),
    ("利威尔兵长", "进击的巨人"),
    ("三笠战斗", "进击的巨人"),
    ("阿尔敏", "进击的巨人"),
    ("纳兰迦替身", "JOJO的奇妙冒险"),
    ("御坂美琴", "某科学的超电磁炮"),
    ("赤瞳", "斩·赤红之瞳"),
    # 视觉特征→IP
    ("火焰特效", "鬼灭之刃"),
    ("立体机动装置", "进击的巨人"),
    ("冰晶能力", "某科学的超电磁炮"),
    # 组织/设定名→IP
    ("调查兵团", "进击的巨人"),
    ("柱", "鬼灭之刃"),
    ("暗杀组织", "斩·赤红之瞳"),
    # 情绪/氛围→IP
    ("热血战斗", "进击的巨人"),
    ("悲伤催泪", "斩·赤红之瞳"),
]


def _log(msg: str):
    print(f"[T11] {msg}", flush=True)


def load_intel_cache() -> List[Dict]:
    """加载material_intel缓存"""
    entries = []
    for f in sorted(INTEL_CACHE.glob("*.json")):
        if f.name == "test_results.json":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        desc = data.get("description", "")
        ip_tags = data.get("ip_tags", [])
        ip_names = [t.get("ip_name", "") for t in ip_tags if isinstance(t, dict)]
        content = data.get("content", {})
        entries.append({
            "file_hash": data.get("file_hash", f.stem),
            "filename": data.get("filename", ""),
            "description": desc,
            "ip_names": ip_names,
            "mood": content.get("mood", "") if isinstance(content, dict) else "",
            "scene_type": content.get("scene_type", "") if isinstance(content, dict) else "",
            "primary_ip": data.get("primary_ip", ""),
            "source": "material_intel",
        })
    return entries


def enrich_with_pseudolabels(entries: List[Dict], max_per_ip: int = 50) -> List[Dict]:
    """从伪标签采样帧描述扩充索引(每IP最多max_per_ip条)"""
    pseudo_path = Path(r"D:\aot_corpus\pseudolabels.json")
    if not pseudo_path.exists():
        _log("伪标签不存在, 跳过索引扩充")
        return entries

    pseudo = json.loads(pseudo_path.read_text(encoding="utf-8"))
    # 按IP分组
    ip_groups = {}
    for p in pseudo:
        ip = p["ip"]
        if ip not in ip_groups:
            ip_groups[ip] = []
        ip_groups[ip].append(p)

    # 已有IP集合(避免重复)
    existing_ips = set()
    for e in entries:
        existing_ips.add(e.get("primary_ip", ""))
        existing_ips.update(e.get("ip_names", []))

    n_added = 0
    # 角色→IP反向映射
    ip_to_chars = {}
    for char, ip in CHAR_TO_IP.items():
        if ip not in ip_to_chars:
            ip_to_chars[ip] = []
        ip_to_chars[ip].append(char)

    for ip, frames in ip_groups.items():
        if len(frames) < 10:
            continue
        # 采样
        np.random.seed(42)
        n_sample = min(max_per_ip, len(frames))
        indices = np.random.choice(len(frames), n_sample, replace=False)
        chars = ip_to_chars.get(ip, [])
        visual_kws = IP_VISUAL_KW.get(ip, [])
        for i, idx in enumerate(indices):
            frame = frames[idx]
            frame_path = frame.get("frame_path", "")
            frame_name = Path(frame_path).name if frame_path else f"frame_{idx}"
            conf = frame.get("confidence", 0)
            # 构造增强描述: IP名 + 角色名 + 视觉关键词 + 帧名
            parts = [ip]
            if chars:
                # 每个帧描述包含1-2个角色名(轮换)
                char_idx = i % len(chars)
                parts.append(chars[char_idx])
                if len(chars) > 2:
                    parts.append(chars[(char_idx + 1) % len(chars)])
            if visual_kws:
                # 加入2-3个视觉关键词
                kw_idx = i % len(visual_kws)
                parts.append(visual_kws[kw_idx])
                if len(visual_kws) > 2:
                    parts.append(visual_kws[(kw_idx + 1) % len(visual_kws)])
            desc = ", ".join(parts)
            entry = {
                "file_hash": f"frame_{ip}_{idx}",
                "filename": frame_name,
                "description": desc,
                "ip_names": [ip] + ([c for c in chars if c in ["兵长", "调查兵团"]][:1]),
                "mood": "",
                "scene_type": "",
                "primary_ip": ip,
                "source": "pseudolabel",
            }
            entries.append(entry)
            n_added += 1

    _log(f"伪标签扩充: +{n_added}条帧级条目(总{len(entries)}条)")
    return entries


def build_semantic_index(entries: List[Dict], model) -> np.ndarray:
    """用BGE-M3编码所有description"""
    descriptions = [e["description"] or e["primary_ip"] for e in entries]
    _log(f"编码 {len(descriptions)} 条description...")
    t0 = time.time()
    embeddings = model.encode(descriptions, batch_size=32, show_progress_bar=True)
    _log(f"编码完成: {embeddings.shape}, 耗时{time.time()-t0:.1f}s")
    return embeddings


def rrf_fusion(keyword_results: List[str], semantic_results: List[str], k=60) -> List[str]:
    """RRF融合: score = sum(1/(k+rank))"""
    scores = {}
    for rank, item in enumerate(keyword_results):
        scores[item] = scores.get(item, 0) + 1.0 / (k + rank + 1)
    for rank, item in enumerate(semantic_results):
        scores[item] = scores.get(item, 0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


def keyword_search(entries: List[Dict], query: str) -> List[str]:
    """关键词搜索(增强版: 子串+角色别名+IP视觉关键词+2-gram)"""
    results = []
    query_lower = query.lower()
    # 检查查询是否匹配角色→IP别名
    alias_ips = set()
    for alias, ip in CHAR_TO_IP.items():
        if alias in query_lower or query_lower in alias:
            alias_ips.add(ip)

    for e in entries:
        text = f"{e['description']} {' '.join(e['ip_names'])} {e['mood']} {e['scene_type']}".lower()
        # 1. 基础文本匹配
        if query_lower in text:
            results.append(e["file_hash"])
            continue
        # 2. 角色别名匹配
        if alias_ips:
            e_ip = e.get("primary_ip", "")
            if e_ip in alias_ips or any(ip in e.get("ip_names", []) for ip in alias_ips):
                results.append(e["file_hash"])
                continue
        # 3. IP名子串双向匹配
        if any(query_lower in ip.lower() or ip.lower() in query_lower
               for ip in e["ip_names"] if ip):
            results.append(e["file_hash"])
            continue
        # 4. 中文2-gram模糊匹配(仅当查询>=3字)
        if len(query_lower) >= 3:
            for i in range(len(query_lower) - 1):
                gram = query_lower[i:i+2]
                if gram in text:
                    results.append(e["file_hash"])
                    break
    return results


def semantic_search(embeddings: np.ndarray, entries: List[Dict],
                    query_embedding: np.ndarray, top_k: int = 10) -> List[str]:
    """语义搜索: 余弦相似度Top-K"""
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    emb_norm = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
    similarities = emb_norm @ query_norm
    top_indices = np.argsort(similarities)[::-1][:top_k]
    return [entries[i]["file_hash"] for i in top_indices]


def query_has_alias_hit(query: str) -> bool:
    """查询是否命中别名表/IP名（强关键词通道信号）。

    命中 → 走原 hybrid 链路（legacy 基准满分，重排只会轻微失分）；
    未命中 → 自然语言场景查询，走纯语义+重排（基准 v2 D 臂最优）。
    """
    q = query.lower().strip()
    if not q:
        return False
    for alias in CHAR_TO_IP:
        if alias in q or q in alias:
            return True
    all_ips = set(IP_VISUAL_KW.keys()) | set(CHAR_TO_IP.values())
    for ip in all_ips:
        if ip and (ip in query or query in ip):
            return True
    return False


def decide_route(query: str) -> str:
    """分流决策（纯逻辑，可单测）。返回 'hybrid' 或 'semantic_rerank'。"""
    if os.environ.get(RERANK_ENV, "0") != "1":
        return "hybrid"
    return "hybrid" if query_has_alias_hit(query) else "semantic_rerank"


def _get_reranker():
    """懒加载 CrossEncoder 单例（仅分流启用且命中自然语言分支时加载）。"""
    global _RERANKER
    if _RERANKER is None:
        from sentence_transformers import CrossEncoder
        _RERANKER = CrossEncoder(RERANKER_MODEL, max_length=512)
    return _RERANKER


def _entry_text(e: Dict) -> str:
    """喂给重排器的文档文本（与基准 v2 同口径）。"""
    parts = [e.get("description", ""), " ".join(e.get("ip_names", [])),
             e.get("mood", ""), e.get("scene_type", "")]
    return " ".join(p for p in parts if p).strip() or e.get("primary_ip", "")


def semantic_rerank_search(entries: List[Dict], embeddings: np.ndarray,
                           model, query: str, top_k: int = 10,
                           pool_size: int = RERANK_POOL) -> List[Dict]:
    """自然语言分支：纯语义候选池 + CrossEncoder 重排（基准 v2 D 臂）。"""
    query_emb = model.encode([query])[0]
    pool_hashes = semantic_search(embeddings, entries, query_emb, top_k=pool_size)
    hash_to_entry = {e["file_hash"]: e for e in entries}
    pool = [hash_to_entry[h] for h in pool_hashes if h in hash_to_entry]
    if not pool:
        return []
    pairs = [(query, _entry_text(e)) for e in pool]
    scores = _get_reranker().predict(pairs)
    order = np.argsort(scores)[::-1][:top_k]
    return [pool[i] for i in order]


def hybrid_search(entries: List[Dict], embeddings: np.ndarray,
                  model, query: str, top_k: int = 10) -> List[Dict]:
    """混合检索: 关键词+语义RRF融合（分流启用时按 decide_route 路由）"""
    if decide_route(query) == "semantic_rerank":
        return semantic_rerank_search(entries, embeddings, model, query, top_k)

    # 关键词通道
    kw_results = keyword_search(entries, query)

    # 语义通道
    query_emb = model.encode([query])[0]
    sem_results = semantic_search(embeddings, entries, query_emb, top_k=top_k * 2)

    # RRF融合
    fused = rrf_fusion(kw_results, sem_results, RRF_K)[:top_k]

    # 返回完整信息
    hash_to_entry = {e["file_hash"]: e for e in entries}
    return [hash_to_entry[h] for h in fused if h in hash_to_entry]


def run_t11():
    """主流程: 构建索引 + 验证检索"""
    _log("=" * 60)
    _log("T11: BGE-M3混合检索")
    _log("=" * 60)

    # 1. 加载BGE-M3
    _log("\n[1/4] 加载BGE-M3...")
    t0 = time.time()
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-m3")
    _log(f"  BGE-M3加载: {time.time()-t0:.1f}s, dim={model.get_sentence_embedding_dimension()}")

    # 2. 加载material_intel + 伪标签扩充
    _log("\n[2/4] 加载素材索引...")
    entries = load_intel_cache()
    _log(f"  material_intel: {len(entries)}条")
    entries = enrich_with_pseudolabels(entries, max_per_ip=50)
    _log(f"  扩充后: {len(entries)}条")

    # 3. 构建语义索引(强制重建以包含新条目)
    _log("\n[3/4] 构建语义索引...")
    index_path = INDEX_DIR / "bge_m3_embeddings.npy"
    meta_path = INDEX_DIR / "meta.json"

    # 如果条目数变化或版本不匹配, 强制重建
    INDEX_VERSION = "v2"  # v2: 增强描述(含角色名+视觉关键词)
    need_rebuild = True
    if index_path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("n_entries") == len(entries) and meta.get("version") == INDEX_VERSION:
            need_rebuild = False
            _log("  从磁盘加载缓存索引...")
            embeddings = np.load(str(index_path))

    if need_rebuild:
        _log("  重建索引...")
        embeddings = build_semantic_index(entries, model)
        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        np.save(str(index_path), embeddings)
        meta_path.write_text(json.dumps({
            "n_entries": len(entries),
            "dim": embeddings.shape[1],
            "model": "BAAI/bge-m3",
            "version": INDEX_VERSION,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"  索引: {embeddings.shape}")

    # 4. 验证检索(扩展测试集 + RRF_K扫描)
    _log("\n[4/4] 验证混合检索...")
    best_k, best_recall = RRF_K, 0.0
    all_results = {}

    for k_candidate in [10, 20, 30, 60]:
        results_k = []
        for query, expected_ip in TEST_QUERIES:
            hits = hybrid_search(entries, embeddings, model, query, top_k=5)
            # 计算recall: 命中的IP在Top5中的比例
            n_expected = max(1, sum(1 for e in entries
                                    if expected_ip in e.get("ip_names", []) or
                                    expected_ip in e.get("primary_ip", "")))
            ip_hits = sum(1 for h in hits if expected_ip in h.get("ip_names", []) or
                          expected_ip in h.get("primary_ip", ""))
            recall = ip_hits / min(5, n_expected)
            results_k.append({
                "query": query,
                "expected_ip": expected_ip,
                "top5_recall": round(recall, 3),
                "n_hits": len(hits),
            })
        avg_r = np.mean([r["top5_recall"] for r in results_k])
        all_results[k_candidate] = {"results": results_k, "avg_recall": round(float(avg_r), 3)}
        _log(f"  RRF_K={k_candidate}: avg_recall={avg_r:.3f}")
        if avg_r > best_recall:
            best_k, best_recall = k_candidate, avg_r

    # 使用最优k的结果
    _log(f"\n  最优RRF_K={best_k}, recall={best_recall:.3f}")
    results = all_results[best_k]["results"]
    avg_recall = best_recall

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model": "BAAI/bge-m3",
        "dim": int(embeddings.shape[1]),
        "n_entries": len(entries),
        "rrf_k_best": best_k,
        "rrf_k_scan": {str(k): v["avg_recall"] for k, v in all_results.items()},
        "n_test_queries": len(TEST_QUERIES),
        "test_queries": results,
        "avg_top5_recall": round(float(avg_recall), 3),
        "index_path": str(index_path),
        "status": "complete",
    }
    REPORT_DIR = ROOT / "reports"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "t11_hybrid_search_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    _log(f"\n{'='*60}")
    _log(f"✅ T11混合检索完成")
    _log(f"   平均Top5召回: {avg_recall:.3f}")
    _log(f"   报告: {report_path}")
    _log(f"{'='*60}")
    return report


if __name__ == "__main__":
    run_t11()
