#!/usr/bin/env python3
"""
工作流编排引擎核心 - WorkflowOrchestrator v1.0

设计原则（基于工作流模式）：
1. 声明式定义：通过任务定义和依赖关系描述工作流
2. 依赖驱动：任务按依赖关系自动排序执行
3. 并行执行：无依赖的任务可并行执行
4. 容错恢复：支持重试、降级和补偿操作
5. 动态调整：运行时可暂停、取消、恢复工作流
6. 可观测：集成日志、追踪和指标

工作流模式支持：
- 顺序流（Sequential Flow）
- 并行流（Parallel Flow）
- 条件分支（Conditional Branch）
- 循环（Loop）
- 子流程（Sub-workflow）
- 错误处理（Error Handling）

架构参考：
- Prefect Workflow Engine
- SpiffWorkflow
- Airflow DAG
- Argo Workflows
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union


class TaskStatus(Enum):
    """任务状态"""
    PENDING = auto()       # 等待执行
    QUEUED = auto()        # 已入队
    RUNNING = auto()       # 执行中
    COMPLETED = auto()     # 完成
    FAILED = auto()        # 失败
    SKIPPED = auto()       # 跳过
    RETRYING = auto()      # 重试中


class TaskType(Enum):
    """任务类型"""
    PERCEPTION = "perception"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    SILHOUETTE_ROTO = "silhouette_roto"
    SILHOUETTE_TRACK = "silhouette_track"
    SILHOUETTE_PAINT = "silhouette_paint"
    AE_COMPILE = "ae_compile"
    AE_EXECUTE = "ae_execute"
    AE_RENDER = "ae_render"
    TOPAZ_ENHANCE = "topaz_enhance"
    RUNWAY_GENERATE = "runway_generate"
    PIKA_GENERATE = "pika_generate"
    BLENDER_RENDER = "blender_render"
    FFMPEG_TRANSCODE = "ffmpeg_transcode"
    FEEDBACK = "feedback"
    SUB_WORKFLOW = "sub_workflow"


class WorkflowStatus(Enum):
    """工作流状态"""
    IDLE = auto()          # 初始状态
    RUNNING = auto()       # 运行中
    PAUSED = auto()        # 暂停
    COMPLETED = auto()     # 完成
    FAILED = auto()        # 失败
    CANCELLED = auto()     # 取消


@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str
    task_type: TaskType
    name: str
    func: Callable[..., Any]
    args: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    retry_delay_ms: int = 2000
    timeout_ms: Optional[int] = None
    max_parallel: int = 1
    skip_on_failure: bool = False
    fallback_func: Optional[Callable[..., Any]] = None


@dataclass
class TaskInstance:
    """任务实例"""
    task_def: TaskDefinition
    instance_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[Exception] = None
    retry_attempts: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: float = 0.0


@dataclass
class WorkflowContext:
    """工作流上下文"""
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.IDLE
    tasks: Dict[str, TaskInstance] = field(default_factory=dict)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    progress: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Exception] = None


class WorkflowOrchestrator:
    """工作流编排引擎"""

    def __init__(self, max_concurrent_tasks: int = 5):
        self._logger = logging.getLogger(f"{__name__}.WorkflowOrchestrator")
        self._max_concurrent = max_concurrent_tasks
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._context: Optional[WorkflowContext] = None
        self._running = False
        self._tasks_def: List[TaskDefinition] = []
        self._task_dependencies: Dict[str, Set[str]] = {}
        self._task_dependents: Dict[str, Set[str]] = {}
        self._completed_tasks: Set[str] = set()
        self._failed_tasks: Set[str] = set()
        self._progress_callbacks: List[Callable[[float, Dict], None]] = []

    # -------------------------------------------------------------------------
    # 工作流定义 API
    # -------------------------------------------------------------------------

    def add_task(self, task_def: TaskDefinition) -> None:
        """添加任务定义"""
        self._tasks_def.append(task_def)
        self._task_dependencies[task_def.task_id] = set(task_def.dependencies)
        for dep_id in task_def.dependencies:
            if dep_id not in self._task_dependents:
                self._task_dependents[dep_id] = set()
            self._task_dependents[dep_id].add(task_def.task_id)

    def add_tasks(self, tasks: List[TaskDefinition]) -> None:
        """批量添加任务"""
        for task in tasks:
            self.add_task(task)

    def get_task_def(self, task_id: str) -> Optional[TaskDefinition]:
        """获取任务定义"""
        for task in self._tasks_def:
            if task.task_id == task_id:
                return task
        return None

    # -------------------------------------------------------------------------
    # 依赖分析
    # -------------------------------------------------------------------------

    def _analyze_dependencies(self) -> List[str]:
        """分析任务依赖，返回执行顺序拓扑排序"""
        in_degree = {task.task_id: len(task.dependencies) for task in self._tasks_def}
        queue = [task.task_id for task in self._tasks_def if in_degree[task.task_id] == 0]
        result = []

        while queue:
            task_id = queue.pop(0)
            result.append(task_id)

            for dependent in self._task_dependents.get(task_id, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(self._tasks_def):
            cycle_tasks = set(self._task_dependencies.keys()) - set(result)
            self._logger.warning(f"检测到循环依赖: {cycle_tasks}")

        return result

    def _get_ready_tasks(self) -> List[str]:
        """获取当前就绪的任务（所有依赖已完成或可跳过失败）"""
        ready = []
        for task_def in self._tasks_def:
            task_id = task_def.task_id
            if task_id in self._completed_tasks or task_id in self._failed_tasks:
                continue

            instance = self._context.tasks.get(task_id)
            if instance and instance.status in [TaskStatus.RUNNING, TaskStatus.QUEUED]:
                continue

            deps = self._task_dependencies.get(task_id, set())
            all_deps_met = True
            for dep in deps:
                if dep in self._completed_tasks:
                    continue
                dep_def = self.get_task_def(dep)
                if dep in self._failed_tasks and dep_def and dep_def.skip_on_failure:
                    continue
                all_deps_met = False
                break
            if all_deps_met:
                ready.append(task_id)

        return ready

    # -------------------------------------------------------------------------
    # 工作流执行
    # -------------------------------------------------------------------------

    async def run(self, workflow_id: str = None, initial_data: Dict[str, Any] = None) -> WorkflowContext:
        """执行工作流"""
        self._workflow_id = workflow_id or str(uuid.uuid4())
        self._context = WorkflowContext(
            workflow_id=self._workflow_id,
            data=initial_data or {},
        )
        self._completed_tasks = set()
        self._failed_tasks = set()

        # 初始化任务实例
        for task_def in self._tasks_def:
            self._context.tasks[task_def.task_id] = TaskInstance(task_def=task_def)

        self._logger.info(f"启动工作流: {self._workflow_id}, 共 {len(self._tasks_def)} 个任务")

        self._context.status = WorkflowStatus.RUNNING
        self._context.start_time = time.time()
        self._running = True

        try:
            await self._execute_workflow()
        except Exception as e:
            self._logger.error(f"工作流执行异常: {e}")
            self._context.error = e
            self._context.status = WorkflowStatus.FAILED

        self._context.end_time = time.time()
        self._running = False

        self._logger.info(f"工作流结束: {self._workflow_id}, 状态: {self._context.status.name}")
        return self._context

    async def _execute_workflow(self) -> None:
        """执行工作流主循环"""
        task_order = self._analyze_dependencies()
        self._logger.debug(f"任务执行顺序: {task_order}")

        while self._running:
            ready_tasks = self._get_ready_tasks()

            if not ready_tasks:
                if self._is_workflow_complete():
                    self._context.status = WorkflowStatus.COMPLETED
                    break
                if self._is_workflow_failed():
                    self._context.status = WorkflowStatus.FAILED
                    break
                await asyncio.sleep(0.1)
                continue

            tasks_to_run = [
                self._run_task(task_id)
                for task_id in ready_tasks
                if self._can_run_task(task_id)
            ]

            if tasks_to_run:
                await asyncio.gather(*tasks_to_run, return_exceptions=True)

            self._update_progress()

    def _can_run_task(self, task_id: str) -> bool:
        """检查任务是否可以运行"""
        instance = self._context.tasks.get(task_id)
        if not instance:
            return False

        if instance.status in [TaskStatus.RUNNING, TaskStatus.QUEUED]:
            return False

        if instance.status == TaskStatus.FAILED:
            task_def = instance.task_def
            if instance.retry_attempts < task_def.retry_count:
                return True
            return False

        return True

    async def _run_task(self, task_id: str) -> None:
        """运行单个任务"""
        instance = self._context.tasks.get(task_id)
        if not instance:
            return

        task_def = instance.task_def

        async with self._semaphore:
            instance.status = TaskStatus.RUNNING
            instance.start_time = time.time()
            self._logger.info(f"开始执行任务: {task_id} ({task_def.name})")

            try:
                if task_def.timeout_ms:
                    result = await asyncio.wait_for(
                        self._execute_task_func(task_def, instance),
                        timeout=task_def.timeout_ms / 1000
                    )
                else:
                    result = await self._execute_task_func(task_def, instance)

                instance.result = result
                instance.status = TaskStatus.COMPLETED
                self._completed_tasks.add(task_id)
                self._logger.info(f"任务完成: {task_id}, 耗时: {instance.duration:.2f}s")

            except asyncio.TimeoutError:
                instance.error = TimeoutError(f"任务超时: {task_def.timeout_ms}ms")
                await self._handle_task_failure(task_id, instance)

            except Exception as e:
                instance.error = e
                await self._handle_task_failure(task_id, instance)

            finally:
                instance.end_time = time.time()
                instance.duration = (instance.end_time - instance.start_time) if instance.start_time else 0

    async def _execute_task_func(self, task_def: TaskDefinition, instance: TaskInstance) -> Any:
        """执行任务函数"""
        args = task_def.args.copy()

        for dep_id in task_def.dependencies:
            dep_instance = self._context.tasks.get(dep_id)
            if dep_instance and dep_instance.result is not None:
                args[f"_{dep_id}_result"] = dep_instance.result

        if asyncio.iscoroutinefunction(task_def.func):
            return await task_def.func(**args, context=self._context)
        else:
            return await asyncio.to_thread(task_def.func, **args, context=self._context)

    async def _handle_task_failure(self, task_id: str, instance: TaskInstance) -> None:
        """处理任务失败"""
        task_def = instance.task_def

        if instance.retry_attempts < task_def.retry_count:
            instance.retry_attempts += 1
            instance.status = TaskStatus.RETRYING
            self._logger.warning(f"任务重试: {task_id}, 第 {instance.retry_attempts} 次, 错误: {instance.error}")

            await asyncio.sleep(task_def.retry_delay_ms / 1000)

            instance.status = TaskStatus.PENDING

        else:
            instance.status = TaskStatus.FAILED
            self._failed_tasks.add(task_id)
            self._logger.error(f"任务失败: {task_id}, 错误: {instance.error}")

            if task_def.fallback_func:
                self._logger.info(f"执行降级方案: {task_id}")
                try:
                    fallback_result = await self._execute_task_func(
                        TaskDefinition(
                            task_id=f"{task_id}_fallback",
                            task_type=task_def.task_type,
                            name=f"{task_def.name} (Fallback)",
                            func=task_def.fallback_func,
                            args=task_def.args,
                        ),
                        instance
                    )
                    instance.result = fallback_result
                    instance.status = TaskStatus.COMPLETED
                    self._completed_tasks.add(task_id)
                    self._failed_tasks.remove(task_id)
                    self._logger.info(f"降级成功: {task_id}")
                except Exception as fallback_error:
                    self._logger.error(f"降级失败: {task_id}, 错误: {fallback_error}")

    def _is_workflow_complete(self) -> bool:
        """检查工作流是否完成"""
        total = len(self._tasks_def)
        done = len(self._completed_tasks)
        for task_def in self._tasks_def:
            if task_def.task_id in self._failed_tasks and task_def.skip_on_failure:
                done += 1
        return done == total

    def _is_workflow_failed(self) -> bool:
        """检查工作流是否失败"""
        for task_def in self._tasks_def:
            if task_def.task_id in self._failed_tasks and not task_def.skip_on_failure:
                return True
        return False

    def _update_progress(self) -> None:
        """更新进度"""
        total = len(self._tasks_def)
        completed = len(self._completed_tasks)
        for task_def in self._tasks_def:
            if task_def.task_id in self._failed_tasks and task_def.skip_on_failure:
                completed += 1
        self._context.progress = completed / total if total > 0 else 0.0

        for callback in self._progress_callbacks:
            try:
                callback(self._context.progress, {
                    "completed": completed,
                    "total": total,
                    "failed": len(self._failed_tasks),
                    "workflow_id": self._context.workflow_id,
                })
            except Exception as e:
                self._logger.error(f"进度回调错误: {e}")

    # -------------------------------------------------------------------------
    # 工作流控制
    # -------------------------------------------------------------------------

    def pause(self) -> None:
        """暂停工作流"""
        self._running = False
        self._context.status = WorkflowStatus.PAUSED
        self._logger.info(f"工作流暂停: {self._workflow_id}")

    def resume(self) -> None:
        """恢复工作流"""
        self._running = True
        self._context.status = WorkflowStatus.RUNNING
        self._logger.info(f"工作流恢复: {self._workflow_id}")

    def cancel(self) -> None:
        """取消工作流"""
        self._running = False
        self._context.status = WorkflowStatus.CANCELLED
        self._logger.info(f"工作流取消: {self._workflow_id}")

    def add_progress_callback(self, callback: Callable[[float, Dict], None]) -> None:
        """添加进度回调"""
        self._progress_callbacks.append(callback)

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    @property
    def context(self) -> Optional[WorkflowContext]:
        return self._context

    @property
    def is_running(self) -> bool:
        return self._running

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        if not self._context:
            return None
        instance = self._context.tasks.get(task_id)
        return instance.status if instance else None

    def get_task_result(self, task_id: str) -> Any:
        """获取任务结果"""
        if not self._context:
            return None
        instance = self._context.tasks.get(task_id)
        return instance.result if instance else None

    def get_stats(self) -> Dict[str, Any]:
        """获取工作流统计信息"""
        if not self._context:
            return {"status": "IDLE"}

        task_stats = {}
        for task_id, instance in self._context.tasks.items():
            task_stats[task_id] = {
                "status": instance.status.name,
                "duration": instance.duration,
                "retry_attempts": instance.retry_attempts,
            }

        duration = 0.0
        if self._context.start_time:
            end = self._context.end_time or time.time()
            duration = end - self._context.start_time

        return {
            "workflow_id": self._context.workflow_id,
            "status": self._context.status.name,
            "progress": f"{self._context.progress * 100:.1f}%",
            "duration_seconds": duration,
            "completed_tasks": len(self._completed_tasks),
            "failed_tasks": len(self._failed_tasks),
            "total_tasks": len(self._tasks_def),
            "task_stats": task_stats,
        }

    # -------------------------------------------------------------------------
    # 预设工作流模板
    # -------------------------------------------------------------------------

    def build_default_pipeline(self, pipeline_funcs: Dict[str, Callable]) -> None:
        """构建默认 AE Agent 工作流"""
        self._tasks_def = []

        perception_task = TaskDefinition(
            task_id="perception",
            task_type=TaskType.PERCEPTION,
            name="感知层 - 音视频分析",
            func=pipeline_funcs.get("perceive"),
            retry_count=1,
            retry_delay_ms=3000,
        )

        understanding_task = TaskDefinition(
            task_id="understanding",
            task_type=TaskType.UNDERSTANDING,
            name="理解层 - 语义理解",
            func=pipeline_funcs.get("understand"),
            dependencies=["perception"],
            retry_count=1,
            retry_delay_ms=2000,
        )

        planning_task = TaskDefinition(
            task_id="planning",
            task_type=TaskType.PLANNING,
            name="规划层 - 任务规划",
            func=pipeline_funcs.get("plan"),
            dependencies=["understanding"],
            retry_count=1,
            retry_delay_ms=2000,
        )

        silhouette_task = TaskDefinition(
            task_id="silhouette",
            task_type=TaskType.SILHOUETTE_ROTO,
            name="Silhouette 处理",
            func=pipeline_funcs.get("execute_silhouette"),
            dependencies=["planning"],
            retry_count=2,
            retry_delay_ms=5000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("silhouette_fallback"),
        )

        ae_compile_task = TaskDefinition(
            task_id="ae_compile",
            task_type=TaskType.AE_COMPILE,
            name="AE 编译",
            func=pipeline_funcs.get("compile"),
            dependencies=["planning"],
            retry_count=2,
            retry_delay_ms=3000,
        )

        ae_execute_task = TaskDefinition(
            task_id="ae_execute",
            task_type=TaskType.AE_EXECUTE,
            name="AE 执行",
            func=pipeline_funcs.get("execute_ae"),
            dependencies=["ae_compile", "silhouette"],
            retry_count=3,
            retry_delay_ms=5000,
            timeout_ms=120000,
        )

        # 可选阶段 - Topaz 视频增强（与 Silhouette/AE 并行，依赖规划层）
        topaz_task = TaskDefinition(
            task_id="topaz_enhance",
            task_type=TaskType.TOPAZ_ENHANCE,
            name="Topaz 视频增强",
            func=pipeline_funcs.get("execute_topaz"),
            dependencies=["planning"],
            retry_count=1,
            retry_delay_ms=3000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("topaz_fallback"),
        )

        # 可选阶段 - RunwayML 视频生成（依赖规划层，AI 生成路径）
        runway_task = TaskDefinition(
            task_id="runway_generate",
            task_type=TaskType.RUNWAY_GENERATE,
            name="RunwayML 视频生成",
            func=pipeline_funcs.get("execute_runway"),
            dependencies=["planning"],
            retry_count=2,
            retry_delay_ms=5000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("runway_fallback"),
        )

        # 可选阶段 - Pika 视频生成（依赖规划层，AI 生成路径）
        pika_task = TaskDefinition(
            task_id="pika_generate",
            task_type=TaskType.PIKA_GENERATE,
            name="Pika 视频生成",
            func=pipeline_funcs.get("execute_pika"),
            dependencies=["planning"],
            retry_count=2,
            retry_delay_ms=5000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("pika_fallback"),
        )

        # 可选阶段 - Blender 3D 渲染（依赖规划层，3D 合成路径）
        blender_task = TaskDefinition(
            task_id="blender_render",
            task_type=TaskType.BLENDER_RENDER,
            name="Blender 3D 渲染",
            func=pipeline_funcs.get("execute_blender"),
            dependencies=["planning"],
            retry_count=1,
            retry_delay_ms=3000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("blender_fallback"),
        )

        # 可选阶段 - FFmpeg 转码/滤镜（依赖 AE 执行，后处理路径）
        ffmpeg_task = TaskDefinition(
            task_id="ffmpeg_transcode",
            task_type=TaskType.FFMPEG_TRANSCODE,
            name="FFmpeg 转码处理",
            func=pipeline_funcs.get("execute_ffmpeg"),
            dependencies=["ae_execute"],
            retry_count=1,
            retry_delay_ms=2000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("ffmpeg_fallback"),
        )

        feedback_task = TaskDefinition(
            task_id="feedback",
            task_type=TaskType.FEEDBACK,
            name="反馈层 - 结果评估",
            func=pipeline_funcs.get("feedback"),
            dependencies=["ae_execute"],
            retry_count=0,
        )

        self.add_tasks([
            perception_task,
            understanding_task,
            planning_task,
            silhouette_task,
            ae_compile_task,
            ae_execute_task,
            topaz_task,
            runway_task,
            pika_task,
            blender_task,
            ffmpeg_task,
            feedback_task,
        ])

    # -------------------------------------------------------------------------
    # 工作流持久化
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        if not self._context:
            return {}

        return {
            "workflow_id": self._context.workflow_id,
            "status": self._context.status.name,
            "start_time": self._context.start_time,
            "end_time": self._context.end_time,
            "progress": self._context.progress,
            "data": self._context.data,
            "error": str(self._context.error) if self._context.error else None,
            "tasks": {
                task_id: {
                    "task_type": instance.task_def.task_type.value,
                    "name": instance.task_def.name,
                    "status": instance.status.name,
                    "result": instance.result,
                    "error": str(instance.error) if instance.error else None,
                    "retry_attempts": instance.retry_attempts,
                    "duration": instance.duration,
                }
                for task_id, instance in self._context.tasks.items()
            },
        }

    def save_to_file(self, path: str) -> None:
        """保存到文件"""
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def create_orchestrator(max_concurrent: int = 5) -> WorkflowOrchestrator:
    """创建工作流编排器"""
    return WorkflowOrchestrator(max_concurrent_tasks=max_concurrent)