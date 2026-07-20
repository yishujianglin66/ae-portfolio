"""Blender engine - 3D scene generation via bpy Python API."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class BlenderEngine(BaseEngine):
    """Blender 4.x engine wrapper using bpy via CLI.

    Supports:
    - Procedural stage/scene generation
    - Camera/lighting setup
    - Rendering (Cycles / Eevee)
    - Python script execution via blender --python
    """

    name = "blender"

    STAGE_TEMPLATE = '''
"""Auto-generated Blender puppet stage script."""
import bpy
import sys
import json

# Clear default scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# ============================================================
# Stage geometry
# ============================================================
bpy.ops.mesh.primitive_cube_add(size=1)
stage = bpy.context.active_object
stage.name = "Stage_Base"
stage.scale = ({stage_w}, {stage_h}, {stage_d})
stage.location = (0, 0, -{stage_d}/2)

# Stage material
mat = bpy.data.materials.new(name="StageMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs['Base Color'].default_value = {wood_color}
bsdf.inputs['Roughness'].default_value = {roughness}
bsdf.inputs['Subsurface'].default_value = 0.1

if stage.data.materials:
    stage.data.materials[0] = mat
else:
    stage.data.materials.append(mat)

# ============================================================
# Lighting
# ============================================================
bpy.ops.object.light_add(type='AREA', location=(0, 0, {light_height}))
key_light = bpy.context.active_object
key_light.name = "Key_Light"
key_light.data.energy = {key_light_intensity}
key_light.data.size = {light_size}

bpy.ops.object.light_add(type='AREA', location=(-3, -3, {light_height}))
fill_light = bpy.context.active_object
fill_light.name = "Fill_Light"
fill_light.data.energy = {fill_light_intensity}
fill_light.data.size = {light_size}

bpy.ops.object.light_add(type='AREA', location=(0, 0, -2))
rim_light = bpy.context.active_object
rim_light.name = "Rim_Light"
rim_light.data.energy = {rim_light_intensity}
rim_light.data.size = 3
rim_light.rotation_euler = (3.14159, 0, 0)

# ============================================================
# Camera
# ============================================================
bpy.ops.object.camera_add(location=(0, -{camera_distance}, {camera_height}))
cam = bpy.context.active_object
cam.name = "Main_Camera"
cam.rotation_euler = ({camera_pitch}, 0, 0)
cam.data.lens = {focal_length}
bpy.context.scene.camera = cam

# ============================================================
# Render settings
# ============================================================
scene = bpy.context.scene
scene.render.engine = '{render_engine}'
scene.render.resolution_x = {resolution_x}
scene.render.resolution_y = {resolution_y}
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = '{output_format}'
scene.frame_start = 0
scene.frame_end = 1

# ============================================================
# Save + render
# ============================================================
bpy.ops.wm.save_mainfile(filepath=r"{blend_output}")
scene.render.filepath = r"{render_output}"
bpy.ops.render.render(write_still=True)

# ============================================================
# AE 资产导出（可选）：FBX + PNG 序列帧
# 通过 export_ae 参数控制是否执行
# ============================================================
{ae_export_block}

# Write marker
with open(r"{marker_path}", "w") as f:
    f.write("SUCCESS\\n")
    f.write(f"blend: {blend_output}\\n")
    f.write(f"render: {render_output}\\n")
{ae_marker_lines}
'''

    # 当 export_ae=True 时，注入到 STAGE_TEMPLATE 中的 FBX + PNG 序列帧导出代码
    AE_EXPORT_BLOCK = '''
# ---- FBX 导出（供 AE Element 3D / Cinema 4D Lite 使用） ----
fbx_path = r"{fbx_output}"
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=False,
    bake_anim=True,
    apply_unit_scale=True,
    axis_forward='-Z',
    axis_up='Y',
)

# ---- PNG 序列帧导出（供 AE 作为 3D 背景层叠加） ----
import os
frames_dir = r"{frames_output}"
os.makedirs(frames_dir, exist_ok=True)
scene.frame_start = {ae_frame_start}
scene.frame_end = {ae_frame_end}
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.join(frames_dir, "")
bpy.ops.render.render(animation=True)
'''

    # export_for_ae 独立方法使用的脚本模板（针对已有 .blend 文件）
    EXPORT_AE_TEMPLATE = '''
"""Auto-generated Blender -> AE export script."""
import bpy
import os

# 打开已有的 .blend 文件
bpy.ops.wm.open_mainfile(filepath=r"{blend_path}")

# ============================================================
# FBX 导出
# ============================================================
fbx_path = r"{fbx_output}"
bpy.ops.export_scene.fbx(
    filepath=fbx_path,
    use_selection=False,
    bake_anim=True,
    apply_unit_scale=True,
    axis_forward='-Z',
    axis_up='Y',
)

# ============================================================
# PNG 序列帧导出
# ============================================================
scene = bpy.context.scene
frames_dir = r"{frames_output}"
os.makedirs(frames_dir, exist_ok=True)
scene.frame_start = {ae_frame_start}
scene.frame_end = {ae_frame_end}
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = os.path.join(frames_dir, "")
bpy.ops.render.render(animation=True)

# 写标记文件
with open(r"{marker_path}", "w") as f:
    f.write("SUCCESS\\n")
    f.write(f"fbx: {fbx_output}\\n")
    f.write(f"frames: {frames_output}\\n")
'''

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.blender_path
        super().__init__(path)

    def _color_tuple(self, hex_color: str) -> str:
        """Convert hex color to Blender RGBA tuple string."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return f"({r:.3f}, {g:.3f}, {b:.3f}, 1.0)"

    async def create_puppet_stage(
        self,
        output_dir: Path | str,
        style: str = "wooden",
        resolution: tuple[int, int] = (1920, 1080),
        render_engine: str = "BLENDER_EEVEE",
        export_ae: bool = False,
        ae_frame_start: int = 1,
        ae_frame_end: int = 60,
    ) -> EngineResult:
        """Generate a puppet theatre stage scene.

        Args:
            output_dir: Directory for .blend file and render
            style: Stage style ("wooden", "minimal", "vintage")
            resolution: Output resolution (width, height)
            render_engine: "BLENDER_EEVEE" or "CYCLES"
            export_ae: 是否同时导出 AE 资产（FBX + PNG 序列帧）。
                启用后将在同一 Blender 进程中完成导出，效率高于单独调用 export_for_ae。
            ae_frame_start: AE 序列帧起始帧（仅 export_ae=True 时生效）
            ae_frame_end: AE 序列帧结束帧（仅 export_ae=True 时生效）
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        blend_output = output_dir / "stage.blend"
        render_output = output_dir / "stage_preview.png"
        marker_path = Path(tempfile.gettempdir()) / f"bl_stage_{output_dir.name}.mark"

        # AE 资产导出路径（仅 export_ae=True 时使用）
        fbx_output = output_dir / "stage_export.fbx"
        frames_output = output_dir / "frames"

        style_presets: dict[str, dict[str, Any]] = {
            "wooden": {
                "wood_color": "#8B4513",
                "roughness": 0.6,
                "stage_w": 10,
                "stage_h": 6,
                "stage_d": 0.5,
            },
            "minimal": {
                "wood_color": "#F5F5F5",
                "roughness": 0.3,
                "stage_w": 12,
                "stage_h": 7,
                "stage_d": 0.3,
            },
            "vintage": {
                "wood_color": "#654321",
                "roughness": 0.8,
                "stage_w": 8,
                "stage_h": 5,
                "stage_d": 0.7,
            },
        }
        preset = style_presets.get(style, style_presets["wooden"])

        # 根据export_ae决定是否注入FBX+PNG序列帧导出代码
        if export_ae:
            ae_export_block = self.AE_EXPORT_BLOCK.format(
                fbx_output=str(fbx_output).replace("\\", "\\\\"),
                frames_output=str(frames_output).replace("\\", "\\\\"),
                ae_frame_start=ae_frame_start,
                ae_frame_end=ae_frame_end,
            )
            # 生成 marker 文件追加写入行（与模板里 f.write 的 \n 转义一致）：
            # 路径反斜杠需在生成脚本的字符串字面量中加倍
            fbx_path_escaped = str(fbx_output).replace("\\", "\\\\")
            frames_path_escaped = str(frames_output).replace("\\", "\\\\")
            ae_marker_lines = (
                f'    f.write(f"fbx: {fbx_path_escaped}\\n")\n'
                f'    f.write(f"frames: {frames_path_escaped}\\n")'
            )
            logger.info(
                f"AE export enabled: fbx={fbx_output.name}, "
                f"frames={ae_frame_start}-{ae_frame_end}"
            )
        else:
            # 禁用 AE 导出时占位符替换为注释，保持模板合法
            ae_export_block = "# AE export disabled (export_ae=False)"
            ae_marker_lines = ""

        script_content = self.STAGE_TEMPLATE.format(
            stage_w=preset["stage_w"],
            stage_h=preset["stage_h"],
            stage_d=preset["stage_d"],
            wood_color=self._color_tuple(preset["wood_color"]),
            roughness=preset["roughness"],
            light_height=4.0,
            key_light_intensity=1500,
            fill_light_intensity=500,
            rim_light_intensity=800,
            light_size=3.0,
            camera_distance=10.0,
            camera_height=2.5,
            camera_pitch=1.1,
            focal_length=50,
            render_engine=render_engine,
            resolution_x=resolution[0],
            resolution_y=resolution[1],
            output_format="PNG",
            blend_output=str(blend_output).replace("\\", "\\\\"),
            render_output=str(render_output).replace("\\", "\\\\"),
            marker_path=str(marker_path).replace("\\", "\\\\"),
            ae_export_block=ae_export_block,
            ae_marker_lines=ae_marker_lines,
        )

        script_file = Path(tempfile.gettempdir()) / f"bl_stage_{output_dir.name}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "--background", "--python", str(script_file)]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=3600
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        # 收集 AE 资产导出结果
        metadata: dict[str, Any] = {
            "style": style,
            "render_engine": render_engine,
            "resolution": resolution,
            "render_output": str(render_output),
            "stdout_tail": stdout[-500:] if stdout else "",
        }
        if export_ae:
            frames_list = sorted(frames_output.glob("*.png")) if frames_output.exists() else []
            metadata["fbx_path"] = str(fbx_output) if fbx_output.exists() else None
            metadata["frames_dir"] = str(frames_output) if frames_output.exists() else None
            metadata["frame_count"] = len(frames_list)
            metadata["ae_export"] = bool(fbx_output.exists())

        return EngineResult(
            success=success,
            output_path=blend_output if success else None,
            metadata=metadata,
            error=stderr[:1000] if not success and stderr else None,
        )

    async def run_script(
        self,
        script_content: str,
        blend_file: Optional[Path | str] = None,
        background: bool = True,
    ) -> EngineResult:
        """Run a custom Blender Python script.

        Args:
            script_content: Python script text
            blend_file: Optional .blend file to open first
            background: Run in background mode
        """
        script_file = Path(tempfile.gettempdir()) / "bl_custom_script.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path)]
        if background:
            cmd.append("--background")
        if blend_file:
            cmd.append(str(Path(blend_file)))
        cmd.extend(["--python", str(script_file)])

        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        script_file.unlink(missing_ok=True)

        return EngineResult(
            success=code == 0,
            metadata={
                "stdout_length": len(stdout),
                "stdout_tail": stdout[-1000:] if stdout else "",
            },
            error=stderr[:1000] if code != 0 else None,
        )

    async def render_animation(
        self,
        blend_file: Path | str,
        output_dir: Path | str,
        frame_start: int = 1,
        frame_end: int = 250,
        engine: str = "BLENDER_EEVEE",
    ) -> EngineResult:
        """Render animation from a .blend file."""
        blend_file = Path(blend_file)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.executable_path),
            "--background", str(blend_file),
            "--engine", engine,
            "--frame-start", str(frame_start),
            "--frame-end", str(frame_end),
            "--render-anim",
            "--render-output", str(output_dir) + "/",
        ]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=86400
        )

        frames = list(output_dir.glob("*.png")) + list(output_dir.glob("*.exr"))
        return EngineResult(
            success=code == 0,
            output_path=output_dir if code == 0 else None,
            metadata={
                "frame_count": len(frames),
                "engine": engine,
                "frame_range": [frame_start, frame_end],
            },
            error=stderr[:1000] if code != 0 else None,
        )

    async def export_for_ae(
        self,
        blend_path: Path | str,
        output_dir: Path | str,
        frame_start: int = 1,
        frame_end: int = 60,
    ) -> EngineResult:
        """导出 3D 资产供 After Effects 使用。

        将已有的 .blend 文件转换为 AE 可导入的格式：
        1. FBX 文件 - 通过 bpy.ops.export_scene.fbx 导出，可由 AE 的
           Element 3D / Cinema 4D Lite / Cineware 等插件直接加载。
        2. PNG 序列帧 - 通过 bpy.ops.render.render(animation=True) 渲染，
           可在 AE 中作为 3D 背景层叠加使用。

        与 create_puppet_stage(export_ae=True) 的区别：
        - 此方法针对已存在的 .blend 文件单独运行，适用于复用已有场景
        - create_puppet_stage(export_ae=True) 在场景生成的同时一并导出，
          效率更高（单次 Blender 进程）

        Args:
            blend_path: 已存在的 .blend 文件路径
            output_dir: 输出目录（FBX 和 frames 子目录将创建于此）
            frame_start: PNG 序列帧起始帧
            frame_end: PNG 序列帧结束帧
        """
        blend_path = Path(blend_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not blend_path.exists():
            return EngineResult(
                success=False,
                error=f"Blend file not found: {blend_path}",
            )

        # 输出路径
        fbx_output = output_dir / "stage_export.fbx"
        frames_output = output_dir / "frames"
        frames_output.mkdir(parents=True, exist_ok=True)
        marker_path = Path(tempfile.gettempdir()) / f"bl_ae_export_{output_dir.name}.mark"

        # 路径转义（与 create_puppet_stage 保持一致：raw string 中使用双反斜杠）
        blend_path_escaped = str(blend_path).replace("\\", "\\\\")
        fbx_path_escaped = str(fbx_output).replace("\\", "\\\\")
        frames_path_escaped = str(frames_output).replace("\\", "\\\\")
        marker_path_escaped = str(marker_path).replace("\\", "\\\\")

        script_content = self.EXPORT_AE_TEMPLATE.format(
            blend_path=blend_path_escaped,
            fbx_output=fbx_path_escaped,
            frames_output=frames_path_escaped,
            ae_frame_start=frame_start,
            ae_frame_end=frame_end,
            marker_path=marker_path_escaped,
        )

        script_file = Path(tempfile.gettempdir()) / f"bl_ae_export_{output_dir.name}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "--background", "--python", str(script_file)]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=3600
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        # 收集序列帧产物
        frames_list = sorted(frames_output.glob("*.png")) if frames_output.exists() else []

        logger.info(
            f"[Blender] AE export done: fbx={fbx_output.exists()}, "
            f"frames={len(frames_list)}"
        )

        return EngineResult(
            success=success,
            output_path=fbx_output if success and fbx_output.exists() else None,
            metadata={
                "fbx_path": str(fbx_output) if fbx_output.exists() else None,
                "frames_dir": str(frames_output) if frames_output.exists() else None,
                "frame_count": len(frames_list),
                "frame_range": [frame_start, frame_end],
                "blend_source": str(blend_path),
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def export_camera_data(
        self,
        blend_file: Path | str,
        output_path: Path | str,
    ) -> EngineResult:
        """导出相机数据供 AE 使用。

        从 .blend 文件中提取相机位置、旋转、焦距等数据，
        输出为 JSON 格式，可在 AE 中通过脚本重建相机运动。

        Args:
            blend_file: Blender 场景文件路径
            output_path: 输出 JSON 文件路径

        Returns:
            EngineResult 包含相机数据
        """
        import json

        blend_file = Path(blend_file)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not blend_file.exists():
            return EngineResult(
                success=False,
                error=f"Blend file not found: {blend_file}",
            )

        blend_path_esc = str(blend_file).replace("\\", "\\\\")
        output_path_esc = str(output_path).replace("\\", "\\\\")
        script_content = f"""
