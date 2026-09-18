"""
AE Knowledge Vault - 垂直小模型训练框架
参考思科 Antares "精悍够用" 哲学：用最小参数量在垂直场景达到甚至超越大模型效果

模块结构：
- training: 训练器（LoRA微调、全量微调）
- data: 数据集与数据准备
- evaluation: 评估器与基准测试
- deployment: 模型注册、转换、推理服务
- configs: 各模型配置
- utils: 工具函数（指标、分词器、回调）
"""

from .configs.jsx_code_config import JSXCodeConfig
from .configs.param_optim_config import ParamOptimConfig
from .configs.style_classify_config import StyleClassifyConfig
from .data.data_preparator import DataPreparator
from .data.dataset_base import BaseDataset, DatasetConfig
from .data.jsx_code_dataset import JSXCodeDataset
from .data.style_classify_dataset import StyleClassifyDataset
from .deployment.inference_server import InferenceServer
from .deployment.model_converter import ModelConverter
from .deployment.model_registry import ModelInfo, ModelRegistry
from .evaluation.benchmark import BenchmarkResult, BenchmarkSuite
from .evaluation.evaluator_base import BaseEvaluator, EvaluationResult
from .evaluation.jsx_code_evaluator import JSXCodeEvaluator
from .evaluation.style_classify_evaluator import StyleClassifyEvaluator
from .training.full_finetune_trainer import FullFinetuneTrainer
from .training.jsx_code_trainer import JSXCodeTrainer, JSXCodeTrainingConfig
from .training.lora_trainer import LoRATrainer
from .training.trainer_base import BaseTrainer, TrainingConfig, TrainingResult
from .utils.metrics import (
    accuracy,
    bleu_score,
    code_bleu_score,
    cost_effectiveness_ratio,
    count_parameters,
    f1_score,
    inference_benchmark,
    precision,
    recall,
)
from .utils.tokenizer_utils import TokenizerUtils
from .utils.training_callbacks import (
    CheckpointCallback,
    EarlyStoppingCallback,
    LoggingCallback,
    MetricsCallback,
    TrainingCallback,
)

__all__ = [
    "BaseTrainer", "TrainingConfig", "TrainingResult",
    "LoRATrainer", "FullFinetuneTrainer", "JSXCodeTrainer", "JSXCodeTrainingConfig",
    "BaseDataset", "DatasetConfig",
    "JSXCodeDataset", "StyleClassifyDataset", "DataPreparator",
    "BaseEvaluator", "EvaluationResult",
    "JSXCodeEvaluator", "StyleClassifyEvaluator",
    "BenchmarkSuite", "BenchmarkResult",
    "ModelRegistry", "ModelInfo",
    "ModelConverter", "InferenceServer",
    "JSXCodeConfig", "StyleClassifyConfig", "ParamOptimConfig",
    "accuracy", "precision", "recall", "f1_score",
    "bleu_score", "code_bleu_score",
    "count_parameters", "inference_benchmark",
    "cost_effectiveness_ratio",
    "TokenizerUtils",
    "TrainingCallback", "LoggingCallback", "EarlyStoppingCallback",
    "CheckpointCallback", "MetricsCallback",
]

__version__ = "1.0.0"
