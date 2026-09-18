import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from feedback_loop_manager import (
    ERROR_RECOVERY_STRATEGIES,
    ExecutionRecord,
    FeedbackLoopManager,
    VerificationResult,
)


class TestFeedbackLoopManagerInitialization:
    def test_initialization(self):
        flm = FeedbackLoopManager(confidence_threshold=0.7)
        assert flm.confidence_threshold == 0.7
        assert flm.records == []
        assert flm._intent_history == {}

    def test_initialization_default(self):
        flm = FeedbackLoopManager()
        assert flm.confidence_threshold == 0.6


class TestRecordExecution:
    def test_record_successful_execution(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0}}
        actual = {"settings": {"intensity": 50.0}}

        record = flm.record_execution(
            user_input="添加电影感效果",
            intent_type="apply_effect",
            success=True,
            expected=expected,
            actual=actual,
            base_confidence=0.5,
        )

        assert isinstance(record, ExecutionRecord)
        assert record.success is True
        assert record.intent_type == "apply_effect"
        assert record.user_input == "添加电影感效果"
        assert record.confidence_before == 0.5
        assert record.confidence_after > 0.5
        assert len(flm.records) == 1
        assert flm._intent_history["apply_effect"]["success"] == 1
        assert flm._intent_history["apply_effect"]["total"] == 1

    def test_record_failed_execution(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0}}
        actual = {"settings": {"intensity": 30.0}}

        record = flm.record_execution(
            user_input="添加发光效果",
            intent_type="apply_effect",
            success=False,
            expected=expected,
            actual=actual,
            error_message="效果参数不匹配",
            error_code="PROPERTY_NOT_FOUND",
            base_confidence=0.6,
        )

        assert record.success is False
        assert record.error_code == "PROPERTY_NOT_FOUND"
        assert record.error_message == "效果参数不匹配"
        assert record.confidence_after < 0.6
        assert flm._intent_history["apply_effect"]["success"] == 0
        assert flm._intent_history["apply_effect"]["total"] == 1


class TestVerifyParameters:
    def test_verify_parameters_match(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0, "radius": 20.0}}
        actual = {"settings": {"intensity": 50.0, "radius": 20.0}}

        result = flm.verify_parameters(expected, actual)
        assert isinstance(result, VerificationResult)
        assert result.passed is True
        assert result.match_score == 1.0
        assert len(result.mismatches) == 0

    def test_verify_parameters_mismatch(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0, "radius": 20.0}}
        actual = {"settings": {"intensity": 30.0, "radius": 20.0}}

        result = flm.verify_parameters(expected, actual, tolerance=0.01)
        assert result.passed is False
        assert result.match_score == 0.5
        assert len(result.mismatches) == 1
        assert result.mismatches[0]["type"] == "value_mismatch"
        assert result.mismatches[0]["param"] == "intensity"

    def test_verify_parameters_with_tolerance(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0}}
        actual = {"settings": {"intensity": 51.0}}

        result_strict = flm.verify_parameters(expected, actual, tolerance=0.01)
        assert result_strict.passed is False

        result_loose = flm.verify_parameters(expected, actual, tolerance=0.05)
        assert result_loose.passed is True

    def test_verify_parameters_missing_in_actual(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {"intensity": 50.0, "radius": 20.0}}
        actual = {"settings": {"intensity": 50.0}}

        result = flm.verify_parameters(expected, actual)
        assert result.passed is False
        assert len(result.mismatches) == 1
        assert result.mismatches[0]["type"] == "missing_in_actual"

    def test_verify_parameters_empty(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {}}
        actual = {"settings": {}}

        result = flm.verify_parameters(expected, actual)
        assert result.passed is True
        assert result.match_score == 1.0


