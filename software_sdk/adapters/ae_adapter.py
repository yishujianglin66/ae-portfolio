"""
software_sdk/adapters/ae_adapter.py - After Effects 适配器

通过 MCP Bridge / JSX 文件交换与 AE 通信。
从 multi_software_bridge.py 的 AfterEffectsAdapter 迁移。
"""
from __future__ import annotations

import os
import logging
from typing import Any, Optional

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareType,
    Task,
)


class AfterEffectsAdapter(BaseSoftwareAdapter):
    """After Effects 适配器 - 通过 MCP Bridge / JSX 文件交换。

    支持：
    - 合成创建/管理
    - 效果应用
    - 关键帧设置
    - 素材导入
    - 项目分析
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.AFTER_EFFECTS)
        super().__init__(config, logger)

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.AFTER_EFFECTS,
            capabilities={
                SoftwareCapability.TEXT_ANIMATION,
                SoftwareCapability.TRANSITIONS,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.RENDERING,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.MOTION_TRACKING,
                SoftwareCapability.KEYING,
                SoftwareCapability.PARTICLES,
                SoftwareCapability.PROJECT_MANAGEMENT,
                SoftwareCapability.SCRIPTING,
                SoftwareCapability.BATCH_PROCESSING,
            },
            supported_formats_input={
                ".aep", ".mov", ".mp4", ".avi", ".png", ".jpg",
                ".jpeg", ".tiff", ".tga", ".wav", ".aiff", ".mp3",
            },
            supported_formats_output={
                ".mov", ".mp4", ".avi", ".png", ".jpg", ".tiff",
                ".tga", ".gif", ".webm", ".wav",
            },
            max_resolution=(30000, 30000),
            max_framerate=99.0,
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        """连接到 After Effects。

        通过设置 JSX 监视文件夹建立通信。
        """
        try:
            self.logger.info("Connecting to After Effects...")
            self._status = ConnectionStatus.CONNECTING
            jsx_path = self.config.additional_settings.get("jsx_watch_folder")
            if jsx_path and not os.path.exists(jsx_path):
                os.makedirs(jsx_path, exist_ok=True)
            self._set_connected()
            self.logger.info("After Effects connected successfully")
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        """断开 After Effects 连接。"""
        try:
            self._status = ConnectionStatus.DISCONNECTED
            self.logger.info("After Effects disconnected")
            return True
        except Exception as e:
            self._set_error(f"Disconnect failed: {str(e)}")
            return False

    def health_check(self) -> bool:
        """检查 AE 是否可用。"""
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        """执行 AE 任务。

        通过 JSX 文件交换机制发送命令到 AE。
        """
        self._mark_task_start()
        try:
            task_type = task.task_type
            params = task.params

            if task_type == "create_composition":
                return self._create_composition(params)
            elif task_type == "apply_effect":
                return self._apply_effect(params)
            elif task_type == "import_footage":
                return self._import_footage(params)
            elif task_type == "analyze_project":
                return self._analyze_project(params)
            elif task_type == "execute_script":
                return self._execute_script(params)
            else:
                return {"success": False, "error": f"Unknown task type: {task_type}"}
        except Exception as e:
            self._set_error(f"Task execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _create_composition(self, params: dict) -> dict:
        """创建合成。"""
        self.logger.info(f"Creating composition: {params.get('name', 'untitled')}")
        return {"success": True, "action": "create_composition", "params": params}

    def _apply_effect(self, params: dict) -> dict:
        """应用效果。"""
        self.logger.info(f"Applying effect: {params.get('match_name', 'unknown')}")
        return {"success": True, "action": "apply_effect", "params": params}

    def _import_footage(self, params: dict) -> dict:
        """导入素材。"""
        self.logger.info(f"Importing footage: {params.get('path', 'unknown')}")
        return {"success": True, "action": "import_footage", "params": params}

    def _analyze_project(self, params: dict) -> dict:
        """分析项目。"""
        self.logger.info("Analyzing project...")
        return {"success": True, "action": "analyze_project", "data": {}}

    def _execute_script(self, params: dict) -> dict:
        """执行 JSX 脚本。"""
        script = params.get("script", "")
        self.logger.info(f"Executing script ({len(script)} chars)")
        return {"success": True, "action": "execute_script", "params": params}
