"""
推理服务封装 - 统一的推理接口、批量推理、性能优化
与 llm_gateway 的适配层预留
参考 Antares 哲学：高效推理，精悍够用
"""
import os
import time
import logging
from typing import Any, Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from core.torch_runtime import infer_ctx

logger = logging.getLogger(__name__)


@dataclass
class InferenceConfig:
    """推理配置"""
    model_path: str = ""
    model_type: str = "jsx_code"
    """模型类型：jsx_code, style_classify, param_optim"""
    device: str = "auto"
    """设备：auto, cpu, cuda, mps"""
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    do_sample: bool = True
    batch_size: int = 1
    """批处理大小"""
    use_cache: bool = True
    """是否使用推理缓存"""
    cache_size: int = 1000
    """缓存大小（条目数）"""
    timeout_ms: int = 30000
    """超时时间（毫秒）"""


@dataclass
class InferenceResult:
    """推理结果"""
    output: Any = None
    """输出结果"""
    latency_ms: float = 0.0
    """推理延迟（毫秒）"""
    tokens_generated: int = 0
    """生成的 token 数"""
    tokens_per_second: float = 0.0
    """生成速度（token/s）"""
    cache_hit: bool = False
    """是否命中缓存"""
    model_name: str = ""
    """使用的模型名称"""
    error: Optional[str] = None
    """错误信息（如果有）"""


class InferenceServer:
    """推理服务
    
    提供：
    - 统一的推理接口
    - 批量推理
    - 性能优化（缓存、批处理）
    - 与 llm_gateway 的适配层预留
    
    参考 Antares 哲学：高效推理，在保证效果的前提下追求最低延迟。
    """

    def __init__(self, config: InferenceConfig):
        """初始化推理服务
        
        Args:
            config: 推理配置
        """
        self.config = config
        self._model = None
        self._tokenizer = None
        self._cache: Dict[str, InferenceResult] = {}
        self._cache_order: List[str] = []
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'total_latency_ms': 0.0,
            'total_tokens': 0,
        }
        self._dependencies_available = self._check_dependencies()
        self._is_loaded = False

    def _check_dependencies(self) -> bool:
        """检查依赖库是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            import torch
            import transformers
            return True
        except ImportError:
            logger.warning("PyTorch/transformers not available, running in framework mode")
            return False

    def load_model(self) -> bool:
        """加载模型
        
        Returns:
            bool: 是否成功加载
        """
        logger.info(f"Loading model from {self.config.model_path}")
        
        if not self._dependencies_available:
            logger.warning("Dependencies not available, running in framework mode")
            self._is_loaded = True
            return True
        
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            device = self._get_device()
            
            self._tokenizer = AutoTokenizer.from_pretrained(self.config.model_path)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.config.model_path,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "auto" else device,
            )
            
            self._is_loaded = True
            logger.info("Model loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def _get_device(self) -> str:
        """获取推理设备
        
        Returns:
            str: 设备类型
        """
        if self.config.device != "auto":
            return self.config.device
        
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        
        return "cpu"

    def infer(self, prompt: str, **kwargs) -> InferenceResult:
        """执行推理
        
        Args:
            prompt: 输入提示
            **kwargs: 额外参数
            
        Returns:
            InferenceResult: 推理结果
        """
        self._stats['total_requests'] += 1
        
        cache_key = self._make_cache_key(prompt, kwargs)
        
        if self.config.use_cache and cache_key in self._cache:
            self._stats['cache_hits'] += 1
            cached = self._cache[cache_key]
            cached.cache_hit = True
            return cached
        
        start_time = time.time()
        
        if not self._is_loaded:
            if not self.load_model():
                return InferenceResult(
                    error="Failed to load model",
                    latency_ms=0.0,
                )
        
        try:
            result = self._do_infer(prompt, **kwargs)
        except Exception as e:
            logger.error(f"Inference error: {e}")
            result = InferenceResult(
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
        
        latency_ms = (time.time() - start_time) * 1000
        result.latency_ms = latency_ms
        
        self._stats['total_latency_ms'] += latency_ms
        self._stats['total_tokens'] += result.tokens_generated
        
        if result.tokens_generated > 0 and latency_ms > 0:
            result.tokens_per_second = result.tokens_generated / (latency_ms / 1000.0)
        
        if self.config.use_cache and result.error is None:
            self._update_cache(cache_key, result)
        
        return result

    def batch_infer(self, prompts: List[str], **kwargs) -> List[InferenceResult]:
        """批量推理
        
        Args:
            prompts: 提示列表
            **kwargs: 额外参数
            
        Returns:
            List[InferenceResult]: 结果列表
        """
        results = []
        
        if not prompts:
            return results
        
        if self.config.batch_size <= 1:
            for prompt in prompts:
                results.append(self.infer(prompt, **kwargs))
            return results
        
        for i in range(0, len(prompts), self.config.batch_size):
            batch = prompts[i:i + self.config.batch_size]
            batch_results = self._do_batch_infer(batch, **kwargs)
            results.extend(batch_results)
        
        return results

    def _do_infer(self, prompt: str, **kwargs) -> InferenceResult:
        """执行实际推理
        
        Args:
            prompt: 输入提示
            **kwargs: 额外参数
            
        Returns:
            InferenceResult: 推理结果
        """
        if not self._dependencies_available or self._model is None:
            return self._simulate_infer(prompt)
        
        try:
            import torch
            
            max_new_tokens = kwargs.get('max_new_tokens', self.config.max_new_tokens)
            temperature = kwargs.get('temperature', self.config.temperature)
            top_p = kwargs.get('top_p', self.config.top_p)
            do_sample = kwargs.get('do_sample', self.config.do_sample)
            
            inputs = self._tokenizer(prompt, return_tensors="pt")
            inputs = {k: v.to(self._model.device) for k, v in inputs.items()}
            
            with infer_ctx(str(self._model.device)):
                outputs = self._model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=do_sample,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            
            generated_ids = outputs[0][inputs['input_ids'].shape[1]:]
            generated_text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
            
            return InferenceResult(
                output=generated_text,
                tokens_generated=len(generated_ids),
            )
            
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            return InferenceResult(error=str(e))

    def _do_batch_infer(self, batch: List[str], **kwargs) -> List[InferenceResult]:
        """执行批量推理
        
        Args:
            batch: 批次提示
            **kwargs: 额外参数
            
        Returns:
            List[InferenceResult]: 结果列表
        """
        results = []
        
        if not self._dependencies_available or self._model is None:
            for prompt in batch:
                results.append(self._simulate_infer(prompt))
            return results
        
        try:
            import torch
            
            max_new_tokens = kwargs.get('max_new_tokens', self.config.max_new_tokens)
            temperature = kwargs.get('temperature', self.config.temperature)
            top_p = kwargs.get('top_p', self.config.top_p)
            do_sample = kwargs.get('do_sample', self.config.do_sample)
            
            tokenized = self._tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            tokenized = {k: v.to(self._model.device) for k, v in tokenized.items()}
            
            with infer_ctx(str(self._model.device)):
                outputs = self._model.generate(
                    **tokenized,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=do_sample,
                    pad_token_id=self._tokenizer.eos_token_id,
                )
            
            for i, output_ids in enumerate(outputs):
                input_len = tokenized['input_ids'][i].shape[0]
                generated_ids = output_ids[input_len:]
                generated_text = self._tokenizer.decode(generated_ids, skip_special_tokens=True)
                
                results.append(InferenceResult(
                    output=generated_text,
                    tokens_generated=len(generated_ids),
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Batch inference failed: {e}")
            return [InferenceResult(error=str(e)) for _ in batch]

    def _simulate_infer(self, prompt: str) -> InferenceResult:
        """模拟推理（框架模式）
        
        Args:
            prompt: 输入提示
            
        Returns:
            InferenceResult: 模拟结果
        """
        import time
        time.sleep(0.01)
        
        mock_output = self._get_mock_output(prompt)
        
        return InferenceResult(
            output=mock_output,
            tokens_generated=len(mock_output.split()),
        )

    def _get_mock_output(self, prompt: str) -> str:
        """获取模拟输出
        
        Args:
            prompt: 输入提示
            
        Returns:
            str: 模拟输出
        """
        if self.config.model_type == "jsx_code":
            return """var comp = app.project.activeItem;
