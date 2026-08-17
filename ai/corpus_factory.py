# -*- coding: utf-8 -*-
"""T19 巨人语料工厂 — D盘约150集自动扫描→场景切镜头→关键帧抽取→元数据落盘。

设计要点（P4方案）:
- 断点续传: state.json记录已处理文件, 崩溃/中断可直接重跑
- hash去重: 帧内容phash近似去重(首16KB哈希粗筛)
- 全自动化零点击, 后台长跑
用法: python -m ai.corpus_factory --build [--max-videos N] [--fps-thr 0.35]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
CORPUS_ROOT = Path(r"D:\aot_corpus")
FRAMES_DIR = CORPUS_ROOT / "frames"
META_PATH = CORPUS_ROOT / "corpus_meta.json"
STATE_PATH = CORPUS_ROOT / "state.json"
LOG_PATH = Path("reports") / "corpus_factory_log.txt"

SEASON_DIRS = [
    (r"D:\夸克\[DMG&EMD&VCB-Studio] Shingeki no Kyojin [Ma10p_1080p]", "S1"),
    (r"D:\夸克\[DMG&VCB-Studio] Shingeki no Kyojin Season 2 [Ma10p_1080p]", "S2"),
    (r"D:\夸克\[BeanSub&VCB-Studio] Shingeki no Kyojin Season 3 [Ma10p_1080p]", "S3"),
    (r"D:\夸克\[BeanSub&VCB-Studio] Shingeki no Kyojin The Final Season [Ma10p_1080p]", "FS"),
    (r"D:\夸克\[DMG&EMD&BeanSub&VCB-Studio] Shingeki no Kyojin OADs [Ma10p_1080p]", "OAD"),
]


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def scan_videos() -> list:
    vids = []
    for base, season in SEASON_DIRS:
        base_p = Path(base)
        if not base_p.exists():
            log(f"跳过不存在目录: {base}")
            continue
        for p in sorted(base_p.rglob("*")):
            if p.suffix.lower() in (".mkv", ".mp4") and p.is_file():
                vids.append({"path": str(p), "season": season, "name": p.stem})
    return vids


def probe_duration(path: str) -> float:
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", path],
                           capture_output=True, text=True, timeout=60)
        return float(r.stdout.strip() or 0)
    except Exception:
        return 0.0


def detect_scenes(path: str, thr: float) -> list:
    """ffmpeg scene-change检测, 返回切点秒列表。"""
    cmd = [FFMPEG, "-hide_banner", "-hwaccel", "auto", "-an", "-i", path, "-vf",
           f"select='gt(scene,{thr})',showinfo", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", timeout=3600)
        pts = []
        for line in r.stderr.splitlines():
            if "pts_time" in line:
                try:
                    seg = line.split("pts_time:")[1].split()[0]
                    pts.append(float(seg))
                except Exception:
                    continue
        return sorted(pts)
    except Exception as e:
        log(f"  scene检测失败: {e}")
        return []


def shots_from_scenes(scenes: list, duration: float, max_shot_len: float = 20.0) -> list:
    """切点→镜头段(in,out); 超长段按max_shot_len细分。"""
    bounds = [0.0] + scenes + [duration]
    shots = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        if b - a < 0.4:
            continue
        t = a
        while t < b - 0.2:
            e = min(t + max_shot_len, b)
            shots.append((t, e))
            t = e
    return shots


def extract_keyframes(path: str, shots: list, vid_id: str) -> list:
    """每镜头取最多2帧关键帧(1/3与2/3处), 粗hash去重。"""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    out, seen = [], set()
    for si, (a, b) in enumerate(shots):
        dur = b - a
        for frac in (0.33, 0.67):
            t = a + dur * frac
            fn = FRAMES_DIR / f"{vid_id}_s{si:04d}_{int(t*1000)}.jpg"
            if fn.exists():
                out.append({"frame": str(fn), "shot": si, "t_in": a, "t_out": b, "t": t})
                continue
            cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-hwaccel", "auto",
                   "-ss", f"{t:.3f}",
                   "-i", path, "-frames:v", "1", "-q:v", "3", "-vf",
                   "scale='min(640,iw)':-2", str(fn), "-y"]
            try:
                subprocess.run(cmd, capture_output=True, timeout=120)
            except Exception:
                continue
            if not fn.exists() or fn.stat().st_size < 2000:
                if fn.exists():
                    fn.unlink()
                continue
            h = hashlib.md5(fn.read_bytes()[:16384]).hexdigest()
            if h in seen:
                fn.unlink()
                continue
            seen.add(h)
            out.append({"frame": str(fn), "shot": si, "t_in": a, "t_out": b, "t": t})
    return out


def build(max_videos: int = 0, thr: float = 0.35):
    CORPUS_ROOT.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {"done": {}, "frames_total": 0}
    meta = json.loads(META_PATH.read_text(encoding="utf-8")) if META_PATH.exists() else {"videos": [], "frames_total": 0}
    done_names = set(state["done"].keys())

    vids = scan_videos()
    if max_videos > 0:
        vids = vids[:max_videos]
    log(f"扫描到视频 {len(vids)} 个, 已完成 {len(done_names)} 个")

    for vi, v in enumerate(vids):
        if v["name"] in done_names:
            continue
        t0 = time.time()
        duration = probe_duration(v["path"])
        if duration <= 0:
            log(f"[{vi+1}/{len(vids)}] 探测失败跳过: {v['name']}")
            state["done"][v["name"]] = {"status": "probe_fail"}
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            continue
        scenes = detect_scenes(v["path"], thr)
        shots = shots_from_scenes(scenes, duration)
        vid_id = f"{v['season']}_{vi:03d}"
        frames = extract_keyframes(v["path"], shots, vid_id)
        rec = {"vid": vid_id, "season": v["season"], "name": v["name"],
               "path": v["path"], "duration": round(duration, 2),
               "n_scenes": len(scenes), "n_shots": len(shots),
               "frames": frames}
        meta["videos"].append(rec)
        meta["frames_total"] += len(frames)
        state["done"][v["name"]] = {"status": "ok", "frames": len(frames),
                                    "shots": len(shots)}
        state["frames_total"] = meta["frames_total"]
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        META_PATH.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        log(f"[{vi+1}/{len(vids)}] {v['name']} | {duration:.0f}s | 镜头{len(shots)} | 帧{len(frames)} | "
            f"累计{meta['frames_total']} | {time.time()-t0:.0f}s")
    log(f"语料工厂完成: 视频{len(meta['videos'])} 帧总数{meta['frames_total']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--max-videos", type=int, default=0)
    ap.add_argument("--fps-thr", type=float, default=0.35)
    args = ap.parse_args()
    if args.build:
        build(args.max_videos, args.fps_thr)
