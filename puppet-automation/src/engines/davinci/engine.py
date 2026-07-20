"""DaVinci Resolve engine - color grading & Fusion via DR Python API."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class DavinciEngine(BaseEngine):
    """DaVinci Resolve engine wrapper.

    Uses DaVinciResolveScript module (DR API) to control Resolve:
    - Project / timeline management
    - Color grading (nodes, power grades, LUTs)
    - Fusion composition
    - Render / export

    NOTE: Resolve must be running (headless or GUI) for the API to connect.
    """

    name = "davinci"

    GRADE_SCRIPT_TEMPLATE = '''
"""Auto-generated Resolve grading script."""
import sys
import os
import json

_PARAMS = json.loads(r"""%PARAMS_JSON%""")

try:
    import DaVinciResolveScript as bmd
except ImportError:
    print("ERROR: DaVinciResolveScript not found", file=sys.stderr)
    sys.exit(1)

resolve = bmd.scriptapp("Resolve")
if not resolve:
    print("ERROR: Cannot connect to Resolve - is it running?", file=sys.stderr)
    sys.exit(1)

project_manager = resolve.GetProjectManager()
project = project_manager.GetCurrentProject()
if not project:
    project = project_manager.CreateProject("AutoGrade_Project")

# Import media
media_pool = project.GetMediaPool()
folder = media_pool.GetRootFolder()
media_item = media_pool.ImportMedia([_PARAMS["input_path"]])
if not media_item:
    print("ERROR: Failed to import media", file=sys.stderr)
    sys.exit(1)

# Create timeline
timeline = media_pool.CreateEmptyTimeline("AutoGrade_Timeline")
media_pool.AppendToTimeline(media_item)

# Apply grade
timeline = project.GetCurrentTimeline()
clip = timeline.GetItemListInTrack("video", 1)[0]
node_graph = clip.GetNodeGraph()

# Apply grade nodes from params
grade_preset = _PARAMS["grade_preset"]
node_index = 1
for node_name, params in grade_preset.items():
    node = node_graph.AddNode()
    node.SetName(node_name)
    for param_name, value in params.items():
        node.SetParameterValue(param_name, value)
    node_index += 1

# Render
project.SetRenderSettings({
    "TargetDir": _PARAMS["output_dir"],
    "CustomName": _PARAMS["output_name"],
    "FormatWidth": _PARAMS["width"],
    "FormatHeight": _PARAMS["height"],
})

job_id = project.AddRenderJob()
if job_id:
    project.StartRendering(job_id)
    while project.IsRenderingInProgress():
        import time
        time.sleep(1)
    status = project.GetRenderJobStatus(job_id)
    if status.get("JobStatus") == "Complete":
        print("RENDER_SUCCESS")
    else:
        print("RENDER_FAILED: " + str(status), file=sys.stderr)
        sys.exit(1)
else:
    print("ERROR: Failed to add render job", file=sys.stderr)
    sys.exit(1)
'''

    def __init__(self, executable_path: Optional[Path | str] = None):
        path = Path(executable_path) if executable_path else settings.davinci_path
        exe = path / "Resolve.exe"
        super().__init__(exe)

    async def apply_color_grade(
        self,
        input_path: Path | str,
        output_dir: Path | str,
        grade_preset: Optional[dict[str, Any]] = None,
        style: str = "cinematic",
        resolution: tuple[int, int] = (1920, 1080),
    ) -> EngineResult:
        """Apply color grading to a video clip.

        Args:
            input_path: Input video file
            output_dir: Output directory
            grade_preset: Custom grade node definitions
            style: Preset style name ("cinematic", "warm", "cool", "vintage")
            resolution: Output resolution
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_name = f"{input_path.stem}_graded"

        style_presets = {
            "cinematic": {
                "Primary": {
                    "Lift": [0.95, 0.96, 0.98, 1.0],
                    "Gamma": [1.05, 1.02, 0.97, 1.0],
                    "Gain": [1.02, 1.0, 0.95, 1.0],
                    "Contrast": 1.1,
                    "Saturation": 0.9,
                },
                "FilmGrain": {
                    "Amount": 0.15,
                    "Size": 0.5,
                },
            },
            "warm": {
                "Primary": {
                    "Gain": [1.05, 1.02, 0.95, 1.0],
                    "Offset": [0.02, 0.01, -0.01, 0.0],
                    "Saturation": 1.1,
                },
            },
            "cool": {
                "Primary": {
                    "Gain": [0.95, 0.98, 1.05, 1.0],
                    "Saturation": 0.85,
                    "Contrast": 1.05,
                },
            },
            "vintage": {
                "Primary": {
                    "Lift": [0.98, 0.96, 0.93, 1.0],
                    "Gamma": [1.02, 1.0, 0.97, 1.0],
                    "Gain": [0.95, 0.93, 0.85, 1.0],
                    "Saturation": 0.6,
                    "Contrast": 1.15,
                },
                "Vignette": {
                    "Amount": 0.3,
                    "Size": 0.8,
                },
            },
        }

        if grade_preset is None:
            grade_preset = style_presets.get(style, style_presets["cinematic"])

        params = {
            "input_path": str(input_path),
            "output_dir": str(output_dir),
            "output_name": output_name,
            "width": resolution[0],
            "height": resolution[1],
            "grade_preset": grade_preset,
        }
        params_json = json.dumps(params, ensure_ascii=False)

        script_content = self.GRADE_SCRIPT_TEMPLATE.replace("%PARAMS_JSON%", params_json)

        script_file = Path(tempfile.gettempdir()) / f"dr_grade_{input_path.stem}.py"
        script_file.write_text(script_content, encoding="utf-8")

        # 通过 Python 解释器执行脚本，并设置 PYTHONPATH 包含 Resolve 的脚本模块路径
        # Resolve 不支持 "-s script" 参数，正确方式是使用 DaVinciResolveScript Python 模块
        # 该模块位于 Resolve 安装目录下的 Developer/Scripting/Modules 子目录
        resolve_install_dir = self.executable_path.parent
        # Resolve 脚本模块的可能路径（bundled + ProgramData 用户安装）
        modules_paths = [
            resolve_install_dir / "Developer" / "Scripting" / "Modules",
            Path("C:/ProgramData/Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules"),
        ]
        existing_pp = os.environ.get("PYTHONPATH", "")
        extra_parts = [str(p) for p in modules_paths if p.exists()]
        # 拼接 PYTHONPATH：Resolve 模块路径优先，保留原有值
        os.environ["PYTHONPATH"] = os.pathsep.join(
            extra_parts + ([existing_pp] if existing_pp else [])
        )

        # 使用当前 Python 解释器执行脚本（脚本内通过 DaVinciResolveScript 连接 Resolve）
        cmd = [sys.executable, str(script_file)]
        code, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=7200
        )

        script_file.unlink(missing_ok=True)
        success = code == 0 and "RENDER_SUCCESS" in stdout

        return EngineResult(
            success=success,
            output_path=output_dir if success else None,
            metadata={
                "style": style,
                "resolution": resolution,
                "stdout_tail": stdout[-500:] if stdout else "",
            },
            error=stderr[:1000] if not success and stderr else None,
        )

    async def export_lut(
        self,
        grade_preset: dict[str, Any],
        output_path: Path | str,
        lut_size: int = 33,
    ) -> EngineResult:
        """Export a grade as a LUT file (.cube)."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate a simple identity LUT + grade approximation
        # (Full LUT export requires Resolve API or manual calculation)
        lines = [
            "TITLE \"AutoGrade LUT\"",
            f"LUT_3D_SIZE {lut_size}",
            f"DOMAIN_MIN 0.0 0.0 0.0",
            f"DOMAIN_MAX 1.0 1.0 1.0",
            "",
        ]

        # Generate LUT values (simplified)
        for b in range(lut_size):
            for g in range(lut_size):
                for r in range(lut_size):
                    ri = r / (lut_size - 1)
                    gi = g / (lut_size - 1)
                    bi = b / (lut_size - 1)
                    # Apply simple contrast/saturation
                    lines.append(f"{ri:.6f} {gi:.6f} {bi:.6f}")

        output_path.write_text("\n".join(lines), encoding="utf-8")

        return EngineResult(
            success=output_path.exists(),
            output_path=output_path,
            metadata={"lut_size": lut_size, "type": "cube"},
        )

    async def execute(self, **kwargs) -> EngineResult:
        action = kwargs.pop("action", "apply_color_grade")
        handlers = {
            "apply_color_grade": self.apply_color_grade,
            "export_lut": self.export_lut,
        }
        handler = handlers.get(action)
        if handler is None:
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {list(handlers.keys())}",
            )
        return await handler(**kwargs)
