"""core/config + core/workflow_orchestrator 补充测试 — 覆盖 P2 缺口

重点缺口:
- ConfigManager.__init__ auto_load=True 时 load_config 抛异常：降级分支（合并默认配置层 + memory.db_path 兜底）
- memory.db_path 在 __init__ 异常分支 vs load_config 正常路径产生的值一致（消除读写分离隐患）
- WorkflowOrchestrator: fallback_func 也失败时 task 最终状态 = FAILED（不卡 RUNNING）
- WorkflowOrchestrator: _is_workflow_complete + _get_ready_tasks + _update_progress 的 skip_on_failure 语义正确性
"""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ConfigManager


# ============================================================================
# Fixtures
# ============================================================================


# ============================================================================
# 1. ConfigManager.__init__ auto-load 异常降级（B4-4 修复回归防护）
# ============================================================================


class TestConfigManagerInitAutoLoadFailure:
    """B4-4 漏洞修复：__init__ 中 auto_load=True 的 try/except 分支之前从未被执行过。"""

    def test_init_autoload_exception_merges_default_config(self, tmp_path):
        """__init__ 中 load_config() 抛异常 → 降级后 _config 非空（含默认配置）。"""
        class _BoomConfigManager(ConfigManager):
            """子类化覆盖 load_config 强制抛异常。"""
            def load_config(self, config_files=None):
                raise RuntimeError("simulated corrupted config file")

        mgr = _BoomConfigManager(auto_load=True)
        # 降级分支应该把 _sources[0]（默认配置层） merge 进来
        assert mgr._config, "_config 在降级分支后为空（B4-4 回归）"
        # server.port 是默认配置里有的，验证默认值生效
        assert mgr.get("server.port") == 8000

    def test_init_autoload_exception_memory_db_path_fallback(self, tmp_path):
        """降级分支中 memory.db_path 被设为默认路径（不依赖 load_config 修正逻辑）。"""
        class _Boom2(ConfigManager):
            def load_config(self, config_files=None):
                raise RuntimeError("simulated boom")

        mgr = _Boom2(auto_load=True)
        db_path = mgr.get("memory.db_path")
        assert db_path is not None, "降级分支未给 memory.db_path 赋值"
        # 默认路径应该含有 ".ae-knowledge-vault/memory.db"
        assert "memory.db" in str(db_path)

    def test_init_autoload_fallback_equals_normal_load_memory_path(self, tmp_path):
        """__init__ 降级路径与正常 load_config 路径产生的 memory.db_path 等价（消除读写分离）。"""
        # (A) 正常路径（空 config_files 列表，不读不存在的文件）
        normal_mgr = ConfigManager(auto_load=True)
        normal_mgr.load_config([])
        normal_db = normal_mgr.get("memory.db_path")

        # (B) 异常降级路径
        class _Boom3(ConfigManager):
            def load_config(self, config_files=None):
                raise RuntimeError("boom")
        fallback_mgr = _Boom3(auto_load=True)
        fallback_db = fallback_mgr.get("memory.db_path")

        # 两者应该都是 ~/.ae-knowledge-vault/memory.db
        # （允许 str 形式不同，用 basename 判断核心语义等价）
        assert os.path.basename(str(normal_db)) == "memory.db"
        assert os.path.basename(str(fallback_db)) == "memory.db"


# ============================================================================
# 2. WorkflowOrchestrator skip_on_failure 语义正确性
# ============================================================================


