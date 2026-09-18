"""创意规划提示词定义。

为 ``pipeline.minimal_creative_loop.MinimalCreativeLoop`` 提供：

- :data:`ContentType` / :data:`StylePreset` - 创意规划枚举
- :data:`SYSTEM_PROMPT_CREATIVE_PLANNING` - 通用创意规划系统提示词
- :data:`CONTENT_TYPE_TEMPLATES` - 按内容类型附加的领域知识
- :data:`STYLE_DESCRIPTIONS` - 按风格预设附加的视觉描述
- :data:`STYLE_PRESET_MAP` - 风格枚举到 DaVinci 调色预设的映射
- :func:`build_system_prompt` - 动态拼接系统提示词
- :func:`build_user_prompt` - 动态拼装用户提示词

设计原则
========

1. **Caveman 风格压缩**：提示词中的冗余修饰词被替换为简短表达，
   节省 token 同时保留关键信息。
2. **JSON Schema 约束**：在系统提示词中直接给出 ``CreativePlan`` 字段，
   让 LLM 输出可被 ``_parse_llm_plan`` 解析。
3. **领域知识注入**：每种内容类型、每种风格都附带专业描述（如电影感
   青橙调色、复古胶片、音乐 MV 冲击等），无需外部知识库查询。

注意
====

为避免 ``pipeline.minimal_creative_loop`` 与 ``pipeline.prompts`` 之间的
循环导入，本模块**定义并导出** ``ContentType`` / ``StylePreset`` 枚举；
主循环模块会从本模块再导出。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Tuple

# ============================================================================
# 内容类型枚举（与 minimal_creative_loop 中 re-export 保持一致）
# ============================================================================

class ContentType(Enum):
    """内容类型。"""

    TEXT_ANIMATION = "text_animation"      # 纯文字动画
    MOTION_GRAPHICS = "motion_graphics"    # 动态图形
    LYRIC_VIDEO = "lyric_video"            # 歌词视频
    PRODUCT_SHOWCASE = "product_showcase"  # 产品展示
    TRANSITION_EFFECT = "transition_effect"  # 转场效果


class StylePreset(Enum):
    """风格预设。"""

    CARTOON = "cartoon"                    # 卡通
    CINEMATIC = "cinematic"                # 电影感
    NEON = "neon"                          # 霓虹
    VINTAGE = "vintage"                    # 复古
    MINIMAL = "minimal"                    # 极简
    ENERGETIC = "energetic"                # 活力
    ROMANTIC = "romantic"                  # 浪漫
    DARK_MOOD = "dark_mood"                # 暗黑


# ============================================================================
# 通用系统提示词（CreativePlan JSON Schema）
# ============================================================================

SYSTEM_PROMPT_CREATIVE_PLANNING: str = """你是 AE 视频自动化专家。给定用户描述，输出 JSON 格式的结构化创意规划。

# 角色
- 视频创意总监：理解用户意图、规划画面结构、编排关键帧
- 调色顾问：根据风格选择合适的视觉表达

# 原则
- 只输出 JSON，不要任何解释、Markdown 包装或代码块
- 所有字段都按下方 Schema 填充，缺省值用 null / [] / 0.0
- 数值采用 AE 标准单位（时间为秒、位置为像素、颜色为 [R,G,B] 0-1 范围）
- 图层、关键帧、效果的数量要少而精（≤ 6 个）

# JSON Schema
{
  "comp_name": "string",                     // 合成名称
  "duration": float,                          // 时长（秒）
  "fps": float,                               // 帧率
  "resolution": [width, height],              // 分辨率
  "background": {                             // 背景
    "type": "solid|gradient",                 // 背景类型
    "color": [r, g, b] or null,               // 纯色 (0-1)
    "gradient": {                             // 渐变参数（type=gradient 时填）
      "from": [r, g, b],
      "to": [r, g, b],
      "angle": float
    } or null
  },
  "layers": [                                 // 图层列表
    {
      "type": "text|shape|solid|adjustment",  // 图层类型
      "name": "string",                       // 图层名称
      "properties": {                         // 类型相关参数
        "text": "string or null",             // text 专属
        "font_size": float,                   // text 专属
        "color": [r, g, b],                   // text/solid
        "font_family": "string",              // text 专属
        "shape": "rect|ellipse|star|polygon", // shape 专属
        "size": [w, h],                       // shape/solid 专属
        "position": [x, y]                    // 位置（默认居中）
      }
    }
  ],
  "keyframes": [                               // 关键帧列表
    {
      "layer_name": "string",                 // 作用图层
      "property": "Position|Scale|Rotation|Opacity|...|Anchor Point",
      "time": float,                          // 关键帧时间（秒）
      "value": [...],                         // 关键帧值
      "easing": "linear|easeIn|easeOut|easeInOut"  // 缓动（可选）
    }
  ],
  "effects": [                                 // 效果列表
    {
      "layer_name": "string",
      "effect_name": "Glow|Drop Shadow|...|CC Ball Action|...|Gaussian Blur",
      "settings": { ... }                     // 效果参数
    }
  ],
  "text_content": "string or null",           // 主要文字内容
  "text_style": {                             // 文字主样式
    "font_size": float,
    "color": [r, g, b],
    "font_family": "string",
    "alignment": "left|center|right"
  } or null,
  "color_grading": {                          // 调色方案
    "preset_name": "string or null",          // DaVinci 调色预设名
    "style_description": "string"             // 调色思路（人类可读）
  } or null,
  "estimated_complexity": float               // 复杂度 0.0-1.0
}
"""


# ============================================================================
# 内容类型附加模板
# ============================================================================

CONTENT_TYPE_TEMPLATES: dict[ContentType, str] = {
    ContentType.TEXT_ANIMATION: """# 内容类型：文字动画
