# -*- coding: utf-8 -*-
"""download_reference_set.py — 参照集批量下载（B站，2026-09-08）

从 collect_reference_candidates.py 产出的候选池中，按分层抽样挑选目标数量，
下载完整视频到 data/reference_top/，并输出 manifest（含实际时长/分辨率/大小/SHA 短码）。

关键实测约束（2026-09-08）：
  - B站 412 反爬在"带 cookie + 桌面 UA"组合下最易触发；不带 cookie 用 yt-dlp 默认 UA 可正常取流。
  - 画质选 bv[height<=1080]，与参照集现有口径一致（大师级不靠高码率）。
  - 文件名沿用现有惯例：<标题> [<BV>].mp4

用法:
  python scripts/download_reference_set.py --target 55 [--dry-run]
  python scripts/download_reference_set.py --target 55 --only-tier burn narrative
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
CAND = REF_DIR / "_candidates.json"
MANIFEST = REF_DIR / "_manifest.json"

FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"


def sanitize(title: str) -> str:
    """文件名安全化：去路径分隔与非法字符，保留中文与常见符号。"""
    t = re.sub(r'[<>:"/\\|?*\n\r\t]', " ", title)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:120]


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
    fr = st.get("r_frame_rate", "0/1")
    try:
        num, den = fr.split("/")
        fps = round(float(num) / float(den), 2) if float(den) else 0
    except Exception:
        fps = 0
    return {
        "width": st.get("width"),
        "height": st.get("height"),
        "fps": fps,
        "vcodec": st.get("codec_name"),
        "duration": round(float(fmt.get("duration", 0) or 0), 2),
        "size_mb": round(float(fmt.get("size", 0) or 0) / 1e6, 1),
    }


def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")


def download(bv: str, title: str, attempt: int = 0) -> Path | None:
    """下载单个视频，返回实际文件路径。

    412 反爬规避（2026-09-08 实测）：必须同时带桌面 UA + Referer，
    否则网页抓取返回 412；带 cookie 反而更易触发。命中 412 时指数退避重试。
    """
    url = f"https://www.bilibili.com/video/{bv}"
    out_tpl = str(REF_DIR / f"{sanitize(title)} [{bv}].%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-warnings",
        "--user-agent", UA,
        "--add-header", "Referer:https://www.bilibili.com",
        "-f", "bv[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "-o", out_tpl,
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
        print(f"    [超时] {bv}")
        return None
    target = REF_DIR / f"{sanitize(title)} [{bv}].mp4"
    if target.exists() and target.stat().st_size > 200_000:
        return target
    hits = list(REF_DIR.glob(f"*[{bv}].mp4")) + list(REF_DIR.glob(f"*{bv}*.mp4"))
    if hits:
        return hits[0]
    err = (r.stderr or "")
    if "412" in err and attempt < 3:
        backoff = 30 * (attempt + 1)
        print(f"    [412 风控] 退避 {backoff}s 后重试 ({attempt + 1}/3) ...", flush=True)
        time.sleep(backoff)
        return download(bv, title, attempt + 1)
    tail = err[-220:].replace("\n", " ")
    print(f"    [失败] {bv}: {tail}")
    return None


def is_amv(title: str) -> bool:
    """相关性闸门：参照集必须是 AMV/MAD 作品，排除素材包、教程、非剪辑内容。"""
    t = title.lower()
    # 必须命中 AMV 域核心信号（"mv"/"剪辑"过宽，不作独立信号）
    signals = ["amv", "mad", "混剪", "踩点", "卡点", "漫剪", "手书", "静止",
               "高燃", "燃向", "叙事向", "催泪"]
    if not any(s in t for s in signals):
        return False
    # 排除：素材包 / 教程 / 非作品内容
    bad = ["素材", "无水印", "教程", "必学", "吃透", "连招", "教学", "入门",
           "怎么", "如何", "课程", "软件", "插件", "模板下载", "合集下载",
           "情绪短片", "自制短片", "文案", "语录", "壁纸", "剪辑手法", "学习",
           "教会你", "心法", "完整版", "初阶", "基础", "小白", "干货"]
    return not any(b in t for b in bad)


def pick(cands: list[dict], target: int, existing: int, tiers: list[str],
         min_views: int = 10_000, exclude: set[str] | None = None) -> list[dict]:
    """分层抽样：每层按播放量降序轮转取片，保证风格分布不偏。

    min_views 下限对应报告定位的"B站头部 AMV"——播放量过低的不具备对标价值。
    exclude 为已在盘/已入 manifest 的 BV，必须排除，否则每轮都重复选中同一批。
    """
    exclude = exclude or set()
    pools = {}
    for c in cands:
        if tiers and c["tier"] not in tiers:
            continue
        if c["views"] < min_views:
            continue
        if c["bv"] in exclude:
            continue
        if not is_amv(c["title"]):
            continue
        pools.setdefault(c["tier"], []).append(c)
    for k in pools:
        pools[k].sort(key=lambda x: -x["views"])

    need = max(0, target - existing)
    # 配额：burn 45% / narrative 25% / creator 20% / technique 10%
    weights = {"burn": 0.45, "narrative": 0.25, "creator": 0.20,
               "technique": 0.10, "general": 0.0}
    quota = {}
    for t, w in weights.items():
        if t in pools:
            quota[t] = max(1, round(need * w)) if w else 0
    # 配额不足时由 burn 兜底
    if sum(quota.values()) < need and "burn" in pools:
        quota["burn"] = quota.get("burn", 0) + (need - sum(quota.values()))

    out, idx = [], {t: 0 for t in pools}
    while len(out) < need:
        progressed = False
        for t in sorted(quota, key=lambda x: -quota[x]):
            if quota[t] <= 0:
                continue
            if idx.get(t, 0) < len(pools.get(t, [])):
                out.append(pools[t][idx[t]])
                idx[t] += 1
                quota[t] -= 1
                progressed = True
                if len(out) >= need:
                    break
        if not progressed:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=55, help="参照集目标总数")
    ap.add_argument("--min-views", type=int, default=10_000,
                    help="播放量下限（头部 AMV 定位）")
    ap.add_argument("--only-tier", nargs="*", default=[],
                    help="只从这些层抽样（默认全部）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CAND.exists():
        print(f"候选池不存在: {CAND}\n先跑 scripts/collect_reference_candidates.py")
        return 1
    data = json.loads(CAND.read_text(encoding="utf-8"))
    existing_files = sorted(REF_DIR.glob("*.mp4"))
    existing = len(existing_files)
    print(f"现有参照集: {existing} 部 | 候选池: {data['n_candidates']} 条 | 目标: {args.target}")

    manifest = []
    if MANIFEST.exists():
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            manifest = []
    # 排除已入 manifest 的 + 已在盘的（manifest 与磁盘可能不同步）
    done_bv = {m["bv"] for m in manifest}
    for f in existing_files:
        m = re.search(r"(BV[0-9A-Za-z]{10})", f.name)
        if m:
            done_bv.add(m.group(1))

    todo = pick(data["candidates"], args.target, existing, args.only_tier,
                min_views=args.min_views, exclude=done_bv)
    print(f"本轮计划下载: {len(todo)} 部")
    for i, c in enumerate(todo, 1):
        print(f"  {i:>3}. [{c['tier']:<9}] {c['views']:>8} 播放 {c['duration']:>5.0f}s "
              f"{c['bv']} {c['title'][:46]}")
    if args.dry_run:
        return 0

    ok = fail = 0
    for i, c in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {c['title'][:50]} ({c['bv']})", flush=True)
        p = download(c["bv"], c["title"])
        if p is None:
            fail += 1
            continue
        info = probe(p)
        rec = {
            "bv": c["bv"], "title": c["title"], "tier": c["tier"],
            "views": c["views"], "file": p.name,
            "sha256_16": sha16(p), **info,
        }
        manifest.append(rec)
        done_bv.add(c["bv"])
        ok += 1
        print(f"    ✓ {p.name} | {info.get('duration')}s {info.get('width')}x"
              f"{info.get('height')} {info.get('fps')}fps {info.get('size_mb')}MB")
        MANIFEST.write_text(json.dumps({
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_items": len(manifest),
            "items": manifest,
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(3.0)  # 节流：避免连续请求触发 412 风控

    total = len(list(REF_DIR.glob("*.mp4")))
    print(f"\n本轮成功 {ok} / 失败 {fail} | 参照集现有 {total} 部")
    print(f"manifest → {MANIFEST}")
    return 0 if total >= args.target else 2


if __name__ == "__main__":
    sys.exit(main())
