"""
core/evolution/ — 自进化 Harness（借鉴 PenguinHarness 设计理念）
=================================================================

核心组件:
- protocol: EvolutionMessage 统一消息协议 + 数据结构 + 成本上限
- evaluator: 独立评测器（确定性指标 + LLM Rubrics 双通道）
- version_manager: 版本管理 + 严格更高才接受的回退机制
- runner: 闭环入口 — 评测 → 版本决策 → 知识沉淀
- rubrics: Rubrics 隐藏评分引擎 (P1)
- benchmark_builder: 评测基准自动出题 (P1)
- optimizer_agent: Optimizer Agent 失分分析与配置改进 (P1)
- run_evolution: 评测驱动的进化主循环 CLI (P1)
- agent_assets: Agent Prompt/Skill 资产管理，Optimizer 可修改 (P2)
- auto_benchmark: 从历史执行自动生成/轮换评测题目 (P2)
- knowledge_sink: 进化知识自动沉淀与消费 (P2)

P0 用法:
    from core.evolution import record_pipeline_run

    # 管线运行结束后调用（在 UnifiedPipeline.run_all 末尾自动触发）
    decision = record_pipeline_run(pipeline_result_dict, scope="style_transfer")

P1 用法:
    python -m core.evolution.run_evolution --task style_transfer --iterations 3
"""
from core.evolution.protocol import (
    BenchmarkTask,
    COST_LIMITS,
    EvaluationResult,
    EvolutionMessage,
    EvolutionMsgType,
    within_cost_limit,
)
from core.evolution.evaluator import EvolutionEvaluator, get_evolution_evaluator
from core.evolution.version_manager import (
    VersionDecision,
    VersionManager,
    get_version_manager,
)
from core.evolution.runner import record_pipeline_run, get_evolution_runner
from core.evolution.rubrics import (
    RubricScoreResult,
    RubricsScorer,
    get_rubrics_scorer,
)
from core.evolution.benchmark_builder import (
    BenchmarkBuilder,
    get_benchmark_builder,
)
from core.evolution.optimizer_agent import (
    OptimizationProposal,
    OptimizerAgent,
    get_optimizer_agent,
)
from core.evolution.agent_assets import (
    AgentAssetManager,
    PromptUpdateResult,
    get_agent_asset_manager,
)
from core.evolution.auto_benchmark import AutoBenchmark, get_auto_benchmark
from core.evolution.knowledge_sink import KnowledgeSink, get_knowledge_sink

__all__ = [
    "BenchmarkTask",
    "COST_LIMITS",
    "EvaluationResult",
    "EvolutionMessage",
    "EvolutionMsgType",
    "within_cost_limit",
    "EvolutionEvaluator",
    "get_evolution_evaluator",
    "VersionDecision",
    "VersionManager",
    "get_version_manager",
    "record_pipeline_run",
    "get_evolution_runner",
    "RubricScoreResult",
    "RubricsScorer",
    "get_rubrics_scorer",
    "BenchmarkBuilder",
    "get_benchmark_builder",
    "OptimizationProposal",
    "OptimizerAgent",
    "get_optimizer_agent",
    "AgentAssetManager",
    "PromptUpdateResult",
    "get_agent_asset_manager",
    "AutoBenchmark",
    "get_auto_benchmark",
    "KnowledgeSink",
    "get_knowledge_sink",
]
