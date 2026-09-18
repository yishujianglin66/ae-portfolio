"""Tests for MCP Gateway."""
from __future__ import annotations

from pathlib import Path

import pytest
from src.engines.base import BaseEngine, EngineResult
from src.mcp_gateway import MCPRegistry, MCPTool, initialize_gateway


class MockEngine(BaseEngine):
    """Mock engine for testing."""
    name = "mock"

    def __init__(self, name: str = "mock", tmp_path=None):
        self._name = name
        if tmp_path:
            path = Path(tmp_path) / f"{name}.exe"
            path.touch()
        else:
            path = Path(f"/tmp/mock_{name}.exe")
        super().__init__(path)

    async def execute(self, action: str, **kwargs) -> EngineResult:
        return EngineResult(
            success=True,
            output_path=None,
            metadata={"action": action, "kwargs": kwargs},
        )


class TestMCPTool:
    """Test MCPTool dataclass."""

    def test_create_tool(self):
        async def dummy_handler(**kwargs):
            from src.engines.base import EngineResult
            return EngineResult(success=True)

        tool = MCPTool(
            name="test_do_something",
            description="Test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=dummy_handler,
            engine="test",
            action="do_something",
        )
        assert tool.name == "test_do_something"
        assert tool.engine == "test"
        assert tool.action == "do_something"


class TestMCPRegistry:
    """Test MCPRegistry."""

    def test_empty_registry(self):
        reg = MCPRegistry()
        assert len(reg.tools) == 0
        assert len(reg.engines) == 0
        assert reg.list_tools() == []

    def test_register_engine(self):
        reg = MCPRegistry()
        engine = MockEngine("test_engine")
        reg.register_engine("test", engine)
        assert "test" in reg.engines
        assert reg.engines["test"] == engine

    def test_register_and_get_tool(self):
        reg = MCPRegistry()

        async def handler(x: int):
            from src.engines.base import EngineResult
            return EngineResult(success=True, metadata={"x": x})

        tool = MCPTool(
            name="test_add",
            description="Add numbers",
            input_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
            handler=handler,
            engine="test",
            action="add",
        )
        reg.register_tool(tool)

        assert reg.get_tool("test_add") == tool
        assert len(reg.list_tools()) == 1

    def test_list_tools_format(self):
        reg = MCPRegistry()

        async def handler():
            from src.engines.base import EngineResult
            return EngineResult(success=True)

        reg.register_tool(MCPTool(
            name="demo_action",
            description="Demo tool",
            input_schema={"type": "object"},
            handler=handler,
            engine="demo",
            action="action",
        ))

        tools = reg.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "demo_action"
        assert tools[0]["description"] == "Demo tool"
        assert "inputSchema" in tools[0]

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        reg = MCPRegistry()

        async def handler(value: str):
            from src.engines.base import EngineResult
            return EngineResult(success=True, metadata={"received": value})

        reg.register_tool(MCPTool(
            name="echo",
            description="Echo tool",
            input_schema={"type": "object"},
            handler=handler,
            engine="test",
            action="echo",
        ))

        result = await reg.call_tool("echo", {"value": "hello"})
        assert result["isError"] is False
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        reg = MCPRegistry()
        with pytest.raises(KeyError):
            await reg.call_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_call_tool_error(self):
        reg = MCPRegistry()

        async def failing_handler():
            raise RuntimeError("boom")

        reg.register_tool(MCPTool(
            name="failing",
            description="Fails always",
            input_schema={"type": "object"},
            handler=failing_handler,
            engine="test",
            action="fail",
        ))

        result = await reg.call_tool("failing", {})
        assert result["isError"] is True


class TestInitializeGateway:
    """Test initialize_gateway function."""

    def test_initialize_with_mock_engines(self):
        engines = {
            "ffmpeg": MockEngine("ffmpeg"),
            "ae": MockEngine("ae"),
        }
        registry = initialize_gateway(engines)

        assert len(registry.engines) == 2
        assert "ffmpeg" in registry.engines
        assert "ae" in registry.engines

        # Should have FFmpeg and AE tools
        tool_names = [t.name for t in registry.tools.values()]
        # Check at least some ffmpeg tools exist
        ffmpeg_tools = [n for n in tool_names if n.startswith("ffmpeg_")]
        assert len(ffmpeg_tools) >= 3

        # Check some AE tools exist
        ae_tools = [n for n in tool_names if n.startswith("ae_")]
        assert len(ae_tools) >= 2

    def test_initialize_missing_engine_skips_tools(self):
        engines = {
            "ffmpeg": MockEngine("ffmpeg"),
        }
        registry = initialize_gateway(engines)

        tool_names = [t.name for t in registry.tools.values()]
        # No silhouette tools since engine not registered
        sil_tools = [n for n in tool_names if n.startswith("silhouette_")]
        assert len(sil_tools) == 0

    @pytest.mark.asyncio
    async def test_tool_handler_uses_engine_execute(self):
        engines = {
            "ffmpeg": MockEngine("ffmpeg"),
        }
        registry = initialize_gateway(engines)

        # Call a tool that exists
        tool = registry.get_tool("ffmpeg_convert_video")
        assert tool is not None

        result = await registry.call_tool(
            "ffmpeg_convert_video",
            {"input_path": "/tmp/in.mp4", "output_path": "/tmp/out.mp4"},
        )
        assert result["isError"] is False


class TestToolDefinitions:
    """Test that all expected tools are defined."""

    def test_expected_tool_count(self):
        engines = {
            "ffmpeg": MockEngine("ffmpeg"),
            "ae": MockEngine("ae"),
            "topaz": MockEngine("topaz"),
            "silhouette": MockEngine("silhouette"),
            "blender": MockEngine("blender"),
            "davinci": MockEngine("davinci"),
        }
        registry = initialize_gateway(engines)

        tool_names = [t.name for t in registry.tools.values()]

        # FFmpeg: convert, extract_frames, extract_audio, concat = 4
        ffmpeg_tools = [n for n in tool_names if n.startswith("ffmpeg_")]
        assert len(ffmpeg_tools) == 4

        # AE: render_comp, run_script = 2
        ae_tools = [n for n in tool_names if n.startswith("ae_")]
        assert len(ae_tools) == 2

        # Topaz: enhance = 1
        topaz_tools = [n for n in tool_names if n.startswith("topaz_")]
        assert len(topaz_tools) == 1

        # Silhouette: roto_video, track_points = 2
        sil_tools = [n for n in tool_names if n.startswith("silhouette_")]
        assert len(sil_tools) == 2

        # Blender: create_stage, run_script, render_animation = 3
        blender_tools = [n for n in tool_names if n.startswith("blender_")]
        assert len(blender_tools) == 3

        # DaVinci: apply_grade, export_lut = 2
        dav_tools = [n for n in tool_names if n.startswith("davinci_")]
        assert len(dav_tools) == 2

        # Total: 4 + 2 + 1 + 2 + 3 + 2 = 14
        assert len(tool_names) == 14
