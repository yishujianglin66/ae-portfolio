"""
Filter Engine - 滤镜参数契约定义
==================================
滤镜参数数据结构定义，包含归一化、范围验证、强度锚缩放等核心契约。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FilterParam:
    """单个滤镜参数契约
    
    核心契约:
    1. 范围归一化：所有参数必须在 [0, 1] 范围内
    2. 强度锚缩放：dose 参数影响基数效果
    3. 深拷贝保护：避免副作用
    """
    name: str
    value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    dose: float = 1.0  # 强度锚
    
    def validate(self) -> bool:
        """参数有效性验证"""
        if not (self.min_value <= self.value <= self.max_value):
            return False
        if not (0.0 <= self.dose <= 2.0):  # dose 范围限制
            return False
        return True
    
    def scaled_value(self) -> float:
        """计算缩放后的实际值 (考虑 dose)"""
        normalized = (self.value - self.min_value) / (self.max_value - self.min_value)
        scaled = normalized * self.dose
        return max(self.min_value, min(self.max_value, scaled))
    
    def copy(self) -> 'FilterParam':
        """深拷贝保护"""
        return FilterParam(
            name=self.name,
            value=self.value,
            min_value=self.min_value,
            max_value=self.max_value,
            dose=self.dose
        )


@dataclass
class FilterPreset:
    """滤镜预设契约
    
    核心契约:
    1. 预设名称唯一性
    2. 参数列表完整性
    3. 跨软件兼容性标记
    """
    name: str
    category: str
    parameters: list[FilterParam] = field(default_factory=list)
    software_compatible: list[str] = field(default_factory=list)
    description: str = ""
    
    def add_parameter(self, param: FilterParam) -> None:
        """添加参数并验证"""
        if not param.validate():
            raise ValueError(f"Invalid parameter: {param.name}")
        self.parameters.append(param)
    
    def get_effective_parameters(self, dose: float = 1.0) -> dict[str, float]:
        """获取有效参数 (考虑剂量缩放)"""
        return {p.name: p.scaled_value() * dose for p in self.parameters}
