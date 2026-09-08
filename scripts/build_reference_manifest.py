# -*- coding: utf-8 -*-
"""build_reference_manifest.py — 参照集清单构建与分层统计（2026-09-08）

扫描 data/reference_top/*.mp4，逐个 ffprobe 提取时长/分辨率/帧率/码率，
按来源分层统计，输出：
  - data/reference_top/_manifest.json   （完整逐部清单，含 SHA-256 短码）
  - data/reference_top/README.md        （人类可读清单表，替代手工维护）

用法: python scripts/build_reference_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
REF_DIR = PROJ / "data" / "reference_top"
CAND = REF_DIR / "_candidates.json"
MANIFEST = REF_DIR / "_manifest.json"
README = REF_DIR / "README.md"
FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"
BV_RE = re.compile(r"(BV[0-9A-Za-z]{10})")


def probe(path: Path) -> dict:
    r = subprocess.run(
        [FFPROBE, "-v", "error",
         "-show_entries", "stream=width,height,r_frame_rate,codec_name,bit_rate",
         "-show_entries", "format=duration,size,bit_rate",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60)
    try:
        d = json.loads(r.stdout)
    except Exception:
        return {}
    streams = d.get("streams") or [{}]
    v = next((s for s in streams if s.get("width")), streams[0])
    fmt = d.get("format", {})
    try:
        num, den = (v.get("r_frame_rate") or "0/1").split("/")
        fps = round(float(num) / float(den), 2) if float(den) else 0
    except Exception:
        fps = 0
    dur = float(fmt.get("duration", 0) or 0)
    size = float(fmt.get("size", 0) or 0)
    return {
        "width": v.get("width"), "height": v.get("height"), "fps": fps,
        "vcodec": v.get("codec_name"),
        "duration": round(dur, 1),
        "size_mb": round(size / 1e6, 1),
        "kbps": round(size * 8 / dur / 1000) if dur else 0,
    }


def sha16(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main() -> int:
    # 候选池的 tier/views 用于回填元数据
    meta_by_bv: dict[str, dict] = {}
    if CAND.exists():
        try:
            for c in json.loads(CAND.read_text(encoding="utf-8"))["candidates"]:
                meta_by_bv[c["bv"]] = c
        except Exception:
            pass
    # yt-dlp 通道的 manifest 也回填
    old_items = []
    if MANIFEST.exists():
        try:
            old_items = json.loads(MANIFEST.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            pass
    for it in old_items:
        meta_by_bv.setdefault(it["bv"], it)

    items = []
    for f in sorted(REF_DIR.glob("*.mp4")):
        m = BV_RE.search(f.name)
        bv = m.group(1) if m else ""
        cand = meta_by_bv.get(bv, {})
        info = probe(f)
        title = re.sub(r"\s*\[BV[0-9A-Za-z]{10}\]$", "", f.stem).strip()
        items.append({
            "bv": bv,
            "title": title,
            "tier": cand.get("tier", "seed"),
            "views": cand.get("views"),
            "file": f.name,
            "sha256_16": sha16(f),
            **info,
        })

    MANIFEST.write_text(json.dumps({
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_items": len(items),
        "tiers": dict(Counter(i["tier"] for i in items)),
        "items": items,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # 分层统计
    res = Counter(f"{i['width']}x{i['height']}" for i in items)
    fps_band = Counter("≤30fps" if i["fps"] <= 30.5 else ">30fps" for i in items)
    durs = [i["duration"] for i in items if i["duration"]]
    kbps = [i["kbps"] for i in items if i["kbps"]]
    tiers = Counter(i["tier"] for i in items)
    total_gb = sum(i["size_mb"] or 0 for i in items) / 1000

    lines = [
        "# 顶尖漫剪参照集 (data/reference_top)",
        "",
        "个人对标学习用途，仅本地分析、不商用、不外发。",
        f"下载工具: yt-dlp + ffmpeg（2026-09-08 扩充至 {len(items)} 部）。",
        "",
        "## 采集口径",
        "",
        "- 来源：B站（`yt-dlp bilisearch` 多组关键词，29 组检索词建候选池）",
        "- 筛选：标题须命中 AMV/MAD 域信号；排除教程/素材包/短片；播放量下限 2,000",
        "- 分层：燃向 burn / 叙事 narrative / 技术流 technique / 顶尖创作者 creator",
        "- 下载：完整视频，`bv[height<=1080]+ba` 优先 1080p（大师级不靠高码率）",
        "",
        f"## 规模（{len(items)} 部 / {total_gb:.1f} GB）",
        "",
        f"- 分层分布：{', '.join(f'{k} {v}' for k, v in sorted(tiers.items(), key=lambda x: -x[1]))}",
        f"- 分辨率：{', '.join(f'{k} × {v}' for k, v in sorted(res.items(), key=lambda x: -x[1]))}",
        f"- 帧率：{', '.join(f'{k} × {v}' for k, v in fps_band.items())}",
        f"- 时长：{min(durs):.0f}s ~ {max(durs):.0f}s（中位 {sorted(durs)[len(durs)//2]:.0f}s）"
        if durs else "- 时长：n/a",
        f"- 码率：{min(kbps)} ~ {max(kbps)} kbps（中位 {sorted(kbps)[len(kbps)//2]} kbps）"
        if kbps else "- 码率：n/a",
        "",
        "## 清单",
        "",
        "| # | 标题 | 分层 | 时长 | 分辨率 | 帧率 | 大小 | BV |",
        "|---|------|------|------|--------|------|------|-----|",
    ]
    for i, it in enumerate(sorted(items, key=lambda x: -(x["views"] or 0)), 1):
        t = it["title"][:42].replace("|", "｜")
        lines.append(
            f"| {i} | {t} | {it['tier']} | {it['duration']:.0f}s | "
            f"{it['width']}x{it['height']} | {it['fps']:g} | {it['size_mb']:.1f}MB | "
            f"[{it['bv']}](https://www.bilibili.com/video/{it['bv']}) |")

    lines += [
        "",
        "## 复现",
        "",
        "```bash",
        "# 1. 建候选池（B站检索，只取元数据）",
        "python scripts/collect_reference_candidates.py --per-query 20",
        "# 2. 下载（分层抽样，含 412 风控退避重试）",
        "python scripts/download_reference_set.py --target 60 --min-views 3000",
        "# 3. 重建清单与本表",
        "python scripts/build_reference_manifest.py",
        "```",
        "",
        "## 已知限制",
        "",
        "- 全部来自 B站单一平台（YouTube 无代理不可达），平台分布未覆盖。",
        "- 播放量为下载时快照，非持续追踪。",
        "- 单风格域偏重燃向踩点（占多数），叙事/技术流样本较少，分层统计时需注意功效。",
        "- 逐部指标（beat_hit_rate / cut_visibility 等）由 `scripts/score_reference_gap.py` 计算。",
        "",
    ]
    README.write_text("\n".join(lines), encoding="utf-8")

    print(f"清单已生成: {MANIFEST}")
    print(f"README 已生成: {README}")
    print(f"共 {len(items)} 部 / {total_gb:.1f} GB")
    print(f"分层: {dict(tiers)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
