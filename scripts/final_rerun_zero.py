"""最终重跑 0% 检出率视频的优化脚本。

策略：
1. 策略A（快速）：auto_frame + yolov8x + conf=0.01 + detect_class="all"
   - 检测所有类别（不只 person），极低置信度
   - 速度快（10-20 帧/分钟）
2. 策略B（精准）：video + 显著性 prompt + small 模型
   - 用显著性检测找到的 prompt 点
   - small 模型更快（4-6 帧/分钟）
   - 超时 7200s（2小时）
3. 策略C（回退）：video + 显著性 prompt + base 模型
   - 仅对策略B仍 0% 的短视频（<500帧）
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from saliency_prompt import find_prompts_with_visualization
from src.engines.sam2.engine import SAM2Engine

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")
VIS_DIR = Path(r"D:\AE-Work\saliency_vis")
VIS_DIR.mkdir(parents=True, exist_ok=True)

YOLO_X = r"D:\AE-Work\models\yolov8x.pt"


def get_frame_count(video: Path) -> int:
    import subprocess
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def quick_alpha_check(mov: Path, step: int = 100) -> float:
    """快速检查 MOV 的 alpha 检出率。"""
    import subprocess
    total = get_frame_count(mov)
    if total == 0:
        return 0.0
    has_fg = 0
    sampled = 0
    tmp = Path(r"D:\AE-Work\alpha_tmp.png")
    for idx in range(0, total, step):
        cmd = [FFMPEG, "-y", "-i", str(mov), "-vf", f"select=eq(n\\,{idx})",
               "-vframes", "1", "-pix_fmt", "rgba", "-f", "image2", str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not tmp.exists():
            continue
        try:
            d = np.fromfile(str(tmp), dtype=np.uint8)
        except Exception:
            continue
        if d.size == 0:
            continue
        try:
            tmp.unlink(missing_ok=True)
        except PermissionError:
            pass
        f = cv2.imdecode(d, cv2.IMREAD_UNCHANGED)
        if f is None or f.ndim != 3 or f.shape[2] != 4:
            continue
        sampled += 1
        if (f[:, :, 3] > 127).mean() > 0.001:
            has_fg += 1
    return has_fg / sampled if sampled > 0 else 0.0


def read_zero_videos() -> list[str]:
    """读取 0% 检出率视频列表。"""
    f = Path(r"D:\AE-Work\low_detection_videos.json")
    if not f.exists():
        return []
    data = json.loads(f.read_text(encoding="utf-8-sig"))
    stems = []
    for v in data:
        stem = v["Stem"] if isinstance(v, dict) else v
        if stem not in stems:
            stems.append(stem)
    return stems


def get_saliency_prompts(stem: str) -> list[dict]:
    """从显著性分析结果获取 prompt。"""
    f = VIS_DIR / "saliency_prompts.json"
    if not f.exists():
        return []
    data = json.loads(f.read_text(encoding="utf-8"))
    for item in data:
        if item["stem"] == stem:
            return item.get("prompts", [])
    return []


def find_prompts_multi_frame(video: Path, num_points: int = 3) -> list[dict]:
    """多帧显著性分析：尝试首帧、第10帧、第30帧、第60帧。"""
    for frame_idx in [0, 10, 30, 60, 100]:
        prompts, _ = find_prompts_with_visualization(video, VIS_DIR / f"{video.stem}_sal_f{frame_idx}.png", num_points=num_points, frame_idx=frame_idx)
        if prompts:
            print(f"    第 {frame_idx} 帧找到 {len(prompts)} 个候选点")
            return prompts
    return []


async def run_strategy_a(engine: SAM2Engine, stem: str) -> dict:
    """策略A：auto_frame + conf=0.05 + detect_class=all。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    mov = out_dir / f"{stem}_transparent.mov"

    if not src.exists():
        return {"stem": stem, "success": False, "error": "源不存在"}

    # 清理旧成品
    if mov.exists():
        mov.unlink()
    if out_dir.exists():
        for sub in out_dir.iterdir():
            if sub.is_dir():
                shutil.rmtree(sub, ignore_errors=True)

    print("  [策略A] auto_frame + yolov8x + conf=0.05 + detect_class=all")
    t0 = time.time()
    try:
        r = await engine.extract_foreground(
            video_path=src, output_path=mov,
            model_size="base", mode="auto_frame",
            detect_class="all", detect_conf=0.05,
            yolo_model=YOLO_X,
        )
        elapsed = round(time.time() - t0, 0)
        success = r.success
        mask_count = r.metadata.get("mask_count", 0)
    except Exception as e:
        elapsed = round(time.time() - t0, 0)
        success = False
        mask_count = 0

    detection_rate = 0.0
    if success and mov.exists():
        detection_rate = quick_alpha_check(mov)

    return {
        "stem": stem, "strategy": "A", "success": success,
        "elapsed": elapsed, "mask_count": mask_count,
        "detection_rate": round(detection_rate, 3),
    }


