#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
木偶风格引擎 - 核心风格化引擎
================================

提供 8 种木偶风格预设，生成 AE 效果配置和关键帧数据。

支持风格:
1. wooden_puppet - 木质木偶 (木纹材质 + 关节连接)
2. ceramic_puppet - 陶瓷木偶 (光滑釉质 + 裂纹细节)
3. marionette_puppet - 提线木偶 (丝线 + 关节球)
4. clay_puppet - 黏土木偶 (黏土质感 + 手工痕迹)
5. paper_puppet - 纸艺木偶 (折痕 + 剪纸纹理)
6. metal_puppet - 金属木偶 (金属光泽 + 铆钉连接)
7. fabric_puppet - 布艺木偶 (布料纹理 + 缝线)
8. glass_puppet - 玻璃木偶 (透明折射 + 高光)
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class PuppetStyleType(Enum):
    """木偶风格类型枚举"""
    WOODEN_PUPPET = "wooden_puppet"
    CERAMIC_PUPPET = "ceramic_puppet"
    MARIONETTE_PUPPET = "marionette_puppet"
    CLAY_PUPPET = "clay_puppet"
    PAPER_PUPPET = "paper_puppet"
    METAL_PUPPET = "metal_puppet"
    FABRIC_PUPPET = "fabric_puppet"
    GLASS_PUPPET = "glass_puppet"


@dataclass
class PuppetStyleConfig:
    """木偶风格配置
    
    Attributes:
        style_type: 风格类型
        intensity: 强度 (0.0-2.0)
        enable_joints: 启用关节效果
        enable_texture: 启用纹理效果
        enable_lighting: 启用灯光效果
        color_tint: 色调偏移 (-1.0~1.0)
    """
    style_type: PuppetStyleType = PuppetStyleType.WOODEN_PUPPET
    intensity: float = 1.0
    enable_joints: bool = True
    enable_texture: bool = True
    enable_lighting: bool = True
    color_tint: float = 0.0
    
    def validate(self) -> bool:
        """配置有效性验证"""
        if not (0.0 <= self.intensity <= 2.0):
            return False
        if not (-1.0 <= self.color_tint <= 1.0):
            return False
        return True


@dataclass
class PuppetStyleResult:
    """木偶风格化处理结果
    
    Attributes:
        success: 是否成功
        style_applied: 应用的风格类型
        keyframes: 关键帧数据列表
        effects: AE 效果配置字典
        warnings: 警告信息列表
    """
    success: bool = False
    style_applied: Optional[PuppetStyleType] = None
    keyframes: List[Dict[str, Any]] = field(default_factory=list)
    effects: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


