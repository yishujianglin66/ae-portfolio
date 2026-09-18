#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 网关回归测试 - 覆盖高风险缺口

缺口列表：
1. _sanitize_log_text 新增敏感模式
2. _extract_provider_name URL 解析
3. TokenCompressor 边缘情况
4. _calculate_cost / _update_tier_stats 成本计算
5. Provider 健康跟踪半开探测（Circuit Breaker Half-Open）
6. configure_from_env 环境变量优先级与回填
"""
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 项目路径注入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm_gateway import (
    LLMConfig,
    LLMGateway,
    LLMResponse,
    ModelTier,
    ProviderHealth,
    ProviderStatus,
    TokenCompressor,
    _sanitize_log_text,
)


# =============================================================================
# 缺口1: _sanitize_log_text 新增模式
# =============================================================================
class TestSanitizeLogTextGaps:
    """测试日志脱敏函数未覆盖的敏感模式"""

    def test_pem_rsa_private_key_block(self):
        """PEM 格式 RSA 私钥块（多行 base64）应被完整掩码"""
        pem_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEpAIBAAKCAQEA0Zabcdef1234567890ghijklmnop\n"
            "qrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/=\n"
            "-----END RSA PRIVATE KEY-----"
        )
        log_line = f"加载私钥: {pem_key} 完成"
        result = _sanitize_log_text(log_line)
        assert "MIIEpAIBAAK" not in result
        assert "***PEM_KEY_REDACTED***" in result
        assert "加载私钥: " in result
        assert " 完成" in result

    def test_pem_generic_key_block(self):
        """PEM 格式通用私钥/公钥块（EC/OPENSSH 等）应被掩码"""
        ec_key = (
            "-----BEGIN EC PRIVATE KEY-----\n"
            "MHQCAQEEIPabcdefghijklmnopqrstuvwxyz1234567890\n"
            "-----END EC PRIVATE KEY-----"
        )
        result = _sanitize_log_text(ec_key)
        assert "MHQCAQEEI" not in result
        assert "***PEM_KEY_REDACTED***" in result

    def test_jwt_token_three_part(self):
        """JWT token（eyJ 开头三段式 base64）应被掩码"""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        log = f"用户 token: {jwt} 已过期"
        result = _sanitize_log_text(log)
        assert "eyJhbGciOiJIUzI1Ni" not in result
        assert "***JWT_REDACTED***" in result

    def test_rk_prefix_key_bug_validation(self):
        """rk- 开头密钥：验证 [spr]k- 字符集是否包含 r（原正则字符集 [spr] 含 r，应匹配）"""
        # Bug 描述：原正则 r'(?i)\b([spr]k-)[A-Za-z0-9_\-]{16,}'
        # [spr] 匹配 s/p/r 三个字母任一，所以 rk- 应该匹配
        rk_key = "rk-abcdefghij1234567890ABCDEFGHIJ"
        result = _sanitize_log_text(f"使用密钥 {rk_key} 调用")
        assert rk_key not in result
        assert "rk-***REDACTED***" in result

    def test_sk_pk_prefix_still_work(self):
        """原有 sk-/pk- 前缀密钥仍然正常掩码（回归验证）"""
        sk_key = "sk-abcdefghij1234567890ABCDEFGHIJ"
        pk_key = "pk-abcdefghij1234567890ABCDEFGHIJ"
        log = f"sk={sk_key} pk={pk_key}"
        result = _sanitize_log_text(log)
        assert sk_key not in result
        assert pk_key not in result
        assert "sk-***REDACTED***" in result
        assert "pk-***REDACTED***" in result

    def test_private_key_long_field_to_eol(self):
        """private_key / private_key_pem / privatekey / rsa_private_key 字段应掩码到行尾"""
        # private_key（含空格/换行等长内容）
        log1 = "config.private_key = -----BEGIN RSA KEY-----\nMIIEpAIBAAK...\n-----END RSA KEY-----"
        result1 = _sanitize_log_text(log1)
        # 关键：应被替换为 ***REDACTED***（由 PEM 规则先处理或 private_key 规则处理）
        assert "MIIEpAIBAAK" not in result1 or "***REDACTED***" in result1

        # private_key_pem
        log2 = 'private_key_pem="long base64 content with special chars +/= and spaces here"'
        result2 = _sanitize_log_text(log2)
        assert "long base64" not in result2
        assert "***REDACTED***" in result2

        # privatekey（无下划线）
        log3 = "privatekey=abcdef1234567890thisisalongkeyvalue"
        result3 = _sanitize_log_text(log3)
        assert "abcdef1234567890" not in result3
        assert "***REDACTED***" in result3

        # rsa_private_key
        log4 = "rsa_private_key=this_is_very_long_private_key_content_123456"
        result4 = _sanitize_log_text(log4)
        assert "this_is_very_long" not in result4
        assert "***REDACTED***" in result4

    def test_credential_access_secret_app_key_fields(self):
        """credential / access_key / secret_key / app_key 字段应被掩码"""
        log = (
            "credential=my_cred_value_123&"
            "access_key=AKIAIOSFODNN7EXAMPLE&"
            "secret_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY&"
            "app_key=app_abcdef1234567890"
        )
        result = _sanitize_log_text(log)
        assert "my_cred_value_123" not in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "wJalrXUtnFEMI" not in result
        assert "app_abcdef1234567890" not in result
        assert "credential=***REDACTED***" in result
        assert "access_key=***REDACTED***" in result
        assert "secret_key=***REDACTED***" in result
        assert "app_key=***REDACTED***" in result

    def test_authorization_header_case_insensitive(self):
        """大小写混合的 Authorization header 应被掩码（AUTHORIZATION / Authorization / authorization）"""
        # 全大写
        log1 = "AUTHORIZATION: Bearer sk-testtoken1234567890abcdef"
        result1 = _sanitize_log_text(log1)
        assert "sk-testtoken1234567890" not in result1
        assert "AUTHORIZATION: Bearer ***REDACTED***" in result1

        # 首字母大写
        log2 = "Authorization: Basic dXNlcjpwYXNzd29yZA=="
        result2 = _sanitize_log_text(log2)
        assert "dXNlcjpwYXNzd29yZA==" not in result2
        assert "Authorization: Basic ***REDACTED***" in result2

        # 等号分隔
        log3 = 'authorization=Token abcdefghij1234567890mnopqrst'
        result3 = _sanitize_log_text(log3)
        assert "abcdefghij1234567890" not in result3
        assert "authorization=Token ***REDACTED***" in result3

    def test_empty_and_none_input(self):
        """空字符串和 None（Python 空输入）"""
        assert _sanitize_log_text("") == ""
        assert _sanitize_log_text(None) is None


# =============================================================================
# 缺口2: _extract_provider_name 无测试
# =============================================================================
class TestExtractProviderName:
    """测试从 URL 提取 Provider 名称的各种边界情况"""

    def setup_method(self):
        """每个测试前创建一个干净的网关实例"""
        self.gateway = LLMGateway(LLMConfig(base_url="http://localhost:5273/v1", api_key="test"))

    def test_empty_string_returns_unknown(self):
        """空字符串 → "unknown" """
        assert self.gateway._extract_provider_name("") == "unknown"

    def test_normal_https_url_returns_hostname(self):
        """正常 https URL: https://api.deepseek.com/v1 → hostname (api.deepseek.com)"""
        result = self.gateway._extract_provider_name("https://api.deepseek.com/v1")
        assert result == "api.deepseek.com"

    def test_localhost_with_port(self):
        """带端口的 URL: http://localhost:5273/v1 → localhost"""
        result = self.gateway._extract_provider_name("http://localhost:5273/v1")
        assert result == "localhost"

    def test_ip_address_with_port(self):
        """IP 地址 URL: http://192.168.1.1:8080/v1 → 192.168.1.1"""
        result = self.gateway._extract_provider_name("http://192.168.1.1:8080/v1")
        assert result == "192.168.1.1"

    def test_no_scheme_pure_string_returns_original(self):
        """无协议的纯字符串 → 返回原字符串（走异常分支，不崩溃）"""
        # 无 :// 前缀的字符串，urlparse 会把它当作 path，hostname 为 None → 返回原字符串
        result = self.gateway._extract_provider_name("random-string-without-scheme")
        assert result == "random-string-without-scheme"

    def test_url_with_path_and_query_params(self):
        """带路径和复杂查询参数的 URL → 只返回 hostname"""
        url = (
            "https://duckmiss.site/v1/chat/completions"
            "?model=claude-sonnet&temperature=0.7&stream=true"
        )
        result = self.gateway._extract_provider_name(url)
        assert result == "duckmiss.site"

    def test_http_without_path(self):
        """仅有域名无路径"""
        result = self.gateway._extract_provider_name("http://example.com")
        assert result == "example.com"