import bpy
import json

bpy.ops.wm.open_mainfile(filepath=r"{blend_path_esc}")

cameras = []
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        scene = bpy.context.scene
        frames = []
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            loc = obj.location
            rot = obj.rotation_euler
            cameras.append({{
                "name": obj.name,
                "frame": frame,
                "location": [loc.x, loc.y, loc.z],
                "rotation": [rot.x, rot.y, rot.z],
                "focal_length": obj.data.lens,
                "sensor_width": obj.data.sensor_width,
            }})

with open(r"{output_path_esc}", "w") as f:
    json.dump({{"cameras": cameras}}, f, indent=2)
"""
        result = await self.run_script(script_content)
        if result.success and output_path.exists():
            return EngineResult(
                success=True,
                output_path=output_path,
                metadata={"camera_data_path": str(output_path)},
            )
        return EngineResult(
            success=False,
            error="Camera export failed",
            metadata=result.metadata,
        )

    async def render_foreground_element(
        self,
        output_dir: Path | str,
        element_type: str = "logo",
        element_params: dict[str, Any] | None = None,
        resolution: tuple[int, int] = (1920, 1080),
        frame_start: int = 1,
        frame_end: int = 60,
        engine: str = "BLENDER_EEVEE",
        transparent_background: bool = True,
    ) -> EngineResult:
        """渲染 3D 前景元素（带 Alpha 通道）。

        生成可用于 AE 合成的 3D 前景元素，支持多种类型：
        - logo: 3D Logo 动画
        - text: 3D 文字
        - particles: 粒子效果
        - decoration: 装饰性元素

        Args:
            output_dir: 输出目录（PNG 序列帧将输出到此目录）
            element_type: 元素类型（logo, text, particles, decoration）
            element_params: 元素参数字典（根据类型不同而不同）
            resolution: 输出分辨率 (width, height)
            frame_start: 起始帧
            frame_end: 结束帧
            engine: 渲染引擎（BLENDER_EEVEE / CYCLES）
            transparent_background: 是否使用透明背景

        Returns:
            EngineResult: 渲染结果，metadata 包含 frames_dir, frame_count
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_output = output_dir / "frames"
        frames_output.mkdir(parents=True, exist_ok=True)
        marker_path = Path(tempfile.gettempdir()) / f"bl_fg_{output_dir.name}.mark"

        element_params = element_params or {}
        color = self._color_tuple(element_params.get("color", "#FFFFFF"))
        text_content = element_params.get("text", "3D TEXT")
        extrusion_depth = element_params.get("extrusion_depth", 0.2)
        bevel_size = element_params.get("bevel_size", 0.02)
        rotation_speed = element_params.get("rotation_speed", 0.5)
        float_amplitude = element_params.get("float_amplitude", 0.1)

        frames_path_escaped = str(frames_output).replace("\\", "\\\\")
        marker_path_escaped = str(marker_path).replace("\\", "\\\\")

        script_content = f"""
import bpy
import math
import os

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

scene = bpy.context.scene
scene.render.engine = '{engine}'
scene.render.resolution_x = {resolution[0]}
scene.render.resolution_y = {resolution[1]}
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.frame_start = {frame_start}
scene.frame_end = {frame_end}

if {transparent_background}:
    scene.render.film_transparent = True

if '{element_type}' == 'text':
    bpy.ops.object.text_add(location=(0, 0, 0))
    text_obj = bpy.context.active_object
    text_obj.data.body = "{text_content}"
    text_obj.data.size = 1.0
    text_obj.data.align_x = 'CENTER'
    text_obj.data.align_y = 'CENTER'

    text_obj.data.extrude = {extrusion_depth}
    text_obj.data.bevel_depth = {bevel_size}
    text_obj.data.bevel_resolution = 4

    mat = bpy.data.materials.new(name="ElementMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = {color}
    bsdf.inputs['Metallic'].default_value = 0.8
    bsdf.inputs['Roughness'].default_value = 0.2
    if text_obj.data.materials:
        text_obj.data.materials[0] = mat
    else:
        text_obj.data.materials.append(mat)

    text_obj.keyframe_insert(data_path="rotation_euler", frame={frame_start})
    text_obj.rotation_euler.z = 2 * math.pi * {rotation_speed}
    text_obj.keyframe_insert(data_path="rotation_euler", frame={frame_end})

    text_obj.keyframe_insert(data_path="location", frame={frame_start})
    text_obj.location.z = {float_amplitude}
    text_obj.keyframe_insert(data_path="location", frame={frame_start} + ({frame_end} - {frame_start}) // 2)
    text_obj.location.z = 0
    text_obj.keyframe_insert(data_path="location", frame={frame_end})

elif '{element_type}' == 'logo':
    bpy.ops.mesh.primitive_cube_add(size=1)
    cube = bpy.context.active_object
    cube.scale = (1.5, 0.1, 1.0)

    mat = bpy.data.materials.new(name="ElementMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = {color}
    bsdf.inputs['Metallic'].default_value = 0.9
    bsdf.inputs['Roughness'].default_value = 0.1
    if cube.data.materials:
        cube.data.materials[0] = mat
    else:
        cube.data.materials.append(mat)

    cube.keyframe_insert(data_path="rotation_euler", frame={frame_start})
    cube.rotation_euler.y = 2 * math.pi * {rotation_speed}
    cube.keyframe_insert(data_path="rotation_euler", frame={frame_end})

elif '{element_type}' == 'particles':
    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.05, location=(0, 0, 0))
    particle_obj = bpy.context.active_object

    mat = bpy.data.materials.new(name="ParticleMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = {color}
    bsdf.inputs['Emission'].default_value = {color}
    bsdf.inputs['Emission Strength'].default_value = 2.0
    if particle_obj.data.materials:
        particle_obj.data.materials[0] = mat
    else:
        particle_obj.data.materials.append(mat)

    particle_obj.modifiers.new(name="ParticleSystem", type='PARTICLE_SYSTEM')
    ps = particle_obj.particle_systems[0]
    ps.settings.count = 200
    ps.settings.frame_start = {frame_start}
    ps.settings.frame_end = {frame_end}
    ps.settings.lifetime = 30
    ps.settings.normal_factor = 2.0
    ps.settings.render_type = 'HALO'
    ps.settings.particle_size = 0.05
else:
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.1, location=(0, 0, 0))
    deco = bpy.context.active_object

    mat = bpy.data.materials.new(name="ElementMaterial")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs['Base Color'].default_value = {color}
    bsdf.inputs['Metallic'].default_value = 0.7
    bsdf.inputs['Roughness'].default_value = 0.3
    if deco.data.materials:
        deco.data.materials[0] = mat
    else:
        deco.data.materials.append(mat)

    deco.keyframe_insert(data_path="rotation_euler", frame={frame_start})
    deco.rotation_euler.z = 2 * math.pi * {rotation_speed}
    deco.keyframe_insert(data_path="rotation_euler", frame={frame_end})

bpy.ops.object.camera_add(location=(0, -5, 2))
cam = bpy.context.active_object
cam.rotation_euler = (1.1, 0, 0)
cam.data.lens = 50
scene.camera = cam

bpy.ops.object.light_add(type='AREA', location=(2, -3, 3))
key_light = bpy.context.active_object
key_light.data.energy = 1000
key_light.data.size = 2

bpy.ops.object.light_add(type='AREA', location=(-2, -3, 2))
fill_light = bpy.context.active_object
fill_light.data.energy = 300
fill_light.data.size = 2

frames_dir = r"{frames_path_escaped}"
os.makedirs(frames_dir, exist_ok=True)
scene.render.filepath = os.path.join(frames_dir, "")
bpy.ops.render.render(animation=True)

with open(r"{marker_path_escaped}", "w") as f:
    f.write("SUCCESS\\n")
    f.write(f"frames: {frames_dir}\\n")
"""

        script_file = Path(tempfile.gettempdir()) / f"bl_fg_{output_dir.name}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "--background", "--python", str(script_file)]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        frames_list = sorted(frames_output.glob("*.png")) if frames_output.exists() else []

        logger.info(
            f"[Blender] Foreground element render done: type={element_type}, "
            f"frames={len(frames_list)}"
        )

        return EngineResult(
            success=success,
            output_path=frames_output if success else None,
            metadata={
                "element_type": element_type,
                "frames_dir": str(frames_output) if frames_output.exists() else None,
                "frame_count": len(frames_list),
                "frame_range": [frame_start, frame_end],
                "engine": engine,
                "transparent": transparent_background,
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def export_camera_data(
        self,
        blend_path: Path | str,
        output_path: Path | str,
        camera_name: str = "Camera",
        frame_start: int = 1,
        frame_end: int = 60,
    ) -> EngineResult:
        """导出摄像机数据给 After Effects。

        将 Blender 中的摄像机动画数据导出为 JSON 格式，
        包含位置、旋转、焦距等关键帧数据，可在 AE 中用于：
        - 3D 摄像机跟踪匹配
        - 摄像机动画同步
        - 景深效果匹配

        Args:
            blend_path: 已存在的 .blend 文件路径
            output_path: 输出 JSON 文件路径
            camera_name: 摄像机名称（默认 "Camera"）
            frame_start: 起始帧
            frame_end: 结束帧

        Returns:
            EngineResult: 导出结果，metadata 包含 output_path, frame_count
        """
        blend_path = Path(blend_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not blend_path.exists():
            return EngineResult(
                success=False,
                error=f"Blend file not found: {blend_path}",
            )

        marker_path = Path(tempfile.gettempdir()) / f"bl_cam_{output_path.stem}.mark"

        blend_path_escaped = str(blend_path).replace("\\", "\\\\")
        output_path_escaped = str(output_path).replace("\\", "\\\\")
        marker_path_escaped = str(marker_path).replace("\\", "\\\\")

        script_content = f"""
import bpy
import json
import math

bpy.ops.wm.open_mainfile(filepath=r"{blend_path_escaped}")

cam = bpy.data.objects.get("{camera_name}")
if cam is None:
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            cam = obj
            break

if cam is None:
    with open(r"{marker_path_escaped}", "w") as f:
        f.write("ERROR\\n")
        f.write("Camera not found\\n")
    exit(1)

camera_data = {{
    "camera_name": cam.name,
    "type": "perspective",
    "sensor_width": cam.data.sensor_width,
    "sensor_height": cam.data.sensor_height,
    "lens": cam.data.lens,
    "focal_length": cam.data.lens,
    "frame_start": {frame_start},
    "frame_end": {frame_end},
    "fps": bpy.context.scene.render.fps,
    "resolution": [
        bpy.context.scene.render.resolution_x,
        bpy.context.scene.render.resolution_y
    ],
    "keyframes": []
}}

for frame in range({frame_start}, {frame_end} + 1):
    bpy.context.scene.frame_set(frame)
    keyframe = {{
        "frame": frame,
        "position": [
            cam.location.x,
            cam.location.y,
            cam.location.z
        ],
        "rotation_euler": [
            cam.rotation_euler.x,
            cam.rotation_euler.y,
            cam.rotation_euler.z
        ],
        "rotation_quaternion": [
            cam.rotation_quaternion.w,
            cam.rotation_quaternion.x,
            cam.rotation_quaternion.y,
            cam.rotation_quaternion.z
        ],
        "scale": [
            cam.scale.x,
            cam.scale.y,
            cam.scale.z
        ],
        "lens": cam.data.lens,
        "f_stop": cam.data.dof.aperture_fstop if cam.data.dof else 0,
        "focus_distance": cam.data.dof.focus_distance if cam.data.dof else 10,
    }}
    camera_data["keyframes"].append(keyframe)

with open(r"{output_path_escaped}", "w", encoding="utf-8") as f:
    json.dump(camera_data, f, ensure_ascii=False, indent=2)

with open(r"{marker_path_escaped}", "w") as f:
    f.write("SUCCESS\\n")
    f.write(f"output: {output_path_escaped}\\n")
    f.write(f"keyframes: {len(camera_data['keyframes'])}\\n")
"""

        script_file = Path(tempfile.gettempdir()) / f"bl_cam_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "--background", "--python", str(script_file)]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=3600
        )

        success = code == 0 and marker_path.exists() and output_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        logger.info(
            f"[Blender] Camera data export done: {output_path.name}, "
            f"frames={frame_end - frame_start + 1}"
        )

        return EngineResult(
            success=success,
            output_path=output_path if success else None,
            metadata={
                "camera_name": camera_name,
                "frame_count": frame_end - frame_start + 1,
                "frame_range": [frame_start, frame_end],
                "output_format": "json",
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def execute(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "create_puppet_stage")
        handlers = {
            "create_puppet_stage": self.create_puppet_stage,
            "run_script": self.run_script,
            "render_animation": self.render_animation,
            "export_for_ae": self.export_for_ae,
            "render_foreground_element": self.render_foreground_element,
            "export_camera_data": self.export_camera_data,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)


# ========================================================================
# P2 分层渲染管线 - 类级别别名（必须在类定义完成后设置）
# ========================================================================

BlenderEngine.render_foreground_layer = BlenderEngine.render_foreground_element
