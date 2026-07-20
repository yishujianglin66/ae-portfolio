"""Engine base classes and shared interfaces."""
from __future__ import annotations

import abc
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


@dataclass
class EngineResult:
    """Standard engine execution result."""
    success: bool
    output_path: Optional[Path] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_seconds: float = 0.0


class BaseEngine(abc.ABC):
    """Abstract base class for all engine integrations."""

    name: str = "base"

    def __init__(self, executable_path: Path | str):
        self.executable_path = Path(executable_path)
        self._verify_executable()

    def _verify_executable(self) -> None:
        """Verify engine executable exists."""
        if not self.executable_path.exists():
            logger.warning(
                f"{self.name} executable not found at {self.executable_path}"
            )

    @abc.abstractmethod
    async def execute(self, *args, **kwargs) -> EngineResult:
        """Execute engine task. Subclasses must implement."""
        ...

    def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int = 3600,
        cwd: Optional[Path] = None,
    ) -> tuple[int, str, str]:
        """Run subprocess and capture output."""
        logger.debug(f"[{self.name}] Running: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"[{self.name}] Command timed out after {timeout}s")
            return -1, "", f"Timeout after {timeout}s"
        except Exception as e:
            logger.error(f"[{self.name}] Command failed: {e}")
            return -1, "", str(e)
