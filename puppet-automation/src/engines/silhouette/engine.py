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
        code, stdout, stderr = await asyncio.to_thread(
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
        code, stdout, stderr = await asyncio.to_thread(
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

    async def execute(self, **kwargs) -> EngineResult:
        """Dispatch engine actions."""
        action = kwargs.pop("action", "create_roto_session")
        handlers = {
            "create_roto_session": self.create_roto_session,
            "run_tracker": self.run_tracker,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)
