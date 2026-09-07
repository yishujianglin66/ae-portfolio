#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core.llm_gateway 路由层回归缺口测试 — 2026-08-24 工作树新增代码路径。

缺口识别依据（git diff core/llm_gateway.py）：
1. SiliconFlow Provider 加载（configure_providers_from_env 内新增块，无测试）
2. chat_with_routing Step 1b Provider 兜底链（TASK_PROVIDER_MAP 指向 Provider
   未加载时 → 寻找含同 model_type 的 Provider → 否则含 default 档 → 否则第一）
3. chat_with_routing 图片自动升级到 vision 档（images 非空且 model_type≠vision
   且目标 Provider 配置了 vision 档 → 升级）
4. QWEN_PRIVATIZED / QWEN_DATA_ISOLATION 合规标志边界值解析

不覆盖：HALF_OPEN 熔断器（test_llm_gateway_failover.py 已覆盖）、
QWEN_PRIORITY 路由（test_qwen_provider_integration.py 已覆盖）、
H3 TaskType 扩展（test_h3_llm_gateway.py 已覆盖）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# 环境变量隔离：所有测试在干净 env 中运行，避免 .env / 系统 env 串扰
# ---------------------------------------------------------------------------
_PROVIDER_ENV_KEYS = (
    # Claude / GPT / 图像 / DeepSeek / 豆包
    "AEKV_LLM_BASE_URL", "AEKV_LLM_API_KEY", "AEKV_LLM_MODEL",
    "OPENAI_BASE_URL", "OPENAI_API_KEY",
    "DUCKMISS_API_KEY", "DUCKMISS_BASE_URL",
    "GPT_GATEWAY_API_KEY",
    "IMAGE_GEN_API_KEY", "IMAGE_GEN_BASE_URL", "IMAGE_GEN_MODEL",
    "DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL",
    "DOUBAO_API_KEY", "DOUBAO_BASE_URL", "DOUBAO_MODEL", "ARK_API_KEY",
    # SiliconFlow
    "SILICONFLOW_API_KEY", "SILICONFLOW_BASE_URL",
    "SILICONFLOW_VISION_MODEL", "SILICONFLOW_DEFAULT_MODEL",
    "SILICONFLOW_FLASH_MODEL",
    # Qwen
    "QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_LOCAL_BASE_URL",
    "QWEN_MODEL", "QWEN_REASONING_MODEL", "QWEN_VISION_MODEL",
    "QWEN_FLASH_MODEL", "QWEN_PRIVATIZED", "QWEN_DATA_ISOLATION",
    "AEKV_QWEN_PRIORITY",
    # Fallback
    "AEKV_LLM_FALLBACKS",
)


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch):
    """测试前清空所有 Provider 相关环境变量，测试后恢复。"""
    saved = {}
    for k in _PROVIDER_ENV_KEYS:
        saved[k] = os.environ.get(k)
        if k in os.environ:
            del os.environ[k]
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v


def _make_gateway():
    """创建一个空配置的 LLMGateway（不依赖任何 env）。"""
    from core.llm_gateway import LLMGateway
    return LLMGateway()


# ===========================================================================
# 缺口1: SiliconFlow Provider 加载（视觉多模态高性价比）
# ===========================================================================

