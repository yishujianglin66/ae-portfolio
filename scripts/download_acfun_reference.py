# -*- coding: utf-8 -*-
"""download_acfun_reference.py — AcFun 参照集下载（2026-09-08）

把 AcFun 候选（含 AKROSS Con 国际赛事作品）下载进参照集，文件名沿用
`<标题> [ac<contentId>].mp4` 以便与 B站 的 `[BVxxxx]` 区分。

优先级：contest（国际赛事）> amv > mad；同层按播放量降序。

安全约束：下载 URL 由已校验的 contentId 构造（必须为纯数字），
主机固定为白名单 www.acfun.cn；文件名仅接受安全字符，写入前确认落在 REF_DIR 内。

用法: python scripts/download_acfun_reference.py --target 15 [--dry-run]
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
CAND = REF_DIR / "_candidates_acfun.json"
MANIFEST = REF_DIR / "_manifest.json"
FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"

API_HOST = "www.acfun.cn"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
CID_RE = re.compile(r"^\d{4,12}$")
SAFE_CHARS = re.compile(r"[^\w\u4e00-\u9fff \-\[\]\(\)（）「」·~!！？?、。，,.]+")


def sanitize(title: str) -> str:
    t = SAFE_CHARS.sub(" ", title)
    t = re.sub(r"\s+", " ", t).strip()[:100]
    return t or "untitled"


def dest_for(root: Path, name: str) -> Path | None:
    """在 root 内构造目标路径；只接受纯文件名，禁止分隔符。

    不用 `".." in name` 判定穿越——标题中的省略号 `......` 会误伤；
    Path(name).name == name 已能保证无目录成分，再由 resolve 后 parent 复核。
    """
    if not name or Path(name).name != name:
        return None
    if name in (".", ".."):
        return None
    root_r = root.resolve()
    d = (root_r / name).resolve()
    return d if d.parent == root_r else None


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


def download(cid: str, title: str, attempt: int = 0) -> Path | None:
    if not CID_RE.match(cid):
        print(f"    [非法 cid] {cid!r}")
        return None
    name = f"{sanitize(title)} [ac{cid}].mp4"
    target = dest_for(REF_DIR, name)
    if target is None:
        print(f"    [路径越界] {cid}")
        return None
    if target.exists() and target.stat().st_size > 200_000:
        return target
    url = f"https://{API_HOST}/v/ac{cid}"
    out_tpl = str(REF_DIR / (name[:-4] + ".%(ext)s"))
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--user-agent", UA,
        "-f", "bv+ba/b",
        "--merge-output-format", "mp4",
        "-o", out_tpl,
        "--no-playlist",
        "--socket-timeout", "30",
        "--retries", "3",
        "--fragment-retries", "5",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                           encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        print(f"    [超时] {cid}")
        return None
    if target.exists() and target.stat().st_size > 200_000:
        return target
    err = r.stderr or ""
    if ("412" in err or "429" in err) and attempt < 2:
        wait = 20 * (attempt + 1)
        print(f"    [限流] 退避 {wait}s 重试 ({attempt + 1}/2)", flush=True)
        time.sleep(wait)
        return download(cid, title, attempt + 1)
    print(f"    [失败] {cid}: {err[-180:].replace(chr(10), ' ')}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=15, help="AcFun 新增数量目标")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CAND.exists():
        print(f"候选池不存在: {CAND}\n先跑 scripts/collect_acfun_candidates.py")
        return 1
    data = json.loads(CAND.read_text(encoding="utf-8"))
    have = set()
    for f in REF_DIR.glob("*.mp4"):
        m = re.search(r"\[ac(\d+)\]", f.name)
        if m:
            have.add(m.group(1))
    todo = [c for c in data["candidates"] if c["cid"] not in have]
    order = {"contest": 0, "amv": 1, "mad": 2}
    todo.sort(key=lambda c: (order.get(c["tier"], 9), -c["views"]))
    todo = todo[:args.target]
    print(f"AcFun 候选 {data['n_candidates']} 条 | 已在盘 {len(have)} | 本轮下载 {len(todo)}")
    for i, c in enumerate(todo, 1):
        print(f"  {i:>3}. [{c['tier']:<8}] {c['views']:>8} {c['cid']} {c['title'][:48]}")
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
        print(f"[{i}/{len(todo)}] {c['title'][:50]} (ac{c['cid']})", flush=True)
        p = download(c["cid"], c["title"])
        if p is None:
            fail += 1
            continue
        rec = {"bv": f"ac{c['cid']}", "cid": c["cid"], "title": c["title"],
               "tier": c["tier"], "views": c["views"], "file": p.name,
               "platform": "acfun", "source": "yt-dlp",
               "sha256_16": sha16(p), **probe(p)}
        manifest.append(rec)
        ok += 1
        print(f"    ✓ {p.name[:56]} | {rec.get('duration')}s "
              f"{rec.get('width')}x{rec.get('height')} {rec.get('fps')}fps "
              f"{rec.get('size_mb')}MB")
        MANIFEST.write_text(json.dumps({
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_items": len(manifest), "items": manifest,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.5)

    print(f"\n本轮成功 {ok} / 失败 {fail} | 参照集总计 {len(list(REF_DIR.glob('*.mp4')))} 部")
    return 0


if __name__ == "__main__":
    sys.exit(main())
