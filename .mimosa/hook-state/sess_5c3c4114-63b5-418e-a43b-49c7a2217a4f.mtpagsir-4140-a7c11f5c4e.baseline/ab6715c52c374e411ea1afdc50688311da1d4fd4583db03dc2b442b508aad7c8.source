"""
tests/test_orchestrator_dag.py — DAG 编排器单元测试
====================================================

运行：pytest tests/test_orchestrator_dag.py -v
"""
import asyncio
import json
import time
from pathlib import Path

import pytest

from core.workflow_orchestrator import (
    DAGOrchestrator,
    RunManifest,
    StageRecord,
    create_dag_orchestrator,
)


# ============================================================================
#  Fixtures
# ============================================================================

@pytest.fixture
def run_dir(tmp_path):
    """临时 run 目录"""
    d = tmp_path / "flagship_test_run"
    d.mkdir()
    return d


@pytest.fixture
def dag(run_dir):
    """基础 DAG 编排器"""
    return DAGOrchestrator(run_dir=run_dir, run_id="test_run_001")


# ============================================================================
#  StageRecord / RunManifest 数据类
# ============================================================================

class TestDataClasses:
    def test_stage_record_defaults(self):
        rec = StageRecord(stage_id="S0")
        assert rec.status == "pending"
        assert rec.elapsed_s == 0.0
        assert rec.output_paths == []

    def test_manifest_to_json(self):
        m = RunManifest(run_id="r1", pipeline_name="test")
        m.stages["S0"] = StageRecord(stage_id="S0", status="passed")
        data = json.loads(m.to_json())
        assert data["run_id"] == "r1"
        assert data["stages"]["S0"]["status"] == "passed"

    def test_manifest_save_and_load(self, tmp_path):
        m = RunManifest(run_id="r2", pipeline_name="flagship")
        m.stages["S0"] = StageRecord(stage_id="S0", status="passed", elapsed_s=1.5)
        m.stages["S1"] = StageRecord(stage_id="S1", status="failed", error="timeout")

        path = tmp_path / "manifest.json"
        m.save(path)
        assert path.exists()

        loaded = RunManifest.load(path)
        assert loaded.run_id == "r2"
        assert loaded.stages["S0"].status == "passed"
        assert loaded.stages["S1"].error == "timeout"

    def test_manifest_save_creates_dirs(self, tmp_path):
        m = RunManifest(run_id="r3")
        path = tmp_path / "deep" / "nested" / "manifest.json"
        m.save(path)
        assert path.exists()


# ============================================================================
#  拓扑排序
# ============================================================================

class TestTopologicalSort:
    def test_linear_chain(self, dag):
        dag.define_stage("S0", func=lambda *a: {}, deps=[])
        dag.define_stage("S1", func=lambda *a: {}, deps=["S0"])
        dag.define_stage("S2", func=lambda *a: {}, deps=["S1"])
        order = dag._topological_sort()
        assert order == ["S0", "S1", "S2"]

    def test_diamond_dag(self, dag):
        dag.define_stage("S0", func=lambda *a: {}, deps=[])
        dag.define_stage("S1", func=lambda *a: {}, deps=["S0"])
        dag.define_stage("S2", func=lambda *a: {}, deps=["S0"])
        dag.define_stage("S3", func=lambda *a: {}, deps=["S1", "S2"])
        order = dag._topological_sort()
        assert order.index("S0") < order.index("S1")
        assert order.index("S0") < order.index("S2")
        assert order.index("S1") < order.index("S3")
        assert order.index("S2") < order.index("S3")

    def test_cycle_detection(self, dag):
        dag.define_stage("A", func=lambda *a: {}, deps=["B"])
        dag.define_stage("B", func=lambda *a: {}, deps=["A"])
        with pytest.raises(ValueError, match="循环依赖"):
            dag._topological_sort()

    def test_parallel_stages(self, dag):
        dag.define_stage("S0", func=lambda *a: {}, deps=[])
        dag.define_stage("S1", func=lambda *a: {}, deps=[])
        dag.define_stage("S2", func=lambda *a: {}, deps=[])
        order = dag._topological_sort()
        assert set(order) == {"S0", "S1", "S2"}


# ============================================================================
#  执行测试
# ============================================================================

