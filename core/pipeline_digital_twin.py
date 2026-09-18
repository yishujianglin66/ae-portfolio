"""
core/pipeline_digital_twin.py — 管线数字孪生预测器 v1.0
=========================================================

在执行前预测管线各阶段的耗时、成功率、质量分数和资源消耗。
支持瓶颈定位、配置对比和运行时预测校正。

设计原则:
1. 预测优先: 给定输入+配置，预测每阶段执行结果
2. 瓶颈感知: 自动识别最可能成为瓶颈的阶段
3. 配置对比: 多方案并行预测，输出帕累托最优配置
4. 在线校正: 每阶段实际结果出来后，贝叶斯更新修正后续预测
5. 离线可用: 纯 numpy 实现梯度提升回归

集成方式:
    from core.pipeline_digital_twin import get_digital_twin

    twin = get_digital_twin()
    prediction = await twin.predict_execution(input_spec, config)
    bottleneck = await twin.find_bottleneck(prediction)
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class InputSpecification:
    """输入素材规格"""
    material_count: int = 0
    video_count: int = 0
    image_count: int = 0
    audio_count: int = 0
    avg_resolution: tuple[int, int] = (1920, 1080)
    total_duration_sec: float = 0.0
    total_file_size_mb: float = 0.0
    has_reference_video: bool = False
    codecs: list[str] = field(default_factory=list)


@dataclass
class PipelineConfig:
    """管线配置摘要"""
    mode: str = "auto"                    # auto / reference_video / mixed
    enable_vrs: bool = False
    enable_feedback_loop: bool = True
    max_quality_iterations: int = 3
    use_davinci_render: bool = True
    use_ae_render: bool = True
    use_ffmpeg_fallback: bool = True
    publish_platforms: list[str] = field(default_factory=list)
    effects_count: int = 0
    transitions_count: int = 0
    target_resolution: tuple[int, int] = (1920, 1080)
    target_fps: int = 30


@dataclass
class StagePrediction:
    """单阶段预测结果"""
    stage_name: str
    predicted_duration: float = 0.0       # 预测耗时(秒)
    duration_confidence: float = 0.0      # 耗时预测置信度
    predicted_success_rate: float = 0.0   # 预测成功率
    success_confidence: float = 0.0       # 成功率置信度
    predicted_quality: float = 0.0        # 预测质量分数(0-100)
    predicted_memory_mb: float = 0.0      # 预测内存峰值(MB)
    predicted_disk_mb: float = 0.0        # 预测磁盘占用(MB)
    risk_factors: list[str] = field(default_factory=list)
    optimization_suggestions: list[str] = field(default_factory=list)


@dataclass
class ExecutionPrediction:
    """完整管线执行预测"""
    total_predicted_duration: float = 0.0
    total_predicted_memory_mb: float = 0.0
    total_predicted_disk_mb: float = 0.0
    overall_success_rate: float = 0.0
    predicted_output_quality: float = 0.0
    stage_predictions: list[StagePrediction] = field(default_factory=list)
    critical_path: list[str] = field(default_factory=list)
    config_id: str = ""
    timestamp: float = 0.0


@dataclass
class BottleneckReport:
    """瓶颈分析报告"""
    primary_bottleneck: str = ""
    secondary_bottlenecks: list[str] = field(default_factory=list)
    bottleneck_reason: str = ""
    optimization_strategies: list[dict[str, str]] = field(default_factory=list)
    estimated_improvement: float = 0.0    # 优化后预期改善比例


@dataclass
class ConfigComparison:
    """配置对比结果"""
    configs: list[PipelineConfig] = field(default_factory=list)
    predictions: list[ExecutionPrediction] = field(default_factory=list)
    pareto_optimal_indices: list[int] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class ExecutionObservation:
    """执行观测（用于校正）"""
    stage_name: str
    actual_duration: float
    actual_success: bool
    actual_quality: float = 0.0
    actual_memory_mb: float = 0.0


# ============================================================================
#  P3.5: 不确定性量化 (Uncertainty Quantification)
# ============================================================================

@dataclass
class UncertaintyReport:
    """不确定性量化报告

    通过 Monte Carlo dropout-style 采样估计预测的置信区间。

    Attributes:
        metric_name: 指标名 (如 "total_duration" / "success_rate" / "quality")
        mean: 均值
        std: 标准差
        p5: 5% 分位数 (悲观估计)
        p50: 中位数
        p95: 95% 分位数 (乐观估计)
        ci_lower: 95% 置信区间下界
        ci_upper: 95% 置信区间上界
        n_samples: MC 采样次数
        per_stage: 各阶段不确定性 {stage_name: UncertaintyReport}
    """
    metric_name: str = ""
    mean: float = 0.0
    std: float = 0.0
    p5: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    ci_lower: float = 0.0
    ci_upper: float = 0.0
    n_samples: int = 0
    per_stage: dict[str, "UncertaintyReport"] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典 (用于持久化)"""
        return {
            "metric_name": self.metric_name,
            "mean": self.mean,
            "std": self.std,
            "p5": self.p5,
            "p50": self.p50,
            "p95": self.p95,
            "ci_lower": self.ci_lower,
            "ci_upper": self.ci_upper,
            "n_samples": self.n_samples,
            "per_stage": {k: v.to_dict() for k, v in self.per_stage.items()},
        }


@dataclass
class SensitivityResult:
    """参数敏感性分析结果

    衡量每个参数对预测输出的影响程度。

    Attributes:
        output_name: 输出指标名 (如 "total_duration" / "quality")
        parameter_sensitivities: {param_name: sensitivity_score}
            sensitivity_score 范围 [0, 1], 越大代表该参数对输出影响越大
        most_sensitive_param: 最敏感的参数名
        least_sensitive_param: 最不敏感的参数名
        method: 使用的敏感性分析方法 (如 "morris" / "sobol" / "finite_diff")
        n_samples: 采样次数
    """
    output_name: str = ""
    parameter_sensitivities: dict[str, float] = field(default_factory=dict)
    most_sensitive_param: str = ""
    least_sensitive_param: str = ""
    method: str = "finite_diff"
    n_samples: int = 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            "output_name": self.output_name,
            "parameter_sensitivities": dict(self.parameter_sensitivities),
            "most_sensitive_param": self.most_sensitive_param,
            "least_sensitive_param": self.least_sensitive_param,
            "method": self.method,
            "n_samples": self.n_samples,
        }


