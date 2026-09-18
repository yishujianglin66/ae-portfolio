"""伪装高帧服务 v2 - 先真实补帧再视觉增强.

策略：
1. 先用 minterpolate 真实补帧到 60/120fps
2. 在高帧率下应用运动模糊 + tblend 帧混合
3. 输出高帧率视频，平台压缩后依然流畅
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from ..config import settings
from ..engines.ffmpeg.engine import FFmpegEngine


class FakeHighFrameRateService:
    """Service for creating visually smooth videos via real interpolation + visual enhancement."""

    def __init__(self):
        self.ffmpeg = FFmpegEngine(settings.get_ffmpeg())

    async def _run_ffmpeg(self, cmd: list[str], timeout: int = 3600) -> tuple[int, str, str]:
        """Run ffmpeg command and return (code, stdout, stderr)."""
        return await asyncio.to_thread(self.ffmpeg._run_subprocess, cmd, timeout=timeout)

    async def apply_fake_hfr(
        self,
        input_path: str | Path,
        output_path: str | Path,
        target_fps: int = 60,
        mode: str = "smart",
        blur_strength: float = 0.3,
        blend_alpha: float = 0.3,
        sharpen_amount: float = 1.5,
        upscale_4k: bool = True,
        preserve_audio: bool = True,
    ) -> dict[str, Any]:
        """Apply fake high frame rate: real interpolation + visual enhancement.

        Args:
            input_path: Input video
            output_path: Output video
            target_fps: Interpolate to this FPS (60 or 120)
            mode: Processing mode:
                - 'interpolate': Only real frame interpolation
                - 'blur': Interpolation + motion blur
                - 'blend': Interpolation + frame blending
                - 'smart': Interpolation + blur + blend + sharpen (recommended)
                - 'full': All effects including color enhancement
            blur_strength: Motion blur sigma (0.1-3.0)
            blend_alpha: Frame blend opacity (0-1)
            sharpen_amount: Sharpening intensity (0-3)
            upscale_4k: Upscale to 4K first
            preserve_audio: Keep audio
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Fake HFR v2: {input_path.name} -> {target_fps}fps, mode={mode}")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            current = input_path

            # Step 1: Real frame interpolation at ORIGINAL resolution (much faster)
            step1 = td_path / "step1_interp.mp4"
            logger.info(f"  [1/4] Frame interpolation to {target_fps}fps...")
            interp_filter = (
                f"minterpolate=fps={target_fps}:mi_mode=mci:"
                f"mc_mode=aobmc:vsbmc=1:me_mode=bidir:me=epzs"
            )
            cmd = [
                str(self.ffmpeg.executable_path), "-y",
                "-i", str(current),
                "-vf", interp_filter,
                "-r", str(target_fps),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-an",
                str(step1),
            ]
            code, _, err = await self._run_ffmpeg(cmd, timeout=7200)
            if code != 0:
                logger.warning("  minterpolate mci failed, trying blend mode...")
                # Fallback: simpler interpolation
                interp_fallback = f"minterpolate=fps={target_fps}:mi_mode=blend"
                cmd_fb = [
                    str(self.ffmpeg.executable_path), "-y",
                    "-i", str(current),
                    "-vf", interp_fallback,
                    "-r", str(target_fps),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-an",
                    str(step1),
                ]
                code, _, err = await self._run_ffmpeg(cmd_fb)
                if code != 0:
                    return {"success": False, "error": f"Interpolation failed: {err[-300:]}"}
            current = step1

            # Step 2: Upscale to 4K (after interpolation, so it's fast)
            if upscale_4k:
                step2 = td_path / "step2_4k.mp4"
                logger.info("  [2/4] 4K upscale...")
                cmd = [
                    str(self.ffmpeg.executable_path), "-y",
                    "-i", str(current),
                    "-vf", "scale=3840:2160:flags=lanczos",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                    "-r", str(target_fps),
                    "-an",
                    str(step2),
                ]
                code, _, err = await self._run_ffmpeg(cmd)
                if code != 0:
                    return {"success": False, "error": f"4K upscale failed: {err[-300:]}"}
                current = step2

            # Step 3: Visual enhancement (motion blur + frame blending + sharpen)
            if mode in ("blur", "smart", "full"):
                step3 = td_path / "step3_enhanced.mp4"
                logger.info("  [3/4] Visual enhancement...")

                vf_parts = []

                # Motion blur via gblur
                if mode in ("blur", "smart", "full"):
                    vf_parts.append(f"gblur=sigma={blur_strength}:steps=3")

                # Frame blending via tblend
                if mode in ("blend", "smart", "full"):
                    vf_parts.append(
                        f"tblend=all_mode=overlay:all_opacity={blend_alpha}"
                    )

                # Sharpening
                if mode in ("smart", "full"):
                    vf_parts.append(
                        f"unsharp=5:5:{sharpen_amount}:5:5:{sharpen_amount * 0.5}"
                    )

                # Color enhancement
                if mode == "full":
                    vf_parts.append("eq=contrast=1.05:saturation=1.08:brightness=0.02")

                vf = ",".join(vf_parts) if vf_parts else "null"

                # Build command with audio from original
                cmd = [
                    str(self.ffmpeg.executable_path), "-y",
                    "-i", str(current),
                ]
                if preserve_audio:
                    cmd.extend(["-i", str(input_path), "-map", "0:v:0", "-map", "1:a:0"])

                cmd.extend([
                    "-vf", vf,
                    "-r", str(target_fps),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p",
                ])
                if preserve_audio:
                    cmd.extend(["-c:a", "aac", "-b:a", "192k"])
                cmd.append(str(step3))

                code, _, err = await self._run_ffmpeg(cmd)
                if code != 0:
                    return {"success": False, "error": f"Enhancement failed: {err[-300:]}"}
                current = step3
            else:
                # Just copy interpolated video, add audio
                if preserve_audio:
                    step3 = td_path / "step3_audio.mp4"
                    cmd = [
                        str(self.ffmpeg.executable_path), "-y",
                        "-i", str(current),
                        "-i", str(input_path),
                        "-map", "0:v:0", "-map", "1:a:0",
                        "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k",
                        "-r", str(target_fps),
                        str(step3),
                    ]
                    code, _, err = await self._run_ffmpeg(cmd)
                    if code != 0:
                        return {"success": False, "error": f"Audio mux failed: {err[-300:]}"}
                    current = step3

            # Step 4: Copy to final output
            logger.info("  [4/4] Finalizing...")
            import shutil
            shutil.copy2(str(current), str(output_path))

            logger.info(f"  Done: {output_path.name}")
            return {
                "success": True,
                "output_path": str(output_path),
                "target_fps": target_fps,
                "mode": mode,
                "blur_strength": blur_strength,
                "blend_alpha": blend_alpha,
                "sharpen_amount": sharpen_amount,
                "upscaled_4k": upscale_4k,
            }

    async def batch_apply_fake_hfr(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        target_fps: int = 60,
        mode: str = "smart",
    ) -> list[dict[str, Any]]:
        """Batch apply fake HFR to all videos in a directory."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
        videos = []
        for ext in extensions:
            videos.extend(input_dir.glob(f"*{ext}"))

        results = []
        for i, video in enumerate(videos, 1):
            logger.info(f"[{i}/{len(videos)}] {video.name}")
            output_path = output_dir / f"{video.stem}_hfr_{target_fps}fps.mp4"
            result = await self.apply_fake_hfr(
                video, output_path, target_fps=target_fps, mode=mode,
            )
            result["input"] = str(video)
            results.append(result)

        return results

    def get_optimal_settings(
        self,
        platform: str = "douyin",
        content_type: str = "general",
    ) -> dict[str, Any]:
        """Get optimal settings for different platforms and content types."""
        platform_profiles = {
            "douyin": {"target_fps": 60, "mode": "smart", "blur_strength": 0.3, "blend_alpha": 0.3, "sharpen_amount": 1.5},
            "bilibili": {"target_fps": 60, "mode": "smart", "blur_strength": 0.25, "blend_alpha": 0.25, "sharpen_amount": 1.5},
            "youtube": {"target_fps": 60, "mode": "smart", "blur_strength": 0.2, "blend_alpha": 0.2, "sharpen_amount": 2.0},
            "tiktok": {"target_fps": 60, "mode": "blur", "blur_strength": 0.4, "blend_alpha": 0.35, "sharpen_amount": 1.5},
        }
        content_adjustments = {
            "action": {"blur_strength": 0.5, "blend_alpha": 0.4, "target_fps": 120},
            "animation": {"blur_strength": 0.15, "sharpen_amount": 2.5},
            "sports": {"blur_strength": 0.6, "blend_alpha": 0.5, "target_fps": 120},
            "general": {},
        }
        cfg = platform_profiles.get(platform, platform_profiles["douyin"])
        cfg.update(content_adjustments.get(content_type, {}))
        return cfg
