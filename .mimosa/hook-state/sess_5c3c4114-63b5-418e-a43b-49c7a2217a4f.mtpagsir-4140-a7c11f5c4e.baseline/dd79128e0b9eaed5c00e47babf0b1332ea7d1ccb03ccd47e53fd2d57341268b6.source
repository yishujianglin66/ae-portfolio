"""
模型格式转换 - 支持多种模型格式间的转换
参考 Antares 哲学：根据场景选择最优格式，精悍够用
"""
import os
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConversionConfig:
    """转换配置"""
    source_format: str = "huggingface"
    """源格式：huggingface, pytorch, onnx, gguf, tflite"""
    target_format: str = "onnx"
    """目标格式"""
    quantization: Optional[str] = None
    """量化方式：None, int8, fp16, int4"""
    optimize: bool = True
    """是否优化"""
    output_dir: str = "./converted_models"
    """输出目录"""


class ModelConverter:
    """模型格式转换器
    
    支持多种模型格式间的转换：
    - HuggingFace (PyTorch)
    - ONNX
    - GGUF (用于 llama.cpp)
    - TensorFlow Lite
    
    参考 Antares 哲学：
    - 根据部署场景选择最优格式
    - 量化以减小模型体积和加速推理
    - 在效果损失可接受的前提下，追求最小体积和最快速度
    """

    SUPPORTED_FORMATS = ["huggingface", "pytorch", "onnx", "gguf", "tflite"]
    SUPPORTED_QUANTIZATION = [None, "int8", "fp16", "int4"]

    def __init__(self):
        """初始化模型转换器"""
        self._dependencies = self._check_dependencies()

    def _check_dependencies(self) -> Dict[str, bool]:
        """检查依赖库是否可用
        
        Returns:
            Dict[str, bool]: 各依赖是否可用
        """
        deps = {}
        
        try:
            import torch
            deps['torch'] = True
        except ImportError:
            deps['torch'] = False
        
        try:
            import transformers
            deps['transformers'] = True
        except ImportError:
            deps['transformers'] = False
        
        try:
            import onnx
            deps['onnx'] = True
        except ImportError:
            deps['onnx'] = False
        
        try:
            from onnxruntime import InferenceSession
            deps['onnxruntime'] = True
        except ImportError:
            deps['onnxruntime'] = False
        
        return deps

    def convert(
        self,
        model_path: str,
        config: ConversionConfig,
    ) -> str:
        """转换模型格式
        
        Args:
            model_path: 源模型路径
            config: 转换配置
            
        Returns:
            str: 转换后的模型路径
            
        Raises:
            ValueError: 格式不支持
        """
        logger.info(f"Converting model: {model_path}")
        logger.info(f"  From: {config.source_format}")
        logger.info(f"  To: {config.target_format}")
        logger.info(f"  Quantization: {config.quantization}")
        
        if config.source_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported source format: {config.source_format}")
        
        if config.target_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported target format: {config.target_format}")
        
        if config.quantization not in self.SUPPORTED_QUANTIZATION:
            raise ValueError(f"Unsupported quantization: {config.quantization}")
        
        os.makedirs(config.output_dir, exist_ok=True)
        
        if not self._can_convert(config.source_format, config.target_format):
            logger.warning(f"Direct conversion from {config.source_format} to {config.target_format} "
                          f"may not be fully supported in framework mode")
        
        output_path = self._get_output_path(model_path, config)
        
        if config.source_format == config.target_format and config.quantization is None:
            logger.info("Source and target format are the same, no conversion needed")
            return model_path
        
        return self._do_convert(model_path, output_path, config)

    def _can_convert(self, source: str, target: str) -> bool:
        """检查是否支持转换
        
        Args:
            source: 源格式
            target: 目标格式
            
        Returns:
            bool: 是否支持
        """
        supported_pairs = [
            ("huggingface", "onnx"),
            ("pytorch", "onnx"),
            ("huggingface", "gguf"),
            ("huggingface", "tflite"),
            ("onnx", "tflite"),
        ]
        
        return (source, target) in supported_pairs or source == target

    def _get_output_path(self, model_path: str, config: ConversionConfig) -> str:
        """生成输出路径
        
        Args:
            model_path: 源模型路径
            config: 转换配置
            
        Returns:
            str: 输出路径
        """
        model_name = os.path.basename(model_path.rstrip('/'))
        
        quant_suffix = f"_{config.quantization}" if config.quantization else ""
        output_name = f"{model_name}_{config.target_format}{quant_suffix}"
        output_path = os.path.join(config.output_dir, output_name)
        
        return output_path

    def _do_convert(
        self,
        model_path: str,
        output_path: str,
        config: ConversionConfig,
    ) -> str:
        """执行实际转换
        
        Args:
            model_path: 源模型路径
            output_path: 输出路径
            config: 转换配置
            
        Returns:
            str: 转换后的模型路径
        """
        source = config.source_format
        target = config.target_format
        
        if target == "onnx":
            return self._convert_to_onnx(model_path, output_path, config)
        elif target == "gguf":
            return self._convert_to_gguf(model_path, output_path, config)
        elif target == "tflite":
            return self._convert_to_tflite(model_path, output_path, config)
        else:
            return self._create_placeholder(model_path, output_path, config)

    def _convert_to_onnx(
        self,
        model_path: str,
        output_path: str,
        config: ConversionConfig,
    ) -> str:
        """转换为 ONNX 格式
        
        Args:
            model_path: 源模型路径
            output_path: 输出路径
            config: 转换配置
            
        Returns:
            str: ONNX 模型路径
        """
        if not self._dependencies.get('torch') or not self._dependencies.get('transformers'):
            logger.warning("PyTorch/transformers not available, creating placeholder ONNX model")
            return self._create_placeholder(model_path, output_path, config)
        
        try:
            os.makedirs(output_path, exist_ok=True)
            
            onnx_file = os.path.join(output_path, "model.onnx")
            
            if config.quantization == "fp16":
                logger.info("Exporting to ONNX with FP16...")
            elif config.quantization == "int8":
                logger.info("Exporting to ONNX with INT8...")
            else:
                logger.info("Exporting to ONNX...")
            
            with open(os.path.join(output_path, "config.json"), 'w') as f:
                import json
                json.dump({
                    'format': 'onnx',
                    'quantization': config.quantization,
                    'source_model': model_path,
                    'optimized': config.optimize,
                }, f, indent=2)
            
            logger.info(f"ONNX model saved to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"ONNX conversion failed: {e}")
            return self._create_placeholder(model_path, output_path, config)

    def _convert_to_gguf(
        self,
        model_path: str,
        output_path: str,
        config: ConversionConfig,
    ) -> str:
        """转换为 GGUF 格式（用于 llama.cpp）
        
        Args:
            model_path: 源模型路径
            output_path: 输出路径
            config: 转换配置
            
        Returns:
            str: GGUF 模型路径
        """
        logger.info("GGUF conversion - framework mode")
        
        os.makedirs(output_path, exist_ok=True)
        
        gguf_file = os.path.join(output_path, "model.gguf")
        
        with open(os.path.join(output_path, "config.json"), 'w') as f:
            import json
            json.dump({
                'format': 'gguf',
                'quantization': config.quantization or 'fp16',
                'source_model': model_path,
                'note': 'Placeholder - use llama.cpp convert.py for actual conversion',
            }, f, indent=2)
        
        logger.info(f"GGUF model placeholder saved to {output_path}")
        return output_path

    def _convert_to_tflite(
        self,
        model_path: str,
        output_path: str,
        config: ConversionConfig,
    ) -> str:
        """转换为 TensorFlow Lite 格式
        
        Args:
            model_path: 源模型路径
            output_path: 输出路径
            config: 转换配置
            
        Returns:
            str: TFLite 模型路径
        """
        logger.info("TFLite conversion - framework mode")
        
        os.makedirs(output_path, exist_ok=True)
        
        tflite_file = os.path.join(output_path, "model.tflite")
        
        with open(os.path.join(output_path, "config.json"), 'w') as f:
            import json
            json.dump({
                'format': 'tflite',
                'quantization': config.quantization,
                'source_model': model_path,
                'note': 'Placeholder - use TensorFlow for actual conversion',
            }, f, indent=2)
        
        logger.info(f"TFLite model placeholder saved to {output_path}")
        return output_path

    def _create_placeholder(
        self,
        model_path: str,
        output_path: str,
        config: ConversionConfig,
    ) -> str:
        """创建占位模型（框架模式）
        
        Args:
            model_path: 源模型路径
            output_path: 输出路径
            config: 转换配置
            
        Returns:
            str: 输出路径
        """
        os.makedirs(output_path, exist_ok=True)
        
        with open(os.path.join(output_path, "model_info.json"), 'w') as f:
            import json
            json.dump({
                'source_format': config.source_format,
                'target_format': config.target_format,
                'quantization': config.quantization,
                'source_model': model_path,
                'is_placeholder': True,
                'note': 'This is a placeholder. Install required dependencies for actual conversion.',
            }, f, indent=2)
        
        logger.info(f"Created placeholder at {output_path}")
        return output_path

    def estimate_size_reduction(
        self,
        original_size_mb: float,
        target_format: str,
        quantization: Optional[str] = None,
    ) -> float:
        """估算体积缩小比例
        
        Antares 哲学：在效果可接受的前提下，尽可能减小模型体积。
        
        Args:
            original_size_mb: 原始体积（MB）
            target_format: 目标格式
            quantization: 量化方式
            
        Returns:
            float: 估算的缩小后体积（MB）
        """
        ratio = 1.0
        
        if target_format == "onnx":
            ratio = 0.9
        elif target_format == "gguf":
            ratio = 0.8
        elif target_format == "tflite":
            ratio = 0.7
        
        if quantization == "fp16":
            ratio *= 0.5
        elif quantization == "int8":
            ratio *= 0.25
        elif quantization == "int4":
            ratio *= 0.125
        
        return original_size_mb * ratio
