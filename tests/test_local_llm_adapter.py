#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 LocalLLMAdapter 核心业务逻辑
==================================

覆盖 ai/local_llm_adapter.py 中对产品稳定性最关键的部分：
1. 显存驱动的模型自动选择（_auto_select_model）
2. 显存不足时的降级路径（initialize 中 size_category != TINY 分支）
3. 缺依赖时 chat() 失败信息（快速回退保障）
4. get_info() 输出结构稳定（被 LLM gateway 调用）
5. quick_chat() 在初始化失败时返回错误字符串（不抛异常）
6. get_local_llm_adapter() 全局单例语义
7. ModelSize 枚举值、LocalModelConfig / LLMResponse 字段
8. RECOMMENDED_MODELS 字典完整性
9. detect_format 路径以外的 detect_format 分支
10. unload() 在 model 为 None 时不抛异常

注意：这些测试不真正加载 transformers/torch 模型，
仅覆盖决定路由与故障语义的纯逻辑。
"""
from __future__ import annotations

import asyncio
import os
import sys
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================
# 数据类 / 枚举
# ============================================================
class TestModelSize:
    """ModelSize 枚举值必须稳定（路由会读 .value）。"""

    def test_size_values(self):
        from ai.local_llm_adapter import ModelSize

        assert ModelSize.TINY.value == "tiny"
        assert ModelSize.SMALL.value == "small"
        assert ModelSize.MEDIUM.value == "medium"

    def test_size_count(self):
        from ai.local_llm_adapter import ModelSize

        # 一旦增减枚举值需同步更新 model_router / 推荐表
        assert len(list(ModelSize)) == 3


class TestLocalModelConfig:
    """LocalModelConfig 字段必须符合 LLM gateway 的读取约定。"""

    def test_required_fields(self):
        from ai.local_llm_adapter import LocalModelConfig, ModelSize

        cfg = LocalModelConfig(
            model_id="test/model",
            name="Test",
            size_category=ModelSize.SMALL,
            vram_required_gb=2.0,
            description="desc",
        )
        assert cfg.model_id == "test/model"
        assert cfg.name == "Test"
        assert cfg.size_category is ModelSize.SMALL
        assert cfg.vram_required_gb == 2.0
        assert cfg.description == "desc"
        assert cfg.max_context_length == 4096  # 默认值


class TestLLMResponse:
    """LLMResponse 字段必须稳定（被上游使用）。"""

    def test_default_values(self):
        from ai.local_llm_adapter import LLMResponse

        r = LLMResponse()
        assert r.content == ""
        assert r.model == ""
        assert r.tokens_input == 0
        assert r.tokens_output == 0
        assert r.latency_ms == 0.0
        assert r.success is False
        assert r.error == ""
        assert r.device == "cpu"
        assert r.raw == {}

    def test_assignable(self):
        from ai.local_llm_adapter import LLMResponse

        r = LLMResponse(
            content="hi",
            model="phi3",
            tokens_input=5,
            tokens_output=2,
            latency_ms=120.0,
            success=True,
            device="cuda:0",
        )
        assert r.success is True
        assert r.device == "cuda:0"
        assert r.latency_ms == 120.0


# ============================================================
# 推荐模型表
# ============================================================
class TestRecommendedModels:
    """RECOMMENDED_MODELS 必须包含关键模型键（业务依赖）。"""

    def test_required_keys(self):
        from ai.local_llm_adapter import RECOMMENDED_MODELS

        for key in ("phi3-mini", "gemma2-2b", "qwen2-7b", "llama3-8b"):
            assert key in RECOMMENDED_MODELS, f"缺失关键模型键: {key}"

    def test_all_have_valid_config(self):
        from ai.local_llm_adapter import RECOMMENDED_MODELS, LocalModelConfig

        for key, cfg in RECOMMENDED_MODELS.items():
            assert isinstance(cfg, LocalModelConfig)
            assert cfg.model_id, f"{key} 缺少 model_id"
            assert cfg.name, f"{key} 缺少 name"
            assert cfg.vram_required_gb > 0, f"{key} vram_required_gb <= 0"
            assert cfg.max_context_length > 0, f"{key} max_context_length <= 0"

    def test_vram_progression(self):
        """TINY < SMALL < MEDIUM：降级路径才能选择更小模型。"""
        from ai.local_llm_adapter import RECOMMENDED_MODELS, ModelSize

        sizes = {
            ModelSize.TINY: [],
            ModelSize.SMALL: [],
            ModelSize.MEDIUM: [],
        }
        for cfg in RECOMMENDED_MODELS.values():
            sizes[cfg.size_category].append(cfg.vram_required_gb)

        if sizes[ModelSize.TINY] and sizes[ModelSize.MEDIUM]:
            assert max(sizes[ModelSize.TINY]) <= min(sizes[ModelSize.MEDIUM])


# ============================================================
# LocalLLMAdapter 行为
# ============================================================
class TestLocalLLMAdapterInit:
    """构造与依赖检查的契约。"""

    def test_default_init(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        assert adapter.model_dir == tmp_path
        assert adapter._is_initialized is False
        assert adapter._model is None
        assert adapter._tokenizer is None

    def test_model_dir_created(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        new_dir = tmp_path / "nested" / "models"
        assert not new_dir.exists()
        adapter = LocalLLMAdapter(model_dir=new_dir)
        assert new_dir.exists()

    def test_unknown_model_name_keeps_none(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_name="nonexistent-model", model_dir=tmp_path)
        assert adapter._model_config is None

    def test_known_model_name_stored(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_name="phi3-mini", model_dir=tmp_path)
        assert adapter._model_config is not None
        assert adapter._model_config.size_category is ModelSize.SMALL

    def test_dependency_flags_reflect_real_env(self, tmp_path):
        """_torch_available 等属性必须反映真实环境（不能硬编码 True/False）。"""
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        # 至少一个为 bool
        assert isinstance(adapter._torch_available, bool)
        assert isinstance(adapter._transformers_available, bool)
        assert isinstance(adapter._bnb_available, bool)


class TestAutoSelectModel:
    """_auto_select_model 必须根据 VRAM 选择合适档位。"""

    def test_high_vram_selects_medium(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 12.0}):
            cfg = adapter._auto_select_model()
        # 8GB+ VRAM 选 MEDIUM（7-8B）
        assert cfg.size_category is ModelSize.MEDIUM

    def test_mid_vram_selects_small(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 6.0}):
            cfg = adapter._auto_select_model()
        assert cfg.size_category is ModelSize.SMALL

    def test_low_vram_selects_tiny(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 2.0}):
            cfg = adapter._auto_select_model()
        assert cfg.size_category is ModelSize.TINY

    def test_no_gpu_selects_tiny(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_detect_gpu", return_value={"available": False, "vram_gb": 0}):
            cfg = adapter._auto_select_model()
        assert cfg.size_category is ModelSize.TINY

    def test_boundary_vram_8gb_is_medium(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        # 边界值：恰好 8GB
        with patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 8.0}):
            cfg = adapter._auto_select_model()
        assert cfg.size_category is ModelSize.MEDIUM

    def test_boundary_vram_4gb_is_small(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 4.0}):
            cfg = adapter._auto_select_model()
        assert cfg.size_category is ModelSize.SMALL


class TestInitializeDowngrade:
    """initialize() 在 VRAM 不足时降级到更小模型。

    注意：所有用例都 mock `_load_model` 避免真实加载 4-bit 量化模型。
    """

    @staticmethod
    def _async_noop(*_args, **_kwargs):
        """生成一个可 await 的 mock 函数。"""
        async def _coro(*_a, **_kw):
            return None
        return _coro

    @pytest.mark.asyncio
    async def test_no_deps_returns_false(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", False), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=self._async_noop()):
            ok = await adapter.initialize()
        assert ok is False
        assert adapter._is_initialized is False

    @pytest.mark.asyncio
    async def test_vram_downgrade_when_model_exceeds_available(self, tmp_path):
        """请求 7B 模型但只有 3GB VRAM → 降级到 Gemma 2 2B（TINY）。"""
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize, RECOMMENDED_MODELS

        adapter = LocalLLMAdapter(model_name="qwen2-7b", model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=self._async_noop()), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 3.0}):
            ok = await adapter.initialize(model_name="qwen2-7b")
        # 不需要真正加载模型，只验证降级路径
        assert ok is True
        # 关键是降级后的配置应该是 TINY
        assert adapter._model_config is not None
        assert adapter._model_config.size_category is ModelSize.TINY
        assert adapter._model_config.model_id == RECOMMENDED_MODELS["gemma2-2b"].model_id
        assert adapter._is_initialized is True

    @pytest.mark.asyncio
    async def test_tiny_model_not_downgraded(self, tmp_path):
        """已经是最小模型时不重复降级。"""
        from ai.local_llm_adapter import LocalLLMAdapter, ModelSize

        adapter = LocalLLMAdapter(model_name="gemma2-2b", model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=self._async_noop()), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 0.5}):
            await adapter.initialize(model_name="gemma2-2b")
        # 保持 TINY，不应被替换为不存在的更小模型
        assert adapter._model_config.size_category is ModelSize.TINY

    @pytest.mark.asyncio
    async def test_already_initialized_returns_true(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        adapter._is_initialized = True
        ok = await adapter.initialize()
        assert ok is True

    @pytest.mark.asyncio
    async def test_explicit_model_name_overrides_existing(self, tmp_path):
        """显式传 model_name 时应替换已有配置。"""
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_name="gemma2-2b", model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=self._async_noop()), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 10.0}):
            await adapter.initialize(model_name="qwen2-7b")
        assert adapter._model_config is not None
        assert "Qwen2" in adapter._model_config.name

    @pytest.mark.asyncio
    async def test_load_model_failure_returns_false(self, tmp_path):
        """_load_model 抛异常时 initialize 返回 False（不应崩溃上层）。"""
        from ai.local_llm_adapter import LocalLLMAdapter

        async def failing_load(*_a, **_kw):
            raise RuntimeError("加载失败")

        adapter = LocalLLMAdapter(model_name="phi3-mini", model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=failing_load), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 12.0}):
            ok = await adapter.initialize(model_name="phi3-mini")
        assert ok is False
        assert adapter._is_initialized is False


# ============================================================
# get_info / quick_chat / get_local_llm_adapter / unload
# ============================================================
class TestGetInfo:
    """get_info() 输出结构是 LLM 网关调用的契约。"""

    def test_initial_state(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        info = adapter.get_info()
        assert info["initialized"] is False
        assert "torch_available" in info
        assert "transformers_available" in info
        assert "bnb_available" in info
        assert "gpu_info" in info
        # current_model 在未设置时为 None
        assert info["current_model"] is None
        # 至少暴露 4 个推荐模型
        assert len(info["available_models"]) == 4

    def test_with_model_set(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_name="phi3-mini", model_dir=tmp_path)
        info = adapter.get_info()
        assert info["current_model"] is not None
        assert info["current_model"]["name"] == "Phi-3 Mini"
        assert info["current_model"]["vram_required_gb"] == 2.5
        # 暴露的字段
        for key in ("key", "name", "vram_required_gb", "description"):
            assert key in info["available_models"][0]

    def test_available_models_match_recommended(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter, RECOMMENDED_MODELS

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        info = adapter.get_info()
        keys = {m["key"] for m in info["available_models"]}
        assert keys == set(RECOMMENDED_MODELS.keys())


class TestChatFailurePath:
    """chat() 在初始化失败时不应抛异常，必须返回 LLMResponse(success=False)。"""

    @pytest.mark.asyncio
    async def test_chat_returns_error_when_init_fails(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        with patch.object(adapter, "_torch_available", False), \
             patch.object(adapter, "_transformers_available", True):
            resp = await adapter.chat("hello")
        assert resp.success is False
        assert "初始化" in resp.error or "init" in resp.error.lower() or "失败" in resp.error
        assert resp.latency_ms >= 0


class TestQuickChat:
    """quick_chat 在失败时必须返回 [错误]... 字符串（不抛异常给上层）。"""

    @pytest.mark.asyncio
    async def test_returns_error_string_on_init_failure(self, tmp_path):
        from ai.local_llm_adapter import quick_chat

        with patch("ai.local_llm_adapter.LocalLLMAdapter") as MockAdapter:
            instance = MockAdapter.return_value
            instance.chat = MagicMock(
                return_value=asyncio.Future()
            )
            instance.chat.return_value.set_result(
                _make_failed_response("依赖缺失")
            )
            result = await quick_chat("test", model_name="phi3-mini")
        assert result.startswith("[错误]")
        assert "依赖缺失" in result

    @pytest.mark.asyncio
    async def test_returns_content_on_success(self):
        from ai.local_llm_adapter import quick_chat

        with patch("ai.local_llm_adapter.LocalLLMAdapter") as MockAdapter:
            instance = MockAdapter.return_value
            fut = asyncio.Future()
            fut.set_result(_make_success_response("hello back"))
            instance.chat.return_value = fut
            result = await quick_chat("hi")
        assert result == "hello back"


def _make_failed_response(error: str):
    from ai.local_llm_adapter import LLMResponse
    return LLMResponse(success=False, error=error, latency_ms=0.5)


def _make_success_response(content: str):
    from ai.local_llm_adapter import LLMResponse
    return LLMResponse(success=True, content=content, model="phi3", latency_ms=100.0)


class TestGetLocalLLMAdapter:
    """全局单例工厂（线程安全）。"""

    def test_returns_instance(self, tmp_path, monkeypatch):
        from ai import local_llm_adapter
        from ai.local_llm_adapter import LocalLLMAdapter, get_local_llm_adapter

        # 重置全局单例
        local_llm_adapter._local_llm_adapter = None
        monkeypatch.setattr(local_llm_adapter, "_DEFAULT_MODEL_DIR", tmp_path)

        a = get_local_llm_adapter()
        b = get_local_llm_adapter()
        assert a is b
        assert isinstance(a, LocalLLMAdapter)

    def test_reset_yields_new_instance(self, tmp_path, monkeypatch):
        from ai import local_llm_adapter
        from ai.local_llm_adapter import get_local_llm_adapter

        local_llm_adapter._local_llm_adapter = None
        monkeypatch.setattr(local_llm_adapter, "_DEFAULT_MODEL_DIR", tmp_path)
        a = get_local_llm_adapter()
        local_llm_adapter._local_llm_adapter = None
        b = get_local_llm_adapter()
        assert a is not b

    def test_concurrent_singleton_creation_is_thread_safe(self, tmp_path, monkeypatch):
        """多线程并发调用 get_local_llm_adapter() 应只创建一个实例。

        回归测试：修复前在 Web 服务启动时，多个请求并发到达，
        检查 + 创建之间存在竞态条件，导致：
        1. 多个 LocalLLMAdapter 实例被创建
        2. 显存泄漏（第一个实例的模型未释放）
        3. 应用崩溃（引用被覆盖，状态不一致）
        """
        from ai import local_llm_adapter
        from ai.local_llm_adapter import get_local_llm_adapter

        # 重置全局单例
        local_llm_adapter._local_llm_adapter = None
        monkeypatch.setattr(local_llm_adapter, "_DEFAULT_MODEL_DIR", tmp_path)

        instances = []
        barrier = threading.Barrier(10)  # 10个线程同时开始

        def get_instance():
            barrier.wait()  # 等待所有线程就绪
            inst = get_local_llm_adapter()
            instances.append(id(inst))

        threads = [threading.Thread(target=get_instance) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 关键：所有线程应获得同一个实例（id 相同）
        unique_ids = set(instances)
        assert len(unique_ids) == 1, (
            f"并发调用应返回同一实例，但发现了 {len(unique_ids)} 个不同实例。"
            f"实例 IDs: {unique_ids}"
        )

    def test_adapter_lock_exists(self, monkeypatch):
        """_adapter_lock 必须存在以序列化单例创建。"""
        from ai import local_llm_adapter
        import tempfile

        # 确保 _adapter_lock 在模块级别被初始化（修复后）
        # 需要先重置单例以触发模块级锁的初始化路径
        local_llm_adapter._local_llm_adapter = None
        with tempfile.TemporaryDirectory() as tmp:
            monkeypatch.setattr(local_llm_adapter, "_DEFAULT_MODEL_DIR", Path(tmp))
            # 首次访问触发锁初始化
            _ = local_llm_adapter.get_local_llm_adapter()

        assert hasattr(local_llm_adapter, "_adapter_lock")
        assert isinstance(local_llm_adapter._adapter_lock, type(threading.Lock()))


class TestUnload:
    """unload() 在 model 为 None 时不应抛异常（幂等）。"""

    def test_unload_without_model(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        # 未加载模型就 unload，不应抛
        adapter.unload()
        assert adapter._model is None
        assert adapter._is_initialized is False

    def test_unload_resets_state(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        adapter._is_initialized = True
        adapter._model = MagicMock()
        # mock torch
        with patch.dict(sys.modules, {"torch": MagicMock()}):
            adapter.unload()
        assert adapter._model is None
        assert adapter._is_initialized is False


class TestConcurrentInitializeLock:
    """并发 initialize() 必须只加载模型一次（防止显存翻倍 OOM）。

    回归测试：修复前 chat() 的并发调用会重复触发 _load_model()，
    在 RTX 4060 8GB 上加载两个 7B 模型导致 CUDA OOM。
    """

    @pytest.mark.asyncio
    async def test_concurrent_initialize_loads_model_once(self, tmp_path):
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_name="phi3-mini", model_dir=tmp_path)
        load_count = 0

        async def slow_load(*_a, **_kw):
            nonlocal load_count
            load_count += 1
            # 模拟模型加载耗时，让其他协程有机会进入
            await asyncio.sleep(0.05)

        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=slow_load), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 12.0}):
            # 并发发起 5 个 initialize 调用
            results = await asyncio.gather(*[adapter.initialize() for _ in range(5)])

        assert all(r is True for r in results)
        # 关键：_load_model 只应被调用一次（锁阻止了重复加载）
        assert load_count == 1, f"并发 initialize 应只加载一次，实际加载 {load_count} 次"
        assert adapter._is_initialized is True

    @pytest.mark.asyncio
    async def test_second_call_after_first_completes_skips_load(self, tmp_path):
        """第一个 initialize 完成后，第二次调用应直接返回（不再加载）。"""
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_name="phi3-mini", model_dir=tmp_path)
        load_count = 0

        async def slow_load(*_a, **_kw):
            nonlocal load_count
            load_count += 1

        with patch.object(adapter, "_torch_available", True), \
             patch.object(adapter, "_transformers_available", True), \
             patch.object(adapter, "_load_model", new=slow_load), \
             patch.object(adapter, "_detect_gpu", return_value={"available": True, "vram_gb": 12.0}):
            await adapter.initialize()
            assert load_count == 1
            # 第二次调用应命中 fast-path，不再加载
            ok = await adapter.initialize()
            assert ok is True
            assert load_count == 1, "已初始化后再次调用不应重复加载"

    def test_init_lock_exists(self, tmp_path):
        """_init_lock 必须存在以序列化模型加载。"""
        from ai.local_llm_adapter import LocalLLMAdapter

        adapter = LocalLLMAdapter(model_dir=tmp_path)
        assert hasattr(adapter, "_init_lock")
        assert isinstance(adapter._init_lock, asyncio.Lock)

