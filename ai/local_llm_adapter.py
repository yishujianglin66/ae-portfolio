#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地轻量级 LLM 推理适配器
==========================

基于 NVIDIA 开源生态，为 RTX 4060 (8GB VRAM) 优化的本地推理方案：
- transformers + bitsandbytes 4-bit 量化
- 支持模型: Phi-3-mini (3.8B), Gemma-2-2B, Qwen2-7B (INT4)
- 首次使用自动下载模型
- 显存不足时自动降级到 CPU

硬件要求:
    - NVIDIA GPU (CUDA >= 11.8)
    - 显存: 4GB+ (INT4 量化), 8GB+ (推荐)
    - 内存: 16GB+

可选依赖:
    pip install torch transformers accelerate bitsandbytes

用法:
    adapter = LocalLLMAdapter()
    response = await adapter.chat("分析这段视频的情绪")
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.torch_runtime import infer_ctx

import requests

warnings.filterwarnings("ignore", message=".*torch.classes.*")
warnings.filterwarnings("ignore", message=".*CUDA.*")
warnings.filterwarnings("ignore", message=".*resume_download.*")
warnings.filterwarnings("ignore", message=".*symlinks.*")

# 禁用 HuggingFace symlink 警告
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
# 修复 NumPy + PyTorch OpenMP 冲突
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_DIR = Path(r"D:\AE-Work\models\local_llm")


class ModelSize(Enum):
    TINY = "tiny"      # <= 2B 参数
    SMALL = "small"    # 2-4B 参数
    MEDIUM = "medium"  # 7-8B 参数 (INT4)


@dataclass
class LocalModelConfig:
    """本地模型配置。"""
    model_id: str
    name: str
    size_category: ModelSize
    vram_required_gb: float
    description: str
    max_context_length: int = 4096


# 8GB VRAM 友好的模型推荐
RECOMMENDED_MODELS: Dict[str, LocalModelConfig] = {
    "phi3-mini": LocalModelConfig(
        model_id="microsoft/Phi-3-mini-4k-instruct",
        name="Phi-3 Mini",
        size_category=ModelSize.SMALL,
        vram_required_gb=2.5,
        description="微软 Phi-3 3.8B，质量优秀，速度快",
        max_context_length=4096,
    ),
    "gemma2-2b": LocalModelConfig(
        model_id="google/gemma-2-2b-it",
        name="Gemma 2 2B",
        size_category=ModelSize.TINY,
        vram_required_gb=1.8,
        description="Google Gemma 2 2B，轻量高效",
        max_context_length=8192,
    ),
    "qwen2-7b": LocalModelConfig(
        model_id="Qwen/Qwen2-7B-Instruct",
        name="Qwen2 7B",
        size_category=ModelSize.MEDIUM,
        vram_required_gb=4.5,
        description="阿里 Qwen2 7B，中文能力强",
        max_context_length=32768,
    ),
    "llama3-8b": LocalModelConfig(
        model_id="meta-llama/Meta-Llama-3-8B-Instruct",
        name="Llama 3 8B",
        size_category=ModelSize.MEDIUM,
        vram_required_gb=5.0,
        description="Meta Llama 3 8B，通用能力强",
        max_context_length=8192,
    ),
}


@dataclass
class LLMResponse:
    """LLM 推理结果。"""
    content: str = ""
    model: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0
    success: bool = False
    error: str = ""
    device: str = "cpu"  # cpu / cuda
    raw: Dict[str, Any] = field(default_factory=dict)


