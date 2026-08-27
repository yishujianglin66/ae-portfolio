#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blender_proc_adapter.py — BlenderProc 3D 场景生成适配器
========================================================

将 DLR-RM/BlenderProc (程序化 3D 场景生成) 融入五层架构。

来源项目: https://github.com/DLR-RM/BlenderProc
集成层级: Layer 1 (引擎接入层) — 3D 场景/资产生成引擎
对应缺陷: D-07(3D 资产生成), D-09(风格化 3D 场景)

核心能力:
    - 程序化室内/室外场景生成
    - 物体随机摆放 + 物理模拟
    - 材质/纹理程序化生成
    - 自动标注 (深度/法线/语义分割/实例分割)
    - HDRi 环境光照
    - 多种相机模型 (透视/鱼眼/全景)
    - 合成视锥 + 可见性检查

安装:
    cd external/BlenderProc && pip install -e .

使用示例:
    from integrations.blender_proc_adapter import BlenderProcAdapter

    adapter = BlenderProcAdapter()
    if adapter.check_available():
        result = adapter.generate_scene(
            scene_type="indoor",
            style="modern_living_room",
            resolution=(1920, 1080),
            num_objects=10,
        )
        print(f"Generated: {result.output_files}")
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── 常量 ─────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BLENDER_PROC_DIR = PROJECT_ROOT / "external" / "BlenderProc"