class PuppetStyleEngine:
    """木偶风格引擎
    
    核心能力:
    - 8 种木偶风格预设
    - 根据人物姿态生成针对性效果
    - AE JSX 脚本生成
    - 三级降级机制
    """
    
    STYLE_PRESETS = {
        PuppetStyleType.WOODEN_PUPPET: {
            "description": "木质木偶风格",
            "texture": "wood_grain",
            "joints": ["shoulder", "elbow", "knee"],
            "color_range": [0.3, 0.6],
            "intensity_range": [0.8, 1.5],
        },
        PuppetStyleType.CERAMIC_PUPPET: {
            "description": "陶瓷木偶风格",
            "texture": "glazed_ceramic",
            "joints": ["neck", "wrist", "ankle"],
            "color_range": [0.6, 0.9],
            "intensity_range": [1.0, 1.8],
        },
        PuppetStyleType.MARIONETTE_PUPPET: {
            "description": "提线木偶风格",
            "texture": "string_lines",
            "joints": ["head", "hands", "feet"],
            "color_range": [0.2, 0.5],
            "intensity_range": [0.5, 1.2],
        },
        PuppetStyleType.CLAY_PUPPET: {
            "description": "黏土木偶风格",
            "texture": "clay_handmade",
            "joints": ["all_limbs"],
            "color_range": [0.4, 0.7],
            "intensity_range": [0.7, 1.4],
        },
        PuppetStyleType.PAPER_PUPPET: {
            "description": "纸艺木偶风格",
            "texture": "paper_folds",
            "joints": ["hinge_joints"],
            "color_range": [0.5, 0.8],
            "intensity_range": [0.6, 1.3],
        },
        PuppetStyleType.METAL_PUPPET: {
            "description": "金属木偶风格",
            "texture": "metal_rivets",
            "joints": ["bolt_joints"],
            "color_range": [0.3, 0.5],
            "intensity_range": [1.2, 2.0],
        },
        PuppetStyleType.FABRIC_PUPPET: {
            "description": "布艺木偶风格",
            "texture": "fabric_stitches",
            "joints": ["seam_joints"],
            "color_range": [0.4, 0.8],
            "intensity_range": [0.5, 1.2],
        },
        PuppetStyleType.GLASS_PUPPET: {
            "description": "玻璃木偶风格",
            "texture": "glass_refraction",
            "joints": ["crystal_joints"],
            "color_range": [0.7, 1.0],
            "intensity_range": [1.5, 2.0],
        },
    }
    
    def __init__(self):
        """初始化木偶风格引擎"""
        self._available_styles = list(PuppetStyleType)
        self._style_engine_initialized = True
    
    def is_available(self) -> bool:
        """检查引擎是否可用"""
        return self._style_engine_initialized
    
    def get_available_styles(self) -> List[Dict[str, Any]]:
        """获取可用风格列表"""
        styles = []
        for style_type in self._available_styles:
            preset = self.STYLE_PRESETS[style_type]
            styles.append({
                "type": style_type.value,
                "description": preset["description"],
                "texture": preset["texture"],
            })
        return styles
    
    def apply_style(self, config: PuppetStyleConfig, 
                    pose_data: Dict[str, Any]) -> PuppetStyleResult:
        """应用木偶风格
        
        Args:
            config: 风格配置
            pose_data: 人物姿态数据
            
        Returns:
            PuppetStyleResult: 处理结果
        """
        result = PuppetStyleResult()
        
        # 验证配置
        if not config.validate():
            result.warnings.append("配置参数超出有效范围")
            return result
        
        # 应用风格
        result.style_applied = config.style_type
        preset = self.STYLE_PRESETS[config.style_type]
        
        # 生成关键帧数据
        result.keyframes = self._generate_keyframes(config, pose_data, preset)
        
        # 生成 AE 效果配置
        result.effects = self._generate_ae_effects(config, preset)
        
        result.success = True
        return result
    
    def _generate_keyframes(self, config: PuppetStyleConfig, 
                           pose_data: Dict[str, Any],
                           preset: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成关键帧数据"""
        keyframes = []
        
        # 根据姿态数据生成针对性关键帧
        if "pose_landmarks" in pose_data:
            landmarks = pose_data["pose_landmarks"]
            
            # 为每个关节生成关键帧
            for joint_name in preset["joints"]:
                if joint_name in landmarks:
                    landmark_data = landmarks[joint_name]
                    keyframe = {
                        "joint": joint_name,
                        "position": landmark_data.get("position", [0, 0, 0]),
                        "rotation": landmark_data.get("rotation", [0, 0, 0]),
                        "scale": landmark_data.get("scale", [1, 1, 1]),
                        "intensity": config.intensity,
                    }
                    keyframes.append(keyframe)
        
        return keyframes
    
    def _generate_ae_effects(self, config: PuppetStyleConfig,
                            preset: Dict[str, Any]) -> Dict[str, Any]:
        """生成 AE 效果配置"""
        effects = {
            "style_type": config.style_type.value,
            "texture_map": preset["texture"],
            "color_tint": config.color_tint,
            "intensity": config.intensity,
            "effects_list": [],
        }
        
        # 添加关节效果
        if config.enable_joints:
            effects["effects_list"].append({
                "name": "JointHighlights",
                "type": "displacement_map",
                "intensity": config.intensity * 0.5,
            })
        
        # 添加纹理效果
        if config.enable_texture:
            effects["effects_list"].append({
                "name": "TextureOverlay",
                "type": "turbulent_displace",
                "intensity": config.intensity * 0.8,
            })
        
        # 添加灯光效果
        if config.enable_lighting:
            effects["effects_list"].append({
                "name": "LightingEffects",
                "type": "bevel_alpha",
                "intensity": config.intensity * 0.6,
            })
        
        return effects
