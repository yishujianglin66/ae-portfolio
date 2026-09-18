"""
Text Animation Engine — 文字动画引擎
====================================
基于 ASS 字幕格式的文字动画系统。

核心能力:
- 18 种动画预设（scale_bounce, slide_left, shockwave, neon_stroke 等）
- 3 层结构（光晕层 + 主体层 + 高光层）
- 6 种位置策略
- 5 种字体映射
- 7 种情绪配色

依赖:
    无外部依赖（纯 Python 生成 ASS 文件）

用法:
    engine = TextAnimationEngine()
    ass_content = engine.generate_ass("歌词文本", "climax", 0.8)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  常量定义
# ================================================================

# 动画预设
class AnimationPreset(str, Enum):
    """动画预设"""
    SCALE_BOUNCE = "scale_bounce"       # 缩放弹跳
    SLIDE_LEFT = "slide_left"           # 从左滑入
    SLIDE_RIGHT = "slide_right"         # 从右滑入
    SLIDE_UP = "slide_up"               # 从下滑入
    SLIDE_DOWN = "slide_down"           # 从上滑入
    FADE_IN = "fade_in"                 # 淡入
    FADE_OUT = "fade_out"               # 淡出
    SHOCKWAVE = "shockwave"             # 冲击波
    NEON_STROKE = "neon_stroke"         # 霓虹描边
    GLITCH_SHAKE = "glitch_shake"       # 故障抖动
    TYPEWRITER = "typewriter"           # 打字机效果
    WAVE = "wave"                       # 波浪效果
    PULSE = "pulse"                     # 脉冲效果
    ROTATE_IN = "rotate_in"             # 旋转进入
    ZOOM_BLUR = "zoom_blur"             # 缩放模糊
    BOUNCE_IN = "bounce_in"             # 弹跳进入
    FLIP_IN = "flip_in"                 # 翻转进入
    GLOW_PULSE = "glow_pulse"           # 光晕脉冲


# 位置策略
class PositionStrategy(str, Enum):
    """位置策略"""
    CENTER = "center"                   # 中心
    UPPER_CENTER = "upper_center"       # 上中
    LOWER_CENTER = "lower_center"       # 下中
    LEFT_THIRD = "left_third"           # 左三分之一
    RIGHT_THIRD = "right_third"         # 右三分之一
    BOTTOM_THIRD = "bottom_third"       # 下三分之一


# 字体映射
FONT_MAP = {
    "title_bold": "Source Han Sans CN Bold",
    "body_regular": "Source Han Sans CN Regular",
    "handwriting": "ZCOOL KuaiLe",
    "mono_tech": "JetBrains Mono",
    "subtitle_light": "Source Han Sans CN Light",
}

# 情绪配色
MOOD_COLORS = {
    "intro": {"main": "#FFD700", "glow": "#FFA500", "accent": "#FFFFFF"},      # 金色
    "build": {"main": "#00BFFF", "glow": "#1E90FF", "accent": "#E0FFFF"},      # 青色
    "drop": {"main": "#FF4500", "glow": "#FF0000", "accent": "#FFD700"},       # 橙红
    "climax": {"main": "#FF0000", "glow": "#8B0000", "accent": "#FFD700"},     # 红色
    "break": {"main": "#9370DB", "glow": "#8A2BE2", "accent": "#E6E6FA"},     # 紫色
    "outro": {"main": "#FFD700", "glow": "#DAA520", "accent": "#FFFFFF"},      # 金色
    "flash": {"main": "#FFFFFF", "glow": "#FF0000", "accent": "#FFD700"},      # 白色闪白
}

# 位置坐标（基于 1920x1080）
POSITION_MAP = {
    "center": (960, 540),
    "upper_center": (960, 270),
    "lower_center": (960, 810),
    "left_third": (320, 540),
    "right_third": (1600, 540),
    "bottom_third": (960, 900),
}


# ================================================================
#  数据结构
# ================================================================

@dataclass
class TextStyle:
    """文字样式"""
    font_name: str = "Source Han Sans CN Bold"
    font_size: int = 72
    bold: bool = True
    italic: bool = False
    color_main: str = "#FFFFFF"
    color_glow: str = "#FFD700"
    color_accent: str = "#FFFFFF"
    outline_width: int = 3
    shadow_distance: int = 2
    shadow_angle: int = 45
    mood: str = "climax"  # 情绪标签（决定样式表中的配色行；2026-08-15 修复 Style_{hex} 引用 bug）


@dataclass
class AnimationConfig:
    """动画配置"""
    preset: str = AnimationPreset.SCALE_BOUNCE.value
    duration_ms: int = 500              # 动画时长（毫秒）
    delay_ms: int = 0                   # 延迟
    easing: str = "ease_out"            # 缓动函数


@dataclass
class TextAnimation:
    """文字动画实例"""
    text: str
    start_time: float                   # 开始时间（秒）
    end_time: float                     # 结束时间（秒）
    style: TextStyle
    animation: AnimationConfig
    position: tuple[int, int]           # (x, y)
    layer: int = 0                      # 图层


# ================================================================
#  文字动画引擎
# ================================================================

class TextAnimationEngine:
    """文字动画引擎"""

    def __init__(
        self,
        video_width: int = 1920,
        video_height: int = 1080,
        fps: int = 24,
    ):
        self.width = video_width
        self.height = video_height
        self.fps = fps

    def generate_ass(
        self,
        animations: list[TextAnimation],
        output_path: str | None = None,
    ) -> str:
        """
        生成 ASS 字幕文件。

        Args:
            animations: 文字动画列表
            output_path: 可选输出路径

        Returns:
            ASS 文件内容
        """
        lines = []

        # ASS 头部
        lines.append("[Script Info]")
        lines.append("Title: Levi MAD Lyrics")
        lines.append("ScriptType: v4.00+")
        lines.append(f"PlayResX: {self.width}")
        lines.append(f"PlayResY: {self.height}")
        lines.append("Timer: 100.0000")
        lines.append("")

        # 样式定义
        lines.append("[V4+ Styles]")
        lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
        
        # 为实际用到的 (mood, font_size) 组合创建样式（修复：原实现按全部 mood 生成 72 号样式，
        # 而 Dialogue 行引用 Style_{hex} 完全错配；font_size 参数从不生效）
        used_styles = {}
        for anim in animations:
            key = (anim.style.mood, anim.style.font_size)
            if key not in used_styles:
                used_styles[key] = anim.style
        for (mood, font_size), style in used_styles.items():
            style_name = f"Style_{mood}_{font_size}"
            primary = self._hex_to_ass_color(style.color_main)
            outline = self._hex_to_ass_color(style.color_glow)
            lines.append(
                f"Style: {style_name},{style.font_name},{font_size},{primary},&H00FFFFFF,{outline},&H00000000,"
                f"{-1 if style.bold else 0},{1 if style.italic else 0},0,0,100,100,0,0,1,"
                f"{style.outline_width},{style.shadow_distance},5,20,20,20,1"
            )
        
        lines.append("")

        # 事件
        lines.append("[Events]")
        lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

        for anim in animations:
            # 生成对话行
            start_time = self._format_time(anim.start_time)
            end_time = self._format_time(anim.end_time)
            
            # 位置
            x, y = anim.position
            
            # 动画效果
            effect = self._generate_effect(anim)
            
            # 文字内容
            text = anim.text
            if effect:
                text = f"{effect}{text}"
            
            # 图层：光晕层 + 主体层 + 高光层（样式名统一 mood_fontsize，修复 Style_{hex} 引用 bug）
            style_ref = f"Style_{anim.style.mood}_{anim.style.font_size}"
            # 光晕层
            lines.append(
                f"Dialogue: 0,{start_time},{end_time},{style_ref},,0,0,0,,{{\\pos({x},{y})\\an5\\blur20\\alpha&H80}}{anim.text}"
            )
            # 主体层
            lines.append(
                f"Dialogue: 1,{start_time},{end_time},{style_ref},,0,0,0,,{{\\pos({x},{y})\\an5\\bord3\\shad2}}{anim.text}"
            )
            # 高光层（可选）
            if anim.animation.preset in [AnimationPreset.NEON_STROKE.value, AnimationPreset.GLOW_PULSE.value]:
                lines.append(
                    f"Dialogue: 2,{start_time},{end_time},{style_ref},,0,0,0,,{{\\pos({x},{y})\\an5\\blur5\\alpha&H40}}{anim.text}"
                )

        lines.append("")

        content = "\n".join(lines)

        if output_path:
            Path(output_path).write_text(content, encoding="utf-8-sig")
            print(f"[OK] ASS 文件已生成: {output_path}")

        return content

    def _hex_to_ass_color(self, hex_color: str) -> str:
        """转换 HEX 颜色为 ASS 格式"""
        hex_color = hex_color.lstrip("#")
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        return f"&H00{b}{g}{r}&"

    def _format_time(self, seconds: float) -> str:
        """格式化时间为 ASS 时间格式 (H:MM:SS.CC)"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _generate_effect(self, anim: TextAnimation) -> str:
        """生成动画效果"""
        preset = anim.animation.preset
        duration = anim.animation.duration_ms
        
        if preset == AnimationPreset.SCALE_BOUNCE.value:
            # 缩放弹跳
            return f"{{\\fscx0\\fscy0\\t(0,{duration},\\fscx100\\fscy100)}}"
        
        elif preset == AnimationPreset.SLIDE_LEFT.value:
            # 从左滑入
            x, y = anim.position
            return f"{{\\pos({-200},{y})\\t(0,{duration},\\pos({x},{y}))}}"
        
        elif preset == AnimationPreset.SLIDE_RIGHT.value:
            # 从右滑入
            x, y = anim.position
            return f"{{\\pos({self.width + 200},{y})\\t(0,{duration},\\pos({x},{y}))}}"
        
        elif preset == AnimationPreset.SLIDE_UP.value:
            # 从下滑入
            x, y = anim.position
            return f"{{\\pos({x},{self.height + 100})\\t(0,{duration},\\pos({x},{y}))}}"
        
        elif preset == AnimationPreset.FADE_IN.value:
            # 淡入
            return f"{{\\alpha&HFF\\t(0,{duration},\\alpha&H00&)}}"
        
        elif preset == AnimationPreset.SHOCKWAVE.value:
            # 冲击波
            return f"{{\\fscx50\\fscy50\\t(0,{duration//2},\\fscx120\\fscy120)\\t({duration//2},{duration},\\fscx100\\fscy100)}}"
        
        elif preset == AnimationPreset.NEON_STROKE.value:
            # 霓虹描边
            return f"{{\\bord0\\t(0,{duration//2},\\bord6)\\t({duration//2},{duration},\\bord3)}}"
        
        elif preset == AnimationPreset.GLITCH_SHAKE.value:
            # 故障抖动（简化版）
            return "{\\fad(100,100)}"
        
        elif preset == AnimationPreset.PULSE.value:
            # 脉冲
            return f"{{\\fscx100\\fscy100\\t(0,{duration//2},\\fscx110\\fscy110)\\t({duration//2},{duration},\\fscx100\\fscy100)}}"
        
        elif preset == AnimationPreset.ROTATE_IN.value:
            # 旋转进入
            return f"{{\\frz-180\\t(0,{duration},\\frz0)}}"
        
        elif preset == AnimationPreset.BOUNCE_IN.value:
            # 弹跳进入
            return f"{{\\fscx0\\fscy0\\t(0,{duration//3},\\fscx120\\fscy120)\\t({duration//3},{duration},\\fscx100\\fscy100)}}"
        
        elif preset == AnimationPreset.GLOW_PULSE.value:
            # 光晕脉冲
            return f"{{\\blur5\\t(0,{duration//2},\\blur20)\\t({duration//2},{duration},\\blur5)}}"

        elif preset == AnimationPreset.SLIDE_DOWN.value:
            # 从上滑入
            x, y = anim.position
            return f"{{\\pos({x},{-100})\\t(0,{duration},\\pos({x},{y}))}}"

        elif preset == AnimationPreset.FADE_OUT.value:
            # 淡出
            return f"{{\\alpha&H00&\\t(0,{duration},\\alpha&HFF&)}}"

        elif preset == AnimationPreset.TYPEWRITER.value:
            # 打字机（ASS 单行限制，用快速淡入近似；完整逐字需逐字符 Dialogue 行）
            return f"{{\\fad(0,{min(duration, 150)})}}"

        elif preset == AnimationPreset.WAVE.value:
            # 波浪（Y 轴往复简化版）
            x, y = anim.position
            return (f"{{\\pos({x},{y})\\t(0,{duration//4},\\pos({x},{y - 15}))"
                    f"\\t({duration//4},{duration//2},\\pos({x},{y + 10}))"
                    f"\\t({duration//2},{duration * 3 // 4},\\pos({x},{y - 8}))"
                    f"\\t({duration * 3 // 4},{duration},\\pos({x},{y}))}}")

        elif preset == AnimationPreset.ZOOM_BLUR.value:
            # 缩放模糊（大模糊+缩小 → 清晰+原尺寸）
            return (f"{{\\blur30\\fscx50\\fscy50"
                    f"\\t(0,{duration},\\blur0\\fscx100\\fscy100)}}")

        elif preset == AnimationPreset.FLIP_IN.value:
            # 翻转进入（X 轴 3D 翻转）
            return f"{{\\frx-90\\t(0,{duration},\\frx0)}}"

        else:
            return ""

    def create_animation(
        self,
        text: str,
        start_time: float,
        end_time: float,
        mood: str = "climax",
        preset: str = AnimationPreset.SCALE_BOUNCE.value,
        position: str = PositionStrategy.CENTER.value,
        font_size: int = 72,
    ) -> TextAnimation:
        """
        创建文字动画实例。

        Args:
            text: 文字内容
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            mood: 情绪标签
            preset: 动画预设
            position: 位置策略
            font_size: 字体大小

        Returns:
            TextAnimation 实例
        """
        # 获取颜色
        colors = MOOD_COLORS.get(mood, MOOD_COLORS["climax"])
        
        # 创建样式
        style = TextStyle(
            font_name=FONT_MAP["title_bold"],
            font_size=font_size,
            bold=True,
            color_main=colors["main"],
            color_glow=colors["glow"],
            color_accent=colors["accent"],
            mood=mood,
        )
        
        # 创建动画配置
        animation = AnimationConfig(
            preset=preset,
            duration_ms=500,
        )
        
        # 获取位置
        pos = POSITION_MAP.get(position, POSITION_MAP["center"])
        
        return TextAnimation(
            text=text,
            start_time=start_time,
            end_time=end_time,
            style=style,
            animation=animation,
            position=pos,
        )


