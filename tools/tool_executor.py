#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具执行引擎 - 模型驱动的工具调用系统
=====================================

核心功能：
1. 将工具链注册为 V4 Function Calling 格式
2. 模型分析 → 选择工具 → 执行 → 反馈闭环
3. 支持 Trae 任务中的工具命令执行

设计原则：
- 效果优先：使用 V4-Pro 进行工具选择和推理
- 安全执行：所有命令经过签名验证
- 状态追踪：记录每次工具调用的结果
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

sys.path.insert(0, str(Path(__file__).parent))

try:
    from ai_agent import V4Agent
    V4_AVAILABLE = True
except ImportError:
    V4_AVAILABLE = False

try:
    from model_router import TaskCategory, select_model
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False


class ToolType(Enum):
    """工具类型"""
    ENGINE = "engine"
    MCP = "mcp"
    SCRIPT = "script"
    COMMAND = "command"


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ToolDefinition:
    """工具定义（V4 Function Calling 格式）"""
    name: str
    description: str
    type: ToolType
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    handler: Callable | None = None
    engine_name: str = ""
    action: str = ""
    executable: str = ""
    arguments: list[str] = field(default_factory=list)
    
    def to_v4_tool(self) -> dict[str, Any]:
        """转换为 V4 Function Calling 工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            }
        }


@dataclass
class ToolCallResult:
    """工具调用结果"""
    tool_name: str
    status: ExecutionStatus
    output: str | None = None
    error: str = ""
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration": self.duration,
            "metadata": self.metadata,
        }


class ToolExecutor:
    """工具执行引擎"""
    
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._v4_agent: V4Agent | None = None
        self._call_history: list[ToolCallResult] = []
        self._load_builtin_tools()
    
    @property
    def tools(self) -> dict[str, ToolDefinition]:
        return self._tools
    
    @property
    def call_history(self) -> list[ToolCallResult]:
        return self._call_history
    
    def _load_builtin_tools(self):
        """加载内置工具"""
        builtin_tools = [
            ToolDefinition(
                name="ffmpeg_transcode",
                description="使用FFmpeg转码视频文件，支持格式转换、分辨率调整、编码设置",
                type=ToolType.COMMAND,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "输入视频文件路径"},
                        "output_path": {"type": "string", "description": "输出视频文件路径"},
                        "codec": {"type": "string", "description": "视频编码格式，如libx264、libx265"},
                        "resolution": {"type": "string", "description": "输出分辨率，如1920x1080"},
                        "fps": {"type": "number", "description": "帧率"},
                    },
                    "required": ["input_path", "output_path"],
                },
                executable="ffmpeg",
            ),
            ToolDefinition(
                name="ffmpeg_extract_audio",
                description="从视频中提取音频",
                type=ToolType.COMMAND,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "输入视频文件路径"},
                        "output_path": {"type": "string", "description": "输出音频文件路径"},
                        "format": {"type": "string", "description": "音频格式，如mp3、wav"},
                    },
                    "required": ["input_path", "output_path"],
                },
                executable="ffmpeg",
            ),
            ToolDefinition(
                name="ffmpeg_extract_frames",
                description="从视频中提取关键帧图片",
                type=ToolType.COMMAND,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "输入视频文件路径"},
                        "output_dir": {"type": "string", "description": "输出目录"},
                        "interval": {"type": "number", "description": "提取间隔（秒）"},
                        "count": {"type": "number", "description": "提取帧数"},
                    },
                    "required": ["input_path", "output_dir"],
                },
                executable="ffmpeg",
            ),
            ToolDefinition(
                name="topaz_enhance",
                description="使用Topaz Video AI增强视频画质，支持超分、降噪、增稳",
                type=ToolType.ENGINE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "输入视频文件路径"},
                        "output_path": {"type": "string", "description": "输出视频文件路径"},
                        "model": {"type": "string", "description": "AI模型，如aion-4、proteus"},
                        "upscale": {"type": "number", "description": "超分倍数，如2"},
                        "denoise": {"type": "number", "description": "降噪强度0-1"},
                        "stabilize": {"type": "boolean", "description": "是否增稳"},
                    },
                    "required": ["input_path", "output_path"],
                },
                engine_name="topaz_video_ai",
                action="enhance",
            ),
            ToolDefinition(
                name="ae_create_composition",
                description="在After Effects中创建合成",
                type=ToolType.MCP,
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "合成名称"},
                        "width": {"type": "number", "description": "宽度（像素）"},
                        "height": {"type": "number", "description": "高度（像素）"},
                        "duration": {"type": "number", "description": "时长（秒）"},
                        "fps": {"type": "number", "description": "帧率"},
                    },
                    "required": ["name", "width", "height"],
                },
                engine_name="after_effects",
                action="create_composition",
            ),
            ToolDefinition(
                name="ae_run_script",
                description="在After Effects中执行JSX脚本",
                type=ToolType.MCP,
                input_schema={
                    "type": "object",
                    "properties": {
                        "script_content": {"type": "string", "description": "JSX脚本内容"},
                        "timeout": {"type": "number", "description": "超时时间（秒）"},
                    },
                    "required": ["script_content"],
                },
                engine_name="after_effects",
                action="run_script",
            ),
            ToolDefinition(
                name="ae_add_text_layer",
                description="在AE合成中添加文字层",
                type=ToolType.MCP,
                input_schema={
                    "type": "object",
                    "properties": {
                        "comp_name": {"type": "string", "description": "合成名称"},
                        "text": {"type": "string", "description": "文字内容"},
                        "font_size": {"type": "number", "description": "字体大小"},
                        "position": {"type": "array", "items": {"type": "number"}, "description": "位置[x, y]"},
                        "color": {"type": "string", "description": "颜色，如#FF0000"},
                    },
                    "required": ["comp_name", "text"],
                },
                engine_name="after_effects",
                action="add_text_layer",
            ),
            ToolDefinition(
                name="blender_render",
                description="使用Blender渲染场景",
                type=ToolType.ENGINE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "blend_file": {"type": "string", "description": "Blender场景文件路径"},
                        "output_path": {"type": "string", "description": "输出渲染路径"},
                        "format": {"type": "string", "description": "输出格式，如png、exr"},
                        "resolution": {"type": "string", "description": "渲染分辨率"},
                        "samples": {"type": "number", "description": "采样数"},
                    },
                    "required": ["blend_file", "output_path"],
                },
                engine_name="blender",
                action="render",
            ),
            ToolDefinition(
                name="davinci_color_grade",
                description="使用DaVinci Resolve进行颜色分级",
                type=ToolType.ENGINE,
                input_schema={
                    "type": "object",
                    "properties": {
                        "input_path": {"type": "string", "description": "输入视频文件路径"},
                        "output_path": {"type": "string", "description": "输出视频文件路径"},
                        "preset": {"type": "string", "description": "调色预设名称"},
                        "intensity": {"type": "number", "description": "应用强度0-1"},
                    },
                    "required": ["input_path", "output_path"],
                },
                engine_name="davinci_resolve",
                action="color_grade",
            ),
            ToolDefinition(
                name="python_run_script",
                description="执行Python脚本文件",
                type=ToolType.COMMAND,
                input_schema={
                    "type": "object",
                    "properties": {
                        "script_path": {"type": "string", "description": "Python脚本文件路径"},
                        "arguments": {"type": "array", "items": {"type": "string"}, "description": "命令行参数"},
                    },
                    "required": ["script_path"],
                },
                executable="python",
            ),
        ]
        
        for tool in builtin_tools:
            self.register_tool(tool)
    
    def register_tool(self, tool: ToolDefinition):
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> ToolDefinition | None:
        """获取工具定义"""
        return self._tools.get(name)
    
    def list_v4_tools(self) -> list[dict[str, Any]]:
        """获取所有工具的V4 Function Calling格式列表"""
        return [tool.to_v4_tool() for tool in self._tools.values()]
    
    def execute_command(self, executable: str, arguments: list[str], 
                       timeout: int = 120) -> ToolCallResult:
        """执行命令行工具"""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [executable] + arguments,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                return ToolCallResult(
                    tool_name=executable,
                    status=ExecutionStatus.SUCCESS,
                    output=result.stdout,
                    duration=duration,
                    metadata={"return_code": 0},
                )
            else:
                return ToolCallResult(
                    tool_name=executable,
                    status=ExecutionStatus.FAILED,
                    output=result.stdout,
                    error=result.stderr,
                    duration=duration,
                    metadata={"return_code": result.returncode},
                )
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return ToolCallResult(
                tool_name=executable,
                status=ExecutionStatus.TIMEOUT,
                error=f"Command timed out after {timeout} seconds",
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return ToolCallResult(
                tool_name=executable,
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration=duration,
            )
    
    def execute_mcp_tool(self, engine_name: str, action: str, 
                         arguments: dict[str, Any]) -> ToolCallResult:
        """执行MCP工具"""
        try:
            from mcp_bridge_client import MCPBridgeClient
            
            client = MCPBridgeClient()
            
            jsx_script = self._generate_jsx_script(engine_name, action, arguments)
            
            result = client.send_command(jsx_script, timeout=arguments.get("timeout", 30))
            
            if result.get("status") == "success":
                return ToolCallResult(
                    tool_name=f"{engine_name}_{action}",
                    status=ExecutionStatus.SUCCESS,
                    output=json.dumps(result, ensure_ascii=False),
                    metadata=result.get("metadata", {}),
                )
            else:
                return ToolCallResult(
                    tool_name=f"{engine_name}_{action}",
                    status=ExecutionStatus.FAILED,
                    error=result.get("error", "Unknown error"),
                    metadata=result,
                )
        except ImportError:
            return ToolCallResult(
                tool_name=f"{engine_name}_{action}",
                status=ExecutionStatus.FAILED,
                error="MCP Bridge Client not available",
            )
        except Exception as e:
            return ToolCallResult(
                tool_name=f"{engine_name}_{action}",
                status=ExecutionStatus.FAILED,
                error=str(e),
            )
    
    def _generate_jsx_script(self, engine_name: str, action: str, 
                            arguments: dict[str, Any]) -> str:
        """生成JSX脚本"""
        if engine_name == "after_effects":
            if action == "create_composition":
                return f"""
