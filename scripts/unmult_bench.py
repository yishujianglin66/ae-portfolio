# -*- coding: utf-8 -*-
"""unmult_bench.py — Unmult 分流评测（AE 2026 特性落地验证）

背景（R5 修正报告 §3）：AE 原生 Unmult 特性已确认真实存在。
实测发现本机 AE 25.3x71 已装 Red Giant 免费版 UnMult（matchName="KNSW Unmult"）。
本脚本做**客观评测**，回答"Unmult 与 BiRefNet 的适用边界"：

  测什么：
    1. 黑底素材（光斑/烟）→ Unmult 去底 vs 原图，算"黑区残留率 / 前景保留率"
    2. 白底素材（墨迹）→ 同上（Unmult 同时支持黑白底）
    3. 耗时对比（Unmult 秒级 vs BiRefNet 模型推理）

  产物：
    - tmp/unmult_bench/：测试素材 + 处理结果 PNG
    - reports/unmult_bench.json：客观指标

用法:
  python scripts/unmult_bench.py --gen-only     # 只生成测试素材
  python scripts/unmult_bench.py --analyze      # 分析 AE 处理结果
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

PROJ = Path(__file__).resolve().parent.parent
BENCH = PROJ / "tmp" / "unmult_bench"
AE_OUT = BENCH / "ae_out"
FF = "C:/ffmpeg/bin/ffmpeg.exe"


def gen_black_glow(path: Path, w: int = 640, h: int = 480, nf: int = 48) -> None:
    """黑底光斑素材：黑背景 + 3 个移动径向光斑（橙/白），标准 VFX overlay 形态。"""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, 24, (w, h))
    centers = [(0.2, 0.7, (80, 200, 255)), (0.5, 0.4, (255, 255, 255)),
               (0.8, 0.6, (60, 160, 255))]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for i in range(nf):
        t = i / nf
        frame = np.zeros((h, w, 3), np.float32)
        for cx, cy, col in centers:
            px = (cx + 0.12 * np.sin(2 * np.pi * t)) * w
            py = (cy + 0.10 * np.cos(2 * np.pi * t + 1.1)) * h
            r = 60 + 22 * np.sin(2 * np.pi * t * 1.7)
            d2 = (xx - px) ** 2 + (yy - py) ** 2
            glow = np.exp(-d2 / (2 * r * r))
            for c in range(3):
                frame[:, :, c] += glow * col[c]
        frame = np.clip(frame, 0, 255).astype(np.uint8)
        vw.write(frame)
    vw.release()


def gen_white_ink(path: Path, w: int = 640, h: int = 480, nf: int = 48) -> None:
    """白底墨迹素材：白背景 + 深色扩散斑（验证 Unmult 白底模式）。"""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(str(path), fourcc, 24, (w, h))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rng = np.random.default_rng(7)
    base = rng.random((h // 16, w // 16)).astype(np.float32)
    for i in range(nf):
        t = i / nf
        frame = np.full((h, w, 3), 255.0, np.float32)
        px, py = (0.3 + 0.4 * t) * w, (0.5 + 0.15 * np.sin(4 * np.pi * t)) * h
        r = 70 + 30 * t
        d2 = (xx - px) ** 2 + (yy - py) ** 2
        ink = np.exp(-d2 / (2 * r * r)) * 0.85
        small = cv2.resize(base, (w, h), interpolation=cv2.INTER_LINEAR)
        ink = np.clip(ink + 0.25 * small, 0, 1)
        for c in range(3):
            frame[:, :, c] *= (1.0 - ink)
        vw.write(np.clip(frame, 0, 255).astype(np.uint8))
    vw.release()


def gen_alpha_compare(path: Path) -> None:
    """把 AE 输出的 PNG 序列拼成对比视频（Black 底上看残留）。"""
    seq = sorted(AE_OUT.glob("unmult_*.png"))
    if not seq:
        return
    lst = AE_OUT / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\nduration 0.04\n" for p in seq),
                   encoding="utf-8")
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-vf", "scale=640:480", str(path)], check=False)


def analyze() -> dict:
    """客观指标：黑色背景区（原本应为纯黑）的残留度 + 前景亮度保留。

    Unmult 原理：输出 = 原图 - α*底색，黑底素材处理后在黑背景上应完全消失。
    指标：
      bg_residual  背景区（原图黑/白区）处理后 |值| 均值 → 越接近 0 越好
      fg_keep      前景区（原图亮斑）处理后能量保留比 → 越接近 1 越好
    """
    src_black = BENCH / "test_black_glow.mp4"
    rep: dict = {"samples": {}}
    for tag, src in (("black", src_black), ("white", BENCH / "test_white_ink.mp4")):
        out_png = AE_OUT / f"unmult_{tag}_f20.png"
        if not src.exists():
            continue
        cap = cv2.VideoCapture(str(src))
        cap.set(cv2.CAP_PROP_POS_FRAMES, 20)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            continue
        entry = {"src_exists": True, "out_exists": out_png.exists()}
        if out_png.exists():
            out = cv2.imread(str(out_png), cv2.IMREAD_UNCHANGED)
            g_src = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            # 前景掩码：原图亮度 > 阈值
            fg = g_src > 40
            bg = ~fg
            if out.shape[2] == 4:
                rgb = out[:, :, :3].astype(np.float32)
            else:
                rgb = out.astype(np.float32)
            g_out = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
            entry["bg_residual"] = round(float(g_out[bg].mean()), 2) if bg.any() else None
            entry["fg_keep"] = (round(float(g_out[fg].mean() / max(g_src[fg].mean(), 1e-6)), 4)
                                if fg.any() else None)
            entry["has_alpha"] = out.shape[2] == 4
        rep["samples"][tag] = entry
    return rep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-only", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()

    BENCH.mkdir(parents=True, exist_ok=True)
    AE_OUT.mkdir(parents=True, exist_ok=True)

    if args.analyze:
        rep = analyze()
        out = PROJ / "reports" / "unmult_bench.json"
        out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        print(f"\n→ {out}")
        return 0

    gen_black_glow(BENCH / "test_black_glow.mp4")
    gen_white_ink(BENCH / "test_white_ink.mp4")
    print(f"测试素材已生成: {BENCH}")
    for p in sorted(BENCH.glob("*.mp4")):
        print(f"  {p.name} ({p.stat().st_size/1e3:.0f}KB)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
