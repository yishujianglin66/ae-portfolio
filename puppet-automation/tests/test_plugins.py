"""Tests for the plugin system.

Covers:
- Plugin base classes and interfaces
- PluginManager registration/unregistration
- Built-in plugin discovery
- Hook execution order and priority
- Filter plugin execution
- Plugin enable/disable
- Orchestrator integration (plugins fire during pipeline run)
"""

import asyncio
from pathlib import Path
from typing import Optional

import pytest
from src.models.pipeline import (
    PhaseResult,
    PipelineJob,
    PipelinePhase,
    PipelineState,
    TaskStatus,
)
from src.plugins.base import (
    BasePlugin,
    FilterPlugin,
    HookPlugin,
    PhasePlugin,
    PluginContext,
    PluginPriority,
    PluginState,
)
from src.plugins.manager import PluginManager

# ============================================================
# Test fixtures
# ============================================================

@pytest.fixture
def manager():
    """Fresh PluginManager for each test."""
    return PluginManager()


@pytest.fixture
def sample_job():
    """Sample pipeline job."""
    return PipelineJob(
        job_id="test_plugin_job",
        input_video="test.mp4",
        phases=[
            PipelinePhase.PHASE1_PREPROCESS,
            PipelinePhase.PHASE2_KEYING,
            PipelinePhase.PHASE3_STYLIZE,
            PipelinePhase.PHASE4_RENDER,
        ],
    )


@pytest.fixture
def sample_state():
    """Sample pipeline state."""
    return PipelineState(
        job_id="test_plugin_job",
        overall_status=TaskStatus.PENDING,
        phase_results={},
    )


@pytest.fixture
def sample_ctx(sample_job, sample_state, tmp_path):
    """Sample plugin context."""
    return PluginContext(
        job=sample_job,
        state=sample_state,
        engines={},
        work_dir=tmp_path,
    )


# ============================================================
# Simple test plugins
# ============================================================

class SimpleHookPlugin(HookPlugin):
    """Test hook plugin that records calls."""
    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    @property
    def name(self): return "simple_hook"
    @property
    def version(self): return "1.0.0"

    async def on_job_created(self, ctx): self.calls.append("on_job_created")
    async def on_pipeline_start(self, ctx): self.calls.append("on_pipeline_start")
    async def before_phase(self, ctx): self.calls.append("before_phase")
    async def after_phase(self, ctx): self.calls.append("after_phase")
    async def on_pipeline_success(self, ctx): self.calls.append("on_pipeline_success")
    async def on_pipeline_failure(self, ctx): self.calls.append("on_pipeline_failure")
    async def on_pipeline_cancel(self, ctx): self.calls.append("on_pipeline_cancel")


class HighPriorityPlugin(HookPlugin):
    """High priority test plugin."""
    @property
    def name(self): return "high_priority"
    @property
    def version(self): return "1.0.0"
    @property
    def priority(self): return PluginPriority.HIGH

    def __init__(self):
        super().__init__()
        self.order: list[int] = []

    async def on_pipeline_start(self, ctx):
        self.order.append(1)


class LowPriorityPlugin(HookPlugin):
    """Low priority test plugin."""
    @property
    def name(self): return "low_priority"
    @property
    def version(self): return "1.0.0"
    @property
    def priority(self): return PluginPriority.LOW

    def __init__(self):
        super().__init__()
        self.order: list[int] = []

    async def on_pipeline_start(self, ctx):
        self.order.append(2)


class ResultModifierPlugin(HookPlugin):
    """Modifies phase result in after_phase hook."""
    @property
    def name(self): return "result_modifier"
    @property
    def version(self): return "1.0.0"

    async def after_phase(self, ctx):
        if ctx.phase_result:
            modified = PhaseResult(
                phase=ctx.phase_result.phase,
                status=ctx.phase_result.status,
                metadata={"modified_by": "result_modifier"},
            )
            return modified
        return None


class TestFilterPlugin(FilterPlugin):
    """Test filter plugin."""
    @property
    def name(self): return "test_filter"
    @property
    def version(self): return "1.0.0"
    @property
    def target_phase(self): return PipelinePhase.PHASE1_PREPROCESS

    def __init__(self):
        super().__init__()
        self.filter_called = False

    async def filter(self, ctx):
        self.filter_called = True
        if ctx.phase_result:
            ctx.phase_result.metadata = {
                **(ctx.phase_result.metadata or {}),
                "filtered": True,
            }
            return ctx.phase_result
        return None


# ============================================================
# Plugin base class tests
# ============================================================