- 核心：字体选择、节奏、动效、转场
- 推荐图层结构：背景层 + 文字层（1-3 个），可加 adjustment 层做全局调色
- 关键帧重点：Position / Scale / Opacity / Rotation，0.3-0.8s 节奏
- 推荐效果：Glow、Drop Shadow、CC Ball Action、CC Scale Wipe
- 文字大小：1080p 下 60-120pt 适合标题，30-50pt 适合副标题
- 动画原则：缓入缓出（easeInOut），避免匀速直线""",

    ContentType.MOTION_GRAPHICS: """# 内容类型：动态图形（MG）
- 核心：形状动画、循环节奏、信息可视化
- 推荐图层结构：背景 + 多个 shape layer（rect/ellipse/polygon），可加 text
- 关键帧重点：Position / Scale / Rotation，2-4 个图层错落动画
- 推荐效果：Trim Paths、Repeater、CC Sphere、Mercury
- 配色：2-3 个主色 + 1 强调色
- 节奏：每 2-3 秒一个完整动作循环""",

    ContentType.LYRIC_VIDEO: """# 内容类型：歌词视频
- 核心：歌词逐句展示、节拍同步、字体节奏
- 推荐图层结构：背景层 + 当前歌词 + 高亮歌词 + 翻译歌词（可选）
- 关键帧重点：Opacity（淡入淡出）、Position（推入推出）、Scale（弹跳）
- 推荐效果：Glow（高亮当前句）、Sweep（扫光）、CC Light Sweep
- 颜色：当前句用高对比色，已播句降饱和
- 时间分配：每句歌词 1.5-3 秒""",

    ContentType.PRODUCT_SHOWCASE: """# 内容类型：产品展示
- 核心：产品居中、光照、动态文字
- 推荐图层结构：背景渐变 + 模拟产品占位（用 text/shape 代替）+ 文案层
- 关键帧重点：Scale（呼吸感 1.0-1.05）、Position（缓慢平移）、Opacity
- 推荐效果：Glow（产品边缘光）、Drop Shadow（立体感）、CC Lens
- 配色：白底 + 1 强调色 或 深色高端质感
- 时长：10 秒内展示 1-2 个核心卖点""",

    ContentType.TRANSITION_EFFECT: """# 内容类型：转场效果
- 核心：转场曲线、能量节奏、视觉冲击
- 推荐图层结构：转场层（shape）+ 装饰元素
- 关键帧重点：Scale、Opacity、Rotation
- 推荐效果：CC Glass Wipe、CC Grid Wipe、Radial Wipe、Light Sweep
- 节奏：前 0.3s 慢启动，0.3-0.7s 加速，0.7-1.0s 完成
- 颜色：黑/白/纯色为主，少量高光""",
}


# ============================================================================
# 风格描述
# ============================================================================

STYLE_DESCRIPTIONS: dict[StylePreset, str] = {
    StylePreset.CARTOON: """# 风格：卡通
- 颜色：高饱和、原色为主（红/黄/蓝/绿）
- 字体：圆润、卡通体（如 Source Han Sans Rounded）
- 动效：弹跳、夸张、节奏感强
- 调色：明亮、对比适中、轻微暖色偏移
- 适用：儿童内容、趣味短片、动画 MV""",

    StylePreset.CINEMATIC: """# 风格：电影感
- 颜色：阴影偏青、高光偏暖（teal & orange 经典组合）
- 字体：粗体无衬线（如 Impact、Helvetica Bold）
- 动效：缓慢、克制、有戏剧感
- 调色：cinematic_teal_orange，对比 1.10，饱和 1.15
- 适用：电影感短片、MV、片头""",

    StylePreset.NEON: """# 风格：霓虹
- 颜色：荧光色（品红/青/紫/绿），深色背景
- 字体：现代科技感（如 Orbitron、Rajdhani）
- 动效：发光、闪烁、抖动
- 调色：music_video_punch，饱和 1.30，对比 1.20
- 效果：必加 Glow，强度 0.5-1.0
- 适用：电子音乐、赛博朋克、潮流短片""",

    StylePreset.VINTAGE: """# 风格：复古
- 颜色：暖黄、褐色、低饱和
- 字体：衬线体、复古印刷感（如 Playfair Display）
- 动效：缓慢淡入、轻微抖动（模拟胶片）
- 调色：vintage_film，饱和 0.85，暖色偏移
- 效果：可加噪波（Noise）、色调分离（Posterize）
- 适用：怀旧风格、老电影、复古 MV""",

    StylePreset.MINIMAL: """# 风格：极简
