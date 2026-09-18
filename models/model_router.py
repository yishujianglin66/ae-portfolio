#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模型路由器 - 智能选择模型
========================

核心原则：效果优先，成本其次。

支持的模型：
┌─────────────────────────────────────────────────────────────────────────┐
│  PRO 级模型 (默认)                                                      │
│  • deepseek-v4-pro (1.6T参数，最强推理)                                 │
│  • doubao-seed-2-1-pro (豆包Seed Pro)                                  │
│  • doubao-pro-256k (豆包Pro长文本)                                     │
│  • deepseek-v3-2 / deepseek-r1 (DeepSeek R1系列)                       │
│  • qwen2-5-72b / qwen3-32b (通义千问)                                 │
│  • glm-5-2 (智谱GLM)                                                   │
│  • kimi-k2 (Moonshot Kimi)                                             │
├─────────────────────────────────────────────────────────────────────────┤
│  FLASH 级模型 (仅简单重复场景)                                           │
│  • deepseek-v4-flash (284B参数，快速经济)                              │
│  • doubao-seed-2-1-turbo (豆包Seed Turbo)                              │
│  • doubao-seed-1-6-flash (豆包Seed Flash)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  LITE 级模型 (低延迟场景)                                                │
│  • doubao-lite-128k (豆包Lite)                                         │
│  • doubao-seed-2-0-lite / mini (豆包Seed Lite)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  THINKING 深度思考模型                                                   │
│  • doubao-1-5-thinking-pro (豆包思考版)                                │
│  • doubao-seed-1-6-thinking (豆包Seed思考版)                           │
├─────────────────────────────────────────────────────────────────────────┤
│  SPECIALIZED 垂直领域模型                                                │
│  • doubao-seed-code (代码生成)                                         │
│  • doubao-seed-translation (专业翻译)                                  │
│  • doubao-seed-character (角色扮演)                                   │
│  • doubao-seed-evolving (演进模型)                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  VISION 视觉模型                                                        │
│  • doubao-vision-pro-32k (视觉理解专业版)                              │
│  • doubao-seed-1-6-vision (Seed视觉)                                  │
├─────────────────────────────────────────────────────────────────────────┤
│  IMAGE_GENERATION 图像生成                                               │
│  • doubao-seedream-5-0-pro (图像生成专业版)                            │
│  • doubao-seedream-5-0 (图像生成标准版)                                │
├─────────────────────────────────────────────────────────────────────────┤
│  VIDEO_GENERATION 视频生成                                               │
│  • doubao-seedance-2-0 (视频生成)                                     │
│  • doubao-seedance-2-0-fast (视频生成快速版)                           │
├─────────────────────────────────────────────────────────────────────────┤
│  EMBEDDING 向量化模型                                                   │
│  • doubao-embedding (文本向量化)                                       │
│  • doubao-embedding-large (大文本向量化)                                │
│  • doubao-embedding-vision (视觉向量化)                                │
└─────────────────────────────────────────────────────────────────────────┘

