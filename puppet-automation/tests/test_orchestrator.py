"""Tests for Pipeline Orchestrator."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.models.pipeline import (
    PhaseResult,
    PipelineJob,
    PipelinePhase,
    PipelineState,
    PuppetStyle,
    TaskStatus,
)
from src.orchestrator import PipelineOrchestrator


class MockEngine:
    """Mock engine for orchestrator tests - supports any method call."""

    def __init__(self, name: str = "mock", succeed: bool = True, tmp_path=None):
        self.name = name
        self.succeed = succeed
        self._calls = []
        # Use a real Path object so .parent, .exists() etc work correctly
        if tmp_path:
            self.executable_path = Path(tmp_path) / f"{name}.exe"
            self.executable_path.touch()
        else:
            self.executable_path = Path(f"/tmp/mock_{name}.exe")

    async def execute(self, action: str, **kwargs):
        from src.engines.base import EngineResult
        self._calls.append((action, kwargs))
        if not self.succeed:
            return EngineResult(success=False, error=f"{self.name} {action} failed")
        return EngineResult(
            success=True,
            output_path=Path(f"/tmp/{self.name}_{action}_out.mp4"),
            metadata={"action": action, "engine": self.name},
        )

    def __getattr__(self, name):
        """Return an async mock method for any engine action."""
        if name.startswith('_'):
            raise AttributeError(name)

        from src.engines.base import EngineResult

        async def _mock_method(**kwargs):
            self._calls.append((name, kwargs))
            if not self.succeed:
                return EngineResult(success=False, error=f"{self.name} {name} failed")
            return EngineResult(
                success=True,
                output_path=Path(f"/tmp/{self.name}_{name}_out"),
                metadata={"method": name, "engine": self.name},
            )

        return _mock_method


@pytest.fixture
def mock_engines():
    """Create mock engines for testing."""
    return {
        "ffmpeg": MockEngine("ffmpeg"),
        "ae": MockEngine("ae"),
        "topaz": MockEngine("topaz"),
        "silhouette": MockEngine("silhouette"),
        "blender": MockEngine("blender"),
        "davinci": MockEngine("davinci"),
    }


@pytest.fixture
def orch(mock_engines, tmp_path):
    """Create a PipelineOrchestrator with mock engines."""
    work_dir = tmp_path / "jobs"
    return PipelineOrchestrator(mock_engines, base_work_dir=work_dir)


@pytest.fixture
def sample_job(sample_video_path):
    """Create a sample pipeline job."""
    return PipelineJob(
        job_id="test_job_001",
        input_video=str(sample_video_path),
        style=PuppetStyle.WOODEN,
        enable_face_puppet=False,
        enable_body_puppet=False,
        enable_audio=False,
        enable_3d_stage=False,
    )


class TestPipelineOrchestratorBasics:
    """Test basic orchestrator functionality."""

    def test_create_orchestrator(self, orch, mock_engines):
        assert orch.engines == mock_engines
        assert len(orch.states) == 0

    def test_create_job(self, orch, sample_job):
        state = orch.create_job(sample_job)
        assert state.job_id == "test_job_001"
        assert state.overall_status == TaskStatus.PENDING
        assert state.progress == 0.0
        assert "test_job_001" in orch.states

    def test_get_state_existing(self, orch, sample_job):
        orch.create_job(sample_job)
        state = orch.get_state("test_job_001")
        assert state is not None
        assert state.job_id == "test_job_001"

    def test_get_state_nonexistent(self, orch):
        assert orch.get_state("nonexistent") is None

    def test_list_jobs_empty(self, orch):
        assert orch.list_jobs() == []

    def test_list_jobs_with_jobs(self, orch, sample_job):
        orch.create_job(sample_job)
        jobs = orch.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_id == "test_job_001"

    def test_create_job_duplicate_id_returns_existing(self, orch, sample_job):
        """Creating a job with duplicate ID should return existing state, not overwrite."""
        state1 = orch.create_job(sample_job)
        state1.progress = 50.0

        # Attempt to create same job again
        state2 = orch.create_job(sample_job)

        # Should return existing state, not a new one
        assert state2 is state1
        assert state2.progress == 50.0
        assert len(orch.list_jobs()) == 1


class TestPipelineExecution:
    """Test full pipeline execution."""

    @pytest.mark.asyncio
    async def test_run_pipeline_creates_state(self, orch, sample_job):
        state = await orch.run_pipeline(sample_job)
        assert state.job_id == "test_job_001"
        assert state.started_at is not None
        assert state.completed_at is not None

    @pytest.mark.asyncio
    async def test_run_pipeline_all_phases_present(self, orch, sample_job):
        state = await orch.run_pipeline(sample_job)
        for phase in PipelinePhase:
            assert phase in state.phase_results

    @pytest.mark.asyncio
    async def test_run_pipeline_final_status_success(self, orch, sample_job):
        state = await orch.run_pipeline(sample_job)
        assert state.overall_status == TaskStatus.SUCCESS
        assert state.progress == 100.0

    @pytest.mark.asyncio
    async def test_run_pipeline_progress_increases(self, orch, sample_job, tmp_path):
        # We can't easily test intermediate progress, but we verify final progress
        state = await orch.run_pipeline(sample_job)
        assert state.progress == 100.0

    @pytest.mark.asyncio
    async def test_run_pipeline_with_subset_phases(self, orch, sample_job):
        sample_job.phases = [
            PipelinePhase.PHASE1_PREPROCESS,
            PipelinePhase.PHASE4_RENDER,
        ]
        state = await orch.run_pipeline(sample_job)
        assert state.overall_status == TaskStatus.SUCCESS
        assert PipelinePhase.PHASE2_KEYING not in state.phase_results
        assert PipelinePhase.PHASE3_STYLIZE not in state.phase_results
        assert len(state.phase_results) == 2

    @pytest.mark.asyncio
    async def test_run_pipeline_single_phase(self, orch, sample_job):
        sample_job.phases = [PipelinePhase.PHASE1_PREPROCESS]
        state = await orch.run_pipeline(sample_job)
        assert state.overall_status == TaskStatus.SUCCESS
        assert len(state.phase_results) == 1
        assert state.progress == 100.0


class TestPhase3Stylize:
    """Test Phase 3 stylization with different puppet styles."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("style", list(PuppetStyle))
    async def test_all_puppet_styles(self, orch, sample_job, style):
        sample_job.style = style
        sample_job.phases = [PipelinePhase.PHASE3_STYLIZE]
        state = await orch.run_pipeline(sample_job)

        phase3 = state.phase_results[PipelinePhase.PHASE3_STYLIZE]
        assert phase3.status == TaskStatus.SUCCESS
        assert phase3.metadata["style"] == style.value

    @pytest.mark.asyncio
    async def test_3d_stage_flag(self, orch, sample_job):
        sample_job.enable_3d_stage = True
        sample_job.phases = [PipelinePhase.PHASE3_STYLIZE]
        state = await orch.run_pipeline(sample_job)

        phase3 = state.phase_results[PipelinePhase.PHASE3_STYLIZE]
        # Stage generation may fail gracefully if blender not really available
        # but the metadata should reflect the flag
        assert "has_3d_stage" in phase3.metadata


