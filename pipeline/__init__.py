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
# batch_queue 中任务类名为 Task (旧名 BatchTask 已重命名, 此处保留别名兼容历史引用)
from pipeline.batch_queue import BatchQueue, TaskStatus
from pipeline.batch_queue import Task as BatchTask
from pipeline.feedback_loop import (
    AdjustmentAdvice,
    FeedbackLoop,
    FeedbackResult,
    QualityIssue,
    get_past_feedback,
    get_success_patterns,
    process_quality_feedback,
)
from pipeline.multi_thread_executor import (
    ExecutionResult,
    MultiThreadExecutor,
    PipelineMonitor,
    StageDAG,
    create_video_pipeline_executor,
)
from pipeline.presets import PRESETS, apply_preset, get_preset, get_preset_context, list_presets
from pipeline.unified_pipeline import (
    KnowledgeInjector,
    PipelineConfig,
    PipelineMode,
    PipelineResult,
    StageResult,
    StageStatus,
    UnifiedPipeline,
)

__all__ = [
    "UnifiedPipeline", "PipelineConfig", "PipelineResult",
    "PipelineMode", "StageStatus", "StageResult", "KnowledgeInjector",
    "MultiThreadExecutor", "ExecutionResult", "StageDAG", "PipelineMonitor",
    "create_video_pipeline_executor",
    "FeedbackLoop", "FeedbackResult", "QualityIssue", "AdjustmentAdvice",
    "process_quality_feedback", "get_past_feedback", "get_success_patterns",
]
