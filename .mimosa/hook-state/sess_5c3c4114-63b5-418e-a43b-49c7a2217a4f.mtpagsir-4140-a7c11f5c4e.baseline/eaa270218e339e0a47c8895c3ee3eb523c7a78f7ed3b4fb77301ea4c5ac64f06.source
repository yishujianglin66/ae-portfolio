"""
pipeline/orchestration_interface.py - 工作流编排抽象层 (Prefect 前期铺垫)
======================================================================

本模块为后续接入 Prefect 工作流编排引擎预留抽象接口。
当前阶段: 仅定义接口协议和数据格式，不做实际集成。

======================================================================
后续接入路线图 (Prefect 完整集成)
======================================================================

阶段1: 数据格式对齐 (当前已完成)
  - 定义 StageTask 数据协议，与 Prefect @task 装饰器兼容
  - 定义 FlowResult 数据协议，与 Prefect State 对象可互转
  - 确保现有 StageResult 可无损映射为 Prefect 任务状态

阶段2: 接口适配 (低侵入)
  - 实现 PrefectOrchestrator 类，包装现有 _run_stage() 逻辑
  - 每个管线阶段注册为 Prefect Task (加 @task 装饰器)
  - 依赖关系通过 Prefect 的 DAG 自动推导
  - 预计改动: unified_pipeline.py +50行, 新增本文件 ~200行

阶段3: 调度增强 (中等改动)
  - 替换 run_all() 中的 for 循环为 Prefect Flow 执行
  - 利用 Prefect 的 retry 机制替代手写 max_retries
  - 利用 Prefect 的 cache 机制实现"只重跑失败阶段"
  - 预计改动: unified_pipeline.py run_all() 重写 (~80行)

阶段4: 可观测性 (增值)
  - 启动 Prefect Server (prefect server start)
  - 管线执行自动上报到 http://localhost:4200
  - 可视化 DAG、耗时、失败原因
  - 定时调度: 经验汲取改为 cron 触发
  - 预计改动: 新增配置文件, 不改业务代码

完整集成时需要重构的模块:
  - pipeline/unified_pipeline.py: run_all() → Prefect Flow
  - pipeline/unified_pipeline.py: _run_stage() → @task 包装
  - pipeline/unified_pipeline.py: 错误重试逻辑 → Prefect retry_policy
  - core/experience_harvester.py: _trigger_experience_harvest → 定时调度
  - 新增: pipeline/prefect_flows.py (Flow 定义)
  - 新增: pipeline/prefect_tasks.py (Task 定义)

依赖预检:
  - pip install prefect (纯Python, 无需编译)
  - 最低 Python 3.9+
  - 本地运行无需网络 (prefect server start 即可)
  - 数据存储: 本地 SQLite (默认)
======================================================================
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
#  数据协议: 与 Prefect State 兼容的任务状态
# ============================================================================

class TaskState(Enum):
    """任务状态 (对齐 Prefect State 枚举)"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRYING = "RETRYING"
    CACHED = "CACHED"


@dataclass
class StageTask:
    """阶段任务定义 (对齐 Prefect @task 参数)
    
    后续集成时，每个 StageTask 实例将被包装为:
        @task(name=task.name, retries=task.max_retries, ...)
        def wrapped_task():
            return task.run_fn(context)
    """
    name: str                           # 任务名 (perceive/analyze/plan/...)
    run_fn: Optional[Callable] = None   # 实际执行函数
    dependencies: List[str] = field(default_factory=list)  # 依赖的前置任务名
    max_retries: int = 1                # 最大重试次数
    retry_delay_sec: float = 2.0        # 重试间隔
    timeout_sec: float = 300.0          # 超时时间
    cache_key: str = ""                 # 缓存键(用于跳过已完成任务)
    tags: List[str] = field(default_factory=list)  # 标签(用于分组/过滤)