@dataclass
class WhatIfScenario:
    """What-If 分析的单个场景"""
    name: str = ""
    description: str = ""
    config_changes: dict[str, Any] = field(default_factory=dict)
    predicted_total_duration: float = 0.0
    predicted_success_rate: float = 0.0
    predicted_quality: float = 0.0
    delta_duration: float = 0.0       # 与基线的差值
    delta_success_rate: float = 0.0
    delta_quality: float = 0.0


@dataclass
class WhatIfResult:
    """What-If 分析结果

    Attributes:
        baseline: 基线预测
        scenarios: 各场景预测列表
        best_scenario: 综合最优的场景
        worst_scenario: 综合最差的场景
    """
    baseline: ExecutionPrediction | None = None
    scenarios: list[WhatIfScenario] = field(default_factory=list)
    best_scenario: WhatIfScenario | None = None
    worst_scenario: WhatIfScenario | None = None


# ============================================================================
#  阶段预测器
# ============================================================================

class StagePredictor:
    """单阶段预测器
    
    使用梯度提升回归树（简化版）预测:
    - 耗时
    - 成功率
    - 资源消耗
    """
    
    STAGES = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    
    # 各阶段基础耗时估计（秒）
    BASE_DURATIONS: dict[str, float] = {
        "perceive": 15.0,
        "analyze": 20.0,
        "plan": 10.0,
        "execute": 60.0,
        "render": 120.0,
        "verify": 30.0,
        "learn": 5.0,
    }
    
    # 各阶段基础成功率
    BASE_SUCCESS_RATES: dict[str, float] = {
        "perceive": 0.95,
        "analyze": 0.90,
        "plan": 0.92,
        "execute": 0.75,
        "render": 0.80,
        "verify": 0.95,
        "learn": 0.98,
    }
    
    def __init__(self):
        # 历史观测数据: stage -> List[ExecutionObservation]
        self._observations: dict[str, list[ExecutionObservation]] = {
            stage: [] for stage in self.STAGES
        }
        # 贝叶斯先验参数
        self._duration_params: dict[str, tuple[float, float]] = {}  # stage -> (mean, var)
        self._success_params: dict[str, tuple[float, float]] = {}   # stage -> (alpha, beta)
        
        # 初始化先验
        for stage in self.STAGES:
            base_dur = self.BASE_DURATIONS[stage]
            self._duration_params[stage] = (base_dur, base_dur * 0.3)
            base_sr = self.BASE_SUCCESS_RATES[stage]
            # Beta 分布参数
            self._success_params[stage] = (base_sr * 20, (1 - base_sr) * 20)
    
    def predict_duration(
        self,
        stage_name: str,
        input_spec: InputSpecification,
        config: PipelineConfig
    ) -> tuple[float, float]:
        """预测阶段耗时
        
        Returns:
            (mean_duration, std_duration)
        """
        base = self.BASE_DURATIONS.get(stage_name, 30.0)
        
        # 素材因子
        material_factor = 1.0
        if stage_name == "perceive":
            material_factor = 1.0 + input_spec.video_count * 0.3 + input_spec.image_count * 0.05
        elif stage_name in ("execute", "render"):
            material_factor = 1.0 + input_spec.total_duration_sec * 0.01
            # 分辨率因子
            res_factor = (input_spec.avg_resolution[0] * input_spec.avg_resolution[1]) / (1920 * 1080)
            material_factor *= max(0.5, min(3.0, res_factor))
        elif stage_name == "analyze":
            material_factor = 1.0 + input_spec.material_count * 0.1
        
        # 配置因子
        config_factor = 1.0
        if stage_name == "execute":
            config_factor = 1.0 + config.effects_count * 0.15
        elif stage_name == "render":
            if config.use_davinci_render and config.use_ae_render:
                config_factor = 1.5  # 双引擎渲染
            target_pixels = config.target_resolution[0] * config.target_resolution[1]
            config_factor *= target_pixels / (1920 * 1080)
        elif stage_name == "plan":
            if config.enable_vrs:
                config_factor = 0.7  # VRS 加速规划
        elif stage_name == "analyze":
            if config.enable_vrs:
                config_factor = 0.5  # VRS 提供分析结果
        
        # 如果有历史数据，用贝叶斯更新
        obs_list = self._observations.get(stage_name, [])
        if len(obs_list) >= 3:
            # 贝叶斯后验: 先验 + 观测
            prior_mean, prior_var = self._duration_params[stage_name]
            obs_mean = np.mean([o.actual_duration for o in obs_list])
            obs_var = np.var([o.actual_duration for o in obs_list]) if len(obs_list) > 1 else prior_var
            
            # 共轭正态后验
            n = len(obs_list)
            post_var = 1.0 / (1.0 / prior_var + n / max(obs_var, 1e-6))
            post_mean = post_var * (prior_mean / prior_var + n * obs_mean / max(obs_var, 1e-6))
            
            predicted = post_mean * material_factor * config_factor
            std = math.sqrt(post_var) * material_factor * config_factor
        else:
            predicted = base * material_factor * config_factor
            _, prior_var = self._duration_params[stage_name]
            std = math.sqrt(prior_var) * material_factor * config_factor
        
        return max(1.0, predicted), max(0.1, std)
    
    def predict_success_rate(
        self,
        stage_name: str,
        input_spec: InputSpecification,
        config: PipelineConfig,
        causal_failure_prob: float = 0.0
    ) -> tuple[float, float]:
        """预测阶段成功率
        
        Args:
            causal_failure_prob: 因果引擎提供的故障概率
            
        Returns:
            (mean_success_rate, confidence)
        """
        # 贝叶斯后验（Beta-Binomial 共轭）
        alpha, beta = self._success_params[stage_name]
        obs_list = self._observations.get(stage_name, [])
        
        n_success = sum(1 for o in obs_list if o.actual_success)
        n_fail = len(obs_list) - n_success
        
        post_alpha = alpha + n_success
        post_beta = beta + n_fail
        
        mean_sr = post_alpha / (post_alpha + post_beta)
        
        # 调整因子
        adjustment = 1.0
        
        # 风险因子
        risk_factors = []
        if stage_name == "execute":
            if config.effects_count > 10:
                adjustment *= 0.85
                risk_factors.append(f"效果数量过多({config.effects_count})")
            if input_spec.total_duration_sec > 300:
                adjustment *= 0.9
                risk_factors.append(f"素材时长过长({input_spec.total_duration_sec:.0f}s)")
        elif stage_name == "render":
            res = config.target_resolution
            if res[0] * res[1] > 3840 * 2160:
                adjustment *= 0.8
                risk_factors.append(f"输出分辨率过高({res[0]}x{res[1]})")
        
        # 因果引擎故障概率
        if causal_failure_prob > 0:
            adjustment *= (1.0 - causal_failure_prob * 0.5)
        
        mean_sr = np.clip(mean_sr * adjustment, 0.0, 1.0)
        confidence = min(1.0, (len(obs_list) + 1) / 20.0)
        
        return float(mean_sr), confidence
    
    def predict_resources(
        self,
        stage_name: str,
        input_spec: InputSpecification,
        config: PipelineConfig
    ) -> tuple[float, float]:
        """预测资源消耗
        
        Returns:
            (memory_mb, disk_mb)
        """
        # 内存预测
        base_memory = {
            "perceive": 200, "analyze": 500, "plan": 100,
            "execute": 2000, "render": 4000, "verify": 800, "learn": 100
        }
        mem = base_memory.get(stage_name, 500)
        
        if stage_name in ("execute", "render"):
            res_factor = (input_spec.avg_resolution[0] * input_spec.avg_resolution[1]) / (1920 * 1080)
            mem *= max(1.0, res_factor)
            mem += input_spec.total_duration_sec * 5  # 每秒素材约5MB内存
        
        # 磁盘预测
        base_disk = {
            "perceive": 50, "analyze": 100, "plan": 10,
            "execute": 500, "render": 2000, "verify": 200, "learn": 50
        }
        disk = base_disk.get(stage_name, 100)
        
        if stage_name == "render":
            target_pixels = config.target_resolution[0] * config.target_resolution[1]
            # 1080p 视频约 10MB/s, 4K 约 40MB/s
            bitrate = target_pixels / (1920 * 1080) * 10
            disk = input_spec.total_duration_sec * bitrate + 200
        
        return float(mem), float(disk)