class TestSiliconFlowProviderRegistration:
    """SILICONFLOW_* 环境变量驱动的 Provider 注册。"""

    def test_siliconflow_registered_with_default_endpoint(self, monkeypatch):
        """仅设 SILICONFLOW_API_KEY → 默认端点 api.siliconflow.cn/v1。"""
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-sf-1234567890abcdef")
        gw = _make_gateway()
        gw.configure_providers_from_env()

        assert "siliconflow" in gw._config.providers
        cfg = gw._config.providers["siliconflow"]
        assert cfg["base_url"] == "https://api.siliconflow.cn/v1"
        assert cfg["api_key"] == "sk-test-sf-1234567890abcdef"
        # 三档位齐全：vision / default / fast
        assert "vision" in cfg["models"]
        assert "default" in cfg["models"]
        assert "fast" in cfg["models"]

    def test_siliconflow_not_registered_without_key(self):
        """无 SILICONFLOW_API_KEY → 不注册 siliconflow，不影响其它 Provider。"""
        gw = _make_gateway()
        gw.configure_providers_from_env()
        assert "siliconflow" not in gw._config.providers

    def test_siliconflow_model_names_overridable(self, monkeypatch):
        """三个模型名均可经 env 覆盖。"""
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-sf")
        monkeypatch.setenv("SILICONFLOW_VISION_MODEL", "Qwen/Qwen2-VL-72B")
        monkeypatch.setenv("SILICONFLOW_DEFAULT_MODEL", "Qwen/Qwen2-72B-Instruct")
        monkeypatch.setenv("SILICONFLOW_FLASH_MODEL", "deepseek-ai/DeepSeek-V3-Flash")

        gw = _make_gateway()
        gw.configure_providers_from_env()
        models = gw._config.providers["siliconflow"]["models"]
        assert models["vision"] == "Qwen/Qwen2-VL-72B"
        assert models["default"] == "Qwen/Qwen2-72B-Instruct"
        assert models["fast"] == "deepseek-ai/DeepSeek-V3-Flash"

    def test_siliconflow_base_url_overridable(self, monkeypatch):
        """SILICONFLOW_BASE_URL 可覆盖默认端点（私有化部署场景）。"""
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-sf")
        monkeypatch.setenv("SILICONFLOW_BASE_URL", "http://localhost:8080/v1")
        gw = _make_gateway()
        gw.configure_providers_from_env()
        assert gw._config.providers["siliconflow"]["base_url"] == "http://localhost:8080/v1"

    def test_siliconflow_health_tracked_after_register(self, monkeypatch):
        """注册后 _provider_health 自动跟踪 siliconflow。"""
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-sf")
        gw = _make_gateway()
        gw.configure_providers_from_env()
        # 健康字典中存在 siliconflow 对应条目
        assert any(
            h.name == "siliconflow" or h.name.startswith("api.siliconflow.cn")
            for h in gw._provider_health.values()
        ), f"_provider_health 未跟踪 siliconflow: {list(gw._provider_health.keys())}"


# ===========================================================================
# 缺口2: chat_with_routing Step 1b Provider 兜底链
# ===========================================================================

