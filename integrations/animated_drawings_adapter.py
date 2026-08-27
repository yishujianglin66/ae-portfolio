"""
integrations/animated_drawings_adapter.py — Meta AnimatedDrawings 涂鸦动画适配器
================================================================================

Meta AnimatedDrawings: 涂鸦 → 骨骼 → 动画
  - 从手绘涂鸦自动检测角色结构
  - 自动骨骼绑定 + 动画生成
  - 支持多种预定义动作 (走路/跑步/跳跃/跳舞)
  - GitHub: https://github.com/facebookresearch/AnimatedDrawings

集成点:
  - 手书动画管线: 涂鸦 → AnimatedDrawings → 角色动画
  - 木偶动画增强: 与 puppet-automation 互补

用法:
    from integrations.animated_drawings_adapter import AnimatedDrawingsAdapter
    adapter = AnimatedDrawingsAdapter()
    result = adapter.execute("animate_drawing", {
        "image_path": "doodle.png",
        "motion": "walk",
        "output_path": "animated_doodle.mp4",
    })
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXTERNAL_DIR = _PROJECT_ROOT / "external"
_AD_DIR = _EXTERNAL_DIR / "AnimatedDrawings"


class AnimatedDrawingsAdapter:
    """Meta AnimatedDrawings 涂鸦动画适配器"""

    TOOL_NAME = "animated_drawings"
    SUPPORTED_OPERATIONS = [
        "animate_drawing",
        "check_environment",
        "list_motions",
        "get_model_info",
    ]

    # 预定义动作列表
    PREDEFINED_MOTIONS = [
        "walk", "run", "jump", "dance",
        "idle", "wave", "kick", "swing_dance",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._source_available = _AD_DIR.is_dir()
        self._simulate = not self._source_available
        self._env_check = self._check_environment()

    def _check_environment(self) -> Dict[str, Any]:
        checks = {
            "source_cloned": self._source_available,
            "simulate_mode": self._simulate,
        }
        for mod in ["torch", "torchvision", "detectron2"]:
            try:
                __import__(mod)
                checks[f"dep_{mod}"] = True
            except ImportError:
                checks[f"dep_{mod}"] = False
        return checks

    def check_available(self) -> bool:
        return self._source_available and self._env_check.get("dep_torch", False)

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}

        if operation == "check_environment":
            return self._env_check
        elif operation == "list_motions":
            return {"status": "success", "motions": self.PREDEFINED_MOTIONS}
        elif operation == "get_model_info":
            return self._get_model_info()
        elif operation == "animate_drawing":
            return self._animate_drawing(params)
        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _get_model_info(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "model_name": "AnimatedDrawings",
            "org": "Meta AI Research",
            "github": "https://github.com/facebookresearch/AnimatedDrawings",
            "license": "MIT",
            "paper": "Animating Drawings with Motion-Capture (SIGGRAPH 2022)",
            "key_features": [
                "从涂鸦自动检测角色结构",
                "自动骨骼提取和绑定",
                "30+ 预定义动作模板",
                "支持自定义动作文件",
            ],
        }

    def _animate_drawing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_path = params.get("image_path", "")
        motion = params.get("motion", "walk")
        output_path = params.get("output_path", "")

        if not image_path:
            return {"status": "error", "message": "image_path is required"}

        if self._simulate:
            return {
                "status": "success",
                "mode": "simulate",
                "message": "AnimatedDrawings 未克隆，使用模拟模式",
                "output_path": output_path or "animated_drawing_simulate.mp4",
                "params": {"image_path": image_path, "motion": motion},
                "simulated_output": True,
            }

        try:
            cmd = [
                sys.executable, "-m", "animated_drawings",
                "-i", image_path,
                "-m", motion,
                "-o", output_path or "animated_drawing.mp4",
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=300, cwd=str(_AD_DIR),
            )
            if proc.returncode == 0:
                return {"status": "success", "mode": "real",
                        "output_path": output_path or "animated_drawing.mp4"}
            return {"status": "error", "stderr": proc.stderr[-500:]}
        except Exception as e:
            return {"status": "error", "message": str(e)}


def get_adapter(config=None):
    return AnimatedDrawingsAdapter(config)
