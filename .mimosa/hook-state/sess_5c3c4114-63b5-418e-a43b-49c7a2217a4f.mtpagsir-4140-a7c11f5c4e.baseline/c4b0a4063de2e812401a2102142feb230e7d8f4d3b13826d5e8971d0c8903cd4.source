"""pipeline.prompts - 创意规划提示词集合。

为 ``pipeline.minimal_creative_loop`` 提供所有 LLM 提示词定义与模板，
覆盖不同内容类型（文字动画 / 动态图形 / 歌词视频 / 产品展示 / 转场）、
不同风格预设（电影感 / 复古 / 霓虹 / 极简 / 暗黑 等）的领域知识。

所有提示词遵循以下原则：

1. **结构化输出**：要求 LLM 必须输出符合 ``CreativePlan`` 的 JSON Schema，
   避免自然语言模糊，便于下游 ``_parse_llm_plan`` 解析。
2. **可降级**：当 LLM 失败或输出非法 JSON 时，由 ``_fallback_plan`` 接管，
   不会阻断主流程。
3. **领域知识注入**：将不同风格、不同内容类型的最佳实践浓缩到提示词中，
   让 LLM 生成更专业的规划。

模块列表
========

- :mod:`pipeline.prompts.creative_planning`  - 创意规划核心提示词
"""
from pipeline.prompts.creative_planning import (
    ContentType,
    StylePreset,
    SYSTEM_PROMPT_CREATIVE_PLANNING,
    CONTENT_TYPE_TEMPLATES,
    STYLE_DESCRIPTIONS,
    STYLE_PRESET_MAP,
    build_user_prompt,
    build_system_prompt,
)

__all__ = [
    "ContentType",
    "StylePreset",
    "SYSTEM_PROMPT_CREATIVE_PLANNING",
    "CONTENT_TYPE_TEMPLATES",
    "STYLE_DESCRIPTIONS",
    "STYLE_PRESET_MAP",
    "build_user_prompt",
    "build_system_prompt",
]
