"""ae.adapters 单元测试 - 适配器层核心逻辑"""
from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ae.adapters.puppet_adapter import (
    BaseAEAdapter,
    PuppetEngineAdapter,
    json_repr,
    _resolve_output_module,
)
from ae.adapters.mcp_adapter import MCPClientAdapter


# ---------------------------------------------------------------------------
# BaseAEAdapter 测试
# ---------------------------------------------------------------------------


class TestBaseAEAdapter:
    """BaseAEAdapter 基类测试。"""

    def test_name_default(self):
        """name 属性默认为 'base'。"""
        adapter = BaseAEAdapter()
        assert adapter.name == "base"

    def test_supports_gui_default(self):
        """supports_gui 默认为 False。"""
        adapter = BaseAEAdapter()
        assert adapter.supports_gui is False

    def test_requires_gui_default(self):
        """requires_gui 默认为 False。"""
        adapter = BaseAEAdapter()
        assert adapter.requires_gui is False

    def test_is_available_default(self):
        """is_available 默认返回 False。"""
        adapter = BaseAEAdapter()
        assert adapter.is_available() is False

    def test_not_implemented_format(self):
        """_not_implemented 返回格式正确性。"""
        adapter = BaseAEAdapter()
        result = adapter._not_implemented("test_method")
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "test_method" in result["error"]
        assert result["channel"] == "base"

    def test_create_composition_not_implemented(self):
        """create_composition 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.create_composition("Test", 1920, 1080)
        assert result["success"] is False
        assert "create_composition" in result["error"]
        assert result["channel"] == "base"

    def test_list_compositions_not_implemented(self):
        """list_compositions 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.list_compositions()
        assert result["success"] is False
        assert "list_compositions" in result["error"]
        assert result["channel"] == "base"

    def test_create_text_layer_not_implemented(self):
        """create_text_layer 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.create_text_layer("Comp", "Hello")
        assert result["success"] is False
        assert "create_text_layer" in result["error"]
        assert result["channel"] == "base"

    def test_apply_effect_not_implemented(self):
        """apply_effect 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.apply_effect("Comp", 1, "Blur")
        assert result["success"] is False
        assert "apply_effect" in result["error"]
        assert result["channel"] == "base"

    def test_render_not_implemented(self):
        """render 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.render("Comp", "out.mp4")
        assert result["success"] is False
        assert "render" in result["error"]
        assert result["channel"] == "base"

    def test_execute_atom_script_not_implemented(self):
        """execute_atom_script 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.execute_atom_script("alert('hi')")
        assert result["success"] is False
        assert "execute_atom_script" in result["error"]
        assert result["channel"] == "base"

    def test_set_blend_mode_not_implemented(self):
        """set_blend_mode 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.set_blend_mode("Comp", 1, "screen")
        assert result["success"] is False
        assert "set_blend_mode" in result["error"]
        assert result["channel"] == "base"

    def test_set_layer_keyframe_not_implemented(self):
        """set_layer_keyframe 未实现时返回统一格式。"""
        adapter = BaseAEAdapter()
        result = adapter.set_layer_keyframe("Comp", 1, "position", 0, [100, 100])
        assert result["success"] is False
        assert "set_layer_keyframe" in result["error"]
        assert result["channel"] == "base"


# ---------------------------------------------------------------------------
# MCPClientAdapter 测试
# ---------------------------------------------------------------------------


class TestMCPClientAdapter:
    """MCPClientAdapter 测试。"""

    def test_name(self):
        """name 属性为 'mcp'。"""
        adapter = MCPClientAdapter()
        assert adapter.name == "mcp"

    def test_supports_gui(self):
        """supports_gui 为 True。"""
        adapter = MCPClientAdapter()
        assert adapter.supports_gui is True

    def test_requires_gui(self):
        """requires_gui 为 True。"""
        adapter = MCPClientAdapter()
        assert adapter.requires_gui is True

    # -- _wrap 测试 --

    def test_wrap_dict_payload_adds_channel_and_success(self):
        """_wrap：dict payload 标注 channel 和 success。"""
        adapter = MCPClientAdapter()
        payload = {"result": "ok"}
        result = adapter._wrap(payload)
        assert result["result"] == "ok"
        assert result["channel"] == "mcp"
        assert result["success"] is True

    def test_wrap_dict_does_not_override_existing_channel(self):
        """_wrap：不覆盖已有 channel。"""
        adapter = MCPClientAdapter()
        payload = {"channel": "custom", "data": "x"}
        result = adapter._wrap(payload)
        assert result["channel"] == "custom"

    def test_wrap_dict_does_not_override_existing_success(self):
        """_wrap：不覆盖已有 success。"""
        adapter = MCPClientAdapter()
        payload = {"success": False, "error": "failed"}
        result = adapter._wrap(payload)
        assert result["success"] is False

    def test_wrap_non_dict_payload(self):
        """_wrap：非 dict payload 包装为 {success, data, channel}。"""
        adapter = MCPClientAdapter()
        result = adapter._wrap("hello")
        assert result["success"] is True
        assert result["data"] == "hello"
        assert result["channel"] == "mcp"

    def test_wrap_list_payload(self):
        """_wrap：list 被当作非 dict 包装。"""
        adapter = MCPClientAdapter()
        result = adapter._wrap([1, 2, 3])
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]
        assert result["channel"] == "mcp"

    # -- _wrap_list 测试 --

    def test_wrap_list_of_dicts(self):
        """_wrap_list：list of dict 每个都加 channel。"""
        adapter = MCPClientAdapter()
        payload = [{"name": "a"}, {"name": "b"}]
        result = adapter._wrap_list(payload)
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[0]["channel"] == "mcp"
        assert result[1]["name"] == "b"
        assert result[1]["channel"] == "mcp"

    def test_wrap_list_non_list_payload(self):
        """_wrap_list：非 list 包装为单元素列表。"""
        adapter = MCPClientAdapter()
        result = adapter._wrap_list("single")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["data"] == "single"
        assert result[0]["channel"] == "mcp"

    def test_wrap_list_mixed_items(self):
        """_wrap_list：混合 dict 和非 dict 项。"""
        adapter = MCPClientAdapter()
        payload = [{"name": "a"}, "plain"]
        result = adapter._wrap_list(payload)
        assert result[0]["name"] == "a"
        assert result[0]["channel"] == "mcp"
        assert result[1]["data"] == "plain"
        assert result[1]["channel"] == "mcp"

    # -- _ensure_client 测试 --

    def test_ensure_client_with_injected_client(self):
        """_ensure_client：注入 client 时直接返回。"""
        mock_client = MagicMock()
        adapter = MCPClientAdapter(mcp_client=mock_client)
        result = adapter._ensure_client()
        assert result is mock_client

    @patch("ae.adapters.mcp_adapter.AEMCPClient", create=True)
    def test_ensure_client_creates_default(self, mock_client_cls):
        """_ensure_client：未注入时创建默认实例。"""
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        with patch.dict("sys.modules", {"ae.ae_mcp_client": MagicMock(AEMCPClient=mock_client_cls)}):
            adapter = MCPClientAdapter()
            result = adapter._ensure_client()
            assert result is mock_instance
            mock_client_cls.assert_called_once()

    def test_ensure_client_import_failure_raises_runtime_error(self):
        """_ensure_client：导入失败时抛出 RuntimeError。"""
        adapter = MCPClientAdapter()
        with patch.dict("sys.modules", {"ae.ae_mcp_client": None}):
            with pytest.raises(RuntimeError, match="无法导入 AEMCPClient"):
                adapter._ensure_client()

    # -- is_available 测试 --

    def test_is_available_client_alive(self):
        """is_available：client alive 时返回 True。"""
        mock_client = MagicMock()
        mock_client.is_alive.return_value = True
        adapter = MCPClientAdapter(mcp_client=mock_client)
        assert adapter.is_available() is True
        mock_client.is_alive.assert_called_once()

    def test_is_available_client_not_alive(self):
        """is_available：client 不 alive 时返回 False。"""
        mock_client = MagicMock()
        mock_client.is_alive.return_value = False
        adapter = MCPClientAdapter(mcp_client=mock_client)
        assert adapter.is_available() is False

    def test_is_available_client_raises_exception(self):
        """is_available：client 抛异常时返回 False。"""
        mock_client = MagicMock()
        mock_client.is_alive.side_effect = ConnectionError("down")
        adapter = MCPClientAdapter(mcp_client=mock_client)
        assert adapter.is_available() is False

    def test_is_available_import_failure(self):
        """is_available：导入失败时返回 False。"""
        adapter = MCPClientAdapter()
        with patch.dict("sys.modules", {"ae.ae_mcp_client": None}):
            assert adapter.is_available() is False

    # -- create_composition 测试 --

    def test_create_composition_params_passed(self):
        """create_composition：参数正确传递给 client，结果被 _wrap。"""
        mock_client = MagicMock()
        mock_client.create_composition.return_value = {"id": "comp-1"}
        adapter = MCPClientAdapter(mcp_client=mock_client)

        result = adapter.create_composition(
            name="TestComp",
            width=1920,
            height=1080,
            fps=29.97,
            duration=5.0,
            bg_color=[1, 1, 1],
        )

        mock_client.create_composition.assert_called_once_with(
            name="TestComp",
            width=1920,
            height=1080,
            duration=5.0,
            frame_rate=29.97,
            bg_color=[1, 1, 1],
        )
        assert result["id"] == "comp-1"
        assert result["channel"] == "mcp"
        assert result["success"] is True

    # -- list_compositions 测试 --

    def test_list_compositions_field_mapping(self):
        """list_compositions：返回字段名映射转换。"""
        mock_client = MagicMock()

        class MockComp:
            name = "Comp1"
            id = 1
            width = 1920
            height = 1080
            duration = 10.0
            frame_rate = 30.0
            num_layers = 3

        mock_client.list_compositions.return_value = [MockComp()]
        adapter = MCPClientAdapter(mcp_client=mock_client)

        result = adapter.list_compositions()

        assert len(result) == 1
        assert result[0]["name"] == "Comp1"
        assert result[0]["id"] == 1
        assert result[0]["width"] == 1920
        assert result[0]["height"] == 1080
        assert result[0]["duration"] == 10.0
        assert result[0]["frameRate"] == 30.0
        assert result[0]["numLayers"] == 3
        assert result[0]["channel"] == "mcp"

    def test_list_compositions_client_unavailable(self):
        """list_compositions：client 不可用时返回空列表。"""
        adapter = MCPClientAdapter()
        with patch.dict("sys.modules", {"ae.ae_mcp_client": None}):
            result = adapter.list_compositions()
            assert result == []

    # -- execute_atom_script 测试 --

    def test_execute_atom_script_dry_run(self):
        """execute_atom_script：dry_run 模式直接返回。"""
        mock_client = MagicMock()
        adapter = MCPClientAdapter(mcp_client=mock_client)
        script = "alert('hello')"

        result = adapter.execute_atom_script(script, dry_run=True)

        mock_client.execute_atom_script.assert_not_called()
        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["script_length"] == len(script)
        assert result["channel"] == "mcp"

    def test_execute_atom_script_normal(self):
        """execute_atom_script：正常模式调用 client。"""
        mock_client = MagicMock()
        mock_client.execute_atom_script.return_value = {"result": "ok"}
        adapter = MCPClientAdapter(mcp_client=mock_client)
        script = "alert('hi')"

        result = adapter.execute_atom_script(script)

        mock_client.execute_atom_script.assert_called_once_with(script_content=script)
        assert result["result"] == "ok"
        assert result["channel"] == "mcp"

    # -- create_text_layer 抽样测试 --

    def test_create_text_layer_params_passed(self):
        """create_text_layer：参数正确传递。"""
        mock_client = MagicMock()
        mock_client.create_text_layer.return_value = {"layer_index": 1}
        adapter = MCPClientAdapter(mcp_client=mock_client)

        result = adapter.create_text_layer(
            comp_name="Comp",
            text="Hello",
            layer_name="TextLayer",
            font_size=24,
            fill_color=[1, 0, 0],
            position=[100, 200],
        )

        mock_client.create_text_layer.assert_called_once_with(
            comp_name="Comp",
            text="Hello",
            layer_name="TextLayer",
            font_family=None,
            font_size=24,
            fill_color=[1, 0, 0],
            position=[100, 200],
        )
        assert result["layer_index"] == 1
        assert result["channel"] == "mcp"

    # -- apply_effect 抽样测试 --

    def test_apply_effect_params_passed(self):
        """apply_effect：参数正确传递。"""
        mock_client = MagicMock()
        mock_client.apply_effect.return_value = {"effect_index": 1}
        adapter = MCPClientAdapter(mcp_client=mock_client)

        result = adapter.apply_effect(
            comp_name="Comp",
            layer_index=1,
            effect_name="Gaussian Blur",
            settings={"blurriness": 10},
            layer_name="Layer1",
        )

        mock_client.apply_effect.assert_called_once_with(
            comp_name="Comp",
            layer_name="Layer1",
            effect_name="Gaussian Blur",
            settings={"blurriness": 10},
        )
        assert result["effect_index"] == 1
        assert result["channel"] == "mcp"

    # -- render 抽样测试 --

    def test_render_params_passed(self):
        """render：参数正确传递。"""
        mock_client = MagicMock()
        mock_client.render.return_value = {"output": "/tmp/out.mp4"}
        adapter = MCPClientAdapter(mcp_client=mock_client)

        result = adapter.render(
            comp_name="Comp",
            output_path="/tmp/out.mp4",
            format="h264",
        )

        mock_client.render.assert_called_once_with(
            comp_name="Comp",
            output_path="/tmp/out.mp4",
            output_format="h264",
        )
        assert result["output"] == "/tmp/out.mp4"
        assert result["channel"] == "mcp"


# ---------------------------------------------------------------------------
# PuppetEngineAdapter 测试
# ---------------------------------------------------------------------------


class TestPuppetEngineAdapter:
    """PuppetEngineAdapter 测试。"""

    def test_name(self):
        """name 属性为 'puppet'。"""
        adapter = PuppetEngineAdapter()
        assert adapter.name == "puppet"

    def test_supports_gui(self):
        """supports_gui 为 False。"""
        adapter = PuppetEngineAdapter()
        assert adapter.supports_gui is False

    def test_requires_gui(self):
        """requires_gui 为 False。"""
        adapter = PuppetEngineAdapter()
        assert adapter.requires_gui is False

    # -- _to_dict 测试 --

    def test_to_dict_none_returns_error(self):
        """_to_dict：None 返回错误格式。"""
        adapter = PuppetEngineAdapter()
        result = adapter._to_dict(None)
        assert result["success"] is False
        assert result["error"] == "empty result"
        assert result["channel"] == "puppet"

    def test_to_dict_dict_input_adds_channel(self):
        """_to_dict：dict 输入加 channel。"""
        adapter = PuppetEngineAdapter()
        result = adapter._to_dict({"success": True, "data": "x"})
        assert result["success"] is True
        assert result["data"] == "x"
        assert result["channel"] == "puppet"

    def test_to_dict_dict_preserves_existing_channel(self):
        """_to_dict：dict 输入不覆盖已有 channel。"""
        adapter = PuppetEngineAdapter()
        result = adapter._to_dict({"channel": "custom", "ok": True})
        assert result["channel"] == "custom"

    def test_to_dict_engine_result_success(self):
        """_to_dict：EngineResult 对象属性提取（成功）。"""

        class MockEngineResult:
            success = True
            metadata = {"key": "value"}
            output_path = "/tmp/out.aep"
            error = None

        adapter = PuppetEngineAdapter()
        result = adapter._to_dict(MockEngineResult())
        assert result["success"] is True
        assert result["metadata"] == {"key": "value"}
        assert result["output_path"] == "/tmp/out.aep"
        assert result["channel"] == "puppet"
        assert "error" not in result

    def test_to_dict_engine_result_failure(self):
        """_to_dict：EngineResult 对象属性提取（失败）。"""

        class MockEngineResult:
            success = False
            metadata = {}
            output_path = None
            error = "something went wrong"

        adapter = PuppetEngineAdapter()
        result = adapter._to_dict(MockEngineResult())
        assert result["success"] is False
        assert result["error"] == "something went wrong"
        assert result["channel"] == "puppet"

    def test_to_dict_engine_result_no_output_path(self):
        """_to_dict：EngineResult 无 output_path 时不含该字段。"""

        class MockEngineResult:
            success = True
            metadata = {}
            output_path = None
            error = None

        adapter = PuppetEngineAdapter()
        result = adapter._to_dict(MockEngineResult())
        assert "output_path" not in result

    # -- is_available 测试 --

    def test_is_available_with_injected_engine(self):
        """is_available：注入 engine 时返回 True。"""
        mock_engine = MagicMock()
        adapter = PuppetEngineAdapter(engine=mock_engine)
        assert adapter.is_available() is True

    def test_is_available_with_factory(self):
        """is_available：工厂方法已配置时返回 True。"""
        adapter = PuppetEngineAdapter()
        adapter._engine_factory = lambda: MagicMock()
        assert adapter.is_available() is True

    def test_is_available_engine_unavailable(self):
        """is_available：引擎不可用时返回 False。"""
        adapter = PuppetEngineAdapter(ae_exe_path="/nonexistent/path/aerender.exe")
        with patch.object(adapter, "_ensure_engine", side_effect=ImportError("not found")):
            assert adapter.is_available() is False

    # -- create_composition 测试 --

    def test_create_composition_params_passed(self):
        """create_composition：参数正确传递，结果被 _to_dict。"""
        mock_engine = MagicMock()

        class MockResult:
            success = True
            metadata = {"comp_id": "1"}
            output_path = None
            error = None

        async def mock_create_comp(**kwargs):
            return MockResult()

        mock_engine.create_comp = mock_create_comp
        adapter = PuppetEngineAdapter(engine=mock_engine)

        with patch.object(adapter, "_run_async", return_value=MockResult()):
            result = adapter.create_composition(
                name="TestComp",
                width=1920,
                height=1080,
                fps=30.0,
                duration=5.0,
                project_path="/tmp/test.aep",
            )

        assert result["success"] is True
        assert result["metadata"] == {"comp_id": "1"}
        assert result["channel"] == "puppet"

    # -- render 测试 --

    def test_render_requires_project_path(self):
        """render：缺少 project_path 时返回错误。"""
        mock_engine = MagicMock()
        adapter = PuppetEngineAdapter(engine=mock_engine)

        result = adapter.render("Comp", "out.mp4")

        assert result["success"] is False
        assert "project_path" in result["error"]
        assert result["channel"] == "puppet"

    def test_render_with_project_path(self):
        """render：有 project_path 时调用 engine.render_comp。"""
        mock_engine = MagicMock()

        class MockResult:
            success = True
            metadata = {}
            output_path = "out.mp4"
            error = None

        adapter = PuppetEngineAdapter(engine=mock_engine)

        with patch.object(adapter, "_run_async", return_value=MockResult()):
            result = adapter.render(
                comp_name="Comp",
                output_path="out.mp4",
                format="h264",
                project_path="/tmp/test.aep",
            )

        assert result["success"] is True
        assert result["output_path"] == "out.mp4"
        assert result["channel"] == "puppet"

    # -- execute_atom_script 测试 --

    def test_execute_atom_script_dry_run(self):
        """execute_atom_script：dry_run 模式直接返回。"""
        mock_engine = MagicMock()
        adapter = PuppetEngineAdapter(engine=mock_engine)
        script = "alert('hello')"

        result = adapter.execute_atom_script(script, dry_run=True)

        mock_engine.run_script.assert_not_called()
        assert result["success"] is True
        assert result["dry_run"] is True
        assert result["script_length"] == len(script)
        assert result["channel"] == "puppet"

    def test_execute_atom_script_normal(self):
        """execute_atom_script：正常模式调用 engine.run_script。"""
        mock_engine = MagicMock()

        class MockResult:
            success = True
            metadata = {"stdout": "done"}
            output_path = None
            error = None

        adapter = PuppetEngineAdapter(engine=mock_engine)

        with patch.object(adapter, "_run_async", return_value=MockResult()):
            result = adapter.execute_atom_script("alert('hi')", project_path="/tmp/test.aep")

        assert result["success"] is True
        assert result["channel"] == "puppet"

    # -- set_parent_layer 参数格式化测试 --

    def test_set_parent_layer_script_format(self):
        """set_parent_layer：inline script 参数格式化。"""
        import asyncio

        mock_engine = MagicMock()

        class MockResult:
            success = True
            metadata = {}
            output_path = None
            error = None

        adapter = PuppetEngineAdapter(engine=mock_engine)
        captured_script = None

        async def capture_run_script(script, **kwargs):
            nonlocal captured_script
            captured_script = script
            return MockResult()

        mock_engine.run_script = capture_run_script

        def run_async_side_effect(coro):
            return asyncio.run(coro)

        with patch.object(adapter, "_run_async", side_effect=run_async_side_effect):
            adapter.set_parent_layer("MyComp", 2, 1)

        assert captured_script is not None
        assert "MyComp" in captured_script
        assert "2" in captured_script
        assert "1" in captured_script
        assert "parent" in captured_script.lower()

    # -- _run_async 测试 --

    def test_run_async_calls_asyncio_run(self):
        """_run_async：调用 asyncio.run 执行协程。"""
        adapter = PuppetEngineAdapter()

        async def sample_coro():
            return 42

        with patch("asyncio.run", return_value=42) as mock_run:
            result = adapter._run_async(sample_coro())
            assert result == 42
            mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# 工具函数测试
# ---------------------------------------------------------------------------


class TestJsonRepr:
    """json_repr 工具函数测试。"""

    def test_string_serialization(self):
        """字符串序列化。"""
        assert json_repr("hello") == '"hello"'

    def test_string_with_special_chars(self):
        """含特殊字符的字符串序列化。"""
        assert json_repr('he"llo') == '"he\\"llo"'

    def test_number_serialization(self):
        """数字序列化。"""
        assert json_repr(42) == "42"
        assert json_repr(3.14) == "3.14"

    def test_boolean_serialization(self):
        """布尔值序列化。"""
        assert json_repr(True) == "true"
        assert json_repr(False) == "false"

    def test_none_serialization(self):
        """None 序列化。"""
        assert json_repr(None) == "null"

    def test_list_serialization(self):
        """列表序列化。"""
        assert json_repr([1, 2, 3]) == "[1, 2, 3]"

    def test_dict_serialization(self):
        """字典序列化。"""
        result = json_repr({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result


class TestResolveOutputModule:
    """_resolve_output_module 工具函数测试。"""

    def test_h264_mapping(self):
        """h264 → H.264。"""
        assert _resolve_output_module("h264") == "H.264"

    def test_h265_mapping(self):
        """h265 → H.265。"""
        assert _resolve_output_module("h265") == "H.265"

    def test_hevc_mapping(self):
        """hevc → H.265。"""
        assert _resolve_output_module("hevc") == "H.265"

    def test_prores_mapping(self):
        """prores → Apple ProRes 422。"""
        assert _resolve_output_module("prores") == "Apple ProRes 422"

    def test_lossless_mapping(self):
        """lossless → Lossless。"""
        assert _resolve_output_module("lossless") == "Lossless"

    def test_png_mapping(self):
        """png → PNG Sequence。"""
        assert _resolve_output_module("png") == "PNG Sequence"

    def test_unknown_format_passthrough(self):
        """未知格式原样返回。"""
        assert _resolve_output_module("custom_format") == "custom_format"

    def test_case_insensitive(self):
        """大小写不敏感。"""
        assert _resolve_output_module("H264") == "H.264"
        assert _resolve_output_module("H265") == "H.265"
        assert _resolve_output_module("ProRes") == "Apple ProRes 422"
