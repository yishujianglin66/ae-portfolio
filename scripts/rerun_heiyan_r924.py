"""重跑黑岩射手_r924的3个视频，detect_conf=0.10。

按源视频从小到大顺序执行，每个完成后自动清理中间帧。
"""
from __future__ import annotations

import asyncio
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))

from src.engines.sam2.engine import SAM2Engine

SRC_DIR = PROJECT_ROOT / "data" / "real_amv_test"
OUT_BASE = Path(r"D:\AE-Work\batch_auto_frame")

# 3个视频，按源文件大小从小到大排序
TARGETS = [
    "DL_黑岩射手_r924_BV1JW411s7GV",
    "DL_黑岩射手_r924_BV1fx411C74e",
    "DL_黑岩射手_r924_BV1NL4y1H7u7",
]


async def rerun_one(stem: str, engine: SAM2Engine) -> dict:
    """重跑单个视频。"""
    src = SRC_DIR / f"{stem}.mp4"
    out_dir = OUT_BASE / stem
    out_mov = out_dir / f"{stem}_transparent.mov"

    # 删除旧成品和遮罩目录
    if out_mov.exists():
        size_mb = out_mov.stat().st_size / 1048576
        out_mov.unlink()
        print(f"  删除旧MOV: {size_mb:.1f}MB")
    for sub in out_dir.iterdir():
        if sub.is_dir():
            shutil.rmtree(sub, ignore_errors=True)
            print(f"  删除目录: {sub.name}")

    print(f"  开始重跑: detect_conf=0.10 ...")
    t0 = time.time()
    r = await engine.extract_foreground(
        video_path=src, output_path=out_mov,
        model_size="base", mode="auto_frame",
        detect_class="person", detect_conf=0.10,
    )
    elapsed = time.time() - t0
    print(f"  完成: success={r.success}  耗时={elapsed:.0f}s  mask_count={r.metadata.get('mask_count', '?')}")
    if r.error:
        print(f"  错误: {r.error}")
    return {
        "stem": stem,
        "success": r.success,
        "elapsed": elapsed,
        "mask_count": r.metadata.get("mask_count", 0),
        "mov_size_mb": out_mov.stat().st_size / 1048576 if out_mov.exists() else 0,
    }


async def main():
    engine = SAM2Engine()
    results = []
    for i, stem in enumerate(TARGETS):
        print(f"\n[{i+1}/{len(TARGETS)}] {stem}")
        try:
            r = await rerun_one(stem, engine)
            results.append(r)
        except Exception as e:
            print(f"  异常: {e}")
            results.append({"stem": stem, "success": False, "error": str(e)})

    print(f"\n{'='*60}")
    print("重跑汇总")
    print(f"{'='*60}")
    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        print(f"  [{status}] {r['stem']}  耗时={r.get('elapsed',0):.0f}s  "
              f"遮罩={r.get('mask_count',0)}  MOV={r.get('mov_size_mb',0):.1f}MB")


asyncio.run(main())