async def run_strategy_b(engine: SAM2Engine, stem: str) -> dict:
    """策略B：video + 显著性 prompt + small 模型。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    mov = out_dir / f"{stem}_transparent.mov"

    # 获取显著性 prompt（先从缓存，再多帧分析）
    prompts = get_saliency_prompts(stem)
    if not prompts:
        print("  多帧显著性分析...")
        prompts = find_prompts_multi_frame(src)

    if not prompts:
        return {"stem": stem, "strategy": "B", "success": False, "error": "无显著性候选点"}

    print(f"  [策略B] video + small + 显著性 prompt ({len(prompts)} 点)")
    for i, p in enumerate(prompts):
        print(f"    [{i+1}] x={p['x']}, y={p['y']}")

    # 清理旧成品
    if mov.exists():
        mov.unlink()
    if out_dir.exists():
        for sub in out_dir.iterdir():
            if sub.is_dir():
                shutil.rmtree(sub, ignore_errors=True)

    t0 = time.time()
    try:
        r = await engine.extract_foreground(
            video_path=src, output_path=mov,
            model_size="small", mode="video",
            prompts=prompts,
        )
        elapsed = round(time.time() - t0, 0)
        success = r.success
        mask_count = r.metadata.get("mask_count", 0)
    except Exception as e:
        elapsed = round(time.time() - t0, 0)
        success = False
        mask_count = 0

    detection_rate = 0.0
    if success and mov.exists():
        detection_rate = quick_alpha_check(mov)

    return {
        "stem": stem, "strategy": "B", "success": success,
        "elapsed": elapsed, "mask_count": mask_count,
        "detection_rate": round(detection_rate, 3),
    }


async def main():
    print("=" * 70)
    print("最终重跑 0% 检出率视频（直接走策略B）")
    print("=" * 70)
    print("说明：YOLOv8x (COCO 训练) 对动画帧检测不到任何目标，")
    print("      即使 conf=0.05 + detect_class=all。已验证策略A无效。")
    print("      直接执行策略B：video 传播模式 + 显著性 prompt + small 模型。")

    stems = read_zero_videos()
    print(f"\n共 {len(stems)} 个 0% 视频")

    # 按帧数排序（短的先跑）
    video_info = []
    for stem in stems:
        src = SRC_DIR / f"{stem}.mp4"
        if src.exists():
            frames = get_frame_count(src)
            video_info.append((stem, frames))
    video_info.sort(key=lambda x: x[1])

    print("\n视频按帧数排序:")
    for stem, frames in video_info:
        print(f"  {stem[:50]:<50} {frames:>6} 帧")

    print(f"\n{'='*70}")
    print("策略B：video + small + 显著性 prompt")
    print(f"{'='*70}")

    engine = SAM2Engine()
    results_b = []

    for i, (stem, frames) in enumerate(video_info):
        print(f"\n[{i+1}/{len(video_info)}] {stem[:60]} ({frames} 帧)")
        rb = await run_strategy_b(engine, stem)
        results_b.append(rb)
        print(f"  → success={rb['success']}  检出率={rb['detection_rate']:.0%}  "
              f"遮罩={rb['mask_count']}  耗时={rb['elapsed']:.0f}s")
        if rb.get("error"):
            print(f"    error: {rb['error']}")

    # 最终汇总
    print(f"\n{'='*70}")
    print("最终汇总")
    print(f"{'='*70}")
    print(f"{'视频':<45} {'检出率':<8} {'遮罩':<6} {'耗时':<6}")
    print("-" * 70)
    for r in results_b:
        stem = r["stem"]
        rate = r.get("detection_rate", 0)
        masks = r.get("mask_count", 0)
        elapsed = r.get("elapsed", 0)
        print(f"{stem[:45]:<45} {rate:<8.0%} {masks:<6} {elapsed:<6.0f}s")

    # 保存结果
    out_file = Path(r"D:\AE-Work\final_rerun_results.json")
    out_file.write_text(json.dumps(results_b, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果: {out_file}")

    # 写入完成标记
    Path(r"D:\AE-Work\saliency_rerun_done.marker").write_text("done", encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
