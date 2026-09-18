#!/usr/bin/env python3
"""
Step 4 A1: B站动漫运镜数据集采集 (OP/ED + 漫剪/AMV)

背景: 自建动漫运镜数据集需要镜头语言标准的素材源 (docs/plans/
2026-08-14-step4-anime-camera-dataset.md):
  - OP/ED: 30-50 部高知名度动漫的 OP/ED (镜头语言规范, 运镜类型齐全)
  - 漫剪/AMV: 100 条 (运镜密集, 与项目素材同域)

技术要点 (2026-08-14 实测):
  - B站搜索 API 需 WBI 签名 + buvid3, 否则 412/-352 风控
    (实现见 _wbi_sign; 会话密钥缓存到 wbi_session.json)
  - 720p 免 cookie (运镜分类足够), 1080p 需 cookie
  - 断点续传: manifest.jsonl 记录已下载 BV, 重复运行自动跳过

目录布局:
  D:\\AE-Data\\AnimeCamera\\
    videos\\oped\\{anime}\\{bvid}.mp4     (OP/ED)
    videos\\amv\\{anime}\\{bvid}.mp4      (漫剪)
    manifest.jsonl                        (采集清单)
    wbi_session.json                      (运行时密钥缓存)

用法:
  py -3.12 scripts/collect_anime_camera_data.py --mode smoke   # 冒烟: 3 部各 1 条
  py -3.12 scripts/collect_anime_camera_data.py --mode oped    # 40 部 OP/ED
  py -3.12 scripts/collect_anime_camera_data.py --mode amv     # 100 条漫剪
  py -3.12 scripts/collect_anime_camera_data.py --mode all --dry-run  # 只搜索不下载
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
VIDEO_ROOT = DATA_ROOT / "videos"
MANIFEST = DATA_ROOT / "manifest.jsonl"
SESSION_CACHE = DATA_ROOT / "wbi_session.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ── 目标清单 ─────────────────────────────────────────────────────────────

# 40 部高知名度动漫 (镜头语言规范, OP/ED 制作精良)
OPED_TARGETS: list[tuple[str, list[str]]] = [
    ("进击的巨人", ["进击的巨人 NCOP", "进击的巨人 OP"]),
    ("鬼灭之刃", ["鬼灭之刃 NCOP", "鬼灭之刃 OP"]),
    ("咒术回战", ["咒术回战 NCOP", "咒术回战 OP"]),
    ("电锯人", ["电锯人 OP"]),
    ("孤独摇滚", ["孤独摇滚 NCOP", "孤独摇滚 OP"]),
    ("葬送的芙莉莲", ["葬送的芙莉莲 OP"]),
    ("间谍过家家", ["间谍过家家 NCOP", "间谍过家家 OP"]),
    ("辉夜大小姐想让我告白", ["辉夜大小姐想让我告白 OP"]),
    ("紫罗兰永恒花园", ["紫罗兰永恒花园 OP"]),
    ("冰菓", ["冰菓 OP"]),
    ("吹响吧上低音号", ["吹响吧上低音号 OP"]),
    ("魔法少女小圆", ["魔法少女小圆 OP"]),
    ("Fate stay night", ["Fate stay night OP"]),
    ("命运石之门", ["命运石之门 OP"]),
    ("刀剑神域", ["刀剑神域 OP"]),
    ("无职转生", ["无职转生 OP"]),
    ("Re从零开始的异世界生活", ["Re0 OP", "从零开始的异世界生活 OP"]),
    ("赛马娘", ["赛马娘 OP"]),
    ("灵能百分百", ["灵能百分百 OP"]),
    ("一拳超人", ["一拳超人 OP"]),
    ("火影忍者", ["火影忍者 OP"]),
    ("海贼王", ["海贼王 OP"]),
    ("死神", ["死神 OP"]),
    ("犬夜叉", ["犬夜叉 OP"]),
    ("龙珠", ["龙珠 OP"]),
    ("名侦探柯南", ["名侦探柯南 OP"]),
    ("高达SEED", ["高达SEED OP"]),
    ("反叛的鲁路修", ["反叛的鲁路修 OP"]),
    ("星际牛仔", ["星际牛仔 OP"]),
    ("新世纪福音战士", ["EVA OP"]),
    ("攻壳机动队", ["攻壳机动队 OP"]),
    ("灌篮高手", ["灌篮高手 OP"]),
    ("排球少年", ["排球少年 OP"]),
    ("蓝色监狱", ["蓝色监狱 OP"]),
    ("夏日重现", ["夏日重现 OP"]),
    ("奇巧计程车", ["奇巧计程车 OP"]),
    ("迷宫饭", ["迷宫饭 OP"]),
    ("无头骑士异闻录", ["无头骑士异闻录 OP"]),
    ("来自深渊", ["来自深渊 OP"]),
    ("三月的狮子", ["三月的狮子 OP"]),
]

# 漫剪/AMV 搜索词 (运镜密集)
AMV_TERMS: list[tuple[str, list[str]]] = [
    ("通用燃向", ["动漫 燃向混剪", "动漫 AMV 高燃", "动画 MAD 燃"]),
    ("进击的巨人", ["进击的巨人 AMV", "进击的巨人 燃向"]),
    ("鬼灭之刃", ["鬼灭之刃 AMV"]),
    ("咒术回战", ["咒术回战 AMV"]),
    ("火影忍者", ["火影忍者 AMV", "火影忍者 燃向"]),
    ("海贼王", ["海贼王 AMV"]),
    ("Fate", ["Fate AMV", "Fate 燃向 MAD"]),
    ("刀剑神域", ["刀剑神域 AMV"]),
    ("一拳超人", ["一拳超人 AMV"]),
    ("灵能百分百", ["灵能百分百 AMV"]),
    ("电锯人", ["电锯人 AMV"]),
    ("排球少年", ["排球少年 AMV"]),
    ("咒术回战2", ["咒术回战 战斗混剪"]),
    ("巨人2", ["进击的巨人 战斗混剪"]),
]

# 时长筛选 (秒)
OPED_DURATION = (45, 240)    # OP/ED 通常 90s 左右, 允许完整版 1:30-4:00
AMV_DURATION = (30, 360)     # 漫剪 30s-6min

# OP/ED 候选排除词 (翻唱/演奏/解说等非原片内容)
OPED_EXCLUDE = ("唱", "翻唱", "现场", "反应", "解说", "吐槽", "伴奏",
                "钢琴", "演奏", "reaction", "cover", "盘点", "排名")


# ── WBI 签名 ─────────────────────────────────────────────────────────────

_MIXIN_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27,
              43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48,
              7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54,
              21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]


def _http_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    h = {"User-Agent": UA, "Referer": "https://www.bilibili.com"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_session(force: bool = False) -> dict[str, str]:
    """获取并缓存 buvid3/4 + wbi 密钥 (会话级, 风控前提)。"""
    if not force and SESSION_CACHE.exists():
        try:
            return json.loads(SESSION_CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    spi = _http_json("https://api.bilibili.com/x/frontend/finger/spi")
    nav = _http_json("https://api.bilibili.com/x/web-interface/nav")
    img = nav["data"]["wbi_img"]["img_url"]
    sub = nav["data"]["wbi_img"]["sub_url"]
    session = {
        "buvid3": spi["data"]["b_3"],
        "buvid4": spi["data"]["b_4"],
        "img_key": re.search(r"/([^/]+)\.png$", img).group(1),
        "sub_key": re.search(r"/([^/]+)\.png$", sub).group(1),
    }
    SESSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_CACHE.write_text(json.dumps(session), encoding="utf-8")
    return session


def _wbi_sign(params: dict[str, Any], session: dict[str, str]) -> dict[str, Any]:
    """WBI 签名: wts + 排序编码 + 过滤特殊字符 + md5。

    注意: 必须用 quote_via=urllib.parse.quote (空格→%20), 默认 quote_plus
    会把空格编码为 +, 导致含空格关键词的签名 md5 不匹配 → 风控软失败
    (返回 code=0 但空结果, 2026-08-14 实测)。
    """
    mixin = "".join(
        (session["img_key"] + session["sub_key"])[i] for i in _MIXIN_TAB)[:32]
    params = dict(params)
    params["wts"] = int(time.time())
    q = urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote)
    q = re.sub(r"[!'()*]", "", q)
    params["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return params


def bili_search(keyword: str, page_size: int = 20, page: int = 1,
                session: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """WBI 签名的 B站视频搜索 (order=click 高播放优先)。"""
    session = session or _fetch_session()
    params = _wbi_sign({"search_type": "video", "keyword": keyword,
                        "page": page, "page_size": page_size,
                        "order": "click"}, session)
    url = ("https://api.bilibili.com/x/web-interface/wbi/search/type?"
           + urllib.parse.urlencode(params))
    data = _http_json(url, headers={"Cookie": f"buvid3={session['buvid3']}"})
    if data.get("code") != 0:
        raise RuntimeError(f"搜索失败 code={data.get('code')} msg={data.get('message')}")
    results = []
    for item in (data.get("data", {}).get("result") or []):
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        bvid = item.get("bvid", "")
        # duration 形如 "MM:SS", 解析为秒
        dur_parts = [int(x) for x in item.get("duration", "0:0").split(":")]
        duration = dur_parts[0] * 60 + dur_parts[1] if len(dur_parts) == 2 else dur_parts[0]
        if bvid:
            results.append({"bvid": bvid, "title": title, "duration": duration})
    return results


# ── 下载 ─────────────────────────────────────────────────────────────────

def download_bv(bvid: str, out_dir: Path, max_height: int = 720) -> str | None:
    """yt-dlp 下载 BV 视频 (720p 免 cookie), 返回文件路径。"""
    from yt_dlp import YoutubeDL
    out_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": (f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]"
                   f"/best"),
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / f"{bvid}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 30,
    }
    url = f"https://www.bilibili.com/video/{bvid}"
    with YoutubeDL(opts) as ydl:
        ydl.extract_info(url, download=True)
    for f in out_dir.glob(f"{bvid}.*"):
        if f.suffix in (".mp4", ".mkv", ".flv", ".webm") and f.stat().st_size > 1_000_000:
            return str(f)
    return None


# ── 主流程 ────────────────────────────────────────────────────────────────

def _load_done_bvids() -> set:
    done = set()
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["bvid"])
            except (json.JSONDecodeError, KeyError):
                pass
    return done


def _append_manifest(entry: dict[str, Any]) -> None:
    with MANIFEST.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _pick_candidates(results: list[dict[str, Any]], dur_range: tuple[int, int],
                     done: set, want: int, prefer: str = "",
                     exclude: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """筛选时长 + 去重 + 排除噪音, prefer 命中标题的排前面。"""
    picked = []
    for r in results:
        if r["bvid"] in done:
            continue
        if not (dur_range[0] <= r["duration"] <= dur_range[1]):
            continue
        title_l = r["title"].lower()
        if exclude and any(e in title_l for e in exclude):
            continue
        r["_score"] = (0 if prefer and prefer.lower() in title_l else 1)
        picked.append(r)
    picked.sort(key=lambda x: (x["_score"], -x["duration"]))
    return picked[:want]


def run_collect(mode: str, dry_run: bool, limit: int) -> dict[str, Any]:
    session = _fetch_session()
    done = _load_done_bvids()
    print(f"[collect] mode={mode} dry_run={dry_run} 已下载 {len(done)} 条")

    stats = {"searched_terms": 0, "candidates": 0, "downloaded": 0, "failed": 0}
    n_oped = 0
    n_amv = 0

    if mode in ("smoke", "oped", "all"):
        targets = OPED_TARGETS[:3] if mode == "smoke" else OPED_TARGETS
        want_per = 1
        for anime, terms in targets:
            if limit and n_oped >= limit:
                break
            for term in terms:
                if limit and n_oped >= limit:
                    break
                try:
                    results = bili_search(term, page_size=10, session=session)
                    stats["searched_terms"] += 1
                    time.sleep(1.2)  # 限速
                except Exception as exc:  # noqa: BLE001
                    print(f"  搜索失败 {term}: {exc}")
                    continue
                candidates = _pick_candidates(results, OPED_DURATION, done,
                                              want=want_per, prefer="NC",
                                              exclude=OPED_EXCLUDE)
                stats["candidates"] += len(candidates)
                for c in candidates:
                    if dry_run:
                        print(f"  [dry] {anime} | {c['bvid']} | {c['duration']}s | {c['title'][:40]}")
                        continue
                    out_dir = VIDEO_ROOT / "oped" / anime
                    try:
                        path = download_bv(c["bvid"], out_dir)
                        if path:
                            _append_manifest({
                                "bvid": c["bvid"], "title": c["title"],
                                "duration": c["duration"], "type": "oped",
                                "anime": anime, "source_term": term,
                                "path": path, "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            })
                            done.add(c["bvid"])
                            n_oped += 1
                            stats["downloaded"] += 1
                            print(f"  [OK] {anime} | {c['bvid']} | {c['title'][:36]} -> {path}")
                        else:
                            stats["failed"] += 1
                    except Exception as exc:  # noqa: BLE001
                        stats["failed"] += 1
                        print(f"  [FAIL] {c['bvid']}: {str(exc)[:60]}")
                    time.sleep(1.0)
                    if limit and n_oped >= limit:
                        break

    if mode in ("smoke", "amv", "all"):
        targets = AMV_TERMS[:3] if mode == "smoke" else AMV_TERMS
        want_per = 1 if mode == "smoke" else 6
        for anime, terms in targets:
            if limit and n_amv >= limit:
                break
            for term in terms:
                if limit and n_amv >= limit:
                    break
                try:
                    results = bili_search(term, page_size=15, session=session)
                    stats["searched_terms"] += 1
                    time.sleep(1.2)
                except Exception as exc:  # noqa: BLE001
                    print(f"  搜索失败 {term}: {exc}")
                    continue
                candidates = _pick_candidates(results, AMV_DURATION, done, want=want_per)
                stats["candidates"] += len(candidates)
                for c in candidates:
                    if dry_run:
                        print(f"  [dry] {anime} | {c['bvid']} | {c['duration']}s | {c['title'][:40]}")
                        continue
                    out_dir = VIDEO_ROOT / "amv" / anime
                    try:
                        path = download_bv(c["bvid"], out_dir)
                        if path:
                            _append_manifest({
                                "bvid": c["bvid"], "title": c["title"],
                                "duration": c["duration"], "type": "amv",
                                "anime": anime, "source_term": term,
                                "path": path, "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            })
                            done.add(c["bvid"])
                            n_amv += 1
                            stats["downloaded"] += 1
                            print(f"  [OK] {anime} | {c['bvid']} | {c['title'][:36]} -> {path}")
                        else:
                            stats["failed"] += 1
                    except Exception as exc:  # noqa: BLE001
                        stats["failed"] += 1
                        print(f"  [FAIL] {c['bvid']}: {str(exc)[:60]}")
                    time.sleep(1.0)
                    if limit and n_amv >= limit:
                        break

    return stats


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Step 4 A1: B站动漫运镜数据集采集")
    parser.add_argument("--mode", default="smoke", choices=["smoke", "oped", "amv", "all"])
    parser.add_argument("--dry-run", action="store_true", help="只搜索不下载")
    parser.add_argument("--limit", type=int, default=0, help="下载条数上限 (0=不限制)")
    parser.add_argument("--refresh-session", action="store_true", help="强制刷新 WBI 密钥")
    args = parser.parse_args()

    if args.refresh_session:
        _fetch_session(force=True)
        print("[session] WBI 密钥已刷新")
        return 0

    stats = run_collect(args.mode, args.dry_run, args.limit)
    print(f"\n=== 汇总 ===\n  {json.dumps(stats, ensure_ascii=False)}")
    print(f"  manifest -> {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
