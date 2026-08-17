"""三种方案对比测试 v2：在极低检出率视频上测试。

方案A: auto_frame + yolov8x.pt + detect_conf=0.05
方案B: auto_frame + yolov8n.pt + detect_conf=0.05 (baseline)
方案C: video传播模式 + 画面中心点 prompt（无需YOLO检测首帧）
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))

from src.engines.sam2.engine import SAM2Engine

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
YOLO_X = r"D:\AE-Work\models\yolo\yolov8x.pt"
YOLO_N = r"D:\AE-Work\models\yolo\yolov8n.pt"
OUT_BASE = Path(r"D:\AE-Work\approach_test")

# 从扫描结果中选极低检出率的短视频
TEST_STEMS = [
    "BV1os411Z7jg_闪现流AMVBlazing",     # 极低 0%
    "BV1mxmMBWEzG_RGBЧ",                 # 正常（对照组）
]


def get_video_info(video_path: Path) -> dict:
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"fps": fps, "frames": frame_count, "width": w, "height": h}


def count_nonempty_masks(mask_dir: Path) -> tuple[int, int]:
    masks = sorted(mask_dir.glob("mask_*.png"))
    total = len(masks)
    nonempty = 0
    for mf in masks:
        d = np.fromfile(str(mf), dtype=np.uint8)
        m = cv2.imdecode(d, cv2.IMREAD_GRAYSCALE)
        if m is not None and np.sum(m > 127) > 0:
            nonempty += 1
    return nonempty, total


def extract_frame_alpha(mov_path: Path, frame_idx: int) -> float:
    tmp = Path(r"D:\AE-Work\tmp_test_alpha.png")
    cmd = [FFMPEG, "-y", "-i", str(mov_path), "-vf", f"select=eq(n\\,{frame_idx})",
           "-vframes", "1", "-pix_fmt", "rgba", "-f", "image2", str(tmp)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not tmp.exists():
        return -1
    d = np.fromfile(str(tmp), dtype=np.uint8)
    try:
        tmp.unlink(missing_ok=True)
    except PermissionError:
        pass
    f = cv2.imdecode(d, cv2.IMREAD_UNCHANGED)
    if f is None or f.ndim != 3 or f.shape[2] != 4:
        return -1
    a = f[:, :, 3]
    return (a > 127).mean() * 100


async def test_approach(
    engine: SAM2Engine,
    video_path: Path,
    approach_name: str,
    out_dir: Path,
    mode: str = "auto_frame",
    yolo_model: str = YOLO_N,
    detect_conf: float = 0.30,
    prompts: list | None = None,
) -> dict:
    print(f"\n{'='*60}")
    print(f"方案: {approach_name}")
    print(f"  mode={mode}  yolo={Path(yolo_model).name}  conf={detect_conf}  prompts={'有' if prompts else '无'}")

    mov_path = out_dir / f"{approach_name}.mov"
    mask_dir = out_dir / f"{approach_name}_masks"

    if mov_path.exists():
        mov_path.unlink()
    if mask_dir.exists():
        shutil.rmtree(mask_dir, ignore_errors=True)

    t0 = time.time()
    try:
        r = await engine.extract_foreground(
            video_path=video_path,
            output_path=mov_path,
            model_size="base",
            mode=mode,
            detect_class="person",
            detect_conf=detect_conf,
            yolo_model=yolo_model,
            prompts=prompts,
        )
        elapsed = time.time() - t0
        success = r.success
        error = r.error
    except Exception as e:
        elapsed = time.time() - t0
        success = False
        error = str(e)

    mask_nonempty, mask_total = 0, 0
    if mask_dir.exists():
        mask_nonempty, mask_total = count_nonempty_masks(mask_dir)

    alpha_samples = {}
    if mov_path.exists() and mask_total > 0:
        for idx in [0, mask_total // 4, mask_total // 2, mask_total * 3 // 4, mask_total - 1]:
            if idx >= 0 and idx < mask_total:
                fg = extract_frame_alpha(mov_path, idx)
                alpha_samples[idx] = round(fg, 1)

    result = {
        "approach": approach_name,
        "success": success,
        "elapsed": round(elapsed, 0),
        "mask_nonempty": mask_nonempty,
        "mask_total": mask_total,
        "detection_rate": f"{mask_nonempty}/{mask_total}" if mask_total > 0 else "0/0",
        "alpha_samples": alpha_samples,
        "mov_size_mb": round(mov_path.stat().st_size / 1048576, 1) if mov_path.exists() else 0,
        "error": error,
    }
    print(f"  结果: success={success}  遮罩={mask_nonempty}/{mask_total}  耗时={elapsed:.0f}s")
    print(f"  Alpha抽样: {alpha_samples}")
    if error:
        print(f"  错误: {error}")

    return result


async def test_one_video(engine: SAM2Engine, stem: str, src_dir: Path):
    """对单个视频测试三种方案。"""
    video_path = src_dir / f"{stem}.mp4"
    if not video_path.exists():
        print(f"视频不存在: {video_path}")
        return []

    info = get_video_info(video_path)
    print(f"\n{'#'*60}")
    print(f"# 测试视频: {stem}")
    print(f"# 分辨率: {info['width']}x{info['height']}  帧数: {info['frames']}  FPS: {info['fps']:.1f}")
    print(f"{'#'*60}")

    if info["frames"] > 8000:
        print(f"视频过长({info['frames']}帧)，跳过")
        return []

    out_dir = OUT_BASE / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    # 方案A: yolov8x + conf=0.05 + auto_frame
    r = await test_approach(
        engine, video_path, "A_xlarge_conf005", out_dir,
        mode="auto_frame", yolo_model=YOLO_X, detect_conf=0.05,
    )
    results.append(r)

    # 方案B: yolov8n + conf=0.05 + auto_frame
    r = await test_approach(
        engine, video_path, "B_nano_conf005", out_dir,
        mode="auto_frame", yolo_model=YOLO_N, detect_conf=0.05,
    )
    results.append(r)

    # 方案C: video传播模式 + 中心点 prompt
    prompts = [{"type": "positive", "x": info["width"] // 2, "y": info["height"] // 2}]
    r = await test_approach(
        engine, video_path, "C_video_center", out_dir,
        mode="video", yolo_model=YOLO_X, detect_conf=0.05, prompts=prompts,
    )
    results.append(r)

    # 汇总
    print(f"\n{'='*60}")
    print(f"对比汇总: {stem}")
    print(f"{'='*60}")
    print(f"{'方案':<25} {'遮罩检出':<12} {'Alpha抽样':<40} {'耗时':<6}")
    print("-" * 83)
    for r in results:
        alpha_str = str(r["alpha_samples"])
        print(f"{r['approach']:<25} {r['detection_rate']:<12} {alpha_str:<40} {r['elapsed']:<6.0f}s")

    return results


async def main():
    engine = SAM2Engine()
    src_dir = PROJECT_ROOT / "data" / "real_amv_test"

    all_results = {}
    for stem in TEST_STEMS:
        results = await test_one_video(engine, stem, src_dir)
        all_results[stem] = results

    # 最终汇总
    print(f"\n{'#'*60}")
    print("# 最终对比汇总")
    print(f"{'#'*60}")
    for stem, results in all_results.items():
        print(f"\n{stem}:")
        for r in results:
            alpha_avg = np.mean(list(r["alpha_samples"].values())) if r["alpha_samples"] else 0
            print(f"  {r['approach']:<25}  遮罩={r['detection_rate']:<10}  "
                  f"平均Alpha={alpha_avg:5.1f}%  耗时={r['elapsed']:.0f}s")

    # 保存
    out_file = OUT_BASE / "comparison_results.json"
    out_file.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果: {out_file}")


asyncio.run(main())
