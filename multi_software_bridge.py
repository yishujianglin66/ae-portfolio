"""
Multi-Software Bridge - DEPRECATED - Use software_sdk instead
=============================================================

.. deprecated::
    This module is deprecated. Use ``software_sdk`` package instead:
    - ``software_sdk.SoftwareRegistry`` for adapter management
    - ``software_sdk.adapters.*`` for individual software adapters
    - ``software_sdk.types`` for type definitions

This module is kept for backward compatibility only.
All new code should import from ``software_sdk``.

Original description:
提供统一的API层，连接和编排 After Effects, Premiere Pro, Photoshop,
DaVinci Resolve, Blender, Topaz Video AI, FFmpeg, RunwayML/Pika, Media Encoder 等软件。
"""

from __future__ import annotations

import os
import sys
import json
import time
import uuid
import logging
import threading
import subprocess
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any, Callable, Dict, List, Optional, Tuple, Union,
    TypeVar, Generic, Set, Type, Sequence
)
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from queue import PriorityQueue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from abc import ABC, abstractmethod
from collections import defaultdict, deque


# ============================================================================
# 1. CORE ARCHITECTURE - Enums, Status, Capabilities
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
# Data Classes
# ============================================================================

@dataclass
class SoftwareStatus:
    """软件状态信息"""
    software: SoftwareType
    status: ConnectionStatus
    version: Optional[str] = None
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None
    cpu_usage: float = 0.0
    gpu_usage: float = 0.0
    memory_usage: float = 0.0
    active_tasks: int = 0
    max_tasks: int = 1

    def to_dict(self) -> Dict[str, Any]:
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
    capabilities: Set[SoftwareCapability] = field(default_factory=set)
    supported_formats_input: Set[str] = field(default_factory=set)
    supported_formats_output: Set[str] = field(default_factory=set)
    max_resolution: Tuple[int, int] = (3840, 2160)
    max_framerate: float = 60.0
    gpu_accelerated: bool = False
    scriptable: bool = False

    def has_capability(self, capability: SoftwareCapability) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
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
    target_software: Optional[SoftwareType] = None
    params: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    callback: Optional[Callable[[Task], None]] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    progress: float = 0.0
    software_used: Optional[SoftwareType] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __lt__(self, other: Task) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return self.priority.value > other.priority.value

    def to_dict(self) -> Dict[str, Any]:
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
    executable_path: Optional[str] = None
    install_dir: Optional[str] = None
    version: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    max_concurrent_tasks: int = 1
    priority_weight: float = 1.0
    license_key: Optional[str] = None
    additional_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    task_type: str = ""
    software: Optional[SoftwareType] = None
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: int = 3600
    required: bool = True
    fallback_strategy: FallbackStrategyType = FallbackStrategyType.NEXT_SOFTWARE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "name": self.name,
            "task_type": self.task_type,
            "software": self.software.value if self.software else None,
            "params": self.params,
            "depends_on": self.depends_on,
            "timeout_seconds": self.timeout_seconds,
            "required": self.required,
            "fallback_strategy": self.fallback_strategy.value,
        }


@dataclass
class Workflow:
    """工作流定义"""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "tags": self.tags,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class PerformanceMetrics:
    """性能指标"""
    total_tasks_executed: int = 0
    total_tasks_failed: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    tasks_by_software: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    success_rate: float = 0.0
    throughput_tasks_per_hour: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)

    def record_task(self, software: SoftwareType, duration: float, success: bool) -> None:
        self.total_tasks_executed += 1
        if not success:
            self.total_tasks_failed += 1
        self.total_execution_time += duration
        self.tasks_by_software[software.value] += 1
        self.average_execution_time = (
            self.total_execution_time / self.total_tasks_executed
        )
        total_elapsed = (datetime.now() - self.start_time).total_seconds()
        if total_elapsed > 0:
            self.throughput_tasks_per_hour = (
                self.total_tasks_executed / (total_elapsed / 3600)
            )
        if self.total_tasks_executed > 0:
            self.success_rate = (
                (self.total_tasks_executed - self.total_tasks_failed)
                / self.total_tasks_executed
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks_executed": self.total_tasks_executed,
            "total_tasks_failed": self.total_tasks_failed,
            "average_execution_time": self.average_execution_time,
            "total_execution_time": self.total_execution_time,
            "tasks_by_software": dict(self.tasks_by_software),
            "success_rate": self.success_rate,
            "throughput_tasks_per_hour": self.throughput_tasks_per_hour,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
        }


# ============================================================================
# 2. SOFTWARE ADAPTERS - Base class and all specific adapters
# ============================================================================

