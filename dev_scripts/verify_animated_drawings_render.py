# -*- coding: utf-8 -*-
"""AnimatedDrawings 真实渲染验证：官方测试资产 char1 + zombie 动作 → mp4。

无需 torchserve（跳过涂鸦检测段，直接走"标注 → 骨骼重定向 → 渲染"链路）。
用法（在 external/AnimatedDrawings 目录下）：
    python ../../dev_scripts/verify_animated_drawings_render.py
"""
import os
import sys
import time
from pathlib import Path

import yaml

import numpy as np

# numpy 2.x 兼容：官方代码使用已移除的 np.bool8
if not hasattr(np, "bool8"):
    np.bool8 = np.bool_

# numpy 2.x 兼容：math.* 不再隐式接受单元素数组，包一层标量化
import math as _math  # noqa: E402


def _scalarize(fn):
    def wrapper(*args):
        args = [a.item() if isinstance(a, np.ndarray) and a.size == 1 else a for a in args]
        return fn(*args)
    return wrapper


for _name in ("sqrt", "acos", "asin", "atan2", "cos", "sin"):
    setattr(_math, _name, _scalarize(getattr(_math, _name)))

AD_ROOT = Path(__file__).resolve().parent.parent / "external" / "AnimatedDrawings"
sys.path.insert(0, str(AD_ROOT))

import animated_drawings.render  # noqa: E402

OUT_DIR = AD_ROOT / "results_verify"
OUT_VIDEO = OUT_DIR / "zombie_dance.mp4"


def run():
    OUT_DIR.mkdir(exist_ok=True)
    mvc_cfg = {
        "scene": {
            "ANIMATED_CHARACTERS": [
                {
                    "character_cfg": "tests/test_render_files/char1/char_cfg.yaml",
                    "motion_cfg": "tests/test_render_files/zombie.yaml",
                    "retarget_cfg": "tests/test_render_files/human_zombie.yaml",
                }
            ]
        },
        "controller": {
            "MODE": "video_render",
            "OUTPUT_VIDEO_PATH": str(OUT_VIDEO),
        },
    }
    cfg_fn = OUT_DIR / "mvc_cfg.yaml"
    with open(cfg_fn, "w", encoding="utf-8") as f:
        yaml.dump(mvc_cfg, f)

    os.chdir(AD_ROOT)
    t0 = time.time()
    animated_drawings.render.start(str(cfg_fn))
    dt = time.time() - t0

    assert OUT_VIDEO.exists(), f"渲染产物不存在: {OUT_VIDEO}"
    size_kb = OUT_VIDEO.stat().st_size / 1024
    print(f"渲染耗时 = {dt:.2f}s")
    print(f"产物: {OUT_VIDEO} ({size_kb:.0f} KB)")
    assert size_kb > 100, "产物小于 100KB，按项目标准判定内容不可见"
    print("VERIFY OK")


if __name__ == "__main__":
    run()
