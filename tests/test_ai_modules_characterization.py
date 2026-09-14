"""ai/ 纯逻辑模块 characterization（特征/黄金基准）测试网。

背景（2026-09-14 全景审计 A5 覆盖率）：
    ai/ 下大量模块单元覆盖为 0%；其中相当一部分是**纯逻辑/纯数学**（无外部服务、
    无 GPU、无网络），最适合先行补"安全网"。
    本文件遵循与 `test_core_god_files_characterization.py` 相同的原则：
    只钉**真实可观察行为**（纯函数数值、键集、守卫分支），数值用精确黄金值。

覆盖范围（本批）：
    - ai/rhythm_reward.py：踩拍打分族的纯函数
      （on_beat_rate / soft_beat_score / cut_features / _pairwise_accuracy）
      注：score_plan 会 pickle 加载训练模型产物（MODEL_PKL），**非纯函数**，
      故不在此钉值（避免把"模型产物存在性"绑进单测）。
"""
from __future__ import annotations

import pytest

from ai.clarification_engine import (
    ClarificationEngine,
    clarification_engine,
)
from ai.nlu_parser import ConfidenceThresholds, Intent, IntentSlots, IntentType
from ai.rhythm_reward import (
    _pairwise_accuracy,
    cut_features,
    on_beat_rate,
    soft_beat_score,
)

# 共用确定性输入：切点正好落在节拍上
CUTS_ON_BEAT = [1.0, 2.0, 3.0]
BEATS = [1.0, 2.0, 3.0, 4.0]

FEATURE_KEYS = {
    "n_cuts", "cut_rate", "phase_entropy", "phase_conc",
    "shot_dur_mean", "shot_dur_std", "shot_dur_cv", "short_shot_ratio",
    "beat_coverage", "grid_regularity", "phase_mean_sin", "phase_mean_cos",
    "frac_near_015", "frac_near_030", "frac_offbeat",
}


class TestOnBeatRate:
    """硬踩拍率（含自适应容差与空输入守卫）。"""

    def test_perfect_hits(self) -> None:
        assert on_beat_rate(CUTS_ON_BEAT, BEATS) == pytest.approx(1.0)

    def test_all_off_beat(self) -> None:
        assert on_beat_rate([1.3, 2.3, 3.3], BEATS) == pytest.approx(0.0)

    def test_empty_guards(self) -> None:
        assert on_beat_rate([], BEATS) == 0.0
        assert on_beat_rate(CUTS_ON_BEAT, []) == 0.0

    def test_tolerance_is_capped_by_half_beat_interval(self) -> None:
        """容差 = min(tol_ms/1000, 0.2*中位节拍间隔)；间隔 1s 时 0.2s < 默认 0.12s? 不——
        0.2*1.0=0.2 > 0.12，故取 0.12s：0.1s 内命中，0.15s 出局。"""
        assert on_beat_rate([1.1, 2.1, 3.1], BEATS) == pytest.approx(1.0)
        assert on_beat_rate([1.15, 2.15, 3.15], BEATS) == pytest.approx(0.0)


class TestSoftBeatScore:
    """软踩拍得分（主标签，连续梯度）。"""

    def test_perfect_hits(self) -> None:
        assert soft_beat_score(CUTS_ON_BEAT, BEATS) == pytest.approx(1.0)

    def test_half_beat_offset_scores_zero(self) -> None:
        """偏移 = 半拍时 1 - dev/half == 0（half=max(bi/2, 0.1)）。"""
        assert soft_beat_score([1.5, 2.5, 3.5], BEATS) == pytest.approx(0.0)

    def test_quarter_beat_offset_is_partial(self) -> None:
        # dev=0.25, half=0.5 → 每切点 1-0.5=0.5
        assert soft_beat_score([1.25, 2.25, 3.25], BEATS) == pytest.approx(0.5)

    def test_empty_guards(self) -> None:
        assert soft_beat_score([], BEATS) == 0.0
        assert soft_beat_score(CUTS_ON_BEAT, []) == 0.0


class TestCutFeatures:
    """特征提取：键集固定 + 黄金数值。"""

    def test_key_set_is_stable(self) -> None:
        assert set(cut_features(CUTS_ON_BEAT, BEATS, 5.0)) == FEATURE_KEYS

    def test_empty_cuts_returns_all_zero(self) -> None:
        feats = cut_features([], BEATS, 5.0)
        assert set(feats) == FEATURE_KEYS
        assert all(v == 0.0 for v in feats.values())

    def test_golden_values_on_beat_grid(self) -> None:
        feats = cut_features(CUTS_ON_BEAT, BEATS, 5.0)
        assert feats["n_cuts"] == pytest.approx(3.0)
        assert feats["cut_rate"] == pytest.approx(0.6)          # 3 cuts / 5s
        assert feats["shot_dur_mean"] == pytest.approx(1.25)
        assert feats["shot_dur_std"] == pytest.approx(0.4330127, abs=1e-6)
        assert feats["shot_dur_cv"] == pytest.approx(0.3464102, abs=1e-6)
        assert feats["short_shot_ratio"] == pytest.approx(0.0)
        assert feats["beat_coverage"] == pytest.approx(0.75)    # 3 / 4 beats
        assert feats["grid_regularity"] == pytest.approx(1.0)
        # 全部落在节拍上 → 相位完全集中
        assert feats["phase_conc"] == pytest.approx(1.0)
        assert feats["phase_mean_cos"] == pytest.approx(1.0)
        assert feats["phase_mean_sin"] == pytest.approx(0.0)
        assert feats["frac_near_015"] == pytest.approx(1.0)
        assert feats["frac_near_030"] == pytest.approx(1.0)
        assert feats["frac_offbeat"] == pytest.approx(0.0)


