#!/usr/bin/env python3
"""
最终验收盲评集生成: 从合并标签分层抽 100 条 (按方向类均衡),
生成 GIF + HTML + CSV (同 build_review_kit.py 的交互), 供人工打分验收。

用法 (v3 训练完成后):
  py -3.12 scripts/build_blind_review.py
"""
from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
LABELS = DATA_ROOT / "vlm_labels_merged.jsonl"
REVIEW_DIR = DATA_ROOT / "blind_review"
GIF_DIR = REVIEW_DIR / "gifs"
FFMPEG = "ffmpeg"
N_TOTAL = 100


def local_clip(clip: str) -> str:
    """云端路径回落到本地 shots 目录 (合并标签含云端 clip_path)。"""
    p = Path(clip)
    if p.exists():
        return clip
    local = DATA_ROOT / "shots" / p.name
    return str(local) if local.exists() else clip


def make_gif(clip: str, out: Path, width: int = 320, fps: int = 5) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return True
    r = subprocess.run([FFMPEG, "-y", "-i", clip, "-vf",
                        f"fps={fps},scale={width}:-2:flags=lanczos,split[s0][s1];"
                        f"[s0]palettegen[p];[s1][p]paletteuse", "-loop", "0", str(out)],
                       capture_output=True,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode == 0 and out.exists()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not LABELS.exists():
        print("先完成 v3 标签合并")
        return 1
    rows = [json.loads(l) for l in LABELS.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_dir: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if float(r.get("confidence", 0)) >= 0.7 and r.get("movement_label") != "complex":
            by_dir[r["movement_label"]].append(r)

    # 每类按比例抽, 均衡至 N_TOTAL (每类至少 3 条)
    n_classes = len(by_dir)
    per = max(3, N_TOTAL // n_classes)
    random.seed(20260815)
    picked: List[Dict[str, Any]] = []
    for d, items in by_dir.items():
        k = min(per, len(items))
        picked.extend(random.sample(items, k))
    random.shuffle(picked)
    print(f"盲评集: {len(picked)} 条 (覆盖 {n_classes} 个方向类)")

    items = []
    for i, r in enumerate(picked, 1):
        gif = f"{i:03d}_{r['shot_id']}.gif"
        if make_gif(local_clip(r["clip_path"]), GIF_DIR / gif):
            items.append({"index": i, "shot_id": r["shot_id"], "gif": gif,
                          "direction": r["movement_label"],
                          "confidence": r.get("confidence", 0),
                          "anime": r.get("anime", ""),
                          "duration_sec": r.get("duration_sec", 0),
                          "clip": local_clip(r["clip_path"])})
    print(f"GIF 生成: {len(items)}")

    # HTML
    cells = "\n".join(
        f'<div class="cell"><img src="gifs/{it["gif"]}" loading="lazy">'
        f'<div class="meta"><b>#{it["index"]:03d}</b> {it["shot_id"]}<br>'
        f'<span class="tag">{it["direction"]}</span> conf={it["confidence"]}<br>'
        f'<span class="anime">{it["anime"]} ({it["duration_sec"]}s)</span></div></div>'
        for it in items)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>运镜盲评验收 ({len(items)})</title>
<style>body{{font-family:"Microsoft YaHei",sans-serif;margin:16px;background:#111;color:#ddd}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}}
.cell{{background:#1c1c1c;border-radius:8px;padding:8px}}
.cell img{{width:100%;border-radius:4px}}
.meta{{font-size:12px;margin-top:6px;line-height:1.5}}.tag{{color:#ffd166;font-weight:bold}}.anime{{color:#8ab4f8}}
</style></head><body><h1>运镜盲评验收 — {len(items)} 镜头</h1>
<p>修正方式: 填 blind_answers.csv 的 human_direction 列</p>
<div class="grid">{cells}</div></body></html>"""
    (REVIEW_DIR / "blind_review.html").write_text(html, encoding="utf-8")

    with (REVIEW_DIR / "blind_answers.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["index", "shot_id", "vlm_direction", "human_direction"])
        for it in items:
            w.writerow([it["index"], it["shot_id"], it["direction"], ""])
    print(f"输出 -> {REVIEW_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
