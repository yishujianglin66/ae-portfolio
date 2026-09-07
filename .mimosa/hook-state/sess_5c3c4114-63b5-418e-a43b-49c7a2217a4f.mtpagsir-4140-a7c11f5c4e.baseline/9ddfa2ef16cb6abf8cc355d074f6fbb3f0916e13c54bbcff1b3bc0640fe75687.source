# -*- coding: utf-8 -*-
"""成品质量评估 — 多维整合 (技术指标 + 导演报告指标)

用法:
    python scripts/assess_product.py <成片.mp4> [production_report.json]
输出: 终端表格 + JSON (可选 --out)

维度:
  1. 技术指标 (ffprobe): 时长/分辨率/帧率/码率/音频
  2. 导演报告: 运镜种类数/转场分布/反默认违规/自进化 quality/叙事一致性
  3. 优良成品判定 (粗标准):
     - 时长 >= 60s (完整片段) 或 15-25s (高潮片段, 二选一)
     - 帧率 >= 48fps (补帧增强) 或 24fps 原始
     - 运镜种类 >= 5 (多样性)
     - 反默认违规 = 0
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def ffprobe_metrics(path: str) -> dict:
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return {"error": r.stderr[:200]}
    info = json.loads(r.stdout)
    fmt = info.get("format", {})
    v = next((s for s in info.get("streams", [])
              if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", [])
              if s.get("codec_type") == "audio"), None)
    fps_str = v.get("r_frame_rate", "0/1")
    num, den = fps_str.split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    size_mb = float(fmt.get("size", 0)) / 1024 / 1024
    dur = float(fmt.get("duration", 0))
    bitrate = size_mb * 8 * 1024 / dur if dur > 0 else 0  # kbps
    return {
        "duration_sec": round(dur, 1),
        "resolution": f"{v.get('width')}x{v.get('height')}",
        "fps": round(fps, 2),
        "bitrate_kbps": round(bitrate, 0),
        "size_mb": round(size_mb, 1),
        "has_audio": a is not None,
        "codec": v.get("codec_name", ""),
    }


def director_metrics(report_path: str) -> dict:
    if not report_path or not Path(report_path).exists() \
            or not Path(report_path).is_file():
        return {}
    rep = json.loads(Path(report_path).read_text(encoding="utf-8"))
    segs = rep.get("script", {}).get("segments", []) or []
    tp = rep.get("taste_profile", {})
    cams = Counter(s["zoompan_effect"] for s in segs if s.get("zoompan_effect"))
    trans = Counter(s["transition"] for s in segs if s.get("transition"))
    return {
        "n_segments": len(segs),
        "n_camera_types": len(cams),
        "camera_dist": dict(cams),
        "transition_dist": dict(trans),
        "violations": len(tp.get("anti_default_violations", [])),
        "taste": (tp.get("visual_variance"), tp.get("motion_intensity"),
                  tp.get("information_density")),
        "quality": rep.get("quality"),
    }


def verdict(tech: dict, director: dict) -> dict:
    checks = []
    d = tech.get("duration_sec", 0)
    checks.append(("时长达标 (>=15s)", d >= 15))
    checks.append(("补帧增强 (>=48fps)", tech.get("fps", 0) >= 48))
    checks.append(("运镜多样 (>=5类)", director.get("n_camera_types", 0) >= 5))
    checks.append(("反默认违规=0", director.get("violations", -1) == 0))
    checks.append(("含音频", tech.get("has_audio", False)))
    passed = sum(1 for _, ok in checks if ok)
    return {"checks": [{"name": n, "ok": ok} for n, ok in checks],
            "score": f"{passed}/{len(checks)}",
            "excellent": passed >= 4}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("report", nargs="?", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    tech = ffprobe_metrics(args.video)
    director = director_metrics(args.report)
    v = verdict(tech, director)
    result = {"video": args.video, "tech": tech,
              "director": director, "verdict": v}

    print(f"== 成品评估: {Path(args.video).name} ==")
    if "error" in tech:
        print("  ffprobe 失败:", tech["error"])
        return 1
    print(f"  技术: {tech['duration_sec']}s | {tech['resolution']} | "
          f"{tech['fps']}fps | {tech['bitrate_kbps']}kbps | "
          f"{tech['size_mb']}MB | 音频={tech['has_audio']} | {tech['codec']}")
    if director:
        print(f"  导演: {director['n_segments']} 段 | 运镜 {director['n_camera_types']} 类 | "
              f"违规 {director['violations']} | taste {director['taste']}")
        print(f"  转场: {director['transition_dist']}")
    print(f"  判定: {v['score']} {'✅ 优良' if v['excellent'] else '❌ 未达标'}")
    for c in v["checks"]:
        print(f"    {'✅' if c['ok'] else '❌'} {c['name']}")

    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False,
                                             indent=2), encoding="utf-8")
        print(f"  -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
