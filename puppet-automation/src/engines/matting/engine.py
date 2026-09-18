r"""
Matting Engine - 图像/视频抠像引擎
====================================

封装 PP-MattingV2 ONNX 推理抠像能力：
- 单图人像抠像（human_matting）：输出 Alpha 遮罩 + 透明 PNG
- 目录批量抠像：遍历目录中所有图片，批量生成 Alpha + 透明 PNG
- 帧序列批处理（batch_frames）：视频帧序列抠像，用于后期抠像流水线

依赖检测：
- onnxruntime (CPU) / onnxruntime-gpu (GPU)
- 模型预下载到本地 D:\AE-Work\models\matting\
- PP-MattingV2 ONNX 模型 (~150MB)

使用方式：
    engine = MattingEngine()
    result = await engine.execute(action="human_matting", input_path="img.png", output_dir="out/")
    result = await engine.execute(action="batch_frames", input_path="frames/", output_dir="masks/")
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from ..base import BaseEngine, EngineResult  # noqa: E402

_DEFAULT_MODEL_DIR = Path(r"D:\AE-Work\models\matting")


class MattingEngine(BaseEngine):
    """Matting (抠像) engine based on PP-MattingV2 ONNX.

    通过 onnxruntime 加载 PP-MattingV2 模型进行人像抠像推理。
    onnxruntime 未安装或模型不存在时诚实降级（_matting=False）。
    """

    name = "matting"

    def __init__(
        self,
        executable_path: Path | str | None = None,
        model_dir: Path | None = None,
    ):
        try:
            from ...config import settings as _settings
            default_model_dir = getattr(_settings, "matting_model_dir", _DEFAULT_MODEL_DIR)
        except Exception:
            default_model_dir = _DEFAULT_MODEL_DIR

        self.model_dir = Path(model_dir) if model_dir else Path(default_model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        venv_py = Path(os.environ.get("AEKV_MATTING_PYTHON", str(executable_path or sys.executable)))
        super().__init__(venv_py)

        self._matting: bool | None = None
        self._onnxruntime = None
        self._model_session = None
        self._check_available()

        self._handlers: dict[str, Callable[..., Any]] = {
            "human_matting": self.human_matting,
            "batch_frames": self.batch_frames,
        }

    def _check_available(self) -> None:
        """检测 onnxruntime 是否可导入、模型目录是否就绪。失败时诚实降级 _matting=False。"""
        self._matting = True

        try:
            import onnxruntime as ort
            self._onnxruntime = ort
            logger.info(f"[{self.name}] onnxruntime loaded (version={getattr(ort, '__version__', 'unknown')})")
        except ImportError:
            self._matting = False
            logger.warning(
                f"[{self.name}] onnxruntime not installed. "
                f"Run: pip install onnxruntime (CPU) or pip install onnxruntime-gpu (GPU)"
            )
            return

        model_report = self._scan_model_dir()
        if not model_report["has_any_model"]:
            logger.warning(
                f"[{self.name}] No ONNX model found in {self.model_dir}. "
                f"Expected PP-MattingV2 .onnx file."
            )

    def _scan_model_dir(self) -> dict[str, Any]:
        """扫描模型目录，返回检测报告。"""
        report: dict[str, Any] = {
            "model_dir": str(self.model_dir),
            "model_dir_exists": self.model_dir.exists(),
            "onnx_files": [],
            "pp_mattingv2_found": False,
            "has_any_model": False,
        }

        if self.model_dir.exists():
            onnx_files = sorted(self.model_dir.glob("*.onnx"))
            report["onnx_files"] = [str(p) for p in onnx_files]
            report["has_any_model"] = len(onnx_files) > 0
            for p in onnx_files:
                if "ppmattingv2" in p.name.lower() or "pp_mattingv2" in p.name.lower() or "matting" in p.name.lower():
                    report["pp_mattingv2_found"] = True
                    report["recommended_model"] = str(p)
                    break

        return report

    async def _execute_impl(self, *args, **kwargs) -> EngineResult:
        """基于 handlers dict + getattr 的 action 路由分发。

        使用 getattr 动态解析方法名，保证 unittest.patch.object 可以正确
        替换 human_matting / batch_frames 实现路由映射校验。
        """
        action = kwargs.get("action", "human_matting")
        if action not in self._handlers:
            available = ", ".join(sorted(self._handlers.keys()))
            return EngineResult(
                success=False,
                error=f"Unknown action '{action}'. Available actions: {available}",
                error_code="MATTING_UNKNOWN_ACTION",
                is_error_sample=True,
            )

        handler = getattr(self, action)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k != "action"}
        return await handler(*args, **filtered_kwargs)

    async def human_matting(
        self,
        input_path: Path | str,
        output_dir: Path | str,
        model_name: str | None = None,
    ) -> EngineResult:
        """人像抠像（单图或目录批量）。

        Args:
            input_path: 输入图片路径或图片目录
            output_dir: 输出目录（生成 alpha 遮罩 + 透明 PNG）
            model_name: 可选的模型文件名（不含目录），默认自动选择 PP-MattingV2

        Returns:
            EngineResult.metadata 中包含:
              processed_count: 处理成功的图片数
              alpha_dir: Alpha 遮罩输出目录
              rgba_dir: 透明 PNG 输出目录
              model_used: 使用的模型路径
        """
        import time

        start = time.time()
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        if not input_path.exists():
            return EngineResult(
                success=False,
                error=f"Input path not found: {input_path}",
                error_code="MATTING_INPUT_NOT_FOUND",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        if self._matting is not True:
            return EngineResult(
                success=False,
                available=False,
                error="onnxruntime not installed. "
                      "Run: pip install onnxruntime (CPU) or pip install onnxruntime-gpu (GPU)",
                error_code="MATTING_NOT_AVAILABLE",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        model_path = self._resolve_model(model_name)
        if model_path is None:
            return EngineResult(
                success=False,
                error=f"No ONNX matting model found in {self.model_dir}. "
                      f"Expected PP-MattingV2 .onnx file.",
                error_code="MATTING_MODEL_NOT_FOUND",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            alpha_dir = output_dir / "alpha"
            rgba_dir = output_dir / "rgba"
            alpha_dir.mkdir(parents=True, exist_ok=True)
            rgba_dir.mkdir(parents=True, exist_ok=True)

            input_files: list[Path] = []
            if input_path.is_dir():
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.webp"):
                    input_files.extend(sorted(input_path.glob(ext)))
            else:
                input_files = [input_path]

            if not input_files:
                return EngineResult(
                    success=False,
                    error=f"No image files found in {input_path}",
                    error_code="MATTING_NO_INPUT_FILES",
                    duration_seconds=time.time() - start,
                    is_error_sample=True,
                )

            processed_count = await asyncio.to_thread(
                self._run_matting_batch,
                input_files,
                alpha_dir,
                rgba_dir,
                model_path,
            )

            duration = time.time() - start

            return EngineResult(
                success=True,
                output_path=output_dir,
                metadata={
                    "processed_count": processed_count,
                    "total_count": len(input_files),
                    "alpha_dir": str(alpha_dir),
                    "rgba_dir": str(rgba_dir),
                    "model_used": str(model_path),
                    "input_path": str(input_path),
                    "mode": "directory" if input_path.is_dir() else "single",
                },
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"human_matting failed: {type(e).__name__}: {str(e)[:500]}",
                error_code="MATTING_INFERENCE_ERROR",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

    async def batch_frames(
        self,
        input_path: Path | str,
        output_dir: Path | str,
        model_name: str | None = None,
    ) -> EngineResult:
        """帧序列批量抠像。

        针对视频帧序列（frame_00001.png 等命名格式）的优化批处理，
        输出与输入帧一一对应的 Alpha 遮罩序列，供后续合成管线使用。

        Args:
            input_path: 帧序列目录（PNG/JPG 序列）
            output_dir: 输出遮罩目录（保持文件名一一对应）
            model_name: 可选的模型文件名
        """
        import time

        start = time.time()
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        if not input_path.exists() or not input_path.is_dir():
            return EngineResult(
                success=False,
                error=f"Frame directory not found: {input_path}",
                error_code="MATTING_INPUT_NOT_FOUND",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        if self._matting is not True:
            return EngineResult(
                success=False,
                available=False,
                error="onnxruntime not installed. "
                      "Run: pip install onnxruntime (CPU) or pip install onnxruntime-gpu (GPU)",
                error_code="MATTING_NOT_AVAILABLE",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        model_path = self._resolve_model(model_name)
        if model_path is None:
            return EngineResult(
                success=False,
                error=f"No ONNX matting model found in {self.model_dir}.",
                error_code="MATTING_MODEL_NOT_FOUND",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

        try:
            output_dir.mkdir(parents=True, exist_ok=True)

            frame_files: list[Path] = []
            for ext in ("*.png", "*.jpg", "*.jpeg"):
                frame_files.extend(sorted(input_path.glob(ext)))

            if not frame_files:
                return EngineResult(
                    success=False,
                    error=f"No frame files found in {input_path}",
                    error_code="MATTING_NO_INPUT_FILES",
                    duration_seconds=time.time() - start,
                    is_error_sample=True,
                )

            processed_count = await asyncio.to_thread(
                self._run_frames_batch,
                frame_files,
                output_dir,
                model_path,
            )

            duration = time.time() - start

            return EngineResult(
                success=True,
                output_path=output_dir,
                metadata={
                    "processed_count": processed_count,
                    "total_count": len(frame_files),
                    "model_used": str(model_path),
                    "frame_dir": str(input_path),
                    "naming_convention": "preserve_source_filename",
                },
                duration_seconds=duration,
            )

        except Exception as e:
            return EngineResult(
                success=False,
                error=f"batch_frames failed: {type(e).__name__}: {str(e)[:500]}",
                error_code="MATTING_INFERENCE_ERROR",
                duration_seconds=time.time() - start,
                is_error_sample=True,
            )

    def _resolve_model(self, model_name: str | None = None) -> Path | None:
        """解析模型文件路径。

        优先级：
        1. _model_index 命中（key 匹配，或 stem 匹配、完整路径匹配）
        2. model_name 参数指定的文件名（在 model_dir 中查找）
        3. 目录中包含 ppmattingv2 / pp_mattingv2 / matting 的 .onnx
        4. 目录中任意 .onnx 文件
        """
        idx = getattr(self, "_model_index", None) or {}

        if model_name:
            # 先精确查 key
            if model_name in idx:
                p = idx[model_name]
                if p and Path(p).exists():
                    return Path(p)
            # 再查 "name 匹配 Path.stem"
            for k, v in idx.items():
                if not v:
                    continue
                vp = Path(v)
                if vp.stem == model_name or vp.name == model_name or str(vp) == model_name:
                    if vp.exists():
                        return vp
            # 最后查 model_dir
            candidate = self.model_dir / model_name
            if candidate.exists():
                return candidate
            # 补 .onnx 后缀再试一次
            if not model_name.lower().endswith(".onnx"):
                candidate2 = self.model_dir / f"{model_name}.onnx"
                if candidate2.exists():
                    return candidate2

        report = self._scan_model_dir()
        if not report["has_any_model"]:
            # 目录扫描为空时，fallback 到 _model_index 第一个有效条目
            for v in idx.values():
                if v and Path(v).exists():
                    return Path(v)
            return None

        if report.get("recommended_model"):
            return Path(report["recommended_model"])

        if report["onnx_files"]:
            return Path(report["onnx_files"][0])

        for v in idx.values():
            if v and Path(v).exists():
                return Path(v)
        return None

    def _run_matting_batch(
        self,
        input_files: list[Path],
        alpha_dir: Path,
        rgba_dir: Path,
        model_path: Path,
    ) -> int:
        """运行单图/目录抠像（同步，在线程中执行）。"""
        return self._run_onnx_matting_impl(input_files, alpha_dir, rgba_dir, model_path)

    def _run_frames_batch(
        self,
        frame_files: list[Path],
        output_dir: Path,
        model_path: Path,
    ) -> int:
        """运行帧序列抠像（同步，在线程中执行）。"""
        return self._run_onnx_matting_impl(frame_files, output_dir, None, model_path)

    def _run_onnx_matting_impl(
        self,
        input_files: list[Path],
        alpha_output_dir: Path,
        rgba_output_dir: Path | None,
        model_path: Path,
    ) -> int:
        """实际 ONNX 推理实现（无 onnxruntime 时不执行到此处）。

        不生成假数据：onnxruntime 缺失时 _matting=False，上层已短路返回。
        这里仅为真实推理逻辑的骨架，在环境就绪时可直接填充完整实现。
        """
        if self._onnxruntime is None:
            raise RuntimeError("onnxruntime not available")

        logger.info(
            f"[{self.name}] Processing {len(input_files)} images "
            f"with model {model_path.name}"
        )

        ort = self._onnxruntime

        providers = ["CPUExecutionProvider"]
        try:
            if "CUDAExecutionProvider" in ort.get_available_providers():
                providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass

        session = ort.InferenceSession(str(model_path), providers=providers)

        try:
            import numpy as np
        except ImportError:
            raise RuntimeError("numpy is required for matting inference")

        processed = 0

        for src_file in input_files:
            try:
                img = self._imread_unicode(src_file)
                if img is None:
                    continue

                h, w = img.shape[:2]

                input_tensor, pp_params = self._preprocess(img, session)
                input_name = session.get_inputs()[0].name
                outputs = session.run(None, {input_name: input_tensor})

                alpha = self._postprocess(outputs, (h, w), pp_params)

                alpha_out = alpha_output_dir / f"{src_file.stem}.png"
                self._imwrite_unicode(alpha_out, (alpha * 255).astype(np.uint8))

                if rgba_output_dir is not None:
                    if len(img.shape) == 2:
                        img_rgb = np.stack([img] * 3, axis=-1)
                    else:
                        img_rgb = img[:, :, ::-1] if img.shape[2] == 3 else img[:, :, :3]
                    rgba = np.concatenate([img_rgb, (alpha * 255).astype(np.uint8)[:, :, None]], axis=-1)
                    rgba_out = rgba_output_dir / f"{src_file.stem}.png"
                    self._imwrite_unicode(rgba_out, rgba)

                processed += 1

            except Exception as e:
                logger.warning(f"[{self.name}] Failed to process {src_file.name}: {e}")
                import traceback
                logger.debug(f"[{self.name}] Traceback:\n{traceback.format_exc()}")
                continue

        logger.info(f"[{self.name}] Matting complete: {processed}/{len(input_files)} images")
        return processed

    @staticmethod
    def _preprocess(img: Any, session: Any) -> tuple[Any, dict]:
        """通用 ONNX 人像抠像预处理。

        自动适配以下模型家族：
        - MODNet / U2Net / PP-Matting：动态尺寸，RGB→BGR，(x/255 - 0.5)/0.5
        - RMBG-1.4 / BiRefNet：固定 1024×1024，RGB，x/255（不做零中心）

        返回：(tensor, pp_params)；pp_params 用于后处理时反向还原 pad/scale。
        """
        import numpy as np

        input_meta = session.get_inputs()[0]
        input_shape = input_meta.shape
        if len(input_shape) == 4:
            target_h = input_shape[2]
            target_w = input_shape[3]
        else:
            target_h = target_w = 512

        dyn_size = isinstance(target_h, str) or target_h is None or isinstance(target_w, str) or target_w is None

        # === 策略探测 ===
        # 固定 1024×1024 且不动态 => 高概率 RMBG/BiRefNet 家族：RGB, x/255, no zero-center
        # 动态尺寸 => MODNet 家族：BGR, zero-center
        model_family = "modern" if (not dyn_size and target_h == target_w and target_h >= 768) else "classic"

        if dyn_size:
            # MODNet 推荐 512 长边以保证 CPU 速度
            MAX = 1024
            h0, w0 = img.shape[:2]
            mx = max(h0, w0)
            if mx > MAX:
                s = MAX / mx
                target_h, target_w = int(h0 * s), int(w0 * s)
            else:
                target_h, target_w = h0, w0
            # 保证能被 32 整除（CNN 下采样友好）
            target_h = (target_h // 32) * 32 or 32
            target_w = (target_w // 32) * 32 or 32

        h, w = img.shape[:2]
        if len(img.shape) == 2:
            img = np.stack([img] * 3, axis=-1)
        elif img.shape[2] == 4:
            img = img[:, :, :3]

        if model_family == "classic":
            # BGR + zero-center
            img = img[:, :, ::-1]
            x = img.astype(np.float32) / 255.0
        else:
            # modern：RGB + [0,1] 线性归一化（不做零中心）
            x = img.astype(np.float32)[:, :, ::-1] / 255.0 if False else img.astype(np.float32) / 255.0

        scale = min(target_h / h, target_w / w)
        new_h, new_w = int(round(h * scale)), int(round(w * scale))
        new_h = max(1, new_h); new_w = max(1, new_w)

        try:
            import cv2
            resized = cv2.resize(x, (new_w, new_h), interpolation=cv2.INTER_AREA if (new_w < w or new_h < h) else cv2.INTER_LINEAR)
        except Exception:
            resized = x[:new_h, :new_w]

        pad_h = target_h - new_h
        pad_w = target_w - new_w
        padded = np.pad(resized, ((0, pad_h), (0, pad_w), (0, 0)), mode="constant")

        if model_family == "classic":
            mean = np.array([0.5, 0.5, 0.5], dtype=np.float32)
            std = np.array([0.5, 0.5, 0.5], dtype=np.float32)
            padded = (padded - mean) / std

        tensor = padded.transpose(2, 0, 1)[None, ...].astype(np.float32)

        pp_params = {
            "scale": scale,
            "new_h": new_h,
            "new_w": new_w,
            "pad_h": pad_h,
            "pad_w": pad_w,
            "target_h": target_h,
            "target_w": target_w,
            "family": model_family,
        }
        return tensor, pp_params

    @staticmethod
    def _postprocess(outputs: Any, original_size: tuple[int, int], pp_params: dict | None = None) -> Any:
        """通用 ONNX 人像抠像后处理。

        兼容：NCHW / NHWC / 输出 >1 通道（取第一通道作为 alpha）。
        同时反向还原预处理中做的 resize + letterbox pad，避免字母条被拉伸回原图。
        """
        import numpy as np

        alpha = outputs[0]

        # 从 4D 提取 2D alpha map
        if alpha.ndim == 4:
            # 探测 NHWC vs NCHW：哪一维度是 1 或较小
            B = alpha.shape[0]
            # NCHW: [B,1,H,W] ; NHWC: [B,H,W,1]
            if alpha.shape[1] in (1, 2, 3, 4) and alpha.shape[-1] > alpha.shape[1]:
                # 疑似 NCHW
                alpha = alpha[0, 0]
            elif alpha.shape[-1] in (1, 2, 3, 4) and alpha.shape[1] > alpha.shape[-1]:
                # 疑似 NHWC
                alpha = alpha[0, ..., 0]
            else:
                # fallback：取第一组第一通道
                alpha = alpha[0, 0] if alpha.shape[1] == 1 else alpha[0, ..., 0]
        elif alpha.ndim == 3:
            alpha = alpha[0]

        alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)

        h, w = original_size
        if pp_params is not None:
            th, tw = pp_params["target_h"], pp_params["target_w"]
            ph, pw = pp_params["pad_h"], pp_params["pad_w"]
            nh, nw = pp_params["new_h"], pp_params["new_w"]
            try:
                import cv2
                # 若模型输出和预处理后的输入尺寸不同（常见：动态 downsample），先缩回到 padded 尺寸
                if alpha.shape != (th, tw):
                    alpha = cv2.resize(alpha, (tw, th), interpolation=cv2.INTER_LINEAR)
                # 去掉 letterbox padding
                if ph > 0 or pw > 0:
                    crop_h = th - ph
                    crop_w = tw - pw
                    if crop_h > 0 and crop_w > 0:
                        alpha = alpha[:crop_h, :crop_w]
                # 最后还原到原图尺寸
                alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
            except Exception:
                try:
                    import cv2
                    alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
                except Exception:
                    pass
        else:
            try:
                import cv2
                alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
            except Exception:
                pass

        return alpha

    @staticmethod
    def _imread_unicode(path: Path) -> Any:
        """支持中文路径的图像读取。"""
        try:
            import cv2
            import numpy as np
            data = np.fromfile(str(path), dtype=np.uint8)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            return None

    @staticmethod
    def _imwrite_unicode(path: Path, img: Any) -> bool:
        """支持中文路径的图像写入。"""
        try:
            import cv2
            ext = path.suffix or ".png"
            ok, buf = cv2.imencode(ext, img)
            if ok:
                buf.tofile(str(path))
                return True
        except Exception:
            pass
        return False

    def get_info(self) -> dict[str, Any]:
        """返回引擎信息与模型检测报告。"""
        model_report = self._scan_model_dir()
        return {
            "name": self.name,
            "available": self._matting is True,
            "onnxruntime_loaded": self._onnxruntime is not None,
            "onnxruntime_version": getattr(self._onnxruntime, "__version__", None) if self._onnxruntime else None,
            "model_dir": str(self.model_dir),
            "model_dir_exists": self.model_dir.exists(),
            "model_report": model_report,
            "actions": sorted(self._handlers.keys()),
            "install_command": (
                "pip install onnxruntime opencv-python numpy  (CPU)\n"
                "Or:  pip install onnxruntime-gpu opencv-python numpy  (GPU/CUDA)"
            ),
            "model_download_hint": (
                "Download PP-MattingV2 ONNX model from PaddleOCR/PaddleSeg model zoo "
                f"and place .onnx file in {self.model_dir}"
            ),
        }
