#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vlm_label_survey.py — 全量 VLM 标注分布速览"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DATA_ROOT = Path(r"D:\AE-Data\AnimeCamera")


def survey(path: Path, name: str) -> None:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    lab = Counter(r.get("movement_label", "?") for r in rows)
    conf = Counter(round(r.get("confidence", 0.0), 2) for r in rows)
    speed = Counter(r.get("speed", "?") for r in rows)
    stab = Counter(r.get("stability", "?") for r in rows)
    dur = [r.get("duration_sec", 0.0) for r in rows]
    print(f"\n===== {name} (n={len(rows)}) =====")
    print("movement_label:", dict(sorted(lab.items(), key=lambda kv: -kv[1])))
    print("confidence:", dict(sorted(conf.items())))
    print("speed:", dict(speed), "stability:", dict(stab))
    print(f"duration: min={min(dur):.2f} med={sorted(dur)[len(dur)//2]:.2f} max={max(dur):.2f}")
    # 高置信子集
    hi = [r for r in rows if r.get("confidence", 0) >= 0.9]
    print(f"conf>=0.9: {len(hi)} -> {dict(Counter(r['movement_label'] for r in hi))}")
    mid = [r for r in rows if 0.7 <= r.get("confidence", 0) < 0.9]
    print(f"conf 0.7-0.9: {len(mid)} -> {dict(Counter(r['movement_label'] for r in mid))}")
    lo = [r for r in rows if r.get("confidence", 0) < 0.7]
    print(f"conf<0.7: {len(lo)} -> {dict(Counter(r['movement_label'] for r in lo))}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    survey(DATA_ROOT / "vlm_labels.jsonl", "vlm_labels")
    survey(DATA_ROOT / "vlm_labels_v2.jsonl", "vlm_labels_v2")
    survey(DATA_ROOT / "vlm_labels_merged.jsonl", "vlm_labels_merged")
