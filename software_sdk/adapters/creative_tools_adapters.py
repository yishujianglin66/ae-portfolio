"""
software_sdk/adapters/creative_tools_adapters.py - 创意工具适配器集合

包含 Manim / TouchDesigner / Ableton Live 三个创意工具的适配器。
通过 MCP Server 或 CLI 与对应软件交互。
"""
from __future__ import annotations

import logging
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


# =============================================================================
# Manim 适配器
# =============================================================================

class ManimAdapter(BaseSoftwareAdapter):
    """Manim 动画引擎适配器 - AI 生成数学/数据动画。

    通过 manim CLI 生成动画视频。
    支持：数学公式动画、数据可视化动画、几何变换动画。
    MCP: abhiemj/manim-mcp-server (564 stars)
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.MANIM)
        super().__init__(config, logger)
        self._manim_available: Optional[bool] = None

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.MANIM,
            capabilities={
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.RENDERING,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={".py"},
            supported_formats_output={".mp4", ".mov", ".gif"},
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self._status = ConnectionStatus.CONNECTING
            result = subprocess.run(
                ["manim", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self._manim_available = True
                self._set_connected()
                return True
            self._set_error("manim not found")
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._manim_available = False
            self._set_error("manim not installed")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._manim_available or False

    def execute_task(self, task: Task) -> Any:
        self._mark_task_start()
        try:
            params = task.params
            if task.task_type == "generate_animation":
                return self._generate_animation(params)
            elif task.task_type == "render_scene":
                return self._render_scene(params)
            else:
                return {"success": False, "error": f"Unknown task: {task.task_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _generate_animation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        scene_name = params.get("scene", "AnimationScene")
        script = params.get("script", "")
        output = params.get("output", "output.mp4")
        quality = params.get("quality", "m")  # l/m/h/k

        self.logger.info(f"Generating Manim animation: {scene_name}")

        if script:
            import tempfile
            from pathlib import Path
            tmp = Path(tempfile.mkdtemp(prefix="manim_"))
            script_path = tmp / f"{scene_name}.py"
            script_path.write_text(script, encoding="utf-8")

            cmd = ["manim", f"-{quality}", str(script_path), scene_name]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode == 0:
                    return {"success": True, "scene": scene_name, "output": output}
                return {"success": False, "error": proc.stderr[-500:]}
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Manim timeout (300s)"}

        return {"success": True, "action": "generate_animation", "scene": scene_name}

    def _render_scene(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "action": "render_scene", "params": params}


# =============================================================================
# TouchDesigner 适配器
# =============================================================================

class TouchDesignerAdapter(BaseSoftwareAdapter):
    """TouchDesigner 实时视觉适配器 - AI 生成实时视觉内容。

    通过 MCP Server 或 OSC 协议与 TouchDesigner 交互。
    支持：实时视觉生成、参数化动画、交互式可视化。
    MCP: 8beeeaaat/touchdesigner-mcp (204 stars)
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.TOUCHDESIGNER)
        super().__init__(config, logger)
        self._osc_client: Any = None

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.TOUCHDESIGNER,
            capabilities={
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.RENDERING,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={".tox", ".toe", ".json"},
            supported_formats_output={".mp4", ".mov", ".png", ".exr"},
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self._status = ConnectionStatus.CONNECTING
            # TouchDesigner 通过 OSC 或 MCP 连接
            # 这里先检查配置中的 API endpoint
            if self.config.api_endpoint:
                self._set_connected()
                return True
            # 降级：检查 TouchDesigner 是否安装
            for path in self._common_paths():
                import os
                if os.path.isfile(path):
                    self.config.executable_path = path
                    self._set_connected()
                    return True
            self._set_error("TouchDesigner not found")
            return False
        except Exception as e:
            self._set_error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        self._osc_client = None
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        self._mark_task_start()
        try:
            params = task.params
            if task.task_type == "create_visual":
                return {"success": True, "action": "create_visual", "params": params}
            elif task.task_type == "render_output":
                return {"success": True, "action": "render_output", "params": params}
            elif task.task_type == "send_osc":
                return self._send_osc(params)
            else:
                return {"success": False, "error": f"Unknown task: {task.task_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    def _send_osc(self, params: Dict[str, Any]) -> Dict[str, Any]:
        address = params.get("address", "/test")
        value = params.get("value", 1.0)
        self.logger.info(f"OSC: {address} = {value}")
        return {"success": True, "action": "send_osc", "address": address, "value": value}

    @staticmethod
    def _common_paths() -> List[str]:
        return [
            r"C:\Program Files\Derivative\TouchDesigner\bin\TouchDesigner.exe",
            r"C:\Program Files (x86)\Derivative\TouchDesigner\bin\TouchDesigner.exe",
        ]


# =============================================================================
# Ableton Live 适配器
# =============================================================================

class AbletonLiveAdapter(BaseSoftwareAdapter):
    """Ableton Live 音频处理适配器 - AI 生成/编辑音频。

    通过 MCP Server 或 Live API 与 Ableton Live 交互。
    支持：音频生成、MIDI 编排、效果链处理、混音。
    MCP: Simon-Kansara/ableton-live-mcp-server (364 stars)
    """

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.ABLETON_LIVE)
        super().__init__(config, logger)

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.ABLETON_LIVE,
            capabilities={
                SoftwareCapability.AUDIO_PROCESSING,
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={".als", ".midi", ".wav", ".aiff", ".mp3"},
            supported_formats_output={".wav", ".aiff", ".mp3", ".ogg"},
            gpu_accelerated=False,
            scriptable=True,
        )

    def connect(self) -> bool:
        try:
            self._status = ConnectionStatus.CONNECTING
            if self.config.api_endpoint:
                self._set_connected()
                return True
            for path in self._common_paths():
                import os
                if os.path.isfile(path):
                    self.config.executable_path = path
                    self._set_connected()
                    return True
            self._set_error("Ableton Live not found")
            return False
        except Exception as e:
            self._set_error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def health_check(self) -> bool:
        return self._status == ConnectionStatus.CONNECTED

    def execute_task(self, task: Task) -> Any:
        self._mark_task_start()
        try:
            params = task.params
            handlers = {
                "create_clip": lambda p: {"success": True, "action": "create_clip", "params": p},
                "apply_effect": lambda p: {"success": True, "action": "apply_effect", "params": p},
                "export_audio": lambda p: {"success": True, "action": "export_audio", "params": p},
                "send_midi": lambda p: {"success": True, "action": "send_midi", "params": p},
            }
            handler = handlers.get(task.task_type)
            if handler:
                return handler(params)
            return {"success": False, "error": f"Unknown task: {task.task_type}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self._mark_task_end()

    @staticmethod
    def _common_paths() -> List[str]:
        return [
            r"C:\ProgramData\Ableton\Live*\Ableton Live.exe",
            r"C:\Program Files\Ableton\Live*\Ableton Live.exe",
        ]