class TestProviderFallbackChain:
    """TASK_PROVIDER_MAP 指向的 Provider 未加载时的回退逻辑。

    回退策略（按优先级）：
      a) 已加载 Provider 中含目标 model_type 档位的第一个
      b) 否则已加载 Provider 中含 "default" 档位的第一个
      c) 否则已加载 Provider 字典第一个
    """

    def _prepare(
        self,
        monkeypatch,
        providers_cfg: dict,
        provider_name_override: str = None,
    ):
        """构造一个仅含指定 provider 的 gateway，monkey-patch chat_with_provider 记录调用。"""
        from core.llm_gateway import LLMResponse

        # 清理全部 provider env，确保仅 providers_cfg 生效
        for k in _PROVIDER_ENV_KEYS:
            if k in os.environ:
                del os.environ[k]

        gw = _make_gateway()
        # 手工注入 providers（绕过 env 加载，避免无关 Provider 干扰）
        gw._config.providers = providers_cfg
        # 重置健康状态
        from core.llm_gateway import ProviderHealth
        for name in providers_cfg:
            gw._provider_health[name] = ProviderHealth(name=name)

        calls = {}

        async def fake_chat_with_provider(prompt, provider, model_type="default",
                                           system_prompt="", images=None,
                                           temperature=0.7, max_tokens=4096,
                                           allow_tier_fallback=True):
            calls["provider"] = provider
            calls["model_type"] = model_type
            return LLMResponse(
                success=True, content="ok", provider=provider, model="m"
            )

        async def fake_nvidia(*args, **kwargs):
            return None  # NVIDIA 未配置，按 stub 默认行为

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        monkeypatch.setattr(gw, "_try_nvidia_local", fake_nvidia)
        return gw, calls

    @pytest.mark.asyncio
    async def test_target_provider_not_loaded_falls_back_to_same_model_type(
        self, monkeypatch
    ):
        """VISION_UNDERSTANDING 默认 siliconflow/vision，但 siliconflow 未加载
        → 找到含 vision 档位的 claude，回退到 claude/vision。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"vision": "claude-v", "default": "claude-d"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("看图", task_type=TaskType.VISION_UNDERSTANDING)
        assert resp.success
        # 回退到 claude（因为只有 claude 含 vision 档）
        assert calls["provider"] == "claude"
        assert calls["model_type"] == "vision"

    @pytest.mark.asyncio
    async def test_no_target_model_type_falls_back_to_default_tier(
        self, monkeypatch
    ):
        """无 Provider 含目标 vision 档，但有 Provider 含 default 档 → 回退到该 Provider。

        注意：Step 1b 仅替换 provider，不替换 model_type。model_type 仍由
        TASK_PROVIDER_MAP 指定为 vision，下游 chat_with_provider 内部
        _tier_fallback_sequence 再做档位回退。
        """
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "doubao": {
                "base_url": "https://ark.test/v1", "api_key": "sk-d",
                # doubao 只有 default 档（与生产配置一致）
                "models": {"default": "doubao-default"},
            },
        })

        from core.llm_gateway import TaskType
        # VISION_UNDERSTANDING → ("siliconflow", "vision")，但 siliconflow 未加载
        # → 找含 vision 档：doubao 没有 → 找含 default 档：doubao 有 → 回退 doubao
        resp = await gw.chat_with_routing("看图", task_type=TaskType.VISION_UNDERSTANDING)
        assert resp.success
        assert calls["provider"] == "doubao"
        # model_type 不被 Step 1b 替换（保持 TASK_PROVIDER_MAP 指定的 vision）
        assert calls["model_type"] == "vision"

    @pytest.mark.asyncio
    async def test_no_matching_model_type_falls_back_to_first_loaded(
        self, monkeypatch
    ):
        """无 Provider 含 default 档 → 退而求其次取 providers 字典第一个。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            # 仅一个 Provider，且只有 flash 档（既无 vision 也无 default）
            "weird_provider": {
                "base_url": "https://weird.test/v1", "api_key": "sk-w",
                "models": {"flash": "weird-flash"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("看图", task_type=TaskType.VISION_UNDERSTANDING)
        assert resp.success
        # 兜底取第一个
        assert calls["provider"] == "weird_provider"

    @pytest.mark.asyncio
    async def test_target_provider_loaded_skips_fallback(self, monkeypatch):
        """TASK_PROVIDER_MAP 指向的 Provider 已加载 → 跳过回退，直接调用。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "siliconflow": {
                "base_url": "https://api.siliconflow.cn/v1", "api_key": "sk-sf",
                "models": {"vision": "sf-vision", "default": "sf-default"},
            },
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"vision": "claude-v", "default": "claude-d"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("看图", task_type=TaskType.VISION_UNDERSTANDING)
        assert resp.success
        # 应当直接走 siliconflow，不回退到 claude
        assert calls["provider"] == "siliconflow"
        assert calls["model_type"] == "vision"


# ===========================================================================
# 缺口3: chat_with_routing 图片自动升级到 vision 档
# ===========================================================================

class TestImageAutoPromotionToVision:
    """images 非空 + Provider 含 vision 档 → model_type 自动升级为 vision。"""

    def _prepare(self, monkeypatch, providers_cfg: dict):
        from core.llm_gateway import LLMResponse

        for k in _PROVIDER_ENV_KEYS:
            if k in os.environ:
                del os.environ[k]

        gw = _make_gateway()
        gw._config.providers = providers_cfg
        from core.llm_gateway import ProviderHealth
        for name in providers_cfg:
            gw._provider_health[name] = ProviderHealth(name=name)

        calls = {}

        async def fake_chat_with_provider(prompt, provider, model_type="default",
                                           system_prompt="", images=None,
                                           temperature=0.7, max_tokens=4096,
                                           allow_tier_fallback=True):
            calls["provider"] = provider
            calls["model_type"] = model_type
            calls["images"] = images
            return LLMResponse(success=True, content="ok", provider=provider, model="m")

        async def fake_nvidia(*args, **kwargs):
            return None

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        monkeypatch.setattr(gw, "_try_nvidia_local", fake_nvidia)
        return gw, calls

    @pytest.mark.asyncio
    async def test_images_with_non_vision_task_promotes_to_vision(self, monkeypatch):
        """GENERAL 任务默认走 default 档，传 images → 自动升级到 vision 档。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"vision": "claude-v", "default": "claude-d"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("描述", task_type=TaskType.GENERAL,
                                           images=["fake_base64_data"])
        assert resp.success
        # 即使 GENERAL 默认走 default，images 应触发升级到 vision
        assert calls["model_type"] == "vision"
        assert calls["images"] == ["fake_base64_data"]

    @pytest.mark.asyncio
    async def test_images_already_vision_keeps_vision(self, monkeypatch):
        """VISION_UNDERSTANDING 已默认 vision 档，传 images → 保持 vision。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "siliconflow": {
                "base_url": "https://api.siliconflow.cn/v1", "api_key": "sk-sf",
                "models": {"vision": "sf-vision", "default": "sf-default"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("看图", task_type=TaskType.VISION_UNDERSTANDING,
                                           images=["img1"])
        assert resp.success
        assert calls["model_type"] == "vision"

    @pytest.mark.asyncio
    async def test_images_but_provider_no_vision_tier_keeps_original(
        self, monkeypatch
    ):
        """目标 Provider 没有 vision 档 → 维持 TASK_PROVIDER_MAP 原 model_type，不升级。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            # doubao 默认无 vision 档（与生产配置一致）
            "doubao": {
                "base_url": "https://ark.test/v1", "api_key": "sk-d",
                "models": {"default": "doubao-default"},
            },
        })

        from core.llm_gateway import TaskType
        # DEEP_REASONING → ("doubao", "thinking")
        # doubao 既无 thinking 也无 vision → 走 Step 1b（doubao 已加载，跳过），
        # model_type 保持 "thinking"。images 非空 → 检查 doubao 有无 vision 档
        # → 无 → 保持 "thinking"（不升级）。
        resp = await gw.chat_with_routing("推理", task_type=TaskType.DEEP_REASONING,
                                           images=["img1"])
        assert resp.success
        # 无 vision 档时维持原 model_type（"thinking" 由 DEEP_REASONING 指定）
        assert calls["model_type"] == "thinking"

    @pytest.mark.asyncio
    async def test_no_images_keeps_task_default_model_type(self, monkeypatch):
        """无 images → 维持 TASK_PROVIDER_MAP 指定的 model_type。"""
        gw, calls = self._prepare(monkeypatch, providers_cfg={
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"vision": "claude-v", "default": "claude-d"},
            },
        })

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("普通对话", task_type=TaskType.GENERAL)
        assert resp.success
        # 无 images → 保持 default
        assert calls["model_type"] == "default"


