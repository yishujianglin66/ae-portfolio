"""
GL-Transition Renderer — GPU加速转场渲染引擎
==============================================
基于 gl-transitions (https://github.com/gl-transitions/gl-transitions) 开源项目，
使用 OpenGL Shader 实现 70+ GPU 加速转场效果，替代 CPU 渲染方案。

核心功能:
- 74种 GPU 转场效果（涵盖擦除/滑动/缩放/旋转/故障/溶解等）
- 自动降级到 CPU MoviePy 模式（无 GPU 时）
- 与 PremiereTransitionSystem 双向映射
- 支持自定义 Shader 扩展

依赖:
    pip install moderngl numpy pillow moviepy
    git clone https://github.com/gl-transitions/gl-transitions (shader源)

用法:
    renderer = GLTransitionRenderer()
    renderer.render_transition("Mosaic", frame_a, frame_b, progress=0.5)
"""

from __future__ import annotations

import json
import os
import sys
import time
import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent.parent))


# ================================================================
#  GL 转场类型 → gl-transitions 名称映射
# ================================================================
GL_TRANSITION_TABLE: Dict[str, Dict[str, Any]] = {
    # ================================================================
    #  125 GLSL shader 完整映射表 (v2 — 基于 gl-transitions 仓库)
    #  70 个 shader 包含参数化的 uniform 默认值
    # ================================================================
    # --- 溶解/淡入淡出 [dissolve] ---
    "crossfade":         {"gl_name": "fade",                 "category": "dissolve",    "gpu_intensive": False},
    "fade":              {"gl_name": "fade",                 "category": "dissolve",    "gpu_intensive": False},
    "fadecolor":         {"gl_name": "fadecolor",            "category": "dissolve",    "gpu_intensive": True,  "params": [["float","colorPhase","0.4"]]},
    "fadegrayscale":     {"gl_name": "fadegrayscale",        "category": "dissolve",    "gpu_intensive": True,  "params": [["float","intensity","0.3"]]},
    "dissolve":          {"gl_name": "dissolve",             "category": "dissolve",    "gpu_intensive": False, "params": [["float","uLineWidth","0.1"],["float","uPow","5.0"],["float","uIntensity","1.0"]]},
    "directional_warp":  {"gl_name": "directionalwarp",      "category": "dissolve",    "gpu_intensive": True,  "params": [["float","smoothness","0.1"]]},
    "burn":              {"gl_name": "burn",                 "category": "dissolve",    "gpu_intensive": True},

    # --- 擦除/扫过 [wipe] ---
    "wipe_left":         {"gl_name": "wipeLeft",             "category": "wipe",        "gpu_intensive": False},
    "wipe_right":        {"gl_name": "wipeRight",            "category": "wipe",        "gpu_intensive": False},
    "wipe_up":           {"gl_name": "wipeUp",               "category": "wipe",        "gpu_intensive": False},
    "wipe_down":         {"gl_name": "wipeDown",             "category": "wipe",        "gpu_intensive": False},
    "wind":              {"gl_name": "wind",                 "category": "wipe",        "gpu_intensive": False, "params": [["float","size","0.2"]]},
    "radial":            {"gl_name": "Radial",               "category": "wipe",        "gpu_intensive": True,  "params": [["float","smoothness","1.0"]]},
    "linear_blur":       {"gl_name": "LinearBlur",           "category": "wipe",        "gpu_intensive": True,  "params": [["float","intensity","0.1"]]},
    "water_drop":        {"gl_name": "WaterDrop",            "category": "wipe",        "gpu_intensive": True,  "params": [["float","amplitude","30"],["float","speed","30"]]},
    "push":              {"gl_name": "swap",                 "category": "slide",       "gpu_intensive": False, "params": [["float","reflection","0.4"],["float","perspective","0.2"],["float","depth","3.0"]]},
    "swap":              {"gl_name": "swap",                 "category": "slide",       "gpu_intensive": False, "params": [["float","reflection","0.4"],["float","perspective","0.2"],["float","depth","3.0"]]},
    "directionalwipe":   {"gl_name": "directionalwipe",      "category": "wipe",        "gpu_intensive": True,  "params": [["float","smoothness","0.5"]]},
    "split_slide_h_in":  {"gl_name": "splitSlideInHorizontal",    "category": "slide", "gpu_intensive": True},
    "split_slide_h_out": {"gl_name": "splitSlideOutHorizontal",   "category": "slide", "gpu_intensive": True},
    "split_slide_h_inout":{"gl_name": "splitSlideInOutHorizontal","category": "slide", "gpu_intensive": True},
    "split_slide_v_in":  {"gl_name": "splitSlideInVertical",      "category": "slide", "gpu_intensive": True},
    "split_slide_v_out": {"gl_name": "splitSlideOutVertical",     "category": "slide", "gpu_intensive": True},
    "split_slide_v_inout":{"gl_name": "splitSlideInOutVertical",  "category": "slide", "gpu_intensive": True},
    "leftright":         {"gl_name": "LeftRight",            "category": "slide",       "gpu_intensive": True},
    "topbottom":         {"gl_name": "TopBottom",            "category": "slide",       "gpu_intensive": True},
    "slides":            {"gl_name": "Slides",               "category": "slide",       "gpu_intensive": True,  "params": [["int","type","0"]]},
    "x_axis_translation":{"gl_name": "x_axis_translation",   "category": "slide",       "gpu_intensive": True},

    # --- 缩放 [zoom] ---
    "directional":       {"gl_name": "Directional",          "category": "zoom",        "gpu_intensive": True},
    "directional_scaled":{"gl_name": "DirectionalScaled",    "category": "zoom",        "gpu_intensive": True,  "params": [["float","scale",".7"]]},
    "crosszoom":         {"gl_name": "CrossZoom",            "category": "zoom",        "gpu_intensive": True,  "params": [["float","strength","0.4"]]},
    "dreamyzoom":        {"gl_name": "DreamyZoom",           "category": "zoom",        "gpu_intensive": True,  "params": [["float","rotation","6"],["float","scale","1.2"]]},
    "simplezoom":        {"gl_name": "SimpleZoom",           "category": "zoom",        "gpu_intensive": True,  "params": [["float","zoom_quickness","0.8"]]},
    "simplezoomout":     {"gl_name": "SimpleZoomOut",        "category": "zoom",        "gpu_intensive": True,  "params": [["float","zoom_quickness","0.8"]]},
    "zoom_left_wipe":    {"gl_name": "ZoomLeftWipe",         "category": "zoom",        "gpu_intensive": True,  "params": [["float","zoom_quickness","0.8"]]},
    "zoom_right_wipe":   {"gl_name": "ZoomRigthWipe",        "category": "zoom",        "gpu_intensive": True,  "params": [["float","zoom_quickness","0.8"]]},
    "zoominout":         {"gl_name": "zoomInOut",            "category": "zoom",        "gpu_intensive": True},

    # --- 旋转/翻转 [rotate] ---
    "cube":              {"gl_name": "cube",                 "category": "rotate",      "gpu_intensive": True,  "params": [["float","persp","0.7"],["float","unzoom","0.3"],["float","reflection","0.4"],["float","floating","3.0"]]},
    "bookflip":          {"gl_name": "BookFlip",             "category": "rotate",      "gpu_intensive": True},
    "gridflip":          {"gl_name": "GridFlip",             "category": "rotate",      "gpu_intensive": True,  "params": [["float","pause","0.1"],["float","dividerWidth","0.05"],["float","randomness","0.1"]]},
    "simpleflip":        {"gl_name": "SimpleFlip",           "category": "rotate",      "gpu_intensive": True},
    "revolve_left":      {"gl_name": "Revolve_Left",         "category": "rotate",      "gpu_intensive": True,  "params": [["float","maxRotation","1.95"],["float","peakZoom","2.22"],["float","swirl","2.85"],["float","barrel","0.38"],["float","motionBlur","1.0"],["float","switchStart","0.30"],["float","switchEnd","0.50"],["float","shadow","0.16"]]},
    "rotatetransition":  {"gl_name": "rotateTransition",     "category": "rotate",      "gpu_intensive": True},
    "rotate_scale_fade": {"gl_name": "rotate_scale_fade",    "category": "rotate",      "gpu_intensive": True,  "params": [["float","rotations","1"],["float","scale","8"]]},
    "rotatescalevanish": {"gl_name": "RotateScaleVanish",    "category": "rotate",      "gpu_intensive": True},

    # --- 变形/扭曲 [distort] ---
    "swirl":             {"gl_name": "Swirl",                "category": "distort",     "gpu_intensive": True},
    "squeeze":           {"gl_name": "squeeze",              "category": "distort",     "gpu_intensive": True,  "params": [["float","colorSeparation","0.04"]]},
    "ripple":            {"gl_name": "ripple",               "category": "distort",     "gpu_intensive": True,  "params": [["float","amplitude","100.0"],["float","speed","50.0"]]},
    "morph":             {"gl_name": "morph",                "category": "distort",     "gpu_intensive": True,  "params": [["float","strength","0.1"]]},
    "circleopen":        {"gl_name": "circleopen",           "category": "distort",     "gpu_intensive": False, "params": [["float","smoothness","0.3"]]},
    "circle_crop":       {"gl_name": "CircleCrop",           "category": "distort",     "gpu_intensive": True},
    "bowtie_h_pure":     {"gl_name": "BowTieHorizontal",     "category": "distort",     "gpu_intensive": True},
    "bowtie_v_pure":     {"gl_name": "BowTieVertical",       "category": "distort",     "gpu_intensive": True},
    "bowtie_with_param": {"gl_name": "BowTieWithParameter",  "category": "distort",     "gpu_intensive": True,  "params": [["float","adjust","0.5"]]},
    "horizontal_close":  {"gl_name": "HorizontalClose",      "category": "distort",     "gpu_intensive": True},
    "horizontal_open":   {"gl_name": "HorizontalOpen",       "category": "distort",     "gpu_intensive": True},
    "vertical_close":    {"gl_name": "VerticalClose",        "category": "distort",     "gpu_intensive": True},
    "vertical_open":     {"gl_name": "VerticalOpen",         "category": "distort",     "gpu_intensive": True},
    "rect_crop":        {"gl_name": "RectangleCrop",         "category": "distort",     "gpu_intensive": True},
    "rectangle":        {"gl_name": "Rectangle",             "category": "distort",     "gpu_intensive": True},
    "windowblinds":     {"gl_name": "windowblinds",          "category": "distort",     "gpu_intensive": True},
    "fold":             {"gl_name": "Fold",                  "category": "distort",     "gpu_intensive": True},

    # --- 像素/故障 [glitch] ---
    "glitch_memories":   {"gl_name": "GlitchMemories",       "category": "glitch",      "gpu_intensive": True},
    "glitch_displace":   {"gl_name": "GlitchDisplace",       "category": "glitch",      "gpu_intensive": True},
    "glitch":            {"gl_name": "GlitchMemories",       "category": "glitch",      "gpu_intensive": True},
    "pixelize":          {"gl_name": "pixelize",             "category": "glitch",      "gpu_intensive": True,  "params": [["int","steps","50"]]},
    "color_phase":       {"gl_name": "colorphase",           "category": "glitch",      "gpu_intensive": True},
    "mosaic":            {"gl_name": "Mosaic",               "category": "glitch",      "gpu_intensive": True,  "params": [["int","endx","2"]]},
    "advanced_mosaic":   {"gl_name": "AdvancedMosaic",       "category": "glitch",      "gpu_intensive": True,  "params": [["float","pixelSize","50.0"]]},
    "datamosh_glitch":   {"gl_name": "StripDatamoshGlitch",  "category": "glitch",      "gpu_intensive": True,  "params": [["float","strength","1.0"],["float","horizontalBars","42.0"],["float","verticalSlits","18.0"],["float","tear","0.18"],["float","chroma","0.032"],["float","residue","0.62"],["float","noiseAmount","0.16"],["float","scanAmount","0.13"],["float","flashAmount","0.20"]]},
    "tv_static":         {"gl_name": "TVStatic",             "category": "glitch",      "gpu_intensive": True,  "params": [["float","offset","0.05"]]},
    "static_wipe":       {"gl_name": "static_wipe",          "category": "glitch",      "gpu_intensive": True,  "params": [["float","u_max_static_span","0.5"]]},
    "old_tv_lost_signal":{"gl_name": "old_tv_lost_signal",   "category": "glitch",      "gpu_intensive": True},
    "parametric_glitch": {"gl_name": "parametric_glitch",    "category": "glitch",      "gpu_intensive": True,  "params": [["float","ampx","1.0"],["float","ampy","1.0"]]},
    "drop_zone_flicker": {"gl_name": "Drop_Zone_Flicker",    "category": "glitch",      "gpu_intensive": True,  "params": [["float","frameRate","24.0"],["float","rgbOffset","0.014"],["float","blockAmount","0.72"],["float","ghostAmount","0.62"],["float","redCyan","0.58"],["float","scanline","0.075"]]},
    "hsvfade":           {"gl_name": "HSVfade",              "category": "glitch",      "gpu_intensive": True},

    # --- 几何类 [geometry] ---
    "doorway":           {"gl_name": "doorway",              "category": "geometry",    "gpu_intensive": False, "params": [["float","reflection","0.4"],["float","perspective","0.4"],["float","depth","3"]]},
    "windowslice":       {"gl_name": "windowslice",          "category": "geometry",    "gpu_intensive": False, "params": [["float","count","10.0"],["float","smoothness","0.5"]]},
    "crosshatch":        {"gl_name": "crosshatch",           "category": "geometry",    "gpu_intensive": False, "params": [["float","threshold","3.0"],["float","fadeEdge","0.1"]]},
    "hexagonalize":      {"gl_name": "hexagonalize",         "category": "geometry",    "gpu_intensive": True,  "params": [["int","steps","50"],["float","horizontalHexagons","20"]]},
    "polka_dots":        {"gl_name": "PolkaDotsCurtain",     "category": "geometry",    "gpu_intensive": True,  "params": [["float","dots","20.0"]]},
    "kaleidoscope":      {"gl_name": "kaleidoscope",         "category": "geometry",    "gpu_intensive": False, "params": [["float","speed","1.0"],["float","angle","1.0"],["float","power","1.5"]]},
    "box":               {"gl_name": "Box",                  "category": "geometry",    "gpu_intensive": True,  "params": [["int","rectIn","1"],["int","location","0"]]},
    "block_dissolve":    {"gl_name": "BlockDissolve",        "category": "geometry",    "gpu_intensive": True,  "params": [["float","blocksize","0.02"]]},
    "chessboard":        {"gl_name": "chessboard",           "category": "geometry",    "gpu_intensive": True,  "params": [["float","grid_num","10.0"]]},
    "puzzle_right":      {"gl_name": "PuzzleRight",          "category": "geometry",    "gpu_intensive": True,  "params": [["float","pause","0.1"],["float","dividerWidth","0.005"]]},
    "starwipe":          {"gl_name": "StarWipe",             "category": "geometry",    "gpu_intensive": True,  "params": [["float","border_thickness","0.01"],["float","star_rotation","0.75"]]},

    # --- 动态类 [dynamic] ---
    "angular":           {"gl_name": "angular",              "category": "dynamic",     "gpu_intensive": False, "params": [["float","startingAngle","90"]]},
    "flyeye":            {"gl_name": "flyeye",               "category": "dynamic",     "gpu_intensive": False, "params": [["float","size","0.04"],["float","zoom","50.0"],["float","colorSeparation","0.3"]]},
    "luma":              {"gl_name": "luma",                 "category": "dynamic",     "gpu_intensive": False},
    "luminance_melt":    {"gl_name": "luminance_melt",       "category": "dynamic",     "gpu_intensive": False, "params": [["bool","direction","1"],["float","l_threshold","0.8"]]},
    "randomsquares":     {"gl_name": "randomsquares",        "category": "dynamic",     "gpu_intensive": False, "params": [["float","smoothness","0.5"]]},
    "circle":            {"gl_name": "circle",               "category": "dynamic",     "gpu_intensive": True},
    "stereo_viewer":     {"gl_name": "StereoViewer",         "category": "dynamic",     "gpu_intensive": True,  "params": [["float","zoom","0.88"],["float","corner_radius","0.22"]]},
    "scale_in":          {"gl_name": "scale-in",             "category": "dynamic",     "gpu_intensive": True},
    "overexposure":      {"gl_name": "Overexposure",         "category": "dynamic",     "gpu_intensive": True,  "params": [["float","strength","0.6"]]},
    "defocusblur":       {"gl_name": "DefocusBlur",          "category": "dynamic",     "gpu_intensive": True,  "params": [["float","blurSize","0.02"]]},
    "staticfade":        {"gl_name": "StaticFade",           "category": "dynamic",     "gpu_intensive": True,  "params": [["float","n_noise_pixels","200.0"],["float","static_luminosity","0.8"]]},
    "fragment":          {"gl_name": "fragment",             "category": "dynamic",     "gpu_intensive": True},

    # --- 创意类 [creative] ---
    "heart":             {"gl_name": "heart",                "category": "creative",    "gpu_intensive": False},
    "bounce":            {"gl_name": "Bounce",               "category": "creative",    "gpu_intensive": True,  "params": [["float","shadow_height","0.075"],["float","bounces","3.0"]]},
    "colour_distance":   {"gl_name": "ColourDistance",       "category": "creative",    "gpu_intensive": True,  "params": [["float","power","5.0"]]},
    "crazy_parametric":  {"gl_name": "CrazyParametricFun",   "category": "creative",    "gpu_intensive": True,  "params": [["float","a","4"],["float","b","1"],["float","amplitude","120"],["float","smoothness","0.1"]]},
    "inverted_pagecurl": {"gl_name": "InvertedPageCurl",     "category": "creative",    "gpu_intensive": True},
    "perlin":            {"gl_name": "perlin",               "category": "creative",    "gpu_intensive": False, "params": [["float","scale","4.0"],["float","smoothness","0.01"],["float","seed","12.9898"]]},
    "pinwheel":          {"gl_name": "pinwheel",             "category": "creative",    "gpu_intensive": False, "params": [["float","speed","2.0"]]},
    "powerkaleido":      {"gl_name": "powerKaleido",         "category": "creative",    "gpu_intensive": True,  "params": [["float","scale","2.0"],["float","z","1.5"],["float","speed","5."]]},
    "tangentmotionblur": {"gl_name": "tangentMotionBlur",    "category": "creative",    "gpu_intensive": True},
    "crosswarp":         {"gl_name": "crosswarp",            "category": "creative",    "gpu_intensive": True},
    "zoomin_circles":    {"gl_name": "ZoomInCircles",        "category": "creative",    "gpu_intensive": True},
    "doom_transition":   {"gl_name": "DoomScreenTransition", "category": "creative",    "gpu_intensive": True,  "params": [["int","bars","30"],["float","amplitude","2"],["float","noise","0.1"],["float","frequency","0.5"],["float","dripScale","0.5"]]},
    "filmburn":          {"gl_name": "FilmBurn",             "category": "creative",    "gpu_intensive": True,  "params": [["float","Seed","2.31"]]},
    "dreamy":            {"gl_name": "Dreamy",               "category": "creative",    "gpu_intensive": True},
    "butterfly_scrawl":  {"gl_name": "ButterflyWaveScrawler","category": "creative",    "gpu_intensive": True,  "params": [["float","amplitude","1.0"],["float","waves","30.0"],["float","colorSeparation","0.3"]]},
    "cannabisleaf":      {"gl_name": "cannabisleaf",         "category": "creative",    "gpu_intensive": True},
    "burn0":             {"gl_name": "burn0",                "category": "creative",    "gpu_intensive": True},
    "displacement":      {"gl_name": "displacement",         "category": "creative",    "gpu_intensive": True,  "params": [["float","strength","0.5"]]},
    "directional_easing":{"gl_name": "directional-easing",   "category": "creative",    "gpu_intensive": True},
    "edge_transition":   {"gl_name": "EdgeTransition",       "category": "creative",    "gpu_intensive": True,  "params": [["float","edge_thickness","0.001"],["float","edge_brightness","8.0"]]},
    "mosaic_trans":      {"gl_name": "mosaic_transition",    "category": "creative",    "gpu_intensive": True,  "params": [["float","mosaicNum","10.0"]]},
    "multiply_blend":    {"gl_name": "multiply_blend",       "category": "creative",    "gpu_intensive": True},
    "polar_function":    {"gl_name": "polar_function",       "category": "creative",    "gpu_intensive": True,  "params": [["int","segments","5"]]},
    "random_noisex":     {"gl_name": "randomNoisex",         "category": "creative",    "gpu_intensive": True},
    "squareswire":       {"gl_name": "squareswire",          "category": "creative",    "gpu_intensive": True,  "params": [["float","smoothness","1.6"]]},
    "tileswave":         {"gl_name": "TilesWave",            "category": "creative",    "gpu_intensive": True},
    "undulatingburnout": {"gl_name": "undulatingBurnOut",    "category": "creative",    "gpu_intensive": True,  "params": [["float","smoothness","0.03"]]},
    "coord_from_in":     {"gl_name": "coord-from-in",        "category": "creative",    "gpu_intensive": True},
    "rolls":             {"gl_name": "Rolls",                "category": "creative",    "gpu_intensive": True,  "params": [["int","type","0"]]},
}

