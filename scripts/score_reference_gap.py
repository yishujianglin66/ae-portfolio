# -*- coding: utf-8 -*-
"""score_reference_gap.py — 参照集 vs 本片 同口径评分 diff (2026-09-04)

把"觉得不如顶尖漫剪"变成可复测的逐维差值表：对参照集(外网顶尖漫剪)与你自己的
成片跑同一套【视频自含】指标，输出 mine / ref 均值 / Δ，并按 Δ 排序点出真正短板。

只允许"任意 mp4 都能算"的口径（外网参照片没有 production_report）：
  信号 5 项（视频+自身音轨）：削波峰值 / 高频能量 / 切点踩拍率 / 切点可见性 / 切率
  语义 7 维（cnn_scorer.local_score，CLIP+Ridge 本地 0-10）：动感/构图/色彩/文字/纹理/节奏/整体

用法:
  python scripts/score_reference_gap.py \
      --mine output/unified_run53/run53_final.mp4 \
      --refs data/reference_top/a.mp4 data/reference_top/b.mp4 \
      [--thr 0.30] [--out reports/reference_gap.json]
`--refs` 可传目录（自动扫 *.mp4）或多个文件。退出码 0。

依赖: ffmpeg, numpy, soundfile, librosa（信号）；open_clip+torch+sklearn（语义, 缺失则语义维标 N/A）。
"""
import argparse
import io
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))  # 让 from core.cnn_scorer import 可用
FF = shutil.which("ffmpeg") or "C:/ffmpeg/bin/ffmpeg.exe"

# 语义 7 维 (cnn_scorer TARGETS, 0-10, 越高越好)
SEMANTIC_DIMS = [
    "score_dynamism", "score_composition", "score_color_harmony",
    "score_text_read", "score_texture", "score_pacing", "score_overall",
]
# 信号指标方向: True=越高越好, False=越低越好
SIGNAL_DIR = {
    "peak": False,
    "hf_energy": True,
    "onset_density": True,
    "cut_rate": True,
    "beat_hit_rate": True,
    "cut_visibility": True,
}


def _video_audio(path):
    import soundfile as sf
    r = subprocess.run([FF, "-y", "-i", str(path), "-vn", "-ac", "1", "-ar",
                        "22050", "-f", "wav", "-"], capture_output=True, timeout=600)
    y, sr = sf.read(io.BytesIO(r.stdout), dtype="float32")
    return (y.mean(axis=1) if y.ndim > 1 else y), sr


def _duration(path):
    r = subprocess.run([FF, "-i", str(path)], capture_output=True, timeout=120)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)(\.\d+)?", r.stderr.decode("utf-8", "replace"))
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + float(m.group(4) or 0)


def _scene_cuts(path, thr):
    """ffmpeg select+scene 检测切点时间(s)列表。"""
    cmd = [FF, "-i", str(path), "-vf", f"select='gt(scene,{thr})',showinfo",
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=1200)
    txt = r.stderr.decode("utf-8", "replace")
    cuts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", txt)]
    return sorted(set(cuts))


def _onsets(y, sr):
    import librosa
    yh, yp = librosa.effects.hpss(y)
    on = librosa.onset.onset_detect(y=yp, sr=sr, units="time", backtrack=False,
                                    hop_length=256, delta=0.03, wait=2)
    return list(on)


def _frame_gray(path, t):
    r = subprocess.run([FF, "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                        "-vf", "scale=48:27,normalize", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-"], capture_output=True, timeout=120)
    v = np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)
    if v.size == 0:
        return None
    return (v - v.mean()) / (v.std() + 1e-6)


