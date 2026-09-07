"""
pipeline/multi_thread_executor.py - 多线程全阶段执行器 v1.0
============================================================

基于 DAG（有向无环图）的多线程管线调度器。
自动识别阶段间依赖关系，将无依赖阶段并行执行，最大化吞吐量。

架构:
    StageDAG          → 定义阶段依赖 + 拓扑排序
    StageWorker       → 单阶段工作线程（线程安全）
    MultiThreadExecutor → 多线程调度器（核心）
    PipelineMonitor   → 实时进度监控

用法:
    from pipeline.multi_thread_executor import MultiThreadExecutor

    executor = MultiThreadExecutor(max_workers=4)
    executor.add_stage("perceive", perceive_fn)
    executor.add_stage("analyze", analyze_fn)
    executor.add_stage("plan", plan_fn, deps=["perceive", "analyze"])
    executor.add_stage("execute", execute_fn, deps=["plan"])
    result = executor.run_all()

Author: AE-Knowledge-Vault Team
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, Future, as_completed, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  数据类型
# ============================================================================

class StageState(Enum):
    """阶段状态"""
    PENDING = "pending"
    QUEUED = "queued"       # 已入队等待执行
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"     # 依赖失败导致跳过


@dataclass
class StageDefinition:
    """阶段定义"""
    name: str
    handler: Callable[..., Dict[str, Any]]
    deps: List[str] = field(default_factory=list)
    timeout: float = 300.0          # 超时秒数
    max_retries: int = 1            # 最大重试次数
    priority: int = 0               # 优先级（高优先先调度）
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageExecution:
    """阶段执行状态（线程安全）"""
    definition: StageDefinition
    state: StageState = StageState.PENDING
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    attempt: int = 0
    thread_name: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def duration_sec(self) -> float:
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 2)
        return 0.0

    def set_running(self, thread_name: str):
        with self._lock:
            self.state = StageState.RUNNING
            self.start_time = time.time()
            self.thread_name = thread_name
            self.attempt += 1

    def set_done(self, result: Dict[str, Any]):
        with self._lock:
            self.state = StageState.DONE
            self.result = result
            self.end_time = time.time()

    def set_failed(self, error: str):
        with self._lock:
            self.state = StageState.FAILED
            self.error = error
            self.end_time = time.time()

    def set_skipped(self, reason: str):
        with self._lock:
            self.state = StageState.SKIPPED
            self.error = reason
            self.end_time = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.definition.name,
            "state": self.state.value,
            "deps": self.definition.deps,
            "duration_sec": self.duration_sec,
            "attempt": self.attempt,
            "thread": self.thread_name,
            "error": self.error,
        }


# ============================================================================
#  DAG 拓扑排序
# ============================================================================

class StageDAG:
    """阶段 DAG — 管理依赖关系 + 拓扑排序"""

    def __init__(self):
        self._stages: Dict[str, StageDefinition] = {}
        self._reverse_deps: Dict[str, List[str]] = defaultdict(list)

    def add_stage(self, stage: StageDefinition):
        """添加阶段"""
        if stage.name in self._stages:
            raise ValueError(f"Duplicate stage: {stage.name}")
        # 验证依赖存在
        for dep in stage.deps:
            if dep not in self._stages:
                # 延迟检查：先记录，run 时再验证
                pass
        self._stages[stage.name] = stage
        for dep in stage.deps:
            self._reverse_deps[dep].append(stage.name)

    def validate(self):
        """验证 DAG 完整性"""
        for name, stage in self._stages.items():
            for dep in stage.deps:
                if dep not in self._stages:
                    raise ValueError(f"Stage '{name}' depends on unknown stage '{dep}'")
        # 检测循环依赖
        visited = set()
        rec_stack = set()

        def _dfs(node):
            visited.add(node)
            rec_stack.add(node)
            for child in self._reverse_deps.get(node, []):
                if child not in visited:
                    if _dfs(child):
                        return True
                elif child in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for node in self._stages:
            if node not in visited:
                if _dfs(node):
                    raise ValueError("Circular dependency detected in stage DAG")

    def get_ready_stages(self, completed: Set[str], running: Set[str]) -> List[str]:
        """获取所有依赖已完成的待执行阶段"""
        ready = []
        for name, stage in self._stages.items():
            if name in completed or name in running:
                continue
            if all(dep in completed for dep in stage.deps):
                ready.append(name)
        # 按优先级排序
        ready.sort(key=lambda n: -self._stages[n].priority)
        return ready

    def get_all_names(self) -> List[str]:
        return list(self._stages.keys())

    def get_stage(self, name: str) -> StageDefinition:
        return self._stages[name]

    @property
    def stage_count(self) -> int:
        return len(self._stages)


# ============================================================================
#  进度监控
# ============================================================================

class PipelineMonitor:
    """管线进度监控器"""

    def __init__(self, total_stages: int):
        self.total_stages = total_stages
        self.completed_stages = 0
        self.failed_stages = 0
        self.skipped_stages = 0
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._events: List[Dict[str, Any]] = []
        self._callbacks: List[Callable] = []

    def on_stage_start(self, name: str, thread: str):
        event = {
            "time": time.time(),
            "event": "start",
            "stage": name,
            "thread": thread,
        }
        with self._lock:
            self._events.append(event)
        self._notify(event)
        logger.info(f"[MONITOR] Stage [{name}] started on {thread}")

    def on_stage_done(self, name: str, duration: float):
        event = {
            "time": time.time(),
            "event": "done",
            "stage": name,
            "duration": duration,
        }
        with self._lock:
            self._events.append(event)
            self.completed_stages += 1
        self._notify(event)
        logger.info(f"[MONITOR] Stage [{name}] done ({duration:.1f}s)")

    def on_stage_failed(self, name: str, error: str):
        event = {
            "time": time.time(),
            "event": "failed",
            "stage": name,
            "error": error,
        }
        with self._lock:
            self._events.append(event)
            self.failed_stages += 1
        self._notify(event)
        logger.error(f"[MONITOR] Stage [{name}] failed: {error}")

    def on_stage_skipped(self, name: str, reason: str):
        event = {
            "time": time.time(),
            "event": "skipped",
            "stage": name,
            "reason": reason,
        }
        with self._lock:
            self._events.append(event)
            self.skipped_stages += 1
        self._notify(event)

    def add_callback(self, cb: Callable):
        """添加进度回调 cb(event_dict)"""
        self._callbacks.append(cb)

    def _notify(self, event: Dict):
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            elapsed = time.time() - self.start_time
            return {
                "total": self.total_stages,
                "completed": self.completed_stages,
                "failed": self.failed_stages,
                "skipped": self.skipped_stages,
                "pending": self.total_stages - self.completed_stages - self.failed_stages - self.skipped_stages,
                "elapsed_sec": round(elapsed, 1),
                "progress_pct": round(
                    (self.completed_stages + self.failed_stages + self.skipped_stages)
                    / max(self.total_stages, 1) * 100, 1
                ),
                "events": list(self._events),
            }


# ============================================================================
#  多线程执行器
# ============================================================================

@dataclass
class ExecutionResult:
    """执行结果"""
    run_id: str
    success: bool
    stages: Dict[str, StageExecution] = field(default_factory=dict)
    total_duration_sec: float = 0.0
    errors: List[str] = field(default_factory=list)
    monitor_status: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "success": self.success,
            "total_duration_sec": self.total_duration_sec,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "errors": self.errors,
            "monitor": self.monitor_status,
        }


class MultiThreadExecutor:
    """多线程全阶段执行器

    基于 DAG 依赖自动调度：
    - 无依赖阶段自动并行
    - 有依赖阶段等待前置完成
    - 失败阶段自动跳过下游
    - 支持超时 + 重试
    """

    def __init__(
        self,
        max_workers: int = 4,
        default_timeout: float = 300.0,
        enable_monitor: bool = True,
    ):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.dag = StageDAG()
        self._executions: Dict[str, StageExecution] = {}
        self._monitor: Optional[PipelineMonitor] = None
        self._shared_context: Dict[str, Any] = {}
        self._context_lock = threading.Lock()
        self._completed: Set[str] = set()
        self._failed: Set[str] = set()
        self._running: Set[str] = set()
        self._all_done = threading.Event()

    def add_stage(
        self,
        name: str,
        handler: Callable[..., Dict[str, Any]],
        deps: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        max_retries: int = 1,
        priority: int = 0,
        **metadata,
    ) -> "MultiThreadExecutor":
        """添加阶段（链式调用）"""
        stage = StageDefinition(
            name=name,
            handler=handler,
            deps=deps or [],
            timeout=timeout or self.default_timeout,
            max_retries=max_retries,
            priority=priority,
            metadata=metadata,
        )
        self.dag.add_stage(stage)
        self._executions[name] = StageExecution(definition=stage)
        return self

    def set_context(self, key: str, value: Any):
        """设置共享上下文（线程安全）"""
        with self._context_lock:
            self._shared_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取共享上下文（线程安全）"""
        with self._context_lock:
            return self._shared_context.get(key, default)

    def add_monitor_callback(self, cb: Callable):
        """添加进度回调"""
        if self._monitor:
            self._monitor.add_callback(cb)

    def run_all(self) -> ExecutionResult:
        """执行所有阶段（多线程并行）"""
        run_id = f"mt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        start = time.time()

        # 验证 DAG
        self.dag.validate()
        total = self.dag.stage_count

        # 初始化监控
        self._monitor = PipelineMonitor(total_stages=total)

        logger.info(f"[EXECUTOR] Starting run {run_id} with {total} stages, "
                    f"max_workers={self.max_workers}")
        print(f"\n{'='*60}")
        print(f"  Multi-Thread Pipeline Executor v1.0")
        print(f"  Run ID: {run_id}")
        print(f"  Stages: {total} | Workers: {self.max_workers}")
        print(f"{'='*60}\n")

        # 重置状态
        self._completed.clear()
        self._failed.clear()
        self._running.clear()
        self._all_done.clear()

        # 主调度循环
        with ThreadPoolExecutor(max_workers=self.max_workers,
                                thread_name_prefix="Stage") as pool:
            futures: Dict[Future, str] = {}

            while True:
                # 检查完成条件
                all_finished = (
                    len(self._completed) + len(self._failed) +
                    len(self._get_skipped()) >= total
                )
                if all_finished:
                    break

                # 获取可调度阶段
                ready = self.dag.get_ready_stages(
                    self._completed | self._get_skipped(),
                    self._running,
                )

                # 检查是否有阶段因依赖失败需要跳过
                newly_skipped = self._check_skip_conditions()
                if newly_skipped:
                    continue

                if not ready and not futures:
                    # 没有可调度阶段且没有运行中的 → 死锁或完成
                    break

                # 调度就绪阶段
                for stage_name in ready:
                    if stage_name in self._running:
                        continue
                    self._running.add(stage_name)
                    execution = self._executions[stage_name]

                    future = pool.submit(self._execute_stage, stage_name, execution)
                    futures[future] = stage_name

                # 等待任意一个完成
                done_futures = []
                for f, name in futures.items():
                    if f.done():
                        done_futures.append(f)

                if done_futures:
                    for f in done_futures:
                        name = futures.pop(f)
                        self._running.discard(name)
                        try:
                            success = f.result()
                            if success:
                                self._completed.add(name)
                            else:
                                self._failed.add(name)
                        except Exception as e:
                            logger.error(f"[EXECUTOR] Stage [{name}] thread error: {e}")
                            self._failed.add(name)
                else:
                    # 短暂等待避免忙循环
                    time.sleep(0.05)

            # 等待剩余运行中的 future
            for f in futures:
                name = futures[f]
                try:
                    f.result(timeout=10)
                except Exception:
                    pass

        total_dur = time.time() - start
        monitor_status = self._monitor.get_status() if self._monitor else {}
        success = len(self._failed) == 0

        result = ExecutionResult(
            run_id=run_id,
            success=success,
            stages=dict(self._executions),
            total_duration_sec=round(total_dur, 2),
            errors=[
                f"Stage [{e.definition.name}] failed: {e.error}"
                for e in self._executions.values()
                if e.state == StageState.FAILED
            ],
            monitor_status=monitor_status,
        )

        # 打印汇总
        self._print_summary(result)
        return result

    def _execute_stage(self, name: str, execution: StageExecution) -> bool:
        """执行单个阶段（在线程池中运行）"""
        thread_name = threading.current_thread().name
        execution.set_running(thread_name)

        if self._monitor:
            self._monitor.on_stage_start(name, thread_name)

        stage_def = execution.definition
        max_attempts = stage_def.max_retries
        stage_timeout = stage_def.timeout

        for attempt in range(1, max_attempts + 1):
            try:
                # 执行阶段处理器（支持超时控制）
                context = dict(self._shared_context)
                if stage_timeout and stage_timeout > 0:
                    # 通过子线程池 + future.result(timeout=) 实现超时控制
                    sub_pool = ThreadPoolExecutor(max_workers=1)
                    future = sub_pool.submit(stage_def.handler, context)
                    try:
                        result = future.result(timeout=stage_timeout)
                    except FuturesTimeoutError:
                        sub_pool.shutdown(wait=False)
                        raise TimeoutError(
                            f"Stage [{name}] timed out after {stage_timeout}s"
                        )
                    sub_pool.shutdown(wait=False)
                else:
                    result = stage_def.handler(context)

                # 检查结果 success 标志：success=False 视为阶段失败
                if isinstance(result, dict) and not result.get("success", True):
                    err_msg = (
                        result.get("error")
                        or result.get("message")
                        or "stage reported failure"
                    )
                    execution.set_failed(str(err_msg))
                    if self._monitor:
                        self._monitor.on_stage_failed(name, str(err_msg))
                    return False

                execution.set_done(result or {})
                dur = execution.duration_sec

                if self._monitor:
                    self._monitor.on_stage_done(name, dur)

                logger.info(f"[EXECUTOR] Stage [{name}] done ({dur:.1f}s)")
                return True

            except Exception as e:
                logger.warning(f"[EXECUTOR] Stage [{name}] attempt {attempt} failed: {e}")
                if attempt >= max_attempts:
                    execution.set_failed(str(e))
                    if self._monitor:
                        self._monitor.on_stage_failed(name, str(e))
                    return False
                time.sleep(0.5)

        return False

    def _check_skip_conditions(self) -> List[str]:
        """检查并标记需要跳过的阶段（依赖失败）"""
        skipped = []
        for name, execution in self._executions.items():
            if execution.state != StageState.PENDING:
                continue
            # 检查是否有依赖失败
            for dep in execution.definition.deps:
                dep_exec = self._executions.get(dep)
                if dep_exec and dep_exec.state == StageState.FAILED:
                    reason = f"Dependency '{dep}' failed"
                    execution.set_skipped(reason)
                    if self._monitor:
                        self._monitor.on_stage_skipped(name, reason)
                    skipped.append(name)
                    logger.info(f"[EXECUTOR] Stage [{name}] skipped: {reason}")
                    break
        return skipped

    def _get_skipped(self) -> Set[str]:
        return {n for n, e in self._executions.items() if e.state == StageState.SKIPPED}

    def _print_summary(self, result: ExecutionResult):
        """打印执行汇总"""
        print(f"\n{'='*60}")
        print(f"  EXECUTION COMPLETE: {'SUCCESS' if result.success else 'PARTIAL'}")
        print(f"  Run ID: {result.run_id}")
        print(f"  Duration: {result.total_duration_sec:.1f}s")
        print(f"{'='*60}")

        for name, execution in result.stages.items():
            state = execution.state.value
            dur = f"{execution.duration_sec:.1f}s" if execution.duration_sec > 0 else "-"
            thread = execution.thread_name or "-"
            icon = {"done": "[OK]", "failed": "[FAIL]", "skipped": "[SKIP]",
                    "running": "[...]", "pending": "[--]"}.get(state, "[??]")
            print(f"  {icon:6s} {name:20s} | {state:8s} | {dur:>8s} | {thread}")

        if result.errors:
            print(f"\n  Errors:")
            for err in result.errors:
                print(f"    - {err}")
        print()


