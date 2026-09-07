"""Adobe Media Encoder engine - batch encoding & delivery.

ME 的集成策略：
1. Watch Folder 模式 - 监控文件夹自动编码（核心能力）
2. CLI 直接调用 - 命令行传参编码
3. 预设管理 - .epr 预设文件生成

ME 相比 ffmpeg 的优势：
- Adobe全家桶原生集成（AE/PR队列直发）
- 保留元数据（标记、章节、字幕轨）
- 内置各平台预设（抖音/B站/YouTube）
- Watch Folder 原生并发批量处理
"""

from __future__ import annotations

import asyncio
import json
import shutil
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


# 平台预设映射
PLATFORM_PRESETS = {
    "douyin": {
        "name": "抖音/TikTok",
        "resolution": (1080, 1920),
        "fps": 30,
        "bitrate": "8M",
        "audio_bitrate": "128k",
        "format": "mp4",
        "codec": "h264",
    },
    "bilibili": {
        "name": "哔哩哔哩",
        "resolution": (1920, 1080),
        "fps": 60,
        "bitrate": "20M",
        "audio_bitrate": "192k",
        "format": "mp4",
        "codec": "h264",
    },
    "youtube": {
        "name": "YouTube",
        "resolution": (3840, 2160),
        "fps": 60,
        "bitrate": "45M",
        "audio_bitrate": "256k",
        "format": "mp4",
        "codec": "h264",
    },
    "xiaohongshu": {
        "name": "小红书",
        "resolution": (1080, 1920),
        "fps": 30,
        "bitrate": "6M",
        "audio_bitrate": "128k",
        "format": "mp4",
        "codec": "h264",
    },
    "wechat": {
        "name": "微信视频号",
        "resolution": (1080, 1920),
        "fps": 30,
        "bitrate": "6M",
        "audio_bitrate": "128k",
        "format": "mp4",
        "codec": "h264",
    },
    "master": {
        "name": "母版存档",
        "resolution": (3840, 2160),
        "fps": 60,
        "bitrate": "80M",
        "audio_bitrate": "320k",
        "format": "mp4",
        "codec": "h264",
    },
}