var comp = app.project.items.addComp(
    "{arguments.get('name', 'New Comp')}",
    {arguments.get('width', 1920)},
    {arguments.get('height', 1080)},
    1,
    {arguments.get('duration', 10)},
    {arguments.get('fps', 30)}
);
{{ status: "success", compName: comp.name, layerCount: comp.numLayers }}
"""
            elif action == "add_text_layer":
                pos = arguments.get("position", [960, 540])
                return f"""
var comp = app.project.items.itemByName("{arguments['comp_name']}");
if (comp && comp instanceof CompItem) {{
    var textLayer = comp.layers.addText("{arguments['text']}");
    var textProp = textLayer.property("ADBE Text Properties").property("ADBE Text Document");
    var doc = textProp.value;
    doc.fontSize = {arguments.get('font_size', 48)};
    textLayer.property("Position").setValue([{pos[0]}, {pos[1]}]);
    textProp.setValue(doc);
    {{ status: "success", layerName: textLayer.name }}
}} else {{
    {{ status: "error", message: "Composition not found" }}
}}
"""
            elif action == "run_script":
                return arguments.get("script_content", "")
        
        return f"{{ status: 'error', message: 'Unsupported action {action}' }}"
    
    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolCallResult:
        """执行工具（统一入口）"""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolCallResult(
                tool_name=tool_name,
                status=ExecutionStatus.FAILED,
                error=f"Tool '{tool_name}' not found",
            )
        
        print(f"[工具执行] {tool_name} - 参数: {json.dumps(arguments, ensure_ascii=False)[:100]}...")
        
        if tool.type == ToolType.COMMAND:
            cmd_args = self._build_command_args(tool, arguments)
            result = self.execute_command(tool.executable, cmd_args)
        
        elif tool.type == ToolType.MCP:
            result = self.execute_mcp_tool(tool.engine_name, tool.action, arguments)
        
        elif tool.type == ToolType.ENGINE:
            result = self._execute_engine_tool(tool, arguments)
        
        else:
            result = ToolCallResult(
                tool_name=tool_name,
                status=ExecutionStatus.FAILED,
                error=f"Unsupported tool type: {tool.type}",
            )
        
        self._call_history.append(result)
        print(f"[执行结果] {tool_name} - {result.status.value} - {result.duration:.2f}s")
        
        return result
    
    def _build_command_args(self, tool: ToolDefinition, arguments: dict[str, Any]) -> list[str]:
        """构建命令行参数"""
        args = []
        
        if tool.name == "ffmpeg_transcode":
            args.extend(["-i", arguments["input_path"]])
            if arguments.get("codec"):
                args.extend(["-c:v", arguments["codec"]])
            if arguments.get("resolution"):
                args.extend(["-s", arguments["resolution"]])
            if arguments.get("fps"):
                args.extend(["-r", str(arguments["fps"])])
            args.append(arguments["output_path"])
        
        elif tool.name == "ffmpeg_extract_audio":
            args.extend(["-i", arguments["input_path"], "-vn", "-acodec", "copy"])
            args.append(arguments["output_path"])
        
        elif tool.name == "ffmpeg_extract_frames":
            args.extend(["-i", arguments["input_path"]])
            if arguments.get("interval"):
                args.extend(["-r", str(1.0 / arguments["interval"])])
            elif arguments.get("count"):
                args.extend(["-vf", f"fps={arguments['count']}/10"])
            os.makedirs(arguments["output_dir"], exist_ok=True)
            args.append(os.path.join(arguments["output_dir"], "frame_%04d.png"))
        
        elif tool.name == "python_run_script":
            args.append(arguments["script_path"])
            args.extend(arguments.get("arguments", []))
        
        else:
            for key, value in arguments.items():
                args.append(f"--{key}")
                args.append(str(value))
        
        return args
    
    def _execute_engine_tool(self, tool: ToolDefinition, arguments: dict[str, Any]) -> ToolCallResult:
        """执行引擎工具"""
        try:
            from toolchain_manager import ToolchainManager
            
            manager = ToolchainManager()
            result = manager.execute_tool(
                tool.engine_name,
                tool.action,
                arguments,
            )
            
            if result.success:
                return ToolCallResult(
                    tool_name=tool.name,
                    status=ExecutionStatus.SUCCESS,
                    output=str(result.output_path) if result.output_path else "",
                    metadata=result.output_data,
                )
            else:
                return ToolCallResult(
                    tool_name=tool.name,
                    status=ExecutionStatus.FAILED,
                    error=result.error,
                )
                
        except ImportError:
            return ToolCallResult(
                tool_name=tool.name,
                status=ExecutionStatus.FAILED,
                error="Toolchain Manager not available",
            )
        except Exception as e:
            return ToolCallResult(
                tool_name=tool.name,
                status=ExecutionStatus.FAILED,
                error=str(e),
            )
    
    def model_driven_execution(self, user_request: str, 
                               max_tool_calls: int = 5) -> dict[str, Any]:
        """模型驱动的工具执行
        
        流程：V4分析 → 选择工具 → 执行 → 反馈 → 继续/结束
        
        Args:
            user_request: 用户请求（自然语言）
            max_tool_calls: 最大工具调用次数
            
        Returns:
            执行结果汇总
        """
        if not V4_AVAILABLE:
            return {
                "success": False,
                "error": "V4 Agent not available",
                "steps": [],
            }
        
        if self._v4_agent is None:
            self._v4_agent = V4Agent()
        
        all_tools = self.list_v4_tools()
        
        system_prompt = f"""你是一个专业的视频制作工具调用助手。
