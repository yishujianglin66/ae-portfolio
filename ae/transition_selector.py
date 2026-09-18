#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transition Selector — 方向2：转场智能选择器 (阶段 B 骨架)
===========================================================

基于素材内容、风格标签、节奏感智能选择最佳转场效果。

核心能力:
- 根据剪辑风格推荐适配转场类型
- 根据素材间内容衔接关系选择转场
- 转场规则引擎 (可配置的规则表)
- 支持 PR 转场库 (pr_transition_system) 和 AE 预设转场

架构定位:
    位于 e2e_pipeline Phase B 的 transition_selection 步骤。
    被 e2e_pipeline.E2EPipeline._select_transitions() 调用。
    最终产出 transition_map: {clip_id: transition_type}。

依赖:
    ae.timeline_ir          — IRTransitionType 枚举
    ae.pr_transition_system — TransitionType / TransitionSystem (可选)

用法:
    from ae.transition_selector import TransitionSelector
    selector = TransitionSelector()
    transition_map = selector.select_for_sequence(
        clips=["clip1.mp4", "clip2.mp4", "clip3.mp4"],
        style="dynamic_cut",
    )
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .timeline_ir import IRTransitionType

# ================================================================
#  枚举定义
# ================================================================

class StyleCategory(str, Enum):
    """剪辑风格大类"""
    DYNAMIC = "dynamic"        # 快节奏 / 卡点
    SMOOTH = "smooth"          # 平滑 / 抒情
    CINEMATIC = "cinematic"    # 电影感
    GLITCH = "glitch"          # 故障风 / 赛博朋克
    VLOG = "vlog"              # Vlog
    RETRO = "retro"            # 复古
    MINIMAL = "minimal"        # 极简


class ContentRelation(str, Enum):
    """相邻素材关系"""
    CONTINUOUS = "continuous"      # 连续场景 (同场景)
    TIME_JUMP = "time_jump"        # 时间跳跃
    SPACE_JUMP = "space_jump"      # 空间跳跃
    CONTRAST = "contrast"          # 对比 / 情绪转变
    MATCH_CUT = "match_cut"        # 匹配剪辑
    PARALLEL = "parallel"          # 平行蒙太奇


# ================================================================
#  转场规则
# ================================================================

@dataclass
class TransitionRule:
    """转场推荐规则"""
    style: StyleCategory
    relation: ContentRelation
    primary: IRTransitionType
    alternatives: list[IRTransitionType] = field(default_factory=list)
    min_duration: float = 0.15
    max_duration: float = 1.0
    default_duration: float = 0.5
    weight: float = 1.0  # 规则权重


# ================================================================
#  转场选择器
# ================================================================