- 颜色：黑/白/灰/1 个强调色
- 字体：细体无衬线（如 Helvetica Light、Avenir）
- 动效：缓慢优雅的淡入、缓慢平移
- 调色：high_key_bright，对比 0.90，饱和 1.05
- 效果：极少使用，只在关键点用模糊/遮罩
- 适用：品牌片、文艺短片、纪录片""",

    StylePreset.ENERGETIC: """# 风格：活力
- 颜色：高饱和、对比强烈（红/橙/黄/蓝）
- 字体：粗体动感（如 Bebas Neue、Bebas）
- 动效：快速、弹跳、缩放冲击
- 调色：music_video_punch，饱和 1.30
- 效果：CC Scale Wipe、Radial Blur（瞬间）
- 适用：运动集锦、快剪、活力 MV""",

    StylePreset.ROMANTIC: """# 风格：浪漫
- 颜色：粉/桃/暖金/柔白
- 字体：优雅衬线（如 Georgia、Times Italic）
- 动效：缓慢淡入、轻柔缩放
- 调色：warm_portrait，饱和 1.05
- 效果：Glow（柔光）、ProShift（柔焦）
- 适用：婚礼、爱情短片、文艺告白""",

    StylePreset.DARK_MOOD: """# 风格：暗黑
- 颜色：深色为主（深蓝/黑/暗红），少量高光
- 字体：粗体厚重（如 Trajan、Bebas Neue）
- 动效：缓慢、压抑、爆发
- 调色：low_key_dark，对比 1.25，饱和 0.90
- 效果：可加 CC Vignette（暗角）、Tritone（三色调）
- 适用：悬疑、惊悚、暗黑 MV""",
}


# ============================================================================
# 风格 → DaVinci 调色预设映射
# ============================================================================

STYLE_PRESET_MAP: dict[StylePreset, str] = {
    StylePreset.CARTOON: "high_key_bright",
    StylePreset.CINEMATIC: "cinematic_teal_orange",
    StylePreset.NEON: "music_video_punch",
    StylePreset.VINTAGE: "vintage_film",
    StylePreset.MINIMAL: "high_key_bright",
    StylePreset.ENERGETIC: "music_video_punch",
    StylePreset.ROMANTIC: "warm_portrait",
    StylePreset.DARK_MOOD: "low_key_dark",
}


# ============================================================================
# 动态拼装函数
# ============================================================================

def build_system_prompt(
    content_type: ContentType,
    style: StylePreset,
) -> str:
    """根据内容类型和风格动态拼装系统提示词。

    Args:
        content_type: 内容类型（决定附加的领域知识）。
        style: 风格预设（决定附加的视觉描述）。

    Returns:
        完整的系统提示词（包含通用 Schema + 内容类型 + 风格）。
    """
    parts: list[str] = [SYSTEM_PROMPT_CREATIVE_PLANNING]
    type_tpl = CONTENT_TYPE_TEMPLATES.get(content_type)
    if type_tpl:
        parts.append(type_tpl)
    style_desc = STYLE_DESCRIPTIONS.get(style)
    if style_desc:
        parts.append(style_desc)
    return "\n\n".join(parts)


def build_user_prompt(
    description: str,
    content_type: ContentType,
    style: StylePreset,
    duration: float,
    resolution: tuple[int, int],
    frame_rate: float,
    additional_context: dict[str, Any] | None = None,
) -> str:
    """拼装用户提示词。

    Args:
        description: 用户原始描述。
        content_type: 内容类型。
        style: 风格预设。
        duration: 视频时长（秒）。
        resolution: 分辨率 ``(width, height)``。
        frame_rate: 帧率（fps）。
        additional_context: 额外上下文（附加参数、风格关键词等），可选。

    Returns:
        完整用户提示词。
    """
    lines: list[str] = [
        "# 用户需求",
        f"描述：{description}",
        f"内容类型：{content_type.value}",
        f"风格：{style.value}",
        f"时长：{duration:.1f} 秒",
        f"分辨率：{resolution[0]} x {resolution[1]}",
        f"帧率：{frame_rate:.1f} fps",
    ]
    if additional_context:
        lines.append("")
        lines.append("# 附加上下文")
        for key, value in additional_context.items():
            lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "# 输出",
        "输出符合 Schema 的 JSON。确保：",
        "1. comp_name 简短可读（英文/拼音，不要空格）",
        "2. 关键帧和效果数量合理（≤ 6）",
        "3. 颜色值在 [0, 1] 范围内",
        "4. time 在 [0, duration] 范围内",
        "5. estimated_complexity 在 [0, 1] 范围内",
    ])
    return "\n".join(lines)


__all__ = [
    "ContentType",
    "StylePreset",
    "SYSTEM_PROMPT_CREATIVE_PLANNING",
    "CONTENT_TYPE_TEMPLATES",
    "STYLE_DESCRIPTIONS",
    "STYLE_PRESET_MAP",
    "build_system_prompt",
    "build_user_prompt",
]
