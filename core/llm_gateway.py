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
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


def _sanitize_log_text(text: str) -> str:
    """日志脱敏：移除或掩码敏感信息。

    脱敏范围：
    - Authorization: Bearer <token>
    - api_key=<value> / apikey=<value>
    - sk- 开头的 API Key
    - 各类 token / secret / password 值

    Args:
        text: 原始日志文本

    Returns:
        脱敏后的文本
    """
    if not text:
        return text

    result = text

    # Authorization: Bearer xxx
    result = re.sub(
        r'(?i)(bearer\s+)[A-Za-z0-9_\-\.]{6,}',
        r'\1***REDACTED***',
        result,
    )

    # api_key=xxx / apikey=xxx / apiKey=xxx
    result = re.sub(
        r'(?i)(api[_-]?key\s*[=:]\s*)[A-Za-z0-9_\-]{6,}',
        r'\1***REDACTED***',
        result,
    )

    # sk- 开头的 OpenAI 风格密钥
    result = re.sub(
        r'sk-[A-Za-z0-9_\-]{20,}',
        'sk-***REDACTED***',
        result,
    )

    # password=xxx / secret=xxx / token=xxx
    for keyword in ['password', 'secret', 'token']:
        result = re.sub(
            rf'(?i)({keyword}\s*[=:]\s*)[A-Za-z0-9_\-{{}}!@#$%^&*()+=\.]+',
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


class ProviderStatus(Enum):
    """Provider 健康状态"""
    HEALTHY = auto()
    DEGRADED = auto()
    UNAVAILABLE = auto()


@dataclass
class LLMConfig:
    """LLM 配置"""
    base_url: str = "http://localhost:5273/v1"
    api_key: str = ""
    default_model: str = "auto"
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_ms: int = 1000
    enable_compression: bool = True
    enable_fallback: bool = True

    # 任务→模型路由表
    model_routing: Dict[TaskType, str] = field(default_factory=lambda: {
        TaskType.INTENT_CLASSIFICATION: "auto",
        TaskType.SCENE_DESCRIPTION: "auto",
        TaskType.EFFECT_PLANNING: "auto",
        TaskType.QUALITY_REVIEW: "auto",
        TaskType.FEEDBACK_ANALYSIS: "auto",
        TaskType.PARAMETER_OPTIMIZATION: "auto",
        TaskType.EFFECT_SEARCH: "auto",
        TaskType.GENERAL: "auto",
    })

    # 降级 Provider 列表
    fallback_providers: List[Dict[str, str]] = field(default_factory=list)

    # 多Provider配置（VRS v2.0 任务级路由）
    # 格式: {"claude": {"base_url":"...", "api_key":"...",
    #          "models": {"vision":"...", "thinking":"...", "fast":"..."}}, ...}
    providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str = ""
    model: str = ""
    provider: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    latency_ms: float = 0.0
    success: bool = False
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Provider 健康状态跟踪"""
    name: str
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    last_success_time: float = 0.0
    last_error: str = ""
    total_requests: int = 0
    total_failures: int = 0


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
TASK_PROVIDER_MAP: Dict[TaskType, Tuple[str, str]] = {
    TaskType.SCENE_DESCRIPTION: ("claude", "vision"),       # 场景描述 → Claude VISION
    TaskType.EFFECT_PLANNING: ("claude", "thinking"),       # 效果规划 → Claude opus
    TaskType.INTENT_CLASSIFICATION: ("claude", "fast"),     # 意图分类 → Claude haiku
    TaskType.QUALITY_REVIEW: ("claude", "thinking"),        # 质量审查 → Claude opus
    TaskType.PARAMETER_OPTIMIZATION: ("claude", "default"), # 参数优化 → Claude sonnet
    TaskType.FEEDBACK_ANALYSIS: ("claude", "fast"),         # 反馈分析 → Claude haiku
    TaskType.EFFECT_SEARCH: ("claude", "fast"),             # 效果搜索 → Claude haiku
    TaskType.GENERAL: ("claude", "default"),                # 通用 → Claude sonnet
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

    def __init__(self, config: Optional[LLMConfig] = None):
        self._logger = logging.getLogger(f"{__name__}.LLMGateway")
        self._config = config or LLMConfig()
        self._compressor = TokenCompressor()
        self._provider_health: Dict[str, ProviderHealth] = {}
        self._stats = {
            "total_requests": 0,
            "total_successes": 0,
            "total_failures": 0,
            "total_tokens_input": 0,
            "total_tokens_output": 0,
            "total_latency_ms": 0.0,
        }
        self._http_client = None

        # 初始化 Provider 健康状态
        self._init_provider_health()

    def _init_provider_health(self) -> None:
        """初始化 Provider 健康跟踪"""
        primary_name = self._extract_provider_name(self._config.base_url)
        self._provider_health[primary_name] = ProviderHealth(name=primary_name)

        for fb in self._config.fallback_providers:
            name = self._extract_provider_name(fb.get("base_url", ""))
            if name not in self._provider_health:
                self._provider_health[name] = ProviderHealth(name=name)

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
        """从环境变量加载配置"""
        base_url = os.environ.get("AEKV_LLM_BASE_URL",
                                   os.environ.get("OPENAI_BASE_URL",
                                   os.environ.get("DUCK_MISS_BASE_URL", "")))
        api_key = os.environ.get("AEKV_LLM_API_KEY",
                                  os.environ.get("OPENAI_API_KEY",
                                  os.environ.get("DUCK_MISS_API_KEY", "")))
        model = os.environ.get("AEKV_LLM_MODEL",
                                os.environ.get("DUCK_MISS_DEFAULT_MODEL", "auto"))

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

    def configure_providers_from_env(self) -> None:
        """从环境变量加载多Provider配置（并行于 configure_from_env）。

        加载 Claude / GPT / 图像生成 / DeepSeek / 豆包 五个 Provider，
        每个 Provider 包含 base_url、api_key 与多档位模型映射。
        缺失 API Key 的 Provider 自动跳过，不影响其他 Provider。
        """
        providers: Dict[str, Dict[str, Any]] = {}

        # Claude Provider（VISION/深度推理主力）
        claude_key = os.environ.get("DUCKMISS_API_KEY", "") or os.environ.get("AEKV_LLM_API_KEY", "")
        if claude_key:
            providers["claude"] = {
                "base_url": os.environ.get("DUCKMISS_BASE_URL", "https://duckmiss.site/v1"),
                "api_key": claude_key,
                "models": {
                    "vision": os.environ.get("DUCKMISS_VISION_MODEL", "claude-sonnet-4-6"),
                    "thinking": os.environ.get("DUCKMISS_THINKING_MODEL", "claude-opus-4-8"),
                    "fast": os.environ.get("DUCKMISS_FAST_MODEL", "claude-haiku-4-5-20251001"),
                    "default": os.environ.get("DUCKMISS_DEFAULT_MODEL", "claude-sonnet-4-6"),
                },
            }

        # GPT Provider（代码生成/视觉备用）
        gpt_key = os.environ.get("GPT_GATEWAY_API_KEY", "")
        if gpt_key:
            providers["gpt"] = {
                "base_url": os.environ.get("GPT_GATEWAY_BASE_URL", "https://duckmiss.site/v1"),
                "api_key": gpt_key,
                "models": {
                    "vision": os.environ.get("GPT_GATEWAY_VISION_MODEL", "gpt-5.6-sol"),
                    "code": os.environ.get("GPT_GATEWAY_CODE_MODEL", "gpt-5.6-luna"),
                    "reasoning": os.environ.get("GPT_GATEWAY_REASONING_MODEL", "gpt-5.6-terra"),
                    "default": "gpt-5.6",
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

        # DeepSeek Provider（文本降级）
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if ds_key:
            providers["deepseek"] = {
                "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
                "api_key": ds_key,
                "models": {"default": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")},
            }

        # 豆包 Provider（文本降级）
        db_key = os.environ.get("DOUBAO_API_KEY", "")
        if db_key:
            providers["doubao"] = {
                "base_url": os.environ.get("DOUBAO_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"),
                "api_key": db_key,
                "models": {"default": os.environ.get("DOUBAO_MODEL", "deepseek-v4-pro-260425")},
            }

        self._config.providers = providers
        # 初始化每个 Provider 的健康状态
        for name in providers:
            if name not in self._provider_health:
                self._provider_health[name] = ProviderHealth(name=name)

        self._logger.info(
            f"已加载 {len(providers)} 个Provider: {list(providers.keys())}"
        )

    def is_available(self) -> bool:
        """检查 LLM 网关是否可用"""
        return bool(self._config.base_url and self._config.api_key)

    # -------------------------------------------------------------------------
    # HTTP 客户端
    # -------------------------------------------------------------------------

    async def _get_http_client(self):
        """获取 HTTP 客户端（懒加载）"""
        if self._http_client is None:
            try:
                import aiohttp
                self._http_client = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(
                        total=self._config.timeout_seconds
                    )
                )
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
    # -------------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        system_prompt: str = "",
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        use_compression: Optional[bool] = None,
        images: Optional[List[str]] = None,
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
            content_parts: List[Dict[str, Any]] = [{"type": "text", "text": message}]
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
        )

        # 降级处理
        if not response.success and self._config.enable_fallback:
            for fb in self._config.fallback_providers:
                fb_url = fb.get("base_url", "")
                fb_key = fb.get("api_key", "")
                if not fb_url or not fb_key:
                    continue

                self._logger.warning(f"主 Provider 失败，尝试降级: {fb_url}")
                response = await self._call_provider(
                    fb_url, fb_key, model,
                    messages, temperature, max_tokens,
                )
                if response.success:
                    break

        # 解压响应
        if response.success and should_compress:
            response.content = self._compressor.decompress_response(response.content)

        return response

    async def chat_with_routing(
        self,
        message: str,
        task_type: TaskType = TaskType.GENERAL,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        根据任务类型自动路由到最优模型的聊天请求

        Args:
            message: 用户消息
            task_type: 任务类型（决定模型选择）
            system_prompt: 系统提示词
            images: base64 图片列表，用于多模态调用（自动路由到 VISION 模型）

        路由策略：
            - 若 ``LLMConfig.providers`` 非空（多Provider模式）：按
              ``TASK_PROVIDER_MAP`` 选择 Provider 与模型档位，失败则降级
              到原有单 Provider 逻辑。
            - 否则：使用 ``model_routing`` 表选模型，走单 Provider 调用。
        """
        # 任务类型→温度调整（多Provider与单Provider路径共用）
        if task_type == TaskType.INTENT_CLASSIFICATION:
            temperature = 0.1
        elif task_type == TaskType.EFFECT_PLANNING:
            temperature = 0.5
        elif task_type == TaskType.QUALITY_REVIEW:
            temperature = 0.2
        elif images is not None and task_type == TaskType.SCENE_DESCRIPTION:
            # 视觉理解任务用低温度保证输出稳定
            temperature = min(temperature, 0.3)

        # 多Provider路由：优先按 TASK_PROVIDER_MAP 调用
        if self._config.providers:
            provider, model_type = TASK_PROVIDER_MAP.get(
                task_type, ("claude", "default")
            )
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
                    return response
                # 失败 → 降级到原有单 Provider 逻辑
                self._logger.warning(
                    f"多Provider路由失败(provider={provider}, "
                    f"model_type={model_type})，降级到单Provider: "
                    f"{_sanitize_log_text(response.error)}"
                )
            except Exception as e:
                self._logger.warning(
                    f"多Provider路由异常，降级到单Provider: {e}"
                )

        # 原有单 Provider 逻辑（向后兼容）
        model = self._config.model_routing.get(task_type, self._config.default_model)
        return await self.chat(
            message=message,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
        )

    async def chat_with_provider(
        self,
        prompt: str,
        provider: str,
        model_type: str = "default",
        system_prompt: str = "",
        images: Optional[List[str]] = None,
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

        p = providers[provider]
        models = p.get("models", {})
        model = models.get(model_type, models.get("default", "auto"))

        # 临时切换主配置，使 _call_provider_internal 复用现有调用链路
        old_base = self._config.base_url
        old_key = self._config.api_key
        old_model = self._config.default_model
        try:
            self._config.base_url = p["base_url"]
            self._config.api_key = p["api_key"]
            self._config.default_model = model
            response = await self._call_provider_internal(
                prompt=prompt,
                model=model,
                system_prompt=system_prompt,
                images=images,
                temperature=temperature,
                max_tokens=max_tokens,
                provider_name=provider,
            )
            return response
        finally:
            self._config.base_url = old_base
            self._config.api_key = old_key
            self._config.default_model = old_model

    async def _call_provider_internal(
        self,
        prompt: str,
        model: str,
        system_prompt: str,
        images: Optional[List[str]],
        temperature: float,
        max_tokens: int,
        provider_name: str = "",
    ) -> LLMResponse:
        """内部辅助：构建 messages 并调用 ``_call_provider``。

        复用 ``chat`` 的多模态消息构建与 Token 压缩逻辑，但直接按
        ``self._config.base_url`` / ``api_key`` 调用，便于 ``chat_with_provider``
        临时切换配置后复用。
        """
        has_images = bool(images)
        should_compress = self._config.enable_compression

        sys_prompt = system_prompt
        user_prompt = prompt
        if should_compress:
            sys_prompt = self._compressor.compress_system(system_prompt)
            if not has_images:
                user_prompt = self._compressor.compress_prompt(prompt)
                user_prompt += self._compressor.get_compression_suffix()

        messages: List[Dict[str, Any]] = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        if has_images:
            content_parts: List[Dict[str, Any]] = [
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
            self._config.base_url,
            self._config.api_key,
            model,
            messages,
            temperature,
            max_tokens,
        )

        # 标注 Provider 友好名（_call_provider 默认用 hostname）
        if provider_name and response.provider != provider_name:
            response.provider = provider_name

        if response.success and should_compress:
            response.content = self._compressor.decompress_response(response.content)

        return response

    async def _call_provider(
        self,
        base_url: str,
        api_key: str,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """调用单个 Provider"""
        provider_name = self._extract_provider_name(base_url)
        health = self._provider_health.get(provider_name, ProviderHealth(name=provider_name))

        if health.status == ProviderStatus.UNAVAILABLE:
            return LLMResponse(
                success=False,
                provider=provider_name,
                error=f"Provider {provider_name} 不可用（连续失败 {health.consecutive_failures} 次）"
            )

        client = await self._get_http_client()
        if client is None:
            return LLMResponse(success=False, error="HTTP 客户端不可用")

        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        start_time = time.time()
        self._stats["total_requests"] += 1
        health.total_requests += 1

        for attempt in range(self._config.max_retries):
            try:
                async with client.post(url, json=payload, headers=headers) as resp:
                    latency_ms = (time.time() - start_time) * 1000

                    if resp.status != 200:
                        error_text = await resp.text()
                        safe_error_text = _sanitize_log_text(error_text[:200])
                        self._logger.warning(
                            f"LLM 调用失败 (HTTP {resp.status}): {safe_error_text}"
                        )
                        if attempt < self._config.max_retries - 1:
                            await asyncio.sleep(self._config.retry_delay_ms / 1000)
                            continue

                        health.consecutive_failures += 1
                        health.total_failures += 1
                        health.last_error = f"HTTP {resp.status}: {safe_error_text}"

                        if health.consecutive_failures >= 3:
                            health.status = ProviderStatus.UNAVAILABLE

                        self._stats["total_failures"] += 1
                        return LLMResponse(
                            success=False,
                            provider=provider_name,
                            latency_ms=latency_ms,
                            error=f"HTTP {resp.status}: {safe_error_text}",
                        )

                    data = await resp.json()

                    content = ""
                    if data.get("choices"):
                        content = data["choices"][0].get("message", {}).get("content", "")

                    usage = data.get("usage", {})
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    used_model = data.get("model", model)

                    # 更新健康状态
                    health.status = ProviderStatus.HEALTHY
                    health.consecutive_failures = 0
                    health.last_success_time = time.time()

                    # 更新统计
                    self._stats["total_successes"] += 1
                    self._stats["total_tokens_input"] += tokens_in
                    self._stats["total_tokens_output"] += tokens_out
                    self._stats["total_latency_ms"] += latency_ms

                    return LLMResponse(
                        content=content,
                        model=used_model,
                        provider=provider_name,
                        tokens_input=tokens_in,
                        tokens_output=tokens_out,
                        latency_ms=latency_ms,
                        success=True,
                        raw=data,
                    )

            except asyncio.TimeoutError:
                self._logger.warning(f"LLM 调用超时 (尝试 {attempt + 1}/{self._config.max_retries})")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay_ms / 1000)
                    continue

                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_error = "Timeout"
                self._stats["total_failures"] += 1
                return LLMResponse(
                    success=False,
                    provider=provider_name,
                    error=f"请求超时 ({self._config.timeout_seconds}s)",
                )

            except Exception as e:
                self._logger.error(f"LLM 调用异常: {e}")
                if attempt < self._config.max_retries - 1:
                    await asyncio.sleep(self._config.retry_delay_ms / 1000)
                    continue

                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_error = str(e)
                self._stats["total_failures"] += 1
                return LLMResponse(
                    success=False,
                    provider=provider_name,
                    error=str(e),
                )

        return LLMResponse(success=False, error="重试次数耗尽")

    # -------------------------------------------------------------------------
    # 双模型对抗审查（参考 cavekit）
    # -------------------------------------------------------------------------

    async def dual_model_review(
        self,
        content: str,
        review_prompt: str = "",
    ) -> Tuple[LLMResponse, LLMResponse]:
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

    def get_stats(self) -> Dict[str, Any]:
        """获取网关统计"""
        total = self._stats["total_requests"]
        success_rate = (self._stats["total_successes"] / total * 100) if total > 0 else 0
        avg_latency = (self._stats["total_latency_ms"] / total) if total > 0 else 0

        return {
            "total_requests": total,
            "success_rate": f"{success_rate:.1f}%",
            "total_tokens_input": self._stats["total_tokens_input"],
            "total_tokens_output": self._stats["total_tokens_output"],
            "avg_latency_ms": f"{avg_latency:.0f}",
            "providers": {
                name: {
                    "status": h.status.name,
                    "consecutive_failures": h.consecutive_failures,
                    "total_requests": h.total_requests,
                    "total_failures": h.total_failures,
                }
                for name, h in self._provider_health.items()
            },
        }

    def get_health(self) -> Dict[str, Any]:
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
    images: List[str],
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

def _load_dotenv_manual() -> None:
    """无 python-dotenv 时的简易 .env 加载器。"""
    env_path = os.path.join(os.getcwd(), ".env")
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
            # 跳过空值
            if value:
                os.environ.setdefault(key, value)


if __name__ == "__main__":
    import asyncio
    import base64
    import io

    def _make_test_jpeg_b64() -> Optional[str]:
        """生成 8x8 白色 JPEG 的 base64，用于 VISION 自测。

        依赖 Pillow；缺失时返回 None，VISION 测试将被跳过。
        """
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            return None
        img = Image.new("RGB", (8, 8), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    async def _main() -> None:
        # 加载 .env
        try:
            from dotenv import load_dotenv  # type: ignore
            load_dotenv()
        except ImportError:
            _load_dotenv_manual()

        # 配置主 Provider + 多 Provider
        llm_gateway.configure_from_env()
        llm_gateway.configure_providers_from_env()

        print("=" * 60)
        print("已配置 Provider 清单")
        print("=" * 60)
        for name, cfg in llm_gateway._config.providers.items():
            models = list(cfg.get("models", {}).keys())
            print(f"  [{name:10s}] base_url={cfg.get('base_url')}")
            print(f"              models={models}")

        print("\nProvider 健康状态:")
        for name, h in llm_gateway.get_health().items():
            print(f"  [{name:10s}] status={h['status']}")

        # 测试 THINKING 调用
        print("\n" + "=" * 60)
        print("测试 chat_thinking() — 深度推理")
        print("=" * 60)
        resp = await chat_thinking(
            "1+1=?  请只输出最终数字。",
            system_prompt="你是数学助手，必须简短回答。",
        )
        print(f"  success : {resp.success}")
        print(f"  provider: {resp.provider}")
        print(f"  model   : {resp.model}")
        print(f"  latency : {resp.latency_ms:.0f} ms")
        print(f"  tokens  : in={resp.tokens_input} out={resp.tokens_output}")
        if resp.success:
            print(f"  content : {resp.content[:200]}")
        else:
            print(f"  error   : {_sanitize_log_text(resp.error)}")

        # 测试 VISION 调用
        print("\n" + "=" * 60)
        print("测试 chat_vision() — 多模态（8x8 白色 JPEG）")
        print("=" * 60)
        test_jpeg = _make_test_jpeg_b64()
        if test_jpeg is None:
            print("  跳过：未安装 Pillow，无法生成测试图片")
        else:
            resp = await chat_vision(
                "请用一句话描述这张图片的颜色和内容。",
                images=[test_jpeg],
                system_prompt="你是图像分析专家，请简短回答。",
            )
            print(f"  success : {resp.success}")
            print(f"  provider: {resp.provider}")
            print(f"  model   : {resp.model}")
            print(f"  latency : {resp.latency_ms:.0f} ms")
            print(f"  tokens  : in={resp.tokens_input} out={resp.tokens_output}")
            if resp.success:
                print(f"  content : {resp.content[:200]}")
            else:
                print(f"  error   : {_sanitize_log_text(resp.error)}")

        # 统计
        print("\n" + "=" * 60)
        print("网关统计:")
        print("=" * 60)
        stats = llm_gateway.get_stats()
        print(f"  total_requests: {stats['total_requests']}")
        print(f"  success_rate  : {stats['success_rate']}")
        print(f"  avg_latency_ms: {stats['avg_latency_ms']}")

        await llm_gateway.close()

    asyncio.run(_main())
