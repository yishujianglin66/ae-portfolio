"""
pipeline/unified_pipeline.py - 端到端视频创作管线 v2
=====================================================

统一编排: perceive → analyze → plan → execute → render → verify → learn

v2 新增能力:
  - 3种触发模式: 文字主题 / 参考视频(VRS) / 混合输入
  - VRS 逆向分析 → 生产数据流打通
  - 知识库实时注入每个决策节点
  - 反馈闭环: QualityAgent → KB → 自迭代

用法:
    from pipeline import UnifiedPipeline, PipelineConfig

    # 模式1: 文字主题驱动
    config = PipelineConfig(input_topic="利威尔高燃混剪")
    pipe = UnifiedPipeline(config)
    result = pipe.run_all()

    # 模式2: 参考视频驱动 (VRS 逆向复刻)
    config = PipelineConfig(reference_video="ref.mp4")
    pipe = UnifiedPipeline(config)
    result = pipe.run_all()

    # 模式3: 混合输入
    config = PipelineConfig(
        input_topic="冰海战记电影感",
        reference_video="style_ref.mp4",
        materials_dir="data/materials",
    )
    pipe = UnifiedPipeline(config)
    result = pipe.run_all()
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings

# ffmpeg/ffprobe 默认路径收口到 core/paths.py（AEK_FFMPEG / AEK_FFPROBE 可覆盖）
try:
    from core.paths import ffmpeg_bin as _paths_ffmpeg, ffprobe_bin as _paths_ffprobe
except ImportError:
    _paths_ffmpeg = lambda: r"C:\ffmpeg\bin\ffmpeg.exe"
    _paths_ffprobe = lambda: r"C:\ffmpeg\bin\ffprobe.exe"

logger = logging.getLogger(__name__)


def try_h3_motion_transfer(
    source_video: str,
    target_style_ref: str,
    output_path: str,
    *,
    logger: Optional[logging.Logger] = None,
) -> Tuple[bool, str]:
    """尝试 H3 V2V Motion Transfer（动作迁移）：把 source_video 中动作迁移到 target_style_ref 形象上。

    失败不会抛异常，由调用方自行决定是否 fallback。
    """
    _log = logger or logging.getLogger("h3_v2v")
    try:
        from core.llm_gateway import llm_gateway
        if not hasattr(llm_gateway, "edit_video"):
            return False, "当前 llm_gateway 未接入 H3 edit_video"
        result = llm_gateway.edit_video(
            operation="motion_transfer",
            source_video=source_video,
            reference_image=target_style_ref,
            output_path=output_path,
        )
        if result.get("success") and result.get("output_path"):
            return True, result["output_path"]
        return False, f"H3 V2V 失败: {result.get('error', 'unknown')}"
    except Exception as e:
        _log.warning(f"[H3 V2V] 失败: {e}")
        return False, f"H3 V2V 异常: {e}"


# ============================================================================
#  P3: 自适应降级路径选择器 (Agentic 增强)
# ============================================================================

@dataclass
class EngineCandidate:
    """降级候选引擎 (P2.4 新增)
    
    用于 AdaptiveFallbackSelector.select_with_meta 的候选输入。
    封装降级路径 ID、引擎名、引擎元数据，供评分函数读取多源信号。
    
    Attributes:
        path_id: 降级路径标识 (例如 "ae_retry" / "ffmpeg_fallback" / "skip_stage")
        engine_name: 对应的引擎名 (可选，用于联动 EngineRegistry 查询历史)
        metadata: 引擎元数据 (可选，含 quality_tier / cost_per_sec)
        priority: 优先级覆盖 (0-1，越高越优先；默认 0.5 表示不覆盖)
    """
    path_id: str
    engine_name: str = ""
    metadata: Any = None
    priority: float = 0.5


# AdaptiveFallbackSelector 已拆出 (2026-08-14), 此处 re-export 保持向后兼容:
#   from pipeline.unified_pipeline import (AdaptiveFallbackSelector,
#       get_fallback_selector)
from pipeline.adaptive_fallback import (  # noqa: E402,F401
    AdaptiveFallbackSelector,
    get_fallback_selector,
)



def try_h3_native_av_generate(
    prompt: str,
    output_path: str,
    *,
    duration_sec: int = 10,
    resolution: str = "768p",
    aspect_ratio: str = "16:9",
    reference_images: Optional[List[str]] = None,
    reference_videos: Optional[List[str]] = None,
    reference_audios: Optional[List[str]] = None,
    logger: Optional[logging.Logger] = None,
) -> Tuple[bool, str]:
    """尝试用 MiniMax H3 原生双声道音画同步生成（≤15s 短片推荐）。

    优点：跳过独立 BGM 匹配+合成步骤，一步生成带匹配 BGM 的视频；
    局限：时长上限 15s，长视频仍需分镜拼接；需 H3 API 配置。

    Returns:
        (success: bool, message_or_path: str)
        成功时返回 (True, 输出文件绝对路径)；失败时返回 (False, 失败原因)。
    """
    _log = logger or logging.getLogger("h3_native_av")
    if duration_sec > 15:
        return False, f"H3 时长上限 15s，请求 {duration_sec}s"
    try:
        from core.llm_gateway import llm_gateway
        if not hasattr(llm_gateway, "generate_video"):
            return False, "当前 llm_gateway 未接入 H3 generate_video（Group C 未执行或失败）"
        result = llm_gateway.generate_video(
            prompt=prompt,
            duration_sec=duration_sec,
            resolution=resolution,
            aspect_ratio=aspect_ratio,
            reference_images=reference_images or [],
            reference_videos=reference_videos or [],
            reference_audios=reference_audios or [],
            output_path=output_path,
        )
        if result.get("success") and result.get("output_path"):
            return True, result["output_path"]
        return False, f"H3 生成失败: {result.get('error', 'unknown')}"
    except Exception as e:
        _log.warning(f"[H3 native AV] 生成失败: {e}")
        return False, f"H3 生成异常: {e}"


# ============================================================================
#  数据类型
# ============================================================================

class StageStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineMode(Enum):
    """管线触发模式"""
    TEXT_TOPIC = "text_topic"           # 纯文字主题
    REFERENCE_VIDEO = "reference_video" # 参考视频 (VRS逆向)
    MIXED = "mixed"                     # 混合输入


@dataclass
class StageResult:
    """单阶段结果"""
    stage: str
    status: StageStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_sec: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PipelineConfig:
    """管线配置"""
    # 输入
    input_topic: str = ""
    materials_dir: str = ""
    reference_video: str = ""
    style_reference: str = ""
    audio_path: str = ""

    # 输出
    output_dir: str = "output"
    project_name: str = ""

    # 阶段控制
    skip_stages: List[str] = field(default_factory=list)
    start_from: str = ""

    # 渲染
    render_format: str = "h264"
    reuse_ae: bool = True
    auto_render: bool = True

    # 知识库
    use_knowledge: bool = True
    style_match: bool = True

    # LLM
    llm_provider: str = "deepseek"
    llm_model: str = ""

    # v2 新增
    enable_vrs: bool = True              # 启用 VRS 逆向分析
    enable_feedback_loop: bool = True    # 启用反馈闭环
    enable_multi_agent: bool = True      # 启用多智能体执行
    max_quality_iterations: int = 3      # 最大质量迭代次数 (默认3, 上限5, 防止无限循环)
    min_quality_score: float = 60.0      # 最低质量分
    publish_platforms: List[str] = field(default_factory=list)  # 发布平台
    use_davinci_render: bool = False       # 启用 DaVinci 后处理渲染
    ffmpeg_bin: str = ""                   # FFmpeg 可执行文件路径 (空=自动搜索)
    use_compiler: bool = False              # 使用 compiler 确定性管线替代 LLM
    enable_evolution: bool = True           # 启用自进化闭环 (P0: 评测+版本对比+回退)
    # Loop Engineering 语义评判闭环 (verify 阶段 VLM/规则双后端)
    enable_visual_judge: bool = True        # 启用语义级视觉评判 (黑帧/特效缺失/风格跑偏)
    visual_judge_backend: str = "auto"      # vlm / rule / auto (vlm不可用时自动降级rule)
    visual_judge_min_score: float = 60.0    # 语义分达标阈值 (0-100)
    visual_judge_model_path: str = "models/weights/Qwen3-VL-8B-Instruct"  # 本地VLM权重目录 (空=仅规则后端)
    visual_judge_quantize: str = "4bit"     # none=bf16 / 4bit=nf4量化 / auto=先bf16后降级 (8B在8GB显存必须4bit)
    semantic_score_weight: float = 0.6      # 融合权重: final = (1-w)*信号分 + w*语义分

    def detect_mode(self) -> PipelineMode:
        """自动检测管线模式"""
        has_topic = bool(self.input_topic)
        has_video = bool(self.reference_video)
        if has_topic and has_video:
            return PipelineMode.MIXED
        elif has_video:
            return PipelineMode.REFERENCE_VIDEO
        else:
            return PipelineMode.TEXT_TOPIC

    def __post_init__(self) -> None:
        """配置合法性校验与边界钳制。

        修复前存在的问题:
          - max_quality_iterations=0 或负数 → 主循环 `for _ in range(0):` 一次都不执行,
            用户在无报错的情况下得不到任何输出 (静默功能退化)。
          - max_quality_iterations=2.7 等浮点数 → `range(float)` 抛 TypeError 导致崩溃。
          - max_quality_iterations=100 超大值 → 尽管 execute_multi_pass 内部有
            `min(x, 5)` 上限, 但外层主循环不应该浪费资源。
        """
        # 强制整数: 浮点 / 字符串数字 / None → 安全转 int, 失败回退到默认 3
        try:
            if isinstance(self.max_quality_iterations, bool):
                # bool 是 int 的子类, False=0 会导致静默空循环, 当作非法值处理
                iterations = 3
            else:
                iterations = int(self.max_quality_iterations)
        except (TypeError, ValueError):
            iterations = 3
        # 边界钳制: [1, 5] - 至少执行 1 轮主循环, 最多 5 轮 (与注释一致)
        if iterations < 1:
            iterations = 1
        if iterations > 5:
            iterations = 5
        self.max_quality_iterations = iterations

        # min_quality_score 同样钳制到 [0, 100] 范围 (防止越界比较)
        try:
            if isinstance(self.min_quality_score, bool):
                score = 60.0
            else:
                score = float(self.min_quality_score)
        except (TypeError, ValueError):
            score = 60.0
        if score < 0.0:
            score = 0.0
        if score > 100.0:
            score = 100.0
        self.min_quality_score = score

        # 语义评判配置钳制: 权重 [0,1], 阈值 [0,100], backend 白名单
        try:
            if isinstance(self.semantic_score_weight, bool):
                weight = 0.6
            else:
                weight = float(self.semantic_score_weight)
        except (TypeError, ValueError):
            weight = 0.6
        self.semantic_score_weight = max(0.0, min(1.0, weight))

        try:
            if isinstance(self.visual_judge_min_score, bool):
                vj_score = 60.0
            else:
                vj_score = float(self.visual_judge_min_score)
        except (TypeError, ValueError):
            vj_score = 60.0
        self.visual_judge_min_score = max(0.0, min(100.0, vj_score))

        if str(self.visual_judge_backend).lower() not in ("auto", "vlm", "rule"):
            self.visual_judge_backend = "auto"
        if str(self.visual_judge_quantize).lower() not in ("none", "4bit", "auto"):
            self.visual_judge_quantize = "auto"

    def to_dict(self) -> Dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class PipelineResult:
    """管线最终结果"""
    run_id: str
    status: str  # success / failed / partial
    mode: str = ""
    stages: Dict[str, StageResult] = field(default_factory=dict)
    output_path: str = ""
    project_path: str = ""
    total_duration_sec: float = 0.0
    quality_score: float = 0.0
    iterations: int = 0
    errors: List[str] = field(default_factory=list)
    vrs_analysis: Dict[str, Any] = field(default_factory=dict)
    kb_context: Dict[str, Any] = field(default_factory=dict)
    # P2: 渲染链路追踪 — 供进化评测器识别真实渲染引擎 (ae_render/aerender/real_mix/ffmpeg)
    render_engine: str = ""
    execution_mode: str = ""

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "mode": self.mode,
            "stages": {k: {"status": v.status.value, "duration": v.duration_sec,
                           "error": v.error} for k, v in self.stages.items()},
            "output_path": self.output_path,
            "project_path": self.project_path,
            "total_duration_sec": self.total_duration_sec,
            "quality_score": self.quality_score,
            "iterations": self.iterations,
            "errors": self.errors,
            "render_engine": self.render_engine,
            "execution_mode": self.execution_mode,
        }


# ============================================================================
#  知识库注入器
# ============================================================================

class KnowledgeInjector:
    """知识库实时注入器 — 在每个决策节点查询 KB 获取上下文。"""

    def __init__(self):
        self._loader = None

    @property
    def loader(self):
        if self._loader is None:
            try:
                from knowledge_base.kb_loader import KnowledgeBaseLoader
                self._loader = KnowledgeBaseLoader.get_instance()
            except Exception as e:
                logger.warning(f"[KB] Loader init failed: {e}")
        return self._loader

    def get_style_context(self, topic: str) -> Dict[str, Any]:
        """获取风格上下文 (规划阶段用)"""
        if not self.loader:
            return {}
        try:
            context = self.loader.get_style_context_for_prompt(topic)
            return {"style_context": context, "source": "kb_style"}
        except Exception as e:
            logger.debug(f"[KB] Style context failed: {e}")
            return {}

    def get_effect_recommendations(self, mood: str, content_type: str) -> List[Dict]:
        """获取效果推荐 (执行阶段用)"""
        if not self.loader:
            return []
        try:
            query = f"{mood} {content_type} 效果推荐"
            results = self.loader.search(query, max_results=5)
            return [{"title": r.get("title", ""), "content": r.get("content", "")[:200]}
                    for r in results]
        except Exception:
            return []

    def get_transition_recommendations(self, prev_mood: str, curr_mood: str) -> List[str]:
        """获取转场推荐"""
        if not self.loader:
            return []
        try:
            query = f"转场 {prev_mood} to {curr_mood}"
            results = self.loader.search(query, max_results=3)
            return [r.get("title", "") for r in results]
        except Exception:
            return []

    def get_color_grade_recommendations(self, style: str) -> List[str]:
        """获取调色推荐"""
        if not self.loader:
            return []
        try:
            query = f"调色 {style} cinematic"
            results = self.loader.search(query, max_results=3)
            return [r.get("title", "") for r in results]
        except Exception:
            return []

    def write_feedback(self, project_id: str, feedback: Dict[str, Any]):
        """将反馈写入知识库 (供未来项目参考)"""
        if not self.loader:
            return
        try:
            # 类型安全清洗：None/非数值 强制转float，避免比较崩溃
            raw_qs = feedback.get("quality_score")
            try:
                qs = 0.0 if raw_qs is None else float(raw_qs)
            except (TypeError, ValueError):
                qs = 0.0

            feedback_entry = {
                "project_id": project_id,
                "timestamp": datetime.now().isoformat(),
                "quality_score": qs,
                "recommendations": feedback.get("recommendations", []),
                "style_used": feedback.get("style", ""),
                "effects_used": feedback.get("effects", []),
                "success": qs >= 60.0,
            }
            # 写入反馈日志
            feedback_dir = Path(settings.feedback_dir)
            feedback_dir.mkdir(parents=True, exist_ok=True)
            feedback_file = feedback_dir / f"feedback_{project_id}.json"
            with open(feedback_file, "w", encoding="utf-8") as f:
                json.dump(feedback_entry, f, ensure_ascii=False, indent=2)
            logger.info(f"[KB] Feedback written: {feedback_file}")
        except Exception as e:
            logger.warning(f"[KB] Write feedback failed: {e}")

    def get_past_feedback(self, style: str) -> List[Dict]:
        """获取历史反馈 (同类风格的成功/失败经验)"""
        feedback_dir = Path(settings.feedback_dir)
        if not feedback_dir.exists():
            return []
        results = []
        for f in feedback_dir.glob("feedback_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    entry = json.load(fh)
                if entry.get("style_used") == style or not style:
                    results.append(entry)
            except Exception:
                continue
        return sorted(results, key=lambda x: x.get("quality_score", 0), reverse=True)[:5]


# ============================================================================
#  UnifiedPipeline v2
# ============================================================================

class UnifiedPipeline:
    """端到端视频创作管线 v2 — 融合 VRS + 多智能体 + 知识库 + 反馈闭环"""

    STAGES = ["perceive", "analyze", "plan", "execute", "render", "verify", "learn"]
    # use_compiler 模式下在 plan 前插入 compile 阶段

    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()
        self.run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.mode = self.config.detect_mode()
        self._results: Dict[str, StageResult] = {}
        self._persist_dir = Path("data/pipeline_runs") / self.run_id
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        # 延迟加载组件
        self._perception = None
        self._analysis = None
        self._planning = None
        self._execution = None
        self._rendering = None
        self._compiler = None
        self._kb = KnowledgeInjector()
        self._vrs_result: Dict[str, Any] = {}
        self._production_data = None  # VRS Bridge 转换结果
        self._iteration = 0
        self._enhanced_video_path = None  # 质量增强后的视频路径
        self._trace_prop = None  # P4: TracePropagator 延迟加载
        self._root_span = None  # P4: 根 trace span
        # P4 模块延迟加载 (graceful degrade: 任何模块初始化失败不影响管线)
        self._quality_gate = None       # P4.2 QualityGate
        self._artifact_mgr = None       # P4.3 ArtifactManager
        self._failure_pm = None         # P4.4 FailurePostmortem
        self._perf_baseline = None      # P4.5 PerformanceBaseline
        self._engine_registry = None     # P2.1 EngineRegistry
        # P4 产物血缘追踪 (art_id 列表，按 stage_name 索引)
        self._artifact_ids: Dict[str, List[str]] = {}
        self._perf_regressions: Dict[str, Dict] = {}  # P4.5b 阶段性能回归检测结果
        # 【H级修复P2-2-A#4】本run级局部配置覆盖，防止 _should_skip_stage 直接改全局 config 造成副作用
        self._local_overrides: Dict[str, Any] = {}
        # FX 节拍缓存：_extract_beats 三级降级结果按 run 缓存，避免重复 librosa 分析
        self._beats_cache: Optional[list] = None

        self._log(f"Pipeline v2 created: {self.run_id}")
        self._log(f"Mode: {self.mode.value}")
        self._log(f"Config: topic={self.config.input_topic}, ref_video={self.config.reference_video}")

        # P2.1: 惰性注册内置引擎能力到 EngineRegistry (使 select_best 可覆盖历史选择)
        self._register_builtin_engines()

    def _register_builtin_engines(self):
        """P2.1: 惰性注册内置引擎能力到 EngineRegistry。

        仅当引擎尚未注册时补充 metadata，避免覆盖外部已注册的能力定义。
        引擎类不可 JSON 序列化，故此处传占位类；历史选择仅依赖 metadata + history。
        graceful degrade: 注册失败不影响管线。
        """
        if not self.engine_registry:
            return
        try:
            from core.engine_registry import EngineMetadata
            builtins = [
                ("ae", ["execute", "render"], "high", 0.05),
                ("davinci", ["render"], "ultra", 0.08),
                ("ffmpeg", ["execute", "render"], "medium", 0.01),
                ("moviepy", ["render"], "low", 0.005),
            ]
            for name, caps, tier, cost in builtins:
                if name not in self.engine_registry.list_available():
                    self.engine_registry.register(name, object, EngineMetadata(
                        name=name, version="builtin", capabilities=caps,
                        quality_tier=tier, cost_per_sec=cost,
                    ))
            self._log("[P2.1] Builtin engines registered")
        except Exception as e:
            logger.debug(f"[P2.1] Builtin engine registration failed: {e}")

    def _select_engine_for_stage(self, stage: str, candidates: list) -> str:
        """P2.1: 基于 EngineRegistry 历史成功率选择最优引擎。

        返回被选中的引擎名；无注册/无历史/异常时返回空串，由调用方走默认逻辑。
        用于 execute / render 阶段：当策略或 M3 预测不强制降级时，
        历史成功率可驱动引擎偏好，形成"记账→学习→选择"闭环。
        """
        if not self.engine_registry:
            return ""
        try:
            best = self.engine_registry.select_best(stage, candidates=list(candidates))
            if best:
                self._log(f"[P2.1] select_best({stage}) -> {best}")
            return best or ""
        except Exception as e:
            logger.debug(f"[P2.1] select_best failed: {e}")
            return ""

    def _select_engine_with_meta(self, stage: str, candidates: list, error: Exception = None) -> str:
        """P2.4: 深度集成引擎选择 — select_with_meta (本选择器历史 + quality_tier + 策略偏好 + EngineRegistry)。

        构造 EngineCandidate 列表交给 AdaptiveFallbackSelector.select_with_meta 评分，
        融合多源信号后返回选中的引擎名。这是 select_with_meta 深集成能力的生产接线点。
        graceful degrade: 异常返回空串，调用方走默认逻辑。
        """
        try:
            selector = get_fallback_selector()
            cands = []
            for name in candidates:
                meta = None
                if self.engine_registry:
                    meta = self.engine_registry.get_metadata(name)
                cands.append(EngineCandidate(
                    path_id=f"{name}_fallback",
                    engine_name=name,
                    metadata=meta,
                ))
            chosen = selector.select_with_meta(
                stage, error, cands, context={"run_id": self.run_id}
            )
            for name in candidates:
                if chosen == f"{name}_fallback":
                    self._log(f"[P2.4] select_with_meta({stage}) -> {name}")
                    return name
            return ""
        except Exception as e:
            logger.debug(f"[P2.4] select_with_meta failed: {e}")
            return ""

    def _cfg(self, key: str, default: Any = None) -> Any:
        """【辅助】读取带本run局部覆盖的 config 值，禁止直接改全局 config 有状态副作用。"""
        if key in self._local_overrides:
            return self._local_overrides[key]
        return getattr(self.config, key, default)

    def _log(self, msg: str, level: str = "INFO"):
        ts = time.strftime("%H:%M:%S")
        try:
            print(f"  [PIPELINE v2][{ts}][{level}] {msg}")
        except (UnicodeEncodeError, OSError):
            # Windows GBK 控制台无法输出某些 Unicode 字符, 降级为 ascii
            safe = msg.encode('ascii', errors='replace').decode('ascii')
            print(f"  [PIPELINE v2][{ts}][{level}] {safe}")

    # ----------------------------------------------------------------
    #  阶段处理器（延迟加载）
    # ----------------------------------------------------------------

    @property
    def perception(self):
        if self._perception is None:
            try:
                from pipeline.stages.perception import PerceptionStage
                self._perception = PerceptionStage(self.config)
            except Exception:
                self._perception = _FallbackPerception(self.config)
        return self._perception

    @property
    def analysis(self):
        if self._analysis is None:
            try:
                from pipeline.stages.analysis import AnalysisStage
                self._analysis = AnalysisStage(self.config)
            except Exception:
                self._analysis = _FallbackAnalysis(self.config)
        return self._analysis

    @property
    def planning(self):
        if self._planning is None:
            try:
                from pipeline.stages.planning import PlanningStage
                self._planning = PlanningStage(self.config)
            except Exception:
                self._planning = _FallbackPlanning(self.config, self._kb)
        return self._planning

    @property
    def execution(self):
        if self._execution is None:
            try:
                from pipeline.stages.execution import ExecutionStage
                self._execution = ExecutionStage(self.config)
            except Exception:
                self._execution = _FallbackExecution(self.config)
        return self._execution

    @property
    def rendering(self):
        if self._rendering is None:
            try:
                from pipeline.stages.rendering import RenderingStage
                self._rendering = RenderingStage(self.config)
            except Exception:
                self._rendering = _FallbackRendering(self.config)
        return self._rendering

    @property
    def compiler(self):
        if self._compiler is None:
            try:
                from pipeline.stages.compiler import CompilerStage
                self._compiler = CompilerStage(self.config)
            except Exception:
                self._compiler = None
        return self._compiler

    @property
    def trace_prop(self):
        """P4: TracePropagator 延迟加载（避免 import 循环）"""
        if self._trace_prop is None:
            try:
                from core.observability import get_trace_propagator
                self._trace_prop = get_trace_propagator()
            except Exception as e:
                self._log(f"TracePropagator init failed: {e}", "WARN")
                self._trace_prop = None
        return self._trace_prop

    @property
    def quality_gate(self):
        """P4.2: QualityGate 延迟加载"""
        if self._quality_gate is None:
            try:
                from core.quality_gate import get_quality_gate
                self._quality_gate = get_quality_gate()
            except Exception as e:
                self._log(f"QualityGate init failed: {e}", "WARN")
                self._quality_gate = None
        return self._quality_gate

    @property
    def artifact_mgr(self):
        """P4.3: ArtifactManager 延迟加载"""
        if self._artifact_mgr is None:
            try:
                from core.artifact_manager import get_artifact_manager
                self._artifact_mgr = get_artifact_manager()
            except Exception as e:
                self._log(f"ArtifactManager init failed: {e}", "WARN")
                self._artifact_mgr = None
        return self._artifact_mgr

    @property
    def failure_pm(self):
        """P4.4: FailurePostmortem 延迟加载"""
        if self._failure_pm is None:
            try:
                from core.failure_postmortem import get_failure_postmortem
                self._failure_pm = get_failure_postmortem()
            except Exception as e:
                self._log(f"FailurePostmortem init failed: {e}", "WARN")
                self._failure_pm = None
        return self._failure_pm

    @property
    def perf_baseline(self):
        """P4.5: PerformanceBaseline 延迟加载"""
        if self._perf_baseline is None:
            try:
                from core.performance_baseline import get_performance_baseline
                self._perf_baseline = get_performance_baseline()
            except Exception as e:
                self._log(f"PerformanceBaseline init failed: {e}", "WARN")
                self._perf_baseline = None
        return self._perf_baseline

    @property
    def engine_registry(self):
        """P2.1: EngineRegistry 延迟加载"""
        if self._engine_registry is None:
            try:
                from core.engine_registry import get_engine_registry
                self._engine_registry = get_engine_registry()
            except Exception as e:
                self._log(f"EngineRegistry init failed: {e}", "WARN")
                self._engine_registry = None
        return self._engine_registry

    # ----------------------------------------------------------------
    #  运行控制
    # ----------------------------------------------------------------

    def run_all(self) -> PipelineResult:
        """运行全部阶段"""
        start = time.time()
        # C2 修复: 保存原始 materials_dir, 防止 _run_perceive 改写后污染后续 run
        _original_materials_dir = self.config.materials_dir
        self._log("=" * 60)
        self._log(f"Pipeline v2 START: {self.run_id} (mode={self.mode.value})")
        self._log("=" * 60)

        # P4: 启动全链路 trace
        if self.trace_prop:
            self._root_span = self.trace_prop.start_trace(self.run_id)
            self._log(f"[Trace] trace_id={self._root_span.trace_id}")

        # 特殊前置: VRS 逆向分析 (参考视频模式)
        if self.mode in (PipelineMode.REFERENCE_VIDEO, PipelineMode.MIXED):
            if self.config.enable_vrs and self.config.reference_video:
                self._run_vrs_analysis()

        # 知识库前置: 获取历史反馈经验
        if self.config.use_knowledge:
            self._preload_kb_experience()

        # M3: 数字孪生执行前预测
        self._run_digital_twin_prediction()

        # L1: 策略引擎选择执行策略
        self._select_execution_strategy()

        # 主循环 (支持质量迭代)
        # __post_init__ 已将 max_quality_iterations 钳制到 [1, 5] 整数;
        # 这里再使用 int() 作为纵深防御, 避免子类或外部直接修改 config 后 range(float) 崩溃
        max_iterations = (
            int(self.config.max_quality_iterations)
            if self.config.enable_feedback_loop
            else 1
        )

        for iteration in range(max_iterations):
            self._iteration = iteration
            if iteration > 0:
                self._log(f"--- Quality iteration {iteration} ---")

            for stage_name in self.STAGES:
                if stage_name in self.config.skip_stages:
                    self._results[stage_name] = StageResult(
                        stage=stage_name, status=StageStatus.SKIPPED
                    )
                    continue

                if self.config.start_from and stage_name != self.config.start_from:
                    if stage_name not in self._results:
                        continue

                # P2: 动态阶段跳过判断
                if self._should_skip_stage(stage_name):
                    self._results[stage_name] = StageResult(
                        stage=stage_name, status=StageStatus.SKIPPED,
                        data={"skip_reason": "dynamic_skip", "iteration": iteration}
                    )
                    self._log(f"Stage [{stage_name}] SKIPPED (dynamic optimization)")
                    continue

                result = self._run_stage(stage_name)
                self._results[stage_name] = result
                self._persist_stage(stage_name, result)

                if result.status == StageStatus.FAILED:
                    self._log(f"Stage {stage_name} FAILED: {result.error}", "ERROR")
                    if stage_name in ("execute", "render"):
                        break

            # 质量检查 (反馈闭环)
            if self.config.enable_feedback_loop:
                should_retry = self._check_quality_gate()
                if not should_retry:
                    break
                # 清理需要重跑的阶段
                for s in ["execute", "render", "verify", "learn"]:
                    self._results.pop(s, None)
            else:
                break

        total = time.time() - start
        pipeline_result = self._build_result(total)
        self._persist_result(pipeline_result)

        # L3: 自进化引擎 — 执行后自动学习
        self._trigger_self_evolution(pipeline_result, total)

        # 经验汲取: 将本次执行产生的日志/报告消化为结构化经验
        self._trigger_experience_harvest()

        # P0-2: 参数反馈写入 — 闭合 parameter_optimizer 的反馈腿
        self._trigger_param_feedback(pipeline_result)

        # P0-自进化闭环: 独立评测 → 版本对比 → 严格更高才接受，否则回退
        self._trigger_evolution_closed_loop(pipeline_result)

        # P4: 结束根 trace 并导出持久化
        if self._root_span and self.trace_prop:
            self.trace_prop.end_span(
                self._root_span,
                status="success" if pipeline_result.status == "success" else "error",
            )
            try:
                self.trace_prop.export_trace(self._root_span.trace_id)
                self._log(f"[Trace] exported: {self._root_span.trace_id}")
            except Exception as e:
                self._log(f"[Trace] export failed: {e}", "WARN")

        self._log("=" * 60)
        self._log(f"Pipeline v2 END: {pipeline_result.status} ({total:.1f}s)")
        if pipeline_result.quality_score > 0:
            self._log(f"Quality: {pipeline_result.quality_score:.1f} ({pipeline_result.iterations} iterations)")
        self._log("=" * 60)
        # C2 修复: 恢复原始 materials_dir, 防止跨 run 状态污染
        try:
            return pipeline_result
        finally:
            self.config.materials_dir = _original_materials_dir
    
    def _should_skip_stage(self, stage_name: str) -> bool:
        """P2: 基于上下文动态判断是否跳过阶段
        
        跳过规则:
        1. VRS已提供完整分析时，简化analyze
        2. 质量迭代时，跳过已完成的稳定阶段
        3. 配置禁用某功能时，跳过相关阶段
        4. (S3.1) 纯图片输入时，跳过perceive的运动分析
        5. (S3.2) 社交媒体竖屏时，跳过DaVinci调色
        6. (S3.3) REFERENCE_VIDEO模式下，简化analyze阶段
        7. (S3.4) KB有完整风格映射时，简化plan阶段
        """
        # 规则1: VRS已提供完整分析时，简化analyze
        if stage_name == "analyze" and self._vrs_result:
            effects = self._vrs_result.get("effects", [])
            transitions = self._vrs_result.get("transitions", [])
            if len(effects) >= 3 and len(transitions) >= 2:
                self._log(f"[P2] VRS provided rich analysis ({len(effects)} effects, {len(transitions)} transitions)")
                return False  # 保持运行，但内部可简化
        
        # 规则2: 质量迭代时，如果perceive/analyze/plan已稳定，跳过重跑
        if self._iteration > 0 and stage_name in ("perceive", "analyze", "plan"):
            prev_result = self._results.get(stage_name)
            if prev_result and prev_result.status == StageStatus.DONE:
                learn_result = self._results.get("learn")
                if learn_result and learn_result.status == StageStatus.DONE:
                    adjustments = learn_result.data.get("adjustments", [])
                    needs_adjust = any(
                        adj.get("stage") == stage_name 
                        for adj in adjustments
                    )
                    if not needs_adjust:
                        self._log(f"[P2] Skipping {stage_name}: stable from previous iteration")
                        return True
        
        # 规则3: 配置禁用某功能时，跳过相关阶段
        if stage_name == "learn" and not self.config.enable_feedback_loop:
            self._log(f"[P2] Skipping {stage_name}: feedback_loop disabled")
            return True
        
        # S3.1: 纯图片输入时，跳过perceive的运动分析（但保留perceive本身）
        if stage_name == "perceive" and self.mode == PipelineMode.TEXT_TOPIC:
            materials_dir = self.config.materials_dir
            if materials_dir:
                from pathlib import Path as _Path
                mat_path = _Path(materials_dir)
                if mat_path.exists():
                    image_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}
                    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
                    files = list(mat_path.rglob("*"))
                    has_video = any(f.suffix.lower() in video_exts for f in files if f.is_file())
                    if not has_video:
                        self._log(f"[P2/S3.1] Skipping perceive motion analysis: no video materials")
                        # 不跳过perceive，但标记为图片模式（内部可简化）
                        return False
        
        # S3.2: 社交媒体竖屏发布时，跳过DaVinci调色（直接在AE内完成）
        if stage_name == "render" and self.config.publish_platforms:
            social_platforms = {"tiktok", "douyin", "instagram", "youtube_shorts", "kuaishou"}
            is_social = any(p.lower() in social_platforms for p in self.config.publish_platforms)
            if is_social and self._cfg("use_davinci_render", False):
                self._log(f"[P2/S3.2] Skipping DaVinci render: social media vertical video, using AE only")
                # 【H级修复P2-2-A#4】不直接修改全局 config（跨run有状态副作用）
                # 改为存储在 self._local_overrides 中，仅影响本次 run 的后续读取
                self._local_overrides["use_davinci_render"] = False
                return False  # 不跳过render，但关闭DaVinci
        
        # S3.3: REFERENCE_VIDEO模式下，如果VRS已提供完整分析，简化analyze
        if stage_name == "analyze" and self.mode == PipelineMode.REFERENCE_VIDEO:
            if self._vrs_result and self._vrs_result.get("effects"):
                self._log(f"[P2/S3.3] Simplifying analyze: VRS already provided effect list")
                return False  # 保持运行但内部简化
        
        # S3.4: KB有完整风格映射时，简化plan阶段
        if stage_name == "plan" and self.config.use_knowledge:
            kb_result = self._results.get("_kb_experience")
            if kb_result and kb_result.status == StageStatus.DONE:
                kb_data = kb_result.data or {}
                style_mapping = kb_data.get("style_mapping", {})
                if style_mapping and len(style_mapping) >= 3:
                    self._log(f"[P2/S3.4] Simplifying plan: KB has {len(style_mapping)} style mappings")
                    return False  # 保持运行但内部简化
        
        # L2: 多模态融合决策辅助跳过
        try:
            fusion_result = self._results.get("_fusion_decision")
            if fusion_result and fusion_result.status == StageStatus.DONE:
                fusion_data = fusion_result.data or {}
                skip_decision = fusion_data.get("skip_stages", {})
                if skip_decision.get(stage_name, {}).get("should_skip", False):
                    confidence = skip_decision[stage_name].get("confidence", 0)
                    if confidence > 0.8:
                        self._log(f"[L2] Fusion hub suggests skip {stage_name} (confidence={confidence:.2f})")
                        return True
        except Exception:
            pass
        
        return False

    def run_stage(self, stage_name: str) -> StageResult:
        """运行单个阶段"""
        result = self._run_stage(stage_name)
        self._results[stage_name] = result
        self._persist_stage(stage_name, result)
        return result

    # ----------------------------------------------------------------
    #  VRS 逆向分析 (v2 新增)
    # ----------------------------------------------------------------

    def _run_vrs_analysis(self):
        """VRS 逆向分析 — 从参考视频提取效果/转场/调色/节奏"""
        self._log("VRS: Starting reverse engineering analysis...")
        start = time.time()

        try:
            # 尝试完整 VRS 分析
            from vrs.vrs_orchestrator import VRSOrchestrator
            vrs = VRSOrchestrator()
            # 异步调用转同步
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                vrs_result = loop.run_until_complete(
                    vrs.analyze(self.config.reference_video)
                )
            finally:
                loop.close()

            self._vrs_result = vrs_result or {}
            dur = time.time() - start
            self._log(f"VRS: Analysis complete ({dur:.1f}s)")
            self._log(f"VRS: Found {len(self._vrs_result.get('effects', []))} effects, "
                      f"{len(self._vrs_result.get('transitions', []))} transitions")

        except Exception as e:
            self._log(f"VRS: Full analysis failed: {e}, trying basic analysis", "WARN")
            # 降级: 基础视频信息提取
            self._vrs_result = self._basic_video_analysis(self.config.reference_video)

        # 将 VRS 结果注入配置上下文
        self._inject_vrs_to_config()

    def _basic_video_analysis(self, video_path: str) -> Dict:
        """基础视频分析 (VRS 不可用时降级)"""
        result = {"source": "basic_analysis", "video_path": video_path}
        try:
            import subprocess
            from pipeline.stages import resolve_ffprobe
            ffprobe = resolve_ffprobe(self.config)
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "format=duration:stream=width,height,r_frame_rate,codec_name",
                 "-of", "json", video_path],
                capture_output=True, text=True, timeout=30,
            )
            if probe.returncode == 0:
                info = json.loads(probe.stdout)
                result["format"] = info.get("format", {})
                result["streams"] = info.get("streams", [])
        except Exception:
            pass
        return result

    def _inject_vrs_to_config(self):
        """将 VRS 分析结果注入到配置中，供后续阶段使用"""
        if not self._vrs_result:
            return

        # 使用 VRSProductionBridge 转换为生产数据
        try:
            from vrs.vrs_production_bridge import VRSProductionBridge
            bridge = VRSProductionBridge(min_confidence=self.config.min_quality_score / 100)
            self._production_data = bridge.convert(self._vrs_result)
            self._log(f"VRS Bridge: {len(self._production_data.segments)} segments, "
                      f"{len(self._production_data.jsx_commands)} JSX commands")
        except Exception as e:
            self._log(f"VRS Bridge conversion failed: {e}", "WARN")
            self._production_data = None

        # 提取 VRS 发现的效果/转场/调色
        effects = self._vrs_result.get("effects", [])
        transitions = self._vrs_result.get("transitions", [])
        color_grade = self._vrs_result.get("color_grade", "")
        style = self._vrs_result.get("style", {})

        # 如果没有主题但有参考视频，从 VRS 结果生成主题
        if not self.config.input_topic and self._vrs_result:
            detected_style = style.get("name", "cinematic")
            self.config.input_topic = f"VRS replicate: {detected_style}"

        self._log(f"VRS: Injected {len(effects)} effects, {len(transitions)} transitions, "
                  f"color={color_grade} into pipeline context")

    # ----------------------------------------------------------------
    #  知识库集成 (v2 新增)
    # ----------------------------------------------------------------

    def _preload_kb_experience(self):
        """预加载历史经验"""
        style = ""
        if self._vrs_result:
            style = self._vrs_result.get("style", {}).get("name", "")
        past = self._kb.get_past_feedback(style)
        if past:
            self._log(f"KB: Found {len(past)} past project feedbacks")

        # P2-3: 加载 system_memory 历史教训，闭合“记录但不回读”死路
        lessons = self._load_system_lessons()
        if lessons:
            self._log(f"[P2-3] Loaded {len(lessons)} historical lessons from system_memory")
        
        # P2-3b: 加载 postmortem 蒸馏规则，闭合“蒸馏但不回读”死路
        distilled = self._load_postmortem_rules()
        if distilled:
            self._log(f"[P2-3b] Loaded {len(distilled)} distilled rules from postmortem archives")

        # 能力注册表回读: 预设/字体/调色/技法评分与进化提案注入决策上下文
        # 闭合"能力注册/进化提案只写不读"断点 — 主链此前从不消费 capability_registry
        capability = self._capability_feedback()
        if capability:
            self._log(
                f"[CapabilityFeedback] Re-read capability registry: "
                f"coverage={capability.get('coverage', {}).get('coverage_rate', 0):.0%} "
                f"preset_weights={len(capability.get('preset_weights', {}))} "
                f"font_recs={len(capability.get('font_recommendations', {}))}"
            )

        if past or lessons or distilled or capability:
            # 将历史经验 + 教训 + 蒸馏规则 + 能力注册表评分注入到规划上下文
            self._results["_kb_experience"] = StageResult(
                stage="_kb_experience", status=StageStatus.DONE,
                data={
                    "past_feedback": past or [],
                    "lessons": lessons,
                    "distilled_rules": distilled,
                    "capability_feedback": capability,
                }
            )

    def _load_system_lessons(self) -> List[Dict]:
        """P2-3: 从 system_memory 加载历史教训（graceful degrade）"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
            from system_memory import SystemMemory
            mem = SystemMemory()
            raw_lessons = mem.get_all_lessons()
            # 取最近 10 条教训，提取核心信息
            lessons = []
            for entry in raw_lessons[:10]:
                value = entry.get("value", {})
                lesson_text = value.get("lesson", "") if isinstance(value, dict) else str(value)
                if lesson_text:
                    lessons.append({
                        "lesson": lesson_text,
                        "context": value.get("context", {}) if isinstance(value, dict) else {},
                        "created_at": entry.get("created_at", ""),
                    })
            return lessons
        except ImportError:
            logger.debug("[P2-3] system_memory 未安装，跳过教训加载")
            return []
        except Exception as e:
            logger.debug(f"[P2-3] 教训加载失败: {e}")
            return []

    def _load_postmortem_rules(self) -> List[Dict]:
        """P2-3b: 从 data/postmortem/ 加载蒸馏规则（影响后续决策）"""
        try:
            archive_dir = Path(__file__).resolve().parent.parent / "data" / "postmortem"
            if not archive_dir.is_dir():
                return []
            rules: List[Dict] = []
            # 读取最近 5 份报告的蒸馏规则
            reports = sorted(archive_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for report_file in reports[:5]:
                try:
                    with open(report_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for rule in data.get("distilled_rules", []):
                        if rule.get("condition") and rule.get("action"):
                            rules.append(rule)
                except (json.JSONDecodeError, OSError):
                    continue
            return rules[:20]  # 最多 20 条
        except Exception as e:
            logger.debug(f"[P2-3b] 蒸馏规则加载失败: {e}")
            return []

    def _capability_feedback(self) -> Dict[str, Any]:
        """回读能力注册表/进化提案，注入决策上下文（graceful degrade）。

        闭合进化闭环读侧断点：core/evolution/capability_feedback.py 的
        CapabilityFeedbackLoop 记录了预设/字体/调色/技法的 EMA 评分与覆盖率，
        并生成 data/evolution/proposals/ 下的进化提案，但主链 pipeline 此前
        从不消费这些"学习产出"。此处统一回读能力评分与推荐权重，写入
        _kb_experience 供 plan/execute 阶段读取，让学习结果真正影响后续决策。

        Returns:
            Dict 含 preset_weights / coverage / font_recommendations /
            grading_style_recommendations；模块不可用或异常时返回空 dict。
        """
        try:
            from core.evolution.capability_feedback import get_capability_feedback
            fb = get_capability_feedback()
            return {
                "preset_weights": fb.get_preset_weights(),
                "coverage": fb.get_coverage_stats(),
                "font_recommendations": fb.get_font_recommendations(),
                "grading_style_recommendations": fb.get_grading_style_recommendations(),
            }
        except ImportError:
            logger.debug("[P2-3c] capability_feedback 未安装，跳过能力回读")
            return {}
        except Exception as e:
            logger.debug(f"[P2-3c] 能力注册表回读失败: {e}")
            return {}

    # ----------------------------------------------------------------
    #  各阶段实现
    # ----------------------------------------------------------------

    def _run_stage(self, *args, **kwargs):
        """委托 pipeline.unified_pipeline_helpers.run_stage (2026-08-14 拆分)。"""
        from pipeline.unified_pipeline_helpers import run_stage
        return run_stage(self, *args, **kwargs)


    def _extract_engine_name(self, stage_name: str, data: Optional[Dict] = None) -> str:
        """从阶段结果中提取引擎名，便于 EngineRegistry 记录真实执行的引擎"""
        if data:
            for key in ("render_engine", "engine", "execution_mode", "engine_name"):
                val = data.get(key)
                if val:
                    return str(val)
        return stage_name

    def _extract_quality_score(self, data: Optional[Dict]) -> float:
        """从阶段结果中提取质量分 (0-100)；异常样本或无分时默认成功满分 100"""
        if not data:
            return 100.0
        if data.get("is_error_sample", False):
            return 0.0
        for key in ("final_score", "score", "quality_score", "vmaf_score"):
            try:
                val = data.get(key)
                if val is not None:
                    return min(100.0, max(0.0, float(val)))
            except (TypeError, ValueError):
                continue
        return 100.0

    def _extract_stage_artifact_path(self, stage_name: str, data: Optional[Dict]) -> str:
        """从阶段结果中提取已落盘的产物文件路径"""
        if not data:
            return ""
        for key in ("output_path", "project_path", "script_path", "report_path", "json_path"):
            path = data.get(key)
            if path and Path(path).exists():
                return str(path)
        return ""

    def _artifact_type_for_stage(self, stage_name: str) -> str:
        """根据阶段名推断产物类型 (perceive/analyze/plan/execute/render/verify/learn)"""
        mapping = {
            "perceive": "config",
            "analyze": "report",
            "plan": "script",
            "execute": "video",
            "render": "video",
            "verify": "report",
            "learn": "report",
        }
        return mapping.get(stage_name, "other")

    def _record_stage_success(self, stage_name: str, data: Optional[Dict], duration: float):
        """P2.1/P4.3/P4.5: 成功阶段统一登记 — 引擎执行历史 + 产物血缘 + 性能基线"""
        engine = self._extract_engine_name(stage_name, data)
        quality = self._extract_quality_score(data)

        # P2.1: 引擎执行历史 (供 select_best 用于后续引擎选择)
        if self.engine_registry:
            try:
                self.engine_registry.record_execution(
                    engine_name=engine,
                    success=True,
                    duration=duration,
                    quality=quality,
                    stage=stage_name,
                )
            except Exception as e:
                logger.debug(f"[P2.1] engine_registry record failed: {e}")

        # P4.5: 性能基线 (供回归检测 / 趋势分析)
        if self.perf_baseline:
            try:
                self.perf_baseline.record_baseline(
                    name=f"stage/{stage_name}",
                    metrics={
                        "duration_sec": round(duration, 3),
                        "quality_score": round(quality, 1),
                    },
                    note=f"run_id={self.run_id}",
                )
                # P4.5b: 回归检测 — 与历史基线对比，发现性能退化并记录
                self._check_performance_regression(stage_name, duration, quality)
            except Exception as e:
                logger.debug(f"[P4.5] perf baseline record failed: {e}")

        # P4.3: 产物血缘注册
        if self.artifact_mgr:
            try:
                from core.artifact_manager import Artifact
                artifact = Artifact(
                    type=self._artifact_type_for_stage(stage_name),
                    stage=stage_name,
                    path=self._extract_stage_artifact_path(stage_name, data),
                    run_id=self.run_id,
                    parent_ids=list(self._artifact_ids.get(stage_name, [])),
                    metadata={"engine": engine, "quality": round(quality, 1)},
                )
                aid = self.artifact_mgr.register(artifact)
                self._artifact_ids[stage_name] = [aid]
            except Exception as e:
                logger.debug(f"[P4.3] artifact register failed: {e}")

    def _check_performance_regression(self, stage_name: str, duration: float, quality: float):
        """P4.5b: 性能回归检测 — 与历史基线对比，将回归结果写入 _results 供决策。

        首次记录后从第二次起，用 compare_current + detect_regression 检查
        duration(越低越好) 与 quality(越高越好) 是否相对基线退化超过阈值。
        闭合"perf_baseline 只写不读"断点。graceful degrade: 失败不影响。
        """
        try:
            name = f"stage/{stage_name}"
            comparison = self.perf_baseline.compare_current(
                name,
                {"duration_sec": round(duration, 3), "quality_score": round(quality, 1)},
            )
            # 写入独立属性而非 _results (避免干扰 StageResult 集合)
            if not hasattr(self, "_perf_regressions"):
                self._perf_regressions = {}
            self._perf_regressions[stage_name] = comparison.to_dict()
            if comparison.overall_status == "regression":
                regs = self.perf_baseline.detect_regression(comparison)
                self._log(
                    f"[P4.5b] Performance regression in '{stage_name}': "
                    f"{[r.metric for r in regs]}"
                )
        except Exception as e:
            logger.debug(f"[P4.5b] Regression check skipped: {e}")

    def _record_stage_failure(self, stage_name: str, error_msg: str, duration: float):
        """P2.1: 失败阶段记录引擎执行 (供历史成功率统计，辅助降级选择)"""
        if self.engine_registry:
            try:
                self.engine_registry.record_execution(
                    engine_name=stage_name,
                    success=False,
                    duration=duration,
                    quality=0.0,
                    stage=stage_name,
                )
            except Exception as e:
                logger.debug(f"[P2.1] engine_registry failure record failed: {e}")

    def _query_error_memory(self, error: Exception, stage_name: str) -> Optional[Dict]:
        """P0: 查询错误记忆库获取修复方案"""
        try:
            from pipeline.feedback_loop import get_error_memory
            memory = get_error_memory()
            context = {"stage": stage_name, "run_id": self.run_id}
            return memory.find_similar_error(error, context)
        except Exception as e:
            logger.debug(f"[P0] Error memory query failed: {e}")
            return None
    
    def _record_error_pattern(self, error: Exception, stage_name: str, attempt: int):
        """P0: 记录错误模式到记忆库"""
        try:
            from pipeline.feedback_loop import get_error_memory
            memory = get_error_memory()
            context = {
                "stage": stage_name,
                "run_id": self.run_id,
                "attempt": attempt,
                "iteration": self._iteration,
            }
            # 记录错误（尚未应用修复，success=False）
            memory.record_error(
                error=error,
                context=context,
                fix_applied="pending",  # 待后续确定
                success=False
            )
        except Exception as e:
            logger.debug(f"[P0] Error pattern recording failed: {e}")

    def _llm_diagnose_error(self, error: Exception, stage_name: str) -> Optional[Dict]:
        """P1: LLM辅助错误诊断（同步包装，内部调用规则引擎 + 可选LLM）"""
        try:
            from core.error_diagnostician import get_diagnostician
            diagnostician = get_diagnostician()
            context = {
                "stage": stage_name,
                "run_id": self.run_id,
                "iteration": self._iteration,
                "mode": self.mode.value if hasattr(self.mode, 'value') else str(self.mode),
            }
            # 同步调用：规则引擎诊断（LLM部分在同步模式下跳过）
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 已在异步环境中，仅用规则引擎
                    result = diagnostician._rule_based_diagnose(error, context)
                else:
                    result = loop.run_until_complete(
                        diagnostician.diagnose(error, context, use_llm=True)
                    )
            except RuntimeError:
                # 无事件循环，创建新的
                result = asyncio.run(diagnostician.diagnose(error, context, use_llm=True))
            
            if result.success:
                return {
                    "fix_type": result.fix_type.name,
                    "fix_description": result.fix_description,
                    "fix_code": result.fix_code,
                    "confidence": result.confidence,
                    "root_cause": result.root_cause,
                    "source": result.source,
                }
            return None
        except Exception as e:
            logger.debug(f"[P1] LLM diagnose failed: {e}")
            return None

    def _query_causal_engine(self, error: Exception, stage_name: str) -> Optional[Dict]:
        """M1: 查询因果引擎获取跨引擎诊断"""
        try:
            from core.causal_engine import get_causal_engine, EngineFailure, EngineType, Intervention
            import asyncio
            engine = get_causal_engine()
            
            # 推断引擎类型
            engine_type = EngineType.PIPELINE
            if stage_name in ("execute", "render"):
                if self.config.use_ae_render:
                    engine_type = EngineType.AE
                elif self.config.use_davinci_render:
                    engine_type = EngineType.DAVINCI
            else:
                engine_type = EngineType.FFMPEG
            
            failure = EngineFailure(
                engine=engine_type,
                stage=stage_name,
                error_msg=str(error),
                error_type=type(error).__name__
            )
            intervention = Intervention(
                target_node=f"{engine_type.value}_{stage_name}",
                action="retry",
                description=f"重试 {stage_name}"
            )
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return None  # 异步环境中跳过
                result = loop.run_until_complete(
                    engine.counterfactual_query(failure, intervention)
                )
            except RuntimeError:
                result = asyncio.run(
                    engine.counterfactual_query(failure, intervention)
                )
            
            return {
                "causal_effect": result.causal_effect,
                "confidence": result.confidence,
                "explanation": result.explanation,
                "reasoning": result.counterfactual
            }
        except Exception as e:
            logger.debug(f"[M1] Causal engine query failed: {e}")
            return None

    def _count_materials(self) -> int:
        """统计素材目录下的媒体文件数，供数字孪生输入规格使用。"""
        try:
            md = self.config.materials_dir
            if not md:
                return 0
            p = Path(md)
            if not p.exists():
                return 0
            if p.is_file():
                return 1
            exts = (".mp4", ".mov", ".mkv", ".avi", ".flv", ".webm", ".png", ".jpg", ".jpeg")
            return sum(1 for f in p.rglob("*") if f.suffix.lower() in exts)
        except Exception:
            return 0

    def _run_digital_twin_prediction(self):
        """M3: 数字孪生执行前预测"""
        try:
            from core.pipeline_digital_twin import get_digital_twin, InputSpecification, PipelineConfig
            import asyncio
            twin = get_digital_twin()
            
            input_spec = InputSpecification(
                material_count=self._count_materials(),
                total_duration_sec=int(getattr(self.config, 'max_duration', 60) or 60),
                has_reference_video=bool(self.config.reference_video)
            )
            config = PipelineConfig(
                mode=self.mode.value if hasattr(self.mode, 'value') else str(self.mode),
                enable_vrs=self.config.enable_vrs,
                enable_feedback_loop=self.config.enable_feedback_loop,
                use_davinci_render=self.config.use_davinci_render,
                use_ae_render=bool(getattr(self.config, 'use_ae_render', False)),
                publish_platforms=self.config.publish_platforms or []
            )
            
            try:
                # 统一用 asyncio.run 创建独立事件循环，避免 get_event_loop 在
                # 3.11+/异步环境下的歧义导致预测被跳过
                prediction = asyncio.run(
                    twin.predict_execution(input_spec, config)
                )
            except RuntimeError as e:
                logger.debug(f"[M3] Digital twin predict failed (loop): {e}")
                return
            
            # 记录预测结果
            report = twin.generate_report(prediction)
            self._log(f"[M3] Digital Twin Prediction:\n{report}")
            
            self._results["_twin_prediction"] = StageResult(
                stage="_twin_prediction",
                status=StageStatus.DONE,
                data={"prediction": {
                    "total_duration": prediction.total_predicted_duration,
                    "overall_success_rate": prediction.overall_success_rate,
                    "quality": prediction.predicted_output_quality,
                    "critical_path": prediction.critical_path
                }}
            )
        except Exception as e:
            logger.debug(f"[M3] Digital twin prediction failed: {e}")

    def _build_engine_history_context(self) -> Dict[str, Any]:
        """P2.1: 汇总 EngineRegistry 历史统计，作为策略引擎的决策先验。

        将各引擎在 execute/render 上的成功率/平均质量/平均耗时注入 user_constraints，
        使 L1 策略选择能感知历史成功闭环。graceful degrade: 不可用返回空 dict。
        """
        if not self.engine_registry:
            return {}
        try:
            engines = self.engine_registry.list_available()
            stats = {}
            best = {}
            for eng in engines:
                st = self.engine_registry.get_statistics(eng)
                if st.get("total", 0) > 0:
                    stats[eng] = {
                        "success_rate": round(st.get("success_rate", 0.5), 3),
                        "avg_quality": round(st.get("avg_quality", 50.0), 1),
                        "avg_duration": round(st.get("avg_duration", 30.0), 1),
                    }
                for stage in ("execute", "render"):
                    b = self.engine_registry.select_best(stage, candidates=[eng])
                    if b:
                        best[eng] = stage
            ctx = {"engine_stats": stats, "engine_best_stage": best}
            if stats:
                self._log(f"[P2.1] Strategy sees engine history: {list(stats.keys())}")
            return ctx
        except Exception as e:
            logger.debug(f"[P2.1] build engine history context failed: {e}")
            return {}

    def _select_execution_strategy(self):
        """L1: 策略引擎选择执行策略"""
        try:
            from core.meta_strategy_engine import get_strategy_engine, TaskContext
            import asyncio
            engine = get_strategy_engine()
            
            context = TaskContext(
                task_id=self.run_id,
                mode=self.mode.value if hasattr(self.mode, 'value') else str(self.mode),
                available_engines=["ae"] + (["davinci"] if self.config.use_davinci_render else []) + ["ffmpeg"],
                priority="balanced",
                user_constraints=self._build_engine_history_context(),
            )
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return
                selection = loop.run_until_complete(
                    engine.select_strategy(context)
                )
            except RuntimeError:
                selection = asyncio.run(engine.select_strategy(context))
            
            # 安全检查
            guardrail = engine.safety_guardrail(selection)
            if not guardrail.get("safe", True):
                self._log(f"[L1] Safety guardrail: {guardrail.get('reason', '')}")
                if guardrail.get("action") == "fallback_to_default":
                    return  # 使用默认策略
            
            self._log(f"[L1] Strategy selected: {selection.selected_strategy.name} "
                     f"(confidence={selection.confidence:.2f})")
            
            self._results["_strategy_selection"] = StageResult(
                stage="_strategy_selection",
                status=StageStatus.DONE,
                data={
                    "strategy_id": selection.selected_strategy.strategy_id,
                    "strategy_name": selection.selected_strategy.name,
                    "confidence": selection.confidence,
                    "reasoning": selection.reasoning
                }
            )
        except Exception as e:
            logger.debug(f"[L1] Strategy selection failed: {e}")

    def _trigger_self_evolution(self, pipeline_result, total_duration: float):
        """L3: 触发自进化引擎"""
        try:
            from core.self_evolution_engine import get_evolution_engine, ExecutionRecord
            import asyncio
            engine = get_evolution_engine()
            
            # 构建执行记录
            stages_data = {}
            for stage_name, result in self._results.items():
                if stage_name.startswith("_"):
                    continue
                stages_data[stage_name] = {
                    "success": result.status == StageStatus.DONE if hasattr(result, 'status') else False,
                    "duration": result.duration_sec if hasattr(result, 'duration_sec') else 0,
                    "error": result.error if hasattr(result, 'error') else ""
                }
            
            record = ExecutionRecord(
                run_id=self.run_id,
                timestamp=time.time(),
                stages=stages_data,
                success=pipeline_result.status.value == "success" if hasattr(pipeline_result.status, 'value') else False,
                output_quality=pipeline_result.quality_score if hasattr(pipeline_result, 'quality_score') else 0,
                total_duration=total_duration,
                strategy_id=self._results.get("_strategy_selection", StageResult(stage="", status=StageStatus.SKIPPED)).data.get("strategy_id", "") if self._results.get("_strategy_selection") else ""
            )
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    return
                review = loop.run_until_complete(
                    engine.post_execution_review(record)
                )
            except RuntimeError:
                review = asyncio.run(engine.post_execution_review(record))
            
            self._log(f"[L3] Self-evolution review: quality={review.quality.overall_score:.1f}, "
                     f"deviation={review.prediction_deviation:.3f}")
        except Exception as e:
            logger.debug(f"[L3] Self-evolution failed: {e}")

    def _trigger_experience_harvest(self):
        """经验汲取: 将本次执行产生的日志消化为结构化经验
        
        增量模式: 只处理上次汲取后新增/修改的文件，避免重复注入。
        性能保护: 单次汲取耗时超过5s则跳过（不阻塞主管线）。
        """
        try:
            from core.experience_harvester import ExperienceHarvester
            # project_root 指向项目根目录(即 output_dir 的上级目录的上级)
            # 用 Path 安全解析，避免字符串无 .parent 属性
            try:
                out_dir = Path(self.config.output_dir)
                project_root = str(out_dir.resolve().parent.parent)
            except Exception:
                project_root = "."

            # 性能保护: 首跑全量扫描可能耗时，用线程超时(30s)避免阻塞主管线；
            # harvest_incremental 内部带解析预算截断，超预算时未处理文件留待下次，
            # 因此放宽超时不会导致主管线长时间等待（后台线程 + shutdown(wait=False)）。
            import concurrent.futures
            harvester = ExperienceHarvester(project_root=project_root)
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = executor.submit(harvester.harvest_incremental)
            try:
                report = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                self._log("[Harvest] Timed out (>30s), skipped", "WARN")
                self._results["_harvest"] = StageResult(
                    stage="_harvest", status=StageStatus.SKIPPED,
                    data={"timed_out": True},
                )
                executor.shutdown(wait=False)
                return
            executor.shutdown(wait=False)
            summary = {
                "total_records_extracted": report.total_records_extracted,
                "total_stage_experiences": report.total_stage_experiences,
                "total_sources_scanned": report.total_sources_scanned,
            }
            # 写入 _results 形成可观测闭环（供验收/后续阶段读取）
            self._results["_harvest"] = StageResult(
                stage="_harvest", status=StageStatus.DONE, data=summary
            )
            if report.total_records_extracted > 0:
                self._log(f"[Harvest] +{report.total_records_extracted} records, "
                         f"{report.total_stage_experiences} stage experiences")
        except Exception as e:
            logger.debug(f"[Harvest] Experience harvest skipped: {e}")

    def _trigger_param_feedback(self, pipeline_result):
        """P0-2: 将本次执行的效果参数写入 FeedbackStore，闭合反馈驱动优化的写侧

        修复目标：parameter_optimizer.record_feedback 此前无生产调用者，
        导致 FeedbackStore 恒为空，'反馈驱动优化'退化为纯规则表。
        现在管线成功完成后，自动将效果参数 + 质量评分写入反馈存储。
        """
        try:
            # 仅在管线成功/部分成功时记录反馈
            status = pipeline_result.status if hasattr(pipeline_result, 'status') else "failed"
            if status == "failed":
                return

            # 从 plan 阶段提取 effect_stack
            plan_result = self._results.get("plan")
            if not plan_result or not hasattr(plan_result, 'data') or not plan_result.data:
                return
            effect_stack = plan_result.data.get("effect_stack", [])
            if not effect_stack:
                return

            # 从 verify 阶段提取质量评分作为 rating (0-1)
            quality_score = pipeline_result.quality_score if hasattr(pipeline_result, 'quality_score') else 0
            rating = max(0.0, min(1.0, quality_score / 100.0)) if quality_score > 1 else max(0.0, min(1.0, quality_score))
            # 如果无质量评分但管线成功，给予基础正反馈
            if rating <= 0 and status == "success":
                rating = 0.6

            # 提取风格名
            style_name = None
            if self._vrs_result and isinstance(self._vrs_result, dict):
                style_name = self._vrs_result.get("style", {}).get("name")

            from learning.parameter_optimizer import enhanced_optimizer

            recorded_count = 0
            for effect in effect_stack:
                effect_name = effect.get("matchName") or effect.get("id") or effect.get("name", "")
                if not effect_name:
                    continue
                params = effect.get("params", {})
                if not params:
                    continue

                enhanced_optimizer.record_feedback(
                    effect_name=effect_name,
                    parameters=params,
                    rating=rating,
                    style_name=style_name,
                    adjustment=None,  # 无用户手动调整
                )
                recorded_count += 1

            if recorded_count > 0:
                self._log(f"[P0-2] Param feedback recorded: {recorded_count} effects, rating={rating:.2f}")
        except Exception as e:
            logger.debug(f"[P0-2] Param feedback skipped: {e}")

    def _trigger_evolution_closed_loop(self, pipeline_result):
        """P0-自进化闭环 (借鉴 PenguinHarness): 评测 → 版本对比 → 严格回退

        流程:
            1. 将管线结果规范化为独立 Evaluator 可消费的字典 (解耦)
            2. Evaluator 双通道评分 (确定性指标 + LLM Rubrics 语义评分)
            3. 创建候选版本 (配置快照, 文件即真相)
            4. 严格对比: 仅当 score > best + epsilon 才接受, 否则回退
            5. 决策写入 data/versions/decision_log.jsonl (可审计)

        任何异常都不会中断主管线 (进化是增强, 不是依赖)。
        """
        if not getattr(self.config, "enable_evolution", False):
            return
        try:
            from core.evolution import get_evolution_runner

            # 规范化阶段数据 — Evaluator 与被测管线完全解耦
            stages_norm = {}
            for name, r in self._results.items():
                stages_norm[name] = {
                    "status": getattr(r.status, "value", str(r.status)),
                    "data": r.data if isinstance(r.data, dict) else {},
                    "error": getattr(r, "error", "") or "",
                }

            pr_dict = {
                "run_id": pipeline_result.run_id,
                "status": pipeline_result.status,
                "mode": pipeline_result.mode,
                "output_path": pipeline_result.output_path,
                "project_path": getattr(pipeline_result, "project_path", ""),
                "total_duration_sec": pipeline_result.total_duration_sec,
                "quality_score": pipeline_result.quality_score,
                "iterations": pipeline_result.iterations,
                "stages": stages_norm,
            }

            # 配置快照 — 版本回退时可恢复 (P1 由 Optimizer 消费)
            snapshot = {}
            try:
                snapshot = {"config": self.config.to_dict()}
            except Exception:
                pass

            # 性能保护: record_pipeline_run 内部 Rubrics LLM 评分(3次采样)可能较慢，
            # 用线程超时(120s)避免进化阻塞主管线收尾；超时后 shutdown(wait=False)
            # 让后台线程自行退出，不阻塞主管线。
            import concurrent.futures
            runner = get_evolution_runner()
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            # 位置参数: (pipeline_result, scope="", config_snapshot=snapshot)
            # 此前把 snapshot(dict) 误传为 scope，导致 VersionManager 用 dict 做 key 报 unhashable
            future = executor.submit(runner.record_pipeline_run, pr_dict, "", snapshot)
            try:
                decision = future.result(timeout=120)
            except concurrent.futures.TimeoutError:
                self._log("[Evolution] record_pipeline_run timed out (>120s), skipped", "WARN")
                executor.shutdown(wait=False)
                return
            executor.shutdown(wait=False)
            if decision:
                self._log(
                    f"[Evolution] score={decision.score:.1f} best={decision.best_score:.1f} "
                    f"→ {decision.decision} ({decision.reason})"
                )
                # 将进化决策附加到结果中 (下划线前缀 = 不参与主状态判定)
                self._results["_evolution"] = StageResult(
                    stage="_evolution",
                    status=StageStatus.DONE,
                    data=decision.to_dict(),
                )
        except Exception as e:
            self._log(f"[Evolution] closed loop skipped: {e}", "WARN")

    def _trigger_failure_postmortem(self, stage_name: str, error_msg: str, exception: Optional[Exception] = None):
        """P1-3: 失败复盘 — 将阶段失败自动接入 failure_postmortem 进行根因分析

        修复目标：failure_postmortem 模块此前完全脱离生产管线，
        现在每次阶段失败后自动生成复盘报告并归档，形成可检索的失败知识库。
        """
        try:
            from core.failure_postmortem import get_failure_postmortem, FailureRecord
            import traceback

            tb_str = ""
            if exception:
                tb_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))

            record = FailureRecord(
                run_id=self.run_id,
                stage=stage_name,
                error_type=type(exception).__name__ if exception else "UnknownError",
                error_message=error_msg or "unknown",
                traceback_str=tb_str,
                context={
                    "mode": self.mode.value,
                    "iteration": self._iteration,
                    "topic": self.config.input_topic or "",
                },
                trace_id=self._root_span.trace_id if self._root_span else "",
            )

            pm = get_failure_postmortem()
            report = pm.analyze(record)
            pm.archive_report(report)

            self._log(
                f"[P1-3] Failure postmortem archived: sig={report.signature.signature[:8]} "
                f"root_causes={len(report.root_causes)} rules={len(report.distilled_rules)}"
            )
        except ImportError:
            logger.debug("[P1-3] failure_postmortem 未安装，跳过复盘")
        except Exception as e:
            logger.warning(f"[P1-3] Failure postmortem 异常: {e}")

    # ------------------------------------------------------------------
    #  开源项目集成辅助方法 (项目1-4)
    # ------------------------------------------------------------------

    def _preprocess_materials(self) -> Dict:
        """项目1: Auto-Editor 素材预处理(去静音/去静止)"""
        try:
            materials_dir = self.config.materials_dir
            if not materials_dir or not Path(materials_dir).exists():
                return {"skipped": True, "reason": "no materials_dir"}

            from integrations.auto_editor_adapter import AutoEditorAdapter
            adapter = AutoEditorAdapter(ffmpeg_bin=self.config.ffmpeg_bin)
            if not adapter.available:
                return {"skipped": True, "reason": "auto-editor/ffmpeg not available"}

            # 找到视频文件
            video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
            mat_path = Path(materials_dir)
            videos = [f for f in mat_path.rglob("*") if f.suffix.lower() in video_exts and f.is_file()]
            if not videos:
                return {"skipped": True, "reason": "no video files"}

            # 只对第一个视频做静音检测(不剪除，仅报告)
            segments = adapter.detect_silence_segments(str(videos[0]))
            return {
                "skipped": False,
                "videos_found": len(videos),
                "silence_segments": len(segments),
                "total_silence_sec": sum(s["duration"] for s in segments),
                "first_video": str(videos[0].name),
            }
        except Exception as e:
            logger.debug(f"[P1/AutoEditor] Preprocess skipped: {e}")
            return {"skipped": True, "reason": str(e)}

    def _generate_beat_timeline(self) -> Dict:
        """项目4: Mugen 节奏卡点规划"""
        try:
            audio_path = self.config.audio_path
            if not audio_path or not Path(audio_path).exists():
                return {"available": False, "reason": "no audio"}

            from integrations.mugen_beat_adapter import MugenBeatAdapter
            adapter = MugenBeatAdapter()
            timeline = adapter.generate_cut_timeline(
                audio_path, events_speed="1/2"  # 默认每两拍切一次
            )
            if timeline.error:
                return {"available": False, "reason": timeline.error}

            return {
                "available": True,
                "bpm": timeline.bpm,
                "n_cuts": timeline.n_cuts,
                "cut_points": timeline.cut_points[:50],  # 最多50个切点
                "method": timeline.method,
                "total_duration": timeline.total_duration,
            }
        except Exception as e:
            logger.debug(f"[P4/Mugen] Beat timeline skipped: {e}")
            return {"available": False, "reason": str(e)}

    def _moviepy_fallback_render(self, data: Dict, prev: Dict) -> Dict:
        """项目3: MoviePy 降级渲染(当AE/DaVinci无输出时)"""
        try:
            from integrations.moviepy_renderer import MoviePyRenderer
            renderer = MoviePyRenderer(ffmpeg_bin=self.config.ffmpeg_bin)
            if not renderer.available:
                return data

            # 尝试从素材目录拼接一个基础视频
            materials_dir = self.config.materials_dir
            if not materials_dir or not Path(materials_dir).exists():
                return data

            video_exts = {".mp4", ".mov", ".avi", ".mkv"}
            mat_path = Path(materials_dir)
            videos = sorted(
                [str(f) for f in mat_path.rglob("*")
                 if f.suffix.lower() in video_exts and f.is_file()]
            )[:10]  # 最多10个片段

            if not videos:
                return data

            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = str(output_dir / f"{self.run_id}_fallback.mp4")

            result = renderer.concatenate_clips(videos, output=output_path)
            if result.success:
                self._log(f"[P3/MoviePy] Fallback render: {result.output_path}")
                data["output_path"] = result.output_path
                data["render_mode"] = "moviepy_fallback"
                data["file_size"] = int(result.file_size_mb * 1024 * 1024)
            return data
        except Exception as e:
            logger.debug(f"[P3/MoviePy] Fallback render skipped: {e}")
            return data

    def _assess_vmaf_quality(self, output_path: str) -> Optional[Dict]:
        """项目2: VMAF 感知质量评估"""
        try:
            from integrations.vmaf_quality_adapter import VMAFAdapter
            adapter = VMAFAdapter(ffmpeg_bin=self.config.ffmpeg_bin)
            if not adapter.available:
                return None

            reference = self.config.reference_video or ""
            result = adapter.assess_quality(
                output_path, reference=reference,
                threshold=self.config.min_quality_score
            )
            if not result.success:
                return None

            return {
                "score": result.vmaf_score,
                "ssim": result.ssim_score,
                "psnr": result.psnr_score,
                "passed": result.passed,
                "method": result.method,
                "worst_segment": result.worst_segment,
            }
        except Exception as e:
            logger.debug(f"[P2/VMAF] Quality assessment skipped: {e}")
            return None

    def _run_perceive(self) -> Dict:
        """感知阶段：收集素材信息 + KB 注入 + 素材预处理(Auto-Editor) + 素材扫描"""
        data = self.perception.run(self._get_previous_data())
        # v2: KB 注入素材推荐
        if self.config.use_knowledge and self.config.input_topic:
            data["kb_material_hints"] = self._kb.get_effect_recommendations(
                self.config.input_topic, "material"
            )
        # 项目1集成: Auto-Editor 素材预处理(去静音/去静止)
        data["preprocess"] = self._preprocess_materials()
        # P0: 素材扫描器 — 结构化元数据供 plan/execute 消费
        if self.config.materials_dir and Path(self.config.materials_dir).exists():
            try:
                from pipeline.material_scanner import MaterialScanner
                scanner = MaterialScanner(
                    ffprobe_bin=self._cfg("ffprobe_bin", "") or _paths_ffprobe()
                )
                scan_result = scanner.scan(self.config.materials_dir)
                data["material_scan"] = scan_result.to_dict()
                data["material_plan"] = scanner.get_plan_materials(scan_result)
                self._log(
                    f"[PERCEIVE] MaterialScanner: {len(scan_result.videos)} videos, "
                    f"{scan_result.total_video_duration:.0f}s total, "
                    f"scan={scan_result.scan_time_sec:.1f}s"
                )
            except Exception as e:
                self._log(f"[PERCEIVE] MaterialScanner failed: {e}", "WARN")
        # P1-Stock: 无水印素材自动获取 (Pexels + Pixabay)
        # 当本地素材不足时，自动从素材库下载无水印视频
        stock_videos = data.get("material_scan", {}).get("videos", [])
        if len(stock_videos) < 3 and self.config.input_topic:
            try:
                from pipeline.stock_footage import get_stock_client
                client = get_stock_client()
                query = client.translate_query(self.config.input_topic)
                self._log(f"[PERCEIVE-Stock] Fetching stock footage: '{query}' (topic='{self.config.input_topic}')")
                downloaded = client.search_and_download(query, count=5, min_width=1280, min_height=720)
                if downloaded:
                    data["stock_footage"] = downloaded
                    data["stock_footage_query"] = query
                    # 更新 materials_dir 指向素材缓存目录
                    stock_dir = str(Path(downloaded[0]).parent)
                    if not self.config.materials_dir or not Path(self.config.materials_dir).exists():
                        self.config.materials_dir = stock_dir
                    self._log(f"[PERCEIVE-Stock] Downloaded {len(downloaded)} watermark-free videos -> {stock_dir}")
                    # 重新扫描素材
                    try:
                        from pipeline.material_scanner import MaterialScanner
                        scanner = MaterialScanner(ffprobe_bin=_paths_ffprobe())
                        scan_result = scanner.scan(stock_dir)
                        if scan_result.videos:
                            data["material_scan"] = scan_result.to_dict()
                            data["material_plan"] = scanner.get_plan_materials(scan_result)
                            self._log(f"[PERCEIVE-Stock] Re-scan: {len(scan_result.videos)} videos, {scan_result.total_video_duration:.0f}s")
                    except Exception as e2:
                        self._log(f"[PERCEIVE-Stock] Re-scan failed: {e2}", "WARN")
                else:
                    self._log("[PERCEIVE-Stock] No stock footage downloaded", "WARN")
            except Exception as e:
                self._log(f"[PERCEIVE-Stock] Stock footage failed: {e}", "WARN")
        # P1: 注入 VRS 真分析结果（已在前置 _run_vrs_analysis 中产出）
        # 让 perceive 阶段返回值携带 vrs_result，供 analyze/plan 阶段消费
        if self._vrs_result:
            data["vrs_result"] = self._vrs_result
        return data

    def _run_analyze(self) -> Dict:
        """分析阶段：深度分析 + VRS 结果融合 + 多模态融合决策"""
        data = self.analysis.run(self._get_previous_data())
        # v2: 融合 VRS 分析结果
        if self._vrs_result:
            data["vrs_analysis"] = self._vrs_result
            data["effects_detected"] = self._vrs_result.get("effects", [])
            data["transitions_detected"] = self._vrs_result.get("transitions", [])
            data["color_grade_detected"] = self._vrs_result.get("color_grade", "")
        # v2: 融合 VRS Bridge 生产数据
        if self._production_data:
            data["vrs_production"] = self._production_data.to_pipeline_context()
            data["vrs_segments"] = [s.to_dict() for s in self._production_data.segments]
            data["vrs_jsx"] = self._production_data.jsx_commands
        # P3: 多模态融合决策 (视觉/音频/文本 → 效果选择 + 参数调整)
        fusion = self._run_multimodal_fusion(data)
        if fusion:
            data["multimodal_fusion"] = fusion
        return data

    def _run_multimodal_fusion(self, data: Dict) -> Optional[Dict]:
        """P3: 多模态融合决策 — 将 MultimodalFusionHub 接入 analyze 阶段。

        用 topic 文本 + VRS 风格/效果 + 音频路径，通过融合决策头产出
        select_effect / tune_params 建议，写入 analyze 结果供 plan/execute 消费。
        graceful degrade: hub 不可用或不含文本模态时返回 None，不影响 analyze。
        """
        try:
            from core.multimodal_fusion_hub import get_fusion_hub
            hub = get_fusion_hub()
            text_desc = self.config.input_topic or ""
            if not text_desc:
                return None
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                embedding = loop.run_until_complete(
                    hub.encode_all(
                        video_path=self.config.reference_video or None,
                        audio_path=self.config.audio_path or None,
                        text_description=text_desc,
                    )
                )
                eff_decision = loop.run_until_complete(
                    hub.fused_decision(embedding, "select_effect", context={"run_id": self.run_id})
                )
                tune_decision = loop.run_until_complete(
                    hub.fused_decision(embedding, "tune_params", context={"run_id": self.run_id})
                )
            finally:
                loop.close()
            hub.record_decision(eff_decision)
            hub.record_decision(tune_decision)
            result = {
                "selected_effect": eff_decision.decision,
                "effect_confidence": eff_decision.confidence,
                "param_adjustments": tune_decision.decision,
                "modality_weights": eff_decision.modality_contributions,
                "alignment_quality": embedding.alignment_quality,
                "reasoning": f"{eff_decision.reasoning} | {tune_decision.reasoning}",
            }
            self._log(
                f"[P3] Multimodal fusion -> effect={result['selected_effect']} "
                f"conf={result['effect_confidence']:.2f} params={result['param_adjustments']}"
            )
            return result
        except Exception as e:
            logger.debug(f"[P3] Multimodal fusion skipped: {e}")
            return None

    def _run_plan(self) -> Dict:
        """规划阶段：compiler 确定性路径 或 LLM 生成剧本 + KB 风格注入 + 节奏卡点(Mugen)

        S6 学习回读闭合：在 effect_stack 生成后，调用 LearningBridge 将三个学习系统
        (PersistentLearningLoop / BayesianParameterOptimizer / MemoryStore) 的历史
        经验注入参数，闭合"学了不用"的读侧断点。

        P2: VRS 驱动 effect_stack — 在 LLM/compiler 生成剧本之后，调用
        _build_effect_stack_from_vrs 把 VRS 真分析检测到的 effects 直接注入
        effect_stack 前列，并由 color_palette/rhythm/motion/style_tags 调整参数。
        返回值新增 effect_stack_source 与 vrs_to_effects_mapping 字段。
        """
        # compiler 模式：确定性 NLU → 操作列表（绕过 LLM）
        if self.config.use_compiler:
            comp = self.compiler
            if comp:
                self._log("Plan: using compiler deterministic path")
                comp_result = comp.run(self._get_previous_data())
                if not comp_result.get("fallback"):
                    effect_stack = comp_result.get("effect_stack", [])
                    # P2: VRS 驱动注入（compiler 路径同样消费 vrs_result）
                    vrs_stack, vrs_src, vrs_map = self._inject_vrs_into_effect_stack(effect_stack)
                    # S6: 学习回读增强
                    enhancement_report = self._apply_learning_enhancement(vrs_stack)
                    return {
                        "script": comp_result.get("script", {}),
                        "effect_stack": vrs_stack,
                        "effect_stack_source": vrs_src,
                        "vrs_to_effects_mapping": vrs_map,
                        "transition_plan": comp_result.get("transition_plan", []),
                        "compiler_used": True,
                        "compiler_result": comp_result,
                        "learning_enhancement": enhancement_report,
                    }
                self._log("Plan: compiler fallback, using LLM path", "WARN")

        # 默认 LLM 路径
        data = self.planning.run(self._get_previous_data())
        # v2: KB 风格上下文增强
        if self.config.use_knowledge and self.config.input_topic:
            kb_style = self._kb.get_style_context(self.config.input_topic)
            if kb_style:
                data["kb_context"] = kb_style
                # 合并 KB 推荐与 VRS 发现
                if self._vrs_result:
                    data["merged_style"] = self._merge_style_sources(
                        data.get("style_params", {}),
                        kb_style,
                        self._vrs_result.get("style", {})
                    )
        # 项目4集成: Mugen 节奏卡点规划
        data["beat_timeline"] = self._generate_beat_timeline()

        # P2: VRS 驱动 effect_stack — 把 VRS 检测的 effects 注入前列
        llm_stack = data.get("effect_stack", []) or []
        vrs_stack, vrs_src, vrs_map = self._inject_vrs_into_effect_stack(llm_stack)
        data["effect_stack"] = vrs_stack
        data["effect_stack_source"] = vrs_src
        data["vrs_to_effects_mapping"] = vrs_map
        self._log(
            f"[P2-VRS] effect_stack_source={vrs_src}, "
            f"size={len(vrs_stack)}, vrs_mappings={len(vrs_map)}"
        )

        # S6: 学习回读增强 — 将历史学习数据注入 effect_stack
        if vrs_stack:
            enhancement_report = self._apply_learning_enhancement(vrs_stack)
            data["learning_enhancement"] = enhancement_report
        return data

    def _inject_vrs_into_effect_stack(
        self, llm_stack: List[Dict[str, Any]]
    ) -> tuple:
        """P2: 用 VRS 真分析数据驱动生成 effect_stack。

        策略（优先级从高到低）：
          1. 若 self._vrs_result 存在且 effects 非空 → 走 VRS 驱动路径
             a. _build_effect_stack_from_vrs 把 VRS effects 直接映射为栈条目（注入前列）
             b. 由 color_palette/rhythm/motion/style_tags 调整后续参数
             c. 与 LLM 栈去重（同义效果保留 VRS 版本）
             d. 若映射后仍 <2 条，补 _build_default_effect_stack 凑足
             → source = "vrs_driven"（VRS 直接生成）或 "vrs_injected"（VRS 注入+LLM 合并）
          2. 无 VRS 但 llm_stack 非空 → 直接用 LLM 栈
             → source = "llm_generated"
          3. 都为空 → _build_default_effect_stack 兜底
             → source = "default_fallback"

        Returns:
            (effect_stack, effect_stack_source, vrs_to_effects_mapping)
        """
        vrs = self._vrs_result if isinstance(self._vrs_result, dict) else {}
        vrs_effects = vrs.get("effects", []) if vrs else []

        if not vrs_effects:
            # 无 VRS 检测效果
            if llm_stack:
                return llm_stack, "llm_generated", []
            # 兜底
            return self._build_default_effect_stack(), "default_fallback", []

        # VRS 驱动：把 VRS effects 映射为 effect_stack 条目
        vrs_driven_stack, mapping = self._build_effect_stack_from_vrs(vrs)

        # 与 LLM 栈合并：VRS 优先，去重
        # 收集 VRS 已生成的效果名关键词集合（小写）
        vrs_name_keys: set = set()
        for entry in vrs_driven_stack:
            n = (entry.get("name") or "").lower()
            for kw in ("color", "grade", "neon", "cool", "warm", "saturation",
                       "contrast", "sharpen", "vignette", "blur", "motion"):
                if kw in n:
                    vrs_name_keys.add(kw)

        merged: List[Dict[str, Any]] = list(vrs_driven_stack)
        for eff in llm_stack:
            n = (eff.get("name") or "").lower()
            # 命中任一 VRS 已有效果关键词则跳过 LLM 版本
            if any(kw in n for kw in vrs_name_keys):
                continue
            merged.append(eff)

        # 保证至少 2 个效果
        if len(merged) < 2:
            for eff in self._build_default_effect_stack():
                if len(merged) >= 2:
                    break
                # 避免与已有重复
                n = (eff.get("name") or "").lower()
                if not any(n in (m.get("name") or "").lower() for m in merged):
                    merged.append(eff)

        source = "vrs_driven" if not llm_stack else "vrs_injected"
        return merged, source, mapping

    def _build_effect_stack_from_vrs(self, *args, **kwargs):
        """委托 pipeline.unified_pipeline_helpers.build_effect_stack_from_vrs (2026-08-14 拆分)。"""
        from pipeline.unified_pipeline_helpers import build_effect_stack_from_vrs
        return build_effect_stack_from_vrs(self, *args, **kwargs)


    def _apply_learning_enhancement(self, effect_stack: List[Dict[str, Any]]) -> Dict[str, Any]:
        """S6 学习回读增强：将三个学习系统的历史数据注入 effect_stack

        闭合学习闭环读侧断点：让 case-store.json 的参数模板、default-value-store.json
        的偏差学习值、BayesianParameterOptimizer 的推荐、MemoryStore 的历史经验
        真正影响 plan 阶段的参数生成决策。失败不影响主管线。

        风格上下文构造：从 VRS 逆向分析结果 + KB 风格库自动构造 StyleVector，
        让贝叶斯推荐感知"高燃"vs"电影感"等风格差异。
        """
        try:
            from learning.learning_bridge import get_learning_bridge
            bridge = get_learning_bridge()

            # 提取 KB 风格上下文（若已加载）
            kb_style = None
            if self.config.use_knowledge and self.config.input_topic:
                try:
                    kb_style = self._kb.get_style_context(self.config.input_topic)
                except Exception:
                    kb_style = None

            # S6b: ExperienceHarvester 历史经验回读 — 将已汲取的成功经验注入 effect_stack
            harvested = self._inject_harvested_experience(effect_stack)
            report = bridge.enhance_effect_stack(
                effect_stack=effect_stack,
                style_context=None,  # 让 bridge 自动构造
                user_input=self.config.input_topic,
                vrs_result=self._vrs_result if self._vrs_result else None,
                kb_style=kb_style,
            )
            if report.enhanced_count > 0 or harvested:
                self._log(
                    f"[S6] LearningBridge enhanced {report.enhanced_count}/"
                    f"{report.total_effects} effects"
                )
                for e in report.per_effect:
                    if e.enhanced:
                        self._log(
                            f"[S6]   effect[{e.effect_index}] '{e.effect_name}': "
                            f"sources={e.sources}, params={list(e.applied_params.keys())}"
                        )
            else:
                self._log(
                    f"[S6] LearningBridge: no enhancement applied "
                    f"(total={report.total_effects}, errors={len(report.errors)})"
                )
            out = report.to_dict()
            if harvested:
                out["harvested_experience"] = harvested
            return out
        except Exception as e:
            self._log(f"[S6] LearningBridge failed: {e}", "WARN")
            return {"error": str(e), "enhanced_count": 0}

    def _inject_harvested_experience(self, effect_stack: List[Dict[str, Any]]) -> Dict[str, Any]:
        """S6b: ExperienceHarvester 历史经验回读注入 effect_stack。

        用 build_records_from_structured() 重建历史 pipeline 记录，选取总体成功且
        plan/execute 阶段有参数的记录，抽取其参数注入 effect_stack。
        闭合"harvest 只提取不消费"的读侧断点。graceful degrade: 无可读经验返回空 dict。
        """
        try:
            from core.experience_harvester import ExperienceHarvester
            harvester = ExperienceHarvester(project_root=".")
            records = harvester.build_records_from_structured()
            if not records:
                return {}
            applied = 0
            used = []
            for rec in records:
                if rec.overall_success is False:
                    continue
                for stage_exp in rec.stages:
                    if stage_exp.stage_name not in ("plan", "execute"):
                        continue
                    params = stage_exp.params or {}
                    if not params:
                        continue
                    effect_stack.append({
                        "name": f"learned_{stage_exp.stage_name}",
                        "description": f"Harvested {stage_exp.stage_name} experience",
                        "params": dict(params),
                        "duration": stage_exp.duration_sec or 2.0,
                        "timing": "auto",
                        "source": "harvested_experience",
                    })
                    applied += 1
                    used.append(stage_exp.stage_name)
                    break
            if applied:
                self._log(f"[S6b] Injected {applied} harvested experience entries")
            return {"applied": applied, "records_used": used}
        except Exception as e:
            logger.debug(f"[S6b] Harvested experience injection skipped: {e}")
            return {}

    def _run_execute(self) -> Dict:
        """执行阶段：多智能体协作 + KB 效果推荐 (支持质量迭代增强)

        S2闭环: 消费L1策略选择结果，根据策略动作类型调整执行模式
        - action_type="simplify": 跳过多智能体，直接走基础执行
        - action_type="fallback": 强制使用FFmpeg降级路径
        - action_type="run": 正常多智能体执行
        """
        # 如果有质量增强视频，直接使用作为执行结果
        if self._enhanced_video_path and Path(self._enhanced_video_path).exists():
            self._log(f"Using quality-enhanced video: {self._enhanced_video_path}")
            return {
                "project_path": self._enhanced_video_path,
                "composition": "quality_enhanced",
                "layers_created": 1,
                "effects_applied": 1,
                "execution_mode": "quality_enhanced",
            }

        # S2: 读取L1策略选择结果，决定执行模式
        exec_mode = "default"
        strategy_name = ""
        strategy_params = {}
        strategy_result = self._results.get("_strategy_selection")
        if strategy_result and strategy_result.status == StageStatus.DONE:
            sdata = strategy_result.data or {}
            strategy_name = sdata.get("strategy_name", "")
            # 查找execute阶段的动作类型
            from core.meta_strategy_engine import get_strategy_engine
            try:
                engine = get_strategy_engine()
                strategy = engine.get_library().get(sdata.get("strategy_id", ""))
                if strategy:
                    for step in strategy.action_sequence:
                        if step.stage == "execute":
                            if step.action_type == "simplify":
                                exec_mode = "simplified"
                            elif step.action_type == "fallback":
                                exec_mode = "fallback"
                            elif step.action_type == "skip":
                                exec_mode = "skip"
                            strategy_params = step.params
                            break
                    if exec_mode != "default":
                        self._log(
                            f"[S2] Strategy '{strategy_name}' suggests execute mode: "
                            f"{exec_mode} (params={strategy_params})"
                        )
            except Exception as e:
                logger.debug(f"[S2] Strategy lookup failed: {e}")

        # 策略指示跳过执行
        if exec_mode == "skip":
            self._log("[S2] Strategy suggests skip execute, returning minimal result")
            return {
                "project_path": "",
                "composition": "skipped_by_strategy",
                "layers_created": 0,
                "effects_applied": 0,
                "execution_mode": "strategy_skip",
                "strategy": strategy_name,
            }

        # 策略指示简化执行: 跳过多智能体，直接走基础执行
        if exec_mode == "simplified":
            self._log("[S2] Strategy suggests simplified execute, using basic runner")
            result = self.execution.run(self._get_previous_data())
            result["execution_mode"] = "strategy_simplified"
            result["strategy"] = strategy_name
            return result

        # 策略指示降级: 标记使用FFmpeg
        if exec_mode == "fallback":
            self._log("[S2] Strategy suggests fallback, will prefer FFmpeg in render")
            # 在results中标记，供render阶段读取
            self._results["_strategy_fallback"] = StageResult(
                stage="_strategy_fallback", status=StageStatus.DONE,
                data={"prefer_ffmpeg": True, "strategy": strategy_name}
            )

        # P2.1: 历史成功率驱动执行引擎选择
        # 当策略未强制降级且历史表明 ffmpeg 更可靠时，直接走真混剪 FFmpeg 路径，
        # 避免在多智能体/AE 上反复失败。graceful degrade: 失败则继续正常流程。
        if exec_mode not in ("fallback", "simplified", "skip"):
            engine_choice = self._select_engine_for_stage("execute", ["ae", "ffmpeg"])
            if engine_choice == "ffmpeg":
                self._log("[P2.1] EngineRegistry historical success favors ffmpeg for execute")
                result = self._run_execute_real_mix()
                if result.get("output_path") or result.get("project_path"):
                    result["execution_mode"] = "historical_ffmpeg"
                    result["engine_choice"] = engine_choice
                    # P3: 同样生成 FX 脚本
                    fx = self._apply_fx_scripts(result)
                    if fx:
                        result["fx_scripts"] = fx
                    return result

        if self.config.enable_multi_agent:
            result = self._execute_with_agents()
        else:
            result = self.execution.run(self._get_previous_data())

        # 记录策略信息到结果
        if strategy_name:
            result["strategy"] = strategy_name
            result["strategy_exec_mode"] = exec_mode

        # P1 真混剪保障: 如果 execute 没产出真实视频文件 (.mp4/.mov 等),
        # 调用 _run_execute_real_mix 用 FFmpegEditEngine 按 effect_stack 分段应用滤镜+concat,
        # 不再降级到"参考视频截取 10s 片段"。
        result = self._ensure_real_mix_output(result)

        # P3: FX 效果脚本生成 (粒子/文字冲击/风格预设) — 作为 execute 附加产物
        fx = self._apply_fx_scripts(result)
        if fx:
            result["fx_scripts"] = fx
        return result

    def _apply_fx_scripts(self, result: Dict) -> Dict:
        """P3: 将 core/fx 效果引擎接入 execute 阶段。

        根据 analyze 的多模态融合决策 + VRS 检测效果 + 卡点 beats，生成
        粒子/文字冲击/大气氛围的 JSX 脚本文件到输出目录，作为 execute 附加产物。
        不强制下发 AE(避免阻塞)，只落盘脚本供后续渲染/人工使用。
        graceful degrade: fx 模块不可用时不生成，不影响 execute 结果。
        """
        try:
            from core.fx.particle_presets import (
                build_particle_jsx, get_particle_fx_client,
            )
            from core.fx.text_impact import _build_jsx as build_text_jsx
            from core.fx.style_preset_engine import get_style_preset_engine

            out_dir = Path(self.config.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            files = {}

            # 1) 多模态融合选择的效果 → 粒子脚本
            #      融合决策来自 analyze 阶段结果，而非 execute 自身
            fusion = result.get("multimodal_fusion") or {}
            if not fusion:
                ana_res = self._results.get("analyze")
                if ana_res and getattr(ana_res, "data", None):
                    fusion = ana_res.data.get("multimodal_fusion") or {}
            selected = fusion.get("selected_effect") or ""
            if selected:
                particle_type = str(selected).replace(" ", "_")[:40]
                jsx = build_particle_jsx("generate", compName="Main", type=particle_type)
                p = out_dir / f"{self.run_id}_fx_particle.jsx"
                p.write_text(jsx, encoding="utf-8")
                files["particle_jsx"] = str(p)
                get_particle_fx_client().record_call(
                    "generate", {"compName": "Main", "type": particle_type}, {"status": "generated"}
                )

            # 2) VRS 检测的卡点 beats → 文字冲击脚本 (beat_sync 卡点缩放脉冲)
            beats = self._extract_beats()
            if beats:
                try:
                    t0 = time.time()
                    ti_jsx = build_text_jsx("beat_sync", compName="Main", layerName="TextLayer", beats=beats)
                    p = out_dir / f"{self.run_id}_fx_text_impact.jsx"
                    p.write_text(ti_jsx, encoding="utf-8")
                    files["text_impact_jsx"] = str(p)
                    self._log(
                        f"[FX] text_impact 生成成功: {len(beats)} beats -> {p.name} "
                        f"({len(ti_jsx.splitlines())} 行, {(time.time() - t0) * 1000:.0f}ms)",
                        "INFO",
                    )
                except Exception as e:
                    self._log(
                        f"[FX] text_impact 生成失败: {type(e).__name__}: {str(e)[:200]}",
                        "WARN",
                    )
            else:
                self._log(
                    "[FX] text_impact 跳过: beats 为空（VRS/analyze/音频现场三级来源均无节拍）",
                    "WARN",
                )

            # 3) 风格预设引擎执行记录 (调色/风格上下文)
            style_engine = get_style_preset_engine()
            style_engine.record_execution(
                style_id="auto", comp_name="Main",
                result={"summary": {"score": float(fusion.get("effect_confidence", 0.5) or 0.5)}},
            )

            if files:
                self._log(f"[P3] FX scripts generated: {list(files.keys())}")
            return files
        except Exception as e:
            logger.debug(f"[P3] FX script generation skipped: {e}")
            return {}

    def _extract_beats(self) -> list:
        """从 VRS 检测结果 / analyze 数据 / 配置音频 中提取卡点 beats (秒数列表)。

        三级降级:
          1. VRS 逆向分析的 beats (需参考视频)
          2. analyze 阶段 librosa 分析的 beats (需音频输入)
          3. 【补全】现场从 config.audio_path / perceive.audios 分析一次
             (librosa)，确保没有参考视频时卡点文字特效也能拿到节拍点。

        结果按 run 缓存（_beats_cache），避免多次调用重复做 librosa 分析。
        """
        if self._beats_cache is not None:
            self._log(
                f"[BEATS] 命中缓存: {len(self._beats_cache)} beats",
                "DEBUG",
            )
            return self._beats_cache

        t0 = time.time()
        source = "none"
        beats = []
        if self._vrs_result:
            beats = self._vrs_result.get("beats", []) or []
            source = "vrs"
        if not beats:
            prev = self._get_previous_data()
            beats = (prev.get("analyze", {}) or {}).get("beats", []) or []
            source = "analyze"
        if not beats:
            beats = self._extract_beats_from_audio()
            source = "audio_live"

        # 兼容两种 beats 格式: float 列表(秒) 或 dict 列表({"time": 秒, "bpm": ...})
        # 此前只认 float，analyze 阶段产出的 dict 列表被全滤掉，导致 beats 误判为空
        cleaned: List[float] = []
        for b in beats:
            if isinstance(b, (int, float)):
                cleaned.append(float(b))
            elif isinstance(b, dict):
                t = b.get("time")
                if t is not None:
                    try:
                        cleaned.append(float(t))
                    except (TypeError, ValueError):
                        pass
        elapsed_ms = (time.time() - t0) * 1000
        head = [round(b, 2) for b in cleaned[:5]]
        if cleaned:
            self._log(
                f"[BEATS] 提取完成: source={source}, total={len(cleaned)}, "
                f"{elapsed_ms:.0f}ms, 前5={head}",
                "INFO",
            )
        else:
            self._log(
                f"[BEATS] 三级降级均无 beats (vrs/analyze/audio_live), "
                f"{elapsed_ms:.0f}ms — text_impact 将跳过",
                "WARN",
            )
        self._beats_cache = cleaned
        return cleaned

    @staticmethod
    def _tempo_value(tempo) -> float:
        """兼容 librosa 0.9/0.10: beat_track 返回的 tempo 可能是标量或 1 维数组。

        librosa >=0.10 的 beat_track 返回 (tempo_ndarray, beats)，直接 float(tempo)
        会抛 "only 0-dimensional arrays can be converted to Python scalars"。
        """
        try:
            return float(tempo)
        except (TypeError, ValueError):
            import numpy as np
            return float(np.ravel(np.asarray(tempo))[0])

    def _extract_beats_from_audio(self) -> list:
        """从配置音频 / perceive 音频现场分析节拍 (librosa)，返回秒数列表。

        graceful degrade: librosa 不可用或音频不可读时返回空，不影响 execute。
        """
        candidates: List[str] = []
        # 1) config.audio_path（管线主音频/BGM）
        cfg_audio = getattr(self.config, "audio_path", "") or ""
        if cfg_audio and os.path.isfile(str(cfg_audio)):
            candidates.append(str(cfg_audio))
        # 2) perceive 阶段收集的 audios
        try:
            prev = self._get_previous_data()
            for a in (prev.get("perceive", {}) or {}).get("audios", []) or []:
                p = a.get("path")
                if p and os.path.isfile(str(p)):
                    candidates.append(str(p))
        except Exception:
            pass
        if not candidates:
            self._log("[BEATS] 音频现场分析: 无候选音频 (config.audio_path / perceive.audios 均为空)", "DEBUG")
            return []
        self._log(
            f"[BEATS] 音频现场分析: {len(candidates)} 个候选 -> "
            f"{[Path(c).name for c in candidates]}",
            "DEBUG",
        )
        for path in candidates:
            try:
                import librosa
                t0 = time.time()
                y, sr = librosa.load(path, sr=None, mono=True, duration=90)
                tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                if len(beat_frames) < 2:
                    self._log(
                        f"[BEATS] {Path(path).name}: 节拍帧不足({len(beat_frames)}), 跳过",
                        "DEBUG",
                    )
                    continue
                beat_times = librosa.frames_to_time(beat_frames, sr=sr)
                self._log(
                    f"[BEATS] 现场节拍分析成功: {Path(path).name} -> "
                    f"{len(beat_times)} beats, BPM={self._tempo_value(tempo):.1f}, "
                    f"{(time.time() - t0) * 1000:.0f}ms",
                    "INFO",
                )
                return [round(float(t), 3) for t in beat_times]
            except Exception as e:
                self._log(
                    f"[BEATS] {Path(path).name} 分析失败: {type(e).__name__}: {str(e)[:120]}",
                    "DEBUG",
                )
                continue
        return []

    def _ensure_real_mix_output(self, result: Dict) -> Dict:
        """P1 真混剪保障: 检查 execute 结果是否为真实视频文件, 否则调用真混剪流水线。

        判定真实视频: project_path 后缀为视频格式 AND 文件存在 AND size>1KB
        AND execution_mode 不是 ffmpeg_fallback。
        .aep / 空字符串 / 不存在文件 / ffmpeg_fallback 单段降级 均视为非真实混剪, 触发真混剪。
        (ffmpeg_fallback 虽可能产出真实视频, 但是单段 concat+简单滤镜的降级路径,
         不是 P1 真混剪的 4 段效果 concat; P1-1 要求 execute 必须走 _run_execute_real_mix)
        """
        proj_path = result.get("project_path", "") or ""
        exec_mode = result.get("execution_mode", "")
        video_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
        is_real_video = (
            bool(proj_path)
            and Path(proj_path).suffix.lower() in video_exts
            and Path(proj_path).exists()
            and Path(proj_path).stat().st_size > 1024
            and exec_mode != "ffmpeg_fallback"
        )
        if is_real_video:
            self._log(f"[EXEC-P1] execute produced real video: {proj_path}")
            return result

        self._log(
            f"[EXEC-P1] execute did NOT produce real mix video "
            f"(path={proj_path!r} mode={exec_mode!r}), "
            f"running real mix pipeline"
        )
        mix_result = self._run_execute_real_mix()
        if mix_result.get("output_path") or mix_result.get("project_path"):
            # 保留原 result 的策略信息
            mix_result["strategy"] = result.get("strategy", "")
            mix_result["strategy_exec_mode"] = result.get("strategy_exec_mode", "")
            mix_result["fallback_from"] = result.get("execution_mode", "")
            self._log(
                f"[EXEC-P1] real mix SUCCESS: {mix_result.get('output_path') or mix_result.get('project_path')} "
                f"segments={mix_result.get('layers_created', 0)} effects={mix_result.get('effects_applied', 0)}"
            )
            return mix_result

        self._log(
            f"[EXEC-P1] real mix also failed: code={mix_result.get('error_code')} "
            f"err={mix_result.get('error', '')}", "WARN"
        )
        result["real_mix_attempted"] = True
        result["real_mix_error"] = mix_result.get("error", "unknown")
        result["real_mix_error_code"] = mix_result.get("error_code", "UNKNOWN")
        return result

    def _run_execute_real_mix(self) -> Dict:
        """真实混合执行阶段 (委托 pipeline.unified_pipeline_execute, 2026-08-14 拆分)。"""
        from pipeline.unified_pipeline_execute import run_execute_real_mix
        return run_execute_real_mix(self)


    def _build_default_effect_stack(self) -> List[Dict]:
        """构建默认 cyberpunk 风格效果栈 (当 plan 输出 effect_stack 为空时)。

        保证至少 2 个效果, 满足"用参考视频应用至少 2 个效果再输出"约束。
        """
        return [
            {
                "name": "neon_color_grade",
                "description": "霓虹调色: 高饱和+冷色调",
                "params": {
                    "brightness": 0.05, "contrast": 1.2,
                    "saturation": 1.4, "gamma": 0.95,
                },
                "duration": 4.0,
                "timing": "segment_0",
            },
            {
                "name": "sharpen_vignette",
                "description": "锐化+暗角: 增强边缘与聚焦感",
                "params": {
                    "sharpen_amount": 1.5, "sharpen_radius": 0.8,
                    "vignette_angle": 4.0,
                },
                "duration": 4.0,
                "timing": "segment_1",
            },
            {
                "name": "cool_grade",
                "description": "冷色调色: 蓝绿偏色",
                "params": {
                    "brightness": 0.0, "contrast": 1.15,
                    "saturation": 1.2, "temperature": -0.5,
                },
                "duration": 4.0,
                "timing": "segment_2",
            },
            {
                "name": "warm_grade",
                "description": "暖色调色: 橙红偏色",
                "params": {
                    "brightness": 0.05, "contrast": 1.1,
                    "saturation": 1.3, "temperature": 0.5,
                },
                "duration": 4.0,
                "timing": "segment_3",
            },
        ]

    def _apply_effect_to_filter_builder(
        self, fb, eff: Dict, seg_dur: float
    ) -> bool:
        """把 effect 描述应用到 FFmpegFilterBuilder, 返回是否应用了真实效果。

        支持的效果关键词 (中英): color/grade/neon/cool/warm/cinematic/调色/霓虹
        sharpen/锐化, vignette/暗角, blur/模糊, saturation/饱和, motion/运动, rhythm/节奏。
        未匹配时应用默认调色+锐化, 保证每段都有真实效果。

        P2: 兼容 VRS 驱动的 effect_stack，含 temperature 字符串字段 (cool/warm/neutral)
        会自动转为数值 (cool→-0.3, warm→+0.3, neutral→0.0)。
        """
        from pipeline.ffmpeg_edit_engine import (
            ColorGradeParams, SharpenParams, VignetteParams, BlurParams,
        )
        name = (eff.get("name", "") or "").lower()
        params = eff.get("params", {}) or {}
        applied = False

        def _coerce_temperature(val) -> float:
            """temperature 字段兼容字符串 (cool/warm/neutral) 与数值。"""
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, str):
                v = val.strip().lower()
                if v == "cool":
                    return -0.3
                if v == "warm":
                    return 0.3
                # 数字字符串
                try:
                    return float(v)
                except ValueError:
                    return 0.0
            return 0.0

        def _coerce_float(val, default: float = 0.0) -> float:
            """把任意值转 float，失败返回 default。"""
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        if any(k in name for k in ["color", "grade", "neon", "cool", "warm",
                                    "cinematic", "调色", "霓虹"]):
            fb.color_grade(ColorGradeParams(
                brightness=_coerce_float(params.get("brightness", 0.0)),
                contrast=_coerce_float(params.get("contrast", 1.15), 1.15),
                saturation=_coerce_float(params.get("saturation", 1.25), 1.25),
                gamma=_coerce_float(params.get("gamma", 1.0), 1.0),
                temperature=_coerce_temperature(params.get("temperature", 0.0)),
                tint=_coerce_float(params.get("tint", 0.0)),
            ))
            applied = True
        # saturation 独立效果 (VRS saturation_boost → name="saturation")
        if name == "saturation" or any(k in name for k in ["saturation", "饱和"]):
            amount = _coerce_float(params.get("amount", 0.5), 0.5)
            sat_factor = _coerce_float(params.get("saturation", 1.0 + amount), 1.3)
            # 只有未应用过 color_grade 时才单独加调色（避免覆盖 color_grade 的 saturation）
            if not applied:
                fb.color_grade(ColorGradeParams(
                    saturation=sat_factor,
                    contrast=1.10,
                ))
                applied = True
        # contrast 独立效果 (VRS high_contrast_grade → name="contrast")
        if name == "contrast":
            amount = _coerce_float(params.get("amount", 0.4), 0.4)
            contrast_factor = _coerce_float(params.get("contrast", 1.0 + amount), 1.25)
            if not applied:
                fb.color_grade(ColorGradeParams(
                    contrast=contrast_factor,
                    saturation=1.10,
                ))
                applied = True
        if any(k in name for k in ["sharpen", "锐化"]):
            fb.sharpen(SharpenParams(
                amount=_coerce_float(params.get("sharpen_amount", 1.3), 1.3),
                radius=_coerce_float(params.get("sharpen_radius", 0.8), 0.8),
            ))
            applied = True
        if any(k in name for k in ["vignette", "暗角"]):
            fb.vignette(VignetteParams(
                angle=_coerce_float(params.get("vignette_angle", 3.5), 3.5),
            ))
            applied = True
        if any(k in name for k in ["motion_blur", "motion blur", "运动模糊"]):
            # 运动模糊用 boxblur 近似 (samples 参数记录但 ffmpeg 用固定半径)
            intensity = _coerce_float(params.get("intensity", 0.4), 0.4)
            radius = max(1.0, min(8.0, intensity * 10.0))
            fb.blur(BlurParams(radius_x=radius, radius_y=radius))
            applied = True
        elif any(k in name for k in ["blur", "模糊"]):
            fb.blur(BlurParams(radius_x=3.0, radius_y=3.0))
            applied = True
        # rhythm_transition: VRS tempo 驱动的转场效果, 通过 eq 微调 + fade 体现
        # (实际转场由 fb.fade_in/fade_out 在段间完成, 这里仅补调色)
        if name == "rhythm_transition" and not applied:
            tempo = params.get("tempo", "medium")
            if tempo == "fast":
                fb.color_grade(ColorGradeParams(contrast=1.15, saturation=1.20))
            else:
                fb.color_grade(ColorGradeParams(contrast=1.05, saturation=1.10))
            applied = True

        # 未匹配任何效果 → 应用默认调色+锐化, 保证每段有真实效果
        if not applied:
            fb.color_grade(ColorGradeParams(contrast=1.1, saturation=1.15))
            fb.sharpen(SharpenParams(amount=1.0, radius=0.7))
            applied = True
        return applied

    def _run_render(self) -> Dict:
        """渲染阶段：输出成品 (支持 AE + DaVinci 双引擎 + 质量迭代)

        S3闭环: 消费M3数字孪生预测，当成功率预测<0.5时预防性降级
        - overall_success_rate < 0.5: 跳过DaVinci后处理，直接走FFmpeg
        - critical_path包含render: 增加降级触发概率
        """
        # 质量迭代模式: execute返回增强视频，直接作为最终输出
        prev = self._get_previous_data()
        if prev.get("execution_mode") == "quality_enhanced":
            enhanced_path = prev.get("project_path", "")
            if enhanced_path and Path(enhanced_path).exists():
                self._log(f"Render: passing through quality-enhanced video")
                return {
                    "output_path": enhanced_path,
                    "render_mode": "quality_passthrough",
                    "file_size": os.path.getsize(enhanced_path) if os.path.isfile(enhanced_path) else 0,
                }

        # S3: 读取M3数字孪生预测，决定是否预防性降级
        twin_prefer_ffmpeg = False
        twin_success_rate = 1.0  # 默认值，确保始终有定义
        critical_path = []  # 默认值，确保始终有定义
        twin_result = self._results.get("_twin_prediction")
        if twin_result and twin_result.status == StageStatus.DONE:
            tdata = twin_result.data or {}
            prediction = tdata.get("prediction", {})
            twin_success_rate = prediction.get("overall_success_rate", 1.0)
            critical_path = prediction.get("critical_path", [])

            if twin_success_rate < 0.5:
                twin_prefer_ffmpeg = True
                self._log(
                    f"[S3] Twin prediction low success rate ({twin_success_rate:.2f}), "
                    f"enabling preventive FFmpeg fallback"
                )
            elif "render" in critical_path and twin_success_rate < 0.7:
                self._log(
                    f"[S3] Render in critical path with moderate risk ({twin_success_rate:.2f}), "
                    f"keeping DaVinci but preparing fallback"
                )

        # S2联动: 策略也可能指示fallback
        strategy_fallback = self._results.get("_strategy_fallback")
        if strategy_fallback and strategy_fallback.status == StageStatus.DONE:
            if strategy_fallback.data.get("prefer_ffmpeg", False):
                twin_prefer_ffmpeg = True
                self._log("[S3] Strategy also prefers FFmpeg, confirming fallback")

        # 预防性降级: 直接走MoviePy/FFmpeg，跳过AE/DaVinci
        if twin_prefer_ffmpeg:
            self._log("[S3] Using preventive FFmpeg/MoviePy render path")
            data = self._moviepy_fallback_render({}, prev)
            if data.get("output_path") and Path(data["output_path"]).exists():
                data["render_mode"] = "preventive_ffmpeg"
                data["twin_success_rate"] = twin_success_rate
                return data
            self._log("[S3] Preventive render failed, falling back to normal flow", "WARN")

        # P2.1/P2.4: 历史成功率 + 质量档 + 策略偏好 驱动引擎选择 (深度集成)
        # 当孪生/策略未强制降级，而历史/元数据信号强烈偏好 ffmpeg 时，补充降级信号
        engine_choice = self._select_engine_with_meta("render", ["ae", "davinci", "ffmpeg", "moviepy"])
        if not engine_choice:
            engine_choice = self._select_engine_for_stage("render", ["ae", "davinci", "ffmpeg", "moviepy"])
        if engine_choice == "ffmpeg" and not twin_prefer_ffmpeg:
            self._log("[P2.1/P2.4] EngineRegistry historical success favors ffmpeg for render")
            data = self._moviepy_fallback_render({}, prev)
            if data.get("output_path") and Path(data["output_path"]).exists():
                data["render_mode"] = "historical_ffmpeg"
                data["engine_choice"] = engine_choice
                return data

        # 正常渲染流程
        exec_mode_dbg = prev.get("execution_mode", "")
        proj_path_dbg = prev.get("project_path", "")
        self._log(
            f"[RENDER-DBG] exec_mode={exec_mode_dbg!r} project_path={proj_path_dbg!r} "
            f"exists={Path(proj_path_dbg).exists() if proj_path_dbg else False}"
        )
        data = self.rendering.run(prev)
        out_dbg = data.get("output_path", "")
        self._log(
            f"[RENDER-DBG] rendering.run -> output_path={out_dbg!r} "
            f"status={data.get('status', '')!r} render_engine={data.get('render_engine', '')!r} "
            f"exists={Path(out_dbg).exists() if out_dbg else False} "
            f"size={Path(out_dbg).stat().st_size if out_dbg and Path(out_dbg).exists() else 0}"
        )

        # v2: 如果配置了 DaVinci 渲染，尝试后处理
        # S3: 如果数字孪生预测render在critical_path且成功率低，跳过DaVinci
        skip_davinci = False
        if twin_result and twin_result.status == StageStatus.DONE:
            if "render" in critical_path and twin_success_rate < 0.5:
                skip_davinci = True
                self._log("[S3] Skipping DaVinci post-process: twin predicts render risk")

        if self._cfg("use_davinci_render", False) and not skip_davinci:
            data = self._davinci_post_process(data)

        # 项目3集成: MoviePy 降级渲染(当主渲染无输出时)
        if not data.get("output_path") or not Path(data.get("output_path", "")).exists():
            data = self._moviepy_fallback_render(data, prev)

        return data

    def _davinci_post_process(self, base_data: Dict) -> Dict:
        """DaVinci 后处理: 调色 + 最终渲染"""
        input_path = base_data.get("output_path", "")
        if not input_path or not Path(input_path).exists():
            self._log("DaVinci: No input for post-processing, skipping", "WARN")
            return base_data

        try:
            from integrations.davinci_render_queue import RenderQueueManager
            rq = RenderQueueManager()

            # 添加调色+渲染任务
            output_path = str(Path(input_path).parent / f"{Path(input_path).stem}_graded.mp4")
            job_id = rq.add_render_job(
                input_path=input_path,
                output_path=output_path,
                preset_name="H.264 Master",
            )

            # 执行渲染
            rq.start_render(job_id)
            result = rq.wait_for_completion(job_id, timeout=300)

            if result.get("status") == "completed":
                self._log(f"DaVinci: Post-process complete -> {output_path}")
                base_data["output_path"] = output_path
                base_data["davinci_render"] = True
                base_data["davinci_job_id"] = job_id
            else:
                self._log(f"DaVinci: Post-process failed: {result.get('error', 'unknown')}", "WARN")

        except Exception as e:
            self._log(f"DaVinci: Post-process error: {e}", "WARN")

        return base_data

    def _run_verify(self) -> Dict:
        """质检阶段 (委托 pipeline.unified_pipeline_verify, 2026-08-14 拆分)。"""
        from pipeline.unified_pipeline_verify import run_verify
        return run_verify(self)


    def _trace_artifact_manifest(self) -> Dict[str, Any]:
        """P4.3b: 产物血缘追溯 — 导出本 run 的产物清单与上游血缘。

        用 export_manifest 汇总各阶段登记产物，并在 render 产物上做血缘回溯，
        验证上游(plan/execute)产物完整性。闭合"artifact 只写不读"断点。
        graceful degrade: 无产物管理器或无产物时返回空 dict。
        """
        if not self.artifact_mgr:
            return {}
        try:
            manifest = self.artifact_mgr.export_manifest(self.run_id)
            if not manifest.get("artifacts_by_stage"):
                return manifest
            # 血缘回溯: 取 render 阶段第一个产物，向上追溯其祖先
            lineage = {"render": [], "plan": 0, "execute": 0}
            render_arts = manifest.get("artifacts_by_stage", {}).get("render", [])
            if render_arts:
                first = render_arts[0]
                lineage["render"] = self.artifact_mgr.get_lineage(first.get("id", ""))
            lineage["plan"] = len(manifest.get("artifacts_by_stage", {}).get("plan", []))
            lineage["execute"] = len(manifest.get("artifacts_by_stage", {}).get("execute", []))
            self._log(
                f"[P4.3b] Artifact manifest: {manifest.get('artifact_count', 0)} artifacts, "
                f"render lineage={len(lineage['render'])}"
            )
            return {"manifest_summary": manifest, "lineage": lineage}
        except Exception as e:
            logger.debug(f"[P4.3b] Artifact trace skipped: {e}")
            return {}

    def _run_quality_gate(self, output_path: str, qa_result: Dict[str, Any]):
        """P4.2: 对渲染产物执行 QualityGate 质量规则校验，结果附加到 qa_result。

        graceful degrade: QualityGate 不可用时仅记录 WARN，不影响 verify 结论。
        规则: VMAF阈值 / 时长范围 / 分辨率 / 音频峰值 / 文件大小 / 阶段成功。
        """
        if not self.quality_gate:
            return
        try:
            from core.quality_gate import QualityContext

            vmaf = qa_result.get("vmaf", {}) or {}
            vmaf_score = vmaf.get("score")
            resolution = vmaf.get("resolution")
            duration_sec = (
                float(vmaf.get("duration_sec", 0) or 0)
                if vmaf.get("duration_sec")
                else 0.0
            )
            # 【统一口径】数据补齐: VMAF 缺失时长/分辨率时用 ffprobe 实测，
            # 避免 DurationRule/ResolutionRule 因缺数据(0/None)误判 FAIL
            if duration_sec <= 0 or not resolution:
                probe_dur, probe_res = self._probe_media(output_path)
                if duration_sec <= 0 and probe_dur > 0:
                    duration_sec = probe_dur
                if not resolution and probe_res:
                    resolution = probe_res
            file_size_mb = 0.0
            if output_path and Path(output_path).exists():
                file_size_mb = round(os.path.getsize(output_path) / 1024 / 1024, 2)

            context = QualityContext(
                output_path=output_path or "",
                vmaf_score=float(vmaf_score) if vmaf_score is not None else None,
                duration_sec=duration_sec,
                resolution=tuple(resolution) if isinstance(resolution, (list, tuple)) and len(resolution) == 2 else None,
                file_size_mb=file_size_mb,
                stages_success=bool(qa_result.get("verified", False)),
                extra={
                    "final_score": qa_result.get("final_score"),
                    # 【统一口径】把 verify 实测综合分喂给 OverallQualityRule，
                    # 使 QualityGate 的 status 与 verify 的 verified 结论一致
                    "overall_score": qa_result.get("final_score"),
                    "min_score": float(self.config.min_quality_score),
                    "run_id": self.run_id,
                },
            )
            result = self.quality_gate.evaluate(context)
            # 【埋点】逐规则判定明细（PASS/FAIL/分数/原因），便于真实运行排查
            for rr in result.rule_results:
                self._log(
                    f"[QGATE] rule[{rr.rule_id}] passed={rr.passed} "
                    f"score={rr.score:.2f} sev={rr.severity} | {rr.reason}",
                    "DEBUG",
                )
            mitigations = self.quality_gate.suggest_mitigations(result)
            qa_result["quality_gate"] = {
                "status": result.status,
                "overall_score": result.overall_score,
                "overall_score_100": round(result.overall_score * 100, 1),
                "passed": result.passed,
                "issues": [i.__dict__ if hasattr(i, "__dict__") else str(i) for i in result.issues],
                "mitigations": [m.__dict__ if hasattr(m, "__dict__") else str(m) for m in mitigations],
            }
            self._log(
                f"[QGATE] status={result.status} overall={result.overall_score:.2f} "
                f"(0-100: {result.overall_score * 100:.1f}) passed={result.passed} "
                f"issues={len(result.issues)} | context: duration={duration_sec:.1f}s "
                f"res={resolution} vmaf={vmaf_score} file={file_size_mb}MB "
                f"overall_score(喂入)={qa_result.get('final_score')} min={self.config.min_quality_score}",
            )
            # 【统一口径】QualityGate=FAIL(存在 error 级规则问题，含整体分不达标) →
            # verify 判定改为不通过。此前 QualityGate 仅做"附加诊断"不参与判定，
            # 导致 "QualityGate FAIL" 与 "score=70.6 passed=True" 两套结论打架。
            if result.status == "FAIL":
                was_verified = bool(qa_result.get("verified", False))
                qa_result["verified"] = False
                qa_result["quality_gate_failed"] = True
                if was_verified:
                    self._log(
                        f"[P4.2] QualityGate=FAIL → verify 结论改为不通过 "
                        f"(实测分={qa_result.get('final_score', '?')}, "
                        f"规则问题 {len(result.issues)} 项)",
                        "WARN",
                    )
        except Exception as e:
            logger.warning(f"[P4.2] QualityGate evaluate failed (degraded): {e}")

    def _probe_media(self, path: str):
        """ffprobe 实测 (时长, 分辨率)，供 QualityGate 数据补齐。失败返回 (0.0, None)。"""
        import subprocess

        if not path or not os.path.isfile(path):
            return 0.0, None
        ffprobe = self._cfg("ffprobe_bin", "") or _paths_ffprobe()
        if not os.path.isfile(ffprobe):
            return 0.0, None
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-print_format", "json",
                 "-show_entries", "format=duration:stream=width,height,codec_type",
                 path],
                capture_output=True, text=True, timeout=15,
            )
            data = json.loads(r.stdout or "{}")
            fmt = data.get("format", {}) or {}
            try:
                dur = float(fmt.get("duration") or 0) or 0.0
            except (TypeError, ValueError):
                dur = 0.0
            res = None
            for s in data.get("streams", []) or []:
                if s.get("codec_type") == "video" and s.get("width") and s.get("height"):
                    try:
                        res = (int(s["width"]), int(s["height"]))
                    except (TypeError, ValueError):
                        res = None
                    break
            return dur, res
        except Exception:
            return 0.0, None

    def _run_learn(self, *args, **kwargs):
        """委托 pipeline.unified_pipeline_helpers.run_learn (2026-08-14 拆分)。"""
        from pipeline.unified_pipeline_helpers import run_learn
        return run_learn(self, *args, **kwargs)


    def _execute_with_agents(self) -> Dict:
        """通过 MultiAgentOrchestrator 执行"""
        plan = self._get_previous_data().get("plan", {})
        perceive = self._get_previous_data().get("perceive", {})

        try:
            import asyncio
            from core.multi_agent_orchestrator import MultiAgentOrchestrator
            mao = MultiAgentOrchestrator()

            # 构建执行参数
            exec_args = {
                "prompt": self.config.input_topic or "Pipeline generated video",
                "compose_type": "preview",
                "output": str(Path(self.config.output_dir) / f"{self.run_id}.mp4"),
            }

            # 如果有音频，加入
            if self.config.audio_path:
                exec_args["audio_path"] = self.config.audio_path

            # 如果有 VRS 效果，传给 composer
            if self._vrs_result:
                exec_args["jsx"] = self._generate_jsx_from_vrs()

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(mao.produce(**exec_args))
            finally:
                loop.close()

            return {
                "project_path": result.get("phases", {}).get("compose", {}).get("output", ""),
                "agent_results": {k: v for k, v in result.get("phases", {}).items()},
                "success": result.get("success", False),
            }
        except Exception as e:
            self._log(f"Multi-agent execution failed: {e}, falling back to basic", "WARN")
            return self.execution.run(self._get_previous_data())

    def _generate_jsx_from_vrs(self) -> str:
        """从 VRS 分析结果生成 JSX 脚本"""
        if not self._vrs_result:
            return ""
        effects = self._vrs_result.get("effects", [])
        jsx_parts = ["// Auto-generated from VRS analysis"]
        for eff in effects:
            eff_name = eff.get("name", "")
            if eff_name:
                jsx_parts.append(f'// Effect: {eff_name} (confidence: {eff.get("confidence", 0):.0%})')
        return "\n".join(jsx_parts)

    # ----------------------------------------------------------------
    #  质量门控 (v2 新增)
    # ----------------------------------------------------------------

    def _check_quality_gate(self) -> bool:
        """检查是否需要迭代修复 + 应用 FeedbackExecutor 增强

        【P1-多轮优化后】若 verify 阶段已通过 execute_multi_pass 做过多轮 FFmpeg 优化
        (optimization_applied=True), 则不再触发粗粒度重跑 (避免重复 execute→render)。
        """
        verify = self._results.get("verify")
        if not verify or verify.status != StageStatus.DONE:
            return False

        # 强制类型清洗：None / 字符串 / 非数值 一律归零，保持 float 防止格式化崩溃
        raw_score = verify.data.get("score")
        try:
            score = 0.0 if raw_score is None else float(raw_score)
        except (TypeError, ValueError):
            score = 0.0
        passed = bool(verify.data.get("verified", False))

        self._log(f"Quality gate: score={score:.1f}, passed={passed}")

        # 上游产物为占位视频 (placeholder) 时, 标记质量降级 (不中断流程)
        render = self._results.get("render")
        if render and render.status == StageStatus.DONE and render.data.get("placeholder"):
            verify.data["quality_degraded"] = True
            self._log("Quality gate: upstream render is placeholder, marking quality_degraded")

        if passed and score >= float(self.config.min_quality_score):
            return False  # 质量达标，不需要迭代
        
        # 【P1 反馈闭环】verify 已做多轮优化:
        #   - 如果优化后分数达标 → 不重跑
        #   - 如果优化后分数仍不达标 → 允许粗粒度重跑 (verify→execute 回环)
        if verify.data.get("optimization_applied", False):
            passes = verify.data.get("optimization_passes", 0)
            final_score = float(verify.data.get("final_score", score))
            if final_score >= float(self.config.min_quality_score):
                self._log(
                    f"Quality gate: multi-pass optimization succeeded "
                    f"(passes={passes}, final={final_score:.1f}), skip retry"
                )
                return False
            else:
                self._log(
                    f"Quality gate: multi-pass optimization INSUFFICIENT "
                    f"(passes={passes}, final={final_score:.1f} < "
                    f"threshold={self.config.min_quality_score}), "
                    f"triggering verify->execute re-do"
                )
                # 调整执行参数, 让下轮 execute 使用不同策略
                self._adjust_params_for_retry(verify.data)
                # 不返回 False, 继续往下走 retry 逻辑

        if self._iteration >= int(self.config.max_quality_iterations) - 1:
            self._log("Quality gate: max iterations reached, accepting result")
            # 迭代耗尽照收, 但标记质量降级供下游感知
            verify.data["quality_degraded"] = True
            return False

        # 需要迭代 — 先应用 FeedbackExecutor 增强当前视频
        # 【Loop Engineering】语义硬否决/语义不达标也走调参, 确保下轮 execute 换策略;
        # 硬否决类灾难问题 (黑帧/文件过小) FFmpeg 增强救不回, 只能靠重跑 execute/render
        self._adjust_params_for_retry(verify.data)
        recs = verify.data.get("recommendations", [])
        self._log(f"Quality gate: RETRY needed. Recommendations: {recs}")
        self._apply_quality_enhancement(verify.data)
        return True

    def _apply_quality_enhancement(self, verify_data: Dict):
        """将质检反馈转化为实际视频增强，存储增强路径供下轮迭代使用"""
        render = self._results.get("render")
        if not render or render.status != StageStatus.DONE:
            return

        output_path = render.data.get("output_path", "")
        if not output_path or not Path(output_path).exists():
            return

        try:
            from pipeline.feedback_executor import FeedbackExecutor
            executor = FeedbackExecutor(self.config.ffmpeg_bin or "")

            # 构建质检报告
            quality_report = {
                "score": verify_data.get("score", 50),
                "checks": verify_data.get("checks", {}),
                "suggestions": verify_data.get("recommendations", []),
            }

            # 执行增强
            enhanced_path = str(Path(output_path).parent / f"{Path(output_path).stem}_enhanced.mp4")
            result = executor.execute(output_path, quality_report, enhanced_path)

            if result.get("success") and Path(enhanced_path).exists():
                self._enhanced_video_path = enhanced_path
                actions = result.get("actions", [])
                self._log(f"Quality enhancement: {len(actions)} actions applied -> {enhanced_path}")
                for a in actions:
                    self._log(f"  [{a['type']}] {a['reason']}")
            else:
                self._log(f"Quality enhancement failed: {result.get('error', 'unknown')}", "WARN")

        except Exception as e:
            self._log(f"Quality enhancement error: {e}", "WARN")

    def _adjust_params_for_retry(self, verify_data: Dict):
        """P1 反馈闭环: 根据 verify 反馈调整 execute 参数, 让下轮重跑使用不同策略。

        调整策略:
          1. 切换转场类型 (避免重复使用同一转场)
          2. 增加效果强度 (对比度/饱和度 +10%)
          3. 增加段时长 (从 3s → 4s, 减少切换频率)
          4. 记录重试原因供 learn 阶段消费
        """
        recommendations = verify_data.get("recommendations", [])
        checks = verify_data.get("checks", {})
        score = verify_data.get("final_score", verify_data.get("score", 0))

        # 将调整参数存入 _results 供下轮 execute 读取
        retry_adjustments: Dict[str, Any] = {
            "iteration": self._iteration + 1,
            "reason": f"score={score} < threshold={self.config.min_quality_score}",
            "recommendations": recommendations,
        }

        # 策略 1: 切换转场类型
        prev_plan = self._results.get("plan")
        if prev_plan and prev_plan.data:
            old_transitions = prev_plan.data.get("transition_plan", [])
            # 旋转到下一组转场类型
            _ALT_TRANSITIONS = [
                [{"type": "smoothleft", "duration": 0.5}, {"type": "radial", "duration": 0.6}],
                [{"type": "wipeleft", "duration": 0.4}, {"type": "circlecrop", "duration": 0.5}],
                [{"type": "dissolve", "duration": 0.7}, {"type": "slideright", "duration": 0.5}],
            ]
            alt_set = _ALT_TRANSITIONS[self._iteration % len(_ALT_TRANSITIONS)]
            new_transitions = []
            for i, t in enumerate(old_transitions):
                new_t = dict(t)
                alt = alt_set[i % len(alt_set)]
                new_t["type"] = alt["type"]
                new_t["duration"] = alt["duration"]
                new_transitions.append(new_t)
            if new_transitions:
                prev_plan.data["transition_plan"] = new_transitions
                retry_adjustments["new_transitions"] = [t["type"] for t in new_transitions]

            # 策略 2: 增强效果参数
            effect_stack = prev_plan.data.get("effect_stack", [])
            for eff in effect_stack:
                params = eff.get("params", {})
                # 对比度 +10%
                if "contrast" in params:
                    params["contrast"] = round(float(params["contrast"]) * 1.1, 3)
                # 饱和度 +10%
                if "saturation" in params:
                    params["saturation"] = round(float(params["saturation"]) * 1.1, 3)
                # 锐化 +20%
                if "sharpen_amount" in params:
                    params["sharpen_amount"] = round(float(params["sharpen_amount"]) * 1.2, 2)
            retry_adjustments["effects_boosted"] = True

        # 策略 3: 增加段时长 (减少切换频率, 提升观感)
        retry_adjustments["segment_duration_boost"] = 1.3  # 下轮段时长 x1.3

        # 存入 _results 供下轮读取
        self._results["_retry_adjustments"] = StageResult(
            stage="_retry_adjustments",
            status=StageStatus.DONE,
            data=retry_adjustments,
        )
        self._log(
            f"[FEEDBACK] Retry adjustments prepared: "
            f"transitions={retry_adjustments.get('new_transitions', 'unchanged')} "
            f"effects_boosted={retry_adjustments.get('effects_boosted', False)} "
            f"seg_dur_x={retry_adjustments.get('segment_duration_boost', 1.0)}"
        )

    # ----------------------------------------------------------------
    #  辅助方法
    # ----------------------------------------------------------------

    def _merge_style_sources(self, *style_dicts: Dict) -> Dict:
        """合并多个风格来源 (KB + VRS + 默认)"""
        merged = {}
        for d in style_dicts:
            if isinstance(d, dict):
                for k, v in d.items():
                    if k not in merged or v:
                        merged[k] = v
        return merged

    def _get_previous_data(self) -> Dict:
        """增强版上下文聚合器 (P4: 跨阶段上下文智能传播)
        
        确保关键上下文（VRS发现、KB推荐、历史反馈、错误记忆）在阶段间完整传播。
        """
        merged = {}
        for stage_name in self.STAGES:
            if stage_name in self._results:
                r = self._results[stage_name]
                if r.status == StageStatus.DONE:
                    merged[stage_name] = r.data
        
        # v2增强: 注入全局上下文 (P4)
        merged["_global"] = {
            "vrs_result": self._vrs_result,
            "kb_experience": self._results.get("_kb_experience", StageResult(stage="_kb_experience", status=StageStatus.SKIPPED)).data if "_kb_experience" in self._results else {},
            "iteration": self._iteration,
            "mode": self.mode.value,
            "run_id": self.run_id,
            "config_summary": {
                "use_davinci": self.config.use_davinci_render,
                "enable_vrs": self.config.enable_vrs,
                "style_match": self.config.style_match,
                "use_knowledge": self.config.use_knowledge,
                "enable_feedback_loop": self.config.enable_feedback_loop,
                "max_quality_iterations": self.config.max_quality_iterations,
            },
        }
        
        # v2增强: 注入错误记忆（供后续阶段参考）(P4 + P0)
        merged["_error_memory"] = self._get_relevant_error_patterns()
        
        # 包含 VRS 结果 (向后兼容)
        if self._vrs_result:
            merged["_vrs"] = self._vrs_result
        
        return merged
    
    def _get_relevant_error_patterns(self) -> Dict:
        """获取与当前上下文相关的错误模式 (P0集成)"""
        try:
            from pipeline.feedback_loop import get_error_memory
            memory = get_error_memory()
            stats = memory.get_statistics()
            
            # 返回统计信息和已知陷阱列表
            return {
                "total_patterns": stats.get("total_patterns", 0),
                "overall_success_rate": stats.get("overall_success_rate", 0),
                "known_pitfalls": list(memory.KNOWN_ENGINE_PITFALLS.keys()),
                "by_error_type": stats.get("by_error_type", {}),
            }
        except Exception as e:
            logger.debug(f"[Pipeline] Error memory not available: {e}")
            return {}

    def _persist_stage(self, stage_name: str, result: StageResult):
        path = self._persist_dir / f"{stage_name}.json"
        data = {
            "stage": result.stage,
            "status": result.status.value,
            "data": result.data,
            "error": result.error,
            "duration_sec": result.duration_sec,
            "timestamp": result.timestamp,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception:
            pass

    def _persist_result(self, result: PipelineResult):
        path = self._persist_dir / "pipeline_result.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_result(self, total: float) -> PipelineResult:
        errors = [r.error for r in self._results.values() if r.error]
        all_done = all(r.status in (StageStatus.DONE, StageStatus.SKIPPED)
                       for r in self._results.values() if not r.stage.startswith("_"))
        any_done = any(r.status == StageStatus.DONE for r in self._results.values())

        output_path = ""
        project_path = ""
        render_engine = ""
        execution_mode = ""
        if "render" in self._results and self._results["render"].status == StageStatus.DONE:
            output_path = self._results["render"].data.get("output_path", "")
            render_engine = self._results["render"].data.get("render_engine", "")
        if "execute" in self._results and self._results["execute"].status == StageStatus.DONE:
            project_path = self._results["execute"].data.get("project_path", "")
            execution_mode = self._results["execute"].data.get("execution_mode", "")

        quality_score = 0.0
        if "verify" in self._results and self._results["verify"].status == StageStatus.DONE:
            vdata = self._results["verify"].data
            raw_score = vdata.get("score") if isinstance(vdata, dict) else None
            # 【H级修复P2-2-A#2】异常样本或非数值 score 一律归零，避免 PipelineResult 字段 str/None 类型不稳定
            if raw_score is None or (isinstance(vdata, dict) and vdata.get("is_error_sample", False)):
                quality_score = 0.0
            else:
                try:
                    quality_score = float(raw_score)
                except (TypeError, ValueError):
                    self._log(
                        f"[BUILD] WARN: verify score={raw_score!r} cannot cast to float, "
                        "force 0.0 to keep type stability",
                        "WARN",
                    )
                    quality_score = 0.0

        return PipelineResult(
            run_id=self.run_id,
            status="success" if all_done else ("partial" if any_done else "failed"),
            mode=self.mode.value,
            stages=dict(self._results),
            output_path=output_path,
            project_path=project_path,
            total_duration_sec=total,
            quality_score=quality_score,
            iterations=self._iteration + 1,
            errors=errors,
            vrs_analysis=self._vrs_result,
            render_engine=render_engine,
            execution_mode=execution_mode,
        )


# ============================================================================
#  Fallback 阶段实现 (当 stages/ 子模块不可用时)
# ============================================================================

class _FallbackPerception:
    def __init__(self, config): self.config = config
    def run(self, prev): return {"source": "fallback", "topic": self.config.input_topic}

class _FallbackAnalysis:
    def __init__(self, config): self.config = config
    def run(self, prev): return {"source": "fallback", "analysis": "basic"}

class _FallbackPlanning:
    def __init__(self, config, kb):
        self.config = config
        self.kb = kb
    def run(self, prev):
        script = {"title": self.config.input_topic or "Pipeline Output", "segments": []}
        kb_ctx = self.kb.get_style_context(self.config.input_topic) if self.config.use_knowledge else {}
        return {"script": script, "style_params": kb_ctx, "shot_list": [], "transition_plan": [], "effect_stack": []}

class _FallbackExecution:
    def __init__(self, config): self.config = config
    def run(self, prev):
        plan = prev.get("plan", {})
        return {"project_path": "", "composition": "", "layers_created": 0, "effects_applied": 0}

class _FallbackRendering:
    def __init__(self, config): self.config = config
    def run(self, prev):
        return {"output_path": "", "rendered": False, "note": "Rendering requires AE or FFmpeg"}


# ============================================================================
# Phase C 入口绑定：阶段完成后统一校验形式化不变量。
#
# C1: 阶段结果 data 补充不变量所需字段（真实映射，不硬编码假数据）。
#     - execute: 该阶段仅产生图层/效果计数（layers_created / effects_applied），
#       不生成结构化 ae_layers（无 position/rotation 数据），故写入空列表但带
#       字段存在，由 check_invariants 的缺数据告警处理（区分"未测量"与"真实值"）。
#     - render: 渲染引擎真实使用 "-b:v 4M" / "fps=30"（见 ffmpeg_edit_engine.py
#       与 pipeline/stages/rendering.py 实际命令），映射为 ffmpeg_params（bps 整数）；
#       ae_render_time_ms 由渲染耗时实测值 render_time_sec（秒）换算。
# C2: check_invariants 违规 → 包装为 StageResult(FAILED) 返回，不裸抛，
#     保证 run_all / run_stage 主循环契约稳定（始终返回 StageResult）。
# L2(b): 仅 ModuleNotFoundError（formal_spec 模块缺失）降级；其他异常（如语法
#     错误）向上传播，避免掩盖真实故障。
# M3: 绑定幂等 —— 仅在首次执行时保存原始 _run_stage 并安装包装器；重复执行
#     本模块（importlib.reload / 重复 import）不会二次包装，避免递归与双日志。
#     恢复方法: UnifiedPipeline._run_stage = UnifiedPipeline._legacy_run_stage
#     （再删除 _legacy_run_stage_stored 标记后重新 import 本模块）。
# ============================================================================

# 渲染/执行引擎真实使用的 FFmpeg 参数（-b:v 4M / fps=30），单位统一 bps 整数。
_INVARIANT_FFMPEG_BITRATE_BPS: int = 4_000_000
_INVARIANT_FFMPEG_FRAMERATE: float = 30.0


def _attach_stage_invariant_data(
    self, stage_name: str, result: StageResult,
) -> None:
    """C1: 为阶段结果补齐不变量所需字段（真实映射，不硬编码假数据）。

    仅在阶段成功且产出数据时补充；阶段自身已提供对应字段时不覆盖
    （保留真实值，如假阶段测试注入的越界 ae_layers）。
    """
    if result.status != StageStatus.DONE or not result.data:
        return
    if stage_name == "execute" and "ae_layers" not in result.data:
        # 阶段未生成结构化图层数据 → 空列表占位（字段存在，由不变量告警"未测量"）
        result.data["ae_layers"] = []
    elif stage_name == "render":
        data = result.data
        if "ffmpeg_params" not in data:
            # 渲染阶段真实产生 ffmpeg 参数（渲染引擎 -b:v 4M / fps=30 映射为 bps）
            data["ffmpeg_params"] = {
                "bitrate": _INVARIANT_FFMPEG_BITRATE_BPS,
                "framerate": _INVARIANT_FFMPEG_FRAMERATE,
            }
        if "ae_render_time_ms" not in data:
            # 渲染耗时实测值: render_time_sec（秒）→ 毫秒；无法换算则保持缺字段
            sec = data.get("render_time_sec")
            if sec is not None:
                try:
                    data["ae_render_time_ms"] = int(float(sec) * 1000)
                except (TypeError, ValueError):
                    pass  # 保持缺字段，由不变量告警


def _run_stage_with_invariants(self, stage_name: str) -> StageResult:
    result = _UnifiedPipeline_legacy_run_stage(self, stage_name)
    try:
        # 先导入再进入校验: 模块缺失时在 try 外抛 ModuleNotFoundError,
        # 由下方外层处理器降级 (旧写法把 import 放 try 内, 失败后
        # `except InvariantViolation` 因名字未定义反而抛 UnboundLocalError)
        from core.formal_spec import InvariantViolation, check_invariants
        try:
            self._attach_stage_invariant_data(stage_name, result)
            context = self._formal_spec_context(stage_name, result)
            check_invariants(
                context,
                skip=bool(getattr(self.config, "debug_skip_invariants", False)),
            )
        except InvariantViolation as e:
            # C2: 违规不裸抛 — 包装为 FAILED StageResult，保留阶段数据
            logger.error("Stage [%s] invariant violation: %s", stage_name, e)
            return StageResult(
                stage=stage_name,
                status=StageStatus.FAILED,
                data=result.data,
                error=f"[invariants] {e}",
            )
        except (TypeError, ValueError) as e:
            # C2/H1: 数据形态异常 → 包装为 FAILED StageResult，不裸抛
            logger.error("Stage [%s] invariant data error: %s", stage_name, e)
            return StageResult(
                stage=stage_name,
                status=StageStatus.FAILED,
                data=result.data,
                error=f"[invariants] data error: {e}",
            )
    except ModuleNotFoundError:
        # L2(b): 仅 formal_spec 模块缺失时降级；其他异常（语法错误等）向上传播
        logger.warning("FormalSpec 模块不可用，跳过不变量校验")
    return result


def _formal_spec_context(self, stage_name: str, result: StageResult) -> Dict[str, Any]:
    # L2(a): 先合并阶段数据，再设置固定键 stage/stage_result，
    # 防止阶段数据键（如 "stage"）覆盖固定键。
    context: Dict[str, Any] = dict(result.data or {})
    context["stage"] = stage_name
    context["stage_result"] = result
    return context


# M3: 幂等绑定 — 首次执行时保存原始实现并安装包装器；reload/重复执行不再二次包装
if not hasattr(UnifiedPipeline, "_legacy_run_stage_stored"):
    _UnifiedPipeline_legacy_run_stage = UnifiedPipeline._run_stage
    UnifiedPipeline._legacy_run_stage = _UnifiedPipeline_legacy_run_stage
    UnifiedPipeline._legacy_run_stage_stored = True
    UnifiedPipeline._attach_stage_invariant_data = _attach_stage_invariant_data
    UnifiedPipeline._formal_spec_context = _formal_spec_context
    UnifiedPipeline._run_stage_with_invariants = _run_stage_with_invariants
    UnifiedPipeline._run_stage = _run_stage_with_invariants
else:
    _UnifiedPipeline_legacy_run_stage = UnifiedPipeline._legacy_run_stage
    UnifiedPipeline._legacy_run_stage = _UnifiedPipeline_legacy_run_stage
    UnifiedPipeline._legacy_run_stage_stored = True
    UnifiedPipeline._attach_stage_invariant_data = _attach_stage_invariant_data
    UnifiedPipeline._formal_spec_context = _formal_spec_context
    UnifiedPipeline._run_stage_with_invariants = _run_stage_with_invariants
