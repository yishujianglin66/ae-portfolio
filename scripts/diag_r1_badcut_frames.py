# -*- coding: utf-8 -*-
"""R1 坏切点段内运动诊断：区分"切点没切"与"素材内容本身静止"。

对每个坏切点 t，抽取 [t-0.25, t+0.25] 共 12 帧，算相邻帧 ahash 距离序列：

    [f-6][f-5][f-4][f-3][f-2][f-1] | [f+1][f+2][f+3][f+4][f+5][f+6]
                                 ↑ t

判定：
  - 段内相邻距离普遍 ≈0，切点处也 ≈0  → **素材内容静止**（选点问题，不是切点问题）
  - 段内相邻距离明显 >0，切点处 ≈0    → **切点真的没切**（渲染/拼接问题）
  - 段内 >0 且切点处也 >0             → 已修好（不该出现在本脚本输入里）

用法:
    python scripts/diag_r1_badcut_frames.py <video> <t1> <t2> ...
    python scripts/diag_r1_badcut_frames.py output/.../cut.mp4 --from-json reports/xxx.json
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cut_visibility_v3 import ahash, hamming, probe_fps, frames_by_number  # noqa: E402

WIN = 6  # 切点前后各取 6 帧


def frame_window(video: Path, t: float, fps: float, win: int = WIN):
    """抽 [t-win/fps, t+win/fps] 区间的帧，返回 {frame_no: Image}。"""
    fn_center = int(round(t * fps))
    lo, hi = fn_center - win, fn_center + win
    ss = max(0.0, lo / fps - 0.05)
    dur = (hi - lo) / fps + 0.15
    # 顺序编号：第 k 个输出文件 = 第 lo+k 帧（不用 -frame_pts，那是 pts 不是序号）
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "f%06d.png"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{ss:.4f}", "-i", str(video),
             "-t", f"{dur:.4f}", "-vsync", "0", str(out)],
            check=True, capture_output=True,
        )
        import numpy as np
        from PIL import Image
        imgs = {}
        for k, p in enumerate(sorted(Path(td).glob("f*.png"))):
            arr = np.asarray(Image.open(p).convert("L").resize((64, 64)),
                             dtype=np.uint8)
            imgs[lo + k + 1] = arr
        return imgs, lo, hi


def diagnose(video: Path, t: float, fps: float) -> dict:
    imgs, lo, hi = frame_window(video, t, fps)
    fn = int(round(t * fps))
    if fn not in imgs or (fn + 1) not in imgs:
        return {"t": t, "error": "missing center frames"}

    seq = []
    for n in range(lo, hi):
        if n in imgs and (n + 1) in imgs:
            seq.append((n, hamming(ahash(imgs[n]), ahash(imgs[n + 1]))))

    at_cut = next((d for n, d in seq if n == fn), None)
    before = [d for n, d in seq if n < fn - 1]
    after = [d for n, d in seq if n > fn + 1]
    inner = before + after
    inner_avg = sum(inner) / len(inner) if inner else 0.0
    inner_max = max(inner) if inner else 0

    if inner_max <= 3:
        verdict = "素材内容静止（整段无运动，选点问题）"
    elif at_cut is not None and at_cut <= 3 and inner_avg > 5:
        verdict = "切点没切（段内有运动，切点处无变化）"
    else:
        verdict = "其他（段内/切点均有变化，可能已修好）"

    return {
        "t": t,
        "frame": fn,
        "at_cut_hamming": at_cut,
        "inner_avg": round(inner_avg, 1),
        "inner_max": inner_max,
        "seq": seq,
        "verdict": verdict,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--from-json", help="v3 明细 json，自动取其中的坏刀")
    args = ap.parse_args()

    video = Path(args.video)
    fps = probe_fps(video)

    times = list(args.times)
    if args.from_json:
        d = json.load(open(args.from_json, encoding="utf-8"))
        times += [c["t"] for c in d["cuts"]
                  if c.get("frozen") or (c.get("vis") or 0) < 0.2]
    times = sorted(set(round(t, 4) for t in times))
    if not times:
        print("无坏切点")
        return 0

    print(f"[段内运动诊断] {video.name}  fps={fps}  坏切点 {len(times)} 个\n")
    print(f"{'t':>7} {'fn':>5} {'切点':>5} {'段内均':>6} {'段内峰':>6}  判定")
    print("-" * 72)
    tally = {}
    for t in times:
        r = diagnose(video, t, fps)
        if "error" in r:
            print(f"{t:7.2f}  {r['error']}")
            continue
        print(f"{t:7.2f} {r['frame']:5d} {r['at_cut_hamming']:5d} "
              f"{r['inner_avg']:6.1f} {r['inner_max']:6d}  {r['verdict']}")
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\n汇总:")
    for k, v in sorted(tally.items(), key=lambda x: -x[1]):
        print(f"  {v:3d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