@dataclass
class FlowDefinition:
    """工作流定义 (对齐 Prefect @flow)
    
    后续集成时，整个管线将被定义为:
        @flow(name=flow.name, retries=flow.max_retries)
        def pipeline_flow():
            # 按 DAG 顺序执行 tasks
    """
    name: str = "video_pipeline"
    tasks: List[StageTask] = field(default_factory=list)
    max_retries: int = 0
    description: str = "AE-Knowledge-Vault 视频创作管线"
    
    def get_execution_order(self) -> List[List[str]]:
        """拓扑排序: 返回分层执行顺序(同层可并行)"""
        resolved = set()
        layers = []
        remaining = {t.name: t for t in self.tasks}
        
        while remaining:
            # 找出所有依赖已满足的任务
            ready = [
                name for name, task in remaining.items()
                if all(dep in resolved for dep in task.dependencies)
            ]
            if not ready:
                # 循环依赖，强制打破
                ready = list(remaining.keys())[:1]
            layers.append(ready)
            for name in ready:
                resolved.add(name)
                del remaining[name]
        
        return layers


@dataclass
class TaskResult:
    """任务执行结果 (对齐 Prefect State + 业务数据)"""
    task_name: str = ""
    state: TaskState = TaskState.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    attempts: int = 0
    cached: bool = False

    @property
    def duration_sec(self) -> float:
        return self.end_time - self.start_time if self.end_time > 0 else 0.0


# ============================================================================
#  抽象编排器接口
# ============================================================================

class OrchestrationBackend(ABC):
    """编排后端抽象接口
    
    当前实现: SimpleOrchestrator (顺序执行，无外部依赖)
    未来实现: PrefectOrchestrator (Prefect Flow 执行)
    """

    @abstractmethod
    def execute_flow(self, flow: FlowDefinition, context: Dict[str, Any]) -> Dict[str, TaskResult]:
        """执行整个工作流"""
        ...

    @abstractmethod
    def get_backend_name(self) -> str:
        """返回后端名称"""
        ...


class SimpleOrchestrator(OrchestrationBackend):
    """简单顺序编排器 (当前默认，无外部依赖)
    
    行为与现有 unified_pipeline.py 的 run_all() 一致:
    - 按阶段顺序执行
    - 失败时重试
    - 关键阶段失败则中断
    """

    def __init__(self, critical_stages: List[str] = None):
        self._critical = set(critical_stages or ["execute", "render"])

    def get_backend_name(self) -> str:
        return "simple_sequential"

    def execute_flow(
        self, flow: FlowDefinition, context: Dict[str, Any]
    ) -> Dict[str, TaskResult]:
        """按拓扑顺序执行所有任务"""
        results: Dict[str, TaskResult] = {}
        layers = flow.get_execution_order()

        for layer in layers:
            for task_name in layer:
                task = next((t for t in flow.tasks if t.name == task_name), None)
                if not task or not task.run_fn:
                    results[task_name] = TaskResult(
                        task_name=task_name, state=TaskState.SKIPPED
                    )
                    continue

                result = self._execute_task(task, context, results)
                results[task_name] = result

                # 关键阶段失败 → 中断
                if (result.state == TaskState.FAILED and
                    task_name in self._critical):
                    logger.warning(f"[Orchestrator] Critical task failed: {task_name}")
                    return results

        return results

    def _execute_task(
        self, task: StageTask, context: Dict[str, Any],
        prev_results: Dict[str, TaskResult]
    ) -> TaskResult:
        """执行单个任务(带重试)"""
        result = TaskResult(task_name=task.name)
        
        for attempt in range(1, task.max_retries + 1):
            result.attempts = attempt
            result.start_time = time.time()
            try:
                data = task.run_fn(context)
                result.end_time = time.time()
                result.state = TaskState.COMPLETED
                result.data = data if isinstance(data, dict) else {"result": data}
                return result
            except Exception as e:
                result.end_time = time.time()
                result.error = str(e)
                if attempt < task.max_retries:
                    result.state = TaskState.RETRYING
                    time.sleep(task.retry_delay_sec)
                else:
                    result.state = TaskState.FAILED

        return result


