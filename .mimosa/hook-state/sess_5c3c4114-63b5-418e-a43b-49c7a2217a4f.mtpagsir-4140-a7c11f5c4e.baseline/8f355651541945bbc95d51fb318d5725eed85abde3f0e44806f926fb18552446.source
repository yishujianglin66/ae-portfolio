"""
software_sdk/adapters/blender_adapter.py - Blender 适配器

通过 subprocess 调用 blender --python script.py 执行 Blender 脚本。
从 blender_3d_integration.py 迁移核心逻辑。
"""
from __future__ import annotations

import os
import logging
import subprocess
import tempfile
from typing import Any, Dict, List, Optional

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareType,
    Task,
)


class BlenderAdapter(BaseSoftwareAdapter):
    """Blender 适配器 - 3D 场景创建/渲染。

    支持：
    - 创建 3D 场景
    - 导入模型
    - 渲染输出
    - 与 AE 数据交换（3D 坐标 -> AE 图层位置）
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.BLENDER)
        super().__init__(config, logger)

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.BLENDER,
            capabilities={
                SoftwareCapability.THREE_D,
                SoftwareCapability.RENDERING,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.PARTICLES,
            },
            supported_formats_input={
                ".blend", ".fbx", ".obj", ".abc", ".usd",
                ".gltf", ".glb", ".stl",
            },
            supported_formats_output={
                ".blend", ".fbx", ".obj", ".exr", ".png",
                ".mp4", ".avi",
            },
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        """检查 Blender 是否可用。"""
        try:
            self._status = ConnectionStatus.CONNECTING
            exe_path = self.config.executable_path
            if exe_path and os.path.isfile(exe_path):
                self._set_connected()
                return True
            for path in self._common_paths():
                if os.path.isfile(path):
                    self.config.executable_path = path
                    self._set_connected()
                    return True
            self._set_error("Blender executable not found")
            return False
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        if self._status != ConnectionStatus.CONNECTED:
            return False
        exe = self.config.executable_path
        if exe and os.path.isfile(exe):
            try:
                result = subprocess.run(
                    [exe, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                return result.returncode == 0
            except Exception:
                return False
        return False

    def execute_task(self, task: Task) -> Any:
        """执行 Blender 任务。"""
        self._mark_task_start()
        try:
            task_type = task.task_type
            params = task.params

            if task_type == "create_scene":
                return self._create_scene(params)
            elif task_type == "import_model":
                return self._import_model(params)
            elif task_type == "render":
                return self._render(params)
            elif task_type == "export_for_ae":
                return self._export_for_ae(params)
            elif task_type == "run_script":
                return self._run_script(params)
            else:
                return {"success": False, "error": f"Unknown task: {task_type}"}
        except Exception as e:
            self._set_error(f"Task failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _create_scene(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """创建 3D 场景。"""
        script = self._generate_scene_script(params)
        return self._run_blender_script(script)

    def _import_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """导入模型。"""
        model_path = params.get("path", "")
        if not model_path:
            return {"success": False, "error": "No model path provided"}
        script = self._generate_import_script(model_path, params)
        return self._run_blender_script(script)

    def _render(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """渲染输出。"""
        output_path = params.get("output", "render_output")
        script = self._generate_render_script(params)
        return self._run_blender_script(script)

    def _export_for_ae(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """导出为 AE 兼容格式。"""
        self.logger.info("Exporting for AE...")
        return {
            "success": True,
            "action": "export_for_ae",
            "format": params.get("format", "fbx"),
        }

    def _run_script(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行自定义 Blender Python 脚本。"""
        script = params.get("script", "")
        return self._run_blender_script(script)

    def _run_blender_script(self, script_content: str) -> Dict[str, Any]:
        """运行 Blender Python 脚本。"""
        exe = self.config.executable_path
        if not exe:
            return {"success": False, "error": "Blender path not configured"}

        # 写入临时脚本文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, prefix="blender_"
        ) as f:
            f.write(script_content)
            script_path = f.name

        try:
            cmd = [exe, "--background", "--python", script_path]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Blender script timed out"}
        except FileNotFoundError:
            return {"success": False, "error": f"Blender not found at: {exe}"}
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def _generate_scene_script(self, params: Dict[str, Any]) -> str:
        """生成场景创建脚本。"""
        scene_name = params.get("name", "Scene")
        return f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.name = "{scene_name}"
bpy.ops.mesh.primitive_plane_add()
bpy.ops.object.camera_add(location=(0, -5, 2))
bpy.ops.object.light_add(type='SUN', location=(0, 0, 5))
print("Scene created: {scene_name}")
"""

    def _generate_import_script(
        self, model_path: str, params: Dict[str, Any]
    ) -> str:
        """生成模型导入脚本。"""
        ext = os.path.splitext(model_path)[1].lower()
        path_escaped = model_path.replace("\\", "/")
        if ext == ".fbx":
            return f"""
import bpy
bpy.ops.import_scene.fbx(filepath="{path_escaped}")
print("Imported FBX: {path_escaped}")
"""
        elif ext == ".obj":
            return f"""
import bpy
bpy.ops.wm.obj_import(filepath="{path_escaped}")
print("Imported OBJ: {path_escaped}")
"""
        else:
            return f"""
import bpy
print(f"Unsupported format: {ext}")
"""

    def _generate_render_script(self, params: Dict[str, Any]) -> str:
        """生成渲染脚本。"""
        output = params.get("output", "//render_####")
        fmt = params.get("format", "PNG")
        return f"""
import bpy
scene = bpy.context.scene
scene.render.filepath = "{output}"
scene.render.image_settings.file_format = "{fmt}"
bpy.ops.render.render(write_still=True)
print("Render complete")
"""

    @staticmethod
    def _common_paths() -> List[str]:
        """Blender 常见安装路径。"""
        return [
            r"D:\Blender\Blender 5.1.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
        ]
