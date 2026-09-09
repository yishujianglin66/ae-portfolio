# -*- coding: utf-8 -*-
"""collect_masters_candidates.py — 大师名 / 领域权威定向采集（2026-09-08）

背景：第一轮关键词检索的技术流层为空（该关键词域全是教程），且国际赛事覆盖面窄。
本脚本改用**具体人名**定向检索——大师作品被搬运到国内平台时，标题里通常带名字，
这比风格词更精准。

名单来源（不凭空编造）：
  - 12-漫剪拉镜大师：Xenoz / Donya / Floby / Molob / DxshNova / YUNG_DAGGER / YashFX
  - 11-大师知识库：Andrew Kramer / Ben Marriott / Casey Neistat / Devin Graham /
    Jordy Vandeput / MtMograph / Peter McKinnon / School of Motion / Zack Royce
  - 报告已提国内创作者：暗猫の祝福 / N.ec鱼丸 / 泛式 / 黑桃Q / NanaMi / Sakuramai / Crossfade

双平台：B站（yt-dlp bilisearch）+ AcFun（官方搜索 API，带 host 白名单与公网 IP 校验）。

用法: python scripts/collect_masters_candidates.py --per-query 15
输出: data/reference_top/_candidates_masters.json
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
OUT = REF_DIR / "_candidates_masters.json"

# (搜索词, 归属类别) —— 类别用于分层统计
NAMES: list[tuple[str, str]] = [
    # --- 12 号库：漫剪拉镜大师 ---
    ("Xenoz", "master_lens"),
    ("Xenoz AMV", "master_lens"),
    ("Donya AMV", "master_lens"),
    ("Donya 拉镜", "master_lens"),
    ("Floby AMV", "master_lens"),
    ("Floby 韩式", "master_lens"),
    ("Molob AMV", "master_lens"),
    ("Molob Yoav", "master_lens"),
    ("DxshNova", "master_lens"),
    ("YUNG DAGGER AMV", "master_lens"),
    ("YashFX", "master_lens"),
    # --- 11 号库：运动设计 / 影视权威 ---
    ("Andrew Kramer", "authority"),
    ("Video Copilot", "authority"),
    ("Ben Marriott", "authority"),
    ("MtMograph", "authority"),
    ("School of Motion", "authority"),
    ("Zack Royce", "authority"),
    ("Peter McKinnon", "authority"),
    ("Casey Neistat", "authority"),
    ("Jordy Vandeput", "authority"),
    ("Devin Graham", "authority"),
    # --- 国内知名创作者 ---
    ("暗猫の祝福", "creator_cn"),
    ("鱼丸 MAD", "creator_cn"),
    ("泛式 MAD", "creator_cn"),
    ("黑桃Q MAD", "creator_cn"),
    ("NanaMi AMV", "creator_cn"),
    ("Sakuramai", "creator_cn"),
    ("Crossfade AMV", "creator_cn"),
    # --- 国际赛事/团队（作品常以团队名出现） ---
    ("AKROSS Con", "contest"),
    ("Anime Expo AMV", "contest"),
    ("AMV 大赛 获奖", "contest"),
]

EXCLUDE_WORDS = [
    "教程", "教学", "讲解", "课程", "入门", "怎么", "如何", "零基础",
    "软件", "插件", "下载", "安装", "直播", "录播", "预告", "花絮",
    "reaction", "解析", "盘点", "排行", "推荐", "科普", "合集", "大赛",
    "采访", "访谈", "课程", "workshop", "tutorial",
]

# AcFun 请求安全约束
AC_HOST = "www.acfun.cn"
AC_PATH = "/rest/pc-direct/search/video"
AC_ALLOWED = (AC_HOST,)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


# ---------------- AcFun ----------------

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


# ---------------- B站 ----------------

def bili_search(kw: str, n: int) -> list[dict]:
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--print", "%(id)s\t%(title)s\t%(duration)s\t%(view_count)s",
        f"bilisearch{n}:{kw}",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return []
    out = []
    for line in r.stdout.strip().split("\n"):
        p = line.split("\t")
        if len(p) < 4:
            continue
        vid, title, dur, views = p[0], p[1], p[2], p[3]
        if "_p" in vid:
            continue
        try:
            duration = float(dur)
            view = int(views)
        except (TypeError, ValueError):
            continue
        out.append({"id": vid, "title": title, "duration": duration, "views": view})
    return out


def parse_acfun_dur(s) -> int:
    try:
        parts = str(s).replace("s", "").split(":")
        return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
    except Exception:
        return 0


def accept(title: str, secs: float) -> bool:
    if not (60 <= secs <= 400):
        return False
    if any(w.lower() in title.lower() for w in EXCLUDE_WORDS):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=15)
    args = ap.parse_args()

    pool: dict[str, dict] = {}
    if OUT.exists():
        try:
            pool = {c["key"]: c for c in
                    json.loads(OUT.read_text(encoding="utf-8"))["candidates"]}
        except Exception:
            pool = {}

    for i, (kw, cat) in enumerate(NAMES, 1):
        n_b = n_a = 0
        # B站
        for it in bili_search(kw, args.per_query):
            if not accept(it["title"], it["duration"]):
                continue
            key = it["id"]
            if key in pool:
                continue
            pool[key] = {"key": key, "platform": "bilibili", "id": it["id"],
                         "url": f"https://www.bilibili.com/video/{it['id']}",
                         "title": it["title"], "duration": round(it["duration"], 1),
                         "views": it["views"], "category": cat, "query": kw}
            n_b += 1
        # AcFun
        for v in acfun_search(kw, args.per_query):
            cid = str(v.get("contentId") or "")
            title = str(v.get("title") or v.get("emTitle") or "")
            secs = parse_acfun_dur(v.get("playDuration"))
            if not cid.isdigit() or not accept(title, secs):
                continue
            key = f"ac{cid}"
            if key in pool:
                continue
            pool[key] = {"key": key, "platform": "acfun", "id": cid,
                         "url": f"https://{AC_HOST}/v/ac{cid}",
                         "title": title, "duration": secs,
                         "views": int(v.get("viewCount") or 0),
                         "category": cat, "query": kw}
            n_a += 1
        print(f"[{i}/{len(NAMES)}] {kw}: B站 +{n_b} / AcFun +{n_a}", flush=True)
        time.sleep(1.2)

    rows = sorted(pool.values(), key=lambda x: -x["views"])
    cats: dict[str, int] = {}
    for r in rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    OUT.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_candidates": len(rows),
        "by_category": cats,
        "by_platform": {p: sum(1 for r in rows if r["platform"] == p)
                        for p in {r["platform"] for r in rows}},
        "candidates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n大师名候选池: {len(rows)} 条 → {OUT}")
    print(f"类别: {json.dumps(cats, ensure_ascii=False)}")
    print(f"平台: {json.dumps({p: sum(1 for r in rows if r['platform'] == p) for p in {r['platform'] for r in rows}}, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
