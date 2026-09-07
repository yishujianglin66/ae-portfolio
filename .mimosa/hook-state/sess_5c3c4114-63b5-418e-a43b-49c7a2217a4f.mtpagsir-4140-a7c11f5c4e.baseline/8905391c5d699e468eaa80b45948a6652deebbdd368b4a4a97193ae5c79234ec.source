# -*- coding: utf-8 -*-
"""v5 静态镜头定量验证 — 鼓点前后帧差 MAD 对比 (v4 vs v5).

原理: v4 中 static 镜头被 onset punch 覆盖 → 每个鼓点附近发生 3 帧内
1.0→1.25 的全局缩放 → 鼓点前后两帧 MAD 大; v5 修复后 static 无缩放,
鼓点前后帧差仅来自素材内容本身 → MAD 显著下降。

用法:
  python scripts/verify_v5_static_metric.py <v5_script.yaml> <v4.mp4> <v5.mp4> <out_dir>
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml

TARGET_SIZE = (480, 270)


def ffmpeg_here():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import ffmpeg_bin
    return ffmpeg_bin()


def extract(video, t, out_png, ffmpeg):
    subprocess.run(
        [ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
         "-vf", f"scale={TARGET_SIZE[0]}:{TARGET_SIZE[1]}", out_png],
        capture_output=True, text=True, timeout=60, check=False)
    return Path(out_png).exists()


def luma_mad(png_a, png_b):
    from PIL import Image
    a = Image.open(png_a).convert("L")
    b = Image.open(png_b).convert("L")
    pa, pb = a.load(), b.load()
    w, h = a.size
    total = 0.0
    for y in range(h):
        for x in range(w):
            total += abs(pa[x, y] - pb[x, y])
    return total / (w * h * 255.0)


def main():
    script_p, v4_p, v5_p, out_dir = sys.argv[1:5]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_here()
    segs = yaml.safe_load(open(script_p, encoding="utf-8"))["segments"]

    # 选 10 个带 onset 的静态镜头, 覆盖不同素材
    statics = [s for s in segs
               if s.get("zoompan_effect") == "static"
               and s.get("onset_times") and s["duration"] > 0.6]
    statics = sorted(statics, key=lambda s: s["start_time"])
    step = max(1, len(statics) // 10)
    picks = statics[::step][:10]

    rows = []
    for i, s in enumerate(picks):
        t_on = s["start_time"] + min(s["onset_times"])
        t_a = max(0.0, t_on - 0.06)
        t_b = t_on + 0.08
        pa, pb = {}, {}
        for tag, video in (("v4", v4_p), ("v5", v5_p)):
            a = out_dir / f"m_{i}_{tag}_a.png"
            b = out_dir / f"m_{i}_{tag}_b.png"
            if extract(video, t_a, a, ffmpeg) and extract(video, t_b, b, ffmpeg):
                pa[tag], pb[tag] = a, b
        if len(pa) == 2:
            rows.append({
                "seg_start": round(s["start_time"], 2),
                "source": Path(s["source_file"]).name[:12],
                "t_onset": round(t_on, 2),
                "mad_v4": round(luma_mad(pa["v4"], pb["v4"]), 4),
                "mad_v5": round(luma_mad(pa["v5"], pb["v5"]), 4),
            })

    med4 = sorted(r["mad_v4"] for r in rows)[len(rows) // 2] if rows else 0
    med5 = sorted(r["mad_v5"] for r in rows)[len(rows) // 2] if rows else 0
    verdict = "PASS" if med5 < med4 * 0.6 else "FAIL"
    result = {"rows": rows, "median_mad_v4": round(med4, 4),
              "median_mad_v5": round(med5, 4),
              "drop_ratio": round(med5 / max(med4, 1e-6), 3), "verdict": verdict}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    (out_dir / "v5_mad_compare.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
