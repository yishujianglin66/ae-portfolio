"""
效果参数优化模型配置
参考 Antares "精悍够用" 哲学：用最小参数量实现 AE 效果参数的智能优化
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ParamOptimConfig:
    """效果参数优化模型配置
    
    针对 AE 效果参数优化场景的优化配置，
    遵循 Antares 哲学：轻量模型 + 强化学习 = 精准调参。
    
    输入：效果类型 + 目标风格描述
    输出：各参数的推荐值
    """
    
    model_name: str = "param-optimizer"
    """模型名称"""
    
    base_model: str = "gpt2"
    """推荐基座模型（GPT-2 小型，用于序列到序列的参数生成）"""
    
    alternative_base_models: list[str] = field(default_factory=lambda: [
        "distilgpt2",
        "gpt2",
        "facebook/bart-base",
        "t5-small",
    ])
    """备选基座模型列表，按参数量从小到大排序"""
    
    target_params_million: float = 10.0
    """目标参数量（百万）— Antares 核心指标：参数优化模型不需要太大"""
    
    task_type: str = "parameter_optimization"
    """任务类型"""
    
    input_type: str = "effect_config"
    """输入类型：effect_config (效果配置 + 目标描述)"""
    
    output_type: str = "parameter_values"
    """输出类型：parameter_values (参数值 JSON)"""
    
    supported_effects: list[str] = field(default_factory=lambda: [
        "ADBE_Lumetri_Color",
        "ADBE_Sharpen",
        "ADBE_Vignette",
        "ADBE_Glow",
        "ADBE_Levels",
        "ADBE_Curves",
        "ADBE_Hue_Saturation",
        "ADBE_Color_Balance",
        "ADBE_Tint",
        "ADBE_Channel_Mixer",
    ])
    """支持的效果列表"""
    
    num_parameters: int = 50
    """平均每个效果的参数数量"""
    
    parameter_embedding_dim: int = 64
    """参数嵌入维度"""
    
    use_lora: bool = True
    """是否使用 LoRA 微调"""
    
    lora_rank: int = 12
    """LoRA rank"""
    
    lora_alpha: int = 24
    """LoRA alpha"""
    
    lora_dropout: float = 0.05
    """LoRA dropout"""
    
    lora_target_modules: list[str] = field(default_factory=lambda: [
        "c_attn", "c_proj",
    ])
    """LoRA 目标模块"""
    
    training_epochs: int = 8
    """训练轮数"""
    
    batch_size: int = 16
    """批次大小"""
    
    learning_rate: float = 1.5e-4
    """学习率"""
    
    warmup_steps: int = 80
    """预热步数"""
    
    weight_decay: float = 0.005
    """权重衰减"""
    
    lr_scheduler_type: str = "cosine_with_restarts"
    """学习率调度器类型"""
    
    early_stopping_patience: int = 4
    """早停耐心值"""
    
    fp16: bool = True
    """是否使用混合精度训练"""
    
    gradient_accumulation_steps: int = 2
    """梯度累积步数"""
    
    max_grad_norm: float = 1.0
    """梯度裁剪范数"""
    
    seed: int = 42
    """随机种子"""
    
    logging_steps: int = 15
    """日志记录步数"""
    
    save_steps: int = 150
    """模型保存步数"""
    
    eval_steps: int = 100
    """评估步数"""
    
    data_augmentation: bool = True
    """是否启用数据增强"""
    
    augmentation_types: list[str] = field(default_factory=lambda: [
        "parameter_jitter",
        "style_description_paraphrase",
        "parameter_masking",
        "effect_order_shuffle",
    ])
    """数据增强类型"""
    
    augmentation_jitter_std: float = 0.03
    """参数抖动标准差（归一化后）"""
    
    use_rl_finetune: bool = False
    """是否使用强化学习微调（预留）"""
    
    rl_reward_type: str = "style_similarity"
    """RL 奖励类型：style_similarity / human_preference / combined"""
    
    evaluation_metrics: list[str] = field(default_factory=lambda: [
        "parameter_accuracy",
        "style_similarity",
        "param_range_validity",
        "smoothness_score",
        "render_success_rate",
    ])
    """评估指标列表"""
    
    parameter_tolerance: float = 0.1
    """参数容差（归一化后），在此范围内视为正确"""
    
    estimated_training_cost_usd: float = 3.0
    """估算训练成本（美元）— Antares 式成本控制"""
    
    estimated_inference_latency_ms: float = 50.0
    """估算推理延迟（毫秒）"""
    
    target_parameter_accuracy: float = 0.85
    """目标参数准确率"""
    
    target_style_similarity: float = 0.80
    """目标风格相似度"""
    
    quality_gate_threshold: float = 0.75
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
            "max_seq_length": 1024,
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
        """估算模型参数量（百万）
        
        Returns:
            float: 估算参数量（百万）
        """
        if self.use_lora:
            hidden_size = 768
            num_layers = 12
            num_modules = len(self.lora_target_modules)
            params_per_module = 2 * hidden_size * self.lora_rank
            lora_params = params_per_module * num_modules * num_layers
            
            head_params = hidden_size * self.num_parameters + self.num_parameters
            
            total_params = lora_params + head_params
        else:
            total_params = 124_000_000
        
        return total_params / 1_000_000
