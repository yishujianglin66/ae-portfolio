#!/usr/bin/env python3
"""
LLM 网关层 - LLMGateway v1.0

设计原则（基于 OmniRoute 架构）：
1. 统一接口：兼容 OpenAI API 格式，支持任意 OmniRoute 网关
2. 智能路由：根据任务类型自动选择最优模型
3. 自动降级：Provider 失败时自动 failover 到备用
4. Token 优化：集成压缩语法（Caveman 风格）
5. 可观测：内置 token 用量追踪和成本监控

架构参考：
- OmniRoute (diegosouzapw/OmniRoute) — 多 Provider AI 网关
- Caveman (JuliusBrussee/caveman) — Token 压缩语法

集成方式：
    from core.llm_gateway import llm_gateway, chat, chat_with_routing

    # 简单调用
    response = await chat("分析这段视频的情绪", system_prompt="你是视频分析专家")

    # 路由调用（根据任务类型自动选模型）
    response = await chat_with_routing(
        "扣掉埼玉然后加发光",
        task_type="intent_classification"
    )
"""
import asyncio
import inspect
import json
import logging
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# 规范要求（.trae/rules/api-adaptation.md）："通过 observability.py 上报指标"。
# 守卫式 import：observability 不可用时优雅降级，不影响网关正常工作。
try:
    from core import observability as _observability
except Exception:  # pragma: no cover - 极端环境兜底
    _observability = None


def _parse_env_flag(key: str, default: bool) -> bool:
    """解析布尔型环境变量（大小写不敏感的 truthy 集合）。

    truthy: 1/true/yes/on；其余非空值一律视为 falsy；
    未设置或空串返回 ``default``。
    """
    v = os.environ.get(key)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _sanitize_log_text(text: str) -> str:
    """日志脱敏：移除或掩码敏感信息。

    脱敏范围：
    - Authorization: Bearer <token>
    - api_key=<value> / apikey=<value> / X-API-Key header
    - sk- / pk- / rk- 开头的 API Key（OpenAI/Anthropic/ModelScope 风格）
    - 各类 token / secret / password / key / auth 值
    - 可能包含密钥的长十六进制/base64 字符串

    Args:
        text: 原始日志文本

    Returns:
        脱敏后的文本
    """
    if not text:
        return text

    result = text

    # 0. 最高优先级：掩码 PEM 格式密钥块（-----BEGIN ... KEY----- ... -----END ... KEY-----）
    #    包括 RSA/EC/OPENSSH/DSA 等 PRIVATE KEY 和 PUBLIC KEY，中间是多行 base64
    result = re.sub(
        r'-----BEGIN [A-Z0-9 ]*KEY-----[\s\S]+?-----END [A-Z0-9 ]*KEY-----',
        '***PEM_KEY_REDACTED***',
        result,
    )

    # 1. 优先掩码 JWT（三段式 base64，eyJ 开头）—— 避免被后面的 Bearer 规则先吞掉
    result = re.sub(
        r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+',
        '***JWT_REDACTED***',
        result,
    )

    # 2. Authorization: Bearer xxx / Basic xxx / Token xxx（JWT 已被替换，这里匹配其他 token）
    result = re.sub(
        r'(?i)(authorization\s*[:=]\s*(?:bearer|basic|token)\s+)[A-Za-z0-9_\-\.=+/]{6,}',
        r'\1***REDACTED***',
        result,
    )

    # 3. X-API-Key / api_key / apikey / apiKey = xxx
    result = re.sub(
        r'(?i)(x-?api-?key\s*[:=]\s*|api[_-]?key\s*[=:]\s*)[A-Za-z0-9_\-]{6,}',
        r'\1***REDACTED***',
        result,
    )

    # 4. sk- / pk- / rk- / mk- 开头的密钥（OpenAI/Anthropic/ModelScope 等风格）
    result = re.sub(
        r'(?i)\b([spr]k-)[A-Za-z0-9_\-]{16,}',
        r'\1***REDACTED***',
        result,
    )

    # 5. 常见敏感字段 = xxx（包括含斜杠、加号、等号的 base64 内容如 AWS 密钥、私钥）
    #    注意：private_key 等 PEM 类字段值包含空格/换行且很长，单独用"到行尾"规则掩码
    pem_keywords = ['private_key', 'private_key_pem', 'privatekey', 'rsa_private_key']
    for keyword in pem_keywords:
        result = re.sub(
            rf'(?i)({keyword}\s*[=:]\s*).+',
            r'\1***REDACTED***',
            result,
        )

    #    普通敏感字段匹配到下一个空白/&/"/'为止（适用于URL参数、短token）
    sensitive_keywords = [
        'password', 'secret', 'token', 'auth', 'credential',
        'access_key', 'secret_key', 'app_key',
    ]
    for keyword in sensitive_keywords:
        # 匹配到行尾或下一个空白/&/"/'为止，覆盖 base64 中出现的 +/= 字符
        # 值字符类排除 '*'，避免二次改写已脱敏标记（如 JWT/REDACTED）
        result = re.sub(
            rf'(?i)({keyword}\s*[=:]\s*)[^\s&"\')*]+',
            r'\1***REDACTED***',
            result,
        )

    return result


class LLMUnavailableError(RuntimeError):
    """所有 LLM Provider 均不可用时抛出。

    由 ``LLMGateway.chat`` / ``chat_with_routing`` 在严格模式下抛出，
    也可由业务层在收到 ``LLMResponse(success=False)`` 时主动抛出。
    上层（如 API 端点）应捕获此异常并返回 503 Service Unavailable。
    """


class TaskType(Enum):
    """LLM 任务类型 — 决定路由到哪个模型"""
    INTENT_CLASSIFICATION = auto()   # 意图分类
    SCENE_DESCRIPTION = auto()       # 场景描述生成
    EFFECT_PLANNING = auto()         # 效果规划
    QUALITY_REVIEW = auto()          # 质量审查（双模型对抗）
    FEEDBACK_ANALYSIS = auto()       # 反馈分析
    PARAMETER_OPTIMIZATION = auto()  # 参数优化
    EFFECT_SEARCH = auto()           # 效果知识图谱搜索
    GENERAL = auto()                 # 通用对话
    VIDEO_GENERATION = auto()       # H3 文生视频/图生视频
    VIDEO_EDITING = auto()          # H3 视频编辑（字幕/特效/BGM/剪辑）
    IMAGE_GENERATION = auto()       # 文生图（含任何 AI 图像生成）
    SUBTITLE_MODIFICATION = auto()  # 视频内字幕文字修改
    STYLE_TRANSFER = auto()         # 风格化/手绘特效转换
    MOTION_TRANSFER = auto()        # V2V 动作迁移
    OBJECT_REPLACEMENT = auto()     # 局部物体/人物替换
    SCENE_ALTERATION = auto()       # 场景环境修改
    RATE_ADJUSTMENT = auto()        # 镜头快慢/速度调整
    INPAINTING = auto()             # 画面瑕疵修复/擦除
    VISION_UNDERSTANDING = auto()   # 图像/视频帧深度理解（保持与 api-adaptation.md 一致）
    DEEP_REASONING = auto()         # 深度推理（分镜推演/复杂逻辑，路由到 thinking 档）
    # ── 开源项目集成新增 TaskType (2026-08-11) ──────────────────────────
    SOCIAL_MEDIA_CRAWL = auto()     # 社媒素材采集 (MediaCrawler)
    WEB_CONTEXT_FETCH = auto()      # 联网上下文获取 (Firecrawl)
    SCENE_GENERATION_3D = auto()    # 3D 场景生成 (BlenderProc)
    COMFYUI_WORKFLOW = auto()       # ComfyUI 工作流生成/执行
    ADOBE_AUTOMATION = auto()       # Adobe 套件自动化 (adobe-mcp)
    RENDER_AUTOMATION = auto()      # 模板化渲染自动化 (nexrender)
    SUBTITLE_GENERATION = auto()    # 字幕自动生成 (auto-subs/faster-whisper)


class ModelTier(Enum):
    """模型档位 — 按能力/成本分层"""
    TIER_1_LOCAL_SPECIALIZED = "tier1_local"    # 本地垂直小模型（最快、最便宜）
    TIER_2_MIDTIER_GENERAL = "tier2_midtier"      # 中端通用模型（性价比均衡）
    TIER_3_FLAGSHIP_REASONING = "tier3_flagship"  # 旗舰推理模型（最强、最贵）


class ConfidenceLevel(Enum):
    """置信度级别"""
    VERY_LOW = "very_low"     # < 0.3
    LOW = "low"              # 0.3 - 0.5
    MEDIUM = "medium"        # 0.5 - 0.7
    HIGH = "high"            # 0.7 - 0.9
    VERY_HIGH = "very_high"  # >= 0.9


class ProviderStatus(Enum):
    """Provider 健康状态"""
    HEALTHY = auto()
    DEGRADED = auto()
    UNAVAILABLE = auto()
    HALF_OPEN = auto()  # 熔断冷却结束，放行单次探测请求（半开状态）


@dataclass
class LLMConfig:
    """LLM 配置"""
    base_url: str = "http://localhost:5273/v1"
    api_key: str = ""
    default_model: str = "auto"
    timeout_seconds: int = 90
    max_retries: int = 3
    retry_delay_ms: int = 1000
    enable_compression: bool = False
    enable_fallback: bool = True

    # 分层路由配置
    enable_tiered_routing: bool = True
    prefer_small_model: bool = False

    # 各档位配置
    tier_config: dict[ModelTier, dict[str, Any]] = field(default_factory=lambda: {
        ModelTier.TIER_1_LOCAL_SPECIALIZED: {
            "enabled": True,
            "providers": ["nvidia-local"],
            "max_retries": 1,
            "timeout_seconds": 15,
            "cost_per_1k_input": 0.0,
            "cost_per_1k_output": 0.0,
        },
        ModelTier.TIER_2_MIDTIER_GENERAL: {
            "enabled": True,
            "providers": ["claude-fast", "deepseek-flash"],
            "max_retries": 2,
            "timeout_seconds": 30,
            "cost_per_1k_input": 0.0001,
            "cost_per_1k_output": 0.0003,
        },
        ModelTier.TIER_3_FLAGSHIP_REASONING: {
            "enabled": True,
            "providers": ["claude-opus", "gpt-4"],
            "max_retries": 3,
            "timeout_seconds": 90,
            "cost_per_1k_input": 0.015,
            "cost_per_1k_output": 0.075,
        },
    })

    # 级联路由配置
    enable_cascade: bool = True
    cascade_confidence_threshold: float = 0.7
    cascade_max_upgrades: int = 2
    cascade_enable_skip_tiers: list[str] = field(default_factory=list)
    confidence_extraction_prompt: str = ""
    auto_confidence_calibration: dict[str, float] = field(default_factory=lambda: {
        ModelTier.TIER_1_LOCAL_SPECIALIZED.value: -0.1,
        ModelTier.TIER_2_MIDTIER_GENERAL.value: 0.0,
        ModelTier.TIER_3_FLAGSHIP_REASONING.value: 0.1,
    })

    # 任务→模型路由表
    model_routing: dict[TaskType, str] = field(default_factory=lambda: {
        TaskType.INTENT_CLASSIFICATION: "auto",
        TaskType.SCENE_DESCRIPTION: "auto",
        TaskType.EFFECT_PLANNING: "auto",
        TaskType.QUALITY_REVIEW: "auto",
        TaskType.FEEDBACK_ANALYSIS: "auto",
        TaskType.PARAMETER_OPTIMIZATION: "auto",
        TaskType.EFFECT_SEARCH: "auto",
        TaskType.GENERAL: "auto",
        TaskType.VIDEO_GENERATION: "auto",
        TaskType.VIDEO_EDITING: "auto",
        TaskType.IMAGE_GENERATION: "auto",
        TaskType.SUBTITLE_MODIFICATION: "auto",
        TaskType.STYLE_TRANSFER: "auto",
        TaskType.MOTION_TRANSFER: "auto",
        TaskType.OBJECT_REPLACEMENT: "auto",
        TaskType.SCENE_ALTERATION: "auto",
        TaskType.RATE_ADJUSTMENT: "auto",
        TaskType.INPAINTING: "auto",
        TaskType.VISION_UNDERSTANDING: "auto",
        TaskType.DEEP_REASONING: "auto",
        # 开源项目集成新增 TaskType（2026-08-11）— 必须与 TASK_TIER_MAP 保持一致
        TaskType.SOCIAL_MEDIA_CRAWL: "auto",
        TaskType.WEB_CONTEXT_FETCH: "auto",
        TaskType.SCENE_GENERATION_3D: "auto",
        TaskType.COMFYUI_WORKFLOW: "auto",
        TaskType.ADOBE_AUTOMATION: "auto",
        TaskType.RENDER_AUTOMATION: "auto",
        TaskType.SUBTITLE_GENERATION: "auto",
    })

    # 降级 Provider 列表
    fallback_providers: list[dict[str, str]] = field(default_factory=list)

    # 多Provider配置（VRS v2.0 任务级路由）
    # 格式: {"claude": {"base_url":"...", "api_key":"...",
    #          "models": {"vision":"...", "thinking":"...", "fast":"..."}}, ...}
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str = ""
    model: str = ""
    provider: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    latency_ms: float = 0.0
    success: bool = False
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    tier: str = ""
    cost_usd: float = 0.0
    tier_upgraded: bool = False
    confidence: float = 0.0
    confidence_level: str = ""
    confidence_reason: str = ""
    cascade_path: list[str] = field(default_factory=list)
    upgrade_count: int = 0
    saved_cost_usd: float = 0.0
    # ---- 多模态计费（per-second / per-image，非 token 口径）----
    video_seconds: float = 0.0           # H3 视频生成秒数（用于计费）
    video_resolution: str = ""           # "768p" / "2k"，决定单价
    image_count: int = 0                 # 图像生成张数
    modality_cost_usd: float = 0.0       # 多模态部分累计成本（秒数*单价 + 张数*单张单价），单独统计不覆盖 cost_usd


@dataclass
class ProviderHealth:
    """Provider 健康状态跟踪"""
    name: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    last_error: str = ""
    total_requests: int = 0
    total_failures: int = 0
    tier: ModelTier | None = None
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    total_video_seconds: float = 0.0     # 累计生成视频秒数
    total_images_generated: int = 0      # 累计生成图片张数
    # 熔断器参数：连续失败 CIRCUIT_FAILURE_THRESHOLD 次触发熔断，
    # 冷却 RECOVERY_INTERVAL_SEC 秒后转入 HALF_OPEN 单次探测
    CIRCUIT_FAILURE_THRESHOLD: int = 3
    # 自动恢复：UNAVAILABLE 状态下 60 秒后自动重试
    RECOVERY_INTERVAL_SEC: int = 60
    # 性能追踪（健康感知排序用）
    total_successes: int = 0
    total_latency_ms: float = 0.0
    # 半开探测计数（同一时刻只放行 1 个探测请求）
    half_open_probes: int = 0


# -----------------------------------------------------------------------------
# Caveman 风格 Token 压缩器
# -----------------------------------------------------------------------------

class TokenCompressor:
    """
    Token 压缩器 — 参考 caveman 项目的压缩语法

    压缩规则：
    1. 系统提示词压缩：去除冗余修饰词
    2. 输出格式约束：要求模型使用压缩格式回复
    3. 上下文裁剪：只保留关键信息
    """

    COMPRESSION_PROMPT = (
        "回复须简洁如穴居人：省略冠词/连接词/客套话，"
        "仅保留技术要点。用'|'分隔条目。"
    )

    # 系统提示词压缩映射
    COMPRESSION_MAP = {
        "请详细分析": "分析",
        "请生成": "生成",
        "请描述": "描述",
        "你需要": "须",
        "你应该": "须",
        "请注意": "注意",
        "非常重要": "重要",
        "请确保": "确保",
        "这是一个": "这是",
        "以下是": "如下",
    }

    def compress_prompt(self, prompt: str) -> str:
        """压缩提示词"""
        compressed = prompt
        for long, short in self.COMPRESSION_MAP.items():
            compressed = compressed.replace(long, short)
        return compressed

    def compress_system(self, system: str) -> str:
        """压缩系统提示词"""
        compressed = self.compress_prompt(system)
        if len(compressed) > 200:
            logging.getLogger(__name__).warning(
                f"系统提示词压缩后被截断：原长度 {len(compressed)} 超过 200 字符上限，"
                "可能丢失上下文信息（compression 已开启）"
            )
            compressed = compressed[:200] + "..."
        return compressed

    def get_compression_suffix(self) -> str:
        """获取压缩指令后缀"""
        return f"\n[{self.COMPRESSION_PROMPT}]"

    def decompress_response(self, response: str) -> str:
        """
        解压响应 — 将穴居人格式还原为正常格式
        """
        if not response:
            return response

        lines = response.split("|")
        if len(lines) <= 1:
            return response

        result_parts = []
        for line in lines:
            line = line.strip()
            if line:
                result_parts.append(line)

        return "\n".join(result_parts)


# -----------------------------------------------------------------------------
# 任务类型 → Provider + 模型类型 映射（VRS v2.0 多Provider路由）
# -----------------------------------------------------------------------------

# 当 LLMConfig.providers 非空时，chat_with_routing 优先按此表选择 Provider
# 与模型档位；失败再降级到原有单 Provider 逻辑。
# 2026-07-31: 接入 DeepSeek V4-Flash 正式版，将轻量任务路由到 deepseek 以降低成本
# 路由策略：
#   - 视觉/深度推理任务 → Claude（VISION/THINKING 档位）
#   - 意图分类/参数优化/反馈分析 → DeepSeek Flash 正式版（低成本、快速响应）
#   - 通用对话 → DeepSeek default（V4-Flash 正式版）
# 任务 → Provider/档位路由表 (2026-08-14 重路由: 弃用 DuckMiss 中转站)
# 成本策略:
#   - 视觉任务 → siliconflow vision (Qwen3-VL-30B-A3B, MoE 最省)
#   - 深度推理(分镜/质量审查) → doubao thinking (deepseek-v4-pro)
#   - 代码任务 → siliconflow code (Kimi-K2.7-Code 专用代码模型)
#   - 高频快速任务 → doubao flash (deepseek-v4-flash-ga 最新 GA 版)
TASK_PROVIDER_MAP: dict[TaskType, tuple[str, str]] = {
    TaskType.SCENE_DESCRIPTION: ("siliconflow", "vision"),  # 场景描述 → Qwen3-VL
    TaskType.EFFECT_PLANNING: ("doubao", "thinking"),       # 效果规划 → deepseek-v4-pro
    TaskType.INTENT_CLASSIFICATION: ("doubao", "flash"),    # 意图分类 → v4-flash-ga
    TaskType.QUALITY_REVIEW: ("doubao", "thinking"),        # 质量审查 → deepseek-v4-pro
    TaskType.PARAMETER_OPTIMIZATION: ("siliconflow", "code"),  # 参数优化 → Kimi-K2.7-Code
    TaskType.FEEDBACK_ANALYSIS: ("doubao", "flash"),        # 反馈分析 → v4-flash-ga
    TaskType.EFFECT_SEARCH: ("doubao", "flash"),            # 效果搜索 → v4-flash-ga
    TaskType.GENERAL: ("doubao", "default"),                # 通用 → default 档（下游档位回退自然覆盖 flash）
    TaskType.VIDEO_GENERATION: ("minimax_h3", "video_generation"),
    TaskType.VIDEO_EDITING: ("minimax_h3", "video_editing"),
    TaskType.IMAGE_GENERATION: ("minimax_h3", "image_generation"),
    TaskType.SUBTITLE_MODIFICATION: ("minimax_h3", "video_editing"),
    TaskType.STYLE_TRANSFER: ("minimax_h3", "video_editing"),
    TaskType.MOTION_TRANSFER: ("minimax_h3", "video_editing"),
    TaskType.OBJECT_REPLACEMENT: ("minimax_h3", "video_editing"),
    TaskType.SCENE_ALTERATION: ("minimax_h3", "video_editing"),
    TaskType.RATE_ADJUSTMENT: ("minimax_h3", "video_editing"),
    TaskType.INPAINTING: ("minimax_h3", "video_editing"),
    TaskType.VISION_UNDERSTANDING: ("siliconflow", "vision"),  # 视觉理解 → Qwen3-VL
    TaskType.DEEP_REASONING: ("doubao", "thinking"),        # 深度推理 → deepseek-v4-pro
    # ── 开源集成新增路由 (2026-08-11) ──────────────────────────────
    TaskType.SOCIAL_MEDIA_CRAWL: ("doubao", "flash"),     # 社媒采集 → 快速
    TaskType.WEB_CONTEXT_FETCH: ("doubao", "flash"),      # 联网获取 → 快速
    TaskType.SCENE_GENERATION_3D: ("siliconflow", "vision"),  # 3D场景 → Qwen3-VL
    TaskType.COMFYUI_WORKFLOW: ("siliconflow", "vision"),     # ComfyUI → Qwen3-VL
    TaskType.ADOBE_AUTOMATION: ("siliconflow", "code"),       # Adobe自动化 → Kimi-K2.7-Code
    TaskType.RENDER_AUTOMATION: ("siliconflow", "code"),      # 渲染自动化 → Kimi-K2.7-Code
    TaskType.SUBTITLE_GENERATION: ("local", "whisper"),       # 字幕生成 → 本地 whisper
}

