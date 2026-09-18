#!/usr/bin/env python3
"""
反馈闭环管理器 v1.0
建立完整的反馈闭环，支持执行验证、错误恢复和置信度自适应学习

核心功能：
1. 执行记录管理 - 完整记录每次执行的上下文和结果
2. 参数验证 - 对比预期与实际参数，量化匹配度
3. 错误恢复策略 - 根据错误码提供恢复建议
4. 置信度自适应 - 根据历史成功率动态调整置信度
5. 学习摘要 - 统计整体执行表现和各意图类型的表现
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

ERROR_RECOVERY_STRATEGIES = {
    "EFFECT_NOT_FOUND": {
        "actions": [
            "检查效果名称拼写是否正确",
            "在效果预设库中搜索相似效果",
            "尝试使用等效效果替代",
            "降级为基础效果组合"
        ],
        "default": "使用相似效果替代或降级为基础效果组合"
    },
    "PROPERTY_NOT_FOUND": {
        "actions": [
            "检查属性名称和路径是否正确",
            "验证效果是否支持该属性",
            "使用属性映射表查找等效属性",
            "跳过该属性并记录警告"
        ],
        "default": "使用属性映射表查找等效属性或跳过该属性"
    },
    "SCRIPT_ERROR": {
        "actions": [
            "检查脚本语法错误",
            "验证ExtendScript API兼容性",
            "回退到上一个成功的脚本版本",
            "拆分为更小的脚本步骤执行"
        ],
        "default": "回退到上一个成功版本或拆分为更小步骤执行"
    },
    "TIMEOUT": {
        "actions": [
            "增加超时时间重试",
            "检查AE是否处于忙碌状态",
            "减少单次操作的复杂度",
            "分批执行操作"
        ],
        "default": "增加超时时间重试或分批执行操作"
    },
    "AE_NOT_RESPONDING": {
        "actions": [
            "检查AE进程是否正在运行",
            "尝试重新建立连接",
            "重启AE应用程序",
            "检查系统资源占用情况"
        ],
        "default": "重新建立连接或重启AE应用程序"
    }
}


@dataclass
class VerificationResult:
    passed: bool = False
    mismatches: list[dict] = field(default_factory=list)
    match_score: float = 0.0
    details: str = ""


@dataclass
class ExecutionRecord:
    id: str = ""
    user_input: str = ""
    intent_type: str = ""
    success: bool = False
    expected: dict = field(default_factory=dict)
    actual: dict | None = None
    error_message: str = ""
    error_code: str = ""
    timestamp: str = ""
    confidence_before: float = 0.5
    confidence_after: float = 0.5
    user_adjusted: bool = False
    final_params: dict | None = None


class FeedbackLoopManager:
    def __init__(self, confidence_threshold: float = 0.6):
        self.confidence_threshold = confidence_threshold
        self.records: list[ExecutionRecord] = []
        self._intent_history: dict[str, dict[str, int]] = {}

    def record_execution(
        self,
        user_input: str,
        intent_type: str,
        success: bool,
        expected: dict,
        actual: dict | None,
        error_message: str = "",
        error_code: str = "",
        base_confidence: float = 0.5
    ) -> ExecutionRecord:
        record_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        confidence_adjustment = self.calculate_confidence_adjustment(
            intent_type, success, base_confidence
        )
        confidence_after = max(0.0, min(1.0, base_confidence + confidence_adjustment))

        if intent_type not in self._intent_history:
            self._intent_history[intent_type] = {"success": 0, "total": 0}
        self._intent_history[intent_type]["total"] += 1
        if success:
            self._intent_history[intent_type]["success"] += 1

        record = ExecutionRecord(
            id=record_id,
            user_input=user_input,
            intent_type=intent_type,
            success=success,
            expected=expected,
            actual=actual,
            error_message=error_message,
            error_code=error_code,
            timestamp=timestamp,
            confidence_before=base_confidence,
            confidence_after=confidence_after,
            user_adjusted=False,
            final_params=None
        )

        self.records.append(record)
        return record

    def verify_parameters(
        self,
        expected: dict,
        actual: dict | None,
        tolerance: float = 0.01
    ) -> VerificationResult:
        mismatches = []
        expected_settings = expected.get("settings", {})
        
        if actual is None:
            if expected_settings:
                for param, exp_val in expected_settings.items():
                    mismatches.append({
                        "type": "missing_actual",
                        "param": param,
                        "expected": exp_val,
                        "actual": None,
                        "diff": None,
                        "diff_percent": None
                    })
            return VerificationResult(
                passed=False,
                mismatches=mismatches,
                match_score=0.0,
                details="执行结果为None，无法比较参数"
            )
        
        actual_settings = actual.get("settings", {})

        all_params = set(expected_settings.keys()) | set(actual_settings.keys())
        total_params = len(all_params)

        if total_params == 0:
            return VerificationResult(
                passed=True,
                mismatches=[],
                match_score=1.0,
                details="无参数可比较"
            )

        match_count = 0

        for param in all_params:
            exp_val = expected_settings.get(param)
            act_val = actual_settings.get(param)

            if exp_val is None and act_val is not None:
                mismatches.append({
                    "type": "missing_in_expected",
                    "param": param,
                    "expected": None,
                    "actual": act_val,
                    "diff": None,
                    "diff_percent": None
                })
            elif act_val is None and exp_val is not None:
                mismatches.append({
                    "type": "missing_in_actual",
                    "param": param,
                    "expected": exp_val,
                    "actual": None,
                    "diff": None,
                    "diff_percent": None
                })
            elif isinstance(exp_val, (int, float)) and isinstance(act_val, (int, float)):
                diff = abs(exp_val - act_val)
                if exp_val != 0:
                    diff_percent = diff / abs(exp_val)
                else:
                    diff_percent = 0.0 if diff == 0 else 1.0

                if diff_percent <= tolerance:
                    match_count += 1
                else:
                    mismatches.append({
                        "type": "value_mismatch",
                        "param": param,
                        "expected": exp_val,
                        "actual": act_val,
                        "diff": diff,
                        "diff_percent": diff_percent
                    })
            else:
                if exp_val == act_val:
                    match_count += 1
                else:
                    mismatches.append({
                        "type": "type_mismatch",
                        "param": param,
                        "expected": exp_val,
                        "actual": act_val,
                        "diff": None,
                        "diff_percent": None
                    })

        match_score = match_count / total_params if total_params > 0 else 1.0
        passed = len(mismatches) == 0

        details = (
            f"共 {total_params} 个参数，匹配 {match_count} 个，"
            f"不匹配 {len(mismatches)} 个，匹配度 {match_score:.2%}"
        )

        return VerificationResult(
            passed=passed,
            mismatches=mismatches,
            match_score=match_score,
            details=details
        )

    def get_success_rate(self, intent_type: str | None = None) -> float:
        if intent_type:
            history = self._intent_history.get(intent_type)
            if not history or history["total"] == 0:
                return 0.0
            return history["success"] / history["total"]

        total = len(self.records)
        if total == 0:
            return 0.0
        successful = sum(1 for r in self.records if r.success)
        return successful / total

    def suggest_recovery(self, error_code: str, context: dict | None = None) -> dict:
        strategy = ERROR_RECOVERY_STRATEGIES.get(error_code)

        if not strategy:
            return {
                "error_code": error_code,
                "actions": ["记录错误日志", "检查系统状态", "尝试重试操作"],
                "default": "通用错误：检查日志并重试",
                "known_error": False
            }

        result = {
            "error_code": error_code,
            "actions": list(strategy["actions"]),
            "default": strategy["default"],
            "known_error": True
        }

        if context:
            result["context"] = context

        return result

    def calculate_confidence_adjustment(
        self,
        intent_type: str,
        success: bool,
        base_confidence: float
    ) -> float:
        history_rate = self.get_success_rate(intent_type)
        history_count = self._intent_history.get(intent_type, {}).get("total", 0)

        if success:
            base_adjustment = 0.01 + (history_rate * 0.04)
            if history_count > 10 and history_rate > 0.8:
                base_adjustment *= 0.5
            return min(0.05, base_adjustment)
        else:
            base_adjustment = -0.02 - ((1 - history_rate) * 0.06)
            if history_count > 10 and history_rate < 0.3:
                base_adjustment *= 1.5
            return max(-0.08, base_adjustment)

    def get_learning_summary(self) -> dict:
        total = len(self.records)
        successful = sum(1 for r in self.records if r.success)
        failed = total - successful
        success_rate = successful / total if total > 0 else 0.0

        by_intent = {}
        unique_intents = set()

        for record in self.records:
            intent = record.intent_type
            unique_intents.add(intent)
            if intent not in by_intent:
                by_intent[intent] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "success_rate": 0.0,
                    "avg_confidence_before": 0.0,
                    "avg_confidence_after": 0.0
                }

            by_intent[intent]["total"] += 1
            if record.success:
                by_intent[intent]["success"] += 1
            else:
                by_intent[intent]["failed"] += 1

            by_intent[intent]["avg_confidence_before"] += record.confidence_before
            by_intent[intent]["avg_confidence_after"] += record.confidence_after

        for intent in by_intent:
            data = by_intent[intent]
            cnt = data["total"]
            data["success_rate"] = data["success"] / cnt if cnt > 0 else 0.0
            data["avg_confidence_before"] /= cnt
            data["avg_confidence_after"] /= cnt

        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "by_intent": by_intent,
            "unique_intents": list(unique_intents)
        }

    def get_recent_records(self, limit: int = 10) -> list[ExecutionRecord]:
        return self.records[-limit:] if limit > 0 else []
