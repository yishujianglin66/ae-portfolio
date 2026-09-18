"""
评估器基类 - 定义模型评估的统一接口
参考 Antares 哲学：量化评估，精悍够用
"""
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """评估配置"""
    eval_name: str = ""
    batch_size: int = 8
    max_samples: int | None = None
    metric_names: list[str] = field(default_factory=list)
    """要计算的指标名称列表，为空则计算全部"""
    output_dir: str = "./eval_output"
    save_results: bool = True
    """是否保存评估结果"""


@dataclass
class EvaluationResult:
    """评估结果
    
    包含模型在特定数据集上的评估指标。
    特别关注 Antares 式的成本效益分析。
    """
    eval_name: str = ""
    model_name: str = ""
    dataset_name: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    """评估指标字典"""
    total_samples: int = 0
    evaluation_time_seconds: float = 0.0
    cost_effectiveness: float = 0.0
    """成本效益比（Antares 核心指标），越高越好"""
    params_million: float = 0.0
    """模型参数量（百万）"""
    details: dict[str, Any] = field(default_factory=dict)
    """详细信息，如混淆矩阵、示例等"""

    def summary(self) -> str:
        """生成评估摘要
        
        Returns:
            str: 评估摘要文本
        """
        lines = [
            f"=== Evaluation: {self.eval_name} ===",
            f"Model: {self.model_name}",
            f"Dataset: {self.dataset_name}",
            f"Total samples: {self.total_samples}",
            f"Time: {self.evaluation_time_seconds:.2f}s",
            f"Params: {self.params_million:.2f}M",
            f"Cost-effectiveness: {self.cost_effectiveness:.4f}",
            "",
            "Metrics:",
        ]
        
        for name, value in sorted(self.metrics.items()):
            lines.append(f"  {name}: {value:.4f}")
        
        return "\n".join(lines)


class BaseEvaluator(ABC):
    """评估器抽象基类
    
    定义所有评估器必须实现的统一接口。
    参考 Antares 哲学：通过标准化的评估确保小模型"精悍够用"。
    """

    def __init__(self, config: EvaluationConfig):
        """初始化评估器
        
        Args:
            config: 评估配置
        """
        self.config = config
        self._model = None
        self._dataset = None
        self._start_time = 0.0

    @abstractmethod
    def load_model(self, model_path: str) -> None:
        """加载待评估的模型
        
        Args:
            model_path: 模型路径
        """
        pass

    @abstractmethod
    def load_dataset(self, dataset: Any) -> None:
        """加载评估数据集
        
        Args:
            dataset: 数据集对象或数据路径
        """
        pass

    @abstractmethod
    def evaluate(self) -> EvaluationResult:
        """执行评估
        
        Returns:
            EvaluationResult: 评估结果
        """
        pass

    @abstractmethod
    def calculate_metrics(self, predictions: list[Any], references: list[Any]) -> dict[str, float]:
        """计算评估指标
        
        Args:
            predictions: 预测结果列表
            references: 参考结果列表
            
        Returns:
            Dict[str, float]: 指标字典
        """
        pass

    def _start_evaluation(self) -> None:
        """评估开始时调用"""
        self._start_time = time.time()
        logger.info(f"Starting evaluation: {self.config.eval_name}")

    def _end_evaluation(self, result: EvaluationResult) -> EvaluationResult:
        """评估结束时调用
        
        Args:
            result: 评估结果
            
        Returns:
            EvaluationResult: 更新后的评估结果
        """
        result.evaluation_time_seconds = time.time() - self._start_time
        
        if self.config.save_results:
            self._save_result(result)
        
        logger.info(f"Evaluation completed in {result.evaluation_time_seconds:.2f}s")
        logger.info(result.summary())
        
        return result

    def _save_result(self, result: EvaluationResult) -> None:
        """保存评估结果
        
        Args:
            result: 评估结果
        """
        try:
            import json
            import os
            
            os.makedirs(self.config.output_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{result.eval_name}_{timestamp}.json"
            filepath = os.path.join(self.config.output_dir, filename)
            
            result_dict = {
                'eval_name': result.eval_name,
                'model_name': result.model_name,
                'dataset_name': result.dataset_name,
                'metrics': result.metrics,
                'total_samples': result.total_samples,
                'evaluation_time_seconds': result.evaluation_time_seconds,
                'cost_effectiveness': result.cost_effectiveness,
                'params_million': result.params_million,
                'details': result.details,
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Evaluation result saved to {filepath}")
        except Exception as e:
            logger.warning(f"Failed to save evaluation result: {e}")

    def calculate_cost_effectiveness(
        self,
        primary_metric: float,
        params_million: float,
        training_time_hours: float = 0.0,
        inference_time_ms: float = 0.0
    ) -> float:
        """计算成本效益比（Antares 核心指标）
        
        综合考虑效果、参数量、训练成本、推理速度。
        值越高表示"精悍够用"程度越高。
        
        公式：cost_effectiveness = primary_metric / (params_million * 0.1 + training_time_hours * 0.5 + inference_time_ms * 0.01)
        
        Args:
            primary_metric: 主要评估指标（如准确率、BLEU等）
            params_million: 参数量（百万）
            training_time_hours: 训练时间（小时）
            inference_time_ms: 单样本推理时间（毫秒）
            
        Returns:
            float: 成本效益比
        """
        cost = params_million * 0.1 + training_time_hours * 0.5 + inference_time_ms * 0.01
        if cost == 0:
            return primary_metric
        return primary_metric / cost
