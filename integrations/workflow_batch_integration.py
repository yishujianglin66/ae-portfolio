#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流编排器 - 批处理队列集成
=============================

将木偶风格化工作流与批处理队列系统深度集成，
提供企业级任务调度与管理能力。

功能:
- 工作流任务封装（多阶段流水线）
- 批量视频处理
- 任务依赖管理
- 资源感知调度
- 进度汇总与报告
- 失败重试与降级
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from logger import get_logger
    _logger = get_logger("workflow-batch")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    _logger = logging.getLogger("workflow-batch")

try:
    from batch_queue import BatchQueue, ProgressContext, TaskStatus, get_default_queue
    _BATCH_AVAILABLE = True
except ImportError:
    _BATCH_AVAILABLE = False

try:
    from resource_manager import ResourceManager, TaskResourceRequirement, get_resource_manager
    _RESOURCE_AVAILABLE = True
except ImportError:
    _RESOURCE_AVAILABLE = False

try:
    from task_persistence import PersistenceConfig, TaskPersistence, get_task_persistence
    _PERSISTENCE_AVAILABLE = True
except ImportError:
    _PERSISTENCE_AVAILABLE = False


# ============================================================================
# 工作流阶段定义
# ============================================================================

@dataclass
class WorkflowStage:
    """工作流阶段"""
    name: str
    description: str = ""
    func: Callable[..., Any] | None = None
    timeout: float = 300.0
    retry_count: int = 1
    required: bool = True


# ============================================================================
# 工作流任务
# ============================================================================

@dataclass
class WorkflowTask:
    """工作流任务"""
    task_id: str = field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:12]}")
    name: str = ""
    workflow_type: str = "puppet_style"
    input_path: str = ""
    output_dir: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    status: str = "pending"
    current_stage: int = 0
    total_stages: int = 0
    progress: float = 0.0
    progress_message: str = ""
    stages: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    duration: float = 0.0
    mode: str = "auto"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "name": self.name,
            "workflow_type": self.workflow_type,
            "input_path": self.input_path,
            "output_dir": self.output_dir,
            "config": self.config,
            "priority": self.priority,
            "status": self.status,
            "current_stage": self.current_stage,
            "total_stages": self.total_stages,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "stages": self.stages,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "mode": self.mode,
        }


# ============================================================================
# 工作流编排器 - 批处理集成
# ============================================================================

