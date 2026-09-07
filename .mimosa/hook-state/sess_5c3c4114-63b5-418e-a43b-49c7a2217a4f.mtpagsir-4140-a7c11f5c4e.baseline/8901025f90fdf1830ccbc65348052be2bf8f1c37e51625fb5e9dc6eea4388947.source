# -*- coding: utf-8 -*-
"""v5 静态镜头帧级验证 — 证明"静态镜头真静态"修复生效.

用法:
  python scripts/verify_v5_static.py <v5_script.yaml> <v5.mp4> <v4.mp4> <out_dir>

1) 从 v5 剧本统计: static 占比 / push+zoom_in 撞击镜头 (数量≤6、间隔≥20s、只在
   drop/climax 强拍);
2) 对 3 个静态镜头: 在 v4 与 v5 成片同一时间戳抽帧, 供人工比对
   (v4 同镜头被鼓点推拉覆盖, v5 应为稳定取景);
3) 对撞击镜头抽 onset 前后帧验证 punch 存在.
"""
import json
import subprocess
import sys
from pathlib import Path

import yaml


def ffmpeg_here():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.paths import ffmpeg_bin
    return ffmpeg_bin()


def extract_frame(video: str, t: float, out_png: str, ffmpeg: str) -> bool:
    r = subprocess.run(
        [ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", video,
         "-frames:v", "1", "-q:v", "2", out_png],
        capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and Path(out_png).exists()


def main():
    script_p, v5_p, v4_p, out_dir = sys.argv[1:5]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_here()

    doc = yaml.safe_load(open(script_p, encoding="utf-8"))
    segs = doc["segments"]

    # 1) 静态/撞击统计
    static = [s for s in segs if s.get("zoompan_effect") == "static"]
    punches = [s for s in segs if s.get("zoompan_effect") in ("push", "zoom_in")]
    motion = [s for s in segs if s.get("zoompan_effect") != "static"]
    report = {
        "total": len(segs),
        "static": len(static),
        "static_ratio": round(len(static) / len(segs), 3),
        "motion_types": {},
        "punches": [],
        "punch_spacing_ok": True,
        "punch_section_ok": True,
    }
    for s in motion:
        report["motion_types"][s.get("zoompan_effect")] = \
            report["motion_types"].get(s.get("zoompan_effect"), 0) + 1
    last_punch = None
    for s in punches:
        report["punches"].append({
            "start": s["start_time"], "mood": s["mood"],
            "onsets": len(s.get("onset_times") or []),
        })
        if s["mood"] not in ("drop", "climax"):
            report["punch_section_ok"] = False
        if last_punch is not None and s["start_time"] - last_punch < 20.0:
            report["punch_spacing_ok"] = False
        last_punch = s["start_time"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    (out_dir / "v5_static_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) 静态镜头同时间戳抽帧比对 (v4 vs v5)
    static_sel = [s for s in static if s["duration"] > 0.8][:3]
    for i, s in enumerate(static_sel):
        t0, dur = s["start_time"], s["duration"]
        for j, frac in enumerate((0.15, 0.5, 0.85)):
            t = t0 + dur * frac
            extract_frame(v5_p, t, str(out_dir / f"v5_static{i}_f{j}_t{t:.2f}.png"), ffmpeg)
            extract_frame(v4_p, t, str(out_dir / f"v4_static{i}_f{j}_t{t:.2f}.png"), ffmpeg)

    # 3) 撞击镜头 onset 前后帧
    for i, s in enumerate(punches[:2]):
        ons = s.get("onset_times") or []
        if not ons:
            continue
        t_on = s["start_time"] + ons[0]
        for j, dt in enumerate((-0.12, 0.0, 0.25)):
            extract_frame(v5_p, max(0, t_on + dt),
                          str(out_dir / f"v5_punch{i}_j{j}.png"), ffmpeg)

    print(f"抽帧完成 → {out_dir}")


if __name__ == "__main__":
    main()
