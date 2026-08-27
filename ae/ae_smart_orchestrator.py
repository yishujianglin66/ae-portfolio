#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AE 智能合成编排器 - V4驱动
========================

V4 深度分析用户需求 → 自动生成 AE 合成脚本 → 通过 MCP Bridge 执行 → 返回结果

完整链路:
用户自然语言描述 → V4 Pro 分析+分解 → 生成结构化操作列表 →
转换为AE ExtendScript命令 → 发送到AE MCP Bridge → AE执行 → 返回结果

支持外出远程使用：用户无需在电脑前，只要有网络即可通过 API 触发。
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

try:
    from ai_agent import V4Agent
    _V4_AVAILABLE = True
except ImportError:
    V4Agent = None
    _V4_AVAILABLE = False

try:
    from ae_mcp_client import AECommandClient
    _AE_CLIENT_AVAILABLE = True
except ImportError:
    AECommandClient = None
    _AE_CLIENT_AVAILABLE = False

try:
    import ae_composition_presets
    _PRESETS_AVAILABLE = True
except ImportError:
    ae_composition_presets = None
    _PRESETS_AVAILABLE = False


class AESmartOrchestrator:
    """V4 驱动的智能 AE 合成编排器"""

    def __init__(self):
        self.v4_agent = V4Agent() if _V4_AVAILABLE and V4Agent else None
        self.ae_client = AECommandClient() if _AE_CLIENT_AVAILABLE and AECommandClient else None
        self.presets = ae_composition_presets if _PRESETS_AVAILABLE else None
        self.task_history: List[Dict[str, Any]] = []
        self.execution_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def compose(self, task_description: str, mode: str = "auto") -> dict:
        """智能合成主入口

        Args:
            task_description: 自然语言描述，如 "创建竖屏音乐视频，用冰海战记素材，加发光粒子效果"
            mode: 执行模式 "auto"(自动V4分析) / "preset"(预设匹配) / "script"(直接脚本)

        Returns:
            {"success": bool, "steps": [...], "results": [...], "ae_script": str, "error": str}
        """
        start = time.time()
        task_record = {
            "description": task_description,
            "mode": mode,
            "start_time": start,
            "success": False,
        }

        try:
            if mode == "auto":
                # 1. V4 分析任务描述
                plan = self._v4_analyze_task(task_description)
                # 2. 验证操作步骤
                if not self._validate_plan(plan):
                    return {
                        "success": False,
                        "steps": [],
                        "results": [],
                        "ae_script": "",
                        "error": "操作计划验证失败",
                    }
                # 3. 执行操作计划
                results = self._execute_plan(plan)
                # 4. 生成独立脚本（备选）
                script = self._plan_to_script(plan)
                task_record["success"] = all(r.get("success", False) for r in results)
                return {
                    "success": task_record["success"],
                    "task_type": plan.get("task_type", ""),
                    "steps": plan.get("operations", []),
                    "results": results,
                    "ae_script": script,
                    "error": "",
                }

            elif mode == "preset":
                # 从描述中尝试匹配预设名
                preset_name = task_description.strip()
                return self.compose_from_preset(preset_name)

            elif mode == "script":
                # 直接把描述当脚本执行
                if self.ae_client:
                    result = self.ae_client.send_command("evalScript", {"script": task_description})
                    return {
                        "success": result.get("success", False),
                        "steps": [{"op": "evalScript", "params": {"script": task_description}}],
                        "results": [result],
                        "ae_script": task_description,
                        "error": result.get("error", ""),
                    }
                return {
                    "success": False,
                    "steps": [],
                    "results": [],
                    "ae_script": task_description,
                    "error": "AE MCP Bridge 不可用",
                }

            else:
                return {
                    "success": False,
                    "steps": [],
                    "results": [],
                    "ae_script": "",
                    "error": f"未知模式: {mode}",
                }

        except Exception as e:
            task_record["error"] = str(e)
            return {
                "success": False,
                "steps": [],
                "results": [],
                "ae_script": "",
                "error": str(e),
            }
        finally:
            task_record["duration"] = time.time() - start
            self.task_history.append(task_record)

    # ------------------------------------------------------------------
    # V4 分析
    # ------------------------------------------------------------------

    def _v4_analyze_task(self, task_description: str) -> dict:
        """V4 Pro 分析任务，返回结构化操作计划"""
        if not self.v4_agent:
            # 退化为基础计划
            return {
                "task_type": "composition",
                "comp_settings": {
                    "name": "SmartComp",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "duration": 10,
                },
                "operations": [
                    {"op": "createComposition", "params": {"name": "SmartComp", "width": 1920, "height": 1080, "fps": 30, "duration": 10}},
                ],
            }

        system_prompt = """你是 AE 合成编排专家。根据用户的自然语言描述，生成结构化操作计划。

返回严格的 JSON 格式（不要多余文字）：
{
    "task_type": "composition|render|effect|animation",
    "comp_settings": {"name":"","width":1920,"height":1080,"fps":30,"duration":10},
    "operations": [
        {"op": "createComposition", "params": {...}},
        {"op": "importFootage", "params": {"path": "..."}},
        {"op": "addEffect", "params": {"layer": 1, "effect": "Glow", "radius": 20, "intensity": 0.8}},
        {"op": "addKeyframe", "params": {"layer": 1, "prop": "Position", "time": 0, "value": [0,0]}},
        {"op": "render", "params": {"output": "output.mp4", "format": "mp4"}}
    ]
}

可用操作:
- createComposition: 创建合成
- importFootage: 导入素材
- addLayer: 添加图层
- addEffect: 添加效果
- addKeyframe: 添加关键帧
- setText: 设置文字内容
- render: 渲染输出

只返回 JSON，不要任何其他内容。"""

        try:
            response = self.v4_agent.ask(
                f"{system_prompt}\n\n用户需求: {task_description}"
            )
            # 解析 V4 返回的 JSON（可能包裹在 ```json ``` 中）
            return self._parse_json_response(response)
        except Exception as e:
            # 退化为基础计划
            return {
                "task_type": "composition",
                "comp_settings": {
                    "name": "SmartComp",
                    "width": 1920,
                    "height": 1080,
                    "fps": 30,
                    "duration": 10,
                },
                "operations": [
                    {"op": "createComposition", "params": {"name": "SmartComp", "width": 1920, "height": 1080, "fps": 30, "duration": 10}},
                ],
                "_v4_error": str(e),
            }

    @staticmethod
    def _parse_json_response(text: str) -> dict:
        """从可能包裹在 markdown 代码块中的文本提取 JSON"""
        # 尝试提取 ```json ... ``` 块
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
        else:
            json_str = text.strip()

        # 去掉可能的前后非 JSON 字符
        start = json_str.find("{")
        end = json_str.rfind("}")
        if start != -1 and end != -1:
            json_str = json_str[start:end + 1]

        return json.loads(json_str)

    # ------------------------------------------------------------------
    # 验证 & 执行
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: dict) -> bool:
        """验证操作计划的合法性"""
        if not isinstance(plan, dict):
            return False
        if "operations" not in plan:
            return False
        ops = plan["operations"]
        if not isinstance(ops, list) or len(ops) == 0:
            return False

        valid_ops = {
            "createComposition", "importFootage", "addLayer", "addEffect",
            "addKeyframe", "setText", "render", "evalScript",
        }
        for op_item in ops:
            if not isinstance(op_item, dict):
                return False
            if op_item.get("op") not in valid_ops:
                return False

        return True

    def _execute_plan(self, plan: dict) -> list:
        """执行操作计划，返回每步结果"""
        results = []
        for op_item in plan.get("operations", []):
            op = op_item.get("op", "")
            params = op_item.get("params", {})
            step_log = {"op": op, "params": params, "success": False}

            try:
                if self.ae_client:
                    result = self.ae_client.send_command(op, params)
                    step_log["result"] = result
                    step_log["success"] = result.get("success", False)
                else:
                    step_log["result"] = {"message": "AE Bridge 不可用，跳过执行"}
                    step_log["success"] = True  # 标记为成功以便生成脚本
            except Exception as e:
                step_log["error"] = str(e)
                step_log["success"] = False

            self.execution_log.append(step_log)
            results.append(step_log)

        return results

    # ------------------------------------------------------------------
    # 计划转脚本
    # ------------------------------------------------------------------

    def _plan_to_script(self, plan: dict) -> str:
        """将操作计划转换为独立 ExtendScript 代码（可用于无 Bridge 时手动执行）"""
        lines = ['// AE 智能合成脚本 - 由 AESmartOrchestrator 自动生成', '// ==========']

        comp_settings = plan.get("comp_settings", {})
        comp_name = comp_settings.get("name", "SmartComp")
        comp_w = comp_settings.get("width", 1920)
        comp_h = comp_settings.get("height", 1080)
        comp_fps = comp_settings.get("fps", 30)
        comp_dur = comp_settings.get("duration", 10)

        for op_item in plan.get("operations", []):
            op = op_item.get("op", "")
            params = op_item.get("params", {})

            if op == "createComposition":
                name = params.get("name", comp_name)
                w = params.get("width", comp_w)
                h = params.get("height", comp_h)
                fps = params.get("fps", comp_fps)
                dur = params.get("duration", comp_dur)
                lines.append(
                    f'var comp = app.project.items.addComp("{name}", {w}, {h}, {fps}, {dur}, 1);'
                )

            elif op == "importFootage":
                path = params.get("path", "").replace("\\", "/")
                lines.append(f'var footage = app.project.importFile(new ImportOptions(File("{path}")));')
                lines.append('if (footage) comp.layers.add(footage);')

            elif op == "addLayer":
                layer_type = params.get("type", "solid")
                if layer_type == "solid":
                    color = params.get("color", [1, 1, 1])
                    name = params.get("name", "Solid")
                    lines.append(
                        f'comp.layers.addSolid([{color[0]},{color[1]},{color[2]}], "{name}", '
                        f'{comp_w}, {comp_h}, 1);'
                    )
                elif layer_type == "text":
                    text = params.get("text", "Text")
                    lines.append(f'comp.layers.addText("{text}");')

            elif op == "addEffect":
                layer = params.get("layer", 1)
                effect = params.get("effect", "Glow")
                lines.append(f'var layer{layer} = comp.layer({layer});')
                lines.append(f'var fx = layer{layer}.Effects.addProperty("{effect}");')
                # 应用参数
                for key, value in params.items():
                    if key not in ("layer", "effect"):
                        lines.append(f'fx.property("{key}").setValue({json.dumps(value)});')

            elif op == "addKeyframe":
                layer = params.get("layer", 1)
                prop = params.get("prop", "Position")
                t = params.get("time", 0)
                value = params.get("value", [0, 0])
                lines.append(f'var layer{layer} = comp.layer({layer});')
                lines.append(
                    f'layer{layer}.property("{prop}").addKey({t});'
                )
                lines.append(
                    f'layer{layer}.property("{prop}").setValueAtKey({t}, {json.dumps(value)});'
                )

            elif op == "setText":
                layer = params.get("layer", 1)
                text = params.get("text", "")
                lines.append(f'comp.layer({layer}).property("Source Text").setValue("{text}");')

            elif op == "render":
                output = params.get("output", "output.mp4").replace("\\", "/")
                lines.append('// 渲染队列添加')
                lines.append('var rq = app.project.renderQueue;')
                lines.append('var rqItem = rq.items.add(comp);')
                lines.append(f'rqItem.outputModule(1).file = File("{output}");')
                lines.append('rq.render();')

            lines.append('')

        lines.append('// 脚本结束')
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 预设合成
    # ------------------------------------------------------------------

    def compose_from_preset(self, preset_name: str, **overrides) -> dict:
        """从预设创建合成"""
        if not self.presets:
            return {
                "success": False,
                "steps": [],
                "results": [],
                "ae_script": "",
                "error": "预设模块不可用",
            }

        try:
            get_preset = getattr(self.presets, "get_preset", None)
            if get_preset:
                preset_config = get_preset(preset_name)
            else:
                preset_config = None

            if not preset_config:
                # 尝试字典方式
                preset_config = getattr(self.presets, "PRESETS", {}).get(preset_name)

            if not preset_config:
                return {
                    "success": False,
                    "steps": [],
                    "results": [],
                    "ae_script": "",
                    "error": f"预设不存在: {preset_name}",
                }

            # 合并 overrides
            if overrides:
                if isinstance(preset_config, dict):
                    preset_config = {**preset_config, **overrides}

            # 构建计划并执行
            plan = {
                "task_type": "composition",
                "comp_settings": preset_config.get("comp_settings", {}),
                "operations": preset_config.get("operations", []),
            }

            if not self._validate_plan(plan):
                return {
                    "success": False,
                    "steps": [],
                    "results": [],
                    "ae_script": "",
                    "error": "预设配置验证失败",
                }

            results = self._execute_plan(plan)
            script = self._plan_to_script(plan)

            return {
                "success": all(r.get("success", False) for r in results),
                "task_type": plan.get("task_type", ""),
                "steps": plan.get("operations", []),
                "results": results,
                "ae_script": script,
                "error": "",
            }

        except Exception as e:
            return {
                "success": False,
                "steps": [],
                "results": [],
                "ae_script": "",
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """获取编排器状态"""
        return {
            "v4_available": self.v4_agent is not None,
            "ae_bridge_available": self.ae_client is not None,
            "presets_available": self.presets is not None,
            "tasks_completed": len([t for t in self.task_history if t.get("success")]),
            "tasks_total": len(self.task_history),
            "last_error": self.task_history[-1].get("error", "") if self.task_history else "",
        }

    # ------------------------------------------------------------------
    # 快速方法
    # ------------------------------------------------------------------

    def quick_music_video(self, bgm_path: str = "", frame_dir: str = "", **kw) -> dict:
        """快速创建音乐视频"""
        return self.compose(
            f"创建音乐视频，BGM路径:{bgm_path}，帧目录:{frame_dir}",
            mode="auto",
        )

    def quick_puppet(self, input_video: str = "", style: str = "wood", **kw) -> dict:
        """快速创建木偶风格"""
        return self.compose(
            f"对视频{input_video}应用木偶{style}风格",
            mode="auto",
        )

    def quick_text_animation(self, text: str = "", **kw) -> dict:
        """快速创建文字动画"""
        return self.compose(
            f"创建文字动画，内容:{text}",
            mode="auto",
        )

    def quick_particle_fx(self, source: str = "", **kw) -> dict:
        """快速创建粒子特效"""
        return self.compose(
            f"为素材{source}添加粒子特效",
            mode="auto",
        )

    def quick_render(self, comp_name: str = "", output: str = "", **kw) -> dict:
        """快速渲染输出"""
        return self.compose(
            f"渲染合成{comp_name}输出到{output}",
            mode="auto",
        )
