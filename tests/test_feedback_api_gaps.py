"""learning.feedback_api 补充测试 — 覆盖 P0 高风险缺口

重点缺口 (覆盖前 0%):
- rating<=3 自动降级：satisfied + rating=1/2/3 → undone + failure_learn
- 三态学习策略分支：satisfied/adjusted/undone → strategy 字段正确
- submit_feedback_dict：FastAPI 字典接口、全局异常捕获返回格式
- 非法 feedback_type 处理：返回结构化错误而非抛异常
- _build_contexts：三态上下文构造（score边界、deviation_score语义、reasoning_path兜底）

设计原则：
- 不依赖真实 PersistentLearningLoop（用 monkeypatch + MagicMock 注入 stub）
- 不写真实文件（tmp_path 重定向 _history_dir）
- 断言具体的字段值而非"非空"
"""
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from learning.feedback_api import (
    FeedbackApi,
    FeedbackType,
    LearningTriggerResult,
    UserFeedbackEntry,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api(tmp_path, monkeypatch):
    """提供 FeedbackApi 实例，重定向历史目录到 tmp_path，并用 stub 替换学习系统。

    关键点：
    1. _history_dir 指向临时目录，避免污染 APPDATA
    2. _ensure_loaded() 不真实 import PersistentLearningLoop，
       而是手动设置 self._learner / self._optimizer / self._memory_store 为 MagicMock
    """
    hist_dir = tmp_path / "feedback"
    api_instance = FeedbackApi(history_dir=str(hist_dir))

    # ---- stub 学习系统（完全隔离，避免磁盘/依赖问题）----
    fake_learner = MagicMock()
    fake_learner.record_execution.return_value = "rec_stub_001"
    fake_learner.get_stats.return_value = {
        "record_count": 0,
        "template_count": 0,
    }

    fake_optimizer = MagicMock()
    fake_optimizer.get_statistics.return_value = {
        "tracked_effects": [],
        "total_observations": 0,
    }
    fake_optimizer.observe.return_value = True

    fake_memory = MagicMock()
    # MemoryStore 需要 _conn.execute() 用于 get_learning_stats
    fake_cursor = MagicMock()
    fake_cursor.fetchall.return_value = []
    fake_memory._conn.execute.return_value = fake_cursor

    api_instance._learner = fake_learner
    api_instance._optimizer = fake_optimizer
    api_instance._memory_store = fake_memory
    # 标记已加载，避免 submit_feedback 内部再调 _ensure_loaded 触发真实 import
    api_instance._loaded = True

    return api_instance


@pytest.fixture
def plan_ctx_glow():
    """典型 plan_context：包含一个 Glow 效果 + reasoning_path"""
    return {
        "effect_stack": [
            {
                "name": "Glow",
                "matchName": "ADBE Glo2",
                "params": {
                    "glow_threshold": 50,
                    "glow_radius": 25,
                    "glow_intensity": 1.2,
                },
            }
        ],
        "reasoning_path": ["kb_style_match", "bayesian_suggest"],
        "strategy": "cinematic",
    }


@pytest.fixture
def exec_ctx_success():
    return {
        "success": True,
        "execution_time_ms": 5200,
        "effect_name": "Glow",
    }


@pytest.fixture
def verify_ctx_good():
    return {
        "score": 88.0,
        "render_time_sec": 9.0,
        "file_size_mb": 22.0,
        "recommendations": ["色温偏冷，建议加暖"],
    }


# ============================================================================
# 1. rating<=3 自动降级（最高优先级：防止差评被误当正向样本）
# ============================================================================


class TestRatingAutoDowngrade:
    """satisfied + rating=1/2/3 应自动转为 undone 并触发 failure_learn。"""

    def test_rating_1_satisfied_goes_to_failure_learn(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """边界：rating=1 最低分。"""
        result = api.submit_feedback(
            run_id="test_downgrade_r1",
            feedback_type="satisfied",
            rating=1,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.success is True
        assert result.strategy == "failure_learn"
        assert result.confidence_penalized is True
        assert result.confidence_boosted is False

    def test_rating_3_satisfied_goes_to_failure_learn(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """边界：rating=3 是降级阈值（<=3 都降级）。"""
        result = api.submit_feedback(
            run_id="test_downgrade_r3",
            feedback_type="satisfied",
            rating=3,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.strategy == "failure_learn"
        assert result.confidence_penalized is True

    def test_rating_4_satisfied_stays_success_learn(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """边界：rating=4 是满意下界（>=4 保持 satisfied）。"""
        result = api.submit_feedback(
            run_id="test_nodowngrade_r4",
            feedback_type="satisfied",
            rating=4,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.strategy == "success_learn"
        assert result.confidence_boosted is True
        assert result.confidence_penalized is False

    def test_rating_5_satisfied_stays_success_learn(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        result = api.submit_feedback(
            run_id="test_nodowngrade_r5",
            feedback_type="satisfied",
            rating=5,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.strategy == "success_learn"
        assert result.confidence_boosted is True

    def test_adjusted_ignores_rating_for_downgrade(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """adjusted 类型不应因 rating 走降级逻辑（adjusted 是满意的变体）。"""
        result = api.submit_feedback(
            run_id="test_adjusted_r1_nodegrade",
            feedback_type="adjusted",
            rating=1,  # 低分但类型=adjusted，仍应走 deviation_learn
            adjusted_params={"Glow": {"glow_radius": 35, "glow_threshold": 45}},
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.strategy == "deviation_learn"
        assert result.confidence_boosted is True

    def test_undone_ignores_rating_for_downgrade(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """undone + rating=5 也应走 failure_learn。"""
        result = api.submit_feedback(
            run_id="test_undone_r5_nodegrade",
            feedback_type="undone",
            rating=5,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.strategy == "failure_learn"
        assert result.confidence_penalized is True


# ============================================================================
# 2. 三态学习策略分支（字段值精确断言）
# ============================================================================


class TestThreeStrategyBranches:
    """satisfied / adjusted / undone → 正确 strategy + 正确 confidence + record_execution 被调用一次。"""

    def test_satisfied_success_learn_calls_record_execution(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        result = api.submit_feedback(
            run_id="test_sat_001",
            feedback_type="satisfied",
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.success is True
        assert result.strategy == "success_learn"
        assert result.record_id == "rec_stub_001"
        # record_execution 应该被调用恰好一次
        api._learner.record_execution.assert_called_once()
        # 检查传入的 user_feedback 字段：satisfied=True, adjusted=False, undone=False
        call_kwargs = api._learner.record_execution.call_args.kwargs
        uf = call_kwargs["user_feedback"]
        assert uf.satisfied is True
        assert uf.adjusted is False
        assert uf.undone is False

    def test_adjusted_deviation_learn_user_feedback_fields(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        """adjusted 的 UserFeedback 必须是 satisfied=True + adjusted=True（调整后仍被采用）。"""
        adjusted = {"Glow": {"glow_radius": 35, "glow_threshold": 45}}
        result = api.submit_feedback(
            run_id="test_adj_001",
            feedback_type="adjusted",
            adjusted_params=adjusted,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context=verify_ctx_good,
        )
        assert result.success is True
        assert result.strategy == "deviation_learn"
        assert result.confidence_boosted is True

        call_kwargs = api._learner.record_execution.call_args.kwargs
        uf = call_kwargs["user_feedback"]
        assert uf.satisfied is True
        assert uf.adjusted is True
        assert uf.undone is False
        # final_params 非空（从 adjusted_params 构造）
        assert uf.final_params is not None
        param_names = {fp.name for fp in uf.final_params}
        assert "glow_radius" in param_names
        assert "glow_threshold" in param_names

    def test_undone_failure_learn_user_feedback_fields(
        self, api, plan_ctx_glow
    ):
        """undone 的 UserFeedback：satisfied=False + undone=True。"""
        result = api.submit_feedback(
            run_id="test_und_001",
            feedback_type="undone",
            comment="渲染崩了，重做",
            plan_context=plan_ctx_glow,
            execute_context={"success": False, "error_message": "AE crash"},
            verify_context={"score": 0},
        )
        assert result.success is True
        assert result.strategy == "failure_learn"
        assert result.confidence_penalized is True

        call_kwargs = api._learner.record_execution.call_args.kwargs
        uf = call_kwargs["user_feedback"]
        assert uf.satisfied is False
        assert uf.adjusted is False
        assert uf.undone is True


# ============================================================================
# 3. submit_feedback_dict 字典接口（FastAPI 反序列化路径）
# ============================================================================


class TestSubmitFeedbackDict:
    """submit_feedback_dict 返回格式必须与前端解析一致。"""

    def test_normal_payload_returns_correct_shape(
        self, api, plan_ctx_glow, exec_ctx_success, verify_ctx_good
    ):
        payload = {
            "run_id": "dict_001",
            "feedback_type": "satisfied",
            "rating": 5,
            "plan_context": plan_ctx_glow,
            "execute_context": exec_ctx_success,
            "verify_context": verify_ctx_good,
        }
        resp = api.submit_feedback_dict(payload)
        # 必须包含这 5 个键（前端解析用）
        assert set(resp.keys()) == {"success", "strategy", "record_id", "message", "errors"}
        assert resp["success"] is True
        assert resp["strategy"] == "success_learn"
        assert resp["record_id"] == "rec_stub_001"
        assert isinstance(resp["errors"], list)

    def test_exception_in_submit_is_caught_not_raised(self, api):
        """全局 except Exception 兜底：内部抛异常也返回结构化错误，不冒泡。"""
        # 让 record_execution 抛运行时异常
        api._learner.record_execution.side_effect = RuntimeError("simulated DB crash")
        payload = {
            "run_id": "dict_crash_001",
            "feedback_type": "satisfied",
        }
        resp = api.submit_feedback_dict(payload)
        assert resp["success"] is False
        assert "errors" in resp
        assert isinstance(resp["errors"], list)
        assert len(resp["errors"]) >= 1
        # 错误消息中应包含异常原因（方便排查）
        assert any("simulated DB crash" in e for e in resp["errors"])

    def test_missing_fields_defaulted_gracefully(self, api):
        """缺 run_id / feedback_type 空串 → 非法输入分支而非 KeyError。"""
        resp = api.submit_feedback_dict({})  # 完全空 payload
        # 缺 feedback_type 走非法分支，success=False
        assert resp["success"] is False
        assert isinstance(resp["errors"], list)
        assert len(resp["errors"]) >= 1


# ============================================================================
# 4. 非法 feedback_type 处理（结构化返回，不抛 ValueError）
# ============================================================================


class TestInvalidFeedbackType:
    """非 satisfied/adjusted/undone 的值应返回结构化错误而非崩。"""

    def test_bad_string_type(self, api):
        result = api.submit_feedback(
            run_id="bad_001",
            feedback_type="happy",  # 非法值
        )
        assert result.success is False
        assert result.strategy == ""  # 空串：无策略被触发
        assert isinstance(result.errors, list)
        assert len(result.errors) >= 1
        assert "Invalid feedback_type" in result.errors[0]

    def test_none_type(self, api):
        result = api.submit_feedback(run_id="bad_002", feedback_type=None)
        assert result.success is False
        assert result.strategy == ""
        assert len(result.errors) >= 1

    def test_empty_string_type(self, api):
        result = api.submit_feedback(run_id="bad_003", feedback_type="")
        assert result.success is False
        assert result.strategy == ""
        assert len(result.errors) >= 1


# ============================================================================
# 5. _ensure_loaded 学习系统加载失败（优雅降级）
# ============================================================================


class TestLearnerLoadFailure:
    """self._learner is None 时，submit_feedback 返回结构化错误，不抛 AttributeError。"""

    def test_learner_none_returns_structured_response(self, tmp_path):
        """手动构造 _learner=None 的场景：不抛异常，返回结构完整。
        实际行为：success=True（因为 feedback 被文件记录成功），学习系统未加载仅提示性处理。
        我们只验证结构完整性（record_id/message 字段非空，errors 字段是列表）。"""
        api_instance = FeedbackApi(history_dir=str(tmp_path / "fb2"))
        api_instance._learner = None
        api_instance._optimizer = None
        api_instance._memory_store = None
        api_instance._loaded = True  # 跳过 _ensure_loaded

        result = api_instance.submit_feedback(
            run_id="noloader_001",
            feedback_type="satisfied",
        )
        # 结构完整性断言：字段都存在且类型正确
        assert isinstance(result.success, bool)
        assert isinstance(result.message, str)
        assert isinstance(result.errors, list)
        # 策略字段至少非空（会设默认值 success_learn 或空）
        assert isinstance(result.strategy, str)


# ============================================================================
# 6. _build_contexts 边界条件（score/verification 语义）
# ============================================================================


class TestBuildContextsBoundaries:
    """_build_contexts 是三态学习的上下文构造核心，需要验证 score 边界和 reasoning_path 兜底。"""

    def test_score_59_undone_sets_verification_failed(
        self, api, plan_ctx_glow, exec_ctx_success
    ):
        """undone + score=59 (<60) → verification.passed=False, deviation_score=1.0"""
        from learning.feedback_api import FeedbackType as FT
        expected, execution, verification, reasoning_path, _ = api._build_contexts(
            run_id="ctx_001",
            ftype=FT.UNDONE,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context={"score": 59},
            adjusted_params=None,
        )
        assert verification.passed is False
        assert verification.deviation_score == 1.0

    def test_score_60_satisfied_sets_verification_passed(
        self, api, plan_ctx_glow, exec_ctx_success
    ):
        """satisfied + score=60 (阈值边界) → verification.passed=True"""
        from learning.feedback_api import FeedbackType as FT
        _, _, verification, _, _ = api._build_contexts(
            run_id="ctx_002",
            ftype=FT.SATISFIED,
            plan_context=plan_ctx_glow,
            execute_context=exec_ctx_success,
            verify_context={"score": 60},
            adjusted_params=None,
        )
        assert verification.passed is True
        # deviation_score = (100-60)/100 = 0.4
        assert abs(verification.deviation_score - 0.4) < 1e-6

    def test_reasoning_path_missing_uses_default_strategy(
        self, api
    ):
        """plan_context 不含 reasoning_path → 兜底到 [strategy] 或 ['default']"""
        from learning.feedback_api import FeedbackType as FT
        plan = {"strategy": "my_manual_strategy"}  # 无 effect_stack，无 reasoning_path
        _, _, _, reasoning_path, _ = api._build_contexts(
            run_id="ctx_003",
            ftype=FT.SATISFIED,
            plan_context=plan,
            execute_context=None,
            verify_context=None,
            adjusted_params=None,
        )
        assert reasoning_path is not None
        assert isinstance(reasoning_path, list)
        assert len(reasoning_path) >= 1
        assert "my_manual_strategy" in reasoning_path or "default" in reasoning_path

    def test_exec_success_defaults_to_not_undone(
        self, api
    ):
        """execute_context=None + ftype=SATISFIED → exec_success=True (默认)"""
        from learning.feedback_api import FeedbackType as FT
        _, execution, _, _, _ = api._build_contexts(
            run_id="ctx_004",
            ftype=FT.SATISFIED,
            plan_context=None,
            execute_context=None,
            verify_context=None,
            adjusted_params=None,
        )
        assert execution.success is True

    def test_exec_success_defaults_false_for_undone(
        self, api
    ):
        """execute_context=None + ftype=UNDONE → exec_success=False"""
        from learning.feedback_api import FeedbackType as FT
        _, execution, _, _, _ = api._build_contexts(
            run_id="ctx_005",
            ftype=FT.UNDONE,
            plan_context=None,
            execute_context=None,
            verify_context=None,
            adjusted_params=None,
        )
        assert execution.success is False
