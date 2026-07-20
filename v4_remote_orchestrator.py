#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4 远程编排引擎
===============
外出时通过 V4 深度分析远程触发 AE 自动化合成任务。
支持：自然语言描述 → V4分析 → 生成AE脚本 → 自动执行 → 反馈

调用方式:
    from v4_remote_orchestrator import V4RemoteOrchestrator

    orch = V4RemoteOrchestrator()
    result = orch.execute_composition_task(
        "创建一个576x768竖屏合成，导入冰海战记素材，添加发光和粒子效果，渲染为mp4"
    )
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from ai_agent import V4Agent
except ImportError:
    V4Agent = None  # type: ignore[assignment,misc]

try:
    from ae_mcp_client import AECommandClient
except ImportError:
    AECommandClient = None  # type: ignore[assignment,misc]

try:
    from ae_composition_presets import COMPOSITION_PRESETS
except ImportError:
    COMPOSITION_PRESETS = {}  # type: ignore[assignment]

# V4 Function Calling 系统提示
_ORCHESTRATOR_SYSTEM_PROMPT = """你是「V4远程编排引擎」，负责将用户的自然语言描述转化为结构化的 AE 操作计划。

工作流程:
1. 分析用户的任务描述，理解意图和需求
2. 将任务分解为具体的 AE 操作步骤
3. 为每个步骤选择正确的 MCP Bridge 命令和参数
4. 生成可执行的操作计划

可用的 AE 操作:
- createComposition: 创建合成（需指定名称、宽、高、帧率、时长）
- importFootage: 导入素材（需指定文件路径）
- addLayerToComp: 添加图层到合成
- addEffect: 添加效果（需指定效果名和参数）
- setKeyframe: 设置关键帧
- setExpression: 设置表达式
- setBlendingMode: 设置混合模式
- addMask: 添加遮罩
- addTextLayer: 添加文本图层
- addSolidLayer: 添加纯色/调整图层
- addShapeLayer: 添加形状图层
- setLayer3D: 设置3D图层
- addCamera: 添加摄像机
- addLight: 添加灯光
- precompose: 预合成
- renderQueue: 添加到渲染队列
- applyPreset: 应用预设
- executeScript: 执行自定义脚本

输出格式:
返回 JSON 数组，每个元素包含 op（操作名）和 params（参数对象）。
示例:
[
  {"op": "createComposition", "params": {"name": "竖屏MV", "width": 576, "height": 768, "frameRate": 30, "duration": 12}},
  {"op": "importFootage", "params": {"filePath": "D:/素材/视频.mp4"}},
  {"op": "addEffect", "params": {"layerName": "视频", "effectName": "ADBE Glo2", "params": {"发光半径": 20}}},
  {"op": "renderQueue", "params": {"outputPath": "D:/输出/result.mp4", "format": "mp4"}}
]

规则:
1. 中文回答
2. 只返回 JSON 数组，不要其他文字
3. 参数使用 AE 官方匹配名称
4. 文件路径使用正斜杠
"""