def _signal(path, cuts):
    y, sr = _video_audio(path)
    dur = len(y) / sr
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    from numpy.fft import irfft, rfft
    F = rfft(y); fr = np.fft.rfftfreq(len(y), 1 / sr)
    F[(fr < 4000) | (fr > 12000)] = 0
    # 按时长归一: 否则 30s vs 180s 的整段能量总和不可比
    hf_energy = float(np.sum(irfft(F, len(y)) ** 2)) / dur if dur else 0.0
    ons = _onsets(y, sr)
    n_cut = len(cuts)
    hit = 0
    for c in cuts:
        if any(abs(c - o) <= 0.080 for o in ons):
            hit += 1
    beat_hit = round(hit / n_cut, 4) if n_cut else 0.0
    # 切点可见: 采样 ≤12 个切点, 帧差(亮度归一化) 均值
    vis = []
    for t in cuts[:: max(1, n_cut // 12)][:12]:
        a = _frame_gray(path, max(0, t - 1 / 24))
        b = _frame_gray(path, t + 3 / 24)
        if a is not None and b is not None:
            vis.append(float(abs(a - b).mean()))
    return {
        "peak": round(peak, 4),
        "hf_energy": round(hf_energy, 1),
        "onset_density": round(len(ons) / dur, 3) if dur else 0.0,
        "cut_rate": round(n_cut / dur, 3) if dur else 0.0,
        "beat_hit_rate": beat_hit,
        "cut_visibility": round(float(np.mean(vis)), 4) if vis else 0.0,
        "n_cuts": n_cut,
        "duration": round(dur, 2),
    }


def _semantic(path):
    try:
        from core.cnn_scorer import local_score
        r = local_score(str(path))
        if "error" in r:
            print(f"    [语义跳过] {r['error']}")
            return None
        return r.get("scores", {})
    except Exception as e:
        print(f"    [语义跳过] {type(e).__name__}: {e}")
        return None


def collect(path, thr):
    print(f"  分析: {Path(path).name}")
    cuts = _scene_cuts(path, thr)
    sig = _signal(path, cuts)
    sem = _semantic(path)
    return {"signal": sig, "semantic": sem or {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", default=str(PROJ / "output" / "unified_run53" / "run53_final.mp4"))
    ap.add_argument("--refs", nargs="+", required=True,
                    help="参照视频文件或目录(自动扫 *.mp4)")
    ap.add_argument("--thr", type=float, default=0.30, help="场景切点阈值")
    ap.add_argument("--out", default=None, help="JSON 输出路径")
    args = ap.parse_args()

    refs = []
    for p in args.refs:
        pp = Path(p)
        if pp.is_dir():
            refs += sorted(pp.glob("*.mp4"))
        else:
            refs.append(pp)
    refs = [r for r in refs if r.exists() and r.suffix.lower() == ".mp4"]
    if not refs:
        print("无有效参照视频"); return 1
    mine = Path(args.mine)
    if not mine.exists():
        print(f"本片不存在: {mine}"); return 1

    print("=" * 72)
    print(f"本片: {mine.name}   参照 {len(refs)} 条")
    print("=" * 72)
    m = collect(mine, args.thr)
    R = [collect(r, args.thr) for r in refs]

    # 逐维聚合
    def agg(key_fn):
        return {k: round(float(np.mean([key_fn(d)[k] for d in R])), 4)
                for k in key_fn(m)}

    sig_mean = {k: round(float(np.mean([d["signal"][k] for d in R])), 4)
                for k in SIGNAL_DIR}
    sig_min = {k: round(float(np.min([d["signal"][k] for d in R])), 4) for k in SIGNAL_DIR}
    sig_max = {k: round(float(np.max([d["signal"][k] for d in R])), 4) for k in SIGNAL_DIR}
    sem_mean, sem_min = {}, {}
    for k in SEMANTIC_DIMS:
        vals = [d["semantic"][k] for d in R
                if d["semantic"] and d["semantic"].get(k) is not None]
        sem_mean[k] = round(float(np.mean(vals)), 4) if vals else None
        sem_min[k] = round(float(np.min(vals)), 4) if vals else None

    print("\n信号指标 (方向: ↑ 越高越好 / ↓ 越低越好):")
    print(f"  {'指标':<16}{'方向':<5}{'本片':>10}{'参照均值':>10}{'Δ(参照-本片)':>14}")
    rows = {}
    for k, better in SIGNAL_DIR.items():
        mv = m["signal"][k]
        rv = sig_mean[k]
        delta = round(rv - mv, 4)
        rows[k] = {"mine": mv, "ref_mean": rv, "ref_min": sig_min[k], "ref_max": sig_max[k],
                   "delta": delta, "better": better}
        print(f"  {k:<16}{'↑' if better else '↓':<5}{mv:>10}{rv:>10}{delta:>14}")

    print("\n语义指标 (↑ 越高越好, 0-10):")
    print(f"  {'指标':<24}{'本片':>8}{'参照均值':>10}{'参照最低':>10}{'Δ':>8}")
    for k in SEMANTIC_DIMS:
        mv = m["semantic"].get(k)
        rv = sem_mean[k]
        rmin = sem_min[k]
        mv_v = round(mv, 2) if mv is not None else None
        delta = round(rv - mv, 2) if (rv is not None and mv is not None) else None
        rows[k] = {"mine": mv_v, "ref_mean": rv, "ref_min": rmin,
                   "delta": delta, "better": True}
        print(f"  {k:<24}{(str(mv_v) if mv_v is not None else 'N/A'):>8}"
              f"{(str(rv) if rv is not None else 'N/A'):>10}"
              f"{(str(rmin) if rmin is not None else 'N/A'):>10}"
              f"{(str(delta) if delta is not None else 'N/A'):>8}")

    # 短板排行: higher=better 维度按 Δ 降序 → 参考最领先 = 最该补
    print("\n短板排行 (参考最领先的维度, 即你最该补的):")
    ranked = sorted(
        [(k, v) for k, v in rows.items() if v["better"] and v["delta"] is not None],
        key=lambda kv: kv[1]["delta"], reverse=True)
    for i, (k, v) in enumerate(ranked, 1):
        flag = "  ← 最大短板" if i == 1 else ""
        print(f"  {i:>2}. {k:<24} Δ={v['delta']:+.3f}{flag}")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mine": args.mine, "refs": [str(r) for r in refs],
            "mine_signal": m["signal"], "mine_semantic": m["semantic"],
            "ref_signal_mean": sig_mean, "ref_semantic_mean": sem_mean,
            "deltas": {k: v for k, v in rows.items()},
            "ranking": [k for k, _ in ranked],
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n已写 JSON: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())