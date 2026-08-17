"""
Distributed Renderer — 分布式渲染调度引擎
=========================================
提供多节点分布式渲染与任务队列管理能力。

核心能力:
- 多节点渲染任务分发
- 任务优先级队列
- 渲染进度追踪
- 自动故障转移
- 渲染农场集成 (OpenCue/Afanasy 适配)
- 本地多进程渲染 (aerender multiprocess)

依赖:
    pip install redis celery (分布式)
    # 本地模式不需要额外依赖

用法:
    scheduler = DistributedRenderer(mode="local")
    scheduler.submit_task("project.aep", "output.mp4")
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import subprocess
import uuid
import threading
import queue
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from datetime import datetime
import multiprocessing

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  数据结构
# ================================================================
class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class RenderMode(Enum):
    LOCAL = "local"           # 本地多进程
    DISTRIBUTED = "distributed"  # 分布式网络渲染
    HYBRID = "hybrid"         # 混合模式


@dataclass(order=True)
class RenderTask:
    """渲染任务"""
    priority: int
    task_id: str = field(compare=False)
    project_path: str = field(compare=False)
    output_path: str = field(compare=False)
    composition: str = ""             # AE 合成名称
    start_frame: int = 0
    end_frame: int = 0
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0            # 0.0 ~ 1.0
    error_message: str = ""
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    worker_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class RenderWorker:
    """渲染工作节点"""
    worker_id: str
    hostname: str
    status: str = "idle"        # idle, busy, offline
    gpu_available: bool = False
    cpu_cores: int = 4
    current_task: Optional[str] = None
    tasks_completed: int = 0
    total_render_time: float = 0.0
    last_heartbeat: str = ""


@dataclass
class RenderBatch:
    """渲染批次"""
    batch_id: str
    tasks: List[RenderTask]
    total_progress: float = 0.0
    completed_tasks: int = 0
    failed_tasks: int = 0


# ================================================================
#  分布式渲染调度器
# ================================================================
class DistributedRenderer:
    """分布式渲染调度引擎"""

    def __init__(
        self,
        mode: RenderMode = RenderMode.LOCAL,
        max_workers: int = None,
        aerender_path: str = None,
        redis_url: str = None,
        output_dir: str = None,
    ):
        self.mode = mode
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)
        self.aerender_path = aerender_path or self._find_aerender()
        self.redis_url = redis_url
        self.output_dir = output_dir or str(Path.home() / "ae-renders")

        # 任务队列
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._active_tasks: Dict[str, RenderTask] = {}
        self._completed_tasks: Dict[str, RenderTask] = {}
        self._workers: Dict[str, RenderWorker] = {}

        # 回调
        self._on_task_complete: Optional[Callable] = None
        self._on_task_error: Optional[Callable] = None
        self._on_task_progress: Optional[Callable[[str, float], None]] = None

        # 执行器
        self._executor: Optional[ThreadPoolExecutor] = None
        self._running = False
        self._lock = threading.Lock()

    @staticmethod
    def _find_aerender() -> Optional[str]:
        """查找 aerender 可执行文件"""
        candidates = [
            r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\aerender.exe",
            r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\aerender.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return "aerender"  # 使用 PATH 中的

    # ================================================================
    #  任务提交
    # ================================================================
    def submit_task(
        self,
        project_path: str,
        output_path: str = None,
        composition: str = "",
        start_frame: int = 0,
        end_frame: int = 0,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: Dict = None,
    ) -> str:
        """提交渲染任务"""
        task_id = str(uuid.uuid4())[:8]

        if output_path is None:
            output_name = Path(project_path).stem + "_rendered.mp4"
            output_path = str(Path(self.output_dir) / output_name)

        os.makedirs(Path(output_path).parent, exist_ok=True)

        task = RenderTask(
            priority=priority.value,
            task_id=task_id,
            project_path=project_path,
            output_path=output_path,
            composition=composition,
            start_frame=start_frame,
            end_frame=end_frame,
            status=TaskStatus.QUEUED,
            metadata=metadata or {},
        )

        self._task_queue.put(task)

        with self._lock:
            self._active_tasks[task_id] = task

        self._ensure_running()
        return task_id

    def submit_batch(
        self,
        tasks: List[Dict[str, Any]],
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> RenderBatch:
        """批量提交任务"""
        batch_id = f"batch_{uuid.uuid4().hex[:6]}"
        batch = RenderBatch(batch_id=batch_id, tasks=[])

        for task_config in tasks:
            task_id = self.submit_task(
                project_path=task_config.get("project_path", ""),
                output_path=task_config.get("output_path"),
                composition=task_config.get("composition", ""),
                start_frame=task_config.get("start_frame", 0),
                end_frame=task_config.get("end_frame", 0),
                priority=task_config.get("priority", priority),
                metadata={"batch_id": batch_id, **task_config.get("metadata", {})},
            )
            if task_id:
                batch.tasks.append(self._active_tasks.get(task_id))

        return batch

    def split_video_task(
        self,
        project_path: str,
        output_path: str,
        total_frames: int,
        segments: int = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> List[str]:
        """
        视频分段渲染 — 将长视频拆分为多段并行渲染。

        Args:
            project_path: AE 项目路径
            output_path: 最终输出路径
            total_frames: 总帧数
            segments: 分段数（默认 = max_workers）
            priority: 优先级

        Returns:
            任务 ID 列表
        """
        if segments is None:
            segments = self.max_workers

        frames_per_segment = total_frames // segments
        task_ids = []

        for i in range(segments):
            start = i * frames_per_segment
            end = total_frames if i == segments - 1 else (i + 1) * frames_per_segment - 1

            seg_output = str(Path(output_path).with_stem(f"{Path(output_path).stem}_seg_{i:03d}"))

            task_id = self.submit_task(
                project_path=project_path,
                output_path=seg_output,
                start_frame=start,
                end_frame=end,
                priority=priority,
                metadata={"segment": i, "total_segments": segments},
            )
            task_ids.append(task_id)

        return task_ids

    # ================================================================
    #  渲染执行
    # ================================================================
    def _ensure_running(self):
        """确保执行器在运行"""
        if not self._running:
            self._running = True
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
            for _ in range(self.max_workers):
                self._executor.submit(self._worker_loop)

    def _worker_loop(self):
        """工作循环"""
        worker_id = f"worker_{threading.get_ident()}"

        while self._running:
            try:
                task = self._task_queue.get(timeout=5)
            except queue.Empty:
                continue

            if task.status == TaskStatus.CANCELLED:
                self._task_queue.task_done()
                continue

            self._execute_task(task, worker_id)
            self._task_queue.task_done()

    def _execute_task(self, task: RenderTask, worker_id: str):
        """执行单个渲染任务"""
        task.status = TaskStatus.RUNNING
        task.worker_id = worker_id
        task.started_at = datetime.now().isoformat()

        try:
            if task.project_path.endswith(".aep"):
                self._render_ae(task)
            elif task.project_path.endswith(".mp4"):
                self._render_ffmpeg(task)
            else:
                self._render_ffmpeg(task)

            task.status = TaskStatus.COMPLETED
            task.progress = 1.0
            task.completed_at = datetime.now().isoformat()

            with self._lock:
                self._completed_tasks[task.task_id] = task
                if task.task_id in self._active_tasks:
                    del self._active_tasks[task.task_id]

            if self._on_task_complete:
                self._on_task_complete(task)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)

            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.QUEUED
                self._task_queue.put(task)

            if self._on_task_error:
                self._on_task_error(task, e)

    def _render_ae(self, task: RenderTask):
        """使用 aerender 渲染 AE 项目"""
        if not self.aerender_path:
            raise RuntimeError("aerender not found")

        cmd = [self.aerender_path, "-project", task.project_path]
        if task.composition:
            cmd.extend(["-comp", task.composition])
        cmd.extend(["-output", task.output_path])

        if task.end_frame > task.start_frame:
            cmd.extend([
                "-OMtemplate", "H.264",
                "-output", task.output_path,
            ])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"aerender failed: {stderr}")

        task.progress = 1.0

    def _render_ffmpeg(self, task: RenderTask):
        """使用 ffmpeg 渲染视频"""
        import subprocess

        # 验证输入文件存在
        if not os.path.exists(task.project_path):
            raise FileNotFoundError(f"Input file not found: {task.project_path}")

        cmd = [
            "ffmpeg", "-y",
            "-i", task.project_path,
        ]

        if task.start_frame > 0 or task.end_frame > 0:
            cmd.extend([
                "-ss", str(task.start_frame / 30.0),
                "-to", str(task.end_frame / 30.0),
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            task.output_path,
        ])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 实时读取进度
        for line in process.stderr:
            if "time=" in line:
                # 解析 ffmpeg 进度
                try:
                    time_str = line.split("time=")[1].split()[0]
                    h, m, s = time_str.split(":")
                    current_sec = float(h) * 3600 + float(m) * 60 + float(s)
                    task.progress = min(0.99, current_sec / max(1, (task.end_frame - task.start_frame) / 30.0))
                except (ValueError, IndexError):
                    pass

        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg render failed with code {process.returncode}")

        task.progress = 1.0

    # ================================================================
    #  状态查询
    # ================================================================
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self._active_tasks.get(task_id) or self._completed_tasks.get(task_id)
        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "progress": task.progress,
            "error": task.error_message,
            "output": task.output_path if task.status == TaskStatus.COMPLETED else None,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "worker": task.worker_id,
            "retries": task.retry_count,
        }

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "mode": self.mode.value,
            "queue_size": self._task_queue.qsize(),
            "active_tasks": len(self._active_tasks),
            "completed_tasks": len(self._completed_tasks),
            "workers": self.max_workers,
            "running": self._running,
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self._active_tasks.get(task_id)
        if task and task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def get_batch_progress(self, batch_id: str) -> Dict[str, Any]:
        """获取批次进度"""
        batch_tasks = [
            t for t in list(self._active_tasks.values()) + list(self._completed_tasks.values())
            if t.metadata.get("batch_id") == batch_id
        ]

        if not batch_tasks:
            return {"found": False}

        completed = sum(1 for t in batch_tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in batch_tasks if t.status == TaskStatus.FAILED)
        total = len(batch_tasks)
        progress = sum(t.progress for t in batch_tasks) / max(total, 1)

        return {
            "found": True,
            "batch_id": batch_id,
            "progress": round(progress, 3),
            "completed": completed,
            "failed": failed,
            "total": total,
            "tasks": [self.get_task_status(t.task_id) for t in batch_tasks],
        }

    # ================================================================
    #  回调注册
    # ================================================================
    def on_complete(self, callback: Callable[[RenderTask], None]):
        self._on_task_complete = callback

    def on_error(self, callback: Callable[[RenderTask, Exception], None]):
        self._on_task_error = callback

    def on_progress(self, callback: Callable[[str, float], None]):
        self._on_task_progress = callback

    # ================================================================
    #  生命周期
    # ================================================================
    def shutdown(self, wait: bool = True):
        """关闭渲染器"""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=wait)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()


# ================================================================
#  渲染农场适配器
# ================================================================
class RenderFarmAdapter:
    """渲染农场适配器（OpenCue / Afanasy 等）。

    仅在配置了真实农场端点时才提交任务；否则返回 status="unsupported"
    且 success=False 并附明确提示，绝不返回伪造的 "submitted" 状态。

    P0-2 决策：submit_to_opencue / submit_to_afanasy 在已配置 endpoint 但未接入
    真实提交逻辑时，显式 raise NotImplementedError（诚实失败，而非伪造成功）。
    外部农场集成属 Phase 1+ 工作，不在 P0 可运行性治理范围内脚手架实现。
    """

    def __init__(self, farm_type: str = "opencue", endpoint: Optional[str] = None):
        self.farm_type = farm_type
        self.endpoint = endpoint

    def _unsupported(
        self,
        project_path: str,
        output_path: str,
        frames: str = "",
    ) -> Dict:
        return {
            "farm": self.farm_type,
            "status": "unsupported",
            "success": False,
            "error": (
                f"{self.farm_type} 渲染农场端点未配置，无法提交任务。"
                "请通过 endpoint 参数或环境变量提供真实农场地址后重试，"
                "否则请降级到本地多进程渲染（RenderMode.LOCAL）。"
            ),
            "project": project_path,
            "output": output_path,
            "frames": frames,
        }

    def submit_to_opencue(
        self,
        project_path: str,
        output_path: str,
        frames: str = "1-300",
    ) -> Dict:
        """提交到 OpenCue 渲染农场。

        未配置真实 OpenCue 端点时返回 unsupported + success=False；
        若已配置端点但真实提交逻辑未接入，则抛出 NotImplementedError。
        """
        if not self.endpoint:
            return self._unsupported(project_path, output_path, frames)
        raise NotImplementedError(
            "OpenCue 真实提交逻辑尚未接入。已配置 endpoint，但需实现 courier 提交才能提交。"
        )

    def submit_to_afanasy(
        self,
        project_path: str,
        output_path: str,
        frames: str = "1-300",
    ) -> Dict:
        """提交到 Afanasy 渲染管理器。

        未配置真实 Afanasy 端点时返回 unsupported + success=False；
        若已配置端点但真实提交逻辑未接入，则抛出 NotImplementedError。
        """
        if not self.endpoint:
            return self._unsupported(project_path, output_path, frames)
        raise NotImplementedError(
            "Afanasy 真实提交逻辑尚未接入。已配置 endpoint，但需实现 afrender 提交才能提交。"
        )


__all__ = [
    "DistributedRenderer",
    "RenderTask",
    "RenderWorker",
    "RenderBatch",
    "RenderFarmAdapter",
    "TaskStatus",
    "TaskPriority",
    "RenderMode",
]
