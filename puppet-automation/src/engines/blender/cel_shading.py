"""Cel-shading (3渲2) 辅助模块 —— Blender Python 脚本模板与风格预设.

本模块为 BlenderEngine 提供:
- CEL_SHADING_SCRIPT_TEMPLATE: 在 Blender background 模式下执行的完整脚本模板
- get_style_preset(): 五种风格（日系动漫/美式卡通/赛博朋克/水墨/低多边形）的参数配置

优化点（v2 - 最高品质呈现）:
1. 双层色块分级（主色 + 阴影 + 高光 + 边缘光分块）
2. 平滑环绕 + 上下浮动 + 景深的相机动画
3. HDRI 环境光 + 顶部柔光 + 三点布光
4. 双层 Freestyle 轮廓线（外轮廓 + 内部结构线）
5. 128 采样 + SSR + DoF + 16bit PNG 输出
6. 渐变背景 + 后处理节点（色相微调 / AO / Bloom）
7. 修复 Blender 5.x 中 fcurves 访问错误

所有颜色值统一使用 Blender RGBA 元组字符串格式,便于直接嵌入脚本.
"""
from __future__ import annotations

from typing import Any

# =============================================================================
# 风格预设（v2 - 精致化色阶）
# =============================================================================


def get_style_preset(style: str) -> dict[str, Any]:
    """获取指定风格的完整参数预设.

    Args:
        style: 风格标识,支持 "anime" | "cartoon" | "cyberpunk" | "ink" | "lowpoly"

    Returns:
        包含颜色、轮廓、光照、渲染、后处理参数的字典
    """
    presets: dict[str, dict[str, Any]] = {
        "anime": {
            "display_name": "日系动漫",
            # 主色块分级（5层）
            "ramp_stops": [
                (0.0, "(0.12, 0.15, 0.38, 1.0)"),
                (0.25, "(0.32, 0.42, 0.72, 1.0)"),
                (0.50, "(0.62, 0.70, 0.92, 1.0)"),
                (0.78, "(0.90, 0.93, 0.98, 1.0)"),
                (1.0, "(1.0, 1.0, 1.0, 1.0)"),
            ],
            # 高光分块（金属/光泽面的强反光）
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.7, "(0.0, 0.0, 0.0, 1.0)"),
                (0.9, "(0.85, 0.88, 0.95, 1.0)"),
                (1.0, "(1.0, 1.0, 1.0, 1.0)"),
            ],
            # 边缘光分块（rim light 单独分级，增强立体感）
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.6, "(0.0, 0.0, 0.0, 1.0)"),
                (0.85, "(0.6, 0.7, 1.0, 1.0)"),
                (1.0, "(1.0, 1.0, 1.0, 1.0)"),
            ],
            "outline_color": "(0.02, 0.02, 0.05, 1.0)",
            "outline_thickness": 2.2,
            "inner_line_thickness": 1.2,
            "use_freestyle": True,
            "use_inner_lines": True,
            "key_light": {"color": "(1.0, 0.97, 0.92, 1.0)", "energy": 1800, "size": 3.0},
            "fill_light": {"color": "(0.7, 0.78, 1.0, 1.0)", "energy": 600, "size": 5.0},
            "rim_light": {"color": "(1.0, 0.95, 0.85, 1.0)", "energy": 1000, "size": 2.0},
            "top_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 400, "size": 6.0},
            "background_top": "(0.85, 0.88, 0.95, 1.0)",
            "background_bottom": "(0.45, 0.50, 0.70, 1.0)",
            "film_transparent": False,
            "render_samples": 128,
            "use_bloom": True,
            "bloom_intensity": 0.08,
            "use_ssr": True,
            "use_ao": True,
            "ao_factor": 0.6,
            "use_dof": True,
            "dof_aperture": 0.15,
            "hue_shift": 0.0,
            "saturation": 1.05,
            "value_mult": 1.02,
        },
        "cartoon": {
            "display_name": "美式卡通",
            "ramp_stops": [
                (0.0, "(0.55, 0.12, 0.08, 1.0)"),
                (0.35, "(0.85, 0.42, 0.10, 1.0)"),
                (0.65, "(0.98, 0.75, 0.25, 1.0)"),
                (1.0, "(1.0, 0.95, 0.80, 1.0)"),
            ],
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.8, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(1.0, 0.95, 0.80, 1.0)"),
            ],
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.7, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(1.0, 0.85, 0.50, 1.0)"),
            ],
            "outline_color": "(0.05, 0.05, 0.05, 1.0)",
            "outline_thickness": 4.5,
            "inner_line_thickness": 2.0,
            "use_freestyle": True,
            "use_inner_lines": True,
            "key_light": {"color": "(1.0, 0.98, 0.9, 1.0)", "energy": 2000, "size": 3.0},
            "fill_light": {"color": "(0.85, 0.9, 1.0, 1.0)", "energy": 350, "size": 3.0},
            "rim_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 900, "size": 2.0},
            "top_light": {"color": "(1.0, 0.98, 0.92, 1.0)", "energy": 500, "size": 7.0},
            "background_top": "(0.98, 0.92, 0.78, 1.0)",
            "background_bottom": "(0.78, 0.55, 0.30, 1.0)",
            "film_transparent": False,
            "render_samples": 128,
            "use_bloom": True,
            "bloom_intensity": 0.12,
            "use_ssr": True,
            "use_ao": True,
            "ao_factor": 0.7,
            "use_dof": True,
            "dof_aperture": 0.18,
            "hue_shift": 0.0,
            "saturation": 1.15,
            "value_mult": 1.05,
        },
        "cyberpunk": {
            "display_name": "赛博朋克",
            "ramp_stops": [
                (0.0, "(0.03, 0.0, 0.12, 1.0)"),
                (0.28, "(0.35, 0.0, 0.55, 1.0)"),
                (0.55, "(0.0, 0.75, 0.95, 1.0)"),
                (0.85, "(0.85, 0.15, 0.75, 1.0)"),
                (1.0, "(1.0, 0.30, 0.85, 1.0)"),
            ],
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.75, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(0.0, 1.0, 1.0, 1.0)"),
            ],
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.5, "(0.0, 0.0, 0.0, 1.0)"),
                (0.85, "(0.0, 0.95, 1.0, 1.0)"),
                (1.0, "(1.0, 0.20, 0.85, 1.0)"),
            ],
            "outline_color": "(0.0, 0.85, 1.0, 1.0)",
            "outline_thickness": 2.5,
            "inner_line_thickness": 1.5,
            "use_freestyle": True,
            "use_inner_lines": True,
            "key_light": {"color": "(1.0, 0.20, 0.80, 1.0)", "energy": 1800, "size": 3.0},
            "fill_light": {"color": "(0.0, 0.65, 1.0, 1.0)", "energy": 1000, "size": 3.0},
            "rim_light": {"color": "(0.0, 1.0, 0.85, 1.0)", "energy": 1500, "size": 2.0},
            "top_light": {"color": "(0.5, 0.0, 0.95, 1.0)", "energy": 600, "size": 5.0},
            "background_top": "(0.10, 0.05, 0.25, 1.0)",
            "background_bottom": "(0.35, 0.0, 0.45, 1.0)",
            "film_transparent": False,
            "render_samples": 160,
            "use_bloom": True,
            "bloom_intensity": 0.25,
            "use_ssr": True,
            "use_ao": True,
            "ao_factor": 0.5,
            "use_dof": True,
            "dof_aperture": 0.20,
            "hue_shift": 0.0,
            "saturation": 1.25,
            "value_mult": 1.0,
        },
        "ink": {
            "display_name": "水墨风格",
            "ramp_stops": [
                (0.0, "(0.03, 0.03, 0.03, 1.0)"),
                (0.35, "(0.30, 0.30, 0.32, 1.0)"),
                (0.70, "(0.65, 0.66, 0.68, 1.0)"),
                (1.0, "(0.92, 0.92, 0.94, 1.0)"),
            ],
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.9, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(0.95, 0.95, 0.95, 1.0)"),
            ],
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.8, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(1.0, 1.0, 1.0, 1.0)"),
            ],
            "outline_color": "(0.05, 0.05, 0.05, 1.0)",
            "outline_thickness": 4.0,
            "inner_line_thickness": 2.0,
            "use_freestyle": True,
            "use_inner_lines": True,
            "key_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 1200, "size": 5.0},
            "fill_light": {"color": "(0.85, 0.88, 0.95, 1.0)", "energy": 250, "size": 5.0},
            "rim_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 500, "size": 4.0},
            "top_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 300, "size": 8.0},
            "background_top": "(0.98, 0.97, 0.95, 1.0)",
            "background_bottom": "(0.75, 0.72, 0.68, 1.0)",
            "film_transparent": False,
            "render_samples": 96,
            "use_bloom": False,
            "bloom_intensity": 0.0,
            "use_ssr": False,
            "use_ao": True,
            "ao_factor": 0.8,
            "use_dof": True,
            "dof_aperture": 0.12,
            "hue_shift": 0.0,
            "saturation": 0.85,
            "value_mult": 1.05,
        },
        "lowpoly": {
            "display_name": "低多边形",
            "ramp_stops": [
                (0.0, "(0.18, 0.48, 0.58, 1.0)"),
                (0.5, "(0.48, 0.82, 0.78, 1.0)"),
                (1.0, "(1.0, 1.0, 0.85, 1.0)"),
            ],
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.85, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(0.9, 0.95, 0.85, 1.0)"),
            ],
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.75, "(0.0, 0.0, 0.0, 1.0)"),
                (1.0, "(0.95, 0.98, 0.85, 1.0)"),
            ],
            "outline_color": "(0.10, 0.10, 0.15, 1.0)",
            "outline_thickness": 2.0,
            "inner_line_thickness": 1.0,
            "use_freestyle": False,
            "use_inner_lines": False,
            "key_light": {"color": "(1.0, 0.95, 0.85, 1.0)", "energy": 1600, "size": 4.0},
            "fill_light": {"color": "(0.80, 0.90, 1.0, 1.0)", "energy": 400, "size": 4.0},
            "rim_light": {"color": "(1.0, 1.0, 1.0, 1.0)", "energy": 600, "size": 3.0},
            "top_light": {"color": "(1.0, 0.98, 0.90, 1.0)", "energy": 350, "size": 6.0},
            "background_top": "(0.55, 0.78, 0.85, 1.0)",
            "background_bottom": "(0.30, 0.50, 0.60, 1.0)",
            "film_transparent": False,
            "render_samples": 96,
            "use_bloom": True,
            "bloom_intensity": 0.06,
            "use_ssr": True,
            "use_ao": True,
            "ao_factor": 0.85,
            "use_dof": True,
            "dof_aperture": 0.20,
            "hue_shift": 0.0,
            "saturation": 1.10,
            "value_mult": 1.05,
        },
        "douyin_3to2": {
            "display_name": "抖音3渲2(赛璐璐+厚涂混合)",
            # 逆向自参考视频: banding_score=1.0, 2级主色阶, 冷海军蓝色系
            # v3修正(仅对标frame_0011~0033): 目标段brightness_std=82.7, 需极端两极分化
            "ramp_stops": [
                (0.0, "(0.01, 0.01, 0.03, 1.0)"),
                (0.25, "(0.08, 0.12, 0.24, 1.0)"),
                (0.50, "(0.28, 0.36, 0.55, 1.0)"),
                (0.75, "(0.65, 0.72, 0.86, 1.0)"),
                (1.0, "(1.0, 0.97, 0.92, 1.0)"),
            ],
            # 软渐变高光(视频specular_style=soft_gradient, 暖色倾向)
            "specular_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.60, "(0.0, 0.0, 0.0, 1.0)"),
                (0.82, "(0.50, 0.48, 0.55, 1.0)"),
                (1.0, "(1.0, 0.95, 0.88, 1.0)"),
            ],
            # 极弱边缘光(视频rim_intensity=0.0, 仅保留微量立体感)
            "rim_stops": [
                (0.0, "(0.0, 0.0, 0.0, 1.0)"),
                (0.70, "(0.0, 0.0, 0.0, 1.0)"),
                (0.90, "(0.25, 0.30, 0.42, 1.0)"),
                (1.0, "(0.50, 0.55, 0.65, 1.0)"),
            ],
            # 深灰蓝描边(视频实测#33444B, 2.1px; v2加粗补偿线条覆盖不足)
            "outline_color": "(0.05, 0.06, 0.10, 1.0)",
            "outline_thickness": 2.5,
            "inner_line_thickness": 1.8,
            "use_freestyle": True,
            "use_inner_lines": True,
            # v3: 主灯再加强+补光再减弱 → 极端明暗分离(目标std=82.7)
            "key_light": {"color": "(1.0, 0.97, 0.92, 1.0)", "energy": 3200, "size": 4.0},
            "fill_light": {"color": "(0.45, 0.52, 0.78, 1.0)", "energy": 180, "size": 6.0},
            "rim_light": {"color": "(0.70, 0.75, 0.90, 1.0)", "energy": 200, "size": 2.0},
            "top_light": {"color": "(0.92, 0.92, 0.95, 1.0)", "energy": 400, "size": 7.0},
            # 暗海军蓝渐变背景(v2进一步压暗)
            "background_top": "(0.05, 0.07, 0.14, 1.0)",
            "background_bottom": "(0.01, 0.02, 0.05, 1.0)",
            "film_transparent": False,
            "render_samples": 256,
            "use_bloom": True,
            "bloom_intensity": 0.05,
            "use_ssr": False,
            "use_ao": True,
            "ao_factor": 0.6,
            "use_dof": True,
            "dof_aperture": 0.10,
            "hue_shift": 0.0,
            "saturation": 1.05,
            "value_mult": 1.0,
        },
    }
    return presets.get(style, presets["anime"])


# =============================================================================
# Blender Python 脚本模板（v2 - 最高品质）
# =============================================================================