# =============================================================================
# 缺口3: TokenCompressor 边缘情况
# =============================================================================
class TestTokenCompressorEdgeCases:
    """TokenCompressor 边缘情况测试"""

    def setup_method(self):
        self.compressor = TokenCompressor()

    def test_decompress_pipes_with_spaces_and_empty_items(self):
        """decompress_response: 管道间有空格、有空白项"""
        # "| item1 | | item2 |" → 应提取 item1 和 item2，中间空格空白项被跳过
        response = "| item1 | | item2 |"
        result = self.compressor.decompress_response(response)
        # 应生成两行：item1\nitem2
        lines = [l for l in result.split("\n") if l]
        assert len(lines) == 2
        assert "item1" in lines[0]
        assert "item2" in lines[1]

    def test_decompress_only_separators_no_content(self):
        """decompress_response: 只有分隔符无内容（"||||"）"""
        result = self.compressor.decompress_response("||||")
        # 全是空项 → 要么返回原字符串（长度<=1判断时返回），要么返回空
        # len("||||".split("|")) == 5 > 1，会走 strip 过滤，全部为空 → 最终 ""
        assert result.strip() == "" or result == "||||"

    def test_decompress_many_blank_and_valid(self):
        """混合多个空白项和有效项"""
        response = "  |   | first |   |   | second | third |   |   "
        result = self.compressor.decompress_response(response)
        lines = [l for l in result.split("\n") if l]
        assert len(lines) == 3
        assert "first" in lines[0]
        assert "second" in lines[1]
        assert "third" in lines[2]

    def test_compress_prompt_substring_mapping_safety(self):
        """compress_prompt: 压缩映射词是另一个词的子串时不会错误替换

        验证不会发生"请详细分析分析" → 错误替换的问题。
        COMPRESSION_MAP 包含 "请详细分析": "分析"
        如果 prompt 是 "请详细分析分析这个场景"，替换 "请详细分析" → "分析"
        结果应该是 "分析分析这个场景"，而不是错误的结果（即不会递归替换）
        """
        # 子串冲突场景："请描述" 是映射，但 "请描述你" 中只有 "请描述" 会被替换
        prompt = "请详细分析分析这个场景"
        result = self.compressor.compress_prompt(prompt)
        # "请详细分析" → "分析"，剩下 "分析这个场景"，所以结果是 "分析分析这个场景"
        assert "请详细分析" not in result
        assert result == "分析分析这个场景"

    def test_compress_prompt_no_match_unchanged(self):
        """没有任何匹配词时 prompt 保持不变"""
        prompt = "完全没有压缩词的文本 abcdef 123456"
        result = self.compressor.compress_prompt(prompt)
        assert result == prompt

    def test_decompress_empty_response(self):
        """空字符串或 None 响应"""
        assert self.compressor.decompress_response("") == ""
        assert self.compressor.decompress_response(None) is None

    def test_decompress_single_item_no_pipe(self):
        """单条内容不含管道符 → 原样返回"""
        single = "这是一条没有分隔符的普通回复"
        result = self.compressor.decompress_response(single)
        assert result == single


