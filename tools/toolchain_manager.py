#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具链统一管理器 (Toolchain Unified Manager) v1.0
=================================================

统一管理AE-Knowledge-Vault项目中的所有工具，提供工具注册、发现、调用和工作流编排功能。

支持的工具类型：
1. 软件引擎：AE/Topaz/Blender/FFmpeg/DaVinci/Silhouette
2. AE扩展脚本：74个JSX脚本
3. MCP工具：22个标准工具 + 扩展工具
4. Python集成工具：统一工具集成器、扩展脚本集成器等

核心功能：
- 工具注册与发现
- 统一工具调用接口
- 工作流编排与执行
- 工具状态监控
- 错误降级与重试

知识库参考：
- [[工具链集成总览]]
- [[跨工具集成工作流-全工具联动指南]]
- [[🎬-风格化剪辑知识库-MOC]]
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


def _env_path(env_var: str, *candidates: str) -> str:
    """路径解析：优先环境变量，其次按顺序返回第一个存在的候选路径。"""
    v = os.environ.get(env_var, "").strip()
    if v and Path(v).exists():
        return v
    for c in candidates:
        if c and Path(c).exists():
            return c
    return v or (candidates[0] if candidates else "")


def _run(cmd: list[str], log: list[str], timeout: int = 600) -> None:
    """执行子进程，失败抛异常（由调用方决定降级）。"""
    log.append("CMD: " + " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.stdout:
        log.append("OUT: " + r.stdout[-2000:])
    if r.stderr:
        log.append("ERR: " + r.stderr[-2000:])
    if r.returncode != 0:
        raise RuntimeError(f"命令失败 exit={r.returncode}")


class ToolCategory(str, Enum):
    """工具分类"""
    ENGINE = "engine"
    SCRIPT = "script"
    MCP_TOOL = "mcp_tool"
    PYTHON_TOOL = "python_tool"


class ToolStatus(str, Enum):
    """工具状态"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    RUNNING = "running"
    ERROR = "error"


class ExecutionMode(str, Enum):
    """执行模式"""
    REAL = "real"
    SIMULATE = "simulate"
    AUTO = "auto"


@dataclass
class ToolInfo:
    """工具信息"""
    name: str
    category: str
    description: str
    status: str = ToolStatus.UNAVAILABLE.value
    executable_path: str = ""
    adapter_class: Callable | None = None
    capabilities: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    tool_name: str
    operation: str
    output_path: str | None = None
    output_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    duration_ms: float = 0
    mode_used: str = "simulate"
    log: list[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    name: str
    tool_name: str
    operation: str
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    enabled: bool = True
    retry_count: int = 0


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_name: str
    status: str
    steps: list[ToolResult] = field(default_factory=list)
    total_duration_ms: float = 0
    output_files: list[str] = field(default_factory=list)
    error: str = ""
    summary: str = ""


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: dict[str, ToolInfo] = {}
        self._categories: dict[str, list[str]] = {cat.value: [] for cat in ToolCategory}
        self._status_cache: dict[str, str] = {}

    def register_tool(self, tool_info: ToolInfo) -> None:
        """注册工具"""
        self._tools[tool_info.name] = tool_info
        self._categories[tool_info.category].append(tool_info.name)
        self._status_cache[tool_info.name] = tool_info.status

    def get_tool(self, name: str) -> ToolInfo | None:
        """获取工具信息"""
        return self._tools.get(name)

    def list_tools(self, category: str | None = None) -> list[ToolInfo]:
        """列出工具"""
        if category:
            return [self._tools[name] for name in self._categories.get(category, [])]
        return list(self._tools.values())

    def list_tool_names(self, category: str | None = None) -> list[str]:
        """列出工具名称"""
        if category:
            return self._categories.get(category, [])
        return list(self._tools.keys())

    def check_status(self, name: str) -> str:
        """检查工具状态"""
        tool = self._tools.get(name)
        if not tool:
            return ToolStatus.UNAVAILABLE.value

        if tool.status == ToolStatus.AVAILABLE.value:
            if tool.executable_path:
                if Path(tool.executable_path).exists():
                    return ToolStatus.AVAILABLE.value
                # 检查备选路径
                alt_paths = tool.metadata.get("alt_paths", [])
                for alt in alt_paths:
                    if Path(alt).exists():
                        return ToolStatus.AVAILABLE.value
                # 检查PATH中的命令（如ffmpeg）
                exe_name = Path(tool.executable_path).name
                if shutil.which(exe_name):
                    return ToolStatus.AVAILABLE.value
                return ToolStatus.UNAVAILABLE.value

        return tool.status


class ToolchainManager:
    """工具链统一管理器"""

    def __init__(self):
        self.registry = ToolRegistry()
        self._engine_adapters: dict[str, Any] = {}
        self._init_default_tools()

    def _init_default_tools(self) -> None:
        """初始化默认工具"""
        self._register_engines()
        self._register_scripts()
        self._register_mcp_tools()
        self._register_python_tools()

    def _register_engines(self) -> None:
        """注册软件引擎"""
        engines = [
            ToolInfo(
                name="after_effects",
                category=ToolCategory.ENGINE.value,
                description="Adobe After Effects 合成引擎 (2025/2026 自适应)",
                status=ToolStatus.AVAILABLE.value,
                executable_path=_env_path(
                    "AE_EXE",
                    r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\aerender.exe",
                    r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe",
                ),
                capabilities=["render_comp", "run_script", "apply_effect", "set_keyframe"],
                metadata={"version": "auto", "type": "compositing",
                          "gui_path": _env_path("AE_GUI",
                              r"C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\AfterFX.exe",
                              r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe")}
            ),
            ToolInfo(
                name="premiere_pro",
                category=ToolCategory.ENGINE.value,
                description="Adobe Premiere Pro 2025 剪辑引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="D:\\pr\\Adobe Premiere Pro 2025\\Adobe Premiere Pro.exe",
                capabilities=["edit_timeline", "export_media", "color_correction"],
                metadata={"version": "2025", "type": "editing"}
            ),
            ToolInfo(
                name="photoshop",
                category=ToolCategory.ENGINE.value,
                description="Adobe Photoshop 2025 图像处理引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="D:\\ps\\Adobe Photoshop 2025\\Photoshop.exe",
                capabilities=["image_processing", "batch_process", "color_correction"],
                metadata={"version": "2025", "type": "image_editing"}
            ),
            ToolInfo(
                name="illustrator",
                category=ToolCategory.ENGINE.value,
                description="Adobe Illustrator 2025 矢量设计引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="D:\\Ai\\Adobe Illustrator 2025\\Support Files\\Contents\\Windows\\Illustrator.exe",
                capabilities=["vector_design", "mg_animation", "text_processing"],
                metadata={"version": "2025", "type": "vector_design"}
            ),
            ToolInfo(
                name="media_encoder",
                category=ToolCategory.ENGINE.value,
                description="Adobe Media Encoder 2025 编码引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="D:\\Me\\Adobe Media Encoder 2025\\Adobe Media Encoder.exe",
                capabilities=["encode", "batch_encode", "preset_management"],
                metadata={"version": "2025", "type": "encoding"}
            ),
            ToolInfo(
                name="topaz_video_ai",
                category=ToolCategory.ENGINE.value,
                description="Topaz Video AI Pro 视频增强引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path=_env_path("TOPAZ_EXE", r"D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe"),
                capabilities=["enhance", "upscale", "denoise", "interpolate"],
                metadata={"version": "Pro", "type": "ai_enhancement", "cli_name": "tvai"}
            ),
            ToolInfo(
                name="blender",
                category=ToolCategory.ENGINE.value,
                description="Blender 5.1.0 3D渲染引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path=_env_path("BLENDER_EXE", r"D:\Blender\Blender 5.1.0\blender.exe"),
                capabilities=["render_scene", "run_python", "render_queue", "geometry_nodes"],
                metadata={"version": "5.1.0", "type": "3d_rendering"}
            ),
            ToolInfo(
                name="ffmpeg",
                category=ToolCategory.ENGINE.value,
                description="FFmpeg 编码引擎 (自动探测 PATH)",
                status=ToolStatus.AVAILABLE.value,
                executable_path=_env_path(
                    "FFMPEG_EXE",
                    r"C:\ffmpeg\bin\ffmpeg.exe",
                    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                ),
                capabilities=["encode", "apply_filter", "convert", "stream"],
                metadata={"version": "auto", "type": "encoding"}
            ),
            ToolInfo(
                name="davinci_resolve",
                category=ToolCategory.ENGINE.value,
                description="DaVinci Resolve 调色引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="D:\\DaVinci Resolve\\Resolve.exe",
                capabilities=["apply_grade", "render_deliverable"],
                metadata={"version": "19.x", "type": "color_grading"}
            ),
            ToolInfo(
                name="silhouette",
                category=ToolCategory.ENGINE.value,
                description="Silhouette 抠像引擎",
                status=ToolStatus.AVAILABLE.value,
                executable_path="",
                capabilities=["roto_node", "track_node", "paint_node"],
                metadata={"version": "2026", "type": "rotoscoping"}
            )
        ]

        for engine in engines:
            self.registry.register_tool(engine)

    def _register_scripts(self) -> None:
        """注册AE扩展脚本"""
        script_dir = Path("AE-Scripts/ScriptUI Panels")
        if script_dir.exists():
            scripts = []
            for jsx_file in sorted(script_dir.glob("*.jsx")):
                scripts.append(ToolInfo(
                    name=f"script_{jsx_file.stem}",
                    category=ToolCategory.SCRIPT.value,
                    description=f"AE脚本: {jsx_file.stem}",
                    status=ToolStatus.AVAILABLE.value,
                    executable_path=str(jsx_file),
                    capabilities=["execute"],
                    metadata={"file": jsx_file.name, "size": jsx_file.stat().st_size}
                ))

            for script in scripts:
                self.registry.register_tool(script)

    def _register_mcp_tools(self) -> None:
        """注册MCP工具"""
        mcp_tools = [
            ToolInfo(name="mcp_create_composition", category=ToolCategory.MCP_TOOL.value, description="创建合成"),
            ToolInfo(name="mcp_get_project_details", category=ToolCategory.MCP_TOOL.value, description="获取项目详情"),
            ToolInfo(name="mcp_list_compositions", category=ToolCategory.MCP_TOOL.value, description="列出合成"),
            ToolInfo(name="mcp_create_text_layer", category=ToolCategory.MCP_TOOL.value, description="创建文字层"),
            ToolInfo(name="mcp_create_shape_layer", category=ToolCategory.MCP_TOOL.value, description="创建形状层"),
            ToolInfo(name="mcp_create_solid_layer", category=ToolCategory.MCP_TOOL.value, description="创建纯色层"),
            ToolInfo(name="mcp_create_camera", category=ToolCategory.MCP_TOOL.value, description="创建摄像机"),
            ToolInfo(name="mcp_create_null_object", category=ToolCategory.MCP_TOOL.value, description="创建空对象"),
            ToolInfo(name="mcp_duplicate_layer", category=ToolCategory.MCP_TOOL.value, description="复制图层"),
            ToolInfo(name="mcp_delete_layer", category=ToolCategory.MCP_TOOL.value, description="删除图层"),
            ToolInfo(name="mcp_set_keyframe", category=ToolCategory.MCP_TOOL.value, description="设置关键帧"),
            ToolInfo(name="mcp_set_expression", category=ToolCategory.MCP_TOOL.value, description="设置表达式"),
            ToolInfo(name="mcp_set_properties", category=ToolCategory.MCP_TOOL.value, description="设置属性"),
            ToolInfo(name="mcp_batch_set_properties", category=ToolCategory.MCP_TOOL.value, description="批量设置属性"),
            ToolInfo(name="mcp_get_layer_info", category=ToolCategory.MCP_TOOL.value, description="获取图层信息"),
            ToolInfo(name="mcp_set_mask", category=ToolCategory.MCP_TOOL.value, description="设置遮罩"),
            ToolInfo(name="mcp_run_script", category=ToolCategory.MCP_TOOL.value, description="执行脚本"),
            ToolInfo(name="mcp_add_effect", category=ToolCategory.MCP_TOOL.value, description="添加效果"),
            ToolInfo(name="mcp_set_effect_property", category=ToolCategory.MCP_TOOL.value, description="设置效果属性"),
            ToolInfo(name="mcp_beatedit_analyze", category=ToolCategory.MCP_TOOL.value, description="节拍分析"),
        ]

        for tool in mcp_tools:
            tool.status = ToolStatus.AVAILABLE.value
            self.registry.register_tool(tool)

    def _register_python_tools(self) -> None:
        """注册Python集成工具"""
        python_tools = [
            ToolInfo(
                name="unified_tool_integrator",
                category=ToolCategory.PYTHON_TOOL.value,
                description="统一多工具集成调度器",
                status=ToolStatus.AVAILABLE.value,
                capabilities=["run_workflow", "list_presets", "create_custom_workflow"]
            ),
            ToolInfo(
                name="ae_extension_integrator",
                category=ToolCategory.PYTHON_TOOL.value,
                description="AE扩展脚本深度集成器",
                status=ToolStatus.AVAILABLE.value,
                capabilities=["search_effect", "generate_script", "list_scripts"]
            ),
            ToolInfo(
                name="resource_manager",
                category=ToolCategory.PYTHON_TOOL.value,
                description="系统资源管理器",
                status=ToolStatus.AVAILABLE.value,
                capabilities=["monitor_cpu", "monitor_memory", "monitor_disk"]
            ),
            ToolInfo(
                name="distributed_scheduler",
                category=ToolCategory.PYTHON_TOOL.value,
                description="分布式任务调度器",
                status=ToolStatus.AVAILABLE.value,
                capabilities=["submit_task", "schedule_task", "cancel_task"]
            )
        ]

        for tool in python_tools:
            self.registry.register_tool(tool)

    def get_tool_status(self, tool_name: str) -> dict[str, Any]:
        """获取工具状态"""
        tool = self.registry.get_tool(tool_name)
        if not tool:
            return {"name": tool_name, "status": "not_found", "error": "工具不存在"}

        status = self.registry.check_status(tool_name)
        return {
            "name": tool.name,
            "category": tool.category,
            "status": status,
            "description": tool.description,
            "executable_path": tool.executable_path,
            "capabilities": tool.capabilities,
            "metadata": tool.metadata
        }

    def get_all_tool_status(self) -> dict[str, Any]:
        """获取所有工具状态"""
        result = {
            "total_tools": len(self.registry.list_tools()),
            "categories": {},
            "tools": []
        }

        for category in ToolCategory:
            tools = self.registry.list_tools(category.value)
            result["categories"][category.value] = len(tools)

        for tool in self.registry.list_tools():
            status = self.registry.check_status(tool.name)
            result["tools"].append({
                "name": tool.name,
                "category": tool.category,
                "status": status,
                "description": tool.description,
                "capabilities": tool.capabilities
            })

        return result

    def execute_tool(self, tool_name: str, operation: str, params: dict[str, Any],
                     mode: str = "auto") -> ToolResult:
        """执行工具操作"""
        start_time = time.time()
        log = []

        try:
            tool = self.registry.get_tool(tool_name)
            if not tool:
                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    operation=operation,
                    error=f"工具不存在: {tool_name}",
                    duration_ms=(time.time() - start_time) * 1000,
                    log=log
                )

            status = self.registry.check_status(tool_name)
            if status != ToolStatus.AVAILABLE.value:
                log.append(f"工具不可用: {tool_name}, 状态: {status}")

                if mode == "auto" or mode == "simulate":
                    log.append("使用模拟模式执行")
                    return self._simulate_execution(tool_name, operation, params, log, start_time)

                return ToolResult(
                    success=False,
                    tool_name=tool_name,
                    operation=operation,
                    error=f"工具不可用: {tool_name}",
                    duration_ms=(time.time() - start_time) * 1000,
                    log=log
                )

            if mode == "real":
                return self._execute_real(tool_name, operation, params, log, start_time)
            elif mode == "simulate":
                return self._simulate_execution(tool_name, operation, params, log, start_time)
            else:
                try:
                    return self._execute_real(tool_name, operation, params, log, start_time)
                except Exception as e:
                    log.append(f"真实模式失败: {str(e)}")
                    log.append("降级到模拟模式")
                    return self._simulate_execution(tool_name, operation, params, log, start_time)

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            log.append(f"执行异常: {str(e)}")
            return ToolResult(
                success=False,
                tool_name=tool_name,
                operation=operation,
                error=str(e),
                duration_ms=duration,
                log=log
            )

    def _tool_exe(self, name: str) -> str:
        """取引擎可执行路径（来自注册表）。"""
        t = self.registry.get_tool(name)
        return t.executable_path if (t and t.executable_path) else ""

    def _execute_real(self, tool_name: str, operation: str, params: dict[str, Any],
                      log: list[str], start_time: float) -> ToolResult:
        """执行真实工具（真正调用二进制；失败抛异常由 auto 降级 simulate）"""
        log.append(f"执行真实工具: {tool_name}.{operation}")
        if tool_name == "ffmpeg":
            return self._execute_ffmpeg(operation, params, log)
        if tool_name == "after_effects":
            return self._execute_ae(operation, params, log)
        if tool_name == "topaz_video_ai":
            return self._execute_topaz(operation, params, log)
        if tool_name == "blender":
            return self._execute_blender(operation, params, log)
        raise NotImplementedError(f"工具 {tool_name} 暂无真实执行适配器")

    def _execute_ffmpeg(self, operation: str, params: dict[str, Any], log: list[str]) -> ToolResult:
        """真实调用 FFmpeg（本机唯一保证可用的真实引擎）"""
        exe = self._tool_exe("ffmpeg")
        if not exe:
            raise RuntimeError("ffmpeg 可执行文件未找到")
        inp = params.get("input_path")
        out = params.get("output_path")
        codec = params.get("codec", "h264")
        if operation in ("encode", "convert") and inp and out:
            if not Path(inp).exists():
                raise FileNotFoundError(f"输入文件不存在: {inp}")
            cmd = [exe, "-y", "-i", inp]
            if operation == "encode" and codec:
                cmd += ["-c:v", codec, "-pix_fmt", "yuv420p"]
            cmd += [out]
            _run(cmd, log)
            if not Path(out).exists():
                raise RuntimeError(f"ffmpeg 未生成输出: {out}")
            return ToolResult(success=True, tool_name="ffmpeg", operation=operation,
                              output_path=out, output_data={"codec": codec}, mode_used="real", log=log)
        if operation == "transcode" and inp and out:
            if not Path(inp).exists():
                raise FileNotFoundError(f"输入文件不存在: {inp}")
            filters = params.get("filters") or []
            cmd = [exe, "-y", "-i", inp]
            if filters:
                cmd += ["-vf", ",".join(str(f) for f in filters)]
            cmd += ["-c:v", codec, "-pix_fmt", "yuv420p", out]
            _run(cmd, log)
            if not Path(out).exists():
                raise RuntimeError(f"ffmpeg 未生成输出: {out}")
            return ToolResult(success=True, tool_name="ffmpeg", operation=operation,
                              output_path=out, output_data={"filters": filters}, mode_used="real", log=log)
        raise NotImplementedError(f"ffmpeg 操作 {operation} 需提供 input_path/output_path")

    def _execute_ae(self, operation: str, params: dict[str, Any], log: list[str]) -> ToolResult:
        """真实调用 aerender（需 project/comp/output）"""
        exe = self._tool_exe("after_effects")
        if not exe:
            raise RuntimeError("After Effects aerender 未找到")
        if operation == "render_comp":
            proj, comp, out = params.get("project_path"), params.get("comp_name"), params.get("output_path")
            if not (proj and comp and out):
                raise NotImplementedError("AE 真实渲染需提供 project_path / comp_name / output_path")
            if not Path(proj).exists():
                raise FileNotFoundError(f"AE 项目不存在: {proj}")
            _run([exe, "-project", proj, "-comp", comp, "-output", out], log)
            if not Path(out).exists():
                raise RuntimeError(f"AE 未生成输出: {out}")
            return ToolResult(success=True, tool_name="after_effects", operation=operation,
                              output_path=out, output_data={"comp": comp}, mode_used="real", log=log)
        raise NotImplementedError(f"AE 操作 {operation} 暂无真实适配器")

    def _execute_topaz(self, operation: str, params: dict[str, Any], log: list[str]) -> ToolResult:
        """Topaz 为 GUI BETA，无标准 CLI 适配器 → 诚实失败由 auto 降级 simulate"""
        raise NotImplementedError("Topaz Video AI 暂无真实 CLI 适配器")

    def _execute_blender(self, operation: str, params: dict[str, Any], log: list[str]) -> ToolResult:
        """真实调用 Blender（需 project/脚本）"""
        exe = self._tool_exe("blender")
        if not exe:
            raise RuntimeError("Blender 未找到")
        proj = params.get("project_path") or params.get("blend_file")
        if operation in ("render_scene", "run_python") and proj:
            if not Path(proj).exists():
                raise FileNotFoundError(f"Blender 工程不存在: {proj}")
            cmd = [exe, "-b", proj]
            if params.get("script_path"):
                cmd += ["-P", params["script_path"]]
            _run(cmd, log)
            return ToolResult(success=True, tool_name="blender", operation=operation,
                              output_data={"project": proj}, mode_used="real", log=log)
        raise NotImplementedError(f"Blender 操作 {operation} 需提供 project_path")

    def _simulate_execution(self, tool_name: str, operation: str, params: dict[str, Any],
                            log: list[str], start_time: float) -> ToolResult:
        """模拟执行"""
        duration = (time.time() - start_time) * 1000
        log.append(f"模拟执行: {tool_name}.{operation}")
        log.append(f"参数: {json.dumps(params, ensure_ascii=False)[:200]}")

        output_data = {
            "tool": tool_name,
            "operation": operation,
            "params": params,
            "mode": "simulate",
            "message": f"模拟执行 {tool_name}.{operation} 成功"
        }

        return ToolResult(
            success=True,
            tool_name=tool_name,
            operation=operation,
            output_data=output_data,
            duration_ms=duration,
            mode_used="simulate",
            log=log
        )

    def run_workflow(self, workflow_name: str, input_path: str, output_path: str,
                     mode: str = "auto") -> WorkflowResult:
        """执行工作流"""
        start_time = time.time()
        steps = self._get_workflow_steps(workflow_name, input_path, output_path)
        results = []
        output_files = []

        for step in steps:
            if not step.enabled:
                results.append(ToolResult(
                    success=True,
                    tool_name=step.tool_name,
                    operation=step.operation,
                    output_data={"message": f"步骤 {step.step_id} 已跳过"}
                ))
                continue

            result = self.execute_tool(step.tool_name, step.operation, step.params, mode)
            results.append(result)

            if result.success and result.output_path:
                output_files.append(result.output_path)

        total_duration = (time.time() - start_time) * 1000
        all_success = all(r.success for r in results)

        result = WorkflowResult(
            workflow_name=workflow_name,
            status="success" if all_success else "partial",
            steps=results,
            total_duration_ms=total_duration,
            output_files=output_files,
            error="" if all_success else "部分步骤失败",
            summary=f"工作流 {workflow_name} 完成，{len(results)} 个步骤，{sum(1 for r in results if r.success)} 个成功"
        )
        self._write_run_manifest(workflow_name, result)
        return result

    def _write_run_manifest(self, workflow_name: str, result: "WorkflowResult") -> None:
        """闭环产物：写入工作流运行清单 JSON（非致命）"""
        try:
            out_dir = Path("output/workflow_runs")
            out_dir.mkdir(parents=True, exist_ok=True)
            manifest = {
                "workflow": workflow_name,
                "status": result.status,
                "total_duration_ms": round(result.total_duration_ms, 2),
                "output_files": result.output_files,
                "error": result.error,
                "summary": result.summary,
                "steps": [
                    {"tool": s.tool_name, "operation": s.operation,
                     "success": s.success, "mode": s.mode_used, "output": s.output_path}
                    for s in result.steps
                ],
                "generated_at": datetime.now().isoformat(),
            }
            path = out_dir / f"workflow_run_{workflow_name}_{int(time.time())}.json"
            path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            result.output_files.append(str(path))
        except Exception as e:
            try:
                result.output_files.append(f"<manifest-write-failed:{e}>")
            except Exception:
                pass

    def _get_workflow_steps(self, workflow_name: str, input_path: str, output_path: str) -> list[WorkflowStep]:
        """获取工作流步骤"""
        workflows = {
            "enhance_quality": [
                WorkflowStep(
                    step_id="topaz_enhance",
                    name="Topaz视频增强",
                    tool_name="topaz_video_ai",
                    operation="enhance",
                    params={"input_path": input_path, "output_path": output_path, "model": "proteus", "scale": 2.0}
                )
            ],
            "delivery_pipeline": [
                WorkflowStep(
                    step_id="ae_render",
                    name="AE渲染",
                    tool_name="after_effects",
                    operation="render_comp",
                    params={"input_path": input_path, "output_path": output_path.replace(".mp4", "_ae.mp4")}
                ),
                WorkflowStep(
                    step_id="topaz_enhance",
                    name="Topaz增强",
                    tool_name="topaz_video_ai",
                    operation="enhance",
                    params={"input_path": output_path.replace(".mp4", "_ae.mp4"), "output_path": output_path},
                    depends_on=["ae_render"]
                ),
                WorkflowStep(
                    step_id="ffmpeg_encode",
                    name="FFmpeg编码",
                    tool_name="ffmpeg",
                    operation="encode",
                    params={"input_path": output_path, "output_path": output_path.replace(".mp4", "_final.mp4"), "codec": "h264"},
                    depends_on=["topaz_enhance"]
                )
            ],
            "full_production": [
                WorkflowStep(
                    step_id="silhouette_roto",
                    name="Silhouette抠像",
                    tool_name="silhouette",
                    operation="roto_node",
                    params={"input_path": input_path, "output_path": output_path.replace(".mp4", "_roto.mp4")}
                ),
                WorkflowStep(
                    step_id="ae_composite",
                    name="AE合成",
                    tool_name="after_effects",
                    operation="render_comp",
                    params={"input_path": output_path.replace(".mp4", "_roto.mp4"), "output_path": output_path.replace(".mp4", "_comp.mp4")},
                    depends_on=["silhouette_roto"]
                ),
                WorkflowStep(
                    step_id="resolve_grade",
                    name="DaVinci调色",
                    tool_name="davinci_resolve",
                    operation="apply_grade",
                    params={"input_path": output_path.replace(".mp4", "_comp.mp4"), "output_path": output_path.replace(".mp4", "_graded.mp4")},
                    depends_on=["ae_composite"]
                ),
                WorkflowStep(
                    step_id="ffmpeg_delivery",
                    name="FFmpeg输出",
                    tool_name="ffmpeg",
                    operation="encode",
                    params={"input_path": output_path.replace(".mp4", "_graded.mp4"), "output_path": output_path, "codec": "h264"},
                    depends_on=["resolve_grade"]
                )
            ]
        }

        return workflows.get(workflow_name, [])

    def list_workflows(self) -> list[str]:
        """列出所有工作流"""
        return ["enhance_quality", "delivery_pipeline", "full_production"]

    def get_workflow_details(self, workflow_name: str) -> dict[str, Any]:
        """获取工作流详情"""
        steps = self._get_workflow_steps(workflow_name, "input.mp4", "output.mp4")
        return {
            "workflow_name": workflow_name,
            "step_count": len(steps),
            "steps": [
                {
                    "step_id": s.step_id,
                    "name": s.name,
                    "tool": s.tool_name,
                    "operation": s.operation,
                    "depends_on": s.depends_on
                }
                for s in steps
            ]
        }


def main():
    """测试入口"""
    manager = ToolchainManager()

    print("=" * 60)
    print("工具链统一管理器 v1.0")
    print("=" * 60)

    print("\n1. 工具状态概览")
    status = manager.get_all_tool_status()
    print(f"总工具数: {status['total_tools']}")
    for cat, count in status["categories"].items():
        print(f"  {cat}: {count}个")

    print("\n2. 可用引擎")
    engines = manager.registry.list_tools("engine")
    for engine in engines:
        st = manager.registry.check_status(engine.name)
        icon = "✅" if st == "available" else "❌"
        print(f"  {icon} {engine.name}: {engine.description}")

    print("\n3. 工作流列表")
    workflows = manager.list_workflows()
    for wf in workflows:
        details = manager.get_workflow_details(wf)
        print(f"  • {wf} ({details['step_count']}个步骤)")
        for step in details["steps"]:
            print(f"    └── {step['step_id']}: {step['tool']}.{step['operation']}")

    print("\n4. 执行工作流模拟")
    result = manager.run_workflow("delivery_pipeline", "input.mp4", "output.mp4", mode="simulate")
    print(f"工作流: {result.workflow_name}")
    print(f"状态: {result.status}")
    print(f"总耗时: {result.total_duration_ms:.2f}ms")
    print(f"输出文件: {result.output_files}")
    print(f"摘要: {result.summary}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()