任务类型分类：
┌─────────────────────────────────────────────────────────────────────────┐
│  PRO 级任务 (默认)                                                      │
│  • 架构设计 / 复杂分析 / 战略规划                                       │
│  • 代码审查 / 调试疑难杂症                                              │
│  • 风格分析 / 创意生成 / 多模态理解                                     │
│  • 工具编排 / 工作流设计                                                │
│  • 知识库深度问答 / 跨文档推理                                          │
│  • 用户明确要求高质量的任务                                              │
│  • 职场学习心理分析 / 月度报告生成                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  FLASH 级任务 (仅简单重复场景)                                           │
│  • 简单事实问答 / 信息检索                                               │
│  • 格式转换 / 文本润色 / 翻译                                            │
│  • 大规模批量处理（单次成本敏感）                                         │
│  • 实时交互低延迟需求（可降级）                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  THINKING 深度思考任务                                                   │
│  • 需要多步骤推理的复杂问题                                              │
│  • 需要深思熟虑的决策分析                                                │
│  • 创意发散与创新思考                                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  SPECIALIZED 垂直领域任务                                                │
│  • 代码生成与调试                                                       │
│  • 专业翻译                                                             │
│  • 角色扮演与模拟对话                                                   │
│  • 持续学习与演进任务                                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  视觉任务                                                               │
│  • 图像分析 / 视频理解                                                   │
│  • AE效果识别 / 关键帧分析                                              │
│  • 图像生成 / 创意设计                                                  │
└─────────────────────────────────────────────────────────────────────────┘
"""

from enum import Enum
from typing import Dict, List, Optional


class TaskTier(Enum):
    PRO = "pro"
    FLASH = "flash"
    LITE = "lite"
    THINKING = "thinking"
    SPECIALIZED = "specialized"
    VISION_PRO = "vision_pro"
    VISION_LITE = "vision_lite"
    IMAGE_GEN = "image_gen"
    VIDEO_GEN = "video_gen"
    EMBEDDING = "embedding"


class TaskCategory(Enum):
    ARCHITECTURE = "architecture"
    CODE_REVIEW = "code_review"
    DEBUGGING = "debugging"
    STYLE_ANALYSIS = "style_analysis"
    CREATIVE = "creative"
    TOOL_ORCHESTRATION = "tool_orch"
    WORKFLOW_DESIGN = "workflow_design"
    DEEP_QA = "deep_qa"
    PLANNING = "planning"
    MULTIMODAL = "multimodal"
    
    CAREER_GROWTH = "career_growth"
    DAILY_REPORT = "daily_report"
    MONTHLY_REPORT = "monthly_report"
    
    SIMPLE_QA = "simple_qa"
    FORMAT_CONVERT = "format_convert"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    BATCH_PROCESSING = "batch"
    
    THINKING_TASK = "thinking"
    CODE_GENERATION = "code_gen"
    ROLEPLAY = "roleplay"
    EVOLVING = "evolving"
    
    IMAGE_ANALYSIS = "image_analysis"
    AE_EFFECT_ANALYSIS = "ae_effect"
    KEYFRAME_ANALYSIS = "keyframe"
    IMAGE_GENERATION = "image_gen"
    SCENE_DETECTION = "scene_detect"
    VIDEO_GENERATION = "video_gen"
    TEXT_EMBEDDING = "embedding"


CATEGORY_TIER_MAP = {
    TaskCategory.ARCHITECTURE: TaskTier.PRO,
    TaskCategory.CODE_REVIEW: TaskTier.PRO,
    TaskCategory.DEBUGGING: TaskTier.PRO,
    TaskCategory.STYLE_ANALYSIS: TaskTier.PRO,
    TaskCategory.CREATIVE: TaskTier.PRO,
    TaskCategory.TOOL_ORCHESTRATION: TaskTier.PRO,
    TaskCategory.WORKFLOW_DESIGN: TaskTier.PRO,
    TaskCategory.DEEP_QA: TaskTier.PRO,
    TaskCategory.PLANNING: TaskTier.PRO,
    TaskCategory.MULTIMODAL: TaskTier.PRO,
    
    TaskCategory.CAREER_GROWTH: TaskTier.PRO,
    TaskCategory.DAILY_REPORT: TaskTier.PRO,
    TaskCategory.MONTHLY_REPORT: TaskTier.PRO,
    
    TaskCategory.SIMPLE_QA: TaskTier.FLASH,
    TaskCategory.FORMAT_CONVERT: TaskTier.FLASH,
    TaskCategory.TRANSLATION: TaskTier.FLASH,
    TaskCategory.SUMMARIZATION: TaskTier.FLASH,
    TaskCategory.BATCH_PROCESSING: TaskTier.LITE,
    
    TaskCategory.THINKING_TASK: TaskTier.THINKING,
    TaskCategory.CODE_GENERATION: TaskTier.SPECIALIZED,
    TaskCategory.ROLEPLAY: TaskTier.SPECIALIZED,
    TaskCategory.EVOLVING: TaskTier.SPECIALIZED,
    
    TaskCategory.IMAGE_ANALYSIS: TaskTier.VISION_LITE,
    TaskCategory.AE_EFFECT_ANALYSIS: TaskTier.VISION_PRO,
    TaskCategory.KEYFRAME_ANALYSIS: TaskTier.VISION_LITE,
    TaskCategory.SCENE_DETECTION: TaskTier.VISION_LITE,
    TaskCategory.IMAGE_GENERATION: TaskTier.IMAGE_GEN,
    TaskCategory.VIDEO_GENERATION: TaskTier.VIDEO_GEN,
    TaskCategory.TEXT_EMBEDDING: TaskTier.EMBEDDING,
}


MODEL_NAMES = {
    "pro": "deepseek-v4-pro-260425",
    "flash": "deepseek-v4-flash-260425",
    "lite": "doubao-lite-128k-240428",
    "thinking": "doubao-seed-1-6-thinking-250722",
    "specialized": "doubao-seed-code-251228",
    "vision_pro": "doubao-vision-pro-32k-240428",
    "vision_lite": "doubao-vision-lite-32k-240428",
    "image_gen": "doubao-seedream-5-0-pro-260628",
    "video_gen": "doubao-seedance-1-5-pro-251128",  # 2.0不可用，使用1.5
    "embedding": "doubao-embedding-240428",
    
    "doubao_pro": "doubao-seed-2-1-pro-260628",
    "doubao_turbo": "doubao-seed-2-1-turbo-260628",
    "doubao_thinking": "doubao-1-5-thinking-pro-241128",
    "doubao_code": "doubao-seed-code-251228",
    "doubao_translation": "doubao-seed-translation-250722",
    "doubao_character": "doubao-seed-character-251228",
    
    # DuckMiss中转站模型 (可用: claude-sonnet-4-6, claude-opus-4-6/7/8, claude-sonnet-5, claude-fable-5)
    "duckmiss_pro": "claude-opus-4-8",
    "duckmiss_default": "claude-sonnet-4-6",
    "duckmiss_fast": "claude-sonnet-4-6",
    "duckmiss_vision": "claude-sonnet-4-6",  # 多模态支持
    
    # GPT网关模型 (复用DuckMiss Claude)
    "gpt_pro": "claude-opus-4-8",
    "gpt_default": "claude-sonnet-4-6",
    "gpt_fast": "claude-sonnet-4-6",
    "gpt_code": "claude-sonnet-4-6",
    "gpt_vision": "claude-sonnet-4-6",
}


# 中转站多模态模型配置
DUCK_MISS_MODELS = {
    "text": "claude-sonnet-4-6",               # 文本对话（均衡）
    "pro": "claude-opus-4-8",                  # 高质量推理
    "fast": "claude-sonnet-4-6",               # 快速响应
    "vision": "claude-sonnet-4-6",             # 视觉理解（多模态）
    "code": "claude-sonnet-4-6",               # 代码生成
}

# GPT网关模型配置 (复用DuckMiss)
GPT_GATEWAY_MODELS = {
    "text": "claude-sonnet-4-6",
    "pro": "claude-opus-4-8",
    "fast": "claude-sonnet-4-6",
    "vision": "claude-sonnet-4-6",
    "code": "claude-sonnet-4-6",
}

# 模型能力矩阵（用于智能选择最优模型）
MODEL_CAPABILITY_MATRIX = {
    # 任务类型: (最优提供商, 模型, 次选提供商, 模型)
    "visual_analysis": ("claude", "claude-sonnet-4-6", "ark", "ep-20260716122053-t2lst"),
    "deep_reasoning": ("claude", "claude-opus-4-8", "ark", "deepseek-v4-flash-260425"),
    "code_generation": ("claude", "claude-sonnet-4-6", "ark", "deepseek-v4-flash-260425"),
    "fast_classification": ("claude", "claude-sonnet-4-6", "ark", "deepseek-v4-flash-260425"),
    "parameter_inference": ("claude", "claude-opus-4-8", "ark", "deepseek-v4-flash-260425"),
    "color_analysis": ("claude", "claude-sonnet-4-6", "ark", "deepseek-v4-flash-260425"),
    "rhythm_analysis": ("claude", "claude-sonnet-4-6", "ark", "deepseek-v4-flash-260425"),
    "creative_writing": ("claude", "claude-opus-4-8", "ark", "deepseek-v4-flash-260425"),
    "multimodal_understanding": ("claude", "claude-sonnet-4-6", "ark", "ep-20260716122053-t2lst"),
    "complex_planning": ("claude", "claude-opus-4-8", "ark", "deepseek-v4-flash-260425"),
}


class ModelRouter:
    def __init__(self, default_tier: TaskTier = TaskTier.PRO):
        self.default_tier = default_tier
        self._call_stats = {
            "pro": 0, "flash": 0, "lite": 0,
            "thinking": 0, "specialized": 0,
            "vision_pro": 0, "vision_lite": 0,
            "image_gen": 0, "video_gen": 0, "embedding": 0,
        }
    
    def select_model(self, 
                     category: TaskCategory | None = None,
                     force_pro: bool = False,
                     prefer_pro: bool = True) -> str:
        if force_pro:
            tier = TaskTier.PRO
        elif category is not None:
            tier = CATEGORY_TIER_MAP.get(category, self.default_tier)
        else:
            tier = TaskTier.PRO if prefer_pro else self.default_tier
        
        self._call_stats[tier.value] += 1
        return tier.value
    
    def select_for_prompt(self, prompt: str, keywords: dict | None = None) -> str:
        flash_keywords = [
            "翻译", "translate", "转换", "格式", "总结", "摘要",
            "简单", "快速", "简短", "一句话", "简介",
        ]
        
        pro_keywords = [
            "分析", "架构", "设计", "规划", "优化", "审查", "review",
            "调试", "bug", "问题", "为什么", "原理", "深度",
            "风格", "创意", "生成", "工作流", "编排",
            "复杂", "详细", "全面", "系统", "方案",
        ]
        
        thinking_keywords = [
            "思考", "推理", "论证", "逻辑", "推演", "权衡",
            "利弊", "多角度", "全面分析", "深度思考",
        ]
        
        code_keywords = [
            "代码", "编程", "python", "javascript", "java", "cpp",
            "function", "class", "method", "实现", "开发",
        ]
        
        translate_keywords = [
            "翻译", "英语", "中文", "日语", "韩语", "法语",
            "德语", "西班牙语", "俄语", "翻译为",
        ]
        
        roleplay_keywords = [
            "扮演", "模拟", "对话", "角色扮演", "情景", "场景",
        ]
        
        vision_keywords = [
            "图片", "图像", "照片", "截图", "视觉", "识别",
            "效果", "特效", "画面", "帧",
        ]
        
        image_gen_keywords = [
            "生成图片", "画", "创作", "设计", "配图", "海报",
            "插画", "绘画", "生成图像",
        ]
        
        prompt_lower = prompt.lower()
        
        pro_score = sum(1 for kw in pro_keywords if kw in prompt_lower)
        flash_score = sum(1 for kw in flash_keywords if kw in prompt_lower)
        thinking_score = sum(1 for kw in thinking_keywords if kw in prompt_lower)
        code_score = sum(1 for kw in code_keywords if kw in prompt_lower)
        translate_score = sum(1 for kw in translate_keywords if kw in prompt_lower)
        roleplay_score = sum(1 for kw in roleplay_keywords if kw in prompt_lower)
        vision_score = sum(1 for kw in vision_keywords if kw in prompt_lower)
        image_gen_score = sum(1 for kw in image_gen_keywords if kw in prompt_lower)
        
        max_score = max(pro_score, flash_score, thinking_score, 
                        code_score, translate_score, roleplay_score,
                        vision_score, image_gen_score)
        
        if code_score >= 2 and code_score == max_score:
            self._call_stats["specialized"] += 1
            return "specialized"
        elif translate_score >= 2 and translate_score == max_score:
            self._call_stats["flash"] += 1
            return "flash"
        elif thinking_score >= 2 and thinking_score == max_score:
            self._call_stats["thinking"] += 1
            return "thinking"
        elif roleplay_score >= 2 and roleplay_score == max_score:
            self._call_stats["specialized"] += 1
            return "specialized"
        elif image_gen_score >= 2 and image_gen_score == max_score:
            self._call_stats["image_gen"] += 1
            return "image_gen"
        elif vision_score >= 2 and vision_score == max_score:
            self._call_stats["vision_lite"] += 1
            return "vision_lite"
        elif pro_score > flash_score:
            self._call_stats["pro"] += 1
            return "pro"
        elif flash_score > pro_score and flash_score >= 2:
            self._call_stats["flash"] += 1
            return "flash"
        else:
            self._call_stats["pro"] += 1
            return "pro"
    
    @property
    def stats(self) -> dict[str, int]:
        return dict(self._call_stats)
    
    def reset_stats(self):
        self._call_stats = {
            "pro": 0, "flash": 0, "lite": 0,
            "thinking": 0, "specialized": 0,
            "vision_pro": 0, "vision_lite": 0,
            "image_gen": 0, "video_gen": 0, "embedding": 0,
        }


_default_router = ModelRouter(default_tier=TaskTier.PRO)


def select_model(category: TaskCategory | None = None, 
                 force_pro: bool = False,
                 prefer_pro: bool = True) -> str:
    return _default_router.select_model(
        category=category, 
        force_pro=force_pro, 
        prefer_pro=prefer_pro
    )


def select_for_prompt(prompt: str) -> str:
    return _default_router.select_for_prompt(prompt)


def get_router_stats() -> dict[str, int]:
    return _default_router.stats


def get_model_name(tier: str) -> str:
    return MODEL_NAMES.get(tier, "deepseek-v4-pro-260425")


def get_model_provider(tier: str) -> str:
    if tier.startswith("doubao") or tier in ["image_gen", "video_gen", "embedding"]:
        return "doubao"
    return "deepseek"


def get_all_available_models() -> dict[str, list[str]]:
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
            "doubao-vision-lite-32k-240428",
            "doubao-seed-1-6-vision-250722",
        ],
        "image_gen": [
            "doubao-seedream-5-0-pro-260628",
            "doubao-seedream-5-0-260128",
            "doubao-seedream-4-5-251128",
        ],
        "video_gen": [
            "doubao-seedance-2-0-260128",
            "doubao-seedance-2-0-fast-260128",
            "doubao-seedance-1-5-pro-251128",
        ],
        "embedding": [
            "doubao-embedding-240428",
            "doubao-embedding-large-240428",
            "doubao-embedding-vision-240428",
        ],
        "3d_gen": [
            "doubao-seed3d-2-0-251228",
            "hyper3d-gen2-260128",
        ],
    }
