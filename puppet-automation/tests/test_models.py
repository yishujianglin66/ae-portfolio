"""Tests for data models and enums."""
from __future__ import annotations

import pytest
from datetime import datetime

from src.models.pipeline import (
    AudioAnalysis,
    DetectionResult,
    FaceAnalysisResult,
    MattingResult,
    MCPEngineRequest,
    MCPEngineResponse,
    PhaseResult,
    PipelineJob,
    PipelinePhase,
    PipelineState,
    PoseFrame,
    PuppetStyle,
    SceneSegment,
    TaskStatus,
    VideoMetadata,
)


class TestEnums:
    """Test enum classes."""

    def test_pipeline_phase_values(self):
        assert PipelinePhase.PHASE1_PREPROCESS == "phase1_preprocess"
        assert PipelinePhase.PHASE2_KEYING == "phase2_keying"
        assert PipelinePhase.PHASE3_STYLIZE == "phase3_stylize"
        assert PipelinePhase.PHASE4_RENDER == "phase4_render"
        assert len(PipelinePhase) == 4

    def test_task_status_values(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCESS == "success"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.SKIPPED == "skipped"

    def test_puppet_style_values(self):
        styles = list(PuppetStyle)
        assert len(styles) >= 6
        assert PuppetStyle.WOODEN == "wooden"
        assert PuppetStyle.STOP_MOTION == "stop_motion"


class TestVideoMetadata:
    """Test VideoMetadata model."""

    def test_create_metadata(self):
        m = VideoMetadata(
            width=1920,
            height=1080,
            fps=30.0,
            duration=10.5,
            codec="h264",
            bitrate=5000000,
            has_audio=True,
            audio_codec="aac",
            file_size=1024000,
            path="/tmp/test.mp4",
        )
        assert m.width == 1920
        assert m.height == 1080
        assert m.fps == 30.0
        assert m.has_audio is True
        assert m.file_size == 1024000

    def test_metadata_no_audio(self):
        m = VideoMetadata(
            width=1280,
            height=720,
            fps=24.0,
            duration=5.0,
            codec="h264",
            bitrate=2000000,
            has_audio=False,
            file_size=512000,
            path="/tmp/test2.mp4",
        )
        assert m.audio_codec is None
        assert m.has_audio is False


class TestSceneSegment:
    """Test SceneSegment model."""

    def test_create_segment(self):
        s = SceneSegment(
            scene_id=0,
            start_frame=0,
            end_frame=300,
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            avg_motion=0.5,
        )
        assert s.scene_id == 0
        assert s.duration == 10.0
        assert s.avg_motion == 0.5
        assert s.keyframe_path is None


class TestPipelineJob:
    """Test PipelineJob model."""

    def test_default_values(self):
        job = PipelineJob(
            job_id="test1",
            input_video="/tmp/in.mp4",
        )
        assert job.style == PuppetStyle.WOODEN
        assert job.target_resolution == (1920, 1080)
        assert job.target_fps == 30.0
        assert job.enable_audio is True
        assert job.enable_face_puppet is True
        assert len(job.phases) == 4

    def test_custom_phases(self):
        job = PipelineJob(
            job_id="test2",
            input_video="/tmp/in.mp4",
            phases=[PipelinePhase.PHASE1_PREPROCESS, PipelinePhase.PHASE4_RENDER],
        )
        assert len(job.phases) == 2
        assert job.phases[0] == PipelinePhase.PHASE1_PREPROCESS

    def test_all_puppet_styles(self):
        for style in PuppetStyle:
            job = PipelineJob(
                job_id=f"test_{style.value}",
                input_video="/tmp/in.mp4",
                style=style,
            )
            assert job.style == style


class TestPhaseResult:
    """Test PhaseResult model."""

    def test_default_status(self):
        pr = PhaseResult(phase=PipelinePhase.PHASE1_PREPROCESS)
        assert pr.status == TaskStatus.PENDING
        assert pr.started_at is None
        assert pr.error is None
        assert pr.metadata == {}

    def test_completed_result(self):
        pr = PhaseResult(
            phase=PipelinePhase.PHASE2_KEYING,
            status=TaskStatus.SUCCESS,
            output_path="/tmp/out.mov",
            metadata={"quality": 0.9},
        )
        assert pr.status == TaskStatus.SUCCESS
        assert pr.output_path == "/tmp/out.mov"
        assert pr.metadata["quality"] == 0.9


class TestPipelineState:
    """Test PipelineState model."""

    def test_default_state(self):
        state = PipelineState(job_id="test1")
        assert state.overall_status == TaskStatus.PENDING
        assert state.current_phase is None
        assert state.progress == 0.0
        assert state.phase_results == {}

    def test_state_with_phase_results(self):
        phase_result = PhaseResult(
            phase=PipelinePhase.PHASE1_PREPROCESS,
            status=TaskStatus.SUCCESS,
        )
        state = PipelineState(
            job_id="test2",
            overall_status=TaskStatus.RUNNING,
            current_phase=PipelinePhase.PHASE2_KEYING,
            phase_results={PipelinePhase.PHASE1_PREPROCESS: phase_result},
            progress=25.0,
        )
        assert state.progress == 25.0
        assert PipelinePhase.PHASE1_PREPROCESS in state.phase_results


class TestMCPModels:
    """Test MCP request/response models."""

    def test_mcp_request(self):
        from src.models.pipeline import EngineName
        req = MCPEngineRequest(
            engine=EngineName.FFMPEG,
            action="convert",
            params={"input_path": "/tmp/in.mp4", "output_path": "/tmp/out.mp4"},
        )
        assert req.engine == EngineName.FFMPEG
        assert req.action == "convert"
        assert req.timeout == 3600

    def test_mcp_response_success(self):
        resp = MCPEngineResponse(
            success=True,
            output_path="/tmp/out.mp4",
            metadata={"codec": "h264"},
            duration_seconds=5.5,
        )
        assert resp.success is True
        assert resp.error is None
        assert resp.duration_seconds == 5.5

    def test_mcp_response_failure(self):
        resp = MCPEngineResponse(
            success=False,
            error="Something went wrong",
        )
        assert resp.success is False
        assert resp.error == "Something went wrong"
        assert resp.output_path is None
