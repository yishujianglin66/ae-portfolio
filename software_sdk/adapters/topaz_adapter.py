"""
software_sdk/adapters/topaz_adapter.py - Topaz Video AI 适配器

通过 subprocess 调用 topazcli.exe 进行视频增强。
从 topaz_integration.py 迁移核心逻辑。
"""
from __future__ import annotations

import logging
import os
import subprocess
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


class TopazAdapter(BaseSoftwareAdapter):
    """Topaz Video AI 适配器 - 视频超分辨率/补帧/降噪。

    支持：
    - Upscale (超分辨率)
    - Interpolate (补帧/慢动作)
    - Denoise (降噪)
    - Sharpen (锐化)
    - Stabilize (稳定)
    """

    # Topaz 模型列表
    MODELS = {
        "proteus": "Proteus (通用增强)",
        "artemis": "Artemis (低质量视频)",
        "gaia": "Gaia (高质量视频)",
        "iris": "Iris (人脸增强)",
        "rhea": "Rhea (动画/卡通)",
        "nyx": "Nyx (降噪)",
        "theseus": "Theseus (隔行扫描)",
    }

    def __init__(
        self,
        config: SoftwareConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.TOPAZ_VIDEO_AI)
        super().__init__(config, logger)

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.TOPAZ_VIDEO_AI,
            capabilities={
                SoftwareCapability.UPSCALING,
                SoftwareCapability.INTERPOLATION,
                SoftwareCapability.DENOSING,
                SoftwareCapability.STABILIZATION,
                SoftwareCapability.RENDERING,
            },
            supported_formats_input={
                ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".mxf",
            },
            supported_formats_output={
                ".mp4", ".mov", ".prores",
            },
            gpu_accelerated=True,
            scriptable=False,
        )

    def connect(self) -> bool:
        """检查 Topaz Video AI 是否可用。"""
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
            self._set_error("Topaz Video AI not found")
            return False
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        """执行 Topaz 任务。"""
        self._mark_task_start()
        try:
            task_type = task.task_type
            params = task.params

            if task_type == "upscale":
                return self._upscale(params)
            elif task_type == "interpolate":
                return self._interpolate(params)
            elif task_type == "denoise":
                return self._denoise(params)
            elif task_type == "stabilize":
                return self._stabilize(params)
            else:
                return {"success": False, "error": f"Unknown task: {task_type}"}
        except Exception as e:
            self._set_error(f"Task failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _upscale(self, params: dict[str, Any]) -> dict[str, Any]:
        """视频超分辨率。"""
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        model = params.get("model", "proteus")
        scale = params.get("scale", 2)

        cmd = self._build_cmd(input_path, output_path, model, scale=scale)
        return self._run_topaz(cmd, params)

    def _interpolate(self, params: dict[str, Any]) -> dict[str, Any]:
        """视频补帧/慢动作。"""
        input_path = params.get("input", "")
        output_path = params.get("output", "")
        fps = params.get("target_fps", 60)

        cmd = [
            "--model", "chroma",
            "--fps", str(fps),
        ]
        return self._run_topaz(cmd, params, input_path, output_path)

    def _denoise(self, params: dict[str, Any]) -> dict[str, Any]:
        """视频降噪。"""
        input_path = params.get("input", "")
        output_path = params.get("output", "")

        cmd = self._build_cmd(input_path, output_path, "nyx")
        return self._run_topaz(cmd, params)

    def _stabilize(self, params: dict[str, Any]) -> dict[str, Any]:
        """视频稳定。"""
        input_path = params.get("input", "")
        output_path = params.get("output", "")

        cmd = [
            "--stabilize",
        ]
        return self._run_topaz(cmd, params, input_path, output_path)

    def _build_cmd(
        self,
        input_path: str,
        output_path: str,
        model: str,
        scale: int = 2,
    ) -> list[str]:
        """构建 Topaz CLI 命令。"""
        cmd = [
            "--model", model,
            "--scale", str(scale),
        ]
        return cmd

    def _run_topaz(
        self,
        args: list[str],
        params: dict[str, Any],
        input_path: str = "",
        output_path: str = "",
    ) -> dict[str, Any]:
        """运行 Topaz 命令。"""
        exe = self.config.executable_path
        if not exe:
            return {"success": False, "error": "Topaz path not configured"}

        input_path = input_path or params.get("input", "")
        output_path = output_path or params.get("output", "")

        if not input_path:
            return {"success": False, "error": "No input file specified"}

        cmd = [exe, "-i", input_path] + args
        if output_path:
            cmd += ["-o", output_path]

        self.logger.info(f"Running Topaz: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 1800),
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-1000:] if result.stderr else "",
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Topaz command timed out"}
        except FileNotFoundError:
            return {"success": False, "error": f"Topaz not found at: {exe}"}

    @staticmethod
    def _common_paths() -> list[str]:
        """Topaz Video AI 常见安装路径。"""
        return [
            r"C:\Program Files\Topaz Labs LLC\Topaz Video AI\topazcli.exe",
            r"C:\Program Files\Topaz Labs\Topaz Video AI\topazcli.exe",
            r"C:\Program Files (x86)\Topaz Labs LLC\Topaz Video AI\topazcli.exe",
        ]
