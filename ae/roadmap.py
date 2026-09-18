#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Roadmap — 阶段状态机 / 能力注册表
====================================

管理项目 5 阶段 (A→E) 的开发进度、能力注册与阶段切换。

核心功能:
- PhaseRegistry: 注册每个阶段的能力模块
- PhaseStateMachine: 管理阶段流转 (A→B→C→D→E)
- CapabilityChecker: 运行时能力检测
- PhaseReport: 导出阶段进度报告

阶段定义:
  Phase A: 素材感知 (Perception)    — scene_detector, beat_detector, whisper_subtitle
  Phase B: 智能编排 (Orchestration) — creative_planner, timeline_composer, transition_selector, subtitle_product
  Phase C: IR 标准化 (IR)           — timeline_ir
  Phase D: 落轨执行 (Placement)     — e2e_pipeline (PR/AE 导出)
  Phase E: 审核优化 (Review)        — validation, review

用法:
    from ae.roadmap import Roadmap, Phase
    roadmap = Roadmap()
    print(roadmap.current_phase)   # Phase.B
    print(roadmap.report())        # 完整阶段报告
    roadmap.advance_to(Phase.C)    # 推进至下一阶段
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ================================================================
#  阶段枚举
# ================================================================

class Phase(str, Enum):
    """项目阶段"""
    A = "A"  # 素材感知
    B = "B"  # 智能编排
    C = "C"  # IR 标准化
    D = "D"  # 落轨执行
    E = "E"  # 审核优化


PHASE_NAMES: dict[Phase, str] = {
    Phase.A: "素材感知 (Perception)",
    Phase.B: "智能编排 (Orchestration)",
    Phase.C: "IR 标准化 (IR Standardization)",
    Phase.D: "落轨执行 (Track Placement)",
    Phase.E: "审核优化 (Review & Optimization)",
}


class CapabilityStatus(str, Enum):
    """能力状态"""
    PLANNED = "planned"        # 计划中
    IN_PROGRESS = "in_progress"  # 开发中
    STABLE = "stable"          # 稳定可用
    DEPRECATED = "deprecated"  # 已弃用


class PhaseTransition(str, Enum):
    """阶段转换事件"""
    ADVANCE = "advance"        # 前进
    ROLLBACK = "rollback"      # 回退
    FREEZE = "freeze"          # 冻结
    RESUME = "resume"          # 恢复


# ================================================================
#  Capability 定义
# ================================================================

@dataclass
class Capability:
    """能力单元"""
    name: str                          # 能力标识 (如 "scene_detection")
    display_name: str                  # 显示名称 (如 "场景检测")
    module: str                        # 模块路径 (如 "ae.scene_detector")
    phase: Phase                       # 所属阶段
    status: CapabilityStatus = CapabilityStatus.PLANNED
    dependencies: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)  # 导出的主要类/函数
    description: str = ""
    test_coverage: float = 0.0         # 测试覆盖率 (0.0-1.0)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "module": self.module,
            "phase": self.phase.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "exports": self.exports,
            "description": self.description,
            "test_coverage": self.test_coverage,
            "notes": self.notes,
        }


# ================================================================
#  能力注册表
# ================================================================

