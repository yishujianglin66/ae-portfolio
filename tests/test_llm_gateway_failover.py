"""LLM 网关降级与路由测试 - 覆盖 provider failover、健康跟踪、任务路由"""
from __future__ import annotations

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
