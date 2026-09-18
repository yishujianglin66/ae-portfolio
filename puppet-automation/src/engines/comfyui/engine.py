"""ComfyUI engine adapter.

Communicates with a running ComfyUI instance via its HTTP API:
- Queue prompt / workflow
- Poll execution status
- Download output images
- Upload input images

Supports both image and video workflows (via ComfyUI-VideoHelperSuite).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx
from loguru import logger

from src.engines.base import EngineResult


class ComfyUIEngine:
    """ComfyUI engine adapter using HTTP API.

    Unlike other engines, ComfyUI is a running server, not an executable.
    So we don't inherit from BaseEngine (which expects an .exe path).
    Instead we provide the same EngineResult interface.
    """

    name = "comfyui"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8188",
        output_dir: Path | None = None,
        input_dir: Path | None = None,
        timeout: int = 600,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.output_dir = Path(output_dir) if output_dir else Path("data/comfyui_output")
        self.input_dir = Path(input_dir) if input_dir else Path("data/comfyui_input")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._available: bool | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ============================================================
    # 统一执行入口（支持 MCP 网关调度）
    # ============================================================

    async def execute(self, **kwargs: Any) -> EngineResult:
        """统一执行入口，供 MCP 网关通过 action 参数调度。

        支持的 action：
        - run_workflow: 执行 ComfyUI 工作流
        - upload_image: 上传图片到 ComfyUI 输入目录
        - get_status: 查询服务器状态
        """
        action = kwargs.pop("action", "run_workflow")

        if action == "run_workflow":
            return await self.run_workflow(**kwargs)

        if action == "upload_image":
            filename = await self.upload_image(**kwargs)
            if filename:
                return EngineResult(
                    success=True,
                    metadata={"filename": filename, "uploaded": True},
                )
            return EngineResult(success=False, error="图片上传失败")

        if action == "get_status":
            return await self._get_status()

        return EngineResult(success=False, error=f"未知 action: {action}")

    async def _get_status(self) -> EngineResult:
        """获取 ComfyUI 服务器状态（可用性 + 系统统计 + 队列）。"""
        try:
            available = await self.is_available(force_check=True)
            stats: dict[str, Any] = {}
            queue: dict[str, Any] = {}
            if available:
                try:
                    stats = await self.get_system_stats()
                except Exception as e:
                    logger.debug(f"[ComfyUI] get_system_stats 失败: {e}")
                try:
                    queue = await self.get_queue()
                except Exception as e:
                    logger.debug(f"[ComfyUI] get_queue 失败: {e}")
            return EngineResult(
                success=True,
                metadata={
                    "available": available,
                    "base_url": self.base_url,
                    "system_stats": stats,
                    "queue": queue,
                },
            )
        except Exception as e:
            return EngineResult(success=False, error=str(e))

    # ============================================================
    # Server health
    # ============================================================

    async def is_available(self, force_check: bool = False) -> bool:
        """Check if ComfyUI server is reachable."""
        if self._available is not None and not force_check:
            return self._available
        try:
            resp = await self.client.get(f"{self.base_url}/system_stats", timeout=5.0)
            self._available = resp.status_code == 200
        except Exception as e:
            logger.debug(f"[ComfyUI] Server not available: {e}")
            self._available = False
        return self._available

    async def get_system_stats(self) -> dict[str, Any]:
        """Get ComfyUI system stats (GPU, VRAM, queue)."""
        resp = await self.client.get(f"{self.base_url}/system_stats")
        resp.raise_for_status()
        return resp.json()

    async def get_queue(self) -> dict[str, Any]:
        """Get current queue status."""
        resp = await self.client.get(f"{self.base_url}/queue")
        resp.raise_for_status()
        return resp.json()

    # ============================================================
    # Workflow execution
    # ============================================================

    async def queue_prompt(
        self,
        workflow: dict[str, Any],
        client_id: str | None = None,
    ) -> str:
        """Queue a workflow prompt. Returns the prompt_id."""
        client_id = client_id or str(uuid.uuid4())
        payload = {
            "prompt": workflow,
            "client_id": client_id,
        }
        resp = await self.client.post(f"{self.base_url}/prompt", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("prompt_id") or data.get("prompt_id", "")

    async def poll_until_complete(
        self,
        prompt_id: str,
        interval: float = 1.0,
    ) -> dict[str, Any]:
        """Poll history endpoint until prompt completes.

        Returns the history entry with outputs.
        Raises on timeout or error.
        """
        start = time.time()
        while True:
            if time.time() - start > self.timeout:
                raise TimeoutError(
                    f"ComfyUI prompt {prompt_id} timed out after {self.timeout}s"
                )

            try:
                resp = await self.client.get(f"{self.base_url}/history/{prompt_id}")
                if resp.status_code == 200:
                    history = resp.json()
                    if prompt_id in history:
                        entry = history[prompt_id]
                        if entry.get("status", {}).get("completed", False):
                            return entry
                        outputs = entry.get("outputs", {})
                        if outputs:
                            return entry
            except Exception as e:
                logger.debug(f"[ComfyUI] Poll error (will retry): {e}")

            await asyncio.sleep(interval)

    async def run_workflow(
        self,
        workflow: dict[str, Any],
        output_dir: Path | None = None,
    ) -> EngineResult:
        """Run a ComfyUI workflow and download outputs.

        Args:
            workflow: ComfyUI workflow JSON dict (node_id -> node_config)
            output_dir: Directory to save output files

        Returns:
            EngineResult with output paths and metadata
        """
        result = EngineResult(success=False)
        start = time.time()
        save_dir = Path(output_dir) if output_dir else self.output_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        try:
            if not await self.is_available(force_check=True):
                result.error = "ComfyUI server not available"
                result.duration_seconds = time.time() - start
                return result

            prompt_id = await self.queue_prompt(workflow)
            logger.info(f"[ComfyUI] Queued prompt {prompt_id}")

            history_entry = await self.poll_until_complete(prompt_id)
            outputs = history_entry.get("outputs", {})

            # Download output images
            output_files: list[Path] = []
            for node_id, node_outputs in outputs.items():
                images = node_outputs.get("images", [])
                for img in images:
                    filename = img.get("filename", "")
                    subfolder = img.get("subfolder", "")
                    img_type = img.get("type", "output")
                    if filename:
                        local_path = await self._download_image(
                            filename, subfolder, img_type, save_dir
                        )
                        if local_path:
                            output_files.append(local_path)

            result.success = True
            result.output_path = output_files[0] if output_files else None
            result.metadata = {
                "prompt_id": prompt_id,
                "output_count": len(output_files),
                "output_files": [str(f) for f in output_files],
                "nodes_executed": list(outputs.keys()),
            }
            logger.info(
                f"[ComfyUI] Workflow completed: {len(output_files)} outputs, "
                f"{time.time() - start:.1f}s"
            )

        except Exception as e:
            result.error = str(e)
            logger.error(f"[ComfyUI] Workflow failed: {e}")

        result.duration_seconds = time.time() - start
        return result

    async def _download_image(
        self,
        filename: str,
        subfolder: str,
        img_type: str,
        save_dir: Path,
    ) -> Path | None:
        """Download an output image from ComfyUI."""
        params = {"filename": filename, "subfolder": subfolder, "type": img_type}
        try:
            resp = await self.client.get(f"{self.base_url}/view", params=params)
            resp.raise_for_status()
            local_path = save_dir / filename
            local_path.write_bytes(resp.content)
            return local_path
        except Exception as e:
            logger.warning(f"[ComfyUI] Failed to download {filename}: {e}")
            return None

    # ============================================================
    # Input upload
    # ============================================================

    async def upload_image(
        self,
        image_path: Path | str,
        overwrite: bool = True,
    ) -> str | None:
        """Upload an image to ComfyUI input folder.

        Returns the filename that can be used in LoadImage nodes.
        """
        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning(f"[ComfyUI] Image not found: {image_path}")
            return None

        try:
            with open(image_path, "rb") as f:
                files = {"image": (image_path.name, f, "image/png")}
                data = {"overwrite": "true" if overwrite else "false"}
                resp = await self.client.post(
                    f"{self.base_url}/upload/image", files=files, data=data
                )
                resp.raise_for_status()
                result = resp.json()
                return result.get("name", image_path.name)
        except Exception as e:
            logger.warning(f"[ComfyUI] Upload failed for {image_path.name}: {e}")
            return None

    # ============================================================
    # Workflow helpers
    # ============================================================

    @staticmethod
    def set_workflow_input(
        workflow: dict[str, Any],
        node_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Set inputs on a workflow node. Returns modified workflow (copy)."""
        import copy
        wf = copy.deepcopy(workflow)
        if node_id in wf:
            inputs = wf[node_id].get("inputs", {})
            inputs.update(kwargs)
            wf[node_id]["inputs"] = inputs
        return wf

    @staticmethod
    def find_node_by_class(
        workflow: dict[str, Any],
        class_type: str,
    ) -> str | None:
        """Find first node ID with given class_type."""
        for node_id, node_config in workflow.items():
            if node_config.get("class_type") == class_type:
                return node_id
        return None

    # ============================================================
    # 内置工作流模板（文生图 / 图生图 / ControlNet）
    # ============================================================

    def build_txt2img_workflow(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        cfg: float = 7.0,
        sampler: str = "dpmpp_2m",
        scheduler: str = "karras",
        seed: int = -1,
        batch_size: int = 1,
        model: str = "sd_xl_base_1.0.safetensors",
    ) -> dict[str, Any]:
        """构建文生图工作流。"""
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["1", 1]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
            },
            "4": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0],
                },
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": width, "height": height, "batch_size": batch_size},
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["4", 0], "vae": ["1", 2]},
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "txt2img", "images": ["6", 0]},
            },
        }
        return workflow

    def build_img2img_workflow(
        self,
        image_path: str,
        prompt: str,
        negative_prompt: str = "",
        denoise: float = 0.7,
        steps: int = 20,
        cfg: float = 7.0,
        sampler: str = "dpmpp_2m",
        scheduler: str = "karras",
        seed: int = -1,
        model: str = "sd_xl_base_1.0.safetensors",
    ) -> dict[str, Any]:
        """构建图生图工作流。"""
        workflow = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": model},
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["1", 1]},
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": negative_prompt, "clip": ["1", 1]},
            },
            "4": {
                "class_type": "LoadImage",
                "inputs": {"image": image_path},
            },
            "5": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["4", 0], "vae": ["1", 2]},
            },
            "6": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "denoise": denoise,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["5", 0],
                },
            },
            "7": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["6", 0], "vae": ["1", 2]},
            },
            "8": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "img2img", "images": ["7", 0]},
            },
        }
        return workflow

    def build_controlnet_workflow(
        self,
        image_path: str,
        prompt: str,
        control_type: str = "canny",
        negative_prompt: str = "",
        strength: float = 1.0,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = -1,
        model: str = "sd_xl_base_1.0.safetensors",
        control_net_model: str = "control-lora-canny-rank256.safetensors",
    ) -> dict[str, Any]:
        """构建 ControlNet 工作流。control_type: canny/depth/openpose/softedge/ipadapter"""
        preprocessor_map = {
            "canny": "Canny",
            "depth": "DepthAnythingV2Preprocessor",
            "openpose": "OpenPosePreprocessor",
            "softedge": "SoftEdgePreprocessor",
        }
        preprocessor = preprocessor_map.get(control_type, "Canny")
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
            "4": {"class_type": "LoadImage", "inputs": {"image": image_path}},
            "5": {"class_type": preprocessor, "inputs": {"image": ["4", 0]}},
            "6": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": control_net_model}},
            "7": {
                "class_type": "ControlNetApply",
                "inputs": {"strength": strength, "conditioning": ["2", 0], "control_net": ["6", 0], "image": ["5", 0]},
            },
            "8": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
            "9": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed, "steps": steps, "cfg": cfg,
                    "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
                    "model": ["1", 0], "positive": ["7", 0], "negative": ["3", 0], "latent_image": ["8", 0],
                },
            },
            "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["1", 2]}},
            "11": {"class_type": "SaveImage", "inputs": {"filename_prefix": "controlnet", "images": ["10", 0]}},
        }
        return workflow

    # ============================================================
    # 便捷方法
    # ============================================================

    async def txt2img(self, prompt: str, output_dir: Path | None = None, **kwargs: Any) -> EngineResult:
        """文生图。"""
        workflow = self.build_txt2img_workflow(prompt, **kwargs)
        return await self.run_workflow(workflow, output_dir=output_dir)

    async def img2img(
        self, image_path: Path | str, prompt: str, output_dir: Path | None = None, **kwargs: Any
    ) -> EngineResult:
        """图生图（自动上传图片）。"""
        image_path = Path(image_path)
        uploaded_name = await self.upload_image(image_path)
        if not uploaded_name:
            return EngineResult(success=False, error="图片上传失败")
        workflow = self.build_img2img_workflow(uploaded_name, prompt, **kwargs)
        return await self.run_workflow(workflow, output_dir=output_dir)

    async def controlnet_generate(
        self, image_path: Path | str, prompt: str, control_type: str = "canny",
        output_dir: Path | None = None, **kwargs: Any
    ) -> EngineResult:
        """ControlNet 生成。"""
        image_path = Path(image_path)
        uploaded_name = await self.upload_image(image_path)
        if not uploaded_name:
            return EngineResult(success=False, error="图片上传失败")
        workflow = self.build_controlnet_workflow(uploaded_name, prompt, control_type=control_type, **kwargs)
        return await self.run_workflow(workflow, output_dir=output_dir)

    async def batch_generate(
        self, prompts: list[str], output_dir: Path | None = None, **kwargs: Any
    ) -> list[EngineResult]:
        """批量文生图。"""
        results = []
        for i, prompt in enumerate(prompts):
            logger.info(f"[ComfyUI] 批量生成 {i+1}/{len(prompts)}: {prompt[:50]}...")
            result = await self.txt2img(prompt, output_dir=output_dir, **kwargs)
            results.append(result)
        return results

    async def list_models(self) -> list[str]:
        """列出可用的 Checkpoint 模型。"""
        try:
            resp = await self.client.get(f"{self.base_url}/models/checkpoints")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[ComfyUI] 获取模型列表失败: {e}")
            return []

    async def list_controlnets(self) -> list[str]:
        """列出可用的 ControlNet 模型。"""
        try:
            resp = await self.client.get(f"{self.base_url}/models/controlnet")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"[ComfyUI] 获取 ControlNet 列表失败: {e}")
            return []

    def get_supported_features(self) -> dict[str, Any]:
        """获取支持的功能清单。"""
        return {
            "txt2img": True,
            "img2img": True,
            "controlnet": ["canny", "depth", "openpose", "softedge", "ipadapter"],
            "samplers": ["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde"],
            "schedulers": ["normal", "karras", "exponential", "sgm_uniform"],
            "batch": True,
            "workflow_templates": True,
        }
