"""Plugin system for puppet automation pipeline.

Provides extensible hook-based plugin architecture:
- HookPlugin: subscribes to pipeline lifecycle events
- PhasePlugin: implements custom pipeline phases
- FilterPlugin: post-processing filters

Plugin discovery supports both entry-point based and directory scanning.
"""

from src.plugins.base import (
    BasePlugin,
    FilterPlugin,
    HookPlugin,
    PhasePlugin,
    PluginContext,
    PluginPriority,
    PluginState,
)
from src.plugins.manager import PluginManager, plugin_manager

__all__ = [
    "BasePlugin",
    "HookPlugin",
    "PhasePlugin",
    "FilterPlugin",
    "PluginContext",
    "PluginState",
    "PluginPriority",
    "PluginManager",
    "plugin_manager",
]
