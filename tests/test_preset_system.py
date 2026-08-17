#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预设系统测试用例

运行方式：
    py -3.12 -m pytest tests/test_preset_system.py -v
"""

import pytest
import json
from typing import Dict, Any

from ae.preset_system import PresetSystem, Preset
from ae.preset_executor import PresetExecutor, PresetLibrary, initialize_default_combinations
from ae.ai_creative_planner import AICreativePlanner


class TestPresetSystem:
    """预设系统测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.preset_system = PresetSystem()

    def test_load_presets(self):
        """测试加载预设"""
        presets = self.preset_system.list_presets()
        assert len(presets) > 0

    def test_get_preset(self):
        """测试获取预设"""
        preset = self.preset_system.get_preset("douyin_bounce_title")
        assert preset is not None
        assert preset.name == "douyin_bounce_title"
        assert preset.category == "text_animation"

    def test_search_presets(self):
        """测试搜索预设"""
        presets = self.preset_system.search_presets("赛博朋克")
        assert len(presets) > 0
        assert any("cyberpunk" in preset.name.lower() for preset in presets)

    def test_list_presets_by_category(self):
        """测试按分类列出预设"""
        text_animations = self.preset_system.list_presets("text_animation")
        assert len(text_animations) > 0

    def test_get_category_info(self):
        """测试获取分类信息"""
        info = self.preset_system.get_category_info()
        assert "text_animation" in info
        assert "color_grading" in info
        assert "transition" in info


class TestPreset:
    """预设类测试"""

    def test_generate_jsx(self):
        """测试生成JSX脚本"""
        preset_system = PresetSystem()
        preset = preset_system.get_preset("douyin_bounce_title")
        assert preset is not None

        jsx = preset.generate_jsx(textLayerName="TEST", duration=2.0)
        assert isinstance(jsx, str)
        assert "TEST" in jsx
        assert "2.0" in jsx

    def test_validate_params(self):
        """测试参数验证"""
        preset_system = PresetSystem()
        preset = preset_system.get_preset("douyin_bounce_title")
        assert preset is not None

        params = preset.validate_params({"duration": 10.0, "intensity": 3.0})
        assert params["duration"] == 5.0
        assert params["intensity"] == 2.0

    def test_to_dict(self):
        """测试转换为字典"""
        preset_system = PresetSystem()
        preset = preset_system.get_preset("douyin_bounce_title")
        assert preset is not None

        data = preset.to_dict()
        assert "name" in data
        assert "category" in data
        assert "description" in data
        assert "parameters" in data

    def test_generate_jsx_with_list_params(self):
        """测试列表参数生成JSX（确保列表中字符串的空格不被移除）"""
        preset = Preset({
            'name': 'test_list_params',
            'script_template': 'var arr = ${items};',
            'default_values': {'items': ['hello world', 'foo bar']}
        })
        
        jsx = preset.generate_jsx()
        assert isinstance(jsx, str)
        assert '["hello world", "foo bar"]' in jsx
        assert '"helloworld"' not in jsx
        assert '"foobar"' not in jsx


