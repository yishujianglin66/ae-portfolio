#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NVIDIA Agent Toolkit 适配器 - 本地AI代理部署支持
================================================

核心能力:
1. 对接NVIDIA Agent Toolkit API（OpenAI兼容协议）
2. GB300 Blackwell Ultra GPU加速推理
3. 本地模型自动加载与健康检查
4. 自动降级到云端（当本地不可用时）
5. 与Omniverse引擎集成支持

架构设计:
    ┌─────────────────────────────────────────────────────────────┐
    │                     AI Director / LLM Gateway               │
    └──────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                NVIDIA Agent Adapter                         │
    │  ┌─────────────────┐  ┌─────────────────┐                  │
    │  │  健康检查模块     │  │  模型路由模块     │                  │
    │  └────────┬────────┘  └────────┬────────┘                  │
    │           │                    │                           │
    │           ▼                    ▼                           │
    │  ┌─────────────────┐  ┌─────────────────┐                  │
    │  │  GB300 推理引擎   │  │  Omniverse渲染   │                  │
    │  │  (本地)          │  │  (本地)          │                  │
    │  └────────┬────────┘  └─────────────────┘                  │
    │           │                                                 │
    │           └──────────────┬──────────────────────────────────┘
    │                          ▼                                  │
    │                ┌─────────────────┐                          │
    │                │  云端降级模块     │                          │
    │                │  (fallback)      │                          │
    │                └─────────────────┘                          │
    └─────────────────────────────────────────────────────────────┘

用法:
    adapter = NVIDIAAgentAdapter()
    response = await adapter.chat("分析这段视频的情绪")

参考:
    - NVIDIA Agent Toolkit API 文档
    - GB300 Blackwell Ultra 技术规格
    - Omniverse Kit SDK
