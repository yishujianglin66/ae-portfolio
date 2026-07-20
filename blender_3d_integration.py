#!/usr/bin/env python3
"""
Blender 3D 场景集成模块 v1.0
==============================

通过 Python API (bpy) 和命令行接口集成 Blender，支持 3D 场景生成、
材质、灯光、摄像机、动画、渲染等功能，提供真实模式、模拟模式和自动降级模式。

安装路径: C:\Program Files\Blender Foundation\Blender 4.x
CLI 命令: blender --python script.py

支持的功能:
- scene_generation : 3D 场景生成（物体/灯光/摄像机）
- material_setup   : 材质与纹理设置
- lighting_setup   : 灯光布置（三点布光、舞台灯光等）
- animation        : 关键帧动画
- rendering        : 静帧渲染 / 动画渲染

执行模式:
- real    : 通过 blender --python 真实执行（需要安装 Blender）
- simulate: 模拟执行，生成模拟结果（用于测试和流程验证）
- auto    : 优先真实模式，失败自动降级到模拟模式
"""
import os
import sys
import json
import time
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

DEFAULT_BLENDER_HOME = Path(r"C:\Program Files\Blender Foundation\Blender 4.2")
BLENDER_HOME = Path(os.environ.get("BLENDER_HOME", str(DEFAULT_BLENDER_HOME)))

BLENDER_CLI_CANDIDATES = [
    BLENDER_HOME / "blender.exe",
    BLENDER_HOME / "blender-launcher.exe",
]

OUTPUT_BASE = Path(os.environ.get("AE_WORK_DIR", r"D:\AE-Work"))

RENDER_ENGINES = ["eevee", "cycles", "workbench"]
OUTPUT_FORMATS = ["PNG", "JPEG", "OPEN_EXR", "FFmpeg_video"]
VIDEO_CODECS = ["H264", "MPEG4"]


@dataclass
class BlenderConfig:
    """Blender 配置数据类。

    Attributes:
        install_path: Blender 安装路径
        mode: 运行模式（real/simulate/auto）
        output_dir: 输出目录
        engine: 渲染引擎（eevee / cycles / workbench）
        resolution_x: 分辨率宽度
        resolution_y: 分辨率高度
        fps: 帧率
        samples: 渲染采样数（cycles 用）
        output_format: 输出格式（PNG / JPEG / OPEN_EXR / FFmpeg_video）
        video_codec: 视频编码（H264 / MPEG4）
        use_gpu: 是否使用 GPU 渲染
        denoise: 是否降噪
    """
    install_path: str = str(BLENDER_HOME)
    mode: str = "auto"
    output_dir: str = str(OUTPUT_BASE / "blender_output")
    engine: str = "eevee"
    resolution_x: int = 1920
    resolution_y: int = 1080
    fps: int = 24
    samples: int = 128
    output_format: str = "PNG"
    video_codec: str = "H264"
    use_gpu: bool = False
    denoise: bool = True


@dataclass
class BlenderSceneResult:
    """Blender 场景生成结果数据类。

    Attributes:
        success: 是否成功
        blend_file: .blend 工程文件路径
        output_path: 渲染输出路径（视频或序列帧目录）
        duration: 处理耗时（秒）
        object_count: 物体数量
        light_count: 灯光数量
        camera_count: 摄像机数量
        frame_range: 帧范围 (start, end)
        error: 错误信息（如果失败）
        mode: 实际使用的执行模式
    """
    success: bool = False
    blend_file: str = ""
    output_path: str = ""
    duration: float = 0.0
    object_count: int = 0
    light_count: int = 0
    camera_count: int = 0
    frame_range: Tuple[int, int] = (1, 1)
    error: Optional[str] = None
    mode: str = "simulate"


@dataclass
class Scene3DConfig:
    """3D 场景配置数据类。

    Attributes:
        scene_type: 场景类型
        background_color: 背景色 (R, G, B, A)
        objects: 物体列表（type/name/location/rotation/scale/material）
        lights: 灯光列表（type/name/location/energy/color）
        cameras: 摄像机列表（name/location/rotation/lens/fov）
        animations: 动画列表（object_name/property/keyframes）
    """
    scene_type: str = "empty"
    background_color: Tuple[float, float, float, float] = (0.1, 0.1, 0.1, 1.0)
    objects: List[Dict[str, Any]] = field(default_factory=list)
    lights: List[Dict[str, Any]] = field(default_factory=list)
    cameras: List[Dict[str, Any]] = field(default_factory=list)
    animations: List[Dict[str, Any]] = field(default_factory=list)


