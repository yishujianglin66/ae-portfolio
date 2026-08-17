"""
pipeline/batch_queue.py - 批量生产队列
=========================================
管理多个管线任务的排队、并发执行与状态追踪。

用法:
    from pipeline.batch_queue import BatchQueue

    queue = BatchQueue(max_concurrent=2)
    queue.add_task(input_topic="高燃混剪", preset="high_energy")
    queue.add_task(input_topic="电影感Vlog", preset="cinematic")
    queue.add_task(reference_video="ref.mp4", preset="vlog")
    results = queue.run_all()
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchTask:
    """单个批量任务"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    input_topic: str = ""
    reference_video: str = ""
    materials_dir: str = ""
    preset: str = ""
    output_dir: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict] = None
    error: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def duration_sec(self) -> float:
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 1)
        return 0.0

    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "input_topic": self.input_topic,
            "reference_video": self.reference_video,
            "preset": self.preset,
            "output_dir": self.output_dir,
            "status": self.status.value,
            "error": self.error,
            "duration_sec": self.duration_sec,
            "created_at": self.created_at,
        }


class BatchQueue:
    """批量生产队列"""

    def __init__(
        self,
        max_concurrent: int = 1,
        output_base_dir: str = "output/batch",
        auto_retry: bool = False,
        max_retries: int = 2,
    ):
        self.max_concurrent = max_concurrent
        self.output_base_dir = output_base_dir
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        self._tasks: List[BatchTask] = []
        self._results: Dict[str, Any] = {}

    def add_task(
        self,
        input_topic: str = "",
        reference_video: str = "",
        materials_dir: str = "",
        preset: str = "",
        output_dir: str = "",
    ) -> BatchTask:
        """添加任务到队列"""
        if not output_dir:
            safe_name = (input_topic or reference_video or "task")[:20].replace(" ", "_")
            output_dir = os.path.join(self.output_base_dir, safe_name)

        task = BatchTask(
            input_topic=input_topic,
            reference_video=reference_video,
            materials_dir=materials_dir,
            preset=preset,
            output_dir=output_dir,
        )
        self._tasks.append(task)
        logger.info(f"Batch: Added task {task.task_id} ({input_topic or reference_video})")
        return task

    def add_tasks_from_list(self, task_specs: List[Dict]) -> List[BatchTask]:
        """批量添加任务"""
        return [self.add_task(**spec) for spec in task_specs]

    def get_status(self) -> Dict:
        """获取队列状态"""
        status_counts = {}
        for s in TaskStatus:
            status_counts[s.value] = sum(1 for t in self._tasks if t.status == s)

        return {
            "total": len(self._tasks),
            "status": status_counts,
            "max_concurrent": self.max_concurrent,
            "tasks": [t.to_dict() for t in self._tasks],
        }

    def run_all(self) -> List[Dict]:
        """执行所有任务"""
        start = time.time()
        logger.info(f"Batch: Starting {len(self._tasks)} tasks (concurrent={self.max_concurrent})")

        if self.max_concurrent <= 1:
            # 串行执行
            for task in self._tasks:
                if task.status == TaskStatus.CANCELLED:
                    continue
                self._run_single(task)
        else:
            # 并行执行
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                futures = {}
                for task in self._tasks:
                    if task.status == TaskStatus.CANCELLED:
                        continue
                    future = executor.submit(self._run_single, task)
                    futures[future] = task

                for future in as_completed(futures):
                    task = futures[future]
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Batch: Task {task.task_id} thread error: {e}")

        total = time.time() - start
        results = [t.to_dict() for t in self._tasks]
        succeeded = sum(1 for t in self._tasks if t.status == TaskStatus.DONE)
        logger.info(f"Batch: Complete ({total:.1f}s) - {succeeded}/{len(self._tasks)} succeeded")
        return results

    def _run_single(self, task: BatchTask):
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        logger.info(f"Batch: Task {task.task_id} START ({task.input_topic or task.reference_video})")

        retries = self.max_retries if self.auto_retry else 1
        for attempt in range(1, retries + 1):
            try:
                result = self._execute_pipeline(task)
                task.result = result
                task.status = TaskStatus.DONE
                task.end_time = time.time()
                logger.info(f"Batch: Task {task.task_id} DONE ({task.duration_sec}s)")
                return
            except Exception as e:
                logger.error(f"Batch: Task {task.task_id} attempt {attempt} failed: {e}")
                if attempt >= retries:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.end_time = time.time()
                    logger.error(f"Batch: Task {task.task_id} FAILED after {retries} attempts")

    def _execute_pipeline(self, task: BatchTask) -> Dict:
        """执行管线"""
        from pipeline import UnifiedPipeline, PipelineConfig

        # 构建 config
        config = PipelineConfig(
            input_topic=task.input_topic,
            reference_video=task.reference_video,
            materials_dir=task.materials_dir,
            output_dir=task.output_dir,
        )

        # 应用预设
        if task.preset:
            from pipeline.presets import apply_preset
            config = apply_preset(config, task.preset)

        # 运行管线
        pipe = UnifiedPipeline(config)
        result = pipe.run_all()

        return {
            "run_id": pipe.run_id,
            "status": result.status.value if hasattr(result.status, 'value') else str(result.status),
            "stages": {
                name: {
                    "status": sr.status.value if hasattr(sr.status, 'value') else str(sr.status),
                    "duration": sr.duration_sec,
                }
                for name, sr in pipe._results.items()
            },
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        for task in self._tasks:
            if task.task_id == task_id and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                return True
        return False

    def retry_failed(self) -> int:
        """重试所有失败的任务"""
        retried = 0
        for task in self._tasks:
            if task.status == TaskStatus.FAILED:
                task.status = TaskStatus.PENDING
                task.error = ""
                task.result = None
                retried += 1
        return retried

    def save_manifest(self, path: str = None) -> str:
        """保存任务清单"""
        if not path:
            path = os.path.join(self.output_base_dir, "batch_manifest.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        manifest = {
            "created_at": datetime.now().isoformat(),
            "max_concurrent": self.max_concurrent,
            "tasks": [t.to_dict() for t in self._tasks],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return path
