"""
AI Scene Detector — 镜头分割引擎
=================================
基于 TransNetV2 (https://github.com/soCzech/TransNetV2) 开源项目，支持
真实预训练权重加载与推理。AI(TransNetV2) 路径为实验性能力，默认关闭；
仅在 ``enable_ai=True`` 且能加载到真实权重时启用，否则诚实降级到可靠的
PySceneDetect 传统方法（scene_detector），绝不返回随机权重产生的噪声
结果冒充 'AI 检测'。

权重加载策略（按优先级）：
    1. ``transnetv2`` pip 包（推荐）：``pip install transnetv2``，直接
       使用 ``predict_images`` 接口
    2. ONNX Runtime：``pip install onnxruntime-gpu`` + 用户提供 ``.onnx``
       模型文件（项目 requirements 已声明 onnxruntime-gpu）
    3. PyTorch：``pip install torch`` + 用户克隆官方仓库到
       ``external/TransNetV2/``（项目 requirements 已声明 torch）
    4. 上述均不可用 → 诚实降级 + 详细安装指引日志

权重缓存路径优先级：
    1. ``AEKV_TRANSNETV2_WEIGHTS`` 环境变量指定的权重文件
    2. ``D:/AE-Work/models/transnetv2/transnetv2_weights.pth``
    3. ``~/.cache/transnetv2/transnetv2_weights.pth``
    4. ``<project_root>/models/transnetv2_weights.pth``

下载支持断点续传，不重复下载。本机 RTX 4060 8GB VRAM 时启用 half
precision 并在推理后释放模型显存。

核心能力:
- 镜头分割：默认使用 PySceneDetect 传统方法（真实可用）
- 渐变转场检测 (淡入淡出/溶解)
- TransNetV2 AI 路径（实验性，需 enable_ai=True 且真实权重可用）
- 视频元场景分析 (场景类型分类)
- 批量视频处理

依赖:
    pip install numpy opencv-python scenedetect
    # TransNetV2 真实推理（任选其一）：
    #   pip install transnetv2              # 官方 pip 包（推荐）
    #   pip install onnxruntime-gpu         # ONNX Runtime
    #   pip install torch                   # PyTorch + external/TransNetV2 仓库
    # 权重可选：AEKV_TRANSNETV2_WEIGHTS 指向真实 .pth/.onnx 文件

用法:
    detector = AISceneDetector()
    shots = detector.detect("input.mp4")
    # shots = [Shot(start=0.0, end=3.5, type='CUT'), ...]
"""

from __future__ import annotations

import json
import math
import os
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import warnings

try:
    from loguru import logger
except ImportError:  # pragma: no cover - loguru 在项目 requirements 中
    import logging
    logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=FutureWarning)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.torch_runtime import get_device, infer_ctx


# ================================================================
#  数据结构
# ================================================================
class ShotType(Enum):
    CUT = "cut"             # 硬切
    DISSOLVE = "dissolve"   # 溶解转场
    FADE_IN = "fade_in"     # 淡入
    FADE_OUT = "fade_out"   # 淡出
    WIPE = "wipe"           # 擦除转场


@dataclass
class Shot:
    """镜头信息"""
    index: int
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    duration: float
    shot_type: ShotType = ShotType.CUT
    confidence: float = 0.0
    thumbnail_frame: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "index": self.index,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "shot_type": self.shot_type.value,
            "confidence": self.confidence,
            "thumbnail_frame": self.thumbnail_frame,
            "metadata": self.metadata,
        }


@dataclass
class ShotTransition:
    """镜头过渡"""
    frame: int
    time: float
    type: ShotType
    confidence: float


