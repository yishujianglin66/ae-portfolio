"""OpenMontage 深度集成模块。

将 OpenMontage 的工作流引擎、技能系统、风格手册、Remotion 合成能力
集成到 AE-Knowledge-Vault 中。
"""
from .cost_tracker import BudgetPolicy, CostEntry, CostTracker
from .pipeline_runtime import (
    OpenMontagePipelineRuntime,
    PipelineManifest,
    PipelineStatus,
    StageDefinition,
    StageResult,
)
from .remotion_bridge import RemotionBridge, RemotionComponent
from .skill_loader import Skill, SkillLoader
from .style_playbook import DesignTokens, StylePlaybook, StylePlaybookLoader
from .whisperx_subtitles import (
    SubtitleSegment,
    WhisperXSubtitleGenerator,
    WordTimestamp,
)

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
