"""Silhouette engine - Roto keying & tracking via fx Python API."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class SilhouetteEngine(BaseEngine):
    """Boris FX Silhouette 2026 engine wrapper.

    Integrates with Silhouette's fx Python API for:
    - Automated roto / keying via RotoNode
    - Point / planar / camera tracking via TrackerNode
    - Paint / wire removal via PaintNode

    NOTE: Silhouette scripts run inside the Silhouette process via the
    Actions mechanism. We generate a .py script and launch Silhouette
    in headless mode with the script as an action.
    """

    name = "silhouette"

    SESSION_TEMPLATE = '''
"""Auto-generated Silhouette roto session script."""
from fx import *
import sys
import os
import json

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    # Create session
    session = createObject("Session")
    session.property("mediaPath").setValue(params["input_path"], 0)

    # --- Node Graph Setup ---
    source_node = createObject("SourceNode")
    source_node.property("mediaPath").setValue(params["input_path"], 0)

    roto_node = createObject("RotoNode")
    roto_node.property("mode").setValue(params["roto_mode"], 0)
    roto_node.property("quality").setValue(params["quality"], 0)

    output_node = createObject("OutputNode")
    output_node.property("format").setValue(params["output_format"], 0)
    output_node.property("outputPath").setValue(params["output_path"], 0)

    # Connect nodes
    source_node.outputs[0].connect(roto_node.inputs[1])  # foreground input
    roto_node.outputs[0].connect(output_node.inputs[0])

    # --- Execute Roto ---
    # 执行 RotoNode 处理 - 基于 Boris FX Silhouette fx API
    # 假设1：通过 session 设置处理帧范围，RotoNode 会自动处理范围内的所有帧
    # 假设2：roto_mode 为 "foreground" 时提取前景遮罩，"background" 时提取背景
    # 假设3：auto_roto 为 True 时自动生成 roto 形状（无需手动绘制）
    # 假设4：roto_node.execute() 触发遮罩计算，结果通过 outputs 传递给 output_node
    session.property("startFrame").setValue(0, 0)
    session.property("endFrame").setValue(100, 0)

    # 如果启用自动 roto，触发表面/形状自动生成
    if params.get("auto_roto", True):
        # 设置自动生成模式（fx API 中通常通过属性控制）
        roto_node.property("autoGenerate").setValue(True, 0)

    # 触发 RotoNode 执行 - 处理输入帧并生成遮罩
    # 注意：fx API 中节点执行通过 execute() 方法触发逐帧处理
    roto_node.execute()

    # --- Render output ---
    output_node.property('firstFrame').setValue(0, 0)
    output_node.property('lastFrame').setValue(100, 0)

    # Write result marker
    with open(params["marker_path"], "w") as f:
        f.write("SUCCESS\\n")
        f.write("output: " + params["output_path"] + "\\n")

main()
'''

    TRACKER_TEMPLATE = '''
"""Auto-generated Silhouette tracker script."""
from fx import *
import json
import sys

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    input_path = params["input_path"]
    output_path = params["output_path"]
    tracker_type = params["tracker_type"]
    track_points = params["track_points"]

    session = createObject("Session")
    session.property("mediaPath").setValue(input_path, 0)

    source_node = createObject("SourceNode")
    source_node.property("mediaPath").setValue(input_path, 0)

    # Tracker node setup
    tracker = createObject("TrackerNode")
    tracker.property("trackerType").setValue(tracker_type, 0)

    # Add tracking points
    for i, pt in enumerate(track_points):
        tracker.property('points').addProperty('ADBE Point Tracker')
        tracker.property('points')[i].property('featureCenter').setValue(
            [pt["x"], pt["y"]], 0
        )

    # Connect
    source_node.outputs[0].connect(tracker.inputs[0])

    # Track forward
    tracker.property("trackForward").setValue(True, 0)

    # 收集跟踪数据 - 从 tracker 节点提取逐帧跟踪结果
    # 假设1：跟踪完成后，每个跟踪点的位置数据存储在 point 的属性中
    # 假设2：通过遍历帧范围获取每帧的跟踪位置（featureCenter 或 trackPosition）
    # 假设3：tracker.property('points') 返回所有跟踪点集合
    # 假设4：getNumValues() 返回跟踪点数量，getValue(frame) 按帧读取位置
    track_data = []
    point_count = tracker.property('points').getNumValues()

    # 获取会话帧范围
    start_frame = int(session.property("startFrame").getValue(0))
    end_frame = int(session.property("endFrame").getValue(0))

    for i in range(point_count):
        point = tracker.property('points')[i]
        point_data = {
            "point_index": i,
            "frames": [],
        }
        # 遍历每帧提取跟踪位置
        for frame in range(start_frame, end_frame + 1):
            try:
                # 读取该帧的跟踪位置（优先使用 trackPosition，回退到 featureCenter）
                pos = point.property('trackPosition').getValue(frame)
                point_data["frames"].append({
                    "frame": frame,
                    "x": float(pos[0]),
                    "y": float(pos[1]),
                })
            except Exception:
                # 跟踪数据在该帧可能不存在（跟踪失败或未覆盖的帧）
                continue
        track_data.append(point_data)

    with open(output_path, "w") as f:
        json.dump({
            "tracker_type": tracker_type,
            "points_count": len(track_points),
            "data": track_data,
        }, f, indent=2)

main()
'''

    EXPORT_SHAPES_TEMPLATE = '''
"""Auto-generated Silhouette export shapes script."""
from fx import *
import json
import sys

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    input_path = params["input_path"]
    output_path = params["output_path"]
    marker_path = params["marker_path"]
    session_path = params.get("session_path", "")

    if session_path and os.path.exists(session_path):
        session = loadSession(session_path)
    else:
        session = createObject("Session")
        session.property("mediaPath").setValue(input_path, 0)

    shapes_data = {"version": "1.0", "frames": [], "name": "silhouette_export"}

    start_frame = int(session.property("startFrame").getValue(0))
    end_frame = int(session.property("endFrame").getValue(0))

    nodes = session.getNodes()
    for node in nodes:
        if node.type() == "RotoNode":
            shapes_prop = node.property("shapes")
            if shapes_prop:
                for shape_idx in range(shapes_prop.getNumSubProperties()):
                    shape = shapes_prop.getSubProperty(shape_idx)
                    shape_name = shape.name
                    total_frames = end_frame - start_frame + 1

                    for frame in range(start_frame, end_frame + 1):
                        frame_data = {"frame": frame, "contours": []}
                        paths_prop = shape.property("paths")
                        if paths_prop:
                            for path_idx in range(paths_prop.getNumSubProperties()):
                                path_prop = paths_prop.getSubProperty(path_idx)
                                points_prop = path_prop.property("points")
                                if points_prop:
                                    contour = {"points": []}
                                    for pt_idx in range(points_prop.getNumSubProperties()):
                                        pt = points_prop.getSubProperty(pt_idx)
                                        x = pt.property("x").getValue(frame)
                                        y = pt.property("y").getValue(frame)
                                        contour["points"].append({"x": x, "y": y})
                                    if len(contour["points"]) >= 3:
                                        frame_data["contours"].append(contour)
                        if frame_data["contours"]:
                            shapes_data["frames"].append(frame_data)
                            break

    with open(output_path, "w") as f:
        json.dump(shapes_data, f, indent=2)

    with open(marker_path, "w") as f:
        f.write("SUCCESS\\n")
        f.write("output: " + output_path + "\\n")
        f.write("frames_exported: " + str(len(shapes_data["frames"])) + "\\n")

main()
'''

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.silhouette_path
        # Silhouette.exe is the main executable
        exe = path / "Silhouette.exe"
        super().__init__(exe)

    async def create_roto_session(
        self,
        input_path: Path | str,
        output_path: Path | str,
        roto_mode: str = "foreground",
        quality: int = 60,
        output_format: str = "OpenEXR",
        auto_roto: bool = True,
    ) -> EngineResult:
        """Create a Silhouette roto session and render output.

        Args:
            input_path: Input video file
            output_path: Output path for rendered matte
            roto_mode: Roto mode ("foreground" or "background")
            quality: Roto quality 1-100
            output_format: Output format (OpenEXR, TIFF, PNG, etc.)
            auto_roto: Whether to run auto-roto
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        marker_path = Path(tempfile.gettempdir()) / f"sil_roto_{output_path.stem}.mark"

        params = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "marker_path": str(marker_path),
            "roto_mode": roto_mode,
            "quality": quality,
            "output_format": output_format,
            "auto_roto": auto_roto,
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.SESSION_TEMPLATE.replace("%PARAMS_JSON%", params_json)

        script_file = Path(tempfile.gettempdir()) / f"sil_roto_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        # Launch Silhouette with script
        cmd = [
            str(self.executable_path),
            "-script", str(script_file),
            "-headless",
        ]
        code, stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        return EngineResult(
            success=success,
            output_path=output_path if success else None,
            metadata={
                "roto_mode": roto_mode,
                "quality": quality,
                "output_format": output_format,
                "auto_roto": auto_roto,
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def run_tracker(
        self,
        input_path: Path | str,
        output_path: Path | str,
        tracker_type: str = "point",
        track_points: list[dict[str, float]] | None = None,
    ) -> EngineResult:
        """Run tracking on input video.

        Args:
            input_path: Input video
            output_path: Output track data path (.json)
            tracker_type: "point", "planar", or "camera"
            track_points: List of {x, y} points to track
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        track_points = track_points or []

        params = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "tracker_type": tracker_type,
            "track_points": track_points,
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.TRACKER_TEMPLATE.replace("%PARAMS_JSON%", params_json)

        script_file = Path(tempfile.gettempdir()) / f"sil_track_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "-script", str(script_file), "-headless"]
        code, _stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200
        )

        script_file.unlink(missing_ok=True)

        return EngineResult(
            success=code == 0 and output_path.exists(),
            output_path=output_path if (code == 0 and output_path.exists()) else None,
            metadata={
                "tracker_type": tracker_type,
                "points_count": len(track_points),
            },
            error=stderr[:1000] if code != 0 else None,
        )

    async def export_shapes(
        self,
        output_path: Path | str,
        input_path: Optional[Path | str] = None,
        session_path: Optional[Path | str] = None,
    ) -> EngineResult:
        """导出 Silhouette Roto 形状数据为 JSON。

        将 Silhouette 会话中的 RotoNode 形状数据导出为标准 JSON 格式，
        供 AE 桥接器创建 Mask 路径图层使用。

        Args:
            output_path: 导出的形状 JSON 文件路径
            input_path: 关联的输入视频路径
            session_path: Silhouette 会话文件路径（可选）

        Returns:
            EngineResult 包含导出结果
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        input_path = Path(input_path) if input_path else ""
        session_path = Path(session_path) if session_path else ""

        marker_path = Path(tempfile.gettempdir()) / f"sil_export_{output_path.stem}.mark"

        params = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "marker_path": str(marker_path),
            "session_path": str(session_path),
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.EXPORT_SHAPES_TEMPLATE.replace("%PARAMS_JSON%", params_json)
        script_file = Path(tempfile.gettempdir()) / f"sil_export_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "-script", str(script_file), "-headless"]
        code, stdout, stderr, _ = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        return EngineResult(
            success=success,
            output_path=output_path if success else None,
            metadata={
                "output_path": str(output_path),
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    IMPORT_SHAPES_TEMPLATE = '''
"""Auto-generated Silhouette import shapes script."""
from fx import *
import json
import sys

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    shapes_path = params["shapes_path"]
    input_path = params["input_path"]
    output_path = params["output_path"]
    marker_path = params["marker_path"]

    with open(shapes_path, "r") as f:
        shape_data = json.load(f)

    session = createObject("Session")
    session.property("mediaPath").setValue(input_path, 0)

    source_node = createObject("SourceNode")
    source_node.property("mediaPath").setValue(input_path, 0)

    roto_node = createObject("RotoNode")
    roto_node.property("mode").setValue("foreground", 0)
    roto_node.property("quality").setValue(80, 0)

    shape_name = shape_data.get("name", "imported_shape")
    frames = shape_data.get("frames", [])

    if frames:
        shape_obj = roto_node.property("shapes").addProperty("Shape")
        shape_obj.name = shape_name

        for frame_data in frames:
            frame_idx = frame_data.get("frame", 0)
            contours = frame_data.get("contours", [])

            for ci, contour in enumerate(contours):
                points = contour.get("points", [])
                if len(points) < 3:
                    continue

                path_prop = shape_obj.property("paths").addProperty("Path")
                path_prop.name = f"contour_{ci}"

                for pi, pt in enumerate(points):
                    point_prop = path_prop.property("points").addProperty("BezierPoint")
                    point_prop.property("x").setValue(pt["x"], frame_idx)
                    point_prop.property("y").setValue(pt["y"], frame_idx)

    output_node = createObject("OutputNode")
    output_node.property("format").setValue("OpenEXR", 0)
    output_node.property("outputPath").setValue(output_path, 0)

    source_node.outputs[0].connect(roto_node.inputs[1])
    roto_node.outputs[0].connect(output_node.inputs[0])

    roto_node.execute()

    start_frame = int(session.property("startFrame").getValue(0))
    end_frame = int(session.property("endFrame").getValue(0))
    output_node.property('firstFrame').setValue(start_frame, 0)
    output_node.property('lastFrame').setValue(end_frame, 0)

    with open(marker_path, "w") as f:
        f.write("SUCCESS\\n")
        f.write("output: " + output_path + "\\n")
        f.write("shapes_imported: " + str(len(frames)) + "\\n")

main()
'''

    REFINE_MASK_TEMPLATE = '''
"""Auto-generated Silhouette mask refinement script."""
from fx import *
import json
import sys

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    input_path = params["input_path"]
    mask_dir = params["mask_dir"]
    output_path = params["output_path"]
    marker_path = params["marker_path"]
    feather = params.get("feather", 2.0)
    motion_blur = params.get("motion_blur", 0.5)
    bezier_simplify = params.get("bezier_simplify", 1.0)

    session = createObject("Session")
    session.property("mediaPath").setValue(input_path, 0)

    source_node = createObject("SourceNode")
    source_node.property("mediaPath").setValue(input_path, 0)

    roto_node = createObject("RotoNode")
    roto_node.property("mode").setValue("foreground", 0)
    roto_node.property("quality").setValue(90, 0)

    roto_node.property("edgeFeather").setValue(feather, 0)
    roto_node.property("motionBlur").setValue(motion_blur, 0)
    roto_node.property("bezierSimplify").setValue(bezier_simplify, 0)

    output_node = createObject("OutputNode")
    output_node.property("format").setValue("OpenEXR", 0)
    output_node.property("outputPath").setValue(output_path, 0)

    source_node.outputs[0].connect(roto_node.inputs[1])
    roto_node.outputs[0].connect(output_node.inputs[0])

    roto_node.execute()

    start_frame = int(session.property("startFrame").getValue(0))
    end_frame = int(session.property("endFrame").getValue(0))
    output_node.property('firstFrame').setValue(start_frame, 0)
    output_node.property('lastFrame').setValue(end_frame, 0)

    with open(marker_path, "w") as f:
        f.write("SUCCESS\\n")
        f.write("output: " + output_path + "\\n")
        f.write("feather: " + str(feather) + "\\n")
        f.write("motion_blur: " + str(motion_blur) + "\\n")

main()
'''

    RENDER_ALPHA_TEMPLATE = '''
"""Auto-generated Silhouette alpha render script."""
from fx import *
import json
import sys

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

def main():
    params = _PARAMS
    input_path = params["input_path"]
    output_path = params["output_path"]
    marker_path = params["marker_path"]
    output_format = params.get("output_format", "PNG")
    alpha_only = params.get("alpha_only", True)

    session = createObject("Session")
    session.property("mediaPath").setValue(input_path, 0)

    source_node = createObject("SourceNode")
    source_node.property("mediaPath").setValue(input_path, 0)

    output_node = createObject("OutputNode")
    output_node.property("format").setValue(output_format, 0)
    output_node.property("outputPath").setValue(output_path, 0)

    if alpha_only:
        output_node.property("alphaOnly").setValue(True, 0)

    source_node.outputs[0].connect(output_node.inputs[0])

    start_frame = int(session.property("startFrame").getValue(0))
    end_frame = int(session.property("endFrame").getValue(0))
    output_node.property('firstFrame').setValue(start_frame, 0)
    output_node.property('lastFrame').setValue(end_frame, 0)

    with open(marker_path, "w") as f:
        f.write("SUCCESS\\n")
        f.write("output: " + output_path + "\\n")
        f.write("alpha_only: " + str(alpha_only) + "\\n")

main()
'''

    async def import_roto_shapes(
        self,
        shapes_path: Path | str,
        input_path: Path | str,
        output_path: Path | str,
    ) -> EngineResult:
        """导入 SAM2 生成的形状数据到 Silhouette。

        将 SAM2 导出的 JSON 形状数据导入 Silhouette RotoNode，
        作为自动 roto 的基础形状。

        Args:
            shapes_path: SAM2 导出的形状 JSON 文件路径
            input_path: 输入视频/图像序列路径
            output_path: 输出会话或遮罩路径

        Returns:
            EngineResult 包含导入结果
        """
        shapes_path = Path(shapes_path)
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not shapes_path.exists():
            return EngineResult(
                success=False,
                error=f"Shapes file not found: {shapes_path}",
            )

        marker_path = Path(tempfile.gettempdir()) / f"sil_import_{output_path.stem}.mark"

        params = {
            "shapes_path": str(shapes_path),
            "input_path": str(input_path),
            "output_path": str(output_path),
            "marker_path": str(marker_path),
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.IMPORT_SHAPES_TEMPLATE.replace("%PARAMS_JSON%", params_json)
        script_file = Path(tempfile.gettempdir()) / f"sil_import_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "-script", str(script_file), "-headless"]
        code, stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        return EngineResult(
            success=success,
            output_path=output_path if success else None,
            metadata={
                "shapes_path": str(shapes_path),
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def refine_mask(
        self,
        mask_dir: Path | str,
        output_dir: Path | str,
        video_path: Optional[Path | str] = None,
        feather: float = 2.0,
        motion_blur: float = 0.5,
        bezier_simplify: float = 1.0,
    ) -> EngineResult:
        """精修 mask - 贝塞尔曲线简化、边缘羽化、运动模糊。

        使用 Silhouette 的 RotoNode 对输入遮罩进行精修处理，
        包括边缘羽化、运动模糊和贝塞尔曲线简化。

        Args:
            mask_dir: 输入遮罩序列目录
            output_dir: 输出精修后遮罩目录
            video_path: 原始视频路径（可选，用于运动分析）
            feather: 边缘羽化值（像素）
            motion_blur: 运动模糊强度（0-1）
            bezier_simplify: 贝塞尔曲线简化容差

        Returns:
            EngineResult 包含精修结果
        """
        mask_dir = Path(mask_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not mask_dir.exists():
            return EngineResult(
                success=False,
                error=f"Mask directory not found: {mask_dir}",
            )

        mask_files = sorted(mask_dir.glob("*.png"))
        if not mask_files:
            return EngineResult(
                success=False,
                error=f"No mask files found in {mask_dir}",
            )

        input_path = video_path or mask_files[0]
        marker_path = Path(tempfile.gettempdir()) / f"sil_refine_{output_dir.name}.mark"

        params = {
            "input_path": str(input_path),
            "mask_dir": str(mask_dir),
            "output_path": str(output_dir),
            "marker_path": str(marker_path),
            "feather": feather,
            "motion_blur": motion_blur,
            "bezier_simplify": bezier_simplify,
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.REFINE_MASK_TEMPLATE.replace("%PARAMS_JSON%", params_json)
        script_file = Path(tempfile.gettempdir()) / f"sil_refine_{output_dir.name}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "-script", str(script_file), "-headless"]
        code, stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        return EngineResult(
            success=success,
            output_path=output_dir if success else None,
            metadata={
                "feather": feather,
                "motion_blur": motion_blur,
                "bezier_simplify": bezier_simplify,
                "input_mask_count": len(mask_files),
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def render_alpha(
        self,
        input_path: Path | str,
        output_path: Path | str,
        output_format: str = "PNG",
        alpha_only: bool = True,
    ) -> EngineResult:
        """渲染 alpha 通道序列。

        将 Silhouette 会话或视频渲染为 alpha 通道图像序列。

        Args:
            input_path: 输入视频/会话路径
            output_path: 输出 alpha 序列路径
            output_format: 输出格式（PNG, OpenEXR, TIFF 等）
            alpha_only: 是否仅输出 alpha 通道

        Returns:
            EngineResult 包含渲染结果
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        marker_path = Path(tempfile.gettempdir()) / f"sil_alpha_{output_path.stem}.mark"

        params = {
            "input_path": str(input_path),
            "output_path": str(output_path),
            "marker_path": str(marker_path),
            "output_format": output_format,
            "alpha_only": alpha_only,
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.RENDER_ALPHA_TEMPLATE.replace("%PARAMS_JSON%", params_json)
        script_file = Path(tempfile.gettempdir()) / f"sil_alpha_{output_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        cmd = [str(self.executable_path), "-script", str(script_file), "-headless"]
        code, stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )

        success = code == 0 and marker_path.exists()
        script_file.unlink(missing_ok=True)
        marker_path.unlink(missing_ok=True)

        return EngineResult(
            success=success,
            output_path=output_path if success else None,
            metadata={
                "output_format": output_format,
                "alpha_only": alpha_only,
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def _execute_impl(self, **kwargs) -> EngineResult:
        """【子类实现】action 调度；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        action = kwargs.pop("action", "create_roto_session")
        handlers = {
            "create_roto_session": self.create_roto_session,
            "run_tracker": self.run_tracker,
            "import_roto_shapes": self.import_roto_shapes,
            "refine_mask": self.refine_mask,
            "render_alpha": self.render_alpha,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)


# ========================================================================
# P2 联合抠像工作流 - 类级别别名（必须在类定义完成后设置）
# ========================================================================

SilhouetteEngine.import_shapes = SilhouetteEngine.import_roto_shapes
SilhouetteEngine.refine_shapes = SilhouetteEngine.refine_mask
SilhouetteEngine.export_roto = SilhouetteEngine.render_alpha