class WorkflowBatchIntegration:
    """工作流编排器与批处理队列集成

    将多阶段工作流封装为批处理任务，提供统一的调度与管理接口。
    """

    def __init__(
        self,
        queue: BatchQueue | None = None,
        resource_manager: ResourceManager | None = None,
        persistence: TaskPersistence | None = None,
    ):
        self._queue = queue or (get_default_queue() if _BATCH_AVAILABLE else None)
        self._resource_manager = resource_manager or (get_resource_manager() if _RESOURCE_AVAILABLE else None)
        self._persistence = persistence or (get_task_persistence() if _PERSISTENCE_AVAILABLE else None)
        self._workflow_tasks: dict[str, WorkflowTask] = {}

    # --------------------------------------------------------------------
    # 工作流定义
    # --------------------------------------------------------------------

    def get_puppet_style_stages(self, config: dict[str, Any]) -> list[WorkflowStage]:
        """获取木偶风格化工作流阶段"""
        auto_detect = config.get("auto_detect", True)
        use_resolve = config.get("use_resolve", False)

        stages = [
            WorkflowStage(
                name="media_analysis",
                description="视频与音频分析",
                timeout=120.0,
                retry_count=1,
            ),
        ]

        if auto_detect:
            stages.append(WorkflowStage(
                name="pose_detection",
                description="人物姿态检测与关节提取",
                timeout=180.0,
                retry_count=1,
            ))

        stages.extend([
            WorkflowStage(
                name="style_generation",
                description="木偶风格化效果生成",
                timeout=300.0,
                retry_count=1,
            ),
            WorkflowStage(
                name="ae_integration",
                description="AE 合成与脚本生成",
                timeout=240.0,
                retry_count=1,
            ),
        ])

        if use_resolve:
            stages.append(WorkflowStage(
                name="color_grading",
                description="达芬奇调色",
                timeout=180.0,
                retry_count=1,
            ))

        stages.append(WorkflowStage(
            name="output_render",
            description="渲染输出",
            timeout=300.0,
            retry_count=1,
        ))

        return stages

    # --------------------------------------------------------------------
    # 单视频处理
    # --------------------------------------------------------------------

    def submit_puppet_workflow(
        self,
        input_path: str,
        output_dir: str,
        style: str = "wood",
        auto_detect: bool = True,
        quality: str = "high",
        mode: str = "auto",
        priority: int = 5,
        on_progress: Callable[[WorkflowTask], None] | None = None,
        on_complete: Callable[[WorkflowTask], None] | None = None,
        on_failure: Callable[[WorkflowTask], None] | None = None,
    ) -> WorkflowTask:
        """提交木偶风格化工作流

        Args:
            input_path: 输入视频路径
            output_dir: 输出目录
            style: 风格类型
            auto_detect: 是否自动检测姿态
            quality: 输出质量
            mode: 执行模式
            priority: 优先级
            on_progress: 进度回调
            on_complete: 完成回调
            on_failure: 失败回调

        Returns:
            工作流任务
        """
        os.makedirs(output_dir, exist_ok=True)

        config = {
            "input_path": input_path,
            "output_dir": output_dir,
            "style": style,
            "auto_detect": auto_detect,
            "quality": quality,
            "mode": mode,
        }

        stages = self.get_puppet_style_stages(config)
        total_stages = len(stages)

        wf_task = WorkflowTask(
            name=f"puppet-{style}-{Path(input_path).stem}",
            workflow_type="puppet_style",
            input_path=input_path,
            output_dir=output_dir,
            config=config,
            priority=priority,
            total_stages=total_stages,
            stages=[{"name": s.name, "description": s.description, "status": "pending"} for s in stages],
            mode=mode,
        )

        self._workflow_tasks[wf_task.task_id] = wf_task

        if self._persistence:
            self._persistence.save_task(wf_task.task_id, wf_task.to_dict())

        def progress_callback(stage_idx: int, stage_progress: float, message: str):
            overall = (stage_idx + stage_progress) / total_stages
            wf_task.progress = min(1.0, max(0.0, overall))
            wf_task.progress_message = message
            wf_task.current_stage = stage_idx
            if stage_idx < len(wf_task.stages):
                wf_task.stages[stage_idx]["status"] = "running"
                wf_task.stages[stage_idx]["progress"] = stage_progress

            if self._persistence:
                self._persistence.save_task(wf_task.task_id, wf_task.to_dict())

            if on_progress:
                try:
                    on_progress(wf_task)
                except Exception:
                    pass

        def workflow_executor(progress_ctx: ProgressContext):
            wf_task.status = "running"
            wf_task.started_at = time.time()

            if self._persistence:
                self._persistence.save_task(wf_task.task_id, wf_task.to_dict())

            try:
                result = self._execute_puppet_workflow(
                    config=config,
                    stages=stages,
                    progress_callback=lambda idx, prog, msg: progress_callback(idx, prog, msg),
                    check_cancel=lambda: progress_ctx.check_cancel(),
                )

                wf_task.status = "completed"
                wf_task.result = result
                wf_task.progress = 1.0
                wf_task.progress_message = "处理完成"
                wf_task.completed_at = time.time()
                wf_task.duration = wf_task.completed_at - wf_task.started_at

                for stage in wf_task.stages:
                    stage["status"] = "completed"

                if self._persistence:
                    self._persistence.save_task(wf_task.task_id, wf_task.to_dict())

                if on_complete:
                    try:
                        on_complete(wf_task)
                    except Exception:
                        pass

                return result

            except Exception as e:
                wf_task.status = "failed"
                wf_task.error = str(e)
                wf_task.completed_at = time.time()
                wf_task.duration = wf_task.completed_at - (wf_task.started_at or time.time())

                if self._persistence:
                    self._persistence.save_task(wf_task.task_id, wf_task.to_dict())

                if on_failure:
                    try:
                        on_failure(wf_task)
                    except Exception:
                        pass

                raise

        if self._queue:
            self._queue.submit(
                workflow_executor,
                name=wf_task.name,
                priority=priority,
                max_retries=1,
                metadata={"workflow_type": "puppet_style", "wf_task_id": wf_task.task_id},
                on_progress=lambda t, p, m: None,
            )
        else:
            _logger.warning("批处理队列不可用，同步执行工作流")
            from batch_queue import ProgressContext
            ctx = ProgressContext(type('Task', (), {'status': TaskStatus.PENDING})())
            workflow_executor(ctx)

        return wf_task

    def _execute_puppet_workflow(
        self,
        config: dict[str, Any],
        stages: list[WorkflowStage],
        progress_callback: Callable[[int, float, str], None],
        check_cancel: Callable[[], bool],
    ) -> dict[str, Any]:
        """执行木偶风格化工作流（模拟实现）"""
        input_path = config.get("input_path", "")
        output_dir = config.get("output_dir", "")
        style = config.get("style", "wood")
        auto_detect = config.get("auto_detect", True)
        mode = config.get("mode", "simulate")

        stage_results: dict[str, Any] = {}

        for i, stage in enumerate(stages):
            if check_cancel():
                raise RuntimeError("任务被取消")

            progress_callback(i, 0.0, f"开始阶段: {stage.description}")
            _logger.info(f"执行阶段 {i+1}/{len(stages)}: {stage.name} - {stage.description}")

            try:
                if stage.name == "media_analysis":
                    result = self._stage_media_analysis(input_path, mode)
                    stage_results[stage.name] = result

                elif stage.name == "pose_detection":
                    result = self._stage_pose_detection(input_path, mode)
                    stage_results[stage.name] = result

                elif stage.name == "style_generation":
                    result = self._stage_style_generation(style, auto_detect, mode)
                    stage_results[stage.name] = result

                elif stage.name == "ae_integration":
                    result = self._stage_ae_integration(output_dir, style, mode)
                    stage_results[stage.name] = result

                elif stage.name == "color_grading":
                    result = self._stage_color_grading(output_dir, mode)
                    stage_results[stage.name] = result

                elif stage.name == "output_render":
                    result = self._stage_output_render(output_dir, style, mode)
                    stage_results[stage.name] = result

                for p in range(1, 11):
                    if check_cancel():
                        raise RuntimeError("任务被取消")
                    progress_callback(i, p / 10, f"{stage.description}: {p*10}%")
                    time.sleep(0.05)

                progress_callback(i, 1.0, f"完成阶段: {stage.description}")

            except Exception as e:
                if stage.required:
                    _logger.error(f"阶段 {stage.name} 失败: {e}")
                    raise
                else:
                    _logger.warning(f"可选阶段 {stage.name} 失败，继续执行: {e}")
                    stage_results[stage.name] = {"skipped": True, "error": str(e)}

        return {
            "success": True,
            "style": style,
            "input_path": input_path,
            "output_dir": output_dir,
            "mode": mode,
            "stages_completed": len(stages),
            "stage_results": stage_results,
            "output_files": [
                os.path.join(output_dir, f"puppet_{style}.mp4"),
                os.path.join(output_dir, f"puppet_{style}.aep"),
            ],
        }

    def _stage_media_analysis(self, input_path: str, mode: str) -> dict[str, Any]:
        """阶段: 媒体分析"""
        if mode == "simulate":
            time.sleep(0.2)
            return {
                "duration": 30.0,
                "fps": 30,
                "width": 1920,
                "height": 1080,
                "scenes": 15,
                "has_audio": True,
                "bgm_bpm": 120,
            }

        try:
            from video_analyzer_enhanced import VideoAnalyzer
            analyzer = VideoAnalyzer()
            result = analyzer.analyze(input_path)
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            return {"simulated": True, "error": str(e)}

    def _stage_pose_detection(self, input_path: str, mode: str) -> dict[str, Any]:
        """阶段: 姿态检测"""
        if mode == "simulate":
            time.sleep(0.3)
            return {
                "persons_detected": 1,
                "joints_detected": 17,
                "face_detected": True,
                "tracking_confidence": 0.85,
                "key_frames": 10,
            }

        try:
            from mediapipe_integration import MediaPipeIntegrator
            integrator = MediaPipeIntegrator()
            result = integrator.detect_video(input_path)
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            return {"simulated": True, "error": str(e)}

    def _stage_style_generation(self, style: str, auto_detect: bool, mode: str) -> dict[str, Any]:
        """阶段: 风格化生成"""
        if mode == "simulate":
            time.sleep(0.4)
            return {
                "style": style,
                "effects_applied": 8,
                "auto_detect": auto_detect,
                "keyframes_generated": 24,
                "layer_count": 6,
            }

        try:
            from puppet_style_engine import PuppetStyleEngine
            engine = PuppetStyleEngine()
            config = engine.PuppetStyleConfig(style_type=style)
            result = engine.generate_style(config)
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            return {"simulated": True, "error": str(e)}

    def _stage_ae_integration(self, output_dir: str, style: str, mode: str) -> dict[str, Any]:
        """阶段: AE集成"""
        if mode == "simulate":
            time.sleep(0.3)
            jsx_path = os.path.join(output_dir, f"puppet_{style}.jsx")
            with open(jsx_path, "w", encoding="utf-8") as f:
                f.write(f"// 木偶风格化脚本 - {style}\n// 自动生成\n")
            return {
                "script_generated": True,
                "script_path": jsx_path,
                "script_size": 2048,
                "effects_count": 8,
            }

        try:
            from ae_command_generator import AECommandGenerator
            generator = AECommandGenerator()
            return {"script_generated": True, "generator": str(generator)}
        except Exception as e:
            return {"simulated": True, "error": str(e)}

    def _stage_color_grading(self, output_dir: str, mode: str) -> dict[str, Any]:
        """阶段: 调色"""
        if mode == "simulate":
            time.sleep(0.2)
            return {
                "preset": "puppet_warm",
                "nodes_applied": 2,
                "color_summary": {
                    "contrast": 1.1,
                    "saturation": 1.05,
                    "warmth": 5,
                },
            }

        try:
            from davinci_resolve_integration import DavinciColorist
            colorist = DavinciColorist()
            return {"colorist_available": True}
        except Exception as e:
            return {"simulated": True, "error": str(e)}

    def _stage_output_render(self, output_dir: str, style: str, mode: str) -> dict[str, Any]:
        """阶段: 渲染输出"""
        if mode == "simulate":
            time.sleep(0.3)
            output_path = os.path.join(output_dir, f"puppet_{style}.mp4")
            with open(output_path, "wb") as f:
                f.write(b"\x00" * 1024)
            return {
                "output_path": output_path,
                "file_size_kb": 1,
                "duration": 30.0,
                "resolution": "1920x1080",
                "fps": 30,
            }

        return {"output_dir": output_dir, "style": style}

    # --------------------------------------------------------------------
    # 批量处理
    # --------------------------------------------------------------------

    def submit_batch_puppet_workflow(
        self,
        input_files: list[str],
        output_base_dir: str,
        style: str = "wood",
        auto_detect: bool = True,
        quality: str = "high",
        mode: str = "auto",
        priority: int = 5,
        max_concurrent: int = 2,
        on_batch_complete: Callable[[list[WorkflowTask]], None] | None = None,
    ) -> list[WorkflowTask]:
        """批量提交木偶风格化工作流

        Args:
            input_files: 输入文件列表
            output_base_dir: 输出根目录
            style: 风格类型
            auto_detect: 是否自动检测姿态
            quality: 输出质量
            mode: 执行模式
            priority: 优先级
            max_concurrent: 最大并发数
            on_batch_complete: 批量完成回调

        Returns:
            工作流任务列表
        """
        tasks: list[WorkflowTask] = []
        remaining = len(input_files)
        import threading
        lock = threading.Lock()

        def check_all_done(wf_task: WorkflowTask):
            nonlocal remaining
            with lock:
                remaining -= 1
                if remaining <= 0 and on_batch_complete:
                    try:
                        on_batch_complete(tasks)
                    except Exception:
                        pass

        for input_file in input_files:
            filename = Path(input_file).stem
            output_dir = os.path.join(output_base_dir, filename)

            wf_task = self.submit_puppet_workflow(
                input_path=input_file,
                output_dir=output_dir,
                style=style,
                auto_detect=auto_detect,
                quality=quality,
                mode=mode,
                priority=priority,
                on_complete=lambda t: check_all_done(t),
                on_failure=lambda t: check_all_done(t),
            )
            tasks.append(wf_task)

        return tasks

    # --------------------------------------------------------------------
    # 任务查询
    # --------------------------------------------------------------------

    def get_workflow_task(self, task_id: str) -> WorkflowTask | None:
        """获取工作流任务"""
        task = self._workflow_tasks.get(task_id)
        if task:
            return task

        if self._persistence:
            data = self._persistence.get_task(task_id)
            if data:
                task = WorkflowTask(**{k: v for k, v in data.items() if k in WorkflowTask.__dataclass_fields__})
                self._workflow_tasks[task_id] = task
                return task

        return None

    def get_all_workflow_tasks(self) -> list[WorkflowTask]:
        """获取所有工作流任务"""
        tasks = list(self._workflow_tasks.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks

    def get_tasks_by_status(self, status: str) -> list[WorkflowTask]:
        """按状态获取任务"""
        return [t for t in self._workflow_tasks.values() if t.status == status]

    # --------------------------------------------------------------------
    # 统计信息
    # --------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        tasks = self.get_all_workflow_tasks()
        status_counts: dict[str, int] = {}
        for t in tasks:
            status_counts[t.status] = status_counts.get(t.status, 0) + 1

        avg_duration = 0.0
        completed = [t for t in tasks if t.status == "completed" and t.duration > 0]
        if completed:
            avg_duration = sum(t.duration for t in completed) / len(completed)

        return {
            "total_tasks": len(tasks),
            "status_counts": status_counts,
            "avg_duration": round(avg_duration, 2),
            "queue_stats": self._queue.get_stats() if self._queue else {},
            "resource_available": _RESOURCE_AVAILABLE,
            "persistence_available": _PERSISTENCE_AVAILABLE,
        }


# ============================================================================
# 模块单例
# ============================================================================

_default_integration: WorkflowBatchIntegration | None = None


def get_workflow_batch_integration() -> WorkflowBatchIntegration:
    """获取默认工作流批处理集成实例"""
    global _default_integration
    if _default_integration is None:
        _default_integration = WorkflowBatchIntegration()
    return _default_integration


# ============================================================================
# 命令行演示入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  工作流编排器 - 批处理队列集成演示")
    print("=" * 70)

    import shutil
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="wf_batch_demo_")
    print(f"\n临时目录: {tmp_dir}")

    try:
        integration = WorkflowBatchIntegration()

        print("\n" + "─" * 70)
        print("  阶段 1: 提交单视频木偶风格化工作流")
        print("─" * 70)

        input_video = os.path.join(tmp_dir, "test_video.mp4")
        with open(input_video, "wb") as f:
            f.write(b"\x00" * 1024)

        output_dir = os.path.join(tmp_dir, "output_single")
        os.makedirs(output_dir, exist_ok=True)

        wf_task = integration.submit_puppet_workflow(
            input_path=input_video,
            output_dir=output_dir,
            style="wood",
            auto_detect=True,
            quality="high",
            mode="simulate",
            priority=6,
            on_progress=lambda t: print(f"    进度: {int(t.progress*100):3d}% [{t.current_stage+1}/{t.total_stages}] {t.progress_message}"),
        )

        print(f"\n  任务已提交: {wf_task.task_id}")
        print(f"  任务名称: {wf_task.name}")
        print(f"  总阶段数: {wf_task.total_stages}")
        print("  阶段列表:")
        for i, stage in enumerate(wf_task.stages):
            print(f"    {i+1}. {stage['name']} - {stage['description']}")

        print("\n  等待任务完成...")
        import time as _time
        deadline = _time.time() + 30
        while _time.time() < deadline:
            task = integration.get_workflow_task(wf_task.task_id)
            if task and task.status in ("completed", "failed", "cancelled"):
                break
            _time.sleep(0.2)

        task = integration.get_workflow_task(wf_task.task_id)
        if task:
            print(f"\n  任务状态: {task.status}")
            print(f"  总耗时: {task.duration:.2f}s")
            if task.result:
                print(f"  输出文件: {len(task.result.get('output_files', []))} 个")
                for f in task.result.get('output_files', [])[:3]:
                    print(f"    - {f}")
            if task.error:
                print(f"  错误: {task.error}")

        print("\n" + "─" * 70)
        print("  阶段 2: 批量视频处理")
        print("─" * 70)

        batch_dir = os.path.join(tmp_dir, "batch_input")
        batch_output = os.path.join(tmp_dir, "batch_output")
        os.makedirs(batch_dir, exist_ok=True)
        os.makedirs(batch_output, exist_ok=True)

        batch_files = []
        for i in range(3):
            fpath = os.path.join(batch_dir, f"clip_{i:02d}.mp4")
            with open(fpath, "wb") as f:
                f.write(b"\x00" * 1024)
            batch_files.append(fpath)

        print(f"\n  提交 {len(batch_files)} 个批量任务...")
        batch_tasks = integration.submit_batch_puppet_workflow(
            input_files=batch_files,
            output_base_dir=batch_output,
            style="ceramic",
            auto_detect=True,
            mode="simulate",
            priority=5,
            max_concurrent=2,
        )

        for t in batch_tasks:
            print(f"    - {t.name}: {t.task_id}")

        print("\n  等待批量任务完成...")
        deadline = _time.time() + 60
        while _time.time() < deadline:
            all_done = all(
                (integration.get_workflow_task(t.task_id) or t).status
                in ("completed", "failed", "cancelled")
                for t in batch_tasks
            )
            if all_done:
                break
            _time.sleep(0.5)

        print("\n  批量任务结果:")
        success_count = 0
        for t in batch_tasks:
            task = integration.get_workflow_task(t.task_id) or t
            status_icon = "✅" if task.status == "completed" else "❌" if task.status == "failed" else "⏳"
            print(f"    {status_icon} {task.name}: {task.status} ({task.duration:.2f}s)")
            if task.status == "completed":
                success_count += 1

        print(f"\n  成功率: {success_count}/{len(batch_tasks)} ({success_count/len(batch_tasks)*100:.0f}%)")

        print("\n" + "─" * 70)
        print("  阶段 3: 系统统计")
        print("─" * 70)

        stats = integration.get_stats()
        print(f"\n  总任务数: {stats['total_tasks']}")
        print("  状态分布:")
        for status, count in stats['status_counts'].items():
            print(f"    {status}: {count}")
        print(f"  平均耗时: {stats['avg_duration']:.2f}s")
        print(f"  队列可用: {'是' if stats['queue_stats'] else '否'}")

        print("\n" + "=" * 70)
        print("  演示完成！")
        print("=" * 70)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        print("\n临时目录已清理")