class PhaseRegistry:
    """
    阶段能力注册表。

    管理所有阶段的能力模块，支持按阶段查询、按模块查询、依赖图构建。
    """

    def __init__(self):
        self._capabilities: dict[str, Capability] = {}
        self._phase_caps: dict[Phase, list[str]] = {p: [] for p in Phase}
        self._register_builtins()

    # ----------------------------------------------------------
    #  注册
    # ----------------------------------------------------------

    def register(self, cap: Capability) -> None:
        """注册一个能力单元"""
        self._capabilities[cap.name] = cap
        if cap.name not in self._phase_caps[cap.phase]:
            self._phase_caps[cap.phase].append(cap.name)

    def _register_builtins(self) -> None:
        """注册内置能力"""
        builtins = [
            # Phase A: 素材感知
            Capability(
                name="scene_detection",
                display_name="场景检测",
                module="ae.scene_detector",
                phase=Phase.A,
                status=CapabilityStatus.STABLE,
                exports=["SceneDetector", "SceneCut", "SceneMetadata", "DetectionMethod"],
                description="PySceneDetect/TransNetV2 场景切割检测",
                test_coverage=0.6,
            ),
            Capability(
                name="ai_scene_detection",
                display_name="AI 镜头分割",
                module="ae.ai_scene_detector",
                phase=Phase.A,
                status=CapabilityStatus.STABLE,
                dependencies=["scene_detection"],
                exports=["AISceneDetector", "Shot", "ShotTransition", "ShotType"],
                description="基于 TransNetV2 的 AI 镜头分割",
                test_coverage=0.5,
            ),
            Capability(
                name="beat_detection",
                display_name="节拍检测",
                module="ae.beat_detector",
                phase=Phase.A,
                status=CapabilityStatus.STABLE,
                exports=["BeatDetector", "BeatInfo", "MusicStructure", "ClipSuggestion"],
                description="librosa + madmom 节拍/BPM 检测",
                test_coverage=0.5,
            ),
            Capability(
                name="whisper_subtitle",
                display_name="语音识别字幕",
                module="ae.whisper_subtitle",
                phase=Phase.A,
                status=CapabilityStatus.STABLE,
                exports=["WhisperSubtitleEngine", "TranscribeResult", "SubtitleSegment", "WordTiming"],
                description="faster-whisper 语音识别 + 字幕生成",
                test_coverage=0.4,
            ),

            # Phase B: 智能编排
            Capability(
                name="creative_planning",
                display_name="AI 创意规划",
                module="ae.ai_creative_planner",
                phase=Phase.B,
                status=CapabilityStatus.STABLE,
                dependencies=["preset_system", "creative_patterns"],
                exports=["AICreativePlanner"],
                description="LLM 驱动的创意描述解析与任务图生成",
                test_coverage=0.3,
            ),
            Capability(
                name="timeline_composition",
                display_name="时间线编排",
                module="ae.timeline_composer",
                phase=Phase.B,
                status=CapabilityStatus.STABLE,
                exports=["TimelineComposer", "Timeline", "Track", "ClipItem", "TimelineStyle"],
                description="多素材智能排序与时间线编排",
                test_coverage=0.4,
            ),
            Capability(
                name="transition_selection",
                display_name="转场智能选择",
                module="ae.transition_selector",
                phase=Phase.B,
                status=CapabilityStatus.IN_PROGRESS,
                dependencies=["pr_transition_system"],
                exports=["TransitionSelector", "TransitionRule"],
                description="基于风格/内容关系的智能转场选择 (Phase B 骨架)",
                test_coverage=0.0,
                notes="Phase B skeleton — 规则引擎可用，待 LLM 增强",
            ),
            Capability(
                name="subtitle_production",
                display_name="字幕产品化",
                module="ae.subtitle_product",
                phase=Phase.B,
                status=CapabilityStatus.IN_PROGRESS,
                dependencies=["subtitle_system", "whisper_subtitle"],
                exports=["SubtitlePipeline", "SubtitleStyler", "SubtitleResult"],
                description="产品级字幕管线: 解析→优化→样式→IR (Phase B 骨架)",
                test_coverage=0.0,
                notes="Phase B skeleton — 核心管线可用，待双语/动画增强",
            ),

            # Phase C: IR 标准化
            Capability(
                name="timeline_ir",
                display_name="Timeline IR",
                module="ae.timeline_ir",
                phase=Phase.C,
                status=CapabilityStatus.IN_PROGRESS,
                exports=[
                    "IRSequence", "IRTrack", "IRClip", "IREffect", "IRTransition",
                    "validate_ir", "export_to_pr_json", "export_to_ae_jsx",
                ],
                description="统一时间线中间表示: Schema + 校验 + PR/AE 导出",
                test_coverage=0.0,
                notes="Phase C 核心 — Schema 已定义，导出器已实现",
            ),
            Capability(
                name="preset_system",
                display_name="预设系统",
                module="ae.preset_system",
                phase=Phase.C,
                status=CapabilityStatus.STABLE,
                exports=["Preset", "PresetSystem"],
                description="AE 预设定义与 JSX 代码生成",
                test_coverage=0.5,
            ),

            # Phase D: 落轨执行
            Capability(
                name="e2e_pipeline",
                display_name="端到端管道",
                module="ae.e2e_pipeline",
                phase=Phase.D,
                status=CapabilityStatus.IN_PROGRESS,
                dependencies=["scene_detection", "beat_detection", "timeline_composition",
                              "timeline_ir", "transition_selection", "subtitle_production"],
                exports=["E2EPipeline", "PipelineResult", "PipelineContext"],
                description="感知→编排→IR→落轨 全流程管道",
                test_coverage=0.0,
                notes="Phase D 核心 — 管道骨架已就绪",
            ),
            Capability(
                name="pr_mcp_integration",
                display_name="PR MCP 集成",
                module="ae.pr_mcp_client",
                phase=Phase.D,
                status=CapabilityStatus.STABLE,
                exports=["PRMCPClient", "PRConnectionError"],
                description="Premiere Pro MCP 桥接客户端",
                test_coverage=0.4,
            ),
            Capability(
                name="ae_mcp_integration",
                display_name="AE MCP 集成",
                module="ae.ae_mcp_client",
                phase=Phase.D,
                status=CapabilityStatus.STABLE,
                exports=["AEMCPClient"],
                description="After Effects MCP 桥接客户端",
                test_coverage=0.3,
            ),

            # Phase E: 审核优化
            Capability(
                name="ir_validation",
                display_name="IR 校验器",
                module="ae.timeline_ir",
                phase=Phase.E,
                status=CapabilityStatus.IN_PROGRESS,
                dependencies=["timeline_ir"],
                exports=["validate_ir", "IRValidationResult", "IRValidationError"],
                description="IR Schema 严格校验",
                test_coverage=0.0,
            ),
            Capability(
                name="distributed_render",
                display_name="分布式渲染",
                module="ae.distributed_renderer",
                phase=Phase.E,
                status=CapabilityStatus.PLANNED,
                exports=["DistributedRenderer", "RenderTask", "RenderBatch"],
                description="多机分布式渲染农场",
                test_coverage=0.1,
            ),
        ]
        for cap in builtins:
            self.register(cap)

    # ----------------------------------------------------------
    #  查询
    # ----------------------------------------------------------

    def get(self, name: str) -> Capability | None:
        """按名称获取能力"""
        return self._capabilities.get(name)

    def list_by_phase(self, phase: Phase) -> list[Capability]:
        """列出某阶段所有能力"""
        return [
            self._capabilities[name]
            for name in self._phase_caps.get(phase, [])
            if name in self._capabilities
        ]

    def list_by_status(self, status: CapabilityStatus) -> list[Capability]:
        """列出某状态所有能力"""
        return [c for c in self._capabilities.values() if c.status == status]

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """获取依赖图 {cap_name: [dep_name, ...]}"""
        return {
            name: cap.dependencies
            for name, cap in self._capabilities.items()
        }

    def get_phase_summary(self, phase: Phase) -> dict[str, Any]:
        """获取阶段摘要"""
        caps = self.list_by_phase(phase)
        statuses = {}
        for c in caps:
            statuses[c.status.value] = statuses.get(c.status.value, 0) + 1
        return {
            "phase": phase.value,
            "name": PHASE_NAMES.get(phase, ""),
            "total_capabilities": len(caps),
            "status_breakdown": statuses,
            "stable_count": sum(1 for c in caps if c.status == CapabilityStatus.STABLE),
            "in_progress_count": sum(1 for c in caps if c.status == CapabilityStatus.IN_PROGRESS),
            "planned_count": sum(1 for c in caps if c.status == CapabilityStatus.PLANNED),
        }

    def get_all_summaries(self) -> list[dict[str, Any]]:
        """获取全阶段摘要"""
        return [self.get_phase_summary(p) for p in Phase]

    def to_dict(self) -> dict[str, Any]:
        """导出为字典"""
        return {
            "phases": {
                p.value: {
                    "name": PHASE_NAMES[p],
                    "capabilities": {
                        name: cap.to_dict()
                        for name, cap in zip(
                            self._phase_caps.get(p, []),
                            [self._capabilities[n] for n in self._phase_caps.get(p, []) if n in self._capabilities]
                        )
                    }
                }
                for p in Phase
            }
        }


