# -*- coding: utf-8 -*-
"""scan_material_library.py — 素材库扫描建档 (2026-09-05)

扫描本机素材目录, 产出可当"源素材"用的清单(data/material_manifest.json):
番(distribution) / 文件 / 时长 / 分辨率 / 帧率。用于 #12 素材库扩充 — 把引擎从
7 源扩到多番多源, 缓解"画面同质/静帧"导致的切点软、观感单一。

排除: 成品示例(成品.mp4)、AE教程(数字开头的.mp4)、抖音/MAC/Overlay 等非动漫源、
时长<5s 或横向<640 的残片。两素材根目录若为 junction(同一实体), 用 realpath 去重。

用法: python scripts/scan_material_library.py [--out data/material_manifest.json]
"""
import argparse
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOTS = [
    "D:/AE-Work/resources/video",
    "D:/BaiduNetdiskDownload/AE新手10套",
]
EXTS = {".mp4", ".mov", ".mkv", ".avi", ".flv", ".wmv", ".webm"}
# 文件名命中即排除(成品示例/教程/工具类非动漫源)
EXCLUDE_RE = re.compile(
    r"^(成品|教程|抖音|MAC|Overlay|字幕|封面|文案|片头|片尾|工程|模板)",
    re.IGNORECASE,
)
EXCLUDE_EXACT = {"成品.mp4", "素材.MP4", "素材.mp4"}  # 竖屏"素材"已在子目录单独对待


def probe(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate:format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, timeout=120,
    )
    out = r.stdout.decode("utf-8", "replace").strip().split("\n")
    if len(out) < 2 or not out[0].strip():
        return None
    parts = out[0].split(",")
    try:
        w, h = int(parts[0]), int(parts[1])
        fps = parts[2]
        dur = float(out[1].split("\n")[-1].strip() or 0)
    except (ValueError, IndexError):
        return None
    return {"width": w, "height": h, "fps": fps, "duration": round(dur, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent
                                         / "data" / "material_manifest.json"))
    args = ap.parse_args()

    seen = set()   # realpath 去重(两目录可能 junction 到同一实体)
    records = []
    for root in ROOTS:
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if d not in ("__pycache__", ".git")]
            for f in fn:
                if os.path.splitext(f)[1].lower() not in EXTS:
                    continue
                full = os.path.join(dp, f)
                rp = os.path.realpath(full)
                if rp in seen:
                    continue
                seen.add(rp)
                if EXCLUDE_RE.match(os.path.splitext(f)[0]):
                    continue
                rel = os.path.relpath(dp, root)
                # 根目录顶层的都是 AE 教程(数字编号/含"教程"), 非番源 → 跳过
                if rel == ".":
                    continue
                meta = probe(full)
                if not meta or meta["duration"] < 5 or meta["width"] < 640:
                    continue
                # 番 = 根目录下第一层文件夹名
                franch = rel.split(os.sep)[0]
                records.append({
                    "franchise": franch,
                    "path": full.replace("\\", "/"),
                    "name": f,
                    **meta,
                })

    # 按番聚合
    by_f = defaultdict(list)
    for r in records:
        by_f[r["franchise"]].append(r)

    print(f"可用源素材: {len(records)} 个, 分布 {len(by_f)} 个番/组")
    print(f"{'番':<16}{'源数':>5}{'时长范围':>14}{'分辨率/帧率'}")
    for f, rs in sorted(by_f.items(), key=lambda x: -len(x[1])):
        durs = [r["duration"] for r in rs]
        res = {f'{r["width"]}x{r["height"]}@{r["fps"].split("/")[0]}fps' for r in rs}
        print(f"{f:<16}{len(rs):>5}{min(durs):>7.0f}-{max(durs):>6.0f}s  {' '.join(sorted(res))}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "roots": ROOTS, "total": len(records),
        "materials": records,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())