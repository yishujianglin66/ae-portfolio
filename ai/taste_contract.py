"""ai/taste_contract.py - 品味契约模块

基于 OpenMontage taste-direction.md 的三旋钮品味契约, 接入 v23 导演系统。
零外部依赖, 纯 Python 数据类 + 规则函数。

三旋钮:
  visual_variance   1-10  视觉变化度 (低=重复语法, 高=每拍不同视觉模式)
  motion_intensity  1-10  运动强度   (低=静缓, 高=快切多方向变化)
  information_density 1-10 信息密度   (低=一帧一意, 高=密集仪表板)

Anti-Default Checklist (机检化前 3 条):
  #1 无主体理由时不用通用 AI 紫/企业蓝
  #2 visual_variance >= 4 时不允许所有切点用同一转场
  #3 低 information_density + 高 motion_intensity 时警告运动干扰叙事
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# ============================================================
# 运镜池
# ============================================================

LOW_MOTION_POOL: list[str] = [
    "static",        # 固定镜头
    "zoom_out",      # 缓拉
    "zoom_in",       # 缓推
]

MID_MOTION_POOL: list[str] = [
    "pan_left",      # 横摇
    "pan_right",     # 反横摇
    "zoom_in",       # 推近
    "zoom_out",      # 拉远
    "diag_pan",      # 对角摇
]

HIGH_MOTION_POOL: list[str] = [
    "pan_left",
    "pan_right",
    "zoom_in",
    "zoom_out",
    "zoom_back",     # 先推后拉
    "diag_pan",      # 对角线
    "orbit",         # 环绕
    "push",          # 快推
]


def camera_pool_for_intensity(motion_intensity: int) -> list[str]:
    """根据 motion_intensity 返回候选运镜池。

    Args:
        motion_intensity: 1-10 运动强度旋钮

    Returns:
        运镜名称列表(可重复, 供导演循环选取)
    """
    mi = max(1, min(10, motion_intensity))
    if mi <= 3:
        return LOW_MOTION_POOL[:]
    elif mi <= 6:
        return MID_MOTION_POOL[:]
    else:
        return HIGH_MOTION_POOL[:]


# ============================================================
# TasteProfile 数据类
# ============================================================

@dataclass
class TasteProfile:
    """品味契约三旋钮 + 创意阅读。"""
    visual_variance: int = 5
    motion_intensity: int = 5
    information_density: int = 5
    design_read: str = ""
    anti_patterns: list[str] = field(default_factory=list)
    quality_gates: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.visual_variance = max(1, min(10, int(self.visual_variance)))
        self.motion_intensity = max(1, min(10, int(self.motion_intensity)))
        self.information_density = max(1, min(10, int(self.information_density)))

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TasteProfile:
        return cls(
            visual_variance=d.get("visual_variance", 5),
            motion_intensity=d.get("motion_intensity", 5),
            information_density=d.get("information_density", 5),
            design_read=d.get("design_read", ""),
            anti_patterns=d.get("anti_patterns", []),
            quality_gates=d.get("quality_gates", []),
        )

    def camera_pool(self) -> list[str]:
        """快捷: 返回当前 motion_intensity 对应的运镜池。"""
        return camera_pool_for_intensity(self.motion_intensity)


# 默认品味(中性)
DEFAULT_TASTE = TasteProfile()


# ============================================================
# Anti-Default Checklist 机检
# ============================================================

def check_anti_defaults(
    segments: Sequence[dict[str, Any]],
    taste: TasteProfile,
) -> list[dict[str, str]]:
    """机检 Anti-Default Checklist 前 3 条。

    Args:
        segments: 导演输出的 segment 列表(每段含 transition/zoompan_effect)
        taste: 当前品味契约

    Returns:
        违规列表, 每项 {"rule": 规则标识, "detail": 说明}
    """
    if not segments:
        return []

    violations: list[dict[str, str]] = []

    # --- Rule #2: visual_variance >= 4 时不允许"可变化转场"的切点全部同质 ---
    # 统计范围限定为"转场可变化的镜头":
    #   - 排除 drop/climax 段 (漫剪铁律: 爆发段硬切卡点, 设计内)
    #   - 排除变速镜头 speed != 1.0 (渲染层强制硬切防切点漂移, 工程约束)
    # 修复 (2026-08-14): 此前对全部镜头统计, 把"设计内硬切"误报为违规。
    if taste.visual_variance >= 4 and len(segments) >= 3:
        _eligible = [
            s for s in segments
            if s.get("mood") not in ("drop", "climax")
            and float(s.get("speed", 1.0) or 1.0) == 1.0
        ]
        if len(_eligible) >= 3:
            transitions = [s.get("transition") for s in _eligible if s.get("transition")]
            if transitions:
                counter = Counter(transitions)
                most_common_t, most_common_count = counter.most_common(1)[0]
                ratio = most_common_count / len(transitions)
                if ratio > 0.8:
                    violations.append({
                        "rule": "anti_default_transition",
                        "detail": (
                            f"visual_variance={taste.visual_variance}(>=4) 但可变化转场"
                            f"镜头({len(_eligible)}个)中 {ratio:.0%} 使用同一转场 "
                            f"'{most_common_t}' (爆发段硬切/变速镜头硬切不计入)"
                        ),
                    })

    # --- Rule #3: 低 information_density + 高 motion_intensity → 运动干扰叙事 ---
    if taste.information_density <= 3 and taste.motion_intensity >= 7:
        violations.append({
            "rule": "anti_default_motion_narration_conflict",
            "detail": (
                f"information_density={taste.information_density}(<=3) + "
                f"motion_intensity={taste.motion_intensity}(>=7): "
                "高运动强度可能干扰低信息密度的叙事可读性"
            ),
        })

    return violations
