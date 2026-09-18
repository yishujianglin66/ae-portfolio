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
AC_RE = re.compile(r"\[ac(\d+)\]")


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
    # 候选池的 tier/views 用于回填元数据（B站 / AcFun / 大师名 / 风格系列 四个池）
    meta_by_bv: dict[str, dict] = {}
    for cand_file in (CAND,
                      REF_DIR / "_candidates_acfun.json",
                      REF_DIR / "_candidates_masters.json",
                      REF_DIR / "_candidates_styles.json"):
        if not cand_file.exists():
            continue
        try:
            for c in json.loads(cand_file.read_text(encoding="utf-8"))["candidates"]:
                key = (c.get("bv") or c.get("key")
                       or (f"ac{c['cid']}" if c.get("cid") else ""))
                if not key:
                    continue
                # 统一 tier/series 字段名
                if "category" in c and "tier" not in c:
                    c["tier"] = c["category"]
                if "series" in c:
                    c["tier"] = c["series"]
                meta_by_bv[key] = c
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
        # 支持两种来源标记：B站 [BVxxxxxxxxxx] / AcFun [ac<cid>]
        mb = BV_RE.search(f.name)
        ma = AC_RE.search(f.name)
        if mb:
            key, platform = mb.group(1), "bilibili"
        elif ma:
            key, platform = f"ac{ma.group(1)}", "acfun"
        else:
            key, platform = "", "unknown"
        cand = meta_by_bv.get(key, {})
        info = probe(f)
        title = re.sub(r"\s*\[(BV[0-9A-Za-z]{10}|ac\d+)\]$", "", f.stem).strip()
        # 画质档位：评估时按档筛选，避免老资源拉低对标基线
        h = info.get("height") or 0
        if h >= 1080:
            quality = "hd1080"
        elif h >= 720:
            quality = "hd720"
        elif h >= 480:
            quality = "sd480"
        else:
            quality = "low"
        items.append({
            "bv": key,
            "platform": platform,
            "cid": cand.get("cid"),
            "title": title,
            "tier": cand.get("tier", "seed"),
            "quality": quality,
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
    platforms = Counter(i["platform"] for i in items)
    qualities = Counter(i.get("quality", "unknown") for i in items)
    total_gb = sum(i["size_mb"] or 0 for i in items) / 1000

    lines = [
        "# 顶尖漫剪参照集 (data/reference_top)",
        "",
        "个人对标学习用途，仅本地分析、不商用、不外发。",
        f"下载工具: yt-dlp + ffmpeg（2026-09-08 扩充至 {len(items)} 部）。",
        "",
        "## 采集口径",
        "",
        "- 来源：**B站**（`yt-dlp bilisearch` 29 组关键词）+ **AcFun**（官方搜索 API，含 AKROSS Con 国际赛事作品）",
        "- 筛选：标题须命中 AMV/MAD 域信号；排除教程/素材包/合集/短片；时长 60-400s",
        "- 分层：燃向 burn / 叙事 narrative / 赛事 contest / 顶尖创作者 creator",
        "- 下载：完整视频，优先 1080p（大师级不靠高码率）",
        f"- 平台分布：{', '.join(f'{k} {v}' for k, v in sorted(platforms.items(), key=lambda x: -x[1]))}",
        "",
        f"## 规模（{len(items)} 部 / {total_gb:.1f} GB）",
        "",
        f"- 分层分布：{', '.join(f'{k} {v}' for k, v in sorted(tiers.items(), key=lambda x: -x[1]))}",
        f"- 画质档位：{', '.join(f'{k} {v}' for k, v in sorted(qualities.items(), key=lambda x: -x[1]))}",
        "  （`low`/`sd480` 为老资源，评估时可用 `quality` 字段筛除，避免拉低对标基线）",
        f"- 分辨率：{', '.join(f'{k} × {v}' for k, v in sorted(res.items(), key=lambda x: -x[1]))}",
        f"- 帧率：{', '.join(f'{k} × {v}' for k, v in fps_band.items())}",
        f"- 时长：{min(durs):.0f}s ~ {max(durs):.0f}s（中位 {sorted(durs)[len(durs)//2]:.0f}s）"
        if durs else "- 时长：n/a",
        f"- 码率：{min(kbps)} ~ {max(kbps)} kbps（中位 {sorted(kbps)[len(kbps)//2]} kbps）"
        if kbps else "- 码率：n/a",
        "",
    ]

    # 分位数段落（若 reference_stats.py 已跑过则自动嵌入）
    stats_file = PROJ / "reports" / "reference_stats.json"
    if stats_file.exists():
        try:
            st = json.loads(stats_file.read_text(encoding="utf-8"))
            pct = st.get("percentiles") or {}
            mine_sig = (st.get("mine") or {}).get("signal") or {}
            if pct:
                lines += [
                    f"## 指标分位数（n={st.get('n_refs')}，实测）",
                    "",
                    "由 `scripts/reference_stats.py` 计算，逐部落盘 `reports/reference_stats.json`，",
                    "缓存 `reports/ref_metrics_cache.json`（二次运行秒出）。",
                    "",
                    "| 指标 | 均值 | p25 | p50 | p75 | p90 | min | max |",
                    "|------|------|-----|-----|-----|-----|-----|-----|",
                ]
                for k, s in pct.items():
                    lines.append(
                        f"| {k} | {s['mean']} | {s['p25']} | {s['p50']} | {s['p75']} | "
                        f"{s['p90']} | {s['min']} | {s['max']} |")
                if mine_sig:
                    lines += [
                        "",
                        "**与 run61 最佳候选（master_hr.mp4）对比**：",
                        "",
                        "| 指标 | 本片 | 参照均值 | p75 | 判定 |",
                        "|------|------|---------|-----|------|",
                    ]
                    for k, s in pct.items():
                        mv = mine_sig.get(k)
                        if mv is None:
                            continue
                        if s["better"]:
                            verdict = ("超 p90" if mv > s["p90"] else
                                       "超 p75" if mv > s["p75"] else
                                       "超均值" if mv > s["mean"] else "低于均值")
                        else:
                            verdict = "优于均值" if mv < s["mean"] else "劣于均值"
                        lines.append(f"| {k} | {mv} | {s['mean']} | {s['p75']} | {verdict} |")
                lines += [
                    "",
                    "> **证据说明**：原评估报告引用的「参照前三分位 0.8193」在落盘数据中不存在"
                    "（旧脚本 `score_reference_gap.py` 只算 mean/min/max，未实现分位数）。",
                    f"以上分位数为 n={st.get('n_refs')} 实测值，可直接复核。",
                    "",
                ]
            # 按风格分层（跨风格混算均值会失真）
            by_tier = st.get("by_tier") or {}
            if by_tier:
                lines += [
                    "### 按风格分层（均值，跨风格不可直接混算）",
                    "",
                    "| tier | n | beat_hit_rate | cut_visibility | cut_rate | hf_energy |",
                    "|------|---|--------------|---------------|---------|-----------|",
                ]
                for t, e in sorted(by_tier.items(), key=lambda x: -x[1]["n"]):
                    lines.append(
                        f"| {t} | {e['n']} | {e['beat_hit_rate']} | "
                        f"{e['cut_visibility']} | {e['cut_rate']} | {e['hf_energy']} |")
                lines += [
                    "",
                    "> 木偶（puppet）与手书（handdrawn）的 cut_visibility / cut_rate 天然远低于",
                    "> 燃向漫剪——前者是有限动画/骨骼驱动，切点密度本就稀疏。**对标 run61 这类",
                    "> 燃向踩点片时，应只与 burn / amv / seed 层比较**，勿用全体均值。",
                    "",
                ]
        except Exception as e:
            lines += [f"<!-- 分位数段落生成失败: {e} -->", ""]

    lines += [
        "## 清单",
        "",
        "| # | 标题 | 平台 | 分层 | 画质 | 时长 | 分辨率 | 帧率 | 大小 | 来源 |",
        "|---|------|------|------|------|------|--------|------|------|------|",
    ]
    for i, it in enumerate(sorted(items, key=lambda x: -(x["views"] or 0)), 1):
        t = it["title"][:40].replace("|", "｜")
        if it["platform"] == "bilibili":
            src = f"[{it['bv']}](https://www.bilibili.com/video/{it['bv']})"
        elif it["platform"] == "acfun":
            src = f"[{it['bv']}](https://www.acfun.cn/v/ac{it['cid'] if it.get('cid') else it['bv'][2:]})"
        else:
            src = "—"
        lines.append(
            f"| {i} | {t} | {it['platform']} | {it['tier']} | {it.get('quality', '—')} | "
            f"{it['duration']:.0f}s | "
            f"{it['width']}x{it['height']} | {it['fps']:g} | {it['size_mb']:.1f}MB | "
            f"{src} |")

    lines += [
        "",
        "## 复现",
        "",
        "```bash",
        "# 1a. 建 B站候选池（检索，只取元数据）",
        "python scripts/collect_reference_candidates.py --per-query 20",
        "# 1b. 建 AcFun 候选池（含 AKROSS Con 赛事作品）",
        "python scripts/collect_acfun_candidates.py --per-query 30",
        "# 2a. 下载 B站（分层抽样，含 412 风控退避重试）",
        "python scripts/download_reference_set.py --target 60 --min-views 3000",
        "# 2b. 下载 AcFun（赛事层优先）",
        "python scripts/download_acfun_reference.py --target 20",
        "# 3. 重建清单与本表",
        "python scripts/build_reference_manifest.py",
        "# 4. 逐部指标 + 分位数（并行，带缓存）",
        "python scripts/reference_stats.py --refs data/reference_top \\",
        "    --mine output/unified_run61/polish/master_hr.mp4 --workers 6",
        "```",
        "",
        "## 已知限制",
        "",
        "- 平台覆盖 B站 + AcFun 两家（YouTube/Niconico/Vimeo 无代理不可达，已实测）。",
        "- 播放量为下载时快照，非持续追踪。",
        "- 分层偏重燃向（burn 占比最高）；技术流层为空——B站/AcFun 该关键词域均为教程，",
        "  需改用大师名定向搜索或人工投稿补齐。",
        "- 逐部指标（beat_hit_rate / cut_visibility 等）由 `scripts/reference_stats.py` 计算，",
        "  与旧 `score_reference_gap.py` 同源函数，但后者不输出分位数。",
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
