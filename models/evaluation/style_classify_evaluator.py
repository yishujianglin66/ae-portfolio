"""
风格分类评估器 - 评估视频风格分类模型的性能
评估维度：
- 准确率 (Accuracy)
- 精确率/召回率/F1
- 混淆矩阵
- Top-K 准确率
参考 Antares 哲学：量化评估，精悍够用
"""
import logging
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from .evaluator_base import BaseEvaluator, EvaluationConfig, EvaluationResult

logger = logging.getLogger(__name__)


class StyleClassifyEvaluator(BaseEvaluator):
    """风格分类评估器
    
    评估视频风格分类模型的性能。
    
    评估维度：
    - accuracy: 准确率
    - precision_macro: 宏平均精确率
    - recall_macro: 宏平均召回率
    - f1_macro: 宏平均 F1 分数
    - precision_weighted: 加权精确率
    - recall_weighted: 加权召回率
    - f1_weighted: 加权 F1 分数
    - top_k_accuracy: Top-K 准确率
    
    参考 Antares 哲学：用多维度指标确保小模型"精悍够用"。
    """

    def __init__(self, config: EvaluationConfig):
        """初始化风格分类评估器
        
        Args:
            config: 评估配置
        """
        super().__init__(config)
        self._labels: List[str] = []
        self._label_to_idx: Dict[str, int] = {}

    def load_model(self, model_path: str) -> None:
        """加载待评估的模型
        
        Args:
            model_path: 模型路径
        """
        logger.info(f"Loading model from {model_path} for style classification evaluation")
        self._model = model_path

    def load_dataset(self, dataset: Any) -> None:
        """加载评估数据集
        
        Args:
            dataset: 数据集对象
        """
        logger.info("Loading dataset for style classification evaluation")
        self._dataset = dataset
        
        if hasattr(dataset, 'STYLE_LABELS'):
            self._labels = dataset.STYLE_LABELS
        elif hasattr(dataset, '_label_to_idx'):
            self._label_to_idx = dataset._label_to_idx
            self._labels = sorted(self._label_to_idx.keys(), key=lambda k: self._label_to_idx[k])

    def evaluate(self) -> EvaluationResult:
        """执行评估
        
        Returns:
            EvaluationResult: 评估结果
        """
        self._start_evaluation()
        
        result = EvaluationResult(
            eval_name=self.config.eval_name or "style_classify_evaluation",
            model_name=str(self._model),
        )
        
        test_data = self._get_test_data()
        if not test_data:
            logger.warning("No test data available")
            result.metrics = {"error": -1.0}
            return self._end_evaluation(result)
        
        predictions = []
        references = []
        prediction_probs = []
        
        for sample in test_data:
            true_label = self._get_true_label(sample)
            if true_label is None:
                continue
            
            pred_label, pred_probs = self._predict(sample)
            
            predictions.append(pred_label)
            references.append(true_label)
            prediction_probs.append(pred_probs)
        
        total = len(references)
        result.total_samples = total
        
        metrics = self.calculate_metrics(predictions, references)
        
        top_k_acc = self._calculate_top_k_accuracy(prediction_probs, references, k=3)
        metrics['top_3_accuracy'] = top_k_acc
        
        top_k_acc_5 = self._calculate_top_k_accuracy(prediction_probs, references, k=5)
        metrics['top_5_accuracy'] = top_k_acc_5
        
        confusion_matrix = self._build_confusion_matrix(predictions, references)
        result.details['confusion_matrix'] = confusion_matrix
        
        per_class_metrics = self._calculate_per_class_metrics(predictions, references)
        result.details['per_class_metrics'] = per_class_metrics
        
        if self.config.metric_names:
            metrics = {k: v for k, v in metrics.items() if k in self.config.metric_names}
        
        result.metrics = metrics
        
        primary_metric = metrics.get('f1_weighted', metrics.get('accuracy', 0.0))
        result.cost_effectiveness = self.calculate_cost_effectiveness(
            primary_metric=primary_metric,
            params_million=result.params_million,
        )
        
        return self._end_evaluation(result)

    def _get_test_data(self) -> List[Any]:
        """获取测试数据
        
        Returns:
            List[Any]: 测试数据列表
        """
        if self._dataset is None:
            return []
        
        if hasattr(self._dataset, 'get_test_data'):
            return self._dataset.get_test_data()
        
        if isinstance(self._dataset, list):
            return self._dataset
        
        return []

    def _get_true_label(self, sample: Any) -> Optional[str]:
        """获取真实标签
        
        Args:
            sample: 样本
            
        Returns:
            Optional[str]: 真实标签
        """
        if hasattr(sample, 'label'):
            return sample.label
        if isinstance(sample, dict):
            return sample.get('label', sample.get('style'))
        return None

    def _predict(self, sample: Any) -> Tuple[str, Dict[str, float]]:
        """预测（框架模式下返回模拟结果）
        
        Args:
            sample: 输入样本
            
        Returns:
            Tuple[str, Dict[str, float]]: (预测标签, 各类别概率)
        """
        true_label = self._get_true_label(sample)
        
        if self._labels:
            probs = {}
            for label in self._labels:
                if label == true_label:
                    probs[label] = 0.7 + 0.2 * (hash(str(sample)) % 100) / 100
                else:
                    probs[label] = 0.05 + 0.1 * (hash(label + str(sample)) % 100) / 100
            
            total = sum(probs.values())
            probs = {k: v / total for k, v in probs.items()}
            
            pred_label = max(probs, key=probs.get)
            return pred_label, probs
        
        return true_label or "unknown", {}

    def calculate_metrics(self, predictions: List[str], references: List[str]) -> Dict[str, float]:
        """计算分类评估指标
        
        Args:
            predictions: 预测标签列表
            references: 真实标签列表
            
        Returns:
            Dict[str, float]: 指标字典
        """
        metrics = {}
        
        metrics['accuracy'] = self._calculate_accuracy(predictions, references)
        
        precision_macro, recall_macro, f1_macro = self._calculate_macro_metrics(predictions, references)
        metrics['precision_macro'] = precision_macro
        metrics['recall_macro'] = recall_macro
        metrics['f1_macro'] = f1_macro
        
        precision_w, recall_w, f1_w = self._calculate_weighted_metrics(predictions, references)
        metrics['precision_weighted'] = precision_w
        metrics['recall_weighted'] = recall_w
        metrics['f1_weighted'] = f1_w
        
        return metrics

    def _calculate_accuracy(self, predictions: List[str], references: List[str]) -> float:
        """计算准确率
        
        Args:
            predictions: 预测列表
            references: 真实标签列表
            
        Returns:
            float: 准确率
        """
        if not predictions or not references:
            return 0.0
        
        correct = sum(1 for p, r in zip(predictions, references) if p == r)
        return correct / len(predictions)

    def _calculate_macro_metrics(
        self, 
        predictions: List[str], 
        references: List[str]
    ) -> Tuple[float, float, float]:
        """计算宏平均指标
        
        Args:
            predictions: 预测列表
            references: 真实标签列表
            
        Returns:
            Tuple[float, float, float]: (precision, recall, f1)
        """
        all_labels = set(references) | set(predictions)
        
        if not all_labels:
            return 0.0, 0.0, 0.0
        
        precisions = []
        recalls = []
        f1s = []
        
        for label in all_labels:
            tp = sum(1 for p, r in zip(predictions, references) if p == label and r == label)
            fp = sum(1 for p, r in zip(predictions, references) if p == label and r != label)
            fn = sum(1 for p, r in zip(predictions, references) if p != label and r == label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)
        
        return (
            sum(precisions) / len(precisions) if precisions else 0.0,
            sum(recalls) / len(recalls) if recalls else 0.0,
            sum(f1s) / len(f1s) if f1s else 0.0,
        )

    def _calculate_weighted_metrics(
        self, 
        predictions: List[str], 
        references: List[str]
    ) -> Tuple[float, float, float]:
        """计算加权平均指标
        
        Args:
            predictions: 预测列表
            references: 真实标签列表
            
        Returns:
            Tuple[float, float, float]: (precision, recall, f1)
        """
        all_labels = set(references) | set(predictions)
        
        if not all_labels or not references:
            return 0.0, 0.0, 0.0
        
        label_counts = defaultdict(int)
        for label in references:
            label_counts[label] += 1
        
        total = len(references)
        
        weighted_precision = 0.0
        weighted_recall = 0.0
        weighted_f1 = 0.0
        
        for label in all_labels:
            tp = sum(1 for p, r in zip(predictions, references) if p == label and r == label)
            fp = sum(1 for p, r in zip(predictions, references) if p == label and r != label)
            fn = sum(1 for p, r in zip(predictions, references) if p != label and r == label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            
            weight = label_counts.get(label, 0) / total
            weighted_precision += precision * weight
            weighted_recall += recall * weight
            weighted_f1 += f1 * weight
        
        return weighted_precision, weighted_recall, weighted_f1

    def _calculate_top_k_accuracy(
        self, 
        prediction_probs: List[Dict[str, float]], 
        references: List[str],
        k: int = 3
    ) -> float:
        """计算 Top-K 准确率
        
        Args:
            prediction_probs: 预测概率列表
            references: 真实标签列表
            k: K 值
            
        Returns:
            float: Top-K 准确率
        """
        if not prediction_probs or not references:
            return 0.0
        
        correct = 0
        total = 0
        
        for probs, true_label in zip(prediction_probs, references):
            if not probs:
                continue
            
            sorted_labels = sorted(probs.keys(), key=lambda l: probs[l], reverse=True)
            top_k = sorted_labels[:k]
            
            if true_label in top_k:
                correct += 1
            total += 1
        
        return correct / total if total > 0 else 0.0

    def _build_confusion_matrix(
        self, 
        predictions: List[str], 
        references: List[str]
    ) -> Dict[str, Dict[str, int]]:
        """构建混淆矩阵
        
        Args:
            predictions: 预测列表
            references: 真实标签列表
            
        Returns:
            Dict[str, Dict[str, int]]: 混淆矩阵
        """
        all_labels = sorted(set(references) | set(predictions))
        
        matrix = {}
        for true_label in all_labels:
            matrix[true_label] = {}
            for pred_label in all_labels:
                matrix[true_label][pred_label] = 0
        
        for pred, ref in zip(predictions, references):
            if ref in matrix and pred in matrix[ref]:
                matrix[ref][pred] += 1
        
        return matrix

    def _calculate_per_class_metrics(
        self, 
        predictions: List[str], 
        references: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """计算每个类别的指标
        
        Args:
            predictions: 预测列表
            references: 真实标签列表
            
        Returns:
            Dict[str, Dict[str, float]]: 每个类别的指标
        """
        all_labels = sorted(set(references) | set(predictions))
        
        per_class = {}
        
        for label in all_labels:
            tp = sum(1 for p, r in zip(predictions, references) if p == label and r == label)
            fp = sum(1 for p, r in zip(predictions, references) if p == label and r != label)
            fn = sum(1 for p, r in zip(predictions, references) if p != label and r == label)
            tn = sum(1 for p, r in zip(predictions, references) if p != label and r != label)
            
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            
            per_class[label] = {
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'specificity': specificity,
                'tp': tp,
                'fp': fp,
                'fn': fn,
                'tn': tn,
            }
        
        return per_class
