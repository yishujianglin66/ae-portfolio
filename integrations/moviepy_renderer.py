"""
integrations/moviepy_renderer.py - MoviePy 轻量级渲染器
=====================================================

将 MoviePy 封装为管线的降级渲染方案和快速预览工具。
当 AE/DaVinci 不可用时，用 MoviePy 完成基础的视频拼接、
转场、文字叠加和音频混合。

功能:
- 多片段拼接(支持淡入淡出转场)
- 文字/字幕叠加
- 音频混合与替换
- 快速预览渲染(低分辨率/低帧率)
- 批量片段合成

集成点: pipeline/unified_pipeline.py → _run_render() 降级渲染
约束: 离线可用、无需GPU、纯Python + FFmpeg

用法:
    from integrations.moviepy_renderer import MoviePyRenderer
    renderer = MoviePyRenderer()
    result = renderer.render_segments([
        {"path": "clip1.mp4", "start": 0, "end": 5},
        {"path": "clip2.mp4", "start": 2, "end": 8},
    ], output="preview.mp4", transition="crossfade")
"""
from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RenderResult:
    """渲染结果"""
    success: bool = False
    output_path: str = ""
    duration_sec: float = 0.0
    resolution: str = ""
    fps: float = 0.0
    file_size_mb: float = 0.0
    segments_used: int = 0
    method: str = "moviepy"
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class MoviePyRenderer:
    """MoviePy 轻量级渲染器
    
    优先使用 MoviePy 库；若未安装则降级为 FFmpeg concat。
    适用于:
    - AE/DaVinci 不可用时的降级渲染
    - 快速预览(不需要高质量)
    - 简单的片段拼接和转场
    """

    def __init__(self, ffmpeg_bin: str = ""):
        self._ffmpeg = ffmpeg_bin or shutil.which("ffmpeg") or "ffmpeg"
        self._moviepy_available: Optional[bool] = None

    @property
    def available(self) -> bool:
        """MoviePy 或 FFmpeg 是否可用"""
        return self.moviepy_available or bool(self._ffmpeg)

    @property
    def moviepy_available(self) -> bool:
        """检查 MoviePy 是否已安装"""
        if self._moviepy_available is None:
            try:
                import moviepy  # noqa: F401
                self._moviepy_available = True
            except ImportError:
                self._moviepy_available = False
        return self._moviepy_available

    def render_segments(
        self,
        segments: List[Dict[str, Any]],
        output: str = "",
        transition: str = "crossfade",
        transition_duration: float = 0.5,
        resolution: tuple = (1920, 1080),
        fps: float = 30.0,
        audio_path: str = "",
        preview_mode: bool = False,
    ) -> RenderResult:
        """渲染多个片段为一个视频
        
        Args:
            segments: 片段列表 [{"path": "...", "start": 0, "end": 5}, ...]
            output: 输出路径
            transition: 转场类型 - "crossfade"/"fade"/"none"
            transition_duration: 转场时长(秒)
            resolution: 输出分辨率 (width, height)
            fps: 输出帧率
            audio_path: 背景音乐路径(可选，替换原始音频)
            preview_mode: 预览模式(半分辨率、低帧率)
        """
        if not segments:
            return RenderResult(error="No segments provided")

        # 验证输入文件
        valid_segments = []
        for seg in segments:
            path = seg.get("path", "")
            if path and os.path.isfile(path):
                valid_segments.append(seg)
        if not valid_segments:
            return RenderResult(error="No valid segment files found")

        if not output:
            output = "output_moviepy_render.mp4"

        # 预览模式: 降低质量加速
        if preview_mode:
            resolution = (resolution[0] // 2, resolution[1] // 2)
            fps = min(fps, 15.0)

        # 优先 MoviePy
        if self.moviepy_available:
            result = self._render_with_moviepy(
                valid_segments, output, transition,
                transition_duration, resolution, fps, audio_path
            )
        else:
            # 降级: FFmpeg concat
            result = self._render_with_ffmpeg(
                valid_segments, output, resolution, fps, audio_path
            )

        # 补充元数据
        if result.success and os.path.isfile(result.output_path):
            result.file_size_mb = os.path.getsize(result.output_path) / (1024 * 1024)
            result.resolution = f"{resolution[0]}x{resolution[1]}"
            result.fps = fps
            result.segments_used = len(valid_segments)

        return result

    def render_preview(
        self,
        segments: List[Dict[str, Any]],
        output: str = "",
        audio_path: str = "",
    ) -> RenderResult:
        """快速预览渲染(低质量、快速)"""
        return self.render_segments(
            segments, output=output, transition="none",
            resolution=(960, 540), fps=15.0,
            audio_path=audio_path, preview_mode=True
        )

    def concatenate_clips(
        self,
        clip_paths: List[str],
        output: str = "",
        method: str = "stream_copy",
    ) -> RenderResult:
        """简单拼接多个完整视频文件(不裁剪)
        
        Args:
            clip_paths: 视频文件路径列表
            output: 输出路径
            method: "stream_copy"(无损快速) / "reencode"(统一格式)
        """
        valid = [p for p in clip_paths if os.path.isfile(p)]
        if not valid:
            return RenderResult(error="No valid clips")
        if not output:
            output = "output_concat.mp4"

        return self._render_with_ffmpeg(
            [{"path": p} for p in valid], output,
            resolution=(0, 0), fps=0, audio_path="",
            stream_copy=(method == "stream_copy")
        )

    # ------------------------------------------------------------------
    #  内部方法
    # ------------------------------------------------------------------

    def _render_with_moviepy(
        self, segments: List[Dict], output: str, transition: str,
        trans_dur: float, resolution: tuple, fps: float, audio_path: str
    ) -> RenderResult:
        """使用 MoviePy 渲染"""
        try:
            from moviepy.editor import (
                VideoFileClip, concatenate_videoclips,
                AudioFileClip, CompositeVideoClip, TextClip
            )
            from moviepy.video.fx.all import fadein, fadeout

            clips = []
            for seg in segments:
                clip = VideoFileClip(seg["path"])
                start = seg.get("start", 0)
                end = seg.get("end", clip.duration)
                if start > 0 or end < clip.duration:
                    clip = clip.subclip(start, min(end, clip.duration))
                # 统一分辨率
                if resolution[0] > 0:
                    clip = clip.resize(newsize=resolution)
                clips.append(clip)

            if not clips:
                return RenderResult(error="No clips loaded")

            # 应用转场
            if transition == "crossfade" and len(clips) > 1:
                # MoviePy crossfade: 每个clip设置fadein
                processed = [clips[0]]
                for c in clips[1:]:
                    processed.append(fadein(c, trans_dur))
                final = concatenate_videoclips(processed, method="compose")
            elif transition == "fade" and len(clips) > 1:
                processed = []
                for c in clips:
                    c = fadein(c, trans_dur / 2)
                    c = fadeout(c, trans_dur / 2)
                    processed.append(c)
                final = concatenate_videoclips(processed)
            else:
                final = concatenate_videoclips(clips)

            # 替换/添加音频
            if audio_path and os.path.isfile(audio_path):
                audio_clip = AudioFileClip(audio_path)
                # 循环或截断音频匹配视频时长
                if audio_clip.duration < final.duration:
                    from moviepy.editor import afx
                    audio_clip = afx.audio_loop(audio_clip, duration=final.duration)
                else:
                    audio_clip = audio_clip.subclip(0, final.duration)
                final = final.set_audio(audio_clip)

            # 写出
            final.write_videofile(
                output, fps=fps, codec="libx264",
                audio_codec="aac", preset="fast",
                logger=None  # 静默模式
            )

            # 清理
            final.close()
            for c in clips:
                c.close()

            duration = final.duration if hasattr(final, 'duration') else 0
            return RenderResult(
                success=True, output_path=output,
                duration_sec=duration, method="moviepy"
            )
        except ImportError:
            # MoviePy 导入失败，降级
            return self._render_with_ffmpeg(
                segments, output, resolution, fps, audio_path
            )
        except Exception as e:
            logger.debug(f"[MoviePy] Render failed: {e}, trying FFmpeg fallback")
            return self._render_with_ffmpeg(
                segments, output, resolution, fps, audio_path
            )

    def _render_with_ffmpeg(
        self, segments: List[Dict], output: str,
        resolution: tuple, fps: float, audio_path: str,
        stream_copy: bool = False
    ) -> RenderResult:
        """FFmpeg 降级渲染"""
        import subprocess
        import tempfile

        try:
            # 创建 concat 文件列表
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                concat_file = f.name
                for seg in segments:
                    path = seg["path"].replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{path}'\n")

            cmd = [self._ffmpeg, "-y", "-f", "concat", "-safe", "0",
                   "-i", concat_file]

            if stream_copy:
                cmd.extend(["-c", "copy"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])
                if resolution[0] > 0:
                    cmd.extend(["-vf", f"scale={resolution[0]}:{resolution[1]}"])
                if fps > 0:
                    cmd.extend(["-r", str(fps)])
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])

            # 添加背景音乐
            if audio_path and os.path.isfile(audio_path):
                cmd.extend(["-i", audio_path, "-map", "0:v", "-map", "1:a",
                           "-shortest"])

            cmd.append(output)
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            # 清理临时文件
            try:
                os.unlink(concat_file)
            except OSError:
                pass

            if proc.returncode == 0 and os.path.isfile(output):
                return RenderResult(
                    success=True, output_path=output, method="ffmpeg_concat"
                )
            else:
                return RenderResult(error=f"FFmpeg failed: {proc.stderr[-200:]}")

        except subprocess.TimeoutExpired:
            return RenderResult(error="FFmpeg timeout (>600s)")
        except Exception as e:
            return RenderResult(error=str(e))
