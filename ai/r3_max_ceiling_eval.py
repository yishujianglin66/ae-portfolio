# -*- coding: utf-8 -*-
"""R3 上限冲击（2026-09-10，Boss 指令"追求最高上限和呈现效果推进"）。

路径：对决赛满分归一器 qwen3.8-flash（P=1.000，36/36）重跑全部 56 条归一化
→ Phase2 检索评测。对照当前主力 deepseek-v4.1-flash（P=0.944 → R@10 0.944）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
from ai.r3_query_norm_eval import (
    IP_UNIVERSE,
    SYSTEM_PROMPT,
    _call_with_retry,
    _log,
    load_api_key,
    run_retrieval,
)
from ai.t11_hybrid_search import TEST_QUERIES

CACHE = ROOT / "cache" / "bge_m3_index" / "query_norm_q38f_cache.jsonl"
MODEL = "qwen3.8-flash"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def run_norm_q38f(queries: list):
    """qwen3.8-flash 归一化（独立缓存，断点续传）。"""
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                if d.get("raw"):
                    cache[d["query"]] = d
            except Exception:
                continue
    todo = [q for q in queries if q not in cache]
    _log(f"Phase1-Q38F: 共 {len(queries)}，缓存 {len(cache)}，待做 {len(todo)}")
    if not todo:
        return cache

    key = load_api_key("BAILIAN_API_KEY") or load_api_key("DASHSCOPE_API_KEY")
    t0 = time.time()
    with open(CACHE, "a", encoding="utf-8") as f:
        for q in todo:
            try:
                raw = _call_with_retry(BASE_URL, key, MODEL, q)
            except Exception as e:  # noqa: BLE001
                _log(f"  [WARN] {q[:16]}: {type(e).__name__}")
                raw = ""
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
                   "backend": "BAILIAN", "model": MODEL, "raw": raw[:200]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            cache[q] = rec
    _log(f"  完成 {len(todo)} 条，{time.time()-t0:.0f}s -> {CACHE}")
    return cache


def main():
    all_queries = [q for q, _ in HELD_OUT_QUERIES] + [q for q, _ in TEST_QUERIES]
    norm = run_norm_q38f(all_queries)
    # 识别率速报
    for name, qset in (("heldout", HELD_OUT_QUERIES), ("legacy", TEST_QUERIES)):
        ok = sum(1 for q, ip in qset if norm[q]["ip"] == ip)
        _log(f"  [{name}] qwen3.8-flash 识别率 {ok}/{len(qset)}")
    run_retrieval(norm)


if __name__ == "__main__":
    main()