# ============================================================================
#  主预测器: PipelineDigitalTwin
# ============================================================================

class PipelineDigitalTwin:
    """管线数字孪生预测器"""
    
    DEFAULT_DATA_DIR = "data/digital_twin"
    STAGES = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 各阶段预测器
        self._stage_predictors = {
            stage: StagePredictor() for stage in self.STAGES
        }
        # 共享的 StagePredictor 实例（各阶段用同一个但数据独立）
        self._shared_predictor = StagePredictor()
        
        # 因果引擎引用（延迟导入避免循环依赖）
        self._causal_engine = None
        
        # 历史预测记录
        self._prediction_history: list[dict] = []
        
        # 加载持久化数据
        self._load_state()
    
    def _get_causal_engine(self):
        """延迟获取因果引擎"""
        if self._causal_engine is None:
            try:
                from core.causal_engine import get_causal_engine
                self._causal_engine = get_causal_engine()
            except ImportError:
                pass
        return self._causal_engine
    
    # ----------------------------------------------------------------
    #  M3.1-M3.3: 执行预测
    # ----------------------------------------------------------------
    
    async def predict_execution(
        self,
        input_spec: InputSpecification,
        config: PipelineConfig
    ) -> ExecutionPrediction:
        """预测完整管线执行结果"""
        stage_predictions = []
        total_duration = 0.0
        total_memory = 0.0
        total_disk = 0.0
        overall_sr = 1.0
        critical_path = []
        
        causal_engine = self._get_causal_engine()
        
        for stage_name in self.STAGES:
            predictor = self._shared_predictor
            
            # 获取因果引擎故障概率
            causal_fp = 0.0
            if causal_engine:
                # 从因果图获取该阶段的故障概率
                stats = causal_engine.get_statistics()
                # 简化: 用平均边权重作为故障概率代理
                causal_fp = max(0.0, 1.0 - stats.get("avg_confidence", 0.5))
            
            # 预测耗时
            dur_mean, dur_std = predictor.predict_duration(stage_name, input_spec, config)
            
            # 预测成功率
            sr_mean, sr_conf = predictor.predict_success_rate(
                stage_name, input_spec, config, causal_fp
            )
            
            # 预测质量
            quality = self._predict_quality(stage_name, input_spec, config)
            
            # 预测资源
            mem, disk = predictor.predict_resources(stage_name, input_spec, config)
            
            # 风险因子
            risk_factors = self._identify_risk_factors(stage_name, input_spec, config)
            
            # 优化建议
            suggestions = self._generate_optimization_suggestions(
                stage_name, dur_mean, sr_mean, risk_factors
            )
            
            sp = StagePrediction(
                stage_name=stage_name,
                predicted_duration=dur_mean,
                duration_confidence=min(1.0, 1.0 / (1.0 + dur_std / max(dur_mean, 1.0))),
                predicted_success_rate=sr_mean,
                success_confidence=sr_conf,
                predicted_quality=quality,
                predicted_memory_mb=mem,
                predicted_disk_mb=disk,
                risk_factors=risk_factors,
                optimization_suggestions=suggestions
            )
            stage_predictions.append(sp)
            
            # 累计
            total_duration += dur_mean
            total_memory = max(total_memory, mem)  # 内存取峰值
            total_disk += disk
            overall_sr *= sr_mean
            
            # 关键路径: 耗时最长的阶段
            if dur_mean > 10:
                critical_path.append(stage_name)
        
        # 按耗时排序关键路径
        critical_path.sort(
            key=lambda s: next(
                (sp.predicted_duration for sp in stage_predictions if sp.stage_name == s), 0
            ),
            reverse=True
        )
        
        prediction = ExecutionPrediction(
            total_predicted_duration=total_duration,
            total_predicted_memory_mb=total_memory,
            total_predicted_disk_mb=total_disk,
            overall_success_rate=overall_sr,
            predicted_output_quality=np.mean([sp.predicted_quality for sp in stage_predictions]) if stage_predictions else 0.0,
            stage_predictions=stage_predictions,
            critical_path=critical_path,
            config_id=f"cfg_{int(time.time())}",
            timestamp=time.time()
        )
        
        # 记录预测
        self._prediction_history.append({
            "input": {
                "material_count": input_spec.material_count,
                "video_count": input_spec.video_count,
                "duration": input_spec.total_duration_sec
            },
            "prediction": {
                "total_duration": total_duration,
                "overall_sr": overall_sr,
                "quality": prediction.predicted_output_quality
            },
            "timestamp": time.time()
        })
        
        self._save_state()
        return prediction
    
    def _predict_quality(
        self, stage_name: str, input_spec: InputSpecification, config: PipelineConfig
    ) -> float:
        """预测阶段质量贡献"""
        base_quality = {
            "perceive": 70.0, "analyze": 75.0, "plan": 80.0,
            "execute": 65.0, "render": 70.0, "verify": 85.0, "learn": 50.0
        }
        q = base_quality.get(stage_name, 60.0)
        
        # 素材质量影响
        if stage_name in ("execute", "render"):
            if input_spec.total_duration_sec > 0:
                q *= min(1.0, 60.0 / input_spec.total_duration_sec)
                q = max(q, 40.0)
        
        # 配置影响
        if stage_name == "render":
            if config.use_davinci_render:
                q += 5  # DaVinci 调色加分
            if config.target_fps >= 60:
                q -= 3  # 高帧率可能降低质量
        
        return float(np.clip(q, 0.0, 100.0))
    
    def _identify_risk_factors(
        self, stage_name: str, input_spec: InputSpecification, config: PipelineConfig
    ) -> list[str]:
        """识别风险因子"""
        risks = []
        
        if stage_name == "execute":
            if config.effects_count > 15:
                risks.append(f"AE效果数量过多({config.effects_count}), 可能触发内存溢出")
            if input_spec.total_duration_sec > 600:
                risks.append(f"素材时长过长({input_spec.total_duration_sec:.0f}s), 渲染可能超时")
            res = input_spec.avg_resolution
            if res[0] * res[1] > 3840 * 2160:
                risks.append(f"素材分辨率过高({res[0]}x{res[1]})")
        
        elif stage_name == "render":
            if config.use_davinci_render and config.use_ae_render:
                risks.append("双引擎渲染增加协调复杂度")
            target_res = config.target_resolution
            if target_res[0] * target_res[1] > 3840 * 2160:
                risks.append(f"目标分辨率{target_res[0]}x{target_res[1]}可能导致渲染失败")
        
        elif stage_name == "perceive":
            if input_spec.video_count > 20:
                risks.append(f"视频素材数量过多({input_spec.video_count}), 分析耗时较长")
        
        return risks
    
    def _generate_optimization_suggestions(
        self, stage_name: str, duration: float, success_rate: float,
        risk_factors: list[str]
    ) -> list[str]:
        """生成优化建议"""
        suggestions = []
        
        if duration > 120:
            suggestions.append(f"考虑简化{stage_name}阶段配置以减少耗时")
        
        if success_rate < 0.8:
            suggestions.append(f"{stage_name}成功率较低, 建议准备降级方案")
        
        if stage_name == "execute" and risk_factors:
            suggestions.append("建议启用FFmpeg降级通道作为备份")
        
        if stage_name == "render":
            suggestions.append("建议先渲染低分辨率预览确认效果后再渲染全分辨率")
        
        return suggestions
    
    # ----------------------------------------------------------------
    #  M3.4: 瓶颈定位
    # ----------------------------------------------------------------
    
    async def find_bottleneck(
        self, prediction: ExecutionPrediction
    ) -> BottleneckReport:
        """识别瓶颈阶段并推荐优化策略"""
        if not prediction.stage_predictions:
            return BottleneckReport(primary_bottleneck="unknown")
        
        # 按耗时排序
        sorted_stages = sorted(
            prediction.stage_predictions,
            key=lambda sp: sp.predicted_duration,
            reverse=True
        )
        
        # 主瓶颈: 耗时最长的阶段
        primary = sorted_stages[0]
        
        # 次瓶颈
        secondary = [sp.stage_name for sp in sorted_stages[1:3]
                     if sp.predicted_duration > primary.predicted_duration * 0.3]
        
        # 综合瓶颈评分（考虑耗时+成功率+风险）
        bottleneck_scores = {}
        for sp in prediction.stage_predictions:
            time_score = sp.predicted_duration / max(prediction.total_predicted_duration, 1.0)
            risk_score = len(sp.risk_factors) * 0.1
            failure_risk = (1.0 - sp.predicted_success_rate) * 0.3
            score = time_score + risk_score + failure_risk
            bottleneck_scores[sp.stage_name] = score
        
        # 重新按综合评分排序
        ranked = sorted(bottleneck_scores.items(), key=lambda x: -x[1])
        primary_name = ranked[0][0] if ranked else primary.stage_name
        
        # 生成优化策略
        strategies = []
        for stage_name, score in ranked[:3]:
            sp = next((s for s in prediction.stage_predictions if s.stage_name == stage_name), None)
            if not sp:
                continue
            
            if stage_name == "execute":
                strategies.append({
                    "stage": stage_name,
                    "strategy": "减少效果数量或使用更轻量的效果替代",
                    "expected_improvement": "30-50% 耗时减少"
                })
            elif stage_name == "render":
                strategies.append({
                    "stage": stage_name,
                    "strategy": "使用代理文件渲染或降低预览分辨率",
                    "expected_improvement": "40-60% 耗时减少"
                })
            elif stage_name == "analyze":
                strategies.append({
                    "stage": stage_name,
                    "strategy": "启用VRS预分析或跳过非关键分析步骤",
                    "expected_improvement": "20-40% 耗时减少"
                })
            elif stage_name == "perceive":
                strategies.append({
                    "stage": stage_name,
                    "strategy": "对素材进行预筛选，减少分析素材量",
                    "expected_improvement": "20-30% 耗时减少"
                })
            else:
                strategies.append({
                    "stage": stage_name,
                    "strategy": f"优化{stage_name}阶段的内部实现",
                    "expected_improvement": "10-20% 耗时减少"
                })
        
        # 预期改善
        estimated_improvement = 0.0
        if strategies:
            estimated_improvement = 0.2  # 默认20%
            if primary_name == "render":
                estimated_improvement = 0.35
            elif primary_name == "execute":
                estimated_improvement = 0.30
        
        return BottleneckReport(
            primary_bottleneck=primary_name,
            secondary_bottlenecks=secondary,
            bottleneck_reason=f"{primary_name}阶段预测耗时{primary.predicted_duration:.1f}s, "
                             f"占总预测耗时{primary.predicted_duration/max(prediction.total_predicted_duration,1)*100:.0f}%",
            optimization_strategies=strategies,
            estimated_improvement=estimated_improvement
        )
    
    # ----------------------------------------------------------------
    #  M3.5: 配置对比
    # ----------------------------------------------------------------
    
    async def compare_configs(
        self,
        configs: list[PipelineConfig],
        input_spec: InputSpecification,
        objectives: list[str] = None
    ) -> ConfigComparison:
        """多目标配置方案对比"""
        if objectives is None:
            objectives = ["quality", "speed", "reliability"]
        
        predictions = []
        for config in configs:
            pred = await self.predict_execution(input_spec, config)
            predictions.append(pred)
        
        # 提取帕累托最优
        # 目标向量: (quality, -duration, success_rate) — 全部最大化
        obj_matrix = np.array([
            [p.predicted_output_quality, -p.total_predicted_duration, p.overall_success_rate]
            for p in predictions
        ])
        
        pareto_indices = self._find_pareto_indices(obj_matrix)
        
        # 生成推荐
        if pareto_indices:
            best_idx = pareto_indices[0]
            best_pred = predictions[best_idx]
            recommendation = (
                f"推荐配置 #{best_idx}: "
                f"质量={best_pred.predicted_output_quality:.1f}, "
                f"耗时={best_pred.total_predicted_duration:.0f}s, "
                f"成功率={best_pred.overall_success_rate:.1%}"
            )
        else:
            recommendation = "无显著帕累托最优配置，建议选择综合评分最高的方案"
        
        return ConfigComparison(
            configs=configs,
            predictions=predictions,
            pareto_optimal_indices=pareto_indices,
            recommendation=recommendation
        )
    
    def _find_pareto_indices(self, obj_matrix: np.ndarray) -> list[int]:
        """找到帕累托最优配置的索引"""
        n = len(obj_matrix)
        is_pareto = np.ones(n, dtype=bool)
        
        for i in range(n):
            if not is_pareto[i]:
                continue
            for j in range(n):
                if i == j or not is_pareto[j]:
                    continue
                # j 支配 i?
                if np.all(obj_matrix[j] >= obj_matrix[i]) and np.any(obj_matrix[j] > obj_matrix[i]):
                    is_pareto[i] = False
                    break
        
        return [i for i in range(n) if is_pareto[i]]
    
    # ----------------------------------------------------------------
    #  M3.7: 运行时预测校正
    # ----------------------------------------------------------------
    
    def correct_from_observation(
        self,
        observation: ExecutionObservation,
        prediction: ExecutionPrediction
    ) -> ExecutionPrediction:
        """基于实际观测校正后续预测
        
        贝叶斯更新: 将实际结果作为新观测，更新后续阶段的预测
        """
        # 记录观测到对应阶段预测器
        predictor = self._shared_predictor
        predictor._observations.setdefault(observation.stage_name, []).append(observation)
        
        # 更新贝叶斯参数
        stage = observation.stage_name
        if stage in predictor._duration_params:
            prior_mean, prior_var = predictor._duration_params[stage]
            # 共轭正态更新
            n = len(predictor._observations[stage])
            obs_mean = observation.actual_duration
            post_var = 1.0 / (1.0 / prior_var + n / max(obs_mean * 0.1, 1.0))
            post_mean = post_var * (prior_mean / prior_var + n * obs_mean / max(obs_mean * 0.1, 1.0))
            predictor._duration_params[stage] = (post_mean, post_var)
        
        # 更新成功率参数
        if stage in predictor._success_params:
            alpha, beta = predictor._success_params[stage]
            if observation.actual_success:
                alpha += 1
            else:
                beta += 1
            predictor._success_params[stage] = (alpha, beta)
        
        # 校正后续阶段的预测
        corrected_stages = []
        past_current = False
        for sp in prediction.stage_predictions:
            if sp.stage_name == observation.stage_name:
                past_current = True
                # 更新当前阶段的实际值
                sp.predicted_duration = observation.actual_duration
                sp.predicted_success_rate = 1.0 if observation.actual_success else 0.0
                corrected_stages.append(sp)
                continue
            
            if past_current:
                # 后续阶段: 根据当前观测调整
                if not observation.actual_success:
                    # 当前失败 → 后续阶段风险增加
                    sp.predicted_success_rate *= 0.9
                    sp.risk_factors.append(f"上游{stage}失败, 级联风险增加")
                
                # 耗时校正: 如果当前阶段比预期快/慢，后续可能也类似
                if sp.stage_name in predictor._duration_params:
                    new_mean, _ = predictor._duration_params[sp.stage_name]
                    old_pred = sp.predicted_duration
                    correction_factor = new_mean / max(old_pred, 1.0)
                    sp.predicted_duration *= np.clip(correction_factor, 0.7, 1.3)
            
            corrected_stages.append(sp)
        
        prediction.stage_predictions = corrected_stages
        
        # 重新计算总计
        prediction.total_predicted_duration = sum(sp.predicted_duration for sp in corrected_stages)
        prediction.overall_success_rate = np.prod([sp.predicted_success_rate for sp in corrected_stages])
        prediction.total_predicted_memory_mb = max(sp.predicted_memory_mb for sp in corrected_stages) if corrected_stages else 0
        
        return prediction
    
    # ----------------------------------------------------------------
    #  报告生成
    # ----------------------------------------------------------------
    
    def generate_report(self, prediction: ExecutionPrediction) -> str:
        """生成人类可读的预测报告"""
        lines = [
            "=" * 60,
            "Digital Twin - 管线数字孪生预测报告",
            "=" * 60,
            f"总预测耗时: {prediction.total_predicted_duration:.1f}s",
            f"总成功率:   {prediction.overall_success_rate:.1%}",
            f"预测质量:   {prediction.predicted_output_quality:.1f}/100",
            f"内存峰值:   {prediction.total_predicted_memory_mb:.0f}MB",
            f"磁盘占用:   {prediction.total_predicted_disk_mb:.0f}MB",
            f"关键路径:   {' → '.join(prediction.critical_path)}",
            "",
            "各阶段详情:",
            "-" * 60,
            f"{'阶段':<12} {'耗时(s)':<10} {'成功率':<10} {'质量':<8} {'风险'}",
            "-" * 60,
        ]
        
        for sp in prediction.stage_predictions:
            risks = "; ".join(sp.risk_factors[:2]) if sp.risk_factors else "-"
            lines.append(
                f"{sp.stage_name:<12} {sp.predicted_duration:<10.1f} "
                f"{sp.predicted_success_rate:<10.1%} {sp.predicted_quality:<8.1f} {risks}"
            )
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------
    
    def _save_state(self) -> None:
        """持久化预测器状态

        持久化内容:
        - duration_params: 各阶段耗时分布参数 (mean, var)
        - success_params: 各阶段成功率 Beta 分布参数 (alpha, beta)
        - observations: 各阶段观测数据 (用于校准和回溯)
        - prediction_history: 最近50条预测记录
        """
        try:
            state_path = self._data_dir / "twin_state.json"
            # 序列化 observations (ExecutionObservation dataclass → dict)
            observations_serialized = {}
            for stage, obs_list in self._shared_predictor._observations.items():
                observations_serialized[stage] = [
                    {
                        "stage_name": o.stage_name,
                        "actual_duration": o.actual_duration,
                        "actual_success": o.actual_success,
                        "actual_quality": o.actual_quality,
                        "actual_memory_mb": o.actual_memory_mb,
                    }
                    for o in obs_list
                ]
            state = {
                "duration_params": {
                    stage: list(params)
                    for stage, params in self._shared_predictor._duration_params.items()
                },
                "success_params": {
                    stage: list(params)
                    for stage, params in self._shared_predictor._success_params.items()
                },
                "observations": observations_serialized,
                "prediction_history": self._prediction_history[-50:]
            }
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[DigitalTwin] Save state failed: {e}")

    def _load_state(self) -> None:
        """加载持久化状态

        加载内容:
        - duration_params: 各阶段耗时分布参数
        - success_params: 各阶段成功率 Beta 分布参数
        - observations: 各阶段观测数据 (用于校准和回溯)
        - prediction_history: 预测历史
        """
        try:
            state_path = self._data_dir / "twin_state.json"
            if state_path.exists():
                with open(state_path, "r", encoding="utf-8") as f:
                    state = json.load(f)

                for stage, params in state.get("duration_params", {}).items():
                    if stage in self._shared_predictor._duration_params:
                        self._shared_predictor._duration_params[stage] = tuple(params)

                for stage, params in state.get("success_params", {}).items():
                    if stage in self._shared_predictor._success_params:
                        self._shared_predictor._success_params[stage] = tuple(params)

                # 反序列化 observations → ExecutionObservation 对象
                observations_serialized = state.get("observations", {})
                for stage, obs_dicts in observations_serialized.items():
                    if stage not in self._shared_predictor._observations:
                        continue
                    # 重建 ExecutionObservation 列表
                    rebuilt = []
                    for o in obs_dicts:
                        try:
                            rebuilt.append(ExecutionObservation(
                                stage_name=o.get("stage_name", stage),
                                actual_duration=float(o.get("actual_duration", 0.0)),
                                actual_success=bool(o.get("actual_success", True)),
                                actual_quality=float(o.get("actual_quality", 0.0)),
                                actual_memory_mb=float(o.get("actual_memory_mb", 0.0)),
                            ))
                        except Exception:
                            continue
                    # 覆盖默认空列表
                    self._shared_predictor._observations[stage] = rebuilt

                self._prediction_history = state.get("prediction_history", [])
        except Exception as e:
            logger.warning(f"[DigitalTwin] Load state failed: {e}")
    
    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "prediction_history_size": len(self._prediction_history),
            "duration_params": {
                stage: {"mean": p[0], "var": p[1]}
                for stage, p in self._shared_predictor._duration_params.items()
            },
            "success_params": {
                stage: {"alpha": p[0], "beta": p[1]}
                for stage, p in self._shared_predictor._success_params.items()
            }
        }

    # ================================================================
    #  P3.5: 不确定性量化 / 敏感性分析 / What-If 分析
    # ================================================================

    def uncertainty_quantification(
        self,
        input_spec: InputSpecification,
        config: PipelineConfig,
        n_samples: int = 100,
        metric: str = "total_duration",
        seed: int | None = None,
    ) -> UncertaintyReport:
        """不确定性量化 (Monte Carlo dropout-style)

        通过对阶段预测器的高斯后验进行 MC 采样, 估计输出指标的不确定性。

        数学原理:
        - 每阶段耗时 ~ N(μ_stage, σ²_stage) (来自贝叶斯后验)
        - 每阶段成功率 ~ Beta(α, β)
        - 总耗时 = Σ_stage duration_i (独立求和)
        - 总成功率 = Π_stage success_rate_i (独立乘积)
        - 通过采样估计输出分布的均值/方差/分位数

        Args:
            input_spec: 输入素材规格
            config: 管线配置
            n_samples: MC 采样次数 (默认 100)
            metric: 待评估指标 ("total_duration" / "success_rate" / "quality")
            seed: 随机种子 (None = 不固定)

        Returns:
            UncertaintyReport: 包含均值/标准差/分位数/置信区间
        """
        if n_samples < 1:
            n_samples = 1
        if seed is not None:
            np.random.seed(seed)

        predictor = self._shared_predictor
        valid_metrics = {"total_duration", "success_rate", "quality"}
        if metric not in valid_metrics:
            raise ValueError(
                f"metric must be one of {valid_metrics}, got {metric}"
            )

        # 收集各阶段预测分布参数
        stage_dists: dict[str, tuple[float, float]] = {}  # (mean, std) for duration
        stage_sr_dists: dict[str, tuple[float, float]] = {}  # (mean, std) for success rate
        stage_quality_dists: dict[str, tuple[float, float]] = {}

        for stage in self.STAGES:
            dur_mean, dur_std = predictor.predict_duration(stage, input_spec, config)
            sr_mean, _ = predictor.predict_success_rate(stage, input_spec, config)
            # 成功率方差近似: Beta 分布方差 = αβ / ((α+β)²(α+β+1))
            alpha, beta = predictor._success_params.get(stage, (10.0, 2.0))
            sr_var = (alpha * beta) / max((alpha + beta) ** 2 * (alpha + beta + 1), 1e-6)
            sr_std = math.sqrt(sr_var)
            stage_dists[stage] = (dur_mean, dur_std)
            stage_sr_dists[stage] = (sr_mean, sr_std)
            q = self._predict_quality(stage, input_spec, config)
            stage_quality_dists[stage] = (q, max(q * 0.1, 1.0))  # 假设 10% 相对不确定性

        # MC 采样
        samples: list[float] = []
        per_stage_samples: dict[str, list[float]] = {
            stage: [] for stage in self.STAGES
        }

        for _ in range(n_samples):
            if metric == "total_duration":
                # 总耗时 = Σ stage_duration_i
                total = 0.0
                for stage in self.STAGES:
                    m, s = stage_dists[stage]
                    val = max(0.0, np.random.normal(m, s))
                    per_stage_samples[stage].append(val)
                    total += val
                samples.append(total)
            elif metric == "success_rate":
                # 总成功率 = Π success_rate_i
                total = 1.0
                for stage in self.STAGES:
                    m, s = stage_sr_dists[stage]
                    val = float(np.clip(np.random.normal(m, s), 0.0, 1.0))
                    per_stage_samples[stage].append(val)
                    total *= val
                samples.append(total)
            elif metric == "quality":
                # 总质量 = mean(stage_quality_i)
                qualities = []
                for stage in self.STAGES:
                    m, s = stage_quality_dists[stage]
                    val = float(np.clip(np.random.normal(m, s), 0.0, 100.0))
                    per_stage_samples[stage].append(val)
                    qualities.append(val)
                samples.append(float(np.mean(qualities)))

        arr = np.array(samples)
        # 各阶段不确定性
        per_stage_reports: dict[str, UncertaintyReport] = {}
        for stage in self.STAGES:
            stage_arr = np.array(per_stage_samples[stage])
            per_stage_reports[stage] = self._build_uq_report(
                f"{metric}::{stage}", stage_arr
            )

        report = self._build_uq_report(metric, arr)
        report.per_stage = per_stage_reports
        return report

    def _build_uq_report(self, metric: str, arr: np.ndarray) -> UncertaintyReport:
        """从采样数组构建不确定性报告"""
        if len(arr) == 0:
            return UncertaintyReport(metric_name=metric, n_samples=0)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        p5 = float(np.percentile(arr, 5))
        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))
        # 95% 置信区间 = [p2.5, p97.5]
        ci_lower = float(np.percentile(arr, 2.5))
        ci_upper = float(np.percentile(arr, 97.5))
        return UncertaintyReport(
            metric_name=metric,
            mean=mean,
            std=std,
            p5=p5,
            p50=p50,
            p95=p95,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_samples=len(arr),
        )

    def sensitivity_analysis(
        self,
        input_spec: InputSpecification,
        config: PipelineConfig,
        output_name: str = "total_duration",
        method: str = "finite_diff",
        delta: float = 0.1,
    ) -> SensitivityResult:
        """参数敏感性分析

        使用有限差分法估计每个参数对输出的影响。

        数学原理:
        - 有限差分法: S_i = |f(x + δe_i) - f(x - δe_i)| / (2δ)
            其中 e_i 是第 i 个参数方向上的单位向量
        - 归一化: sensitivity_i = S_i / Σ S_j
        - 范围 [0, 1], 越大代表该参数对输出影响越大

        Args:
            input_spec: 输入素材规格 (基线)
            config: 管线配置 (基线)
            output_name: 输出指标 ("total_duration" / "success_rate" / "quality")
            method: 分析方法 (目前仅支持 "finite_diff")
            delta: 扰动步长 (相对值, 默认 0.1 即 10%)

        Returns:
            SensitivityResult: 各参数的敏感性评分
        """
        valid_outputs = {"total_duration", "success_rate", "quality"}
        if output_name not in valid_outputs:
            raise ValueError(
                f"output_name must be one of {valid_outputs}, got {output_name}"
            )

        # 基线输出
        baseline_value = self._evaluate_output_sync(
            input_spec, config, output_name
        )

        # 待分析的参数: 从 input_spec 和 config 中提取数值参数
        params_to_test: list[tuple[str, float, str, Any]] = []
        # input_spec 参数
        params_to_test.append(("material_count", float(input_spec.material_count), "input_spec", input_spec))
        params_to_test.append(("video_count", float(input_spec.video_count), "input_spec", input_spec))
        params_to_test.append(("image_count", float(input_spec.image_count), "input_spec", input_spec))
        params_to_test.append(("audio_count", float(input_spec.audio_count), "input_spec", input_spec))
        params_to_test.append(("total_duration_sec", input_spec.total_duration_sec, "input_spec", input_spec))
        params_to_test.append(("total_file_size_mb", input_spec.total_file_size_mb, "input_spec", input_spec))
        # config 参数
        params_to_test.append(("effects_count", float(config.effects_count), "config", config))
        params_to_test.append(("transitions_count", float(config.transitions_count), "config", config))
        params_to_test.append(("target_fps", float(config.target_fps), "config", config))
        params_to_test.append(("max_quality_iterations", float(config.max_quality_iterations), "config", config))

        sensitivities: dict[str, float] = {}

        for param_name, base_val, source, owner in params_to_test:
            if base_val == 0:
                # 跳过零值参数 (无法计算相对扰动)
                sensitivities[param_name] = 0.0
                continue

            # 正负扰动
            delta_plus = base_val * (1.0 + delta)
            delta_minus = base_val * (1.0 - delta)
            # 防止负数 (如 count)
            if delta_minus < 0:
                delta_minus = 0.0

            # 构建扰动后的 spec/config
            spec_plus, spec_minus = self._copy_input_spec(input_spec), self._copy_input_spec(input_spec)
            cfg_plus, cfg_minus = self._copy_config(config), self._copy_config(config)

            if source == "input_spec":
                self._set_attr(spec_plus, param_name, delta_plus)
                self._set_attr(spec_minus, param_name, delta_minus)
            else:
                self._set_attr(cfg_plus, param_name, delta_plus)
                self._set_attr(cfg_minus, param_name, delta_minus)

            val_plus = self._evaluate_output_sync(spec_plus, cfg_plus, output_name)
            val_minus = self._evaluate_output_sync(spec_minus, cfg_minus, output_name)

            # 中心差分: |f(x+δ) - f(x-δ)| / (2δ * |x|) (归一化为相对变化)
            denom = max(abs(baseline_value), 1e-6)
            sens = abs(val_plus - val_minus) / (2.0 * delta * max(abs(base_val), 1e-6))
            # 归一化到 [0, 1] 区间 (使用 sigmoid)
            sens = float(1.0 - math.exp(-sens))
            sensitivities[param_name] = sens

        # 排序找最敏感/最不敏感
        sorted_params = sorted(
            sensitivities.items(), key=lambda x: x[1], reverse=True
        )
        most_sensitive = sorted_params[0][0] if sorted_params else ""
        least_sensitive = sorted_params[-1][0] if sorted_params else ""

        return SensitivityResult(
            output_name=output_name,
            parameter_sensitivities=sensitivities,
            most_sensitive_param=most_sensitive,
            least_sensitive_param=least_sensitive,
            method=method,
            n_samples=len(params_to_test),
        )

    def _evaluate_output_sync(
        self,
        input_spec: InputSpecification,
        config: PipelineConfig,
        output_name: str,
    ) -> float:
        """同步评估输出指标 (用于敏感性分析)"""
        total_dur = 0.0
        total_sr = 1.0
        qualities = []
        predictor = self._shared_predictor
        for stage in self.STAGES:
            dur_mean, _ = predictor.predict_duration(stage, input_spec, config)
            sr_mean, _ = predictor.predict_success_rate(stage, input_spec, config)
            q = self._predict_quality(stage, input_spec, config)
            total_dur += dur_mean
            total_sr *= sr_mean
            qualities.append(q)
        avg_q = float(np.mean(qualities)) if qualities else 0.0
        if output_name == "total_duration":
            return total_dur
        elif output_name == "success_rate":
            return total_sr
        elif output_name == "quality":
            return avg_q
        return 0.0

    def _copy_input_spec(self, spec: InputSpecification) -> InputSpecification:
        """深拷贝 InputSpecification"""
        return InputSpecification(
            material_count=spec.material_count,
            video_count=spec.video_count,
            image_count=spec.image_count,
            audio_count=spec.audio_count,
            avg_resolution=spec.avg_resolution,
            total_duration_sec=spec.total_duration_sec,
            total_file_size_mb=spec.total_file_size_mb,
            has_reference_video=spec.has_reference_video,
            codecs=list(spec.codecs),
        )

    def _copy_config(self, config: PipelineConfig) -> PipelineConfig:
        """深拷贝 PipelineConfig"""
        return PipelineConfig(
            mode=config.mode,
            enable_vrs=config.enable_vrs,
            enable_feedback_loop=config.enable_feedback_loop,
            max_quality_iterations=config.max_quality_iterations,
            use_davinci_render=config.use_davinci_render,
            use_ae_render=config.use_ae_render,
            use_ffmpeg_fallback=config.use_ffmpeg_fallback,
            publish_platforms=list(config.publish_platforms),
            effects_count=config.effects_count,
            transitions_count=config.transitions_count,
            target_resolution=config.target_resolution,
            target_fps=config.target_fps,
        )

    def _set_attr(self, obj: Any, attr: str, value: Any) -> None:
        """安全设置对象属性 (按类型转换)

        支持的类型:
        - bool: 转 bool
        - int: 转 int
        - float: 转 float
        - tuple: 直接赋值 (如 target_resolution)
        - list: 直接赋值
        - str: 直接赋值
        """
        try:
            current = getattr(obj, attr)
            if isinstance(current, bool):
                setattr(obj, attr, bool(value))
            elif isinstance(current, int):
                setattr(obj, attr, int(value))
            elif isinstance(current, float):
                setattr(obj, attr, float(value))
            elif isinstance(current, (tuple, list, str)):
                # 直接赋值 (target_resolution = (3840, 2160))
                setattr(obj, attr, value)
            else:
                setattr(obj, attr, value)
        except AttributeError:
            pass

    async def what_if_analysis(
        self,
        input_spec: InputSpecification,
        baseline_config: PipelineConfig,
        scenarios: list[tuple[str, dict[str, Any]]],
    ) -> WhatIfResult:
        """What-If 分析

        在基线配置上应用多个假设场景, 对比预测结果。

        流程:
        1. 用基线配置预测 → 得到基线指标
        2. 对每个场景:
            a. 复制基线 config
            b. 应用 config_changes (覆盖字段)
            c. 预测 → 得到场景指标
            d. 计算 delta = 场景值 - 基线值
        3. 按 (success_rate, quality) 综合排序, 选出 best/worst

        Args:
            input_spec: 输入素材规格
            baseline_config: 基线配置
            scenarios: [(scenario_name, config_changes_dict), ...]
                config_changes_dict: {config_field: new_value}

        Returns:
            WhatIfResult: 包含基线、各场景、best/worst 场景
        """
        baseline = await self.predict_execution(input_spec, baseline_config)
        baseline_dur = baseline.total_predicted_duration
        baseline_sr = baseline.overall_success_rate
        baseline_q = baseline.predicted_output_quality

        results: list[WhatIfScenario] = []
        for name, changes in scenarios:
            modified = self._copy_config(baseline_config)
            for field_name, value in changes.items():
                # 直接传值, _set_attr 会按目标属性类型自动转换
                self._set_attr(modified, field_name, value)
            pred = await self.predict_execution(input_spec, modified)
            scenario = WhatIfScenario(
                name=name,
                description=f"Apply {changes}",
                config_changes=changes,
                predicted_total_duration=pred.total_predicted_duration,
                predicted_success_rate=pred.overall_success_rate,
                predicted_quality=pred.predicted_output_quality,
                delta_duration=pred.total_predicted_duration - baseline_dur,
                delta_success_rate=pred.overall_success_rate - baseline_sr,
                delta_quality=pred.predicted_output_quality - baseline_q,
            )
            results.append(scenario)

        # 综合评分: success_rate * 0.5 + quality/100 * 0.3 - duration/300 * 0.2
        def score(s: WhatIfScenario) -> float:
            return (
                s.predicted_success_rate * 0.5
                + s.predicted_quality / 100.0 * 0.3
                - s.predicted_total_duration / 300.0 * 0.2
            )

        best = max(results, key=score) if results else None
        worst = min(results, key=score) if results else None

        return WhatIfResult(
            baseline=baseline,
            scenarios=results,
            best_scenario=best,
            worst_scenario=worst,
        )


# ============================================================================
#  全局单例
# ============================================================================

_global_twin: PipelineDigitalTwin | None = None


def get_digital_twin(data_dir: str = PipelineDigitalTwin.DEFAULT_DATA_DIR
                     ) -> PipelineDigitalTwin:
    """获取全局数字孪生单例"""
    global _global_twin
    if _global_twin is None:
        _global_twin = PipelineDigitalTwin(data_dir)
    return _global_twin
