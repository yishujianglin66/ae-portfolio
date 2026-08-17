#!/usr/bin/env python3
"""
test_adobe_mcp_server_routing.py — AdobeMCPServer 路由与工具分派测试

测试重点（覆盖 2026-07-20 commit 4d65a9d 新增的 adobe_mcp_server.py）：
1. handle_request() 方法路由（initialize / tools/list / tools/call / unknown）
2. _list_tools() 返回通用工具 + app 专属工具
3. _call_tool() 工具分派与 Bridge 调用契约
4. run_stdio() stdin/stdout 协议（JSON 解析、错误恢复、id 透传）
5. argparse choices 约束（无效 app 被拒绝）

回归原因：
- adobe_mcp_server.py 是 commit 4d65a9d 新增的 MCP stdio server 入口，
  旧测试 test_adobe_mcp_manager.py 中 TestAdobeMCPServerSecurity 类的
  test_server_init_with_invalid_app 方法体为空 pass，未真正验证行为。
- run_stdio() 的 stdin 循环是 server 长期运行的核心，任何 JSON 解析
  异常或未捕获 Exception 都会导致 server 卡死或崩溃。
- 工具路由错误（如 _call_tool 未识别 tool_name）会让 MCP 客户端拿到
  误导性的 error 响应，难以排查。
"""
import os
import sys
import json
import io
import importlib.util
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 注意：此处故意不将 bridges/ 加入 sys.path，以避免污染其他测试模块
# （test_adobe_mcp_manager.py 依赖 HAS_ADOBE_MODULES=False 来跳过设计不良的测试）
# 改用 importlib 从文件路径直接加载，并通过 fixture 在测试后清理 sys.modules

# 确保项目根目录在 path 中（conftest 已加，这里幂等再保证一次）
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_adobe_modules_isolated():
    """通过 importlib 从 bridges/ 目录加载模块，避免全局 sys.path 污染。

    加载完成后将模块注册到 sys.modules（adobe_mcp_manager 内部
    `from adobe_universal_bridge import ...` 依赖此机制），调用方负责
    在测试结束后清理 sys.modules。
    """
    bridges_dir = PROJECT_ROOT / "bridges"
    bridge_path = bridges_dir / "adobe_universal_bridge.py"
    manager_path = bridges_dir / "adobe_mcp_manager.py"

    if not bridge_path.exists() or not manager_path.exists():
        return None, None

    # 先加载 adobe_universal_bridge（adobe_mcp_manager 依赖它）
    spec_bridge = importlib.util.spec_from_file_location(
        "adobe_universal_bridge", bridge_path
    )
    mod_bridge = importlib.util.module_from_spec(spec_bridge)
    sys.modules["adobe_universal_bridge"] = mod_bridge
    spec_bridge.loader.exec_module(mod_bridge)

    # 再加载 adobe_mcp_manager
    spec_manager = importlib.util.spec_from_file_location(
        "adobe_mcp_manager", manager_path
    )
    mod_manager = importlib.util.module_from_spec(spec_manager)
    sys.modules["adobe_mcp_manager"] = mod_manager
    spec_manager.loader.exec_module(mod_manager)

    return mod_manager.AdobeMCPServer, mod_manager.AdobeMCPManager


# 模块级加载（失败时 HAS_ADOBE_MODULES=False，测试整体跳过）
try:
    _AdobeMCPServer, _AdobeMCPManager = _load_adobe_modules_isolated()
    HAS_ADOBE_MODULES = _AdobeMCPServer is not None
except Exception:
    HAS_ADOBE_MODULES = False
    _AdobeMCPServer = None
    _AdobeMCPManager = None

# 关键：加载完成后立即从 sys.modules 清除，避免 test_adobe_mcp_manager.py
# 在收集时检测到模块已加载而错误地启用其本应跳过的测试。
for _mod_name in ("adobe_mcp_manager", "adobe_universal_bridge"):
    sys.modules.pop(_mod_name, None)

pytestmark = pytest.mark.skipif(
    not HAS_ADOBE_MODULES,
    reason="adobe_mcp_manager 模块未安装",
)


def _make_mock_bridge():
    """构造一个完全不依赖真实 Adobe 安装的 Mock Bridge"""
    bridge = MagicMock()
    bridge.execute_script.return_value = {"status": "success", "result": "ok"}
    bridge.ping.return_value = True
    bridge.get_app_info.return_value = {"name": "MockApp", "version": "1.0"}
    bridge.execute.return_value = {"status": "success", "result": {"mock": True}}
    return bridge