class TestPresetExecutor:
    """预设执行器测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.preset_system = PresetSystem()
        self.executor = PresetExecutor(self.preset_system)

    def test_execute_preset_dry_run(self):
        """测试干运行模式执行预设"""
        result = self.executor.execute_preset("douyin_bounce_title", ae_client=None)
        assert result["success"] is True
        assert result["status"] == "dry_run"
        assert "jsx" in result

    def test_execute_preset_chain(self):
        """测试执行预设链"""
        result = self.executor.execute_preset_chain(
            ["douyin_bounce_title", "cyberpunk_grade"],
            ae_client=None,
            shared_params={"textLayerName": "TEST"},
        )
        assert result["total_presets"] == 2
        assert result["success_count"] == 2

    def test_search_and_execute(self):
        """测试搜索并执行"""
        result = self.executor.search_and_execute("赛博朋克", ae_client=None)
        assert result["success"] is True

    def test_get_preset_info(self):
        """测试获取预设信息"""
        info = self.executor.get_preset_info("douyin_bounce_title")
        assert info is not None
        assert info["name"] == "douyin_bounce_title"

    def test_list_presets_by_category(self):
        """测试按分类列出预设"""
        presets = self.executor.list_presets_by_category("text_animation")
        assert len(presets) > 0

    def test_execute_nonexistent_preset(self):
        """测试执行不存在的预设"""
        result = self.executor.execute_preset("nonexistent_preset_xyz", ae_client=None)
        assert result["success"] is False
        assert "error" in result
        assert "不存在" in result["error"]

    def test_execute_preset_with_ae_client_exception(self):
        """测试AE客户端异常时的处理"""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.run_script.side_effect = RuntimeError("AE connection failed")

        result = self.executor.execute_preset("douyin_bounce_title", ae_client=mock_client)
        assert result["success"] is False
        assert "error" in result
        assert "AE connection failed" in result["error"]
        assert "jsx" in result

    def test_execute_preset_with_ae_client_success(self):
        """测试AE客户端成功执行"""
        from unittest.mock import MagicMock
        mock_client = MagicMock()
        mock_client.run_script.return_value = {"status": "ok"}

        result = self.executor.execute_preset("douyin_bounce_title", ae_client=mock_client)
        assert result["success"] is True
        assert result["preset"] == "douyin_bounce_title"
        assert "category" in result
        assert "result" in result
        assert result["result"] == {"status": "ok"}

    def test_generate_combined_script(self):
        """测试生成组合脚本"""
        script = self.executor.generate_combined_script(
            ["douyin_bounce_title", "cyberpunk_grade"]
        )
        assert isinstance(script, str)
        assert "预设组合" in script
        assert len(script) > 0

    def test_generate_combined_script_with_nonexistent(self):
        """测试生成包含不存在预设的组合脚本"""
        script = self.executor.generate_combined_script(
            ["douyin_bounce_title", "nonexistent_preset"]
        )
        assert isinstance(script, str)
        assert "预设组合" in script

    def test_generate_combined_script_empty_list(self):
        """测试空列表生成组合脚本"""
        script = self.executor.generate_combined_script([])
        assert isinstance(script, str)

    def test_execute_preset_chain_with_failures(self):
        """测试预设链包含失败的情况"""
        result = self.executor.execute_preset_chain(
            ["douyin_bounce_title", "nonexistent_preset_xyz"],
            ae_client=None,
        )
        assert result["total_presets"] == 2
        assert result["success_count"] == 1
        assert result["failed_count"] == 1
        assert len(result["results"]) == 2

    def test_execute_preset_chain_empty_list(self):
        """测试空预设链"""
        result = self.executor.execute_preset_chain([], ae_client=None)
        assert result["total_presets"] == 0
        assert result["success_count"] == 0
        assert result["failed_count"] == 0
        assert result["results"] == []

    def test_search_and_execute_no_match(self):
        """测试搜索无匹配结果"""
        result = self.executor.search_and_execute("zzz_no_match_xyz_123", ae_client=None)
        assert result["success"] is False
        assert "error" in result
        assert "未找到" in result["error"]

    def test_get_preset_info_nonexistent(self):
        """测试获取不存在预设的信息"""
        info = self.executor.get_preset_info("nonexistent_preset_xyz")
        assert info is None

    def test_execute_preset_chain_with_per_preset_params(self):
        """测试带每个预设独立参数的预设链"""
        result = self.executor.execute_preset_chain(
            ["douyin_bounce_title", "cyberpunk_grade"],
            ae_client=None,
            shared_params={"duration": 3.0},
            per_preset_params={
                "douyin_bounce_title": {"textLayerName": "TITLE"},
                "cyberpunk_grade": {"intensity": 0.8},
            },
        )
        assert result["total_presets"] == 2
        assert result["success_count"] == 2


class TestPresetLibrary:
    """预设库测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.library = PresetLibrary()

    def test_list_combinations(self):
        """测试列出组合"""
        combinations = self.library.list_combinations()
        assert len(combinations) >= 0

    def test_create_combination(self):
        """测试创建组合"""
        combo = self.library.create_combination(
            "test_combo",
            "测试组合",
            ["douyin_bounce_title", "cyberpunk_grade"],
        )
        assert combo is not None
        assert combo.name == "test_combo"
        assert len(combo.presets) == 2

    def test_initialize_default_combinations(self):
        """测试初始化默认组合"""
        initialize_default_combinations(self.library)
        combinations = self.library.list_combinations()
        assert "cyberpunk_title_sequence" in combinations


class TestPresetIntegrationWithCreativePlanner:
    """预设系统与创意规划引擎集成测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.planner = AICreativePlanner(enable_presets=True)

    def test_list_presets(self):
        """测试列出预设"""
        presets = self.planner.list_presets()
        assert len(presets) > 0

    def test_search_presets(self):
        """测试搜索预设"""
        presets = self.planner.search_presets("打字机")
        assert len(presets) > 0

    def test_execute_preset(self):
        """测试执行预设"""
        result = self.planner.execute_preset("douyin_bounce_title")
        assert result["success"] is True

    def test_generate_preset_task_graph(self):
        """测试从预设生成任务图"""
        task_graph = self.planner.generate_preset_task_graph("douyin_bounce_title")
        assert "tasks" in task_graph
        assert len(task_graph["tasks"]) == 1

    def test_list_preset_combinations(self):
        """测试列出预设组合"""
        combinations = self.planner.list_preset_combinations()
        assert len(combinations) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