你可以使用以下工具来完成用户请求：

可用工具列表：
{json.dumps(all_tools, indent=2, ensure_ascii=False)}

工作流程：
1. 分析用户请求
2. 选择合适的工具
3. 输出工具调用JSON（不要其他文字）
4. 如果需要多次调用，请在一次回复中输出多个工具调用
5. 如果无法完成或不需要工具，请直接回答

工具调用格式（JSON数组）：
[
  {{
    "name": "工具名称",
    "arguments": {{参数对象}}
  }}
]

注意：
- 参数必须符合工具的input_schema
- 路径使用绝对路径
- 如果需要多次操作，按顺序输出多个工具调用
- 只输出JSON，不要其他文字
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ]
        
        print(f"[模型驱动] 分析请求: {user_request[:50]}...")
        
        try:
            result = self._v4_agent.ask(
                user_request,
                model="pro",
                max_tokens=8192,
            )
            
            tool_calls = self._parse_tool_calls(result)
            executed_steps = []
            
            for i, call in enumerate(tool_calls[:max_tool_calls]):
                print(f"[步骤 {i+1}] 调用工具: {call['name']}")
                
                exec_result = self.execute(call["name"], call["arguments"])
                executed_steps.append({
                    "tool": call["name"],
                    "arguments": call["arguments"],
                    "result": exec_result.to_dict(),
                })
                
                if exec_result.status != ExecutionStatus.SUCCESS:
                    print(f"[步骤 {i+1}] 执行失败: {exec_result.error}")
                    break
            
            return {
                "success": all(s["result"]["status"] == "success" for s in executed_steps),
                "steps": executed_steps,
                "total_steps": len(executed_steps),
                "v4_analysis": result,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "steps": [],
            }
    
    def _parse_tool_calls(self, result: str) -> list[dict[str, Any]]:
        """解析V4返回的工具调用"""
        try:
            json_start = result.find("[")
            json_end = result.rfind("]") + 1
            
            if json_start != -1 and json_end != -1:
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
            
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            
            if json_start != -1 and json_end != -1:
                json_str = result[json_start:json_end]
                data = json.loads(json_str)
                return [data]
                
        except (json.JSONDecodeError, ValueError):
            pass
        
        return []
    
    def execute_plan(self, plan: list[dict[str, Any]]) -> dict[str, Any]:
        """执行预定义计划"""
        executed_steps = []
        
        for i, step in enumerate(plan):
            tool_name = step["tool"]
            arguments = step.get("arguments", {})
            
            print(f"[计划步骤 {i+1}] 调用工具: {tool_name}")
            
            exec_result = self.execute(tool_name, arguments)
            executed_steps.append({
                "step": i + 1,
                "tool": tool_name,
                "arguments": arguments,
                "result": exec_result.to_dict(),
            })
            
            if exec_result.status != ExecutionStatus.SUCCESS:
                print(f"[计划步骤 {i+1}] 执行失败: {exec_result.error}")
                break
        
        return {
            "success": all(s["result"]["status"] == "success" for s in executed_steps),
            "steps": executed_steps,
            "total_steps": len(executed_steps),
        }


# 全局实例
_executor = None


def get_executor() -> ToolExecutor:
    """获取全局工具执行器实例"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor


def execute_tool(tool_name: str, **kwargs) -> ToolCallResult:
    """快捷函数：执行工具"""
    return get_executor().execute(tool_name, kwargs)


def model_execute(user_request: str) -> dict[str, Any]:
    """快捷函数：模型驱动执行"""
    return get_executor().model_driven_execution(user_request)


if __name__ == "__main__":
    executor = ToolExecutor()
    
    print("=" * 60)
    print("工具执行引擎 - 测试模式")
    print("=" * 60)
    
    print(f"\n已注册工具: {len(executor.tools)}个")
    for name, tool in executor.tools.items():
        print(f"  - {name}: {tool.description[:30]}...")
    
    print("\n" + "=" * 60)
    print("测试模型驱动执行...")
    print("=" * 60)
    
    test_request = "从视频 D:/AE-Work/test.mp4 中提取10帧关键帧到 D:/AE-Work/frames 目录"
    print(f"\n请求: {test_request}")
    
    result = executor.model_driven_execution(test_request)
    print(f"\n结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