# ================================================================
#  阶段状态机
# ================================================================

class PhaseStateMachine:
    """
    阶段状态机 — 管理 A→B→C→D→E 流转。

    规则:
    - 阶段只能向前推进 (advance) 或向后回退 (rollback)
    - 冻结 (freeze) 可暂停推进，恢复 (resume) 可继续
    - 每个阶段可设置前置条件 (gate)，条件不满足时禁止推进
    """

    _PHASE_ORDER: tuple[Phase, ...] = (Phase.A, Phase.B, Phase.C, Phase.D, Phase.E)
    _PHASE_INDEX: dict[Phase, int] = {p: i for i, p in enumerate(_PHASE_ORDER)}

    def __init__(self, initial_phase: Phase = Phase.B, registry: PhaseRegistry | None = None):
        self._current = initial_phase
        self._frozen = False
        self._transition_history: list[tuple[float, Phase, Phase, PhaseTransition]] = []
        self._gates: dict[Phase, list[str]] = {}  # phase -> 前置条件描述
        self.registry = registry or PhaseRegistry()

    @property
    def current_phase(self) -> Phase:
        return self._current

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def progress(self) -> float:
        """当前进度 (0.0 ~ 1.0)"""
        return self._PHASE_INDEX[self._current] / (len(self._PHASE_ORDER) - 1)

    @property
    def phase_name(self) -> str:
        return PHASE_NAMES.get(self._current, "Unknown")

    def set_gate(self, phase: Phase, conditions: list[str]) -> None:
        """设置阶段门控条件"""
        self._gates[phase] = conditions

    def check_gate(self, phase: Phase) -> tuple[bool, list[str]]:
        """检查是否能进入某阶段"""
        conditions = self._gates.get(phase, [])
        return len(conditions) == 0, conditions

    def advance_to(self, target: Phase) -> bool:
        """
        推进到目标阶段。

        Args:
            target: 目标阶段

        Returns:
            是否成功

        Raises:
            ValueError: 无法推进
        """
        if self._frozen:
            raise ValueError(f"阶段已冻结，无法推进到 {target.value}")

        target_idx = self._PHASE_INDEX[target]
        current_idx = self._PHASE_INDEX[self._current]

        if target_idx < current_idx:
            raise ValueError(
                f"不能向前推进到更早的阶段: "
                f"当前 {self._current.value} → 目标 {target.value}"
            )

        if target_idx == current_idx:
            return True  # 已在目标阶段

        # 检查门控
        for idx in range(current_idx + 1, target_idx + 1):
            phase = self._PHASE_ORDER[idx]
            ok, conditions = self.check_gate(phase)
            if not ok and idx == target_idx:
                raise ValueError(
                    f"无法推进到 {phase.value}，前置条件不满足:\n  " +
                    "\n  ".join(f"- {c}" for c in conditions)
                )

        old = self._current
        self._current = target
        self._transition_history.append((time.time(), old, target, PhaseTransition.ADVANCE))
        return True

    def advance_next(self) -> Phase | None:
        """推进到下一阶段"""
        current_idx = self._PHASE_INDEX[self._current]
        if current_idx >= len(self._PHASE_ORDER) - 1:
            return None  # 已经是最后阶段
        next_phase = self._PHASE_ORDER[current_idx + 1]
        self.advance_to(next_phase)
        return next_phase

    def rollback_to(self, target: Phase) -> bool:
        """回退到目标阶段"""
        target_idx = self._PHASE_INDEX[target]
        current_idx = self._PHASE_INDEX[self._current]

        if target_idx >= current_idx:
            raise ValueError(
                f"回退目标不能是当前或更后的阶段: "
                f"当前 {self._current.value} → 目标 {target.value}"
            )

        old = self._current
        self._current = target
        self._transition_history.append((time.time(), old, target, PhaseTransition.ROLLBACK))
        return True

    def freeze(self) -> None:
        """冻结阶段推进"""
        self._frozen = True

    def resume(self) -> None:
        """恢复阶段推进"""
        self._frozen = False

    def report(self) -> dict[str, Any]:
        """阶段状态报告"""
        summary = self.registry.get_phase_summary(self._current) if self.registry else {}
        return {
            "current_phase": self._current.value,
            "phase_name": self.phase_name,
            "progress": round(self.progress * 100, 1),
            "frozen": self._frozen,
            "transitions": len(self._transition_history),
            "capabilities": summary,
            "phase_order": [p.value for p in self._PHASE_ORDER],
            "last_transition": (
                {
                    "from": self._transition_history[-1][1].value,
                    "to": self._transition_history[-1][2].value,
                    "type": self._transition_history[-1][3].value,
                }
                if self._transition_history
                else None
            ),
        }


