"""
RIFE Engine - Frame Interpolation
===================================

封装 external/rife/ 的帧插值能力，提供：
- 2x/4x/8x 帧率提升
- 慢动作生成
- 与 Topaz 的互补策略：RIFE 免费快速作默认，Topaz 高质量作备选

使用方式：
    engine = RifeEngine()
    result = await engine.interpolate("input.mp4", "output.mp4", multiplier=2)
    result = await engine.slomo("input.mp4", "output.mp4", slow_factor=4)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

# 添加 external/rife 到 Python 路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_RIFE_ROOT = _PROJECT_ROOT / "external" / "rife"
if str(_RIFE_ROOT) not in sys.path:
    sys.path.insert(0, str(_RIFE_ROOT))

from ..base import BaseEngine, EngineResult  # noqa: E402


class RifeEngine(BaseEngine):
    """RIFE frame interpolation engine.

    Wraps the RIFE PyTorch implementation for video frame interpolation.
    Supports 2x/4x/8x frame rate multiplication and slow-motion generation.
    """

    name = "rife"

    def __init__(
        self,
        executable_path: Path | str = sys.executable,
        rife_root: Optional[Path] = None,
    ):
        self.rife_root = rife_root or _RIFE_ROOT
        self.inference_script = self.rife_root / "inference_video.py"
        # 使用 python 解释器作为 executable
        super().__init__(executable_path)
        self._verify_rife_installation()

    def _verify_rife_installation(self) -> None:
        """验证 RIFE 安装完整性。"""
        if not self.inference_script.exists():
            logger.warning(
                f"RIFE inference script not found at {self.inference_script}"
            )
        model_dir = self.rife_root / "train_log"
        if not model_dir.exists():
            logger.warning(
                f"RIFE model directory not found at {model_dir}. "
                "Please download pretrained weights."
            )

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】参数推断分发；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        if "multiplier" in kwargs or "fps" in kwargs:
            return await self.interpolate(*args, **kwargs)
        if "slow_factor" in kwargs:
            return await self.slomo(*args, **kwargs)
        return await self.interpolate(*args, **kwargs)

    async def interpolate(
        self,
        input_path: Path | str,
        output_path: Path | str,
        multiplier: int = 2,
        fps: Optional[int] = None,
        fp16: bool = False,
        scale: float = 1.0,
        UHD: bool = False,
        ext: str = "mp4",
    ) -> EngineResult:
        """帧插值：提升视频帧率。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            multiplier: 倍率 (2=2x, 4=4x, 8=8x)
            fps: 指定输出FPS（覆盖multiplier）
            fp16: 使用半精度加速（需Tensor Core显卡）
            scale: 处理缩放（0.5用于4K视频节省显存）
            UHD: 4K视频模式（自动设置scale=0.5）
            ext: 输出格式
        """
        import time

        start_time = time.time()
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            return EngineResult(
                success=False,
                error=f"Input video not found: {input_path}",
            )

        # 计算 exp 参数 (2^exp = multiplier)
        exp = {"2": 1, "4": 2, "8": 3}.get(str(multiplier), 1)

        cmd = [
            str(self.executable_path),
            str(self.inference_script),
            "--video", str(input_path),
            "--output", str(output_path),
            "--exp", str(exp),
            "--scale", str(scale),
            "--ext", ext,
        ]

        if fps:
            cmd.extend(["--fps", str(fps)])
        if fp16:
            cmd.append("--fp16")
        if UHD:
            cmd.append("--UHD")

        logger.info(f"[RIFE] Interpolating {input_path} -> {output_path} ({multiplier}x)")

        # 使用 asyncio.to_thread 避免阻塞事件循环（_run_subprocess 返回 4 元组）
        rc, _stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200, cwd=self.rife_root
        )

        duration = time.time() - start_time

        if rc != 0:
            logger.error(f"[RIFE] Failed with rc={rc}: {stderr[:500]}")
            return EngineResult(
                success=False,
                error=f"RIFE interpolation failed: {stderr[:1000]}",
                duration_seconds=duration,
            )

        if not output_path.exists():
            return EngineResult(
                success=False,
                error="Output file was not generated",
                duration_seconds=duration,
            )

        logger.success(f"[RIFE] Completed in {duration:.1f}s: {output_path}")
        return EngineResult(
            success=True,
            output_path=output_path,
            metadata={
                "multiplier": multiplier,
                "fps_target": fps,
                "fp16": fp16,
                "UHD": UHD,
                "input_duration": self._get_video_duration(input_path),
            },
            duration_seconds=duration,
        )

    async def slomo(
        self,
        input_path: Path | str,
        output_path: Path | str,
        slow_factor: float = 4.0,
        **kwargs,
    ) -> EngineResult:
        """生成慢动作视频。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            slow_factor: 慢放倍数 (2.0=0.5x速度, 4.0=0.25x速度)
        """
        # slow_factor = 输出帧率 / 输入帧率
        # 要达到 slow_factor 的慢放，需要 multiplier = slow_factor 的帧插值
        # 同时设置输出FPS为原始FPS，这样播放时就是慢动作
        multiplier = int(slow_factor)
        if multiplier < 2:
            multiplier = 2

        # 先获取原始FPS
        original_fps = self._get_video_fps(input_path)
        if original_fps:
            target_fps = int(original_fps)  # 保持原始FPS播放 = 慢动作
        else:
            target_fps = None

        return await self.interpolate(
            input_path, output_path,
            multiplier=multiplier,
            fps=target_fps,
            **kwargs,
        )

    @staticmethod
    def _get_video_duration(video_path: Path) -> float:
        """获取视频时长（秒）。"""
        try:
            import cv2
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            return frames / fps if fps > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _get_video_fps(video_path: Path) -> Optional[float]:
        """获取视频帧率。"""
        try:
            import cv2
            cap = cv2.VideoCapture(str(video_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            return fps if fps > 0 else None
        except Exception:
            return None

    def get_info(self) -> dict:
        """返回引擎信息。"""
        return {
            "name": self.name,
            "rife_root": str(self.rife_root),
            "inference_script": str(self.inference_script),
            "script_exists": self.inference_script.exists(),
            "model_dir_exists": (self.rife_root / "train_log").exists(),
            "capabilities": ["interpolate", "slomo"],
        }