TASK_TIER_MAP: dict[TaskType, ModelTier] = {
    TaskType.INTENT_CLASSIFICATION: ModelTier.TIER_1_LOCAL_SPECIALIZED,
    TaskType.EFFECT_SEARCH: ModelTier.TIER_1_LOCAL_SPECIALIZED,
    TaskType.FEEDBACK_ANALYSIS: ModelTier.TIER_1_LOCAL_SPECIALIZED,
    TaskType.PARAMETER_OPTIMIZATION: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.SCENE_DESCRIPTION: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.EFFECT_PLANNING: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.QUALITY_REVIEW: ModelTier.TIER_3_FLAGSHIP_REASONING,
    TaskType.GENERAL: ModelTier.TIER_2_MIDTIER_GENERAL,
    # VIDEO 类：涉及 H3 付费，默认 TIER_2（有配置可升级到 TIER_3 质量优先）
    TaskType.VIDEO_GENERATION: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.VIDEO_EDITING: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.IMAGE_GENERATION: ModelTier.TIER_2_MIDTIER_GENERAL,
    # 纯编辑类：TIER_1 快速响应
    TaskType.SUBTITLE_MODIFICATION: ModelTier.TIER_1_LOCAL_SPECIALIZED,
    TaskType.RATE_ADJUSTMENT: ModelTier.TIER_1_LOCAL_SPECIALIZED,
    # 视觉理解：TIER_3 旗舰推理
    TaskType.VISION_UNDERSTANDING: ModelTier.TIER_3_FLAGSHIP_REASONING,
    # 深度推理：TIER_3 旗舰推理
    TaskType.DEEP_REASONING: ModelTier.TIER_3_FLAGSHIP_REASONING,
    # 风格化/动作迁移等：TIER_2
    TaskType.STYLE_TRANSFER: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.MOTION_TRANSFER: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.OBJECT_REPLACEMENT: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.SCENE_ALTERATION: ModelTier.TIER_2_MIDTIER_GENERAL,
    TaskType.INPAINTING: ModelTier.TIER_2_MIDTIER_GENERAL,
    # ── 开源集成新增分层 (2026-08-11) ───────────────────────────────
    TaskType.SOCIAL_MEDIA_CRAWL: ModelTier.TIER_1_LOCAL_SPECIALIZED,   # 采集 → 本地快速
    TaskType.WEB_CONTEXT_FETCH: ModelTier.TIER_1_LOCAL_SPECIALIZED,    # 联网 → 本地快速
    TaskType.SCENE_GENERATION_3D: ModelTier.TIER_2_MIDTIER_GENERAL,    # 3D → 中端
    TaskType.COMFYUI_WORKFLOW: ModelTier.TIER_2_MIDTIER_GENERAL,       # AI生成 → 中端
    TaskType.ADOBE_AUTOMATION: ModelTier.TIER_1_LOCAL_SPECIALIZED,     # Adobe → 代码级
    TaskType.RENDER_AUTOMATION: ModelTier.TIER_1_LOCAL_SPECIALIZED,    # 渲染 → 代码级
    TaskType.SUBTITLE_GENERATION: ModelTier.TIER_1_LOCAL_SPECIALIZED,    # 字幕 → 本地 whisper
}


# -----------------------------------------------------------------------------
# Qwen 优先上位开关（AEKV_QWEN_PRIORITY）
# 开启后将深度推理/视觉理解任务的主选 Provider 切换为 qwen（高性价比备选）。
# 默认关闭；仅在 benchmark 验证质量达标后启用。qwen Provider 未注册时自动不生效。
# -----------------------------------------------------------------------------
QWEN_PRIORITY_TASKS: dict[TaskType, tuple[str, str]] = {
    TaskType.VISION_UNDERSTANDING: ("qwen", "vision"),    # 视觉理解档位
    TaskType.QUALITY_REVIEW: ("qwen", "thinking"),        # 深度推理档位
}


# -----------------------------------------------------------------------------
# LLM 网关核心
# -----------------------------------------------------------------------------

