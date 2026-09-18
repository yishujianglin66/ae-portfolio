"""
media_preprocessor.py
Phase 2-3 感知层增强 — 基于 ffmpeg-python 的素材预处理模块

用途：
    对输入素材执行转码、抽帧、提取音频、获取元数据等预处理操作，
    为后续的镜头分割、音频分析、AE 合成准备标准化素材。

设计原则：
    1. 优雅降级：ffmpeg-python 或 ffmpeg 二进制不可用时返回 success=False。
    2. 原子操作：每个方法独立完成一个预处理任务，可单独调用。
    3. 结构化输出：MediaInfo / PreprocessResult dataclass，含 to_dict()。
    4. 与 video_analyzer_enhanced.py / scene_detector.py 互补：
       本模块负责素材"前处理"，后者负责"分析"。

对齐文件: ae_agent_pipeline.py perceive() / scene_detector.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = [
    "MediaInfo",
    "PreprocessResult",
    "MediaPreprocessor",
    "get_media_info",
    "extract_audio",
    "extract_thumbnails",
    "transcode",
]

# 检测依赖可用性
try:
    import ffmpeg
    _FFMPEG_PYTHON_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FFMPEG_PYTHON_AVAILABLE = False
    ffmpeg = None


def _ffmpeg_binary_available() -> bool:
    """检查 ffmpeg 二进制是否可用"""
    return shutil.which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class MediaInfo:
    """媒体元数据

    Attributes:
        success: 是否成功
        error: 错误信息
        path: 媒体路径
        duration: 时长（秒）
        width: 宽度
        height: 高度
        fps: 帧率
        codec: 编解码器
        bitrate: 比特率（bps）
        has_audio: 是否包含音频流
        audio_codec: 音频编解码器
        audio_sample_rate: 音频采样率
        audio_channels: 音频通道数
        format_name: 容器格式
        file_size: 文件大小（字节）
    """
    success: bool = False
    error: str = ""
    path: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""
    bitrate: int = 0
    has_audio: bool = False
    audio_codec: str = ""
    audio_sample_rate: int = 0
    audio_channels: int = 0
    format_name: str = ""
    file_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "path": self.path,
            "duration": round(self.duration, 4),
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 4),
            "codec": self.codec,
            "bitrate": self.bitrate,
            "has_audio": self.has_audio,
            "audio_codec": self.audio_codec,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_channels": self.audio_channels,
            "format_name": self.format_name,
            "file_size": self.file_size,
        }


@dataclass
class PreprocessResult:
    """预处理结果

    Attributes:
        success: 是否成功
        error: 错误信息
        operation: 操作名称
        input_path: 输入路径
        output_path: 输出路径
        output_paths: 多输出路径列表（如抽帧）
        duration: 处理耗时（秒）
        metadata: 附加元数据
    """
    success: bool = False
    error: str = ""
    operation: str = ""
    input_path: str = ""
    output_path: str = ""
    output_paths: list[str] = field(default_factory=list)
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "error": self.error,
            "operation": self.operation,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "output_paths": self.output_paths,
            "duration": round(self.duration, 4),
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# 预处理器
# ---------------------------------------------------------------------------

class MediaPreprocessor:
    """基于 ffmpeg-python 的素材预处理器

    Usage:
        pp = MediaPreprocessor()
        info = pp.get_info("video.mp4")
        audio_result = pp.extract_audio("video.mp4", "audio.wav")
        thumbs_result = pp.extract_thumbnails("video.mp4", "thumbs/")
    """

    def __init__(self, ffmpeg_path: str | None = None):
        """
        Args:
            ffmpeg_path: 自定义 ffmpeg 二进制路径（默认从 PATH 查找）
        """
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg")
        # ffmpeg-python 库内部使用 'ffmpeg' 命令，可以通过环境变量指定路径
        if ffmpeg_path and _FFMPEG_PYTHON_AVAILABLE:
            os.environ.setdefault("FFMPEG_BINARY", ffmpeg_path)

    # ------------------------------------------------------------------
    # 元数据
    # ------------------------------------------------------------------

    def get_info(self, media_path: str) -> MediaInfo:
        """获取媒体元数据

        Args:
            media_path: 媒体文件路径

        Returns:
            MediaInfo
        """
        if not os.path.exists(media_path):
            return MediaInfo(
                success=False,
                error=f"文件不存在: {media_path}",
                path=media_path,
            )

        if not _FFMPEG_PYTHON_AVAILABLE:
            # 降级：使用 ffprobe 命令行（ffmpeg-python 不可用时）
            return self._get_info_via_cli(media_path)

        try:
            probe = ffmpeg.probe(media_path)
        except Exception as e:
            # 尝试 CLI 降级
            cli_result = self._get_info_via_cli(media_path)
            if cli_result.success:
                return cli_result
            return MediaInfo(
                success=False,
                error=f"ffprobe 失败: {type(e).__name__}: {e}",
                path=media_path,
            )

        info = MediaInfo(
            success=True,
            path=media_path,
            file_size=os.path.getsize(media_path),
            format_name=probe.get("format", {}).get("format_name", ""),
            bitrate=int(probe.get("format", {}).get("bit_rate", 0) or 0),
            duration=float(probe.get("format", {}).get("duration", 0) or 0),
        )

        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                info.codec = stream.get("codec_name", "")
                info.width = int(stream.get("width", 0) or 0)
                info.height = int(stream.get("height", 0) or 0)
                # 帧率
                avg_frame_rate = stream.get("avg_frame_rate", "0/1")
                info.fps = self._parse_fraction(avg_frame_rate)
            elif stream.get("codec_type") == "audio":
                info.has_audio = True
                info.audio_codec = stream.get("codec_name", "")
                info.audio_sample_rate = int(stream.get("sample_rate", 0) or 0)
                info.audio_channels = int(stream.get("channels", 0) or 0)

        return info

    def _get_info_via_cli(self, media_path: str) -> MediaInfo:
        """使用 ffprobe 命令行获取元数据（降级方案）"""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return MediaInfo(
                success=False,
                error="ffmpeg-python 与 ffprobe 均不可用",
                path=media_path,
            )
        try:
            import json as _json
            cmd = [
                ffprobe, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                media_path,
            ]
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            probe = _json.loads(output)
            # 复用 get_info 的解析逻辑
            tmp = MediaInfo(success=True, path=media_path,
                            file_size=os.path.getsize(media_path))
            tmp.format_name = probe.get("format", {}).get("format_name", "")
            tmp.bitrate = int(probe.get("format", {}).get("bit_rate", 0) or 0)
            tmp.duration = float(probe.get("format", {}).get("duration", 0) or 0)
            for stream in probe.get("streams", []):
                if stream.get("codec_type") == "video":
                    tmp.codec = stream.get("codec_name", "")
                    tmp.width = int(stream.get("width", 0) or 0)
                    tmp.height = int(stream.get("height", 0) or 0)
                    tmp.fps = self._parse_fraction(
                        stream.get("avg_frame_rate", "0/1")
                    )
                elif stream.get("codec_type") == "audio":
                    tmp.has_audio = True
                    tmp.audio_codec = stream.get("codec_name", "")
                    tmp.audio_sample_rate = int(stream.get("sample_rate", 0) or 0)
                    tmp.audio_channels = int(stream.get("channels", 0) or 0)
            return tmp
        except Exception as e:
            return MediaInfo(
                success=False,
                error=f"ffprobe CLI 失败: {type(e).__name__}: {e}",
                path=media_path,
            )

    @staticmethod
    def _parse_fraction(frac: str) -> float:
        """解析 '30000/1001' 形式的分数"""
        try:
            if "/" in frac:
                num, den = frac.split("/")
                den_f = float(den)
                return float(num) / den_f if den_f != 0 else 0.0
            return float(frac)
        except (ValueError, ZeroDivisionError):
            return 0.0

    # ------------------------------------------------------------------
    # 音频提取
    # ------------------------------------------------------------------

    def extract_audio(
        self,
        video_path: str,
        output_path: str,
        audio_format: str = "wav",
        sample_rate: int = 22050,
        mono: bool = True,
    ) -> PreprocessResult:
        """从视频中提取音频

        Args:
            video_path: 输入视频路径
            output_path: 输出音频路径
            audio_format: 输出格式（wav/mp3/aac/flac）
            sample_rate: 采样率
            mono: 是否单声道

        Returns:
            PreprocessResult
        """
        if not os.path.exists(video_path):
            return PreprocessResult(
                success=False,
                error=f"输入文件不存在: {video_path}",
                operation="extract_audio",
                input_path=video_path,
            )

        # 确保输出目录存在
        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if not _FFMPEG_PYTHON_AVAILABLE:
            return self._extract_audio_via_cli(
                video_path, output_path, audio_format, sample_rate, mono
            )

        try:
            import time as _time
            start = _time.time()
            stream = ffmpeg.input(video_path)
            audio_kwargs = {"ar": sample_rate, "format": audio_format}
            if mono:
                audio_kwargs["ac"] = 1
            stream = ffmpeg.output(stream.audio, output_path, **audio_kwargs)
            ffmpeg.run(stream, quiet=True, overwrite_output=True)

            if not os.path.exists(output_path):
                return PreprocessResult(
                    success=False,
                    error="ffmpeg 执行完成但输出文件未生成",
                    operation="extract_audio",
                    input_path=video_path,
                    output_path=output_path,
                )
            return PreprocessResult(
                success=True,
                operation="extract_audio",
                input_path=video_path,
                output_path=output_path,
                duration=round(_time.time() - start, 4),
                metadata={"format": audio_format, "sample_rate": sample_rate,
                          "mono": mono},
            )
        except Exception as e:
            return PreprocessResult(
                success=False,
                error=f"音频提取失败: {type(e).__name__}: {e}",
                operation="extract_audio",
                input_path=video_path,
                output_path=output_path,
            )

    def _extract_audio_via_cli(
        self, video_path: str, output_path: str,
        audio_format: str, sample_rate: int, mono: bool,
    ) -> PreprocessResult:
        """使用 ffmpeg CLI 直接提取音频（降级方案）"""
        if not self.ffmpeg_path:
            return PreprocessResult(
                success=False,
                error="ffmpeg-python 与 ffmpeg 二进制均不可用",
                operation="extract_audio",
                input_path=video_path,
            )
        try:
            import time as _time
            start = _time.time()
            cmd = [self.ffmpeg_path, "-y", "-i", video_path,
                   "-ar", str(sample_rate), "-f", audio_format]
            if mono:
                cmd.append("-ac")
                cmd.append("1")
            cmd.append(output_path)
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            return PreprocessResult(
                success=True,
                operation="extract_audio",
                input_path=video_path,
                output_path=output_path,
                duration=round(_time.time() - start, 4),
                metadata={"format": audio_format, "sample_rate": sample_rate,
                          "mono": mono, "via": "cli"},
            )
        except subprocess.CalledProcessError as e:
            return PreprocessResult(
                success=False,
                error=f"ffmpeg CLI 失败: {e}",
                operation="extract_audio",
                input_path=video_path,
                output_path=output_path,
            )

    # ------------------------------------------------------------------
    # 抽帧
    # ------------------------------------------------------------------

    def extract_thumbnails(
        self,
        video_path: str,
        output_dir: str,
        interval: float = 1.0,
        width: int | None = None,
        height: int | None = None,
        filename_pattern: str = "thumb_%04d.jpg",
    ) -> PreprocessResult:
        """从视频中按间隔抽取缩略图

        Args:
            video_path: 输入视频路径
            output_dir: 输出目录
            interval: 抽帧间隔（秒）
            width: 缩略图宽度（保持比例则只设一个）
            height: 缩略图高度
            filename_pattern: 文件名模式（支持 %d / %04d）

        Returns:
            PreprocessResult，output_paths 为生成的所有缩略图路径
        """
        if not os.path.exists(video_path):
            return PreprocessResult(
                success=False,
                error=f"输入文件不存在: {video_path}",
                operation="extract_thumbnails",
                input_path=video_path,
            )

        os.makedirs(output_dir, exist_ok=True)
        output_pattern = os.path.join(output_dir, filename_pattern)

        if not _FFMPEG_PYTHON_AVAILABLE:
            return self._extract_thumbnails_via_cli(
                video_path, output_pattern, interval, width, height
            )

        try:
            import glob as _glob
            import time as _time
            start = _time.time()
            stream = ffmpeg.input(video_path)
            vf_kwargs = {"fps": 1.0 / interval if interval > 0 else 1.0}
            scale_filter = ""
            if width and height:
                scale_filter = f"scale={width}:{height}"
            elif width:
                scale_filter = f"scale={width}:-1"
            elif height:
                scale_filter = f"scale=-1:{height}"
            if scale_filter:
                vf_kwargs["filter:v"] = scale_filter
            stream = ffmpeg.output(stream, output_pattern, **vf_kwargs)
            ffmpeg.run(stream, quiet=True, overwrite_output=True)

            # 收集生成的文件
            base_pattern = filename_pattern.replace("%04d", "*").replace("%d", "*")
            search_pattern = os.path.join(output_dir, base_pattern)
            output_paths = sorted(_glob.glob(search_pattern))

            return PreprocessResult(
                success=len(output_paths) > 0,
                error="" if output_paths else "未生成任何缩略图",
                operation="extract_thumbnails",
                input_path=video_path,
                output_path=output_dir,
                output_paths=output_paths,
                duration=round(_time.time() - start, 4),
                metadata={"interval": interval, "width": width,
                          "height": height, "count": len(output_paths)},
            )
        except Exception as e:
            return PreprocessResult(
                success=False,
                error=f"抽帧失败: {type(e).__name__}: {e}",
                operation="extract_thumbnails",
                input_path=video_path,
                output_path=output_dir,
            )

    def _extract_thumbnails_via_cli(
        self, video_path: str, output_pattern: str,
        interval: float, width: int | None, height: int | None,
    ) -> PreprocessResult:
        """使用 ffmpeg CLI 抽帧（降级方案）"""
        if not self.ffmpeg_path:
            return PreprocessResult(
                success=False,
                error="ffmpeg-python 与 ffmpeg 二进制均不可用",
                operation="extract_thumbnails",
                input_path=video_path,
            )
        try:
            import glob as _glob
            import time as _time
            start = _time.time()
            cmd = [self.ffmpeg_path, "-y", "-i", video_path,
                   "-vf", f"fps={1.0/interval if interval > 0 else 1.0}"]
            scale_filter = ""
            if width and height:
                scale_filter = f"scale={width}:{height}"
            elif width:
                scale_filter = f"scale={width}:-1"
            elif height:
                scale_filter = f"scale=-1:{height}"
            if scale_filter:
                cmd[-1] = f"fps={1.0/interval if interval > 0 else 1.0},{scale_filter}"
            cmd.append(output_pattern)
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)

            output_dir = os.path.dirname(output_pattern)
            base_pattern = os.path.basename(output_pattern).replace("%04d", "*").replace("%d", "*")
            search_pattern = os.path.join(output_dir, base_pattern)
            output_paths = sorted(_glob.glob(search_pattern))

            return PreprocessResult(
                success=len(output_paths) > 0,
                error="" if output_paths else "未生成任何缩略图",
                operation="extract_thumbnails",
                input_path=video_path,
                output_path=output_dir,
                output_paths=output_paths,
                duration=round(_time.time() - start, 4),
                metadata={"interval": interval, "via": "cli",
                          "count": len(output_paths)},
            )
        except subprocess.CalledProcessError as e:
            return PreprocessResult(
                success=False,
                error=f"ffmpeg CLI 失败: {e}",
                operation="extract_thumbnails",
                input_path=video_path,
            )

    # ------------------------------------------------------------------
    # 转码
    # ------------------------------------------------------------------

    def transcode(
        self,
        input_path: str,
        output_path: str,
        video_codec: str = "libx264",
        audio_codec: str = "aac",
        crf: int = 23,
        preset: str = "medium",
        width: int | None = None,
        height: int | None = None,
        fps: float | None = None,
    ) -> PreprocessResult:
        """视频转码

        Args:
            input_path: 输入路径
            output_path: 输出路径
            video_codec: 视频编码器（libx264/libx265/mpeg4...）
            audio_codec: 音频编码器（aac/mp3/pcm_s16le...）
            crf: 恒定质量（0-51，越小质量越高）
            preset: 编码速度预设（ultrafast/fast/medium/slow...）
            width: 目标宽度（保持比例则只设一个）
            height: 目标高度
            fps: 目标帧率

        Returns:
            PreprocessResult
        """
        if not os.path.exists(input_path):
            return PreprocessResult(
                success=False,
                error=f"输入文件不存在: {input_path}",
                operation="transcode",
                input_path=input_path,
            )

        out_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(out_dir, exist_ok=True)

        if not _FFMPEG_PYTHON_AVAILABLE:
            return self._transcode_via_cli(
                input_path, output_path, video_codec, audio_codec,
                crf, preset, width, height, fps
            )

        try:
            import time as _time
            start = _time.time()
            stream = ffmpeg.input(input_path)
            output_kwargs = {
                "c:v": video_codec,
                "c:a": audio_codec,
                "crf": crf,
                "preset": preset,
            }
            vf_filters = []
            if width and height:
                vf_filters.append(f"scale={width}:{height}")
            elif width:
                vf_filters.append(f"scale={width}:-1")
            elif height:
                vf_filters.append(f"scale=-1:{height}")
            if fps:
                vf_filters.append(f"fps={fps}")
            if vf_filters:
                output_kwargs["vf"] = ",".join(vf_filters)
            stream = ffmpeg.output(stream, output_path, **output_kwargs)
            ffmpeg.run(stream, quiet=True, overwrite_output=True)

            if not os.path.exists(output_path):
                return PreprocessResult(
                    success=False,
                    error="ffmpeg 执行完成但输出文件未生成",
                    operation="transcode",
                    input_path=input_path,
                    output_path=output_path,
                )
            return PreprocessResult(
                success=True,
                operation="transcode",
                input_path=input_path,
                output_path=output_path,
                duration=round(_time.time() - start, 4),
                metadata={
                    "video_codec": video_codec, "audio_codec": audio_codec,
                    "crf": crf, "preset": preset,
                    "width": width, "height": height, "fps": fps,
                    "output_size": os.path.getsize(output_path),
                },
            )
        except Exception as e:
            return PreprocessResult(
                success=False,
                error=f"转码失败: {type(e).__name__}: {e}",
                operation="transcode",
                input_path=input_path,
                output_path=output_path,
            )

    def _transcode_via_cli(
        self, input_path: str, output_path: str,
        video_codec: str, audio_codec: str, crf: int, preset: str,
        width: int | None, height: int | None, fps: float | None,
    ) -> PreprocessResult:
        """使用 ffmpeg CLI 转码（降级方案）"""
        if not self.ffmpeg_path:
            return PreprocessResult(
                success=False,
                error="ffmpeg-python 与 ffmpeg 二进制均不可用",
                operation="transcode",
                input_path=input_path,
            )
        try:
            import time as _time
            start = _time.time()
            cmd = [self.ffmpeg_path, "-y", "-i", input_path,
                   "-c:v", video_codec, "-c:a", audio_codec,
                   "-crf", str(crf), "-preset", preset]
            vf_filters = []
            if width and height:
                vf_filters.append(f"scale={width}:{height}")
            elif width:
                vf_filters.append(f"scale={width}:-1")
            elif height:
                vf_filters.append(f"scale=-1:{height}")
            if fps:
                vf_filters.append(f"fps={fps}")
            if vf_filters:
                cmd.extend(["-vf", ",".join(vf_filters)])
            cmd.append(output_path)
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            return PreprocessResult(
                success=True,
                operation="transcode",
                input_path=input_path,
                output_path=output_path,
                duration=round(_time.time() - start, 4),
                metadata={"via": "cli",
                          "output_size": os.path.getsize(output_path)},
            )
        except subprocess.CalledProcessError as e:
            return PreprocessResult(
                success=False,
                error=f"ffmpeg CLI 失败: {e}",
                operation="transcode",
                input_path=input_path,
                output_path=output_path,
            )


# ---------------------------------------------------------------------------
# 模块级便捷 API
# ---------------------------------------------------------------------------

def get_media_info(media_path: str) -> MediaInfo:
    """便捷 API：获取媒体元数据"""
    return MediaPreprocessor().get_info(media_path)


def extract_audio(
    video_path: str, output_path: str, **kwargs
) -> PreprocessResult:
    """便捷 API：从视频提取音频"""
    return MediaPreprocessor().extract_audio(video_path, output_path, **kwargs)


def extract_thumbnails(
    video_path: str, output_dir: str, **kwargs
) -> PreprocessResult:
    """便捷 API：从视频抽取缩略图"""
    return MediaPreprocessor().extract_thumbnails(video_path, output_dir, **kwargs)


def transcode(
    input_path: str, output_path: str, **kwargs
) -> PreprocessResult:
    """便捷 API：视频转码"""
    return MediaPreprocessor().transcode(input_path, output_path, **kwargs)


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    print(f"ffmpeg-python available: {_FFMPEG_PYTHON_AVAILABLE}")
    print(f"ffmpeg binary available: {_ffmpeg_binary_available()}")
    if len(sys.argv) > 1:
        pp = MediaPreprocessor()
        info = pp.get_info(sys.argv[1])
        print(f"\n媒体: {sys.argv[1]}")
        print(f"成功: {info.success}")
        if info.success:
            print(f"时长: {info.duration:.2f}s")
            print(f"分辨率: {info.width}x{info.height}")
            print(f"帧率: {info.fps:.2f}fps")
            print(f"编码: {info.codec}")
            print(f"包含音频: {info.has_audio}")
            if info.has_audio:
                print(f"音频编码: {info.audio_codec}")
                print(f"采样率: {info.audio_sample_rate}Hz")
        else:
            print(f"错误: {info.error}")