class LocalLLMAdapter:
    """本地轻量级 LLM 推理适配器。

    支持 transformers + bitsandbytes 4-bit 量化推理，
    自动检测 GPU 能力并选择合适的模型。
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        model_dir: Optional[Path] = None,
        device: Optional[str] = None,
    ):
        self._logger = logging.getLogger(f"{__name__}.LocalLLMAdapter")
        self.model_dir = model_dir or _DEFAULT_MODEL_DIR
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self._model_config: Optional[LocalModelConfig] = None
        self._model = None
        self._tokenizer = None
        self._device = device
        self._is_initialized = False
        self._gpu_info: Dict[str, Any] = {}
        # 防止并发 chat() 调用重复触发模型加载导致显存翻倍 OOM
        self._init_lock = asyncio.Lock()

        # 依赖检查
        self._torch_available = self._check_torch()
        self._transformers_available = self._check_transformers()
        self._bnb_available = self._check_bitsandbytes()

        if model_name:
            self._model_config = RECOMMENDED_MODELS.get(model_name)

    def _check_torch(self) -> bool:
        try:
            import torch
            self._logger.info(f"PyTorch 已安装: {torch.__version__}")
            return True
        except ImportError:
            self._logger.warning(
                "PyTorch 未安装。本地 LLM 推理不可用。"
                "运行: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
            )
            return False

    def _check_transformers(self) -> bool:
        try:
            import transformers
            self._logger.info(f"transformers 已安装: {transformers.__version__}")
            return True
        except ImportError:
            self._logger.warning(
                "transformers 未安装。本地 LLM 推理不可用。"
                "运行: pip install transformers accelerate"
            )
            return False

    def _check_bitsandbytes(self) -> bool:
        try:
            import bitsandbytes
            self._logger.info(f"bitsandbytes 已安装")
            return True
        except ImportError:
            self._logger.warning(
                "bitsandbytes 未安装。4-bit 量化不可用，将使用 8-bit 或全精度。"
                "运行: pip install bitsandbytes"
            )
            return False

    def _detect_gpu(self) -> Dict[str, Any]:
        """检测 GPU 能力。"""
        if not self._torch_available:
            return {"available": False, "vram_gb": 0}

        import torch

        if not torch.cuda.is_available():
            return {"available": False, "vram_gb": 0}

        try:
            gpu_name = torch.cuda.get_device_name(0)
            total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)

            info = {
                "available": True,
                "name": gpu_name,
                "vram_gb": round(total_vram, 1),
                "cuda_version": torch.version.cuda,
            }
            self._logger.info(f"GPU 检测: {gpu_name}, VRAM: {info['vram_gb']:.1f} GB")
            return info
        except Exception as e:
            self._logger.warning(f"GPU 检测失败: {e}")
            return {"available": False, "vram_gb": 0}

    def _auto_select_model(self) -> LocalModelConfig:
        """根据 GPU 能力自动选择模型。"""
        gpu_info = self._detect_gpu()
        vram = gpu_info.get("vram_gb", 0)

        if vram >= 8:
            # 8GB+ VRAM，可以尝试 7-8B 模型
            return RECOMMENDED_MODELS["qwen2-7b"]
        elif vram >= 4:
            # 4-8GB VRAM，使用 3-4B 模型
            return RECOMMENDED_MODELS["phi3-mini"]
        else:
            # < 4GB VRAM，使用最小模型
            return RECOMMENDED_MODELS["gemma2-2b"]

    async def initialize(self, model_name: Optional[str] = None) -> bool:
        """初始化本地 LLM 推理引擎。

        Args:
            model_name: 模型名称，None=自动选择

        Returns:
            是否初始化成功
        """
        if self._is_initialized:
            return True

        if not self._torch_available or not self._transformers_available:
            self._logger.error("缺少必要依赖，无法初始化本地 LLM")
            return False

        # 加锁防止并发 chat() 调用重复加载模型导致显存翻倍 OOM
        async with self._init_lock:
            # 双重检查：另一协程可能在等待锁期间已完成加载
            if self._is_initialized:
                return True

            # 选择模型
            if model_name and model_name in RECOMMENDED_MODELS:
                self._model_config = RECOMMENDED_MODELS[model_name]
            elif self._model_config is None:
                self._model_config = self._auto_select_model()

            self._gpu_info = self._detect_gpu()

            # 检查显存是否足够
            if self._gpu_info["available"] and self._gpu_info["vram_gb"] < self._model_config.vram_required_gb:
                self._logger.warning(
                    f"显存不足: 需要 {self._model_config.vram_required_gb}GB, "
                    f"可用 {self._gpu_info['vram_gb']:.1f}GB。将使用 CPU 或更小模型。"
                )
                # 降级到更小的模型
                if self._model_config.size_category != ModelSize.TINY:
                    self._logger.info("自动降级到 Gemma 2 2B")
                    self._model_config = RECOMMENDED_MODELS["gemma2-2b"]

            self._logger.info(
                f"初始化模型: {self._model_config.name} "
                f"({self._model_config.model_id})"
            )

            try:
                await self._load_model()
                self._is_initialized = True
                return True
            except Exception as e:
                self._logger.error(f"模型加载失败: {e}")
                return False

    async def _load_model(self) -> None:
        """加载模型到内存/GPU。"""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        model_id = self._model_config.model_id
        cache_dir = str(self.model_dir)

        # 设备选择
        if self._device:
            device = self._device
        elif self._gpu_info.get("available", False):
            device = "cuda:0"
        else:
            device = "cpu"

        self._logger.info(f"使用设备: {device}")

        # 量化配置
        if self._bnb_available and device.startswith("cuda"):
            # 4-bit 量化
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            torch_dtype = torch.float16
            self._logger.info("使用 4-bit 量化 (NF4)")
        elif device.startswith("cuda"):
            # 8-bit 量化（如果没有 bitsandbytes）
            torch_dtype = torch.float16
            quantization_config = None
            self._logger.info("使用 8-bit 量化")
        else:
            # CPU 模式
            torch_dtype = torch.float32
            quantization_config = None
            self._logger.info("使用 CPU 推理 (FP32)")

        # 加载 tokenizer
        self._logger.info("加载 tokenizer...")
        self._tokenizer = await asyncio.to_thread(
            AutoTokenizer.from_pretrained,
            model_id,
            cache_dir=cache_dir,
            trust_remote_code=True,
        )

        # 加载模型
        self._logger.info("加载模型权重...")
        load_kwargs = {
            "pretrained_model_name_or_path": model_id,
            "cache_dir": cache_dir,
            "torch_dtype": torch_dtype,
            "trust_remote_code": True,
            "device_map": "auto" if device.startswith("cuda") else None,
            "attn_implementation": "eager",  # 避免 flash-attention 依赖
        }

        if quantization_config:
            load_kwargs["quantization_config"] = quantization_config
        elif device == "cpu":
            load_kwargs["low_cpu_mem_usage"] = True

        self._model = await asyncio.to_thread(
            AutoModelForCausalLM.from_pretrained,
            **load_kwargs,
        )

        if device == "cpu":
            self._model = self._model.to("cpu")

        self._device = device
        self._logger.info(f"模型加载完成，设备: {device}")

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs,
    ) -> LLMResponse:
        """执行聊天推理。

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词
            temperature: 采样温度
            max_tokens: 最大输出 token 数

        Returns:
            LLMResponse 推理结果
        """
        start_time = time.time()

        if not self._is_initialized:
            success = await self.initialize()
            if not success:
                return LLMResponse(
                    success=False,
                    error="本地 LLM 初始化失败",
                )

        try:
            import torch

            # 构建消息
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            # 应用聊天模板
            input_text = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

            # 编码输入
            inputs = self._tokenizer(
                input_text,
                return_tensors="pt",
                padding=True,
            )

            if self._device.startswith("cuda"):
                inputs = {k: v.to(self._device) for k, v in inputs.items()}
            else:
                inputs = {k: v.to("cpu") for k, v in inputs.items()}

            # 生成参数
            gen_kwargs = {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "do_sample": temperature > 0.1,
                "top_p": kwargs.get("top_p", 0.9),
                "pad_token_id": self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
            }

            if kwargs.get("stream"):
                gen_kwargs["streamer"] = kwargs.get("streamer")

            # 推理
            with infer_ctx():
                outputs = await asyncio.to_thread(
                    self._model.generate,
                    **inputs,
                    **gen_kwargs,
                )

            # 解码输出
            input_length = inputs["input_ids"].shape[1]
            output_tokens = outputs[0][input_length:]
            response_text = self._tokenizer.decode(
                output_tokens,
                skip_special_tokens=True,
            )

            latency_ms = (time.time() - start_time) * 1000

            return LLMResponse(
                content=response_text.strip(),
                model=self._model_config.name if self._model_config else "unknown",
                tokens_input=input_length,
                tokens_output=len(output_tokens),
                latency_ms=latency_ms,
                success=True,
                device=self._device,
            )

        except Exception as e:
            self._logger.error(f"推理失败: {e}")
            return LLMResponse(
                success=False,
                error=f"推理失败: {str(e)[:500]}",
                latency_ms=(time.time() - start_time) * 1000,
            )

    async def batch_chat(
        self,
        prompts: List[str],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> List[LLMResponse]:
        """批量推理。

        Args:
            prompts: 提示词列表
            system_prompt: 系统提示词
            temperature: 采样温度
            max_tokens: 最大输出 token 数

        Returns:
            LLMResponse 列表
        """
        results = []
        for prompt in prompts:
            result = await self.chat(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            results.append(result)
        return results

    def get_info(self) -> Dict[str, Any]:
        """获取适配器信息。"""
        return {
            "initialized": self._is_initialized,
            "torch_available": self._torch_available,
            "transformers_available": self._transformers_available,
            "bnb_available": self._bnb_available,
            "gpu_info": self._gpu_info,
            "current_model": {
                "name": self._model_config.name if self._model_config else None,
                "id": self._model_config.model_id if self._model_config else None,
                "vram_required_gb": self._model_config.vram_required_gb if self._model_config else 0,
            } if self._model_config else None,
            "available_models": [
                {
                    "key": key,
                    "name": cfg.name,
                    "vram_required_gb": cfg.vram_required_gb,
                    "description": cfg.description,
                }
                for key, cfg in RECOMMENDED_MODELS.items()
            ],
        }

    def unload(self) -> None:
        """卸载模型释放显存。"""
        if self._model is not None:
            import torch
            del self._model
            self._model = None
            torch.cuda.empty_cache()
            self._logger.info("模型已卸载，显存已释放")
        self._is_initialized = False


# ========== 便捷函数 ==========

async def quick_chat(
    prompt: str,
    model_name: Optional[str] = None,
    system_prompt: str = "",
    **kwargs,
) -> str:
    """快速聊天（一行代码）。

    Args:
        prompt: 用户输入
        model_name: 模型名称
        system_prompt: 系统提示词

    Returns:
        模型回复文本
    """
    adapter = LocalLLMAdapter(model_name=model_name)
    response = await adapter.chat(prompt, system_prompt=system_prompt, **kwargs)
    if response.success:
        return response.content
    return f"[错误] {response.error}"


# 全局单例（线程安全）
_local_llm_adapter: Optional[LocalLLMAdapter] = None
_adapter_lock = threading.Lock()


def get_local_llm_adapter() -> LocalLLMAdapter:
    """获取全局本地 LLM 适配器实例（线程安全）。"""
    global _local_llm_adapter
    if _local_llm_adapter is None:
        with _adapter_lock:
            # 双重检查：另一线程可能在等待锁期间已完成创建
            if _local_llm_adapter is None:
                _local_llm_adapter = LocalLLMAdapter()
    return _local_llm_adapter
