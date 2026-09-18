#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
豆包模型客户端 - Doubao Client
=============================

支持豆包开放平台和火山方舟(ARK)两种接入方式。

核心功能：
1. 豆包API调用封装
2. 支持多模型切换（3.5-turbo/pro/4/Seed系列/视觉/图像生成等）
3. 智能路由：根据任务类型自动选择模型
4. 错误处理和自动重试
5. 与现有ai_agent.py无缝集成

配置方式：
- 环境变量：DOUBAO_API_KEY
- 配置文件：core/config.py → doubao 段

使用方式：
    from doubao_client import DoubaoClient
    
    # 创建客户端（自动读取环境变量）
    client = DoubaoClient()
    
    # 简单问答
    result = client.ask("你好，介绍一下你自己")
    
    # 深度分析（自动使用Pro模型）
    result = client.analyze("分析一下新能源行业趋势")
    
    # 指定模型
    result = client.ask("专业问题", model="doubao-seed-2-1-pro-260628")

注意（DeprecationWarning）：
    自 2026-08 起，所有 LLM 调用应统一走 core/llm_gateway 网关（自动适配/路由/
    降级/成本追踪）。本客户端仅作为网关内部实现细节或历史脚本兼容保留，
    新代码请勿直接 import，请改用 core.llm_gateway.llm_gateway.chat()。
