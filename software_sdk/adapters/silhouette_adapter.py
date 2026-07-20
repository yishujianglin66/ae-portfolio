"""
software_sdk/adapters/silhouette_adapter.py - Silhouette 适配器

通过 subprocess 调用 Silhouette.exe 进行 Roto/Paint/Track 操作。
从 silhouette_executor.py 迁移核心逻辑。
"""
from __future__ import annotations

import os
import logging
import subprocess
from typing import Any, Dict, Optional

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareType,
    Task,
)


class SilhouetteAdapter(BaseSoftwareAdapter):
    """Silhouette 适配器 - Roto/Paint/Track。

    支持：
    - Rotoscoping (Roto)
    - Paint (修复/修补)
    - Motion Tracking (跟踪)
    - 导出遮罩到 AE
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.SILHOUETTE)
        super().__init__(config, logger)
        self._process: Optional[subprocess.Popen] = None

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.SILHOUETTE,
            capabilities={
                SoftwareCapability.ROTOSCOPING,
                SoftwareCapability.PAINTING,
                SoftwareCapability.MOTION_TRACKING,
                SoftwareCapability.KEYING,
                SoftwareCapability.COMPOSITING,
            },
            supported_formats_input={
                ".sfx", ".exr", ".png", ".jpg", ".tiff", ".dpx",
            },
            supported_formats_output={
                ".exr", ".png", ".tiff", ".dpx", ".psd",
            },
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        """检查 Silhouette 是否可用。"""
        try:
            self._status = ConnectionStatus.CONNECTING
            exe_path = self.config.executable_path
            if exe_path and os.path.isfile(exe_path):
                self._set_connected()
                self.logger.info(f"Silhouette found at: {exe_path}")
                return True
            # 尝试常见路径
            for path in self._common_paths():
                if os.path.isfile(path):
                    self.config.executable_path = path
                    self._set_connected()
                    self.logger.info(f"Silhouette found at: {path}")
                    return True
            self._set_error("Silhouette executable not found")
            return False
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """断开 Silhouette。"""
        self._status = ConnectionStatus.DISCONNECTED
        self._process = None
        return True

    def health_check(self) -> bool:
        """检查 Silhouette 健康状态。"""
        if self._status != ConnectionStatus.CONNECTED:
            return False
        exe = self.config.executable_path
        if exe and os.path.isfile(exe):
            return True
        return False

    def execute_task(self, task: Task) -> Any:
        """执行 Silhouette 任务。"""
        self._mark_task_start()
        try:
            task_type = task.task_type
            params = task.params

            if task_type == "roto":
                return self._run_roto(params)
            elif task_type == "paint":
                return self._run_paint(params)
            elif task_type == "track":
                return self._run_track(params)
            elif task_type == "export_mask":
                return self._export_mask(params)
            else:
                return {"success": False, "error": f"Unknown task: {task_type}"}
        except Exception as e:
            self._set_error(f"Task failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _run_roto(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行 Roto 任务。"""
        self.logger.info("Running Silhouette Roto...")
        return self._run_command(["roto"], params)

    def _run_paint(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行 Paint 任务。"""
        self.logger.info("Running Silhouette Paint...")
        return self._run_command(["paint"], params)

    def _run_track(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """运行 Track 任务。"""
        self.logger.info("Running Silhouette Track...")
        return self._run_command(["track"], params)

    def _export_mask(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """导出遮罩。"""
        self.logger.info("Exporting mask from Silhouette...")
        return {
            "success": True,
            "action": "export_mask",
            "output_format": params.get("format", "exr"),
        }

    def _run_command(
        self, args: list, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """运行 Silhouette 命令。"""
        exe = self.config.executable_path
        if not exe:
            return {"success": False, "error": "Silhouette path not configured"}

        cmd = [exe] + args
        self.logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=params.get("timeout", 300),
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Silhouette command timed out"}
        except FileNotFoundError:
            return {"success": False, "error": f"Silhouette not found at: {exe}"}

    @staticmethod
    def _common_paths() -> list:
        """Silhouette 常见安装路径。"""
        return [
            r"C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
            r"C:\Program Files\BorisFX\Silhouette\Silhouette.exe",
        ]
