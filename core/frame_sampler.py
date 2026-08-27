"""core/frame_sampler.py - 真实帧采样统计

通过 ffmpeg/ffprobe 解码视频, 产出亮度/对比度/时序变化等实测统计。
为 AutoQualityEvaluator 提供"真正看过画面"的视觉质量信号。

诊断依据: D1 根因 — self_evolution_engine.py:_evaluate_visual 仅数阶段成功数,
从未解码像素。此模块补上"真实帧解码"这一缺失环节。
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FrameStats:
    """帧采样统计结果"""
    n_sampled: int = 0
    mean_luma: float = 0.0        # [0,1] 全帧平均亮度
    luma_contrast: float = 0.0    # 帧内亮度标准差的均值(越高=纹理越丰富)
    temporal_change: float = 0.0  # 相邻采样帧平均绝对差(越高=动态越强)


def probe_video(path: str) -> dict:
    """ffprobe 读取真实技术参数。

    Args:
        path: 视频文件路径

    Returns:
        dict with keys: width, height, fps, duration, bitrate_kbps, codec, has_audio

    Raises:
        FileNotFoundError: 文件不存在
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", "-show_format", str(p)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True,
    ).stdout
    data = json.loads(out)
    v = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )
    a = next(
        (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
        None,
    )
    num, _, den = (v.get("avg_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den) if float(den or 0) else 0.0
    return {
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": fps,
        "duration": float(data.get("format", {}).get("duration", 0.0)),
        "bitrate_kbps": int(data.get("format", {}).get("bit_rate", 0)) // 1000,
        "codec": v.get("codec_name", ""),
        "has_audio": a is not None,
    }


def sample_frame_stats(
    path: str,
    n_frames: int = 16,
    scale: int = 160,
) -> FrameStats:
    """抽 n_frames 帧解码为灰度 rawvideo, 计算亮度统计与帧间差。

    通过 ffmpeg 将视频缩放至 scale 宽度并转灰度, 均匀采样 n_frames 帧,
    以 rawvideo(gray) 格式输出到 stdout, 用 numpy 解析为像素数组。

    Args:
        path: 视频文件路径
        n_frames: 采样帧数(默认 16)
        scale: 缩放后宽度(默认 160, 高度按比例)

    Returns:
        FrameStats 包含: n_sampled, mean_luma, luma_contrast, temporal_change

    Raises:
        FileNotFoundError: 文件不存在
    """
    import numpy as np

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    # 获取真实时长以计算采样帧率
    dur_out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(p)],
        capture_output=True, text=True, check=True,
    ).stdout
    dur = float(json.loads(dur_out)["format"]["duration"])

    # 构造均匀采样帧率
    fps_filter = f"fps={max(n_frames, 1) / max(dur, 0.1)}"
    cmd = [
        "ffmpeg", "-v", "quiet", "-i", str(p),
        "-vf", f"{fps_filter},scale={scale}:-2,format=gray",
        "-frames:v", str(n_frames), "-f", "rawvideo", "-",
    ]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout

    # gray rawvideo: 每帧 = scale * h 字节, h 从总字节量反推
    h = len(raw) // scale // max(n_frames, 1)
    if h <= 0 or len(raw) < scale * h:
        return FrameStats()

    frames = np.frombuffer(raw[: scale * h * n_frames], dtype=np.uint8)
    frames = frames.reshape(-1, h, scale).astype(np.float32) / 255.0

    return FrameStats(
        n_sampled=len(frames),
        mean_luma=float(frames.mean()),
        luma_contrast=float(frames.std(axis=(1, 2)).mean()),
        temporal_change=float(
            (abs(frames[1:] - frames[:-1]).mean(axis=(1, 2)).mean())
            if len(frames) > 1 else 0.0
        ),
    )