"""

import os
import sys
import time
from enum import Enum
from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:
    # 不在导入期 sys.exit(1)：否则 import 本模块的上层（ai_agent / 测试套件）
    # 会在收集阶段直接崩溃（SystemExit 不会被上层的 except ImportError 捕获）。
    # 改为标记不可用，仅在真正发起请求时再报错（运行时失败，而非导入期）。
    requests = None  # type: ignore[assignment]
    REQUESTS_AVAILABLE = False
    print(
        "[doubao_client] 警告: 未安装 requests，网络相关功能将不可用；"
        "请运行 `py -3.11 -m pip install requests`"
    )
else:
    REQUESTS_AVAILABLE = True


class DoubaoPlatform(Enum):
    """豆包接入平台"""
    OPEN_PLATFORM = "open_platform"    # 豆包开放平台
    ARK = "ark"                        # 火山方舟


class DoubaoModel(Enum):
    """豆包开放平台可用模型"""
    TURBO = "doubao-3.5-turbo"
    PRO = "doubao-3.5-pro"
    V4 = "doubao-4"


class ArkTextModel(Enum):
    """火山方舟文本对话模型"""
    # DeepSeek系列
    DEEPSEEK_V4_PRO = "deepseek-v4-pro-260425"
    DEEPSEEK_V4_FLASH = "deepseek-v4-flash-260425"
    DEEPSEEK_V3 = "deepseek-v3-250722"
    DEEPSEEK_V3_1 = "deepseek-v3-1-250922"
    DEEPSEEK_V3_2 = "deepseek-v3-2-260122"
    DEEPSEEK_R1 = "deepseek-r1-250722"
    DEEPSEEK_R1_DISTILL_7B = "deepseek-r1-distill-qwen-7b-250722"
    DEEPSEEK_R1_DISTILL_32B = "deepseek-r1-distill-qwen-32b-250722"
    
    # 豆包基础系列
    DOUBO_LITE_4K = "doubao-lite-4k-240428"
    DOUBO_LITE_32K = "doubao-lite-32k-240428"
    DOUBO_LITE_128K = "doubao-lite-128k-240428"
    DOUBO_PRO_4K = "doubao-pro-4k-240428"
    DOUBO_PRO_32K = "doubao-pro-32k-240428"
    DOUBO_PRO_128K = "doubao-pro-128k-240428"
    DOUBO_PRO_256K = "doubao-pro-256k-240428"
    
    # 豆包Seed系列
    SEED_1_6 = "doubao-seed-1-6-250722"
    SEED_1_6_FLASH = "doubao-seed-1-6-flash-250722"
    SEED_1_6_LITE = "doubao-seed-1-6-lite-250722"
    SEED_1_6_THINKING = "doubao-seed-1-6-thinking-250722"
    SEED_1_8 = "doubao-seed-1-8-251128"
    SEED_2_0_MINI = "doubao-seed-2-0-mini-251228"
    SEED_2_0_LITE = "doubao-seed-2-0-lite-251228"
    SEED_2_0_PRO = "doubao-seed-2-0-pro-251228"
    SEED_2_0_CODE = "doubao-seed-2-0-code-251228"
    SEED_2_1_TURBO = "doubao-seed-2-1-turbo-260628"
    SEED_2_1_PRO = "doubao-seed-2-1-pro-260628"
    
    # 深度思考模型
    DOUBO_1_5_THINKING = "doubao-1-5-thinking-pro-241128"
    SEED_1_6_THINKING_V2 = "doubao-seed-1-6-thinking-250722"
    
    # 垂直领域模型
    SEED_CODE = "doubao-seed-code-251228"
    SEED_TRANSLATION = "doubao-seed-translation-250722"
    SEED_CHARACTER = "doubao-seed-character-251228"
    SEED_EVOLVING = "doubao-seed-evolving-251228"
    
    # 其他厂商模型
    QWEN3_8B = "qwen3-8b-260328"
    QWEN3_14B = "qwen3-14b-260328"
    QWEN3_32B = "qwen3-32b-260328"
    QWEN3_0_6B = "qwen3-0-6b-250922"
    QWEN2_5_72B = "qwen2-5-72b-250922"
    GLM_4_7 = "glm-4-7-250722"
    GLM_4_5_AIR = "glm-4-5-air-260328"
    GLM_5_2 = "glm-5-2-260617"
    KIMI_K2 = "kimi-k2-260328"
    WAN2_14B = "wan2-1-14b-250722"
    MISTRAL_7B = "mistral-7b-240428"


class ArkVisionModel(Enum):
    """火山方舟视觉理解模型"""
    DOUBO_VISION_PRO = "doubao-vision-pro-32k-240428"
    DOUBO_VISION_LITE = "doubao-vision-lite-32k-240428"
    DOUBO_1_5_VISION_PRO = "doubao-1-5-vision-pro-241128"
    DOUBO_1_5_VISION_PRO_32K = "doubao-1-5-vision-pro-32k-241128"
    DOUBO_1_5_VISION_LITE = "doubao-1-5-vision-lite-241128"
    DOUBO_1_5_THINKING_VISION = "doubao-1-5-thinking-vision-pro-241128"
    SEED_1_6_VISION = "doubao-seed-1-6-vision-250722"


class ArkImageModel(Enum):
    """火山方舟图像生成模型"""
    SEEDREAM_5_0_PRO = "doubao-seedream-5-0-pro-260628"
    SEEDREAM_5_0 = "doubao-seedream-5-0-260128"
    SEEDREAM_4_5 = "doubao-seedream-4-5-251128"
    SEEDREAM_4_0 = "doubao-seedream-4-0-250722"
    SEEDREAM_3_0 = "doubao-seedream-3-0-t2i-241128"


class ArkVideoModel(Enum):
    """火山方舟视频生成模型"""
    SEEDANCE_2_0 = "doubao-seedance-2-0-260128"
    SEEDANCE_2_0_FAST = "doubao-seedance-2-0-fast-260128"
    SEEDANCE_2_0_MINI = "doubao-seedance-2-0-mini-260128"
    SEEDANCE_1_5_PRO = "doubao-seedance-1-5-pro-251128"
    SEEDANCE_1_0_PRO = "doubao-seedance-1-0-pro-250722"
    SEEDANCE_1_0_FAST = "doubao-seedance-1-0-pro-fast-250722"
    SEEDANCE_1_0_LITE_I2V = "doubao-seedance-1-0-lite-i2v-250722"
    SEEDANCE_1_0_LITE_T2V = "doubao-seedance-1-0-lite-t2v-250722"


class Ark3DModel(Enum):
    """火山方舟3D生成模型"""
    SEED3D_1_0 = "doubao-seed3d-1-0-250722"
    SEED3D_2_0 = "doubao-seed3d-2-0-251228"
    HYPER3D = "hyper3d-gen2-260128"
    HITEM3D = "hitem3d-2-0-260128"


class ArkEmbeddingModel(Enum):
    """火山方舟Embedding模型"""
    DOUBO_EMBEDDING = "doubao-embedding-240428"
    DOUBO_EMBEDDING_LARGE = "doubao-embedding-large-240428"
    DOUBO_EMBEDDING_VISION = "doubao-embedding-vision-240428"


class ModelTier(Enum):
    """模型等级"""
    PRO = "pro"
    FLASH = "flash"
    LITE = "lite"
    THINKING = "thinking"
    SPECIALIZED = "specialized"
    VISION = "vision"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    EMBEDDING = "embedding"


MODEL_TIER_MAP = {
    "deepseek-v4-pro": ModelTier.PRO,
    "doubao-seed-2-1-pro-260628": ModelTier.PRO,
    "doubao-pro": ModelTier.PRO,
    "deepseek-v3-2": ModelTier.PRO,
    "deepseek-r1": ModelTier.PRO,
    "qwen2-5-72b": ModelTier.PRO,
    "qwen3-32b": ModelTier.PRO,
    "glm-5-2": ModelTier.PRO,
    "kimi-k2": ModelTier.PRO,
    
    "deepseek-v4-flash": ModelTier.FLASH,
    "doubao-seed-2-1-turbo-260628": ModelTier.FLASH,
    "doubao-seed-1-6-flash": ModelTier.FLASH,
    "doubao-lite": ModelTier.LITE,
    "doubao-seed-2-0-lite": ModelTier.LITE,
    "doubao-seed-2-0-mini": ModelTier.LITE,
    
    "doubao-1-5-thinking": ModelTier.THINKING,
    "doubao-seed-1-6-thinking": ModelTier.THINKING,
    
    "doubao-seed-code": ModelTier.SPECIALIZED,
    "doubao-seed-translation": ModelTier.SPECIALIZED,
    "doubao-seed-character": ModelTier.SPECIALIZED,
    "doubao-seed-evolving": ModelTier.SPECIALIZED,
}


class DoubaoClient:
    """豆包模型客户端"""
    
    OPEN_PLATFORM_BASE = "https://api.doubao.com/v1"
    ARK_BASE_TEMPLATE = "https://ark.cn-beijing.volces.com/api/v3"
    
    SYSTEM_PROMPT = """你是「力王新能源职场学习助手」，专为闫起名提供职场学习和成长指导。

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
    
    def __init__(self, 
                 api_key: str | None = None,
                 platform: DoubaoPlatform = DoubaoPlatform.OPEN_PLATFORM,
                 ark_endpoint_id: str | None = None):
        self.api_key = api_key or os.environ.get("DOUBAO_API_KEY", "")
        if not self.api_key:
            raise ValueError("未设置 DOUBAO_API_KEY 环境变量")
        
        self.platform = platform
        self.ark_endpoint_id = ark_endpoint_id
        
        if platform == DoubaoPlatform.OPEN_PLATFORM:
            self.base_url = self.OPEN_PLATFORM_BASE
        else:
            self.base_url = self.ARK_BASE_TEMPLATE
            if not ark_endpoint_id:
                raise ValueError("火山方舟平台需要提供 ark_endpoint_id")
        
        self.history = []
        self.total_tokens = 0
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
    
    def ask(self, 
            question: str, 
            model: str = "doubao-3.5-turbo", 
            max_tokens: int = 4096,
            temperature: float = 0.7) -> str:
        """豆包对话。

        注意：当前为临时直连 ARK / 豆包 Provider API，待统一网关完全覆盖后迁移。
        """
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": question})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if self.platform == DoubaoPlatform.ARK and self.ark_endpoint_id:
            payload["endpoint_id"] = self.ark_endpoint_id
        
        start = time.time()
        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=self._get_timeout(model),
            )
            response.raise_for_status()
            result = response.json()
            
            duration = time.time() - start
            
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                self.history.append({"role": "user", "content": question})
                self.history.append({"role": "assistant", "content": content})
                
                if "usage" in result:
                    usage = result["usage"]
                    self.total_tokens += usage.get("total_tokens", 0)
                    cost = self._calc_cost(usage, model)
                    print(f"\n[豆包 {model} | {duration:.1f}s | {usage.get('total_tokens', 0)} tokens | ¥{cost:.4f}]")
                
                return content
            else:
                return f"API异常: {result}"
                
        except requests.exceptions.HTTPError as e:
            return f"HTTP错误: {e}\n响应: {e.response.text if e.response else 'N/A'}"
        except Exception as e:
            return f"请求失败: {e}"
    
    def analyze(self, topic: str) -> str:
        return self.ask(
            f"请深度分析以下主题，给出结构化结论和具体建议:\n\n{topic}",
            model="doubao-seed-2-1-pro-260628",
            max_tokens=8192,
        )
    
    def qa(self, question: str, use_turbo: bool = False) -> str:
        if use_turbo:
            return self.ask(question, model="doubao-seed-2-1-turbo-260628")
        
        pro_keywords = ["分析", "架构", "设计", "规划", "优化", "深度", "复杂", "详细"]
        turbo_keywords = ["简单", "快速", "翻译", "转换", "格式", "总结"]
        
        question_lower = question.lower()
        pro_score = sum(1 for kw in pro_keywords if kw in question_lower)
        turbo_score = sum(1 for kw in turbo_keywords if kw in question_lower)
        
        if pro_score > turbo_score:
            return self.ask(question, model="doubao-seed-2-1-pro-260628")
        elif turbo_score >= 2:
            return self.ask(question, model="doubao-seed-2-1-turbo-260628")
        else:
            return self.ask(question, model="doubao-seed-2-1-pro-260628")
    
    def plan(self, task: str) -> str:
        return self.ask(
            f"请为以下任务制定详细的执行计划，包括步骤、所需工具、预估时间和风险:\n\n{task}",
            model="doubao-seed-2-1-pro-260628",
            max_tokens=8192,
        )
    
    def creative(self, brief: str) -> str:
        return self.ask(
            f"请基于以下需求进行创意设计，给出具体方案和示例:\n\n{brief}",
            model="doubao-seed-2-1-pro-260628",
            max_tokens=8192,
        )
    
    def daily_report_analysis(self, content: str) -> str:
        prompt = f"""请分析以下工作记录，给出心理历程分析和改进建议：

工作记录：
{content}

请按照以下结构输出：
1. 情绪分析（当天的情绪基调、波动点）
2. 心理状态（压力水平、动力来源、成就感）
3. 成长轨迹（相比之前的进步、正在克服的挑战）
4. 改进建议（针对性的学习策略、心理调适建议）

语气要温暖、鼓励、专业。"""
        
        return self.ask(prompt, model="doubao-seed-2-1-pro-260628", max_tokens=8192)
    
    def think_deeply(self, topic: str) -> str:
        return self.ask(
            f"请对以下主题进行深度思考分析，从多个角度进行推理，给出全面的见解:\n\n{topic}",
            model="doubao-seed-1-6-thinking-250722",
            max_tokens=8192,
            temperature=0.8,
        )
    
    def translate(self, text: str, target_lang: str = "中文") -> str:
        return self.ask(
            f"请将以下文本翻译成{target_lang}，保持原意和专业术语准确性:\n\n{text}",
            model="doubao-seed-translation-250722",
            max_tokens=4096,
            temperature=0.3,
        )
    
    def generate_code(self, requirement: str, language: str = "Python") -> str:
        return self.ask(
            f"请根据以下需求生成{language}代码，包含注释和测试用例:\n\n{requirement}",
            model="doubao-seed-code-251228",
            max_tokens=8192,
            temperature=0.7,
        )
    
    def roleplay(self, character: str, scenario: str) -> str:
        return self.ask(
            f"请扮演{character}，在以下场景中进行互动:\n\n场景: {scenario}",
            model="doubao-seed-character-251228",
            max_tokens=4096,
            temperature=0.9,
        )
    
    def clear_history(self):
        self.history = []
    
    def _get_timeout(self, model: str) -> int:
        if "pro" in model or "thinking" in model:
            return 120
        return 60
    
    def _calc_cost(self, usage: dict, model: str) -> float:
        if "pro" in model or "4" in model or "72b" in model or "32b" in model:
            in_price, out_price = 4, 8
        elif "flash" in model or "turbo" in model:
            in_price, out_price = 2, 4
        else:
            in_price, out_price = 1, 2
        
        prompt = usage.get("prompt_tokens", 0) / 1_000_000
        completion = usage.get("completion_tokens", 0) / 1_000_000
        return prompt * in_price + completion * out_price

    def list_available_models(self) -> dict[str, list[str]]:
        """列出当前平台可用的模型"""
        if self.platform == DoubaoPlatform.OPEN_PLATFORM:
            return {
                "text": ["doubao-3.5-turbo", "doubao-3.5-pro", "doubao-4"],
            }
        else:
            return {
                "text_pro": [
                    "deepseek-v4-pro-260425",
                    "doubao-seed-2-1-pro-260628",
                    "doubao-pro-256k-240428",
                    "deepseek-v3-2-260122",
                    "deepseek-r1-250722",
                    "qwen2-5-72b-250922",
                    "qwen3-32b-260328",
                    "glm-5-2-260617",
                    "kimi-k2-260328",
                ],
                "text_flash": [
                    "deepseek-v4-flash-260425",
                    "doubao-seed-2-1-turbo-260628",
                    "doubao-seed-1-6-flash-250722",
                ],
                "text_lite": [
                    "doubao-lite-128k-240428",
                    "doubao-seed-2-0-lite-251228",
                    "doubao-seed-2-0-mini-251228",
                ],
                "thinking": [
                    "doubao-1-5-thinking-pro-241128",
                    "doubao-seed-1-6-thinking-250722",
                ],
                "specialized": [
                    "doubao-seed-code-251228",
                    "doubao-seed-translation-250722",
                    "doubao-seed-character-251228",
                    "doubao-seed-evolving-251228",
                ],
                "vision": [
                    "doubao-vision-pro-32k-240428",
                    "doubao-seed-1-6-vision-250722",
                ],
                "image_gen": [
                    "doubao-seedream-5-0-pro-260628",
                    "doubao-seedream-5-0-260128",
                ],
                "video_gen": [
                    "doubao-seedance-2-0-260128",
                    "doubao-seedance-2-0-fast-260128",
                ],
                "embedding": [
                    "doubao-embedding-240428",
                    "doubao-embedding-large-240428",
                ],
            }