# ============================================================================
#  便捷工厂：构建标准管线 DAG
# ============================================================================

def create_video_pipeline_executor(
    pipeline_instance,
    video_path: str,
    output_dir: str,
    max_workers: int = 4,
    **kwargs,
) -> MultiThreadExecutor:
    """创建标准视频处理管线的多线程执行器

    将 UnifiedVideoPipeline 的方法映射到 DAG 阶段：

    DAG:
        perceive ──┐
                    ├──→ plan ──→ execute ──→ render ──→ verify
        analyze  ──┘

    阶段映射:
        perceive → scene_detect
        analyze  → auto_analyze + smart_grade_params
        plan     → 生成调色预设映射
        execute  → resolve_grade (专业调色)
        render   → frame_interpolate (补帧)
        verify   → 输出验证

    Args:
        pipeline_instance: UnifiedVideoPipeline 实例
        video_path: 输入视频路径
        output_dir: 输出目录
        max_workers: 最大线程数

    Returns:
        配置好的 MultiThreadExecutor
    """
    executor = MultiThreadExecutor(max_workers=max_workers)

    # 共享上下文
    executor.set_context("video_path", video_path)
    executor.set_context("output_dir", output_dir)

    # --- perceive: 场景检测 ---
    def _perceive(ctx):
        scenes = pipeline_instance.detect_scenes(video_path)
        executor.set_context("scenes", scenes)
        return {"scenes": len(scenes), "data": scenes}

    # --- analyze: 视频分析 + 智能调色参数 ---
    def _analyze(ctx):
        analysis = pipeline_instance.auto_analyze(video_path)
        smart = pipeline_instance.smart_grade_params(video_path)
        executor.set_context("analysis", analysis)
        executor.set_context("smart_params", smart)
        return {"analysis": analysis, "smart_params": smart}

    # --- plan: 生成调色预设映射 ---
    def _plan(ctx):
        scenes = executor.get_context("scenes", [])
        smart = executor.get_context("smart_params", {})
        from integrations.davinci_fuscript import DCTL_PRESET_MAP

        segment_presets = None
        if scenes:
            preset_cycle = list(DCTL_PRESET_MAP.keys())[:6]
            segment_presets = {}
            for i in range(min(len(scenes), len(preset_cycle))):
                segment_presets[f"scene_{i}"] = preset_cycle[i % len(preset_cycle)]

        resolve_preset = smart.get("preset", "cinematic")
        executor.set_context("segment_presets", segment_presets)
        executor.set_context("resolve_preset", resolve_preset)
        return {"segment_presets": segment_presets, "resolve_preset": resolve_preset}

    # --- execute: Resolve 专业调色 ---
    def _execute(ctx):
        smart = executor.get_context("smart_params", {})
        segment_presets = executor.get_context("segment_presets")
        resolve_preset = executor.get_context("resolve_preset", "cinematic")

        result = pipeline_instance.resolve_grade(
            video_path=video_path,
            output_dir=output_dir,
            preset=resolve_preset,
            segment_presets=segment_presets,
            brightness=smart.get("brightness", 1.05),
            contrast=smart.get("contrast", 1.1),
            saturation=smart.get("saturation", 1.05),
            close_after=True,
        )
        executor.set_context("grade_result", result)
        return result

    # --- render: 补帧 ---
    def _render(ctx):
        grade_result = executor.get_context("grade_result", {})
        interp_input = grade_result.get("output_path", "") or video_path
        interp_output = str(Path(output_dir) / f"{Path(interp_input).stem}_60fps.mp4")

        result = pipeline_instance.frame_interpolate(
            interp_input, interp_output,
            target_fps=60.0, method="mvscale",
        )
        executor.set_context("interp_output", result)
        return {"output": result, "target_fps": 60}

    # --- verify: 输出验证 ---
    def _verify(ctx):
        interp_output = executor.get_context("interp_output", "")
        grade_result = executor.get_context("grade_result", {})

        checks = {
            "grade_success": grade_result.get("success", False),
            "grade_clips": grade_result.get("clips_graded", 0),
            "interp_exists": bool(interp_output and Path(interp_output).exists()),
        }
        if interp_output and Path(interp_output).exists():
            checks["interp_size_mb"] = round(
                Path(interp_output).stat().st_size / (1024 * 1024), 1
            )
        return checks

    # 构建 DAG
    executor.add_stage("perceive", _perceive, deps=[], priority=10, max_retries=2)
    executor.add_stage("analyze", _analyze, deps=[], priority=10, max_retries=2)
    executor.add_stage("plan", _plan, deps=["perceive", "analyze"], priority=5)
    executor.add_stage("execute", _execute, deps=["plan"], priority=3,
                       timeout=600, max_retries=2)
    executor.add_stage("render", _render, deps=["execute"], priority=2, timeout=600)
    executor.add_stage("verify", _verify, deps=["render"], priority=1)

    return executor