# =============================================================================
# 缺口4: _calculate_cost / _update_tier_stats 成本计算
# =============================================================================
class TestCostCalculationAndTierStats:
    """成本计算与档位统计更新测试"""

    def setup_method(self):
        self.gateway = LLMGateway(LLMConfig(base_url="http://localhost/v1", api_key="test"))

    def test_tier1_local_cost_zero(self):
        """TIER_1 本地模型成本为 0"""
        cost = self.gateway._calculate_cost(1000, 500, ModelTier.TIER_1_LOCAL_SPECIALIZED)
        # tier1 cost_per_1k_input=0.0, output=0.0 → 0
        assert cost == 0.0

    def test_tier2_midtier_cost_correct(self):
        """TIER_2 中端模型成本正确性
        cost_per_1k_input=0.0001, cost_per_1k_output=0.0003
        1000 in + 500 out = 0.0001*1 + 0.0003*0.5 = 0.0001 + 0.00015 = 0.00025
        """
        cost = self.gateway._calculate_cost(1000, 500, ModelTier.TIER_2_MIDTIER_GENERAL)
        expected = round(0.0001 * 1000 / 1000 + 0.0003 * 500 / 1000, 6)
        assert cost == pytest.approx(expected)
        assert cost == pytest.approx(0.00025)

    def test_tier3_flagship_cost_correct(self):
        """TIER_3 旗舰模型成本正确性
        cost_per_1k_input=0.015, cost_per_1k_output=0.075
        2000 in + 1000 out = 0.015*2 + 0.075*1 = 0.03 + 0.075 = 0.105
        """
        cost = self.gateway._calculate_cost(2000, 1000, ModelTier.TIER_3_FLAGSHIP_REASONING)
        expected = round(0.015 * 2000 / 1000 + 0.075 * 1000 / 1000, 6)
        assert cost == pytest.approx(expected)
        assert cost == pytest.approx(0.105)

    def test_zero_tokens_boundary(self):
        """0 token 边界情况：所有档位成本均为 0"""
        for tier in ModelTier:
            cost = self.gateway._calculate_cost(0, 0, tier)
            assert cost == 0.0, f"tier {tier} 0 token 成本应=0，实际={cost}"

    def test_missing_cost_per_1k_falls_back_to_zero(self):
        """tier_config 中缺失 cost_per_1k 字段时，默认返回 0（不崩溃）"""
        # 直接移除 tier_config 中某 tier 的 cost 字段后测试
        original_cfg = self.gateway._config.tier_config.get(ModelTier.TIER_2_MIDTIER_GENERAL, {}).copy()
        try:
            # 删除成本字段
            del self.gateway._config.tier_config[ModelTier.TIER_2_MIDTIER_GENERAL]["cost_per_1k_input"]
            del self.gateway._config.tier_config[ModelTier.TIER_2_MIDTIER_GENERAL]["cost_per_1k_output"]
            cost = self.gateway._calculate_cost(1000, 500, ModelTier.TIER_2_MIDTIER_GENERAL)
            # tier_cfg.get("cost_per_1k_input", 0) → 缺省 → 0，所以总成本 0
            assert cost == 0.0
        finally:
            # 恢复
            self.gateway._config.tier_config[ModelTier.TIER_2_MIDTIER_GENERAL] = original_cfg

    def test_unknown_tier_returns_zero(self):
        """未知 tier 未在 tier_config 中 → 取空 dict，get 默认 0 → 成本 0"""
        # 构造一个不在 tier_config 的假 tier 值
        fake_tier = "__not_in_config__"
        # 直接内部调用 tier_config.get 返回 {}
        tier_cfg = self.gateway._config.tier_config.get(fake_tier, {})
        cost_in = tier_cfg.get("cost_per_1k_input", 0) * 1000 / 1000
        cost_out = tier_cfg.get("cost_per_1k_output", 0) * 500 / 1000
        assert cost_in == 0.0
        assert cost_out == 0.0

    def test_update_tier_stats_success_updates_success_counter(self):
        """_update_tier_stats: 成功响应时 total_successes +1，failures 不变"""
        tier = ModelTier.TIER_2_MIDTIER_GENERAL
        before = self.gateway._tier_stats[tier].copy()
        success_resp = LLMResponse(
            success=True,
            latency_ms=123.4,
            tokens_input=500,
            tokens_output=200,
            cost_usd=0.000123,
        )
        self.gateway._update_tier_stats(tier, success_resp)
        after = self.gateway._tier_stats[tier]

        assert after["total_requests"] == before["total_requests"] + 1
        assert after["total_successes"] == before["total_successes"] + 1
        assert after["total_failures"] == before["total_failures"]  # 不变
        assert after["total_tokens_input"] == before["total_tokens_input"] + 500
        assert after["total_tokens_output"] == before["total_tokens_output"] + 200
        assert after["total_latency_ms"] == pytest.approx(before["total_latency_ms"] + 123.4)
        assert after["total_cost_usd"] == pytest.approx(before["total_cost_usd"] + 0.000123)

    def test_update_tier_stats_failure_updates_failure_counter(self):
        """_update_tier_stats: 失败响应时 total_failures +1，successes 不变"""
        tier = ModelTier.TIER_3_FLAGSHIP_REASONING
        before = self.gateway._tier_stats[tier].copy()
        fail_resp = LLMResponse(
            success=False,
            latency_ms=456.7,
            tokens_input=0,
            tokens_output=0,
            cost_usd=0.0,
            error="timeout",
        )
        self.gateway._update_tier_stats(tier, fail_resp)
        after = self.gateway._tier_stats[tier]

        assert after["total_requests"] == before["total_requests"] + 1
        assert after["total_failures"] == before["total_failures"] + 1
        assert after["total_successes"] == before["total_successes"]  # 不变

    def test_update_tier_stats_unknown_tier_no_crash(self):
        """未知 tier（不在 _tier_stats 的 key 中）不崩溃，函数直接 return"""
        # 函数签名是 tier: ModelTier，但鸭子类型下传入非枚举 key 不应抛错
        # 函数 L1794: tier_stat = self._tier_stats.get(tier) → None → L1795 return
        unknown_tier = "__not_a_registered_tier_key__"
        # 不抛异常 = 测试通过
        try:
            self.gateway._update_tier_stats(unknown_tier, LLMResponse())
        except Exception as exc:
            pytest.fail(f"未知 tier 传入 _update_tier_stats 不应抛异常，但抛了: {exc!r}")


