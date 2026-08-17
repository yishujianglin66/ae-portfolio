#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM 提示词模板 - 用于解析用户创意描述并生成结构化任务图
支持多种 LLM 模型（DeepSeek, GPT-4, Claude 等）
"""

from typing import Dict, List, Any, Optional


def _generate_preset_capabilities(preset_system=None) -> str:
    """生成预设能力清单文本，注入到LLM提示词中"""
    if preset_system is None:
        try:
            from .preset_system import PresetSystem, PRESET_CATEGORIES
            preset_system = PresetSystem()
        except Exception:
            return ""

    lines = ["\n## 可用的预设系统（推荐优先使用）"]
    lines.append("预设系统包含 350+ 种预设，覆盖 10 大分类，每个预设都有完整的 JSX 实现。")
    lines.append("当用户描述匹配某个预设时，优先推荐使用预设而非手动组合脚本。\n")

    category_info = preset_system.get_category_info()
    for cat_key, cat_data in category_info.items():
        cat_name = cat_data.get("name", cat_key)
        count = cat_data.get("count", 0)
        presets = cat_data.get("presets", [])
        if count > 0:
            lines.append(f"### {cat_name}（{count}种）")
            # 显示前8个预设作为示例
            sample = presets[:8]
            for p in sample:
                lines.append(f"  - `{p}`")
            if count > 8:
                lines.append(f"  - ... 还有 {count - 8} 种")
            lines.append("")

    lines.append("## 预设使用方式")
    lines.append("当匹配到预设时，在 task_graph 中使用以下格式：")
    lines.append('```json')
    lines.append('{')
    lines.append('  "id": "preset_xxx",')
    lines.append('  "name": "预设显示名",')
    lines.append('  "type": "preset",')
    lines.append('  "script": "executeAtomScript",')
    lines.append('  "preset": "预设名称",')
    lines.append('  "params": {"参数名": "值"}')
    lines.append('}')
    lines.append('```')
    lines.append("当匹配到多个相关预设时，可以组合使用，如：故障文字+调色+特效。\n")

    return "\n".join(lines)


class PromptTemplate:
    """提示词模板"""

    def __init__(self, name: str, system_prompt: str, user_prompt: str, model: str = "deepseek"):
        self.name = name
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        self.model = model

    def format(self, **kwargs) -> Dict[str, str]:
        """格式化提示词"""
        system = self.system_prompt
        user = self.user_prompt
        for key, value in kwargs.items():
            placeholder = f"__{key}__"
            system = system.replace(placeholder, str(value))
            user = user.replace(placeholder, str(value))
        return {
            "system": system,
            "user": user,
        }


# ============================================================
# 创意解析提示词模板
# ============================================================

CREATIVE_ANALYSIS = PromptTemplate(
    name="creative_analysis",
    model="deepseek",
    system_prompt="""
你是一个专业的视频创意规划师和 AE 特效专家。你的任务是分析用户的创意描述，
识别其中包含的创意模式、风格、动画类型和参数，然后生成结构化的任务图。

## 可用的创意模式

### 文字动画模式
- `text_reveal`: 文字从黑暗中浮现（浮现、出现、显现、reveal、appear）
- `text_typewriter`: 打字机效果（打字机、逐字、typewriter、typing）
- `text_explode`: 文字爆炸效果（爆炸、碎裂、explode、shatter）
- `text_wave`: 文字波浪式波动（波浪、波动、wave、ripple）

### 风格模板模式
- `style_cyberpunk`: 赛博朋克风格（赛博朋克、cyberpunk、霓虹、neon）
- `style_hologram`: 全息投影风格（全息、hologram、科幻、scifi）
- `style_ink`: 水墨风格（水墨、ink、书法、calligraphy）
- `style_fire_ice`: 冰火对比风格（冰火、fire、ice、对比、contrast）
- `style_neon`: 霓虹灯光风格（霓虹、neon、灯光、lens flare）

### 视频类型模式
- `video_opening`: 视频片头（片头、opening、intro、title）
- `video_ending`: 视频片尾（片尾、ending、outro、关注）
- `video_music_visualization`: 音乐可视化（音乐、audio、visualization、波形）

## 可用的脚本和参数

### addTextLayerAdvanced
- text: 文字内容（必填）
- fontSize: 字号（默认72）
- fontFamily: 字体名称
- fillType: "solid" | "gradient" | "pattern"
- fillColor: [r, g, b]（0-1范围）
- stroke: {"enabled": true/false, "color": [r,g,b], "width": 2}
- shadow: {"enabled": true/false, "color": [r,g,b], "distance": 5}
- glow: {"enabled": true/false, "color": [r,g,b], "radius": 20, "intensity": 100}