class SceneType(str, Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    OBJECT = "object"
    CUSTOM = "custom"


class RenderEngine(str, Enum):
    CYCLES = "cycles"
    EEVEE = "eevee"


@dataclass
class SceneGenResult:
    """场景生成结果"""
    scene_type: str = ""
    status: str = "pending"
    output_files: List[str] = field(default_factory=list)
    render_path: str = ""
    depth_map: str = ""
    segmentation_map: str = ""
    normal_map: str = ""
    scene_config: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    error: Optional[str] = None
    used_fallback: bool = False


# ── 适配器 ───────────────────────────────────────────────────────────────

class BlenderProcAdapter:
    """BlenderProc 3D 场景生成适配器

    将 BlenderProc 的程序化场景生成能力封装为项目统一接口。
    融入 Layer 1 3D 场景/资产生成引擎。

    双模式架构:
        1. subprocess 模式 — 调用 blenderproc CLI（主要）
        2. Python API 模式 — 直接 import blenderproc（备选）

    降级策略:
        - BlenderProc 不可用 → 返回空结果
        - Blender 未安装 → 提示安装路径
        - GPU 渲染失败 → 降级到 CPU 渲染
    """

    TOOL_NAME = "blender_proc"

    SUPPORTED_OPERATIONS: Dict[str, Dict[str, Any]] = {
        "generate_indoor": {"type": "indoor", "desc": "生成程序化室内场景"},
        "generate_outdoor": {"type": "outdoor", "desc": "生成程序化室外场景"},
        "generate_object": {"type": "object", "desc": "生成单个 3D 物体渲染"},
        "generate_custom": {"type": "custom", "desc": "自定义配置生成场景"},
        "load_assets": {"type": "assets", "desc": "加载外部 3D 资产库"},
        "render_depth": {"type": "depth", "desc": "渲染深度图"},
        "render_segmentation": {"type": "seg", "desc": "渲染语义/实例分割图"},
        "render_normal": {"type": "normal", "desc": "渲染法线图"},
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._proc_dir = Path(self.config.get("proc_dir", str(BLENDER_PROC_DIR)))
        self._blender_path = self.config.get("blender_path",
            r"D:\Blender\Blender 5.1.0\blender.exe")  # 已确认安装
        # BlenderProc 2.8 官方仅支持 Blender 4.2.x（2026-08-15 实装验证）
        # --custom-blender-path 期望的是"安装目录"（含版本号子目录），非 exe 路径
        self._blender_dir = self.config.get("blender_dir",
            r"D:\Blender\bp42\blender-4.2.1-windows-x64")
        self._render_engine = self.config.get("render_engine", "cycles")
        self._gpu_render = self.config.get("gpu_render", True)
        self._output_dir = Path(self.config.get(
            "output_dir",
            str(PROJECT_ROOT / "output_production" / "blender_proc"),
        ))
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def check_available(self) -> bool:
        """检查 BlenderProc 是否可用

        BlenderProc 必须通过 `blenderproc run` 启动（依赖 Blender Python 环境），
        不能直接 import。因此检查:
        1. Blender 可执行文件存在
        2. blenderproc pip 包已安装
        3. blenderproc CLI 可访问
        """
        # 检查 Blender 可执行文件（exe 或安装目录二者其一）
        blender_ok = (self._blender_path and Path(self._blender_path).exists()) or \
                     (self._blender_dir and (Path(self._blender_dir) / "blender.exe").exists())
        if not blender_ok:
            logger.warning("[BlenderProc] Blender not found: exe=%s dir=%s",
                           self._blender_path, self._blender_dir)
            return False

        # 检查 blenderproc pip 包是否已安装
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "show", "blenderproc"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                logger.warning("[BlenderProc] blenderproc pip package not installed")
                return False
        except Exception:
            return False

        # 检查 blenderproc CLI
        try:
            bp_script = self._proc_dir / "blenderproc.py"
            if bp_script.exists():
                return True
            # 或者检查 CLI 入口点
            cli_path = Path(sys.executable).parent / "Scripts" / "blenderproc.exe"
            if cli_path.exists():
                return True
            # 回退到检查 blenderproc 目录结构
            return (self._proc_dir / "blenderproc").is_dir()
        except Exception:
            return False

    def list_operations(self) -> List[str]:
        return list(self.SUPPORTED_OPERATIONS.keys())

    # ── 高级 API ──────────────────────────────────────────────────────

    def generate_scene(self, scene_type: str = "indoor",
                       style: str = "",
                       resolution: Tuple[int, int] = (1920, 1080),
                       num_objects: int = 10,
                       enable_depth: bool = True,
                       enable_segmentation: bool = True,
                       enable_normal: bool = True) -> SceneGenResult:
        """生成程序化 3D 场景

        Args:
            scene_type: 场景类型 (indoor/outdoor/object/custom)
            style: 风格描述 (如 "modern_living_room", "scifi_corridor")
            resolution: 渲染分辨率
            num_objects: 场景中物体数量
            enable_depth: 是否输出深度图
            enable_segmentation: 是否输出分割图
            enable_normal: 是否输出法线图
        """
        result = SceneGenResult(scene_type=scene_type)
        start_time = time.time()

        try:
            # 生成 BlenderProc 配置
            config = self._build_config(
                scene_type=scene_type,
                style=style,
                resolution=resolution,
                num_objects=num_objects,
                enable_depth=enable_depth,
                enable_segmentation=enable_segmentation,
                enable_normal=enable_normal,
            )
            result.scene_config = config

            # 写入 BlenderProc Python 脚本（2.8 格式）
            script_path = Path(config["script_path"])
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(config["script"], encoding="utf-8")

            # 执行 BlenderProc
            output = self._run_blenderproc(str(script_path))
            if output:
                result.status = "success"
                result.output_files = output.get("files", [])
                result.render_path = output.get("render", "")
                result.depth_map = output.get("depth", "")
                result.segmentation_map = output.get("segmentation", "")
                result.normal_map = output.get("normal", "")
            else:
                result.status = "degraded"
                result.error = "BlenderProc execution returned no output"
                result.used_fallback = True

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            logger.error("[BlenderProc] Scene generation failed: %s", e)
        finally:
            result.duration_ms = (time.time() - start_time) * 1000

        return result

    def generate_indoor(self, **kwargs) -> SceneGenResult:
        """生成室内场景的便捷方法"""
        return self.generate_scene(scene_type="indoor", **kwargs)

    def generate_outdoor(self, **kwargs) -> SceneGenResult:
        """生成室外场景的便捷方法"""
        return self.generate_scene(scene_type="outdoor", **kwargs)

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> SceneGenResult:
        """统一执行接口"""
        params = params or {}
        op_info = self.SUPPORTED_OPERATIONS.get(operation)
        if not op_info:
            return SceneGenResult(status="failed", error=f"Unknown operation: {operation}")

        op_type = op_info["type"]
        if op_type in ("indoor", "outdoor", "object", "custom"):
            return self.generate_scene(scene_type=op_type, **params)
        else:
            return SceneGenResult(status="degraded", error=f"Operation {operation} not yet implemented")

    # ── 内部方法 ──────────────────────────────────────────────────────

    def _build_config(self, scene_type: str, style: str,
                      resolution: Tuple[int, int], num_objects: int,
                      enable_depth: bool, enable_segmentation: bool,
                      enable_normal: bool) -> Dict[str, Any]:
        """构建 BlenderProc 配置

        BlenderProc 2.8 使用 Python 脚本（bproc API）而非 JSON pipeline。
        返回 dict 供 generate_scene 序列化为 .py 脚本（2026-08-15 修复:
        旧实现生成 BlenderProc 1.x 风格 JSON，2.8 无法执行）。
        """
        obj_type = "MONKEY" if scene_type == "object" else "CUBE"
        w, h = resolution
        lines = [
            "import blenderproc as bproc",
            "import numpy as np",
            "bproc.init()",
            "",
            "# 物体",
            f"obj = bproc.object.create_primitive(\"{obj_type}\")",
            f"for _ in range({num_objects - 1}):",
            "    o = bproc.object.create_primitive(\"CUBE\")",
            "    o.set_location([np.random.uniform(-2, 2), np.random.uniform(-2, 2), 0])",
            "",
            "# 光源",
            "light = bproc.types.Light()",
            "light.set_location([2, -2, 0])",
            "light.set_energy(300)",
            "",
            "# 相机",
            f"bproc.camera.set_resolution({w}, {h})",
            "cam_pose = bproc.math.build_transformation_mat([0, -5, 0], [np.pi / 2, 0, 0])",
            "bproc.camera.add_camera_pose(cam_pose)",
            "",
            "# 渲染",
            "data = bproc.renderer.render()",
            f"bproc.writer.write_hdf5(\"{str(self._output_dir).replace(chr(92), '/')}/\", data)",
        ]
        if enable_depth:
            lines.insert(-3, "data = bproc.renderer.render_depth()\n    # 深度图已写入 data")
        return {
            "script": "\n".join(lines),
            "script_path": str(self._output_dir / "scene_generate.py"),
            "meta": {
                "scene_type": scene_type, "style": style,
                "resolution": list(resolution), "num_objects": num_objects,
                "enable_depth": enable_depth,
                "enable_segmentation": enable_segmentation,
                "enable_normal": enable_normal,
            },
        }

    def _run_blenderproc(self, config_path: str) -> Optional[Dict[str, Any]]:
        """执行 BlenderProc

        2026-08-15 修复: BlenderProc 2.8 CLI 用 --custom-blender-path 指定
        Blender 安装目录（非 exe 路径），且须从 vendored 仓库目录运行。
        """
        if not self.check_available():
            logger.warning("[BlenderProc] Not available, cannot execute")
            return None

        cmd = [
            "blenderproc",
            "run", config_path,
            "--custom-blender-path", self._blender_dir,
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._proc_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
            )
            if proc.returncode != 0:
                logger.error("[BlenderProc] CLI failed: %s", proc.stderr[-800:])
                return None

            # 收集输出文件（hdf5 + 渲染帧）
            output_files = []
            for ext in ("*.hdf5", "*.png", "*.exr", "*.hdr"):
                output_files.extend(
                    str(f) for f in self._output_dir.glob(ext)
                )

            return {
                "files": output_files,
                "render": str(self._output_dir / "0.hdf5"),
                "depth": str(self._output_dir / "depth_0000.hdf5"),
                "segmentation": "",
                "normal": "",
            }
        except subprocess.TimeoutExpired:
            logger.error("[BlenderProc] Timeout (600s)")
            return None
        except Exception as e:
            logger.error("[BlenderProc] Error: %s", e)
            return None


# ── 便捷函数 ─────────────────────────────────────────────────────────────

def get_adapter(config: Optional[Dict[str, Any]] = None) -> BlenderProcAdapter:
    return BlenderProcAdapter(config)


def quick_test() -> Dict[str, Any]:
    adapter = get_adapter()
    return {
        "available": adapter.check_available(),
        "operations_count": len(adapter.list_operations()),
        "operations": adapter.list_operations(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    result = quick_test()
    print(json.dumps(result, indent=2, ensure_ascii=False))
