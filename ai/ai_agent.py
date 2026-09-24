#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI Agent - M3助手的多模型协作层
=============================

支持 DeepSeek V4 和 豆包 双模型调用。

策略升级：效果优先（默认Pro模型）
- 所有核心方法默认使用 V4-Pro (1.6T参数) 或 豆包Pro
- 仅明确指定 flash 时才降级
- 集成 model_router 智能路由
- 职场学习类任务自动使用豆包模型

调用方式:
    from ai_agent import V4Agent
    
    agent = V4Agent()
    result = agent.analyze("分析项目架构")      # Pro
    answer = agent.qa("知识库里怎么用Glow效果")   # Pro (默认升级)
    answer = agent.qa("简单问题", use_flash=True) # Flash (显式指定)
    
    # 豆包模型（职场学习专用）
    result = agent.career_analysis("今天工作内容")  # 自动使用豆包Pro
    
    # 新模型支持
    result = agent.think_deeply("复杂推理问题")    # 深度思考模型
    code = agent.generate_code("写个排序算法")      # 代码生成模型
    text = agent.translate("Hello", "中文")        # 翻译模型
"""

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


# 加载项目根目录 .env / .env.doubao 配置到环境变量
# (2026-08-15 修复: 原逻辑只加载 ai/.env.doubao — 该文件不存在,
#  而密钥实际在项目根 .env/.env.doubao, 导致渲染子进程内
#  "未检测到 API Key"、LLM 分镜退化为规则弧段)
def _load_env_files() -> None:
    _root = Path(__file__).resolve().parent.parent
    for _name in (".env", ".env.doubao"):
        _p = _root / _name
        if not _p.exists():
            continue
        try:
            with open(_p, "r", encoding="utf-8", errors="replace") as _f:
                for line in _f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, _, value = line.partition("=")
                        key, value = key.strip(), value.strip()
                        if key and value and key not in os.environ:
                            os.environ[key] = value
        except Exception as _env_err:  # noqa: BLE001
            logger.warning(f"[ai_agent] 加载 {_p.name} 失败: {_env_err}")


# 注意: _load_env_files 在 logger 就绪后调用

try:
    import requests
except ImportError:
    # 不在导入期 sys.exit(1)：否则任何 import 本模块的上层
    # （api_server / style_copy / 测试套件）会在收集阶段直接崩溃，
    # 连带整个 pytest 运行以 INTERNALERROR 终止。
    # 改为标记不可用，仅在真正发起请求时再报错（运行时失败，而非导入期）。
    requests = None  # type: ignore[assignment]
    REQUESTS_AVAILABLE = False
    print(
        "[ai_agent] 警告: 未安装 requests，网络相关功能将不可用；"
        "请运行 `py -3.11 -m pip install requests`"
    )
else:
    REQUESTS_AVAILABLE = True

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("ai_agent")

_load_env_files()

try:
    from model_router import TaskCategory, get_model_name, get_model_provider, select_for_prompt, select_model
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False

# DeepSeek V4 API配置
API_BASE = "https://api.deepseek.com"
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"


def _log_llm_cost(provider: str, action: str, usage: dict, cost_cny: float,
                  **meta) -> None:
    """把一次 LLM 调用的成本写入 data/cost_log.jsonl (2026-09-19 接入生产)。

    此前只 print/logger.info, 数据落不了盘 —— cost_report 报表因此长期为空
    (评审 §五)。记账失败必须静默: 出片不能因为记账挂掉。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from core.cost_logger import log_usage
        log_usage(provider, action, usage, cost_cny, metadata=meta)
    except Exception:  # noqa: BLE001
        pass

# 豆包模型可用性检查
DOUBAO_AVAILABLE = False
try:
    from doubao_client import DoubaoClient
    from doubao_client import is_available as doubao_is_available
    if doubao_is_available():
        DOUBAO_AVAILABLE = True
except ImportError:
    pass

# 火山方舟(ARK)模型配置
ARK_AVAILABLE = False
ARK_API_KEY = os.environ.get("DOUBAO_API_KEY", "")
ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# 第三方中转站(DuckMiss)配置 - 兼容OpenAI API格式
DUCK_MISS_AVAILABLE = False
DUCK_MISS_API_KEY = os.environ.get("DUCK_MISS_API_KEY", "")
DUCK_MISS_BASE_URL = os.environ.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1")
DUCK_MISS_DEFAULT_MODEL = os.environ.get("DUCK_MISS_DEFAULT_MODEL", "claude-sonnet-4-6")
DUCK_MISS_PRO_MODEL = os.environ.get("DUCK_MISS_PRO_MODEL", "claude-opus-4-8")
DUCK_MISS_FAST_MODEL = os.environ.get("DUCK_MISS_FAST_MODEL", "claude-sonnet-4-6")
DUCK_MISS_VISION_MODEL = os.environ.get("DUCK_MISS_VISION_MODEL", "claude-sonnet-4-6")
if DUCK_MISS_API_KEY and DUCK_MISS_BASE_URL:
    DUCK_MISS_AVAILABLE = True

