"""批量 auto_frame 分割脚本。

遍历 data/real_amv_test/ 所有 mp4，对每个视频：
1. auto_frame 模式生成遮罩 PNG 序列（YOLO 检测 person + SAM2 单帧分割）
2. 合成 qtrle 透明视频（with Alpha）

特性：
- 断点续传：已存在 transparent.mov 的视频自动跳过
- 容错：单个视频失败不中断批次，记录错误继续下一个
- 进度日志：实时输出进度 + 汇总 JSON

用法:
    python batch_auto_frame.py [--model-size base] [--detect-conf 0.30]
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# 项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))

from src.engines.sam2.engine import SAM2Engine  # noqa: E402

# 输入输出（输出到 D 盘，避免 C 盘空间不足）
INPUT_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUTPUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")
LOG_FILE = OUTPUT_BASE / "batch_log.json"

# C 盘旧输出目录（断点续传检查用）
OLD_OUTPUT_BASE = PROJECT_ROOT / "data" / "output" / "batch_auto_frame"


async def process_one(
    engine: SAM2Engine,
    video_path: Path,
    index: int,
    total: int,
    model_size: str,
    detect_conf: float,
) -> dict:
    """处理单个视频：遮罩 + 透明视频。"""
    stem = video_path.stem
    out_dir = OUTPUT_BASE / stem
    out_dir.mkdir(parents=True, exist_ok=True)
    alpha_path = out_dir / f"{stem}_transparent.mov"

    # 断点续传：D 盘新目录或 C 盘旧目录有透明视频则跳过
    if alpha_path.exists() and alpha_path.stat().st_size > 1000:
        print(f"[{index+1}/{total}] SKIP (D盘已有): {stem}")
        return {"video": stem, "status": "skipped", "alpha_video": str(alpha_path)}

    old_alpha_path = OLD_OUTPUT_BASE / stem / f"{stem}_transparent.mov"
    if old_alpha_path.exists() and old_alpha_path.stat().st_size > 1000:
        print(f"[{index+1}/{total}] SKIP (C盘已有): {stem}")
        return {"video": stem, "status": "skipped", "alpha_video": str(old_alpha_path)}

    start = time.time()
    print(f"\n[{index+1}/{total}] START: {stem}")
    print(f"  video: {video_path.name}")

    result_info: dict = {"video": stem, "status": "unknown", "start": start}

    try:
        # 调用 extract_foreground（内部自动 auto_mask + 合成透明视频）
        fg_result = await engine.extract_foreground(
            video_path=video_path,
            output_path=alpha_path,
            model_size=model_size,
            mode="auto_frame",
            detect_class="person",
            detect_conf=detect_conf,
        )

        duration = round(time.time() - start, 1)

        if fg_result.success:
            # 从 metadata 读取遮罩数（engine 已自动清理 alpha 中间帧）
            mask_count = fg_result.metadata.get("mask_count", 0)
            mask_dir_str = fg_result.metadata.get("mask_dir", "")

            # 清理遮罩目录（PNG 序列，批量处理只需透明视频成品）
            if mask_dir_str:
                try:
                    import shutil
                    shutil.rmtree(mask_dir_str, ignore_errors=True)
                except Exception:
                    pass

            result_info.update({
                "status": "success",
                "mask_count": mask_count,
                "alpha_video": str(fg_result.output_path),
                "alpha_size_mb": round(alpha_path.stat().st_size / 1048576, 1) if alpha_path.exists() else 0,
                "duration": duration,
            })
            print(f"  ✓ DONE: {mask_count} masks, "
                  f"alpha={result_info['alpha_size_mb']}MB, {duration}s (已清理中间帧)")
        else:
            result_info.update({
                "status": "failed",
                "error": (fg_result.error or "")[:500],
                "duration": duration,
            })
            print(f"  ✗ FAILED ({duration}s): {fg_result.error}")

    except Exception as e:
        duration = round(time.time() - start, 1)
        result_info.update({
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)[:400]}",
            "duration": duration,
        })
        print(f"  ✗ ERROR ({duration}s): {e}")

    return result_info


async def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="批量 auto_frame 分割")
    parser.add_argument("--model-size", default="base", help="模型档位 base/large/small/tiny")
    parser.add_argument("--detect-conf", type=float, default=0.30, help="检测置信度")
    parser.add_argument("--limit", type=int, default=0, help="只处理前N个（0=全部）")
    args = parser.parse_args()

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)

    # 扫描视频
    videos = sorted(INPUT_DIR.glob("*.mp4"))
    if args.limit > 0:
        videos = videos[: args.limit]

    total = len(videos)
    print("=" * 70)
    print("批量 auto_frame 分割")
    print(f"  输入: {INPUT_DIR}")
    print(f"  输出: {OUTPUT_BASE}")
    print(f"  视频数: {total}")
    print(f"  模型: {args.model_size} | detect_conf={args.detect_conf}")
    print("  模式: auto_frame (YOLO person + SAM2 单帧分割)")
    print("  输出: 遮罩PNG序列 + qtrle透明视频MOV")
    print("=" * 70)

    # 实例化引擎（只一次）
    print("\n初始化 SAM2Engine...")
    engine = SAM2Engine()
    if engine._sam2 is not True:
        print("✗ SAM2Engine 不可用，请先安装。")
        return 1
    print(f"✓ SAM2Engine 就绪 (venv={engine.executable_path})\n")

    # 批量处理
    results: list[dict] = []
    batch_start = time.time()

    for i, video in enumerate(videos):
        info = await process_one(
            engine, video, i, total, args.model_size, args.detect_conf,
        )
        results.append(info)

        # 实时写日志（断点续传用，磁盘满时不崩溃）
        try:
            LOG_FILE.write_text(
                json.dumps(results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as log_err:
            print(f"  ⚠ 日志写入失败（磁盘空间不足？）: {log_err}")

        # 进度摘要
        done = i + 1
        success = sum(1 for r in results if r["status"] == "success")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] in ("failed", "error"))
        elapsed = round(time.time() - batch_start, 0)
        print(f"  进度: {done}/{total} | ✓{success} ⏭{skipped} ✗{failed} | 已用{elapsed}s")

    # 汇总
    batch_duration = round(time.time() - batch_start, 1)
    success = [r for r in results if r["status"] == "success"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] in ("failed", "error")]

    summary = {
        "total": total,
        "success": len(success),
        "skipped": len(skipped),
        "failed": len(failed),
        "batch_duration_seconds": batch_duration,
        "model_size": args.model_size,
        "detect_conf": args.detect_conf,
        "results": results,
    }

    summary_file = OUTPUT_BASE / "batch_summary.json"
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n" + "=" * 70)
    print("批量处理完成")
    print(f"  总数: {total}")
    print(f"  成功: {len(success)}")
    print(f"  跳过: {len(skipped)}")
    print(f"  失败: {len(failed)}")
    print(f"  总耗时: {batch_duration}s ({round(batch_duration/60, 1)}min)")
    print(f"  汇总报告: {summary_file}")
    if failed:
        print("\n失败列表:")
        for r in failed:
            print(f"  - {r['video']}: {r.get('error', 'unknown')[:100]}")
    print("=" * 70)

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
