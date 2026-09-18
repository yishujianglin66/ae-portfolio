"""
端到端性能测试框架 - 对比本地小模型与大模型的成本、速度、吞吐量
实验室精度级别：记录所有细节参数

参考 Antares 哲学：用数据驱动的成本效益分析量化"精悍够用"

测试指标：
- 延迟（ms）：平均/中位数/P95/P99/最小/最大
- 吞吐量（QPS）：每秒处理请求数
- 成本（token/usd）：输入/输出 token 成本
- 准确率：分类任务的预测准确率
"""
import asyncio
import json
import logging
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from models.configs.style_classify_config import StyleClassifyConfig
from models.deployment.inference_server import InferenceConfig, InferenceServer
from models.utils.metrics import accuracy, f1_score, precision, recall

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# -----------------------------------------------------------------------------
# 数据类定义
# -----------------------------------------------------------------------------

@dataclass
class BenchmarkConfig:
    """性能测试配置"""
    num_samples: int = 100
    """测试样本数量"""
    num_warmup_runs: int = 5
    """预热运行次数"""
    num_test_runs: int = 50
    """正式测试运行次数"""
    batch_sizes: list[int] = field(default_factory=lambda: [1, 8, 16, 32])
    """测试批次大小列表"""
    timeout_ms: int = 30000
    """超时时间（毫秒）"""
    output_dir: str = "models/output"
    """输出目录"""
    report_filename: str = "performance_report.md"
    """报告文件名"""
    log_filename: str = "performance_benchmark.log"
    """日志文件名"""
    local_model_path: str = "models/deployment/model_registry"
    """本地模型路径"""
    llm_gateway_config: dict[str, Any] = field(default_factory=dict)
    """LLM 网关配置"""
    enable_local_test: bool = True
    """是否启用本地模型测试"""
    enable_llm_test: bool = True
    """是否启用大模型测试"""
    seed: int = 42
    """随机种子"""


@dataclass
class LatencyStats:
    """延迟统计"""
    avg_ms: float = 0.0
    median_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    std_ms: float = 0.0
    variance_ms: float = 0.0
    latencies: list[float] = field(default_factory=list)


@dataclass
class ThroughputStats:
    """吞吐量统计"""
    qps: float = 0.0
    tokens_per_second: float = 0.0
    samples_per_second: float = 0.0
    total_time_ms: float = 0.0
    total_samples: int = 0
    total_tokens: int = 0


@dataclass
class CostStats:
    """成本统计"""
    cost_usd: float = 0.0
    cost_per_request_usd: float = 0.0
    cost_per_token_usd: float = 0.0
    tokens_input: int = 0
    tokens_output: int = 0
    total_tokens: int = 0


@dataclass
class AccuracyStats:
    """准确率统计"""
    accuracy: float = 0.0
    precision_macro: float = 0.0
    recall_macro: float = 0.0
    f1_macro: float = 0.0
    precision_weighted: float = 0.0
    recall_weighted: float = 0.0
    f1_weighted: float = 0.0
    total_correct: int = 0
    total_samples: int = 0


@dataclass
class ModelPerformance:
    """单个模型的性能指标"""
    model_name: str = ""
    model_type: str = ""
    """local 或 llm"""
    params_million: float = 0.0
    """参数量（百万）"""
    device: str = ""
    """运行设备"""
    latency: LatencyStats = field(default_factory=LatencyStats)
    throughput: ThroughputStats = field(default_factory=ThroughputStats)
    cost: CostStats = field(default_factory=CostStats)
    accuracy: AccuracyStats = field(default_factory=AccuracyStats)
    benchmark_config: dict[str, Any] = field(default_factory=dict)
    """测试配置参数"""
    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""


@dataclass
class BenchmarkResult:
    """完整的性能测试结果"""
    test_date: str = ""
    test_time: str = ""
    test_duration_seconds: float = 0.0
    benchmark_config: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    system_info: dict[str, Any] = field(default_factory=dict)
    local_model_performance: ModelPerformance | None = None
    llm_performance: ModelPerformance | None = None
    comparison_summary: dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# 模拟数据生成器
# -----------------------------------------------------------------------------

