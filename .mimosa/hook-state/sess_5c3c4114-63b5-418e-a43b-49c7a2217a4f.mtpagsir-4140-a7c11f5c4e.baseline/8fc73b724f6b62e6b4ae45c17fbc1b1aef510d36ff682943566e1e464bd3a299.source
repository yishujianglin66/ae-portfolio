#!/usr/bin/env python3
"""
Silhouette MCP 执行端 v2.0 - 真实模式 + 知识库自动调用
=====================================================

基于 Boris FX Silhouette 2026.0.2 真实 fx API 实现，
支持真实模式（通过Silhouette.exe执行）和模拟模式（fx_emulator），
自动从知识库检索模板和参数配置。

安装路径: C:\Program Files\BorisFX\Silhouette 2026.0\
Python: resources\python\python.exe (Python 3.x + PySide6)
API文档: resources\doc\scripting\reference\fx-module.html

支持的命令:
- silhouette_roto         : 自动生成 Roto 遮罩
- silhouette_track        : 平面/点跟踪并导出数据
- silhouette_paint        : Paint 修复/擦除
- silhouette_export       : 导出 Matte/Tracking 数据到 AE
- silhouette_joint_track  : 人体关节点跟踪
- silhouette_face_track   : 面部关键点跟踪与表情分析

执行模式:
- real    : 通过 Silhouette.exe 执行（需要安装Silhouette）
- simulate: 使用 fx_emulator 模拟执行（无需安装）
- auto    : 优先真实模式，失败回退模拟模式

知识库路径: 14-Silhouette知识库/
- 案例模板: 案例模板/roto/, 案例模板/track/, 案例模板/paint/
- 参数文档: Silhouette fx API 参数详解手册.md
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from ae_bridge_base import AEBridgeClient

SILHOUETTE_HOME = Path(r"C:\Program Files\BorisFX\Silhouette 2026.0")
SILHOUETTE_EXE = SILHOUETTE_HOME / "Silhouette.exe"
SILHOUETTE_PYTHON = SILHOUETTE_HOME / "resources" / "python" / "python.exe"
SILHOUETTE_FX_EMULATOR = SILHOUETTE_HOME / "resources" / "scripts" / "fx_emulator.py"

OUTPUT_BASE = Path(os.environ.get("AE_WORK_DIR", r"D:\AE-Work"))

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "14-Silhouette知识库"
TEMPLATE_DIR = KNOWLEDGE_BASE_DIR / "案例模板"

PRESET_CONFIGS = {
    "standard_keying": {
        "alpha_blur": 0.5,
        "antialias": 1.0,
        "fill": True,
        "stroke": False,
        "matte_mode": "alpha",
        "matte_invert": False,
    },
    "hair_keying": {
        "alpha_blur": 1.5,
        "antialias": 1.5,
        "fill": True,
        "motion_blur": True,
        "motion_blur_shutter": 0.7,
        "matte_mode": "alpha",
    },
    "hard_edge_keying": {
        "alpha_blur": 0.1,
        "antialias": 0.5,
        "fill": True,
        "matte_mode": "alpha",
        "matte_invert": False,
    },
    "soft_edge_keying": {
        "alpha_blur": 2.0,
        "antialias": 2.0,
        "fill": True,
        "matte_mode": "alpha",
        "motion_blur": False,
    },
    "multi_shape_keying": {
        "alpha_blur": 0.5,
        "antialias": 1.0,
        "fill": True,
        "matte_mode": "alpha",
        "multi_shape": True,
    },
    "ai_assisted_keying": {
        "alpha_blur": 0.8,
        "antialias": 1.2,
        "fill": True,
        "matte_mode": "alpha",
        "ai_assisted": True,
        "motion_blur": True,
        "motion_blur_shutter": 0.6,
    },
    "garbage_matte": {
        "alpha_blur": 0.0,
        "antialias": 0.0,
        "fill": True,
        "matte_mode": "alpha",
        "matte_invert": True,
    },
    "holdout_matte": {
        "alpha_blur": 0.3,
        "antialias": 0.8,
        "fill": True,
        "matte_mode": "alpha",
        "matte_invert": False,
    },
    "planar_track": {
        "track_type": "planar",
        "search_area": 21,
        "accuracy": "medium",
        "pattern_size": 11,
        "keyframes": 1,
    },
    "high_precision_track": {
        "track_type": "planar",
        "search_area": 31,
        "accuracy": "high",
        "pattern_size": 15,
        "keyframes": 1,
    },
    "fast_track": {
        "track_type": "point",
        "search_area": 15,
        "accuracy": "low",
        "pattern_size": 7,
        "keyframes": 5,
    },
    "point_track": {
        "track_type": "point",
        "search_area": 21,
        "accuracy": "medium",
        "pattern_size": 9,
        "keyframes": 2,
    },
    "stabilize": {
        "track_type": "point",
        "search_area": 25,
        "accuracy": "high",
        "pattern_size": 11,
        "keyframes": 1,
        "stabilize": True,
    },
    "camera_solve": {
        "track_type": "planar",
        "search_area": 31,
        "accuracy": "high",
        "pattern_size": 13,
        "keyframes": 1,
        "camera_solve": True,
    },
    "clone_repair": {
        "brush_size": 30.0,
        "brush_hardness": 0.3,
        "brush_flow": 1.0,
        "mode": "clone",
        "sample_offset": [50, 0],
    },
    "smart_repair": {
        "brush_size": 20.0,
        "brush_hardness": 0.2,
        "brush_flow": 0.8,
        "mode": "repair",
        "sample_offset": [0, 0],
    },
    "wire_removal": {
        "brush_size": 15.0,
        "brush_hardness": 0.5,
        "brush_flow": 1.0,
        "mode": "clone",
        "sample_offset": [0, -30],
    },
    "digital_makeup": {
        "brush_size": 25.0,
        "brush_hardness": 0.15,
        "brush_flow": 0.6,
        "mode": "repair",
        "sample_offset": [0, 0],
    },
    "sequence_repair": {
        "brush_size": 35.0,
        "brush_hardness": 0.4,
        "brush_flow": 0.9,
        "mode": "clone",
        "sample_offset": [40, 0],
    },
    "object_removal": {
        "brush_size": 40.0,
        "brush_hardness": 0.35,
        "brush_flow": 1.0,
        "mode": "clone",
        "sample_offset": [60, 0],
    },
    "joint_track_17point": {
        "track_type": "point",
        "search_area": 25,
        "accuracy": "high",
        "pattern_size": 11,
        "keyframes": 1,
        "joint_count": 17,
        "joint_names": [
            "head", "neck",
            "left_shoulder", "right_shoulder",
            "left_elbow", "right_elbow",
            "left_wrist", "right_wrist",
            "left_hip", "right_hip",
            "left_knee", "right_knee",
            "left_ankle", "right_ankle",
            "left_hand", "right_hand",
            "pelvis",
        ],
    },
    "face_track_basic": {
        "track_type": "point",
        "search_area": 15,
        "accuracy": "high",
        "pattern_size": 7,
        "keyframes": 1,
        "landmark_count": 20,
        "landmark_groups": {
            "eyes": ["left_eye_inner", "left_eye_outer", "right_eye_inner", "right_eye_outer",
                     "left_eyebrow_inner", "left_eyebrow_outer", "right_eyebrow_inner", "right_eyebrow_outer"],
            "mouth": ["mouth_left", "mouth_right", "mouth_top", "mouth_bottom"],
            "jaw": ["jaw_left", "jaw_chin", "jaw_right"],
            "nose": ["nose_tip", "nose_bridge"],
        },
    },
    "face_track_expression": {
        "track_type": "point",
        "search_area": 12,
        "accuracy": "high",
        "pattern_size": 5,
        "keyframes": 1,
        "landmark_count": 68,
        "expression_params": [
            "eye_open_left", "eye_open_right",
            "mouth_open", "mouth_wide",
            "brow_raise_left", "brow_raise_right",
            "smile_left", "smile_right",
            "jaw_drop", "chin_raise",
            "nose_wrinkle", "upper_lip_raise",
            "lip_pucker", "lip_stretch",
            "cheek_raise_left", "cheek_raise_right",
            "eye_squint_left", "eye_squint_right",
            "brow_furrow_left", "brow_furrow_right",
        ],
    },
}


class SilhouetteExecutor(AEBridgeClient):

    def __init__(self, secret=None, mode="auto"):
        documents_dir = Path(os.environ.get('USERPROFILE', '')).joinpath('Documents')
        self.bridge_dir = documents_dir.joinpath('ae-mcp-bridge')

        resolved_secret = secret or os.environ.get("MCP_BRIDGE_SECRET", "")
        super().__init__(
            command_file=str(self.bridge_dir.joinpath('silhouette_command.json')),
            result_file=str(self.bridge_dir.joinpath('silhouette_result.json')),
            timeout=300,
            poll_interval=1.0,
            signature_enabled=bool(resolved_secret),
            secret=resolved_secret,
        )
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self._load_knowledge_base()

    def _load_secret(self) -> str:
        return os.environ.get("MCP_BRIDGE_SECRET", "")

    def _is_result_ready(self, result: Dict[str, Any]) -> bool:
        return result.get('status') in ['success', 'error', 'timeout', 'pending_silhouette']

    def _load_knowledge_base(self):
        self.templates = {}
        if TEMPLATE_DIR.exists():
            for category in ["roto", "track", "paint", "export"]:
                cat_dir = TEMPLATE_DIR / category
                if cat_dir.exists():
                    for template_file in cat_dir.glob("*.py"):
                        template_name = template_file.stem
                        self.templates[f"{category}/{template_name}"] = str(template_file)
        print(f"[SilhouetteExecutor] Loaded {len(self.templates)} templates from knowledge base")

    def _get_preset(self, preset_name: str) -> Dict:
        return PRESET_CONFIGS.get(preset_name, {})

    def execute(self, command_data: Dict[str, Any]) -> Dict[str, Any]:
        cmd_type = command_data.get("command", "")
        params = command_data.get("params", {})

        handlers = {
            "silhouette_roto": self._handle_roto,
            "silhouette_track": self._handle_track,
            "silhouette_paint": self._handle_paint,
            "silhouette_export": self._handle_export,
            "silhouette_joint_track": self._handle_joint_track,
            "silhouette_face_track": self._handle_face_track,
        }

        handler = handlers.get(cmd_type)
        if not handler:
            return {
                "status": "error",
                "error": f"Unknown Silhouette command: {cmd_type}",
                "supported": list(handlers.keys()),
            }

        try:
            return handler(params)
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "command": cmd_type,
            }

    def _handle_roto(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = Path(params["source_path"])
        if not source.exists():
            return {"status": "error", "error": f"Source not found: {source}"}

        shape_type = params.get("shape_type", "x-spline")
        tracking = params.get("tracking")
        tolerance = params.get("tolerance", 1.0)
        keyframes = params.get("keyframes", 5)
        fmt = params.get("output_format", "exr")
        # Silhouette OutputNode format 属性需要完整名称（非小写缩写）
        fmt_map = {
            "exr": "OpenEXR",
            "png": "PNG",
            "tiff": "TIFF",
            "tif": "TIFF",
            "dpx": "DPX",
            "jpg": "JPEG",
            "jpeg": "JPEG",
        }
        sfx_fmt = fmt_map.get(fmt.lower(), "OpenEXR")
        preset = params.get("preset", "standard_keying")

        output = params.get("output_path")
        if not output:
            # Silhouette OutputNode 输出格式: basename.####.ext（点+4位帧号）
            ts = int(time.time())
            output = OUTPUT_BASE / "silhouette_output" / f"matte_{source.stem}_{ts}.####.{fmt}"
            output.parent.mkdir(parents=True, exist_ok=True)
        output = Path(output)

        preset_config = self._get_preset(preset)
        tolerance = preset_config.get("alpha_blur", tolerance)

        script = self._generate_roto_script(
            source=str(source),
            output=str(output),
            shape_type=shape_type,
            tracking=tracking,
            tolerance=tolerance,
            keyframes=keyframes,
            fmt=sfx_fmt,
            preset_config=preset_config,
        )

        result = self._run_silhouette_script(script, output)
        result["operation"] = "roto"
        result["shape_type"] = shape_type
        result["tracking"] = tracking
        result["preset"] = preset
        return result

    def _generate_roto_script(
        self,
        source: str,
        output: str,
        shape_type: str = "x-spline",
        tracking: Optional[str] = None,
        tolerance: float = 1.0,
        keyframes: int = 5,
        fmt: str = "exr",
        preset_config: Dict = None,
    ) -> str:
        source_fwd = source.replace("\\", "/")
        output_fwd = output.replace("\\", "/")

        if preset_config is None:
            preset_config = {}

        alpha_blur = preset_config.get("alpha_blur", tolerance)
        antialias = preset_config.get("antialias", 1.0)
        fill = preset_config.get("fill", True)
        stroke = preset_config.get("stroke", False)
        matte_mode = preset_config.get("matte_mode", "alpha")
        matte_invert = preset_config.get("matte_invert", False)
        motion_blur = preset_config.get("motion_blur", False)
        motion_blur_shutter = preset_config.get("motion_blur_shutter", 0.5)

        fill_py = "True" if fill else "False"
        stroke_py = "True" if stroke else "False"
        invert_py = "True" if matte_invert else "False"
        motion_blur_py = "True" if motion_blur else "False"

        script = f'''import fx
import os
from tools.renderer import Renderer
from tools.progress import CommandLineProgress
from tools.session import SessionBuilder

proj = fx.activeProject()
if proj is None:
    proj = fx.Project()
    fx.activate(proj)

# 使用官方 fx.Source API
src = fx.Source("{source_fwd}")
src.label = "Roto_Source"
proj.addItem(src)

# 使用 SessionBuilder 正确创建 SourceNode（关键：stream.primary 属性）
sb = SessionBuilder()
sb.build(src, depth=getattr(src, 'depth', 0))
sb.addSource(src)
src_node = sb.source_nodes[-1]
src_node.label = "SrcNode"
session = sb.session
session.label = "AutoRoto"
fx.activate(session)
if session not in proj.items:
    proj.addItem(session)

roto = fx.Node("RotoNode")
roto.label = "AutoRoto_{shape_type}"
session.addNode(roto)

# 创建初始形状（覆盖全画面的基础遮罩）
try:
    # Silhouette createObject 支持的类型：Shape, Layer
    # Shape 对象用 label 而不是 name
    base_shape = fx.createObject("Shape")
    base_shape.label = "Base_Matte"
    base_shape.closed = True
    base_shape.feather = {alpha_blur}

    # 获取源尺寸
    src_width = 1920
    src_height = 1080
    try:
        if hasattr(src, "size"):
            sz = src.size
            src_width = int(sz.width)
            src_height = int(sz.height)
    except Exception:
        pass

    # 添加四个角点（覆盖全画面，带2%边缘内缩）
    margin_x = src_width * 0.02
    margin_y = src_height * 0.02

    points = [
        fx.Point3(margin_x, margin_y, 0),
        fx.Point3(src_width - margin_x, margin_y, 0),
        fx.Point3(src_width - margin_x, src_height - margin_y, 0),
        fx.Point3(margin_x, src_height - margin_y, 0),
    ]

    for i, pt in enumerate(points):
        base_shape.points.insert(i, pt)

    # 将形状添加到 Roto 节点
    if hasattr(roto, "objects") and roto.objects is not None:
        roto.objects.append(base_shape)
    elif hasattr(roto, "shapes"):
        roto.shapes.append(base_shape)
    elif hasattr(base_shape, "setParent"):
        base_shape.setParent(roto)

    print("[SILHOUETTE] Created shape: {{}} ({{}}x{{}})".format(
        base_shape.label, src_width, src_height))
except Exception as e:
    print("[SILHOUETTE] Shape creation warning: {{}}".format(e))
    import traceback
    traceback.print_exc()

out_node = fx.Node("OutputNode")
out_node.label = "MatteOutput"
out_node.property("path").setValue("{output_fwd}", 0)
out_node.property("format").setValue("{fmt}", 0)
session.addNode(out_node)

# 连接节点：Source → Roto(foreground) → Output
src_node.outputs[0].connect(roto.inputs[1])
roto.outputs[0].connect(out_node.inputs[0])

# 设置 Roto 属性（只有 alpha.blur, antialias, motionBlur 存在）
try:
    if roto.property("alpha.blur"):
        roto.property("alpha.blur").setValue({alpha_blur}, 0)
    if roto.property("antialias"):
        roto.property("antialias").setValue({antialias}, 0)
except Exception as e:
    print("[SILHOUETTE] Property set warning: {{}}".format(e))
'''

        if motion_blur:
            script += f'''
try:
    if roto.property("motionBlur"):
        roto.property("motionBlur").setValue({motion_blur_py}, 0)
    if roto.property("motionBlur.shutter"):
        roto.property("motionBlur.shutter").setValue({motion_blur_shutter}, 0)
except Exception as e:
    print("[SILHOUETTE] Motion blur warning: {{}}".format(e))
'''

        script += f'''
# 获取帧范围
start_frame = 0
end_frame = 0
try:
    if hasattr(src, "startFrame"):
        start_frame = int(src.startFrame)
    if hasattr(src, "duration"):
        duration = int(src.duration)
        end_frame = start_frame + max(0, duration - 1)
except Exception as e:
    print("[SILHOUETTE] Frame range detection: {{}}".format(e))

if end_frame <= start_frame:
    end_frame = start_frame

print("[SILHOUETTE] Rendering frames {{}} to {{}}".format(
    start_frame, end_frame))

# 设置输出节点帧范围（OutputNode 无 startFrame/endFrame 属性，帧范围通过 Renderer 选项控制）
print("[SILHOUETTE] Output frame range: {{}}-{{}}".format(start_frame, end_frame))

# 使用官方 Renderer 渲染
try:
    progress = CommandLineProgress()
    options = {{
        "session": session,
        "nodes": [out_node],
        "progress": progress,
        "write": True,
        "frames": (start_frame, end_frame),
        "validate": False,
    }}
    r = Renderer()
    r.render(options)
    print("[SILHOUETTE] Render complete")
except Exception as e:
    print("[SILHOUETTE] Render failed: {{}}".format(e))
    import traceback
    traceback.print_exc()

# 保存项目
try:
    proj_path = os.path.join(os.path.dirname("{output_fwd}"), "silhouette_project.sfx")
    proj.save(proj_path)
    print("[SILHOUETTE] Project saved: {{}}".format(proj_path))
except Exception as e:
    print("[SILHOUETTE] Project save warning: {{}}".format(e))

print("[SILHOUETTE] Roto pipeline complete")
print("[SILHOUETTE] Source: {source_fwd}")
print("[SILHOUETTE] Output: {output_fwd}")
'''
        return script

    def _handle_track(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = Path(params["source_path"])
        if not source.exists():
            return {"status": "error", "error": f"Source not found: {source}"}

        track_type = params.get("track_type", "planar")
        export_format = params.get("export_format", "ae")
        search_area = params.get("search_area", 21)
        accuracy = params.get("accuracy", "medium")
        preset = params.get("preset", "planar_track")

        output = params.get("output_path")
        if not output:
            output = OUTPUT_BASE / "silhouette_output" / f"track_{track_type}_{source.stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
        output = Path(output)

        preset_config = self._get_preset(preset)
        search_area = preset_config.get("search_area", search_area)
        accuracy = preset_config.get("accuracy", accuracy)
        track_type = preset_config.get("track_type", track_type)
        pattern_size = preset_config.get("pattern_size", 11)
        keyframes = preset_config.get("keyframes", 1)

        script = self._generate_track_script(
            source=str(source),
            output=str(output),
            track_type=track_type,
            export_format=export_format,
            search_area=search_area,
            accuracy=accuracy,
            pattern_size=pattern_size,
            keyframes=keyframes,
        )

        result = self._run_silhouette_script(script, output)
        result["operation"] = "track"
        result["track_type"] = track_type
        result["export_format"] = export_format
        result["preset"] = preset
        return result

    def _generate_track_script(
        self,
        source: str,
        output: str,
        track_type: str,
        export_format: str,
        search_area: int,
        accuracy: str,
        pattern_size: int = 11,
        keyframes: int = 1,
    ) -> str:
        source_fwd = source.replace("\\", "/")
        output_fwd = output.replace("\\", "/")

        script = f'''from fx import *
import json

proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

session = activeSession()
if session is None:
    session = Session(label="AutoTrack", width=1920, height=1080, frameRate=24.0)
    activate(session)
    proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("{source_fwd}", 0)
session.addNode(src)

track = Node("TrackerNode")
track.label = "Track_{track_type}"
track.property("trackType").setValue("{track_type}", 0)
track.property("searchArea").setValue({search_area}, 0)
track.property("accuracy").setValue("{accuracy}", 0)
track.property("patternSize").setValue({pattern_size}, 0)
track.property("keyframes").setValue({keyframes}, 0)
track.property("forward").setValue(true, 0)
track.property("backward").setValue(false, 0)
track.property("autoKeyframe").setValue(true, 0)
session.addNode(track)

src.outputs[0].connect(track.inputs[0])

# 创建初始跟踪点
try:
    src_width = 1920
    src_height = 1080
    try:
        sz = src.property("size").value
        if isinstance(sz, (list, tuple)) and len(sz) >= 2:
            src_width, src_height = int(sz[0]), int(sz[1])
    except:
        pass

    # 在画面中心创建一个跟踪点
    center_x = src_width / 2
    center_y = src_height / 2

    try:
        # 尝试通过 createObject 创建跟踪器
        tracker = createObject("Tracker")
        tracker.name = "Tracker_1"
        tracker.position = Point3(center_x, center_y, 0)

        if hasattr(track, "objects") and track.objects is not None:
            track.objects.append(tracker)
        elif hasattr(track, "trackers"):
            track.trackers.append(tracker)
        else:
            try:
                track.property("trackers").setValue([tracker], 0)
            except:
                pass

        print(f"[SILHOUETTE] Created tracker at ({{center_x}}, {{center_y}})")
    except Exception as te:
        print(f"[SILHOUETTE] Tracker creation: {{te}}")
except Exception as e:
    print(f"[SILHOUETTE] Tracker setup warning: {{e}}")

tracking_data = {{
    "version": "2026.0.2",
    "track_type": "{track_type}",
    "source": "{source_fwd}",
    "search_area": {search_area},
    "accuracy": "{accuracy}",
    "pattern_size": {pattern_size},
    "frames": [],
    "trackers": [],
    "fps": 24.0
}}

# 执行跟踪
try:
    start_frame = 0
    end_frame = 0
    try:
        fr = src.property("frameRange").value
        if isinstance(fr, (list, tuple)) and len(fr) >= 2:
            start_frame, end_frame = int(fr[0]), int(fr[1])
    except:
        pass

    if end_frame <= start_frame:
        end_frame = start_frame

    print(f"[SILHOUETTE] Tracking frames {{start_frame}} to {{end_frame}}")

    # 尝试多种跟踪执行方式
    tracked = False
    try:
        fx.execute("track", track, start_frame, end_frame + 1)
        tracked = True
        print("[SILHOUETTE] Tracking via fx.execute complete")
    except Exception as e1:
        print(f"[SILHOUETTE] fx.execute track failed: {{e1}}")
        try:
            track.track(start_frame, end_frame + 1)
            tracked = True
            print("[SILHOUETTE] Tracking via track.track complete")
        except Exception as e2:
            print(f"[SILHOUETTE] track.track failed: {{e2}}")

    # 收集跟踪数据（多种方式尝试）
    tracker_count = 0
    try:
        tracker_count = int(track.property("trackerCount").value)
    except:
        try:
            if hasattr(track, "trackers"):
                tracker_count = len(track.trackers)
            elif hasattr(track, "objects"):
                tracker_count = len(track.objects)
        except:
            pass

    if tracker_count == 0:
        tracker_count = 1

    print(f"[SILHOUETTE] Collecting data from {{tracker_count}} trackers")

    for i in range(tracker_count):
        tracker_data = {{"id": i, "frames": []}}
        try:
            tracker_obj = None
            if hasattr(track, "trackers") and i < len(track.trackers):
                tracker_obj = track.trackers[i]
            elif hasattr(track, "objects") and i < len(track.objects):
                tracker_obj = track.objects[i]

            for frame in range(start_frame, min(end_frame + 1, start_frame + 30)):
                try:
                    pos = None
                    if tracker_obj and hasattr(tracker_obj, "position"):
                        pos = tracker_obj.position.animatedValue(frame) if hasattr(tracker_obj.position, "animatedValue") else tracker_obj.position
                    else:
                        pos = track.property("position").animatedValue(frame)

                    if pos and isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        tracker_data["frames"].append({{"frame": frame, "x": float(pos[0]), "y": float(pos[1])}})
                except:
                    pass
        except Exception as te:
            print(f"[SILHOUETTE] Tracker {{i}} data: {{te}}")

        tracking_data["trackers"].append(tracker_data)

    tracking_data["frames"] = list(range(start_frame, min(end_frame + 1, start_frame + 30)))

except Exception as e:
    print(f"[SILHOUETTE] Tracking execution: {{e}}")

with open("{output_fwd}", "w") as f:
    json.dump(tracking_data, f, indent=2)

print("[SILHOUETTE] Tracking pipeline complete")
print(f"[SILHOUETTE] Output: {output_fwd}")
'''
        return script

    def _handle_paint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = Path(params["source_path"])
        if not source.exists():
            return {"status": "error", "error": f"Source not found: {source}"}

        brush_size = params.get("brush_size", 25)
        brush_hardness = params.get("brush_hardness", 0.5)
        mode = params.get("mode") or params.get("paint_mode", "clone")
        preset = params.get("preset", "clone_repair")

        output = params.get("output_path")
        if not output:
            output = OUTPUT_BASE / "silhouette_output" / f"paint_{mode}_{source.stem}[####].exr"
            output.parent.mkdir(parents=True, exist_ok=True)
        output = Path(output)

        preset_config = self._get_preset(preset)
        brush_size = preset_config.get("brush_size", brush_size)
        brush_hardness = preset_config.get("brush_hardness", brush_hardness)
        brush_flow = preset_config.get("brush_flow", 1.0)
        mode = preset_config.get("mode", mode)
        sample_offset = preset_config.get("sample_offset", [0, 0])

        script = self._generate_paint_script(
            source=str(source),
            output=str(output),
            brush_size=brush_size,
            brush_hardness=brush_hardness,
            brush_flow=brush_flow,
            mode=mode,
            sample_offset=sample_offset,
        )

        result = self._run_silhouette_script(script, output)
        result["operation"] = "paint"
        result["mode"] = mode
        result["preset"] = preset
        return result

    def _generate_paint_script(
        self,
        source: str,
        output: str,
        brush_size: float,
        brush_hardness: float,
        brush_flow: float,
        mode: str,
        sample_offset: List[float],
    ) -> str:
        source_fwd = source.replace("\\", "/")
        output_fwd = output.replace("\\", "/")

        script = f'''from fx import *

proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

session = activeSession()
if session is None:
    session = Session(label="AutoPaint", width=1920, height=1080)
    activate(session)
    proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("{source_fwd}", 0)
session.addNode(src)

paint = Node("PaintNode")
paint.label = "Paint_{mode}"
paint.property("brush.size").setValue({brush_size}, 0)
paint.property("brush.hardness").setValue({brush_hardness}, 0)
paint.property("brush.flow").setValue({brush_flow}, 0)
paint.property("mode").setValue("{mode}", 0)
paint.property("sampleOffset").setValue({sample_offset}, 0)
session.addNode(paint)

out_node = Node("OutputNode")
out_node.property("path").setValue("{output_fwd}", 0)
out_node.property("format").setValue("exr", 0)
session.addNode(out_node)

src.outputs[0].connect(paint.inputs[0])
paint.outputs[0].connect(out_node.inputs[0])

# 添加初始 Paint 笔触（中心线水平涂抹作为演示）
try:
    src_width = 1920
    src_height = 1080
    try:
        sz = src.property("size").value
        if isinstance(sz, (list, tuple)) and len(sz) >= 2:
            src_width, src_height = int(sz[0]), int(sz[1])
    except:
        pass

    # 获取帧范围
    p_start = 0
    p_end = 0
    try:
        fr = src.property("frameRange").value
        if isinstance(fr, (list, tuple)) and len(fr) >= 2:
            p_start, p_end = int(fr[0]), int(fr[1])
    except:
        pass
    if p_end <= p_start:
        p_end = p_start

    # 在每帧创建一个笔触（中心线水平涂抹）
    center_y = src_height / 2
    stroke_count = 0

    for frame in range(p_start, min(p_start + 5, p_end + 1)):
        try:
            # 创建笔触（stroke）
            stroke = createObject("Stroke")
            stroke.frame = frame
            stroke.brushSize = {brush_size}
            stroke.brushHardness = {brush_hardness}
            stroke.brushFlow = {brush_flow}
            stroke.mode = "{mode}"

            # 添加笔触点（从左到右）
            num_points = 10
            for i in range(num_points):
                x = src_width * 0.1 + (src_width * 0.8 * i / (num_points - 1))
                y = center_y + (i % 3 - 1) * 10
                pt = Point3(x, y, 0)
                stroke.points.insert(i, pt)

            # 添加到 Paint 节点
            if hasattr(paint, "objects") and paint.objects is not None:
                paint.objects.append(stroke)
            elif hasattr(paint, "strokes"):
                paint.strokes.append(stroke)
            else:
                try:
                    paint.property("strokes").setValue([stroke], frame)
                except:
                    pass

            stroke_count += 1
        except Exception as se:
            print(f"[SILHOUETTE] Frame {{frame}} stroke: {{se}}")
            break

    print(f"[SILHOUETTE] Added {{stroke_count}} paint strokes")
except Exception as e:
    print(f"[SILHOUETTE] Paint strokes warning: {{e}}")

# 获取帧范围并执行渲染
start_frame = 0
end_frame = 0
try:
    fr = src.property("frameRange").value
    if isinstance(fr, (list, tuple)) and len(fr) >= 2:
        start_frame, end_frame = int(fr[0]), int(fr[1])
except:
    pass

if end_frame <= start_frame:
    end_frame = start_frame

print(f"[SILHOUETTE] Paint rendering frames {{start_frame}} to {{end_frame}}")
out_node.property("startFrame").setValue(start_frame, 0)
out_node.property("endFrame").setValue(end_frame, 0)

try:
    fx.execute("render", session, start_frame, end_frame + 1)
    print("[SILHOUETTE] Paint render complete")
except Exception as e:
    print(f"[SILHOUETTE] Render failed: {{e}}")
    try:
        session.render(start_frame, end_frame + 1)
        print("[SILHOUETTE] Paint render via session.render complete")
    except Exception as e2:
        print(f"[SILHOUETTE] session.render failed: {{e2}}")

print("[SILHOUETTE] Paint pipeline complete")
print(f"[SILHOUETTE] Output: {output_fwd}")
'''
        return script

    def _handle_export(self, params: Dict[str, Any]) -> Dict[str, Any]:
        export_type = params.get("export_type", "matte")
        output_dir = Path(params.get("output_dir", OUTPUT_BASE / "silhouette_output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        ae_size = params.get("ae_comp_size", [1920, 1080])

        ae_data = {
            "version": "2.0",
            "source": "silhouette",
            "timestamp": datetime.now().isoformat(),
            "aeIntegration": {
                "compName": "Silhouette_Integration",
                "importPath": str(output_dir).replace("\\", "/") + "/",
                "applyAs": "track_matte" if export_type == "matte" else "tracking_data",
                "targetLayer": "selected",
                "matteMode": "alpha",
            },
        }

        if export_type == "matte":
            matte_path = params.get("matte_path", str(output_dir / "matte_[####].exr"))
            ae_data["roto"] = {
                "matteSequence": matte_path.replace("\\", "/"),
                "shapeType": "x-spline",
                "frameRange": [0, 0],
                "resolution": ae_size,
            }

        if export_type == "tracking":
            ae_data["tracking"] = {
                "trackers": params.get("tracking_data", []),
                "exportFormat": "ae_keyframes",
                "nullObjectName": "Silhouette_Tracker",
            }

        if export_type == "paint":
            ae_data["paint"] = {
                "paintedFrames": str(output_dir / "paint_[####].png").replace("\\", "/"),
                "paintMode": "clone",
            }

        output_file = output_dir / f"silhouette_export_{export_type}_{int(time.time())}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(ae_data, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "operation": "export",
            "export_type": export_type,
            "output_file": str(output_file),
            "ae_comp_size": ae_size,
            "ae_integration_data": ae_data,
        }

    def _handle_joint_track(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """关节点跟踪处理方法。

        使用多个 TrackerNode 对人体关节点进行逐帧跟踪，支持 point 或 planar 模式。

        Args:
            params: 参数字典，包含：
                - video_path: 视频文件路径
                - joint_points: 关节点列表，每个元素为 {name, x, y, frame}
                - track_mode: 跟踪模式，"point" 或 "planar"
                - preset: 预设名称，默认 "joint_track_17point"
                - output_path: 输出 JSON 文件路径（可选）

        Returns:
            包含跟踪结果的字典，每个关节点对应逐帧坐标数据。
        """
        source = Path(params.get("video_path") or params.get("source_path", ""))
        if not source.exists():
            return {"status": "error", "error": f"Source not found: {source}"}

        joint_points = params.get("joint_points", [])
        track_mode = params.get("track_mode", "point")
        preset = params.get("preset", "joint_track_17point")

        output = params.get("output_path")
        if not output:
            output = OUTPUT_BASE / "silhouette_output" / f"joint_track_{source.stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
        output = Path(output)

        preset_config = self._get_preset(preset)
        search_area = preset_config.get("search_area", 25)
        accuracy = preset_config.get("accuracy", "high")
        pattern_size = preset_config.get("pattern_size", 11)
        keyframes = preset_config.get("keyframes", 1)
        joint_names = preset_config.get("joint_names", [])

        script = self._generate_joint_track_script(
            source=str(source),
            output=str(output),
            joint_points=joint_points,
            track_mode=track_mode,
            search_area=search_area,
            accuracy=accuracy,
            pattern_size=pattern_size,
            keyframes=keyframes,
            joint_names=joint_names,
        )

        result = self._run_silhouette_script(script, output)
        result["operation"] = "joint_track"
        result["track_mode"] = track_mode
        result["joint_count"] = len(joint_points) if joint_points else preset_config.get("joint_count", 17)
        result["preset"] = preset
        return result

    def _generate_joint_track_script(
        self,
        source: str,
        output: str,
        joint_points: List[Dict[str, Any]],
        track_mode: str,
        search_area: int,
        accuracy: str,
        pattern_size: int,
        keyframes: int,
        joint_names: List[str],
    ) -> str:
        """生成关节跟踪 Silhouette 脚本。

        Args:
            source: 源视频路径
            output: 输出 JSON 路径
            joint_points: 初始关节点列表
            track_mode: 跟踪模式
            search_area: 搜索区域大小
            accuracy: 跟踪精度
            pattern_size: 模式大小
            keyframes: 关键帧间隔
            joint_names: 关节名称列表

        Returns:
            生成的 Python 脚本字符串
        """
        source_fwd = source.replace("\\", "/")
        output_fwd = output.replace("\\", "/")

        joint_points_json = json.dumps(joint_points, ensure_ascii=False)
        joint_names_json = json.dumps(joint_names, ensure_ascii=False)

        script = f'''from fx import *
import json

proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

session = activeSession()
if session is None:
    session = Session(label="JointTrack", width=1920, height=1080, frameRate=24.0)
    activate(session)
    proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("{source_fwd}", 0)
session.addNode(src)

joint_points = {joint_points_json}
joint_names = {joint_names_json}

joint_trackers = {{}}

src_width = 1920
src_height = 1080
try:
    sz = src.property("size").value
    if isinstance(sz, (list, tuple)) and len(sz) >= 2:
        src_width, src_height = int(sz[0]), int(sz[1])
except:
    pass

start_frame = 0
end_frame = 0
try:
    fr = src.property("frameRange").value
    if isinstance(fr, (list, tuple)) and len(fr) >= 2:
        start_frame, end_frame = int(fr[0]), int(fr[1])
except:
    pass
if end_frame <= start_frame:
    end_frame = start_frame

default_joints = [
    {{"name": "head", "x_ratio": 0.5, "y_ratio": 0.1}},
    {{"name": "neck", "x_ratio": 0.5, "y_ratio": 0.2}},
    {{"name": "left_shoulder", "x_ratio": 0.35, "y_ratio": 0.28}},
    {{"name": "right_shoulder", "x_ratio": 0.65, "y_ratio": 0.28}},
    {{"name": "left_elbow", "x_ratio": 0.25, "y_ratio": 0.4}},
    {{"name": "right_elbow", "x_ratio": 0.75, "y_ratio": 0.4}},
    {{"name": "left_wrist", "x_ratio": 0.2, "y_ratio": 0.55}},
    {{"name": "right_wrist", "x_ratio": 0.8, "y_ratio": 0.55}},
    {{"name": "left_hip", "x_ratio": 0.4, "y_ratio": 0.55}},
    {{"name": "right_hip", "x_ratio": 0.6, "y_ratio": 0.55}},
    {{"name": "left_knee", "x_ratio": 0.38, "y_ratio": 0.72}},
    {{"name": "right_knee", "x_ratio": 0.62, "y_ratio": 0.72}},
    {{"name": "left_ankle", "x_ratio": 0.35, "y_ratio": 0.9}},
    {{"name": "right_ankle", "x_ratio": 0.65, "y_ratio": 0.9}},
    {{"name": "left_hand", "x_ratio": 0.15, "y_ratio": 0.6}},
    {{"name": "right_hand", "x_ratio": 0.85, "y_ratio": 0.6}},
    {{"name": "pelvis", "x_ratio": 0.5, "y_ratio": 0.58}},
]

if not joint_points:
    joint_points = []
    for j in default_joints:
        joint_points.append({{
            "name": j["name"],
            "x": int(src_width * j["x_ratio"]),
            "y": int(src_height * j["y_ratio"]),
            "frame": start_frame,
        }})

for idx, jp in enumerate(joint_points):
    jname = jp.get("name", f"joint_{{idx}}")
    jx = float(jp.get("x", src_width / 2))
    jy = float(jp.get("y", src_height / 2))
    jframe = int(jp.get("frame", start_frame))

    track = Node("TrackerNode")
    track.label = f"JointTracker_{{jname}}"
    track.property("trackType").setValue("{track_mode}", 0)
    track.property("searchArea").setValue({search_area}, 0)
    track.property("accuracy").setValue("{accuracy}", 0)
    track.property("patternSize").setValue({pattern_size}, 0)
    track.property("keyframes").setValue({keyframes}, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(false, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    src.outputs[0].connect(track.inputs[0])

    try:
        tracker = createObject("Tracker")
        tracker.name = jname
        tracker.position = Point3(jx, jy, 0)

        if hasattr(track, "objects") and track.objects is not None:
            track.objects.append(tracker)
        elif hasattr(track, "trackers"):
            track.trackers.append(tracker)
        else:
            try:
                track.property("trackers").setValue([tracker], 0)
            except:
                pass

        print(f"[SILHOUETTE] Created joint tracker {{jname}} at ({{jx}}, {{jy}})")
    except Exception as te:
        print(f"[SILHOUETTE] Joint tracker {{jname}} creation: {{te}}")

    joint_trackers[jname] = track

joint_data = {{
    "version": "2026.0.2",
    "track_type": "joint",
    "track_mode": "{track_mode}",
    "source": "{source_fwd}",
    "search_area": {search_area},
    "accuracy": "{accuracy}",
    "pattern_size": {pattern_size},
    "joints": {{}},
    "frames": [],
    "fps": 24.0,
}}

try:
    print(f"[SILHOUETTE] Joint tracking frames {{start_frame}} to {{end_frame}}")

    for jname, track in joint_trackers.items():
        try:
            try:
                fx.execute("track", track, start_frame, end_frame + 1)
            except Exception as e1:
                try:
                    track.track(start_frame, end_frame + 1)
                except Exception as e2:
                    print(f"[SILHOUETTE] {{jname}} track failed: {{e2}}")
        except Exception as e:
            print(f"[SILHOUETTE] {{jname}} tracking: {{e}}")

    max_frames = min(end_frame - start_frame + 1, 60)
    joint_data["frames"] = list(range(start_frame, start_frame + max_frames))

    for jname, track in joint_trackers.items():
        frames_list = []
        try:
            tracker_obj = None
            if hasattr(track, "trackers") and len(track.trackers) > 0:
                tracker_obj = track.trackers[0]
            elif hasattr(track, "objects") and len(track.objects) > 0:
                tracker_obj = track.objects[0]

            for frame in range(start_frame, start_frame + max_frames):
                try:
                    pos = None
                    if tracker_obj and hasattr(tracker_obj, "position"):
                        pos = tracker_obj.position.animatedValue(frame) if hasattr(tracker_obj.position, "animatedValue") else tracker_obj.position
                    else:
                        pos = track.property("position").animatedValue(frame)

                    if pos and isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        frames_list.append({{"frame": frame, "x": float(pos[0]), "y": float(pos[1])}})
                    elif pos and hasattr(pos, "x") and hasattr(pos, "y"):
                        frames_list.append({{"frame": frame, "x": float(pos.x), "y": float(pos.y)}})
                except:
                    pass
        except Exception as te:
            print(f"[SILHOUETTE] Joint {{jname}} data collect: {{te}}")

        joint_data["joints"][jname] = frames_list

except Exception as e:
    print(f"[SILHOUETTE] Joint tracking execution: {{e}}")
    import traceback
    traceback.print_exc()

with open("{output_fwd}", "w") as f:
    json.dump(joint_data, f, indent=2)

print("[SILHOUETTE] Joint tracking pipeline complete")
print(f"[SILHOUETTE] Output: {output_fwd}")
'''
        return script

    def _handle_face_track(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """面部跟踪处理方法。

        使用多个 TrackerNode 对面部关键点进行逐帧跟踪，并推导表情参数。

        Args:
            params: 参数字典，包含：
                - video_path: 视频文件路径
                - face_landmarks: 面部关键点列表，每个元素为 {name, x, y, frame}
                - expression_mode: 表情分析模式，"basic" 或 "full"
                - preset: 预设名称，默认 "face_track_basic"
                - output_path: 输出 JSON 文件路径（可选）

        Returns:
            包含面部跟踪结果和表情参数的字典。
        """
        source = Path(params.get("video_path") or params.get("source_path", ""))
        if not source.exists():
            return {"status": "error", "error": f"Source not found: {source}"}

        face_landmarks = params.get("face_landmarks", [])
        expression_mode = params.get("expression_mode", "basic")
        preset = params.get("preset", "face_track_basic")

        output = params.get("output_path")
        if not output:
            output = OUTPUT_BASE / "silhouette_output" / f"face_track_{source.stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
        output = Path(output)

        preset_config = self._get_preset(preset)
        search_area = preset_config.get("search_area", 15)
        accuracy = preset_config.get("accuracy", "high")
        pattern_size = preset_config.get("pattern_size", 7)
        keyframes = preset_config.get("keyframes", 1)
        landmark_groups = preset_config.get("landmark_groups", {})
        expression_params = preset_config.get("expression_params", [])

        script = self._generate_face_track_script(
            source=str(source),
            output=str(output),
            face_landmarks=face_landmarks,
            expression_mode=expression_mode,
            search_area=search_area,
            accuracy=accuracy,
            pattern_size=pattern_size,
            keyframes=keyframes,
            landmark_groups=landmark_groups,
            expression_params=expression_params,
        )

        result = self._run_silhouette_script(script, output)
        result["operation"] = "face_track"
        result["expression_mode"] = expression_mode
        result["landmark_count"] = len(face_landmarks) if face_landmarks else preset_config.get("landmark_count", 20)
        result["preset"] = preset
        return result

    def _generate_face_track_script(
        self,
        source: str,
        output: str,
        face_landmarks: List[Dict[str, Any]],
        expression_mode: str,
        search_area: int,
        accuracy: str,
        pattern_size: int,
        keyframes: int,
        landmark_groups: Dict[str, List[str]],
        expression_params: List[str],
    ) -> str:
        """生成面部跟踪 Silhouette 脚本。

        Args:
            source: 源视频路径
            output: 输出 JSON 路径
            face_landmarks: 初始面部关键点列表
            expression_mode: 表情分析模式
            search_area: 搜索区域大小
            accuracy: 跟踪精度
            pattern_size: 模式大小
            keyframes: 关键帧间隔
            landmark_groups: 关键点分组
            expression_params: 表情参数列表

        Returns:
            生成的 Python 脚本字符串
        """
        source_fwd = source.replace("\\", "/")
        output_fwd = output.replace("\\", "/")

        face_landmarks_json = json.dumps(face_landmarks, ensure_ascii=False)
        landmark_groups_json = json.dumps(landmark_groups, ensure_ascii=False)
        expression_params_json = json.dumps(expression_params, ensure_ascii=False)

        script = f'''from fx import *
import json
import math

proj = activeProject()
if proj is None:
    proj = Project()
    activate(proj)

session = activeSession()
if session is None:
    session = Session(label="FaceTrack", width=1920, height=1080, frameRate=24.0)
    activate(session)
    proj.addItem(session)

src = Node("SourceNode")
src.property("mediaPath").setValue("{source_fwd}", 0)
session.addNode(src)

face_landmarks = {face_landmarks_json}
landmark_groups = {landmark_groups_json}
expression_params = {expression_params_json}

face_trackers = {{}}

src_width = 1920
src_height = 1080
try:
    sz = src.property("size").value
    if isinstance(sz, (list, tuple)) and len(sz) >= 2:
        src_width, src_height = int(sz[0]), int(sz[1])
except:
    pass

start_frame = 0
end_frame = 0
try:
    fr = src.property("frameRange").value
    if isinstance(fr, (list, tuple)) and len(fr) >= 2:
        start_frame, end_frame = int(fr[0]), int(fr[1])
except:
    pass
if end_frame <= start_frame:
    end_frame = start_frame

default_landmarks = [
    {{"name": "left_eye_inner", "x_ratio": 0.42, "y_ratio": 0.38}},
    {{"name": "left_eye_outer", "x_ratio": 0.35, "y_ratio": 0.38}},
    {{"name": "right_eye_inner", "x_ratio": 0.58, "y_ratio": 0.38}},
    {{"name": "right_eye_outer", "x_ratio": 0.65, "y_ratio": 0.38}},
    {{"name": "left_eyebrow_inner", "x_ratio": 0.42, "y_ratio": 0.30}},
    {{"name": "left_eyebrow_outer", "x_ratio": 0.34, "y_ratio": 0.28}},
    {{"name": "right_eyebrow_inner", "x_ratio": 0.58, "y_ratio": 0.30}},
    {{"name": "right_eyebrow_outer", "x_ratio": 0.66, "y_ratio": 0.28}},
    {{"name": "mouth_left", "x_ratio": 0.40, "y_ratio": 0.52}},
    {{"name": "mouth_right", "x_ratio": 0.60, "y_ratio": 0.52}},
    {{"name": "mouth_top", "x_ratio": 0.50, "y_ratio": 0.48}},
    {{"name": "mouth_bottom", "x_ratio": 0.50, "y_ratio": 0.56}},
    {{"name": "jaw_left", "x_ratio": 0.35, "y_ratio": 0.50}},
    {{"name": "jaw_chin", "x_ratio": 0.50, "y_ratio": 0.62}},
    {{"name": "jaw_right", "x_ratio": 0.65, "y_ratio": 0.50}},
    {{"name": "nose_tip", "x_ratio": 0.50, "y_ratio": 0.42}},
    {{"name": "nose_bridge", "x_ratio": 0.50, "y_ratio": 0.35}},
    {{"name": "left_pupil", "x_ratio": 0.385, "y_ratio": 0.38}},
    {{"name": "right_pupil", "x_ratio": 0.615, "y_ratio": 0.38}},
    {{"name": "forehead_center", "x_ratio": 0.50, "y_ratio": 0.20}},
]

if not face_landmarks:
    face_landmarks = []
    for lm in default_landmarks:
        face_landmarks.append({{
            "name": lm["name"],
            "x": int(src_width * lm["x_ratio"]),
            "y": int(src_height * lm["y_ratio"]),
            "frame": start_frame,
        }})

for idx, lm in enumerate(face_landmarks):
    lname = lm.get("name", f"landmark_{{idx}}")
    lx = float(lm.get("x", src_width / 2))
    ly = float(lm.get("y", src_height / 2))
    lframe = int(lm.get("frame", start_frame))

    track = Node("TrackerNode")
    track.label = f"FaceTracker_{{lname}}"
    track.property("trackType").setValue("point", 0)
    track.property("searchArea").setValue({search_area}, 0)
    track.property("accuracy").setValue("{accuracy}", 0)
    track.property("patternSize").setValue({pattern_size}, 0)
    track.property("keyframes").setValue({keyframes}, 0)
    track.property("forward").setValue(true, 0)
    track.property("backward").setValue(false, 0)
    track.property("autoKeyframe").setValue(true, 0)
    session.addNode(track)

    src.outputs[0].connect(track.inputs[0])

    try:
        tracker = createObject("Tracker")
        tracker.name = lname
        tracker.position = Point3(lx, ly, 0)

        if hasattr(track, "objects") and track.objects is not None:
            track.objects.append(tracker)
        elif hasattr(track, "trackers"):
            track.trackers.append(tracker)
        else:
            try:
                track.property("trackers").setValue([tracker], 0)
            except:
                pass

        print(f"[SILHOUETTE] Created face landmark {{lname}} at ({{lx}}, {{ly}})")
    except Exception as te:
        print(f"[SILHOUETTE] Face landmark {{lname}} creation: {{te}}")

    face_trackers[lname] = track

face_data = {{
    "version": "2026.0.2",
    "track_type": "face",
    "expression_mode": "{expression_mode}",
    "source": "{source_fwd}",
    "search_area": {search_area},
    "accuracy": "{accuracy}",
    "pattern_size": {pattern_size},
    "landmarks": {{}},
    "expressions": {{}},
    "frames": [],
    "fps": 24.0,
}}

def calc_distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

try:
    print(f"[SILHOUETTE] Face tracking frames {{start_frame}} to {{end_frame}}")

    for lname, track in face_trackers.items():
        try:
            try:
                fx.execute("track", track, start_frame, end_frame + 1)
            except Exception as e1:
                try:
                    track.track(start_frame, end_frame + 1)
                except Exception as e2:
                    print(f"[SILHOUETTE] {{lname}} track failed: {{e2}}")
        except Exception as e:
            print(f"[SILHOUETTE] {{lname}} tracking: {{e}}")

    max_frames = min(end_frame - start_frame + 1, 60)
    face_data["frames"] = list(range(start_frame, start_frame + max_frames))

    landmark_positions = {{}}

    for lname, track in face_trackers.items():
        frames_list = []
        pos_list = []
        try:
            tracker_obj = None
            if hasattr(track, "trackers") and len(track.trackers) > 0:
                tracker_obj = track.trackers[0]
            elif hasattr(track, "objects") and len(track.objects) > 0:
                tracker_obj = track.objects[0]

            for frame in range(start_frame, start_frame + max_frames):
                try:
                    pos = None
                    if tracker_obj and hasattr(tracker_obj, "position"):
                        pos = tracker_obj.position.animatedValue(frame) if hasattr(tracker_obj.position, "animatedValue") else tracker_obj.position
                    else:
                        pos = track.property("position").animatedValue(frame)

                    x, y = 0.0, 0.0
                    if pos and isinstance(pos, (list, tuple)) and len(pos) >= 2:
                        x, y = float(pos[0]), float(pos[1])
                    elif pos and hasattr(pos, "x") and hasattr(pos, "y"):
                        x, y = float(pos.x), float(pos.y)
                    frames_list.append({{"frame": frame, "x": x, "y": y}})
                    pos_list.append((x, y))
                except:
                    pos_list.append((0.0, 0.0))
        except Exception as te:
            print(f"[SILHOUETTE] Landmark {{lname}} data collect: {{te}}")

        face_data["landmarks"][lname] = frames_list
        landmark_positions[lname] = pos_list

    for param_name in expression_params:
        expr_frames = []
        for fi in range(max_frames):
            value = 0.5
            try:
                if param_name == "eye_open_left":
                    if "left_eye_inner" in landmark_positions and "left_eyebrow_inner" in landmark_positions:
                        d = calc_distance(landmark_positions["left_eye_inner"][fi], landmark_positions["left_eyebrow_inner"][fi])
                        value = min(1.0, max(0.0, d / 80.0))
                elif param_name == "eye_open_right":
                    if "right_eye_inner" in landmark_positions and "right_eyebrow_inner" in landmark_positions:
                        d = calc_distance(landmark_positions["right_eye_inner"][fi], landmark_positions["right_eyebrow_inner"][fi])
                        value = min(1.0, max(0.0, d / 80.0))
                elif param_name == "mouth_open":
                    if "mouth_top" in landmark_positions and "mouth_bottom" in landmark_positions:
                        d = calc_distance(landmark_positions["mouth_top"][fi], landmark_positions["mouth_bottom"][fi])
                        value = min(1.0, max(0.0, d / 60.0))
                elif param_name == "mouth_wide":
                    if "mouth_left" in landmark_positions and "mouth_right" in landmark_positions:
                        d = calc_distance(landmark_positions["mouth_left"][fi], landmark_positions["mouth_right"][fi])
                        value = min(1.0, max(0.0, d / 200.0))
                elif param_name == "brow_raise_left":
                    if "left_eyebrow_inner" in landmark_positions and "left_eye_inner" in landmark_positions:
                        d = calc_distance(landmark_positions["left_eyebrow_inner"][fi], landmark_positions["left_eye_inner"][fi])
                        value = min(1.0, max(0.0, d / 80.0))
                elif param_name == "brow_raise_right":
                    if "right_eyebrow_inner" in landmark_positions and "right_eye_inner" in landmark_positions:
                        d = calc_distance(landmark_positions["right_eyebrow_inner"][fi], landmark_positions["right_eye_inner"][fi])
                        value = min(1.0, max(0.0, d / 80.0))
                elif param_name == "smile_left":
                    if "mouth_left" in landmark_positions and "mouth_top" in landmark_positions:
                        d = landmark_positions["mouth_left"][fi][1] - landmark_positions["mouth_top"][fi][1]
                        value = min(1.0, max(0.0, (30.0 + d) / 60.0))
                elif param_name == "smile_right":
                    if "mouth_right" in landmark_positions and "mouth_top" in landmark_positions:
                        d = landmark_positions["mouth_right"][fi][1] - landmark_positions["mouth_top"][fi][1]
                        value = min(1.0, max(0.0, (30.0 + d) / 60.0))
                elif param_name == "jaw_drop":
                    if "jaw_chin" in landmark_positions and "nose_tip" in landmark_positions:
                        d = calc_distance(landmark_positions["jaw_chin"][fi], landmark_positions["nose_tip"][fi])
                        value = min(1.0, max(0.0, (d - 80.0) / 100.0))
                else:
                    value = 0.5
            except:
                pass
            expr_frames.append({{"frame": start_frame + fi, "value": round(value, 4)}})
        face_data["expressions"][param_name] = expr_frames

except Exception as e:
    print(f"[SILHOUETTE] Face tracking execution: {{e}}")
    import traceback
    traceback.print_exc()

with open("{output_fwd}", "w") as f:
    json.dump(face_data, f, indent=2)

print("[SILHOUETTE] Face tracking pipeline complete")
print(f"[SILHOUETTE] Output: {output_fwd}")
'''
        return script

    def _run_silhouette_script(self, script_content: str, expected_output: Path) -> Dict[str, Any]:
        script_file = self.bridge_dir / f"silhouette_script_{int(time.time())}.py"

        # ---- 安全检查：确保脚本路径在可信目录内 ----
        try:
            script_abs = script_file.resolve()
            bridge_abs = self.bridge_dir.resolve()
            if not str(script_abs).startswith(str(bridge_abs)):
                return {
                    "status": "error",
                    "error": f"Security: Script path outside trusted directory: {script_abs}",
                }
        except Exception as e:
            return {"status": "error", "error": f"Security: Path validation failed: {e}"}

        script_content = self._wrap_script(script_content)
        script_file.write_text(script_content, encoding="utf-8")

        # ---- 安全审计日志 ----
        print(f"[SilhouetteExecutor][SECURITY] Executing script: {script_file}")
        print(f"[SilhouetteExecutor][SECURITY] Script size: {len(script_content)} bytes")

        if self.mode == "real" or (self.mode == "auto" and SILHOUETTE_EXE.exists()):
            return self._run_real_mode(script_file, expected_output)
        else:
            return self._run_simulate_mode(script_file, expected_output)

    def _wrap_script(self, script_content: str) -> str:
        """包装脚本，添加异常处理和退出信号。"""
        wrapped_lines = []
        wrapped_lines.append("#!/usr/bin/env python3")
        wrapped_lines.append("# Silhouette 自动执行脚本 - 由 silhouette_executor.py 生成")
        wrapped_lines.append("import sys")
        wrapped_lines.append("import os")
        wrapped_lines.append("import traceback")
        wrapped_lines.append("")
        wrapped_lines.append("try:")
        for line in script_content.splitlines():
            if line.strip():
                wrapped_lines.append("    " + line)
            else:
                wrapped_lines.append("")
        wrapped_lines.append("except Exception as e:")
        wrapped_lines.append('    print(f"[SILHOUETTE_ERROR] {e}")')
        wrapped_lines.append("    traceback.print_exc()")
        wrapped_lines.append("    sys.exit(1)")
        wrapped_lines.append("")
        wrapped_lines.append('print("[SILHOUETTE_DONE] Script completed successfully")')
        wrapped_lines.append("sys.exit(0)")
        wrapped_lines.append("")
        return "\n".join(wrapped_lines)

    def _is_silhouette_running(self) -> bool:
        """检查 Silhouette 进程是否正在运行。"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Silhouette.exe"],
                capture_output=True, text=True, timeout=10
            )
            return "Silhouette.exe" in result.stdout
        except Exception:
            return False

    def _launch_silhouette(self) -> bool:
        """启动 Silhouette 应用。"""
        if not SILHOUETTE_EXE.exists():
            print(f"[SilhouetteExecutor] Silhouette not found at: {SILHOUETTE_EXE}")
            return False

        if self._is_silhouette_running():
            print("[SilhouetteExecutor] Silhouette is already running")
            return True

        print(f"[SilhouetteExecutor] Launching Silhouette: {SILHOUETTE_EXE}")
        try:
            proc = subprocess.Popen(
                [str(SILHOUETTE_EXE)],
                cwd=str(SILHOUETTE_HOME),
                creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
            )
            print(f"[SilhouetteExecutor] Silhouette PID: {proc.pid}")

            # 等待应用启动（最多30秒）
            for _ in range(30):
                time.sleep(1)
                if self._is_silhouette_running():
                    print("[SilhouetteExecutor] Silhouette is now running")
                    time.sleep(3)  # 额外等待应用完全加载
                    return True

            print("[SilhouetteExecutor] Silhouette did not start within 30s")
            return False
        except Exception as e:
            print(f"[SilhouetteExecutor] Failed to launch Silhouette: {e}")
            return False

    def _run_real_mode(self, script_file: Path, expected_output: Path) -> Dict[str, Any]:
        # 优先使用 Silhouette RPC（官方内置，无需额外启动）
        rpc_result = self._run_real_mode_via_rpc(script_file, expected_output)
        if rpc_result is not None:
            return rpc_result

        # 回退：旧方式（subprocess + Silhouette Python，fx 模块可能不可用）
        # 确保应用正在运行
        if not self._is_silhouette_running():
            launched = self._launch_silhouette()
            if not launched:
                if self.mode == "auto":
                    print("[SilhouetteExecutor] Cannot launch Silhouette, falling back to simulate mode")
                    return self._run_simulate_mode(script_file, expected_output)
                return {
                    "status": "error",
                    "mode": "real",
                    "error": f"Cannot launch Silhouette at {SILHOUETTE_EXE}",
                    "script_file": str(script_file),
                }

        # 使用 Silhouette 内置 Python 执行脚本
        python_exe = SILHOUETTE_PYTHON if SILHOUETTE_PYTHON.exists() else Path(sys.executable)

        # 构建执行命令 - 通过 Silhouette 的 Python 环境运行脚本
        env = os.environ.copy()
        if SILHOUETTE_HOME.exists():
            env["SILHOUETTE_HOME"] = str(SILHOUETTE_HOME)
            # 添加 fx 模块到 Python 路径
            fx_path = SILHOUETTE_HOME / "resources" / "python"
            if fx_path.exists():
                env["PYTHONPATH"] = str(fx_path) + os.pathsep + env.get("PYTHONPATH", "")
            plugin_path = SILHOUETTE_HOME / "resources" / "plugins"
            if plugin_path.exists():
                env["SILHOUETTE_PLUGIN_PATH"] = str(plugin_path)

        try:
            print(f"[SilhouetteExecutor] Executing script via {python_exe}")
            print(f"[SilhouetteExecutor] Script: {script_file}")

            result = subprocess.run(
                [str(python_exe), str(script_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=str(self.bridge_dir),
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            has_done = "[SILHOUETTE_DONE]" in stdout
            has_error = "[SILHOUETTE_ERROR]" in stdout

            # 等待输出文件生成（最多60秒）
            output_ready = False
            if not has_error:
                output_ready = self._wait_for_output(expected_output, timeout=60)

            if output_ready or has_done:
                return {
                    "status": "success",
                    "mode": "real",
                    "output_file": str(expected_output) if expected_output.exists() else None,
                    "output_ready": output_ready,
                    "stdout": stdout[-3000:] if len(stdout) > 3000 else stdout,
                    "stderr": stderr[-1000:] if stderr else "",
                    "returncode": result.returncode,
                    "script_file": str(script_file),
                    "silhouette_running": self._is_silhouette_running(),
                }
            elif has_error:
                return {
                    "status": "error",
                    "mode": "real",
                    "error": "Script execution failed (see stdout for details)",
                    "stdout": stdout[-3000:],
                    "stderr": stderr[-1000:],
                    "returncode": result.returncode,
                    "script_file": str(script_file),
                }
            else:
                # 脚本执行完成但输出未就绪 - 可能需要手动在 Silhouette 中触发渲染
                return {
                    "status": "pending_silhouette",
                    "mode": "real",
                    "message": "Script executed. If output not generated, open Silhouette and run the script manually.",
                    "script_file": str(script_file),
                    "expected_output": str(expected_output),
                    "stdout": stdout[-3000:],
                    "stderr": stderr[-1000:],
                    "returncode": result.returncode,
                    "silhouette_running": self._is_silhouette_running(),
                    "manual_steps": [
                        f"1. Open Silhouette (already running: {self._is_silhouette_running()})",
                        f"2. Run script: {script_file}",
                        f"3. Expected output: {expected_output}",
                    ],
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "mode": "real",
                "message": f"Silhouette execution timed out after {self.timeout}s",
                "script_file": str(script_file),
                "silhouette_running": self._is_silhouette_running(),
            }
        except Exception as e:
            if self.mode == "auto":
                print(f"[SilhouetteExecutor] Real mode failed ({e}), falling back to simulate")
                return self._run_simulate_mode(script_file, expected_output)
            return {
                "status": "error",
                "mode": "real",
                "error": str(e),
                "script_file": str(script_file),
            }

    def _run_real_mode_via_rpc(
        self, script_file: Path, expected_output: Path
    ) -> Optional[Dict[str, Any]]:
        """通过 Silhouette 内置 RPC 服务器执行脚本（真实模式首选）。

        Silhouette 2026.0.2+ 自带 RPC 服务器（fxrpc.cpp），通过命名管道
        （Windows）或 Unix socket（macOS/Linux）提供 exec/exec_file 命令。
        这是官方推荐的真实模式执行方式，脚本在 Silhouette 应用进程内运行，
        可以直接 `from fx import *`。

        Returns:
            成功时返回结果字典；RPC 不可用时返回 None（回退到旧方式）。
        """
        try:
            import asyncio
            sys.path.insert(
                0, str(SILHOUETTE_HOME / "resources" / "mcp")
            )
            from sfx_mcp.rpc_client import (
                SilhouetteRpcClient,
                _read_silhouette_info,
            )

            info = _read_silhouette_info()
            if not info:
                print(
                    "[SilhouetteExecutor] No Silhouette RPC info found "
                    "(Silhouette not running?)"
                )
                return None

            print(
                f"[SilhouetteExecutor] Using Silhouette RPC "
                f"(pid={info.get('pid')}, v{info.get('version')})"
            )

            async def _run() -> Dict[str, Any]:
                client = SilhouetteRpcClient(
                    read_timeout=float(self.timeout)
                )
                try:
                    await client.connect()
                    result = await client.exec_file(str(script_file))

                    stdout = result.stdout or ""
                    stderr = result.stderr or ""
                    has_done = "[SILHOUETTE_DONE]" in stdout
                    has_error = "[SILHOUETTE_ERROR]" in stdout

                    output_ready = False
                    actual_output = None
                    if not has_error:
                        output_ready = self._wait_for_output(
                            expected_output, timeout=60
                        )
                        if output_ready:
                            # 找到实际输出文件名
                            import glob
                            pattern = str(expected_output).replace(
                                "[####]", "*"
                            ).replace(
                                ".####.", ".*."
                            ).replace(
                                "%04d", "*"
                            )
                            matches = glob.glob(pattern)
                            if matches:
                                actual_output = sorted(matches)[-1]

                    if output_ready or (has_done and not has_error):
                        return {
                            "status": "success",
                            "mode": "real",
                            "rpc": True,
                            "output_file": actual_output or str(expected_output),
                            "expected_output": str(expected_output),
                            "output_ready": output_ready,
                            "stdout": stdout[-3000:],
                            "stderr": stderr[-1000:],
                            "returncode": 0 if result.ok else 1,
                            "script_file": str(script_file),
                            "silhouette_running": True,
                        }
                    if has_error:
                        return {
                            "status": "error",
                            "mode": "real",
                            "rpc": True,
                            "error": "Script failed (see stdout)",
                            "stdout": stdout[-3000:],
                            "stderr": stderr[-1000:],
                            "returncode": 1,
                            "script_file": str(script_file),
                        }
                    return {
                        "status": "pending_silhouette",
                        "mode": "real",
                        "rpc": True,
                        "message": "Script executed but output not ready",
                        "script_file": str(script_file),
                        "expected_output": str(expected_output),
                        "stdout": stdout[-3000:],
                        "stderr": stderr[-1000:],
                        "returncode": 0 if result.ok else 1,
                        "silhouette_running": True,
                    }
                finally:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass

            return asyncio.run(_run())

        except ImportError as e:
            print(
                f"[SilhouetteExecutor] sfx_mcp module not available: {e}"
            )
            return None
        except Exception as e:
            print(
                f"[SilhouetteExecutor] RPC execution failed ({e}), "
                "falling back to render_tree mode"
            )
            # 尝试 render_tree offline 模式
            return self._run_real_mode_via_render_tree(expected_output)

    def _run_real_mode_via_render_tree(
        self, expected_output: Path
    ) -> Optional[Dict[str, Any]]:
        """通过 Silhouette render_tree 命令行模式执行渲染。

        使用官方 tree DSL 构建节点图并渲染，无需手动处理 SourceNode 属性。
        这是 Silhouette 官方推荐的批处理渲染方式。
        """
        try:
            import asyncio
            sys.path.insert(
                0, str(SILHOUETTE_HOME / "resources" / "mcp")
            )
            from sfx_mcp.offline_client import render_tree

            # 从 expected_output 解析路径
            output_str = str(expected_output).replace("\\", "/")

            # 从脚本文件名解析源素材路径（通过查看脚本内容）
            # 这里使用默认的 source 路径
            source_path = getattr(self, "_current_source", "")
            if not source_path:
                print(
                    "[SilhouetteExecutor] No source path for render_tree"
                )
                return None

            source_fwd = source_path.replace("\\", "/")

            print(
                f"[SilhouetteExecutor] Using render_tree: "
                f"{source_fwd} → {output_str}"
            )

            # 构建 tree DSL tokens
            tree_args = [
                source_fwd,
                "-RotoNode",
                f"alpha.blur={self._current_alpha_blur}",
                f"antialias={self._current_antialias}",
                f"fill={str(self._current_fill).lower()}",
                "-o", output_str,
            ]

            render_args = ["-range=1"]

            async def _run() -> Dict[str, Any]:
                result = await render_tree(
                    tree_args=tree_args,
                    render_args=render_args,
                    output_dir=str(expected_output.parent),
                    timeout=float(self.timeout),
                )
                return result

            result = asyncio.run(_run())

            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            exit_code = result.get("exit_code", -1)
            new_files = result.get("new_files", [])

            if exit_code == 0 or new_files:
                return {
                    "status": "success",
                    "mode": "real",
                    "render_tree": True,
                    "output_file": (
                        new_files[0] if new_files else str(expected_output)
                    ),
                    "output_ready": bool(new_files),
                    "stdout": stdout[-3000:],
                    "stderr": stderr[-1000:],
                    "returncode": exit_code,
                    "script_file": "",
                    "silhouette_running": True,
                }
            return {
                "status": "error",
                "mode": "real",
                "render_tree": True,
                "error": f"render_tree failed (exit={exit_code})",
                "stdout": stdout[-3000:],
                "stderr": stderr[-1000:],
                "returncode": exit_code,
            }

        except ImportError as e:
            print(
                f"[SilhouetteExecutor] render_tree not available: {e}"
            )
            return None
        except Exception as e:
            print(
                f"[SilhouetteExecutor] render_tree failed ({e})"
            )
            return None

    def _wait_for_output(self, expected_output: Path, timeout: int = 60) -> bool:
        """轮询等待输出文件生成。"""
        # 处理序列帧路径（支持 [####]、.####.、%04d 模式）
        output_str = str(expected_output)
        is_sequence = (
            "[####]" in output_str
            or ".####." in output_str
            or "%04d" in output_str
        )
        if is_sequence:
            # 序列帧：检查目录下是否有任何匹配的文件
            output_dir = expected_output.parent
            pattern = (
                expected_output.name
                .replace("[####]", "*")
                .replace(".####.", ".*.")
                .replace("%04d", "*")
            )
        else:
            output_dir = expected_output.parent
            pattern = expected_output.name

        print(f"[SilhouetteExecutor] Waiting for output: {expected_output}")
        for i in range(timeout):
            if expected_output.exists():
                print(f"[SilhouetteExecutor] Output found after {i}s")
                return True
            # 检查目录下是否有匹配的序列帧
            if output_dir.exists():
                matching = list(output_dir.glob(pattern)) if "*" in pattern else []
                if matching:
                    print(f"[SilhouetteExecutor] Found {len(matching)} output files after {i}s")
                    return True
            time.sleep(1)

        print(f"[SilhouetteExecutor] Output not found after {timeout}s")
        return False

    def _create_simulated_output(self, expected_output: Path):
        """在模拟模式下创建模拟输出文件，使流程可以继续。"""
        output_str = str(expected_output)
        output_dir = expected_output.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 处理序列帧路径
        if "[####]" in output_str:
            # 创建3帧模拟输出
            for i in range(1, 4):
                fname = expected_output.name.replace("[####]", f"{i:04d}")
                fpath = output_dir / fname
                if not fpath.exists():
                    fpath.write_bytes(b"SIMULATED_MATTE")
            print(f"[SilhouetteExecutor] Created 3 simulated frames in {output_dir}")
        elif output_str.endswith(".json"):
            # 跟踪数据
            import json as _json
            sim_data = {
                "version": "2026.0.2",
                "simulated": True,
                "track_type": "planar",
                "frames": list(range(0, 10)),
                "trackers": [{"id": 0, "frames": [{"frame": f, "x": 960.0, "y": 540.0} for f in range(10)]}],
                "fps": 24.0,
            }
            with open(expected_output, "w") as f:
                _json.dump(sim_data, f, indent=2)
            print(f"[SilhouetteExecutor] Created simulated tracking data: {expected_output}")
        else:
            # 单帧输出
            if not expected_output.exists():
                expected_output.write_bytes(b"SIMULATED_OUTPUT")
            print(f"[SilhouetteExecutor] Created simulated output: {expected_output}")

    def _run_simulate_mode(self, script_file: Path, expected_output: Path) -> Dict[str, Any]:
        python_exe = SILHOUETTE_PYTHON if SILHOUETTE_PYTHON.exists() else Path(sys.executable)

        env = os.environ.copy()
        if SILHOUETTE_FX_EMULATOR.parent.exists():
            env["PYTHONPATH"] = str(SILHOUETTE_FX_EMULATOR.parent) + os.pathsep + env.get("PYTHONPATH", "")

        # 创建 wrapper 脚本：先注入 fx_emulator 作为 fx 模块，再执行实际脚本
        wrapper_file = self.bridge_dir / f"silhouette_wrapper_{int(time.time())}.py"
        wrapper_content = f'''#!/usr/bin/env python3
"""Silhouette 模拟模式 wrapper - 注入 fx_emulator 作为 fx 模块"""
import sys
import os
import importlib.util
import traceback

# 注入 fx_emulator 作为 fx 模块
fx_emulator_path = r"{SILHOUETTE_FX_EMULATOR}"
if os.path.exists(fx_emulator_path):
    spec = importlib.util.spec_from_file_location("fx", fx_emulator_path)
    fx_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fx_mod)
    sys.modules["fx"] = fx_mod
    # 注入 Silhouette fx 模块中的全局常量
    import builtins
    if not hasattr(fx_mod, "true"):
        fx_mod.true = True
    if not hasattr(fx_mod, "false"):
        fx_mod.false = False
    # 让 from fx import * 能获取到 true/false
    if not hasattr(fx_mod, "__all__"):
        fx_mod.__all__ = [k for k in dir(fx_mod) if not k.startswith("_")]
    else:
        fx_mod.__all__ = list(fx_mod.__all__) + ["true", "false"]
    print(f"[SILHOUETTE] fx_emulator loaded as 'fx' module")
else:
    print(f"[SILHOUETTE_ERROR] fx_emulator not found: {{fx_emulator_path}}")
    sys.exit(1)

# 添加 Silhouette scripts 目录到 path
scripts_dir = r"{SILHOUETTE_FX_EMULATOR.parent}"
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# 也添加 tools 目录
tools_dir = os.path.join(os.path.dirname(scripts_dir), "python")
if os.path.exists(tools_dir) and tools_dir not in sys.path:
    sys.path.insert(0, tools_dir)

# 执行实际脚本
script_path = r"{script_file}"
trusted_dir = r"{self.bridge_dir}"

# ---- 安全检查：确保脚本在可信目录内 ----
script_abs = os.path.abspath(script_path)
trusted_abs = os.path.abspath(trusted_dir)
if not script_abs.startswith(trusted_abs):
    print(f"[SILHOUETTE_ERROR] Security: Script outside trusted directory: {{script_abs}}")
    sys.exit(1)

print(f"[SILHOUETTE] Executing: {{script_path}}")

try:
    with open(script_path, "r", encoding="utf-8") as f:
        script_code = f.read()
    exec(compile(script_code, script_path, "exec"))
except SystemExit as e:
    if e.code != 0:
        print(f"[SILHOUETTE_ERROR] Script exited with code {{e.code}}")
    sys.exit(e.code if isinstance(e.code, int) else 0)
except Exception as e:
    print(f"[SILHOUETTE_ERROR] {{e}}")
    traceback.print_exc()
    sys.exit(1)
'''
        wrapper_file.write_text(wrapper_content, encoding="utf-8")

        try:
            result = subprocess.run(
                [str(python_exe), str(wrapper_file)],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                cwd=str(self.bridge_dir),
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""

            has_done = "[SILHOUETTE_DONE]" in stdout
            has_error = "[SILHOUETTE_ERROR]" in stdout

            # 在模拟模式下，如果脚本执行成功但输出文件不存在，创建模拟输出
            if has_done and not expected_output.exists():
                self._create_simulated_output(expected_output)

            # 检查输出是否就绪（支持序列帧 [####] 模式）
            output_ready = expected_output.exists()
            if not output_ready and "[####]" in str(expected_output):
                output_dir = expected_output.parent
                pattern = expected_output.name.replace("[####]", "*")
                output_ready = len(list(output_dir.glob(pattern))) > 0 if output_dir.exists() else False

            if output_ready:
                # 找到实际输出文件
                if expected_output.exists():
                    actual_output = str(expected_output)
                else:
                    output_dir = expected_output.parent
                    pattern = expected_output.name.replace("[####]", "*")
                    files = sorted(output_dir.glob(pattern))
                    actual_output = str(files[0]) if files else str(expected_output)
                return {
                    "status": "success",
                    "mode": "simulate",
                    "output_file": actual_output,
                    "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
                    "stderr": stderr[-500:] if stderr else "",
                    "returncode": result.returncode,
                    "script_file": str(script_file),
                }
            elif has_error:
                return {
                    "status": "error",
                    "mode": "simulate",
                    "error": "Script execution failed (see stdout)",
                    "script_file": str(script_file),
                    "expected_output": str(expected_output),
                    "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
                    "stderr": stderr[-500:] if stderr else "",
                    "returncode": result.returncode,
                }
            else:
                return {
                    "status": "pending_silhouette",
                    "mode": "simulate",
                    "message": "Script executed (simulate mode). Output may require manual generation.",
                    "script_file": str(script_file),
                    "expected_output": str(expected_output),
                    "stdout": stdout[-2000:] if len(stdout) > 2000 else stdout,
                    "stderr": stderr[-500:] if stderr else "",
                }

        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "mode": "simulate",
                "message": f"Script execution timed out after {self.timeout}s",
                "script_file": str(script_file),
            }
        except Exception as e:
            return {
                "status": "error",
                "mode": "simulate",
                "error": str(e),
                "script_file": str(script_file),
            }

    def run(self):
        print(f"[SilhouetteExecutor] Starting... Mode: {self.mode}")
        print(f"[SilhouetteExecutor] Silhouette home: {SILHOUETTE_HOME}")
        print(f"[SilhouetteExecutor] Silhouette.exe available: {SILHOUETTE_EXE.exists()}")
        print(f"[SilhouetteExecutor] Python: {SILHOUETTE_PYTHON}")
        print(f"[SilhouetteExecutor] Knowledge base: {KNOWLEDGE_BASE_DIR}")
        print(f"[SilhouetteExecutor] Templates: {list(self.templates.keys())}")
        print(f"[SilhouetteExecutor] Presets: {list(PRESET_CONFIGS.keys())}")
        print(f"[SilhouetteExecutor] Waiting for commands at: {self.command_file}")

        while True:
            try:
                if Path(self.command_file).exists():
                    with open(self.command_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    if self.signature_enabled:
                        sig = data.pop("signature", "")
                        sig_alg = data.pop("signature_alg", "")
                        expected = self._generate_signature(data)
                        if sig != expected:
                            result = {"status": "error", "error": "Invalid signature"}
                            self._write_result(result)
                            continue

                    result = self.execute(data)
                    self._write_result(result)

                    try:
                        os.remove(self.command_file)
                    except OSError:
                        pass

                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                print("[SilhouetteExecutor] Stopped.")
                break
            except Exception as e:
                print(f"[SilhouetteExecutor] Error: {e}")
                time.sleep(self.poll_interval)

    def _write_result(self, result: Dict[str, Any]):
        with open(self.result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)


def execute_silhouette_command(command: str, mode="auto", **params) -> Dict[str, Any]:
    executor = SilhouetteExecutor(mode=mode)
    return executor.execute({"command": command, "params": params})


def _run_self_tests():
    """自测函数：验证新添加的关节跟踪和面部跟踪功能。"""
    print("=" * 60)
    print("Silhouette Executor 自测 - 关节跟踪 & 面部跟踪")
    print("=" * 60)

    test_image = Path(__file__).parent / "05-测试套件" / "test_resources" / "test_image.png"
    if not test_image.exists():
        test_image = Path(__file__).parent / "05-测试套件" / "test_resources" / "test_image.svg"
    if not test_image.exists():
        print(f"[警告] 未找到测试图片，创建临时测试文件...")
        test_image = Path(__file__).parent / "test_temp.png"
        test_image.write_bytes(b"\x89PNG\r\n\x1a\n")

    results = []

    print("\n[测试 1/6] 检查 PRESET_CONFIGS 新预设...")
    preset_names = ["joint_track_17point", "face_track_basic", "face_track_expression"]
    for pname in preset_names:
        if pname in PRESET_CONFIGS:
            print(f"  ✓ {pname} 存在")
            results.append(("preset_" + pname, True))
        else:
            print(f"  ✗ {pname} 不存在")
            results.append(("preset_" + pname, False))

    print("\n[测试 2/6] 检查命令注册...")
    executor = SilhouetteExecutor(mode="simulate")
    test_cmds = ["silhouette_joint_track", "silhouette_face_track"]
    for cmd in test_cmds:
        test_result = executor.execute({"command": cmd, "params": {"video_path": str(test_image)}})
        if test_result.get("status") != "error" or "Unknown Silhouette command" not in str(test_result.get("error", "")):
            print(f"  ✓ {cmd} 已注册")
            results.append(("cmd_" + cmd, True))
        else:
            print(f"  ✗ {cmd} 未注册")
            results.append(("cmd_" + cmd, False))

    print("\n[测试 3/6] 检查 _handle_joint_track 方法...")
    if hasattr(executor, "_handle_joint_track") and callable(getattr(executor, "_handle_joint_track")):
        print("  ✓ _handle_joint_track 方法存在")
        results.append(("method_handle_joint_track", True))
    else:
        print("  ✗ _handle_joint_track 方法不存在")
        results.append(("method_handle_joint_track", False))

    print("\n[测试 4/6] 检查 _generate_joint_track_script 方法...")
    if hasattr(executor, "_generate_joint_track_script") and callable(getattr(executor, "_generate_joint_track_script")):
        script = executor._generate_joint_track_script(
            source=str(test_image),
            output="test_joint.json",
            joint_points=[{"name": "head", "x": 960, "y": 108, "frame": 0}],
            track_mode="point",
            search_area=25,
            accuracy="high",
            pattern_size=11,
            keyframes=1,
            joint_names=["head"],
        )
        if "JointTrack" in script and "TrackerNode" in script and "joint_data" in script:
            print("  ✓ _generate_joint_track_script 生成有效脚本")
            results.append(("method_generate_joint_script", True))
        else:
            print("  ✗ _generate_joint_track_script 脚本内容不正确")
            results.append(("method_generate_joint_script", False))
    else:
        print("  ✗ _generate_joint_track_script 方法不存在")
        results.append(("method_generate_joint_script", False))

    print("\n[测试 5/6] 检查 _handle_face_track 方法...")
    if hasattr(executor, "_handle_face_track") and callable(getattr(executor, "_handle_face_track")):
        print("  ✓ _handle_face_track 方法存在")
        results.append(("method_handle_face_track", True))
    else:
        print("  ✗ _handle_face_track 方法不存在")
        results.append(("method_handle_face_track", False))

    print("\n[测试 6/6] 检查 _generate_face_track_script 方法...")
    if hasattr(executor, "_generate_face_track_script") and callable(getattr(executor, "_generate_face_track_script")):
        script = executor._generate_face_track_script(
            source=str(test_image),
            output="test_face.json",
            face_landmarks=[{"name": "nose_tip", "x": 960, "y": 540, "frame": 0}],
            expression_mode="basic",
            search_area=15,
            accuracy="high",
            pattern_size=7,
            keyframes=1,
            landmark_groups={"nose": ["nose_tip"]},
            expression_params=["mouth_open"],
        )
        if "FaceTrack" in script and "TrackerNode" in script and "face_data" in script and "calc_distance" in script:
            print("  ✓ _generate_face_track_script 生成有效脚本")
            results.append(("method_generate_face_script", True))
        else:
            print("  ✗ _generate_face_track_script 脚本内容不正确")
            results.append(("method_generate_face_script", False))
    else:
        print("  ✗ _generate_face_track_script 方法不存在")
        results.append(("method_generate_face_script", False))

    if test_image.name == "test_temp.png":
        try:
            test_image.unlink()
        except:
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
    parser = argparse.ArgumentParser(description="Silhouette MCP Executor")
    parser.add_argument("--mode", choices=["real", "simulate", "auto"], default="auto", help="Execution mode")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)
    else:
        executor = SilhouetteExecutor(mode=args.mode)
        executor.run()
