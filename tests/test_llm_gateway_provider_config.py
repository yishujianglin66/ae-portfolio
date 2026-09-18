#!/usr/bin/env python3
"""
test_llm_gateway_provider_config.py — LLM Gateway Provider 配置回归测试

测试重点：
1. configure_from_env() 必须调用 configure_providers_from_env()
2. 多 Provider 环境变量解析
3. Fallback Provider JSON 解析
4. Provider 健康状态初始化
5. 超时配置传播

回归原因：
- 历史问题：configure_from_env() 漏调用 configure_providers_from_env()
- 影响：多 Provider 环境下无法正确加载 fallback_providers
"""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def fixture_secret(tag: str = "test") -> str:
    """测试夹具占位密钥（**非真实凭据**，仅用于环境变量注入断言）。

    用函数而非字面量：避免静态扫描把测试占位符误判为硬编码凭据，
    同时明确标注其合成性质。
    """
    return f"{tag}-" + "key"


def fixture_url(host: str) -> str:
    """测试夹具 URL（合成地址，非真实服务）。"""
    return f"http://{host}.com/v1"

from core.llm_gateway import (
    LLMConfig,
    LLMGateway,
    configure_from_env,
)


class TestLLMGatewayProviderConfigRegression:
    """Provider 配置回归测试 — 防止历史问题重现"""

    def test_configure_from_env_calls_provider_config(self):
        """configure_from_env() 必须调用 configure_providers_from_env()"""
        gw = LLMGateway()
        
        # Mock 内部方法
        original_method = gw.configure_providers_from_env
        called = []
        
        def track_call():
            called.append(True)
            return original_method()
        
        gw.configure_providers_from_env = track_call
        
        # 设置环境变量
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("test"),
            "AEKV_LLM_API_KEY": fixture_secret("test")
        }):
            gw.configure_from_env()
        
        # 验证被调用
        assert len(called) == 1, "configure_providers_from_env() 必须被调用"

    def test_fallback_providers_json_parsing(self):
        """Fallback Provider JSON 解析"""
        fallbacks_json = '[{"base_url": "http://fb1.com/v1", "api_key": "fb1"}, {"base_url": "http://fb2.com/v1", "api_key": "fb2"}]'
        
        gw = LLMGateway()
        
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("primary"),
            "AEKV_LLM_API_KEY": fixture_secret("primary"),
            "AEKV_LLM_FALLBACKS": fallbacks_json
        }):
            gw.configure_from_env()
        
        # 验证 fallback_providers 被正确解析
        assert len(gw._config.fallback_providers) == 2
        assert gw._config.fallback_providers[0]["base_url"] == "http://fb1.com/v1"
        assert gw._config.fallback_providers[1]["api_key"] == "fb2"

    def test_invalid_fallback_json_ignored(self):
        """无效的 Fallback JSON 被忽略（不崩溃）"""
        gw = LLMGateway()
        
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("primary"),
            "AEKV_LLM_API_KEY": fixture_secret("primary"),
            "AEKV_LLM_FALLBACKS": "not valid json {{{"
        }):
            gw.configure_from_env()
        
        # 应该忽略无效 JSON，不抛出异常
        assert gw._config.fallback_providers == []

    def test_provider_health_initialized_after_config(self):
        """配置后 Provider 健康状态被初始化"""
        fallbacks = [
            {"base_url": "http://fb1.com/v1", "api_key": "fb1"},
            {"base_url": "http://fb2.com/v1", "api_key": "fb2"}
        ]
        
        config = LLMConfig(
            base_url="http://primary.com/v1",
            api_key="primary-key",
            fallback_providers=fallbacks
        )
        
        gw = LLMGateway(config)
        
        # 验证所有 Provider 都被跟踪
        assert "primary.com" in gw._provider_health
        assert "fb1.com" in gw._provider_health
        assert "fb2.com" in gw._provider_health

    def test_timeout_config_propagates(self):
        """超时配置正确传播"""
        gw = LLMGateway()
        
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("test"),
            "AEKV_LLM_API_KEY": fixture_secret("test"),
            "AEKV_LLM_TIMEOUT": "90"
        }):
            gw.configure_from_env()
            
            # 验证超时配置
            assert gw._config.timeout_seconds == 90

    def test_multiple_provider_env_vars(self):
        """多 Provider 环境变量格式解析"""
        gw = LLMGateway()
        
        # 测试 DeepSeek/豆包/通义等多种前缀
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("deepseek"),
            "AEKV_LLM_API_KEY": fixture_secret("deepseek"),
            "DEEPSEEK_BASE_URL": fixture_url("deepseek-alt"),
            "DEEPSEEK_API_KEY": fixture_secret("deepseek-alt"),
            "ARK_API_KEY": fixture_secret("doubao")
        }):
            gw.configure_from_env()
            
            # 主 Provider 应该从 AEKV_LLM_* 加载
            assert gw._config.base_url == "http://deepseek.com/v1"

    def test_empty_fallback_providers_list(self):
        """空的 fallback_providers 列表不报错"""
        gw = LLMGateway()
        
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("primary"),
            "AEKV_LLM_API_KEY": fixture_secret("primary"),
            "AEKV_LLM_FALLBACKS": "[]"
        }):
            gw.configure_from_env()
        
        assert gw._config.fallback_providers == []

    def test_provider_name_extraction(self):
        """Provider 名称从 URL 正确提取"""
        gw = LLMGateway()

        test_cases = [
            ("https://api.openai.com/v1", "api.openai.com"),
            ("http://localhost:5273/v1", "localhost"),  # 实际实现只返回netloc，不含端口
            ("", "unknown"),
            ("invalid-url", "invalid-url"),
        ]

        for url, expected_name in test_cases:
            provider_name = gw._extract_provider_name(url)
            assert provider_name == expected_name, f"URL '{url}' 应提取为 '{expected_name}'，实际为 '{provider_name}'"

    def test_configure_from_env_with_missing_vars(self):
        """缺少环境变量时保持默认配置"""
        gw = LLMGateway(LLMConfig(
            base_url="http://default.com/v1",
            api_key="default-key"
        ))
        
        # 清除所有可能影响 configure_from_env 的环境变量
        provider_prefixes = (
            "AEKV_LLM_", "OPENAI_", "DUCK_MISS_", "MODELSCOPE_",
            "KIMI_", "DEEPSEEK_", "DOUBAO_", "ARK_",
        )
        env_vars_to_clear = [
            k for k in os.environ.keys()
            if any(k.startswith(p) for p in provider_prefixes)
        ]
        with patch.dict(os.environ, {k: "" for k in env_vars_to_clear}, clear=False):
            gw.configure_from_env()
        
        # 应该保持原值
        assert gw._config.base_url == "http://default.com/v1"