class TransitionSelector:
    """
    转场智能选择器 (Phase B 骨架)。

    当前阶段 (B) 实现：
    - 基于风格 → 转场映射的规则引擎
    - 可配置的转场规则表
    - 支持 PR 转场系统对接 (ae.pr_transition_system)

    后续阶段扩展：
    - 基于素材内容分析的关系推断
    - 基于节拍密度的转场时长自适应
    - LLM 辅助的转场选择
    """

    # 风格 → 默认转场映射
    STYLE_TRANSITION_MAP: dict[str, list[IRTransitionType]] = {
        "dynamic_cut": [
            IRTransitionType.CUT,
            IRTransitionType.WHIP_PAN_RIGHT,
            IRTransitionType.WHIP_PAN_LEFT,
            IRTransitionType.ZOOM_IN,
            IRTransitionType.PUSH_LEFT,
        ],
        "fast_beat": [
            IRTransitionType.CUT,
            IRTransitionType.FLASH,
            IRTransitionType.GLITCH,
            IRTransitionType.ZOOM_IN,
        ],
        "smooth_flow": [
            IRTransitionType.CROSS_DISSOLVE,
            IRTransitionType.DISSOLVE,
            IRTransitionType.SLIDE,
        ],
        "slow_cinematic": [
            IRTransitionType.CROSS_DISSOLVE,
            IRTransitionType.DIP_TO_BLACK,
            IRTransitionType.DISSOLVE,
        ],
        "glitch_style": [
            IRTransitionType.GLITCH,
            IRTransitionType.FLASH,
            IRTransitionType.ZOOM_IN,
            IRTransitionType.WHIP_PAN_LEFT,
        ],
        "vlog": [
            IRTransitionType.WHIP_PAN_RIGHT,
            IRTransitionType.ZOOM_IN,
            IRTransitionType.SLIDE,
            IRTransitionType.CROSS_DISSOLVE,
        ],
    }

    # 风格名映射到 StyleCategory
    STYLE_ALIASES: dict[str, StyleCategory] = {
        "dynamic_cut": StyleCategory.DYNAMIC,
        "fast_beat": StyleCategory.DYNAMIC,
        "smooth_flow": StyleCategory.SMOOTH,
        "slow_cinematic": StyleCategory.CINEMATIC,
        "glitch_style": StyleCategory.GLITCH,
        "vlog": StyleCategory.VLOG,
        "retro": StyleCategory.RETRO,
        "minimal": StyleCategory.MINIMAL,
    }

    def __init__(self, seed: int | None = None, rules: list[TransitionRule] | None = None):
        """
        Args:
            seed: 随机种子 (用于可复现的转场选择)
            rules: 自定义转场规则表
        """
        self.rng = random.Random(seed)
        self.rules = rules or self._build_default_rules()

    # ----------------------------------------------------------
    #  核心选择
    # ----------------------------------------------------------

    def select_for_sequence(
        self,
        clips: list[str],
        style: str = "dynamic_cut",
        relations: list[ContentRelation] | None = None,
        bpm: float = 120.0,
    ) -> dict[str, str]:
        """
        为素材序列选择转场。

        Args:
            clips: 素材路径列表
            style: 剪辑风格
            relations: 素材间关系列表 (len = len(clips) - 1)
            bpm: BPM (影响转场时长)

        Returns:
            {clip_path: transition_type_string} 转场映射
        """
        if len(clips) <= 1:
            return {clips[0]: "cut"} if clips else {}

        transition_map: dict[str, str] = {}
        first_clip = clips[0]
        transition_map[first_clip] = "cut"  # 第一个片段无需入转场

        for i in range(1, len(clips)):
            relation = (
                relations[i - 1]
                if relations and i - 1 < len(relations)
                else ContentRelation.CONTINUOUS
            )

            trans = self._select_transition(style, relation)
            transition_map[clips[i]] = trans.value if isinstance(trans, IRTransitionType) else trans

        return transition_map

    def select_single(
        self,
        style: str = "dynamic_cut",
        relation: ContentRelation = ContentRelation.CONTINUOUS,
        duration: float | None = None,
    ) -> IRTransitionType:
        """
        选择单个转场。

        Args:
            style: 剪辑风格
            relation: 素材关系
            duration: 期望转场时长 (秒)

        Returns:
            选定的转场类型
        """
        return self._select_transition(style, relation)

    def select_with_duration(
        self,
        style: str = "dynamic_cut",
        relation: ContentRelation = ContentRelation.CONTINUOUS,
    ) -> tuple[IRTransitionType, float]:
        """
        选择转场并推荐时长。

        Returns:
            (转场类型, 推荐时长秒)
        """
        trans = self._select_transition(style, relation)
        # 根据类型推荐时长
        duration_map = {
            IRTransitionType.CUT: 0.0,
            IRTransitionType.FLASH: 0.15,
            IRTransitionType.GLITCH: 0.2,
            IRTransitionType.WHIP_PAN_LEFT: 0.3,
            IRTransitionType.WHIP_PAN_RIGHT: 0.3,
            IRTransitionType.ZOOM_IN: 0.4,
            IRTransitionType.ZOOM_OUT: 0.4,
            IRTransitionType.PUSH_LEFT: 0.35,
            IRTransitionType.PUSH_RIGHT: 0.35,
            IRTransitionType.SLIDE: 0.4,
            IRTransitionType.CROSS_DISSOLVE: 0.5,
            IRTransitionType.DISSOLVE: 0.5,
            IRTransitionType.DIP_TO_BLACK: 0.6,
            IRTransitionType.DIP_TO_WHITE: 0.4,
        }
        return trans, duration_map.get(trans, 0.3)

    # ----------------------------------------------------------
    #  内部选择逻辑
    # ----------------------------------------------------------

    def _select_transition(
        self, style: str, relation: ContentRelation
    ) -> IRTransitionType:
        """核心选择逻辑：规则匹配 → 风格回退"""
        style_cat = self._resolve_style(style)

        # 1. 尝试规则匹配
        matching_rules = [
            r for r in self.rules
            if r.style == style_cat and r.relation == relation
        ]
        if matching_rules:
            rule = self.rng.choices(
                matching_rules,
                weights=[r.weight for r in matching_rules],
                k=1,
            )[0]
            choices = [rule.primary] + rule.alternatives
            # 加权随机 (primary 有更高权重)
            weights = [3.0] + [1.0] * len(rule.alternatives)
            return self.rng.choices(choices, weights=weights, k=1)[0]

        # 2. 风格回退 (取风格默认列表随机)
        candidates = self.STYLE_TRANSITION_MAP.get(
            style,
            self.STYLE_TRANSITION_MAP.get("dynamic_cut", [IRTransitionType.CUT]),
        )
        return self.rng.choice(candidates)

    def _resolve_style(self, style: str) -> StyleCategory:
        """解析风格字符串"""
        style_lower = style.lower().replace("-", "_").replace(" ", "_")
        return self.STYLE_ALIASES.get(
            style_lower,
            StyleCategory.DYNAMIC,
        )

    # ----------------------------------------------------------
    #  规则构建
    # ----------------------------------------------------------

    @staticmethod
    def _build_default_rules() -> list[TransitionRule]:
        """构建默认转场规则表"""
        D = StyleCategory.DYNAMIC
        S = StyleCategory.SMOOTH
        C = StyleCategory.CINEMATIC
        G = StyleCategory.GLITCH
        V = StyleCategory.VLOG
        R = StyleCategory.RETRO
        M = StyleCategory.MINIMAL

        return [
            # === 快节奏 ===
            TransitionRule(D, ContentRelation.CONTINUOUS,
                           IRTransitionType.CUT, [IRTransitionType.WHIP_PAN_RIGHT]),
            TransitionRule(D, ContentRelation.TIME_JUMP,
                           IRTransitionType.WHIP_PAN_RIGHT, [IRTransitionType.ZOOM_IN]),
            TransitionRule(D, ContentRelation.SPACE_JUMP,
                           IRTransitionType.ZOOM_IN, [IRTransitionType.WHIP_PAN_LEFT]),
            TransitionRule(D, ContentRelation.CONTRAST,
                           IRTransitionType.FLASH, [IRTransitionType.GLITCH]),
            TransitionRule(D, ContentRelation.MATCH_CUT,
                           IRTransitionType.WHIP_PAN_LEFT, [IRTransitionType.ZOOM_IN]),
            TransitionRule(D, ContentRelation.PARALLEL,
                           IRTransitionType.PUSH_RIGHT, [IRTransitionType.SLIDE]),

            # === 平滑 ===
            TransitionRule(S, ContentRelation.CONTINUOUS,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.DISSOLVE]),
            TransitionRule(S, ContentRelation.TIME_JUMP,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.DIP_TO_BLACK]),
            TransitionRule(S, ContentRelation.SPACE_JUMP,
                           IRTransitionType.SLIDE, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(S, ContentRelation.CONTRAST,
                           IRTransitionType.DIP_TO_BLACK, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(S, ContentRelation.MATCH_CUT,
                           IRTransitionType.DISSOLVE, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(S, ContentRelation.PARALLEL,
                           IRTransitionType.SLIDE, [IRTransitionType.CROSS_DISSOLVE]),

            # === 电影感 ===
            TransitionRule(C, ContentRelation.CONTINUOUS,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.DISSOLVE]),
            TransitionRule(C, ContentRelation.TIME_JUMP,
                           IRTransitionType.DIP_TO_BLACK, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(C, ContentRelation.SPACE_JUMP,
                           IRTransitionType.DIP_TO_BLACK, [IRTransitionType.SLIDE]),
            TransitionRule(C, ContentRelation.CONTRAST,
                           IRTransitionType.DIP_TO_BLACK, [IRTransitionType.DIP_TO_WHITE]),
            TransitionRule(C, ContentRelation.MATCH_CUT,
                           IRTransitionType.CUT, [IRTransitionType.DISSOLVE]),
            TransitionRule(C, ContentRelation.PARALLEL,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.SLIDE]),

            # === 故障风 ===
            TransitionRule(G, ContentRelation.CONTINUOUS,
                           IRTransitionType.GLITCH, [IRTransitionType.FLASH]),
            TransitionRule(G, ContentRelation.TIME_JUMP,
                           IRTransitionType.GLITCH, [IRTransitionType.ZOOM_IN]),
            TransitionRule(G, ContentRelation.SPACE_JUMP,
                           IRTransitionType.GLITCH, [IRTransitionType.FLASH]),
            TransitionRule(G, ContentRelation.CONTRAST,
                           IRTransitionType.GLITCH, [IRTransitionType.FLASH]),
            TransitionRule(G, ContentRelation.MATCH_CUT,
                           IRTransitionType.FLASH, [IRTransitionType.GLITCH]),
            TransitionRule(G, ContentRelation.PARALLEL,
                           IRTransitionType.GLITCH, [IRTransitionType.ZOOM_IN]),

            # === Vlog ===
            TransitionRule(V, ContentRelation.CONTINUOUS,
                           IRTransitionType.WHIP_PAN_RIGHT, [IRTransitionType.ZOOM_IN]),
            TransitionRule(V, ContentRelation.TIME_JUMP,
                           IRTransitionType.ZOOM_IN, [IRTransitionType.WHIP_PAN_RIGHT]),
            TransitionRule(V, ContentRelation.SPACE_JUMP,
                           IRTransitionType.WHIP_PAN_LEFT, [IRTransitionType.ZOOM_IN]),
            TransitionRule(V, ContentRelation.CONTRAST,
                           IRTransitionType.SLIDE, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(V, ContentRelation.MATCH_CUT,
                           IRTransitionType.ZOOM_IN, [IRTransitionType.WHIP_PAN_RIGHT]),
            TransitionRule(V, ContentRelation.PARALLEL,
                           IRTransitionType.SLIDE, [IRTransitionType.PUSH_RIGHT]),

            # === 复古 ===
            TransitionRule(R, ContentRelation.CONTINUOUS,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.DIP_TO_BLACK]),
            TransitionRule(R, ContentRelation.TIME_JUMP,
                           IRTransitionType.DIP_TO_BLACK, [IRTransitionType.WIPE_LEFT]),
            TransitionRule(R, ContentRelation.SPACE_JUMP,
                           IRTransitionType.WIPE_RIGHT, [IRTransitionType.DIP_TO_BLACK]),
            TransitionRule(R, ContentRelation.CONTRAST,
                           IRTransitionType.DIP_TO_WHITE, [IRTransitionType.FLASH]),
            TransitionRule(R, ContentRelation.MATCH_CUT,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.WIPE_IRIS]),
            TransitionRule(R, ContentRelation.PARALLEL,
                           IRTransitionType.SLIDE, [IRTransitionType.CROSS_DISSOLVE]),

            # === 极简 ===
            TransitionRule(M, ContentRelation.CONTINUOUS,
                           IRTransitionType.CUT, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(M, ContentRelation.TIME_JUMP,
                           IRTransitionType.CROSS_DISSOLVE, [IRTransitionType.DISSOLVE]),
            TransitionRule(M, ContentRelation.SPACE_JUMP,
                           IRTransitionType.CUT, [IRTransitionType.CROSS_DISSOLVE]),
            TransitionRule(M, ContentRelation.CONTRAST,
                           IRTransitionType.CUT, [IRTransitionType.DIP_TO_BLACK]),
            TransitionRule(M, ContentRelation.MATCH_CUT,
                           IRTransitionType.CUT, [IRTransitionType.DISSOLVE]),
            TransitionRule(M, ContentRelation.PARALLEL,
                           IRTransitionType.CUT, [IRTransitionType.SLIDE]),
        ]

    # ----------------------------------------------------------
    #  工具方法
    # ----------------------------------------------------------

    def list_available_transitions(self, style: str | None = None) -> list[str]:
        """列出可用转场"""
        if style:
            candidates = self.STYLE_TRANSITION_MAP.get(style, [])
            return [t.value for t in candidates]
        all_types = set()
        for transitions in self.STYLE_TRANSITION_MAP.values():
            all_types.update(t.value for t in transitions)
        return sorted(all_types)

    def add_rule(self, rule: TransitionRule) -> None:
        """动态添加转场规则"""
        self.rules.append(rule)

    def get_rules_for_style(self, style: str) -> list[TransitionRule]:
        """获取某风格的所有规则"""
        style_cat = self._resolve_style(style)
        return [r for r in self.rules if r.style == style_cat]

    def to_pr_transition(self, ir_type: IRTransitionType) -> str | None:
        """
        将 IRTransitionType 映射到 PR TransitionType。

        Args:
            ir_type: IR 转场类型

        Returns:
            PR 转场类型字符串 (ae.pr_transition_system.TransitionType)
        """
        MAPPING = {
            IRTransitionType.CROSS_DISSOLVE: "cross_dissolve",
            IRTransitionType.DISSOLVE: "dissolve",
            IRTransitionType.DIP_TO_BLACK: "dip_to_black",
            IRTransitionType.DIP_TO_WHITE: "dip_to_white",
            IRTransitionType.WIPE_LEFT: "wipe_left",
            IRTransitionType.WIPE_RIGHT: "wipe_right",
            IRTransitionType.WIPE_UP: "wipe_up",
            IRTransitionType.WIPE_DOWN: "wipe_down",
            IRTransitionType.WIPE_IRIS: "wipe_iris",
            IRTransitionType.ZOOM_IN: "zoom_in",
            IRTransitionType.ZOOM_OUT: "zoom_out",
            IRTransitionType.WHIP_PAN_LEFT: "whip_pan_left",
            IRTransitionType.WHIP_PAN_RIGHT: "whip_pan_right",
            IRTransitionType.GLITCH: "glitch",
            IRTransitionType.FLASH: "flash",
            IRTransitionType.PUSH_LEFT: "push_left",
            IRTransitionType.PUSH_RIGHT: "push_right",
            IRTransitionType.SLIDE: "slide",
        }
        return MAPPING.get(ir_type)