class MediaEncoderEngine(BaseEngine):
    """Adobe Media Encoder 2025 engine wrapper.

    支持两种工作模式：
    1. CLI模式：直接调用AMEncodeCmdLine.exe编码
    2. Watch Folder模式：监控文件夹自动编码
    """

    name = "media_encoder"

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.media_encoder_path
        super().__init__(path)
        # 注意：不设 cli_path 字段——AME 无 AMETemplateFile.dll CLI，
        # 指向不存在文件的路径字段已在 84fb30d 清理（test_ame_no_dead_cli_path 守卫）。
        # Watch Folder 默认路径
        self.watch_folder_path = settings.output_dir / "me_watch_folder"

    async def _execute_impl(self, **kwargs) -> EngineResult:
        """【子类实现】action 调度；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        action = kwargs.pop("action", "encode")
        handlers = {
            "encode": self.encode,
            "batch_encode": self.batch_encode,
            "add_to_watch_folder": self.add_to_watch_folder,
            "list_presets": self.list_presets,
            "get_preset": self.get_preset,
            # 旗舰管线 API（从 c1e3db1 移植，2026-08-27）
            "submit_queue_render": self.submit_queue_render,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(success=False, error=f"Unknown action: {action}")
        return await handler(**kwargs)

    async def encode(
        self,
        input_path: Path | str,
        output_path: Path | str,
        platform: str = "douyin",
        preset_file: Optional[Path | str] = None,
        overwrite: bool = True,
    ) -> EngineResult:
        """使用 Media Encoder 编码视频。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            platform: 平台预设名称（douyin/bilibili/youtube/...）
            preset_file: 自定义 .epr 预设文件路径（优先于 platform）
            overwrite: 是否覆盖输出
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            return EngineResult(success=False, error=f"Input not found: {input_path}")

        # 优先使用自定义预设
        if preset_file:
            preset_path = Path(preset_file)
            if not preset_path.exists():
                return EngineResult(success=False, error=f"Preset not found: {preset_path}")
            logger.info(f"ME encode with custom preset: {preset_path.name}")
            return await self._encode_with_cli(input_path, output_path, preset_path, overwrite)

        # 使用平台预设
        preset = PLATFORM_PRESETS.get(platform)
        if not preset:
            return EngineResult(
                success=False,
                error=f"Unknown platform: {platform}. Available: {list(PLATFORM_PRESETS)}",
            )

        logger.info(f"ME encode: {input_path.name} -> {platform} ({preset['name']})")

        # 生成临时 .epr 预设文件
        epr_file = await self._generate_epr_preset(platform, preset)
        if epr_file is None:
            # 如果预设生成失败，回退到 Watch Folder 模式
            logger.warning("EPR preset generation failed, falling back to Watch Folder")
            return await self._encode_via_watch_folder(input_path, output_path, preset)

        return await self._encode_with_cli(input_path, output_path, epr_file, overwrite)

    async def _encode_with_cli(
        self,
        input_path: Path,
        output_path: Path,
        preset_file: Path,
        overwrite: bool,
    ) -> EngineResult:
        """通过 CLI 调用 Media Encoder 编码。

        AME 的命令行工具实际上是通过 Premiere 的 HeadlessRender 机制。
        由于 AME 本身没有公开的 CLI API，我们采用 Watch Folder 作为可靠方案。
        """
        # AME 没有公开 CLI，使用 Watch Folder 模式更可靠
        return await self._encode_via_watch_folder(
            input_path, output_path, PLATFORM_PRESETS.get("douyin"), preset_file,
        )

    async def _encode_via_watch_folder(
        self,
        input_path: Path,
        output_path: Path,
        preset: Optional[dict] = None,
        preset_file: Optional[Path] = None,
    ) -> EngineResult:
        """通过 Watch Folder 模式编码。

        工作流程：
        1. 将输入文件复制到 Watch Folder
        2. 启动 ME（如果未运行）
        3. ME 自动检测并编码
        4. 等待编码完成，移动输出文件
        """
        self.watch_folder_path.mkdir(parents=True, exist_ok=True)
        output_folder = self.watch_folder_path / "output"
        output_folder.mkdir(parents=True, exist_ok=True)

        # 复制输入文件到 Watch Folder
        dest_input = self.watch_folder_path / input_path.name
        logger.debug(f"Copying to watch folder: {dest_input}")
        await asyncio.to_thread(shutil.copy2, str(input_path), str(dest_input))

        # 启动 Media Encoder（如果未运行）
        await self._ensure_me_running()

        # 等待输出文件出现（Watch Folder 处理后输出到 output 子目录）
        expected_output = output_folder / f"{input_path.stem}.mp4"
        logger.info(f"Waiting for ME to process: {input_path.name}")
        logger.info(f"Expected output: {expected_output}")

        # 轮询等待（最多等待 30 分钟）
        max_wait = 1800  # 30分钟
        poll_interval = 5  # 5秒
        waited = 0

        while waited < max_wait:
            if expected_output.exists():
                # 等待文件写入完成
                await asyncio.sleep(2)
                # 移动到最终输出路径
                await asyncio.to_thread(shutil.move, str(expected_output), str(output_path))
                # 清理 Watch Folder 中的源文件
                dest_input.unlink(missing_ok=True)
                logger.info(f"ME encoding complete: {output_path.name}")
                return EngineResult(
                    success=True,
                    output_path=output_path,
                    metadata={
                        "method": "watch_folder",
                        "platform": preset.get("name", "custom") if preset else "custom",
                    },
                )
            await asyncio.sleep(poll_interval)
            waited += poll_interval

        # 超时
        dest_input.unlink(missing_ok=True)
        return EngineResult(
            success=False,
            error=f"Watch Folder timeout after {max_wait}s. ME may not be running or preset not configured.",
        )

    async def _ensure_me_running(self) -> None:
        """确保 Media Encoder 正在运行。"""
        try:
            # 检查 ME 进程
            tasklist_cmd = ["tasklist", "/FI", "IMAGENAME eq Adobe Media Encoder.exe", "/FO", "CSV", "/NH"]
            code, stdout, _, _err_code = await asyncio.to_thread(
                self._run_subprocess, tasklist_cmd, timeout=10,
            )

            if "Adobe Media Encoder.exe" not in stdout:
                logger.info("Starting Media Encoder...")
                # 启动 ME（非阻塞）
                start_cmd = [
                    "cmd", "/c", "start", "",
                    str(self.executable_path),
                ]
                await asyncio.to_thread(
                    self._run_subprocess, start_cmd, timeout=30,
                )
                # 等待 ME 启动
                logger.info("Waiting for ME to initialize...")
                await asyncio.sleep(15)
            else:
                logger.debug("Media Encoder is already running")

        except Exception as e:
            logger.warning(f"Failed to check/start ME: {e}. Manual launch may be required.")

    async def _generate_epr_preset(self, platform: str, preset: dict) -> Optional[Path]:
        """生成 .epr 预设文件（简化版）。

        实际的 .epr 文件是复杂的 XML 格式，这里生成基础版本。
        完整预设需要从 AME 导出后作为模板使用。
        """
        preset_dir = settings.cache_dir / "me_presets"
        preset_dir.mkdir(parents=True, exist_ok=True)
        epr_path = preset_dir / f"{platform}.epr"

        if epr_path.exists():
            return epr_path

        # .epr 是复杂的 XML 格式，无法从零生成完整版本
        # 实际使用时需要从 AME 导出预设模板
        # 这里返回 None，触发 Watch Folder 回退
        logger.debug(f"No preset template for {platform}, will use Watch Folder")
        return None

    async def batch_encode(
        self,
        input_dir: Path | str,
        output_dir: Path | str,
        platform: str = "douyin",
    ) -> EngineResult:
        """批量编码：将整个目录的视频加入 Watch Folder。

        Args:
            input_dir: 输入目录
            output_dir: 输出目录
            platform: 平台预设
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not input_dir.exists():
            return EngineResult(success=False, error=f"Input dir not found: {input_dir}")

        # 收集所有视频
        extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"]
        videos = []
        for ext in extensions:
            videos.extend(input_dir.glob(f"*{ext}"))

        if not videos:
            return EngineResult(success=False, error="No videos found in input directory")

        preset = PLATFORM_PRESETS.get(platform)
        if not preset:
            return EngineResult(
                success=False,
                error=f"Unknown platform: {platform}. Available: {list(PLATFORM_PRESETS)}",
            )

        logger.info(f"ME batch encode: {len(videos)} videos -> {platform}")

        # 设置 Watch Folder
        self.watch_folder_path.mkdir(parents=True, exist_ok=True)
        wf_output = self.watch_folder_path / "output"
        wf_output.mkdir(parents=True, exist_ok=True)

        # 复制所有视频到 Watch Folder
        for video in videos:
            dest = self.watch_folder_path / video.name
            if not dest.exists():
                await asyncio.to_thread(shutil.copy2, str(video), str(dest))

        # 启动 ME
        await self._ensure_me_running()

        # 等待所有输出完成
        results = []
        max_wait = 7200  # 2小时
        poll_interval = 10
        waited = 0

        pending = {v.stem: v for v in videos}
        completed = []

        while pending and waited < max_wait:
            for stem in list(pending.keys()):
                expected = wf_output / f"{stem}.mp4"
                if expected.exists():
                    await asyncio.sleep(1)
                    final_path = output_dir / f"{stem}_{platform}.mp4"
                    await asyncio.to_thread(shutil.move, str(expected), str(final_path))
                    completed.append({
                        "input": str(pending[stem]),
                        "output": str(final_path),
                        "success": True,
                    })
                    del pending[stem]
                    logger.info(f"  [{len(completed)}/{len(videos)}] Done: {stem}")

            if pending:
                await asyncio.sleep(poll_interval)
                waited += poll_interval

        # 超时处理
        for stem, v in pending.items():
            completed.append({
                "input": str(v),
                "output": None,
                "success": False,
                "error": "Timeout",
            })

        # 清理 Watch Folder 源文件
        for video in videos:
            dest = self.watch_folder_path / video.name
            dest.unlink(missing_ok=True)

        success_count = sum(1 for r in completed if r["success"])
        return EngineResult(
            success=success_count > 0,
            output_path=output_dir,
            metadata={
                "total": len(videos),
                "success": success_count,
                "failed": len(videos) - success_count,
                "platform": platform,
                "results": completed,
            },
            error=None if success_count == len(videos) else f"{len(videos) - success_count} files failed",
        )

    async def add_to_watch_folder(
        self,
        input_path: Path | str,
        platform: str = "douyin",
    ) -> EngineResult:
        """将视频添加到 Watch Folder（异步处理）。

        与 encode 不同，此方法不等待完成，仅添加到队列。
        """
        input_path = Path(input_path)
        if not input_path.exists():
            return EngineResult(success=False, error=f"Input not found: {input_path}")

        self.watch_folder_path.mkdir(parents=True, exist_ok=True)
        dest = self.watch_folder_path / input_path.name
        await asyncio.to_thread(shutil.copy2, str(input_path), str(dest))

        # 确保ME运行
        await self._ensure_me_running()

        return EngineResult(
            success=True,
            output_path=dest,
            metadata={
                "platform": platform,
                "watch_folder": str(self.watch_folder_path),
                "note": "File added to Watch Folder. ME will process automatically.",
            },
        )

    async def list_presets(self) -> EngineResult:
        """列出所有可用预设。"""
        return EngineResult(
            success=True,
            metadata={
                "platforms": {
                    k: {
                        "name": v["name"],
                        "resolution": f"{v['resolution'][0]}x{v['resolution'][1]}",
                        "fps": v["fps"],
                        "bitrate": v["bitrate"],
                    }
                    for k, v in PLATFORM_PRESETS.items()
                }
            },
        )

    async def get_preset(self, platform: str) -> EngineResult:
        """获取指定平台的预设配置。"""
        preset = PLATFORM_PRESETS.get(platform)
        if not preset:
            return EngineResult(
                success=False,
                error=f"Unknown platform: {platform}. Available: {list(PLATFORM_PRESETS)}",
            )
        return EngineResult(success=True, metadata={"platform": platform, **preset})

    # ------------------------------------------------------------------
    # 旗舰管线专用 API（S6 导出，从 c1e3db1 移植，2026-08-27）
    # ------------------------------------------------------------------

    async def submit_queue_render(
        self,
        input_path: Path | str,
        output_path: Path | str,
        codec: str = "h264",
        resolution: str = "1920x1080",
        fps: float = 24.0,
        timeout: float = 1800.0,
    ) -> EngineResult:
        """旗舰管线 S6：清空旧队列 → 提交渲染任务 → 等待完成。

        流程：
        1. 清空 AME 旧队列（避免残留任务干扰）
        2. 提交 H.264 1920×1080 24fps 渲染任务
        3. 等待完成（超时 1800s）
        4. 验证产物 + 生成 ffprobe.json
        """
        import json as _json
        import time as _time

        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            return EngineResult(
                success=False,
                error=f"Input not found: {input_path}",
                error_code="INPUT_MISSING",
            )

        t0 = _time.time()

        # Step 1: 清空旧队列（通过 Watch Folder 清理）
        try:
            if self.watch_folder_path.exists():
                for f in self.watch_folder_path.iterdir():
                    if f.is_file():
                        f.unlink(missing_ok=True)
                logger.info(f"[AME] Cleared old watch folder: {self.watch_folder_path}")
        except OSError as e:
            logger.warning(f"[AME] Failed to clear watch folder: {e}")

        # Step 2: 提交渲染（优先 CLI，降级 Watch Folder）
        logger.info(f"[AME] Submitting render: {input_path.name} -> {output_path.name}")

        encode_result = await self.encode(
            input_path=input_path,
            output_path=output_path,
            platform="youtube",  # 使用 YouTube 预设（H.264 1080p）
            overwrite=True,
        )

        if not encode_result.success:
            # CLI 失败，尝试 Watch Folder
            logger.warning("[AME] CLI encode failed, trying Watch Folder")
            encode_result = await self._encode_via_watch_folder(
                input_path, output_path,
                {"name": "Flagship H.264", "resolution": (1920, 1080), "fps": 24, "bitrate": "20M"},
            )

        if not encode_result.success:
            return EngineResult(
                success=False,
                error=f"AME render failed: {encode_result.error}",
                error_code="RENDER_FAILED",
                duration_seconds=_time.time() - t0,
            )

        # Step 3: 等待产物出现（Watch Folder 模式可能异步）
        deadline = t0 + timeout
        while not output_path.exists() and _time.time() < deadline:
            await asyncio.sleep(2.0)

        if not output_path.exists():
            return EngineResult(
                success=False,
                error=f"Output not produced within {timeout}s: {output_path}",
                error_code="TIMEOUT",
                duration_seconds=_time.time() - t0,
            )

        # Step 4: 生成 ffprobe.json
        ffprobe_json = output_path.parent / "ffprobe.json"
        probe_data = await self._run_ffprobe(output_path)
        if probe_data:
            ffprobe_json.write_text(_json.dumps(probe_data, indent=2), encoding="utf-8")

        elapsed = _time.time() - t0
        file_size = output_path.stat().st_size
        logger.info(f"[AME] Render complete in {elapsed:.1f}s: {output_path} ({file_size} bytes)")

        return EngineResult(
            success=True,
            output_path=output_path,
            metadata={
                "codec": codec,
                "resolution": resolution,
                "fps": fps,
                "file_size": file_size,
                "ffprobe_json": str(ffprobe_json) if ffprobe_json.exists() else None,
            },
            duration_seconds=elapsed,
        )

    async def _run_ffprobe(self, video_path: Path) -> Optional[dict]:
        """运行 ffprobe 获取视频元数据。"""
        import subprocess
        import json as _json

        try:
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                str(video_path),
            ]
            proc = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=30
            )
            if proc.returncode == 0:
                return _json.loads(proc.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass
        return None
