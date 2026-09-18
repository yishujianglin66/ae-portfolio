"""Tests for the Celery backend and its integration with the orchestrator.

These tests exercise the dual-mode behaviour:

* With ``CELERY_ENABLED=false`` (default in CI), the orchestrator must keep
  using the in-process ``asyncio`` path that the existing 191 tests already
  exercise.
* We invoke Celery task bodies directly to cover the task body / state
  helpers without needing a live broker.  ``get_redis`` is patched to return
  either the ``_NullRedis`` stand-in or a MagicMock.

We never require a live Redis.  The ``_NullRedis`` stand-in is exercised
in every code path; the state-helper tests use a MagicMock that implements
only the methods we touch.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _celery_app_module():
    """Return the *module* object of ``src.workers.celery_app``.

    The ``src.workers`` package re-exports ``celery_app`` (the Celery app
    instance) under the same name, so a plain ``from src.workers import
    celery_app`` would shadow the module.  We sidestep this by loading the
    module by its fully qualified path.
    """
    return importlib.import_module("src.workers.celery_app")


# ============================================================
# Feature flag / state helpers
# ============================================================

class TestFeatureFlag:
    """The CELERY_ENABLED flag must default to False (CI-safe)."""

    def test_celery_disabled_by_default(self):
        m = _celery_app_module()
        # CI never sets the env var
        os.environ.pop("CELERY_ENABLED", None)
        # Re-evaluate the module-level constant by reloading if needed
        assert m.CELERY_ENABLED is False

    def test_celery_enabled_via_env(self, monkeypatch):
        m1 = _celery_app_module()
        monkeypatch.setenv("CELERY_ENABLED", "true")
        importlib.reload(m1)
        try:
            assert m1.CELERY_ENABLED is True
        finally:
            monkeypatch.delenv("CELERY_ENABLED", raising=False)
            importlib.reload(m1)
            assert m1.CELERY_ENABLED is False


class TestNullRedis:
    """The no-op Redis stand-in used when Redis is unavailable."""

    def test_all_methods_are_safe(self):
        m = _celery_app_module()
        r = m._NullRedis()
        # Every operation must return a non-throwing default
        assert r.set("k", "v") is True
        assert r.setnx("k", "v") is True
        assert r.get("k") is None
        assert r.hset("h", "k", "v") == 1
        assert r.hgetall("h") == {}
        assert r.delete("k") == 1
        assert list(r.scan_iter()) == []
        assert r.expire("k", 10) is True
        assert r.close() is None


class TestStateHelpers:
    """State persistence helpers fall back to no-op when Redis is absent."""

    def test_save_state_no_redis(self):
        m = _celery_app_module()
        with patch.object(m, "get_redis", return_value=m._NullRedis()):
            # Should be a silent no-op, not raise
            m.save_state_to_redis({"job_id": "x", "status": "pending"})

    def test_load_state_no_redis(self):
        m = _celery_app_module()
        with patch.object(m, "get_redis", return_value=m._NullRedis()):
            assert m.load_state_from_redis("x") is None

    def test_list_states_no_redis(self):
        m = _celery_app_module()
        with patch.object(m, "get_redis", return_value=m._NullRedis()):
            assert m.list_states_from_redis() == []

    def test_lock_acquire_no_redis(self):
        m = _celery_app_module()
        with patch.object(m, "get_redis", return_value=m._NullRedis()):
            # Without Redis there is no contention; lock always succeeds
            assert m.acquire_job_lock("any") is True
            m.release_job_lock("any")  # no-op

    def test_save_state_with_fake_redis(self):
        m = _celery_app_module()
        fake = MagicMock()
        fake.hset.return_value = 1
        fake.sadd.return_value = 1
        with patch.object(m, "get_redis", return_value=fake):
            m.save_state_to_redis({
                "job_id": "abc",
                "overall_status": "running",
                "phase_results": {"phase1": {"phase": "phase1_preprocess"}},
            })
        fake.hset.assert_called_once()
        fake.sadd.assert_called_once_with(m._index_key(), "abc")

    def test_load_state_with_fake_redis(self):
        m = _celery_app_module()
        fake = MagicMock()
        fake.hgetall.return_value = {
            "job_id": "abc",
            "overall_status": "running",
            "phase_results": "{}",
        }
        with patch.object(m, "get_redis", return_value=fake):
            data = m.load_state_from_redis("abc")
        assert data["job_id"] == "abc"
        assert data["overall_status"] == "running"

    def test_lock_acquire_with_fake_redis(self):
        m = _celery_app_module()
        fake = MagicMock()
        fake.set.return_value = True
        with patch.object(m, "get_redis", return_value=fake):
            result = m.acquire_job_lock("job-1", ttl_seconds=60)
        assert result is True
        # SETNX via redis-py: set(..., nx=True, ex=...)
        fake.set.assert_called_once_with(
            m._lock_key("job-1"), "1", nx=True, ex=60
        )

    def test_lock_acquire_contended(self):
        m = _celery_app_module()
        fake = MagicMock()
        fake.set.return_value = None  # SETNX returns None when key already exists
        with patch.object(m, "get_redis", return_value=fake):
            assert m.acquire_job_lock("contended") is False


# ============================================================
# Celery task body - invoked directly
# ============================================================

class TestRunPipelineTaskEager:
    """Run the Celery task body in-process by calling .run() directly."""

    def test_task_registered(self):
        m = _celery_app_module()
        assert "pipeline.run" in m.celery_app.tasks

    def test_task_body_completes(self, tmp_path):
        """Invoke the task body; expect success/failed result.  The state
        is persisted to Redis (or silently skipped when no Redis).
        """
        m = _celery_app_module()
        with patch.object(m, "save_state_to_redis") as save:
            result = m.run_pipeline_task.run({
                "job_id": "eager-1",
                "input_video": str(tmp_path / "in.mp4"),
                "style": "wooden",
                "phases": ["phase4_render"],
                "options": {},
            })
        assert result["job_id"] == "eager-1"
        assert result["status"] in {"success", "failed", "skipped"}
        # The body always calls save (it's a no-op when no Redis)
        assert save.called

    def test_task_skipped_when_locked(self, tmp_path):
        m = _celery_app_module()
        with patch.object(m, "acquire_job_lock", return_value=False):
            result = m.run_pipeline_task.run({
                "job_id": "locked-1",
                "input_video": str(tmp_path / "in.mp4"),
                "phases": ["phase4_render"],
            })
        assert result["status"] == "skipped"
        assert result["reason"] == "locked"


# ============================================================
# Orchestrator <-> Celery backend integration (mocked)
# ============================================================

class TestOrchestratorCeleryIntegration:
    """When Celery is disabled (default), the orchestrator uses asyncio."""

    @pytest.mark.asyncio
    async def test_start_job_async_uses_local_when_celery_disabled(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        assert celery_backend.celery_is_enabled() is False

        work_dir = tmp_path / "jobs"
        orch = PipelineOrchestrator(mock_engines, base_work_dir=work_dir)
        job_id = orch.start_job_async(sample_job)
        assert job_id == "test_job_001"
        # Local mode stores the task in _running
        assert "test_job_001" in orch._running
        # task_ids stays empty - no Celery submission happened
        assert "test_job_001" not in orch._task_ids
        # Clean up the task to avoid RuntimeWarning
        task = orch._running.pop("test_job_001")
        task.cancel()
        try:
            await task
        except BaseException:
            pass

    def test_get_state_uses_local_when_celery_disabled(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator

        orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
        orch.create_job(sample_job)
        # With Celery disabled, get_state returns the local copy
        state = orch.get_state("test_job_001")
        assert state is not None
        assert state.job_id == "test_job_001"

    def test_list_jobs_uses_local_when_celery_disabled(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator

        orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
        orch.create_job(sample_job)
        jobs = orch.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_id == "test_job_001"


class TestOrchestratorWithMockedCelery:
    """Force-enable Celery via mocks to verify the integration code path."""

    @pytest.mark.asyncio
    async def test_start_job_async_calls_celery_submit(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        with patch.object(celery_backend, "celery_is_enabled", return_value=True), \
             patch.object(celery_backend, "submit_job", return_value="celery-task-42") as submit:
            orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
            job_id = orch.start_job_async(sample_job)

        assert job_id == "test_job_001"
        submit.assert_called_once()
        # task_id was tracked
        assert orch._task_ids["test_job_001"] == "celery-task-42"
        # No local asyncio task was created
        assert "test_job_001" not in orch._running

    @pytest.mark.asyncio
    async def test_start_job_async_falls_back_when_submit_fails(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        with patch.object(celery_backend, "celery_is_enabled", return_value=True), \
             patch.object(celery_backend, "submit_job", return_value=None):  # submit failed
            orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
            job_id = orch.start_job_async(sample_job)

        assert job_id == "test_job_001"
        # Fell back to local asyncio
        assert "test_job_001" in orch._running
        # Clean up
        task = orch._running.pop("test_job_001")
        task.cancel()
        try:
            await task
        except BaseException:
            pass

    def test_cancel_job_revokes_celery_task(
        self, mock_engines, tmp_path, sample_job
    ):
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        with patch.object(celery_backend, "celery_is_enabled", return_value=True), \
             patch.object(celery_backend, "submit_job", return_value="celery-task-7"), \
             patch.object(celery_backend, "cancel_task", return_value=True) as cancel, \
             patch.object(celery_backend, "delete_state") as delete:
            orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
            orch.start_job_async(sample_job)

            result = orch.cancel_job("test_job_001")
            assert result is True
            cancel.assert_called_once_with("celery-task-7")
            delete.assert_called_once_with("test_job_001")
            assert "test_job_001" not in orch._task_ids

    def test_get_state_uses_celery_when_enabled(self, mock_engines, tmp_path, sample_job):
        from src.models.pipeline import PipelineState, TaskStatus
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        remote_state = PipelineState(
            job_id="test_job_001",
            overall_status=TaskStatus.SUCCESS,
            progress=100.0,
        )
        with patch.object(celery_backend, "celery_is_enabled", return_value=True), \
             patch.object(celery_backend, "hydrate_state", return_value=remote_state) as hydrate:
            orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
            state = orch.get_state("test_job_001")

        hydrate.assert_called_once_with("test_job_001")
        assert state.overall_status == TaskStatus.SUCCESS

    def test_list_jobs_merges_redis_jobs(self, mock_engines, tmp_path, sample_job):
        from src.models.pipeline import PipelineState, TaskStatus
        from src.orchestrator import PipelineOrchestrator
        from src.workers import celery_backend

        redis_state = PipelineState(
            job_id="remote-only",
            overall_status=TaskStatus.SUCCESS,
        )
        with patch.object(celery_backend, "celery_is_enabled", return_value=True), \
             patch.object(celery_backend, "list_known_job_ids", return_value={"remote-only"}), \
             patch.object(celery_backend, "hydrate_state", return_value=redis_state):
            orch = PipelineOrchestrator(mock_engines, base_work_dir=tmp_path / "jobs")
            orch.create_job(sample_job)  # local
            jobs = orch.list_jobs()

        ids = {j.job_id for j in jobs}
        assert "test_job_001" in ids
        assert "remote-only" in ids


# ============================================================
# Backend adapter - state hydration
# ============================================================

class TestBackendAdapter:
    """The backend adapter's state-hydration logic."""

    def test_hydrate_state_returns_none_when_disabled(self):
        from src.workers import celery_backend
        assert celery_backend.hydrate_state("any") is None

    def test_hydrate_state_handles_json_dicts(self):
        from src.models.pipeline import PipelineState, TaskStatus
        from src.workers import celery_backend

        raw = {
            "job_id": "h1",
            "current_phase": None,
            "overall_status": "success",
            "phase_results": {},
            "progress": 100.0,
            "error": None,
            "started_at": "2026-01-01T00:00:00",
            "completed_at": "2026-01-01T00:00:10",
        }
        with patch.object(celery_backend, "is_enabled", return_value=True), \
             patch.object(celery_backend, "_load_state", return_value=raw):
            state = celery_backend.hydrate_state("h1")

        assert isinstance(state, PipelineState)
        assert state.overall_status == TaskStatus.SUCCESS
        assert state.progress == 100.0

    def test_hydrate_state_returns_none_on_validation_error(self):
        from src.workers import celery_backend

        with patch.object(celery_backend, "is_enabled", return_value=True), \
             patch.object(celery_backend, "_load_state", return_value={"bogus": True}):
            # Pydantic will reject unknown-shape data; we should get None
            assert celery_backend.hydrate_state("bad") is None

    def test_persist_state_no_op_when_disabled(self):
        from src.models.pipeline import PipelineState
        from src.workers import celery_backend
        # Should not raise
        celery_backend.persist_state(PipelineState(job_id="x"))

    def test_list_known_job_ids_empty_when_disabled(self):
        from src.workers import celery_backend
        assert celery_backend.list_known_job_ids() == []

    def test_submit_job_delegates_to_celery_app_module(self, sample_job):
        """When Celery is enabled, submit_job must forward the dumped job to
        ``celery_app.submit_pipeline_job`` and return its task id.

        Regression guard: an earlier version referenced an undefined name
        ``celery_module`` here, raising ``NameError`` at call time.
        """
        from src.workers import celery_backend

        with patch.object(celery_backend, "is_enabled", return_value=True), \
             patch.object(
                 celery_backend._celery_app_module,
                 "submit_pipeline_job",
                 return_value="celery-task-99",
             ) as submit:
            result = celery_backend.submit_job(sample_job)

        assert result == "celery-task-99"
        assert submit.call_count == 1
        forwarded = submit.call_args.args[0]
        assert forwarded["job_id"] == "test_job_001"

    def test_submit_job_returns_none_when_disabled(self, sample_job):
        from src.workers import celery_backend
        assert celery_backend.submit_job(sample_job) is None

    def test_cancel_task_delegates_to_celery_app_module(self):
        """When Celery is enabled, cancel_task must forward the revoke call to
        ``celery_app.revoke_pipeline_job`` with ``terminate=True``.

        Regression guard: an earlier version referenced an undefined name
        ``celery_module`` here, raising ``NameError`` at call time.
        """
        from src.workers import celery_backend

        with patch.object(celery_backend, "is_enabled", return_value=True), \
             patch.object(
                 celery_backend._celery_app_module,
                 "revoke_pipeline_job",
                 return_value=True,
             ) as revoke:
            result = celery_backend.cancel_task("celery-task-7")

        assert result is True
        revoke.assert_called_once_with("celery-task-7", terminate=True)

    def test_cancel_task_returns_false_when_no_task_id(self):
        from src.workers import celery_backend
        with patch.object(celery_backend, "is_enabled", return_value=True):
            assert celery_backend.cancel_task(None) is False
            assert celery_backend.cancel_task("") is False


# ============================================================
# Fixtures shared with the rest of the test suite
# ============================================================

@pytest.fixture
def mock_engines():
    from tests.test_orchestrator import MockEngine
    return {
        "ffmpeg": MockEngine("ffmpeg"),
        "ae": MockEngine("ae"),
        "topaz": MockEngine("topaz"),
        "silhouette": MockEngine("silhouette"),
        "blender": MockEngine("blender"),
        "davinci": MockEngine("davinci"),
    }


@pytest.fixture
def sample_job(tmp_path):
    from src.models.pipeline import PipelineJob, PuppetStyle
    return PipelineJob(
        job_id="test_job_001",
        input_video=str(tmp_path / "in.mp4"),
        style=PuppetStyle.WOODEN,
        enable_face_puppet=False,
        enable_body_puppet=False,
        enable_audio=False,
        enable_3d_stage=False,
    )
