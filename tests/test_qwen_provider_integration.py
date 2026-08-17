#!/usr/bin/env python3
"""Qwen3.8-Max 接入：Provider 注册 + AEKV_QWEN_PRIORITY 上位开关 + model_router 备选链。

验收目标：
1. QWEN_API_KEY 存在时 configure_providers_from_env 注册 qwen Provider（默认 DashScope 端点）
2. QWEN_API_KEY 缺失时不注册 qwen（零破坏现有链路）
3. QWEN_LOCAL_BASE_URL 优先于 QWEN_BASE_URL（私有化自部署路径，权重落地后可用）
4. 模型名可经 env 覆盖；privatized/data_isolation 合规标志正确解析
5. AEKV_QWEN_PRIORITY=true 且 qwen 已注册 → 深度推理/视觉理解主选切换为 qwen
6. 开关关闭/未注册时主选保持 claude（TASK_PROVIDER_MAP 基线不变）
7. ai/model_router.py：QWEN_OFFICIAL_MODELS + 能力矩阵三级备选链 + 可用模型清单
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# 环境变量隔离
# ---------------------------------------------------------------------------

_QWEN_ENV_KEYS = (
    "QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_LOCAL_BASE_URL",
    "QWEN_MODEL", "QWEN_REASONING_MODEL", "QWEN_VISION_MODEL",
    "QWEN_FLASH_MODEL", "QWEN_PRIVATIZED", "QWEN_DATA_ISOLATION",
    "AEKV_QWEN_PRIORITY",
)


@pytest.fixture(autouse=True)
def _clean_qwen_env(monkeypatch):
    """所有测试前清除 Qwen 相关环境变量，避免 .env / 系统环境串扰。"""
    for k in _QWEN_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


def _make_gateway():
    from core.llm_gateway import LLMGateway

    return LLMGateway()


# ---------------------------------------------------------------------------
# 1-4: Provider 注册
# ---------------------------------------------------------------------------

class TestQwenProviderRegistration:

    def test_qwen_registered_with_api_key(self, monkeypatch):
        """QWEN_API_KEY 存在 → qwen Provider 注册，默认 DashScope 兼容端点。"""
        monkeypatch.setenv("QWEN_API_KEY", "sk-test-qwen")
        gw = _make_gateway()
        gw.configure_providers_from_env()

        assert "qwen" in gw._config.providers
        cfg = gw._config.providers["qwen"]
        assert cfg["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        assert cfg["api_key"] == "sk-test-qwen"
        # 四档位齐全：default/thinking/vision/flash
        models = cfg["models"]
        assert models["default"] == "qwen3.8-max"
        assert models["thinking"] == "qwen3.8-max"
        assert models["vision"] == "qwen3.8-max"
        assert models["flash"] == "qwen3.8-27b"
        # 合规标志默认值
        assert cfg["privatized"] is False
        assert cfg["data_isolation"] is True

    def test_qwen_not_registered_without_key(self):
        """无 QWEN_API_KEY → 不注册 qwen，不影响其他 Provider 加载。"""
        gw = _make_gateway()
        gw.configure_providers_from_env()
        assert "qwen" not in gw._config.providers

    def test_local_base_url_takes_precedence(self, monkeypatch):
        """QWEN_LOCAL_BASE_URL（vLLM 自部署）优先于 QWEN_BASE_URL。"""
        monkeypatch.setenv("QWEN_API_KEY", "sk-test-qwen")
        monkeypatch.setenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        monkeypatch.setenv("QWEN_LOCAL_BASE_URL", "http://localhost:8000/v1")
        monkeypatch.setenv("QWEN_PRIVATIZED", "true")
        gw = _make_gateway()
        gw.configure_providers_from_env()

        cfg = gw._config.providers["qwen"]
        assert cfg["base_url"] == "http://localhost:8000/v1"
        assert cfg["privatized"] is True

    def test_model_names_env_override(self, monkeypatch):
        """模型名全部可经 env 覆盖（应对官方 model ID 调整）。"""
        monkeypatch.setenv("QWEN_API_KEY", "sk-test-qwen")
        monkeypatch.setenv("QWEN_MODEL", "qwen-max-latest")
        monkeypatch.setenv("QWEN_REASONING_MODEL", "qwen3.8-max-thinking")
        monkeypatch.setenv("QWEN_VISION_MODEL", "qwen3.8-max-vl")
        monkeypatch.setenv("QWEN_FLASH_MODEL", "qwen3.8-27b-instruct")
        gw = _make_gateway()
        gw.configure_providers_from_env()

        models = gw._config.providers["qwen"]["models"]
        assert models["default"] == "qwen-max-latest"
        assert models["thinking"] == "qwen3.8-max-thinking"
        assert models["vision"] == "qwen3.8-max-vl"
        assert models["flash"] == "qwen3.8-27b-instruct"


# ---------------------------------------------------------------------------
# 5-6: AEKV_QWEN_PRIORITY 上位开关
# ---------------------------------------------------------------------------

class TestQwenPriorityRouting:

    def _prepare_gateway(self, monkeypatch, priority: bool):
        from core.llm_gateway import LLMResponse

        monkeypatch.setenv("QWEN_API_KEY", "sk-test-qwen")
        if priority:
            monkeypatch.setenv("AEKV_QWEN_PRIORITY", "true")
        gw = _make_gateway()
        gw.configure_providers_from_env()

        calls = {}

        async def fake_chat_with_provider(prompt, provider, model_type="default",
                                           system_prompt="", images=None,
                                           temperature=0.7, max_tokens=4096):
            calls["provider"] = provider
            calls["model_type"] = model_type
            return LLMResponse(success=True, content="ok", provider=provider, model="m")

        async def fake_nvidia_local(*args, **kwargs):
            return LLMResponse(success=False, error="nvidia not configured")

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        monkeypatch.setattr(gw, "_try_nvidia_local", fake_nvidia_local)
        return gw, calls

    @pytest.mark.asyncio
    async def test_priority_on_routes_vision_to_qwen(self, monkeypatch):
        """开关开启 → VISION_UNDERSTANDING 主选切换为 qwen/vision。"""
        from core.llm_gateway import TaskType

        gw, calls = self._prepare_gateway(monkeypatch, priority=True)
        resp = await gw.chat_with_routing("描述画面", task_type=TaskType.VISION_UNDERSTANDING)
        assert resp.success
        assert calls["provider"] == "qwen"
        assert calls["model_type"] == "vision"

    @pytest.mark.asyncio
    async def test_priority_on_routes_review_to_qwen_thinking(self, monkeypatch):
        """开关开启 → QUALITY_REVIEW（深度推理档位）切换为 qwen/thinking。"""
        from core.llm_gateway import TaskType

        gw, calls = self._prepare_gateway(monkeypatch, priority=True)
        resp = await gw.chat_with_routing("审查质量", task_type=TaskType.QUALITY_REVIEW)
        assert resp.success
        assert calls["provider"] == "qwen"
        assert calls["model_type"] == "thinking"

    @pytest.mark.asyncio
    async def test_priority_off_keeps_claude_primary(self, monkeypatch):
        """开关默认关闭 → 主选保持当前路由基线（2026-08-14 重路由后视觉走 siliconflow）。"""
        from core.llm_gateway import TaskType

        gw, calls = self._prepare_gateway(monkeypatch, priority=False)
        await gw.chat_with_routing("描述画面", task_type=TaskType.VISION_UNDERSTANDING)
        assert calls["provider"] == "siliconflow"
        assert calls["model_type"] == "vision"

    @pytest.mark.asyncio
    async def test_priority_on_but_qwen_unregistered_keeps_claude(self, monkeypatch):
        """开关开启但 qwen 未注册（无 key）→ 自动不生效，保持当前主选 siliconflow。"""
        from core.llm_gateway import LLMResponse, TaskType

        monkeypatch.setenv("AEKV_QWEN_PRIORITY", "true")  # 注意：不设 QWEN_API_KEY
        monkeypatch.setenv("SILICONFLOW_API_KEY", "sk-test-sf")  # 使 providers 非空
        gw = _make_gateway()
        gw.configure_providers_from_env()
        assert "qwen" not in gw._config.providers

        calls = {}

        async def fake_chat_with_provider(prompt, provider, model_type="default",
                                           system_prompt="", images=None,
                                           temperature=0.7, max_tokens=4096):
            calls["provider"] = provider
            return LLMResponse(success=True, content="ok", provider=provider)

        async def fake_nvidia_local(*args, **kwargs):
            return LLMResponse(success=False, error="nvidia not configured")

        monkeypatch.setattr(gw, "chat_with_provider", fake_chat_with_provider)
        monkeypatch.setattr(gw, "_try_nvidia_local", fake_nvidia_local)

        await gw.chat_with_routing("描述画面", task_type=TaskType.VISION_UNDERSTANDING)
        assert calls["provider"] == "siliconflow"

    def test_task_provider_map_baseline_unchanged(self):
        """TASK_PROVIDER_MAP 基线（2026-08-14 重路由: 视觉→siliconflow, 深度推理→doubao）。"""
        from core.llm_gateway import TASK_PROVIDER_MAP, TaskType

        assert TASK_PROVIDER_MAP[TaskType.VISION_UNDERSTANDING] == ("siliconflow", "vision")
        assert TASK_PROVIDER_MAP[TaskType.QUALITY_REVIEW] == ("doubao", "thinking")

    def test_qwen_priority_tasks_constant_defined(self):
        """QWEN_PRIORITY_TASKS 常量定义正确。"""
        from core.llm_gateway import QWEN_PRIORITY_TASKS, TaskType

        assert QWEN_PRIORITY_TASKS[TaskType.VISION_UNDERSTANDING] == ("qwen", "vision")
        assert QWEN_PRIORITY_TASKS[TaskType.QUALITY_REVIEW] == ("qwen", "thinking")


# ---------------------------------------------------------------------------
# 7: ai/model_router.py 集成
# ---------------------------------------------------------------------------

class TestModelRouterQwenIntegration:

    def test_qwen_official_models_defined(self):
        """QWEN_OFFICIAL_MODELS 四档位定义且可被 env 覆盖。"""
        from ai.model_router import QWEN_OFFICIAL_MODELS

        assert QWEN_OFFICIAL_MODELS["default"] == "qwen3.8-max"
        assert QWEN_OFFICIAL_MODELS["thinking"] == "qwen3.8-max"
        assert QWEN_OFFICIAL_MODELS["vision"] == "qwen3.8-max"
        assert QWEN_OFFICIAL_MODELS["flash"] == "qwen3.8-27b"

    def test_capability_matrix_third_fallback_is_qwen(self):
        """deep_reasoning / multimodal_understanding 扩展为三级备选链（索引 4/5 为 qwen）。"""
        from ai.model_router import MODEL_CAPABILITY_MATRIX

        dr = MODEL_CAPABILITY_MATRIX["deep_reasoning"]
        assert len(dr) == 6
        assert dr[0] == "claude"          # 主选不变
        assert dr[4] == "qwen"
        assert dr[5] == "qwen3.8-max"

        mm = MODEL_CAPABILITY_MATRIX["multimodal_understanding"]
        assert len(mm) == 6
        assert mm[0] == "claude"
        assert mm[4] == "qwen"
        assert mm[5] == "qwen3.8-max"

    def test_capability_matrix_backward_compatible(self):
        """其余条目保持 4 元组，向后兼容。"""
        from ai.model_router import MODEL_CAPABILITY_MATRIX

        for key in ("visual_analysis", "code_generation", "fast_classification",
                    "parameter_inference", "color_analysis", "rhythm_analysis",
                    "creative_writing", "complex_planning"):
            assert len(MODEL_CAPABILITY_MATRIX[key]) == 4, f"{key} 应保持 4 元组"

    def test_available_models_include_qwen(self):
        """get_all_available_models 的 text_pro / vision 清单含 qwen3.8-max。"""
        from ai.model_router import get_all_available_models

        models = get_all_available_models()
        assert "qwen3.8-max" in models["text_pro"]
        assert "qwen3.8-max" in models["vision"]
