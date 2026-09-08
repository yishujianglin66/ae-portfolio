# -*- coding: utf-8 -*-
"""collect_reference_candidates2.py — 参照集候选补充采集（技术流/叙事向缺口）

第一轮采集（collect_reference_candidates.py）的 technique 层全部命中教程/素材包，
被相关性闸门正确排除，导致技术流层为 0。本脚本用更精准的关键词补采，
要求标题同时含「作品信号 + 技术信号」，避免混入教学与素材包。

用法: python scripts/collect_reference_candidates2.py --per-query 20
输出: 合并进 data/reference_top/_candidates.json（保留既有条目）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
CAND = REF_DIR / "_candidates.json"

# 技术流：关键词组合要求"作品名 + 技术词"，避开教程
QUERIES: list[tuple[str, str]] = [
    ("AMV 拉镜 神级", "technique"),
    ("漫剪 运镜 高级感", "technique"),
    ("MAD 转场 无缝", "technique"),
    ("AMV 三维 空间 运镜", "technique"),
    ("动漫 混剪 特效 燃", "technique"),
    ("AMV 分镜 设计", "technique"),
    ("漫剪 推拉 镜头", "technique"),
    ("AMV 无缝转场", "technique"),
    ("动漫 混剪 遮罩 转场", "technique"),
    ("MAD 时间重映射", "technique"),
    # 叙事向补强
    ("静止系 MAD 神作", "narrative"),
    ("AMV 叙事 故事向", "narrative"),
    ("动漫 手书 PV", "narrative"),
    ("MAD 误解系 神作", "narrative"),
    ("AMV 治愈 情感 混剪", "narrative"),
    # 创作者定向
    ("Xenoz AMV", "creator"),
    ("Donya AMV", "creator"),
    ("Floby AMV", "creator"),
]

EXCLUDE_WORDS = [
    "教程", "教学", "讲解", "课程", "入门", "怎么", "如何", "零基础",
    "软件", "插件", "下载", "安装", "直播", "录播", "预告", "花絮",
    "reaction", "React", "解析", "盘点", "排行", "推荐", "科普",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def search(query: str, count: int) -> list[dict]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--print", "%(id)s\t%(title)s\t%(duration)s\t%(view_count)s",
        f"bilisearch{count}:{query}",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print(f"  [timeout] {query}")
        return []
    out = []
    for line in r.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        vid, title, dur, views = parts[0], parts[1], parts[2], parts[3]
        if "_p" in vid:
            continue
        try:
            duration = float(dur)
            view = int(views)
        except (TypeError, ValueError):
            continue
        if not (60 <= duration <= 400):
            continue
        if any(w.lower() in title.lower() for w in EXCLUDE_WORDS):
            continue
        out.append({"bv": vid, "title": title, "duration": round(duration, 1),
                    "views": view, "query": query})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=20)
    args = ap.parse_args()

    data = json.loads(CAND.read_text(encoding="utf-8"))
    pool = {c["bv"]: c for c in data["candidates"]}
    before = len(pool)

    added = 0
    for i, (q, tier) in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] {q} ...", flush=True)
        for item in search(q, args.per_query):
            if item["bv"] in pool:
                continue
            item["tier"] = tier
            item["queries"] = [q]
            pool[item["bv"]] = item
            added += 1
        time.sleep(1.2)

    rows = sorted(pool.values(), key=lambda x: -x["views"])
    data["candidates"] = rows
    data["n_candidates"] = len(rows)
    data["by_tier"] = {}
    for r in rows:
        data["by_tier"][r["tier"]] = data["by_tier"].get(r["tier"], 0) + 1
    data["supplemented"] = time.strftime("%Y-%m-%d %H:%M:%S")
    CAND.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n候选池 {before} → {len(rows)}（新增 {added}）")
    print(f"分层: {data['by_tier']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
