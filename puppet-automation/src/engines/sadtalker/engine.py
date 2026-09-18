"""SadTalker Engine - Audio-Driven Talking Head Video Generation
================================================================

封装 SadTalker 音频驱动数字人视频生成能力：
- 输入：静态人物图片 + 音频文件
- 输出：口型同步的说话头像视频
- 集成 sitecustomize.py 自动修复 numpy/torchvision/ffmpeg 兼容性问题

使用方式：
    engine = SadTalkerEngine()
    result = await engine.generate(
        source_image="character.png",
        driven_audio="speech.wav",
        output_path="output.mp4",
    )
"""
from __future__ import annotations

import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from loguru import logger

from ...config import settings
from ..base import BaseEngine, EngineResult

# SadTalker 项目根目录与兼容补丁目录
_SADTALKER_ROOT = Path("D:/AE-Work/sadtalker")
_SADTALKER_VENV_PYTHON = _SADTALKER_ROOT / "venv" / "Scripts" / "python.exe"
_SADTALKER_INFERENCE = _SADTALKER_ROOT / "inference.py"
# sitecustomize.py 所在目录（通过 PYTHONPATH 注入兼容补丁）
_PATCH_DIR = Path("c:/Users/Administrator/Desktop/AE-Knowledge-Vault/scripts")