class TestExecution:
    @pytest.mark.asyncio
    async def test_simple_pass(self, dag, run_dir):
        """全部阶段成功"""
        results = []

        def stage_func(stage_id, rd, manifest):
            results.append(stage_id)
            return {"success": True, "output_paths": [f"{stage_id}.out"]}

        dag.define_stage("S0", func=stage_func, deps=[])
        dag.define_stage("S1", func=stage_func, deps=["S0"])

        manifest = await dag.execute()
        assert manifest.overall_status == "passed"
        assert manifest.stages["S0"].status == "passed"
        assert manifest.stages["S1"].status == "passed"
        assert results == ["S0", "S1"]

    @pytest.mark.asyncio
    async def test_stage_failure_stops_dag(self, dag, run_dir):
        """阶段失败 → 后续跳过 → 整体 failed"""
        def fail_func(stage_id, rd, manifest):
            return {"success": False, "error": "bridge down", "error_code": "BRIDGE_DOWN"}

        def pass_func(stage_id, rd, manifest):
            return {"success": True}

        dag.define_stage("S0", func=fail_func, deps=[])
        dag.define_stage("S1", func=pass_func, deps=["S0"])

        manifest = await dag.execute()
        assert manifest.overall_status == "failed"
        assert manifest.stages["S0"].status == "failed"
        assert manifest.stages["S0"].error_code == "BRIDGE_DOWN"
        # S1 不应被执行（依赖 S0 失败）
        assert manifest.stages["S1"].status in ("pending", "skipped")

    @pytest.mark.asyncio
    async def test_exception_in_stage(self, dag, run_dir):
        """阶段抛异常 → 重试 → 最终 failed"""
        call_count = {"n": 0}

        def explode_func(stage_id, rd, manifest):
            call_count["n"] += 1
            raise RuntimeError("unexpected crash")

        dag.max_retry = 1
        dag.define_stage("S0", func=explode_func, deps=[])

        manifest = await dag.execute()
        assert manifest.overall_status == "failed"
        assert manifest.stages["S0"].status == "failed"
        assert "crash" in manifest.stages["S0"].error
        assert call_count["n"] == 2  # 初始 + 1 次重试

    @pytest.mark.asyncio
    async def test_async_stage_func(self, dag, run_dir):
        """支持异步 stage func"""
        async def async_func(stage_id, rd, manifest):
            await asyncio.sleep(0.01)
            return {"success": True, "output_paths": ["async.out"]}

        dag.define_stage("S0", func=async_func, deps=[])
        manifest = await dag.execute()
        assert manifest.stages["S0"].status == "passed"
        assert manifest.stages["S0"].output_paths == ["async.out"]

    @pytest.mark.asyncio
    async def test_manifest_persisted(self, dag, run_dir):
        """执行后 manifest.json 落盘"""
        dag.define_stage("S0", func=lambda *a: {"success": True}, deps=[])
        await dag.execute()

        manifest_path = run_dir / "manifest.json"
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert data["overall_status"] == "passed"
        assert data["stages"]["S0"]["status"] == "passed"

    @pytest.mark.asyncio
    async def test_elapsed_time_recorded(self, dag, run_dir):
        """记录阶段耗时"""
        def slow_func(stage_id, rd, manifest):
            time.sleep(0.05)
            return {"success": True}

        dag.define_stage("S0", func=slow_func, deps=[])
        manifest = await dag.execute()
        assert manifest.stages["S0"].elapsed_s >= 0.04
        assert manifest.total_elapsed_s >= 0.04


# ============================================================================
#  Resume 测试
# ============================================================================

class TestResume:
    @pytest.mark.asyncio
    async def test_resume_skips_passed(self, run_dir):
        """resume 时跳过已通过阶段"""
        # 第一次运行：S0 通过，S1 失败
        dag1 = DAGOrchestrator(run_dir=run_dir, run_id="resume_test")
        call_log = []

        def s0_func(stage_id, rd, manifest):
            call_log.append("S0")
            return {"success": True}

        def s1_func(stage_id, rd, manifest):
            call_log.append("S1")
            return {"success": False, "error": "first fail"}

        dag1.define_stage("S0", func=s0_func, deps=[])
        dag1.define_stage("S1", func=s1_func, deps=["S0"])
        await dag1.execute()
        assert dag1.manifest.overall_status == "failed"

        # 第二次运行：从 S1 恢复，S1 这次成功
        dag2 = DAGOrchestrator(run_dir=run_dir, run_id="resume_test")
        call_log.clear()

        def s1_fixed(stage_id, rd, manifest):
            call_log.append("S1_fixed")
            return {"success": True}

        dag2.define_stage("S0", func=s0_func, deps=[])
        dag2.define_stage("S1", func=s1_fixed, deps=["S0"])
        manifest = await dag2.execute(resume_from="S1")

        assert manifest.overall_status == "passed"
        assert "S0" not in call_log  # S0 被跳过
        assert "S1_fixed" in call_log


# ============================================================================
#  便捷函数
# ============================================================================

class TestConvenience:
    def test_create_dag_orchestrator(self, tmp_path):
        dag = create_dag_orchestrator(
            run_dir=tmp_path / "run",
            run_id="conv_test",
            pipeline_name="my_pipeline",
        )
        assert dag.run_id == "conv_test"
        assert dag.pipeline_name == "my_pipeline"

    def test_manifest_property(self, dag):
        assert dag.manifest.run_id == "test_run_001"
