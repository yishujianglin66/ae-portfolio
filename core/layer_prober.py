# -*- coding: utf-8 -*-
"""layer_prober.py — 镜头内"层产生方式"判别探针（制作链考古 Stage C）。

回答"这个镜头的哪些层来自哪种生产工具"——每个判别信号绑定产生方式假设：
  line_boil      边缘位置帧间抖动度 → 手书逐帧（高）vs 赛璐璐/木偶（低）
  rigid_blocks   光流分块一致率 → 木偶刚体部件驱动（块内一致+块间离散）
  parallax_split 画面上下/左右光流幅值差 → 2.5D 分层视差 / camera projection
  flow_diverge   光流散度非零占比 → 三维摄像机运动（推轨/环绕的透视证据）
  edge_halo      主体边界渐变环宽度 → 抠像蒙版（Silhouette Roto/PS 抠图）
  color_banding  唯一色/总像素比 → 动画赛璐璐（低）vs 实拍（高）
  flat_share     纯色像素占比 → shape 层闪白/黑场/遮罩擦除层
  alpha_island   孤立高对比前景连通域 → 前景角色独立层（预合成嫌疑）

用法: python core/layer_prober.py --video <路径> --graph <shot_graph.json>
产物: <graph 同目录>/<name>.layers.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

SCALE_W, SCALE_H = 320, 180


def _decode(v: str, t0: float, dur: float, max_frames: int = 30) -> list[np.ndarray]:
    """解镜头帧（超过 max_frames 时均匀抽帧，保首尾）。"""
    r = subprocess.run(
        [ "ffmpeg", "-ss", f"{t0:.3f}", "-t", f"{max(dur, 1/120):.3f}", "-i", v,
          "-vf", f"scale={SCALE_W}:{SCALE_H}:force_original_aspect_ratio=disable",
          "-f", "image2pipe", "-vcodec", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True, timeout=300)
    n = len(r.stdout) // (SCALE_W * SCALE_H * 3)
    if n == 0:
        return []
    arr = np.frombuffer(r.stdout, dtype=np.uint8)[: n * SCALE_W * SCALE_H * 3]
    arr = arr.reshape(n, SCALE_H, SCALE_W, 3)
    if n <= max_frames:
        return [a for a in arr]
    idx = sorted(set(np.linspace(0, n - 1, max_frames).round().astype(int)))
    return [arr[i] for i in idx]


def probe_shot(frames: list[np.ndarray]) -> dict:
    if len(frames) < 3:
        g = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames] if frames else []
        flat = float((frames[-1] == frames[-1][0, 0]).all(axis=2).mean()) if frames else 0.0
        return {"n_frames": len(frames), "flat_share": round(flat, 3)}
    g = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frames]

    # line_boil：Canny 边缘图帧间 IoU 波动（手书逐帧边缘每年都在抖）
    edges = [cv2.Canny(x.astype(np.uint8), 80, 160) > 0 for x in g]
    ious = [float((edges[i] & edges[i + 1]).sum() / max((edges[i] | edges[i + 1]).sum(), 1))
            for i in range(len(edges) - 1)]
    line_boil = round(float(np.std(ious)), 4) if len(ious) > 2 else 0.0
    edge_stability = round(float(np.mean(ious)), 3)

    # 光流场序列
    flows = []
    for a, b in zip(g[:-1], g[1:]):
        fl = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        flows.append(fl)
    F = np.stack(flows)                      # (t, H, W, 2)
    mag = np.hypot(F[..., 0], F[..., 1])     # (t, H, W)

    # rigid_blocks：运动块的光流方向与全局主方向一致率（平移/刚体→高，多向形变→低）
    bs = SCALE_H // 8
    bw = SCALE_W // 8
    consistent = []
    for t in range(F.shape[0]):
        m_all = mag[t]
        if m_all.mean() < 0.15:  # 整帧几乎静止，不采样本帧
            continue
        # 全局主方向：运动像素光流方向的中位数
        sel = m_all > 0.3
        if sel.sum() < 50:
            continue
        ang = np.arctan2(F[t][..., 1][sel], F[t][..., 0][sel])
        main_ang = float(np.median(ang))
        for by in range(8):
            for bx in range(8):
                blk_m = m_all[by * bs:(by + 1) * bs, bx * bw:(bx + 1) * bw]
                if blk_m.mean() <= 0.3:
                    continue  # 只看运动块
                ba = np.arctan2(F[t, by * bs:(by + 1) * bs, bx * bw:(bx + 1) * bw, 1][blk_m > 0.3],
                                F[t, by * bs:(by + 1) * bs, bx * bw:(bx + 1) * bw, 0][blk_m > 0.3])
                if len(ba) == 0:
                    continue
                d = np.abs(np.angle(np.exp(1j * (ba - main_ang))))
                consistent.append(float((d < np.pi / 6).mean()))  # ±30° 内算一致
    rigid_consistency = round(float(np.mean(consistent)), 3) if consistent else 0.0

    # parallax_split：上半 vs 下半平均流幅差比（2.5D 视差/投影分层）
    top, bot = mag[:, :SCALE_H // 2].mean(), mag[:, SCALE_H // 2:].mean()
    parallax_split = round(float(abs(top - bot) / max(top + bot, 1e-6) * 2), 3)

    # flow_diverge：散度非零占比（透视膨胀/收缩 = 三维摄像机推拉证据）
    divs = []
    for t in range(mag.shape[0]):
        dv = np.gradient(mag[t], axis=0) + np.gradient(mag[t], axis=1)
        divs.append(float((np.abs(dv) > 0.05 * mag[t].mean()).mean()))
    flow_diverge = round(float(np.mean(divs)), 3)

    # edge_halo：最大轮廓膨胀环的平均灰度梯度（抠像边缘残留）
    cnts, _ = cv2.findContours((edges[-1].astype(np.uint8)) * 255,
                               cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    halo = 0.0
    if cnts:
        big = max(cnts, key=cv2.contourArea)
        if cv2.contourArea(big) > 400:
            m = np.zeros((SCALE_H, SCALE_W), np.uint8)
            cv2.drawContours(m, [big], -1, 255, -1)
            ring = (cv2.dilate(m, np.ones((5, 5), np.uint8)) > 0) & (m == 0)
            core = m > 0
            if ring.sum() > 50 and core.sum() > 50:
                halo = round(float(abs(g[-1][ring].mean() - g[-1][core].mean())), 1)

    # color_banding：唯一色数/像素数（赛璐璐平涂低、实拍高）
    px = (frames[-1].reshape(-1, 3) // 8).astype(np.int32)
    uniq = len(np.unique(px[:, 0] * 1024 + px[:, 1] * 32 + px[:, 2]))
    color_banding = round(uniq / (SCALE_W * SCALE_H), 4)

    # flat_share：纯色占比（闪白/黑场/纯色遮罩层证据）
    flat = float((frames[-1] == frames[-1][0, 0]).all(axis=2).mean())

    return {"n_frames": len(frames),
            "line_boil": line_boil, "edge_stability": edge_stability,
            "rigid_consistency": rigid_consistency,
            "parallax_split": parallax_split, "flow_diverge": flow_diverge,
            "edge_halo": halo, "color_banding": color_banding,
            "flat_share": round(flat, 3)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--limit", type=int, default=0, help="只探前 N 镜（0=全部）")
    a = ap.parse_args()
    g = json.load(open(a.graph, encoding="utf-8"))
    shots = g["shots"][: a.limit or None]
    out = []
    for s in shots:
        frames = _decode(a.video, s["start"], s["end"] - s["start"])
        pr = probe_shot(frames)
        out.append({**{k: s[k] for k in ("idx", "start", "end", "dur")}, "layers": pr})
        print(f"镜{s['idx']:>3} {s['start']:>7.2f}-{s['end']:>7.2f} "
              f"boil={pr.get('line_boil')} rigid={pr.get('rigid_consistency')} "
              f"parallax={pr.get('parallax_split')} diverge={pr.get('flow_diverge')} "
              f"halo={pr.get('edge_halo')} banding={pr.get('color_banding')} "
              f"flat={pr.get('flat_share')}", flush=True)
    p = Path(a.graph).with_suffix(".layers.json")
    p.write_text(json.dumps({"video": a.video, "shots_layers": out},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    print("层考古图谱:", p)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