class BaseSoftwareAdapter(ABC):
    """软件适配器基类 - 定义所有软件适配器的统一接口"""

    def __init__(self, config: SoftwareConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.software_type = config.software
        self._status = ConnectionStatus.DISCONNECTED
        self._capabilities = self._initialize_capabilities()
        self._active_tasks: int = 0
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None
        self.logger = logger or logging.getLogger(f"bridge.{self.software_type.value}")

    @abstractmethod
    def _initialize_capabilities(self) -> SoftwareCapabilities:
        """初始化软件能力列表"""
        ...

    @abstractmethod
    def connect(self) -> bool:
        """建立与软件的连接"""
        ...

    @abstractmethod
    def disconnect(self) -> bool:
        """断开与软件的连接"""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """检查软件健康状态"""
        ...

    @abstractmethod
    def execute_task(self, task: Task) -> Any:
        """执行任务 - 子类必须实现"""
        ...

    def get_capabilities(self) -> SoftwareCapabilities:
        """获取软件能力"""
        return self._capabilities

    def get_status(self) -> SoftwareStatus:
        """获取软件状态"""
        return SoftwareStatus(
            software=self.software_type,
            status=self._status,
            version=self.config.version,
            last_heartbeat=datetime.now(),
            error_message=self._last_error,
            active_tasks=self._active_tasks,
            max_tasks=self.config.max_concurrent_tasks,
        )

    def can_accept_task(self) -> bool:
        """检查是否可以接受新任务"""
        with self._lock:
            return (
                self._status == ConnectionStatus.CONNECTED
                and self._active_tasks < self.config.max_concurrent_tasks
            )

    def _mark_task_start(self) -> None:
        with self._lock:
            self._active_tasks += 1

    def _mark_task_end(self) -> None:
        with self._lock:
            self._active_tasks = max(0, self._active_tasks - 1)

    def _set_error(self, error_msg: str) -> None:
        self._last_error = error_msg
        self._status = ConnectionStatus.ERROR
        self.logger.error(f"{self.software_type.value} error: {error_msg}")

    def _set_connected(self) -> None:
        self._status = ConnectionStatus.CONNECTED
        self._last_error = None


class AfterEffectsAdapter(BaseSoftwareAdapter):
    """After Effects 适配器 - 通过 MCP Bridge / JSX 文件交换"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.AFTER_EFFECTS,
            capabilities={
                SoftwareCapability.TEXT_ANIMATION,
                SoftwareCapability.TRANSITIONS,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.RENDERING,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.MOTION_TRACKING,
                SoftwareCapability.KEYING,
                SoftwareCapability.PARTICLES,
                SoftwareCapability.PROJECT_MANAGEMENT,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".aep", ".mov", ".mp4", ".avi", ".png", ".jpg",
                ".jpeg", ".tiff", ".tga", ".wav", ".aiff", ".mp3"
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".png", ".jpg", ".tiff",
                ".tga", ".gif", ".webm", ".wav"
            },
            max_resolution=(30000, 30000),
            max_framerate=99.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to After Effects...")
            self._status = ConnectionStatus.CONNECTING
            jsx_path = self.config.additional_settings.get("jsx_watch_folder")
            if jsx_path and not os.path.exists(jsx_path):
                os.makedirs(jsx_path, exist_ok=True)
            self._set_connected()
            self.logger.info("After Effects connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        try:
            self._status = ConnectionStatus.DISCONNECTED
            self.logger.info("After Effects disconnected")
            return True
        except Exception as e:
            self._set_error(f"Disconnect failed: {str(e)}")
            return False

    def health_check(self) -> bool:
        if self._status != ConnectionStatus.CONNECTED:
            return False
        return True

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = self._dispatch_task(task)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            raise
        finally:
            self._mark_task_end()

    def _dispatch_task(self, task: Task) -> Any:
        task_type = task.task_type
        handlers = {
            "import_asset": self._handle_import,
            "export": self._handle_export,
            "text_animation": self._handle_text_animation,
            "apply_effect": self._handle_apply_effect,
            "render": self._handle_render,
            "create_composition": self._handle_create_composition,
            "add_layer": self._handle_add_layer,
        }
        handler = handlers.get(task_type, self._handle_generic)
        return handler(task.params)

    def _handle_import(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path", "")
        self.logger.info(f"AE: Importing {file_path}")
        return {"imported": True, "file": file_path, "item_id": str(uuid.uuid4())}

    def _handle_export(self, params: Dict[str, Any]) -> Dict[str, Any]:
        comp_name = params.get("comp_name", "output")
        output_path = params.get("output_path", "./output.mov")
        self.logger.info(f"AE: Exporting comp '{comp_name}' to {output_path}")
        return {"exported": True, "output_path": output_path}

    def _handle_text_animation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        self.logger.info(f"AE: Creating text animation: {text[:30]}...")
        return {"created": True, "text": text, "layer_id": str(uuid.uuid4())}

    def _handle_apply_effect(self, params: Dict[str, Any]) -> Dict[str, Any]:
        effect_name = params.get("effect_name", "")
        self.logger.info(f"AE: Applying effect '{effect_name}'")
        return {"applied": True, "effect": effect_name}

    def _handle_render(self, params: Dict[str, Any]) -> Dict[str, Any]:
        comp_name = params.get("comp_name", "")
        self.logger.info(f"AE: Rendering comp '{comp_name}'")
        return {"rendered": True, "comp": comp_name}

    def _handle_create_composition(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name", "Comp 1")
        width = params.get("width", 1920)
        height = params.get("height", 1080)
        duration = params.get("duration", 10)
        self.logger.info(f"AE: Creating composition {name} ({width}x{height}, {duration}s)")
        return {"created": True, "comp_name": name, "comp_id": str(uuid.uuid4())}

    def _handle_add_layer(self, params: Dict[str, Any]) -> Dict[str, Any]:
        layer_type = params.get("layer_type", "solid")
        comp_name = params.get("comp_name", "")
        self.logger.info(f"AE: Adding {layer_type} layer to '{comp_name}'")
        return {"added": True, "layer_id": str(uuid.uuid4())}

    def _handle_generic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"AE: Executing generic task with params")
        return {"executed": True, "params_count": len(params)}


class PremiereProAdapter(BaseSoftwareAdapter):
    """Premiere Pro 适配器 - 通过 ExtendScript / Dynamic Link"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.PREMIERE_PRO,
            capabilities={
                SoftwareCapability.EDITING,
                SoftwareCapability.TRANSITIONS,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.COLOR_GRADING,
                SoftwareCapability.RENDERING,
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.PROJECT_MANAGEMENT,
                SoftwareCapability.BATCH_PROCESSING,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={
                ".prproj", ".mov", ".mp4", ".avi", ".mxf", ".mts",
                ".png", ".jpg", ".wav", ".mp3", ".aac"
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".mxf", ".mp3", ".wav", ".aac"
            },
            max_resolution=(8192, 8192),
            max_framerate=120.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Premiere Pro...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            self.logger.info("Premiere Pro connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class PhotoshopAdapter(BaseSoftwareAdapter):
    """Photoshop 适配器 - 通过 COM / JSX"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.PHOTOSHOP,
            capabilities={
                SoftwareCapability.IMAGE_MANIPULATION,
                SoftwareCapability.PAINTING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.RENDERING,
                SoftwareCapability.BATCH_PROCESSING,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={
                ".psd", ".png", ".jpg", ".jpeg", ".tiff", ".tga",
                ".bmp", ".gif", ".webp", ".raw", ".ai"
            },
            supported_formats_output={
                ".psd", ".png", ".jpg", ".tiff", ".tga", ".bmp",
                ".gif", ".webp", ".pdf", ".svg"
            },
            max_resolution=(300000, 300000),
            max_framerate=0.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Photoshop...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            self.logger.info("Photoshop connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class ResolveAdapter(BaseSoftwareAdapter):
    """DaVinci Resolve 适配器 - 通过 Resolve Scripting API"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.DAVINCI_RESOLVE,
            capabilities={
                SoftwareCapability.COLOR_GRADING,
                SoftwareCapability.EDITING,
                SoftwareCapability.FUSION_VFX if hasattr(SoftwareCapability, 'FUSION_VFX') else SoftwareCapability.COMPOSITING,
                SoftwareCapability.RENDERING,
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.MOTION_TRACKING,
                SoftwareCapability.KEYING,
                SoftwareCapability.PROJECT_MANAGEMENT,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".drp", ".mov", ".mp4", ".mxf", ".mts", ".ari",
                ".r3d", ".png", ".jpg", ".wav", ".aiff", ".mp3"
            },
            supported_formats_output={
                ".mov", ".mp4", ".mxf", ".dpx", ".png", ".jpg",
                ".tiff", ".wav", ".aiff", ".mp3"
            },
            max_resolution=(32768, 32768),
            max_framerate=120.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to DaVinci Resolve...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            self.logger.info("DaVinci Resolve connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class BlenderAdapter(BaseSoftwareAdapter):
    """Blender 适配器 - 通过 Blender Python (bpy) 子进程"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.BLENDER,
            capabilities={
                SoftwareCapability.THREE_D,
                SoftwareCapability.PARTICLES,
                SoftwareCapability.RENDERING,
                SoftwareCapability.SIMULATION if hasattr(SoftwareCapability, 'SIMULATION') else SoftwareCapability.RENDERING,
                SoftwareCapability.MOTION_TRACKING,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.VIDEO_ENCODING,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".blend", ".obj", ".fbx", ".abc", ".dae", ".stl",
                ".ply", ".gltf", ".glb", ".png", ".jpg", ".mov", ".mp4"
            },
            supported_formats_output={
                ".blend", ".obj", ".fbx", ".abc", ".stl", ".ply",
                ".gltf", ".glb", ".png", ".jpg", ".tiff", ".exr",
                ".mov", ".mp4", ".avi"
            },
            max_resolution=(65536, 65536),
            max_framerate=240.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Blender...")
            self._status = ConnectionStatus.CONNECTING
            blender_path = self.config.executable_path
            if blender_path and not os.path.exists(blender_path):
                self.logger.warning(f"Blender executable not found at {blender_path}")
            self._set_connected()
            self.logger.info("Blender connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class TopazVideoAIAdapter(BaseSoftwareAdapter):
    """Topaz Video AI 适配器 - 通过 CLI / 文件监视"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.TOPAZ_VIDEO_AI,
            capabilities={
                SoftwareCapability.UPSCALING,
                SoftwareCapability.DENOSING,
                SoftwareCapability.STABILIZATION,
                SoftwareCapability.INTERPOLATION,
                SoftwareCapability.VIDEO_ENCODING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".mov", ".mp4", ".avi", ".mkv", ".mts", ".mxf",
                ".prores", ".dv", ".wmv", ".flv", ".webm"
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".mkv", ".prores"
            },
            max_resolution=(16384, 16384),
            max_framerate=120.0,
            gpu_accelerated=True,
            scriptable=False,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Topaz Video AI...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            self.logger.info("Topaz Video AI connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class FFmpegAdapter(BaseSoftwareAdapter):
    """FFmpeg 适配器 - 通过子进程 CLI"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.FFMPEG,
            capabilities={
                SoftwareCapability.VIDEO_ENCODING,
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.TRANSITIONS,
                SoftwareCapability.BATCH_PROCESSING,
                SoftwareCapability.STABILIZATION,
                SoftwareCapability.DENOSING,
                SoftwareCapability.INTERPOLATION,
            },
            supported_formats_input={
                ".mov", ".mp4", ".avi", ".mkv", ".webm", ".flv",
                ".wmv", ".mts", ".mxf", ".m4v", ".3gp",
                ".wav", ".mp3", ".aac", ".flac", ".ogg",
                ".png", ".jpg", ".tiff", ".bmp", ".gif", ".webp"
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".mkv", ".webm", ".flv",
                ".wmv", ".mxf", ".gif",
                ".wav", ".mp3", ".aac", ".flac", ".ogg",
                ".png", ".jpg", ".tiff", ".bmp", ".webp"
            },
            max_resolution=(65536, 65536),
            max_framerate=1000.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to FFmpeg...")
            self._status = ConnectionStatus.CONNECTING
            ffmpeg_path = self.config.executable_path or "ffmpeg"
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-version"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    version_line = result.stdout.split("\n")[0]
                    self.config.version = version_line
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self.logger.warning("FFmpeg not found in PATH, proceeding in stub mode")
            self._set_connected()
            self.logger.info("FFmpeg connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = self._dispatch_ffmpeg_task(task)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now()
            raise
        finally:
            self._mark_task_end()

    def _dispatch_ffmpeg_task(self, task: Task) -> Dict[str, Any]:
        task_type = task.task_type
        if task_type == "transcode":
            return self._handle_transcode(task.params)
        elif task_type == "concat":
            return self._handle_concat(task.params)
        elif task_type == "extract_audio":
            return self._handle_extract_audio(task.params)
        elif task_type == "get_info":
            return self._handle_get_info(task.params)
        else:
            return {"executed": True, "task_type": task_type}

    def _handle_transcode(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input_path", "")
        output_path = params.get("output_path", "")
        codec = params.get("codec", "libx264")
        bitrate = params.get("bitrate", "5M")
        self.logger.info(f"FFmpeg: Transcoding {input_path} -> {output_path} ({codec}, {bitrate})")
        return {
            "transcoded": True,
            "input": input_path,
            "output": output_path,
            "codec": codec,
            "bitrate": bitrate,
        }

    def _handle_concat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        inputs = params.get("inputs", [])
        output_path = params.get("output_path", "")
        self.logger.info(f"FFmpeg: Concatenating {len(inputs)} files to {output_path}")
        return {"concatenated": True, "count": len(inputs), "output": output_path}

    def _handle_extract_audio(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input_path", "")
        output_path = params.get("output_path", "")
        self.logger.info(f"FFmpeg: Extracting audio from {input_path}")
        return {"extracted": True, "input": input_path, "output": output_path}

    def _handle_get_info(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input_path", "")
        self.logger.info(f"FFmpeg: Getting info for {input_path}")
        return {
            "info": {
                "filename": os.path.basename(input_path) if input_path else "",
                "duration": 0.0,
                "resolution": "1920x1080",
                "codec": "h264",
                "fps": 30.0,
            }
        }


class RunwayMLAdapter(BaseSoftwareAdapter):
    """RunwayML 适配器 - 通过 HTTP API"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.RUNWAYML,
            capabilities={
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.IMAGE_MANIPULATION,
                SoftwareCapability.VIDEO_ENCODING,
            },
            supported_formats_input={
                ".png", ".jpg", ".jpeg", ".mp4", ".mov", ".webp"
            },
            supported_formats_output={
                ".png", ".jpg", ".mp4", ".mov", ".webm"
            },
            max_resolution=(1920, 1080),
            max_framerate=24.0,
            gpu_accelerated=False,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to RunwayML API...")
            self._status = ConnectionStatus.CONNECTING
            api_key = self.config.api_key
            if not api_key:
                self.logger.warning("RunwayML API key not configured")
            self._set_connected()
            self.logger.info("RunwayML API connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class PikaAdapter(BaseSoftwareAdapter):
    """Pika 适配器 - 通过 HTTP API"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.PIKA,
            capabilities={
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.VIDEO_ENCODING,
            },
            supported_formats_input={
                ".png", ".jpg", ".jpeg", ".mp4", ".mov"
            },
            supported_formats_output={
                ".mp4", ".mov"
            },
            max_resolution=(1280, 720),
            max_framerate=24.0,
            gpu_accelerated=False,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Pika API...")
            self._status = ConnectionStatus.CONNECTING
            if not self.config.api_key:
                self.logger.warning("Pika API key not configured")
            self._set_connected()
            self.logger.info("Pika API connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class MediaEncoderAdapter(BaseSoftwareAdapter):
    """Adobe Media Encoder 适配器 - 通过监视文件夹 / AME 脚本"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.MEDIA_ENCODER,
            capabilities={
                SoftwareCapability.VIDEO_ENCODING,
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.BATCH_PROCESSING,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={
                ".aep", ".prproj", ".mov", ".mp4", ".avi", ".mxf",
                ".mts", ".png", ".jpg", ".wav", ".mp3"
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".mxf", ".wmv", ".webm",
                ".mp3", ".wav", ".aac", ".gif"
            },
            max_resolution=(8192, 8192),
            max_framerate=120.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Adobe Media Encoder...")
            self._status = ConnectionStatus.CONNECTING
            watch_folder = self.config.additional_settings.get("watch_folder")
            if watch_folder:
                os.makedirs(watch_folder, exist_ok=True)
            self._set_connected()
            self.logger.info("Adobe Media Encoder connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class IllustratorAdapter(BaseSoftwareAdapter):
    """Illustrator 适配器"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.ILLUSTRATOR,
            capabilities={
                SoftwareCapability.VECTOR_GRAPHICS,
                SoftwareCapability.IMAGE_MANIPULATION,
                SoftwareCapability.PAINTING,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".ai", ".eps", ".svg", ".pdf", ".png", ".jpg", ".tiff"
            },
            supported_formats_output={
                ".ai", ".eps", ".svg", ".pdf", ".png", ".jpg", ".tiff", ".webp"
            },
            max_resolution=(1000000, 1000000),
            max_framerate=0.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Illustrator...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


class SilhouetteAdapter(BaseSoftwareAdapter):
    """Silhouette 适配器 - 用于精细的rotoscoping和paint"""

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.SILHOUETTE,
            capabilities={
                SoftwareCapability.ROTOSCOPING,
                SoftwareCapability.PAINTING,
                SoftwareCapability.KEYING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={
                ".sfx", ".mov", ".mp4", ".avi", ".png", ".jpg",
                ".tiff", ".tga", ".exr", ".dpx"
            },
            supported_formats_output={
                ".mov", ".mp4", ".png", ".tiff", ".tga", ".exr", ".dpx"
            },
            max_resolution=(8192, 8192),
            max_framerate=120.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self.logger.info("Connecting to Silhouette...")
            self._status = ConnectionStatus.CONNECTING
            self._set_connected()
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        if not self.can_accept_task():
            raise RuntimeError(f"{self.software_type.value} cannot accept tasks")
        self._mark_task_start()
        try:
            task.started_at = datetime.now()
            task.status = TaskStatus.RUNNING
            task.software_used = self.software_type
            result = {"executed": True, "task_type": task.task_type}
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            return result
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            raise
        finally:
            self._mark_task_end()


# Adapter registry
ADAPTER_REGISTRY: Dict[SoftwareType, Type[BaseSoftwareAdapter]] = {
    SoftwareType.AFTER_EFFECTS: AfterEffectsAdapter,
    SoftwareType.PREMIERE_PRO: PremiereProAdapter,
    SoftwareType.PHOTOSHOP: PhotoshopAdapter,
    SoftwareType.DAVINCI_RESOLVE: ResolveAdapter,
    SoftwareType.BLENDER: BlenderAdapter,
    SoftwareType.TOPAZ_VIDEO_AI: TopazVideoAIAdapter,
    SoftwareType.FFMPEG: FFmpegAdapter,
    SoftwareType.RUNWAYML: RunwayMLAdapter,
    SoftwareType.PIKA: PikaAdapter,
    SoftwareType.MEDIA_ENCODER: MediaEncoderAdapter,
    SoftwareType.ILLUSTRATOR: IllustratorAdapter,
    SoftwareType.SILHOUETTE: SilhouetteAdapter,
}


# ============================================================================
# 3. TASK ORCHESTRATION SYSTEM
# ============================================================================

class TaskQueue:
    """优先级任务队列，支持依赖管理"""

    def __init__(self, maxsize: int = 0):
        self._queue: PriorityQueue = PriorityQueue(maxsize=maxsize)
        self._pending: Dict[str, Task] = {}
        self._completed: Dict[str, Task] = {}
        self._failed: Dict[str, Task] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("bridge.task_queue")

    def add_task(self, task: Task) -> str:
        """添加任务到队列"""
        with self._lock:
            task.status = TaskStatus.QUEUED
            self._pending[task.task_id] = task
            self._queue.put((-task.priority.value, task.task_id, task))
            self.logger.info(f"Task {task.task_id} added to queue (priority: {task.priority.name})")
            return task.task_id

    def get_task(self, timeout: float = 1.0) -> Optional[Task]:
        """获取下一个就绪的任务"""
        try:
            priority, task_id, task = self._queue.get(timeout=timeout)
            if not self._check_dependencies(task):
                self._queue.put((priority, task_id, task))
                time.sleep(0.1)
                return None
            return task
        except Empty:
            return None

    def _check_dependencies(self, task: Task) -> bool:
        """检查任务依赖是否都已完成"""
        if not task.dependencies:
            return True
        for dep_id in task.dependencies:
            if dep_id not in self._completed:
                return False
        return True

    def mark_completed(self, task: Task) -> None:
        """标记任务完成"""
        with self._lock:
            task.status = TaskStatus.COMPLETED
            if task.task_id in self._pending:
                del self._pending[task.task_id]
            self._completed[task.task_id] = task
            self.logger.info(f"Task {task.task_id} completed")

    def mark_failed(self, task: Task) -> None:
        """标记任务失败"""
        with self._lock:
            task.status = TaskStatus.FAILED
            if task.task_id in self._pending:
                del self._pending[task.task_id]
            self._failed[task.task_id] = task
            self.logger.warning(f"Task {task.task_id} failed: {task.error}")

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        with self._lock:
            if task_id in self._pending:
                return self._pending[task_id].status
            if task_id in self._completed:
                return self._completed[task_id].status
            if task_id in self._failed:
                return self._failed[task_id].status
            return None

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务详情"""
        with self._lock:
            if task_id in self._pending:
                return self._pending[task_id]
            if task_id in self._completed:
                return self._completed[task_id]
            if task_id in self._failed:
                return self._failed[task_id]
            return None

    def get_queue_size(self) -> int:
        """获取队列大小"""
        return self._queue.qsize()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        with self._lock:
            return {
                "pending": len(self._pending),
                "completed": len(self._completed),
                "failed": len(self._failed),
                "queue_size": self._queue.qsize(),
            }


class TaskScheduler:
    """任务调度器 - 将任务分配给可用的软件"""

    def __init__(self, bridge: 'MultiSoftwareBridge'):
        self.bridge = bridge
        self.task_queue = TaskQueue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_pool: Optional[ThreadPoolExecutor] = None
        self.logger = logging.getLogger("bridge.task_scheduler")

    def start(self, max_workers: int = 4) -> None:
        """启动调度器"""
        self._running = True
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-worker")
        self._worker_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._worker_thread.start()
        self.logger.info(f"Task scheduler started with {max_workers} workers")

    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        if self._thread_pool:
            self._thread_pool.shutdown(wait=False)
        self.logger.info("Task scheduler stopped")

    def _scheduler_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                task = self.task_queue.get_task(timeout=1.0)
                if task:
                    self._assign_task(task)
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                time.sleep(1)

    def _assign_task(self, task: Task) -> None:
        """分配任务给合适的软件"""
        target_software = task.target_software
        if target_software:
            adapter = self.bridge.get_adapter(target_software)
            if adapter and adapter.can_accept_task():
                self._execute_task_on_adapter(task, adapter)
                return
            elif adapter:
                self.task_queue.add_task(task)
                return

        software_list = self.bridge.auto_select_software(task.task_type, task.params)
        for software_type in software_list:
            adapter = self.bridge.get_adapter(software_type)
            if adapter and adapter.can_accept_task():
                self._execute_task_on_adapter(task, adapter)
                return

        self.task_queue.add_task(task)

    def _execute_task_on_adapter(self, task: Task, adapter: BaseSoftwareAdapter) -> None:
        """在线程池中执行任务"""
        if not self._thread_pool:
            raise RuntimeError("Thread pool not initialized")
        future = self._thread_pool.submit(self._run_task, task, adapter)
        future.add_done_callback(lambda f: self._on_task_complete(f, task))

    def _run_task(self, task: Task, adapter: BaseSoftwareAdapter) -> Any:
        """运行任务的实际执行函数"""
        self.logger.info(f"Executing task {task.task_id} on {adapter.software_type.value}")
        try:
            result = adapter.execute_task(task)
            return result
        except Exception as e:
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                self.logger.info(f"Retrying task {task.task_id} (attempt {task.retry_count}/{task.max_retries})")
                time.sleep(2 ** task.retry_count)
                raise
            raise

    def _on_task_complete(self, future: Future, task: Task) -> None:
        """任务完成回调"""
        try:
            result = future.result()
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            self.task_queue.mark_completed(task)
            if task.callback:
                try:
                    task.callback(task)
                except Exception as e:
                    self.logger.error(f"Task callback error: {e}")
            if task.software_used:
                self.bridge.performance_metrics.record_task(
                    task.software_used,
                    (task.completed_at - task.started_at).total_seconds() if task.started_at else 0,
                    True
                )
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            self.task_queue.mark_failed(task)
            if task.callback:
                try:
                    task.callback(task)
                except Exception as cb_err:
                    self.logger.error(f"Task callback error: {cb_err}")
            if task.software_used:
                self.bridge.performance_metrics.record_task(
                    task.software_used,
                    (task.completed_at - task.started_at).total_seconds() if task.started_at else 0,
                    False
                )

    def submit_task(self, task: Task) -> str:
        """提交任务"""
        return self.task_queue.add_task(task)

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self.task_queue.get_task_status(task_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务详情"""
        return self.task_queue.get_task(task_id)


# ============================================================================
# 4. DATA EXCHANGE LAYER
# ============================================================================

class FileExchange:
    """文件交换 - 监视文件夹，软件间文件传输"""

    def __init__(self, base_dir: str = "./exchange"):
        self.base_dir = Path(base_dir)
        self.watch_folders: Dict[SoftwareType, Path] = {}
        self._watchers: Dict[str, threading.Thread] = {}
        self.logger = logging.getLogger("bridge.file_exchange")
        self._setup_directories()

    def _setup_directories(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        for software in SoftwareType:
            sw_dir = self.base_dir / software.value
            sw_dir.mkdir(exist_ok=True)
            (sw_dir / "in").mkdir(exist_ok=True)
            (sw_dir / "out").mkdir(exist_ok=True)
            self.watch_folders[software] = sw_dir

    def get_input_path(self, software: SoftwareType, filename: str) -> Path:
        return self.watch_folders[software] / "in" / filename

    def get_output_path(self, software: SoftwareType, filename: str) -> Path:
        return self.watch_folders[software] / "out" / filename

    def transfer_file(self, source: Path, destination: Path, wait: bool = True) -> bool:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(str(source), str(destination))
            self.logger.info(f"File transferred: {source} -> {destination}")
            return True
        except Exception as e:
            self.logger.error(f"File transfer failed: {e}")
            return False

    def wait_for_file(self, filepath: Path, timeout: float = 60.0) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if filepath.exists() and filepath.stat().st_size > 0:
                return True
            time.sleep(0.5)
        return False


class FormatConverter:
    """格式转换器 - 在格式之间自动转换"""

    def __init__(self, bridge: 'MultiSoftwareBridge'):
        self.bridge = bridge
        self.logger = logging.getLogger("bridge.format_converter")
        self._format_chain: Dict[str, List[str]] = {
            ".bmp": [".png", ".jpg", ".tiff"],
            ".tga": [".png", ".tiff", ".exr"],
            ".exr": [".tiff", ".png", ".jpg"],
            ".webp": [".png", ".jpg"],
            ".gif": [".mp4", ".mov", ".png"],
            ".mkv": [".mp4", ".mov"],
            ".webm": [".mp4", ".mov"],
            ".avi": [".mp4", ".mov"],
            ".flv": [".mp4", ".mov"],
            ".wmv": [".mp4", ".mov"],
        }

    def can_convert(self, from_format: str, to_format: str) -> bool:
        if from_format.lower() == to_format.lower():
            return True
        chain = self._format_chain.get(from_format.lower(), [])
        return to_format.lower() in chain

    def convert(self, input_path: str, output_path: str, params: Optional[Dict[str, Any]] = None) -> bool:
        params = params or {}
        self.logger.info(f"Converting {input_path} -> {output_path}")
        try:
            ffmpeg_adapter = self.bridge.get_adapter(SoftwareType.FFMPEG)
            if ffmpeg_adapter and ffmpeg_adapter.get_status().status == ConnectionStatus.CONNECTED:
                task = Task(
                    task_type="transcode",
                    target_software=SoftwareType.FFMPEG,
                    params={
                        "input_path": input_path,
                        "output_path": output_path,
                        **params
                    }
                )
                ffmpeg_adapter.execute_task(task)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Conversion failed: {e}")
            return False

    def get_best_intermediate_format(self, source_formats: Set[str], target_formats: Set[str]) -> Optional[str]:
        common = source_formats & target_formats
        if common:
            priority_formats = [".mov", ".mp4", ".png", ".tiff", ".jpg", ".wav", ".mp3"]
            for fmt in priority_formats:
                if fmt in common:
                    return fmt
            return next(iter(common))
        for src_fmt in source_formats:
            for tgt_fmt in target_formats:
                if self.can_convert(src_fmt, tgt_fmt):
                    return tgt_fmt
        return None


class MetadataTransfer:
    """基于JSON的元数据管道"""

    def __init__(self):
        self.logger = logging.getLogger("bridge.metadata_transfer")

    def create_metadata(self, data: Dict[str, Any], filepath: str) -> str:
        try:
            metadata_path = filepath + ".meta.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            return metadata_path
        except Exception as e:
            self.logger.error(f"Failed to create metadata: {e}")
            raise

    def read_metadata(self, filepath: str) -> Optional[Dict[str, Any]]:
        metadata_path = filepath + ".meta.json"
        if not os.path.exists(metadata_path):
            return None
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read metadata: {e}")
            return None

    def transfer_metadata(self, source_path: str, target_path: str) -> bool:
        metadata = self.read_metadata(source_path)
        if metadata:
            self.create_metadata(metadata, target_path)
            return True
        return False


class IntermediateCache:
    """中间渲染输出缓存，用于重用"""

    def __init__(self, cache_dir: str = "./cache", max_size_gb: float = 10.0):
        self.cache_dir = Path(cache_dir)
        self.max_size_gb = max_size_gb
        self._cache_index: Dict[str, Dict[str, Any]] = {}
        self._access_order: deque = deque()
        self._lock = threading.Lock()
        self.logger = logging.getLogger("bridge.cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_key(self, params: Dict[str, Any]) -> str:
        import hashlib
        key_str = json.dumps(params, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._cache_index:
                cache_entry = self._cache_index[key]
                filepath = cache_entry["path"]
                if os.path.exists(filepath):
                    if key in self._access_order:
                        self._access_order.remove(key)
                    self._access_order.append(key)
                    self.logger.info(f"Cache hit: {key}")
                    return filepath
                else:
                    del self._cache_index[key]
            return None

    def put(self, key: str, filepath: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            try:
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
            except OSError:
                file_size = 0
            self._cache_index[key] = {
                "path": filepath,
                "size": file_size,
                "metadata": metadata or {},
                "created": datetime.now(),
            }
            self._access_order.append(key)
            self._evict_if_needed()
            self.logger.info(f"Cached: {key} ({file_size / 1024 / 1024:.2f} MB)")

    def _evict_if_needed(self) -> None:
        total_size = sum(e["size"] for e in self._cache_index.values())
        max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024
        while total_size > max_size_bytes and self._access_order:
            oldest_key = self._access_order.popleft()
            if oldest_key in self._cache_index:
                entry = self._cache_index.pop(oldest_key)
                total_size -= entry["size"]
                try:
                    if os.path.exists(entry["path"]):
                        os.remove(entry["path"])
                except OSError:
                    pass
                self.logger.info(f"Evicted from cache: {oldest_key}")

    def clear(self) -> None:
        with self._lock:
            self._cache_index.clear()
            self._access_order.clear()
            self.logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_size = sum(e["size"] for e in self._cache_index.values())
            return {
                "items": len(self._cache_index),
                "total_size_mb": total_size / 1024 / 1024,
                "max_size_gb": self.max_size_gb,
            }


# ============================================================================
# 5. RESOURCE MANAGEMENT
# ============================================================================

class ResourcePool:
    """资源池 - 跟踪软件实例、许可证、GPU/CPU使用情况"""

    def __init__(self):
        self._instances: Dict[SoftwareType, Dict[str, Any]] = {}
        self._gpu_devices: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("bridge.resource_pool")

    def register_instance(self, software: SoftwareType, instance_info: Dict[str, Any]) -> None:
        self._instances[software] = {
            "registered_at": datetime.now(),
            **instance_info
        }
        self.logger.info(f"Registered instance: {software.value}")

    def unregister_instance(self, software: SoftwareType) -> None:
        if software in self._instances:
            del self._instances[software]
            self.logger.info(f"Unregistered instance: {software.value}")

    def get_available_instances(self, software: SoftwareType) -> List[Dict[str, Any]]:
        if software in self._instances:
            return [self._instances[software]]
        return []

    def get_total_resources(self) -> Dict[str, Any]:
        return {
            "total_software": len(self._instances),
            "software_types": list(self._instances.keys()),
        }


class LicenseManager:
    """许可证管理器 - 跟踪可用席位、浮动许可证"""

    def __init__(self):
        self._licenses: Dict[SoftwareType, Dict[str, Any]] = {}
        self.logger = logging.getLogger("bridge.license_manager")

    def add_license(self, software: SoftwareType, license_key: str, seats: int = 1, floating: bool = False) -> None:
        self._licenses[software] = {
            "key": license_key,
            "total_seats": seats,
            "used_seats": 0,
            "floating": floating,
            "added_at": datetime.now(),
        }
        self.logger.info(f"License added: {software.value} (seats: {seats})")

    def acquire_license(self, software: SoftwareType) -> bool:
        if software not in self._licenses:
            return True
        lic = self._licenses[software]
        if lic["used_seats"] < lic["total_seats"]:
            lic["used_seats"] += 1
            return True
        return False

    def release_license(self, software: SoftwareType) -> None:
        if software in self._licenses:
            lic = self._licenses[software]
            lic["used_seats"] = max(0, lic["used_seats"] - 1)

    def get_license_status(self, software: SoftwareType) -> Dict[str, Any]:
        if software not in self._licenses:
            return {"available": True, "no_license": True}
        lic = self._licenses[software]
        return {
            "available": lic["used_seats"] < lic["total_seats"],
            "total_seats": lic["total_seats"],
            "used_seats": lic["used_seats"],
            "floating": lic["floating"],
        }


class GPULoadBalancer:
    """GPU负载均衡器"""

    def __init__(self):
        self._gpus: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("bridge.gpu_balancer")

    def add_gpu(self, gpu_id: str, name: str, total_memory_mb: int) -> None:
        self._gpus.append({
            "id": gpu_id,
            "name": name,
            "total_memory_mb": total_memory_mb,
            "used_memory_mb": 0,
            "load": 0.0,
            "tasks": 0,
        })
        self.logger.info(f"GPU added: {name} ({gpu_id})")

    def get_optimal_gpu(self, required_memory_mb: int = 0) -> Optional[str]:
        best_gpu = None
        best_score = -1
        for gpu in self._gpus:
            available_memory = gpu["total_memory_mb"] - gpu["used_memory_mb"]
            if available_memory >= required_memory_mb:
                score = available_memory - (gpu["load"] * 1000) - (gpu["tasks"] * 500)
                if score > best_score:
                    best_score = score
                    best_gpu = gpu["id"]
        return best_gpu

    def assign_task(self, gpu_id: str, memory_mb: int) -> bool:
        for gpu in self._gpus:
            if gpu["id"] == gpu_id:
                if gpu["total_memory_mb"] - gpu["used_memory_mb"] >= memory_mb:
                    gpu["used_memory_mb"] += memory_mb
                    gpu["tasks"] += 1
                    return True
        return False

    def release_task(self, gpu_id: str, memory_mb: int) -> None:
        for gpu in self._gpus:
            if gpu["id"] == gpu_id:
                gpu["used_memory_mb"] = max(0, gpu["used_memory_mb"] - memory_mb)
                gpu["tasks"] = max(0, gpu["tasks"] - 1)
                break

    def get_status(self) -> List[Dict[str, Any]]:
        return [dict(gpu) for gpu in self._gpus]


class MemoryManager:
    """内存管理器 - 跟踪内存使用，优化缓存"""

    def __init__(self, max_cache_gb: float = 10.0):
        self.max_cache_gb = max_cache_gb
        self._current_usage = 0.0
        self._cache_items: List[Dict[str, Any]] = []
        self.logger = logging.getLogger("bridge.memory_manager")

    def allocate(self, size_mb: float, label: str = "") -> bool:
        if self._current_usage + size_mb <= self.max_cache_gb * 1024:
            self._current_usage += size_mb
            self._cache_items.append({"size": size_mb, "label": label, "time": time.time()})
            return True
        return False

    def release(self, size_mb: float) -> None:
        self._current_usage = max(0.0, self._current_usage - size_mb)

    def get_usage(self) -> Dict[str, Any]:
        return {
            "used_mb": self._current_usage,
            "max_mb": self.max_cache_gb * 1024,
            "usage_percent": (self._current_usage / (self.max_cache_gb * 1024)) * 100 if self.max_cache_gb > 0 else 0,
            "cache_items": len(self._cache_items),
        }


class ConcurrencyLimiter:
    """并发限制器 - 每个软件的最大并行任务数"""

    def __init__(self):
        self._limits: Dict[SoftwareType, int] = {}
        self._current: Dict[SoftwareType, int] = defaultdict(int)
        self._lock = threading.Lock()
        self.logger = logging.getLogger("bridge.concurrency_limiter")

    def set_limit(self, software: SoftwareType, max_tasks: int) -> None:
        self._limits[software] = max_tasks
        self.logger.info(f"Concurrency limit set for {software.value}: {max_tasks}")

    def can_acquire(self, software: SoftwareType) -> bool:
        with self._lock:
            limit = self._limits.get(software, 1)
            return self._current[software] < limit

    def acquire(self, software: SoftwareType) -> bool:
        with self._lock:
            limit = self._limits.get(software, 1)
            if self._current[software] < limit:
                self._current[software] += 1
                return True
            return False

    def release(self, software: SoftwareType) -> None:
        with self._lock:
            if self._current[software] > 0:
                self._current[software] -= 1

    def get_status(self) -> Dict[str, Dict[str, int]]:
        result = {}
        for sw, limit in self._limits.items():
            result[sw.value] = {
                "current": self._current[sw],
                "limit": limit,
                "available": limit - self._current[sw],
            }
        return result


# ============================================================================
# 6. ERROR HANDLING & RECOVERY
# ============================================================================

class CircuitBreaker:
    """熔断器 - 停止向故障软件发送任务"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._states: Dict[SoftwareType, Dict[str, Any]] = {}
        self.logger = logging.getLogger("bridge.circuit_breaker")

    def record_success(self, software: SoftwareType) -> None:
        if software not in self._states:
            self._states[software] = self._initial_state()
        state = self._states[software]
        if state["status"] == "open":
            state["status"] = "half-open"
            self.logger.info(f"Circuit breaker half-open: {software.value}")
        state["failures"] = 0
        state["last_success"] = time.time()

    def record_failure(self, software: SoftwareType) -> None:
        if software not in self._states:
            self._states[software] = self._initial_state()
        state = self._states[software]
        state["failures"] += 1
        state["last_failure"] = time.time()
        if state["failures"] >= self.failure_threshold and state["status"] != "open":
            state["status"] = "open"
            state["opened_at"] = time.time()
            self.logger.warning(f"Circuit breaker opened: {software.value}")

    def can_execute(self, software: SoftwareType) -> bool:
        if software not in self._states:
            return True
        state = self._states[software]
        if state["status"] == "open":
            if time.time() - state["opened_at"] > self.recovery_timeout:
                state["status"] = "half-open"
                self.logger.info(f"Circuit breaker half-open (recovery): {software.value}")
                return True
            return False
        return True

    def _initial_state(self) -> Dict[str, Any]:
        return {
            "status": "closed",
            "failures": 0,
            "last_success": None,
            "last_failure": None,
            "opened_at": None,
        }

    def get_status(self, software: SoftwareType) -> Dict[str, Any]:
        if software not in self._states:
            return {"status": "closed", "failures": 0}
        return dict(self._states[software])

    def reset(self, software: SoftwareType) -> None:
        self._states[software] = self._initial_state()
        self.logger.info(f"Circuit breaker reset: {software.value}")


class ErrorRecovery:
    """错误恢复 - 重试、回退、回滚"""

    def __init__(self, bridge: 'MultiSoftwareBridge'):
        self.bridge = bridge
        self.logger = logging.getLogger("bridge.error_recovery")

    def execute_with_retry(self, task: Task, adapter: BaseSoftwareAdapter, max_retries: int = 3) -> Any:
        last_error = None
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}/{max_retries} for task {task.task_id}")
                result = adapter.execute_task(task)
                return result
            except Exception as e:
                last_error = e
                task.retry_count = attempt + 1
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        raise last_error

    def execute_with_fallback(self, task: Task, software_list: List[SoftwareType]) -> Any:
        last_error = None
        for software in software_list:
            adapter = self.bridge.get_adapter(software)
            if not adapter:
                continue
            if not adapter.can_accept_task():
                continue
            try:
                self.logger.info(f"Trying {software.value} for task {task.task_id}")
                result = adapter.execute_task(task)
                return result
            except Exception as e:
                last_error = e
                self.logger.warning(f"{software.value} failed: {e}")
                continue
        raise last_error or RuntimeError("No software available for task")

    def rollback_task(self, task: Task) -> bool:
        self.logger.info(f"Rolling back task {task.task_id}")
        return True


class HealthMonitor:
    """健康监控器 - 定期检查所有软件的健康状态"""

    def __init__(self, bridge: 'MultiSoftwareBridge', check_interval: float = 30.0):
        self.bridge = bridge
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._health_history: Dict[SoftwareType, List[Dict[str, Any]]] = defaultdict(list)
        self.logger = logging.getLogger("bridge.health_monitor")

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("Health monitor started")

    def stop(self) -> None:
        self._running = False
        self.logger.info("Health monitor stopped")

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                self._check_all_software()
                time.sleep(self.check_interval)
            except Exception as e:
                self.logger.error(f"Health monitor error: {e}")
                time.sleep(self.check_interval)

    def _check_all_software(self) -> None:
        for software_type, adapter in self.bridge._adapters.items():
            try:
                healthy = adapter.health_check()
                status = "healthy" if healthy else "unhealthy"
                self._health_history[software_type].append({
                    "time": datetime.now(),
                    "status": status,
                })
                if len(self._health_history[software_type]) > 100:
                    self._health_history[software_type] = self._health_history[software_type][-100:]
                if not healthy:
                    self.bridge.circuit_breaker.record_failure(software_type)
                else:
                    self.bridge.circuit_breaker.record_success(software_type)
            except Exception as e:
                self.logger.error(f"Health check failed for {software_type.value}: {e}")

    def get_health_history(self, software: SoftwareType, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self._health_history.get(software, []))[-limit:]

    def get_overall_health(self) -> Dict[str, Any]:
        total = 0
        healthy = 0
        details = {}
        for sw, adapter in self.bridge._adapters.items():
            total += 1
            status = adapter.get_status()
            is_healthy = status.status == ConnectionStatus.CONNECTED
            if is_healthy:
                healthy += 1
            details[sw.value] = {
                "status": status.status.value,
                "healthy": is_healthy,
            }
        return {
            "total_software": total,
            "healthy_software": healthy,
            "health_percentage": (healthy / total * 100) if total > 0 else 0,
            "details": details,
        }


class TimeoutManager:
    """超时管理器 - 每个任务的超时设置"""

    def __init__(self):
        self._timeouts: Dict[str, float] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger("bridge.timeout_manager")

    def set_timeout(self, task_id: str, timeout_seconds: float) -> None:
        with self._lock:
            self._timeouts[task_id] = time.time() + timeout_seconds

    def is_expired(self, task_id: str) -> bool:
        with self._lock:
            if task_id not in self._timeouts:
                return False
            return time.time() > self._timeouts[task_id]

    def clear_timeout(self, task_id: str) -> None:
        with self._lock:
            self._timeouts.pop(task_id, None)

    def get_remaining_time(self, task_id: str) -> float:
        with self._lock:
            if task_id not in self._timeouts:
                return float('inf')
            return max(0, self._timeouts[task_id] - time.time())


# ============================================================================
# 7. CONFIGURATION & DISCOVERY
# ============================================================================

class SoftwareDiscovery:
    """软件自动发现"""

    def __init__(self):
        self.logger = logging.getLogger("bridge.discovery")
        self._common_paths = {
            "windows": {
                SoftwareType.AFTER_EFFECTS: [
                    r"C:\Program Files\Adobe\Adobe After Effects 2024\Support Files\AfterFX.exe",
                    r"C:\Program Files\Adobe\Adobe After Effects 2023\Support Files\AfterFX.exe",
                    r"C:\Program Files\Adobe\Adobe After Effects 2022\Support Files\AfterFX.exe",
                ],
                SoftwareType.PREMIERE_PRO: [
                    r"C:\Program Files\Adobe\Adobe Premiere Pro 2024\Adobe Premiere Pro.exe",
                    r"C:\Program Files\Adobe\Adobe Premiere Pro 2023\Adobe Premiere Pro.exe",
                ],
                SoftwareType.PHOTOSHOP: [
                    r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
                    r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
                ],
                SoftwareType.DAVINCI_RESOLVE: [
                    r"C:\Program Files\Blackmagic Design\DaVinci Resolve\Resolve.exe",
                ],
                SoftwareType.BLENDER: [
                    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
                    r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
                ],
                SoftwareType.MEDIA_ENCODER: [
                    r"C:\Program Files\Adobe\Adobe Media Encoder 2024\Adobe Media Encoder.exe",
                ],
                SoftwareType.ILLUSTRATOR: [
                    r"C:\Program Files\Adobe\Adobe Illustrator 2024\Support Files\Contents\Windows\Illustrator.exe",
                ],
            },
            "macos": {
                SoftwareType.AFTER_EFFECTS: [
                    "/Applications/Adobe After Effects 2024/Adobe After Effects 2024.app",
                ],
                SoftwareType.PREMIERE_PRO: [
                    "/Applications/Adobe Premiere Pro 2024/Adobe Premiere Pro 2024.app",
                ],
                SoftwareType.PHOTOSHOP: [
                    "/Applications/Adobe Photoshop 2024/Adobe Photoshop 2024.app",
                ],
            },
        }

    def discover_all(self) -> Dict[SoftwareType, SoftwareConfig]:
        discovered = {}
        platform = sys.platform
        if platform == "win32":
            paths = self._common_paths.get("windows", {})
        elif platform == "darwin":
            paths = self._common_paths.get("macos", {})
        else:
            paths = {}

        for software, path_list in paths.items():
            for path in path_list:
                if os.path.exists(path):
                    config = SoftwareConfig(
                        software=software,
                        executable_path=path,
                        enabled=True,
                    )
                    discovered[software] = config
                    self.logger.info(f"Discovered {software.value} at {path}")
                    break

        ffmpeg_path = self._find_ffmpeg()
        if ffmpeg_path:
            discovered[SoftwareType.FFMPEG] = SoftwareConfig(
                software=SoftwareType.FFMPEG,
                executable_path=ffmpeg_path,
                enabled=True,
            )

        return discovered

    def _find_ffmpeg(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["where", "ffmpeg"] if sys.platform == "win32" else ["which", "ffmpeg"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0].strip()
        except Exception:
            pass
        return None


class VersionCompatibility:
    """版本兼容性检查"""

    def __init__(self):
        self._compatibility_matrix: Dict[SoftwareType, List[str]] = {}
        self.logger = logging.getLogger("bridge.version_compat")
        self._init_matrix()

    def _init_matrix(self) -> None:
        self._compatibility_matrix = {
            SoftwareType.AFTER_EFFECTS: ["2022", "2023", "2024", "2025"],
            SoftwareType.PREMIERE_PRO: ["2022", "2023", "2024", "2025"],
            SoftwareType.PHOTOSHOP: ["2022", "2023", "2024", "2025"],
            SoftwareType.DAVINCI_RESOLVE: ["17", "18", "19"],
            SoftwareType.BLENDER: ["3.0", "3.5", "3.6", "4.0", "4.1", "4.2"],
            SoftwareType.FFMPEG: ["4.x", "5.x", "6.x", "7.x"],
            SoftwareType.MEDIA_ENCODER: ["2022", "2023", "2024", "2025"],
        }

    def check_compatibility(self, software: SoftwareType, version: str) -> bool:
        if software not in self._compatibility_matrix:
            return True
        supported = self._compatibility_matrix[software]
        for v in supported:
            if v.endswith(".x"):
                major = v.rstrip(".x")
                if version.startswith(major):
                    return True
            elif version.startswith(v):
                return True
        return False

    def get_supported_versions(self, software: SoftwareType) -> List[str]:
        return self._compatibility_matrix.get(software, [])


class PluginInventory:
    """插件库存 - 列出每个软件安装的插件"""

    def __init__(self):
        self._plugins: Dict[SoftwareType, List[Dict[str, Any]]] = defaultdict(list)
        self.logger = logging.getLogger("bridge.plugin_inventory")

    def register_plugin(self, software: SoftwareType, name: str, version: str, vendor: str = "") -> None:
        self._plugins[software].append({
            "name": name,
            "version": version,
            "vendor": vendor,
            "enabled": True,
        })
        self.logger.info(f"Plugin registered: {name} ({software.value})")

    def get_plugins(self, software: SoftwareType) -> List[Dict[str, Any]]:
        return list(self._plugins[software])

    def has_plugin(self, software: SoftwareType, plugin_name: str) -> bool:
        return any(p["name"] == plugin_name for p in self._plugins[software])

    def scan_plugins(self, software: SoftwareType, plugin_dir: str) -> List[Dict[str, Any]]:
        self.logger.info(f"Scanning plugins in {plugin_dir}")
        plugins = []
        if os.path.isdir(plugin_dir):
            for item in os.listdir(plugin_dir):
                item_path = os.path.join(plugin_dir, item)
                if os.path.isdir(item_path) or item.endswith((".aex", ".plugin", ".8bf", ".dll")):
                    plugin_info = {"name": item, "path": item_path}
                    plugins.append(plugin_info)
        return plugins


class PresetSync:
    """预设同步 - 跨软件同步预设"""

    def __init__(self, presets_dir: str = "./presets"):
        self.presets_dir = Path(presets_dir)
        self._presets: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("bridge.preset_sync")
        self.presets_dir.mkdir(parents=True, exist_ok=True)

    def save_preset(self, name: str, software: SoftwareType, preset_data: Dict[str, Any]) -> str:
        preset_id = f"{software.value}/{name}"
        filepath = self.presets_dir / software.value / f"{name}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2, ensure_ascii=False)
        self._presets[preset_id] = {
            "name": name,
            "software": software.value,
            "path": str(filepath),
            "data": preset_data,
        }
        self.logger.info(f"Preset saved: {preset_id}")
        return preset_id

    def load_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        if preset_id in self._presets:
            return self._presets[preset_id]["data"]
        parts = preset_id.split("/", 1)
        if len(parts) == 2:
            sw, name = parts
            filepath = self.presets_dir / sw / f"{name}.json"
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        return None

    def list_presets(self, software: Optional[SoftwareType] = None) -> List[str]:
        if software:
            return [pid for pid in self._presets if pid.startswith(f"{software.value}/")]
        return list(self._presets.keys())


# ============================================================================
# 8. WORKFLOW TEMPLATES
# ============================================================================

class WorkflowTemplateRegistry:
    """工作流模板注册表"""

    def __init__(self):
        self._templates: Dict[str, Workflow] = {}
        self.logger = logging.getLogger("bridge.workflow_registry")
        self._register_builtin_templates()

    def _register_builtin_templates(self) -> None:
        self.register(self._create_footage_enhancement_workflow())
        self.register(self._create_color_grading_workflow())
        self.register(self._create_3d_integration_workflow())
        self.register(self._create_ai_generation_workflow())
        self.register(self._create_batch_transcoding_workflow())
        self.register(self._create_full_pipeline_workflow())

    def _create_footage_enhancement_workflow(self) -> Workflow:
        return Workflow(
            name="footage_enhancement",
            description="素材增强工作流: Topaz Video AI 增强 -> After Effects 合成 -> Media Encoder 输出",
            steps=[
                WorkflowStep(
                    name="upscale",
                    task_type="upscale",
                    software=SoftwareType.TOPAZ_VIDEO_AI,
                    params={"model": "proteus", "scale": 2},
                    timeout_seconds=1800,
                ),
                WorkflowStep(
                    name="stabilize",
                    task_type="stabilize",
                    software=SoftwareType.TOPAZ_VIDEO_AI,
                    params={"model": "video_stabilize"},
                    depends_on=["upscale"],
                    timeout_seconds=1800,
                ),
                WorkflowStep(
                    name="compose",
                    task_type="create_composition",
                    software=SoftwareType.AFTER_EFFECTS,
                    params={"width": 3840, "height": 2160},
                    depends_on=["stabilize"],
                    timeout_seconds=600,
                ),
                WorkflowStep(
                    name="export",
                    task_type="render",
                    software=SoftwareType.MEDIA_ENCODER,
                    params={"format": "h264", "bitrate": "50M"},
                    depends_on=["compose"],
                    timeout_seconds=3600,
                ),
            ],
            tags=["enhancement", "upscaling", "stabilization"],
            version="1.0.0",
        )

    def _create_color_grading_workflow(self) -> Workflow:
        return Workflow(
            name="color_grading",
            description="调色工作流: After Effects 初调 -> DaVinci Resolve 精调 -> Media Encoder 输出",
            steps=[
                WorkflowStep(
                    name="primary_correction",
                    task_type="color_correction",
                    software=SoftwareType.AFTER_EFFECTS,
                    params={"lut": "standard"},
                    timeout_seconds=300,
                ),
                WorkflowStep(
                    name="secondary_grading",
                    task_type="color_grading",
                    software=SoftwareType.DAVINCI_RESOLVE,
                    params={"grade": "cinematic"},
                    depends_on=["primary_correction"],
                    timeout_seconds=600,
                ),
                WorkflowStep(
                    name="final_export",
                    task_type="render",
                    software=SoftwareType.MEDIA_ENCODER,
                    params={"format": "prores422hq"},
                    depends_on=["secondary_grading"],
                    timeout_seconds=3600,
                ),
            ],
            tags=["color", "grading", "grading"],
            version="1.0.0",
        )

    def _create_3d_integration_workflow(self) -> Workflow:
        return Workflow(
            name="3d_integration",
            description="3D集成工作流: Blender 渲染 -> After Effects 合成 -> Media Encoder 输出",
            steps=[
                WorkflowStep(
                    name="render_3d",
                    task_type="render",
                    software=SoftwareType.BLENDER,
                    params={"engine": "cycles", "samples": 128},
                    timeout_seconds=7200,
                ),
                WorkflowStep(
                    name="composite",
                    task_type="composite",
                    software=SoftwareType.AFTER_EFFECTS,
                    params={"mode": "screen"},
                    depends_on=["render_3d"],
                    timeout_seconds=600,
                ),
                WorkflowStep(
                    name="final_output",
                    task_type="render",
                    software=SoftwareType.MEDIA_ENCODER,
                    params={"format": "h264"},
                    depends_on=["composite"],
                    timeout_seconds=3600,
                ),
            ],
            tags=["3d", "blender", "compositing"],
            version="1.0.0",
        )

    def _create_ai_generation_workflow(self) -> Workflow:
        return Workflow(
            name="ai_generation",
            description="AI生成工作流: RunwayML/Pika 生成 -> After Effects 后期 -> DaVinci Resolve 调色",
            steps=[
                WorkflowStep(
                    name="generate",
                    task_type="generate",
                    software=SoftwareType.RUNWAYML,
                    params={"model": "gen-3", "duration": 4},
                    timeout_seconds=1800,
                    fallback_strategy=FallbackStrategyType.NEXT_SOFTWARE,
                ),
                WorkflowStep(
                    name="post_process",
                    task_type="apply_effect",
                    software=SoftwareType.AFTER_EFFECTS,
                    params={"effect": "film_grain"},
                    depends_on=["generate"],
                    timeout_seconds=300,
                ),
                WorkflowStep(
                    name="color",
                    task_type="color_grading",
                    software=SoftwareType.DAVINCI_RESOLVE,
                    params={"grade": "vibrant"},
                    depends_on=["post_process"],
                    timeout_seconds=600,
                ),
            ],
            tags=["ai", "generation", "creative"],
            version="1.0.0",
        )

    def _create_batch_transcoding_workflow(self) -> Workflow:
        return Workflow(
            name="batch_transcoding",
            description="批量转码工作流: FFmpeg / Media Encoder 批量处理",
            steps=[
                WorkflowStep(
                    name="transcode_batch",
                    task_type="transcode",
                    software=SoftwareType.FFMPEG,
                    params={"codec": "libx264", "preset": "medium"},
                    timeout_seconds=7200,
                ),
            ],
            tags=["batch", "transcoding", "ffmpeg"],
            version="1.0.0",
        )

    def _create_full_pipeline_workflow(self) -> Workflow:
        return Workflow(
            name="full_pipeline",
            description="完整制作管线: 素材 -> 增强 -> 编辑 -> VFX -> 调色 -> 交付",
            steps=[
                WorkflowStep(
                    name="ingest",
                    task_type="import_asset",
                    software=SoftwareType.PREMIERE_PRO,
                    params={"bin": "Footage"},
                    timeout_seconds=300,
                ),
                WorkflowStep(
                    name="enhance",
                    task_type="enhance",
                    software=SoftwareType.TOPAZ_VIDEO_AI,
                    params={"denoise": True, "sharpen": 0.5},
                    depends_on=["ingest"],
                    timeout_seconds=1800,
                ),
                WorkflowStep(
                    name="edit",
                    task_type="edit",
                    software=SoftwareType.PREMIERE_PRO,
                    params={"sequence": "Main"},
                    depends_on=["enhance"],
                    timeout_seconds=1800,
                ),
                WorkflowStep(
                    name="vfx",
                    task_type="composite",
                    software=SoftwareType.AFTER_EFFECTS,
                    params={"comp": "Main"},
                    depends_on=["edit"],
                    timeout_seconds=3600,
                ),
                WorkflowStep(
                    name="color",
                    task_type="color_grading",
                    software=SoftwareType.DAVINCI_RESOLVE,
                    params={"grade": "final"},
                    depends_on=["vfx"],
                    timeout_seconds=1800,
                ),
                WorkflowStep(
                    name="deliver",
                    task_type="render",
                    software=SoftwareType.MEDIA_ENCODER,
                    params={"format": "h264", "quality": "high"},
                    depends_on=["color"],
                    timeout_seconds=7200,
                ),
            ],
            tags=["full", "pipeline", "production"],
            version="1.0.0",
        )

    def register(self, workflow: Workflow) -> str:
        self._templates[workflow.name] = workflow
        self.logger.info(f"Workflow template registered: {workflow.name}")
        return workflow.name

    def get(self, name: str) -> Optional[Workflow]:
        return self._templates.get(name)

    def list_templates(self, tags: Optional[List[str]] = None) -> List[Workflow]:
        if not tags:
            return list(self._templates.values())
        return [
            w for w in self._templates.values()
            if any(tag in w.tags for tag in tags)
        ]

    def unregister(self, name: str) -> bool:
        if name in self._templates:
            del self._templates[name]
            self.logger.info(f"Workflow template unregistered: {name}")
            return True
        return False


# ============================================================================
# 9. MONITORING & LOGGING
# ============================================================================

class UnifiedLogger:
    """统一日志系统"""

    def __init__(self, log_dir: str = "./logs", log_level: int = logging.INFO):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._loggers: Dict[str, logging.Logger] = {}
        self._setup_root_logger(log_level)

    def _setup_root_logger(self, level: int) -> None:
        root_logger = logging.getLogger("bridge")
        root_logger.setLevel(level)

        log_file = self.log_dir / "bridge.log"
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(level)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

    def get_logger(self, name: str) -> logging.Logger:
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(f"bridge.{name}")
        return self._loggers[name]


class ProgressTracker:
    """进度追踪器"""

    def __init__(self):
        self._tasks: Dict[str, float] = {}
        self._callbacks: List[Callable[[float, Dict[str, float]], None]] = []
        self._lock = threading.Lock()
        self.logger = logging.getLogger("bridge.progress")

    def update_progress(self, task_id: str, progress: float) -> None:
        with self._lock:
            self._tasks[task_id] = max(0.0, min(1.0, progress))
            overall = self._calculate_overall()
            for callback in self._callbacks:
                try:
                    callback(overall, dict(self._tasks))
                except Exception as e:
                    self.logger.error(f"Progress callback error: {e}")

    def _calculate_overall(self) -> float:
        if not self._tasks:
            return 0.0
        return sum(self._tasks.values()) / len(self._tasks)

    def get_overall_progress(self) -> float:
        with self._lock:
            return self._calculate_overall()

    def get_task_progress(self, task_id: str) -> float:
        with self._lock:
            return self._tasks.get(task_id, 0.0)

    def add_progress_callback(self, callback: Callable[[float, Dict[str, float]], None]) -> None:
        self._callbacks.append(callback)

    def remove_task(self, task_id: str) -> None:
        with self._lock:
            self._tasks.pop(task_id, None)


class StatusDashboard:
    """状态仪表板"""

    def __init__(self, bridge: 'MultiSoftwareBridge'):
        self.bridge = bridge
        self.logger = logging.getLogger("bridge.dashboard")

    def get_dashboard(self) -> Dict[str, Any]:
        software_statuses = self.bridge.get_all_software_status()
        queue_stats = self.bridge.task_scheduler.task_queue.get_stats()
        performance = self.bridge.performance_metrics.to_dict()
        health = self.bridge.health_monitor.get_overall_health()
        cache_stats = self.bridge.intermediate_cache.get_stats()

        return {
            "timestamp": datetime.now().isoformat(),
            "software": {
                "total": len(software_statuses),
                "connected": sum(
                    1 for s in software_statuses.values()
                    if s.status == ConnectionStatus.CONNECTED
                ),
                "details": {k.value: v.to_dict() for k, v in software_statuses.items()},
            },
            "tasks": {
                "queue": queue_stats,
                "performance": performance,
            },
            "health": health,
            "cache": cache_stats,
        }

    def print_dashboard(self) -> None:
        dashboard = self.get_dashboard()
        print("\n" + "=" * 60)
        print("MULTI-SOFTWARE BRIDGE - STATUS DASHBOARD")
        print("=" * 60)
        print(f"\nSoftware Status:")
        for sw, info in dashboard["software"]["details"].items():
            status_icon = "✓" if info["status"] == "connected" else "✗"
            print(f"  {status_icon} {sw:25s} {info['status']:15s} active: {info['active_tasks']}/{info['max_tasks']}")
        print(f"\nTask Queue:")
        queue = dashboard["tasks"]["queue"]
        print(f"  Pending: {queue['pending']}  Completed: {queue['completed']}  Failed: {queue['failed']}")
        print(f"\nPerformance:")
        perf = dashboard["tasks"]["performance"]
        print(f"  Success Rate: {perf['success_rate']*100:.1f}%")
        print(f"  Avg Execution Time: {perf['average_execution_time']:.1f}s")
        print(f"  Throughput: {perf['throughput_tasks_per_hour']:.1f} tasks/hour")
        print(f"\nSystem Health: {dashboard['health']['health_percentage']:.1f}%")
        print(f"\nCache: {dashboard['cache']['total_size_mb']:.1f} MB / {dashboard['cache']['max_size_gb']} GB")
        print("=" * 60 + "\n")


# ============================================================================
# 10. MAIN CLASS - MultiSoftwareBridge (Facade)
# ============================================================================

class MultiSoftwareBridge:
    """
    多软件桥接系统 - 统一API层

    提供统一的接口来连接、控制和编排多个创意软件。
    采用外观模式(Facade)，封装了复杂的内部实现。
    """

    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path("./config")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._adapters: Dict[SoftwareType, BaseSoftwareAdapter] = {}
        self._configs: Dict[SoftwareType, SoftwareConfig] = {}
        self._lock = threading.Lock()

        self._init_logging()
        self._init_resource_management()
        self._init_data_exchange()
        self._init_error_handling()
        self._init_task_orchestration()
        self._init_workflows()
        self._init_monitoring()

        self.logger.info("MultiSoftwareBridge initialized")

    def _init_logging(self) -> None:
        log_dir = self.config_dir / "logs"
        self.unified_logger = UnifiedLogger(str(log_dir))
        self.logger = self.unified_logger.get_logger("core")

    def _init_resource_management(self) -> None:
        self.resource_pool = ResourcePool()
        self.license_manager = LicenseManager()
        self.gpu_balancer = GPULoadBalancer()
        self.memory_manager = MemoryManager()
        self.concurrency_limiter = ConcurrencyLimiter()

    def _init_data_exchange(self) -> None:
        exchange_dir = self.config_dir / "exchange"
        self.file_exchange = FileExchange(str(exchange_dir))
        self.format_converter: Optional[FormatConverter] = None
        self.metadata_transfer = MetadataTransfer()
        cache_dir = self.config_dir / "cache"
        self.intermediate_cache = IntermediateCache(str(cache_dir))

    def _init_error_handling(self) -> None:
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        self.error_recovery: Optional[ErrorRecovery] = None
        self.timeout_manager = TimeoutManager()
        self.discovery = SoftwareDiscovery()
        self.version_compatibility = VersionCompatibility()
        self.plugin_inventory = PluginInventory()
        self.preset_sync = PresetSync(str(self.config_dir / "presets"))

    def _init_task_orchestration(self) -> None:
        self.task_scheduler = TaskScheduler(self)

    def _init_workflows(self) -> None:
        self.workflow_registry = WorkflowTemplateRegistry()

    def _init_monitoring(self) -> None:
        self.health_monitor = HealthMonitor(self, check_interval=30.0)
        self.progress_tracker = ProgressTracker()
        self.dashboard = StatusDashboard(self)
        self.performance_metrics = PerformanceMetrics()
        self.audit_trail: List[Dict[str, Any]] = []

    def configure_software(self, config: SoftwareConfig) -> bool:
        """配置软件"""
        self._configs[config.software] = config
        self.logger.info(f"Configured {config.software.value}")
        return True

    def connect_software(self, software: SoftwareType) -> bool:
        """连接指定软件"""
        with self._lock:
            if software in self._adapters:
                if self._adapters[software].get_status().status == ConnectionStatus.CONNECTED:
                    return True

            config = self._configs.get(software)
            if not config:
                config = SoftwareConfig(software=software)
                self._configs[software] = config

            if not config.enabled:
                self.logger.warning(f"{software.value} is disabled")
                return False

            adapter_class = ADAPTER_REGISTRY.get(software)
            if not adapter_class:
                self.logger.error(f"No adapter found for {software.value}")
                return False

            adapter = adapter_class(config, self.unified_logger.get_logger(software.value))
            success = adapter.connect()

            if success:
                self._adapters[software] = adapter
                self.concurrency_limiter.set_limit(software, config.max_concurrent_tasks)
                self.resource_pool.register_instance(software, {"config": config.to_dict()})
                if not self.format_converter:
                    self.format_converter = FormatConverter(self)
                if not self.error_recovery:
                    self.error_recovery = ErrorRecovery(self)
            else:
                self.logger.error(f"Failed to connect {software.value}")

            return success

    def disconnect_software(self, software: SoftwareType) -> bool:
        """断开指定软件连接"""
        with self._lock:
            if software in self._adapters:
                result = self._adapters[software].disconnect()
                del self._adapters[software]
                self.resource_pool.unregister_instance(software)
                self.logger.info(f"Disconnected {software.value}")
                return result
            return True

    def connect_all(self) -> Dict[SoftwareType, bool]:
        """连接所有已配置的软件"""
        results = {}
        for software in SoftwareType:
            config = self._configs.get(software)
            if config and config.enabled:
                results[software] = self.connect_software(software)
        return results

    def disconnect_all(self) -> Dict[SoftwareType, bool]:
        """断开所有软件连接"""
        results = {}
        for software in list(self._adapters.keys()):
            results[software] = self.disconnect_software(software)
        return results

    def get_adapter(self, software: SoftwareType) -> Optional[BaseSoftwareAdapter]:
        """获取软件适配器"""
        return self._adapters.get(software)

    def get_connected_software(self) -> List[SoftwareType]:
        """获取所有已连接的软件列表"""
        return [sw for sw, adapter in self._adapters.items()
                if adapter.get_status().status == ConnectionStatus.CONNECTED]

    def get_all_software_status(self) -> Dict[SoftwareType, SoftwareStatus]:
        """获取所有软件的状态"""
        statuses = {}
        for software in SoftwareType:
            if software in self._adapters:
                statuses[software] = self._adapters[software].get_status()
            else:
                statuses[software] = SoftwareStatus(
                    software=software,
                    status=ConnectionStatus.DISCONNECTED
                )
        return statuses

    def auto_select_software(self, task_type: str, params: Optional[Dict[str, Any]] = None) -> List[SoftwareType]:
        """
        根据任务类型自动选择最佳软件

        返回按推荐顺序排列的软件类型列表
        """
        params = params or {}
        capability_map = {
            "text_animation": SoftwareCapability.TEXT_ANIMATION,
            "create_text": SoftwareCapability.TEXT_ANIMATION,
            "transition": SoftwareCapability.TRANSITIONS,
            "apply_transition": SoftwareCapability.TRANSITIONS,
            "filter": SoftwareCapability.FILTERS_EFFECTS,
            "apply_effect": SoftwareCapability.FILTERS_EFFECTS,
            "effect": SoftwareCapability.FILTERS_EFFECTS,
            "render": SoftwareCapability.RENDERING,
            "export": SoftwareCapability.RENDERING,
            "composite": SoftwareCapability.COMPOSITING,
            "color_grading": SoftwareCapability.COLOR_GRADING,
            "color_correction": SoftwareCapability.COLOR_GRADING,
            "edit": SoftwareCapability.EDITING,
            "3d": SoftwareCapability.THREE_D,
            "render_3d": SoftwareCapability.THREE_D,
            "particles": SoftwareCapability.PARTICLES,
            "tracking": SoftwareCapability.MOTION_TRACKING,
            "keying": SoftwareCapability.KEYING,
            "rotoscoping": SoftwareCapability.ROTOSCOPING,
            "paint": SoftwareCapability.PAINTING,
            "image_manipulation": SoftwareCapability.IMAGE_MANIPULATION,
            "transcode": SoftwareCapability.VIDEO_ENCODING,
            "encode": SoftwareCapability.VIDEO_ENCODING,
            "audio": SoftwareCapability.AUDIO_PROCESSING,
            "generate": SoftwareCapability.AI_GENERATION,
            "ai_generate": SoftwareCapability.AI_GENERATION,
            "upscale": SoftwareCapability.UPSCALING,
            "stabilize": SoftwareCapability.STABILIZATION,
            "denoise": SoftwareCapability.DENOSING,
            "interpolate": SoftwareCapability.INTERPOLATION,
            "vector": SoftwareCapability.VECTOR_GRAPHICS,
            "import_asset": SoftwareCapability.PROJECT_MANAGEMENT,
            "batch": SoftwareCapability.BATCH_PROCESSING,
        }

        required_capability = capability_map.get(task_type)
        if not required_capability:
            return self.get_connected_software()

        scored_software = []
        for software in self.get_connected_software():
            adapter = self._adapters[software]
            capabilities = adapter.get_capabilities()
            if capabilities.has_capability(required_capability):
                score = self._calculate_software_score(software, task_type, params)
                scored_software.append((software, score))

        scored_software.sort(key=lambda x: x[1], reverse=True)
        return [sw for sw, score in scored_software]

    def _calculate_software_score(self, software: SoftwareType, task_type: str, params: Dict[str, Any]) -> float:
        """计算软件对特定任务的适配分数"""
        score = 0.0
        adapter = self._adapters.get(software)
        if not adapter:
            return 0.0

        config = self._configs.get(software)
        if config:
            score += config.priority_weight * 10

        status = adapter.get_status()
        if status.status != ConnectionStatus.CONNECTED:
            return 0.0

        score += max(0, (status.max_tasks - status.active_tasks)) * 5

        if status.gpu_usage < 0.5:
            score += 10
        elif status.gpu_usage < 0.8:
            score += 5

        specializations = {
            SoftwareType.AFTER_EFFECTS: ["text_animation", "composite", "effect", "particles", "tracking"],
            SoftwareType.PREMIERE_PRO: ["edit", "transitions", "batch"],
            SoftwareType.PHOTOSHOP: ["image_manipulation", "paint", "filter"],
            SoftwareType.DAVINCI_RESOLVE: ["color_grading", "edit", "keying"],
            SoftwareType.BLENDER: ["3d", "particles", "render_3d"],
            SoftwareType.TOPAZ_VIDEO_AI: ["upscale", "stabilize", "denoise", "interpolate"],
            SoftwareType.FFMPEG: ["transcode", "batch", "audio", "extract"],
            SoftwareType.RUNWAYML: ["generate", "ai_generate"],
            SoftwareType.PIKA: ["generate", "ai_generate"],
            SoftwareType.MEDIA_ENCODER: ["render", "export", "batch", "transcode"],
            SoftwareType.ILLUSTRATOR: ["vector", "image_manipulation"],
            SoftwareType.SILHOUETTE: ["rotoscoping", "paint", "keying"],
        }

        if software in specializations:
            if any(kw in task_type for kw in specializations[software]):
                score += 20

        return score

    def get_software_for_task(self, task_type: str, params: Optional[Dict[str, Any]] = None) -> Optional[SoftwareType]:
        """获取执行任务的最佳软件"""
        software_list = self.auto_select_software(task_type, params)
        return software_list[0] if software_list else None

    # ===== Unified API Layer =====

    def unified_import(self, file_path: str, target_software: Optional[SoftwareType] = None,
                       params: Optional[Dict[str, Any]] = None) -> Task:
        """统一导入 - 将素材导入到任意软件"""
        params = params or {}
        params["file_path"] = file_path

        if not target_software:
            target_software = self.get_software_for_task("import_asset", params)

        task = Task(
            task_type="import_asset",
            target_software=target_software,
            params=params,
            priority=TaskPriority.NORMAL,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("import", {"file": file_path, "software": target_software.value if target_software else None})
        return task

    def unified_export(self, source: str, output_path: str,
                       target_software: Optional[SoftwareType] = None,
                       params: Optional[Dict[str, Any]] = None) -> Task:
        """统一导出 - 从任意软件导出到目标格式"""
        params = params or {}
        params["source"] = source
        params["output_path"] = output_path

        if not target_software:
            target_software = self.get_software_for_task("render", params)

        task = Task(
            task_type="export",
            target_software=target_software,
            params=params,
            priority=TaskPriority.NORMAL,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("export", {"output": output_path, "software": target_software.value if target_software else None})
        return task

    def unified_text(self, text: str, target_software: Optional[SoftwareType] = None,
                     params: Optional[Dict[str, Any]] = None) -> Task:
        """统一文本动画 - 在目标软件中创建文本动画"""
        params = params or {}
        params["text"] = text

        if not target_software:
            target_software = self.get_software_for_task("text_animation", params)

        task = Task(
            task_type="text_animation",
            target_software=target_software,
            params=params,
            priority=TaskPriority.NORMAL,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("text_animation", {"text": text[:50], "software": target_software.value if target_software else None})
        return task

    def unified_transition(self, transition_type: str, target_software: Optional[SoftwareType] = None,
                           params: Optional[Dict[str, Any]] = None) -> Task:
        """统一转场 - 在目标软件中应用转场"""
        params = params or {}
        params["transition_type"] = transition_type

        if not target_software:
            target_software = self.get_software_for_task("transition", params)

        task = Task(
            task_type="transition",
            target_software=target_software,
            params=params,
            priority=TaskPriority.NORMAL,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("transition", {"type": transition_type, "software": target_software.value if target_software else None})
        return task

    def unified_filter(self, filter_name: str, target_software: Optional[SoftwareType] = None,
                       params: Optional[Dict[str, Any]] = None) -> Task:
        """统一滤镜 - 在目标软件中应用滤镜/效果"""
        params = params or {}
        params["filter_name"] = filter_name
        params["effect_name"] = filter_name

        if not target_software:
            target_software = self.get_software_for_task("filter", params)

        task = Task(
            task_type="apply_effect",
            target_software=target_software,
            params=params,
            priority=TaskPriority.NORMAL,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("filter", {"filter": filter_name, "software": target_software.value if target_software else None})
        return task

    def unified_render(self, comp_name: str, output_path: str,
                       target_software: Optional[SoftwareType] = None,
                       params: Optional[Dict[str, Any]] = None) -> Task:
        """统一渲染 - 在最优软件中渲染"""
        params = params or {}
        params["comp_name"] = comp_name
        params["output_path"] = output_path

        if not target_software:
            target_software = self.get_software_for_task("render", params)

        task = Task(
            task_type="render",
            target_software=target_software,
            params=params,
            priority=TaskPriority.HIGH,
        )
        self.task_scheduler.submit_task(task)
        self._log_audit("render", {"comp": comp_name, "software": target_software.value if target_software else None})
        return task

    def unified_batch(self, tasks: List[Dict[str, Any]],
                      target_software: Optional[SoftwareType] = None) -> List[Task]:
        """统一批量操作"""
        result_tasks = []
        for task_params in tasks:
            task_type = task_params.get("task_type", "generic")
            params = task_params.get("params", {})
            task = Task(
                task_type=task_type,
                target_software=target_software,
                params=params,
                priority=TaskPriority.LOW,
            )
            self.task_scheduler.submit_task(task)
            result_tasks.append(task)
        self._log_audit("batch", {"count": len(tasks)})
        return result_tasks

    def execute_workflow(self, workflow_name: str,
                         params: Optional[Dict[str, Any]] = None) -> Optional[List[Task]]:
        """
        执行多步骤多软件工作流

        Args:
            workflow_name: 工作流模板名称
            params: 工作流参数

        Returns:
            任务列表，如果工作流不存在则返回None
        """
        params = params or {}
        template = self.workflow_registry.get(workflow_name)
        if not template:
            self.logger.error(f"Workflow not found: {workflow_name}")
            return None

        self.logger.info(f"Executing workflow: {workflow_name}")
        self._log_audit("workflow_start", {"workflow": workflow_name})

        step_tasks: Dict[str, Task] = {}
        task_list: List[Task] = []

        for step in template.steps:
            step_params = {**step.params, **params.get(step.name, {})}
            task = Task(
                task_type=step.task_type,
                target_software=step.software,
                params=step_params,
                priority=TaskPriority.HIGH,
                dependencies=[step_tasks[dep].task_id for dep in step.depends_on if dep in step_tasks],
                timeout_seconds=step.timeout_seconds,
                metadata={"step_name": step.name, "workflow": workflow_name},
            )
            step_tasks[step.step_id] = task
            task_list.append(task)
            self.task_scheduler.submit_task(task)

        return task_list

    def start(self) -> None:
        """启动桥接系统"""
        self.task_scheduler.start(max_workers=4)
        self.health_monitor.start()
        self.logger.info("MultiSoftwareBridge started")

    def stop(self) -> None:
        """停止桥接系统"""
        self.health_monitor.stop()
        self.task_scheduler.stop()
        self.disconnect_all()
        self.logger.info("MultiSoftwareBridge stopped")

    def _log_audit(self, action: str, details: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(),
            "action": action,
            "details": details,
        }
        self.audit_trail.append(entry)
        if len(self.audit_trail) > 10000:
            self.audit_trail = self.audit_trail[-10000:]

    def get_audit_trail(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计追踪记录"""
        return list(self.audit_trail[-limit:])

    def save_config(self, filepath: Optional[str] = None) -> str:
        """保存配置到文件"""
        filepath = filepath or str(self.config_dir / "bridge_config.json")
        config_data = {
            "software": {k.value: v.to_dict() for k, v in self._configs.items()},
            "cache_max_size_gb": self.intermediate_cache.max_size_gb,
            "scheduler_workers": 4,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False, default=str)
        self.logger.info(f"Config saved to {filepath}")
        return filepath

    def load_config(self, filepath: Optional[str] = None) -> bool:
        """从文件加载配置"""
        filepath = filepath or str(self.config_dir / "bridge_config.json")
        if not os.path.exists(filepath):
            self.logger.warning(f"Config file not found: {filepath}")
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            for sw_str, sw_config in config_data.get("software", {}).items():
                try:
                    software = SoftwareType(sw_str)
                    config = SoftwareConfig(
                        software=software,
                        enabled=sw_config.get("enabled", True),
                        executable_path=sw_config.get("executable_path"),
                        install_dir=sw_config.get("install_dir"),
                        version=sw_config.get("version"),
                        api_endpoint=sw_config.get("api_endpoint"),
                        api_key=sw_config.get("api_key"),
                        max_concurrent_tasks=sw_config.get("max_concurrent_tasks", 1),
                        priority_weight=sw_config.get("priority_weight", 1.0),
                        additional_settings=sw_config.get("additional_settings", {}),
                    )
                    self._configs[software] = config
                except ValueError:
                    self.logger.warning(f"Unknown software type: {sw_str}")
            self.logger.info(f"Config loaded from {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            return False


# ============================================================================
# Demo / Main
# ============================================================================

def main():
    """演示 MultiSoftwareBridge 的使用"""
    print("\n" + "=" * 70)
    print("  Multi-Software Bridge - Demo")
    print("=" * 70)

    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_data")
    bridge = MultiSoftwareBridge(config_dir=config_dir)

    print("\n[1] 配置软件...")
    ae_config = SoftwareConfig(
        software=SoftwareType.AFTER_EFFECTS,
        enabled=True,
        max_concurrent_tasks=2,
        priority_weight=1.0,
        additional_settings={"jsx_watch_folder": os.path.join(config_dir, "ae_watch")},
    )
    bridge.configure_software(ae_config)

    ffmpeg_config = SoftwareConfig(
        software=SoftwareType.FFMPEG,
        enabled=True,
        max_concurrent_tasks=4,
        priority_weight=1.5,
    )
    bridge.configure_software(ffmpeg_config)

    me_config = SoftwareConfig(
        software=SoftwareType.MEDIA_ENCODER,
        enabled=True,
        max_concurrent_tasks=2,
        priority_weight=1.0,
    )
    bridge.configure_software(me_config)

    topaz_config = SoftwareConfig(
        software=SoftwareType.TOPAZ_VIDEO_AI,
        enabled=True,
        max_concurrent_tasks=1,
        priority_weight=1.2,
    )
    bridge.configure_software(topaz_config)

    resolve_config = SoftwareConfig(
        software=SoftwareType.DAVINCI_RESOLVE,
        enabled=True,
        max_concurrent_tasks=1,
        priority_weight=1.0,
    )
    bridge.configure_software(resolve_config)

    blender_config = SoftwareConfig(
        software=SoftwareType.BLENDER,
        enabled=True,
        max_concurrent_tasks=1,
        priority_weight=1.0,
    )
    bridge.configure_software(blender_config)

    runway_config = SoftwareConfig(
        software=SoftwareType.RUNWAYML,
        enabled=True,
        max_concurrent_tasks=2,
        priority_weight=0.8,
    )
    bridge.configure_software(runway_config)

    print("  ✓ 软件配置完成")

    print("\n[2] 连接软件...")
    results = bridge.connect_all()
    connected = sum(1 for v in results.values() if v)
    print(f"  ✓ 已连接 {connected}/{len(results)} 个软件")
    for sw, ok in results.items():
        status = "✓ 已连接" if ok else "✗ 未连接"
        print(f"    {status} - {sw.value}")

    print("\n[3] 启动桥接系统...")
    bridge.start()
    print("  ✓ 任务调度器已启动")
    print("  ✓ 健康监控器已启动")

    print("\n[4] 统一API演示...")

    print("\n  4.1 统一导入 (unified_import)")
    import_task = bridge.unified_import(
        file_path="input_video.mp4",
        params={"bin": "Footage", "interpret_footage": True}
    )
    print(f"    任务ID: {import_task.task_id}")
    print(f"    任务类型: {import_task.task_type}")
    print(f"    目标软件: {import_task.target_software.value if import_task.target_software else 'auto'}")

    print("\n  4.2 统一文本动画 (unified_text)")
    text_task = bridge.unified_text(
        text="Hello Multi-Software Bridge!",
        params={"font": "Arial", "font_size": 72, "color": "#FFFFFF"}
    )
    print(f"    任务ID: {text_task.task_id}")
    print(f"    目标软件: {text_task.target_software.value if text_task.target_software else 'auto'}")

    print("\n  4.3 统一滤镜 (unified_filter)")
    filter_task = bridge.unified_filter(
        filter_name="Gaussian Blur",
        params={"blurriness": 10.0}
    )
    print(f"    任务ID: {filter_task.task_id}")
    print(f"    目标软件: {filter_task.target_software.value if filter_task.target_software else 'auto'}")

    print("\n  4.4 统一渲染 (unified_render)")
    render_task = bridge.unified_render(
        comp_name="Main Comp",
        output_path="output_render.mov",
        params={"quality": "high", "format": "h264"}
    )
    print(f"    任务ID: {render_task.task_id}")
    print(f"    目标软件: {render_task.target_software.value if render_task.target_software else 'auto'}")

    print("\n  4.5 智能软件选择 (auto_select_software)")
    task_types_to_test = [
        "text_animation",
        "color_grading",
        "transcode",
        "3d",
        "upscale",
        "generate",
    ]
    for task_type in task_types_to_test:
        best = bridge.get_software_for_task(task_type)
        best_list = bridge.auto_select_software(task_type)
        best_names = [s.value for s in best_list[:3]]
        print(f"    {task_type:20s} → 最佳: {best.value if best else 'N/A':20s} 候选: {best_names}")

    print("\n[5] 工作流模板...")
    templates = bridge.workflow_registry.list_templates()
    print(f"  已注册 {len(templates)} 个工作流模板:")
    for wf in templates:
        print(f"    • {wf.name:25s} - {wf.description[:50]}...")
        print(f"      步骤数: {len(wf.steps)}, 标签: {wf.tags}")

    print("\n  5.1 执行工作流 (footage_enhancement)")
    workflow_tasks = bridge.execute_workflow(
        "footage_enhancement",
        params={
            "upscale": {"scale": 2, "model": "proteus"},
            "export": {"format": "h264", "bitrate": "50M"},
        }
    )
    if workflow_tasks:
        print(f"    已提交 {len(workflow_tasks)} 个任务:")
        for i, t in enumerate(workflow_tasks):
            step_name = t.metadata.get("step_name", f"step_{i}")
            print(f"      [{i+1}] {step_name:20s} → {t.target_software.value if t.target_software else 'auto'}")

    print("\n[6] 资源管理...")
    print(f"  GPU设备: {len(bridge.gpu_balancer.get_status())} 个")
    print(f"  许可证状态: {len(bridge.license_manager._licenses)} 个已注册")
    print(f"  内存使用: {bridge.memory_manager.get_usage()['used_mb']:.0f} MB")

    print("\n[7] 状态仪表板...")
    bridge.dashboard.print_dashboard()

    print("\n[8] 等待任务执行 (3秒)...")
    time.sleep(3)

    print("\n[9] 任务状态...")
    all_tasks = [
        import_task, text_task, filter_task, render_task,
    ]
    if workflow_tasks:
        all_tasks.extend(workflow_tasks)

    for t in all_tasks:
        task_info = bridge.task_scheduler.get_task(t.task_id)
        status = task_info.status.value if task_info else "unknown"
        print(f"  {t.task_id[:8]}... {t.task_type:20s} {status:12s}")

    print("\n[10] 性能指标...")
    perf = bridge.performance_metrics.to_dict()
    print(f"  总执行任务: {perf['total_tasks_executed']}")
    print(f"  成功率: {perf['success_rate']*100:.1f}%")
    print(f"  平均执行时间: {perf['average_execution_time']:.2f}s")

    print("\n[11] 保存配置...")
    config_path = bridge.save_config()
    print(f"  ✓ 配置已保存到: {config_path}")

    print("\n[12] 软件能力详情...")
    for sw in bridge.get_connected_software():
        adapter = bridge.get_adapter(sw)
        if adapter:
            caps = adapter.get_capabilities()
            cap_list = [c.value for c in list(caps.capabilities)[:6]]
            print(f"  {sw.value:20s} - {len(caps.capabilities)} 种能力: {', '.join(cap_list)}...")

    print("\n[13] 停止桥接系统...")
    bridge.stop()
    print("  ✓ 桥接系统已停止")

    print("\n" + "=" * 70)
    print("  Demo 完成!")
    print("=" * 70)
    print("\n主要特性总结:")
    print("  ✓ 12种软件适配器 (AE, PR, PS, Resolve, Blender, Topaz, FFmpeg,")
    print("    RunwayML, Pika, Media Encoder, Illustrator, Silhouette)")
    print("  ✓ 优先级任务队列 + 依赖管理")
    print("  ✓ 智能软件自动选择")
    print("  ✓ 6个预定义工作流模板")
    print("  ✓ 熔断器 + 错误恢复机制")
    print("  ✓ GPU负载均衡 + 并发限制")
    print("  ✓ 格式转换 + 元数据传递")
    print("  ✓ 中间结果缓存")
    print("  ✓ 统一API层 (导入/导出/文本/转场/滤镜/渲染)")
    print("  ✓ 健康监控 + 性能指标")
    print("  ✓ 状态仪表板")
    print("  ✓ 审计追踪")
    print()


if __name__ == "__main__":
    main()
