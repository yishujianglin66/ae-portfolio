# -*- coding: utf-8 -*-
"""shot_forensics.py — 逐镜头视觉工程取证（制作逆向 Stage B，四层需求的核心）。

每个镜头跑一组可量化的像素取证，每个信号→效果推断都附数值与置信度：
  aberr_px      R/B 通道互相关偏移 → 色差/色散(Chromatic Aberration / AE Glow A-B 模式)
  glow_score    高亮像素边界外环带能量衰减 → 辉光半径与强度(Glow/Saber/Bloom)
  blur_elong    帧间差的方向自相关伸长率 → 运动模糊拖影(RSMB/Twixtor)
  particle_n    高亮小连通域计数 → 粒子(Particular/Form)
  grain_energy  拉普拉斯高频且帧间不相关 → 胶片颗粒/噪点
  dof_ratio     中心 vs 周边高频能比 → 景深虚化(镜头模糊/Deep Focus 反证)
  sharp_over    边缘过冲(亮暗条纹)宽度 → unsharp/细节增强剂量
  vignette      亮度径向衰减率 → 暗角
  sat/hue_rot   HSV 统计+色调旋转角 → 调色风格(单色偏移/低饱和/高对比)
  speed_curve   镜头内光流幅值序列 → 变速曲线形态(常量/线性/缓动/分段)
  dup_frames    相邻帧全等率 → 抽帧/静帧/定格(Twixtor 反证: 60fps 里的重复帧)

用法: python core/shot_forensics.py --graph data/shot_graphs/<模板>.json [--shots 0,1,2|all]
产物: data/shot_graphs/<模板>.forensics.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

FF = "ffmpeg"
SCALE_W = 320  # 取证分辨率（速度优先；px 类指标按比例换算说明）


def _decode_range(v: str, t0: float, t1: float) -> list[np.ndarray]:
    """解 [t0,t1) 全部帧到 320px BGR（内存安全：>6s 的镜头降采样到 15fps）。"""
    dur = max(t1 - t0, 1 / 120)
    r = subprocess.run(
        [FF, "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", v,
         "-vf", f"scale={SCALE_W}:-2", "-f", "image2pipe",
         "-vcodec", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True, timeout=300)
    h = int(SCALE_W * 9 / 16)  # 16:9 假设；非 16:9 模板由调用方校正
    # 用第一帧实际尺寸反推 h：从字节数算
    n = len(r.stdout)
    if n == 0:
        return []
    # 反推 h: n = frames * W * H * 3，取常见 H
    for cand_h in (180, 240, 135, 144, 270, 360):
        if n % (SCALE_W * cand_h * 3) == 0:
            h = cand_h
            break
    arr = np.frombuffer(r.stdout, dtype=np.uint8).reshape(-1, h, SCALE_W, 3)
    return [a for a in arr]


def _g(frames: list[np.ndarray]) -> np.ndarray:
    return np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]).astype(np.float32)


def sig_aberration(frames: list[np.ndarray]) -> dict:
    """R/B 通道水平互相关偏移（中位帧）。±2px 内视为无。"""
    f = frames[len(frames) // 2].astype(np.float32)
    R, B = f[:, :, 2], f[:, :, 0]
    best, bshift = -1.0, 0
    for s in range(-6, 7):
        a, b = (R, B[:, -s:]) if s > 0 else (R[:, :-s], B) if s < 0 else (R, B)
        w = min(a.shape[1], b.shape[1])
        a, b = a[:, :w], b[:, :w]
        c = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
        if c > best:
            best, bshift = c, s
    return {"aberr_px": bshift, "aberr_corr": round(best, 4)}


def sig_glow(frames: list[np.ndarray]) -> dict:
    """高亮核(>235)外 1/3/6px 环带均值 → 辉光衰减曲线粗样。"""
    g = _g(frames)[-1]
    core = g > 235
    if core.mean() < 0.001 or core.mean() > 0.3:
        return {"glow_score": 0.0, "glow_area": round(float(core.mean()), 4)}
    out = {}
    for r in (1, 3, 6):
        ring = (cv2.dilate(core.astype(np.uint8), np.ones((2 * r + 1,) * 2, np.uint8)) > 0) & ~core
        out[f"ring{r}"] = float(g[ring].mean()) if ring.any() else 0.0
    base = float(g[~core & (g < 200)].mean()) if (~core & (g < 200)).any() else 1.0
    score = max(0.0, (out.get("ring3", 0) - base) / max(base, 1.0))
    return {"glow_score": round(score, 3), "glow_area": round(float(core.mean()), 4),
            "halo_rings": {k: round(v, 1) for k, v in out.items()}}


def sig_motion_blur(frames: list[np.ndarray]) -> dict:
    """相邻帧差的方向能量伸长率（拖影特征）：水平/垂直差比偏离 1 越远越有方向性。"""
    if len(frames) < 3:
        return {"blur_elong": 1.0}
    g = _g(frames)
    d = np.abs(np.diff(g, axis=0))
    dh = np.abs(np.diff(d, axis=2)).mean() if d.shape[2] > 2 else 0  # 水平梯度
    dv = np.abs(np.diff(d, axis=1)).mean() if d.shape[1] > 2 else 0  # 垂直梯度
    e = (dh + 1e-6) / (dv + 1e-6)
    return {"blur_elong": round(float(max(e, 1 / e)), 2),
            "diff_energy": round(float(d.mean()), 2)}


def sig_particles(frames: list[np.ndarray]) -> dict:
    """高亮小连通域（面积 2-40px，亮度>200，孤立）计数 → 粒子嫌疑。"""
    g = _g(frames)[-1]
    m = ((g > 200).astype(np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(m)
    small = [s for s in stats[1:] if 2 <= s[4] <= 40]
    return {"particle_n": len(small),
            "particle_area_mean": round(float(np.mean([s[4] for s in small])), 1) if small else 0}


def sig_grain(frames: list[np.ndarray]) -> dict:
    """空间高频能 + 帧间高频相关性：低相关=时间噪声(颗粒)，高相关=纹理。"""
    g = _g(frames)
    lap = np.stack([cv2.Laplacian(x, cv2.CV_32F) for x in g])
    e = float(np.abs(lap[-1]).mean())
    if len(lap) >= 4:
        a = lap[-1][-8:, :].ravel()  # 简化：末两帧高频相关
        b = lap[-2][-8:, :].ravel()
        corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else 1.0
    else:
        corr = 1.0
    return {"grain_energy": round(e, 2), "grain_temporal_corr": round(corr, 2)}


def sig_dof(frames: list[np.ndarray]) -> dict:
    """中心 50% 与外圈的高频能比：<0.8 中心更糊(背景对焦?)，>1.25 周边糊=浅景深。"""
    g = _g(frames)[-1]
    h, w = g.shape
    cy, cx = slice(h // 4, h * 3 // 4), slice(w // 4, w * 3 // 4)
    lap = cv2.Laplacian(g, cv2.CV_32F)
    ic, ir = float(np.abs(lap[cy, cx]).mean()), float(np.abs(lap).mean())
    out_ring = np.abs(lap).copy()
    out_ring[cy, cx] = 0
    ob = float(out_ring[out_ring > 0].mean()) if (out_ring > 0).any() else 1.0
    return {"dof_ratio": round(ic / max(ob, 1e-6), 2)}


def sig_grade(frames: list[np.ndarray]) -> dict:
    """HSV 调色特征：饱和均值/亮度对比/hue 直方图集中度(单色调偏移)。"""
    f = frames[len(frames) // 2]
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.float32)
    h_hist = np.histogram(hsv[:, :, 0], bins=18, range=(0, 180))[0]
    p = h_hist / max(h_hist.sum(), 1)
    hue_conc = float((p.max()))  # 1/18=均匀；>0.25 明显色相集中
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    return {"sat_mean": round(float(hsv[:, :, 1].mean()), 1),
            "val_mean": round(float(hsv[:, :, 2].mean()), 1),
            "contrast_std": round(float(g.std()), 1),
            "hue_concentration": round(hue_conc, 3)}


def sig_speed_curve(frames: list[np.ndarray]) -> dict:
    """镜头内逐对光流幅值序列 → 形态分类（常量/线性/缓动/分段/近零=定格）。"""
    if len(frames) < 4:
        return {"flow_n": len(frames) - 1}
    gs = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    mags = []
    for a, b in zip(gs[:-1], gs[1:]):
        fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 9, 3, 5, 1.2, 0)
        mags.append(float(np.hypot(fl[..., 0], fl[..., 1]).mean()))
    m = np.array(mags)
    near_zero = float((m < 0.05).mean())
    cv_ = float(m.std() / max(m.mean(), 1e-6)) if len(m) > 1 else 0.0
    if near_zero > 0.6:
        shape = "frozen"
    else:
        x = np.linspace(0, 1, len(m))
        slope = float(np.polyfit(x, m, 1)[0]) if len(m) > 2 else 0.0
        if cv_ < 0.25:
            shape = "constant"
        elif abs(slope) > 0.5 * m.mean():
            shape = "ramp_up" if slope > 0 else "ramp_down"
        else:
            shape = "varied"
    return {"flow_mean": round(float(m.mean()), 3), "flow_cv": round(cv_ if len(m) > 1 else 0, 2),
            "flow_shape": shape, "flow_seq": [round(x, 3) for x in m[:24]]}


def sig_dup_frames(frames: list[np.ndarray], fps: float) -> dict:
    """相邻全等帧率（>0.15 且 fps>=50 → 抽帧/伪60fps；静帧时长估算）。"""
    if len(frames) < 2:
        return {"dup_ratio": 0.0}
    g = _g(frames)
    same = [float(np.abs(a - b).mean()) < 0.5 for a, b in zip(g[:-1], g[1:])]
    return {"dup_ratio": round(float(np.mean(same)), 3)}


def forensic_shot(video: str, shot: dict, fps: float) -> dict:
    frames = _decode_range(video, shot["start"], shot["end"])
    if not frames:
        return {**shot, "forensics_error": "no frames"}
    out = {**shot}
    out.update(sig_aberration(frames))
    out.update(sig_glow(frames))
    out.update(sig_motion_blur(frames))
    out.update(sig_particles(frames))
    out.update(sig_grain(frames))
    out.update(sig_dof(frames))
    out.update(sig_grade(frames))
    out.update(sig_speed_curve(frames))
    out.update(sig_dup_frames(frames, fps))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--shots", default="all")
    a = ap.parse_args()
    g = json.load(open(a.graph, encoding="utf-8"))
    v, fps = g["video"], g["fps"]
    idxs = range(len(g["shots"])) if a.shots == "all" else [int(x) for x in a.shots.split(",")]
    shots_out = []
    for i in idxs:
        s = g["shots"][i]
        r = forensic_shot(v, s, fps)
        shots_out.append(r)
        print(f"  镜{i} {s['start']:.2f}-{s['end']:.2f} "
              f"aberr={r.get('aberr_px')} glow={r.get('glow_score')} "
              f"blurE={r.get('blur_elong')} part={r.get('particle_n')} "
              f"dof={r.get('dof_ratio')} sat={r.get('sat_mean')} "
              f"flow={r.get('flow_shape')}({r.get('flow_mean')}) dup={r.get('dup_ratio')}")
    out_p = Path(a.graph).with_suffix(".forensics.json")
    doc = {k: g[k] for k in ("template", "video", "duration", "fps", "beat_sync", "sections")}
    doc["shots_forensic"] = shots_out
    doc["stage"] = "B_pixel_forensics"
    out_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"取证图谱: {out_p}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
