"""Progress logger plugin.

Logs detailed progress information at each pipeline lifecycle event.
Useful for debugging and monitoring pipeline execution.
"""

from __future__ import annotations

from src.models.pipeline import TaskStatus
from src.plugins.base import HookPlugin, PluginContext, PluginPriority


class ProgressLoggerPlugin(HookPlugin):
    """Logs pipeline progress at each lifecycle event."""

    @property
    def name(self) -> str:
        return "progress_logger"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Detailed progress logging for all pipeline events"

    @property
    def priority(self) -> PluginPriority:
        return PluginPriority.HIGHEST

    async def on_job_created(self, ctx: PluginContext) -> None:
        from loguru import logger
        logger.info(
            f"[Plugin:ProgressLogger] Job created: {ctx.job.job_id}, "
            f"input={ctx.job.input_video}"
        )

    async def on_pipeline_start(self, ctx: PluginContext) -> None:
        from loguru import logger
        phases = [p.value for p in ctx.job.phases]
        logger.info(
            f"[Plugin:ProgressLogger] Pipeline starting for {ctx.job.job_id}, "
            f"phases={phases}"
        )

    async def before_phase(self, ctx: PluginContext) -> None:
        from loguru import logger
        phase_name = ctx.phase.value if ctx.phase else "unknown"
        logger.info(
            f"[Plugin:ProgressLogger] >>> Starting phase '{phase_name}' "
            f"for job {ctx.job.job_id}"
        )

    async def after_phase(self, ctx: PluginContext) -> None:
        from loguru import logger
        phase_name = ctx.phase.value if ctx.phase else "unknown"
        status = ctx.phase_result.status.value if ctx.phase_result else "unknown"
        duration = ctx.phase_result.duration_seconds if ctx.phase_result else 0
        logger.info(
            f"[Plugin:ProgressLogger] <<< Phase '{phase_name}' completed: "
            f"status={status}, duration={duration:.2f}s"
        )

    async def on_pipeline_success(self, ctx: PluginContext) -> None:
        from loguru import logger
        logger.info(
            f"[Plugin:ProgressLogger] Pipeline SUCCESS for {ctx.job.job_id}, "
            f"progress={ctx.state.progress:.1f}%"
        )

    async def on_pipeline_failure(self, ctx: PluginContext) -> None:
        from loguru import logger
        logger.error(
            f"[Plugin:ProgressLogger] Pipeline FAILED for {ctx.job.job_id}: "
            f"{ctx.state.error}"
        )

    async def on_pipeline_cancel(self, ctx: PluginContext) -> None:
        from loguru import logger
        logger.warning(
            f"[Plugin:ProgressLogger] Pipeline CANCELLED for {ctx.job.job_id}"
        )
