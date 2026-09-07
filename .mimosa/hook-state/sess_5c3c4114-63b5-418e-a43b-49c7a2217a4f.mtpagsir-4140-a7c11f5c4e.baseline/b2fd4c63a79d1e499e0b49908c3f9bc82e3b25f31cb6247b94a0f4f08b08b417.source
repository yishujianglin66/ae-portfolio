"""Plugin manager - discovery, loading, registration, and execution.

Supports:
- Built-in plugin auto-discovery from ``src/plugins/builtin/``
- External plugin loading from a directory
- Programmatic registration via ``register()``
- Priority-ordered hook execution
- Plugin enable/disable at runtime
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from src.plugins.base import (
    BasePlugin,
    FilterPlugin,
    HookPlugin,
    PhasePlugin,
    PluginContext,
    PluginPriority,
    PluginState,
)


class PluginManager:
    """Central plugin manager.

    Manages the full plugin lifecycle:
    1. Discovery (scan directories or import builtins)
    2. Loading (instantiate and call ``init()``)
    3. Registration (add to hook/phase/filter registries)
    4. Execution (invoke hooks in priority order)
    5. Unloading (call ``cleanup()`` and remove)
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._hook_plugins: list[HookPlugin] = []
        self._phase_plugins: dict[str, PhasePlugin] = {}  # phase.value -> plugin
        self._filter_plugins: dict[str, list[FilterPlugin]] = {}  # target_phase.value -> [plugins]
        self._discovered: bool = False

    # ============================================================
    # Properties
    # ============================================================

    @property
    def plugins(self) -> dict[str, BasePlugin]:
        """All registered plugins (name -> instance)."""
        return dict(self._plugins)

    @property
    def hook_plugins(self) -> list[HookPlugin]:
        """All hook plugins sorted by priority."""
        return sorted(self._hook_plugins, key=lambda p: p.priority)

    @property
    def phase_plugins(self) -> dict[str, PhasePlugin]:
        """Phase plugins (phase.value -> plugin)."""
        return dict(self._phase_plugins)

    @property
    def filter_plugins(self) -> dict[str, list[FilterPlugin]]:
        """Filter plugins grouped by target phase."""
        return {k: sorted(v, key=lambda p: p.priority) for k, v in self._filter_plugins.items()}

    # ============================================================
    # Registration
    # ============================================================

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin instance.

        Raises:
            ValueError: If a plugin with the same name already exists.
        """
        if plugin.name in self._plugins:
            raise ValueError(f"Plugin '{plugin.name}' is already registered")
        self._plugins[plugin.name] = plugin

        if isinstance(plugin, HookPlugin):
            self._hook_plugins.append(plugin)
            self._hook_plugins.sort(key=lambda p: p.priority)
            logger.debug(f"[PluginManager] Registered hook plugin: {plugin.name}")

        if isinstance(plugin, PhasePlugin):
            phase_key = plugin.phase.value
            if phase_key in self._phase_plugins:
                raise ValueError(
                    f"Phase '{phase_key}' already has a plugin: "
                    f"{self._phase_plugins[phase_key].name}"
                )
            self._phase_plugins[phase_key] = plugin
            logger.debug(f"[PluginManager] Registered phase plugin: {plugin.name} -> {phase_key}")

        if isinstance(plugin, FilterPlugin):
            target_key = plugin.target_phase.value
            self._filter_plugins.setdefault(target_key, []).append(plugin)
            self._filter_plugins[target_key].sort(key=lambda p: p.priority)
            logger.debug(f"[PluginManager] Registered filter plugin: {plugin.name} -> {target_key}")

        logger.info(f"[PluginManager] Registered plugin: {plugin.name} v{plugin.version}")

    def unregister(self, name: str) -> Optional[BasePlugin]:
        """Unregister and cleanup a plugin by name.

        Returns the plugin instance if found, None otherwise.
        """
        plugin = self._plugins.pop(name, None)
        if plugin is None:
            return None

        if isinstance(plugin, HookPlugin):
            self._hook_plugins = [p for p in self._hook_plugins if p.name != name]

        if isinstance(plugin, PhasePlugin):
            self._phase_plugins.pop(plugin.phase.value, None)

        if isinstance(plugin, FilterPlugin):
            target = plugin.target_phase.value
            if target in self._filter_plugins:
                self._filter_plugins[target] = [
                    p for p in self._filter_plugins[target] if p.name != name
                ]
                if not self._filter_plugins[target]:
                    del self._filter_plugins[target]

        logger.info(f"[PluginManager] Unregistered plugin: {name}")
        return plugin

    # ============================================================
    # Discovery and loading
    # ============================================================

    def discover_builtin(self) -> list[BasePlugin]:
        """Discover and load built-in plugins from ``src/plugins/builtin/``.

        Returns list of loaded plugin instances.
        """
        builtin_dir = Path(__file__).parent / "builtin"
        if not builtin_dir.exists():
            logger.debug("[PluginManager] No builtin plugins directory found")
            return []

        loaded: list[BasePlugin] = []
        for py_file in sorted(builtin_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"src.plugins.builtin.{py_file.stem}"
            try:
                module = importlib.import_module(module_name)
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BasePlugin)
                        and obj not in (BasePlugin, HookPlugin, PhasePlugin, FilterPlugin)
                        and not inspect.isabstract(obj)
                    ):
                        instance = obj()
                        self.register(instance)
                        loaded.append(instance)
            except Exception as e:
                logger.warning(f"[PluginManager] Failed to load builtin '{py_file.stem}': {e}")

        self._discovered = True
        logger.info(f"[PluginManager] Discovered {len(loaded)} builtin plugins")
        return loaded

    def load_from_directory(self, plugin_dir: Path | str) -> list[BasePlugin]:
        """Load plugins from an external directory.

        Each ``.py`` file in the directory is scanned for BasePlugin subclasses.
        """
        plugin_dir = Path(plugin_dir)
        if not plugin_dir.is_dir():
            logger.warning(f"[PluginManager] Plugin directory not found: {plugin_dir}")
            return []

        loaded: list[BasePlugin] = []
        import sys

        if str(plugin_dir) not in sys.path:
            sys.path.insert(0, str(plugin_dir))

        for py_file in sorted(plugin_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = py_file.stem
            try:
                if module_name in sys.modules:
                    module = importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, BasePlugin)
                        and obj not in (BasePlugin, HookPlugin, PhasePlugin, FilterPlugin)
                        and not inspect.isabstract(obj)
                    ):
                        instance = obj()
                        self.register(instance)
                        loaded.append(instance)
            except Exception as e:
                logger.warning(f"[PluginManager] Failed to load '{py_file.name}': {e}")

        logger.info(f"[PluginManager] Loaded {len(loaded)} plugins from {plugin_dir}")
        return loaded

    async def init_all(self) -> None:
        """Initialize all registered plugins."""
        for plugin in self._plugins.values():
            try:
                await plugin.init()
            except Exception as e:
                logger.error(f"[PluginManager] Init failed for '{plugin.name}': {e}")
                plugin._state = PluginState.ERROR
                plugin.disable()

    async def cleanup_all(self) -> None:
        """Cleanup all registered plugins."""
        for plugin in list(self._plugins.values()):
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"[PluginManager] Cleanup failed for '{plugin.name}': {e}")

    # ============================================================
    # Hook execution
    # ============================================================

    async def run_hooks(
        self,
        hook_name: str,
        ctx: PluginContext,
    ) -> Optional[Any]:
        """Run a named hook on all enabled hook plugins in priority order.

        For ``after_phase`` hooks, the first non-None return value
        (a modified PhaseResult) is returned.
        """
        result: Optional[Any] = None
        for plugin in self.hook_plugins:
            if not plugin.enabled:
                continue
            try:
                hook = getattr(plugin, hook_name)
                ret = await hook(ctx)
                if ret is not None and hook_name == "after_phase":
                    result = ret
                    ctx.phase_result = ret
            except Exception as e:
                logger.error(
                    f"[PluginManager] Hook '{hook_name}' failed in "
                    f"'{plugin.name}': {e}"
                )
        return result

    async def run_filters(self, ctx: PluginContext) -> Optional[Any]:
        """Run filter plugins for the current phase in priority order.

        Returns the final (possibly modified) PhaseResult.
        """
        if ctx.phase is None:
            return None
        phase_key = ctx.phase.value
        filters = self._filter_plugins.get(phase_key, [])
        result = ctx.phase_result
        for f in filters:
            if not f.enabled:
                continue
            try:
                result = await f.filter(ctx)
                ctx.phase_result = result
            except Exception as e:
                logger.error(f"[PluginManager] Filter '{f.name}' failed: {e}")
        return result

    def get_phase_plugin(self, phase_value: str) -> Optional[PhasePlugin]:
        """Get the phase plugin for a given phase value."""
        return self._phase_plugins.get(phase_value)

    # ============================================================
    # State queries
    # ============================================================

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def list_plugins(self) -> list[dict[str, Any]]:
        """List all registered plugins with metadata."""
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "type": type(p).__name__,
                "priority": int(p.priority),
                "enabled": p.enabled,
                "state": p._state.value,
            }
            for p in self._plugins.values()
        ]

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin by name. Returns True if found."""
        p = self._plugins.get(name)
        if p:
            p.enable()
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin by name. Returns True if found."""
        p = self._plugins.get(name)
        if p:
            p.disable()
            return True
        return False


# ============================================================
# Global singleton
# ============================================================

plugin_manager = PluginManager()
