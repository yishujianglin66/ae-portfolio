#!/usr/bin/env python3
"""
VRS Compiler Bridge - 视频效果分析 → 原子编译器桥接模块
========================================================
将 VideoEffectAnalyzer 的分析结果（JSON）转换为 AE 原子参数编译器
（compiler/src）可执行的 CompilerInput 格式，并支持：
  1. 通过 ae_ts_compiler_client.py 调用 TS 编译器生成 ExtendScript
  2. 直接生成 MCP 命令序列（不经过编译器，供 mcp-extension 执行）

支持的输入格式：
  - video-effect-analyzer.py 的 analyze_video() 返回的简单分析结果
    （包含 basic_info / color_grading / transitions / motion_analysis / visual_effects）
  - VRS 多阶段分析结果（包含 stages.visual_analysis / stages.ae_parameters /
    stages.layer_stack / stages.color_params / stages.rhythm）

输出格式遵循 compiler/src/types.ts 的 CompilerInput 定义。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# =====================================================================
# 效果 matchName 映射表
# 参考 compiler/src/phase3/effect-name-map.ts，扩展覆盖任务要求的全部类别
# =====================================================================

EFFECT_MATCHNAME_MAP: Dict[str, Dict[str, Any]] = {
    # ==================== 模糊类 ====================
    "高斯模糊": {"matchName": "ADBE Gaussian Blur 2", "category": "blur", "params": {"Blurriness": "Blurriness", "Blur Dimensions": "Blur Dimensions"}},
    "Gaussian Blur": {"matchName": "ADBE Gaussian Blur 2", "category": "blur", "params": {"Blurriness": "Blurriness", "Blur Dimensions": "Blur Dimensions"}},
    "方向模糊": {"matchName": "ADBE Directional Blur", "category": "blur", "params": {"Blur Length": "Blur Length", "Direction": "Direction"}},
    "Directional Blur": {"matchName": "ADBE Directional Blur", "category": "blur", "params": {"Blur Length": "Blur Length", "Direction": "Direction"}},
    "运动模糊": {"matchName": "ADBE Directional Blur", "category": "blur", "params": {"Blur Length": "Blur Length", "Direction": "Direction"}},
    "CC Radial Blur": {"matchName": "CC Radial Blur", "category": "blur", "params": {"Amount": "Amount", "Center": "Center", "Type": "Type"}},
    "放射模糊": {"matchName": "CC Radial Blur", "category": "blur", "params": {"Amount": "Amount", "Center": "Center", "Type": "Type"}},
    "镜头模糊": {"matchName": "ADBE Camera Lens Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iris Shape": "Iris Shape", "Highlight Gain": "Highlight Gain"}},
    "Camera Lens Blur": {"matchName": "ADBE Camera Lens Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iris Shape": "Iris Shape", "Highlight Gain": "Highlight Gain"}},
    "失焦模糊": {"matchName": "ADBE Camera Lens Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iris Shape": "Iris Shape"}},
    "Fast Box Blur": {"matchName": "ADBE Box Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iterations": "Iterations"}},
    "方块模糊": {"matchName": "ADBE Box Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iterations": "Iterations"}},
    "Compound Blur": {"matchName": "ADBE Compound Blur", "category": "blur", "params": {"Blur Layer": "Blur Layer", "Maximum Blur": "Maximum Blur"}},
    "CC Cross Blur": {"matchName": "CC Cross Blur", "category": "blur", "params": {"Amount": "Amount"}},
    "CC Force Motion Blur": {"matchName": "ADBE Force Motion Blur", "category": "blur", "params": {"Shutter Angle": "Shutter Angle", "Shutter Samples": "Shutter Samples", "Vector Detail": "Vector Detail"}},
    "CC Vector Blur": {"matchName": "ADBE CC Vector Blur", "category": "blur", "params": {"Type": "Type", "Amount": "Amount", "Angle": "Angle"}},

    # ==================== 发光类 ====================
    "Glow": {"matchName": "ADBE Glo2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}},
    "发光": {"matchName": "ADBE Glo2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}},
    "辉光": {"matchName": "ADBE Glo2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}},
    "ADBE Glow2": {"matchName": "ADBE Glow2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}},
    "Deep Glow": {"matchName": "ADBE Deep Glow", "category": "glow", "params": {"Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity", "Glow Threshold": "Glow Threshold"}},
    "深度发光": {"matchName": "ADBE Deep Glow", "category": "glow", "params": {"Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity", "Glow Threshold": "Glow Threshold"}},
    "Starglow": {"matchName": "ADBE Starglow", "category": "glow", "params": {"Threshold": "Threshold", "Streak Length": "Streak Length", "Boost": "Boost"}},
    "S_Glow": {"matchName": "S_Glow", "category": "glow", "params": {"Threshold": "Threshold", "Width": "Width", "Brightness": "Brightness"}},
    "Sapphire Glow": {"matchName": "S_Glow", "category": "glow", "params": {"Threshold": "Threshold", "Width": "Width", "Brightness": "Brightness"}},
    "Sapphire S_Glow": {"matchName": "S_Glow", "category": "glow", "params": {"Threshold": "Threshold", "Width": "Width", "Brightness": "Brightness"}},

    # ==================== 调色类 ====================
    "Lumetri Color": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Temperature": "Temperature", "Tint": "Tint", "Contrast": "Contrast", "Saturation": "Saturation"}},
    "调色": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Temperature": "Temperature", "Tint": "Tint", "Contrast": "Contrast", "Saturation": "Saturation"}},
    "Curves": {"matchName": "ADBE CurvesCustom", "category": "color", "params": {"Channel": "Channel"}},
    "曲线": {"matchName": "ADBE CurvesCustom", "category": "color", "params": {"Channel": "Channel"}},
    "ADBE Curves": {"matchName": "ADBE CurvesCustom", "category": "color", "params": {"Channel": "Channel"}},
    "Vibrance": {"matchName": "ADBE Vibrance", "category": "color", "params": {"Vibrance": "Vibrance", "Saturation": "Saturation"}},
    "自然饱和度": {"matchName": "ADBE Vibrance", "category": "color", "params": {"Vibrance": "Vibrance", "Saturation": "Saturation"}},
    "Hue/Saturation": {"matchName": "ADBE HUE SATURATION", "category": "color", "params": {"Master Hue": "Master Hue", "Master Saturation": "Master Saturation", "Master Lightness": "Master Lightness"}},
    "色相/饱和度": {"matchName": "ADBE HUE SATURATION", "category": "color", "params": {"Master Hue": "Master Hue", "Master Saturation": "Master Saturation", "Master Lightness": "Master Lightness"}},
    "ADBE HUE COLOR": {"matchName": "ADBE HUE COLOR", "category": "color", "params": {}},
    "Color Balance": {"matchName": "ADBE Color Balance", "category": "color", "params": {"Shadow Red Balance": "Shadow Red Balance", "Midtone Red Balance": "Midtone Red Balance", "Hilight Red Balance": "Hilion Red Balance"}},
    "色彩平衡": {"matchName": "ADBE Color Balance", "category": "color", "params": {"Shadow Red Balance": "Shadow Red Balance", "Midtone Red Balance": "Midtone Red Balance"}},
    "Brightness & Contrast": {"matchName": "ADBE Brightness & Contrast 2", "category": "color", "params": {"Brightness": "Brightness", "Contrast": "Contrast"}},
    "亮度对比度": {"matchName": "ADBE Brightness & Contrast 2", "category": "color", "params": {"Brightness": "Brightness", "Contrast": "Contrast"}},
    "Levels": {"matchName": "ADBE Easy Levels2", "category": "color", "params": {"Input Black": "Input Black", "Input White": "Input White", "Gamma": "Gamma"}},
    "色阶": {"matchName": "ADBE Easy Levels2", "category": "color", "params": {"Input Black": "Input Black", "Input White": "Input White", "Gamma": "Gamma"}},
    "Exposure": {"matchName": "ADBE Exposure2", "category": "color", "params": {"Exposure": "Exposure"}},
    "曝光": {"matchName": "ADBE Exposure2", "category": "color", "params": {"Exposure": "Exposure"}},
    "Posterize": {"matchName": "ADBE Posterize", "category": "color", "params": {"Level": "Level"}},
    "海报化": {"matchName": "ADBE Posterize", "category": "color", "params": {"Level": "Level"}},
    "Vignette": {"matchName": "ADBE Vignette", "category": "color", "params": {"Amount": "Amount", "Softness": "Softness"}},
    "暗角": {"matchName": "ADBE Vignette", "category": "color", "params": {"Amount": "Amount", "Softness": "Softness"}},
    "Drop Shadow": {"matchName": "ADBE Drop Shadow", "category": "color", "params": {"Shadow Color": "Shadow Color", "Opacity": "Opacity", "Direction": "Direction", "Distance": "Distance", "Softness": "Softness"}},
    "投影": {"matchName": "ADBE Drop Shadow", "category": "color", "params": {"Shadow Color": "Shadow Color", "Opacity": "Opacity", "Direction": "Direction", "Distance": "Distance"}},

    # ==================== 扭曲类 ====================
    "Turbulent Displace": {"matchName": "ADBE Turbulent Displace", "category": "distort", "params": {"Amount": "Amount", "Size": "Size", "Complexity": "Complexity", "Evolution": "Evolution"}},
    "湍流置换": {"matchName": "ADBE Turbulent Displace", "category": "distort", "params": {"Amount": "Amount", "Size": "Size", "Complexity": "Complexity", "Evolution": "Evolution"}},
    "Wave Warp": {"matchName": "ADBE Wave Warp", "category": "distort", "params": {"Wave Height": "Wave Height", "Wave Width": "Wave Width", "Direction": "Direction", "Speed": "Speed"}},
    "波浪扭曲": {"matchName": "ADBE Wave Warp", "category": "distort", "params": {"Wave Height": "Wave Height", "Wave Width": "Wave Width", "Direction": "Direction"}},
    "CC Glass": {"matchName": "CC Glass", "category": "distort", "params": {"Surface": "Surface", "Height": "Height", "Displacement": "Displacement"}},
    "CC Bend It": {"matchName": "CC Bend It", "category": "distort", "params": {"Bend": "Bend", "Start": "Start", "End": "End"}},
    "Optics Compensation": {"matchName": "ADBE Optics Compensation", "category": "distort", "params": {"Field of View (FOV)": "Field of View (FOV)", "Reverse Lens Distortion": "Reverse Lens Distortion"}},
    "镜头畸变": {"matchName": "ADBE Optics Compensation", "category": "distort", "params": {"Field of View (FOV)": "Field of View (FOV)", "Reverse Lens Distortion": "Reverse Lens Distortion"}},
    "Bezier Warp": {"matchName": "ADBE Bezier Warp", "category": "distort", "params": {"Top Left Vertex": "Top Left Vertex"}},
    "Mesh Warp": {"matchName": "ADBE Mesh Warp", "category": "distort", "params": {"Rows": "Rows", "Columns": "Columns"}},
    "Liquify": {"matchName": "ADBE Liquify", "category": "distort", "params": {"Warp Tool": "Warp Tool", "Warp Strength": "Warp Strength"}},
    "液化": {"matchName": "ADBE Liquify", "category": "distort", "params": {"Warp Tool": "Warp Tool", "Warp Strength": "Warp Strength"}},
    "CC Page Turn": {"matchName": "CC Page Turn", "category": "distort", "params": {"Fold Position": "Fold Position", "Angle": "Angle"}},
    "Find Edges": {"matchName": "ADBE Find Edges", "category": "distort", "params": {"Invert": "Invert", "Blend with Original": "Blend with Original"}},
    "边缘查找": {"matchName": "ADBE Find Edges", "category": "distort", "params": {"Invert": "Invert", "Blend with Original": "Blend with Original"}},
    "Cartoon": {"matchName": "ADBE Cartoon", "category": "distort", "params": {"Render": "Render", "Edge Threshold": "Edge Threshold", "Edge Width": "Edge Width"}},
    "Echo": {"matchName": "ADBE Echo", "category": "distort", "params": {"Echo Time": "Echo Time", "Number of Echoes": "Number of Echoes", "Decay": "Decay", "Echo Operator": "Echo Operator"}},
    "Shatter": {"matchName": "ADBE Shatter", "category": "distort", "params": {"View": "View", "Shape": "Shape", "Extrusion Depth": "Extrusion Depth"}},

    # ==================== 粒子类 ====================
    "Trapcode Particular": {"matchName": "ACP Particular", "category": "particle", "params": {"Emitter X": "Emitter X", "Emitter Y": "Emitter Y", "Emitter Z": "Emitter Z", "Particles/sec": "Particles/sec", "Velocity": "Velocity", "Life": "Life", "Size": "Size", "Color": "Color"}},
    "Particular": {"matchName": "ACP Particular", "category": "particle", "params": {"Particles/sec": "Particles/sec", "Velocity": "Velocity", "Life": "Life", "Size": "Size", "Color": "Color"}},
    "粒子": {"matchName": "ACP Particular", "category": "particle", "params": {"Particles/sec": "Particles/sec", "Velocity": "Velocity", "Life": "Life", "Size": "Size"}},
    "CC Particle World": {"matchName": "CC Particle World", "category": "particle", "params": {"Producer X": "Producer X", "Producer Y": "Producer Y", "Producer Z": "Producer Z", "Velocity": "Velocity", "Birth Rate": "Birth Rate", "Longevity": "Longevity", "Gravity": "Gravity"}},
    "CC粒子": {"matchName": "CC Particle World", "category": "particle", "params": {"Producer X": "Producer X", "Producer Y": "Producer Y", "Velocity": "Velocity"}},
    "Particle Playground": {"matchName": "ADBE Particle Playground", "category": "particle", "params": {"Cannon Position": "Cannon Position", "Barrel Radius": "Barrel Radius", "Particles Per Second": "Particles Per Second", "Velocity": "Velocity"}},
    "CC Star Burst": {"matchName": "CC Star Burst", "category": "particle", "params": {"Speed": "Speed", "Phase": "Phase"}},
    "Plexus": {"matchName": "ACP Plexus", "category": "particle", "params": {"Points": "Points"}},

    # ==================== 光效类 ====================
    "Optical Flares": {"matchName": "VC Optical Flares", "category": "light", "params": {"Brightness": "Brightness", "Scale": "Scale", "Position XY": "Position XY", "Tint Color": "Tint Color"}},
    "镜头光晕": {"matchName": "VC Optical Flares", "category": "light", "params": {"Brightness": "Brightness", "Scale": "Scale", "Position XY": "Position XY"}},
    "光斑": {"matchName": "VC Optical Flares", "category": "light", "params": {"Brightness": "Brightness", "Scale": "Scale"}},
    "Lens Flare": {"matchName": "ADBE Lens Flare", "category": "light", "params": {"Flare Center": "Flare Center", "Flare Brightness": "Flare Brightness", "Lens Type": "Lens Type"}},
    "CC Light Rays": {"matchName": "CC Light Rays", "category": "light", "params": {"Intensity": "Intensity", "Radius": "Radius", "Warp": "Warp", "Center": "Center"}},
    "体积光": {"matchName": "CC Light Rays", "category": "light", "params": {"Intensity": "Intensity", "Radius": "Radius", "Warp": "Warp", "Center": "Center"}},
    "CC 光线": {"matchName": "CC Light Rays", "category": "light", "params": {"Intensity": "Intensity", "Radius": "Radius", "Center": "Center"}},
    "S_EdgeRays": {"matchName": "S_EdgeRays", "category": "light", "params": {"Intensity": "Intensity", "Ray Length": "Ray Length", "Threshold": "Threshold"}},
    "Sapphire Rays": {"matchName": "S_EdgeRays", "category": "light", "params": {"Intensity": "Intensity", "Ray Length": "Ray Length"}},
    "Trapcode Shine": {"matchName": "TC Shine", "category": "light", "params": {"Ray Length": "Ray Length", "Boost Light": "Boost Light", "Shimmer Amount": "Shimmer Amount", "Source Point": "Source Point"}},
    "Shine": {"matchName": "TC Shine", "category": "light", "params": {"Ray Length": "Ray Length", "Boost Light": "Boost Light", "Source Point": "Source Point"}},
    "Saber": {"matchName": "VC Saber", "category": "light", "params": {"Core Thickness": "Core Thickness", "Glow Intensity": "Glow Intensity", "Glow Width": "Glow Width", "Glow Color": "Glow Color", "Core Color": "Core Color", "Preset Type": "Preset Type"}},
    "能量光剑": {"matchName": "VC Saber", "category": "light", "params": {"Core Thickness": "Core Thickness", "Glow Intensity": "Glow Intensity", "Glow Color": "Glow Color"}},
    "S_EdgeFlash": {"matchName": "S_EdgeFlash", "category": "light", "params": {"Threshold": "Threshold", "Width": "Width", "Brightness": "Brightness", "Color": "Color"}},

    # ==================== 文字类 ====================
    "ADBE Text": {"matchName": "ADBE Text", "category": "text", "params": {"Source Text": "Source Text"}},
    "文本": {"matchName": "ADBE Text", "category": "text", "params": {"Source Text": "Source Text"}},
    "CC Typewriter": {"matchName": "CC Typewriter", "category": "text", "params": {}},
    "打字机": {"matchName": "CC Typewriter", "category": "text", "params": {}},

    # ==================== 转场类 ====================
    "CC Block Load": {"matchName": "CC Block Load", "category": "transition", "params": {"Transition Completion": "Transition Completion"}},
    "CC Glass Wipe": {"matchName": "CC Glass Wipe", "category": "transition", "params": {"Transition Completion": "Transition Completion"}},
    "玻璃擦除": {"matchName": "CC Glass Wipe", "category": "transition", "params": {"Transition Completion": "Transition Completion"}},
    "CC Grid Wipe": {"matchName": "CC Grid Wipe", "category": "transition", "params": {"Transition Completion": "Transition Completion"}},
    "Linear Wipe": {"matchName": "ADBE Linear Wipe", "category": "transition", "params": {"Transition Completion": "Transition Completion", "Wipe Angle": "Wipe Angle", "Feather": "Feather"}},
    "线性擦除": {"matchName": "ADBE Linear Wipe", "category": "transition", "params": {"Transition Completion": "Transition Completion", "Wipe Angle": "Wipe Angle", "Feather": "Feather"}},
    "Venetian Blinds": {"matchName": "ADBE Venetian Blinds", "category": "transition", "params": {"Transition Completion": "Transition Completion", "Direction": "Direction", "Width": "Width", "Feather": "Feather"}},
    "百叶窗": {"matchName": "ADBE Venetian Blinds", "category": "transition", "params": {"Transition Completion": "Transition Completion", "Direction": "Direction", "Width": "Width"}},

    # ==================== 转场-闪白/闪黑类（混剪常用，复合操作）====================
    # 这些转场不通过单一 addEffect 实现，而是用 固态层+混合模式+不透明度关键帧 复合生成
    # transition_type 字段标记走 _build_transition_operations() 路径
    "闪白": {"matchName": "_TRANSITION_FLASH_WHITE", "category": "transition", "params": {}, "transition_type": "flash_white"},
    "闪黑": {"matchName": "_TRANSITION_FLASH_BLACK", "category": "transition", "params": {}, "transition_type": "flash_black"},
    "flash_white": {"matchName": "_TRANSITION_FLASH_WHITE", "category": "transition", "params": {}, "transition_type": "flash_white"},
    "flash_black": {"matchName": "_TRANSITION_FLASH_BLACK", "category": "transition", "params": {}, "transition_type": "flash_black"},
    "white_flash": {"matchName": "_TRANSITION_FLASH_WHITE", "category": "transition", "params": {}, "transition_type": "flash_white"},
    "black_flash": {"matchName": "_TRANSITION_FLASH_BLACK", "category": "transition", "params": {}, "transition_type": "flash_black"},
    "白场过渡": {"matchName": "_TRANSITION_FLASH_WHITE", "category": "transition", "params": {}, "transition_type": "flash_white"},
    "黑场过渡": {"matchName": "_TRANSITION_FLASH_BLACK", "category": "transition", "params": {}, "transition_type": "flash_black"},
    "white_fade": {"matchName": "_TRANSITION_FLASH_WHITE", "category": "transition", "params": {}, "transition_type": "flash_white"},
    "black_fade": {"matchName": "_TRANSITION_FLASH_BLACK", "category": "transition", "params": {}, "transition_type": "flash_black"},
    "亮度闪白/闪黑": {"matchName": "_TRANSITION_FLASH_AUTO", "category": "transition", "params": {}, "transition_type": "flash_auto"},

    # ==================== 转场-其他常见类型 ====================
    "硬切": {"matchName": "_TRANSITION_HARD_CUT", "category": "transition", "params": {}, "transition_type": "hard_cut"},
    "hard_cut": {"matchName": "_TRANSITION_HARD_CUT", "category": "transition", "params": {}, "transition_type": "hard_cut"},
    "淡入淡出": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "fade": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "dissolve": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "叠化": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "cross_dissolve": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "CC Cross Fade": {"matchName": "CC Cross Fade", "category": "transition", "params": {"Transition Completion": "Transition Completion"}, "transition_type": "fade"},
    "缩放转场": {"matchName": "_TRANSITION_ZOOM", "category": "transition", "params": {}, "transition_type": "zoom"},
    "zoom_transition": {"matchName": "_TRANSITION_ZOOM", "category": "transition", "params": {}, "transition_type": "zoom"},
    "滑动": {"matchName": "_TRANSITION_SLIDE", "category": "transition", "params": {}, "transition_type": "slide"},
    "slide": {"matchName": "_TRANSITION_SLIDE", "category": "transition", "params": {}, "transition_type": "slide"},
    "旋转转场": {"matchName": "_TRANSITION_ROTATION", "category": "transition", "params": {}, "transition_type": "rotation"},
    "rotation_transition": {"matchName": "_TRANSITION_ROTATION", "category": "transition", "params": {}, "transition_type": "rotation"},
    "spin": {"matchName": "_TRANSITION_ROTATION", "category": "transition", "params": {}, "transition_type": "rotation"},
    "闪屏": {"matchName": "_TRANSITION_GLITCH", "category": "transition", "params": {}, "transition_type": "glitch_flash"},
    "glitch_flash": {"matchName": "_TRANSITION_GLITCH", "category": "transition", "params": {}, "transition_type": "glitch_flash"},

    # ==================== 变速效果（timeRemap 关键帧）====================
    "加速": {"matchName": "_SPEED_UP", "category": "speed", "params": {}, "speed_type": "speed_up"},
    "speed_up": {"matchName": "_SPEED_UP", "category": "speed", "params": {}, "speed_type": "speed_up"},
    "慢动作": {"matchName": "_SLOW_MOTION", "category": "speed", "params": {}, "speed_type": "slow_motion"},
    "slow_motion": {"matchName": "_SLOW_MOTION", "category": "speed", "params": {}, "speed_type": "slow_motion"},
    "变速": {"matchName": "_SPEED_RAMP", "category": "speed", "params": {}, "speed_type": "speed_ramp"},
    "speed_ramp": {"matchName": "_SPEED_RAMP", "category": "speed", "params": {}, "speed_type": "speed_ramp"},

    # ==================== 调色-预设别名 ====================
    "去色": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Saturation": "Saturation"}, "preset": {"Saturation": -100}},
    "desaturate": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Saturation": "Saturation"}, "preset": {"Saturation": -100}},
    "黑白": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Saturation": "Saturation"}, "preset": {"Saturation": -100}},
    "black_white": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Saturation": "Saturation"}, "preset": {"Saturation": -100}},
    "高对比": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Contrast": "Contrast"}, "preset": {"Contrast": 50}},
    "high_contrast": {"matchName": "ADBE Lumetri", "category": "color", "params": {"Contrast": "Contrast"}, "preset": {"Contrast": 50}},

    # ==================== 发光-别名 ====================
    "edge_glow": {"matchName": "ADBE Glo2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}, "preset": {"Glow Threshold": 80}},
    "边缘发光": {"matchName": "ADBE Glo2", "category": "glow", "params": {"Glow Threshold": "Glow Threshold", "Glow Radius": "Glow Radius", "Glow Intensity": "Glow Intensity"}, "preset": {"Glow Threshold": 80}},

    # ==================== 模糊-别名补充 ====================
    "motion_blur": {"matchName": "ADBE Force Motion Blur", "category": "blur", "params": {"Shutter Angle": "Shutter Angle", "Shutter Samples": "Shutter Samples", "Vector Detail": "Vector Detail"}},
    "径向模糊": {"matchName": "CC Radial Blur", "category": "blur", "params": {"Amount": "Amount", "Center": "Center", "Type": "Type"}},
    "radial_blur": {"matchName": "CC Radial Blur", "category": "blur", "params": {"Amount": "Amount", "Center": "Center", "Type": "Type"}},
    "directional_blur": {"matchName": "ADBE Directional Blur", "category": "blur", "params": {"Blur Length": "Blur Length", "Direction": "Direction"}},

    # ==================== 3D & 其他 ====================
    "Element 3D": {"matchName": "VC Element", "category": "3d", "params": {"Group 1 Model": "Group 1 Model", "Group 1 Position XY": "Group 1 Position XY", "Group 1 Scale": "Group 1 Scale"}},
    "Cineware": {"matchName": "ADBE Cineware", "category": "3d", "params": {"Renderer": "Renderer", "Samples": "Samples"}},
    "CC Radial Fast Blur": {"matchName": "CC Radial Fast Blur", "category": "blur", "params": {"Amount": "Amount", "Center": "Center"}},
    "Fast Blur": {"matchName": "ADBE Box Blur", "category": "blur", "params": {"Blur Radius": "Blur Radius", "Iterations": "Iterations"}},
    "Tint": {"matchName": "ADBE Tint", "category": "color", "params": {"Map Black To": "Map Black To", "Map White To": "Map White To", "Amount of Tint": "Amount of Tint"}},
    "Unsharp Mask": {"matchName": "ADBE Unsharp Mask", "category": "color", "params": {"Amount": "Amount", "Radius": "Radius", "Threshold": "Threshold"}},
    "Noise": {"matchName": "ADBE Noise", "category": "color", "params": {"Amount of Noise": "Amount of Noise"}},
    "Add Grain": {"matchName": "ADBE Add Grain", "category": "color", "params": {"Intensity": "Intensity", "Size": "Size", "Softness": "Softness"}},
}

# =====================================================================
# 缓动类型映射（用户友好名 → 编译器 EasingType）
# =====================================================================

EASING_TYPE_MAP: Dict[str, str] = {
    "linear": "linear",
    "easeIn": "ease_in",
    "ease_in": "ease_in",
    "easeInEaseOut": "ease_in_out",
    "easeOut": "ease_out",
    "ease_out": "ease_out",
    "easeInOut": "ease_in_out",
    "ease_in_out": "ease_in_out",
    "bezier": "bezier",
    "hold": "hold",
}


class VRCompilerBridge:
    """VRS 分析结果 → 编译器 CompilerInput 桥接器。

    主要职责：
        1. 解析 video-effect-analyzer.py 或 VRS 多阶段分析输出
        2. 将 color_grading / transitions / motion_analysis / visual_effects
           转换为编译器 operations 序列
        3. 调用 ae_ts_compiler_client 生成 ExtendScript
        4. 或直接生成 MCP 命令序列供 mcp-extension 执行
    """

    def __init__(
        self,
        compiler_client: Optional[Any] = None,
        default_comp_name: str = "VRS Reproduction Comp",
        default_width: int = 1920,
        default_height: int = 1080,
        default_fps: int = 30,
        default_duration: float = 10.0,
    ) -> None:
        """
        初始化桥接器。

        Args:
            compiler_client: 可选的 AETSCompilerClient 实例，未提供时按需懒加载
            default_comp_name: 默认合成名
            default_width: 默认合成宽度
            default_height: 默认合成高度
            default_fps: 默认帧率
            default_duration: 默认时长（秒）
        """
        self._compiler_client = compiler_client
        self.default_comp_name = default_comp_name
        self.default_width = default_width
        self.default_height = default_height
        self.default_fps = default_fps
        self.default_duration = default_duration

        # 内部状态
        self._op_counter = 0
        self._layer_ref_map: Dict[int, str] = {}  # layer_index → ref_id
        self._effect_ref_map: Dict[str, str] = {}  # effect_uid → ref_id

    # ================================================================
    #  公开 API
    # ================================================================

    def convert_analysis_to_compiler_input(self, analysis_result: dict) -> dict:
        """将视频效果分析结果转换为编译器 CompilerInput 格式。

        自动识别输入格式：
            - 简单格式（analyze_video 输出）：包含 basic_info / color_grading /
              transitions / motion_analysis / visual_effects
            - VRS 多阶段格式：包含 stages.visual_analysis / stages.ae_parameters /
              stages.layer_stack / stages.color_params

        Args:
            analysis_result: 分析结果字典

        Returns:
            CompilerInput 格式的字典，含 metadata 与 operations 字段
        """
        # 重置内部状态
        self._op_counter = 0
        self._layer_ref_map.clear()
        self._effect_ref_map.clear()

        operations: List[Dict[str, Any]] = []

        # 提取基础信息（合成参数）
        comp_info = self._extract_composition_info(analysis_result)
        comp_ref = "main_comp"
        operations.append({
            "op": "createComp",
            "ref": comp_ref,
            "name": comp_info["name"],
            "width": comp_info["width"],
            "height": comp_info["height"],
            "frameRate": comp_info["fps"],
            "duration": comp_info["duration"],
            "bgColor": [0, 0, 0],
        })

        # 提取图层信息（如果有）
        layers = self._extract_layers(analysis_result)
        for layer in layers:
            layer_ref = layer["ref"]
            self._layer_ref_map[layer["index"]] = layer_ref
            layer_type = layer.get("type", "solid")
            op: Dict[str, Any] = {
                "op": "addLayer",
                "ref": layer_ref,
                "compRef": comp_ref,
                "layerType": layer_type,
                "name": layer.get("name", f"Layer {layer['index']}"),
            }
            # 根据图层类型补齐必填字段（TS 编译器 validator 要求）
            if layer_type == "solid":
                op["color"] = layer.get("color", [0, 0, 0])
                op["width"] = comp_info["width"]
                op["height"] = comp_info["height"]
            elif layer_type == "footage":
                # footage 类型必须有 filePath（使用占位符，由调用方替换）
                op["filePath"] = layer.get("file_path", layer.get("filePath", "<placeholder.mp4>"))
            elif layer_type == "adjustment":
                # 调整层：补齐默认尺寸
                op["width"] = comp_info["width"]
                op["height"] = comp_info["height"]
            if layer.get("color") is not None and "color" not in op:
                op["color"] = layer["color"]
            if layer.get("opacity") is not None:
                op["opacity"] = layer["opacity"]
            if layer.get("blend_mode") and layer["blend_mode"] != "normal":
                # 混合模式通过独立操作设置
                pass
            operations.append(op)

        # 为非 normal 混合模式添加 setBlendMode 操作
        for layer in layers:
            if layer.get("blend_mode") and layer["blend_mode"] != "normal":
                layer_ref = self._layer_ref_map.get(layer["index"], f"layer_{layer['index']:03d}")
                operations.append({
                    "op": "setBlendMode",
                    "ref": self._next_ref("blend"),
                    "layerRef": layer_ref,
                    "blendMode": self._normalize_blend_mode(layer["blend_mode"]),
                    "dependsOn": [layer["ref"]],
                })

        # 提取调色（Lumetri）
        color_ops = self._build_color_grading_ops(analysis_result, layers)
        operations.extend(color_ops)

        # 提取转场
        transition_ops = self._build_transition_ops(analysis_result, layers)
        operations.extend(transition_ops)

        # 提取速度变化（timeRemap）
        motion = self._extract_motion(analysis_result)
        speed_ops = self._build_speed_change_ops(motion, layers)
        operations.extend(speed_ops)

        # 提取相机运动（缩放/位移关键帧）
        camera_ops = self._build_camera_motion_ops(motion, layers, comp_info)
        operations.extend(camera_ops)

        # 提取视觉效果
        vfx = self._extract_visual_effects(analysis_result)
        vfx_ops = self.build_operations_from_effects(vfx, layers)
        operations.extend(vfx_ops)

        # 提取视觉分析中识别的插件效果（VRS 多阶段格式）
        plugin_ops = self._build_plugin_ops_from_visual_analysis(analysis_result, layers)
        operations.extend(plugin_ops)

        # 排序：createComp → addLayer → setBlendMode → 其他（按 layer_index → time → dependency）
        operations = self._sort_operations(operations)

        compiler_input = {
            "metadata": {
                "source": "vrs_compiler_bridge",
                "description": f"VRS 分析转换 - {comp_info['name']}",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "operation_count": len(operations),
            },
            "operations": operations,
        }

        logger.info(
            "VRS bridge: 转换完成 - 合成 {}x{}@{}fps 时长{}s, 操作数 {}",
            comp_info["width"], comp_info["height"], comp_info["fps"],
            comp_info["duration"], len(operations),
        )
        return compiler_input

    def build_operations_from_effects(
        self, effects: list, layers: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """将效果列表转换为原子操作序列。

        每个效果映射为：
            - 转场类效果（闪白/闪黑/淡入淡出等）→ 复合操作：
              addLayer(solid) + setBlendMode + setKeyframe(opacity)
            - 普通效果 → addEffect 操作（必须） + setKeyframe 操作（如果带关键帧）

        Args:
            effects: 效果列表，每项为 dict，可包含字段：
                - name / effect / ae_effect: 效果名（人类可读）
                - matchName / matchname: AE matchName（优先使用）
                - layerIndex: 目标图层索引
                - params / key_params / settings / ae_params: 效果参数
                - time / time_sec: 应用时间点（秒）
                - keyframes: 关键帧列表
                - confidence: 置信度
            layers: 可选的图层列表，用于查找 layerRef

        Returns:
            操作列表，每个操作遵循 compiler/src/types.ts 的 AddEffectOp/SetKeyframeOp 格式
        """
        layers = layers or []
        operations: List[Dict[str, Any]] = []

        for idx, fx in enumerate(effects):
            if not isinstance(fx, dict):
                continue

            # 解析效果名（用于查表和判断转场）
            effect_name = (
                fx.get("name")
                or fx.get("effect")
                or fx.get("ae_effect")
                or ""
            )

            # 显式 matchName（如果存在，则不是转场类，直接走 addEffect 路径）
            explicit_matchname = fx.get("matchName") or fx.get("matchname")

            # 解析时间（同时支持 time / time_sec 字段，兼容 vrs_demo 格式）
            apply_time = fx.get("time", fx.get("time_sec", 0))

            # 解析目标图层
            layer_index = fx.get("layerIndex", fx.get("layer_index", 1))

            # ============================================================
            # 转场类效果优先处理：使用复合操作生成
            # （闪白/闪黑/淡入淡出等不能通过单一 addEffect 实现）
            # ============================================================
            if not explicit_matchname and self._is_transition_effect(effect_name):
                # 解析参数（兼容多种字段名）
                tr_params = (
                    fx.get("params")
                    or fx.get("ae_params")
                    or fx.get("key_params")
                    or fx.get("settings")
                    or {}
                )
                if not isinstance(tr_params, dict):
                    tr_params = {}

                transition_ops = self._build_transition_operations(
                    effect_name=effect_name,
                    layer_index=layer_index,
                    time_sec=float(apply_time),
                    params=tr_params,
                    layers=layers,
                )
                if transition_ops:
                    operations.extend(transition_ops)
                    logger.debug(
                        "VRS bridge: 生成转场操作 {} @ {:.2f}s ({} ops)",
                        effect_name, float(apply_time), len(transition_ops),
                    )
                else:
                    logger.debug(
                        "VRS bridge: 转场 {} @ {:.2f}s 无需生成操作",
                        effect_name, float(apply_time),
                    )
                continue

            # ============================================================
            # 普通效果：生成 addEffect 操作
            # ============================================================
            match_name = explicit_matchname or self._lookup_matchname(effect_name)
            if not match_name:
                logger.warning("VRS bridge: 跳过未知效果: {}", effect_name or "unknown")
                continue

            layer_ref = self._resolve_layer_ref(layer_index, layers)

            # 解析效果参数
            params = (
                fx.get("params")
                or fx.get("key_params")
                or fx.get("settings")
                or {}
            )
            # 过滤非原子值（保留 number/string/bool/array）
            clean_params = self._sanitize_params(params)

            # 生成 addEffect 操作
            fx_ref = self._next_ref("fx")
            effect_uid = f"{match_name}@layer{layer_index}@{idx}"
            self._effect_ref_map[effect_uid] = fx_ref

            add_effect_op: Dict[str, Any] = {
                "op": "addEffect",
                "ref": fx_ref,
                "layerRef": layer_ref,
                "matchName": match_name,
                "dependsOn": [layer_ref],
            }

            # 显示名
            if effect_name and effect_name != match_name:
                add_effect_op["name"] = effect_name

            # 静态参数作为 settings
            if clean_params:
                add_effect_op["settings"] = clean_params

            operations.append(add_effect_op)

            # 关键帧处理
            keyframes = fx.get("keyframes") or []
            if keyframes:
                kf_op = self._build_keyframe_op(
                    layer_ref=layer_ref,
                    fx_ref=fx_ref,
                    keyframes=keyframes,
                    default_property=self._guess_default_property(match_name),
                )
                if kf_op:
                    operations.append(kf_op)

            # 记录置信度到日志
            confidence = fx.get("confidence")
            if confidence is not None and confidence < 0.7:
                logger.debug(
                    "VRS bridge: 低置信度效果 {} ({:.2f})",
                    match_name, confidence,
                )

        return operations

    def _is_transition_effect(self, effect_name: str) -> bool:
        """判断效果名是否为转场类效果（需要复合操作生成）。

        转场类效果（如闪白/闪黑/淡入淡出）需要生成
        addLayer + setBlendMode + setKeyframe 复合操作序列，
        而非单一的 addEffect 操作。

        判定规则：EFFECT_MATCHNAME_MAP 中对应条目带 transition_type 字段。

        Args:
            effect_name: 效果名（可为中英文别名）

        Returns:
            True 表示是转场类效果，False 表示是普通效果
        """
        if not effect_name:
            return False
        # 精确匹配
        entry = EFFECT_MATCHNAME_MAP.get(effect_name)
        if entry and entry.get("transition_type"):
            return True
        # 大小写不敏感匹配
        name_lower = effect_name.lower()
        for key, ent in EFFECT_MATCHNAME_MAP.items():
            if key.lower() == name_lower and ent.get("transition_type"):
                return True
        return False

    def _build_transition_operations(
        self,
        effect_name: str,
        layer_index: int,
        time_sec: float,
        params: Dict[str, Any],
        layers: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """生成转场效果操作序列。

        闪白/闪黑转场不通过 addEffect 实现，而是通过：
            1. 添加固态层（白色/黑色）
            2. 设置混合模式（SCREEN / NORMAL / MULTIPLY）
            3. 添加不透明度关键帧（0→100→0 形成闪烁）

        其他转场类型（淡入淡出/缩放/滑动/旋转）则直接对目标图层
        生成对应属性的关键帧操作。

        Args:
            effect_name: 转场效果名（如"闪白"/"闪黑"/"淡入淡出"）
            layer_index: 目标图层索引
            time_sec: 转场发生时间点（秒）
            params: 额外参数，可包含：
                - duration: 转场持续时间（秒，默认 0.3）
                - from / to: 缩放/位移起止值
                - value: 亮度值（用于 flash_auto 自动判定闪白/闪黑）
            layers: 可选的图层列表，用于查找 layerRef

        Returns:
            操作列表，包含 addLayer / setBlendMode / setKeyframe 操作；
            若为硬切则返回空列表（仅时间点标记）
        """
        layers = layers or []

        # 查找转场类型
        transition_type: Optional[str] = None
        entry = EFFECT_MATCHNAME_MAP.get(effect_name)
        if entry:
            transition_type = entry.get("transition_type")
        if not transition_type:
            # 大小写不敏感回退
            name_lower = effect_name.lower()
            for key, ent in EFFECT_MATCHNAME_MAP.items():
                if key.lower() == name_lower and ent.get("transition_type"):
                    transition_type = ent["transition_type"]
                    break
        if not transition_type:
            return []

        # 解析持续时间（默认 0.3s），限制到 [0.1, 2.0]
        try:
            duration = float(params.get("duration", 0.3))
        except (TypeError, ValueError):
            duration = 0.3
        duration = max(0.1, min(duration, 2.0))

        # 解析目标图层引用
        target_layer_ref = self._resolve_layer_ref(layer_index, layers)

        # ============================================================
        # flash_auto: 根据 brightness value 自动判定闪白/闪黑
        # ============================================================
        if transition_type == "flash_auto":
            value = params.get("value")
            # value > 0 → 闪白；value < 0 → 闪黑；value == 0 默认闪白
            try:
                brightness = float(value) if value is not None else 100.0
            except (TypeError, ValueError):
                brightness = 100.0
            transition_type = "flash_white" if brightness >= 0 else "flash_black"

        # ============================================================
        # 硬切：仅时间点标记，不生成任何操作
        # ============================================================
        if transition_type == "hard_cut":
            logger.debug("VRS bridge: 硬切转场 @ {:.2f}s，无需生成操作", time_sec)
            return []

        # ============================================================
        # 淡入淡出/叠化：直接对目标图层设置 Opacity 关键帧
        # ============================================================
        if transition_type == "fade":
            kf_op = self._build_keyframe_op(
                layer_ref=target_layer_ref,
                fx_ref=None,
                keyframes=[
                    {"property": "Opacity", "time": time_sec, "value": 0, "easing": "ease_in_out"},
                    {"property": "Opacity", "time": time_sec + duration, "value": 100, "easing": "ease_in_out"},
                ],
                default_property="Transform/Opacity",
            )
            return [kf_op] if kf_op else []

        # ============================================================
        # 缩放转场：Scale 关键帧
        # ============================================================
        if transition_type == "zoom":
            scale_from = self._parse_numeric(params.get("from"), default=100) or 100
            scale_to = self._parse_numeric(params.get("to"), default=130) or 130
            kf_op = self._build_keyframe_op(
                layer_ref=target_layer_ref,
                fx_ref=None,
                keyframes=[
                    {"property": "Scale", "time": time_sec, "value": float(scale_from), "easing": "ease_in_out"},
                    {"property": "Scale", "time": time_sec + duration, "value": float(scale_to), "easing": "ease_in_out"},
                ],
                default_property="Transform/Scale",
            )
            return [kf_op] if kf_op else []

        # ============================================================
        # 滑动转场：Position 关键帧（从屏幕外滑入）
        # ============================================================
        if transition_type == "slide":
            kf_op = self._build_keyframe_op(
                layer_ref=target_layer_ref,
                fx_ref=None,
                keyframes=[
                    {"property": "Position", "time": time_sec,
                     "value": [self.default_width + 100, self.default_height / 2],
                     "easing": "ease_in_out"},
                    {"property": "Position", "time": time_sec + duration,
                     "value": [self.default_width / 2, self.default_height / 2],
                     "easing": "ease_in_out"},
                ],
                default_property="Transform/Position",
            )
            return [kf_op] if kf_op else []

        # ============================================================
        # 旋转转场：Rotation 关键帧（0 → 360）
        # ============================================================
        if transition_type == "rotation":
            kf_op = self._build_keyframe_op(
                layer_ref=target_layer_ref,
                fx_ref=None,
                keyframes=[
                    {"property": "Rotation", "time": time_sec, "value": 0, "easing": "ease_in_out"},
                    {"property": "Rotation", "time": time_sec + duration, "value": 360, "easing": "ease_in_out"},
                ],
                default_property="Transform/Rotation",
            )
            return [kf_op] if kf_op else []

        # ============================================================
        # 闪屏（glitch_flash）：用灰色固态层 + DIFFERENCE 混合模拟
        # ============================================================
        if transition_type == "glitch_flash":
            color = [128, 128, 128]
            blend_mode = "difference"
            layer_name = f"闪屏_{time_sec:.2f}s"
        elif transition_type == "flash_white":
            # 闪白：白色固态层 + SCREEN 混合 + Opacity 0→100→0
            color = [255, 255, 255]
            blend_mode = "screen"
            layer_name = f"闪白_{time_sec:.2f}s"
        elif transition_type == "flash_black":
            # 闪黑：黑色固态层 + NORMAL 混合 + Opacity 0→100→0
            color = [0, 0, 0]
            blend_mode = "normal"
            layer_name = f"闪黑_{time_sec:.2f}s"
        else:
            logger.warning("VRS bridge: 未知转场类型: {}", transition_type)
            return []

        # ============================================================
        # 通用闪白/闪黑/闪屏流程：
        # 1. 添加固态层
        # 2. 设置混合模式
        # 3. 设置不透明度关键帧（0 → 100 → 0 形成闪烁）
        # ============================================================
        ops: List[Dict[str, Any]] = []
        solid_ref = self._next_ref("solid")

        # 1. 添加固态层（带起止时间，仅在转场期间存在）
        ops.append({
            "op": "addLayer",
            "ref": solid_ref,
            "compRef": "main_comp",
            "layerType": "solid",
            "name": layer_name,
            "color": color,
            "width": self.default_width,
            "height": self.default_height,
            "startTime": time_sec,
            "duration": duration,
            "dependsOn": ["main_comp"],
        })

        # 2. 设置混合模式
        blend_ref = self._next_ref("blend")
        ops.append({
            "op": "setBlendMode",
            "ref": blend_ref,
            "layerRef": solid_ref,
            "blendMode": self._normalize_blend_mode(blend_mode),
            "dependsOn": [solid_ref],
        })

        # 3. 设置不透明度关键帧（0 → 100 → 0）
        kf_ref = self._next_ref("kf")
        # 关键帧时间点：开始(t) → 峰值(t+0.1s 或 duration/2) → 结束(t+duration)
        peak_offset = min(0.1, duration / 2)
        peak_time = time_sec + peak_offset
        end_time = time_sec + duration
        ops.append({
            "op": "setKeyframe",
            "ref": kf_ref,
            "layerRef": solid_ref,
            "propertyPath": "Transform/Opacity",
            "keyframes": [
                {"time": time_sec, "value": 0, "easing": {"type": "ease_out"}},
                {"time": peak_time, "value": 100, "easing": {"type": "linear"}},
                {"time": end_time, "value": 0, "easing": {"type": "ease_in"}},
            ],
            "dependsOn": [solid_ref],
        })

        return ops

    def build_keyframe_operations(
        self,
        transitions: list,
        speed_changes: list,
        motion: dict,
    ) -> List[Dict[str, Any]]:
        """将转场、速度变化、相机运动转换为关键帧操作。

        支持缓动类型：linear / easeIn / easeOut / easeInOut

        Args:
            transitions: 转场列表，每项含 time_sec / type / duration / ae_params
            speed_changes: 速度变化列表，每项含 time_sec / type / ae_params
            motion: 相机运动信息，含 camera_motion / zoom_range / pan_range 等

        Returns:
            setKeyframe 操作列表
        """
        operations: List[Dict[str, Any]] = []

        # 转场关键帧（属性：Opacity 或 Transition Completion）
        for tr in transitions or []:
            if not isinstance(tr, dict):
                continue
            t_sec = tr.get("time_sec", tr.get("time", 0))
            t_dur = tr.get("duration", 0.5)
            t_type = tr.get("type", "fade")
            ae_params = tr.get("ae_params") or {}

            if t_type in ("fade", "dissolve", "淡入淡出"):
                # Opacity 关键帧：0 → 100
                kf_op = self._build_keyframe_op(
                    layer_ref="layer_001",
                    fx_ref=None,
                    keyframes=[
                        {"property": "Opacity", "time": t_sec, "value": 0, "easing": "easeInOut"},
                        {"property": "Opacity", "time": t_sec + t_dur, "value": 100, "easing": "easeInOut"},
                    ],
                    default_property="Transform/Opacity",
                )
                if kf_op:
                    operations.append(kf_op)
            elif t_type in ("wipe", "linear_wipe", "线性擦除"):
                completion = ae_params.get("Transition Completion", 0)
                kf_op = self._build_keyframe_op(
                    layer_ref="layer_001",
                    fx_ref=None,
                    keyframes=[
                        {"property": "Transition Completion", "time": t_sec, "value": 0, "easing": "linear"},
                        {"property": "Transition Completion", "time": t_sec + t_dur, "value": 100, "easing": "easeInOut"},
                    ],
                    default_property="Effects.Linear Wipe.Transition Completion",
                )
                if kf_op:
                    operations.append(kf_op)
            elif t_type in ("zoom", "缩放"):
                # Scale 关键帧
                scale_start = ae_params.get("scale_start", 100)
                scale_end = ae_params.get("scale_end", 130)
                kf_op = self._build_keyframe_op(
                    layer_ref="layer_001",
                    fx_ref=None,
                    keyframes=[
                        {"property": "Scale", "time": t_sec, "value": scale_start, "easing": "easeInOut"},
                        {"property": "Scale", "time": t_sec + t_dur, "value": scale_end, "easing": "easeInOut"},
                    ],
                    default_property="Transform/Scale",
                )
                if kf_op:
                    operations.append(kf_op)

        # 速度变化关键帧（属性：timeRemap）
        for sc in speed_changes or []:
            if not isinstance(sc, dict):
                continue
            t_sec = sc.get("time_sec", sc.get("time", 0))
            speed_type = sc.get("type", "normal")
            ae_params = sc.get("ae_params") or {}

            # speed_factor: 1.0 = 原速, 0.5 = 慢动作, 2.0 = 加速
            speed_factor = ae_params.get("speed_factor", 1.0)
            if speed_type == "slow_motion":
                target_factor = 0.3
            elif speed_type == "fast_forward":
                target_factor = 3.0
            else:
                target_factor = float(speed_factor)

            kf_op = self._build_keyframe_op(
                layer_ref="layer_001",
                fx_ref=None,
                keyframes=[
                    {"property": "timeRemap", "time": t_sec, "value": t_sec, "easing": "easeInOut"},
                    {"property": "timeRemap", "time": t_sec + 0.1, "value": t_sec + 0.1 * target_factor, "easing": "easeInOut"},
                ],
                default_property="Time Remap",
            )
            if kf_op:
                operations.append(kf_op)

        # 相机运动关键帧（属性：Scale / Position）
        camera_motion = (motion or {}).get("camera_motion", "")
        if camera_motion in ("持续缩放进入", "zoom_in", "push_in"):
            zoom_range = (motion or {}).get("zoom_range", (100, 130))
            kf_op = self._build_keyframe_op(
                layer_ref="layer_001",
                fx_ref=None,
                keyframes=[
                    {"property": "Scale", "time": 0, "value": zoom_range[0], "easing": "easeInOut"},
                    {"property": "Scale", "time": self.default_duration, "value": zoom_range[1], "easing": "easeInOut"},
                ],
                default_property="Transform/Scale",
            )
            if kf_op:
                operations.append(kf_op)
        elif camera_motion in ("持续缩放退出", "zoom_out", "pull_out"):
            zoom_range = (motion or {}).get("zoom_range", (130, 100))
            kf_op = self._build_keyframe_op(
                layer_ref="layer_001",
                fx_ref=None,
                keyframes=[
                    {"property": "Scale", "time": 0, "value": zoom_range[0], "easing": "easeInOut"},
                    {"property": "Scale", "time": self.default_duration, "value": zoom_range[1], "easing": "easeInOut"},
                ],
                default_property="Transform/Scale",
            )
            if kf_op:
                operations.append(kf_op)
        elif camera_motion in ("pan_left", "pan_right", "横向摇移"):
            pan_range = (motion or {}).get("pan_range", (0, 200))
            direction = 1 if camera_motion == "pan_right" else -1
            kf_op = self._build_keyframe_op(
                layer_ref="layer_001",
                fx_ref=None,
                keyframes=[
                    {"property": "Position", "time": 0, "value": [960 + pan_range[0] * direction, 540], "easing": "easeInOut"},
                    {"property": "Position", "time": self.default_duration, "value": [960 + pan_range[1] * direction, 540], "easing": "easeInOut"},
                ],
                default_property="Transform/Position",
            )
            if kf_op:
                operations.append(kf_op)

        return operations

    def compile_to_script(self, compiler_input: dict) -> dict:
        """调用 ae_ts_compiler_client 执行编译，生成 ExtendScript 脚本。

        Args:
            compiler_input: CompilerInput 格式字典（含 metadata / operations）

        Returns:
            {
                "success": bool,
                "script_content": str,
                "errors": list,
                "warnings": list,
                "stats": dict
            }
        """
        client = self._get_compiler_client()
        if client is None:
            return {
                "success": False,
                "script_content": "",
                "errors": ["编译器客户端不可用（ae_ts_compiler_client 未找到或 node 不可用）"],
                "warnings": [],
                "stats": {"operationCount": 0, "compileTimeMs": 0},
            }

        # 将 CompilerInput 转换为 ae_ts_compiler_client 期望的 planning_result 格式
        # （通过 _run_compiler 直接调用，避免重复转换）
        try:
            result = client._run_compiler(compiler_input)
        except Exception as exc:
            logger.exception("VRS bridge: 编译器调用失败")
            return {
                "success": False,
                "script_content": "",
                "errors": [f"编译器调用异常: {exc}"],
                "warnings": [],
                "stats": {"operationCount": len(compiler_input.get("operations", [])), "compileTimeMs": 0},
            }

        if result.get("success"):
            return {
                "success": True,
                "script_content": result.get("jsx_code", ""),
                "errors": [],
                "warnings": [],
                "stats": {
                    "operationCount": len(compiler_input.get("operations", [])),
                    "scriptSize": len(result.get("jsx_code", "")),
                    "compileTimeMs": 0,
                },
            }

        # TS 编译器失败时使用降级方案
        logger.warning("VRS bridge: TS 编译器失败，使用降级方案: {}", result.get("error", "unknown"))
        try:
            effects_list = [
                {"matchName": op.get("matchName", ""), "settings": op.get("settings", {})}
                for op in compiler_input.get("operations", [])
                if op.get("op") == "addEffect"
            ]
            keyframes_list = [
                {"propertyPath": op.get("propertyPath", ""), "keyframes": op.get("keyframes", [])}
                for op in compiler_input.get("operations", [])
                if op.get("op") == "setKeyframe"
            ]
            jsx = client._generate_standalone_jsx(effects=effects_list, keyframes=keyframes_list)
            return {
                "success": True,
                "script_content": jsx,
                "errors": [result.get("error", "unknown")],
                "warnings": ["使用降级方案生成 JSX（TS 编译器不可用）"],
                "stats": {
                    "operationCount": len(compiler_input.get("operations", [])),
                    "scriptSize": len(jsx),
                    "compileTimeMs": 0,
                },
            }
        except Exception as exc:
            logger.exception("VRS bridge: 降级方案也失败")
            return {
                "success": False,
                "script_content": "",
                "errors": [f"降级方案异常: {exc}"],
                "warnings": [],
                "stats": {"operationCount": 0, "compileTimeMs": 0},
            }

    def compile_analysis_to_mcp_commands(self, analysis_result: dict) -> list:
        """直接生成 MCP 命令序列（不经过编译器）。

        每条命令格式遵循 mcp-extension/new-tools-inline.ts 中定义的工具签名：
            {tool: "add-effect-with-keyframes", args: {...}}
            {tool: "set-blend-mode", args: {...}}
            {tool: "batch-add-effects", args: {...}}
            {tool: "set-keyframe-easing", args: {...}}

        Args:
            analysis_result: 视频效果分析结果

        Returns:
            MCP 命令列表
        """
        compiler_input = self.convert_analysis_to_compiler_input(analysis_result)
        comp_name = self.default_comp_name
        commands: List[Dict[str, Any]] = []

        # 收集每个图层的效果，便于使用 batch-add-effects
        layer_effects: Dict[int, List[Dict[str, Any]]] = {}
        layer_keyframes: Dict[int, List[Dict[str, Any]]] = {}

        # 建立 layer_ref → index 反向映射
        ref_to_index: Dict[str, int] = {}
        for op in compiler_input["operations"]:
            if op.get("op") == "addLayer":
                ref = op.get("ref", "")
                # 从 ref 中提取 index（如 layer_001 → 1）
                m = re.search(r"(\d+)$", ref)
                if m:
                    ref_to_index[ref] = int(m.group(1))

        for op in compiler_input["operations"]:
            op_type = op.get("op")

            if op_type == "addEffect":
                layer_ref = op.get("layerRef", "layer_001")
                layer_index = ref_to_index.get(layer_ref, 1)
                match_name = op.get("matchName", "")
                settings = op.get("settings", {})

                cmd = {
                    "tool": "add-effect-with-keyframes",
                    "args": {
                        "compName": comp_name,
                        "layerIndex": layer_index,
                        "effectMatchName": match_name,
                        "settings": settings,
                        "keyframes": [],  # 后续填充
                    },
                }
                commands.append(cmd)
                # 记录此效果以关联关键帧
                layer_effects.setdefault(layer_index, []).append({
                    "matchName": match_name,
                    "settings": settings,
                    "cmd_idx": len(commands) - 1,
                })

            elif op_type == "setKeyframe":
                layer_ref = op.get("layerRef", "layer_001")
                layer_index = ref_to_index.get(layer_ref, 1)
                property_path = op.get("propertyPath", "")
                kf_list = op.get("keyframes", [])

                # 转换为 MCP 关键帧格式
                mcp_keyframes = []
                for kf in kf_list:
                    easing_type = "linear"
                    if kf.get("easing"):
                        easing_type = kf["easing"].get("type", "linear")
                        # 映射编译器 easing → MCP easing
                        easing_map_mcp = {
                            "linear": "linear",
                            "ease_in": "easeIn",
                            "ease_out": "easeOut",
                            "ease_in_out": "easeInOut",
                            "bezier": "bezier",
                            "hold": "hold",
                        }
                        easing_type = easing_map_mcp.get(easing_type, "linear")

                    mcp_keyframes.append({
                        "propertyName": property_path,
                        "time": kf.get("time", 0),
                        "value": kf.get("value"),
                        "easingType": easing_type,
                    })

                # 附加到上一个 addEffect 命令的 keyframes 字段（如有效果）
                if layer_index in layer_effects and layer_effects[layer_index]:
                    last_effect = layer_effects[layer_index][-1]
                    cmd_idx = last_effect["cmd_idx"]
                    if cmd_idx < len(commands) and commands[cmd_idx]["tool"] == "add-effect-with-keyframes":
                        commands[cmd_idx]["args"]["keyframes"].extend(mcp_keyframes)
                    else:
                        # 独立的关键帧命令
                        commands.append({
                            "tool": "set-keyframe-easing",
                            "args": {
                                "compName": comp_name,
                                "layerIndex": layer_index,
                                "propertyPath": property_path,
                                "keyframes": mcp_keyframes,
                            },
                        })
                else:
                    # 图层变换属性的关键帧（非效果）
                    commands.append({
                        "tool": "add-effect-with-keyframes",
                        "args": {
                            "compName": comp_name,
                            "layerIndex": layer_index,
                            "effectMatchName": "ADBE Transform",
                            "settings": {},
                            "keyframes": mcp_keyframes,
                        },
                    })

            elif op_type == "setBlendMode":
                layer_ref = op.get("layerRef", "layer_001")
                layer_index = ref_to_index.get(layer_ref, 1)
                commands.append({
                    "tool": "set-blend-mode",
                    "args": {
                        "compName": comp_name,
                        "layerIndex": layer_index,
                        "blendMode": op.get("blendMode", "normal"),
                    },
                })

            elif op_type == "addLayer":
                # 创建图层的命令（MCP 通常有 add-solid / add-adjustment-layer 等专用工具）
                layer_type = op.get("layerType", "solid")
                layer_name = op.get("name", "Layer")
                tool_name = {
                    "solid": "add-solid",
                    "adjustment": "add-adjustment-layer",
                    "null": "add-null",
                    "text": "add-text-layer",
                    "shape": "add-shape-layer",
                }.get(layer_type, "add-solid")
                commands.append({
                    "tool": tool_name,
                    "args": {
                        "compName": comp_name,
                        "name": layer_name,
                        "color": op.get("color", [0, 0, 0]),
                        "width": op.get("width", self.default_width),
                        "height": op.get("height", self.default_height),
                    },
                })

            elif op_type == "createComp":
                commands.append({
                    "tool": "create-comp",
                    "args": {
                        "name": op.get("name", comp_name),
                        "width": op.get("width", self.default_width),
                        "height": op.get("height", self.default_height),
                        "frameRate": op.get("frameRate", self.default_fps),
                        "duration": op.get("duration", self.default_duration),
                    },
                })

        logger.info("VRS bridge: 生成 {} 条 MCP 命令", len(commands))
        return commands

    # ================================================================
    #  内部辅助方法
    # ================================================================

    def _get_compiler_client(self) -> Optional[Any]:
        """懒加载 ae_ts_compiler_client.AETSCompilerClient 实例。"""
        if self._compiler_client is not None:
            return self._compiler_client
        try:
            # 动态导入，避免模块未安装时硬失败
            import importlib
            module = importlib.import_module("ae_ts_compiler_client")
            client_cls = getattr(module, "AETSCompilerClient")
            self._compiler_client = client_cls()
            return self._compiler_client
        except ImportError:
            logger.warning("VRS bridge: ae_ts_compiler_client 模块未找到")
            return None
        except Exception as exc:
            logger.warning("VRS bridge: 初始化编译器客户端失败: {}", exc)
            return None

    def _next_ref(self, prefix: str = "op") -> str:
        """生成下一个操作引用 ID。"""
        self._op_counter += 1
        return f"{prefix}_{self._op_counter:03d}"

    def _lookup_matchname(self, name: str) -> Optional[str]:
        """从名称查找 matchName（支持中英文别名）。"""
        if not name:
            return None
        # 精确匹配
        entry = EFFECT_MATCHNAME_MAP.get(name)
        if entry:
            return entry["matchName"]
        # 大小写不敏感匹配
        for key, entry in EFFECT_MATCHNAME_MAP.items():
            if key.lower() == name.lower():
                return entry["matchName"]
        # 模糊匹配（包含关系）
        for key, entry in EFFECT_MATCHNAME_MAP.items():
            if key.lower() in name.lower() or name.lower() in key.lower():
                return entry["matchName"]
        return None

    def _extract_composition_info(self, analysis: dict) -> Dict[str, Any]:
        """提取合成信息，支持简单格式和 VRS 多阶段格式。"""
        # VRS 多阶段格式：stages.layer_stack.compositions
        stages = analysis.get("stages") or {}
        layer_stack = stages.get("layer_stack") or {}
        comps = layer_stack.get("compositions") or []
        if comps:
            comp = comps[0]
            return {
                "name": comp.get("name", self.default_comp_name),
                "width": int(comp.get("width", self.default_width)),
                "height": int(comp.get("height", self.default_height)),
                "fps": int(comp.get("fps", self.default_fps)),
                "duration": float(analysis.get("basic_info", {}).get("duration", self.default_duration)),
            }

        # 简单格式：basic_info
        basic = analysis.get("basic_info") or {}
        return {
            "name": self.default_comp_name,
            "width": int(basic.get("width", self.default_width)),
            "height": int(basic.get("height", self.default_height)),
            "fps": int(basic.get("fps", self.default_fps)),
            "duration": float(basic.get("duration", self.default_duration)),
        }

    def _extract_layers(self, analysis: dict) -> List[Dict[str, Any]]:
        """提取图层列表。"""
        layers: List[Dict[str, Any]] = []

        # VRS 多阶段格式：stages.layer_stack.layers
        stages = analysis.get("stages") or {}
        layer_stack = stages.get("layer_stack") or {}
        raw_layers = layer_stack.get("layers") or []

        if raw_layers:
            for layer in raw_layers:
                idx = layer.get("index", len(layers) + 1)
                layer_type = self._normalize_layer_type(layer.get("type", "solid"))
                ref = f"layer_{idx:03d}"
                layers.append({
                    "index": idx,
                    "ref": ref,
                    "name": layer.get("name", f"Layer {idx}"),
                    "type": layer_type,
                    "blend_mode": layer.get("blend_mode", "normal"),
                    "opacity": layer.get("opacity", 100),
                    "effects": layer.get("effects", []),
                    "mask": layer.get("mask", "none"),
                })
            return layers

        # ae_parameters.adjustment_layers（简单格式）
        ae_params = analysis.get("ae_parameters") or {}
        for adj in ae_params.get("adjustment_layers", []):
            idx = len(layers) + 1
            layers.append({
                "index": idx,
                "ref": f"layer_{idx:03d}",
                "name": adj.get("name", f"Adjustment {idx}"),
                "type": "adjustment",
                "blend_mode": "normal",
                "opacity": 100,
                "effects": [adj.get("effect", "Lumetri Color")],
            })

        # 如果没有任何图层，创建默认主体层
        if not layers:
            layers.append({
                "index": 1,
                "ref": "layer_001",
                "name": "主体层",
                "type": "footage",
                "blend_mode": "normal",
                "opacity": 100,
                "effects": [],
            })

        return layers

    def _extract_motion(self, analysis: dict) -> Dict[str, Any]:
        """提取运动分析信息。"""
        # 简单格式：motion_analysis
        motion = analysis.get("motion_analysis")
        if motion:
            return motion

        # VRS 多阶段格式：从 consensus 中聚合
        stages = analysis.get("stages") or {}
        visual_analysis = stages.get("visual_analysis") or {}
        frames = visual_analysis.get("frames") or []

        camera_motions: List[str] = []
        for frame in frames:
            consensus = frame.get("consensus") or {}
            cm = consensus.get("camera_movement", "")
            if cm:
                camera_motions.append(cm)

        # 简单启发式：取最常见的相机运动类型
        camera_motion = ""
        if camera_motions:
            # 检测关键词
            joined = " ".join(camera_motions).lower()
            if any(kw in joined for kw in ["zoom", "push", "推近", "缩放进入"]):
                camera_motion = "持续缩放进入"
            elif any(kw in joined for kw in ["pull", "拉远", "缩放退出"]):
                camera_motion = "持续缩放退出"
            elif any(kw in joined for kw in ["pan", "摇移", "横向"]):
                camera_motion = "pan_right"
            elif any(kw in joined for kw in ["rotate", "旋转", "环绕"]):
                camera_motion = "rotate"
            else:
                camera_motion = "固定"

        return {
            "camera_motion": camera_motion,
            "speed_changes": [],
        }

    def _extract_visual_effects(self, analysis: dict) -> List[Dict[str, Any]]:
        """提取视觉效果列表。"""
        # 简单格式：visual_effects.detected_effects
        vfx = analysis.get("visual_effects") or {}
        detected = vfx.get("detected_effects") or []
        if detected:
            return detected

        # 简单格式：ae_parameters.effects
        ae_params = analysis.get("ae_parameters") or {}
        effects = ae_params.get("effects") or []
        result = []
        for eff in effects:
            result.append({
                "name": eff.get("name", "unknown"),
                "ae_effect": eff.get("effect", ""),
                "ae_params": eff.get("params", {}),
                "time": eff.get("time", 0),
            })
        return result

    def _build_color_grading_ops(
        self, analysis: dict, layers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """构建调色操作（Lumetri Color）。"""
        ops: List[Dict[str, Any]] = []

        # 简单格式：color_grading.ae_lumetri_params
        color = analysis.get("color_grading") or {}
        lumetri_params = color.get("ae_lumetri_params")
        if lumetri_params:
            # 创建调整层（如果没有）
            adj_layer_ref = self._find_or_create_adjustment_layer(layers, "调色调整层", ops)
            fx_ref = self._next_ref("fx")
            ops.append({
                "op": "addEffect",
                "ref": fx_ref,
                "layerRef": adj_layer_ref,
                "matchName": "ADBE Lumetri",
                "name": "Lumetri Color",
                "settings": self._sanitize_params(lumetri_params),
                "dependsOn": [adj_layer_ref],
            })

        # VRS 多阶段格式：stages.color_params.nodes
        stages = analysis.get("stages") or {}
        color_params = stages.get("color_params") or {}
        nodes = color_params.get("nodes") or []
        if nodes:
            adj_layer_ref = self._find_or_create_adjustment_layer(layers, "调色调整层", ops)
            fx_ref = self._next_ref("fx")
            # 将 color nodes 转换为 Lumetri 参数
            lumetri_settings: Dict[str, Any] = {}
            for node in nodes:
                tool = node.get("tool", "")
                value = node.get("value", "")
                # 简单映射
                if tool == "Saturation":
                    lumetri_settings["Saturation"] = self._parse_numeric(value, default=0)
                elif tool == "Contrast":
                    lumetri_settings["Contrast"] = self._parse_numeric(value, default=0)
                elif tool == "Temperature":
                    lumetri_settings["Temperature"] = self._parse_numeric(value, default=0)
                elif tool == "Tint":
                    lumetri_settings["Tint"] = self._parse_numeric(value, default=0)
                elif tool == "Exposure":
                    lumetri_settings["Exposure"] = self._parse_numeric(value, default=0)

            if lumetri_settings:
                ops.append({
                    "op": "addEffect",
                    "ref": fx_ref,
                    "layerRef": adj_layer_ref,
                    "matchName": "ADBE Lumetri",
                    "name": "Lumetri Color (from color_params)",
                    "settings": lumetri_settings,
                    "dependsOn": [adj_layer_ref],
                })

        return ops

    def _build_transition_ops(
        self, analysis: dict, layers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """构建转场操作。"""
        ops: List[Dict[str, Any]] = []
        transitions = analysis.get("transitions") or []
        # 转场通常应用在主体图层上
        target_layer_ref = layers[0]["ref"] if layers else "layer_001"

        # 转场关键帧操作委托给 build_keyframe_operations
        kf_ops = self.build_keyframe_operations(transitions, [], {})
        for kf_op in kf_ops:
            # 覆盖 layerRef 为目标图层
            kf_op["layerRef"] = target_layer_ref
            kf_op["ref"] = self._next_ref("kf")
            kf_op["dependsOn"] = [target_layer_ref]
            ops.append(kf_op)

        # 如果转场有显式的 ae_effect，添加为效果
        for tr in transitions:
            if not isinstance(tr, dict):
                continue
            ae_effect = tr.get("ae_effect") or ""
            if not ae_effect:
                continue
            match_name = self._lookup_matchname(ae_effect)
            if match_name:
                fx_ref = self._next_ref("fx")
                ops.append({
                    "op": "addEffect",
                    "ref": fx_ref,
                    "layerRef": target_layer_ref,
                    "matchName": match_name,
                    "name": f"转场_{tr.get('type', 'unknown')}@{tr.get('time_sec', 0)}s",
                    "settings": self._sanitize_params(tr.get("ae_params", {})),
                    "dependsOn": [target_layer_ref],
                })

        return ops

    def _build_speed_change_ops(
        self, motion: dict, layers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """构建速度变化操作（timeRemap 关键帧）。"""
        ops: List[Dict[str, Any]] = []
        speed_changes = motion.get("speed_changes") or []
        target_layer_ref = layers[0]["ref"] if layers else "layer_001"

        kf_ops = self.build_keyframe_operations([], speed_changes, {})
        for kf_op in kf_ops:
            kf_op["layerRef"] = target_layer_ref
            kf_op["ref"] = self._next_ref("kf")
            kf_op["dependsOn"] = [target_layer_ref]
            ops.append(kf_op)

        return ops

    def _build_camera_motion_ops(
        self, motion: dict, layers: List[Dict[str, Any]], comp_info: dict
    ) -> List[Dict[str, Any]]:
        """构建相机运动操作（缩放/位移关键帧）。"""
        ops: List[Dict[str, Any]] = []
        target_layer_ref = layers[0]["ref"] if layers else "layer_001"

        # 委托给 build_keyframe_operations
        # 临时设置 default_duration 以匹配 comp_info
        old_duration = self.default_duration
        self.default_duration = comp_info["duration"]
        try:
            kf_ops = self.build_keyframe_operations([], [], motion)
        finally:
            self.default_duration = old_duration

        for kf_op in kf_ops:
            kf_op["layerRef"] = target_layer_ref
            kf_op["ref"] = self._next_ref("kf")
            kf_op["dependsOn"] = [target_layer_ref]
            ops.append(kf_op)

        return ops

    def _build_plugin_ops_from_visual_analysis(
        self, analysis: dict, layers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从 VRS 多阶段格式的视觉分析中提取插件效果。"""
        ops: List[Dict[str, Any]] = []
        stages = analysis.get("stages") or {}
        visual_analysis = stages.get("visual_analysis") or {}
        frames = visual_analysis.get("frames") or []

        # 收集所有 possible_plugins
        plugins_counter: Dict[str, int] = {}
        for frame in frames:
            consensus = frame.get("consensus") or {}
            for plugin in consensus.get("possible_plugins", []):
                plugins_counter[plugin] = plugins_counter.get(plugin, 0) + 1

        # 按出现次数排序，取 Top N
        sorted_plugins = sorted(plugins_counter.items(), key=lambda x: -x[1])
        target_layer_ref = layers[0]["ref"] if layers else "layer_001"

        # 也尝试从 stages.ae_parameters.effects 解析（如果有结构化数据）
        ae_params_stage = stages.get("ae_parameters") or {}
        raw_effects_str = ae_params_stage.get("raw", "")

        # 解析 ae_parameters.raw（JSON 字符串）中的效果列表
        parsed_effects = self._parse_ae_parameters_raw(raw_effects_str)

        if parsed_effects:
            # 优先使用结构化的 ae_parameters.raw 数据
            for eff in parsed_effects:
                match_name = eff.get("matchname") or eff.get("matchName")
                if not match_name or "N/A" in match_name:
                    # 尝试从效果名查表
                    match_name = self._lookup_matchname(eff.get("name", "") or eff.get("ae_effect", ""))
                if not match_name:
                    continue

                fx_ref = self._next_ref("fx")
                key_params = eff.get("key_params", {})
                # 过滤非数值参数
                settings = self._sanitize_params(key_params)

                op: Dict[str, Any] = {
                    "op": "addEffect",
                    "ref": fx_ref,
                    "layerRef": target_layer_ref,
                    "matchName": match_name,
                    "name": eff.get("name", match_name),
                    "dependsOn": [target_layer_ref],
                }
                if settings:
                    op["settings"] = settings
                ops.append(op)
        else:
            # 从 possible_plugins 中提取（去重，按出现频率）
            seen_matchnames: set = set()
            for plugin_name, count in sorted_plugins[:15]:  # 取前 15 个最常见的
                match_name = self._lookup_matchname(plugin_name)
                if match_name and match_name not in seen_matchnames:
                    seen_matchnames.add(match_name)
                    fx_ref = self._next_ref("fx")
                    ops.append({
                        "op": "addEffect",
                        "ref": fx_ref,
                        "layerRef": target_layer_ref,
                        "matchName": match_name,
                        "name": plugin_name,
                        "settings": {},
                        "dependsOn": [target_layer_ref],
                    })

        return ops

    def _parse_ae_parameters_raw(self, raw_str: str) -> List[Dict[str, Any]]:
        """解析 stages.ae_parameters.raw JSON 字符串。

        raw 字段可能包含 ```json ... ``` 包裹的 JSON 字符串。
        """
        if not raw_str:
            return []

        # 去除 markdown 代码块标记
        cleaned = raw_str.strip()
        if cleaned.startswith("```"):
            # 去除首行 ```json 或 ```
            lines = cleaned.split("\n")
            if len(lines) > 2:
                cleaned = "\n".join(lines[1:-1])

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                effects = data.get("effects", [])
                if isinstance(effects, list):
                    return effects
        except json.JSONDecodeError:
            # 尝试从字符串中提取 JSON
            try:
                match = re.search(r"\{[\s\S]*\}", cleaned)
                if match:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict):
                        return data.get("effects", [])
            except (json.JSONDecodeError, AttributeError):
                pass

        return []

    def _build_keyframe_op(
        self,
        layer_ref: str,
        fx_ref: Optional[str],
        keyframes: List[Dict[str, Any]],
        default_property: str,
    ) -> Optional[Dict[str, Any]]:
        """构建单个 setKeyframe 操作。"""
        if not keyframes:
            return None

        normalized_kfs: List[Dict[str, Any]] = []
        for kf in keyframes:
            if not isinstance(kf, dict):
                continue
            kf_time = kf.get("time", 0)
            kf_value = kf.get("value")
            if kf_value is None:
                continue

            easing = kf.get("easing")
            easing_obj: Optional[Dict[str, Any]] = None
            if easing:
                # easing 可能是字符串或 dict
                if isinstance(easing, str):
                    easing_type = EASING_TYPE_MAP.get(easing, "linear")
                    easing_obj = {"type": easing_type}
                elif isinstance(easing, dict):
                    raw_type = easing.get("type", "linear")
                    easing_type = EASING_TYPE_MAP.get(raw_type, "linear")
                    easing_obj = {
                        "type": easing_type,
                        "inSpeed": easing.get("inSpeed", easing.get("in_speed", 0)),
                        "inInfluence": easing.get("inInfluence", easing.get("in_influence", 33)),
                        "outSpeed": easing.get("outSpeed", easing.get("out_speed", 0)),
                        "outInfluence": easing.get("outInfluence", easing.get("out_influence", 33)),
                    }

            kf_entry: Dict[str, Any] = {
                "time": float(kf_time),
                "value": kf_value,
            }
            if easing_obj:
                kf_entry["easing"] = easing_obj
            normalized_kfs.append(kf_entry)

        if not normalized_kfs:
            return None

        op: Dict[str, Any] = {
            "op": "setKeyframe",
            "ref": self._next_ref("kf"),
            "layerRef": layer_ref,
            "propertyPath": default_property,
            "keyframes": normalized_kfs,
            "dependsOn": [layer_ref],
        }
        if fx_ref:
            op["dependsOn"].append(fx_ref)
        return op

    def _find_or_create_adjustment_layer(
        self, layers: List[Dict[str, Any]], name: str, ops: List[Dict[str, Any]]
    ) -> str:
        """查找或创建调整层。"""
        for layer in layers:
            if layer.get("type") == "adjustment" and name in layer.get("name", ""):
                return layer["ref"]

        # 创建新调整层
        idx = max([l["index"] for l in layers], default=0) + 1
        ref = f"layer_{idx:03d}"
        new_layer = {
            "index": idx,
            "ref": ref,
            "name": name,
            "type": "adjustment",
            "blend_mode": "normal",
            "opacity": 100,
            "effects": [],
        }
        layers.append(new_layer)
        self._layer_ref_map[idx] = ref

        ops.append({
            "op": "addLayer",
            "ref": ref,
            "compRef": "main_comp",
            "layerType": "adjustment",
            "name": name,
        })
        return ref

    def _resolve_layer_ref(
        self, layer_index: int, layers: List[Dict[str, Any]]
    ) -> str:
        """解析图层引用 ID。"""
        # 优先从映射表查找
        if layer_index in self._layer_ref_map:
            return self._layer_ref_map[layer_index]
        # 从 layers 列表查找
        for layer in layers:
            if layer["index"] == layer_index:
                return layer["ref"]
        # 默认回退
        ref = f"layer_{layer_index:03d}"
        self._layer_ref_map[layer_index] = ref
        return ref

    def _guess_default_property(self, match_name: str) -> str:
        """根据 matchName 猜测默认动画属性。"""
        if "Gaussian Blur" in match_name or "Box Blur" in match_name:
            return "Effects.Blur.Blurriness"
        if "Directional Blur" in match_name:
            return "Effects.Blur.Blur Length"
        if "Glow" in match_name:
            return "Effects.Glow.Glow Intensity"
        if "Lumetri" in match_name:
            return "Effects.Lumetri Color.Saturation"
        if "Exposure" in match_name:
            return "Effects.Exposure.Exposure"
        return "Effects.Effect.Property"

    def _normalize_layer_type(self, layer_type: str) -> str:
        """规范化图层类型。"""
        mapping = {
            "adjustment": "adjustment",
            "solid": "solid",
            "footage": "footage",
            "shape": "shape",
            "text": "text",
            "null": "null",
            "camera": "camera",
            "light": "light",
        }
        return mapping.get(layer_type.lower(), "solid")

    def _normalize_blend_mode(self, mode: str) -> str:
        """规范化混合模式名称。"""
        mapping = {
            "normal": "normal",
            "add": "add",
            "screen": "screen",
            "multiply": "multiply",
            "overlay": "overlay",
            "soft_light": "softLight",
            "softlight": "softLight",
            "hard_light": "hardLight",
            "hardlight": "hardLight",
            "lighten": "lighten",
            "darken": "darken",
            "difference": "difference",
            "exclusion": "exclusion",
            "color_dodge": "colorDodge",
            "colordodge": "colorDodge",
            "color_burn": "colorBurn",
            "colorburn": "colorBurn",
            "hue": "hue",
            "saturation": "saturation",
            "color": "color",
            "luminosity": "luminosity",
        }
        return mapping.get(mode.lower(), "normal")

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """过滤参数，只保留原子值（number/string/bool/array of numbers）。"""
        if not isinstance(params, dict):
            return {}
        clean: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, bool):
                clean[k] = v
            elif isinstance(v, (int, float)):
                clean[k] = v
            elif isinstance(v, str):
                # 尝试解析数值字符串
                parsed = self._parse_numeric(v)
                if parsed is not None:
                    clean[k] = parsed
                else:
                    # 保留字符串（可能是下拉选项值如 "Full"）
                    clean[k] = v
            elif isinstance(v, (list, tuple)):
                # 数组（如颜色 [R, G, B]）
                arr = [x for x in v if isinstance(x, (int, float))]
                if arr:
                    clean[k] = arr
        return clean

    def _parse_numeric(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        """尝试解析数值。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # 提取第一个数字
            match = re.search(r"-?\d+\.?\d*", value)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    return default
        return default

    def _sort_operations(self, operations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 layer_index → time → dependency 排序操作。

        排序规则：
            1. createComp 始终第一个
            2. addLayer 按 index 升序
            3. setBlendMode 紧跟在对应 addLayer 之后
            4. 其他操作按 layer_index → time → ref 序排序
        """
        if not operations:
            return operations

        def sort_key(op: Dict[str, Any]) -> Tuple[int, int, float, str]:
            op_type = op.get("op", "")
            ref = op.get("ref", "")
            layer_ref = op.get("layerRef", "")

            # createComp 优先级 0
            if op_type == "createComp":
                return (0, 0, 0.0, "")
            # addLayer 优先级 1，按 index 排序
            if op_type == "addLayer":
                idx = self._extract_index_from_ref(ref)
                return (1, idx, 0.0, ref)
            # setBlendMode 优先级 2
            if op_type == "setBlendMode":
                idx = self._extract_index_from_ref(layer_ref)
                return (2, idx, 0.0, ref)
            # 其他操作优先级 3，按 layer_index → time 排序
            idx = self._extract_index_from_ref(layer_ref)
            # 尝试从 settings 或 keyframes 提取 time
            t = 0.0
            if op.get("keyframes"):
                kfs = op["keyframes"]
                if isinstance(kfs, list) and kfs:
                    t = float(kfs[0].get("time", 0))
            return (3, idx, t, ref)

        return sorted(operations, key=sort_key)

    def _extract_index_from_ref(self, ref: str) -> int:
        """从引用 ID 中提取索引数字。"""
        if not ref:
            return 0
        match = re.search(r"(\d+)$", ref)
        return int(match.group(1)) if match else 0


# =====================================================================
#  便捷函数
# =====================================================================


def convert_analysis_file(
    analysis_path: str | Path,
    output_path: Optional[str | Path] = None,
    bridge: Optional[VRCompilerBridge] = None,
) -> Dict[str, Any]:
    """便捷函数：从文件加载分析结果并转换为 CompilerInput。

    Args:
        analysis_path: 分析结果 JSON 文件路径
        output_path: 可选，将 CompilerInput 写入此路径
        bridge: 可选的 VRCompilerBridge 实例

    Returns:
        CompilerInput 字典
    """
    analysis_path = Path(analysis_path)
    if not analysis_path.is_file():
        raise FileNotFoundError(f"分析结果文件不存在: {analysis_path}")

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    b = bridge or VRCompilerBridge()
    compiler_input = b.convert_analysis_to_compiler_input(analysis)

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(compiler_input, f, ensure_ascii=False, indent=2)
        logger.info("VRS bridge: CompilerInput 已写入 {}", output_path)

    return compiler_input


def get_effect_map_stats() -> Dict[str, Any]:
    """获取效果映射表统计信息。"""
    by_category: Dict[str, int] = {}
    unique_matchnames: set = set()
    for entry in EFFECT_MATCHNAME_MAP.values():
        cat = entry.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1
        unique_matchnames.add(entry["matchName"])
    return {
        "total_entries": len(EFFECT_MATCHNAME_MAP),
        "unique_matchnames": len(unique_matchnames),
        "by_category": by_category,
    }


# =====================================================================
#  自测入口
# =====================================================================

if __name__ == "__main__":
    import sys

    # 配置 loguru
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{level: <8}</level> | {message}")

    print("=" * 72)
    print("VRS Compiler Bridge - 自测")
    print("=" * 72)

    # 1. 输出映射表统计
    stats = get_effect_map_stats()
    print(f"\n[1] 效果映射表统计:")
    print(f"    总条目数: {stats['total_entries']}")
    print(f"    唯一 matchName 数: {stats['unique_matchnames']}")
    print(f"    分类分布: {stats['by_category']}")

    # 2. 加载 saitama_analysis.json
    project_root = Path(__file__).parent
    analysis_file = project_root / "output" / "saitama_analysis.json"
    if not analysis_file.is_file():
        print(f"\n[ERROR] 测试数据不存在: {analysis_file}")
        sys.exit(1)

    print(f"\n[2] 加载分析结果: {analysis_file}")
    with open(analysis_file, "r", encoding="utf-8") as f:
        analysis = json.load(f)
    print(f"    视频路径: {analysis.get('video_path', 'unknown')}")
    print(f"    提供商: {analysis.get('providers', [])}")

    # 3. 转换为 CompilerInput
    print(f"\n[3] 转换为 CompilerInput...")
    bridge = VRCompilerBridge()
    compiler_input = bridge.convert_analysis_to_compiler_input(analysis)

    op_types: Dict[str, int] = {}
    for op in compiler_input["operations"]:
        t = op.get("op", "unknown")
        op_types[t] = op_types.get(t, 0) + 1

    print(f"    操作总数: {len(compiler_input['operations'])}")
    print(f"    操作类型分布: {op_types}")

    # 4. 保存 CompilerInput 到中间文件
    compiler_input_file = project_root / "output" / "vrs_compiler_input.json"
    with open(compiler_input_file, "w", encoding="utf-8") as f:
        json.dump(compiler_input, f, ensure_ascii=False, indent=2)
    print(f"    CompilerInput 已保存: {compiler_input_file}")

    # 5. 调用编译器生成 JSX
    print(f"\n[4] 调用编译器生成 ExtendScript...")
    compile_result = bridge.compile_to_script(compiler_input)

    print(f"    编译成功: {compile_result['success']}")
    print(f"    脚本大小: {compile_result['stats'].get('scriptSize', 0)} 字符")
    if compile_result["errors"]:
        print(f"    错误: {compile_result['errors'][:3]}")  # 只显示前3条
    if compile_result["warnings"]:
        print(f"    警告: {compile_result['warnings'][:3]}")

    # 6. 写入输出 JSX 文件
    output_jsx = project_root / "output" / "vrs_test_output.jsx"
    with open(output_jsx, "w", encoding="utf-8") as f:
        f.write(compile_result.get("script_content", ""))
    print(f"    JSX 脚本已保存: {output_jsx}")

    # 7. 生成 MCP 命令序列
    print(f"\n[5] 生成 MCP 命令序列...")
    mcp_commands = bridge.compile_analysis_to_mcp_commands(analysis)
    print(f"    MCP 命令数: {len(mcp_commands)}")

    cmd_types: Dict[str, int] = {}
    for cmd in mcp_commands:
        t = cmd.get("tool", "unknown")
        cmd_types[t] = cmd_types.get(t, 0) + 1
    print(f"    命令类型分布: {cmd_types}")

    # 保存 MCP 命令
    mcp_file = project_root / "output" / "vrs_mcp_commands.json"
    with open(mcp_file, "w", encoding="utf-8") as f:
        json.dump(mcp_commands, f, ensure_ascii=False, indent=2)
    print(f"    MCP 命令已保存: {mcp_file}")

    # ================================================================
    # [6] 闪白/闪黑转场专项测试（使用 vrs_demo/01_cv_analysis.json）
    # 验证 MATCHNAME_MAP 扩展后，闪白/闪黑不再被跳过
    # ================================================================
    print(f"\n[6] 闪白/闪黑转场专项测试...")
    cv_analysis_file = project_root / "output" / "vrs_demo" / "01_cv_analysis.json"
    if not cv_analysis_file.is_file():
        print(f"    [SKIP] 测试数据不存在: {cv_analysis_file}")
    else:
        with open(cv_analysis_file, "r", encoding="utf-8") as f:
            cv_analysis = json.load(f)

        # 统计原始 detected_effects 中的闪白/闪黑数量
        detected = (cv_analysis.get("visual_effects") or {}).get("detected_effects") or []
        flash_white_count = sum(
            1 for e in detected
            if isinstance(e, dict) and (e.get("name") == "闪白" or e.get("name") == "闪白")
            and (e.get("ae_params") or {}).get("value", 0) > 0
        )
        flash_black_count = sum(
            1 for e in detected
            if isinstance(e, dict) and (e.get("name") == "闪黑"
            and (e.get("ae_params") or {}).get("value", 0) < 0)
        )
        flash_total = sum(
            1 for e in detected
            if isinstance(e, dict) and e.get("type") == "flash"
        )
        print(f"    原始 detected_effects 总数: {len(detected)}")
        print(f"    其中 flash 类型: {flash_total}")

        # 转换为 CompilerInput
        cv_bridge = VRCompilerBridge()
        cv_compiler_input = cv_bridge.convert_analysis_to_compiler_input(cv_analysis)

        # 统计操作类型分布
        cv_op_types: Dict[str, int] = {}
        for op in cv_compiler_input["operations"]:
            t = op.get("op", "unknown")
            cv_op_types[t] = cv_op_types.get(t, 0) + 1
        print(f"    操作总数: {len(cv_compiler_input['operations'])}")
        print(f"    操作类型分布: {cv_op_types}")

        # 统计闪白/闪黑生成的固态层数量
        solid_layers = [
            op for op in cv_compiler_input["operations"]
            if op.get("op") == "addLayer"
            and op.get("layerType") == "solid"
            and ("闪白" in op.get("name", "") or "闪黑" in op.get("name", ""))
        ]
        flash_white_solids = [op for op in solid_layers if "闪白" in op.get("name", "")]
        flash_black_solids = [op for op in solid_layers if "闪黑" in op.get("name", "")]
        print(f"    闪白固态层数: {len(flash_white_solids)}")
        print(f"    闪黑固态层数: {len(flash_black_solids)}")

        # 验证：闪白+闪黑固态层数应等于原始 flash 总数（不再被跳过）
        if flash_total > 0:
            if len(solid_layers) == flash_total:
                print(f"    [PASS] 闪白/闪黑全部生成操作 ({len(solid_layers)}/{flash_total})")
            else:
                print(f"    [WARN] 闪白/闪黑操作数与原始数不符: "
                      f"{len(solid_layers)}/{flash_total}")
        else:
            print(f"    [SKIP] 原始数据无 flash 效果")

        # 打印前 20 个操作预览
        print(f"\n    前 20 个操作预览:")
        for i, op in enumerate(cv_compiler_input["operations"][:20]):
            op_type = op.get("op", "?")
            ref = op.get("ref", "")
            name = op.get("name", op.get("matchName", op.get("propertyPath", "")))
            extra = ""
            if op_type == "addLayer":
                extra = f" type={op.get('layerType', '?')} name={op.get('name', '')}"
                if op.get("startTime") is not None:
                    extra += f" @ {op.get('startTime')}s"
            elif op_type == "setBlendMode":
                extra = f" layer={op.get('layerRef', '?')} mode={op.get('blendMode', '?')}"
            elif op_type == "setKeyframe":
                kfs = op.get("keyframes", [])
                extra = f" prop={op.get('propertyPath', '?')} kfs={len(kfs)}"
                if kfs:
                    extra += f" t0={kfs[0].get('time', '?')}"
            elif op_type == "addEffect":
                extra = f" layer={op.get('layerRef', '?')} match={op.get('matchName', '?')}"
            print(f"      [{i+1:02d}] {op_type:14s} ref={ref:12s}{extra} name={name}")

        # 保存转换结果
        cv_output_file = project_root / "output" / "vrs_demo" / "06_transition_test_output.json"
        with open(cv_output_file, "w", encoding="utf-8") as f:
            json.dump(cv_compiler_input, f, ensure_ascii=False, indent=2)
        print(f"\n    转换结果已保存: {cv_output_file}")

    print(f"\n{'=' * 72}")
    print("VRS Compiler Bridge 自测完成")
    print(f"{'=' * 72}")
