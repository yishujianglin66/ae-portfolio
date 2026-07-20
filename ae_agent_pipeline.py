#!/usr/bin/env python3
"""
AE AI Agent 端到端流程管理器 v2.0 - 企业级架构重构版

架构设计（五层架构 + 核心基础设施层）：
┌──────────────────────────────────────────────────────────────────────────┐
│                        Core Infrastructure                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ EventBus    │  │ StateMachine│  │ Observability│  │ ConfigManager   │ │
│  │ (事件驱动)   │  │ (状态管理)   │  │ (可观测性)   │  │ (配置管理)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │               │                 │                  │         │
└─────────┼───────────────┼─────────────────┼──────────────────┼─────────┘
          │               │                 │                  │
┌─────────▼────────────────▼────────────────▼──────────────────▼─────────┐
│                        AE AI Agent Pipeline                            │
├────────────────────────────────────────────────────────────────────────┤
│  Layer 5: Feedback (反馈层)                                           │
│  ├── 结果评估                                                          │
│  ├── 学习优化                                                          │
│  └── 置信度校准                                                        │
├────────────────────────────────────────────────────────────────────────┤
│  Layer 4: Execution (执行层) - WorkflowOrchestrator                    │
│  ├── Silhouette 执行引擎                                               │
│  ├── AE 执行引擎                                                       │
│  └── 自动化渲染                                                         │
├────────────────────────────────────────────────────────────────────────┤
│  Layer 3: Planning (规划层)                                            │
│  ├── 任务分解                                                          │
│  ├── 步骤规划                                                          │
│  └── 资源调度                                                          │
├────────────────────────────────────────────────────────────────────────┤
│  Layer 2: Understanding (理解层)                                       │
│  ├── 语义理解                                                          │
│  ├── 情绪识别                                                          │
│  └── 意图推理 / IntentRouter                                            │
├────────────────────────────────────────────────────────────────────────┤
│  Layer 1: Perception (感知层)                                          │
│  ├── 视频帧分析                                                         │
│  ├── 音频分析                                                          │
│  └── 素材检索                                                          │
└────────────────────────────────────────────────────────────────────────┘
"""
import os
import json
import time
import math
import hashlib
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field


@dataclass
class PerceptionResult:
    video_analysis: Dict = None
    audio_analysis: Dict = None
    clip_features: List[Dict] = None
    music_features: Dict = None
    topaz_enhanced: List[Dict] = None
    color_graded: List[Dict] = None
    ai_generated: List[Dict] = None
    blender_scenes: List[Dict] = None


@dataclass
class UnderstandingResult:
    intent: str = ""
    mood: str = ""
    mood_score: float = 0.0
    style: str = ""
    tempo: float = 0.0
    duration: float = 0.0
    keywords: List[str] = field(default_factory=list)
    scene_description: str = ""
    silhouette_task: str = ""
    is_hybrid: bool = False
    route_type: str = "ae_only"
    # NLU Parser 精细意图字段（Phase4 衔接）
    nlu_intent_type: str = ""
    nlu_confidence: float = 0.0
    nlu_slots: Dict[str, Any] = field(default_factory=dict)
    nlu_matched_pattern: str = ""
    # LLM 增强置信度
    confidence: float = 0.0
    # ClarificationEngine 澄清字段
    clarification_questions: List[Dict] = field(default_factory=list)
    confidence_gaps: Dict[str, float] = field(default_factory=dict)
    # EffectDescriptionParser 效果描述解析字段
    effect_keywords: List[str] = field(default_factory=list)
    color_keywords: List[Dict] = field(default_factory=list)
    intensity_keywords: List[str] = field(default_factory=list)
    temporal_keywords: List[str] = field(default_factory=list)
    # intent_to_report 生成的 AnalysisReport（Phase4→Phase3 衔接）
    analysis_report: Any = None
    # AIScheduler 统一调度结果（Phase4 完整管线编排）
    scheduler_result: Any = None
    # vocabulary_map 增强扫描结果（比 effect_description_parser 更丰富的同义词覆盖）
    vocab_scan_enhanced: Dict[str, Any] = field(default_factory=dict)
    # Phase3 effect_name_map 增强结果（display_name→matchName 解析）
    effect_name_map_resolved: Dict[str, Any] = field(default_factory=dict)
    # DaVinci Resolve 调色相关字段
    resolve_preset: str = ""
    needs_color_grading: bool = False
    # AI 视频生成相关字段
    ai_video_requested: bool = False
    ai_provider: str = ""
    ai_prompt: str = ""
    # Blender 3D 场景相关字段
    blender_requested: bool = False
    blender_scene_type: str = ""


@dataclass
class PlanningResult:
    composition: Dict = None
    layers: List[Dict] = field(default_factory=list)
    effects: List[Dict] = field(default_factory=list)
    keyframes: List[Dict] = field(default_factory=list)
    transitions: List[Dict] = field(default_factory=list)
    timeline: List[Dict] = field(default_factory=list)
    execution_order: List[str] = field(default_factory=list)
    silhouette_operations: List[Dict] = field(default_factory=list)
    # Phase3 report_to_ops 生成的编译器操作列表（createComp/addLayer/addEffect/...）
    compiler_operations: List[Dict] = field(default_factory=list)
    # Phase3 analyze_report 统计信息
    report_stats: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    success: bool = False
    error_message: str = ""
    output_path: str = ""
    execution_time: float = 0.0
    steps_completed: int = 0
    total_steps: int = 0
    artifacts: List[Dict] = field(default_factory=list)
    silhouette_artifacts: List[Dict] = field(default_factory=list)


@dataclass
class FeedbackResult:
    rating: float = 0.0
    confidence: float = 0.0
    improvement_suggestions: List[str] = field(default_factory=list)
    learned_patterns: Dict = field(default_factory=dict)
    error_log: List[str] = field(default_factory=list)
    # Phase5 验证结果（ResultVerifier 回读对比）
    verification_result: Dict[str, Any] = field(default_factory=dict)
    # Phase5 学习循环度量（LearningLoop.get_metrics）
    learning_metrics: Dict[str, Any] = field(default_factory=dict)
    # Phase5 失败恢复动作（FailureRecovery.handle_failure 返回）
    recovery_action: Dict[str, Any] = field(default_factory=dict)


