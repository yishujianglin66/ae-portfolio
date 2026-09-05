# -*- coding: utf-8 -*-
"""底片闪帧减密 pass (2026-09-05) — 用户反馈: 15s 后连续闪动没跟音乐节奏

检测底片 (run53_lut.mp4) 里引擎烘的冲击帧:
- 白/黑闪: 全画面 luma 突跳 (kick 起始 2帧, 2-of-3 轮换 → 密度 ~2/s = 连续闪动主因)
- RGB 故障: rgbashift 红蓝边缘条纹 (snare 3帧, 半数)
保留规则 = 音乐重音对齐: 距强鼓点 ≤0.12s 且距上一个保留事件 ≥1.6s; 其余抹除
(邻帧线性插值), 让闪动从"每拍都闪"变成"乐句重音 punctuation"。
用法: python scripts/deflash_lut.py <lut.mp4> [--apply]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 160, 90, 24
LUMA_TH = 20.0    # 全画面 luma 突跳阈值 (0-255)
FRINGE_TH = 9.0   # |R-B| 边缘条纹突跳阈值


def _decode(path):
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-vf", f"scale={W}:{H}",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    buf = r.stdout
    n = len(buf) // (W * H * 3)
    return np.frombuffer(buf[:n * W * H * 3], dtype=np.uint8).reshape(n, H, W, 3).astype(np.float32)


def detect(frames):
    lm = frames.mean(axis=(1, 2, 3)) if frames.ndim == 4 else frames.mean(axis=(1, 2))
    rb = np.abs(frames[:, :, :, 0] - frames[:, :, :, 2]).mean(axis=(1, 2))
    n = len(lm)
    flags = np.zeros(n, dtype=bool)   # True=闪帧
    kinds = [""] * n
    for i in range(2, n - 2):
        nb = np.median([lm[i - 2], lm[i - 1], lm[i + 1], lm[i + 2]])
        if abs(lm[i] - nb) > LUMA_TH:
            flags[i] = True
            kinds[i] = "flash"
        nbr = np.median([rb[i - 2], rb[i - 1], rb[i + 1], rb[i + 2]])
        if not flags[i] and abs(rb[i] - nbr) > FRINGE_TH:
            flags[i] = True
            kinds[i] = "glitch"
    # 聚事件 (连续帧)
    events = []
    i = 0
    while i < n:
        if flags[i]:
            j = i
            while j + 1 < n and flags[j + 1] and kinds[j + 1] == kinds[i]:
                j += 1
            events.append({"f0": i, "f1": j, "kind": kinds[i],
                           "t": round(i / FPS, 3)})
            i = j + 1
        else:
            i += 1
    return events


def main():
    lut = Path(sys.argv[1])
    apply = "--apply" in sys.argv
    frames = _decode(lut)
    events = detect(frames)
    strong = json.loads((ROOT / "tmp/music_envelope.json").read_text(encoding="utf-8"))["strong"]

    kept, removed = [], []
    last_kept = -999.0
    for ev in events:
        on_accent = any(abs(ev["t"] - s) <= 0.12 for s in strong)
        spaced = ev["t"] - last_kept >= 1.6
        if on_accent and spaced:
            kept.append(ev)
            last_kept = ev["t"]
        else:
            removed.append(ev)
    print(f"检测到 {len(events)} 个闪动事件 ({len(events)/30:.1f}/s) → "
          f"保留 {len(kept)} (重音对齐) / 抹除 {len(removed)}")
    for ev in kept:
        print(f"  KEEP {ev['kind']:6s} @{ev['t']:6.2f}s ({ev['f0']}-{ev['f1']}帧)")
    print("  REMOVE:", [f"{ev['kind'][:1]}@{ev['t']:.1f}" for ev in removed[:24]])

    if not apply:
        print("(dry-run, 加 --apply 执行抹除)")
        return

    # 抹除: 全分辨率流式 (v2 — 缩略图只做检测, 抹除在原分辨率上做, 修复分辨率丢失 bug)
    # 相邻/相接事件合并成 span, 从 span 外真实帧线性插值
    removed_sorted = sorted(removed, key=lambda e: e["f0"])
    spans = []
    for ev in removed_sorted:
        if spans and ev["f0"] <= spans[-1][1] + 1:
            spans[-1][1] = max(spans[-1][1], ev["f1"])
        else:
            spans.append([ev["f0"], ev["f1"]])
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                         "stream=width,height", "-of", "csv=p=0", str(lut)],
                        capture_output=True, text=True)
    ow, oh = pr.stdout.strip().split(",")[:2]
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(lut), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, timeout=600)
    buf = r.stdout
    nf = len(buf) // (int(ow) * int(oh) * 3)
    full = np.frombuffer(buf[:nf * int(ow) * int(oh) * 3],
                         dtype=np.uint8).copy()
    fw, fh = int(ow), int(oh)
    fr = full.reshape(nf, fh, fw, 3)
    for a, b in spans:
        A, B = max(a - 1, 0), min(b + 1, nf - 1)
        span = B - A
        fa = fr[A].astype(np.float32)
        fb = fr[B].astype(np.float32)
        for k, fi in enumerate(range(A + 1, B)):
            w = (k + 1) / span
            fr[fi] = (fa * (1 - w) + fb * w).clip(0, 255).astype(np.uint8)
    del buf
    out = lut.with_name(lut.stem + "_deflash.mp4")
    # Windows 管道写大流不可靠 (Errno 22/死锁) → 临时 raw 文件中转
    raw = lut.with_name(lut.stem + "_raw.rgb")
    raw.write_bytes(full.tobytes())
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{fw}:{fh}", "-r", str(FPS), "-i", str(raw),
         "-i", str(lut), "-map", "0:v", "-map", "1:a?",
         "-c:v", "libx264", "-crf", "16", "-bf", "0",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
         str(out)], capture_output=True, timeout=1800)
    raw.unlink(missing_ok=True)
    if r.returncode != 0:
        print("ENCODE FAIL:", r.stderr.decode(errors="replace")[-300:])
        return
    print("写出:", out, out.stat().st_size)
    (ROOT / "tmp/kept_events.json").write_text(
        json.dumps({"kept": kept, "removed": len(removed)}, ensure_ascii=False),
        encoding="utf-8")


import numpy as np  # noqa: E402

if __name__ == "__main__":
    main()
