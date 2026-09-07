"""PR Bridge JSX 协议大修验证测试。

验证 D-11/D-12/D-13/D-14/D-18/D-24 修复：
  - D-11: 单文件协议 (pr_command.json / pr_result.json)
  - D-12: snake_case 命令名 (execute_script)
  - D-13: 全局对象重命名为 PRBridge
  - D-14: handler_pr_business.jsx 单一来源
  - D-18: PRBridgeCEP 扩展已部署
  - D-24: 使用项目目录而非 TEMP 目录

使用 pytest，不依赖 PR 实际运行。
"""
from __future__ import annotations

from pathlib import Path

import pytest

# ============================================================
# 路径常量
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
BRIDGE_DIR = PROJECT_ROOT / ".premiere-mcp-bridge"
PR_BRIDGE_CORE_JSX = SCRIPTS_DIR / "pr_bridge_core.jsx"
HANDLER_PR_BUSINESS_JSX = SCRIPTS_DIR / "handler_pr_business.jsx"

# PRBridgeCEP 扩展以源仓库为权威版本（git 控制，内容断言可回归）。
# 部署副本位于 CEP extensions 目录，由部署脚本同步，测试只检查其存在性。
CEP_EXTENSIONS_DIR = Path(
    r"C:\Users\Administrator\AppData\Roaming\Adobe\CEP\extensions"
)
PRBRIDGE_CEP_DIR = PROJECT_ROOT / "bridges" / "PRBridgeCEP"
PRBRIDGE_CEP_MANIFEST = PRBRIDGE_CEP_DIR / "CSXS" / "manifest.xml"
PRBRIDGE_CEP_DEPLOYED_DIR = CEP_EXTENSIONS_DIR / "PRBridgeCEP"


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture(scope="module")
def pr_bridge_core_content() -> str:
    """读取 pr_bridge_core.jsx 全文。"""
    if not PR_BRIDGE_CORE_JSX.exists():
        pytest.skip(f"pr_bridge_core.jsx not found: {PR_BRIDGE_CORE_JSX}")
    return PR_BRIDGE_CORE_JSX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def pr_bridge_cep_manifest_content() -> str:
    """读取 PRBridgeCEP manifest.xml 全文。"""
    if not PRBRIDGE_CEP_MANIFEST.exists():
        pytest.skip(f"PRBridgeCEP manifest.xml not found: {PRBRIDGE_CEP_MANIFEST}")
    return PRBRIDGE_CEP_MANIFEST.read_text(encoding="utf-8")


# ============================================================
# D-11: 单文件协议
# ============================================================
def test_pr_bridge_core_jsx_uses_single_file_protocol(pr_bridge_core_content: str) -> None:
    """D-11: JSX 必须使用单文件协议 pr_command.json / pr_result.json。"""
    assert "pr_command.json" in pr_bridge_core_content, (
        "pr_bridge_core.jsx 必须引用 pr_command.json（单文件协议）"
    )
    assert "pr_result.json" in pr_bridge_core_content, (
        "pr_bridge_core.jsx 必须引用 pr_result.json（单文件协议）"
    )
    # 不应使用多文件协议 cmd_*.json
    assert "cmd_*.json" not in pr_bridge_core_content, (
        "pr_bridge_core.jsx 不应使用 cmd_*.json 多文件协议"
    )


# ============================================================
# D-24: 使用项目目录 .premiere-mcp-bridge
# ============================================================
def test_pr_bridge_core_jsx_uses_project_dir(pr_bridge_core_content: str) -> None:
    """D-24: JSX 必须使用项目目录 .premiere-mcp-bridge 而非 TEMP。"""
    assert ".premiere-mcp-bridge" in pr_bridge_core_content, (
        "pr_bridge_core.jsx 必须使用 .premiere-mcp-bridge 项目目录"
    )


def test_pr_bridge_core_jsx_no_temp_dir(pr_bridge_core_content: str) -> None:
    """D-24: JSX 不应硬编码 Folder.temp（TEMP 目录）。"""
    assert "Folder.temp" not in pr_bridge_core_content, (
        "pr_bridge_core.jsx 不应硬编码 Folder.temp（TEMP 目录）"
    )


# ============================================================
# D-12: snake_case 命令名
# ============================================================
def test_pr_bridge_core_jsx_uses_snake_case(pr_bridge_core_content: str) -> None:
    """D-12: JSX 必须注册 execute_script（snake_case），而非 executeScript。"""
    # 必须注册 execute_script（snake_case）
    assert 'register("execute_script"' in pr_bridge_core_content, (
        'pr_bridge_core.jsx 必须注册 execute_script（snake_case）'
    )


