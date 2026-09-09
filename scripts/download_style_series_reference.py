# -*- coding: utf-8 -*-
"""download_style_series_reference.py — 木偶 / 手书系列下载（2026-09-08）

从 _candidates_styles.json 中经**系列专属闸门**筛选后下载。

闸门设计（两系列口径不同）：
  - 手书 handdrawn：标题须含 手书/手書/描改/手绘PV；排除翻唱、直播、教程。
  - 木偶 puppet：只收**二次元角色纸片人/骨骼/Live2D**类；明确排除
    布袋戏/皮影戏/定格黏土/影视道具/真人cosplay——这些不是项目定义的
    「立绘拆分→骨骼绑定→驱动」木偶动画。

安全：写入前路径必须落在 REF_DIR；id 必须匹配格式。

用法: python scripts/download_style_series_reference.py --series handdrawn --target 20 [--dry-run]
      python scripts/download_style_series_reference.py --series puppet --target 15
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
CAND = REF_DIR / "_candidates_styles.json"
MANIFEST = REF_DIR / "_manifest.json"
FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
SAFE_CHARS = re.compile(r"[^\w\u4e00-\u9fff \-\[\]\(\)（）「」『』·~!！？?、。，,.]+")
BV_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")
CID_RE = re.compile(r"^\d{4,12}$")

# 手书：必须命中作品信号
HD_SIG = ["手书", "手書", "描改", "手绘", "手書き", "手繪"]
# 手书排除：非作品 / 非 PV
HD_BAD = ["教程", "教学", "课程", "入门", "直播", "录播", "预告", "翻唱",
          "采访", "访谈", "盘点", "排行", "reaction", "合集", "制作过程",
          "过程记录", "素材", "汉化组", "字幕组", "PV1", "PV2", "PV3",
          "霹雳", "布袋戏", "隔壁小孩", "抽奖", "飙歌"]

# 木偶：必须含明确的**二次元骨骼/纸片驱动**信号
PP_SIG = ["纸片人", "live2d", "骨骼动画", "动态立绘", "mmd动画", "东方mmd",
          "纸片动画", "立绘动画"]
# 木偶排除：布袋戏/皮影/黏土/真人/手工DIY/游戏实机/教程
PP_BAD = ["布袋戏", "霹雳", "皮影", "定格", "黏土", "粘土", "泥塑", "真人",
          "cosplay", "道具", "操偶", "提线", "木偶戏", "崂山道士", "教程",
          "教学", "课程", "直播", "录播", "预告", "翻唱", "游戏实机",
          "解说", "盘点", "排行", "武打", "特效教程", "画师修炼", "弹唱",
          "筷子", "不要扔", "过关", "皮肤", "手工", "隔壁小孩", "三年",
          "跳舞的线", "原创动画", "小动画"]


def sanitize(title: str) -> str:
    t = SAFE_CHARS.sub(" ", title)
    return (re.sub(r"\s+", " ", t).strip()[:100]) or "untitled"


def dest_for(root: Path, name: str) -> Path | None:
    """只接受纯文件名；不用 ".." in name（会误伤标题里的省略号）。"""
    if not name or Path(name).name != name or name in (".", ".."):
        return None
    root_r = root.resolve()
    d = (root_r / name).resolve()
    return d if d.parent == root_r else None


def gate(rec: dict, series: str) -> bool:
    t = rec["title"].lower()
    if series == "handdrawn":
        return any(s in t for s in HD_SIG) and not any(b in t for b in HD_BAD)
    if series == "puppet":
        return any(s in t for s in PP_SIG) and not any(b in t for b in PP_BAD)
    return False


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
            return None
        url, tag = f"https://www.bilibili.com/video/{ident}", ident
    else:
        if not CID_RE.match(ident):
            return None
        url, tag = f"https://www.acfun.cn/v/ac{ident}", f"ac{ident}"

    name = f"{sanitize(title)} [{tag}].mp4"
    target = dest_for(REF_DIR, name)
    if target is None:
        print(f"    [路径越界] {tag}")
        return None
    if target.exists() and target.stat().st_size > 200_000:
        return target

    cmd = [sys.executable, "-m", "yt_dlp", "--no-warnings",
           "--user-agent", UA,
           "--add-header", "Referer:https://www.bilibili.com",
           "-f", "bv[height<=1080]+ba/b[height<=1080]/b",
           "--merge-output-format", "mp4",
           "-o", str(REF_DIR / (name[:-4] + ".%(ext)s")),
           "--no-playlist", "--socket-timeout", "30",
           "--retries", "3", "--fragment-retries", "5",
           "--sleep-requests", "1.5", url]
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
    print(f"    [失败] {tag}: {err[-150:].replace(chr(10), ' ')}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", required=True, choices=["handdrawn", "puppet"])
    ap.add_argument("--target", type=int, default=20)
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

    pool = [c for c in data["candidates"]
            if c["series"] == args.series and c["key"] not in have
            and gate(c, args.series)]
    pool.sort(key=lambda c: -c["views"])
    todo = pool[:args.target]
    print(f"[{args.series}] 候选 {sum(1 for c in data['candidates'] if c['series'] == args.series)} "
          f"| 闸门通过 {len(pool)} | 本轮下载 {len(todo)}")
    for i, c in enumerate(todo, 1):
        print(f"  {i:>3}. {c['views']:>8} {c['duration']:>5.0f}s {c['title'][:54]}")
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
        rec = {"bv": c["key"], "cid": c["id"] if c["platform"] == "acfun" else None,
               "title": c["title"], "tier": args.series, "views": c["views"],
               "file": p.name, "platform": c["platform"],
               "source": "style_search", "sha256_16": sha16(p), **probe(p)}
        manifest.append(rec)
        ok += 1
        print(f"    ✓ {p.name[:56]} | {rec.get('duration')}s "
              f"{rec.get('width')}x{rec.get('height')} {rec.get('size_mb')}MB")
        MANIFEST.write_text(json.dumps({
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_items": len(manifest), "items": manifest,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.5)

    print(f"\n[{args.series}] 成功 {ok} / 失败 {fail} | 参照集总计 "
          f"{len(list(REF_DIR.glob('*.mp4')))} 部")
    return 0


if __name__ == "__main__":
    sys.exit(main())
