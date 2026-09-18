"""
integrations/davinci_render_queue.py — DaVinci Resolve 渲染队列自动化
====================================================================

管理 DaVinci Resolve 的渲染任务：
  - 添加/移除渲染任务
  - 批量渲染 (Batch Render)
  - 进度监控与回调
  - 渲染预设管理
  - 输出验证 (文件完整性检查)
  - FFmpeg 降级渲染 (当 Resolve 不可用时)

用法:
    from integrations.davinci_render_queue import RenderQueueManager

    rq = RenderQueueManager()
    job_id = rq.add_render_job(
        timeline_name="MyTimeline",
        output_path="output/final.mp4",
        preset="H.264 Master",
    )
    rq.start_render()
    status = rq.monitor_progress(job_id)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

class RenderStatus(Enum):
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RenderPreset:
    """渲染预设配置"""
    name: str
    format: str = "mp4"           # mp4/mov/mxf/dpx/exr
    codec: str = "h264"           # h264/h265/prores/dnxhr
    resolution: str = "1920x1080" # 输出分辨率
    fps: float = 30.0
    quality: int = 18             # CRF 值 (越低质量越高)
    audio_codec: str = "aac"
    audio_bitrate: str = "320k"
    custom_args: dict[str, Any] = field(default_factory=dict)

    def to_ffmpeg_args(self, input_path: str, output_path: str) -> list[str]:
        """转换为 FFmpeg 命令参数"""
        w, h = self.resolution.split("x")
        args = [
            "ffmpeg", "-y", "-i", input_path,
            "-c:v", self.codec if self.codec != "h264" else "libx264",
            "-crf", str(self.quality),
            "-preset", "medium",
            "-vf", f"scale={w}:{h}",
            "-r", str(self.fps),
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
            "-movflags", "+faststart",
            output_path,
        ]
        return args


@dataclass
class RenderJob:
    """渲染任务"""
    job_id: str
    timeline_name: str = ""
    input_path: str = ""
    output_path: str = ""
    preset: RenderPreset = field(default_factory=lambda: RenderPreset(name="default"))
    status: RenderStatus = RenderStatus.QUEUED
    progress: float = 0.0
    start_time: float | None = None
    end_time: float | None = None
    error: str = ""
    file_size: int = 0
    render_mode: str = "resolve"  # resolve / ffmpeg / simulate

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "timeline_name": self.timeline_name,
            "input_path": self.input_path,
            "output_path": self.output_path,
            "preset": self.preset.name,
            "status": self.status.value,
            "progress": self.progress,
            "duration_sec": (self.end_time or time.time()) - (self.start_time or time.time()) if self.start_time else 0,
            "error": self.error,
            "file_size": self.file_size,
            "render_mode": self.render_mode,
        }


# 预设渲染配置
BUILTIN_PRESETS = {
    "H.264 Master": RenderPreset(
        name="H.264 Master", format="mp4", codec="h264",
        resolution="1920x1080", fps=30, quality=15,
    ),
    "H.264 Web": RenderPreset(
        name="H.264 Web", format="mp4", codec="h264",
        resolution="1920x1080", fps=30, quality=23,
    ),
    "H.264 4K": RenderPreset(
        name="H.264 4K", format="mp4", codec="h264",
        resolution="3840x2160", fps=30, quality=18,
    ),
    "ProRes 422 HQ": RenderPreset(
        name="ProRes 422 HQ", format="mov", codec="prores_ks",
        resolution="1920x1080", fps=30, quality=1,
    ),
    "H.265 HEVC": RenderPreset(
        name="H.265 HEVC", format="mp4", codec="h265",
        resolution="1920x1080", fps=30, quality=20,
    ),
    "DNxHR HQ": RenderPreset(
        name="DNxHR HQ", format="mxf", codec="dnxhd",
        resolution="1920x1080", fps=30, quality=1,
    ),
    "Vertical 9:16": RenderPreset(
        name="Vertical 9:16", format="mp4", codec="h264",
        resolution="1080x1920", fps=30, quality=18,
    ),
}


# ============================================================================
#  渲染队列管理器
# ============================================================================

class RenderQueueManager:
    """DaVinci Resolve 渲染队列管理器"""

    def __init__(self):
        self._jobs: dict[str, RenderJob] = {}
        self._resolve_api = None
        self._resolve_available = False
        self._ffmpeg_available = False
        self._callbacks: dict[str, list[Callable]] = {
            "on_start": [],
            "on_progress": [],
            "on_complete": [],
            "on_error": [],
        }
        self._init_connections()

    def _init_connections(self):
        """初始化连接"""
        # 检查 Resolve
        try:
            import DaVinciResolveScript as dvr  # type: ignore
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                self._resolve_api = resolve
                self._resolve_available = True
                logger.info("[RenderQueue] Connected to DaVinci Resolve")
        except Exception:
            logger.info("[RenderQueue] DaVinciResolveScript not available")

        # 检查 FFmpeg
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            self._ffmpeg_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._ffmpeg_available = False

        logger.info(f"[RenderQueue] Resolve: {self._resolve_available}, FFmpeg: {self._ffmpeg_available}")

    # ----------------------------------------------------------------
    #  任务管理
    # ----------------------------------------------------------------

    def add_render_job(
        self,
        timeline_name: str = "",
        output_path: str = "",
        input_path: str = "",
        preset_name: str = "H.264 Master",
        custom_preset: RenderPreset | None = None,
    ) -> str:
        """添加渲染任务到队列。

        Args:
            timeline_name: Resolve 时间线名称
            output_path: 输出文件路径
            input_path: 输入文件路径 (FFmpeg模式用)
            preset_name: 预设名称

        Returns:
            job_id: 任务ID
        """
        job_id = f"rj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        preset = custom_preset or BUILTIN_PRESETS.get(preset_name, BUILTIN_PRESETS["H.264 Master"])

        # 确定渲染模式
        render_mode = "simulate"
        if self._resolve_available and timeline_name:
            render_mode = "resolve"
        elif self._ffmpeg_available and input_path:
            render_mode = "ffmpeg"

        job = RenderJob(
            job_id=job_id,
            timeline_name=timeline_name,
            input_path=input_path,
            output_path=output_path or f"output/render_{job_id}.{preset.format}",
            preset=preset,
            render_mode=render_mode,
        )
        self._jobs[job_id] = job
        logger.info(f"[RenderQueue] Added job {job_id}: {preset_name} ({render_mode})")
        return job_id

    def remove_job(self, job_id: str) -> bool:
        """移除渲染任务"""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            if job.status == RenderStatus.RENDERING:
                logger.warning(f"[RenderQueue] Cannot remove rendering job {job_id}")
                return False
            del self._jobs[job_id]
            return True
        return False

    def get_job(self, job_id: str) -> RenderJob | None:
        """获取任务状态"""
        return self._jobs.get(job_id)

    def list_jobs(self, status: RenderStatus | None = None) -> list[RenderJob]:
        """列出所有任务"""
        jobs = list(self._jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    def clear_completed(self) -> int:
        """清除已完成的任务"""
        to_remove = [jid for jid, j in self._jobs.items()
                     if j.status in (RenderStatus.COMPLETED, RenderStatus.FAILED)]
        for jid in to_remove:
            del self._jobs[jid]
        return len(to_remove)

    # ----------------------------------------------------------------
    #  渲染执行
    # ----------------------------------------------------------------

    def start_render(self, job_id: str | None = None) -> bool:
        """开始渲染。

        Args:
            job_id: 指定任务ID，为 None 时渲染队列中所有待处理任务

        Returns:
            是否成功启动
        """
        if job_id:
            jobs = [self._jobs.get(job_id)]
            jobs = [j for j in jobs if j]
        else:
            jobs = [j for j in self._jobs.values() if j.status == RenderStatus.QUEUED]

        if not jobs:
            logger.warning("[RenderQueue] No jobs to render")
            return False

        for job in jobs:
            self._execute_job(job)

        return True

    def _execute_job(self, job: RenderJob):
        """执行单个渲染任务"""
        job.status = RenderStatus.RENDERING
        job.start_time = time.time()

        # 触发回调
        self._fire_callback("on_start", job)

        try:
            if job.render_mode == "resolve":
                self._render_resolve(job)
            elif job.render_mode == "ffmpeg":
                self._render_ffmpeg(job)
            else:
                self._render_simulate(job)

            # 验证输出
            if job.status == RenderStatus.RENDERING:
                self._verify_output(job)

        except Exception as e:
            job.status = RenderStatus.FAILED
            job.error = str(e)
            self._fire_callback("on_error", job)
            logger.error(f"[RenderQueue] Job {job.job_id} failed: {e}")

        if job.status == RenderStatus.RENDERING:
            job.status = RenderStatus.COMPLETED
            job.end_time = time.time()
            job.progress = 100.0
            self._fire_callback("on_complete", job)

    def _render_resolve(self, job: RenderJob):
        """通过 Resolve API 渲染"""
        if not self._resolve_api:
            raise RuntimeError("Resolve API not available")

        resolve = self._resolve_api
        project_manager = resolve.GetProjectManager()
        project = project_manager.GetCurrentProject()

        if not project:
            raise RuntimeError("No active project in Resolve")

        # 设置渲染预设
        project.SetRenderSettings({
            "SelectAllClips": True,
            "TargetDir": str(Path(job.output_path).parent),
            "CustomName": Path(job.output_path).stem,
            "MarkIn": 0,
            "MarkOut": int(project.GetTimeline().GetEndFrame() or 900),
        })

        # 添加到渲染队列并启动
        render_job_id = project.AddRenderJob()
        if render_job_id:
            project.StartRendering(render_job_id)
            # 等待完成
            while project.IsRenderingInProgress():
                progress = project.GetRenderJobStatus(render_job_id)
                job.progress = progress.get("CompletionPercentage", 0)
                self._fire_callback("on_progress", job)
                time.sleep(2)

    def _render_ffmpeg(self, job: RenderJob):
        """通过 FFmpeg 渲染"""
        if not job.input_path or not Path(job.input_path).exists():
            raise RuntimeError(f"Input file not found: {job.input_path}")

        # 确保输出目录存在
        Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)

        args = job.preset.to_ffmpeg_args(job.input_path, job.output_path)
        logger.info(f"[RenderQueue] FFmpeg: {' '.join(args)}")

        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # 监控进度 (简化版)
        while process.poll() is None:
            time.sleep(1)
            # 检查输出文件大小作为进度指标
            if Path(job.output_path).exists():
                job.file_size = Path(job.output_path).stat().st_size
                job.progress = min(95, job.progress + 5)
                self._fire_callback("on_progress", job)

        if process.returncode != 0:
            stderr = process.stderr.read() if process.stderr else ""
            raise RuntimeError(f"FFmpeg failed: {stderr[:500]}")

        job.file_size = Path(job.output_path).stat().st_size if Path(job.output_path).exists() else 0

    def _render_simulate(self, job: RenderJob):
        """模拟渲染 (测试用)"""
        logger.info(f"[RenderQueue] Simulating render: {job.job_id}")
        for i in range(10):
            job.progress = (i + 1) * 10
            self._fire_callback("on_progress", job)
            time.sleep(0.1)

    def _verify_output(self, job: RenderJob):
        """验证输出文件"""
        if not Path(job.output_path).exists():
            job.status = RenderStatus.FAILED
            job.error = "Output file not created"
            return

        file_size = Path(job.output_path).stat().st_size
        if file_size < 1000:  # 小于 1KB 视为异常
            job.status = RenderStatus.FAILED
            job.error = f"Output file too small: {file_size} bytes"
            return

        job.file_size = file_size

        # FFprobe 验证
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "format=duration,size:stream=codec_name,width,height",
                 "-of", "json", job.output_path],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                info = json.loads(result.stdout)
                job.file_size = int(info.get("format", {}).get("size", file_size))
        except Exception:
            pass  # ffprobe 失败不影响

    # ----------------------------------------------------------------
    #  进度监控
    # ----------------------------------------------------------------

    def monitor_progress(self, job_id: str) -> dict:
        """监控单个任务进度"""
        job = self._jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        return job.to_dict()

    def monitor_all(self) -> list[dict]:
        """监控所有任务进度"""
        return [j.to_dict() for j in self._jobs.values()]

    def wait_for_completion(self, job_id: str, timeout: float = 600) -> dict:
        """等待任务完成"""
        start = time.time()
        while time.time() - start < timeout:
            job = self._jobs.get(job_id)
            if not job:
                return {"error": "Job not found"}
            if job.status in (RenderStatus.COMPLETED, RenderStatus.FAILED):
                return job.to_dict()
            time.sleep(1)
        return {"error": "Timeout", "job": job.to_dict()}

    # ----------------------------------------------------------------
    #  回调注册
    # ----------------------------------------------------------------

    def on_start(self, callback: Callable):
        self._callbacks["on_start"].append(callback)

    def on_progress(self, callback: Callable):
        self._callbacks["on_progress"].append(callback)

    def on_complete(self, callback: Callable):
        self._callbacks["on_complete"].append(callback)

    def on_error(self, callback: Callable):
        self._callbacks["on_error"].append(callback)

    def _fire_callback(self, event: str, job: RenderJob):
        for cb in self._callbacks.get(event, []):
            try:
                cb(job)
            except Exception:
                pass

    # ----------------------------------------------------------------
    #  预设管理
    # ----------------------------------------------------------------

    def list_presets(self) -> list[str]:
        """列出所有可用预设"""
        return list(BUILTIN_PRESETS.keys())

    def get_preset(self, name: str) -> RenderPreset | None:
        """获取预设配置"""
        return BUILTIN_PRESETS.get(name)

    def add_preset(self, preset: RenderPreset):
        """添加自定义预设"""
        BUILTIN_PRESETS[preset.name] = preset


# ============================================================================
#  便捷函数
# ============================================================================

def quick_render(
    input_path: str,
    output_path: str,
    preset: str = "H.264 Master",
) -> dict:
    """快捷渲染函数"""
    rq = RenderQueueManager()
    job_id = rq.add_render_job(
        input_path=input_path,
        output_path=output_path,
        preset_name=preset,
    )
    rq.start_render(job_id)
    return rq.wait_for_completion(job_id)
