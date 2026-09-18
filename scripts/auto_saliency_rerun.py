"""自动用显著性 prompt 重跑 0% 检出率的视频。

策略：
1. 读取 batch_rerun_yolov8x.py 的结果文件
2. 筛选 detection_rate < 0.1 的视频
3. 对每个视频用 saliency_prompt.py 找到候选点
4. 用 SAM2 video 传播模式重跑
5. 输出最终汇总报告

用法:
    python auto_saliency_rerun.py
    python auto_saliency_rerun.py --threshold 0.1  # 检出率阈值
"""
from __future__ import annotations

import argparse
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


def get_frame_count(mov: Path) -> int:
    import subprocess
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(mov)],
        capture_output=True, text=True,
    )
    try:
        return int(r.stdout.strip())
    except ValueError:
        return 0


def quick_alpha_check(mov: Path, step: int = 200) -> float:
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


async def rerun_with_saliency(
    engine: SAM2Engine,
    stem: str,
    num_points: int = 3,
) -> dict:
    """用显著性 prompt 重跑单个视频。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    mov = out_dir / f"{stem}_transparent.mov"

    if not src.exists():
        return {"stem": stem, "success": False, "error": f"源视频不存在: {src}"}

    # 1. 生成显著性 prompt
    vis_png = VIS_DIR / f"{stem}_saliency.png"
    prompts, _ = find_prompts_with_visualization(src, vis_png, num_points=num_points)

    if not prompts:
        return {"stem": stem, "success": False, "error": "显著性检测未找到候选点"}

    print("  显著性 prompt:")
    for i, p in enumerate(prompts):
        print(f"    [{i+1}] x={p['x']}, y={p['y']}, score={p['score']}")

    # 2. 删除旧成品
    if mov.exists():
        mov.unlink()
    for sub in list(out_dir.iterdir()) if out_dir.exists() else []:
        if sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)

    # 3. 调用 SAM2 video 传播模式
    t0 = time.time()
    try:
        r = await engine.extract_foreground(
            video_path=src, output_path=mov,
            model_size="base", mode="video",
            prompts=prompts,
        )
        elapsed = round(time.time() - t0, 0)
        success = r.success
        error = r.error
        mask_count = r.metadata.get("mask_count", 0)
    except Exception as e:
        elapsed = round(time.time() - t0, 0)
        success = False
        error = str(e)
        mask_count = 0

    # 4. 验证检出率
    detection_rate = 0.0
    if success and mov.exists():
        detection_rate = quick_alpha_check(mov)

    return {
        "stem": stem,
        "success": success,
        "elapsed": elapsed,
        "mask_count": mask_count,
        "detection_rate": round(detection_rate, 3),
        "prompts": prompts,
        "error": error,
        "vis_png": str(vis_png),
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.1,
                        help="检出率阈值，低于此值的视频将重跑（默认 0.1）")
    parser.add_argument("--num-points", type=int, default=3,
                        help="每个视频生成的显著性 prompt 数量（默认 3）")
    parser.add_argument("--results-file", type=str,
                        default=r"D:\AE-Work\rerun_results.json",
                        help="batch_rerun_yolov8x.py 的结果文件路径")
    args = parser.parse_args()

    print("=" * 70)
    print("显著性 prompt 自动重跑工具")
    print("=" * 70)
    print(f"检出率阈值: <{args.threshold:.0%}")
    print(f"每视频 prompt 数: {args.num_points}")
    print()

    # 1. 读取 batch_rerun_yolov8x.py 结果
    results_file = Path(args.results_file)
    if not results_file.exists():
        print(f"结果文件不存在: {results_file}")
        print("请先运行 batch_rerun_yolov8x.py")
        return

    prev_results = json.loads(results_file.read_text(encoding="utf-8"))
    print(f"读取到 {len(prev_results)} 个视频的上一轮结果")

    # 2. 筛选低检出率视频
    low_detection = [r for r in prev_results if r.get("detection_rate", 0) < args.threshold]
    print(f"其中 {len(low_detection)} 个视频检出率 < {args.threshold:.0%}，将用显著性 prompt 重跑:")
    for r in low_detection:
        print(f"  - {r['stem'][:60]}  检出率={r.get('detection_rate', 0):.0%}")

    if not low_detection:
        print("没有需要重跑的视频!")
        return

    print()
    print("=" * 70)
    print(f"开始显著性 prompt 重跑（{len(low_detection)} 个视频）")
    print("=" * 70)

    engine = SAM2Engine()
    new_results = []

    for i, prev in enumerate(low_detection):
        stem = prev["stem"]
        print(f"\n[{i+1}/{len(low_detection)}] {stem}")
        print(f"  上轮检出率: {prev.get('detection_rate', 0):.0%}")

        r = await rerun_with_saliency(engine, stem, num_points=args.num_points)
        new_results.append(r)

        print(f"  → success={r['success']}  检出率={r['detection_rate']:.0%}  "
              f"遮罩={r['mask_count']}  耗时={r['elapsed']:.0f}s")

    # 3. 汇总
    print()
    print("=" * 70)
    print("显著性 prompt 重跑汇总")
    print("=" * 70)
    print(f"{'视频':<50} {'检出率':<10} {'遮罩':<8} {'耗时':<6}")
    print("-" * 78)
    for r in new_results:
        print(f"{r['stem'][:50]:<50} {r['detection_rate']:<10.0%} "
              f"{r['mask_count']:<8} {r['elapsed']:<6.0f}s")

    # 4. 保存结果
    out_file = Path(r"D:\AE-Work\saliency_rerun_results.json")
    out_file.write_text(json.dumps(new_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细结果: {out_file}")
    print(f"可视化图: {VIS_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
