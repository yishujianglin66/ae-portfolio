"""AI Planner Service — 通过 core/llm_gateway.py 统一网关调用 LLM 解析自然语言指令。

将中文自然语言命令解析为结构化参数（效果名 / 颜色 / 强度 / 图层 / 风格 / 意图），
供 API 层（/api/v1/ai/plan）和编排层使用。

设计要点：
- 所有 LLM 调用必须经 ``core/llm_gateway.py`` 网关，禁止直连 Provider HTTP API
- 任务类型为 ``TaskType.INTENT_CLASSIFICATION``（意图识别 + 参数提取）
- LLM 不可用时抛出 ``LLMUnavailableError``，由上层返回 503
- 异步优先：所有 I/O 方法为 ``async def``
- 日志输出经过 ``_sanitize_log_text()`` 脱敏处理

用法示例::

    from src.services.ai_planner import AIPlannerService

    service = AIPlannerService()
    try:
        result = await service.plan("给主角加一个红色发光效果，强度 0.8")
        # result = {
        #     "intent": "apply_effect",
        #     "params": {
        #         "effect_name": "发光",
        #         "color": "red",
        #         "intensity": 0.8,
        #         "target_layer": "主角",
        #         "style": None,
        #     },
        #     "raw_response": "{ ... }",
        # }
    except LLMUnavailableError:
        # 上层返回 503
        ...
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from loguru import logger

from ..config import settings

# ============================================================
# 系统提示词 — 意图识别 + 参数提取
# ============================================================

AI_PLANNER_SYSTEM_PROMPT = """你是 AE 视频制作流水线的意图识别与参数提取助手。

任务：将用户的中文自然语言命令解析为结构化 JSON，用于驱动 AE 效果自动化。

## 输出 JSON Schema（必须严格遵循）：
{
  "intent": "apply_effect | remove_effect | adjust_param | query_status | pipeline_plan | other",
  "params": {
    "effect_name": "效果名（中文/英文，如：发光/Glow、色彩校正/Color Correction、粒子/Particular）",
    "color": "颜色（如：red、#FF0000、蓝色）或 null",
    "intensity": "强度数值 0.0-1.0 或 null",
    "target_layer": "目标图层名或描述（如：主角、背景、字幕层）或 null",
    "style": "视觉风格（如：电影感、漫画风、复古）或 null",
    "duration_seconds": "持续时间（秒）或 null",
    "extra": { /* 其他补充参数 */ }
  }
}

## 解析规则：
1. intent 必须是上述枚举之一
2. 缺失字段填 null，不要编造
3. 颜色优先返回英文标准色名或 #RRGGBB
4. 强度若用户未给出，根据语义给默认值（如 "强烈" → 0.9，"轻微" → 0.2）
5. target_layer 若未指明，填 null（由后续图层选择器决定）
6. 只输出 JSON，不要其他文字、不要 markdown 代码块
"""


AI_PLANNER_USER_TEMPLATE = """用户命令：{user_query}

视频文件路径：{video_path}

