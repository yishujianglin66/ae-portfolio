"""
core/bayesian_optimizer.py — 多目标贝叶斯参数优化器 v1.0
==========================================================

基于高斯过程代理模型和多目标采集函数(EHVI)的效果参数自动优化。

设计原则:
1. 少样本快速收敛: 3-5次渲染后锁定最优参数区间
2. 多目标帕累托: 同时优化质量/渲染时间/文件大小
3. 跨效果迁移: 从 Glow 的最优参数推断 TurbulentDisperse 的参数范围
4. 离线可用: 纯 numpy 实现高斯过程，无需外部ML库

集成方式:
    from core.bayesian_optimizer import get_optimizer

    optimizer = get_optimizer()
    suggestions = optimizer.recommend("Glow", style_context, constraints)
    optimizer.observe("Glow", params, quality=85, render_time=3.2, file_size=150)
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
#  EI 辅助: 标准正态 CDF / PDF (优先使用 scipy, 不可用时回退到 erf 近似)
# ============================================================================

def _norm_pdf(x: np.ndarray | float) -> np.ndarray | float:
    """标准正态分布概率密度函数 φ(x) = (1/√(2π)) * exp(-x²/2)"""
    return np.exp(-0.5 * np.asarray(x, dtype=float) ** 2) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: np.ndarray | float) -> np.ndarray | float:
    """标准正态分布累积分布函数 Φ(x)

    优先使用 scipy.special.ndtr (基于 erf), 不可用时回退到 math.erf。
    Φ(x) = 0.5 * (1 + erf(x / √2))
    """
    try:
        from scipy.special import ndtr  # type: ignore
        return ndtr(x)
    except ImportError:
        arr = np.asarray(x, dtype=float)
        scalar_input = arr.ndim == 0
        flat = arr.ravel()
        cdf = np.array([0.5 * (1.0 + math.erf(float(v) / math.sqrt(2.0))) for v in flat])
        cdf = cdf.reshape(arr.shape)
        return float(cdf) if scalar_input else cdf


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class ParameterSpec:
    """单个参数的规格"""
    name: str
    param_type: str          # "float" | "int" | "enum" | "bool"
    min_val: float = 0.0
    max_val: float = 1.0
    default_val: float = 0.5
    enum_values: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ParameterConstraints:
    """参数约束集"""
    hard_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    soft_preferences: Dict[str, float] = field(default_factory=dict)  # param -> preferred value
    linked_params: List[Tuple[str, str, str]] = field(default_factory=list)  # (p1, p2, relation)


@dataclass
class StyleVector:
    """风格上下文向量"""
    style_name: str = ""
    mood: str = ""               # e.g. "energetic", "cinematic", "minimal"
    color_palette: List[str] = field(default_factory=list)
    intensity: float = 0.5       # 0=subtle, 1=intense
    target_platform: str = ""    # e.g. "bilibili", "douyin"
    reference_params: Dict[str, float] = field(default_factory=dict)


@dataclass
class ParameterSuggestion:
    """参数推荐"""
    params: Dict[str, float]
    expected_quality: float = 0.0
    expected_render_time: float = 0.0
    expected_file_size: float = 0.0
    confidence: float = 0.0
    acquisition_score: float = 0.0
    is_transfer: bool = False    # 是否来自迁移学习


@dataclass
class Observation:
    """参数观测结果"""
    params: Dict[str, float]
    quality: float               # 0-100
    render_time: float           # 秒
    file_size: float             # MB
    timestamp: float = 0.0
    success: bool = True


@dataclass
class TransferResult:
    """跨效果迁移结果"""
    source_effect: str
    target_effect: str
    transferred_params: Dict[str, float]
    transfer_confidence: float = 0.0
    correlation_matrix: Optional[np.ndarray] = None


@dataclass
class ParetoPoint:
    """帕累托前沿上的点"""
    params: Dict[str, float]
    objectives: Tuple[float, float, float]  # (quality, -render_time, -file_size)
    observation: Observation


# ============================================================================
#  P3.4: 多目标贝叶斯优化扩展
# ============================================================================

@dataclass
class ParamSpec:
    """通用参数规格（用于 multi_objective_optimize）
    
    与现有 ParameterSpec 互补:
    - ParameterSpec: 面向 AE 效果参数（含 enum_values / description）
    - ParamSpec: 通用参数规格，适用于任意优化问题
    
    Attributes:
        name: 参数名
        low: 下界
        high: 上界
        dtype: 数据类型 ("float" / "int")
        default: 默认值
    """
    name: str
    low: float = 0.0
    high: float = 1.0
    dtype: str = "float"  # "float" | "int"
    default: float = 0.5


@dataclass
class ObjectiveSpec:
    """目标规格（用于 multi_objective_optimize）
    
    Attributes:
        name: 目标名 (如 "quality" / "speed" / "cost")
        direction: 优化方向 ("maximize" 或 "minimize")
        weight: 该目标的先验权重（用于 best_per_objective 排序，不影响帕累托前沿）
    """
    name: str
    direction: str = "maximize"  # "maximize" | "minimize"
    weight: float = 1.0


@dataclass
class ParetoSolution:
    """帕累托前沿上的单个解
    
    Attributes:
        params: 参数取值
        objectives: 各目标的取值 {obj_name: value}
        is_pareto: 是否在帕累托前沿上
    """
    params: Dict[str, float] = field(default_factory=dict)
    objectives: Dict[str, float] = field(default_factory=dict)
    is_pareto: bool = True


@dataclass
class ParetoFront:
    """多目标优化的帕累托前沿结果
    
    Attributes:
        solutions: 所有评估的解（含帕累托最优与非最优）
        pareto_solutions: 仅帕累托最优解
        hypervolume: 超体积指标（越大越好）
        best_per_objective: 每个目标单独最优的解 {obj_name: ParetoSolution}
        n_evaluations: 总评估次数
    """
    solutions: List[ParetoSolution] = field(default_factory=list)
    pareto_solutions: List[ParetoSolution] = field(default_factory=list)
    hypervolume: float = 0.0
    best_per_objective: Dict[str, ParetoSolution] = field(default_factory=dict)
    n_evaluations: int = 0


# ============================================================================
#  M2.5: AE 效果参数空间定义
# ============================================================================

# AE 常用效果参数空间
PARAMETER_SPACES: Dict[str, List[ParameterSpec]] = {
    "Glow": [
        ParameterSpec("glow_threshold", "float", 0.0, 100.0, 50.0,
                      description="Glow threshold (brightness cutoff)"),
        ParameterSpec("glow_radius", "float", 0.0, 200.0, 30.0,
                      description="Glow radius in pixels"),
        ParameterSpec("glow_intensity", "float", 0.0, 5.0, 1.0,
                      description="Glow intensity multiplier"),
        ParameterSpec("glow_colors", "enum", 0.0, 2.0, 0.0,
                      enum_values=["From Behind", "Original Colors", "Custom"],
                      description="Glow color source"),
    ],
    "TurbulentDisperse": [
        ParameterSpec("turb_size", "float", 0.1, 500.0, 50.0,
                      description="Turbulence size"),
        ParameterSpec("turb_complexity", "float", 1.0, 10.0, 3.0,
                      description="Turbulence complexity (octaves)"),
        ParameterSpec("turb_evolution", "float", 0.0, 100.0, 10.0,
                      description="Turbulence evolution speed"),
        ParameterSpec("disperse_amount", "float", 0.0, 2.0, 0.5,
                      description="Disperse amount"),
    ],
    "CC_StarGlow": [
        ParameterSpec("starglow_threshold", "float", 0.0, 1.0, 0.5,
                      description="Star glow threshold"),
        ParameterSpec("starglow_glow", "float", 0.0, 10.0, 2.0,
                      description="Star glow amount"),
        ParameterSpec("starglow_star_size", "float", 0.0, 200.0, 50.0,
                      description="Star size"),
        ParameterSpec("starglow_bias", "float", -1.0, 1.0, 0.0,
                      description="Star bias"),
    ],
    "FastBlur": [
        ParameterSpec("blur_radius", "float", 0.0, 100.0, 10.0,
                      description="Blur radius"),
        ParameterSpec("blur_direction", "enum", 0.0, 2.0, 0.0,
                      enum_values=["Blur Horizontally", "Blur Vertically", "Blur Both"],
                      description="Blur direction"),
    ],
    "ColorBalance": [
        ParameterSpec("shadow_r", "float", -100.0, 100.0, 0.0),
        ParameterSpec("shadow_g", "float", -100.0, 100.0, 0.0),
        ParameterSpec("shadow_b", "float", -100.0, 100.0, 0.0),
        ParameterSpec("midtone_r", "float", -100.0, 100.0, 0.0),
        ParameterSpec("midtone_g", "float", -100.0, 100.0, 0.0),
        ParameterSpec("midtone_b", "float", -100.0, 100.0, 0.0),
        ParameterSpec("highlight_r", "float", -100.0, 100.0, 0.0),
        ParameterSpec("highlight_g", "float", -100.0, 100.0, 0.0),
        ParameterSpec("highlight_b", "float", -100.0, 100.0, 0.0),
    ],
    "Curves": [
        ParameterSpec("curve_brightness", "float", -100.0, 100.0, 0.0),
        ParameterSpec("curve_contrast", "float", -100.0, 100.0, 0.0),
        ParameterSpec("curve_midtone", "float", 0.1, 9.9, 5.0),
    ],
    "MotionBlur": [
        ParameterSpec("motion_samples", "int", 4.0, 64.0, 16.0,
                      description="Motion blur samples"),
        ParameterSpec("motion_shutter_angle", "float", 0.0, 720.0, 180.0,
                      description="Shutter angle in degrees"),
    ],
    # 补充：与 feedback_executor 的 type_to_effect 映射对齐
    "Sharpen": [
        ParameterSpec("sharpen_amount", "float", 0.0, 100.0, 50.0,
                      description="Sharpen amount"),
        ParameterSpec("sharpen_radius", "float", 0.0, 100.0, 1.0,
                      description="Sharpen radius"),
        ParameterSpec("sharpen_threshold", "float", 0.0, 255.0, 0.0,
                      description="Sharpen threshold"),
    ],
    "Vignette": [
        ParameterSpec("vignette_amount", "float", -100.0, 100.0, -30.0,
                      description="Vignette amount (negative=darken edges)"),
        ParameterSpec("vignette_size", "float", 0.0, 100.0, 50.0,
                      description="Vignette size"),
        ParameterSpec("vignette_feather", "float", 0.0, 100.0, 25.0,
                      description="Vignette feather edge softness"),
        ParameterSpec("vignette_roundness", "float", -100.0, 100.0, 0.0,
                      description="Vignette roundness"),
    ],
    # 补充：常见 AMV 调色效果
    "UnsharpMask": [
        ParameterSpec("unsharp_amount", "float", 0.0, 100.0, 50.0,
                      description="Unsharp Mask amount"),
        ParameterSpec("unsharp_radius", "float", 0.0, 100.0, 1.0,
                      description="Unsharp Mask radius"),
        ParameterSpec("unsharp_threshold", "float", 0.0, 255.0, 0.0,
                      description="Unsharp Mask threshold"),
    ],
    "CurvesAdvanced": [
        ParameterSpec("curve_brightness", "float", -100.0, 100.0, 0.0),
        ParameterSpec("curve_contrast", "float", -100.0, 100.0, 0.0),
        ParameterSpec("curve_midtone", "float", 0.1, 9.9, 5.0),
        ParameterSpec("curve_saturation", "float", -100.0, 100.0, 0.0),
    ],
}

# 效果间相似度矩阵（用于迁移学习）
# 值越大表示两个效果的参数空间越相似
# 补充规则：
# - 发光类（Glow/CC_StarGlow）：阈值(threshold)+半径(radius)+强度(intensity)+颜色(color)
# - 锐化类（Sharpen/UnsharpMask）：量(amount)+半径(radius)+阈值(threshold)，三参数高度重合
# - 模糊类（FastBlur/TurbulentDisperse/MotionBlur）：半径/方向/采样
# - 调色类（ColorBalance/Curves/CurvesAdvanced）：亮度+对比度+饱和度
# - 暗角（Vignette）：量+半径+羽化，与模糊类有弱相关（都作用于周边）
EFFECT_SIMILARITY: Dict[str, Dict[str, float]] = {
    # ---------- 发光类 ----------
    "Glow": {
        "CC_StarGlow": 0.85,  # 结构几乎一致：threshold+radius+intensity+colors
        "Sharpen": 0.2,       # 都有 threshold 语义
        "FastBlur": 0.45,     # 都有 radius/amount 语义（反方向：扩散 vs 模糊）
        "TurbulentDisperse": 0.25,
        "ColorBalance": 0.15, # 都有 color 相关
        "Curves": 0.2,        # 调色互通：曲线可控制辉光溢出
        "CurvesAdvanced": 0.2,
        "UnsharpMask": 0.35,  # sharpen 是反 blur，glow 是 add blur，参数空间相似
        "Vignette": 0.1,
        "MotionBlur": 0.2,
    },
    "CC_StarGlow": {
        "Glow": 0.85,
        "Sharpen": 0.15,
        "FastBlur": 0.35,
        "TurbulentDisperse": 0.35,
        "ColorBalance": 0.1,
        "Curves": 0.15,
        "CurvesAdvanced": 0.15,
        "UnsharpMask": 0.25,
        "Vignette": 0.1,
        "MotionBlur": 0.15,
    },
    # ---------- 锐化类 ----------
    "Sharpen": {
        "UnsharpMask": 0.95,  # 几乎等价：amount+radius+threshold 三个参数完全同构
        "Glow": 0.2,
        "CC_StarGlow": 0.15,
        "FastBlur": 0.4,      # sharpen 是反 blur，参数空间对称
        "TurbulentDisperse": 0.2,
        "Curves": 0.15,       # 锐化配合 S 曲线增强细节
        "CurvesAdvanced": 0.15,
        "ColorBalance": 0.1,
        "Vignette": 0.1,
        "MotionBlur": 0.2,
    },
    "UnsharpMask": {
        "Sharpen": 0.95,
        "Glow": 0.35,
        "CC_StarGlow": 0.25,
        "FastBlur": 0.5,      # unsharp = original - blur，参数空间高度对称
        "TurbulentDisperse": 0.25,
        "Curves": 0.2,
        "CurvesAdvanced": 0.2,
        "ColorBalance": 0.1,
        "Vignette": 0.1,
        "MotionBlur": 0.25,
    },
    # ---------- 模糊类 ----------
    "FastBlur": {
        "Glow": 0.45,
        "CC_StarGlow": 0.35,
        "TurbulentDisperse": 0.6,
        "Sharpen": 0.4,
        "UnsharpMask": 0.5,
        "MotionBlur": 0.5,    # 方向模糊同构
        "Curves": 0.1,        # 模糊柔化边缘，可配合曲线降低光晕
        "ColorBalance": 0.1,
        "CurvesAdvanced": 0.1,
        "Vignette": 0.25,     # 都有羽化/半径概念
    },
    "TurbulentDisperse": {
        "Glow": 0.25,
        "CC_StarGlow": 0.35,
        "FastBlur": 0.6,
        "Sharpen": 0.2,
        "UnsharpMask": 0.25,
        "MotionBlur": 0.4,
        "Curves": 0.15,
        "ColorBalance": 0.1,
        "CurvesAdvanced": 0.15,
        "Vignette": 0.2,
    },
    "MotionBlur": {
        "FastBlur": 0.5,
        "TurbulentDisperse": 0.4,
        "UnsharpMask": 0.25,
        "Sharpen": 0.2,
        "Glow": 0.2,
        "CC_StarGlow": 0.15,
        "Curves": 0.15,       # 运动尾迹配合曲线加深明暗对比
        "ColorBalance": 0.1,
        "CurvesAdvanced": 0.15,
        "Vignette": 0.15,
    },
    # ---------- 调色类 ----------
    "ColorBalance": {
        "Curves": 0.7,
        "CurvesAdvanced": 0.75,  # CurvesAdvanced 是增强版：亮度+对比+饱和 vs 三色阶
        "Glow": 0.15,
        "CC_StarGlow": 0.1,
        "Sharpen": 0.1,
        "UnsharpMask": 0.1,
        "FastBlur": 0.1,
        "TurbulentDisperse": 0.1,
        "Vignette": 0.2,        # 都作用于曝光/阴影
        "MotionBlur": 0.1,
    },
    "Curves": {
        "ColorBalance": 0.7,
        "CurvesAdvanced": 0.8,   # 超集关系：CurvesAdvanced = Curves(brightness/contrast/midtone) + Saturation
        "Glow": 0.2,
        "CC_StarGlow": 0.15,
        "Sharpen": 0.15,
        "UnsharpMask": 0.2,
        "FastBlur": 0.1,
        "TurbulentDisperse": 0.15,
        "Vignette": 0.25,        # 曲线可以模拟暗角
        "MotionBlur": 0.15,
    },
    "CurvesAdvanced": {
        "Curves": 0.8,
        "ColorBalance": 0.75,
        "Glow": 0.2,
        "CC_StarGlow": 0.15,
        "Sharpen": 0.15,
        "UnsharpMask": 0.2,
        "FastBlur": 0.1,
        "TurbulentDisperse": 0.15,
        "Vignette": 0.3,         # 暗角是曝光控制的子集
        "MotionBlur": 0.15,
    },
    # ---------- 暗角 ----------
    "Vignette": {
        "CurvesAdvanced": 0.3,
        "Curves": 0.25,
        "ColorBalance": 0.2,
        "FastBlur": 0.25,
        "TurbulentDisperse": 0.2,
        "Glow": 0.1,
        "CC_StarGlow": 0.1,
        "Sharpen": 0.1,
        "UnsharpMask": 0.1,
        "MotionBlur": 0.15,
    },
}


# ============================================================================
#  M2.1: 高斯过程代理模型（纯 numpy 实现）
# ============================================================================

class GaussianProcessRegressor:
    """高斯过程回归器（纯 numpy 实现）
    
    核函数: Matern 5/2（适合高维参数空间，比 RBF 更鲁棒）
    优化: 对数边际似然最大化（L-BFGS 简化版）
    """
    
    def __init__(
        self,
        length_scale: float = 1.0,
        noise: float = 0.1,
        signal_variance: float = 1.0
    ):
        self._length_scale = length_scale
        self._noise = noise
        self._signal_variance = signal_variance
        
        # 训练数据
        self._X: Optional[np.ndarray] = None
        self._y: Optional[np.ndarray] = None
        self._K_inv: Optional[np.ndarray] = None
        self._alpha: Optional[np.ndarray] = None
        self._fitted = False
    
    def _matern52_kernel(self, X1: np.ndarray, X2: np.ndarray) -> np.ndarray:
        """Matern 5/2 核函数
        
        k(x, x') = sigma^2 * (1 + sqrt(5)*r/l + 5*r^2/(3*l^2)) * exp(-sqrt(5)*r/l)
        其中 r = ||x - x'||
        """
        ls = max(self._length_scale, 1e-6)
        # 计算距离矩阵
        sq_dist = np.sum(X1**2, axis=1, keepdims=True) - 2 * X1 @ X2.T + np.sum(X2**2, axis=1)
        sq_dist = np.maximum(sq_dist, 0.0)
        r = np.sqrt(sq_dist)
        
        sqrt5_r_l = math.sqrt(5) * r / ls
        K = self._signal_variance * (1 + sqrt5_r_l + 5 * r**2 / (3 * ls**2)) * np.exp(-sqrt5_r_l)
        return K
    
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """拟合高斯过程
        
        Args:
            X: (n_samples, n_features) 输入
            y: (n_samples,) 输出
        """
        self._X = X.copy()
        self._y = y.copy()
        
        n = X.shape[0]
        if n == 0:
            self._fitted = False
            return
        
        # 优化超参数（简化网格搜索）
        best_lml = -np.inf
        best_ls = self._length_scale
        
        for ls in [0.1, 0.5, 1.0, 2.0, 5.0]:
            self._length_scale = ls
            K = self._matern52_kernel(X, X) + self._noise**2 * np.eye(n)
            
            try:
                L = np.linalg.cholesky(K)
                alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
                # 对数边际似然
                lml = -0.5 * y @ alpha - np.sum(np.log(np.diag(L))) - 0.5 * n * math.log(2 * math.pi)
                if lml > best_lml:
                    best_lml = lml
                    best_ls = ls
            except np.linalg.LinAlgError:
                continue
        
        self._length_scale = best_ls
        
        # 用最优超参数重新计算
        K = self._matern52_kernel(X, X) + self._noise**2 * np.eye(n)
        try:
            L = np.linalg.cholesky(K)
            self._K_inv = np.linalg.solve(L.T, np.linalg.solve(L, np.eye(n)))
            self._alpha = np.linalg.solve(L.T, np.linalg.solve(L, y))
            self._fitted = True
        except np.linalg.LinAlgError:
            # 退化情况: 添加更多正则化
            K += 0.1 * np.eye(n)
            try:
                self._K_inv = np.linalg.inv(K)
                self._alpha = self._K_inv @ y
                self._fitted = True
            except np.linalg.LinAlgError:
                self._fitted = False
    
    def predict(self, X_new: np.ndarray, return_std: bool = True
                ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """预测
        
        Args:
            X_new: (n_new, n_features)
            return_std: 是否返回标准差
            
        Returns:
            mean: (n_new,) 预测均值
            std: (n_new,) 预测标准差（如果 return_std=True）
        """
        if not self._fitted or self._X is None:
            n = X_new.shape[0]
            mean = np.zeros(n)
            std = np.ones(n) * self._signal_variance
            return mean, std if return_std else None
        
        K_star = self._matern52_kernel(X_new, self._X)
        mean = K_star @ self._alpha
        
        if return_std:
            K_ss = self._matern52_kernel(X_new, X_new)
            var = np.diag(K_ss) - np.sum(K_star @ self._K_inv * K_star, axis=1)
            var = np.maximum(var, 1e-10)
            std = np.sqrt(var)
            return mean, std
        
        return mean, None
    
    def log_marginal_likelihood(self) -> float:
        """计算对数边际似然"""
        if not self._fitted or self._X is None or self._y is None:
            return -np.inf
        n = len(self._y)
        lml = -0.5 * self._y @ self._alpha
        if self._K_inv is not None:
            K = self._matern52_kernel(self._X, self._X) + self._noise**2 * np.eye(n)
            try:
                L = np.linalg.cholesky(K)
                lml -= np.sum(np.log(np.diag(L)))
            except np.linalg.LinAlgError:
                pass
        lml -= 0.5 * n * math.log(2 * math.pi)
        return float(lml)


# ============================================================================
#  M2.2: 多目标采集函数 (EHVI)
# ============================================================================

class EHVIAcquisition:
    """Expected Hypervolume Improvement 采集函数
    
    多目标贝叶斯优化的核心:
    - 目标1: 最大化质量 (quality)
    - 目标2: 最小化渲染时间 (render_time)
    - 目标3: 最小化文件大小 (file_size)
    
    EHVI = E[max(0, HV(P_new) - HV(P_current))]
    其中 HV 是超体积指标
    """
    
    def __init__(self, reference_point: Tuple[float, float, float] = (0.0, -100.0, -1000.0)):
        """
        Args:
            reference_point: 参考点（帕累托前沿的下界）
                quality 下界=0, render_time 上界=100s, file_size 上界=1000MB
        """
        self._ref = np.array(reference_point)
    
    def compute_ehvi(
        self,
        X_candidates: np.ndarray,
        models: Tuple[GaussianProcessRegressor, GaussianProcessRegressor, GaussianProcessRegressor],
        pareto_front: np.ndarray,
        n_samples: int = 100
    ) -> np.ndarray:
        """计算候选点的 EHVI
        
        Args:
            X_candidates: (n_candidates, n_features) 候选参数点
            models: 三个目标的 GP 模型 (quality, render_time, file_size)
            pareto_front: (n_pareto, 3) 当前帕累托前沿
            n_samples: MC 采样数
            
        Returns:
            ehvi: (n_candidates,) 每个候选点的 EHVI
        """
        n_candidates = X_candidates.shape[0]
        ehvi = np.zeros(n_candidates)
        
        # 获取每个模型的预测分布
        means = []
        stds = []
        for model in models:
            mu, sigma = model.predict(X_candidates, return_std=True)
            means.append(mu)
            stds.append(sigma if sigma is not None else np.ones(n_candidates))
        
        # 当前帕累托前沿的超体积
        current_hv = self._compute_hypervolume(pareto_front) if len(pareto_front) > 0 else 0.0
        
        for i in range(n_candidates):
            # MC 采样估计 EHVI
            improvements = []
            for _ in range(n_samples):
                # 从预测分布采样
                q = np.random.normal(means[0][i], max(stds[0][i], 1e-6))
                rt = np.random.normal(means[1][i], max(stds[1][i], 1e-6))
                fs = np.random.normal(means[2][i], max(stds[2][i], 1e-6))
                
                # 转换为最大化目标
                sample_point = np.array([q, -rt, -fs])
                
                # 计算新帕累托前沿的超体积
                new_front = np.vstack([pareto_front, sample_point.reshape(1, -1)]) if len(pareto_front) > 0 else sample_point.reshape(1, -1)
                new_front = self._extract_pareto_front(new_front)
                new_hv = self._compute_hypervolume(new_front)
                
                improvements.append(max(0, new_hv - current_hv))
            
            ehvi[i] = np.mean(improvements)
        
        return ehvi
    
    def _extract_pareto_front(self, points: np.ndarray) -> np.ndarray:
        """提取帕累托前沿（最大化所有目标）- 向量化版本"""
        if len(points) <= 1:
            return points
        
        n = len(points)
        # 向量化支配检查: points[i] 支配 points[j] 当且仅当
        # all(points[i] >= points[j]) and any(points[i] > points[j])
        # 使用广播: (n, 1, d) vs (1, n, d) -> (n, n, d)
        geq = np.all(points[:, None, :] >= points[None, :, :], axis=2)  # (n, n)
        gt = np.any(points[:, None, :] > points[None, :, :], axis=2)   # (n, n)
        dominates = geq & gt  # dominates[i, j] = True if i dominates j
        
        # 如果存在任何点支配 i，则 i 不是帕累托点
        is_dominated = np.any(dominates, axis=0)  # (n,)
        is_pareto = ~is_dominated
        
        return points[is_pareto]
    
    def _compute_hypervolume(self, pareto_front: np.ndarray) -> float:
        """计算超体积指标（3目标）
        
        对于3维情况，使用精确算法
        """
        if len(pareto_front) == 0:
            return 0.0
        
        if len(pareto_front) == 1:
            # 单点: 与参考点的包围盒体积
            diff = pareto_front[0] - self._ref
            if np.all(diff > 0):
                return float(np.prod(diff))
            return 0.0
        
        # 2D 简化: 按第一维排序后扫描线算法
        if pareto_front.shape[1] == 2:
            sorted_idx = np.argsort(-pareto_front[:, 0])
            hv = 0.0
            prev_y = self._ref[1]
            for idx in sorted_idx:
                p = pareto_front[idx]
                if p[1] > prev_y:
                    hv += (p[0] - self._ref[0]) * (p[1] - prev_y)
                    prev_y = p[1]
            return hv
        
        # 3D: MC 近似 - 向量化版本 (性能优化: 纯Python循环 → numpy广播)
        n_mc = 200  # 降低采样数，平衡精度与速度
        # 确定采样范围
        lower = self._ref
        upper = np.max(pareto_front, axis=0)
        
        # 确保 upper > lower，避免零体积
        if np.any(upper <= lower):
            return 0.0
        
        samples = np.random.uniform(lower, upper, size=(n_mc, 3))
        
        # 向量化支配检查: 检查每个采样点是否被帕累托前沿支配
        # pareto_front: (n_pareto, 3), samples: (n_mc, 3)
        # 广播: (n_pareto, 1, 3) >= (1, n_mc, 3) -> (n_pareto, n_mc, 3)
        dominated = np.any(
            np.all(pareto_front[:, None, :] >= samples[None, :, :], axis=2),
            axis=0
        )  # (n_mc,) - 每个采样点是否被支配
        dominated_count = int(np.sum(dominated))
        
        total_volume = float(np.prod(upper - lower))
        hv = total_volume * dominated_count / n_mc
        return hv


# ============================================================================
#  主优化器: BayesianParameterOptimizer
# ============================================================================

def _default_bo_data_dir() -> Path:
    """返回贝叶斯优化器默认存储目录（与 PersistentLearningLoop 同根）。

    优先使用系统 APPDATA 下的 AE-Knowledge-Vault/bayesian-optimizer
    （绝对路径，不受 CWD 影响，跨进程共享）。
    另外，如果旧路径 <project-root>/data/bayesian_optimizer/ 下已有
    observations.json，则自动迁移到新目录，避免数据丢失。
    """
    import os as _os
    if _os.name == "nt":
        base = _os.environ.get("APPDATA", _os.path.expanduser("~"))
    else:
        base = _os.environ.get("HOME", _os.path.expanduser("~"))
    new_dir = Path(base) / "AE-Knowledge-Vault" / "bayesian-optimizer"
    new_dir.mkdir(parents=True, exist_ok=True)

    # ---- 一次性迁移：从旧的相对路径 data/bayesian_optimizer/ 拷贝过来 ----
    legacy = Path("data/bayesian_optimizer")
    try:
        if legacy.is_absolute():
            # 调用方已经传入绝对路径，跳过自动迁移
            return new_dir
        if legacy.exists() and (legacy / "observations.json").exists():
            target_obs = new_dir / "observations.json"
            if not target_obs.exists():
                import shutil as _shutil
                _shutil.copy2(legacy / "observations.json", target_obs)
                pareto_src = legacy / "pareto_fronts.json"
                if pareto_src.exists():
                    _shutil.copy2(pareto_src, new_dir / "pareto_fronts.json")
                try:
                    _log = __import__("logging").getLogger("bayesian")
                    _log.info(
                        f"[BayesianOptimizer] Migrated legacy data from {legacy.resolve()} -> {new_dir}"
                    )
                except Exception:
                    pass
    except Exception:
        # 迁移失败不影响运行（最坏情况：重新积累观测）
        pass

    # ---- 迁移：从项目根下的 data/bayesian_optimizer/（相对 CWD 可能不同）
    # 也尝试从 core/ 上两级定位项目根 ----
    try:
        project_root = Path(__file__).resolve().parent.parent  # core/.. = 项目根
        legacy2 = project_root / "data" / "bayesian_optimizer"
        if legacy2.exists() and (legacy2 / "observations.json").exists():
            target_obs = new_dir / "observations.json"
            if not target_obs.exists():
                import shutil as _shutil2
                _shutil2.copy2(legacy2 / "observations.json", target_obs)
                pareto_src2 = legacy2 / "pareto_fronts.json"
                if pareto_src2.exists():
                    _shutil2.copy2(pareto_src2, new_dir / "pareto_fronts.json")
    except Exception:
        pass

    return new_dir


class BayesianParameterOptimizer:
    """多目标贝叶斯参数优化器

    整合 GP 代理模型 + EHVI 采集函数 + 跨效果迁移
    """

    DEFAULT_DATA_DIR: str = str(_default_bo_data_dir())

    def __init__(self, data_dir: str | None = None):
        # 空字符串 / None → 走默认绝对路径（禁止默认相对路径，避免 CWD 影响）
        if data_dir is None or str(data_dir).strip() == "":
            data_dir = self.DEFAULT_DATA_DIR
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 每个效果一个组的 GP 模型
        self._models: Dict[str, Tuple[GaussianProcessRegressor,
                                       GaussianProcessRegressor,
                                       GaussianProcessRegressor]] = {}
        
        # 观测历史: effect_name -> List[Observation]
        self._observations: Dict[str, List[Observation]] = {}
        
        # 帕累托前沿: effect_name -> List[ParetoPoint]
        self._pareto_fronts: Dict[str, List[ParetoPoint]] = {}
        
        # 跨效果迁移矩阵
        self._transfer_cache: Dict[str, np.ndarray] = {}
        
        # EHVI 采集函数
        self._acquisition = EHVIAcquisition()
        
        # 加载持久化数据
        self._load_state()
    
    # ----------------------------------------------------------------
    #  参数推荐
    # ----------------------------------------------------------------
    
    def recommend(
        self,
        effect_name: str,
        style_context: Optional[StyleVector] = None,
        constraints: Optional[ParameterConstraints] = None,
        n_suggestions: int = 3
    ) -> List[ParameterSuggestion]:
        """贝叶斯优化推荐
        
        Args:
            effect_name: 效果名称
            style_context: 风格上下文
            constraints: 参数约束
            n_suggestions: 推荐数量
            
        Returns:
            参数推荐列表
        """
        specs = PARAMETER_SPACES.get(effect_name, [])
        if not specs:
            logger.warning(f"[BayesianOptimizer] Unknown effect: {effect_name}")
            return self._default_suggestions(effect_name, n_suggestions)
        
        obs_list = self._observations.get(effect_name, [])
        
        # 冷启动: 无观测数据时使用默认值 + 拉丁超立方采样
        if len(obs_list) < 2:
            return self._cold_start_recommend(effect_name, specs, style_context,
                                               constraints, n_suggestions)
        
        # 构建 GP 模型
        models = self._get_or_build_models(effect_name, obs_list, specs)
        
        # 构建帕累托前沿
        pareto_points = self._build_pareto_front(effect_name, obs_list)
        pareto_array = np.array([p.objectives for p in pareto_points]) if pareto_points else np.empty((0, 3))
        
        # 生成候选点
        n_candidates = max(100, n_suggestions * 50)
        candidates = self._generate_candidates(specs, n_candidates, constraints, style_context)
        
        # 计算 EHVI
        ehvi_scores = self._acquisition.compute_ehvi(
            candidates, models, pareto_array, n_samples=50
        )
        
        # 选择 top-K
        top_indices = np.argsort(-ehvi_scores)[:n_suggestions]
        
        suggestions = []
        for idx in top_indices:
            params = self._vector_to_params(candidates[idx], specs)
            # 预测目标值
            x = candidates[idx:idx+1]
            q_mu, _ = models[0].predict(x, return_std=False)
            rt_mu, _ = models[1].predict(x, return_std=False)
            fs_mu, _ = models[2].predict(x, return_std=False)
            
            suggestions.append(ParameterSuggestion(
                params=params,
                expected_quality=float(q_mu[0]),
                expected_render_time=float(rt_mu[0]),
                expected_file_size=float(fs_mu[0]),
                confidence=min(1.0, len(obs_list) / 10.0),
                acquisition_score=float(ehvi_scores[idx]),
                is_transfer=False
            ))
        
        return suggestions
    
    def _cold_start_recommend(
        self,
        effect_name: str,
        specs: List[ParameterSpec],
        style_context: Optional[StyleVector],
        constraints: Optional[ParameterConstraints],
        n: int
    ) -> List[ParameterSuggestion]:
        """冷启动推荐（无观测数据）"""
        suggestions = []
        
        # 尝试迁移学习
        transfer_result = self._try_transfer(effect_name, specs)
        if transfer_result and transfer_result.transfer_confidence > 0.3:
            suggestions.append(ParameterSuggestion(
                params=transfer_result.transferred_params,
                confidence=transfer_result.transfer_confidence,
                is_transfer=True
            ))
        
        # 拉丁超立方采样
        lhc_samples = self._latin_hypercube(specs, max(n - len(suggestions), 1))
        
        for sample in lhc_samples[:n - len(suggestions)]:
            params = self._vector_to_params(sample, specs)
            
            # 应用风格调整
            if style_context:
                params = self._apply_style_adjustment(params, specs, style_context)
            
            # 应用约束
            if constraints:
                params = self._apply_constraints(params, constraints)
            
            suggestions.append(ParameterSuggestion(
                params=params,
                confidence=0.1,  # 冷启动低置信度
                acquisition_score=0.0,
                is_transfer=False
            ))
        
        return suggestions[:n]
    
    def _try_transfer(
        self, target_effect: str, specs: List[ParameterSpec]
    ) -> Optional[TransferResult]:
        """尝试从相似效果迁移参数"""
        similarities = EFFECT_SIMILARITY.get(target_effect, {})
        if not similarities:
            return None
        
        # 找最相似且有观测数据的效果
        best_source = None
        best_sim = 0.0
        
        for source_effect, sim in sorted(similarities.items(), key=lambda x: -x[1]):
            if source_effect in self._observations and len(self._observations[source_effect]) >= 3:
                best_source = source_effect
                best_sim = sim
                break
        
        if not best_source:
            return None
        
        return self.transfer_knowledge(best_source, target_effect)
    
    # ----------------------------------------------------------------
    #  观测更新
    # ----------------------------------------------------------------
    
    def observe(
        self,
        effect_name: str,
        params: Dict[str, float],
        quality: float,
        render_time: float,
        file_size: float,
        success: bool = True
    ) -> None:
        """记录观测结果并更新代理模型
        
        Args:
            effect_name: 效果名称
            params: 参数值
            quality: 质量分数 (0-100)
            render_time: 渲染时间 (秒)
            file_size: 文件大小 (MB)
            success: 是否成功渲染
        """
        obs = Observation(
            params=params,
            quality=quality,
            render_time=render_time,
            file_size=file_size,
            timestamp=time.time(),
            success=success
        )
        
        self._observations.setdefault(effect_name, []).append(obs)
        
        # 更新帕累托前沿
        self._update_pareto_front(effect_name, obs)
        
        # 重建 GP 模型
        specs = PARAMETER_SPACES.get(effect_name, [])
        if specs and len(self._observations[effect_name]) >= 2:
            self._get_or_build_models(effect_name, self._observations[effect_name], specs)
        
        self._save_state()
    
    def _update_pareto_front(self, effect_name: str, new_obs: Observation) -> None:
        """更新帕累托前沿"""
        if not new_obs.success:
            return
        
        objectives = (new_obs.quality, -new_obs.render_time, -new_obs.file_size)
        new_point = ParetoPoint(params=new_obs.params, objectives=objectives, observation=new_obs)
        
        front = self._pareto_fronts.get(effect_name, [])
        front.append(new_point)
        
        # 过滤被支配的点
        filtered = []
        for p in front:
            dominated = False
            for q in front:
                if p is q:
                    continue
                if all(q.objectives[i] >= p.objectives[i] for i in range(3)):
                    if any(q.objectives[i] > p.objectives[i] for i in range(3)):
                        dominated = True
                        break
            if not dominated:
                filtered.append(p)
        
        self._pareto_fronts[effect_name] = filtered
    
    # ----------------------------------------------------------------
    #  M2.3: 跨效果迁移学习
    # ----------------------------------------------------------------
    
    def transfer_knowledge(
        self,
        source_effect: str,
        target_effect: str
    ) -> TransferResult:
        """跨效果参数知识迁移
        
        策略:
        1. 找到源效果帕累托前沿上的最优参数
        2. 映射到目标效果的参数空间（基于参数语义相似度）
        3. 用迁移置信度缩放
        """
        source_obs = self._observations.get(source_effect, [])
        if not source_obs:
            return TransferResult(
                source_effect=source_effect,
                target_effect=target_effect,
                transferred_params={},
                transfer_confidence=0.0
            )
        
        # 找到源效果的最优参数（质量最高）
        best_obs = max(source_obs, key=lambda o: o.quality if o.success else 0)
        
        # 参数映射（基于参数名称语义）
        target_specs = PARAMETER_SPACES.get(target_effect, [])
        transferred = {}
        
        for spec in target_specs:
            # 查找源效果中的相似参数
            best_match = None
            best_match_score = 0.0
            
            for src_param_name, src_val in best_obs.params.items():
                score = self._param_similarity(spec.name, src_param_name)
                if score > best_match_score:
                    best_match_score = score
                    best_match = (src_param_name, src_val)
            
            if best_match and best_match_score > 0.3:
                src_name, src_val = best_match
                # 归一化到目标参数空间
                src_spec = self._find_spec(source_effect, src_name)
                if src_spec:
                    src_norm = (src_val - src_spec.min_val) / max(src_spec.max_val - src_spec.min_val, 1e-6)
                    target_val = spec.min_val + src_norm * (spec.max_val - spec.min_val)
                    transferred[spec.name] = float(np.clip(target_val, spec.min_val, spec.max_val))
                else:
                    transferred[spec.name] = spec.default_val
            else:
                transferred[spec.name] = spec.default_val
        
        # 迁移置信度 = 效果相似度 * 源数据量因子
        sim = EFFECT_SIMILARITY.get(source_effect, {}).get(target_effect, 0.1)
        data_factor = min(1.0, len(source_obs) / 10.0)
        confidence = sim * data_factor
        
        return TransferResult(
            source_effect=source_effect,
            target_effect=target_effect,
            transferred_params=transferred,
            transfer_confidence=confidence
        )
    
    def _param_similarity(self, name1: str, name2: str) -> float:
        """计算两个参数名的语义相似度（简化版）"""
        n1 = name1.lower().replace("_", "")
        n2 = name2.lower().replace("_", "")
        
        # 完全匹配
        if n1 == n2:
            return 1.0
        
        # 包含关系
        if n1 in n2 or n2 in n1:
            return 0.7
        
        # 关键词匹配
        keywords1 = set(n1.split("_")) if "_" in n1 else {n1}
        keywords2 = set(n2.split("_")) if "_" in n2 else {n2}
        
        # 语义等价组
        semantic_groups = [
            {"size", "radius", "width", "scale"},
            {"intensity", "amount", "strength", "power"},
            {"threshold", "cutoff", "limit"},
            {"speed", "evolution", "rate"},
            {"color", "colour", "hue"},
            {"brightness", "lightness", "luminance"},
            {"contrast", "dynamic"},
        ]
        
        overlap = 0
        total = max(len(keywords1), len(keywords2))
        for k1 in keywords1:
            for k2 in keywords2:
                if k1 == k2:
                    overlap += 1
                    break
                for group in semantic_groups:
                    if k1 in group and k2 in group:
                        overlap += 0.8
                        break
        
        return overlap / max(total, 1)
    
    def _find_spec(self, effect_name: str, param_name: str) -> Optional[ParameterSpec]:
        """查找参数规格"""
        for spec in PARAMETER_SPACES.get(effect_name, []):
            if spec.name == param_name:
                return spec
        return None
    
    # ----------------------------------------------------------------
    #  内部方法
    # ----------------------------------------------------------------
    
    def _get_or_build_models(
        self,
        effect_name: str,
        obs_list: List[Observation],
        specs: List[ParameterSpec]
    ) -> Tuple[GaussianProcessRegressor, GaussianProcessRegressor, GaussianProcessRegressor]:
        """获取或构建 GP 代理模型"""
        if effect_name in self._models and len(obs_list) <= 3:
            return self._models[effect_name]
        
        # 参数向量化
        X = np.array([self._params_to_vector(o.params, specs) for o in obs_list if o.success])
        y_quality = np.array([o.quality for o in obs_list if o.success])
        y_render_time = np.array([o.render_time for o in obs_list if o.success])
        y_file_size = np.array([o.file_size for o in obs_list if o.success])
        
        if len(X) < 2:
            # 数据不足，返回默认模型
            default = GaussianProcessRegressor()
            return (default, default, default)
        
        # 归一化
        X_mean = np.mean(X, axis=0)
        X_std = np.std(X, axis=0)
        X_std[X_std < 1e-6] = 1.0
        X_norm = (X - X_mean) / X_std
        
        # 构建三个 GP 模型
        gp_q = GaussianProcessRegressor()
        gp_q.fit(X_norm, (y_quality - np.mean(y_quality)) / max(np.std(y_quality), 1e-6))
        
        gp_rt = GaussianProcessRegressor()
        gp_rt.fit(X_norm, (y_render_time - np.mean(y_render_time)) / max(np.std(y_render_time), 1e-6))
        
        gp_fs = GaussianProcessRegressor()
        gp_fs.fit(X_norm, (y_file_size - np.mean(y_file_size)) / max(np.std(y_file_size), 1e-6))
        
        models = (gp_q, gp_rt, gp_fs)
        self._models[effect_name] = models
        return models
    
    def _params_to_vector(self, params: Dict[str, float], specs: List[ParameterSpec]) -> np.ndarray:
        """参数字典 → 归一化向量"""
        vec = []
        for spec in specs:
            val = params.get(spec.name, spec.default_val)
            norm = (val - spec.min_val) / max(spec.max_val - spec.min_val, 1e-6)
            vec.append(np.clip(norm, 0.0, 1.0))
        return np.array(vec)
    
    def _vector_to_params(self, vec: np.ndarray, specs: List[ParameterSpec]) -> Dict[str, float]:
        """归一化向量 → 参数字典"""
        params = {}
        for i, spec in enumerate(specs):
            if i >= len(vec):
                params[spec.name] = spec.default_val
                continue
            val = spec.min_val + vec[i] * (spec.max_val - spec.min_val)
            params[spec.name] = float(np.clip(val, spec.min_val, spec.max_val))
        return params
    
    def _generate_candidates(
        self,
        specs: List[ParameterSpec],
        n: int,
        constraints: Optional[ParameterConstraints] = None,
        style_context: Optional[StyleVector] = None
    ) -> np.ndarray:
        """生成候选参数点"""
        dim = len(specs)
        candidates = np.random.uniform(0, 1, size=(n, dim))
        
        # 应用硬约束
        if constraints:
            for i, spec in enumerate(specs):
                if spec.name in constraints.hard_bounds:
                    lo, hi = constraints.hard_bounds[spec.name]
                    lo_norm = (lo - spec.min_val) / max(spec.max_val - spec.min_val, 1e-6)
                    hi_norm = (hi - spec.min_val) / max(spec.max_val - spec.min_val, 1e-6)
                    candidates[:, i] = np.clip(candidates[:, i], lo_norm, hi_norm)
        
        return candidates
    
    def _latin_hypercube(
        self, specs: List[ParameterSpec], n: int
    ) -> List[np.ndarray]:
        """拉丁超立方采样"""
        dim = len(specs)
        samples = []
        
        for i in range(n):
            sample = np.zeros(dim)
            for j in range(dim):
                # 在 [i/n, (i+1)/n] 区间内均匀采样
                lo = i / n
                hi = (i + 1) / n
                sample[j] = np.random.uniform(lo, hi)
            samples.append(sample)
        
        # 随机打乱每个维度
        result = np.array(samples)
        for j in range(dim):
            np.random.shuffle(result[:, j])
        
        return [result[i] for i in range(n)]
    
    def _apply_style_adjustment(
        self, params: Dict[str, float], specs: List[ParameterSpec],
        style: StyleVector
    ) -> Dict[str, float]:
        """根据风格调整参数"""
        adjusted = dict(params)
        
        # 强度调整: 高能量风格 → 增大效果强度
        intensity_factor = style.intensity
        
        for spec in specs:
            if spec.name in adjusted:
                val = adjusted[spec.name]
                mid = (spec.min_val + spec.max_val) / 2
                # 高能量风格: 参数偏向高值
                adjusted[spec.name] = float(np.clip(
                    mid + (val - mid) * (0.5 + intensity_factor),
                    spec.min_val, spec.max_val
                ))
        
        return adjusted
    
    def _apply_constraints(
        self, params: Dict[str, float], constraints: ParameterConstraints
    ) -> Dict[str, float]:
        """应用参数约束"""
        constrained = dict(params)
        for param_name, (lo, hi) in constraints.hard_bounds.items():
            if param_name in constrained:
                constrained[param_name] = float(np.clip(constrained[param_name], lo, hi))
        return constrained
    
    def _build_pareto_front(
        self, effect_name: str, obs_list: List[Observation]
    ) -> List[ParetoPoint]:
        """构建帕累托前沿"""
        return self._pareto_fronts.get(effect_name, [])
    
    def _default_suggestions(
        self, effect_name: str, n: int
    ) -> List[ParameterSuggestion]:
        """默认推荐（未知效果）"""
        specs = PARAMETER_SPACES.get(effect_name, [])
        suggestions = []
        for _ in range(n):
            params = {s.name: s.default_val for s in specs}
            suggestions.append(ParameterSuggestion(
                params=params, confidence=0.0
            ))
        return suggestions
    
    # ----------------------------------------------------------------
    #  持久化
    # ----------------------------------------------------------------
    
    def _save_state(self) -> None:
        """持久化观测历史和帕累托前沿"""
        try:
            # 保存观测历史
            obs_path = self._data_dir / "observations.json"
            obs_data = {}
            for effect, obs_list in self._observations.items():
                obs_data[effect] = [
                    {
                        "params": o.params,
                        "quality": o.quality,
                        "render_time": o.render_time,
                        "file_size": o.file_size,
                        "timestamp": o.timestamp,
                        "success": o.success
                    }
                    for o in obs_list[-50:]  # 每个效果最多保存50条
                ]
            with open(obs_path, "w", encoding="utf-8") as f:
                json.dump(obs_data, f, ensure_ascii=False, indent=2)
            
            # 保存帕累托前沿
            pareto_path = self._data_dir / "pareto_fronts.json"
            pareto_data = {}
            for effect, front in self._pareto_fronts.items():
                pareto_data[effect] = [
                    {"params": p.params, "objectives": list(p.objectives)}
                    for p in front
                ]
            with open(pareto_path, "w", encoding="utf-8") as f:
                json.dump(pareto_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[BayesianOptimizer] Save state failed: {e}")
    
    def _load_state(self) -> None:
        """加载持久化状态"""
        try:
            obs_path = self._data_dir / "observations.json"
            if obs_path.exists():
                with open(obs_path, "r", encoding="utf-8") as f:
                    obs_data = json.load(f)
                for effect, obs_list in obs_data.items():
                    self._observations[effect] = [
                        Observation(
                            params=o["params"],
                            quality=o["quality"],
                            render_time=o["render_time"],
                            file_size=o["file_size"],
                            timestamp=o.get("timestamp", 0.0),
                            success=o.get("success", True)
                        )
                        for o in obs_list
                    ]
            
            pareto_path = self._data_dir / "pareto_fronts.json"
            if pareto_path.exists():
                with open(pareto_path, "r", encoding="utf-8") as f:
                    pareto_data = json.load(f)
                for effect, front_data in pareto_data.items():
                    self._pareto_fronts[effect] = [
                        ParetoPoint(
                            params=p["params"],
                            objectives=tuple(p["objectives"]),
                            observation=Observation(params=p["params"], quality=0,
                                                    render_time=0, file_size=0)
                        )
                        for p in front_data
                    ]
        except Exception as e:
            logger.warning(f"[BayesianOptimizer] Load state failed: {e}")
    
    # ----------------------------------------------------------------
    #  统计
    # ----------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取优化器统计信息"""
        return {
            "tracked_effects": len(self._observations),
            "total_observations": sum(len(v) for v in self._observations.values()),
            "pareto_fronts": {k: len(v) for k, v in self._pareto_fronts.items()},
            "built_models": len(self._models),
        }
    
    def get_pareto_front(self, effect_name: str) -> List[ParetoPoint]:
        """获取指定效果的帕累托前沿"""
        return self._pareto_fronts.get(effect_name, [])

    # ================================================================
    #  P3.4: 多目标贝叶斯优化扩展
    # ================================================================

    def expected_improvement(
        self,
        X_candidates: np.ndarray,
        model: "GaussianProcessRegressor",
        best_y: float,
        xi: float = 0.01,
    ) -> np.ndarray:
        """计算候选点的 Expected Improvement (EI) 采集函数值

        适用于单目标最大化问题。EI 公式 (Jones 1998):

            EI(x) = (f_best - mu(x) - ξ) · Φ(z) + σ(x) · φ(z)

        其中:
            z = (f_best - mu(x) - ξ) / σ(x)
            Φ: 标准正态 CDF
            φ: 标准正态 PDF
            ξ (xi): 探索-利用平衡参数 (越大越鼓励探索)
            f_best: 当前最优观测值 (最大化场景下取 max y)

        当 σ → 0 时, EI 退化为 max(0, f_best - mu - ξ)。

        Args:
            X_candidates: (n_candidates, n_features) 候选参数点
            model: 已拟合的 GaussianProcessRegressor
            best_y: 当前最优观测目标值 (最大化场景)
            xi: 探索参数 (默认 0.01, 典型范围 [0, 0.1])

        Returns:
            ei: (n_candidates,) 每个候选点的 EI 值 (非负)
        """
        mu, sigma = model.predict(X_candidates, return_std=True)
        if sigma is None:
            sigma = np.ones_like(mu) * 1e-6
        sigma = np.maximum(sigma, 1e-10)

        # 改进量 = 当前最优 - 预测均值 - xi
        improvement = best_y - mu - xi
        z = improvement / sigma

        ei = improvement * _norm_cdf(z) + sigma * _norm_pdf(z)
        # EI 非负
        return np.maximum(ei, 0.0)

    def multi_objective_optimize(
        self,
        param_specs: List["ParamSpec"],
        objective_specs: List["ObjectiveSpec"],
        objective_fn: "Callable[[Dict[str, float]], Dict[str, float]]",
        n_iterations: int = 30,
        n_initial_samples: int = 5,
        seed: Optional[int] = None,
    ) -> "ParetoFront":
        """多目标贝叶斯优化

        流程:
        1. 初始化: 拉丁超立方采样生成 n_initial_samples 个初始点
        2. 迭代优化 (n_iterations 次):
            a. 为每个目标拟合一个 GP 模型
            b. 用 EHVI/EI 采集函数选择下一评估点
            c. 调用 objective_fn 评估目标值
            d. 更新 GP 模型与帕累托前沿
        3. 返回最终帕累托前沿及所有评估结果

        数学原理:
        - 多目标帕累托支配: 解 A 支配 B 当且仅当
            ∀i: f_i(A) ≥ f_i(B) 且 ∃j: f_j(A) > f_j(B)
            (maximize 场景; minimize 时取反)
        - 超体积 HV(P) = Λ({ q | ∃p ∈ P : p ≽ q ≽ r_ref })
            衡量帕累托前沿的"体积", 越大代表前沿越优

        Args:
            param_specs: 参数规格列表 (ParamSpec)
            objective_specs: 目标规格列表 (ObjectiveSpec)
            objective_fn: 目标函数, 输入 {param_name: value}, 返回 {obj_name: value}
            n_iterations: 贝叶斯优化迭代次数
            n_initial_samples: 初始采样数 (拉丁超立方)
            seed: 随机种子 (None = 不固定)

        Returns:
            ParetoFront: 包含所有解、帕累托最优解、超体积、各目标最优解
        """
        if not param_specs:
            return ParetoFront()
        if not objective_specs:
            return ParetoFront(solutions=[
                ParetoSolution(params={}, objectives={}, is_pareto=True)
            ], pareto_solutions=[
                ParetoSolution(params={}, objectives={}, is_pareto=True)
            ], n_evaluations=0)

        if seed is not None:
            rng = np.random.RandomState(seed)
            np.random.seed(seed)

        # Step 1: 初始采样 (拉丁超立方 + 评估)
        X_obs: List[np.ndarray] = []
        y_obs: Dict[str, List[float]] = {obj.name: [] for obj in objective_specs}
        params_obs: List[Dict[str, float]] = []
        objectives_obs: List[Dict[str, float]] = []

        # 拉丁超立方初始采样
        initial_samples = self._lhs_generic(param_specs, n_initial_samples)
        for sample_vec in initial_samples:
            params = self._vec_to_params_generic(sample_vec, param_specs)
            try:
                obj_values = objective_fn(params)
            except Exception as e:
                logger.warning(
                    "[BayesianOptimizer] objective_fn failed at %s: %s",
                    params, e,
                )
                continue
            X_obs.append(sample_vec)
            params_obs.append(params)
            objectives_obs.append(dict(obj_values))
            for obj in objective_specs:
                y_obs[obj.name].append(float(obj_values.get(obj.name, 0.0)))

        # Step 2: 贝叶斯优化迭代
        for it in range(n_iterations):
            if len(X_obs) < 2:
                # 数据不足, 继续随机采样
                sample_vec = np.array([
                    np.random.uniform(s.low, s.high) for s in param_specs
                ])
                params = self._vec_to_params_generic(sample_vec, param_specs)
                try:
                    obj_values = objective_fn(params)
                except Exception:
                    continue
                X_obs.append(sample_vec)
                params_obs.append(params)
                objectives_obs.append(dict(obj_values))
                for obj in objective_specs:
                    y_obs[obj.name].append(float(obj_values.get(obj.name, 0.0)))
                continue

            X_arr = np.array(X_obs)
            # 归一化 X
            x_mean = X_arr.mean(axis=0)
            x_std = X_arr.std(axis=0)
            x_std[x_std < 1e-6] = 1.0
            X_norm = (X_arr - x_mean) / x_std

            # 为每个目标构建 GP
            gp_models: Dict[str, GaussianProcessRegressor] = {}
            for obj in objective_specs:
                y = np.array(y_obs[obj.name])
                gp = GaussianProcessRegressor()
                if len(y) >= 2:
                    y_norm = (y - y.mean()) / max(y.std(), 1e-6)
                    gp.fit(X_norm, y_norm)
                gp_models[obj.name] = gp

            # 生成候选点 (随机采样)
            n_candidates = 100
            candidates = np.array([
                np.random.uniform(s.low, s.high) for s in param_specs
                for _ in range(n_candidates)
            ]).reshape(n_candidates, len(param_specs))
            # 归一化候选点
            cand_norm = (candidates - x_mean) / x_std

            # 计算每个目标的 EI (maximize 场景)
            ei_scores = np.zeros(n_candidates)
            for obj in objective_specs:
                y = np.array(y_obs[obj.name])
                if obj.direction == "maximize":
                    best_y = y.max()
                else:  # minimize → 取负转为 maximize
                    best_y = -y.min()
                gp = gp_models[obj.name]
                ei = self.expected_improvement(cand_norm, gp, best_y, xi=0.01)
                # minimize 场景: 取负后 best_y = -y.min()
                ei_scores += ei * obj.weight

            # 选择 EI 最高的候选点
            best_idx = int(np.argmax(ei_scores))
            next_vec = candidates[best_idx]
            next_params = self._vec_to_params_generic(next_vec, param_specs)
            try:
                next_obj = objective_fn(next_params)
            except Exception:
                continue
            X_obs.append(next_vec)
            params_obs.append(next_params)
            objectives_obs.append(dict(next_obj))
            for obj in objective_specs:
                y_obs[obj.name].append(float(next_obj.get(obj.name, 0.0)))

        # Step 3: 计算帕累托前沿
        solutions: List[ParetoSolution] = []
        for i in range(len(params_obs)):
            solutions.append(ParetoSolution(
                params=params_obs[i],
                objectives=objectives_obs[i],
                is_pareto=True,  # 默认假设, 后续过滤
            ))

        pareto_solutions = self._extract_pareto_solutions(
            solutions, objective_specs
        )

        # 标记非帕累托解
        pareto_ids = {id(p) for p in pareto_solutions}
        for s in solutions:
            if id(s) not in pareto_ids:
                s.is_pareto = False

        # 计算超体积 (2D 精确, 高维 MC)
        hypervolume = self._compute_hv_generic(
            pareto_solutions, objective_specs
        )

        # 各目标单独最优
        best_per_objective: Dict[str, ParetoSolution] = {}
        for obj in objective_specs:
            if not solutions:
                continue
            if obj.direction == "maximize":
                best = max(solutions, key=lambda s: s.objectives.get(obj.name, -np.inf))
            else:
                best = min(solutions, key=lambda s: s.objectives.get(obj.name, np.inf))
            best_per_objective[obj.name] = best

        return ParetoFront(
            solutions=solutions,
            pareto_solutions=pareto_solutions,
            hypervolume=hypervolume,
            best_per_objective=best_per_objective,
            n_evaluations=len(solutions),
        )

    # ----------------------------------------------------------------
    #  multi_objective_optimize 辅助方法
    # ----------------------------------------------------------------

    def _lhs_generic(
        self,
        param_specs: List["ParamSpec"],
        n: int,
    ) -> List[np.ndarray]:
        """通用拉丁超立方采样 (基于归一化空间 [0,1])"""
        dim = len(param_specs)
        if dim == 0 or n <= 0:
            return []
        # 每个维度在 [i/n, (i+1)/n] 内随机采样
        result = np.zeros((n, dim))
        for j in range(dim):
            for i in range(n):
                result[i, j] = np.random.uniform(i / n, (i + 1) / n)
            # 打乱该维度
            np.random.shuffle(result[:, j])
        # 转换回参数原始范围
        samples: List[np.ndarray] = []
        for i in range(n):
            vec = np.array([
                param_specs[j].low +
                result[i, j] * (param_specs[j].high - param_specs[j].low)
                for j in range(dim)
            ])
            samples.append(vec)
        return samples

    def _vec_to_params_generic(
        self,
        vec: np.ndarray,
        param_specs: List["ParamSpec"],
    ) -> Dict[str, float]:
        """向量 → 参数字典 (通用版)"""
        params: Dict[str, float] = {}
        for i, spec in enumerate(param_specs):
            if i >= len(vec):
                params[spec.name] = spec.default
                continue
            val = float(np.clip(vec[i], spec.low, spec.high))
            if spec.dtype == "int":
                val = float(int(round(val)))
            params[spec.name] = val
        return params

    def _extract_pareto_solutions(
        self,
        solutions: List["ParetoSolution"],
        objective_specs: List["ObjectiveSpec"],
    ) -> List["ParetoSolution"]:
        """提取帕累托最优解

        帕累托支配规则 (假设所有目标都已转为 maximize 方向):
            A 支配 B ⟺ ∀i: A_i ≥ B_i ∧ ∃j: A_j > B_j

        对于 minimize 目标, 我们在比较前取反。
        """
        if not solutions:
            return []

        n = len(solutions)
        is_pareto = [True] * n

        # 预处理: 把每个解的目标值转为统一的 maximize 方向
        # direction_to_sign[name] = +1 if maximize else -1
        sign: Dict[str, float] = {}
        for obj in objective_specs:
            sign[obj.name] = 1.0 if obj.direction == "maximize" else -1.0

        # 标准化目标值数组 (maximize 方向)
        obj_names = [obj.name for obj in objective_specs]
        obj_matrix = np.zeros((n, len(obj_names)))
        for i, sol in enumerate(solutions):
            for j, name in enumerate(obj_names):
                obj_matrix[i, j] = sign[name] * float(
                    sol.objectives.get(name, 0.0)
                )

        # 支配检查
        for i in range(n):
            if not is_pareto[i]:
                continue
            for j in range(n):
                if i == j or not is_pareto[j]:
                    continue
                # j 支配 i?
                if np.all(obj_matrix[j] >= obj_matrix[i]) and np.any(
                    obj_matrix[j] > obj_matrix[i]
                ):
                    is_pareto[i] = False
                    break

        return [solutions[i] for i in range(n) if is_pareto[i]]

    def _compute_hv_generic(
        self,
        pareto_solutions: List["ParetoSolution"],
        objective_specs: List["ObjectiveSpec"],
    ) -> float:
        """计算超体积指标 (2D 精确, 高维 MC 近似)

        超体积定义:
            HV(P) = ∫_{R^n} 1{∃p ∈ P : p ≽ q ≽ r_ref} dq

        参考点 r_ref 取所有目标的最差值 (maximize 场景取 min, minimize 取 max)。
        """
        if not pareto_solutions or not objective_specs:
            return 0.0

        sign: Dict[str, float] = {}
        for obj in objective_specs:
            sign[obj.name] = 1.0 if obj.direction == "maximize" else -1.0

        obj_names = [obj.name for obj in objective_specs]
        n = len(pareto_solutions)
        dim = len(obj_names)

        # 标准化目标矩阵 (统一 maximize 方向)
        mat = np.zeros((n, dim))
        for i, sol in enumerate(pareto_solutions):
            for j, name in enumerate(obj_names):
                mat[i, j] = sign[name] * float(sol.objectives.get(name, 0.0))

        # 参考点 = 每维的最小值 - 1
        ref = mat.min(axis=0) - 1.0

        # 1D: 区间长度
        if dim == 1:
            return float(max(0.0, mat.max() - ref[0]))

        # 2D: 扫描线算法
        if dim == 2:
            # 按第一维降序排序
            sorted_idx = np.argsort(-mat[:, 0])
            hv = 0.0
            prev_y = ref[1]
            for idx in sorted_idx:
                if mat[idx, 1] > prev_y:
                    hv += (mat[idx, 0] - ref[0]) * (mat[idx, 1] - prev_y)
                    prev_y = mat[idx, 1]
            return float(max(0.0, hv))

        # 高维: Monte Carlo 近似
        n_mc = 1000
        lower = ref
        upper = mat.max(axis=0)
        rng_range = upper - lower
        if np.any(rng_range <= 0):
            return 0.0

        samples = np.random.uniform(lower, upper, size=(n_mc, dim))
        dominated = 0
        for s in samples:
            for p in mat:
                if np.all(p >= s):
                    dominated += 1
                    break
        total_vol = float(np.prod(rng_range))
        return float(total_vol * dominated / n_mc)


# ============================================================================
#  全局单例
# ============================================================================

_global_optimizer: Optional[BayesianParameterOptimizer] = None


def get_optimizer(data_dir: str | None = None) -> BayesianParameterOptimizer:
    """获取全局优化器单例

    不传 data_dir 时，自动走默认的 APPDATA 绝对路径（跨进程共享，不受 CWD 影响）。
    """
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = BayesianParameterOptimizer(
            data_dir if data_dir else BayesianParameterOptimizer.DEFAULT_DATA_DIR
        )
    return _global_optimizer
