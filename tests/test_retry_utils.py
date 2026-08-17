"""core.retry_utils 单元测试 - 通用重试与进度回调工具

覆盖范围（最高优先级共享工具缺口）：
- retry_with_backoff 装饰器：成功路径、耗尽重试、可重试/不可重试异常、on_retry回调、max_delay钳制
- call_with_retry 非装饰器模式：RetryConfig/RetryResult字段完整性
- ProgressCallback 上下文管理器：step/update/子进度/成功与失败退出分支
- SubProgressReporter 子进度映射：范围转换正确
- progress_context 轻量上下文：yield update函数、异常时也标记完成
- exponential_backoff 延迟计算：0次尝试、钳制、因子倍增
"""
from __future__ import annotations

import os
import sys
import time
import pytest
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retry_utils import (
    RetryConfig,
    RetryResult,
    retry_with_backoff,
    call_with_retry,
    ProgressCallback,
    SubProgressReporter,
    progress_context,
    exponential_backoff,
)


# ============================================================
# 数据类测试
# ============================================================


class TestRetryConfig:
    def test_default_values(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.backoff_factor == 2.0
        assert cfg.retryable_exceptions == (Exception,)
        assert cfg.on_retry is None

    def test_custom_values(self):
        def dummy_cb(a, b, c):
            pass

        cfg = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=10.0,
            backoff_factor=1.5,
            retryable_exceptions=(ValueError, TypeError),
            on_retry=dummy_cb,
        )
        assert cfg.max_retries == 5
        assert cfg.base_delay == 0.5
        assert cfg.backoff_factor == 1.5
        assert cfg.on_retry is dummy_cb


class TestRetryResult:
    def test_default_values(self):
        r = RetryResult()
        assert r.success is False
        assert r.attempts == 0
        assert r.total_delay == 0.0
        assert r.last_error is None
        assert r.errors == []

    def test_failure_fields_populated(self):
        err = ValueError("boom")
        r = RetryResult(
            success=False,
            attempts=3,
            total_delay=2.5,
            last_error=err,
            errors=["ValueError: boom"],
        )
        assert r.success is False
        assert r.attempts == 3
        assert r.total_delay == 2.5
        assert r.last_error is err
        assert r.errors == ["ValueError: boom"]


# ============================================================
# exponential_backoff - 纯函数，边界条件密集
# ============================================================


class TestExponentialBackoff:
    def test_attempt_0_is_base_delay(self):
        assert exponential_backoff(0, base_delay=1.0) == 1.0

    def test_attempt_1_is_base_times_factor(self):
        # attempt 0: 1.0, attempt 1: 1.0*2 = 2.0
        assert exponential_backoff(1, base_delay=1.0, backoff_factor=2.0) == 2.0

    def test_attempt_2_grows_exponentially(self):
        # attempt 0: 1, attempt 1: 2, attempt 2: 4
        assert exponential_backoff(2, base_delay=1.0, backoff_factor=2.0) == 4.0

    def test_max_delay_clamps_early_attempts(self):
        # attempt 2 would be 1*2*2 = 4.0, but max is 3.0
        assert exponential_backoff(2, base_delay=1.0, max_delay=3.0, backoff_factor=2.0) == 3.0

    def test_huge_attempts_never_exceed_max(self):
        # 1.0 * 2^100 is enormous, must be clamped to max_delay
        assert exponential_backoff(100, base_delay=1.0, max_delay=5.0, backoff_factor=2.0) == 5.0

    def test_factor_1_is_constant(self):
        # backoff_factor=1 means constant delay
        for attempt in range(10):
            assert exponential_backoff(attempt, base_delay=2.0, backoff_factor=1.0) == 2.0


# ============================================================
# retry_with_backoff 装饰器
# ============================================================