# ===========================================================================
# 缺口4: QWEN_PRIVATIZED / QWEN_DATA_ISOLATION 合规标志边界值
# ===========================================================================

class TestQwenComplianceFlagEdgeCases:
    """合规标志解析的字符串值边界（test_qwen_provider_integration.py 仅测了 happy path）。"""

    def test_privatized_various_truthy_values(self, monkeypatch):
        """privatized 接受 truthy 字符串：1/true/yes/on（大小写不敏感）。"""
        truthy = ("1", "true", "TRUE", "True", "yes", "YES", "Yes", "on", "ON", "On")
        for v in truthy:
            monkeypatch.setenv("QWEN_API_KEY", "sk-test")
            monkeypatch.setenv("QWEN_PRIVATIZED", v)
            gw = _make_gateway()
            gw.configure_providers_from_env()
            assert gw._config.providers["qwen"]["privatized"] is True, (
                f"QWEN_PRIVATIZED={v!r} 应解析为 True"
            )

    def test_privatized_falsy_values(self, monkeypatch):
        """privatized 接受 falsy 字符串：0/false/no/off/空串 → False。"""
        falsy = ("0", "false", "FALSE", "no", "NO", "off", "OFF", "")
        for v in falsy:
            monkeypatch.setenv("QWEN_API_KEY", "sk-test")
            monkeypatch.setenv("QWEN_PRIVATIZED", v)
            gw = _make_gateway()
            gw.configure_providers_from_env()
            assert gw._config.providers["qwen"]["privatized"] is False, (
                f"QWEN_PRIVATIZED={v!r} 应解析为 False"
            )

    def test_data_isolation_various_falsy_values(self, monkeypatch):
        """data_isolation 默认 True；显式 falsy 字符串 → False。"""
        falsy = ("0", "false", "FALSE", "no", "NO", "off", "OFF")
        for v in falsy:
            monkeypatch.setenv("QWEN_API_KEY", "sk-test")
            monkeypatch.setenv("QWEN_DATA_ISOLATION", v)
            gw = _make_gateway()
            gw.configure_providers_from_env()
            assert gw._config.providers["qwen"]["data_isolation"] is False, (
                f"QWEN_DATA_ISOLATION={v!r} 应解析为 False"
            )

    def test_data_isolation_truthy_or_empty_defaults_true(self, monkeypatch):
        """data_isolation：truthy 字符串 / 未设置 / 空串 → 默认 True。"""
        truthy = ("1", "true", "yes", "on", "ON", "")
        for v in truthy:
            monkeypatch.setenv("QWEN_API_KEY", "sk-test")
            monkeypatch.setenv("QWEN_DATA_ISOLATION", v)
            gw = _make_gateway()
            gw.configure_providers_from_env()
            assert gw._config.providers["qwen"]["data_isolation"] is True, (
                f"QWEN_DATA_ISOLATION={v!r} 应解析为 True（默认值）"
            )


