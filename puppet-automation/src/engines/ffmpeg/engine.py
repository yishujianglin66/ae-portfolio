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
        self.ffprobe_available: bool = self.ffprobe_path.exists()
        if not self.ffprobe_available:
            logger.warning(
                f"[{self.name}] ffprobe not available at {self.ffprobe_path}. "
                "get_video_info() will short-circuit."
            )

    async def get_video_info(self, video_path: Path | str) -> EngineResult:
        """Get video metadata via ffprobe. Returns EngineResult with video_info in metadata."""
        video_path = Path(video_path)
        if not video_path.exists():
            return EngineResult(
                success=False,
                error=f"Video not found: {video_path}",
                error_code="FFMPEG_VIDEO_NOT_FOUND",
                sample_id=str(video_path),
                is_error_sample=True,
            )
        if not getattr(self, "ffprobe_available", True):
            return EngineResult(
                success=False,
                error="ffprobe not available, cannot read video info",
                error_code="FFPROBE_NOT_AVAILABLE",
                available=False,
            )

        cmd = [
            str(self.ffprobe_path),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]
        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        if code != 0:
            return EngineResult(
                success=False,
                error=f"ffprobe failed: {stderr}",
                error_code=err_code or "FFPROBE_EXEC_FAILED",
                sample_id=str(video_path),
                is_error_sample=True,
            )
        try:
            video_info = json.loads(stdout)
            return EngineResult(
                success=True,
                metadata={"video_info": video_info},
                sample_id=str(video_path),
            )
        except json.JSONDecodeError as e:
            return EngineResult(
                success=False,
                error=f"ffprobe JSON parse failed: {e}",
                error_code="JSON_PARSE_ERROR",
                sample_id=str(video_path),
                is_error_sample=True,
            )

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
        from ..base import validate_path_safety
        input_path = validate_path_safety(input_path, must_exist=True)
        output_path = validate_path_safety(output_path, must_exist=False)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        cmd = [str(self.executable_path), "-y", "-i", str(input_path)]
        if crf is not None:
            cmd.extend(["-c:v", codec, "-crf", str(crf), "-preset", preset])
        else:
            cmd.extend(["-c:v", codec, "-b:v", bitrate, "-preset", preset])
        cmd.extend(["-c:a", audio_codec, "-b:a", audio_bitrate])
        if extra_args:
            cmd.extend(extra_args)
        cmd.append(str(output_path))

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
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
        from ..base import validate_path_safety
        video_path = validate_path_safety(video_path, must_exist=True)
        output_dir = validate_path_safety(output_dir, must_exist=False)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        pattern = str(output_dir / f"frame_%06d.{image_format}")

        cmd = [
            str(self.executable_path), "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", str(quality),
            pattern,
        ]
        code, stdout, stderr, err_code = await asyncio.to_thread(
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
            error_code=err_code if code != 0 else None,
        )

    async def concat(
        self,
        input_paths: list[Path | str],
        output_path: Path | str,
        reencode: bool = False,
    ) -> EngineResult:
        """Concatenate multiple videos."""
        from ..base import validate_path_safety
        validated_inputs = []
        for p in input_paths:
            validated_inputs.append(validate_path_safety(p, must_exist=True))
        input_paths = validated_inputs
        output_path = validate_path_safety(output_path, must_exist=False)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

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

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        list_file.unlink(missing_ok=True)
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
        )

    async def image_sequence_to_video(
        self,
        frames_dir: Path | str,
        output_path: Path | str,
        fps: float = 30.0,
        codec: str = "libx264",
        crf: int = 18,
        preset: str = "slow",
        frame_pattern: str = "frame_%06d.png",
        pixel_format: str = "yuv420p",
        audio_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """将 PNG 帧序列合成为视频（替代 AME 的 PNG 序列编码）。

        用于 AME 不可用时承接 AE 渲染的帧序列 → 视频链路。
        """
        from ..base import validate_path_safety
        frames_dir = validate_path_safety(frames_dir, must_exist=True)
        output_path = validate_path_safety(output_path, must_exist=False)
        if audio_path is not None:
            audio_path = validate_path_safety(audio_path, must_exist=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 验证帧存在（按 frame_pattern 推断首帧文件名）
        idx = frame_pattern.find("%0")
        if idx >= 0:
            # frame_%06d.png → frame_000001.png
            digits_str = frame_pattern[idx:]
            import re as _re
            m = _re.match(r"%0?(\d+)d", digits_str)
            width = int(m.group(1)) if m else 6
            start_idx = "1".zfill(width)
            first_frame_name = frame_pattern.replace("%0" + str(width) + "d", start_idx)
        else:
            first_frame_name = frame_pattern
        first_frame = frames_dir / first_frame_name
        if not first_frame.exists():
            return EngineResult(
                success=False,
                error=f"No frames found at {first_frame} (pattern={frame_pattern})",
                error_code="FRAMES_NOT_FOUND",
            )

        input_pattern = str(frames_dir / frame_pattern)
        cmd = [
            str(self.executable_path), "-y",
            "-framerate", str(fps),
            "-i", input_pattern,
            "-c:v", codec,
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", pixel_format,
        ]

        # 可选音轨合成
        if audio_path and Path(audio_path).exists():
            cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-b:a", "192k", "-shortest"])
        cmd.append(str(output_path))

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
            metadata={
                "fps": fps,
                "codec": codec,
                "frame_pattern": frame_pattern,
                "frames_dir": str(frames_dir),
                "audio": bool(audio_path),
            },
        )

    async def extract_audio(
        self,
        video_path: Path | str,
        output_path: Path | str,
        audio_codec: str = "pcm_s16le",
        sample_rate: int = 16000,
        channels: int = 1,
    ) -> EngineResult:
        """Extract audio track from video.

        若 output_path 扩展名与 audio_codec 不匹配（如 .mp3 配 pcm_s16le），
        会自动按扩展名推断 codec，避免 FFmpeg 因容器/编码不匹配输出空文件。
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 按输出扩展名推断 codec，避免扩展名与编码不匹配
        suffix = output_path.suffix.lower()
        _CODEC_BY_EXT = {
            ".mp3": "libmp3lame",
            ".m4a": "aac",
            ".aac": "aac",
            ".ogg": "libvorbis",
            ".opus": "libopus",
            ".wma": "wmav2",
            ".flac": "flac",
        }
        if suffix in _CODEC_BY_EXT:
            audio_codec = _CODEC_BY_EXT[suffix]

        cmd = [
            str(self.executable_path), "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", audio_codec,
            "-ar", str(sample_rate),
            "-ac", str(channels),
            str(output_path),
        ]
        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            error=stderr if code != 0 else None,
            error_code=err_code if code != 0 else None,
        )

    async def _execute_impl(self, **kwargs) -> EngineResult:
        """Generic execute dispatch."""
        action = kwargs.pop("action", "convert")
        handler = {
            "convert": self.convert,
            "extract_frames": self.extract_frames,
            "concat": self.concat,
            "extract_audio": self.extract_audio,
            "get_info": self.get_video_info,
            "image_sequence_to_video": self.image_sequence_to_video,
        }.get(action)
        if handler is None:
            return EngineResult(success=False, error=f"Unknown action: {action}")
        if asyncio.iscoroutinefunction(handler):
            return await handler(**kwargs)
        return EngineResult(success=False, error="Handler is not async")
