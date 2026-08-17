"""
训练器基类 - 定义训练流程的统一接口
参考 Antares 的工程哲学：小模型、精调、垂直场景
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import time
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """训练配置
    
    包含所有训练相关的超参数，参考 Antares "精悍够用" 哲学，
    支持通过 target_params_million 限制目标参数量。
    """
    model_name: str = ""
    base_model_path: str = ""
    output_dir: str = "./output"
    epochs: int = 3
    batch_size: int = 8
    learning_rate: float = 2e-5
    warmup_steps: int = 100
    max_seq_length: int = 512
    gradient_accumulation_steps: int = 1
    max_grad_norm: float = 1.0
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    seed: int = 42
    fp16: bool = True
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    early_stopping_patience: int = 3
    target_params_million: Optional[float] = None
    """目标参数量（百万），Antares式精悍够用"""


@dataclass
class TrainingResult:
    """训练结果
    
    包含训练完成后的所有指标，特别关注参数量、训练时间、成本估算等，
    用于 Antares 式的"精悍够用"评估。
    """
    model_path: str = ""
    total_steps: int = 0
    total_epochs: int = 0
    train_loss: float = 0.0
    eval_loss: float = 0.0
    eval_metrics: Dict[str, float] = field(default_factory=dict)
    params_million: float = 0.0
    """实际参数量（百万）"""
    training_time_seconds: float = 0.0
    gpu_memory_used_mb: float = 0.0
    cost_estimate_usd: float = 0.0
    """估算训练成本"""


class BaseTrainer(ABC):
    """训练器抽象基类
    
    定义所有训练器必须实现的统一接口。
    参考 Antares 哲学：通过标准化的训练流程，确保小模型的精调质量。
    """

    def __init__(self, config: TrainingConfig):
        """初始化训练器
        
        Args:
            config: 训练配置
        """
        self.config = config
        self._callbacks: List[Callable] = []
        self._step = 0
        self._epoch = 0
        self._train_dataset = None
        self._eval_dataset = None
        self._model = None
        self._tokenizer = None
        self._start_time = 0.0

    @abstractmethod
    def load_dataset(self, train_data: Any, eval_data: Any = None) -> None:
        """加载数据集
        
        Args:
            train_data: 训练数据，可以是文件路径、数据集对象等
            eval_data: 评估数据，可选
        """
        pass

    @abstractmethod
    def load_base_model(self) -> None:
        """加载基座模型
        
        从指定的 base_model_path 加载预训练模型。
        """
        pass

    @abstractmethod
    def train(self) -> TrainingResult:
        """执行训练
        
        Returns:
            TrainingResult: 训练结果
        """
        pass

    @abstractmethod
    def evaluate(self) -> Dict[str, float]:
        """评估模型
        
        Returns:
            Dict[str, float]: 评估指标字典
        """
        pass

    @abstractmethod
    def save_model(self, output_path: str) -> str:
        """保存模型
        
        Args:
            output_path: 保存路径
            
        Returns:
            str: 实际保存的路径
        """
        pass

    def add_callback(self, callback: Callable) -> None:
        """添加训练回调
        
        Args:
            callback: 回调函数，签名为 callback(event, step, epoch, **kwargs)
        """
        self._callbacks.append(callback)

    def _fire_callback(self, event: str, **kwargs) -> None:
        """触发回调
        
        Args:
            event: 事件名称
            **kwargs: 额外参数
        """
        for cb in self._callbacks:
            try:
                cb(event, step=self._step, epoch=self._epoch, **kwargs)
            except Exception as e:
                logger.warning(f"Callback execution failed: {e}")

    def _start_training(self) -> None:
        """训练开始时调用"""
        self._start_time = time.time()
        self._fire_callback("on_training_start")
        logger.info(f"Training started: {self.config.model_name}")

    def _end_training(self) -> None:
        """训练结束时调用"""
        training_time = time.time() - self._start_time
        self._fire_callback("on_training_end", training_time=training_time)
        logger.info(f"Training completed in {training_time:.2f}s")

    def _estimate_cost(self, params_million: float, training_time_seconds: float) -> float:
        """估算训练成本（Antares 式成本效益分析基础）
        
        基于 GPU 每小时约 $1.5 的 A10 估算。
        
        Args:
            params_million: 参数量（百万）
            training_time_seconds: 训练时间（秒）
            
        Returns:
            float: 估算成本（美元）
        """
        gpu_hours = training_time_seconds / 3600.0
        cost_per_hour = 1.5
        return gpu_hours * cost_per_hour
