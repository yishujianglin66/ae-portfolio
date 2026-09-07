#!/usr/bin/env python3
"""
人工复核工具包生成器 (Step 4 A3 人工复核)

把 human_review_queue.jsonl 的低置信/复杂镜头做成易复核的:
  review/gifs/{idx:03d}_{shot_id}.gif   逐镜头 GIF 预览 (320px, 5fps)
  review/review.html                    HTML 图库 (全部 GIF + VLM 标签)
  review/review_template.csv            修正模板 (human_direction 列留空待填)

用法:
  py -3.12 scripts/build_review_kit.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")
QUEUE = DATA_ROOT / "human_review_queue.jsonl"
REVIEW_DIR = DATA_ROOT / "review"
GIF_DIR = REVIEW_DIR / "gifs"
FFMPEG = "ffmpeg"

# 可选的正确方向标签 (与 core/camera_vocabulary.py ANNOTATION_LABEL_SCHEMA 一致)
DIRECTION_OPTIONS = ["static", "pan_left", "pan_right", "tilt_up", "tilt_down",
                     "zoom_in", "zoom_out", "push", "zoom_back", "orbit", "complex"]


def make_gif(clip_path: str, out_path: Path, width: int = 320, fps: int = 5) -> bool:
    """ffmpeg 生成小 GIF 预览。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        return True
    cmd = [FFMPEG, "-y", "-i", clip_path,
           "-vf", f"fps={fps},scale={width}:-2:flags=lanczos,split[s0][s1];"
                  f"[s0]palettegen[p];[s1][p]paletteuse",
           "-loop", "0", str(out_path)]
    r = subprocess.run(cmd, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    return r.returncode == 0 and out_path.exists()


def build_html(items: List[Dict[str, Any]]) -> str:
    """生成自包含 HTML 图库 (GIF 网格 + 标签)。"""
    cells = []
    for it in items:
        cells.append(f"""
    <div class="cell">
      <img src="gifs/{it['gif']}" loading="lazy">
      <div class="meta">
        <b>#{it['index']:03d}</b> {it['shot_id']}<br>
        <span class="tag">{it['direction']}</span>
        conf={it['confidence']}<br>
        <span class="anime">{it['anime']} ({it['duration_sec']}s)</span>
      </div>
    </div>""")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>运镜人工复核 ({len(items)} 镜头)</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 16px; background: #111; color: #ddd; }}
h1 {{ font-size: 18px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }}
.cell {{ background: #1c1c1c; border-radius: 8px; padding: 8px; }}
.cell img {{ width: 100%; border-radius: 4px; }}
.meta {{ font-size: 12px; margin-top: 6px; line-height: 1.5; }}
.tag {{ color: #ffd166; font-weight: bold; }}
.anime {{ color: #8ab4f8; }}
</style></head><body>
<h1>运镜人工复核 — {len(items)} 镜头 (VLM 预标注仅供参考, 以肉眼为准)</h1>
<p>修正方式: 填 <code>review_template.csv</code> 的 human_direction 列 (选项: {', '.join(DIRECTION_OPTIONS)})</p>
<div class="grid">{''.join(cells)}
</div></body></html>"""


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not QUEUE.exists():
        print(f"[review] 队列不存在: {QUEUE}")
        return 1
    rows = [json.loads(l) for l in QUEUE.read_text(encoding="utf-8").splitlines() if l.strip()]

    items: List[Dict[str, Any]] = []
    for i, r in enumerate(rows, 1):
        shot_id = r["shot_id"]
        gif = f"{i:03d}_{shot_id}.gif"
        ok = make_gif(r["clip_path"], GIF_DIR / gif)
        if not ok:
            print(f"  GIF 生成失败: {shot_id}")
            continue
        items.append({
            "index": i,
            "shot_id": shot_id,
            "gif": gif,
            "direction": r.get("movement_label", "?"),
            "confidence": r.get("confidence", 0),
            "anime": r.get("anime", ""),
            "duration_sec": r.get("duration_sec", 0),
            "clip": r.get("clip_path", ""),
        })
        print(f"  [{i}/{len(rows)}] {shot_id} -> {gif}")

    # HTML
    (REVIEW_DIR / "review.html").write_text(build_html(items), encoding="utf-8")

    # CSV 模板
    with (REVIEW_DIR / "review_template.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["index", "shot_id", "vlm_direction", "vlm_confidence",
                    "human_direction", "备注"])
        for it in items:
            w.writerow([it["index"], it["shot_id"], it["direction"],
                        it["confidence"], "", ""])

    print(f"\n=== 复核工具包就绪 ===\n  {REVIEW_DIR / 'review.html'}")
    print(f"  {REVIEW_DIR / 'review_template.csv'}")
    print(f"  共 {len(items)} 个 GIF -> {GIF_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