# ================================================================
#  TransNetV2 引擎
# ================================================================
class AISceneDetector:
    """镜头分割器。

    默认使用可靠的 PySceneDetect 传统方法。AI(TransNetV2) 路径为实验性
    能力，默认关闭；仅在 enable_ai=True 且能加载到真实权重时启用，
    否则诚实降级并标记原因，绝不返回随机权重噪声。

    真实权重加载支持三种后端（按优先级）：
        1. ``transnetv2`` pip 包（推荐，开箱即用）
        2. ONNX Runtime + ``.onnx`` 模型文件
        3. PyTorch + ``external/TransNetV2/`` 官方架构代码
    三者均不可用时保留降级 fallback，并输出详细安装指引日志。
    """

    # TransNetV2 模型权重 URL（官方发布）
    TRANS_NET_V2_WEIGHTS_URL = "https://github.com/soCzech/TransNetV2/releases/download/v1.0/transnetv2_weights.pth"

    # 权重缓存目录候选（按优先级）
    _CACHE_DIR_CANDIDATES = (
        Path("D:/AE-Work/models/transnetv2"),
        Path.home() / ".cache" / "transnetv2",
    )

    def __init__(
        self,
        use_transnet_v2: bool = False,
        enable_ai: bool = False,
        confidence_threshold: float = 0.3,
        min_shot_length: int = 15,      # 最小镜头帧数
        detect_gradual: bool = True,     # 检测渐变转场
        fps: float = 30.0,
        auto_download: bool = False,     # 自动下载权重（默认关闭，避免无网络时阻塞）
    ):
        self.enable_ai = bool(enable_ai or use_transnet_v2)
        self.confidence_threshold = confidence_threshold
        self.min_shot_length = min_shot_length
        self.detect_gradual = detect_gradual
        self.fps = fps
        self.auto_download = bool(auto_download)
        self._model = None
        self._degraded_reason: Optional[str] = None
        self._backend: Optional[str] = None  # transnetv2_pkg / onnxruntime / torch
        self._transnet_available = self._check_transnet()
        self._load_transnet_model()

    # ----------------------------------------------------------------
    #  权重路径解析与下载
    # ----------------------------------------------------------------
    @staticmethod
    def _find_weights_path() -> Optional[Path]:
        """查找本地真实 TransNetV2 权重文件。

        支持的环境变量与缓存路径（按优先级）：
            1. ``AEKV_TRANSNETV2_WEIGHTS`` 指向的 .pth / .onnx 文件
            2. ``D:/AE-Work/models/transnetv2/transnetv2_weights.pth``
            3. ``~/.cache/transnetv2/transnetv2_weights.pth``
            4. ``<project_root>/models/transnetv2_weights.pth``
            5. 上述目录下的任意 ``.onnx`` 文件（ONNX 后端）
        """
        override = os.environ.get("AEKV_TRANSNETV2_WEIGHTS")
        if override:
            p = Path(override)
            if p.exists():
                return p
        candidates = [
            Path("D:/AE-Work/models/transnetv2/transnetv2_weights.pth"),
            Path.home() / ".cache" / "transnetv2" / "transnetv2_weights.pth",
            Path(__file__).parent.parent / "models" / "transnetv2_weights.pth",
        ]
        for p in candidates:
            if p.exists():
                return p
        # ONNX 模型文件
        for d in (
            Path("D:/AE-Work/models/transnetv2"),
            Path.home() / ".cache" / "transnetv2",
            Path(__file__).parent.parent / "models",
        ):
            if d.exists():
                onnx_files = list(d.glob("*.onnx"))
                if onnx_files:
                    return onnx_files[0]
        return None

    @staticmethod
    def _get_cache_dir() -> Optional[Path]:
        """返回可写的权重缓存目录，找不到返回 None。"""
        for d in AISceneDetector._CACHE_DIR_CANDIDATES:
            try:
                d.mkdir(parents=True, exist_ok=True)
                # 可写性测试
                (d / ".write_test").touch()
                (d / ".write_test").unlink()
                return d
            except (OSError, PermissionError):
                continue
        return None

    def _try_download_weights(self) -> Optional[Path]:
        """下载 TransNetV2 权重到本地缓存（支持断点续传）。

        仅在 ``enable_ai=True`` 时调用。下载失败返回 None，由上层降级。
        """
        cache_dir = self._get_cache_dir()
        if cache_dir is None:
            logger.warning("[AISceneDetector] 无可写缓存目录，跳过权重下载")
            return None

        cache_path = cache_dir / "transnetv2_weights.pth"
        if cache_path.exists():
            return cache_path

        tmp_path = cache_path.with_suffix(".pth.part")
        try:
            existing_size = tmp_path.stat().st_size if tmp_path.exists() else 0
            req = urllib.request.Request(self.TRANS_NET_V2_WEIGHTS_URL)
            if existing_size > 0:
                req.add_header("Range", f"bytes={existing_size}-")
                logger.info(
                    f"[AISceneDetector] 断点续传 TransNetV2 权重: 已有 {existing_size} bytes"
                )
            else:
                logger.info("[AISceneDetector] 开始下载 TransNetV2 权重...")

            with urllib.request.urlopen(req, timeout=120) as resp:
                total = int(resp.headers.get("Content-Length", 0)) + existing_size
                mode = "ab" if existing_size > 0 and resp.status == 206 else "wb"
                if mode == "wb":
                    existing_size = 0
                with open(tmp_path, mode) as f:
                    downloaded = existing_size
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and downloaded % (1024 * 1024) < 64 * 1024:
                            logger.debug(
                                f"[AISceneDetector] 下载进度: {downloaded}/{total} "
                                f"({100 * downloaded // total}%)"
                            )
            tmp_path.rename(cache_path)
            logger.info(f"[AISceneDetector] TransNetV2 权重下载完成: {cache_path}")
            return cache_path
        except Exception as e:
            logger.warning(
                f"[AISceneDetector] 权重下载失败: {type(e).__name__}: {e}"
            )
            return None

    # ----------------------------------------------------------------
    #  后端检测
    # ----------------------------------------------------------------
    @staticmethod
    def _detect_available_backend() -> Optional[str]:
        """检测可用的 TransNetV2 推理后端。

        返回:
            ``"transnetv2_pkg"`` / ``"onnxruntime"`` / ``"torch"`` / ``None``
        """
        # 优先级1：transnetv2 pip 包（开箱即用）
        try:
            import transnetv2  # noqa: F401
            return "transnetv2_pkg"
        except ImportError:
            pass
        # 优先级2：ONNX Runtime（项目 requirements 已声明 onnxruntime-gpu）
        try:
            import onnxruntime  # noqa: F401
            return "onnxruntime"
        except ImportError:
            pass
        # 优先级3：PyTorch（项目 requirements 已声明 torch==2.3.1）
        try:
            import torch  # noqa: F401
            return "torch"
        except ImportError:
            pass
        return None

    def _check_transnet(self) -> bool:
        """检测任意可用的 TransNetV2 推理后端，写入 ``self._backend``。"""
        self._backend = self._detect_available_backend()
        return self._backend is not None

    @staticmethod
    def _find_transnet_architecture() -> Optional[Path]:
        """查找 TransNetV2 官方架构代码（transnetv2.py）。

        不从零复制架构，仅引用用户克隆的官方仓库。
        """
        candidates = [
            Path(__file__).parent.parent / "external" / "TransNetV2" / "transnetv2.py",
            Path(__file__).parent.parent / "external" / "TransNetV2" / "TransNetV2.py",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    @staticmethod
    def _log_install_guide(reason: str) -> None:
        """输出详细安装指引日志，帮助用户启用真实 AI 推理。"""
        logger.warning(
            f"[AISceneDetector] TransNetV2 真实推理不可用 (原因: {reason})。\n"
            "启用 AI 镜头检测的任一方式：\n"
            "  1. pip install transnetv2              # 官方 pip 包（推荐）\n"
            "  2. pip install onnxruntime-gpu          # ONNX Runtime + .onnx 模型文件\n"
            "  3. pip install torch                    # PyTorch\n"
            "     git clone https://github.com/soCzech/TransNetV2 external/TransNetV2\n"
            "权重下载：设置 enable_ai=True 后会自动下载到 D:/AE-Work/models/transnetv2/\n"
            "或手动下载并设置环境变量 AEKV_TRANSNETV2_WEIGHTS=/path/to/transnetv2_weights.pth"
        )

    # ----------------------------------------------------------------
    #  模型加载
    # ----------------------------------------------------------------
    def _load_transnet_model(self):
        """加载真实 TransNetV2 权重并构建推理后端。

        按后端优先级加载：
            - ``transnetv2_pkg``：直接使用 ``predict_images`` 接口
            - ``onnxruntime``：加载 ``.onnx`` 文件为 InferenceSession
            - ``torch``：需要 ``external/TransNetV2/`` 架构代码，加载 .pth state_dict
        任一后端加载成功则 ``self._model`` 非 None 且 ``_degraded_reason=None``；
        否则记录降级原因并保留 fallback。
        """
        if self._model is not None:
            return self._model

        if not self._transnet_available:
            self._degraded_reason = "transnetv2_backend_unavailable"
            self._log_install_guide("无可用推理后端（transnetv2/onnxruntime/torch 均未安装）")
            return None

        weights_path = self._find_weights_path()
        if weights_path is None:
            # 仅在 enable_ai=True 时尝试下载
            if self.enable_ai:
                weights_path = self._try_download_weights()
            if weights_path is None:
                self._degraded_reason = "transnetv2_weights_not_found"
                self._transnet_available = False
                if self.enable_ai:
                    self._log_install_guide("权重文件未找到且下载失败")
                return None

        # 按后端加载
        if self._backend == "transnetv2_pkg":
            return self._load_with_transnetv2_pkg(weights_path)
        if self._backend == "onnxruntime":
            return self._load_with_onnxruntime(weights_path)
        if self._backend == "torch":
            return self._load_with_torch(weights_path)
        # 不应到达此处
        self._degraded_reason = "transnetv2_unknown_backend"
        self._transnet_available = False
        return None

    def _load_with_transnetv2_pkg(self, weights_path: Path):
        """使用 transnetv2 pip 包加载。"""
        try:
            from transnetv2 import predict_images  # noqa: F401
            self._model = {
                "backend": "transnetv2_pkg",
                "predict_fn": predict_images,
                "weights_path": str(weights_path),
            }
            self._degraded_reason = None
            logger.info("[AISceneDetector] TransNetV2 后端就绪: transnetv2 pip 包")
            return self._model
        except Exception as e:
            self._degraded_reason = f"transnetv2_pkg_load_failed: {type(e).__name__}"
            self._transnet_available = False
            logger.warning(f"[AISceneDetector] transnetv2 包加载失败: {e}")
            return None

    def _load_with_onnxruntime(self, weights_path: Path):
        """使用 ONNX Runtime 加载。需要 .onnx 文件（.pth 不支持自动转换）。"""
        if weights_path.suffix.lower() != ".onnx":
            # 查找同目录下的 .onnx 文件
            onnx_files = list(weights_path.parent.glob("*.onnx"))
            if not onnx_files:
                self._degraded_reason = "transnetv2_onnx_model_unavailable"
                self._transnet_available = False
                self._log_install_guide(
                    "检测到 onnxruntime 后端但缺少 .onnx 模型文件（.pth→.onnx 转换需要官方架构代码）"
                )
                return None
            weights_path = onnx_files[0]
        try:
            import onnxruntime as ort
            # 优先使用 GPU（RTX 4060），失败回退 CPU
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            session = ort.InferenceSession(str(weights_path), providers=providers)
            self._model = {
                "backend": "onnxruntime",
                "session": session,
                "weights_path": str(weights_path),
            }
            self._degraded_reason = None
            logger.info(
                f"[AISceneDetector] TransNetV2 后端就绪: ONNX Runtime "
                f"({session.get_providers()})"
            )
            return self._model
        except Exception as e:
            self._degraded_reason = f"transnetv2_onnx_load_failed: {type(e).__name__}"
            self._transnet_available = False
            logger.warning(f"[AISceneDetector] ONNX Runtime 加载失败: {e}")
            return None

    def _load_with_torch(self, weights_path: Path):
        """使用 PyTorch 加载。需要 external/TransNetV2/ 官方架构代码。"""
        if weights_path.suffix.lower() != ".pth":
            self._degraded_reason = "transnetv2_torch_weights_not_pth"
            self._transnet_available = False
            return None
        arch_path = self._find_transnet_architecture()
        if arch_path is None:
            self._degraded_reason = "transnetv2_architecture_not_available"
            self._transnet_available = False
            self._log_install_guide(
                "检测到 PyTorch 后端和 .pth 权重，但缺少 TransNetV2 官方架构代码\n"
                "    请执行: git clone https://github.com/soCzech/TransNetV2 external/TransNetV2"
            )
            return None
        try:
            import torch
            if str(arch_path.parent) not in sys.path:
                sys.path.insert(0, str(arch_path.parent))
            # 动态导入官方架构（不复制代码）
            import importlib
            spec = importlib.util.spec_from_file_location("transnetv2_arch", str(arch_path))
            arch_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(arch_module)
            # 官方仓库中类名为 TransNetV2
            ModelClass = getattr(arch_module, "TransNetV2", None)
            if ModelClass is None:
                self._degraded_reason = "transnetv2_arch_class_not_found"
                self._transnet_available = False
                return None
            model = ModelClass()
            state_dict = torch.load(str(weights_path), map_location="cpu")
            model.load_state_dict(state_dict)
            model.eval()
            device = get_device()
            if device == "cuda":
                # RTX 4060 8GB VRAM：使用 half precision 节省显存
                model = model.to(device).half()
            else:
                model = model.to(device)
            self._model = {
                "backend": "torch",
                "model": model,
                "device": device,
                "weights_path": str(weights_path),
            }
            self._degraded_reason = None
            logger.info(
                f"[AISceneDetector] TransNetV2 后端就绪: PyTorch ({device}, "
                f"half={device == 'cuda'})"
            )
            return self._model
        except Exception as e:
            self._degraded_reason = f"transnetv2_torch_load_failed: {type(e).__name__}"
            self._transnet_available = False
            logger.warning(f"[AISceneDetector] PyTorch 加载失败: {e}")
            return None

    def release_model(self) -> None:
        """释放模型显存（推理完成后调用，避免 8GB VRAM 占用）。"""
        if self._model is None:
            return
        backend = self._model.get("backend")
        try:
            if backend == "torch":
                import torch
                model = self._model.get("model")
                if model is not None:
                    del model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            elif backend == "onnxruntime":
                session = self._model.get("session")
                if session is not None:
                    del session
        except Exception:
            pass
        self._model = None
        self._transnet_available = False
        self._degraded_reason = "transnetv2_model_released"
        logger.debug("[AISceneDetector] 模型已释放")

    def _extract_transnet_features(self, frames: list) -> Any:
        """从帧序列提取 TransNetV2 特征"""
        import numpy as np
        import cv2

        if len(frames) < 16:
            return None

        # 调整为 48x27 的输入
        features = []
        for frame in frames:
            resized = cv2.resize(frame, (48, 27))
            features.append(resized)

        # 组织为 batch
        batch = np.array(features, dtype=np.float32) / 255.0
        return np.expand_dims(batch, axis=0)  # [1, N, 27, 48, 3]

    def detect(self, video_path: str) -> List[Shot]:
        """
        检测视频中的所有镜头。

        AI(TransNetV2) 为实验性能力，默认关闭。仅当 enable_ai=True 且
        加载到真实权重时才走 AI 路径；否则回退到可靠的 scene_detector，
        并在 metadata 中标记降级原因，绝不返回随机权重噪声。

        Args:
            video_path: 视频文件路径

        Returns:
            镜头列表
        """
        if self.enable_ai and self._transnet_available and self._model is not None:
            return self._detect_transnet(video_path)
        shots = self._detect_fallback(video_path)
        if self.enable_ai:
            for shot in shots:
                shot.metadata["ai"] = False
                shot.metadata["degraded"] = self._degraded_reason or "transnetv2_unavailable"
        return shots

    def _detect_transnet(self, video_path: str) -> List[Shot]:
        """TransNetV2 深度学习检测（基于真实权重和后端推理）。

        根据 ``self._backend`` 分发到不同推理路径：
            - ``transnetv2_pkg``：调用 ``predict_images`` 一次性推理
            - ``onnxruntime`` / ``torch``：分批读取帧 + 滑动窗口推理
        """
        import cv2
        import numpy as np

        if self._model is None:
            return self._detect_fallback(video_path)

        backend = self._model.get("backend")

        # transnetv2 pip 包后端：直接调用 predict_images
        if backend == "transnetv2_pkg":
            return self._detect_with_transnetv2_pkg(video_path)

        # ONNX / PyTorch 后端：分批读取帧 + 滑动窗口推理
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return self._detect_fallback(video_path)

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS) or self.fps

        window_size = 100  # TransNetV2 推荐窗口大小
        all_predictions = []
        frame_idx = 0
        frames_buffer = []

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 降采样 (TransNetV2 原生使用 48x27)
                small = cv2.resize(frame, (48, 27))
                frames_buffer.append(small)

                if len(frames_buffer) >= window_size:
                    preds = self._infer_batch(frames_buffer[-window_size:], backend)
                    all_predictions.extend(preds)
                    # 保留 16 帧重叠，保证转场点连续性
                    frames_buffer = frames_buffer[window_size - 16:]

                frame_idx += 1
                if frame_idx % 500 == 0 and total_frames > 0:
                    logger.debug(
                        f"[AISceneDetector] Processing... {frame_idx}/{total_frames}"
                    )

            # 处理剩余帧
            if frames_buffer:
                preds = self._infer_batch(frames_buffer, backend)
                all_predictions.extend(preds)
        finally:
            cap.release()

        shots = self._predictions_to_shots(all_predictions, actual_fps)
        return shots

    def _infer_batch(self, frames: list, backend: str) -> List[float]:
        """对一批帧进行 TransNetV2 推理，返回每帧的转场概率。

        Args:
            frames: list of (27, 48, 3) BGR uint8 帧
            backend: ``"onnxruntime"`` 或 ``"torch"``
        """
        import numpy as np

        if not frames:
            return []

        batch = np.array(frames, dtype=np.float32) / 255.0
        batch = np.expand_dims(batch, axis=0)  # [1, N, 27, 48, 3]

        try:
            if backend == "onnxruntime":
                session = self._model["session"]
                input_name = session.get_inputs()[0].name
                outputs = session.run(None, {input_name: batch})
                # TransNetV2 输出: (predictions, transitions) 或仅 predictions
                if isinstance(outputs, (list, tuple)) and len(outputs) >= 1:
                    preds = np.asarray(outputs[0]).flatten().tolist()
                else:
                    preds = np.asarray(outputs).flatten().tolist()
            elif backend == "torch":
                import torch
                model = self._model["model"]
                device = self._model["device"]
                with infer_ctx(device):
                    t = torch.from_numpy(batch).to(device)
                    if device == "cuda":
                        t = t.half()
                    outputs = model(t)
                    if isinstance(outputs, (tuple, list)):
                        preds = outputs[0].cpu().float().numpy().flatten().tolist()
                    else:
                        preds = outputs.cpu().float().numpy().flatten().tolist()
            else:
                preds = [0.0] * len(frames)
        except Exception as e:
            logger.warning(f"[AISceneDetector] 推理失败 (batch={len(frames)}): {e}")
            preds = [0.0] * len(frames)

        return preds

    def _detect_with_transnetv2_pkg(self, video_path: str) -> List[Shot]:
        """使用 transnetv2 pip 包的 predict_images 接口进行检测。"""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return self._detect_fallback(video_path)

        actual_fps = cap.get(cv2.CAP_PROP_FPS) or self.fps
        frames = []
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(cv2.resize(frame, (48, 27)))
        finally:
            cap.release()

        if not frames:
            return []

        predict_fn = self._model["predict_fn"]
        try:
            # transnetv2.predict_images(frames) 返回 (predictions, transitions)
            result = predict_fn(frames)
            if isinstance(result, tuple) and len(result) >= 1:
                preds = np.asarray(result[0]).flatten().tolist()
            else:
                preds = np.asarray(result).flatten().tolist()
        except Exception as e:
            logger.warning(f"[AISceneDetector] transnetv2 包推理失败: {e}")
            return self._detect_fallback(video_path)

        return self._predictions_to_shots(preds, actual_fps)

    def _predictions_to_shots(self, predictions: List[float], fps: float) -> List[Shot]:
        """将 TransNetV2 预测转为 Shot 列表"""
        import numpy as np

        preds = np.array(predictions)

        # 平滑处理
        kernel_size = 5
        if len(preds) > kernel_size:
            kernel = np.ones(kernel_size) / kernel_size
            smoothed = np.convolve(preds, kernel, mode='same')
        else:
            smoothed = preds

        # 找峰值（过渡点）
        shots = []
        shot_start = 0
        shot_idx = 0

        for i in range(1, len(smoothed)):
            is_peak = smoothed[i] > self.confidence_threshold and smoothed[i] > smoothed[i - 1]

            if is_peak and (i - shot_start) >= self.min_shot_length:
                # 检测过渡类型
                transition_type = ShotType.CUT
                if self.detect_gradual:
                    # 渐变检测：检查周围帧的预测值模式
                    window = smoothed[max(0, i-10):min(len(smoothed), i+10)]
                    if len(window) >= 5:
                        peak_width = np.sum(window > self.confidence_threshold * 0.8)
                        if peak_width > 3:
                            transition_type = ShotType.DISSOLVE

                shot = Shot(
                    index=shot_idx,
                    start_frame=shot_start,
                    end_frame=i - 1,
                    start_time=round(shot_start / fps, 3),
                    end_time=round((i - 1) / fps, 3),
                    duration=round((i - 1 - shot_start) / fps, 3),
                    shot_type=transition_type,
                    confidence=round(float(smoothed[i]), 3),
                    thumbnail_frame=shot_start + int((i - 1 - shot_start) * 0.3),
                )
                shots.append(shot)
                shot_start = i
                shot_idx += 1

        # 最后一个镜头
        if shot_start < len(smoothed):
            shots.append(Shot(
                index=shot_idx,
                start_frame=shot_start,
                end_frame=len(smoothed) - 1,
                start_time=round(shot_start / fps, 3),
                end_time=round((len(smoothed) - 1) / fps, 3),
                duration=round((len(smoothed) - 1 - shot_start) / fps, 3),
                shot_type=ShotType.CUT,
                confidence=1.0,
                thumbnail_frame=shot_start + int((len(smoothed) - 1 - shot_start) * 0.3),
            ))

        return shots

    def _detect_fallback(self, video_path: str) -> List[Shot]:
        """回退到 PySceneDetect + 传统方法"""
        from .scene_detector import SceneDetector

        sd = SceneDetector(fps=int(self.fps), min_scene_length=self.min_shot_length / self.fps, extract_metadata=False)
        scene_cuts = sd.detect(video_path)

        shots = []
        for cut in scene_cuts:
            shot = Shot(
                index=cut.index,
                start_frame=cut.start_frame,
                end_frame=cut.end_frame,
                start_time=cut.start_time,
                end_time=cut.end_time,
                duration=cut.duration,
                shot_type=ShotType.CUT,
                confidence=0.6,
                thumbnail_frame=cut.thumbnail_frame,
            )
            shots.append(shot)

        return shots

    def detect_transitions(self, video_path: str) -> List[ShotTransition]:
        """专门检测转场类型和位置"""
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or self.fps
        prev_frame = None
        transitions = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if prev_frame is not None:
                gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray_prev = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

                # 帧间亮度变化
                mean_diff = np.mean(np.abs(gray_curr.astype(np.float32) - gray_prev.astype(np.float32)))

                transition_type = ShotType.CUT
                confidence = 0.0

                if mean_diff > 30:
                    transition_type = ShotType.CUT
                    confidence = min(1.0, mean_diff / 100.0)
                elif 10 < mean_diff <= 30:
                    # 可能是渐变
                    transition_type = ShotType.DISSOLVE
                    confidence = mean_diff / 30.0

                if confidence > self.confidence_threshold:
                    transitions.append(ShotTransition(
                        frame=frame_idx,
                        time=round(frame_idx / fps, 3),
                        type=transition_type,
                        confidence=round(confidence, 3),
                    ))

            prev_frame = frame
            frame_idx += 1

        cap.release()
        return transitions

    def detect_scene_types(self, video_path: str) -> List[Dict]:
        """
        对每个镜头进行类型分类。

        分类: 对话/动作/风景/特写/摇镜/Zoom等
        """
        import cv2
        import numpy as np

        shots = self.detect(video_path)
        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            return [s.to_dict() for s in shots]

        for shot in shots:
            mid_frame_idx = shot.start_frame + shot.frame_count // 2
            cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame_idx)
            ret, frame = cap.read()

            if ret:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                # 特写检测：高边缘密度 + 面部肤色比例
                edges = cv2.Canny(gray, 50, 150)
                edge_density = np.mean(edges > 0)

                # 肤色检测（简化的 HSV 范围）
                skin_mask = cv2.inRange(hsv, (0, 20, 70), (20, 255, 255))
                skin_ratio = np.mean(skin_mask > 0)

                # 场景分类
                if skin_ratio > 0.15:
                    scene_type = "closeup_person"
                elif edge_density > 0.1:
                    scene_type = "detailed"
                elif np.mean(gray) > 200:
                    scene_type = "bright_outdoor"
                elif np.mean(gray) < 60:
                    scene_type = "dark_scene"
                else:
                    scene_type = "general"

                shot.metadata["scene_type"] = scene_type
                shot.metadata["edge_density"] = round(float(edge_density), 4)
                shot.metadata["skin_ratio"] = round(float(skin_ratio), 4)
                shot.metadata["avg_brightness"] = round(float(np.mean(gray)), 2)

        cap.release()
        return [s.to_dict() for s in shots]

    def export_shot_timeline(
        self,
        video_path: str,
        output_path: str,
        include_transitions: bool = True,
    ) -> str:
        """导出镜头分割时间线 JSON"""
        shots = self.detect(video_path)
        transitions = self.detect_transitions(video_path) if include_transitions else []

        data = {
            "source": str(Path(video_path).absolute()),
            "fps": self.fps,
            "shot_count": len(shots),
            "total_duration": shots[-1].end_time if shots else 0,
            "shots": [s.to_dict() for s in shots],
            "transitions": [
                {"frame": t.frame, "time": t.time, "type": t.type.value, "confidence": t.confidence}
                for t in transitions
            ],
        }

        Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        return output_path


__all__ = [
    "AISceneDetector",
    "Shot",
    "ShotTransition",
    "ShotType",
]
