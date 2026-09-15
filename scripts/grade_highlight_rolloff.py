#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grade_highlight_rolloff.py — 高光过冲回收后级（highlight rolloff post-grade）

根因（2026-09-14 质量审计，见 docs/handoff-2026-09-14-quality-audit-sync.md / 文字线会话）：
    run53 基底母版在若干镜头被推到近死白 —— 实测像素 ≥250 的占比：
        0.5s 14.7% / 22.0s 11.9% / 28.0s 7.5% / 3.3s 5.2% / 19.0s 4.7%
    交付成片观感"脏 / 不好看"的高光部分来自这里（非文字层）。

做法：一条**只压高光、保中间调与黑位、不动色相**的单调曲线（`curves all=`，默认 gentle 档）：
        0 → 0 ,  0.70 → 0.70 ,  0.90 → 0.89 ,  0.97 → 0.955 ,  1.00 → 0.965
    只在 0.7 以上引入极软肩，把 ≥250 的死白拉回可分辨区间。

实测（同 5 个最差帧，before → after；gentle 档）：
        hi%  14.7→0.0  11.9→0.0  7.5→0.0  5.2→0.0  4.7→0.0
        饱和度不变；锐度损失最小（8.5s lap 264→244、28.0s 131→118；
        更钝的 medium 档会分别掉到 225 / 100）。
    对照：`colorlevels=romax=.94` 亦能清零过冲，但会**整体压暗中间调**（较钝），故不采用。

用法:
    python scripts/grade_highlight_rolloff.py <in.mp4> <out.mp4> [--crf 16] [--shoulder soft|strong]

说明：本脚本是**后级**，不改上游 AE 管线（build_master_polish 的 bloom/Glo2 与逐镜 grade）。
可作为 AE 渲染出片后的收尾一步，或对既有成片做一次性回收。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# 只压高光的单调软肩（保 0 / 0.5 中间调不动）。
# gentle 为默认：实测与 medium 同样清零过冲，但**锐度损失约减半**
#（8.5s lap 264→244 vs 225；28.0s 131→118 vs 100）——软肩越靠上、对中间调影响越小。
SHOULDERS = {
    "gentle": "all='0/0 0.7/0.7 0.9/0.89 0.97/0.955 1/0.965'",   # 默认（审计实测采用档）
    "medium": "all='0/0 0.5/0.5 0.75/0.73 0.90/0.86 1/0.94'",
    "strong": "all='0/0 0.5/0.5 0.70/0.67 0.85/0.80 1/0.91'",
}

# 可选：对比自适应锐化（cas）。对**已锐**帧温和（8.5s lap 372→+35%），
# 不像 unsharp 那样把已锐帧放大到 2.3x（易出光晕）；但对近乎无细节的帧无法无中生有。
SHARPEN = {"none": None, "light": 0.4, "medium": 0.8}


def _resolve_existing(raw: str, label: str) -> Path:
    """把 CLI 路径解析为 Path 并校验（拒绝空字节；输入必须已存在）。

    校验后仅作为**参数列表**元素传给 subprocess(不经过 shell)，故无命令注入面。
    """
    if "\x00" in raw:
        raise ValueError(f"{label} 含非法空字节")
    p = Path(raw).expanduser().resolve()
    if label == "输入" and not p.is_file():
        raise ValueError(f"{label} 不是文件: {p}")
    return p


def build_filter_chain(shoulder: str = "gentle", sharpen: str = "none",
                       saturation: float = 1.0) -> str:
    """构造 ffmpeg `-vf` 链路。

    全部成分来自固定枚举 + 数值参数（非任意串拼接），故无注入面。
    """
    if shoulder not in SHOULDERS:
        raise ValueError(f"未知 shoulder: {shoulder}（可选 {sorted(SHOULDERS)}）")
    if sharpen not in SHARPEN:
        raise ValueError(f"未知 sharpen: {sharpen}（可选 {sorted(SHARPEN)}）")
    chain = ["curves=" + SHOULDERS[shoulder]]
    if SHARPEN[sharpen] is not None:
        chain.append(f"cas=strength={SHARPEN[sharpen]}")
    if saturation != 1.0:
        chain.append(f"eq=saturation={saturation}")
    return ",".join(chain)


def apply_highlight_rolloff(
    src,
    dst,
    *,
    shoulder: str = "gentle",
    sharpen: str = "none",
    saturation: float = 1.0,
    crf: int = 16,
    preset: str = "medium",
) -> Path:
    """把 `src` 的高光过冲回收并写到 `dst`（**供管线 import 调用**，等价 CLI）。

    参数经固定枚举校验；ffmpeg 以**参数列表**调用（shell=False），
    路径仅作列表元素、不参与 shell 解析 → 无命令注入面。失败抛 RuntimeError。
    """
    if shoulder not in SHOULDERS:
        raise ValueError(f"未知 shoulder: {shoulder}（可选 {sorted(SHOULDERS)}）")
    if sharpen not in SHARPEN:
        raise ValueError(f"未知 sharpen: {sharpen}（可选 {sorted(SHARPEN)}）")
    s = _resolve_existing(str(src), "输入")
    d = _resolve_existing(str(dst), "输出")
    d.parent.mkdir(parents=True, exist_ok=True)

    vf = build_filter_chain(shoulder, sharpen, saturation)
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(s),
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(int(crf)), "-preset", str(preset), "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        str(d),
    ]
    r = subprocess.run(  # noqa: S603 - 参数列表 + shell=False，无 shell 解析
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 失败: {r.stderr[-800:]}")
    return d


def main() -> int:
    ap = argparse.ArgumentParser(description="高光过冲回收后级 (highlight rolloff)")
    ap.add_argument("input", help="输入视频")
    ap.add_argument("output", help="输出视频")
    ap.add_argument("--crf", type=int, default=16, help="x264 CRF（默认 16，近无损）")
    ap.add_argument("--preset", default="medium", help="x264 preset（默认 medium）")
    ap.add_argument("--shoulder", choices=sorted(SHOULDERS), default="gentle")
    ap.add_argument("--sharpen", choices=sorted(SHARPEN), default="none",
                    help="对比自适应锐化 cas（默认 none；light/medium 供软片候选）")
    ap.add_argument("--saturation", type=float, default=1.0, help="饱和度缩放（默认 1.0）")
    a = ap.parse_args()

    print(f"[grade] shoulder={a.shoulder} sharpen={a.sharpen} sat={a.saturation}\n"
          f"        {build_filter_chain(a.shoulder, a.sharpen, a.saturation)}")
    try:
        dst = apply_highlight_rolloff(
            a.input, a.output, shoulder=a.shoulder, sharpen=a.sharpen,
            saturation=a.saturation, crf=a.crf, preset=a.preset,
        )
    except (ValueError, RuntimeError) as e:
        print(f"[ERR] {e}")
        return 2
    print(f"[OK] {dst} ({dst.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