class TestSuccessRate:
    def test_get_success_rate(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {}}
        actual = {"settings": {}}

        for i in range(7):
            flm.record_execution(f"test{i}", "intent_a", True, expected, actual)
        for i in range(3):
            flm.record_execution(f"test{i}", "intent_a", False, expected, actual)

        rate = flm.get_success_rate()
        assert rate == pytest.approx(0.7)

    def test_get_success_rate_by_intent(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {}}
        actual = {"settings": {}}

        for i in range(8):
            flm.record_execution(f"test{i}", "intent_a", True, expected, actual)
        for i in range(2):
            flm.record_execution(f"test{i}", "intent_a", False, expected, actual)
        for i in range(3):
            flm.record_execution(f"test{i}", "intent_b", True, expected, actual)
        for i in range(7):
            flm.record_execution(f"test{i}", "intent_b", False, expected, actual)

        rate_a = flm.get_success_rate("intent_a")
        rate_b = flm.get_success_rate("intent_b")

        assert rate_a == pytest.approx(0.8)
        assert rate_b == pytest.approx(0.3)

    def test_get_success_rate_empty(self):
        flm = FeedbackLoopManager()
        assert flm.get_success_rate() == 0.0
        assert flm.get_success_rate("nonexistent") == 0.0


class TestRecovery:
    def test_suggest_recovery(self):
        flm = FeedbackLoopManager()

        for error_code in ERROR_RECOVERY_STRATEGIES.keys():
            result = flm.suggest_recovery(error_code)
            assert result["error_code"] == error_code
            assert result["known_error"] is True
            assert len(result["actions"]) > 0
            assert "default" in result

    def test_suggest_recovery_unknown(self):
        flm = FeedbackLoopManager()
        result = flm.suggest_recovery("UNKNOWN_ERROR_CODE")
        assert result["error_code"] == "UNKNOWN_ERROR_CODE"
        assert result["known_error"] is False
        assert len(result["actions"]) > 0

    def test_suggest_recovery_with_context(self):
        flm = FeedbackLoopManager()
        context = {"effect_name": "Glow", "param": "intensity"}
        result = flm.suggest_recovery("EFFECT_NOT_FOUND", context=context)
        assert "context" in result
        assert result["context"] == context


class TestConfidenceAdjustment:
    def test_calculate_confidence_adjustment(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {}}
        actual = {"settings": {}}

        for i in range(5):
            flm.record_execution(f"test{i}", "intent_a", True, expected, actual)

        adj_success = flm.calculate_confidence_adjustment("intent_a", True, 0.5)
        adj_failure = flm.calculate_confidence_adjustment("intent_a", False, 0.5)

        assert adj_success > 0
        assert adj_failure < 0
        assert adj_success <= 0.05
        assert adj_failure >= -0.08

    def test_calculate_confidence_adjustment_new_intent(self):
        flm = FeedbackLoopManager()

        adj_success = flm.calculate_confidence_adjustment("new_intent", True, 0.5)
        adj_failure = flm.calculate_confidence_adjustment("new_intent", False, 0.5)

        assert adj_success > 0
        assert adj_failure < 0


class TestLearningSummary:
    def test_get_learning_summary(self):
        flm = FeedbackLoopManager()
        expected = {"settings": {}}
        actual = {"settings": {}}

        for i in range(6):
            flm.record_execution(f"test{i}", "intent_a", True, expected, actual)
        for i in range(4):
            flm.record_execution(f"test{i}", "intent_a", False, expected, actual)
        for i in range(8):
            flm.record_execution(f"test{i}", "intent_b", True, expected, actual)
        for i in range(2):
            flm.record_execution(f"test{i}", "intent_b", False, expected, actual)

        summary = flm.get_learning_summary()
        assert summary["total_executions"] == 20
        assert summary["successful"] == 14
        assert summary["failed"] == 6
        assert summary["success_rate"] == pytest.approx(0.7)
        assert "by_intent" in summary
        assert "intent_a" in summary["by_intent"]
        assert "intent_b" in summary["by_intent"]
        assert summary["by_intent"]["intent_a"]["success_rate"] == pytest.approx(0.6)
        assert summary["by_intent"]["intent_b"]["success_rate"] == pytest.approx(0.8)
        assert len(summary["unique_intents"]) == 2

    def test_get_learning_summary_empty(self):
        flm = FeedbackLoopManager()
        summary = flm.get_learning_summary()
        assert summary["total_executions"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0
        assert summary["success_rate"] == 0.0
        assert summary["by_intent"] == {}
        assert summary["unique_intents"] == []
