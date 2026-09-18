#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创意模式库 - 预定义常见的创意模式和脚本组合
每个模式定义了从创意描述到 AE 脚本执行的映射关系
"""

from typing import Any, Dict, List


class CreativePattern:
    """创意模式定义"""

    def __init__(
        self,
        name: str,
        description: str,
        keywords: list[str],
        script_sequence: list[dict[str, Any]],
        default_params: dict[str, Any] = None,
    ):
        self.name = name
        self.description = description
        self.keywords = keywords
        self.script_sequence = script_sequence
        self.default_params = default_params or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "keywords": self.keywords,
            "script_sequence": self.script_sequence,
            "default_params": self.default_params,
        }


# ============================================================
# 文字动画模式
# ============================================================

TEXT_REVEAL = CreativePattern(
    name="text_reveal",
    description="文字从黑暗中浮现，带有发光效果",
    keywords=["浮现", "出现", "显现", "reveal", "appear"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0, 1, 0.8], "radius": 25, "intensity": 2.0},
                "shadow": {"enabled": True, "color": [0, 0, 0], "distance": 8},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "dissolve",
                "direction": "up",
                "duration": "{{duration}}",
                "easing": "easeOut",
            },
        },
    ],
    default_params={"font_size": 120},
)

TEXT_TYPEWRITER = CreativePattern(
    name="text_typewriter",
    description="打字机效果，逐字显示文字",
    keywords=["打字机", "逐字", "typewriter", "typing"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "fontFamily": "Consolas",
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "typewriter",
                "duration": "{{duration}}",
                "speed": "{{speed}}",
                "cursor": "|",
            },
        },
    ],
    default_params={"font_size": 80, "speed": 8},
)

TEXT_EXPLODE = CreativePattern(
    name="text_explode",
    description="文字爆炸效果，碎片四散",
    keywords=["爆炸", "碎裂", "explode", "shatter"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
            },
        },
        {
            "script": "applyExpression",
            "params": {
                "expressionType": "wiggle",
                "expressionParams": {"frequency": 10, "amount": 50},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "fireIceEffect"},
        },
    ],
    default_params={"font_size": 140},
)

TEXT_WAVE = CreativePattern(
    name="text_wave",
    description="文字波浪式波动效果",
    keywords=["波浪", "波动", "wave", "ripple"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.5, 0.8, 1], "radius": 15},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "wave",
                "waveHeight": "{{wave_height}}",
                "waveFrequency": "{{wave_freq}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 100, "wave_height": 30, "wave_freq": 3},
)

TEXT_BOUNCE_IN = CreativePattern(
    name="text_bounce_in",
    description="文字弹跳进入效果，带有弹性缓冲",
    keywords=["弹跳", "弹入", "bounce", "弹性"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [1, 0.6, 0], "radius": 20},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "bounce_in",
                "bounceCount": "{{bounce_count}}",
                "duration": "{{duration}}",
                "easing": "easeOut",
            },
        },
    ],
    default_params={"font_size": 120, "bounce_count": 2},
)

TEXT_SCALE_IN = CreativePattern(
    name="text_scale_in",
    description="文字缩放进入效果，从中心向外扩展",
    keywords=["缩放", "放大", "scale", "grow"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.8, 0.2, 1], "radius": 25},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "scale_in",
                "startScale": 0,
                "endScale": 100,
                "duration": "{{duration}}",
                "easing": "easeOutBack",
            },
        },
    ],
    default_params={"font_size": 130},
)

TEXT_ROTATE_IN = CreativePattern(
    name="text_rotate_in",
    description="文字旋转进入效果，360度旋转显现",
    keywords=["旋转", "翻转", "rotate", "spin"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.2, 0.8, 0.4], "radius": 20},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "rotate_in",
                "rotationAngle": "{{rotation_angle}}",
                "duration": "{{duration}}",
                "easing": "easeOut",
            },
        },
    ],
    default_params={"font_size": 110, "rotation_angle": 360},
)

TEXT_SLIDE_IN = CreativePattern(
    name="text_slide_in",
    description="文字从侧边滑入效果",
    keywords=["滑动", "滑入", "slide", "swipe"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.3, 0.6, 1], "radius": 18},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "slide_in",
                "direction": "{{direction}}",
                "distance": "{{distance}}",
                "duration": "{{duration}}",
                "easing": "easeOutQuad",
            },
        },
    ],
    default_params={"font_size": 100, "direction": "left", "distance": 300},
)

TEXT_PER_CHAR = CreativePattern(
    name="text_per_char",
    description="文字逐字符动画效果，每个字符独立运动",
    keywords=["逐字", "逐个", "per_char", "letter_by_letter"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [1, 0.4, 0.6], "radius": 22},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "per_char",
                "charDelay": "{{char_delay}}",
                "charAnimation": "{{char_animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 90, "char_delay": 0.1, "char_animation": "scale_in"},
)

TEXT_FADE_IN_OUT = CreativePattern(
    name="text_fade_in_out",
    description="文字淡入淡出效果，优雅的显现和消失",
    keywords=["淡入", "淡出", "fade", "appear", "disappear"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.9, 0.9, 0.9], "radius": 15},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "fade_in_out",
                "fadeInDuration": "{{fade_in_duration}}",
                "holdDuration": "{{hold_duration}}",
                "fadeOutDuration": "{{fade_out_duration}}",
            },
        },
    ],
    default_params={"font_size": 100, "fade_in_duration": 1, "hold_duration": 2, "fade_out_duration": 1},
)

TEXT_SHOCK = CreativePattern(
    name="text_shock",
    description="文字震动效果，强烈的视觉冲击",
    keywords=["震动", "冲击", "shock", "shake"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [1, 0, 0], "radius": 30},
            },
        },
        {
            "script": "applyExpression",
            "params": {
                "expressionType": "wiggle",
                "expressionParams": {"frequency": 20, "amount": 15},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "glitchEffect"},
        },
    ],
    default_params={"font_size": 140},
)

TEXT_SPIRAL = CreativePattern(
    name="text_spiral",
    description="文字螺旋上升效果，3D旋转进入",
    keywords=["螺旋", "盘旋", "spiral", "twist"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "glow": {"enabled": True, "color": [0.6, 0.2, 0.8], "radius": 28},
            },
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "spiral",
                "rotationCount": "{{rotation_count}}",
                "startHeight": "{{start_height}}",
                "duration": "{{duration}}",
                "easing": "easeInOut",
            },
        },
    ],
    default_params={"font_size": 120, "rotation_count": 2, "start_height": 200},
)

# ============================================================
# 风格模板模式
# ============================================================

STYLE_CYBERPUNK = CreativePattern(
    name="style_cyberpunk",
    description="赛博朋克风格，霓虹发光 + 网格背景",
    keywords=["赛博朋克", "cyberpunk", "霓虹", "neon"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "fillColor": [0, 1, 0.8],
                "glow": {"enabled": True, "color": [0, 1, 0.8], "radius": 30, "intensity": 2.5},
                "stroke": {"enabled": True, "color": [0, 0.5, 0.8], "width": 3},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "cyberGlow", "addGrid": True, "addBackground": True},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 130, "animation": "scale_in"},
)

STYLE_HOLOGRAM = CreativePattern(
    name="style_hologram",
    description="全息投影风格，青色发光 + 扫描线",
    keywords=["全息", "hologram", "科幻", "scifi"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "fillColor": [0.3, 0.8, 1],
                "glow": {"enabled": True, "color": [0.3, 0.8, 1], "radius": 20, "intensity": 1.5},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "hologramEffect", "addScanlines": True},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 110, "animation": "per_char"},
)

STYLE_INK = CreativePattern(
    name="style_ink",
    description="水墨风格，粗糙边缘 + 模糊效果",
    keywords=["水墨", "ink", "书法", "calligraphy"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "fontFamily": "KaiTi",
                "fillColor": [0.15, 0.12, 0.1],
                "transform": {"bend": 10},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "colorGrade"},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 140, "animation": "typewriter"},
)

STYLE_FIRE_ICE = CreativePattern(
    name="style_fire_ice",
    description="冰火对比风格，暖色与冷色碰撞",
    keywords=["冰火", "fire", "ice", "对比", "contrast"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "fireIceEffect"},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 130, "animation": "bounce_in"},
)

STYLE_NEON = CreativePattern(
    name="style_neon",
    description="霓虹灯光风格，强发光 + 镜头光晕",
    keywords=["霓虹", "neon", "灯光", "lens flare"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
                "fillColor": [1, 0.2, 0.8],
                "glow": {"enabled": True, "color": [1, 0.2, 0.8], "radius": 35, "intensity": 3.0},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "neonEffect"},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
            },
        },
    ],
    default_params={"font_size": 120, "animation": "scale_in"},
)

# ============================================================
# 视频类型模式
# ============================================================

VIDEO_OPENING = CreativePattern(
    name="video_opening",
    description="视频片头，品牌展示",
    keywords=["片头", "opening", "intro", "title"],
    script_sequence=[
        {
            "script": "createSubtitleTemplate",
            "params": {
                "templateType": "{{style}}",
                "subtitleText": "{{text}}",
                "animation": "{{animation}}",
                "background": {"enabled": True, "color": [0, 0, 0], "opacity": 0.8},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "{{combo}}"},
        },
    ],
    default_params={"style": "cinematic", "animation": "fade", "combo": "colorGrade"},
)

VIDEO_ENDING = CreativePattern(
    name="video_ending",
    description="视频片尾，关注引导",
    keywords=["片尾", "ending", "outro", "关注"],
    script_sequence=[
        {
            "script": "addTextLayerAdvanced",
            "params": {
                "text": "{{text}}",
                "fontSize": "{{font_size}}",
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "colorGrade"},
        },
        {
            "script": "applyTextAnimation",
            "params": {
                "animationType": "{{animation}}",
                "duration": "{{duration}}",
                "reverse": True,
            },
        },
    ],
    default_params={"font_size": 90, "animation": "fade"},
)

VIDEO_MUSIC_VISUALIZATION = CreativePattern(
    name="video_music_visualization",
    description="音乐可视化，音频响应效果",
    keywords=["音乐", "audio", "visualization", "波形"],
    script_sequence=[
        {
            "script": "applyExpression",
            "params": {
                "expressionType": "audio_react",
                "expressionParams": {"audioLayerIndex": 1, "property": "both", "sensitivity": 100},
            },
        },
        {
            "script": "applyEffectCombo",
            "params": {"comboType": "{{combo}}"},
        },
    ],
    default_params={"combo": "cyberGlow"},
)

# ============================================================
# 创意模式注册表
# ============================================================

CREATIVE_PATTERNS = [
    # 文字动画
    TEXT_REVEAL,
    TEXT_TYPEWRITER,
    TEXT_EXPLODE,
    TEXT_WAVE,
    TEXT_BOUNCE_IN,
    TEXT_SCALE_IN,
    TEXT_ROTATE_IN,
    TEXT_SLIDE_IN,
    TEXT_PER_CHAR,
    TEXT_FADE_IN_OUT,
    TEXT_SHOCK,
    TEXT_SPIRAL,
    # 风格模板
    STYLE_CYBERPUNK,
    STYLE_HOLOGRAM,
    STYLE_INK,
    STYLE_FIRE_ICE,
    STYLE_NEON,
    # 视频类型
    VIDEO_OPENING,
    VIDEO_ENDING,
    VIDEO_MUSIC_VISUALIZATION,
]


def find_patterns_by_keyword(keyword: str) -> list[CreativePattern]:
    """根据关键词查找匹配的创意模式"""
    keyword_lower = keyword.lower()
    matches = []
    for pattern in CREATIVE_PATTERNS:
        for kw in pattern.keywords:
            if keyword_lower in kw.lower():
                matches.append(pattern)
                break
    return matches


def get_pattern_by_name(name: str) -> CreativePattern:
    """根据名称查找创意模式"""
    for pattern in CREATIVE_PATTERNS:
        if pattern.name == name:
            return pattern
    return None


def interpolate_params(
    pattern: CreativePattern, user_params: dict[str, Any]
) -> list[dict[str, Any]]:
    """将用户参数插入到脚本序列中"""
    merged_params = {**pattern.default_params, **user_params}
    interpolated_sequence = []

    for step in pattern.script_sequence:
        interpolated_step = {}
        for key, value in step.items():
            if isinstance(value, str):
                for param_name, param_value in merged_params.items():
                    placeholder = f"{{{{{param_name}}}}}"
                    value = value.replace(placeholder, str(param_value))
                interpolated_step[key] = value
            elif isinstance(value, dict):
                interpolated_step[key] = interpolate_dict_params(value, merged_params)
            else:
                interpolated_step[key] = value
        interpolated_sequence.append(interpolated_step)

    return interpolated_sequence


def interpolate_dict_params(d: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    """递归处理字典中的参数占位符"""
    result = {}
    for key, value in d.items():
        if isinstance(value, str):
            for param_name, param_value in params.items():
                placeholder = f"{{{{{param_name}}}}}"
                value = value.replace(placeholder, str(param_value))
            result[key] = value
        elif isinstance(value, dict):
            result[key] = interpolate_dict_params(value, params)
        elif isinstance(value, list):
            result[key] = [
                interpolate_dict_params(item, params) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def generate_task_graph(
    pattern_name: str, user_params: dict[str, Any]
) -> dict[str, Any]:
    """生成完整的任务图"""
    pattern = get_pattern_by_name(pattern_name)
    if not pattern:
        raise ValueError(f"未知的创意模式: {pattern_name}")

    script_sequence = interpolate_params(pattern, user_params)

    return {
        "version": "1.0",
        "project": user_params.get("project", "CreativeProject"),
        "duration": user_params.get("duration", 5),
        "pattern": pattern_name,
        "description": pattern.description,
        "params": user_params,
        "tasks": [
            {
                "id": f"task_{i + 1}",
                "name": step.get("script", "unknown"),
                "type": "ae_script",
                "script": step.get("script"),
                "params": step.get("params", {}),
                "dependencies": [],
                "timeout": 30,
            }
            for i, step in enumerate(script_sequence)
        ],
    }
