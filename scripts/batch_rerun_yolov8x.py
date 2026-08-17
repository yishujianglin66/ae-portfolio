"""批量重跑所有低检出率视频。

策略：
1. 先扫描全部58个视频（快速采样，每300帧）
2. 检出率<50%的视频用 yolov8x + conf=0.05 + auto_frame 重跑
3. 重跑后检出率仍<30%的视频回退 video 传播模式
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
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"
YOLO_X = r"D:\AE-Work\models\yolo\yolov8x.pt"
YOLO_N = r"D:\AE-Work\models\yolo\yolov8n.pt"

SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")
TMP = Path(r"D:\AE-Work\scan_tmp.png")
RERUN_LIST = Path(r"D:\AE-Work\rerun_progress.json")


def get_frame_count(mov: Path) -> int:
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(mov)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def quick_alpha_check(mov: Path, step: int = 300) -> float:
    """快速检查 MOV 的 alpha 检出率，返回有前景帧的比例。"""
    total = get_frame_count(mov)
    if total == 0:
        return 0.0
    has_fg = 0
    sampled = 0
    for idx in range(0, total, step):
        cmd = [FFMPEG, "-y", "-i", str(mov), "-vf", f"select=eq(n\\,{idx})",
               "-vframes", "1", "-pix_fmt", "rgba", "-f", "image2", str(TMP)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not TMP.exists():
            continue
        try:
            d = np.fromfile(str(TMP), dtype=np.uint8)
        except Exception:
            continue
        if d.size == 0:
            continue
        try:
            TMP.unlink(missing_ok=True)
        except PermissionError:
            pass
        f = cv2.imdecode(d, cv2.IMREAD_UNCHANGED)
        if f is None or f.ndim != 3 or f.shape[2] != 4:
            continue
        sampled += 1
        if (f[:, :, 3] > 127).mean() > 0.001:
            has_fg += 1
    return has_fg / sampled if sampled > 0 else 0.0


def find_mov(stem: str) -> Path | None:
    """在 C盘和D盘输出目录中查找成品 MOV。"""
    for base in [OUT_BASE, Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\output\batch_auto_frame")]:
        mov = base / stem / f"{stem}_transparent.mov"
        if mov.exists():
            return mov
    return None


async def rerun_video(
    engine: SAM2Engine,
    stem: str,
    mode: str = "auto_frame",
    yolo_model: str = YOLO_X,
    detect_conf: float = 0.05,
    prompts: list | None = None,
) -> dict:
    """重跑单个视频。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    mov = out_dir / f"{stem}_transparent.mov"

    # 删除旧成品
    if mov.exists():
        mov.unlink()
    for sub in list(out_dir.iterdir()) if out_dir.exists() else []:
        if sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)

    t0 = time.time()
    try:
        r = await engine.extract_foreground(
            video_path=src, output_path=mov,
            model_size="base", mode=mode,
            detect_class="person", detect_conf=detect_conf,
            yolo_model=yolo_model, prompts=prompts,
        )
        elapsed = time.time() - t0
        success = r.success
        error = r.error
        mask_count = r.metadata.get("mask_count", 0)
    except Exception as e:
        elapsed = time.time() - t0
        success = False
        error = str(e)
        mask_count = 0

    # 验证
    detection_rate = 0.0
    if success and mov.exists():
        detection_rate = quick_alpha_check(mov)

    return {
        "stem": stem,
        "mode": mode,
        "success": success,
        "elapsed": round(elapsed, 0),
        "mask_count": mask_count,
        "detection_rate": round(detection_rate, 3),
        "mov_size_mb": round(mov.stat().st_size / 1048576, 1) if mov.exists() else 0,
        "error": error,
    }


async def main():
    engine = SAM2Engine()

    # Step 1: 扫描全部视频
    print("=" * 70)
    print("Step 1: 扫描全部58个视频的检出率")
    print("=" * 70)

    all_stems = sorted(f.stem for f in SRC_DIR.glob("*.mp4"))
    print(f"共 {len(all_stems)} 个视频")

    need_rerun = []
    for i, stem in enumerate(all_stems):
        mov = find_mov(stem)
        if mov is None:
            print(f"  [{i+1:2d}/{len(all_stems)}] {stem[:50]:52s} 未找到成品")
            need_rerun.append(stem)
            continue
        rate = quick_alpha_check(mov)
        flag = "需重跑" if rate < 0.5 else "OK"
        print(f"  [{i+1:2d}/{len(all_stems)}] {stem[:50]:52s} 检出率={rate:.0%}  {flag}")
        if rate < 0.5:
            need_rerun.append(stem)

    print(f"\n需重跑: {len(need_rerun)} 个视频")

    if not need_rerun:
        print("所有视频检出率正常，无需重跑!")
        return

    # 保存重跑列表
    RERUN_LIST.write_text(json.dumps({
        "need_rerun": need_rerun,
        "total": len(all_stems),
        "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # Step 2: 用 yolov8x + conf=0.05 重跑
    print(f"\n{'='*70}")
    print(f"Step 2: 用 yolov8x + conf=0.05 重跑 {len(need_rerun)} 个视频")
    print(f"{'='*70}")

    results = []
    for i, stem in enumerate(need_rerun):
        print(f"\n[{i+1}/{len(need_rerun)}] {stem}")
        r = await rerun_video(engine, stem, mode="auto_frame", yolo_model=YOLO_X, detect_conf=0.05)
        results.append(r)
        print(f"  → success={r['success']}  检出率={r['detection_rate']:.0%}  "
              f"遮罩={r['mask_count']}  耗时={r['elapsed']:.0f}s")

    # Step 3: 对检出率仍低的视频回退 video 模式
    still_low = [r for r in results if r["detection_rate"] < 0.3]
    if still_low:
        print(f"\n{'='*70}")
        print(f"Step 3: {len(still_low)} 个视频检出率仍<30%，回退 video 传播模式")
        print(f"{'='*70}")

        for i, prev in enumerate(still_low):
            stem = prev["stem"]
            print(f"\n[{i+1}/{len(still_low)}] {stem} (auto_frame检出率={prev['detection_rate']:.0%})")

            # 获取视频尺寸，用中心点作为 prompt
            src = SRC_DIR / f"{stem}.mp4"
            cap = cv2.VideoCapture(str(src))
            ret, frame = cap.read()
            cap.release()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                prompts = [{"type": "positive", "x": w // 2, "y": h // 2}]
            else:
                prompts = None

            r = await rerun_video(engine, stem, mode="video", yolo_model=YOLO_X,
                                  detect_conf=0.05, prompts=prompts)
            r["prev_detection_rate"] = prev["detection_rate"]
            results = [r if x["stem"] == r["stem"] else x for x in results]
            print(f"  → success={r['success']}  检出率={r['detection_rate']:.0%}  "
                  f"(之前={prev['detection_rate']:.0%})  耗时={r['elapsed']:.0f}s")

    # 汇总
    print(f"\n{'='*70}")
    print("重跑汇总")
    print(f"{'='*70}")
    print(f"{'视频':<50} {'模式':<12} {'检出率':<8} {'遮罩':<8} {'耗时':<6}")
    print("-" * 84)
    for r in results:
        print(f"{r['stem'][:50]:<50} {r['mode']:<12} {r['detection_rate']:<8.0%} "
              f"{r['mask_count']:<8} {r['elapsed']:<6.0f}s")

    # 保存结果
    result_file = Path(r"D:\AE-Work\rerun_results.json")
    result_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果: {result_file}")


asyncio.run(main())