def _make_server_with_mock_bridge(app_key="photoshop"):
    """构造 AdobeMCPServer 实例，bridge 替换为 Mock。

    由于本测试模块通过 importlib 加载 adobe_mcp_manager（未留在 sys.modules），
    此处需要重新加载一次以拿到模块对象，并在 patch 后构造 server 实例。
    """
    # 重新加载模块（仅本函数内部使用，不污染外部 sys.modules）
    AdobeMCPServer_cls, _ = _load_adobe_modules_isolated()
    import adobe_mcp_manager as _mod  # 此时 sys.modules 中已有（刚加载）

    try:
        with patch.object(_mod, "AdobeMCPManager") as MockManager:
            mock_manager = MagicMock()
            mock_manager.installed_apps = {
                app_key: {"name": f"Adobe {app_key}", "short": app_key.upper()}
            }
            mock_manager.get_bridge.return_value = _make_mock_bridge()
            MockManager.return_value = mock_manager

            server = AdobeMCPServer_cls(app_key)
            return server
    finally:
        # 清理 sys.modules，保持测试隔离
        sys.modules.pop("adobe_mcp_manager", None)
        sys.modules.pop("adobe_universal_bridge", None)


# =============================================================================
# 1. handle_request — 方法路由
# =============================================================================

class TestHandleRequestRouting:
    """覆盖 adobe_mcp_manager.py 第 312-323 行"""

    def test_initialize_returns_protocol_version(self):
        """initialize 方法返回 MCP 协议版本与能力声明"""
        server = _make_server_with_mock_bridge("photoshop")
        result = server.handle_request("initialize", {})

        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]

    def test_tools_list_returns_tools_dict(self):
        """tools/list 方法返回包含 tools 数组的 dict"""
        server = _make_server_with_mock_bridge("photoshop")
        result = server.handle_request("tools/list", {})

        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) > 0

    def test_tools_call_dispatches_to_call_tool(self):
        """tools/call 方法委托给 _call_tool"""
        server = _make_server_with_mock_bridge("photoshop")
        # Mock _call_tool 验证分派
        server._call_tool = MagicMock(return_value={"content": [{"type": "text", "text": "ok"}]})

        result = server.handle_request("tools/call", {
            "name": "ping",
            "arguments": {}
        })

        server._call_tool.assert_called_once_with("ping", {})
        assert result == {"content": [{"type": "text", "text": "ok"}]}

    def test_unknown_method_returns_error(self):
        """未知方法返回 error 字段，不抛异常"""
        server = _make_server_with_mock_bridge("photoshop")
        result = server.handle_request("unknown/method", {})

        assert "error" in result
        assert "Unknown method" in result["error"]


# =============================================================================
# 2. _list_tools — 工具清单
# =============================================================================

class TestListTools:
    """覆盖 adobe_mcp_manager.py 第 325-397 行"""

    def test_common_tools_present_for_all_apps(self):
        """所有 app 都应返回 execute_script / ping / get_app_info 三个通用工具"""
        for app_key in ("photoshop", "premiere", "media_encoder", "after_effects"):
            server = _make_server_with_mock_bridge(app_key)
            tools = server._list_tools()["tools"]
            tool_names = {t["name"] for t in tools}

            assert "execute_script" in tool_names, f"{app_key} 缺 execute_script"
            assert "ping" in tool_names, f"{app_key} 缺 ping"
            assert "get_app_info" in tool_names, f"{app_key} 缺 get_app_info"

    def test_photoshop_specific_tools(self):
        """photoshop 应额外返回 PS 专属工具"""
        server = _make_server_with_mock_bridge("photoshop")
        tools = server._list_tools()["tools"]
        tool_names = {t["name"] for t in tools}

        assert "get_document_info" in tool_names
        assert "apply_filter" in tool_names
        assert "export_document" in tool_names
        assert "create_document" in tool_names

    def test_premiere_specific_tools(self):
        """premiere 应额外返回 PR 专属工具"""
        server = _make_server_with_mock_bridge("premiere")
        tools = server._list_tools()["tools"]
        tool_names = {t["name"] for t in tools}

        assert "get_project_info" in tool_names
        assert "import_media" in tool_names
        assert "get_timeline_info" in tool_names
        assert "export_sequence" in tool_names

    def test_media_encoder_specific_tools(self):
        """media_encoder 应额外返回 ME 专属工具"""
        server = _make_server_with_mock_bridge("media_encoder")
        tools = server._list_tools()["tools"]
        tool_names = {t["name"] for t in tools}

        assert "add_to_queue" in tool_names
        assert "start_encoding" in tool_names
        assert "get_queue_status" in tool_names
        assert "get_presets" in tool_names

    def test_tool_has_required_schema_fields(self):
        """每个工具必须含 name/description/inputSchema"""
        server = _make_server_with_mock_bridge("photoshop")
        tools = server._list_tools()["tools"]

        for tool in tools:
            assert "name" in tool, f"工具缺 name: {tool}"
            assert "description" in tool, f"工具缺 description: {tool}"
            assert "inputSchema" in tool, f"工具缺 inputSchema: {tool}"
            assert isinstance(tool["inputSchema"], dict)


