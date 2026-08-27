# -*- coding: utf-8 -*-
"""MatAnyone2 GPU 真实推理验证：走官方 process_video() 链路，记录显存峰值 + alpha 质量。

用法（在 external/matanyone2 目录下）：
    python ../../dev_scripts/verify_matanyone2_gpu.py
"""
import glob
import os
import sys
import time

import cv2
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "external", "matanyone2"))

from matanyone2.inference.inference_core import InferenceCore
from matanyone2.utils.get_default_model import get_matanyone2_model
from matanyone2.utils.device import get_default_device

CKPT = "pretrained_models/matanyone2.pth"
VIDEO = "inputs/video/test-sample1"
MASK = "inputs/mask/test-sample1.png"
OUT = "results_verify"


def run():
    device = get_default_device()
    assert device.type == "cuda", f"未检测到 CUDA 设备: {device}"
    print(f"device = {device} ({torch.cuda.get_device_name(0)})")

    t0 = time.time()
    model = get_matanyone2_model(CKPT, device)
    processor = InferenceCore(model, cfg=model.cfg)
    print(f"模型加载耗时 = {time.time() - t0:.2f}s")

    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    fgr_path, pha_path = processor.process_video(
        input_path=VIDEO,
        mask_path=MASK,
        output_path=OUT,
        n_warmup=10,
        r_erode=10,
        r_dilate=10,
        save_image=True,
    )
    dt = time.time() - t0
    peak = torch.cuda.max_memory_allocated() / 1024**2

    # 用产出的 pha 帧序列校验 alpha 质量
    phas = sorted(glob.glob(os.path.join(OUT, "test-sample1", "pha", "*.png")))
    assert len(phas) == 30, f"pha 帧数异常: {len(phas)}"
    means = [cv2.imread(f, 0).mean() / 255.0 for f in phas]
    print(f"推理+写出耗时 = {dt:.2f}s (30 有效帧, {30 / dt:.2f} FPS)")
    print(f"显存峰值 = {peak:.0f} MiB")
    print(f"alpha 平均覆盖率: 首帧={means[0]:.3f} 末帧={means[-1]:.3f} 最低={min(means):.3f}")
    print(f"产物: {fgr_path} / {pha_path}")

    assert peak < 8 * 1024, "显存峰值超出 8GB 边界"
    assert 0.01 < min(means) < 0.9, "alpha 覆盖率异常（疑似全黑/全白）"
    print("VERIFY OK")


if __name__ == "__main__":
    run()
