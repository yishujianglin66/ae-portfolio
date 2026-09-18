"""
scripts/benchmark_rvm_matting.py
=================================
RVM (Robust Video Matting) 基准脚本 —— 与 SAM2 基线同段同口径对比（科研级真实执行）。

任务口径（对应 09-计划文件/2026-08-14_RVM对比评估报告.md）：
- 基准视频: data/real_amv_test/DL_黑岩射手_r924_BV1NL4y1H7u7.mp4 (1280x720@30fps)
- 帧段: --start 2000, --frames 50（2000~2049，与 WS-5 SAM2 基线 s50_s2000_ki6 同段）
- 模型: external/rvm（vendored）MattingNetwork('mobilenetv3') + rvm_mobilenetv3.pth
- 输入口径: 保持 720p 全分辨率（不 resize），downsample_ratio=0.4 = 官方 auto（min(512/max(w,h),1)）
  原因: (1) 官方 inference.py 对 720p 源默认即此配置; (2) alpha 输出 1280x720 与 SAM2 基线
  mask 分辨率一致 → 指标直接可比; (3) 实测峰值显存仅 ~129MB（RTX 4060 8GB 无压力）。
- 输出: alpha 灰度 PNG + 二值 mask PNG（threshold 默认 0.5，0/255 与 SAM2 保存格式一致）
  + result JSON（逐帧面积占比、多阈值敏感性、耗时）。

帧提取: 用 ffmpeg 按全局帧号精确抽取到 ASCII 临时目录（规避 OpenCV 中文路径问题），
脚本内再用 cv2.imdecode(np.fromfile(...)) 读取（unicode 安全）。

用法:
  py -3.12 scripts/benchmark_rvm_matting.py --start 2000 --frames 50 --outdir <dir>
  # --no-extract 跳过 ffmpeg 抽取（帧已就位时）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

from core.torch_runtime import get_device, infer_ctx

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_VIDEO = PROJECT / "data" / "real_amv_test" / "DL_黑岩射手_r924_BV1NL4y1H7u7.mp4"
DEFAULT_CKPT = PROJECT / "external" / "rvm" / "rvm_mobilenetv3.pth"
FFMPEG = "ffmpeg"


def extract_frames(video: Path, start: int, frames: int, outdir: Path) -> None:
    """ffmpeg 按全局帧号 [start, start+frames) 精确抽取为 PNG（保持原始分辨率）。"""
    outdir.mkdir(parents=True, exist_ok=True)
    end = start + frames - 1
    vf = f"select='between(n,{start},{end})'"
    cmd = [FFMPEG, "-y", "-i", str(video), "-vf", vf, "-vsync", "0",
           "-frame_pts", "1", str(outdir / "f_%05d.png")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed rc={r.returncode}\n{r.stderr[-2000:]}")
    n = len(list(outdir.glob("f_*.png")))
    if n != frames:
        raise RuntimeError(f"ffmpeg extracted {n} frames, expected {frames}")
    print(f"[EXTRACT] {n} frames -> {outdir}")


def imread_unicode(p: Path) -> np.ndarray:
    buf = np.fromfile(str(p), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"cannot decode {p}")
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description="RVM matting benchmark (与 SAM2 基线同段同口径)")
    ap.add_argument("--video", default=str(DEFAULT_VIDEO))
    ap.add_argument("--checkpoint", default=str(DEFAULT_CKPT))
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--frames", type=int, default=50)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="二值 mask 阈值（默认 0.5）；另在 result 中输出 0.1/0.3/0.5 敏感性")
    ap.add_argument("--no-extract", action="store_true", help="帧已就位时跳过 ffmpeg 抽取")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    frame_dir = outdir / "frames"

    # ---- 1. 帧提取 ----
    if not args.no_extract:
        extract_frames(Path(args.video), args.start, args.frames, frame_dir)
    frame_paths = sorted(frame_dir.glob("f_*.png"))
    if len(frame_paths) < args.frames:
        print(f"[WARN] only {len(frame_paths)} frames found, continuing")
    if not frame_paths:
        print("[ERROR] no frames extracted"); return 1

    # ---- 2. 模型 ----
    sys.path.insert(0, str(PROJECT / "external" / "rvm"))
    from model import MattingNetwork  # noqa: E402

    dev = get_device()
    net = MattingNetwork("mobilenetv3").eval().to(dev)
    net.load_state_dict(torch.load(args.checkpoint, map_location=dev, weights_only=True))
    print(f"[MODEL] MattingNetwork(mobilenetv3) on {dev}; "
          f"ckpt={Path(args.checkpoint).name} ({Path(args.checkpoint).stat().st_size} bytes)")

    # ---- 3. 逐帧推理 ----
    rec = [None] * 4
    rows: list[dict] = []
    t_load = time.time()
    frames: list[tuple[int, np.ndarray]] = []
    for i, p in enumerate(frame_paths):
        bgr = imread_unicode(p)                       # HxWx3 BGR uint8
        global_idx = args.start + i
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        src = torch.from_numpy(rgb).float().div(255.0).permute(2, 0, 1)  # 3,H,W
        src = src.unsqueeze(0).unsqueeze(0).to(dev)   # 1,1,3,H,W

        t0 = time.time()
        with infer_ctx(dev):
            fgr, pha, *rec = net(src, *rec, downsample_ratio=0.4)
        dt = time.time() - t0
        pha_np = pha[0, 0, 0].cpu().numpy()           # HxW float [0,1]

        area = {}
        for th in (0.1, 0.3, 0.5):
            area[f"area_{th}"] = float(np.mean(pha_np > th))
        rows.append({"global_frame": global_idx, "infer_s": round(dt, 4), **area})
        frames.append((global_idx, pha_np))
        if (i + 1) % 10 == 0:
            print(f"[INFER] {i+1}/{len(frame_paths)} frames, "
                  f"mean {np.mean([r['infer_s'] for r in rows]):.4f} s/f")

    t_total = time.time() - t_load
    infer_times = [r["infer_s"] for r in rows]
    print(f"[INFER] done {len(rows)} frames | infer mean {np.mean(infer_times):.4f} s/f | "
          f"total(含帧I/O) {t_total:.2f} s")

    # ---- 4. 保存 alpha + 二值 mask（0/255，与 SAM2 保存格式一致）----
    alpha_dir = outdir / "alpha"
    mask_dir = outdir / "mask"
    alpha_dir.mkdir(exist_ok=True)
    mask_dir.mkdir(exist_ok=True)
    for gi, pha in frames:
        a8 = (pha * 255.0).astype(np.uint8)
        cv2.imencode(".png", a8)[1].tofile(str(alpha_dir / f"alpha_{gi:05d}.png"))
        m8 = np.where(pha > args.threshold, 255, 0).astype(np.uint8)
        cv2.imencode(".png", m8)[1].tofile(str(mask_dir / f"mask_{gi:05d}.png"))
    print(f"[SAVE] alpha -> {alpha_dir} ({len(frames)} png) | mask(th={args.threshold}) -> {mask_dir}")

    # ---- 5. result JSON ----
    area_05 = [r["area_0.5"] for r in rows]
    nonempty = [1.0 if v > 0.001 else 0.0 for v in area_05]
    jumps = []
    prev = None
    for r in rows:
        if prev is not None:
            d = abs(r["area_0.5"] - prev["area_0.5"])
            if d > 0.5:
                jumps.append({"frame": r["global_frame"], "delta": round(d, 4)})
        prev = r
    result = {
        "model": "RVM MattingNetwork(mobilenetv3)",
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "video": str(Path(args.video).resolve()),
        "start_frame": args.start,
        "num_frames": len(rows),
        "input": "1280x720 full-res, downsample_ratio=0.4 (official auto min(512/max(w,h),1))",
        "mask_threshold": args.threshold,
        "resolution": f"{pha_np.shape[1]}x{pha_np.shape[0]}",
        "infer_mean_s_per_frame": round(float(np.mean(infer_times)), 4),
        "infer_min_s": round(float(np.min(infer_times)), 4),
        "infer_max_s": round(float(np.max(infer_times)), 4),
        "total_elapsed_s": round(t_total, 2),
        "nonempty_rate": round(float(np.mean(nonempty)), 4),
        "area_mean_pct": round(100.0 * float(np.mean(area_05)), 2),
        "area_min_pct": round(100.0 * float(np.min(area_05)), 2),
        "area_max_pct": round(100.0 * float(np.max(area_05)), 2),
        "area_median_pct": round(100.0 * float(np.median(area_05)), 2),
        "J500_jump_count": len(jumps),
        "J500_jump_frames": jumps,
        "fallback": "N/A - RVM 无 fallback 概念（单模型端到端，无路由/回退 auto_frame）",
        "per_frame": rows,
    }
    out_json = outdir / "result.json"
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "nonempty_rate": result["nonempty_rate"],
        "area_mean_pct": result["area_mean_pct"],
        "J500_jump_count": result["J500_jump_count"],
        "J500_jump_frames": [j["frame"] for j in jumps],
        "infer_mean_s_per_frame": result["infer_mean_s_per_frame"],
        "total_elapsed_s": result["total_elapsed_s"],
        "result_json": str(out_json),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
