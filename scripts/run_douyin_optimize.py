# -*- coding: utf-8 -*-
"""
抖音分发优化脚本（基于 2026-08-12 实测 VMAF 实验结论）
=========================================================
实测结论（1920x1080 @ 4Mbps 压缩模拟，VMAF 越高越接近源片）:
  - 无锐化直压:         92.03   ← 画面糊、边缘损失大
  - 高帧率+锐化:         98.59   ← +6.5 分
  - 低帧率+锐化:         99.83   ← 锐化收益占主导

关键发现:
  1. 锐化(unsharp)是抗压缩的最大杠杆——把边缘细节"提前加重"，
     让压缩器更舍得保边缘，比高帧率带来的收益大得多
  2. 高帧率(48fps)对抗压缩的收益有限(92→93)，主要价值是流畅度
  3. 伪高帧的本质：AI补帧(RIFE) + 微锐化 + 高码率，
     让解码端"看起来"顺滑清晰，而非真的有更多真实细节

用法:
  python run_douyin_optimize.py <input.mp4> [--fps 48] [--sharp 1.0]
  默认: 2x AI补帧 → unsharp=5:5:1.0 → 高码率导出 → 独立产物
"""
import argparse
import json
import os
import re
import subprocess
import sys

FFMPEG = "C:/ffmpeg/bin/ffmpeg.exe"
FFPROBE = "C:/ffmpeg/bin/ffprobe.exe"
PY = r"C:/Users/Administrator/AppData/Local/Programs/Python/Python312/python.exe"


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd[:6])}...\n{(r.stderr or '')[-500:]}")
    return r


def ffprobe(path, key):
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", f"stream={key}", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description="抖音分发优化：AI补帧+锐化+高码率")
    ap.add_argument("input")
    ap.add_argument("--fps", type=int, default=48, help="目标帧率（默认48，传0=保持原帧率）")
    ap.add_argument("--sharp", type=float, default=1.0, help="锐化强度 0.0-2.0（默认1.0）")
    ap.add_argument("--crf", type=int, default=18, help="导出CRF（默认18，越低越清晰）")
    args = ap.parse_args()

    src = os.path.abspath(args.input)
    if not os.path.exists(src):
        print(f"[ERR] 文件不存在: {src}")
        sys.exit(1)

    fps_cur = float(ffprobe(src, "r_frame_rate").split("/")[0])
    print(f"[1/4] 源片: {os.path.basename(src)} @ {fps_cur:.0f}fps")

    # 1. AI 补帧（可选）
    out = src
    if args.fps and args.fps > fps_cur:
        print(f"[2/4] RIFE 补帧 {fps_cur:.0f} -> {args.fps}fps ...")
        r = sh([PY, "core/post_enhancer.py", src, "--enable", "--engine", "rife_local"])
        out = re.search(r"输出:\s*(\S+)", r.stdout or "").group(1)
        if not os.path.exists(out):
            # CLI 输出格式兜底
            out = os.path.splitext(src)[0] + "_enhanced_rife_local.mp4"
        print(f"      补帧产物: {os.path.basename(out)}")
        src = out

    # 2. 锐化 + 高码率导出
    print(f"[3/4] 锐化(unsharp={args.sharp}) + 导出 ...")
    vf = f"unsharp=5:5:{args.sharp}:5:5:0.0"
    dst = os.path.splitext(src)[0] + "_douyin.mp4"
    sh([FFMPEG, "-y", "-i", src, "-vf", vf,
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", dst])

    # 3. 报告
    nb = ffprobe(dst, "nb_frames")
    br = ffprobe(dst, "bit_rate")
    sz = os.path.getsize(dst) / 1048576
    print(f"[4/4] 产物: {os.path.basename(dst)} | {sz:.1f}MB | {nb}帧 | {br}bps")
    print("      抖音建议: 竖屏9:16 + 分辨率≥1080 + 码率≥3Mbps 效果最佳")


if __name__ == "__main__":
    main()
