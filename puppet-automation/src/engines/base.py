"""Engine base classes and shared interfaces."""
from __future__ import annotations

import abc
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger


def _get_allowed_roots() -> list[Path]:
    """获取允许文件操作的根目录列表。"""
    from ..config import settings
    project_root = Path(settings.project_root).resolve()
    roots = [
        Path(settings.output_dir).resolve() if hasattr(settings, "output_dir") else project_root / "output",
        project_root / "data",
        project_root / "temp",
        project_root / "resources",
    ]
    # 二线实战反馈隔离目录：允许引擎实战产物写入（若已配置）
    if hasattr(settings, "feedback_dir"):
        roots.append(Path(settings.feedback_dir).resolve())
    # D 盘资源库与 AE 工程目录（引擎真实写入/读取的工作区）
    if hasattr(settings, "resources_dir"):
        roots.append(Path(settings.resources_dir).resolve())
    if hasattr(settings, "ae_projects_dir"):
        roots.append(Path(settings.ae_projects_dir).resolve())
    return roots


def validate_path_safety(path: Path | str, must_exist: bool = True) -> Path:
    """校验路径在允许的根目录内，防止路径遍历攻击。

    Args:
        path: 用户提供的文件路径
        must_exist: 是否要求路径必须存在

    Returns:
        解析后的绝对路径

    Raises:
        ValueError: 路径不在允许的根目录内
        FileNotFoundError: must_exist=True 且文件不存在
    """
    resolved = Path(path).resolve()
    allowed_roots = _get_allowed_roots()
    if not any(
        resolved == root or resolved.is_relative_to(root)
        for root in allowed_roots
    ):
        raise ValueError(f"路径不在允许的目录范围内: {resolved}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"路径不存在: {resolved}")
    return resolved


@dataclass
class EngineResult:
    """Standard engine execution result."""
    success: bool
    output_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0
    # ====== 新增：可追溯性/类型稳定性 ======
    run_id: str | None = None        # 关联 pipeline.run_id
    trace_id: str | None = None      # 关联追踪ID
    sample_id: str | None = None     # 关联素材/样本ID
    error_code: str | None = None    # 错误码枚举: ENGINE_NOT_AVAILABLE / PARAM_MISSING / TIMEOUT / JSON_PARSE_ERROR 等
    is_error_sample: bool = False       # 异常样本标记（避免污染学习数据）
    available: bool = True              # 引擎是否可用（软件是否安装）


class BaseEngine(abc.ABC):
    """Abstract base class for all engine integrations."""

    name: str = "base"

    def __init__(self, executable_path: Path | str):
        self.executable_path = Path(executable_path)
        self._verify_executable()

    def _verify_executable(self) -> None:
        """Verify engine executable exists. Sets self.available=False if not found."""
        self.available: bool = True
        if not self.executable_path.exists():
            self.available = False
            logger.warning(
                f"[{self.name}] Engine NOT AVAILABLE: executable not found at "
                f"{self.executable_path}. All execute() calls will short-circuit return."
            )
        else:
            logger.debug(f"[{self.name}] Engine available at {self.executable_path}")

    async def execute(self, *args, **kwargs) -> EngineResult:
        """【Final模板方法】子类不要覆盖此方法，实现 _execute_impl()。

        负责：1) available 短路返回  2) 全局异常包裹  3) 时长统计  4) 错误码标准化
        """
        import time as _time
        start_ts = _time.time()

        # 从 kwargs 提取上下文注入（如果有）
        run_id = kwargs.pop("run_id", None)
        trace_id = kwargs.pop("trace_id", None)
        sample_id = kwargs.pop("sample_id", None)

        # Step1: 可用性短路
        if not getattr(self, "available", True):
            dur = _time.time() - start_ts
            return EngineResult(
                success=False,
                available=False,
                error=f"{self.name} engine not available: executable not found at {self.executable_path}",
                error_code=f"{self.name.upper()}_NOT_AVAILABLE",
                duration_seconds=dur,
                run_id=run_id,
                trace_id=trace_id,
                sample_id=sample_id,
                is_error_sample=True,
            )

        # Step2: 调用子类实现 + 全局异常捕获
        try:
            result = await self._execute_impl(*args, **kwargs)
            # 确保返回的是 EngineResult（子类可能返回 dict 或其他）
            if not isinstance(result, EngineResult):
                if isinstance(result, dict):
                    result = EngineResult(**{k: v for k, v in result.items()
                                            if k in EngineResult.__dataclass_fields__})
                else:
                    result = EngineResult(success=True, metadata={"raw_result": str(result)})
            # 注入上下文
            if run_id and not result.run_id:
                result.run_id = run_id
            if trace_id and not result.trace_id:
                result.trace_id = trace_id
            if sample_id and not result.sample_id:
                result.sample_id = sample_id
            result.duration_seconds = _time.time() - start_ts
            return result
        except TypeError as e:
            dur = _time.time() - start_ts
            err_msg = str(e)
            error_code = "PARAM_MISSING" if "required positional argument" in err_msg or "missing" in err_msg else "PARAM_TYPE_INVALID"
            logger.exception(f"[{self.name}] execute failed ({error_code}): {e}")
            return EngineResult(
                success=False,
                error=f"Parameter error: {err_msg}",
                error_code=error_code,
                duration_seconds=dur,
                is_error_sample=True,
                run_id=run_id,
                trace_id=trace_id,
                sample_id=sample_id,
            )
        except Exception as e:
            dur = _time.time() - start_ts
            logger.exception(f"[{self.name}] execute unexpected error: {e}")
            return EngineResult(
                success=False,
                error=f"{self.name} internal error: {type(e).__name__}: {e}",
                error_code="ENGINE_INTERNAL_ERROR",
                duration_seconds=dur,
                is_error_sample=True,
                run_id=run_id,
                trace_id=trace_id,
                sample_id=sample_id,
            )

    @abc.abstractmethod
    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """【子类实现】实际业务逻辑，不需要处理异常/available/时长统计"""
        ...

    def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int = 3600,
        cwd: Path | None = None,
    ) -> tuple[int, str, str, str | None]:
        """Run subprocess with fine-grained error classification.

        Returns: (returncode, stdout, stderr, error_code)
          error_code=None 表示成功或无明确分类
          error_code="SUBPROCESS_TIMEOUT" / "SUBPROCESS_EXECUTABLE_NOT_FOUND" /
                     "SUBPROCESS_PERMISSION_DENIED" / "SUBPROCESS_UNKNOWN_ERROR"
        """
        # 安全日志：仅记录可执行文件名和参数数量，不泄露完整路径和敏感参数
        safe_cmd_name = Path(cmd[0]).name if cmd else "unknown"
        logger.debug(f"[{self.name}] Running: {safe_cmd_name} with {len(cmd) - 1} args")
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
            return proc.returncode, proc.stdout, proc.stderr, None
        except subprocess.TimeoutExpired as e:
            logger.error(f"[{self.name}] Command timed out after {timeout}s: {' '.join(cmd[:3])}...")
            return -1, "", f"Timeout after {timeout}s: {e}", "SUBPROCESS_TIMEOUT"
        except FileNotFoundError as e:
            logger.error(f"[{self.name}] Executable not found: {e}")
            return -1, "", f"Executable not found: {e}", "SUBPROCESS_EXECUTABLE_NOT_FOUND"
        except PermissionError as e:
            logger.error(f"[{self.name}] Permission denied executing command: {e}")
            return -1, "", f"Permission denied: {e}", "SUBPROCESS_PERMISSION_DENIED"
        except Exception as e:
            logger.error(f"[{self.name}] Command failed: {e}")
            return -1, "", str(e), "SUBPROCESS_UNKNOWN_ERROR"
