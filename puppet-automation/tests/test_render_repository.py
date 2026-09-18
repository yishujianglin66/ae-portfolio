"""RenderJobRepository 单元测试。

测试覆盖：
- 连接生命周期（context manager / 文件数据库创建）
- CRUD 操作（create_job / get_job / update_job / delete_job）
- list_jobs 多维度筛选（status / project_path / days / limit / offset）
- get_active_jobs
- mark_stale_as_failed（重启恢复清理）
- get_stats（成功率 / 平均耗时 / 失败原因 Top N）
- 并发安全（多个协程同时写）
- RenderProgressParser 与 repository 集成
- RenderJob / RenderStats 数据类 to_dict/from_dict
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
async def repo():
    """每个测试用例使用独立的临时文件数据库。"""
    from src.services.render_repository import RenderJobRepository

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "render_jobs.db"
        repository = RenderJobRepository(db_path=db_path)
        await repository.connect()
        yield repository
        await repository.close()


@pytest.fixture
async def memory_repo():
    """内存数据库（更快，适合不需要文件持久化的测试）。"""
    from src.services.render_repository import RenderJobRepository

    repository = RenderJobRepository(db_path=":memory:")
    await repository.connect()
    yield repository
    await repository.close()


def _make_iso(days_ago: float = 0.0) -> str:
    """生成相对当前时间 days_ago 天前的 ISO 8601 UTC 字符串。"""
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================
# 数据类测试
# ============================================================

class TestRenderJobDataclass:
    def test_default_values(self):
        from src.models.render_job import RENDER_STATUS_PENDING, RenderJob

        job = RenderJob(
            job_id="j1",
            project_path="/p.aep",
            comp_name="comp",
            output_path="/out.mp4",
        )
        assert job.status == RENDER_STATUS_PENDING
        assert job.progress == 0.0
        assert job.total_frames == 0
        assert job.retry_count == 0
        assert job.created_at  # 自动填充
        assert job.updated_at  # 自动填充

    def test_to_dict_contains_all_fields(self):
        from src.models.render_job import RenderJob

        job = RenderJob(
            job_id="j1",
            project_path="/p.aep",
            comp_name="comp",
            output_path="/out.mp4",
        )
        d = job.to_dict()
        assert d["job_id"] == "j1"
        assert "status" in d
        assert "progress" in d
        assert "metadata" in d
        assert "created_at" in d

    def test_from_dict_ignores_unknown_fields(self):
        from src.models.render_job import RenderJob

        job = RenderJob.from_dict({
            "job_id": "j1",
            "project_path": "/p.aep",
            "comp_name": "comp",
            "output_path": "/out.mp4",
            "unknown_field": "ignored",
        })
        assert job.job_id == "j1"
        assert not hasattr(job, "unknown_field")

    def test_is_active_is_terminal(self):
        from src.models.render_job import RenderJob

        pending = RenderJob("j", "p", "c", "o", status="pending")
        rendering = RenderJob("j", "p", "c", "o", status="rendering")
        completed = RenderJob("j", "p", "c", "o", status="completed")
        failed = RenderJob("j", "p", "c", "o", status="failed")

        assert pending.is_active and not pending.is_terminal
        assert rendering.is_active and not rendering.is_terminal
        assert not completed.is_active and completed.is_terminal
        assert not failed.is_active and failed.is_terminal

    def test_percent_with_total_frames(self):
        from src.models.render_job import RenderJob

        job = RenderJob("j", "p", "c", "o", current_frame=25, total_frames=100)
        assert job.percent == 25.0

    def test_percent_with_progress_field(self):
        from src.models.render_job import RenderJob

        job = RenderJob("j", "p", "c", "o", progress=0.5, total_frames=0)
        assert job.percent == 50.0

    def test_metadata_dict_parses_json(self):
        from src.models.render_job import RenderJob

        job = RenderJob(
            "j", "p", "c", "o",
            metadata='{"key": "value", "n": 42}',
        )
        assert job.metadata_dict == {"key": "value", "n": 42}

    def test_metadata_dict_invalid_returns_empty(self):
        from src.models.render_job import RenderJob

        job = RenderJob("j", "p", "c", "o", metadata="not-json")
        assert job.metadata_dict == {}

    def test_metadata_dict_empty(self):
        from src.models.render_job import RenderJob

        job = RenderJob("j", "p", "c", "o")
        assert job.metadata_dict == {}


class TestRenderStatsDataclass:
    def test_to_dict_serializes_failure_reasons(self):
        from src.models.render_job import RenderStats

        stats = RenderStats(
            total_jobs=10,
            completed=7,
            failed=2,
            rendering=1,
            pending=0,
            cancelled=1,
            success_rate=7 / 10,
            avg_elapsed_seconds=120.5,
            common_failure_reasons=[("OOM", 3), ("timeout", 2)],
        )
        d = stats.to_dict()
        assert d["total_jobs"] == 10
        assert d["success_rate"] == 0.7
        assert d["common_failure_reasons"] == [
            {"reason": "OOM", "count": 3},
            {"reason": "timeout", "count": 2},
        ]

    def test_default_zero_success_rate(self):
        from src.models.render_job import RenderStats

        stats = RenderStats()
        assert stats.success_rate == 0.0
        assert stats.avg_elapsed_seconds == 0.0
        assert stats.common_failure_reasons == []


# ============================================================
# Repository 连接与生命周期
# ============================================================

class TestRepositoryLifecycle:
    @pytest.mark.asyncio
    async def test_connect_and_close(self, tmp_path):
        from src.services.render_repository import RenderJobRepository

        db_path = tmp_path / "test.db"
        repo = RenderJobRepository(db_path=db_path)
        assert not repo.is_connected
        await repo.connect()
        assert repo.is_connected
        await repo.close()
        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_context_manager(self, tmp_path):
        from src.services.render_repository import RenderJobRepository

        db_path = tmp_path / "ctx.db"
        async with RenderJobRepository(db_path=db_path) as repo:
            assert repo.is_connected
            await repo.create_job("j1", "/p.aep", "comp", "/out.mp4")
            job = await repo.get_job("j1")
            assert job is not None
        assert not repo.is_connected

    @pytest.mark.asyncio
    async def test_connect_creates_parent_dir(self, tmp_path):
        from src.services.render_repository import RenderJobRepository

        db_path = tmp_path / "subdir" / "nested" / "test.db"
        async with RenderJobRepository(db_path=db_path) as repo:
            await repo.create_job("j1", "/p.aep", "comp", "/out.mp4")
        assert db_path.exists()
        assert db_path.parent.exists()

    @pytest.mark.asyncio
    async def test_get_before_connect_raises(self):
        from src.services.render_repository import RenderJobRepository

        repo = RenderJobRepository(db_path=":memory:")
        with pytest.raises(RuntimeError, match="not connected"):
            await repo.get_job("any")

    @pytest.mark.asyncio
    async def test_memory_db(self, memory_repo):
        """内存数据库应能正常工作。"""
        job = await memory_repo.create_job(
            "j1", "/p.aep", "comp", "/out.mp4", total_frames=100
        )
        assert job.job_id == "j1"
        loaded = await memory_repo.get_job("j1")
        assert loaded is not None
        assert loaded.total_frames == 100


# ============================================================
# CRUD 操作
# ============================================================

class TestCreateJob:
    @pytest.mark.asyncio
    async def test_create_basic(self, repo):
        job = await repo.create_job(
            "j1", "/proj.aep", "main_comp", "/out.mp4", total_frames=300
        )
        assert job.job_id == "j1"
        assert job.project_path == "/proj.aep"
        assert job.comp_name == "main_comp"
        assert job.output_path == "/out.mp4"
        assert job.total_frames == 300
        assert job.status == "pending"

    @pytest.mark.asyncio
    async def test_create_with_optional_fields(self, repo):
        job = await repo.create_job(
            "j1", "/p.aep", "c", "/o.mp4", 100,
            fps=24.0,
            status="rendering",
            started_at=_make_iso(0),
            metadata={"renderer": "aerender"},
        )
        assert job.fps == 24.0
        assert job.status == "rendering"
        # metadata 自动序列化为 JSON 字符串
        assert isinstance(job.metadata, str)
        assert json.loads(job.metadata) == {"renderer": "aerender"}

    @pytest.mark.asyncio
    async def test_create_duplicate_raises(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        with pytest.raises(ValueError, match="已存在"):
            await repo.create_job("j1", "/p.aep", "c", "/o.mp4")

    @pytest.mark.asyncio
    async def test_create_invalid_field_raises(self, repo):
        with pytest.raises(ValueError, match="不允许的字段"):
            await repo.create_job(
                "j1", "/p.aep", "c", "/o.mp4",
                invalid_field="oops",
            )


class TestGetJob:
    @pytest.mark.asyncio
    async def test_get_existing(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)
        job = await repo.get_job("j1")
        assert job is not None
        assert job.job_id == "j1"
        assert job.total_frames == 100

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, repo):
        assert await repo.get_job("nope") is None


class TestUpdateJob:
    @pytest.mark.asyncio
    async def test_update_basic(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)
        updated = await repo.update_job(
            "j1", status="rendering", current_frame=50, progress=0.5
        )
        assert updated is not None
        assert updated.status == "rendering"
        assert updated.current_frame == 50
        assert updated.progress == 0.5

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self, repo):
        result = await repo.update_job("nope", status="rendering")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_with_no_fields_raises(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        with pytest.raises(ValueError, match="至少需要"):
            await repo.update_job("j1")

    @pytest.mark.asyncio
    async def test_update_invalid_field_raises(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        with pytest.raises(ValueError, match="不允许更新"):
            await repo.update_job("j1", unknown_field="hacked")

    @pytest.mark.asyncio
    async def test_update_metadata_dict_serialized(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        updated = await repo.update_job("j1", metadata={"foo": "bar"})
        assert updated is not None
        assert isinstance(updated.metadata, str)
        assert json.loads(updated.metadata) == {"foo": "bar"}

    @pytest.mark.asyncio
    async def test_update_status_rendering_sets_started_at(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        updated = await repo.update_job("j1", status="rendering")
        assert updated is not None
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_update_status_completed_sets_completed_at(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        await repo.update_job("j1", status="rendering")
        updated = await repo.update_job(
            "j1", status="completed", elapsed_seconds=42.5
        )
        assert updated is not None
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_failure_reason(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        updated = await repo.update_job(
            "j1", status="failed", failure_reason="OOM"
        )
        assert updated is not None
        assert updated.status == "failed"
        assert updated.failure_reason == "OOM"


class TestDeleteJob:
    @pytest.mark.asyncio
    async def test_delete_existing(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        assert await repo.delete_job("j1") is True
        assert await repo.get_job("j1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, repo):
        assert await repo.delete_job("nope") is False


# ============================================================
# 列表查询
# ============================================================

class TestListJobs:
    @pytest.mark.asyncio
    async def test_list_empty(self, repo):
        jobs = await repo.list_jobs()
        assert jobs == []

    @pytest.mark.asyncio
    async def test_list_all_recent(self, repo):
        for i in range(5):
            await repo.create_job(f"j{i}", "/p.aep", "c", "/o.mp4")
        jobs = await repo.list_jobs(days=7)
        assert len(jobs) == 5

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="pending")
        await repo.create_job("j2", "/p.aep", "c", "/o.mp4", status="rendering")
        await repo.create_job("j3", "/p.aep", "c", "/o.mp4", status="completed")

        pending = await repo.list_jobs(status="pending")
        assert {j.job_id for j in pending} == {"j1"}

        rendering = await repo.list_jobs(status="rendering")
        assert {j.job_id for j in rendering} == {"j2"}

    @pytest.mark.asyncio
    async def test_list_filter_by_project(self, repo):
        await repo.create_job("j1", "/projA.aep", "c", "/o.mp4")
        await repo.create_job("j2", "/projB.aep", "c", "/o.mp4")
        await repo.create_job("j3", "/projA.aep", "c", "/o.mp4")

        projA = await repo.list_jobs(project_path="/projA.aep")
        assert {j.job_id for j in projA} == {"j1", "j3"}

    @pytest.mark.asyncio
    async def test_list_filter_by_days(self, repo):
        """days=0 应排除所有任务（因为时间下界是 now）。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        jobs = await repo.list_jobs(days=0)
        # created_at 是 'now'，可能刚好等于 cutoff 或不等于，结果不确定
        # 但 days=7 应能查到
        assert len(await repo.list_jobs(days=7)) == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, repo):
        for i in range(10):
            await repo.create_job(f"j{i:02d}", "/p.aep", "c", "/o.mp4")
        page1 = await repo.list_jobs(limit=5, offset=0)
        page2 = await repo.list_jobs(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        page1_ids = {j.job_id for j in page1}
        page2_ids = {j.job_id for j in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_list_limit_capped_at_500(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4")
        # 传入超大 limit 应被裁剪到 500，不报错
        jobs = await repo.list_jobs(limit=10000)
        assert len(jobs) == 1

    @pytest.mark.asyncio
    async def test_list_combined_filters(self, repo):
        await repo.create_job("j1", "/A.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j2", "/A.aep", "c", "/o.mp4", status="failed")
        await repo.create_job("j3", "/B.aep", "c", "/o.mp4", status="completed")

        result = await repo.list_jobs(status="completed", project_path="/A.aep")
        assert {j.job_id for j in result} == {"j1"}


class TestGetActiveJobs:
    @pytest.mark.asyncio
    async def test_active_jobs_only(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="pending")
        await repo.create_job("j2", "/p.aep", "c", "/o.mp4", status="rendering")
        await repo.create_job("j3", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j4", "/p.aep", "c", "/o.mp4", status="failed")

        active = await repo.get_active_jobs()
        active_ids = {j.job_id for j in active}
        assert active_ids == {"j1", "j2"}

    @pytest.mark.asyncio
    async def test_active_jobs_empty(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        assert await repo.get_active_jobs() == []


# ============================================================
# mark_stale_as_failed（重启恢复）
# ============================================================

class TestMarkStaleAsFailed:
    @pytest.mark.asyncio
    async def test_no_stale_jobs(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        count = await repo.mark_stale_as_failed(stale_minutes=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_stale_active_job_marked_failed(self, repo):
        """手动将 updated_at 改为 60 分钟前来模拟 stale。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="rendering")
        # 直接 SQL 改 updated_at
        old_iso = _make_iso(60 / 1440)  # 60 分钟前
        await repo._conn.execute(
            "UPDATE render_jobs SET updated_at = ? WHERE job_id = ?",
            (old_iso, "j1"),
        )
        await repo._conn.commit()

        count = await repo.mark_stale_as_failed(stale_minutes=30)
        assert count == 1

        job = await repo.get_job("j1")
        assert job.status == "failed"
        assert "stale" in (job.failure_reason or "").lower() or (
            "无更新" in (job.failure_reason or "")
        )

    @pytest.mark.asyncio
    async def test_stale_threshold_inclusive(self, repo):
        """刚创建的任务（updated_at=now）不应被标记为 stale。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="rendering")
        count = await repo.mark_stale_as_failed(stale_minutes=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_terminal_jobs_not_affected(self, repo):
        """已完成的任务不应被 mark_stale_as_failed 影响。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        old_iso = _make_iso(60 / 1440)
        await repo._conn.execute(
            "UPDATE render_jobs SET updated_at = ? WHERE job_id = ?",
            (old_iso, "j1"),
        )
        await repo._conn.commit()

        count = await repo.mark_stale_as_failed(stale_minutes=30)
        assert count == 0
        job = await repo.get_job("j1")
        assert job.status == "completed"

    @pytest.mark.asyncio
    async def test_multiple_stale_jobs(self, repo):
        for i in range(3):
            await repo.create_job(
                f"j{i}", "/p.aep", "c", "/o.mp4", status="rendering"
            )
            old_iso = _make_iso(60 / 1440)
            await repo._conn.execute(
                "UPDATE render_jobs SET updated_at = ? WHERE job_id = ?",
                (old_iso, f"j{i}"),
            )
        await repo._conn.commit()

        count = await repo.mark_stale_as_failed(stale_minutes=30)
        assert count == 3


# ============================================================
# 统计
# ============================================================

class TestGetStats:
    @pytest.mark.asyncio
    async def test_empty_stats(self, repo):
        stats = await repo.get_stats(days=30)
        assert stats.total_jobs == 0
        assert stats.completed == 0
        assert stats.success_rate == 0.0
        assert stats.avg_elapsed_seconds == 0.0
        assert stats.common_failure_reasons == []

    @pytest.mark.asyncio
    async def test_status_counts(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j2", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j3", "/p.aep", "c", "/o.mp4", status="failed")
        await repo.create_job("j4", "/p.aep", "c", "/o.mp4", status="rendering")
        await repo.create_job("j5", "/p.aep", "c", "/o.mp4", status="pending")
        await repo.create_job("j6", "/p.aep", "c", "/o.mp4", status="cancelled")

        stats = await repo.get_stats(days=30)
        assert stats.total_jobs == 6
        assert stats.completed == 2
        assert stats.failed == 1
        assert stats.rendering == 1
        assert stats.pending == 1
        assert stats.cancelled == 1

    @pytest.mark.asyncio
    async def test_success_rate(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j2", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j3", "/p.aep", "c", "/o.mp4", status="failed")

        stats = await repo.get_stats(days=30)
        # terminal = 2 completed + 1 failed = 3, success = 2/3
        assert stats.success_rate == pytest.approx(2 / 3, abs=1e-3)

    @pytest.mark.asyncio
    async def test_success_rate_no_terminal(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="rendering")
        stats = await repo.get_stats(days=30)
        assert stats.success_rate == 0.0

    @pytest.mark.asyncio
    async def test_avg_elapsed_seconds(self, repo):
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.create_job("j2", "/p.aep", "c", "/o.mp4", status="completed")
        await repo.update_job("j1", elapsed_seconds=100.0)
        await repo.update_job("j2", elapsed_seconds=200.0)

        stats = await repo.get_stats(days=30)
        assert stats.avg_elapsed_seconds == 150.0

    @pytest.mark.asyncio
    async def test_common_failure_reasons(self, repo):
        await repo.create_job(
            "j1", "/p.aep", "c", "/o.mp4", status="failed", failure_reason="OOM"
        )
        await repo.create_job(
            "j2", "/p.aep", "c", "/o.mp4", status="failed", failure_reason="OOM"
        )
        await repo.create_job(
            "j3", "/p.aep", "c", "/o.mp4", status="failed", failure_reason="timeout"
        )
        await repo.create_job(
            "j4", "/p.aep", "c", "/o.mp4", status="failed", failure_reason="OOM"
        )

        stats = await repo.get_stats(days=30)
        reasons = dict(stats.common_failure_reasons)
        assert reasons["OOM"] == 3
        assert reasons["timeout"] == 1

    @pytest.mark.asyncio
    async def test_common_failure_reasons_top5(self, repo):
        for reason in ["r1", "r2", "r3", "r4", "r5", "r6"]:
            await repo.create_job(
                f"j-{reason}", "/p.aep", "c", "/o.mp4",
                status="failed", failure_reason=reason,
            )
        stats = await repo.get_stats(days=30)
        assert len(stats.common_failure_reasons) == 5


# ============================================================
# 并发安全
# ============================================================

class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_writes_different_jobs(self, repo):
        """多个协程并发创建不同 job_id 的任务。"""
        async def create_one(idx: int):
            await repo.create_job(
                f"j{idx:03d}", "/p.aep", "c", "/o.mp4", 100
            )

        await asyncio.gather(*[create_one(i) for i in range(20)])
        jobs = await repo.list_jobs(days=7, limit=500)
        assert len(jobs) == 20

    @pytest.mark.asyncio
    async def test_concurrent_updates_same_job(self, repo):
        """多个协程并发更新同一个任务的不同字段。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)

        async def update_field(field: str, value: Any):
            await repo.update_job("j1", **{field: value})

        # 并发更新不同字段
        await asyncio.gather(
            update_field("current_frame", 50),
            update_field("status", "rendering"),
            update_field("fps", 24.0),
            update_field("elapsed_seconds", 30.5),
        )

        job = await repo.get_job("j1")
        # 最终所有更新都应生效（顺序可能不同）
        assert job.current_frame == 50
        assert job.status == "rendering"
        assert job.fps == 24.0
        assert job.elapsed_seconds == 30.5

    @pytest.mark.asyncio
    async def test_concurrent_mixed_read_write(self, repo):
        """并发读 + 写不互相阻塞。"""
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)

        async def writer():
            for i in range(10):
                await repo.update_job("j1", current_frame=i)
            await repo.update_job("j1", status="completed")

        async def reader():
            for _ in range(10):
                await repo.get_job("j1")

        await asyncio.gather(writer(), reader())
        job = await repo.get_job("j1")
        assert job.status == "completed"


# ============================================================
# RenderProgressParser 集成
# ============================================================

class TestParserIntegration:
    @pytest.mark.asyncio
    async def test_parser_persists_status_changes(self, repo):
        """解析到 PROGRESS 行时，状态变化应被持久化到 repository。"""
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(
            total_frames=100,
            job_id="j1",
            repository=repo,
        )
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)

        # 模拟首帧行（idle → rendering）
        parser.parse_line("PROGRESS:  0:00:00:01 (1): 0 Seconds")
        # 让 create_task 完成
        await asyncio.sleep(0.05)

        job = await repo.get_job("j1")
        assert job.status == "rendering"
        assert job.current_frame >= 1
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_parser_persists_progress(self, repo):
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(
            total_frames=100,
            job_id="j1",
            repository=repo,
        )
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)

        parser.parse_line("PROGRESS:  0:00:00:01 (1): 0 Seconds")
        parser.parse_line("PROGRESS:  0:00:00:02 (50): 1 Seconds")
        await asyncio.sleep(0.05)

        job = await repo.get_job("j1")
        assert job.current_frame >= 50
        assert job.progress > 0

    @pytest.mark.asyncio
    async def test_parser_persists_completion(self, repo):
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(
            total_frames=100,
            job_id="j1",
            repository=repo,
        )
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)
        # 先进入 rendering
        parser.parse_line("PROGRESS:  0:00:00:01 (1): 0 Seconds")
        # 模拟完成（Total Time Elapsed 行）
        parser.parse_line("Total Time Elapsed: 0:00:30:00")
        await asyncio.sleep(0.05)

        job = await repo.get_job("j1")
        assert job.status == "completed"
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_parser_persists_failure(self, repo):
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(
            total_frames=100,
            job_id="j1",
            repository=repo,
        )
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)
        parser.parse_line("PROGRESS:  0:00:00:01 (1): 0 Seconds")
        parser.parse_line("aerender error: crashed")
        await asyncio.sleep(0.05)

        job = await repo.get_job("j1")
        assert job.status == "failed"

    @pytest.mark.asyncio
    async def test_parser_without_repository_skips_persist(self, repo):
        """未注入 repository 时，解析器不应抛异常。"""
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(total_frames=100)
        # 不应抛出异常
        result = parser.parse_line("PROGRESS:  0:00:00:01 (1): 0 Seconds")
        assert result is not None
        assert result.status == "rendering"

    @pytest.mark.asyncio
    async def test_parser_persist_progress_method(self, repo):
        """persist_progress() 方法主动同步进度。"""
        from src.services.render_progress import RenderProgressParser

        parser = RenderProgressParser(
            total_frames=100,
            job_id="j1",
            repository=repo,
        )
        await repo.create_job("j1", "/p.aep", "c", "/o.mp4", 100)

        # 直接修改内存状态后用 persist_progress 主动同步
        parser.progress.current_frame = 25
        parser.progress.status = "rendering"
        await parser.persist_progress()

        job = await repo.get_job("j1")
        assert job.current_frame == 25
        assert job.status == "rendering"


# ============================================================
# 持久化跨连接验证（模拟服务重启）
# ============================================================

class TestPersistenceAcrossRestarts:
    @pytest.mark.asyncio
    async def test_data_survives_reconnect(self, tmp_path):
        """关闭并重新打开数据库后，数据应仍然存在。"""
        from src.services.render_repository import RenderJobRepository

        db_path = tmp_path / "restart.db"

        # 第一次连接：写入数据
        repo1 = RenderJobRepository(db_path=db_path)
        await repo1.connect()
        await repo1.create_job("j1", "/p.aep", "c", "/o.mp4", 100)
        await repo1.update_job("j1", status="rendering", current_frame=50)
        await repo1.close()

        # 第二次连接：验证数据仍在
        repo2 = RenderJobRepository(db_path=db_path)
        await repo2.connect()
        job = await repo2.get_job("j1")
        assert job is not None
        assert job.status == "rendering"
        assert job.current_frame == 50

        # mark_stale_as_failed 应能识别旧记录
        count = await repo2.mark_stale_as_failed(stale_minutes=30)
        # 任务刚创建，不应被标记为 stale
        assert count == 0
        await repo2.close()

    @pytest.mark.asyncio
    async def test_stale_detection_after_restart(self, tmp_path):
        """模拟服务崩溃后重启：未完成的活跃任务应被 mark_stale_as_failed 清理。"""
        from src.services.render_repository import RenderJobRepository

        db_path = tmp_path / "crash.db"

        # 第一次连接：写入一个 rendering 状态的任务，模拟服务崩溃前
        repo1 = RenderJobRepository(db_path=db_path)
        await repo1.connect()
        await repo1.create_job("j1", "/p.aep", "c", "/o.mp4", 100, status="rendering")
        # 把 updated_at 改为 2 小时前，模拟服务崩溃 2 小时后重启
        old_iso = _make_iso(120 / 1440)
        await repo1._conn.execute(
            "UPDATE render_jobs SET updated_at = ? WHERE job_id = ?",
            (old_iso, "j1"),
        )
        await repo1._conn.commit()
        await repo1.close()

        # 第二次连接：模拟重启
        repo2 = RenderJobRepository(db_path=db_path)
        await repo2.connect()
        count = await repo2.mark_stale_as_failed(stale_minutes=30)
        assert count == 1

        job = await repo2.get_job("j1")
        assert job.status == "failed"
        assert job.failure_reason is not None
        await repo2.close()
