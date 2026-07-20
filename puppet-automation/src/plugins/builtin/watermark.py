"""Watermark filter plugin.

Adds a watermark to the final rendered output in Phase 4.
Uses ffmpeg to overlay a text or image watermark.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from src.plugins.base import FilterPlugin, PluginContext, PluginPriority
from src.models.pipeline import (
    PhaseResult,
    PipelinePhase,
    TaskStatus,
)


class WatermarkPlugin(FilterPlugin):
    """Adds a text watermark to the Phase 4 render output.

    Configuration:
        text: Watermark text (default: "Puppet Automation")
        position: Position [x:y] (default: "W-w-20:H-h-20" = bottom-right)
        font_size: Font size (default: 24)
        font_color: Font color (default: "white@0.5")
    """

    @property
    def name(self) -> str:
        return "watermark"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Adds a text watermark to rendered output via ffmpeg"

    @property
    def priority(self) -> PluginPriority:
        return PluginPriority.NORMAL

    @property
    def target_phase(self) -> PipelinePhase:
        return PipelinePhase.PHASE4_RENDER

    def __init__(self) -> None:
        super().__init__()
        self._text: str = "Puppet Automation"
        self._position: str = "W-w-20:H-h-20"
        self._font_size: int = 24
        self._font_color: str = "white@0.5"

    @property
    def watermark_text(self) -> str:
        return self._text

    @watermark_text.setter
    def watermark_text(self, value: str) -> None:
        self._text = value

    @property
    def position(self) -> str:
        return self._position

    @position.setter
    def position(self, value: str) -> None:
        self._position = value

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, value: int) -> None:
        self._font_size = value

    async def filter(self, ctx: PluginContext) -> PhaseResult:
        """Apply watermark to the render output."""
        result = ctx.phase_result
        if not result or result.status != TaskStatus.SUCCESS:
            return result

        metadata = dict(result.metadata or {})
        output_path = metadata.get("output_path", "")

        if not output_path:
            from loguru import logger
            logger.warning("[Plugin:Watermark] No output_path found, skipping watermark")
            return result

        output_file = Path(output_path)
        if not output_file.exists():
            from loguru import logger
            logger.warning(f"[Plugin:Watermark] Output file not found: {output_file}")
            return result

        # Create watermarked version
        watermarked_path = output_file.parent / f"{output_file.stem}_wm{output_file.suffix}"

        from loguru import logger
        logger.info(f"[Plugin:Watermark] Applying watermark to {output_file.name}")

        # Build ffmpeg overlay filter
        drawtext = (
            f"drawtext=text='{self._text}':"
            f"fontsize={self._font_size}:"
            f"fontcolor={self._font_color}:"
            f"x={self._position}"
        )

        ffmpeg_engine = ctx.engines.get("ffmpeg")
        ffmpeg_bin = "ffmpeg"
        if ffmpeg_engine and hasattr(ffmpeg_engine, "executable_path"):
            ffmpeg_bin = str(ffmpeg_engine.executable_path)

        cmd = [
            ffmpeg_bin,
            "-i", str(output_file),
            "-vf", drawtext,
            "-c:a", "copy",
            "-y",
            str(watermarked_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and watermarked_path.exists():
                # Replace original with watermarked version
                watermarked_path.replace(output_file)
                metadata["watermarked"] = True
                metadata["watermark_text"] = self._text
                logger.info(f"[Plugin:Watermark] Watermark applied successfully")
            else:
                logger.warning(
                    f"[Plugin:Watermark] ffmpeg failed (rc={proc.returncode}): "
                    f"{stderr.decode()[:200]}"
                )
                metadata["watermarked"] = False
        except Exception as e:
            logger.warning(f"[Plugin:Watermark] Failed to apply watermark: {e}")
            metadata["watermarked"] = False

        result.metadata = metadata
        return result