class TestRetryWithBackoff:
    """使用 mock time.sleep 避免真实等待"""

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_success_on_first_try_no_sleep(self, mock_sleep):
        call_count = {"n": 0}

        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def flaky():
            call_count["n"] += 1
            return "ok"

        assert flaky() == "ok"
        assert call_count["n"] == 1
        mock_sleep.assert_not_called()

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_recovers_after_one_failure(self, mock_sleep):
        call_count = {"n": 0}

        @retry_with_backoff(max_retries=3, base_delay=0.1)
        def flaky():
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("transient")
            return "ok"

        assert flaky() == "ok"
        assert call_count["n"] == 2
        # 一次重试，应 sleep 一次
        assert mock_sleep.call_count == 1

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_exhausts_retries_then_raises(self, mock_sleep):
        """耗尽 max_retries+1 次尝试后，必须抛出原始异常"""
        call_count = {"n": 0}

        @retry_with_backoff(max_retries=2, base_delay=0.1)
        def always_fail():
            call_count["n"] += 1
            raise ValueError("persistent")

        with pytest.raises(ValueError, match="persistent"):
            always_fail()

        # max_retries=2 -> 首次尝试 + 2 次重试 = 3 次
        assert call_count["n"] == 3
        # 重试间 sleep 2 次
        assert mock_sleep.call_count == 2

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_non_retryable_exception_no_retry(self, mock_sleep):
        """不在 retryable_exceptions 中的异常立即抛出，不重试"""
        call_count = {"n": 0}

        @retry_with_backoff(
            max_retries=3,
            base_delay=0.1,
            retryable_exceptions=(RuntimeError,),
        )
        def raise_value_error():
            call_count["n"] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            raise_value_error()

        # 只尝试一次
        assert call_count["n"] == 1
        mock_sleep.assert_not_called()

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_on_retry_callback_invoked(self, mock_sleep):
        """on_retry 回调每次重试都应被调用，参数正确"""
        call_count = {"n": 0}
        callbacks = []

        def my_on_retry(attempt, exc, delay):
            callbacks.append((attempt, type(exc).__name__, delay))

        @retry_with_backoff(
            max_retries=2,
            base_delay=0.1,
            max_delay=5.0,
            backoff_factor=2.0,
            on_retry=my_on_retry,
        )
        def always_fail():
            call_count["n"] += 1
            raise RuntimeError(f"fail-{call_count['n']}")

        with pytest.raises(RuntimeError):
            always_fail()

        assert len(callbacks) == 2
        # attempt 从 0 开始
        assert callbacks[0][0] == 0
        assert callbacks[0][1] == "RuntimeError"
        # delay 序列: attempt 0 用 base_delay=0.1, attempt 1 用 0.2
        assert callbacks[0][2] == pytest.approx(0.1)
        assert callbacks[1][2] == pytest.approx(0.2)

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_max_delay_clamps_sleep_duration(self, mock_sleep):
        """指数退避计算的延迟不应超过 max_delay"""
        delays_recorded = []

        def on_retry(attempt, exc, delay):
            delays_recorded.append(delay)

        # base=1.0, factor=2.0, max=0.5 => 所有重试延迟都被钳制到 0.5
        @retry_with_backoff(
            max_retries=3,
            base_delay=1.0,
            max_delay=0.5,
            backoff_factor=2.0,
            on_retry=on_retry,
        )
        def always_fail():
            raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            always_fail()

        assert len(delays_recorded) == 3
        for d in delays_recorded:
            assert d <= 0.5

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_zero_retries_means_single_attempt(self, mock_sleep):
        """max_retries=0 不应重试（只执行 1 次）"""
        call_count = {"n": 0}

        @retry_with_backoff(max_retries=0, base_delay=0.1)
        def fail_once():
            call_count["n"] += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            fail_once()

        assert call_count["n"] == 1
        mock_sleep.assert_not_called()

    def test_decorator_preserves_function_metadata(self):
        """functools.wraps 应保留原名和文档"""
        @retry_with_backoff(max_retries=1)
        def my_special_function():
            """这是我的文档"""
            pass

        assert my_special_function.__name__ == "my_special_function"
        assert my_special_function.__doc__ == "这是我的文档"


# ============================================================
# call_with_retry - 非装饰器模式
# ============================================================


