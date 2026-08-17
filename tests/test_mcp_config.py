"""
.mcp.json 配置完整性测试
========================
端到端验证 `.mcp.json` 中注册的 MCP server 入口文件确实存在、命令可解析，
并捕获「名字碰撞指向第三方包」之类的配置缺陷——例如 AdobeMCP 曾误指向
Python312 site-packages 中的第三方 `adobe_mcp` 包，而非项目内的
`bridges/adobe_mcp_server.py`。

仅做静态 / 文件级检查，不真正启动 server、不依赖真实 AE / PR / Resolve 环境，
因此可在 CI 默认环境稳定通过。

运行:
    uv run --no-project python -m pytest tests/test_mcp_config.py -v

背景：P0-3 端到端验证发现，`.mcp.json` 里 AEToolsMCP 依赖系统 Python312 全局
安装的 fastmcp（未在 pyproject 声明），且 AdobeMCP 的 `python -m adobe_mcp`
命中的是第三方同名包。本测试把这类「配置即代码」的契约固化下来。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MCP_JSON = PROJECT_ROOT / ".mcp.json"

# 这些 server 的入口是外部命令（npx / uvx / streamable_http），
# 不在本仓库内，无法做文件级存在性校验，跳过路径检查。
_EXTERNAL_ONLY = {
    "fetch",
    "bing-cn-mcp-server",
    "qwen-mm-plugins-core",
    "qwen-mm-plugins-video-edit",
    "qwen-mm-plugins-video-memory",
    "ytdlp",
}


@pytest.fixture(scope="module")
def mcp_config():
    assert MCP_JSON.is_file(), f".mcp.json 不存在: {MCP_JSON}"
    return json.loads(MCP_JSON.read_text(encoding="utf-8"))


def _is_source_entry(arg: str) -> bool:
    """判断 MCP args 中的某项是否是需做存在性校验的「源码入口文件」。

    只校验真正的 server 脚本（.py/.js/.ts/.jsx/.mjs）；
    排除 npx 作用域包（@scope/pkg，含 '/' 但非文件）与 filesystem 等的数据根目录。
    """
    if not isinstance(arg, str) or arg.startswith("@"):
        return False
    return arg.lower().endswith((".py", ".js", ".ts", ".jsx", ".mjs"))


def test_mcp_json_valid(mcp_config) -> None:
    assert "mcpServers" in mcp_config
    assert mcp_config["mcpServers"], "mcpServers 为空"


def test_server_entry_files_exist(mcp_config) -> None:
    """每个 server 的本地入口文件（.py/.js 等）必须真实存在。

    能捕获「路径写错 / 文件被移动或删除」这类端到端断链
    （如 external/.../server.py 不存在、ae_tools_mcp_server.py 缺失）。
    """
    missing: list[str] = []
    for name, server in mcp_config["mcpServers"].items():
        if name in _EXTERNAL_ONLY:
            continue
        args = server.get("args", [])
        for arg in args:
            if _is_source_entry(arg):
                p = Path(arg)
                if not p.is_absolute():
                    p = PROJECT_ROOT / p
                if not p.exists():
                    missing.append(f"{name}: {arg}")
    assert not missing, "以下 MCP 入口文件不存在:\n" + "\n".join(missing)


def test_adobemcp_points_to_project_server(mcp_config) -> None:
    """AdobeMCP 必须指向项目内的 bridges/adobe_mcp_server.py，而非第三方同名包。

    历史缺陷：`.mcp.json` 曾写 `python -m adobe_mcp`，命中 Python312 site-packages
    里的第三方同名 PyPI 包，导致 AdobeMCP 实际启动的是错误 server。
    已修正为 `python bridges/adobe_mcp_server.py --app after_effects`。
    """
    srv = mcp_config["mcpServers"]["AdobeMCP"]
    # 不应使用 `python -m adobe_mcp`（第三方名字碰撞）
    assert srv.get("args") != ["-m", "adobe_mcp"]
    # 应指向项目内的 bridges/adobe_mcp_server.py
    assert any(
        "bridges/adobe_mcp_server.py" in str(a) for a in srv.get("args", [])
    )
