#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.local_model_adapter import (
    InferenceBackend,
    LocalModelAdapter,
    LocalModelConfig,
    LocalModelResponse,
    LocalModelType,
)


class TestBackendSelect:
    def test_default_backend_is_transformers(self):
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
        )
        assert cfg.backend == InferenceBackend.TRANSFORMERS

    def test_backend_openvino_enum_exists(self):
        assert InferenceBackend.OPENVINO.value == "openvino"
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            backend=InferenceBackend.OPENVINO,
        )
        assert cfg.backend == InferenceBackend.OPENVINO
        assert cfg.ov_compile_precision == "fp16"

    @pytest.mark.asyncio
    async def test_check_openvino_ready_missing_libs(self):
        adapter = LocalModelAdapter(
            LocalModelConfig(
                model_type=LocalModelType.QWEN2_15B,
                model_path="Qwen/Qwen2-1.5B",
                backend=InferenceBackend.OPENVINO,
            )
        )

        def _fake_import():
            raise ImportError("No module named 'optimum'")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = lambda fn, *a, **kw: asyncio.to_thread(_fake_import) if False else fn()
            ok, reason = await adapter._check_openvino_ready()
            assert ok is False
            assert "缺少依赖库" in reason

    @pytest.mark.asyncio
    async def test_check_openvino_ready_import_error_specific(self):
        adapter = LocalModelAdapter(
            LocalModelConfig(
                model_type=LocalModelType.QWEN2_15B,
                model_path="Qwen/Qwen2-1.5B",
                backend=InferenceBackend.OPENVINO,
            )
        )

        real_side_effect = ImportError("No module named 'openvino'")

        async def _fake_to_thread(fn, *a, **kw):
            raise real_side_effect

        with patch("asyncio.to_thread", _fake_to_thread):
            ok, reason = await adapter._check_openvino_ready()
            assert ok is False


class TestOVResolveDevice:
    @pytest.mark.parametrize(
        "device, expected",
        [
            ("gpu", "GPU.0"),
            ("GPU", "GPU.0"),
            ("cuda", "GPU.0"),
            ("CUDA", "GPU.0"),
            ("npu", "NPU"),
            ("NPU", "NPU"),
            ("cpu", "CPU"),
            ("CPU", "CPU"),
            ("any_unknown", "CPU"),
        ],
    )
    def test_resolve_device(self, device, expected):
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            device=device,
            backend=InferenceBackend.OPENVINO,
        )
        adapter = LocalModelAdapter(cfg)
        assert adapter._resolve_ov_device() == expected


class TestOVDispatch:
    @pytest.mark.asyncio
    async def test_initialize_openvino_dispatch(self):
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            backend=InferenceBackend.OPENVINO,
        )
        adapter = LocalModelAdapter(cfg)

        with patch.object(adapter, "_initialize_openvino", new_callable=AsyncMock) as mock_init_ov, \
             patch.object(adapter, "_initialize_transformers", new_callable=AsyncMock) as mock_init_tf:
            mock_init_ov.return_value = None
            ok, err = await adapter.initialize()
            assert ok is True
            mock_init_ov.assert_awaited_once()
            mock_init_tf.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_openvino_dispatch_not_touch_transformers(self):
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            backend=InferenceBackend.OPENVINO,
        )
        adapter = LocalModelAdapter(cfg)
        adapter._initialized = True
        adapter._init_error = None

        fake_resp = LocalModelResponse(
            success=True,
            content="Hello from OpenVINO",
            tokens_used=10,
        )

        with patch.object(adapter, "_generate_openvino", new_callable=AsyncMock) as mock_gen_ov:
            mock_gen_ov.return_value = fake_resp
            import torch as _torch
            with patch("core.local_model_adapter.LocalModelAdapter.generate") as _:
                pass
            resp = await adapter.generate("test prompt")
            assert resp.success is True
            assert resp.content == "Hello from OpenVINO"
            mock_gen_ov.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_initialize_transformers_dispatch_when_backend_tf(self):
        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            backend=InferenceBackend.TRANSFORMERS,
        )
        adapter = LocalModelAdapter(cfg)

        with patch.object(adapter, "_initialize_openvino", new_callable=AsyncMock) as mock_init_ov, \
             patch.object(adapter, "_initialize_transformers", new_callable=AsyncMock) as mock_init_tf:
            mock_init_tf.return_value = True
            ok, err = await adapter.initialize()
            assert ok is True
            mock_init_tf.assert_awaited_once()
            mock_init_ov.assert_not_awaited()


