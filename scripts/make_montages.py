#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_montages.py — 对指定 shot 生成帧序列蒙太奇 PNG, 供人工目检运镜

用法: py -3.12 scripts/make_montages.py <shot_id> [shot_id ...]
输出: analysis_out/montages/<shot_id>.png  (3行x5列, 时间均匀采样15帧)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

REVIEWED = Path(r"D:\AE-Data\AnimeCamera\reviewed_results.jsonl")
OUT_DIR = PROJECT_ROOT / "analysis_out" / "montages"

COLS, ROWS = 5, 3
THUMB_W, THUMB_H = 256, 192
LABEL_H = 24


def montage(video_path: str, out_png: Path, title: str) -> bool:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    n = COLS * ROWS
    idxs = [int(round(i * (total - 1) / (n - 1))) for i in range(n)] if total > 1 else [0] * n
    frames = []
    for i, idx in enumerate(idxs):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        frames.append((i, frame))
    cap.release()
    if not frames:
        return False

    cell_h = THUMB_H + LABEL_H
    canvas = np.full((ROWS * cell_h, COLS * THUMB_W, 3), 30, dtype=np.uint8)
    for i, frame in frames:
        r, c = divmod(i, COLS)
        f = cv2.resize(frame, (THUMB_W, THUMB_H), interpolation=cv2.INTER_AREA)
        canvas[r * cell_h:r * cell_h + THUMB_H, c * THUMB_W:(c + 1) * THUMB_W] = f
        t = idxs[i] / max(total - 1, 1)
        cv2.putText(canvas, f"f{idxs[i]} t={t:.2f}",
                    (c * THUMB_W + 4, r * cell_h + THUMB_H + 17),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, title, (4, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                (255, 255, 255), 1, cv2.LINE_AA)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_png), canvas)
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = {r["shot_id"]: r for r in
            (json.loads(l) for l in REVIEWED.read_text(encoding="utf-8").splitlines() if l.strip())}
    shots = sys.argv[1:]
    if not shots:
        print("用法: py -3.12 scripts/make_montages.py <shot_id> [...]")
        return 1
    ok = 0
    for sid in shots:
        r = rows.get(sid)
        if r is None:
            print(f"未找到 {sid}")
            continue
        segs = r.get("reviewed_per_segment", [])
        seg_str = " | ".join(f"{s['label']}({s['confidence']:.2f})" for s in segs)
        title = (f"{sid}  VLM={r['original_label']}({r['original_confidence']}) -> "
                 f"FLOW={r['reviewed_label']}({r['reviewed_confidence']:.2f})  {seg_str}")
        out = OUT_DIR / f"{sid}.png"
        if montage(r["clip_path"], out, title):
            print(f"OK  {out}")
            ok += 1
        else:
            print(f"FAIL {sid}")
    print(f"完成 {ok} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main())
