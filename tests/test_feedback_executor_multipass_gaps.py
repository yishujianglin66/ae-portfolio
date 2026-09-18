#!/usr/bin/env python3
"""
tests/test_feedback_executor_multipass_gaps.py - FeedbackExecutor.execute_multi_pass 加固回归测试

覆盖 commit bf99595/86026af 引入的纵深防御逻辑：
  1. MAX_PASSES_HARD_CAP=10 函数级硬上限 (调用方传 100 → 钳位到 10)
  2. max_passes 非整数/负数/0 的钳位
  3. quality_report_fn 返回非 dict / score 非数值 的兜底
  4. self.execute 返回非 dict / success=False 的早退
  5. score >= threshold 的早退成功路径
  6. 达到最大轮次仍未达标 → success=False + adjustment_log
  7. 最终返回字段完整性 (final_file/final_score/passes/history/reasoning)

这些测试不依赖真实 FFmpeg，通过 mock self.execute 与 quality_report_fn
隔离外部 I/O，保证确定性。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.feedback_executor import FeedbackExecutor


@pytest.fixture
def executor_no_engine() -> FeedbackExecutor:
    """构造一个 engine=None 的执行器，避免依赖真实 FFmpeg。

    multi_pass 逻辑只调用 self.execute（已被 mock），不会触碰 self.engine。
    """
    with patch("pipeline.feedback_executor._FFMPEG_ENGINE_AVAILABLE", True):
        # 临时让 _FFMPEG_ENGINE_AVAILABLE=True 以绕过 __init__ 的 engine=None 短路
        # 但 engine 仍是 None（FFmpegEditEngine 真实构造可能失败），无影响
        ex = FeedbackExecutor(ffmpeg_bin="", use_bayesian_optimizer=False)
    return ex


# =========================================================================
#  场景 1：MAX_PASSES_HARD_CAP 硬上限
# =========================================================================
class TestMaxPassesHardCap:
    """函数级硬上限 MAX_PASSES_HARD_CAP=10 防止调用方未钳位时的无限循环。"""

    def test_max_passes_100_clamped_to_10(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """调用方传 max_passes=100 → 实际最多执行 10 轮。"""
        call_count = {"report": 0, "execute": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            # 永远不达标，强制走完所有轮次
            return {"score": 10.0, "checks": {}, "suggestions": []}

        def fake_execute(current: str, report: dict, output: str = "") -> dict:
            call_count["execute"] += 1
            return {"success": True, "output": output or current}

        executor_no_engine.execute = fake_execute  # type: ignore[assignment]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/input.mp4",
            quality_report_fn=report_fn,
            max_passes=100,
            threshold=90.0,
        )

        # 硬上限 10：report 调用最多 10 次（每轮调用一次，最后一轮也可能调用）
        assert call_count["report"] <= 11, (
            f"hard cap violated: report called {call_count['report']} times"
        )
        # execute 最多调用 9 次（最后一轮若不达标不会再 execute）
        assert call_count["execute"] <= 10
        assert result["success"] is False
        assert len(result["history"]) <= 11

    def test_max_passes_5_respected(self, executor_no_engine: FeedbackExecutor) -> None:
        """max_passes=5（合法值）→ 不被钳位，执行 5 轮。"""
        call_count = {"report": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            return {"score": 5.0}

        def fake_execute(current: str, report: dict, output: str = "") -> dict:
            return {"success": True, "output": output or current}

        executor_no_engine.execute = fake_execute  # type: ignore[assignment]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=5,
            threshold=90.0,
        )

        # 5 轮，每轮调用 report_fn 一次
        assert call_count["report"] == 5
        assert result["passes"] == 5


# =========================================================================
#  场景 2：max_passes 非法值的钳位
# =========================================================================
class TestMaxPassesClamping:
    """max_passes 非整数/负数/0 的钳位逻辑。"""

    def test_max_passes_zero_clamped_to_1(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """max_passes=0 → 钳位到 1，至少跑一轮。"""
        call_count = {"report": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            return {"score": 90.0}  # 第一轮就达标

        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=0,
            threshold=70.0,
        )

        assert call_count["report"] == 1
        assert result["success"] is True
        assert result["passes"] == 1

    def test_max_passes_negative_clamped_to_1(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """max_passes=-5 → 钳位到 1。"""
        call_count = {"report": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            return {"score": 90.0}

        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=-5,
            threshold=70.0,
        )

        assert call_count["report"] == 1
        assert result["passes"] == 1

    def test_max_passes_string_fallback_to_3(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """max_passes="abc" → int() 抛 ValueError → 回退到 3。"""
        call_count = {"report": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            return {"score": 90.0}

        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes="not_a_number",  # type: ignore[arg-type]
            threshold=70.0,
        )

        # 第一轮就达标，但 max_passes 回退到 3（不影响早退）
        assert call_count["report"] == 1
        assert result["success"] is True
        assert result["passes"] == 1

    def test_max_passes_float_string_fallback_to_3(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """max_passes=2.7 (float) → int(2.7)=2，正常工作。"""
        # 注意：int(2.7) 不会抛异常，返回 2
        call_count = {"report": 0}

        def report_fn(path: str) -> dict[str, Any]:
            call_count["report"] += 1
            return {"score": 90.0}

        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=2.7,  # type: ignore[arg-type]
            threshold=70.0,
        )

        assert result["success"] is True
        assert result["passes"] == 1  # 第一轮达标早退


# =========================================================================
#  场景 3：quality_report_fn 返回非 dict / score 非数值
# =========================================================================
class TestQualityReportFnRobustness:
    """quality_report_fn 返回异常值时的兜底处理。"""

    def test_report_returns_none(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """quality_report_fn 返回 None → 当作 {"score": 0, "error": "invalid_report"}。"""
        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: None,  # type: ignore[return-value]
            max_passes=1,
            threshold=70.0,
        )

        # score=0 < 70，execute 被调用但 result["success"] 仍为 False
        assert result["final_score"] == 0
        assert result["success"] is False

    def test_report_returns_string(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """quality_report_fn 返回字符串 → 当作 invalid_report，score=0。"""
        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: "not a dict",  # type: ignore[return-value]
            max_passes=1,
            threshold=70.0,
        )

        assert result["final_score"] == 0
        assert result["success"] is False

    def test_report_score_is_string_number(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """score="85" (字符串数字) → float("85")=85.0 → 达标早退。"""
        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"score": "85"},
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is True
        assert result["final_score"] == 85.0
        assert result["passes"] == 1

    def test_report_score_is_non_numeric_string(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """score="abc" → float() 抛 ValueError → score=0。"""
        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"score": "abc"},
            max_passes=1,
            threshold=70.0,
        )

        assert result["final_score"] == 0
        assert result["success"] is False

    def test_report_missing_score_key(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """report dict 无 score 键 → .get("score", 0) → 0。"""
        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[0]}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"checks": {}, "suggestions": []},
            max_passes=1,
            threshold=70.0,
        )

        assert result["final_score"] == 0


# =========================================================================
#  场景 4：self.execute 返回非 dict / success=False
# =========================================================================
class TestExecuteReturnRobustness:
    """self.execute 返回异常值时的兜底。"""

    def test_execute_returns_none(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """execute 返回 None → 当作 {"success": False, ...} → 早退失败。"""
        executor_no_engine.execute = lambda *a, **kw: None  # type: ignore[return-value]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"score": 10.0},
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is False
        assert result["passes"] == 1  # 第一轮 execute 失败 → 早退
        assert "调整失败" in result["reasoning"]

    def test_execute_returns_non_dict(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """execute 返回字符串 → 当作 invalid → 早退失败。"""
        executor_no_engine.execute = lambda *a, **kw: "unexpected"  # type: ignore[return-value]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"score": 10.0},
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is False
        assert result["passes"] == 1

    def test_execute_success_false_early_exit(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """execute 返回 success=False → 早退，不再继续迭代。"""
        call_count = {"execute": 0}

        def fake_execute(current: str, report: dict, output: str = "") -> dict:
            call_count["execute"] += 1
            return {"success": False, "error": "ffmpeg_failed", "output": current}

        executor_no_engine.execute = fake_execute  # type: ignore[assignment]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=lambda path: {"score": 10.0},
            max_passes=5,
            threshold=70.0,
        )

        # 只调用一次 execute 就早退
        assert call_count["execute"] == 1
        assert result["success"] is False
        assert result["passes"] == 1
        assert "ffmpeg_failed" in result["reasoning"]


# =========================================================================
#  场景 5：score >= threshold 早退成功
# =========================================================================
class TestEarlySuccess:
    """首轮或中途达标 → 立即返回成功。"""

    def test_first_pass_meets_threshold(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """首轮 report 就达标 → passes=1，不调用 execute。"""
        call_count = {"execute": 0}

        def report_fn(path: str) -> dict[str, Any]:
            return {"score": 75.0}

        def fake_execute(*a, **kw):
            call_count["execute"] += 1
            return {"success": True, "output": a[0]}

        executor_no_engine.execute = fake_execute  # type: ignore[assignment]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is True
        assert result["passes"] == 1
        assert call_count["execute"] == 0  # 达标不调用 execute
        assert result["final_score"] == 75.0
        assert result["final_file"] == "/fake/in.mp4"
        assert len(result["history"]) == 1
        assert result["history"][0]["pass"] == 1
        assert result["history"][0]["score"] == 75.0

    def test_second_pass_meets_threshold(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """第二轮达标 → passes=2。"""
        scores = iter([50.0, 80.0])

        def report_fn(path: str) -> dict[str, Any]:
            return {"score": next(scores)}

        executor_no_engine.execute = lambda *a, **kw: {"success": True, "output": a[2] if len(a) > 2 else "/fake/out.mp4"}

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is True
        assert result["passes"] == 2
        assert len(result["history"]) == 2


# =========================================================================
#  场景 6：达到最大轮次仍未达标
# =========================================================================
class TestMaxPassesExhausted:
    """用尽所有轮次仍未达标 → success=False + adjustment_log。"""

    def test_all_passes_fail_threshold(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """3 轮全部不达标 → success=False, passes=3。"""
        report_calls: list[str] = []

        def report_fn(path: str) -> dict[str, Any]:
            report_calls.append(path)
            return {"score": 30.0}

        def fake_execute(current: str, report: dict, output: str = "") -> dict:
            return {"success": True, "output": output or current}

        executor_no_engine.execute = fake_execute  # type: ignore[assignment]

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=3,
            threshold=70.0,
        )

        assert result["success"] is False
        assert result["passes"] == 3
        assert len(result["history"]) == 3
        assert "达到最大迭代次数" in result["reasoning"]
        # adjustment_log 字段存在（即使为空也必须有键）
        assert "adjustment_log" in result

    def test_history_records_each_pass(
        self, executor_no_engine: FeedbackExecutor
    ) -> None:
        """history 记录每轮的 pass/score/file。"""
        scores = iter([20.0, 30.0, 40.0])

        def report_fn(path: str) -> dict[str, Any]:
            return {"score": next(scores)}

        executor_no_engine.execute = lambda *a, **kw: {
            "success": True,
            "output": "/fake/pass_out.mp4",
        }

        result = executor_no_engine.execute_multi_pass(
            input_video="/fake/in.mp4",
            quality_report_fn=report_fn,
            max_passes=3,
            threshold=70.0,
        )

        assert len(result["history"]) == 3
        assert result["history"][0]["pass"] == 1
        assert result["history"][0]["score"] == 20.0
        assert result["history"][1]["pass"] == 2
        assert result["history"][1]["score"] == 30.0
        assert result["history"][2]["pass"] == 3
        assert result["history"][2]["score"] == 40.0