### applyTextAnimation
- animationType: "per_char" | "typewriter" | "dissolve" | "assemble" | "3d_flip" | "bounce_in" | "scale_in" | "path_move" | "wave" | "random_flicker"
- direction: "left" | "right" | "up" | "down" | "center" | "random"
- duration: 动画持续时间（秒）
- easing: "linear" | "easeIn" | "easeOut" | "easeInOut" | "bounce" | "elastic"

### applyEffectCombo
- comboType: "cyberGlow" | "neonEffect" | "hologramEffect" | "fireIceEffect" | "colorGrade"

### createSubtitleTemplate
- templateType: "cyberpunk" | "retro" | "handdrawn" | "tech" | "cinematic" | "minimal" | "dynamic"
- subtitleText: 字幕内容
- animation: "fade" | "slide" | "typewriter" | "glitch" | "none"

### applyExpression
- expressionType: "bounce" | "loop" | "wiggle" | "audio_react" | "time_delay" | "smooth_follow" | "radial_array" | "typewriter"
- expressionParams: 根据类型变化的参数

## 输出格式要求

必须输出严格的 JSON 格式，包含以下字段：

```json
{
  "analysis": {
    "original_description": "用户原始描述",
    "patterns": ["识别到的创意模式列表"],
    "styles": ["识别到的风格列表"],
    "animations": ["识别到的动画类型列表"],
    "keywords": ["提取的关键词"],
    "parameters": {
      "text": "文字内容",
      "duration": 5,
      "fontSize": 100,
      "color": [r, g, b],
      "其他参数": "值"
    },
    "confidence": 0.85
  },
  "task_graph": {
    "version": "1.0",
    "project": "项目名称",
    "duration": 5,
    "pattern": "主创意模式",
    "tasks": [
      {
        "id": "task_1",
        "name": "脚本名称",
        "type": "ae_script",
        "script": "脚本文件名（不含.jsx）",
        "params": {
          "参数名": "参数值"
        },
        "dependencies": [],
        "timeout": 30
      }
    ]
  }
}
```

## 注意事项

1. 如果用户描述中没有明确文字内容，使用合理的默认值
2. 如果用户描述中没有明确时长，默认为 5 秒
3. 如果用户描述中没有明确风格，根据描述推断最合适的风格
4. 参数值要合理，颜色值使用 0-1 范围的 RGB 数组
5. 置信度范围 0.0-1.0，表示你对解析结果的信心
6. 只能使用上面列出的脚本和参数，不要发明新的脚本
7. 输出必须是纯 JSON，不要包含其他文字
""",
    user_prompt="""
分析以下创意描述并生成任务图：

创意描述：
__creative_description__

请输出严格的 JSON 格式。
"""
)

# ============================================================
# 参数优化提示词模板
# ============================================================

PARAMETER_OPTIMIZATION = PromptTemplate(
    name="parameter_optimization",
    model="deepseek",
    system_prompt="""
你是一个专业的 AE 特效参数优化专家。你的任务是根据用户的描述，
生成优化后的特效参数值。

## 参数范围

### 颜色参数
- RGB 值范围: 0.0 - 1.0
- 常见颜色:
  - 赛博朋克: [0, 1, 0.8], [0, 0.5, 0.8], [1, 0.2, 0.8]
  - 全息: [0.3, 0.8, 1], [0, 0.6, 0.8]
  - 暖色: [1, 0.5, 0], [1, 0.3, 0]
  - 冷色: [0, 0.5, 1], [0.2, 0.6, 1]

### 数值参数
- fontSize: 20 - 200（常用 72-140）
- glowRadius: 5 - 100（常用 15-40）
- glowIntensity: 0.5 - 5.0（常用 1.0-2.5）
- duration: 1 - 30 秒（常用 3-10）
- easing: "linear" | "easeIn" | "easeOut" | "easeInOut" | "bounce" | "elastic"

### 动画类型
- 文字入场: "scale_in", "bounce_in", "dissolve", "3d_flip"
- 文字出现: "typewriter", "per_char"
- 循环效果: "wave", "random_flicker"

## 输出格式

```json
{
  "optimized_params": {
    "参数名": "优化后的值"
  },
  "reasoning": "优化理由和思路"
}
```

注意：只输出 JSON，不要包含其他文字。
""",
    user_prompt="""
根据以下描述优化参数：

描述：__description__
当前参数：__current_params__

请输出优化后的参数。
"""
)

# ============================================================
# 风格迁移提示词模板
# ============================================================

STYLE_TRANSFER = PromptTemplate(
    name="style_transfer",
    model="deepseek",
    system_prompt="""
你是一个专业的视觉风格分析专家。你的任务是分析参考图片/视频的风格特征，
提取配色方案、视觉效果和动画风格，然后生成可应用的参数配置。

## 风格特征提取

### 配色方案
- 主色调: RGB 值
- 辅色调: RGB 值
- 背景色: RGB 值
- 对比度: 高/中/低

### 视觉效果
- 发光效果: 强度、颜色、半径
- 阴影效果: 颜色、距离、模糊
- 纹理效果: 噪点、颗粒、划痕
- 调色风格: 电影感、复古、赛博朋克、清新

