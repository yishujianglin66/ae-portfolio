"""Cinema 4D 2026 engine - 3D scene generation + MoGraph via c4dpy Python API.

通过 c4dpy.exe（独立 Python 解释器，预装 c4d 模块）执行 Python 脚本，
实现 3D 场景渲染、FBX 导出、相机数据导出与 MoGraph 运动图形生成。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class Cinema4DEngine(BaseEngine):
    """Cinema 4D 2026 引擎，通过 c4dpy CLI 执行 Python 脚本。

    支持的操作：
    - render_scene: 渲染 3D 场景（舞台/Logo/文字/粒子/装饰）为 PNG 序列帧
    - export_fbx: 导出 FBX 文件（供 AE Element 3D / Cineware 使用）
    - export_camera_data: 导出相机动画数据为 JSON（供 AE 重建相机运动）
    - render_motion_graphics: 渲染 MoGraph 运动图形动画
    - run_python_script: 通用 Python 脚本执行接口
    """

    name = "cinema4d"

    # ===================================================================
    # 场景渲染脚本模板（render_scene）
    # ===================================================================
    SCENE_RENDER_TEMPLATE = '''
"""Auto-generated Cinema 4D scene render script."""
from __future__ import annotations
import os
import sys
import c4d
from c4d import documents, gui, plugins

def main():
    doc = documents.GetActiveDocument()
    if doc is None:
        doc = c4d.documents.BaseDocument()

    # 清空默认场景
    while doc.GetFirstObject():
        obj = doc.GetFirstObject()
        doc.InsertObject(obj, None, None, True) if False else None
        obj.Remove()

    scene_type = "{scene_type}"
    res_w = {resolution_x}
    res_h = {resolution_y}
    frame_start = {frame_start}
    frame_end = {frame_end}
    render_engine = "{render_engine}"
    frames_dir = r"{frames_output}"

    os.makedirs(frames_dir, exist_ok=True)

    # ---- 根据场景类型创建几何 ----
    if scene_type == "stage":
        # 舞台：地板 + 背板
        floor = c4d.BaseObject(c4d.Oplane)
        floor.SetName("Stage_Floor")
        floor[c4d.PRIM_PLANE_WIDTH] = 20.0
        floor[c4d.PRIM_PLANE_HEIGHT] = 12.0
        doc.InsertObject(floor)

        back = c4d.BaseObject(c4d.Oplane)
        back.SetName("Stage_Back")
        back[c4d.PRIM_PLANE_WIDTH] = 20.0
        back[c4d.PRIM_PLANE_HEIGHT] = 10.0
        back.SetAbsPos(c4d.Vector(0, 5, -6))
        back.SetAbsRot(c4d.Vector(0, 0, 0))
        doc.InsertObject(back)

    elif scene_type == "logo":
        # Logo 立方体
        cube = c4d.BaseObject(c4d.Ocube)
        cube.SetName("Logo_Cube")
        cube[c4d.PRIM_CUBE_LEN] = c4d.Vector(3.0, 0.3, 2.0)
        doc.InsertObject(cube)

    elif scene_type == "text":
        # 3D 文字（MoText）
        text_obj = c4d.BaseObject(c4d.Otext)
        text_obj.SetName("Title_Text")
        text_obj[c4d.PRIM_TEXT_TEXT] = "C4D TITLE"
        text_obj[c4d.PRIM_TEXT_ALIGN] = c4d.PRIM_TEXT_ALIGN_MIDDLE
        text_obj[c4d.PRIM_TEXT_HEIGHT] = 2.0
        text_obj[c4d.PRIM_TEXT_DEPTH] = 0.3
        doc.InsertObject(text_obj)

    elif scene_type == "particles":
        # 粒子源（Emitter）
        emitter = c4d.BaseObject(c4d.Oparticle)
        emitter.SetName("Particle_Emitter")
        emitter[c4d.PARTICLEOBJECT_BIRTHRATE] = 200
        emitter[c4d.PARTICLEOBJECT_LIFETIME] = 60.0
        doc.InsertObject(emitter)

    else:  # decoration
        torus = c4d.BaseObject(c4d.Otorus)
        torus.SetName("Decoration_Torus")
        torus[c4d.PRIM_TORUS_RADIUS] = 2.0
        torus[c4d.PRIM_TORUS_TUBERADIUS] = 0.2
        doc.InsertObject(torus)

    # ---- 相机 ----
    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName("Main_Camera")
    cam.SetAbsPos(c4d.Vector(0, 5, 15))
    cam.SetAbsRot(c4d.utils.VectorToHPB(c4d.Vector(0, -3, 0)))
    cam[c4d.CAMERAOBJECT_FOV] = 45.0
    doc.InsertObject(cam)
    doc.SetActiveObject(cam)

    # ---- 灯光 ----
    key_light = c4d.BaseObject(c4d.Olight)
    key_light.SetName("Key_Light")
    key_light.SetAbsPos(c4d.Vector(5, 10, 5))
    key_light[c4d.LIGHT_BRIGHTNESS] = 0.8
    doc.InsertObject(key_light)

    fill_light = c4d.BaseObject(c4d.Olight)
    fill_light.SetName("Fill_Light")
    fill_light.SetAbsPos(c4d.Vector(-5, 5, 5))
    fill_light[c4d.LIGHT_BRIGHTNESS] = 0.3
    doc.InsertObject(fill_light)

    # ---- 渲染设置 ----
    rd = doc.GetActiveRenderData()
    if rd is None:
        rd = c4d.RenderData()
        doc.InsertRenderData(rd)
        rd = doc.GetActiveRenderData()

    rd[c4d.RDATA_XRES] = res_w
    rd[c4d.RDATA_YRES] = res_h
    rd[c4d.RDATA_FRAMESEQUENCE_FROM] = frame_start
    rd[c4d.RDATA_FRAMESEQUENCE_TO] = frame_end
    rd[c4d.RDATA_FORMAT] = c4d.FILTER_PNG
    rd[c4d.RDATA_FORMATDEPTH] = c4d.RDATA_FORMATDEPTH_8

    # 渲染引擎：standard / physical
    if render_engine == "physical":
        rd[c4d.RDATA_RENDERENGINE] = c4d.RENDERENGINE_PHYSICAL
    else:
        rd[c4d.RDATA_RENDERENGINE] = c4d.RENDERENGINE_STANDARD

    # 输出路径（PNG 序列）
    base_path = os.path.join(frames_dir, "frame_")
    rd[c4d.RDATA_PATH] = base_path

    c4d.EventAdd()

    # ---- 保存场景文件 ----
    c4d_path = r"{c4d_output}"
    documents.SaveDocument(doc, c4d_path, c4d.SAVEDOCUMENTFLAGS_0, c4d.FORMAT_C4DEXPORT)

    # ---- 渲染序列帧 ----
    for frame in range(frame_start, frame_end + 1):
        doc.SetTime(c4d.BaseTime(frame, 30))
        c4d.EventAdd()
        rd[c4d.RDATA_FRAMESEQUENCE_FROM] = frame
        rd[c4d.RDATA_FRAMESEQUENCE_TO] = frame
        frame_path = base_path + str(frame).zfill(4) + ".png"
        rd[c4d.RDATA_PATH] = frame_path
        bmp = c4d.bitmaps.BaseBitmap()
        bmp.Init(res_w, res_h)
        if documents.RenderDocument(doc, rd, bmp, c4d.RENDERFLAGS_EXTERNAL) == c4d.RENDERRESULT_OK:
            bmp.Save(frame_path, c4d.FILTER_PNG)
        else:
            print(f"WARN: render frame {{frame}} failed")

    # ---- 写标记文件 ----
    with open(r"{marker_path}", "w") as f:
        f.write("SUCCESS\\n")
        f.write(f"c4d: {{c4d_path}}\\n")
        f.write(f"frames_dir: {{frames_dir}}\\n")

    print("C4D render scene done")

if __name__ == "__main__":
    main()
'''

    # ===================================================================
    # FBX 导出脚本模板（export_fbx）
    # ===================================================================
    FBX_EXPORT_TEMPLATE = '''
"""Auto-generated Cinema 4D FBX export script."""
from __future__ import annotations
import c4d
from c4d import documents, plugins

def main():
    input_file = r"{input_file}"
    output_fbx = r"{output_fbx}"

    # 加载源文件
    doc = documents.LoadDocument(input_file, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS)
    if doc is None:
        print("ERROR: failed to load document: " + input_file)
        with open(r"{marker_path}", "w") as f:
            f.write("ERROR\\n")
            f.write("Failed to load document\\n")
        return

    # 调用 FBX 导出器插件
    fbx_exporter = plugins.FindPlugin(c4d.FORMAT_FBX_EXPORT, c4d.PLUGINTYPE_SCENELOADER)
    if fbx_exporter is None:
        fbx_exporter = plugins.FindPlugin(1026370, c4d.PLUGINTYPE_SCENELOADER)  # FBX EXPORT legacy id

    # 直接通过 SaveDocument 导出 FBX
    ok = documents.SaveDocument(doc, output_fbx, c4d.SAVEDOCUMENTFLAGS_DONTADDTOHISTORY, c4d.FORMAT_FBX_EXPORT)
    if not ok:
        # 尝试备用 format id
        ok = documents.SaveDocument(doc, output_fbx, c4d.SAVEDOCUMENTFLAGS_DONTADDTOHISTORY, 1026370)

    with open(r"{marker_path}", "w") as f:
        if ok:
            f.write("SUCCESS\\n")
            f.write(f"fbx: {{output_fbx}}\\n")
        else:
            f.write("ERROR\\n")
            f.write("FBX export failed\\n")

    print("C4D FBX export done: ok=" + str(ok))

if __name__ == "__main__":
    main()
'''

    # ===================================================================
    # 相机数据导出脚本模板（export_camera_data）
    # ===================================================================
    CAMERA_EXPORT_TEMPLATE = '''
"""Auto-generated Cinema 4D camera data export script."""
from __future__ import annotations
import json
import c4d
from c4d import documents

def main():
    input_file = r"{input_file}"
    output_json = r"{output_json}"

    doc = documents.LoadDocument(input_file, c4d.SCENEFILTER_OBJECTS | c4d.SCENEFILTER_MATERIALS)
    if doc is None:
        print("ERROR: failed to load document")
        with open(r"{marker_path}", "w") as f:
            f.write("ERROR\\n")
            f.write("Load failed\\n")
        return

    fps = doc.GetFps()
    frame_start = {frame_start}
    frame_end = {frame_end}

    cameras = []
    obj = doc.GetFirstObject()
    cam_objs = []
    while obj:
        if obj.GetType() == c4d.Ocamera:
            cam_objs.append(obj)
        child = obj.GetDown()
        if child:
            obj = child
        else:
            while obj and not obj.GetNext():
                obj = obj.GetUp()
            if obj:
                obj = obj.GetNext()

    for cam in cam_objs:
        for frame in range(frame_start, frame_end + 1):
            doc.SetTime(c4d.BaseTime(frame, fps))
            c4d.EventAdd()
            pos = cam.GetAbsPos()
            rot = cam.GetAbsRot()
            focal = cam[c4d.CAMERAOBJECT_FOCAL_LENGTH] if cam.HasKey(c4d.CAMERAOBJECT_FOCAL_LENGTH) else 50.0
            sensor = 36.0
            try:
                sensor = cam[c4d.CAMERAOBJECT_FILM_WIDTH] if cam.HasKey(c4d.CAMERAOBJECT_FILM_WIDTH) else 36.0
            except Exception:
                sensor = 36.0
            cameras.append({{
                "name": cam.GetName(),
                "frame": frame,
                "position": [pos.x, pos.y, pos.z],
                "rotation": [rot.x, rot.y, rot.z],
                "focal_length": focal,
                "sensor_width": sensor,
            }})

    out = {{
        "fps": fps,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "cameras": cameras,
    }}
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    with open(r"{marker_path}", "w") as f:
        f.write("SUCCESS\\n")
        f.write(f"json: {{output_json}}\\n")
        f.write(f"entries: {{len(cameras)}}\\n")

    print("C4D camera export done")

if __name__ == "__main__":
    main()
'''

    # ===================================================================
    # MoGraph 渲染脚本模板（render_motion_graphics）
    # ===================================================================
    MOGRAPH_RENDER_TEMPLATE = '''
"""Auto-generated Cinema 4D MoGraph render script."""
from __future__ import annotations
import os
import c4d
from c4d import documents

def main():
    doc = documents.GetActiveDocument()
    if doc is None:
        doc = c4d.documents.BaseDocument()

    preset = "{preset}"
    frame_start, frame_end = {frame_range}
    res_w = {resolution_x}
    res_h = {resolution_y}
    frames_dir = r"{frames_output}"
    os.makedirs(frames_dir, exist_ok=True)

    # MoGraph Cloner 对象 ID = 1018544
    cloner = c4d.BaseObject(1018544)
    cloner.SetName("MoGraph_Cloner")
    cloner[c4d.ID_MG_CLUSTER_MODE] = 0  # 网格模式

    # 子对象：基础几何
    cube = c4d.BaseObject(c4d.Ocube)
    cube.SetName("Cube_Instance")
    cube[c4d.PRIM_CUBE_LEN] = c4d.Vector(0.5, 0.5, 0.5)
    cube.InsertUnder(cloner)

    cloner[c4d.MG_GRID_RESOLUTION] = c4d.Vector(5, 5, 1)
    cloner[c4d.MG_GRID_SIZE] = c4d.Vector(5.0, 5.0, 0.0)
    doc.InsertObject(cloner)

    # 根据预设配置相机与渲染
    if preset == "lower_third":
        cam_pos = c4d.Vector(0, -3, 8)
        rd_res = (1920, 1080)
    elif preset == "title_card":
        cam_pos = c4d.Vector(0, 0, 12)
        rd_res = (1920, 1080)
    elif preset == "logo_sting":
        cam_pos = c4d.Vector(2, 2, 10)
        rd_res = (1920, 1080)
    else:  # background_loop
        cam_pos = c4d.Vector(0, 5, 15)
        rd_res = (1920, 1080)

    cam = c4d.BaseObject(c4d.Ocamera)
    cam.SetName("MoGraph_Camera")
    cam.SetAbsPos(cam_pos)
    doc.InsertObject(cam)
    doc.SetActiveObject(cam)

    light = c4d.BaseObject(c4d.Olight)
    light.SetAbsPos(c4d.Vector(5, 10, 5))
    light[c4d.LIGHT_BRIGHTNESS] = 0.8
    doc.InsertObject(light)

    rd = doc.GetActiveRenderData()
    if rd is None:
        rd = c4d.RenderData()
        doc.InsertRenderData(rd)
        rd = doc.GetActiveRenderData()

    rd[c4d.RDATA_XRES] = res_w
    rd[c4d.RDATA_YRES] = res_h
    rd[c4d.RDATA_FRAMESEQUENCE_FROM] = frame_start
    rd[c4d.RDATA_FRAMESEQUENCE_TO] = frame_end
    rd[c4d.RDATA_FORMAT] = c4d.FILTER_PNG
    rd[c4d.RDATA_RENDERENGINE] = c4d.RENDERENGINE_STANDARD

    base_path = os.path.join(frames_dir, "mograph_")
    fps = doc.GetFps() or 30

    for frame in range(frame_start, frame_end + 1):
        doc.SetTime(c4d.BaseTime(frame, fps))
        c4d.EventAdd()
        rd[c4d.RDATA_FRAMESEQUENCE_FROM] = frame
        rd[c4d.RDATA_FRAMESEQUENCE_TO] = frame
        frame_path = base_path + str(frame).zfill(4) + ".png"
        rd[c4d.RDATA_PATH] = frame_path
        bmp = c4d.bitmaps.BaseBitmap()
        bmp.Init(res_w, res_h)
        if documents.RenderDocument(doc, rd, bmp, c4d.RENDERFLAGS_EXTERNAL) == c4d.RENDERRESULT_OK:
            bmp.Save(frame_path, c4d.FILTER_PNG)
        else:
            print(f"WARN: mograph frame {{frame}} failed")

    # 保存工程文件
    c4d_proj = r"{c4d_output}"
    documents.SaveDocument(doc, c4d_proj, c4d.SAVEDOCUMENTFLAGS_0, c4d.FORMAT_C4DEXPORT)

    with open(r"{marker_path}", "w") as f:
        f.write("SUCCESS\\n")
        f.write(f"c4d: {{c4d_proj}}\\n")
        f.write(f"frames_dir: {{frames_dir}}\\n")

    print("C4D MoGraph render done")

if __name__ == "__main__":
    main()
'''

    # ===================================================================
    # 构造与初始化
    # ===================================================================
    def __init__(self, executable_path: Optional[Path | str] = None):
        """初始化 Cinema4D 引擎。

        Args:
            executable_path: c4dpy.exe 路径。若为空则使用 settings.c4dpy_executable。
        """
        path = Path(executable_path) if executable_path else settings.c4dpy_executable
        super().__init__(path)
        # 同时保留 Cinema 4D.exe 路径，便于将来需要 GUI 模式时使用
        self.c4d_executable: Path = settings.c4d_executable

    # ===================================================================
    # 1. render_scene - 渲染 3D 场景为 PNG 序列帧
    # ===================================================================
    async def render_scene(
        self,
        output_dir: Path | str,
        scene_type: str = "stage",
        resolution: tuple[int, int] = (1920, 1080),
        frame_start: int = 1,
        frame_end: int = 60,
        engine: str = "standard",
    ) -> EngineResult:
        """渲染 3D 场景，生成 PNG 序列帧。

        Args:
            output_dir: 输出目录（frames 子目录将创建于此）
            scene_type: 场景类型 ("stage" / "logo" / "text" / "particles" / "decoration")
            resolution: 输出分辨率 (width, height)
            frame_start: 起始帧
            frame_end: 结束帧
            engine: 渲染引擎 ("standard" / "physical")

        Returns:
            EngineResult: metadata 包含 frames_dir / frame_count / c4d_path
        """
        valid_types = {"stage", "logo", "text", "particles", "decoration"}
        if scene_type not in valid_types:
            return EngineResult(
                success=False,
                error=f"Invalid scene_type '{scene_type}'. Valid: {sorted(valid_types)}",
                error_code="PARAM_INVALID",
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_output = output_dir / "frames"
        frames_output.mkdir(parents=True, exist_ok=True)
        c4d_output = output_dir / f"scene_{scene_type}.c4d"
        marker_path = Path(tempfile.gettempdir()) / f"c4d_scene_{output_dir.name}.mark"

        script_content = self.SCENE_RENDER_TEMPLATE.format(
            scene_type=scene_type,
            resolution_x=resolution[0],
            resolution_y=resolution[1],
            frame_start=frame_start,
            frame_end=frame_end,
            render_engine=engine,
            frames_output=str(frames_output).replace("\\", "\\\\"),
            c4d_output=str(c4d_output).replace("\\", "\\\\"),
            marker_path=str(marker_path).replace("\\", "\\\\"),
        )

        result = await self._run_c4dpy_script(script_content, marker_path)
        frames_list = sorted(frames_output.glob("*.png")) if frames_output.exists() else []

        metadata: dict[str, Any] = {
            "scene_type": scene_type,
            "engine": engine,
            "resolution": resolution,
            "frame_range": [frame_start, frame_end],
            "frames_dir": str(frames_output) if frames_output.exists() else None,
            "frame_count": len(frames_list),
            "c4d_path": str(c4d_output) if c4d_output.exists() else None,
        }
        metadata.update(result.pop("metadata_extra", {}))

        return EngineResult(
            success=result["success"],
            output_path=frames_output if result["success"] else None,
            metadata=metadata,
            error=result.get("error"),
        )

    # ===================================================================
    # 2. export_fbx - 导出 FBX 文件
    # ===================================================================
    async def export_fbx(
        self,
        input_file: Path | str,
        output_fbx: Path | str,
    ) -> EngineResult:
        """导出 FBX 文件（供 AE Element 3D / Cineware 使用）。

        Args:
            input_file: 源 .c4d 文件路径
            output_fbx: 输出 .fbx 文件路径

        Returns:
            EngineResult: output_path 为 fbx 文件路径
        """
        input_file = Path(input_file)
        output_fbx = Path(output_fbx)
        output_fbx.parent.mkdir(parents=True, exist_ok=True)

        if not input_file.exists():
            return EngineResult(
                success=False,
                error=f"Input file not found: {input_file}",
                error_code="FILE_NOT_FOUND",
            )

        marker_path = Path(tempfile.gettempdir()) / f"c4d_fbx_{output_fbx.stem}.mark"

        script_content = self.FBX_EXPORT_TEMPLATE.format(
            input_file=str(input_file).replace("\\", "\\\\"),
            output_fbx=str(output_fbx).replace("\\", "\\\\"),
            marker_path=str(marker_path).replace("\\", "\\\\"),
        )

        result = await self._run_c4dpy_script(script_content, marker_path)

        return EngineResult(
            success=result["success"] and output_fbx.exists(),
            output_path=output_fbx if output_fbx.exists() else None,
            metadata={
                "input_file": str(input_file),
                "fbx_path": str(output_fbx) if output_fbx.exists() else None,
            },
            error=result.get("error"),
        )

    # ===================================================================
    # 3. export_camera_data - 导出相机动画数据为 JSON
    # ===================================================================
    async def export_camera_data(
        self,
        blend_file: Path | str,
        output_json: Path | str,
        frame_start: int = 1,
        frame_end: int = 60,
    ) -> EngineResult:
        """导出相机动画数据为 JSON（供 AE 重建相机运动）。

        Args:
            blend_file: 源 .c4d 文件路径（参数名沿用 blend_file 以保持接口一致性）
            output_json: 输出 JSON 文件路径
            frame_start: 起始帧
            frame_end: 结束帧

        Returns:
            EngineResult: metadata 包含 camera_entries 数量
        """
        input_file = Path(blend_file)
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)

        if not input_file.exists():
            return EngineResult(
                success=False,
                error=f"Input file not found: {input_file}",
                error_code="FILE_NOT_FOUND",
            )

        marker_path = Path(tempfile.gettempdir()) / f"c4d_cam_{output_json.stem}.mark"

        script_content = self.CAMERA_EXPORT_TEMPLATE.format(
            input_file=str(input_file).replace("\\", "\\\\"),
            output_json=str(output_json).replace("\\", "\\\\"),
            frame_start=frame_start,
            frame_end=frame_end,
            marker_path=str(marker_path).replace("\\", "\\\\"),
        )

        result = await self._run_c4dpy_script(script_content, marker_path)

        # 解析 JSON 文件获取相机条数
        camera_count = 0
        if output_json.exists():
            try:
                data = json.loads(output_json.read_text(encoding="utf-8"))
                camera_count = len(data.get("cameras", []))
            except (json.JSONDecodeError, OSError):
                pass

        return EngineResult(
            success=result["success"] and output_json.exists(),
            output_path=output_json if output_json.exists() else None,
            metadata={
                "input_file": str(input_file),
                "json_path": str(output_json) if output_json.exists() else None,
                "camera_entries": camera_count,
                "frame_range": [frame_start, frame_end],
            },
            error=result.get("error"),
        )

    # ===================================================================
    # 4. render_motion_graphics - 渲染 MoGraph 运动图形
    # ===================================================================
    async def render_motion_graphics(
        self,
        output_dir: Path | str,
        preset: str = "lower_third",
        frame_range: tuple[int, int] = (1, 60),
        resolution: tuple[int, int] = (1920, 1080),
    ) -> EngineResult:
        """渲染运动图形（MoGraph）动画。

        Args:
            output_dir: 输出目录
            preset: 预设 ("lower_third" / "title_card" / "logo_sting" / "background_loop")
            frame_range: 帧范围 (start, end)
            resolution: 输出分辨率

        Returns:
            EngineResult: metadata 包含 frames_dir / frame_count / preset
        """
        valid_presets = {"lower_third", "title_card", "logo_sting", "background_loop"}
        if preset not in valid_presets:
            return EngineResult(
                success=False,
                error=f"Invalid preset '{preset}'. Valid: {sorted(valid_presets)}",
                error_code="PARAM_INVALID",
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        frames_output = output_dir / "frames"
        frames_output.mkdir(parents=True, exist_ok=True)
        c4d_output = output_dir / f"mograph_{preset}.c4d"
        marker_path = Path(tempfile.gettempdir()) / f"c4d_mg_{output_dir.name}.mark"

        script_content = self.MOGRAPH_RENDER_TEMPLATE.format(
            preset=preset,
            frame_range=frame_range,
            resolution_x=resolution[0],
            resolution_y=resolution[1],
            frames_output=str(frames_output).replace("\\", "\\\\"),
            c4d_output=str(c4d_output).replace("\\", "\\\\"),
            marker_path=str(marker_path).replace("\\", "\\\\"),
        )

        result = await self._run_c4dpy_script(script_content, marker_path)
        frames_list = sorted(frames_output.glob("*.png")) if frames_output.exists() else []

        return EngineResult(
            success=result["success"],
            output_path=frames_output if result["success"] else None,
            metadata={
                "preset": preset,
                "frame_range": list(frame_range),
                "frames_dir": str(frames_output) if frames_output.exists() else None,
                "frame_count": len(frames_list),
                "c4d_path": str(c4d_output) if c4d_output.exists() else None,
            },
            error=result.get("error"),
        )

    # ===================================================================
    # 5. run_python_script - 通用 Python 脚本执行
    # ===================================================================
    async def run_python_script(
        self,
        script_content: str,
        c4d_file: Optional[Path | str] = None,
    ) -> EngineResult:
        """运行自定义 Python 脚本（通用接口）。

        将脚本写入临时文件，调用 c4dpy.exe script.py 执行。

        Args:
            script_content: Python 脚本文本（可使用 c4d 模块）
            c4d_file: 可选，执行前需要打开的 .c4d 文件路径

        Returns:
            EngineResult: metadata 包含 stdout_tail / returncode
        """
        script_file = Path(tempfile.gettempdir()) / "c4d_custom_script.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path)]
        if c4d_file:
            # c4dpy 支持 "c4dpy.exe <scene.c4d> <script.py>" 形式
            cmd.append(str(Path(c4d_file)))
        cmd.append(str(script_file))

        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        script_file.unlink(missing_ok=True)

        return EngineResult(
            success=code == 0,
            metadata={
                "returncode": code,
                "stdout_length": len(stdout),
                "stdout_tail": stdout[-1000:] if stdout else "",
                "stderr_tail": stderr[-500:] if stderr else "",
            },
            error=stderr[:1000] if code != 0 else None,
            error_code=err_code if code != 0 else None,
        )

    # ===================================================================
    # 内部辅助：通过 c4dpy 执行脚本并验证 marker 文件
    # ===================================================================
    async def _run_c4dpy_script(
        self,
        script_content: str,
        marker_path: Path,
        timeout: int = 7200,
    ) -> dict[str, Any]:
        """执行 c4dpy 脚本并通过 marker 文件验证成功状态。

        Args:
            script_content: Python 脚本文本
            marker_path: 脚本完成后会写入的标记文件路径
            timeout: 超时秒数

        Returns:
            dict: {"success": bool, "error": Optional[str], "metadata_extra": dict}
        """
        script_file = Path(tempfile.gettempdir()) / f"c4d_{marker_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), str(script_file)]
        code, stdout, stderr, err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=timeout
        )

        script_file.unlink(missing_ok=True)
        marker_existed = marker_path.exists()
        marker_path.unlink(missing_ok=True)

        success = (code == 0) and marker_existed
        error = None
        if not success:
            err_parts = []
            if code != 0:
                err_parts.append(f"returncode={code}")
            if not marker_existed:
                err_parts.append("marker file not written")
            if stderr:
                err_parts.append(f"stderr={stderr[:500]}")
            error = "; ".join(err_parts)

        return {
            "success": success,
            "error": error,
            "metadata_extra": {
                "returncode": code,
                "stdout_tail": stdout[-500:] if stdout else "",
                "stderr_tail": stderr[-300:] if stderr else "",
            },
        }

    # ===================================================================
    # _execute_impl - 主分发方法
    # ===================================================================
    async def _execute_impl(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "run_python_script")
        handlers = {
            "render_scene": self.render_scene,
            "export_fbx": self.export_fbx,
            "export_camera_data": self.export_camera_data,
            "render_motion_graphics": self.render_motion_graphics,
            "run_python_script": self.run_python_script,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
                error_code="ACTION_NOT_FOUND",
            )
        return await handler(**kwargs)
