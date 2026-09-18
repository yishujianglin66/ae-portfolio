"""
software_sdk/types.py - 核心类型定义

定义软件 SDK 使用的所有枚举和数据类。
从 multi_software_bridge.py 提取并精简。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ============================================================================
# 枚举类型
# ============================================================================

class SoftwareType(Enum):
    """所有支持的创意软件类型枚举"""
    AFTER_EFFECTS = "after_effects"
    PREMIERE_PRO = "premiere_pro"
    PHOTOSHOP = "photoshop"
    DAVINCI_RESOLVE = "davinci_resolve"
    BLENDER = "blender"
    TOPAZ_VIDEO_AI = "topaz_video_ai"
    FFMPEG = "ffmpeg"
    RUNWAYML = "runwayml"
    PIKA = "pika"
    MEDIA_ENCODER = "media_encoder"
    ILLUSTRATOR = "illustrator"
    SILHOUETTE = "silhouette"


class ConnectionStatus(Enum):
    """软件连接状态"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TIMEOUT = "timeout"


class TaskStatus(Enum):
    """任务执行状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class SoftwareCapability(Enum):
    """软件能力类型"""
    TEXT_ANIMATION = "text_animation"
    TRANSITIONS = "transitions"
    FILTERS_EFFECTS = "filters_effects"
    RENDERING = "rendering"
    COMPOSITING = "compositing"
    COLOR_GRADING = "color_grading"
    EDITING = "editing"
    THREE_D = "3d"
    PARTICLES = "particles"
    MOTION_TRACKING = "motion_tracking"
    KEYING = "keying"
    ROTOSCOPING = "rotoscoping"
    PAINTING = "painting"
    IMAGE_MANIPULATION = "image_manipulation"
    VIDEO_ENCODING = "video_encoding"
    AUDIO_PROCESSING = "audio_processing"
    AI_GENERATION = "ai_generation"
    UPSCALING = "upscaling"
    STABILIZATION = "stabilization"
    DENOSING = "denoising"
    INTERPOLATION = "interpolation"
    VECTOR_GRAPHICS = "vector_graphics"
    PROJECT_MANAGEMENT = "project_management"
    BATCH_PROCESSING = "batch_processing"
    SCRIPTING = "scripting"


class FallbackStrategyType(Enum):
    """回退策略类型"""
    NONE = "none"
    NEXT_SOFTWARE = "next_software"
    SIMPLIFY_TASK = "simplify_task"
    RETRY = "retry"
    SKIP = "skip"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class SoftwareStatus:
    """软件状态信息"""
    software: SoftwareType
    status: ConnectionStatus
    version: str | None = None
    last_heartbeat: datetime | None = None
    error_message: str | None = None
    cpu_usage: float = 0.0
    gpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_tasks: int = 0
    max_tasks: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "software": self.software.value,
            "status": self.status.value,
            "version": self.version,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "error_message": self.error_message,
            "cpu_usage": self.cpu_usage,
            "gpu_usage": self.gpu_usage,
            "memory_usage": self.memory_usage,
            "active_tasks": self.active_tasks,
            "max_tasks": self.max_tasks,
        }


@dataclass
class SoftwareCapabilities:
    """软件能力描述"""
    software: SoftwareType
    capabilities: set[SoftwareCapability] = field(default_factory=set)
    supported_formats_input: set[str] = field(default_factory=set)
    supported_formats_output: set[str] = field(default_factory=set)
    max_resolution: tuple[int, int] = (3840, 2160)
    max_framerate: float = 60.0
    gpu_accelerated: bool = False
    scriptable: bool = False

    def has_capability(self, capability: SoftwareCapability) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        return {
            "software": self.software.value,
            "capabilities": [c.value for c in self.capabilities],
            "supported_formats_input": list(self.supported_formats_input),
            "supported_formats_output": list(self.supported_formats_output),
            "max_resolution": list(self.max_resolution),
            "max_framerate": self.max_framerate,
            "gpu_accelerated": self.gpu_accelerated,
            "scriptable": self.scriptable,
        }


@dataclass
class Task:
    """任务数据类"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "generic"
    target_software: SoftwareType | None = None
    params: dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Any | None = None
    error: str | None = None
    callback: Callable[["Task"], None] | None = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    dependencies: list[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    progress: float = 0.0
    software_used: SoftwareType | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: "Task") -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority.value > other.priority.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "target_software": self.target_software.value if self.target_software else None,
            "params": self.params,
            "priority": self.priority.value,
            "status": self.status.value,
            "result": str(self.result) if self.result else None,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "dependencies": self.dependencies,
            "retry_count": self.retry_count,
            "progress": self.progress,
            "software_used": self.software_used.value if self.software_used else None,
            "metadata": self.metadata,
        }


@dataclass
class SoftwareConfig:
    """软件配置"""
    software: SoftwareType
    enabled: bool = True
    executable_path: str | None = None
    install_dir: str | None = None
    version: str | None = None
    api_endpoint: str | None = None
    api_key: str | None = None
    max_concurrent_tasks: int = 1
    priority_weight: float = 1.0
    license_key: str | None = None
    additional_settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "software": self.software.value,
            "enabled": self.enabled,
            "executable_path": self.executable_path,
            "install_dir": self.install_dir,
            "version": self.version,
            "api_endpoint": self.api_endpoint,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "priority_weight": self.priority_weight,
            "additional_settings": self.additional_settings,
        }