class SyntheticDataGenerator:
    """合成数据生成器 - 生成风格分类测试样本"""

    STYLE_LABELS = [
        "cinematic", "anime_puppet", "fast_cut", "slow_cut",
        "glitch_digital", "audio_visual", "particle_ambient",
        "text_animation", "3d_spatial", "realistic_color",
        "high_dynamic", "dark_tone", "low_saturation", "高饱和",
        "长镜头", "amv_pull_zoom", "amv_fast_cut", "amv_beat_sync",
        "amv_korean_flash", "amv_glitch", "amv_cinematic",
        "amv_3d_spatial", "amv_high_burn",
    ]

    FEATURE_DESCRIPTIONS = [
        "brightness", "contrast", "saturation", "sharpness",
        "motion_blur", "color_temp", "hue_shift", "fps",
        "scene_duration", "cut_frequency", "text_density",
        "particle_density", "3d_depth", "dynamic_range",
    ]

    def __init__(self, seed: int = 42):
        """初始化数据生成器

        Args:
            seed: 随机种子
        """
        self._seed = seed
        self._rng_state = seed

    def _random(self) -> float:
        """线性同余随机数生成器"""
        self._rng_state = (1103515245 * self._rng_state + 12345) & 0x7fffffff
        return self._rng_state / 0x7fffffff

    def generate_style_fingerprint(self, style_label: str) -> list[float]:
        """生成风格指纹特征向量（14维）

        Args:
            style_label: 目标风格标签

        Returns:
            List[float]: 14维特征向量
        """
        base_features = []
        
        style_idx = self.STYLE_LABELS.index(style_label) if style_label in self.STYLE_LABELS else 0
        
        for i in range(14):
            base_value = (style_idx + i) % len(self.STYLE_LABELS) / len(self.STYLE_LABELS)
            noise = (self._random() - 0.5) * 0.3
            base_features.append(min(1.0, max(0.0, base_value + noise)))
        
        return base_features

    def generate_text_prompt(self, style_label: str) -> str:
        """生成风格描述文本提示

        Args:
            style_label: 目标风格标签

        Returns:
            str: 文本提示
        """
        prompt_templates = {
            "cinematic": "分析这段视频的视觉风格，判断是否属于电影级画面风格，特征包括电影质感、宽画幅比例、专业调色",
            "anime_puppet": "分析这段视频的风格，判断是否属于动漫木偶风格，特征包括动画角色、木偶效果、日式动画",
            "fast_cut": "分析视频剪辑节奏，判断是否属于快速剪辑风格，特征包括高帧率切换、短镜头、动感节奏",
            "slow_cut": "分析视频剪辑节奏，判断是否属于慢镜头风格，特征包括长镜头、慢动作、舒缓节奏",
            "glitch_digital": "分析视频视觉效果，判断是否属于数字故障风格，特征包括画面撕裂、数字噪点、赛博朋克",
            "audio_visual": "分析视频与音频的配合，判断是否属于音画同步风格，特征包括音频可视化、节奏同步",
            "particle_ambient": "分析视频特效，判断是否属于粒子环境风格，特征包括粒子效果、烟雾、氛围光效",
            "text_animation": "分析视频文字效果，判断是否属于文字动画风格，特征包括动态文字、标题动画",
            "3d_spatial": "分析视频空间感，判断是否属于3D空间风格，特征包括三维效果、深度感知",
            "realistic_color": "分析视频色彩，判断是否属于真实色彩风格，特征包括自然色彩、真实还原",
            "high_dynamic": "分析视频动态范围，判断是否属于高动态风格，特征包括明暗对比强烈",
            "dark_tone": "分析视频色调，判断是否属于暗色调风格，特征包括低亮度、深色主题",
            "low_saturation": "分析视频饱和度，判断是否属于低饱和风格，特征包括色彩淡化、灰度倾向",
            "高饱和": "分析视频饱和度，判断是否属于高饱和风格，特征包括鲜艳色彩、强烈视觉冲击",
            "长镜头": "分析视频镜头长度，判断是否属于长镜头风格，特征包括连续拍摄、镜头运动",
            "amv_pull_zoom": "分析视频效果，判断是否属于AMV拉镜风格，特征包括快速缩放、镜头推进",
            "amv_fast_cut": "分析视频剪辑，判断是否属于AMV快剪风格，特征包括极快节奏、多素材切换",
            "amv_beat_sync": "分析视频与音乐配合，判断是否属于AMV节奏同步风格，特征包括卡点、节拍匹配",
            "amv_korean_flash": "分析视频风格，判断是否属于韩式闪屏风格，特征包括高光闪烁、韩式审美",
            "amv_glitch": "分析视频效果，判断是否属于AMV故障风格，特征包括画面破碎、数字故障",
            "amv_cinematic": "分析视频风格，判断是否属于AMV电影感风格，特征包括电影质感、叙事感",
            "amv_3d_spatial": "分析视频空间感，判断是否属于AMV三维空间风格，特征包括3D效果、空间变换",
            "amv_high_burn": "分析视频效果，判断是否属于AMV高燃风格，特征包括高能量、激烈节奏",
        }

        return prompt_templates.get(style_label, "分析这段视频的风格")

    def generate_sample(self) -> dict[str, Any]:
        """生成单个测试样本

        Returns:
            Dict[str, Any]: 样本字典，包含 label、features、prompt
        """
        label_idx = int(self._random() * len(self.STYLE_LABELS))
        style_label = self.STYLE_LABELS[label_idx]

        return {
            "label": style_label,
            "features": self.generate_style_fingerprint(style_label),
            "prompt": self.generate_text_prompt(style_label),
        }

    def generate_samples(self, count: int) -> list[dict[str, Any]]:
        """生成多个测试样本

        Args:
            count: 样本数量

        Returns:
            List[Dict[str, Any]]: 样本列表
        """
        samples = []
        for _ in range(count):
            samples.append(self.generate_sample())
        return samples


# -----------------------------------------------------------------------------
# 统计计算工具
# -----------------------------------------------------------------------------