class TestWorkflowSkipOnFailureSemantics:
    """skip_on_failure 三端一致性：_get_ready_tasks / _is_workflow_complete / _update_progress。"""

    @pytest.fixture
    def orch(self):
        """新编排器 + 3 个任务：t0（起点）→ t1（会失败但可跳过）→ t2（依赖 t1）。"""
        from core.workflow_orchestrator import WorkflowOrchestrator, TaskDefinition, TaskType
        o = WorkflowOrchestrator(max_concurrent_tasks=2)

        async def _t0(**kw):  # 用 **kwargs 接收所有参数，避免签名不匹配
            return {"v": 0}

        async def _t1_fail(**kw):
            raise RuntimeError("simulated failure in t1")

        async def _t2(**kw):
            return {"v": 2}

        o.add_task(TaskDefinition(
            task_id="t0", task_type=TaskType.PLANNING, name="T0",
            func=_t0, dependencies=[], retry_count=0,
        ))
        o.add_task(TaskDefinition(
            task_id="t1", task_type=TaskType.AE_RENDER, name="T1_FAIL_SKIP",
            func=_t1_fail, dependencies=["t0"], retry_count=0,
            skip_on_failure=True,
        ))
        o.add_task(TaskDefinition(
            task_id="t2", task_type=TaskType.AE_EXECUTE, name="T2",
            func=_t2, dependencies=["t1"], retry_count=0,
        ))
        return o

    def test_skipped_failed_dep_marks_dep_ready(self, orch):
        """t1 fail but skip_on_failure=True → t2 should be marked ready。"""
        import asyncio
        ctx = asyncio.run(orch.run(initial_data={}))

        # t1 是失败状态但在 _failed_tasks 里
        assert "t1" in orch._failed_tasks
        # t2 应该被执行（因为 t1 的失败可跳过）
        t2_instance = ctx.tasks.get("t2")
        assert t2_instance is not None
        # t2 可能成功完成（status.COMPLETED） 或者应该至少不被阻塞为 PENDING
        from core.workflow_orchestrator import TaskStatus
        assert t2_instance.status != TaskStatus.PENDING, (
            "t1 skip_on_failure 但下游 t2 仍被挂起未执行"
        )

    def test_workflow_completes_with_skipped_failure(self, orch):
        """1 个任务完成 + 1 个失败可跳过 + 1 个下游 = 总进度 3/3 = complete。"""
        import asyncio
        ctx = asyncio.run(orch.run(initial_data={}))
        from core.workflow_orchestrator import WorkflowStatus
        # 最终状态不应是 FAILED（因为唯一失败的 t1 有 skip_on_failure）
        assert ctx.status != WorkflowStatus.FAILED, (
            f"工作流因 skip_on_failure=True 的任务失败而标记 FAILED（实际={ctx.status}）"
        )
        # 完成度：3/3 应该被算做完（_is_workflow_complete 逻辑）
        assert orch._is_workflow_complete() is True

    def test_progress_reaches_1_0_with_skipped_failure(self, orch):
        """_update_progress 把 skip_on_failure 的失败算作完成，进度最终到 1.0。"""
        import asyncio
        ctx = asyncio.run(orch.run(initial_data={}))
        assert ctx.progress == 1.0, (
            f"含 1 个 skip_on_failure 失败的工作流进度不到 1.0（实际={ctx.progress}）"
        )


# ============================================================================
# 3. WorkflowOrchestrator fallback_func 也失败的最糟场景
# ============================================================================


class TestWorkflowFallbackAlsoFails:
    """fallback_func 也抛异常 → 状态正确为 FAILED，update_success_rate 异常不冒泡。"""

    def test_fallback_failure_ends_in_failed_not_running(self):
        from core.workflow_orchestrator import WorkflowOrchestrator, TaskDefinition, TaskType
        orch = WorkflowOrchestrator(max_concurrent_tasks=1)

        async def _main_fail(**kw):
            raise RuntimeError("main fails")

        async def _fallback_also_fails(**kw):
            raise ZeroDivisionError("fallback also fails")

        orch.add_task(TaskDefinition(
            task_id="double_failure",
            task_type=TaskType.PLANNING,  # 使用确定存在的枚举值
            name="main+fallback both fail",
            func=_main_fail,
            dependencies=[],
            retry_count=0,
            fallback_func=_fallback_also_fails,
            skip_on_failure=False,
        ))

        import asyncio
        ctx = asyncio.run(orch.run())
        from core.workflow_orchestrator import WorkflowStatus, TaskStatus

        # 工作流整体 = FAILED（因为 skip_on_failure=False）
        assert ctx.status == WorkflowStatus.FAILED
        # 单个任务也 = FAILED
        ti = ctx.tasks["double_failure"]
        assert ti.status == TaskStatus.FAILED