# ================================================================
#  Roadmap 主入口
# ================================================================

class Roadmap:
    """
    开发路线图管理器。

    集成 PhaseRegistry + PhaseStateMachine，提供统一的阶段查看与推进接口。
    """

    def __init__(self, initial_phase: Phase = Phase.B):
        self.registry = PhaseRegistry()
        self.state_machine = PhaseStateMachine(
            initial_phase=initial_phase,
            registry=self.registry,
        )

    @property
    def current_phase(self) -> Phase:
        return self.state_machine.current_phase

    @property
    def progress(self) -> float:
        return self.state_machine.progress

    def advance_to(self, phase: Phase) -> bool:
        return self.state_machine.advance_to(phase)

    def advance_next(self) -> Phase | None:
        return self.state_machine.advance_next()

    def rollback_to(self, phase: Phase) -> bool:
        return self.state_machine.rollback_to(phase)

    def freeze(self) -> None:
        self.state_machine.freeze()

    def resume(self) -> None:
        self.state_machine.resume()

    def report(self) -> dict[str, Any]:
        """完整路线图报告"""
        rpt = self.state_machine.report()
        rpt["all_phases"] = self.registry.get_all_summaries()
        rpt["total_capabilities"] = len(self.registry._capabilities)
        return rpt

    def report_text(self) -> str:
        """人类可读的路线图报告"""
        rpt = self.report()
        lines = [
            "=" * 60,
            "  AE Knowledge Vault — 开发路线图",
            "=" * 60,
            "",
            f"当前阶段: Phase {rpt['current_phase']} — {rpt['phase_name']}",
            f"整体进度: {rpt['progress']:.0f}%",
            "",
            "--- 阶段总览 ---",
        ]
        for phase_summary in rpt["all_phases"]:
            p = phase_summary
            marker = " ← 当前" if p["phase"] == rpt["current_phase"] else ""
            lines.append(
                f"  Phase {p['phase']}: {p['name']}{marker}\n"
                f"    能力: {p['total_capabilities']} 个 "
                f"(stable={p['stable_count']}, "
                f"in_progress={p['in_progress_count']}, "
                f"planned={p['planned_count']})"
            )

        return "\n".join(lines)

    def export_json(self, path: str | None = None) -> str:
        """导出路线图为 JSON"""
        data = self.report()
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def get_capabilities(self, phase: Phase | None = None) -> list[Capability]:
        """获取能力列表"""
        if phase:
            return self.registry.list_by_phase(phase)
        return list(self.registry._capabilities.values())


# ================================================================
#  便捷函数
# ================================================================

def get_roadmap() -> Roadmap:
    """获取默认路线图实例 (当前阶段 B)"""
    return Roadmap(initial_phase=Phase.B)


def print_roadmap() -> None:
    """打印路线图到 stdout"""
    r = get_roadmap()
    print(r.report_text())
