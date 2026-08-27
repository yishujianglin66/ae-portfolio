#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
comfyui_mcp_server.py — ComfyUI MCP Server
============================================

轻量级 MCP Server，将 ComfyUI 本地 API 暴露为 MCP 工具。
支持自然语言驱动 AI 图像/视频生成。

工具列表:
  - comfyui_generate_image: 文生图 / 图生图
  - comfyui_generate_video: 文生视频 / 图生视频
  - comfyui_list_models: 列出已安装模型
  - comfyui_gpu_info: GPU 状态信息
  - comfyui_run_workflow: 运行自定义工作流 JSON
  - comfyui_queue_prompt: 直接提交工作流
  - comfyui_get_history: 获取历史任务

启动:
  py -3.11 comfyui_mcp_server.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("[ComfyUI MCP] mcp package not found, running in standalone mode")


COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")


# ================================================================
#  ComfyUI API 客户端
# ================================================================

class ComfyUIClient:
    """ComfyUI API 客户端。"""

    def __init__(self, base_url: str = COMFYUI_URL):
        self.base_url = base_url

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_system_stats(self) -> Dict:
        req = urllib.request.Request(f"{self.base_url}/system_stats")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_object_info(self, class_name: str) -> Dict:
        req = urllib.request.Request(f"{self.base_url}/object_info/{class_name}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def queue_prompt(self, workflow: Dict) -> str:
        data = json.dumps(workflow).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/prompt", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("prompt_id", "")

    def get_history(self, prompt_id: str) -> Dict:
        req = urllib.request.Request(f"{self.base_url}/history/{prompt_id}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def wait_for_completion(self, prompt_id: str, max_wait: int = 300) -> Optional[Dict]:
        start = time.time()
        while time.time() - start < max_wait:
            try:
                history = self.get_history(prompt_id)
                if prompt_id in history:
                    entry = history[prompt_id]
                    if entry.get("outputs") or entry.get("status", {}).get("completed"):
                        return entry
            except Exception:
                pass
            time.sleep(5)
        return None

    def get_gpu_info(self) -> Dict:
        stats = self.get_system_stats()
        devices = stats.get("devices", [])
        return {
            "devices": [
                {
                    "name": d.get("name", "Unknown"),
                    "vram_total_gb": round(d.get("vram_total", 0) / 1024**3, 1),
                    "vram_free_gb": round(d.get("vram_free", 0) / 1024**3, 1),
                }
                for d in devices
            ]
        }

    def list_models(self) -> List[str]:
        try:
            info = self.get_object_info("CheckpointLoaderSimple")
            return info.get("CheckpointLoaderSimple", {}).get(
                "input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        except Exception:
            return []


client = ComfyUIClient()


# ================================================================
#  MCP Server 定义
# ================================================================

if MCP_AVAILABLE:
    app = Server("comfyui-mcp")

    @app.list_tools()
    async def list_tools() -> List[Tool]:
        return [
            Tool(
                name="comfyui_generate_image",
                description="使用 ComfyUI 生成图像 (支持 Flux/SDXL/SD3.5 等模型)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "生成提示词"},
                        "negative_prompt": {"type": "string", "default": "blurry, low quality"},
                        "width": {"type": "integer", "default": 1024},
                        "height": {"type": "integer", "default": 1024},
                        "model": {"type": "string", "default": "flux-dev"},
                        "steps": {"type": "integer", "default": 20},
                        "output_path": {"type": "string", "default": "output.png"},
                    },
                    "required": ["prompt"],
                },
            ),
            Tool(
                name="comfyui_generate_video",
                description="使用 ComfyUI 生成视频 (支持 Wan 2.2/HunyuanVideo/LTX 等模型)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "生成提示词"},
                        "width": {"type": "integer", "default": 720},
                        "height": {"type": "integer", "default": 1280},
                        "model": {"type": "string", "default": "wan2.2_14b"},
                        "frames": {"type": "integer", "default": 81},
                        "output_path": {"type": "string", "default": "output.mp4"},
                    },
                    "required": ["prompt"],
                },
            ),
            Tool(
                name="comfyui_list_models",
                description="列出 ComfyUI 已安装的所有模型",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="comfyui_gpu_info",
                description="获取 GPU 状态信息",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="comfyui_run_workflow",
                description="运行自定义 ComfyUI 工作流 JSON",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow": {"type": "object", "description": "ComfyUI workflow JSON"},
                        "output_path": {"type": "string", "default": "output.png"},
                        "timeout": {"type": "integer", "default": 300},
                    },
                    "required": ["workflow"],
                },
            ),
            Tool(
                name="comfyui_get_history",
                description="获取 ComfyUI 历史任务结果",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "prompt_id": {"type": "string", "description": "任务ID"},
                    },
                    "required": ["prompt_id"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
        try:
            if name == "comfyui_generate_image":
                result = _generate_image(arguments)
            elif name == "comfyui_generate_video":
                result = _generate_video(arguments)
            elif name == "comfyui_list_models":
                result = {"models": client.list_models()}
            elif name == "comfyui_gpu_info":
                result = client.get_gpu_info()
            elif name == "comfyui_run_workflow":
                result = _run_workflow(arguments)
            elif name == "comfyui_get_history":
                result = client.get_history(arguments.get("prompt_id", ""))
            else:
                result = {"error": f"Unknown tool: {name}"}

            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


def _generate_image(args: Dict) -> Dict:
    """图像生成。"""
    prompt = args.get("prompt", "")
    negative = args.get("negative_prompt", "blurry, low quality")
    w = args.get("width", 1024)
    h = args.get("height", 1024)
    model = args.get("model", "flux-dev")
    steps = args.get("steps", 20)
    output = args.get("output_path", "output.png")

    ckpt = f"{model}.safetensors" if not model.endswith(".safetensors") else model
    workflow = {
        "prompt": {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
            "3": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
            "4": {"class_type": "KSampler", "inputs": {
                "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                "latent_image": ["3", 0], "steps": steps, "cfg": 3.5,
            }},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["2", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
            "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "mcp"}},
        }
    }

    prompt_id = client.queue_prompt(workflow)
    if not prompt_id:
        return {"success": False, "error": "Failed to queue"}

    result = client.wait_for_completion(prompt_id, max_wait=120)
    if result:
        return {"success": True, "prompt_id": prompt_id, "outputs": result.get("outputs", {})}
    return {"success": False, "error": "Timeout", "prompt_id": prompt_id}


def _generate_video(args: Dict) -> Dict:
    """视频生成。"""
    prompt = args.get("prompt", "")
    w = args.get("width", 720)
    h = args.get("height", 1280)
    model = args.get("model", "wan2.2_14b")
    frames = args.get("frames", 81)

    ckpt = f"{model}.gguf" if "wan" in model else f"{model}.safetensors"
    workflow = {
        "prompt": {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
            "2": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
            "3": {"class_type": "EmptyLatentVideo", "inputs": {"width": w, "height": h, "length": frames, "batch_size": 1}},
            "4": {"class_type": "KSampler", "inputs": {
                "model": ["2", 0], "positive": ["1", 0], "negative": ["5", 0],
                "latent_image": ["3", 0], "steps": 20, "cfg": 7.0,
            }},
            "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["2", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["2", 1]}},
            "7": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 16, "format": "video/h264-mp4"}},
        }
    }

    prompt_id = client.queue_prompt(workflow)
    if not prompt_id:
        return {"success": False, "error": "Failed to queue"}

    result = client.wait_for_completion(prompt_id, max_wait=600)
    if result:
        return {"success": True, "prompt_id": prompt_id, "outputs": result.get("outputs", {})}
    return {"success": False, "error": "Timeout", "prompt_id": prompt_id}


def _run_workflow(args: Dict) -> Dict:
    """运行自定义工作流。"""
    workflow = args.get("workflow", {})
    timeout = args.get("timeout", 300)

    prompt_id = client.queue_prompt(workflow)
    if not prompt_id:
        return {"success": False, "error": "Failed to queue"}

    result = client.wait_for_completion(prompt_id, max_wait=timeout)
    if result:
        return {"success": True, "prompt_id": prompt_id, "outputs": result.get("outputs", {})}
    return {"success": False, "error": "Timeout", "prompt_id": prompt_id}


# ================================================================
#  启动
# ================================================================

async def main():
    if not MCP_AVAILABLE:
        print("[ComfyUI MCP] Install mcp: pip install mcp[cli]")
        return

    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
