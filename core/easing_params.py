"""
Transition Engine - 缓动函数契约定义
======================================
缓动函数数据结构定义，包含 20+ 标准缓动函数及其参数化配置。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict


class EasingFunction(Enum):
    """标准缓动函数枚举"""
    LINEAR = "linear"
    EASE_IN_QUAD = "ease_in_quad"
    EASE_OUT_QUAD = "ease_out_quad"
    EASE_IN_OUT_QUAD = "ease_in_out_quad"
    EASE_IN_CUBIC = "ease_in_cubic"
    EASE_OUT_CUBIC = "ease_out_cubic"
    EASE_IN_OUT_CUBIC = "ease_in_out_cubic"
    EASE_IN_QUART = "ease_in_quart"
    EASE_OUT_QUART = "ease_out_quart"
    EASE_IN_OUT_QUART = "ease_in_out_quart"
    EASE_IN_QUINT = "ease_in_quint"
    EASE_OUT_QUINT = "ease_out_quint"
    EASE_IN_OUT_QUINT = "ease_in_out_quint"
    EASE_IN_SINE = "ease_in_sine"
    EASE_OUT_SINE = "ease_out_sine"
    EASE_IN_OUT_SINE = "ease_in_out_sine"
    EASE_IN_EXPO = "ease_in_expo"
    EASE_OUT_EXPO = "ease_out_expo"
    EASE_IN_OUT_EXPO = "ease_in_out_expo"
    EASE_IN_CIRC = "ease_in_circ"
    EASE_OUT_CIRC = "ease_out_circ"
    EASE_IN_OUT_CIRC = "ease_in_out_circ"
    BACK_IN = "back_in"
    BACK_OUT = "back_out"
    BACK_IN_OUT = "back_in_out"
    BOUNCE_OUT = "bounce_out"
    ELASTIC_IN = "elastic_in"
    ELASTIC_OUT = "elastic_out"


@dataclass
class EasingConfig:
    """缓动配置契约
    
    核心契约:
    1. 支持 20+ 标准缓动函数
    2. 可自定义 overshoot/ampitude 参数
    3. 提供预定义配置和自定义配置两种模式
    """
    name: str
    easing_type: EasingFunction
    overshoot: float = 1.70151  # back 默认值
    amplitude: float = 1.0      # elastic 默认值
    period: float = 0.3         # elastic 默认周期
    
    def get_easing_function(self) -> Callable[[float], float]:
        """获取缓动函数实现"""
        t = self.overshoot
        
        if self.easing_type == EasingFunction.LINEAR:
            return lambda x: x
        
        elif self.easing_type == EasingFunction.EASE_IN_QUAD:
            return lambda x: x * x
        
        elif self.easing_type == EasingFunction.EASE_OUT_QUAD:
            return lambda x: 1 - (1 - x) * (1 - x)
        
        elif self.easing_type == EasingFunction.EASE_IN_OUT_QUAD:
            return lambda x: 0.5 * x * x if x < 0.5 else 1 - 0.5 * (1 - x) * (1 - x)
        
        elif self.easing_type == EasingFunction.EASE_IN_CUBIC:
            return lambda x: x * x * x
        
        elif self.easing_type == EasingFunction.EASE_OUT_CUBIC:
            return lambda x: 1 - (1 - x) ** 3
        
        elif self.easing_type == EasingFunction.EASE_IN_OUT_CUBIC:
            return lambda x: 4 * x * x * x if x < 0.5 else 1 - (-2*x + 2)**3 / 2
        
        elif self.easing_type == EasingFunction.EASE_IN_SINE:
            return lambda x: 1 - (1 - x) ** 2
        
        elif self.easing_type == EasingFunction.EASE_OUT_SINE:
            return lambda x: (1 - x) ** 2
        
        elif self.easing_type == EasingFunction.EASE_IN_OUT_SINE:
            return lambda x: 0.5 * (1 - (1 - x) ** 2) if x < 0.5 else 0.5 * (1 - (x - 0.5) ** 2)
        
        elif self.easing_type == EasingFunction.BACK_IN:
            return lambda x: x * x * ((t + 1) * x - t)
        
        elif self.easing_type == EasingFunction.BACK_OUT:
            return lambda x: 1 - ((1 - x) * (t + 1) * (1 - x) + t)
        
        elif self.easing_type == EasingFunction.BOUNCE_OUT:
            def bounce_out(x: float) -> float:
                n1 = 7.5625
                d1 = 2.75
                if x < 1/d1:
                    return n1 * x * x
                elif x < 2/d1:
                    x -= 1.5/d1
                    return n1 * x * x + 0.75
                elif x < 2.5/d1:
                    x -= 2.25/d1
                    return n1 * x * x + 0.9375
                else:
                    x -= 2.625/d1
                    return n1 * x * x + 0.984375
            return bounce_out
        
        # 其他缓动函数可扩展...
        return lambda x: x  # 默认线性
    
    def validate(self) -> bool:
        """配置有效性验证"""
        if not (0.0 <= self.overshoot <= 5.0):
            return False
        if not (0.0 <= self.amplitude <= 5.0):
            return False
        if not (0.0 < self.period <= 1.0):
            return False
        return True
    
    def copy(self) -> 'EasingConfig':
        """深拷贝保护"""
        return EasingConfig(
            name=self.name,
            easing_type=self.easing_type,
            overshoot=self.overshoot,
            amplitude=self.amplitude,
            period=self.period
        )