_client = None


def get_client(platform: DoubaoPlatform = DoubaoPlatform.OPEN_PLATFORM,
               ark_endpoint_id: str | None = None) -> DoubaoClient:
    global _client
    if _client is None:
        _client = DoubaoClient(platform=platform, ark_endpoint_id=ark_endpoint_id)
    return _client


def ask(question: str, model: str = "doubao-3.5-turbo") -> str:
    return get_client().ask(question, model=model)


def analyze(topic: str) -> str:
    return get_client().analyze(topic)


def qa(question: str) -> str:
    return get_client().qa(question)


def plan(task: str) -> str:
    return get_client().plan(task)


def analyze_daily_report(content: str) -> str:
    return get_client().daily_report_analysis(content)


def is_available() -> bool:
    return bool(os.environ.get("DOUBAO_API_KEY"))


if __name__ == "__main__":
    if not is_available():
        print("请先设置 DOUBAO_API_KEY 环境变量")
        print("例如: $env:DOUBAO_API_KEY='your_api_key'")
        sys.exit(1)
    
    client = DoubaoClient()
    print("豆包模型客户端测试...")
    print("\n可用模型列表:")
    models = client.list_available_models()
    for category, model_list in models.items():
        print(f"  {category}: {len(model_list)}个模型")
    
    result = client.qa("你好，介绍一下你自己")
    print(f"\n测试结果:\n{result[:200]}...")