class V4RemoteOrchestrator:
    """V4 远程编排引擎 - 自然语言驱动的 AE 自动化合成

    通过 V4 深度分析将用户的自然语言描述转化为 AE 操作计划，
    并通过 AECommandClient 自动执行。
    """

    def __init__(
        self,
        v4_api_key: Optional[str] = None,
        ae_bridge_dir: Optional[str] = None,
    ) -> None:
        """初始化编排引擎

        Args:
            v4_api_key: DeepSeek V4 API Key（None 则从环境变量读取）
            ae_bridge_dir: AE MCP Bridge 目录（None 则使用默认路径）
        """
        # 初始化 V4Agent
        if V4Agent is None:
            raise ImportError("ai_agent.V4Agent 不可用，请检查 ai_agent.py")
        self.v4: V4Agent = V4Agent(api_key=v4_api_key)

        # 初始化 AECommandClient
        if AECommandClient is None:
            raise ImportError("ae_mcp_client.AECommandClient 不可用，请检查 ae_mcp_client.py")
        self.ae: AECommandClient = AECommandClient()

        # 任务历史
        self.task_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 核心方法
    # ------------------------------------------------------------------

    def execute_composition_task(self, task_description: str) -> Dict[str, Any]:
        """核心方法：V4 分析任务描述 → 生成步骤 → 执行 → 返回结果

        Args:
            task_description: 自然语言描述的 AE 合成任务

        Returns:
            包含 plan、results、status 等字段的执行结果字典
        """
        task_id = f"task_{int(time.time())}_{len(self.task_history)}"
        start_time = time.time()

        print(f"\n{'='*60}")
        print(f"[V4编排] 任务 {task_id} 开始")
        print(f"[V4编排] 描述: {task_description}")
        print(f"{'='*60}")

        # 1. V4 分析 → 生成操作计划
        try:
            plan = self.analyze_and_plan(task_description)
        except Exception as e:
            error_result = {
                "task_id": task_id,
                "status": "error",
                "stage": "analyze_and_plan",
                "error": str(e),
                "task_description": task_description,
            }
            self.task_history.append(error_result)
            return error_result

        print(f"[V4编排] 生成操作计划: {len(plan)} 步")

        # 2. 执行操作计划
        try:
            results = self.execute_plan(plan)
        except Exception as e:
            error_result = {
                "task_id": task_id,
                "status": "error",
                "stage": "execute_plan",
                "error": str(e),
                "plan": plan,
                "task_description": task_description,
            }
            self.task_history.append(error_result)
            return error_result

        # 3. 汇总结果
        success_count = sum(1 for r in results if r.get("status") == "success")
        total_count = len(results)
        duration = time.time() - start_time

        final_status = "success" if success_count == total_count else "partial"

        result = {
            "task_id": task_id,
            "status": final_status,
            "task_description": task_description,
            "plan": plan,
            "results": results,
            "summary": {
                "total_steps": total_count,
                "success_steps": success_count,
                "failed_steps": total_count - success_count,
                "duration_seconds": round(duration, 2),
            },
            "timestamp": datetime.now().isoformat(),
        }

        self.task_history.append(result)

        print(f"\n[V4编排] 任务 {task_id} 完成: {final_status}")
        print(f"[V4编排] 成功 {success_count}/{total_count} 步, 耗时 {duration:.1f}s")
        print(f"{'='*60}\n")

        return result

    # ------------------------------------------------------------------
    # 分析与计划
    # ------------------------------------------------------------------

    def analyze_and_plan(self, task_description: str) -> List[Dict[str, Any]]:
        """V4 分析任务描述，返回操作计划列表

        Args:
            task_description: 自然语言任务描述

        Returns:
            结构化操作列表 [{"op": str, "params": dict}, ...]
        """
        prompt = (
            f"{_ORCHESTRATOR_SYSTEM_PROMPT}\n\n"
            f"用户任务描述:\n{task_description}\n\n"
            f"请生成操作计划（JSON数组）:"
        )

        raw_response: str = self.v4.ask(prompt, model="pro", max_tokens=8192)

        # 解析 V4 返回的 JSON
        plan = self._parse_plan_from_response(raw_response)

        if not plan:
            # 回退：尝试用 analyze 方法
            print("[V4编排] 首次解析失败，尝试 V4 analyze 回退")
            analysis = self.v4.analyze(
                f"将以下AE任务分解为操作步骤（每步包含 op 和 params）:\n{task_description}"
            )
            plan = self._parse_plan_from_response(analysis)

        if not plan:
            print("[V4编排] V4 未能生成有效计划，返回空计划")
            return []

        return plan

    def _parse_plan_from_response(self, response: str) -> List[Dict[str, Any]]:
        """从 V4 响应中解析操作计划 JSON

        Args:
            response: V4 的原始文本响应

        Returns:
            操作计划列表
        """
        # 尝试直接解析
        try:
            plan = json.loads(response)
            if isinstance(plan, list):
                return plan
        except json.JSONDecodeError:
            pass

        # 尝试提取 JSON 代码块
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group(1).strip())
                if isinstance(plan, list):
                    return plan
            except json.JSONDecodeError:
                pass

        # 尝试提取方括号内容
        bracket_match = re.search(r'\[[\s\S]*\]', response)
        if bracket_match:
            try:
                plan = json.loads(bracket_match.group(0))
                if isinstance(plan, list):
                    return plan
            except json.JSONDecodeError:
                pass

        return []

    # ------------------------------------------------------------------
    # 脚本生成
    # ------------------------------------------------------------------

    def generate_ae_script(self, plan: List[Dict[str, Any]]) -> str:
        """根据操作计划生成完整 AE ExtendScript 代码

        Args:
            plan: 操作计划列表

        Returns:
            完整的 JSX/ExtendScript 代码字符串
        """
        jsx_lines: List[str] = [
            "// V4 远程编排 - 自动生成脚本",
            f"// 生成时间: {datetime.now().isoformat()}",
            f"// 操作步骤: {len(plan)}",
            "",
            "(function() {",
            "  var _results = [];",
            "  var _errors = [];",
            "",
        ]

        for i, step in enumerate(plan):
            op = step.get("op", "")
            params = step.get("params", {})
            jsx_lines.append(f"  // --- 步骤 {i + 1}: {op} ---")

            if op == "createComposition":
                name = params.get("name", f"V4_Comp_{i}")
                width = params.get("width", 1920)
                height = params.get("height", 1080)
                frame_rate = params.get("frameRate", 30)
                duration = params.get("duration", 10)
                bg_color = params.get("bgColor", [0, 0, 0])
                jsx_lines.extend([
                    f'  var comp{i} = app.project.items.addComp("{name}", {width}, {height}, {frame_rate}, {duration}, 1);',
                    f"  comp{i}.bgColor = {json.dumps(bg_color)};",
                    f'  _results.push({{step: {i + 1}, op: "{op}", status: "success", name: "{name}"}});',
                ])

            elif op == "importFootage":
                file_path = params.get("filePath", "").replace("\\", "/")
                jsx_lines.extend([
                    f'  var file{i} = new File("{file_path}");',
                    f"  if (file{i}.exists) {{",
                    f"    var footage{i} = app.project.importFile(new ImportOptions(file{i}));",
                    f'    _results.push({{step: {i + 1}, op: "{op}", status: "success", name: footage{i}.name}});',
                    f"  }} else {{",
                    f'    _errors.push({{step: {i + 1}, op: "{op}", error: "File not found: {file_path}"}});',
                    f"  }}",
                ])

            elif op == "addEffect":
                layer_name = params.get("layerName", "")
                effect_name = params.get("effectName", "ADBE Glo2")
                effect_params = params.get("params", {})
                jsx_lines.extend([
                    f"  try {{",
                    f"    var comp = app.project.activeItem;",
                    f'    var layer = null;',
                    f"    for (var j=1; j<=comp.numLayers; j++) {{",
                    f'      if (comp.layer(j).name == "{layer_name}") {{ layer = comp.layer(j); break; }}',
                    f"    }}",
                    f"    if (!layer) layer = comp.layer(1);",
                    f'    var effect{i} = layer.Effects.addProperty("{effect_name}");',
                ])
                for pk, pv in effect_params.items():
                    jsx_lines.append(f'    // effect param: {pk} = {pv}')
                jsx_lines.extend([
                    f'    _results.push({{step: {i + 1}, op: "{op}", status: "success", effect: "{effect_name}"}});',
                    f"  }} catch(e) {{",
                    f'    _errors.push({{step: {i + 1}, op: "{op}", error: e.toString()}});',
                    f"  }}",
                ])

            elif op == "addTextLayer":
                text = params.get("text", "Text")
                jsx_lines.extend([
                    f"  try {{",
                    f"    var comp = app.project.activeItem;",
                    f'    var textLayer{i} = comp.layers.addText("{text}");',
                    f'    _results.push({{step: {i + 1}, op: "{op}", status: "success", text: "{text}"}});',
                    f"  }} catch(e) {{",
                    f'    _errors.push({{step: {i + 1}, op: "{op}", error: e.toString()}});',
                    f"  }}",
                ])

            elif op == "addSolidLayer":
                color = params.get("color", [1, 1, 1])
                name = params.get("name", f"Solid_{i}")
                jsx_lines.extend([
                    f"  try {{",
                    f"    var comp = app.project.activeItem;",
                    f'    var solid{i} = comp.layers.addSolid({json.dumps(color)}, "{name}", comp.width, comp.height, 1);',
                    f'    _results.push({{step: {i + 1}, op: "{op}", status: "success", name: "{name}"}});',
                    f"  }} catch(e) {{",
                    f'    _errors.push({{step: {i + 1}, op: "{op}", error: e.toString()}});',
                    f"  }}",
                ])

            elif op == "renderQueue":
                output_path = params.get("outputPath", "").replace("\\", "/")
                jsx_lines.extend([
                    f"  try {{",
                    f"    var comp = app.project.activeItem;",
                    f"    var rqItem = app.project.renderQueue.items.add(comp);",
                    f'    var om = rqItem.outputModule(1);',
                    f'    om.file = new File("{output_path}");',
                    f'    _results.push({{step: {i + 1}, op: "{op}", status: "success", outputPath: "{output_path}"}});',
                    f"  }} catch(e) {{",
                    f'    _errors.push({{step: {i + 1}, op: "{op}", error: e.toString()}});',
                    f"  }}",
                ])

            else:
                # 通用步骤：记录为注释
                jsx_lines.extend([
                    f"  // 未映射的操作: {op}",
                    f"  // 参数: {json.dumps(params, ensure_ascii=False)}",
                    f'  _results.push({{step: {i + 1}, op: "{op}", status: "skipped", reason: "未映射操作"}});',
                ])

            jsx_lines.append("")

        # 收尾
        jsx_lines.extend([
            "  return JSON.stringify({results: _results, errors: _errors});",
            "})();",
        ])

        return "\n".join(jsx_lines)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def execute_plan(self, plan: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """执行操作计划

        Args:
            plan: 操作计划列表

        Returns:
            每个步骤的执行结果列表
        """
        results: List[Dict[str, Any]] = []

        for i, step in enumerate(plan):
            op = step.get("op", "")
            params = step.get("params", {})

            print(f"[V4编排] 步骤 {i + 1}/{len(plan)}: {op}")

            try:
                result = self.ae.send_command(op, params)
                results.append({
                    "step": i + 1,
                    "op": op,
                    "params": params,
                    "status": result.get("status", "unknown"),
                    "result": result,
                })
                print(f"  → {result.get('status', 'unknown')}")
            except Exception as e:
                results.append({
                    "step": i + 1,
                    "op": op,
                    "params": params,
                    "status": "error",
                    "error": str(e),
                })
                print(f"  → 错误: {e}")

        return results

    def execute_script_direct(self, jsx_code: str) -> Dict[str, Any]:
        """直接执行 JSX 脚本

        Args:
            jsx_code: ExtendScript/JSX 代码字符串

        Returns:
            AE 执行结果
        """
        try:
            return self.ae.send_command("executeAtomScript", {"scriptContent": jsx_code})
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # 工具定义（注册给 V4 Function Calling）
    # ------------------------------------------------------------------

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """返回所有可用的 AE 操作工具列表（注册给 V4 Function Calling）

        Returns:
            工具定义列表，符合 OpenAI Function Calling 格式
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "createComposition",
                    "description": "创建AE合成",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "合成名称"},
                            "width": {"type": "integer", "description": "宽度（像素）", "default": 1920},
                            "height": {"type": "integer", "description": "高度（像素）", "default": 1080},
                            "frameRate": {"type": "number", "description": "帧率", "default": 30},
                            "duration": {"type": "number", "description": "时长（秒）", "default": 10},
                            "bgColor": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "背景色 [R,G,B] 0-1",
                                "default": [0, 0, 0],
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "importFootage",
                    "description": "导入素材到AE项目",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filePath": {"type": "string", "description": "素材文件路径"},
                            "name": {"type": "string", "description": "项目面板中的名称"},
                            "asSequence": {"type": "boolean", "description": "是否作为序列帧导入", "default": False},
                        },
                        "required": ["filePath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addLayerToComp",
                    "description": "添加图层到合成",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "footageName": {"type": "string", "description": "素材名称"},
                            "layerName": {"type": "string", "description": "图层名称"},
                        },
                        "required": ["compName", "footageName"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addEffect",
                    "description": "为图层添加效果",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "effectName": {"type": "string", "description": "效果匹配名（如 ADBE Glo2）"},
                            "params": {
                                "type": "object",
                                "description": "效果参数键值对",
                                "additionalProperties": True,
                            },
                        },
                        "required": ["layerName", "effectName"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "setKeyframe",
                    "description": "设置关键帧",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "propertyName": {"type": "string", "description": "属性名"},
                            "time": {"type": "number", "description": "时间（秒）"},
                            "value": {"description": "关键帧值"},
                        },
                        "required": ["layerName", "propertyName", "time", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "setExpression",
                    "description": "设置表达式",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "propertyName": {"type": "string", "description": "属性名"},
                            "expression": {"type": "string", "description": "表达式代码"},
                        },
                        "required": ["layerName", "propertyName", "expression"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "setBlendingMode",
                    "description": "设置图层混合模式",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "mode": {"type": "string", "description": "混合模式（如 ADD, SCREEN, MULTIPLY）"},
                        },
                        "required": ["layerName", "mode"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addMask",
                    "description": "添加遮罩",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "maskShape": {"type": "string", "description": "遮罩形状类型（rectangle, ellipse, bezier）"},
                            "mode": {"type": "string", "description": "遮罩模式（add, subtract, intersect）"},
                        },
                        "required": ["layerName"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addTextLayer",
                    "description": "添加文本图层",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "text": {"type": "string", "description": "文本内容"},
                            "fontSize": {"type": "number", "description": "字号", "default": 72},
                            "fontFamily": {"type": "string", "description": "字体", "default": "Arial"},
                        },
                        "required": ["text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addSolidLayer",
                    "description": "添加纯色/调整图层",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "name": {"type": "string", "description": "图层名称"},
                            "color": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "颜色 [R,G,B] 0-1",
                                "default": [1, 1, 1],
                            },
                            "isAdjustment": {"type": "boolean", "description": "是否为调整图层", "default": False},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addShapeLayer",
                    "description": "添加形状图层",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "shapeType": {"type": "string", "description": "形状类型（rectangle, ellipse, polygon, star）"},
                            "size": {"type": "number", "description": "大小", "default": 100},
                            "color": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "填充色 [R,G,B] 0-1",
                            },
                        },
                        "required": ["shapeType"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "setLayer3D",
                    "description": "设置3D图层",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "is3D": {"type": "boolean", "description": "是否启用3D", "default": True},
                        },
                        "required": ["layerName"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addCamera",
                    "description": "添加摄像机",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "name": {"type": "string", "description": "摄像机名称"},
                            "focalLength": {"type": "number", "description": "焦距（mm）", "default": 50},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "addLight",
                    "description": "添加灯光",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "name": {"type": "string", "description": "灯光名称"},
                            "lightType": {
                                "type": "string",
                                "description": "灯光类型（Point, Parallel, Spot, Ambient）",
                                "default": "Point",
                            },
                            "intensity": {"type": "number", "description": "强度", "default": 100},
                            "color": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "颜色 [R,G,B] 0-1",
                                "default": [1, 1, 1],
                            },
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "precompose",
                    "description": "预合成选中图层",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "当前合成名称"},
                            "layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要预合成的图层名称列表",
                            },
                            "newCompName": {"type": "string", "description": "新合成名称"},
                        },
                        "required": ["layers", "newCompName"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "renderQueue",
                    "description": "添加到渲染队列并输出",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "compName": {"type": "string", "description": "合成名称"},
                            "outputPath": {"type": "string", "description": "输出文件路径"},
                            "format": {"type": "string", "description": "输出格式（mp4, mov, avi）", "default": "mp4"},
                            "preset": {"type": "string", "description": "输出模块预设", "default": "H.264"},
                        },
                        "required": ["outputPath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "applyPreset",
                    "description": "应用效果预设",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "layerName": {"type": "string", "description": "图层名称"},
                            "presetPath": {"type": "string", "description": "预设文件路径(.ffx)"},
                        },
                        "required": ["layerName", "presetPath"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "executeScript",
                    "description": "执行自定义ExtendScript脚本",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "scriptContent": {"type": "string", "description": "ExtendScript/JSX 代码"},
                        },
                        "required": ["scriptContent"],
                    },
                },
            },
        ]

    # ------------------------------------------------------------------
    # 快速合成预设
    # ------------------------------------------------------------------

    def quick_composition(self, preset: str, **kwargs: Any) -> Dict[str, Any]:
        """快速合成预设 - 一键创建预配置的 AE 合成

        Args:
            preset: 预设名称，支持:
                - "music_video": 竖屏音乐视频合成（576x768）
                - "puppet_style": 木偶风格合成
                - "particle_fx": 粒子特效合成
                - "text_animation": 文字动画合成
                - "3d_scene": 3D场景合成
            **kwargs: 覆盖预设参数

        Returns:
            执行结果
        """
        preset_key = {
            "music_video": "music_video_vertical",
            "puppet_style": "puppet_style",
            "particle_fx": "particle_fx",
            "text_animation": "text_animation",
            "3d_scene": "3d_scene",
        }.get(preset)

        if not preset_key or preset_key not in COMPOSITION_PRESETS:
            available = list(COMPOSITION_PRESETS.keys()) if COMPOSITION_PRESETS else ["无预设可用"]
            return {
                "status": "error",
                "error": f"未知预设: {preset}",
                "available_presets": available,
            }

        config = COMPOSITION_PRESETS[preset_key]

        # 用 kwargs 覆盖配置
        comp_settings = {**config.get("comp_settings", {}), **kwargs}
        comp_name = comp_settings.get("name", config.get("name", f"V4_{preset}"))
        width = comp_settings.get("width", 576)
        height = comp_settings.get("height", 768)
        frame_rate = comp_settings.get("frameRate", 30)
        duration = comp_settings.get("duration", 12)
        bg_color = comp_settings.get("bgColor", [5, 5, 15])

        print(f"[V4编排] 快速合成: {preset} → {comp_name}")

        # 构建操作计划
        plan: List[Dict[str, Any]] = [
            {
                "op": "createComposition",
                "params": {
                    "name": comp_name,
                    "width": width,
                    "height": height,
                    "frameRate": frame_rate,
                    "duration": duration,
                    "bgColor": bg_color,
                },
            }
        ]

        # 添加默认图层
        for layer_cfg in config.get("layers", []):
            plan.append({"op": layer_cfg.get("op", "addSolidLayer"), "params": layer_cfg.get("params", {})})

        # 添加默认效果
        for effect_cfg in config.get("effects", []):
            plan.append({"op": "addEffect", "params": effect_cfg.get("params", effect_cfg)})

        # 添加渲染设置
        render_cfg = config.get("render_settings", {})
        if render_cfg:
            plan.append({"op": "renderQueue", "params": render_cfg})

        # 执行计划
        return self.execute_composition_task(
            f"快速合成预设[{preset}]: {comp_name} {width}x{height}@{frame_rate}fps {duration}s"
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def get_task_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取任务执行历史

        Args:
            limit: 返回最近 N 条记录

        Returns:
            任务历史列表
        """
        return self.task_history[-limit:]

    def clear_history(self) -> None:
        """清空任务历史"""
        self.task_history.clear()


# ======================================================================
# 全局单例与快捷函数
# ======================================================================

_orchestrator: Optional[V4RemoteOrchestrator] = None


def get_orchestrator() -> V4RemoteOrchestrator:
    """获取全局编排引擎单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = V4RemoteOrchestrator()
    return _orchestrator


def execute_composition_task(task_description: str) -> Dict[str, Any]:
    """快捷函数：执行合成任务"""
    return get_orchestrator().execute_composition_task(task_description)


def quick_composition(preset: str, **kwargs: Any) -> Dict[str, Any]:
    """快捷函数：快速合成预设"""
    return get_orchestrator().quick_composition(preset, **kwargs)


# ======================================================================
# 命令行入口
# ======================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="V4 远程编排引擎")
    parser.add_argument("task", nargs="?", help="任务描述")
    parser.add_argument("--preset", help="快速预设名称")
    parser.add_argument("--tools", action="store_true", help="列出可用工具")
    args = parser.parse_args()

    if args.tools:
        orch = V4RemoteOrchestrator()
        tools = orch.get_available_tools()
        print(f"\n可用工具 ({len(tools)} 个):")
        for t in tools:
            fn = t["function"]
            print(f"  - {fn['name']}: {fn['description']}")
    elif args.preset:
        orch = V4RemoteOrchestrator()
        result = orch.quick_composition(args.preset)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.task:
        orch = V4RemoteOrchestrator()
        result = orch.execute_composition_task(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