var layer = comp.layers.addSolid([1, 1, 1], "New Layer", 1920, 1080, 1);
var effect = layer.Effects.addProperty("ADBE Gaussian Blur 2");
effect.property("ADBE Gaussian Blur 2-0001").setValue(10);"""
        elif self.config.model_type == "style_classify":
            return "cinematic"
        elif self.config.model_type == "param_optim":
            return '{"blur": 15, "opacity": 80, "scale": 100}'
        else:
            return "OK"

    def _make_cache_key(self, prompt: str, kwargs: Dict[str, Any]) -> str:
        """生成缓存键
        
        Args:
            prompt: 提示
            kwargs: 额外参数
            
        Returns:
            str: 缓存键
        """
        key_parts = [prompt]
        for k in sorted(kwargs.keys()):
            key_parts.append(f"{k}={kwargs[k]}")
        return "|".join(key_parts)

    def _update_cache(self, key: str, result: InferenceResult) -> None:
        """更新缓存
        
        Args:
            key: 缓存键
            result: 推理结果
        """
        if len(self._cache) >= self.config.cache_size:
            oldest_key = self._cache_order.pop(0)
            if oldest_key in self._cache:
                del self._cache[oldest_key]
        
        self._cache[key] = result
        self._cache_order.append(key)

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._cache_order.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = self._stats.copy()
        
        if stats['total_requests'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] / stats['total_requests']
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_requests']
        else:
            stats['avg_latency_ms'] = 0.0
            stats['cache_hit_rate'] = 0.0
        
        if stats['total_latency_ms'] > 0:
            stats['overall_tokens_per_second'] = stats['total_tokens'] / (stats['total_latency_ms'] / 1000.0)
        else:
            stats['overall_tokens_per_second'] = 0.0
        
        stats['cache_size'] = len(self._cache)
        stats['model_loaded'] = self._is_loaded
        stats['device'] = self._get_device()
        
        return stats

    def health_check(self) -> Dict[str, Any]:
        """健康检查
        
        Returns:
            Dict[str, Any]: 健康状态
        """
        return {
            'status': 'healthy' if self._is_loaded else 'unloaded',
            'model_loaded': self._is_loaded,
            'model_path': self.config.model_path,
            'model_type': self.config.model_type,
            'device': self._get_device(),
            'cache_size': len(self._cache),
        }
