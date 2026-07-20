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

    async def execute(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "create_puppet_stage")
        handlers = {
            "create_puppet_stage": self.create_puppet_stage,
            "run_script": self.run_script,
            "render_animation": self.render_animation,
            "export_for_ae": self.export_for_ae,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)
