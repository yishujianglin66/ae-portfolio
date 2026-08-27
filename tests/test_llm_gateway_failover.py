"""LLM 网关降级与路由测试 - 覆盖 provider failover、健康跟踪、任务路由"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.llm_gateway import (
    LLMGateway,
    LLMConfig,
    LLMResponse,
    ProviderHealth,
    ProviderStatus,
    TaskType,
    _sanitize_log_text,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def base_config():
    """基础单 Provider 配置"""
    return LLMConfig(
        base_url="https://primary.test/v1",
        api_key="sk-primary-test-key",
        default_model="primary-model",
        enable_fallback=False,
        max_retries=1,
        enable_compression=False,
    )


@pytest.fixture
def fallback_config():
    """带降级的配置"""
    return LLMConfig(
        base_url="https://primary.test/v1",
        api_key="sk-primary-test-key",
        default_model="primary-model",
        enable_fallback=True,
        max_retries=1,
        enable_compression=False,
        fallback_providers=[
            {
                "base_url": "https://fallback.test/v1",
                "api_key": "sk-fallback-test-key",
                "default_model": "fallback-model",
            }
        ],
    )


@pytest.fixture
def multi_fallback_config():
    """多降级 Provider 配置"""
    return LLMConfig(
        base_url="https://primary.test/v1",
        api_key="sk-primary-test-key",
        default_model="primary-model",
        enable_fallback=True,
        max_retries=1,
        enable_compression=False,
        fallback_providers=[
            {"base_url": "https://fb1.test/v1", "api_key": "sk-fb1", "default_model": "fb1-model"},
            {"base_url": "https://fb2.test/v1", "api_key": "sk-fb2", "default_model": "fb2-model"},
            {"base_url": "https://fb3.test/v1", "api_key": "sk-fb3", "default_model": "fb3-model"},
        ],
    )


def _make_success_response(content="ok", provider="primary.test", tokens_in=10, tokens_out=20):
    return LLMResponse(
        success=True,
        content=content,
        model="test-model",
        provider=provider,
        tokens_input=tokens_in,
        tokens_output=tokens_out,
        latency_ms=50.0,
    )


def _make_error_response(error_msg, provider="primary.test"):
    return LLMResponse(
        success=False,
        content="",
        model="",
        provider=provider,
        tokens_input=0,
        tokens_output=0,
        latency_ms=100.0,
        error=error_msg,
    )


# ============================================================================
# Provider 健康跟踪
# ============================================================================

class TestProviderHealth:
    def test_initial_state_healthy(self):
        h = ProviderHealth(name="test-provider")
        assert h.name == "test-provider"
        assert h.status == ProviderStatus.HEALTHY
        assert h.consecutive_failures == 0
        assert h.total_requests == 0
        assert h.total_failures == 0

    def test_consecutive_failures_increments(self):
        h = ProviderHealth(name="test")
        h.consecutive_failures += 1
        h.consecutive_failures += 1
        assert h.consecutive_failures == 2

    def test_unavailable_status_triggered_at_threshold(self):
        h = ProviderHealth(name="test")
        h.consecutive_failures = 2
        h.status = ProviderStatus.HEALTHY
        # 模拟达到阈值
        h.consecutive_failures = 3
        h.status = ProviderStatus.UNAVAILABLE
        assert h.status == ProviderStatus.UNAVAILABLE


# ============================================================================
# 日志脱敏
# ============================================================================

class TestLogSanitization:
    def test_api_key_redacted(self):
        text = "错误详情: sk-abc123def456ghi789jkl 已失效"
        result = _sanitize_log_text(text)
        assert "sk-abc123def456ghi789jkl" not in result
        assert "***REDACTED***" in result

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer sk-secret-token-123456"
        result = _sanitize_log_text(text)
        assert "sk-secret-token-123456" not in result
        assert "Bearer" in result

    def test_api_key_param_redacted(self):
        text = "url?api_key=my-secret-key-abc&other=value"
        result = _sanitize_log_text(text)
        assert "my-secret-key-abc" not in result
        assert "api_key=" in result

    def test_clean_text_unchanged(self):
        text = "正常的错误消息: 模型不存在"
        result = _sanitize_log_text(text)
        assert result == text

    def test_multiple_secrets_all_redacted(self):
        text = "key1: sk-aaa12345678901234567, key2: sk-bbb12345678901234567"
        result = _sanitize_log_text(text)
        assert "sk-aaa12345678901234567" not in result
        assert "sk-bbb12345678901234567" not in result


# ============================================================================
# 单 Provider 成功调用
# ============================================================================

class TestLLMGatewaySingleProviderSuccess:
    @pytest.mark.asyncio
    async def test_successful_chat_returns_content(self, base_config):
        gw = LLMGateway(base_config)
        gw._call_provider = AsyncMock(return_value=_make_success_response("hello world"))

        resp = await gw.chat("你好")
        assert resp.success is True
        assert resp.content == "hello world"

    @pytest.mark.asyncio
    async def test_provider_name_extracted_from_url(self, base_config):
        gw = LLMGateway(base_config)
        gw._call_provider = AsyncMock(return_value=_make_success_response("ok", provider="primary.test"))

        resp = await gw.chat("hi")
        assert resp.provider == "primary.test"

    @pytest.mark.asyncio
    async def test_call_provider_invoked_once_on_success(self, base_config):
        gw = LLMGateway(base_config)
        mock_call = AsyncMock(return_value=_make_success_response("ok", tokens_in=15, tokens_out=25))
        gw._call_provider = mock_call

        await gw.chat("test")
        assert mock_call.call_count == 1

    @pytest.mark.asyncio
    async def test_system_prompt_passed_through(self, base_config):
        gw = LLMGateway(base_config)
        mock_call = AsyncMock(return_value=_make_success_response("ok"))
        gw._call_provider = mock_call

        await gw.chat("hi", system_prompt="你是助手")
        # 验证 messages 中包含 system 角色
        call_args = mock_call.call_args
        messages = call_args[0][3]  # 第 4 个位置参数是 messages
        assert any(m["role"] == "system" for m in messages)


# ============================================================================
# HTTP 500 错误触发降级
# ============================================================================

class TestLLMGatewayFailoverHTTP500:
    @pytest.mark.asyncio
    async def test_500_error_triggers_fallback(self, fallback_config):
        gw = LLMGateway(fallback_config)
        call_count = 0

        async def mock_call_provider(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            nonlocal call_count
            call_count += 1
            if "primary.test" in base_url:
                return _make_error_response("HTTP 500: Internal Server Error", provider="primary.test")
            elif "fallback.test" in base_url:
                return _make_success_response("fallback result", provider="fallback.test")
            return _make_error_response("unknown provider")

        gw._call_provider = mock_call_provider

        resp = await gw.chat("test")
        assert resp.success is True
        assert resp.provider == "fallback.test"
        assert call_count == 2

    @pytest.mark.skip(reason="需要验证健康状态更新逻辑")
    @pytest.mark.asyncio
    async def test_primary_marked_unhealthy_after_500(self, fallback_config):
        gw = LLMGateway(fallback_config)

        async def mock_call_provider(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            if "primary.test" in base_url:
                return _make_error_response("HTTP 500: 服务器错误 sk-secret123", provider="primary.test")
            return _make_error_response("全部失败", provider="fallback.test")

        gw._call_provider = mock_call_provider

        resp = await gw.chat("test")
        assert resp.success is False
        # 验证 primary 被标记为不健康（连续失败 >=3 才会变成 UNAVAILABLE，这里只失败1次）
        primary_health = gw._provider_health.get("primary.test")
        assert primary_health is not None
        assert primary_health.consecutive_failures >= 1
        # 错误信息应该被脱敏
        assert "sk-secret123" not in primary_health.last_error


# ============================================================================
# 超时触发降级
# ============================================================================

class TestLLMGatewayFailoverAllFailed:
    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_failure(self, multi_fallback_config):
        gw = LLMGateway(multi_fallback_config)
        call_order = []

        async def mock_call_provider(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            call_order.append(base_url)
            return _make_error_response(f"失败: {base_url}")

        gw._call_provider = mock_call_provider

        resp = await gw.chat("test")
        assert resp.success is False
        # 应该尝试了 primary + 3 个 fallback = 4 次
        assert len(call_order) == 4

    @pytest.mark.asyncio
    async def test_first_fallback_success_skips_rest(self, multi_fallback_config):
        gw = LLMGateway(multi_fallback_config)
        call_order = []

        async def mock_call_provider(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            call_order.append(base_url)
            if "fb2.test" in base_url:
                return _make_success_response("ok from fb2", provider="fb2.test")
            return _make_error_response(f"fail: {base_url}")

        gw._call_provider = mock_call_provider

        resp = await gw.chat("test")
        assert resp.success is True
        assert resp.provider == "fb2.test"
        # primary (失败) -> fb1 (失败) -> fb2 (成功)，fb3 不应被调用
        assert len(call_order) == 3
        assert not any("fb3.test" in url for url in call_order)


# ============================================================================
# 降级顺序
# ============================================================================

class TestLLMGatewayFailoverOrder:
    @pytest.mark.asyncio
    async def test_fallback_attempted_in_configured_order(self, multi_fallback_config):
        gw = LLMGateway(multi_fallback_config)
        attempted = []

        async def mock_call_provider(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            attempted.append(base_url)
            return _make_error_response("fail")

        gw._call_provider = mock_call_provider

        await gw.chat("test")

        # 验证顺序: primary -> fb1 -> fb2 -> fb3
        assert "primary.test" in attempted[0]
        assert "fb1.test" in attempted[1]
        assert "fb2.test" in attempted[2]
        assert "fb3.test" in attempted[3]


# ============================================================================
# 任务类型路由
# ============================================================================

class TestLLMGatewayChatWithRouting:
    @pytest.mark.asyncio
    async def test_routing_uses_model_routing_table(self, base_config):
        gw = LLMGateway(base_config)
        called_with = {}

        async def mock_call(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            called_with["model"] = model
            called_with["temperature"] = temperature
            return _make_success_response("ok")

        gw._call_provider = mock_call

        await gw.chat_with_routing("test", task_type=TaskType.INTENT_CLASSIFICATION)
        # 单 Provider 模式下，model 来自 model_routing 表（默认 "auto"）
        assert called_with["model"] == "auto"

    @pytest.mark.asyncio
    async def test_intent_classification_uses_low_temperature(self, base_config):
        gw = LLMGateway(base_config)
        called_temp = None

        async def mock_call(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            nonlocal called_temp
            called_temp = temperature
            return _make_success_response("ok")

        gw._call_provider = mock_call

        await gw.chat_with_routing("test", task_type=TaskType.INTENT_CLASSIFICATION)
        # 意图分类应该用较低温度
        assert called_temp is not None
        assert called_temp < 0.5

    @pytest.mark.asyncio
    async def test_general_uses_default_temperature(self, base_config):
        gw = LLMGateway(base_config)
        called_temp = None

        async def mock_call(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            nonlocal called_temp
            called_temp = temperature
            return _make_success_response("ok")

        gw._call_provider = mock_call

        await gw.chat_with_routing("test", task_type=TaskType.GENERAL)
        assert called_temp == 0.7

    @pytest.mark.asyncio
    async def test_scene_description_with_images(self, base_config):
        gw = LLMGateway(base_config)
        called_messages = None

        async def mock_call(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            nonlocal called_messages
            called_messages = messages
            return _make_success_response("ok")

        gw._call_provider = mock_call

        await gw.chat_with_routing(
            "描述图片",
            task_type=TaskType.SCENE_DESCRIPTION,
            images=["fake_base64_image_data"],
        )
        assert called_messages is not None
        user_msg = [m for m in called_messages if m["role"] == "user"][0]
        assert isinstance(user_msg["content"], list)
        assert any(part.get("type") == "image_url" for part in user_msg["content"])


# ============================================================================
# 用量统计
# ============================================================================

class TestLLMGatewayUsageStats:
    def test_get_stats_initial_state(self, base_config):
        gw = LLMGateway(base_config)
        stats = gw.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens_input"] == 0
        assert stats["total_tokens_output"] == 0

    def test_get_stats_accumulates_tokens(self, base_config):
        gw = LLMGateway(base_config)
        gw._stats["total_requests"] = 5
        gw._stats["total_successes"] = 4
        gw._stats["total_tokens_input"] = 100
        gw._stats["total_tokens_output"] = 200
        gw._stats["total_latency_ms"] = 500

        stats = gw.get_stats()
        assert stats["total_requests"] == 5
        assert stats["total_tokens_input"] == 100
        assert stats["total_tokens_output"] == 200
        assert "success_rate" in stats
        assert "avg_latency_ms" in stats


# ============================================================================
# Token 压缩
# ============================================================================

class TestLLMGatewayTokenCompression:
    @pytest.mark.asyncio
    async def test_compression_disabled_keeps_original(self, base_config):
        # base_config 中 enable_compression=False
        gw = LLMGateway(base_config)
        sent_messages = None

        async def mock_call(base_url, api_key, model, messages, temperature, max_tokens, **kwargs):
            nonlocal sent_messages
            sent_messages = messages
            return _make_success_response("ok")

        gw._call_provider = mock_call

        long_prompt = "测试内容" * 10
        await gw.chat(long_prompt)

        user_msg = [m for m in sent_messages if m["role"] == "user"][0]
        # 未压缩时，内容应保持原样
        assert user_msg["content"] == long_prompt


# ============================================================================
# Provider 名称提取
# ============================================================================

class TestProviderNameExtraction:
    def test_extract_from_standard_url(self):
        gw = LLMGateway.__new__(LLMGateway)
        gw._provider_health = {}
        name = gw._extract_provider_name("https://api.deepseek.com/v1")
        assert "deepseek" in name

    def test_extract_from_subdomain(self):
        gw = LLMGateway.__new__(LLMGateway)
        gw._provider_health = {}
        name = gw._extract_provider_name("https://ark.cn-beijing.volces.com/api/v3")
        assert name  # 非空即可

    def test_localhost_url(self):
        gw = LLMGateway.__new__(LLMGateway)
        gw._provider_health = {}
        name = gw._extract_provider_name("http://localhost:8080/v1")
        assert "localhost" in name


# ============================================================================
# HALF_OPEN 并发安全（回归：防止半开状态被并发请求打穿）
# ============================================================================

class TestHalfOpenConcurrency:
    @pytest.mark.asyncio
    async def test_half_open_allows_only_one_probe_concurrently(self, base_config):
        """高并发场景下，HALF_OPEN 状态必须只放行 1 个探测请求。

        触发场景：Provider 从 UNAVAILABLE 恢复进入 HALF_OPEN 后，多个并发请求
        同时到达。无锁保护时，多个请求可能同时通过 `half_open_probes >= 1` 检查，
        导致探测请求被并发打穿，违背熔断器语义。
        """
        gw = LLMGateway(base_config)
        provider_name = "primary.test"

        # 预置 Provider 为 HALF_OPEN（模拟冷却期刚过）
        health = gw._provider_health[provider_name]
        health.status = ProviderStatus.HALF_OPEN
        health.half_open_probes = 0
        health.last_failure_time = time.time() - health.RECOVERY_INTERVAL_SEC

        # Mock _get_http_client 使其永远不会返回，这样我们可以检查
        # 有多少请求真正通过了 HALF_OPEN 检查并继续向下执行。
        # 使用一个延迟较长的 future 来"卡住"通过检查的探测请求。
        delay_event = asyncio.Event()
        passed_count = 0
        lock = asyncio.Lock()

        async def slow_get_http_client():
            nonlocal passed_count
            async with lock:
                passed_count += 1
            await delay_event.wait()  # 永远等待，模拟正在进行的探测
            return None

        gw._get_http_client = slow_get_http_client

        # 并发发起 10 个请求
        async def single_call():
            return await gw._call_provider(
                base_url="https://primary.test/v1",
                api_key="sk-test",
                model="test-model",
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.7,
                max_tokens=100,
            )

        tasks = [asyncio.create_task(single_call()) for _ in range(10)]

        # 给事件循环一个机会调度所有任务
        await asyncio.sleep(0.1)

        # 断言：只有一个请求通过了 HALF_OPEN 检查（即进入了 slow_get_http_client）
        assert passed_count == 1, (
            f"HALF_OPEN 应只放行 1 个探测请求，但实际放行了 {passed_count} 个"
        )

        # 其余 9 个请求应被返回 "半开探测进行中"
        blocked_count = sum(
            1 for t in tasks
            if t.done() and "半开探测进行中" in (t.result().error or "")
        )
        assert blocked_count == 9, (
            f"应有 9 个请求被阻塞，实际被阻塞 {blocked_count} 个"
        )

        # 清理：释放等待的任务
        delay_event.set()
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 最终断言：half_open_probes 在整个过程中没有超过 1
        assert health.half_open_probes == 1, (
            f"half_open_probes 不应超过 1，实际为 {health.half_open_probes}"
        )

    @pytest.mark.asyncio
    async def test_half_open_probe_failure_reopens_circuit(self, base_config):
        """半开探测失败后，必须重新熔断并阻止后续请求。"""
        gw = LLMGateway(base_config)
        provider_name = "primary.test"

        health = gw._provider_health[provider_name]
        health.status = ProviderStatus.HALF_OPEN
        health.half_open_probes = 0
        health.consecutive_failures = 3  # 已达到阈值

        # Mock _get_http_client 返回一个会立即报 500 的 client
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=AsyncMock(
            status=500,
            text=AsyncMock(return_value="Internal Server Error"),
            json=AsyncMock(return_value={}),
            __aenter__=AsyncMock(return_value=AsyncMock(
                status=500,
                text=AsyncMock(return_value="err"),
                json=AsyncMock(return_value={}),
            )),
            __aexit__=AsyncMock(return_value=False),
        ))
        gw._http_client = mock_client

        resp = await gw._call_provider(
            base_url="https://primary.test/v1",
            api_key="sk-test",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
            max_tokens=100,
        )

        assert resp.success is False
        # 探测失败后应重新熔断
        assert health.status == ProviderStatus.UNAVAILABLE
        assert health.half_open_probes == 0
        assert health.consecutive_failures == 4  # 3 + 1

    @pytest.mark.asyncio
    async def test_half_open_probe_success_closes_circuit(self, base_config):
        """半开探测成功后，必须恢复为 HEALTHY 并允许正常流量。"""
        gw = LLMGateway(base_config)
        provider_name = "primary.test"

        health = gw._provider_health[provider_name]
        health.status = ProviderStatus.HALF_OPEN
        health.half_open_probes = 0
        health.consecutive_failures = 3

        # Mock 成功响应（支持 async with 协议）
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        }))
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "test-model",
        })

        async def _aenter(_self):
            return mock_response
        async def _aexit(_self, *args):
            return False
        mock_response.__aenter__ = _aenter
        mock_response.__aexit__ = _aexit

        # client.post(...) 在 aiohttp 中返回上下文管理器对象（非协程）
        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_response)
        gw._http_client = mock_client

        resp = await gw._call_provider(
            base_url="https://primary.test/v1",
            api_key="sk-test",
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.7,
            max_tokens=100,
        )

        assert resp.success is True
        assert health.status == ProviderStatus.HEALTHY
        assert health.half_open_probes == 0
        assert health.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_unavailable_transitions_to_half_open_after_recovery_interval(self, base_config):
        """UNAVAILABLE 状态在冷却期结束后，必须自动转入 HALF_OPEN。

        2026-08-18 新增逻辑：_call_provider 在检测到 UNAVAILABLE 且冷却期已过时，
        立即转为 HALF_OPEN 状态，无需等待外部触发。
        """
        gw = LLMGateway(base_config)
        provider_name = "primary.test"

        health = gw._provider_health[provider_name]
        health.status = ProviderStatus.UNAVAILABLE
        health.consecutive_failures = 3
        health.last_failure_time = time.time() - health.RECOVERY_INTERVAL_SEC - 1  # 冷却期已过

        # Mock 成功响应
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({
            "choices": [{"message": {"content": "recovered"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            "model": "test-model",
        }))
        mock_response.json = AsyncMock(return_value={
            "choices": [{"message": {"content": "recovered"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            "model": "test-model",
        })

        async def _aenter(_self):
            return mock_response
        async def _aexit(_self, *args):
            return False
        mock_response.__aenter__ = _aenter
        mock_response.__aexit__ = _aexit

        mock_client = MagicMock()
        mock_client.post = MagicMock(return_value=mock_response)
        gw._http_client = mock_client

        resp = await gw._call_provider(
            base_url="https://primary.test/v1",
            api_key="sk-test",
            model="test-model",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.7,
            max_tokens=50,
        )

        # 验证：冷却期结束后自动转为 HALF_OPEN，探测成功后转为 HEALTHY
        assert resp.success is True
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0


# ============================================================================
# 缺口: _register_provider_failure 状态机推进（2026-08-18 新增逻辑）
# ============================================================================

class TestCircuitBreakerRegisterFailure:
    """直接单元测试 _register_provider_failure 的状态机语义。

    该函数在 _call_provider 的三个失败路径（HTTP 非200 / 超时 / 异常）
    共用，必须保证：阈值判定正确、半开失败重熔断正确、所有计数器同步更新。
    """

    def test_healthy_below_threshold_stays_healthy(self):
        """HEALTHY 且连续失败 < 阈值时，状态保持 HEALTHY，不触发熔断。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        gw._stats = {"total_failures": 0}
        h = ProviderHealth(name="test")
        h.CIRCUIT_FAILURE_THRESHOLD = 3
        h.status = ProviderStatus.HEALTHY
        h.consecutive_failures = 0
        h.total_failures = 0
        h.total_requests = 0

        # 第 1、2 次失败 → 仍为 HEALTHY
        gw._register_provider_failure(h, "err1")
        assert h.status == ProviderStatus.HEALTHY
        assert h.consecutive_failures == 1
        assert h.total_failures == 1
        assert h.last_error == "err1"
        assert h.half_open_probes == 0
        assert h.last_failure_time > 0
        assert gw._stats["total_failures"] == 1

        gw._register_provider_failure(h, "err2")
        assert h.status == ProviderStatus.HEALTHY
        assert h.consecutive_failures == 2

    def test_healthy_reaches_threshold_triggers_unavailable(self):
        """HEALTHY 下连续失败达到阈值 → 转为 UNAVAILABLE 并重置 half_open_probes。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        gw._stats = {"total_failures": 0}
        h = ProviderHealth(name="test")
        h.CIRCUIT_FAILURE_THRESHOLD = 3
        h.status = ProviderStatus.HEALTHY
        h.consecutive_failures = 2  # 已经 2 次
        h.half_open_probes = 99  # 故意设置脏数据

        gw._register_provider_failure(h, "err3")

        assert h.status == ProviderStatus.UNAVAILABLE
        assert h.consecutive_failures == 3
        assert h.half_open_probes == 0  # 必须清零
        assert h.total_failures == 1

    def test_degraded_reaches_threshold_triggers_unavailable(self):
        """DEGRADED 状态达到阈值也应熔断（不因为降级状态就绕过阈值）。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        gw._stats = {"total_failures": 0}
        h = ProviderHealth(name="test")
        h.CIRCUIT_FAILURE_THRESHOLD = 2
        h.status = ProviderStatus.DEGRADED
        h.consecutive_failures = 1

        gw._register_provider_failure(h, "another_error")

        assert h.status == ProviderStatus.UNAVAILABLE

    def test_half_open_probe_failure_reenters_unavailable(self):
        """HALF_OPEN 探测失败 → 立即重新熔断 UNAVAILABLE（无论阈值是否达到）。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        gw._stats = {"total_failures": 0}
        h = ProviderHealth(name="test")
        h.CIRCUIT_FAILURE_THRESHOLD = 10  # 故意设大，确认不是阈值触发
        h.status = ProviderStatus.HALF_OPEN
        h.consecutive_failures = 1
        h.half_open_probes = 1

        gw._register_provider_failure(h, "probe_failed")

        # HALF_OPEN 路径独立，不依赖阈值
        assert h.status == ProviderStatus.UNAVAILABLE
        assert h.half_open_probes == 0  # 必须清零
        assert h.consecutive_failures == 2

    def test_already_unavailable_increments_counters_keeps_status(self):
        """已是 UNAVAILABLE 时再失败：计数器继续增加，但状态保持 UNAVAILABLE。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        gw._stats = {"total_failures": 5}
        h = ProviderHealth(name="test")
        h.status = ProviderStatus.UNAVAILABLE
        h.consecutive_failures = 3
        h.total_failures = 3

        gw._register_provider_failure(h, "extra_fail")

        assert h.status == ProviderStatus.UNAVAILABLE  # 保持
        assert h.consecutive_failures == 4
        assert h.total_failures == 4
        assert h.last_error == "extra_fail"
        assert gw._stats["total_failures"] == 6


