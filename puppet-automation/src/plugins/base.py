"""Plugin base classes and interfaces.

Defines the contract for all pipeline plugins:
- HookPlugin: lifecycle event hooks (pre-pipeline, pre/post-phase, etc.)
- PhasePlugin: custom phase implementation
- FilterPlugin: post-processing filter on phase output
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Optional

from src.models.pipeline import (
    PhaseResult,
    PipelineJob,
    PipelinePhase,
    PipelineState,
    TaskStatus,
)

# ============================================================
# Plugin state and priority
# ============================================================

class PluginState(str, Enum):
    """Plugin lifecycle state."""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


class PluginPriority(IntEnum):
    """Plugin execution priority (lower = earlier)."""
    HIGHEST = 0
    HIGH = 10
    NORMAL = 50
    LOW = 90
    LOWEST = 100


# ============================================================
# Plugin context
# ============================================================

@dataclass
class PluginContext:
    """Context passed to plugins during execution.

    Provides access to the orchestrator's engines, work directory,
    and shared state so plugins can interact with the pipeline.
    """
    job: PipelineJob
    state: PipelineState
    engines: dict[str, Any]
    work_dir: Path
    phase: PipelinePhase | None = None
    phase_result: PhaseResult | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Base plugin
# ============================================================

class BasePlugin(ABC):
    """Base class for all plugins.

    Subclasses must implement ``name`` and ``version`` properties.
    Override ``init`` and ``cleanup`` for lifecycle management.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin identifier."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version string."""

    @property
    def description(self) -> str:
        """Human-readable description."""
        return ""

    @property
    def priority(self) -> PluginPriority:
        """Execution priority (lower = earlier)."""
        return PluginPriority.NORMAL

    @property
    def enabled(self) -> bool:
        """Whether this plugin is enabled."""
        return self._enabled

    def __init__(self) -> None:
        self._enabled: bool = True
        self._state: PluginState = PluginState.UNLOADED

    async def init(self) -> None:
        """Called when plugin is loaded. Override for setup."""
        self._state = PluginState.LOADED

    async def cleanup(self) -> None:
        """Called when plugin is unloaded. Override for teardown."""
        self._state = PluginState.UNLOADED

    def enable(self) -> None:
        self._enabled = True
        self._state = PluginState.ENABLED

    def disable(self) -> None:
        self._enabled = False
        self._state = PluginState.DISABLED


# ============================================================
# Hook plugin - lifecycle event hooks
# ============================================================

class HookPlugin(BasePlugin):
    """Plugin that subscribes to pipeline lifecycle hooks.

    Override any combination of the hook methods. Each hook receives
    a :class:`PluginContext` with current pipeline state.
    """

    async def on_job_created(self, ctx: PluginContext) -> None:
        """Called when a job is created (before pipeline starts)."""

    async def on_pipeline_start(self, ctx: PluginContext) -> None:
        """Called before the first phase executes."""

    async def before_phase(self, ctx: PluginContext) -> None:
        """Called before each phase executes."""

    async def after_phase(self, ctx: PluginContext) -> PhaseResult | None:
        """Called after each phase completes.

        Can return a modified PhaseResult to override the original.
        Return None to keep the original result.
        """
        return None

    async def on_pipeline_success(self, ctx: PluginContext) -> None:
        """Called after successful pipeline completion."""

    async def on_pipeline_failure(self, ctx: PluginContext) -> None:
        """Called when pipeline fails."""

    async def on_pipeline_cancel(self, ctx: PluginContext) -> None:
        """Called when pipeline is cancelled."""


# ============================================================
# Phase plugin - custom phase implementation
# ============================================================

class PhasePlugin(BasePlugin):
    """Plugin that implements a custom pipeline phase.

    Register with a unique PipelinePhase to extend the pipeline.
    """

    @property
    @abstractmethod
    def phase(self) -> PipelinePhase:
        """The pipeline phase this plugin implements."""

    @abstractmethod
    async def execute(self, ctx: PluginContext) -> PhaseResult:
        """Execute the phase and return result."""


# ============================================================
# Filter plugin - post-processing filter
# ============================================================

class FilterPlugin(BasePlugin):
    """Plugin that filters/processes phase output.

    Filters run after a phase completes, can modify files or metadata.
    """

    @property
    @abstractmethod
    def target_phase(self) -> PipelinePhase:
        """Which phase's output to filter."""

    @abstractmethod
    async def filter(self, ctx: PluginContext) -> PhaseResult:
        """Process the phase output and return (possibly modified) result."""
