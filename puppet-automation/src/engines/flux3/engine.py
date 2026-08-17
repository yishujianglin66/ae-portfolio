"""Flux 3 engine adapter.

Communicates with Flux 3 API (Black Forest Labs) for unified image + video + audio generation.

Key capabilities:
- Text-to-image (Flux image models)
- Image-to-image
- Text-to-video (Flux 3 - unified audio-video generation)
- Image-to-video
- Audio generation (synchronized with video)

API design follows OpenAI-compatible patterns with BFL-specific extensions for video/audio.
Actual API endpoints may vary; this adapter provides a stable interface for the pipeline.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

from src.engines.base import EngineResult


class Flux3Engine:
    """Flux 3 engine adapter using HTTP API.

    Like ComfyUI, Flux 3 is a remote API service, not a local executable.
    It does not inherit from BaseEngine but provides the same EngineResult interface.

    Supports generation modes:
    - image: text-to-image / image-to-image
    - video: text-to-video / image-to-video (Flux 3, with native audio sync)
    - audio: standalone audio generation
    """

    name = "flux3"

    def __init__(
        self,
        base_url: str = "https://api.bfl.ml/v1",
        api_key: str = "",
        output_dir: Optional[Path] = None,
        timeout: int = 1800,
        poll_interval: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.output_dir = Path(output_dir) if output_dir else Path("data/flux3_output")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ============================================================
    # 统一执行入口（支持 MCP 网关 / 编排器调度）
    # ============================================================

    async def execute(self, **kwargs: Any) -> EngineResult:
        """统一执行入口。

        支持的 action：
        - generate_image: 文生图
        - image_to_image: 图生图
        - generate_video: 文生视频（音画一体）
        - image_to_video: 图生视频
        - generate_audio: 纯音频生成
        - get_status: 查询引擎状态
        """
        action = kwargs.pop("action", "generate_image")

        if action == "generate_image":
            return await self.generate_image(**kwargs)
        if action == "image_to_image":
            return await self.image_to_image(**kwargs)
        if action == "generate_video":
            return await self.generate_video(**kwargs)
        if action == "image_to_video":
            return await self.image_to_video(**kwargs)
        if action == "generate_audio":
            return await self.generate_audio(**kwargs)
        if action == "get_status":
            return await self._get_status()

        return EngineResult(success=False, error=f"未知 action: {action}")

    async def _get_status(self) -> EngineResult:
        """获取 Flux 3 API 状态与支持的模型列表。"""
        try:
            available = await self.is_available(force_check=True)
            models: list[str] = []
            if available:
                try:
                    models = await self.list_models()
                except Exception as e:
                    logger.debug(f"[Flux3] list_models 失败: {e}")
            return EngineResult(
                success=True,
                metadata={
                    "available": available,
                    "base_url": self.base_url,
                    "has_api_key": bool(self.api_key),
                    "models": models,
                    "features": self.get_supported_features(),
                },
            )
        except Exception as e:
            return EngineResult(success=False, error=str(e))

    # ============================================================
    # Health & availability
    # ============================================================

    async def is_available(self, force_check: bool = False) -> bool:
        """Check if Flux 3 API is reachable."""
        if self._available is not None and not force_check:
            return self._available
        if not self.api_key:
            self._available = False
            return False
        try:
            resp = await self.client.get(f"{self.base_url}/models", timeout=10.0)
            self._available = resp.status_code == 200
        except Exception as e:
            logger.debug(f"[Flux3] API not available: {e}")
            self._available = False
        return self._available

    async def list_models(self) -> list[str]:
        """列出可用模型。"""
        try:
            resp = await self.client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "data" in data:
                return [m.get("id", "") for m in data.get("data", [])]
            if isinstance(data, list):
                return [m.get("id", "") for m in data]
            return []
        except Exception as e:
            logger.warning(f"[Flux3] 获取模型列表失败: {e}")
            return []

    # ============================================================
    # Async job helpers (polling pattern)
    # ============================================================

    async def _submit_job(self, endpoint: str, payload: dict[str, Any]) -> str:
        """提交异步生成任务，返回 job_id。"""
        resp = await self.client.post(f"{self.base_url}/{endpoint}", json=payload)
        resp.raise_for_status()
        data = resp.json()
        job_id = data.get("id") or data.get("job_id") or data.get("task_id") or ""
        if not job_id:
            raise ValueError(f"API 响应中未找到 job_id: {data}")
        return job_id

    async def _poll_job(
        self,
        job_id: str,
        endpoint: str = "results",
        interval: Optional[float] = None,
    ) -> dict[str, Any]:
        """轮询任务直到完成。返回最终结果字典。"""
        poll_interval = interval or self.poll_interval
        start = time.time()

        while True:
            if time.time() - start > self.timeout:
                raise TimeoutError(
                    f"Flux 3 job {job_id} timed out after {self.timeout}s"
                )

            try:
                resp = await self.client.get(f"{self.base_url}/{endpoint}/{job_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "").lower()
                    if status in ("succeeded", "completed", "done", "success"):
                        return data
                    if status in ("failed", "error", "cancelled"):
                        error_msg = data.get("error") or data.get("error_message") or "任务失败"
                        raise RuntimeError(f"Job {job_id} failed: {error_msg}")
            except (httpx.HTTPStatusError, httpx.ConnectError):
                pass

            await asyncio.sleep(poll_interval)

    async def _download_output(
        self,
        url: str,
        save_dir: Path,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """下载生成结果到本地。"""
        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            if not filename:
                # 从 URL 提取文件名或生成 UUID
                url_path = Path(url.split("?")[0])
                filename = url_path.name or f"flux3_{uuid.uuid4().hex[:12]}"
            local_path = save_dir / filename
            local_path.write_bytes(resp.content)
            return local_path
        except Exception as e:
            logger.warning(f"[Flux3] 下载失败 {url[:80]}...: {e}")
            return None

    # ============================================================
    # Image generation
    # ============================================================

    async def generate_image(
        self,
        prompt: str,
        model: str = "flux-1.1-pro",
        width: int = 1024,
        height: int = 1024,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """文生图。

        Args:
            prompt: 正向提示词
            model: 模型名称
            width: 图像宽度
            height: 图像高度
            steps: 采样步数（可选）
            seed: 随机种子（可选）
            output_dir: 输出目录
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir / "images"
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not self.api_key:
                result.error = "未配置 Flux 3 API Key"
                result.duration_seconds = time.time() - start
                return result

            payload: dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "width": width,
                "height": height,
            }
            if steps is not None:
                payload["steps"] = steps
            if seed is not None:
                payload["seed"] = seed
            # 透传额外参数
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            job_id = await self._submit_job("image", payload)
            logger.info(f"[Flux3] 图像生成任务已提交: {job_id}")

            data = await self._poll_job(job_id, endpoint="image")
            output_url = self._extract_output_url(data)

            if not output_url:
                result.error = "API 响应中未找到输出 URL"
                result.duration_seconds = time.time() - start
                return result

            local_path = await self._download_output(output_url, save_dir)
            if local_path:
                result.success = True
                result.output_path = local_path
                result.metadata = {
                    "job_id": job_id,
                    "model": model,
                    "width": width,
                    "height": height,
                    "seed": data.get("seed", seed),
                    "output_url": output_url,
                }
                logger.info(
                    f"[Flux3] 图像生成完成: {local_path.name}, "
                    f"{time.time() - start:.1f}s"
                )
            else:
                result.error = "下载生成结果失败"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[Flux3] 图像生成失败: {e}")

        result.duration_seconds = time.time() - start
        return result

    async def image_to_image(
        self,
        image_path: str | Path,
        prompt: str,
        model: str = "flux-1.1-pro",
        strength: float = 0.7,
        width: Optional[int] = None,
        height: Optional[int] = None,
        steps: Optional[int] = None,
        seed: Optional[int] = None,
        output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """图生图。

        Args:
            image_path: 输入图像路径
            prompt: 正向提示词
            model: 模型名称
            strength: 重绘强度 (0-1)
            width/height: 输出尺寸（可选，默认跟随输入）
            steps/seed: 同 generate_image
            output_dir: 输出目录
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir / "images"
        save_dir.mkdir(parents=True, exist_ok=True)
        image_path = Path(image_path)

        try:
            if not self.api_key:
                result.error = "未配置 Flux 3 API Key"
                result.duration_seconds = time.time() - start
                return result
            if not image_path.exists():
                result.error = f"输入图像不存在: {image_path}"
                result.duration_seconds = time.time() - start
                return result

            # 上传图像
            uploaded_url = await self._upload_image(image_path)
            if not uploaded_url:
                result.error = "图像上传失败"
                result.duration_seconds = time.time() - start
                return result

            payload: dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "image": uploaded_url,
                "strength": strength,
            }
            if width is not None:
                payload["width"] = width
            if height is not None:
                payload["height"] = height
            if steps is not None:
                payload["steps"] = steps
            if seed is not None:
                payload["seed"] = seed
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            job_id = await self._submit_job("image", payload)
            logger.info(f"[Flux3] 图生图任务已提交: {job_id}")

            data = await self._poll_job(job_id, endpoint="image")
            output_url = self._extract_output_url(data)

            if not output_url:
                result.error = "API 响应中未找到输出 URL"
                result.duration_seconds = time.time() - start
                return result

            local_path = await self._download_output(output_url, save_dir)
            if local_path:
                result.success = True
                result.output_path = local_path
                result.metadata = {
                    "job_id": job_id,
                    "model": model,
                    "strength": strength,
                    "seed": data.get("seed", seed),
                    "input_image": str(image_path),
                }
                logger.info(
                    f"[Flux3] 图生图完成: {local_path.name}, "
                    f"{time.time() - start:.1f}s"
                )
            else:
                result.error = "下载生成结果失败"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[Flux3] 图生图失败: {e}")

        result.duration_seconds = time.time() - start
        return result

    # ============================================================
    # Video generation (Flux 3 - 音画一体)
    # ============================================================

    async def generate_video(
        self,
        prompt: str,
        model: str = "flux-3",
        width: int = 1280,
        height: int = 720,
        duration: float = 20.0,
        fps: int = 24,
        seed: Optional[int] = None,
        audio_enabled: bool = True,
        audio_prompt: Optional[str] = None,
        output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """文生视频（Flux 3 原生音画同步）。

        Args:
            prompt: 视频内容提示词
            model: 模型名称（默认 flux-3）
            width: 视频宽度
            height: 视频高度
            duration: 视频时长（秒），Flux 3 支持最长约 20 秒
            fps: 帧率
            seed: 随机种子
            audio_enabled: 是否生成同步音频（Flux 3 原生能力）
            audio_prompt: 音频提示词（可选，未提供则根据视频内容自动生成）
            output_dir: 输出目录
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir / "videos"
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not self.api_key:
                result.error = "未配置 Flux 3 API Key"
                result.duration_seconds = time.time() - start
                return result

            payload: dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": fps,
            }
            if seed is not None:
                payload["seed"] = seed
            if audio_enabled:
                payload["audio"] = True
                if audio_prompt:
                    payload["audio_prompt"] = audio_prompt
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            job_id = await self._submit_job("video", payload)
            logger.info(f"[Flux3] 视频生成任务已提交: {job_id} (音画一体={audio_enabled})")

            data = await self._poll_job(job_id, endpoint="video")
            video_url = self._extract_output_url(data, media_type="video")
            audio_url = self._extract_output_url(data, media_type="audio")

            if not video_url:
                result.error = "API 响应中未找到视频输出 URL"
                result.duration_seconds = time.time() - start
                return result

            video_path = await self._download_output(video_url, save_dir)
            audio_path = None
            if audio_url and audio_enabled:
                audio_path = await self._download_output(audio_url, save_dir)

            if video_path:
                result.success = True
                result.output_path = video_path
                result.metadata = {
                    "job_id": job_id,
                    "model": model,
                    "width": width,
                    "height": height,
                    "duration": duration,
                    "fps": fps,
                    "seed": data.get("seed", seed),
                    "audio_enabled": audio_enabled,
                    "audio_path": str(audio_path) if audio_path else None,
                    "has_sync_audio": audio_path is not None,
                    "output_url": video_url,
                }
                logger.info(
                    f"[Flux3] 视频生成完成: {video_path.name}, "
                    f"音频={'✓' if audio_path else '✗'}, "
                    f"{time.time() - start:.1f}s"
                )
            else:
                result.error = "下载生成结果失败"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[Flux3] 视频生成失败: {e}")

        result.duration_seconds = time.time() - start
        return result

    async def image_to_video(
        self,
        image_path: str | Path,
        prompt: str = "",
        model: str = "flux-3",
        duration: float = 20.0,
        fps: int = 24,
        seed: Optional[int] = None,
        audio_enabled: bool = True,
        audio_prompt: Optional[str] = None,
        output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """图生视频。

        Args:
            image_path: 起始图像路径
            prompt: 运动/内容提示词（可选）
            model/duration/fps/seed/audio_*: 同 generate_video
            output_dir: 输出目录
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir / "videos"
        save_dir.mkdir(parents=True, exist_ok=True)
        image_path = Path(image_path)

        try:
            if not self.api_key:
                result.error = "未配置 Flux 3 API Key"
                result.duration_seconds = time.time() - start
                return result
            if not image_path.exists():
                result.error = f"输入图像不存在: {image_path}"
                result.duration_seconds = time.time() - start
                return result

            uploaded_url = await self._upload_image(image_path)
            if not uploaded_url:
                result.error = "图像上传失败"
                result.duration_seconds = time.time() - start
                return result

            payload: dict[str, Any] = {
                "image": uploaded_url,
                "model": model,
                "duration": duration,
                "fps": fps,
            }
            if prompt:
                payload["prompt"] = prompt
            if seed is not None:
                payload["seed"] = seed
            if audio_enabled:
                payload["audio"] = True
                if audio_prompt:
                    payload["audio_prompt"] = audio_prompt
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            job_id = await self._submit_job("video", payload)
            logger.info(f"[Flux3] 图生视频任务已提交: {job_id}")

            data = await self._poll_job(job_id, endpoint="video")
            video_url = self._extract_output_url(data, media_type="video")
            audio_url = self._extract_output_url(data, media_type="audio")

            if not video_url:
                result.error = "API 响应中未找到视频输出 URL"
                result.duration_seconds = time.time() - start
                return result

            video_path = await self._download_output(video_url, save_dir)
            audio_path = None
            if audio_url and audio_enabled:
                audio_path = await self._download_output(audio_url, save_dir)

            if video_path:
                result.success = True
                result.output_path = video_path
                result.metadata = {
                    "job_id": job_id,
                    "model": model,
                    "duration": duration,
                    "fps": fps,
                    "seed": data.get("seed", seed),
                    "audio_enabled": audio_enabled,
                    "audio_path": str(audio_path) if audio_path else None,
                    "has_sync_audio": audio_path is not None,
                    "input_image": str(image_path),
                }
                logger.info(
                    f"[Flux3] 图生视频完成: {video_path.name}, "
                    f"音频={'✓' if audio_path else '✗'}, "
                    f"{time.time() - start:.1f}s"
                )
            else:
                result.error = "下载生成结果失败"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[Flux3] 图生视频失败: {e}")

        result.duration_seconds = time.time() - start
        return result

    # ============================================================
    # Audio generation
    # ============================================================

    async def generate_audio(
        self,
        prompt: str,
        model: str = "flux-3-audio",
        duration: float = 10.0,
        seed: Optional[int] = None,
        output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> EngineResult:
        """纯音频生成。

        Args:
            prompt: 音频描述提示词
            model: 模型名称
            duration: 音频时长（秒）
            seed: 随机种子
            output_dir: 输出目录
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir / "audio"
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not self.api_key:
                result.error = "未配置 Flux 3 API Key"
                result.duration_seconds = time.time() - start
                return result

            payload: dict[str, Any] = {
                "prompt": prompt,
                "model": model,
                "duration": duration,
            }
            if seed is not None:
                payload["seed"] = seed
            for k, v in kwargs.items():
                if k not in payload:
                    payload[k] = v

            job_id = await self._submit_job("audio", payload)
            logger.info(f"[Flux3] 音频生成任务已提交: {job_id}")

            data = await self._poll_job(job_id, endpoint="audio")
            audio_url = self._extract_output_url(data, media_type="audio")

            if not audio_url:
                result.error = "API 响应中未找到音频输出 URL"
                result.duration_seconds = time.time() - start
                return result

            local_path = await self._download_output(audio_url, save_dir)
            if local_path:
                result.success = True
                result.output_path = local_path
                result.metadata = {
                    "job_id": job_id,
                    "model": model,
                    "duration": duration,
                    "seed": data.get("seed", seed),
                }
                logger.info(
                    f"[Flux3] 音频生成完成: {local_path.name}, "
                    f"{time.time() - start:.1f}s"
                )
            else:
                result.error = "下载生成结果失败"

        except Exception as e:
            result.error = str(e)
            logger.error(f"[Flux3] 音频生成失败: {e}")

        result.duration_seconds = time.time() - start
        return result

    # ============================================================
    # Internal helpers
    # ============================================================

    async def _upload_image(self, image_path: Path) -> Optional[str]:
        """上传图像到 API，返回可访问的 URL。

        不同 Provider 上传方式不同，这里提供标准 multipart 上传实现。
        若 API 支持直接传 base64 或公网 URL，可在子类中覆盖。
        """
        try:
            with open(image_path, "rb") as f:
                files = {"image": (image_path.name, f, "image/png")}
                resp = await self.client.post(
                    f"{self.base_url}/upload", files=files
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("url") or data.get("image_url") or data.get("id")
        except Exception as e:
            logger.warning(f"[Flux3] 上传图像失败: {e}")
            return None

    @staticmethod
    def _extract_output_url(
        data: dict[str, Any],
        media_type: str = "image",
    ) -> Optional[str]:
        """从 API 响应中提取输出文件 URL。

        兼容多种响应格式：
        - {output: {url: "..."}}
        - {result: {url: "..."}}
        - {images: [{url: "..."}]}
        - {video_url: "..."} / {audio_url: "..."}
        - {output_url: "..."}
        """
        # 直接字段
        direct_fields = {
            "image": ["image_url", "output_url", "url", "result_url"],
            "video": ["video_url", "output_url", "url", "result_url"],
            "audio": ["audio_url", "output_url", "url", "result_url"],
        }
        fields = direct_fields.get(media_type, direct_fields["image"])
        for field in fields:
            if field in data and isinstance(data[field], str) and data[field].startswith("http"):
                return data[field]

        # 嵌套 output/result
        for container in ("output", "result", "data"):
            if container in data and isinstance(data[container], dict):
                for field in fields:
                    val = data[container].get(field)
                    if isinstance(val, str) and val.startswith("http"):
                        return val

        # images/videos 数组
        list_fields = {
            "image": ["images", "output_images"],
            "video": ["videos", "output_videos"],
            "audio": ["audios", "output_audios"],
        }
        for list_field in list_fields.get(media_type, []):
            if list_field in data and isinstance(data[list_field], list):
                for item in data[list_field]:
                    if isinstance(item, dict):
                        url = item.get("url") or item.get("src")
                        if isinstance(url, str) and url.startswith("http"):
                            return url
                    elif isinstance(item, str) and item.startswith("http"):
                        return item

        return None

    # ============================================================
    # Capability query
    # ============================================================

    def get_supported_features(self) -> dict[str, Any]:
        """获取支持的功能清单。"""
        return {
            "text_to_image": True,
            "image_to_image": True,
            "text_to_video": True,
            "image_to_video": True,
            "audio_generation": True,
            "unified_audio_video": True,  # Flux 3 核心特性：音画一体原生同步
            "models": {
                "image": ["flux-1.1-pro", "flux-1-dev", "flux-1-schnell"],
                "video": ["flux-3"],
                "audio": ["flux-3-audio"],
            },
            "max_video_duration": 20.0,
            "resolutions": {
                "image": [
                    (1024, 1024),
                    (1280, 720),
                    (720, 1280),
                    (1920, 1080),
                    (1080, 1920),
                ],
                "video": [
                    (1280, 720),
                    (720, 1280),
                    (1920, 1080),
                ],
            },
        }