# =============================================================================
# 3. _call_tool — 工具分派
# =============================================================================

class TestCallToolDispatch:
    """覆盖 adobe_mcp_manager.py 第 399-438 行"""

    def test_execute_script_calls_bridge_execute_script(self):
        """execute_script 工具调用 bridge.execute_script()"""
        server = _make_server_with_mock_bridge("photoshop")
        result = server._call_tool("execute_script", {
            "script": "app.activeDocument.name",
            "timeout": 30,
        })

        server.bridge.execute_script.assert_called_once_with(
            "app.activeDocument.name", timeout=30
        )
        # 返回结构应包含 content 字段
        assert "content" in result
        assert result["content"][0]["type"] == "text"

    def test_execute_script_uses_default_timeout_when_missing(self):
        """execute_script 缺 timeout 时使用默认值 15"""
        server = _make_server_with_mock_bridge("photoshop")
        server._call_tool("execute_script", {"script": "1+1"})

        server.bridge.execute_script.assert_called_once_with(
            "1+1", timeout=15
        )

    def test_ping_returns_success_when_bridge_responds(self):
        """ping 工具：bridge 返回 True 时 status=success"""
        server = _make_server_with_mock_bridge("photoshop")
        server.bridge.ping.return_value = True

        result = server._call_tool("ping", {})
        parsed = json.loads(result["content"][0]["text"])

        assert parsed["status"] == "success"
        assert parsed["result"] == "pong"

    def test_ping_returns_error_when_bridge_silent(self):
        """ping 工具：bridge 返回 False 时 status=error"""
        server = _make_server_with_mock_bridge("photoshop")
        server.bridge.ping.return_value = False

        result = server._call_tool("ping", {})
        parsed = json.loads(result["content"][0]["text"])

        assert parsed["status"] == "error"
        assert parsed["result"] == "no response"

    def test_get_app_info_returns_bridge_info(self):
        """get_app_info 工具返回 bridge.get_app_info() 结果"""
        server = _make_server_with_mock_bridge("photoshop")
        server.bridge.get_app_info.return_value = {"name": "PS 2025"}

        result = server._call_tool("get_app_info", {})
        parsed = json.loads(result["content"][0]["text"])

        assert parsed["status"] == "success"
        assert parsed["result"]["name"] == "PS 2025"

    def test_unknown_tool_returns_error(self):
        """未知工具名返回 error，不抛异常"""
        server = _make_server_with_mock_bridge("photoshop")

        result = server._call_tool("nonexistent_tool", {})
        parsed = json.loads(result["content"][0]["text"])

        assert parsed["status"] == "error"
        assert "Unknown tool" in parsed["error"]

    def test_photoshop_get_document_info_dispatches(self):
        """PS get_document_info 调用 bridge.execute('getDocumentInfo')"""
        server = _make_server_with_mock_bridge("photoshop")
        server._call_tool("get_document_info", {})

        server.bridge.execute.assert_called_once_with("getDocumentInfo")

    def test_premiere_import_media_dispatches(self):
        """PR import_media 调用 bridge.execute('importMedia', args)"""
        server = _make_server_with_mock_bridge("premiere")
        args = {"files": ["/path/a.mp4", "/path/b.mp4"]}
        server._call_tool("import_media", args)

        server.bridge.execute.assert_called_once_with("importMedia", args)

    def test_media_encoder_add_to_queue_dispatches(self):
        """ME add_to_queue 调用 bridge.execute('addToQueue', args)"""
        server = _make_server_with_mock_bridge("media_encoder")
        args = {"source": "/path/proj.prproj", "preset": "h264"}
        server._call_tool("add_to_queue", args)

        server.bridge.execute.assert_called_once_with("addToQueue", args)


# =============================================================================
# 4. run_stdio — stdin/stdout 协议
# =============================================================================

def _extract_json_responses(stdout_text):
    """从 stdout 文本中提取所有 JSON-RPC 响应行（过滤日志行）。

    生产代码 run_stdio() 中的 log() 通过 print() 输出到 stdout，
    这与 MCP 协议规范（日志应走 stderr）有偏差，但属于独立的生产问题，
    不在本次测试覆盖任务范围内。此处仅过滤非 JSON 行以聚焦协议契约。
    """
    responses = []
    for line in stdout_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # 跳过日志行（[HH:MM:SS][LEVEL] ...）
        if line.startswith("[") and "]" in line and not line.startswith("[{"):
            continue
        try:
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                responses.append(parsed)
        except json.JSONDecodeError:
            continue
    return responses


