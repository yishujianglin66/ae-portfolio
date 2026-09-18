"""
Transition Engine - 过渡参数契约定义
=======================================
过渡效果参数数据结构定义，包含持续时间、缓动函数、跨软件兼容性等核心契约。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EasingType(Enum):
    """缓动类型枚举"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BACK_IN = "back_in"
    BACK_OUT = "back_out"
    BOUNCE_OUT = "bounce_out"
    CIRC_IN = "circ_in"
    CIRC_OUT = "circ_out"
    ELASTIC_IN = "elastic_in"
    ELASTIC_OUT = "elastic_out"
    POWER_IN_1 = "power_in_1"
    POWER_IN_2 = "power_in_2"
    POWER_IN_3 = "power_in_3"
    POWER_IN_4 = "power_in_4"
    POWER_OUT_1 = "power_out_1"
    POWER_OUT_2 = "power_out_2"
    POWER_OUT_3 = "power_out_3"
    POWER_OUT_4 = "power_out_4"


@dataclass
class TransitionParam:
    """单个过渡参数契约
    
    核心契约:
    1. 持续时间归一化：所有 duration 参数必须在 [0.1, 5.0] 秒范围内
    2. 缓动函数标准化：支持 20+ 标准缓动函数
    3. 跨软件兼容性标记
    """
    name: str
    value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    easing: EasingType = EasingType.EASE_IN_OUT
    duration_sec: float = 1.0  # 默认持续时间
    
    def validate(self) -> bool:
        """参数有效性验证"""
        if not (self.min_value <= self.value <= self.max_value):
            return False
        if not (0.1 <= self.duration_sec <= 5.0):
            return False
        return True
    
    def copy(self) -> 'TransitionParam':
        """深拷贝保护"""
        return TransitionParam(
            name=self.name,
            value=self.value,
            min_value=self.min_value,
            max_value=self.max_value,
            easing=self.easing,
            duration_sec=self.duration_sec
        )


@dataclass
class TransitionConfig:
    """过渡配置契约
    
    核心契约:
    1. 配置名称唯一性
    2. 参数列表完整性
    3. 跨软件兼容性标记
    """
    name: str
    category: str
    params: Dict[str, TransitionParam] = field(default_factory=dict)
    software_support: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def add_param(self, param: TransitionParam) -> None:
        """添加参数并验证"""
        if not param.validate():
            raise ValueError(f"Invalid parameter: {param.name}")
        self.params[param.name] = param
    
    def get_effective_params(self) -> Dict[str, float]:
        """获取有效参数字典"""
        return {name: p.value for name, p in self.params.items()}