# ============================================================================
#  工厂函数: 获取当前可用的编排后端
# ============================================================================

def get_orchestrator(backend: str = "auto") -> OrchestrationBackend:
    """获取编排后端实例
    
    Args:
        backend: "auto"(自动选择) / "simple"(强制简单) / "prefect"(强制Prefect)
    
    当前: 始终返回 SimpleOrchestrator
    未来: 当 backend="prefect" 且 prefect 已安装时，返回 PrefectOrchestrator
    """
    if backend == "prefect":
        try:
            import prefect  # noqa: F401
            # TODO: 阶段2实现 PrefectOrchestrator
            logger.info("[Orchestrator] Prefect detected but not yet integrated, using simple")
        except ImportError:
            logger.debug("[Orchestrator] Prefect not installed, using simple")
    
    return SimpleOrchestrator()


# ============================================================================
#  工具函数: 现有管线 → FlowDefinition 转换
# ============================================================================

def pipeline_stages_to_flow(
    stage_fns: Dict[str, Callable],
    skip_stages: List[str] = None,
) -> FlowDefinition:
    """将现有管线的阶段函数转换为 FlowDefinition
    
    用于后续 Prefect 集成时的数据格式对齐。
    
    Args:
        stage_fns: {"perceive": fn, "analyze": fn, ...}
        skip_stages: 需要跳过的阶段
    """
    skip = set(skip_stages or [])
    
    # 定义标准依赖关系
    dependencies = {
        "perceive": [],
        "analyze": ["perceive"],
        "plan": ["analyze"],
        "execute": ["plan"],
        "render": ["execute"],
        "verify": ["render"],
        "learn": ["verify"],
    }
    
    # 重试策略
    retries = {"execute": 2, "render": 2}
    
    tasks = []
    for name, fn in stage_fns.items():
        if name in skip:
            continue
        tasks.append(StageTask(
            name=name,
            run_fn=fn,
            dependencies=dependencies.get(name, []),
            max_retries=retries.get(name, 1),
            tags=["pipeline_stage"],
        ))
    
    return FlowDefinition(
        name="video_pipeline_v2",
        tasks=tasks,
        description="AE-Knowledge-Vault 端到端视频创作管线",
    )


# ============================================================================
#  P2.2: PipelineCoordinator - UnifiedPipeline 与 PipelineOrchestrator 协作模式
# ============================================================================
# 不合并两条管线 (会破坏现有测试)，而是建立协作模式:
# - UnifiedPipeline: 端到端视频创作主流水线 (perceive→...→learn)
# - WorkflowOrchestrator: 通用工作流编排引擎 (任务依赖、并行、重试)
# - PipelineCoordinator: 根据任务特性选择管线，并合并结果