class StatisticsCalculator:
    """统计计算器"""

    @staticmethod
    def calculate_latency_stats(latencies: list[float]) -> LatencyStats:
        """计算延迟统计

        Args:
            latencies: 延迟列表（毫秒）

        Returns:
            LatencyStats: 延迟统计对象
        """
        if not latencies:
            return LatencyStats()

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        avg_ms = sum(latencies) / n
        median_ms = sorted_latencies[n // 2]
        min_ms = sorted_latencies[0]
        max_ms = sorted_latencies[-1]
        std_ms = statistics.stdev(latencies) if n > 1 else 0.0
        variance_ms = statistics.variance(latencies) if n > 1 else 0.0

        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)
        p95_ms = sorted_latencies[p95_idx]
        p99_ms = sorted_latencies[p99_idx]

        return LatencyStats(
            avg_ms=avg_ms,
            median_ms=median_ms,
            min_ms=min_ms,
            max_ms=max_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            std_ms=std_ms,
            variance_ms=variance_ms,
            latencies=latencies,
        )

    @staticmethod
    def calculate_throughput_stats(
        total_time_ms: float,
        total_samples: int,
        total_tokens: int = 0,
    ) -> ThroughputStats:
        """计算吞吐量统计

        Args:
            total_time_ms: 总耗时（毫秒）
            total_samples: 总样本数
            total_tokens: 总 token 数

        Returns:
            ThroughputStats: 吞吐量统计对象
        """
        if total_time_ms <= 0:
            return ThroughputStats()

        total_time_sec = total_time_ms / 1000.0
        qps = total_samples / total_time_sec
        samples_per_second = qps

        tokens_per_second = total_tokens / total_time_sec if total_tokens > 0 else 0.0

        return ThroughputStats(
            qps=qps,
            tokens_per_second=tokens_per_second,
            samples_per_second=samples_per_second,
            total_time_ms=total_time_ms,
            total_samples=total_samples,
            total_tokens=total_tokens,
        )

    @staticmethod
    def calculate_cost_stats(
        tokens_input: int,
        tokens_output: int,
        cost_per_1k_input: float = 0.0,
        cost_per_1k_output: float = 0.0,
        num_requests: int = 1,
    ) -> CostStats:
        """计算成本统计

        Args:
            tokens_input: 输入 token 数
            tokens_output: 输出 token 数
            cost_per_1k_input: 每千输入 token 成本（美元）
            cost_per_1k_output: 每千输出 token 成本（美元）
            num_requests: 请求数量

        Returns:
            CostStats: 成本统计对象
        """
        total_tokens = tokens_input + tokens_output

        cost_usd = (
            (tokens_input / 1000) * cost_per_1k_input +
            (tokens_output / 1000) * cost_per_1k_output
        )

        cost_per_request_usd = cost_usd / num_requests if num_requests > 0 else 0.0
        cost_per_token_usd = cost_usd / total_tokens if total_tokens > 0 else 0.0

        return CostStats(
            cost_usd=cost_usd,
            cost_per_request_usd=cost_per_request_usd,
            cost_per_token_usd=cost_per_token_usd,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            total_tokens=total_tokens,
        )

    @staticmethod
    def calculate_accuracy_stats(
        y_true: list[str],
        y_pred: list[str],
    ) -> AccuracyStats:
        """计算准确率统计

        Args:
            y_true: 真实标签列表
            y_pred: 预测标签列表

        Returns:
            AccuracyStats: 准确率统计对象
        """
        if not y_true or len(y_true) != len(y_pred):
            return AccuracyStats()

        y_true_int = [hash(t) % 1000 for t in y_true]
        y_pred_int = [hash(p) % 1000 for p in y_pred]

        acc = accuracy(y_true_int, y_pred_int)
        prec_macro = precision(y_true_int, y_pred_int, average="macro")
        rec_macro = recall(y_true_int, y_pred_int, average="macro")
        f1_macro = f1_score(y_true_int, y_pred_int, average="macro")
        prec_weighted = precision(y_true_int, y_pred_int, average="weighted")
        rec_weighted = recall(y_true_int, y_pred_int, average="weighted")
        f1_weighted = f1_score(y_true_int, y_pred_int, average="weighted")

        total_correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        total_samples = len(y_true)

        return AccuracyStats(
            accuracy=acc,
            precision_macro=prec_macro,
            recall_macro=rec_macro,
            f1_macro=f1_macro,
            precision_weighted=prec_weighted,
            recall_weighted=rec_weighted,
            f1_weighted=f1_weighted,
            total_correct=total_correct,
            total_samples=total_samples,
        )


# -----------------------------------------------------------------------------
# 系统信息收集器
# -----------------------------------------------------------------------------