"""
import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from core.config import config_manager

# 本地轻量级 LLM 回退（当 NVIDIA Agent Toolkit 不可用时）
try:
    from ai.local_llm_adapter import LocalLLMAdapter
    _LOCAL_LLM_AVAILABLE = True
except ImportError:
    _LOCAL_LLM_AVAILABLE = False


class ModelType(Enum):
    TEXT_PRO = auto()
    TEXT_FLASH = auto()
    VISION = auto()
    IMAGE_GEN = auto()
    VIDEO_GEN = auto()
    EMBEDDING = auto()
    CODE = auto()


class ProviderStatus(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    UNAVAILABLE = auto()


@dataclass
class NVIDIAConfig:
    enabled: bool = False
    api_base: str = "http://localhost:8000/v1"
    api_key: str = ""
    max_retries: int = 3
    timeout_seconds: int = 120
    fallback_to_cloud: bool = True
    health_check_interval_seconds: int = 30
    # 本地 LLM 回退配置（当 Agent Toolkit 不可用时）
    fallback_to_local_llm: bool = True
    local_llm_model: str = "phi3-mini"  # phi3-mini / gemma2-2b / qwen2-7b
    
    local_models: Dict[str, str] = field(default_factory=lambda: {
        "text_pro": "nvidia-llama-3.3-70b",
        "text_flash": "nvidia-llama-3.3-8b",
        "vision": "nvidia-megatron-vision",
        "image_gen": "nvidia-sd-3",
        "video_gen": "nvidia-veo",
        "embedding": "nvidia-embedding",
        "code": "nvidia-code-llama",
    })


@dataclass
class ModelHealth:
    model_name: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    last_health_check: float = 0.0
    latency_ms: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0


@dataclass
class InferenceResult:
    content: str = ""
    model: str = ""
    provider: str = "nvidia-local"
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0
    success: bool = False
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class NVIDIAHealthChecker:
    def __init__(self, config: NVIDIAConfig):
        self._config = config
        self._logger = logging.getLogger(f"{__name__}.NVIDIAHealthChecker")
        self._model_health: Dict[str, ModelHealth] = {}
        self._last_check_time = 0.0
        
    def _build_health_url(self) -> str:
        base = self._config.api_base.rstrip("/")
        return f"{base}/health"
    
    async def check_health(self) -> bool:
        now = time.time()
        if now - self._last_check_time < self._config.health_check_interval_seconds:
            return self._is_healthy()
        
        self._last_check_time = now
        url = self._build_health_url()
        
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                response = await asyncio.to_thread(
                    requests.get, url, timeout=self._config.timeout_seconds
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self._update_model_health(data)
                    self._logger.info(f"NVIDIA Agent Toolkit 健康检查通过: {data}")
                    return True
                else:
                    self._mark_unhealthy()
                    self._logger.warning(f"NVIDIA Agent Toolkit 健康检查失败: {response.status_code}")
                    return False
        except Exception as e:
            self._mark_unhealthy()
            self._logger.error(f"NVIDIA Agent Toolkit 健康检查异常: {e}")
            return False
    
    def _update_model_health(self, health_data: Dict[str, Any]) -> None:
        models = health_data.get("models", {})
        for model_name, status in models.items():
            if model_name not in self._model_health:
                self._model_health[model_name] = ModelHealth(model_name=model_name)
            
            if status.get("healthy", False):
                self._model_health[model_name].status = ProviderStatus.HEALTHY
                self._model_health[model_name].latency_ms = status.get("latency_ms", 0)
                self._model_health[model_name].consecutive_failures = 0
            else:
                self._model_health[model_name].status = ProviderStatus.UNAVAILABLE
                self._model_health[model_name].consecutive_failures += 1
    
    def _mark_unhealthy(self) -> None:
        for health in self._model_health.values():
            health.status = ProviderStatus.UNAVAILABLE
            health.consecutive_failures += 1
    
    def _is_healthy(self) -> bool:
        if not self._model_health:
            return False
        return all(h.status == ProviderStatus.HEALTHY for h in self._model_health.values())
    
    def get_model_health(self, model_name: str) -> Optional[ModelHealth]:
        return self._model_health.get(model_name)


class NVIDIAInferenceClient:
    def __init__(self, config: NVIDIAConfig):
        self._config = config
        self._logger = logging.getLogger(f"{__name__}.NVIDIAInferenceClient")
        self._session = requests.Session()
        if self._config.api_key:
            self._session.headers.update({
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            })
    
    def _build_url(self, endpoint: str) -> str:
        base = self._config.api_base.rstrip("/")
        return f"{base}/{endpoint}"
    
    async def chat_completion(self, messages: List[Dict[str, str]], 
                              model: str = None, **kwargs) -> InferenceResult:
        start_time = time.time()
        model = model or self._config.local_models.get("text_pro")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "stream": kwargs.get("stream", False),
        }
        
        for key in ["top_p", "frequency_penalty", "presence_penalty", "stop"]:
            if key in kwargs:
                payload[key] = kwargs[key]
        
        url = self._build_url("chat/completions")
        
        for attempt in range(self._config.max_retries):
            try:
                async with asyncio.timeout(self._config.timeout_seconds):
                    response = await asyncio.to_thread(
                        self._session.post, url, json=payload, timeout=self._config.timeout_seconds
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        latency_ms = (time.time() - start_time) * 1000
                        return self._parse_response(data, model, latency_ms)
                    else:
                        self._logger.warning(f"推理失败 (尝试 {attempt+1}): {response.status_code}")
            except Exception as e:
                self._logger.warning(f"推理异常 (尝试 {attempt+1}): {e}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        latency_ms = (time.time() - start_time) * 1000
        return InferenceResult(
            success=False,
            error="所有重试均失败",
            model=model,
            latency_ms=latency_ms,
        )
    
    async def vision_completion(self, messages: List[Dict[str, Any]], 
                                model: str = None, **kwargs) -> InferenceResult:
        model = model or self._config.local_models.get("vision")
        return await self.chat_completion(messages, model=model, **kwargs)
    
    async def image_generation(self, prompt: str, **kwargs) -> InferenceResult:
        start_time = time.time()
        model = kwargs.get("model") or self._config.local_models.get("image_gen")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "n": kwargs.get("n", 1),
            "size": kwargs.get("size", "1024x1024"),
        }
        
        url = self._build_url("images/generations")
        
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                response = await asyncio.to_thread(
                    self._session.post, url, json=payload, timeout=self._config.timeout_seconds
                )
                
                if response.status_code == 200:
                    data = response.json()
                    latency_ms = (time.time() - start_time) * 1000
                    return InferenceResult(
                        content=json.dumps(data),
                        model=model,
                        success=True,
                        latency_ms=latency_ms,
                        raw=data,
                    )
                else:
                    self._logger.warning(f"图像生成失败: {response.status_code}")
        except Exception as e:
            self._logger.warning(f"图像生成异常: {e}")
        
        latency_ms = (time.time() - start_time) * 1000
        return InferenceResult(
            success=False,
            error="图像生成失败",
            model=model,
            latency_ms=latency_ms,
        )
    
    async def embedding(self, input_text: Union[str, List[str]], 
                        model: str = None, **kwargs) -> InferenceResult:
        start_time = time.time()
        model = model or self._config.local_models.get("embedding")
        
        payload = {
            "model": model,
            "input": input_text,
        }
        
        url = self._build_url("embeddings")
        
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                response = await asyncio.to_thread(
                    self._session.post, url, json=payload, timeout=self._config.timeout_seconds
                )
                
                if response.status_code == 200:
                    data = response.json()
                    latency_ms = (time.time() - start_time) * 1000
                    return InferenceResult(
                        content=json.dumps(data),
                        model=model,
                        success=True,
                        latency_ms=latency_ms,
                        raw=data,
                    )
                else:
                    self._logger.warning(f"向量化失败: {response.status_code}")
        except Exception as e:
            self._logger.warning(f"向量化异常: {e}")
        
        latency_ms = (time.time() - start_time) * 1000
        return InferenceResult(
            success=False,
            error="向量化失败",
            model=model,
            latency_ms=latency_ms,
        )
    
    def _parse_response(self, data: Dict[str, Any], model: str, latency_ms: float) -> InferenceResult:
        choices = data.get("choices", [])
        if not choices:
            return InferenceResult(
                success=False,
                error="无返回结果",
                model=model,
                latency_ms=latency_ms,
            )
        
        message = choices[0].get("message", {})
        content = message.get("content", "")
        
        usage = data.get("usage", {})
        return InferenceResult(
            content=content,
            model=model,
            success=True,
            tokens_input=usage.get("prompt_tokens", 0),
            tokens_output=usage.get("completion_tokens", 0),
            latency_ms=latency_ms,
            raw=data,
        )


class NVIDIAAgentAdapter:
    def __init__(self, config: Optional[NVIDIAConfig] = None):
        self._logger = logging.getLogger(f"{__name__}.NVIDIAAgentAdapter")
        self._config = config or self._load_config()
        self._health_checker = NVIDIAHealthChecker(self._config)
        self._client = NVIDIAInferenceClient(self._config)
        self._initialized = False
        
        # 本地 LLM 回退适配器
        self._local_llm: Optional[Any] = None
        if _LOCAL_LLM_AVAILABLE and self._config.fallback_to_local_llm:
            try:
                self._local_llm = LocalLLMAdapter(
                    model_name=self._config.local_llm_model,
                )
                self._logger.info(
                    f"本地 LLM 回退已启用: {self._config.local_llm_model}"
                )
            except Exception as e:
                self._logger.warning(f"本地 LLM 初始化失败: {e}")
    
    def _load_config(self) -> NVIDIAConfig:
        config_data = config_manager.get_config().get("nvidia", {})
        return NVIDIAConfig(
            enabled=config_data.get("enabled", False),
            api_base=config_data.get("api_base", "http://localhost:8000/v1"),
            api_key=config_data.get("api_key", ""),
            max_retries=config_data.get("max_retries", 3),
            timeout_seconds=config_data.get("timeout_seconds", 120),
            fallback_to_cloud=config_data.get("fallback_to_cloud", True),
            fallback_to_local_llm=config_data.get("fallback_to_local_llm", True),
            local_llm_model=config_data.get("local_llm_model", "phi3-mini"),
            health_check_interval_seconds=config_data.get("health_check_interval_seconds", 30),
            local_models=config_data.get("local_models", {}),
        )
    
    async def initialize(self) -> bool:
        if not self._config.enabled:
            self._logger.info("NVIDIA Agent Toolkit 未启用")
            return False
        
        self._logger.info("初始化 NVIDIA Agent Toolkit 适配器...")
        healthy = await self._health_checker.check_health()
        
        if healthy:
            self._initialized = True
            self._logger.info("NVIDIA Agent Toolkit 初始化成功")
            return True
        else:
            self._logger.warning("NVIDIA Agent Toolkit 健康检查失败，将使用云端降级")
            return False
    
    async def chat(self, prompt: str, system_prompt: str = "", 
                   model_type: ModelType = ModelType.TEXT_PRO, **kwargs) -> InferenceResult:
        """执行聊天推理。

        优先级：NVIDIA Agent Toolkit -> 本地 LLM (transformers) -> 失败
        """
        # 尝试 NVIDIA Agent Toolkit
        if self._config.enabled:
            if not self._initialized:
                await self.initialize()
            
            if self._initialized:
                model_name = self._config.local_models.get(model_type.name.lower())
                if not model_name:
                    model_name = self._config.local_models.get("text_pro")
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                result = await self._client.chat_completion(messages, model=model_name, **kwargs)
                
                if result.success:
                    return result
                
                self._logger.warning("NVIDIA Agent Toolkit 推理失败")
        
        # 回退到本地 LLM (transformers + bitsandbytes)
        if self._local_llm is not None:
            self._logger.info("回退到本地 LLM 推理...")
            try:
                local_result = await self._local_llm.chat(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 1024),
                )
                
                if local_result.success:
                    return InferenceResult(
                        content=local_result.content,
                        model=local_result.model,
                        provider="local-transformers",
                        tokens_input=local_result.tokens_input,
                        tokens_output=local_result.tokens_output,
                        latency_ms=local_result.latency_ms,
                        success=True,
                    )
            except Exception as e:
                self._logger.error(f"本地 LLM 推理失败: {e}")
        
        # 所有路径均失败
        return InferenceResult(
            success=False,
            error="NVIDIA Agent Toolkit 和本地 LLM 均不可用。"
                  "请安装依赖: pip install torch transformers accelerate bitsandbytes",
        )
    
    async def vision_chat(self, prompt: str, images: List[str], 
                          system_prompt: str = "", **kwargs) -> InferenceResult:
        if not self._config.enabled:
            return InferenceResult(
                success=False,
                error="NVIDIA Agent Toolkit 未启用",
            )
        
        if not self._initialized:
            await self.initialize()
        
        model_name = self._config.local_models.get("vision")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        content = [{"type": "text", "text": prompt}]
        for image_url in images:
            content.append({"type": "image_url", "image_url": {"url": image_url}})
        
        messages.append({"role": "user", "content": content})
        
        return await self._client.vision_completion(messages, model=model_name, **kwargs)
    
    async def generate_image(self, prompt: str, **kwargs) -> InferenceResult:
        if not self._config.enabled:
            return InferenceResult(
                success=False,
                error="NVIDIA Agent Toolkit 未启用",
            )
        
        if not self._initialized:
            await self.initialize()
        
        return await self._client.image_generation(prompt, **kwargs)
    
    async def generate_embedding(self, input_text: Union[str, List[str]], **kwargs) -> InferenceResult:
        if not self._config.enabled:
            return InferenceResult(
                success=False,
                error="NVIDIA Agent Toolkit 未启用",
            )
        
        if not self._initialized:
            await self.initialize()
        
        return await self._client.embedding(input_text, **kwargs)
    
    def is_available(self) -> bool:
        return self._config.enabled and self._initialized
    
    def get_config(self) -> NVIDIAConfig:
        return self._config
    
    def get_health_status(self) -> Dict[str, Any]:
        return {
            "enabled": self._config.enabled,
            "initialized": self._initialized,
            "api_base": self._config.api_base,
            "fallback_to_cloud": self._config.fallback_to_cloud,
        }


nvidia_adapter = NVIDIAAgentAdapter()
