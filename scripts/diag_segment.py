"""诊断长视频分段处理失败的原因。

手动测试：
1. 从长视频切出前 500 帧
2. 检查段视频是否正常
3. 用显著性分析找 prompt
4. 用 SAM2Engine 处理段
5. 检查结果
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

FFMPEG = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE = r"C:\ffmpeg\bin\ffprobe.exe"

SRC = PROJECT_ROOT / "data" / "real_amv_test" / "DL_黑岩射手_r924_BV1JW411s7GV.mp4"
TEMP = Path(r"D:\AE-Work\diag_tmp")
TEMP.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 70)
    print("诊断长视频分段处理")
    print("=" * 70)

    # 1. 检查源视频
    print(f"\n源视频: {SRC.name}")
    if not SRC.exists():
        print("ERROR: 源视频不存在")
        return

    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames,width,height,codec_name,r_frame_rate",
         "-of", "default=noprint_wrappers=1", str(SRC)],
        capture_output=True, text=True,
    )
    print(f"ffprobe: {r.stdout.strip()}")

    # 2. 切出前 500 帧
    seg = TEMP / "seg0_500frames.mp4"
    print(f"\n切段: 帧 0-499 → {seg.name}")
    cmd = [
        FFMPEG, "-y",
        "-i", str(SRC),
        "-vf", "select=between(n\\,0\\,499),setpts=PTS-STARTPTS",
        "-af", "aselect=aseq(0),asetpts=PTS-STARTPTS",
        "-vsync", "0",
        str(seg),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(f"  returncode={r.returncode}")
    if r.returncode != 0:
        print(f"  stderr: {r.stderr[:500]}")
    if seg.exists():
        print(f"  文件大小: {seg.stat().st_size / 1024 / 1024:.1f} MB")

    # 检查段视频
    r = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=nb_frames,width,height,codec_name",
         "-of", "default=noprint_wrappers=1", str(seg)],
        capture_output=True, text=True,
    )
    print(f"  段视频 ffprobe: {r.stdout.strip()}")

    # 3. 用 OpenCV 检查段视频能否读取
    cap = cv2.VideoCapture(str(seg))
    frame_count = 0
    first_frame = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_count == 0:
            first_frame = frame
        frame_count += 1
    cap.release()
    print(f"  OpenCV 读取帧数: {frame_count}")
    if first_frame is not None:
        print(f"  首帧 shape: {first_frame.shape}")

    # 4. 显著性分析
    print("\n显著性分析:")
    from saliency_prompt import find_prompts_with_visualization
    vis_png = TEMP / "seg0_saliency.png"
    prompts, _ = find_prompts_with_visualization(seg, vis_png, num_points=3, frame_idx=0)
    if prompts:
        print(f"  找到 {len(prompts)} 个候选点:")
        for i, p in enumerate(prompts):
            print(f"    [{i+1}] x={p['x']}, y={p['y']}, score={p['score']}")
    else:
        print("  未找到候选点！尝试第 30 帧...")
        prompts, _ = find_prompts_with_visualization(seg, vis_png, num_points=3, frame_idx=30)
        if prompts:
            print(f"  第 30 帧找到 {len(prompts)} 个候选点:")
            for i, p in enumerate(prompts):
                print(f"    [{i+1}] x={p['x']}, y={p['y']}, score={p['score']}")
        else:
            print("  第 30 帧也未找到候选点！")
            # 手动指定画面中心点作为 prompt
            h, w = first_frame.shape[:2]
            prompts = [{"type": "positive", "x": w // 2, "y": h // 2}]
            print(f"  使用画面中心点: ({w//2}, {h//2})")

    # 5. SAM2 推理
    print("\nSAM2 推理:")
    import asyncio

    from src.engines.sam2.engine import SAM2Engine

    async def run():
        engine = SAM2Engine()
        mask_dir = TEMP / "seg0_masks"
        mov = TEMP / "seg0.mov"

        if mask_dir.exists():
            import shutil
            shutil.rmtree(mask_dir, ignore_errors=True)

        print(f"  model=small, mode=video, prompts={len(prompts)}点")
        r = await engine.extract_foreground(
            video_path=seg, output_path=mov,
            model_size="small", mode="video",
            prompts=prompts,
        )
        print(f"  success={r.success}")
        print(f"  mask_count={r.metadata.get('mask_count', 0)}")
        print(f"  nonempty_count={r.metadata.get('nonempty_count', 'N/A')}")
        if r.error:
            print(f"  error: {r.error[:500]}")
        if r.success and mask_dir.exists():
            masks = sorted(mask_dir.glob("mask_*.png"))
            print(f"  实际 mask 文件数: {len(masks)}")
            if masks:
                # 检查前 3 个和后 3 个
                sample = masks[:3] + masks[-3:]
                for m in sample:
                    d = np.fromfile(str(m), dtype=np.uint8)
                    img = cv2.imdecode(d, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        nonempty = int((img > 127).sum())
                        print(f"    {m.name}: nonempty_px={nonempty}, max={img.max()}")
                    else:
                        print(f"    {m.name}: NONE")
        return r

    r = asyncio.run(run())
    print(f"\n最终结果: success={r.success}")


if __name__ == "__main__":
    main()
