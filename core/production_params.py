"""
Production Director - 编排器参数契约定义
==========================================
渲染编排器参数数据结构定义，包含素材、音乐、时长、目标 IP 等核心契约。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TargetIP(Enum):
    """目标 IP 枚举"""
    AMV_HIGH_ENERGY = "amv_high_energy"
    AMV_EPIC_EXTREME = "amv_epic_extreme"
    MANGA_EDIT = "manga_edit"
    CINEMATIC = "cinematic"
    CYBERPUNK = "cyberpunk"


@dataclass
class ProductionParam:
    """单个生产参数契约
    
    核心契约:
    1. 时长归一化：所有 duration 参数必须在 [5, 300] 秒范围内
    2. 素材数量限制：sources 列表最大支持 50 个素材
    3. 目标 IP 标准化
    """
    name: str
    value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    target_ip: TargetIP = TargetIP.AMV_HIGH_ENERGY
    duration_sec: float = 30.0
    
    def validate(self) -> bool:
        """参数有效性验证"""
        if not (self.min_value <= self.value <= self.max_value):
            return False
        if not (5.0 <= self.duration_sec <= 300.0):
            return False
        return True
    
    def copy(self) -> 'ProductionParam':
        """深拷贝保护"""
        return ProductionParam(
            name=self.name,
            value=self.value,
            min_value=self.min_value,
            max_value=self.max_value,
            target_ip=self.target_ip,
            duration_sec=self.duration_sec
        )


@dataclass
class ProductionConfig:
    """生产配置契约
    
    核心契约:
    1. 配置名称唯一性
    2. 参数列表完整性
    3. 素材来源合法性
    """
    name: str
    category: str
    params: Dict[str, ProductionParam] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    def add_param(self, param: ProductionParam) -> None:
        """添加参数并验证"""
        if not param.validate():
            raise ValueError(f"Invalid parameter: {param.name}")
        self.params[param.name] = param
    
    def get_effective_params(self) -> Dict[str, float]:
        """获取有效参数字典"""
        return {name: p.value for name, p in self.params.items()}