class TestPluginBase:

    def test_hook_plugin_name_version_required(self):
        """Plugins must implement name and version."""
        with pytest.raises(TypeError):
            HookPlugin()  # Cannot instantiate abstract class

    def test_plugin_enable_disable(self):
        plugin = SimpleHookPlugin()
        assert plugin.enabled is True
        plugin.disable()
        assert plugin.enabled is False
        plugin.enable()
        assert plugin.enabled is True

    @pytest.mark.asyncio
    async def test_plugin_init_cleanup(self):
        plugin = SimpleHookPlugin()
        assert plugin._state == PluginState.UNLOADED
        await plugin.init()
        assert plugin._state == PluginState.LOADED
        await plugin.cleanup()
        assert plugin._state == PluginState.UNLOADED

    def test_priority_defaults(self):
        plugin = SimpleHookPlugin()
        assert plugin.priority == PluginPriority.NORMAL


# ============================================================
# PluginManager tests
# ============================================================

class TestPluginManager:

    def test_register_hook_plugin(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        assert "simple_hook" in manager.plugins
        assert plugin in manager.hook_plugins

    def test_register_duplicate_raises(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        with pytest.raises(ValueError, match="already registered"):
            manager.register(SimpleHookPlugin())

    def test_unregister_plugin(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        removed = manager.unregister("simple_hook")
        assert removed is plugin
        assert "simple_hook" not in manager.plugins
        assert plugin not in manager.hook_plugins

    def test_unregister_nonexistent(self, manager):
        result = manager.unregister("nonexistent")
        assert result is None

    def test_priority_ordering(self, manager):
        """Plugins should be sorted by priority."""
        low = LowPriorityPlugin()
        high = HighPriorityPlugin()
        manager.register(low)
        manager.register(high)
        ordered = manager.hook_plugins
        assert ordered[0] is high  # HIGH priority = lower number = first
        assert ordered[1] is low

    def test_enable_disable_plugin(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        assert manager.disable_plugin("simple_hook") is True
        assert plugin.enabled is False
        assert manager.enable_plugin("simple_hook") is True
        assert plugin.enabled is True

    def test_enable_nonexistent_returns_false(self, manager):
        assert manager.disable_plugin("nonexistent") is False
        assert manager.enable_plugin("nonexistent") is False

    def test_list_plugins(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        plugins = manager.list_plugins()
        assert len(plugins) == 1
        assert plugins[0]["name"] == "simple_hook"
        assert plugins[0]["type"] == "SimpleHookPlugin"
        assert plugins[0]["enabled"] is True

    def test_get_plugin(self, manager):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        assert manager.get_plugin("simple_hook") is plugin
        assert manager.get_plugin("nonexistent") is None


# ============================================================
# Hook execution tests
# ============================================================

class TestHookExecution:

    @pytest.mark.asyncio
    async def test_all_hooks_fire(self, manager, sample_ctx):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        await manager.init_all()

        await manager.run_hooks("on_job_created", sample_ctx)
        await manager.run_hooks("on_pipeline_start", sample_ctx)
        await manager.run_hooks("before_phase", sample_ctx)
        await manager.run_hooks("after_phase", sample_ctx)
        await manager.run_hooks("on_pipeline_success", sample_ctx)
        await manager.run_hooks("on_pipeline_failure", sample_ctx)
        await manager.run_hooks("on_pipeline_cancel", sample_ctx)

        assert plugin.calls == [
            "on_job_created",
            "on_pipeline_start",
            "before_phase",
            "after_phase",
            "on_pipeline_success",
            "on_pipeline_failure",
            "on_pipeline_cancel",
        ]

    @pytest.mark.asyncio
    async def test_disabled_plugin_not_executed(self, manager, sample_ctx):
        plugin = SimpleHookPlugin()
        manager.register(plugin)
        plugin.disable()

        await manager.run_hooks("on_pipeline_start", sample_ctx)
        assert plugin.calls == []

    @pytest.mark.asyncio
    async def test_hook_error_does_not_crash(self, manager, sample_ctx):
        class ErrorPlugin(HookPlugin):
            @property
            def name(self): return "error_plugin"
            @property
            def version(self): return "1.0.0"

            async def on_pipeline_start(self, ctx):
                raise RuntimeError("Intentional error")

        manager.register(ErrorPlugin())
        # Should not raise
        await manager.run_hooks("on_pipeline_start", sample_ctx)

    @pytest.mark.asyncio
    async def test_after_phase_can_modify_result(self, manager, sample_ctx):
        plugin = ResultModifierPlugin()
        manager.register(plugin)

        # Set up context with a phase result
        original = PhaseResult(
            phase=PipelinePhase.PHASE1_PREPROCESS,
            status=TaskStatus.SUCCESS,
            metadata={"original": True},
        )
        sample_ctx.phase = PipelinePhase.PHASE1_PREPROCESS
        sample_ctx.phase_result = original

        result = await manager.run_hooks("after_phase", sample_ctx)
        assert result is not None
        assert result.metadata == {"modified_by": "result_modifier"}

    @pytest.mark.asyncio
    async def test_priority_execution_order(self, manager, sample_ctx):
        """High priority plugin should execute before low priority."""
        high = HighPriorityPlugin()
        low = LowPriorityPlugin()
        manager.register(low)
        manager.register(high)

        # Both plugins append to their own lists, we need a shared list
        order: list[str] = []

        class OrderTracker(HookPlugin):
            @property
            def name(self): return f"tracker_{self._label}"
            @property
            def version(self): return "1.0.0"

            def __init__(self, label, pri):
                super().__init__()
                self._label = label
                self._pri = pri

            @property
            def priority(self): return self._pri

            async def on_pipeline_start(self, ctx):
                order.append(self._label)

        manager2 = PluginManager()
        manager2.register(OrderTracker("low", PluginPriority.LOW))
        manager2.register(OrderTracker("high", PluginPriority.HIGH))
        await manager2.run_hooks("on_pipeline_start", sample_ctx)
        assert order == ["high", "low"]


# ============================================================
# Filter plugin tests
# ============================================================

class TestFilterPlugins:

    @pytest.mark.asyncio
    async def test_filter_registration(self, manager):
        f = TestFilterPlugin()
        manager.register(f)
        assert "phase1_preprocess" in manager.filter_plugins
        assert f in manager.filter_plugins["phase1_preprocess"]

    @pytest.mark.asyncio
    async def test_filter_execution(self, manager, sample_ctx):
        f = TestFilterPlugin()
        manager.register(f)

        result = PhaseResult(
            phase=PipelinePhase.PHASE1_PREPROCESS,
            status=TaskStatus.SUCCESS,
        )
        sample_ctx.phase = PipelinePhase.PHASE1_PREPROCESS
        sample_ctx.phase_result = result

        await manager.run_filters(sample_ctx)
        assert f.filter_called is True
        assert result.metadata.get("filtered") is True

    @pytest.mark.asyncio
    async def test_filter_no_phase_returns_none(self, manager, sample_ctx):
        f = TestFilterPlugin()
        manager.register(f)
        sample_ctx.phase = None
        result = await manager.run_filters(sample_ctx)
        assert result is None


# ============================================================
# Built-in plugin discovery tests
# ============================================================

class TestBuiltinDiscovery:

    def test_discover_builtin_loads_plugins(self, manager):
        """discover_builtin should find and register built-in plugins."""
        loaded = manager.discover_builtin()
        names = [p.name for p in loaded]
        assert "progress_logger" in names
        assert "quality_check" in names
        assert "watermark" in names

    @pytest.mark.asyncio
    async def test_builtin_plugins_init_cleanup(self, manager):
        manager.discover_builtin()
        await manager.init_all()
        for plugin in manager.plugins.values():
            assert plugin._state in (PluginState.LOADED, PluginState.ERROR)
        await manager.cleanup_all()


# ============================================================
# Built-in plugin behavior tests
# ============================================================

class TestBuiltinPlugins:

    @pytest.mark.asyncio
    async def test_quality_check_adds_score(self, manager, sample_ctx):
        """QualityCheckPlugin should add quality_score to metadata."""
        from src.plugins.builtin.quality_check import QualityCheckPlugin
        plugin = QualityCheckPlugin()
        manager.register(plugin)

        result = PhaseResult(
            phase=PipelinePhase.PHASE1_PREPROCESS,
            status=TaskStatus.SUCCESS,
            metadata={"total_scenes": 5},
        )
        sample_ctx.phase = PipelinePhase.PHASE1_PREPROCESS
        sample_ctx.phase_result = result

        modified = await manager.run_hooks("after_phase", sample_ctx)
        assert modified is not None
        assert "quality_score" in modified.metadata
        assert modified.metadata["quality_score"] == 1.0

    @pytest.mark.asyncio
    async def test_quality_check_warns_no_scenes(self, manager, sample_ctx):
        """QualityCheckPlugin should warn when no scenes detected."""
        from src.plugins.builtin.quality_check import QualityCheckPlugin
        plugin = QualityCheckPlugin()
        manager.register(plugin)

        result = PhaseResult(
            phase=PipelinePhase.PHASE1_PREPROCESS,
            status=TaskStatus.SUCCESS,
            metadata={"total_scenes": 0},
        )
        sample_ctx.phase = PipelinePhase.PHASE1_PREPROCESS
        sample_ctx.phase_result = result

        modified = await manager.run_hooks("after_phase", sample_ctx)
        assert modified is not None
        assert "quality_warnings" in modified.metadata
        assert len(modified.metadata["quality_warnings"]) > 0

    @pytest.mark.asyncio
    async def test_progress_logger_logs_all_events(self, manager, sample_ctx):
        """ProgressLoggerPlugin should have all hook methods."""
        from src.plugins.builtin.progress_logger import ProgressLoggerPlugin
        plugin = ProgressLoggerPlugin()
        manager.register(plugin)

        # Just verify it doesn't crash on any hook
        await manager.run_hooks("on_job_created", sample_ctx)
        await manager.run_hooks("on_pipeline_start", sample_ctx)
        await manager.run_hooks("before_phase", sample_ctx)
        await manager.run_hooks("after_phase", sample_ctx)
        await manager.run_hooks("on_pipeline_success", sample_ctx)
        await manager.run_hooks("on_pipeline_failure", sample_ctx)
        await manager.run_hooks("on_pipeline_cancel", sample_ctx)

    @pytest.mark.asyncio
    async def test_watermark_plugin_config(self):
        """WatermarkPlugin should have configurable properties."""
        from src.plugins.builtin.watermark import WatermarkPlugin
        plugin = WatermarkPlugin()
        assert plugin.watermark_text == "Puppet Automation"
        plugin.watermark_text = "Custom Watermark"
        assert plugin.watermark_text == "Custom Watermark"
        assert plugin.target_phase == PipelinePhase.PHASE4_RENDER

    @pytest.mark.asyncio
    async def test_watermark_skips_no_output(self, manager, sample_ctx):
        """Watermark should skip when no output_path."""
        from src.plugins.builtin.watermark import WatermarkPlugin
        plugin = WatermarkPlugin()
        manager.register(plugin)

        result = PhaseResult(
            phase=PipelinePhase.PHASE4_RENDER,
            status=TaskStatus.SUCCESS,
            metadata={},
        )
        sample_ctx.phase = PipelinePhase.PHASE4_RENDER
        sample_ctx.phase_result = result

        filtered = await manager.run_filters(sample_ctx)
        # Should return the result unchanged (no output_path)
        assert filtered is not None
        assert filtered.metadata.get("watermarked") is None or \
               filtered.metadata.get("watermarked") is False


# ============================================================
# Orchestrator integration tests
# ============================================================

class TestOrchestratorPluginIntegration:

    @pytest.mark.asyncio
    async def test_plugins_fire_during_pipeline(self, tmp_path):
        """Plugins should fire when running pipeline through orchestrator."""
        from src.orchestrator.pipeline import PipelineOrchestrator
        from src.plugins.base import HookPlugin, PluginContext, PluginPriority
        from src.plugins.manager import PluginManager

        # Custom tracking plugin
        class TrackerPlugin(HookPlugin):
            @property
            def name(self): return "tracker"
            @property
            def version(self): return "1.0.0"
            @property
            def priority(self): return PluginPriority.HIGHEST

            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            async def on_job_created(self, ctx): self.events.append("job_created")
            async def on_pipeline_start(self, ctx): self.events.append("pipeline_start")
            async def before_phase(self, ctx): self.events.append(f"before_{ctx.phase.value}")
            async def after_phase(self, ctx): self.events.append(f"after_{ctx.phase.value}")
            async def on_pipeline_success(self, ctx): self.events.append("pipeline_success")

        tracker = TrackerPlugin()
        orch = PipelineOrchestrator(
            engines={},
            base_work_dir=tmp_path / "jobs",
            enable_persistence=False,
            enable_plugins=True,
        )
        # Manually init plugin system and register tracker
        await orch._init_plugins()
        if orch._plugin_mgr:
            orch._plugin_mgr.register(tracker)

        job = PipelineJob(
            job_id="plugin_integration_test",
            input_video="nonexistent.mp4",
            phases=[PipelinePhase.PHASE1_PREPROCESS],
        )
        state = await orch.run_pipeline(job)

        # Verify plugins fired
        assert "job_created" in tracker.events
        assert "pipeline_start" in tracker.events
        assert "before_phase1_preprocess" in tracker.events
        assert "after_phase1_preprocess" in tracker.events
        assert "pipeline_success" in tracker.events

    @pytest.mark.asyncio
    async def test_plugins_disabled_no_crash(self, tmp_path):
        """Orchestrator with plugins disabled should work normally."""
        from src.orchestrator.pipeline import PipelineOrchestrator

        orch = PipelineOrchestrator(
            engines={},
            base_work_dir=tmp_path / "jobs",
            enable_persistence=False,
            enable_plugins=False,
        )
        job = PipelineJob(
            job_id="no_plugin_test",
            input_video="nonexistent.mp4",
            phases=[PipelinePhase.PHASE1_PREPROCESS],
        )
        state = await orch.run_pipeline(job)
        # Should complete without plugin errors
        assert state.overall_status == TaskStatus.SUCCESS
