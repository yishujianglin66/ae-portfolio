"""learning_loop.py - Phase5 学习循环模块

学习策略：
    1. 正向学习（用户满意）：记录参数模板 → 提升推理路径置信度
    2. 偏差学习（用户调整）：计算参数偏差 → 更新默认值建议
    3. 负向学习（用户撤销/失败）：降低推理路径置信度
    4. 案例存储：成功案例 → 参数模板库

对齐 TS 源文件 compiler/src/phase5/learning-loop.ts
"""

from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 数据类定义
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """执行结果"""

    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    effect_index: Optional[int] = None
    effect_name: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class ExpectedProperty:
    """期望参数属性"""

    name: str
    value: Any
    tolerance: Optional[float] = None


@dataclass
class ExpectedParameters:
    """期望参数集合"""

    comp_name: str
    layer_index: int
    effect_match_name: Optional[str] = None
    effect_name: Optional[str] = None
    properties: List[ExpectedProperty] = field(default_factory=list)
    keyframes: Optional[List[Any]] = None


@dataclass
class ParameterMismatch:
    """参数偏差记录"""

    param: str
    expected: Any
    actual: Any
    deviation: Optional[float] = None


@dataclass
class VerificationResult:
    """校验结果"""

    passed: bool
    mismatches: List[ParameterMismatch] = field(default_factory=list)
    reason: Optional[str] = None
    deviation_score: float = 0.0


@dataclass
class FinalParam:
    """用户最终确认的参数"""

    name: str
    value: Any


@dataclass
class UserFeedback:
    """用户反馈"""

    satisfied: Optional[bool] = None
    adjusted: Optional[bool] = None
    undone: Optional[bool] = None
    final_params: Optional[List[FinalParam]] = None


@dataclass
class ExecutionRecord:
    """执行记录"""

    id: str
    timestamp: str
    user_input: str
    intent_type: str
    expected: ExpectedParameters
    execution: ExecutionResult
    verification: VerificationResult
    user_satisfied: Optional[bool] = None
    user_adjusted: Optional[bool] = None
    user_undone: Optional[bool] = None
    final_params: Optional[List[FinalParam]] = None
    reasoning_path: Optional[List[str]] = None


@dataclass
class ParameterTemplate:
    """参数模板"""

    id: str
    source: str  # "auto-learned" | "manual" | "preset"
    effect_match_name: str
    effect_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    user_rating: str = "neutral"  # "positive" | "negative" | "neutral"
    usage_count: int = 0
    last_used: str = ""
    source_input: Optional[str] = None


@dataclass
class ConfidenceAdjustment:
    """推理路径置信度调整"""

    reasoning_path: List[str]
    direction: str  # "boost" | "penalize"
    delta: float
    reason: str
    timestamp: str


@dataclass
class LearningMetrics:
    """学习指标"""

    total_executions: int
    success_count: int
    failure_count: int
    user_adjusted_count: int
    user_undone_count: int
    success_rate: float
    average_deviation: float
    learned_templates: int
    confidence_adjustments: int
    accuracy_improvement: float


@dataclass
class LearningLoopOptions:
    """学习循环配置项"""

    learning_rate: Optional[float] = None
    boost_delta: Optional[float] = None
    penalize_delta: Optional[float] = None


# ---------------------------------------------------------------------------
# 抽象基类
# ---------------------------------------------------------------------------


class CaseStore(ABC):
    """案例存储抽象基类"""

    @abstractmethod
    def add_template(self, template: ParameterTemplate) -> None:
        ...

    @abstractmethod
    def find_templates(self, effect_match_name: str) -> List[ParameterTemplate]:
        ...

    @abstractmethod
    def increment_usage(self, template_id: str) -> None:
        ...

    @abstractmethod
    def get_all_templates(self) -> List[ParameterTemplate]:
        ...


class DefaultValueStore(ABC):
    """默认值存储抽象基类"""

    @abstractmethod
    def get(self, effect_match_name: str, param_name: str) -> Any:
        ...

    @abstractmethod
    def update(
        self,
        effect_match_name: str,
        param_name: str,
        actual_value: Any,
        learning_rate: float,
    ) -> None:
        ...

    @abstractmethod
    def get_all(self, effect_match_name: str) -> Dict[str, Any]:
        ...


# ---------------------------------------------------------------------------
# 内存实现
# ---------------------------------------------------------------------------


