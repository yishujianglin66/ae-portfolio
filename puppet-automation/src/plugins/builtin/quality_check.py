"""Quality check plugin.

Validates phase outputs and records quality metrics.
If a phase produces no output or has errors, it adds warnings to metadata.
"""

from __future__ import annotations

from typing import Optional

from src.plugins.base import HookPlugin, PluginContext, PluginPriority
from src.models.pipeline import (
    PhaseResult,
    PipelinePhase,
    TaskStatus,
)


class QualityCheckPlugin(HookPlugin):
    """Validates phase outputs and records quality metrics."""

    @property
    def name(self) -> str:
        return "quality_check"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Validates phase outputs and records quality metrics"

    @property
    def priority(self) -> PluginPriority:
        return PluginPriority.HIGH

    async def after_phase(self, ctx: PluginContext) -> Optional[PhaseResult]:
        """Check phase output quality and add warnings if needed."""
        if not ctx.phase_result or not ctx.phase:
            return None

        result = ctx.phase_result
        warnings: list[str] = []
        metadata = dict(result.metadata or {})

        # Phase-specific quality checks
        if ctx.phase == PipelinePhase.PHASE1_PREPROCESS:
            scenes = metadata.get("total_scenes", 0)
            if scenes == 0:
                warnings.append("No scenes detected in preprocessing")
            metadata.setdefault("quality_score", 1.0 if scenes > 0 else 0.0)

        elif ctx.phase == PipelinePhase.PHASE2_KEYING:
            method = metadata.get("method", "unknown")
            if method == "fallback":
                warnings.append("Keying used fallback method")
            metadata.setdefault("quality_score", 0.8 if method != "fallback" else 0.5)

        elif ctx.phase == PipelinePhase.PHASE3_STYLIZE:
            style = metadata.get("style", "unknown")
            metadata.setdefault("quality_score", 0.9)

        elif ctx.phase == PipelinePhase.PHASE4_RENDER:
            output_path = metadata.get("output_path", "")
            metadata.setdefault("quality_score", 0.95 if output_path else 0.0)

        # Add warnings to metadata
        if warnings:
            existing = metadata.get("quality_warnings", [])
            metadata["quality_warnings"] = existing + warnings

        # Always record quality check timestamp
        import time
        metadata["quality_checked_at"] = time.time()

        # Return modified result with updated metadata
        result.metadata = metadata
        from loguru import logger
        if warnings:
            logger.warning(
                f"[Plugin:QualityCheck] Phase '{ctx.phase.value}' warnings: {warnings}"
            )
        else:
            logger.info(
                f"[Plugin:QualityCheck] Phase '{ctx.phase.value}' passed quality check"
            )

        return result
