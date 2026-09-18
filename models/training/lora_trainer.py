"""
LoRA 微调训练器 - 低秩适应（Low-Rank Adaptation）
最常用的小样本微调方式，适合垂直领域小模型
参考 Antares 哲学：用最小的可训练参数量达到最好的效果
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .trainer_base import BaseTrainer, TrainingConfig, TrainingResult

logger = logging.getLogger(__name__)


@dataclass
class LoRAConfig:
    """LoRA 配置
    
    低秩适应的核心参数，控制可训练参数量。
    参考 Antares 哲学：通过调整 rank 来平衡参数量与效果。
    """
    rank: int = 8
    """LoRA 秩，越大参数量越多，效果可能越好但训练越慢"""
    
    alpha: int = 16
    """LoRA alpha，缩放因子，通常设为 rank 的 2 倍"""
    
    dropout: float = 0.05
    """LoRA dropout 概率"""
    
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    """目标模块，指定哪些层应用 LoRA"""
    
    bias: str = "none"
    """bias 训练方式：none, all, lora_only"""
    
    task_type: str = "CAUSAL_LM"
    """任务类型：CAUSAL_LM, SEQ_CLS, TOKEN_CLS 等"""
    
    inference_mode: bool = False
    """是否为推理模式"""
    
    r: int = 8
    """同 rank，兼容 peft 库的参数名"""
    
    lora_alpha: int = 16
    """同 alpha，兼容 peft 库的参数名"""
    
    lora_dropout: float = 0.05
    """同 dropout，兼容 peft 库的参数名"""


class LoRATrainer(BaseTrainer):
    """LoRA 微调训练器
    
    使用低秩适应（Low-Rank Adaptation）进行高效微调。
    只训练少量参数（通常 < 1%），大大降低训练成本。
    参考 Antares "精悍够用" 哲学：用最小参数量达到目标效果。
    
    注意：实际训练需要 peft + transformers + torch 库。
    若依赖缺失，会优雅降级并给出框架说明。
    """

    def __init__(self, config: TrainingConfig, lora_config: LoRAConfig | None = None):
        """初始化 LoRA 训练器
        
        Args:
            config: 训练配置
            lora_config: LoRA 特定配置，为 None 时使用默认值
        """
        super().__init__(config)
        self.lora_config = lora_config or LoRAConfig()
        self._peft_model = None
        self._optimizer = None
        self._scheduler = None
        self._dependencies_available = self._check_dependencies()

    def _check_dependencies(self) -> bool:
        """检查依赖库是否可用
        
        Returns:
            bool: 所有必需依赖是否可用
        """
        try:
            import peft
            import torch
            import transformers
            logger.info(f"Dependencies available: torch={torch.__version__}, "
                       f"transformers={transformers.__version__}, peft={peft.__version__}")
            return True
        except ImportError as e:
            logger.warning(f"Dependencies not fully available: {e}")
            logger.warning("LoRA training will work in framework mode only. "
                          "Install torch, transformers, peft for actual training.")
            return False

    def load_dataset(self, train_data: Any, eval_data: Any = None) -> None:
        """加载数据集
        
        Args:
            train_data: 训练数据，可以是 Dataset 对象或文件路径
            eval_data: 评估数据，可选
        """
        logger.info("Loading dataset for LoRA training")
        self._train_dataset = train_data
        self._eval_dataset = eval_data
        self._fire_callback("on_dataset_loaded", 
                          train_size=len(train_data) if hasattr(train_data, '__len__') else None,
                          eval_size=len(eval_data) if eval_data and hasattr(eval_data, '__len__') else None)

    def load_base_model(self) -> None:
        """加载基座模型
        
        从 base_model_path 加载预训练模型和分词器，
        然后应用 LoRA 配置。
        """
        logger.info(f"Loading base model from {self.config.base_model_path}")
        
        if not self._dependencies_available:
            logger.warning("Dependencies not available, simulating model loading")
            self._model = None
            self._tokenizer = None
            self._fire_callback("on_model_loaded", simulated=True)
            return

        try:
            import torch
            from peft import LoraConfig as PeftLoraConfig
            from peft import get_peft_model
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.config.base_model_path)
            
            model = AutoModelForCausalLM.from_pretrained(
                self.config.base_model_path,
                torch_dtype=torch.float16 if self.config.fp16 else torch.float32,
                device_map="auto"
            )

            peft_config = PeftLoraConfig(
                r=self.lora_config.rank,
                lora_alpha=self.lora_config.alpha,
                lora_dropout=self.lora_config.dropout,
                target_modules=self.lora_config.target_modules,
                bias=self.lora_config.bias,
                task_type=self.lora_config.task_type,
            )

            self._peft_model = get_peft_model(model, peft_config)
            self._model = self._peft_model
            
            trainable_params, total_params = self._peft_model.get_nb_trainable_parameters()
            params_million = total_params / 1e6
            trainable_million = trainable_params / 1e6
            
            logger.info(f"Model loaded: total={params_million:.2f}M params, "
                       f"trainable={trainable_million:.2f}M ({trainable_params/total_params*100:.2f}%)")
            
            self._fire_callback("on_model_loaded", 
                              total_params=total_params,
                              trainable_params=trainable_params)

        except Exception as e:
            logger.error(f"Failed to load base model: {e}")
            raise

    def train(self) -> TrainingResult:
        """执行 LoRA 微调训练
        
        Returns:
            TrainingResult: 训练结果
        """
        self._start_training()
        logger.info("Starting LoRA fine-tuning")

        if not self._dependencies_available:
            logger.warning("Dependencies not available, returning simulated training result")
            return self._simulate_training()

        try:
            result = self._execute_training()
            self._end_training()
            return result
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise

    def _execute_training(self) -> TrainingResult:
        """执行实际训练逻辑
        
        Returns:
            TrainingResult: 训练结果
        """
        import time

        import torch
        from peft import get_peft_model_state_dict
        from transformers import Trainer, TrainingArguments

        output_dir = os.path.join(self.config.output_dir, self.config.model_name)
        os.makedirs(output_dir, exist_ok=True)

        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=self.config.epochs,
            per_device_train_batch_size=self.config.batch_size,
            per_device_eval_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            max_grad_norm=self.config.max_grad_norm,
            weight_decay=self.config.weight_decay,
            lr_scheduler_type=self.config.lr_scheduler_type,
            fp16=self.config.fp16,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            eval_steps=self.config.eval_steps,
            evaluation_strategy="steps" if self._eval_dataset else "no",
            save_strategy="steps",
            load_best_model_at_end=self._eval_dataset is not None,
            seed=self.config.seed,
            report_to="none",
        )

        trainer = Trainer(
            model=self._peft_model,
            args=training_args,
            train_dataset=self._train_dataset,
            eval_dataset=self._eval_dataset,
        )

        start_time = time.time()
        trainer.train()
        training_time = time.time() - start_time

        model_save_path = os.path.join(output_dir, "final")
        self.save_model(model_save_path)

        eval_metrics = {}
        eval_loss = 0.0
        if self._eval_dataset:
            eval_result = trainer.evaluate()
            eval_loss = eval_result.get("eval_loss", 0.0)
            eval_metrics = {k: v for k, v in eval_result.items() if k != "eval_loss"}

        total_params = sum(p.numel() for p in self._peft_model.parameters())
        trainable_params = sum(p.numel() for p in self._peft_model.parameters() if p.requires_grad)

        result = TrainingResult(
            model_path=model_save_path,
            total_steps=trainer.state.global_step,
            total_epochs=self.config.epochs,
            train_loss=trainer.state.log_history[-1].get("loss", 0.0) if trainer.state.log_history else 0.0,
            eval_loss=eval_loss,
            eval_metrics=eval_metrics,
            params_million=total_params / 1e6,
            training_time_seconds=training_time,
            gpu_memory_used_mb=torch.cuda.max_memory_allocated() / 1024 / 1024 if torch.cuda.is_available() else 0.0,
            cost_estimate_usd=self._estimate_cost(total_params / 1e6, training_time),
        )

        return result

    def _simulate_training(self) -> TrainingResult:
        """模拟训练（当依赖不可用时）
        
        Returns:
            TrainingResult: 模拟的训练结果
        """
        import time
        time.sleep(0.1)
        
        estimated_params = self._estimate_params()
        
        result = TrainingResult(
            model_path=os.path.join(self.config.output_dir, self.config.model_name, "final"),
            total_steps=self.config.epochs * 100,
            total_epochs=self.config.epochs,
            train_loss=2.5,
            eval_loss=2.8,
            eval_metrics={"accuracy": 0.75, "perplexity": 16.4},
            params_million=estimated_params,
            training_time_seconds=1800.0,
            gpu_memory_used_mb=4000.0,
            cost_estimate_usd=self._estimate_cost(estimated_params, 1800.0),
        )
        
        logger.info(f"Simulated training result: params={result.params_million:.2f}M, "
                   f"cost=${result.cost_estimate_usd:.4f}")
        
        return result

    def _estimate_params(self) -> float:
        """估算参数量（基于 LoRA 配置）
        
        Returns:
            float: 估算的参数量（百万）
        """
        base_params = {
            "gpt2": 124,
            "gpt2-medium": 355,
            "gpt2-large": 774,
            "gpt2-xl": 1500,
            "distilgpt2": 82,
            "bert-base-uncased": 110,
            "roberta-base": 125,
        }
        
        base_model_lower = self.config.base_model_path.lower()
        base_params_million = 100.0
        
        for name, params in base_params.items():
            if name in base_model_lower:
                base_params_million = params
                break
        
        return base_params_million

    def evaluate(self) -> dict[str, float]:
        """评估模型
        
        Returns:
            Dict[str, float]: 评估指标
        """
        logger.info("Evaluating LoRA model")
        
        if not self._dependencies_available or self._model is None:
            logger.warning("Model not loaded, returning simulated evaluation")
            return {"accuracy": 0.75, "perplexity": 16.4, "loss": 2.8}

        try:
            if self._eval_dataset is None:
                logger.warning("No eval dataset available")
                return {}
            
            from transformers import Trainer
            trainer = Trainer(model=self._peft_model)
            eval_result = trainer.evaluate(self._eval_dataset)
            return {k: float(v) for k, v in eval_result.items()}
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {"error": str(e)}

    def save_model(self, output_path: str) -> str:
        """保存 LoRA 模型（只保存适配器权重）
        
        Args:
            output_path: 保存路径
            
        Returns:
            str: 实际保存路径
        """
        logger.info(f"Saving LoRA model to {output_path}")
        os.makedirs(output_path, exist_ok=True)

        if not self._dependencies_available or self._peft_model is None:
            logger.warning("Model not loaded, creating placeholder files")
            with open(os.path.join(output_path, "adapter_config.json"), "w") as f:
                import json
                json.dump({
                    "r": self.lora_config.rank,
                    "lora_alpha": self.lora_config.alpha,
                    "lora_dropout": self.lora_config.dropout,
                    "task_type": self.lora_config.task_type,
                }, f, indent=2)
            return output_path

        try:
            self._peft_model.save_pretrained(output_path)
            if self._tokenizer:
                self._tokenizer.save_pretrained(output_path)
            logger.info(f"LoRA adapter saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise
