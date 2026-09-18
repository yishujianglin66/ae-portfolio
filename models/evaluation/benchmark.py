"""
基准测试套件 - 标准测试集管理、多模型对比、评估报告生成
Antares 式的"精悍够用"量化：成本-效果分析
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .evaluator_base import BaseEvaluator, EvaluationConfig, EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """基准测试结果
    
    包含多个模型在多个数据集上的对比结果，
    特别关注 Antares 式的成本效益分析。
    """
    benchmark_name: str = ""
    models: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    results: dict[str, dict[str, EvaluationResult]] = field(default_factory=dict)
    """results[model_name][dataset_name] = EvaluationResult"""
    cost_effectiveness_ranking: list[tuple[str, float]] = field(default_factory=list)
    """按成本效益比排序的模型列表 [(model_name, score), ...]"""
    summary: dict[str, Any] = field(default_factory=dict)

    def generate_report(self) -> str:
        """生成基准测试报告
        
        Returns:
            str: 报告文本
        """
        lines = [
            "=" * 60,
            f"  Benchmark Report: {self.benchmark_name}",
            "=" * 60,
            "",
            f"Models evaluated: {len(self.models)}",
            f"Datasets: {len(self.datasets)}",
            f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        
        lines.append("-" * 60)
        lines.append("  Cost-Effectiveness Ranking (Antares Score)")
        lines.append("-" * 60)
        lines.append(f"{'Rank':<6}{'Model':<30}{'Score':<12}")
        lines.append("-" * 60)
        
        for rank, (model, score) in enumerate(self.cost_effectiveness_ranking, 1):
            lines.append(f"{rank:<6}{model:<30}{score:<12.4f}")
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("  Detailed Results")
        lines.append("-" * 60)
        
        for model_name in self.models:
            lines.append("")
            lines.append(f"Model: {model_name}")
            lines.append("-" * 40)
            
            for dataset_name in self.datasets:
                if model_name in self.results and dataset_name in self.results[model_name]:
                    result = self.results[model_name][dataset_name]
                    lines.append(f"  Dataset: {dataset_name}")
                    lines.append(f"    Samples: {result.total_samples}")
                    lines.append(f"    Time: {result.evaluation_time_seconds:.2f}s")
                    lines.append(f"    Params: {result.params_million:.2f}M")
                    lines.append(f"    Cost-effectiveness: {result.cost_effectiveness:.4f}")
                    lines.append("    Metrics:")
                    for metric_name, metric_value in sorted(result.metrics.items()):
                        lines.append(f"      {metric_name}: {metric_value:.4f}")
                    lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)

    def save_report(self, output_dir: str) -> str:
        """保存报告到文件
        
        Args:
            output_dir: 输出目录
            
        Returns:
            str: 报告文件路径
        """
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(output_dir, f"benchmark_{timestamp}.txt")
        json_file = os.path.join(output_dir, f"benchmark_{timestamp}.json")
        
        report = self.generate_report()
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        json_data = {
            'benchmark_name': self.benchmark_name,
            'models': self.models,
            'datasets': self.datasets,
            'cost_effectiveness_ranking': [
                {'model': m, 'score': s} for m, s in self.cost_effectiveness_ranking
            ],
            'results': {
                model: {
                    dataset: {
                        'metrics': res.metrics,
                        'total_samples': res.total_samples,
                        'evaluation_time_seconds': res.evaluation_time_seconds,
                        'cost_effectiveness': res.cost_effectiveness,
                        'params_million': res.params_million,
                    }
                    for dataset, res in datasets.items()
                }
                for model, datasets in self.results.items()
            },
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Benchmark report saved to {report_file}")
        return report_file


class BenchmarkSuite:
    """基准测试套件
    
    提供：
    - 标准测试集管理
    - 多模型对比
    - 生成评估报告
    - 成本-效果分析（Antares 式的"精悍够用"量化）
    
    参考 Antares 哲学：用成本效益比量化"精悍够用"的程度。
    """

    def __init__(self, benchmark_name: str = "default_benchmark", output_dir: str = "./benchmark_output"):
        """初始化基准测试套件
        
        Args:
            benchmark_name: 基准测试名称
            output_dir: 输出目录
        """
        self.benchmark_name = benchmark_name
        self.output_dir = output_dir
        self._evaluators: dict[str, BaseEvaluator] = {}
        self._datasets: dict[str, Any] = {}
        self._models: dict[str, str] = {}

    def register_dataset(self, name: str, dataset: Any) -> None:
        """注册测试数据集
        
        Args:
            name: 数据集名称
            dataset: 数据集对象
        """
        self._datasets[name] = dataset
        logger.info(f"Registered dataset: {name}")

    def register_model(self, name: str, model_path: str) -> None:
        """注册待测试模型
        
        Args:
            name: 模型名称
            model_path: 模型路径
        """
        self._models[name] = model_path
        logger.info(f"Registered model: {name}")

    def register_evaluator(self, evaluator_type: str, evaluator: BaseEvaluator) -> None:
        """注册评估器
        
        Args:
            evaluator_type: 评估器类型
            evaluator: 评估器实例
        """
        self._evaluators[evaluator_type] = evaluator
        logger.info(f"Registered evaluator: {evaluator_type}")

    def run_benchmark(
        self,
        evaluator_type: str,
        datasets: list[str] | None = None,
        models: list[str] | None = None,
    ) -> BenchmarkResult:
        """运行基准测试
        
        Args:
            evaluator_type: 使用的评估器类型
            datasets: 要测试的数据集名称列表，None 表示全部
            models: 要测试的模型名称列表，None 表示全部
            
        Returns:
            BenchmarkResult: 基准测试结果
        """
        logger.info(f"Starting benchmark: {self.benchmark_name}")
        
        if evaluator_type not in self._evaluators:
            raise ValueError(f"Evaluator type '{evaluator_type}' not registered")
        
        evaluator_template = self._evaluators[evaluator_type]
        
        dataset_names = datasets or list(self._datasets.keys())
        model_names = models or list(self._models.keys())
        
        result = BenchmarkResult(
            benchmark_name=self.benchmark_name,
            models=model_names,
            datasets=dataset_names,
        )
        
        for model_name in model_names:
            result.results[model_name] = {}
            
            if model_name not in self._models:
                logger.warning(f"Model '{model_name}' not registered, skipping")
                continue
            
            model_path = self._models[model_name]
            
            for dataset_name in dataset_names:
                if dataset_name not in self._datasets:
                    logger.warning(f"Dataset '{dataset_name}' not registered, skipping")
                    continue
                
                dataset = self._datasets[dataset_name]
                
                logger.info(f"Evaluating model '{model_name}' on dataset '{dataset_name}'")
                
                evaluator = self._clone_evaluator(evaluator_template)
                evaluator.load_model(model_path)
                evaluator.load_dataset(dataset)
                
                eval_result = evaluator.evaluate()
                eval_result.model_name = model_name
                eval_result.dataset_name = dataset_name
                
                result.results[model_name][dataset_name] = eval_result
        
        result.cost_effectiveness_ranking = self._calculate_ranking(result)
        result.summary = self._generate_summary(result)
        
        if self.output_dir:
            result.save_report(self.output_dir)
        
        logger.info(f"Benchmark completed: {self.benchmark_name}")
        return result

    def _clone_evaluator(self, template: BaseEvaluator) -> BaseEvaluator:
        """克隆评估器（基于配置创建新实例）
        
        Args:
            template: 模板评估器
            
        Returns:
            BaseEvaluator: 新的评估器实例
        """
        evaluator_class = template.__class__
        new_evaluator = evaluator_class(template.config)
        return new_evaluator

    def _calculate_ranking(self, benchmark_result: BenchmarkResult) -> list[tuple[str, float]]:
        """计算成本效益排名
        
        Antares 核心指标：综合考虑各数据集上的效果与模型成本。
        
        Args:
            benchmark_result: 基准测试结果
            
        Returns:
            List[Tuple[str, float]]: 按分数降序排列的 [(model_name, score), ...]
        """
        model_scores = {}
        
        for model_name in benchmark_result.models:
            total_score = 0.0
            count = 0
            
            for dataset_name, eval_result in benchmark_result.results.get(model_name, {}).items():
                if eval_result.cost_effectiveness > 0:
                    total_score += eval_result.cost_effectiveness
                    count += 1
            
            avg_score = total_score / count if count > 0 else 0.0
            model_scores[model_name] = avg_score
        
        ranking = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        return ranking

    def _generate_summary(self, benchmark_result: BenchmarkResult) -> dict[str, Any]:
        """生成摘要信息
        
        Args:
            benchmark_result: 基准测试结果
            
        Returns:
            Dict[str, Any]: 摘要
        """
        summary = {
            'total_models': len(benchmark_result.models),
            'total_datasets': len(benchmark_result.datasets),
            'best_model': benchmark_result.cost_effectiveness_ranking[0][0] if benchmark_result.cost_effectiveness_ranking else None,
            'best_score': benchmark_result.cost_effectiveness_ranking[0][1] if benchmark_result.cost_effectiveness_ranking else 0.0,
        }
        return summary

    def compare_models(
        self,
        model_a: str,
        model_b: str,
        dataset: str,
        primary_metric: str = "accuracy",
    ) -> dict[str, Any]:
        """比较两个模型在特定数据集上的表现
        
        Args:
            model_a: 模型 A 名称
            model_b: 模型 B 名称
            dataset: 数据集名称
            primary_metric: 主要对比指标
            
        Returns:
            Dict[str, Any]: 对比结果
        """
        if model_a not in self._models or model_b not in self._models:
            raise ValueError("Both models must be registered")
        
        if dataset not in self._datasets:
            raise ValueError(f"Dataset '{dataset}' not registered")
        
        result_a = None
        result_b = None
        
        for evaluator_type in self._evaluators:
            evaluator = self._evaluators[evaluator_type]
            
            eval_a = self._clone_evaluator(evaluator)
            eval_a.load_model(self._models[model_a])
            eval_a.load_dataset(self._datasets[dataset])
            result_a = eval_a.evaluate()
            
            eval_b = self._clone_evaluator(evaluator)
            eval_b.load_model(self._models[model_b])
            eval_b.load_dataset(self._datasets[dataset])
            result_b = eval_b.evaluate()
            
            break
        
        if not result_a or not result_b:
            return {'error': 'No evaluator available'}
        
        metric_a = result_a.metrics.get(primary_metric, 0.0)
        metric_b = result_b.metrics.get(primary_metric, 0.0)
        
        improvement = 0.0
        if metric_a > 0:
            improvement = (metric_b - metric_a) / metric_a * 100
        
        comparison = {
            'model_a': model_a,
            'model_b': model_b,
            'dataset': dataset,
            'primary_metric': primary_metric,
            'metric_a': metric_a,
            'metric_b': metric_b,
            'improvement_percent': improvement,
            'cost_effectiveness_a': result_a.cost_effectiveness,
            'cost_effectiveness_b': result_b.cost_effectiveness,
            'winner': model_b if metric_b > metric_a else model_a,
            'all_metrics_a': result_a.metrics,
            'all_metrics_b': result_b.metrics,
        }
        
        return comparison