class AEAgentPipeline:
    def __init__(self, config_path: str = None):
        self._init_core_infrastructure()
        self._config_path = config_path
        self._load_config()

        self.video_analyzer = None
        self.audio_analyzer = None
        self.feedback_store = None

        self.topaz_enhancer = None
        self.topaz_enabled = False
        self.topaz_mode = "auto"
        self.topaz_preset = "default"

        self.resolve_colorist = None
        self.ai_video_generator = None
        self.blender_integrator = None
        self.resolve_enabled = False
        self.ai_video_enabled = False
        self.blender_enabled = False
        self.resolve_preset = "default"

        self.keyframe_generator = None
        self.beat_mapper = None
        self.ts_compiler = None

        self.scene_orchestrator = None
        self.beat_orchestrator = None
        self.effect_composition_engine = None
        self.effect_composer = None
        self.feedback_manager = None

        self.nlu_parser = None
        self.effect_description_parser = None
        self.clarification_engine = None
        self.parameter_optimizer = None

        self.silhouette_executor = None

        self.intent_router = None
        self.hybrid_coordinator = None

        self._init_analyzers()
        self._init_phase2_modules()
        self._init_phase3_modules()
        self._init_phase4_modules()
        self._init_phase5_modules()

        self._subscribe_events()

    def _init_core_infrastructure(self):
        self._observability = None
        self._logger = logging.getLogger("ae-agent")
        self._tracer = None
        self._metrics = None

        try:
            from core.observability import (
                ObservabilityContext, create_context, set_global_context,
                log_info, log_warning, log_error, log_debug,
                increment_counter, record_histogram
            )
            self._observability = create_context()
            set_global_context(self._observability)
            self._logger = self._observability.logger
            self._tracer = self._observability.tracer
            self._metrics = self._observability.metrics
            self.log_info("Observability 加载成功")
        except ImportError as e:
            self.log_warning(f"Observability 加载失败: {e}")

        try:
            from core.config import ConfigManager, get_config
            self._config_manager = ConfigManager()
            self._config_manager.load_config()
            self._config = self._config_manager
            self.log_info("ConfigManager 加载成功")
        except ImportError as e:
            self._config_manager = None
            self._config = None
            self.log_warning(f"ConfigManager 加载失败: {e}")

        try:
            from core.event_bus import EventBus, event_bus, publish_pipeline_event, publish_error, EventCategory
            self._event_bus = event_bus
            self._publish_pipeline_event = self._publish_with_correlation
            self._publish_error = self._publish_error_with_correlation
            self._correlation_id = None
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._event_bus.start())
            except RuntimeError:
                pass
            self._init_event_subscribers()
            self._init_event_audit()
            self.log_info("EventBus 加载成功")
        except ImportError as e:
            self._event_bus = None
            self._publish_pipeline_event = lambda *args, **kwargs: None
            self._publish_error = lambda *args, **kwargs: None
            self.log_warning(f"EventBus 加载失败: {e}")

        try:
            from core.state_machine import PipelineStateMachine
            self._state_machine = PipelineStateMachine()
            self.log_info("PipelineStateMachine 加载成功")
        except ImportError as e:
            self._state_machine = None
            self.log_warning(f"PipelineStateMachine 加载失败: {e}")

        try:
            from core.workflow_orchestrator import WorkflowOrchestrator, create_orchestrator
            self._orchestrator = create_orchestrator(max_concurrent=5)
            self._orchestrator.add_progress_callback(self._on_workflow_progress)
            self.log_info("WorkflowOrchestrator 加载成功")
        except ImportError as e:
            self._orchestrator = None
            self.log_warning(f"WorkflowOrchestrator 加载失败: {e}")

        # LLM 网关 (OmniRoute 兼容)
        self._llm_gateway = None
        try:
            from core.llm_gateway import LLMGateway, LLMConfig, TaskType
            self._llm_gateway = LLMGateway()
            self._llm_gateway.configure_from_env()

            # 从 ConfigManager 加载配置
            if self._config_manager:
                model_cfg = self._config_manager.get("model", {})
                if model_cfg.get("base_url") or model_cfg.get("api_key"):
                    llm_config = LLMConfig(
                        base_url=model_cfg.get("base_url",
                                                self._llm_gateway._config.base_url),
                        api_key=model_cfg.get("api_key",
                                               self._llm_gateway._config.api_key),
                        default_model=model_cfg.get("default_model", "auto"),
                        timeout_seconds=model_cfg.get("timeout_seconds", 30),
                        max_retries=model_cfg.get("max_retries", 3),
                        enable_compression=model_cfg.get("enable_compression", True),
                        enable_fallback=model_cfg.get("enable_fallback", True),
                    )
                    self._llm_gateway.configure(llm_config)

            if self._llm_gateway.is_available():
                self.log_info("LLM 网关加载成功 (OmniRoute 兼容)")
            else:
                self.log_info("LLM 网关未配置 (nlu_model=local 模式)")
        except ImportError as e:
            self._llm_gateway = None
            self.log_warning(f"LLM 网关加载失败: {e}")

        # 持久化记忆系统 (cavemem 架构)
        self._memory_store = None
        try:
            from core.memory_store import MemoryStore
            db_path = None
            if self._config_manager:
                mem_cfg = self._config_manager.get("memory", {})
                if mem_cfg.get("enabled", True):
                    db_path = mem_cfg.get("db_path") or None
                else:
                    self._memory_store = None
                    self.log_info("记忆系统已禁用")
                    return
            self._memory_store = MemoryStore(db_path=db_path)
            self.log_info("持久化记忆系统加载成功 (cavemem 架构)")
        except ImportError as e:
            self._memory_store = None
            self.log_warning(f"记忆系统加载失败: {e}")

    def close(self) -> None:
        """关闭 Pipeline 资源，释放数据库连接"""
        if self._memory_store:
            try:
                self._memory_store.close()
            except Exception:
                pass
            self._memory_store = None
        if self._observability:
            try:
                import asyncio
                asyncio.run(self._observability.close())
            except Exception:
                pass
            self._observability = None
        if self._event_bus:
            self._event_bus = None

    def _load_config(self):
        if self._config_manager:
            return

        if not self._config_path:
            self._config_path = os.path.join(
                os.path.dirname(__file__), "config", "media-config.json"
            )

        try:
            from performance.cache_manager import get_config_cached
            data = get_config_cached(self._config_path)
            if data:
                self._config = data
                return
        except ImportError:
            pass

        if not os.path.exists(self._config_path):
            self._config = {
                "audio": {"default_sample_rate": 22050},
                "video": {"default_fps": 30, "sample_interval": 5},
                "output": {"default_dir": "./output"},
                "ae": {"command_file": "./ae_command.json", "result_file": "./ae_result.json"}
            }
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except:
            self._config = {
                "audio": {"default_sample_rate": 22050},
                "video": {"default_fps": 30, "sample_interval": 5},
                "output": {"default_dir": "./output"},
                "ae": {"command_file": "./ae_command.json", "result_file": "./ae_result.json"}
            }

    def _publish_with_correlation(self, event_type: str, payload: Dict = None) -> None:
        """发布带 correlation_id 的工作流事件（用于请求追踪）"""
        if not self._event_bus:
            return
        try:
            from core.event_bus import PipelineEvent
            event = PipelineEvent(
                event_type,
                payload=payload or {},
                correlation_id=self._correlation_id,
            )
            self._event_bus.publish(event)
        except Exception:
            pass

    def _publish_error_with_correlation(
        self, event_type: str, error=None, payload: Dict = None
    ) -> None:
        """发布带 correlation_id 的错误事件"""
        if not self._event_bus:
            return
        try:
            from core.event_bus import ErrorEvent
            event = ErrorEvent(
                event_type,
                error,
                payload=payload or {},
                correlation_id=self._correlation_id,
            )
            self._event_bus.publish(event)
        except Exception:
            pass

    def _init_event_audit(self):
        """初始化全局事件审计订阅器 - 记录所有事件用于追溯"""
        if not self._event_bus:
            return
        try:
            self._event_bus.subscribe_global(self._on_audit_event)
        except Exception as e:
            self.log_warning(f"全局审计订阅失败: {e}")

    def _on_audit_event(self, event) -> None:
        """全局审计回调 - 记录事件摘要到日志"""
        try:
            if hasattr(event, 'event_type'):
                # 只记录关键事件，避免日志爆炸
                if event.event_type in (
                    "pipeline.start", "pipeline.completed", "pipeline.failed",
                    "silhouette.start", "silhouette.completed",
                    "phase.execution.completed", "error.occurred",
                ):
                    self.log_info(
                        f"[AUDIT] {event.event_type} "
                        f"(id={event.event_id[:8]}, "
                        f"corr={event.correlation_id[:8] if event.correlation_id else 'N/A'})"
                    )
        except Exception:
            pass

    def get_event_stats(self) -> Dict:
        """获取事件总线统计信息"""
        if not self._event_bus:
            return {}
        try:
            return self._event_bus.get_stats()
        except Exception:
            return {}

    def get_recent_events(self, limit: int = 20) -> List[Dict]:
        """获取最近的事件历史（用于调试和追溯）"""
        if not self._event_bus:
            return []
        try:
            events = self._event_bus.get_event_history(limit=limit)
            return [e.to_dict() if hasattr(e, 'to_dict') else str(e) for e in events]
        except Exception:
            return []

    def _subscribe_events(self):
        if not self._event_bus:
            return

        from core.event_bus import EventCategory

        @self._event_bus.subscribe(event_category=EventCategory.PIPELINE, event_type="pipeline.start")
        def on_pipeline_start(event):
            self.log_info(f"Pipeline started: {event.payload.get('pipeline_id')}")
            increment_counter("pipeline.starts")

        @self._event_bus.subscribe(event_category=EventCategory.PIPELINE, event_type="pipeline.completed")
        def on_pipeline_completed(event):
            duration = event.payload.get("duration", 0)
            self.log_info(f"Pipeline completed in {duration:.2f}s")
            record_histogram("pipeline.duration", duration)
            increment_counter("pipeline.completions")

        @self._event_bus.subscribe(event_category=EventCategory.PIPELINE, event_type="pipeline.failed")
        def on_pipeline_failed(event):
            error = event.payload.get("error", "")
            self.log_error(f"Pipeline failed: {error}")
            increment_counter("pipeline.failures")

        @self._event_bus.subscribe(event_category=EventCategory.SILHOUETTE, event_type="silhouette.start")
        def on_silhouette_start(event):
            self.log_info(f"Silhouette task started: {event.payload.get('task_type')}")

        @self._event_bus.subscribe(event_category=EventCategory.SILHOUETTE, event_type="silhouette.completed")
        def on_silhouette_completed(event):
            self.log_info(f"Silhouette task completed")
            increment_counter("silhouette.completions")

        @self._event_bus.subscribe(event_category=EventCategory.AE, event_type="ae.execute")
        def on_ae_execute(event):
            self.log_info(f"AE command: {event.payload.get('command')}")

        @self._event_bus.subscribe(event_category=EventCategory.ERROR, event_type="error.occurred")
        def on_error(event):
            error_type = event.payload.get("error_type", "")
            error_msg = event.payload.get("error_message", "")
            self.log_error(f"Error occurred [{error_type}]: {error_msg}")

    def _on_workflow_progress(self, progress: float, info: Dict):
        self.log_info(f"Workflow progress: {progress * 100:.1f}% ({info['completed']}/{info['total']})")
        if self._state_machine:
            self._state_machine._context.progress = progress

    # -------------------------------------------------------------------------
    # 工作流运行时控制 API
    # -------------------------------------------------------------------------

    def pause_pipeline(self) -> None:
        """暂停当前工作流执行"""
        if self._orchestrator and self._orchestrator.is_running:
            self._orchestrator.pause()
            if self._state_machine:
                self._state_machine.pause()
            self._publish_pipeline_event("pipeline.paused")
            self.log_info("Pipeline 已暂停")

    def resume_pipeline(self) -> None:
        """恢复暂停的工作流"""
        if self._orchestrator and not self._orchestrator.is_running:
            self._orchestrator.resume()
            if self._state_machine:
                self._state_machine.resume()
            self._publish_pipeline_event("pipeline.resumed")
            self.log_info("Pipeline 已恢复")

    def cancel_pipeline(self) -> None:
        """取消当前工作流"""
        if self._orchestrator:
            self._orchestrator.cancel()
            if self._state_machine:
                self._state_machine.cancel()
            self._publish_pipeline_event("pipeline.cancelled")
            self.log_info("Pipeline 已取消")

    def get_workflow_stats(self) -> Dict:
        """获取当前工作流统计信息（任务状态、耗时、重试次数）"""
        if not self._orchestrator:
            return {}
        try:
            stats = self._orchestrator.get_stats()
            stats["event_bus"] = self.get_event_stats()
            stats["state_machine"] = {
                "status": self._state_machine.status.name
                if self._state_machine else "N/A",
                "phase": self._state_machine.phase.name
                if self._state_machine else "N/A",
                "progress": self._state_machine._context.progress
                if self._state_machine else 0,
            }
            return stats
        except Exception as e:
            self.log_warning(f"获取工作流统计失败: {e}")
            return {}

    def save_workflow_state(self, path: str) -> bool:
        """持久化当前工作流状态到文件（用于断点恢复）"""
        if not self._orchestrator:
            return False
        try:
            self._orchestrator.save_to_file(path)
            self.log_info(f"工作流状态已保存: {path}")
            return True
        except Exception as e:
            self.log_warning(f"工作流状态保存失败: {e}")
            return False

    def _init_event_subscribers(self):
        """初始化 EventBus 事件订阅者，实现模块间解耦通信"""
        if not self._event_bus:
            return

        try:
            from core.event_bus import EventCategory, Event

            def on_planning_completed(event: Event):
                """规划完成事件 → 触发参数优化日志记录"""
                payload = event.payload or {}
                effect_count = payload.get("effect_count", 0)
                if effect_count > 0 and self._memory_store:
                    self._memory_store.remember(
                        category="planning",
                        key="plan_effect_count",
                        content={"effect_count": effect_count},
                        tags=["planning", "effects"],
                        confidence=0.5,
                    )

            def on_execution_completed(event: Event):
                """执行完成事件 → 更新反馈学习"""
                payload = event.payload or {}
                if not payload.get("success", False) and self._memory_store:
                    self._memory_store.remember(
                        category="execution",
                        key="execution_failure",
                        content=payload,
                        tags=["execution", "failure"],
                        confidence=0.8,
                    )

            def on_feedback_completed(event: Event):
                """反馈完成事件 → 记录评分"""
                payload = event.payload or {}
                rating = payload.get("rating", 0)
                if rating > 0.5 and self._memory_store:
                    self._memory_store.remember(
                        category="feedback",
                        key="good_rating",
                        content=payload,
                        tags=["feedback", "good"],
                        confidence=rating,
                    )

            self._event_bus.subscribe(
                EventCategory.PIPELINE,
                event_type="phase.planning.completed",
                handler=on_planning_completed,
                priority=10,
            )
            self._event_bus.subscribe(
                EventCategory.PIPELINE,
                event_type="phase.execution.completed",
                handler=on_execution_completed,
                priority=10,
            )
            self._event_bus.subscribe(
                EventCategory.PIPELINE,
                event_type="phase.feedback.completed",
                handler=on_feedback_completed,
                priority=10,
            )

            self.log_debug("EventBus 事件订阅者初始化完成")
        except Exception as e:
            self.log_warning(f"EventBus 订阅初始化失败（不影响主流程）: {e}")

    def log_info(self, message: str, **extra):
        if self._observability:
            self._observability.logger.info(message, **extra)
        else:
            self._logger.info(message)

    def log_warning(self, message: str, **extra):
        if self._observability:
            self._observability.logger.warning(message, **extra)
        else:
            self._logger.warning(message)

    def log_error(self, message: str, **extra):
        if self._observability:
            self._observability.logger.error(message, **extra)
        else:
            self._logger.error(message)

    def log_debug(self, message: str, **extra):
        if self._observability:
            self._observability.logger.debug(message, **extra)
        else:
            self._logger.debug(message)

    def _init_analyzers(self):
        try:
            from video_analyzer_enhanced import EnhancedVideoAnalyzer
            self.video_analyzer = EnhancedVideoAnalyzer()
        except ImportError as e:
            self.log_warning(f"视频分析器加载失败: {e}")

        try:
            from audio_analyzer_enhanced import EnhancedAudioAnalyzer
            self.audio_analyzer = EnhancedAudioAnalyzer()
        except ImportError as e:
            self.log_warning(f"音频分析器加载失败: {e}")

        try:
            from training_logger import VideoGenerationLogger
            self.logger_class = VideoGenerationLogger
        except ImportError as e:
            self.log_warning(f"训练日志器加载失败: {e}")
            self.logger_class = None

        # Phase 2 感知层增强模块（独立封装，与 EnhancedAnalyzer 互补）
        # 当对应第三方依赖未安装时模块本身会优雅降级（返回 success=False），
        # 这里只在导入失败时记录警告，不影响主流程。
        self.scene_detector = None
        try:
            from scene_detector import SceneDetector
            self.scene_detector = SceneDetector(enable_cache=False)
            self.log_info("SceneDetector 加载成功 (PySceneDetect 镜头分割)")
        except ImportError as e:
            self.log_warning(f"SceneDetector 加载失败: {e}")

        self.librosa_audio_analyzer = None
        try:
            from audio_analyzer_librosa import LibrosaAudioAnalyzer
            self.librosa_audio_analyzer = LibrosaAudioAnalyzer(enable_cache=False)
            self.log_info("LibrosaAudioAnalyzer 加载成功 (librosa 深度音频分析)")
        except ImportError as e:
            self.log_warning(f"LibrosaAudioAnalyzer 加载失败: {e}")

        self.media_preprocessor = None
        try:
            from media_preprocessor import MediaPreprocessor
            self.media_preprocessor = MediaPreprocessor()
            self.log_info("MediaPreprocessor 加载成功 (ffmpeg-python 素材预处理)")
        except ImportError as e:
            self.log_warning(f"MediaPreprocessor 加载失败: {e}")

        # Topaz Video AI 画质增强模块
        self.topaz_enhancer = None
        self.topaz_enabled = False
        try:
            from topaz_integration import TopazEnhancer, TopazConfig
            self.topaz_enhancer = TopazEnhancer()
            self.topaz_enabled = True
            self.log_info("TopazEnhancer 加载成功 (Topaz Video AI 画质增强)")
        except ImportError as e:
            self.log_warning(f"TopazEnhancer 加载失败: {e}")

        # DaVinci Resolve 调色模块
        self.resolve_colorist = None
        self.resolve_enabled = False
        try:
            from davinci_resolve_integration import DavinciColorist
            self.resolve_colorist = DavinciColorist()
            self.resolve_enabled = True
            self.log_info("DavinciColorist 加载成功 (DaVinci Resolve 专业调色)")
        except ImportError as e:
            self.log_warning(f"DavinciColorist 加载失败: {e}")

        # AI 视频生成模块（RunwayML / Pika）
        self.ai_video_generator = None
        self.ai_video_enabled = False
        try:
            from ai_video_generator import AIVideoGenerator
            self.ai_video_generator = AIVideoGenerator()
            self.ai_video_enabled = True
            self.log_info("AIVideoGenerator 加载成功 (RunwayML/Pika AI 视频生成)")
        except ImportError as e:
            self.log_warning(f"AIVideoGenerator 加载失败: {e}")

        # Blender 3D 场景集成模块
        self.blender_integrator = None
        self.blender_enabled = False
        try:
            from blender_3d_integration import Blender3DIntegrator
            self.blender_integrator = Blender3DIntegrator()
            self.blender_enabled = True
            self.log_info("Blender3DIntegrator 加载成功 (Blender 3D 场景)")
        except ImportError as e:
            self.log_warning(f"Blender3DIntegrator 加载失败: {e}")

        # Adobe 全家桶集成 (PS/PR/ME)
        self.adobe_suite = None
        self.adobe_enabled = False
        try:
            from adobe_suite_integration import AdobeSuiteIntegrator
            self.adobe_suite = AdobeSuiteIntegrator(mode="auto")
            self.adobe_enabled = True
            self.log_info("AdobeSuiteIntegrator 加载成功 (PS/PR/ME 全家桶)")
        except ImportError as e:
            self.log_warning(f"AdobeSuiteIntegrator 加载失败: {e}")

        # MediaPipe 人物识别与姿态估计
        self.mediapipe_integrator = None
        self.mediapipe_enabled = False
        try:
            from mediapipe_integration import MediaPipeIntegrator, MediaPipeConfig
            self.mediapipe_integrator = MediaPipeIntegrator(
                MediaPipeConfig(
                    mode="auto",
                    detect_pose=True,
                    detect_face=True,
                    detect_hands=False,
                    confidence_threshold=0.5,
                    max_num_persons=1,
                    sample_interval=5,
                )
            )
            self.mediapipe_enabled = True
            self.log_info("MediaPipeIntegrator 加载成功 (人物检测/姿态估计/面部跟踪)")
        except ImportError as e:
            self.log_warning(f"MediaPipeIntegrator 加载失败: {e}")

        # 木偶风格化自动处理器
        self.puppet_auto_processor = None
        self.puppet_auto_enabled = False
        try:
            from puppet_auto_processor import PuppetAutoProcessor
            self.puppet_auto_processor = PuppetAutoProcessor(mediapipe_mode="auto")
            self.puppet_auto_enabled = True
            self.log_info("PuppetAutoProcessor 加载成功 (木偶风格化自动识别与处理)")
        except ImportError as e:
            self.log_warning(f"PuppetAutoProcessor 加载失败: {e}")

        # 木偶风格化工作流编排器（端到端: 检测→风格化→AE执行→调色→报告）
        self.puppet_workflow_orchestrator = None
        self.puppet_workflow_enabled = False
        try:
            from puppet_workflow_orchestrator import (
                PuppetWorkflowOrchestrator,
                WorkflowConfig,
            )
            self.puppet_workflow_orchestrator = PuppetWorkflowOrchestrator(
                WorkflowConfig(
                    mediapipe_mode="auto",
                    style_types=["wooden_puppet"],
                    execute_ae=False,
                    color_grade=False,
                )
            )
            self.puppet_workflow_enabled = True
            self.log_info("PuppetWorkflowOrchestrator 加载成功 (端到端工作流编排)")
        except ImportError as e:
            self.log_warning(f"PuppetWorkflowOrchestrator 加载失败: {e}")

    def _init_phase2_modules(self):
        try:
            from keyframe_animation_generator import KeyframeAnimationGenerator
            self.keyframe_generator = KeyframeAnimationGenerator()
        except ImportError:
            self.keyframe_generator = None

        try:
            from beat_keyframe_mapper import BeatKeyframeMapper
            self.beat_mapper = BeatKeyframeMapper(precision_ms=10.0)
        except ImportError:
            self.beat_mapper = None

        try:
            from ae_ts_compiler_client import AETSCompilerClient
            self.ts_compiler = AETSCompilerClient()
        except ImportError:
            self.ts_compiler = None

    def _init_phase3_modules(self):
        try:
            from scene_orchestrator import SceneOrchestrator
            self.scene_orchestrator = SceneOrchestrator()
        except ImportError:
            self.scene_orchestrator = None

        try:
            from beat_orchestrator import BeatOrchestrator
            self.beat_orchestrator = BeatOrchestrator()
        except ImportError:
            self.beat_orchestrator = None

        try:
            from effect_composition_engine import EffectCompositionEngine
            self.effect_composition_engine = EffectCompositionEngine()
        except ImportError:
            self.effect_composition_engine = None

        try:
            from effect_composer import EffectComposer
            self.effect_composer = EffectComposer()
        except ImportError:
            self.effect_composer = None

        try:
            from style_template_library import STYLE_TEMPLATES
            self._style_templates = STYLE_TEMPLATES
        except ImportError:
            self._style_templates = {}

        try:
            from effect_generators import EffectGeneratorFactory, GeneratorContext
            self.effect_generator_factory = EffectGeneratorFactory()
        except ImportError:
            self.effect_generator_factory = None

        try:
            from parameter_mapper import ParameterMapper, MapperContext
            self.parameter_mapper = ParameterMapper()
        except ImportError:
            self.parameter_mapper = None

        try:
            from feedback_loop_manager import FeedbackLoopManager
            self.feedback_manager = FeedbackLoopManager()
        except ImportError:
            self.feedback_manager = None

    def _init_phase4_modules(self):
        try:
            from nlu_parser import NLUParser
            self.nlu_parser = NLUParser()
        except ImportError:
            self.nlu_parser = None

        try:
            from effect_description_parser import EffectDescriptionParser
            self.effect_description_parser = EffectDescriptionParser()
        except ImportError:
            self.effect_description_parser = None

        try:
            from clarification_engine import ClarificationEngine
            self.clarification_engine = ClarificationEngine()
        except ImportError:
            self.clarification_engine = None

        try:
            from parameter_optimizer import ParameterOptimizer
            self.parameter_optimizer = ParameterOptimizer()
        except ImportError:
            self.parameter_optimizer = None

        # AIScheduler：聚合 NLU+参数生成+优化的完整管线编排器
        try:
            from ai_scheduler import AIScheduler, SchedulerOptions
            self.ai_scheduler = AIScheduler()
            self.log_info("AIScheduler 已加载 (Phase4 完整管线编排)")
        except ImportError as e:
            self.ai_scheduler = None
            self.log_warning(f"AIScheduler 加载失败: {e}")

        # vocabulary_map：增强词汇扫描（13 类 72 条目，比 effect_description_parser 更丰富）
        try:
            import vocabulary_map
            self._vocabulary_map = vocabulary_map
            self.log_info(
                f"vocabulary_map 已加载 "
                f"({vocabulary_map.get_vocab_stats()['total']} 条目)"
            )
        except ImportError as e:
            self._vocabulary_map = None
            self.log_warning(f"vocabulary_map 加载失败: {e}")

    def _init_phase5_modules(self):
        try:
            from silhouette_executor import SilhouetteExecutor
            sil_mode = "auto"
            if self._config_manager:
                sil_mode = self._config_manager.get(
                    "silhouette", {}
                ).get("mode", "auto")
            self.silhouette_executor = SilhouetteExecutor(mode=sil_mode)
            self.log_info(f"Silhouette 执行端已加载 (mode={sil_mode})")
        except ImportError as e:
            self.log_warning(f"Silhouette 执行端加载失败: {e}")
            self.silhouette_executor = None

        try:
            from intent_router import IntentRouter
            self.intent_router = IntentRouter(
                memory_store=self._memory_store
            )
            self.log_info("IntentRouter 路由决策器已加载")
        except ImportError as e:
            self.log_warning(f"IntentRouter 加载失败: {e}")
            self.intent_router = None

        try:
            from hybrid_coordinator import HybridCoordinator
            self.hybrid_coordinator = HybridCoordinator(
                intent_router=self.intent_router
            )
            self.log_info("HybridCoordinator 混合协调器已加载")
        except ImportError as e:
            self.log_warning(f"HybridCoordinator 加载失败: {e}")
            self.hybrid_coordinator = None

        # ===== Phase3 模块初始化 =====
        # effect_name_map：效果显示名→matchName 映射库（42 条目）
        try:
            import effect_name_map
            self._effect_name_map = effect_name_map
            stats = effect_name_map.get_stats()
            self.log_info(
                f"effect_name_map 已加载 "
                f"({stats['total']} 条目, "
                f"{len(stats['byCategory'])} 类别)"
            )
        except ImportError as e:
            self._effect_name_map = None
            self.log_warning(f"effect_name_map 加载失败: {e}")

        # report_to_ops：决策树报告→编译器输入转换层
        try:
            import report_to_ops
            self._report_to_ops = report_to_ops
            self.log_info("report_to_ops 已加载 (Phase3 报告转换)")
        except ImportError as e:
            self._report_to_ops = None
            self.log_warning(f"report_to_ops 加载失败: {e}")

        # ===== Phase5 模块初始化 =====
        # result_verifier：执行结果验证器（通过 MCP 回读对比）
        try:
            from result_verifier import ResultVerifier, RealMcpClient
            # 延迟注入 RealMcpClient（在执行时才创建 AECommandClient）
            self._result_verifier = ResultVerifier()
            self._result_verifier_mcp_class = RealMcpClient
            self.log_info("ResultVerifier 已加载 (Phase5 结果验证, RealMcpClient 可用)")
        except ImportError as e:
            self._result_verifier = None
            self._result_verifier_mcp_class = None
            self.log_warning(f"ResultVerifier 加载失败: {e}")

        # learning_loop：学习循环（参数模板 + 默认值 + 置信度调整）
        try:
            from learning_loop import LearningLoop
            self._learning_loop = LearningLoop()
            self.log_info("LearningLoop 已加载 (Phase5 学习循环)")
        except ImportError as e:
            self._learning_loop = None
            self.log_warning(f"LearningLoop 加载失败: {e}")

        # failure_recovery：失败恢复策略（错误码→RecoveryAction）
        try:
            from failure_recovery import FailureRecovery
            self._failure_recovery = FailureRecovery()
            self.log_info("FailureRecovery 已加载 (Phase5 失败恢复)")
        except ImportError as e:
            self._failure_recovery = None
            self.log_warning(f"FailureRecovery 加载失败: {e}")

    def set_silhouette_mode(self, mode: str) -> None:
        """运行时切换 Silhouette 执行模式 (real/simulate/auto)"""
        if self.silhouette_executor:
            self.silhouette_executor.mode = mode
            self.log_info(f"Silhouette 执行模式切换为: {mode}")
        else:
            self.log_warning("Silhouette 执行端未加载，无法切换模式")

    def _to_compiler_ease(self, ease_type: str) -> str:
        if not ease_type:
            return "linear"
        lower = ease_type.lower().replace("_", "").replace("-", "").replace(" ", "")
        if lower in ("linear", "line"):
            return "linear"
        if lower in ("easein", "easein"):
            return "ease_in"
        if lower in ("easeout", "easeout"):
            return "ease_out"
        if lower in ("easeinout", "easeinout"):
            return "ease_in_out"
        if lower in ("bezier", "curve"):
            return "bezier"
        if lower in ("hold", "static"):
            return "hold"
        return "linear"

    def compile_planning_to_jsx(self, planning: PlanningResult) -> Dict:
        if self.ts_compiler is None:
            return {
                "success": False,
                "jsx_code": "",
                "command_count": 0,
                "method": "no_compiler",
                "error": "TS编译器客户端未加载",
            }

        layers = planning.layers or []
        effects = planning.effects or []
        keyframes = planning.keyframes or []

        layer_refs = []
        for i, layer in enumerate(layers):
            layer_refs.append("layer_{:03d}".format(i + 1))

        kf_by_layer = {}
        for kf in keyframes:
            ln = kf.get("layerName", "")
            if ln not in kf_by_layer:
                kf_by_layer[ln] = []
            kf_by_layer[ln].append(kf)

        operations = []

        comp = planning.composition or {}
        operations.append({
            "op": "createComp",
            "ref": "main_comp",
            "name": comp.get("name", "AI_Generated"),
            "width": comp.get("width", 1920),
            "height": comp.get("height", 1080),
            "frameRate": comp.get("frameRate", 30),
            "duration": comp.get("duration", 5),
        })

        for i, layer in enumerate(layers):
            layer_type = layer.get("type", "solid")
            layer_op = {
                "op": "addLayer",
                "ref": layer_refs[i],
                "compRef": "main_comp",
                "layerType": layer_type,
                "name": layer.get("name", "Layer_{}".format(i + 1)),
            }
            if layer_type == "solid":
                layer_op["color"] = layer.get("color", [0, 0, 0])
            if "startTime" in layer:
                layer_op["startTime"] = layer["startTime"]
            operations.append(layer_op)

        for i, fx in enumerate(effects):
            layer_name = fx.get("layerName", "")
            layer_idx = 0
            for j, layer in enumerate(layers):
                if layer.get("name") == layer_name:
                    layer_idx = j
                    break
            layer_ref = layer_refs[layer_idx] if layer_idx < len(layer_refs) else layer_refs[0]

            operations.append({
                "op": "addEffect",
                "layerRef": layer_ref,
                "matchName": fx.get("effectName", fx.get("matchName", "")),
                "settings": fx.get("settings", {}),
            })

        for ln, kf_list in kf_by_layer.items():
            layer_idx = 0
            for j, layer in enumerate(layers):
                if layer.get("name") == ln:
                    layer_idx = j
                    break
            layer_ref = layer_refs[layer_idx] if layer_idx < len(layer_refs) else layer_refs[0]

            kf_by_prop = {}
            for kf in kf_list:
                prop = kf.get("propertyName", "")
                if prop not in kf_by_prop:
                    kf_by_prop[prop] = []
                kf_by_prop[prop].append(kf)

            for prop, prop_kfs in kf_by_prop.items():
                sorted_kfs = sorted(prop_kfs, key=lambda k: k.get("time", 0))
                keyframe_list = []
                for kf in sorted_kfs:
                    keyframe_list.append({
                        "time": kf.get("time", 0),
                        "value": kf.get("value", 0),
                        "easing": {
                            "type": self._to_compiler_ease(kf.get("easeType", "linear")),
                        },
                    })
                operations.append({
                    "op": "setKeyframe",
                    "layerRef": layer_ref,
                    "propertyPath": "ADBE Transform/" + prop,
                    "keyframes": keyframe_list,
                })

        result = self.ts_compiler._run_compiler({
            "version": "1.0",
            "operations": operations,
        })
        result["method"] = "ts_compiler" if result.get("success") else "standalone_jsx"
        result["command_count"] = len(operations)
        return result

    def run_pipeline(self,
                     music_path: str,
                     clip_paths: List[str],
                     user_prompt: str = "",
                     style_preset: str = "default",
                     use_orchestrator: bool = True) -> Dict:
        """
        运行完整的端到端流程

        Args:
            music_path: 音乐文件路径
            clip_paths: 视频片段路径列表
            user_prompt: 用户提示词
            style_preset: 风格预设
            use_orchestrator: 是否使用工作流编排器

        Returns:
            完整的流程结果
        """
        pipeline_id = self._generate_pipeline_id(music_path, clip_paths)

        # 设置 correlation_id 用于关联本次 pipeline 运行的所有事件
        self._correlation_id = pipeline_id

        if self._state_machine:
            self._state_machine.start(pipeline_id)
        self._publish_pipeline_event("pipeline.start", payload={"pipeline_id": pipeline_id})

        if self._observability:
            span = self._observability.start_span("run_pipeline")

        results = {
            "pipeline_id": pipeline_id,
            "start_time": datetime.now().isoformat(),
            "music_path": music_path,
            "clip_paths": clip_paths,
            "user_prompt": user_prompt,
            "style_preset": style_preset,
            "infrastructure": {
                "config_manager": self._config_manager is not None,
                "event_bus": self._event_bus is not None,
                "state_machine": self._state_machine is not None,
                "observability": self._observability is not None,
                "orchestrator": self._orchestrator is not None,
            }
        }

        try:
            if use_orchestrator and self._orchestrator:
                self.log_info("使用 WorkflowOrchestrator 执行流程")
                execution_result = asyncio.run(self._run_with_orchestrator(
                    music_path, clip_paths, user_prompt, style_preset
                ))
                results.update(execution_result)
            else:
                self.log_info("使用传统顺序执行模式")
                results = self._run_traditional(music_path, clip_paths, user_prompt, style_preset)

        except Exception as e:
            self._publish_error("pipeline.error", error=e)
            results["error"] = str(e)
            results["end_time"] = datetime.now().isoformat()
            results["overall_success"] = False
            self.log_error(f"流程失败: {e}")
            if self._state_machine:
                self._state_machine.fail(e)

        if self._observability:
            self._observability.end_span("success" if results.get("overall_success") else "error")

        return results

    def _do_perceive(self, music_path, clip_paths):
        """orchestrator 辅助：执行感知并存储结果"""
        self._perception_result = self.perceive(music_path, clip_paths)
        return self._perception_result

    def _do_understand(self, user_prompt):
        """orchestrator 辅助：执行理解并存储结果"""
        self._understanding_result = self.understand(self._perception_result, user_prompt)
        return self._understanding_result

    def _do_plan(self):
        """orchestrator 辅助：执行规划并存储结果"""
        self._planning_result = self.plan(self._understanding_result, self._perception_result)
        return self._planning_result

    def _do_execute_ae(self):
        """orchestrator 辅助：执行 AE 命令并存储结果"""
        self._execution_result = self._execute_ae(self._planning_result)
        return self._execution_result

    # ==================================================================
    # Phase3 公共包装方法
    # ==================================================================

    def compose_style_effects(self, style_name: str, layer_name: str = "layer_001",
                              intensity: float = 1.0) -> Dict:
        """组合风格效果"""
        if not self.effect_composer:
            raise RuntimeError("EffectComposer 未加载")
        return self.effect_composer.compose(style_name, intensity=intensity, layer_name=layer_name)

    def recommend_styles(self, keywords: List[str], limit: int = 5) -> List[Dict]:
        """推荐风格"""
        if not self.effect_composer:
            return []
        return self.effect_composer.recommend_by_keywords(keywords, limit)

    def orchestrate_beat_show(self, layer_name: str, bpm: float = 120.0,
                              duration: float = 5.0, style: str = "energetic",
                              structure_template: str = "short_hook") -> Dict:
        """编排节拍秀"""
        from beat_orchestrator import BeatOrchestrator
        orchestrator = BeatOrchestrator(bpm=bpm)
        return orchestrator.generate_full_beat_show(layer_name, duration, style, structure_template)

    def orchestrate_scenes(self, scenes: List[Dict], transition_type: str = "crossfade",
                           transition_duration: float = 0.5) -> Dict:
        """多场景编排"""
        from scene_orchestrator import SceneOrchestrator, Scene, Transition
        orch = SceneOrchestrator()
        for s in scenes:
            orch.add_scene(Scene(name=s["name"], duration=s["duration"]))
        transitions = orch.generate_transitions(transition_type, transition_duration)
        timeline = orch.generate_timeline()
        return {
            "scene_count": len(orch.scenes),
            "total_duration": sum(s.duration for s in orch.scenes),
            "timeline": timeline,
            "transitions": [
                {"from_scene": t.from_scene, "to_scene": t.to_scene,
                 "type": t.type, "duration": t.duration, "start_time": t.start_time}
                for t in transitions
            ],
        }

    def apply_camera_move(self, layer_name: str, move_type: str = "push",
                          duration: float = 2.0, start_scale: float = 100.0,
                          end_scale: float = 120.0) -> List[Dict]:
        """应用摄像机运动"""
        from scene_orchestrator import SceneOrchestrator, Scene, CameraMove
        orch = SceneOrchestrator()
        scene = Scene(name="cam", duration=duration, layer_name=layer_name)
        move = CameraMove(type=move_type, duration=duration,
                          start_scale=start_scale, end_scale=end_scale)
        return orch.apply_camera_move(scene, move, layer_name)

    def run_with_feedback(self, user_input: str, intent_type: str,
                          execute_fn, expected: Dict,
                          base_confidence: float = 0.5) -> Dict:
        """带反馈循环的执行"""
        from feedback_loop_manager import FeedbackLoopManager
        manager = self.feedback_manager or FeedbackLoopManager()

        # 执行
        exec_result = execute_fn()
        success = exec_result.get("success", False)
        actual = exec_result.get("result", exec_result)

        # 记录执行
        record = manager.record_execution(
            user_input=user_input,
            intent_type=intent_type,
            success=success,
            expected=expected,
            actual=actual if success else None,
            error_message="" if success else exec_result.get("error", ""),
        )

        # 验证参数
        verification = manager.verify_parameters(expected, actual if success else None)

        # 失败时建议恢复
        suggestion = None
        if not success or not verification.passed:
            suggestion = manager.suggest_recovery(
                getattr(record, "error_code", "UNKNOWN"),
                {"expected": expected, "actual": actual},
            )

        return {
            "success": success,
            "record": record,
            "verification": verification,
            "suggestion": suggestion,
        }

    def orchestrate_full(self, perception: Dict, understanding: Dict,
                         layer_name: str = "main_layer") -> Dict:
        """全流程编排（效果 + 关键帧）"""
        style = understanding.get("style", "cinematic")
        bpm = perception.get("audio", {}).get("bpm", 120)
        duration = perception.get("audio", {}).get("duration", 5.0)

        # 组合风格效果
        effects = []
        try:
            if self.effect_composer:
                composed = self.effect_composer.compose(style, intensity=1.0, layer_name=layer_name)
                effects = composed.get("effects", [])
        except Exception:
            effects = []

        # 生成节拍关键帧
        keyframes = []
        try:
            from beat_orchestrator import BeatOrchestrator
            beat_orch = BeatOrchestrator(bpm=bpm)
            beat_show = beat_orch.generate_full_beat_show(layer_name, duration, style="energetic")
            keyframes = beat_show.get("keyframes", [])
        except Exception:
            pass

        return {
            "style": style,
            "bpm": bpm,
            "duration": duration,
            "effects": effects,
            "keyframes": keyframes,
            "effect_count": len(effects),
            "keyframe_count": len(keyframes),
        }

    # ==================================================================
    # Phase4 公共包装方法
    # ==================================================================

    def parse_nlu(self, text: str) -> Dict:
        """NLU 解析"""
        import dataclasses
        if not self.nlu_parser:
            raise RuntimeError("NLUParser 未加载")
        intent = self.nlu_parser.parse(text)
        return {
            "intent": intent.type,
            "confidence": intent.confidence,
            "slots": dataclasses.asdict(intent.slots) if intent.slots else {},
        }

    def parse_effect_description(self, text: str, intent_type: str = None) -> Dict:
        """效果描述解析"""
        import dataclasses
        if not self.effect_description_parser:
            raise RuntimeError("EffectDescriptionParser 未加载")
        desc = self.effect_description_parser.parse(text, intent_type)
        return dataclasses.asdict(desc)

    def generate_clarification(self, intent: Dict) -> Dict:
        """生成澄清问题"""
        from nlu_parser import Intent, IntentSlots
        if not self.clarification_engine:
            raise RuntimeError("ClarificationEngine 未加载")

        # dict → Intent 对象
        intent_obj = Intent(
            type=intent.get("intent", "UNKNOWN"),
            confidence=intent.get("confidence", 0.0),
            slots=IntentSlots(**intent.get("slots", {})) if intent.get("slots") else IntentSlots(),
            rawInput=intent.get("rawInput", ""),
        )

        needs = self.clarification_engine.needs_clarification(intent_obj)
        questions = self.clarification_engine.generate_questions(intent_obj)

        return {
            "needs_clarification": needs,
            "questions": [
                {"text": q.question, "slot": q.slot,
                 "options": q.options, "required": q.required}
                for q in questions
            ] if questions else [],
        }

    def optimize_parameters(self, effect_name: str, style_name: str = None,
                            intensity: float = 0.5, **kwargs) -> Dict:
        """参数优化"""
        from parameter_optimizer import ParameterContext
        if not self.parameter_optimizer:
            raise RuntimeError("ParameterOptimizer 未加载")

        ctx = ParameterContext(
            effect_name=effect_name,
            style_name=style_name,
            intensity=intensity,
            **{k: v for k, v in kwargs.items() if hasattr(ParameterContext, k)},
        )
        result = self.parameter_optimizer.optimize(ctx)
        return {
            "effect_name": result.effect_name,
            "settings": result.settings,
            "confidence": result.confidence,
        }

    def nlu_to_effect(self, text: str) -> Dict:
        """NLU → 效果一站式转换"""
        # 1. NLU 解析
        nlu_result = self.parse_nlu(text)

        # 2. 澄清判断
        clarification = self.generate_clarification(nlu_result)

        # 3. 如果不需要澄清，优化参数
        parameters = {}
        if not clarification["needs_clarification"]:
            slots = nlu_result.get("slots", {})
            effect_name = slots.get("effectName", "")
            if effect_name:
                try:
                    parameters = self.optimize_parameters(
                        effect_name=effect_name,
                        style_name=slots.get("styleName"),
                        intensity=0.5,
                    )
                except Exception:
                    parameters = {"effect_name": "", "settings": {}, "confidence": 0.0}

        return {
            "needs_clarification": clarification["needs_clarification"],
            "intent": nlu_result,
            "parameters": parameters,
        }

    async def _run_with_orchestrator(
        self, music_path: str, clip_paths: List[str], user_prompt: str, style_preset: str
    ) -> Dict:
        """使用工作流编排器执行流程"""
        self._perception_result = None
        self._understanding_result = None
        self._planning_result = None
        self._execution_result = None
        self._feedback_result = None

        funcs = {
            "perceive": lambda **kw: self._do_perceive(music_path, clip_paths),
            "understand": lambda **kw: self._do_understand(user_prompt),
            "plan": lambda **kw: self._do_plan(),
            "execute_silhouette": lambda **kw: self._execute_silhouette(self._planning_result),
            "silhouette_fallback": lambda **kw: self._silhouette_fallback(),
            "compile": lambda **kw: self.compile_planning_to_jsx(self._planning_result),
            "execute_ae": lambda **kw: self._do_execute_ae(),
            "feedback": lambda **kw: self.feedback(
                self._perception_result, self._understanding_result,
                self._planning_result, self._execution_result
            ),
        }

        self._orchestrator.build_default_pipeline(funcs)

        context = await self._orchestrator.run()

        results = {
            "pipeline_id": context.workflow_id,
            "status": context.status.name,
            "progress": context.progress,
            "start_time": datetime.fromtimestamp(context.start_time).isoformat() if context.start_time else "",
            "end_time": datetime.fromtimestamp(context.end_time).isoformat() if context.end_time else "",
            "total_duration": (context.end_time - context.start_time) if context.start_time and context.end_time else 0,
            "overall_success": context.status == "COMPLETED",
        }

        if context.tasks.get("perception"):
            self._perception_result = context.tasks["perception"].result
            results["perception"] = self._perception_result

        if context.tasks.get("understanding"):
            self._understanding_result = context.tasks["understanding"].result
            results["understanding"] = self._understanding_result

        if context.tasks.get("planning"):
            self._planning_result = context.tasks["planning"].result
            results["planning"] = self._planning_result

        if context.tasks.get("ae_execute"):
            self._execution_result = context.tasks["ae_execute"].result
            results["execution"] = self._execution_result

        if context.tasks.get("feedback"):
            self._feedback_result = context.tasks["feedback"].result
            results["feedback"] = self._feedback_result

        return results

    def _run_traditional(
        self, music_path: str, clip_paths: List[str], user_prompt: str, style_preset: str
    ) -> Dict:
        """传统顺序执行模式"""
        self.log_info("="*70)
        self.log_info("🎬 AE AI Agent 端到端流程")
        self.log_info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log_info("="*70)

        results = {
            "start_time": datetime.now().isoformat(),
            "music_path": music_path,
            "clip_paths": clip_paths,
            "user_prompt": user_prompt,
            "style_preset": style_preset
        }

        try:
            self.log_info("📡 Layer 1: 感知层 - 音视频分析")
            perception_result = self.perceive(music_path, clip_paths)
            results["perception"] = perception_result
            self.log_info("  ✓ 感知层完成")

            self.log_info("🧠 Layer 2: 理解层 - 语义理解与意图推理")
            understanding_result = self.understand(perception_result, user_prompt)
            results["understanding"] = understanding_result
            self.log_info(f"  ✓ 意图识别: {understanding_result.intent}")
            self.log_info(f"  ✓ 情绪推断: {understanding_result.mood} ({understanding_result.mood_score:.2f})")
            self.log_info(f"  ✓ 风格选择: {understanding_result.style}")

            self.log_info("📋 Layer 3: 规划层 - 任务分解与步骤规划")
            planning_result = self.plan(understanding_result, perception_result)
            results["planning"] = planning_result
            self.log_info(f"  ✓ 生成 {len(planning_result.layers)} 个图层")
            self.log_info(f"  ✓ 应用 {len(planning_result.effects)} 个效果")
            self.log_info(f"  ✓ 设置 {len(planning_result.keyframes)} 个关键帧")

            self.log_info("🎮 Layer 4: 执行层 - AE执行引擎")
            execution_result = self.execute(planning_result)
            results["execution"] = execution_result
            self.log_info(f"  ✓ 执行完成: {'成功' if execution_result.success else '失败'}")

            self.log_info("🔄 Layer 5: 反馈层 - 结果评估与学习")
            feedback_result = self.feedback(perception_result, understanding_result,
                                            planning_result, execution_result)
            results["feedback"] = feedback_result
            self.log_info(f"  ✓ 置信度: {feedback_result.confidence:.2f}")
            self.log_info(f"  ✓ 评分: {feedback_result.rating:.2f}")

            results["end_time"] = datetime.now().isoformat()
            results["total_duration"] = (datetime.fromisoformat(results["end_time"]) -
                                       datetime.fromisoformat(results["start_time"])).total_seconds()
            results["overall_success"] = execution_result.success

            self.log_info("="*70)
            self.log_info(f"🎉 流程完成! 总耗时: {results['total_duration']:.2f}秒")
            self.log_info("="*70)

        except Exception as e:
            results["error"] = str(e)
            results["end_time"] = datetime.now().isoformat()
            results["overall_success"] = False
            self.log_error(f"流程失败: {e}")

        return results

    def perceive(self, music_path: str, clip_paths: List[str]) -> PerceptionResult:
        perception = PerceptionResult()

        if self._state_machine:
            self._state_machine.phase_perception_done()
        self._publish_pipeline_event("phase.perception.start")

        obs_start = time.time()
        has_obs = self._observability is not None
        if has_obs:
            self._observability.start_span("perceive")
            self._observability.logger.info(
                f"开始感知层处理: clips={len(clip_paths)}"
            )

        try:
            if self.audio_analyzer and os.path.exists(music_path):
                self.log_info("  ├─ 分析音频...")
                audio_result = self.audio_analyzer.analyze_audio(music_path)
                if audio_result["success"]:
                    perception.audio_analysis = audio_result
                    perception.music_features = audio_result["features"]
                    self.log_info(f"    ✓ BPM: {audio_result['features']['bpm']}, 情绪: {audio_result['features']['mood']}")
                else:
                    self.log_error(f"    ✗ 音频分析失败: {audio_result['error']}")

            if self.video_analyzer:
                self.log_info("  ├─ 分析视频片段...")
                clip_features = self._analyze_clips_parallel(clip_paths)
                perception.clip_features = clip_features

            # Phase 2 感知层增强：媒体元数据 + 镜头分割 + librosa 深度音频分析
            # 这些调用是"增强"而非"替代"，失败时降级为 warning，不影响主流程
            self._enhance_perception_with_phase2(
                perception, music_path, clip_paths
            )

            # Topaz Video AI 画质增强预处理
            # 失败时降级为原始路径，不影响主流程
            self._enhance_with_topaz(perception, clip_paths)

            # DaVinci Resolve 专业调色增强
            # 失败时降级为原始路径，不影响主流程
            if self.resolve_enabled and self.resolve_preset:
                self._enhance_with_resolve_color(perception, clip_paths)

            if has_obs:
                self._metrics.histogram("pipeline.perceive.duration",
                                       time.time() - obs_start,
                                       clip_count=len(clip_paths))
                self._metrics.gauge("pipeline.perceive.clip_count",
                                   len(perception.clip_features or []))
                self._metrics.increment("pipeline.perceive.count")

            self._publish_pipeline_event("phase.perception.completed")

            if has_obs:
                self._observability.end_span("success")
        except Exception as e:
            if has_obs:
                self._observability.end_span("error")
                self._metrics.increment("pipeline.perceive.errors", error=type(e).__name__)
            raise

        return perception

    def _analyze_clips_parallel(self, clip_paths, max_workers: int = None):
        valid_paths = [(p, os.path.exists(p)) for p in clip_paths]
        existing = [p for p, exists in valid_paths if exists]
        missing = [p for p, exists in valid_paths if not exists]

        for p in missing:
            self.log_warning(f"    ✗ {os.path.basename(p)}: 文件不存在")

        if not existing:
            return []

        if len(existing) == 1:
            clip_path = existing[0]
            video_result = self.video_analyzer.analyze_video(clip_path)
            if video_result["success"]:
                self.log_info(f"    ✓ {os.path.basename(clip_path)}: 时长 {video_result.get('duration', 0):.1f}s")
                return [video_result]
            self.log_error(f"    ✗ {os.path.basename(clip_path)}: 分析失败")
            return []

        import concurrent.futures
        if max_workers is None:
            max_workers = min(len(existing), (os.cpu_count() or 4))

        results_by_path = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.video_analyzer.analyze_video, p): p
                for p in existing
            }
            for future in concurrent.futures.as_completed(future_to_path):
                clip_path = future_to_path[future]
                try:
                    video_result = future.result()
                    results_by_path[clip_path] = video_result
                    if video_result["success"]:
                        self.log_info(f"    ✓ {os.path.basename(clip_path)}: 时长 {video_result.get('duration', 0):.1f}s")
                    else:
                        self.log_error(f"    ✗ {os.path.basename(clip_path)}: 分析失败")
                except Exception as e:
                    self.log_error(f"    ✗ {os.path.basename(clip_path)}: 异常 {e}")
                    results_by_path[clip_path] = {"success": False, "error": str(e)}

        return [results_by_path[p] for p in existing if results_by_path.get(p, {}).get("success")]

    # ------------------------------------------------------------------
    # Phase 2 感知层增强
    # ------------------------------------------------------------------

    def _enhance_perception_with_phase2(
        self,
        perception: PerceptionResult,
        music_path: str,
        clip_paths: List[str],
    ) -> None:
        """Phase 2 感知层增强：媒体元数据 + 镜头分割 + librosa 深度音频分析

        本方法为"增强"而非"替代"：
        - 失败时仅记录 warning，不抛异常，不中断主流程
        - 成功时将增强结果追加到 perception 的扩展字段中
          （scene_segments / librosa_audio_analysis / media_infos）
        - 当对应模块未加载时（依赖未安装）静默跳过

        Args:
            perception: 待增强的 PerceptionResult（原地修改）
            music_path: 音乐路径
            clip_paths: 片段路径列表
        """
        # 1. 媒体元数据（每个 clip 的 duration/分辨率/编码等）
        if self.media_preprocessor and clip_paths:
            try:
                media_infos = []
                for path in clip_paths:
                    if not os.path.exists(path):
                        continue
                    info = self.media_preprocessor.get_info(path)
                    if info.success:
                        media_infos.append(info.to_dict())
                if media_infos:
                    # 追加到 perception 的扩展字段
                    if not hasattr(perception, "media_infos"):
                        # PerceptionResult 是 dataclass，直接 setattr 即可
                        setattr(perception, "media_infos", media_infos)
                    else:
                        perception.media_infos = media_infos
                    self.log_info(f"    ✓ Phase2 增强: {len(media_infos)} 个片段元数据")
            except Exception as e:
                self.log_warning(f"媒体元数据增强失败: {e}")

        # 2. 镜头分割（对每个 clip 调用 SceneDetector）
        if self.scene_detector and clip_paths:
            try:
                all_segments = []
                for path in clip_paths:
                    if not os.path.exists(path):
                        continue
                    scene_result = self.scene_detector.detect(path)
                    if scene_result.success and scene_result.segments:
                        all_segments.append({
                            "video_path": path,
                            "scene_count": scene_result.scene_count,
                            "total_duration": scene_result.total_duration,
                            "fps": scene_result.fps,
                            "segments": [s.to_dict() for s in scene_result.segments],
                        })
                if all_segments:
                    setattr(perception, "scene_segments", all_segments)
                    total_scenes = sum(s["scene_count"] for s in all_segments)
                    self.log_info(f"    ✓ Phase2 增强: 镜头分割 {len(all_segments)} 个视频，"
                          f"共 {total_scenes} 个镜头")
            except Exception as e:
                self.log_warning(f"镜头分割增强失败: {e}")

        # 3. librosa 深度音频分析（替代或补充 EnhancedAudioAnalyzer）
        # 仅在 EnhancedAudioAnalyzer 未成功时调用，避免重复分析
        if (self.librosa_audio_analyzer
                and music_path
                and os.path.exists(music_path)
                and not perception.music_features):
            try:
                audio_result = self.librosa_audio_analyzer.analyze(music_path)
                if audio_result.success:
                    # 用 librosa 输出填充 music_features，与 EnhancedAudioAnalyzer 兼容
                    perception.music_features = audio_result.to_music_features()
                    perception.audio_analysis = {
                        "success": True,
                        "features": perception.music_features,
                        "source": "librosa",
                    }
                    self.log_info(f"    ✓ Phase2 增强: librosa BPM={audio_result.bpm:.1f}, "
                          f"beats={len(audio_result.beats)}, mood={audio_result.mood}")
            except Exception as e:
                self.log_warning(f"librosa 音频分析增强失败: {e}")

    def _enhance_with_topaz(
        self, perception: PerceptionResult, clip_paths: List[str],
        preset: str = None, output_dir: str = None
    ) -> List[str]:
        """Topaz 画质增强预处理

        对输入视频进行画质增强（超分/降噪/补帧），返回增强后的视频路径列表。
        失败时返回原始路径，不中断主流程。

        Args:
            perception: 感知结果对象，用于存储增强记录（原地修改）
            clip_paths: 原始视频片段路径列表
            preset: 使用的 Topaz 预设名称，为 None 时使用 self.topaz_preset
            output_dir: 输出目录，为 None 时使用默认输出目录

        Returns:
            增强后的视频路径列表（与输入长度一致，失败的项保留原路径）
        """
        if self.topaz_enhancer is None or not self.topaz_enabled:
            return clip_paths

        if not clip_paths:
            return clip_paths

        preset = preset or self.topaz_preset
        enhanced_results = []
        enhanced_paths = []

        try:
            self.log_info(f"  ├─ Topaz 画质增强 (preset={preset})...")

            for idx, clip_path in enumerate(clip_paths):
                try:
                    if not os.path.exists(clip_path):
                        self.log_warning(f"    ✗ Topaz 跳过不存在的文件: {clip_path}")
                        enhanced_paths.append(clip_path)
                        continue

                    result = self.topaz_enhancer.enhance_video(
                        input_path=clip_path,
                    )

                    if result and result.success:
                        output_path = result.output_path
                        enhanced_paths.append(output_path)
                        enhanced_results.append({
                            "index": idx,
                            "original_path": clip_path,
                            "enhanced_path": output_path,
                            "preset": preset,
                            "success": True,
                            "original_size": result.original_size,
                            "output_size": result.output_size,
                            "original_fps": result.original_fps,
                            "output_fps": result.output_fps,
                            "duration": result.duration,
                        })
                        self.log_info(f"    ✓ Topaz 增强完成: {os.path.basename(clip_path)}")
                    else:
                        enhanced_paths.append(clip_path)
                        enhanced_results.append({
                            "index": idx,
                            "original_path": clip_path,
                            "enhanced_path": clip_path,
                            "preset": preset,
                            "success": False,
                            "error": result.error if result else "增强失败",
                        })
                        self.log_warning(f"    ✗ Topaz 增强失败: {os.path.basename(clip_path)}")

                except Exception as e:
                    enhanced_paths.append(clip_path)
                    enhanced_results.append({
                        "index": idx,
                        "original_path": clip_path,
                        "enhanced_path": clip_path,
                        "preset": preset,
                        "success": False,
                        "error": str(e),
                    })
                    self.log_warning(f"    ✗ Topaz 增强异常 [{os.path.basename(clip_path)}]: {e}")

            if enhanced_results:
                if perception.topaz_enhanced is None:
                    perception.topaz_enhanced = []
                perception.topaz_enhanced.extend(enhanced_results)

                success_count = sum(1 for r in enhanced_results if r.get("success"))
                self.log_info(f"    ✓ Topaz 增强完成: {success_count}/{len(enhanced_results)} 个片段成功")

        except Exception as e:
            self.log_warning(f"Topaz 画质增强预处理失败: {e}")
            return clip_paths

        return enhanced_paths

    def _enhance_with_resolve_color(
        self, perception: PerceptionResult, clip_paths: List[str],
        preset: str = None
    ) -> List[str]:
        """DaVinci Resolve 专业调色增强

        对输入视频进行 DaVinci Resolve 调色处理，返回调色后的视频路径列表。
        失败时返回原始路径，不中断主流程。

        Args:
            perception: 感知结果对象，用于存储调色记录（原地修改）
            clip_paths: 原始视频片段路径列表
            preset: 使用的 Resolve 调色预设名称，为 None 时使用 self.resolve_preset

        Returns:
            调色后的视频路径列表（与输入长度一致，失败的项保留原路径）
        """
        if self.resolve_colorist is None or not self.resolve_enabled:
            return clip_paths

        if not clip_paths:
            return clip_paths

        preset = preset or self.resolve_preset
        graded_results = []
        graded_paths = []

        try:
            self.log_info(f"  ├─ DaVinci Resolve 调色 (preset={preset})...")

            for idx, clip_path in enumerate(clip_paths):
                try:
                    if not os.path.exists(clip_path):
                        self.log_warning(f"    ✗ Resolve 跳过不存在的文件: {clip_path}")
                        graded_paths.append(clip_path)
                        continue

                    from davinci_resolve_integration import create_config_from_preset
                    config = create_config_from_preset(preset)
                    config.input_path = clip_path
                    result = self.resolve_colorist.color_grade(
                        input_path=clip_path,
                        config=config,
                    )

                    if result and result.success:
                        output_path = result.output_path
                        graded_paths.append(output_path)
                        graded_results.append({
                            "index": idx,
                            "original_path": clip_path,
                            "graded_path": output_path,
                            "preset": preset,
                            "success": True,
                            "color_space": getattr(result, "color_space", ""),
                            "lut_applied": getattr(result, "lut_applied", ""),
                            "duration": getattr(result, "duration", 0),
                        })
                        self.log_info(f"    ✓ Resolve 调色完成: {os.path.basename(clip_path)}")
                    else:
                        graded_paths.append(clip_path)
                        graded_results.append({
                            "index": idx,
                            "original_path": clip_path,
                            "graded_path": clip_path,
                            "preset": preset,
                            "success": False,
                            "error": result.error if result else "调色失败",
                        })
                        self.log_warning(f"    ✗ Resolve 调色失败: {os.path.basename(clip_path)}")

                except Exception as e:
                    graded_paths.append(clip_path)
                    graded_results.append({
                        "index": idx,
                        "original_path": clip_path,
                        "graded_path": clip_path,
                        "preset": preset,
                        "success": False,
                        "error": str(e),
                    })
                    self.log_warning(f"    ✗ Resolve 调色异常 [{os.path.basename(clip_path)}]: {e}")

            if graded_results:
                if perception.color_graded is None:
                    perception.color_graded = []
                perception.color_graded.extend(graded_results)

                success_count = sum(1 for r in graded_results if r.get("success"))
                self.log_info(f"    ✓ Resolve 调色完成: {success_count}/{len(graded_results)} 个片段成功")

        except Exception as e:
            self.log_warning(f"DaVinci Resolve 调色预处理失败: {e}")
            return clip_paths

        return graded_paths

    def _enhance_with_ai_video(
        self, understanding: UnderstandingResult, perception: PerceptionResult
    ) -> List[str]:
        """AI 视频生成增强（RunwayML / Pika）

        根据理解结果中的 AI 视频生成请求，调用 AI 视频生成器生成视频。
        失败时返回空列表，不中断主流程。

        Args:
            understanding: 理解结果对象，包含 AI 生成请求参数
            perception: 感知结果对象，用于存储生成记录（原地修改）

        Returns:
            生成的视频路径列表
        """
        if self.ai_video_generator is None or not self.ai_video_enabled:
            return []

        if not understanding.ai_video_requested:
            return []

        generated_paths = []
        generated_results = []

        try:
            self.log_info(f"  ├─ AI 视频生成 (provider={understanding.ai_provider or 'auto'})...")

            prompt = understanding.ai_prompt or understanding.scene_description or ""
            if not prompt:
                self.log_warning("    ✗ AI 视频生成跳过：未提供提示词")
                return []

            result = self.ai_video_generator.generate_video(
                prompt=prompt,
                provider=understanding.ai_provider or None,
            )

            if result and result.success:
                output_path = result.output_path
                generated_paths.append(output_path)
                generated_results.append({
                    "prompt": prompt,
                    "provider": understanding.ai_provider or getattr(result, "provider", ""),
                    "output_path": output_path,
                    "success": True,
                    "duration": getattr(result, "duration", 0),
                    "resolution": getattr(result, "resolution", ""),
                    "model": getattr(result, "model", ""),
                })
                self.log_info(f"    ✓ AI 视频生成完成: {os.path.basename(output_path)}")
            else:
                generated_results.append({
                    "prompt": prompt,
                    "provider": understanding.ai_provider or "",
                    "output_path": "",
                    "success": False,
                    "error": result.error if result else "生成失败",
                })
                self.log_warning("    ✗ AI 视频生成失败")

            if generated_results:
                if perception.ai_generated is None:
                    perception.ai_generated = []
                perception.ai_generated.extend(generated_results)

        except Exception as e:
            self.log_warning(f"AI 视频生成失败: {e}")
            return []

        return generated_paths

    def _enhance_with_blender(
        self, understanding: UnderstandingResult, perception: PerceptionResult
    ) -> List[Dict]:
        """Blender 3D 场景生成增强

        根据理解结果中的 Blender 场景请求，生成 Blender 3D 场景配置。
        失败时返回空列表，不中断主流程。

        Args:
            understanding: 理解结果对象，包含 Blender 场景请求参数
            perception: 感知结果对象，用于存储场景记录（原地修改）

        Returns:
            生成的 Blender 场景配置列表
        """
        if self.blender_integrator is None or not self.blender_enabled:
            return []

        if not understanding.blender_requested:
            return []

        scene_configs = []

        try:
            self.log_info(f"  ├─ Blender 3D 场景生成 (type={understanding.blender_scene_type or 'default'})...")

            scene_type = understanding.blender_scene_type or "default"
            result = self.blender_integrator.create_scene(
                scene_type=scene_type,
                description=understanding.scene_description or "",
            )

            if result and result.success:
                scene_config = result.scene_config
                scene_configs.append(scene_config)

                if perception.blender_scenes is None:
                    perception.blender_scenes = []
                perception.blender_scenes.append({
                    "scene_type": scene_type,
                    "scene_config": scene_config,
                    "success": True,
                    "output_path": getattr(result, "output_path", ""),
                    "poly_count": getattr(result, "poly_count", 0),
                    "materials": getattr(result, "materials", []),
                })
                self.log_info(f"    ✓ Blender 场景生成完成: {scene_type}")
            else:
                if perception.blender_scenes is None:
                    perception.blender_scenes = []
                perception.blender_scenes.append({
                    "scene_type": scene_type,
                    "scene_config": {},
                    "success": False,
                    "error": result.error if result else "场景生成失败",
                })
                self.log_warning(f"    ✗ Blender 场景生成失败: {scene_type}")

        except Exception as e:
            self.log_warning(f"Blender 3D 场景生成失败: {e}")
            return []

        return scene_configs

    def understand(self, perception: PerceptionResult, user_prompt: str = "") -> UnderstandingResult:
        understanding = UnderstandingResult()

        if self._state_machine:
            self._state_machine.phase_understanding_done()
        self._publish_pipeline_event("phase.understanding.start")

        obs_start = time.time()
        has_obs = self._observability is not None
        if has_obs:
            self._observability.start_span("understand")
            self._observability.logger.info(f"开始理解层处理: prompt={user_prompt[:50]}...")

        try:
            if perception.music_features:
                understanding.mood = perception.music_features.get("mood", "neutral")
                understanding.mood_score = perception.music_features.get("mood_score", 0.5)
                understanding.tempo = perception.music_features.get("tempo", 100)
                understanding.duration = perception.music_features.get("duration", 0)

            understanding.keywords = self._extract_keywords(user_prompt)
            understanding.intent = self._infer_intent(user_prompt, understanding.mood)
            understanding.style = self._determine_style(user_prompt, understanding.mood)
            understanding.scene_description = self._generate_scene_description(perception)

            self._enhance_with_nlu_parser(understanding, user_prompt)
            self._enhance_with_clarification(understanding, user_prompt)
            self._enhance_with_effect_description(understanding, user_prompt)

            self._detect_silhouette_intent(understanding, user_prompt)

            self._detect_external_tool_intents(understanding, user_prompt)

            # Phase4 完整管线编排：AIScheduler + vocabulary_map 增强
            self._enhance_with_vocabulary_map(understanding, user_prompt)
            self._enhance_with_ai_scheduler(understanding, user_prompt)

            self._enhance_understanding_with_llm(understanding, user_prompt, perception)

            if has_obs:
                self._metrics.histogram("pipeline.understand.duration",
                                       time.time() - obs_start,
                                       intent=understanding.intent)
                self._metrics.increment("pipeline.understand.count",
                                       intent=understanding.intent,
                                       route=understanding.route_type)

            self._publish_pipeline_event("phase.understanding.completed", payload={
                "intent": understanding.intent,
                "route_type": understanding.route_type,
                "silhouette_task": understanding.silhouette_task,
            })

            if has_obs:
                self._observability.end_span("success")
        except Exception as e:
            if has_obs:
                self._observability.end_span("error")
                self._metrics.increment("pipeline.understand.errors", error=type(e).__name__)
            raise

        return understanding

    def _enhance_with_nlu_parser(
        self,
        understanding: "UnderstandingResult",
        user_prompt: str,
    ) -> None:
        """
        使用 Phase4 NLUParser 进行精细意图识别
        - 调用 parse_enhanced()（含 LLM 增强 + 记忆缓存 + 自动降级）
        - 将精细意图（ADD_EFFECT/CREATE_ANIM/ADJUST_PARAM 等）写入 understanding
        - 不覆盖 understanding.intent（粗粒度业务意图保留）
        - 失败时不影响主流程
        """
        nlu_parser = getattr(self, "nlu_parser", None)
        if not nlu_parser or not user_prompt.strip():
            return

        try:
            intent = nlu_parser.parse_enhanced(user_prompt)
            if not intent:
                return

            understanding.nlu_intent_type = intent.type or ""
            understanding.nlu_confidence = float(intent.confidence or 0.0)
            understanding.nlu_matched_pattern = intent.matchedPattern or ""

            # 合并槽位（过滤 None）
            slots = {}
            if intent.slots:
                slots = {
                    k: v for k, v in intent.slots.__dict__.items()
                    if v is not None and v != ""
                }
                understanding.nlu_slots = slots

            # 高置信度精细意图可反哺粗粒度 intent
            if intent.type == "ADD_EFFECT":
                understanding.intent = "video_editing"
            elif intent.type == "STYLE_COMBO":
                understanding.intent = "short_reel"

            self.log_info(
                f"NLU 精细意图: type={intent.type}, "
                f"confidence={intent.confidence:.2f}, "
                f"slots={list(slots.keys())}"
            )
        except Exception as e:
            self.log_warning(f"NLU Parser 增强失败（不影响主流程）: {e}")

    def _enhance_with_clarification(
        self,
        understanding: "UnderstandingResult",
        user_prompt: str,
    ) -> None:
        """
        ClarificationEngine 澄清引擎增强
        - 当 NLU 置信度低于阈值时，生成澄清问题
        - 将澄清问题列表存入 understanding 供前端交互使用
        - 不阻塞主流程，仅作为增强信息
        """
        if not getattr(self, "clarification_engine", None) or not user_prompt.strip():
            return

        try:
            from nlu_parser import Intent, IntentType, IntentSlots

            intent = Intent(
                type=understanding.nlu_intent_type or IntentType.UNKNOWN,
                confidence=understanding.nlu_confidence or 0.0,
                slots=IntentSlots(
                    effectName=understanding.nlu_slots.get("effectName"),
                    targetLayer=understanding.nlu_slots.get("targetLayer"),
                    styleName=understanding.nlu_slots.get("styleName"),
                    color=understanding.nlu_slots.get("color"),
                ),
                rawInput=user_prompt,
                matchedPattern=understanding.nlu_matched_pattern or "",
            )

            if self.clarification_engine.needs_clarification(intent):
                questions = self.clarification_engine.generate_questions(intent)
                if questions:
                    understanding.clarification_questions = [
                        {
                            "question": q.question,
                            "slot": q.slot,
                            "options": q.options,
                            "required": q.required,
                        }
                        for q in questions
                    ]
                    self.log_info(
                        f"ClarificationEngine: 生成 {len(questions)} 个澄清问题"
                    )

                    gap_analysis = self.clarification_engine.analyze_confidence_gap(intent)
                    if gap_analysis:
                        understanding.confidence_gaps = gap_analysis
        except Exception as e:
            self.log_warning(f"ClarificationEngine 增强失败（不影响主流程）: {e}")

    def _enhance_with_effect_description(
        self,
        understanding: "UnderstandingResult",
        user_prompt: str,
    ) -> None:
        """
        EffectDescriptionParser 效果描述解析增强
        - 从用户输入中提取效果关键词、颜色、强度、时间信息
        - 将解析结果存入 understanding 供 plan() 阶段使用
        """
        if not getattr(self, "effect_description_parser", None) or not user_prompt.strip():
            return

        try:
            parser = self.effect_description_parser
            description = parser.parse(user_prompt, intent_type=understanding.nlu_intent_type)

            understanding.effect_keywords = [
                ref.name for ref in description.effectKeywords
            ]
            understanding.color_keywords = [
                {"keyword": ref.keyword, "rgb": ref.rgb, "temperature": ref.temperature}
                for ref in description.colorKeywords
            ]
            understanding.intensity_keywords = [
                ref.value for ref in description.intensityKeywords
            ]
            understanding.temporal_keywords = [
                ref.position for ref in description.temporalKeywords
            ]

            if understanding.effect_keywords:
                self.log_info(
                    f"EffectDescriptionParser: 提取 {len(understanding.effect_keywords)} 个效果关键词"
                )
            if understanding.color_keywords:
                self.log_info(
                    f"EffectDescriptionParser: 提取 {len(understanding.color_keywords)} 个颜色关键词"
                )

            if not understanding.style and description.styleKeywords:
                style_ref = description.styleKeywords[0]
                understanding.style = style_ref.name.lower()
                self.log_info(f"EffectDescriptionParser: 识别风格 {understanding.style}")

            # 使用 intent_to_report 生成 AnalysisReport（Phase4→Phase3 衔接）
            try:
                from intent_to_report import intent_to_report
                from nlu_parser import Intent, IntentSlots
                # 构造 Intent 对象（intent_to_report 需要 .confidence 属性）
                intent_obj = Intent(
                    type=understanding.nlu_intent_type or "UNKNOWN",
                    confidence=understanding.confidence,
                    slots=IntentSlots(),
                    rawInput=user_prompt,
                )
                report = intent_to_report(
                    intent=intent_obj,
                    description=description,
                    context={"duration": str(understanding.duration)},
                )
                understanding.analysis_report = report
                self.log_info(
                    f"intent_to_report: 生成 AnalysisReport "
                    f"({len(report.effects)} 效果, "
                    f"{len(report.parameters)} 参数, "
                    f"{len(report.keyframes)} 关键帧)"
                )
            except Exception as e2:
                self.log_warning(f"intent_to_report 生成失败（不影响主流程）: {e2}")

        except Exception as e:
            self.log_warning(f"EffectDescriptionParser 增强失败（不影响主流程）: {e}")

    def _enhance_understanding_with_llm(
        self,
        understanding: "UnderstandingResult",
        user_prompt: str,
        perception: "PerceptionResult",
    ) -> None:
        """LLM 增强理解层 — 当 LLM 网关可用时补充语义理解"""
        if not self._llm_gateway or not self._llm_gateway.is_available():
            return

        # 检查记忆系统中是否有相似任务的经验
        if self._memory_store:
            experiences = self._memory_store.get_experience(
                category="understanding",
                task_keyword=user_prompt[:50],
                limit=3,
            )
            if experiences:
                best = experiences[0]
                self.log_info(f"找到历史经验: {best.key} (置信度={best.confidence:.2f})")
                # 如果历史经验置信度高，可以直接复用
                if best.confidence > 0.7:
                    understanding.confidence = best.confidence
                    return

        # 异步调用 LLM 增强（但 understand 是同步方法，用 asyncio.run）
        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中，创建任务但不阻塞
            # 这里不阻塞主流程，LLM 增强失败不影响本地解析
            return
        except RuntimeError:
            pass

        # 同步调用 LLM
        try:
            result = asyncio.run(self._llm_gateway.chat_with_routing(
                message=f"分析以下视频创作意图，返回意图类别和情绪:\n{user_prompt}",
                task_type=__import__('core.llm_gateway', fromlist=['TaskType']).TaskType.INTENT_CLASSIFICATION,
                system_prompt="你是视频创作意图分析专家。返回JSON格式: {intent, mood, confidence}",
            ))

            if result.success and result.content:
                # LLM 增强成功，记录到记忆系统
                if self._memory_store:
                    self._memory_store.remember(
                        category="understanding",
                        key=user_prompt[:50],
                        content={
                            "intent": understanding.intent,
                            "mood": understanding.mood,
                            "llm_response": result.content[:200],
                            "model": result.model,
                        },
                        tags=[understanding.intent, understanding.mood],
                        confidence=0.6,
                    )

                self.log_info(f"LLM 增强完成: model={result.model}, tokens={result.tokens_input + result.tokens_output}")
        except Exception as e:
            self.log_warning(f"LLM 增强失败（不影响主流程）: {e}")

    def _extract_keywords(self, prompt: str) -> List[str]:
        keywords = []
        style_keywords = ["cinematic", "fast", "slow", "epic", "minimal", "vibrant",
                          "muted", "dramatic", "playful", "elegant", "dark", "bright"]
        mood_keywords = ["happy", "sad", "excited", "calm", "romantic", "mysterious", "epic"]

        for kw in style_keywords:
            if kw.lower() in prompt.lower():
                keywords.append(kw)
        for kw in mood_keywords:
            if kw.lower() in prompt.lower():
                keywords.append(kw)

        return keywords

    def _infer_intent(self, prompt: str, mood: str) -> str:
        if not prompt or prompt.strip() == "":
            return ""
        if "edit" in prompt.lower() or "剪辑" in prompt:
            return "video_editing"
        elif "promo" in prompt.lower() or "宣传" in prompt:
            return "promotional_video"
        elif "story" in prompt.lower() or "故事" in prompt:
            return "storytelling"
        elif "reel" in prompt.lower() or "短片" in prompt:
            return "short_reel"
        elif "tiktok" in prompt.lower() or "抖音" in prompt:
            return "social_media"
        elif mood in ["epic", "excited"]:
            return "high_energy_video"
        elif mood in ["calm", "romantic"]:
            return "relaxing_video"
        else:
            return "general_video"

    def _determine_style(self, prompt: str, mood: str) -> str:
        if "cinematic" in prompt.lower():
            return "cinematic"
        elif "fast" in prompt.lower() or "quick" in prompt.lower():
            return "fast_cut"
        elif "slow" in prompt.lower() or "smooth" in prompt.lower():
            return "slow_motion"
        elif "minimal" in prompt.lower():
            return "minimalist"
        elif "vibrant" in prompt.lower() or "colorful" in prompt.lower():
            return "vibrant"
        elif "dark" in prompt.lower() or "mysterious" in prompt.lower():
            return "dark_moody"
        elif mood == "epic":
            return "cinematic"
        elif mood == "excited":
            return "fast_cut"
        elif mood == "calm":
            return "slow_motion"
        elif mood == "romantic":
            return "soft_dreamy"
        else:
            return "default"

    def _generate_scene_description(self, perception: PerceptionResult) -> str:
        if not perception.clip_features:
            return "未知场景"

        descriptions = []
        for clip in perception.clip_features:
            scene_info = clip.get("scene_analysis", {})
            color_info = clip.get("color_analysis", {})

            scene_type = scene_info.get("dominant_scene_type", "unknown")
            main_color = color_info.get("dominant_color", "")

            desc_parts = []
            if scene_type:
                desc_parts.append(scene_type)
            if main_color:
                desc_parts.append(main_color)

            if desc_parts:
                descriptions.append(" + ".join(desc_parts))

        return "; ".join(descriptions)

    def plan(self, understanding: UnderstandingResult, perception: PerceptionResult) -> PlanningResult:
        plan = PlanningResult()

        if self._state_machine:
            self._state_machine.phase_planning_done()
        self._publish_pipeline_event("phase.planning.start")

        obs_start = time.time()
        has_obs = self._observability is not None
        if has_obs:
            self._observability.start_span("plan")
            self._observability.logger.info(f"开始规划层处理: style={understanding.style}")

        try:
            plan.silhouette_operations = self._generate_silhouette_operations(understanding, perception)

            plan.composition = self._create_composition(understanding)
            plan.layers = self._create_layers(understanding, perception)

            plan.effects = self._create_effects(understanding, plan.layers)
            plan.effects = self._enhance_with_style_templates(plan.effects, understanding, plan.layers)
            plan.effects = self._optimize_effects(plan.effects, understanding)

            plan.keyframes = self._create_keyframes(understanding, perception, plan.layers)
            plan.transitions = self._create_transitions(understanding, plan.layers)

            # 转场落地：将抽象转场转换为实际 AE 效果/关键帧/图层操作
            self._apply_transitions_to_plan(plan, understanding)

            plan = self._enhance_with_scene_orchestrator(plan, understanding, perception)

            # 3D 场景增强：根据风格开启 3D 图层、创建摄像机与灯光
            self._enhance_with_3d_scene(plan, understanding)

            # 多图层编排增强：轨道遮罩 / 混合模式 / 父子关系 / 调整图层
            self._enhance_with_layer_orchestration(plan, understanding)

            # 木偶风格化增强：如果是木偶风格，生成完整木偶效果
            self._enhance_with_puppet_style(plan, understanding)

            plan.timeline = self._build_timeline(plan.layers, plan.transitions)
            plan.execution_order = self._determine_execution_order()

            # Phase5 学习反馈增强：使用 LearningLoop 积累的经验优化效果参数
            self._enhance_with_learning_loop(plan, understanding)

            # Phase3 增强：使用 effect_name_map 解析效果显示名→matchName，
            # 并通过 report_to_ops 生成编译器操作列表
            self._enhance_with_phase3_modules(plan, understanding)

            if has_obs:
                self._metrics.histogram("pipeline.plan.duration",
                                       time.time() - obs_start,
                                       style=understanding.style)
                self._metrics.gauge("pipeline.plan.layer_count", len(plan.layers),
                                    style=understanding.style)
                self._metrics.gauge("pipeline.plan.effect_count", len(plan.effects),
                                    style=understanding.style)
                self._metrics.gauge("pipeline.plan.keyframe_count", len(plan.keyframes),
                                    style=understanding.style)
                self._metrics.increment("pipeline.plan.count",
                                       style=understanding.style,
                                       route=understanding.route_type)

            self._publish_pipeline_event("phase.planning.completed", payload={
                "layer_count": len(plan.layers),
                "effect_count": len(plan.effects),
                "silhouette_ops": len(plan.silhouette_operations),
            })

            if has_obs:
                self._observability.end_span("success")
        except Exception as e:
            if has_obs:
                self._observability.end_span("error")
                self._metrics.increment("pipeline.plan.errors", error=type(e).__name__)
            raise

        return plan

    _SILHOUETTE_KW = [
        r"扣|抠|遮罩|蒙版|mask|roto",
        r"跟踪|追踪|track",
        r"修|擦|paint|修复|去除|擦除",
        r"silhouette",
        r"木偶|puppet|cartoon|toon|定格|stop.motion|提线|marionette|皮影|黏土|clay|布偶|毛绒|陶瓷|瓷偶|木质|木头",
    ]
    _AE_EFFECT_KW = [
        r"发光|辉光|glow|霓虹",
        r"模糊|blur|高斯",
        r"粒子|particle",
        r"噪波|noise|分形",
        r"渐变|ramp|gradient",
        r"调色|color|lut|色调",
        r"扭曲|distort|变形|warp",
        r"阴影|shadow|投影",
        r"动画|anim|弹入|淡入|滑入|缩放|旋转",
        r"风格化|stylize|风格转换|卡通化|漫画",
    ]
    _HYBRID_CONNECTORS = [
        r"然后", r"之后再?", r"接着", r"完后", r"最后",
        r"然后加", r"再加", r"同时加", r"并加",
        r"后加", r"后添加", r"后做",
    ]

    def _enhance_with_vocabulary_map(
        self, understanding: "UnderstandingResult", user_prompt: str
    ) -> None:
        """使用 vocabulary_map 进行增强词汇扫描

        vocabulary_map 提供 13 类 72 条目的同义词覆盖，
        比 effect_description_parser 的基础 VOCAB_MAP 更丰富。
        扫描结果补充到 understanding.vocab_scan_enhanced 中，
        供后续 plan() 阶段参考，不覆盖已有字段。
        """
        vm = getattr(self, "_vocabulary_map", None)
        if not vm or not user_prompt.strip():
            return

        try:
            vocab_refs = vm.scan_vocab(user_prompt)
            color_refs = vm.scan_colors(user_prompt)
            intensity_refs = vm.scan_intensity(user_prompt)
            temporal_refs = vm.scan_temporal(user_prompt)

            understanding.vocab_scan_enhanced = {
                "vocab_refs": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "matchedKeyword": r.matchedKeyword,
                        "suggestedEffect": r.suggestedEffect,
                        "confidence": r.confidence,
                    }
                    for r in vocab_refs
                ],
                "color_refs": [
                    {
                        "keyword": c.keyword,
                        "rgb": c.rgb,
                        "temperature": c.temperature,
                    }
                    for c in color_refs
                ],
                "intensity_refs": [
                    {
                        "keyword": i.keyword,
                        "value": i.value,
                        "level": vm.get_intensity_level(i.value)
                            if vm.get_intensity_details(i.keyword)
                            else "moderate",
                    }
                    for i in intensity_refs
                ],
                "temporal_refs": [
                    {
                        "keyword": t.keyword,
                        "position": t.position,
                    }
                    for t in temporal_refs
                ],
                "stats": vm.get_vocab_stats(),
            }

            # 如果基础 effect_keywords 为空，用增强扫描结果补充
            if not understanding.effect_keywords and vocab_refs:
                understanding.effect_keywords = [
                    r.name for r in vocab_refs
                ]

            self.log_info(
                f"vocabulary_map 增强扫描: "
                f"{len(vocab_refs)} 词汇, "
                f"{len(color_refs)} 颜色, "
                f"{len(intensity_refs)} 强度, "
                f"{len(temporal_refs)} 时间"
            )
        except Exception as e:
            self.log_warning(f"vocabulary_map 增强扫描失败: {e}")

    def _enhance_with_ai_scheduler(
        self, understanding: "UnderstandingResult", user_prompt: str
    ) -> None:
        """使用 AIScheduler 进行完整 Phase4 管线编排

        AIScheduler 聚合 NLUParser + EffectDescriptionParser +
        ParameterMapper + EffectGeneratorFactory + ParameterOptimizer +
        IntentRouter，提供统一的调度 API。

        本方法调用 run_nlu_pipeline() 获取统一 NLU 结果，
        并存储到 understanding.scheduler_result 中供 plan() 阶段使用。
        不覆盖 understand() 中已有字段（NLU/EffectDescription 等），
        仅作为增强信息补充。
        """
        scheduler = getattr(self, "ai_scheduler", None)
        if not scheduler or not user_prompt.strip():
            return

        try:
            nlu_result = scheduler.run_nlu_pipeline(user_prompt)

            # 存储完整调度结果供 plan() 阶段使用
            understanding.scheduler_result = {
                "intent_type": nlu_result.intent.type,
                "intent_confidence": nlu_result.intent.confidence,
                "understood": nlu_result.understood,
                "needs_clarification": nlu_result.needs_clarification,
                "clarification_question": nlu_result.clarification_question,
                "clarification_options": nlu_result.clarification_options,
                "effect_description": {
                    "effect_keywords": [
                        r.id for r in
                        nlu_result.effect_description.effectKeywords
                    ],
                    "style_keywords": [
                        r.id for r in
                        nlu_result.effect_description.styleKeywords
                    ],
                    "intensity_keywords": [
                        i.keyword for i in
                        nlu_result.effect_description.intensityKeywords
                    ],
                    "color_keywords": [
                        c.keyword for c in
                        nlu_result.effect_description.colorKeywords
                    ],
                },
            }

            # 如果 NLU 精细意图为空，用 scheduler 结果补充
            if not understanding.nlu_intent_type:
                understanding.nlu_intent_type = nlu_result.intent.type or ""
                understanding.nlu_confidence = float(
                    nlu_result.intent.confidence or 0.0
                )

            # 更新综合置信度
            if nlu_result.understood:
                understanding.confidence = max(
                    understanding.confidence,
                    nlu_result.intent.confidence,
                )

            self.log_info(
                f"AIScheduler 管线编排: "
                f"type={nlu_result.intent.type}, "
                f"understood={nlu_result.understood}, "
                f"needs_clarification={nlu_result.needs_clarification}"
            )
        except Exception as e:
            self.log_warning(f"AIScheduler 管线编排失败: {e}")

    def _enhance_with_learning_loop(
        self, plan: "PlanningResult",
        understanding: "UnderstandingResult"
    ) -> None:
        """Phase5 学习反馈增强：使用 LearningLoop 积累的经验优化效果参数

        1. 遍历 plan.effects，对每个效果查询 LearningLoop 中的参数模板
        2. 如果找到高置信度模板，用其参数值增强当前效果参数
        3. 使用默认值表补充缺失的参数
        4. 记录使用的模板，供后续学习统计
        """
        learning_loop = getattr(self, "_learning_loop", None)
        if not learning_loop or not plan.effects:
            return

        try:
            case_store = learning_loop.get_case_store()
            default_store = learning_loop.get_default_value_store()
            enhanced_count = 0

            for effect in plan.effects:
                match_name = effect.get("matchName", "")
                effect_name = effect.get("effectName", "")
                key = match_name or effect_name
                if not key:
                    continue

                # 1. 查询参数模板（取使用频率最高的）
                templates = case_store.find_templates(key)
                best_template = None
                if templates:
                    # 优先选成功次数多、使用频率高的模板
                    best_template = max(
                        templates,
                        key=lambda t: (
                            getattr(t, "success_count", 0),
                            getattr(t, "usage_count", 0),
                        )
                    )

                # 2. 应用模板参数
                if best_template and best_template.parameters:
                    tpl_params = best_template.parameters
                    if isinstance(tpl_params, dict):
                        # 只增强尚未设置的参数，避免覆盖用户明确指定的
                        current_params = effect.get("parameters", {})
                        for pk, pv in tpl_params.items():
                            if pk not in current_params or current_params[pk] is None:
                                current_params[pk] = pv
                        effect["parameters"] = current_params
                        effect["_enhanced_by_template"] = best_template.id
                        effect["_template_source"] = getattr(best_template, "source", "learning")
                        enhanced_count += 1
                        # 增加模板使用计数
                        case_store.increment_usage(best_template.id)

                # 3. 用默认值表补充缺失参数
                current_params = effect.get("parameters", {})
                if default_store:
                    # 尝试一些常见参数
                    common_params = ["amount", "intensity", "radius", "opacity", "scale"]
                    for pk in common_params:
                        if pk not in current_params:
                            dv = default_store.get(key, pk)
                            if dv is not None:
                                current_params[pk] = dv

            if enhanced_count > 0:
                self.log_info(
                    f"LearningLoop 增强: {enhanced_count}/{len(plan.effects)} 个效果 "
                    f"使用了历史学习参数"
                )
                understanding.learning_loop_enhanced = {
                    "enhanced_count": enhanced_count,
                    "total_effects": len(plan.effects),
                }
        except Exception as e:
            self.log_warning(f"LearningLoop 增强失败: {e}")

    def _enhance_with_phase3_modules(
        self, plan: "PlanningResult",
        understanding: "UnderstandingResult"
    ) -> None:
        """Phase3 增强：effect_name_map 解析 + report_to_ops 转换

        1. 使用 effect_name_map 将 plan.effects 中的 effectName 解析为
           matchName，补充到 understanding.effect_name_map_resolved
        2. 如果 understanding.analysis_report 存在，调用 report_to_ops
           生成编译器操作列表并存储到 plan.compiler_operations
        """
        # ===== 1. effect_name_map 解析 =====
        name_map = getattr(self, "_effect_name_map", None)
        if name_map and plan.effects:
            resolved = {}
            for effect in plan.effects:
                effect_name = effect.get("effectName", "")
                match_name = effect.get("matchName", "")
                if not match_name and effect_name:
                    entry = name_map.find_by_name(effect_name)
                    if entry:
                        match_name = entry.match_name
                        # 回填到 effect 字典
                        effect["matchName"] = match_name
                if effect_name or match_name:
                    resolved[effect_name] = {
                        "matchName": match_name,
                        "displayName": effect_name,
                    }
            understanding.effect_name_map_resolved = resolved

        # ===== 2. report_to_ops 转换 =====
        r2o = getattr(self, "_report_to_ops", None)
        if r2o and understanding.analysis_report is not None:
            try:
                # 从 plan.composition 获取合成名（如有）
                comp_name = "Phase3 Output"
                if plan.composition:
                    comp_name = plan.composition.get("name", comp_name)

                options = r2o.ReportToOpsOptions(
                    comp_name=comp_name,
                    comp_duration=10.0,
                    comp_frame_rate=30,
                )

                compiler_input = r2o.report_to_ops(
                    understanding.analysis_report, options
                )
                plan.compiler_operations = compiler_input.operations

                # 生成统计信息（ReportStats dataclass → dict）
                stats_obj = r2o.analyze_report(understanding.analysis_report)
                # 按操作类型计数
                ops_by_type: Dict[str, int] = {}
                for op in plan.compiler_operations:
                    op_type = op.get("op", "unknown")
                    ops_by_type[op_type] = ops_by_type.get(op_type, 0) + 1
                plan.report_stats = {
                    "total_effects": stats_obj.total_effects,
                    "mapped_effects": stats_obj.mapped_effects,
                    "unknown_effects": stats_obj.unknown_effects,
                    "total_parameters": stats_obj.total_parameters,
                    "total_keyframes": stats_obj.total_keyframes,
                    "avg_confidence": stats_obj.avg_confidence,
                    "generated_ops": len(plan.compiler_operations),
                    "ops_by_type": ops_by_type,
                }

                self.log_info(
                    f"Phase3 report_to_ops: "
                    f"生成 {len(plan.compiler_operations)} 个操作, "
                    f"类型分布={ops_by_type}"
                )
            except Exception as e:
                self.log_warning(f"Phase3 report_to_ops 转换失败: {e}")

    def _detect_silhouette_intent(self, understanding: UnderstandingResult, prompt: str) -> None:
        if not prompt:
            return

        # 优先使用 IntentRouter（支持记忆增强和降级策略）
        if getattr(self, 'intent_router', None):
            try:
                route = self.intent_router.route(prompt)
                understanding.route_type = route.type
                understanding.is_hybrid = route.type == "hybrid"
                understanding.confidence = max(
                    understanding.confidence, route.confidence
                )
                # 从路由结果提取 Silhouette 任务类型
                for op in route.silhouette_operations:
                    task_type = op.get("taskType", op.get("task_type", ""))
                    if task_type:
                        understanding.silhouette_task = task_type
                        break
                # 记录路由原因用于调试
                if not hasattr(understanding, '_route_reason'):
                    understanding._route_reason = route.reason
                self.log_info(
                    f"IntentRouter 路由结果: type={route.type}, "
                    f"confidence={route.confidence:.2f}, "
                    f"reason={route.reason}"
                )
                # 补充：木偶风格关键词检测（IntentRouter 可能未覆盖）
                import re as _re
                _puppet_pat = r"木偶|puppet|cartoon|toon|定格|stop\.motion|提线|marionette|皮影|黏土|clay|布偶|毛绒|陶瓷|瓷偶|木质|木头"
                if _re.search(_puppet_pat, prompt, _re.IGNORECASE):
                    if not understanding.style or understanding.style == "default":
                        understanding.style = "wooden_puppet"
                    if not understanding.silhouette_task:
                        understanding.silhouette_task = "puppet_roto"
                    understanding.route_type = "hybrid"
                    understanding.is_hybrid = True
                    self.log_info(
                        f"木偶风格检测(IntentRouter后): "
                        f"style={understanding.style}, "
                        f"task={understanding.silhouette_task}"
                    )
                return
            except Exception as e:
                self.log_warning(f"IntentRouter 路由失败，降级为本地规则: {e}")

        # 降级为本地规则路由
        import re

        has_sil = any(re.search(p, prompt, re.IGNORECASE) for p in self._SILHOUETTE_KW)
        has_ae = any(re.search(p, prompt, re.IGNORECASE) for p in self._AE_EFFECT_KW)
        has_conn = any(re.search(p, prompt) for p in self._HYBRID_CONNECTORS)

        if not has_sil:
            understanding.route_type = "ae_only"
            return

        if re.search(r"扣|抠|遮罩|蒙版|mask|roto", prompt, re.IGNORECASE):
            understanding.silhouette_task = "roto"
        elif re.search(r"跟踪|追踪|track", prompt, re.IGNORECASE):
            understanding.silhouette_task = "track"
        elif re.search(r"修|擦|paint|修复|去除|擦除", prompt, re.IGNORECASE):
            understanding.silhouette_task = "paint"
        elif re.search(r"木偶|puppet|cartoon|toon|定格|stop.motion|提线|marionette|皮影|黏土|clay|布偶|毛绒|陶瓷|瓷偶|木质|木头", prompt, re.IGNORECASE):
            understanding.style = "wooden_puppet"
            understanding.silhouette_task = "puppet_roto"
            understanding.route_type = "hybrid"
            understanding.is_hybrid = True
            self.log_info(
                f"木偶风格检测: 匹配木偶关键词, "
                f"style={understanding.style}, "
                f"task={understanding.silhouette_task}, "
                f"route={understanding.route_type}"
            )
            return

        if has_sil and has_ae and has_conn:
            understanding.route_type = "hybrid"
            understanding.is_hybrid = True
        else:
            understanding.route_type = "silhouette_only"

    def _detect_external_tool_intents(self, understanding: UnderstandingResult, prompt: str) -> None:
        """检测外部工具意图（DaVinci Resolve 调色 / AI 视频生成 / Blender 3D 场景）

        通过关键词匹配识别用户是否请求外部工具能力，并设置对应的理解结果字段。
        失败时不影响主流程。

        Args:
            understanding: 理解结果对象（原地修改）
            prompt: 用户输入提示词
        """
        if not prompt:
            return

        import re

        try:
            # DaVinci Resolve 调色关键词检测
            resolve_pattern = r"调色|达芬奇|resolve|电影级|胶片|调色预设"
            if re.search(resolve_pattern, prompt, re.IGNORECASE):
                understanding.needs_color_grading = True
                understanding.resolve_preset = "cinematic"
                self.log_info(
                    f"外部工具检测: DaVinci Resolve 调色 "
                    f"(preset={understanding.resolve_preset})"
                )

            # AI 视频生成关键词检测
            ai_pattern = r"ai生成|runway|pika|文生视频|图生视频"
            if re.search(ai_pattern, prompt, re.IGNORECASE):
                understanding.ai_video_requested = True
                # 识别具体提供商
                if re.search(r"runway", prompt, re.IGNORECASE):
                    understanding.ai_provider = "runway"
                elif re.search(r"pika", prompt, re.IGNORECASE):
                    understanding.ai_provider = "pika"
                # 提取 AI 生成提示词（使用场景描述作为默认）
                if not understanding.ai_prompt:
                    understanding.ai_prompt = prompt
                self.log_info(
                    f"外部工具检测: AI 视频生成 "
                    f"(provider={understanding.ai_provider or 'auto'})"
                )

            # Blender 3D 场景关键词检测
            blender_pattern = r"3d场景|blender|三维|舞台|微缩场景"
            if re.search(blender_pattern, prompt, re.IGNORECASE):
                understanding.blender_requested = True
                # 识别具体场景类型
                if re.search(r"舞台", prompt, re.IGNORECASE):
                    understanding.blender_scene_type = "stage"
                elif re.search(r"微缩", prompt, re.IGNORECASE):
                    understanding.blender_scene_type = "miniature"
                elif re.search(r"三维|3d", prompt, re.IGNORECASE):
                    understanding.blender_scene_type = "generic_3d"
                self.log_info(
                    f"外部工具检测: Blender 3D 场景 "
                    f"(type={understanding.blender_scene_type or 'default'})"
                )

        except Exception as e:
            self.log_warning(f"外部工具意图检测失败（不影响主流程）: {e}")

    def _generate_silhouette_operations(
        self, understanding: UnderstandingResult, perception: PerceptionResult
    ) -> List[Dict]:
        task = understanding.silhouette_task
        if not task:
            return []

        source_path = ""
        if perception.clip_features:
            source_path = perception.clip_features[0].get("source_path", "")

        ops: List[Dict] = []

        if task == "roto":
            ops.append({
                "command": "silhouette_roto",
                "params": {
                    "source_path": source_path,
                    "shape_type": "x-spline",
                    "tracking": "planar",
                    "tolerance": 1.0,
                    "keyframes": 5,
                    "output_format": "exr",
                },
            })
        elif task == "track":
            ops.append({
                "command": "silhouette_track",
                "params": {
                    "source_path": source_path,
                    "track_type": "planar",
                    "export_format": "ae",
                    "search_area": 21,
                    "accuracy": "medium",
                },
            })
        elif task == "paint":
            ops.append({
                "command": "silhouette_paint",
                "params": {
                    "source_path": source_path,
                    "brush_size": 25,
                    "brush_hardness": 0.5,
                    "mode": "clone",
                },
            })
        elif task in ("puppet", "puppet_roto"):
            ops.append({
                "command": "silhouette_roto",
                "params": {
                    "source_path": source_path,
                    "shape_type": "x-spline",
                    "tracking": "planar",
                    "tolerance": 0.8,
                    "keyframes": 8,
                    "output_format": "exr",
                    "preset": "hair_keying",
                },
            })
        elif task == "joint_track":
            ops.append({
                "command": "silhouette_joint_track",
                "params": {
                    "source_path": source_path,
                    "preset": "joint_track_17point",
                    "export_format": "ae",
                    "accuracy": "high",
                },
            })
        elif task == "face_track":
            ops.append({
                "command": "silhouette_face_track",
                "params": {
                    "source_path": source_path,
                    "preset": "face_track_basic",
                    "export_format": "ae",
                    "accuracy": "high",
                },
            })

        return ops

    def _create_composition(self, understanding: UnderstandingResult) -> Dict:
        return {
            "name": f"AI Generated - {understanding.style}",
            "width": 1920,
            "height": 1080,
            "duration": understanding.duration + 2,
            "frameRate": 30,
            "pixelAspectRatio": 1.0,
            "backgroundColor": [0, 0, 0]
        }

    def _create_layers(self, understanding: UnderstandingResult, perception: PerceptionResult) -> List[Dict]:
        layers = []

        if perception.music_features:
            audio_path = ""
            if perception.audio_analysis:
                audio_path = perception.audio_analysis.get("audio_path", "")
            layers.append({
                "name": "Music Track",
                "type": "audio",
                "source": audio_path,
                "startTime": 0,
                "duration": perception.music_features.get("duration", 0),
                "locked": True
            })

        if perception.clip_features and perception.music_features:
            beat_times = perception.music_features.get("beats", [])
            downbeats = perception.music_features.get("downbeats", [])

            clips = perception.clip_features.copy()
            clips = self._sort_clips_by_motion(clips, understanding.style)

            current_time = 0
            beat_index = 0

            for i, clip in enumerate(clips):
                clip_duration = (clip.get("duration")
                                 or clip.get("basic_info", {}).get("duration")
                                 or clip.get("features", {}).get("duration")
                                 or 5)
                clip_path = clip.get("video_path", clip.get("file_path", ""))

                if beat_index < len(downbeats) and downbeats[beat_index] > current_time:
                    start_time = downbeats[beat_index]
                elif beat_index < len(beat_times) and beat_times[beat_index] > current_time:
                    start_time = beat_times[beat_index]
                else:
                    start_time = current_time

                if start_time + clip_duration > perception.music_features.get("duration", 100):
                    break

                motion_level = self._classify_motion_level(clip)
                scene_type = clip.get("scene_analysis", {}).get("dominant_scene_type", "unknown")

                layers.append({
                    "name": f"Clip_{i+1}",
                    "type": "footage",
                    "source": clip_path,
                    "startTime": start_time,
                    "duration": clip_duration,
                    "motionLevel": motion_level,
                    "sceneType": scene_type,
                    "beatSync": beat_index < len(beat_times),
                    "beatIndex": beat_index
                })

                current_time = start_time + clip_duration
                beat_index += 1

        return layers

    def _sort_clips_by_motion(self, clips: List[Dict], style: str) -> List[Dict]:
        def get_motion(x):
            return (x.get("motion_analysis", {}).get("avg_motion_intensity", 0)
                    or x.get("motion_features", {}).get("avg_motion", 0)
                    or x.get("features", {}).get("avg_motion", 0))
        if style in ["fast_cut", "high_energy"]:
            return sorted(clips, key=get_motion, reverse=True)
        elif style in ["slow_motion", "relaxing"]:
            return sorted(clips, key=get_motion)
        else:
            return clips

    def _classify_motion_level(self, clip: Dict) -> str:
        motion = (clip.get("motion_analysis", {}).get("avg_motion_intensity", 0)
                  or clip.get("motion_features", {}).get("avg_motion", 0)
                  or clip.get("features", {}).get("avg_motion", 0))
        if motion > 30:
            return "high"
        elif motion > 10:
            return "medium"
        else:
            return "low"

    def _create_effects(self, understanding: UnderstandingResult, layers: List[Dict]) -> List[Dict]:
        """
        创建效果列表（结合效果知识图谱搜索 + NLU 精细意图 + 风格配方）
        优先级：NLU 精细意图 > 风格配方 > 默认效果
        """
        effects = []

        style_effects = {
            "cinematic": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": 5, "Master Lightness": -5}},
                {"effectName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 0.5}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 20, "Glow Intensity": 0.5}}
            ],
            "fast_cut": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": 10, "Master Lightness": 0}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 3, "Glow Intensity": 0.3}}
            ],
            "slow_motion": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": -5, "Master Lightness": 5}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 5, "Glow Intensity": 0.5}},
                {"effectName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 0.3}}
            ],
            "minimalist": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": -10, "Master Lightness": 5}},
                {"effectName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 0.2}}
            ],
            "vibrant": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": 30, "Master Lightness": 0}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 5, "Glow Intensity": 0.5}}
            ],
            "dark_moody": [
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": -20, "Master Lightness": -10}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 30, "Glow Intensity": 0.8}},
                {"effectName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 0.5}}
            ],
            "soft_dreamy": [
                {"effectName": "ADBE Gaussian Blur 2", "settings": {"Blurriness": 2}},
                {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 15, "Glow Intensity": 1.0}},
                {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": -5, "Master Lightness": 5}}
            ]
        }

        default_effects = [
            {"effectName": "ADBE HUE SATURATION", "settings": {"Master Saturation": 5}},
            {"effectName": "ADBE Glo2", "settings": {"Glow Radius": 10, "Glow Intensity": 0.3}}
        ]

        selected_effects = style_effects.get(understanding.style, default_effects)

        # 通过效果知识图谱搜索增强（基于 NLU 精细意图）
        selected_effects = self._enhance_effects_with_knowledge_graph(selected_effects, understanding)

        # 通过效果组合引擎增强（synergy 加成 + 冲突解决）
        selected_effects = self._enhance_with_composition_engine(selected_effects, understanding)

        # 通过效果生成器增强（智能参数生成 + 强度/颜色修饰）
        selected_effects = self._enhance_with_effect_generators(
            selected_effects, understanding
        )

        # 通过 effect_name_map 解析效果名→matchName
        effect_name_map_available = self._effect_name_map is not None

        def _resolve_effect(effect_entry: Dict) -> Dict:
            """通过 effect_name_map 解析效果名，补充 matchName"""
            result = dict(effect_entry)
            effect_name = result.get("effectName", "")
            if effect_name_map_available and effect_name:
                try:
                    from effect_name_map import find_by_name
                    entry = find_by_name(effect_name)
                    if entry:
                        # 如果原始 effectName 是 matchName 格式，保留；否则用映射表的 displayName
                        if not effect_name.startswith("ADBE"):
                            result["effectName"] = entry.display_name or effect_name
                        result["matchName"] = entry.match_name
                except Exception:
                    pass
            return result

        for layer in layers:
            if layer["type"] == "footage":
                for effect_template in selected_effects:
                    resolved = _resolve_effect(effect_template)
                    effects.append({
                        "layerName": layer["name"],
                        "effectName": resolved.get("effectName", effect_template["effectName"]),
                        "matchName": resolved.get("matchName", ""),
                        "settings": effect_template["settings"].copy()
                    })

                if layer.get("motionLevel") == "high":
                    resolved = _resolve_effect({"effectName": "ADBE Gaussian Blur 2"})
                    effects.append({
                        "layerName": layer["name"],
                        "effectName": resolved.get("effectName", "ADBE Gaussian Blur 2"),
                        "matchName": resolved.get("matchName", ""),
                        "settings": {"Blurriness": 1}
                    })

                if layer.get("sceneType") in ["close_up", "medium_shot"]:
                    resolved = _resolve_effect({"effectName": "ADBE Sharpen"})
                    effects.append({
                        "layerName": layer["name"],
                        "effectName": resolved.get("effectName", "ADBE Sharpen"),
                        "matchName": resolved.get("matchName", ""),
                        "settings": {"Sharpen Amount": 30}
                    })

        return effects

    def _enhance_effects_with_knowledge_graph(self, effects: List[Dict], understanding: UnderstandingResult) -> List[Dict]:
        """
        通过效果知识图谱搜索增强效果列表
        1. 根据 NLU 精细意图搜索匹配效果
        2. 根据风格名称推荐风格配方
        3. 合并去重，保留原有效果
        """
        try:
            from effect_knowledge_graph import search_effects_enhanced, recommend_style_enhanced

            enhanced_effects = list(effects)
            seen_effects = {e["effectName"] for e in effects}

            # 1. 根据 NLU 精细意图搜索匹配效果
            if understanding.nlu_slots.get("effectName"):
                effect_name = understanding.nlu_slots["effectName"]
                found_effects = search_effects_enhanced(effect_name)
                for effect_node in found_effects[:3]:
                    if effect_node.match_name not in seen_effects:
                        seen_effects.add(effect_node.match_name)
                        default_settings = {}
                        for param in effect_node.parameters:
                            if param.default is not None:
                                default_settings[param.name] = param.default
                        enhanced_effects.append({
                            "effectName": effect_node.match_name,
                            "settings": default_settings,
                            "_fromKnowledgeGraph": True,
                            "_confidence": effect_node.confidence,
                        })

            # 2. 根据 EffectDescriptionParser 提取的效果关键词搜索
            if understanding.effect_keywords:
                for keyword in understanding.effect_keywords[:5]:
                    found_effects = search_effects_enhanced(keyword)
                    for effect_node in found_effects[:2]:
                        if effect_node.match_name not in seen_effects:
                            seen_effects.add(effect_node.match_name)
                            default_settings = {}
                            for param in effect_node.parameters:
                                if param.default is not None:
                                    default_settings[param.name] = param.default
                            enhanced_effects.append({
                                "effectName": effect_node.match_name,
                                "settings": default_settings,
                                "_fromEffectKeywords": True,
                                "_keyword": keyword,
                                "_confidence": effect_node.confidence,
                            })

            # 3. 根据风格名称推荐风格配方
            if understanding.style:
                style_recipe = recommend_style_enhanced(understanding.style)
                if style_recipe and style_recipe.effects:
                    for style_effect in style_recipe.effects[:3]:
                        if style_effect.match_name not in seen_effects:
                            seen_effects.add(style_effect.match_name)
                            enhanced_effects.append({
                                "effectName": style_effect.match_name,
                                "settings": style_effect.settings or {},
                                "_fromStyleRecipe": True,
                                "_styleName": style_recipe.name,
                            })

            # 4. 根据颜色关键词调整效果参数
            if understanding.color_keywords:
                for effect in enhanced_effects:
                    if effect.get("effectName") == "ADBE Color Balance":
                        settings = effect["settings"]
                        for color_keyword in understanding.color_keywords:
                            temp = color_keyword.get("temperature", "")
                            rgb = color_keyword.get("rgb", [0.5, 0.5, 0.5])
                            if temp == "warm":
                                settings["Red Midtone Level"] = settings.get("Red Midtone Level", 0) + 5
                                settings["Blue Midtone Level"] = settings.get("Blue Midtone Level", 0) - 3
                            elif temp == "cool":
                                settings["Blue Midtone Level"] = settings.get("Blue Midtone Level", 0) + 5
                                settings["Red Midtone Level"] = settings.get("Red Midtone Level", 0) - 3

            if len(enhanced_effects) > len(effects):
                self.log_info(f"效果知识图谱增强: {len(effects)} -> {len(enhanced_effects)} 个效果")

            return enhanced_effects
        except ImportError:
            self.log_warning("效果知识图谱未安装，跳过增强")
            return effects
        except Exception as e:
            self.log_warning(f"效果知识图谱增强失败（不影响主流程）: {e}")
            return effects

    def _enhance_with_composition_engine(
        self, effects: List[Dict], understanding: UnderstandingResult
    ) -> List[Dict]:
        """
        使用 EffectCompositionEngine 进行智能效果组合
        - 基于关键词组合新效果（synergy 加成）
        - 检测并解决冲突（mutex 关系）
        - 记录协同关系用于反馈
        """
        if not self.effect_composition_engine:
            return effects

        try:
            engine = self.effect_composition_engine

            # 收集关键词：效果关键词 + NLU 意图关键词
            keywords = list(understanding.effect_keywords or [])
            if understanding.nlu_slots.get("effectName"):
                keywords.append(understanding.nlu_slots["effectName"])
            if understanding.style:
                keywords.append(understanding.style)

            # 1. 基于关键词组合效果（含 synergy 加成和冲突解决）
            if keywords:
                intensity = 1.0
                if understanding.intensity_keywords:
                    intensity = 1.3

                composition = engine.compose_from_keywords(
                    keywords=keywords,
                    intensity=intensity,
                    max_effects=5,
                )

                # 将组合结果中未冲突的新效果合并进来
                seen = {e.get("effectName") for e in effects}
                for comp_effect in composition.effects:
                    match_name = comp_effect.get("matchName")
                    if match_name and match_name not in seen:
                        seen.add(match_name)
                        effects.append({
                            "effectName": match_name,
                            "settings": comp_effect.get("settings", {}),
                            "_fromCompositionEngine": True,
                            "_confidence": comp_effect.get("confidence", 0.5),
                        })

                if composition.warnings:
                    for w in composition.warnings[:3]:
                        self.log_warning(f"效果组合: {w}")
                if composition.synergies:
                    self.log_info(
                        f"效果协同: {len(composition.synergies)} 组 "
                        f"(confidence={composition.confidence:.2f})"
                    )

            # 2. 对当前已有效果列表做冲突分析
            current_names = [
                e.get("effectName") for e in effects
                if e.get("effectName", "").startswith("ADBE")
            ]
            if len(current_names) >= 2:
                analysis = engine.analyze_combination(current_names)
                conflicts = analysis.get("conflicts", [])
                if conflicts:
                    removed = set()
                    for conflict in conflicts:
                        if conflict.get("strength", 0) >= 0.8:
                            removed.add(conflict.get("effect_b"))
                            self.log_warning(
                                f"冲突移除: {conflict.get('effect_b')} "
                                f"vs {conflict.get('effect_a')}"
                            )
                    if removed:
                        effects = [
                            e for e in effects
                            if e.get("effectName") not in removed
                        ]

            return effects
        except Exception as e:
            self.log_warning(f"效果组合引擎增强失败（不影响主流程）: {e}")
            return effects

    def list_available_styles(self) -> List[Dict]:
        """列出所有可用的风格预设（直接访问 STYLE_TEMPLATES）"""
        if not self._style_templates:
            return []
        return [
            {
                "name": name,
                "display_name": tpl.get("display_name", name),
                "category": tpl.get("category", ""),
                "description": tpl.get("description", ""),
                "keywords": tpl.get("keywords", []),
                "effect_count": len(tpl.get("effects", [])),
            }
            for name, tpl in self._style_templates.items()
        ]

    def get_style_template(self, style_name: str) -> Optional[Dict]:
        """获取指定风格的完整模板（直接访问 STYLE_TEMPLATES）"""
        if not self._style_templates:
            return None
        return self._style_templates.get(style_name)

    def apply_style_with_intensity(
        self, style_name: str, intensity: float = 1.0
    ) -> List[Dict]:
        """按强度系数应用风格模板，返回带强度缩放的效果列表"""
        template = self.get_style_template(style_name)
        if not template:
            return []

        intensity_range = template.get("intensity_range", [0.2, 1.5])
        clamped = max(intensity_range[0], min(intensity_range[1], intensity))

        scaled_effects = []
        for eff in template.get("effects", []):
            eff_copy = dict(eff)
            settings = dict(eff_copy.get("settings", {}))

            intensity_param = eff_copy.get("intensity_param")
            intensity_factor = eff_copy.get("intensity_factor", 1.0)
            if intensity_param and intensity_param in settings:
                base = settings[intensity_param]
                settings[intensity_param] = base * clamped * intensity_factor

            eff_copy["settings"] = settings
            eff_copy["_style"] = style_name
            eff_copy["_intensity"] = clamped
            scaled_effects.append(eff_copy)

        return scaled_effects

    def _enhance_with_effect_generators(
        self, effects: List[Dict], understanding: UnderstandingResult
    ) -> List[Dict]:
        """使用 EffectGeneratorFactory 智能生成/优化效果参数

        为已选效果提供智能参数生成，根据强度关键词和风格调整参数值。
        """
        if not getattr(self, 'effect_generator_factory', None):
            return effects

        try:
            factory = self.effect_generator_factory

            # 构建修饰词上下文
            modifiers = {
                "intensity": [
                    {"keyword": kw, "value": 1.0}
                    for kw in understanding.intensity_keywords
                ],
                "color": [],
                "temporal": [],
                "style": understanding.style or "",
            }

            # 如果有强度关键词，计算总体缩放
            if understanding.intensity_keywords:
                # 强度词越多，缩放越大
                scale = 1.0 + 0.3 * len(understanding.intensity_keywords)
                modifiers["intensity"] = [
                    {"keyword": kw, "value": scale}
                    for kw in understanding.intensity_keywords
                ]

            enhanced = []
            for eff in effects:
                match_name = eff.get("effectName", "")
                try:
                    params = factory.generate_effect_by_match_name(
                        match_name, modifiers
                    )
                    if params and params.settings:
                        # 合并生成器参数到现有设置（生成器优先）
                        merged = dict(eff.get("settings", {}))
                        merged.update(params.settings)
                        eff_copy = dict(eff)
                        eff_copy["settings"] = merged
                        eff_copy["_generator_confidence"] = params.confidence
                        enhanced.append(eff_copy)
                    else:
                        enhanced.append(eff)
                except Exception:
                    # 生成器不支持该效果，保留原参数
                    enhanced.append(eff)

            generated_count = sum(
                1 for e in enhanced if e.get("_generator_confidence")
            )
            if generated_count > 0:
                self.log_info(
                    f"效果生成器增强: {generated_count}/{len(enhanced)} "
                    f"个效果参数已优化"
                )

            return enhanced
        except Exception as e:
            self.log_warning(f"效果生成器增强失败（不影响主流程）: {e}")
            return effects

    def _enhance_with_style_templates(self, effects: List[Dict],
                                       understanding: UnderstandingResult,
                                       layers: List[Dict]) -> List[Dict]:
        """EffectComposer 风格模板增强 — 根据风格匹配补充效果"""
        if not getattr(self, "effect_composer", None) or not understanding.style:
            return effects

        try:
            composer = self.effect_composer
            style = understanding.style

            template = composer.get_template(style)
            if not template:
                recommendations = composer.recommend_by_keywords(
                    understanding.keywords[:5] if understanding.keywords else [style],
                    limit=1
                )
                if recommendations:
                    style = recommendations[0]["name"]
                    template = composer.get_template(style)
                if not template:
                    return effects

            footage_layers = [l for l in layers if l.get("type") == "footage"]
            if not footage_layers:
                return effects

            target_layer = footage_layers[0].get("name", "layer_001")

            # 根据强度关键词调整 intensity
            intensity = 0.7
            if understanding.intensity_keywords:
                intensity = 1.0

            # 直接使用 STYLE_TEMPLATES 进行强度缩放
            direct_effects = self.apply_style_with_intensity(style, intensity)
            if direct_effects:
                existing_names = {e.get("effectName") for e in effects}
                added = 0
                for eff in direct_effects:
                    eff["layerName"] = target_layer
                    if eff["effectName"] not in existing_names:
                        effects.append(eff)
                        added += 1
                if added > 0:
                    self.log_info(
                        f"风格模板增强: {style} 补充 {added} 个效果 "
                        f"(intensity={intensity:.1f})"
                    )
                return effects

            # 降级到 EffectComposer.compose
            composed = composer.compose(style, intensity=intensity, layer_name=target_layer)

            existing_names = {e.get("effectName") for e in effects}
            added = 0
            for eff in composed.get("effects", []):
                if eff["effectName"] not in existing_names:
                    effects.append(eff)
                    added += 1

            if added > 0:
                self.log_info(f"风格模板增强: {style} 补充 {added} 个效果")

            return effects
        except Exception as e:
            self.log_warning(f"风格模板增强失败（不影响主流程）: {e}")
            return effects

    def _enhance_with_scene_orchestrator(self, plan: PlanningResult,
                                          understanding: UnderstandingResult,
                                          perception: PerceptionResult) -> PlanningResult:
        """SceneOrchestrator 增强 — 生成转场关键帧和镜头运动"""
        if not getattr(self, "scene_orchestrator", None):
            return plan

        try:
            from scene_orchestrator import Scene, CameraMove, Transition as SceneTransition

            orchestrator = self.scene_orchestrator
            orchestrator.scenes = []
            orchestrator.transitions = []

            for layer in plan.layers:
                if layer.get("type") != "footage":
                    continue
                scene = Scene(
                    name=layer.get("name", "scene"),
                    duration=layer.get("duration", 5.0),
                    layer_name=layer.get("name", ""),
                )
                orchestrator.add_scene(scene)

            if len(orchestrator.scenes) >= 2:
                transition_type = "crossfade"
                if understanding.style == "fast_cut":
                    transition_type = "flash_white"
                elif understanding.style == "cinematic":
                    transition_type = "dissolve"
                elif understanding.style == "dark_moody":
                    transition_type = "blur"

                orchestrator.generate_transitions(transition_type, duration=0.5)

                transition_keyframes = orchestrator.generate_transition_keyframes()
                if transition_keyframes:
                    plan.keyframes.extend(transition_keyframes)
                    self.log_info(
                        f"SceneOrchestrator 增强: 添加 {len(transition_keyframes)} 个转场关键帧"
                    )

                if understanding.style == "cinematic" and orchestrator.scenes:
                    push_move = CameraMove(
                        type="push",
                        duration=2.0,
                        start_scale=100.0,
                        end_scale=110.0,
                    )
                    camera_kfs = orchestrator.apply_camera_move(
                        orchestrator.scenes[0], push_move
                    )
                    if camera_kfs:
                        plan.keyframes.extend(camera_kfs)
                        self.log_info(
                            f"SceneOrchestrator 增强: 添加 {len(camera_kfs)} 个镜头运动关键帧"
                        )

            return plan
        except Exception as e:
            self.log_warning(f"SceneOrchestrator 增强失败（不影响主流程）: {e}")
            return plan

    def _enhance_with_3d_scene(
        self, plan: PlanningResult, understanding: UnderstandingResult,
    ) -> None:
        """3D 场景增强 — 根据风格开启 3D 图层、创建摄像机与灯光

        通过 scene_3d_orchestrator 生成：
        - 3D 图层配置（Z 轴深度排列）
        - 摄像机图层 + 运动关键帧
        - 灯光图层
        """
        try:
            from scene_3d_orchestrator import Scene3DOrchestrator
        except ImportError:
            return

        try:
            comp_info = plan.composition or {}
            comp_width = comp_info.get("width", 1920)
            comp_height = comp_info.get("height", 1080)
            comp_duration = comp_info.get("duration", 5.0)

            orch = Scene3DOrchestrator(
                style=understanding.style or "cinematic",
                comp_width=comp_width,
                comp_height=comp_height,
            )

            result = orch.generate_scene(plan.layers, comp_duration)

            if not result.get("enable_3d"):
                return

            # 1. 标记 3D 图层
            layer_3d_map = {
                c["layer_name"]: c for c in result.get("layer_3d_configs", [])
            }
            for layer in plan.layers:
                lname = layer.get("name", "")
                if lname in layer_3d_map:
                    layer["threeD"] = True
                    layer["zPosition"] = layer_3d_map[lname].get("z_position", 0.0)

            # 2. 添加摄像机图层
            for cam in result.get("cameras", []):
                cam_layer = {
                    "name": cam["name"],
                    "type": "camera",
                    "startTime": 0.0,
                    "duration": comp_duration,
                    "threeD": True,
                    "position": cam.get("position", [comp_width/2, comp_height/2, -1000]),
                    "pointOfInterest": cam.get("pointOfInterest", [comp_width/2, comp_height/2, 0]),
                    "_3d": True,
                }
                plan.layers.append(cam_layer)

            # 3. 添加灯光图层
            for light in result.get("lights", []):
                light_layer = {
                    "name": light["name"],
                    "type": "light",
                    "light_type": light.get("light_type", "point"),
                    "startTime": 0.0,
                    "duration": comp_duration,
                    "threeD": True,
                    "position": light.get("position", [0, 0, 0]),
                    "intensity": light.get("intensity", 100),
                    "color": light.get("color", [255, 255, 255]),
                    "_3d": True,
                }
                plan.layers.append(light_layer)

            # 4. 添加 3D 关键帧
            for kf_op in result.get("keyframe_operations", []):
                keyframe_entry = {
                    "layerName": kf_op.get("layerName", ""),
                    "propertyPath": kf_op.get("propertyPath", ""),
                    "keyframes": kf_op.get("keyframes", []),
                    "_3d": True,
                }
                plan.keyframes.append(keyframe_entry)

            self.log_info(
                f"3D 场景增强: 风格={understanding.style}, "
                f"{len(result.get('layer_3d_configs', []))} 个 3D 图层, "
                f"{len(result.get('cameras', []))} 个摄像机, "
                f"{len(result.get('lights', []))} 个灯光"
            )
        except Exception as e:
            self.log_warning(f"3D 场景增强失败（不影响主流程）: {e}")

    def _enhance_with_layer_orchestration(
        self, plan: PlanningResult, understanding: UnderstandingResult,
    ) -> None:
        """多图层编排增强 — 轨道遮罩 / 混合模式 / 父子关系 / 调整图层

        通过 layer_orchestrator 自动处理图层间复杂关系：
        - 轨道遮罩：Silhouette 产出 → Track Matte
        - 混合模式：根据效果类型自动分配
        - 父子关系：3D 摄像机 → 3D 图层
        - 调整图层：全局风格效果批量应用
        """
        try:
            from layer_orchestrator import LayerOrchestrator
        except ImportError:
            return

        try:
            orch = LayerOrchestrator()
            result = orch.orchestrate(
                layers=plan.layers,
                effects=plan.effects,
                style=understanding.style or "cinematic",
                silhouette_artifacts=getattr(plan, "silhouette_artifacts", None),
            )

            # 1. 应用混合模式到图层
            blend_modes = result.get("blend_modes", {})
            for layer in plan.layers:
                lname = layer.get("name", "")
                if lname in blend_modes:
                    layer["blendMode"] = blend_modes[lname]

            # 2. 应用轨道遮罩
            track_mattes = result.get("track_mattes", [])
            for tm in track_mattes:
                for layer in plan.layers:
                    if layer.get("name") == tm["target_layer"]:
                        layer["trackMatte"] = tm
                        break

            # 3. 应用父子关系
            parents = result.get("parent_relationships", [])
            for parent_info in parents:
                for layer in plan.layers:
                    if layer.get("name") == parent_info["child"]:
                        layer["parent"] = parent_info["parent"]
                        break

            # 4. 添加调整图层
            for adj in result.get("adjustment_layers", []):
                adj_layer = {
                    "name": adj["name"],
                    "type": "adjustment",
                    "startTime": adj.get("startTime", 0.0),
                    "duration": adj.get("duration", 0.0),
                    "adjustment": True,
                    "_adjustment_layer": True,
                }
                plan.layers.append(adj_layer)
                # 调整图层的效果也加入 effects
                for eff in adj.get("effects", []):
                    plan.effects.append({
                        "layerName": adj["name"],
                        "effectName": eff.get("effectName", ""),
                        "matchName": eff.get("matchName", ""),
                        "settings": eff.get("settings", {}),
                        "_adjustment_layer": True,
                    })

            self.log_info(
                f"多图层编排: "
                f"{len(blend_modes)} 个混合模式, "
                f"{len(track_mattes)} 个轨道遮罩, "
                f"{len(parents)} 个父子关系, "
                f"{len(result.get('adjustment_layers', []))} 个调整图层"
            )
        except Exception as e:
            self.log_warning(f"多图层编排增强失败（不影响主流程）: {e}")

    def _enhance_with_puppet_style(
        self, plan: PlanningResult, understanding: UnderstandingResult,
    ) -> None:
        """木偶风格化增强 — 如果是木偶风格，生成完整木偶效果

        通过 PuppetStyleEngine 生成：
        - 材质质感效果（木质/陶瓷/布偶/黏土/金属）
        - 定格动画效果
        - 关节系统效果
        - 微缩场景效果
        """
        try:
            from puppet_style_engine import PuppetStyleEngine, PuppetStyleConfig
        except ImportError:
            return

        try:
            puppet_styles = {
                "wooden_puppet", "ceramic_puppet", "cloth_puppet",
                "clay_puppet", "metal_puppet", "stop_motion_basic",
                "marionette", "shadow_puppet",
            }

            style = understanding.style or ""
            if style not in puppet_styles:
                return

            comp_info = plan.composition or {}
            comp_width = comp_info.get("width", 1920)
            comp_height = comp_info.get("height", 1080)
            comp_duration = comp_info.get("duration", 5.0)

            intensity = getattr(understanding, "intensity", 1.0)
            if not isinstance(intensity, (int, float)):
                intensity = 1.0

            engine = PuppetStyleEngine()
            config = PuppetStyleConfig(
                style_type=style,
                intensity=float(intensity),
                comp_width=comp_width,
                comp_height=comp_height,
            )

            target_layer_name = ""
            if plan.layers:
                for layer in plan.layers:
                    if layer.get("type") == "footage":
                        target_layer_name = layer.get("name", "")
                        break
                if not target_layer_name:
                    target_layer_name = plan.layers[0].get("name", "layer_001")
            else:
                target_layer_name = "layer_001"

            result = engine.generate_style(
                config, layer_name=target_layer_name, duration=comp_duration
            )

            if result.effects:
                for eff in result.effects:
                    eff_entry = {
                        "layerName": eff.get("layer_name", target_layer_name),
                        "effectName": eff.get("effect_name", eff.get("effectName", "")),
                        "matchName": eff.get("match_name", eff.get("matchName", "")),
                        "settings": eff.get("settings", {}),
                        "_puppet_style": True,
                    }
                    plan.effects.append(eff_entry)

            if result.keyframes:
                for kf in result.keyframes:
                    kf_entry = {
                        "layerName": kf.get("layer_name", target_layer_name),
                        "propertyPath": kf.get("property_path", kf.get("propertyPath", "")),
                        "keyframes": kf.get("keyframes", []),
                        "_puppet_style": True,
                    }
                    plan.keyframes.append(kf_entry)

            if result.layers:
                for layer in result.layers:
                    layer_entry = {
                        "name": layer.get("name", layer.get("layerName", "puppet_layer")),
                        "type": layer.get("type", layer.get("layerType", "footage")),
                        "startTime": layer.get("startTime", 0.0),
                        "duration": layer.get("duration", comp_duration),
                        "_puppet_style": True,
                    }
                    for k, v in layer.items():
                        if k not in layer_entry and k not in ("name", "type", "startTime", "duration"):
                            layer_entry[k] = v
                    plan.layers.append(layer_entry)

            if result.adjustment_layers:
                for adj in result.adjustment_layers:
                    adj_layer = {
                        "name": adj.get("name", "Puppet Adjustment"),
                        "type": "adjustment",
                        "startTime": adj.get("startTime", 0.0),
                        "duration": adj.get("duration", comp_duration),
                        "adjustment": True,
                        "_puppet_style": True,
                        "_adjustment_layer": True,
                    }
                    plan.layers.append(adj_layer)
                    for eff in adj.get("effects", []):
                        plan.effects.append({
                            "layerName": adj.get("name", "Puppet Adjustment"),
                            "effectName": eff.get("effectName", ""),
                            "matchName": eff.get("matchName", ""),
                            "settings": eff.get("settings", {}),
                            "_puppet_style": True,
                            "_adjustment_layer": True,
                        })

            self.log_info(
                f"木偶风格化增强: 风格={style}, "
                f"强度={intensity:.2f}, "
                f"效果数={len(result.effects)}, "
                f"关键帧数={len(result.keyframes)}, "
                f"图层数={len(result.layers)}, "
                f"调整层数={len(result.adjustment_layers)}"
            )
        except Exception as e:
            self.log_warning(f"木偶风格化增强失败（不影响主流程）: {e}")

    def _optimize_effects(self, effects: List[Dict], understanding: UnderstandingResult) -> List[Dict]:
        """
        LLM 增强参数优化（记忆缓存 + 本地规则 + LLM 建议）
        失败时自动降级为原效果列表，不影响主流程
        """
        if not effects:
            return effects

        try:
            from parameter_optimizer import ParameterOptimizer, ParameterContext

            optimizer = ParameterOptimizer()
            optimized_effects = []
            memory_hits = 0

            for effect in effects:
                effect_name = effect.get("effectName", "")
                settings = effect.get("settings", {})
                layer_name = effect.get("layerName", "")

                ctx = ParameterContext(
                    effect_name=effect_name,
                    intensity=0.7,
                    style_name=understanding.style or "default",
                )

                result = optimizer.optimize_enhanced(ctx)

                optimized_settings = settings.copy()
                if result.settings:
                    optimized_settings.update(result.settings)

                final_confidence = result.confidence

                if self._memory_store and effect_name:
                    mem_entry = self._memory_store.recall(
                        category="effect_params",
                        key=effect_name,
                    )
                    if mem_entry and mem_entry.content.get("settings"):
                        mem_settings = mem_entry.content["settings"]
                        mem_confidence = mem_entry.confidence
                        if mem_confidence > final_confidence:
                            optimized_settings.update(mem_settings)
                            final_confidence = mem_confidence
                            memory_hits += 1

                optimized_effects.append({
                    "layerName": layer_name,
                    "effectName": result.effect_name or effect_name,
                    "settings": optimized_settings,
                    "_optimized": True,
                    "_confidence": final_confidence,
                    "_fromMemory": memory_hits > 0,
                })

            log_msg = f"效果参数优化完成: {len(optimized_effects)} 个效果"
            if memory_hits > 0:
                log_msg += f" (记忆命中: {memory_hits})"
            self.log_info(log_msg)
            return optimized_effects
        except ImportError:
            self.log_warning("参数优化器未安装，跳过优化")
            return effects
        except Exception as e:
            self.log_warning(f"效果参数优化失败（不影响主流程）: {e}")
            return effects

    _BEAT_STYLE_MAP = {
        "cinematic": "subtle",
        "fast_cut": "energetic",
        "slow_motion": "chill",
        "minimalist": "subtle",
        "vibrant": "heavy",
        "dark_moody": "heavy",
        "soft_dreamy": "chill",
    }

    _BEAT_STRUCTURE_MAP = {
        "cinematic": "pop_song",
        "fast_cut": "short_hook",
        "slow_motion": "pop_song",
        "minimalist": "short_hook",
        "vibrant": "edm_drop",
        "dark_moody": "edm_drop",
        "soft_dreamy": "pop_song",
    }

    def _create_beat_orchestrated_keyframes(
        self,
        understanding: UnderstandingResult,
        perception: PerceptionResult,
        layers: List[Dict],
    ) -> List[Dict]:
        """使用 BeatOrchestrator 生成节拍同步关键帧"""
        if not self.beat_orchestrator:
            return []

        music = perception.music_features or {}
        bpm = music.get("bpm", music.get("tempo", 120))
        fps = music.get("fps", 30)
        duration = music.get("duration", understanding.duration or 10)

        # 用实际 BPM 重配 BeatOrchestrator
        try:
            from beat_orchestrator import BeatOrchestrator
            self.beat_orchestrator = BeatOrchestrator(
                bpm=bpm, fps=fps, beats_per_measure=4
            )
        except Exception:
            pass

        beat_style = self._BEAT_STYLE_MAP.get(understanding.style, "energetic")
        structure = self._BEAT_STRUCTURE_MAP.get(understanding.style, "pop_song")

        all_keyframes = []
        for layer in layers:
            if layer["type"] != "footage":
                continue
            if not layer.get("beatSync"):
                continue

            layer_name = layer["name"]
            layer_duration = layer.get("duration", duration)

            try:
                show = self.beat_orchestrator.generate_full_beat_show(
                    layer_name=layer_name,
                    duration=layer_duration,
                    style=beat_style,
                    structure_template=structure,
                )
            except Exception as e:
                self.log_warning(f"BeatOrchestrator 生成失败: {e}")
                continue

            for kf in show.get("keyframes", []):
                prop = kf.get("propertyName", "")
                val = kf.get("value")

                # Scale/Position 需要二维数组格式
                if prop in ("Scale", "Position") and not isinstance(val, list):
                    kf["value"] = [val, val]

                all_keyframes.append(kf)

            # 节拍触发的效果关键帧也并入
            for trig in show.get("effect_triggers", []):
                all_keyframes.append(trig)

        return all_keyframes

    def _create_keyframes(self, understanding: UnderstandingResult,
                          perception: PerceptionResult, layers: List[Dict]) -> List[Dict]:
        keyframes = []

        # 优先使用 BeatOrchestrator 生成节拍同步关键帧
        beat_kfs = self._create_beat_orchestrated_keyframes(
            understanding, perception, layers
        )
        if beat_kfs:
            keyframes.extend(beat_kfs)

        if perception.music_features:
            beats = perception.music_features.get("beats", [])
            downbeats = perception.music_features.get("downbeats", [])
            energy_peaks = perception.music_features.get("energy_curve", {}).get("peaks", [])
            segments = perception.music_features.get("segments", [])

            for layer in layers:
                if layer["type"] != "footage":
                    continue

                layer_start = layer.get("startTime", 0)
                layer_duration = layer.get("duration", 5)
                layer_name = layer["name"]

                keyframes.append({
                    "layerName": layer_name,
                    "propertyName": "Opacity",
                    "time": layer_start,
                    "value": 0,
                    "easeType": "easeOut"
                })
                keyframes.append({
                    "layerName": layer_name,
                    "propertyName": "Opacity",
                    "time": layer_start + 0.3,
                    "value": 100,
                    "easeType": "easeIn"
                })

                if layer.get("beatSync") and not beat_kfs:
                    keyframes.append({
                        "layerName": layer_name,
                        "propertyName": "Scale",
                        "time": layer_start,
                        "value": [105, 105],
                        "easeType": "easeOut"
                    })
                    keyframes.append({
                        "layerName": layer_name,
                        "propertyName": "Scale",
                        "time": layer_start + 0.1,
                        "value": [100, 100],
                        "easeType": "easeIn"
                    })

                for peak in energy_peaks[:5]:
                    if isinstance(peak, dict):
                        peak_time = peak.get("time", 0)
                    else:
                        peak_time = peak
                    if layer_start <= peak_time <= layer_start + layer_duration:
                        keyframes.append({
                            "layerName": layer_name,
                            "propertyName": "Scale",
                            "time": peak_time,
                            "value": [108, 108],
                            "easeType": "easeOut"
                        })
                        keyframes.append({
                            "layerName": layer_name,
                            "propertyName": "Scale",
                            "time": peak_time + 0.15,
                            "value": [100, 100],
                            "easeType": "easeIn"
                        })

                for seg in segments:
                    seg_start = seg.get("start_time", seg.get("start", 0))
                    seg_type = seg.get("segment_type", seg.get("label", ""))
                    if layer_start <= seg_start <= layer_start + layer_duration:
                        if seg_type in ["chorus", "outro_climax"]:
                            keyframes.append({
                                "layerName": layer_name,
                                "propertyName": "Scale",
                                "time": seg_start,
                                "value": [110, 110],
                                "easeType": "easeOut"
                            })
                            keyframes.append({
                                "layerName": layer_name,
                                "propertyName": "Scale",
                                "time": seg_start + 0.2,
                                "value": [100, 100],
                                "easeType": "easeIn"
                            })

                if understanding.style == "cinematic":
                    keyframes.append({
                        "layerName": layer_name,
                        "propertyName": "Position",
                        "time": layer_start,
                        "value": [960, 540],
                        "easeType": "linear"
                    })
                    keyframes.append({
                        "layerName": layer_name,
                        "propertyName": "Position",
                        "time": layer_start + layer_duration - 0.5,
                        "value": [970, 535],
                        "easeType": "linear"
                    })
                elif understanding.style == "fast_cut":
                    for i, beat in enumerate(beats[:20]):
                        if layer_start <= beat <= layer_start + layer_duration:
                            keyframes.append({
                                "layerName": layer_name,
                                "propertyName": "Opacity",
                                "time": beat - 0.02,
                                "value": 80,
                                "easeType": "linear"
                            })
                            keyframes.append({
                                "layerName": layer_name,
                                "propertyName": "Opacity",
                                "time": beat + 0.02,
                                "value": 100,
                                "easeType": "linear"
                            })

                keyframes.append({
                    "layerName": layer_name,
                    "propertyName": "Opacity",
                    "time": layer_start + layer_duration - 0.3,
                    "value": 100,
                    "easeType": "easeIn"
                })
                keyframes.append({
                    "layerName": layer_name,
                    "propertyName": "Opacity",
                    "time": layer_start + layer_duration,
                    "value": 0,
                    "easeType": "easeOut"
                })

        return keyframes

    def _create_transitions(self, understanding: UnderstandingResult, layers: List[Dict]) -> List[Dict]:
        transitions = []

        transition_types = {
            "cinematic": "crossfade",
            "fast_cut": "hard_cut",
            "slow_motion": "dissolve",
            "minimalist": "wipe",
            "vibrant": "zoom_blur",
            "dark_moody": "fade_to_black",
            "soft_dreamy": "dreamy_dissolve"
        }

        selected_transition = transition_types.get(understanding.style, "crossfade")

        footage_layers = [l for l in layers if l["type"] == "footage"]

        for i in range(len(footage_layers) - 1):
            current_layer = footage_layers[i]
            next_layer = footage_layers[i + 1]

            overlap_time = min(0.5, current_layer["duration"] * 0.1)

            transitions.append({
                "fromLayer": current_layer["name"],
                "toLayer": next_layer["name"],
                "type": selected_transition,
                "startTime": next_layer["startTime"] - overlap_time,
                "duration": overlap_time,
                "easeType": "easeInOut"
            })

        return transitions

    def _apply_transitions_to_plan(
        self, plan: PlanningResult, understanding: UnderstandingResult,
    ) -> None:
        """将抽象转场转换为实际 AE 操作并注入 plan

        通过 transition_map 将 transitions 转换为：
        - effects：转场效果
        - keyframes：转场关键帧
        - layers：转场需要的额外图层（如 fade_to_black 的黑色 Solid 层）
        """
        if not plan.transitions:
            return

        try:
            from transition_map import transition_to_ae_ops
        except ImportError:
            self.log_warning("transition_map 不可用，跳过转场落地")
            return

        total_effects = 0
        total_keyframes = 0
        total_layers = 0

        for transition in plan.transitions:
            try:
                ops = transition_to_ae_ops(transition)
            except Exception as e:
                self.log_warning(f"转场 {transition.get('type')} 转换失败: {e}")
                continue

            for op in ops:
                op_type = op.get("op", "")
                params = op.get("params", {}) if "params" in op else op

                if op_type == "addEffect":
                    effect_entry = {
                        "layerName": params.get("layerRef", ""),
                        "effectName": params.get("effectName", "Transition"),
                        "matchName": params.get("matchName", ""),
                        "settings": params.get("settings", {}),
                        "_transition": True,
                        "_transition_type": transition.get("type", ""),
                    }
                    plan.effects.append(effect_entry)
                    total_effects += 1

                elif op_type == "setKeyframe":
                    keyframe_entry = {
                        "layerName": params.get("layerRef", ""),
                        "propertyPath": params.get("propertyPath", ""),
                        "keyframes": [
                            {
                                "time": kf.get("time", 0),
                                "value": kf.get("value", 0),
                                "ease": kf.get("ease", "linear"),
                            }
                            for kf in params.get("keyframes", [])
                        ],
                        "_transition": True,
                    }
                    plan.keyframes.append(keyframe_entry)
                    total_keyframes += len(params.get("keyframes", []))

                elif op_type == "addLayer":
                    layer_entry = {
                        "name": params.get("name", f"transition_{total_layers:03d}"),
                        "type": params.get("layerType", "solid"),
                        "source": params.get("source", ""),
                        "startTime": params.get("startTime", 0),
                        "duration": params.get("duration", 0),
                        "settings": params.get("settings", {}),
                        "_transition": True,
                    }
                    plan.layers.append(layer_entry)
                    total_layers += 1

        self.log_info(
            f"转场落地: {len(plan.transitions)} 个转场 → "
            f"{total_effects} 个效果, {total_keyframes} 个关键帧, {total_layers} 个图层"
        )

    def _build_timeline(self, layers: List[Dict], transitions: List[Dict]) -> List[Dict]:
        timeline = []

        for layer in layers:
            timeline_entry = {
                "layerName": layer["name"],
                "type": layer["type"],
                "startTime": layer["startTime"],
                "endTime": layer["startTime"] + layer["duration"],
                "duration": layer["duration"]
            }
            timeline.append(timeline_entry)

        for transition in transitions:
            timeline.append({
                "type": "transition",
                "fromLayer": transition["fromLayer"],
                "toLayer": transition["toLayer"],
                "transitionType": transition["type"],
                "startTime": transition["startTime"],
                "duration": transition["duration"]
            })

        return sorted(timeline, key=lambda x: x["startTime"])

    def _determine_execution_order(self) -> List[str]:
        return [
            "createComposition",
            "importFootage",
            "placeFootageInComp",
            "applyEffects",
            "setKeyframes",
            "addTransitions",
            "renderVideo"
        ]

    def _compiler_ops_to_commands(
        self, compiler_operations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """将 Phase3 compiler_operations 转换为 MCP 客户端可执行的命令格式

        report_to_ops 生成的操作格式：
          - op: createComp/addLayer/addEffect/setProperty/setKeyframe
          - ref/compRef/layerRef 等引用字段
          - 各操作的特定参数

        MCP 客户端命令格式：{op: str, params: Dict}
        """
        commands: List[Dict[str, Any]] = []
        ref_to_name_map: Dict[str, str] = {}  # ref -> 实际名称/索引映射

        for op_data in compiler_operations:
            op_type = op_data.get("op", "")
            params: Dict[str, Any] = {}

            if op_type == "createComp":
                params = {
                    "compName": op_data.get("name", "Comp"),
                    "width": op_data.get("width", 1920),
                    "height": op_data.get("height", 1080),
                    "frameRate": op_data.get("frameRate", 30),
                    "duration": op_data.get("duration", 5),
                    "pixelAspect": op_data.get("pixelAspect", 1),
                    "bgColor": op_data.get("bgColor", [0, 0, 0]),
                }
                ref_to_name_map[op_data.get("ref", "")] = params["compName"]
                commands.append({"op": "createComp", "params": params})

            elif op_type == "addLayer":
                comp_ref = op_data.get("compRef", "")
                comp_name = ref_to_name_map.get(comp_ref, comp_ref)
                layer_type = op_data.get("layerType", "solid")
                layer_name = op_data.get("name", "Layer")
                params = {
                    "compName": comp_name,
                    "layerType": layer_type,
                    "layerName": layer_name,
                    "duration": op_data.get("duration", 5),
                }
                if "color" in op_data:
                    params["color"] = op_data["color"]
                if "startTime" in op_data:
                    params["startTime"] = op_data["startTime"]
                ref_to_name_map[op_data.get("ref", "")] = layer_name
                commands.append({"op": "addLayer", "params": params})

            elif op_type == "addEffect":
                comp_ref = op_data.get("compRef", "")
                comp_name = ref_to_name_map.get(comp_ref, comp_ref)
                layer_ref = op_data.get("layerRef", "")
                layer_name = ref_to_name_map.get(layer_ref, layer_ref)
                match_name = op_data.get("matchName", "")
                effect_name = op_data.get("effectName", match_name)
                params = {
                    "compName": comp_name,
                    "layerName": layer_name,
                    "matchName": match_name,
                    "effectName": effect_name,
                }
                ref_to_name_map[op_data.get("ref", "")] = effect_name
                commands.append({"op": "addEffect", "params": params})

            elif op_type == "setProperty":
                comp_ref = op_data.get("compRef", "")
                comp_name = ref_to_name_map.get(comp_ref, comp_ref)
                layer_ref = op_data.get("layerRef", "")
                layer_name = ref_to_name_map.get(layer_ref, layer_ref)
                property_path = op_data.get("propertyPath", "")
                value = op_data.get("value", 0)
                params = {
                    "compName": comp_name,
                    "layerName": layer_name,
                    "propertyPath": property_path,
                    "value": value,
                }
                commands.append({"op": "setProperty", "params": params})

            elif op_type == "setKeyframe":
                comp_ref = op_data.get("compRef", "")
                comp_name = ref_to_name_map.get(comp_ref, comp_ref)
                layer_ref = op_data.get("layerRef", "")
                layer_name = ref_to_name_map.get(layer_ref, layer_ref)
                property_path = op_data.get("propertyPath", "")
                keyframes = op_data.get("keyframes", [])
                params = {
                    "compName": comp_name,
                    "layerName": layer_name,
                    "propertyPath": property_path,
                    "keyframes": keyframes,
                }
                commands.append({"op": "setKeyframes", "params": params})

            else:
                self.log_warning(f"未知的 compiler 操作类型: {op_type}，跳过")

        return commands

    def execute(self, planning: PlanningResult) -> ExecutionResult:
        result = ExecutionResult()
        result.total_steps = len(planning.execution_order) + len(planning.silhouette_operations)
        step_start = time.time()

        if self._state_machine:
            self._state_machine.phase_execution_done()
        self._publish_pipeline_event("phase.execution.start")

        obs_start = time.time()
        has_obs = self._observability is not None
        exec_error_type = "unknown"
        if has_obs:
            self._observability.start_span("execute")
            self._observability.logger.info(
                f"开始执行层处理: layers={len(planning.layers)}, "
                f"effects={len(planning.effects)}, "
                f"silhouette_ops={len(planning.silhouette_operations)}"
            )

        try:
            if planning.silhouette_operations and self.silhouette_executor:
                self._publish_pipeline_event("silhouette.start")
                if self._state_machine:
                    self._state_machine.silhouette_start()
                    self._state_machine.silhouette_routed()
                    self._state_machine.silhouette_start_process()
                self.log_info("  ├─ [Silhouette] 执行遮罩/跟踪任务...")
                sil_failed = False
                silhouette_outputs = []
                for i, op in enumerate(planning.silhouette_operations):
                    cmd_type = op.get("command", "silhouette_roto")
                    params = op.get("params", {})
                    self.log_info(f"  │   ├─ [{i+1}/{len(planning.silhouette_operations)}] {cmd_type}...")

                    sil_result = self._execute_with_retry(
                        lambda ct=cmd_type, p=params: self.silhouette_executor.execute({
                            "command": ct, "params": p
                        }),
                        max_retries=3,
                        retry_delay=2.0,
                    )

                    if sil_result.get("status") == "success":
                        result.silhouette_artifacts.append({
                            "command": cmd_type,
                            "output_file": sil_result.get("output_file", ""),
                            "status": "success"
                        })
                        self.log_info(f"  │   │   ✅ 输出: {sil_result.get('output_file', 'N/A')}")
                        # 收集 Silhouette 输出用于数据流打通
                        if sil_result.get("ae_integration_data"):
                            silhouette_outputs.append(
                                sil_result["ae_integration_data"]
                            )
                    elif sil_result.get("status") == "pending_silhouette":
                        result.silhouette_artifacts.append({
                            "command": cmd_type,
                            "status": "pending",
                            "message": sil_result.get("message", "需手动在 Silhouette 中完成")
                        })
                        self.log_info(f"  │   │   ⏳ 待 Silhouette 中手动完成")
                    elif sil_result.get("status") == "fallback":
                        result.silhouette_artifacts.append({
                            "command": cmd_type,
                            "status": "fallback",
                            "method": sil_result.get("method", "ae_native"),
                            "message": sil_result.get("message", ""),
                        })
                        self.log_warning(f"  │   │   ⚠️ 降级: {sil_result.get('message', '')}")
                        # 将 FALLBACK_MAP 中的 AE 降级操作注入 planning
                        fallback_ops = sil_result.get("ae_fallback_ops", [])
                        if fallback_ops:
                            for fb_op in fallback_ops:
                                if fb_op.get("op") == "addEffect":
                                    effect_entry = {
                                        "effectName": fb_op.get("effectName", "AE Native Fallback"),
                                        "matchName": fb_op.get("matchName", ""),
                                        "layerName": fb_op.get("layerRef", ""),
                                        "parameters": fb_op.get("settings", {}),
                                        "_fallback": True,
                                    }
                                    planning.effects.append(effect_entry)
                            self.log_info(
                                f"Silhouette 降级: 注入 {len(fallback_ops)} 个 AE 原生操作"
                            )
                        sil_failed = True
                    else:
                        self.log_error(f"  │   │   ⚠️ {sil_result.get('error', 'Unknown error')}")
                        sil_failed = True

                    result.steps_completed += 1

                # Silhouette → AE 数据流打通
                if silhouette_outputs:
                    for sil_out in silhouette_outputs:
                        planning = self._apply_silhouette_to_ae(
                            sil_out, planning
                        )
                    self.log_info(f"  │   └─ 📤 Silhouette 输出已应用到 AE 规划")

                if self._state_machine:
                    if sil_failed:
                        self._state_machine.silhouette_fallback()
                    else:
                        self._state_machine.silhouette_done()
                self._publish_pipeline_event("silhouette.completed")

            from ae_mcp_client import AECommandClient

            client = AECommandClient(signature_enabled=True)

            comp_name = planning.composition.get("name", "AI_Generated") if planning.composition else "AI_Generated"

            if self._state_machine:
                self._state_machine.ae_compile()

            # 优先使用 Phase3 compiler_operations（如果存在且非空）
            use_compiler_ops = (
                hasattr(planning, 'compiler_operations')
                and planning.compiler_operations
                and len(planning.compiler_operations) > 0
            )

            if use_compiler_ops:
                commands = self._compiler_ops_to_commands(planning.compiler_operations)
                command_source = "phase3_compiler_ops"
                self.log_info(
                    f"使用 Phase3 compiler_operations: "
                    f"{len(planning.compiler_operations)} ops -> "
                    f"{len(commands)} commands"
                )
            else:
                from ae_command_generator import AECommandGenerator
                generator = AECommandGenerator()
                commands = generator.generate_from_planning_result({
                    "composition": planning.composition,
                    "layers": planning.layers,
                    "effects": planning.effects,
                    "keyframes": planning.keyframes,
                    "transitions": planning.transitions
                })
                command_source = "ae_command_generator"

            self.log_info(f"  ├─ 生成 {len(commands)} 个 AE 命令 (来源: {command_source})")

            if self._state_machine:
                self._state_machine.ae_compiled()

            effect_execution_records = []
            import asyncio

            for i, cmd in enumerate(commands):
                op = cmd["op"]
                params = cmd["params"]

                self.log_info(f"  │   ├─ [{i+1}/{len(commands)}] {op}...")
                self._publish_pipeline_event("ae.execute", payload={"command": op})

                # 使用 FailureRecovery 支持的重试循环
                max_ae_result = None
                retry_count = 0
                current_params = params
                retry_request_id = f"ae_{op}_{i}"

                while True:
                    ae_result = client.send_command(op, current_params)
                    max_ae_result = ae_result

                    if ae_result.get("success") is not False and ae_result.get("status") != "error":
                        break  # 成功，退出重试循环

                    # 失败，尝试 FailureRecovery
                    failure_recovery = getattr(self, "_failure_recovery", None)
                    if not failure_recovery or retry_count >= 2:
                        break  # 没有恢复模块或已达重试上限，退出

                    # 构造失败信息并获取恢复动作
                    try:
                        from failure_recovery import (
                            ExecutionResult as FRExecution,
                            ExpectedParameters as FRExpected,
                            ExpectedProperty as FRProp,
                            ErrorCode,
                        )

                        error_msg = ae_result.get("message", ae_result.get("error", "Unknown"))
                        error_msg_lower = str(error_msg).lower()

                        # 推断错误码
                        error_code = ErrorCode.UNKNOWN.value
                        if "not found" in error_msg_lower or "未找到" in error_msg_lower:
                            if "effect" in error_msg_lower or "效果" in error_msg_lower:
                                error_code = ErrorCode.EFFECT_NOT_FOUND.value
                            elif "layer" in error_msg_lower or "图层" in error_msg_lower:
                                error_code = ErrorCode.LAYER_NOT_FOUND.value
                            elif "comp" in error_msg_lower or "合成" in error_msg_lower:
                                error_code = ErrorCode.COMP_NOT_FOUND.value
                            elif "property" in error_msg_lower or "属性" in error_msg_lower:
                                error_code = ErrorCode.PROPERTY_NOT_FOUND.value
                        elif "timeout" in error_msg_lower or "超时" in error_msg_lower:
                            error_code = ErrorCode.EXECUTION_TIMEOUT.value
                        elif "keyframe" in error_msg_lower or "关键帧" in error_msg_lower:
                            error_code = ErrorCode.KEYFRAME_FAILED.value
                        elif "memory" in error_msg_lower or "内存" in error_msg_lower:
                            error_code = ErrorCode.OUT_OF_MEMORY.value
                        elif "expression" in error_msg_lower or "表达式" in error_msg_lower:
                            error_code = ErrorCode.EXPRESSION_ERROR.value
                        elif "param" in error_msg_lower or "参数" in error_msg_lower:
                            error_code = ErrorCode.PARAM_OUT_OF_RANGE.value

                        # 构造 ExpectedParameters（从当前 params 提取）
                        props = []
                        match_name = current_params.get("matchName", "")
                        for pk, pv in current_params.items():
                            if pk not in ("compName", "layerName", "matchName", "effectName", "propertyPath", "keyframes"):
                                if isinstance(pv, (int, float, str, bool, list)):
                                    props.append(FRProp(name=pk, value=pv))

                        expected = FRExpected(
                            comp_name=current_params.get("compName", ""),
                            layer_index=i + 1,
                            effect_match_name=match_name or None,
                            effect_name=current_params.get("effectName", ""),
                            properties=props,
                        )

                        actual = FRExecution(
                            success=False,
                            error_code=error_code,
                            error_message=str(error_msg),
                        )

                        loop = asyncio.new_event_loop()
                        try:
                            recovery_action = loop.run_until_complete(
                                failure_recovery.handle_failure(
                                    actual, expected,
                                    request_id=retry_request_id
                                )
                            )
                        finally:
                            loop.close()

                        self.log_info(
                            f"FailureRecovery: {op} 失败 "
                            f"(error={error_code}), "
                            f"恢复动作={recovery_action.action}"
                        )

                        # 根据恢复动作调整参数并重试
                        if recovery_action.action == "retry_with_alternative":
                            # 替换效果 matchName
                            if recovery_action.alternative and "matchName" in current_params:
                                current_params = dict(current_params)
                                current_params["matchName"] = recovery_action.alternative
                                retry_count += 1
                                self.log_warning(f"  │   │   🔄 重试: 使用替代效果 {recovery_action.alternative}")
                                continue

                        elif recovery_action.action == "retry_with_adjusted_params":
                            # 调整参数值
                            if recovery_action.adjusted_params:
                                current_params = dict(current_params)
                                for adj_prop in recovery_action.adjusted_params.properties:
                                    if adj_prop.name in current_params:
                                        current_params[adj_prop.name] = adj_prop.value
                                retry_count += 1
                                self.log_warning(f"  │   │   🔄 重试: 参数已调整")
                                continue

                        elif recovery_action.action == "retry_with_longer_timeout":
                            # 延展超时（如果支持的话）
                            retry_count += 1
                            self.log_warning(f"  │   │   🔄 重试: 超时延展到 {recovery_action.timeout}ms")
                            continue

                        elif recovery_action.action == "wait_and_retry":
                            # 等待后重试
                            if recovery_action.delay:
                                import time as _t
                                _t.sleep(recovery_action.delay / 1000.0)
                            retry_count += 1
                            self.log_warning(f"  │   │   🔄 重试: 等待 {recovery_action.delay}ms 后重试")
                            continue

                        # 其他动作（ask_user/report_error）不重试
                        break

                    except Exception as rec_e:
                        self.log_warning(f"FailureRecovery 处理失败: {rec_e}")
                        break

                ae_result = max_ae_result

                if ae_result.get("success") is False or ae_result.get("status") == "error":
                    result.success = False
                    result.error_message = f"{op} failed: {ae_result.get('message', ae_result.get('error', 'Unknown'))}"
                    result.steps_completed += i + 1
                    result.execution_time = time.time() - step_start
                    if self._state_machine:
                        self._state_machine.ae_fail("execute", Exception(result.error_message))
                    if has_obs:
                        self._metrics.histogram("pipeline.execute.duration",
                                               time.time() - obs_start,
                                               success="false")
                        self._metrics.increment("pipeline.execute.errors", error=op)
                        self._observability.end_span("error")
                    self._publish_pipeline_event("phase.execution.completed", payload={
                        "success": False,
                        "output_path": "",
                    })
                    return result

                if "addEffect" in op or "setEffectParam" in op:
                    effect_execution_records.append({
                        "operation": op,
                        "params": params,
                        "timestamp": datetime.now().isoformat()
                    })

                client.clear_result()
                result.steps_completed += 1

            if self._state_machine:
                self._state_machine.ae_executed()

            self.log_info(f"  ├─ 渲染视频...")
            output_dir = self._config.get("output", {}).get("default_dir", "./output") if isinstance(self._config, dict) else "./output"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")

            render_result = client.send_command("renderComposition", {
                "compName": comp_name,
                "outputPath": output_path,
                "format": "mp4",
                "quality": "high",
                "waitForCompletion": True,
                "maxWaitMs": 300000
            })

            # 检查渲染结果：只有 status=success 才算真正成功
            render_status = render_result.get("status", "")
            if render_result.get("success") and render_status == "success":
                result.success = True
                result.output_path = output_path
                # 验证输出文件存在性（模拟环境下文件可能不存在，降级为 warning）
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    if file_size < 1000:
                        result.success = False
                        result.error_message = f"渲染输出文件过小 ({file_size} bytes)，可能已损坏"
                    else:
                        self.log_info(f"渲染完成: {output_path} ({file_size} bytes)")
                else:
                    # 文件不存在但 AE 返回 success — 可能是模拟环境
                    result.warning = f"AE 返回成功但输出文件不存在: {output_path}"
                    self.log_warning(result.warning)
                if self._state_machine and result.success:
                    self._state_machine.ae_rendered()
            elif render_status == "queued":
                # 渲染仅入队，视为部分成功
                result.success = True
                result.output_path = output_path
                result.warning = "渲染已入队但未确认完成"
                self.log_warning("渲染仅入队未等待完成")
                if self._state_machine:
                    self._state_machine.ae_rendered()
            elif render_status == "timeout":
                result.success = False
                result.error_message = f"渲染超时: {render_result.get('message', 'Unknown')}"
                if self._state_machine:
                    self._state_machine.ae_fail("render", Exception(result.error_message))
            else:
                result.success = False
                result.error_message = f"渲染失败: {render_result.get('message', render_result.get('error', 'Unknown'))}"
                if self._state_machine:
                    self._state_machine.ae_fail("render", Exception(result.error_message))

            result.steps_completed += 1
            result.execution_time = time.time() - step_start

            if self._memory_store and planning.effects:
                effect_keywords = [e.get("effectName", "") for e in planning.effects if e.get("effectName")]
                self._memory_store.remember(
                    category="execution",
                    key="effect_execution",
                    content={
                        "effects": planning.effects,
                        "execution_records": effect_execution_records,
                        "success": result.success,
                        "output_path": result.output_path,
                        "execution_time": result.execution_time
                    },
                    tags=effect_keywords,
                    confidence=0.7 if result.success else 0.3
                )

        except ImportError as e:
            result.success = False
            result.error_message = f"模块导入失败: {str(e)}"
            exec_error_type = "ImportError"
            if self._state_machine:
                self._state_machine.ae_fail("compile", e)
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            exec_error_type = type(e).__name__
            if self._state_machine:
                self._state_machine.ae_fail("execute", e)

        if has_obs:
            self._metrics.histogram("pipeline.execute.duration",
                                   time.time() - obs_start,
                                   success="true" if result.success else "false")
            self._metrics.increment("pipeline.execute.count",
                                   success="true" if result.success else "false")
            if not result.success:
                self._metrics.increment("pipeline.execute.errors",
                                       error=exec_error_type)
            self._observability.end_span("success" if result.success else "error")

        self._publish_pipeline_event("phase.execution.completed", payload={
            "success": result.success,
            "output_path": result.output_path,
        })
        return result

    def _execute_silhouette(self, planning: PlanningResult) -> Dict:
        if not planning.silhouette_operations or not self.silhouette_executor:
            return {"status": "skipped"}

        results = []
        for op in planning.silhouette_operations:
            cmd_type = op.get("command", "silhouette_roto")
            params = op.get("params", {})
            sil_result = self._execute_with_retry(
                lambda ct=cmd_type, p=params: self.silhouette_executor.execute({
                    "command": ct, "params": p
                }),
                max_retries=2,
                retry_delay=1.0,
            )
            results.append(sil_result)

        return {"status": "completed", "results": results}

    def _execute_hybrid_flow(
        self,
        planning: PlanningResult,
        user_input: str = "",
    ) -> Dict:
        """使用 HybridCoordinator 执行完整的混合流程

        流程：Silhouette → 数据转换 → AE 导入
        """
        if not self.hybrid_coordinator:
            self.log_warning("HybridCoordinator 未加载，回退到分步执行")
            sil_result = self._execute_silhouette(planning)
            return {
                "status": "fallback",
                "silhouette": sil_result,
                "data_transfer": {"status": "skipped"},
                "ae_import": {"status": "pending"},
            }

        try:
            from hybrid_coordinator import ExecutionOptions

            output_dir = "./output"
            if isinstance(self._config, dict):
                output_dir = self._config.get(
                    "output", {}
                ).get("default_dir", "./output")
            os.makedirs(output_dir, exist_ok=True)

            source_path = ""
            if planning.layers:
                for layer in planning.layers:
                    if layer.get("type") == "footage" and layer.get("sourcePath"):
                        source_path = layer["sourcePath"]
                        break

            options = ExecutionOptions(
                source_path=source_path,
                output_dir=output_dir,
                enable_fallback=True,
                max_retries=3,
                retry_delay_ms=2000,
                on_progress=self._hybrid_progress_callback,
            )

            hybrid_result = self.hybrid_coordinator.execute(
                user_input or "hybrid_task",
                options=options,
            )

            return {
                "status": hybrid_result.status,
                "phases": [
                    {
                        "phase": p.phase,
                        "status": p.status,
                        "duration_ms": p.duration_ms,
                        "outputs": p.outputs,
                        "error": p.error,
                    }
                    for p in hybrid_result.phases
                ],
                "silhouette_output": hybrid_result.silhouette_output,
                "ae_script": hybrid_result.ae_script,
                "used_fallback": hybrid_result.used_fallback,
                "total_duration_ms": hybrid_result.total_duration_ms,
            }

        except Exception as e:
            self.log_warning(f"HybridCoordinator 执行失败: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    def _hybrid_progress_callback(
        self, phase: str, progress: float, message: str
    ) -> None:
        """混合执行进度回调"""
        self._publish_pipeline_event("hybrid.progress", payload={
            "phase": phase,
            "progress": round(progress, 3),
            "message": message,
        })

    def _execute_with_retry(
        self, fn, max_retries: int = 3, retry_delay: float = 2.0
    ):
        """带重试的执行包装器"""
        last_error = None
        for i in range(max_retries):
            try:
                result = fn()
                if isinstance(result, dict) and result.get("status") in (
                    "success", "pending_silhouette",
                ):
                    return result
                if isinstance(result, dict) and result.get("status") == "error":
                    last_error = result.get("error", "Unknown error")
                    self.log_warning(
                        f"执行失败 (尝试 {i+1}/{max_retries}): "
                        f"{last_error}"
                    )
                    if i < max_retries - 1:
                        import time as _t
                        _t.sleep(retry_delay * (i + 1))
                    continue
                return result
            except Exception as e:
                last_error = e
                self.log_warning(
                    f"执行异常 (尝试 {i+1}/{max_retries}): {e}"
                )
                if i < max_retries - 1:
                    import time as _t
                    _t.sleep(retry_delay * (i + 1))

        # 所有重试耗尽后尝试降级
        self.log_warning(
            f"重试耗尽，尝试降级: {last_error}"
        )
        return self._execute_fallback(last_error)

    def _execute_fallback(self, error, task_type: str = "roto") -> Dict:
        """执行降级策略：Silhouette 不可用时回退到 AE 原生工具

        消费 intent_router.FALLBACK_MAP 生成实际的 AE 降级操作列表。
        """
        self.log_warning(f"降级执行 (task={task_type}): {error}")
        if self._state_machine:
            self._state_machine.silhouette_fallback()

        # 从 FALLBACK_MAP 获取降级操作
        fallback_ops = []
        fallback_message = "Silhouette 不可用，降级为 AE 原生工具"
        try:
            from intent_router import FALLBACK_MAP
            fallback_config = FALLBACK_MAP.get(task_type, {})
            fallback_ops = fallback_config.get("ae_fallback_ops", [])
            fallback_message = fallback_config.get("message", fallback_message)
        except ImportError:
            self.log_warning("无法导入 FALLBACK_MAP，使用空降级操作")

        return {
            "status": "fallback",
            "method": f"ae_native_{task_type}",
            "message": fallback_message,
            "ae_fallback_ops": fallback_ops,
            "original_error": str(error),
        }

    def _apply_silhouette_to_ae(
        self, silhouette_output: Dict, planning: PlanningResult
    ) -> PlanningResult:
        """将 Silhouette 输出自动应用到 AE 规划中

        数据流：Silhouette Matte/Track → AE Track Matte/Null 层
        """
        if not silhouette_output:
            return planning

        ae_integration = silhouette_output.get("aeIntegration") or \
                        silhouette_output.get("ae_integration_data", {}).get("aeIntegration")
        if not ae_integration:
            return planning

        # 1. Roto Matte → 添加 Track Matte 层
        roto_data = silhouette_output.get("roto")
        if roto_data:
            matte_path = roto_data.get("matteSequence", "")
            if matte_path:
                matte_layer = {
                    "name": "Silhouette_Matte",
                    "type": "footage",
                    "sourcePath": matte_path,
                    "startTime": 0,
                    "duration": planning.composition.get("duration", 5),
                    "opacity": 100,
                    "isMatte": True,
                }
                planning.layers.append(matte_layer)

                # 为主体视频层设置 Track Matte
                for layer in planning.layers:
                    if layer.get("type") == "footage" and not layer.get("isMatte"):
                        layer["trackMatteType"] = "alpha"
                        layer["matteLayer"] = "Silhouette_Matte"
                        break

                self.log_info(f"Silhouette Matte 已应用到 AE: {matte_path}")

        # 2. Tracking → 添加 Null 层关键帧
        tracking_data = silhouette_output.get("tracking")
        if tracking_data:
            trackers = tracking_data.get("trackers", [])
            null_name = tracking_data.get("nullObjectName", "Silhouette_Tracker")
            for tracker in trackers:
                for kf in tracker.get("keyframes", []):
                    frame = kf.get("frame", 0)
                    position = kf.get("position", [0, 0])
                    planning.keyframes.append({
                        "layerName": null_name,
                        "propertyName": "Position",
                        "time": frame / planning.composition.get("fps", 30),
                        "value": list(position),
                        "easeType": "linear",
                    })
            self.log_info(
                f"Silhouette Tracking 已应用到 AE: "
                f"{len(trackers)} trackers"
            )

        # 3. Paint → 添加修复帧层
        paint_data = silhouette_output.get("paint")
        if paint_data:
            paint_path = paint_data.get("paintedFrames", "")
            if paint_path:
                paint_layer = {
                    "name": "Silhouette_Paint",
                    "type": "footage",
                    "sourcePath": paint_path,
                    "startTime": 0,
                    "duration": planning.composition.get("duration", 5),
                    "opacity": 100,
                    "blendMode": "normal",
                }
                planning.layers.append(paint_layer)
                self.log_info(f"Silhouette Paint 已应用到 AE: {paint_path}")

        return planning

    def _silhouette_fallback(self, task_type: str = "roto") -> Dict:
        """Silhouette 降级：使用 AE 原生工具替代

        消费 intent_router.FALLBACK_MAP 生成实际的 AE 降级操作：
        - roto → ADBE Mask
        - track → ADBE Tracker
        - paint → ADBE Paint
        """
        self.log_warning(f"Silhouette 降级 (task={task_type}): 使用 AE 原生工具替代")

        fallback_ops = []
        fallback_message = f"降级到 AE 原生工具 (task={task_type})"
        try:
            from intent_router import FALLBACK_MAP
            fallback_config = FALLBACK_MAP.get(task_type, {
                "condition": "Silhouette 不可用",
                "ae_fallback_ops": [],
                "message": f"无法降级 task={task_type}，请安装 Silhouette 或手动操作",
            })
            fallback_ops = fallback_config.get("ae_fallback_ops", [])
            fallback_message = fallback_config.get("message", fallback_message)
        except ImportError:
            self.log_warning("无法导入 FALLBACK_MAP")

        return {
            "status": "fallback",
            "method": f"ae_native_{task_type}",
            "message": fallback_message,
            "ae_fallback_ops": fallback_ops,
        }

    def _execute_ae(self, planning: PlanningResult) -> ExecutionResult:
        return self.execute(planning)

    def feedback(self, perception: PerceptionResult, understanding: UnderstandingResult,
                 planning: PlanningResult, execution: ExecutionResult) -> FeedbackResult:
        feedback = FeedbackResult()

        if self._state_machine:
            self._state_machine.phase_feedback_done()
        self._publish_pipeline_event("phase.feedback.start")

        obs_start = time.time()
        has_obs = self._observability is not None
        if has_obs:
            self._observability.start_span("feedback")
            self._observability.logger.info(
                f"开始反馈层处理: success={execution.success}"
            )

        try:
            if execution.success:
                feedback.rating = self._calculate_rating(planning, execution)
                feedback.confidence = self._calculate_confidence(perception, understanding, execution)
                feedback.improvement_suggestions = self._generate_suggestions(planning, execution)
                feedback.learned_patterns = self._extract_patterns(perception, understanding, planning)

                self._log_feedback(feedback)
                self._update_confidence_cache(understanding.mood, understanding.style, feedback.confidence)
            else:
                feedback.rating = 0.0
                feedback.confidence = 0.3
                feedback.error_log = [execution.error_message]

            # FeedbackLoopManager 增强：执行记录、参数验证和恢复建议
            self._enhance_with_feedback_loop(feedback, understanding, planning, execution)

            # Phase5 增强：ResultVerifier + LearningLoop + FailureRecovery
            self._enhance_with_phase5_modules(
                feedback, understanding, planning, execution
            )

            if has_obs:
                self._metrics.histogram("pipeline.feedback.duration",
                                       time.time() - obs_start,
                                       success="true" if execution.success else "false")
                self._metrics.gauge("pipeline.feedback.rating", feedback.rating,
                                    success="true" if execution.success else "false")
                self._metrics.gauge("pipeline.feedback.confidence", feedback.confidence,
                                    success="true" if execution.success else "false")
                self._metrics.increment("pipeline.feedback.count",
                                       success="true" if execution.success else "false")

            self._publish_pipeline_event("phase.feedback.completed", payload={
                "rating": feedback.rating,
                "confidence": feedback.confidence,
            })
            self._publish_pipeline_event("pipeline.completed", payload={
                "duration": execution.execution_time,
            })

            if has_obs:
                self._observability.end_span("success")
        except Exception as e:
            if has_obs:
                self._observability.end_span("error")
                self._metrics.increment("pipeline.feedback.errors", error=type(e).__name__)
            raise

        return feedback

    def _enhance_with_feedback_loop(self, feedback: FeedbackResult,
                                     understanding: UnderstandingResult,
                                     planning: PlanningResult,
                                     execution: ExecutionResult) -> None:
        """FeedbackLoopManager 增强 — 执行记录、参数验证和恢复建议"""
        if not getattr(self, "feedback_manager", None):
            return

        try:
            fm = self.feedback_manager

            intent_type = understanding.nlu_intent_type or understanding.intent or "unknown"

            expected_params = {}
            for effect in planning.effects:
                expected_params[effect.get("effectName", "")] = effect.get("settings", {})

            record = fm.record_execution(
                user_input=" ".join(understanding.keywords) if understanding.keywords else "",
                intent_type=str(intent_type),
                success=execution.success,
                expected={"settings": expected_params},
                actual=None,
                error_message=execution.error_message or "",
                error_code="",
                base_confidence=feedback.confidence,
            )

            feedback.confidence = record.confidence_after

            if not execution.success and execution.error_message:
                error_code = "SCRIPT_ERROR"
                if "not found" in execution.error_message.lower():
                    error_code = "EFFECT_NOT_FOUND"
                elif "property" in execution.error_message.lower():
                    error_code = "PROPERTY_NOT_FOUND"
                elif "timeout" in execution.error_message.lower():
                    error_code = "TIMEOUT"

                recovery = fm.suggest_recovery(error_code)
                if recovery.get("actions"):
                    feedback.improvement_suggestions.extend(recovery["actions"])

            if len(fm.records) % 10 == 0 and len(fm.records) > 0:
                summary = fm.get_learning_summary()
                self.log_info(
                    f"反馈学习摘要: 成功率={summary['success_rate']:.1%}, "
                    f"总执行={summary['total_executions']}"
                )

            if execution.success and feedback.rating >= 0.6 and self._memory_store:
                for effect in planning.effects:
                    effect_name = effect.get("effectName", "")
                    settings = effect.get("settings", {})
                    if effect_name and settings:
                        self._memory_store.remember(
                            category="effect_params",
                            key=effect_name,
                            content={
                                "settings": settings,
                                "style": understanding.style or "",
                                "rating": feedback.rating,
                            },
                            tags=[effect_name, "params"],
                            confidence=feedback.rating,
                        )

        except Exception as e:
            self.log_warning(f"FeedbackLoopManager 增强失败（不影响主流程）: {e}")

    def _enhance_with_phase5_modules(
        self, feedback: FeedbackResult,
        understanding: UnderstandingResult,
        planning: PlanningResult,
        execution: ExecutionResult
    ) -> None:
        """Phase5 增强：ResultVerifier + LearningLoop + FailureRecovery

        1. ResultVerifier：通过 MCP 回读实际参数与预期对比
           （默认 MockMcpClient 不回读，仅记录执行成功）
        2. LearningLoop：记录执行结果触发学习
           （正向/偏差/负向三种学习策略）
        3. FailureRecovery：执行失败时生成恢复动作
           （retry_with_alternative / retry_with_adjusted_params / ...）
        """
        import asyncio

        # ===== 1. ResultVerifier 验证 =====
        verifier = getattr(self, "_result_verifier", None)
        if verifier:
            try:
                from result_verifier import (
                    ExpectedParameters as RVExpected,
                    ExecutionResult as RVExecution,
                    ExpectedProperty,
                )

                # 构造 ExpectedParameters
                properties = []
                for effect in planning.effects:
                    settings = effect.get("settings", {})
                    match_name = effect.get("matchName", "")
                    for prop_name, prop_value in settings.items():
                        properties.append(ExpectedProperty(
                            name=prop_name, value=prop_value
                        ))
                    if match_name and properties:
                        break  # 仅验证第一个效果

                expected = RVExpected(
                    comp_name=planning.composition.get("name", "Comp")
                        if planning.composition else "Comp",
                    layer_index=1,
                    effect_match_name=planning.effects[0].get(
                        "matchName", ""
                    ) if planning.effects else None,
                    effect_name=planning.effects[0].get(
                        "effectName", ""
                    ) if planning.effects else None,
                    properties=properties,
                )

                actual = RVExecution(
                    success=execution.success,
                    error_message=execution.error_message or None,
                )

                # async 调用
                loop = asyncio.new_event_loop()
                try:
                    verification = loop.run_until_complete(
                        verifier.verify(expected, actual)
                    )
                finally:
                    loop.close()

                feedback.verification_result = {
                    "passed": verification.passed,
                    "mismatches": [
                        {
                            "param": m.param,
                            "expected": str(m.expected),
                            "actual": str(m.actual),
                            "deviation": m.deviation,
                        }
                        for m in verification.mismatches
                    ],
                    "reason": verification.reason or "",
                    "deviation_score": verification.deviation_score,
                }
            except Exception as e:
                self.log_warning(f"ResultVerifier 验证失败: {e}")

        # ===== 2. LearningLoop 学习循环 =====
        learning_loop = getattr(self, "_learning_loop", None)
        if learning_loop:
            try:
                from learning_loop import (
                    ExpectedParameters as LLExpected,
                    ExecutionResult as LLExecution,
                    VerificationResult as LLVerification,
                    ExpectedProperty as LLProp,
                    UserFeedback,
                )

                # 构造 ExpectedParameters
                properties = []
                for effect in planning.effects[:1]:  # 仅第一个效果
                    settings = effect.get("settings", {})
                    for prop_name, prop_value in settings.items():
                        properties.append(LLProp(
                            name=prop_name, value=prop_value
                        ))

                expected = LLExpected(
                    comp_name=planning.composition.get("name", "Comp")
                        if planning.composition else "Comp",
                    layer_index=1,
                    effect_match_name=planning.effects[0].get(
                        "matchName", ""
                    ) if planning.effects else None,
                    effect_name=planning.effects[0].get(
                        "effectName", ""
                    ) if planning.effects else None,
                    properties=properties,
                )

                exec_result = LLExecution(
                    success=execution.success,
                    error_message=execution.error_message or None,
                )

                verification = LLVerification(
                    passed=execution.success,
                    deviation_score=0.0 if execution.success else 1.0,
                )

                # 用户反馈：根据 rating 推断
                if execution.success:
                    user_feedback = UserFeedback(
                        satisfied=feedback.rating >= 0.6,
                    )
                else:
                    user_feedback = UserFeedback(
                        satisfied=False, undone=False
                    )

                intent_type = (
                    understanding.nlu_intent_type
                    or understanding.intent or "unknown"
                )

                learning_loop.record_execution(
                    user_input=" ".join(understanding.keywords)
                        if understanding.keywords else "",
                    intent_type=str(intent_type),
                    expected=expected,
                    execution=exec_result,
                    verification=verification,
                    user_feedback=user_feedback,
                    reasoning_path=[understanding.route_type or "ae_only"],
                )

                # 获取学习度量
                metrics = learning_loop.get_metrics()
                feedback.learning_metrics = {
                    "total_executions": metrics.total_executions,
                    "success_count": metrics.success_count,
                    "failure_count": metrics.failure_count,
                    "success_rate": metrics.success_rate,
                    "average_deviation": metrics.average_deviation,
                    "learned_templates": metrics.learned_templates,
                    "confidence_adjustments": (
                        metrics.confidence_adjustments
                    ),
                    "accuracy_improvement": metrics.accuracy_improvement,
                }

                self.log_info(
                    f"LearningLoop: "
                    f"total={metrics.total_executions}, "
                    f"success_rate={metrics.success_rate:.1%}, "
                    f"templates={metrics.learned_templates}"
                )

                # Silhouette 执行数据进入 LearningLoop
                if execution.silhouette_artifacts:
                    for sil_art in execution.silhouette_artifacts:
                        cmd = sil_art.get("command", "")
                        task_type = cmd.replace("silhouette_", "") if cmd.startswith("silhouette_") else "unknown"
                        sil_status = sil_art.get("status", "unknown")
                        learning_loop.record_silhouette_execution(
                            user_input=" ".join(understanding.keywords)
                                if understanding.keywords else "",
                            task_type=task_type,
                            params=sil_art.get("params", {}),
                            success=(sil_status == "success"),
                            fallback=(sil_status == "fallback"),
                            error_message=sil_art.get("error", ""),
                            output_path=sil_art.get("output_path", ""),
                        )
                    self.log_info(
                        f"LearningLoop: 记录 {len(execution.silhouette_artifacts)} 条 Silhouette 执行数据"
                    )
            except Exception as e:
                self.log_warning(f"LearningLoop 学习失败: {e}")

        # ===== 3. FailureRecovery 失败恢复 =====
        failure_recovery = getattr(self, "_failure_recovery", None)
        if failure_recovery and not execution.success:
            try:
                from failure_recovery import (
                    ExpectedParameters as FRExpected,
                    ExecutionResult as FRExecution,
                    ExpectedProperty as FRProp,
                    ErrorCode,
                )

                # 推断错误码
                error_msg = (execution.error_message or "").lower()
                error_code = ErrorCode.UNKNOWN.value
                if "not found" in error_msg or "未找到" in error_msg:
                    error_code = ErrorCode.EFFECT_NOT_FOUND.value
                elif "property" in error_msg or "属性" in error_msg:
                    error_code = ErrorCode.PROPERTY_NOT_FOUND.value
                elif "timeout" in error_msg or "超时" in error_msg:
                    error_code = ErrorCode.EXECUTION_TIMEOUT.value
                elif "layer" in error_msg or "图层" in error_msg:
                    error_code = ErrorCode.LAYER_NOT_FOUND.value
                elif "comp" in error_msg or "合成" in error_msg:
                    error_code = ErrorCode.COMP_NOT_FOUND.value
                elif "keyframe" in error_msg or "关键帧" in error_msg:
                    error_code = ErrorCode.KEYFRAME_FAILED.value
                elif "expression" in error_msg or "表达式" in error_msg:
                    error_code = ErrorCode.EXPRESSION_ERROR.value
                elif "memory" in error_msg or "内存" in error_msg:
                    error_code = ErrorCode.OUT_OF_MEMORY.value

                properties = []
                match_name = ""
                if planning.effects:
                    effect = planning.effects[0]
                    match_name = effect.get("matchName", "")
                    for prop_name, prop_value in effect.get(
                        "settings", {}
                    ).items():
                        properties.append(FRProp(
                            name=prop_name, value=prop_value
                        ))

                expected = FRExpected(
                    comp_name=planning.composition.get("name", "Comp")
                        if planning.composition else "Comp",
                    layer_index=1,
                    effect_match_name=match_name or None,
                    properties=properties,
                )

                actual = FRExecution(
                    success=False,
                    error_code=error_code,
                    error_message=execution.error_message or None,
                )

                # async 调用
                loop = asyncio.new_event_loop()
                try:
                    action = loop.run_until_complete(
                        failure_recovery.handle_failure(
                            actual, expected, request_id=None
                        )
                    )
                finally:
                    loop.close()

                feedback.recovery_action = {
                    "action": action.action,
                    "alternative": action.alternative,
                    "timeout": action.timeout,
                    "delay": action.delay,
                    "max_retries": action.max_retries,
                    "message": action.message or "",
                }

                if action.message:
                    feedback.improvement_suggestions.append(
                        f"[恢复建议] {action.message}"
                    )

                self.log_info(
                    f"FailureRecovery: action={action.action}, "
                    f"error_code={error_code}"
                )
            except Exception as e:
                self.log_warning(f"FailureRecovery 恢复失败: {e}")

    def _calculate_rating(self, planning: PlanningResult, execution: ExecutionResult) -> float:
        factors = []

        layer_count = len(planning.layers)
        if layer_count >= 5:
            factors.append(0.25)
        elif layer_count >= 3:
            factors.append(0.2)
        else:
            factors.append(0.15)

        effect_count = len(planning.effects)
        if effect_count >= 5:
            factors.append(0.2)
        elif effect_count >= 3:
            factors.append(0.15)
        else:
            factors.append(0.1)

        keyframe_count = len(planning.keyframes)
        if keyframe_count >= 10:
            factors.append(0.2)
        elif keyframe_count >= 5:
            factors.append(0.15)
        else:
            factors.append(0.1)

        transition_count = len(planning.transitions)
        if transition_count >= 3:
            factors.append(0.15)
        else:
            factors.append(0.1)

        step_ratio = execution.steps_completed / max(execution.total_steps, 1)
        if step_ratio >= 0.9:
            factors.append(0.2)
        elif step_ratio >= 0.7:
            factors.append(0.15)
        else:
            factors.append(0.1)

        silhouette_count = len(planning.silhouette_operations)
        if silhouette_count > 0:
            factors.append(0.1)

        rating = min(1.0, sum(factors))
        return rating

    def _calculate_confidence(self, perception: PerceptionResult,
                              understanding: UnderstandingResult,
                              execution: ExecutionResult) -> float:
        confidence = 0.5

        if perception.music_features:
            confidence += 0.1
        if perception.clip_features:
            confidence += 0.1
        if understanding.intent:
            confidence += 0.1
        if understanding.keywords:
            confidence += 0.05
        if execution.success:
            confidence += 0.15

        return min(1.0, confidence)

    def _generate_suggestions(self, planning: PlanningResult,
                              execution: ExecutionResult) -> List[str]:
        suggestions = []

        if len(planning.layers) < 3:
            suggestions.append("建议增加更多视频片段以丰富内容")
        if len(planning.effects) < 3:
            suggestions.append("建议添加更多视觉效果增强表现力")
        if len(planning.transitions) < 2:
            suggestions.append("建议添加转场效果使剪辑更流畅")
        if not execution.output_path:
            suggestions.append("渲染输出路径未设置，请检查输出配置")

        try:
            from effect_knowledge_graph import find_conflicts, check_boundaries

            for effect in planning.effects:
                effect_name = effect.get("effectName", "")
                settings = effect.get("settings", {})

                if not settings:
                    suggestions.append(f"效果 {effect_name} 缺少参数设置，建议补充参数")
                    continue

                conflicts = find_conflicts(effect_name, settings)
                if conflicts:
                    for conflict in conflicts:
                        suggestions.append(f"效果 {effect_name}: {conflict['message']}")

                boundary_issues = check_boundaries(effect_name, settings)
                if boundary_issues:
                    for issue in boundary_issues:
                        suggestions.append(f"效果 {effect_name}: 参数 {issue['param']} 值 {issue['value']} 接近边界 {issue['boundary']}")

        except Exception:
            pass

        return suggestions

    def _extract_patterns(self, perception: PerceptionResult,
                          understanding: UnderstandingResult,
                          planning: PlanningResult) -> Dict:
        patterns = {}

        if perception.music_features:
            patterns["music_mood"] = perception.music_features.get("mood")
            patterns["music_bpm"] = perception.music_features.get("bpm")

        patterns["style"] = understanding.style
        patterns["intent"] = understanding.intent
        patterns["layer_count"] = len(planning.layers)
        patterns["effect_count"] = len(planning.effects)
        patterns["has_silhouette"] = len(planning.silhouette_operations) > 0

        return patterns

    def _log_feedback(self, feedback: FeedbackResult) -> None:
        if self._observability:
            self._observability.logger.info("反馈评估结果",
                rating=feedback.rating,
                confidence=feedback.confidence,
                suggestion_count=len(feedback.improvement_suggestions),
            )

        # 记录执行结果到记忆系统（用于经验学习）
        if self._memory_store:
            self._memory_store.record_outcome(
                category="pipeline_execution",
                key=feedback.pipeline_id if hasattr(feedback, 'pipeline_id') else "default",
                success=feedback.rating >= 0.5,
            )

    def _update_confidence_cache(self, mood: str, style: str, confidence: float) -> None:
        """更新置信度缓存 — 使用持久化记忆系统"""
        if not self._memory_store:
            return

        self._memory_store.remember(
            category="confidence_cache",
            key=f"{mood}_{style}",
            content={
                "mood": mood,
                "style": style,
                "confidence": confidence,
            },
            tags=[mood, style],
            confidence=confidence,
        )

    def _generate_pipeline_id(self, music_path: str, clip_paths: List[str]) -> str:
        unique_str = f"{music_path}_{'_'.join(clip_paths)}_{datetime.now().isoformat()}"
        return hashlib.md5(unique_str.encode()).hexdigest()