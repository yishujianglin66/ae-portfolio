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
import inspect
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

# 安全护栏组件（从 4b8aa81 移植，2026-08-27）：缺失时降级为无护栏，不阻断导入
try:
    from core.security import (
        AuditLogEntry,
        SecurityManager,
        ApprovalRequest,
        SecurityError,
        RiskLevel,
    )
except ImportError:
    AuditLogEntry = None
    SecurityManager = None
    ApprovalRequest = None
    SecurityError = None
    RiskLevel = None


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
    STYLE_CLASSIFICATION = "style_classification"  # 风格分类（4b8aa81 补回，style_transfer_agents 使用）
    PARAM_MAPPING = "param_mapping"  # 参数映射（4b8aa81 补回，style_transfer_agents 使用）
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
    # 以下成员从 4b8aa81 补回（L1-L5 风险映射要求覆盖全部任务类型）
    PR_IMPORT = "pr_import"
    PR_EDIT = "pr_edit"
    PR_TRANSITION = "pr_transition"
    PR_EXPORT = "pr_export"
    FLUX3_GENERATE = "flux3_generate"
    PS_PREPROCESS = "ps_preprocess"          # PS 预处理
    DAVINCI_GRADE = "davinci_grade"          # DaVinci 调色
    C4D_MOGRAPH = "c4d_mograph"              # C4D 运动图形
    FFMPEG_EXPORT = "ffmpeg_export"          # FFmpeg 最终导出
    WHISPER_SUBTITLE = "whisper_subtitle"    # Whisper 字幕
    AME_ENCODE = "ame_encode"                # AME 编码输出
    # H3 生成/编辑类任务类型
    IMAGE_GENERATION = "image_generation"
    INPAINTING = "inpainting"
    MINIMAX_H3_GENERATE = "minimax_h3_generate"
    MOTION_TRANSFER = "motion_transfer"
    OBJECT_REPLACEMENT = "object_replacement"
    RATE_ADJUSTMENT = "rate_adjustment"
    SCENE_ALTERATION = "scene_alteration"
    STYLE_TRANSFER = "style_transfer"
    SUBTITLE_MODIFICATION = "subtitle_modification"
    VIDEO_EDITING = "video_editing"
    VIDEO_GENERATION = "video_generation"


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

    def __init__(self, max_concurrent_tasks: int = 5, enable_security: bool = True):
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
        # L1-L5 RiskGuard 初始化（从 4b8aa81 移植，2026-08-27）
        self._enable_security = enable_security and SecurityManager is not None
        self._security_manager: Optional[Any] = (
            SecurityManager() if self._enable_security else None
        )
        self._risk_assessor = None
        self._sandbox_policy = None
        self._approval_policy = None
        self._audit_chain = None
        if self._enable_security:
            try:
                from core.security import ApprovalPolicy, AuditChain, RiskAssessor, SandboxPolicy
                self._risk_assessor = RiskAssessor(workspace_root=Path.cwd())
                self._sandbox_policy = SandboxPolicy(workspace_root=Path.cwd())
                self._approval_policy = ApprovalPolicy()
                self._audit_chain = AuditChain(Path.cwd() / "logs" / "audit_chain.jsonl")
            except Exception as exc:
                # fail-closed：安全开关开启时组件初始化失败不允许静默降级
                raise RuntimeError(f"RiskGuard 初始化失败(安全开关已启用): {exc}") from exc

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
                # SecurityError 不重试（审批拒绝等安全硬约束，重试无意义）
                if SecurityError is not None and isinstance(e, SecurityError):
                    instance.status = TaskStatus.FAILED
                    self._failed_tasks.add(task_id)
                    self._logger.error(f"任务被安全护栏拦截(不重试): {task_id}, 错误: {e}")
                else:
                    await self._handle_task_failure(task_id, instance)

            finally:
                instance.end_time = time.time()
                instance.duration = (instance.end_time - instance.start_time) if instance.start_time else 0

    async def _execute_task_func(self, task_def: TaskDefinition, instance: TaskInstance) -> Any:
        """执行任务函数"""
        if task_def.func is None:
            return None

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

        # 可选阶段 - Flux 3 音画一体生成（依赖规划层，AI 生成路径）
        flux3_task = TaskDefinition(
            task_id="flux3_generate",
            task_type=TaskType.FLUX3_GENERATE,
            name="Flux 3 音画一体生成",
            func=pipeline_funcs.get("execute_flux3"),
            dependencies=["planning"],
            retry_count=2,
            retry_delay_ms=5000,
            skip_on_failure=True,
            fallback_func=pipeline_funcs.get("flux3_fallback"),
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

        # PS 预处理（依赖感知层，提取 PSD 图层）
        ps_preprocess_task = TaskDefinition(
            task_id="ps_preprocess",
            task_type=TaskType.PS_PREPROCESS,
            name="PS 预处理 - 图层/LUT",
            func=pipeline_funcs.get("execute_ps_preprocess"),
            dependencies=["perception"],
            retry_count=1,
            retry_delay_ms=3000,
            skip_on_failure=True,
        )

        # DaVinci 调色（依赖 Topaz 增强或 AE 执行）
        davinci_grade_task = TaskDefinition(
            task_id="davinci_grade",
            task_type=TaskType.DAVINCI_GRADE,
            name="DaVinci 调色",
            func=pipeline_funcs.get("execute_davinci_grade"),
            dependencies=["topaz_enhance"],
            retry_count=2,
            retry_delay_ms=5000,
            skip_on_failure=True,
        )

        # C4D 运动图形（依赖规划层，与 Blender 并行）
        c4d_mograph_task = TaskDefinition(
            task_id="c4d_mograph",
            task_type=TaskType.C4D_MOGRAPH,
            name="C4D MoGraph 渲染",
            func=pipeline_funcs.get("execute_c4d_mograph"),
            dependencies=["planning"],
            retry_count=1,
            retry_delay_ms=3000,
            skip_on_failure=True,
        )

        # Whisper 字幕生成（依赖感知层，与理解层并行）
        whisper_subtitle_task = TaskDefinition(
            task_id="whisper_subtitle",
            task_type=TaskType.WHISPER_SUBTITLE,
            name="Whisper 字幕生成",
            func=pipeline_funcs.get("execute_whisper_subtitle"),
            dependencies=["perception"],
            retry_count=1,
            retry_delay_ms=2000,
            skip_on_failure=True,
        )

        # FFmpeg 最终导出（依赖 AE 执行 + DaVinci 调色）
        ffmpeg_export_task = TaskDefinition(
            task_id="ffmpeg_export",
            task_type=TaskType.FFMPEG_EXPORT,
            name="FFmpeg 最终导出",
            func=pipeline_funcs.get("execute_ffmpeg_export"),
            dependencies=["ae_execute", "davinci_grade"],
            retry_count=2,
            retry_delay_ms=3000,
            skip_on_failure=True,
        )

        # AME 编码输出（依赖 FFmpeg 导出）
        ame_encode_task = TaskDefinition(
            task_id="ame_encode",
            task_type=TaskType.AME_ENCODE,
            name="AME 编码输出",
            func=pipeline_funcs.get("execute_ame_encode"),
            dependencies=["ffmpeg_export"],
            retry_count=1,
            retry_delay_ms=5000,
            skip_on_failure=True,
        )

        feedback_task = TaskDefinition(
            task_id="feedback",
            task_type=TaskType.FEEDBACK,
            name="反馈层 - 结果评估",
            func=pipeline_funcs.get("feedback"),
            dependencies=["ae_execute", "ffmpeg_export"],
            retry_count=0,
        )

        self.add_tasks([
            perception_task,
            understanding_task,
            planning_task,
            ps_preprocess_task,
            silhouette_task,
            ae_compile_task,
            ae_execute_task,
            topaz_task,
            davinci_grade_task,
            runway_task,
            pika_task,
            flux3_task,
            blender_task,
            c4d_mograph_task,
            whisper_subtitle_task,
            ffmpeg_task,
            ffmpeg_export_task,
            ame_encode_task,
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

    # -------------------------------------------------------------------------
    # L1-L5 安全护栏（从孤儿提交 4b8aa81 移植，2026-08-27）：
    # test_l1_l5_guard 依赖 _execute_task_with_guard/_sanitize_args 等。
    # -------------------------------------------------------------------------

    async def _execute_task_with_guard(
        self,
        task_def: TaskDefinition,
        instance: TaskInstance
    ) -> Any:
        """带 L1-L5 护栏的任务执行包装器。

        安全开关关闭(enable_security=False)时完整禁用护栏, 直接走 legacy;
        开关开启时执行 评估 -> 审批 -> 沙箱 -> 审计链, 任一环节失败均抛
        SecurityError(不重试, 见 _run_task)。审计链覆盖成功/拒绝/失败全分支。
        """
        if not self._enable_security:
            return await self._execute_task_legacy(task_def, instance)

        # fail-closed: 开关开启但关键组件缺失(不应发生)禁止静默降级到 legacy。
        if self._risk_assessor is None:
            raise SecurityError("RiskGuard 组件缺失: RiskAssessor 不可用(安全开关已启用)")
        if self._approval_policy is None or self._sandbox_policy is None:
            raise SecurityError("RiskGuard 组件缺失: 审批/沙箱策略不可用(安全开关已启用)")

        task_type_str = (
            task_def.task_type.value
            if hasattr(task_def.task_type, "value")
            else str(task_def.task_type)
        )
        assessment = self._risk_assessor.assess(task_type_str, task_def.args)
        self._logger.info(
            f"风险评估: task_id={task_def.task_id}, risk_level=L{assessment.risk_level.value}, "
            f"requires_sandbox={assessment.requires_sandbox}, requires_approval={assessment.requires_approval}"
        )

        start_time = time.time()
        audit_written = False
        try:
            # L4/L5 审批 — 安全硬约束, 任务级开关不可绕过。
            if assessment.requires_approval:
                request = ApprovalRequest(
                    request_id=str(uuid.uuid4()),
                    task_id=task_def.task_id,
                    task_type=task_type_str,
                    risk_level=assessment.risk_level,
                    reasons=assessment.reasons,
                    args_preview=self._sanitize_args(task_def.args),
                    requested_at=time.time(),
                )
                result = await self._approval_policy.request_approval(request)
                if not result.approved:
                    self._append_audit_entry(
                        task_def, task_type_str, assessment,
                        "approval_denied", "denied", None, None, start_time,
                    )
                    audit_written = True
                    raise SecurityError(
                        f"L{assessment.risk_level.value} 任务被审批拒绝: {result.comment}"
                    )
                if assessment.requires_second_confirm and not result.second_confirmed:
                    self._append_audit_entry(
                        task_def, task_type_str, assessment,
                        "second_confirm_denied", "denied", None, None, start_time,
                    )
                    audit_written = True
                    raise SecurityError("L5 任务需要二次确认")

            # L3+ 沙箱执行。任务显式声明 sandboxed=False 且级别 < L4 时尊重声明。
            if assessment.requires_sandbox:
                if self._sandbox_policy is None:
                    raise SecurityError("沙箱策略缺失(安全开关已启用)")
                if getattr(task_def, "sandboxed", False) is False and assessment.risk_level < RiskLevel.L4_DESTRUCTIVE:
                    self._logger.info(
                        f"任务显式声明 sandboxed=False, 跳过沙箱: {task_def.task_id}"
                    )
                    result = await self._execute_task_legacy(task_def, instance)
                else:
                    result = await self._sandbox_policy.wrap_execution(
                        self._execute_guarded_task_inner,
                        {"task_def": task_def, "instance": instance},
                        assessment,
                    )
            else:
                result = await self._execute_task_legacy(task_def, instance)

            # L4+ 审计哈希链(成功路径)
            if assessment.requires_audit_chain:
                self._append_audit_entry(
                    task_def, task_type_str, assessment,
                    "task_executed", "completed", result, None, start_time,
                )
                audit_written = True

            return result

        except SecurityError as exc:
            # 审批拒绝 / 二次确认拒绝 / 沙箱违规(未写审计时补写 denied)
            if not audit_written and assessment.requires_audit_chain:
                self._append_audit_entry(
                    task_def, task_type_str, assessment,
                    "blocked", "denied", None, exc, start_time,
                )
            raise

        except Exception as exc:
            # 任务函数异常(审计链补写 failed)
            if assessment.requires_audit_chain:
                self._append_audit_entry(
                    task_def, task_type_str, assessment,
                    "task_executed", "failed", None, exc, start_time,
                )
            raise

    def _append_audit_entry(
        self,
        task_def: TaskDefinition,
        task_type_str: str,
        assessment: Any,
        action: str,
        status: str,
        result: Any,
        error: Optional[Exception],
        start_time: Optional[float],
    ) -> None:
        """审计链统一写入辅助(成功 completed / 拒绝 denied / 失败 failed)。

        受任务级开关 enable_audit 控制; 审计写入失败不影响任务结果。
        """
        if self._audit_chain is None:
            return
        if not getattr(task_def, "enable_audit", True):
            return
        duration_ms = (time.time() - start_time) * 1000 if start_time else 0.0
        entry = AuditLogEntry(
            timestamp=time.time(),
            workflow_id=self._context.workflow_id if self._context else "",
            task_id=task_def.task_id,
            task_type=task_type_str,
            security_level=f"L{assessment.risk_level.value}",
            action=action,
            status=status,
            input_hash=SecurityManager.hash_content(str(task_def.args)),
            output_hash=SecurityManager.hash_content(str(result)) if result is not None else "",
            duration_ms=duration_ms,
            details=f"reasons={assessment.reasons}; error={error}" if error else f"reasons={assessment.reasons}",
        )
        try:
            self._audit_chain.append(entry)
        except Exception as exc:
            self._logger.error(f"审计链写入失败: {exc}")

    async def _execute_guarded_task_inner(
        self,
        task_def: TaskDefinition,
        instance: TaskInstance,
        sandbox_dir: Optional[str] = None,
    ) -> Any:
        """沙箱内执行任务，保留依赖结果和 context 注入。

        ``sandbox_dir`` 由 SandboxPolicy.wrap_execution 注入: 仅当任务函数接受时透传。
        """
        if task_def.func is None:
            return None
        args = task_def.args.copy()
        if sandbox_dir:
            try:
                signature = inspect.signature(task_def.func)
                accepts_kwargs = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in signature.parameters.values()
                )
                accepts_sandbox = "sandbox_dir" in signature.parameters
            except (TypeError, ValueError):
                accepts_kwargs = False
                accepts_sandbox = False
            if accepts_kwargs or accepts_sandbox:
                args.setdefault("sandbox_dir", sandbox_dir)
        if self._context is not None:
            for dep_id in task_def.dependencies:
                dep_instance = self._context.tasks.get(dep_id)
                if dep_instance and dep_instance.result is not None:
                    args[f"_{dep_id}_result"] = dep_instance.result
        args["context"] = self._context
        if asyncio.iscoroutinefunction(task_def.func):
            args.pop("context", None)
            return await task_def.func(**args, context=self._context)
        return await asyncio.to_thread(task_def.func, **args)

    @staticmethod
    def _sanitize_args(args: Any) -> Any:
        """递归脱敏嵌套 dict/list/tuple 中的敏感字段为 \"***REDACTED***\"。"""
        if isinstance(args, dict):
            out: Dict[str, Any] = {}
            for key, value in args.items():
                lowered = str(key).lower()
                if any(
                    s in lowered
                    for s in ("key", "token", "password", "secret", "credential", "api_key", "authorization")
                ):
                    out[key] = "***REDACTED***"
                else:
                    out[key] = WorkflowOrchestrator._sanitize_args(value)
            return out
        if isinstance(args, (list, tuple)):
            return [WorkflowOrchestrator._sanitize_args(v) for v in args]
        return args


def _bind_guard_entry() -> None:
    """幂等绑定 guard 入口: 保留原始实现为 _execute_task_legacy，
    现有 _execute_task_func 调用点自动获得护栏。重复执行不会递归绑定。"""
    if not hasattr(WorkflowOrchestrator, "_execute_task_legacy"):
        _legacy = WorkflowOrchestrator._execute_task_func
        WorkflowOrchestrator._execute_task_legacy = _legacy
        WorkflowOrchestrator._execute_task_func = WorkflowOrchestrator._execute_task_with_guard


_bind_guard_entry()


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def create_orchestrator(max_concurrent: int = 5) -> WorkflowOrchestrator:
    """创建工作流编排器"""
    return WorkflowOrchestrator(max_concurrent_tasks=max_concurrent)

# =============================================================================
# 以下 DAG 执行层从孤儿提交 4b8aa81 移植（2026-08-27）：
# test_orchestrator_dag / test_flagship_e2e 依赖 DAGOrchestrator/RunManifest，
# 迁移事故中丢失。与 WorkflowOrchestrator 并存，旗舰管线阶段粒度专用。
# =============================================================================

@dataclass
class StageRecord:
    """单阶段执行记录（写入 manifest.json）"""
    stage_id: str
    status: str = "pending"  # pending / running / passed / failed / skipped
    elapsed_s: float = 0.0
    output_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None
    error_code: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class RunManifest:
    """幂等运行清单（持久化为 manifest.json）"""
    run_id: str
    pipeline_name: str = "flagship_e2e"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    overall_status: str = "pending"  # pending / running / passed / failed / resumed
    stages: Dict[str, StageRecord] = field(default_factory=dict)
    input_config: Dict[str, Any] = field(default_factory=dict)
    total_elapsed_s: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, default=str)

    def save(self, path: "Path") -> "Path":
        from pathlib import Path as _P
        path = _P(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        self.updated_at = time.time()
        return path

    @classmethod
    def load(cls, path: "Path") -> "RunManifest":
        from pathlib import Path as _P
        data = json.loads(_P(path).read_text(encoding="utf-8"))
        stages = {
            k: StageRecord(**v) if isinstance(v, dict) else v
            for k, v in data.get("stages", {}).items()
        }
        data["stages"] = stages
        return cls(**data)


class DAGOrchestrator:
    """旗舰管线 DAG 编排器

    与 WorkflowOrchestrator 的关系：
    - WorkflowOrchestrator 是通用工作流引擎（任务粒度）
    - DAGOrchestrator 是旗舰管线专用（阶段粒度），更轻量、支持 manifest 持久化和 resume

    Usage::

        dag = DAGOrchestrator(run_dir=Path("output/flagship_001"))
        dag.define_stage("S0", func=run_health, deps=[])
        dag.define_stage("S1", func=run_assets, deps=["S0"])
        dag.define_stage("S2", func=run_beat, deps=["S1"])
        dag.define_stage("S3", func=run_ae, deps=["S1"])
        dag.define_stage("S4", func=run_pr, deps=["S2", "S3"])
        manifest = await dag.execute()
    """

    def __init__(
        self,
        run_dir: "Path",
        run_id: Optional[str] = None,
        pipeline_name: str = "flagship_e2e",
        max_retry: int = 1,
    ):
        from pathlib import Path as _P
        self._logger = logging.getLogger(f"{__name__}.DAGOrchestrator")
        self.run_dir = _P(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id or f"run_{uuid.uuid4().hex[:12]}"
        self.pipeline_name = pipeline_name
        self.max_retry = max_retry

        # DAG 定义
        self._stages: Dict[str, Dict[str, Any]] = {}  # stage_id -> {func, deps}
        self._manifest = RunManifest(
            run_id=self.run_id,
            pipeline_name=pipeline_name,
        )
        self._manifest_path = self.run_dir / "manifest.json"

    # ------------------------------------------------------------------
    # DAG 定义 API
    # ------------------------------------------------------------------

    def define_stage(
        self,
        stage_id: str,
        func: Callable,
        deps: Optional[List[str]] = None,
    ) -> None:
        """定义一个阶段及其依赖

        Args:
            stage_id: 阶段 ID（如 "S0", "S1"）
            func: 异步或同步可调用对象，签名 func(stage_id, run_dir, manifest) -> dict
            deps: 前置阶段 ID 列表
        """
        self._stages[stage_id] = {"func": func, "deps": deps or []}
        self._manifest.stages[stage_id] = StageRecord(stage_id=stage_id)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    async def execute(self, resume_from: Optional[str] = None) -> RunManifest:
        """执行 DAG。

        Args:
            resume_from: 从指定阶段恢复执行（之前的阶段保持已有状态）

        Returns:
            RunManifest（已持久化）
        """
        # 尝试加载已有 manifest（幂等）
        if self._manifest_path.exists() and resume_from:
            try:
                self._manifest = RunManifest.load(self._manifest_path)
                self._manifest.overall_status = "resumed"
                self._logger.info(f"[DAG] 从 manifest 恢复: {self._manifest_path}")
            except Exception as e:
                self._logger.warning(f"[DAG] manifest 加载失败，重新开始: {e}")

        self._manifest.overall_status = "running"
        self._manifest.save(self._manifest_path)
        start_time = time.time()

        # 拓扑排序
        order = self._topological_sort()
        self._logger.info(f"[DAG] 执行顺序: {order}")

        # 确定起始点
        start_idx = 0
        if resume_from and resume_from in order:
            start_idx = order.index(resume_from)

        for stage_id in order[start_idx:]:
            stage_info = self._stages[stage_id]
            record = self._manifest.stages[stage_id]

            # 跳过已通过的阶段（resume 场景）
            if record.status == "passed" and stage_id != resume_from:
                self._logger.info(f"[DAG] 跳过已通过阶段: {stage_id}")
                continue

            # 检查依赖是否全部通过
            deps = stage_info["deps"]
            deps_ok = all(
                self._manifest.stages[d].status == "passed"
                for d in deps
                if d in self._manifest.stages
            )
            if not deps_ok:
                record.status = "skipped"
                record.error = "前置依赖未通过"
                self._manifest.save(self._manifest_path)
                continue

            # 执行阶段（带重试）
            await self._execute_stage(stage_id, stage_info["func"])

            # 如果失败且不可恢复，中止整个 DAG
            if record.status == "failed":
                self._manifest.overall_status = "failed"
                self._manifest.total_elapsed_s = time.time() - start_time
                self._manifest.save(self._manifest_path)
                self._logger.error(f"[DAG] 阶段 {stage_id} 失败，管线中止")
                return self._manifest

        # 全部完成
        all_passed = all(
            r.status in ("passed", "skipped")
            for r in self._manifest.stages.values()
        )
        self._manifest.overall_status = "passed" if all_passed else "failed"
        self._manifest.total_elapsed_s = time.time() - start_time
        self._manifest.save(self._manifest_path)
        self._logger.info(
            f"[DAG] 管线完成: {self._manifest.overall_status}, "
            f"耗时 {self._manifest.total_elapsed_s:.1f}s"
        )
        return self._manifest

    async def _execute_stage(self, stage_id: str, func: Callable) -> None:
        """执行单个阶段（带重试）"""
        record = self._manifest.stages[stage_id]
        attempts = 0

        while attempts <= self.max_retry:
            attempts += 1
            record.status = "running"
            record.started_at = time.time()
            self._manifest.save(self._manifest_path)

            try:
                self._logger.info(f"[DAG] 执行阶段 {stage_id} (尝试 {attempts})")
                # 支持同步和异步 func
                import asyncio as _aio
                import inspect
                if inspect.iscoroutinefunction(func):
                    result = await func(stage_id, self.run_dir, self._manifest)
                else:
                    result = await _aio.to_thread(func, stage_id, self.run_dir, self._manifest)

                # 解析结果
                if isinstance(result, dict):
                    record.output_paths = result.get("output_paths", [])
                    if result.get("success") is False:
                        record.status = "failed"
                        record.error = result.get("error", "unknown")
                        record.error_code = result.get("error_code")
                    else:
                        record.status = "passed"
                else:
                    record.status = "passed"

                record.finished_at = time.time()
                record.elapsed_s = record.finished_at - record.started_at
                self._manifest.save(self._manifest_path)

                if record.status == "passed":
                    self._logger.info(
                        f"[DAG] 阶段 {stage_id} 通过 ({record.elapsed_s:.1f}s)"
                    )
                    return

            except Exception as e:
                record.error = str(e)
                record.error_code = "STAGE_EXCEPTION"
                record.status = "failed"
                record.finished_at = time.time()
                record.elapsed_s = record.finished_at - record.started_at
                self._manifest.save(self._manifest_path)
                self._logger.error(f"[DAG] 阶段 {stage_id} 异常: {e}")

            # 重试前等待
            if attempts <= self.max_retry:
                self._logger.info(f"[DAG] 阶段 {stage_id} 重试 ({attempts}/{self.max_retry})")
                await asyncio.sleep(2.0)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _topological_sort(self) -> List[str]:
        """Kahn 拓扑排序"""
        in_degree = {sid: len(info["deps"]) for sid, info in self._stages.items()}
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        result = []

        while queue:
            # 按字母序保证确定性
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            for sid, info in self._stages.items():
                if node in info["deps"]:
                    in_degree[sid] -= 1
                    if in_degree[sid] == 0:
                        queue.append(sid)

        if len(result) != len(self._stages):
            missing = set(self._stages.keys()) - set(result)
            raise ValueError(f"DAG 存在循环依赖: {missing}")

        return result

    @property
    def manifest(self) -> RunManifest:
        return self._manifest


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

def create_orchestrator(max_concurrent: int = 5) -> WorkflowOrchestrator:
    """创建工作流编排器"""
    return WorkflowOrchestrator(max_concurrent_tasks=max_concurrent)


def create_dag_orchestrator(
    run_dir: "Path",
    run_id: Optional[str] = None,
    pipeline_name: str = "flagship_e2e",
) -> DAGOrchestrator:
    """创建旗舰管线 DAG 编排器"""
    return DAGOrchestrator(run_dir=run_dir, run_id=run_id, pipeline_name=pipeline_name)
