"""
puppet_effects 包
木偶风格化效果模块集合

包含：
- material_effects: 材质质感效果生成器
- stop_motion: 定格动画效果生成器
- joint_system: 关节化处理系统
- mini_scene: 微缩场景效果
- face_puppet: 面部木偶化效果
"""

from .face_puppet import FacePuppetConfig, FacePuppetEffect
from .joint_system import JointConfig, JointPoint, JointSystem
from .material_effects import MaterialEffects
from .mini_scene import MiniSceneConfig, MiniSceneEffect
from .stop_motion import StopMotionConfig, StopMotionEffect

__all__ = [
    "MaterialEffects",
    "StopMotionEffect",
    "StopMotionConfig",
    "JointPoint",
    "JointConfig",
    "JointSystem",
    "MiniSceneConfig",
    "MiniSceneEffect",
    "FacePuppetConfig",
    "FacePuppetEffect",
]
