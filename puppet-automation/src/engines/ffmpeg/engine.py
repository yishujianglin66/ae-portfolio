"""FFmpeg engine - video processing core."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class FFmpegEngine(BaseEngine):
    """FFmpeg wrapper for video conversion, encoding, frame extraction."""

    name = "ffmpeg"

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.ffmpeg_path
        super().__init__(path)
        self.ffprobe_path = path.parent / "ffprobe.exe" if path.name == "ffmpeg.exe" else path

    async def get_video_info(self, video_path: Path | str) -> dict:
        """Get video metadata via ffprobe."""
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        if code != 0:
            raise RuntimeError(f"ffprobe failed: {stderr}")
        return json.loads(stdout)

    async def convert(
        self,
        input_path: Path | str,
        output_path: Path | str,
        codec: str = "libx264",
        bitrate: str = "20M",
        preset: str = "medium",
        crf: Optional[int] = None,
        audio_codec: str = "aac",
        audio_bitrate: str = "192k",
        extra_args: Optional[list[str]] = None,
    ) -> EngineResult:
        """Convert video format with specified encoding."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(self.executable_path), "-y", "-i", str(input_path)]
        if crf is not None:
            cmd.extend(["-c:v", codec, "-crf", str(crf), "-preset", preset])
        else:
            cmd.extend(["-c:v", codec, "-b:v", bitrate, "-preset", preset])
        cmd.extend(["-c:a", audio_codec, "-b:a", audio_bitrate])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(str(output_path))

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
            metadata={"codec": codec, "preset": preset, "crf": crf},
        )

    async def extract_frames(
        self,
        video_path: Path | str,
        output_dir: Path | str,
        fps: float = 1.0,
        image_format: str = "png",
        quality: int = 2,
    ) -> EngineResult:
        """Extract frames from video at specified FPS."""
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        pattern = str(output_dir / f"frame_%06d.{image_format}")

        cmd = [
            str(self.executable_path), "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", str(quality),
            pattern,
        ]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=3600
        )

        frames = sorted(output_dir.glob(f"*.{image_format}"))
        return EngineResult(
            success=code == 0,
            output_path=output_dir,
            metadata={
                "frame_count": len(frames),
                "fps": fps,
                "format": image_format,
            },
            error=stderr if code != 0 else None,
        )

    async def concat(
        self,
        input_paths: list[Path | str],
        output_path: Path | str,
        reencode: bool = False,
    ) -> EngineResult:
        """Concatenate multiple videos."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create concat list file
        list_file = output_path.parent / "concat_list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for p in input_paths:
                f.write(f"file '{Path(p).absolute().as_posix()}'\n")

        cmd = [str(self.executable_path), "-y", "-f", "concat", "-safe", "0"]
        if not reencode:
            cmd.append("-c")
            cmd.append("copy")
        cmd.extend(["-i", str(list_file), str(output_path)])

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        list_file.unlink(missing_ok=True)
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
        )

    async def extract_audio(
        self,
        video_path: Path | str,
        output_path: Path | str,
        audio_codec: str = "pcm_s16le",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> EngineResult:
        """Extract audio track from video."""
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.executable_path), "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", audio_codec,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_path),
        ]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
        )

    async def execute(self, **kwargs) -> EngineResult:
        """Generic execute dispatch."""
        action = kwargs.pop("action", "convert")
        handler = {
            "convert": self.convert,
            "extract_frames": self.extract_frames,
            "concat": self.concat,
            "extract_audio": self.extract_audio,
            "get_info": self.get_video_info,
        }.get(action)
        if handler is None:
            return EngineResult(success=False, error=f"Unknown action: {action}")
        if asyncio.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return EngineResult(success=False, error="Handler is not async")
