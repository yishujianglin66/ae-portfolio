#!/usr/bin/env python3
"""
vocabulary_map.py
Phase 4 - 自然语言→解析词汇映射库 (Python 版)

该模块是 L1 NLU 层的"词典"：
  - 输入：用户输入的自然语言关键词
  - 输出：解析词汇表中的标准术语引用 (VT-XXX)

对齐 TypeScript 端 compiler/src/phase4/vocabulary-map.ts。

数据来源：《解析词汇表与推理决策树》第二章 视觉特征词汇库

设计要点：
  1. 复用 effect_description_parser 中的现有数据类 (VocabRef/ColorRef/IntensityRef/TemporalRef)
     以保证向后兼容性
  2. 提供比 effect_description_parser.scan_vocab 更丰富的同义词覆盖
     (13 个类别，每个条目带多个 keywords 同义词)
  3. 提供 find_vocab (精确匹配) 和 scan_vocab (子串扫描) 两种查找方式
  4. 额外提供 get_temporal_details / get_intensity_level 等元信息查询
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

# 复用现有数据类（向后兼容）
from effect_description_parser import (
    VocabRef, ColorRef, IntensityRef, TemporalRef,
)


# ============================================================================
# 词汇映射条目
# ============================================================================

@dataclass
class VocabMapEntry:
    """词汇映射条目（对齐 TS VocabMapEntry）"""
    vocab_id: str           # 词汇 ID（VT-XXX / KF-XXX）
    vocab_name: str         # 词汇名
    suggested_effect: Optional[str] = None  # 建议的效果 matchName
    confidence: float = 0.0
    keywords: List[str] = None              # 同义关键词列表

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


# ============================================================================
# 模糊类视觉特征词 (VT-001 ~ VT-010)
# ============================================================================

BLUR_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-001", "均匀模糊扩散", "ADBE Gaussian Blur 2", 0.85,
                  ["模糊", "柔化", "虚化", "blur", "gaussian", "高斯模糊",
                   "soffen", "soften", "高斯柔化"]),
    VocabMapEntry("VT-002", "方向性拖尾", "ADBE Directional Blur", 0.90,
                  ["运动模糊", "方向模糊", "拖尾", "motion blur",
                   "directional", "拉丝", "速度线", "动感模糊"]),
    VocabMapEntry("VT-003", "径向辐射模糊", "CC Radial Blur", 0.88,
                  ["径向模糊", "放射模糊", "辐射模糊", "radial blur",
                   "zoom blur", "spin", "旋焦", "变焦模糊"]),
    VocabMapEntry("VT-004", "镜头光斑模糊", "ADBE Camera Lens Blur", 0.82,
                  ["景深", "镜头模糊", "bokeh", "camera blur",
                   "虚化背景", "光斑模糊", "散景", "焦外成像"]),
    VocabMapEntry("VT-005", "方块状模糊", "ADBE Fast Box Blur", 0.65,
                  ["方块模糊", "box blur", "fast blur",
                   "快速模糊", "盒式模糊"]),
    VocabMapEntry("VT-006", "区域差异模糊", "ADBE Compound Blur", 0.75,
                  ["复合模糊", "区域模糊", "compound blur",
                   "depth blur", "差异模糊", "深度模糊"]),
    VocabMapEntry("VT-007", "双向模糊", "ADBE Bilateral Blur", 0.72,
                  ["双边模糊", "bilateral blur", "保边模糊",
                   "表面模糊", "智能模糊"]),
    VocabMapEntry("VT-008", "通道模糊", "ADBE Channel Blur", 0.68,
                  ["通道模糊", "channel blur", "rgb模糊", "分通道模糊"]),
    VocabMapEntry("VT-009", "径向快速模糊", "CC Radial Fast Blur", 0.70,
                  ["快速径向模糊", "radial fast blur",
                   "cc径向模糊", "放射状模糊"]),
    VocabMapEntry("VT-010", "矢量运动模糊", "CC Vector Blur", 0.73,
                  ["矢量模糊", "vector blur", "向量模糊", "方向性柔化"]),
]

# ============================================================================
# 发光类视觉特征词 (VT-101 ~ VT-106)
# ============================================================================

GLOW_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-101", "边缘发光", "ADBE Glo2", 0.80,
                  ["发光", "辉光", "glow", "边缘光",
                   "rim light", "outline glow", "光晕"]),
    VocabMapEntry("VT-102", "区域发光", "ADBE Glo2", 0.78,
                  ["区域发光", "bloom", "soft glow",
                   "整体发光", "全屏辉光"]),
    VocabMapEntry("VT-103", "镜头光斑", "ACP Optical Flares", 0.85,
                  ["镜头光斑", "光斑", "lens flare",
                   "optical flare", "flare"]),
    VocabMapEntry("VT-104", "体积光柱", "CC Light Rays", 0.83,
                  ["体积光", "光柱", "god ray", "light rays",
                   "光线", "光束", "shine"]),
    VocabMapEntry("VT-105", "星芒", "ADBE Starglow", 0.80,
                  ["星芒", "starglow", "star burst",
                   "十字星", "射线星"]),
    VocabMapEntry("VT-106", "多色光晕", "ADBE Deep Glow", 0.75,
                  ["多色光晕", "渐变辉光",
                   "deep glow", "彩色光晕"]),
]

# ============================================================================
# 扭曲类视觉特征词 (VT-201 ~ VT-206)
# ============================================================================

DISTORT_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-201", "流体扭曲", "ADBE Turbulent Displace", 0.85,
                  ["流体扭曲", "湍流", "turbulent",
                   "热浪", "水波", "波动扭曲"]),
    VocabMapEntry("VT-202", "规律波浪", "ADBE Wave Warp", 0.82,
                  ["波浪", "wave warp", "正弦波", "规律波动"]),
    VocabMapEntry("VT-203", "局部变形", "ADBE Liquify", 0.70,
                  ["液化", "liquify", "局部变形",
                   "mesh warp", "网格变形"]),
    VocabMapEntry("VT-204", "透视拉伸", "CC Power Pin", 0.78,
                  ["透视", "四角变形", "power pin",
                   "corner pin", "梯形变形"]),
    VocabMapEntry("VT-205", "液化推拉", "ADBE Liquify", 0.68,
                  ["液化推拉", "推拉变形",
                   "liquify push", "刷子变形"]),
    VocabMapEntry("VT-206", "镜头畸变", "ADBE Optics Compensation", 0.72,
                  ["镜头畸变", "optics compensation",
                   "鱼眼", "桶形畸变", "枕形畸变"]),
]

# ============================================================================
# 色彩类视觉特征词 (VT-301+)
# ============================================================================

COLOR_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-301", "暖色调偏移", "ADBE Color Balance", 0.80,
                  ["暖色", "暖调", "warm", "暖色调", "偏暖"]),
    VocabMapEntry("VT-302", "冷色调偏移", "ADBE Color Balance", 0.80,
                  ["冷色", "冷调", "cool", "冷色调", "偏冷"]),
    VocabMapEntry("VT-303", "青品对比色调", "ADBE Curves", 0.78,
                  ["赛博朋克", "cyberpunk", "青品", "霓虹色调"]),
    VocabMapEntry("VT-304", "橙青电影色调", "ADBE Curves", 0.82,
                  ["电影感", "电影调色", "cinematic",
                   "orange teal", "橙青", "电影色调"]),
    VocabMapEntry("VT-305", "高对比黑白", "ADBE Black & White", 0.85,
                  ["黑白", "单色", "monochrome",
                   "black white", "grayscale"]),
    VocabMapEntry("VT-306", "复古胶片色调", "ADBE Colorista", 0.70,
                  ["复古", "vintage", "胶片",
                   "film", "怀旧", "老电影"]),
    VocabMapEntry("VT-307", "亮度对比度调整",
                  "ADBE Brightness & Contrast 2", 0.85,
                  ["亮度", "对比度", "调亮", "调暗", "变亮", "变暗",
                   "brightness", "contrast", "明暗"]),
]

# ============================================================================
# 粒子类视觉特征词 (VT-401+)
# ============================================================================

PARTICLE_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-401", "离散点状元素", "ACP Particular", 0.88,
                  ["粒子", "particle", "particular",
                   "点状元素", "颗粒"]),
    VocabMapEntry("VT-402", "向上扩散粒子", "ACP Particular", 0.85,
                  ["飘散", "上升粒子", "飘雪", "飘花", "spray"]),
    VocabMapEntry("VT-403", "高速衰减粒子", "ACP Particular", 0.82,
                  ["火花", "spark", "爆炸粒子", "emitter"]),
    VocabMapEntry("VT-404", "缓慢上升云状体", "ACP Form", 0.78,
                  ["烟雾", "smoke", "云雾", "fog", "mist", "form"]),
]

# ============================================================================
# 转场类视觉特征词 (VT-501+)
# ============================================================================

TRANSITION_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-501", "淡入淡出", "ADBE Opacity", 0.90,
                  ["淡入", "淡出", "fade", "dissolve", "渐隐"]),
    VocabMapEntry("VT-502", "位移转场", "ADBE Transform", 0.82,
                  ["滑动", "slide", "位移转场", "推拉转场"]),
    VocabMapEntry("VT-503", "缩放转场", "ADBE Transform", 0.80,
                  ["缩放转场", "zoom transition",
                   "推拉", "scale transition"]),
    VocabMapEntry("VT-504", "旋转转场", "ADBE Transform", 0.78,
                  ["旋转转场", "spin transition",
                   "rotate transition", "翻转"]),
]

# ============================================================================
# 文字类视觉特征词 (VT-601+)
# ============================================================================

TEXT_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-601", "文字弹入", "ADBE Text", 0.85,
                  ["弹入", "bounce in", "弹性入场", "弹簧"]),
    VocabMapEntry("VT-602", "文字打字机", "ADBE Text", 0.88,
                  ["打字机", "typewriter", "逐字显示",
                   "typewriter effect"]),
]

# ============================================================================
# 噪波与颗粒类视觉特征词 (VT-701+)
# ============================================================================

NOISE_GRAIN_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-701", "分形噪波", "ADBE Fractal Noise", 0.88,
                  ["分形噪波", "fractal noise", "噪波",
                   "noise", "噪声", "分形噪声"]),
    VocabMapEntry("VT-702", "颗粒感", "ADBE Noise", 0.82,
                  ["颗粒", "grain", "噪点",
                   "颗粒感", "film grain", "胶片颗粒"]),
    VocabMapEntry("VT-703", "中间值平滑", "ADBE Median", 0.70,
                  ["中间值", "median", "降噪", "平滑", "去噪点"]),
    VocabMapEntry("VT-704", "湍流噪波", "ADBE Turbulent Noise", 0.75,
                  ["湍流噪波", "turbulent noise",
                   "流动噪波", "动态噪波"]),
    VocabMapEntry("VT-705", "杂色", "ADBE Noise Alpha", 0.65,
                  ["杂色", "杂点", "alpha噪波", "通道噪波"]),
]

# ============================================================================
# 通道与键控类视觉特征词 (VT-801+)
# ============================================================================

KEYING_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-801", "颜色键控", "ADBE Color Key", 0.88,
                  ["抠像", "键控", "key", "color key",
                   "抠图", "色键"]),
    VocabMapEntry("VT-802", "亮度键控", "ADBE Luma Key", 0.80,
                  ["亮度键", "luma key",
                   "亮度抠像", "明度键"]),
    VocabMapEntry("VT-803", "轨道遮罩", "ADBE Set Matte", 0.75,
                  ["遮罩", "matte", "轨道蒙版",
                   "set matte", "蒙版设置"]),
    VocabMapEntry("VT-804", "边缘收缩", "ADBE Simple Choker", 0.72,
                  ["收缩", "choker", "边缘收缩",
                   "蒙版收缩", "simple choker"]),
    VocabMapEntry("VT-805", "通道转换", "ADBE Shift Channels", 0.68,
                  ["通道", "channels", "通道转换",
                   "rgb通道", "shift channels"]),
]

# ============================================================================
# 风格化类视觉特征词 (VT-901+)
# ============================================================================

STYLIZE_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-901", "马赛克", "ADBE Mosaic", 0.90,
                  ["马赛克", "mosaic", "打码",
                   "像素化", "pixelate"]),
    VocabMapEntry("VT-902", "边缘检测", "ADBE Find Edges", 0.82,
                  ["描边", "边缘检测", "find edges",
                   "线稿", "轮廓", "勾边"]),
    VocabMapEntry("VT-903", "卡通效果", "ADBE Cartoon", 0.78,
                  ["卡通", "cartoon", "动画风格",
                   "赛璐璐", "cel-shaded"]),
    VocabMapEntry("VT-904", "暗角晕映", "CC Vignette", 0.85,
                  ["暗角", "vignette", "晕映",
                   "边角压暗", "暗角效果"]),
    VocabMapEntry("VT-905", "浮雕效果", "ADBE Emboss", 0.70,
                  ["浮雕", "emboss", "凹凸效果", "立体浮雕"]),
    VocabMapEntry("VT-906", "粗糙边缘", "ADBE Roughen Edges", 0.75,
                  ["粗糙边缘", "roughen edges", "边缘粗糙",
                   "风化效果", "破损边缘"]),
]

# ============================================================================
# 透视与3D类视觉特征词 (VT-1001+)
# ============================================================================

PERSPECTIVE_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-1001", "投影效果", "ADBE Drop Shadow", 0.88,
                  ["投影", "阴影", "drop shadow",
                   "影子", "阴影效果"]),
    VocabMapEntry("VT-1002", "倒角斜面", "ADBE Bevel Alpha", 0.75,
                  ["倒角", "bevel", "斜面",
                   "bevel alpha", "立体边缘"]),
    VocabMapEntry("VT-1003", "基础3D", "ADBE Basic 3D", 0.78,
                  ["3d旋转", "basic 3d", "基础3d",
                   "三维旋转", "空间翻转"]),
    VocabMapEntry("VT-1004", "球体效果", "CC Sphere", 0.72,
                  ["球面", "sphere", "球体",
                   "cc sphere", "球形化"]),
    VocabMapEntry("VT-1005", "圆柱效果", "CC Cylinder", 0.68,
                  ["圆柱", "cylinder", "cc cylinder", "柱面化"]),
    VocabMapEntry("VT-1006", "镜头畸变", "ADBE Optics Compensation", 0.72,
                  ["镜头畸变", "鱼眼",
                   "optics compensation",
                   "桶形畸变", "枕形畸变"]),
]

# ============================================================================
# 生成与绘制类视觉特征词 (VT-1101+)
# ============================================================================

GENERATE_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("VT-1101", "颜色填充", "ADBE Fill", 0.85,
                  ["填充", "fill", "纯色填充", "颜色填充"]),
    VocabMapEntry("VT-1102", "渐变过渡", "ADBE Ramp", 0.82,
                  ["渐变", "ramp", "渐变色",
                   "渐变填充", "过渡色"]),
    VocabMapEntry("VT-1103", "描边路径", "ADBE Stroke", 0.80,
                  ["描边", "stroke", "画线", "路径描边"]),
    VocabMapEntry("VT-1104", "四色渐变", "ADBE 4-Color Gradient", 0.72,
                  ["四色渐变", "4-color gradient",
                   "四角渐变", "多色渐变"]),
    VocabMapEntry("VT-1105", "圆形生成", "ADBE Circle", 0.70,
                  ["圆形", "circle", "圆环", "生成圆形"]),
    VocabMapEntry("VT-1106", "棋盘格", "ADBE Checkerboard", 0.68,
                  ["棋盘格", "checkerboard", "格子", "格纹"]),
    VocabMapEntry("VT-1107", "粒子系统", "CC Particle World", 0.82,
                  ["粒子世界", "粒子特效", "粒子系统",
                   "cc particle world"]),
]

# ============================================================================
# 关键帧动画类词汇 (KF-010+)
# ============================================================================

KEYFRAME_VOCAB: List[VocabMapEntry] = [
    VocabMapEntry("KF-010", "弹性缓入", "ADBE Glo2", 0.80,
                  ["弹入", "弹性", "bounce", "spring", "回弹"]),
    VocabMapEntry("KF-011", "线性渐入", "ADBE Opacity", 0.85,
                  ["淡入", "fade in", "渐入", "线性渐入"]),
    VocabMapEntry("KF-012", "位移渐入", "ADBE Transform", 0.82,
                  ["滑入", "slide in", "位移入场", "从左侧滑入"]),
    VocabMapEntry("KF-013", "缩放渐变", "ADBE Transform", 0.80,
                  ["缩放", "scale", "从小到大", "放大入场"]),
    VocabMapEntry("KF-014", "旋转变换", "ADBE Transform", 0.78,
                  ["旋转", "rotate", "旋转入场", "翻转入场"]),
]

# ============================================================================
# 全部词汇表（合并）
# ============================================================================

ALL_VOCAB: List[VocabMapEntry] = (
    BLUR_VOCAB + GLOW_VOCAB + DISTORT_VOCAB + COLOR_VOCAB +
    PARTICLE_VOCAB + TRANSITION_VOCAB + TEXT_VOCAB +
    NOISE_GRAIN_VOCAB + KEYING_VOCAB + STYLIZE_VOCAB +
    PERSPECTIVE_VOCAB + GENERATE_VOCAB + KEYFRAME_VOCAB
)

# 按 vocab_id 建立快速查找索引
_VOCAB_BY_ID: Dict[str, VocabMapEntry] = {e.vocab_id: e for e in ALL_VOCAB}

# 预编译关键词扫描索引（lower → entry）
# 一个关键词可能对应多个 entry（如 "模糊" 同时匹配 VT-001 等）
_KW_TO_ENTRIES: Dict[str, List[VocabMapEntry]] = {}
for _entry in ALL_VOCAB:
    for _kw in _entry.keywords:
        _kw_lower = _kw.lower()
        if _kw_lower not in _KW_TO_ENTRIES:
            _KW_TO_ENTRIES[_kw_lower] = []
        _KW_TO_ENTRIES[_kw_lower].append(_entry)

# 按长度降序的关键词列表（用于子串扫描时优先匹配长词）
_SORTED_KEYWORDS = sorted(_KW_TO_ENTRIES.keys(), key=len, reverse=True)
_VOCAB_SCAN_RE = re.compile(
    "(?=(" + "|".join(re.escape(k) for k in _SORTED_KEYWORDS) + "))",
    re.IGNORECASE,
)


# ============================================================================
# 颜色映射表（对齐 TS COLOR_MAP，带 temperature）
# ============================================================================

@dataclass
class ColorMapEntry:
    keyword: str
    rgb: List[float]
    temperature: str  # "warm" | "cool" | "neutral"


COLOR_MAP: List[ColorMapEntry] = [
    ColorMapEntry("暖色", [1.0, 0.7, 0.3], "warm"),
    ColorMapEntry("暖金", [1.0, 0.8, 0.4], "warm"),
    ColorMapEntry("橙", [1.0, 0.5, 0.0], "warm"),
    ColorMapEntry("橙色", [1.0, 0.5, 0.0], "warm"),
    ColorMapEntry("红", [1.0, 0.0, 0.0], "warm"),
    ColorMapEntry("红色", [1.0, 0.0, 0.0], "warm"),
    ColorMapEntry("黄", [1.0, 1.0, 0.0], "warm"),
    ColorMapEntry("黄色", [1.0, 1.0, 0.0], "warm"),
    ColorMapEntry("冷色", [0.3, 0.6, 1.0], "cool"),
    ColorMapEntry("青", [0.0, 1.0, 1.0], "cool"),
    ColorMapEntry("青色", [0.0, 1.0, 1.0], "cool"),
    ColorMapEntry("蓝", [0.0, 0.4, 1.0], "cool"),
    ColorMapEntry("蓝色", [0.0, 0.4, 1.0], "cool"),
    ColorMapEntry("紫", [0.6, 0.0, 1.0], "cool"),
    ColorMapEntry("紫色", [0.6, 0.0, 1.0], "cool"),
    ColorMapEntry("品红", [1.0, 0.0, 1.0], "cool"),
    ColorMapEntry("绿", [0.0, 1.0, 0.0], "neutral"),
    ColorMapEntry("绿色", [0.0, 1.0, 0.0], "neutral"),
    ColorMapEntry("白", [1.0, 1.0, 1.0], "neutral"),
    ColorMapEntry("白色", [1.0, 1.0, 1.0], "neutral"),
    ColorMapEntry("黑", [0.0, 0.0, 0.0], "neutral"),
    ColorMapEntry("黑色", [0.0, 0.0, 0.0], "neutral"),
]

_COLOR_KW_LOOKUP: Dict[str, ColorMapEntry] = {
    e.keyword.lower(): e for e in COLOR_MAP
}
_SORTED_COLOR_KW = sorted(_COLOR_KW_LOOKUP.keys(), key=len, reverse=True)
_COLOR_SCAN_RE = re.compile(
    "(?=(" + "|".join(re.escape(k) for k in _SORTED_COLOR_KW) + "))",
    re.IGNORECASE,
)


# ============================================================================
# 强度映射表（对齐 TS INTENSITY_MAP）
# Python IntensityRef 使用 value (0-1)，TS 使用 level + scale
# 这里同时保留 level/scale 元信息供 get_intensity_level 查询
# ============================================================================

@dataclass
class IntensityMapEntry:
    keyword: str
    level: str   # "subtle" | "moderate" | "strong" | "extreme"
    scale: float  # TS 用的 scale 倍率
    value: float  # Python 用的 value (0-1)


INTENSITY_MAP: List[IntensityMapEntry] = [
    IntensityMapEntry("轻微", "subtle", 0.4, 0.3),
    IntensityMapEntry("微微", "subtle", 0.3, 0.2),
    IntensityMapEntry("稍", "subtle", 0.5, 0.3),
    IntensityMapEntry("一点", "subtle", 0.5, 0.2),
    IntensityMapEntry("一些", "subtle", 0.5, 0.3),
    IntensityMapEntry("稍微", "subtle", 0.5, 0.2),
    IntensityMapEntry("略微", "subtle", 0.4, 0.2),
    IntensityMapEntry("subtle", "subtle", 0.4, 0.3),
    IntensityMapEntry("弱", "subtle", 0.3, 0.3),
    IntensityMapEntry("小", "subtle", 0.3, 0.3),
    IntensityMapEntry("低", "subtle", 0.3, 0.3),
    IntensityMapEntry("weak", "subtle", 0.3, 0.3),
    IntensityMapEntry("slight", "subtle", 0.3, 0.3),
    IntensityMapEntry("low", "subtle", 0.3, 0.3),
    IntensityMapEntry("适中", "moderate", 1.0, 0.5),
    IntensityMapEntry("中等", "moderate", 1.0, 0.5),
    IntensityMapEntry("正常", "moderate", 1.0, 0.5),
    IntensityMapEntry("普通", "moderate", 1.0, 0.5),
    IntensityMapEntry("moderate", "moderate", 1.0, 0.5),
    IntensityMapEntry("medium", "moderate", 1.0, 0.5),
    IntensityMapEntry("normal", "moderate", 1.0, 0.5),
    IntensityMapEntry("强烈", "strong", 1.5, 0.8),
    IntensityMapEntry("强", "strong", 1.5, 0.8),
    IntensityMapEntry("明显", "strong", 1.3, 0.7),
    IntensityMapEntry("大", "strong", 1.5, 0.8),
    IntensityMapEntry("高", "strong", 1.5, 0.8),
    IntensityMapEntry("strong", "strong", 1.5, 0.8),
    IntensityMapEntry("high", "strong", 1.5, 0.8),
    IntensityMapEntry("intense", "strong", 1.5, 0.8),
    IntensityMapEntry("夸张", "extreme", 2.0, 1.0),
    IntensityMapEntry("极致", "extreme", 2.0, 1.0),
    IntensityMapEntry("非常强", "extreme", 2.0, 1.0),
    IntensityMapEntry("极强", "extreme", 2.0, 1.0),
    IntensityMapEntry("extreme", "extreme", 2.0, 1.0),
    IntensityMapEntry("very", "extreme", 2.0, 1.0),
]

_INTENSITY_KW_LOOKUP: Dict[str, IntensityMapEntry] = {
    e.keyword.lower(): e for e in INTENSITY_MAP
}
_SORTED_INTENSITY_KW = sorted(_INTENSITY_KW_LOOKUP.keys(), key=len, reverse=True)
_INTENSITY_SCAN_RE = re.compile(
    "(?=(" + "|".join(re.escape(k) for k in _SORTED_INTENSITY_KW) + "))",
    re.IGNORECASE,
)


# ============================================================================
# 时间映射表（对齐 TS TEMPORAL_MAP）
# Python TemporalRef 使用 position (str)，TS 使用 atTime + duration
# 这里同时保留 atTime/duration 元信息供 get_temporal_details 查询
# ============================================================================

@dataclass
class TemporalMapEntry:
    keyword: str
    position: str  # "start" | "end" | "middle" | "custom"
    at_time: Optional[float] = None    # 秒；-1 表示末尾，-0.5 表示中点
    duration: Optional[float] = None   # 秒


TEMPORAL_MAP: List[TemporalMapEntry] = [
    TemporalMapEntry("开头", "start", at_time=0),
    TemporalMapEntry("开始", "start", at_time=0),
    TemporalMapEntry("起点", "start", at_time=0),
    TemporalMapEntry("start", "start", at_time=0),
    TemporalMapEntry("结尾", "end", at_time=-1),
    TemporalMapEntry("结束", "end", at_time=-1),
    TemporalMapEntry("终点", "end", at_time=-1),
    TemporalMapEntry("end", "end", at_time=-1),
    TemporalMapEntry("中间", "middle", at_time=-0.5),
    TemporalMapEntry("中点", "middle", at_time=-0.5),
    TemporalMapEntry("mid", "middle", at_time=-0.5),
    TemporalMapEntry("middle", "middle", at_time=-0.5),
    TemporalMapEntry("center", "middle", at_time=-0.5),
    TemporalMapEntry("持续2秒", "custom", duration=2),
    TemporalMapEntry("持续3秒", "custom", duration=3),
    TemporalMapEntry("持续5秒", "custom", duration=5),
]

_TEMPORAL_KW_LOOKUP: Dict[str, TemporalMapEntry] = {
    e.keyword.lower(): e for e in TEMPORAL_MAP
}
_SORTED_TEMPORAL_KW = sorted(_TEMPORAL_KW_LOOKUP.keys(), key=len, reverse=True)
_TEMPORAL_SCAN_RE = re.compile(
    "(?=(" + "|".join(re.escape(k) for k in _SORTED_TEMPORAL_KW) + "))",
    re.IGNORECASE,
)


# ============================================================================
# 公共 API
# ============================================================================

def find_vocab(keyword: str) -> List[VocabRef]:
    """查找词汇映射（精确匹配）

    对齐 TS findVocab。返回所有匹配的 VocabRef（可能有多个）。

    Args:
        keyword: 用户输入的关键词
    Returns:
        匹配到的词汇引用列表
    """
    refs: List[VocabRef] = []
    kw_lower = keyword.lower()
    entries = _KW_TO_ENTRIES.get(kw_lower)
    if entries:
        for entry in entries:
            refs.append(VocabRef(
                id=entry.vocab_id,
                name=entry.vocab_name,
                matchedKeyword=keyword,
                suggestedEffect=entry.suggested_effect,
                confidence=entry.confidence,
            ))
    return refs


def scan_vocab(text: str) -> List[VocabRef]:
    """在文本中扫描所有词汇（子串匹配）

    对齐 TS scanVocab。使用预编译的正则扫描，长关键词优先匹配。
    每个 vocab_id 只返回一次（去重）。

    Args:
        text: 用户输入文本
    Returns:
        匹配到的所有词汇引用列表
    """
    refs: List[VocabRef] = []
    seen_ids: set = set()
    for m in _VOCAB_SCAN_RE.finditer(text):
        kw_lower = m.group(1).lower()
        entries = _KW_TO_ENTRIES.get(kw_lower)
        if not entries:
            continue
        for entry in entries:
            if entry.vocab_id in seen_ids:
                continue
            seen_ids.add(entry.vocab_id)
            refs.append(VocabRef(
                id=entry.vocab_id,
                name=entry.vocab_name,
                matchedKeyword=m.group(1),
                suggestedEffect=entry.suggested_effect,
                confidence=entry.confidence,
            ))
    return refs


def scan_colors(text: str) -> List[ColorRef]:
    """在文本中扫描颜色

    对齐 TS scanColors。返回所有匹配的 ColorRef。

    Args:
        text: 用户输入文本
    Returns:
        匹配到的颜色引用列表
    """
    refs: List[ColorRef] = []
    seen_keywords: set = set()
    for m in _COLOR_SCAN_RE.finditer(text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen_keywords:
            continue
        seen_keywords.add(kw_lower)
        entry = _COLOR_KW_LOOKUP[kw_lower]
        refs.append(ColorRef(
            keyword=entry.keyword,
            rgb=list(entry.rgb),
            temperature=entry.temperature,
        ))
    return refs


def scan_intensity(text: str) -> List[IntensityRef]:
    """在文本中扫描强度

    对齐 TS scanIntensity。返回 Python 现有 IntensityRef (keyword + value)。
    如需 level/scale 元信息，请使用 get_intensity_details。

    Args:
        text: 用户输入文本
    Returns:
        匹配到的强度引用列表
    """
    refs: List[IntensityRef] = []
    seen_keywords: set = set()
    for m in _INTENSITY_SCAN_RE.finditer(text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen_keywords:
            continue
        seen_keywords.add(kw_lower)
        entry = _INTENSITY_KW_LOOKUP[kw_lower]
        refs.append(IntensityRef(
            keyword=entry.keyword,
            value=entry.value,
        ))
    return refs


def scan_temporal(text: str) -> List[TemporalRef]:
    """在文本中扫描时间

    对齐 TS scanTemporal。返回 Python 现有 TemporalRef (keyword + position)。
    如需 atTime/duration 元信息，请使用 get_temporal_details。

    Args:
        text: 用户输入文本
    Returns:
        匹配到的时间引用列表
    """
    refs: List[TemporalRef] = []
    seen_keywords: set = set()
    for m in _TEMPORAL_SCAN_RE.finditer(text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen_keywords:
            continue
        seen_keywords.add(kw_lower)
        entry = _TEMPORAL_KW_LOOKUP[kw_lower]
        refs.append(TemporalRef(
            keyword=entry.keyword,
            position=entry.position,
        ))
    return refs


# ============================================================================
# 元信息查询 API（TS 端有但 Python 端原本缺失）
# ============================================================================

def get_intensity_details(keyword: str) -> Optional[IntensityMapEntry]:
    """查询强度的 level/scale/value 元信息

    Args:
        keyword: 强度关键词
    Returns:
        IntensityMapEntry 或 None
    """
    return _INTENSITY_KW_LOOKUP.get(keyword.lower())


def get_temporal_details(keyword: str) -> Optional[TemporalMapEntry]:
    """查询时间的 atTime/duration 元信息

    Args:
        keyword: 时间关键词
    Returns:
        TemporalMapEntry 或 None
    """
    return _TEMPORAL_KW_LOOKUP.get(keyword.lower())


def get_intensity_level(value: float) -> str:
    """根据 value (0-1) 推断 level

    Args:
        value: 0-1 之间的强度值
    Returns:
        "subtle" | "moderate" | "strong" | "extreme"
    """
    if value < 0.4:
        return "subtle"
    elif value < 0.7:
        return "moderate"
    elif value < 0.9:
        return "strong"
    else:
        return "extreme"


def get_vocab_by_id(vocab_id: str) -> Optional[VocabMapEntry]:
    """根据 vocab_id 查询词条"""
    return _VOCAB_BY_ID.get(vocab_id)


def get_suggested_effect(vocab_id: str) -> Optional[str]:
    """根据 vocab_id 查询建议的效果 matchName"""
    entry = _VOCAB_BY_ID.get(vocab_id)
    return entry.suggested_effect if entry else None


def get_vocab_stats() -> Dict[str, Any]:
    """获取词汇统计

    对齐 TS getVocabStats。

    Returns:
        {"total": int, "byCategory": {category_name: count}}
    """
    return {
        "total": len(ALL_VOCAB),
        "byCategory": {
            "blur": len(BLUR_VOCAB),
            "glow": len(GLOW_VOCAB),
            "distort": len(DISTORT_VOCAB),
            "color": len(COLOR_VOCAB),
            "particle": len(PARTICLE_VOCAB),
            "transition": len(TRANSITION_VOCAB),
            "text": len(TEXT_VOCAB),
            "noise_grain": len(NOISE_GRAIN_VOCAB),
            "keying": len(KEYING_VOCAB),
            "stylize": len(STYLIZE_VOCAB),
            "perspective": len(PERSPECTIVE_VOCAB),
            "generate": len(GENERATE_VOCAB),
            "keyframe": len(KEYFRAME_VOCAB),
        },
    }


def list_all_keywords() -> List[str]:
    """列出所有关键词（用于调试/测试）"""
    return list(_KW_TO_ENTRIES.keys())


def list_vocab_by_category(category: str) -> List[VocabMapEntry]:
    """按类别列出词汇

    Args:
        category: 类别名 (blur/glow/distort/color/particle/
                  transition/text/noise_grain/keying/stylize/
                  perspective/generate/keyframe)
    Returns:
        该类别的所有 VocabMapEntry
    """
    category_map = {
        "blur": BLUR_VOCAB,
        "glow": GLOW_VOCAB,
        "distort": DISTORT_VOCAB,
        "color": COLOR_VOCAB,
        "particle": PARTICLE_VOCAB,
        "transition": TRANSITION_VOCAB,
        "text": TEXT_VOCAB,
        "noise_grain": NOISE_GRAIN_VOCAB,
        "keying": KEYING_VOCAB,
        "stylize": STYLIZE_VOCAB,
        "perspective": PERSPECTIVE_VOCAB,
        "generate": GENERATE_VOCAB,
        "keyframe": KEYFRAME_VOCAB,
    }
    return category_map.get(category, [])


# ============================================================================
# 模块自测
# ============================================================================

if __name__ == "__main__":
    # 基本功能测试
    print("=== Vocabulary Map 自测 ===")
    stats = get_vocab_stats()
    print(f"总词汇数: {stats['total']}")
    print(f"类别分布: {stats['byCategory']}")

    # 测试 find_vocab
    refs = find_vocab("发光")
    print(f"\nfind_vocab('发光'): {len(refs)} 个结果")
    for r in refs:
        print(f"  - {r.id} {r.name} → {r.suggestedEffect}")

    # 测试 scan_vocab
    text = "给人物加蓝色发光和强烈模糊"
    refs = scan_vocab(text)
    print(f"\nscan_vocab('{text}'): {len(refs)} 个结果")
    for r in refs:
        print(f"  - {r.id} {r.name} (matched: {r.matchedKeyword})")

    # 测试 scan_colors
    colors = scan_colors(text)
    print(f"\nscan_colors: {len(colors)} 个结果")
    for c in colors:
        print(f"  - {c.keyword} rgb={c.rgb} temp={c.temperature}")

    # 测试 scan_intensity
    intensity = scan_intensity(text)
    print(f"\nscan_intensity: {len(intensity)} 个结果")
    for i in intensity:
        details = get_intensity_details(i.keyword)
        print(f"  - {i.keyword} value={i.value} "
              f"level={details.level if details else '?'}")

    print("\n=== 自测完成 ===")