class MemoryCaseStore(CaseStore):
    """基于内存的案例存储实现"""

    def __init__(self) -> None:
        self._templates: Dict[str, ParameterTemplate] = {}

    def add_template(self, template: ParameterTemplate) -> None:
        self._templates[template.id] = template

    def find_templates(self, effect_match_name: str) -> List[ParameterTemplate]:
        matched = [
            t for t in self._templates.values()
            if t.effect_match_name == effect_match_name
        ]
        return sorted(matched, key=lambda t: t.usage_count, reverse=True)

    def increment_usage(self, template_id: str) -> None:
        t = self._templates.get(template_id)
        if t is not None:
            t.usage_count += 1
            t.last_used = datetime.now().isoformat()

    def get_all_templates(self) -> List[ParameterTemplate]:
        return list(self._templates.values())


class MemoryDefaultValueStore(DefaultValueStore):
    """基于内存的默认值存储实现

    数值类型采用加权平均更新；非数值类型直接替换。
    """

    def __init__(self) -> None:
        # key -> (value, weight)
        self._store: Dict[str, Tuple[Any, float]] = {}

    def get(self, effect_match_name: str, param_name: str) -> Any:
        entry = self._store.get(f"{effect_match_name}.{param_name}")
        return entry[0] if entry is not None else None

    def update(
        self,
        effect_match_name: str,
        param_name: str,
        actual_value: Any,
        learning_rate: float,
    ) -> None:
        key = f"{effect_match_name}.{param_name}"
        existing = self._store.get(key)
        if existing is None:
            self._store[key] = (actual_value, learning_rate)
            return
        existing_value, existing_weight = existing
        if (
            self._is_number(existing_value)
            and self._is_number(actual_value)
        ):
            total_weight = existing_weight + learning_rate
            new_value = (
                existing_value * existing_weight
                + actual_value * learning_rate
            ) / total_weight
            self._store[key] = (new_value, total_weight)
        else:
            self._store[key] = (actual_value, learning_rate)

    def get_all(self, effect_match_name: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        prefix = f"{effect_match_name}."
        for key, entry in self._store.items():
            if key.startswith(prefix):
                param_name = key[len(prefix):]
                result[param_name] = entry[0]
        return result

    @staticmethod
    def _is_number(value: Any) -> bool:
        # Python 中 bool 是 int 的子类，需排除以对齐 TS typeof === "number"
        return isinstance(value, (int, float)) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# 学习循环
# ---------------------------------------------------------------------------


class LearningLoop:
    """学习循环主体"""

    def __init__(
        self,
        case_store: Optional[CaseStore] = None,
        default_value_store: Optional[DefaultValueStore] = None,
        options: Optional[LearningLoopOptions] = None,
    ) -> None:
        self._case_store: CaseStore = (
            case_store if case_store is not None else MemoryCaseStore()
        )
        self._default_value_store: DefaultValueStore = (
            default_value_store
            if default_value_store is not None
            else MemoryDefaultValueStore()
        )
        self._confidence_adjustments: List[ConfidenceAdjustment] = []
        self._execution_records: List[ExecutionRecord] = []
        self._learning_rate: float = (
            0.3 if options is None or options.learning_rate is None
            else options.learning_rate
        )
        self._boost_delta: float = (
            0.05 if options is None or options.boost_delta is None
            else options.boost_delta
        )
        self._penalize_delta: float = (
            0.1 if options is None or options.penalize_delta is None
            else options.penalize_delta
        )

    # ------------------------------------------------------------------
    # 记录执行
    # ------------------------------------------------------------------

    def record_execution(
        self,
        user_input: str,
        intent_type: str,
        expected: ExpectedParameters,
        execution: ExecutionResult,
        verification: VerificationResult,
        user_feedback: Optional[UserFeedback] = None,
        reasoning_path: Optional[List[str]] = None,
    ) -> ExecutionRecord:
        """记录一次执行并触发相应学习策略"""
        record = ExecutionRecord(
            id=f"exec_{int(time.time() * 1000)}_{random.randint(0, 9999)}",
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            intent_type=intent_type,
            expected=expected,
            execution=execution,
            verification=verification,
            user_satisfied=user_feedback.satisfied if user_feedback else None,
            user_adjusted=user_feedback.adjusted if user_feedback else None,
            user_undone=user_feedback.undone if user_feedback else None,
            final_params=user_feedback.final_params if user_feedback else None,
            reasoning_path=reasoning_path,
        )
        self._execution_records.append(record)

        if user_feedback and user_feedback.undone:
            self._learn_from_failure(record)
        elif (
            user_feedback
            and user_feedback.adjusted
            and user_feedback.final_params
        ):
            self._learn_from_deviation(record, user_feedback.final_params)
        elif (
            (user_feedback and user_feedback.satisfied)
            or (execution.success and verification.passed)
        ):
            self._learn_from_success(record)
        elif not execution.success:
            self._learn_from_failure(record)
        return record

    # ------------------------------------------------------------------
    # 学习策略
    # ------------------------------------------------------------------

    def _learn_from_success(self, record: ExecutionRecord) -> None:
        """正向学习：记录参数模板 + 提升推理路径置信度"""
        expected = record.expected
        execution = record.execution
        if expected.effect_match_name and execution.effect_name:
            template = ParameterTemplate(
                id=f"tpl_{int(time.time() * 1000)}_{random.randint(0, 9999)}",
                source="auto-learned",
                effect_match_name=expected.effect_match_name,
                effect_name=execution.effect_name,
                parameters=self._props_to_object(expected.properties),
                user_rating="positive",
                usage_count=1,
                last_used=datetime.now().isoformat(),
                source_input=record.user_input,
            )
            self._case_store.add_template(template)
        if record.reasoning_path and len(record.reasoning_path) > 0:
            self._confidence_adjustments.append(ConfidenceAdjustment(
                reasoning_path=record.reasoning_path,
                direction="boost",
                delta=self._boost_delta,
                reason=f"执行成功 (record: {record.id})",
                timestamp=datetime.now().isoformat(),
            ))

    def _learn_from_deviation(
        self, record: ExecutionRecord, final_params: List[FinalParam]
    ) -> None:
        """偏差学习：计算参数偏差 → 更新默认值建议"""
        expected = record.expected
        if not expected.effect_match_name:
            return
        for final_param in final_params:
            expected_param = next(
                (p for p in expected.properties if p.name == final_param.name),
                None,
            )
            if not expected_param:
                continue
            deviation = self._calculate_param_deviation(
                expected_param.value, final_param.value
            )
            if deviation > 0.05:
                self._default_value_store.update(
                    expected.effect_match_name,
                    final_param.name,
                    final_param.value,
                    self._learning_rate,
                )

    def _learn_from_failure(self, record: ExecutionRecord) -> None:
        """负向学习：降低推理路径置信度"""
        if record.reasoning_path and len(record.reasoning_path) > 0:
            if record.execution.success:
                reason = f"用户撤销 (record: {record.id})"
            else:
                error_code = record.execution.error_code or "unknown"
                reason = f"执行失败: {error_code} (record: {record.id})"
            self._confidence_adjustments.append(ConfidenceAdjustment(
                reasoning_path=record.reasoning_path,
                direction="penalize",
                delta=self._penalize_delta,
                reason=reason,
                timestamp=datetime.now().isoformat(),
            ))

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _calculate_param_deviation(
        self, expected: Any, actual: Any
    ) -> float:
        """计算参数偏差（相对偏差）"""
        if (
            MemoryDefaultValueStore._is_number(expected)
            and MemoryDefaultValueStore._is_number(actual)
        ):
            if expected == 0:
                return abs(actual)
            return abs(expected - actual) / abs(expected)
        if isinstance(expected, list) and isinstance(actual, list):
            if len(expected) == 0:
                return 0.0
            deviations = []
            for i, e in enumerate(expected):
                a = actual[i] if i < len(actual) else 0
                if e == 0:
                    deviations.append(abs(a))
                else:
                    deviations.append(abs(e - a) / abs(e))
            return sum(deviations) / len(deviations)
        return 0.0 if expected == actual else 1.0

    @staticmethod
    def _props_to_object(
        props: List[ExpectedProperty]
    ) -> Dict[str, Any]:
        """将属性列表转换为参数字典"""
        result: Dict[str, Any] = {}
        for p in props:
            result[p.name] = p.value
        return result

    # ------------------------------------------------------------------
    # 指标与访问器
    # ------------------------------------------------------------------

    def get_metrics(self) -> LearningMetrics:
        """计算并返回学习指标"""
        total = len(self._execution_records)
        success_count = sum(
            1 for r in self._execution_records
            if r.execution.success and r.verification.passed
        )
        failure_count = sum(
            1 for r in self._execution_records if not r.execution.success
        )
        user_adjusted_count = sum(
            1 for r in self._execution_records if r.user_adjusted
        )
        user_undone_count = sum(
            1 for r in self._execution_records if r.user_undone
        )
        deviation_records = [
            r for r in self._execution_records
            if r.verification.deviation_score is not None
        ]
        deviation_sum = sum(
            r.verification.deviation_score for r in deviation_records
        )
        deviation_count = len(deviation_records)
        average_deviation = (
            deviation_sum / deviation_count if deviation_count > 0 else 0.0
        )
        learned_templates = len(self._case_store.get_all_templates())
        confidence_adjustments = len(self._confidence_adjustments)
        accuracy_improvement = self._calculate_accuracy_improvement()
        return LearningMetrics(
            total_executions=total,
            success_count=success_count,
            failure_count=failure_count,
            user_adjusted_count=user_adjusted_count,
            user_undone_count=user_undone_count,
            success_rate=success_count / total if total > 0 else 0.0,
            average_deviation=average_deviation,
            learned_templates=learned_templates,
            confidence_adjustments=confidence_adjustments,
            accuracy_improvement=accuracy_improvement,
        )

    def _calculate_accuracy_improvement(self) -> float:
        """计算准确率提升（近期成功率 - 早期成功率）"""
        records = self._execution_records
        if len(records) < 4:
            return 0.0
        recent_count = min(10, len(records) // 2)
        recent_records = records[-recent_count:]
        earlier_records = records[-recent_count * 2:-recent_count]
        if len(earlier_records) == 0:
            return 0.0
        recent_success = (
            sum(1 for r in recent_records if r.execution.success)
            / len(recent_records)
        )
        earlier_success = (
            sum(1 for r in earlier_records if r.execution.success)
            / len(earlier_records)
        )
        return recent_success - earlier_success

    def get_execution_records(self) -> List[ExecutionRecord]:
        return list(self._execution_records)

    def get_confidence_adjustments(self) -> List[ConfidenceAdjustment]:
        return list(self._confidence_adjustments)

    def get_case_store(self) -> CaseStore:
        return self._case_store

    def get_default_value_store(self) -> DefaultValueStore:
        return self._default_value_store

    # ------------------------------------------------------------------
    # Silhouette 执行学习
    # ------------------------------------------------------------------

    def record_silhouette_execution(
        self,
        user_input: str,
        task_type: str,
        params: dict,
        success: bool,
        fallback: bool = False,
        error_message: str = "",
        output_path: str = "",
    ) -> ExecutionRecord:
        """记录 Silhouette 执行并触发学习

        将 roto/track/paint 执行参数和结果记录到学习循环中，
        使系统能跨任务积累 Silhouette 最优参数经验。
        """
        # 构造 ExpectedParameters（用 task_type 作为 effect_match_name）
        expected = ExpectedParameters(
            comp_name="",
            layer_index=0,
            effect_match_name=f"silhouette_{task_type}",
            effect_name=task_type,
            properties=[
                ExpectedProperty(name=k, value=v)
                for k, v in params.items()
                if isinstance(v, (int, float, str, bool))
            ],
        )

        execution = ExecutionResult(
            success=success,
            error_code="" if success else "SIL_FAILED",
            error_message=error_message,
            effect_name=task_type,
        )

        verification = VerificationResult(
            passed=success,
            deviation_score=0.0 if success else 1.0,
            mismatches=[],
        )

        record = ExecutionRecord(
            id=f"sil_{int(time.time() * 1000)}_{random.randint(0, 9999)}",
            timestamp=datetime.now().isoformat(),
            user_input=user_input,
            intent_type=f"silhouette_{task_type}",
            expected=expected,
            execution=execution,
            verification=verification,
            user_satisfied=success,
            user_adjusted=fallback,
            user_undone=False,
            final_params=params if fallback else None,
            reasoning_path=["silhouette", task_type],
        )
        self._execution_records.append(record)

        # 触发学习策略
        if success and not fallback:
            self._learn_from_silhouette_success(record, task_type, params)
        elif fallback:
            self._learn_from_silhouette_deviation(record, params)
        else:
            self._learn_from_silhouette_failure(record, task_type, error_message)

        return record

    def _learn_from_silhouette_success(
        self, record: ExecutionRecord, task_type: str, params: dict,
    ) -> None:
        """正向学习：记录 Silhouette 成功参数模板"""
        template = ParameterTemplate(
            id=f"sil_tpl_{int(time.time() * 1000)}_{random.randint(0, 9999)}",
            source="silhouette-learned",
            effect_match_name=f"silhouette_{task_type}",
            effect_name=task_type,
            parameters={
                k: v for k, v in params.items()
                if isinstance(v, (int, float, str, bool))
            },
            user_rating="positive",
            usage_count=1,
            last_used=datetime.now().isoformat(),
            source_input=record.user_input,
        )
        self._case_store.add_template(template)

    def _learn_from_silhouette_deviation(
        self, record: ExecutionRecord, adjusted_params: dict,
    ) -> None:
        """偏差学习：Silhouette 降级时的参数调整"""
        for k, v in adjusted_params.items():
            if isinstance(v, (int, float)):
                self._default_value_store.update(
                    record.expected.effect_match_name, k, v, 0.3,
                )

    def _learn_from_silhouette_failure(
        self, record: ExecutionRecord, task_type: str, error: str,
    ) -> None:
        """负向学习：记录失败原因，降低置信度"""
        self._confidence_adjustments.append(ConfidenceAdjustment(
            reasoning_path=["silhouette", task_type],
            direction="penalize",
            delta=0.1,
            reason=f"Silhouette {task_type} 失败: {error}",
            timestamp=datetime.now().isoformat(),
        ))


# ---------------------------------------------------------------------------
# 模块级单例
# ---------------------------------------------------------------------------

learning_loop = LearningLoop()


__all__ = [
    "ExecutionResult",
    "ExpectedProperty",
    "ExpectedParameters",
    "ParameterMismatch",
    "VerificationResult",
    "FinalParam",
    "UserFeedback",
    "ExecutionRecord",
    "ParameterTemplate",
    "ConfidenceAdjustment",
    "LearningMetrics",
    "LearningLoopOptions",
    "CaseStore",
    "DefaultValueStore",
    "MemoryCaseStore",
    "MemoryDefaultValueStore",
    "LearningLoop",
    "learning_loop",
]


# ---------------------------------------------------------------------------
# 自检
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    loop = LearningLoop()

    # 公共测试数据
    expected = ExpectedParameters(
        comp_name="Comp 1",
        layer_index=1,
        effect_match_name="ADBE Glo2",
        effect_name="Glow",
        properties=[ExpectedProperty(name="Glow Intensity", value=0.8)],
    )
    execution = ExecutionResult(success=True, effect_name="Glow")
    verification = VerificationResult(passed=True, deviation_score=0.0)

    # 1) 正向学习
    loop.record_execution(
        user_input="加发光",
        intent_type="ADD_EFFECT",
        expected=expected,
        execution=execution,
        verification=verification,
        user_feedback=UserFeedback(satisfied=True),
    )
    metrics = loop.get_metrics()
    print("=== 正向学习后 metrics ===")
    print(f"total_executions={metrics.total_executions}")
    print(f"success_count={metrics.success_count}")
    print(f"learned_templates={metrics.learned_templates}")

    # 2) 偏差学习
    loop.record_execution(
        user_input="加发光",
        intent_type="ADD_EFFECT",
        expected=expected,
        execution=execution,
        verification=verification,
        user_feedback=UserFeedback(
            adjusted=True,
            final_params=[FinalParam(name="Glow Intensity", value=0.9)],
        ),
    )
    stored = loop.get_default_value_store().get("ADBE Glo2", "Glow Intensity")
    print("\n=== 偏差学习后默认值 ===")
    print(f"default_value_store.get('ADBE Glo2', 'Glow Intensity') = {stored}")

    # 3) 负向学习
    loop.record_execution(
        user_input="加发光",
        intent_type="ADD_EFFECT",
        expected=expected,
        execution=execution,
        verification=verification,
        user_feedback=UserFeedback(undone=True),
        reasoning_path=["step1", "step2"],
    )
    adjustments = loop.get_confidence_adjustments()
    print("\n=== 负向学习后 confidence_adjustments ===")
    for adj in adjustments:
        print(
            f"direction={adj.direction}, delta={adj.delta}, "
            f"reason={adj.reason}"
        )

    print("\n自检通过。")