BLENDER_SCENE_PRESETS: Dict[str, Scene3DConfig] = {
    "puppet_stage_wooden": Scene3DConfig(
        scene_type="puppet_stage",
        background_color=(0.05, 0.05, 0.08, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "stage_floor",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (5, 4, 1),
                "material": {"type": "wood", "color": (0.6, 0.4, 0.2, 1.0)},
            },
            {
                "type": "plane",
                "name": "back_curtain",
                "location": (0, -3.5, 2.5),
                "rotation": (1.5708, 0, 0),
                "scale": (5, 1, 3),
                "material": {"type": "fabric", "color": (0.8, 0.2, 0.2, 1.0)},
            },
            {
                "type": "cube",
                "name": "top_beam",
                "location": (0, -2, 5),
                "rotation": (0, 0, 0),
                "scale": (5.5, 0.2, 0.3),
                "material": {"type": "wood", "color": (0.4, 0.25, 0.1, 1.0)},
            },
            {
                "type": "plane",
                "name": "shadow_catcher",
                "location": (0, 0, 0.01),
                "rotation": (0, 0, 0),
                "scale": (8, 6, 1),
                "material": {"type": "shadow_only", "color": (0, 0, 0, 1.0)},
            },
        ],
        lights=[
            {
                "type": "SPOT",
                "name": "main_spotlight",
                "location": (0, -1, 4.5),
                "energy": 1000,
                "color": (1.0, 0.95, 0.85, 1.0),
                "spot_size": 1.0,
            },
            {
                "type": "AREA",
                "name": "fill_left",
                "location": (-3, -1, 2.5),
                "energy": 200,
                "color": (0.9, 0.9, 1.0, 1.0),
            },
            {
                "type": "AREA",
                "name": "fill_right",
                "location": (3, -1, 2.5),
                "energy": 200,
                "color": (0.9, 0.9, 1.0, 1.0),
            },
        ],
        cameras=[
            {
                "name": "front_medium",
                "location": (0, 6, 2.5),
                "rotation": (1.309, 0, 3.1416),
                "lens": 50,
                "fov": 39.6,
            },
            {
                "name": "side_closeup",
                "location": (-4, 2, 2),
                "rotation": (1.309, 0, 2.3562),
                "lens": 85,
                "fov": 23.9,
            },
        ],
        animations=[],
    ),
    "puppet_stage_theater": Scene3DConfig(
        scene_type="puppet_stage",
        background_color=(0.02, 0.02, 0.05, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "stage_floor",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (6, 5, 1),
                "material": {"type": "wood_polished", "color": (0.5, 0.35, 0.2, 1.0)},
            },
            {
                "type": "plane",
                "name": "main_curtain",
                "location": (0, -4, 3),
                "rotation": (1.5708, 0, 0),
                "scale": (6.5, 1, 4),
                "material": {"type": "velvet", "color": (0.7, 0.1, 0.1, 1.0)},
            },
            {
                "type": "cube",
                "name": "proscenium_top",
                "location": (0, -4.2, 5.2),
                "rotation": (0, 0, 0),
                "scale": (7, 0.3, 0.5),
                "material": {"type": "gold", "color": (0.9, 0.75, 0.2, 1.0)},
            },
            {
                "type": "cube",
                "name": "proscenium_left",
                "location": (-3.5, -4.2, 2.5),
                "rotation": (0, 0, 0),
                "scale": (0.3, 0.3, 3),
                "material": {"type": "gold", "color": (0.9, 0.75, 0.2, 1.0)},
            },
            {
                "type": "cube",
                "name": "proscenium_right",
                "location": (3.5, -4.2, 2.5),
                "rotation": (0, 0, 0),
                "scale": (0.3, 0.3, 3),
                "material": {"type": "gold", "color": (0.9, 0.75, 0.2, 1.0)},
            },
            {
                "type": "plane",
                "name": "audience_silhouette",
                "location": (0, 5, 0.5),
                "rotation": (0, 0, 0),
                "scale": (8, 1, 1.5),
                "material": {"type": "silhouette", "color": (0.05, 0.05, 0.08, 1.0)},
            },
        ],
        lights=[
            {
                "type": "SPOT",
                "name": "follow_spot",
                "location": (0, -2, 6),
                "energy": 1500,
                "color": (1.0, 0.98, 0.9, 1.0),
                "spot_size": 0.8,
            },
            {
                "type": "AREA",
                "name": "stage_left",
                "location": (-4, -2, 3),
                "energy": 300,
                "color": (1.0, 0.9, 0.8, 1.0),
            },
            {
                "type": "AREA",
                "name": "stage_right",
                "location": (4, -2, 3),
                "energy": 300,
                "color": (1.0, 0.9, 0.8, 1.0),
            },
            {
                "type": "POINT",
                "name": "audience_glow",
                "location": (0, 6, 1),
                "energy": 50,
                "color": (0.3, 0.3, 0.4, 1.0),
            },
        ],
        cameras=[
            {
                "name": "audience_view",
                "location": (0, 7, 2.5),
                "rotation": (1.309, 0, 3.1416),
                "lens": 35,
                "fov": 54.4,
            },
            {
                "name": "closeup_center",
                "location": (0, 3, 1.8),
                "rotation": (1.2, 0, 3.1416),
                "lens": 100,
                "fov": 20.4,
            },
        ],
        animations=[],
    ),
    "miniature_room": Scene3DConfig(
        scene_type="miniature",
        background_color=(0.9, 0.85, 0.75, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "floor",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (6, 6, 1),
                "material": {"type": "wood_floor", "color": (0.7, 0.55, 0.4, 1.0)},
            },
            {
                "type": "plane",
                "name": "back_wall",
                "location": (0, -4, 2.5),
                "rotation": (1.5708, 0, 0),
                "scale": (6, 1, 3),
                "material": {"type": "wall_paint", "color": (0.95, 0.9, 0.8, 1.0)},
            },
            {
                "type": "plane",
                "name": "window",
                "location": (0, -3.9, 3),
                "rotation": (1.5708, 0, 0),
                "scale": (2, 1, 1.5),
                "material": {"type": "glass", "color": (0.7, 0.85, 1.0, 0.3)},
            },
            {
                "type": "cube",
                "name": "table",
                "location": (-1.5, -1, 0.5),
                "rotation": (0, 0, 0),
                "scale": (1.2, 0.8, 0.1),
                "material": {"type": "wood", "color": (0.5, 0.35, 0.2, 1.0)},
            },
            {
                "type": "cube",
                "name": "chair",
                "location": (-1.5, 0, 0.7),
                "rotation": (0, 0, 0),
                "scale": (0.5, 0.5, 0.8),
                "material": {"type": "wood", "color": (0.45, 0.3, 0.15, 1.0)},
            },
            {
                "type": "cube",
                "name": "bookshelf",
                "location": (2.5, -3.5, 1.5),
                "rotation": (0, 0, 0),
                "scale": (0.8, 0.4, 2),
                "material": {"type": "wood_dark", "color": (0.3, 0.2, 0.1, 1.0)},
            },
        ],
        lights=[
            {
                "type": "AREA",
                "name": "window_light",
                "location": (0, -3.5, 3),
                "energy": 800,
                "color": (0.9, 0.95, 1.0, 1.0),
            },
            {
                "type": "POINT",
                "name": "lamp",
                "location": (-1.5, -1, 1.2),
                "energy": 100,
                "color": (1.0, 0.9, 0.7, 1.0),
            },
            {
                "type": "SUN",
                "name": "sun_light",
                "location": (5, -5, 8),
                "energy": 500,
                "color": (1.0, 0.95, 0.85, 1.0),
            },
        ],
        cameras=[
            {
                "name": "room_overview",
                "location": (2, 4, 2.5),
                "rotation": (1.2, 0, 2.618),
                "lens": 28,
                "fov": 65.5,
            },
            {
                "name": "table_closeup",
                "location": (-1, 1, 1),
                "rotation": (1.0, 0, 2.356),
                "lens": 50,
                "fov": 39.6,
            },
        ],
        animations=[],
    ),
    "studio_3point": Scene3DConfig(
        scene_type="studio",
        background_color=(0.15, 0.15, 0.15, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "seamless_floor",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (10, 10, 1),
                "material": {"type": "seamless_white", "color": (0.95, 0.95, 0.95, 1.0)},
            },
            {
                "type": "plane",
                "name": "seamless_backdrop",
                "location": (0, -5, 3),
                "rotation": (1.5708, 0, 0),
                "scale": (10, 1, 6),
                "material": {"type": "seamless_white", "color": (0.95, 0.95, 0.95, 1.0)},
            },
            {
                "type": "plane",
                "name": "softbox_key",
                "location": (-3, -2, 3),
                "rotation": (0, 0.785, 0.3),
                "scale": (1.5, 0.1, 2),
                "material": {"type": "emissive", "color": (1.0, 0.98, 0.9, 1.0)},
            },
            {
                "type": "plane",
                "name": "softbox_fill",
                "location": (3, -1, 2),
                "rotation": (0, -0.785, 0.2),
                "scale": (1, 0.1, 1.5),
                "material": {"type": "emissive_dim", "color": (0.8, 0.85, 1.0, 1.0)},
            },
            {
                "type": "plane",
                "name": "softbox_back",
                "location": (0, -4, 3.5),
                "rotation": (0, 0, 0),
                "scale": (1.2, 0.1, 1.5),
                "material": {"type": "emissive", "color": (1.0, 1.0, 1.0, 1.0)},
            },
            {
                "type": "plane",
                "name": "reflector",
                "location": (0, 2, 1),
                "rotation": (-0.5, 0, 0),
                "scale": (2, 0.05, 1.5),
                "material": {"type": "white_reflector", "color": (0.9, 0.9, 0.9, 1.0)},
            },
        ],
        lights=[
            {
                "type": "AREA",
                "name": "key_light",
                "location": (-3, -2, 3),
                "energy": 1000,
                "color": (1.0, 0.98, 0.9, 1.0),
            },
            {
                "type": "AREA",
                "name": "fill_light",
                "location": (3, -1, 2),
                "energy": 400,
                "color": (0.85, 0.9, 1.0, 1.0),
            },
            {
                "type": "AREA",
                "name": "back_light",
                "location": (0, -4, 3.5),
                "energy": 600,
                "color": (1.0, 1.0, 1.0, 1.0),
            },
        ],
        cameras=[
            {
                "name": "front_view",
                "location": (0, 4, 2),
                "rotation": (1.1, 0, 3.1416),
                "lens": 50,
                "fov": 39.6,
            },
            {
                "name": "portrait",
                "location": (0, 3, 1.5),
                "rotation": (0.9, 0, 3.1416),
                "lens": 85,
                "fov": 23.9,
            },
        ],
        animations=[],
    ),
    "outdoor_garden": Scene3DConfig(
        scene_type="outdoor",
        background_color=(0.5, 0.7, 0.9, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "grass_ground",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (15, 15, 1),
                "material": {"type": "grass", "color": (0.2, 0.5, 0.2, 1.0)},
            },
            {
                "type": "cone",
                "name": "tree_trunk_1",
                "location": (-4, -3, 1),
                "rotation": (0, 0, 0),
                "scale": (0.3, 0.3, 2),
                "material": {"type": "bark", "color": (0.4, 0.25, 0.1, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "tree_foliage_1",
                "location": (-4, -3, 3),
                "rotation": (0, 0, 0),
                "scale": (1.5, 1.5, 1.2),
                "material": {"type": "leaves", "color": (0.15, 0.4, 0.15, 1.0)},
            },
            {
                "type": "cone",
                "name": "tree_trunk_2",
                "location": (5, 2, 0.8),
                "rotation": (0, 0, 0),
                "scale": (0.25, 0.25, 1.6),
                "material": {"type": "bark", "color": (0.4, 0.25, 0.1, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "tree_foliage_2",
                "location": (5, 2, 2.3),
                "rotation": (0, 0, 0),
                "scale": (1.2, 1.2, 1),
                "material": {"type": "leaves", "color": (0.18, 0.45, 0.18, 1.0)},
            },
            {
                "type": "cube",
                "name": "bench",
                "location": (0, -1, 0.3),
                "rotation": (0, 0.3, 0),
                "scale": (1.5, 0.4, 0.1),
                "material": {"type": "wood_weathered", "color": (0.6, 0.5, 0.35, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "bush_1",
                "location": (-2, 2, 0.3),
                "rotation": (0, 0, 0),
                "scale": (0.6, 0.6, 0.5),
                "material": {"type": "bush", "color": (0.2, 0.45, 0.2, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "bush_2",
                "location": (3, -2, 0.25),
                "rotation": (0, 0, 0),
                "scale": (0.5, 0.5, 0.4),
                "material": {"type": "bush", "color": (0.22, 0.48, 0.22, 1.0)},
            },
        ],
        lights=[
            {
                "type": "SUN",
                "name": "sun",
                "location": (10, -10, 15),
                "energy": 2000,
                "color": (1.0, 0.95, 0.8, 1.0),
            },
            {
                "type": "SKY",
                "name": "sky_light",
                "location": (0, 0, 10),
                "energy": 300,
                "color": (0.6, 0.75, 0.95, 1.0),
            },
        ],
        cameras=[
            {
                "name": "wide_shot",
                "location": (0, 8, 2),
                "rotation": (1.2, 0, 3.1416),
                "lens": 24,
                "fov": 73.7,
            },
            {
                "name": "bench_view",
                "location": (2, 3, 1.2),
                "rotation": (1.0, 0, 2.618),
                "lens": 50,
                "fov": 39.6,
            },
        ],
        animations=[],
    ),
    "night_scene": Scene3DConfig(
        scene_type="night",
        background_color=(0.02, 0.02, 0.08, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "ground",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (12, 12, 1),
                "material": {"type": "asphalt", "color": (0.1, 0.1, 0.12, 1.0)},
            },
            {
                "type": "cube",
                "name": "building_1",
                "location": (-4, -3, 2),
                "rotation": (0, 0, 0),
                "scale": (1.5, 1.5, 4),
                "material": {"type": "building_dark", "color": (0.15, 0.15, 0.2, 1.0)},
            },
            {
                "type": "cube",
                "name": "building_2",
                "location": (4, -2, 2.5),
                "rotation": (0, 0, 0),
                "scale": (1.2, 1.2, 5),
                "material": {"type": "building_dark", "color": (0.12, 0.12, 0.18, 1.0)},
            },
            {
                "type": "cube",
                "name": "neon_sign_1",
                "location": (-4, -1.5, 3),
                "rotation": (0, 0, 0),
                "scale": (1, 0.05, 0.5),
                "material": {"type": "neon_pink", "color": (1.0, 0.2, 0.6, 1.0)},
            },
            {
                "type": "cube",
                "name": "neon_sign_2",
                "location": (4, -0.8, 4),
                "rotation": (0, 0, 0),
                "scale": (0.8, 0.05, 0.4),
                "material": {"type": "neon_blue", "color": (0.2, 0.5, 1.0, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "moon",
                "location": (-8, -8, 8),
                "rotation": (0, 0, 0),
                "scale": (1, 1, 1),
                "material": {"type": "moon_surface", "color": (0.9, 0.9, 0.85, 1.0)},
            },
        ],
        lights=[
            {
                "type": "POINT",
                "name": "neon_glow_pink",
                "location": (-4, -1.5, 3),
                "energy": 500,
                "color": (1.0, 0.2, 0.6, 1.0),
            },
            {
                "type": "POINT",
                "name": "neon_glow_blue",
                "location": (4, -0.8, 4),
                "energy": 400,
                "color": (0.2, 0.5, 1.0, 1.0),
            },
            {
                "type": "SUN",
                "name": "moon_light",
                "location": (-8, -8, 8),
                "energy": 50,
                "color": (0.7, 0.8, 1.0, 1.0),
            },
            {
                "type": "AREA",
                "name": "volume_light",
                "location": (0, -2, 4),
                "energy": 100,
                "color": (0.3, 0.3, 0.5, 1.0),
            },
        ],
        cameras=[
            {
                "name": "street_view",
                "location": (0, 6, 1.5),
                "rotation": (1.1, 0, 3.1416),
                "lens": 35,
                "fov": 54.4,
            },
            {
                "name": "neon_closeup",
                "location": (-2.5, 0, 2.5),
                "rotation": (1.3, 0, 2.356),
                "lens": 85,
                "fov": 23.9,
            },
        ],
        animations=[],
    ),
    "abstract_geometric": Scene3DConfig(
        scene_type="abstract",
        background_color=(0.1, 0.05, 0.15, 1.0),
        objects=[
            {
                "type": "cube",
                "name": "cube_center",
                "location": (0, 0, 1.5),
                "rotation": (0.5, 0.5, 0),
                "scale": (1, 1, 1),
                "material": {"type": "glassy", "color": (0.8, 0.3, 0.6, 1.0)},
            },
            {
                "type": "icosphere",
                "name": "sphere_left",
                "location": (-2, -1, 1.2),
                "rotation": (0, 0, 0),
                "scale": (0.7, 0.7, 0.7),
                "material": {"type": "metallic", "color": (0.3, 0.8, 0.9, 1.0)},
            },
            {
                "type": "cone",
                "name": "cone_right",
                "location": (2, 1, 1.5),
                "rotation": (0, 0, 0.3),
                "scale": (0.8, 0.8, 1.2),
                "material": {"type": "glow", "color": (0.9, 0.7, 0.2, 1.0)},
            },
            {
                "type": "torus",
                "name": "torus_back",
                "location": (0, -2.5, 1.8),
                "rotation": (1.0, 0.5, 0),
                "scale": (0.8, 0.8, 0.3),
                "material": {"type": "neon_edge", "color": (0.5, 1.0, 0.5, 1.0)},
            },
            {
                "type": "cylinder",
                "name": "cylinder_front",
                "location": (1, 2, 1),
                "rotation": (0.3, 0, 0.5),
                "scale": (0.5, 0.5, 1),
                "material": {"type": "glass_blue", "color": (0.2, 0.4, 1.0, 0.7)},
            },
            {
                "type": "plane",
                "name": "floor_reflect",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (8, 8, 1),
                "material": {"type": "dark_reflective", "color": (0.05, 0.05, 0.1, 1.0)},
            },
        ],
        lights=[
            {
                "type": "AREA",
                "name": "rim_light_pink",
                "location": (-3, -3, 3),
                "energy": 400,
                "color": (1.0, 0.4, 0.8, 1.0),
            },
            {
                "type": "AREA",
                "name": "rim_light_cyan",
                "location": (3, -3, 3),
                "energy": 400,
                "color": (0.4, 0.8, 1.0, 1.0),
            },
            {
                "type": "POINT",
                "name": "accent_yellow",
                "location": (0, 2, 3),
                "energy": 200,
                "color": (1.0, 0.9, 0.3, 1.0),
            },
        ],
        cameras=[
            {
                "name": "front_angle",
                "location": (0, 5, 2),
                "rotation": (1.1, 0, 3.1416),
                "lens": 50,
                "fov": 39.6,
            },
            {
                "name": "top_angled",
                "location": (2, 3, 4),
                "rotation": (0.785, 0, 2.618),
                "lens": 35,
                "fov": 54.4,
            },
        ],
        animations=[
            {
                "object_name": "cube_center",
                "property": "rotation_euler",
                "keyframes": [
                    {"frame": 1, "value": [0.5, 0.5, 0]},
                    {"frame": 100, "value": [0.5, 0.5, 6.283]},
                ],
            },
            {
                "object_name": "sphere_left",
                "property": "location",
                "keyframes": [
                    {"frame": 1, "value": [-2, -1, 1.2]},
                    {"frame": 50, "value": [-2, -1, 2.0]},
                    {"frame": 100, "value": [-2, -1, 1.2]},
                ],
            },
        ],
    ),
    "empty_studio": Scene3DConfig(
        scene_type="empty_studio",
        background_color=(0.1, 0.1, 0.1, 1.0),
        objects=[
            {
                "type": "plane",
                "name": "ground_plane",
                "location": (0, 0, 0),
                "rotation": (0, 0, 0),
                "scale": (10, 10, 1),
                "material": {"type": "gray_ground", "color": (0.2, 0.2, 0.2, 1.0)},
            },
        ],
        lights=[
            {
                "type": "SUN",
                "name": "main_light",
                "location": (5, -5, 8),
                "energy": 500,
                "color": (1.0, 0.95, 0.85, 1.0),
            },
        ],
        cameras=[
            {
                "name": "main_camera",
                "location": (0, 5, 2),
                "rotation": (1.1, 0, 3.1416),
                "lens": 50,
                "fov": 39.6,
            },
        ],
        animations=[],
    ),
}


class Blender3DIntegrator:
    """Blender 3D 场景集成器。

    封装 Blender 命令行调用，提供 3D 场景生成、材质设置、灯光布置、
    动画、渲染等功能的统一接口。支持真实模式、模拟模式和自动降级模式。
    """

    def __init__(self, config: Optional[BlenderConfig] = None):
        """初始化 Blender3DIntegrator。

        Args:
            config: Blender 配置对象，为 None 时使用默认配置
        """
        self.config = config or BlenderConfig()
        self._blender_path = self._find_blender()
        self._available = self._check_availability()
        print(f"[Blender3DIntegrator] Mode: {self.config.mode}")
        print(f"[Blender3DIntegrator] Blender available: {self._available}")
        print(f"[Blender3DIntegrator] Path: {self._blender_path}")

    def _find_blender(self) -> Optional[Path]:
        """查找 Blender 可执行文件。

        Returns:
            Blender 可执行文件路径，找不到返回 None
        """
        install_path = Path(self.config.install_path)
        candidates = [
            install_path / "blender.exe",
            install_path / "blender-launcher.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        if install_path.parent.exists():
            for subdir in install_path.parent.iterdir():
                if subdir.is_dir() and "blender" in subdir.name.lower():
                    exe = subdir / "blender.exe"
                    if exe.exists():
                        return exe
        
        extra_paths = [
            Path(r"C:\Program Files\Blender Foundation\Blender"),
            Path(r"C:\Program Files\Blender Foundation\Blender 4.2"),
            Path(r"C:\Program Files\Blender Foundation\Blender 5.0"),
            Path(r"C:\Program Files\Blender Foundation\Blender 5.1"),
            Path(r"C:\Program Files\Blender"),
            Path(r"D:\Program Files\Blender Foundation\Blender"),
            Path(r"D:\Program Files\Blender Foundation\Blender 4.2"),
            Path(r"D:\Program Files\Blender Foundation\Blender 5.0"),
            Path(r"D:\Program Files\Blender Foundation\Blender 5.1"),
            Path(r"D:\Blender"),
            Path(r"D:\Blender Foundation\Blender"),
            Path(r"C:\Blender"),
        ]
        for base_path in extra_paths:
            if base_path.exists():
                for exe_name in ["blender.exe", "blender-launcher.exe"]:
                    candidate = base_path / exe_name
                    if candidate.exists():
                        return candidate
                for subdir in base_path.iterdir():
                    if subdir.is_dir() and "blender" in subdir.name.lower():
                        exe = subdir / "blender.exe"
                        if exe.exists():
                            return exe
        
        return None

    def _check_availability(self) -> bool:
        """检查 Blender 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        if self._blender_path is None:
            return False
        if not self._blender_path.exists():
            return False
        try:
            result = subprocess.run(
                [str(self._blender_path), "--version"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode == 0 or "Blender" in result.stdout + result.stderr
        except Exception:
            return False

    def is_available(self) -> bool:
        """检查 Blender 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        return self._available

    def get_scene_presets(self) -> Dict[str, Scene3DConfig]:
        """获取场景预设字典。

        Returns:
            场景预设名称到 Scene3DConfig 的映射
        """
        return dict(BLENDER_SCENE_PRESETS)

    def generate_blender_script(self, scene_config: Scene3DConfig, output_path: str, blend_output_path: str = None) -> str:
        """生成 Blender Python 脚本文件。

        Args:
            scene_config: 3D 场景配置
            output_path: 输出脚本文件路径
            blend_output_path: .blend 文件保存路径（脚本内save_as_mainfile使用）

        Returns:
            生成的脚本文件路径
        """
        script_lines = [
            "import bpy",
            "import math",
            "",
            "# Clear default objects",
            "bpy.ops.object.select_all(action='SELECT')",
            "bpy.ops.object.delete()",
            "",
            "# Scene setup",
            "scene = bpy.context.scene",
            f"scene.render.resolution_x = {self.config.resolution_x}",
            f"scene.render.resolution_y = {self.config.resolution_y}",
            f"scene.render.fps = {self.config.fps}",
        ]

        # Blender 4.x+: EEVEE -> BLENDER_EEVEE, WORKBENCH -> BLENDER_WORKBENCH
        engine_name = self.config.engine.upper()
        engine_map = {"EEVEE": "BLENDER_EEVEE", "WORKBENCH": "BLENDER_WORKBENCH", "CYCLES": "CYCLES"}
        engine_name = engine_map.get(engine_name, engine_name)
        script_lines.append(f"scene.render.engine = '{engine_name}'")

        if self.config.engine == "cycles":
            script_lines.extend([
                f"scene.cycles.samples = {self.config.samples}",
                f"scene.cycles.use_denoising = {self.config.denoise}",
                f"scene.cycles.device = {'GPU' if self.config.use_gpu else 'CPU'}",
            ])

        bg_r, bg_g, bg_b, bg_a = scene_config.background_color
        script_lines.extend([
            "",
            "# Background",
            "world = bpy.data.worlds.new('World')",
            "scene.world = world",
            "world.use_nodes = True",
            # Blender 4.x/5.x: safely get or create Background and Output nodes
            "nt = world.node_tree",
            "out_node = nt.nodes.get('Material Output') or nt.nodes.get('World Output')",
            "if out_node is None:",
            "    for n in nt.nodes:",
            "        if 'Output' in n.name:",
            "            out_node = n",
            "            break",
            "    if out_node is None:",
            "        out_node = nt.nodes.new('ShaderNodeOutputWorld')",
            "bg_node = None",
            "for n in nt.nodes:",
            "    if n.bl_idname == 'ShaderNodeBackground':",
            "        bg_node = n",
            "        break",
            "if bg_node is None:",
            "    bg_node = nt.nodes.new('ShaderNodeBackground')",
            "    nt.links.new(bg_node.outputs[0], out_node.inputs[0])",
            f"bg_node.inputs[0].default_value = ({bg_r}, {bg_g}, {bg_b}, {bg_a})",
            "bg_node.inputs[1].default_value = 1.0",
        ])

        for idx, obj in enumerate(scene_config.objects):
            obj_type = obj.get("type", "cube").lower()
            obj_name = obj.get("name", f"object_{idx}")
            location = obj.get("location", (0, 0, 0))
            rotation = obj.get("rotation", (0, 0, 0))
            scale = obj.get("scale", (1, 1, 1))
            material = obj.get("material", {})
            mat_color = material.get("color", (0.8, 0.8, 0.8, 1.0))

            script_lines.extend([
                "",
                f"# Create object: {obj_name}",
            ])

            if obj_type == "plane":
                script_lines.append("bpy.ops.mesh.primitive_plane_add(size=2)")
            elif obj_type == "cube":
                script_lines.append("bpy.ops.mesh.primitive_cube_add(size=2)")
            elif obj_type == "sphere" or obj_type == "icosphere":
                script_lines.append("bpy.ops.mesh.primitive_ico_sphere_add(radius=1)")
            elif obj_type == "cone":
                script_lines.append("bpy.ops.mesh.primitive_cone_add(radius1=1, depth=2)")
            elif obj_type == "cylinder":
                script_lines.append("bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2)")
            elif obj_type == "torus":
                script_lines.append("bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.25)")
            else:
                script_lines.append("bpy.ops.mesh.primitive_cube_add(size=2)")

            script_lines.extend([
                f"obj = bpy.context.active_object",
                f"obj.name = '{obj_name}'",
                f"obj.location = ({location[0]}, {location[1]}, {location[2]})",
                f"obj.rotation_euler = ({rotation[0]}, {rotation[1]}, {rotation[2]})",
                f"obj.scale = ({scale[0]}, {scale[1]}, {scale[2]})",
                "",
                f"mat = bpy.data.materials.new('{obj_name}_mat')",
                "mat.use_nodes = True",
                "bsdf = None",
                "for n in mat.node_tree.nodes:",
                "    if 'Principled' in n.bl_idname:",
                "        bsdf = n",
                "        break",
                "if bsdf is None:",
                "    bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')",
                f"bsdf.inputs['Base Color'].default_value = ({mat_color[0]}, {mat_color[1]}, {mat_color[2]}, {mat_color[3]})",
                "obj.data.materials.append(mat)",
            ])

        for idx, light in enumerate(scene_config.lights):
            light_type = light.get("type", "POINT")
            light_name = light.get("name", f"light_{idx}")
            location = light.get("location", (0, 0, 5))
            energy = light.get("energy", 1000)
            color = light.get("color", (1.0, 1.0, 1.0, 1.0))

            script_lines.extend([
                "",
                f"# Create light: {light_name}",
                f"light_data = bpy.data.lights.new(name='{light_name}', type='{light_type}')",
                f"light_data.energy = {energy}",
                f"light_data.color = ({color[0]}, {color[1]}, {color[2]})",
                f"light_obj = bpy.data.objects.new(name='{light_name}', object_data=light_data)",
                "scene.collection.objects.link(light_obj)",
                f"light_obj.location = ({location[0]}, {location[1]}, {location[2]})",
            ])

            if light_type == "SPOT":
                spot_size = light.get("spot_size", 0.785)
                script_lines.append(f"light_data.spot_size = {spot_size}")

        for idx, cam in enumerate(scene_config.cameras):
            cam_name = cam.get("name", f"camera_{idx}")
            location = cam.get("location", (0, -5, 2))
            rotation = cam.get("rotation", (1.1, 0, 3.1416))
            lens = cam.get("lens", 50)

            script_lines.extend([
                "",
                f"# Create camera: {cam_name}",
                f"cam_data = bpy.data.cameras.new(name='{cam_name}')",
                f"cam_data.lens = {lens}",
                f"cam_obj = bpy.data.objects.new(name='{cam_name}', object_data=cam_data)",
                "scene.collection.objects.link(cam_obj)",
                f"cam_obj.location = ({location[0]}, {location[1]}, {location[2]})",
                f"cam_obj.rotation_euler = ({rotation[0]}, {rotation[1]}, {rotation[2]})",
            ])

            if idx == 0:
                script_lines.append("scene.camera = cam_obj")

        for anim in scene_config.animations:
            obj_name = anim.get("object_name", "")
            prop = anim.get("property", "location")
            keyframes = anim.get("keyframes", [])

            script_lines.extend([
                "",
                f"# Animation: {obj_name}.{prop}",
                f"anim_obj = bpy.data.objects.get('{obj_name}')",
                "if anim_obj:",
            ])

            for kf in keyframes:
                frame = kf.get("frame", 1)
                value = kf.get("value", [0, 0, 0])
                script_lines.extend([
                    f"    anim_obj.{prop} = ({value[0]}, {value[1]}, {value[2]})",
                    f"    anim_obj.keyframe_insert(data_path='{prop}', frame={frame})",
                ])

        if scene_config.animations:
            max_frame = 1
            for anim in scene_config.animations:
                for kf in anim.get("keyframes", []):
                    max_frame = max(max_frame, kf.get("frame", 1))
            script_lines.extend([
                "",
                f"scene.frame_start = 1",
                f"scene.frame_end = {max_frame}",
            ])

        script_lines.extend([
            "",
            "# Save blend file",
            f"bpy.ops.wm.save_as_mainfile(filepath=r'{blend_output_path or output_path}')",
            "",
            "print('Scene generated successfully')",
        ])

        script_content = "\n".join(script_lines)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        return output_path

    def generate_scene(self, scene_config: Scene3DConfig, output_name: str = "scene") -> BlenderSceneResult:
        """主方法：生成 3D 场景。

        Args:
            scene_config: 3D 场景配置
            output_name: 输出名称（不含扩展名）

        Returns:
            BlenderSceneResult 场景生成结果对象
        """
        start_time = time.time()

        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        blend_file = str(output_dir / f"{output_name}_{ts}.blend")
        script_file = str(output_dir / f"{output_name}_{ts}_script.py")

        object_count = len(scene_config.objects)
        light_count = len(scene_config.lights)
        camera_count = len(scene_config.cameras)

        frame_range = (1, 1)
        if scene_config.animations:
            max_frame = 1
            for anim in scene_config.animations:
                for kf in anim.get("keyframes", []):
                    max_frame = max(max_frame, kf.get("frame", 1))
            frame_range = (1, max_frame)

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self._available else "simulate"

        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path="",
            object_count=object_count,
            light_count=light_count,
            camera_count=camera_count,
            frame_range=frame_range,
            mode=mode,
        )

        if mode == "real":
            real_result = self._run_real_mode(scene_config, blend_file, script_file)
            result = real_result
            if not real_result.success and self.config.mode == "auto":
                print("[Blender3DIntegrator] Real mode failed, falling back to simulate")
                sim_result = self._run_simulate_mode(scene_config, blend_file)
                result = sim_result
        else:
            sim_result = self._run_simulate_mode(scene_config, blend_file)
            result = sim_result

        result.duration = time.time() - start_time
        return result

    def _run_real_mode(
        self,
        scene_config: Scene3DConfig,
        blend_file: str,
        script_file: str,
    ) -> BlenderSceneResult:
        """真实模式：通过 subprocess 调用 Blender。

        Args:
            scene_config: 3D 场景配置
            blend_file: 输出 .blend 文件路径
            script_file: 临时脚本文件路径

        Returns:
            BlenderSceneResult 场景生成结果
        """
        object_count = len(scene_config.objects)
        light_count = len(scene_config.lights)
        camera_count = len(scene_config.cameras)

        frame_range = (1, 1)
        if scene_config.animations:
            max_frame = 1
            for anim in scene_config.animations:
                for kf in anim.get("keyframes", []):
                    max_frame = max(max_frame, kf.get("frame", 1))
            frame_range = (1, max_frame)

        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path="",
            object_count=object_count,
            light_count=light_count,
            camera_count=camera_count,
            frame_range=frame_range,
            mode="real",
        )

        if self._blender_path is None or not self._blender_path.exists():
            result.error = f"Blender not found at {self.config.install_path}"
            return result

        try:
            self.generate_blender_script(scene_config, script_file, blend_output_path=blend_file)

            cmd = [
                str(self._blender_path),
                "--background",
                "--python",
                script_file,
            ]

            print(f"[Blender3DIntegrator] Running: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(Path(blend_file).parent),
            )

            if process.returncode == 0 and Path(blend_file).exists():
                result.success = True
            else:
                error_msg = process.stderr[:500] if process.stderr else f"Exit code: {process.returncode}"
                result.error = error_msg

            return result

        except subprocess.TimeoutExpired:
            result.error = "Process timed out"
            return result
        except Exception as e:
            result.error = str(e)
            return result

    def _run_simulate_mode(
        self,
        scene_config: Scene3DConfig,
        blend_file: str,
    ) -> BlenderSceneResult:
        """模拟模式：不真正调用 Blender，生成模拟结果。

        Args:
            scene_config: 3D 场景配置
            blend_file: 输出 .blend 文件路径

        Returns:
            BlenderSceneResult 场景生成结果
        """
        object_count = len(scene_config.objects)
        light_count = len(scene_config.lights)
        camera_count = len(scene_config.cameras)

        frame_range = (1, 1)
        if scene_config.animations:
            max_frame = 1
            for anim in scene_config.animations:
                for kf in anim.get("keyframes", []):
                    max_frame = max(max_frame, kf.get("frame", 1))
            frame_range = (1, max_frame)

        sim_duration = 1.5

        time.sleep(sim_duration)

        blend_path = Path(blend_file)
        blend_path.parent.mkdir(parents=True, exist_ok=True)

        with open(blend_file, "wb") as f:
            f.write(b"BLENDER_SIMULATED_FILE")
            f.seek(1024 * 100)
            f.write(b"\0")

        result = BlenderSceneResult(
            success=True,
            blend_file=blend_file,
            output_path="",
            duration=sim_duration,
            object_count=object_count,
            light_count=light_count,
            camera_count=camera_count,
            frame_range=frame_range,
            mode="simulate",
        )

        return result

    def generate_puppet_stage(self, stage_type: str = "wooden", style: str = "classic") -> BlenderSceneResult:
        """生成木偶舞台场景。

        Args:
            stage_type: 舞台类型（wooden / theater）
            style: 风格（classic / modern / minimal）

        Returns:
            BlenderSceneResult 场景生成结果对象
        """
        preset_key = f"puppet_stage_{stage_type}"
        if preset_key in BLENDER_SCENE_PRESETS:
            scene_config = BLENDER_SCENE_PRESETS[preset_key]
        else:
            scene_config = BLENDER_SCENE_PRESETS["puppet_stage_wooden"]

        output_name = f"puppet_stage_{stage_type}_{style}"
        return self.generate_scene(scene_config, output_name)

    def render_animation(
        self,
        blend_file: str,
        start_frame: int = 1,
        end_frame: int = 100,
        output_path: Optional[str] = None,
    ) -> BlenderSceneResult:
        """渲染动画。

        Args:
            blend_file: .blend 工程文件路径
            start_frame: 起始帧
            end_frame: 结束帧
            output_path: 输出路径（可选）

        Returns:
            BlenderSceneResult 渲染结果对象
        """
        start_time = time.time()

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self._available else "simulate"

        if output_path is None:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            if self.config.output_format == "FFmpeg_video":
                ext = "mp4" if self.config.video_codec == "H264" else "mp4"
                output_path = str(output_dir / f"render_anim_{ts}.{ext}")
            else:
                output_path = str(output_dir / f"render_anim_{ts}")

        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path=output_path,
            frame_range=(start_frame, end_frame),
            mode=mode,
        )

        if mode == "real":
            result = self._render_animation_real(blend_file, start_frame, end_frame, output_path)
        else:
            result = self._render_animation_simulate(blend_file, start_frame, end_frame, output_path)

        result.duration = time.time() - start_time
        return result

    def _render_animation_real(
        self,
        blend_file: str,
        start_frame: int,
        end_frame: int,
        output_path: str,
    ) -> BlenderSceneResult:
        """真实模式渲染动画。

        Args:
            blend_file: .blend 文件路径
            start_frame: 起始帧
            end_frame: 结束帧
            output_path: 输出路径

        Returns:
            BlenderSceneResult 渲染结果
        """
        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path=output_path,
            frame_range=(start_frame, end_frame),
            mode="real",
        )

        if self._blender_path is None or not self._blender_path.exists():
            result.error = f"Blender not found at {self.config.install_path}"
            return result

        if not Path(blend_file).exists():
            result.error = f"Blend file not found: {blend_file}"
            return result

        try:
            output_dir = str(Path(output_path).parent)
            output_name = Path(output_path).stem

            cmd = [
                str(self._blender_path),
                "--background",
                blend_file,
                "--render-output",
                str(Path(output_dir) / f"{output_name}_"),
                "--render-frame",
                f"{start_frame}..{end_frame}",
                "--engine",
                self.config.engine.upper(),
            ]

            print(f"[Blender3DIntegrator] Rendering animation: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,
                cwd=output_dir,
            )

            if process.returncode == 0:
                result.success = True
            else:
                error_msg = process.stderr[:500] if process.stderr else f"Exit code: {process.returncode}"
                result.error = error_msg

            return result

        except subprocess.TimeoutExpired:
            result.error = "Render timed out"
            return result
        except Exception as e:
            result.error = str(e)
            return result

    def _render_animation_simulate(
        self,
        blend_file: str,
        start_frame: int,
        end_frame: int,
        output_path: str,
    ) -> BlenderSceneResult:
        """模拟模式渲染动画。

        Args:
            blend_file: .blend 文件路径
            start_frame: 起始帧
            end_frame: 结束帧
            output_path: 输出路径

        Returns:
            BlenderSceneResult 渲染结果
        """
        frame_count = end_frame - start_frame + 1
        sim_duration = min(frame_count * 0.05, 3.0)

        time.sleep(sim_duration)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if self.config.output_format == "FFmpeg_video":
            with open(output_path, "wb") as f:
                f.write(b"SIMULATED_VIDEO_OUTPUT")
                f.seek(1024 * 1024)
                f.write(b"\0")
        else:
            out_path.mkdir(parents=True, exist_ok=True)
            for i in range(start_frame, min(start_frame + 5, end_frame + 1)):
                frame_file = out_path / f"frame_{i:04d}.png"
                with open(frame_file, "wb") as f:
                    f.write(b"SIMULATED_FRAME")

        result = BlenderSceneResult(
            success=True,
            blend_file=blend_file,
            output_path=output_path,
            duration=sim_duration,
            frame_range=(start_frame, end_frame),
            mode="simulate",
        )

        return result

    def render_still_image(
        self,
        blend_file: str,
        frame: int = 1,
        output_path: Optional[str] = None,
    ) -> BlenderSceneResult:
        """渲染静帧图像。

        Args:
            blend_file: .blend 工程文件路径
            frame: 帧号
            output_path: 输出路径（可选）

        Returns:
            BlenderSceneResult 渲染结果对象
        """
        start_time = time.time()

        mode = self.config.mode
        if mode == "auto":
            mode = "real" if self._available else "simulate"

        if output_path is None:
            output_dir = Path(self.config.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            ext = self.config.output_format.lower().replace("open_exr", "exr")
            output_path = str(output_dir / f"render_still_{ts}.{ext}")

        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path=output_path,
            frame_range=(frame, frame),
            mode=mode,
        )

        if mode == "real":
            result = self._render_still_real(blend_file, frame, output_path)
        else:
            result = self._render_still_simulate(blend_file, frame, output_path)

        result.duration = time.time() - start_time
        return result

    def _render_still_real(
        self,
        blend_file: str,
        frame: int,
        output_path: str,
    ) -> BlenderSceneResult:
        """真实模式渲染静帧。

        Args:
            blend_file: .blend 文件路径
            frame: 帧号
            output_path: 输出路径

        Returns:
            BlenderSceneResult 渲染结果
        """
        result = BlenderSceneResult(
            success=False,
            blend_file=blend_file,
            output_path=output_path,
            frame_range=(frame, frame),
            mode="real",
        )

        if self._blender_path is None or not self._blender_path.exists():
            result.error = f"Blender not found at {self.config.install_path}"
            return result

        if not Path(blend_file).exists():
            result.error = f"Blend file not found: {blend_file}"
            return result

        try:
            output_dir = str(Path(output_path).parent)
            output_name = Path(output_path).stem

            cmd = [
                str(self._blender_path),
                "--background",
                blend_file,
                "--render-output",
                str(Path(output_dir) / f"{output_name}_"),
                "--render-frame",
                str(frame),
                "--engine",
                self.config.engine.upper(),
            ]

            print(f"[Blender3DIntegrator] Rendering still: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=output_dir,
            )

            if process.returncode == 0:
                result.success = True
            else:
                error_msg = process.stderr[:500] if process.stderr else f"Exit code: {process.returncode}"
                result.error = error_msg

            return result

        except subprocess.TimeoutExpired:
            result.error = "Render timed out"
            return result
        except Exception as e:
            result.error = str(e)
            return result

    def _render_still_simulate(
        self,
        blend_file: str,
        frame: int,
        output_path: str,
    ) -> BlenderSceneResult:
        """模拟模式渲染静帧。

        Args:
            blend_file: .blend 文件路径
            frame: 帧号
            output_path: 输出路径

        Returns:
            BlenderSceneResult 渲染结果
        """
        sim_duration = 1.0
        time.sleep(sim_duration)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(b"SIMULATED_IMAGE_OUTPUT")
            f.seek(1024 * 500)
            f.write(b"\0")

        result = BlenderSceneResult(
            success=True,
            blend_file=blend_file,
            output_path=output_path,
            duration=sim_duration,
            frame_range=(frame, frame),
            mode="simulate",
        )

        return result


def create_scene_config_from_preset(preset_name: str) -> Scene3DConfig:
    """从预设创建 Scene3DConfig 场景配置对象。

    Args:
        preset_name: 预设名称

    Returns:
        Scene3DConfig 场景配置对象

    Raises:
        ValueError: 预设不存在时抛出
    """
    if preset_name not in BLENDER_SCENE_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset_name}. "
            f"Available presets: {list(BLENDER_SCENE_PRESETS.keys())}"
        )
    return BLENDER_SCENE_PRESETS[preset_name]


def _run_self_tests():
    """自测函数：验证 Blender 3D 集成模块的所有功能。"""
    print("=" * 60)
    print("Blender 3D 场景集成模块 - 自测")
    print("=" * 60)

    results = []

    test_dir = Path(tempfile.mkdtemp(prefix="blender_test_"))

    print("\n[测试 1/10] 检查 BLENDER_SCENE_PRESETS 预设配置...")
    expected_presets = [
        "puppet_stage_wooden",
        "puppet_stage_theater",
        "miniature_room",
        "studio_3point",
        "outdoor_garden",
        "night_scene",
        "abstract_geometric",
        "empty_studio",
    ]
    all_presets_ok = True
    for pname in expected_presets:
        if pname in BLENDER_SCENE_PRESETS:
            print(f"  ✓ {pname} 存在")
        else:
            print(f"  ✗ {pname} 不存在")
            all_presets_ok = False
    results.append(("presets", all_presets_ok))

    print("\n[测试 2/10] 检查 BlenderConfig 数据类...")
    try:
        config = BlenderConfig()
        required_attrs = [
            "install_path", "mode", "output_dir", "engine",
            "resolution_x", "resolution_y", "fps", "samples",
            "output_format", "video_codec", "use_gpu", "denoise",
        ]
        attrs_ok = all(hasattr(config, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ BlenderConfig 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ BlenderConfig 缺少必需属性")
        results.append(("config_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ BlenderConfig 错误: {e}")
        results.append(("config_dataclass", False))

    print("\n[测试 3/10] 检查 BlenderSceneResult 数据类...")
    try:
        result = BlenderSceneResult()
        required_attrs = [
            "success", "blend_file", "output_path", "duration",
            "object_count", "light_count", "camera_count",
            "frame_range", "error", "mode",
        ]
        attrs_ok = all(hasattr(result, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ BlenderSceneResult 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ BlenderSceneResult 缺少必需属性")
        results.append(("result_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ BlenderSceneResult 错误: {e}")
        results.append(("result_dataclass", False))

    print("\n[测试 4/10] 检查 Scene3DConfig 数据类...")
    try:
        config = Scene3DConfig()
        required_attrs = [
            "scene_type", "background_color", "objects",
            "lights", "cameras", "animations",
        ]
        attrs_ok = all(hasattr(config, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ Scene3DConfig 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ Scene3DConfig 缺少必需属性")
        results.append(("scene_config_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ Scene3DConfig 错误: {e}")
        results.append(("scene_config_dataclass", False))

    print("\n[测试 5/10] 检查 Blender3DIntegrator 初始化...")
    try:
        integrator = Blender3DIntegrator(config=BlenderConfig(mode="simulate", output_dir=str(test_dir)))
        print(f"  ✓ Blender3DIntegrator 初始化成功")
        print(f"    - Mode: {integrator.config.mode}")
        print(f"    - Available: {integrator.is_available()}")
        results.append(("integrator_init", True))
    except Exception as e:
        print(f"  ✗ Blender3DIntegrator 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("integrator_init", False))

    print("\n[测试 6/10] 检查 get_scene_presets...")
    try:
        integrator = Blender3DIntegrator(config=BlenderConfig(mode="simulate", output_dir=str(test_dir)))
        presets = integrator.get_scene_presets()
        if isinstance(presets, dict) and len(presets) == 8:
            print(f"  ✓ 场景预设列表: {len(presets)} 个")
            results.append(("get_presets", True))
        else:
            print(f"  ✗ 预设数量不匹配: {len(presets) if isinstance(presets, dict) else 'error'}")
            results.append(("get_presets", False))
    except Exception as e:
        print(f"  ✗ get_scene_presets 错误: {e}")
        results.append(("get_presets", False))

    print("\n[测试 7/10] 检查 generate_blender_script...")
    try:
        integrator = Blender3DIntegrator(config=BlenderConfig(mode="simulate", output_dir=str(test_dir)))
        scene_config = BLENDER_SCENE_PRESETS["puppet_stage_wooden"]
        script_path = str(test_dir / "test_script.py")
        output = integrator.generate_blender_script(scene_config, script_path)
        if Path(output).exists() and Path(output).stat().st_size > 0:
            content = Path(output).read_text(encoding="utf-8")
            if "import bpy" in content and "bpy.ops.mesh" in content:
                print(f"  ✓ Blender 脚本生成成功 ({len(content)} 字符)")
                results.append(("generate_script", True))
            else:
                print(f"  ✗ 脚本内容不完整")
                results.append(("generate_script", False))
        else:
            print(f"  ✗ 脚本文件不存在或为空")
            results.append(("generate_script", False))
    except Exception as e:
        print(f"  ✗ generate_blender_script 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("generate_script", False))

    print("\n[测试 8/10] 检查 simulate 模式 generate_scene...")
    try:
        integrator = Blender3DIntegrator(config=BlenderConfig(mode="simulate", output_dir=str(test_dir)))
        scene_config = BLENDER_SCENE_PRESETS["puppet_stage_wooden"]

        result = integrator.generate_scene(scene_config, output_name="test_scene")

        if result.success and Path(result.blend_file).exists():
            print(f"  ✓ 模拟模式场景生成成功")
            print(f"    - 物体数: {result.object_count}")
            print(f"    - 灯光数: {result.light_count}")
            print(f"    - 摄像机数: {result.camera_count}")
            print(f"    - 模式: {result.mode}")
            results.append(("simulate_generate", True))
        else:
            print(f"  ✗ 模拟模式场景生成失败: {result.error}")
            results.append(("simulate_generate", False))
    except Exception as e:
        print(f"  ✗ simulate generate_scene 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_generate", False))

    print("\n[测试 9/10] 检查 generate_puppet_stage...")
    try:
        integrator = Blender3DIntegrator(config=BlenderConfig(mode="simulate", output_dir=str(test_dir)))
        result = integrator.generate_puppet_stage(stage_type="wooden", style="classic")

        if result.success and result.object_count > 0:
            print(f"  ✓ 木偶舞台生成成功")
            print(f"    - 物体数: {result.object_count}")
            print(f"    - 灯光数: {result.light_count}")
            results.append(("puppet_stage", True))
        else:
            print(f"  ✗ 木偶舞台生成失败: {result.error}")
            results.append(("puppet_stage", False))
    except Exception as e:
        print(f"  ✗ generate_puppet_stage 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("puppet_stage", False))

    print("\n[测试 10/10] 检查 create_scene_config_from_preset...")
    try:
        test_preset = "studio_3point"
        config = create_scene_config_from_preset(test_preset)
        if config.scene_type == "studio" and len(config.lights) >= 3:
            print(f"  ✓ 预设 {test_preset} 创建成功")
            print(f"    - 场景类型: {config.scene_type}")
            print(f"    - 物体数: {len(config.objects)}")
            print(f"    - 灯光数: {len(config.lights)}")
            results.append(("preset_create", True))
        else:
            print(f"  ✗ 预设参数不匹配")
            results.append(("preset_create", False))
    except Exception as e:
        print(f"  ✗ create_scene_config_from_preset 错误: {e}")
        results.append(("preset_create", False))

    print("\n[场景预设清单]")
    for pname, pdata in BLENDER_SCENE_PRESETS.items():
        obj_count = len(pdata.objects)
        light_count = len(pdata.lights)
        cam_count = len(pdata.cameras)
        print(f"  - {pname}: {pdata.scene_type} ({obj_count}物体/{light_count}灯光/{cam_count}摄像机)")

    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"自测结果: {passed}/{total} 通过")
    print("=" * 60)

    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}: {name}")

    return passed == total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Blender 3D Scene Integration")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="Execution mode",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="empty_studio",
        help=f"Scene preset: {list(BLENDER_SCENE_PRESETS.keys())}",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available scene presets",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default="scene",
        help="Output scene name",
    )
    parser.add_argument(
        "--puppet-stage",
        action="store_true",
        help="Generate puppet stage scene",
    )
    parser.add_argument(
        "--stage-type",
        type=str,
        default="wooden",
        help="Puppet stage type (wooden/theater)",
    )

    args = parser.parse_args()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)
    elif args.list_presets:
        print("Available scene presets:")
        for name, data in BLENDER_SCENE_PRESETS.items():
            obj_count = len(data.objects)
            light_count = len(data.lights)
            cam_count = len(data.cameras)
            print(f"  {name}: {data.scene_type} ({obj_count} objs, {light_count} lights, {cam_count} cams)")
    elif args.puppet_stage:
        config = BlenderConfig(mode=args.mode)
        integrator = Blender3DIntegrator(config=config)
        result = integrator.generate_puppet_stage(stage_type=args.stage_type)
        if result.success:
            print(f"\n✓ Success! Blend file: {result.blend_file}")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Objects: {result.object_count}")
            print(f"  Lights: {result.light_count}")
            print(f"  Cameras: {result.camera_count}")
            sys.exit(0)
        else:
            print(f"\n✗ Failed: {result.error}")
            sys.exit(1)
    else:
        parser.print_help()