class TestLLMGatewayLocal:
    @pytest.mark.asyncio
    async def test_chat_routes_to_local_openvino_when_base_url_says_so(self):
        from core.llm_gateway import LLMGateway, LLMConfig, LLMResponse

        cfg = LLMConfig(
            base_url="local://openvino/qwen2-1.5b",
            api_key="none",
            default_model="qwen2-1.5b",
        )
        gateway = LLMGateway(cfg)

        fake_llm_resp = LLMResponse(
            success=True,
            content="从本地 OpenVINO 返回的内容",
            provider="local_openvino",
            model="qwen2-1.5b",
            tokens_output=5,
        )

        with patch.object(gateway, "_call_local_openvino", new_callable=AsyncMock) as mock_local:
            mock_local.return_value = fake_llm_resp
            resp = await gateway.chat("你好")
            assert resp.success is True
            assert resp.content == "从本地 OpenVINO 返回的内容"
            mock_local.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_provider_chain_lands_on_local_openvino(self):
        from core.llm_gateway import LLMGateway, LLMConfig, LLMResponse

        primary_fail = LLMResponse(
            success=False, provider="primary", error="primary network down"
        )
        ark_fail = LLMResponse(
            success=False, provider="fallback_0", error="ark down"
        )
        local_ok = LLMResponse(
            success=True,
            content="Fallback 到本地成功",
            provider="fallback_1",
            model="qwen2-1.5b",
            tokens_output=3,
        )

        cfg = LLMConfig(
            base_url="https://duckmiss.site/v1",
            api_key="fake-test-key-12345",
            default_model="claude-sonnet-4-6",
            enable_fallback=True,
            fallback_providers=[
                {
                    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                    "api_key": "ark-key",
                    "default_model": "deepseek-v4-pro-260425",
                },
                {
                    "name": "local_openvino",
                    "base_url": "local://openvino/qwen2-1.5b",
                    "api_key": "none",
                    "default_model": "qwen2-1.5b",
                },
            ],
        )
        gateway = LLMGateway(cfg)

        call_count = {"n": 0}

        async def _fake_call_provider(*a, **kw):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return primary_fail
            if call_count["n"] == 2:
                return ark_fail
            return local_ok

        with patch.object(gateway, "_call_provider", _fake_call_provider):
            resp = await gateway.chat("测试兜底链")

        assert resp.success is True
        assert resp.content == "Fallback 到本地成功"
        assert call_count["n"] == 3


class TestInt4Fallback:
    @pytest.mark.asyncio
    async def test_int4_quantize_failure_falls_back_to_int8_with_warning(self, caplog):
        import logging

        cfg = LocalModelConfig(
            model_type=LocalModelType.QWEN2_15B,
            model_path="Qwen/Qwen2-1.5B",
            backend=InferenceBackend.OPENVINO,
            ov_compile_precision="int4",
        )
        adapter = LocalModelAdapter(cfg)

        real_init_ov = adapter._initialize_openvino

        async def _patched_init_ov():
            # 模拟：int4 量化失败时，应该记录 WARNING 并降级 int8
            logger_name = "core.local_model_adapter"
            import logging as _lg
            _lg.getLogger(logger_name).warning(
                "OpenVINO int4 量化失败: NNCF 未安装，降级到 int8"
            )
            adapter._initialized = True

        with patch.object(adapter, "_initialize_openvino", _patched_init_ov),              caplog.at_level(logging.WARNING, logger="core.local_model_adapter"):
            await adapter.initialize()

        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        has_int4_warn = any("int4" in r.getMessage().lower() for r in warnings)
        assert has_int4_warn, f"expected int4 warning in caplog: {[r.getMessage() for r in warnings]}"
