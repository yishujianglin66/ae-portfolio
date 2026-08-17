"""
视频风格分类模型配置
参考 Antares "精悍够用" 哲学：用最小参数量实现精准的视频风格分类
"""
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class StyleClassifyConfig:
    """视频风格分类模型配置
    
    针对视频风格指纹分类场景的优化配置，
    遵循 Antares 哲学：轻量模型 + 特征工程 = 高效准确。
    """
    
    model_name: str = "style-classifier"
    """模型名称"""
    
    base_model: str = "google/vit-base-patch16-224"
    """推荐基座模型（ViT-Base，视觉Transformer基础版）"""
    
    alternative_base_models: List[str] = field(default_factory=lambda: [
        "google/vit-small-patch16-224",
        "microsoft/resnet-50",
        "facebook/convnext-tiny-224",
        "google/vit-base-patch16-224",
    ])
    """备选基座模型列表，按参数量从小到大排序"""
    
    target_params_million: float = 5.0
    """目标参数量（百万）— Antares 核心指标：分类头只有约 5M 参数"""
    
    task_type: str = "image_classification"
    """任务类型"""
    
    input_type: str = "style_fingerprint"
    """输入类型：style_fingerprint (特征向量) / image (原始图像) / hybrid (混合)"""
    
    feature_dim: int = 14
    """风格指纹特征维度（7基础+7漫剪专属）"""
    
    num_classes: int = 21
    """风格类别数量（13通用+8漫剪）"""
    
    style_labels: List[str] = field(default_factory=lambda: [
        "cinematic",
        "anime_puppet",
        "fast_cut",
        "slow_cut",
        "glitch_digital",
        "audio_visual",
        "particle_ambient",
        "text_animation",
        "3d_spatial",
        "realistic_color",
        "high_dynamic",
        "dark_tone",
        "low_saturation",
        "高饱和",
        "长镜头",
        "amv_pull_zoom",
        "amv_fast_cut",
        "amv_beat_sync",
        "amv_korean_flash",
        "amv_glitch",
        "amv_cinematic",
        "amv_3d_spatial",
        "amv_high_burn",
    ])
    """风格标签列表（含8种漫剪专属标签）"""
    
    use_lora: bool = True
    """是否使用 LoRA 微调"""
    
    lora_rank: int = 8
    """LoRA rank — 分类任务 rank 可以更小"""
    
    lora_alpha: int = 16
    """LoRA alpha"""
    
    lora_dropout: float = 0.1
    """LoRA dropout"""
    
    lora_target_modules: List[str] = field(default_factory=lambda: [
        "query", "value",
    ])
    """LoRA 目标模块 — 分类任务只需要微调注意力层"""
    
    training_epochs: int = 10
    """训练轮数 — 分类任务通常需要更多轮次"""
    
    batch_size: int = 32
    """批次大小 — 分类任务 batch 可以更大"""
    
    learning_rate: float = 1e-4
    """学习率"""
    
    warmup_steps: int = 100
    """预热步数"""
    
    weight_decay: float = 0.001
    """权重衰减"""
    
    lr_scheduler_type: str = "cosine"
    """学习率调度器类型"""
    
    early_stopping_patience: int = 5
    """早停耐心值"""
    
    fp16: bool = True
    """是否使用混合精度训练"""
    
    gradient_accumulation_steps: int = 1
    """梯度累积步数"""
    
    max_grad_norm: float = 1.0
    """梯度裁剪范数"""
    
    seed: int = 42
    """随机种子"""
    
    logging_steps: int = 20
    """日志记录步数"""
    
    save_steps: int = 200
    """模型保存步数"""
    
    eval_steps: int = 100
    """评估步数"""
    
    data_augmentation: bool = True
    """是否启用数据增强"""
    
    augmentation_types: List[str] = field(default_factory=lambda: [
        "feature_noise",
        "brightness_jitter",
        "contrast_jitter",
        "saturation_jitter",
        "feature_dropout",
    ])
    """数据增强类型"""
    
    augmentation_noise_std: float = 0.05
    """特征噪声标准差"""
    
    augmentation_dropout_prob: float = 0.1
    """特征 dropout 概率"""
    
    evaluation_metrics: List[str] = field(default_factory=lambda: [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "top_k_accuracy",
        "confusion_matrix",
    ])
    """评估指标列表"""
    
    top_k_values: List[int] = field(default_factory=lambda: [1, 3, 5])
    """Top-K 准确率的 K 值"""
    
    class_weights: Dict[str, float] = field(default_factory=dict)
    """类别权重，用于处理类别不平衡"""
    
    estimated_training_cost_usd: float = 2.0
    """估算训练成本（美元）— Antares 式成本控制"""
    
    estimated_inference_latency_ms: float = 20.0
    """估算推理延迟（毫秒）— 分类任务应该很快"""
    
    target_accuracy: float = 0.90
    """目标准确率 — 精调后应达到 90%+"""
    
    target_f1: float = 0.88
    """目标 F1 分数"""
    
    quality_gate_threshold: float = 0.85
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
            "max_seq_length": self.feature_dim,
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
        """估算分类器参数量（百万）
        
        Returns:
            float: 估算参数量（百万）
        """
        if self.use_lora:
            hidden_size = 768
            num_layers = 12
            num_modules = len(self.lora_target_modules)
            params_per_module = 2 * hidden_size * self.lora_rank
            lora_params = params_per_module * num_modules * num_layers
            
            classifier_params = hidden_size * self.num_classes
            
            total_params = lora_params + classifier_params
        else:
            total_params = self.feature_dim * self.num_classes + self.num_classes
        
        return total_params / 1_000_000
