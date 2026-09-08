# -*- coding: utf-8 -*-
"""collect_reference_candidates.py — 参照集候选采集（B站，2026-09-08）

用 yt-dlp bilisearch 多组精准关键词建候选池，输出候选 JSON 供人工/规则筛选。
只收集元数据，不下载。播放量用于质量排序（看增速/热度，不看单一绝对值）。

用法:
  python scripts/collect_reference_candidates.py [--per-query 20] [--out data/reference_top/_candidates.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# 分层关键词：tier 用于后续分层抽样（燃向/叙事/MAD/技术流）
QUERIES: list[tuple[str, str]] = [
    # --- 燃向 / 踩点（主力层，与现有 12 部同域）---
    ("AMV 高燃 踩点", "burn"),
    ("动漫 混剪 踩点 天花板", "burn"),
    ("漫剪 燃向 踩点", "burn"),
    ("MAD 踩点 燃", "burn"),
    ("高燃混剪 AMV 神级", "burn"),
    ("动漫卡点 混剪 超燃", "burn"),
    ("AMV 踩点 无缝衔接", "burn"),
    ("热血 动漫 混剪 踩点", "burn"),
    # --- 叙事 / 情感 / 静止系（第二层）---
    ("静止系 MAD", "narrative"),
    ("AMV 叙事 情感", "narrative"),
    ("动漫 情感 混剪 治愈", "narrative"),
    ("MAD 故事向", "narrative"),
    ("动漫 误解系 MAD", "narrative"),
    ("手书 AMV", "narrative"),
    ("AMV 催泪", "narrative"),
    ("静止画 MAD 日系", "narrative"),
    # --- 技术流 / 拉镜 / 特效（第三层）---
    ("AMV 拉镜 运镜", "technique"),
    ("漫剪 拉镜 教程", "technique"),
    ("AE 特效 AMV", "technique"),
    ("动漫 转场 混剪 高级", "technique"),
    ("AMV 3D 运镜", "technique"),
    ("MAD 特效 合成", "technique"),
    # --- 顶尖创作者（定向）---
    ("暗猫の祝福 AMV", "creator"),
    ("N.ec鱼丸 MAD", "creator"),
    ("泛式 MAD", "creator"),
    ("黑桃Q MAD", "creator"),
    # --- 泛检索兜底 ---
    ("AMV", "general"),
    ("动漫混剪", "general"),
    ("MAD 动漫", "general"),
]

# 排除词：教程/教学/讲解/软件/课程/合集讲解/直播
EXCLUDE_WORDS = [
    "教程", "教学", "讲解", "课程", "入门", "怎么", "如何", "零基础",
    "软件", "插件", "下载", "安装", "直播", "录播", "预告", "花絮",
    "reaction", "React", "解析", "盘点", "排行", "推荐", "科普",
]


def search(query: str, count: int) -> list[dict]:
    # 注意：B站 412 反爬在"带 cookie + 桌面 UA"组合下最易触发；
    # 实测不带 cookie 用 yt-dlp 默认 UA 可正常取流（含 1080p），故此处不加 cookie。
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
        if "_p" in vid:  # 分P，跳过（合集/教程特征）
            continue
        try:
            duration = float(dur)
        except (TypeError, ValueError):
            continue
        try:
            view = int(views)
        except (TypeError, ValueError):
            view = 0
        if not (60 <= duration <= 400):  # 与现有参照集 96-267s 同域，略放宽
            continue
        if any(w.lower() in title.lower() for w in EXCLUDE_WORDS):
            continue
        out.append({
            "bv": vid,
            "title": title,
            "duration": round(duration, 1),
            "views": view,
            "query": query,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=20)
    ap.add_argument("--out", default="data/reference_top/_candidates.json")
    args = ap.parse_args()

    existing = set()
    ref_dir = PROJ / "data" / "reference_top"
    for f in ref_dir.glob("*.mp4"):
        for tok in f.stem.split():
            pass
    # 现有 BV 号从文件名提取
    import re
    for f in ref_dir.glob("*.mp4"):
        m = re.search(r"(BV[0-9A-Za-z]{10})", f.name)
        if m:
            existing.add(m.group(1))

    pool: dict[str, dict] = {}
    for i, (q, tier) in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] {q} ...", flush=True)
        for item in search(q, args.per_query):
            if item["bv"] in existing:
                continue
            item["tier"] = tier
            if item["bv"] in pool:
                pool[item["bv"]].setdefault("queries", []).append(q)
            else:
                item["queries"] = [q]
                pool[item["bv"]] = item
        time.sleep(1.2)

    rows = sorted(pool.values(), key=lambda x: -x["views"])
    out = PROJ / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "existing_in_ref_set": sorted(existing),
        "n_existing": len(existing),
        "n_candidates": len(rows),
        "by_tier": {t: sum(1 for r in rows if r["tier"] == t)
                    for t in {q[1] for q in QUERIES}},
        "candidates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n候选池: {len(rows)} 条 → {out}")
    print(f"现有参照集 {len(existing)} 部（已排除）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
