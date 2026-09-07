"""
JSX 代码生成模型配置
参考 Antares "精悍够用" 哲学：用最小参数量实现高质量 AE JSX 代码生成
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class JSXCodeConfig:
    """JSX 代码生成模型配置
    
    针对 AE ExtendScript 代码生成场景的优化配置，
    遵循 Antares 哲学：小模型 + 垂直精调 = 超越大模型效果。
    """
    
    model_name: str = "jsx-code-generator"
    """模型名称"""
    
    base_model: str = "codellama/CodeLlama-7b-hf"
    """推荐基座模型（7B 起步，LoRA 微调后可达大模型效果）"""
    
    alternative_base_models: List[str] = field(default_factory=lambda: [
        "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        "Qwen/Qwen2.5-Coder-1.5B",
        "codellama/CodeLlama-7b-Instruct-hf",
    ])
    """备选基座模型列表，按参数量从小到大排序"""
    
    target_params_million: float = 50.0
    """目标参数量（百万）— Antares 核心指标：LoRA 只训练约 50M 参数"""
    
    task_type: str = "code_generation"
    """任务类型"""
    
    max_seq_length: int = 2048
    """最大序列长度（JSX 代码通常较长）"""
    
    lora_rank: int = 16
    """LoRA rank — 越小参数量越少，16 是代码任务的甜点"""
    
    lora_alpha: int = 32
    """LoRA alpha — 通常是 rank 的 2 倍"""
    
    lora_dropout: float = 0.05
    """LoRA dropout"""
    
    lora_target_modules: List[str] = field(default_factory=lambda: [
        "q_proj", "v_proj", "k_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])
    """LoRA 目标模块 — 代码任务建议微调所有线性层"""
    
    training_epochs: int = 5
    """训练轮数"""
    
    batch_size: int = 4
    """批次大小"""
    
    learning_rate: float = 2e-4
    """学习率 — LoRA 微调可以用稍大的学习率"""
    
    warmup_steps: int = 50
    """预热步数"""
    
    weight_decay: float = 0.01
    """权重衰减"""
    
    lr_scheduler_type: str = "cosine"
    """学习率调度器类型"""
    
    early_stopping_patience: int = 3
    """早停耐心值"""
    
    fp16: bool = True
    """是否使用混合精度训练"""
    
    gradient_accumulation_steps: int = 4
    """梯度累积步数 — 小 batch 下用累积模拟大 batch"""
    
    max_grad_norm: float = 1.0
    """梯度裁剪范数"""
    
    seed: int = 42
    """随机种子"""
    
    logging_steps: int = 10
    """日志记录步数"""
    
    save_steps: int = 100
    """模型保存步数"""
    
    eval_steps: int = 100
    """评估步数"""
    
    data_format: str = "alpaca"
    """数据格式：alpaca 格式 (instruction, input, output)"""
    
    data_augmentation: bool = True
    """是否启用数据增强"""
    
    augmentation_types: List[str] = field(default_factory=lambda: [
        "variable_renaming",
        "comment_addition",
        "comment_removal",
        "whitespace_variation",
        "string_literal_variation",
    ])
    """数据增强类型"""
    
    syntax_validation: bool = True
    """是否启用语法校验过滤"""
    
    evaluation_metrics: List[str] = field(default_factory=lambda: [
        "syntax_accuracy",
        "functional_correctness",
        "code_bleu",
        "bleu",
        "code_quality_score",
    ])
    """评估指标列表"""
    
    pass_at_k: List[int] = field(default_factory=lambda: [1, 5, 10])
    """pass@k 评估指标"""
    
    estimated_training_cost_usd: float = 5.0
    """估算训练成本（美元）— Antares 式成本控制"""
    
    estimated_inference_latency_ms: float = 200.0
    """估算推理延迟（毫秒）"""
    
    target_code_bleu: float = 0.75
    """目标 CodeBLEU 分数 — 精调后应达到 0.75+"""
    
    quality_gate_threshold: float = 0.7
    """质量门限：低于此分数的模型不允许上线"""
    
    def get_training_config_kwargs(self) -> dict:
        """获取 TrainingConfig 的关键字参数
        
        Returns:
            dict: 可直接传入 TrainingConfig 的参数字典
        """
        return {
            "model_name": self.model_name,
            "base_model_path": self.base_model,
            "epochs": self.training_epochs,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "warmup_steps": self.warmup_steps,
            "max_seq_length": self.max_seq_length,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "max_grad_norm": self.max_grad_norm,
            "weight_decay": self.weight_decay,
            "lr_scheduler_type": self.lr_scheduler_type,
            "seed": self.seed,
            "fp16": self.fp16,
            "logging_steps": self.logging_steps,
            "save_steps": self.save_steps,
            "eval_steps": self.eval_steps,
            "early_stopping_patience": self.early_stopping_patience,
            "target_params_million": self.target_params_million,
        }
    
    def estimate_params_million(self) -> float:
        """估算 LoRA 参数量（百万）
        
        根据 rank 和 target_modules 数量估算。
        
        Returns:
            float: 估算参数量（百万）
        """
        hidden_size = 4096
        num_layers = 32
        num_modules = len(self.lora_target_modules)
        
        params_per_module = 2 * hidden_size * self.lora_rank
        total_params = params_per_module * num_modules * num_layers
        
        return total_params / 1_000_000