# ============================================================================
#  CLI
# ============================================================================

def main():
    """CLI 入口"""
    import os
    import sys
    import argparse
    ap = argparse.ArgumentParser(description="多线程管线执行器")
    ap.add_argument("video", nargs="?", help="输入视频路径")
    ap.add_argument("-o", "--output-dir", default=r"D:\AE-Work\output")
    ap.add_argument("-w", "--workers", type=int, default=4, help="最大线程数")
    ap.add_argument("--demo", action="store_true", help="运行演示（无需视频）")
    args = ap.parse_args()

    if args.demo:
        # 演示模式：模拟阶段
        print("Running demo mode...")
        executor = MultiThreadExecutor(max_workers=args.workers)

        def demo_perceive(ctx):
            time.sleep(1)
            return {"scenes": 5}

        def demo_analyze(ctx):
            time.sleep(1.5)
            return {"brightness": 0.45, "contrast": 0.20}

        def demo_plan(ctx):
            time.sleep(0.5)
            return {"preset": "cinematic"}

        def demo_execute(ctx):
            time.sleep(2)
            return {"clips_graded": 5}

        def demo_render(ctx):
            time.sleep(1)
            return {"output": "demo_60fps.mp4"}

        def demo_verify(ctx):
            time.sleep(0.3)
            return {"all_checks_passed": True}

        executor.add_stage("perceive", demo_perceive, deps=[], priority=10)
        executor.add_stage("analyze", demo_analyze, deps=[], priority=10)
        executor.add_stage("plan", demo_plan, deps=["perceive", "analyze"])
        executor.add_stage("execute", demo_execute, deps=["plan"], max_retries=2)
        executor.add_stage("render", demo_render, deps=["execute"])
        executor.add_stage("verify", demo_verify, deps=["render"])

        result = executor.run_all()
        print(f"\nDemo result: success={result.success}, duration={result.total_duration_sec:.1f}s")
        return

    if not args.video:
        ap.error("请提供输入视频路径或使用 --demo 运行演示")

    from integrations.unified_video_pipeline import UnifiedVideoPipeline
    pipeline = UnifiedVideoPipeline()
    os.makedirs(args.output_dir, exist_ok=True)

    executor = create_video_pipeline_executor(
        pipeline_instance=pipeline,
        video_path=args.video,
        output_dir=args.output_dir,
        max_workers=args.workers,
    )
    result = executor.run_all()

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
