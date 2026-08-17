"""方案 A 冒烟测试：DL_黑岩_BV1JW 前 100 帧 → auto_frame + anime detector → QC（直接读源视频）。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMP_DIR = OUTPUT_DIR / "smoke_anime"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

WORK_ROOT = Path(r"D:\AE-Work")
VENV_PY = WORK_ROOT / "venv-sam2" / "Scripts" / "python.exe"
INFER_SCRIPT = PROJECT_ROOT / "scripts" / "infer_segment_autoframe_anime.py"
SRC_MP4 = PROJECT_ROOT / "data" / "real_amv_test" / "DL_黑岩射手_r924_BV1JW411s7GV.mp4"
YOLOV8X = WORK_ROOT / "models" / "yolo" / "yolov8x.pt"
SAM2_CKPT = WORK_ROOT / "models" / "sam2" / "sam2.1_hiera_small.pt"
# 为空时由 factory 按 checkpoint 名+sam_variant 自动选正确的 sam2.1/xxx config
MODEL_CFG = ""


def main():
    mask_dir = TEMP_DIR / "masks"
    params_path = TEMP_DIR / "params.json"
    import shutil
    if mask_dir.exists():
        shutil.rmtree(mask_dir, ignore_errors=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    params = {
        "video_path": str(SRC_MP4),
        "start_frame": 0,
        "expected_frames": 100,
        "mask_dir": str(mask_dir),
        "sam2_checkpoint": str(SAM2_CKPT),
        "model_cfg": MODEL_CFG,
        "yolov8x_path": str(YOLOV8X),
        "face_conf": 0.35, "face_expand": 4.0,
        "yolo_conf": 0.05, "max_boxes_per_frame": 10,
        "sam_variant": "small",
    }
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
    ok_marker = str(params_path) + ".ok"
    for m in [ok_marker, str(params_path) + ".fail"]:
        if os.path.exists(m):
            try:
                os.remove(m)
            except Exception:
                pass
    print(f">>> infer {SRC_MP4.name} frames [0:100]... (SAM2 small + anime face + YOLO fallback)")
    print(f"    SAM2_CKPT exists: {SAM2_CKPT.exists()}")
    print(f"    YOLOV8X exists: {YOLOV8X.exists()}")
    print(f"    SRC_MP4 exists: {SRC_MP4.exists()}")
    t0 = time.time()
    p = subprocess.run(
        [str(VENV_PY), str(INFER_SCRIPT), str(params_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=7200, cwd=str(PROJECT_ROOT),
    )
    dt = time.time() - t0
    print(f"    rc={p.returncode} dt={dt:.1f}s")
    if p.stderr:
        print("    STDERR (tail 3000):")
        for line in p.stderr.splitlines()[-80:]:
            print(f"       | {line}")
    # marker
    res = None
    if os.path.exists(ok_marker):
        try:
            with open(ok_marker, "r", encoding="utf-8-sig") as f:
                res = json.load(f)
            print("    RESULT from marker:", json.dumps(res, ensure_ascii=False, indent=2))
        except Exception as e:
            print("    parse marker fail:", e)
    if res is None:
        for line in (p.stdout + "\n" + p.stderr).splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    res = json.loads(line)
                    print("    RESULT parsed:", json.dumps(res, ensure_ascii=False, indent=2))
                except Exception:
                    pass
    # Pixel QC on masks
    masks = sorted(mask_dir.glob("mask_*.png"))
    print(f"\n>>> 实际生成的 mask 数量: {len(masks)}")
    if not masks:
        print("FAIL: 没有生成任何 mask")
        sys.exit(1)
    sample_idx = np.linspace(0, len(masks) - 1, min(20, len(masks)), dtype=int).tolist()
    ratios = []
    ne_frames = 0
    for i in sample_idx:
        pth = masks[i]
        buf = np.fromfile(str(pth), dtype=np.uint8)
        if buf.size == 0:
            r = 0.0
        else:
            img = cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
            if img is None:
                r = 0.0
            else:
                nz = int(np.count_nonzero(img))
                r = nz / (img.shape[0] * img.shape[1])
        ratios.append(round(r, 4))
        if r > 1e-4:
            ne_frames += 1
    avg_r = float(np.mean(ratios)) if ratios else 0.0
    print(f"    抽样 {len(ratios)} 帧 / 非空帧 {ne_frames} / avg_alpha_ratio {avg_r:.4f}")
    print(f"    每帧 alpha 占比: {ratios}")
    qc = {
        "infer_result": res,
        "mask_count": len(masks),
        "sample": len(ratios),
        "nonempty_sample_frames": ne_frames,
        "avg_alpha_ratio": avg_r,
        "per_frame": ratios,
        "dt_sec": dt,
        "fps": len(masks) / max(1e-6, dt),
    }
    with open(TEMP_DIR / "smoke_qc.json", "w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)
    if avg_r < 0.02:
        print(f"\n[FAIL QC] 平均 alpha 占比过低: {avg_r:.4f}，模型未能有效检测")
        sys.exit(2)
    elif ne_frames < int(len(ratios) * 0.5):
        print(f"\n[WARN QC] 非空帧占比过低: {ne_frames}/{len(ratios)}，但至少有一定检出；建议继续观察")
    else:
        print(f"\n[PASS QC] 平均 alpha 占比 {avg_r:.4f}，非空帧 {ne_frames}/{len(ratios)}，方案 A 有效！进入全量阶段。")


if __name__ == "__main__":
    main()
