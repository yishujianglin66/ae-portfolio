"""
Frame Interpolator — 帧插值引擎
================================
设计上参考 RIFE (Real-Time Intermediate Flow Estimation) 开源项目，
但本模块**未内置** RIFE 的 IFNet 原始架构，无法加载官方权重做真实光流
推理。因此 RIFE 路径仅在真实权重可用时才启用；否则诚实降级到真实可用的
光流插值（OpenCV Farneback）或帧混合插值，绝不使用随机权重网络冒充
'AI 补帧'。

核心能力:
- 帧率转换 / 慢动作生成
- 光流插值 (OpenCV Farneback，真实可用，默认)
- 帧混合插值 (CPU 回退)
- RIFE 路径（实验性，需真实权重可用）
- 适配 PR/AE 时间重映射

依赖:
    pip install opencv-python numpy
    # RIFE 权重可选：AEKV_RIFE_WEIGHTS 指向真实 .pth 文件

用法:
    interpolator = FrameInterpolator()
    interpolator.interpolate("input.mp4", "output.mp4", factor=2)
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
class InterpolationMethod(Enum):
    RIFE = "rife"
    LINEAR = "linear"
    BLEND = "blend"
    OPTICAL_FLOW = "optical_flow"


@dataclass
class InterpolationResult:
    """插值结果"""
    input_path: str
    output_path: str
    original_fps: float
    target_fps: float
    factor: float
    original_frames: int
    output_frames: int
    duration: float
    method: str
    render_time: float
    degraded_reason: str = ""


@dataclass
class SlowMotionConfig:
    """慢动作配置"""
    source_fps: float
    target_fps: float = 60.0
    slow_factor: float = 2.0
    quality: str = "high"         # "draft", "medium", "high"
    preserve_audio: bool = True


# ================================================================
#  RIFE 帧插值引擎
# ================================================================
class FrameInterpolator:
    """帧插值器。

    默认使用真实可用的光流插值（OpenCV Farneback）。RIFE 路径为实验性
    能力，仅在真实权重可用时启用；否则诚实降级到 blend/optical_flow，
    并在结果中标记降级原因，绝不使用随机权重冒充 AI 补帧。
    """

    # RIFE 模型权重 URL（官方发布）
    RIFE_MODEL_URLS = {
        "v4.6": "https://github.com/hzwer/Practical-RIFE/releases/download/v4.6/rife_v4.6.pth",
        "v4.15": "https://github.com/hzwer/Practical-RIFE/releases/download/v4.15/rife_v4.15.pth",
    }

    def __init__(
        self,
        method: InterpolationMethod = InterpolationMethod.OPTICAL_FLOW,
        model_version: str = "v4.15",
        device: str = "auto",
        tile_size: int = 512,
    ):
        self.method = method
        self.model_version = model_version
        self.device = device
        self.tile_size = tile_size
        self._model = None
        self._degraded_reason: Optional[str] = None
        self._rife_available = self._check_rife()
        self._load_rife_model()

    @staticmethod
    def _find_rife_weights() -> Optional[Path]:
        override = os.environ.get("AEKV_RIFE_WEIGHTS")
        if override:
            p = Path(override)
            if p.exists():
                return p
        candidates = [
            Path(__file__).parent.parent / "models" / "rife" / "latest.pth",
            Path.home() / ".cache" / "rife" / "latest.pth",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    @staticmethod
    def _check_rife() -> bool:
        try:
            import torch
        except ImportError:
            return False
        return FrameInterpolator._find_rife_weights() is not None

    def _load_rife_model(self):
        """仅加载真实 RIFE 权重。

        本模块未内置 RIFE 的 IFNet 原始架构，无法加载官方 .pth 权重做真实
        光流推理。因此不构造随机权重网络冒充 AI 补帧。返回 None 表示 RIFE
        不可用，上游将诚实降级到 blend/optical_flow。
        """
        if self._model is not None:
            return self._model
        if not self._rife_available:
            self._degraded_reason = "rife_backend_or_weights_unavailable"
            return None
        weights_path = self._find_rife_weights()
        if weights_path is None:
            self._degraded_reason = "rife_weights_not_found"
            self._rife_available = False
            return None
        # 真实权重存在，但官方 RIFE IFNet 架构未内置，无法安全加载推理。
        self._degraded_reason = "rife_architecture_not_available"
        self._rife_available = False
        return None

    def interpolate(
        self,
        input_path: str,
        output_path: str,
        factor: float = 2.0,
        target_fps: Optional[float] = None,
    ) -> InterpolationResult:
        """
        视频帧插值/慢动作生成。

        Args:
            input_path: 输入视频路径
            output_path: 输出路径
            factor: 倍率 (2=2x慢动作, 4=4x)
            target_fps: 目标帧率 (可选，优先级高于factor)

        Returns:
            InterpolationResult
        """
        import cv2
        import numpy as np
        import time

        start_time = time.time()

        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {input_path}")

        original_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        out_fps = target_fps or original_fps * factor
        effective_factor = out_fps / original_fps

        # 读取所有帧
        frames = []
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
        cap.release()

        if len(frames) < 2:
            return InterpolationResult(
                input_path=input_path,
                output_path=output_path,
                original_fps=original_fps,
                target_fps=out_fps,
                factor=1.0,
                original_frames=len(frames),
                output_frames=len(frames),
                duration=len(frames) / original_fps,
                method="none",
                render_time=0,
            )

        # 选择插值方法：RIFE 仅在真实权重可用时启用，否则诚实降级
        method = self.method
        degraded_reason = ""
        if method == InterpolationMethod.RIFE and not self._rife_available:
            method = InterpolationMethod.OPTICAL_FLOW
            degraded_reason = self._degraded_reason or "rife_weights_unavailable"

        if method == InterpolationMethod.RIFE:
            output_frames = self._interpolate_rife(frames, effective_factor)
        elif method == InterpolationMethod.OPTICAL_FLOW:
            output_frames = self._interpolate_optical_flow(frames, effective_factor)
        elif method == InterpolationMethod.BLEND:
            output_frames = self._interpolate_blend(frames, effective_factor)
        else:
            output_frames = self._interpolate_linear(frames, effective_factor)

        # 写入输出
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, out_fps, (width, height))

        for frame in output_frames:
            out.write(frame)
        out.release()

        render_time = time.time() - start_time

        return InterpolationResult(
            input_path=input_path,
            output_path=output_path,
            original_fps=original_fps,
            target_fps=out_fps,
            factor=round(effective_factor, 2),
            original_frames=len(frames),
            output_frames=len(output_frames),
            duration=len(output_frames) / out_fps,
            method=method.value,
            render_time=round(render_time, 2),
            degraded_reason=degraded_reason,
        )

    def _interpolate_rife(self, frames: list, factor: float) -> list:
        """RIFE 光流插值（仅在真实 RIFE 模型加载成功时调用）。

        若模型不可用（本模块未内置 RIFE 架构，通常不会加载成功），
        诚实降级到帧混合插值，不制造随机光流扭曲。
        """
        import torch
        import numpy as np
        import cv2

        model = self._load_rife_model()
        if model is None:
            return self._interpolate_blend(frames, factor)

        output = []
        h, w = frames[0].shape[:2]

        # 对齐到8的倍数
        pad_h = (8 - h % 8) % 8
        pad_w = (8 - w % 8) % 8

        for i in range(len(frames) - 1):
            output.append(frames[i])

            # 准备输入张量
            f0 = cv2.resize(frames[i], (w, h)).astype(np.float32) / 255.0
            f1 = cv2.resize(frames[i + 1], (w, h)).astype(np.float32) / 255.0

            f0_t = torch.from_numpy(f0).permute(2, 0, 1).unsqueeze(0).to(self._device)
            f1_t = torch.from_numpy(f1).permute(2, 0, 1).unsqueeze(0).to(self._device)

            # 生成中间帧
            num_inter = int(factor) - 1
            for t_idx in range(1, int(factor)):
                t = t_idx / factor
                timestep = torch.tensor([t]).to(self._device)

                with torch.no_grad():
                    flow = model(f0_t, f1_t)
                    # 后向扭曲
                    grid_y, grid_x = torch.meshgrid(
                        torch.arange(h, device=self._device),
                        torch.arange(w, device=self._device),
                        indexing='ij',
                    )

                    grid_x = grid_x.float() + flow[0, 0] * t * w
                    grid_y = grid_y.float() + flow[0, 1] * t * h

                    # 归一化坐标
                    grid_x = 2 * grid_x / (w - 1) - 1
                    grid_y = 2 * grid_y / (h - 1) - 1

                    grid = torch.stack([grid_x, grid_y], dim=-1).unsqueeze(0)

                    warped = torch.nn.functional.grid_sample(
                        f0_t, grid, mode='bilinear', padding_mode='border', align_corners=False
                    )

                    mid_frame = warped[0].permute(1, 2, 0).cpu().numpy()
                    mid_frame = np.clip(mid_frame * 255, 0, 255).astype(np.uint8)

                output.append(mid_frame)

        output.append(frames[-1])
        return output

    def _interpolate_blend(self, frames: list, factor: float) -> list:
        """帧混合插值 (CPU fallback)"""
        import numpy as np
        import cv2

        output = []
        for i in range(len(frames) - 1):
            output.append(frames[i])
            num_inter = int(factor) - 1
            for j in range(1, num_inter + 1):
                alpha = j / factor
                blended = cv2.addWeighted(frames[i], 1 - alpha, frames[i + 1], alpha, 0)
                output.append(blended)
        output.append(frames[-1])
        return output

    def _interpolate_optical_flow(self, frames: list, factor: float) -> list:
        """光流插值 (OpenCV Farneback)"""
        import cv2
        import numpy as np

        output = []
        for i in range(len(frames) - 1):
            output.append(frames[i])
            f0 = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            f1 = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)

            # 计算光流
            flow = cv2.calcOpticalFlowFarneback(f0, f1, None, 0.5, 3, 15, 3, 5, 1.2, 0)

            num_inter = int(factor) - 1
            for j in range(1, num_inter + 1):
                alpha = j / factor
                h, w = f0.shape
                flow_scaled = flow * alpha

                # 后向扭曲
                y, x = np.mgrid[0:h, 0:w].astype(np.float32)
                x_warp = (x + flow_scaled[..., 0]).astype(np.float32)
                y_warp = (y + flow_scaled[..., 1]).astype(np.float32)

                warped = cv2.remap(frames[i], x_warp, y_warp, cv2.INTER_LINEAR)
                output.append(warped)

        output.append(frames[-1])
        return output

    def _interpolate_linear(self, frames: list, factor: float) -> list:
        """简单线性插值"""
        return self._interpolate_blend(frames, factor)

    def create_slow_motion(
        self,
        input_path: str,
        output_path: str,
        config: SlowMotionConfig,
    ) -> InterpolationResult:
        """创建慢动作视频"""
        return self.interpolate(
            input_path=input_path,
            output_path=output_path,
            target_fps=config.target_fps,
        )

    def generate_time_remap_data(
        self,
        clip_duration: float,
        slow_segments: List[Dict[str, float]],  # [{"start": 1.0, "end": 2.0, "speed": 0.5}]
        original_fps: float = 30.0,
    ) -> Dict[str, Any]:
        """
        生成时间重映射关键帧数据 (用于 PR/AE Time Remap)。

        Args:
            clip_duration: 原始素材时长
            slow_segments: 慢动作区域定义
            original_fps: 原始帧率

        Returns:
            AE/PR 兼容的时间重映射关键帧 JSON
        """
        keyframes = []

        # 起始点
        current_source = 0.0
        current_output = 0.0
        keyframes.append({"source_time": 0.0, "output_time": 0.0})

        # 按起始时间排序
        slow_segments.sort(key=lambda s: s["start"])

        for seg in slow_segments:
            seg_start = seg["start"]
            seg_end = seg["end"]
            speed = seg.get("speed", 0.5)

            # 正常速度段
            if seg_start > current_source:
                normal_dur = seg_start - current_source
                current_output += normal_dur
                keyframes.append({
                    "source_time": seg_start,
                    "output_time": current_output,
                    "speed": 1.0,
                })

            # 慢动作段
            slow_dur = seg_end - seg_start
            output_increment = slow_dur / speed
            current_output += output_increment
            current_source = seg_end

            keyframes.append({
                "source_time": current_source,
                "output_time": current_output,
                "speed": speed,
            })

        # 剩余部分
        if current_source < clip_duration:
            remaining = clip_duration - current_source
            current_output += remaining
            keyframes.append({
                "source_time": clip_duration,
                "output_time": current_output,
                "speed": 1.0,
            })

        return {
            "type": "time_remap",
            "original_duration": clip_duration,
            "remapped_duration": current_output,
            "keyframes": keyframes,
        }


__all__ = [
    "FrameInterpolator",
    "InterpolationResult",
    "SlowMotionConfig",
    "InterpolationMethod",
]
