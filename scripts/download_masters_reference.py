# -*- coding: utf-8 -*-
"""download_masters_reference.py — 大师名定向参照集下载（2026-09-08）

从 collect_masters_candidates.py 的候选池中，经**严格相关性闸门**筛选后下载：
  1. 标题必须命中 AMV 域信号（amv/mad/混剪/踩点/静止/手书/拉镜…）；
  2. 标题必须含目标大师名（检索词首词），防止"韩式"搜出韩餐这类串词；
  3. 排除 cosplay/漫展/美食/字幕组/教学/合集/翻唱等非 AMV 内容。

双平台支持：B站（`[BVxxx]`）与 AcFun（`[acxxx]`），文件名沿用现有惯例。

用法: python scripts/download_masters_reference.py --target 25 [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
CAND = REF_DIR / "_candidates_masters.json"
MANIFEST = REF_DIR / "_manifest.json"
FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

AMV_SIG = ["amv", "mad", "混剪", "踩点", "卡点", "静止", "手书", "燃向",
           "拉镜", "运镜", "衔接", "漫剪", "剧情向", "误解系"]
# 排除非 AMV 作品 / 反应类 / 非日漫域 / 模仿二创
BAD = ["cosplay", "漫展", "美食", "做饭", "料理", "食谱", "字幕组", "office",
       "copilot", "cover", "教学", "教程", "直播", "采访", "访谈", "合集",
       "预告", "reaction", "cos大赏", "宅舞", "舞蹈", "翻唱", "唱见",
       "看mad", "看amv", "看泛式", "泛式看", "生贺", "盘点", "排行",
       "仿:", "仿：", "模仿", "locking", "popping", "柚恩",
       "ben 10", "少年骇客", "b10", "椰子", "小椰", "柔柔", "kamayami"]
SAFE_CHARS = re.compile(r"[^\w\u4e00-\u9fff \-\[\]\(\)（）「」·~!！？?、。，,.]+")
BV_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")
CID_RE = re.compile(r"^\d{4,12}$")


def sanitize(title: str) -> str:
    t = SAFE_CHARS.sub(" ", title)
    return (re.sub(r"\s+", " ", t).strip()[:100]) or "untitled"


def dest_for(root: Path, name: str) -> Path | None:
    """在 root 内构造目标路径。

    只接受纯文件名（无目录成分）。注意：不能用 `".." in name` 判定路径穿越——
    标题里的省略号 `......` 会误伤；只要 Path(name).name == name 就说明无分隔符，
    再由 resolve 后的 parent 复核。
    """
    if not name or Path(name).name != name:
        return None
    if name in (".", ".."):
        return None
    root_r = root.resolve()
    d = (root_r / name).resolve()
    return d if d.parent == root_r else None


def strict_ok(rec: dict) -> bool:
    t = rec["title"].lower()
    if not any(s in t for s in AMV_SIG):
        return False
    if any(b in t for b in BAD):
        return False
    name = rec["query"].split()[0].lower()
    return bool(name) and name in t


def probe(path: Path) -> dict:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,codec_name",
         "-show_entries", "format=duration,size",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout)
    except Exception:
        return {}
    st = (d.get("streams") or [{}])[0]
    fmt = d.get("format", {})
    try:
        num, den = st.get("r_frame_rate", "0/1").split("/")
        fps = round(float(num) / float(den), 2) if float(den) else 0
    except Exception:
        fps = 0
    return {"width": st.get("width"), "height": st.get("height"), "fps": fps,
            "vcodec": st.get("codec_name"),
            "duration": round(float(fmt.get("duration", 0) or 0), 2),
            "size_mb": round(float(fmt.get("size", 0) or 0) / 1e6, 1)}


def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def download(rec: dict, attempt: int = 0) -> Path | None:
    platform, ident, title = rec["platform"], rec["id"], rec["title"]
    if platform == "bilibili":
        if not BV_RE.match(ident):
            print(f"    [非法 id] {ident!r}")
            return None
        url, tag = f"https://www.bilibili.com/video/{ident}", ident
    else:
        if not CID_RE.match(ident):
            print(f"    [非法 cid] {ident!r}")
            return None
        url, tag = f"https://www.acfun.cn/v/ac{ident}", f"ac{ident}"

    name = f"{sanitize(title)} [{tag}].mp4"
    target = dest_for(REF_DIR, name)
    if target is None:
        print(f"    [路径越界] {tag}")
        return None
    if target.exists() and target.stat().st_size > 200_000:
        return target

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--user-agent", UA,
        "--add-header", "Referer:https://www.bilibili.com",
        "-f", "bv[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "-o", str(REF_DIR / (name[:-4] + ".%(ext)s")),
        "--no-playlist",
        "--socket-timeout", "30",
        "--retries", "3",
        "--fragment-retries", "5",
        "--sleep-requests", "1.5",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print(f"    [超时] {tag}")
        return None
    if target.exists() and target.stat().st_size > 200_000:
        return target
    err = r.stderr or ""
    if ("412" in err or "429" in err) and attempt < 2:
        wait = 25 * (attempt + 1)
        print(f"    [限流] 退避 {wait}s 重试 ({attempt + 1}/2)", flush=True)
        time.sleep(wait)
        return download(rec, attempt + 1)
    print(f"    [失败] {tag}: {err[-160:].replace(chr(10), ' ')}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=25, help="本轮下载数量目标")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CAND.exists():
        print(f"候选池不存在: {CAND}")
        return 1
    data = json.loads(CAND.read_text(encoding="utf-8"))
    have = set()
    for f in REF_DIR.glob("*.mp4"):
        m = re.search(r"\[(BV[0-9A-Za-z]{10}|ac\d+)\]", f.name)
        if m:
            have.add(m.group(1))
    todo = [c for c in data["candidates"]
            if strict_ok(c) and c["key"] not in have]
    # 类别优先级：大师运镜 > 赛事 > 权威 > 国内创作者；同类按播放量降序
    order = {"master_lens": 0, "contest": 1, "authority": 2, "creator_cn": 3}
    todo.sort(key=lambda c: (order.get(c["category"], 9), -c["views"]))
    todo = todo[:args.target]
    print(f"严格闸门通过 {sum(1 for c in data['candidates'] if strict_ok(c))} 条 | "
          f"已在盘排除 | 本轮下载 {len(todo)}")
    for i, c in enumerate(todo, 1):
        print(f"  {i:>3}. [{c['category']:<11}] {c['views']:>8} {c['platform'][:3]} "
              f"{c['title'][:50]}")
    if args.dry_run:
        return 0

    manifest = []
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            manifest = []

    ok = fail = 0
    for i, c in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {c['title'][:52]}", flush=True)
        p = download(c)
        if p is None:
            fail += 1
            continue
        rec = {"bv": c["key"] if c["platform"] == "bilibili" else c["key"],
               "cid": c["id"] if c["platform"] == "acfun" else None,
               "title": c["title"], "tier": c["category"],
               "views": c["views"], "file": p.name, "platform": c["platform"],
               "source": "master_search", "sha256_16": sha16(p), **probe(p)}
        manifest.append(rec)
        ok += 1
        print(f"    ✓ {p.name[:56]} | {rec.get('duration')}s "
              f"{rec.get('width')}x{rec.get('height')} {rec.get('size_mb')}MB")
        MANIFEST.write_text(json.dumps({
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_items": len(manifest), "items": manifest,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.5)

    print(f"\n本轮成功 {ok} / 失败 {fail} | 参照集总计 "
          f"{len(list(REF_DIR.glob('*.mp4')))} 部")
    return 0


if __name__ == "__main__":
    sys.exit(main())
