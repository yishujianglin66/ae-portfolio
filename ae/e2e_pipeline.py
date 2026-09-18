#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
E2E Pipeline — 方向1：端到端自动化剪辑管道
==============================================

流程: 感知 (Perception) → 编排 (Orchestration) → IR (Intermediate Representation) → 落轨 (Track Placement)

阶段划分:
  Phase A: 素材感知 — 场景检测 + 节拍分析 + 字幕生成
  Phase B: 智能编排 — 创意规划 + 时间线编排 + 转场/字幕选择
  Phase C: IR 生成 — 标准化的 IRSequence 输出
  Phase D: 落轨执行 — 导出 PR JSON / AE JSX / 直接 MCP 推轨
  Phase E: 审核优化 — 校验 + 人工审核 + 迭代

设计原则:
  - 管道式架构，每个阶段可独立执行或组合
  - 使用 PipelineStage 枚举标记阶段状态
  - 使用 PipelineContext 在阶段间传递数据
  - 支持断点续跑 (checkpoint)

依赖:
    ae.timeline_ir          — IR Schema + 校验 + 导出
    ae.timeline_composer    — 智能时间线编排
    ae.ai_creative_planner  — AI 创意规划
    ae.scene_detector       — 场景检测
    ae.beat_detector        — 节拍检测
    ae.subtitle_system      — 字幕生成
    ae.transition_selector  — 转场智能选择 (Phase B)
    ae.subtitle_product     — 字幕产品化 (Phase B)

用法:
    pipeline = E2EPipeline()
    result = pipeline.run(
        media_paths=["clip1.mp4", "clip2.mp4"],
        audio_path="bgm.mp3",
        creative_description="快节奏卡点视频",
    )
    # result.ir_sequence — 标准化的 IRSequence
    # result.pr_json — 可直接发送到 PremiereProMCP
    # result.ae_jsx — 可直接在 AE 中执行
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .timeline_ir import (
    IRClip,
    IREffect,
    IREffectCategory,
    IRSequence,
    IRTrack,
    IRTrackType,
    IRTransition,
    IRTransitionType,
    IRValidationResult,
    export_timeline_summary,
    export_to_ae_jsx,
    export_to_json,
    export_to_pr_json,
    validate_ir,
)

logger = logging.getLogger(__name__)


# ================================================================
#  阶段枚举
# ================================================================

class PipelineStage(str, Enum):
    """管道阶段"""
    IDLE = "idle"
    PERCEPTION = "perception"          # A: 素材感知
    ORCHESTRATION = "orchestration"    # B: 智能编排
    IR_GENERATION = "ir_generation"    # C: IR 生成
    TRACK_PLACEMENT = "track_placement"  # D: 落轨执行
    REVIEW = "review"                  # E: 审核优化
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(str, Enum):
    """管道子步骤"""
    SCENE_DETECTION = "scene_detection"
    BEAT_ANALYSIS = "beat_analysis"
    SUBTITLE_GENERATION = "subtitle_generation"
    CREATIVE_PLANNING = "creative_planning"
    TIMELINE_LAYOUT = "timeline_layout"
    TRANSITION_SELECTION = "transition_selection"
    SUBTITLE_STYLING = "subtitle_styling"
    IR_ASSEMBLY = "ir_assembly"
    IR_VALIDATION = "ir_validation"
    PR_EXPORT = "pr_export"
    AE_EXPORT = "ae_export"
    MCP_PUSH = "mcp_push"


# ================================================================
#  数据结构
# ================================================================

