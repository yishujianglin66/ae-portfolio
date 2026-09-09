# -*- coding: utf-8 -*-
"""百炼 flash 系模型质量对决赛（2026-09-09，第二额度池）。

Boss 提供新 key（与旧 DASHSCOPE key 模型宇宙一致、额度池独立）。
候选 = flash 系（百炼最便宜/免费额度档）× 36 条 heldout 查询。
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ai.r3_benchmark_v2 import HELD_OUT_QUERIES
from ai.r3_query_norm_eval import IP_UNIVERSE, SYSTEM_PROMPT, load_api_key

BL_KEY = load_api_key("BAILIAN_API_KEY")
BL_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

CANDIDATES = [
    "qwen-flash",
    "qwen3.8-flash",
    "qwen3.6-flash",
    "qwen3.5-flash",
]


def call(model: str, q: str) -> str:
    data = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": q}],
        "max_tokens": 2048, "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        BL_URL, data=data,
        headers={"Authorization": f"Bearer {BL_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"].strip()


def parse_ip(raw: str, q: str) -> str:
    js = raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else ""
    try:
        d = json.loads(js)
        ip = d.get("ip", "NO_IP")
    except Exception:
        ip = "NO_IP"
    if ip != "NO_IP" and ip not in IP_UNIVERSE:
        ip = "NO_IP"
    return ip


def main():
    results = {}
    for model in CANDIDATES:
        ok, fails, t0 = 0, [], time.time()
        for q, expected in HELD_OUT_QUERIES:
            try:
                ip = parse_ip(call(model, q), q)
            except Exception as e:  # noqa: BLE001
                ip = f"ERR:{type(e).__name__}"
            if ip == expected:
                ok += 1
            else:
                fails.append((q[:18], expected, ip))
        acc = ok / len(HELD_OUT_QUERIES)
        results[model] = {"acc": acc, "fails": fails}
        print(f"[{model}] P={acc:.3f} ({ok}/36) {time.time()-t0:.0f}s",
              flush=True)
        for q, e, g in fails[:5]:
            print(f"    错: {q} 期望={e} 实际={g}")

    out = "cache/bge_m3_index/bl_model_probe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("->", out)


if __name__ == "__main__":
    main()
