#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 创意规划引擎测试用例

运行方式：
    py -3.12 -m pytest tests/test_ai_creative_planner.py -v
"""

import pytest
import json
from typing import Dict, Any

from ae.ai_creative_planner import AICreativePlanner
from ae.creative_patterns import (
    CREATIVE_PATTERNS,
    find_patterns_by_keyword,
    get_pattern_by_name,
    generate_task_graph,
)
from ae.prompt_templates import (
    get_template,
    list_templates,
    build_creative_analysis_prompt,
)
from ae.creative_planner_bridge import CreativePlannerBridge


class TestCreativePatterns:
    """创意模式库测试"""

    def test_patterns_are_defined(self):
        """测试创意模式已定义"""
        assert len(CREATIVE_PATTERNS) > 0

    def test_find_patterns_by_keyword(self):
        """测试关键词匹配"""
        patterns = find_patterns_by_keyword("赛博朋克")
        assert len(patterns) > 0

    def test_get_pattern_by_name(self):
        """测试按名称获取模式"""
        pattern = get_pattern_by_name("style_cyberpunk")
        assert pattern is not None
        assert pattern.name == "style_cyberpunk"

    def test_generate_task_graph(self):
        """测试生成任务图"""
        task_graph = generate_task_graph("style_cyberpunk", {"text": "TEST"})
        assert "tasks" in task_graph
        assert len(task_graph["tasks"]) > 0


class TestPromptTemplates:
    """提示词模板测试"""

    def test_templates_are_defined(self):
        """测试模板已定义"""
        templates = list_templates()
        assert len(templates) > 0

    def test_get_template(self):
        """测试获取模板"""
        template = get_template("creative_analysis")
        assert template is not None
        assert template.name == "creative_analysis"

    def test_build_creative_analysis_prompt(self):
        """测试构建创意分析提示词"""
        prompt = build_creative_analysis_prompt("赛博朋克风格文字")
        assert "system" in prompt
        assert "user" in prompt
        assert "赛博朋克风格文字" in prompt["user"]


class TestAICreativePlanner:
    """AI 创意规划引擎测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.planner = AICreativePlanner()

    def test_parse_creative_description(self):
        """测试解析创意描述"""
        result = self.planner.parse_creative_description("赛博朋克风格文字浮现")
        assert "analysis" in result
        assert "task_graph" in result
        analysis = result["analysis"]
        assert "patterns" in analysis
        assert "confidence" in analysis

    def test_heuristic_analysis(self):
        """测试启发式分析"""
        result = self.planner._heuristic_analysis("打字机效果")
        assert "analysis" in result
        assert "task_graph" in result
        assert "typewriter" in result["analysis"]["animations"]

    def test_extract_text_from_description(self):
        """测试从描述中提取文字"""
        text = self.planner._extract_text_from_description('创建文字"HELLO WORLD"')
        assert text == "HELLO WORLD"

    def test_extract_duration(self):
        """测试提取时长"""
        duration = self.planner._extract_duration("动画持续5秒")
        assert duration == 5.0

    def test_extract_keywords(self):
        """测试提取关键词"""
        keywords = self.planner._extract_keywords("赛博朋克风格文字浮现")
        assert "赛博朋克" in keywords

    def test_execute_task_graph(self):
        """测试执行任务图（干运行模式）"""
        task_graph = {
            "project": "TestProject",
            "duration": 5,
            "pattern": "style_cyberpunk",
            "tasks": [
                {
                    "id": "task_1",
                    "name": "test_task",
                    "type": "ae_script",
                    "script": "addTextLayer",
                    "params": {"text": "TEST"},
                    "dependencies": [],
                }
            ],
        }
        result = self.planner.execute_task_graph(task_graph)
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["success"] is True

    def test_list_available_patterns(self):
        """测试列出可用模式"""
        patterns = self.planner.list_available_patterns()
        assert len(patterns) > 0


class TestCreativePlannerBridge:
    """创意规划 Bridge 测试"""

    @pytest.mark.asyncio
    async def test_handle_analyze_creative(self):
        """测试处理分析创意命令"""
        bridge = CreativePlannerBridge()
        result = await bridge.handle_command(
            "analyzeCreative",
            {"description": "赛博朋克风格", "llmEnabled": False},
        )
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_generate_task_graph(self):
        """测试处理生成任务图命令"""
        bridge = CreativePlannerBridge()
        result = await bridge.handle_command(
            "generateTaskGraph",
            {"description": "霓虹发光片头"},
        )
        assert result["status"] == "success"
        assert "tasks" in result["data"]

    @pytest.mark.asyncio
    async def test_handle_apply_creative_pattern(self):
        """测试处理应用创意模式命令"""
        bridge = CreativePlannerBridge()
        result = await bridge.handle_command(
            "applyCreativePattern",
            {"patternName": "style_cyberpunk", "parameters": {"text": "TEST"}},
        )
        assert result["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
