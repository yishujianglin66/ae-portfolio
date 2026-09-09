# -*- coding: utf-8 -*-
"""cut_visibility_v2.py — 切点可见性度量 v2（帧号对齐，2026-09-09）

为什么需要 v2：
  v1（`score_reference_gap.py` 的 cut_visibility）用 `-ss t±1/24` 取帧，
  但 ffmpeg 的 `-ss` 在帧时间戳前 ~0.5ms 内会**回退到上一帧**，导致同一
  切点在 ±0.5ms 扰动下数值在 0.35~1.14 间跳变（3 倍波动）。实测证据见
  `03-阶段报告/cut_visibility根因诊断报告_2026-09-09.md`。

v2 设计：
  1. **帧号对齐**：切点先吸附到帧号 fn = round(t*fps)，取帧用
     `select=eq(n,fn)` 精确选帧，彻底消除时间→帧的歧义。
  2. **多帧对均值**：比较 frame(fn-1) 与 frame(fn+1)、frame(fn+2)、frame(fn+3)
     三对的均值，避免单点恰好落在黑场/纯色帧造成的假阴性/假阳性。
  3. **全切点统计**：不做 12 点采样，报告全切点均值 + 分位数。
  4. **可选 frozen 率**：同时报 ahash 冻结率（与 cutpoint_selfeval 同判据），
     双指标并用避免单一尺子偏差。

用法:
  python scripts/cut_visibility_v2.py --video X.mp4
  python scripts/cut_visibility_v2.py --refs data/reference_top --workers 6
  python scripts/cut_visibility_v2.py --compare A.mp4 B.mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"
FFPROBE = shutil.which("ffprobe") or "C:/ffmpeg/bin/ffprobe.exe"
ALLOWED_SUFFIXES = (".mp4", ".mov", ".mkv", ".webm", ".m4v")
CACHE = PROJ / "reports" / "cutvis_v2_cache.json"

# 与 v1 保持一致的切点检测阈值
SCENE_THR = 0.30
# 多帧对偏移（相对切点帧 fn）
PAIR_OFFSETS = (1, 2, 3)


def safe_video(raw: str | Path) -> Path | None:
    try:
        p = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return p


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          shell=False, check=False)


def probe_fps(path: Path) -> float:
    r = _run([FFPROBE, "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0",
              str(path)], timeout=60)
    try:
        frac = (r.stdout or b"").decode().strip().splitlines()[0]
        num, den = frac.split("/")
        return float(num) / float(den) if float(den) else 24.0
    except (IndexError, ValueError, ZeroDivisionError):
        return 24.0


def scene_cuts(path: Path, thr: float = SCENE_THR) -> list[float]:
    """与 v1 同口径的切点检测（ffmpeg select+scene）。"""
    import re
    cmd = [FF, "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo",
           "-f", "null", "-"]
    r = _run(cmd, timeout=1800)
    txt = (r.stderr or b"").decode("utf-8", "replace")
    return sorted(set(float(m) for m in re.findall(r"pts_time:([0-9.]+)", txt)))


def frames_by_number(path: Path, fns: list[int], w: int = 48, h: int = 27,
                     batch: int = 24) -> dict:
    """按帧号精确取帧。

    实现策略（2026-09-09 性能优化）：一次 ffmpeg 调用抽全片低分辨率灰度帧到内存，
    再按帧号索引。相比逐批 select（每批都要解码全片），这是 O(1) 次解码。

    实测：30s/24fps 片子从 33s 降到 ~4s。
    """
    if not fns:
        return {}
    want = sorted(set(int(n) for n in fns if n >= 0))
    hi = max(want)
    # 只解码到需要的最大帧号即可（-frames:v 截断）
    cmd = [FF, "-v", "error", "-i", str(path),
           "-vf", f"scale={w}:{h}", "-fps_mode", "passthrough",
           "-frames:v", str(hi + 1),
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = _run(cmd, timeout=1800)
    buf = np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)
    n_frames = buf.size // (w * h)
    if n_frames == 0:
        return {}
    arr = buf[:n_frames * w * h].reshape(n_frames, h, w)
    return {fn: arr[fn] for fn in want if fn < n_frames}


def norm(x: np.ndarray) -> np.ndarray:
    """零均值单位方差归一化（与 v1 一致）。"""
    return (x - x.mean()) / (x.std() + 1e-6)


def ahash(frame: np.ndarray, size: int = 8) -> int:
    """平均哈希（8x8），用于冻结帧判据。"""
    h, w = frame.shape
    # 分块均值近似缩放
    bh, bw = max(h // size, 1), max(w // size, 1)
    small = frame[:size * bh, :size * bw].reshape(size, bh, size, bw).mean(axis=(1, 3))
    bits = (small > small.mean()).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def analyze_video(path: Path, thr: float = SCENE_THR,
                  freeze_hamming: int = 10) -> dict:
    """对单部视频计算 v2 切点可见性。"""
    fps = probe_fps(path)
    cuts = scene_cuts(path, thr)
    if not cuts:
        return {"video": str(path), "fps": fps, "n_cuts": 0,
                "cut_visibility_v2": 0.0, "frozen_rate": 0.0, "cuts": []}

    # 收集所有需要的帧号
    needed = set()
    cut_fns = []
    for t in cuts:
        fn = int(round(t * fps))
        cut_fns.append(fn)
        needed.add(fn - 1)
        for off in PAIR_OFFSETS:
            needed.add(fn + off)
    frames = frames_by_number(path, sorted(needed))

    rows = []
    for t, fn in zip(cuts, cut_fns):
        prev = frames.get(fn - 1)
        if prev is None:
            continue
        pn = norm(prev)
        diffs = []
        for off in PAIR_OFFSETS:
            nxt = frames.get(fn + off)
            if nxt is None:
                continue
            diffs.append(float(np.abs(pn - norm(nxt)).mean()))
        if not diffs:
            continue
        # 冻结判据：与 fn+1 的 ahash 距离
        nxt1 = frames.get(fn + 1)
        hd = hamming(ahash(prev), ahash(nxt1)) if nxt1 is not None else None
        rows.append({
            "t": round(t, 3), "frame": fn,
            "vis": round(float(np.mean(diffs)), 4),
            "vis_min": round(float(np.min(diffs)), 4),
            "vis_max": round(float(np.max(diffs)), 4),
            "ahash_dist": hd,
        })

    vals = [r["vis"] for r in rows]
    frozen = [r for r in rows if r["ahash_dist"] is not None
              and r["ahash_dist"] < freeze_hamming]
    return {
        "video": str(path), "fps": fps,
        "n_cuts": len(cuts), "n_measured": len(rows),
        "cut_visibility_v2": round(float(np.mean(vals)), 4) if vals else 0.0,
        "p25": round(float(np.percentile(vals, 25)), 4) if vals else 0.0,
        "p50": round(float(np.percentile(vals, 50)), 4) if vals else 0.0,
        "p75": round(float(np.percentile(vals, 75)), 4) if vals else 0.0,
        "min": round(float(np.min(vals)), 4) if vals else 0.0,
        "frozen_count": len(frozen),
        "frozen_rate": round(len(frozen) / len(rows), 4) if rows else 0.0,
        "weak_cuts": sorted(rows, key=lambda r: r["vis"])[:20],
        "cuts": rows,
    }


def _worker(args: tuple) -> dict:
    path, thr = args
    try:
        return analyze_video(Path(path), thr)
    except Exception as e:  # 单部失败不拖垮整批
        return {"video": str(path), "error": f"{type(e).__name__}: {e}"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default=None)
    ap.add_argument("--refs", default=None, help="参照集目录")
    ap.add_argument("--compare", nargs=2, default=None)
    ap.add_argument("--thr", type=float, default=SCENE_THR)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="reports/cut_visibility_v2.json")
    args = ap.parse_args()

    # ---- 批量：参照集 ----
    if args.refs:
        d = Path(args.refs)
        videos = sorted(d.glob("*.mp4")) if d.is_dir() else [Path(args.refs)]
        cache = {}
        if CACHE.exists() and not args.no_cache:
            try:
                cache = json.loads(CACHE.read_text(encoding="utf-8"))
            except Exception:
                cache = {}
        todo = [v for v in videos if v.name not in cache]
        print(f"参照 {len(videos)} 部 | 缓存 {len(videos) - len(todo)} | 待算 {len(todo)} "
              f"| workers={args.workers}", flush=True)
        t0 = time.time()
        if args.workers <= 1:
            # 单进程模式：逐部落盘缓存，中断可续（多进程池在长视频上易僵住）
            for i, v in enumerate(todo, 1):
                res = _worker((str(v), args.thr))
                if "error" in res:
                    print(f"  [{i}/{len(todo)}] FAIL {v.name[:44]}: "
                          f"{res['error'][:70]}", flush=True)
                    continue
                cache[v.name] = res
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
                print(f"  [{i}/{len(todo)}] {v.name[:40]} "
                      f"v2={res['cut_visibility_v2']} ({time.time() - t0:.0f}s)",
                      flush=True)
        else:
            done = 0
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(_worker, (str(v), args.thr)): v for v in todo}
                for fut in as_completed(futs):
                    res = fut.result()
                    done += 1
                    name = Path(res["video"]).name
                    if "error" in res:
                        print(f"  [{done}/{len(todo)}] FAIL {name[:44]}: "
                              f"{res['error'][:70]}", flush=True)
                        continue
                    cache[name] = res
                    if done % 5 == 0 or done == len(todo):
                        CACHE.parent.mkdir(parents=True, exist_ok=True)
                        CACHE.write_text(
                            json.dumps(cache, ensure_ascii=False, indent=1),
                            encoding="utf-8")
                        print(f"  [{done}/{len(todo)}] {time.time() - t0:.0f}s",
                              flush=True)
        if cache:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1),
                             encoding="utf-8")
            print(f"缓存 → {CACHE}（{len(cache)} 部）", flush=True)

        ok = [v for v in cache.values() if "error" not in v and v.get("n_cuts")]
        vals = [v["cut_visibility_v2"] for v in ok]
        frz = [v["frozen_rate"] for v in ok]
        summary = {
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_videos": len(ok),
            "cut_visibility_v2": {
                "mean": round(float(np.mean(vals)), 4),
                "p25": round(float(np.percentile(vals, 25)), 4),
                "p50": round(float(np.percentile(vals, 50)), 4),
                "p75": round(float(np.percentile(vals, 75)), 4),
                "p90": round(float(np.percentile(vals, 90)), 4),
                "min": round(float(np.min(vals)), 4),
                "max": round(float(np.max(vals)), 4),
            },
            "frozen_rate": {
                "mean": round(float(np.mean(frz)), 4),
                "p50": round(float(np.percentile(frz, 50)), 4),
                "p75": round(float(np.percentile(frz, 75)), 4),
            },
            "per_video": {v["video"]: {k: v[k] for k in
                                       ("n_cuts", "cut_visibility_v2",
                                        "frozen_rate", "p25", "p50", "p75")}
                          for v in ok},
        }
        print(f"\nv2 切点可见性（n={len(ok)}）:")
        for k, v in summary["cut_visibility_v2"].items():
            print(f"  {k:>5}: {v}")
        print(f"冻结率均值: {summary['frozen_rate']['mean']}")
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print(f"\n→ {out}")
        return 0

    # ---- 对比 ----
    if args.compare:
        res = {}
        for v in args.compare:
            p = safe_video(v)
            if p is None:
                print(f"[跳过] {v}")
                continue
            r = analyze_video(p, args.thr)
            res[p.name] = r
            print(f"{p.name}: v2={r['cut_visibility_v2']} "
                  f"冻结率={r['frozen_rate']} ({r['n_cuts']} 刀)")
        if len(res) == 2:
            a, b = res.values()
            d = round(b["cut_visibility_v2"] - a["cut_visibility_v2"], 4)
            df = round(b["frozen_rate"] - a["frozen_rate"], 4)
            print(f"\nΔ可见性 = {d:+.4f} | Δ冻结率 = {df:+.4f}")
        return 0

    # ---- 单片 ----
    if not args.video:
        ap.error("需要 --video / --refs / --compare 之一")
    p = safe_video(args.video)
    if p is None:
        print(f"无效视频: {args.video}")
        return 1
    r = analyze_video(p, args.thr)
    print(f"视频: {p.name}")
    print(f"切点 {r['n_cuts']} 刀 | 成功测量 {r['n_measured']}")
    print(f"cut_visibility_v2 = {r['cut_visibility_v2']}")
    print(f"  p25={r['p25']} p50={r['p50']} p75={r['p75']} min={r['min']}")
    print(f"冻结率 = {r['frozen_rate']}（{r['frozen_count']} 处）")
    print(f"\n最弱 10 刀:")
    print(f"  {'t':>8}{'帧号':>7}{'v2':>9}{'最小对':>9}{'ahash':>7}")
    for c in r["weak_cuts"][:10]:
        print(f"  {c['t']:>8.3f}{c['frame']:>7}{c['vis']:>9.4f}"
              f"{c['vis_min']:>9.4f}{(c['ahash_dist'] if c['ahash_dist'] is not None else -1):>7}")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(r, ensure_ascii=False, indent=1),
                                 encoding="utf-8")
        print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