class LLMGateway:
    """
    LLM 网关 — 统一的 LLM 调用入口

    特性：
    1. 兼容 OpenAI API 格式（/v1/chat/completions）
    2. 支持 OmniRoute 网关（237+ providers, 90+ free）
    3. 智能路由：根据 TaskType 选择最优模型
    4. 自动降级：主 Provider 失败时 failover
    5. Token 压缩：集成 Caveman 语法
    6. 健康检查：跟踪 Provider 状态
    7. 可观测：token 用量、延迟、成功率
    """

    def __init__(self, config: LLMConfig | None = None):
        self._logger = logging.getLogger(f"{__name__}.LLMGateway")
        self._config = config or LLMConfig()
        self._compressor = TokenCompressor()
        self._provider_health: dict[str, ProviderHealth] = {}
        self._stats = {
            "total_requests": 0,
            "total_successes": 0,
            "total_failures": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_latency_ms": 0.0,
            "total_cost_usd": 0.0,
            "total_video_seconds": 0.0,
            "total_images_generated": 0,
            "total_modality_cost_usd": 0.0,
        }
        self._tier_stats: dict[ModelTier, dict[str, Any]] = {
            tier: {
                "total_requests": 0,
                "total_successes": 0,
                "total_failures": 0,
                "total_tokens_input": 0,
                "total_tokens_output": 0,
                "total_latency_ms": 0.0,
                "total_cost_usd": 0.0,
                "total_video_seconds": 0.0,
                "total_images_generated": 0,
                "total_modality_cost_usd": 0.0,
            }
            for tier in ModelTier
        }
        self._cascade_stats: dict[str, Any] = {
            "cascade_attempts": 0,
            "cascade_upgrades": 0,
            "cascade_savings_usd": 0.0,
            "cascade_total_path_length": 0,
            "cascade_avg_path_length": 0.0,
        }
        self._http_client = None
        # CRITICAL FIX(A7): asyncio.Lock 保护懒加载，防止并发首次调用创建多个 session；
        # 同时配合 _get_http_client 中的 loop 检测，避免跨事件循环复用旧 session
        self._http_client_lock = asyncio.Lock()
        self._local_adapters: dict[str, Any] = {}
        # key 状态后台刷新互斥标记（避免并发重复触发）
        self._key_refresh_running = False

        # P3: observability 接入（轻量；observability 不可用时为 None，所有 _obs_* 调用静默 noop）
        self._obs = _observability

        # 初始化 Provider 健康状态
        self._init_provider_health()

    def _init_provider_health(self) -> None:
        """初始化 Provider 健康跟踪"""
        # 清空旧状态（避免配置变更后遗留垃圾数据）
        self._provider_health.clear()

        # 主 Provider：同时注册 hostname 和 "primary" 两个 key
        primary_host = self._extract_provider_name(self._config.base_url)
        primary_health = ProviderHealth(name=primary_host)
        self._provider_health[primary_host] = primary_health
        self._provider_health["primary"] = primary_health

        # Fallback Provider：同时注册 hostname 和 "fallback_N" 两个 key
        for idx, fb in enumerate(self._config.fallback_providers):
            fb_url = fb.get("base_url", "")
            fb_host = self._extract_provider_name(fb_url)
            fb_name = f"fallback_{idx}"
            fb_health = ProviderHealth(name=fb_host)
            if fb_host and fb_host not in self._provider_health:
                self._provider_health[fb_host] = fb_health
            self._provider_health[fb_name] = fb_health

    def _extract_provider_name(self, url: str) -> str:
        """从 URL 提取 Provider 名称"""
        if not url:
            return "unknown"
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.hostname or url
        except Exception:
            return url

    # -------------------------------------------------------------------------
    # 配置
    # -------------------------------------------------------------------------

    def configure(self, config: LLMConfig) -> None:
        """更新配置"""
        self._config = config
        self._init_provider_health()
        self._logger.info(f"LLM 网关配置已更新: {config.base_url}")

    def configure_from_env(self) -> None:
        """从环境变量加载配置。

        读取优先级（避免某些前缀已配置但主配置为空导致请求打空）：
            base_url : AEKV_LLM_BASE_URL > OPENAI_BASE_URL > DUCK_MISS_BASE_URL
                       > MODELSCOPE_BASE_URL > KIMI_BASE_URL / KIMI_LOCAL_BASE_URL
                       > DEEPSEEK_BASE_URL > DOUBAO_BASE_URL
            api_key  : AEKV_LLM_API_KEY > OPENAI_API_KEY > DUCK_MISS_API_KEY
                       > MODELSCOPE_API_KEY > KIMI_API_KEY
                       > DEEPSEEK_API_KEY > DOUBAO_API_KEY
            model    : AEKV_LLM_MODEL > DUCK_MISS_DEFAULT_MODEL
                       > MODELSCOPE_MODEL > KIMI_MODEL
                       > DEEPSEEK_MODEL > DOUBAO_MODEL > "auto"
        """
        def _first(*candidates: str) -> str:
            for c in candidates:
                v = os.environ.get(c, "")
                if v:
                    return v
            return ""

        base_url = _first(
            "AEKV_LLM_BASE_URL",
            "OPENAI_BASE_URL",
            "DUCK_MISS_BASE_URL", "DUCKMISS_BASE_URL",
            "MODELSCOPE_BASE_URL",
            "KIMI_LOCAL_BASE_URL", "KIMI_BASE_URL",
            "DEEPSEEK_BASE_URL",
            "DOUBAO_BASE_URL",
        )
        api_key = _first(
            "AEKV_LLM_API_KEY",
            "OPENAI_API_KEY",
            "DUCK_MISS_API_KEY", "DUCKMISS_API_KEY",
            "MODELSCOPE_API_KEY",
            "KIMI_API_KEY",
            "DEEPSEEK_API_KEY",
            "DOUBAO_API_KEY",
        )
        model = _first(
            "AEKV_LLM_MODEL",
            "DUCK_MISS_DEFAULT_MODEL", "DUCKMISS_DEFAULT_MODEL",
            "MODELSCOPE_MODEL",
            "KIMI_MODEL",
            "DEEPSEEK_MODEL",
            "DOUBAO_MODEL",
        ) or "auto"

        if base_url:
            self._config.base_url = base_url
        if api_key:
            self._config.api_key = api_key
        if model:
            self._config.default_model = model

        # 解析降级 Provider 列表
        fallbacks_str = os.environ.get("AEKV_LLM_FALLBACKS", "")
        if fallbacks_str:
            try:
                self._config.fallback_providers = json.loads(fallbacks_str)
            except json.JSONDecodeError:
                pass

        self._init_provider_health()

        self.configure_providers_from_env()

        # -- 回填主配置：当 .env 只配置了第三方前缀（如MODELSCOPE_*）时，
        #    configure_providers_from_env() 已将其放入 providers 字典，
        #    但此时 _config.base_url/_api_key 可能仍为空，导致 chat() 走
        #    主配置路径时请求到空地址。 这里从已加载的 providers 中选
        #    第一个可用的回填，确保"有配置即可用"。
        if (not self._config.base_url or not self._config.api_key) and self._config.providers:
            # 回填优先级：用户可能想把哪个当主provider就先配哪个
            pref_order = ["modelscope", "kimi", "claude", "gpt", "deepseek", "doubao", "image_gen"]
            chosen: dict[str, Any] | None = None
            chosen_name = ""
            for name in pref_order:
                if name in self._config.providers:
                    chosen = self._config.providers[name]
                    chosen_name = name
                    break
            if chosen is None:
                # 取字典里第一个
                for name, cfg in self._config.providers.items():
                    chosen = cfg
                    chosen_name = name
                    break
            if chosen is not None:
                if not self._config.base_url and chosen.get("base_url"):
                    self._config.base_url = chosen["base_url"]
                    self._logger.info(f"[LLMGateway] 回填主 base_url 从 provider[{chosen_name}]: {self._config.base_url}")
                if not self._config.api_key and chosen.get("api_key"):
                    self._config.api_key = chosen["api_key"]  # 仅日志不打印密钥
                    self._logger.info(f"[LLMGateway] 回填主 api_key 从 provider[{chosen_name}] (len={len(self._config.api_key)})")
                if (not self._config.default_model or self._config.default_model == "auto") \
                        and chosen.get("models") and chosen["models"].get("default"):
                    self._config.default_model = chosen["models"]["default"]
                    self._logger.info(f"[LLMGateway] 回填主 default_model 从 provider[{chosen_name}]: {self._config.default_model}")

    def configure_providers_from_env(self) -> None:
        """从环境变量加载多Provider配置（并行于 configure_from_env）。

        加载 Claude / GPT / 图像生成 / DeepSeek / 豆包 五个 Provider，
        每个 Provider 包含 base_url、api_key 与多档位模型映射。
        缺失 API Key 的 Provider 自动跳过，不影响其他 Provider。
        """
        providers: dict[str, dict[str, Any]] = {}

        # Claude Provider（VISION/深度推理主力）— 兼容 DUCKMISS_/DUCK_MISS_ 两种前缀
        claude_key = (os.environ.get("DUCKMISS_API_KEY", "")
                       or os.environ.get("DUCK_MISS_API_KEY", "")
                       or os.environ.get("AEKV_LLM_API_KEY", ""))
        if claude_key:
            providers["claude"] = {
                "base_url": (os.environ.get("DUCKMISS_BASE_URL", "")
                              or os.environ.get("DUCK_MISS_BASE_URL", "")
                              or "https://duckmiss.site/v1"),
                "api_key": claude_key,
                "models": {
                    "vision": (os.environ.get("DUCKMISS_VISION_MODEL", "")
                                or os.environ.get("DUCK_MISS_VISION_MODEL", "")
                                or "claude-sonnet-4-6"),
                    "thinking": (os.environ.get("DUCKMISS_THINKING_MODEL", "")
                                  or os.environ.get("DUCK_MISS_THINKING_MODEL", "")
                                  or "claude-opus-4-8"),
                    "fast": (os.environ.get("DUCKMISS_FAST_MODEL", "")
                              or os.environ.get("DUCK_MISS_FAST_MODEL", "")
                              or "claude-sonnet-4-6"),
                    "default": (os.environ.get("DUCKMISS_DEFAULT_MODEL", "")
                                 or os.environ.get("DUCK_MISS_DEFAULT_MODEL", "")
                                 or "claude-sonnet-4-6"),
                },
            }

        # GPT Provider（代码生成/视觉备用）— 支持多密钥故障转移
        gpt_key = os.environ.get("GPT_GATEWAY_API_KEY", "")
        gpt_backup_model = os.environ.get("GPT_BACKUP_MODEL", "gpt-5.6")
        # 收集主密钥 + 备用密钥（GPT_BACKUP_KEY_1/2/...）
        gpt_all_keys = [k for k in [gpt_key] + [
            os.environ.get("GPT_BACKUP_KEY_1", ""),
            os.environ.get("GPT_BACKUP_KEY_2", ""),
            os.environ.get("GPT_BACKUP_KEY_3", ""),
        ] if k]
        if gpt_all_keys:
            providers["gpt"] = {
                "base_url": os.environ.get("GPT_GATEWAY_BASE_URL", "https://duckmiss.site/v1"),
                "api_key": gpt_all_keys[0],          # 主密钥（向后兼容）
                "api_keys": gpt_all_keys,            # 全部密钥（故障转移用）
                "models": {
                    "vision": os.environ.get("GPT_GATEWAY_VISION_MODEL", gpt_backup_model),
                    "code": os.environ.get("GPT_GATEWAY_CODE_MODEL", gpt_backup_model),
                    "reasoning": os.environ.get("GPT_GATEWAY_REASONING_MODEL", gpt_backup_model),
                    "default": gpt_backup_model,
                },
            }

        # 图像生成 Provider
        img_key = os.environ.get("IMAGE_GEN_API_KEY", "")
        if img_key:
            providers["image_gen"] = {
                "base_url": os.environ.get("IMAGE_GEN_BASE_URL", "https://duckmiss.site/v1"),
                "api_key": img_key,
                "models": {"default": os.environ.get("IMAGE_GEN_MODEL", "gpt-image-2")},
            }

        # DeepSeek Provider（官方 API 直连，2026-07-31 V4-Flash 正式版公测上线）
        # 多档位模型配置：
        #   - flash: V4-Flash 正式版（deepseek-v4-flash-0731），日常编码、批量处理
        #   - pro: V4-Pro 预览版（deepseek-v4-pro-260425），复杂推理
        #   - code: 复用 Flash 正式版，代码生成专精（原生支持 Responses API + Codex）
        #   - reasoning: R1 系列，深度推理
        #   - default: 等同 flash，保持向后兼容
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if ds_key:
            # 默认使用 V4-Flash 正式版（2026-07-31 公测上线）
            ds_flash = os.environ.get("DEEPSEEK_FLASH_MODEL", "deepseek-v4-flash")
            ds_pro = os.environ.get("DEEPSEEK_PRO_MODEL", "deepseek-v4-pro")
            ds_code = os.environ.get("DEEPSEEK_CODE_MODEL", ds_flash)
            ds_reasoning = os.environ.get("DEEPSEEK_REASONING_MODEL", "deepseek-r1-250722")
            ds_default = os.environ.get("DEEPSEEK_MODEL", ds_flash)
            providers["deepseek"] = {
                "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                "api_key": ds_key,
                "models": {
                    "default": ds_default,
                    "flash": ds_flash,         # TIER_2: 快速响应、低成本
                    "pro": ds_pro,             # TIER_3: 复杂推理（预览版）
                    "code": ds_code,           # SPECIALIZED: 代码生成（Codex 适配）
                    "reasoning": ds_reasoning, # THINKING: 深度推理
                },
                # 峰谷计价感知（DeepSeek 动态收费）
                "peak_hours": [9, 10, 11, 14, 15, 16, 17],
                "prefer_valley": os.environ.get("DEEPSEEK_PREFER_VALLEY", "true").lower() == "true",
            }

        # 豆包/火山方舟 Provider（文本主力, 2026-08-14 重路由）
        # Key: DOUBAO_API_KEY (ark-* 前缀的火山方舟 API Key)
        # 端点: ark.cn-beijing.volces.com/api/v3 (OpenAI 兼容)
        # 档位映射 (按成本优化, 模型名经 2026-08-14 实测验证可用):
        #   flash   = deepseek-v4-flash-ga (最新 GA 版, 高频任务最省)
        #   default = deepseek-v4-flash (稳定版)
        #   thinking/pro = deepseek-v4-pro (深度推理: 分镜/质量审查)
        #   code    = doubao-seed-2-0-code-preview (代码专用, 实测可用)
        # 注意: 该账号未开通 doubao 视觉/思考/翻译系模型(404), 视觉任务全走 siliconflow
        db_key = os.environ.get("DOUBAO_API_KEY", "") or os.environ.get("ARK_API_KEY", "")
        if db_key:
            providers["doubao"] = {
                "base_url": os.environ.get("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
                "api_key": db_key,
                "models": {
                    "default": os.environ.get("DOUBAO_MODEL", "deepseek-v4-flash-260425"),
                    "flash": os.environ.get("DOUBAO_FLASH_MODEL", "deepseek-v4-flash-ga-260731"),
                    "thinking": os.environ.get("DOUBAO_THINKING_MODEL", "deepseek-v4-pro-260425"),
                    "pro": os.environ.get("DOUBAO_PRO_MODEL", "deepseek-v4-pro-260425"),
                    "code": os.environ.get("DOUBAO_CODE_MODEL", "doubao-seed-2-0-code-preview-260215"),
                },
            }

        # 魔搭 ModelScope Provider（阿里云开源模型社区）
        # 注意: 必须使用 stream=True 模式，非流式返回 choices=null
        ms_key = os.environ.get("MODELSCOPE_API_KEY", "")
        if ms_key:
            providers["modelscope"] = {
                "base_url": os.environ.get("MODELSCOPE_BASE_URL", "https://api-inference.modelscope.cn/v1"),
                "api_key": ms_key,
                "stream_required": True,  # ModelScope 必须流式
                "models": {
                    "default": os.environ.get("MODELSCOPE_MODEL", "Qwen/Qwen3-235B-A22B"),
                    "pro": os.environ.get("MODELSCOPE_PRO_MODEL", "Qwen/Qwen3-235B-A22B"),
                    "flash": os.environ.get("MODELSCOPE_FLASH_MODEL", "Qwen/Qwen3-8B"),
                    "vision": os.environ.get("MODELSCOPE_VISION_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct"),
                    "code": os.environ.get("MODELSCOPE_CODE_MODEL", "Qwen/Qwen3-Coder-30B-A3B-Instruct"),
                },
            }

        # SiliconFlow 硅基流动 Provider（视觉 + 代码主力, 2026-08-14 重路由）
        # 档位映射 (按成本优化):
        #   vision   = Qwen/Qwen3-VL-30B-A3B-Instruct (MoE 3B 激活, 视觉标注最省)
        #   code     = moonshotai/Kimi-K2.7-Code (代码专用模型)
        #   thinking = Pro/deepseek-ai/DeepSeek-V3.2 (深度推理兜底)
        #   default/flash = deepseek-ai/DeepSeek-V4-Flash (快速任务兜底)
        sf_key = os.environ.get("SILICONFLOW_API_KEY", "")
        if sf_key:
            providers["siliconflow"] = {
                "base_url": os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
                "api_key": sf_key,
                "models": {
                    "default": os.environ.get("SILICONFLOW_DEFAULT_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
                    "flash": os.environ.get("SILICONFLOW_FLASH_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
                    # fast 档与 flash 同源（调用方可按任一名称引用快速档）
                    "fast": os.environ.get("SILICONFLOW_FLASH_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
                    "vision": os.environ.get("SILICONFLOW_VISION_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct"),
                    "code": os.environ.get("SILICONFLOW_CODE_MODEL", "moonshotai/Kimi-K2.7-Code"),
                    "thinking": os.environ.get("SILICONFLOW_THINKING_MODEL", "Pro/deepseek-ai/DeepSeek-V3.2"),
                },
            }

        # Kimi K3 Provider（国产开源，支持私有化部署）
        # 用于敏感素材处理，降低合规风险
        kimi_key = os.environ.get("KIMI_API_KEY", "")
        if kimi_key:
            # 优先使用私有化部署端点（如果配置）
            kimi_base_url = os.environ.get("KIMI_LOCAL_BASE_URL", "") or \
                           os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
            
            providers["kimi"] = {
                "base_url": kimi_base_url,
                "api_key": kimi_key,
                "models": {
                    "default": os.environ.get("KIMI_MODEL", "kimi-k3"),
                    "pro": os.environ.get("KIMI_PRO_MODEL", "kimi-k3"),
                    "flash": os.environ.get("KIMI_FLASH_MODEL", "kimi-flash"),
                    "vision": os.environ.get("KIMI_VISION_MODEL", "kimi-vision-pro"),
                    "code": os.environ.get("KIMI_CODE_MODEL", "kimi-code"),
                    "embedding": os.environ.get("KIMI_EMBEDDING_MODEL", "kimi-embedding"),
                },
                # 私有化部署标识（用于合规审计）
                "privatized": os.environ.get("KIMI_PRIVATIZED", "false").lower() == "true",
                "data_isolation": os.environ.get("KIMI_DATA_ISOLATION", "true").lower() == "true",
            }

        # Qwen 官方 Provider（阿里 DashScope OpenAI 兼容端点 = 百炼 Token Plan 订阅的调用端点）
        # Key 读取优先级: QWEN_API_KEY → DASHSCOPE_API_KEY（百炼控制台同一 sk-* key，
        # 已有 DASHSCOPE_API_KEY 时无需重复配置即可激活 Token Plan 订阅）。
        # Qwen3.8-Max：2.4T 总参/95B 激活 MoE，1M 上下文，原生图像/视频理解；
        # Token Plan 个人版/团队版均覆盖（模型名与兼容端点一致）。
        qwen_key = os.environ.get("QWEN_API_KEY", "") or os.environ.get("DASHSCOPE_API_KEY", "")
        if qwen_key:
            providers["qwen"] = {
                "base_url": os.environ.get("QWEN_LOCAL_BASE_URL", "") or
                            os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                "api_key": qwen_key,
                "models": {
                    "default": os.environ.get("QWEN_MODEL", "qwen3.8-max"),
                    "thinking": os.environ.get("QWEN_REASONING_MODEL", "qwen3.8-max"),  # 深度推理档位
                    "vision": os.environ.get("QWEN_VISION_MODEL", "qwen3.8-max"),       # 视觉理解档位（原生多模态）
                    "flash": os.environ.get("QWEN_FLASH_MODEL", "qwen3.8-27b"),          # 轻量本地部署档
                },
                # 私有化部署标识（用于合规审计，权重落地后自部署启用）
                # 解析规则：1/true/yes/on 大小写不敏感 → True；其余非空值 → False；
                # 空串/未设置取默认（privatized=False，data_isolation=True）
                "privatized": _parse_env_flag("QWEN_PRIVATIZED", False),
                "data_isolation": _parse_env_flag("QWEN_DATA_ISOLATION", True),
            }

        # 第二把千问 key（2026-08-15 双额度方案）：主 key 额度耗尽时
        # 多 Provider 兜底循环自动切换，无需二选一。注册为独立 Provider
        # "qwen_ai"，模型档位与主 qwen 保持一致。
        qwen_ai_key = os.environ.get("QWEN_AI_API_KEY", "")
        if qwen_ai_key and qwen_ai_key != qwen_key:
            providers["qwen_ai"] = {
                "base_url": os.environ.get("QWEN_AI_BASE_URL",
                                           "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                "api_key": qwen_ai_key,
                "models": {
                    "default": os.environ.get("QWEN_AI_MODEL",
                                              os.environ.get("QWEN_MODEL", "qwen3.8-max")),
                    "thinking": os.environ.get("QWEN_AI_REASONING_MODEL",
                                               os.environ.get("QWEN_REASONING_MODEL", "qwen3.8-max")),
                    "vision": os.environ.get("QWEN_AI_VISION_MODEL",
                                             os.environ.get("QWEN_VISION_MODEL", "qwen3.8-max")),
                    "flash": os.environ.get("QWEN_AI_FLASH_MODEL",
                                            os.environ.get("QWEN_FLASH_MODEL", "qwen3.8-27b")),
                },
                "privatized": False,
                "data_isolation": True,
            }

        self._config.providers = providers
        # 初始化每个 Provider 的健康状态（重置已存在的 Provider）
        for name in providers:
            if name in self._provider_health:
                # 重置健康状态，允许新配置的 API Key 重试
                self._provider_health[name] = ProviderHealth(name=name)
            else:
                self._provider_health[name] = ProviderHealth(name=name)

        self._logger.info(
            f"已加载 {len(providers)} 个Provider: {list(providers.keys())}"
        )

    def is_available(self) -> bool:
        """检查 LLM 网关是否可用"""
        return bool(self._config.base_url and self._config.api_key)

    # 关键状态自动刷新间隔：超过该时长未检查则触发后台刷新（服务运行期兜底，
    # 显式调用 refresh_key_status() 不受此限制——项目启动钩子每次启动都强制刷新）
    KEY_STATUS_TTL_SEC: float = 12 * 3600

    def ensure_configured(self, force: bool = False) -> None:
        """幂等初始化：加载 .env / .env.doubao 并配置网关。

        首次调用（或 force=True）时：
        1. 加载项目根目录 .env（LLM 配置权威来源之一，如 ModelScope）
        2. 加载 .env.doubao（豆包 ARK + DuckMiss Claude 直连配置权威来源）
        3. 调用 configure_from_env() 读取环境变量、装配多 Provider

        已配置且未强制时直接返回，避免重复加载与覆盖运行期配置。
        同时检查 key 状态文件是否过期，过期则后台自动刷新（不阻塞主流程）。

        Args:
            force: True 时忽略已配置状态，强制重新加载。
        """
        self._maybe_auto_refresh_key_status()
        if not force and self._config.api_key and self._config.providers:
            return
        root = _project_root()
        _load_dotenv_file(root / ".env", override=True)
        _load_dotenv_file(root / ".env.doubao", override=True)
        self.configure_from_env()
        self._apply_invalid_key_status()

    def _maybe_auto_refresh_key_status(self) -> None:
        """key 状态文件过期（或缺失）时后台自动刷新，避免误用失效 key。

        只在状态陈旧时触发（TTL 由 KEY_STATUS_TTL_SEC 控制），且刷新为
        后台线程、不阻塞主流程、不修改配置文件（--no-comment）。
        """
        try:
            status_file = _project_root() / "data" / "llm_key_status.json"
            if status_file.exists():
                try:
                    data = json.loads(status_file.read_text(encoding="utf-8"))
                    ts = max(
                        (v.get("checked_at", 0) for v in data.values()
                         if isinstance(v, dict)),
                        default=0,
                    )
                    if (time.time() - ts) <= self.KEY_STATUS_TTL_SEC:
                        return
                except Exception:
                    pass  # 状态文件损坏则视为过期，触发刷新
            self.refresh_key_status(blocking=False)
        except Exception as e:
            self._logger.debug(f"[LLMGateway] key 状态自动刷新检查失败: {e}")

    def refresh_key_status(self, blocking: bool = False, timeout: int = 15) -> None:
        """后台刷新 LLM key 状态（跑 scripts/check_llm_keys.py --no-comment）。

        刷新完成后重新应用失效 Provider 熔断。后台线程 daemon 化：
        - 不阻塞调用方（blocking=False，项目启动钩子默认使用）
        - 不修改配置文件（--no-comment 只更新 data/llm_key_status.json）
        - 已在刷新中则直接返回（互斥）

        Args:
            blocking: True 时同步等待刷新完成（供测试/脚本使用）
            timeout: 单 key 探测超时秒数（默认 15，覆盖 Claude 慢响应）
        """
        if getattr(self, "_key_refresh_running", False):
            return
        self._key_refresh_running = True

        def _refresh() -> None:
            try:
                import subprocess
                import sys
                script = _project_root() / "scripts" / "check_llm_keys.py"
                # 不 capture：检测脚本的逐 key 结果表实时透传到主进程控制台，
                # 便于启动时直接观察每个 API Key 的验证状态
                subprocess.run(
                    [sys.executable, str(script), "--no-comment", "--timeout", str(timeout)],
                    cwd=str(_project_root()),
                    timeout=max(180, timeout * 10),
                )
                self._apply_invalid_key_status()
                self._logger.info(
                    "[LLMGateway] LLM key 状态已后台刷新（check_llm_keys.py --no-comment）"
                )
            except Exception as e:
                self._logger.warning(f"[LLMGateway] key 状态后台刷新失败: {e}")
            finally:
                self._key_refresh_running = False

        t = threading.Thread(target=_refresh, name="llm-key-status-refresh", daemon=True)
        t.start()
        if blocking:
            t.join(timeout=max(200, timeout * 12))

    def _apply_invalid_key_status(self) -> None:
        """读取 data/llm_key_status.json（由 scripts/check_llm_keys.py 生成），
        对标记为 invalid 且已装配的 Provider 设置熔断，避免每次调用先打一发无效请求。

        - 熔断状态下 chat_with_provider 会直接返回失败（不发起网络请求），
          由 chat_with_routing 的备选 Provider 循环兜底。
        - 用户更新 key 后重跑 scripts/check_llm_keys.py 即可解除标记。
        """
        try:
            status_file = _project_root() / "data" / "llm_key_status.json"
            if not status_file.exists():
                return
            data = json.loads(status_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            invalid_providers = {
                item.get("provider")
                for item in data.values()
                if isinstance(item, dict) and item.get("status") == "invalid" and item.get("provider")
            }
            for name in invalid_providers:
                if name in self._provider_health and name in self._config.providers:
                    health = self._provider_health[name]
                    health.status = ProviderStatus.UNAVAILABLE
                    health.last_error = "[INVALID_KEY] 已由 scripts/check_llm_keys.py 标记为无效，跳过直连"
                    self._logger.warning(
                        f"[LLMGateway] Provider {name} 的 key 已被检测为无效，"
                        "跳过直连（由降级链兜底）。更新 key 后重跑 scripts/check_llm_keys.py"
                    )
        except Exception as e:
            self._logger.debug(f"[LLMGateway] 读取 key 状态失败（忽略）: {e}")

    # -------------------------------------------------------------------------
    # P3: observability 上报（轻量集成，失败时静默不影响主流程）
    # -------------------------------------------------------------------------

    def _obs_report_success(self, response: "LLMResponse", task_type: str = "") -> None:
        """上报成功调用指标：latency / tokens / cost / provider / task_type"""
        if self._obs is None:
            return
        try:
            labels = {
                "provider": response.provider or "unknown",
                "task_type": task_type or "general",
                "tier": response.tier or "unknown",
            }
            self._obs.record_histogram("llm_latency_ms", float(response.latency_ms), **labels)
            self._obs.record_histogram(
                "llm_tokens_input", float(response.tokens_input), **labels
            )
            self._obs.record_histogram(
                "llm_tokens_output", float(response.tokens_output), **labels
            )
            self._obs.record_histogram("llm_cost_usd", float(response.cost_usd), **labels)
            if response.video_seconds > 0:
                self._obs.record_histogram(
                    "llm_video_seconds", float(response.video_seconds), **labels
                )
            if response.image_count > 0:
                self._obs.record_histogram(
                    "llm_image_count", float(response.image_count), **labels
                )
            self._obs.increment_counter(
                "llm_calls_total", 1.0, status="success", **labels
            )
        except Exception:
            # observability 上报失败不能影响主流程
            pass

    def _obs_report_failure(
        self, provider: str, error_type: str, task_type: str = ""
    ) -> None:
        """上报 Provider 失败 counter（含 provider / error_type / task_type）"""
        if self._obs is None:
            return
        try:
            self._obs.increment_counter(
                "llm_failures_total",
                1.0,
                provider=provider or "unknown",
                error_type=error_type or "unknown",
                task_type=task_type or "general",
            )
        except Exception:
            pass

    def _obs_report_fallback(
        self,
        from_provider: str,
        to_provider: str,
        task_type: str = "",
        success: bool = True,
    ) -> None:
        """上报降级事件 counter（含 from/to provider / task_type）"""
        if self._obs is None:
            return
        try:
            self._obs.increment_counter(
                "llm_fallback_total",
                1.0,
                from_provider=from_provider or "unknown",
                to_provider=to_provider or "unknown",
                task_type=task_type or "general",
                status="success" if success else "failure",
            )
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 知识库上下文注入
    # -------------------------------------------------------------------------

    def _inject_kb_context(self, system_prompt: str, query: str, task_type: str = "") -> str:
        """将知识库相关内容注入到 system_prompt

        当任务类型与效果/转场/调色相关时，自动检索知识库并注入上下文。

        Args:
            system_prompt: 原始系统提示词
            query: 用户查询/意图描述
            task_type: 任务类型

        Returns:
            增强后的 system_prompt
        """
        # 只在相关任务类型时注入
        kb_relevant_types = {
            "effect_planning", "intent_classification",
            "scene_description", "quality_review", "general",
        }
        if task_type and task_type not in kb_relevant_types:
            return system_prompt

        try:
            try:
                from knowledge.kb_loader import KBLoader
            except ImportError:
                from kb_loader import KBLoader
            loader = KBLoader.get_instance()
            kb_context = loader.get_context_for_llm(task_type, query)
            if kb_context:
                if system_prompt:
                    return f"{system_prompt}\n\n{kb_context}"
                return kb_context
        except Exception as e:
            self._logger.debug(f"知识库上下文注入失败（不影响主流程）: {e}")

        return system_prompt

    # -------------------------------------------------------------------------
    # HTTP 客户端
    # -------------------------------------------------------------------------

    async def _get_http_client(self):
        """获取 HTTP 客户端（懒加载）

        CRITICAL FIX(A7): 检测已有 session 绑定的事件循环是否仍为当前运行循环。
        在模块级单例 + asyncio.run 模式下，第二次调用会复用绑定到已关闭 loop
        的旧 session，导致 RuntimeError。检测到不匹配时关闭旧 session 并重建。
        使用 asyncio.Lock 保护懒加载，避免并发首次调用创建多个 session。
        """
        loop = asyncio.get_running_loop()
        if self._http_client is not None:
            try:
                # aiohttp.ClientSession 内部以 _loop 持有所属事件循环；
                # 仅当 _loop 是真实事件循环时才检测（测试注入的 mock 客户端
                # 自动生成的 _loop 属性不是 AbstractEventLoop，跳过检测避免误关）
                bound_loop = getattr(self._http_client, "_loop", None)
                if (
                    isinstance(bound_loop, asyncio.AbstractEventLoop)
                    and bound_loop is not loop
                ):
                    self._logger.warning(
                        "检测到 HTTP 客户端绑定的事件循环已变更，关闭旧 session 并重建"
                    )
                    await self._http_client.close()
                    self._http_client = None
            except AttributeError:
                # 某些版本可能没有 _loop 属性，忽略检测直接复用
                pass

        if self._http_client is None:
            async with self._http_client_lock:
                # double-checked locking：拿到锁后再次确认仍未初始化
                if self._http_client is not None:
                    return self._http_client
                try:
                    import aiohttp
                    # CRITICAL FIX: 限制最大连接数，防止资源泄漏
                    connector = aiohttp.TCPConnector(
                        limit=20,              # 总连接数上限
                        limit_per_host=10,     # 每个 host 的连接数上限
                        ttl_dns_cache=300,     # DNS 缓存 5 分钟
                    )
                    # 从环境变量读取代理配置
                    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("https_proxy") or os.environ.get("http_proxy")
                    session_kwargs = {
                        "connector": connector,
                        "timeout": aiohttp.ClientTimeout(
                            total=self._config.timeout_seconds
                        ),
                        "trust_env": True,  # 自动读取环境变量中的代理设置
                    }
                    # aiohttp >= 3.9 支持session级proxy
                    if proxy_url:
                        try:
                            session_kwargs["proxy"] = proxy_url
                            self._logger.info(f"LLM Gateway: 使用代理 {proxy_url}")
                        except TypeError:
                            pass  # 旧版aiohttp不支持proxy参数，依赖trust_env
                    self._http_client = aiohttp.ClientSession(**session_kwargs)
                except ImportError:
                    self._logger.warning("aiohttp 未安装，LLM 网关不可用")
                    return None
        return self._http_client

    async def _close_http_client(self) -> None:
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.close()
            self._http_client = None

    # -------------------------------------------------------------------------
    # 核心调用
    def _is_local_openvino(self, base_url: str) -> bool:
        return str(base_url).startswith("local://openvino/")

    async def _call_local_openvino(
        self,
        base_url: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        provider_friendly_name: str = "",
        **_: Any,
    ):
        import time as _t
        _start = _t.perf_counter()

        lookup_name = provider_friendly_name or self._extract_provider_name(base_url)
        if lookup_name not in self._provider_health:
            self._provider_health[lookup_name] = ProviderHealth(name=lookup_name)
        _health = self._provider_health[lookup_name]
        _health.total_requests += 1
        self._stats["total_requests"] += 1

        def _fail(msg):
            _health.consecutive_failures += 1
            _health.total_failures += 1
            _health.last_error = msg
            _health.last_failure_time = _t.time()
            if _health.consecutive_failures >= 3:
                _health.status = ProviderStatus.UNAVAILABLE
            self._stats["total_failures"] += 1
            # P3: observability 上报失败 counter
            self._obs_report_failure(lookup_name, "local_openvino_error")
            return LLMResponse(
                success=False,
                provider=lookup_name,
                error=msg,
            )

        try:
            from core.local_model_adapter import (
                InferenceBackend,
                LocalModelAdapter,
                LocalModelConfig,
                LocalModelType,
            )

            model_name = model or ""
            if not model_name:
                model_name = base_url.split("/")[-1]

            type_map = {
                "qwen2-0.5b": LocalModelType.QWEN2_05B,
                "qwen2-1.5b": LocalModelType.QWEN2_15B,
                "qwen2-7b": LocalModelType.QWEN2_7B,
            }
            model_type = None
            for k, v in type_map.items():
                if k in model_name.lower():
                    model_type = v
                    break
            if model_type is None:
                model_type = LocalModelType.QWEN2_15B

            path_map = {
                LocalModelType.QWEN2_05B: "Qwen/Qwen2-0.5B-Instruct",
                LocalModelType.QWEN2_15B: "Qwen/Qwen2-1.5B-Instruct",
                LocalModelType.QWEN2_7B: "Qwen/Qwen2-7B-Instruct",
            }
            model_path = path_map[model_type]

            cache_key = f"openvino::{model_type.value}"
            adapter = self._local_adapters.get(cache_key)
            if adapter is None:
                adapter_cfg = LocalModelConfig(
                    model_type=model_type,
                    model_path=model_path,
                    device="gpu",
                    backend=InferenceBackend.OPENVINO,
                    ov_compile_precision="int8",
                    max_length=2048,
                )
                adapter = LocalModelAdapter(adapter_cfg)
                self._local_adapters[cache_key] = adapter

            prompt_parts = []
            for m in messages:
                role = m.get("role", "user")
                c = m.get("content", "")
                prompt_parts.append(f"<|im_start|>{role}\n{c}<|im_end|>\n")
            prompt_parts.append("<|im_start|>assistant\n")
            prompt = "".join(prompt_parts)

            ok, err = await adapter.initialize()
            if not ok:
                return _fail(f"Local OpenVINO init failed: {err}")
            resp = await adapter.generate(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temperature,
            )
            if not resp.success:
                return _fail(f"Local OpenVINO generate failed: {resp.error}")

            latency_ms = (_t.perf_counter() - _start) * 1000
            _health.consecutive_failures = 0
            _health.last_success_time = _t.time()
            if _health.avg_latency_ms == 0.0:
                _health.avg_latency_ms = latency_ms
            else:
                _health.avg_latency_ms = 0.8 * _health.avg_latency_ms + 0.2 * latency_ms
            _health.status = ProviderStatus.HEALTHY
            self._stats["total_successes"] += 1
            self._stats["total_tokens_output"] += resp.tokens_used
            self._stats["total_latency_ms"] += latency_ms

            # 组装和云端一致的响应 choices 结构
            _resp = LLMResponse(
                success=True,
                content=resp.content,
                provider=lookup_name,
                model=model_name,
                latency_ms=latency_ms,
                tokens_input=0,
                tokens_output=resp.tokens_used,
                tokens_total=resp.tokens_used,
            )
            # P3: observability 上报成功指标
            self._obs_report_success(_resp)
            return _resp

        except Exception as e:
            self._logger.exception(f"_call_local_openvino error: {e}")
            return _fail(str(e))


    # -------------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        use_compression: bool | None = None,
        images: list[str] | None = None,
    ) -> LLMResponse:
        """
        发送聊天请求

        Args:
            message: 用户消息
            system_prompt: 系统提示词
            model: 模型名称（空则用默认）
            temperature: 温度参数
            max_tokens: 最大输出 token
            use_compression: 是否使用压缩（None 则用配置默认值）
            images: base64 编码的图片列表，用于多模态（VISION）调用。
                    传入后将构建 OpenAI 兼容的多模态 content 结构。
        """
        if not self.is_available():
            return LLMResponse(
                success=False,
                error="LLM 网关未配置（缺少 base_url 或 api_key）"
            )

        has_images = bool(images)

        # Token 压缩（多模态时保留用户消息原文，避免破坏 content 结构）
        should_compress = use_compression if use_compression is not None else self._config.enable_compression
        if should_compress:
            system_prompt = self._compressor.compress_system(system_prompt)
            if not has_images:
                message = self._compressor.compress_prompt(message)
                message += self._compressor.get_compression_suffix()

        model = model or self._config.default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if has_images:
            # 构建 OpenAI 兼容的多模态消息体
            content_parts: list[dict[str, Any]] = [{"type": "text", "text": message}]
            for img_b64 in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                })
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": message})

        # 尝试主 Provider
        response = await self._call_provider(
            self._config.base_url,
            self._config.api_key,
            model,
            messages,
            temperature,
            max_tokens,
            provider_friendly_name="primary",
        )

        # 降级处理
        if not response.success and self._config.enable_fallback:
            # 健康感知排序：健康 Provider 优先，熔断冷却中的剔除，同分保持配置顺序
            ordered_fallbacks = self._order_fallback_candidates(
                self._config.fallback_providers
            )
            for fb in ordered_fallbacks:
                fb_url = fb.get("base_url", "")
                fb_key = fb.get("api_key", "")
                if not fb_url or not fb_key:
                    continue

                # 使用 fallback 配置中的 default_model，避免传递不支持的 "auto"
                fb_model = fb.get("default_model", "") or model
                if fb_model == "auto" or not fb_model:
                    fb_model = model

                # 用 hostname 作为健康状态 key，与 _order_fallback_candidates 评分对齐
                fb_name = self._extract_provider_name(fb_url)
                safe_fb_url = _sanitize_log_text(fb_url)
                self._logger.warning(f"主 Provider 失败，尝试降级[{fb_name}]: {safe_fb_url}")
                response = await self._call_provider(
                    fb_url, fb_key, fb_model,
                    messages, temperature, max_tokens,
                    provider_friendly_name=fb_name,
                )
                if response.success:
                    break

        # 解压响应
        if response.success and should_compress:
            response.content = self._compressor.decompress_response(response.content)

        return response

    async def chat_with_cascade(
        self,
        message: str,
        task_type: TaskType = TaskType.GENERAL,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: list[str] | None = None,
        start_tier: ModelTier | None = None,
        min_confidence: float | None = None,
        max_upgrades: int | None = None,
    ) -> LLMResponse:
        """级联路由聊天 - 从低档位开始尝试，置信度不够自动升级

        流程：
        1. 确定起始档位（默认从推荐档位的低一档，或者从TIER_1开始）
        2. 调用当前档位模型
        3. 提取置信度
        4. 判断是否需要升级
        5. 需要升级则切换到下一档位，重复2-4
        6. 返回最终结果（包含级联路径、节省成本等信息）

        Args:
            message: 用户消息
            task_type: 任务类型
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token
            images: base64 图片列表
            start_tier: 起始档位（默认从 TIER_1 开始）
            min_confidence: 最小置信度阈值（默认使用配置中的值）
            max_upgrades: 最大升级次数（默认使用配置中的值）

        Returns:
            LLMResponse: 最终响应，包含级联路径、置信度、节省成本等信息
        """
        # 级联统计
        self._cascade_stats["cascade_attempts"] += 1

        # 档位顺序
        tier_order = [
            ModelTier.TIER_1_LOCAL_SPECIALIZED,
            ModelTier.TIER_2_MIDTIER_GENERAL,
            ModelTier.TIER_3_FLAGSHIP_REASONING,
        ]

        # 确定起始档位
        if start_tier is None:
            # 如果 prefer_small_model=True，从最低档开始
            if self._config.prefer_small_model:
                current_tier = ModelTier.TIER_1_LOCAL_SPECIALIZED
            else:
                # 从推荐档位开始
                current_tier = TASK_TIER_MAP.get(task_type, ModelTier.TIER_2_MIDTIER_GENERAL)
                # 确保从最低可用档位开始（如果启用级联且偏好小模型）
                if self._config.enable_cascade:
                    current_tier = ModelTier.TIER_1_LOCAL_SPECIALIZED
        else:
            current_tier = start_tier

        # 跳过指定的档位
        skip_tiers = set(self._config.cascade_enable_skip_tiers)
        available_tiers = [t for t in tier_order if t.value not in skip_tiers]

        if not available_tiers:
            return LLMResponse(
                success=False,
                error="没有可用的模型档位（所有档位都被跳过）"
            )

        # 确定当前档位在可用列表中的位置
        if current_tier in available_tiers:
            current_index = available_tiers.index(current_tier)
        else:
            current_index = 0
            current_tier = available_tiers[0]

        # 设置阈值和最大升级次数
        if min_confidence is not None:
            original_threshold = self._config.cascade_confidence_threshold
            self._config.cascade_confidence_threshold = min_confidence
        else:
            original_threshold = None

        if max_upgrades is not None:
            original_max_upgrades = self._config.cascade_max_upgrades
            self._config.cascade_max_upgrades = max_upgrades
        else:
            original_max_upgrades = None

        cascade_path: list[str] = []
        total_cost = 0.0
        upgrade_count = 0
        final_response: LLMResponse | None = None
        total_latency = 0.0

        try:
            while current_index < len(available_tiers):
                tier = available_tiers[current_index]
                cascade_path.append(tier.value)

                self._logger.info(
                    f"级联路由: 尝试档位 {tier.value} "
                    f"(第{len(cascade_path)}次尝试, 升级次数={upgrade_count})"
                )

                # 调用当前档位的模型
                response = await self._call_tier_model(
                    message=message,
                    tier=tier,
                    task_type=task_type,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    images=images,
                )

                total_latency += response.latency_ms
                total_cost += response.cost_usd

                # 提取置信度
                if response.success and response.content:
                    confidence, confidence_reason = self._extract_confidence(
                        response.content, tier, task_type
                    )
                    response.confidence = confidence
                    response.confidence_level = self._get_confidence_level(confidence)
                    response.confidence_reason = confidence_reason

                # 更新级联路径和升级计数
                response.cascade_path = cascade_path.copy()
                response.upgrade_count = upgrade_count
                response.tier_upgraded = upgrade_count > 0

                final_response = response

                # 判断是否需要升级
                should_upgrade, upgrade_reason = self._should_upgrade(
                    response, tier, task_type, upgrade_count
                )

                self._logger.info(
                    f"档位 {tier.value} 结果: "
                    f"success={response.success}, "
                    f"confidence={response.confidence:.2f}, "
                    f"升级判断: {upgrade_reason}"
                )

                if not should_upgrade:
                    break

                # 升级到下一档位
                upgrade_count += 1
                self._cascade_stats["cascade_upgrades"] += 1
                current_index += 1

            # 计算节省的成本
            if final_response:
                # 基于最终响应的 token 数估算旗舰模型成本
                flagship_tier = ModelTier.TIER_3_FLAGSHIP_REASONING
                flagship_cost = self._calculate_cost(
                    final_response.tokens_input,
                    final_response.tokens_output,
                    flagship_tier
                )
                saved_cost = max(0.0, flagship_cost - total_cost)
                final_response.saved_cost_usd = round(saved_cost, 6)
                final_response.cost_usd = round(total_cost, 6)
                final_response.latency_ms = total_latency
                self._cascade_stats["cascade_savings_usd"] += saved_cost

                # 更新平均路径长度
                self._cascade_stats["cascade_total_path_length"] += len(cascade_path)
                avg_length = (
                    self._cascade_stats["cascade_total_path_length"] /
                    self._cascade_stats["cascade_attempts"]
                )
                self._cascade_stats["cascade_avg_path_length"] = round(avg_length, 2)

            return final_response or LLMResponse(
                success=False,
                error="级联路由结束，无有效响应",
                cascade_path=cascade_path,
                upgrade_count=upgrade_count,
            )

        finally:
            # 恢复原始配置
            if original_threshold is not None:
                self._config.cascade_confidence_threshold = original_threshold
            if original_max_upgrades is not None:
                self._config.cascade_max_upgrades = original_max_upgrades

    async def _call_tier_model(
        self,
        message: str,
        tier: ModelTier,
        task_type: TaskType,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: list[str] | None = None,
    ) -> LLMResponse:
        """调用指定档位的模型

        Args:
            message: 用户消息
            tier: 目标档位
            task_type: 任务类型
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token
            images: base64 图片列表

        Returns:
            LLMResponse: 模型响应
        """
        # TIER_1: 优先尝试本地模型
        if tier == ModelTier.TIER_1_LOCAL_SPECIALIZED:
            response = await self._try_nvidia_local(
                message, task_type, system_prompt, temperature, max_tokens, images
            )
            if response.success:
                return response

        # 多Provider模式：根据档位选择对应的模型类型
        if self._config.providers:
            if tier == ModelTier.TIER_2_MIDTIER_GENERAL:
                # 中端模型用 fast 类型
                provider, _ = TASK_PROVIDER_MAP.get(task_type, ("claude", "fast"))
                model_type = "fast"
                if images:
                    p_cfg = self._config.providers.get(provider, {})
                    if "vision" in p_cfg.get("models", {}):
                        model_type = "vision"
                try:
                    response = await self.chat_with_provider(
                        prompt=message,
                        provider=provider,
                        model_type=model_type,
                        system_prompt=system_prompt,
                        images=images,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if response.success:
                        actual_tier = self._get_tier_from_model_type(model_type, tier)
                        response.tier = actual_tier.value
                        response.cost_usd = self._calculate_cost(
                            response.tokens_input, response.tokens_output, actual_tier
                        )
                        self._update_tier_stats(actual_tier, response)
                        return response
                except Exception as e:
                    self._logger.warning(f"TIER_2 多Provider调用失败: {e}")

            elif tier == ModelTier.TIER_3_FLAGSHIP_REASONING:
                # 旗舰模型用 thinking 类型
                provider, _ = TASK_PROVIDER_MAP.get(task_type, ("claude", "thinking"))
                model_type = "thinking"
                if images:
                    p_cfg = self._config.providers.get(provider, {})
                    if "vision" in p_cfg.get("models", {}):
                        model_type = "vision"
                try:
                    response = await self.chat_with_provider(
                        prompt=message,
                        provider=provider,
                        model_type=model_type,
                        system_prompt=system_prompt,
                        images=images,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if response.success:
                        actual_tier = self._get_tier_from_model_type(model_type, tier)
                        response.tier = actual_tier.value
                        response.cost_usd = self._calculate_cost(
                            response.tokens_input, response.tokens_output, actual_tier
                        )
                        self._update_tier_stats(actual_tier, response)
                        return response
                except Exception as e:
                    self._logger.warning(f"TIER_3 多Provider调用失败: {e}")

        # 单Provider模式：降级到通用调用
        model = self._config.model_routing.get(task_type, self._config.default_model)
        response = await self.chat(
            message=message,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
        )

        # 记录档位信息
        if self._config.enable_tiered_routing and response.success:
            actual_tier = self._infer_tier_from_model(model, tier)
            response.tier = actual_tier.value
            response.cost_usd = self._calculate_cost(
                response.tokens_input, response.tokens_output, actual_tier
            )
            self._update_tier_stats(actual_tier, response)

        return response

    async def chat_with_routing(
        self,
        message: str,
        task_type: TaskType = TaskType.GENERAL,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: list[str] | None = None,
        force_temperature: float | None = None,
        source_video: str = "",
    ) -> LLMResponse:
        """
        根据任务类型自动路由到最优模型的聊天请求

        Args:
            message: 用户消息
            task_type: 任务类型（决定模型选择）
            system_prompt: 系统提示词
            temperature: 默认温度
            max_tokens: 最大输出 token
            images: base64 图片列表，用于多模态调用（自动路由到 VISION 模型）
            force_temperature: 显式强制温度（Phase A 深度推理使用）。非 None 时
                优先于任务类型分支内的强制温度（如 QUALITY_REVIEW 的 0.2），
                允许调用方保留发散探索（如 0.7）；为 None 时行为与旧版完全一致。
            source_video: 视频编辑类任务（VIDEO_EDITING 等）的源视频路径或 URL，
                为空时视频编辑短路路径会回退到常规 chat 路径。

        路由策略（优先级从高到低）：
            1. NVIDIA 本地模型（GB300 Blackwell Ultra）→ 最低延迟，数据不出企业
            2. 多Provider模式：按 ``TASK_PROVIDER_MAP`` 选择 Provider 与模型档位
            3. 单 Provider 模式：使用 ``model_routing`` 表选模型

        分层路由逻辑（Phase 1 基础版）：
            - 当 ``enable_tiered_routing=True`` 时启用分层路由追踪
            - 根据 ``TASK_TIER_MAP`` 确定任务推荐档位
            - 记录实际使用的档位和调用成本
            - 为 Phase 2 置信度级联和成本优化打下基础

        级联路由逻辑（Phase 2 增强版）：
            - 当 ``enable_cascade=True`` 且 ``prefer_small_model=True`` 时启用级联路由
            - 从最低档位开始尝试，置信度不足自动升级到更高档位
            - 返回完整的级联路径、置信度评估和成本节省信息
        """
        # P0-4: 视频生成/编辑类任务不进入 chat token 路径，直接短路到 generate_video / edit_video
        try:
            if task_type == TaskType.VIDEO_GENERATION:
                kwargs_extra: dict[str, Any] = {}
                if images is not None:
                    kwargs_extra["reference_images"] = images
                result = await self.generate_video(
                    message,
                    prompt_extra=system_prompt,
                    **kwargs_extra,
                )
                # 包装成 LLMResponse：success 直接看 result.success，文本内容让下游自己看 output_path
                return LLMResponse(
                    success=bool(result.get("success")),
                    content=result.get("output_path") or result.get("error") or "",
                    model="minimax-h3",
                    provider="minimax_h3",
                    cost_usd=result.get("cost_usd") or 0.0,
                    error=result.get("error") or "",
                    raw=result,
                )
            if task_type == TaskType.IMAGE_GENERATION:
                # 网关当前无独立图像生成能力，明确提示避免误路由到文生视频
                return LLMResponse(
                    success=False,
                    error="图像生成（IMAGE_GENERATION）未由 LLM 网关支持，请使用专用图像生成服务",
                    model="",
                    provider="",
                )
            if task_type in (TaskType.VIDEO_EDITING, TaskType.SUBTITLE_MODIFICATION,
                             TaskType.STYLE_TRANSFER, TaskType.MOTION_TRANSFER,
                             TaskType.OBJECT_REPLACEMENT, TaskType.SCENE_ALTERATION,
                             TaskType.RATE_ADJUSTMENT, TaskType.INPAINTING):
                if not source_video:
                    raise ValueError("edit_video 需要 source_video，回退到常规 chat 路径")
                result = await self.edit_video(
                    operation=task_type.name.lower(),
                    source_video=source_video,
                    instruction=message,
                    reference_image=images[0] if images else "",
                )
                return LLMResponse(
                    success=bool(result.get("success")),
                    content=result.get("output_path") or result.get("error") or "",
                    model="minimax-h3",
                    provider="minimax_h3",
                    cost_usd=result.get("cost_usd") or 0.0,
                    error=result.get("error") or "",
                    raw=result,
                )
        except Exception as _e:
            self._logger.warning(f"VIDEO_* 任务短路路由异常，回退到常规 chat 路径: {_e}")

        # 级联路由：当启用级联且偏好小模型时，使用级联路由
        if self._config.enable_cascade and self._config.prefer_small_model:
            return await self.chat_with_cascade(
                message=message,
                task_type=task_type,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                images=images,
            )

        # 确定任务推荐档位
        recommended_tier = TASK_TIER_MAP.get(task_type, ModelTier.TIER_2_MIDTIER_GENERAL)

        # 优先尝试 NVIDIA 本地模型（GB300 Blackwell Ultra）— TIER_1
        nvidia_response = await self._try_nvidia_local(message, task_type, system_prompt, 
                                                       temperature, max_tokens, images)
        if nvidia_response is not None and nvidia_response.success:
            self._logger.info(f"NVIDIA 本地模型调用成功 (task_type={task_type}, latency={nvidia_response.latency_ms:.0f}ms)")
            return nvidia_response

        # 任务类型→温度调整（多Provider与单Provider路径共用）
        # force_temperature 显式传入时优先于分支强制温度（M2：Phase A 回答轮 0.7 不被覆盖）
        if force_temperature is not None:
            temperature = force_temperature
        elif task_type == TaskType.INTENT_CLASSIFICATION:
            temperature = 0.1
        elif task_type == TaskType.EFFECT_PLANNING:
            temperature = 0.5
        elif task_type == TaskType.QUALITY_REVIEW:
            temperature = 0.2
        elif images is not None and task_type == TaskType.SCENE_DESCRIPTION:
            # 视觉理解任务用低温度保证输出稳定
            temperature = min(temperature, 0.3)

        # 知识库上下文自动注入（不影响非相关任务）
        task_type_str = task_type.value if hasattr(task_type, 'value') else str(task_type)
        system_prompt = self._inject_kb_context(system_prompt, message, task_type_str)

        # 多Provider路由：优先按 TASK_PROVIDER_MAP 调用
        if self._config.providers:
            provider, model_type = TASK_PROVIDER_MAP.get(
                task_type, ("claude", "default")
            )
            # Qwen 优先上位（AEKV_QWEN_PRIORITY）：深度推理/视觉理解切换 qwen 主选
            if (
                task_type in QWEN_PRIORITY_TASKS
                and "qwen" in self._config.providers
                and os.environ.get("AEKV_QWEN_PRIORITY", "false").lower() == "true"
            ):
                provider, model_type = QWEN_PRIORITY_TASKS[task_type]

            # 百炼 Token Plan 全量主选（AEKV_QWEN_PRIMARY）：所有 claude/deepseek
            # 文本任务切 qwen（vision→vision 档, thinking→thinking 档, 其余→default）。
            # 订阅制额度优先使用; qwen Provider 未注册(无 key)时自动不生效。
            if (
                "qwen" in self._config.providers
                and os.environ.get("AEKV_QWEN_PRIMARY", "false").lower() == "true"
                and provider in ("claude", "deepseek")
            ):
                _tier_map = {"vision": "vision", "thinking": "thinking"}
                provider, model_type = "qwen", _tier_map.get(model_type, "default")

            # Step 1b: Provider 兜底链 — TASK_PROVIDER_MAP 指向的 Provider 未加载时：
            #   a) 已加载 Provider 中含目标 model_type 档位的第一个
            #   b) 否则含 "default" 档位的第一个；c) 否则字典第一个。
            # 只替换 provider，不替换 model_type（档位回退由下游 _tier_fallback_sequence 完成）
            if provider not in self._config.providers:
                fallback_provider: str | None = None
                for p_name, p_conf in self._config.providers.items():
                    if model_type in p_conf.get("models", {}):
                        fallback_provider = p_name
                        break
                if fallback_provider is None:
                    for p_name, p_conf in self._config.providers.items():
                        if "default" in p_conf.get("models", {}):
                            fallback_provider = p_name
                            break
                if fallback_provider is None:
                    fallback_provider = next(iter(self._config.providers))
                self._logger.warning(
                    f"Provider {provider} 未加载，兜底链回退到 {fallback_provider}"
                    f"（model_type={model_type} 保持不变）"
                )
                provider = fallback_provider

            # 传入图片时强制走 vision 档位
            if images and model_type != "vision":
                # 仅当该 Provider 配置了 vision 档位才切换
                p_cfg = self._config.providers.get(provider, {})
                if "vision" in p_cfg.get("models", {}):
                    model_type = "vision"

            try:
                response = await self.chat_with_provider(
                    prompt=message,
                    provider=provider,
                    model_type=model_type,
                    system_prompt=system_prompt,
                    images=images,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if response.success:
                    # 确定实际档位并计算成本
                    actual_tier = self._get_tier_from_model_type(model_type, recommended_tier)
                    response.tier = actual_tier.value
                    response.cost_usd = self._calculate_cost(
                        response.tokens_input, response.tokens_output, actual_tier
                    )
                    self._update_tier_stats(actual_tier, response)
                    return response
                # 主 Provider 失败 → 尝试其他已配置 Provider（如 ModelScope）
                self._logger.warning(
                    f"多Provider路由失败(provider={provider}, "
                    f"model_type={model_type})，尝试备选 Provider: "
                    f"{_sanitize_log_text(response.error)}"
                )
            except Exception as e:
                self._logger.warning(
                    f"多Provider路由异常，尝试备选 Provider: {e}"
                )

            # 备选 Provider 循环：遍历所有已配置 Provider（排除已失败的主 Provider）
            # 同族 Provider（如 qwen → qwen_ai 双额度）排第一顺位，用尽同平台免费额度再外溢
            fallback_items = list(self._config.providers.items())
            fallback_items.sort(
                key=lambda kv: (0 if kv[0].startswith(f"{provider}_") else 1,
                                self._config.providers and list(self._config.providers).index(kv[0])))
            for fallback_name, fallback_cfg in fallback_items:
                if fallback_name == provider:
                    continue
                try:
                    fb_model_type = model_type
                    fb_models = fallback_cfg.get("models", {})
                    if fb_model_type not in fb_models and "default" in fb_models:
                        fb_model_type = "default"
                    fb_response = await self.chat_with_provider(
                        prompt=message,
                        provider=fallback_name,
                        model_type=fb_model_type,
                        system_prompt=system_prompt,
                        images=images,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if fb_response.success:
                        self._logger.info(
                            f"备选 Provider 成功: {fallback_name} "
                            f"(task_type={task_type}, latency={fb_response.latency_ms:.0f}ms)"
                        )
                        actual_tier = self._get_tier_from_model_type(fb_model_type, recommended_tier)
                        fb_response.tier = actual_tier.value
                        fb_response.cost_usd = self._calculate_cost(
                            fb_response.tokens_input, fb_response.tokens_output, actual_tier
                        )
                        self._update_tier_stats(actual_tier, fb_response)
                        return fb_response
                except Exception as e:
                    self._logger.debug(f"备选 Provider {fallback_name} 失败: {e}")
                    continue

        # 原有单 Provider 逻辑（向后兼容）
        model = self._config.model_routing.get(task_type, self._config.default_model)
        response = await self.chat(
            message=message,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
        )

        # 分层路由：记录档位和成本
        if self._config.enable_tiered_routing and response.success:
            # 根据模型名称推断档位
            actual_tier = self._infer_tier_from_model(model, recommended_tier)
            response.tier = actual_tier.value
            response.cost_usd = self._calculate_cost(
                response.tokens_input, response.tokens_output, actual_tier
            )
            self._update_tier_stats(actual_tier, response)

        return response

    def _get_tier_from_model_type(self, model_type: str, fallback: ModelTier) -> ModelTier:
        """根据模型类型推断档位

        Args:
            model_type: 模型类型（fast/thinking/vision/code 等）
            fallback: 推断失败时的回退档位

        Returns:
            ModelTier: 推断出的档位
        """
        model_type_lower = model_type.lower()
        if model_type_lower in ("fast", "flash", "lite"):
            return ModelTier.TIER_2_MIDTIER_GENERAL
        elif model_type_lower in ("thinking", "reasoning", "pro", "opus"):
            return ModelTier.TIER_3_FLAGSHIP_REASONING
        elif model_type_lower in ("vision",):
            return ModelTier.TIER_2_MIDTIER_GENERAL
        else:
            return fallback

    def _infer_tier_from_model(self, model_name: str, fallback: ModelTier) -> ModelTier:
        """根据模型名称推断档位

        Args:
            model_name: 模型名称
            fallback: 推断失败时的回退档位

        Returns:
            ModelTier: 推断出的档位
        """
        model_lower = model_name.lower()
        # 旗舰推理模型
        flagship_keywords = ["opus", "gpt-4", "gpt-5", "gpt4", "gpt5", "thinking", "reasoning", "pro"]
        for kw in flagship_keywords:
            if kw in model_lower:
                return ModelTier.TIER_3_FLAGSHIP_REASONING
        # 中端通用模型
        midtier_keywords = ["sonnet", "haiku", "flash", "fast", "lite", "mid", "default"]
        for kw in midtier_keywords:
            if kw in model_lower:
                return ModelTier.TIER_2_MIDTIER_GENERAL
        return fallback

    async def chat_with_provider(
        self,
        prompt: str,
        provider: str,
        model_type: str = "default",
        system_prompt: str = "",
        images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """按指定 Provider 和模型类型调用 LLM。

        Args:
            prompt: 用户消息
            provider: ``claude`` / ``gpt`` / ``deepseek`` / ``doubao`` / ``image_gen``
            model_type: ``vision`` / ``thinking`` / ``fast`` / ``code`` /
                ``reasoning`` / ``default``
            system_prompt: 系统提示词
            images: base64 编码的图片列表（VISION 模式）

        Returns:
            LLMResponse：Provider 未配置时返回 ``success=False``。
        """
        providers = self._config.providers
        if provider not in providers:
            return LLMResponse(
                success=False,
                error=f"Provider {provider} 未配置（已加载: {list(providers.keys())}）",
            )

        # 前置熔断：Provider 的 key 已被 scripts/check_llm_keys.py 标记为无效时，
        # 直接返回失败（不发起网络请求、不进入 60s 半开探测），由降级链兜底。
        health = self._provider_health.get(provider)
        if (
            health is not None
            and health.status == ProviderStatus.UNAVAILABLE
            and getattr(health, "last_error", "").startswith("[INVALID_KEY]")
        ):
            return LLMResponse(
                success=False,
                provider=provider,
                error=f"Provider {provider} 的 key 已被检测为无效，跳过直连"
                      "（请更新 key 后重跑 scripts/check_llm_keys.py）",
            )

        p = providers[provider]
        models = p.get("models", {})
        model = models.get(model_type, models.get("default", "auto"))
        base_url = p["base_url"]

        # 多密钥故障转移：依次尝试 api_keys 中的每个密钥
        api_keys = [k for k in (p.get("api_keys") or [p.get("api_key")]) if k]

        last_response: LLMResponse | None = None
        for idx, key in enumerate(api_keys):
            response = await self._call_provider_internal(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                images=images,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_name=provider,
                base_url=base_url,
                api_key=key,
            )
            if response.success:
                return response
            last_response = response
            # 还有备用密钥则继续尝试
            if idx < len(api_keys) - 1:
                self._logger.warning(
                    f"Provider {provider} 密钥#{idx + 1} 失败，切换备用密钥: "
                    f"{_sanitize_log_text(response.error)}"
                )
        # 所有密钥均失败
        return last_response or LLMResponse(
            success=False,
            provider=provider,
            error=f"Provider {provider} 无可用密钥",
        )

    async def _call_provider_internal(
        self,
        prompt: str,
        model: str,
        system_prompt: str,
        images: list[str] | None,
        temperature: float,
        max_tokens: int,
        provider_name: str = "",
        base_url: str = "",
        api_key: str = "",
    ) -> LLMResponse:
        """内部辅助：构建 messages 并调用 ``_call_provider``。

        复用 ``chat`` 的多模态消息构建与 Token 压缩逻辑。
        若未显式传入 ``base_url`` / ``api_key``，则回退到 ``self._config``
        中的值（保持向后兼容）。
        """
        has_images = bool(images)
        should_compress = self._config.enable_compression
        effective_base_url = base_url or self._config.base_url
        effective_api_key = api_key or self._config.api_key

        sys_prompt = system_prompt
        user_prompt = prompt
        if should_compress:
            sys_prompt = self._compressor.compress_system(system_prompt)
            if not has_images:
                user_prompt = self._compressor.compress_prompt(prompt)
                user_prompt += self._compressor.get_compression_suffix()

        messages: list[dict[str, Any]] = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        if has_images:
            content_parts: list[dict[str, Any]] = [
                {"type": "text", "text": user_prompt}
            ]
            for img_b64 in images:
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                })
            messages.append({"role": "user", "content": content_parts})
        else:
            messages.append({"role": "user", "content": user_prompt})

        response = await self._call_provider(
            effective_base_url,
            effective_api_key,
            model,
            messages,
            temperature,
            max_tokens,
            provider_friendly_name=provider_name,
        )

        # 确保响应中使用友好名
        if provider_name:
            response.provider = provider_name

        if response.success and should_compress:
            response.content = self._compressor.decompress_response(response.content)

        return response

    def _health_score(self, provider_name: str) -> float:
        """健康感知评分（数值越低越优先被选为 failover 候选）。

        评分维度：
        - 熔断冷却中的 Provider 返回 +inf，直接从候选中剔除；
        - 冷却已过（待半开探测）/ HALF_OPEN 的 Provider 加重惩罚，排在健康 Provider 之后；
        - 连续失败次数、历史失败率、平均延迟线性累加作为次级排序信号。
        """
        h = self._provider_health.get(provider_name)
        if h is None:
            return 0.0
        score = 0.0
        if h.status == ProviderStatus.UNAVAILABLE:
            if h.last_failure_time > 0:
                elapsed = time.time() - h.last_failure_time
                if elapsed < h.RECOVERY_INTERVAL_SEC:
                    return float("inf")
            # 冷却已过：允许作为半开探测候选，但排在健康 Provider 之后
            score += 2.0
        elif h.status == ProviderStatus.HALF_OPEN:
            score += 2.0
        elif h.status == ProviderStatus.DEGRADED:
            score += 1.0
        score += min(h.consecutive_failures, 5) * 0.2
        if h.total_requests >= 5:
            score += (h.total_failures / h.total_requests) * 1.0
        if h.total_successes > 0:
            avg_ms = h.total_latency_ms / h.total_successes
            score += min(avg_ms / 10000.0, 0.5)
        return score

    def _order_fallback_candidates(
        self, fallbacks: list[dict[str, str]]
    ) -> list[dict[str, str]]:
        """按健康分对降级候选排序（稳定排序：健康优先，熔断冷却中剔除）。

        静态配置顺序只在健康分相同时生效，避免已有部署的语义突变。
        """
        scored = []
        for fb in fallbacks:
            name = self._extract_provider_name(fb.get("base_url", ""))
            scored.append((self._health_score(name), name, fb))
        scored.sort(key=lambda t: t[0])
        ordered = [fb for s, _, fb in scored if s != float("inf")]
        skipped = [name for s, name, _ in scored if s == float("inf")]
        if skipped:
            self._logger.info(f"failover 剔除熔断冷却中的 Provider: {skipped}")
        return ordered

    def _register_provider_failure(
        self, health: ProviderHealth, error_msg: str
    ) -> None:
        """记录 Provider 失败并推进熔断状态机（多处失败路径共用，保证语义一致）。

        - HALF_OPEN 探测失败 → 无条件重新熔断并清零探针计数（由调用方
          半开分支单独处理，此处也保留兼容入口）；
        - HEALTHY/DEGRADED 连续失败达阈值 → 熔断；
        - 已 UNAVAILABLE → 保持状态，仅累加计数器。
        """
        health.consecutive_failures += 1
        health.total_failures += 1
        health.last_error = error_msg
        health.last_failure_time = time.time()
        health.half_open_probes = 0
        if health.status == ProviderStatus.HALF_OPEN:
            health.status = ProviderStatus.UNAVAILABLE
            self._logger.warning(
                f"Provider {health.name} 半开探测失败，重新熔断 {health.RECOVERY_INTERVAL_SEC}s"
            )
        elif (
            health.consecutive_failures >= health.CIRCUIT_FAILURE_THRESHOLD
            and health.status != ProviderStatus.UNAVAILABLE
        ):
            health.status = ProviderStatus.UNAVAILABLE
            self._logger.warning(
                f"Provider {health.name} 连续失败 {health.consecutive_failures} 次，"
                f"熔断 {health.RECOVERY_INTERVAL_SEC}s"
            )
        self._stats["total_failures"] += 1

    async def _call_provider(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        provider_friendly_name: str = "",
    ) -> LLMResponse:
        """调用单个 Provider
        
        Args:
            provider_friendly_name: 友好名称（如"claude"），优先用作健康状态key
        """

        # 本地 OpenVINO Provider 特殊分支：不走 HTTP
        if str(base_url).startswith("local://openvino/"):
            return await self._call_local_openvino(
                base_url=base_url,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_friendly_name=provider_friendly_name,
            )

        # 优先使用友好名作为健康状态key（多Provider路由场景），否则使用hostname
        lookup_name = provider_friendly_name or self._extract_provider_name(base_url)
        
        # CRITICAL FIX: 确保健康状态对象始终存在于 _provider_health 字典中
        # 之前的代码使用 .get(..., ProviderHealth(...)) 创建临时对象，导致状态丢失
        if lookup_name not in self._provider_health:
            self._provider_health[lookup_name] = ProviderHealth(name=lookup_name)
        health = self._provider_health[lookup_name]
        provider_name = lookup_name

        # 熔断状态机：UNAVAILABLE --冷却期到--> HALF_OPEN(单探测)
        #   -> 探测成功 => HEALTHY（完全恢复）
        #   -> 探测失败 => UNAVAILABLE（重新冷却）
        import time as _time
        now = _time.time()
        was_half_open_flag = False
        
        if health.status == ProviderStatus.UNAVAILABLE:
            if health.last_failure_time > 0:
                elapsed = now - health.last_failure_time
                if elapsed >= health.RECOVERY_INTERVAL_SEC:
                    # 转入 HALF_OPEN：允许本次请求作为单次探测
                    health.status = ProviderStatus.HALF_OPEN
                    health.half_open_probes = 0
                    was_half_open_flag = True
                    self._logger.info(
                        f"Provider {provider_name} 熔断冷却结束（{elapsed:.0f}s），转入 HALF_OPEN 探测"
                    )
                else:
                    remaining = health.RECOVERY_INTERVAL_SEC - int(elapsed)
                    return LLMResponse(
                        success=False,
                        provider=provider_name,
                        error=f"Provider {provider_name} 熔断中（连续失败 {health.consecutive_failures} 次，{remaining}s 后半开探测）"
                    )
            else:
                return LLMResponse(
                    success=False,
                    provider=provider_name,
                    error=f"Provider {provider_name} 不可用（连续失败 {health.consecutive_failures} 次）"
                )
        elif health.status == ProviderStatus.HALF_OPEN and health.half_open_probes >= 1:
            # 同一时刻只放行 1 个探测请求，避免半开状态被并发打穿；
            # 检查与下方递增之间无 await，单线程 asyncio 天然原子
            return LLMResponse(
                success=False,
                provider=provider_name,
                error=f"Provider {provider_name} 半开探测进行中，等待探测结果"
            )

        # 标记半开探测占用（检查与递增间无 await，不会被并发穿插）
        if health.status == ProviderStatus.HALF_OPEN:
            health.half_open_probes += 1

        client = await self._get_http_client()
        if client is None:
            return LLMResponse(success=False, error="HTTP 客户端不可用")

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            # 浏览器User-Agent，绕过Cloudflare 1010拦截
            "User-Agent": os.environ.get("LLM_USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # B6 修复：检查 Provider 是否要求流式（如 ModelScope 必须流式否则返回空 choices）
        # 若 stream_required=True，在 payload 中添加 stream=True
        stream_required = False
        if provider_friendly_name and provider_friendly_name in self._config.providers:
            stream_required = bool(
                self._config.providers[provider_friendly_name].get("stream_required", False)
            )
        if stream_required:
            payload["stream"] = True

        # 使用 perf_counter 进行高精度短间隔测量（不受系统时钟调整影响，Windows 分辨率~1us）
        start_time = time.perf_counter()
        self._stats["total_requests"] += 1
        health.total_requests += 1
        # 半开状态可能来自两个地方：
        # 1. 本次请求前就已是 HALF_OPEN（新契约）或 DEGRADED（旧契约用 DEGRADED 模拟半开）
        # 2. 本次请求中从 UNAVAILABLE 恢复到 HALF_OPEN（was_half_open_flag）
        was_half_open = was_half_open_flag or health.status in (
            ProviderStatus.HALF_OPEN, ProviderStatus.DEGRADED
        )

        def _record_failure(error_msg: str, latency_ms: float = 0.0) -> LLMResponse:
            """记录失败并更新熔断状态（内部辅助函数）"""
            if was_half_open or health.status == ProviderStatus.HALF_OPEN:
                # 半开探测失败 → 无视阈值立即重新熔断（并清零探针计数）
                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_error = error_msg
                health.last_failure_time = now
                health.half_open_probes = 0
                health.status = ProviderStatus.UNAVAILABLE
                self._logger.warning(
                    f"Provider {provider_name} 半开探测失败，重新进入熔断"
                )
                self._stats["total_failures"] += 1
            else:
                self._register_provider_failure(health, error_msg)
            # P3: observability 上报失败 counter（从 error_msg 推断 error_type）
            _err_type = "unknown"
            if error_msg:
                if error_msg.startswith("HTTP "):
                    try:
                        _err_type = f"http_{error_msg.split(':', 1)[0].split()[1]}"
                    except Exception:
                        _err_type = "http_error"
                elif "超时" in error_msg or "timeout" in error_msg.lower():
                    _err_type = "timeout"
                elif "Empty response" in error_msg:
                    _err_type = "empty_response"
            self._obs_report_failure(provider_name, _err_type)
            return LLMResponse(
                success=False,
                provider=provider_name,
                latency_ms=latency_ms,
                error=error_msg,
            )

        for attempt in range(self._config.max_retries):
            try:
                post_cm = client.post(url, json=payload, headers=headers)
                # 兼容 AsyncMock/替代实现：post() 可能返回协程，先 await 再进入 async with
                if inspect.isawaitable(post_cm):
                    post_cm = await post_cm
                async with post_cm as resp:
                    latency_ms = (time.perf_counter() - start_time) * 1000

                    if resp.status != 200:
                        error_text = await resp.text()
                        safe_error_text = _sanitize_log_text(error_text[:200])
                        self._logger.warning(
                            f"LLM 调用失败 (HTTP {resp.status}): {safe_error_text}"
                        )
                        # B3 修复：区分可重试与不可重试状态码
                        # - 4xx（除 408 Request Timeout 和 429 Too Many Requests）
                        #   视为不可恢复错误，立即失败不再重试
                        # - 5xx、408、429 重试，使用指数退避 + jitter
                        # - 429 时尊重 Retry-After header（如有）
                        is_retryable = (
                            resp.status >= 500
                            or resp.status == 408
                            or resp.status == 429
                        )
                        if not is_retryable:
                            return _record_failure(
                                f"HTTP {resp.status}: {safe_error_text}",
                                latency_ms,
                            )

                        if attempt < self._config.max_retries - 1:
                            # 指数退避 + jitter
                            delay_sec = (
                                self._config.retry_delay_ms * (2 ** attempt) / 1000.0
                                + random.uniform(0, 0.1)
                            )
                            # 429 时尊重 Retry-After header（秒）
                            if resp.status == 429:
                                retry_after = resp.headers.get("Retry-After")
                                if retry_after:
                                    try:
                                        delay_sec = max(delay_sec, float(retry_after))
                                    except ValueError:
                                        pass  # Retry-After 非数字（HTTP date），忽略
                            await asyncio.sleep(delay_sec)
                            continue

                        return _record_failure(
                            f"HTTP {resp.status}: {safe_error_text}",
                            latency_ms,
                        )

                    data = await resp.json()

                    content = ""
                    if data.get("choices"):
                        content = data["choices"][0].get("message", {}).get("content", "")

                    # B6 修复：stream_required provider 返回空 choices 时标记失败
                    # （未实现 SSE 流式读取，空 choices 表示 provider 要求流式但未正确处理）
                    if not content and stream_required:
                        self._logger.warning(
                            f"Provider {provider_name} 要求流式但返回空 choices（stream_required=True）"
                        )
                        return _record_failure(
                            "Empty response from streaming-required provider",
                            latency_ms,
                        )

                    usage = data.get("usage", {})
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    used_model = data.get("model", model)

                    # 更新健康状态：成功时完全恢复（包括半开探测成功）
                    health.status = ProviderStatus.HEALTHY
                    health.consecutive_failures = 0
                    health.half_open_probes = 0
                    health.total_successes += 1
                    health.total_latency_ms += latency_ms
                    health.last_success_time = now
                    # 更新平均延迟（EWMA 指数加权移动平均）
                    # 注意：health.total_requests 在请求前已 +1，所以用 avg_latency_ms==0 判断首次
                    if health.avg_latency_ms == 0.0:
                        health.avg_latency_ms = latency_ms
                    else:
                        alpha = 0.2  # 平滑系数
                        health.avg_latency_ms = (
                            alpha * latency_ms + (1 - alpha) * health.avg_latency_ms
                        )

                    # 更新统计
                    self._stats["total_successes"] += 1
                    self._stats["total_tokens_input"] += tokens_in
                    self._stats["total_tokens_output"] += tokens_out
                    self._stats["total_latency_ms"] += latency_ms

                    # B5 修复：统一在 _call_provider 成功返回前计算 cost 并累加
                    # 推断档位（用于成本计算），避免 chat/chat_with_provider 路径漏计费
                    inferred_tier = self._get_tier_from_provider(provider_name)
                    response_cost = 0.0
                    if inferred_tier is not None:
                        response_cost = self._calculate_cost(
                            tokens_in, tokens_out, inferred_tier
                        )
                    health.total_cost_usd += response_cost
                    self._stats["total_cost_usd"] += response_cost

                    if was_half_open:
                        self._logger.info(
                            f"Provider {provider_name} 半开探测成功，完全恢复"
                        )

                    return LLMResponse(
                        content=content,
                        model=used_model,
                        provider=provider_name,
                        tokens_input=tokens_in,
                        tokens_output=tokens_out,
                        latency_ms=latency_ms,
                        success=True,
                        raw=data,
                        cost_usd=response_cost,
                    )

            except asyncio.TimeoutError:
                self._logger.warning(f"LLM 调用超时 (尝试 {attempt + 1}/{self._config.max_retries})")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay_ms / 1000)
                    continue

                return _record_failure(f"请求超时 ({self._config.timeout_seconds}s)")

            except Exception as e:
                safe_err = _sanitize_log_text(str(e))
                self._logger.error(f"LLM 调用异常: {safe_err}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay_ms / 1000)
                    continue

                return _record_failure(safe_err)

        return LLMResponse(success=False, error="重试次数耗尽")

    # -------------------------------------------------------------------------
    # MiniMax H3 异步 Provider 适配（文生视频 / 视频编辑）
    # -------------------------------------------------------------------------

    def _get_h3_config(self) -> dict[str, Any]:
        """从 ConfigManager / LLMConfig.providers / 环境变量 读 MiniMax H3 配置。

        优先级（高→低）：环境变量 > 实例 LLMConfig.providers > 配置文件默认层。
        （此前 h3 默认层的 base_url 默认值会在 or 链里吞掉 env，修：env 前置。）
        """
        env_url = os.environ.get("AEKV_LLM_MINIMAX_H3_BASE_URL", "")
        env_key = os.environ.get("AEKV_LLM_MINIMAX_H3_API_KEY", "")
        try:
            from core.config import ConfigManager
            cfg_mgr = ConfigManager()
            h3 = cfg_mgr.get("minimax_h3", {})
        except Exception:
            h3 = {}
        prov = self._config.providers.get("minimax_h3", {})
        base_url = env_url or prov.get("base_url") or h3.get("base_url") or ""
        api_key = env_key or prov.get("api_key") or h3.get("api_key") or ""
        merged: dict[str, Any] = {
            "base_url": base_url,
            "api_key": api_key,
            "cost_per_sec_2k": float(prov.get("cost_per_sec_2k") or h3.get("cost_per_sec_2k") or 0.8),
            "cost_per_sec_768p": float(prov.get("cost_per_sec_768p") or h3.get("cost_per_sec_768p") or 0.3),
            "poll_interval_sec": float(h3.get("poll_interval_sec") or 3.0),
            "max_poll_wait_sec": float(h3.get("max_poll_wait_sec") or 600),
            "download_dir": h3.get("download_dir") or os.path.abspath("./output/h3_downloads"),
            "cache_dir": h3.get("cache_dir") or os.path.abspath("./data/h3_cache"),
        }
        return merged

    async def _download_file(self, url: str, output_path: str) -> bool:
        """异步 HTTP 下载 url 到 output_path，创建目录，失败 False，成功 True。

        不依赖 aiofiles 避免未装就崩；HTTP 客户端优先 self._http_client，
        回退到 self._get_http_client()（H3 自己也走这个）。
        测试时可 monkeypatch 覆盖这个方法。
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        except Exception:
            pass
        client = self._http_client
        if client is None:
            try:
                client = await self._get_http_client()
            except Exception:
                client = None
        if client is None:
            # 最后退路：阻塞 urllib（不建议生产，但可应急）
            try:
                import urllib.request
                urllib.request.urlretrieve(url, output_path)
                return True
            except Exception:
                return False
        try:
            async with client.get(url) as r:
                if getattr(r, "status", 200) != 200:
                    return False
                chunk_list = []
                async for chunk in r.content.iter_chunked(1024 * 256):
                    chunk_list.append(chunk) if hasattr(r, "content") else None
                if not chunk_list:
                    body = await r.read()
                    with open(output_path, "wb") as f:
                        f.write(body)
                else:
                    with open(output_path, "wb") as f:
                        for c in chunk_list:
                            f.write(c)
            return True
        except Exception:
            # 再试同步读
            try:
                async with client.get(url) as r:
                    data = await r.read()
                    with open(output_path, "wb") as f:
                        f.write(data)
                return True
            except Exception:
                return False

    async def _h3_request(self, method: str, path: str, json_body: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
        """内部：发送 H3 HTTP 请求，统一异常捕获。

        Args:
            method: "GET" / "POST"
            path: 相对路径，如 "/video-async/generations"
            json_body: POST body（dict）
            timeout: 超时秒数（None 则用默认 timeout_seconds）

        Returns:
            dict: 成功时返回 JSON 响应；失败返回 {"error": str, "status_code": int}
        """
        h3_cfg = self._get_h3_config()
        client = await self._get_http_client()
        if client is None:
            return {"error": "HTTP 客户端不可用", "status_code": 0}
        if not h3_cfg.get("base_url") or not h3_cfg.get("api_key"):
            return {"error": "MiniMax H3 未配置 base_url 或 api_key", "status_code": 0}

        url = f"{h3_cfg['base_url'].rstrip('/')}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {h3_cfg['api_key']}",
        }
        import aiohttp as _aiohttp
        client_timeout = _aiohttp.ClientTimeout(
            total=timeout or self._config.timeout_seconds
        )
        try:
            if method.upper() == "GET":
                async with client.get(url, headers=headers, timeout=client_timeout) as resp:
                    status = resp.status
                    if status == 200:
                        return await resp.json()
                    text = await resp.text()
                    return {"error": _sanitize_log_text(text[:500]), "status_code": status}
            else:
                async with client.post(url, headers=headers, json=json_body or {}, timeout=client_timeout) as resp:
                    status = resp.status
                    if status in (200, 201, 202):
                        return await resp.json()
                    text = await resp.text()
                    return {"error": _sanitize_log_text(text[:500]), "status_code": status}
        except asyncio.TimeoutError as e:
            return {"error": f"H3 请求超时: {e}", "status_code": 408}
        except Exception as e:
            return {"error": f"H3 请求异常: {e}", "status_code": 0}

    async def _h3_poll_until_done(self, task_id: str, h3_cfg: dict[str, Any]) -> dict[str, Any]:
        """内部：轮询 H3 任务状态直到完成 / 失败 / 超时。

        Args:
            task_id: 创建任务返回的 task_id
            h3_cfg: _get_h3_config() 返回的配置 dict

        Returns:
            dict: 成功时返回 result 字段；失败返回 {"error": str, "status": str}
        """
        poll_interval = h3_cfg.get("poll_interval_sec", 3.0)
        max_wait = h3_cfg.get("max_poll_wait_sec", 600)
        start_time = time.time()

        while (time.time() - start_time) < max_wait:
            resp = await self._h3_request("GET", f"/video-async/tasks/{task_id}")
            if resp.get("error"):
                return resp
            task = resp.get("data", resp)
            status = task.get("status", "")
            if status == "succeeded":
                return task.get("result", task)
            if status in ("failed", "canceled"):
                return {
                    "error": task.get("error_message") or f"H3 任务 {status}",
                    "status": status,
                }
            await asyncio.sleep(poll_interval)

        return {
            "error": f"H3 轮询超时({max_wait}s)",
            "status": "timeout",
        }

    async def generate_video(
        self,
        prompt: str,
        *,
        duration_sec: int = 10,
        resolution: str = "768p",
        aspect_ratio: str = "16:9",
        reference_images: list[str] | None = None,
        reference_videos: list[str] | None = None,
        reference_audios: list[str] | None = None,
        output_path: str = "",
        prompt_extra: str = "",
    ) -> dict[str, Any]:
        """顶层：MiniMax H3 文生视频 / 图生视频。

        Args:
            prompt: 主提示词
            duration_sec: 视频时长（秒），默认 10
            resolution: "768p" 或 "2k"，默认 "768p"
            aspect_ratio: 宽高比，默认 "16:9"
            reference_images: 参考图 URL 或本地路径列表（图生视频）
            reference_videos: 参考视频 URL 或本地路径列表（V2V）
            reference_audios: 参考音频 URL 或本地路径列表
            output_path: 输出文件路径（空则用 download_dir/{uuid}.mp4）
            prompt_extra: 附加提示词（会拼接在主 prompt 后）

        Returns:
            dict: {success, output_path, task_id, duration_sec, resolution,
                   download_url, cost_usd, error}
        """
        h3_cfg = self._get_h3_config()
        result: dict[str, Any] = {
            "success": False,
            "output_path": "",
            "task_id": "",
            "duration_sec": duration_sec,
            "resolution": resolution,
            "download_url": "",
            "cost_usd": 0.0,
            "error": "",
        }
        try:
            if not h3_cfg.get("base_url") or not h3_cfg.get("api_key"):
                result["error"] = "MiniMax H3 未配置 base_url 或 api_key"
                return result

            # 1. 组装请求体
            full_prompt = f"{prompt}\n{prompt_extra}" if prompt_extra else prompt
            body: dict[str, Any] = {
                "model": "minimax-h3",
                "prompt": full_prompt,
                "duration_sec": duration_sec,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            }
            if reference_images:
                body["reference_images"] = reference_images
            if reference_videos:
                body["reference_videos"] = reference_videos
            if reference_audios:
                body["reference_audios"] = reference_audios

            # 2. POST 创建任务
            create_resp = await self._h3_request("POST", "/video-async/generations", body)
            if create_resp.get("error"):
                result["error"] = create_resp["error"]
                return result
            task_data = create_resp.get("data", create_resp)
            task_id = task_data.get("task_id") or task_data.get("id")
            if not task_id:
                result["error"] = f"H3 创建任务响应缺少 task_id: {create_resp}"
                return result
            result["task_id"] = task_id

            # 3. 轮询直到完成
            poll_result = await self._h3_poll_until_done(task_id, h3_cfg)
            if poll_result.get("error"):
                result["error"] = poll_result["error"]
                return result
            download_url = ""
            if isinstance(poll_result, dict):
                samples = poll_result.get("samples") or poll_result.get("output_files") or []
                if samples:
                    download_url = samples[0] if isinstance(samples[0], str) else samples[0].get("url", "")
                if not download_url:
                    download_url = poll_result.get("download_url") or poll_result.get("video_url") or ""
            if not download_url:
                result["error"] = f"H3 任务完成但未找到下载 URL: {poll_result}"
                return result
            result["download_url"] = download_url

            # 4. 下载文件
            try:
                os.makedirs(h3_cfg["download_dir"], exist_ok=True)
            except Exception:
                pass
            if not output_path:
                import uuid
                output_path = os.path.join(h3_cfg["download_dir"], f"{uuid.uuid4().hex}.mp4")
            try:
                client = await self._get_http_client()
                if client is None:
                    result["error"] = "HTTP 客户端不可用（下载阶段）"
                    return result
                async with client.get(download_url) as dl_resp:
                    if dl_resp.status != 200:
                        result["error"] = f"下载失败 HTTP {dl_resp.status}"
                        return result
                    content = await dl_resp.read()
                    with open(output_path, "wb") as f:
                        f.write(content)
                result["output_path"] = output_path
            except Exception as e:
                result["error"] = f"下载视频失败: {e}"
                return result

            # 5. 计费 + 统计
            cost_key = "cost_per_sec_2k" if resolution.lower() in ("2k", "4k") else "cost_per_sec_768p"
            unit_price = float(h3_cfg.get(cost_key, 0.3))
            modality_cost = round(duration_sec * unit_price, 6)
            result["cost_usd"] = modality_cost
            self._stats["total_video_seconds"] += duration_sec
            self._stats["total_modality_cost_usd"] += modality_cost
            self._stats["total_cost_usd"] += modality_cost

            # 对应 tier 统计（VIDEO_GENERATION → TIER_2）
            try:
                tier_stat = self._tier_stats.get(ModelTier.TIER_2_MIDTIER_GENERAL)
                if tier_stat is not None:
                    tier_stat["total_video_seconds"] += duration_sec
                    tier_stat["total_modality_cost_usd"] += modality_cost
                    tier_stat["total_cost_usd"] += modality_cost
            except Exception:
                pass

            # ProviderHealth 更新
            health = self._provider_health.get("minimax_h3")
            if health is None:
                health = ProviderHealth(name="minimax_h3")
                self._provider_health["minimax_h3"] = health
            health.total_requests += 1
            health.total_successes = getattr(health, "total_successes", 0)
            health.total_video_seconds += duration_sec
            health.total_cost_usd += modality_cost

            result["success"] = True
            return result
        except Exception as e:
            result["error"] = f"generate_video 未处理异常: {e}"
            return result

    async def edit_video(
        self,
        *,
        operation: str,
        source_video: str,
        instruction: str = "",
        reference_image: str = "",
        output_path: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """顶层：MiniMax H3 视频编辑（字幕修改 / 风格化 / 动作迁移 / 瑕疵修复 等）。

        Args:
            operation: 操作类型字符串，见函数文档映射表
            source_video: 源视频路径或 URL
            instruction: 自然语言编辑指令
            reference_image: 参考图路径或 URL（如风格化 / 动作迁移用）
            output_path: 输出文件路径（空则用 download_dir/{uuid}.mp4）
            **kwargs: 额外参数：duration_sec（实际秒数，用于计费）等

        Returns:
            dict: {success, output_path, task_id, download_url, cost_usd, error}
        """
        h3_cfg = self._get_h3_config()
        result: dict[str, Any] = {
            "success": False,
            "output_path": "",
            "task_id": "",
            "download_url": "",
            "cost_usd": 0.0,
            "error": "",
        }
        try:
            if not h3_cfg.get("base_url") or not h3_cfg.get("api_key"):
                result["error"] = "MiniMax H3 未配置 base_url 或 api_key"
                return result
            if not source_video:
                result["error"] = "edit_video 需要 source_video"
                return result

            # operation → endpoint 映射
            op_lower = operation.lower()
            endpoint_map = {
                "subtitle_modify": "/video-async/edits/subtitle",
                "字幕修改": "/video-async/edits/subtitle",
                "style_transfer": "/video-async/edits/style",
                "风格化": "/video-async/edits/style",
                "手绘特效": "/video-async/edits/style",
                "motion_transfer": "/video-async/edits/motion-transfer",
                "动作迁移": "/video-async/edits/motion-transfer",
                "inpainting": "/video-async/edits/inpaint",
                "瑕疵修复": "/video-async/edits/inpaint",
                "物体擦除": "/video-async/edits/inpaint",
                "object_replace": "/video-async/edits/object",
                "物体替换": "/video-async/edits/object",
                "scene_alteration": "/video-async/edits/scene",
                "场景修改": "/video-async/edits/scene",
                "rate_adjustment": "/video-async/edits/rate",
                "快慢剪辑": "/video-async/edits/rate",
                "bgm_replace": "/video-async/edits/bgm",
                "bgm更换": "/video-async/edits/bgm",
            }
            endpoint = endpoint_map.get(op_lower, "/video-async/edits")

            # 1. 组装请求体
            body: dict[str, Any] = {
                "model": "minimax-h3",
                "source_video": source_video,
            }
            if instruction:
                body["instruction"] = instruction
            if reference_image:
                body["reference_image"] = reference_image
            # 透传额外参数
            for k, v in kwargs.items():
                if k not in ("source_video", "instruction", "reference_image", "output_path", "operation"):
                    body[k] = v

            # 2. POST 创建任务
            create_resp = await self._h3_request("POST", endpoint, body)
            if create_resp.get("error"):
                result["error"] = create_resp["error"]
                return result
            task_data = create_resp.get("data", create_resp)
            task_id = task_data.get("task_id") or task_data.get("id")
            if not task_id:
                result["error"] = f"H3 创建编辑任务响应缺少 task_id: {create_resp}"
                return result
            result["task_id"] = task_id

            # 3. 轮询
            poll_result = await self._h3_poll_until_done(task_id, h3_cfg)
            if poll_result.get("error"):
                result["error"] = poll_result["error"]
                return result
            download_url = ""
            if isinstance(poll_result, dict):
                samples = poll_result.get("samples") or poll_result.get("output_files") or []
                if samples:
                    download_url = samples[0] if isinstance(samples[0], str) else samples[0].get("url", "")
                if not download_url:
                    download_url = poll_result.get("download_url") or poll_result.get("video_url") or ""
            if not download_url:
                result["error"] = f"H3 编辑任务完成但未找到下载 URL: {poll_result}"
                return result
            result["download_url"] = download_url

            # 4. 下载
            try:
                os.makedirs(h3_cfg["download_dir"], exist_ok=True)
            except Exception:
                pass
            if not output_path:
                import uuid
                output_path = os.path.join(h3_cfg["download_dir"], f"{uuid.uuid4().hex}.mp4")
            try:
                client = await self._get_http_client()
                if client is None:
                    result["error"] = "HTTP 客户端不可用（下载阶段）"
                    return result
                async with client.get(download_url) as dl_resp:
                    if dl_resp.status != 200:
                        result["error"] = f"下载失败 HTTP {dl_resp.status}"
                        return result
                    content = await dl_resp.read()
                    with open(output_path, "wb") as f:
                        f.write(content)
                result["output_path"] = output_path
            except Exception as e:
                result["error"] = f"下载编辑视频失败: {e}"
                return result

            # 5. 计费（若 kwargs 中无 duration_sec 则用默认 10 秒）
            duration_sec = int(kwargs.get("duration_sec", 10) or 10)
            # 编辑任务默认按 768p 单价计费（实际分辨率未暴露时按低档位计算，避免高估）
            unit_price = float(h3_cfg.get("cost_per_sec_768p", 0.3))
            modality_cost = round(duration_sec * unit_price, 6)
            result["cost_usd"] = modality_cost
            self._stats["total_video_seconds"] += duration_sec
            self._stats["total_modality_cost_usd"] += modality_cost
            self._stats["total_cost_usd"] += modality_cost

            # 对应 tier 统计：SUBTITLE_MODIFICATION/RATE_ADJUSTMENT → TIER_1，其余编辑类 → TIER_2
            try:
                tier_1_ops = {"subtitle_modify", "字幕修改", "rate_adjustment", "快慢剪辑"}
                target_tier = (
                    ModelTier.TIER_1_LOCAL_SPECIALIZED
                    if op_lower in tier_1_ops
                    else ModelTier.TIER_2_MIDTIER_GENERAL
                )
                tier_stat = self._tier_stats.get(target_tier)
                if tier_stat is not None:
                    tier_stat["total_video_seconds"] += duration_sec
                    tier_stat["total_modality_cost_usd"] += modality_cost
                    tier_stat["total_cost_usd"] += modality_cost
            except Exception:
                pass

            # ProviderHealth 更新
            health = self._provider_health.get("minimax_h3")
            if health is None:
                health = ProviderHealth(name="minimax_h3")
                self._provider_health["minimax_h3"] = health
            health.total_requests += 1
            health.total_successes = getattr(health, "total_successes", 0)
            health.total_video_seconds += duration_sec
            health.total_cost_usd += modality_cost

            result["success"] = True
            return result
        except Exception as e:
            result["error"] = f"edit_video 未处理异常: {e}"
            return result

    # -------------------------------------------------------------------------
    # P2：MiniMax H3 本地部署 + 手绘特效（代码预留骨架，权重开源后填充）
    # -------------------------------------------------------------------------

    def check_local_h3_available(self) -> dict[str, Any]:
        """P2 骨架：检测 MiniMax H3 本地部署是否可用。
        
        2026-08-03 权重刚开源，具体加载脚本/推理方式待社区确认；
        当前先根据 config + 硬件规格做可用性预判，返回结构化结果供上层决策。
        
        Returns:
            dict: {
                "available": bool,           # 综合判定是否可本地跑
                "reason": str,               # 不可用时的原因（中文）
                "model_path": str,           # 模型权重路径
                "device": str,               # "cuda"/"cpu"/"none"
                "vram_total_gb": float,      # GPU 总显存（cuda 时才有）
                "vram_8gb_mode": bool,       # 是否启用低显存模式
                "min_requirement_gb": float, # H3 最低显存需求（暂估 16GB，8GB 需 offload）
            }
        """
        import os as _os
        cfg = self._get_h3_config()
        local_cfg = cfg.get("local_deployment", {}) if isinstance(cfg, dict) else {}
        result: dict[str, Any] = {
            "available": False,
            "reason": "",
            "model_path": local_cfg.get("model_path", "") or _os.environ.get("AEKV_LLM_MINIMAX_H3_LOCAL_MODEL_PATH", ""),
            "device": local_cfg.get("device", "auto"),
            "vram_total_gb": 0.0,
            "vram_8gb_mode": bool(local_cfg.get("vram_8gb_mode", True)),
            "min_requirement_gb": 16.0,
        }
        if not local_cfg.get("enabled", False):
            result["reason"] = "config.minimax_h3.local_deployment.enabled=False，未启用本地部署"
            return result
        if not result["model_path"] or not _os.path.exists(result["model_path"]):
            result["reason"] = f"本地模型路径不存在: {result['model_path']!r}，请配置 AEKV_LLM_MINIMAX_H3_LOCAL_MODEL_PATH"
            return result
        # 尝试检测 GPU 显存（不硬依赖 pynvml / torch，检测不到就走 CPU 或按 8GB 模式打标）
        vram_gb = 0.0
        try:
            import subprocess as _sp
            out = _sp.check_output(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                stderr=_sp.DEVNULL, timeout=5,
            )
            vram_mb = float(out.decode().strip().splitlines()[0])
            vram_gb = round(vram_mb / 1024.0, 2)
        except Exception:
            vram_gb = 0.0
        result["vram_total_gb"] = vram_gb
        if vram_gb <= 0:
            result["device"] = "cpu"
            result["reason"] = "未检测到 NVIDIA GPU，本地部署只能跑 CPU（速度极慢，不推荐）"
            result["available"] = False  # CPU 跑 H3 几无实用价值，标不可用
            return result
        if vram_gb >= result["min_requirement_gb"]:
            result["device"] = "cuda"
            result["available"] = True
            result["reason"] = f"GPU {vram_gb}GB ≥ 需求 {result['min_requirement_gb']}GB，可本地原生推理"
        elif result["vram_8gb_mode"] and vram_gb >= 6.0:
            # 8GB 玩家：通过 num_persistent_param_in_dit=0 + CPU offload 可以跑，但速度慢
            result["device"] = "cuda-8gb-offload"
            result["available"] = True
            result["reason"] = (
                f"GPU {vram_gb}GB < 需求 {result['min_requirement_gb']}GB，"
                "启用 vram_8gb_mode（低显存+CPU offload）可本地推理，速度较慢"
            )
        else:
            result["available"] = False
            result["reason"] = (
                f"GPU {vram_gb}GB < 需求 {result['min_requirement_gb']}GB，"
                "且 vram_8gb_mode 未启用，无法本地部署"
            )
        return result

    async def sketch_to_effect(
        self,
        *,
        sketch_image_path: str,
        prompt: str,
        output_path: str = "",
        duration_sec: int = 10,
    ) -> dict[str, Any]:
        """P2 骨架：MiniMax H3「手绘即特效」接口封装。
        
        H3 核心卖点之一：用户在画面上画涂鸦/遮罩，配合文字提示即生成对应特效。
        本骨架在调用前先校验本地/云端可用性，统一走 edit_video(inpainting+style_transfer 混合) 路径。
        """
        import os as _os
        result: dict[str, Any] = {
            "success": False,
            "output_path": "",
            "mode": "",
            "error": "",
        }
        if not sketch_image_path or not _os.path.exists(sketch_image_path):
            result["error"] = f"手绘参考图不存在: {sketch_image_path!r}"
            return result
        # 优先云端 API（稳定、无需本地权重）
        h3_cfg = self._get_h3_config()
        if h3_cfg.get("api_key"):
            result["mode"] = "cloud_sketch_to_effect"
            combined_prompt = (
                f"用户手绘参考图已提供，请根据手绘区域和文字提示生成对应特效。"
                f"文字提示：{prompt}。保留原画其他内容不变，只在手绘对应区域应用特效。"
            )
            cloud_result = await self.edit_video(
                operation="style_transfer",
                source_video=sketch_image_path,
                instruction=combined_prompt,
                reference_image=sketch_image_path,
                output_path=output_path,
                duration_sec=duration_sec,
            )
            result.update(cloud_result)
            return result
        # 云端不可用时，尝试本地部署
        local_check = self.check_local_h3_available()
        if local_check["available"]:
            result["mode"] = "local_sketch_to_effect"
            result["error"] = f"本地部署骨架预留：权重路径={local_check['model_path']}，device={local_check['device']}，具体推理脚本待社区方案稳定后填充"
            return result
        result["error"] = "手绘特效接口需要云端 API Key 或本地部署权重，当前两者均不可用"
        return result

    # -------------------------------------------------------------------------
    # 分层路由与成本计算
    # -------------------------------------------------------------------------

    def _calculate_cost(self, tokens_input: int, tokens_output: int, tier: ModelTier) -> float:
        """计算调用成本

        Args:
            tokens_input: 输入 token 数量
            tokens_output: 输出 token 数量
            tier: 模型档位

        Returns:
            float: 本次调用成本（美元），保留6位小数
        """
        tier_cfg = self._config.tier_config.get(tier, {})
        cost_in = tier_cfg.get("cost_per_1k_input", 0) * tokens_input / 1000
        cost_out = tier_cfg.get("cost_per_1k_output", 0) * tokens_output / 1000
        return round(cost_in + cost_out, 6)

    def _update_tier_stats(self, tier: ModelTier, response: LLMResponse) -> None:
        """更新档位统计数据

        Args:
            tier: 模型档位
            response: LLM 响应对象
        """
        tier_stat = self._tier_stats.get(tier)
        if tier_stat is None:
            return

        tier_stat["total_requests"] += 1
        tier_stat["total_latency_ms"] += response.latency_ms
        tier_stat["total_tokens_input"] += response.tokens_input
        tier_stat["total_tokens_output"] += response.tokens_output
        tier_stat["total_cost_usd"] += response.cost_usd

        if response.success:
            tier_stat["total_successes"] += 1
        else:
            tier_stat["total_failures"] += 1

    def _get_tier_from_provider(self, provider_name: str) -> ModelTier | None:
        """根据 Provider 名称推断所属档位

        Args:
            provider_name: Provider 名称

        Returns:
            Optional[ModelTier]: 对应的档位，无法确定时返回 None
        """
        for tier, cfg in self._config.tier_config.items():
            providers = cfg.get("providers", [])
            for p in providers:
                if p.lower() in provider_name.lower() or provider_name.lower() in p.lower():
                    return tier
        return None

    def get_tier_stats(self) -> dict[str, Any]:
        """获取各档位调用统计

        Returns:
            Dict[str, Any]: 各档位的调用量、成功率、平均延迟、总成本等统计信息
        """
        result = {}
        for tier, stat in self._tier_stats.items():
            total = stat["total_requests"]
            success_rate = (stat["total_successes"] / total * 100) if total > 0 else 0
            avg_latency = (stat["total_latency_ms"] / total) if total > 0 else 0
            result[tier.value] = {
                "tier_name": tier.name,
                "total_requests": total,
                "total_successes": stat["total_successes"],
                "total_failures": stat["total_failures"],
                "success_rate": f"{success_rate:.1f}%",
                "total_tokens_input": stat["total_tokens_input"],
                "total_tokens_output": stat["total_tokens_output"],
                "avg_latency_ms": f"{avg_latency:.0f}",
                "total_cost_usd": round(stat["total_cost_usd"], 6),
            }
        return result

    def get_cascade_stats(self) -> dict[str, Any]:
        """获取级联路由统计

        Returns:
            Dict[str, Any]: 级联路由的尝试次数、升级次数、节省金额、平均路径长度等统计信息
        """
        cascade_stats = self._cascade_stats
        attempts = cascade_stats.get("cascade_attempts", 0)
        upgrades = cascade_stats.get("cascade_upgrades", 0)
        upgrade_rate = (upgrades / attempts * 100) if attempts > 0 else 0

        return {
            "cascade_attempts": attempts,
            "cascade_upgrades": upgrades,
            "upgrade_rate": f"{upgrade_rate:.1f}%",
            "cascade_savings_usd": round(cascade_stats.get("cascade_savings_usd", 0.0), 6),
            "cascade_avg_path_length": cascade_stats.get("cascade_avg_path_length", 0.0),
            "cascade_total_path_length": cascade_stats.get("cascade_total_path_length", 0),
        }

    # -------------------------------------------------------------------------
    # 置信度提取机制
    # -------------------------------------------------------------------------

    def _extract_confidence(
        self,
        response_content: str,
        tier: ModelTier,
        task_type: TaskType,
    ) -> tuple[float, str]:
        """从模型响应中提取置信度

        置信度来源优先级：
        1. 显式置信度：模型输出中包含 "confidence: 0.85" 等格式
        2. 结构化置信度：根据输出结构完整性、格式规范度推断
        3. 档位校准：根据不同档位有不同的基准置信度bias
        4. 任务类型校准：简单任务默认置信度更高

        Args:
            response_content: 模型响应内容
            tier: 模型档位
            task_type: 任务类型

        Returns:
            Tuple[float, str]: (置信度分数 0.0-1.0, 置信度判断依据)
        """
        if not response_content:
            return 0.0, "响应内容为空"

        confidence = 0.5
        reasons = []

        # 1. 尝试提取显式置信度
        explicit_patterns = [
            r'confidence\s*[:=]\s*0?\.?(\d{1,3})',
            r'置信度\s*[:=为是]\s*0?\.?(\d{1,3})',
            r'确信度\s*[:=为是]\s*0?\.?(\d{1,3})',
        ]
        for pattern in explicit_patterns:
            match = re.search(pattern, response_content, re.IGNORECASE)
            if match:
                try:
                    val = float(match.group(1))
                    if val > 1:
                        val = val / 100 if val > 10 else val / 10
                    confidence = max(0.0, min(1.0, val))
                    reasons.append(f"显式置信度={confidence:.2f}")
                    break
                except (ValueError, IndexError):
                    pass

        # 2. 结构化置信度启发式评估
        structure_score = 0.0
        structure_reasons = []

        # 2.1 输出长度评估（适中为好）
        content_len = len(response_content)
        if 50 <= content_len <= 2000:
            structure_score += 0.1
            structure_reasons.append("长度适中")
        elif content_len < 20:
            structure_score -= 0.2
            structure_reasons.append("内容过短")
        elif content_len > 5000:
            structure_score -= 0.05
            structure_reasons.append("内容过长")

        # 2.2 格式规范度评估
        structural_patterns = [
            (r'^\s*[-*•]\s+', "列表结构"),
            (r'^\s*\d+\.\s+', "编号列表"),
            (r'```[\s\S]*?```', "代码块"),
            (r'^\s*#{1,6}\s+', "标题结构"),
            (r'^\s*\|.+\|\s*$', "表格结构"),
            (r'^\s*>.+', "引用块"),
        ]
        structure_count = 0
        for pattern, name in structural_patterns:
            if re.search(pattern, response_content, re.MULTILINE):
                structure_count += 1
                structure_reasons.append(name)

        if structure_count >= 3:
            structure_score += 0.15
        elif structure_count >= 1:
            structure_score += 0.08

        # 2.3 犹豫词检测（降低置信度）
        hesitation_words = [
            "可能", "也许", "大概", "或许", "应该是", "可能是",
            "我猜", "估计", "说不定", "不一定", "不太确定",
            "perhaps", "maybe", "probably", "possibly", "might",
            "i think", "i guess", "not sure", "uncertain",
        ]
        hesitation_count = 0
        for word in hesitation_words:
            if word.lower() in response_content.lower():
                hesitation_count += 1
        if hesitation_count >= 3:
            structure_score -= 0.15
            structure_reasons.append(f"犹豫词较多({hesitation_count}个)")
        elif hesitation_count >= 1:
            structure_score -= 0.05
            structure_reasons.append(f"有犹豫词({hesitation_count}个)")

        # 2.4 事实性错误迹象检测
        error_indicators = [
            "抱歉", "对不起", "无法", "不知道", "不清楚",
            "sorry", "unable", "don't know", "not sure",
            "错误", "error", "wrong", "incorrect",
        ]
        error_count = 0
        for indicator in error_indicators:
            if indicator.lower() in response_content.lower():
                error_count += 1
        if error_count >= 2:
            structure_score -= 0.2
            structure_reasons.append(f"错误迹象({error_count}个)")
        elif error_count >= 1:
            structure_score -= 0.1
            structure_reasons.append(f"有错误迹象({error_count}个)")

        confidence += structure_score
        reasons.extend(structure_reasons)

        # 3. 档位校准
        tier_bias = self._config.auto_confidence_calibration.get(tier.value, 0.0)
        confidence += tier_bias
        if tier_bias != 0:
            reasons.append(f"档位校准{tier_bias:+.2f}")

        # 4. 任务类型校准
        simple_tasks = {
            TaskType.INTENT_CLASSIFICATION,
            TaskType.EFFECT_SEARCH,
            TaskType.FEEDBACK_ANALYSIS,
        }
        if task_type in simple_tasks:
            confidence += 0.05
            reasons.append("简单任务+0.05")

        # 确保置信度在 0-1 范围内
        confidence = max(0.0, min(1.0, confidence))

        # 确定置信度级别
        confidence_level = self._get_confidence_level(confidence)
        reasons.append(f"最终置信度={confidence:.2f}({confidence_level})")

        return confidence, "; ".join(reasons)

    def _get_confidence_level(self, confidence: float) -> str:
        """根据置信度分数获取置信度级别

        Args:
            confidence: 置信度分数 (0.0-1.0)

        Returns:
            str: 置信度级别名称
        """
        if confidence >= 0.9:
            return ConfidenceLevel.VERY_HIGH.value
        elif confidence >= 0.7:
            return ConfidenceLevel.HIGH.value
        elif confidence >= 0.5:
            return ConfidenceLevel.MEDIUM.value
        elif confidence >= 0.3:
            return ConfidenceLevel.LOW.value
        else:
            return ConfidenceLevel.VERY_LOW.value

    # -------------------------------------------------------------------------
    # 质量门控
    # -------------------------------------------------------------------------

    def _validate_response_quality(
        self,
        response: LLMResponse,
        task_type: TaskType,
    ) -> tuple[bool, float, str]:
        """验证响应质量，返回 (是否通过, 置信度, 原因)

        质量检查项：
        1. 非空检查
        2. 格式检查（JSON格式任务）
        3. 长度检查
        4. 危险内容检查

        Args:
            response: LLM 响应对象
            task_type: 任务类型

        Returns:
            Tuple[bool, float, str]: (是否通过质量检查, 质量分, 检查原因)
        """
        quality_score = 1.0
        reasons = []
        passed = True

        # 1. 非空检查
        if not response.success:
            quality_score = 0.0
            reasons.append("响应失败")
            passed = False
            return passed, quality_score, "; ".join(reasons)

        if not response.content:
            quality_score = 0.0
            reasons.append("内容为空")
            passed = False
            return passed, quality_score, "; ".join(reasons)

        content = response.content.strip()
        if not content:
            quality_score = 0.0
            reasons.append("内容仅空白字符")
            passed = False
            return passed, quality_score, "; ".join(reasons)

        reasons.append("非空检查通过")

        # 2. 格式检查（JSON格式任务）
        json_task_types = {
            TaskType.INTENT_CLASSIFICATION,
            TaskType.PARAMETER_OPTIMIZATION,
            TaskType.EFFECT_SEARCH,
        }
        if task_type in json_task_types:
            has_json = False
            # 尝试提取 JSON
            json_patterns = [
                r'```json\s*([\s\S]*?)\s*```',
                r'```\s*([\s\S]*?)\s*```',
            ]
            for pattern in json_patterns:
                match = re.search(pattern, content)
                if match:
                    try:
                        json.loads(match.group(1))
                        has_json = True
                        reasons.append("JSON格式正确")
                        break
                    except json.JSONDecodeError:
                        continue

            # 直接尝试解析整个内容
            if not has_json:
                try:
                    json.loads(content)
                    has_json = True
                    reasons.append("JSON格式正确")
                except json.JSONDecodeError:
                    pass

            if not has_json:
                quality_score -= 0.3
                reasons.append("缺少有效JSON格式")

        # 3. 长度检查
        content_len = len(content)
        if content_len < 10:
            quality_score -= 0.2
            reasons.append(f"内容过短({content_len}字符)")
        elif content_len < 30:
            quality_score -= 0.1
            reasons.append(f"内容偏短({content_len}字符)")

        # 4. 危险内容检查（简单启发式）
        dangerous_patterns = [
            r'(?i)rm\s+-rf\s+/',
            r'(?i)drop\s+table',
            r'(?i)delete\s+from\s+\w+',
            r'(?i)<script.*?>',
            r'(?i)javascript:',
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, content):
                quality_score -= 0.5
                reasons.append("检测到潜在危险内容")
                passed = False
                break

        # 确保质量分在 0-1 范围内
        quality_score = max(0.0, min(1.0, quality_score))

        if passed:
            reasons.append(f"质量分={quality_score:.2f}")

        return passed, quality_score, "; ".join(reasons)

    # -------------------------------------------------------------------------
    # 升级判断逻辑
    # -------------------------------------------------------------------------

    def _should_upgrade(
        self,
        response: LLMResponse,
        current_tier: ModelTier,
        task_type: TaskType,
        upgrade_count: int,
    ) -> tuple[bool, str]:
        """判断是否需要升级到更高档位

        判断条件：
        1. 已达最大升级次数 → 不升级
        2. 当前已是最高档 → 不升级
        3. 置信度 < 阈值 → 升级
        4. 响应为空/错误 → 升级
        5. 任务类型必须高档位 → 不升级（已经是推荐档位）

        Args:
            response: 当前档位的响应
            current_tier: 当前模型档位
            task_type: 任务类型
            upgrade_count: 已升级次数

        Returns:
            Tuple[bool, str]: (是否需要升级, 判断原因)
        """
        # 1. 已达最大升级次数
        max_upgrades = self._config.cascade_max_upgrades
        if upgrade_count >= max_upgrades:
            return False, f"已达最大升级次数({max_upgrades}次)"

        # 2. 当前已是最高档
        tier_order = [
            ModelTier.TIER_1_LOCAL_SPECIALIZED,
            ModelTier.TIER_2_MIDTIER_GENERAL,
            ModelTier.TIER_3_FLAGSHIP_REASONING,
        ]
        current_index = tier_order.index(current_tier) if current_tier in tier_order else -1
        if current_index >= len(tier_order) - 1:
            return False, "已是最高档位"

        # 3. 响应为空/错误 → 升级
        if not response.success or not response.content:
            return True, "响应失败或内容为空"

        # 4. 置信度 < 阈值 → 升级
        threshold = self._config.cascade_confidence_threshold
        if response.confidence < threshold:
            return True, f"置信度{response.confidence:.2f} < 阈值{threshold:.2f}"

        # 5. 质量检查不通过 → 升级
        quality_passed, _, quality_reason = self._validate_response_quality(response, task_type)
        if not quality_passed:
            return True, f"质量检查不通过: {quality_reason}"

        return False, f"置信度{response.confidence:.2f} >= 阈值{threshold:.2f}，无需升级"

    # -------------------------------------------------------------------------
    # NVIDIA 本地模型支持（GB300 Blackwell Ultra）
    # -------------------------------------------------------------------------

    async def _try_nvidia_local(
        self,
        message: str,
        task_type: TaskType,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        images: list[str] | None,
    ) -> LLMResponse:
        """尝试调用 NVIDIA Agent Toolkit 本地模型（GB300 Blackwell Ultra）

        当本地模型可用时，优先使用本地推理以获得最低延迟和最高安全性。
        失败时返回 success=False，由上层路由到云端 Provider。

        Args:
            message: 用户消息
            task_type: 任务类型
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token
            images: base64 图片列表（视觉任务）

        Returns:
            LLMResponse：成功时返回本地模型结果，失败时返回 success=False
        """
        try:
            from ai.nvidia_agent_adapter import ModelType, nvidia_adapter
        except ImportError:
            return LLMResponse(success=False, error="NVIDIA Adapter 未安装")

        if not nvidia_adapter.is_available():
            return LLMResponse(success=False, error="NVIDIA 本地模型不可用")

        task_to_model = {
            TaskType.INTENT_CLASSIFICATION: ModelType.TEXT_FLASH,
            TaskType.SCENE_DESCRIPTION: ModelType.VISION if images else ModelType.TEXT_PRO,
            TaskType.EFFECT_PLANNING: ModelType.TEXT_PRO,
            TaskType.QUALITY_REVIEW: ModelType.TEXT_PRO,
            TaskType.FEEDBACK_ANALYSIS: ModelType.TEXT_FLASH,
            TaskType.PARAMETER_OPTIMIZATION: ModelType.CODE,
            TaskType.EFFECT_SEARCH: ModelType.TEXT_PRO,
            TaskType.GENERAL: ModelType.TEXT_PRO,
        }

        model_type = task_to_model.get(task_type, ModelType.TEXT_PRO)

        try:
            if images:
                result = await nvidia_adapter.vision_chat(
                    prompt=message,
                    images=images,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                result = await nvidia_adapter.chat(
                    prompt=message,
                    system_prompt=system_prompt,
                    model_type=model_type,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            if result.success:
                resp = LLMResponse(
                    content=result.content,
                    model=result.model,
                    provider="nvidia-local",
                    tokens_input=result.tokens_input,
                    tokens_output=result.tokens_output,
                    latency_ms=result.latency_ms,
                    success=True,
                    raw=result.raw,
                    tier=ModelTier.TIER_1_LOCAL_SPECIALIZED.value,
                    cost_usd=0.0,
                )
                self._update_tier_stats(ModelTier.TIER_1_LOCAL_SPECIALIZED, resp)
                self._stats["total_cost_usd"] += resp.cost_usd
                return resp
            else:
                resp = LLMResponse(
                    success=False,
                    provider="nvidia-local",
                    error=result.error,
                    latency_ms=result.latency_ms,
                    tier=ModelTier.TIER_1_LOCAL_SPECIALIZED.value,
                )
                self._update_tier_stats(ModelTier.TIER_1_LOCAL_SPECIALIZED, resp)
                return resp
        except Exception as e:
            self._logger.warning(f"NVIDIA 本地模型调用异常: {e}")
            resp = LLMResponse(
                success=False,
                provider="nvidia-local",
                error=str(e),
                tier=ModelTier.TIER_1_LOCAL_SPECIALIZED.value,
            )
            self._update_tier_stats(ModelTier.TIER_1_LOCAL_SPECIALIZED, resp)
            return resp

    # -------------------------------------------------------------------------
    # 双模型对抗审查（参考 cavekit）
    # -------------------------------------------------------------------------

    async def dual_model_review(
        self,
        content: str,
        review_prompt: str = "",
    ) -> tuple[LLMResponse, LLMResponse]:
        """
        双模型对抗审查 — 参考 cavekit 的双模型审查模式

        用两个不同模型分别审查同一内容，对比结果

        Args:
            content: 待审查内容
            review_prompt: 审查提示词

        Returns:
            (模型A审查结果, 模型B审查结果)
        """
        default_prompt = "审查以下内容的准确性、完整性和潜在问题。给出评分(0-1)和改进建议。"
        prompt = review_prompt or default_prompt

        # 模型 A：主模型
        result_a = await self.chat(
            f"{prompt}\n\n内容:\n{content}",
            system_prompt="你是严格的技术审查专家",
            temperature=0.2,
            use_compression=True,
        )

        # 模型 B：用不同温度模拟"不同视角"
        result_b = await self.chat(
            f"从相反角度审查以下内容，找出模型A可能遗漏的问题:\n\n{content}",
            system_prompt="你是逆向思维审查者，专门找反面问题",
            temperature=0.8,
            use_compression=True,
        )

        return result_a, result_b

    # -------------------------------------------------------------------------
    # 统计与监控
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """获取网关统计"""
        total = self._stats["total_requests"]
        success_count = self._stats["total_successes"]
        success_rate = (self._stats["total_successes"] / total * 100) if total > 0 else 0
        # B5 修复：平均延迟分母改为成功请求数（失败请求的延迟不应计入平均响应时间）
        avg_latency = (self._stats["total_latency_ms"] / success_count) if success_count > 0 else 0

        return {
            "total_requests": total,
            "success_rate": f"{success_rate:.1f}%",
            "total_tokens_input": self._stats["total_tokens_input"],
            "total_tokens_output": self._stats["total_tokens_output"],
            "avg_latency_ms": f"{avg_latency:.0f}",
            "total_cost_usd": round(self._stats["total_cost_usd"], 6),
            "tier_stats": self.get_tier_stats(),
            "providers": {
                name: {
                    "status": h.status.name,
                    "consecutive_failures": h.consecutive_failures,
                    "total_requests": h.total_requests,
                    "total_failures": h.total_failures,
                    "tier": h.tier.value if h.tier else None,
                    "total_cost_usd": round(h.total_cost_usd, 6),
                    "avg_latency_ms": round(h.avg_latency_ms, 0),
                }
                for name, h in self._provider_health.items()
            },
        }

    def get_usage_stats(self) -> dict[str, Any]:
        """获取使用统计信息（含分层统计）

        Returns:
            Dict[str, Any]: 完整的使用统计，包括各档位调用量、成本、延迟等
        """
        return self.get_stats()

    def get_health(self) -> dict[str, Any]:
        """获取 Provider 健康状态"""
        return {
            name: {
                "status": h.status.name,
                "last_success": h.last_success_time,
                "consecutive_failures": h.consecutive_failures,
            }
            for name, h in self._provider_health.items()
        }

    async def close(self) -> None:
        """关闭网关"""
        await self._close_http_client()
        self._logger.info("LLM 网关已关闭")


# -----------------------------------------------------------------------------
# 全局实例
# -----------------------------------------------------------------------------

llm_gateway = LLMGateway()


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------

async def chat(
    message: str,
    system_prompt: str = "",
    model: str = "",
    **kwargs,
) -> LLMResponse:
    """便捷聊天函数"""
    return await llm_gateway.chat(message, system_prompt, model, **kwargs)


async def chat_with_routing(
    message: str,
    task_type: TaskType = TaskType.GENERAL,
    system_prompt: str = "",
    **kwargs,
) -> LLMResponse:
    """便捷路由聊天函数"""
    return await llm_gateway.chat_with_routing(message, task_type, system_prompt, **kwargs)


async def chat_with_cascade(
    message: str,
    task_type: TaskType = TaskType.GENERAL,
    system_prompt: str = "",
    **kwargs,
) -> LLMResponse:
    """便捷级联路由聊天函数"""
    return await llm_gateway.chat_with_cascade(message, task_type, system_prompt, **kwargs)


def get_cascade_stats() -> dict[str, Any]:
    """获取级联路由统计"""
    return llm_gateway.get_cascade_stats()


def configure_gateway(config: LLMConfig) -> None:
    """配置全局网关"""
    llm_gateway.configure(config)


def configure_from_env() -> None:
    """从环境变量配置全局网关"""
    llm_gateway.configure_from_env()


def configure_providers_from_env() -> None:
    """从环境变量加载多Provider配置到全局网关"""
    llm_gateway.configure_providers_from_env()


# -----------------------------------------------------------------------------
# 多Provider便捷函数（VRS v2.0）
# -----------------------------------------------------------------------------

async def chat_vision(
    prompt: str,
    images: list[str],
    system_prompt: str = "",
    provider: str = "claude",
) -> LLMResponse:
    """VISION 多模态调用便捷函数。

    Args:
        prompt: 用户消息
        images: base64 编码的图片列表
        system_prompt: 系统提示词
        provider: 默认 ``claude``，可切到 ``gpt`` 使用 gpt-5.6-sol
    """
    return await llm_gateway.chat_with_provider(
        prompt,
        provider=provider,
        model_type="vision",
        system_prompt=system_prompt,
        images=images,
    )


async def chat_thinking(
    prompt: str,
    system_prompt: str = "",
    provider: str = "claude",
) -> LLMResponse:
    """深度推理调用便捷函数（默认 Claude opus-4-8）。"""
    return await llm_gateway.chat_with_provider(
        prompt,
        provider=provider,
        model_type="thinking",
        system_prompt=system_prompt,
    )


async def chat_code(
    prompt: str,
    system_prompt: str = "",
    provider: str = "gpt",
) -> LLMResponse:
    """代码生成调用便捷函数（默认 GPT gpt-5.6-luna）。"""
    return await llm_gateway.chat_with_provider(
        prompt,
        provider=provider,
        model_type="code",
        system_prompt=system_prompt,
    )


# -----------------------------------------------------------------------------
# 自测入口：加载 .env → 配置多Provider → 验证 VISION / THINKING 调用
# -----------------------------------------------------------------------------

def _load_dotenv_manual(override: bool = True) -> None:
    """无 python-dotenv 时的简易 .env 加载器。

    Args:
        override: 为 True 时强制以 .env 值覆盖已存在的系统环境变量。
            必须默认开启——否则陈旧的 Windows 系统环境变量（如旧版
            DUCKMISS_API_KEY）会覆盖 .env 中的正确密钥，导致 401。
            .env 是本项目 LLM 配置的唯一权威来源。
    """
    _load_dotenv_file(os.path.join(os.getcwd(), ".env"), override=override)


def _project_root() -> Path:
    """项目根目录：core/llm_gateway.py 的上上级（core/ → 根）"""
    return Path(__file__).resolve().parents[1]


def _load_dotenv_file(path: os.PathLike | str, override: bool = True) -> None:
    """加载指定 .env 风格文件到 os.environ（无 python-dotenv 依赖）。

    Args:
        path: .env 文件路径
        override: True 时以文件值覆盖已有环境变量，False 时仅填充未设置的变量。
    """
    env_path = os.fspath(path)
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value:
                if override:
                    os.environ[key] = value
                else:
                    os.environ.setdefault(key, value)


# -----------------------------------------------------------------------------
# Phase A: 深度推理升级（ThinkingUpgradePolicy）
# -----------------------------------------------------------------------------

@dataclass
class ThinkingBudget:
    """深度推理预算。"""

    max_rounds: int = 3
    max_tokens_per_round: int = 8000
    timeout_seconds: float = 300
    max_cost_usd: float = 0.5

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "ThinkingBudget":
        """从配置字典构造预算（H1：消费 core.config 的 thinking_upgrade 配置）。

        Args:
            cfg: thinking_upgrade 配置字典，可包含 max_rounds /
                max_tokens_per_round / timeout_seconds / max_cost_usd；
                兼容旧键名 max_cost_per_task_usd。

        Returns:
            ThinkingBudget: 读取到的预算，缺省字段回退到类默认值。
        """
        return cls(
            max_rounds=int(cfg.get("max_rounds", 3)),
            max_tokens_per_round=int(cfg.get("max_tokens_per_round", 8000)),
            timeout_seconds=float(cfg.get("timeout_seconds", 300)),
            max_cost_usd=float(
                cfg.get("max_cost_usd", cfg.get("max_cost_per_task_usd", 0.5))
            ),
        )


@dataclass
class ThinkingUpgradeDecision:
    """深度推理升级决策。"""

    should_upgrade: bool
    reason: str
    upgraded_task_type: str
    estimated_cost_usd: float
    budget: ThinkingBudget
    confidence_threshold: float = 0.85


@dataclass
class ThinkingRound:
    """单轮推理记录。"""

    round_index: int
    prompt: str
    response: str | None = None  # L1: 失败路径归一化为 ""
    self_check_result: str = ""
    passed: bool = False
    latency_ms: float = 0.0  # M10: 回答轮 + 审查轮耗时之和
    cost_usd: float = 0.0


@dataclass
class ThinkingTrace:
    """完整深度推理轨迹。"""

    original_prompt: str
    original_task_type: str
    decision: ThinkingUpgradeDecision
    rounds: list[ThinkingRound]
    final_answer: str | None = None  # L1: 失败路径归一化为 ""
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    error: str | None = None  # M4: partial / timeout / cost_capped / llm_call_failed
    context_keys: list[str] | None = None  # M7: 记录上下文键


# ThinkingUpgradePolicy 已拆出 (2026-08-14), 此处 re-export 保持向后兼容:
#   from core.llm_gateway import ThinkingUpgradePolicy, chat_with_thinking_upgrade
from core.thinking_upgrade_policy import (  # noqa: E402,F401
    ThinkingUpgradePolicy,
    chat_with_thinking_upgrade,
)
