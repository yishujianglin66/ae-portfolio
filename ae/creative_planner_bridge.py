#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 创意规划引擎 - Bridge 协议集成

提供创意规划相关的 Bridge 命令处理器，
使 AE MCP 扩展能够调用创意规划引擎。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:
    from ae.ai_creative_planner import AICreativePlanner
    from ae.creative_patterns import generate_task_graph, get_pattern_by_name
except ImportError:
    import sys
    sys.path.insert(0, str(__file__).rsplit("ae", 1)[0])
    from ae.ai_creative_planner import AICreativePlanner
    from ae.creative_patterns import generate_task_graph, get_pattern_by_name


class CreativePlannerBridge:
    """创意规划引擎的 Bridge 协议集成"""

    def __init__(self, llm_api_url: str = None, llm_api_key: str = None):
        self._planner = AICreativePlanner(
            llm_api_url=llm_api_url,
            llm_api_key=llm_api_key,
        )

    async def handle_command(self, command: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        处理创意规划相关的 Bridge 命令

        Args:
            command: 命令名称
            params: 命令参数

        Returns:
            命令执行结果
        """
        handlers = {
            "analyzeCreative": self._handle_analyze_creative,
            "generateTaskGraph": self._handle_generate_task_graph,
            "executeCreative": self._handle_execute_creative,
            "optimizeParameters": self._handle_optimize_parameters,
            "applyCreativePattern": self._handle_apply_creative_pattern,
            # 预设系统命令
            "listPresets": self._handle_list_presets,
            "listCategoryPresets": self._handle_list_category_presets,
            "searchPresets": self._handle_search_presets,
            "getPresetInfo": self._handle_get_preset_info,
            "executePreset": self._handle_execute_preset,
            "executePresetChain": self._handle_execute_preset_chain,
            "executeCombination": self._handle_execute_combination,
            "listCombinations": self._handle_list_combinations,
        }

        handler = handlers.get(command)
        if not handler:
            return {
                "status": "error",
                "error": f"Unknown command: {command}",
            }

        try:
            result = await handler(params)
            return {
                "status": "success",
                "data": result,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def _handle_analyze_creative(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        分析创意描述

        Args:
            params: {"description": "创意描述", "llmEnabled": False}

        Returns:
            分析结果
        """
        description = params.get("description", "")
        llm_enabled = params.get("llmEnabled", False)

        if llm_enabled and self._planner.llm_api_url:
            result = self._planner.parse_creative_description(description)
        else:
            result = self._planner._heuristic_analysis(description)

        return result

    async def _handle_generate_task_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        生成任务图

        Args:
            params: {"description": "创意描述", "patternName": "", "parameters": {}}

        Returns:
            任务图
        """
        description = params.get("description", "")
        pattern_name = params.get("patternName", "")
        custom_params = params.get("parameters", {})

        if pattern_name:
            task_graph = generate_task_graph(pattern_name, custom_params)
        else:
            analysis = self._planner.parse_creative_description(description)
            task_graph = analysis.get("task_graph", {})

            if custom_params:
                for task in task_graph.get("tasks", []):
                    task["params"] = {**task.get("params", {}), **custom_params}

        return task_graph

    async def _handle_execute_creative(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        执行创意任务图

        Args:
            params: {"taskGraph": {...}, "optimize": False}

        Returns:
            执行结果
        """
        task_graph = params.get("taskGraph", {})
        optimize = params.get("optimize", False)

        execution_result = self._planner.execute_task_graph(task_graph, ae_client=None)

        return {
            "task_graph": task_graph,
            "execution": execution_result,
        }

    async def _handle_optimize_parameters(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        优化参数

        Args:
            params: {"description": "优化描述", "currentParams": {}}

        Returns:
            优化后的参数
        """
        description = params.get("description", "")
        current_params = params.get("currentParams", {})

        optimized = self._planner.optimize_parameters(description, current_params)

        return {
            "optimized_params": optimized,
            "reasoning": "参数优化完成",
        }

    async def _handle_apply_creative_pattern(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        应用创意模式

        Args:
            params: {"patternName": "模式名称", "compName": "", "parameters": {}}

        Returns:
            任务图和执行结果
        """
        pattern_name = params.get("patternName", "")
        comp_name = params.get("compName", "")
        custom_params = params.get("parameters", {})

        pattern = get_pattern_by_name(pattern_name)
        if not pattern:
            return {
                "error": f"Unknown pattern: {pattern_name}",
            }

        task_graph = generate_task_graph(pattern_name, custom_params)

        if comp_name:
            task_graph["project"] = comp_name

        execution_result = self._planner.execute_task_graph(task_graph, ae_client=None)

        return {
            "pattern": pattern_name,
            "task_graph": task_graph,
            "execution": execution_result,
        }

    def get_available_patterns(self) -> dict[str, Any]:
        """获取所有可用的创意模式"""
        patterns = self._planner.list_available_patterns()
        return {"patterns": patterns}

    # ============================================================
    # 预设系统命令处理器
    # ============================================================

    async def _handle_list_presets(self, params: dict[str, Any]) -> dict[str, Any]:
        """列出所有预设分类"""
        if not hasattr(self._planner, "preset_system"):
            return {"error": "预设系统未启用"}
        info = self._planner.preset_system.get_category_info()
        return {"categories": info}

    async def _handle_list_category_presets(self, params: dict[str, Any]) -> dict[str, Any]:
        """按分类列出预设"""
        category = params.get("category", "")
        if not hasattr(self._planner, "preset_system"):
            return {"error": "预设系统未启用"}
        presets = self._planner.preset_system.list_presets(category)
        preset_list = []
        for name in presets:
            preset = self._planner.preset_system.get_preset(name)
            if preset:
                preset_list.append({
                    "name": preset.name,
                    "description": preset.description,
                    "tags": preset.tags,
                })
        return {"category": category, "presets": preset_list, "count": len(preset_list)}

    async def _handle_search_presets(self, params: dict[str, Any]) -> dict[str, Any]:
        """搜索预设"""
        keyword = params.get("keyword", "")
        if not hasattr(self._planner, "preset_system"):
            return {"error": "预设系统未启用"}
        results = self._planner.preset_system.search_presets(keyword)
        return {
            "keyword": keyword,
            "results": [
                {
                    "name": p.name,
                    "category": p.category,
                    "description": p.description,
                    "tags": p.tags,
                }
                for p in results
            ],
            "count": len(results),
        }

    async def _handle_get_preset_info(self, params: dict[str, Any]) -> dict[str, Any]:
        """获取预设详细信息"""
        preset_name = params.get("presetName", "")
        if not hasattr(self._planner, "preset_system"):
            return {"error": "预设系统未启用"}
        info = self._planner.preset_executor.get_preset_info(preset_name)
        if info:
            return info
        return {"error": f"预设不存在: {preset_name}"}

    async def _handle_execute_preset(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行单个预设"""
        preset_name = params.get("presetName", "")
        override_params = params.get("params", {})
        if not hasattr(self._planner, "preset_executor"):
            return {"error": "预设系统未启用"}
        result = self._planner.preset_executor.execute_preset(
            preset_name, ae_client=None, **override_params
        )
        return result

    async def _handle_execute_preset_chain(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行预设链"""
        preset_names = params.get("presetNames", [])
        shared_params = params.get("sharedParams", {})
        if not hasattr(self._planner, "preset_executor"):
            return {"error": "预设系统未启用"}
        result = self._planner.preset_executor.execute_preset_chain(
            preset_names, ae_client=None, shared_params=shared_params
        )
        return result

    async def _handle_execute_combination(self, params: dict[str, Any]) -> dict[str, Any]:
        """执行预设组合"""
        combo_name = params.get("combinationName", "")
        override_params = params.get("params", {})
        if not hasattr(self._planner, "preset_library"):
            return {"error": "预设系统未启用"}
        combo = self._planner.preset_library.get_combination(combo_name)
        if not combo:
            return {"error": f"预设组合不存在: {combo_name}"}
        all_params = {**(combo.parameters or {}), **override_params}
        result = self._planner.preset_executor.execute_preset_chain(
            combo.presets, ae_client=None, shared_params=all_params
        )
        return {"combination": combo_name, "description": combo.description, **result}

    async def _handle_list_combinations(self, params: dict[str, Any]) -> dict[str, Any]:
        """列出预设组合"""
        if not hasattr(self._planner, "preset_library"):
            return {"error": "预设系统未启用"}
        combos = self._planner.preset_library.list_combinations()
        combo_list = []
        for name in combos:
            combo = self._planner.preset_library.get_combination(name)
            if combo:
                combo_list.append({
                    "name": combo.name,
                    "description": combo.description,
                    "presets": combo.presets,
                })
        return {"combinations": combo_list, "count": len(combo_list)}


def create_creative_planner_bridge(llm_api_url: str = None, llm_api_key: str = None) -> CreativePlannerBridge:
    """创建创意规划 Bridge 实例"""
    return CreativePlannerBridge(llm_api_url=llm_api_url, llm_api_key=llm_api_key)


async def main():
    """测试入口"""
    import asyncio

    bridge = create_creative_planner_bridge()

    test_cases = [
        ("analyzeCreative", {"description": "赛博朋克风格文字浮现", "llmEnabled": False}),
        ("generateTaskGraph", {"description": "霓虹发光片头"}),
        ("applyCreativePattern", {"patternName": "style_cyberpunk", "parameters": {"text": "TEST"}}),
    ]

    for command, params in test_cases:
        print(f"\n--- 测试命令: {command} ---")
        print(f"参数: {params}")
        result = await bridge.handle_command(command, params)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
