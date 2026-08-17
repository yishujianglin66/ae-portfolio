#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 CreativePlannerBridge 命令分发协议
========================================

覆盖 ae/creative_planner_bridge.py 的关键契约：

1. 未知命令返回 error 包装（不能抛 KeyError 给 MCP 客户端）
2. handler 抛异常时返回 error 包装（不能冒泡破坏 MCP 通道）
3. 成功路径返回 status=success + data 字段
4. applyCreativePattern 不存在的 pattern 返回 error
5. listPresets / searchPresets / getPresetInfo 与预设系统交互
6. getAvailablePatterns 返回 patterns 字段
7. create_creative_planner_bridge 工厂函数
8. 状态机：一个 handler 抛异常后 bridge 仍能继续处理新命令

注：测试用 mock AICreativePlanner 的方式隔离 Bridge 协议层，
    避免被底层 SubtitleSystem kwargs 不匹配问题干扰。
"""
from __future__ import annotations

import json
import pytest
from typing import Any, Dict
from unittest.mock import MagicMock, AsyncMock, patch


# ============================================================
# 工具：构造一个可用的 bridge（mock 掉底层 planner）
# ============================================================
def _make_planner_mock():
    """构造 AICreativePlanner 的最小可用 mock。

    关键方法都是 AsyncMock 或 MagicMock，
    `llm_api_url` / `llm_api_key` 属性可设置。
    """
    planner = MagicMock()
    planner.llm_api_url = None
    planner.llm_api_key = None
    # 内部调用可能用到的协程方法
    planner.parse_creative_description = MagicMock(return_value={
        "description": "test",
        "task_graph": {"tasks": []},
    })

    def _heuristic(desc):
        # 把传入的描述回填到结果里，便于断言
        return {
            "description": desc,
            "task_graph": {"tasks": []},
            "source": "heuristic",
        }

    planner._heuristic_analysis = MagicMock(side_effect=_heuristic)
    planner.optimize_parameters = MagicMock(return_value={"x": 1})
    planner.execute_task_graph = MagicMock(return_value={"status": "ok"})
    planner.list_available_patterns = MagicMock(return_value=["style_cyberpunk"])
    # 预设系统相关
    planner.preset_system = MagicMock()
    planner.preset_system.get_category_info = MagicMock(return_value={"a": 1})
    planner.preset_system.list_presets = MagicMock(return_value=["p1"])
    planner.preset_system.search_presets = MagicMock(return_value=[])
    planner.preset_system.get_preset = MagicMock(return_value=None)
    planner.preset_executor = MagicMock()
    planner.preset_executor.get_preset_info = MagicMock(return_value=None)
    planner.preset_executor.execute_preset = MagicMock(return_value={"ok": True})
    planner.preset_executor.execute_preset_chain = MagicMock(return_value={"ok": True})
    planner.preset_library = MagicMock()
    planner.preset_library.list_combinations = MagicMock(return_value=[])
    planner.preset_library.get_combination = MagicMock(return_value=None)
    return planner


@pytest.fixture
def bridge():
    """用 mock planner 构造 Bridge，绕开底层 SubtitleSystem kwargs 不匹配问题。"""
    from ae.creative_planner_bridge import CreativePlannerBridge

    planner = _make_planner_mock()
    b = CreativePlannerBridge.__new__(CreativePlannerBridge)
    b._planner = planner
    return b


# ============================================================
# 工厂
# ============================================================
class TestFactory:
    def test_create_returns_bridge(self):
        from ae.creative_planner_bridge import (
            create_creative_planner_bridge,
            CreativePlannerBridge,
        )
        # 通过 mock AICreativePlanner 验证工厂包装
        with patch("ae.creative_planner_bridge.AICreativePlanner") as MockPlanner:
            MockPlanner.return_value = MagicMock()
            bridge = create_creative_planner_bridge()
        assert isinstance(bridge, CreativePlannerBridge)
        assert MockPlanner.called

    def test_create_passes_args(self):
        """LLM URL/Key 透传给底层 planner。"""
        from ae.creative_planner_bridge import create_creative_planner_bridge

        with patch("ae.creative_planner_bridge.AICreativePlanner") as MockPlanner:
            MockPlanner.return_value = MagicMock()
            create_creative_planner_bridge(
                llm_api_url="http://test/llm",
                llm_api_key="test-key",
            )
        call_kwargs = MockPlanner.call_args.kwargs
        assert call_kwargs["llm_api_url"] == "http://test/llm"
        assert call_kwargs["llm_api_key"] == "test-key"


# ============================================================
# 命令分发的协议层
# ============================================================
class TestHandleCommandProtocol:
    """handle_command 必须包裹 status/data/error 字段。"""

    @pytest.mark.asyncio
    async def test_unknown_command_returns_error(self, bridge):
        result = await bridge.handle_command("nonExistentCmd", {})
        assert result["status"] == "error"
        assert "Unknown command" in result["error"]
        assert "nonExistentCmd" in result["error"]
        # 错误时不应有 data 字段
        assert "data" not in result

    @pytest.mark.asyncio
    async def test_known_command_returns_success_envelope(self, bridge):
        result = await bridge.handle_command("listPresets", {})
        assert result["status"] == "success"
        assert "data" in result
        assert "categories" in result["data"]

    @pytest.mark.asyncio
    async def test_handler_exception_wrapped_as_error(self, bridge):
        """handler 抛异常时 handle_command 必须捕获并返回 error 包装。

        否则会破坏 MCP 通道（AE 端整个 panel 卡死）。
        """
        with patch.object(bridge, "_handle_list_presets", side_effect=RuntimeError("boom")):
            result = await bridge.handle_command("listPresets", {})
        assert result["status"] == "error"
        assert "boom" in result["error"]
        # 错误时不应有 data 字段
        assert "data" not in result

    @pytest.mark.asyncio
    async def test_handler_type_error_wrapped(self, bridge):
        with patch.object(bridge, "_handle_search_presets", side_effect=TypeError("wrong arg")):
            result = await bridge.handle_command("searchPresets", {"keyword": "x"})
        assert result["status"] == "error"
        assert "wrong arg" in result["error"]


# ============================================================
# analyzeCreative
# ============================================================
class TestAnalyzeCreative:
    @pytest.mark.asyncio
    async def test_heuristic_when_llm_disabled(self, bridge):
        result = await bridge.handle_command(
            "analyzeCreative",
            {"description": "霓虹发光片头", "llmEnabled": False},
        )
        assert result["status"] == "success"
        data = result["data"]
        assert "description" in data
        assert data["description"] == "霓虹发光片头"
        # 走 heuristic_analysis，不是 parse_creative_description
        assert bridge._planner._heuristic_analysis.called
        assert not bridge._planner.parse_creative_description.called

    @pytest.mark.asyncio
    async def test_heuristic_when_llm_enabled_but_no_url(self, bridge):
        """llmEnabled=True 但无 URL 时退化为启发式（不能崩）。"""
        bridge._planner.llm_api_url = None
        result = await bridge.handle_command(
            "analyzeCreative",
            {"description": "赛博朋克风", "llmEnabled": True},
        )
        # 无 URL 时走启发式
        assert result["status"] == "success"
        assert bridge._planner._heuristic_analysis.called

    @pytest.mark.asyncio
    async def test_uses_parse_when_llm_enabled_and_url_present(self, bridge):
        """llmEnabled=True 且有 URL 时走 parse_creative_description。"""
        bridge._planner.llm_api_url = "http://llm/parse"
        result = await bridge.handle_command(
            "analyzeCreative",
            {"description": "X", "llmEnabled": True},
        )
        assert result["status"] == "success"
        assert bridge._planner.parse_creative_description.called

    @pytest.mark.asyncio
    async def test_empty_description_handled(self, bridge):
        result = await bridge.handle_command(
            "analyzeCreative", {"description": "", "llmEnabled": False}
        )
        # 即便空字符串也不抛
        assert result["status"] == "success"


# ============================================================
# generateTaskGraph
# ============================================================
class TestGenerateTaskGraph:
    @pytest.mark.asyncio
    async def test_with_pattern_name_calls_generate(self, bridge):
        with patch("ae.creative_planner_bridge.generate_task_graph") as mock_gen:
            mock_gen.return_value = {"tasks": [{"id": "t1"}]}
            result = await bridge.handle_command(
                "generateTaskGraph",
                {"description": "test", "patternName": "style_cyberpunk", "parameters": {}},
            )
        assert result["status"] == "success"
        assert mock_gen.called
        assert "tasks" in result["data"]

    @pytest.mark.asyncio
    async def test_with_description_only_uses_parse(self, bridge):
        result = await bridge.handle_command(
            "generateTaskGraph", {"description": "霓虹文字"}
        )
        assert result["status"] == "success"
        # 走 parse_creative_description
        assert bridge._planner.parse_creative_description.called

    @pytest.mark.asyncio
    async def test_custom_params_merged_into_tasks(self, bridge):
        bridge._planner.parse_creative_description.return_value = {
            "task_graph": {
                "tasks": [{"id": "t1", "params": {"existing": 1}}],
            }
        }
        result = await bridge.handle_command(
            "generateTaskGraph",
            {
                "description": "X",
                "parameters": {"override": 2, "new_key": 3},
            },
        )
        assert result["status"] == "success"
        task = result["data"]["tasks"][0]
        # 原有参数保留
        assert task["params"]["existing"] == 1
        # 新参数被合并
        assert task["params"]["override"] == 2
        assert task["params"]["new_key"] == 3


# ============================================================
# applyCreativePattern
# ============================================================
class TestApplyCreativePattern:
    @pytest.mark.asyncio
    async def test_unknown_pattern_returns_data_error(self, bridge):
        with patch("ae.creative_planner_bridge.get_pattern_by_name", return_value=None):
            result = await bridge.handle_command(
                "applyCreativePattern",
                {"patternName": "totally_fake_pattern_xyz", "parameters": {}},
            )
        # handle_command 把 data 包在 status=success 里，但 data 内部含 error 字段
        assert result["status"] == "success"
        assert "error" in result["data"]
        assert "Unknown pattern" in result["data"]["error"]

    @pytest.mark.asyncio
    async def test_known_pattern_succeeds(self, bridge):
        with patch("ae.creative_planner_bridge.get_pattern_by_name", return_value={"name": "x"}), \
             patch("ae.creative_planner_bridge.generate_task_graph", return_value={"tasks": []}):
            result = await bridge.handle_command(
                "applyCreativePattern",
                {"patternName": "style_cyberpunk", "parameters": {"text": "X"}},
            )
        assert result["status"] == "success"
        data = result["data"]
        assert "pattern" in data
        assert "task_graph" in data
        assert "execution" in data
        assert data["pattern"] == "style_cyberpunk"

    @pytest.mark.asyncio
    async def test_comp_name_added_to_project_field(self, bridge):
        with patch("ae.creative_planner_bridge.get_pattern_by_name", return_value={"name": "x"}), \
             patch("ae.creative_planner_bridge.generate_task_graph", return_value={"tasks": []}):
            result = await bridge.handle_command(
                "applyCreativePattern",
                {"patternName": "x", "compName": "MyComp", "parameters": {}},
            )
        assert result["status"] == "success"
        assert result["data"]["task_graph"]["project"] == "MyComp"

    @pytest.mark.asyncio
    async def test_no_comp_name_leaves_project_unchanged(self, bridge):
        with patch("ae.creative_planner_bridge.get_pattern_by_name", return_value={"name": "x"}), \
             patch("ae.creative_planner_bridge.generate_task_graph", return_value={"tasks": [{"id": "t"}], "project": "default_proj"}):
            result = await bridge.handle_command(
                "applyCreativePattern",
                {"patternName": "x", "parameters": {}},
            )
        assert result["status"] == "success"
        # 不传 compName 时 project 保持 generate_task_graph 返回值
        assert result["data"]["task_graph"]["project"] == "default_proj"


# ============================================================
# getAvailablePatterns
# ============================================================
class TestGetAvailablePatterns:
    def test_returns_patterns_field(self, bridge):
        info = bridge.get_available_patterns()
        assert "patterns" in info
        assert isinstance(info["patterns"], list)

    def test_returns_listed_patterns(self, bridge):
        bridge._planner.list_available_patterns.return_value = [
            "style_cyberpunk", "neon_glow"
        ]
        info = bridge.get_available_patterns()
        assert "style_cyberpunk" in info["patterns"]
        assert "neon_glow" in info["patterns"]


# ============================================================
# 预设系统命令
# ============================================================
class TestPresetCommands:
    @pytest.mark.asyncio
    async def test_list_presets(self, bridge):
        result = await bridge.handle_command("listPresets", {})
        assert result["status"] == "success"
        assert "categories" in result["data"]

    @pytest.mark.asyncio
    async def test_list_category_presets(self, bridge):
        # 构造一个 fake preset 对象
        fake_preset = MagicMock()
        fake_preset.name = "p1"
        fake_preset.description = "d1"
        fake_preset.tags = ["t1", "t2"]
        bridge._planner.preset_system.list_presets.return_value = ["p1"]
        bridge._planner.preset_system.get_preset.return_value = fake_preset

        result = await bridge.handle_command(
            "listCategoryPresets", {"category": "effect"}
        )
        assert result["status"] == "success"
        assert result["data"]["category"] == "effect"
        assert result["data"]["count"] == 1
        assert result["data"]["presets"][0]["name"] == "p1"
        assert result["data"]["presets"][0]["tags"] == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_search_presets_empty_keyword(self, bridge):
        result = await bridge.handle_command("searchPresets", {"keyword": ""})
        assert result["status"] == "success"
        assert "results" in result["data"]
        assert "count" in result["data"]

    @pytest.mark.asyncio
    async def test_search_presets_keyword(self, bridge):
        result = await bridge.handle_command("searchPresets", {"keyword": "neon"})
        assert result["status"] == "success"
        # 搜索逻辑交给预设系统，这里只验证包装
        assert "results" in result["data"]

    @pytest.mark.asyncio
    async def test_search_returns_preset_fields(self, bridge):
        fake_preset = MagicMock()
        fake_preset.name = "neon_glow"
        fake_preset.category = "effect"
        fake_preset.description = "霓虹发光"
        fake_preset.tags = ["glow", "neon"]
        bridge._planner.preset_system.search_presets.return_value = [fake_preset]

        result = await bridge.handle_command("searchPresets", {"keyword": "neon"})
        assert result["status"] == "success"
        assert result["data"]["count"] == 1
        assert result["data"]["results"][0]["name"] == "neon_glow"
        assert result["data"]["results"][0]["tags"] == ["glow", "neon"]

    @pytest.mark.asyncio
    async def test_get_preset_info_missing_returns_data_error(self, bridge):
        bridge._planner.preset_executor.get_preset_info.return_value = None
        result = await bridge.handle_command(
            "getPresetInfo", {"presetName": "non_existent_preset_xyz"}
        )
        # 不存在的预设应返回 error（不抛异常）
        assert result["status"] == "success"
        assert "error" in result["data"]
        assert "non_existent_preset_xyz" in result["data"]["error"]

    @pytest.mark.asyncio
    async def test_execute_preset_calls_executor(self, bridge):
        bridge._planner.preset_executor.execute_preset.return_value = {
            "success": True, "preset": "neon_glow"
        }
        result = await bridge.handle_command(
            "executePreset",
            {"presetName": "neon_glow", "params": {"color": "blue"}},
        )
        assert result["status"] == "success"
        assert result["data"]["success"] is True
        # 确认参数已透传
        call = bridge._planner.preset_executor.execute_preset.call_args
        assert call.args[0] == "neon_glow"
        assert call.kwargs.get("color") == "blue" or "blue" in (call.kwargs or {}).values()

    @pytest.mark.asyncio
    async def test_execute_preset_chain(self, bridge):
        bridge._planner.preset_executor.execute_preset_chain.return_value = {
            "success": True, "executed": ["p1", "p2"]
        }
        result = await bridge.handle_command(
            "executePresetChain",
            {"presetNames": ["p1", "p2"], "sharedParams": {"x": 1}},
        )
        assert result["status"] == "success"
        assert result["data"]["executed"] == ["p1", "p2"]

    @pytest.mark.asyncio
    async def test_execute_combination_missing(self, bridge):
        bridge._planner.preset_library.get_combination.return_value = None
        result = await bridge.handle_command(
            "executeCombination", {"combinationName": "neon_sign"}
        )
        assert result["status"] == "success"
        assert "error" in result["data"]
        assert "neon_sign" in result["data"]["error"]

    @pytest.mark.asyncio
    async def test_list_combinations(self, bridge):
        result = await bridge.handle_command("listCombinations", {})
        assert result["status"] == "success"
        assert "combinations" in result["data"]
        assert "count" in result["data"]


# ============================================================
# 状态机：handler 内部异常不污染后续调用
# ============================================================
class TestStateAfterError:
    @pytest.mark.asyncio
    async def test_bridge_reusable_after_handler_error(self, bridge):
        """一个 handler 抛异常后，bridge 仍能继续处理新命令。"""
        with patch.object(bridge, "_handle_list_presets", side_effect=RuntimeError("oops")):
            r1 = await bridge.handle_command("listPresets", {})
        assert r1["status"] == "error"
        # 再次调用应恢复正常
        r2 = await bridge.handle_command("listPresets", {})
        assert r2["status"] == "success"

    @pytest.mark.asyncio
    async def test_bridge_reusable_after_unknown_command(self, bridge):
        r1 = await bridge.handle_command("unknown1", {})
        r2 = await bridge.handle_command("unknown2", {})
        assert r1["status"] == "error"
        assert r2["status"] == "error"
        # 后续正常命令仍可执行
        r3 = await bridge.handle_command("listPresets", {})
        assert r3["status"] == "success"


# ============================================================
# 集成 smoke：end-to-end 协议形状
# ============================================================
class TestProtocolShape:
    """确认成功 / 失败 / 异常三种响应都符合协议形状。"""

    @pytest.mark.asyncio
    async def test_success_shape(self, bridge):
        r = await bridge.handle_command("listPresets", {})
        assert set(r.keys()) >= {"status", "data"}
        assert r["status"] == "success"

    @pytest.mark.asyncio
    async def test_error_shape(self, bridge):
        r = await bridge.handle_command("unknown", {})
        assert set(r.keys()) >= {"status", "error"}
        assert r["status"] == "error"

    @pytest.mark.asyncio
    async def test_exception_shape(self, bridge):
        with patch.object(bridge, "_handle_list_presets", side_effect=ValueError("v")):
            r = await bridge.handle_command("listPresets", {})
        assert set(r.keys()) >= {"status", "error"}
        assert r["status"] == "error"