# ===========================================================================
# 缺口5: _try_nvidia_local stub 默认行为
# ===========================================================================

class TestNvidiaLocalStub:
    """NVIDIA NIM 本地推理存根：未配置时返回 None，跳过走正常路由。"""

    @pytest.mark.asyncio
    async def test_nvidia_stub_returns_none_when_not_configured(self, monkeypatch):
        """未注入 _try_nvidia_local patch 时，默认 stub 返回 None（不影响主流程）。"""
        # 清空 env
        for k in _PROVIDER_ENV_KEYS:
            if k in os.environ:
                del os.environ[k]

        gw = _make_gateway()
        # 配置一个最小可用 Provider，使 chat_with_routing 走多 Provider 路径
        from core.llm_gateway import ProviderHealth, LLMResponse
        gw._config.providers = {
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"vision": "claude-v", "default": "claude-d"},
            },
        }
        gw._provider_health["claude"] = ProviderHealth(name="claude")

        async def fake_chat_with_provider(prompt, provider, model_type="default",
                                           **kwargs):
            return LLMResponse(success=True, content="ok", provider=provider, model="m")

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        # 不 patch _try_nvidia_local，让它走默认实现

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("hi", task_type=TaskType.GENERAL)
        # NVIDIA stub 返回 None → 跳过 → 走主流程 → 调用 chat_with_provider
        assert resp.success
        assert resp.provider == "claude"

    @pytest.mark.asyncio
    async def test_nvidia_stub_override_short_circuits(self, monkeypatch):
        """_try_nvidia_local 被 monkey-patch 返回成功 → 直接返回，跳过 chat_with_provider。"""
        for k in _PROVIDER_ENV_KEYS:
            if k in os.environ:
                del os.environ[k]

        gw = _make_gateway()
        from core.llm_gateway import ProviderHealth, LLMResponse
        gw._config.providers = {
            "claude": {
                "base_url": "https://claude.test/v1", "api_key": "sk-c",
                "models": {"default": "claude-d"},
            },
        }
        gw._provider_health["claude"] = ProviderHealth(name="claude")

        call_count = {"claude": 0}

        async def fake_chat_with_provider(prompt, provider, **kwargs):
            call_count["claude"] += 1
            return LLMResponse(success=True, content="from-claude", provider=provider, model="m")

        async def fake_nvidia(*args, **kwargs):
            # 模拟 NVIDIA 成功响应
            return LLMResponse(success=True, content="from-nvidia", provider="nvidia", model="local")

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        monkeypatch.setattr(gw, "_try_nvidia_local", fake_nvidia)

        from core.llm_gateway import TaskType
        resp = await gw.chat_with_routing("hi", task_type=TaskType.GENERAL)
        # NVIDIA 接管：返回 nvidia 提供的内容，且 chat_with_provider 不应被调用
        assert resp.success
        assert resp.content == "from-nvidia"
        assert resp.provider == "nvidia"
        assert call_count["claude"] == 0, (
            "NVIDIA 成功时应短路 chat_with_provider"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
