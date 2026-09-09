# -*- coding: utf-8 -*-
"""硅基流动模型选型对决赛（2026-09-09，Boss 指令：考虑成本选最适配模型）。

候选 × 36 条 heldout 查询 → IP 闭集识别准确率。
判定：按价格从低到高，取第一个 ≥0.85 的模型（0.85 为 v4 架构下 R@10≥0.91 的门槛）。
价格（元/M tokens, 硅基流动 2026-09-09）:
  GLM-Z1-9B-0414        免费
  Qwen3.5-9B            ~0.1 / 0.5  (小杯)
  Qwen3.5-35B-A3B       0.40 / 3.20
  DeepSeek-V4-Flash     1.00 / 2.00 (缓存命中 0.02)
  DeepSeek-V4.1-Flash   官方免费额度（对照组，P=0.944）
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

SF_KEY = load_api_key("SILICONFLOW_API_KEY")
SF_URL = "https://api.siliconflow.cn/v1/chat/completions"

CANDIDATES = [
    ("THUDM/GLM-Z1-9B-0414", "免费"),
    ("Qwen/Qwen3.5-9B", "~0.1/0.5"),
    ("Qwen/Qwen3.5-35B-A3B", "0.40/3.20"),
    ("deepseek-ai/DeepSeek-V4-Flash", "1.00/2.00"),
]


def call(model: str, q: str) -> str:
    data = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": q}],
        "max_tokens": 2048, "temperature": 0.1,
    }).encode("utf-8")
    req = urllib.request.Request(
        SF_URL, data=data,
        headers={"Authorization": f"Bearer {SF_KEY}",
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
    for model, price in CANDIDATES:
        ok, fails, t0 = 0, [], time.time()
        for q, expected in HELD_OUT_QUERIES:
            try:
                raw = call(model, q)
                ip = parse_ip(raw, q)
            except Exception as e:  # noqa: BLE001
                ip = f"ERR:{type(e).__name__}"
            if ip == expected:
                ok += 1
            else:
                fails.append((q[:18], expected, ip))
        acc = ok / len(HELD_OUT_QUERIES)
        results[model] = {"acc": acc, "price": price, "fails": fails}
        print(f"[{model}] 价格({price}) P={acc:.3f} ({ok}/36) "
              f"{time.time()-t0:.0f}s", flush=True)
        for q, e, g in fails[:5]:
            print(f"    错: {q} 期望={e} 实际={g}")

    out = "cache/bge_m3_index/sf_model_probe.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("->", out)


if __name__ == "__main__":
    main()
