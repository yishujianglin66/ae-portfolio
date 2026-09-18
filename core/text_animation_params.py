"""
Text Animation Engine - 文字动画参数契约定义
===============================================
文字动画参数数据结构定义，包含字体、位置、缩放、旋转等核心契约。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TextAnimationType(Enum):
    """文字动画类型枚举"""
    FADE_IN = "fade_in"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    SCALE_IN = "scale_in"
    ROTATE_IN = "rotate_in"
    BOUNCE_IN = "bounce_in"
    TYPOGRAPHY = "typography"
    GLITCH = "glitch"
    TYPEWRITER = "typewriter"


@dataclass
class TextParam:
    """单个文字动画参数契约
    
    核心契约:
    1. 位置归一化：所有 position 参数必须在 [-1.0, 1.0] 范围内
    2. 缩放归一化：所有 scale 参数必须在 [0.1, 3.0] 范围内
    3. 旋转归一化：所有 rotation 参数必须在 [-360, 360] 度范围内
    """
    name: str
    value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    animation_type: TextAnimationType = TextAnimationType.FADE_IN
    duration_sec: float = 1.0
    
    def validate(self) -> bool:
        """参数有效性验证"""
        if not (self.min_value <= self.value <= self.max_value):
            return False
        if not (0.1 <= self.duration_sec <= 5.0):
            return False
        return True
    
    def copy(self) -> 'TextParam':
        """深拷贝保护"""
        return TextParam(
            name=self.name,
            value=self.value,
            min_value=self.min_value,
            max_value=self.max_value,
            animation_type=self.animation_type,
            duration_sec=self.duration_sec
        )


@dataclass
class TextAnimationConfig:
    """文字动画配置契约
    
    核心契约:
    1. 配置名称唯一性
    2. 参数列表完整性
    3. 字体兼容性标记
    """
    name: str
    category: str
    params: Dict[str, TextParam] = field(default_factory=dict)
    font_support: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def add_param(self, param: TextParam) -> None:
        """添加参数并验证"""
        if not param.validate():
            raise ValueError(f"Invalid parameter: {param.name}")
        self.params[param.name] = param
    
    def get_effective_params(self) -> Dict[str, float]:
        """获取有效参数字典"""
        return {name: p.value for name, p in self.params.items()}