class TestPairwiseAccuracy:
    """成对排序准确率（视频级 GroupKFold 验收指标之一）。"""

    def test_returns_accuracy_and_pair_count(self) -> None:
        acc, n_pairs = _pairwise_accuracy([1.0, 2.0, 3.0], [1.1, 1.9, 3.2], ["a", "a", "b"])
        assert acc == pytest.approx(1.0)
        assert n_pairs == 1  # 仅组 "a" 内 2 个样本产生 1 对

    def test_single_group_with_one_item_has_no_pairs(self) -> None:
        acc, n_pairs = _pairwise_accuracy([1.0], [1.0], ["a"])
        assert n_pairs == 0


# ============================================================================
# ai/clarification_engine.py（0% 覆盖；纯槽位补全逻辑，无外部依赖）
# ============================================================================


def _intent(intent_type: str, confidence: float = 0.5, **slots) -> Intent:
    return Intent(
        type=intent_type,
        confidence=confidence,
        slots=IntentSlots(**slots),
        rawInput="raw",
    )


class TestClarificationThresholds:
    def test_confidence_threshold_constants(self) -> None:
        assert ConfidenceThresholds.AUTO_EXECUTE == pytest.approx(0.7)
        assert ConfidenceThresholds.NO_CLARIFICATION == pytest.approx(0.6)
        assert ConfidenceThresholds.MIN_RECOGNITION == pytest.approx(0.3)

    def test_unknown_always_needs_clarification(self) -> None:
        engine = ClarificationEngine()
        assert engine.needs_clarification(_intent(IntentType.UNKNOWN, confidence=0.99)) is True

    def test_needs_clarification_below_threshold(self) -> None:
        engine = ClarificationEngine()
        assert engine.needs_clarification(_intent(IntentType.ADD_EFFECT, 0.59)) is True
        assert engine.needs_clarification(_intent(IntentType.ADD_EFFECT, 0.60)) is False

    def test_should_auto_execute_at_threshold(self) -> None:
        engine = ClarificationEngine()
        assert engine.should_auto_execute(_intent(IntentType.ADD_EFFECT, 0.69)) is False
        assert engine.should_auto_execute(_intent(IntentType.ADD_EFFECT, 0.70)) is True


class TestClarificationQuestionGeneration:
    def test_add_effect_generates_three_questions_in_order(self) -> None:
        questions = ClarificationEngine().generate_questions(_intent(IntentType.ADD_EFFECT))
        assert [q.slot for q in questions] == ["effectName", "targetLayer", "color"]

    def test_filled_slots_suppress_questions(self) -> None:
        questions = ClarificationEngine().generate_questions(
            _intent(IntentType.ADD_EFFECT, effectName="发光", targetLayer="图层001", color="青色")
        )
        assert questions == []

    def test_templates_carry_options(self) -> None:
        questions = ClarificationEngine().generate_questions(_intent(IntentType.ADD_EFFECT))
        by_slot = {q.slot: q for q in questions}
        assert by_slot["effectName"].options == []          # 自由文本槽
        assert "选中图层" in by_slot["targetLayer"].options

    def test_unknown_intent_single_optional_question(self) -> None:
        questions = ClarificationEngine().generate_questions(_intent(IntentType.UNKNOWN))
        assert len(questions) == 1
        assert questions[0].slot == "rawInput"
        assert questions[0].required is False

    def test_reverse_analyze_has_no_questions(self) -> None:
        assert ClarificationEngine().generate_questions(_intent(IntentType.REVERSE_ANALYZE)) == []


class TestClarificationFlow:
    def test_state_walk_and_final_slots(self) -> None:
        engine = ClarificationEngine()
        state = engine.create_state(_intent(IntentType.ADD_EFFECT))

        assert engine.has_more_questions(state) is True
        assert engine.get_next_question(state).slot == "effectName"

        # 答案两端空白被 strip
        engine.answer_question(state, "  发光  ")
        assert state.answered_slots["effectName"] == "发光"
        assert state.current_question_index == 1

        engine.answer_question(state, "图层001")
        engine.answer_question(state, "青色")
        assert engine.has_more_questions(state) is False
        assert engine.get_next_question(state) is None

        final = engine.get_final_slots(state)
        assert final.effectName == "发光"
        assert final.targetLayer == "图层001"
        assert final.color == "青色"

    def test_answering_when_exhausted_is_noop(self) -> None:
        engine = ClarificationEngine()
        state = engine.create_state(_intent(IntentType.REVERSE_ANALYZE))  # 无问题
        before = state.current_question_index
        engine.answer_question(state, "x")
        assert state.current_question_index == before
        assert state.answered_slots == {}

    def test_empty_answer_does_not_override_original_slot(self) -> None:
        """get_final_slots 只在答案非空时覆盖（`if slot in ... and value`）。"""
        engine = ClarificationEngine()
        state = engine.create_state(_intent(IntentType.ADD_EFFECT, effectName="模糊"))
        engine.answer_question(state, "   ")  # 空答案仅推进游标
        assert engine.get_final_slots(state).effectName == "模糊"

    def test_module_singleton_exists(self) -> None:
        assert isinstance(clarification_engine, ClarificationEngine)


class TestConfidenceGap:
    def test_gap_weights_for_empty_slots(self) -> None:
        gaps = ClarificationEngine().analyze_confidence_gap(_intent(IntentType.ADD_EFFECT))
        assert gaps == {"effectName": 0.3, "targetLayer": 0.2, "color": 0.1, "temporal": 0.1}

    def test_filled_slot_removes_its_gap(self) -> None:
        gaps = ClarificationEngine().analyze_confidence_gap(
            _intent(IntentType.ADD_EFFECT, color="青色")
        )
        assert "color" not in gaps
        assert set(gaps) == {"effectName", "targetLayer", "temporal"}
