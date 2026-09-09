# -*- coding: utf-8 -*-
"""collect_style_series_candidates.py — 木偶 / 手书系列定向采集（2026-09-08）

背景：参照集已覆盖漫剪燃向、叙事、国际赛事、大师运镜，但**木偶动画**与**手书 PV**
两个风格域为空。本脚本按风格关键词双平台（B站 + AcFun）采集候选。

风格关键词依据项目内部知识库：
  - 木偶：10-风格化剪辑知识库《木偶专文》/ puppet-automation —— 纸片人、骨骼、Live2D、皮影
  - 手书：手书 PV 惯例（8-12fps 有限动画 + 3枚撮り）—— 手书、手繪、描改、动态分镜

安全约束：AcFun 请求前校验协议 + host 白名单 + DNS 解析后拒绝环流/私有/保留地址。

用法: python scripts/collect_style_series_candidates.py --per-query 20
输出: data/reference_top/_candidates_styles.json
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
OUT = REF_DIR / "_candidates_styles.json"

# (搜索词, 系列) —— series 用于分层统计
QUERIES: list[tuple[str, str]] = [
    # ---- 木偶 / 纸片人 / 骨骼 ----
    ("木偶动画", "puppet"),
    ("纸片人 动画", "puppet"),
    ("皮影 动画", "puppet"),
    ("布偶 动画", "puppet"),
    ("骨骼动画 二次元", "puppet"),
    ("Live2D 动画", "puppet"),
    ("Live2D 舞蹈", "puppet"),
    ("MMD 动画", "puppet"),
    ("木偶戏 动漫", "puppet"),
    ("纸片人 跳舞", "puppet"),
    # ---- 手书 / 手绘 PV ----
    ("手书", "handdrawn"),
    ("手书 PV", "handdrawn"),
    ("手书 MAD", "handdrawn"),
    ("手绘动画 PV", "handdrawn"),
    ("描改手书", "handdrawn"),
    ("动画手书", "handdrawn"),
    ("手书 原神", "handdrawn"),
    ("手书 咒术回战", "handdrawn"),
    ("手书 进击的巨人", "handdrawn"),
    ("手书 鬼灭之刃", "handdrawn"),
    ("手書 PV", "handdrawn"),
    ("手绘 静止画", "handdrawn"),
]

# 排除：教程/素材/合集/非作品
EXCLUDE_WORDS = [
    "教程", "教学", "讲解", "课程", "入门", "怎么", "如何", "零基础",
    "软件", "插件", "下载", "安装", "直播", "录播", "预告", "花絮",
    "reaction", "解析", "盘点", "排行", "推荐", "科普", "合集", "采访",
    "访谈", "素材", "模型配布", "教程分享", "制作过程", "过程记录",
]

AC_HOST = "www.acfun.cn"
AC_PATH = "/rest/pc-direct/search/video"
AC_ALLOWED = (AC_HOST,)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def ip_is_public(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local
                or a.is_reserved or a.is_multicast or a.is_unspecified)


def url_is_safe(url: str) -> bool:
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https"):
        return False
    host = (u.hostname or "").lower()
    if host not in AC_ALLOWED:
        return False
    if u.port not in (None, 80, 443):
        return False
    try:
        infos = socket.getaddrinfo(host, u.port or 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return False
    return bool(infos) and all(ip_is_public(i[4][0]) for i in infos)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def acfun_search(kw: str, n: int) -> list[dict]:
    url = (f"https://{AC_HOST}{AC_PATH}?"
           + urllib.parse.urlencode({"keyword": kw, "pageNo": 1, "pageSize": n}))
    if not url_is_safe(url):
        return []
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": f"https://{AC_HOST}"})
    for i in range(3):
        try:
            with _OPENER.open(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return d.get("videoList") or []
        except Exception:
            if i < 2:
                time.sleep(4 * (i + 1))
    return []


def bili_search(kw: str, n: int) -> list[dict]:
    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings",
           "--print", "%(id)s\t%(title)s\t%(duration)s\t%(view_count)s",
           f"bilisearch{n}:{kw}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in r.stdout.strip().split("\n"):
        p = line.split("\t")
        if len(p) < 4 or "_p" in p[0]:
            continue
        try:
            out.append({"id": p[0], "title": p[1],
                        "duration": float(p[2]), "views": int(p[3])})
        except (TypeError, ValueError):
            continue
    return out


def parse_dur(s) -> int:
    try:
        parts = str(s).replace("s", "").split(":")
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
    except Exception:
        return 0


def accept(title: str, secs: float) -> bool:
    if not (30 <= secs <= 400):
        return False
    return not any(w.lower() in title.lower() for w in EXCLUDE_WORDS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=20)
    args = ap.parse_args()

    pool: dict[str, dict] = {}
    if OUT.exists():
        try:
            pool = {c["key"]: c for c in
                    json.loads(OUT.read_text(encoding="utf-8"))["candidates"]}
        except Exception:
            pool = {}

    for i, (kw, series) in enumerate(QUERIES, 1):
        nb = na = 0
        for it in bili_search(kw, args.per_query):
            if not accept(it["title"], it["duration"]):
                continue
            if it["id"] in pool:
                continue
            pool[it["id"]] = {
                "key": it["id"], "platform": "bilibili", "id": it["id"],
                "url": f"https://www.bilibili.com/video/{it['id']}",
                "title": it["title"], "duration": round(it["duration"], 1),
                "views": it["views"], "series": series, "query": kw}
            nb += 1
        for v in acfun_search(kw, args.per_query):
            cid = str(v.get("contentId") or "")
            title = str(v.get("title") or v.get("emTitle") or "")
            secs = parse_dur(v.get("playDuration"))
            if not cid.isdigit() or not accept(title, secs):
                continue
            key = f"ac{cid}"
            if key in pool:
                continue
            pool[key] = {
                "key": key, "platform": "acfun", "id": cid,
                "url": f"https://{AC_HOST}/v/ac{cid}",
                "title": title, "duration": secs,
                "views": int(v.get("viewCount") or 0),
                "series": series, "query": kw}
            na += 1
        print(f"[{i}/{len(QUERIES)}] {kw}: B站 +{nb} / AcFun +{na}", flush=True)
        time.sleep(1.2)

    rows = sorted(pool.values(), key=lambda x: -x["views"])
    series_cnt: dict[str, int] = {}
    for r in rows:
        series_cnt[r["series"]] = series_cnt.get(r["series"], 0) + 1
    OUT.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_candidates": len(rows),
        "by_series": series_cnt,
        "by_platform": {p: sum(1 for r in rows if r["platform"] == p)
                        for p in {r["platform"] for r in rows}},
        "candidates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n风格系列候选池: {len(rows)} 条 → {OUT}")
    print(f"系列: {json.dumps(series_cnt, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
