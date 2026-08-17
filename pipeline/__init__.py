"""
pipeline - 端到端视频创作管线 v2
==================================
统一编排: 感知 → 分析 → 规划 → 执行 → 渲染 → 质检 → 学习

v2 特性:
  - 3种触发模式: 文字主题 / 参考视频(VRS) / 混合输入
  - VRS 逆向分析 → 生产数据流打通
  - 知识库实时注入每个决策节点
  - 反馈闭环: QualityAgent → KB → 自迭代
  - 多线程 DAG 并行执行器
"""
from pipeline.unified_pipeline import (
    UnifiedPipeline, PipelineConfig, PipelineResult,
    PipelineMode, StageStatus, StageResult, KnowledgeInjector,
)
from pipeline.presets import apply_preset, list_presets, get_preset, get_preset_context, PRESETS
from pipeline.batch_queue import BatchQueue, BatchTask, TaskStatus
from pipeline.multi_thread_executor import (
    MultiThreadExecutor, ExecutionResult, StageDAG, PipelineMonitor,
    create_video_pipeline_executor,
)
from pipeline.feedback_loop import (
    FeedbackLoop, FeedbackResult, QualityIssue, AdjustmentAdvice,
    process_quality_feedback, get_past_feedback, get_success_patterns,
)

__all__ = [
    "UnifiedPipeline", "PipelineConfig", "PipelineResult",
    "PipelineMode", "StageStatus", "StageResult", "KnowledgeInjector",
    "MultiThreadExecutor", "ExecutionResult", "StageDAG", "PipelineMonitor",
    "create_video_pipeline_executor",
    "FeedbackLoop", "FeedbackResult", "QualityIssue", "AdjustmentAdvice",
    "process_quality_feedback", "get_past_feedback", "get_success_patterns",
]