# GPT网关配置 - 复用DuckMiss Claude
GPT_GATEWAY_AVAILABLE = False
GPT_GATEWAY_API_KEY = os.environ.get("DUCK_MISS_API_KEY_BACKUP", "")
GPT_GATEWAY_BASE_URL = os.environ.get("DUCK_MISS_BASE_URL", "https://duckmiss.site/v1")
GPT_GATEWAY_PRO_MODEL = os.environ.get("GPT_GATEWAY_PRO_MODEL", "claude-opus-4-8")
GPT_GATEWAY_DEFAULT_MODEL = os.environ.get("GPT_GATEWAY_DEFAULT_MODEL", "claude-sonnet-4-6")
GPT_GATEWAY_FAST_MODEL = os.environ.get("GPT_GATEWAY_FAST_MODEL", "claude-sonnet-4-6")
GPT_GATEWAY_CODE_MODEL = os.environ.get("GPT_GATEWAY_CODE_MODEL", "claude-sonnet-4-6")
GPT_GATEWAY_VISION_MODEL = os.environ.get("GPT_GATEWAY_VISION_MODEL", "claude-sonnet-4-6")
if GPT_GATEWAY_API_KEY and GPT_GATEWAY_BASE_URL:
    GPT_GATEWAY_AVAILABLE = True

# ARK模型列表（2026-08-14 实测修正: 该账号仅开通 deepseek 系 + doubao code preview,
# doubao 视觉/思考/翻译系均 404, 已替换为实测可用的 deepseek 系模型）
ARK_MODELS = {
    "pro": "deepseek-v4-pro-260425",
    "flash": "deepseek-v4-flash-260425",
    "flash_ga": "deepseek-v4-flash-ga-260731",
    "doubao_pro": "deepseek-v4-pro-260425",          # 原 doubao-seed-2-1-pro 未开通
    "doubao_turbo": "deepseek-v4-flash-ga-260731",   # 原 doubao-seed-2-1-turbo 未开通
    "thinking": "deepseek-v4-pro-260425",            # 原 doubao thinking 未开通
    "code": "doubao-seed-2-0-code-preview-260215",   # 实测可用
    "translation": "deepseek-v4-flash-260425",       # 原 doubao translation 未开通
    "character": "deepseek-v4-pro-260425",           # 原 doubao character 未开通
    "evolving": "deepseek-v4-pro-260425",            # 原 doubao evolving 未开通
    # 视觉: 该账号无可用 ARK 视觉模型, analyze_image 直接降级 SiliconFlow
    "image_gen": "doubao-seedream-5-0-pro-260628",
    "video_gen": "doubao-seedance-1-5-pro-251215",
    "embedding": "doubao-embedding-large-text-250515",
}

# 模型单价表（per 1k tokens）— 显式映射，避免子串误匹配
MODEL_PRICING = {
    # DeepSeek V4 系列
    "deepseek-v4-flash": {"input": 0.001, "output": 0.002},
    "deepseek-v4-pro": {"input": 0.002, "output": 0.008},
    "deepseek-v4": {"input": 0.002, "output": 0.008},
    # 豆包 Seed 系列
    "doubao-seed-2-1-turbo": {"input": 0.001, "output": 0.002},
    "doubao-seed-2-1-pro": {"input": 0.004, "output": 0.008},
    "doubao-seed-2.1-turbo": {"input": 0.001, "output": 0.002},
    "doubao-seed-2.1-pro": {"input": 0.004, "output": 0.008},
    "doubao-seed-1-6-thinking": {"input": 0.004, "output": 0.012},
    "doubao-seed-code": {"input": 0.002, "output": 0.006},
    "doubao-seed-translation": {"input": 0.001, "output": 0.002},
    "doubao-seed-character": {"input": 0.002, "output": 0.006},
    "doubao-seed-evolving": {"input": 0.002, "output": 0.006},
    "doubao-vision": {"input": 0.003, "output": 0.008},
    "doubao-embedding": {"input": 0.0005, "output": 0.0},
    # Claude 系列（DuckMiss 中转）
    "claude-opus": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "claude-sonnet": {"input": 0.003, "output": 0.015},
    # Kimi
    "kimi-k3": {"input": 0.002, "output": 0.006},
    # 默认低价（turbo 级）
    "__default__": {"input": 0.001, "output": 0.002},
}

if ARK_API_KEY and ARK_API_KEY.startswith("ark-"):
    ARK_AVAILABLE = True

SYSTEM_PROMPT = """你是「M3助手的V4顾问」，负责深度推理分析。

项目背景:
- 项目: AE-Knowledge-Vault (企业级AE知识库系统)
- 规模: 777个文档, 35个工具, 11个软件引擎
- 技术栈: FastAPI + React + 工具链集成

工作原则:
1. 中文回答，结构化输出（Markdown）
2. 先给结论，再给推理过程
3. 涉及代码时给出可执行示例
4. 涉及架构时考虑成本和可维护性
5. 不知道的事情直接说，不要编造
"""

