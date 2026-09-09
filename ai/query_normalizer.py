# -*- coding: utf-8 -*-
"""生产查询归一化器（2026-09-10，R3 收官产物）。

把用户的自然语言描述归一化为 IP 闭集判定 + 扩展查询：
  多数票 API 归一化（5 票并行，qwen3.8-flash 领衔）→ {"ip", "expanded"}
  识别失败/无 key → {"ip": "NO_IP", ...}，调用方回退 D 臂。

质量依据（36 条 heldout 实测）：
  单票 qwen3.8-flash P=0.972；5 票多数制 P=1.000（方差翻转全救回）。
额度链：BAILIAN/DASHSCOPE 双 key 双池 → DeepSeek → SiliconFlow，
  额度耗尽(HTTP 400/402/403/404/429)换模型，网络瞬断退避重试。
开关：AEKV_NORM_API=1（默认关）；key 从 env 或 cache/api_keys.json 取。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "bge_m3_index" / "query_norm_mv_cache.jsonl"
KEYS_FILE = ROOT / "cache" / "api_keys.json"  # gitignored

NORM_API_ENV = "AEKV_NORM_API"
VOTES = 5
TEMPERATURE = 0.4
MAX_TOKENS = 2048  # 推理模型思考走 reasoning_content，小了 content 会被截断

# 质量排序（2026-09-09/10 对决赛）：qwen3.8-flash 满分领衔，双 key 双池，
# DeepSeek 系与硅基流动 DeepSeek-V4-Flash 兜底
NORMALIZER_BACKENDS = [
    {"name": "BAILIAN", "base_url":
     "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "key_env": "BAILIAN_API_KEY", "models": ["qwen3.8-flash"]},
    {"name": "DASHSCOPE", "base_url":
     "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "key_env": "DASHSCOPE_API_KEY", "models": ["qwen3.8-flash"]},
    {"name": "DEEPSEEK", "base_url": "https://api.deepseek.com/v1",
     "key_env": "DEEPSEEK_API_KEY",
     "models": ["deepseek-v4.1-flash-expires-on-0910", "deepseek-v4-flash"]},
    {"name": "SILICONFLOW", "base_url": "https://api.siliconflow.cn/v1",
     "key_env": "SILICONFLOW_API_KEY",
     "models": ["deepseek-ai/DeepSeek-V4-Flash"]},
]

# IP 闭集 = 伪标签语料全部 IP（生产索引 manifest）
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


def _load_key(name: str) -> str:
    v = os.environ.get(name, "")
    if v:
        return v
    try:
        data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        return data.get(name, "")
    except Exception:  # noqa: BLE001
        return ""


def _chain() -> list:
    out = []
    for b in NORMALIZER_BACKENDS:
        key = _load_key(b["key_env"])
        if key:
            out.extend((b["name"], b["base_url"], key, m) for m in b["models"])
    return out


def _one_vote(base_url: str, key: str, model: str, q: str) -> str:
    data = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": q}],
        "max_tokens": MAX_TOKENS, "temperature": TEMPERATURE,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=data,
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"})
    for delay in (0, 5, 15):  # 网络瞬断退避；额度类错误直接失败换模型
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                d = json.loads(r.read())
            return d["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError:
            return ""
        except urllib.error.URLError:
            continue
    return ""


def _parse(raw: str, q: str):
    js = raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw else ""
    try:
        d = json.loads(js)
        ip = d.get("ip", "NO_IP")
        if ip != "NO_IP" and ip not in IP_UNIVERSE:
            ip = "NO_IP"
        return ip, d.get("expanded", q)
    except Exception:
        return "NO_IP", q


def _load_cache() -> dict:
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(line)
                cache[d["query"]] = d
            except Exception:
                continue
    return cache


def normalize_query(query: str, votes: int = VOTES) -> dict:
    """多数票归一化。返回 {"ip","expanded","votes"}；无 key/全失败 → NO_IP。"""
    query = (query or "").strip()
    if not query:
        return {"query": query, "ip": "NO_IP", "expanded": query, "votes": {}}
    if os.environ.get(NORM_API_ENV, "0") != "1":
        return {"query": query, "ip": "NO_IP", "expanded": query, "votes": {}}
    cached = _load_cache().get(query)
    if cached:
        return cached
    rec = {"query": query, "ip": "NO_IP", "expanded": query, "votes": {}}
    for name, base_url, key, model in _chain():
        with ThreadPoolExecutor(max_workers=votes) as ex:
            raws = list(ex.map(lambda _: _one_vote(base_url, key, model, query),
                               range(votes)))
        parsed = [_parse(r, query) for r in raws if r]
        if not parsed:
            continue  # 该模型不可用/额度尽 → 推进
        counts = Counter(ip for ip, _ in parsed)
        ip = counts.most_common(1)[0][0]
        expanded = next((e for i, e in parsed if i == ip), query)
        rec = {"query": query, "ip": ip, "expanded": expanded,
               "backend": name, "model": model, "votes": dict(counts)}
        break
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass
    return rec