请输出结构化 JSON。"""


# ============================================================
# 工具函数
# ============================================================

def _extract_json(text: str) -> dict[str, Any]:
    """从 LLM 响应中提取 JSON（兼容 markdown 代码块和裸 JSON）。"""
    if not text:
        return {}

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"AIPlannerService: 无法从响应中提取 JSON: {text[:200]!r}")
    return {}


def _sanitize_text(text: str) -> str:
    """对日志文本进行脱敏处理（掩码 API Key / Bearer Token）。"""
    try:
        from core.llm_gateway import _sanitize_log_text
        return _sanitize_log_text(text)
    except ImportError:
        return text


# ============================================================
# AIPlannerService
# ============================================================

class AIPlannerService:
    """AI 规划服务 — 通过 LLM 网关解析自然语言到结构化参数。

    所有 LLM 调用通过 ``core.llm_gateway.llm_gateway`` 单例完成。
    若网关未配置或不可用，``plan()`` 抛出 ``LLMUnavailableError``。
    """

    def __init__(self, gateway: Any | None = None) -> None:
        """初始化服务。

        Args:
            gateway: 可选的 LLM 网关实例（用于测试注入）。
                默认使用 ``core.llm_gateway.llm_gateway`` 全局单例。
        """
        self._gateway = gateway

    # ------------------------------------------------------------------
    # 网关获取
    # ------------------------------------------------------------------

    def _get_gateway(self):
        """获取已配置的 LLM 网关实例，未配置返回 None。"""
        if self._gateway is not None:
            return self._gateway

        try:
            from core.llm_gateway import llm_gateway
        except ImportError:
            logger.debug("core.llm_gateway 不可用，AIPlannerService 无法调用 LLM")
            return None

        if not llm_gateway.is_available():
            try:
                cfg = settings.get_llm_gateway_config()
                if cfg.base_url and cfg.api_key:
                    llm_gateway.configure(cfg)
            except Exception as exc:  # noqa: BLE001
                logger.debug(f"AIPlannerService: 网关配置注入失败: {_sanitize_text(str(exc))}")

        return llm_gateway if llm_gateway.is_available() else None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def plan(
        self,
        user_query: str,
        video_path: str = "",
    ) -> dict[str, Any]:
        """解析自然语言命令为结构化参数。

        Args:
            user_query: 用户的中文自然语言命令
            video_path: 关联的视频文件路径（可选，会传给 LLM 作为上下文）

        Returns:
            ``{"intent": str, "params": dict, "raw_response": str}``

        Raises:
            LLMUnavailableError: LLM 网关未配置或所有 Provider 不可用
        """
        from core.llm_gateway import LLMUnavailableError, TaskType

        gateway = self._get_gateway()
        if gateway is None:
            logger.warning("AIPlannerService: LLM 网关不可用")
            raise LLMUnavailableError(
                "LLM 网关未配置（缺少 AEKV_LLM_BASE_URL / AEKV_LLM_API_KEY）"
            )

        prompt = AI_PLANNER_USER_TEMPLATE.format(
            user_query=user_query,
            video_path=video_path or "(未提供)",
        )

        logger.info(
            f"AIPlannerService: 调用 LLM 网关解析意图 (query={user_query[:50]!r})"
        )

        response = await gateway.chat_with_routing(
            message=prompt,
            task_type=TaskType.INTENT_CLASSIFICATION,
            system_prompt=AI_PLANNER_SYSTEM_PROMPT,
        )

        if not response.success:
            logger.warning(
                f"AIPlannerService: LLM 调用失败: {_sanitize_text(response.error)}"
            )
            raise LLMUnavailableError(
                f"LLM 调用失败: {response.error}"
            )

        parsed = _extract_json(response.content)
        intent = self._normalize_intent(parsed.get("intent"))
        params = self._normalize_params(parsed.get("params", {}))

        return {
            "intent": intent,
            "params": params,
            "raw_response": response.content,
        }

    # ------------------------------------------------------------------
    # 输出归一化
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_intent(raw: Any) -> str:
        """归一化 intent 字段为枚举字符串。"""
        valid_intents = {
            "apply_effect", "remove_effect", "adjust_param",
            "query_status", "pipeline_plan", "other",
        }
        if isinstance(raw, str) and raw.lower() in valid_intents:
            return raw.lower()
        return "other"

    @staticmethod
    def _normalize_params(raw: Any) -> dict[str, Any]:
        """归一化 params 字段，确保必要键存在。"""
        if not isinstance(raw, dict):
            raw = {}

        def _opt_str(key: str) -> str | None:
            v = raw.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return s or None

        def _opt_float(key: str) -> float | None:
            v = raw.get(key)
            if v is None:
                return None
            try:
                f = float(v)
                return f
            except (TypeError, ValueError):
                return None

        def _opt_dict(key: str) -> dict[str, Any]:
            v = raw.get(key)
            return v if isinstance(v, dict) else {}

        return {
            "effect_name": _opt_str("effect_name"),
            "color": _opt_str("color"),
            "intensity": _opt_float("intensity"),
            "target_layer": _opt_str("target_layer"),
            "style": _opt_str("style"),
            "duration_seconds": _opt_float("duration_seconds"),
            "extra": _opt_dict("extra"),
        }