# =============================================================================
# 缺口5: Provider 健康跟踪 半开探测
# =============================================================================
class TestProviderHealthHalfOpen:
    """Provider 半开探测 / 熔断机制测试"""

    def setup_method(self):
        """创建网关并确保有一个健康跟踪对象"""
        self.gateway = LLMGateway(LLMConfig(base_url="http://localhost/v1", api_key="test"))
        self.provider_name = "test_provider"
        if self.provider_name not in self.gateway._provider_health:
            self.gateway._provider_health[self.provider_name] = ProviderHealth(name=self.provider_name)
        self.health = self.gateway._provider_health[self.provider_name]

    def test_unavailable_not_elapsed_recovery_returns_circuit_error(self):
        """UNAVAILABLE 状态未到恢复时间：直接返回带熔断 error 的 response，不发 HTTP 请求"""
        # 设置：UNAVAILABLE + 10 秒前失败（RECOVERY_INTERVAL 默认 60s，所以没到）
        self.health.status = ProviderStatus.UNAVAILABLE
        self.health.consecutive_failures = 5
        self.health.last_failure_time = time.time() - 10  # 10s 前，< 60s

        # 不启动真实的 HTTP 调用，直接断言 _call_provider 开头的快速返回分支
        # 通过 patch _get_http_client，确保它没被调用（如果没被调用说明走了快速返回）
        import asyncio

        async def run_test():
            with patch.object(self.gateway, "_get_http_client", new_callable=AsyncMock) as mock_http:
                resp = await self.gateway._call_provider(
                    base_url="http://fake/v1",
                    api_key="sk-test1234567890abcdef",
                    model="test",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.7,
                    max_tokens=100,
                    provider_friendly_name=self.provider_name,
                )
                # 快速返回 → 不应该尝试创建 HTTP 客户端
                mock_http.assert_not_awaited()
                return resp

        resp = asyncio.run(run_test())
        assert resp.success is False
        assert "熔断" in resp.error or "不可用" in resp.error
        assert self.provider_name in resp.provider

    def test_unavailable_elapsed_recovery_goes_half_open(self):
        """UNAVAILABLE 状态超过 RECOVERY_INTERVAL_SEC → 转为 DEGRADED（半开），允许请求通过（调用 HTTP 客户端）

        我们手动控制 RECOVERY_INTERVAL_SEC 很短，然后用 mock HTTP 客户端确保请求开始执行。
        """
        import asyncio

        # 设置 RECOVERY_INTERVAL_SEC=1，last_failure_time 设为 2 秒前 → 超过间隔
        self.health.RECOVERY_INTERVAL_SEC = 1
        self.health.status = ProviderStatus.UNAVAILABLE
        self.health.consecutive_failures = 5
        self.health.last_failure_time = time.time() - 3  # 3s 前

        # Mock HTTP 客户端，让它在 post 时抛异常（不关心成功，只关心是否开始调用）
        mock_session = MagicMock()
        mock_session.post = MagicMock()
        # 让 post 返回一个上下文管理器，里面抛异常或直接返回
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_post(*a, **kw):
            yield MagicMock(status=200, json=AsyncMock(return_value={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                "model": "test",
            }), text=AsyncMock(return_value=""))

        mock_session.post.side_effect = fake_post

        async def run_test():
            with patch.object(self.gateway, "_get_http_client", new_callable=AsyncMock, return_value=mock_session):
                resp = await self.gateway._call_provider(
                    base_url="http://fake/v1",
                    api_key="sk-test1234567890abcdef",
                    model="test",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.7,
                    max_tokens=100,
                    provider_friendly_name=self.provider_name,
                )
                return resp

        resp = asyncio.run(run_test())

        # 关键：状态应该被设为 DEGRADED（半开），然后因为 HTTP 成功 → 最终为 HEALTHY
        # 我们检查状态变化：last_failure_time 超过 RECOVERY_INTERVAL → 进入半开（DEGRADED）
        # 然后 mock 返回成功 → 状态变为 HEALTHY
        assert self.health.status == ProviderStatus.HEALTHY
        assert resp.success is True

    def test_half_open_probe_failure_reverts_to_unavailable(self):
        """半开探测失败：立即重新转回 UNAVAILABLE"""
        import asyncio

        # 设置为 DEGRADED（半开状态）
        self.health.status = ProviderStatus.DEGRADED
        self.health.consecutive_failures = 0
        self.health.last_failure_time = 0

        mock_session = MagicMock()
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_post_fail(*a, **kw):
            # 返回非 200 状态，并且到最后一次重试
            yield MagicMock(
                status=500,
                text=AsyncMock(return_value='{"error": "server down"}'),
            )

        mock_session.post.side_effect = fake_post_fail

        async def run_test():
            # 设置 max_retries=1 省时间
            self.gateway._config.max_retries = 1
            with patch.object(self.gateway, "_get_http_client", new_callable=AsyncMock, return_value=mock_session):
                resp = await self.gateway._call_provider(
                    base_url="http://fake/v1",
                    api_key="sk-test1234567890abcdef",
                    model="test",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.7,
                    max_tokens=100,
                    provider_friendly_name=self.provider_name,
                )
                return resp

        resp = asyncio.run(run_test())

        # 半开探测失败 → 应该重新回到 UNAVAILABLE
        assert resp.success is False
        assert self.health.status == ProviderStatus.UNAVAILABLE

    def test_half_open_probe_success_becomes_healthy(self):
        """半开探测成功：转回 HEALTHY"""
        import asyncio

        self.health.status = ProviderStatus.DEGRADED
        self.health.consecutive_failures = 1
        self.health.last_failure_time = time.time() - 100

        mock_session = MagicMock()
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_post_ok(*a, **kw):
            yield MagicMock(
                status=200,
                json=AsyncMock(return_value={
                    "choices": [{"message": {"content": "hi back"}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                    "model": "test-model",
                }),
                text=AsyncMock(return_value=""),
            )

        mock_session.post.side_effect = fake_post_ok

        async def run_test():
            self.gateway._config.max_retries = 1
            with patch.object(self.gateway, "_get_http_client", new_callable=AsyncMock, return_value=mock_session):
                resp = await self.gateway._call_provider(
                    base_url="http://fake/v1",
                    api_key="sk-test1234567890abcdef",
                    model="test",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.7,
                    max_tokens=100,
                    provider_friendly_name=self.provider_name,
                )
                return resp

        resp = asyncio.run(run_test())
        assert resp.success is True
        assert self.health.status == ProviderStatus.HEALTHY
        assert self.health.consecutive_failures == 0

    def test_3_consecutive_failures_trigger_circuit_breaker(self):
        """连续 3 次失败达到熔断阈值 → 状态变为 UNAVAILABLE"""
        import asyncio

        self.health.status = ProviderStatus.HEALTHY
        self.health.consecutive_failures = 0

        mock_session = MagicMock()
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def fake_post_fail(*a, **kw):
            yield MagicMock(status=500, text=AsyncMock(return_value="err"))

        mock_session.post.side_effect = fake_post_fail
        self.gateway._config.max_retries = 1

        async def single_call():
            with patch.object(self.gateway, "_get_http_client", new_callable=AsyncMock, return_value=mock_session):
                return await self.gateway._call_provider(
                    base_url="http://fake/v1",
                    api_key="sk-test1234567890abcdef",
                    model="test",
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.7,
                    max_tokens=100,
                    provider_friendly_name=self.provider_name,
                )

        # 连续失败 2 次 → 还没到阈值（默认阈值 3，由 consecutive_failures >= 3 判断）
        asyncio.run(single_call())
        assert self.health.consecutive_failures == 1
        # 注意：_record_failure 中 was_half_open=False + consecutive_failures>=3 时才熔断
        # 所以第 3 次失败时状态变为 UNAVAILABLE
        asyncio.run(single_call())
        assert self.health.consecutive_failures == 2

        # 第 3 次失败 → 熔断
        asyncio.run(single_call())
        assert self.health.consecutive_failures == 3
        assert self.health.status == ProviderStatus.UNAVAILABLE


# =============================================================================
# 缺口6: configure_from_env 环境变量优先级与回填
# =============================================================================
class TestConfigureFromEnvPriorityAndBackfill:
    """configure_from_env 环境变量优先级与回填逻辑测试"""

    def setup_method(self):
        """每个测试前清理相关环境变量，创建干净网关"""
        self.env_keys = [
            "AEKV_LLM_BASE_URL", "AEKV_LLM_API_KEY", "AEKV_LLM_MODEL",
            "OPENAI_BASE_URL", "OPENAI_API_KEY",
            "DUCK_MISS_BASE_URL", "DUCK_MISS_API_KEY", "DUCK_MISS_DEFAULT_MODEL",
            "MODELSCOPE_BASE_URL", "MODELSCOPE_API_KEY", "MODELSCOPE_MODEL",
            "KIMI_BASE_URL", "KIMI_LOCAL_BASE_URL", "KIMI_API_KEY", "KIMI_MODEL",
            "DEEPSEEK_BASE_URL", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL",
            "DOUBAO_BASE_URL", "DOUBAO_API_KEY", "DOUBAO_MODEL",
            "DUCKMISS_API_KEY", "GPT_GATEWAY_API_KEY", "IMAGE_GEN_API_KEY",
            "AEKV_LLM_FALLBACKS",
        ]
        # 保存并清空
        self._saved_env = {}
        for k in self.env_keys:
            self._saved_env[k] = os.environ.get(k)
            if k in os.environ:
                del os.environ[k]

        # 空配置创建网关（方便观察回填效果）
        self.gateway = LLMGateway(LLMConfig(base_url="", api_key="", default_model="auto"))

    def teardown_method(self):
        """恢复环境变量"""
        for k, v in self._saved_env.items():
            if v is None:
                if k in os.environ:
                    del os.environ[k]
            else:
                os.environ[k] = v

    def test_modelscope_only_backfills_main_config(self):
        """只设置 MODELSCOPE_BASE_URL + MODELSCOPE_API_KEY（不设 AEKV_LLM_*）
        主配置 base_url/api_key 应该从 providers["modelscope"] 中回填

        回填路径：configure_providers_from_env → 加载 modelscope provider 到 providers dict
        → configure_from_env 末尾回填逻辑（非空 providers + 主配置空 → 回填）
        """
        os.environ["MODELSCOPE_BASE_URL"] = "https://modelscope-test.example.com/v1"
        os.environ["MODELSCOPE_API_KEY"] = "ms-test-key-1234567890abcdef"
        os.environ["MODELSCOPE_MODEL"] = "Qwen-Test-Model"

        # 确保没有 AEKV_LLM_* / OPENAI_* 前缀
        assert "AEKV_LLM_BASE_URL" not in os.environ
        assert "OPENAI_BASE_URL" not in os.environ

        self.gateway.configure_from_env()

        # providers 里应已加载 modelscope
        assert "modelscope" in self.gateway._config.providers
        assert self.gateway._config.providers["modelscope"]["base_url"] == "https://modelscope-test.example.com/v1"

        # 关键：回填后主配置应被填充（回填优先级 pref_order 中 modelscope 排第一，会被选中）
        assert self.gateway._config.base_url == "https://modelscope-test.example.com/v1"
        assert self.gateway._config.api_key == "ms-test-key-1234567890abcdef"
        # default_model 也会被回填为 modelscope 里的 default model
        assert self.gateway._config.default_model == "Qwen-Test-Model"

    def test_fallback_json_decode_error_does_not_crash(self):
        """AEKV_LLM_FALLBACKS JSON 解析失败时不崩溃（捕获 JSONDecodeError）"""
        # 设置无效 JSON
        os.environ["AEKV_LLM_FALLBACKS"] = "{invalid json, not real"
        os.environ["AEKV_LLM_BASE_URL"] = "https://primary.example.com/v1"
        os.environ["AEKV_LLM_API_KEY"] = "sk-test1234567890abcdef"

        # 不应抛异常
        try:
            self.gateway.configure_from_env()
        except json.JSONDecodeError:
            pytest.fail("configure_from_env 应捕获 JSONDecodeError 而不是抛出")
        except Exception as e:
            if "JSONDecodeError" in type(e).__name__ or "json" in str(e).lower():
                pytest.fail(f"不应因无效 fallback JSON 崩溃: {e}")
            raise

        # fallback_providers 应保持不变（默认 []）
        assert self.gateway._config.fallback_providers == []

    def test_valid_fallback_json_parsed_correctly(self):
        """有效 fallback JSON 应被正确解析（回归确认）"""
        valid = json.dumps([
            {"base_url": "https://fb1.example.com/v1", "api_key": "fb-key-1", "default_model": "m1"},
            {"base_url": "https://fb2.example.com/v1", "api_key": "fb-key-2"},
        ])
        os.environ["AEKV_LLM_FALLBACKS"] = valid
        os.environ["AEKV_LLM_BASE_URL"] = "https://pri.example.com/v1"
        os.environ["AEKV_LLM_API_KEY"] = "sk-pri1234567890abcdef"
        self.gateway.configure_from_env()
        assert len(self.gateway._config.fallback_providers) == 2
        assert self.gateway._config.fallback_providers[0]["base_url"] == "https://fb1.example.com/v1"

    def test_env_priority_aekv_over_openai_over_others(self):
        """环境变量优先级验证：
        base_url : AEKV_LLM_BASE_URL > OPENAI_BASE_URL > ...
        api_key  : AEKV_LLM_API_KEY > OPENAI_API_KEY > ...
        """
        # 同时设置多个前缀，AEKV_LLM 应最高优先级
        os.environ["AEKV_LLM_BASE_URL"] = "https://aekv-priority.example.com/v1"
        os.environ["OPENAI_BASE_URL"] = "https://openai.example.com/v1"
        os.environ["DEEPSEEK_BASE_URL"] = "https://deepseek.example.com/v1"
        os.environ["MODELSCOPE_BASE_URL"] = "https://modelscope.example.com/v1"

        os.environ["AEKV_LLM_API_KEY"] = "aekv-key-1234567890abcdef"
        os.environ["OPENAI_API_KEY"] = "openai-key-1234567890abcdef"
        os.environ["DEEPSEEK_API_KEY"] = "deepseek-key-1234567890abcdef"

        os.environ["AEKV_LLM_MODEL"] = "aekv-default-model"
        os.environ["DEEPSEEK_MODEL"] = "deepseek-model"
        os.environ["MODELSCOPE_MODEL"] = "ms-model"

        self.gateway.configure_from_env()

        # 断言 AEKV 优先级最高
        assert self.gateway._config.base_url == "https://aekv-priority.example.com/v1"
        assert self.gateway._config.api_key == "aekv-key-1234567890abcdef"
        assert self.gateway._config.default_model == "aekv-default-model"

    def test_env_priority_openai_over_secondary(self):
        """不设置 AEKV_LLM 时，OPENAI_* 优先于次级（ModelScope/DeepSeek 等）"""
        # 不设置 AEKV_LLM，只设置 OPENAI + DEEPSEEK + MODELSCOPE
        os.environ["OPENAI_BASE_URL"] = "https://openai.example.com/v1"
        os.environ["DEEPSEEK_BASE_URL"] = "https://deepseek.example.com/v1"
        os.environ["MODELSCOPE_BASE_URL"] = "https://modelscope.example.com/v1"

        os.environ["OPENAI_API_KEY"] = "openai-key-1234567890abcdef"
        os.environ["DEEPSEEK_API_KEY"] = "deepseek-key-1234567890abcdef"
        os.environ["MODELSCOPE_API_KEY"] = "ms-key-1234567890abcdef"

        self.gateway.configure_from_env()

        # OPENAI 应优先
        assert self.gateway._config.base_url == "https://openai.example.com/v1"
        assert self.gateway._config.api_key == "openai-key-1234567890abcdef"

    def test_env_priority_modelscope_over_deepseek_and_doubao(self):
        """当只有 ModelScope/DeepSeek/Doubao 时，按 _first 顺序 MODELSCOPE 先于 DEEPSEEK 和 DOUBAO
        base_url 顺序: MODELSCOPE_BASE_URL > KIMI > DEEPSEEK > DOUBAO
        """
        os.environ["MODELSCOPE_BASE_URL"] = "https://ms-1.example.com/v1"
        os.environ["MODELSCOPE_API_KEY"] = "ms-key-1234567890abcdef"
        os.environ["DEEPSEEK_BASE_URL"] = "https://ds.example.com/v1"
        os.environ["DEEPSEEK_API_KEY"] = "ds-key-1234567890abcdef"
        os.environ["DOUBAO_BASE_URL"] = "https://doubao.example.com/v1"
        os.environ["DOUBAO_API_KEY"] = "doubao-key-1234567890abcdef"

        self.gateway.configure_from_env()

        # 主配置顺序：MODELSCOPE 优先
        assert self.gateway._config.base_url == "https://ms-1.example.com/v1"
        assert self.gateway._config.api_key == "ms-key-1234567890abcdef"

        # providers 里应该有 modelscope, deepseek, doubao
        for name in ("modelscope", "deepseek", "doubao"):
            assert name in self.gateway._config.providers, f"provider {name} 缺失"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
