"""引擎注册中心 — 统一的引擎实例化入口。

API 进程和 Celery Worker 都通过 ``build_engine_registry()`` 获取引擎字典，
消除 main.py 与 celery_app.py 之间的重复代码，并预留多机扩展接口。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from .ae import AEEngine
from .audition import AuditionEngine
from .blender import BlenderEngine
from .cinema4d import Cinema4DEngine
from .davinci import DavinciEngine
from .ffmpeg import FFmpegEngine
from .media_encoder import MediaEncoderEngine
from .moviepy import MoviePyEngine
from .openmontage import OpenMontageEngine
from .photoshop import PhotoshopEngine
from .premiere import PremiereEngine
from .matting import MattingEngine
from .rife import RifeEngine
from .sadtalker import SadTalkerEngine
from .sam2 import SAM2Engine
from .silhouette import SilhouetteEngine
from .topaz import TopazEngine
from .whisper import WhisperEngine

# 标准引擎类注册表（subprocess 驱动，路径在 settings 中配置）
ENGINE_CLASSES: dict[str, type] = {
    "ffmpeg": FFmpegEngine,
    "ae": AEEngine,
    "topaz": TopazEngine,
    "silhouette": SilhouetteEngine,
    "blender": BlenderEngine,
    "cinema4d": Cinema4DEngine,
    "davinci": DavinciEngine,
    "media_encoder": MediaEncoderEngine,
    "premiere": PremiereEngine,
    "sadtalker": SadTalkerEngine,
    "audition": AuditionEngine,
    "moviepy": MoviePyEngine,
    "openmontage": OpenMontageEngine,
    "photoshop": PhotoshopEngine,
    "matting": MattingEngine,
    "rife": RifeEngine,
    "sam2": SAM2Engine,
    "whisper": WhisperEngine,
}


def build_engine_registry(
    config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建引擎实例字典。

    Args:
        config_overrides: 可选的配置覆盖，预留多机部署扩展。
            例如 ``{"silhouette_path": Path("/opt/silhouette")}`` 可覆盖
            默认路径。当前版本仅记录日志，引擎内部仍从 settings 读取路径。

    Returns:
        引擎名称到引擎实例的映射字典。初始化失败的引擎会被跳过。
    """
    engines: dict[str, Any] = {}

    for name, cls in ENGINE_CLASSES.items():
        try:
            engines[name] = cls()
            logger.info(f"Engine [{name}] initialized")
        except Exception as e:
            logger.warning(f"Engine [{name}] failed to init: {e}")

    # ComfyUI（HTTP 驱动，总是可实例化）
    try:
        from ..config import settings
        from .comfyui import ComfyUIEngine, WorkflowManager

        comfyui_engine = ComfyUIEngine(
            base_url=settings.comfyui_base_url,
            output_dir=settings.comfyui_output_dir,
            input_dir=settings.comfyui_input_dir,
            timeout=settings.comfyui_timeout,
        )
        engines["comfyui"] = comfyui_engine
        logger.info(f"Engine [comfyui] initialized (url={settings.comfyui_base_url})")
    except Exception as e:
        logger.warning(f"Engine [comfyui] failed to init: {e}")

    # Flux3（HTTP API 驱动）
    try:
        from ..config import settings
        from .flux3 import Flux3Engine

        flux3_api_key_val = (
            settings.flux3_api_key.get_secret_value()
            if hasattr(settings.flux3_api_key, "get_secret_value")
            else settings.flux3_api_key
        )
        flux3_engine = Flux3Engine(
            base_url=settings.flux3_base_url,
            api_key=flux3_api_key_val,
            output_dir=settings.flux3_output_dir,
            timeout=settings.flux3_timeout,
            poll_interval=settings.flux3_poll_interval,
        )
        engines["flux3"] = flux3_engine
        logger.info(
            f"Engine [flux3] initialized (url={settings.flux3_base_url}, "
            f"api_key={'✓' if flux3_api_key_val else '✗'})"
        )
    except Exception as e:
        logger.warning(f"Engine [flux3] failed to init: {e}")

    if config_overrides:
        logger.info(f"Engine registry built with config overrides: {list(config_overrides.keys())}")
    else:
        logger.info(f"Engine registry built with {len(engines)} engines")

    return engines