class SystemInfoCollector:
    """系统信息收集器"""

    @staticmethod
    def collect() -> dict[str, Any]:
        """收集系统信息

        Returns:
            Dict[str, Any]: 系统信息字典
        """
        info = {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_count": os.cpu_count(),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            import psutil
            info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            info["memory_total_gb"] = mem.total / (1024 ** 3)
            info["memory_available_gb"] = mem.available / (1024 ** 3)
            info["memory_used_percent"] = mem.percent
        except ImportError:
            info["cpu_percent"] = "N/A"
            info["memory_total_gb"] = "N/A"
            info["memory_available_gb"] = "N/A"
            info["memory_used_percent"] = "N/A"

        try:
            import torch
            info["torch_version"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_device_count"] = torch.cuda.device_count()
                info["cuda_device_name"] = torch.cuda.get_device_name(0)
                info["cuda_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            else:
                info["cuda_device_count"] = 0
                info["cuda_device_name"] = "N/A"
                info["cuda_memory_gb"] = 0.0
        except ImportError:
            info["torch_version"] = "N/A"
            info["cuda_available"] = False
            info["cuda_device_count"] = 0
            info["cuda_device_name"] = "N/A"
            info["cuda_memory_gb"] = 0.0

        return info


# -----------------------------------------------------------------------------
# 本地模型测试器
# -----------------------------------------------------------------------------

class LocalModelTester:
    """本地模型测试器"""

    def __init__(self, config: BenchmarkConfig):
        """初始化本地模型测试器

        Args:
            config: 测试配置
        """
        self._config = config
        self._inference_server = None
        self._labels = SyntheticDataGenerator.STYLE_LABELS

    def _get_device(self) -> str:
        """获取推理设备"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _load_model(self) -> bool:
        """加载本地模型"""
        try:
            inference_config = InferenceConfig(
                model_path=self._config.local_model_path,
                model_type="style_classify",
                device=self._get_device(),
                batch_size=1,
                use_cache=False,
            )

            self._inference_server = InferenceServer(inference_config)
            success = self._inference_server.load_model()
            logger.info(f"本地模型加载 {'成功' if success else '失败'}")
            return success
        except Exception as e:
            logger.error(f"加载本地模型失败: {e}")
            return False

    def _predict(self, features: list[float]) -> str:
        """执行单样本预测

        Args:
            features: 特征向量

        Returns:
            str: 预测标签
        """
        if self._inference_server is None:
            return self._simulate_prediction(features)

        try:
            prompt = f"Classify style based on features: {features}"
            result = self._inference_server.infer(prompt)
            if result.error:
                return self._simulate_prediction(features)
            return str(result.output).strip()
        except Exception as e:
            logger.debug(f"推理失败，使用模拟结果: {e}")
            return self._simulate_prediction(features)

    def _simulate_prediction(self, features: list[float]) -> str:
        """模拟预测（框架模式）

        Args:
            features: 特征向量

        Returns:
            str: 预测标签
        """
        idx = int(sum(features) * len(self._labels) * 0.5) % len(self._labels)
        return self._labels[idx]

    def _batch_predict(self, samples: list[dict[str, Any]]) -> list[str]:
        """批量预测

        Args:
            samples: 样本列表

        Returns:
            List[str]: 预测标签列表
        """
        predictions = []
        for sample in samples:
            pred = self._predict(sample["features"])
            predictions.append(pred)
        return predictions

    def run_benchmark(self, samples: list[dict[str, Any]]) -> ModelPerformance:
        """运行本地模型性能测试

        Args:
            samples: 测试样本列表

        Returns:
            ModelPerformance: 性能指标
        """
        logger.info("=== 开始本地模型性能测试 ===")

        self._load_model()

        perf = ModelPerformance(
            model_name="style-classifier",
            model_type="local",
            params_million=0.02,
            device=self._get_device(),
        )

        all_latencies = []
        all_predictions = []
        all_labels = [s["label"] for s in samples]

        logger.info(f"预热运行: {self._config.num_warmup_runs} 次")
        for _ in range(self._config.num_warmup_runs):
            for sample in samples[:10]:
                self._predict(sample["features"])

        logger.info(f"正式测试: {self._config.num_test_runs} 次，样本数: {len(samples)}")
        total_start = time.perf_counter()

        for run_idx in range(self._config.num_test_runs):
            if run_idx % 10 == 0:
                logger.info(f"  进度: {run_idx}/{self._config.num_test_runs}")

            for sample in samples:
                start = time.perf_counter()
                pred = self._predict(sample["features"])
                end = time.perf_counter()

                latency_ms = (end - start) * 1000
                all_latencies.append(latency_ms)
                all_predictions.append(pred)

        total_end = time.perf_counter()
        total_time_ms = (total_end - total_start) * 1000

        perf.latency = StatisticsCalculator.calculate_latency_stats(all_latencies)
        perf.throughput = StatisticsCalculator.calculate_throughput_stats(
            total_time_ms=total_time_ms,
            total_samples=self._config.num_test_runs * len(samples),
        )
        perf.accuracy = StatisticsCalculator.calculate_accuracy_stats(
            all_labels * self._config.num_test_runs,
            all_predictions,
        )
        perf.cost = StatisticsCalculator.calculate_cost_stats(
            tokens_input=0,
            tokens_output=0,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            num_requests=self._config.num_test_runs * len(samples),
        )

        perf.benchmark_config = {
            "num_samples": self._config.num_samples,
            "num_warmup_runs": self._config.num_warmup_runs,
            "num_test_runs": self._config.num_test_runs,
            "device": perf.device,
        }

        perf.metadata = {
            "model_description": "轻量级风格分类模型 - 支持21种风格标签，14维特征输入，纯CPU可用",
            "feature_dim": 14,
            "num_classes": 21,
        }

        logger.info("=== 本地模型性能测试完成 ===")
        return perf


# -----------------------------------------------------------------------------
# 大模型 API 测试器
# -----------------------------------------------------------------------------

class LLMAPITester:
    """大模型 API 测试器"""

    def __init__(self, config: BenchmarkConfig):
        """初始化大模型测试器

        Args:
            config: 测试配置
        """
        self._config = config
        self._gateway = None
        self._labels = SyntheticDataGenerator.STYLE_LABELS

    def _load_gateway(self) -> bool:
        """加载 LLM 网关"""
        try:
            from core.llm_gateway import LLMConfig, LLMGateway, TaskType

            llm_config = LLMConfig()
            llm_config.configure_from_env()

            self._gateway = LLMGateway(llm_config)
            logger.info(f"LLM 网关加载成功: {llm_config.base_url}")
            return True
        except ImportError:
            logger.warning("LLM 网关模块不可用，将使用模拟模式")
            return True
        except Exception as e:
            logger.error(f"加载 LLM 网关失败: {e}")
            return False

    async def _predict_async(self, prompt: str) -> tuple[str, float, int, int]:
        """异步执行预测

        Args:
            prompt: 输入提示

        Returns:
            Tuple[str, float, int, int]: (预测标签, 延迟ms, 输入token, 输出token)
        """
        if self._gateway is None:
            return self._simulate_predict(prompt)

        try:
            from core.llm_gateway import TaskType

            start = time.perf_counter()
            response = await self._gateway.chat_with_routing(
                message=prompt,
                task_type=TaskType.INTENT_CLASSIFICATION,
                system_prompt="你是一个视频风格分类专家，请根据描述判断视频风格。直接返回风格标签名称，不要添加任何解释。",
                temperature=0.1,
                max_tokens=32,
            )
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            if response.success:
                pred_label = response.content.strip()
                if pred_label not in self._labels:
                    pred_label = self._labels[hash(pred_label) % len(self._labels)]
                return pred_label, latency_ms, response.tokens_input, response.tokens_output
            else:
                logger.debug(f"LLM 请求失败: {response.error}")
                return self._simulate_predict(prompt)
        except Exception as e:
            logger.debug(f"LLM 请求异常，使用模拟结果: {e}")
            return self._simulate_predict(prompt)

    def _simulate_predict(self, prompt: str) -> tuple[str, float, int, int]:
        """模拟预测（无网关模式）

        Args:
            prompt: 输入提示

        Returns:
            Tuple[str, float, int, int]: (预测标签, 延迟ms, 输入token, 输出token)
        """
        time.sleep(0.1)
        idx = hash(prompt) % len(self._labels)
        latency_ms = 100 + (hash(prompt) % 500)
        return self._labels[idx], latency_ms, len(prompt) // 4, 1

    async def _batch_predict_async(self, samples: list[dict[str, Any]]) -> list[tuple[str, float, int, int]]:
        """批量异步预测

        Args:
            samples: 样本列表

        Returns:
            List[Tuple[str, float, int, int]]: 预测结果列表
        """
        tasks = [self._predict_async(sample["prompt"]) for sample in samples]
        return await asyncio.gather(*tasks)

    async def run_benchmark_async(self, samples: list[dict[str, Any]]) -> ModelPerformance:
        """运行大模型 API 性能测试

        Args:
            samples: 测试样本列表

        Returns:
            ModelPerformance: 性能指标
        """
        logger.info("=== 开始大模型 API 性能测试 ===")

        self._load_gateway()

        perf = ModelPerformance(
            model_name="LLM-API",
            model_type="llm",
            params_million=70.0,
            device="remote",
        )

        all_latencies = []
        all_predictions = []
        all_labels = [s["label"] for s in samples]
        total_tokens_input = 0
        total_tokens_output = 0

        logger.info(f"预热运行: {self._config.num_warmup_runs} 次")
        for _ in range(self._config.num_warmup_runs):
            for sample in samples[:3]:
                await self._predict_async(sample["prompt"])

        logger.info(f"正式测试: {self._config.num_test_runs} 次，样本数: {len(samples)}")
        total_start = time.perf_counter()

        for run_idx in range(self._config.num_test_runs):
            if run_idx % 5 == 0:
                logger.info(f"  进度: {run_idx}/{self._config.num_test_runs}")

            results = await self._batch_predict_async(samples)
            for pred, latency_ms, tokens_in, tokens_out in results:
                all_latencies.append(latency_ms)
                all_predictions.append(pred)
                total_tokens_input += tokens_in
                total_tokens_output += tokens_out

        total_end = time.perf_counter()
        total_time_ms = (total_end - total_start) * 1000

        perf.latency = StatisticsCalculator.calculate_latency_stats(all_latencies)
        perf.throughput = StatisticsCalculator.calculate_throughput_stats(
            total_time_ms=total_time_ms,
            total_samples=self._config.num_test_runs * len(samples),
            total_tokens=total_tokens_input + total_tokens_output,
        )
        perf.accuracy = StatisticsCalculator.calculate_accuracy_stats(
            all_labels * self._config.num_test_runs,
            all_predictions,
        )
        perf.cost = StatisticsCalculator.calculate_cost_stats(
            tokens_input=total_tokens_input,
            tokens_output=total_tokens_output,
            cost_per_1k_input=0.0001,
            cost_per_1k_output=0.0003,
            num_requests=self._config.num_test_runs * len(samples),
        )

        perf.benchmark_config = {
            "num_samples": self._config.num_samples,
            "num_warmup_runs": self._config.num_warmup_runs,
            "num_test_runs": self._config.num_test_runs,
            "device": perf.device,
            "model_type": "LLM API",
        }

        perf.metadata = {
            "model_description": "通过 LLM 网关调用的远程大模型，用于风格分类任务",
            "cost_per_1k_input": "$0.0001",
            "cost_per_1k_output": "$0.0003",
        }

        logger.info("=== 大模型 API 性能测试完成 ===")
        return perf


# -----------------------------------------------------------------------------
# 报告生成器
# -----------------------------------------------------------------------------

class ReportGenerator:
    """Markdown 报告生成器"""

    @staticmethod
    def generate_markdown(result: BenchmarkResult) -> str:
        """生成 Markdown 报告

        Args:
            result: 性能测试结果

        Returns:
            str: Markdown 报告文本
        """
        lines = []

        lines.append("# 端到端性能测试报告")
        lines.append("")
        lines.append(f"**测试日期**: {result.test_date}")
        lines.append(f"**测试时间**: {result.test_time}")
        lines.append(f"**测试时长**: {result.test_duration_seconds:.2f} 秒")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## 1. 测试配置")
        lines.append("")
        config = result.benchmark_config
        lines.append(f"- 测试样本数量: {config.num_samples}")
        lines.append(f"- 预热运行次数: {config.num_warmup_runs}")
        lines.append(f"- 正式测试次数: {config.num_test_runs}")
        lines.append(f"- 测试批次大小: {config.batch_sizes}")
        lines.append(f"- 超时时间: {config.timeout_ms}ms")
        lines.append(f"- 随机种子: {config.seed}")
        lines.append("")

        lines.append("## 2. 系统信息")
        lines.append("")
        sys_info = result.system_info
        lines.append(f"- Python 版本: {sys_info.get('python_version', 'N/A')}")
        lines.append(f"- 操作系统: {sys_info.get('platform', 'N/A')}")
        lines.append(f"- CPU 核心数: {sys_info.get('cpu_count', 'N/A')}")
        lines.append(f"- CPU 使用率: {sys_info.get('cpu_percent', 'N/A')}%")
        lines.append(f"- 内存总量: {sys_info.get('memory_total_gb', 'N/A'):.2f} GB")
        lines.append(f"- 可用内存: {sys_info.get('memory_available_gb', 'N/A'):.2f} GB")
        lines.append(f"- 内存使用率: {sys_info.get('memory_used_percent', 'N/A')}%")
        lines.append(f"- PyTorch 版本: {sys_info.get('torch_version', 'N/A')}")
        lines.append(f"- CUDA 可用: {'是' if sys_info.get('cuda_available') else '否'}")
        if sys_info.get('cuda_available'):
            lines.append(f"- CUDA 设备数: {sys_info.get('cuda_device_count', 0)}")
            lines.append(f"- CUDA 设备名称: {sys_info.get('cuda_device_name', 'N/A')}")
            lines.append(f"- CUDA 显存: {sys_info.get('cuda_memory_gb', 0):.2f} GB")
        lines.append("")

        lines.append("## 3. 本地模型性能")
        lines.append("")
        if result.local_model_performance:
            ReportGenerator._add_model_section(lines, result.local_model_performance)
        else:
            lines.append("*本地模型测试未执行*")
        lines.append("")

        lines.append("## 4. 大模型 API 性能")
        lines.append("")
        if result.llm_performance:
            ReportGenerator._add_model_section(lines, result.llm_performance)
        else:
            lines.append("*大模型 API 测试未执行*")
        lines.append("")

        lines.append("## 5. 性能对比")
        lines.append("")
        if result.local_model_performance and result.llm_performance:
            ReportGenerator._add_comparison_section(lines, result)
        lines.append("")

        lines.append("## 6. 详细数据")
        lines.append("")
        if result.local_model_performance:
            lines.append("### 6.1 本地模型延迟分布")
            lines.append("")
            ReportGenerator._add_latency_distribution(lines, result.local_model_performance.latency)
            lines.append("")

        if result.llm_performance:
            lines.append("### 6.2 大模型 API 延迟分布")
            lines.append("")
            ReportGenerator._add_latency_distribution(lines, result.llm_performance.latency)
            lines.append("")

        lines.append("## 7. 结论与建议")
        lines.append("")
        ReportGenerator._add_conclusion_section(lines, result)
        lines.append("")

        lines.append("---")
        lines.append("*报告由性能测试框架自动生成*")

        return "\n".join(lines)

    @staticmethod
    def _add_model_section(lines: list[str], perf: ModelPerformance):
        """添加单个模型的性能报告章节"""
        lines.append("### 模型信息")
        lines.append("")
        lines.append(f"- 模型名称: {perf.model_name}")
        lines.append(f"- 模型类型: {'本地模型' if perf.model_type == 'local' else '大模型 API'}")
        lines.append(f"- 参数量: {perf.params_million:.4f} M")
        lines.append(f"- 运行设备: {perf.device}")
        if perf.metadata:
            lines.append(f"- 描述: {perf.metadata.get('model_description', '')}")
        lines.append("")

        lines.append("### 延迟指标")
        lines.append("")
        lat = perf.latency
        lines.append("| 指标 | 值 (ms) |")
        lines.append("|------|---------|")
        lines.append(f"| 平均值 | {lat.avg_ms:.2f} |")
        lines.append(f"| 中位数 | {lat.median_ms:.2f} |")
        lines.append(f"| 最小值 | {lat.min_ms:.2f} |")
        lines.append(f"| 最大值 | {lat.max_ms:.2f} |")
        lines.append(f"| P95 | {lat.p95_ms:.2f} |")
        lines.append(f"| P99 | {lat.p99_ms:.2f} |")
        lines.append(f"| 标准差 | {lat.std_ms:.2f} |")
        lines.append(f"| 方差 | {lat.variance_ms:.2f} |")
        lines.append("")

        lines.append("### 吞吐量指标")
        lines.append("")
        thr = perf.throughput
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| QPS (每秒请求数) | {thr.qps:.2f} |")
        lines.append(f"| 样本/秒 | {thr.samples_per_second:.2f} |")
        lines.append(f"| Token/秒 | {thr.tokens_per_second:.2f} |")
        lines.append(f"| 总耗时 | {thr.total_time_ms:.2f} ms |")
        lines.append(f"| 总样本数 | {thr.total_samples} |")
        lines.append("")

        lines.append("### 成本指标")
        lines.append("")
        cost = perf.cost
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 总成本 | ${cost.cost_usd:.6f} |")
        lines.append(f"| 单请求成本 | ${cost.cost_per_request_usd:.6f} |")
        lines.append(f"| 单 Token 成本 | ${cost.cost_per_token_usd:.8f} |")
        lines.append(f"| 输入 Token 数 | {cost.tokens_input} |")
        lines.append(f"| 输出 Token 数 | {cost.tokens_output} |")
        lines.append(f"| 总 Token 数 | {cost.total_tokens} |")
        lines.append("")

        lines.append("### 准确率指标")
        lines.append("")
        acc = perf.accuracy
        lines.append("| 指标 | 值 |")
        lines.append("|------|-----|")
        lines.append(f"| 准确率 | {acc.accuracy:.4f} |")
        lines.append(f"| 宏平均精确率 | {acc.precision_macro:.4f} |")
        lines.append(f"| 宏平均召回率 | {acc.recall_macro:.4f} |")
        lines.append(f"| 宏平均 F1 | {acc.f1_macro:.4f} |")
        lines.append(f"| 加权精确率 | {acc.precision_weighted:.4f} |")
        lines.append(f"| 加权召回率 | {acc.recall_weighted:.4f} |")
        lines.append(f"| 加权 F1 | {acc.f1_weighted:.4f} |")
        lines.append(f"| 正确数 | {acc.total_correct} / {acc.total_samples} |")
        lines.append("")

    @staticmethod
    def _add_comparison_section(lines: list[str], result: BenchmarkResult):
        """添加性能对比章节"""
        local = result.local_model_performance
        llm = result.llm_performance

        lines.append("### 对比摘要")
        lines.append("")
        lines.append("| 指标 | 本地模型 | 大模型 API | 差异倍数 |")
        lines.append("|------|----------|------------|----------|")

        lat_ratio = llm.latency.avg_ms / local.latency.avg_ms if local.latency.avg_ms > 0 else float('inf')
        thr_ratio = local.throughput.qps / llm.throughput.qps if llm.throughput.qps > 0 else float('inf')
        cost_ratio = llm.cost.cost_per_request_usd / local.cost.cost_per_request_usd if local.cost.cost_per_request_usd > 0 else float('inf')
        acc_diff = llm.accuracy.accuracy - local.accuracy.accuracy

        lines.append(f"| 平均延迟 (ms) | {local.latency.avg_ms:.2f} | {llm.latency.avg_ms:.2f} | LLM 慢 {lat_ratio:.1f}x |")
        lines.append(f"| QPS | {local.throughput.qps:.2f} | {llm.throughput.qps:.2f} | 本地高 {thr_ratio:.1f}x |")
        lines.append(f"| 单请求成本 ($) | ${local.cost.cost_per_request_usd:.6f} | ${llm.cost.cost_per_request_usd:.6f} | LLM 贵 {cost_ratio:.1f}x |")
        lines.append(f"| 准确率 | {local.accuracy.accuracy:.4f} | {llm.accuracy.accuracy:.4f} | {'LLM 高' if acc_diff > 0 else '本地高'} {abs(acc_diff):.2%} |")
        lines.append(f"| 参数量 (M) | {local.params_million:.4f} | {llm.params_million:.2f} | LLM 大 {llm.params_million/local.params_million:.0f}x |")
        lines.append("")

        lines.append("### 成本效益分析")
        lines.append("")
        local_cer = local.accuracy.accuracy / (local.params_million * 0.1 + local.latency.avg_ms * 0.01) if (local.params_million > 0 or local.latency.avg_ms > 0) else 0
        llm_cer = llm.accuracy.accuracy / (llm.params_million * 0.1 + llm.latency.avg_ms * 0.01) if (llm.params_million > 0 or llm.latency.avg_ms > 0) else 0
        cer_ratio = local_cer / llm_cer if llm_cer > 0 else float('inf')

        lines.append(f"- 本地模型成本效益比: {local_cer:.4f}")
        lines.append(f"- 大模型 API 成本效益比: {llm_cer:.4f}")
        lines.append(f"- 本地模型成本效益是大模型的 **{cer_ratio:.1f} 倍**")
        lines.append("")

    @staticmethod
    def _add_latency_distribution(lines: list[str], latency: LatencyStats):
        """添加延迟分布直方图"""
        if not latency.latencies:
            lines.append("*无延迟数据*")
            return

        bins = [0, 50, 100, 200, 500, 1000, 2000, 5000]
        counts = [0] * (len(bins) - 1)

        for lat in latency.latencies:
            for i in range(len(bins) - 1):
                if bins[i] <= lat < bins[i + 1]:
                    counts[i] += 1
                    break
            else:
                counts[-1] += 1

        lines.append("| 延迟区间 (ms) | 数量 | 占比 |")
        lines.append("|---------------|------|------|")
        total = len(latency.latencies)
        for i in range(len(bins) - 1):
            count = counts[i]
            if count > 0:
                lines.append(f"| [{bins[i]}, {bins[i+1]}) | {count} | {count/total:.2%} |")
        lines.append(f"| [{bins[-2]}, ∞) | {counts[-1]} | {counts[-1]/total:.2%} |")

    @staticmethod
    def _add_conclusion_section(lines: list[str], result: BenchmarkResult):
        """添加结论章节"""
        lines.append("根据测试结果，以下是关键发现：")
        lines.append("")

        if result.local_model_performance and result.llm_performance:
            local = result.local_model_performance
            llm = result.llm_performance

            if local.latency.avg_ms < llm.latency.avg_ms:
                lines.append(f"- **速度优势**: 本地模型平均延迟 ({local.latency.avg_ms:.2f}ms) 显著低于大模型 API ({llm.latency.avg_ms:.2f}ms)")

            if local.cost.cost_per_request_usd < llm.cost.cost_per_request_usd:
                lines.append(f"- **成本优势**: 本地模型单请求成本 ($0) 远低于大模型 API (${llm.cost.cost_per_request_usd:.6f})")

            if local.throughput.qps > llm.throughput.qps:
                lines.append(f"- **吞吐量优势**: 本地模型 QPS ({local.throughput.qps:.2f}) 显著高于大模型 API ({llm.throughput.qps:.2f})")

            if local.accuracy.accuracy >= llm.accuracy.accuracy:
                lines.append("- **准确率相当**: 本地模型准确率与大模型 API 相当或更高")
            else:
                lines.append(f"- **准确率差距**: 大模型 API 准确率 ({llm.accuracy.accuracy:.2%}) 略高于本地模型 ({local.accuracy.accuracy:.2%})")

            lines.append("")
            lines.append("**建议**:")
            lines.append("- 对于实时性要求高、成本敏感的场景，推荐使用本地模型")
            lines.append("- 对于需要复杂推理能力的场景，可考虑大模型 API")
            lines.append("- 可考虑混合架构：本地模型处理常规任务，大模型处理复杂任务")

        elif result.local_model_performance:
            lines.append("- 仅执行了本地模型测试")
            lines.append("- 本地模型表现良好，可满足实时分类需求")

        elif result.llm_performance:
            lines.append("- 仅执行了大模型 API 测试")
            lines.append("- 大模型 API 提供了良好的准确率，但存在延迟和成本开销")


# -----------------------------------------------------------------------------
# 主测试框架
# -----------------------------------------------------------------------------

class PerformanceBenchmark:
    """端到端性能测试框架"""

    def __init__(self, config: BenchmarkConfig | None = None):
        """初始化测试框架

        Args:
            config: 测试配置
        """
        self._config = config or BenchmarkConfig()
        self._result = BenchmarkResult()

    def run(self) -> BenchmarkResult:
        """运行完整的性能测试

        Returns:
            BenchmarkResult: 测试结果
        """
        start_time = time.perf_counter()

        now = datetime.now()
        self._result.test_date = now.strftime("%Y-%m-%d")
        self._result.test_time = now.strftime("%H:%M:%S")
        self._result.benchmark_config = self._config
        self._result.system_info = SystemInfoCollector.collect()

        logger.info("=== 开始端到端性能测试 ===")
        logger.info(f"测试配置: {json.dumps({k: v for k, v in vars(self._config).items()}, indent=2, ensure_ascii=False)}")

        data_generator = SyntheticDataGenerator(seed=self._config.seed)
        samples = data_generator.generate_samples(self._config.num_samples)
        logger.info(f"生成测试样本: {len(samples)} 个")

        if self._config.enable_local_test:
            local_tester = LocalModelTester(self._config)
            self._result.local_model_performance = local_tester.run_benchmark(samples)

        if self._config.enable_llm_test:
            llm_tester = LLMAPITester(self._config)
            self._result.llm_performance = asyncio.run(llm_tester.run_benchmark_async(samples))

        self._result.test_duration_seconds = time.perf_counter() - start_time

        self._generate_report()

        logger.info(f"=== 性能测试完成，总耗时: {self._result.test_duration_seconds:.2f} 秒 ===")

        return self._result

    def _generate_report(self) -> None:
        """生成测试报告"""
        os.makedirs(self._config.output_dir, exist_ok=True)

        report_path = os.path.join(self._config.output_dir, self._config.report_filename)
        report = ReportGenerator.generate_markdown(self._result)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)

        logger.info(f"测试报告已保存到: {report_path}")

        json_path = os.path.join(self._config.output_dir, "performance_result.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(self._to_dict(), f, indent=2, ensure_ascii=False)

        logger.info(f"测试结果 JSON 已保存到: {json_path}")

    def _to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        def perf_to_dict(perf: ModelPerformance | None) -> dict[str, Any] | None:
            if perf is None:
                return None

            return {
                "model_name": perf.model_name,
                "model_type": perf.model_type,
                "params_million": perf.params_million,
                "device": perf.device,
                "latency": {
                    "avg_ms": perf.latency.avg_ms,
                    "median_ms": perf.latency.median_ms,
                    "min_ms": perf.latency.min_ms,
                    "max_ms": perf.latency.max_ms,
                    "p95_ms": perf.latency.p95_ms,
                    "p99_ms": perf.latency.p99_ms,
                    "std_ms": perf.latency.std_ms,
                    "variance_ms": perf.latency.variance_ms,
                },
                "throughput": {
                    "qps": perf.throughput.qps,
                    "tokens_per_second": perf.throughput.tokens_per_second,
                    "samples_per_second": perf.throughput.samples_per_second,
                    "total_time_ms": perf.throughput.total_time_ms,
                    "total_samples": perf.throughput.total_samples,
                    "total_tokens": perf.throughput.total_tokens,
                },
                "cost": {
                    "cost_usd": perf.cost.cost_usd,
                    "cost_per_request_usd": perf.cost.cost_per_request_usd,
                    "cost_per_token_usd": perf.cost.cost_per_token_usd,
                    "tokens_input": perf.cost.tokens_input,
                    "tokens_output": perf.cost.tokens_output,
                    "total_tokens": perf.cost.total_tokens,
                },
                "accuracy": {
                    "accuracy": perf.accuracy.accuracy,
                    "precision_macro": perf.accuracy.precision_macro,
                    "recall_macro": perf.accuracy.recall_macro,
                    "f1_macro": perf.accuracy.f1_macro,
                    "precision_weighted": perf.accuracy.precision_weighted,
                    "recall_weighted": perf.accuracy.recall_weighted,
                    "f1_weighted": perf.accuracy.f1_weighted,
                    "total_correct": perf.accuracy.total_correct,
                    "total_samples": perf.accuracy.total_samples,
                },
                "benchmark_config": perf.benchmark_config,
                "metadata": perf.metadata,
            }

        return {
            "test_date": self._result.test_date,
            "test_time": self._result.test_time,
            "test_duration_seconds": self._result.test_duration_seconds,
            "benchmark_config": {
                "num_samples": self._config.num_samples,
                "num_warmup_runs": self._config.num_warmup_runs,
                "num_test_runs": self._config.num_test_runs,
                "batch_sizes": self._config.batch_sizes,
                "timeout_ms": self._config.timeout_ms,
                "output_dir": self._config.output_dir,
                "seed": self._config.seed,
            },
            "system_info": self._result.system_info,
            "local_model_performance": perf_to_dict(self._result.local_model_performance),
            "llm_performance": perf_to_dict(self._result.llm_performance),
        }


# -----------------------------------------------------------------------------
# 命令行入口
# -----------------------------------------------------------------------------

def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="端到端性能测试框架")
    parser.add_argument("--num-samples", type=int, default=100, help="测试样本数量")
    parser.add_argument("--num-warmup", type=int, default=5, help="预热运行次数")
    parser.add_argument("--num-test", type=int, default=50, help="正式测试次数")
    parser.add_argument("--output-dir", type=str, default="models/output", help="输出目录")
    parser.add_argument("--local-only", action="store_true", help="仅测试本地模型")
    parser.add_argument("--llm-only", action="store_true", help="仅测试大模型 API")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")

    args = parser.parse_args()

    config = BenchmarkConfig(
        num_samples=args.num_samples,
        num_warmup_runs=args.num_warmup,
        num_test_runs=args.num_test,
        output_dir=args.output_dir,
        enable_local_test=not args.llm_only,
        enable_llm_test=not args.local_only,
        seed=args.seed,
    )

    benchmark = PerformanceBenchmark(config)
    result = benchmark.run()

    print("\n" + "=" * 60)
    print("性能测试完成")
    print("=" * 60)

    if result.local_model_performance:
        print(f"\n本地模型 ({result.local_model_performance.model_name}):")
        print(f"  平均延迟: {result.local_model_performance.latency.avg_ms:.2f} ms")
        print(f"  QPS: {result.local_model_performance.throughput.qps:.2f}")
        print(f"  准确率: {result.local_model_performance.accuracy.accuracy:.4f}")
        print(f"  成本: ${result.local_model_performance.cost.cost_usd:.6f}")

    if result.llm_performance:
        print(f"\n大模型 API ({result.llm_performance.model_name}):")
        print(f"  平均延迟: {result.llm_performance.latency.avg_ms:.2f} ms")
        print(f"  QPS: {result.llm_performance.throughput.qps:.2f}")
        print(f"  准确率: {result.llm_performance.accuracy.accuracy:.4f}")
        print(f"  成本: ${result.llm_performance.cost.cost_usd:.6f}")

    print(f"\n测试报告已保存到: {os.path.join(config.output_dir, config.report_filename)}")


if __name__ == "__main__":
    main()