class SadTalkerEngine(BaseEngine):
    """SadTalker audio-driven talking head video generation engine.

    Generates lip-synced talking head videos from a static image and audio.
    Automatically applies compatibility patches for numpy>=1.24, torchvision>=0.18,
    and minimal ffmpeg via sitecustomize.py import hooks.
    """

    name = "sadtalker"

    def __init__(
        self,
        executable_path: Path | str | None = None,
        sadtalker_root: Path | None = None,
    ):
        self.sadtalker_root = Path(sadtalker_root) if sadtalker_root else _SADTALKER_ROOT
        path = Path(executable_path) if executable_path else _SADTALKER_VENV_PYTHON
        self.inference_script = self.sadtalker_root / "inference.py"
        super().__init__(path)
        self._verify_sadtalker_installation()

    def _verify_sadtalker_installation(self) -> None:
        """验证 SadTalker 安装完整性。"""
        if not self.inference_script.exists():
            logger.warning(
                f"SadTalker inference script not found at {self.inference_script}"
            )
        checkpoint_dir = self.sadtalker_root / "checkpoints"
        if not checkpoint_dir.exists():
            logger.warning(
                f"SadTalker checkpoint directory not found at {checkpoint_dir}"
            )

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """Generic execute dispatch."""
        action = kwargs.pop("action", "generate")
        if action == "generate":
            return await self.generate(**kwargs)
        if action == "get_info":
            return EngineResult(success=True, metadata=self.get_info())
        return EngineResult(success=False, error=f"Unknown action: {action}")

    async def generate(
        self,
        source_image: Path | str,
        driven_audio: Path | str,
        output_path: Path | str | None = None,
        result_dir: Path | str | None = None,
        preprocess: str = "crop",
        size: int = 256,
        enhancer: str | None = None,
        still_mode: bool = False,
        pose_style: int = 0,
        expression_scale: float = 1.0,
        batch_size: int = 2,
        timeout: int = 1800,
    ) -> EngineResult:
        """生成音频驱动说话头像视频。

        Args:
            source_image: 源人物图片路径
            driven_audio: 驱动音频路径（wav/mp3）
            output_path: 最终输出视频路径（可选，若指定则复制到此处）
            result_dir: SadTalker 结果目录（可选，默认使用 settings.sadtalker_output_dir）
            preprocess: 预处理模式 crop/full/resize
            size: 输出尺寸（256 或 512）
            enhancer: 面部增强器 None/gfpgan/restoreformer
            still_mode: 静止模式（减少头部运动）
            pose_style: 姿态风格 0-6
            expression_scale: 表情缩放
            batch_size: 推理批大小
            timeout: 超时秒数
        """
        start_time = time.time()

        source_image = Path(source_image)
        driven_audio = Path(driven_audio)

        if not source_image.exists():
            return EngineResult(
                success=False,
                error=f"Source image not found: {source_image}",
            )
        if not driven_audio.exists():
            return EngineResult(
                success=False,
                error=f"Driven audio not found: {driven_audio}",
            )

        # 确定结果目录
        if result_dir is None:
            result_dir = getattr(
                settings, "sadtalker_output_dir", Path("D:/AE-Work/sadtalker/results")
            )
        result_dir = Path(result_dir)
        result_dir.mkdir(parents=True, exist_ok=True)

        # 构建命令
        cmd = [
            str(self.executable_path),
            "-u",
            str(self.inference_script),
            "--source_image", str(source_image),
            "--driven_audio", str(driven_audio),
            "--preprocess", preprocess,
            "--size", str(size),
            "--result_dir", str(result_dir),
            "--batch_size", str(batch_size),
            "--pose_style", str(pose_style),
            "--expression_scale", str(expression_scale),
        ]

        if enhancer:
            cmd.extend(["--enhancer", enhancer])
        if still_mode:
            cmd.append("--still")

        # 设置环境变量（包含 sitecustomize.py 兼容补丁）
        # 注意：必须将 SadTalker 根目录放在 PYTHONPATH 最前面，
        # 否则系统 PYTHONPATH 中的其他 src 目录（如 puppet-automation/src）会覆盖 SadTalker 的 src 包
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{self.sadtalker_root};{_PATCH_DIR}"

        logger.info(
            f"[SadTalker] Generating video: {source_image.name} + {driven_audio.name}"
        )

        # 运行推理
        rc, stdout, stderr = await asyncio.to_thread(
            self._run_subprocess_with_env, cmd, timeout, self.sadtalker_root, env
        )

        duration = time.time() - start_time

        if rc != 0:
            logger.error(f"[SadTalker] Failed with rc={rc}: {stderr[:500]}")
            return EngineResult(
                success=False,
                error=f"SadTalker inference failed: {stderr[:1000]}",
                duration_seconds=duration,
                metadata={"stdout": stdout[:2000], "stderr": stderr[:2000]},
            )

        # 查找生成的视频文件
        video_path = self._find_latest_video(result_dir)
        if video_path is None:
            return EngineResult(
                success=False,
                error="SadTalker completed but no output video found",
                duration_seconds=duration,
                metadata={"stdout": stdout[-2000:], "result_dir": str(result_dir)},
            )

        logger.success(f"[SadTalker] Generated in {duration:.1f}s: {video_path}")

        # 如果指定了 output_path，复制视频到目标位置
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(video_path, output_path)
            video_path = output_path

        return EngineResult(
            success=True,
            output_path=video_path,
            metadata={
                "source_image": str(source_image),
                "driven_audio": str(driven_audio),
                "preprocess": preprocess,
                "size": size,
                "enhancer": enhancer,
                "still_mode": still_mode,
                "pose_style": pose_style,
                "original_result_dir": str(result_dir),
            },
            duration_seconds=duration,
        )

    def _run_subprocess_with_env(
        self,
        cmd: list[str],
        timeout: int = 1800,
        cwd: Path | None = None,
        env: dict | None = None,
    ) -> tuple[int, str, str]:
        """运行子进程并捕获输出（带自定义环境变量）。"""
        import subprocess

        logger.debug(f"[{self.name}] Running: {' '.join(cmd)}")
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
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

    @staticmethod
    def _find_latest_video(result_dir: Path) -> Path | None:
        """在结果目录中查找最新生成的视频文件。

        SadTalker 在 result_dir 下创建时间戳子目录，
        最终视频可能出现在子目录中或 result_dir 根目录下。
        """
        candidates = []
        for f in result_dir.rglob("*.mp4"):
            if f.is_file() and "temp_" not in f.name:
                candidates.append(f)
        if not candidates:
            return None
        return max(candidates, key=lambda f: f.stat().st_mtime)

    def get_info(self) -> dict:
        """返回引擎信息。"""
        return {
            "name": self.name,
            "sadtalker_root": str(self.sadtalker_root),
            "inference_script": str(self.inference_script),
            "python_executable": str(self.executable_path),
            "script_exists": self.inference_script.exists(),
            "checkpoint_dir_exists": (self.sadtalker_root / "checkpoints").exists(),
            "capabilities": ["generate"],
            "supported_preprocess": ["crop", "full", "resize"],
            "supported_enhancers": [None, "gfpgan", "restoreformer"],
        }
