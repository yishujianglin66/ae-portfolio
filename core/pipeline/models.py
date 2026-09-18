"""
Pipeline 数据模型
================

五层管线的输入/输出数据结构定义。

- PerceptionResult: 感知层输出
- UnderstandingResult: 理解层输出
- PlanningResult: 规划层输出
- ExecutionResult: 执行层输出
- FeedbackResult: 反馈层输出
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PerceptionResult:
    """感知层输出结果"""
    video_analysis: dict = None
    audio_analysis: dict = None
    clip_features: list[dict] = None
    music_features: dict = None
    topaz_enhanced: list[dict] = None
    color_graded: list[dict] = None
    ai_generated: list[dict] = None
    blender_scenes: list[dict] = None


@dataclass
class UnderstandingResult:
    """理解层输出结果"""
    intent: str = ""
    mood: str = ""
    mood_score: float = 0.0
    style: str = ""
    tempo: float = 0.0
    duration: float = 0.0
    keywords: list[str] = field(default_factory=list)
    scene_description: str = ""
    silhouette_task: str = ""
    is_hybrid: bool = False
    route_type: str = "ae_only"
    # NLU Parser 精细意图字段（Phase4 衔接）
    nlu_intent_type: str = ""
    nlu_confidence: float = 0.0
    nlu_slots: dict[str, Any] = field(default_factory=dict)
    nlu_matched_pattern: str = ""
    # LLM 增强置信度
    confidence: float = 0.0
    # ClarificationEngine 澄清字段
    clarification_questions: list[dict] = field(default_factory=list)
    confidence_gaps: dict[str, float] = field(default_factory=dict)
    # EffectDescriptionParser 效果描述解析字段
    effect_keywords: list[str] = field(default_factory=list)
    color_keywords: list[dict] = field(default_factory=list)
    intensity_keywords: list[str] = field(default_factory=list)
    temporal_keywords: list[str] = field(default_factory=list)
    # intent_to_report 生成的 AnalysisReport（Phase4→Phase3 衔接）
    analysis_report: Any = None
    # AIScheduler 统一调度结果（Phase4 完整管线编排）
    scheduler_result: Any = None
    # vocabulary_map 增强扫描结果（比 effect_description_parser 更丰富的同义词覆盖）
    vocab_scan_enhanced: dict[str, Any] = field(default_factory=dict)
    # Phase3 effect_name_map 增强结果（display_name→matchName 解析）
    effect_name_map_resolved: dict[str, Any] = field(default_factory=dict)
    # DaVinci Resolve 调色相关字段
    resolve_preset: str = ""
    needs_color_grading: bool = False
    # AI 视频生成相关字段
    ai_video_requested: bool = False
    ai_provider: str = ""
    ai_prompt: str = ""
    # Blender 3D 场景相关字段
    blender_requested: bool = False
    blender_scene_type: str = ""


@dataclass
class PlanningResult:
    """规划层输出结果"""
    composition: dict = None
    layers: list[dict] = field(default_factory=list)
    effects: list[dict] = field(default_factory=list)
    keyframes: list[dict] = field(default_factory=list)
    transitions: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    execution_order: list[str] = field(default_factory=list)
    silhouette_operations: list[dict] = field(default_factory=list)
    # Phase3 report_to_ops 生成的编译器操作列表（createComp/addLayer/addEffect/...）
    compiler_operations: list[dict] = field(default_factory=list)
    # Phase3 analyze_report 统计信息
    report_stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """执行层输出结果"""
    success: bool = False
    error_message: str = ""
    output_path: str = ""
    execution_time: float = 0.0
    steps_completed: int = 0
    total_steps: int = 0
    artifacts: list[dict] = field(default_factory=list)
    silhouette_artifacts: list[dict] = field(default_factory=list)


@dataclass
class FeedbackResult:
    """反馈层输出结果"""
    rating: float = 0.0
    confidence: float = 0.0
    improvement_suggestions: list[str] = field(default_factory=list)
    learned_patterns: dict = field(default_factory=dict)
    error_log: list[str] = field(default_factory=list)
    # Phase5 验证结果（ResultVerifier 回读对比）
    verification_result: dict[str, Any] = field(default_factory=dict)
    # Phase5 学习循环度量（LearningLoop.get_metrics）
    learning_metrics: dict[str, Any] = field(default_factory=dict)
    # Phase5 失败恢复动作（FailureRecovery.handle_failure 返回）
    recovery_action: dict[str, Any] = field(default_factory=dict)