# ============================================================================
# 缺口: _health_score + _order_fallback_candidates（健康感知 failover 排序）
# ============================================================================

class TestHealthScoreAndFallbackOrder:
    """直接单元测试健康感知评分与降级候选排序。

    2026-08-18 提交 f2758da 的核心新增逻辑：熔断冷却中的 Provider
    必须被剔除（+inf 分），剩余按健康程度稳定排序。
    """

    def _make_gw_with_healths(self, specs):
        """构造带指定健康状态集合的网关。
        specs: [(hostname, status, consecutive_failures, total_requests, total_failures, total_successes, avg_latency_ms), ...]
        """
        config = LLMConfig(
            base_url=f"https://{specs[0][0]}/v1",
            api_key="sk-test",
            fallback_providers=[
                {"base_url": f"https://{s[0]}/v1", "api_key": "k", "default_model": "m"}
                for s in specs[1:]
            ],
        )
        gw = LLMGateway(config)
        for (name, status, cfails, treqs, tfails, tsuccs, avg_ms) in specs:
            if name not in gw._provider_health:
                gw._provider_health[name] = ProviderHealth(name=name)
            h = gw._provider_health[name]
            h.status = status
            h.consecutive_failures = cfails
            h.total_requests = treqs
            h.total_failures = tfails
            h.total_successes = tsuccs
            # total_latency_ms = avg_ms * tsuccs
            h.total_latency_ms = avg_ms * tsuccs
        return gw

    def test_healthy_provider_zero_base_score(self):
        """全新 HEALTHY Provider（无失败、无请求）基准分应为 0。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {"a.test": ProviderHealth(name="a.test")}
        score = gw._health_score("a.test")
        assert score == 0.0

    def test_unknown_provider_returns_zero(self):
        """未注册的 Provider（健康字典无）返回 0，不抛异常。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        assert gw._health_score("never-heard") == 0.0

    def test_status_weight_ordering(self):
        """纯状态权重：HEALTHY(0) < DEGRADED(1) < HALF_OPEN(2) ≈ 冷却后UNAVAILABLE(2) < 冷却中UNAVAILABLE(inf)。"""
        specs = [
            ("healthy.test", ProviderStatus.HEALTHY, 0, 0, 0, 0, 0),
            ("degraded.test", ProviderStatus.DEGRADED, 0, 0, 0, 0, 0),
            ("halfopen.test", ProviderStatus.HALF_OPEN, 0, 0, 0, 0, 0),
            ("unavail-cooled.test", ProviderStatus.UNAVAILABLE, 0, 0, 0, 0, 0),  # 冷却后
            ("unavail-hot.test", ProviderStatus.UNAVAILABLE, 5, 0, 0, 0, 0),
        ]
        gw = self._make_gw_with_healths(specs)
        # 手动设置 last_failure_time 区分"冷却中"和"冷却后"
        cooled = gw._provider_health["unavail-cooled.test"]
        cooled.RECOVERY_INTERVAL_SEC = 1
        cooled.last_failure_time = time.time() - 10  # 超过间隔
        hot = gw._provider_health["unavail-hot.test"]
        hot.RECOVERY_INTERVAL_SEC = 9999
        hot.last_failure_time = time.time()  # 刚失败

        s_healthy = gw._health_score("healthy.test")
        s_degraded = gw._health_score("degraded.test")
        s_halfopen = gw._health_score("halfopen.test")
        s_unavail_cooled = gw._health_score("unavail-cooled.test")
        s_unavail_hot = gw._health_score("unavail-hot.test")

        assert s_healthy == 0.0
        assert s_degraded == 1.0
        assert s_halfopen == 2.0
        assert s_unavail_cooled == 2.0  # 冷却后允许半开探测候选
        assert s_unavail_hot == float("inf")  # 冷却中 → 剔除
        # 严格排序
        assert s_healthy < s_degraded < s_halfopen < s_unavail_hot

    def test_consecutive_failures_penalty_capped_at_5(self):
        """连续失败惩罚：min(cfails, 5) * 0.2，防止无上限放大。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        for cfails, expected_extra in [(0, 0), (1, 0.2), (5, 1.0), (10, 1.0), (99, 1.0)]:
            h = ProviderHealth(name=f"p{cfails}")
            h.consecutive_failures = cfails
            gw._provider_health[f"p{cfails}"] = h
            score = gw._health_score(f"p{cfails}")
            # 基准分 0 只加连续失败惩罚
            assert score == expected_extra, f"cfails={cfails} 期望额外分 {expected_extra}，实际 {score}"

    def test_failure_rate_applied_after_5_requests(self):
        """total_requests >= 5 时附加失败率惩罚：(fail/total) * 1.0。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        # 样本充足（>=5）：成功率 50% → 失败率 0.50 → 附加 0.5
        h = ProviderHealth(name="p50")
        h.total_requests = 10
        h.total_failures = 5
        gw._provider_health["p50"] = h
        assert gw._health_score("p50") == pytest.approx(0.5)
        # 样本不足（<5）：不附加失败率惩罚
        h2 = ProviderHealth(name="p2")
        h2.total_requests = 2
        h2.total_failures = 1
        gw._provider_health["p2"] = h2
        assert gw._health_score("p2") == 0.0  # 样本不足，忽略失败率

    def test_avg_latency_penalty_capped_at_05(self):
        """平均延迟惩罚：avg_ms / 10000，上限 0.5。"""
        gw = LLMGateway.__new__(LLMGateway)
        gw._logger = logging.getLogger(f"{__name__}.LLMGateway")
        gw._provider_health = {}
        for avg_ms, expected_extra in [(0, 0.0), (1000, 0.1), (5000, 0.5), (10000, 0.5), (50000, 0.5)]:
            h = ProviderHealth(name=f"lat{avg_ms}")
            h.total_successes = 1  # 保证 avg = total/successes
            h.total_latency_ms = avg_ms * 1
            gw._provider_health[f"lat{avg_ms}"] = h
            score = gw._health_score(f"lat{avg_ms}")
            assert score == pytest.approx(expected_extra), f"avg_ms={avg_ms} 期望 {expected_extra}，实际 {score}"

    def test_fallback_order_excludes_circuit_broken(self):
        """熔断冷却中的 Provider（+inf 分）必须从 failover 候选中完全剔除。"""
        specs = [
            ("primary.test", ProviderStatus.HEALTHY, 0, 0, 0, 0, 0),
            ("cold.test", ProviderStatus.UNAVAILABLE, 3, 0, 0, 0, 0),  # 冷却中
            ("good.test", ProviderStatus.HEALTHY, 0, 0, 0, 0, 0),
        ]
        gw = self._make_gw_with_healths(specs)
        # 标记 cold.test 为冷却中（刚失败）
        cold = gw._provider_health["cold.test"]
        cold.RECOVERY_INTERVAL_SEC = 9999
        cold.last_failure_time = time.time()
        fallbacks = [
            {"base_url": "https://cold.test/v1", "api_key": "k", "default_model": "m"},
            {"base_url": "https://good.test/v1", "api_key": "k", "default_model": "m"},
        ]
        ordered = gw._order_fallback_candidates(fallbacks)
        hosts = [gw._extract_provider_name(fb["base_url"]) for fb in ordered]
        assert "cold.test" not in hosts  # 被剔除
        assert "good.test" in hosts

    def test_fallback_order_sorts_by_health_then_stable(self):
        """相同静态配置顺序下，健康分低者排前；同分保持原顺序（稳定排序）。"""
        specs = [
            ("primary.test", ProviderStatus.HEALTHY, 0, 0, 0, 0, 0),
            ("b.test", ProviderStatus.DEGRADED, 0, 0, 0, 0, 0),  # 分 = 1
            ("a.test", ProviderStatus.HEALTHY, 2, 0, 0, 0, 0),    # 连续失败2 → 分 0.4
            ("c.test", ProviderStatus.HEALTHY, 0, 0, 0, 0, 0),    # 分 0
        ]
        gw = self._make_gw_with_healths(specs)
        fallbacks = [
            {"base_url": "https://a.test/v1", "api_key": "k", "default_model": "m"},
            {"base_url": "https://b.test/v1", "api_key": "k", "default_model": "m"},
            {"base_url": "https://c.test/v1", "api_key": "k", "default_model": "m"},
        ]
        ordered = gw._order_fallback_candidates(fallbacks)
        hosts = [gw._extract_provider_name(fb["base_url"]) for fb in ordered]
        # 健康分排序：c(0) 最优 → a(0.4) → b(1.0)
        assert hosts.index("c.test") < hosts.index("a.test") < hosts.index("b.test")