CAREER_SYSTEM_PROMPT = """你是「力王新能源职场学习助手」，专为闫起名提供职场学习和成长指导。

用户背景：
- 姓名：闫起名
- 公司：广东力王新能源股份有限公司
- 岗位：设备维护技术员（实习生）
- 背景：3+1校企合作，桂林信息科技学院智能制造工程专业
- 特点：性格开朗、善于沟通、当选班长

工作原则：
1. 中文回答，结构化输出（Markdown）
2. 先给结论，再给推理过程
3. 给出具体可执行的建议和计划
4. 语气温暖、鼓励、专业
5. 不知道的事情直接说，不要编造
"""


class V4Agent:
    """V4协作层 - 给M3助手用（效果优先策略）
    
    默认全部使用 Pro 模型，仅显式指定 flash 时才降级。
    
    支持多种API提供商（优先级从高到低）:
    1. DuckMiss中转站 (兼容OpenAI API)
    2. 火山方舟 ARK
    3. DeepSeek V4 (原生)
    """
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = API_BASE
        self.provider = "deepseek"

        # 2026-08-15: 提供方健康降级链 — DuckMiss 中转站实测已死
        # (连接重置), 但密钥仍在 .env 中 → 此前 V4Agent 锁死 DuckMiss
        # 导致全部 LLM 调用 403。原生 DeepSeek V4 (api.deepseek.com,
        # deepseek-v4-pro/flash) 实测 200 全通 → 默认首选。
        # 显式传入 api_key 视为权威 (跳过探测, 单测/上游指定场景);
        # 否则按 DeepSeek→ARK→DuckMiss 做真实对话探测(6s), 全部失败
        # 时保留 DeepSeek 原生兜底 (调用时自行报错)。
        if not api_key:
            _candidates = [
                ("deepseek", self.api_key, API_BASE, "deepseek-v4-flash"),
            ]
            if ARK_AVAILABLE and ARK_API_KEY:
                _candidates.append(("ark", ARK_API_KEY, ARK_BASE_URL,
                                    ARK_MODELS.get("flash", "deepseek-v4-flash-260425")))
            if DUCK_MISS_AVAILABLE and DUCK_MISS_API_KEY:
                _candidates.append(("duckmiss", DUCK_MISS_API_KEY,
                                    DUCK_MISS_BASE_URL, DUCK_MISS_DEFAULT_MODEL))
            for _prov, _key, _base, _probe_model in _candidates:
                if not _key:
                    continue
                if not self._provider_alive(_key, _base, _probe_model):
                    print(f"[V4Agent] {_prov} 探测失败, 降级下一提供方")
                    continue
                self.api_key = _key
                self.base_url = _base
                self.provider = _prov
                print(f"[V4Agent] 使用 {_prov}: {_base}")
                break

        if not self.api_key:
            raise ValueError("未设置 API Key (DEEPSEEK_API_KEY / DUCK_MISS_API_KEY / DOUBAO_API_KEY)")

        self.history = []
        self.total_tokens = 0
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    @staticmethod
    def _provider_alive(api_key: str, base_url: str, probe_model: str) -> bool:
        """真实对话探测 (6s 超时, max_tokens=1): POST chat/completions"""
        try:
            r = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={"model": probe_model,
                      "messages": [{"role": "user", "content": "hi"}],
                      "max_tokens": 1},
                timeout=6,
            )
            return r.status_code < 400
        except Exception:
            return False
    
    def ask(self, question: str, model: str = "pro", max_tokens: int = 4096,
            reasoning_effort: str | None = None) -> str:
        """问V4一个问题（默认Pro模型，效果优先）
        
        Args:
            question: 问题内容
            model: "pro" 或 "flash"，默认 pro
            max_tokens: 最大输出token数
            reasoning_effort: None 保持默认; "low"/"none" 压缩推理链 —
                "none" 完全关闭推理 (2026-08-15 实测: reasoning_tokens=0,
                content 直接输出, 用于结构化 JSON 场景避免推理链吃满预算
                导致 content 为空)。
        """
        model_name = PRO_MODEL if model != "flash" else FLASH_MODEL
        
        if self.provider == "duckmiss":
            if model == "pro":
                model_name = DUCK_MISS_PRO_MODEL
            elif model == "flash":
                model_name = DUCK_MISS_FAST_MODEL
            else:
                model_name = DUCK_MISS_DEFAULT_MODEL
        elif self.provider == "ark":
            model_name = ARK_MODELS.get(model, ARK_MODELS["pro"])
        
        # 优先走统一网关；网关不可用时降级直连
        gateway_content = self._ask_via_gateway(question, SYSTEM_PROMPT, 0.7, max_tokens)
        if gateway_content is not None:
            self.history.append({"role": "user", "content": question})
            self.history.append({"role": "assistant", "content": gateway_content})
            return gateway_content

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": question})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": max_tokens,
        }

        if model == "flash" and self.provider == "deepseek":
            payload["reasoning_effort"] = "high"
        # 结构化输出场景: 显式压缩/关闭推理链 (DeepSeek 原生端点实测支持)
        if reasoning_effort in ("low", "none") and self.provider == "deepseek":
            payload["reasoning_effort"] = reasoning_effort

        start = time.time()
        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            
            duration = time.time() - start
            
            if "choices" in result and result["choices"]:
                _msg = result["choices"][0].get("message", {}) or {}
                content = _msg.get("content") or ""
                # DeepSeek V4 推理模型: 小 max_tokens 时 content 可能为空,
                # 答案在 reasoning_content → 回退读取 (2026-08-15)
                if not content.strip():
                    content = _msg.get("reasoning_content") or ""
                self.history.append({"role": "user", "content": question})
                self.history.append({"role": "assistant", "content": content})
                
                if "usage" in result:
                    usage = result["usage"]
                    self.total_tokens += usage.get("total_tokens", 0)
                    cost = self._calc_cost(usage, model_name)
                    print(f"\n[{self.provider.upper()} {model_name} | {duration:.1f}s | {usage.get('total_tokens', 0)} tokens | ¥{cost:.4f}]")
                    _log_llm_cost(self.provider, "ask", usage, cost,
                                  model=model_name,
                                  duration_s=round(duration, 2))
                
                return content
            else:
                return f"API异常: {result}"
                
        except requests.exceptions.HTTPError as e:
            return f"HTTP错误: {e}\n响应: {e.response.text if e.response else 'N/A'}"
        except Exception as e:
            return f"请求失败: {e}"

    def analyze(self, topic: str) -> str:
        """深度分析 - Pro模型（架构/方案级任务）"""
        return self.ask(
            f"请深度分析以下主题，给出结构化结论和具体建议:\n\n{topic}",
            model="pro"
        )

    def _resolve_model_name(self, model: str) -> str:
        """根据 provider 与 tier 解析实际模型名"""
        if self.provider == "duckmiss":
            if model == "pro":
                return DUCK_MISS_PRO_MODEL
            if model == "flash":
                return DUCK_MISS_FAST_MODEL
            return DUCK_MISS_DEFAULT_MODEL
        if self.provider == "ark":
            return ARK_MODELS.get(model, ARK_MODELS["pro"])
        # 原生 DeepSeek
        return PRO_MODEL if model != "flash" else FLASH_MODEL

    def chat_with_tools(
        self,
        message: str,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        model: str = "pro",
        max_iterations: int = 5,
        max_tokens: int = 4096,
        system_prompt: str | None = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        """原生 V4 Tool Calling 对接 - 完整工具调用循环

        注意：原生 Function Calling 能力当前统一网关（llm_gateway）尚未覆盖，
        本方法为临时直连 Provider API，待网关扩展工具调用后迁移。

        实现 OpenAI 兼容的原生 Function Calling 闭环（区别于
        tool_executor.model_driven_execution 的文本 JSON 解析模式）:

            1. 发送 user 消息 + tools 定义给 V4
            2. V4 在 message.tool_calls 中返回工具调用
            3. 本地执行每个 tool_call，结果以 role=tool 消息回传
            4. V4 基于工具结果生成最终回答（或继续调用工具）
            5. 最多迭代 max_iterations 次

        Args:
            message: 用户自然语言请求
            tools: V4 Function Calling 工具定义列表（OpenAI 格式）
            tool_executor: 自定义工具执行回调 (tool_name, args) -> result_dict；
                           为 None 时使用 tool_executor.execute_tool
            model: "pro" 或 "flash"，默认 pro
            max_iterations: 最大工具调用迭代次数（防止死循环）
            max_tokens: 单次响应最大 token
            system_prompt: 自定义系统提示词
            temperature: 采样温度

        Returns:
            {
                "content": 最终回答文本,
                "tool_calls": [{name, arguments, result, duration, iteration}],
                "iterations": 实际迭代次数,
                "usage": {prompt_tokens, completion_tokens, total_tokens},
                "model": 实际使用的模型名,
                "provider": API 提供商,
                "error": 错误信息（成功时为空字符串）,
            }
        """
        model_name = self._resolve_model_name(model)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt or SYSTEM_PROMPT}
        ]
        messages.extend(self.history)
        messages.append({"role": "user", "content": message})

        payload: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Flash + 原生 DeepSeek 启用高推理强度
        if model == "flash" and self.provider == "deepseek":
            payload["reasoning_effort"] = "high"

        all_tool_calls: list[dict[str, Any]] = []
        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        start_total = time.time()

        for iteration in range(max_iterations):
            try:
                response = self._session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
            except requests.exceptions.HTTPError as e:
                err_body = e.response.text if e.response is not None else "N/A"
                return {
                    "content": "",
                    "tool_calls": all_tool_calls,
                    "iterations": iteration,
                    "usage": total_usage,
                    "model": model_name,
                    "provider": self.provider,
                    "error": f"HTTP {e.response.status_code if e.response is not None else '?'}: {err_body[:300]}",
                }
            except Exception as e:
                return {
                    "content": "",
                    "tool_calls": all_tool_calls,
                    "iterations": iteration,
                    "usage": total_usage,
                    "model": model_name,
                    "provider": self.provider,
                    "error": f"请求失败: {e}",
                }

            # 累计 token 使用量
            if "usage" in result:
                u = result["usage"]
                total_usage["prompt_tokens"] += u.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += u.get("completion_tokens", 0)
                total_usage["total_tokens"] += u.get("total_tokens", 0)

            choices = result.get("choices") or []
            if not choices:
                return {
                    "content": "",
                    "tool_calls": all_tool_calls,
                    "iterations": iteration,
                    "usage": total_usage,
                    "model": model_name,
                    "provider": self.provider,
                    "error": f"API 返回异常: {str(result)[:300]}",
                }

            msg = choices[0].get("message", {}) or {}
            tool_calls = msg.get("tool_calls") or []

            # 没有工具调用 → V4 已生成最终回答
            if not tool_calls:
                content = msg.get("content", "") or ""
                # 保存对话历史（仅保存最终问答，不保存中间 tool 消息）
                self.history.append({"role": "user", "content": message})
                self.history.append({"role": "assistant", "content": content})
                if total_usage["total_tokens"] > 0:
                    self.total_tokens += total_usage["total_tokens"]

                duration = time.time() - start_total
                cost = self._calc_cost(total_usage, model_name)
                print(
                    f"\n[{self.provider.upper()} {model_name} | tool_calls={len(all_tool_calls)} "
                    f"| {duration:.1f}s | {total_usage['total_tokens']} tokens | ¥{cost:.4f}]"
                )
                _log_llm_cost(self.provider, "chat_tools", total_usage, cost,
                              model=model_name, duration_s=round(duration, 2),
                              tool_calls=len(all_tool_calls))
                return {
                    "content": content,
                    "tool_calls": all_tool_calls,
                    "iterations": iteration + 1,
                    "usage": total_usage,
                    "model": model_name,
                    "provider": self.provider,
                    "error": "",
                }

            # 有工具调用 → 把 assistant 消息（含 tool_calls）原样加入对话
            messages.append(msg)
            payload["messages"] = messages

            # 依次执行每个 tool_call
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                fn = tc.get("function", {}) or {}
                tool_name = fn.get("name", "")
                args_str = fn.get("arguments", "{}") or "{}"
                try:
                    args = json.loads(args_str) if args_str else {}
                except json.JSONDecodeError:
                    args = {"_raw_arguments": args_str}

                t_start = time.time()
                try:
                    if tool_executor is not None:
                        tool_result = tool_executor(tool_name, args)
                    else:
                        # 默认使用项目工具执行引擎
                        try:
                            from tools.tool_executor import execute_tool as _exec
                        except ImportError:
                            from tool_executor import execute_tool as _exec
                        r = _exec(tool_name, **args)
                        tool_result = r.to_dict()
                except Exception as e:
                    tool_result = {"success": False, "error": f"工具执行异常: {e}"}

                t_dur = time.time() - t_start
                all_tool_calls.append({
                    "name": tool_name,
                    "arguments": args,
                    "result": tool_result,
                    "duration": round(t_dur, 3),
                    "iteration": iteration + 1,
                    "tool_call_id": tc_id,
                })
                print(
                    f"[Tool Call {iteration + 1}.{len(all_tool_calls)}] "
                    f"{tool_name} → {tool_result.get('status', 'ok')} ({t_dur:.2f}s)"
                )

                # 工具结果以 role=tool 消息回传给 V4
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                })

            # 继续下一轮让 V4 基于工具结果生成回答

        # 达到最大迭代次数仍未结束
        return {
            "content": "",
            "tool_calls": all_tool_calls,
            "iterations": max_iterations,
            "usage": total_usage,
            "model": model_name,
            "provider": self.provider,
            "error": f"达到最大工具调用迭代次数 ({max_iterations})",
        }

    def qa(self, question: str, use_flash: bool = False) -> str:
        """问答 - 默认Pro模型，确保回答质量
        
        Args:
            question: 问题
            use_flash: 是否使用Flash（仅简单事实问答时设为True）
        """
        if use_flash:
            return self.ask(question, model="flash")
        
        model = select_for_prompt(question) if ROUTER_AVAILABLE else "pro"
        return self.ask(question, model=model)

    def plan(self, task: str) -> str:
        """任务规划 - Pro模型"""
        return self.ask(
            f"请为以下任务制定详细的执行计划，包括步骤、所需工具、预估时间和风险:\n\n{task}", 
            model="pro"
        )

    def code_review(self, code: str, language: str = "python") -> str:
        """代码审查 - Pro模型"""
        return self.ask(
            f"请审查以下{language}代码，指出问题和改进建议:\n\n```\n{code}\n```", 
            model="pro"
        )
    
    def debug(self, error_info: str, context: str = "") -> str:
        """调试排错 - Pro模型"""
        prompt = f"请分析以下错误并给出解决方案：\n\n错误信息:\n{error_info}"
        if context:
            prompt += f"\n\n上下文:\n{context}"
        prompt += "\n\n请给出可能的原因和具体的修复步骤。"
        return self.ask(prompt, model="pro")
    
    def creative(self, brief: str) -> str:
        """创意生成 - Pro模型"""
        return self.ask(
            f"请基于以下需求进行创意设计，给出具体方案和示例:\n\n{brief}", 
            model="pro"
        )
    
    def career_analysis(self, content: str) -> str:
        """职场学习分析 - 自动使用最佳可用模型（职场学习专用）
        
        优先级：
        1. 火山方舟 DeepSeek V4-Pro (效果最佳)
        2. 火山方舟 豆包 Pro (中文对话优秀)
        3. 原生 DeepSeek V4-Pro (兜底)
        """
        if ARK_AVAILABLE:
            try:
                return self._ask_ark(
                    f"请分析以下工作记录，给出心理历程分析和改进建议（温暖、鼓励、专业）:\n\n{content}",
                    model=ARK_MODELS["doubao_pro"],
                    system_prompt=CAREER_SYSTEM_PROMPT,
                    max_tokens=8192
                )
            except Exception as e:
                print(f"ARK调用失败，回退到原生DeepSeek: {e}")
        
        return self.ask(
            f"请分析以下工作记录，给出心理历程分析和改进建议（温暖、鼓励、专业）:\n\n{content}",
            model="pro",
            max_tokens=8192
        )
    
    def think_deeply(self, topic: str) -> str:
        """深度思考 - 使用思考模型进行多步骤推理
        
        使用 doubao-seed-1-6-thinking 或 doubao-1-5-thinking-pro
        """
        if ARK_AVAILABLE:
            try:
                return self._ask_ark(
                    f"请对以下主题进行深度思考分析，从多个角度进行推理，给出全面的见解:\n\n{topic}",
                    model=ARK_MODELS["thinking"],
                    temperature=0.8,
                    max_tokens=8192
                )
            except Exception as e:
                print(f"ARK思考模型调用失败，回退到Pro: {e}")
        
        return self.ask(
            f"请对以下主题进行深度思考分析，从多个角度进行推理，给出全面的见解:\n\n{topic}",
            model="pro",
            max_tokens=8192
        )
    
    def generate_code(self, requirement: str, language: str = "Python") -> str:
        """代码生成 - 使用专门的代码模型
        
        使用 doubao-seed-code 模型
        """
        if ARK_AVAILABLE:
            try:
                return self._ask_ark(
                    f"请根据以下需求生成{language}代码，包含注释和测试用例:\n\n{requirement}",
                    model=ARK_MODELS["code"],
                    temperature=0.7,
                    max_tokens=8192
                )
            except Exception as e:
                print(f"ARK代码模型调用失败，回退到Pro: {e}")
        
        return self.ask(
            f"请根据以下需求生成{language}代码，包含注释和测试用例:\n\n{requirement}",
            model="pro",
            max_tokens=8192
        )
    
    def translate(self, text: str, target_lang: str = "中文") -> str:
        """专业翻译 - 使用专门的翻译模型
        
        使用 doubao-seed-translation 模型
        """
        if ARK_AVAILABLE:
            try:
                return self._ask_ark(
                    f"请将以下文本翻译成{target_lang}，保持原意和专业术语准确性:\n\n{text}",
                    model=ARK_MODELS["translation"],
                    temperature=0.3,
                    max_tokens=4096
                )
            except Exception as e:
                print(f"ARK翻译模型调用失败，回退到Pro: {e}")
        
        return self.ask(
            f"请将以下文本翻译成{target_lang}，保持原意和专业术语准确性:\n\n{text}",
            model="pro",
            max_tokens=4096
        )
    
    def roleplay(self, character: str, scenario: str) -> str:
        """角色扮演 - 使用专门的角色扮演模型
        
        使用 doubao-seed-character 模型
        """
        if ARK_AVAILABLE:
            try:
                return self._ask_ark(
                    f"请扮演{character}，在以下场景中进行互动:\n\n场景: {scenario}",
                    model=ARK_MODELS["character"],
                    temperature=0.9,
                    max_tokens=4096
                )
            except Exception as e:
                print(f"ARK角色扮演模型调用失败，回退到Pro: {e}")
        
        return self.ask(
            f"请扮演{character}，在以下场景中进行互动:\n\n场景: {scenario}",
            model="pro",
            max_tokens=4096
        )
    
    def _ask_ark(self, prompt: str, model: str = None, system_prompt: str = "", 
                 temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """调用火山方舟(ARK) API（优先 llm_gateway 网关，降级直连 ARK）"""
        # 优先走统一网关
        gw_content = self._ask_via_gateway(prompt, system_prompt, temperature, max_tokens)
        if gw_content is not None:
            return gw_content
        # 降级：直连 ARK API
        if not ARK_AVAILABLE:
            raise RuntimeError("ARK未配置")
        
        if model is None:
            model = ARK_MODELS["pro"]
        
        headers = {
            "Authorization": f"Bearer {ARK_API_KEY}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": SYSTEM_PROMPT})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        start = time.time()
        response = requests.post(
            f"{ARK_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        
        duration = time.time() - start
        
        if "choices" in result and result["choices"]:
            content = result["choices"][0]["message"]["content"]
            
            if "usage" in result:
                usage = result["usage"]
                cost = self._calc_cost(usage, model)
                logger.info(f"[ARK {model} | {duration:.1f}s | {usage.get('total_tokens', 0)} tokens | ¥{cost:.4f}]")
                _log_llm_cost("ark", "ark_chat", usage, cost,
                              model=model, duration_s=round(duration, 2))
            
            return content
        return f"API异常: {result}"
    
    def daily_report_analysis(self, content: str) -> str:
        """日常报告分析 - 职场学习专用（career_analysis的别名）"""
        return self.career_analysis(content)
    
    def analyze_image(self, image_path: str, prompt: str = "请描述这张图片") -> str:
        """视觉分析 - 支持多模态模型分析图片

        优先级：
        0. 统一网关 llm_gateway（视觉多模态，路由到 VISION 模型；未配置/失败时降级）
        1. DuckMiss中转站 (Claude 3.5 Sonnet - 多模态)
        2. 火山方舟 ARK (豆包视觉模型)
        3. 硅基流动 SiliconFlow (Qwen2.5-VL)
        """
        import base64
        from pathlib import Path

        # 优先走统一网关（视觉多模态；网关未配置/调用失败时继续降级链）
        try:
            import asyncio

            from core.llm_gateway import llm_gateway
            asyncio.get_running_loop()  # 已有运行循环则不能 asyncio.run，直接跳过网关
        except RuntimeError:
            try:
                gw_response = asyncio.run(llm_gateway.chat(
                    message=prompt,
                    system_prompt="你是专业的视频/图像分析助手，请详细描述图片内容。",
                    images=[self._encode_image_for_multimodal(image_path)],
                ))
            except Exception as e:
                print(f"[gateway] 视觉分析失败，降级: {e}")
                gw_response = None
            if gw_response is not None and getattr(gw_response, "success", False):
                return gw_response.content
        except ImportError:
            pass
        except Exception as e:
            print(f"[gateway] 视觉网关异常，降级: {e}")

        # DuckMiss中转站 - Claude 3.5 Sonnet（多模态）
        if DUCK_MISS_AVAILABLE:
            try:
                image_data = self._encode_image_for_multimodal(image_path)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                    ]}
                ]
                
                payload = {
                    "model": DUCK_MISS_DEFAULT_MODEL,
                    "messages": messages,
                    "max_tokens": 4096,
                }
                
                response = self._session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
                
                if "choices" in result and result["choices"]:
                    return result["choices"][0]["message"]["content"]
                return f"API异常: {result}"
                
            except Exception as e:
                print(f"DuckMiss视觉分析失败，尝试降级: {e}")
        
        # 火山方舟 ARK — 该账号无可用视觉模型(2026-08-14 实测), 直接降级硅基流动
        if ARK_AVAILABLE and "vision_pro" in ARK_MODELS:
            try:
                return self._ask_ark(
                    f"{prompt}\n\n图片路径: {image_path}",
                    model=ARK_MODELS["vision_pro"],
                    max_tokens=4096
                )
            except Exception as e:
                print(f"ARK视觉分析失败，尝试硅基流动: {e}")
        
        # 硅基流动 SiliconFlow - Qwen2.5-VL
        try:
            from vision_client import VisionClient
            client = VisionClient()
            if client.is_available():
                return client.analyze_image(image_path, prompt)
        except ImportError:
            pass
        except Exception as e:
            print(f"硅基流动视觉分析失败: {e}")
        
        raise RuntimeError("所有视觉模型均不可用，请配置 DOUBAO_API_KEY 或 SILICONFLOW_API_KEY")
    
    def _encode_image_for_multimodal(self, image_path: str) -> str:
        """为多模态模型编码图片"""
        from pathlib import Path
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"图片不存在: {image_path}")
        
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def generate_image(self, prompt: str, size: str = "1024x1024") -> dict[str, Any]:
        """图像生成 - 使用ARK图像生成模型

        注意：图像生成能力当前为临时直连 ARK API，待统一网关扩展图像生成后迁移。
        """
        if ARK_AVAILABLE:
            try:
                headers = {
                    "Authorization": f"Bearer {ARK_API_KEY}",
                    "Content-Type": "application/json",
                }
                
                payload = {
                    "model": ARK_MODELS["image_gen"],
                    "prompt": prompt,
                    "size": size,
                }
                
                response = requests.post(
                    f"{ARK_BASE_URL}/images/generations",
                    headers=headers,
                    json=payload,
                    timeout=120,
                )
                response.raise_for_status()
                result = response.json()
                
                if "data" in result and result["data"]:
                    return {"url": result["data"][0].get("url", ""), "success": True}
                return {"error": f"API返回异常: {result}", "success": False}
                
            except Exception as e:
                return {"error": str(e), "success": False}
        
        raise RuntimeError("ARK未配置，请设置 DOUBAO_API_KEY 环境变量")
    
    def execute_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """执行工具（集成工具执行引擎）"""
        try:
            try:
                from tools.tool_executor import execute_tool
            except ImportError:
                from tool_executor import execute_tool
            result = execute_tool(tool_name, **kwargs)
            return result.to_dict()
        except ImportError:
            return {"success": False, "error": "tool_executor not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def orchestrate(self, user_request: str) -> dict[str, Any]:
        """模型驱动的工具编排 - 使用V4分析并执行工具链"""
        try:
            try:
                from tools.tool_executor import model_execute
            except ImportError:
                from tool_executor import model_execute
            return model_execute(user_request)
        except ImportError:
            return {"success": False, "error": "tool_executor not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_history(self):
        """清空对话历史"""
        self.history = []

    def _calc_cost(self, usage: dict, model: str) -> float:
        """计算费用（基于显式 model→price 映射表，per 1k tokens）"""
        pricing = self._lookup_pricing(model)
        
        prompt = usage.get("prompt_tokens", 0) / 1_000
        completion = usage.get("completion_tokens", 0) / 1_000
        return prompt * pricing["input"] + completion * pricing["output"]

    @staticmethod
    def _lookup_pricing(model: str) -> dict[str, float]:
        """按 精确匹配 → 前缀匹配 → 默认低价(turbo) 查找模型单价"""
        default = MODEL_PRICING["__default__"]
        if not model:
            return default
        name = model.lower()
        # 1. 精确匹配
        if name in MODEL_PRICING:
            return MODEL_PRICING[name]
        # 2. 前缀匹配（长键优先，避免 "deepseek-v4" 抢先 "deepseek-v4-flash"）
        for key in sorted(MODEL_PRICING, key=len, reverse=True):
            if key.startswith("__"):
                continue
            if name.startswith(key):
                return MODEL_PRICING[key]
        # 3. 默认低价（turbo 级）
        return default

    def _ask_via_gateway(self, prompt: str, system_prompt: str,
                         temperature: float, max_tokens: int) -> str | None:
        """通过 llm_gateway 统一网关调用（同步上下文桥接异步网关）

        import 失败或已有运行中的事件循环时返回 None，由上层降级到直连 ARK。
        """
        try:
            import asyncio

            from core.llm_gateway import llm_gateway
        except Exception:
            return None
        try:
            asyncio.get_running_loop()
            return None  # 已有运行中的事件循环，降级
        except RuntimeError:
            pass
        try:
            response = asyncio.run(llm_gateway.chat(
                message=prompt,
                system_prompt=system_prompt or SYSTEM_PROMPT,
                temperature=temperature,
                max_tokens=max_tokens,
            ))
        except Exception as e:
            print(f"[gateway] 调用异常: {e}")
            return None
        if not response or not getattr(response, "success", False):
            return None
        # 费用日志
        in_tok = getattr(response, "tokens_input", 0) or 0
        out_tok = getattr(response, "tokens_output", 0) or 0
        if in_tok or out_tok:
            usage = {"prompt_tokens": in_tok, "completion_tokens": out_tok,
                     "total_tokens": in_tok + out_tok}
            cost = self._calc_cost(usage, getattr(response, "model", "") or "")
            latency = getattr(response, "latency_ms", 0.0) / 1000.0
            logger.info(f"[gateway {response.model} | {latency:.1f}s | "
                        f"{usage['total_tokens']} tokens | ¥{cost:.4f}]")
            _log_llm_cost("gateway", "gateway_chat", usage, cost,
                          model=getattr(response, "model", ""),
                          duration_s=round(latency, 2))
        return response.content

    def list_available_models(self) -> dict[str, list[str]]:
        """列出当前可用的模型列表"""
        models = {
            "native_deepseek": {
                "pro": PRO_MODEL,
                "flash": FLASH_MODEL,
            }
        }
        
        if ARK_AVAILABLE:
            models["ark"] = ARK_MODELS
        
        return models


_agent = None

def get_agent() -> V4Agent:
    """获取全局V4 Agent实例"""
    global _agent
    if _agent is None:
        _agent = V4Agent()
    return _agent


def analyze(topic: str) -> str:
    """快捷深度分析"""
    return get_agent().analyze(topic)

def qa(question: str) -> str:
    """快捷问答"""
    return get_agent().qa(question)

def plan(task: str) -> str:
    """快捷任务规划"""
    return get_agent().plan(task)

def execute_tool(tool_name: str, **kwargs) -> dict[str, Any]:
    """快捷工具执行"""
    return get_agent().execute_tool(tool_name, **kwargs)

def orchestrate(user_request: str) -> dict[str, Any]:
    """快捷工具编排（模型驱动）"""
    return get_agent().orchestrate(user_request)

def career_analysis(content: str) -> str:
    """快捷职场学习分析（自动使用豆包模型）"""
    return get_agent().career_analysis(content)

def daily_report_analysis(content: str) -> str:
    """快捷日常报告分析（职场学习专用）"""
    return get_agent().daily_report_analysis(content)

def think_deeply(topic: str) -> str:
    """快捷深度思考分析"""
    return get_agent().think_deeply(topic)

def generate_code(requirement: str, language: str = "Python") -> str:
    """快捷代码生成"""
    return get_agent().generate_code(requirement, language)

def translate(text: str, target_lang: str = "中文") -> str:
    """快捷专业翻译"""
    return get_agent().translate(text, target_lang)

def roleplay(character: str, scenario: str) -> str:
    """快捷角色扮演"""
    return get_agent().roleplay(character, scenario)


if __name__ == "__main__":
    agent = V4Agent()
    print("V4 Agent 测试...")
    print("\n可用模型列表:")
    models = agent.list_available_models()
    for platform, model_dict in models.items():
        print(f"  {platform}:")
        for tier, name in model_dict.items():
            print(f"    {tier}: {name}")
    
    result = agent.qa("AE-Knowledge-Vault项目的核心价值是什么？")
    print(f"\nQA结果:\n{result[:200]}...")
