"""MCP Gateway - Unified engine access via Model Context Protocol.

Implements a lightweight MCP-compatible gateway that exposes all
puppet automation engines as standard MCP tools.

Supports two transport modes:
1. HTTP REST (for simple synchronous calls)
2. SSE (for long-running tasks with progress streaming)

Tool naming convention: {engine}_{action}_{object}
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from ..config import settings
from ..engines.base import EngineResult

_security = HTTPBearer(auto_error=False)

WEAK_TOKENS = {"", "change-me-in-production", "dev-token-change-me", "default-token"}


def _validate_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security),
) -> bool:
    """MCP Gateway Bearer Token 认证。

    安全策略：
    - 开发环境（env=development）且 token 为默认值时，发出警告但允许访问。
    - 生产环境必须设置有效 token，否则拒绝访问。
    - 空 token 或已知弱 token 在生产环境一律拒绝。
    """
    token = credentials.credentials if credentials else ""
    raw = settings.mcp_auth_token
    # 与 main.py 的 _get_configured_mcp_token 保持一致：SecretStr 必须解包后比较，
    # 否则 SecretStr != str 恒成立，开发/生产环境都会误拒（MCP 端点全量 401 回归）。
    configured = raw.get_secret_value() if hasattr(raw, "get_secret_value") else raw

    if settings.env == "production":
        if configured in WEAK_TOKENS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="生产环境 MCP_AUTH_TOKEN 未正确配置",
            )
        if not token or token != configured:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 MCP 认证令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True

    if configured in WEAK_TOKENS:
        logger.warning(
            "MCP Gateway 使用默认认证令牌，仅限开发环境。生产环境请设置 MCP_AUTH_TOKEN。"
        )
        if not token:
            return True
    elif token != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 MCP 认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# ============================================================
# Tool Registry
# ============================================================

@dataclass
class MCPTool:
    """MCP tool descriptor."""
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[EngineResult]]
    engine: str
    action: str


class MCPRegistry:
    """Registry for all MCP-exposed tools."""

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._engines: dict[str, Any] = {}

    def register_engine(self, engine_name: str, engine_instance: Any) -> None:
        """Register an engine instance and auto-discover its actions."""
        self._engines[engine_name] = engine_instance
        logger.info(f"MCP: Registered engine [{engine_name}]")

    def register_tool(self, tool: MCPTool) -> None:
        """Manually register a tool."""
        self._tools[tool.name] = tool
        logger.debug(f"MCP: Registered tool [{tool.name}]")

    def get_tool(self, name: str) -> MCPTool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all tools in MCP format."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call a tool by name with arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise KeyError(f"Tool '{name}' not found")

        try:
            result = await tool.handler(**arguments)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": result.success,
                            "output_path": str(result.output_path) if result.output_path else None,
                            "metadata": result.metadata,
                            "error": result.error,
                        }, default=str),
                    }
                ],
                "isError": not result.success,
            }
        except Exception as e:
            logger.error(f"MCP tool [{name}] failed: {e}")
            return {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            }

    @property
    def tools(self) -> dict[str, MCPTool]:
        return self._tools

    @property
    def engines(self) -> dict[str, Any]:
        return self._engines


# Global registry
mcp_registry = MCPRegistry()


# ============================================================
# Tool Definitions
# ============================================================

def _build_tool_definitions() -> list[MCPTool]:
    """Build all standard tool definitions from engine capabilities."""
    tools = []

    # --- FFmpeg tools ---
    ffmpeg_tools = [
        {
            "name": "ffmpeg_convert_video",
            "description": "Convert video format, codec, bitrate, or resolution",
            "action": "convert",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Input video file path"},
                    "output_path": {"type": "string", "description": "Output video file path"},
                    "codec": {"type": "string", "description": "Video codec", "default": "libx264"},
                    "crf": {"type": "number", "description": "CRF quality 0-51", "default": 23},
                    "preset": {"type": "string", "description": "Encoding preset", "default": "medium"},
                },
                "required": ["input_path", "output_path"],
            },
        },
        {
            "name": "ffmpeg_extract_frames",
            "description": "Extract frames from video at specified FPS",
            "action": "extract_frames",
            "input_schema": {
                "type": "object",
                "properties": {
                    "video_path": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "fps": {"type": "number", "default": 1.0},
                    "image_format": {"type": "string", "default": "png"},
                },
                "required": ["video_path", "output_dir"],
            },
        },
        {
            "name": "ffmpeg_extract_audio",
            "description": "Extract audio track from video",
            "action": "extract_audio",
            "input_schema": {
                "type": "object",
                "properties": {
                    "video_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "audio_codec": {"type": "string", "default": "pcm_s16le"},
                    "sample_rate": {"type": "integer", "default": 16000},
                },
                "required": ["video_path", "output_path"],
            },
        },
        {
            "name": "ffmpeg_concat_videos",
            "description": "Concatenate multiple video files",
            "action": "concat",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_paths": {"type": "array", "items": {"type": "string"}},
                    "output_path": {"type": "string"},
                    "reencode": {"type": "boolean", "default": False},
                },
                "required": ["input_paths", "output_path"],
            },
        },
    ]

    # --- AE tools ---
    ae_tools = [
        {
            "name": "ae_render_composition",
            "description": "Render an After Effects composition via aerender",
            "action": "render_comp",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "comp_name": {"type": "string"},
                    "output_path": {"type": "string"},
                    "output_module": {"type": "string", "default": "H.264"},
                    "render_settings": {"type": "string", "default": "Best Settings"},
                },
                "required": ["project_path", "comp_name", "output_path"],
            },
        },
        {
            "name": "ae_run_script",
            "description": "Execute an ExtendScript in After Effects",
            "action": "run_script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "script_content": {"type": "string"},
                    "project_path": {"type": "string"},
                },
                "required": ["script_content"],
            },
        },
    ]

    # --- Topaz tools ---
    topaz_tools = [
        {
            "name": "topaz_enhance_video",
            "description": "Enhance video quality using Topaz Video AI",
            "action": "enhance",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "model": {"type": "string", "default": "proteus"},
                    "scale": {"type": "number", "default": 2.0},
                    "fps": {"type": "integer"},
                    "denoise": {"type": "integer", "default": 50},
                    "deblur": {"type": "integer", "default": 30},
                },
                "required": ["input_path", "output_path"],
            },
        },
    ]

    # --- Silhouette tools ---
    silhouette_tools = [
        {
            "name": "silhouette_roto_video",
            "description": "Run auto-roto keying on video using Silhouette",
            "action": "create_roto_session",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "roto_mode": {"type": "string", "default": "foreground"},
                    "quality": {"type": "integer", "default": 60},
                    "output_format": {"type": "string", "default": "OpenEXR"},
                },
                "required": ["input_path", "output_path"],
            },
        },
        {
            "name": "silhouette_track_points",
            "description": "Track points in video using Silhouette tracker",
            "action": "run_tracker",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_path": {"type": "string"},
                    "tracker_type": {"type": "string", "default": "point"},
                    "track_points": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of {x, y} points",
                    },
                },
                "required": ["input_path", "output_path"],
            },
        },
    ]

    # --- Blender tools ---
    blender_tools = [
        {
            "name": "blender_create_stage",
            "description": "Generate a puppet theatre stage scene in Blender",
            "action": "create_puppet_stage",
            "input_schema": {
                "type": "object",
                "properties": {
                    "output_dir": {"type": "string"},
                    "style": {"type": "string", "default": "wooden"},
                    "resolution": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "default": [1920, 1080],
                    },
                    "render_engine": {"type": "string", "default": "BLENDER_EEVEE"},
                },
                "required": ["output_dir"],
            },
        },
        {
            "name": "blender_run_script",
            "description": "Run a custom Python script in Blender",
            "action": "run_script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "script_content": {"type": "string"},
                    "blend_file": {"type": "string"},
                },
                "required": ["script_content"],
            },
        },
        {
            "name": "blender_render_animation",
            "description": "Render animation from a Blender project",
            "action": "render_animation",
            "input_schema": {
                "type": "object",
                "properties": {
                    "blend_file": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "frame_start": {"type": "integer", "default": 1},
                    "frame_end": {"type": "integer", "default": 250},
                    "engine": {"type": "string", "default": "BLENDER_EEVEE"},
                },
                "required": ["blend_file", "output_dir"],
            },
        },
    ]

    # --- DaVinci Resolve tools ---
    davinci_tools = [
        {
            "name": "davinci_apply_grade",
            "description": "Apply color grading to a video clip via DaVinci Resolve",
            "action": "apply_color_grade",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "style": {"type": "string", "default": "cinematic"},
                    "grade_preset": {"type": "object"},
                    "resolution": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "default": [1920, 1080],
                    },
                },
                "required": ["input_path", "output_dir"],
            },
        },
        {
            "name": "davinci_export_lut",
            "description": "Export a grade as a .cube LUT file",
            "action": "export_lut",
            "input_schema": {
                "type": "object",
                "properties": {
                    "grade_preset": {"type": "object"},
                    "output_path": {"type": "string"},
                    "lut_size": {"type": "integer", "default": 33},
                },
                "required": ["grade_preset", "output_path"],
            },
        },
        {
            "name": "davinci_run_script",
            "description": "通过 Resolve 21.1 官方 MCP 执行 DaVinciResolveScript Python 脚本（需 Resolve 运行中）",
            "action": "run_script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "Python 脚本源码，可 import DaVinciResolveScript"},
                    "timeout": {"type": "integer", "default": 300},
                    "unsafe": {"type": "boolean", "default": False, "description": "true 时走 run_script_unsafe（无沙箱限制）"},
                },
                "required": ["script"],
            },
        },
        {
            "name": "davinci_mcp_status",
            "description": "查询官方 MCP 视角的 Resolve 运行/连接状态",
            "action": "mcp_status",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "davinci_mcp_call",
            "description": "透传调用 Resolve 21.1 官方 MCP 任意工具（launch_resolve/get_whats_new/search_scripting_api/get_scripting_api/list_luts/list_dctls/generate_lut 等）",
            "action": "call",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "description": "官方 MCP 工具名"},
                    "arguments": {"type": "object", "default": {}},
                    "timeout": {"type": "integer", "default": 120},
                },
                "required": ["tool"],
            },
        },
    ]

    # --- ComfyUI tools ---
    # ComfyUI 是基于 HTTP 的 AI 工作流引擎，提供文生图/图生图/视频生成能力
    comfyui_tools = [
        {
            "name": "comfyui_run_workflow",
            "description": "执行 ComfyUI 工作流（AI 图像/视频生成）",
            "action": "run_workflow",
            "input_schema": {
                "type": "object",
                "properties": {
                    "workflow": {
                        "type": "object",
                        "description": "ComfyUI 工作流 JSON（节点 ID -> 节点配置）",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "输出文件保存目录",
                    },
                },
                "required": ["workflow"],
            },
        },
        {
            "name": "comfyui_upload_image",
            "description": "上传图片到 ComfyUI 输入目录（用于 LoadImage 节点）",
            "action": "upload_image",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "本地图片文件路径",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "default": True,
                        "description": "是否覆盖同名文件",
                    },
                },
                "required": ["image_path"],
            },
        },
        {
            "name": "comfyui_get_status",
            "description": "查询 ComfyUI 服务器状态（可用性、系统统计、队列）",
            "action": "get_status",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]

    # --- Adobe Media Encoder tools ---
    # ME 提供平台预设编码与批量处理能力（抖音/B站/YouTube 等）
    media_encoder_tools = [
        {
            "name": "media_encoder_encode",
            "description": "使用 Adobe Media Encoder 编码视频（支持平台预设）",
            "action": "encode",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "输入视频路径"},
                    "output_path": {"type": "string", "description": "输出视频路径"},
                    "platform": {
                        "type": "string",
                        "default": "douyin",
                        "description": "平台预设（douyin/bilibili/youtube/xiaohongshu/wechat/master）",
                    },
                    "preset_file": {
                        "type": "string",
                        "description": "自定义 .epr 预设文件路径（优先于 platform）",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "default": True,
                        "description": "是否覆盖输出",
                    },
                },
                "required": ["input_path", "output_path"],
            },
        },
        {
            "name": "media_encoder_batch_encode",
            "description": "批量编码目录下所有视频到指定平台预设",
            "action": "batch_encode",
            "input_schema": {
                "type": "object",
                "properties": {
                    "input_dir": {"type": "string", "description": "输入视频目录"},
                    "output_dir": {"type": "string", "description": "输出视频目录"},
                    "platform": {
                        "type": "string",
                        "default": "douyin",
                        "description": "平台预设",
                    },
                },
                "required": ["input_dir", "output_dir"],
            },
        },
        {
            "name": "media_encoder_list_presets",
            "description": "列出所有可用的 Media Encoder 平台预设",
            "action": "list_presets",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]

    engine_tool_map = {
        "ffmpeg": ffmpeg_tools,
        "ae": ae_tools,
        "topaz": topaz_tools,
        "silhouette": silhouette_tools,
        "blender": blender_tools,
        "davinci": davinci_tools,
        "comfyui": comfyui_tools,
        "media_encoder": media_encoder_tools,
    }

    for engine_name, tool_defs in engine_tool_map.items():
        for t in tool_defs:
            tools.append(MCPTool(
                name=t["name"],
                description=t["description"],
                input_schema=t["input_schema"],
                handler=None,  # Set later via register_engine
                engine=engine_name,
                action=t["action"],
            ))

    return tools


def _build_service_tool_definitions() -> list[dict[str, Any]]:
    """Build service-layer tool definitions (resource index, plugin service, etc.)."""
    tools = []

    # --- Resource Index Service tools ---
    resource_tools = [
        {
            "name": "resource_find_font",
            "description": "在资源库中查找字体文件",
            "service": "resource_index",
            "method": "find_font",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "字体名称关键词"},
                    "exact": {"type": "boolean", "default": False, "description": "是否精确匹配"},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_find_lut",
            "description": "在资源库中查找 LUT 调色文件",
            "service": "resource_index",
            "method": "find_lut",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "LUT 名称关键词"},
                    "exact": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_find_effect_image",
            "description": "在资源库中查找特效贴图",
            "service": "resource_index",
            "method": "find_effect_image",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "特效名称关键词"},
                    "exact": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_find_audio",
            "description": "在资源库中查找音频文件",
            "service": "resource_index",
            "method": "find_audio",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "音频名称关键词"},
                    "exact": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_find_script",
            "description": "在资源库中查找 AE 脚本文件",
            "service": "resource_index",
            "method": "find_script",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "脚本名称关键词"},
                    "exact": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_find_template",
            "description": "在资源库中查找 AE 工程模板",
            "service": "resource_index",
            "method": "find_template",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "模板名称关键词"},
                    "exact": {"type": "boolean", "default": False},
                },
                "required": ["name"],
            },
        },
        {
            "name": "resource_list_by_type",
            "description": "列出资源库中指定类别的所有资源",
            "service": "resource_index",
            "method": "list_resources_by_type",
            "input_schema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "资源类别：fonts/luts/effects/psd/audio/video/projects/models/davinci/premiere/scripts/plugins/templates/images",
                    },
                    "limit": {"type": "integer", "default": 50, "description": "返回数量限制"},
                    "offset": {"type": "integer", "default": 0, "description": "偏移量"},
                },
                "required": ["category"],
            },
        },
        {
            "name": "resource_get_stats",
            "description": "获取资源库各分类统计信息",
            "service": "resource_index",
            "method": "get_index_summary",
            "input_schema": {"type": "object", "properties": {}},
        },
    ]
    tools.extend(resource_tools)

    # --- AE Plugin Service tools (high-level effect presets) ---
    plugin_tools = [
        {
            "name": "plugin_apply_saber",
            "description": "应用 Saber 光效插件到指定图层",
            "service": "ae_plugin",
            "method": "apply_saber",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "description": "AE 工程文件路径"},
                    "comp_name": {"type": "string", "description": "合成名称"},
                    "layer_name": {"type": "string", "description": "图层名称"},
                    "preset": {"type": "string", "default": "default", "description": "光效预设名称"},
                    "color_hex": {"type": "string", "default": "#00FFFF", "description": "光效颜色（十六进制）"},
                },
                "required": ["project_path", "comp_name", "layer_name"],
            },
        },
        {
            "name": "plugin_apply_particular",
            "description": "应用 Trapcode Particular 粒子插件",
            "service": "ae_plugin",
            "method": "apply_particular",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "comp_name": {"type": "string"},
                    "layer_name": {"type": "string"},
                    "preset": {"type": "string", "default": "default"},
                },
                "required": ["project_path", "comp_name", "layer_name"],
            },
        },
        {
            "name": "plugin_apply_optical_flares",
            "description": "应用 Optical Flares 镜头光晕插件",
            "service": "ae_plugin",
            "method": "apply_optical_flares",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "comp_name": {"type": "string"},
                    "layer_name": {"type": "string"},
                    "preset": {"type": "string", "default": "default"},
                },
                "required": ["project_path", "comp_name", "layer_name"],
            },
        },
        {
            "name": "plugin_apply_twitch",
            "description": "应用 Twitch 抖动闪烁效果插件",
            "service": "ae_plugin",
            "method": "apply_twitch",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_path": {"type": "string"},
                    "comp_name": {"type": "string"},
                    "layer_name": {"type": "string"},
                },
                "required": ["project_path", "comp_name", "layer_name"],
            },
        },
    ]
    tools.extend(plugin_tools)

    # --- Config tools ---
    config_tools = [
        {
            "name": "config_get_settings",
            "description": "获取当前配置信息（脱敏）",
            "service": "config",
            "method": "get_safe_config",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "config_get_paths",
            "description": "获取所有资源路径配置",
            "service": "config",
            "method": "get_resource_paths",
            "input_schema": {"type": "object", "properties": {}},
        },
    ]
    tools.extend(config_tools)

    return tools


def initialize_gateway(engines: dict[str, Any], services: dict[str, Any] | None = None) -> MCPRegistry:
    """Initialize MCP gateway with all registered engines and services.

    Args:
        engines: Dict of engine_name -> engine_instance
        services: Dict of service_name -> service_instance (optional, for service-layer tools)

    Returns:
        Populated MCPRegistry (global singleton)
    """
    global mcp_registry
    services = services or {}
    mcp_registry = MCPRegistry()
    tool_defs = _build_tool_definitions()

    for name, instance in engines.items():
        mcp_registry.register_engine(name, instance)

    for tool in tool_defs:
        engine = mcp_registry.engines.get(tool.engine)
        if engine is None:
            logger.debug(f"MCP: Skipping tool [{tool.name}] - engine not available")
            continue

        def make_handler(engine_instance, action_name):
            async def handler(**kwargs):
                return await engine_instance.execute(action=action_name, **kwargs)
            return handler

        tool.handler = make_handler(engine, tool.action)
        mcp_registry.register_tool(tool)

    service_tools = _build_service_tool_definitions()
    for tool_def in service_tools:
        svc_name = tool_def.get("service", "")
        svc = services.get(svc_name)
        if svc is None:
            logger.debug(f"MCP: Skipping service tool [{tool_def['name']}] - service '{svc_name}' not available")
            continue

        def make_svc_handler(service_instance, method_name):
            import asyncio

            async def handler(**kwargs):
                method = getattr(service_instance, method_name, None)
                if method is None:
                    return EngineResult(success=False, error=f"Method {method_name} not found")
                try:
                    if asyncio.iscoroutinefunction(method):
                        result = await method(**kwargs)
                    else:
                        result = await asyncio.to_thread(method, **kwargs)
                    if isinstance(result, EngineResult):
                        return result
                    return EngineResult(success=True, metadata={"result": result})
                except Exception as e:
                    logger.error(f"Service tool error: {e}")
                    return EngineResult(success=False, error=str(e))
            return handler

        tool = MCPTool(
            name=tool_def["name"],
            description=tool_def["description"],
            input_schema=tool_def["input_schema"],
            handler=make_svc_handler(svc, tool_def["method"]),
            engine=svc_name,
            action=tool_def["method"],
        )
        mcp_registry.register_tool(tool)

    logger.info(f"MCP Gateway initialized with {len(mcp_registry.tools)} tools ({len(engines)} engines, {len(services)} services)")
    return mcp_registry


# ============================================================
# API Router
# ============================================================

mcp_router = APIRouter(prefix="/mcp", tags=["MCP Gateway"])


@mcp_router.get("/tools")
async def list_mcp_tools(
    _auth: bool = Depends(_validate_token),
) -> dict[str, Any]:
    """List all available MCP tools."""
    return {"tools": mcp_registry.list_tools()}


@mcp_router.post("/tools/{tool_name}/call")
async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any] = {},
    _auth: bool = Depends(_validate_token),
) -> dict[str, Any]:
    """Call an MCP tool with arguments."""
    if tool_name not in mcp_registry.tools:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    return await mcp_registry.call_tool(tool_name, arguments)


@mcp_router.post("/invoke")
async def invoke_mcp(
    request: dict[str, Any],
    _auth: bool = Depends(_validate_token),
) -> dict[str, Any]:
    """MCP-style invoke endpoint (JSON-RPC style).

    Request body:
    {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "tool_name",
            "arguments": {...}
        }
    }
    """
    method = request.get("method", "")
    req_id = request.get("id", None)

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": mcp_registry.list_tools()},
        }

    if method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        try:
            result = await mcp_registry.call_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
        except KeyError as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)},
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method '{method}' not found"},
    }


@mcp_router.get("/engines")
async def list_mcp_engines(
    _auth: bool = Depends(_validate_token),
) -> dict[str, Any]:
    """List registered engines and their availability."""
    engine_info = {}
    for name, engine in mcp_registry.engines.items():
        engine_info[name] = {
            "available": engine.executable_path.exists() if hasattr(engine, "executable_path") else True,
            "tools": [
                t.name for t in mcp_registry.tools.values() if t.engine == name
            ],
        }
    return {"engines": engine_info}


@mcp_router.get("/health")
async def mcp_health() -> dict[str, Any]:
    """MCP gateway health check."""
    return {
        "status": "ok",
        "tools_count": len(mcp_registry.tools),
        "engines_count": len(mcp_registry.engines),
    }
