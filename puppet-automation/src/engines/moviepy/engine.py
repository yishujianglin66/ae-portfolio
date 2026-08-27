"""
MoviePy Engine - Python视频剪辑
=================================

封装 MoviePy 的快速视频剪辑能力：
- 多片段快速合成（秒级预览）
- 字幕烧录
- 音频提取
- 批量处理

与AE的关系：
- MoviePy：快速合成、批量处理、无需打开AE
- AE：复杂合成、特效、关键帧动画
- 建议：MoviePy用于预览/批量，AE用于最终精修

国内网络适配：
- 安装使用清华/阿里云 PyPI 镜像

使用方式：
    engine = MoviePyEngine()
    result = await engine.quick_compose([{"path": "a.mp4"}, {"path": "b.mp4"}], "out.mp4")
    result = await engine.add_subtitles("video.mp4", "subs.srt", "out.mp4")
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402


class MoviePyEngine(BaseEngine):
    """MoviePy video editing engine."""

    name = "moviepy"

    def __init__(
        self,
        executable_path: Path | str = sys.executable,
    ):
        super().__init__(executable_path)
        self._moviepy = None
        self._check_installation()

    def _check_installation(self) -> None:
        """检查 moviepy 是否已安装。"""
        try:
            import moviepy.editor as mp
            self._moviepy = mp
            logger.info("[MoviePy] moviepy module loaded")
        except ImportError:
            logger.warning(
                "[MoviePy] moviepy not installed. "
                "Run: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple moviepy"
            )

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】task 调度；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        task = kwargs.get("task", "compose")
        if task == "compose":
            return await self.quick_compose(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        if task == "subtitles":
            return await self.add_subtitles(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        if task == "audio":
            return await self.extract_audio(*args, **{k: v for k, v in kwargs.items() if k != "task"})
        return EngineResult(success=False, error=f"Unknown task: {task}")

    async def quick_compose(
        self,
        clips: List[Dict[str, Any]],
        output_path: Path | str,
        transitions: str = "fade",  # fade/none/crossfade
        transition_duration: float = 0.5,
        resolution: Optional[str] = None,
        fps: int = 30,
        audio_path: Optional[Path] = None,
    ) -> EngineResult:
        """快速多片段合成。

        Args:
            clips: [{"path": "a.mp4", "start": 0, "duration": 5}, ...]
            output_path: 输出路径
            transitions: 转场类型
            transition_duration: 转场时长(秒)
            resolution: 输出分辨率 (如 "1080x1920")
            fps: 输出帧率
            audio_path: 背景音乐路径
        """
        import time

        start = time.time()
        output_path = Path(output_path)

        if not clips:
            return EngineResult(success=False, error="No clips provided")

        if self._moviepy is None:
            return EngineResult(
                success=False,
                error="MoviePy not installed. "
                      "Run: pip install -i https://pypi.tuna.tsinghua.edu.cn/simple moviepy",
            )

        try:
            result = await asyncio.to_thread(
                self._compose_sync,
                clips, output_path, transitions,
                transition_duration, resolution, fps, audio_path,
            )

            duration = time.time() - start

            if result:
                return EngineResult(
                    success=True,
                    output_path=output_path,
                    metadata={
                        "clip_count": len(clips),
                        "transitions": transitions,
                        "resolution": resolution,
                        "fps": fps,
                    },
                    duration_seconds=duration,
                )
            else:
                return EngineResult(
                    success=False, error="Composition failed",
                    duration_seconds=duration,
                )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Composition error: {str(e)[:500]}",
            )

    def _compose_sync(
        self,
        clips: List[Dict[str, Any]],
        output_path: Path,
        transitions: str,
        transition_duration: float,
        resolution: Optional[str],
        fps: int,
        audio_path: Optional[Path],
    ) -> bool:
        """同步合成（在线程中执行）。"""
        mp = self._moviepy

        # 加载片段
        video_clips = []
        for clip_info in clips:
            clip_path = Path(clip_info["path"])
            if not clip_path.exists():
                logger.warning(f"Clip not found: {clip_path}")
                continue

            clip = mp.VideoFileClip(str(clip_path))

            # 裁剪
            start = clip_info.get("start", 0)
            duration = clip_info.get("duration")
            if duration:
                clip = clip.subclip(start, start + duration)
            elif start > 0:
                clip = clip.subclip(start)

            # 调整分辨率
            if resolution:
                w, h = map(int, resolution.split("x"))
                clip = clip.resize(newsize=(w, h))

            video_clips.append(clip)

        if not video_clips:
            return False

        # 添加转场
        if transitions == "crossfade" and len(video_clips) > 1:
            from moviepy.video.compositing.transitions import crossfadein
            final_clips = [video_clips[0]]
            for clip in video_clips[1:]:
                clip = clip.crossfadein(transition_duration)
                final_clips.append(clip)
            video_clips = final_clips

        # 合成
        final = mp.concatenate_videoclips(
            video_clips,
            method="compose",
        )

        # 添加音频
        if audio_path and audio_path.exists():
            audio = mp.AudioFileClip(str(audio_path))
            if audio.duration > final.duration:
                audio = audio.subclip(0, final.duration)
            final = final.set_audio(audio)

        # 导出
        final.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(output_path.with_suffix(".m4a")),
            remove_temp=True,
        )

        # 清理
        for clip in video_clips:
            clip.close()
        final.close()

        return output_path.exists()

    async def add_subtitles(
        self,
        video_path: Path | str,
        srt_path: Path | str,
        output_path: Path | str,
        font: str = "Arial",
        fontsize: int = 48,
        color: str = "white",
        stroke_color: str = "black",
        stroke_width: int = 2,
        position: str = "center,bottom",  # center,bottom / center,center
    ) -> EngineResult:
        """烧录字幕到视频。

        Args:
            video_path: 视频路径
            srt_path: SRT字幕文件路径
            output_path: 输出路径
            font: 字体名
            fontsize: 字号
            color: 颜色
            stroke_color: 描边颜色
            stroke_width: 描边宽度
            position: 位置
        """
        import time

        start = time.time()
        video_path = Path(video_path)
        srt_path = Path(srt_path)
        output_path = Path(output_path)

        if not video_path.exists():
            return EngineResult(
                success=False, error=f"Video not found: {video_path}",
            )
        if not srt_path.exists():
            return EngineResult(
                success=False, error=f"SRT not found: {srt_path}",
            )

        if self._moviepy is None:
            return EngineResult(
                success=False, error="MoviePy not installed",
            )

        try:
            result = await asyncio.to_thread(
                self._add_subtitles_sync,
                video_path, srt_path, output_path,
                font, fontsize, color, stroke_color, stroke_width, position,
            )

            duration = time.time() - start

            if result:
                return EngineResult(
                    success=True,
                    output_path=output_path,
                    duration_seconds=duration,
                )
            else:
                return EngineResult(
                    success=False, error="Subtitle burn failed",
                    duration_seconds=duration,
                )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Subtitle error: {str(e)[:500]}",
            )

    def _add_subtitles_sync(
        self,
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        font: str,
        fontsize: int,
        color: str,
        stroke_color: str,
        stroke_width: int,
        position: str,
    ) -> bool:
        """同步烧录字幕。"""
        mp = self._moviepy

        video = mp.VideoFileClip(str(video_path))

        # 解析位置
        if position == "center,bottom":
            pos = ("center", "bottom")
        elif position == "center,center":
            pos = ("center", "center")
        else:
            pos = ("center", "bottom")

        # 使用FFmpeg方式烧录（更可靠）
        import subprocess

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vf", (
                f"subtitles={srt_path}:force_style='"
                f"FontName={font},"
                f"FontSize={fontsize},"
                f"PrimaryColour=&H00FFFFFF,"
                f"OutlineColour=&H00000000,"
                f"Outline={stroke_width},"
                f"Alignment=2'"
            ),
            "-c:a", "copy",
            str(output_path),
        ]

        subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        video.close()
        return output_path.exists()

    async def extract_audio(
        self,
        video_path: Path | str,
        output_path: Path | str,
        format: str = "wav",
    ) -> EngineResult:
        """提取音频轨道。

        Args:
            video_path: 视频路径
            output_path: 输出音频路径
            format: 输出格式 (wav/mp3/aac)
        """
        import time

        start = time.time()
        video_path = Path(video_path)
        output_path = Path(output_path)

        if not video_path.exists():
            return EngineResult(
                success=False, error=f"Video not found: {video_path}",
            )

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vn",  # 禁用视频
                "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
                "-ar", "44100",
                "-ac", "2",
                str(output_path),
            ]

            rc, _stdout, stderr, _err_code = await asyncio.to_thread(
                self._run_subprocess, cmd, timeout=300,
            )

            duration = time.time() - start

            if rc != 0:
                return EngineResult(
                    success=False,
                    error=f"Audio extraction failed: {stderr[:500]}",
                    duration_seconds=duration,
                )

            return EngineResult(
                success=True,
                output_path=output_path,
                metadata={"format": format},
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"Extraction error: {str(e)[:500]}",
            )

    def get_info(self) -> dict:
        """返回引擎信息。"""
        return {
            "name": self.name,
            "installed": self._moviepy is not None,
            "capabilities": [
                "quick_compose",
                "add_subtitles",
                "extract_audio",
            ],
            "use_case": "Fast preview / batch processing (AE for final polish)",
            "install_command": (
                "pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
                "moviepy"
            ),
        }