# ================================================================
#  便捷函数
# ================================================================

def generate_lyric_ass(
    lyrics: list[tuple[str, float, float, str, str]],
    output_path: str,
    video_width: int = 1920,
    video_height: int = 1080,
) -> str:
    """
    快速生成歌词 ASS 文件。

    Args:
        lyrics: [(text, start, end, mood, preset), ...]
        output_path: 输出路径
        video_width: 视频宽度
        video_height: 视频高度

    Returns:
        ASS 文件内容
    """
    engine = TextAnimationEngine(video_width, video_height)
    
    animations = []
    for text, start, end, mood, preset in lyrics:
        anim = engine.create_animation(text, start, end, mood, preset)
        animations.append(anim)
    
    return engine.generate_ass(animations, output_path)


__all__ = [
    "TextAnimationEngine",
    "TextAnimation",
    "TextStyle",
    "AnimationConfig",
    "AnimationPreset",
    "PositionStrategy",
    "MOOD_COLORS",
    "FONT_MAP",
    "POSITION_MAP",
    "generate_lyric_ass",
]


# ================================================================
#  自测入口
# ================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TextAnimationEngine 自测")
    print("=" * 60)

    # 测试歌词
    test_lyrics = [
        ("像是只鸟飞不停", 0.0, 1.5, "intro", AnimationPreset.FADE_IN.value),
        ("all eyes on me", 3.5, 5.0, "drop", AnimationPreset.SHOCKWAVE.value),
        ("我已经觉醒", 26.0, 28.0, "climax", AnimationPreset.BOUNCE_IN.value),
    ]

    engine = TextAnimationEngine()
    
    # 创建动画
    animations = []
    for text, start, end, mood, preset in test_lyrics:
        anim = engine.create_animation(text, start, end, mood, preset)
        animations.append(anim)
    
    # 生成 ASS
    output_dir = Path(r"D:\AE-Work\output\levi_mad_director_v1")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "test_lyrics.ass"
    
    content = engine.generate_ass(animations, str(output_path))
    
    print(f"\n生成的 ASS 文件: {output_path}")
    print(f"文件大小: {len(content)} 字节")
    print(f"动画数量: {len(animations)}")