# ============================================================
# D-13: 全局对象重命名为 PRBridge
# ============================================================
def test_pr_bridge_core_jsx_renamed_prbridge(pr_bridge_core_content: str) -> None:
    """D-13: JSX 全局对象必须为 PRBridge，而非 AEBridge。"""
    assert "PRBridge" in pr_bridge_core_content, (
        "pr_bridge_core.jsx 必须使用 PRBridge 全局对象"
    )
    # 不应使用旧的 AEBridge 命名
    assert "AEBridge" not in pr_bridge_core_content, (
        "pr_bridge_core.jsx 不应使用旧的 AEBridge 命名（避免与 PSBridge 冲突）"
    )


# ============================================================
# D-14: handler_pr_business.jsx 单一来源
# ============================================================
def test_handler_pr_business_single_source() -> None:
    """D-14: handler_pr_business.jsx 只应在 scripts/ 存在，.premiere-mcp-bridge/ 副本应删除。"""
    # scripts/ 下必须存在
    assert HANDLER_PR_BUSINESS_JSX.exists(), (
        f"scripts/handler_pr_business.jsx 必须存在（单一来源）：{HANDLER_PR_BUSINESS_JSX}"
    )
    # .premiere-mcp-bridge/ 下不应存在
    duplicate = BRIDGE_DIR / "handler_pr_business.jsx"
    assert not duplicate.exists(), (
        f".premiere-mcp-bridge/handler_pr_business.jsx 不应存在（应删除以避免重复）：{duplicate}"
    )


def test_handler_pr_business_uses_prbridge() -> None:
    """D-13/D-14: 合并后的 handler_pr_business.jsx 必须使用 PRBridge 而非 AEBridge。"""
    if not HANDLER_PR_BUSINESS_JSX.exists():
        pytest.skip("handler_pr_business.jsx not found")
    content = HANDLER_PR_BUSINESS_JSX.read_text(encoding="utf-8")
    assert "PRBridge" in content, "handler_pr_business.jsx 必须使用 PRBridge"
    assert "AEBridge" not in content, (
        "handler_pr_business.jsx 不应使用旧的 AEBridge 命名"
    )


# ============================================================
# D-18: PRBridgeCEP 扩展已部署
# ============================================================
def test_pr_bridge_cep_extension_exists() -> None:
    """D-18: PRBridgeCEP 扩展的 manifest.xml 必须存在（源仓库权威）。"""
    assert PRBRIDGE_CEP_MANIFEST.exists(), (
        f"PRBridgeCEP manifest.xml 必须存在：{PRBRIDGE_CEP_MANIFEST}"
    )


def test_pr_bridge_cep_deployed_copy_exists() -> None:
    """D-18: PRBridgeCEP 应已部署到 CEP extensions 目录（用户环境诊断）。"""
    if not PRBRIDGE_CEP_DEPLOYED_DIR.exists():
        pytest.skip(
            "PRBridgeCEP 未部署到 CEP extensions（跳过，仅诊断提示）"
        )


def test_pr_bridge_cep_manifest_host_ppro(pr_bridge_cep_manifest_content: str) -> None:
    """D-18: manifest.xml 必须包含 Host Name=\"PPRO\" 以支持 Premiere Pro。"""
    assert 'Host Name="PPRO"' in pr_bridge_cep_manifest_content, (
        'manifest.xml 必须包含 Host Name="PPRO"'
    )


def test_pr_bridge_cep_manifest_csxs_version(pr_bridge_cep_manifest_content: str) -> None:
    """D-18: manifest.xml 应使用 CEP 11 (CSXS 11.0)。"""
    assert "11.0" in pr_bridge_cep_manifest_content, (
        "manifest.xml 应使用 CSXS 11.0"
    )


def test_pr_bridge_cep_host_jsx_loads_core() -> None:
    """D-18: PRBridgeCEP host.jsx 必须加载 pr_bridge_core.jsx。"""
    host_jsx = PRBRIDGE_CEP_DIR / "host.jsx"
    assert host_jsx.exists(), f"PRBridgeCEP host.jsx 必须存在：{host_jsx}"
    content = host_jsx.read_text(encoding="utf-8")
    assert "pr_bridge_core.jsx" in content, (
        "host.jsx 必须加载 pr_bridge_core.jsx"
    )


# ============================================================
# 额外验证：CEP 扩展完整结构
# ============================================================
def test_pr_bridge_cep_structure_complete() -> None:
    """PRBridgeCEP 扩展必须包含所有必要文件。"""
    required_files = [
        PRBRIDGE_CEP_DIR / "CSXS" / "manifest.xml",
        PRBRIDGE_CEP_DIR / "index.html",
        PRBRIDGE_CEP_DIR / "main.js",
        PRBRIDGE_CEP_DIR / "host.jsx",
        PRBRIDGE_CEP_DIR / "CSInterface.js",
    ]
    for f in required_files:
        assert f.exists(), f"PRBridgeCEP 缺少必要文件：{f}"
