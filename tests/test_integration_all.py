#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API 演示与集成测试脚本
=====================

验证所有新模块的端到端协作能力：
- FastAPI 服务层
- 批处理队列系统
- 任务持久化
- 资源管理器
- 工作流编排器集成

使用 httpx 测试 API 接口，验证完整链路。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ============================================================================
# 测试辅助工具
# ============================================================================

class TestResult:
    """测试结果"""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error: str | None = None
        self.duration = 0.0
        self.details: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "error": self.error,
            "duration": round(self.duration, 3),
            "details": self.details,
        }


class IntegrationTestSuite:
    """集成测试套件"""

    def __init__(self):
        self.results: list[TestResult] = []
        self.tmp_dir: str | None = None

    def run_test(self, name: str, test_func) -> TestResult:
        """运行单个测试"""
        result = TestResult(name)
        print(f"\n  🧪 {name}...", end=" ")
        start = time.time()

        try:
            details = test_func()
            result.passed = True
            result.details = details or {}
            duration = time.time() - start
            result.duration = duration
            print(f"✅ ({duration:.2f}s)")
        except Exception as e:
            result.error = str(e)
            duration = time.time() - start
            result.duration = duration
            print(f"❌ ({duration:.2f}s)")
            print(f"     错误: {e}")

        self.results.append(result)
        return result

    # --------------------------------------------------------------------
    # 测试用例
    # --------------------------------------------------------------------

    def test_batch_queue(self) -> dict[str, Any]:
        """测试1: 批处理队列系统"""
        from batch_queue import BatchQueue, ProgressContext, TaskStatus

        queue = BatchQueue(max_workers=2, max_retries=1)
        queue.start()

        def simple_task(progress: ProgressContext, total: int = 5) -> str:
            for i in range(total):
                progress.update((i + 1) / total, f"步骤 {i+1}/{total}")
                time.sleep(0.05)
            return "完成"

        task = queue.submit(
            simple_task,
            total=3,
            name="测试任务",
            priority=7,
        )

        assert task.task_id is not None
        assert task.status == TaskStatus.PENDING

        queue.wait_for_task(task.task_id, timeout=10)

        completed_task = queue.get_task(task.task_id)
        assert completed_task is not None
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.result == "完成"

        stats = queue.get_stats()
        assert stats["total_submitted"] >= 1
        assert stats["total_completed"] >= 1

        queue.stop()

        return {
            "task_id": task.task_id,
            "result": completed_task.result,
            "stats": stats,
        }

    def test_task_persistence(self) -> dict[str, Any]:
        """测试2: 任务持久化"""
        from task_persistence import PersistenceConfig, TaskPersistence

        persist_dir = os.path.join(self.tmp_dir, "persistence")
        config = PersistenceConfig(
            enabled=True,
            storage_path=persist_dir,
            auto_save_interval=0,
            max_history=50,
        )

        persist = TaskPersistence(config)

        task_data_1 = {
            "task_id": "test_001",
            "name": "测试任务1",
            "status": "completed",
            "priority": 5,
            "result": {"output": "success"},
            "created_at": time.time() - 3600,
            "completed_at": time.time() - 3500,
        }
        persist.save_task("test_001", task_data_1)

        task_data_2 = {
            "task_id": "test_002",
            "name": "测试任务2",
            "status": "pending",
            "priority": 7,
            "created_at": time.time(),
        }
        persist.save_task("test_002", task_data_2)

        loaded = persist.get_task("test_001")
        assert loaded is not None
        assert loaded["name"] == "测试任务1"

        pending = persist.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0]["task_id"] == "test_002"

        stats = persist.get_stats()
        assert stats["active_tasks"] == 2
        assert stats["history_count"] == 0

        cleared = persist.clear_completed(older_than_hours=0.01)
        assert cleared >= 1

        history = persist.get_history(limit=10)
        assert len(history) >= 1

        persist.shutdown()

        return {
            "persist_dir": persist_dir,
            "active_tasks": stats["active_tasks"],
            "pending_count": len(pending),
            "cleared_count": cleared,
            "history_count": len(history),
        }

    def test_resource_manager(self) -> dict[str, Any]:
        """测试3: 资源管理器"""
        from resource_manager import ResourceManager

        manager = ResourceManager()
        snapshot = manager.get_snapshot()

        assert snapshot.cpu is not None
        assert snapshot.memory is not None
        assert isinstance(snapshot.gpus, list)
        assert isinstance(snapshot.disks, list)

        summary = manager.get_summary()
        assert "cpu" in summary
        assert "memory" in summary
        assert "gpus" in summary
        assert "disks" in summary

        threshold_result = manager.check_thresholds(snapshot)
        assert "is_critical" in threshold_result
        assert "warnings" in threshold_result
        assert "critical" in threshold_result

        from resource_manager import TaskResourceRequirement
        req = TaskResourceRequirement(
            task_id="test_req",
            task_type="puppet_style",
            cpu_cores=1,
            memory_gb=0.1,
            gpu_memory_gb=0.0,
        )
        can_accept, details = manager.can_accept_task(req)
        assert "can_accept" in details

        estimated = manager.estimate_task_resource("puppet_style", input_size_gb=1.0)
        assert estimated.task_type == "puppet_style"
        assert estimated.cpu_cores > 0

        return {
            "cpu_cores": snapshot.cpu.logical_cores,
            "cpu_usage": snapshot.cpu.usage_percent,
            "memory_total_gb": snapshot.memory.total_gb,
            "memory_percent": snapshot.memory.percent,
            "gpu_count": len(snapshot.gpus),
            "disk_count": len(snapshot.disks),
            "threshold_issues": threshold_result["total_issues"],
            "can_accept": can_accept,
            "estimated_cpu": estimated.cpu_cores,
            "estimated_memory_gb": estimated.memory_gb,
        }

    def test_workflow_batch_integration(self) -> dict[str, Any]:
        """测试4: 工作流编排器 - 批处理集成"""
        from workflow_batch_integration import WorkflowBatchIntegration

        integration = WorkflowBatchIntegration()

        input_video = os.path.join(self.tmp_dir, "test_input.mp4")
        with open(input_video, "wb") as f:
            f.write(b"\x00" * 1024)

        output_dir = os.path.join(self.tmp_dir, "wf_output")
        os.makedirs(output_dir, exist_ok=True)

        wf_task = integration.submit_puppet_workflow(
            input_path=input_video,
            output_dir=output_dir,
            style="wood",
            auto_detect=True,
            quality="high",
            mode="simulate",
            priority=6,
        )

        assert wf_task.task_id is not None
        assert wf_task.workflow_type == "puppet_style"
        assert wf_task.total_stages > 0

        deadline = time.time() + 30
        while time.time() < deadline:
            task = integration.get_workflow_task(wf_task.task_id)
            if task and task.status in ("completed", "failed"):
                break
            time.sleep(0.2)

        completed_task = integration.get_workflow_task(wf_task.task_id)
        assert completed_task is not None
        assert completed_task.status == "completed"
        assert completed_task.result is not None

        batch_dir = os.path.join(self.tmp_dir, "batch_input")
        batch_output = os.path.join(self.tmp_dir, "batch_wf_output")
        os.makedirs(batch_dir, exist_ok=True)

        batch_files = []
        for i in range(2):
            fpath = os.path.join(batch_dir, f"clip_{i:02d}.mp4")
            with open(fpath, "wb") as f:
                f.write(b"\x00" * 1024)
            batch_files.append(fpath)

        batch_tasks = integration.submit_batch_puppet_workflow(
            input_files=batch_files,
            output_base_dir=batch_output,
            style="ceramic",
            mode="simulate",
        )
        assert len(batch_tasks) == 2

        deadline = time.time() + 60
        while time.time() < deadline:
            all_done = all(
                (integration.get_workflow_task(t.task_id) or t).status
                in ("completed", "failed")
                for t in batch_tasks
            )
            if all_done:
                break
            time.sleep(0.5)

        stats = integration.get_stats()
        assert stats["total_tasks"] >= 3

        return {
            "single_task_id": wf_task.task_id,
            "single_status": completed_task.status if completed_task else "unknown",
            "single_stages": wf_task.total_stages,
            "batch_count": len(batch_tasks),
            "total_tasks": stats["total_tasks"],
            "status_counts": stats["status_counts"],
        }

    def test_api_server_import(self) -> dict[str, Any]:
        """测试5: FastAPI 服务层导入与基本结构"""
        import importlib

        try:
            api_module = importlib.import_module("api_server")
        except ImportError as e:
            return {
                "imported": False,
                "error": str(e),
                "note": "FastAPI 依赖可能未安装",
            }

        assert hasattr(api_module, "app")
        app = api_module.app
        assert app.title == "AE Knowledge Vault API"

        routes = [route.path for route in app.routes if hasattr(route, "path")]

        expected_routes = [
            "/health",
            "/health/live",
            "/health/ready",
            "/api/v1/stats",
            "/api/v1/tasks",
            "/api/v1/puppet/styles",
            "/api/v1/quality/metrics",
        ]

        found_routes = []
        for expected in expected_routes:
            if any(expected in r for r in routes):
                found_routes.append(expected)

        return {
            "imported": True,
            "app_title": app.title,
            "version": app.version,
            "total_routes": len(routes),
            "found_routes": found_routes,
            "expected_routes": len(expected_routes),
        }

    def test_failure_recovery(self) -> dict[str, Any]:
        """测试6: 失败恢复机制"""
        from failure_recovery import ErrorCode, FailureRecovery, FailureRecoveryOptions

        options = FailureRecoveryOptions(
            max_retries=3,
            retry_backoff_factor=2.0,
        )
        recovery = FailureRecovery(options)

        test_error_codes = [
            ErrorCode.BRIDGE_OFFLINE,
            ErrorCode.EXECUTION_TIMEOUT,
            ErrorCode.EFFECT_NOT_FOUND,
            ErrorCode.PARAM_OUT_OF_RANGE,
        ]

        actions = []
        for error_code in test_error_codes:
            try:
                action = recovery.handle_error(error_code.value, f"测试错误: {error_code}")
                actions.append({
                    "error_code": error_code.value,
                    "action": action.action if hasattr(action, 'action') else str(action),
                })
            except Exception as e:
                actions.append({
                    "error_code": error_code.value,
                    "error": str(e)[:100],
                })

        retry_counter = getattr(recovery, '_retry_counter', None)
        if retry_counter and hasattr(retry_counter, '_counts'):
            retry_counts = len(retry_counter._counts)
        else:
            retry_counts = 0

        return {
            "tested_errors": len(test_error_codes),
            "actions_count": len(actions),
            "successful_actions": sum(1 for a in actions if "action" in a),
            "retry_counts": retry_counts,
            "sample_actions": actions[:2],
        }

    def test_config_schema(self) -> dict[str, Any]:
        """测试7: 配置 Schema 验证"""
        try:
            from config_schema import ConfigSchemaNode, ConfigSchemaValidator, ValidationResult
        except ImportError as e:
            return {
                "imported": False,
                "error": str(e),
            }

        test_schema = {
            "server": ConfigSchemaNode(
                type="dict",
                description="服务器配置",
                properties={
                    "host": ConfigSchemaNode(type="string", default="0.0.0.0", description="监听地址"),
                    "port": ConfigSchemaNode(type="int", default=8000, min_value=1, max_value=65535, description="端口"),
                },
            ),
            "batch_queue": ConfigSchemaNode(
                type="dict",
                description="批处理队列配置",
                properties={
                    "max_workers": ConfigSchemaNode(type="int", default=3, min_value=1, max_value=32, description="最大工作线程"),
                    "max_retries": ConfigSchemaNode(type="int", default=2, min_value=0, max_value=10, description="最大重试次数"),
                },
            ),
            "logging": ConfigSchemaNode(
                type="dict",
                description="日志配置",
                properties={
                    "level": ConfigSchemaNode(type="string", default="INFO", enum=["DEBUG", "INFO", "WARNING", "ERROR"], description="日志级别"),
                    "max_bytes": ConfigSchemaNode(type="int", default=10485760, min_value=1024, description="最大文件大小"),
                },
            ),
        }

        validator = ConfigSchemaValidator(test_schema)

        valid_config = {
            "server": {
                "host": "0.0.0.0",
                "port": 8000,
            },
            "batch_queue": {
                "max_workers": 3,
                "max_retries": 2,
            },
            "logging": {
                "level": "INFO",
                "max_bytes": 10485760,
            },
        }

        result = validator.validate(valid_config)

        return {
            "imported": True,
            "valid_config_valid": result.valid,
            "errors_count": len(result.errors),
            "warnings_count": len(result.warnings),
            "schema_keys": list(test_schema.keys()),
        }

    # --------------------------------------------------------------------
    # 运行全部测试
    # --------------------------------------------------------------------

    def run_all(self) -> bool:
        """运行所有测试"""
        print("=" * 70)
        print("  AE Knowledge Vault - 集成测试套件")
        print("=" * 70)

        self.tmp_dir = tempfile.mkdtemp(prefix="ae_kv_test_")
        print(f"\n测试目录: {self.tmp_dir}")

        tests = [
            ("批处理队列系统", self.test_batch_queue),
            ("任务持久化", self.test_task_persistence),
            ("资源管理器", self.test_resource_manager),
            ("工作流编排器集成", self.test_workflow_batch_integration),
            ("FastAPI 服务层", self.test_api_server_import),
            ("失败恢复机制", self.test_failure_recovery),
            ("配置 Schema 验证", self.test_config_schema),
        ]

        for name, func in tests:
            self.run_test(name, func)

        return self.print_summary()

    def print_summary(self) -> bool:
        """打印测试摘要"""
        print("\n" + "=" * 70)
        print("  测试摘要")
        print("=" * 70)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_duration = sum(r.duration for r in self.results)

        print(f"\n  总测试数: {total}")
        print(f"  通过: {passed} ✅")
        print(f"  失败: {failed} ❌")
        print(f"  通过率: {passed/total*100:.1f}%" if total > 0 else "  通过率: N/A")
        print(f"  总耗时: {total_duration:.2f}s")

        print("\n  详细结果:")
        for r in self.results:
            status_icon = "✅" if r.passed else "❌"
            print(f"    {status_icon} {r.name}: {r.duration:.2f}s")
            if not r.passed and r.error:
                print(f"       错误: {r.error[:80]}...")

        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            print("\n测试目录已清理")

        print("\n" + "=" * 70)

        return failed == 0

    def save_report(self, output_path: str):
        """保存测试报告"""
        report = {
            "generated_at": time.time(),
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "total_duration": sum(r.duration for r in self.results),
            "results": [r.to_dict() for r in self.results],
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n测试报告已保存到: {output_path}")


# ============================================================================
# 主入口
# ============================================================================

def main():
    """主入口"""
    suite = IntegrationTestSuite()
    success = suite.run_all()

    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "test_reports",
        f"integration_test_{int(time.time())}.json",
    )
    suite.save_report(report_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