class TestCallWithRetry:
    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_success_returns_proper_result(self, mock_sleep):
        def good():
            return 42

        result = call_with_retry(good, config=RetryConfig(max_retries=0))
        assert result.success is True
        assert result.attempts == 1
        assert result.total_delay == 0.0
        assert result.last_error is None
        assert result.errors == []
        mock_sleep.assert_not_called()

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_failure_returns_details(self, mock_sleep):
        def boom():
            raise KeyError("missing")

        cfg = RetryConfig(max_retries=2, base_delay=0.1, retryable_exceptions=(KeyError,))
        result = call_with_retry(boom, config=cfg)

        assert result.success is False
        # max_retries=2 => 3 attempts
        assert result.attempts == 3
        assert isinstance(result.last_error, KeyError)
        assert len(result.errors) == 3
        assert all("KeyError" in e for e in result.errors)
        assert result.total_delay > 0
        # 重试间隔 sleep 2 次
        assert mock_sleep.call_count == 2

    def test_args_and_kwargs_passed_through(self):
        captured = {}

        def my_func(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return "done"

        result = call_with_retry(
            my_func,
            args=(1, 2, 3),
            kwargs={"a": "x", "b": "y"},
            config=RetryConfig(max_retries=0),
        )
        assert result.success is True
        assert captured["args"] == (1, 2, 3)
        assert captured["kwargs"] == {"a": "x", "b": "y"}

    @patch("core.retry_utils.time.sleep", return_value=None)
    def test_retry_kwargs_shortcut(self, mock_sleep):
        """不传 config，直接传 retry 关键字参数"""
        def boom():
            raise RuntimeError("x")

        result = call_with_retry(
            boom,
            max_retries=1,
            base_delay=0.01,
            retryable_exceptions=(RuntimeError,),
        )
        assert result.success is False
        assert result.attempts == 2


# ============================================================
# ProgressCallback 上下文管理器
# ============================================================


class TestProgressCallback:
    def test_no_callback_no_crash(self):
        """callback=None 不应抛异常"""
        with ProgressCallback(None, total_steps=3) as p:
            r1 = p.step("a")
            r2 = p.update(0.5, "b")
        assert r1 == pytest.approx(1 / 3)
        assert r2 == pytest.approx(0.5)

    def test_start_msg_sent_at_enter(self):
        events = []

        def cb(progress, msg):
            events.append((progress, msg))

        with ProgressCallback(cb, total_steps=2, start_msg="开始") as p:
            pass
        # 起始 + 完成 = 2 次
        assert events[0] == (0.0, "开始")
        assert events[-1] == (1.0, "Complete")

    def test_step_produces_fractions(self):
        events = []

        def cb(p, m):
            events.append((round(p, 4), m))

        with ProgressCallback(cb, total_steps=4, complete_msg="完成") as p:
            p.step("step1")
            p.step("step2")
            p.step("step3")
            p.step("step4")

        # 起始 0.0 没传 start_msg
        assert len([e for e in events if e[1].startswith("step")]) == 4
        # 步骤值
        progress_vals = [e[0] for e in events if e[1].startswith("step")]
        assert progress_vals == [0.25, 0.5, 0.75, 1.0]
        # 最后一条是 complete_msg（不会重复发送 1.0 同一进度）
        assert events[-1][1] == "完成"

    def test_update_direct_value(self):
        events = []
        with ProgressCallback(lambda p, m: events.append((p, m)), total_steps=1) as p:
            p.update(0.33, "三分之一")
        assert (0.33, "三分之一") in events

    def test_exception_sends_failed_complete(self):
        """上下文管理器内异常，完成消息应为 Failed 前缀"""
        events = []
        try:
            with ProgressCallback(
                lambda p, m: events.append((p, m)),
                total_steps=1,
                complete_msg="OK",
            ) as p:
                raise RuntimeError("测试异常")
        except RuntimeError:
            pass
        # 最后一次进度应该是 1.0，且消息包含失败信息
        last = events[-1]
        assert last[0] == 1.0
        assert "Failed" in last[1] or "RuntimeError" in last[1]


# ============================================================
# SubProgressReporter 子进度
# ============================================================


class TestSubProgressReporter:
    def test_subprogress_maps_to_parent_range(self):
        """父范围 [0.2, 0.8]，子 0.0 -> 0.2，子 0.5 -> 0.5，子 1.0 -> 0.8"""
        parent_events = []

        def parent_cb(p, m):
            parent_events.append((round(p, 4), m))

        with ProgressCallback(parent_cb, total_steps=1) as parent:
            with parent.subprogress("子任务", 0.2, 0.8) as sub:
                sub.update(0.0, "开头")
                sub.update(0.5, "中间")
                sub.update(1.0, "结尾")

        # 查找子进度消息前缀 "子任务:"
        sub_msgs = [e for e in parent_events if e[1].startswith("子任务:")]
        # 子 0.0 -> 父 0.2
        assert sub_msgs[0][0] == pytest.approx(0.2)
        assert "开头" in sub_msgs[0][1]
        # 子 0.5 -> 父 0.2 + 0.6*0.5 = 0.5
        assert sub_msgs[1][0] == pytest.approx(0.5)
        # 子 1.0 -> 父 0.8
        assert sub_msgs[2][0] == pytest.approx(0.8)

    def test_subprogress_without_msg_prefix_strips_colon(self):
        """子 msg 为空时只使用前缀"""
        parent_events = []
        with ProgressCallback(lambda p, m: parent_events.append((p, m)), total_steps=1) as parent:
            with parent.subprogress("前缀", 0.0, 1.0) as sub:
                sub.update(0.5, "")
        # 消息应该只是 "前缀"（没有尾随冒号空格）
        msgs = [e[1] for e in parent_events]
        assert "前缀" in msgs


# ============================================================
# progress_context 轻量上下文
# ============================================================


class TestProgressContext:
    def test_yields_update_function(self):
        events = []

        def cb(p, m):
            events.append((p, m))

        with progress_context(cb, start_msg="起", complete_msg="终") as update:
            update(0.5, "中间")
            update(0.75, "快了")

        assert (0.0, "起") in events
        assert (0.5, "中间") in events
        assert (0.75, "快了") in events
        assert events[-1] == (1.0, "终")

    def test_exception_still_sends_complete(self):
        """即使异常，finally 也会发送 1.0 完成进度"""
        events = []
        try:
            with progress_context(lambda p, m: events.append((p, m)), complete_msg="完"):
                raise ValueError("中断")
        except ValueError:
            pass
        assert events[-1] == (1.0, "完")

    def test_none_callback_noop(self):
        """callback=None 不崩溃"""
        with progress_context(None) as update:
            update(0.5, "ok")
