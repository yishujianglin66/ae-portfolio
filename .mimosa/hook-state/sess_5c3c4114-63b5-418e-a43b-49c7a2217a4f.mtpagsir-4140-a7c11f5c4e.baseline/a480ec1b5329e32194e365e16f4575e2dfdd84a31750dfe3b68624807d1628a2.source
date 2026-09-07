"""
software_sdk/adapters/comfyui_adapter.py - ComfyUI 本地 GPU 生成适配器

ComfyUI 是当前最强大的开源 AI 图像/视频生成引擎 (72k+ Stars)。
通过本地 API 驱动 Wan 2.2 / HunyuanVideo / LTX-Video / Flux 等顶级模型。

架构:
  ComfyUIAdapter → ComfyUI Local API (http://127.0.0.1:8188)
    ├── 图像生成: Flux / SDXL / SD3.5
    ├── 视频生成: Wan 2.2 / HunyuanVideo / LTX-Video
    ├── 3D 生成: Hunyuan3D
    └── 音频生成: Stable Audio

MCP: ComfyUI 官方 MCP Server (2026.6 公测)
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from typing import Any, Dict, List, Optional

from software_sdk.base import BaseSoftwareAdapter
from software_sdk.types import (
    ConnectionStatus,
    SoftwareCapabilities,
    SoftwareCapability,
    SoftwareConfig,
    SoftwareType,
    Task,
)


class ComfyUIAdapter(BaseSoftwareAdapter):
    """ComfyUI 本地 GPU 生成适配器 — 零成本、离线可用。

    通过 ComfyUI 本地 API 驱动开源 AI 生成模型生态。
    支持图像/视频/3D/音频全模态生成。
    """

    DEFAULT_URL = "http://127.0.0.1:8188"

    # 支持的模型矩阵
    MODEL_MATRIX = {
        # 图像模型
        "flux-dev": {"type": "image", "vram_gb": 12, "quality": "S"},
        "flux-schnell": {"type": "image", "vram_gb": 8, "quality": "A"},
        "sd_xl": {"type": "image", "vram_gb": 6, "quality": "A"},
        "sd3.5-large": {"type": "image", "vram_gb": 8, "quality": "S"},
        # 视频模型
        "wan2.2_14b": {"type": "video", "vram_gb": 8, "quality": "S", "max_frames": 81},
        "wan2.2_1.3b": {"type": "video", "vram_gb": 6, "quality": "B", "max_frames": 81},
        "hunyuan-video": {"type": "video", "vram_gb": 14, "quality": "S", "max_frames": 61},
        "ltx-video": {"type": "video", "vram_gb": 12, "quality": "A", "max_frames": 121},
        "cogvideox-5b": {"type": "video", "vram_gb": 16, "quality": "A", "max_frames": 49},
        # 3D 模型
        "hunyuan3d-2": {"type": "3d", "vram_gb": 8, "quality": "S"},
    }

    def __init__(
        self,
        config: Optional[SoftwareConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if config is None:
            config = SoftwareConfig(software=SoftwareType.COMFYUI)
        super().__init__(config, logger)
        self._base_url = os.environ.get("COMFYUI_URL", self.DEFAULT_URL)
        self._system_stats: Optional[Dict] = None

    def _initialize_capabilities(self) -> SoftwareCapabilities:
        return SoftwareCapabilities(
            software=SoftwareType.COMFYUI,
            capabilities={
                SoftwareCapability.AI_GENERATION,
                SoftwareCapability.RENDERING,
                SoftwareCapability.COMPOSITING,
                SoftwareCapability.FILTERS_EFFECTS,
                SoftwareCapability.SCRIPTING,
            },
            supported_formats_input={".png", ".jpg", ".mp4", ".json"},
            supported_formats_output={".png", ".jpg", ".mp4", ".webm", ".gif", ".obj"},
            gpu_accelerated=True,
            scriptable=True,
        )

    def connect(self) -> bool:
        """连接 ComfyUI 本地实例。"""
        try:
            self._status = ConnectionStatus.CONNECTING
            req = urllib.request.Request(f"{self._base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                self._system_stats = json.loads(resp.read().decode("utf-8"))
            self._set_connected()
            self._log.info(f"[ComfyUI] Connected: {self._base_url}")
            return True
        except Exception as e:
            self._set_error(f"ComfyUI not reachable: {e}")
            return False

    def disconnect(self) -> bool:
        self._status = ConnectionStatus.DISCONNECTED
        return True

    def execute_task(self, task: Task) -> Dict[str, Any]:
        """执行 ComfyUI 任务。"""
        task_name = task.name.lower()

        if task_name in ("generate_image", "text_to_image", "t2i"):
            return self._generate_image(task)
        elif task_name in ("generate_video", "text_to_video", "t2v"):
            return self._generate_video(task)
        elif task_name in ("image_to_video", "i2v"):
            return self._image_to_video(task)
        elif task_name == "get_models":
            return self._get_models()
        elif task_name == "run_workflow":
            return self._run_custom_workflow(task)

        return {"success": False, "error": f"Unknown task: {task_name}"}

    def _generate_image(self, task: Task) -> Dict[str, Any]:
        """图像生成。"""
        prompt = task.params.get("prompt", "")
        negative = task.params.get("negative_prompt", "blurry, low quality, distorted")
        width = task.params.get("width", 1024)
        height = task.params.get("height", 1024)
        model = task.params.get("model", "flux-dev")
        steps = task.params.get("steps", 20)
        output_path = task.params.get("output_path", "comfyui_output.png")

        workflow = self._build_image_workflow(prompt, negative, width, height, model, steps)
        return self._submit_and_wait(workflow, output_path, max_wait=120)

    def _generate_video(self, task: Task) -> Dict[str, Any]:
        """视频生成。"""
        prompt = task.params.get("prompt", "")
        width = task.params.get("width", 720)
        height = task.params.get("height", 1280)
        model = task.params.get("model", "wan2.2_14b")
        frames = task.params.get("frames", 81)
        output_path = task.params.get("output_path", "comfyui_output.mp4")

        workflow = self._build_video_workflow(prompt, width, height, frames, model)
        return self._submit_and_wait(workflow, output_path, max_wait=600)

    def _image_to_video(self, task: Task) -> Dict[str, Any]:
        """图生视频。"""
        image_path = task.params.get("image_path", "")
        prompt = task.params.get("prompt", "")
        model = task.params.get("model", "wan2.2_14b")
        output_path = task.params.get("output_path", "comfyui_i2v.mp4")

        workflow = self._build_i2v_workflow(image_path, prompt, model)
        return self._submit_and_wait(workflow, output_path, max_wait=600)

    def _build_image_workflow(self, prompt: str, negative: str,
                              w: int, h: int, model: str, steps: int) -> Dict:
        """构建图像生成工作流。"""
        ckpt = f"{model}.safetensors" if not model.endswith(".safetensors") else model
        return {
            "prompt": {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
                "3": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
                "4": {"class_type": "KSampler", "inputs": {
                    "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                    "latent_image": ["3", 0], "steps": steps, "cfg": 3.5,
                    "sampler_name": "euler", "scheduler": "simple",
                }},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
                "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
                "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "aevault"}},
            }
        }

    def _build_video_workflow(self, prompt: str, w: int, h: int,
                              frames: int, model: str) -> Dict:
        """构建视频生成工作流。"""
        ckpt = f"{model}.gguf" if "wan" in model else f"{model}.safetensors"
        return {
            "prompt": {
                "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
                "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
                "3": {"class_type": "EmptyLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}},
                "4": {"class_type": "KSampler", "inputs": {
                    "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                    "latent_image": ["3", 0], "steps": 20, "cfg": 7.0,
                    "sampler_name": "euler", "scheduler": "normal",
                }},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality", "clip": ["2", 0]}},
                "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
                "7": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 16, "format": "video/h264-mp4"}},
            }
        }

    def _build_i2v_workflow(self, image_path: str, prompt: str, model: str) -> Dict:
        """构建图生视频工作流。"""
        return {
            "prompt": {
                "1": {"class_type": "LoadImage", "inputs": {"image": image_path}},
                "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 0]}},
                "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": f"{model}.gguf"}},
                "5": {"class_type": "KSampler", "inputs": {
                    "model": ["4", 0], "positive": ["2", 0], "negative": ["6", 0],
                    "latent_image": ["7", 0], "steps": 20, "cfg": 7.0,
                }},
                "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["4", 0]}},
                "7": {"class_type": "ImageToVideo", "inputs": {"image": ["1", 0], "vae": ["4", 1]}},
                "8": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["4", 1]}},
                "9": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["8", 0], "frame_rate": 16, "format": "video/h264-mp4"}},
            }
        }

    def _submit_and_wait(self, workflow: Dict, output_path: str, max_wait: int = 300) -> Dict:
        """提交工作流并等待完成。"""
        try:
            # 提交
            prompt_id = self._queue_prompt(workflow)
            if not prompt_id:
                return {"success": False, "error": "Failed to queue"}

            # 等待
            result = self._wait_for_completion(prompt_id, max_wait)
            if not result:
                return {"success": False, "error": f"Timeout ({max_wait}s)"}

            # 下载输出
            outputs = result.get("outputs", {})
            for node_id, node_out in outputs.items():
                if "videos" in node_out:
                    return self._download(node_out["videos"][0], output_path)
                if "images" in node_out:
                    return self._download(node_out["images"][0], output_path)

            return {"success": False, "error": "No output generated"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _queue_prompt(self, workflow: Dict) -> str:
        data = json.dumps(workflow).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/prompt", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8")).get("prompt_id", "")

    def _wait_for_completion(self, prompt_id: str, max_wait: int) -> Optional[Dict]:
        start = time.time()
        while time.time() - start < max_wait:
            try:
                req = urllib.request.Request(f"{self._base_url}/history/{prompt_id}")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("outputs") or entry.get("status", {}).get("completed"):
                        return entry
            except Exception:
                pass
            time.sleep(5)
        return None

    def _download(self, file_info: Dict, output_path: str) -> Dict:
        filename = file_info.get("filename", "")
        subfolder = file_info.get("subfolder", "")
        ftype = file_info.get("type", "output")
        url = f"{self._base_url}/view?filename={filename}&subfolder={subfolder}&type={ftype}"
        urllib.request.urlretrieve(url, output_path)
        return {"success": True, "path": output_path, "source": "ComfyUI"}

    def _get_models(self) -> Dict[str, Any]:
        """获取已安装模型列表。"""
        try:
            req = urllib.request.Request(f"{self._base_url}/object_info/CheckpointLoaderSimple")
            with urllib.request.urlopen(req, timeout=10) as resp:
                info = json.loads(resp.read().decode("utf-8"))
            models = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            return {"success": True, "models": models}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_custom_workflow(self, task: Task) -> Dict[str, Any]:
        """运行用户自定义工作流 JSON。"""
        workflow = task.params.get("workflow", {})
        output_path = task.params.get("output_path", "comfyui_custom.png")
        if not workflow:
            return {"success": False, "error": "No workflow provided"}
        return self._submit_and_wait(workflow, output_path, max_wait=task.params.get("timeout", 300))

    def get_gpu_info(self) -> Dict[str, Any]:
        """获取 GPU 信息。"""
        if self._system_stats:
            devices = self._system_stats.get("devices", [])
            return {
                "device_count": len(devices),
                "devices": [
                    {
                        "name": d.get("name", "Unknown"),
                        "vram_total_mb": d.get("vram_total", 0) // 1024 // 1024,
                        "vram_free_mb": d.get("vram_free", 0) // 1024 // 1024,
                    }
                    for d in devices
                ],
            }
        return {"device_count": 0, "devices": []}
