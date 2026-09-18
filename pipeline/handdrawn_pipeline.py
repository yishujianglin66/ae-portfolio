"""
pipeline/handdrawn_pipeline.py — 手书动画完整管线
===================================================

手绘风格动画的端到端生产管线:
  1. 关键帧输入 (手绘原画/数字绘画/照片)
  2. 手绘风格化处理 (HanddrawnStyler)
  3. AI 中间帧生成/补全 (RIFE / SCAIL-2)
  4. 线条抖动模拟 (模拟手绘不稳定感)
  5. 后处理 (纸张纹理/铅笔笔触/墨水扩散)
  6. AE 合成输出 / 直接 MP4 输出

管线流程:
    关键帧 → HanddrawnStyler → 风格化关键帧
    → SketchFrameInterpolator → 中间帧补全
    → 后处理 → FFmpeg 编码 → 手书动画 MP4

与现有模块的对接:
  - HanddrawnStyler (core/handdrawn_styler.py): 风格化处理
  - RIFEAdapter (integrations/opensource_integrations.py): 帧插值
  - SCAIL2Adapter (integrations/scail2_adapter.py): 角色动画驱动
  - Hand-drawn ComfyUI workflow: 高质量风格化

用法:
    from pipeline.handdrawn_pipeline import HanddrawnPipeline
    pipeline = HanddrawnPipeline()
    result = pipeline.produce(
        keyframes=["frame_001.png", "frame_002.png", "frame_003.png"],
        output_path="output/handdrawn_anim.mp4",
        style="pencil_sketch",
        fps=24,
    )
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class HanddrawnConfig:
    """手书动画配置"""
    style: str = "pencil_sketch"      # 手绘风格
    fps: int = 24                      # 帧率
    interpolation_factor: int = 4      # 中间帧倍率 (每两关键帧间插 N 帧)
    line_jitter: float = 0.3           # 线条抖动强度 (0~1)
    paper_texture: bool = True         # 纸张纹理
    texture_intensity: float = 0.3     # 纹理强度
    add_sound: bool = False            # 添加铅笔书写音效
    output_format: str = "mp4"         # mp4/gif/frame_sequence


class HanddrawnPipeline:
    """手书动画完整管线

    整合:
    1. HanddrawnStyler — 手绘风格化
    2. RIFE / SCAIL-2 — 中间帧补全
    3. 后处理 — 线条抖动 + 纸张纹理
    4. FFmpeg — 最终编码
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        from core.handdrawn_styler import HanddrawnStyler
        self._styler = HanddrawnStyler(config)

    def produce(
        self,
        keyframes: list[str],
        output_path: str = "output_handdrawn.mp4",
        style: str = "pencil_sketch",
        fps: int = 24,
        interpolation_factor: int = 4,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """端到端手书动画生产

        Args:
            keyframes: 关键帧图像路径列表
            output_path: 输出路径
            style: 手绘风格
            fps: 帧率
            interpolation_factor: 中间帧倍率
            params: 额外参数

        Returns:
            生产结果字典
        """
        if not keyframes:
            return {"status": "error", "message": "No keyframes provided"}

        params = params or {}
        hd_config = HanddrawnConfig(
            style=style,
            fps=fps,
            interpolation_factor=interpolation_factor,
            line_jitter=params.get("line_jitter", 0.3),
            paper_texture=params.get("paper_texture", True),
            texture_intensity=params.get("texture_intensity", 0.3),
        )

        with tempfile.TemporaryDirectory(prefix="handdrawn_") as tmpdir:
            tmpdir = Path(tmpdir)

            # 1. 风格化关键帧
            logger.info("[HanddrawnPipeline] Step 1: Stylizing %d keyframes", len(keyframes))
            stylized_dir = tmpdir / "stylized"
            stylized_dir.mkdir()
            stylized_frames = self._stylize_keyframes(keyframes, stylized_dir, hd_config)

            if not stylized_frames:
                return {"status": "error", "message": "Stylization failed for all keyframes"}

            # 2. 中间帧补全
            logger.info("[HanddrawnPipeline] Step 2: Interpolating frames (factor=%d)", interpolation_factor)
            interpolated_dir = tmpdir / "interpolated"
            interpolated_dir.mkdir()
            all_frames = self._interpolate_frames(stylized_frames, interpolated_dir, hd_config)

            # 3. 后处理 (线条抖动 + 纹理)
            logger.info("[HanddrawnPipeline] Step 3: Post-processing (jitter + texture)")
            final_dir = tmpdir / "final"
            final_dir.mkdir()
            final_frames = self._postprocess_frames(all_frames, final_dir, hd_config)

            # 4. 编码输出
            logger.info("[HanddrawnPipeline] Step 4: Encoding to %s", output_path)
            encode_result = self._encode_output(final_frames, output_path, hd_config)

        return {
            "status": encode_result.get("status", "error"),
            "output_path": output_path,
            "keyframes": len(keyframes),
            "stylized_frames": len(stylized_frames),
            "total_frames": len(final_frames),
            "fps": fps,
            "style": style,
            "duration_sec": len(final_frames) / fps if final_frames else 0,
        }

    def _stylize_keyframes(
        self, keyframes: list[str], output_dir: Path, config: HanddrawnConfig
    ) -> list[str]:
        """风格化关键帧"""
        stylized = []
        for i, kf in enumerate(keyframes):
            out_path = str(output_dir / f"stylized_{i:04d}.png")
            result = self._styler.stylize_image(
                kf, out_path, config.style,
                {"paper_texture": config.paper_texture,
                 "texture_intensity": config.texture_intensity},
            )
            if result.get("status") == "success":
                stylized.append(out_path)
        return stylized

    def _interpolate_frames(
        self, frames: list[str], output_dir: Path, config: HanddrawnConfig
    ) -> list[str]:
        """中间帧补全

        策略:
        1. 优先使用 RIFE (实时帧插值，效果好)
        2. 降级: 使用 Pillow 交叉淡入淡出
        """
        if len(frames) < 2:
            # 只有一帧，复制即可
            if frames:
                shutil.copy2(frames[0], str(output_dir / "frame_0000.png"))
            return sorted(str(p) for p in output_dir.glob("*.png"))

        # 尝试 RIFE
        rife_result = self._interpolate_rife(frames, output_dir, config)
        if rife_result:
            return rife_result

        # 降级: Pillow 交叉淡入淡出
        return self._interpolate_pillow(frames, output_dir, config)

    def _interpolate_rife(self, frames, output_dir, config):
        """使用 RIFE 进行帧插值"""
        try:
            from integrations.opensource_integrations import RIFEAdapter
            rife = RIFEAdapter()
            if not rife.check_available():
                return None

            # RIFE 需要视频输入，先编码为视频
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                temp_video = tmp.name

            # 将关键帧编码为低帧率视频
            self._frames_to_video(frames, temp_video, fps=4)

            # RIFE 插值
            result = rife.execute("interpolate", {
                "input_path": temp_video,
                "output_path": str(output_dir / "interpolated.mp4"),
                "scale": config.interpolation_factor,
            })

            os.unlink(temp_video)

            if result.status == "success" and result.output_files:
                # 从插值视频中提取帧
                return self._extract_frames(
                    result.output_files[0], output_dir, prefix="interp"
                )
        except Exception as e:
            logger.debug("[HanddrawnPipeline] RIFE interpolation failed: %s", e)
        return None

    def _interpolate_pillow(self, frames, output_dir, config):
        """Pillow 交叉淡入淡出 (降级方案)"""
        from PIL import Image

        all_frames = []
        factor = config.interpolation_factor

        for i in range(len(frames) - 1):
            img_a = Image.open(frames[i]).convert("RGB")
            img_b = Image.open(frames[i + 1]).convert("RGB")

            for j in range(factor):
                alpha = j / factor
                blended = Image.blend(img_a, img_b, alpha)
                out_path = str(output_dir / f"interp_{len(all_frames):05d}.png")
                blended.save(out_path)
                all_frames.append(out_path)

        # 添加最后一帧
        shutil.copy2(frames[-1], str(output_dir / f"interp_{len(all_frames):05d}.png"))
        all_frames.append(str(output_dir / f"interp_{len(all_frames):05d}.png"))

        return all_frames

    def _postprocess_frames(
        self, frames: list[str], output_dir: Path, config: HanddrawnConfig
    ) -> list[str]:
        """后处理: 线条抖动 + 纹理"""
        if config.line_jitter <= 0:
            return frames

        final = []
        for i, frame_path in enumerate(frames):
            out_path = str(output_dir / f"final_{i:05d}.png")
            try:
                import numpy as np
                from PIL import Image, ImageFilter

                img = Image.open(frame_path).convert("RGB")
                arr = np.array(img, dtype=np.int16)

                # 轻微位移抖动 (模拟手绘不稳定)
                jitter_range = int(config.line_jitter * 3)
                if jitter_range > 0:
                    dy = np.random.randint(-jitter_range, jitter_range + 1)
                    dx = np.random.randint(-jitter_range, jitter_range + 1)
                    arr = np.roll(arr, shift=(dy, dx), axis=(0, 1))

                result = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
                result.save(out_path)
                final.append(out_path)
            except Exception as e:
                # 降级: 直接复制
                shutil.copy2(frame_path, out_path)
                final.append(out_path)

        return final

    def _encode_output(
        self, frames: list[str], output_path: str, config: HanddrawnConfig
    ) -> dict[str, Any]:
        """编码最终输出"""
        if not frames:
            return {"status": "error", "message": "No frames to encode"}

        if config.output_format == "frame_sequence":
            # 直接输出帧序列
            out_dir = Path(output_path)
            out_dir.mkdir(parents=True, exist_ok=True)
            for i, f in enumerate(frames):
                shutil.copy2(f, str(out_dir / f"frame_{i:05d}.png"))
            return {"status": "success", "output_dir": str(out_dir)}

        # FFmpeg 编码
        with tempfile.TemporaryDirectory(prefix="hd_encode_") as tmpdir:
            # 复制帧到临时目录 (连续编号)
            for i, f in enumerate(frames):
                ext = Path(f).suffix
                shutil.copy2(f, os.path.join(tmpdir, f"frame_{i:05d}{ext}"))

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(config.fps),
                "-i", os.path.join(tmpdir, "frame_%05d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "18",
                output_path,
            ]

            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if proc.returncode == 0:
                    return {"status": "success", "output_path": output_path}
                else:
                    return {"status": "error", "message": f"FFmpeg failed: {proc.stderr[-200:]}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    def _frames_to_video(self, frames: list[str], output_path: str, fps: int = 4):
        """帧序列 → 视频 (用于 RIFE 输入)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, f in enumerate(frames):
                shutil.copy2(f, os.path.join(tmpdir, f"frame_{i:05d}.png"))

            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", os.path.join(tmpdir, "frame_%05d.png"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                output_path,
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def _extract_frames(self, video_path: str, output_dir: Path, prefix: str = "frame") -> list[str]:
        """视频 → 帧序列"""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            str(output_dir / f"{prefix}_%05d.png"),
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return sorted(str(p) for p in output_dir.glob(f"{prefix}_*.png"))
