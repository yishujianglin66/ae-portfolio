"""
评估指标工具集
包含分类、代码生成、模型评估等多种指标，
以及 Antares 哲学核心的成本效益比分析。
"""
import logging
import math
import time
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def accuracy(y_true: list[int], y_pred: list[int]) -> float:
    """计算准确率
    
    Args:
        y_true: 真实标签列表
        y_pred: 预测标签列表
        
    Returns:
        float: 准确率 (0-1)
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if len(y_true) == 0:
        return 0.0
    
    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    return correct / len(y_true)


def precision(y_true: list[int], y_pred: list[int], average: str = "macro") -> float:
    """计算精确率
    
    Args:
        y_true: 真实标签列表
        y_pred: 预测标签列表
        average: 平均方式：macro / micro / weighted
        
    Returns:
        float: 精确率
    """
    if len(y_true) == 0:
        return 0.0
    
    labels = set(y_true) | set(y_pred)
    
    if average == "micro":
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        fp = len(y_pred) - tp
        return tp / (tp + fp) if (tp + fp) > 0 else 0.0
    
    precisions = []
    weights = []
    
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        
        if (tp + fp) > 0:
            precisions.append(tp / (tp + fp))
        else:
            precisions.append(0.0)
        
        weights.append(sum(1 for t in y_true if t == label))
    
    if average == "macro":
        return sum(precisions) / len(precisions) if precisions else 0.0
    elif average == "weighted":
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(p * w for p, w in zip(precisions, weights)) / total_weight
    else:
        return sum(precisions) / len(precisions) if precisions else 0.0


def recall(y_true: list[int], y_pred: list[int], average: str = "macro") -> float:
    """计算召回率
    
    Args:
        y_true: 真实标签列表
        y_pred: 预测标签列表
        average: 平均方式：macro / micro / weighted
        
    Returns:
        float: 召回率
    """
    if len(y_true) == 0:
        return 0.0
    
    labels = set(y_true) | set(y_pred)
    
    if average == "micro":
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        fn = len(y_true) - tp
        return tp / (tp + fn) if (tp + fn) > 0 else 0.0
    
    recalls = []
    weights = []
    
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        
        if (tp + fn) > 0:
            recalls.append(tp / (tp + fn))
        else:
            recalls.append(0.0)
        
        weights.append(sum(1 for t in y_true if t == label))
    
    if average == "macro":
        return sum(recalls) / len(recalls) if recalls else 0.0
    elif average == "weighted":
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(r * w for r, w in zip(recalls, weights)) / total_weight
    else:
        return sum(recalls) / len(recalls) if recalls else 0.0


def f1_score(y_true: list[int], y_pred: list[int], average: str = "macro") -> float:
    """计算 F1 分数
    
    Args:
        y_true: 真实标签列表
        y_pred: 预测标签列表
        average: 平均方式：macro / micro / weighted
        
    Returns:
        float: F1 分数
    """
    p = precision(y_true, y_pred, average)
    r = recall(y_true, y_pred, average)
    
    if (p + r) == 0:
        return 0.0
    
    return 2 * p * r / (p + r)


def _ngrams(tokens: list[str], n: int) -> Counter:
    """生成 n-gram 计数
    
    Args:
        tokens: token 列表
        n: n-gram 的 n 值
        
    Returns:
        Counter: n-gram 计数
    """
    ngrams = []
    for i in range(len(tokens) - n + 1):
        ngram = tuple(tokens[i:i + n])
        ngrams.append(ngram)
    return Counter(ngrams)


def bleu_score(reference: str, hypothesis: str, max_n: int = 4) -> float:
    """计算 BLEU 分数
    
    使用简化版 BLEU，适用于快速评估。
    
    Args:
        reference: 参考文本（ground truth）
        hypothesis: 假设文本（模型生成）
        max_n: 最大 n-gram 阶数
        
    Returns:
        float: BLEU 分数 (0-1)
    """
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()
    
    if len(hyp_tokens) == 0:
        return 0.0
    if len(ref_tokens) == 0:
        return 0.0
    
    precisions = []
    for n in range(1, max_n + 1):
        ref_ngrams = _ngrams(ref_tokens, n)
        hyp_ngrams = _ngrams(hyp_tokens, n)
        
        if len(hyp_ngrams) == 0:
            precisions.append(0.0)
            continue
        
        total_hyp = sum(hyp_ngrams.values())
        clipped = 0
        
        for ngram, count in hyp_ngrams.items():
            clipped += min(count, ref_ngrams.get(ngram, 0))
        
        precisions.append(clipped / total_hyp if total_hyp > 0 else 0.0)
    
    if all(p == 0 for p in precisions):
        return 0.0
    
    log_sum = sum(math.log(p) for p in precisions if p > 0)
    geo_mean = math.exp(log_sum / max_n)
    
    bp = min(1.0, math.exp(1 - len(ref_tokens) / len(hyp_tokens))) if len(hyp_tokens) > 0 else 0.0
    
    return bp * geo_mean


def code_bleu_score(reference: str, hypothesis: str) -> float:
    """计算 CodeBLEU 分数（简化版）
    
    CodeBLEU 在 BLEU 基础上增加了语法匹配和语义匹配。
    这里实现简化版本，包含 n-gram 匹配、加权关键词匹配。
    
    Args:
        reference: 参考代码
        hypothesis: 生成代码
        
    Returns:
        float: CodeBLEU 分数 (0-1)
    """
    ngram_bleu = bleu_score(reference, hypothesis, max_n=4)
    
    ref_lines = [l.strip() for l in reference.split('\n') if l.strip()]
    hyp_lines = [l.strip() for l in hypothesis.split('\n') if l.strip()]
    
    if len(ref_lines) == 0 or len(hyp_lines) == 0:
        return ngram_bleu * 0.5
    
    matched_lines = sum(1 for h in hyp_lines if h in ref_lines)
    line_match_score = matched_lines / len(hyp_lines) if len(hyp_lines) > 0 else 0.0
    
    keywords = {
        'var', 'function', 'if', 'else', 'for', 'while', 'return',
        'new', 'this', 'class', 'extends', 'import', 'export',
        'const', 'let', 'app', 'layer', 'effect', 'property',
        'value', 'time', 'comp', 'project', 'item',
    }
    
    ref_words = set(reference.split()) & keywords
    hyp_words = set(hypothesis.split()) & keywords
    
    if len(ref_words) == 0 and len(hyp_words) == 0:
        keyword_match = 1.0
    elif len(ref_words | hyp_words) == 0:
        keyword_match = 0.0
    else:
        keyword_match = len(ref_words & hyp_words) / len(ref_words | hyp_words)
    
    weights = [0.5, 0.25, 0.25]
    final_score = (
        weights[0] * ngram_bleu +
        weights[1] * line_match_score +
        weights[2] * keyword_match
    )
    
    return final_score


def count_parameters(model: Any = None, params_dict: dict | None = None) -> float:
    """统计模型参数量（百万）
    
    支持 PyTorch 模型或手动传入参数字典。
    
    Args:
        model: PyTorch 模型对象（可选）
        params_dict: 参数字典，格式为 {"name": param_count}（可选）
        
    Returns:
        float: 参数量（百万）
    """
    total_params = 0
    
    if model is not None:
        try:
            for p in model.parameters():
                total_params += p.numel()
            return total_params / 1_000_000
        except Exception as e:
            logger.warning(f"Failed to count model parameters: {e}")
    
    if params_dict is not None:
        total_params = sum(params_dict.values())
        return total_params / 1_000_000
    
    return 0.0


def inference_benchmark(
    inference_fn: Callable,
    test_inputs: list[Any],
    num_runs: int = 10,
    warmup_runs: int = 3,
) -> dict[str, float]:
    """推理性能基准测试
    
    Args:
        inference_fn: 推理函数，接受输入返回输出
        test_inputs: 测试输入列表
        num_runs: 运行次数
        warmup_runs: 预热次数
        
    Returns:
        Dict[str, float]: 性能指标，包括：
            - avg_latency_ms: 平均延迟（毫秒）
            - median_latency_ms: 中位延迟（毫秒）
            - min_latency_ms: 最小延迟
            - max_latency_ms: 最大延迟
            - throughput_per_sec: 每秒吞吐量
            - p95_latency_ms: 95分位延迟
    """
    for _ in range(warmup_runs):
        for inp in test_inputs:
            try:
                inference_fn(inp)
            except Exception:
                pass
    
    latencies = []
    
    for _ in range(num_runs):
        for inp in test_inputs:
            start = time.perf_counter()
            try:
                inference_fn(inp)
            except Exception:
                continue
            end = time.perf_counter()
            latencies.append((end - start) * 1000)
    
    if not latencies:
        return {
            "avg_latency_ms": 0.0,
            "median_latency_ms": 0.0,
            "min_latency_ms": 0.0,
            "max_latency_ms": 0.0,
            "throughput_per_sec": 0.0,
            "p95_latency_ms": 0.0,
        }
    
    latencies.sort()
    n = len(latencies)
    
    avg_latency = sum(latencies) / n
    median_latency = latencies[n // 2]
    min_latency = latencies[0]
    max_latency = latencies[-1]
    
    p95_idx = int(n * 0.95)
    p95_latency = latencies[min(p95_idx, n - 1)]
    
    total_time = sum(latencies) / 1000.0
    throughput = n / total_time if total_time > 0 else 0.0
    
    return {
        "avg_latency_ms": avg_latency,
        "median_latency_ms": median_latency,
        "min_latency_ms": min_latency,
        "max_latency_ms": max_latency,
        "throughput_per_sec": throughput,
        "p95_latency_ms": p95_latency,
    }


def cost_effectiveness_ratio(
    quality_score: float,
    params_million: float,
    training_cost_usd: float = 0.0,
    inference_latency_ms: float = 0.0,
    weights: dict[str, float] | None = None,
) -> float:
    """成本效益比 — Antares 哲学核心指标
    
    综合考虑模型质量、参数量、训练成本、推理速度，
    计算"每单位成本获得的质量"。
    
    分数越高越好。
    
    Args:
        quality_score: 质量分数 (0-1)，越高越好
        params_million: 参数量（百万），越低越好
        training_cost_usd: 训练成本（美元），越低越好
        inference_latency_ms: 推理延迟（毫秒），越低越好
        weights: 各维度权重，默认：
            quality: 0.5
            params_efficiency: 0.2
            training_cost_efficiency: 0.15
            inference_efficiency: 0.15
        
    Returns:
        float: 成本效益比，越高越好
    """
    if weights is None:
        weights = {
            "quality": 0.5,
            "params_efficiency": 0.2,
            "training_cost_efficiency": 0.15,
            "inference_efficiency": 0.15,
        }
    
    quality_score = max(0.0, min(1.0, quality_score))
    
    baseline_params = 1000.0
    params_efficiency = min(1.0, baseline_params / max(params_million, 0.001))
    
    baseline_cost = 100.0
    cost_efficiency = min(1.0, baseline_cost / max(training_cost_usd, 0.001))
    
    baseline_latency = 1000.0
    inference_efficiency = min(1.0, baseline_latency / max(inference_latency_ms, 0.001))
    
    total_weight = sum(weights.values())
    if total_weight == 0:
        return quality_score
    
    cer = (
        weights.get("quality", 0) * quality_score +
        weights.get("params_efficiency", 0) * params_efficiency +
        weights.get("training_cost_efficiency", 0) * cost_efficiency +
        weights.get("inference_efficiency", 0) * inference_efficiency
    ) / total_weight
    
    return cer


def top_k_accuracy(
    y_true: list[int],
    y_scores: list[list[float]],
    k: int = 5,
) -> float:
    """Top-K 准确率
    
    Args:
        y_true: 真实标签列表
        y_scores: 预测分数列表，每个元素是所有类别的分数
        k: Top-K 的 K 值
        
    Returns:
        float: Top-K 准确率
    """
    if len(y_true) == 0:
        return 0.0
    
    correct = 0
    for true_label, scores in zip(y_true, y_scores):
        top_k_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        if true_label in top_k_indices:
            correct += 1
    
    return correct / len(y_true)


def confusion_matrix(
    y_true: list[int],
    y_pred: list[int],
    num_classes: int | None = None,
) -> list[list[int]]:
    """计算混淆矩阵
    
    Args:
        y_true: 真实标签列表
        y_pred: 预测标签列表
        num_classes: 类别数量，自动推断
        
    Returns:
        List[List[int]]: 混淆矩阵，[真实][预测]
    """
    if num_classes is None:
        all_labels = set(y_true) | set(y_pred)
        num_classes = max(all_labels) + 1 if all_labels else 0
    
    matrix = [[0] * num_classes for _ in range(num_classes)]
    
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            matrix[t][p] += 1
    
    return matrix
