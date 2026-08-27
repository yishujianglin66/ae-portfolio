"""
core/evolution/runner.py — 自进化闭环入口
==========================================

P0 最小闭环流程:
    管线结果 → Evaluator 独立评分 → 创建候选版本 → 严格对比决策(accept/rollback)
             → 消息日志(轨迹) → 知识沉淀钩子

在 UnifiedPipeline.run_all() 末尾通过 record_pipeline_run() 触发。
任何异常都不会中断主管线（进化是增强，不是依赖）。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.evolution.evaluator import EvolutionEvaluator, get_evolution_evaluator
from core.evolution.protocol import EvolutionMessage, append_jsonl
from core.evolution.version_manager import (
    VersionDecision,
    VersionManager,
    get_version_manager,
)

logger = logging.getLogger(__name__)

# 项目根目录（core/evolution/runner.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class EvolutionRunner:
    """自进化闭环运行器"""

    DEFAULT_MESSAGES_LOG = str(PROJECT_ROOT / "data" / "evolution" / "messages.jsonl")

    def __init__(
        self,
        evaluator: Optional[EvolutionEvaluator] = None,
        version_manager: Optional[VersionManager] = None,
        messages_log: str = DEFAULT_MESSAGES_LOG,
        enable_rubrics: bool = True,
    ):
        self._evaluator = evaluator or get_evolution_evaluator(
            enable_rubrics=enable_rubrics
        )
        self._vm = version_manager or get_version_manager()
        self._messages_log = Path(messages_log)

    # ----------------------------------------------------------------
    #  主入口
    # ----------------------------------------------------------------

    def record_pipeline_run(
        self,
        pipeline_result: Dict[str, Any],
        scope: str = "",
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Optional[VersionDecision]:
        """记录一次管线运行并执行进化决策

        Args:
            pipeline_result: PipelineResult.to_dict() 的输出
            scope: 评测作用域（任务类型）。为空时从结果自动推断。
            config_snapshot: 当前管线配置快照（版本回退时可恢复）

        Returns:
            VersionDecision；任何失败返回 None（不影响主管线）
        """
        try:
            run_id = pipeline_result.get("run_id", "unknown")
            scope = scope or self._infer_scope(pipeline_result)

            # 1. 独立评测（与被测管线解耦）
            eval_result = self._evaluator.evaluate_pipeline_result(
                pipeline_result, scope=scope
            )
            self._log_message(self._evaluator.emit_message(eval_result))

            # 2. 创建候选版本（文件即真相：配置快照）
            version_id = self._vm.create_version(
                scope=scope,
                config_snapshot=config_snapshot or self._default_snapshot(pipeline_result),
                source_run_id=run_id,
                parent_version=self._vm.get_current_version(scope),
            )

            # 3. 严格对比决策（核心：仅当严格更高才接受）
            decision = self._vm.record_and_decide(
                version_id=version_id,
                score=eval_result.score,
                run_id=run_id,
                breakdown={
                    "deterministic": eval_result.deterministic_score,
                    "rubric": eval_result.rubric_score,
                    "checks": eval_result.checks,
                },
            )
            self._log_message(self._vm.emit_message(decision, scope, run_id))

            # 4. 知识沉淀钩子（可选，失败不阻断）
            self._hook_knowledge_sink(eval_result, decision)

            logger.info(
                "[Evolution] run=%s scope=%s score=%.1f → %s (%s)",
                run_id, scope, eval_result.score, decision.decision, decision.reason,
            )
            return decision

        except Exception as e:
            logger.warning("[Evolution] record_pipeline_run failed (non-fatal): %s", e)
            return None

    # ----------------------------------------------------------------
    #  辅助
    # ----------------------------------------------------------------

    def _infer_scope(self, pr: Dict[str, Any]) -> str:
        """从管线结果推断评测作用域（同一任务类型才可比）"""
        mode = str(pr.get("mode", "")).lower()
        if "reference" in mode:
            return "reference_video"
        if "mixed" in mode:
            return "mixed"
        return "text_topic"

    def _default_snapshot(self, pr: Dict[str, Any]) -> Dict[str, Any]:
        """默认配置快照（P0 精简版，P1 由 Optimizer 消费）"""
        return {
            "mode": pr.get("mode", ""),
            "run_id": pr.get("run_id", ""),
            "iterations": pr.get("iterations", 0),
            "output_path": pr.get("output_path", ""),
            "project_path": pr.get("project_path", ""),
            "total_duration_sec": pr.get("total_duration_sec", 0),
        }

    def _log_message(self, msg: EvolutionMessage) -> None:
        """EvolutionMessage 轨迹日志（文件即真相 + 可审计）"""
        try:
            append_jsonl(self._messages_log, msg.to_dict())
        except Exception as e:
            logger.debug("[Evolution] message log failed: %s", e)

    def _hook_knowledge_sink(self, eval_result: Any, decision: VersionDecision) -> None:
        """知识沉淀钩子 — 将评测+决策回写到知识库（可选）

        P2: 双写 — SelfEvolutionEngine 评审历史 + data/self_evolution/ 进化知识库
        """
        # P2: 进化知识库（可被后续 Optimizer/管线消费）
        try:
            from core.evolution.knowledge_sink import get_knowledge_sink
            get_knowledge_sink().record_lesson(
                scope=eval_result.scope,
                decision=decision.decision,
                score=eval_result.score,
                notes=list(eval_result.notes)[:5],
                run_id=eval_result.run_id,
            )
        except Exception as e:
            logger.debug("[Evolution] knowledge_sink skipped: %s", e)

        try:
            from core.self_evolution_engine import get_evolution_engine
            engine = get_evolution_engine()
            # 轻量回写：作为一条蒸馏素材记录到评审历史
            engine._review_history.append({
                "source": "core.evolution",
                "run_id": eval_result.run_id,
                "scope": eval_result.scope,
                "score": eval_result.score,
                "decision": decision.decision,
                "reason": decision.reason,
                "timestamp": time.time(),
            })
            engine._save_state()
        except Exception as e:
            logger.debug("[Evolution] knowledge sink skipped: %s", e)


# ============================================================================
#  全局单例 + 便捷函数
# ============================================================================

_global_runner: Optional[EvolutionRunner] = None


def get_evolution_runner(enable_rubrics: bool = True) -> EvolutionRunner:
    """获取全局进化运行器单例"""
    global _global_runner
    if _global_runner is None:
        _global_runner = EvolutionRunner(enable_rubrics=enable_rubrics)
    return _global_runner


def record_pipeline_run(
    pipeline_result: Dict[str, Any],
    scope: str = "",
    config_snapshot: Optional[Dict[str, Any]] = None,
) -> Optional[VersionDecision]:
    """便捷函数：记录管线运行并执行进化决策"""
    return get_evolution_runner().record_pipeline_run(
        pipeline_result, scope=scope, config_snapshot=config_snapshot
    )