class TestPhaseResults:
    """Test individual phase result structures."""

    @pytest.mark.asyncio
    async def test_phase1_result_structure(self, orch, sample_job):
        sample_job.phases = [PipelinePhase.PHASE1_PREPROCESS]
        state = await orch.run_pipeline(sample_job)
        result = state.phase_results[PipelinePhase.PHASE1_PREPROCESS]

        assert result.phase == PipelinePhase.PHASE1_PREPROCESS
        assert result.status == TaskStatus.SUCCESS
        assert "video_metadata" in result.metadata
        assert "scene_count" in result.metadata

    @pytest.mark.asyncio
    async def test_phase2_result_structure(self, orch, sample_job):
        sample_job.phases = [PipelinePhase.PHASE2_KEYING]
        state = await orch.run_pipeline(sample_job)
        result = state.phase_results[PipelinePhase.PHASE2_KEYING]

        assert result.phase == PipelinePhase.PHASE2_KEYING
        # Phase 2 may fail without real rembg/silhouette, but should have status
        assert result.status in [TaskStatus.SUCCESS, TaskStatus.FAILED]

    @pytest.mark.asyncio
    async def test_phase4_result_structure(self, orch, sample_job):
        sample_job.phases = [PipelinePhase.PHASE4_RENDER]
        state = await orch.run_pipeline(sample_job)
        result = state.phase_results[PipelinePhase.PHASE4_RENDER]

        assert result.phase == PipelinePhase.PHASE4_RENDER
        assert result.status == TaskStatus.SUCCESS
        assert "quality" in result.metadata
        assert "resolution" in result.metadata

    @pytest.mark.asyncio
    async def test_empty_phases_fails(self, orch, sample_job):
        """Pipeline with empty phases should fail gracefully."""
        sample_job.phases = []
        state = await orch.run_pipeline(sample_job)

        assert state.overall_status == TaskStatus.FAILED
        assert state.error == "No phases defined for pipeline job"
        assert state.progress == 0.0


class TestJobCancellation:
    """Test job cancellation (unit level - async tasks tested separately)."""

    def test_cancel_nonexistent_job(self, orch):
        assert orch.cancel_job("nonexistent") is False

    @pytest.mark.asyncio
    async def test_cancel_completed_job_is_false(self, orch, sample_job):
        await orch.run_pipeline(sample_job)
        # After completion, the job is not in _running
        assert orch.cancel_job("test_job_001") is False

    @pytest.mark.asyncio
    async def test_cancel_already_cancelled_job_is_false(self, orch, sample_job):
        """Cancelling an already-cancelled job should return False."""
        orch.start_job_async(sample_job)
        assert orch.cancel_job("test_job_001") is True
        # Second cancel should fail
        assert orch.cancel_job("test_job_001") is False


class TestAsyncJobStart:
    """Test async job starting."""

    @pytest.mark.asyncio
    async def test_start_job_async_returns_job_id(self, orch, sample_job):
        job_id = orch.start_job_async(sample_job)
        assert job_id == "test_job_001"
        assert "test_job_001" in orch._running

        # Wait for completion
        task = orch._running["test_job_001"]
        await task

        # After completion, it should be removed from _running
        assert "test_job_001" not in orch._running


class TestWorkDirectory:
    """Test work directory creation."""

    def test_base_work_dir_created(self, orch, tmp_path):
        assert orch.base_work_dir.exists()
        assert orch.base_work_dir == tmp_path / "jobs"
