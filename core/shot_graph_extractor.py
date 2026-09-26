# -*- coding: utf-8 -*-
"""shot_graph_extractor.py — 模板"镜头设计图谱"提取器（蒸馏管线 Stage A）。

策略转向核心件：禁止凭空造规则——从 9 个 成品.mp4 模板逐镜头蒸馏硬事实。
Stage A（本文件，纯信号级）：
  镜头切分(scene) → 每镜时长/起止帧特征(闪白/黑场/静帧) → 镜间衔接类型
  → 切点-BPM 踩拍分布 → 段落划分(切密度×音频能量窗口)
Stage B（后续叠加）：每镜运镜(SourceCameraInventory)+景别(VLM)。

产物: data/shot_graphs/<模板名>.json —— 编排器的硬约束输入。
用法: python core/shot_graph_extractor.py [--dir D:\\AE-Work\\resources\\video] [--out data/shot_graphs]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

FF = "ffmpeg"
FP = "ffprobe"


def _probe_dur(v: str) -> float:
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", v], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _scene_cuts(v: str, thresh: float = 0.30) -> list[float]:
    """ffmpeg 场景检测切点（秒）。阈值 0.30 对齐闸门"切点可见"口径。"""
    r = subprocess.run(
        [FF, "-i", v, "-vf", f"select='gt(scene,{thresh})',showinfo",
         "-fps_mode", "vfr", "-f", "null", "-"],
        capture_output=True, text=True, errors="ignore", timeout=1200)
    cuts: list[float] = []
    for line in (r.stderr or "").splitlines():
        if "pts_time:" in line:
            try:
                cuts.append(float(line.split("pts_time:")[1].split()[0]))
            except (ValueError, IndexError):
                pass
    return sorted(set(round(c, 3) for c in cuts))


def _fps(v: str) -> float:
    r = subprocess.run([FP, "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", v],
                       capture_output=True, text=True)
    try:
        n, d = r.stdout.strip().split("/")
        return float(n) / float(d)
    except Exception:
        return 30.0


def _frame_at(v: str, t: float, scale: str = "16x9") -> np.ndarray:
    """取 t 时刻灰度帧（16x9 均值足够判闪白/黑场/静帧，解码极快）。"""
    r = subprocess.run(
        [FF, "-ss", f"{max(t, 0):.3f}", "-i", v, "-frames:v", "1",
         "-vf", f"scale={scale},format=gray", "-f", "rawvideo", "-"],
        capture_output=True, timeout=60)  # 不传 text=True：rawvideo 是二进制
    return np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)


def _shot_edge_features(v: str, start: float, end: float, fps: float) -> dict:
    """起止帧特征：闪白(head/tail 亮度过载)、黑场、静帧(首尾帧相同=定格)。"""
    d = end - start
    head = _frame_at(v, start + 0.5 / fps)
    mid = _frame_at(v, start + d / 2)
    tail = _frame_at(v, max(end - 1.5 / fps, start))
    f2 = _frame_at(v, start + 2.5 / fps) if d > 0.15 else mid
    feat = {}
    feat["head_bright"] = float(head.mean())
    feat["flash_in"] = bool(head.mean() > 225 and mid.mean() < 200)
    feat["black_in"] = bool(head.mean() < 12)
    # 静帧：首帧与 2.5 帧后完全相同（同素材定格 ≥0.1s）
    feat["frozen"] = bool(d > 0.1 and np.abs(head - f2).mean() < 1.0)
    return feat


def _transition_kind(v: str, cut_t: float, fps: float) -> str:
    """切点类型：闪白帧/黑帧/硬切（切点后首帧特征判定，剂量留给 Stage B 精算）。"""
    after = _frame_at(v, cut_t + 0.5 / fps)
    before = _frame_at(v, max(cut_t - 2.0 / fps, 0))
    if after.mean() > 225 and before.mean() < 200:
        return "flash"
    if after.mean() < 12:
        return "black"
    return "cut"


def _tmp_wav(v: str) -> str:
    """抽音轨到临时 wav。Windows 坑：NamedTemporaryFile(delete=True) 持文件锁，
    ffmpeg 无法写同一句柄——用 delete=False + 自己清理。"""
    import os
    import tempfile as _tf
    fd, wav = _tf.mkstemp(suffix=".wav")
    os.close(fd)
    subprocess.run([FF, "-y", "-v", "error", "-i", v, "-ac", "1", "-ar", "22050",
                    wav], capture_output=True, timeout=300)
    return wav


def _beats_and_sync(v: str, cuts: list[float]) -> dict:
    """模板自身音轨 BPM + 切点踩拍分布（±ms 直方图，蒸馏"踩拍习惯"）。"""
    try:
        import librosa
        wav = _tmp_wav(v)
        try:
            y, sr = librosa.load(wav, sr=None, mono=True)
        finally:
            import os
            os.unlink(wav)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        beat_t = librosa.frames_to_time(
            librosa.beat.beat_track(y=y, sr=sr)[1], sr=sr)
        bpms = float(np.asarray(tempo).item())
        if not len(beat_t) or not cuts:
            return {"bpm": bpms}
        gaps = [min(abs(c - b) for b in beat_t) * 1000 for c in cuts]
        hist = {"<=50ms": sum(1 for g in gaps if g <= 50),
                "<=80ms": sum(1 for g in gaps if g <= 80),
                "<=120ms": sum(1 for g in gaps if g <= 120),
                ">120ms": sum(1 for g in gaps if g > 120)}
        return {"bpm": bpms, "n_beats": int(len(beat_t)),
                "sync_hist_ms": hist,
                "sync_rate_80ms": round(hist["<=80ms"] / max(len(cuts), 1), 3),
                "gap_median_ms": round(float(np.median(gaps)), 1)}
    except Exception as e:  # noqa: BLE001
        return {"bpm_error": str(e)[:120]}


def _sections(v: str, cuts: list[float], dur: float) -> list[dict]:
    """段落划分：0.5s 粒度切密度 × 音频 RMS 能量双通道，找结构拐点。
    不预设五段式——按真实数据切（密度/能量的显著变化点分段）。"""
    if dur <= 0 or not cuts:
        return []
    grid = np.arange(0, dur, 0.5)
    dens = np.histogram(cuts, bins=np.append(grid, dur + 1))[0] / 0.5
    rms = np.zeros_like(dens, dtype=float)
    try:
        import librosa
        wav = _tmp_wav(v)
        try:
            y, sr = librosa.load(wav, sr=None, mono=True)
        finally:
            import os
            os.unlink(wav)
        frame_rms = librosa.feature.rms(y=y)[0]
        ft = librosa.frames_to_time(np.arange(len(frame_rms)), sr=sr)
        for i, g in enumerate(grid):
            m = (ft >= g) & (ft < g + 0.5)
            rms[i] = float(frame_rms[m].mean()) if m.any() else 0.0
    except Exception:  # noqa: BLE001
        pass
    if dens.max() <= 0:
        return []
    dn, rn = dens / max(dens.max(), 1e-9), rms / max(rms.max(), 1e-9)
    combo = 0.6 * dn + 0.4 * rn  # 密度主导、能量辅助（权重在报告中标注可调）
    segs, cur, cur_lo = [], [], 0
    thr_hi, thr_lo = combo.mean() + combo.std(), combo.mean() - combo.std()
    for i, val in enumerate(combo):
        lvl = "burst" if val > thr_hi else ("calm" if val < thr_lo else "mid")
        if cur and lvl != cur[-1]:
            segs.append((cur_lo, float(grid[i]), cur[0]))
            cur, cur_lo = [], float(grid[i])
        cur.append(lvl)
    if cur:
        segs.append((cur_lo, float(dur), cur[0]))
    return [{"t0": round(a, 2), "t1": round(b, 2), "energy_class": c,
             "dur": round(b - a, 2),
             "cuts": sum(1 for x in cuts if a <= x < b),
             "cut_rate": round(sum(1 for x in cuts if a <= x < b) / max(b - a, .01), 2)}
            for a, b, c in segs if b - a >= 0.4]


def extract(video: str, name: str) -> dict:
    dur, fps = _probe_dur(video), _fps(video)
    cuts = _scene_cuts(video)
    bounds = [0.0] + cuts + [dur]
    shots = []
    for i in range(len(bounds) - 1):
        s, e = bounds[i], bounds[i + 1]
        if e - s < 0.02:
            continue  # 双帧噪声切点合并
        feat = _shot_edge_features(video, s, e, fps)
        shots.append({"idx": len(shots), "start": round(s, 3), "end": round(e, 3),
                      "dur": round(e - s, 3), **feat})
    trans = [_transition_kind(video, c, fps) for c in cuts]
    durs = np.array([x["dur"] for x in shots]) if shots else np.array([0.0])
    graph = {
        "template": name, "video": video, "duration": round(dur, 2), "fps": fps,
        "n_shots": len(shots), "n_cuts": len(cuts),
        "shot_dur_stats": {"mean": round(float(durs.mean()), 3),
                           "median": round(float(np.median(durs)), 3),
                           "p10": round(float(np.percentile(durs, 10)), 3),
                           "p90": round(float(np.percentile(durs, 90)), 3),
                           "min": round(float(durs.min()), 3),
                           "max": round(float(durs.max()), 3)},
        "cut_rate_per_sec": round(len(cuts) / max(dur, .01), 2),
        "transition_dist": {k: trans.count(k) for k in set(trans)},
        "flash_ratio": round(trans.count("flash") / max(len(trans), 1), 3),
        "frozen_shots": [x["idx"] for x in shots if x.get("frozen")],
        "black_shots": [x["idx"] for x in shots if x.get("black_in")],
        "beat_sync": _beats_and_sync(video, cuts),
        "sections": _sections(video, cuts, dur),
        "shots": shots,
        "extracted_at": str(np.datetime64("now", "s")),
        "stage": "A_signal_only (B=camera/shotsize pending)",
    }
    return graph


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=r"D:\AE-Work\resources\video")
    ap.add_argument("--out", default="data/shot_graphs")
    ap.add_argument("--videos", nargs="*", default=None, help="指定文件，默认全部 成品.mp4")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    vids = a.videos or [str(p) for p in Path(a.dir).rglob("成品.mp4")]
    print(f"模板数: {len(vids)}")
    for v in vids:
        pth = Path(v)
        name = f"{pth.parent.name}__{pth.stem}"[:80]  # 含目录前缀防同目录多文件覆盖
        print(f"\n=== {name} ===")
        g = extract(v, name)
        p = out / f"{name}.json"
        p.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        bs = g["beat_sync"]
        bpm = bs.get("bpm")
        bpm_s = f"{bpm:.0f}" if isinstance(bpm, (int, float)) else "?"
        sr80 = bs.get("sync_rate_80ms")
        sr80_s = f"{sr80:.0%}" if isinstance(sr80, (int, float)) else "?"
        print(f"  {g['n_shots']}镜 均长{g['shot_dur_stats']['mean']}s "
              f"p10-p90[{g['shot_dur_stats']['p10']}-{g['shot_dur_stats']['p90']}] "
              f"切率{g['cut_rate_per_sec']}/s 闪切{g['transition_dist'].get('flash', 0)} "
              f"黑场{g['transition_dist'].get('black', 0)} BPM={bpm_s} "
              f"踩拍80ms={sr80_s}")
        print(f"  段落: " + " | ".join(
            f"{s['t0']}-{s['t1']}s {s['energy_class']}({s['cut_rate']}切/s)"
            for s in g["sections"][:8]))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