CEL_SHADING_SCRIPT_TEMPLATE = '''
"""Auto-generated cel-shading (3渲2) render script - v2 optimized."""
import bpy
import sys
import os
import json
import math

# ---------------------------------------------------------------------------
# 参数加载（从 JSON 文件读取）
# ---------------------------------------------------------------------------
PARAMS_FILE = "{params_file}"
with open(PARAMS_FILE, "r", encoding="utf-8") as f:
    params = json.load(f)

STYLE_NAME = params["style_name"]
MODEL_PATH = params["model_path"]
RESOLUTION_X = params["resolution_x"]
RESOLUTION_Y = params["resolution_y"]

print("=" * 60)
print("DEBUG: STYLE =", STYLE_NAME)
print("DEBUG: MODEL_PATH =", repr(MODEL_PATH))
print("DEBUG: MODEL_PATH exists =", os.path.exists(MODEL_PATH))
print("=" * 60)

FRAME_START = params["frame_start"]
FRAME_END = params["frame_end"]
RENDER_OUTPUT = params["render_output"]
BLEND_OUTPUT = params["blend_output"]
MARKER_PATH = params["marker_path"]
EXPORT_FBX = params["export_fbx"]
FBX_OUTPUT = params["fbx_output"]
USE_FREESTYLE = params["use_freestyle"]
USE_INNER_LINES = params["use_inner_lines"]
OUTLINE_COLOR = params["outline_color"]
OUTLINE_THICKNESS = params["outline_thickness"]
INNER_LINE_THICKNESS = params["inner_line_thickness"]
FILM_TRANSPARENT = params["film_transparent"]
RENDER_SAMPLES = params["render_samples"]
USE_BLOOM = params["use_bloom"]
BLOOM_INTENSITY = params["bloom_intensity"]
USE_SSR = params["use_ssr"]
USE_AO = params["use_ao"]
AO_FACTOR = params["ao_factor"]
USE_DOF = params["use_dof"]
DOF_APERTURE = params["dof_aperture"]
HUE_SHIFT = params["hue_shift"]
SATURATION = params["saturation"]
VALUE_MULT = params["value_mult"]
RAMP_STOPS = params["ramp_stops"]
SPECULAR_STOPS = params["specular_stops"]
RIM_STOPS = params["rim_stops"]
KEY_LIGHT = params["key_light"]
FILL_LIGHT = params["fill_light"]
RIM_LIGHT = params["rim_light"]
TOP_LIGHT = params["top_light"]
BACKGROUND_TOP = params["background_top"]
BACKGROUND_BOTTOM = params["background_bottom"]


def safe_eval_color(color_str):
    """安全解析颜色字符串为 RGBA 元组。

    安全策略：使用 ast.literal_eval 替代 eval，仅允许字面量（数字、元组、列表），
    禁止任何函数调用或名称解析，杜绝代码注入风险。
    """
    import ast
    try:
        c = ast.literal_eval(color_str)
        if isinstance(c, (tuple, list)) and len(c) >= 3:
            return (float(c[0]), float(c[1]), float(c[2]), 1.0)
    except (ValueError, SyntaxError, TypeError):
        pass
    return (0.8, 0.8, 0.8, 1.0)


def set_keyframe_linear(obj, data_path, frame, value):
    """插入关键帧并立即设置为线性插值（避免访问 fcurves 出错）."""
    try:
        if isinstance(value, (tuple, list)):
            for i, v in enumerate(value):
                obj.keyframe_insert(data_path=data_path, index=i, frame=frame)
        else:
            obj.keyframe_insert(data_path=data_path, frame=frame)
    except Exception as e:
        print("keyframe_insert failed: " + str(e))
        return

    # 安全地访问 fcurves 并设置线性插值
    try:
        ad = obj.animation_data
        if ad is None:
            return
        action = ad.action
        if action is None:
            # 尝试创建动作
            try:
                ad.action = bpy.data.actions.new(name=obj.name + "_Action")
                action = ad.action
            except Exception:
                return
        # Blender 5.x 兼容：fcurves 可能在 action.fcurves 或 ad.fcurves
        fcurves = None
        try:
            fcurves = action.fcurves
        except AttributeError:
            try:
                fcurves = ad.fcurves
            except AttributeError:
                return
        if fcurves is None:
            return
        for fc in fcurves:
            if fc.data_path == data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    except Exception as e:
        print("set interpolation failed: " + str(e))


# ---------------------------------------------------------------------------
# 1. 清理场景
# ---------------------------------------------------------------------------
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

for mat in list(bpy.data.materials):
    if mat.users == 0:
        bpy.data.materials.remove(mat)
for mesh in list(bpy.data.meshes):
    if mesh.users == 0:
        bpy.data.meshes.remove(mesh)
for cam in list(bpy.data.cameras):
    if cam.users == 0:
        bpy.data.cameras.remove(cam)
for light in list(bpy.data.lights):
    if light.users == 0:
        bpy.data.lights.remove(light)

# ---------------------------------------------------------------------------
# 2. 渲染引擎设置 (EEVEE - 高品质)
# ---------------------------------------------------------------------------
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = RESOLUTION_X
scene.render.resolution_y = RESOLUTION_Y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '16'
scene.render.film_transparent = FILM_TRANSPARENT
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END

# 颜色管理 - 强制 AgX (消除不同机器默认色彩漂移,保证跨设备一致)
# AgX 是 Blender 4.x+ 默认视图变换,提供更自然的对比度和色彩还原
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0
scene.display_settings.display_device = 'sRGB'

# 运动模糊 (v3: 提升动态感,快门 180 度)
try:
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    print(">>> v3: Motion blur enabled (shutter=0.5)")
except Exception as e_mb:
    print(">>> v3: Motion blur failed: " + str(e_mb))

# EEVEE 高品质设置（Blender 5.x: EEVEE Next 已成为默认 BLENDER_EEVEE）
eevee = scene.eevee

# 场景级降噪 (EEVEE 5.x, 让色块边缘更干净)
try:
    eevee.use_denoise = True
    print(">>> v3: EEVEE denoise enabled")
except Exception:
    pass

# 软阴影 + 高质量阴影 (5.x 仍支持)
try:
    eevee.use_soft_shadows = True
except Exception:
    pass
try:
    eevee.taa_samples = 16
except Exception:
    pass

# 渲染采样数 (v3: 提高到 128+)
try:
    eevee.taa_render_samples = RENDER_SAMPLES
except AttributeError:
    pass

# 色块分级提示: AO/Bloom 由材质节点 + 合成器承担
print("EEVEE config: samples=" + str(RENDER_SAMPLES) + " | AO via material node | Bloom via compositor Glare")

# ---------------------------------------------------------------------------
# 3. 加载或创建模型
# ---------------------------------------------------------------------------
mesh_objects = []
if MODEL_PATH and os.path.exists(MODEL_PATH):
    ext = os.path.splitext(MODEL_PATH)[1].lower()
    try:
        if ext == '.fbx':
            bpy.ops.import_scene.fbx(filepath=MODEL_PATH)
        elif ext in ('.obj',):
            bpy.ops.import_scene.obj(filepath=MODEL_PATH)
        elif ext in ('.glb', '.gltf'):
            bpy.ops.import_scene.gltf(filepath=MODEL_PATH)
        else:
            bpy.ops.wm.open_mainfile(filepath=MODEL_PATH)
    except Exception as e:
        print("Model load failed: " + str(e))
        bpy.ops.mesh.primitive_monkey_add(size=1.5, location=(0, 0, 0))
        mesh_objects.append(bpy.context.active_object)

    for o in list(bpy.context.selected_objects):
        if o.type == 'MESH':
            mesh_objects.append(o)

    if not mesh_objects:
        for o in bpy.data.objects:
            if o.type == 'MESH':
                mesh_objects.append(o)
else:
    bpy.ops.mesh.primitive_monkey_add(size=1.5, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = "CelSubject"
    bpy.ops.object.shade_smooth()
    mesh_objects.append(obj)

if not mesh_objects:
    raise RuntimeError("No mesh object available for cel-shading.")


# 计算模型包围盒中心和尺寸
def get_bounds(objects):
    from mathutils import Vector
    min_co = [float('inf')] * 3
    max_co = [float('-inf')] * 3
    for obj in objects:
        bbox = obj.bound_box
        for corner in bbox:
            world_corner = obj.matrix_world @ Vector(corner)
            for i in range(3):
                if world_corner[i] < min_co[i]:
                    min_co[i] = world_corner[i]
                if world_corner[i] > max_co[i]:
                    max_co[i] = world_corner[i]
    center = [(min_co[i] + max_co[i]) / 2 for i in range(3)]
    size = [max_co[i] - min_co[i] for i in range(3)]
    return center, size


bounds_center, bounds_size = get_bounds(mesh_objects)
max_dim = max(bounds_size) if max(bounds_size) > 0 else 1.0
print(">>> [SCALE] Original bounds: center=" + str(bounds_center) + ", size=" + str(bounds_size) + ", max_dim=" + str(max_dim))

# === 模型预处理（Blender Z轴向上，FBX导入后高度已在Z方向）===
# 注意：Blender标准坐标系 Z=上, Y=前(深度), X=右
# FBX导入时Blender会自动处理轴映射，模型通常已是正确站立姿态
# 之前错误地绕X轴旋转-90度，反而把模型放倒了，现移除该操作

# 1. 应用所有对象的现有缩放（让几何数据恢复真实大小）
print(">>> [SCALE] Applying existing transforms (scale + rotation)...")
bpy.ops.object.select_all(action='DESELECT')
for obj in mesh_objects:
    obj.select_set(True)
bpy.context.view_layer.objects.active = mesh_objects[0]
bpy.ops.object.transform_apply(scale=True, rotation=True, location=False)
bpy.context.view_layer.update()

# 2. 计算当前边界
bounds_center, bounds_size = get_bounds(mesh_objects)
max_dim = max(bounds_size) if max(bounds_size) > 0 else 1.0
print(">>> [SCALE] Initial bounds: size=" + str(bounds_size) + ", max_dim=" + str(max_dim))

# 3. 按目标尺寸缩放（目标高度约6个单位，高度是Z轴即bounds_size[2]）
target_size = 6.0
model_height_initial = bounds_size[2] if bounds_size[2] > 0 else max_dim
scale_factor = target_size / model_height_initial
print(">>> [SCALE] Target size=" + str(target_size) + ", scale_factor=" + str(scale_factor))

if abs(scale_factor - 1.0) > 0.001 and MODEL_PATH:
    bpy.ops.object.select_all(action='DESELECT')
    for obj in mesh_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]
    bpy.ops.transform.resize(value=(scale_factor, scale_factor, scale_factor))
    bpy.ops.object.transform_apply(scale=True)
    bounds_center, bounds_size = get_bounds(mesh_objects)
    print(">>> [SCALE] Final scaled: bounds=" + str(bounds_size) + ", max_dim=" + str(max(bounds_size)))

# 平滑着色
for mesh_obj in mesh_objects:
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    bpy.context.view_layer.objects.active = mesh_obj
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass

# 居中模型到原点（正确方法：使用 get_bounds 返回的中心）
if MODEL_PATH:
    print(">>> [CENTER] Model center before centering: " + str(bounds_center))
    
    for obj in mesh_objects:
        obj.location.x -= bounds_center[0]
        obj.location.y -= bounds_center[1]
        obj.location.z -= bounds_center[2]
    
    bpy.context.view_layer.update()
    print(">>> [CENTER] All objects moved to origin (view_layer updated)")
    
    bounds_center, bounds_size = get_bounds(mesh_objects)
    print(">>> [CENTER] Bounds after centering: center=" + str(bounds_center) + ", size=" + str(bounds_size))


# === v4: 模型部件位置检查与修复（修复武器/头饰偏离问题） ===
# 检测是否有部件严重偏离主体（如武器、头饰分离）
# 使用整个模型的几何中心作为基准
max_separation = max(bounds_size) * 0.5
print(">>> [PART_CHECK] Max separation threshold: " + str(max_separation))
print(">>> [PART_CHECK] Reference center: " + str(bounds_center))

separated_parts = []
for obj in mesh_objects:
    obj_center = [0, 0, 0]
    try:
        bbox = obj.bound_box
        corners = [obj.matrix_world @ Vector(v) for v in bbox]
        obj_center = [(min(c[i] for c in corners) + max(c[i] for c in corners)) / 2 for i in range(3)]
    except Exception:
        pass
    # 计算到模型中心的距离
    distance = sum((obj_center[i] - bounds_center[i]) ** 2 for i in range(3)) ** 0.5
    if distance > max_separation:
        obj_name = obj.name.lower()
        separated_parts.append((obj, distance, obj_name))
        print(">>> [PART_CHECK] Found separated part: " + obj.name + " at distance=" + str(distance))

# v7 会处理精细归位，这里只做简单标记，不移动部件


# === v10: 部件识别 (回滚: 移除骨骼系统, 保持FBX原始网格不变形) ===
# 根因: FBX为纯静态网格导出, 程序化骨骼+auto-weight导致网格严重变形
# 回滚策略: 不创建骨骼, 不做权重蒙皮, 模型保持FBX导入后的正确形态
# 仅保留部件识别逻辑(后续扇子归位需要)
import math as _v10_math
from mathutils import Vector as _V10Vec

try:
    _bc_v10 = list(bounds_center)
    _bs_v10 = list(bounds_size)
    _h_v10 = _bs_v10[2] if _bs_v10[2] > 0 else 6.0
    _w_v10 = _bs_v10[0] if _bs_v10[0] > 0 else 4.0
    _bottom_z = _bc_v10[2] - _h_v10 * 0.5
    _top_z = _bc_v10[2] + _h_v10 * 0.5

    # --- 1. 识别部件类型 ---
    _body_parts = []  # 主体mesh(需要蒙皮)
    _crown_part = None  # 发冠/头饰
    _face_part = None
    for _obj_v10 in mesh_objects:
        _nl = _obj_v10.name.lower()
        if 'weapon' in _nl:
            continue  # 武器由后续v9代码处理
        if '_op_' in _nl or 'object001' in _nl:
            # OP = ornament part = 发冠/头饰
            if _crown_part is None:
                _crown_part = _obj_v10
            continue
        if 'face' in _nl:
            _face_part = _obj_v10
        _body_parts.append(_obj_v10)

    # 如果Object001不是发冠，检查哪个小部件在头部区域且未被分类
    if _crown_part is None:
        _head_zone = _bottom_z + _h_v10 * 0.80
        for _obj_v10 in mesh_objects:
            _nl = _obj_v10.name.lower()
            if 'weapon' in _nl or 'face' in _nl or 'leg' in _nl or 'baosha' in _nl:
                continue
            if _obj_v10 in _body_parts and _obj_v10.name.lower().endswith('_high'):
                continue  # 主体部件
            try:
                _corners = [_obj_v10.matrix_world @ _V10Vec(v) for v in _obj_v10.bound_box]
                _cz = (min(c[2] for c in _corners) + max(c[2] for c in _corners)) / 2
                _vol = 1.0
                sx = max(c[0] for c in _corners) - min(c[0] for c in _corners)
                sy = max(c[1] for c in _corners) - min(c[1] for c in _corners)
                sz = max(c[2] for c in _corners) - min(c[2] for c in _corners)
                _vol = sx * sy * sz
                if _cz >= _head_zone and _vol < 1.0:
                    _crown_part = _obj_v10
                    if _obj_v10 in _body_parts:
                        _body_parts.remove(_obj_v10)
                    break
            except Exception:
                pass

    print(">>> [v10-RIG] Parts identified:")
    print(">>>   body_parts: " + str([o.name for o in _body_parts]))
    print(">>>   crown: " + (_crown_part.name if _crown_part else "None"))
    print(">>>   face: " + (_face_part.name if _face_part else "None"))

    # 回滚: 不创建骨骼, 不做权重蒙皮
    # 模型保持FBX导入后的原始形态(发冠/眼睛/身体均正确)
    _v10_armature = None
    _v10_hand_r_world = None
    _v10_hand_l_world = None
    print(">>> [v10-RIG] Armature DISABLED (rollback: keep FBX original mesh, no deformation)")

    # === v13: 发冠归位 — 基于头部顶点聚类定位 ===
    # 原理: 从主体mesh的上部20%区域找到头顶中心, 将发冠移动到该位置
    # v15: 默认禁用 — FBX导入后发冠位置通常正确, 自动归位反而容易出错
    _v13_crown_reposition = False
    if _v13_crown_reposition and _crown_part and _body_parts:
        try:
            bpy.context.view_layer.update()
            # 1. 从body mesh顶点定位头顶
            _crown_body = max([o for o in _body_parts if o.type == 'MESH'],
                             key=lambda o: len(o.data.vertices), default=None)
            if _crown_body and len(_crown_body.data.vertices) > 0:
                _cmw = _crown_body.matrix_world
                _cverts = [(_cmw @ _v.co) for _v in _crown_body.data.vertices]
                _czs = [v[2] for v in _cverts]
                _cz_min = min(_czs)
                _cz_max = max(_czs)
                _ch = _cz_max - _cz_min
                # 头顶区域: 上部15%的顶点 (Z > 85%高度)
                _head_z_threshold = _cz_min + _ch * 0.85
                _head_verts = [v for v in _cverts if v[2] >= _head_z_threshold]
                if len(_head_verts) >= 5:
                    # 头顶中心 = 头部区域顶点的XY中心 + Z最大值
                    _head_cx = sum(v[0] for v in _head_verts) / len(_head_verts)
                    _head_cy = sum(v[1] for v in _head_verts) / len(_head_verts)
                    _head_top_z = max(v[2] for v in _head_verts)
                    print(">>> [v13-CROWN] Head top detected from " + str(len(_head_verts)) + " verts (Z>" + str(round(_head_z_threshold, 2)) + "):")
                    print(">>>   center=(" + str(round(_head_cx, 3)) + ", " + str(round(_head_cy, 3)) + "), top_z=" + str(round(_head_top_z, 3)))

                    # 2. 获取发冠当前bbox中心
                    _crown_corners = [_crown_part.matrix_world @ _V10Vec(v) for v in _crown_part.bound_box]
                    _crown_cx = sum(c[0] for c in _crown_corners) / 8.0
                    _crown_cy = sum(c[1] for c in _crown_corners) / 8.0
                    _crown_cz = sum(c[2] for c in _crown_corners) / 8.0
                    _crown_bottom_z = min(c[2] for c in _crown_corners)
                    print(">>> [v13-CROWN] Crown current center: (" + str(round(_crown_cx, 3)) + ", " + str(round(_crown_cy, 3)) + ", " + str(round(_crown_cz, 3)) + ")")

                    # 3. 计算偏移: 发冠底部应在头顶, XY居中对齐头部中心
                    _crown_height = max(c[2] for c in _crown_corners) - _crown_bottom_z
                    _target_crown_cz = _head_top_z + _crown_height * 0.3  # 发冠底部略微嵌入头顶
                    _shift_x = _head_cx - _crown_cx
                    _shift_y = _head_cy - _crown_cy
                    _shift_z = _target_crown_cz - _crown_cz
                    _total_shift = (_shift_x**2 + _shift_y**2 + _shift_z**2) ** 0.5

                    # 只有偏移显著时才移动 (避免微调已正确的位置)
                    if _total_shift > 0.1:
                        _crown_part.location.x += _shift_x
                        _crown_part.location.y += _shift_y
                        _crown_part.location.z += _shift_z
                        bpy.context.view_layer.update()
                        print(">>> [v13-CROWN] Crown repositioned: shift=(" + str(round(_shift_x, 3)) + ", " + str(round(_shift_y, 3)) + ", " + str(round(_shift_z, 3)) + ")")
                    else:
                        print(">>> [v13-CROWN] Crown already at correct position (shift=" + str(round(_total_shift, 4)) + " < 0.1)")
                else:
                    print(">>> [v13-CROWN] Not enough head vertices (" + str(len(_head_verts)) + "), skipping")
        except Exception as _e_crown:
            print(">>> [v13-CROWN] Crown positioning error: " + str(_e_crown))
    else:
        print(">>> [v10-RIG] Crown positioning skipped (no crown or no body parts)")

except Exception as _e_v10:
    print(">>> [v10-RIG] ERROR: " + str(_e_v10))
    import traceback as _tb_v10
    _tb_v10.print_exc()
    _v10_armature = None
    _v10_hand_r_world = None
    _v10_hand_l_world = None
    _body_parts = [o for o in mesh_objects if 'weapon' not in o.name.lower()]
    _crown_part = None
    _face_part = None


# ---------------------------------------------------------------------------
# 4. 创建 Cel-Shading 材质（v2 - 双层色块 + 高光 + 边缘光分块）
# ---------------------------------------------------------------------------
def create_cel_material_v2(base_color=None, base_color_texture=None):
    """创建高品质 cel-shading 材质.

    节点结构:
      Principled BSDF (带贴图/原色) → ShaderToRGB → ColorRamp(主色块)
                                                          ↓
                                    MixRGB (Multiply, 原色) → 主色输出
      Principled BSDF (Specular) → ColorRamp(高光分块) → 高光输出
      Geometry(Normal/DotView) → ColorRamp(边缘光分块) → 边缘光叠加
      主色 + 高光 + 边缘光 → Mix → Emission(避免光照二次影响)
    """
    mat = bpy.data.materials.new(name="CelShadingMaterial_v2")
    mat.use_nodes = True
    mat.blend_method = 'OPAQUE'
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links

    for node in list(nodes):
        nodes.remove(node)

    # Output
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (1200, 0)

    # === 主色块分级 ===
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.location = (-800, 0)
    principled.inputs['Roughness'].default_value = 0.95
    try:
        principled.inputs['Specular IOR Level'].default_value = 0.0
    except KeyError:
        try:
            principled.inputs['Specular'].default_value = 0.0
        except KeyError:
            pass

    if base_color_texture:
        tex_node = nodes.new(type='ShaderNodeTexImage')
        tex_node.image = base_color_texture
        tex_node.location = (-1100, 100)
        links.new(tex_node.outputs['Color'], principled.inputs['Base Color'])
    elif base_color:
        principled.inputs['Base Color'].default_value = base_color

    # Shader to RGB (关键步骤 - EEVEE 才支持)
    shader_to_rgb = nodes.new(type='ShaderNodeShaderToRGB')
    shader_to_rgb.location = (-500, 0)
    links.new(principled.outputs[0], shader_to_rgb.inputs[0])

    # 主色块 ColorRamp (CONSTANT 模式)
    main_ramp = nodes.new(type='ShaderNodeValToRGB')
    main_ramp.location = (-200, 0)
    main_ramp.color_ramp.interpolation = 'CONSTANT'

    for i, (pos, color_str) in enumerate(RAMP_STOPS):
        pos = float(pos)
        if i == 0:
            main_ramp.color_ramp.elements[0].position = pos
            main_ramp.color_ramp.elements[0].color = safe_eval_color(color_str)
        else:
            elem = main_ramp.color_ramp.elements.new(position=pos)
            elem.color = safe_eval_color(color_str)

    # 用原色 Multiply 调色块（保留贴图颜色）
    color_mix = nodes.new(type='ShaderNodeMixRGB')
    color_mix.location = (100, 0)
    color_mix.blend_type = 'MULTIPLY'
    color_mix.inputs['Fac'].default_value = 1.0

    if base_color_texture:
        tex_copy = nodes.new(type='ShaderNodeTexImage')
        tex_copy.image = base_color_texture
        tex_copy.location = (-200, 300)
        links.new(tex_copy.outputs['Color'], color_mix.inputs[1])
    elif base_color:
        color_mix.inputs[1].default_value = base_color
    else:
        color_mix.inputs[1].default_value = (0.85, 0.85, 0.9, 1.0)

    links.new(shader_to_rgb.outputs[0], main_ramp.inputs[0])
    links.new(main_ramp.outputs[0], color_mix.inputs[2])

    # === 高光分块（基于 Specular 输出）===
    spec_ramp = nodes.new(type='ShaderNodeValToRGB')
    spec_ramp.location = (200, -300)
    spec_ramp.color_ramp.interpolation = 'CONSTANT'

    for i, (pos, color_str) in enumerate(SPECULAR_STOPS):
        pos = float(pos)
        if i == 0:
            spec_ramp.color_ramp.elements[0].position = pos
            spec_ramp.color_ramp.elements[0].color = safe_eval_color(color_str)
        else:
            elem = spec_ramp.color_ramp.elements.new(position=pos)
            elem.color = safe_eval_color(color_str)

    try:
        links.new(principled.outputs['Specular'], spec_ramp.inputs[0])
    except KeyError:
        # Blender 5.x 没有 Specular 输出，使用 GlossyBSDF 替代方案
        spec_ramp.inputs[0].default_value = 0.0

    # 主色 + 高光 = Screen 混合
    spec_mix = nodes.new(type='ShaderNodeMixRGB')
    spec_mix.location = (500, -150)
    spec_mix.blend_type = 'SCREEN'
    spec_mix.inputs['Fac'].default_value = 0.6
    links.new(color_mix.outputs[0], spec_mix.inputs[1])
    links.new(spec_ramp.outputs[0], spec_mix.inputs[2])

    # === 边缘光分块（基于法线与视线夹角）===
    geom_node = nodes.new(type='ShaderNodeNewGeometry')
    geom_node.location = (-500, -500)

    vector_math = nodes.new(type='ShaderNodeVectorMath')
    vector_math.location = (-200, -500)
    vector_math.operation = 'DOT_PRODUCT'
    links.new(geom_node.outputs['Normal'], vector_math.inputs[0])
    links.new(geom_node.outputs['Incoming'], vector_math.inputs[1])

    rim_ramp = nodes.new(type='ShaderNodeValToRGB')
    rim_ramp.location = (100, -500)
    rim_ramp.color_ramp.interpolation = 'CONSTANT'

    for i, (pos, color_str) in enumerate(RIM_STOPS):
        pos = float(pos)
        if i == 0:
            rim_ramp.color_ramp.elements[0].position = pos
            rim_ramp.color_ramp.elements[0].color = safe_eval_color(color_str)
        else:
            elem = rim_ramp.color_ramp.elements.new(position=pos)
            elem.color = safe_eval_color(color_str)

    links.new(vector_math.outputs[0], rim_ramp.inputs[0])

    # 主色 + 边缘光 = Add 混合
    rim_mix = nodes.new(type='ShaderNodeMixRGB')
    rim_mix.location = (700, -300)
    rim_mix.blend_type = 'ADD'
    rim_mix.inputs['Fac'].default_value = 0.8
    links.new(spec_mix.outputs[0], rim_mix.inputs[1])
    links.new(rim_ramp.outputs[0], rim_mix.inputs[2])

    # === 环境光遮蔽 (AO) - Blender 5.x 中 EEVEE use_gtao 已移除,改用材质节点 ===
    # AO 让角落/褶皱处变暗,增强立体感与层次
    ao_node = nodes.new(type='ShaderNodeAmbientOcclusion')
    ao_node.location = (500, -600)
    try:
        ao_node.inputs['Distance'].default_value = 0.5
        ao_node.samples = 16
    except Exception:
        pass

    # AO 因子与主色混合 (Multiply): 角落变暗
    ao_mix = nodes.new(type='ShaderNodeMixRGB')
    ao_mix.location = (850, -150)
    ao_mix.blend_type = 'MULTIPLY'
    ao_mix.inputs['Fac'].default_value = AO_FACTOR
    links.new(rim_mix.outputs[0], ao_mix.inputs[1])
    links.new(ao_node.outputs['AO'], ao_mix.inputs[2])

    # === v3: 次表面散射 (SSS) - 让皮肤/布料更通透 ===
    # SSS 模拟光线穿透材质的效果,增加真实感和层次感
    sss_strength = 0.15
    sss_mix = None
    try:
        sss_node = nodes.new(type='ShaderNodeSubsurfaceScattering')
        sss_node.location = (700, -400)
        try:
            sss_node.inputs['Scale'].default_value = 0.1
            sss_node.inputs['Radius'].default_value = (1.0, 0.5, 0.3)
        except Exception:
            pass

        sss_mix = nodes.new(type='ShaderNodeMixRGB')
        sss_mix.location = (1000, -150)
        sss_mix.blend_type = 'ADD'
        sss_mix.inputs['Fac'].default_value = sss_strength
        links.new(ao_mix.outputs[0], sss_mix.inputs[1])
        links.new(sss_node.outputs['Color'], sss_mix.inputs[2])
        print(">>> v3: SSS enabled (strength=" + str(sss_strength) + ")")
    except Exception as e_sss:
        print(">>> v3: SSS skipped: " + str(e_sss))
        sss_mix = None

    # === 最终输出：使用 Emission 避免被二次光照影响 ===
    emission = nodes.new(type='ShaderNodeEmission')
    emission.location = (1150, 0)
    emission.inputs['Strength'].default_value = 1.0

    if sss_mix is not None:
        links.new(sss_mix.outputs[0], emission.inputs['Color'])
    else:
        links.new(ao_mix.outputs[0], emission.inputs['Color'])

    links.new(emission.outputs[0], output_node.inputs['Surface'])

    return mat


def get_base_color_from_material(mat):
    """从原始材质提取基色或贴图.

    返回 (base_color, base_texture):
    - 当材质有有效的 TexImage 节点（image 不为 None）时，返回 (None, image)
    - 否则返回 (色值, None)，让外层走贴图自动匹配分支
    """
    if not mat or not mat.use_nodes:
        return (0.8, 0.8, 0.8, 1.0), None
    nodes = mat.node_tree.nodes
    for node in nodes:
        if node.type == 'BSDF_PRINCIPLED':
            base_color_input = node.inputs.get('Base Color')
            if base_color_input and base_color_input.is_linked:
                link = base_color_input.links[0]
                if link.from_node.type == 'TEX_IMAGE' and link.from_node.image:
                    # 关键：检查 image 是否真正加载了文件
                    if link.from_node.image.filepath or link.from_node.image.packed_file:
                        return None, link.from_node.image
                    # image 是占位符（FBX 导入时创建的空 TexImage），返回 None
                    # 让外层走贴图自动匹配
                    return (0.8, 0.8, 0.8, 1.0), None
            elif base_color_input:
                return tuple(base_color_input.default_value), None
    return (0.8, 0.8, 0.8, 1.0), None


# === 贴图自动加载：从模型目录搜索贴图文件并按物体名匹配 ===
# 当 FBX 中贴图 FileName 为空时（典型情况），需要手动加载
def find_textures_in_model_dir():
    """扫描模型目录下所有贴图文件,按类型分类返回."""
    if not MODEL_PATH or not os.path.exists(MODEL_PATH):
        return dict()
    model_dir = os.path.dirname(MODEL_PATH)
    tex_files = []
    for root, dirs, files in os.walk(model_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in ('.png', '.jpg', '.jpeg', '.tga', '.bmp'):
                tex_files.append(os.path.join(root, f))
    # 按类型分组
    tex_map = dict()
    for tf in tex_files:
        name = os.path.basename(tf).lower()
        # 漫反射（Diffuse/Base Color）
        if '_d_show' in name or '_d.' in name or name.endswith('_d.png') or 'diffuse' in name or 'base_color' in name or 'basecolor' in name:
            key = 'diffuse'
        elif '_n_show' in name or '_n.' in name or name.endswith('_n.png') or 'normal' in name:
            key = 'normal'
        elif '_mask' in name or 'mask' in name:
            key = 'mask'
        else:
            key = 'other'
        tex_map.setdefault(key, []).append(tf)
    print("Textures found in model dir: " + str(dict((k, len(v)) for k, v in tex_map.items())))
    return tex_map


def match_texture_for_object(obj_name, tex_files):
    """根据物体名匹配最合适的贴图文件."""
    if not tex_files:
        return None
    name = obj_name.lower()
    # 关键词匹配规则（按优先级）
    keyword_map = [
        # (物体名关键词, 贴图文件名关键词)
        (['face', '脸', 'head'], ['face']),
        (['weapon', '武', 'sword', 'blade'], ['weapon']),
        (['baosha', '爆纱', 'effect'], ['baosha']),
        (['body', 'shusheng', 'body2', 'mesh'], ['shusheng_d', 'body_d']),
    ]
    for obj_kw, tex_kws in keyword_map:
        if any(k in name for k in obj_kw):
            for tex_kw in tex_kws:
                for tf in tex_files:
                    if tex_kw in os.path.basename(tf).lower():
                        return tf
    # 没匹配到具体物体，使用第一个贴图
    return tex_files[0] if tex_files else None


def load_image_texture(filepath):
    """加载贴图为 bpy.data.images,失败返回 None."""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        img = bpy.data.images.load(filepath, check_existing=True)
        img.colorspace_settings.name = 'sRGB'  # 漫反射用 sRGB
        return img
    except Exception as e:
        print("Image load failed: " + str(filepath) + " - " + str(e))
        return None


# 收集所有可用贴图
TEX_MAP = find_textures_in_model_dir()
DIFFUSE_TEXS = TEX_MAP.get('diffuse', [])
print(">>> [TEX] Diffuse textures available: " + str(len(DIFFUSE_TEXS)))
for _tf in DIFFUSE_TEXS:
    print(">>>   - " + os.path.basename(_tf))


# 按物体顶点数排序，大→小，用于推测部位（大=主体身体，中=武器/装饰，小=脸）
def obj_vertex_count(o):
    try:
        return len(o.data.vertices)
    except Exception:
        return 0


# 推测贴图分类：根据贴图文件名关键词
def classify_diffuse_textures(tex_list):
    """把找到的 diffuse 贴图按部位分类."""
    body_tex = []
    face_tex = []
    weapon_tex = []
    baosha_tex = []
    other_tex = []
    for tf in tex_list:
        name = os.path.basename(tf).lower()
        if 'face' in name:
            face_tex.append(tf)
        elif 'weapon' in name:
            weapon_tex.append(tf)
        elif 'baosha' in name:
            baosha_tex.append(tf)
        elif 'shusheng_d' in name or '_d_show' in name:
            # 主体漫反射（排除 face/weapon/baosha）
            if 'face' not in name and 'weapon' not in name and 'baosha' not in name:
                body_tex.append(tf)
            else:
                other_tex.append(tf)
        else:
            other_tex.append(tf)
    return dict(
        body=body_tex,
        face=face_tex,
        weapon=weapon_tex,
        baosha=baosha_tex,
        other=other_tex,
    )


CLASSIFIED_TEXS = classify_diffuse_textures(DIFFUSE_TEXS)
print(">>> [TEX] Classified: " + str(dict((k, len(v)) for k, v in CLASSIFIED_TEXS.items())))


# 按顶点数排序物体（大→小）
SORTED_OBJS = sorted(mesh_objects, key=obj_vertex_count, reverse=True)
print("Objects by vertex count (top 3): " + str([(o.name, obj_vertex_count(o)) for o in SORTED_OBJS[:3]]))


# 应用 cel-shading 材质到所有网格
# 策略：根据物体名关键词匹配贴图（更精准）
for idx, mesh_obj in enumerate(mesh_objects):
    base_color = None
    base_tex = None
    orig_mat_name = ""

    # 1. 先尝试从原始材质提取贴图
    if mesh_obj.data.materials and mesh_obj.data.materials[0]:
        orig_mat = mesh_obj.data.materials[0]
        orig_mat_name = orig_mat.name
        base_color, base_tex = get_base_color_from_material(orig_mat)

    print(">>> [OBJ " + str(idx) + "] " + mesh_obj.name + " | orig_mat=" + orig_mat_name + " | has_tex=" + str(base_tex is not None))

    # 2. 如果原始材质没贴图,根据物体名匹配部位贴图
    if base_tex is None and DIFFUSE_TEXS:
        obj_name_lower = mesh_obj.name.lower()
        body_texs = CLASSIFIED_TEXS['body']
        face_texs = CLASSIFIED_TEXS['face']
        weapon_texs = CLASSIFIED_TEXS['weapon']
        baosha_texs = CLASSIFIED_TEXS['baosha']

        matched_tex = None
        matched_part = "fallback"
        # 按物体名关键词精准匹配（按优先级）
        if 'face' in obj_name_lower and face_texs:
            matched_tex = face_texs[0]
            matched_part = "face"
        elif 'weapon' in obj_name_lower and weapon_texs:
            matched_tex = weapon_texs[0]
            matched_part = "weapon"
        elif 'baosha' in obj_name_lower and baosha_texs:
            matched_tex = baosha_texs[0]
            matched_part = "baosha"
        elif body_texs:
            # 主体物体（如 5133_ShuSheng_High）
            matched_tex = body_texs[0]
            matched_part = "body"
        elif DIFFUSE_TEXS:
            matched_tex = DIFFUSE_TEXS[0]  # 兜底
            matched_part = "fallback"

        if matched_tex:
            base_tex = load_image_texture(matched_tex)
            if base_tex:
                print(">>>   -> matched[" + matched_part + "]: " + os.path.basename(matched_tex))
            else:
                print(">>>   -> load FAILED: " + os.path.basename(matched_tex))

    # 3. 应用 cel 材质
    if base_color is None and base_tex is None:
        base_color = (0.85, 0.85, 0.9, 1.0)
    cel_mat = create_cel_material_v2(base_color=base_color, base_color_texture=base_tex)
    if mesh_obj.data.materials:
        mesh_obj.data.materials[0] = cel_mat
    else:
        mesh_obj.data.materials.append(cel_mat)

print(">>> [MAT] Materials applied: " + str(len(mesh_objects)) + " objects")


# === v7 修复：薄纱/外袍半透明 + 武器归位 ===
# 问题根因（日志分析确认）：
#   1. 薄纱(Baosha) Z=-2.28~1.59、外袍(OP) Z=-2.3~1.03 是不透明的(blend_method=OPAQUE)
#      它们的底部边缘(Z≈-2.2)正好对应画面空白起始位置，遮挡了腿部(Z=-2.79~-2.21)
#   2. 武器(Weapon_High) X=-3.0~-0.9 脱离主体(X=0~3)约 3 米，导致"手部错位"
# 修复：
#   - 对薄纱/外袍物体添加 Transparent BSDF + MixShader，设 40% 透明度
#   - 对武器物体沿 +X 方向平移，使其靠近主体
TRANSPARENT_KEYWORDS = ['baosha', '_op_high', 'opa', 'cloak', 'veil', 'scarf', 'ribbon']
trans_count = 0
for mesh_obj in mesh_objects:
    name_lower = mesh_obj.name.lower()
    is_transparent_part = any(kw in name_lower for kw in TRANSPARENT_KEYWORDS)
    if is_transparent_part:
        try:
            mat_slot = mesh_obj.data.materials[0] if mesh_obj.data.materials else None
            if not mat_slot or not mat_slot.use_nodes:
                continue
            tree = mat_slot.node_tree
            # 找到 Output 和 Emission 节点
            out_node = None
            emi_node = None
            for n in tree.nodes:
                if n.type == 'OUTPUT_MATERIAL':
                    out_node = n
                elif n.type == 'EMISSION':
                    emi_node = n
            if not out_node or not emi_node:
                continue
            # 断开 Emission -> Output 的现有连接
            for lk in list(tree.links):
                if lk.to_node == out_node and lk.from_node == emi_node:
                    tree.links.remove(lk)
            # 添加 Transparent BSDF + MixShader
            trans_bsdf = tree.nodes.new(type='ShaderNodeBsdfTransparent')
            trans_bsdf.location = (emi_node.location.x, emi_node.location.y - 250)
            mix_shader = tree.nodes.new(type='ShaderNodeMixShader')
            mix_shader.location = (emi_node.location.x + 150, emi_node.location.y)
            mix_shader.inputs['Fac'].default_value = 0.4  # 40% 透明
            tree.links.new(emi_node.outputs[0], mix_shader.inputs[1])
            tree.links.new(trans_bsdf.outputs[0], mix_shader.inputs[2])
            tree.links.new(mix_shader.outputs[0], out_node.inputs['Surface'])
            mat_slot.blend_method = 'BLEND'
            try:
                mat_slot.shadow_method = 'HASHED'
            except Exception:
                pass
            trans_count += 1
            print(">>> [v7-TRANS] " + mesh_obj.name + " -> 40% transparent (blend=BLEND)")
        except Exception as e_trans:
            print(">>> [v7-TRANS] " + mesh_obj.name + " error: " + str(e_trans))
print(">>> [v7-TRANS] Total transparent parts: " + str(trans_count))


# --- v8 武器归位：精确手位置 + 扇子双部件组装 + 自然姿态 ---
# 问题根因分析：
#   1. 模型无骨骼，无法通过骨骼定位手
#   2. 之前算法把腿部/外袍最宽处当成了手，导致位置错误
#   3. 扇子有两个分离部件（扇柄+扇面），需要正确组装
#   4. v15版本修改了模型尺寸计算，破坏了全局相机定位，导致人物不在画面中
#
# v8 改进（恢复稳定版本）：
#   - 使用全局的 bounds_center, bounds_size，不重新计算模型尺寸
#   - Z-slice 宽度曲线分析，区分躯干/外袍/腿部
#   - 手位置 = 躯干宽度 + 手臂突出量（上半身 45%-55% 高度）
#   - 扇子双部件识别与组装：扇柄在手心，扇面展开
#   - 自然旋转角度，符合握持姿态
try:
    from mathutils import Vector as _WeaponVec
    from mathutils import Euler as _WeaponEuler
    import math as _wpn_math
except ImportError:
    _WeaponVec = None
    _WeaponEuler = None
    _wpn_math = None

_WEAPON_KEYWORDS = ['weapon']
_WEAPON_PROTECTED = ['face', 'leg', 'baosha', 'op']

_weapon_parts = []
_hat_parts = []
for _mesh_obj in mesh_objects:
    _name_lower = _mesh_obj.name.lower()
    _is_weapon = any(_kw in _name_lower for _kw in _WEAPON_KEYWORDS)
    _is_protected = any(_kw in _name_lower for _kw in _WEAPON_PROTECTED) and not _is_weapon
    if _is_weapon and not _is_protected:
        _weapon_parts.append(_mesh_obj)

# === v12核心策略: 网格顶点手部检测 + rotate-first扇子归位 ===
# 根因: FBX原始位置扇子在地面, 必须移动到手部位置
# v12: 用网格顶点找手(骨骼位置因auto-weight失败不可靠), rotate-first避免偏移
_v12_no_reposition = False
_fan_handle = None
_fan_blade = None

if _weapon_parts and _v12_no_reposition:
    print(">>> [v12-WEAPON] Keeping original FBX positions for " + str(len(_weapon_parts)) + " weapon parts")
    # 识别扇柄/扇面 (仅用于日志, 不移动)
    for _mesh_obj in _weapon_parts:
        if _fan_handle is None:
            _fan_handle = (_mesh_obj, 1.0)
        elif _fan_blade is None:
            _fan_blade = (_mesh_obj,)
    # parent到armature (保持原始位置, 跟随角色)
    try:
        if _v10_armature is not None:
            for _mesh_obj in _weapon_parts:
                if _mesh_obj.parent is None:
                    _mesh_obj.parent = _v10_armature
                    _mesh_obj.matrix_parent_inverse = _v10_armature.matrix_world.inverted()
            bpy.context.view_layer.update()
            print(">>> [v12-WEAPON] All weapon parts parented to armature (original positions preserved)")
    except Exception as _e_v12p:
        print(">>> [v12-WEAPON] Parent error: " + str(_e_v12p))

if _weapon_parts and not _v12_no_reposition:
    _bc = list(bounds_center) if hasattr(bounds_center, '__iter__') else [0, 0, 0]
    _bs = list(bounds_size) if hasattr(bounds_size, '__iter__') else [6, 6, 6]
    _model_h = _bs[2] if _bs[2] > 0 else 6.0
    _model_w = _bs[0] if _bs[0] > 0 else 6.0
    _model_d = _bs[1] if _bs[1] > 0 else 6.0
    _model_bottom_z = _bc[2] - _model_h * 0.5
    _model_top_z = _bc[2] + _model_h * 0.5
    _head_zone_z = _model_bottom_z + _model_h * 0.75

    _real_weapons = []
    for _mesh_obj in _weapon_parts:
        try:
            _bbox_corners = [_mesh_obj.matrix_world @ _WeaponVec(v) for v in _mesh_obj.bound_box]
            _zs = [c[2] for c in _bbox_corners]
            _xs = [c[0] for c in _bbox_corners]
            _ys = [c[1] for c in _bbox_corners]
            _weapon_cz = (min(_zs) + max(_zs)) / 2.0
            _wpn_sx = max(_xs) - min(_xs)
            _wpn_sy = max(_ys) - min(_ys)
            _wpn_sz = max(_zs) - min(_zs)
            _wpn_vol = _wpn_sx * _wpn_sy * _wpn_sz
            
            _in_head_zone = _weapon_cz >= _head_zone_z
            
            _sorted_dims = sorted([_wpn_sx, _wpn_sy, _wpn_sz], reverse=True)
            _aspect_ratio = _sorted_dims[0] / _sorted_dims[2] if _sorted_dims[2] > 0 else 999
            _is_vertical = _wpn_sz > _wpn_sx * 1.2 and _wpn_sz > _wpn_sy * 1.2
            _is_elongated = _aspect_ratio > 3.0
            
            _is_headgear = False
            if _in_head_zone:
                if _wpn_vol > 1.0:
                    _is_headgear = False
                elif _is_vertical and _wpn_vol <= 0.6:
                    _is_headgear = True
                elif _wpn_vol <= 0.5 and _wpn_sz > 0.5:
                    _is_headgear = True
            
            if _is_headgear:
                _hat_parts.append(_mesh_obj)
                print(">>> [v14-WEAPON] " + _mesh_obj.name + " is headgear (in head zone, small volume), skip moving")
                print(">>>   size: X=" + str(round(_wpn_sx,3)) + ", Y=" + str(round(_wpn_sy,3)) + ", Z=" + str(round(_wpn_sz,3)) + ", vol=" + str(round(_wpn_vol,3)))
            else:
                _real_weapons.append(_mesh_obj)
                print(">>> [v14-WEAPON] " + _mesh_obj.name + " is real weapon, will position")
                print(">>>   size: X=" + str(round(_wpn_sx,3)) + ", Y=" + str(round(_wpn_sy,3)) + ", Z=" + str(round(_wpn_sz,3)) + ", vol=" + str(round(_wpn_vol,3)) + ", elongated=" + str(_is_elongated))
        except Exception:
            _real_weapons.append(_mesh_obj)

    _weapon_parts = _real_weapons

if _weapon_parts and not _v12_no_reposition:
    print(">>> [v8-WEAPON] Found " + str(len(_weapon_parts)) + " weapon parts to position")

    _all_body_verts = []
    try:
        for _mesh_obj in mesh_objects:
            _name_lower = _mesh_obj.name.lower()
            if 'weapon' in _name_lower:
                continue
            # v13根因修复: 排除腿部部件 — 该模型姿态中大腿在60%高度比手臂更靠左,
            # 导致Z-slice误把腿当成手(leg leftmost X=-0.596 vs arm X=-0.129)
            if 'leg' in _name_lower:
                continue
            if _mesh_obj.data and _mesh_obj.data.vertices:
                for _v in _mesh_obj.data.vertices:
                    _v_world = _mesh_obj.matrix_world @ _v.co
                    _all_body_verts.append(_v_world)
    except Exception:
        pass

    _z_min = _bc[2] - _model_h * 0.5
    _z_max = _bc[2] + _model_h * 0.5

    if _all_body_verts:
        _zs_all = [v.z for v in _all_body_verts]
        _z_min = min(_zs_all)
        _z_max = max(_zs_all)
        _model_h = _z_max - _z_min
        _model_bottom_z = _z_min
        _model_top_z = _z_max

    _num_slices = 50
    _slice_h = (_z_max - _z_min) / _num_slices
    _width_profile = []

    if _all_body_verts:
        for _i in range(_num_slices):
            _z_low = _z_min + _i * _slice_h
            _z_high = _z_low + _slice_h
            _z_mid = _z_low + _slice_h / 2
            _z_pct = (_z_mid - _z_min) / _model_h * 100 if _model_h > 0 else 0

            _slice_verts = [v for v in _all_body_verts if _z_low <= v.z < _z_high]
            if len(_slice_verts) >= 5:
                _sxs = [v.x for v in _slice_verts]
                _sys = [v.y for v in _slice_verts]
                _width = max(_sxs) - min(_sxs)
                _right_x = max(_sxs)
                _left_x = min(_sxs)
                _avg_y = sum(_sys) / len(_sys)
                _width_profile.append({
                    'z_mid': _z_mid, 'z_pct': _z_pct, 'width': _width,
                    'right_x': _right_x, 'left_x': _left_x, 'avg_y': _avg_y,
                    'num_verts': len(_slice_verts)
                })

    _right_hand_x = _bc[0] - _model_w * 0.30
    _right_hand_z = _z_min + _model_h * 0.60
    _right_hand_y = _bc[1] - _model_d * 0.22

    _hand_found_via_slice = False

    if _width_profile:
        _torso_slices = [w for w in _width_profile if 50 <= w['z_pct'] <= 65]

        if _torso_slices:
            _widest_slice = min(_torso_slices, key=lambda w: w['left_x'])

            print(">>> [v8-WEAPON] Torso reference at Z=" + str(round(_widest_slice['z_pct'], 1)) + "%:")
            print(">>>   width=" + str(round(_widest_slice['width'], 3)) +
                  ", right_x=" + str(round(_widest_slice['right_x'], 3)) +
                  ", left_x=" + str(round(_widest_slice['left_x'], 3)) +
                  ", avg_y=" + str(round(_widest_slice['avg_y'], 3)))

            _arm_protrusion = _widest_slice['width'] * 0.18

            _right_hand_x = _widest_slice['left_x'] - _arm_protrusion
            _right_hand_z = _widest_slice['z_mid'] + _model_h * 0.10
            _right_hand_y = _widest_slice['avg_y'] - _model_d * 0.10

            _hand_found_via_slice = True

            print(">>> [v14-WEAPON] Right hand estimated via Z-slice analysis:")
            print(">>>   X=" + str(round(_right_hand_x, 3)) +
                  ", Y=" + str(round(_right_hand_y, 3)) +
                  ", Z=" + str(round(_right_hand_z, 3)))

    if not _hand_found_via_slice:
        print(">>> [v8-WEAPON] Using fallback estimation for right hand position")

    # v13修复: 网格顶点手部检测 — 仅在Z-slice失败时作为回退
    # 根因: 主体mesh(Body_High)不含手臂顶点, 取X最小5%会得到躯干边缘而非手部
    # 策略: Z-slice分析基于全体部件宽度曲线, 更可靠; 网格检测仅作回退
    try:
        _hand_mesh_found = False
        if not _hand_found_via_slice and _body_parts:
            # 只有Z-slice失败时才用网格检测
            _main_body = max([o for o in _body_parts if o.type == 'MESH'],
                            key=lambda o: len(o.data.vertices), default=None)
            if _main_body and len(_main_body.data.vertices) > 0:
                _mw = _main_body.matrix_world
                _all_verts = [(_mw @ _v.co) for _v in _main_body.data.vertices]
                _all_zs = [v[2] for v in _all_verts]
                _mesh_z_min = min(_all_zs)
                _mesh_z_max = max(_all_zs)
                _mesh_h = _mesh_z_max - _mesh_z_min
                _arm_z_low = _mesh_z_min + _mesh_h * 0.40
                _arm_z_high = _mesh_z_min + _mesh_h * 0.55
                _arm_verts = [v for v in _all_verts if _arm_z_low <= v[2] <= _arm_z_high]
                if len(_arm_verts) >= 10:
                    _arm_verts_sorted = sorted(_arm_verts, key=lambda v: v[0])
                    _hand_count = max(int(len(_arm_verts_sorted) * 0.05), 10)
                    _hand_verts = _arm_verts_sorted[:_hand_count]
                    _hand_center_x = sum(_v[0] for _v in _hand_verts) / len(_hand_verts)
                    _hand_center_y = sum(_v[1] for _v in _hand_verts) / len(_hand_verts)
                    _hand_center_z = sum(_v[2] for _v in _hand_verts) / len(_hand_verts)
                    _right_hand_x = _hand_center_x
                    _right_hand_y = _hand_center_y
                    _right_hand_z = _hand_center_z
                    _hand_mesh_found = True
                    print(">>> [v13-WEAPON] Hand from mesh fallback (" + str(len(_hand_verts)) + " verts):")
                    print(">>>   X=" + str(round(_right_hand_x, 3)) + ", Y=" + str(round(_right_hand_y, 3)) + ", Z=" + str(round(_right_hand_z, 3)))
        elif _hand_found_via_slice:
            print(">>> [v13-WEAPON] Using Z-slice hand position (authoritative): X=" + str(round(_right_hand_x, 3)) + ", Y=" + str(round(_right_hand_y, 3)) + ", Z=" + str(round(_right_hand_z, 3)))
        if not _hand_mesh_found and not _hand_found_via_slice:
            print(">>> [v13-WEAPON] Using fallback estimation")
    except Exception as _e_hand_detect:
        print(">>> [v13-WEAPON] Hand detection error: " + str(_e_hand_detect))

    _fan_handle = None
    _fan_blade = None

    for _mesh_obj in _weapon_parts:
        try:
            _bbox_corners = [_mesh_obj.matrix_world @ _WeaponVec(v) for v in _mesh_obj.bound_box]
            _xs = [c[0] for c in _bbox_corners]
            _ys = [c[1] for c in _bbox_corners]
            _zs = [c[2] for c in _bbox_corners]
            _sx = max(_xs) - min(_xs)
            _sy = max(_ys) - min(_ys)
            _sz = max(_zs) - min(_zs)
            _vol = _sx * _sy * _sz

            print(">>> [v8-WEAPON] " + _mesh_obj.name + " size: " +
                  "X=" + str(round(_sx, 3)) +
                  ", Y=" + str(round(_sy, 3)) +
                  ", Z=" + str(round(_sz, 3)) +
                  ", vol~=" + str(round(_vol, 3)))

            if _fan_handle is None or _vol < (_fan_handle[1] if _fan_handle else float('inf')):
                if _fan_blade and _vol < _fan_blade[1]:
                    _fan_handle = (_mesh_obj, _vol)
                elif not _fan_blade:
                    _fan_handle = (_mesh_obj, _vol)
            if _fan_blade is None or _vol > (_fan_blade[1] if _fan_blade else 0):
                _fan_blade = (_mesh_obj, _vol)
        except Exception as _e_wpn:
            print(">>> [v8-WEAPON] " + _mesh_obj.name + " analysis error: " + str(_e_wpn))

    if len(_weapon_parts) == 1:
        _fan_handle = (_weapon_parts[0], 1.0)
        _fan_blade = None

    print(">>> [v8-WEAPON] Fan parts identified:")
    print(">>>   handle: " + (_fan_handle[0].name if _fan_handle else "None"))
    print(">>>   blade: " + (_fan_blade[0].name if _fan_blade else "None"))

    if _fan_handle:
        _handle_obj = _fan_handle[0]
        try:
            # === v15 修复：优化旋转角度，更自然的握持姿态 ===
            # 根因：之前角度扇面朝内穿过身体
            # 正确姿态：扇柄在右手，扇面朝外（远离身体方向）展开
            _rot_x = _wpn_math.radians(15)
            _rot_y = _wpn_math.radians(20)
            _rot_z = _wpn_math.radians(-25)
            _handle_obj.rotation_euler = _WeaponEuler((_rot_x, _rot_y, _rot_z), 'XYZ')
            bpy.context.view_layer.update()
            print(">>> [v14-WEAPON] Fan handle rotated FIRST (in place):")
            print(">>>   rot=(X" + str(round(_wpn_math.degrees(_rot_x), 0)) +
                  ", Y" + str(round(_wpn_math.degrees(_rot_y), 0)) +
                  ", Z" + str(round(_wpn_math.degrees(_rot_z), 0)) + ")")

            # 步骤2: 计算旋转后握点的真实世界坐标
            # 知识库: 握点 = 柄的 min-X 端 (手部握持端)
            # bound_box 始终为局部空间，通过 matrix_world 变换得到旋转后的精确位置
            _local_bbox = [(v[0], v[1], v[2]) for v in _handle_obj.bound_box]
            _lxs = [v[0] for v in _local_bbox]
            _lys = [v[1] for v in _local_bbox]
            _lzs = [v[2] for v in _local_bbox]
            # 握点 = 柄根部（min-X端，原始状态靠近身体侧）
            _grip_local = _WeaponVec((min(_lxs), (min(_lys)+max(_lys))/2.0, (min(_lzs)+max(_lzs))/2.0))
            _grip_world = _handle_obj.matrix_world @ _grip_local

            # 步骤3: 移动扇柄使握点对准手位置
            _shift_x = _right_hand_x - _grip_world[0]
            _shift_y = _right_hand_y - _grip_world[1]
            _shift_z = _right_hand_z - _grip_world[2]
            _handle_obj.location.x += _shift_x
            _handle_obj.location.y += _shift_y
            _handle_obj.location.z += _shift_z
            bpy.context.view_layer.update()

            print(">>> [v9-WEAPON] Fan handle grip aligned to hand:")
            print(">>>   grip_world=(" + str(round(_grip_world[0], 2)) + ", " + str(round(_grip_world[1], 2)) + ", " + str(round(_grip_world[2], 2)) + ")")
            print(">>>   shift=(X" + str(round(_shift_x, 2)) + ", Y" + str(round(_shift_y, 2)) + ", Z" + str(round(_shift_z, 2)) + ")")

        except Exception as _e_wpn:
            print(">>> [v9-WEAPON] Fan handle placement error: " + str(_e_wpn))

    if _fan_blade and _fan_handle:
        _blade_obj = _fan_blade[0]
        _handle_obj = _fan_handle[0]
        try:
            # === v12修复: 先旋转blade→再对齐 (v9先对齐后旋转导致偏移) ===
            # 步骤1: 先旋转blade与handle一致 (绕blade原点旋转)
            _blade_obj.rotation_euler = _handle_obj.rotation_euler.copy()
            bpy.context.view_layer.update()

            # 步骤2: 计算旋转后的handle tip和blade attach点
            # 知识库: handle tip = max-X端 (扇面连接端, 远离手部)
            _h_local = [(v[0], v[1], v[2]) for v in _handle_obj.bound_box]
            _hlxs = [v[0] for v in _h_local]
            _hlys = [v[1] for v in _h_local]
            _hlzs = [v[2] for v in _h_local]
            _tip_local = _WeaponVec((max(_hlxs), (min(_hlys)+max(_hlys))/2.0, (min(_hlzs)+max(_hlzs))/2.0))
            _tip_world = _handle_obj.matrix_world @ _tip_local

            # 扇面连接点 = blade的 min-X端 (靠近柄尖的一端)
            _b_local = [(v[0], v[1], v[2]) for v in _blade_obj.bound_box]
            _blxs = [v[0] for v in _b_local]
            _blys = [v[1] for v in _b_local]
            _blzs = [v[2] for v in _b_local]
            _attach_local = _WeaponVec((min(_blxs), (min(_blys)+max(_blys))/2.0, (min(_blzs)+max(_blzs))/2.0))
            _attach_world = _blade_obj.matrix_world @ _attach_local

            # 步骤3: 移动blade使连接点对准handle tip
            _shift_x = _tip_world[0] - _attach_world[0]
            _shift_y = _tip_world[1] - _attach_world[1]
            _shift_z = _tip_world[2] - _attach_world[2]
            _blade_obj.location.x += _shift_x
            _blade_obj.location.y += _shift_y
            _blade_obj.location.z += _shift_z
            bpy.context.view_layer.update()

            print(">>> [v12-WEAPON] Blade aligned (rotate-first):")
            print(">>>   tip=(" + str(round(_tip_world[0],2)) + "," + str(round(_tip_world[1],2)) + "," + str(round(_tip_world[2],2)) + ")")
            print(">>>   shift=(" + str(round(_shift_x,2)) + "," + str(round(_shift_y,2)) + "," + str(round(_shift_z,2)) + ")")

            # Parent组装
            _blade_obj.parent = _handle_obj
            _blade_obj.matrix_parent_inverse = _handle_obj.matrix_world.inverted()
            bpy.context.view_layer.update()
            print(">>> [v12-WEAPON] Blade parented to handle")

        except Exception as _e_wpn:
            print(">>> [v12-WEAPON] Blade alignment error: " + str(_e_wpn))

    for _mesh_obj in _weapon_parts:
        if _fan_handle and _mesh_obj == _fan_handle[0]:
            continue
        if _fan_blade and _mesh_obj == _fan_blade[0]:
            continue
        try:
            _bbox_corners = [_mesh_obj.matrix_world @ _WeaponVec(v) for v in _mesh_obj.bound_box]
            _xs = [c[0] for c in _bbox_corners]
            _ys = [c[1] for c in _bbox_corners]
            _zs = [c[2] for c in _bbox_corners]
            _weapon_cx = (min(_xs) + max(_xs)) / 2.0
            _weapon_cy = (min(_ys) + max(_ys)) / 2.0
            _weapon_cz = (min(_zs) + max(_zs)) / 2.0

            _shift_x = _right_hand_x - _weapon_cx
            _shift_y = _right_hand_y - _weapon_cy
            _shift_z = _right_hand_z - _weapon_cz

            _mesh_obj.location.x += _shift_x
            _mesh_obj.location.y += _shift_y
            _mesh_obj.location.z += _shift_z

            bpy.context.view_layer.update()

            print(">>> [v8-WEAPON] " + _mesh_obj.name + " moved to right hand (simple)")
        except Exception as _e_wpn:
            print(">>> [v8-WEAPON] " + _mesh_obj.name + " error: " + str(_e_wpn))

# === v12: 武器固定 — v9已用网格顶点位置对齐, 此处仅做简单parent保持位置 ===
# 根因总结: 骨骼位置不可靠(auto-weight失败→骨骼≠网格), 改用网格顶点找手
# v12策略: 不重新定位, 仅parent到armature对象(不绑骨骼), 保持v9的位置
try:
    if _v10_armature is not None and _fan_handle is not None:
        _wpn_handle_obj = _fan_handle[0]
        bpy.context.view_layer.update()

        # 清除已有parent/约束
        if _wpn_handle_obj.parent is not None:
            _wpn_handle_obj.parent = None
        _wpn_handle_obj.constraints.clear()
        bpy.context.view_layer.update()

        # 简单object parent到armature (不绑定具体骨骼, 不改变位置)
        _wpn_handle_obj.parent = _v10_armature
        _wpn_handle_obj.matrix_parent_inverse = _v10_armature.matrix_world.inverted()
        bpy.context.view_layer.update()

        print(">>> [v12-WEAPON] Fan '" + _wpn_handle_obj.name + "' parented to armature (position from mesh vertices)")
        print(">>>   fan_loc=(" + str(round(_wpn_handle_obj.location[0],2)) + ", " + str(round(_wpn_handle_obj.location[1],2)) + ", " + str(round(_wpn_handle_obj.location[2],2)) + ")")

        if _fan_blade:
            print(">>> [v12-WEAPON] Blade '" + _fan_blade[0].name + "' inherits via handle parent")
    else:
        if _v10_armature is None:
            print(">>> [v12-WEAPON] Skipped: no armature")
        elif _fan_handle is None:
            print(">>> [v12-WEAPON] Skipped: no fan handle")
except NameError as _ne_v12:
    print(">>> [v12-WEAPON] Skipped: " + str(_ne_v12))
except Exception as _e_v12_wpn:
    print(">>> [v12-WEAPON] ERROR: " + str(_e_v12_wpn))
    import traceback as _tb_v12w
    _tb_v12w.print_exc()


# === v15-SAFETY: 武器归位最终校验（经验汲取安全网） ===
# 历史教训:
#   1. v15 旋转后 bbox 膨胀导致扇面飞到 X≈-5.6（画面外）
#   2. v13 发冠归位参考mesh选错导致物体移到胸部
#   3. 多次"看起来对但实际错"的假象
# 对策: 归位完成后校验所有武器部件是否在合理范围内, 越界则告警
try:
    _safe_cx, _safe_cy, _safe_cz = bounds_center[0], bounds_center[1], bounds_center[2]
    _safe_sx, _safe_sy, _safe_sz = bounds_size[0], bounds_size[1], bounds_size[2]
    # 放宽到模型尺寸的1.5倍, 因为武器在手伸展时自然会超出身体范围
    _safe_limit = max(_safe_sx, _safe_sy, _safe_sz) * 1.5

    for _safe_obj in mesh_objects:
        _safe_nl = _safe_obj.name.lower()
        if 'weapon' not in _safe_nl:
            continue
        try:
            _safe_corners = [_safe_obj.matrix_world @ _WeaponVec(v) for v in _safe_obj.bound_box]
            _safe_wcx = (min(c[0] for c in _safe_corners) + max(c[0] for c in _safe_corners)) / 2.0
            _safe_wcy = (min(c[1] for c in _safe_corners) + max(c[1] for c in _safe_corners)) / 2.0
            _safe_wcz = (min(c[2] for c in _safe_corners) + max(c[2] for c in _safe_corners)) / 2.0
            _safe_dist = ((_safe_wcx - _safe_cx)**2 + (_safe_wcy - _safe_cy)**2 + (_safe_wcz - _safe_cz)**2) ** 0.5

            if _safe_dist > _safe_limit:
                print(">>> [SAFETY] WARNING: " + _safe_obj.name + " is far from model center!")
                print(">>>   center=(" + str(round(_safe_wcx, 2)) + ", " + str(round(_safe_wcy, 2)) + ", " + str(round(_safe_wcz, 2)) + ")")
                print(">>>   distance=" + str(round(_safe_dist, 2)) + " (limit=" + str(round(_safe_limit, 2)) + ")")
            else:
                print(">>> [SAFETY] " + _safe_obj.name + " OK (dist=" + str(round(_safe_dist, 2)) + " < " + str(round(_safe_limit, 2)) + ")")
        except Exception:
            pass
except Exception as _e_safety:
    print(">>> [SAFETY] Check error: " + str(_e_safety))


# ---------------------------------------------------------------------------
# 5. 渐变背景（避免空洞）
# ---------------------------------------------------------------------------
if not FILM_TRANSPARENT:
    try:
        # 创建背景平面
        bg_size = max(bounds_size) * 6
        ground_z = min_co[2] if 'min_co' in dir() else (bounds_center[2] - bounds_size[2] * 0.5)
        bpy.ops.mesh.primitive_plane_add(size=bg_size, location=(0, 0, ground_z))
        bg_plane = bpy.context.active_object
        bg_plane.name = "BackgroundPlane"

        # 渐变材质
        bg_mat = bpy.data.materials.new(name="BackgroundGradient")
        bg_mat.use_nodes = True
        bg_tree = bg_mat.node_tree
        bg_nodes = bg_tree.nodes
        bg_links = bg_tree.links

        for n in list(bg_nodes):
            bg_nodes.remove(n)

        bg_output = bg_nodes.new(type='ShaderNodeOutputMaterial')
        bg_output.location = (400, 0)

        bg_emission = bg_nodes.new(type='ShaderNodeEmission')
        bg_emission.location = (200, 0)
        bg_emission.inputs['Strength'].default_value = 1.0

        # 渐变纹理
        bg_ramp = bg_nodes.new(type='ShaderNodeValToRGB')
        bg_ramp.location = (-100, 0)
        bg_ramp.color_ramp.interpolation = 'LINEAR'
        bg_ramp.color_ramp.elements[0].position = 0.0
        bg_ramp.color_ramp.elements[0].color = safe_eval_color(BACKGROUND_BOTTOM)
        bg_ramp.color_ramp.elements[1].position = 1.0
        bg_ramp.color_ramp.elements[1].color = safe_eval_color(BACKGROUND_TOP)

        # 渐变方向（从下到上）
        bg_tex_coord = bg_nodes.new(type='ShaderNodeTexCoord')
        bg_tex_coord.location = (-400, 0)

        bg_mapping = bg_nodes.new(type='ShaderNodeMapping')
        bg_mapping.location = (-250, 0)
        bg_links.new(bg_tex_coord.outputs['Generated'], bg_mapping.inputs['Vector'])

        bg_links.new(bg_mapping.outputs['Vector'], bg_ramp.inputs[0])
        bg_links.new(bg_ramp.outputs[0], bg_emission.inputs['Color'])
        bg_links.new(bg_emission.outputs[0], bg_output.inputs['Surface'])

        bg_plane.data.materials.append(bg_mat)
        # v6 修复：使用 Z（高度）而不是 Y（厚度），否则背景平面会挡住模型下半身
        # 原代码 -bounds_size[1] * 0.5 把平面放在 z=-0.945，正好挡住 z<-0.945 的腿部
        # 修复后用 Z 尺寸，平面位于 z=-2.96（模型底部之下），且加 0.5 米安全距离
        bg_plane.location.z = -bounds_size[2] * 0.5 - 0.5
        print(">>> [BG-v6] Background plane Z=" + str(bg_plane.location.z) + " (using Z size=" + str(bounds_size[2]) + ")")

        # 背景不参与投影
        bg_plane.hide_render = False
        bg_plane.is_shadow_catcher = False

        print("Background created with gradient")
    except Exception as e:
        print("Background creation failed: " + str(e))


# ---------------------------------------------------------------------------
# 6. Freestyle 轮廓线（v2 - 双层线条）
# ---------------------------------------------------------------------------
if USE_FREESTYLE:
    try:
        scene.render.use_freestyle = True
        view_layer = scene.view_layers[0]
        freestyle = view_layer.freestyle_settings
        freestyle.use_smoothness = True
        freestyle.use_culling = True
        freestyle.as_render_pass = True
        freestyle.sphere_radius = 1.0
        freestyle.kr_derivative_epsilon = 0.1

        # 清空旧 linesets
        while freestyle.linesets:
            freestyle.linesets.remove(freestyle.linesets[0])

        # === 第一层：外轮廓线（粗） ===
        outer_style = bpy.data.linestyles.new("OuterContour")
        outer_style.color = safe_eval_color(OUTLINE_COLOR)[:3]
        outer_style.thickness = OUTLINE_THICKNESS
        outer_style.thickness_position = 'OUTSIDE'

        outer_set = freestyle.linesets.new("OuterContour")
        outer_set.select_silhouette = True
        outer_set.select_border = True
        outer_set.select_external_contour = True
        outer_set.select_crease = False
        outer_set.select_edge_mark = False
        outer_set.select_material_boundary = True
        outer_set.select_by_collection = False
        outer_set.linestyle = outer_style

        # === 第二层：内部结构线（细）===
        if USE_INNER_LINES:
            inner_style = bpy.data.linestyles.new("InnerStructure")
            inner_color = safe_eval_color(OUTLINE_COLOR)
            # 内部线略浅一点
            inner_style.color = (inner_color[0] * 0.6, inner_color[1] * 0.6, inner_color[2] * 0.6)
            inner_style.thickness = INNER_LINE_THICKNESS
            inner_style.thickness_position = 'OUTSIDE'

            inner_set = freestyle.linesets.new("InnerStructure")
            inner_set.select_silhouette = False
            inner_set.select_border = False
            inner_set.select_external_contour = False
            inner_set.select_crease = True
            inner_set.select_edge_mark = True
            inner_set.select_material_boundary = True
            inner_set.select_by_visibility = False
            inner_set.linestyle = inner_style

        print("Freestyle configured: outer=" + str(OUTLINE_THICKNESS) + ", inner=" + str(INNER_LINE_THICKNESS))
    except Exception as e:
        print("Freestyle init failed: " + str(e) + ", using no outline")
        scene.render.use_freestyle = False
else:
    scene.render.use_freestyle = False


# ---------------------------------------------------------------------------
# 7. 灯光设置（v2 - HDRI + 顶部柔光 + 三点布光）
# ---------------------------------------------------------------------------
# 主光（Key）
bpy.ops.object.light_add(type='AREA', location=(4.5, -5.5, 6.5))
key_light_obj = bpy.context.active_object
key_light_obj.name = "Key_Light"
key_light_obj.data.type = 'AREA'
key_light_obj.data.energy = KEY_LIGHT["energy"]
key_light_obj.data.size = KEY_LIGHT["size"]
key_light_obj.data.color = safe_eval_color(KEY_LIGHT["color"])[:3]
key_light_obj.data.shadow_soft_size = 0.5
key_light_obj.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))

# 补光（Fill）
bpy.ops.object.light_add(type='AREA', location=(-5.5, -3.5, 4.5))
fill_light_obj = bpy.context.active_object
fill_light_obj.name = "Fill_Light"
fill_light_obj.data.type = 'AREA'
fill_light_obj.data.energy = FILL_LIGHT["energy"]
fill_light_obj.data.size = FILL_LIGHT["size"]
fill_light_obj.data.color = safe_eval_color(FILL_LIGHT["color"])[:3]
fill_light_obj.data.shadow_soft_size = 0.8
fill_light_obj.rotation_euler = (math.radians(50), math.radians(-20), math.radians(-30))

# 轮廓光（Rim - 从后方照射）
bpy.ops.object.light_add(type='AREA', location=(0, 5, 5.5))
rim_light_obj = bpy.context.active_object
rim_light_obj.name = "Rim_Light"
rim_light_obj.data.type = 'AREA'
rim_light_obj.data.energy = RIM_LIGHT["energy"]
rim_light_obj.data.size = RIM_LIGHT["size"]
rim_light_obj.data.color = safe_eval_color(RIM_LIGHT["color"])[:3]
rim_light_obj.data.shadow_soft_size = 0.3
rim_light_obj.rotation_euler = (math.radians(-30), 0, math.radians(180))

# 顶部柔光（Top - 提升顶部高光）
bpy.ops.object.light_add(type='AREA', location=(0, 0, 8))
top_light_obj = bpy.context.active_object
top_light_obj.name = "Top_Light"
top_light_obj.data.type = 'AREA'
top_light_obj.data.energy = TOP_LIGHT["energy"]
top_light_obj.data.size = TOP_LIGHT["size"]
top_light_obj.data.color = safe_eval_color(TOP_LIGHT["color"])[:3]
top_light_obj.data.shadow_soft_size = 0.1
top_light_obj.rotation_euler = (0, 0, 0)

# === v3: 底部反光板 (Bounce) - 填充底部阴影,增强立体感 ===
# 模拟地面反光,让角色底部不那么死黑
try:
    bpy.ops.object.light_add(type='AREA', location=(0, 0, -2))
    bounce_light_obj = bpy.context.active_object
    bounce_light_obj.name = "Bounce_Light"
    bounce_light_obj.data.type = 'AREA'
    bounce_light_obj.data.energy = 250
    bounce_light_obj.data.size = 10.0
    bounce_light_obj.data.color = (0.85, 0.9, 0.95)  # 冷色调反光
    bounce_light_obj.data.shadow_soft_size = 1.5
    bounce_light_obj.rotation_euler = (math.radians(90), 0, 0)
    print(">>> v3: Bounce light added")
except Exception as e_bounce:
    print(">>> v3: Bounce light skipped: " + str(e_bounce))

# === v3: 冷暖色温对比 (Key warm + Fill cool) ===
# 主光偏暖(偏橙),补光偏冷(偏蓝),营造电影感
try:
    key_light_obj.data.color = tuple(min(1.0, c * 0.9 + 0.1) for c in key_light_obj.data.color)
    key_light_obj.data.color = (key_light_obj.data.color[0], key_light_obj.data.color[1] * 0.9, key_light_obj.data.color[2] * 0.85)
    fill_light_obj.data.color = (fill_light_obj.data.color[0] * 0.9, fill_light_obj.data.color[1] * 0.95, fill_light_obj.data.color[2])
    print(">>> v3: Color temp contrast applied")
except Exception as e_color:
    print(">>> v3: Color temp skipped: " + str(e_color))

# 环境光（世界设置 - Blender 5.x 兼容）
# 策略: 优先用节点链接,失败则设置 world.color 作为后备
_env_color = (0.5, 0.5, 0.55)
try:
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("CelWorld")
        scene.world = world
    # 后备: 直接设置 world.color (即使节点失败也有环境光)
    try:
        world.color = _env_color
    except Exception:
        pass
    try:
        world.use_nodes = True
    except AttributeError:
        pass

    w_tree = None
    try:
        w_tree = world.node_tree
    except Exception:
        pass

    if w_tree is not None:
        w_nodes = w_tree.nodes
        w_links = w_tree.links
        for n in list(w_nodes):
            w_nodes.remove(n)

        bg_node = w_nodes.new(type='ShaderNodeBackground')
        bg_node.location = (0, 0)
        try:
            bg_node.inputs['Color'].default_value = (_env_color[0], _env_color[1], _env_color[2], 1.0)
            bg_node.inputs['Strength'].default_value = 0.3  # 弱环境光，不抢主光
        except Exception:
            pass

        world_output = w_nodes.new(type='ShaderNodeOutputWorld')
        world_output.location = (300, 0)

        # 遍历 world_output.inputs 找到第一个可用的 Color/Shader 输入
        # 5.x 中输入名为 'Surface', 旧版为 'Background'
        link_done = False
        try:
            bg_out = bg_node.outputs[0]
        except Exception:
            bg_out = None
        if bg_out is not None:
            for inp in world_output.inputs:
                try:
                    w_links.new(bg_out, inp)
                    link_done = True
                    break
                except Exception:
                    continue
        # 后备: 按具名访问
        if not link_done:
            for nm in ('Surface', 'Background'):
                try:
                    w_links.new(bg_node.outputs[0], world_output.inputs[nm])
                    link_done = True
                    break
                except Exception:
                    continue

        print(">>> World environment: link_done=" + str(link_done))
    else:
        print(">>> World: node_tree unavailable, using world.color fallback")
except Exception as e:
    print(">>> World setup failed: " + str(e) + " | using world.color fallback")


# ---------------------------------------------------------------------------
# 8. 相机设置（v7 - 修复坐标系统，Blender Z轴向上）
# ---------------------------------------------------------------------------
# Blender 标准坐标系：Z=上(高度), Y=前(深度), X=右
# 之前错误地把Y轴当高度轴用，导致相机从脚底往上拍
# 修复：高度使用Z轴，相机在XY平面环绕，目标点在模型几何中心

# 重新计算当前模型边界（确保使用最新的居中后数据）
from mathutils import Vector
min_co = [float('inf')] * 3
max_co = [float('-inf')] * 3
for obj in mesh_objects:
    bbox = obj.bound_box
    for corner in bbox:
        world_corner = obj.matrix_world @ Vector(corner)
        for i in range(3):
            if world_corner[i] < min_co[i]:
                min_co[i] = world_corner[i]
            if world_corner[i] > max_co[i]:
                max_co[i] = world_corner[i]

model_height = max_co[2] - min_co[2]
model_width = max_co[0] - min_co[0]
model_center_z = (max_co[2] + min_co[2]) / 2

# === v9: 相机居中修复 — 目标点X/Y使用非武器部件的bbox中心 ===
# 根因: 武器部件在-X侧延伸, 全局居中后身体视觉中心偏移(约X+1.2), 相机target固定X=0导致人物偏右
try:
    _wpn_set = set(_weapon_parts)
except NameError:
    _wpn_set = set()
_body_min_x, _body_max_x = float('inf'), float('-inf')
_body_min_y, _body_max_y = float('inf'), float('-inf')
for obj in mesh_objects:
    if obj in _wpn_set:
        continue
    for corner in obj.bound_box:
        wc = obj.matrix_world @ Vector(corner)
        if wc[0] < _body_min_x:
            _body_min_x = wc[0]
        if wc[0] > _body_max_x:
            _body_max_x = wc[0]
        if wc[1] < _body_min_y:
            _body_min_y = wc[1]
        if wc[1] > _body_max_y:
            _body_max_y = wc[1]
if _body_max_x > _body_min_x:
    body_center_x = (_body_min_x + _body_max_x) / 2.0
    body_center_y = (_body_min_y + _body_max_y) / 2.0
else:
    body_center_x, body_center_y = 0.0, 0.0
print(">>> [CAMERA-v9] Body-only center: X=" + str(round(body_center_x, 2)) + ", Y=" + str(round(body_center_y, 2)) + " (excl. " + str(len(_wpn_set)) + " weapon parts)")

# v7: 使用 50mm 焦距 + sensor_fit='VERTICAL'
lens_mm = 50
sensor_height = 24
fov_rad = 2 * math.atan(sensor_height / (2 * lens_mm))

# 留 50% 边距，确保头顶脚底都有空间
frame_height = model_height * 1.5
cam_radius = (frame_height / 2) / math.tan(fov_rad / 2)
cam_radius = max(cam_radius, model_height * 3.0)

# v7: 构图优化：目标点上移到身高的65%处
# 头顶留白 + 底部地面，符合人物肖像构图美学
target_z = min_co[2] + model_height * 0.65
cam_height = target_z

print(">>> [CAMERA-v7] Model height(Z)=" + str(model_height) + ", width(X)=" + str(model_width))
print(">>> [CAMERA-v7] Vertical FOV=" + str(math.degrees(fov_rad)) + "deg (sensor_fit=VERTICAL)")
print(">>> [CAMERA-v7] cam_radius=" + str(cam_radius) + ", cam_height(Z)=" + str(cam_height))
print(">>> [CAMERA-v7] Model top(Z)=" + str(max_co[2]) + ", bottom(Z)=" + str(min_co[2]) + ", center_z=" + str(model_center_z))
frame_top = target_z + cam_radius * math.tan(fov_rad / 2)
frame_bottom = target_z - cam_radius * math.tan(fov_rad / 2)
print(">>> [CAMERA-v7] Frame top(Z)=" + str(frame_top) + " (model top=" + str(max_co[2]) + ", fit=" + str(frame_top > max_co[2]) + ")")
print(">>> [CAMERA-v7] Frame bottom(Z)=" + str(frame_bottom) + " (model bottom=" + str(min_co[2]) + ", fit=" + str(frame_bottom < min_co[2]) + ")")

bpy.ops.object.camera_add(location=(body_center_x, body_center_y - cam_radius, cam_height))
cam = bpy.context.active_object
cam.name = "CelCamera"
cam.data.lens = lens_mm
cam.data.sensor_width = 36
cam.data.sensor_height = sensor_height
try:
    cam.data.sensor_fit = 'VERTICAL'
    print(">>> [CAMERA-v7] sensor_fit set to VERTICAL")
except Exception as e_fit:
    print(">>> [CAMERA-v7] sensor_fit set failed: " + str(e_fit))

# 景深设置
if USE_DOF:
    try:
        cam.data.dof.use_dof = True
        cam.data.dof.focus_distance = cam_radius * 0.95
        cam.data.dof.aperture_fstop = 2.8
        cam.data.dof.aperture_blades = 8
        cam.data.dof.aperture_ratio = 1.1
        cam.data.dof.aperture_rotation = 0
        print(">>> v7: DoF (f/2.8, focus on center)")
    except Exception as e:
        print("DoF setup failed: " + str(e))

scene.camera = cam

# v9: 相机目标点位于身体几何中心（排除武器部件）
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(body_center_x, body_center_y, target_z))
focus = bpy.context.active_object
focus.name = "CameraTarget"
print(">>> [CAMERA-v7] Target Z=" + str(target_z) + " (model center)")
cam_constraint = cam.constraints.new(type='TRACK_TO')
cam_constraint.target = focus
cam_constraint.track_axis = 'TRACK_NEGATIVE_Z'
cam_constraint.up_axis = 'UP_Y'

# v7-debug: 打印相机实际参数和真实可视范围
try:
    bpy.context.view_layer.update()
    cam_actual_angle = cam.data.angle
    cam_actual_fov_deg = math.degrees(cam_actual_angle)
    actual_frame_h = 2 * cam_radius * math.tan(cam_actual_angle / 2)
    print(">>> [CAMERA-DEBUG] cam.data.lens=" + str(cam.data.lens))
    print(">>> [CAMERA-DEBUG] cam.data.sensor_width=" + str(cam.data.sensor_width))
    print(">>> [CAMERA-DEBUG] cam.data.sensor_height=" + str(cam.data.sensor_height))
    print(">>> [CAMERA-DEBUG] cam.data.sensor_fit=" + str(cam.data.sensor_fit))
    print(">>> [CAMERA-DEBUG] cam.data.angle=" + str(cam_actual_angle) + " rad = " + str(cam_actual_fov_deg) + " deg")
    print(">>> [CAMERA-DEBUG] actual vertical frame at cam_radius=" + str(cam_radius) + " = " + str(actual_frame_h) + " m (need " + str(model_height) + " m)")
    print(">>> [CAMERA-DEBUG] actual frame top(Z)=" + str(target_z + actual_frame_h/2) + ", bottom(Z)=" + str(target_z - actual_frame_h/2))
    print(">>> [CAMERA-DEBUG] render resolution=" + str(scene.render.resolution_x) + "x" + str(scene.render.resolution_y))
    print(">>> [CAMERA-DEBUG] aspect ratio=" + str(scene.render.resolution_x / scene.render.resolution_y))
except Exception as e_dbg:
    print(">>> [CAMERA-DEBUG] error: " + str(e_dbg))

# v3: 轻微镜头畸变
try:
    cam.data.lens_unit = 'MILLIMETERS'
    cam.data.distortion = 0.02
    print(">>> v7: Slight lens distortion (0.02)")
except Exception as e_dist:
    print(">>> v7: Lens distortion skipped: " + str(e_dist))

# === v11: 角色idle动画(多频率正弦叠加 + 自然过渡) ===
# 改进: 更自然的呼吸/摆动/头转/手臂, 兼容Blender 5.1 API
try:
    if _v10_armature is not None:
        _scene = bpy.context.scene
        _f_start = FRAME_START
        _f_end = FRAME_END
        _total_f = _f_end - _f_start + 1

        bpy.ops.object.select_all(action='DESELECT')
        _v10_armature.select_set(True)
        bpy.context.view_layer.objects.active = _v10_armature
        bpy.ops.object.mode_set(mode='POSE')

        _pb = _v10_armature.pose.bones

        def _key_v11(pbone, frame, rot=None, loc=None):
            if rot is not None:
                pbone.rotation_euler = rot
                pbone.keyframe_insert(data_path="rotation_euler", frame=frame)
            if loc is not None:
                pbone.location = loc
                pbone.keyframe_insert(data_path="location", frame=frame)

        # v11: 多频率叠加产生自然感
        # 主呼吸周期 = 全部帧数, 摆动周期 = 0.7x, 头转周期 = 1.3x
        _pi2 = 2 * _v10_math.pi

        # 关键帧间隔: 每5帧一个关键姿态(Blender自动Bezier插值)
        _key_interval = 5
        _key_frames = list(range(_f_start, _f_end + 1, _key_interval))
        if _key_frames[-1] != _f_end:
            _key_frames.append(_f_end)

        for _f in _key_frames:
            _t = (_f - _f_start) / max(_total_f - 1, 1)  # 0~1
            _angle = _pi2 * _t

            # 呼吸: 主频 + 次频叠加 (Spine X轴微俯仰)
            _breath = (_v10_math.sin(_angle) * 1.2 +
                       _v10_math.sin(_angle * 2.0 + 0.3) * 0.4) * _v10_math.radians(1.0)
            if 'Spine' in _pb:
                _rot = list(_pb['Spine'].rotation_euler)
                _rot[0] = _breath
                _key_v11(_pb['Spine'], _f, rot=_rot)

            # 胸部微动 (Chest 与 Spine 略有相位差)
            if 'Chest' in _pb:
                _chest_breath = _v10_math.sin(_angle + 0.4) * _v10_math.radians(0.8)
                _rot = list(_pb['Chest'].rotation_euler)
                _rot[0] = _chest_breath
                _key_v11(_pb['Chest'], _f, rot=_rot)

            # 身体轻摆: Hips绕Z轴 + 微小平移(重心移动)
            _sway = _v10_math.sin(_angle * 0.7) * _v10_math.radians(1.8)
            _hip_shift = _v10_math.sin(_angle * 0.7 + 0.2) * 0.03  # 微小X平移
            if 'Hips' in _pb:
                _rot = list(_pb['Hips'].rotation_euler)
                _rot[2] = _sway
                _loc = list(_pb['Hips'].location)
                _loc[0] = _hip_shift
                _key_v11(_pb['Hips'], _f, rot=_rot, loc=_loc)

            # 头部: 偏航(yaw) + 俯仰(pitch) 多频率
            _head_yaw = (_v10_math.sin(_angle * 1.3 + 0.5) * 3.5 +
                         _v10_math.sin(_angle * 0.5) * 1.5) * _v10_math.radians(1.0)
            _head_pitch = _v10_math.sin(_angle * 0.8 + 0.2) * _v10_math.radians(1.5)
            _head_tilt = _v10_math.sin(_angle * 0.6) * _v10_math.radians(1.0)
            if 'Head' in _pb:
                _rot = list(_pb['Head'].rotation_euler)
                _rot[0] = _head_pitch
                _rot[1] = _head_tilt
                _rot[2] = _v10_math.radians(5) + _head_yaw
                _key_v11(_pb['Head'], _f, rot=_rot)

            # 颈部微动 (与头部反向, 增加自然感)
            if 'Neck' in _pb:
                _neck_yaw = _v10_math.sin(_angle * 1.3 + 0.5) * _v10_math.radians(-1.0)
                _rot = list(_pb['Neck'].rotation_euler)
                _rot[2] = _neck_yaw
                _key_v11(_pb['Neck'], _f, rot=_rot)

            # 手臂: 右臂微摆 + 左臂反向 (不同频率避免机械感)
            _arm_r = (_v10_math.sin(_angle * 1.1) * 2.5 +
                      _v10_math.sin(_angle * 0.6 + 1.0) * 1.0) * _v10_math.radians(1.0)
            _arm_l = (_v10_math.sin(_angle * 0.9 + 0.8) * 2.0 +
                      _v10_math.sin(_angle * 1.4) * 0.8) * _v10_math.radians(1.0)
            if 'UpperArm_R' in _pb:
                _rot = list(_pb['UpperArm_R'].rotation_euler)
                _rot[1] = -_v10_math.radians(35) + _arm_r
                _key_v11(_pb['UpperArm_R'], _f, rot=_rot)
            if 'UpperArm_L' in _pb:
                _rot = list(_pb['UpperArm_L'].rotation_euler)
                _rot[1] = -_v10_math.radians(35) - _arm_l
                _key_v11(_pb['UpperArm_L'], _f, rot=_rot)

            # 前臂微动
            _forearm_r = _v10_math.sin(_angle * 1.5 + 0.3) * _v10_math.radians(2.0)
            if 'ForeArm_R' in _pb:
                _rot = list(_pb['ForeArm_R'].rotation_euler)
                _rot[1] = -_v10_math.radians(15) + _forearm_r
                _key_v11(_pb['ForeArm_R'], _f, rot=_rot)
            if 'ForeArm_L' in _pb:
                _rot = list(_pb['ForeArm_L'].rotation_euler)
                _rot[1] = -_v10_math.radians(15) - _forearm_r * 0.7
                _key_v11(_pb['ForeArm_L'], _f, rot=_rot)

        # 尝试设置插值模式 (Blender 5.1可能不支持fcurves访问, 非关键)
        try:
            if _v10_armature.animation_data and _v10_armature.animation_data.action:
                _action = _v10_armature.animation_data.action
                # Blender 5.1: 尝试新API (slotted actions)
                if hasattr(_action, 'fcurves'):
                    for _fc in _action.fcurves:
                        for _kp in _fc.keyframe_points:
                            _kp.interpolation = 'SINE'
                            _kp.easing = 'EASE_IN_OUT'
                else:
                    # Blender 5.1+: 通过layers/slots访问
                    for _layer in getattr(_action, 'layers', []):
                        for _strip in getattr(_layer, 'strips', []):
                            for _fc in getattr(_strip, 'fcurves', []):
                                for _kp in _fc.keyframe_points:
                                    _kp.interpolation = 'SINE'
                                    _kp.easing = 'EASE_IN_OUT'
        except Exception as _e_interp:
            print(">>> [v11-ANIM] Interpolation setting skipped (non-critical): " + str(_e_interp))

        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.context.view_layer.update()
        print(">>> [v11-ANIM] Idle animation: " + str(len(_key_frames)) + " key poses over " + str(_total_f) + " frames")
        print(">>>   Multi-freq: breath(1x+2x) + sway(0.7x) + head(1.3x+0.5x) + arms(1.1x+0.6x)")
    else:
        print(">>> [v11-ANIM] Skipped: no armature")
except Exception as _e_anim:
    print(">>> [v11-ANIM] Error: " + str(_e_anim))
    import traceback as _tb_anim
    _tb_anim.print_exc()
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        pass

# === 相机环绕动画（v7: XY平面环绕 + 上下浮动 + 手持微晃） ===
total_frames = FRAME_END - FRAME_START + 1

handheld_amplitude = cam_radius * 0.008
handheld_freq_x = 12.0
handheld_freq_y = 8.0
handheld_freq_z = 6.0

for frame_num in range(FRAME_START, FRAME_END + 1):
    progress = (frame_num - FRAME_START) / max(total_frames - 1, 1)
    angle = 2 * math.pi * progress
    float_amplitude = model_height * 0.02
    z_offset = math.sin(angle * 2) * float_amplitude

    hx = (math.sin(angle * handheld_freq_x) + math.sin(angle * handheld_freq_x * 1.7)) * handheld_amplitude
    hy = (math.cos(angle * handheld_freq_y) + math.cos(angle * handheld_freq_y * 2.3)) * handheld_amplitude * 0.7
    hz = (math.sin(angle * handheld_freq_z) + math.cos(angle * handheld_freq_z * 1.5)) * handheld_amplitude * 0.5

    x = body_center_x + math.sin(angle) * cam_radius + hx
    y = body_center_y - math.cos(angle) * cam_radius + hy
    z = cam_height + z_offset + hz

    cam.location = (x, y, z)
    set_keyframe_linear(cam, "location", frame_num, (x, y, z))

print(">>> v7: Camera orbit animation (XY plane) + float + handheld shake")

# v6-debug: 动画后检查相机第一帧实际状态
try:
    bpy.context.view_layer.update()
    scene.frame_set(FRAME_START)
    bpy.context.view_layer.update()
    print(">>> [CAMERA-ANIM-DEBUG] Frame " + str(FRAME_START) + " camera state:")
    print("    location=" + str([cam.location[i] for i in range(3)]))
    print("    rotation_euler=" + str([math.degrees(cam.rotation_euler[i]) for i in range(3)]))
    print("    matrix_world col[3]=" + str([cam.matrix_world[i][3] for i in range(3)]))
    # 检查约束
    for c in cam.constraints:
        print("    constraint: " + c.type + " target=" + (c.target.name if c.target else "None"))
    # 计算相机正前方方向（-Z 轴在世界坐标的方向）
    forward = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    print("    forward (-Z world)=" + str([forward[i] for i in range(3)]))
    print("    up (Y world)=" + str([up[i] for i in range(3)]))
    # 从相机到目标的向量
    to_target = Vector((focus.location[0] - cam.location[0], focus.location[1] - cam.location[1], focus.location[2] - cam.location[2]))
    print("    direction to target=" + str([to_target[i] for i in range(3)]))
    print("    forward . to_target=" + str(forward.dot(to_target.normalized())))

    # v6-debug: 列出每个 mesh 物体的实际 Z 范围和可见性
    print(">>> [MESH-DEBUG] Each mesh object state at frame " + str(FRAME_START) + ":")
    for i, obj in enumerate(mesh_objects):
        try:
            bbox = obj.bound_box
            corners = [obj.matrix_world @ Vector(v) for v in bbox]
            zs = [c[2] for c in corners]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            z_min, z_max = min(zs), max(zs)
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            visible = obj.visible_get()
            in_camera_frame = (z_max > frame_bottom) and (z_min < frame_top)
            print("    [" + str(i) + "] " + obj.name[:40])
            print("        bound_box Z: " + str(round(z_min, 2)) + " ~ " + str(round(z_max, 2)) + " (size=" + str(round(z_max - z_min, 2)) + ")")
            print("        bound_box X: " + str(round(x_min, 2)) + " ~ " + str(round(x_max, 2)))
            print("        bound_box Y: " + str(round(y_min, 2)) + " ~ " + str(round(y_max, 2)))
            print("        visible=" + str(visible) + ", in_camera_z_range=" + str(in_camera_frame))
            # 关键：直接遍历实际顶点，检查 mesh 真实几何范围
            try:
                mesh = obj.data
                if mesh and len(mesh.vertices) > 0:
                    real_zs = []
                    real_xs = []
                    real_ys = []
                    sample_step = max(1, len(mesh.vertices) // 200)  # 采样最多 200 个顶点
                    for vi in range(0, len(mesh.vertices), sample_step):
                        v = mesh.vertices[vi].co
                        # 应用 matrix_world 转换到世界坐标
                        world_v = obj.matrix_world @ Vector(v)
                        real_zs.append(world_v[2])
                        real_xs.append(world_v[0])
                        real_ys.append(world_v[1])
                    if real_zs:
                        rz_min, rz_max = min(real_zs), max(real_zs)
                        rx_min, rx_max = min(real_xs), max(real_xs)
                        ry_min, ry_max = min(real_ys), max(real_ys)
                        print("        REAL_VERT Z: " + str(round(rz_min, 2)) + " ~ " + str(round(rz_max, 2)) + " (sampled " + str(len(real_zs)) + "/" + str(len(mesh.vertices)) + " verts)")
                        print("        REAL_VERT X: " + str(round(rx_min, 2)) + " ~ " + str(round(rx_max, 2)))
                        print("        REAL_VERT Y: " + str(round(ry_min, 2)) + " ~ " + str(round(ry_max, 2)))
                        # 比对 bound_box 和真实顶点
                        if abs(rz_min - z_min) > 0.1 or abs(rz_max - z_max) > 0.1:
                            print("        *** WARNING: bound_box 与真实顶点不一致！")
            except Exception as e_verts:
                print("        REAL_VERT error: " + str(e_verts))
        except Exception as e_mesh:
            print("    [" + str(i) + "] " + obj.name + " error: " + str(e_mesh))
except Exception as e_anim_dbg:
    print(">>> [CAMERA-ANIM-DEBUG] error: " + str(e_anim_dbg))


# ---------------------------------------------------------------------------
# 9. 渲染输出设置
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(RENDER_OUTPUT), exist_ok=True)
scene.render.filepath = RENDER_OUTPUT

# 后处理节点（Blender 5.x: 用 Group Output 替代已移除的 Composite 节点 + Glare Bloom）
# 5.0 变化: Composite 节点被移除,改用 NodeGroupOutput (首个输入需为 Color)
#           scene.node_tree 被移除,改用 scene.compositing_node_group
comp_tree = None
try:
    scene.use_nodes = True
except Exception:
    pass

# 创建 CompositorNodeTree 数据块
try:
    comp_tree = bpy.data.node_groups.new("CelCompositor", 'CompositorNodeTree')
except Exception as e_create:
    print(">>> CompositorNodeTree create failed: " + str(e_create))
    comp_tree = None

# 关联到 scene (5.x: compositing_node_group, 旧版: node_tree)
if comp_tree is not None:
    linked = False
    for attr in ('compositing_node_group', 'node_tree'):
        if hasattr(scene, attr):
            try:
                setattr(scene, attr, comp_tree)
                linked = True
                print(">>> Compositor linked via scene." + attr)
                break
            except Exception as e_link:
                print(">>> Compositor link via " + attr + " failed: " + str(e_link))
    if not linked:
        print(">>> Compositor: no scene link attribute available, post-processing disabled")
        comp_tree = None

if comp_tree is not None:
    try:
        comp_nodes = comp_tree.nodes
        comp_links = comp_tree.links

        # 清空默认节点
        for n in list(comp_nodes):
            comp_nodes.remove(n)

        # 渲染层
        rl_node = comp_nodes.new(type='CompositorNodeRLayers')
        rl_node.location = (0, 0)

        # 色相/饱和度微调 (5.x: 用 inputs)
        hue_node = comp_nodes.new(type='CompositorNodeHueSat')
        hue_node.location = (300, 0)
        try:
            hue_node.inputs['Hue'].default_value = HUE_SHIFT + 0.5
            hue_node.inputs['Saturation'].default_value = SATURATION
            hue_node.inputs['Value'].default_value = VALUE_MULT
        except Exception as e_hue:
            try:
                hue_node.hue = HUE_SHIFT
                hue_node.sat = SATURATION
                hue_node.val = VALUE_MULT
            except Exception:
                print(">>> HueSat setup skipped: " + str(e_hue))

        comp_links.new(rl_node.outputs['Image'], hue_node.inputs['Image'])

        # Bloom 效果 (5.x: EEVEE use_bloom 已移除,用 Glare 节点 Fog Glow)
        last_color_source = hue_node.outputs['Image']
        if USE_BLOOM:
            try:
                glare_node = comp_nodes.new(type='CompositorNodeGlare')
                glare_node.location = (600, 0)
                # 5.x: glare_type/quality 可能改为 inputs 或属性名变化,用多重 fallback
                # FOG_GLOW 枚举索引通常是 2, BLOOM 是 0
                _glare_type_set = False
                for _attr, _val in (('glare_type', 'FOG_GLOW'), ('glare_type', 2)):
                    try:
                        setattr(glare_node, _attr, _val)
                        _glare_type_set = True
                        break
                    except Exception:
                        continue
                if not _glare_type_set:
                    # 5.x: 选项作为 inputs 暴露
                    for _inp_name, _inp_val in (('Glare Type', 2), ('glare_type', 2)):
                        try:
                            glare_node.inputs[_inp_name].default_value = _inp_val
                            _glare_type_set = True
                            break
                        except Exception:
                            continue
                # quality (HIGH=2)
                try:
                    glare_node.quality = 'HIGH'
                except Exception:
                    try:
                        glare_node.inputs['Quality'].default_value = 2
                    except Exception:
                        pass
                try:
                    glare_node.inputs['Mix'].default_value = 0.0
                except Exception:
                    pass
                try:
                    glare_node.inputs['Threshold'].default_value = 0.8
                except Exception:
                    pass
                try:
                    glare_node.size = 6
                except Exception:
                    pass
                # 链接
                comp_links.new(hue_node.outputs['Image'], glare_node.inputs['Image'])
                last_color_source = glare_node.outputs['Image']
                print(">>> Glare (Bloom) configured: glare_type_set=" + str(_glare_type_set) + ", threshold=0.8")
            except Exception as e_glare:
                print(">>> Glare setup failed: " + str(e_glare) + " | bloom disabled")

        # === v3: 暗角效果 (Vignette) - 增强电影感 ===
        try:
            vignette_node = comp_nodes.new(type='CompositorNodeVignette')
            vignette_node.location = (750, 0)
            try:
                vignette_node.inputs['Amount'].default_value = 0.12
                vignette_node.inputs['Radius'].default_value = 0.85
                vignette_node.inputs['Feather'].default_value = 0.5
            except Exception:
                try:
                    vignette_node.amount = 0.12
                    vignette_node.radius = 0.85
                    vignette_node.feather = 0.5
                except Exception:
                    pass
            comp_links.new(last_color_source, vignette_node.inputs['Image'])
            last_color_source = vignette_node.outputs['Image']
            print(">>> v3: Vignette added (amount=0.12)")
        except Exception as e_vignette:
            print(">>> v3: Vignette skipped: " + str(e_vignette))

        # === v3: RGB 曲线微调 (提升对比度) ===
        try:
            curve_node = comp_nodes.new(type='CompositorNodeCurveRGB')
            curve_node.location = (850, 0)
            try:
                crv = curve_node.mapping.curves[0]
                crv.points[0].location = (0.0, 0.0)
                crv.points[1].location = (0.5, 0.52)
                crv.points[2].location = (1.0, 1.0)
                crv.interpolation = 'BEZIER'
            except Exception:
                pass
            comp_links.new(last_color_source, curve_node.inputs['Image'])
            last_color_source = curve_node.outputs['Image']
            print(">>> v3: RGB curve contrast enhancement")
        except Exception as e_curve:
            print(">>> v3: RGB curve skipped: " + str(e_curve))

        # 5.x: 用 NodeGroupOutput 替代已移除的 Composite 节点
        # 首个输入必须是 Color socket
        out_node = None
        for nt_type in ('NodeGroupOutput', 'CompositorNodeComposite'):
            try:
                out_node = comp_nodes.new(type=nt_type)
                out_node.location = (1100, 0)
                print(">>> Output node: " + nt_type)
                break
            except Exception:
                continue

        if out_node is not None:
            # 链接到第一个输入
            linked_out = False
            for inp in out_node.inputs:
                try:
                    comp_links.new(last_color_source, inp)
                    linked_out = True
                    break
                except Exception:
                    continue
            if not linked_out:
                try:
                    comp_links.new(last_color_source, out_node.inputs[0])
                    linked_out = True
                except Exception as e_link_out:
                    print(">>> Output link failed: " + str(e_link_out))

        # Freestyle 轮廓线叠加
        if USE_FREESTYLE and 'Freestyle' in rl_node.outputs:
            try:
                freestyle_mix = comp_nodes.new(type='CompositorNodeAlphaOver')
                freestyle_mix.location = (950, -250)
                comp_links.new(last_color_source, freestyle_mix.inputs[1])
                comp_links.new(rl_node.outputs['Freestyle'], freestyle_mix.inputs[2])
                # 替换输出链接
                if out_node is not None:
                    for link in list(comp_links):
                        if link.to_node == out_node:
                            comp_links.remove(link)
                    comp_links.new(freestyle_mix.outputs[0], out_node.inputs[0])
                print(">>> Freestyle overlay configured in compositor")
            except Exception as e_fs:
                print(">>> Freestyle overlay failed: " + str(e_fs))

        print(">>> v3: Compositor post-processing configured")
    except Exception as e:
        print(">>> Compositor node setup failed: " + str(e))
        try:
            scene.use_nodes = False
        except Exception:
            pass
else:
    # Compositor 不可用: 让 EEVEE 直接渲染到 PNG
    # 色相已在材质中处理, AO 已通过材质节点实现, 仅缺 Bloom
    print(">>> Compositor unavailable: EEVEE direct render (AO via material, Bloom skipped)")
    try:
        scene.use_nodes = False
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 10. 渲染动画
# ---------------------------------------------------------------------------
# v11 状态摘要(确保出现在stdout尾部)
try:
    print(">>> [v11-SUMMARY] armature=" + str(_v10_armature is not None) +
          ", hand_r=" + str(_v10_hand_r_world is not None) +
          ", crown=" + str(_crown_part.name if _crown_part else 'None'))
    if _v10_armature:
        print(">>> [v11-SUMMARY] bones=" + str(len(_v10_armature.data.bones)) +
              ", action=" + str(_v10_armature.animation_data.action.name if _v10_armature.animation_data and _v10_armature.animation_data.action else 'None'))
    # v11: 检查Child Of约束状态
    try:
        if _crown_part:
            _crown_cons = [c.name for c in _crown_part.constraints if c.type == 'CHILD_OF']
            print(">>> [v11-SUMMARY] crown_constraints=" + str(_crown_cons))
    except Exception:
        pass
    try:
        if _fan_handle:
            _wpn_cons = [c.name for c in _fan_handle[0].constraints if c.type == 'CHILD_OF']
            print(">>> [v11-SUMMARY] weapon_constraints=" + str(_wpn_cons))
    except Exception:
        pass
    if not _v10_armature:
        print(">>> [v11-SUMMARY] Armature disabled (rollback: no bone deformation)")
except NameError as _ne:
    print(">>> [v11-SUMMARY] not initialized: " + str(_ne))

print("=" * 60)
print("Starting render...")
print("Frames: " + str(FRAME_START) + " - " + str(FRAME_END))
print("Resolution: " + str(RESOLUTION_X) + "x" + str(RESOLUTION_Y))
print("Samples: " + str(RENDER_SAMPLES))
print("=" * 60)

bpy.ops.render.render(animation=True, write_still=False)
print("Render completed.")


# ---------------------------------------------------------------------------
# 11. 保存 .blend
# ---------------------------------------------------------------------------
if BLEND_OUTPUT:
    os.makedirs(os.path.dirname(BLEND_OUTPUT), exist_ok=True)
    bpy.ops.wm.save_mainfile(filepath=BLEND_OUTPUT)
    print("Blend saved: " + BLEND_OUTPUT)


# ---------------------------------------------------------------------------
# 12. 可选 FBX 导出
# ---------------------------------------------------------------------------
if EXPORT_FBX and FBX_OUTPUT:
    os.makedirs(os.path.dirname(FBX_OUTPUT), exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=FBX_OUTPUT,
        use_selection=False,
        bake_anim=True,
        apply_unit_scale=True,
        axis_forward='-Z',
        axis_up='Y',
    )
    print("FBX exported: " + FBX_OUTPUT)


# ---------------------------------------------------------------------------
# 13. 写标记文件
# ---------------------------------------------------------------------------
with open(MARKER_PATH, "w") as f:
    f.write("SUCCESS\\n")
    f.write("style: " + STYLE_NAME + "\\n")
    f.write("render: " + RENDER_OUTPUT + "\\n")
    if BLEND_OUTPUT:
        f.write("blend: " + BLEND_OUTPUT + "\\n")
    if EXPORT_FBX:
        f.write("fbx: " + FBX_OUTPUT + "\\n")
    f.write("version: v2_optimized\\n")

print("Marker written. Done.")
'''
