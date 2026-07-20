"""Beat-sync video generation service - 卡点视频生成器."""

from __future__ import annotations

import asyncio
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..config import settings
from ..engines.ffmpeg.engine import FFmpegEngine
from .scene_detection import SceneDetectionService


class BeatVideoService:
    """Service for generating beat-synced highlight videos."""

    CINEMATIC_LUTS = {
        "teal_orange": "teal_orange",
        "warm_cinematic": "warm_cinematic",
        "cool_mood": "cool_mood",
        "vintage_film": "vintage_film",
        "noir": "noir",
    }

    TRANSITIONS = [
        "fade", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
        "slideleft", "slideright", "slideup", "slidedown",
        "circlecrop", "rectcrop", "distance",
        "fadeblack", "fadewhite", "fadegrays",
        "radial", "hblur", "wipetl", "wipetr", "wipebl", "wipebr",
    ]

    def __init__(self):
        self.ffmpeg = FFmpegEngine(settings.get_ffmpeg())
        self.scene_detector = SceneDetectionService()
        self._librosa_available = False
        try:
            import librosa
            self._librosa_available = True
            logger.info("librosa available for beat detection")
        except ImportError:
            logger.warning("librosa not available, beat detection disabled")

    async def detect_beats(self, audio_path: str | Path) -> Dict[str, Any]:
        """Detect beat positions in audio using librosa."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not self._librosa_available:
            return {"beats": [], "bpm": 0, "method": "none"}

        import librosa
        import numpy as np

        loop = asyncio.get_event_loop()

        def _detect():
            y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env, sr=sr, backtrack=True
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
            return {
                "bpm": float(tempo) if np.isscalar(tempo) else float(tempo[0]),
                "beats": [round(float(t), 3) for t in beat_times],
                "onsets": [round(float(t), 3) for t in onset_times],
                "duration": round(float(len(y) / sr), 2),
                "method": "librosa",
            }

        return await loop.run_in_executor(None, _detect)

    async def _get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """Get video info using OpenCV (fallback for missing ffprobe)."""
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps > 0 else 0
        has_audio = True
        try:
            cmd = [
                str(self.ffmpeg.executable_path), "-i", str(video_path),
                "-f", "null", "-",
            ]
            code, stdout, stderr = await asyncio.to_thread(
                self.ffmpeg._run_subprocess, cmd, timeout=30
            )
            has_audio = "Audio:" in stderr
        except Exception:
            pass
        cap.release()
        return {
            "duration": duration,
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "has_audio": has_audio,
        }

    async def generate_beat_points(
        self,
        video_path: str | Path,
        mode: str = "combined",
    ) -> Dict[str, Any]:
        """Generate beat/cut points for video editing.

        Args:
            video_path: Path to video file
            mode: "beat" (audio beats only), "scene" (scene changes only),
                  "combined" (both beats + scene changes)

        Returns:
            Dict with cut points and metadata
        """
        video_path = Path(video_path)

        info = await self._get_video_info(video_path)
        duration = info["duration"]
        fps = info["fps"] if info["fps"] > 0 else 30
        has_audio = info.get("has_audio", True)

        cut_points = []
        beat_data = {}
        scene_data = {}

        if mode in ("beat", "combined") and has_audio:
            with tempfile.TemporaryDirectory() as td:
                audio_file = Path(td) / "audio.wav"
                result = await self.ffmpeg.extract_audio(
                    video_path, audio_file, audio_codec="pcm_s16le",
                    sample_rate=22050, channels=1,
                )
                if result.success:
                    beat_data = await self.detect_beats(audio_file)
                    for bt in beat_data.get("beats", []):
                        if bt < duration:
                            cut_points.append({"time": bt, "type": "beat"})

        if mode in ("scene", "combined"):
            scene_data = await self.scene_detector.detect_scenes(video_path)
            for scene in scene_data.get("scenes", []):
                cut_points.append({"time": scene["start_time"], "type": "scene_start"})
                cut_points.append({"time": scene["end_time"], "type": "scene_end"})

        cut_points.sort(key=lambda x: x["time"])

        return {
            "video_duration": round(duration, 2),
            "fps": round(fps, 2),
            "cut_points": cut_points,
            "total_cut_points": len(cut_points),
            "beat_data": beat_data,
            "scene_data": scene_data,
            "mode": mode,
        }

    async def upscale_to_4k(
        self,
        input_path: str | Path,
        output_path: str | Path,
        method: str = "lanczos",
    ) -> Path:
        """Upscale video to 4K resolution (3840x2160).

        Args:
            input_path: Input video path
            output_path: Output video path
            method: "lanczos" (fast), "topaz" (AI quality, requires Topaz)

        Returns:
            Output file path
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        info = await self._get_video_info(input_path)
        width = info.get("width", 1920)
        height = info.get("height", 1080)

        target_w, target_h = 3840, 2160

        if width >= target_w and height >= target_h:
            logger.info(f"Video already 4K+, copying: {width}x{height}")
            return input_path

        if method == "topaz":
            try:
                from ..engines.topaz.engine import TopazEngine
                topaz = TopazEngine()
                scale = max(target_w / width, target_h / height)
                result = await topaz.enhance(
                    input_path, output_path, model="proteus", scale=scale,
                )
                if result.success and result.output_path:
                    return Path(result.output_path)
            except Exception as e:
                logger.warning(f"Topaz upscale failed, falling back to lanczos: {e}")

        vf = (
            f"scale={target_w}:{target_h}:flags=lanczos,"
            f"unsharp=3:3:1.5:3:3:0.5,"
            f"eq=contrast=1.05:saturation=1.1"
        )
        result = await self.ffmpeg.convert(
            input_path, output_path,
            codec="libx264", crf=18, preset="slow",
            extra_args=["-vf", vf, "-pix_fmt", "yuv420p"],
        )
        if not result.success:
            raise RuntimeError(f"4K upscale failed: {result.error}")
        return output_path

    def _get_cinematic_filter(self, style: str = "teal_orange") -> str:
        """Generate cinematic color grading filter chain for FFmpeg.

        Args:
            style: Cinematic style name

        Returns:
            FFmpeg filter string
        """
        styles = {
            "teal_orange": (
                "colorchannelmixer="
                "rr=0.9:rg=0.1:rb=0.05:"
                "gr=0.05:gg=0.85:gb=0.15:"
                "br=0.0:bg=0.2:bb=0.95,"
                "eq=contrast=1.15:saturation=1.2:brightness=0.03:gamma=1.1,"
                "curves=vintage"
            ),
            "warm_cinematic": (
                "colorchannelmixer="
                "rr=1.0:rg=0.05:rb=0.0:"
                "gr=0.1:gg=0.9:gb=0.05:"
                "br=0.15:bg=0.1:bb=0.85,"
                "eq=contrast=1.1:saturation=1.15:brightness=0.05:gamma=1.05,"
                "curves=strong_contrast"
            ),
            "cool_mood": (
                "colorchannelmixer="
                "rr=0.85:rg=0.05:rb=0.1:"
                "gr=0.05:gg=0.9:gb=0.1:"
                "br=0.0:bg=0.1:bb=1.05,"
                "eq=contrast=1.1:saturation=0.95:brightness=-0.02:gamma=1.1"
            ),
            "vintage_film": (
                "colorchannelmixer="
                "rr=0.9:rg=0.15:rb=0.05:"
                "gr=0.1:gg=0.85:gb=0.1:"
                "br=0.05:bg=0.1:bb=0.8,"
                "eq=contrast=0.95:saturation=0.85:brightness=0.03:gamma=1.15,"
                "noise=alls=3:allf=t+u"
            ),
            "noir": (
                "hue=s=0,"
                "eq=contrast=1.3:brightness=-0.05:gamma=1.2,"
                "noise=alls=2:allf=t+u"
            ),
        }
        return styles.get(style, styles["teal_orange"])

    def _get_zoom_in_filter(
        self,
        duration: float,
        zoom_speed: float = 1.15,
        fps: int = 30,
    ) -> str:
        """Generate slow zoom-in effect filter.

        Args:
            duration: Clip duration in seconds
            zoom_speed: Max zoom factor (1.0 = no zoom, 1.2 = 20% zoom in)
            fps: Frames per second

        Returns:
            FFmpeg zoompan filter string
        """
        total_frames = int(duration * fps)
        if total_frames < 2:
            return "copy"
        zoom_min = 1.0
        zoom_max = zoom_speed
        return (
            f"zoompan=z='{zoom_min}+({zoom_max}-{zoom_min})*on/{total_frames}':"
            f"d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"s=3840x2160:fps={fps}"
        )

    async def create_beat_video(
        self,
        input_video: str | Path,
        output_path: str | Path,
        mode: str = "combined",
        cinematic_style: str = "teal_orange",
        clip_duration: float = 0.8,
        transition_duration: float = 0.15,
        enable_zoom: bool = True,
        zoom_speed: float = 1.15,
        upscale_4k: bool = True,
    ) -> Dict[str, Any]:
        """Generate a beat-synced highlight video.

        Args:
            input_video: Path to input video
            output_path: Path to output video
            mode: Beat detection mode ("beat", "scene", "combined")
            cinematic_style: Color grading style
            clip_duration: Base clip duration between cuts
            transition_duration: Transition duration between clips
            enable_zoom: Enable slow zoom-in effect
            zoom_speed: Zoom intensity (1.0-1.5)
            upscale_4k: Upscale output to 4K

        Returns:
            Dict with result info
        """
        input_video = Path(input_video)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Generating beat video from: {input_video}")

        info = await self._get_video_info(input_video)
        has_audio = info.get("has_audio", True)

        points_data = await self.generate_beat_points(input_video, mode=mode)
        cut_points = points_data["cut_points"]
        duration = points_data["video_duration"]
        fps = int(points_data["fps"]) if points_data["fps"] > 0 else 30

        if not cut_points:
            cut_points = [{"time": 0, "type": "start"}]

        clips = []
        prev_time = 0.0

        for cp in cut_points:
            t = cp["time"]
            seg_duration = t - prev_time
            if seg_duration >= clip_duration * 0.5:
                clip_start = prev_time
                clip_end = min(t + clip_duration * 0.3, duration)
                actual_dur = clip_end - clip_start
                if actual_dur >= 0.3:
                    clips.append({
                        "start": clip_start,
                        "end": clip_end,
                        "duration": round(actual_dur, 3),
                        "type": cp.get("type", "cut"),
                    })
            prev_time = t

        if not clips:
            clips.append({
                "start": 0, "end": min(5.0, duration),
                "duration": min(5.0, duration), "type": "full",
            })

        logger.info(f"Generated {len(clips)} clips from {len(cut_points)} cut points")

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            clip_files = []

            cinematic_filter = self._get_cinematic_filter(cinematic_style)

            for i, clip in enumerate(clips):
                clip_file = td_path / f"clip_{i:04d}.mp4"

                vf_parts = []
                if upscale_4k:
                    vf_parts.append("scale=3840:2160:flags=lanczos")
                vf_parts.append(cinematic_filter)
                if enable_zoom:
                    zoom_filter = self._get_zoom_in_filter(
                        clip["duration"], zoom_speed=zoom_speed, fps=fps,
                    )
                    if zoom_filter != "copy":
                        vf_parts.append(zoom_filter)

                vf = ",".join(vf_parts) if vf_parts else "copy"

                cmd = [
                    str(self.ffmpeg.executable_path), "-y",
                    "-ss", str(clip["start"]),
                    "-t", str(clip["duration"]),
                    "-i", str(input_video),
                    "-vf", vf,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-an",
                    str(clip_file),
                ]
                code, stdout, stderr = await asyncio.to_thread(
                    self.ffmpeg._run_subprocess, cmd, timeout=1800,
                )
                if code != 0:
                    logger.warning(f"Clip {i} generation failed: {stderr[:200]}")
                    continue
                clip_files.append(clip_file)

            if len(clip_files) < 2:
                if clip_files and has_audio:
                    clip = clips[0]
                    vf_parts_single = []
                    if upscale_4k:
                        vf_parts_single.append("scale=3840:2160:flags=lanczos")
                    vf_parts_single.append(cinematic_filter)
                    if enable_zoom:
                        zoom_filter = self._get_zoom_in_filter(
                            clip["duration"], zoom_speed=zoom_speed, fps=fps,
                        )
                        if zoom_filter != "copy":
                            vf_parts_single.append(zoom_filter)
                    vf_single = ",".join(vf_parts_single) if vf_parts_single else "copy"
                    final_cmd = [
                        str(self.ffmpeg.executable_path), "-y",
                        "-ss", str(clip["start"]),
                        "-t", str(clip["duration"]),
                        "-i", str(input_video),
                        "-vf", vf_single,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k",
                        str(output_path),
                    ]
                    code, stdout, stderr = await asyncio.to_thread(
                        self.ffmpeg._run_subprocess, final_cmd, timeout=1800,
                    )
                    success = code == 0
                    err = stderr if not success else None
                else:
                    result = await self.ffmpeg.convert(
                        clip_files[0] if clip_files else input_video,
                        output_path,
                        codec="libx264", crf=18, preset="medium",
                    )
                    success = result.success
                    err = result.error
                return {
                    "success": success,
                    "output_path": str(output_path) if success else None,
                    "clips_count": len(clips),
                    "bpm": points_data.get("beat_data", {}).get("bpm", 0),
                    "error": err,
                    "mode": mode,
                    "cinematic_style": cinematic_style,
                    "upscaled_4k": upscale_4k,
                    "zoom_enabled": enable_zoom,
                    "resolution": "3840x2160" if upscale_4k else f"{info['width']}x{info['height']}",
                    "has_audio": has_audio,
                }

            concat_list = td_path / "concat.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for cf in clip_files:
                    f.write(f"file '{cf.absolute().as_posix()}'\n")

            video_only_output = td_path / "video_only.mp4"
            result = await self.ffmpeg.concat(
                clip_files, video_only_output, reencode=True,
            )

            if not result.success:
                return {
                    "success": False,
                    "output_path": None,
                    "clips_count": len(clip_files),
                    "total_clips": len(clips),
                    "cut_points": len(cut_points),
                    "bpm": points_data.get("beat_data", {}).get("bpm", 0),
                    "error": result.error,
                    "mode": mode,
                    "cinematic_style": cinematic_style,
                    "upscaled_4k": upscale_4k,
                    "zoom_enabled": enable_zoom,
                }

            final_cmd = [
                str(self.ffmpeg.executable_path), "-y",
                "-i", str(video_only_output),
            ]
            if has_audio:
                final_cmd.extend([
                    "-i", str(input_video),
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                ])
            else:
                final_cmd.extend(["-c", "copy"])
            final_cmd.append(str(output_path))

            code, stdout, stderr = await asyncio.to_thread(
                self.ffmpeg._run_subprocess, final_cmd, timeout=1800,
            )

            return {
                "success": code == 0,
                "output_path": str(output_path) if code == 0 else None,
                "clips_count": len(clip_files),
                "total_clips": len(clips),
                "cut_points": len(cut_points),
                "bpm": points_data.get("beat_data", {}).get("bpm", 0),
                "error": stderr if code != 0 else None,
                "mode": mode,
                "cinematic_style": cinematic_style,
                "upscaled_4k": upscale_4k,
                "zoom_enabled": enable_zoom,
                "resolution": "3840x2160" if upscale_4k else f"{info['width']}x{info['height']}",
                "has_audio": has_audio,
            }
