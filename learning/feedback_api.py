"""
learning/feedback_api.py — 前端评分接入 API
=============================================

为前端 UI 提供统一的用户反馈接口，让 user_feedback 三态学习
（满意/调整/撤销）完整触发 PersistentLearningLoop 的三种学习策略。

前端接入方式：
    // 渲染完成后用户点击"满意/调整参数/撤销重做"
    POST /api/learning/feedback
    {
        "run_id": "run_20260730_103000_abc123",
        "feedback_type": "satisfied",    // "satisfied" | "adjusted" | "undone"
        "adjusted_params": {             // 仅当 feedback_type="adjusted" 时提供
            "Glow": {
                "Glow Threshold": 45,
                "Glow Radius": 30
            }
        },
        "rating": 4                       // 可选 1-5 分，转化为 satisfied=True/False
    }

三态学习对应关系：
    satisfied → LearningLoop._learn_from_success()
        → 记录参数模板 + 提升推理路径置信度 + case_store.increment_usage()

    adjusted  → LearningLoop._learn_from_deviation()
        → 计算参数偏差 → 更新 default_value_store 建议值（加权平均）

    undone    → LearningLoop._learn_from_failure()
        → 降低推理路径置信度（penalize） + 模板 user_rating=negative
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """前端反馈类型枚举"""

    SATISFIED = "satisfied"  # 用户满意：正向学习
    ADJUSTED = "adjusted"    # 用户调整参数：偏差学习
    UNDONE = "undone"        # 用户撤销重做：负向学习


# ============================================================================
#  反馈记录数据结构
# ============================================================================


@dataclass
class UserFeedbackEntry:
    """一次用户反馈记录（用于持久化）"""

    run_id: str
    feedback_type: FeedbackType
    adjusted_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    rating: int | None = None
    comment: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class LearningTriggerResult:
    """学习策略触发结果"""

    success: bool
    strategy: str  # "success_learn" | "deviation_learn" | "failure_learn"
    record_id: str | None = None
    template_id: str | None = None
    default_values_updated: int = 0
    confidence_boosted: bool = False
    confidence_penalized: bool = False
    message: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================================
#  前端反馈接入主类
# ============================================================================


class FeedbackApi:
    """前端评分接入 API

    用法（Python 端）:
        api = FeedbackApi()
        result = api.submit_feedback(
            run_id="run_xxx",
            feedback_type="satisfied",
            rating=5,
        )

    用法（FastAPI 端点）:
        # 在 puppet-automation/src/api/main.py 中：
        from learning.feedback_api import feedback_api
        @app.post("/api/learning/feedback")
        async def learning_feedback(payload: dict):
            return feedback_api.submit_feedback_dict(payload)
    """

    def __init__(self, history_dir: str | None = None):
        # 反馈历史文件：与 PersistentLearningLoop 同根 %APPDATA%/AE-Knowledge-Vault
        if history_dir is None:
            if os.name == "nt":
                base = os.environ.get("APPDATA", os.path.expanduser("~"))
            else:
                base = os.environ.get("HOME", os.path.expanduser("~"))
            history_dir = str(Path(base) / "AE-Knowledge-Vault" / "feedback-history")
        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._history_dir / "feedback-history.jsonl"

        # ---- 一次性迁移：从旧路径 ~/.ae-knowledge-vault/feedback_history ----
        try:
            legacy_dir = Path.home() / ".ae-knowledge-vault" / "feedback_history"
            legacy_file = legacy_dir / "feedback-history.jsonl"
            if legacy_file.exists() and not self._history_file.exists():
                import shutil as _shutil
                _shutil.copy2(legacy_file, self._history_file)
                logger.info(
                    f"[FeedbackApi] Migrated legacy history {legacy_file} -> {self._history_file}"
                )
        except Exception as _e:
            logger.warning(f"[FeedbackApi] legacy history migration failed: {_e}")

        # 延迟加载学习循环实例
        self._learner = None
        self._optimizer = None
        self._memory_store = None

    # ------------------------------------------------------------------
    #  主入口：提交反馈
    # ------------------------------------------------------------------

    def submit_feedback(
        self,
        run_id: str,
        feedback_type: str,
        adjusted_params: dict[str, dict[str, Any]] | None = None,
        rating: int | None = None,
        comment: str = "",
        plan_context: dict[str, Any] | None = None,
        execute_context: dict[str, Any] | None = None,
        verify_context: dict[str, Any] | None = None,
    ) -> LearningTriggerResult:
        """提交用户反馈，触发对应学习策略

        Args:
            run_id: 管线运行 ID，用于关联执行记录
            feedback_type: "satisfied" | "adjusted" | "undone"
            adjusted_params: 仅 adjusted 时提供，{effect_name: {param_name: value}}
            rating: 可选 1-5 分评分
            comment: 可选用户文字评论
            plan_context: plan 阶段的 context（用于构造 ExpectedParameters）
            execute_context: execute 阶段的 context（用于构造 ExecutionResult）
            verify_context: verify 阶段的 context（用于构造 VerificationResult）

        Returns:
            LearningTriggerResult 描述学习策略是否触发
        """
        # 1. 规范化反馈类型
        try:
            ftype = FeedbackType(feedback_type)
        except ValueError:
            return LearningTriggerResult(
                success=False,
                strategy="",
                errors=[f"Invalid feedback_type: {feedback_type}. Expected satisfied/adjusted/undone."],
                message="反馈类型无效",
            )

        # 2. rating 兼容：5 星制转化为 satisfied=True/False
        if ftype == FeedbackType.SATISFIED and rating is not None:
            # rating 4-5 视为满意，1-3 视为不满意（自动降级为 undone）
            if rating <= 3:
                logger.info(
                    f"[FeedbackApi] run_id={run_id} rating={rating} <= 3, "
                    f"converting satisfied -> undone"
                )
                ftype = FeedbackType.UNDONE

        # 3. 延迟加载学习系统
        self._ensure_loaded()
        if self._learner is None:
            return LearningTriggerResult(
                success=False,
                strategy="",
                errors=["PersistentLearningLoop 加载失败，无法触发学习策略"],
                message="学习系统未就绪",
            )

        # 4. 构造三态上下文
        expected, execution, verification, reasoning_path, final_params = (
            self._build_contexts(
                run_id, ftype, plan_context, execute_context, verify_context, adjusted_params
            )
        )

        # 5. 构造 UserFeedback dataclass
        from learning.learning_loop import FinalParam
        from learning.learning_loop import UserFeedback as ULUserFeedback

        user_feedback = None
        if ftype == FeedbackType.SATISFIED:
            user_feedback = ULUserFeedback(
                satisfied=True,
                adjusted=False,
                undone=False,
                final_params=None,
            )
            strategy = "success_learn"
        elif ftype == FeedbackType.ADJUSTED:
            fp_list: list[FinalParam] = []
            for _, params_dict in (adjusted_params or {}).items():
                for pname, pval in params_dict.items():
                    fp_list.append(FinalParam(name=pname, value=pval))
            final_params = fp_list or final_params
            user_feedback = ULUserFeedback(
                satisfied=True,       # 用户调整后仍然使用，说明是满意的变体
                adjusted=True,
                undone=False,
                final_params=final_params,
            )
            strategy = "deviation_learn"
        else:  # UNDONE
            user_feedback = ULUserFeedback(
                satisfied=False,
                adjusted=False,
                undone=True,
                final_params=None,
            )
            strategy = "failure_learn"

        # 6. 调用 PersistentLearningLoop.record_execution
        #    内部根据 user_feedback 三态自动触发对应学习策略
        record_id = None
        try:
            record_id = self._learner.record_execution(
                user_input=self._extract_user_input(plan_context, run_id),
                intent_type=self._extract_intent(plan_context, run_id),
                expected=expected,
                execution=execution,
                verification=verification,
                user_feedback=user_feedback,
                reasoning_path=reasoning_path,
            )
            logger.info(
                f"[FeedbackApi] strategy={strategy} triggered: "
                f"run_id={run_id}, record_id={record_id}"
            )
        except Exception as e:
            logger.exception(f"[FeedbackApi] record_execution failed: {e}")
            return LearningTriggerResult(
                success=False,
                strategy=strategy,
                errors=[f"record_execution failed: {e}"],
                message=f"学习策略触发失败: {e}",
            )

        # 7. 副作用：贝叶斯优化器 observe（若 adjust 提供了新参数）
        default_values_updated = 0
        if ftype == FeedbackType.ADJUSTED and adjusted_params:
            try:
                default_values_updated = self._update_optimizer_from_adjustment(
                    run_id, adjusted_params, verify_context
                )
            except Exception as e:
                logger.warning(f"[FeedbackApi] optimizer update failed: {e}")

        # 8. 副作用：MemoryStore 记录
        try:
            self._update_memory_store(
                run_id, ftype, adjusted_params, rating, comment, plan_context
            )
        except Exception as e:
            logger.warning(f"[FeedbackApi] memory_store update failed: {e}")

        # 9. 统计置信度变化（仅用于报告）
        from learning.learning_loop import LearningLoopOptions

        options = self._learner._boost_delta if hasattr(self._learner, "_boost_delta") else None
        boosted = ftype in (FeedbackType.SATISFIED, FeedbackType.ADJUSTED)
        penalized = ftype == FeedbackType.UNDONE

        # 10. 持久化反馈历史（JSONL，每行一条，便于离线分析）
        self._append_feedback_history(
            UserFeedbackEntry(
                run_id=run_id,
                feedback_type=ftype,
                adjusted_params=adjusted_params or {},
                rating=rating,
                comment=comment,
            )
        )

        return LearningTriggerResult(
            success=True,
            strategy=strategy,
            record_id=record_id,
            default_values_updated=default_values_updated,
            confidence_boosted=boosted,
            confidence_penalized=penalized,
            message=f"{strategy} 已触发，record_id={record_id}",
        )

    def submit_feedback_dict(self, payload: dict[str, Any]) -> dict[str, Any]:
        """字典式接口（适用于 FastAPI 反序列化的 dict）"""
        try:
            result = self.submit_feedback(
                run_id=payload.get("run_id", ""),
                feedback_type=payload.get("feedback_type", ""),
                adjusted_params=payload.get("adjusted_params"),
                rating=payload.get("rating"),
                comment=payload.get("comment", ""),
                plan_context=payload.get("plan_context"),
                execute_context=payload.get("execute_context"),
                verify_context=payload.get("verify_context"),
            )
            return {
                "success": result.success,
                "strategy": result.strategy,
                "record_id": result.record_id,
                "message": result.message,
                "errors": result.errors,
            }
        except Exception as e:
            logger.exception(f"[FeedbackApi] submit_feedback_dict failed: {e}")
            return {"success": False, "errors": [str(e)], "message": "请求处理异常"}

    # ------------------------------------------------------------------
    #  辅助：构造三态上下文
    # ------------------------------------------------------------------

    def _build_contexts(
        self,
        run_id: str,
        ftype: FeedbackType,
        plan_context: dict[str, Any] | None,
        execute_context: dict[str, Any] | None,
        verify_context: dict[str, Any] | None,
        adjusted_params: dict[str, dict[str, Any]] | None,
    ):
        """从上下文构造 ExpectedParameters / ExecutionResult / VerificationResult"""
        from learning.learning_loop import (
            ExecutionResult,
            ExpectedParameters,
            ExpectedProperty,
            FinalParam,
            VerificationResult,
        )

        # ExpectedParameters
        effect_stack = (plan_context or {}).get("effect_stack", [])
        primary_effect = effect_stack[0] if effect_stack else {}
        params = primary_effect.get("params", {}) or {}

        expected = ExpectedParameters(
            comp_name=run_id,
            layer_index=0,
            effect_match_name=primary_effect.get("matchName")
            or primary_effect.get("id", ""),
            effect_name=primary_effect.get("name", ""),
            properties=[
                ExpectedProperty(name=k, value=v) for k, v in params.items()
            ],
        )

        # ExecutionResult
        exec_success = (execute_context or {}).get("success", ftype != FeedbackType.UNDONE)
        execution = ExecutionResult(
            success=exec_success,
            error_code=(execute_context or {}).get("error_code"),
            error_message=(execute_context or {}).get("error_message"),
            effect_name=expected.effect_name,
            execution_time_ms=(execute_context or {}).get("execution_time_ms"),
        )

        # VerificationResult
        verify_data = verify_context or {}
        score = verify_data.get("score", 0)
        verification = VerificationResult(
            passed=ftype != FeedbackType.UNDONE and score >= 60,
            deviation_score=max(0.0, (100.0 - score) / 100.0) if ftype == FeedbackType.SATISFIED else (
                0.1 if ftype == FeedbackType.ADJUSTED else 1.0
            ),
            reason=(verify_data.get("recommendations") or [None])[0],
        )

        # Reasoning path
        reasoning_path = (plan_context or {}).get("reasoning_path") or [
            (plan_context or {}).get("strategy", "default")
        ]

        # Final params（adjusted 场景）
        final_params: list[FinalParam] | None = None
        if ftype == FeedbackType.ADJUSTED and adjusted_params:
            final_params = []
            for _, params_dict in adjusted_params.items():
                for pname, pval in params_dict.items():
                    final_params.append(FinalParam(name=pname, value=pval))

        return expected, execution, verification, reasoning_path, final_params

    # ------------------------------------------------------------------
    #  副作用：贝叶斯优化器 / MemoryStore 更新
    # ------------------------------------------------------------------

    def _update_optimizer_from_adjustment(
        self,
        run_id: str,
        adjusted_params: dict[str, dict[str, Any]],
        verify_context: dict[str, Any] | None,
    ) -> int:
        """用户调整参数后，把新参数作为观测写入贝叶斯优化器

        返回写入的效果数
        """
        if self._optimizer is None:
            return 0

        from core.bayesian_optimizer import PARAMETER_SPACES
        from learning.learning_bridge import LearningBridge

        score = (verify_context or {}).get("score", 75.0)
        render_time = (verify_context or {}).get("render_time_sec", 0.0)
        file_size = (verify_context or {}).get("file_size_mb", 0.0)

        written = 0
        for effect_name, params_dict in adjusted_params.items():
            # 映射到参数空间
            effect_key = effect_name if effect_name in PARAMETER_SPACES else None
            if not effect_key:
                for mn, en in (("", effect_name),):
                    short = LearningBridge._extract_short_effect_name(mn, effect_name)
                    if short and short in PARAMETER_SPACES:
                        effect_key = short
                        break
            if not effect_key:
                continue

            spec_names = {p.name for p in PARAMETER_SPACES[effect_key]}
            valid_params = {k: v for k, v in params_dict.items() if k in spec_names}
            if not valid_params:
                continue

            self._optimizer.observe(
                effect_name=effect_key,
                params=valid_params,
                quality=float(score),
                render_time=float(render_time),
                file_size=float(file_size),
                success=True,
            )
            written += 1

        return written

    def _update_memory_store(
        self,
        run_id: str,
        ftype: FeedbackType,
        adjusted_params: dict[str, dict[str, Any]] | None,
        rating: int | None,
        comment: str,
        plan_context: dict[str, Any] | None,
    ) -> None:
        """把反馈写入 MemoryStore"""
        if self._memory_store is None:
            return

        effect_stack = (plan_context or {}).get("effect_stack", [])
        if not effect_stack:
            return

        tags = ["feedback", f"feedback_{ftype.value}"]
        if rating:
            tags.append(f"rating_{rating}")

        for i, effect in enumerate(effect_stack):
            effect_name = effect.get("name", "") or f"effect_{i}"
            match_name = effect.get("matchName", "") or ""
            mem_key = f"{run_id}_{effect_name}_feedback"
            self._memory_store.remember(
                category="user_feedback",
                key=mem_key,
                content={
                    "feedback_type": ftype.value,
                    "rating": rating,
                    "comment": comment,
                    "params": adjusted_params.get(effect_name, {})
                    if adjusted_params
                    else effect.get("params", {}),
                    "effect_name": effect_name,
                    "match_name": match_name,
                },
                tags=tags + [effect_name.lower()],
                confidence=0.5 + (0.1 if rating else 0),
            )

    # ------------------------------------------------------------------
    #  内部工具
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._learner is not None:
            return
        try:
            from learning.persistent_learning_loop import PersistentLearningLoop
            self._learner = PersistentLearningLoop()
        except Exception as e:
            logger.warning(f"[FeedbackApi] PersistentLearningLoop load failed: {e}")
            self._learner = None
        try:
            from core.bayesian_optimizer import get_optimizer
            self._optimizer = get_optimizer()
        except Exception as e:
            logger.warning(f"[FeedbackApi] BayesianOptimizer load failed: {e}")
            self._optimizer = None
        try:
            from core.memory_store import MemoryStore
            self._memory_store = MemoryStore()
        except Exception as e:
            logger.warning(f"[FeedbackApi] MemoryStore load failed: {e}")
            self._memory_store = None

    @staticmethod
    def _extract_user_input(plan_context, run_id) -> str:
        if plan_context and plan_context.get("user_input"):
            return plan_context["user_input"]
        return f"feedback_for_{run_id}"

    @staticmethod
    def _extract_intent(plan_context, run_id) -> str:
        if plan_context and plan_context.get("intent"):
            return plan_context["intent"]
        return "pipeline_feedback"

    def _append_feedback_history(self, entry: UserFeedbackEntry) -> None:
        """追加一条反馈记录到 JSONL"""
        try:
            line = {
                "run_id": entry.run_id,
                "feedback_type": entry.feedback_type.value
                if isinstance(entry.feedback_type, FeedbackType)
                else entry.feedback_type,
                "adjusted_params": entry.adjusted_params,
                "rating": entry.rating,
                "comment": entry.comment,
                "timestamp": entry.timestamp,
            }
            with open(self._history_file, "a", encoding="utf-8") as f:
                f.write(__import__("json").dumps(line, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[FeedbackApi] history append failed: {e}")

    # ------------------------------------------------------------------
    #  查询接口：供前端展示
    # ------------------------------------------------------------------

    def get_learning_stats(self) -> dict[str, Any]:
        """获取学习系统统计，供前端仪表盘展示"""
        self._ensure_loaded()
        stats: dict[str, Any] = {}
        if self._learner:
            stats["persistent_learning_loop"] = self._learner.get_stats()
        if self._optimizer:
            stats["bayesian_optimizer"] = self._optimizer.get_statistics()
        if self._memory_store:
            try:
                cursor = self._memory_store._conn.execute(
                    "SELECT category, COUNT(*) FROM memories GROUP BY category"
                )
                stats["memory_store"] = {
                    "by_category": {row[0]: row[1] for row in cursor.fetchall()}
                }
            except Exception:
                stats["memory_store"] = {}
        # 反馈历史计数
        try:
            lines = 0
            if self._history_file.exists():
                with open(self._history_file, "r", encoding="utf-8") as f:
                    for _ in f:
                        lines += 1
            stats["feedback_history_count"] = lines
        except Exception:
            stats["feedback_history_count"] = 0
        return stats


# ============================================================================
#  全局单例
# ============================================================================


_global_feedback_api: FeedbackApi | None = None


def get_feedback_api() -> FeedbackApi:
    """获取全局 FeedbackApi 单例"""
    global _global_feedback_api
    if _global_feedback_api is None:
        _global_feedback_api = FeedbackApi()
    return _global_feedback_api
