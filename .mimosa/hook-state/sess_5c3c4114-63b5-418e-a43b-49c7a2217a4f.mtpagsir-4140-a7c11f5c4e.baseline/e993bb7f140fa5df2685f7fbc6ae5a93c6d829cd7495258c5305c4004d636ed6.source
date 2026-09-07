#!/usr/bin/env python3
"""
状态机模式核心 - PipelineStateMachine 工作流状态管理 v1.0

设计原则（基于 David Harel Statecharts）：
1. 层次化状态：支持嵌套状态和复合状态
2. 并行状态：支持并发执行多个子状态机
3. 转换守卫：支持条件转换
4. 进入/退出动作：状态切换时执行副作用
5. 事件驱动：通过事件触发状态转换
6. 历史状态：支持记住上一次的子状态

状态机生命周期：
- IDLE: 初始状态，等待启动
- RUNNING: 运行中，执行各个阶段
- PAUSED: 暂停，等待恢复
- COMPLETED: 所有阶段完成
- FAILED: 执行失败
- CANCELLED: 用户取消

阶段状态：
- PERCEPTION: 感知层
- UNDERSTANDING: 理解层
- PLANNING: 规划层
- EXECUTION: 执行层（含 Silhouette + AE）
- FEEDBACK: 反馈层

架构参考：
- David Harel Statecharts (1987)
- UML State Machine Diagram
- SCXML (State Chart XML)
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union


class PipelineStatus(Enum):
    """工作流顶层状态"""
    IDLE = auto()        # 初始状态
    RUNNING = auto()     # 运行中
    PAUSED = auto()      # 暂停
    COMPLETED = auto()   # 完成
    FAILED = auto()      # 失败
    CANCELLED = auto()   # 取消


class PipelinePhase(Enum):
    """工作流阶段状态"""
    IDLE = auto()
    PERCEPTION = auto()
    UNDERSTANDING = auto()
    PLANNING = auto()
    EXECUTION = auto()
    FEEDBACK = auto()


class SilhouetteStatus(Enum):
    """Silhouette 子状态"""
    IDLE = auto()
    ROUTING = auto()
    WAITING = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    FAILED = auto()
    FALLBACK = auto()


class AEStatus(Enum):
    """AE 子状态"""
    IDLE = auto()
    COMPILING = auto()
    EXECUTING = auto()
    RENDERING = auto()
    COMPLETED = auto()
    FAILED = auto()


class TopazStatus(Enum):
    """Topaz Video AI 子状态"""
    IDLE = auto()
    LOADING = auto()
    ENHANCING = auto()
    EXPORTING = auto()
    COMPLETED = auto()
    FAILED = auto()


class RunwayStatus(Enum):
    """RunwayML 子状态"""
    IDLE = auto()
    REQUESTING = auto()
    GENERATING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()


class PikaStatus(Enum):
    """Pika 子状态"""
    IDLE = auto()
    REQUESTING = auto()
    GENERATING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    FAILED = auto()


class BlenderStatus(Enum):
    """Blender 子状态"""
    IDLE = auto()
    LAUNCHING = auto()
    RENDERING = auto()
    EXPORTING = auto()
    COMPLETED = auto()
    FAILED = auto()


class FFmpegStatus(Enum):
    """FFmpeg 子状态"""
    IDLE = auto()
    TRANSCODING = auto()
    FILTERING = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class Transition:
    """状态转换定义"""
    from_state: Enum
    to_state: Enum
    event: Optional[str] = None
    guard: Optional[Callable[[Any], bool]] = None
    action: Optional[Callable[[Any], Any]] = None
    priority: int = 0


@dataclass
class StateContext:
    """状态上下文 - 存储当前状态和相关数据"""
    pipeline_id: str
    status: PipelineStatus = PipelineStatus.IDLE
    phase: PipelinePhase = PipelinePhase.IDLE
    silhouette_status: SilhouetteStatus = SilhouetteStatus.IDLE
    ae_status: AEStatus = AEStatus.IDLE
    topaz_status: TopazStatus = TopazStatus.IDLE
    runway_status: RunwayStatus = RunwayStatus.IDLE
    pika_status: PikaStatus = PikaStatus.IDLE
    blender_status: BlenderStatus = BlenderStatus.IDLE
    ffmpeg_status: FFmpegStatus = FFmpegStatus.IDLE
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error: Optional[Exception] = None
    progress: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


class StateListener:
    """状态监听器"""
    def on_state_changed(self, context: StateContext) -> None:
        pass

    def on_phase_changed(self, context: StateContext) -> None:
        pass


class PipelineStateMachine:
    """工作流状态机 - 支持层次化状态和并行子状态机"""

    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.PipelineStateMachine")
        self._context = StateContext(pipeline_id=str(uuid.uuid4()))
        self._listeners: List[StateListener] = []

        # 顶层状态转换表
        self._top_transitions: List[Transition] = [
            Transition(PipelineStatus.IDLE, PipelineStatus.RUNNING, event="start"),
            Transition(PipelineStatus.RUNNING, PipelineStatus.PAUSED, event="pause"),
            Transition(PipelineStatus.PAUSED, PipelineStatus.RUNNING, event="resume"),
            Transition(PipelineStatus.RUNNING, PipelineStatus.CANCELLED, event="cancel"),
            Transition(PipelineStatus.RUNNING, PipelineStatus.COMPLETED, event="complete"),
            Transition(PipelineStatus.RUNNING, PipelineStatus.FAILED, event="fail"),
            Transition(PipelineStatus.FAILED, PipelineStatus.IDLE, event="reset"),
            Transition(PipelineStatus.COMPLETED, PipelineStatus.IDLE, event="reset"),
            Transition(PipelineStatus.CANCELLED, PipelineStatus.IDLE, event="reset"),
        ]

        # 阶段状态转换表
        self._phase_transitions: List[Transition] = [
            Transition(PipelinePhase.IDLE, PipelinePhase.PERCEPTION, event="start"),
            Transition(PipelinePhase.PERCEPTION, PipelinePhase.UNDERSTANDING, event="perception_done"),
            Transition(PipelinePhase.UNDERSTANDING, PipelinePhase.PLANNING, event="understanding_done"),
            Transition(PipelinePhase.PLANNING, PipelinePhase.EXECUTION, event="planning_done"),
            Transition(PipelinePhase.EXECUTION, PipelinePhase.FEEDBACK, event="execution_done"),
            Transition(PipelinePhase.FEEDBACK, PipelinePhase.IDLE, event="feedback_done"),
            Transition(PipelinePhase.PERCEPTION, PipelinePhase.IDLE, event="fail"),
            Transition(PipelinePhase.UNDERSTANDING, PipelinePhase.IDLE, event="fail"),
            Transition(PipelinePhase.PLANNING, PipelinePhase.IDLE, event="fail"),
            Transition(PipelinePhase.EXECUTION, PipelinePhase.IDLE, event="fail"),
            Transition(PipelinePhase.FEEDBACK, PipelinePhase.IDLE, event="fail"),
        ]

        # Silhouette 子状态转换表
        self._silhouette_transitions: List[Transition] = [
            Transition(SilhouetteStatus.IDLE, SilhouetteStatus.ROUTING, event="silhouette_start"),
            Transition(SilhouetteStatus.ROUTING, SilhouetteStatus.WAITING, event="silhouette_routed"),
            Transition(SilhouetteStatus.WAITING, SilhouetteStatus.PROCESSING, event="silhouette_start_process"),
            Transition(SilhouetteStatus.PROCESSING, SilhouetteStatus.COMPLETED, event="silhouette_done"),
            Transition(SilhouetteStatus.PROCESSING, SilhouetteStatus.FALLBACK, event="silhouette_fallback"),
            Transition(SilhouetteStatus.PROCESSING, SilhouetteStatus.FAILED, event="silhouette_fail"),
            Transition(SilhouetteStatus.FALLBACK, SilhouetteStatus.COMPLETED, event="fallback_done"),
            Transition(SilhouetteStatus.COMPLETED, SilhouetteStatus.IDLE, event="reset"),
            Transition(SilhouetteStatus.FAILED, SilhouetteStatus.IDLE, event="reset"),
        ]

        # AE 子状态转换表
        self._ae_transitions: List[Transition] = [
            Transition(AEStatus.IDLE, AEStatus.COMPILING, event="ae_compile"),
            Transition(AEStatus.COMPILING, AEStatus.EXECUTING, event="ae_compiled"),
            Transition(AEStatus.EXECUTING, AEStatus.RENDERING, event="ae_executed"),
            Transition(AEStatus.RENDERING, AEStatus.COMPLETED, event="ae_rendered"),
            Transition(AEStatus.COMPILING, AEStatus.FAILED, event="ae_compile_fail"),
            Transition(AEStatus.EXECUTING, AEStatus.FAILED, event="ae_execute_fail"),
            Transition(AEStatus.RENDERING, AEStatus.FAILED, event="ae_render_fail"),
            Transition(AEStatus.COMPLETED, AEStatus.IDLE, event="reset"),
            Transition(AEStatus.FAILED, AEStatus.IDLE, event="reset"),
        ]

        # Topaz 子状态转换表
        self._topaz_transitions: List[Transition] = [
            Transition(TopazStatus.IDLE, TopazStatus.LOADING, event="topaz_start"),
            Transition(TopazStatus.LOADING, TopazStatus.ENHANCING, event="topaz_loaded"),
            Transition(TopazStatus.ENHANCING, TopazStatus.EXPORTING, event="topaz_enhanced"),
            Transition(TopazStatus.EXPORTING, TopazStatus.COMPLETED, event="topaz_exported"),
            Transition(TopazStatus.LOADING, TopazStatus.FAILED, event="topaz_load_fail"),
            Transition(TopazStatus.ENHANCING, TopazStatus.FAILED, event="topaz_enhance_fail"),
            Transition(TopazStatus.EXPORTING, TopazStatus.FAILED, event="topaz_export_fail"),
            Transition(TopazStatus.COMPLETED, TopazStatus.IDLE, event="reset"),
            Transition(TopazStatus.FAILED, TopazStatus.IDLE, event="reset"),
        ]

        # Runway 子状态转换表
        self._runway_transitions: List[Transition] = [
            Transition(RunwayStatus.IDLE, RunwayStatus.REQUESTING, event="runway_start"),
            Transition(RunwayStatus.REQUESTING, RunwayStatus.GENERATING, event="runway_requested"),
            Transition(RunwayStatus.GENERATING, RunwayStatus.DOWNLOADING, event="runway_generated"),
            Transition(RunwayStatus.DOWNLOADING, RunwayStatus.COMPLETED, event="runway_downloaded"),
            Transition(RunwayStatus.REQUESTING, RunwayStatus.FAILED, event="runway_request_fail"),
            Transition(RunwayStatus.GENERATING, RunwayStatus.FAILED, event="runway_generate_fail"),
            Transition(RunwayStatus.DOWNLOADING, RunwayStatus.FAILED, event="runway_download_fail"),
            Transition(RunwayStatus.COMPLETED, RunwayStatus.IDLE, event="reset"),
            Transition(RunwayStatus.FAILED, RunwayStatus.IDLE, event="reset"),
        ]

        # Pika 子状态转换表
        self._pika_transitions: List[Transition] = [
            Transition(PikaStatus.IDLE, PikaStatus.REQUESTING, event="pika_start"),
            Transition(PikaStatus.REQUESTING, PikaStatus.GENERATING, event="pika_requested"),
            Transition(PikaStatus.GENERATING, PikaStatus.DOWNLOADING, event="pika_generated"),
            Transition(PikaStatus.DOWNLOADING, PikaStatus.COMPLETED, event="pika_downloaded"),
            Transition(PikaStatus.REQUESTING, PikaStatus.FAILED, event="pika_request_fail"),
            Transition(PikaStatus.GENERATING, PikaStatus.FAILED, event="pika_generate_fail"),
            Transition(PikaStatus.DOWNLOADING, PikaStatus.FAILED, event="pika_download_fail"),
            Transition(PikaStatus.COMPLETED, PikaStatus.IDLE, event="reset"),
            Transition(PikaStatus.FAILED, PikaStatus.IDLE, event="reset"),
        ]

        # Blender 子状态转换表
        self._blender_transitions: List[Transition] = [
            Transition(BlenderStatus.IDLE, BlenderStatus.LAUNCHING, event="blender_start"),
            Transition(BlenderStatus.LAUNCHING, BlenderStatus.RENDERING, event="blender_launched"),
            Transition(BlenderStatus.RENDERING, BlenderStatus.EXPORTING, event="blender_rendered"),
            Transition(BlenderStatus.EXPORTING, BlenderStatus.COMPLETED, event="blender_exported"),
            Transition(BlenderStatus.LAUNCHING, BlenderStatus.FAILED, event="blender_launch_fail"),
            Transition(BlenderStatus.RENDERING, BlenderStatus.FAILED, event="blender_render_fail"),
            Transition(BlenderStatus.EXPORTING, BlenderStatus.FAILED, event="blender_export_fail"),
            Transition(BlenderStatus.COMPLETED, BlenderStatus.IDLE, event="reset"),
            Transition(BlenderStatus.FAILED, BlenderStatus.IDLE, event="reset"),
        ]

        # FFmpeg 子状态转换表
        self._ffmpeg_transitions: List[Transition] = [
            Transition(FFmpegStatus.IDLE, FFmpegStatus.TRANSCODING, event="ffmpeg_start"),
            Transition(FFmpegStatus.TRANSCODING, FFmpegStatus.FILTERING, event="ffmpeg_transcoded"),
            Transition(FFmpegStatus.FILTERING, FFmpegStatus.COMPLETED, event="ffmpeg_filtered"),
            Transition(FFmpegStatus.TRANSCODING, FFmpegStatus.FAILED, event="ffmpeg_transcode_fail"),
            Transition(FFmpegStatus.FILTERING, FFmpegStatus.FAILED, event="ffmpeg_filter_fail"),
            Transition(FFmpegStatus.COMPLETED, FFmpegStatus.IDLE, event="reset"),
            Transition(FFmpegStatus.FAILED, FFmpegStatus.IDLE, event="reset"),
        ]

    # -------------------------------------------------------------------------
    # 状态查询
    # -------------------------------------------------------------------------

    @property
    def context(self) -> StateContext:
        return self._context

    @property
    def status(self) -> PipelineStatus:
        return self._context.status

    @property
    def phase(self) -> PipelinePhase:
        return self._context.phase

    @property
    def is_running(self) -> bool:
        return self._context.status == PipelineStatus.RUNNING

    @property
    def is_completed(self) -> bool:
        return self._context.status == PipelineStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self._context.status == PipelineStatus.FAILED

    # -------------------------------------------------------------------------
    # 状态转换 API
    # -------------------------------------------------------------------------

    def trigger(self, event: str, data: Dict[str, Any] = None) -> bool:
        """触发状态转换"""
        data = data or {}
        self._logger.debug(f"Triggering event: {event}")

        # 更新上下文数据
        if data:
            self._context.data.update(data)

        # 尝试阶段转换
        phase_changed = self._try_transition(self._phase_transitions, event, "phase")

        # 尝试顶层状态转换
        status_changed = self._try_transition(self._top_transitions, event, "status")

        # 尝试 Silhouette 子状态转换
        silhouette_changed = self._try_transition(
            self._silhouette_transitions, event, "silhouette_status"
        )

        # 尝试 AE 子状态转换
        ae_changed = self._try_transition(self._ae_transitions, event, "ae_status")

        # 尝试 Topaz 子状态转换
        topaz_changed = self._try_transition(
            self._topaz_transitions, event, "topaz_status"
        )

        # 尝试 Runway 子状态转换
        runway_changed = self._try_transition(
            self._runway_transitions, event, "runway_status"
        )

        # 尝试 Pika 子状态转换
        pika_changed = self._try_transition(
            self._pika_transitions, event, "pika_status"
        )

        # 尝试 Blender 子状态转换
        blender_changed = self._try_transition(
            self._blender_transitions, event, "blender_status"
        )

        # 尝试 FFmpeg 子状态转换
        ffmpeg_changed = self._try_transition(
            self._ffmpeg_transitions, event, "ffmpeg_status"
        )

        # 触发监听器
        if status_changed:
            self._notify_state_changed()
        if phase_changed:
            self._notify_phase_changed()

        return (status_changed or phase_changed or silhouette_changed
                or ae_changed or topaz_changed or runway_changed
                or pika_changed or blender_changed or ffmpeg_changed)

    def _try_transition(
        self,
        transitions: List[Transition],
        event: str,
        state_attr: str,
    ) -> bool:
        """尝试状态转换"""
        current_state = getattr(self._context, state_attr)

        # 找到匹配的转换
        matching = [
            t for t in transitions
            if t.from_state == current_state
            and (t.event is None or t.event == event)
        ]

        if not matching:
            return False

        # 按优先级排序
        matching.sort(key=lambda t: -t.priority)

        for trans in matching:
            # 检查守卫条件
            if trans.guard and not trans.guard(self._context):
                continue

            # 执行动作
            if trans.action:
                try:
                    trans.action(self._context)
                except Exception as e:
                    self._logger.error(f"Transition action error: {e}")

            # 执行状态转换
            setattr(self._context, state_attr, trans.to_state)
            self._logger.info(f"State changed: {current_state.name} -> {trans.to_state.name}")
            return True

        return False

    # -------------------------------------------------------------------------
    # 生命周期 API
    # -------------------------------------------------------------------------

    def start(self, pipeline_id: Optional[str] = None) -> None:
        """启动工作流"""
        if pipeline_id:
            self._context.pipeline_id = pipeline_id
        self._context.start_time = time.time()
        self.trigger("start")

    def pause(self) -> None:
        """暂停工作流"""
        self.trigger("pause")

    def resume(self) -> None:
        """恢复工作流"""
        self.trigger("resume")

    def cancel(self) -> None:
        """取消工作流"""
        self.trigger("cancel")
        self._context.end_time = time.time()

    def complete(self) -> None:
        """标记工作流完成"""
        self.trigger("complete")
        self._context.end_time = time.time()

    def fail(self, error: Exception) -> None:
        """标记工作流失败"""
        self._context.error = error
        self.trigger("fail")
        self._context.end_time = time.time()

    def reset(self) -> None:
        """重置工作流到初始状态"""
        self._context = StateContext(pipeline_id=str(uuid.uuid4()))
        self.trigger("reset")

    # -------------------------------------------------------------------------
    # 阶段完成 API
    # -------------------------------------------------------------------------

    def phase_perception_done(self, data: Dict[str, Any] = None) -> None:
        self._context.progress = 0.2
        self.trigger("perception_done", data)

    def phase_understanding_done(self, data: Dict[str, Any] = None) -> None:
        self._context.progress = 0.4
        self.trigger("understanding_done", data)

    def phase_planning_done(self, data: Dict[str, Any] = None) -> None:
        self._context.progress = 0.6
        self.trigger("planning_done", data)

    def phase_execution_done(self, data: Dict[str, Any] = None) -> None:
        self._context.progress = 0.8
        self.trigger("execution_done", data)

    def phase_feedback_done(self, data: Dict[str, Any] = None) -> None:
        self._context.progress = 1.0
        self.trigger("feedback_done", data)
        self.complete()

    # -------------------------------------------------------------------------
    # Silhouette 子状态 API
    # -------------------------------------------------------------------------

    def silhouette_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("silhouette_start", data)

    def silhouette_routed(self, data: Dict[str, Any] = None) -> None:
        self.trigger("silhouette_routed", data)

    def silhouette_start_process(self, data: Dict[str, Any] = None) -> None:
        self.trigger("silhouette_start_process", data)

    def silhouette_done(self, data: Dict[str, Any] = None) -> None:
        self.trigger("silhouette_done", data)

    def silhouette_fallback(self, data: Dict[str, Any] = None) -> None:
        self.trigger("silhouette_fallback", data)

    def silhouette_fail(self, error: Exception) -> None:
        self._context.data["silhouette_error"] = str(error)
        self.trigger("silhouette_fail")

    # -------------------------------------------------------------------------
    # AE 子状态 API
    # -------------------------------------------------------------------------

    def ae_compile(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_compile", data)

    def ae_compiled(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_compiled", data)

    def ae_execute(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_executing", data)

    def ae_executed(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_executed", data)

    def ae_render(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_render", data)

    def ae_rendered(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ae_rendered", data)

    def ae_fail(self, phase: str, error: Exception) -> None:
        self._context.data["ae_error"] = {"phase": phase, "error": str(error)}
        if phase == "compile":
            self.trigger("ae_compile_fail")
        elif phase == "execute":
            self.trigger("ae_execute_fail")
        elif phase == "render":
            self.trigger("ae_render_fail")

    # -------------------------------------------------------------------------
    # Topaz 子状态 API
    # -------------------------------------------------------------------------

    def topaz_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("topaz_start", data)

    def topaz_loaded(self, data: Dict[str, Any] = None) -> None:
        self.trigger("topaz_loaded", data)

    def topaz_enhanced(self, data: Dict[str, Any] = None) -> None:
        self.trigger("topaz_enhanced", data)

    def topaz_exported(self, data: Dict[str, Any] = None) -> None:
        self.trigger("topaz_exported", data)

    def topaz_fail(self, phase: str, error: Exception) -> None:
        self._context.data["topaz_error"] = {"phase": phase, "error": str(error)}
        if phase == "load":
            self.trigger("topaz_load_fail")
        elif phase == "enhance":
            self.trigger("topaz_enhance_fail")
        elif phase == "export":
            self.trigger("topaz_export_fail")

    # -------------------------------------------------------------------------
    # Runway 子状态 API
    # -------------------------------------------------------------------------

    def runway_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("runway_start", data)

    def runway_requested(self, data: Dict[str, Any] = None) -> None:
        self.trigger("runway_requested", data)

    def runway_generated(self, data: Dict[str, Any] = None) -> None:
        self.trigger("runway_generated", data)

    def runway_downloaded(self, data: Dict[str, Any] = None) -> None:
        self.trigger("runway_downloaded", data)

    def runway_fail(self, phase: str, error: Exception) -> None:
        self._context.data["runway_error"] = {"phase": phase, "error": str(error)}
        if phase == "request":
            self.trigger("runway_request_fail")
        elif phase == "generate":
            self.trigger("runway_generate_fail")
        elif phase == "download":
            self.trigger("runway_download_fail")

    # -------------------------------------------------------------------------
    # Pika 子状态 API
    # -------------------------------------------------------------------------

    def pika_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("pika_start", data)

    def pika_requested(self, data: Dict[str, Any] = None) -> None:
        self.trigger("pika_requested", data)

    def pika_generated(self, data: Dict[str, Any] = None) -> None:
        self.trigger("pika_generated", data)

    def pika_downloaded(self, data: Dict[str, Any] = None) -> None:
        self.trigger("pika_downloaded", data)

    def pika_fail(self, phase: str, error: Exception) -> None:
        self._context.data["pika_error"] = {"phase": phase, "error": str(error)}
        if phase == "request":
            self.trigger("pika_request_fail")
        elif phase == "generate":
            self.trigger("pika_generate_fail")
        elif phase == "download":
            self.trigger("pika_download_fail")

    # -------------------------------------------------------------------------
    # Blender 子状态 API
    # -------------------------------------------------------------------------

    def blender_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("blender_start", data)

    def blender_launched(self, data: Dict[str, Any] = None) -> None:
        self.trigger("blender_launched", data)

    def blender_rendered(self, data: Dict[str, Any] = None) -> None:
        self.trigger("blender_rendered", data)

    def blender_exported(self, data: Dict[str, Any] = None) -> None:
        self.trigger("blender_exported", data)

    def blender_fail(self, phase: str, error: Exception) -> None:
        self._context.data["blender_error"] = {"phase": phase, "error": str(error)}
        if phase == "launch":
            self.trigger("blender_launch_fail")
        elif phase == "render":
            self.trigger("blender_render_fail")
        elif phase == "export":
            self.trigger("blender_export_fail")

    # -------------------------------------------------------------------------
    # FFmpeg 子状态 API
    # -------------------------------------------------------------------------

    def ffmpeg_start(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ffmpeg_start", data)

    def ffmpeg_transcoded(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ffmpeg_transcoded", data)

    def ffmpeg_filtered(self, data: Dict[str, Any] = None) -> None:
        self.trigger("ffmpeg_filtered", data)

    def ffmpeg_fail(self, phase: str, error: Exception) -> None:
        self._context.data["ffmpeg_error"] = {"phase": phase, "error": str(error)}
        if phase == "transcode":
            self.trigger("ffmpeg_transcode_fail")
        elif phase == "filter":
            self.trigger("ffmpeg_filter_fail")

    # -------------------------------------------------------------------------
    # 监听器管理
    # -------------------------------------------------------------------------

    def add_listener(self, listener: StateListener) -> None:
        """添加状态监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: StateListener) -> None:
        """移除状态监听器"""
        self._listeners.remove(listener)

    def _notify_state_changed(self) -> None:
        """通知状态变更"""
        for listener in self._listeners:
            try:
                listener.on_state_changed(self._context)
            except Exception as e:
                self._logger.error(f"Listener error: {e}")

    def _notify_phase_changed(self) -> None:
        """通知阶段变更"""
        for listener in self._listeners:
            try:
                listener.on_phase_changed(self._context)
            except Exception as e:
                self._logger.error(f"Listener error: {e}")

    # -------------------------------------------------------------------------
    # 状态持久化
    # -------------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "pipeline_id": self._context.pipeline_id,
            "status": self._context.status.name,
            "phase": self._context.phase.name,
            "silhouette_status": self._context.silhouette_status.name,
            "ae_status": self._context.ae_status.name,
            "topaz_status": self._context.topaz_status.name,
            "runway_status": self._context.runway_status.name,
            "pika_status": self._context.pika_status.name,
            "blender_status": self._context.blender_status.name,
            "ffmpeg_status": self._context.ffmpeg_status.name,
            "start_time": self._context.start_time,
            "end_time": self._context.end_time,
            "progress": self._context.progress,
            "error": str(self._context.error) if self._context.error else None,
            "data": self._context.data,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineStateMachine":
        """从字典恢复"""
        sm = cls()
        sm._context.pipeline_id = data["pipeline_id"]
        sm._context.status = PipelineStatus[data["status"]]
        sm._context.phase = PipelinePhase[data["phase"]]
        sm._context.silhouette_status = SilhouetteStatus[data["silhouette_status"]]
        sm._context.ae_status = AEStatus[data["ae_status"]]
        sm._context.topaz_status = TopazStatus[data.get("topaz_status", "IDLE")]
        sm._context.runway_status = RunwayStatus[data.get("runway_status", "IDLE")]
        sm._context.pika_status = PikaStatus[data.get("pika_status", "IDLE")]
        sm._context.blender_status = BlenderStatus[data.get("blender_status", "IDLE")]
        sm._context.ffmpeg_status = FFmpegStatus[data.get("ffmpeg_status", "IDLE")]
        sm._context.start_time = data.get("start_time")
        sm._context.end_time = data.get("end_time")
        sm._context.progress = data.get("progress", 0.0)
        sm._context.error = Exception(data["error"]) if data.get("error") else None
        sm._context.data = data.get("data", {})
        return sm

    # -------------------------------------------------------------------------
    # 状态验证
    # -------------------------------------------------------------------------

    def validate_state(self) -> bool:
        """验证当前状态是否合法"""
        # 顶层状态约束
        if self._context.status == PipelineStatus.RUNNING:
            # 运行中必须在某个阶段
            if self._context.phase == PipelinePhase.IDLE:
                return False
        elif self._context.status == PipelineStatus.COMPLETED:
            # 完成时进度必须为 100%
            if self._context.progress < 1.0:
                return False

        # 阶段约束
        if self._context.phase == PipelinePhase.EXECUTION:
            # 执行阶段必须至少有一个子状态机处于活动状态
            active_sub_states = [
                self._context.silhouette_status != SilhouetteStatus.IDLE,
                self._context.ae_status != AEStatus.IDLE,
                self._context.topaz_status != TopazStatus.IDLE,
                self._context.runway_status != RunwayStatus.IDLE,
                self._context.pika_status != PikaStatus.IDLE,
                self._context.blender_status != BlenderStatus.IDLE,
                self._context.ffmpeg_status != FFmpegStatus.IDLE,
            ]
            if not any(active_sub_states):
                return False

        return True

    # -------------------------------------------------------------------------
    # 统计信息
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取状态机统计信息"""
        duration = 0.0
        if self._context.start_time:
            end = self._context.end_time or time.time()
            duration = end - self._context.start_time

        return {
            "pipeline_id": self._context.pipeline_id,
            "status": self._context.status.name,
            "phase": self._context.phase.name,
            "silhouette_status": self._context.silhouette_status.name,
            "ae_status": self._context.ae_status.name,
            "topaz_status": self._context.topaz_status.name,
            "runway_status": self._context.runway_status.name,
            "pika_status": self._context.pika_status.name,
            "blender_status": self._context.blender_status.name,
            "ffmpeg_status": self._context.ffmpeg_status.name,
            "progress": f"{self._context.progress * 100:.1f}%",
            "duration_seconds": duration,
            "is_valid": self.validate_state(),
            "data_keys": list(self._context.data.keys()),
        }