# 默认 Fragment Shader（fallback: 简单交叉溶解）
DEFAULT_FRAGMENT_SHADER = """
#version 330
uniform sampler2D fromTex;
uniform sampler2D toTex;
uniform float progress;
uniform vec2 resolution;
in vec2 v_texcoord;
out vec4 fragColor;

vec4 transition(vec2 uv) {
    return mix(
        texture(fromTex, uv),
        texture(toTex, uv),
        progress
    );
}

void main() {
    fragColor = transition(v_texcoord);
}
"""

# 顶点 Shader（通用）
VERTEX_SHADER = """
#version 330
in vec2 in_position;
in vec2 in_texcoord;
out vec2 v_texcoord;

void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_texcoord = in_texcoord;
}
"""


# ================================================================
#  GPU 转场渲染核心
# ================================================================
class GLTransitionRenderer:
    """GPU 加速转场渲染器 — 基于 gl-transitions Shader"""

    def __init__(
        self,
        shader_dir: str = None,
        fallback_to_cpu: bool = True,
        width: int = 1920,
        height: int = 1080,
    ):
        self.width = width
        self.height = height
        self.fallback_to_cpu = fallback_to_cpu
        self.shader_dir = Path(shader_dir) if shader_dir else Path(__file__).parent / "gl-transitions"

        self._ctx = None
        self._gpu_available = False
        self._shader_cache: Dict[str, str] = {}
        self._program_cache: Dict[str, Any] = {}
        self._init_gpu()

    def _init_gpu(self):
        """初始化 OpenGL 上下文"""
        try:
            import moderngl
            self._ctx = moderngl.create_standalone_context(require=330)
            self._gpu_available = True
        except Exception:
            self._gpu_available = False

    @property
    def available_transitions(self) -> List[str]:
        """列出所有可用转场效果"""
        return sorted(GL_TRANSITION_TABLE.keys())

    def list_by_category(self, category: str) -> List[str]:
        """按分类列出转场"""
        return sorted([
            name for name, info in GL_TRANSITION_TABLE.items()
            if info["category"] == category
        ])

    def list_categories(self) -> List[str]:
        """列出所有分类"""
        return sorted(set(info["category"] for info in GL_TRANSITION_TABLE.values()))

    def get_transition_info(self, name: str) -> Optional[Dict[str, Any]]:
        """获取转场信息"""
        return GL_TRANSITION_TABLE.get(name)

    def load_gl_transition_shader(self, gl_name: str) -> Optional[str]:
        """从 gl-transitions 仓库加载 GLSL Shader 源码"""
        if gl_name in self._shader_cache:
            return self._shader_cache[gl_name]

        shader_file = self.shader_dir / "transitions" / f"{gl_name}.glsl"
        if shader_file.exists():
            shader_src = shader_file.read_text(encoding="utf-8")
            self._shader_cache[gl_name] = shader_src
            return shader_src
        return None

    def build_fragment_shader(self, transition_name: str, gl_name: str) -> str:
        """构建完整的 Fragment Shader，注入 gl-transitions 标准 helper"""
        shader_src = self.load_gl_transition_shader(gl_name)

        if shader_src:
            # 包裹 gl-transitions 的 transition 函数到完整 Shader
            # 注入 getFromColor/getToColor helper —— gl-transitions 标准接口
            return f"""#version 330
uniform sampler2D fromTex;
uniform sampler2D toTex;
uniform float progress;
uniform vec2 resolution;
uniform float ratio;
in vec2 v_texcoord;
out vec4 fragColor;

// === gl-transitions standard helpers ===
vec4 getFromColor(vec2 uv) {{
    return texture(fromTex, uv);
}}
vec4 getToColor(vec2 uv) {{
    return texture(toTex, uv);
}}

// === transition source (from gl-transitions) ===
{shader_src}

void main() {{
    vec2 uv = v_texcoord;
    fragColor = transition(uv);
}}
"""
        # Fallback: 内置简单 Shader
        return self._build_fallback_shader(transition_name)

    def _build_fallback_shader(self, name: str) -> str:
        """生成内置 Shader（无 gl-transitions 源文件时的 fallback）"""
        builtin_shaders = {
            "crossfade": """vec4 transition(vec2 uv) {
                return mix(texture(fromTex, uv), texture(toTex, uv), progress);
            }""",
            "wipe_left": """vec4 transition(vec2 uv) {
                float p = smoothstep(0.0, 0.1, progress - uv.x);
                return mix(texture(fromTex, uv), texture(toTex, uv), p);
            }""",
            "wipe_right": """vec4 transition(vec2 uv) {
                float p = smoothstep(0.0, 0.1, uv.x - (1.0 - progress));
                return mix(texture(fromTex, uv), texture(toTex, uv), p);
            }""",
            "wipe_up": """vec4 transition(vec2 uv) {
                float p = smoothstep(0.0, 0.1, progress - uv.y);
                return mix(texture(fromTex, uv), texture(toTex, uv), p);
            }""",
            "wipe_down": """vec4 transition(vec2 uv) {
                float p = smoothstep(0.0, 0.1, uv.y - (1.0 - progress));
                return mix(texture(fromTex, uv), texture(toTex, uv), p);
            }""",
            "push": """vec4 transition(vec2 uv) {
                vec2 offset = mix(vec2(0.0), vec2(progress, 0.0), step(0.5, progress));
                vec4 fromColor = texture(fromTex, uv - offset);
                vec4 toColor = texture(toTex, uv + vec2(1.0 - progress, 0.0));
                return mix(fromColor, toColor, step(uv.x, 1.0 - progress));
            }""",
            "zoom": """vec4 transition(vec2 uv) {
                vec2 center = vec2(0.5);
                float zoom = 1.0 + progress * 0.5;
                vec2 zoomed = center + (uv - center) / zoom;
                return mix(
                    texture(fromTex, zoomed),
                    texture(toTex, uv),
                    smoothstep(0.3, 0.7, progress)
                );
            }""",
            "spin": """vec4 transition(vec2 uv) {
                float angle = progress * 6.28318;
                vec2 center = vec2(0.5);
                float dist = distance(uv, center);
                float a = atan(uv.y - center.y, uv.x - center.x) + angle * (1.0 - dist * 2.0);
                vec2 rotated = center + vec2(cos(a), sin(a)) * dist;
                return mix(texture(fromTex, rotated), texture(toTex, uv), step(dist, progress * 1.5));
            }""",
            "glitch": """float rand(vec2 co) {
                return fract(sin(dot(co.xy, vec2(12.9898,78.233))) * 43758.5453);
            }
            vec4 transition(vec2 uv) {
                float r = rand(vec2(progress * 10.0, uv.y));
                float offset = r * 0.05 * progress;
                vec4 fromColor = texture(fromTex, uv + vec2(offset, 0.0));
                vec4 toColor = texture(toTex, uv);
                float mask = step(r, progress);
                return mix(fromColor, toColor, mask);
            }""",
            "dissolve": """float rand(vec2 co) {
                return fract(sin(dot(co.xy, vec2(12.9898,78.233))) * 43758.5453);
            }
            vec4 transition(vec2 uv) {
                return mix(
                    texture(fromTex, uv),
                    texture(toTex, uv),
                    step(rand(uv * 100.0), progress)
                );
            }""",
            "swirl": """vec4 transition(vec2 uv) {
                vec2 center = vec2(0.5);
                float angle = progress * 6.28318 * 2.0;
                float dist = distance(uv, center);
                float a = atan(uv.y - center.y, uv.x - center.x) + angle * (1.0 - dist);
                vec2 swirled = center + vec2(cos(a), sin(a)) * dist;
                return mix(texture(fromTex, swirled), texture(toTex, uv), step(dist, progress));
            }""",
            "cube": """vec4 transition(vec2 uv) {
                float p = progress * 1.5;
                vec2 center = vec2(p, 0.5);
                float angle = p * 1.5708;
                mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
                vec2 from_uv = uv;
                vec2 to_uv = uv;
                if (uv.x < p) {
                    from_uv = center + rot * (uv - center);
                    to_uv = vec2(-1.0);
                }
                return mix(texture(fromTex, from_uv), texture(toTex, uv), step(p, uv.x));
            }""",
            "page_curl": """vec4 transition(vec2 uv) {
                float curl = 1.0 - progress;
                float shadow = smoothstep(curl - 0.1, curl + 0.1, uv.x);
                vec3 col = mix(
                    texture(fromTex, uv).rgb,
                    texture(toTex, uv).rgb * 0.3,
                    shadow
                );
                return vec4(col, 1.0);
            }""",
        }

        gl_name = GL_TRANSITION_TABLE.get(name, {}).get("gl_name", "fade")
        func = builtin_shaders.get(
            gl_name,
            """vec4 transition(vec2 uv) {
                return mix(texture(fromTex, uv), texture(toTex, uv), progress);
            }"""
        )
        return f"""#version 330
uniform sampler2D fromTex;
uniform sampler2D toTex;
uniform float progress;
uniform vec2 resolution;
in vec2 v_texcoord;
out vec4 fragColor;

{func}

void main() {{
    fragColor = transition(v_texcoord);
}}
"""

    def render_frames(
        self,
        transition_name: str,
        frame_a: Any,
        frame_b: Any,
        progress: float,
    ) -> Any:
        """
        GPU 渲染两帧之间的转场。

        Args:
            transition_name: 转场名称（如 "wipe_left", "glitch"）
            frame_a: 起始帧 (numpy array RGB)
            frame_b: 结束帧 (numpy array RGB)
            progress: 0.0~1.0 转场进度

        Returns:
            混合后的帧 (numpy array RGB)
        """
        if not self._gpu_available:
            return self._cpu_fallback(transition_name, frame_a, frame_b, progress)

        try:
            import moderngl
            import numpy as np

            info = GL_TRANSITION_TABLE.get(transition_name, {"gl_name": "fade", "category": "dissolve"})
            gl_name = info["gl_name"]

            # 确保帧大小一致
            h, w = frame_a.shape[:2]
            if frame_a.shape != frame_b.shape:
                import cv2
                frame_b = cv2.resize(frame_b, (w, h))

            # 转换为 RGBA
            if len(frame_a.shape) == 2:
                frame_a = np.stack([frame_a] * 3, axis=-1)
            if frame_a.shape[2] == 3:
                frame_a = np.dstack([frame_a, np.full((h, w, 1), 255, dtype=np.uint8)])
            if len(frame_b.shape) == 2:
                frame_b = np.stack([frame_b] * 3, axis=-1)
            if frame_b.shape[2] == 3:
                frame_b = np.dstack([frame_b, np.full((h, w, 1), 255, dtype=np.uint8)])

            # 创建纹理
            tex_a = self._ctx.texture((w, h), 4, frame_a.tobytes())
            tex_b = self._ctx.texture((w, h), 4, frame_b.tobytes())

            # Shader 程序（带缓存）
            cache_key = f"{transition_name}_{w}_{h}"
            if cache_key not in self._program_cache:
                frag_src = self.build_fragment_shader(transition_name, gl_name)
                program = self._ctx.program(
                    vertex_shader=VERTEX_SHADER,
                    fragment_shader=frag_src,
                )
                self._program_cache[cache_key] = program
            else:
                program = self._program_cache[cache_key]

            # 渲染四边形
            quad = np.array([
                -1.0, -1.0, 0.0, 0.0,
                 1.0, -1.0, 1.0, 0.0,
                -1.0,  1.0, 0.0, 1.0,
                 1.0,  1.0, 1.0, 1.0,
            ], dtype=np.float32)

            vbo = self._ctx.buffer(quad.tobytes())
            vao = self._ctx.simple_vertex_array(
                program, vbo, "in_position", "in_texcoord"
            )

            # FBO
            fbo = self._ctx.framebuffer(
                color_attachments=[self._ctx.texture((w, h), 4)]
            )
            fbo.use()

            self._ctx.clear(0, 0, 0, 1)
            tex_a.use(location=0)
            tex_b.use(location=1)
            program["fromTex"] = 0
            program["toTex"] = 1
            program["progress"] = float(progress)
            program["resolution"] = (float(w), float(h))
            program["ratio"] = float(w) / float(h)

            # 注入 shader 参数化 uniform (从 GL_TRANSITION_TABLE)
            for param in info.get("params", []):
                ptype, pname, pdefault = param
                if pname not in ("progress", "resolution", "ratio", "fromTex", "toTex"):
                    try:
                        if ptype == "int":
                            program[pname] = int(float(pdefault))
                        elif ptype == "bool":
                            program[pname] = bool(float(pdefault))
                        elif ptype == "float":
                            program[pname] = float(pdefault)
                        else:
                            program[pname] = float(pdefault)
                    except (KeyError, TypeError):
                        pass  # uniform 可能不在 shader 中或类型不兼容

            vao.render(moderngl.TRIANGLE_STRIP)

            # 读取结果
            result = np.frombuffer(fbo.read(components=4), dtype=np.uint8).reshape((h, w, 4))

            # 清理
            vao.release()
            vbo.release()
            tex_a.release()
            tex_b.release()
            fbo.release()

            return result[:, :, :3]

        except Exception:
            return self._cpu_fallback(transition_name, frame_a, frame_b, progress)

    def _cpu_fallback(self, name: str, frame_a: Any, frame_b: Any, progress: float) -> Any:
        """CPU 回退渲染（使用 NumPy + 简单数学）"""
        import numpy as np

        a = frame_a.astype(np.float32) / 255.0
        b = frame_b.astype(np.float32) / 255.0

        if "wipe_left" in name:
            mask = (np.linspace(0, 1, a.shape[1]) < progress).astype(np.float32)[None, :, None]
        elif "wipe_right" in name:
            mask = (np.linspace(0, 1, a.shape[1]) > (1 - progress)).astype(np.float32)[None, :, None]
        elif "wipe_up" in name:
            mask = (np.linspace(0, 1, a.shape[0]) < progress).astype(np.float32)[:, None, None]
        elif "wipe_down" in name:
            mask = (np.linspace(0, 1, a.shape[0]) > (1 - progress)).astype(np.float32)[:, None, None]
        elif "glitch" in name:
            np.random.seed(int(progress * 1000))
            offsets = (np.random.randn(a.shape[0], a.shape[1], 1) * 0.02 * progress).astype(np.float32)
            r_idx = np.clip(np.arange(a.shape[1])[None, :, None] + offsets * a.shape[1], 0, a.shape[1] - 1).astype(np.int32)
            rows = np.arange(a.shape[0])[:, None, None]
            a = a[rows, r_idx, :].squeeze(2)
            mask = 0.5
            result = np.where(np.random.rand(*a.shape[:2], 1) < progress, b, a)
            return (np.clip(result, 0, 1) * 255).astype(np.uint8)
        elif "dissolve" in name:
            np.random.seed(42)
            mask = (np.random.rand(*a.shape[:2], 1) < progress).astype(np.float32)
        elif "crossfade" in name:
            result = a * (1 - progress) + b * progress
            return (np.clip(result, 0, 1) * 255).astype(np.uint8)
        else:
            mask = progress

        result = a * (1 - mask) + b * mask
        return (np.clip(result, 0, 1) * 255).astype(np.uint8)

    def render_transition_video(
        self,
        transition_name: str,
        video_a_path: str,
        video_b_path: str,
        output_path: str,
        duration: float = 1.0,
        fps: int = 30,
    ) -> Dict[str, Any]:
        """
        渲染两段视频之间的转场效果。

        Args:
            transition_name: 转场名称
            video_a_path: 前段视频路径
            video_b_path: 后段视频路径
            output_path: 输出视频路径
            duration: 转场持续时间（秒）
            fps: 帧率

        Returns:
            渲染结果
        """
        import cv2
        import numpy as np

        cap_a = cv2.VideoCapture(video_a_path)
        cap_b = cv2.VideoCapture(video_b_path)

        total_a = int(cap_a.get(cv2.CAP_PROP_FRAME_COUNT))
        total_b = int(cap_b.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_a = cap_a.get(cv2.CAP_PROP_FPS)
        fps_b = cap_b.get(cv2.CAP_PROP_FPS)

        # 获取转场起始帧和结束帧
        transition_frames = int(duration * fps)
        start_a = max(0, total_a - transition_frames)
        start_b = 0

        cap_a.set(cv2.CAP_PROP_POS_FRAMES, start_a)
        cap_b.set(cv2.CAP_PROP_POS_FRAMES, start_b)

        w = int(cap_a.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap_a.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

        frames_rendered = 0
        for i in range(transition_frames):
            ret_a, frame_a = cap_a.read()
            ret_b, frame_b = cap_b.read()
            if not ret_a:
                break

            progress = (i + 1) / transition_frames
            blended = self.render_frames(transition_name, frame_a, frame_b, progress)
            out.write(blended)
            frames_rendered += 1

        cap_a.release()
        cap_b.release()
        out.release()

        return {
            "success": True,
            "transition": transition_name,
            "frames_rendered": frames_rendered,
            "duration": duration,
            "output": output_path,
        }

    def get_mapping_to_pr_transition(self, gl_transition: str) -> Optional[str]:
        """将 GL 转场映射回 PR TransitionSystem 类型"""
        for pr_name, info in GL_TRANSITION_TABLE.items():
            if info["gl_name"] == gl_transition:
                return pr_name
        return None

    # ================================================================
    #  自动发现 & 参数提取 & 验证
    # ================================================================

    @staticmethod
    def auto_discover_shaders(shader_dir: str = None) -> Dict[str, Dict[str, Any]]:
        """
        自动扫描 gl-transitions/transitions/ 目录，发现所有未映射的 .glsl shader。
        返回 {key: {...}} 字典，可与 GL_TRANSITION_TABLE 合并。
        """
        import glob, re, os

        if shader_dir is None:
            shader_dir = str(Path(__file__).parent.parent / "ae" / "gl-transitions")

        trans_dir = os.path.join(shader_dir, "transitions")
        if not os.path.isdir(trans_dir):
            return {}

        discovered = {}
        known_gl_names = {info["gl_name"] for info in GL_TRANSITION_TABLE.values()}

        for fpath in sorted(glob.glob(os.path.join(trans_dir, "*.glsl"))):
            gl_name = os.path.basename(fpath).replace(".glsl", "")
            if gl_name in known_gl_names:
                continue

            # 分析 shader 复杂度决定分类
            source = open(fpath, "r", encoding="utf-8").read()
            has_rand = "rand(" in source or "noise" in source.lower()
            has_loop = "for(" in source or "for (" in source
            has_if   = "if (" in source
            is_complex = sum([has_rand, has_loop, has_if]) >= 2

            key = gl_name.lower().replace(" ", "_").replace("-", "_")

            # 提取 uniform 参数
            uniforms = re.findall(
                r'uniform\s+(\w+)\s+(\w+)\s*;\s*//\s*=\s*([\d.]+)',
                source
            )
            entry = {
                "gl_name": gl_name,
                "category": "creative" if is_complex else "dynamic",
                "gpu_intensive": is_complex,
                "auto_discovered": True,
            }
            if uniforms:
                entry["params"] = [[t, n, v] for t, n, v in uniforms]

            discovered[key] = entry

        return discovered

    @staticmethod
    def extract_uniform_params(gl_name: str, shader_dir: str = None) -> List[List[str]]:
        """
        提取指定 shader 的 uniform 参数默认值。

        Args:
            gl_name: gl-transitions shader 名称（如 "cube", "GlitchMemories"）

        Returns:
            [[type, name, default_value], ...]
        """
        import re, os

        if shader_dir is None:
            shader_dir = str(Path(__file__).parent.parent / "ae" / "gl-transitions")

        shader_file = os.path.join(shader_dir, "transitions", f"{gl_name}.glsl")
        if not os.path.isfile(shader_file):
            return []

        source = open(shader_file, "r", encoding="utf-8").read()
        uniforms = re.findall(
            r'uniform\s+(\w+)\s+(\w+)\s*;\s*//\s*=\s*([\d.]+)',
            source
        )
        return [[t, n, v] for t, n, v in uniforms]

    @staticmethod
    def validate_all_shaders(shader_dir: str = None) -> Dict[str, Any]:
        """
        验证所有 shader 文件是否可正确加载和构建。

        Returns:
            {
                "total": int,
                "valid": int,
                "missing": [str, ...],
                "parse_errors": [str, ...],
                "params_count": {str: int, ...}
            }
        """
        import os, glob

        if shader_dir is None:
            shader_dir = str(Path(__file__).parent.parent / "ae" / "gl-transitions")

        trans_dir = os.path.join(shader_dir, "transitions")
        result = {"total": 0, "valid": 0, "missing": [], "parse_errors": [], "params_count": {}}

        if not os.path.isdir(trans_dir):
            result["missing"].append(f"directory not found: {trans_dir}")
            return result

        known_gl_names = {info["gl_name"] for info in GL_TRANSITION_TABLE.values()}

        for gl_name in sorted(known_gl_names):
            result["total"] += 1
            fpath = os.path.join(trans_dir, f"{gl_name}.glsl")
            if not os.path.isfile(fpath):
                result["missing"].append(gl_name)
                continue

            try:
                source = open(fpath, "r", encoding="utf-8").read()
                # 基本语法检查：必须包含 transition 函数
                if "transition" not in source:
                    result["parse_errors"].append(f"{gl_name}: missing transition() function")
                    continue

                params = GLTransitionRenderer.extract_uniform_params(gl_name, shader_dir)
                result["params_count"][gl_name] = len(params)
                result["valid"] += 1
            except Exception as e:
                result["parse_errors"].append(f"{gl_name}: {e}")

        return result

    def get_all_transitions(self, include_auto_discovered: bool = False) -> Dict[str, Dict[str, Any]]:
        """获取所有转场（可选合并自动发现的 shader）"""
        all_trans = dict(GL_TRANSITION_TABLE)
        if include_auto_discovered:
            discovered = self.auto_discover_shaders(str(self.shader_dir))
            all_trans.update(discovered)
        return all_trans


# ================================================================
#  PR TransitionSystem 集成适配器
# ================================================================
class GLTransitionAdapter:
    """
    适配器：将 GLTransitionRenderer 集成到现有的 PremiereTransitionSystem 中。
    提供双向映射，支持 GPU 加速渲染以生成预览/代理。
    """

    def __init__(self, shader_dir: str = None):
        self.renderer = GLTransitionRenderer(shader_dir=shader_dir)

    def get_gpu_transitions(self) -> Dict[str, Dict[str, Any]]:
        """获取所有支持 GPU 渲染的转场及其分类"""
        categories = {}
        for name, info in GL_TRANSITION_TABLE.items():
            cat = info["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                "name": name,
                "gl_name": info["gl_name"],
                "gpu_intensive": info["gpu_intensive"],
            })
        return categories

    def render_preview(
        self,
        transition_type: str,
        frame_a_path: str,
        frame_b_path: str,
        output_frame_path: str,
        progress: float = 0.5,
    ) -> str:
        """生成转场预览帧（用于实时预览）"""
        import cv2
        fa = cv2.imread(frame_a_path)
        fb = cv2.imread(frame_b_path)
        if fa is None or fb is None:
            return ""
        result = self.renderer.render_frames(transition_type, fa, fb, progress)
        cv2.imwrite(output_frame_path, result)
        return output_frame_path


__all__ = [
    "GLTransitionRenderer",
    "GLTransitionAdapter",
    "GL_TRANSITION_TABLE",
    "DEFAULT_FRAGMENT_SHADER",
]