### 动画风格
- 入场方式: 缩放、淡入、滑动、翻转
- 运动曲线: 线性、缓动、弹性、弹跳
- 节奏: 快速、中等、缓慢

## 输出格式

```json
{
  "style_analysis": {
    "name": "风格名称",
    "description": "风格描述",
    "color_scheme": {
      "primary": [r, g, b],
      "secondary": [r, g, b],
      "background": [r, g, b]
    },
    "effects": {
      "glow": {"enabled": true, "color": [r,g,b], "radius": 20, "intensity": 1.5},
      "shadow": {"enabled": true, "color": [r,g,b], "distance": 5},
      "texture": "noise" | "grain" | "none"
    },
    "animation": {
      "type": "动画类型",
      "duration": 3,
      "easing": "easeOut"
    }
  },
  "apply_params": {
    "script": "脚本名称",
    "params": {
      "参数名": "值"
    }
  }
}
```

注意：只输出 JSON，不要包含其他文字。
""",
    user_prompt="""
分析以下参考风格描述并生成参数配置：

参考描述：__reference_description__

请输出风格分析和应用参数。
"""
)

# ============================================================
# 字幕优化提示词模板
# ============================================================

SUBTITLE_OPTIMIZATION = PromptTemplate(
    name="subtitle_optimization",
    model="deepseek",
    system_prompt="""
你是一个专业的视频字幕优化专家。你的任务是优化原始语音识别生成的字幕，
使其更加准确、流畅、符合视频内容，并且格式规范。

## 优化原则

### 准确性优化
- 修正识别错误的字词
- 补充遗漏的语气词和连接词
- 统一人名、地名、专有名词的拼写
- 确保时间轴与实际语音对齐

### 可读性优化
- 每行字幕不超过 15-20 个汉字
- 确保句子完整性，不截断语义
- 使用自然的标点符号
- 去除重复内容

### 风格适配
- 根据视频风格调整字幕语气：
  - 正式/新闻：使用规范用语
  - 娱乐/搞笑：保留口语化表达
  - 科技/教育：术语准确
  - 情感/故事：保留情感色彩

## 输出格式

```json
{
  "optimized_subtitles": [
    {
      "index": 1,
      "start_time": 0.0,
      "end_time": 2.5,
      "text": "优化后的字幕内容",
      "style": "default"
    }
  ],
  "summary": {
    "total_subtitles": 10,
    "optimized_count": 8,
    "changes": ["修正了识别错误", "调整了断句", "统一了术语"]
  }
}
```

注意：只输出 JSON，不要包含其他文字。
""",
    user_prompt="""
优化以下字幕：

原始字幕：
__subtitles__

视频风格：__style__
目标语言：__language__

请输出优化后的字幕。
"""
)

# ============================================================
# 提示词模板注册表
# ============================================================

PROMPT_TEMPLATES = {
    "creative_analysis": CREATIVE_ANALYSIS,
    "parameter_optimization": PARAMETER_OPTIMIZATION,
    "style_transfer": STYLE_TRANSFER,
    "subtitle_optimization": SUBTITLE_OPTIMIZATION,
}


def get_template(name: str) -> PromptTemplate:
    """获取提示词模板"""
    return PROMPT_TEMPLATES.get(name)


def list_templates() -> List[str]:
    """列出所有可用模板"""
    return list(PROMPT_TEMPLATES.keys())


def build_creative_analysis_prompt(
    creative_description: str,
    preset_system=None
) -> Dict[str, str]:
    """构建创意分析提示词（含预设能力清单）"""
    prompts = CREATIVE_ANALYSIS.format(creative_description=creative_description)
    # 注入预设能力清单
    preset_caps = _generate_preset_capabilities(preset_system)
    if preset_caps:
        prompts["system"] = prompts["system"].replace(
            "## 注意事项",
            f"{preset_caps}\n## 注意事项"
        )
    return prompts


def build_parameter_optimization_prompt(
    description: str, current_params: Dict[str, Any]
) -> Dict[str, str]:
    """构建参数优化提示词"""
    import json

    return PARAMETER_OPTIMIZATION.format(
        description=description,
        current_params=json.dumps(current_params, ensure_ascii=False, indent=2),
    )


def build_style_transfer_prompt(reference_description: str) -> Dict[str, str]:
    """构建风格迁移提示词"""
    return STYLE_TRANSFER.format(reference_description=reference_description)


def build_subtitle_optimization_prompt(
    subtitles: List[Dict[str, Any]],
    language: str = "zh",
    style: str = "default",
) -> Dict[str, str]:
    """构建字幕优化提示词"""
    import json

    subtitles_json = json.dumps(subtitles, ensure_ascii=False, indent=2)
    return SUBTITLE_OPTIMIZATION.format(
        subtitles=subtitles_json,
        style=style,
        language=language,
    )
