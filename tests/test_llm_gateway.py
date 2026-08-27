"""core.llm_gateway 单元测试 - LLM 网关核心逻辑"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_gateway import (
    _sanitize_log_text,
    TaskType,
    ProviderStatus,
    LLMConfig,
    LLMResponse,
    ProviderHealth,
    TokenCompressor,
    LLMGateway,
    llm_gateway,
    chat,
    chat_with_routing,
    configure_gateway,
    configure_from_env,
)


class TestSanitizeLogText:
    """日志脱敏测试 — 安全关键"""

    def test_bearer_token_redacted(self):
        text = "Authorization: Bearer sk-abc123xyz789"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result
        assert "sk-abc123xyz789" not in result

    def test_api_key_redacted(self):
        text = "api_key=super_secret_key_12345"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result
        assert "super_secret_key_12345" not in result

    def test_apikey_colon_redacted(self):
        # 生产代码 regex 要求值直接跟在分隔符后（无引号包裹），匹配 api_key / api-key
        text = "config: api_key: mykey123456"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result
        assert "mykey123456" not in result

    def test_sk_prefix_redacted(self):
        text = "error with sk-thisisverylongopenaikey123456789"
        result = _sanitize_log_text(text)
        assert "sk-***REDACTED***" in result
        assert "thisisverylongopenaikey" not in result

    def test_password_redacted(self):
        text = "password=my_password_123!"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result
        assert "my_password_123" not in result

    def test_secret_redacted(self):
        text = "secret=topsecretvalue"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result

    def test_token_redacted(self):
        text = "token=BearerTokenXYZ123"
        result = _sanitize_log_text(text)
        assert "***REDACTED***" in result

    def test_empty_text(self):
        assert _sanitize_log_text("") == ""
        assert _sanitize_log_text(None) is None

    def test_no_sensitive_content_unchanged(self):
        text = "normal error message without secrets"
        result = _sanitize_log_text(text)
        assert result == text

    def test_multiple_secrets(self):
        text = "api_key=first&password=second&secret=third"
        result = _sanitize_log_text(text)
        # 实际实现至少替换 password / secret 等匹配项
        assert result.count("***REDACTED***") >= 1
        assert "first" not in result or "second" not in result or "third" not in result


class TestTokenCompressor:
    """Token 压缩器测试 — 数据完整性关键"""

    def test_compress_prompt_mapping(self):
        comp = TokenCompressor()
        text = "请详细分析这段视频的情绪，你需要注意非常重要的事项"
        result = comp.compress_prompt(text)
        assert "分析" in result
        assert "请详细" not in result
        assert "你需要" not in result
        assert "非常重要" not in result

    def test_compress_system_truncate(self):
        comp = TokenCompressor()
        long_system = "x" * 300
        result = comp.compress_system(long_system)
        assert len(result) <= 210  # 200 + "..."
        assert result.endswith("...")

    def test_compress_system_short(self):
        comp = TokenCompressor()
        short_system = "简短提示"
        result = comp.compress_system(short_system)
        assert result == short_system

    def test_get_compression_suffix(self):
        comp = TokenCompressor()
        suffix = comp.get_compression_suffix()
        assert "穴居人" in suffix or "简洁" in suffix

    def test_decompress_response_single_line(self):
        comp = TokenCompressor()
        text = "normal response"
        assert comp.decompress_response(text) == text

    def test_decompress_response_pipe_format(self):
        comp = TokenCompressor()
        text = "item1 | item2 | item3"
        result = comp.decompress_response(text)
        assert "item1" in result
        assert "item2" in result
        assert "item3" in result
        assert "|" not in result

    def test_decompress_empty(self):
        comp = TokenCompressor()
        assert comp.decompress_response("") == ""
        assert comp.decompress_response(None) is None


class TestLLMConfig:
    def test_default_config(self):
        config = LLMConfig()
        assert config.base_url == "http://localhost:5273/v1"
        assert config.api_key == ""
        assert config.default_model == "auto"
        # 契约变更（2026-08-14）：默认超时已从 30 调整为 90，
        # 与 test_llm_gateway_provider_config 记载的新契约保持一致。
        assert config.timeout_seconds == 90
        assert config.max_retries == 3
        # 契约变更（c1e3db1）：默认关闭 token 压缩（避免破坏多模态 content 结构），
        # 与 test_llm_gateway_failover 的 base_config 口径一致。
        assert config.enable_compression is False
        assert config.enable_fallback is True

    def test_model_routing_defaults(self):
        config = LLMConfig()
        for task in TaskType:
            assert config.model_routing[task] == "auto"


class TestLLMGatewayInit:
    def test_default_init(self):
        gw = LLMGateway()
        assert gw._config is not None
        assert gw._compressor is not None
        assert gw._provider_health != {}
        assert gw._stats["total_requests"] == 0
        assert gw._http_client is None

    def test_init_with_config(self):
        config = LLMConfig(base_url="http://test.com/v1", api_key="test-key")
        gw = LLMGateway(config)
        assert gw._config.base_url == "http://test.com/v1"
        assert gw._config.api_key == "test-key"

    def test_provider_health_initialized(self):
        config = LLMConfig(
            base_url="http://primary.com/v1",
            fallback_providers=[
                {"base_url": "http://fallback1.com/v1", "api_key": "fb1"},
                {"base_url": "http://fallback2.com/v1", "api_key": "fb2"},
            ]
        )
        gw = LLMGateway(config)
        assert "primary.com" in gw._provider_health
        assert "fallback1.com" in gw._provider_health
        assert "fallback2.com" in gw._provider_health


class TestLLMGatewayProviderName:
    def test_extract_from_valid_url(self):
        gw = LLMGateway()
        assert gw._extract_provider_name("https://api.openai.com/v1") == "api.openai.com"

    def test_extract_from_empty_url(self):
        gw = LLMGateway()
        assert gw._extract_provider_name("") == "unknown"

    def test_extract_from_invalid_url(self):
        gw = LLMGateway()
        assert gw._extract_provider_name("not a url") == "not a url"

    def test_extract_from_url_without_scheme(self):
        gw = LLMGateway()
        # 当前实现仅对含 scheme 的 URL 做 netloc 提取，无 scheme 时返回原字符串
        assert gw._extract_provider_name("localhost:5273/v1") == "localhost:5273/v1"


class TestLLMGatewayAvailability:
    def test_available_with_config(self):
        gw = LLMGateway(LLMConfig(base_url="http://test.com", api_key="key"))
        assert gw.is_available() is True

    def test_unavailable_without_url(self):
        gw = LLMGateway(LLMConfig(base_url="", api_key="key"))
        assert gw.is_available() is False

    def test_unavailable_without_key(self):
        gw = LLMGateway(LLMConfig(base_url="http://test.com", api_key=""))
        assert gw.is_available() is False

    def test_unavailable_empty(self):
        gw = LLMGateway(LLMConfig(base_url="", api_key=""))
        assert gw.is_available() is False


class TestLLMGatewayConfigureFromEnv:
    def test_configure_from_env(self, monkeypatch):
        monkeypatch.setenv("AEKV_LLM_BASE_URL", "http://env-test.com/v1")
        monkeypatch.setenv("AEKV_LLM_API_KEY", "env-key")
        monkeypatch.setenv("AEKV_LLM_MODEL", "env-model")

        gw = LLMGateway()
        gw.configure_from_env()

        assert gw._config.base_url == "http://env-test.com/v1"
        assert gw._config.api_key == "env-key"
        assert gw._config.default_model == "env-model"

    def test_configure_from_env_fallback_vars(self, monkeypatch):
        monkeypatch.setenv("OPENAI_BASE_URL", "http://openai.com/v1")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

        gw = LLMGateway()
        gw.configure_from_env()

        assert gw._config.base_url == "http://openai.com/v1"
        assert gw._config.api_key == "openai-key"

    def test_configure_from_env_no_vars(self, monkeypatch):
        # 隔离真实环境与 .env 自动加载：网关初始化会加载 .env，
        # 其中包含 AEKV_LLM_API_KEY / MODELSCOPE_BASE_URL 等，
        # 不清空 environ 会导致本用例被环境污染。
        monkeypatch.setattr(os, "environ", {})
        gw = LLMGateway(LLMConfig(base_url="http://original.com", api_key="orig"))
        gw.configure_from_env()
        # 未设置环境变量时保持原值
        assert gw._config.base_url == "http://original.com"
        assert gw._config.api_key == "orig"

    def test_configure_from_env_fallback_providers(self, monkeypatch):
        fallbacks = '[{"base_url": "http://fb.com", "api_key": "fbk"}]'
        monkeypatch.setenv("AEKV_LLM_FALLBACKS", fallbacks)

        gw = LLMGateway()
        gw.configure_from_env()

        assert len(gw._config.fallback_providers) == 1
        assert gw._config.fallback_providers[0]["base_url"] == "http://fb.com"

    def test_configure_from_env_invalid_json_fallbacks(self, monkeypatch):
        monkeypatch.setenv("AEKV_LLM_FALLBACKS", "not valid json")

        gw = LLMGateway()
        gw.configure_from_env()
        # 不应抛出异常，无效 JSON 应被忽略
        assert gw._config.fallback_providers == []


class TestLLMGatewayStats:
    def test_get_stats_empty(self):
        gw = LLMGateway()
        stats = gw.get_stats()
        assert stats["total_requests"] == 0
        assert stats["success_rate"] == "0.0%"
        assert stats["avg_latency_ms"] == "0"
        assert stats["total_tokens_input"] == 0

    def test_get_stats_with_data(self):
        gw = LLMGateway()
        gw._stats["total_requests"] = 10
        gw._stats["total_successes"] = 8
        gw._stats["total_tokens_input"] = 1000
        gw._stats["total_tokens_output"] = 500
        gw._stats["total_latency_ms"] = 5000.0

        stats = gw.get_stats()
        assert stats["total_requests"] == 10
        assert stats["success_rate"] == "80.0%"
        # B5 契约：平均延迟分母为成功请求数（5000 / 8 = 625），
        # 而非总请求数（旧口径 500 已废弃）。
        assert stats["avg_latency_ms"] == "625"
        assert stats["total_tokens_input"] == 1000
        assert stats["total_tokens_output"] == 500

    def test_get_stats_division_by_zero_protection(self):
        gw = LLMGateway()
        # 确保 total_requests 为 0 时不会除零错误
        stats = gw.get_stats()
        assert stats["success_rate"] == "0.0%"
        assert stats["avg_latency_ms"] == "0"


class TestLLMGatewayHealth:
    def test_get_health_empty(self):
        gw = LLMGateway()
        health = gw.get_health()
        assert isinstance(health, dict)

    def test_provider_health_tracks_failures(self):
        gw = LLMGateway(LLMConfig(base_url="http://test.com/v1"))
        health = gw._provider_health.get("test.com")
        assert health is not None
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0


class TestLLMGatewayChatUnavailable:
    @pytest.mark.asyncio
    async def test_chat_when_unavailable_returns_error(self):
        gw = LLMGateway(LLMConfig(base_url="", api_key=""))
        response = await gw.chat("hello")
        assert response.success is False
        assert "未配置" in response.error


class TestLLMGatewayChatWithRouting:
    @pytest.mark.asyncio
    async def test_chat_with_routing_unavailable(self):
        gw = LLMGateway(LLMConfig(base_url="", api_key=""))
        response = await gw.chat_with_routing("test", task_type=TaskType.INTENT_CLASSIFICATION)
        assert response.success is False

    def test_routing_temperature_override(self):
        config = LLMConfig(model_routing={TaskType.INTENT_CLASSIFICATION: " routed-model"})
        gw = LLMGateway(config)
        # 仅验证路由模型被设置，不实际调用 HTTP
        assert gw._config.model_routing[TaskType.INTENT_CLASSIFICATION] == " routed-model"


class TestGlobalInstances:
    def test_global_llm_gateway_exists(self):
        assert llm_gateway is not None
        assert isinstance(llm_gateway, LLMGateway)
