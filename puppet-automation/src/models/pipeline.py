"""Data models for puppet automation pipeline."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

# ============================================================
# Enums
# ============================================================

class PipelinePhase(str, Enum):
    """Pipeline phase identifiers."""
    PHASE1_PREPROCESS = "phase1_preprocess"
    PHASE2_KEYING = "phase2_keying"
    PHASE3_STYLIZE = "phase3_stylize"
    PHASE4_RENDER = "phase4_render"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class PuppetStyle(str, Enum):
    """Available puppet visual styles."""
    WOODEN = "wooden"
    STOP_MOTION = "stop_motion"
    MINIATURE = "miniature"
    CLAY = "clay"
    SHADOW = "shadow"
    PAPER = "paper"
    VOXEL = "voxel"
    HANDLE = "handle"


class EngineName(str, Enum):
    """Supported engine names."""
    FFMPEG = "ffmpeg"
    AE = "ae"
    TOPAZ = "topaz"
    SILHOUETTE = "silhouette"
    BLENDER = "blender"
    DAVINCI = "davinci"
    NEXRENDER = "nexrender"
    COMFYUI = "comfyui"


# ============================================================
# Core Data Models
# ============================================================

class VideoMetadata(BaseModel):
    """Video file metadata."""
    width: int
    height: int
    fps: float
    duration: float
    codec: str
    bitrate: int
    has_audio: bool
    audio_codec: str | None = None
    file_size: int
    path: str


class SceneSegment(BaseModel):
    """Detected scene segment."""
    scene_id: int
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    duration: float
    avg_motion: float = 0.0
    keyframe_path: str | None = None


class DetectionResult(BaseModel):
    """Object detection result per frame."""
    frame_idx: int
    detections: list[dict[str, Any]] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    confidences: list[float] = Field(default_factory=list)
    boxes: list[list[float]] = Field(default_factory=list)


class PoseFrame(BaseModel):
    """Pose estimation frame data."""
    frame_idx: int
    landmarks_2d: list[list[float]] = Field(default_factory=list)
    landmarks_3d: list[list[float]] | None = None
    confidence: list[float] = Field(default_factory=list)


class FaceAnalysisResult(BaseModel):
    """Face analysis result."""
    frame_idx: int
    face_count: int
    bounding_boxes: list[list[float]] = Field(default_factory=list)
    landmarks: list[list[list[float]]] = Field(default_factory=list)
    expressions: list[dict[str, float]] = Field(default_factory=list)
    head_poses: list[dict[str, float]] = Field(default_factory=list)


class MattingResult(BaseModel):
    """Matting/keying result."""
    method: str
    alpha_path: str | None = None
    fg_path: str | None = None
    quality_score: float = 0.0
    processing_time: float = 0.0


class TrackData(BaseModel):
    """Tracking data structure."""
    track_id: int
    track_type: str = "point"
    points: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0


class AudioAnalysis(BaseModel):
    """Audio analysis result."""
    duration: float
    sample_rate: int
    bpm: float = 0.0
    beats: list[float] = Field(default_factory=list)
    onsets: list[float] = Field(default_factory=list)
    energy: list[float] = Field(default_factory=list)
    mfcc_mean: list[float] = Field(default_factory=list)
    spectral_centroid_mean: float = 0.0


class ASRResult(BaseModel):
    """Automatic speech recognition result."""
    text: str
    segments: list[dict[str, Any]] = Field(default_factory=list)
    language: str = "zh-CN"
    duration: float = 0.0


# ============================================================
# Pipeline Models
# ============================================================

class PhaseResult(BaseModel):
    """Result of a single pipeline phase."""
    phase: PipelinePhase
    status: TaskStatus = TaskStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None
    output_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: float = 0.0


class PipelineJob(BaseModel):
    """Full pipeline job definition."""
    job_id: str
    input_video: str
    style: PuppetStyle = PuppetStyle.WOODEN
    target_resolution: tuple[int, int] = (1920, 1080)
    target_fps: float = 30.0
    enable_audio: bool = True
    enable_face_puppet: bool = True
    enable_body_puppet: bool = True
    enable_3d_stage: bool = False
    quality_preset: str = "high"
    phases: list[PipelinePhase] = Field(
        default_factory=lambda: [
            PipelinePhase.PHASE1_PREPROCESS,
            PipelinePhase.PHASE2_KEYING,
            PipelinePhase.PHASE3_STYLIZE,
            PipelinePhase.PHASE4_RENDER,
        ]
    )
    options: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class PipelineState(BaseModel):
    """Current state of a pipeline job."""
    job_id: str
    current_phase: PipelinePhase | None = None
    overall_status: TaskStatus = TaskStatus.PENDING
    phase_results: dict[PipelinePhase, PhaseResult] = Field(default_factory=dict)
    progress: float = 0.0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


# ============================================================
# MCP Models
# ============================================================

class MCPEngineRequest(BaseModel):
    """MCP engine action request."""
    engine: EngineName
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 3600


class MCPEngineResponse(BaseModel):
    """MCP engine action response."""
    success: bool
    output_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
