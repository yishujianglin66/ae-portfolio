"""
训练器模块 - 支持 LoRA 微调和全量微调
参考 Antares 哲学：小模型、精调、垂直场景
"""

from .trainer_base import BaseTrainer, TrainingConfig, TrainingResult
from .lora_trainer import LoRATrainer
from .full_finetune_trainer import FullFinetuneTrainer

__all__ = [
    "BaseTrainer", "TrainingConfig", "TrainingResult",
    "LoRATrainer", "FullFinetuneTrainer",
]