class PipelineCoordinator:
    """管线协作协调器
    
    协调 UnifiedPipeline (端到端视频创作) 与 WorkflowOrchestrator (通用工作流)
    两条管线，根据任务类型自动选择最优管线，并合并结果。
    
    设计原则:
    1. 不修改任一管线的内部实现，仅作为协调者
    2. 基于任务类型 (task_spec) 路由: 端到端 → unified, 多任务 DAG → orchestrator
    3. hybrid 模式: orchestrator 调用 unified 作为子任务执行器
    4. 失败安全: 任一管线异常都不影响另一个
    
    用法:
        coordinator = PipelineCoordinator()
        choice = coordinator.select_pipeline(task_spec)
        if choice == "hybrid":
            result = coordinator.coordinate(unified_pipeline, orchestrator, task_spec)
    """
    
    # 任务类型 → 推荐管线的映射规则
    ROUTING_RULES = {
        # 端到端视频创作类任务 → unified
        "video_creation": "unified",
        "vrs_replicate": "unified",
        "style_transfer": "unified",
        # 通用工作流类任务 → orchestrator
        "multi_task_dag": "orchestrator",
        "parallel_render": "orchestrator",
        "batch_processing": "orchestrator",
        # 复杂任务 → hybrid (orchestrator 调度，unified 作为子任务)
        "complex_pipeline": "hybrid",
        "adaptive_workflow": "hybrid",
    }
    
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.PipelineCoordinator")
    
    def select_pipeline(self, task_spec: Dict[str, Any]) -> str:
        """基于任务类型选择管线
        
        决策逻辑:
        1. 若 task_spec 显式指定 "pipeline" 字段，直接使用
        2. 否则按 task_type 查 ROUTING_RULES
        3. 未匹配的任务类型默认 "unified" (端到端视频创作是主场景)
        
        Args:
            task_spec: 任务规格字典，至少包含 "task_type" 字段
                       可选字段: "pipeline" (覆盖自动选择)
        
        Returns:
            "unified" / "orchestrator" / "hybrid"
        """
        # 1. 显式指定优先
        explicit = task_spec.get("pipeline")
        if explicit in ("unified", "orchestrator", "hybrid"):
            return explicit
        
        # 2. 按 task_type 路由
        task_type = task_spec.get("task_type", "")
        choice = self.ROUTING_RULES.get(task_type)
        if choice:
            self._logger.debug(
                "[Coordinator] Routed task_type='%s' -> %s", task_type, choice
            )
            return choice
        
        # 3. 启发式: 任务含 subtasks 字段 → hybrid
        if "subtasks" in task_spec and len(task_spec["subtasks"]) > 1:
            return "hybrid"
        
        # 4. 默认 unified
        return "unified"
    
    def coordinate(
        self,
        unified_pipeline: Any,
        orchestrator: Any,
        task_spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """协调两条管线执行任务 (hybrid 模式)
        
        流程:
        1. orchestrator 解析 task_spec，将 unified_pipeline.run_all 作为子任务
        2. orchestrator 按依赖调度子任务
        3. 合并 unified 和 orchestrator 的执行结果
        
        Args:
            unified_pipeline: UnifiedPipeline 实例 (需有 run_all() 方法)
            orchestrator: WorkflowOrchestrator 实例 (需有 run() 方法)
            task_spec: 任务规格
        
        Returns:
            合并后的结果字典，包含:
            - "unified_result": unified 管线输出
            - "orchestrator_result": orchestrator 管线输出
            - "merged": 合并后的最终数据
            - "pipeline_choice": 选择的管线模式
        """
        self._logger.info(
            "[Coordinator] Coordinating hybrid pipeline for task_type=%s",
            task_spec.get("task_type", "unknown"),
        )
        
        unified_result: Dict[str, Any] = {}
        orchestrator_result: Dict[str, Any] = {}
        
        # 1. 执行 unified (端到端创作)
        if unified_pipeline is not None:
            try:
                if hasattr(unified_pipeline, "run_all"):
                    unified_result = unified_pipeline.run_all()
                    if hasattr(unified_result, "to_dict"):
                        unified_result = unified_result.to_dict()
                else:
                    unified_result = {"error": "unified_pipeline has no run_all()"}
            except Exception as e:
                self._logger.warning("[Coordinator] Unified pipeline failed: %s", e)
                unified_result = {"error": str(e), "status": "failed"}
        
        # 2. 执行 orchestrator (调度子任务)
        if orchestrator is not None:
            try:
                # orchestrator.run() 是异步的，使用 asyncio 驱动
                import asyncio
                if hasattr(orchestrator, "run"):
                    coro = orchestrator.run(
                        workflow_id=task_spec.get("workflow_id", "hybrid"),
                        initial_data=task_spec.get("initial_data", {}),
                    )
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 已在异步上下文，无法直接 run_until_complete
                            orchestrator_result = {"status": "skipped", "reason": "event loop running"}
                        else:
                            ctx = loop.run_until_complete(coro)
                            orchestrator_result = self._context_to_dict(ctx)
                    except RuntimeError:
                        ctx = asyncio.run(coro)
                        orchestrator_result = self._context_to_dict(ctx)
                else:
                    orchestrator_result = {"error": "orchestrator has no run()"}
            except Exception as e:
                self._logger.warning("[Coordinator] Orchestrator failed: %s", e)
                orchestrator_result = {"error": str(e), "status": "failed"}
        
        # 3. 合并结果
        merged = self.merge_results(unified_result, orchestrator_result)
        merged["pipeline_choice"] = "hybrid"
        return merged
    
    def merge_results(
        self,
        unified_result: Dict[str, Any],
        orchestrator_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """合并两条管线的结果
        
        策略:
        - unified 的 output_path 优先 (主输出)
        - orchestrator 的 workflow_id / task_stats 保留 (调度元数据)
        - errors 字段合并
        - 其他字段: orchestrator 覆盖 unified (orchestrator 是协调者视角)
        
        Args:
            unified_result: unified 管线输出字典
            orchestrator_result: orchestrator 管线输出字典
        
        Returns:
            合并后的结果字典
        """
        merged: Dict[str, Any] = {}
        
        # 1. 先放 unified 的核心输出字段
        if isinstance(unified_result, dict):
            for key in ("run_id", "output_path", "project_path", "quality_score",
                       "mode", "iterations", "vrs_analysis", "kb_context"):
                if key in unified_result:
                    merged[key] = unified_result[key]
        
        # 2. orchestrator 的调度元数据 (不覆盖核心输出)
        if isinstance(orchestrator_result, dict):
            for key in ("workflow_id", "task_stats", "progress", "duration_seconds"):
                if key in orchestrator_result:
                    merged[f"orchestrator_{key}"] = orchestrator_result[key]
        
        # 3. 合并 errors
        errors = []
        if isinstance(unified_result, dict):
            errors.extend(unified_result.get("errors", []))
            if "error" in unified_result:
                errors.append(f"unified: {unified_result['error']}")
        if isinstance(orchestrator_result, dict):
            if "error" in orchestrator_result:
                errors.append(f"orchestrator: {orchestrator_result['error']}")
        if errors:
            merged["errors"] = errors
        
        # 4. status: 任一成功则 partial，全成功则 success
        u_status = unified_result.get("status") if isinstance(unified_result, dict) else None
        o_status = orchestrator_result.get("status") if isinstance(orchestrator_result, dict) else None
        if u_status == "success" and o_status in ("COMPLETED", "success"):
            merged["status"] = "success"
        elif u_status == "success" or o_status in ("COMPLETED", "success"):
            merged["status"] = "partial"
        else:
            merged["status"] = "failed"
        
        merged["unified_result"] = unified_result if isinstance(unified_result, dict) else {}
        merged["orchestrator_result"] = orchestrator_result if isinstance(orchestrator_result, dict) else {}
        return merged
    
    def _context_to_dict(self, ctx: Any) -> Dict[str, Any]:
        """将 WorkflowContext 转为 dict (容错)"""
        if ctx is None:
            return {}
        try:
            if hasattr(ctx, "__dict__"):
                return {
                    "workflow_id": getattr(ctx, "workflow_id", ""),
                    "status": str(getattr(ctx, "status", "")),
                    "progress": getattr(ctx, "progress", 0.0),
                    "data": dict(getattr(ctx, "data", {}) or {}),
                }
        except Exception as e:
            self._logger.debug("[Coordinator] context_to_dict failed: %s", e)
        return {"status": str(ctx)}


# ============================================================================
#  全局 PipelineCoordinator 单例
# ============================================================================

_global_coordinator: Optional[PipelineCoordinator] = None


def get_pipeline_coordinator() -> PipelineCoordinator:
    """获取全局 PipelineCoordinator 单例
    
    Returns:
        PipelineCoordinator 实例
    """
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = PipelineCoordinator()
    return _global_coordinator
