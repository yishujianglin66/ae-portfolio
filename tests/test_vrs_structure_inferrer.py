#!/usr/bin/env python3
"""
test_vrs_structure_inferrer.py — VRS 合成结构推断器回归测试

测试重点（覆盖 2026-07-20 VRS Phase 2 修复）：
1. parse_structure_blueprint() 的 JSON 控制字符清理（两级降级）
   - 历史问题：LLM 输出常含 \x00-\x1f 非法控制字符导致 json.loads 失败
   - 修复：先整体清理，失败再逐行清理后重新拼接
2. _extract_json_block() 三种代码块提取策略
3. _build_fallback_blueprint() 降级路径总能返回可执行结构
4. _validate_and_complete_blueprint() 字段补全与类型规范化
5. 空响应 / 非 dict 解析结果 / 异常输入的边界情况

回归原因：
- VRS v2.0 端到端运行中曾因 LLM 输出含 \x0b \x0c 等控制字符导致
  结构蓝图解析失败，进而整个流程降级为简化结构，丢失多图层信息。
- 该解析路径是 VRS 流水线的关键节点，无测试覆盖即等于"裸奔"。
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "vrs"))

# 检查被测模块是否可用
try:
    from vrs.vrs_structure_inferrer import (
        DEFAULT_COMP,
        SUPPORTED_BLEND_MODES,
        SUPPORTED_LAYER_TYPES,
        CompositionStructureInferrer,
    )
    HAS_INFERRER = True
except ImportError:
    HAS_INFERRER = False

pytestmark = pytest.mark.skipif(
    not HAS_INFERRER,
    reason="vrs.vrs_structure_inferrer 不可用（依赖缺失）",
)


@pytest.fixture
def inferrer():
    """构造一个不写磁盘的结构推断器实例"""
    return CompositionStructureInferrer(output_dir=Path(os.devnull))


# =============================================================================
# 1. parse_structure_blueprint — JSON 控制字符清理（核心修复点）
# =============================================================================

class TestParseStructureBlueprintControlCharCleanup:
    """覆盖 vrs_structure_inferrer.py 第 444-463 行的两级清理降级"""

    def test_clean_json_response_with_control_chars(self, inferrer):
        """LLM 输出含 \x0b \x0c 等控制字符时，第一级清理应成功解析"""
        # 构造带控制字符的 JSON（模拟真实 LLM 输出）
        raw = (
            '```json\n'
            '{"composition": {"name": "Test\x0bComp"}, '
            '"layers": [{"index": 1, "name": "L1\x0c"}], '
            '"reasoning": "ok"}\n'
            '```'
        )
        blueprint = inferrer.parse_structure_blueprint(raw)
        # 应该成功解析（控制字符被替换为空格），不降级
        assert blueprint["composition"]["name"] == "Test\x0bComp" or \
               blueprint["composition"]["name"] == "Test Comp" or \
               blueprint["composition"]["name"] == "Test\x0bComp".replace("\x0b", " ")
        assert "layers" in blueprint
        assert len(blueprint["layers"]) == 1

    def test_cleanup_preserves_valid_escaped_chars(self, inferrer):
        """清理不能误伤合法的 \\n \\t 转义序列"""
        raw = (
            '```json\n'
            '{"reasoning": "line1\\nline2\\ttab", "layers": []}\n'
            '```'
        )
        blueprint = inferrer.parse_structure_blueprint(raw)
        assert "line1\nline2\ttab" == blueprint["reasoning"]

    def test_two_level_degradation_when_first_clean_fails(self, inferrer):
        """第一级整体清理失败时，逐行清理应作为兜底"""
        # 构造一个第一级清理后仍无效，但逐行清理后能恢复的 JSON
        # 这里通过构造一个含尾随逗号（无效 JSON）+ 控制字符的场景
        # 由于尾随逗号无法被清理修复，最终应降级到 fallback
        raw = (
            '```json\n'
            '{"layers": [{"name": "L1\x0b",},], }\n'
            '```'
        )
        blueprint = inferrer.parse_structure_blueprint(raw)
        # 两种合法结局：要么逐行清理成功（极少数情况），要么降级 fallback
        # 关键断言：不抛异常 + 返回 dict + 含 composition/layers 字段
        assert isinstance(blueprint, dict)
        assert "composition" in blueprint
        assert "layers" in blueprint
        assert isinstance(blueprint["layers"], list)

    def test_empty_response_returns_fallback(self, inferrer):
        """空字符串响应应返回降级简化结构"""
        blueprint = inferrer.parse_structure_blueprint("")
        assert isinstance(blueprint, dict)
        assert "composition" in blueprint
        assert "layers" in blueprint
        # fallback 至少包含调色调整层 + 主体素材层
        assert len(blueprint["layers"]) >= 2

    def test_no_json_block_returns_fallback(self, inferrer):
        """响应中无 JSON 块时返回降级结构"""
        blueprint = inferrer.parse_structure_blueprint("纯文本说明，没有任何 JSON")
        assert isinstance(blueprint, dict)
        assert "layers" in blueprint
        assert len(blueprint["layers"]) >= 2  # fallback 双层

    def test_valid_json_without_codeblock(self, inferrer):
        """裸 JSON（无 ```json 包裹）应能被第三种策略提取"""
        raw = '{"composition": {"name": "Bare"}, "layers": [], "reasoning": "bare"}'
        blueprint = inferrer.parse_structure_blueprint(raw)
        assert blueprint["composition"]["name"] == "Bare"
        assert blueprint["layers"] == []

    def test_completely_invalid_json_returns_fallback(self, inferrer):
        """完全无法解析的 JSON 块应优雅降级"""
        raw = '```json\n{this is not json at all!!!\n```'
        blueprint = inferrer.parse_structure_blueprint(raw)
        assert isinstance(blueprint, dict)
        assert "composition" in blueprint
        assert "layers" in blueprint

    def test_non_dict_json_returns_fallback(self, inferrer):
        """解析得到非 dict（如数组、字符串）时降级"""
        raw = '```json\n["not", "a", "dict"]\n```'
        blueprint = inferrer.parse_structure_blueprint(raw)
        # 非字典应触发降级
        assert isinstance(blueprint, dict)
        assert "composition" in blueprint
        assert "layers" in blueprint


# =============================================================================
# 2. _extract_json_block — 三种代码块提取策略
# =============================================================================

class TestExtractJsonBlock:
    """覆盖 vrs_structure_inferrer.py 第 705-736 行"""

    def test_extract_json_codeblock(self, inferrer):
        """优先提取 ```json ... ``` 代码块"""
        text = (
            'before\n'
            '```json\n{"a": 1}\n```\n'
            'after'
        )
        result = inferrer._extract_json_block(text)
        assert result == '{"a": 1}'

    def test_extract_generic_codeblock_with_brace(self, inferrer):
        """通用 ``` ... ``` 代码块（起始为 {）"""
        text = (
            'text\n'
            '```\n{"b": 2}\n```\n'
        )
        result = inferrer._extract_json_block(text)
        assert result == '{"b": 2}'

    def test_extract_generic_codeblock_skip_non_json(self, inferrer):
        """通用代码块起始非 { 或 [ 时跳过"""
        text = '```\nplain text\n```'
        # 退到第三种策略（贪婪 { ... }）
        result = inferrer._extract_json_block(text)
        # 应返回 None（没有 { ... }）
        assert result is None

    def test_extract_bare_braces(self, inferrer):
        """无代码块时，贪婪匹配 { ... }"""
        text = 'prefix {"c": 3} suffix'
        result = inferrer._extract_json_block(text)
        assert result == '{"c": 3}'

    def test_extract_returns_none_for_no_json(self, inferrer):
        """完全无 JSON 痕迹时返回 None"""
        result = inferrer._extract_json_block("no json here at all")
        assert result is None


# =============================================================================
# 3. _build_fallback_blueprint — 降级结构可执行性
# =============================================================================

class TestBuildFallbackBlueprint:
    """覆盖 vrs_structure_inferrer.py 第 1115+ 行"""

    def test_fallback_returns_complete_structure(self, inferrer):
        """降级结构必须包含所有必需字段"""
        blueprint = inferrer._build_fallback_blueprint({})
        for key in ("composition", "layers", "precomps", "cameras", "lights"):
            assert key in blueprint, f"fallback 缺字段: {key}"

    def test_fallback_uses_default_comp_when_empty(self, inferrer):
        """空 analysis 时使用 DEFAULT_COMP"""
        blueprint = inferrer._build_fallback_blueprint({})
        comp = blueprint["composition"]
        assert comp["width"] == DEFAULT_COMP["width"]
        assert comp["height"] == DEFAULT_COMP["height"]
        assert comp["fps"] == DEFAULT_COMP["fps"]
        assert comp["duration"] == DEFAULT_COMP["duration"]

    def test_fallback_inherits_basic_info(self, inferrer):
        """降级结构从 analysis_result.basic_info 继承合成参数"""
        analysis = {
            "basic_info": {
                "width": 1280,
                "height": 720,
                "fps": 24,
                "duration": 15.0,
            }
        }
        blueprint = inferrer._build_fallback_blueprint(analysis)
        assert blueprint["composition"]["width"] == 1280
        assert blueprint["composition"]["height"] == 720
        assert blueprint["composition"]["fps"] == 24
        assert blueprint["composition"]["duration"] == 15.0

    def test_fallback_layers_have_required_fields(self, inferrer):
        """降级结构的每个图层必须含必需字段"""
        blueprint = inferrer._build_fallback_blueprint({})
        for layer in blueprint["layers"]:
            for field in ("index", "name", "type", "blend_mode",
                          "opacity", "effects", "is_3d"):
                assert field in layer, f"layer 缺字段: {field}"

    def test_fallback_first_layer_is_adjustment(self, inferrer):
        """降级结构第一层为调色调整层"""
        blueprint = inferrer._build_fallback_blueprint({})
        first = blueprint["layers"][0]
        assert first["type"] == "adjustment"


# =============================================================================
# 4. _validate_and_complete_blueprint — 字段补全
# =============================================================================

class TestValidateAndCompleteBlueprint:
    """覆盖 vrs_structure_inferrer.py 第 738-787 行"""

    def test_complete_missing_composition(self, inferrer):
        """缺 composition 字段时补全默认值"""
        blueprint = {"layers": []}
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert "composition" in result
        assert result["composition"]["width"] == DEFAULT_COMP["width"]

    def test_complete_missing_layers(self, inferrer):
        """缺 layers 字段时补空列表"""
        blueprint = {"composition": {}}
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert result["layers"] == []

    def test_complete_coerces_non_list_layers(self, inferrer):
        """layers 非 list 时强制转为空列表"""
        blueprint = {"layers": "not a list"}
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert result["layers"] == []

    def test_complete_initializes_precomps_cameras_lights(self, inferrer):
        """precomps/cameras/lights 缺失时初始化为空列表"""
        blueprint = {"composition": {}, "layers": []}
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert result["precomps"] == []
        assert result["cameras"] == []
        assert result["lights"] == []

    def test_complete_normalizes_invalid_layer_type(self, inferrer):
        """非法 layer.type 回退为 footage"""
        blueprint = {
            "layers": [
                {"type": "nonexistent_type", "name": "X"},
            ]
        }
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert result["layers"][0]["type"] == "footage"

    def test_complete_normalizes_invalid_blend_mode(self, inferrer):
        """非法 blend_mode 回退为 NONE"""
        blueprint = {
            "layers": [
                {"type": "footage", "blend_mode": "WTF_MODE"},
            ]
        }
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert result["layers"][0]["blend_mode"] == "NONE"

    def test_complete_adds_default_reasoning(self, inferrer):
        """缺 reasoning 时补默认说明"""
        blueprint = {"composition": {}, "layers": []}
        result = inferrer._validate_and_complete_blueprint(blueprint)
        assert isinstance(result["reasoning"], str)
        assert len(result["reasoning"]) > 0

    def test_complete_skips_non_dict_layer(self, inferrer):
        """layers 中混入非 dict 元素时跳过"""
        blueprint = {
            "layers": [
                {"type": "footage", "name": "valid"},
                "not a dict",
                {"type": "adjustment", "name": "also_valid"},
            ]
        }
        result = inferrer._validate_and_complete_blueprint(blueprint)
        # 仅保留两个 dict 图层
        assert len(result["layers"]) == 2
        assert result["layers"][0]["name"] == "valid"
        assert result["layers"][1]["name"] == "also_valid"


# =============================================================================
# 5. 端到端：infer_structure 在 LLM 不可用时降级
# =============================================================================

class TestInferStructureDegradation:
    """覆盖 infer_structure() 主入口在 LLM 失败/不可用时的降级路径"""

    @pytest.mark.asyncio
    async def test_infer_structure_fallback_when_llm_unavailable(
        self, inferrer, monkeypatch
    ):
        """LLM 网关不可用时，应直接走 fallback 路径并返回可执行结构"""
        # 模拟 _LLM_AVAILABLE = False 的场景：mock chat_with_routing 抛异常
        import vrs.vrs_structure_inferrer as mod

        async def _raise(*args, **kwargs):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr(mod, "_LLM_AVAILABLE", True)
        monkeypatch.setattr(mod, "chat_with_routing", _raise)

        blueprint = await inferrer.infer_structure({"basic_info": {}})

        # 关键断言：即使 LLM 异常，调用方仍能拿到完整蓝图
        assert isinstance(blueprint, dict)
        assert "composition" in blueprint
        assert "layers" in blueprint
        assert "operations" in blueprint  # 由 generate_layer_operations 附加
        assert "metadata" in blueprint
        assert blueprint["metadata"]["inferrer_version"] == "2.0"

    @pytest.mark.asyncio
    async def test_infer_structure_fallback_when_llm_returns_empty(
        self, inferrer, monkeypatch
    ):
        """LLM 返回空内容时降级"""
        import vrs.vrs_structure_inferrer as mod

        async def _empty_response(*args, **kwargs):
            response = MagicMock()
            response.success = True
            response.content = ""
            response.model = "test-model"
            response.tokens_input = 0
            response.tokens_output = 0
            response.latency_ms = 0.0
            return response

        monkeypatch.setattr(mod, "_LLM_AVAILABLE", True)
        monkeypatch.setattr(mod, "chat_with_routing", _empty_response)

        blueprint = await inferrer.infer_structure({"basic_info": {}})

        assert isinstance(blueprint, dict)
        assert "layers" in blueprint
        assert len(blueprint["layers"]) >= 2  # fallback 双层

    @pytest.mark.asyncio
    async def test_infer_structure_with_valid_llm_response(
        self, inferrer, monkeypatch
    ):
        """LLM 返回有效 JSON 时走正常路径"""
        import vrs.vrs_structure_inferrer as mod

        valid_response_json = json.dumps({
            "composition": {"name": "LLM_Comp", "width": 1920, "height": 1080,
                            "fps": 30, "duration": 5.0},
            "layers": [
                {"index": 1, "type": "adjustment", "name": "Color",
                 "blend_mode": "NONE", "opacity": 100,
                 "effects": [{"matchName": "ADBE Lumetri", "params": {}}]},
                {"index": 2, "type": "footage", "name": "Main",
                 "blend_mode": "NONE", "opacity": 100, "effects": []},
            ],
            "precomps": [],
            "cameras": [],
            "lights": [],
            "reasoning": "test",
        })

        async def _valid_response(*args, **kwargs):
            response = MagicMock()
            response.success = True
            response.content = valid_response_json
            response.model = "test-model"
            response.tokens_input = 100
            response.tokens_output = 200
            response.latency_ms = 500.0
            return response

        monkeypatch.setattr(mod, "_LLM_AVAILABLE", True)
        monkeypatch.setattr(mod, "chat_with_routing", _valid_response)

        blueprint = await inferrer.infer_structure({"basic_info": {}})

        assert blueprint["composition"]["name"] == "LLM_Comp"
        assert len(blueprint["layers"]) == 2
        assert blueprint["layers"][0]["name"] == "Color"
        # operations 应被附加
        assert "operations" in blueprint
        assert isinstance(blueprint["operations"], list)
