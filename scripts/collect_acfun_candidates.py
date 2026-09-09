# -*- coding: utf-8 -*-
"""collect_acfun_candidates.py — AcFun 参照集候选采集（2026-09-08）

为什么加 AcFun：B站 检索域缺少"国际赛事级"AMV（AKROSS Con 等），而 AcFun 有
历年 AKROSS Con 单部参赛作品（非合集），这是比 B站头部更接近国际评审水平的素材，
可补 B站 单一平台偏差。

注意：AcFun 搜索结果里 `videoId` 与 `contentId` 不同，实际可下载 URL 用
`https://www.acfun.cn/v/ac<contentId>`（实测 200；用 videoId 会 404）。

安全约束（发请求前强制校验）：
  - 仅允许 http/https；
  - host 必须在白名单内（www.acfun.cn）；
  - DNS 解析后拒绝 localhost / 环回 / 私有 / 保留 / 链路本地 / 多播地址；
  - 禁重定向（避免跳转到非白名单主机）。

用法: python scripts/collect_acfun_candidates.py --per-query 30
输出: data/reference_top/_candidates_acfun.json
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import time
import urllib.parse
import urllib.request
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
OUT = REF_DIR / "_candidates_acfun.json"

# 只采国际赛事/高质量域；"漫剪""静止系"在 AcFun 为 0 结果，故不列
QUERIES: list[tuple[str, str]] = [
    ("AKROSS", "contest"),
    ("AMV 大赛", "contest"),
    ("AMV", "amv"),
    ("MAD", "mad"),
    ("AMV 高燃", "amv"),
    ("MAD 高燃", "mad"),
    ("一拳超人 AMV", "amv"),
    ("FATE AMV", "amv"),
    ("火影 AMV", "amv"),
    ("进击的巨人 AMV", "amv"),
]

EXCLUDE_WORDS = [
    "合集", "教程", "教学", "讲解", "课程", "入门", "怎么", "如何",
    "软件", "插件", "下载", "安装", "直播", "录播", "预告", "花絮",
    "reaction", "解析", "盘点", "排行", "推荐", "科普", "大赛",
]

API_HOST = "www.acfun.cn"
API_PATH = "/rest/pc-direct/search/video"
ALLOWED_HOSTS = (API_HOST,)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def ip_is_public(ip: str) -> bool:
    """拒绝环回/私有/保留/链路本地/多播/未指定地址。"""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (a.is_private or a.is_loopback or a.is_link_local
                or a.is_reserved or a.is_multicast or a.is_unspecified)


def url_is_safe(url: str) -> bool:
    """仅 http/https + host 白名单 + 解析后全部 IP 为公网。"""
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https"):
        return False
    host = (u.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return False
    if u.port not in (None, 80, 443):
        return False
    try:
        infos = socket.getaddrinfo(host, u.port or 443,
                                   proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return False
    if not infos:
        return False
    return all(ip_is_public(i[4][0]) for i in infos)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """禁止重定向，避免被跳转到非白名单主机。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def fetch(kw: str, n: int) -> list[dict]:
    """取 AcFun 搜索 JSON（URL 先过 url_is_safe 校验）。"""
    url = (f"https://{API_HOST}{API_PATH}?"
           + urllib.parse.urlencode({"keyword": kw, "pageNo": 1, "pageSize": n}))
    if not url_is_safe(url):
        print(f"  [拒绝] URL 未通过安全校验: {kw}")
        return []
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": f"https://{API_HOST}"})
    for i in range(3):
        try:
            with _OPENER.open(req, timeout=30) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return d.get("videoList") or []
        except Exception:
            if i < 2:
                time.sleep(5 * (i + 1))
    return []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-query", type=int, default=30)
    args = ap.parse_args()

    pool: dict[str, dict] = {}
    if OUT.exists():
        try:
            pool = {c["cid"]: c for c in
                    json.loads(OUT.read_text(encoding="utf-8"))["candidates"]}
        except Exception:
            pool = {}

    for i, (kw, tier) in enumerate(QUERIES, 1):
        items = fetch(kw, args.per_query)
        print(f"[{i}/{len(QUERIES)}] {kw}: {len(items)} 条", flush=True)
        for v in items:
            cid = str(v.get("contentId") or "")
            title = str(v.get("title") or v.get("emTitle") or "")
            dur = v.get("playDuration") or 0
            try:
                parts = str(dur).replace("s", "").split(":")
                secs = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
            except Exception:
                secs = 0
            if not cid.isdigit() or not title:
                continue
            if not (60 <= secs <= 400):
                continue
            if any(w.lower() in title.lower() for w in EXCLUDE_WORDS):
                continue
            if cid in pool:
                continue
            pool[cid] = {
                "cid": cid,
                "url": f"https://{API_HOST}/v/ac{cid}",
                "title": title,
                "duration": secs,
                "views": int(v.get("viewCount") or 0),
                "tier": tier,
                "platform": "acfun",
            }
        time.sleep(1.2)

    rows = sorted(pool.values(), key=lambda x: -x["views"])
    OUT.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_candidates": len(rows),
        "by_tier": {t: sum(1 for r in rows if r["tier"] == t)
                    for t in {q[1] for q in QUERIES}},
        "note": "AcFun: 下载 URL 用 contentId 构造 /v/ac<cid>；videoId 会 404",
        "candidates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nAcFun 候选池: {len(rows)} 条 → {OUT}")
    tiers = {t: sum(1 for r in rows if r["tier"] == t) for t in {q[1] for q in QUERIES}}
    print(f"分层: {json.dumps(tiers, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
