"""
test_ps_bridge_migration.py - PSBridgeClient 迁移到 UnifiedBridgeBase 的验证测试

验证 D-04/D-15（PSBridgeClient 架构债修复）和 D-18（PS 自动启动）：
1. PSBridgeClient 继承自 UnifiedBridgeBase（而非已弃用的 AEBridgeClient）
2. 类属性 APP_PREFIX/APP_NAME/COMMAND_FILE_NAME 等正确设置
3. 公开 API 方法可用（send_command / ping / is_online / get_document_info / list_layers / execute_script）
4. PSBridgeClient 可以无错误实例化（不启动 PS）
5. ps_bridge_core.jsx 已部署到 Photoshop Scripts 目录
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# 确保项目根与 bridges/ 在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
_BRIDGES_DIR = os.path.join(PROJECT_ROOT, "bridges")
if _BRIDGES_DIR not in sys.path:
    sys.path.insert(0, _BRIDGES_DIR)

from unified_bridge_base import UnifiedBridgeBase  # noqa: E402
from ps_bridge_client import PSBridgeClient  # noqa: E402

# 部署目标路径
PS_SCRIPTS_DIR = Path(r"D:\ps\Adobe Photoshop 2025\Presets\Scripts")
DEPLOYED_JSX = PS_SCRIPTS_DIR / "ps_bridge_core.jsx"


class TestPSBridgeMigration:
    """PSBridgeClient 迁移正确性验证。"""

    def test_ps_bridge_client_inherits_live_base(self):
        """D-15 (2026-08-14): PSBridgeClient 继承活跃基类 ae.ae_bridge_base.

        不再依赖 DEPRECATED 的 unified_bridge_base → bridges/ae_bridge_base
        转发链 (原断言已随修复更新)。
        """
        from ae.ae_bridge_base import AEBridgeClient
        assert issubclass(PSBridgeClient, AEBridgeClient), (
            "PSBridgeClient 必须继承活跃基类 ae.ae_bridge_base.AEBridgeClient"
        )

    def test_ps_bridge_client_class_attributes(self):
        """验证 APP_PREFIX/APP_NAME/COMMAND_FILE_NAME 等类属性正确。"""
        assert PSBridgeClient.APP_PREFIX == "ps"
        assert PSBridgeClient.APP_NAME == "Photoshop"
        assert PSBridgeClient.COMMAND_FILE_NAME == "ps_command.json"
        assert PSBridgeClient.RESULT_FILE_NAME == "ps_result.json"
        assert PSBridgeClient.SECRET_FILE_NAME == ".ps_mcp_secret"

    def test_ps_bridge_client_methods_available(self):
        """验证核心公开方法都存在（含继承自 UnifiedBridgeBase 的方法）。"""
        # 来自 UnifiedBridgeBase 的统一 API
        assert hasattr(PSBridgeClient, "send_command")
        assert hasattr(PSBridgeClient, "ping")
        assert hasattr(PSBridgeClient, "is_online")
        # PS 专属 API
        assert hasattr(PSBridgeClient, "get_document_info")
        assert hasattr(PSBridgeClient, "list_layers")
        assert hasattr(PSBridgeClient, "execute_script")

        # 验证都是可调用的
        for name in (
            "send_command",
            "ping",
            "is_online",
            "get_document_info",
            "list_layers",
            "execute_script",
        ):
            assert callable(getattr(PSBridgeClient, name)), f"{name} 必须可调用"

    def test_ps_bridge_client_instantiation(self):
        """验证 PSBridgeClient() 能实例化（不实际启动 PS）。

        使用临时 bridge_dir 避免污染默认目录。
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            client = PSBridgeClient(bridge_dir=tmp, signature_enabled=False)
            # 验证实例属性
            assert client.APP_PREFIX == "ps"
            assert client.APP_NAME == "Photoshop"
            # bridge_dir 应指向临时目录
            assert Path(client.bridge_dir) == Path(tmp)
            # 命令/结果文件路径应符合 PS 命名约定
            assert client.command_file.endswith("ps_command.json")
            assert client.result_file.endswith("ps_result.json")

    def test_ps_bridge_core_jsx_deployed(self):
        """验证 ps_bridge_core.jsx 已部署到 Photoshop Scripts 目录。"""
        assert PS_SCRIPTS_DIR.exists(), (
            f"Photoshop Scripts 目录不存在: {PS_SCRIPTS_DIR}"
        )
        assert DEPLOYED_JSX.exists(), (
            f"ps_bridge_core.jsx 未部署到: {DEPLOYED_JSX}"
        )
        # 部署文件不应为空
        assert DEPLOYED_JSX.stat().st_size > 0, "部署的 JSX 文件为空"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