@dataclass
class SceneReport:
    """场景检测报告"""
    cuts: list[dict[str, Any]] = field(default_factory=list)
    shot_count: int = 0
    avg_shot_duration: float = 0.0
    method: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BeatReport:
    """节拍分析报告"""
    beats: list[float] = field(default_factory=list)  # 节拍时间列表
    bpm: float = 0.0
    downbeats: list[float] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)  # 歌曲段落
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SubtitleReport:
    """字幕生成报告"""
    segments: list[dict[str, Any]] = field(default_factory=list)
    language: str = "zh"
    confidence: float = 0.0
    word_timings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestrationReport:
    """编排报告"""
    timeline_style: str = "dynamic_cut"
    clip_order: list[str] = field(default_factory=list)
    transition_map: dict[str, str] = field(default_factory=dict)  # clip_id -> transition_type
    effect_suggestions: list[dict[str, Any]] = field(default_factory=list)
    subtitle_style: dict[str, Any] = field(default_factory=dict)
    creative_analysis: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    """管道上下文 — 阶段间数据传递"""
    media_paths: list[str] = field(default_factory=list)
    audio_path: str | None = None
    creative_description: str = ""
    output_dir: str | None = None

    # 阶段结果
    scene_report: SceneReport | None = None
    beat_report: BeatReport | None = None
    subtitle_report: SubtitleReport | None = None
    orchestration_report: OrchestrationReport | None = None

    # IR
    ir_sequence: IRSequence | None = None
    ir_validation: IRValidationResult | None = None

    # 导出产物
    pr_json: dict[str, Any] | None = None
    ae_jsx: str | None = None
    ir_json: str | None = None

    # 状态
    current_stage: PipelineStage = PipelineStage.IDLE
    completed_steps: list[PipelineStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # 时间统计
    start_time: float = 0.0
    stage_timings: dict[str, float] = field(default_factory=dict)

    # Checkpoint
    checkpoint_path: str | None = None

    def log_stage_start(self, stage: PipelineStage) -> None:
        self.current_stage = stage
        self.stage_timings[stage.value] = time.time()

    def log_stage_end(self, stage: PipelineStage) -> None:
        elapsed = time.time() - self.stage_timings.get(stage.value, time.time())
        self.stage_timings[stage.value] = elapsed
        logger.info(f"Stage [{stage.value}] completed in {elapsed:.2f}s")

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error(message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning(message)

    def step_completed(self, step: PipelineStep) -> None:
        self.completed_steps.append(step)

    def save_checkpoint(self) -> None:
        """保存管道检查点"""
        if not self.checkpoint_path:
            return
        data = {
            "current_stage": self.current_stage.value,
            "completed_steps": [s.value for s in self.completed_steps],
            "media_paths": self.media_paths,
            "audio_path": self.audio_path,
            "creative_description": self.creative_description,
            "errors": self.errors,
            "warnings": self.warnings,
        }
        if self.ir_sequence:
            data["ir_sequence"] = self.ir_sequence.to_dict()
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_checkpoint(self) -> bool:
        """加载管道检查点"""
        if not self.checkpoint_path or not os.path.exists(self.checkpoint_path):
            return False
        with open(self.checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.current_stage = PipelineStage(data.get("current_stage", "idle"))
        self.completed_steps = [
            PipelineStep(s) for s in data.get("completed_steps", [])
        ]
        if "ir_sequence" in data:
            self.ir_sequence = IRSequence.from_dict(data["ir_sequence"])
        return True


@dataclass
class PipelineResult:
    """管道执行结果"""
    success: bool = False
    ir_sequence: IRSequence | None = None
    pr_json: dict[str, Any] | None = None
    ae_jsx: str | None = None
    ir_json: str | None = None
    timeline_summary: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_duration: float = 0.0


# ================================================================
#  E2E Pipeline 核心
# ================================================================

class E2EPipeline:
    """
    端到端自动化剪辑管道。

    流程: Perception → Orchestration → IR → Track Placement

    使用方式:
        pipeline = E2EPipeline()
        result = pipeline.run(
            media_paths=["clip1.mp4", "clip2.mp4"],
            audio_path="bgm.mp3",
            creative_description="快节奏卡点视频",
        )
    """

    def __init__(
        self,
        enable_scene_detection: bool = True,
        enable_beat_analysis: bool = True,
        enable_subtitles: bool = True,
        enable_creative_planning: bool = True,
        output_format: str = "all",  # "pr" | "ae" | "json" | "all"
        checkpoint_dir: str | None = None,
    ):
        self.enable_scene_detection = enable_scene_detection
        self.enable_beat_analysis = enable_beat_analysis
        self.enable_subtitles = enable_subtitles
        self.enable_creative_planning = enable_creative_planning
        self.output_format = output_format
        self.checkpoint_dir = checkpoint_dir

    def run(
        self,
        media_paths: list[str],
        audio_path: str | None = None,
        creative_description: str = "",
        output_dir: str | None = None,
        resume: bool = False,
    ) -> PipelineResult:
        """
        执行完整的 E2E 管道。

        Args:
            media_paths: 素材路径列表
            audio_path: 音频路径 (BGM)
            creative_description: 创意描述 (自然语言)
            output_dir: 输出目录
            resume: 是否从检查点恢复

        Returns:
            PipelineResult 包含所有产物
        """
        ctx = PipelineContext(
            media_paths=media_paths,
            audio_path=audio_path,
            creative_description=creative_description,
            output_dir=output_dir,
            start_time=time.time(),
        )

        if self.checkpoint_dir and output_dir:
            ctx.checkpoint_path = os.path.join(
                self.checkpoint_dir, "pipeline_checkpoint.json"
            )

        # 尝试恢复
        if resume and ctx.load_checkpoint():
            logger.info(f"从检查点恢复，当前阶段: {ctx.current_stage.value}")

        try:
            # === Phase A: Perception ===
            if ctx.current_stage in (PipelineStage.IDLE, PipelineStage.PERCEPTION):
                self._run_perception(ctx)

            # === Phase B: Orchestration ===
            if ctx.current_stage in (
                PipelineStage.IDLE, PipelineStage.PERCEPTION,
                PipelineStage.ORCHESTRATION,
            ):
                self._run_orchestration(ctx)

            # === Phase C: IR Generation ===
            if ctx.current_stage in (
                PipelineStage.IDLE, PipelineStage.PERCEPTION,
                PipelineStage.ORCHESTRATION, PipelineStage.IR_GENERATION,
            ):
                self._run_ir_generation(ctx)

            # === Phase D: Track Placement ===
            if ctx.current_stage in (
                PipelineStage.IDLE, PipelineStage.PERCEPTION,
                PipelineStage.ORCHESTRATION, PipelineStage.IR_GENERATION,
                PipelineStage.TRACK_PLACEMENT,
            ):
                self._run_track_placement(ctx)

            # === Phase E: Review ===
            self._run_review(ctx)

            ctx.current_stage = PipelineStage.COMPLETED

        except Exception as e:
            ctx.current_stage = PipelineStage.FAILED
            ctx.add_error(f"管道异常: {e}")
            logger.exception("管道执行失败")
            ctx.save_checkpoint()

        return PipelineResult(
            success=(ctx.current_stage == PipelineStage.COMPLETED),
            ir_sequence=ctx.ir_sequence,
            pr_json=ctx.pr_json,
            ae_jsx=ctx.ae_jsx,
            ir_json=ctx.ir_json,
            timeline_summary=export_timeline_summary(ctx.ir_sequence) if ctx.ir_sequence else "",
            errors=ctx.errors,
            warnings=ctx.warnings,
            total_duration=time.time() - ctx.start_time,
        )

    # ----------------------------------------------------------
    #  Phase A: Perception
    # ----------------------------------------------------------

    def _run_perception(self, ctx: PipelineContext) -> None:
        """Phase A: 素材感知 — 场景检测 + 节拍分析 + 字幕"""
        ctx.log_stage_start(PipelineStage.PERCEPTION)
        logger.info("=" * 50)
        logger.info("Phase A: Perception — 素材感知")
        logger.info("=" * 50)

        # 场景检测
        if self.enable_scene_detection:
            logger.info("[A1] 场景检测...")
            try:
                ctx.scene_report = self._detect_scenes(ctx.media_paths)
                ctx.step_completed(PipelineStep.SCENE_DETECTION)
                logger.info(
                    f"  ✓ 检测到 {ctx.scene_report.shot_count} 个镜头，"
                    f"平均 {ctx.scene_report.avg_shot_duration:.1f}s"
                )
            except Exception as e:
                ctx.add_warning(f"场景检测失败: {e}，使用占位数据")
                ctx.scene_report = SceneReport(
                    shot_count=len(ctx.media_paths),
                    avg_shot_duration=3.0,
                    method="placeholder",
                )
        else:
            ctx.scene_report = SceneReport(
                shot_count=len(ctx.media_paths),
                avg_shot_duration=3.0,
                method="skipped",
            )

        # 节拍分析
        if self.enable_beat_analysis and ctx.audio_path:
            logger.info("[A2] 节拍分析...")
            try:
                ctx.beat_report = self._analyze_beats(ctx.audio_path)
                ctx.step_completed(PipelineStep.BEAT_ANALYSIS)
                logger.info(f"  ✓ BPM={ctx.beat_report.bpm}, {len(ctx.beat_report.beats)} 个节拍")
            except Exception as e:
                ctx.add_warning(f"节拍分析失败: {e}")
                ctx.beat_report = BeatReport(bpm=120.0)
        else:
            ctx.beat_report = BeatReport(bpm=120.0)

        # 字幕
        if self.enable_subtitles and ctx.audio_path:
            logger.info("[A3] 字幕生成...")
            try:
                ctx.subtitle_report = self._generate_subtitles(ctx.audio_path)
                ctx.step_completed(PipelineStep.SUBTITLE_GENERATION)
                logger.info(
                    f"  ✓ {len(ctx.subtitle_report.segments)} 条字幕"
                    f" (置信度: {ctx.subtitle_report.confidence:.1%})"
                )
            except Exception as e:
                ctx.add_warning(f"字幕生成失败: {e}")
                ctx.subtitle_report = SubtitleReport()
        else:
            ctx.subtitle_report = SubtitleReport()

        ctx.log_stage_end(PipelineStage.PERCEPTION)
        ctx.save_checkpoint()

    # ----------------------------------------------------------
    #  Phase B: Orchestration
    # ----------------------------------------------------------

    def _run_orchestration(self, ctx: PipelineContext) -> None:
        """Phase B: 智能编排 — 创意规划 + 时间线布局 + 转场/字幕选择"""
        ctx.log_stage_start(PipelineStage.ORCHESTRATION)
        logger.info("=" * 50)
        logger.info("Phase B: Orchestration — 智能编排")
        logger.info("=" * 50)

        creative_analysis = {}

        # 创意规划 (LLM)
        if self.enable_creative_planning and ctx.creative_description:
            logger.info("[B1] 创意规划...")
            try:
                creative_analysis = self._plan_creatively(ctx)
                ctx.step_completed(PipelineStep.CREATIVE_PLANNING)
                logger.info(f"  ✓ 风格: {creative_analysis.get('style', 'auto')}")
            except Exception as e:
                ctx.add_warning(f"创意规划失败: {e}")

        # 时间线布局
        logger.info("[B2] 时间线布局...")
        try:
            orchestration = self._layout_timeline(ctx, creative_analysis)
            ctx.orchestration_report = orchestration
            ctx.step_completed(PipelineStep.TIMELINE_LAYOUT)
            logger.info(f"  ✓ {len(orchestration.clip_order)} 个片段排序完成")
        except Exception as e:
            ctx.add_error(f"时间线布局失败: {e}")
            raise

        # 转场选择 (Phase B skeleton)
        logger.info("[B3] 转场选择...")
        try:
            self._select_transitions(ctx)
            ctx.step_completed(PipelineStep.TRANSITION_SELECTION)
        except Exception as e:
            ctx.add_warning(f"转场选择失败 (将使用默认切): {e}")

        # 字幕样式 (Phase B skeleton)
        if ctx.subtitle_report and ctx.subtitle_report.segments:
            logger.info("[B4] 字幕样式...")
            try:
                self._style_subtitles(ctx)
                ctx.step_completed(PipelineStep.SUBTITLE_STYLING)
            except Exception as e:
                ctx.add_warning(f"字幕样式设置失败: {e}")

        ctx.log_stage_end(PipelineStage.ORCHESTRATION)
        ctx.save_checkpoint()

    # ----------------------------------------------------------
    #  Phase C: IR Generation
    # ----------------------------------------------------------

    def _run_ir_generation(self, ctx: PipelineContext) -> None:
        """Phase C: IR 生成 — 组装 IRSequence + 校验"""
        ctx.log_stage_start(PipelineStage.IR_GENERATION)
        logger.info("=" * 50)
        logger.info("Phase C: IR Generation — IR 组装与校验")
        logger.info("=" * 50)

        logger.info("[C1] 组装 IRSequence...")
        ctx.ir_sequence = self._assemble_ir_sequence(ctx)
        ctx.step_completed(PipelineStep.IR_ASSEMBLY)
        logger.info(
            f"  ✓ {len(ctx.ir_sequence.tracks)} 轨，"
            f"总时长 {ctx.ir_sequence.total_duration:.1f}s"
        )

        logger.info("[C2] 校验 IR...")
        ctx.ir_validation = validate_ir(ctx.ir_sequence)
        ctx.step_completed(PipelineStep.IR_VALIDATION)

        if ctx.ir_validation.is_valid:
            logger.info("  ✓ 校验通过")
        else:
            logger.warning(f"  ⚠ {len(ctx.ir_validation.errors)} 个校验错误")
            for e in ctx.ir_validation.errors:
                ctx.add_warning(f"IR 校验: [{e.path}] {e.message}")
            # 校验错误不阻断管道，但标记警告
            ctx.ir_validation.raise_if_invalid()

        ctx.log_stage_end(PipelineStage.IR_GENERATION)
        ctx.save_checkpoint()

    # ----------------------------------------------------------
    #  Phase D: Track Placement
    # ----------------------------------------------------------

    def _run_track_placement(self, ctx: PipelineContext) -> None:
        """Phase D: 落轨 — 导出 PR JSON / AE JSX / JSON"""
        ctx.log_stage_start(PipelineStage.TRACK_PLACEMENT)
        logger.info("=" * 50)
        logger.info("Phase D: Track Placement — 落轨导出")
        logger.info("=" * 50)

        if not ctx.ir_sequence:
            ctx.add_error("IRSequence 未生成，无法导出")
            return

        # PR JSON 导出
        if self.output_format in ("pr", "all"):
            logger.info("[D1] 导出 PR JSON...")
            ctx.pr_json = export_to_pr_json(ctx.ir_sequence)
            ctx.step_completed(PipelineStep.PR_EXPORT)
            logger.info(f"  ✓ {sum(1 for _ in _flatten_clips(ctx.ir_sequence))} 个片段")

        # AE JSX 导出
        if self.output_format in ("ae", "all"):
            logger.info("[D2] 导出 AE JSX...")
            ctx.ae_jsx = export_to_ae_jsx(ctx.ir_sequence)
            ctx.step_completed(PipelineStep.AE_EXPORT)
            logger.info(f"  ✓ {len(ctx.ae_jsx)} 字符 JSX 脚本")

        # IR JSON 导出
        if self.output_format in ("json", "all"):
            logger.info("[D3] 导出 IR JSON...")
            ctx.ir_json = export_to_json(ctx.ir_sequence)

        # 写入文件
        if ctx.output_dir:
            self._write_outputs(ctx)

        ctx.log_stage_end(PipelineStage.TRACK_PLACEMENT)
        ctx.save_checkpoint()

    # ----------------------------------------------------------
    #  Phase E: Review
    # ----------------------------------------------------------

    def _run_review(self, ctx: PipelineContext) -> None:
        """Phase E: 审核 — 输出摘要 + 质量检查"""
        ctx.log_stage_start(PipelineStage.REVIEW)
        logger.info("=" * 50)
        logger.info("Phase E: Review — 审核输出")
        logger.info("=" * 50)

        if ctx.ir_sequence:
            summary = export_timeline_summary(ctx.ir_sequence)
            logger.info(f"\n{summary}")

        if ctx.warnings:
            logger.warning(f"\n{len(ctx.warnings)} 个警告:")
            for w in ctx.warnings:
                logger.warning(f"  - {w}")

        if ctx.errors:
            logger.error(f"\n{len(ctx.errors)} 个错误:")
            for e in ctx.errors:
                logger.error(f"  - {e}")

        total_time = time.time() - ctx.start_time
        logger.info(f"\n总耗时: {total_time:.2f}s")

        ctx.log_stage_end(PipelineStage.REVIEW)

    # ----------------------------------------------------------
    #  Sub-methods (可被子类覆盖或注入具体实现)
    # ----------------------------------------------------------

    def _detect_scenes(self, media_paths: list[str]) -> SceneReport:
        """场景检测 — 尝试加载 PySceneDetect，失败回退

        IR 适配层：无论 detector 返回 List[SceneCut]（ae.scene_detector）
        还是 SceneDetectResult（analysis.scene_detector），统一转换为
        List[SceneCut] 后装入 SceneReport，保证下游消费格式一致。
        """
        try:
            from .scene_detector import SceneDetector as _SD
            detector = _SD()
            all_cuts = []
            for path in media_paths:
                cuts = detector.detect(path)
                # IR 适配：兼容 SceneDetectResult（analysis.scene_detector）
                # 与 List[SceneCut]（ae.scene_detector）两种返回类型
                if hasattr(cuts, "to_scene_cuts"):
                    cuts = cuts.to_scene_cuts()
                if isinstance(cuts, list):
                    all_cuts.extend(cuts)
            return SceneReport(
                cuts=[{"time": c} if isinstance(c, (int, float)) else c for c in all_cuts],
                shot_count=len(all_cuts) or len(media_paths),
                avg_shot_duration=3.0,
                method="PySceneDetect" if all_cuts else "file_count",
            )
        except ImportError:
            logger.debug("PySceneDetect 不可用，使用占位数据")
            return SceneReport(
                shot_count=len(media_paths),
                avg_shot_duration=3.0,
                method="placeholder",
            )

    def _analyze_beats(self, audio_path: str) -> BeatReport:
        """节拍分析 — 尝试加载 librosa，失败回退"""
        try:
            from .beat_detector import BeatDetector as _BD
            detector = _BD()
            result = detector.detect(audio_path)
            if isinstance(result, dict):
                return BeatReport(
                    beats=result.get("beats", []),
                    bpm=result.get("bpm", 120.0),
                    downbeats=result.get("downbeats", []),
                    sections=result.get("sections", []),
                )
            return BeatReport(bpm=120.0)
        except ImportError:
            logger.debug("BeatDetector 不可用，使用占位数据")
            return BeatReport(bpm=120.0)

    def _generate_subtitles(self, audio_path: str) -> SubtitleReport:
        """字幕生成 — 尝试加载 WhisperSubtitleEngine，失败回退"""
        try:
            from .subtitle_system import SubtitleParser
            # 尝试 whisper 字幕引擎
            try:
                from .whisper_subtitle import WhisperSubtitleEngine
                engine = WhisperSubtitleEngine()
                result = engine.transcribe(audio_path)
                if result:
                    return SubtitleReport(
                        segments=getattr(result, "segments", []),
                        language=getattr(result, "language", "zh"),
                        confidence=getattr(result, "confidence", 0.0),
                    )
            except (ImportError, Exception):
                pass
            # 回退: 尝试找同名字幕文件
            base = os.path.splitext(audio_path)[0]
            for ext in (".srt", ".vtt", ".ass"):
                sub_path = base + ext
                if os.path.exists(sub_path):
                    with open(sub_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if ext == ".srt":
                        items = SubtitleParser.parse_srt(content)
                    elif ext == ".vtt":
                        items = SubtitleParser.parse_vtt(content)
                    else:
                        items = []
                    return SubtitleReport(
                        segments=[{"start": i.start_time, "end": i.end_time, "text": i.text}
                                  for i in items],
                    )
            return SubtitleReport()
        except Exception:
            return SubtitleReport()

    def _plan_creatively(self, ctx: PipelineContext) -> dict[str, Any]:
        """AI 创意规划"""
        try:
            from .ai_creative_planner import AICreativePlanner
            planner = AICreativePlanner()
            result = planner.parse_creative_description(ctx.creative_description)
            return result.get("analysis", {})
        except ImportError:
            return {"style": "auto", "source": "fallback"}

    def _layout_timeline(
        self, ctx: PipelineContext, creative_analysis: dict[str, Any]
    ) -> OrchestrationReport:
        """时间线布局编排"""
        try:
            from .timeline_composer import TimelineComposer, TimelineStyle
            composer = TimelineComposer()

            style_name = creative_analysis.get("style", "dynamic_cut")
            try:
                style = TimelineStyle(style_name)
            except ValueError:
                style = TimelineStyle.DYNAMIC_CUT

            # 使用 beat 信息计算片段时长
            beat_bpm = ctx.beat_report.bpm if ctx.beat_report else 120.0
            beat_duration = 60.0 / max(beat_bpm, 1.0)

            timeline = composer.build_timeline(
                clips=ctx.media_paths,
                audio=ctx.audio_path,
                style=style.value,
            )

            return OrchestrationReport(
                timeline_style=style.value,
                clip_order=ctx.media_paths,
                transition_map={},
                effect_suggestions=[],
                creative_analysis=creative_analysis,
                metadata={"beat_duration": beat_duration},
            )
        except ImportError:
            return OrchestrationReport(
                timeline_style="dynamic_cut",
                clip_order=ctx.media_paths,
            )

    def _select_transitions(self, ctx: PipelineContext) -> None:
        """转场智能选择 (Phase B skeleton)"""
        try:
            from .transition_selector import TransitionSelector
            selector = TransitionSelector()
            if ctx.orchestration_report and ctx.media_paths:
                transition_map = selector.select_for_sequence(
                    ctx.media_paths,
                    style=ctx.orchestration_report.timeline_style,
                )
                ctx.orchestration_report.transition_map = transition_map or {}
        except ImportError:
            logger.debug("TransitionSelector 不可用，使用默认切")

    def _style_subtitles(self, ctx: PipelineContext) -> None:
        """字幕样式设置 (Phase B skeleton)"""
        try:
            from .subtitle_product import SubtitleStyler
            styler = SubtitleStyler()
            if ctx.orchestration_report:
                style = styler.recommend_style(
                    creative_desc=ctx.creative_description,
                )
                ctx.orchestration_report.subtitle_style = style or {}
        except ImportError:
            logger.debug("SubtitleStyler 不可用，使用默认样式")

    def _assemble_ir_sequence(self, ctx: PipelineContext) -> IRSequence:
        """组装 IRSequence"""
        seq = IRSequence(
            name=ctx.creative_description[:50] or "Auto_Sequence",
            width=1920,
            height=1080,
            frame_rate=30.0,
        )

        # 视频轨
        video_track = IRTrack(index=0, type=IRTrackType.VIDEO, name="Video")
        beat_duration = 3.0
        if ctx.beat_report and ctx.beat_report.beats:
            beat_duration = 60.0 / max(ctx.beat_report.bpm, 1.0)

        transition_map = {}
        if ctx.orchestration_report:
            transition_map = ctx.orchestration_report.transition_map

        for i, path in enumerate(ctx.media_paths):
            timeline_in = i * beat_duration
            clip = IRClip(
                id=f"clip_{i:03d}",
                source_path=path,
                timeline_in=timeline_in,
                timeline_out=timeline_in + beat_duration,
                label=os.path.splitext(os.path.basename(path))[0],
                tags=["auto"],
            )

            # 应用转场
            trans_type = transition_map.get(path, "cut")
            if trans_type != "cut":
                try:
                    t_type = IRTransitionType(trans_type)
                    clip.transition_in = IRTransition(
                        type=t_type,
                        duration=0.5,
                    )
                except ValueError:
                    pass

            video_track.clips.append(clip)

        seq.add_track(video_track)

        # 音频轨
        if ctx.audio_path:
            audio_track = IRTrack(index=1, type=IRTrackType.AUDIO, name="Audio")
            audio_clip = IRClip(
                id="audio_bgm",
                source_path=ctx.audio_path,
                timeline_in=0.0,
                timeline_out=video_track.total_duration,
            )
            audio_track.clips.append(audio_clip)
            seq.add_track(audio_track)

        # 字幕轨
        if ctx.subtitle_report and ctx.subtitle_report.segments:
            sub_track = IRTrack(
                index=2, type=IRTrackType.SUBTITLE, name="Subtitles",
                target_language=ctx.subtitle_report.language,
            )
            for i, seg in enumerate(ctx.subtitle_report.segments):
                start = seg.get("start", 0.0)
                end = seg.get("end", start + 2.0)
                sub_clip = IRClip(
                    id=f"sub_{i:03d}",
                    source_path="__subtitle__",
                    timeline_in=start,
                    timeline_out=end,
                    label=seg.get("text", ""),
                    tags=["subtitle", "auto"],
                )
                sub_track.clips.append(sub_clip)
            seq.add_track(sub_track)

        return seq

    def _write_outputs(self, ctx: PipelineContext) -> None:
        """写入产物到文件"""
        if not ctx.output_dir:
            return
        os.makedirs(ctx.output_dir, exist_ok=True)

        if ctx.pr_json:
            path = os.path.join(ctx.output_dir, "timeline_pr.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ctx.pr_json, f, ensure_ascii=False, indent=2)
            logger.info(f"  已写入: {path}")

        if ctx.ae_jsx:
            path = os.path.join(ctx.output_dir, "timeline_ae.jsx")
            with open(path, "w", encoding="utf-8") as f:
                f.write(ctx.ae_jsx)
            logger.info(f"  已写入: {path}")

        if ctx.ir_json:
            path = os.path.join(ctx.output_dir, "timeline_ir.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(ctx.ir_json)
            logger.info(f"  已写入: {path}")

        if ctx.ir_sequence:
            path = os.path.join(ctx.output_dir, "timeline_summary.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(export_timeline_summary(ctx.ir_sequence))
            logger.info(f"  已写入: {path}")


# ================================================================
#  辅助函数
# ================================================================

def _flatten_clips(sequence: IRSequence):
    """递归展平所有 IRClip"""
    for track in sequence.tracks:
        for clip in track.clips:
            yield clip
            if clip.children:
                for child in clip.children:
                    yield child


# ================================================================
#  便捷函数
# ================================================================

def quick_run(
    media_paths: list[str],
    audio_path: str | None = None,
    description: str = "",
    output_dir: str | None = None,
) -> PipelineResult:
    """
    快速运行 E2E 管道。

    Args:
        media_paths: 素材路径
        audio_path: 背景音乐
        description: 创意描述
        output_dir: 输出目录

    Returns:
        PipelineResult
    """
    pipeline = E2EPipeline(
        enable_scene_detection=True,
        enable_beat_analysis=True,
        enable_subtitles=True,
        enable_creative_planning=bool(description),
        output_format="all",
    )
    return pipeline.run(
        media_paths=media_paths,
        audio_path=audio_path,
        creative_description=description,
        output_dir=output_dir,
    )
