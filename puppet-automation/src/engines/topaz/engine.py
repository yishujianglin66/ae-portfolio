"""Topaz Video AI engine - quality enhancement."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult


class TopazEngine(BaseEngine):
    """Topaz Video AI wrapper via CLI."""

    name = "topaz"

    MODELS = {
        "proteus": "Proteus",
        "artemis": "Artemis",
        "gaia": "Gaia",
        "theia": "Theia",
        "nyx": "Nyx",
        "iris": "Iris",
    }

    def __init__(self, executable_path: Path | str | None = None):
        path = Path(executable_path) if executable_path else settings.topaz_path
        super().__init__(path)

    async def enhance(
        self,
        input_path: Path | str,
        output_path: Path | str,
        model: str = "proteus",
        scale: float = 2.0,
        fps: int | None = None,
        denoise: int = 50,
        deblur: int = 30,
        extra_args: list[str] | None = None,
    ) -> EngineResult:
        """Enhance video quality with Topaz AI."""
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if model not in self.MODELS:
            return EngineResult(
                success=False,
                error=f"Unknown model: {model}. Available: {list(self.MODELS)}",
            )

        cmd = [
            str(self.executable_path),
            "-i", str(input_path),
            "-o", str(output_path),
            "-m", self.MODELS[model],
            "-s", str(scale),
        ]
        if fps:
            cmd.extend(["-f", str(fps)])
        cmd.extend([
            "--denoise", str(denoise),
            "--deblur", str(deblur),
        ])
        if extra_args:
            cmd.extend(extra_args)

        # 注意：_run_subprocess 返回 4 元组 (code, stdout, stderr, error_code)
        code, _stdout, stderr, _err_code = await asyncio.to_thread(
            self._run_subprocess, cmd, timeout=14400
        )
        return EngineResult(
            success=code == 0,
            output_path=output_path if code == 0 else None,
            metadata={
                "model": model,
                "scale": scale,
                "fps": fps,
                "denoise": denoise,
            },
            error=stderr if code != 0 else None,
        )

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】action 调度；available 短路/异常包裹/时长统计由基类 execute() 模板处理。"""
        action = kwargs.pop("action", "enhance")
        if action == "enhance":
            return await self.enhance(**kwargs)
        return EngineResult(success=False, error=f"Unknown action: {action}")
