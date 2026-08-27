# -*- coding: utf-8 -*-
"""MuseTalk GPU 核心生成链真实验证（绕开 mmpose/face-parsing 阻塞段）。

链路：真实音频(whisper base)→特征切片→真实半脸裁剪→VAE 编码→UNet 唇形生成→VAE 解码→贴回合成视频。
被绕过的环节（依赖本机不可得）：dwpose 关键点(需 mmcv×torch2.13 不兼容)、face-parse-bisent 融合。
用法（在 external/musetalk 目录下）：
    python ../../dev_scripts/verify_musetalk_gpu.py
"""
import os
import sys
import time

import cv2
import imageio
import numpy as np
import torch

# ffmpeg 注入 PATH（whisper 解码音频需要）
_FFMPEG_DIR = os.path.join(
    os.path.dirname(sys.executable), "..", "Lib", "site-packages", "imageio_ffmpeg", "binaries"
)
os.environ["PATH"] = os.path.abspath(_FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")

MT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "external", "musetalk"))
sys.path.insert(0, MT_ROOT)
os.chdir(MT_ROOT)

from musetalk.utils.utils import load_all_model  # noqa: E402
from musetalk.whisper.audio2feature import Audio2Feature  # noqa: E402

VIDEO = "data/video/yongen.mp4"
AUDIO = "data/audio/yongen.wav"
WHISPER_PT = os.path.join(os.path.expanduser("~"), ".cache", "whisper", "tiny.pt")  # 384 维，匹配 MuseTalk
UNET_CFG = "models/musetalk_ms/musetalk/musetalk.json"
UNET_BIN = "models/musetalk_ms/musetalk/pytorch_model.bin"
OUT_DIR = "results_verify"
MAX_FRAMES = 100


def detect_face_bbox(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])
    # 近似 MuseTalk 半脸裁剪框：眉毛上方 ~ 下巴下方
    x1 = max(0, int(fx - fw * 0.15))
    x2 = min(frame.shape[1], int(fx + fw * 1.15))
    y1 = max(0, int(fy - fh * 0.35))
    y2 = min(frame.shape[0], int(fy + fh * 1.1))
    return (x1, y1, x2, y2)


def run():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    assert device.type == "cuda", "未检测到 CUDA"
    print(f"device = {device} ({torch.cuda.get_device_name(0)}, 总显存 {torch.cuda.get_device_properties(0).total_memory / 1024**2:.0f} MiB)")

    # ---- 1. 加载真实模型（全部 GPU）----
    t0 = time.time()
    vae, unet, pe = load_all_model(
        unet_model_path=UNET_BIN, vae_type="sd-vae", unet_config=UNET_CFG, device=device)
    pe = pe.to(device)
    timesteps = torch.tensor([0], device=device)
    print(f"模型加载耗时 = {time.time() - t0:.1f}s (UNet {UNET_BIN})")

    # ---- 2. 音频 → whisper 特征切片 ----
    t0 = time.time()
    a2f = Audio2Feature(whisper_model_type="tiny", model_path=WHISPER_PT)
    a2f.model.to(device)
    feat = a2f.audio2feat(AUDIO)
    cap = cv2.VideoCapture(VIDEO)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    whisper_chunks = a2f.feature2chunks(feature_array=feat, fps=fps)
    print(f"音频特征提取耗时 = {time.time() - t0:.1f}s, chunks={len(whisper_chunks)}, fps={fps:.1f}")

    # ---- 3. 视频帧 + 半脸裁剪 → VAE latents ----
    frames, bboxes = [], []
    while len(frames) < MAX_FRAMES:
        ok, frame = cap.read()
        if not ok:
            break
        bbox = detect_face_bbox(frame)
        if bbox is None:
            continue
        frames.append(frame)
        bboxes.append(bbox)
    cap.release()
    assert len(frames) >= 30, f"有效帧太少: {len(frames)}"
    print(f"有效帧 = {len(frames)}")

    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    # 逐帧真实编码（与官方一致：每帧各自裁剪）
    input_latent_list = []
    for bbox, frame in zip(bboxes, frames):
        x1, y1, x2, y2 = bbox
        crop = cv2.resize(frame[y1:y2, x1:x2], (256, 256), interpolation=cv2.INTER_LANCZOS4)
        input_latent_list.append(vae.get_latents_for_unet(crop))
    print(f"VAE 编码耗时 = {time.time() - t0:.1f}s")

    # ---- 4. UNet 生成 + VAE 解码（逐帧流式，避免 latent 驻留显存）----
    n = min(len(whisper_chunks), len(frames))
    t0 = time.time()
    res_frames = []
    for i in range(n):
        whisper_t = torch.from_numpy(np.array(whisper_chunks[i])).float().to(device).unsqueeze(0)
        audio_feature_batch = pe(whisper_t)
        latent = input_latent_list[i].to(dtype=unet.model.dtype)
        pred = unet.model(latent, timesteps, encoder_hidden_states=audio_feature_batch).sample
        recon = vae.decode_latents(pred)
        res_frames.extend(recon)
        input_latent_list[i] = None  # 及时释放，防止显存累积
    dt = time.time() - t0
    torch.cuda.synchronize()
    peak = torch.cuda.max_memory_allocated() / 1024**2
    print(f"生成 {len(res_frames)} 帧耗时 = {dt:.1f}s ({len(res_frames) / dt:.2f} FPS), 显存峰值 = {peak:.0f} MiB")

    # ---- 5. 贴回合成 + 输出 ----
    os.makedirs(OUT_DIR, exist_ok=True)
    out_frames = []
    for i, res in enumerate(res_frames[:n]):
        x1, y1, x2, y2 = bboxes[i]
        canvas = frames[i].copy()
        patch = cv2.resize(res.astype(np.uint8), (x2 - x1, y2 - y1))
        # 椭圆羽化遮罩，避免硬边
        mask = np.zeros((y2 - y1, x2 - x1), np.float32)
        cv2.ellipse(mask, ((x2 - x1) // 2, (y2 - y1) // 2),
                    ((x2 - x1) // 2 - 2, (y2 - y1) // 2 - 2), 0, 0, 360, 1, -1)
        mask = cv2.GaussianBlur(mask, (21, 21), 0)[..., None]
        canvas[y1:y2, x1:x2] = (patch * mask + canvas[y1:y2, x1:x2] * (1 - mask)).astype(np.uint8)
        out_frames.append(canvas)

    out_video = os.path.join(OUT_DIR, "yongen_core_lipsync.mp4")
    imageio.mimwrite(out_video, out_frames, fps=fps, quality=7)

    # 嘴部区域帧间变化量（唇动证据）
    mouth_diffs = []
    for i in range(1, len(res_frames[:n])):
        a = res_frames[i - 1][128:, :].astype(np.float32)
        b = res_frames[i][128:, :].astype(np.float32)
        mouth_diffs.append(np.abs(a - b).mean())
    print(f"下半脸帧间平均变化 = {np.mean(mouth_diffs):.2f} (越大说明唇形随音频变化)")

    size_kb = os.path.getsize(out_video) / 1024
    print(f"产物: {out_video} ({size_kb:.0f} KB)")
    assert peak < 8 * 1024, "显存峰值超 8GB"
    assert size_kb > 100, "产物小于 100KB，内容不可见"
    assert np.mean(mouth_diffs) > 1.0, "下半脸无变化，唇同步疑似失效"
    print("VERIFY OK")


if __name__ == "__main__":
    run()