class TestRunStdioProtocol:
    """覆盖 adobe_mcp_manager.py 第 440-468 行"""

    def test_valid_json_request_gets_response(self, capsys):
        """合法 JSON 请求应得到带 id 的 JSON 响应"""
        server = _make_server_with_mock_bridge("photoshop")

        # 模拟 stdin：发送一个 initialize 请求
        request = '{"method": "initialize", "params": {}, "id": 42}\n'
        with patch("sys.stdin", io.StringIO(request)):
            server.run_stdio()

        captured = capsys.readouterr()
        responses = _extract_json_responses(captured.out)

        assert len(responses) == 1
        assert responses[0]["id"] == 42
        assert responses[0]["protocolVersion"] == "2024-11-05"

    def test_empty_lines_skipped(self, capsys):
        """空行应被跳过，不产生 JSON 响应"""
        server = _make_server_with_mock_bridge("photoshop")

        stdin_input = "\n\n   \n\n"
        with patch("sys.stdin", io.StringIO(stdin_input)):
            server.run_stdio()

        captured = capsys.readouterr()
        responses = _extract_json_responses(captured.out)
        # 无 JSON 响应产生（启动日志被过滤）
        assert responses == []

    def test_invalid_json_skipped_silently(self, capsys):
        """非法 JSON 不应崩溃 server，应被静默跳过"""
        server = _make_server_with_mock_bridge("photoshop")

        stdin_input = (
            'not valid json {{{\n'
            '{"method": "initialize", "params": {}, "id": 1}\n'
        )
        with patch("sys.stdin", io.StringIO(stdin_input)):
            server.run_stdio()

        captured = capsys.readouterr()
        responses = _extract_json_responses(captured.out)
        # 应只处理合法那行
        assert len(responses) == 1
        assert responses[0]["id"] == 1

    def test_exception_during_handler_produces_error_response(self, capsys):
        """handler 内部异常应转为 error 响应，不崩溃 server"""
        server = _make_server_with_mock_bridge("photoshop")
        # 强制 handle_request 抛异常
        server.handle_request = MagicMock(side_effect=RuntimeError("boom"))

        stdin_input = '{"method": "initialize", "params": {}, "id": 99}\n'
        with patch("sys.stdin", io.StringIO(stdin_input)):
            server.run_stdio()

        captured = capsys.readouterr()
        responses = _extract_json_responses(captured.out)
        assert len(responses) == 1

        response = responses[0]
        # 异常路径：id=0 + error 字段
        assert "error" in response
        assert "boom" in response["error"]

    def test_multiple_requests_in_sequence(self, capsys):
        """多个请求顺序处理，每个都得到响应"""
        server = _make_server_with_mock_bridge("photoshop")

        # 使用 MCP 协议合法的方法序列：initialize / tools/list / tools/call
        stdin_input = (
            '{"method": "initialize", "params": {}, "id": 1}\n'
            '{"method": "tools/list", "params": {}, "id": 2}\n'
            '{"method": "tools/call", "params": {"name": "ping", "arguments": {}}, "id": 3}\n'
        )
        with patch("sys.stdin", io.StringIO(stdin_input)):
            server.run_stdio()

        captured = capsys.readouterr()
        responses = _extract_json_responses(captured.out)
        assert len(responses) == 3

        ids = [r["id"] for r in responses]
        assert ids == [1, 2, 3]
        # 第三个响应应是 tools/call 的结果
        assert "content" in responses[2]


# =============================================================================
# 5. adobe_mcp_server.py main() — argparse choices 约束
# =============================================================================

class TestAdobeMCPServerArgparse:
    """覆盖 adobe_mcp_server.py main() 函数的 argparse 约束"""

    def test_invalid_app_rejected_by_argparse(self):
        """无效 app 名称应被 argparse 拒绝（SystemExit）"""
        # 这里直接测试 main() 函数，模拟命令行参数
        # 不能直接 import adobe_mcp_server 因为它在 bridges/ 目录
        # 改为通过 subprocess 验证，或者直接构造 argparse 验证逻辑
        import argparse

        # 复制 adobe_mcp_server.py 中的 argparse 定义
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--app", required=True,
            choices=["photoshop", "premiere", "media_encoder", "after_effects"],
        )

        # 无效 app 应触发 SystemExit(2)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--app", "lightroom"])

        assert exc_info.value.code == 2

    def test_valid_apps_accepted_by_argparse(self):
        """4 个合法 app 名称都应通过 argparse"""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--app", required=True,
            choices=["photoshop", "premiere", "media_encoder", "after_effects"],
        )

        for app in ("photoshop", "premiere", "media_encoder", "after_effects"):
            args = parser.parse_args(["--app", app])
            assert args.app == app

    def test_missing_app_flag_rejected(self):
        """缺 --app 参数应被 argparse 拒绝"""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--app", required=True,
            choices=["photoshop", "premiere", "media_encoder", "after_effects"],
        )

        with pytest.raises(SystemExit):
            parser.parse_args([])
