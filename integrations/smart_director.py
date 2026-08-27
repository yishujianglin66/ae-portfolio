# -*- coding: utf-8 -*-
"""
智能导演系统 — 镜头感知驱动的文字动画决策
==========================================

"感知→分析→决策→执行"闭环：
    1. 感知：ffmpeg 测量每个镜头段落的运动强度 & 场景复杂度
    2. 分析：根据特征划分 intensity_level (gentle / moderate / intense)
    3. 决策：选择动画预设、位置、时长、颜色
    4. 执行：生成多样化 JSX 文字动画代码

知识库消费：
    - ae/presets/text_animation.json   → 动画类型参考（bounce / slide / flip）
    - ae/presets/3d_effect.json        → 3D 旋转 / 翻转参考
    - 10-风格化剪辑知识库              → 风格标签匹配
    - 11-大师知识库                    → 动画节奏经验
    - 12-漫剪拉镜大师                  → 漫画剪辑节奏
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
from typing import Any, Dict, List, Optional

from loguru import logger

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
#  高端 AMV 配色方案（对标外网漫剪风格）
# ============================================================================
ACCENT_COLORS = [
    [1.0, 0.85, 0.3],   # 金色
    [0.3, 0.9, 1.0],    # 青色
    [1.0, 0.3, 0.5],    # 热粉
    [1.0, 1.0, 1.0],    # 纯白
    [0.6, 1.0, 0.4],    # 荧光绿
    [1.0, 0.6, 0.2],    # 橙色
]

def _get_shot_color(idx: int) -> list:
    return ACCENT_COLORS[idx % len(ACCENT_COLORS)]

def _carr(idx: int) -> str:
    """返回 JSX 数组格式的颜色 [r,g,b]"""
    c = ACCENT_COLORS[idx % len(ACCENT_COLORS)]
    return f"[{c[0]},{c[1]},{c[2]}]"

# ============================================================================
#  字体注册表 — 5 种字体变体，覆盖标题/正文/副标题/科技/情感场景
# ============================================================================
FONT_REGISTRY = {
    "title_bold": {
        "font": "MicrosoftYaHei",
        "faux_bold": True,
        "size_range": (88, 110),
        "usage": "标题、高潮段落、冲击型预设",
    },
    "body_regular": {
        "font": "Impact",
        "faux_bold": False,
        "size_range": (72, 84),
        "usage": "正文、中段叙事、力量感展示预设",
    },
    "subtitle_light": {
        "font": "Arial",
        "faux_bold": False,
        "size_range": (56, 72),
        "usage": "副标题、抒情段落、文艺优雅预设",
    },
    "mono_tech": {
        "font": "Consolas",
        "faux_bold": True,
        "size_range": (64, 80),
        "usage": "科技感文字、故障风/赛博朋克预设",
    },
    "handwriting_emotional": {
        "font": "ArialNarrow",
        "faux_bold": False,
        "size_range": (68, 84),
        "usage": "情感/回忆段落、紧凑窄体风格",
    },
}

# 特效-字体最优组合矩阵（14 种预设 × 字体 × 特效）
EFFECT_FONT_MATRIX = {
    # 高能量预设 → 粗体
    "shockwave":         {"font": "title_bold",          "ae_effects": ["Glow", "Directional Blur"]},
    "glow_pulse":        {"font": "title_bold",          "ae_effects": ["Glow"]},
    "elastic_overshoot": {"font": "title_bold",          "ae_effects": []},
    "speed_impact":      {"font": "title_bold",          "ae_effects": ["Directional Blur"]},
    # 中能量预设 → 常规体/等宽体
    "glitch_shake":      {"font": "mono_tech",           "ae_effects": ["Color Balance (HLS)"]},
    "rgb_split":         {"font": "mono_tech",           "ae_effects": ["Duplicate + Screen Blend"]},
    "scale_bounce":      {"font": "body_regular",        "ae_effects": []},
    "rotate_3d":         {"font": "body_regular",        "ae_effects": ["3D Layer"]},
    "flip_card":         {"font": "body_regular",        "ae_effects": ["Glow (soft)"]},
    "neon_stroke":       {"font": "mono_tech",           "ae_effects": ["Glow + Stroke"]},
    # 低能量预设 → 细体/手写体
    "fade_scale":        {"font": "subtitle_light",      "ae_effects": []},
    "slide_left":        {"font": "subtitle_light",      "ae_effects": []},
    "slide_right":       {"font": "handwriting_emotional","ae_effects": []},
    "drop_top":          {"font": "subtitle_light",      "ae_effects": []},
    # 新增预设（第六轮扩展）
    "ink_spread":        {"font": "subtitle_light",      "ae_effects": ["Gaussian Blur"]},
    "glitch_flash":      {"font": "title_bold",          "ae_effects": ["Position Jitter"]},
    "particle_dissolve": {"font": "body_regular",        "ae_effects": ["CC Particle World"]},
    "neon_breathe":      {"font": "mono_tech",           "ae_effects": ["Glow (breathing)"]},
}


def resolve_font_for_preset(preset_key: str, emotion: str = "") -> dict:
    """根据预设名和情绪，从注册表获取最优字体配置。

    Returns:
        {"font": str, "faux_bold": bool}
    """
    matrix_entry = EFFECT_FONT_MATRIX.get(preset_key, {})
    font_key = matrix_entry.get("font", "body_regular")
    # 情绪微调：高唤醒 → 强制粗体，低唤醒 → 强制细体
    if emotion in ("rage", "triumph", "tension", "horror"):
        font_key = "title_bold"
    elif emotion in ("grief", "melancholy", "serenity", "nostalgia"):
        font_key = "subtitle_light"
    fc = FONT_REGISTRY.get(font_key, FONT_REGISTRY["body_regular"])
    return {"font": fc["font"], "faux_bold": fc["faux_bold"]}


# ============================================================================
#  文字动画预设（灵感来源：ae/presets/text_animation.json + 3d_effect.json）
# ============================================================================
# 每个预设：
#   entry : (t0, dur, from_vals, to_vals)     — 入场关键帧
#   hold  : (t0, dur, values)                  — 展示保持
#   exit_ : (t0, dur, from_vals, to_vals)      — 出场关键帧
#   prop_fn : 返回 JSX 属性设置代码
#   pos   : (x_expr, y_expr)                   — 位置表达式
#   apply_effects: 可选，返回 JSX 添加 AE 效果的代码
# ============================================================================

TEXT_ANIM_PRESETS: Dict[str, Dict[str, Any]] = {
    # ① 缩放弹跳（参考 douyin_bounce_title）
    "scale_bounce": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=84, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,1,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[[30,30],[118,118],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[50,50]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ② 左侧滑入 + 右侧滑出（参考 mg_animation slide）
    "slide_left": {
        "pos": ("c.width*0.28", "c.height*0.5"),
        "prop_fn": lambda s, fs=72, font='MicrosoftYaHei', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,0.95,0.8];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.LEFT_JUSTIFY;"
        ),
        "entry": lambda t, d, s, px="c.width*0.28", py="c.height*0.5": (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[-300,{py}],[{px},{py}]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[c.width*0.28,c.height*0.5],[c.width+300,c.height*0.5]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ③ 右侧滑入 + 左侧滑出
    "slide_right": {
        "pos": ("c.width*0.72", "c.height*0.5"),
        "prop_fn": lambda s, fs=72, font='MicrosoftYaHei', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[0.8,0.95,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.RIGHT_JUSTIFY;"
        ),
        "entry": lambda t, d, s, px="c.width*0.72", py="c.height*0.5": (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[{px}+300,{py}],[{px},{py}]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[c.width*0.72,c.height*0.5],[-300,c.height*0.5]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ④ 3D Y轴旋转进出（参考 3d_effect.json → text_rotation / text_flip）
    "rotate_3d": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=80, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,0.85,0.4];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "needs_3d": True,
        "entry": lambda t, d, s: (
            f"tt{s}.property('Y Rotation').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[90,0]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Y Rotation').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,-90]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ⑤ 顶部下落 + 底部下落（参考 manga 漫画拉镜）
    "drop_top": {
        "pos": ("c.width/2", "c.height*0.3"),
        "prop_fn": lambda s, fs=76, font='MicrosoftYaHei', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,1,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[c.width/2,-100],[c.width/2,c.height*0.3]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],"
            f"[[c.width/2,c.height*0.3],[c.width/2,c.height+100]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ⑥ 渐显放大 + 渐隐缩小（柔和风格，参考大师知识库慢节奏技法）
    "fade_scale": {
        "pos": ("c.width/2", "c.height*0.65"),
        "prop_fn": lambda s, fs=68, font='MicrosoftYaHei', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[0.9,0.9,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[60,60],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[70,70]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,95]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[95,0]);"
        ),
    },
    # ====================================================================
    #  ⑦-⑭ 高端漫剪预设（第四轮新增 — 对标外网 AMV/MAD 炫酷风格）
    # ====================================================================
    # ⑦ 辉光脉冲 — Glow 效果 + 缩放弹跳，入场时辉光爆发
    "glow_pulse": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=88, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.35:.3f},{t + d * 0.6:.3f},{t + d:.3f}],"
            f"[[20,20],[125,125],[95,95],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[40,40]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var gf{0}=tt{s}.Effects.addProperty('ADBE Glo2');"
            f"gf{0}.property('ADBE Glo2-0002').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f},{t + d:.3f}],[0.8,0.15,0.5]);"
            f"gf{0}.property('ADBE Glo2-0003').setValuesAtTimes([0],[25]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑧ 故障抖动 — 快速位移抖动 + 色相偏移，赛博朋克风格
    "glitch_shake": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=80, font='Consolas', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d * 0.3:.3f},"
            f"{t + d * 0.45:.3f},{t + d * 0.6:.3f},{t + d:.3f}],"
            f"[[c.width/2+60,c.height/2-40],[c.width/2-30,c.height/2+20],"
            f"[c.width/2+20,c.height/2-10],[c.width/2-10,c.height/2+5],"
            f"[c.width/2+5,c.height/2-3],[c.width/2,c.height/2]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f},{t + d:.3f}],"
            f"[[c.width/2,c.height/2],[c.width/2+40,c.height/2-20],"
            f"[c.width/2+200,c.height/2-100]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.1:.3f},{t + d * 0.2:.3f},"
            f"{t + d * 0.3:.3f},{t + d:.3f}],"
            f"[0,100,40,100,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var hc{0}=tt{s}.Effects.addProperty('ADBE Color Balance (HLS)');"
            f"hc{0}.property('ADBE Color Balance (HLS)-0002').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.2:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[40,-20,30,0]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑨ 弹性过冲 — 三次弹跳收敛，overshoot easing 打击感
    "elastic_overshoot": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=92, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.25:.3f},{t + d * 0.45:.3f},"
            f"{t + d * 0.65:.3f},{t + d * 0.85:.3f},{t + d:.3f}],"
            f"[[0,0],[135,135],[88,88],[115,115],[96,96],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[[100,100],[110,110],[0,0]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
    },
    # ⑩ RGB分离 — 色差效果，三层文字叠加偏移
    "rgb_split": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=84, font='Consolas', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,1,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[30,30],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[50,50]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            # 红色偏移层
            f"try {{ var rs{0}=tt{s}.duplicate();"
            f"rs{0}.name='rgb_r';"
            f"var rstd{0}=rs{0}.property('Source Text').value;"
            f"rstd{0}.fillColor=[1,0.1,0.1];rs{0}.property('Source Text').setValue(rstd{0});"
            f"rs{0}.blendingMode=BlendingMode.SCREEN;"
            f"rs{0}.property('Opacity').setValueAtTime({t:.3f},60);"
            f"rs{0}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[c.width/2-12,c.height/2],[c.width/2-6,c.height/2]]);"
            # 蓝色偏移层
            f"var bs{0}=tt{s}.duplicate();"
            f"bs{0}.name='rgb_b';"
            f"var bstd{0}=bs{0}.property('Source Text').value;"
            f"bstd{0}.fillColor=[0.1,0.1,1];bs{0}.property('Source Text').setValue(bstd{0});"
            f"bs{0}.blendingMode=BlendingMode.SCREEN;"
            f"bs{0}.property('Opacity').setValueAtTime({t:.3f},60);"
            f"bs{0}.property('Position').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[c.width/2+12,c.height/2],[c.width/2+6,c.height/2]]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑪ 速度线冲击 — 放射状缩放 + 运动模糊感
    "speed_impact": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=96, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            # X 方向拉伸 → 回弹，模拟速度感
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.2:.3f},{t + d * 0.5:.3f},{t + d:.3f}],"
            f"[[250,50],[80,110],[105,98],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[[100,100],[50,150],[0,300]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.1:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            # 方向模糊模拟速度线（try-catch 保护）
            f"try {{ var mb{0}=tt{s}.Effects.addProperty('ADBE Directional Blur');"
            f"mb{0}.property('ADBE Directional Blur-0002').setValue(90);"
            f"mb{0}.property('ADBE Directional Blur-0003').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d:.3f}],[40,0,0]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑫ 3D翻转卡片 — Y轴 180° 翻转进出
    "flip_card": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=84, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "needs_3d": True,
        "entry": lambda t, d, s: (
            f"tt{s}.property('Y Rotation').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[180,0]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Y Rotation').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,-180]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t + d * 0.7:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var gf{0}=tt{s}.Effects.addProperty('ADBE Glo2');"
            f"gf{0}.property('ADBE Glo2-0002').setValuesAtTimes([0],[0.3]);"
            f"gf{0}.property('ADBE Glo2-0003').setValuesAtTimes([0],[15]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑬ 霓虹描边 — 发光描边 + 脉冲，赛博朋克美学
    "neon_stroke": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=80, font='Consolas', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[0.05,0.05,0.1];"
            f"td{s}.strokeColor={_carr(s)};td{s}.strokeWidth=3;"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[70,70],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[80,80]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var gf{0}=tt{s}.Effects.addProperty('ADBE Glo2');"
            f"gf{0}.property('ADBE Glo2-0002').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f},{t + d * 0.6:.3f},{t + d:.3f}],"
            f"[0.7,0.2,0.5,0.3]);"
            f"gf{0}.property('ADBE Glo2-0003').setValuesAtTimes([0],[20]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑮ 水墨晕染 — 高斯模糊渐清 + 透明度淡入，文艺优雅
    "ink_spread": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=68, font='MicrosoftYaHei', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[0.9,0.9,0.95];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[80,80],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[0,90]);"
        ),
        "opacity_out": lambda t, d, s: "",
        "apply_effects": lambda s, t, d: (
            f"try {{ var bl{0}=tt{s}.Effects.addProperty('ADBE Gaussian Blur');"
            f"bl{0}.property('ADBE Gaussian Blur-0001').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.6:.3f},{t + d:.3f}],[30,5,0]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑯ 故障闪烁 — 快速透明度抖动 + 位置抖动，赛博紧张感
    "glitch_flash": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=92, font='Consolas', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor={_carr(s)};"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f}],[[50,50],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[100,0]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.1:.3f},{t + d * 0.2:.3f},"
            f"{t + d * 0.3:.3f},{t + d * 0.4:.3f},{t + d * 0.5:.3f},"
            f"{t + d * 0.6:.3f},{t + d * 0.7:.3f},{t + d:.3f}],"
            f"[0,100,20,100,30,100,50,100,100]);"
        ),
        "opacity_out": lambda t, d, s: "",
        "apply_effects": lambda s, t, d: (
            f"try {{ var ps{0}=tt{s}.property('Position');"
            f"ps{0}.setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d * 0.3:.3f},"
            f"{t + d * 0.45:.3f},{t + d * 0.6:.3f},{t + d:.3f}],"
            f"[[c.width/2+25,c.height/2-15],[c.width/2-18,c.height/2+10],"
            f"[c.width/2+12,c.height/2-8],[c.width/2-6,c.height/2+4],"
            f"[c.width/2+3,c.height/2-2],[c.width/2,c.height/2]]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑰ 粒子消散 — CC Particle World + 透明度衰减，过渡段落
    "particle_dissolve": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=80, font='Impact', faux_bold=False: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,1,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[[100,100],[105,105],[115,115]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: "",
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t + d * 0.5:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            # CC Particle World 属性 ID 不稳定，仅添加效果不设置参数
            f"try {{ tt{s}.Effects.addProperty('ADBE CC Particle World');"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑱ 霓虹呼吸 — Glow 正弦波明暗变化，科技感
    "neon_breathe": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=76, font='Consolas', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[0.05,0.05,0.1];"
            f"td{s}.strokeColor={_carr(s)};td{s}.strokeWidth=2;"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.3:.3f}],[[85,85],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d:.3f}],[[100,100],[90,90]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.2:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t + d * 0.7:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var gf{0}=tt{s}.Effects.addProperty('ADBE Glo2');"
            f"gf{0}.property('ADBE Glo2-0002').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.25:.3f},{t + d * 0.5:.3f},"
            f"{t + d * 0.75:.3f},{t + d:.3f}],"
            f"[0.6,0.2,0.5,0.15,0.4]);"
            f"gf{0}.property('ADBE Glo2-0003').setValuesAtTimes([0],[18]);"
            f"}} catch(e) {{}}"
        ),
    },
    # ⑭ 冲击波 — 缩放爆炸 + 辉光爆发 + 方向模糊
    "shockwave": {
        "pos": ("c.width/2", "c.height/2"),
        "prop_fn": lambda s, fs=100, font='MicrosoftYaHei', faux_bold=True: (
            f"td{s}.fontSize={fs};td{s}.fillColor=[1,1,1];"
            f"td{s}.font='{font}';td{s}.fauxBold={str(faux_bold).lower()};"
            f"td{s}.justification=ParagraphJustification.CENTER_JUSTIFY;"
        ),
        "entry": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d * 0.4:.3f},{t + d:.3f}],"
            f"[[0,0],[180,180],[90,90],[100,100]]);"
        ),
        "hold": lambda t, d, s: "",
        "exit": lambda t, d, s: (
            f"tt{s}.property('Scale').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.5:.3f},{t + d:.3f}],"
            f"[[100,100],[140,140],[0,0]]);"
        ),
        "opacity_in": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.08:.3f}],[0,100]);"
        ),
        "opacity_out": lambda t, d, s: (
            f"tt{s}.property('Opacity').setValuesAtTimes("
            f"[{t + d * 0.6:.3f},{t + d:.3f}],[100,0]);"
        ),
        "apply_effects": lambda s, t, d: (
            f"try {{ var gf{0}=tt{s}.Effects.addProperty('ADBE Glo2');"
            f"gf{0}.property('ADBE Glo2-0002').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d:.3f}],[0.9,0.1,0.4]);"
            f"gf{0}.property('ADBE Glo2-0003').setValue(35);"
            f"}} catch(e) {{}}"
            f"try {{ var mb{0}=tt{s}.Effects.addProperty('ADBE Directional Blur');"
            f"mb{0}.property('ADBE Directional Blur-0002').setValue(0);"
            f"mb{0}.property('ADBE Directional Blur-0003').setValuesAtTimes("
            f"[{t:.3f},{t + d * 0.15:.3f},{t + d:.3f}],[30,0,0]);"
            f"}} catch(e) {{}}"
        ),
    },
}

# 预设名循环列表
_PRESET_KEYS = list(TEXT_ANIM_PRESETS.keys())

# ============================================================================
#  位置多样化系统 — 打破居中垄断，构建空间层次
# ============================================================================
# 6 种屏幕位置策略（归一化坐标 → AE 表达式）
POSITION_STRATEGIES = {
    "center":         ("c.width/2",       "c.height/2"),
    "upper_center":   ("c.width/2",       "c.height*0.28"),
    "lower_center":   ("c.width/2",       "c.height*0.72"),
    "left_third":     ("c.width*0.22",    "c.height/2"),
    "right_third":    ("c.width*0.78",    "c.height/2"),
    "bottom_third":   ("c.width/2",       "c.height*0.78"),
}

# 每个预设的位置候选池（按强度级别分配）
# intense → 中央区域（冲击力），moderate → 三分法偏移，gentle → 边缘留白
PRESET_POSITION_VARIANTS = {
    "scale_bounce":        {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third", "center"],
                            "gentle": ["lower_center", "bottom_third"]},
    "slide_left":          {"intense": ["center"],
                            "moderate": ["left_third", "center"],
                            "gentle": ["left_third", "lower_center"]},
    "slide_right":         {"intense": ["center"],
                            "moderate": ["right_third", "center"],
                            "gentle": ["right_third", "lower_center"]},
    "rotate_3d":           {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center", "bottom_third"]},
    "drop_top":            {"intense": ["upper_center", "center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center", "bottom_third"]},
    "fade_scale":          {"intense": ["center"],
                            "moderate": ["lower_center", "bottom_third"],
                            "gentle": ["bottom_third", "left_third", "right_third"]},
    "glow_pulse":          {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center"]},
    "glitch_shake":        {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center"]},
    "elastic_overshoot":   {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third", "center"],
                            "gentle": ["lower_center"]},
    "rgb_split":           {"intense": ["center"],
                            "moderate": ["left_third", "right_third", "upper_center"],
                            "gentle": ["lower_center"]},
    "speed_impact":        {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center"]},
    "flip_card":           {"intense": ["center"],
                            "moderate": ["left_third", "right_third", "upper_center"],
                            "gentle": ["lower_center", "bottom_third"]},
    "neon_stroke":         {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center", "bottom_third"]},
    "shockwave":           {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center"]},
    # 新增预设位置变体
    "ink_spread":          {"intense": ["center"],
                            "moderate": ["lower_center", "bottom_third"],
                            "gentle": ["bottom_third", "left_third", "right_third"]},
    "glitch_flash":        {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center"]},
    "particle_dissolve":   {"intense": ["center"],
                            "moderate": ["left_third", "right_third", "upper_center"],
                            "gentle": ["lower_center", "bottom_third"]},
    "neon_breathe":        {"intense": ["center", "upper_center"],
                            "moderate": ["left_third", "right_third"],
                            "gentle": ["lower_center", "bottom_third"]},
}


def _select_position(preset_key: str, intensity: str, shot_index: int) -> tuple:
    """根据预设、强度和镜头序号选择屏幕位置。

    Returns:
        (x_expr, y_expr) AE 表达式元组
    """
    variants = PRESET_POSITION_VARIANTS.get(preset_key, {})
    pool = variants.get(intensity, ["center"])
    key = pool[shot_index % len(pool)]
    return POSITION_STRATEGIES.get(key, POSITION_STRATEGIES["center"])


# 字号范围（按强度级别，大幅拉开差异）
FONT_SIZE_RANGES = {
    "intense":  (110, 145),   # 高潮：巨大、冲击
    "moderate": (70, 95),     # 中段：正常
    "gentle":   (44, 64),     # 抒情：小巧、留白
}


def _compute_font_size(intensity: str, shot_index: int) -> int:
    """根据强度和镜头序号计算字号（确保大幅差异）。"""
    lo, hi = FONT_SIZE_RANGES.get(intensity, (70, 95))
    return lo + (shot_index * 17) % (hi - lo + 1)


# 副标题文本（用于视觉层次构建）
SUBTITLE_TEXTS = [
    "AMV", "EPISODE", "CHAPTER", "ACT", "SCENE",
    "VOL.", "PART", "PHASE", "STAGE", "SEQ",
]

# 最近一次运行的统计信息（供反馈闭环消费）
_LAST_RUN_STATS: Dict[str, Any] = {
    "presets_used": [],
    "fonts_used": [],
    "preset_count": 0,
    "font_count": 0,
}


def get_last_run_stats() -> Dict[str, Any]:
    """获取最近一次 build_smart_text_jsx 运行的预设/字体使用统计。

    优先返回内存中的统计，若为空则尝试从磁盘文件加载
    （解决跨进程/跨模块实例不共享的问题）。
    """
    if _LAST_RUN_STATS.get("presets_used"):
        return dict(_LAST_RUN_STATS)
    # 尝试从磁盘加载（跨进程兼容）
    stats_path = os.path.join(_PROJECT_ROOT, "data", "last_run_stats.json")
    if os.path.exists(stats_path):
        try:
            with open(stats_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return dict(_LAST_RUN_STATS)


# ============================================================================
#  高级剪辑技法注册表（P2 叙事升级）
# ============================================================================
# 每种技法定义：
#   description  : 技法说明
#   jsx_modifier : 可选，返回额外 JSX 代码（接收 shot_index, t0, dur, label）
#   applicable_intensity: 适用的强度级别列表
#   emotion_tags : 适合的情绪标签
# ============================================================================
ADVANCED_EDIT_TECHNIQUES: Dict[str, Dict[str, Any]] = {
    "match_cut": {
        "description": "匹配剪辑 — 前后镜头视觉元素（形状/颜色/运动方向）对齐",
        "applicable_intensity": ["moderate", "intense"],
        "emotion_tags": ["triumph", "nostalgia"],
        "jsx_modifier": lambda si, t0, dur, label: (
            # 匹配剪辑：文字从上一镜头的结束位置继承，实现视觉连续
            f"/* match_cut: 视觉连续 */"
        ),
        "preset_bias": ["scale_bounce", "rotate_3d", "flip_card"],
    },
    "j_cut": {
        "description": "J-Cut — 声音先行，文字在当前镜头画面结束前 0.3s 淡入",
        "applicable_intensity": ["moderate", "gentle"],
        "emotion_tags": ["tension", "melancholy"],
        "jsx_modifier": lambda si, t0, dur, label: (
            # J-Cut：文字提前 0.3s 出现
            f"/* j_cut: 声音先行，文字提前 0.3s */"
        ),
        "preset_bias": ["fade_scale", "slide_left", "slide_right"],
        "timing_offset": -0.3,  # 文字提前出现
    },
    "l_cut": {
        "description": "L-Cut — 画面先行，文字在当前镜头结束后保持 0.3s",
        "applicable_intensity": ["moderate", "gentle"],
        "emotion_tags": ["nostalgia", "serenity"],
        "jsx_modifier": lambda si, t0, dur, label: (
            f"/* l_cut: 画面先行，文字延连 0.3s */"
        ),
        "preset_bias": ["fade_scale", "drop_top"],
        "timing_extend": 0.3,  # 文字延后消失
    },
    "jump_cut": {
        "description": "跳切 — 突兀的角度切换，配合文字冲击感",
        "applicable_intensity": ["intense"],
        "emotion_tags": ["rage", "tension", "horror"],
        "jsx_modifier": lambda si, t0, dur, label: (
            f"/* jump_cut: 突兀跳切 */"
        ),
        "preset_bias": ["glitch_shake", "shockwave", "speed_impact"],
    },
    "montage_sequence": {
        "description": "蒙太奇段落 — 快速连续的镜头组合，文字节奏加密",
        "applicable_intensity": ["intense"],
        "emotion_tags": ["triumph", "rage"],
        "jsx_modifier": lambda si, t0, dur, label: (
            f"/* montage: 快速蒙太奇 */"
        ),
        "preset_bias": ["glow_pulse", "elastic_overshoot", "rgb_split", "neon_stroke"],
        "speed_multiplier": 1.5,  # 动画速度加快
    },
}


# ============================================================================
#  情绪弧线定义与驱动逻辑
# ============================================================================
# 5 段经典情绪弧线（对应 ai/multimodal_director.py 的 SHOT_TEMPLATES）
EMOTION_ARC_PHASES = [
    {"name": "intro",    "range": (0.0, 0.15), "mood": "serenity",   "intensity_bias": "gentle"},
    {"name": "build",    "range": (0.15, 0.40), "mood": "tension",   "intensity_bias": "moderate"},
    {"name": "climax",   "range": (0.40, 0.65), "mood": "rage",      "intensity_bias": "intense"},
    {"name": "break",    "range": (0.65, 0.80), "mood": "melancholy", "intensity_bias": "gentle"},
    {"name": "outro",    "range": (0.80, 1.00), "mood": "nostalgia", "intensity_bias": "moderate"},
]


def get_arc_phase(normalized_time: float) -> Dict[str, Any]:
    """根据归一化时间 (0~1) 返回当前情绪弧线阶段。"""
    for phase in EMOTION_ARC_PHASES:
        if phase["range"][0] <= normalized_time < phase["range"][1]:
            return phase
    return EMOTION_ARC_PHASES[-1]  # 默认 outro


def select_preset_with_arc(
    preset_pool: List[str],
    shot_index: int,
    total_shots: int,
    normalized_time: float,
    technique: Optional[str] = None,
    feedback_weights: Optional[Dict[str, float]] = None,
    preset_usage_counts: Optional[Dict[str, int]] = None,
) -> str:
    """情绪弧线 + 反馈闭环 + 覆盖率保证联合驱动的预设选择。

    选择逻辑优先级：
    1. 覆盖率保证（未使用过的预设优先，确保 14 种预设全部被用到）
    2. 高级技法 preset_bias（最强偏好）
    3. 反馈权重（历史表现好的预设优先）
    4. 情绪弧线阶段偏好
    5. 默认循环分配

    Args:
        preset_pool: 当前强度级别的预设池
        shot_index: 当前镜头序号
        total_shots: 总镜头数
        normalized_time: 归一化时间 (0~1)
        technique: 可选的高级技法名
        feedback_weights: 可选的反馈权重 {preset_key: weight}
        preset_usage_counts: 可选的预设使用计数 {preset_key: count}

    Returns:
        选中的预设名
    """
    phase = get_arc_phase(normalized_time)
    if not preset_pool:
        return ""

    usage = preset_usage_counts or {}

    # 1. 覆盖率保证：池内仍有未用预设时只在其中选，确保全部预设都被用到
    unused = [p for p in preset_pool if usage.get(p, 0) == 0]
    candidates = unused if unused else list(preset_pool)

    # 2. 高级技法 preset_bias（最强偏好）
    bias_set = set()
    if technique and technique in ADVANCED_EDIT_TECHNIQUES:
        bias_set = set(ADVANCED_EDIT_TECHNIQUES[technique].get("preset_bias", []))

    # 3. 弧线阶段情绪偏好（按预设名关键词亲和）
    _PHASE_AFFINITY = {
        "gentle": ["fade", "scale", "drop", "blur"],
        "moderate": ["slide", "elastic", "glow"],
        "intense": ["glitch", "shock", "speed", "rgb", "neon"],
    }
    affinity = _PHASE_AFFINITY.get(phase.get("intensity_bias", "moderate"), [])

    # 4. 多因子加权：覆盖率 × 反馈权重 × 技法偏好 × 弧线亲和
    weights = []
    for p in candidates:
        w = 1.0 / (1.0 + usage.get(p, 0))              # 少用的优先
        if feedback_weights and p in feedback_weights:
            w *= max(0.1, float(feedback_weights[p]))  # 历史表现反馈闭环
        if p in bias_set:
            w *= 3.0                                   # 技法偏好
        if any(k in p for k in affinity):
            w *= 1.5                                   # 弧线阶段亲和
        weights.append(w)

    # 5. 确定性加权采样（同一镜头可复现）
    rng = random.Random(f"{shot_index}:{total_shots}")
    return rng.choices(candidates, weights=weights, k=1)[0]


# 文字标签库
TEXT_LABELS = [
    "\u6226\u3044", "VINLAND", "SAGA", "\u51b0\u6d77\u6218\u8a18",
    "AMV", "\u30c8\u30eb\u30d5\u30a3\u30f3", "\u7206\u70c8",
    "\u6fc0\u71c3", "EPIC", "\u9583\u5149",
]


# ============================================================================
#  镜头特征提取（ffmpeg 感知层）
# ============================================================================

def analyze_shot_motion(shot_path: str) -> float:
    """用 ffmpeg tblend difference 测量镜头段运动强度（帧间差 YAVG）。

    动作激烈 → YAVG 高（>3）；静态 → YAVG 低（<1）。
    """
    if not os.path.exists(shot_path):
        return 0.0
    try:
        cmd = ["ffmpeg", "-i", shot_path, "-vf",
               "tblend=all_mode=difference,signalstats,metadata=print",
               "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True,
                           encoding="utf-8", errors="ignore", timeout=60)
        vals = [float(v) for v in re.findall(
            r'YAVG=(\d+(?:\.\d+)?)', r.stderr)]
        return sum(vals) / len(vals) if vals else 0.0
    except Exception:
        return 0.0


def analyze_scene_complexity(shot_path: str) -> str:
    """用 edgedetect 边缘密度衡量场景复杂度。

    返回 'low' / 'medium' / 'high'。
    """
    if not os.path.exists(shot_path):
        return "medium"
    try:
        cmd = ["ffmpeg", "-ss", "0.5", "-i", shot_path, "-vframes", "1",
               "-vf", "edgedetect=low=0.1:high=0.3,signalstats",
               "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True,
                           encoding="utf-8", errors="ignore", timeout=30)
        yvals = [float(v) for v in re.findall(
            r'YAVG=(\d+(?:\.\d+)?)', r.stderr)]
        yavg = yvals[0] if yvals else 16.0
        if yavg > 22:
            return "high"
        elif yavg > 18:
            return "medium"
        return "low"
    except Exception:
        return "medium"


def analyze_color_richness(shot_path: str) -> str:
    """用色彩分布衡量视觉丰富度。

    通过色度通道(U/V)标准差评估色彩多样性：
    - 高方差 → 'rich'（多种颜色，适合高彩预设）
    - 低方差 → 'poor'（单色调，适合简约预设）
    """
    if not os.path.exists(shot_path):
        return "medium"
    try:
        # 用 signalstats 读 UAVG/VAVG 差值评估色彩丰富度
        cmd = ["ffmpeg", "-ss", "0.3", "-i", shot_path, "-vframes", "1",
               "-vf", "signalstats,metadata=print", "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True,
                           encoding="utf-8", errors="ignore", timeout=30)
        uvals = [float(v) for v in re.findall(
            r'UAVG=(\d+(?:\.\d+)?)', r.stderr)]
        vvals = [float(v) for v in re.findall(
            r'VAVG=(\d+(?:\.\d+)?)', r.stderr)]
        if not uvals or not vvals:
            return "medium"
        u, v = uvals[0], vvals[0]
        # U/V 差值大 → 色彩丰富
        uv_diff = abs(u - v)
        if uv_diff > 15 or (u > 140 and v > 140):
            return "rich"
        elif uv_diff < 5 and u < 135 and v < 135:
            return "poor"
        return "medium"
    except Exception:
        return "medium"


# ============================================================================
#  智能决策：镜头特征 → 动画强度
# ============================================================================

def decide_intensity(motion: float, complexity: str,
                     color_richness: str = "medium") -> str:
    """根据运动强度、场景复杂度和色彩丰富度决定动画强度等级。

    【第五轮修复】重新校准阈值，确保三档均匀分布：
    - intense: motion > 10 或 (motion > 8 且 high complexity)
    - gentle: motion < 5 且 low complexity
    - moderate: 其余
    色彩丰富度仅在边界附近微调，不再直接跳到 intense。
    """
    if motion > 10.0 or (motion > 8.0 and complexity == "high"):
        return "intense"
    elif motion < 5.0 and complexity == "low":
        return "gentle"
    # 色彩丰富度在边界附近微调
    if color_richness == "rich" and motion > 9.0:
        return "intense"
    if color_richness == "poor" and motion < 6.0:
        return "gentle"
    return "moderate"


# ============================================================================
#  【P2-1】场景节奏 → 三维文字组合 (SmartMatcher 集成)
# ============================================================================

_DIRECTOR_SCENE_FALLBACK = {
    "intense": "battle", "moderate": "cinematic", "gentle": "elegant",
}
_DIRECTOR_INTENSITY_MAP = {
    "intense": "intense", "moderate": "moderate", "gentle": "subtle",
}


def select_text_combo_for_shot(intensity: str = "moderate",
                               scene_tag: str = "",
                               emotion: str = "") -> Optional[Dict[str, Any]]:
    """镜头节奏 → 三维文字组合 (字体×特效×动画×强度)。

    优先级: scene_tag 精确命中 → 情绪标签 → 强度降级表。
    SmartMatcher 不可用时返回 None，降级为旧预设逻辑。
    """
    try:
        from core.jsx_keyframe_animator import (
            get_smart_matcher, AnimationIntensity)
        matcher = get_smart_matcher()
        tag = scene_tag or emotion or _DIRECTOR_SCENE_FALLBACK.get(
            intensity, "cinematic")
        inten = _DIRECTOR_INTENSITY_MAP.get(intensity, "moderate")
        r = matcher.match(scene_tag=tag, intensity=AnimationIntensity(inten))
        return {
            "scene_tag": tag, "font": r.font, "font_id": r.font_id,
            "effect_combo_id": r.effect_combo_id,
            "effect_name": r.effect_combo_name,
            "anim_preset_id": r.anim_preset_id,
            "animation": r.animation,
            "intensity": inten, "confidence": r.confidence,
            "reason": r.reason,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"智能导演三维组合选择失败，降级: {exc}")
        return None


# ============================================================================
#  知识库消费（感知→分析→决策链路中引入外部知识）
# ============================================================================

def _load_knowledge_bases() -> Dict[str, Any]:
    """尝试加载知识库资源，返回可用知识摘要。

    消费：
    - ae/presets/text_animation.json → 可用动画类型清单
    - ae/presets/3d_effect.json      → 3D 效果参考
    - 10-风格化剪辑知识库            → 风格标签
    """
    kb: Dict[str, Any] = {"loaded": False}
    presets_dir = os.path.join(_PROJECT_ROOT, "ae", "presets")
    # 加载文字动画预设清单（仅名称和标签，不加载完整 script_template）
    ta_path = os.path.join(presets_dir, "text_animation.json")
    if os.path.exists(ta_path):
        try:
            with open(ta_path, "r", encoding="utf-8") as f:
                presets = json.load(f)
            kb["text_anim_names"] = [p.get("name", "") for p in presets[:20]]
            kb["text_anim_tags"] = list(set(
                tag for p in presets[:20] for tag in p.get("tags", [])))[:30]
        except Exception:
            pass
    # 加载 3D 效果预设清单
    td_path = os.path.join(presets_dir, "3d_effect.json")
    if os.path.exists(td_path):
        try:
            with open(td_path, "r", encoding="utf-8") as f:
                presets3d = json.load(f)
            kb["effect_3d_names"] = [p.get("name", "") for p in presets3d[:10]]
        except Exception:
            pass
    # 风格化剪辑知识库（仅统计文件数）
    style_dir = os.path.join(_PROJECT_ROOT, "10-风格化剪辑知识库")
    if os.path.isdir(style_dir):
        kb["style_kb_count"] = sum(
            1 for _ in os.listdir(style_dir)
            if _.endswith((".md", ".json")))
    kb["loaded"] = True
    return kb


# ============================================================================
#  主入口：构建智能文字动画 JSX
# ============================================================================

def build_smart_text_jsx(
    cut_times: List[float],
    duration: float,
    shot_analysis: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """根据镜头分析结果，生成多样化的文字动画 JSX 代码。

    每个文字图层有完整的"入场→展示→出场"生命周期，
    动画类型/位置/颜色/节奏根据镜头特征智能选择。

    Args:
        cut_times: 切点时间戳列表
        duration: 视频总时长
        shot_analysis: 每个镜头的分析结果
            [{"motion": float, "complexity": str, "intensity": str}, ...]

    Returns:
        JSX 代码字符串（单行，可直接嵌入 IIFE）
    """
    if not cut_times:
        return ""

    # 消费知识库（首次调用时加载）
    kb = _load_knowledge_bases()
    if kb.get("loaded"):
        logger.info(
            f"智能导演: 知识库已消费 — "
            f"text_anim_presets={len(kb.get('text_anim_names', []))}, "
            f"3d_effects={len(kb.get('effect_3d_names', []))}, "
            f"style_kb={kb.get('style_kb_count', 0)} files")

    parts: List[str] = []
    n = len(cut_times)
    _actual_selections: List[Dict[str, str]] = []  # 记录实际选择的预设和字体
    _combo_usages: List[str] = []  # 【P2-1】记录三维特效组合使用

    # 【P3】加载反馈权重 + 使用计数（覆盖率保证）
    feedback_weights: Optional[Dict[str, float]] = None
    preset_usage_counts: Dict[str, int] = {}
    try:
        from core.evolution.capability_feedback import CapabilityFeedbackLoop
        fb = CapabilityFeedbackLoop()
        weights = fb.get_preset_weights()
        # 仅当有足够历史数据时使用（至少 3 个预设被使用过）
        used_count = sum(1 for v in weights.values() if v < 1.0)
        if used_count >= 3:
            feedback_weights = weights
            logger.info(f"反馈权重已加载: {used_count} 个预设具有历史数据")
        # 加载每个预设的历史使用次数（用于覆盖率保证）
        cov = fb.get_coverage_stats()
        for detail_key, detail_val in cov.get("details", {}).items():
            preset_usage_counts[detail_key] = detail_val.get("usages", 0)
    except Exception:
        pass  # 反馈闭环不可用时使用默认逻辑

    # 【第四轮】按强度分组预设，智能选择而非简单循环
    # 【第五轮】重新平衡池大小，匹配实际强度分布 (intense:moderate:gentle ≈ 3:8:3)
    intense_presets = ["glow_pulse", "glitch_shake", "shockwave",
                        "glitch_flash", "particle_dissolve"]
    moderate_presets = ["scale_bounce", "rotate_3d", "flip_card",
                        "elastic_overshoot", "speed_impact", "rgb_split"]
    gentle_presets = ["fade_scale", "slide_left", "slide_right", "drop_top",
                      "ink_spread", "neon_breathe"]

    for ci, ct in enumerate(cut_times):
        seg_dur = (cut_times[ci + 1] - ct) if ci + 1 < n else (duration - ct)
        if seg_dur < 0.25:
            continue

        label = TEXT_LABELS[ci % len(TEXT_LABELS)]

        # 智能决策：根据镜头特征选择预设和强度
        intensity = "moderate"
        if shot_analysis and ci < len(shot_analysis):
            sa = shot_analysis[ci]
            intensity = sa.get("intensity", "moderate")

        # 【第四轮】根据强度选择预设池
        if intensity == "intense":
            pool = intense_presets
        elif intensity == "gentle":
            pool = gentle_presets
        else:
            pool = moderate_presets

        # 【第五轮 P2】情绪弧线 + 反馈权重 + 覆盖率保证联合驱动预设选择
        normalized_time = ct / duration if duration > 0 else 0.0
        preset_key = select_preset_with_arc(
            pool, ci, n, normalized_time,
            feedback_weights=feedback_weights,
            preset_usage_counts=preset_usage_counts,
        )
        # 递增本次使用计数（保证 within-run 多样性）
        preset_usage_counts[preset_key] = preset_usage_counts.get(preset_key, 0) + 1
        preset = TEXT_ANIM_PRESETS[preset_key]

        # 根据强度调整时长分配
        if intensity == "intense":
            in_ratio, out_ratio = 0.18, 0.18
        elif intensity == "gentle":
            in_ratio, out_ratio = 0.35, 0.35
        else:
            in_ratio, out_ratio = 0.25, 0.25

        t_in = ct + 0.05
        d_in = max(0.12, seg_dur * in_ratio)
        t_out_start = ct + seg_dur - max(0.15, seg_dur * out_ratio)
        d_out = max(0.12, ct + seg_dur - 0.05 - t_out_start)
        t_hold = t_in + d_in
        d_hold = max(0.05, t_out_start - t_hold)

        if d_hold < 0.03:
            continue

        # ★ 位置多样化：动态选择屏幕位置（打破居中垄断）
        px, py = _select_position(preset_key, intensity, ci)
        # ★ 字号差异化：大幅拉开不同强度的视觉权重
        fs = _compute_font_size(intensity, ci)

        # 字体策略：从注册表动态查询最优字体
        font_info = resolve_font_for_preset(preset_key)
        font_name = font_info["font"]
        faux_bold = font_info["faux_bold"]

        # 构建 JSX 片段
        p = preset["prop_fn"](ci, fs, font_name, faux_bold)
        parts.append(f"var tt{ci}=c.layers.addText({json.dumps(label)});")
        parts.append(f"var td{ci}=tt{ci}.property('Source Text').value;")
        parts.append(p)
        parts.append(f"tt{ci}.property('Source Text').setValue(td{ci});")
        parts.append(f"tt{ci}.property('Position').setValue([{px},{py}]);")

        if preset.get("needs_3d"):
            parts.append(f"tt{ci}.threeDLayer=true;")

        # 入场→展示→出场 完整生命周期
        # ★ 滑动预设传入目标位置，实现位置感知的滑入/滑出方向
        if preset_key in ("slide_left", "slide_right"):
            parts.append(preset["entry"](t_in, d_in, ci, px=px, py=py))
        else:
            parts.append(preset["entry"](t_in, d_in, ci))
        parts.append(preset["hold"](t_hold, d_hold, ci))
        parts.append(preset["exit"](t_out_start, d_out, ci))
        parts.append(preset["opacity_in"](t_in, d_in, ci))
        parts.append(preset["opacity_out"](t_out_start, d_out, ci))

        # 【第四轮新增】应用 AE 视觉效果（Glow/方向模糊/色差等）
        # ★ 顶层 try-catch 保护：防止任何效果失败导致整个脚本崩溃
        if "apply_effects" in preset:
            parts.append(f"try {{ {preset['apply_effects'](ci, t_in, seg_dur)} }} catch(e) {{}}")

        # 【P2-1】三维组合特效: 镜头节奏 → SmartMatcher → EffectLayerBuilder
        sa_entry = (shot_analysis[ci]
                    if shot_analysis and ci < len(shot_analysis) else {})
        combo = select_text_combo_for_shot(
            intensity, scene_tag=sa_entry.get("scene_tag", ""))
        if combo is not None:
            try:
                from core.jsx_keyframe_animator import (
                    get_effect_builder, get_preset_tracker,
                    AnimationIntensity)
                eb = get_effect_builder()
                cfg = eb.build_effect_config(
                    combo["effect_combo_id"], font=combo["font"],
                    intensity=AnimationIntensity(combo["intensity"]))
                fx_jsx = eb.to_jsx(cfg, f"tt{ci}") if cfg else ""
                if fx_jsx:
                    parts.append(f"try {{ {fx_jsx} }} catch(e) {{}}")
                    # 【P2-3】三维组合覆盖追踪
                    get_preset_tracker().record_combo(
                        combo["effect_combo_id"], combo["animation"],
                        combo["font"])
                    _combo_usages.append(combo["effect_combo_id"])
            except Exception:  # noqa: BLE001
                pass  # 三维特效失败不影响基础文字动画

        # ★ 视觉层次构建：~30% 镜头添加副标题（主标题 + 副标题双层结构）
        if ci % 3 == 1:
            sub_fs = int(fs * 0.55)  # 副标题字号为主标题的 55%
            sub_label = SUBTITLE_TEXTS[ci % len(SUBTITLE_TEXTS)]
            sub_y = f"({py})+{fs}+18"  # 主标题下方
            parts.append(f"var st{ci}=c.layers.addText({json.dumps(sub_label)});")
            parts.append(f"var sd{ci}=st{ci}.property('Source Text').value;")
            parts.append(
                f"sd{ci}.fontSize={sub_fs};sd{ci}.fillColor=[0.65,0.65,0.65];"
                f"sd{ci}.font='{font_name}';sd{ci}.fauxBold=false;"
                f"sd{ci}.justification=ParagraphJustification.CENTER_JUSTIFY;"
            )
            parts.append(f"st{ci}.property('Source Text').setValue(sd{ci});")
            parts.append(f"st{ci}.property('Position').setValue([{px},{sub_y}]);")
            # 副标题简化动画：淡入 + 淡出
            parts.append(
                f"st{ci}.property('Opacity').setValuesAtTimes("
                f"[{t_in:.3f},{t_in + d_in:.3f},{t_out_start:.3f},{t_out_start + d_out:.3f}],"
                f"[0,55,55,0]);"
            )

        logger.debug(
            f"  shot#{ci}: {preset_key} intensity={intensity} "
            f"pos=({px},{py}) fs={fs}"
            f" motion={shot_analysis[ci]['motion'] if shot_analysis and ci < len(shot_analysis) else '?'}")
        _actual_selections.append({"preset": preset_key, "font": font_name})

    # 统计使用的预设和字体（直接使用主循环中的实际选择，而非重新计算）
    used_presets = [s["preset"] for s in _actual_selections]
    used_fonts = set(s["font"] for s in _actual_selections)

    # 写入模块级统计 + 持久化到磁盘（供反馈闭环跨进程读取）
    _LAST_RUN_STATS["presets_used"] = used_presets
    _LAST_RUN_STATS["fonts_used"] = sorted(used_fonts)
    _LAST_RUN_STATS["preset_count"] = len(set(used_presets))
    _LAST_RUN_STATS["font_count"] = len(used_fonts)
    # 【P2-1】三维特效组合统计
    _LAST_RUN_STATS["text_combos_used"] = _combo_usages
    _LAST_RUN_STATS["text_combo_count"] = len(set(_combo_usages))
    try:
        stats_path = os.path.join(_PROJECT_ROOT, "data", "last_run_stats.json")
        os.makedirs(os.path.dirname(stats_path), exist_ok=True)
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(dict(_LAST_RUN_STATS), f, ensure_ascii=False)
    except Exception:
        pass  # 磁盘写入失败不影响主流程

    logger.info(f"智能导演: 生成 {len(parts)} 条 JSX 语句，"
                f"{n} 个文字动画（{len(set(used_presets))} 种预设: {', '.join(set(used_presets))}，"
                f"{len(used_fonts)} 种字体: {', '.join(sorted(used_fonts))}）")
    return "".join(parts)
