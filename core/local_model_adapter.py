#!/usr/bin/env python3
"""
本地模型适配器 - TIER_1 本地小模型统一接口

支持的模型：
- BGE-Small-ZH (33M): 中文嵌入，适合风格分类
- BGE-M3 (568M): 多语言嵌入，适合语义检索
- Qwen2-0.5B (500M): 轻量生成，适合参数预测
- Qwen2-1.5B (1.5B): 中等生成，适合代码生成

设计原则：
1. 延迟加载：初始化时不加载模型，首次使用时加载
2. 优雅降级：如果依赖库不存在，返回错误而非崩溃
3. CPU优先：本地环境无GPU，使用CPU推理
4. 统一接口：embed()和generate()方法与云端API一致
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


class LocalModelType(Enum):
    """本地模型类型"""
    BGE_SMALL_ZH = "bge-small-zh"      # 33M 中文嵌入
    BGE_BASE_ZH = "bge-base-zh"        # 102M 中文嵌入
    BGE_M3 = "bge-m3"                   # 568M 多语言嵌入
    QWEN2_05B = "qwen2-0.5b"           # 500M 生成
    QWEN2_15B = "qwen2-1.5b"           # 1.5B 生成
    QWEN2_7B = "qwen2-7b"


class InferenceBackend(str, Enum):
    TRANSFORMERS = "transformers"
    OPENVINO = "openvino"


@dataclass
class LocalModelConfig:
    """本地模型配置"""
    model_type: LocalModelType
    model_path: str  # HuggingFace 模型ID 或本地路径
    device: str = "cpu"
    max_length: int = 512
    batch_size: int = 8
    precision: str = "fp32"  # fp32, fp16, int8
    cache_dir: Optional[str] = None
    
    trust_remote_code: bool = True
    use_fast_tokenizer: bool = True

    backend: InferenceBackend = InferenceBackend.TRANSFORMERS
    ov_compile_precision: str = "fp16"


@dataclass
class LocalModelResponse:
    """本地模型响应"""
    success: bool = True
    content: str = ""
    embeddings: Optional[List[List[float]]] = None
    latency_ms: float = 0.0
    error: str = ""
    model_type: str = ""
    tokens_used: int = 0


class LocalModelAdapter:
    """本地模型适配器 - 统一接口
    
    用法：
        adapter = LocalModelAdapter(config)
        await adapter.initialize()
        
        # 嵌入
        embeddings = await adapter.embed(["文本1", "文本2"])
        
        # 生成
        response = await adapter.generate("写一段AE脚本")
    """
    
    def __init__(self, config: LocalModelConfig):
        self.config = config
        self._model: Any = None
        self._tokenizer: Any = None
        self._initialized: bool = False
        self._init_error: Optional[str] = None
        
        # 性能统计
        self._total_calls: int = 0
        self._total_latency_ms: float = 0.0
    
    @property
    def is_embedding_model(self) -> bool:
        """是否为嵌入模型"""
        return "bge" in self.config.model_type.value.lower()
    
    @property
    def is_generation_model(self) -> bool:
        return "qwen" in self.config.model_type.value.lower()

    async def _check_openvino_ready(self) -> Tuple[bool, str]:
        try:
            def _import():
                import importlib
                importlib.import_module("optimum.intel.openvino")
                importlib.import_module("openvino")
                return True
            await asyncio.to_thread(_import)
            return True, ""
        except ImportError as e:
            missing = str(e).split("'")
            missing_name = missing[1] if len(missing) > 1 else str(e)
            return False, f"缺少依赖库: {missing_name}. 请安装: pip install optimum-intel openvino"
        except Exception as e:
            return False, f"OpenVINO 检查异常: {e}"

    def _resolve_ov_device(self) -> str:
        dev = str(self.config.device).lower()
        if dev in ("gpu", "cuda"):
            return "GPU.0"
        if dev == "npu":
            return "NPU"
        return "CPU"

    async def _initialize_openvino(self) -> None:
        try:
            ready, reason = await self._check_openvino_ready()
            if not ready:
                self._init_error = reason
                return

            def _load():
                from optimum.intel.openvino import (
                    OVModelForCausalLM,
                    OVModelForFeatureExtraction,
                )
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model_path,
                    trust_remote_code=self.config.trust_remote_code,
                    cache_dir=self.config.cache_dir,
                    use_fast=self.config.use_fast_tokenizer,
                )

                ov_device = self._resolve_ov_device()
                ov_config = {"PERFORMANCE_HINT": "LATENCY"}

                if self.is_embedding_model:
                    self._model = OVModelForFeatureExtraction.from_pretrained(
                        self.config.model_path,
                        device=ov_device,
                        ov_config=ov_config,
                        cache_dir=self.config.cache_dir,
                    )
                else:
                    load_kwargs = {
                        "device": ov_device,
                        "ov_config": ov_config,
                        "export": True,
                        "cache_dir": self.config.cache_dir,
                    }
                    if self.config.ov_compile_precision == "int8":
                        load_kwargs["load_in_8bit"] = True
                    elif self.config.ov_compile_precision == "int4":
                        try:
                            from optimum.intel.openvino import quantize
                            import tempfile
                            base_model = OVModelForCausalLM.from_pretrained(
                                self.config.model_path,
                                device=ov_device,
                                ov_config=ov_config,
                                export=True,
                                cache_dir=self.config.cache_dir,
                            )
                            tmp_dir = tempfile.mkdtemp(prefix="aekv_ov_int4_")
                            self._model = quantize(base_model, save_directory=tmp_dir)
                            logger.warning(f"OpenVINO int4 量化完成（临时目录: {tmp_dir}）")
                            return
                        except Exception as qe:
                            logger.warning(f"OpenVINO int4 量化失败: {qe}，降级到 int8")
                            load_kwargs["load_in_8bit"] = True

                    self._model = OVModelForCausalLM.from_pretrained(
                        self.config.model_path,
                        **load_kwargs,
                    )

            await asyncio.to_thread(_load)

        except Exception as e:
            self._init_error = f"OpenVINO 模型初始化异常: {e}"
            logger.error(self._init_error)

    async def _generate_openvino(self, prompt: str, **kwargs) -> LocalModelResponse:
        start_time = time.time()
        try:
            def _run():
                inputs = self._tokenizer(
                    prompt,
                    return_tensors="pt",
                    truncation=True,
                    max_length=self.config.max_length,
                )
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=kwargs.get("max_new_tokens", 100),
                    do_sample=kwargs.get("do_sample", True),
                    temperature=kwargs.get("temperature", 0.7),
                    top_p=kwargs.get("top_p", 0.9),
                    pad_token_id=self._tokenizer.eos_token_id,
                )
                return self._tokenizer.decode(
                    outputs[0][inputs["input_ids"].shape[1]:],
                    skip_special_tokens=True,
                )

            generated_text = await asyncio.to_thread(_run)
            latency = (time.time() - start_time) * 1000
            self._total_calls += 1
            self._total_latency_ms += latency

            return LocalModelResponse(
                success=True,
                content=generated_text,
                latency_ms=latency,
                model_type=self.config.model_type.value,
                tokens_used=len(self._tokenizer.encode(prompt)) + kwargs.get("max_new_tokens", 100),
            )
        except Exception as e:
            logger.error(f"OpenVINO 生成失败: {e}")
            return LocalModelResponse(
                success=False,
                error=str(e),
                model_type=self.config.model_type.value,
            )

    async def _embed_openvino(self, texts: list[str]) -> LocalModelResponse:
        start_time = time.time()
        try:
            def _run():
                all_embeddings = []
                for i in range(0, len(texts), self.config.batch_size):
                    batch = texts[i:i + self.config.batch_size]
                    inputs = self._tokenizer(
                        batch,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=self.config.max_length,
                    )
                    outputs = self._model(**inputs)
                    attention_mask = inputs["attention_mask"]
                    hidden_state = outputs.last_hidden_state
                    embedding = (
                        (hidden_state * attention_mask.unsqueeze(-1)).sum(1)
                        / attention_mask.sum(1, keepdim=True)
                    )
                    all_embeddings.extend(embedding.detach().cpu().numpy().tolist())
                return all_embeddings

            embeddings = await asyncio.to_thread(_run)
            latency = (time.time() - start_time) * 1000
            self._total_calls += 1
            self._total_latency_ms += latency

            return LocalModelResponse(
                success=True,
                embeddings=embeddings,
                latency_ms=latency,
                model_type=self.config.model_type.value,
                tokens_used=sum(len(t) for t in texts),
            )
        except Exception as e:
            logger.error(f"OpenVINO 嵌入失败: {e}")
            return LocalModelResponse(
                success=False,
                error=str(e),
                model_type=self.config.model_type.value,
            )

    async def _initialize_transformers(self) -> bool:
        if self.is_embedding_model:
            return await self._init_embedding_model()
        else:
            return await self._init_generation_model()

    async def initialize(self) -> Tuple[bool, str]:
        if self._initialized:
            return True, ""

        if self._init_error:
            return False, self._init_error

        try:
            start_time = time.time()

            if self.config.backend == InferenceBackend.OPENVINO:
                await self._initialize_openvino()
                if self._init_error:
                    return False, self._init_error
                self._initialized = True
                latency = (time.time() - start_time) * 1000
                logger.info(f"[OpenVINO] 模型 {self.config.model_type.value} 初始化完成，耗时 {latency:.0f}ms")
                return True, ""
            else:
                success = await self._initialize_transformers()
                if success:
                    self._initialized = True
                    latency = (time.time() - start_time) * 1000
                    logger.info(f"[Transformers] 模型 {self.config.model_type.value} 初始化完成，耗时 {latency:.0f}ms")
                    return True, ""
                return False, "模型初始化失败"

        except ImportError as e:
            self._init_error = f"缺少依赖库: {e}. 请安装: pip install transformers sentence-transformers torch"
            logger.warning(self._init_error)
            return False, self._init_error
        except Exception as e:
            self._init_error = f"模型初始化异常: {e}"
            logger.error(self._init_error)
            return False, self._init_error
    
    async def _init_embedding_model(self) -> bool:
        """初始化嵌入模型"""
        try:
            # 尝试使用 sentence-transformers（推荐）
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(
                    self.config.model_path,
                    device=self.config.device,
                    cache_folder=self.config.cache_dir
                )
                logger.info(f"使用 sentence-transformers 加载 {self.config.model_path}")
                return True
            except ImportError:
                pass
            
            # 降级到 transformers
            from transformers import AutoModel, AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
                cache_dir=self.config.cache_dir
            )
            self._model = AutoModel.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
                cache_dir=self.config.cache_dir
            )
            
            # 移动到指定设备
            if self.config.device != "cpu":
                self._model = self._model.to(self.config.device)
            
            logger.info(f"使用 transformers 加载 {self.config.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"嵌入模型初始化失败: {e}")
            return False
    
    async def _init_generation_model(self) -> bool:
        """初始化生成模型"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
                cache_dir=self.config.cache_dir,
                use_fast=self.config.use_fast_tokenizer
            )
            
            # 根据精度设置加载模型
            torch_dtype = torch.float32
            if self.config.precision == "fp16":
                torch_dtype = torch.float16
            elif self.config.precision == "int8":
                # int8 需要额外处理
                torch_dtype = torch.float16
            
            self._model = AutoModelForCausalLM.from_pretrained(
                self.config.model_path,
                trust_remote_code=self.config.trust_remote_code,
                cache_dir=self.config.cache_dir,
                torch_dtype=torch_dtype,
                low_cpu_mem_usage=True
            )
            
            # 移动到指定设备
            if self.config.device != "cpu":
                self._model = self._model.to(self.config.device)
            else:
                # CPU 模式下尝试优化
                self._model = self._model.eval()
            
            logger.info(f"生成模型 {self.config.model_path} 加载完成")
            return True
            
        except Exception as e:
            logger.error(f"生成模型初始化失败: {e}")
            return False
    
    async def embed(self, texts: List[str]) -> LocalModelResponse:
        """文本嵌入
        
        Args:
            texts: 待嵌入的文本列表
            
        Returns:
            LocalModelResponse: 包含 embeddings 字段
        """
        start_time = time.time()
        
        # 确保初始化
        if not self._initialized:
            success, error = await self.initialize()
            if not success:
                return LocalModelResponse(
                    success=False,
                    error=error,
                    model_type=self.config.model_type.value
                )

        if self.config.backend == InferenceBackend.OPENVINO and not self._init_error:
            return await self._embed_openvino(texts)

        try:
            embeddings: List[List[float]] = []
            
            if hasattr(self._model, 'encode'):
                # sentence-transformers
                embs = self._model.encode(
                    texts,
                    batch_size=self.config.batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True
                )
                embeddings = [e.tolist() for e in embs]
            else:
                # transformers
                import torch
                
                # 批量处理
                all_embeddings = []
                for i in range(0, len(texts), self.config.batch_size):
                    batch = texts[i:i + self.config.batch_size]
                    inputs = self._tokenizer(
                        batch,
                        return_tensors="pt",
                        padding=True,
                        truncation=True,
                        max_length=self.config.max_length
                    )
                    
                    with torch.no_grad():
                        outputs = self._model(**inputs)
                        # 使用平均池化
                        attention_mask = inputs["attention_mask"]
                        hidden_state = outputs.last_hidden_state
                        embedding = (hidden_state * attention_mask.unsqueeze(-1)).sum(1) / attention_mask.sum(1, keepdim=True)
                        all_embeddings.extend(embedding.numpy().tolist())
                
                embeddings = all_embeddings
            
            latency = (time.time() - start_time) * 1000
            self._total_calls += 1
            self._total_latency_ms += latency
            
            return LocalModelResponse(
                success=True,
                embeddings=embeddings,
                latency_ms=latency,
                model_type=self.config.model_type.value,
                tokens_used=sum(len(t) for t in texts)
            )
            
        except Exception as e:
            logger.error(f"嵌入失败: {e}")
            return LocalModelResponse(
                success=False,
                error=str(e),
                model_type=self.config.model_type.value
            )
    
    async def generate(
        self,
        prompt: str,
        max_new_tokens: int = 100,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **kwargs: Any
    ) -> LocalModelResponse:
        """文本生成
        
        Args:
            prompt: 输入提示
            max_new_tokens: 最大生成token数
            temperature: 温度参数
            top_p: top_p采样
            
        Returns:
            LocalModelResponse: 包含 content 字段
        """
        start_time = time.time()
        
        # 确保初始化
        if not self._initialized:
            success, error = await self.initialize()
            if not success:
                return LocalModelResponse(
                    success=False,
                    error=error,
                    model_type=self.config.model_type.value
                )

        if self.config.backend == InferenceBackend.OPENVINO and not self._init_error:
            return await self._generate_openvino(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                **kwargs,
            )

        try:
            import torch

            inputs = self._tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=self.config.max_length
            )
            
            with torch.no_grad():
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=temperature,
                    top_p=top_p,
                    pad_token_id=self._tokenizer.eos_token_id,
                    **kwargs
                )
            
            # 只解码新生成的部分
            generated_text = self._tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=True
            )
            
            latency = (time.time() - start_time) * 1000
            self._total_calls += 1
            self._total_latency_ms += latency
            
            return LocalModelResponse(
                success=True,
                content=generated_text,
                latency_ms=latency,
                model_type=self.config.model_type.value,
                tokens_used=len(self._tokenizer.encode(prompt)) + max_new_tokens
            )
            
        except Exception as e:
            logger.error(f"生成失败: {e}")
            return LocalModelResponse(
                success=False,
                error=str(e),
                model_type=self.config.model_type.value
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取使用统计"""
        avg_latency = (
            self._total_latency_ms / self._total_calls 
            if self._total_calls > 0 else 0
        )
        return {
            "model_type": self.config.model_type.value,
            "initialized": self._initialized,
            "total_calls": self._total_calls,
            "total_latency_ms": self._total_latency_ms,
            "avg_latency_ms": avg_latency,
            "is_embedding_model": self.is_embedding_model,
            "is_generation_model": self.is_generation_model,
            "backend": self.config.backend.value
        }
    
    def is_ready(self) -> bool:
        """检查模型是否就绪"""
        return self._initialized


class LocalModelRegistry:
    """本地模型注册中心 - 管理多个本地模型实例"""
    
    _instances: Dict[str, LocalModelAdapter] = {}
    
    @classmethod
    def register(cls, name: str, config: LocalModelConfig) -> LocalModelAdapter:
        """注册模型"""
        if name in cls._instances:
            logger.warning(f"模型 {name} 已存在，将被替换")
        
        adapter = LocalModelAdapter(config)
        cls._instances[name] = adapter
        return adapter
    
    @classmethod
    def get(cls, name: str) -> Optional[LocalModelAdapter]:
        """获取模型"""
        return cls._instances.get(name)
    
    @classmethod
    async def initialize_all(cls) -> Dict[str, Tuple[bool, str]]:
        """初始化所有模型"""
        results = {}
        for name, adapter in cls._instances.items():
            success, error = await adapter.initialize()
            results[name] = (success, error)
        return results
    
    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        """获取所有模型统计"""
        return {name: adapter.get_stats() for name, adapter in cls._instances.items()}


# 预定义的模型配置
DEFAULT_MODELS = {
    "bge-small-zh": LocalModelConfig(
        model_type=LocalModelType.BGE_SMALL_ZH,
        model_path="BAAI/bge-small-zh-v1.5",
        device="cpu",
        max_length=512,
        batch_size=16
    ),
    "qwen2-0.5b": LocalModelConfig(
        model_type=LocalModelType.QWEN2_05B,
        model_path="Qwen/Qwen2-0.5B",
        device="cpu",
        max_length=1024,
        precision="fp32"
    ),
    "qwen2-1.5b": LocalModelConfig(
        model_type=LocalModelType.QWEN2_15B,
        model_path="Qwen/Qwen2-1.5B",
        device="cpu",
        max_length=2048,
        precision="fp16"
    )
}


def get_default_model(name: str) -> Optional[LocalModelAdapter]:
    """获取预定义模型"""
    config = DEFAULT_MODELS.get(name)
    if config:
        return LocalModelAdapter(config)
    return None