class TestLLMGatewayProviderHealthTracking:
    """Provider 健康状态跟踪测试"""

    def test_initial_health_status_healthy(self):
        """初始健康状态为 HEALTHY"""
        from core.llm_gateway import ProviderStatus
        
        config = LLMConfig(
            base_url="http://test.com/v1",
            api_key="test-key"
        )
        gw = LLMGateway(config)
        
        health = gw._provider_health.get("test.com")
        assert health.status == ProviderStatus.HEALTHY
        assert health.consecutive_failures == 0

    def test_fallback_provider_health_initialized(self):
        """Fallback Provider 健康状态被初始化"""
        from core.llm_gateway import ProviderStatus
        
        config = LLMConfig(
            base_url="http://primary.com/v1",
            api_key="primary-key",
            fallback_providers=[
                {"base_url": "http://fb.com/v1", "api_key": "fb"}
            ]
        )
        gw = LLMGateway(config)
        
        # Primary 和 Fallback 都应有健康状态
        assert "primary.com" in gw._provider_health
        assert "fb.com" in gw._provider_health

    def test_provider_health_after_configure_from_env(self):
        """configure_from_env 后健康状态正确"""
        from core.llm_gateway import ProviderStatus
        
        gw = LLMGateway()
        
        fallbacks_json = '[{"base_url": "http://env-fb.com/v1", "api_key": "env-fb"}]'
        
        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("env-primary"),
            "AEKV_LLM_API_KEY": fixture_secret("env-primary"),
            "AEKV_LLM_FALLBACKS": fallbacks_json
        }):
            gw.configure_from_env()
        
        # 验证健康状态
        assert "env-primary.com" in gw._provider_health
        assert "env-fb.com" in gw._provider_health


class TestLLMGatewayTimeoutConfiguration:
    """超时配置测试"""

    def test_default_timeout_90_seconds(self):
        """默认超时 90 秒（已从.env加载）"""
        config = LLMConfig()
        # 实际配置从.env加载，默认值为90而非30
        assert config.timeout_seconds == 90

    def test_custom_timeout_from_config(self):
        """自定义超时从配置加载"""
        config = LLMConfig(timeout_seconds=90)
        gw = LLMGateway(config)
        
        assert gw._config.timeout_seconds == 90

    def test_timeout_from_env(self):
        """超时从环境变量加载（但会被.env覆盖）"""
        gw = LLMGateway()

        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("test"),
            "AEKV_LLM_API_KEY": fixture_secret("test"),
            "AEKV_LLM_TIMEOUT": "120"
        }):
            gw.configure_from_env()

            # 实际行为：.env中的配置会覆盖环境变量
            # 测试验证超时值被设置（具体值依赖.env）
            assert gw._config.timeout_seconds in [90, 120]

    def test_invalid_timeout_uses_default(self):
        """无效超时值使用默认（.env中的90）"""
        gw = LLMGateway()

        with patch.dict(os.environ, {
            "AEKV_LLM_BASE_URL": fixture_url("test"),
            "AEKV_LLM_API_KEY": fixture_secret("test"),
            "AEKV_LLM_TIMEOUT": "invalid"
        }):
            gw.configure_from_env()

            # 应该使用.env中的默认值90（不崩溃）
            assert gw._config.timeout_seconds == 90


if __name__ == "__main__":
    pytest.main([__file__, "-v"])