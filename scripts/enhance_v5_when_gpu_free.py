# -*- coding: utf-8 -*-
"""等 GPU 空闲后对 v5 执行 RIFE 增强 (后台重试, 规避并发 GPU 争抢).

用法: python scripts/enhance_v5_when_gpu_free.py [target.mp4]
默认目标: D:\output_director\solo_pilot\v23\v23_final_full_v5.mp4
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET = (sys.argv[1] if len(sys.argv) > 1
          else r"D:\output_director\solo_pilot\v23\v23_final_full_v5.mp4")


def gpu_free_mb() -> float:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        return float(r.stdout.strip().splitlines()[0])
    except Exception:
        return 99999.0


print(f"等待 GPU 空闲 (<2500MB 使用) 后增强: {TARGET}", flush=True)
waited = 0
while gpu_free_mb() > 2500:
    time.sleep(60)
    waited += 60
    if waited % 300 == 0:
        print(f"  已等待 {waited//60}min, GPU used={gpu_free_mb():.0f}MB", flush=True)
    if waited > 6 * 3600:
        print("超时放弃", flush=True)
        sys.exit(1)
print(f"GPU 空闲 (等待 {waited//60}min), 开始增强", flush=True)

from core.post_enhancer import PostEnhancer  # noqa: E402

pe = PostEnhancer()
t0 = time.time()
r = pe.enhance(TARGET)
print(f"enhance: {time.time()-t0:.0f}s -> success={r.success} "
      f"path={r.output_path} err={r.error[:200]}", flush=True)
