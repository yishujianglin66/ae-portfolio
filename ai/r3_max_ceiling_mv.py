# -*- coding: utf-8 -*-
"""R3 上限冲击 v2：多数票归一化（2026-09-10，Boss"追求最高上限"）。

单次采样有 ~3% 方差翻转（水面斩击 鬼灭↔浪客行）。5 票多数制在 3 条
难例上全部拉回正确（实测 5/5、5/5、3:2）。56 查询 × 5 票，票内并行。
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
from ai.r3_query_norm_eval import (
    IP_UNIVERSE,
    SYSTEM_PROMPT,
    _log,
    load_api_key,
    run_retrieval,
)
from ai.t11_hybrid_search import TEST_QUERIES

CACHE = ROOT / "cache" / "bge_m3_index" / "query_norm_mv_cache.jsonl"
MODEL = "qwen3.8-flash"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
VOTES = 5


def _one_vote(url, key, q):
    import urllib.error
    import urllib.request
    data = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": q}],
        "max_tokens": 2048, "temperature": 0.4,
    }).encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/chat/completions", data=data,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    for delay in (0, 5, 15):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"].strip()
        except Exception:  # noqa: BLE001
            continue
    return ""


def norm_one(url, key, q):
    """5 票多数制归一化（票内并行）；expanded 取多数票同阵营里的首个。"""
    with ThreadPoolExecutor(max_workers=VOTES) as ex:
        raws = list(ex.map(lambda _: _one_vote(url, key, q), range(VOTES)))
    parsed = []
    for raw in raws:
        js = raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else ""
        try:
            d = json.loads(js)
            ip = d.get("ip", "NO_IP")
            if ip != "NO_IP" and ip not in IP_UNIVERSE:
                ip = "NO_IP"
            parsed.append((ip, d.get("expanded", q)))
        except Exception:
            parsed.append(("NO_IP", q))
    counts = Counter(ip for ip, _ in parsed)
    ip = counts.most_common(1)[0][0]
    expanded = next((e for i, e in parsed if i == ip), q)
    return {"query": q, "ip": ip, "expanded": expanded,
            "backend": "BAILIAN", "model": f"{MODEL}x{VOTES}mv",
            "votes": dict(counts)}


def main():
    all_queries = [q for q, _ in HELD_OUT_QUERIES] + [q for q, _ in TEST_QUERIES]
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                cache[d["query"]] = d
            except Exception:
                continue
    todo = [q for q in all_queries if q not in cache]
    _log(f"Phase1-MV: 共 {len(all_queries)}，缓存 {len(cache)}，待做 {len(todo)}")
    if todo:
        key = load_api_key("BAILIAN_API_KEY") or load_api_key("DASHSCOPE_API_KEY")
        t0 = time.time()
        with open(CACHE, "a", encoding="utf-8") as f:
            for q in todo:
                rec = norm_one(BASE_URL, key, q)
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                cache[q] = rec
        _log(f"  完成 {len(todo)} 条，{time.time()-t0:.0f}s")
    for name, qset in (("heldout", HELD_OUT_QUERIES), ("legacy", TEST_QUERIES)):
        ok = sum(1 for q, ip in qset if cache[q]["ip"] == ip)
        _log(f"  [{name}] 多数票识别率 {ok}/{len(qset)}")
    run_retrieval(cache)


if __name__ == "__main__":
    main()
