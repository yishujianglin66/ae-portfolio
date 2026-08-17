"""software_sdk/adapters/ffmpeg_adapter.py - FFmpeg 适配器

通过 subprocess 调用 FFmpeg CLI 实现视频/音频处理。
支持：转码、拼接、滤镜、截图、音频提取、GIF 生成等。
"""
from __future__ import annotations

import os
import shutil
import logging
import subprocess
from typing import Any, List, Optional

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareType,
    Task,
)


class FFmpegAdapter(BaseSoftwareAdapter):
    """FFmpeg 适配器 - 通过 subprocess 调用 FFmpeg CLI。

    支持任务类型：
    - transcode: 视频转码（格式/编码/分辨率/帧率）
    - concat: 多文件拼接
    - filter: 应用视频/音频滤镜
    - screenshot: 截取指定时间帧
    - extract_audio: 提取音频轨道
    - gif: 视频转 GIF
    - probe: 获取媒体文件信息（ffprobe）
    - trim: 裁剪片段
    - overlay: 叠加水印/图片
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.FFMPEG)
        super().__init__(config, logger)
        self._ffmpeg_path: Optional[str] = None
        self._ffprobe_path: Optional[str] = None

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.FFMPEG,
            capabilities={
                SoftwareCapability.VIDEO_ENCODING,
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.RENDERING,
                SoftwareCapability.BATCH_PROCESSING,
                SoftwareCapability.EDITING,
            },
            supported_formats_input={
                ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv",
                ".wmv", ".m4v", ".ts", ".mp3", ".wav", ".aac",
                ".flac", ".ogg", ".png", ".jpg", ".gif",
            },
            supported_formats_output={
                ".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif",
                ".mp3", ".wav", ".aac", ".flac", ".png", ".jpg",
            },
            max_resolution=(7680, 4320),  # 8K
            max_framerate=240.0,
            gpu_accelerated=True,  # NVENC/QSV 支持
            scriptable=True,
        )

    def connect(self) -> bool:
        """连接 FFmpeg（检测可执行文件是否存在）。"""
        try:
            self.logger.info("Locating FFmpeg executable...")
            self._status = ConnectionStatus.CONNECTING

            # 优先使用配置中的路径
            if self.config.executable_path and os.path.isfile(self.config.executable_path):
                self._ffmpeg_path = self.config.executable_path
            else:
                self._ffmpeg_path = shutil.which("ffmpeg")

            # ffprobe
            self._ffprobe_path = shutil.which("ffprobe")

            if self._ffmpeg_path:
                self._set_connected()
                self.logger.info(f"FFmpeg found: {self._ffmpeg_path}")
                return True
            else:
                self._set_error("FFmpeg not found in PATH or config")
                return False
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """断开（清理引用）。"""
        self._status = ConnectionStatus.DISCONNECTED
        self._ffmpeg_path = None
        self._ffprobe_path = None
        self.logger.info("FFmpeg disconnected")
        return True

    def health_check(self) -> bool:
        """检查 FFmpeg 是否可用。"""
        if not self._ffmpeg_path:
            return False
        try:
            result = subprocess.run(
                [self._ffmpeg_path, "-version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def execute_task(self, task: Task) -> Any:
        """执行 FFmpeg 任务。"""
        self._mark_task_start()
        try:
            task_type = task.task_type
            params = task.params

            handlers = {
                "transcode": self._transcode,
                "concat": self._concat,
                "filter": self._filter,
                "screenshot": self._screenshot,
                "extract_audio": self._extract_audio,
                "gif": self._gif,
                "probe": self._probe,
                "trim": self._trim,
                "overlay": self._overlay,
            }

            handler = handlers.get(task_type)
            if handler is None:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
            return handler(params)
        except Exception as e:
            self._set_error(f"Task execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    # ------------------------------------------------------------------
    # 内部：subprocess 执行
    # ------------------------------------------------------------------
    def _run_ffmpeg(self, args: List[str], timeout: int = 300) -> dict:
        """执行 ffmpeg 命令。

        Args:
            args: ffmpeg 参数列表（不含 ffmpeg 本身）
            timeout: 超时秒数

        Returns:
            {"success": bool, "stdout": str, "stderr": str, "returncode": int}
        """
        if not self._ffmpeg_path:
            return {"success": False, "error": "FFmpeg not connected"}

        cmd = [self._ffmpeg_path, "-y"] + args  # -y 覆盖输出
        self.logger.info(f"[FFmpeg] Running: {' '.join(cmd[:10])}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            success = result.returncode == 0
            if not success:
                self.logger.error(f"[FFmpeg] Failed (rc={result.returncode}): {result.stderr[-500:]}")
            return {
                "success": success,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"FFmpeg timeout after {timeout}s"}
        except FileNotFoundError:
            return {"success": False, "error": f"FFmpeg not found: {self._ffmpeg_path}"}

    def _run_ffprobe(self, input_path: str) -> dict:
        """执行 ffprobe 获取媒体信息。"""
        if not self._ffprobe_path:
            return {"success": False, "error": "ffprobe not found"}

        cmd = [
            self._ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            input_path,
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            if result.returncode == 0:
                import json
                return {"success": True, "data": json.loads(result.stdout)}
            return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 任务处理器
    # ------------------------------------------------------------------
    def _transcode(self, params: dict) -> dict:
        """视频转码。

        params:
            input: 输入文件路径
            output: 输出文件路径
            codec: 视频编码器 (默认 libx264)
            audio_codec: 音频编码器 (默认 aac)
            resolution: 分辨率 (如 "1920x1080")
            fps: 帧率
            crf: 质量 (0-51, 默认 23)
            preset: 编码速度预设 (默认 medium)
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        args = ["-i", input_path]

        codec = params.get("codec", "libx264")
        args += ["-c:v", codec]

        audio_codec = params.get("audio_codec", "aac")
        args += ["-c:a", audio_codec]

        if params.get("resolution"):
            w, h = params["resolution"].split("x")
            args += ["-vf", f"scale={w}:{h}"]

        if params.get("fps"):
            args += ["-r", str(params["fps"])]

        crf = params.get("crf", 23)
        if codec == "libx264":
            args += ["-crf", str(crf)]

        preset = params.get("preset", "medium")
        if codec in ("libx264", "libx265"):
            args += ["-preset", preset]

        # GPU 加速 (NVENC)
        if params.get("gpu") and codec == "h264_nvenc":
            args = ["-i", input_path, "-c:v", "h264_nvenc", "-c:a", audio_codec]

        args.append(output_path)
        result = self._run_ffmpeg(args, timeout=params.get("timeout", 600))
        result["output"] = output_path
        return result

    def _concat(self, params: dict) -> dict:
        """多文件拼接。

        params:
            inputs: 输入文件列表
            output: 输出文件路径
            method: "concat"(默认) 或 "filter"
        """
        inputs = params.get("inputs", [])
        output_path = params.get("output", "")
        if len(inputs) < 2 or not output_path:
            return {"success": False, "error": "Need at least 2 inputs and output path"}

        # 使用 concat demuxer（需要临时文件列表）
        import tempfile
        list_content = "\n".join(f"file '{p}'" for p in inputs)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(list_content)
            list_file = f.name

        try:
            args = [
                "-f", "concat", "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_path,
            ]
            result = self._run_ffmpeg(args)
            result["output"] = output_path
            return result
        finally:
            os.unlink(list_file)

    def _filter(self, params: dict) -> dict:
        """应用滤镜。

        params:
            input: 输入文件
            output: 输出文件
            video_filter: 视频滤镜字符串 (如 "blur=5:5")
            audio_filter: 音频滤镜字符串
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        args = ["-i", input_path]

        vf = params.get("video_filter", "")
        af = params.get("audio_filter", "")
        if vf:
            args += ["-vf", vf]
        if af:
            args += ["-af", af]

        args.append(output_path)
        result = self._run_ffmpeg(args)
        result["output"] = output_path
        return result

    def _screenshot(self, params: dict) -> dict:
        """截取帧。

        params:
            input: 输入文件
            output: 输出图片路径
            time: 截取时间点 (如 "00:01:30" 或秒数)
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        time_point = params.get("time", "0")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        args = ["-i", input_path, "-ss", str(time_point), "-frames:v", "1", output_path]
        result = self._run_ffmpeg(args)
        result["output"] = output_path
        return result

    def _extract_audio(self, params: dict) -> dict:
        """提取音频。

        params:
            input: 输入视频文件
            output: 输出音频文件
            codec: 音频编码器 (默认 aac)
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        codec = params.get("codec", "aac")
        args = ["-i", input_path, "-vn", "-c:a", codec, output_path]
        result = self._run_ffmpeg(args)
        result["output"] = output_path
        return result

    def _gif(self, params: dict) -> dict:
        """视频转 GIF。

        params:
            input: 输入文件
            output: 输出 GIF 路径
            fps: GIF 帧率 (默认 15)
            width: GIF 宽度 (默认 480)
            start: 起始时间
            duration: 持续时间
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        fps = params.get("fps", 15)
        width = params.get("width", 480)
        start = params.get("start", "0")
        duration = params.get("duration", "")

        args = ["-i", input_path, "-ss", str(start)]
        if duration:
            args += ["-t", str(duration)]

        # 使用调色板优化 GIF 质量
        vf = f"fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
        args += ["-vf", vf, output_path]

        result = self._run_ffmpeg(args, timeout=120)
        result["output"] = output_path
        return result

    def _probe(self, params: dict) -> dict:
        """获取媒体文件信息。

        params:
            input: 输入文件路径
        """
        input_path = params.get("input", "")
        if not input_path:
            return {"success": False, "error": "Missing input path"}
        return self._run_ffprobe(input_path)

    def _trim(self, params: dict) -> dict:
        """裁剪片段。

        params:
            input: 输入文件
            output: 输出文件
            start: 起始时间
            end: 结束时间 (或 duration)
        """
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        if not input_path or not output_path:
            return {"success": False, "error": "Missing input/output path"}

        args = ["-i", input_path]
        if params.get("start"):
            args += ["-ss", str(params["start"])]
        if params.get("end"):
            args += ["-to", str(params["end"])]
        elif params.get("duration"):
            args += ["-t", str(params["duration"])]

        args += ["-c", "copy", output_path]
        result = self._run_ffmpeg(args)
        result["output"] = output_path
        return result

    def _overlay(self, params: dict) -> dict:
        """叠加水印/图片。

        params:
            input: 主视频
            overlay: 叠加图片/视频
            output: 输出文件
            position: 位置 (默认 "10:10")
        """
        input_path = params.get("input", "")
        overlay_path = params.get("overlay", "")
        output_path = params.get("output", "")
        if not all([input_path, overlay_path, output_path]):
            return {"success": False, "error": "Missing input/overlay/output path"}

        position = params.get("position", "10:10")
        args = [
            "-i", input_path,
            "-i", overlay_path,
            "-filter_complex", f"overlay={position}",
            output_path,
        ]
        result = self._run_ffmpeg(args)
        result["output"] = output_path
        return result
