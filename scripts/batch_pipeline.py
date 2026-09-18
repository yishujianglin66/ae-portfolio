#!/usr/bin/env python3
"""
P1.2 + P1.3: 批量处理管线 + 失败自动重试

功能：
1. 任务队列管理（添加/取消/查看）
2. 并行视频分析（可配置并发数）
3. 进度追踪与实时报告
4. 失败自动重试（指数退避）
5. AE Bridge 批量投递
6. 健康检查与自动恢复

用法：
    python scripts/batch_pipeline.py --input-dir data/real_amv_test --output-dir output/batch
    python scripts/batch_pipeline.py --videos video1.mp4 video2.mp4 --style-only
    python scripts/batch_pipeline.py --queue-status
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class PipelineTask:
    """单个管线任务"""
    task_id: str
    video_path: str
    status: TaskStatus = TaskStatus.PENDING
    result: dict | None = None
    error: str | None = None
    attempts: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "video_path": self.video_path,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "attempts": self.attempts,
            "duration": self.duration,
        }


class BatchPipeline:
    """批量处理管线

    支持：
    - 并发控制（默认3路并行分析）
    - 指数退避重试（1s → 2s → 4s）
    - 实时进度回调
    - AE Bridge 批量投递
    """

    def __init__(
        self,
        max_concurrency: int = 3,
        max_retries: int = 3,
        enable_ae_bridge: bool = False,
        output_dir: str = "output/batch",
    ):
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.enable_ae_bridge = enable_ae_bridge
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.tasks: dict[str, PipelineTask] = {}
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._task_counter = 0
        self._progress_callback = None

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self._progress_callback = callback

    def add_task(self, video_path: str) -> str:
        """添加任务到队列"""
        self._task_counter += 1
        task_id = f"task_{self._task_counter:04d}"
        task = PipelineTask(
            task_id=task_id,
            video_path=video_path,
            max_retries=self.max_retries,
        )
        self.tasks[task_id] = task
        logger.info(f"任务已添加: {task_id} → {Path(video_path).name}")
        return task_id

    def add_videos_from_dir(self, input_dir: str, extensions: tuple = (".mp4", ".mkv", ".webm")) -> int:
        """从目录批量添加视频"""
        input_path = Path(input_dir)
        count = 0
        for f in sorted(input_path.iterdir()):
            if f.suffix.lower() in extensions and f.stat().st_size > 50000:
                self.add_task(str(f))
                count += 1
        logger.info(f"从 {input_dir} 添加了 {count} 个视频")
        return count

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False

    def get_queue_status(self) -> dict:
        """获取队列状态"""
        status_counts = {}
        for task in self.tasks.values():
            s = task.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        total = len(self.tasks)
        completed = status_counts.get("success", 0) + status_counts.get("failed", 0)
        progress = completed / total if total > 0 else 0

        return {
            "total": total,
            "progress": progress,
            "status_counts": status_counts,
            "avg_duration": self._avg_duration(),
        }

    def _avg_duration(self) -> float:
        durations = [t.duration for t in self.tasks.values() if t.duration > 0]
        return sum(durations) / len(durations) if durations else 0.0

    async def _process_single_task(self, task: PipelineTask) -> None:
        """处理单个任务（含重试逻辑）"""
        async with self._semaphore:
            for attempt in range(1, task.max_retries + 1):
                task.attempts = attempt
                task.status = TaskStatus.RUNNING if attempt == 1 else TaskStatus.RETRYING
                task.started_at = time.time()

                try:
                    result = await self._execute_pipeline(task.video_path)
                    task.result = result
                    task.status = TaskStatus.SUCCESS
                    task.completed_at = time.time()
                    logger.info(
                        f"✓ {task.task_id}: {result.get('style', '?')} "
                        f"({result.get('confidence', 0):.0%}) "
                        f"[{task.duration:.1f}s]"
                    )
                    break

                except Exception as e:
                    task.error = str(e)
                    if attempt < task.max_retries:
                        # 指数退避: 1s, 2s, 4s
                        backoff = 2 ** (attempt - 1)
                        logger.warning(
                            f"⟳ {task.task_id}: 第{attempt}次失败 ({e}), "
                            f"{backoff}s后重试..."
                        )
                        await asyncio.sleep(backoff)
                    else:
                        task.status = TaskStatus.FAILED
                        task.completed_at = time.time()
                        logger.error(
                            f"✗ {task.task_id}: 最终失败 ({task.attempts}次尝试): {e}"
                        )

                # 进度回调
                if self._progress_callback:
                    self._progress_callback(self.get_queue_status())

    async def _execute_pipeline(self, video_path: str) -> dict[str, Any]:
        """执行完整管线: 分析 → 分类 → JSX生成 → (可选)AE投递"""
        from core.jsx_generator import save_jsx_to_file
        from core.style_pipeline import analyze_video_style
        from core.style_preset_adapter import style_to_atomic_params

        # Step 1: 风格分析
        style_result = await analyze_video_style(video_path, enable_vision=False)

        if style_result.get("error"):
            raise RuntimeError(f"分析失败: {style_result['error']}")

        style = style_result.get("style", "cinematic")
        confidence = style_result.get("confidence", 0.0)

        # Step 2: 参数映射
        atomic_params = style_to_atomic_params(style, confidence)

        # Step 3: JSX生成
        video_name = Path(video_path).stem
        jsx_path = self.output_dir / "jsx" / f"{video_name}_{style}.jsx"
        jsx_path.parent.mkdir(parents=True, exist_ok=True)

        save_jsx_to_file(
            style=style,
            confidence=confidence,
            atomic_params=atomic_params,
            output_path=str(jsx_path),
            video_path=video_path,
        )

        result = {
            "style": style,
            "confidence": confidence,
            "jsx_path": str(jsx_path),
            "features": style_result.get("features", []),
            "latency_ms": style_result.get("latency_ms", 0),
        }

        # Step 4: (可选) AE Bridge 投递
        if self.enable_ae_bridge:
            ae_result = await self._send_to_ae_bridge(jsx_path)
            result["ae_execution"] = ae_result

        return result

    async def _send_to_ae_bridge(self, jsx_path: Path) -> dict:
        """通过Bridge发送JSX到AE执行"""
        from scripts.ae_automation import is_ae_running, send_bridge_command

        if not is_ae_running():
            return {"success": False, "error": "AE未运行"}

        jsx_content = jsx_path.read_text(encoding="utf-8")
        result = send_bridge_command({
            "action": "execute_script",
            "script": jsx_content,
        }, timeout=30)

        return result

    async def run(self) -> dict:
        """执行所有待处理任务"""
        pending_tasks = [
            t for t in self.tasks.values()
            if t.status == TaskStatus.PENDING
        ]

        if not pending_tasks:
            logger.info("无待处理任务")
            return self.get_queue_status()

        logger.info(f"开始批量处理: {len(pending_tasks)} 个任务, "
                    f"并发={self.max_concurrency}, 重试={self.max_retries}")

        start_time = time.time()

        # 并行执行所有任务
        await asyncio.gather(
            *[self._process_single_task(task) for task in pending_tasks]
        )

        total_time = time.time() - start_time
        status = self.get_queue_status()

        # 生成报告
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_time": total_time,
            "config": {
                "max_concurrency": self.max_concurrency,
                "max_retries": self.max_retries,
                "enable_ae_bridge": self.enable_ae_bridge,
            },
            "summary": status,
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }

        report_path = self.output_dir / "batch_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"批量处理完成: {total_time:.1f}s, 报告: {report_path}")
        return report


def print_progress(status: dict):
    """打印进度条"""
    total = status["total"]
    progress = status["progress"]
    counts = status["status_counts"]
    bar_len = 30
    filled = int(bar_len * progress)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {progress:.0%} | "
          f"✓{counts.get('success', 0)} "
          f"✗{counts.get('failed', 0)} "
          f"⟳{counts.get('retrying', 0)} "
          f"…{counts.get('running', 0)} "
          f"| avg {status['avg_duration']:.1f}s", end="", flush=True)


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="批量风格分析管线")
    parser.add_argument("--input-dir", type=str, help="输入视频目录")
    parser.add_argument("--videos", nargs="+", help="视频文件列表")
    parser.add_argument("--output-dir", type=str, default="output/batch")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--ae-bridge", action="store_true", help="启用AE Bridge投递")
    parser.add_argument("--queue-status", action="store_true", help="查看队列状态")
    args = parser.parse_args()

    pipeline = BatchPipeline(
        max_concurrency=args.concurrency,
        max_retries=args.retries,
        enable_ae_bridge=args.ae_bridge,
        output_dir=args.output_dir,
    )
    pipeline.set_progress_callback(print_progress)

    # 添加任务
    if args.input_dir:
        pipeline.add_videos_from_dir(args.input_dir)
    elif args.videos:
        for v in args.videos:
            pipeline.add_task(v)
    else:
        # 默认: 使用 real_amv_test 目录
        default_dir = PROJECT_ROOT / "data" / "real_amv_test"
        if default_dir.exists():
            pipeline.add_videos_from_dir(str(default_dir))
        else:
            print("请指定 --input-dir 或 --videos")
            return

    # 执行
    print("\n" + "=" * 60)
    print("批量风格分析管线")
    print(f"  并发: {args.concurrency} | 重试: {args.retries} | AE: {args.ae_bridge}")
    print("=" * 60 + "\n")

    report = await pipeline.run()

    # 最终汇总
    print("\n\n" + "=" * 60)
    print("最终结果")
    print("=" * 60)
    summary = report["summary"]
    print(f"  总任务: {summary['total']}")
    print(f"  成功: {summary['status_counts'].get('success', 0)}")
    print(f"  失败: {summary['status_counts'].get('failed', 0)}")
    print(f"  总耗时: {report['total_time']:.1f}s")
    print(f"  平均延迟: {summary['avg_duration']:.1f}s/视频")


if __name__ == "__main__":
    asyncio.run(main())
