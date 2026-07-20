"""OpenMontage 深度集成模块。

将 OpenMontage 的工作流引擎、技能系统、风格手册、Remotion 合成能力
集成到 AE-Knowledge-Vault 中。
"""
from .pipeline_runtime import (
    OpenMontagePipelineRuntime,
    PipelineManifest,
    StageDefinition,
    StageResult,
    PipelineStatus,
)
from .skill_loader import SkillLoader, Skill
from .style_playbook import StylePlaybookLoader, StylePlaybook, DesignTokens
from .whisperx_subtitles import (
    WhisperXSubtitleGenerator,
    WordTimestamp,
    SubtitleSegment,
)
from .remotion_bridge import RemotionBridge, RemotionComponent
from .cost_tracker import CostTracker, CostEntry, BudgetPolicy

__all__ = [
    "OpenMontagePipelineRuntime",
    "PipelineManifest",
    "StageDefinition",
    "StageResult",
    "PipelineStatus",
    "SkillLoader",
    "Skill",
    "StylePlaybookLoader",
    "StylePlaybook",
    "DesignTokens",
    "WhisperXSubtitleGenerator",
    "WordTimestamp",
    "SubtitleSegment",
    "RemotionBridge",
    "RemotionComponent",
    "CostTracker",
    "CostEntry",
    "BudgetPolicy",
]
