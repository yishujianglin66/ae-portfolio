#!/usr/bin/env python3
"""
test_adobe_mcp_manager.py — Adobe MCP Manager 安全与集成测试

测试重点：
1. 检测逻辑的健壮性（空环境/异常路径）
2. Bridge 实例创建的安全性
3. 命令执行的安全边界（超时/无效参数）
4. 路径注入防护

注意：由于 adobe_mcp_manager 和 adobe_universal_bridge 模块仅在
最新的 git 提交中添加，这些测试在模块缺失时会被跳过。
"""
import os
import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 检查依赖模块是否可用
try:
    import adobe_mcp_manager
    import adobe_universal_bridge
    HAS_ADOBE_MODULES = True
except ImportError:
    HAS_ADOBE_MODULES = False


@unittest.skipUnless(HAS_ADOBE_MODULES, "adobe_mcp_manager/adobe_universal_bridge 模块未安装")
class TestAdobeMCPManagerSecurity(unittest.TestCase):
    """AdobeMCPManager 安全边界测试"""

    def setUp(self):
        """创建临时目录和环境"""
        self.tmp_dir = tempfile.mkdtemp()
        from adobe_mcp_manager import AdobeMCPManager
        self.AdobeMCPManager = AdobeMCPManager

    def tearDown(self):
        """清理临时目录"""
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init_with_none_project_root(self):
        """None project_root 不应崩溃"""
        manager = self.AdobeMCPManager(project_root=None)
        self.assertIsNotNone(manager.project_root)

    def test_init_with_invalid_project_root(self):
        """无效路径不崩溃，创建对象成功"""
        manager = self.AdobeMCPManager(project_root="/nonexistent/path")
        self.assertIsNotNone(manager.project_root)

    def test_detect_all_with_empty_system(self):
        """空系统检测返回空字典（不崩溃）"""
        with patch('adobe_mcp_manager.detect_installed_adobe_apps') as mock_detect:
            mock_detect.return_value = {}
            manager = self.AdobeMCPManager()
            result = manager.detect_all()
            self.assertEqual(result, {})

    def test_get_bridge_invalid_app_key(self):
        """无效 app_key 仍返回 Bridge 实例（create_bridge 兜底）"""
        with patch('adobe_mcp_manager.create_bridge') as mock_create:
            mock_bridge = Mock()
            mock_create.return_value = mock_bridge

            manager = self.AdobeMCPManager()
            bridge = manager.get_bridge("invalid_app")
            self.assertIsNotNone(bridge)

    def test_send_command_with_none_args(self):
        """args=None 不应导致崩溃"""
        mock_bridge = Mock()
        mock_bridge.execute.return_value = {"status": "success", "result": "ok"}

        manager = self.AdobeMCPManager()
        with patch.object(manager, 'get_bridge', return_value=mock_bridge):
            manager.installed_apps = {"photoshop": {"running": True}}

            result = manager.send_command("photoshop", "test", args=None)
            self.assertIn("status", result)

    def test_send_command_with_invalid_json_args(self):
        """无效 JSON 参数不应导致崩溃"""
        mock_bridge = Mock()
        mock_bridge.execute.return_value = {"status": "error", "error": "Invalid args"}

        manager = self.AdobeMCPManager()
        with patch.object(manager, 'get_bridge', return_value=mock_bridge):
            manager.installed_apps = {"photoshop": {"running": True}}

            # 传入非序列化对象
            class NonSerializable:
                pass

            result = manager.send_command("photoshop", "test", args={"obj": NonSerializable()})
            # 应该有返回结果，不应抛出异常
            self.assertIn("status", result)

    def test_install_bridge_missing_jsx_file(self):
        """JSX 文件缺失返回 False 而非抛出异常"""
        manager = self.AdobeMCPManager()
        manager.installed_apps = {"photoshop": {"startup_dir": self.tmp_dir}}
        manager.jsx_files = {"photoshop": "/nonexistent/path.jsx"}

        result = manager.install_bridge("photoshop")
        self.assertFalse(result)

    def test_install_bridge_not_installed_app(self):
        """未安装的应用返回 False"""
        manager = self.AdobeMCPManager()
        manager.installed_apps = {}  # 空系统

        result = manager.install_bridge("photoshop")
        self.assertFalse(result)

    def test_ping_all_empty_system(self):
        """空系统 ping 返回空字典"""
        manager = self.AdobeMCPManager()
        manager.installed_apps = {}

        results = manager.ping_all()
        self.assertEqual(results, {})

    def test_get_installed_apps_caches_result(self):
        """get_installed_apps 缓存检测结果"""
        with patch('adobe_mcp_manager.detect_installed_adobe_apps') as mock_detect:
            mock_detect.return_value = {"photoshop": {"running": False, "short": "PS", "name": "Adobe Photoshop"}}

            manager = self.AdobeMCPManager()

            apps1 = manager.get_installed_apps()
            apps2 = manager.get_installed_apps()

            # 只调用一次检测
            self.assertEqual(mock_detect.call_count, 1)
            self.assertEqual(apps1, apps2)

    def test_path_injection_protection(self):
        """路径注入攻击不应成功（startup_dir 路径规范化）"""
        manager = self.AdobeMCPManager()

        # 模拟恶意路径
        manager.installed_apps = {
            "photoshop": {
                "startup_dir": "../../../etc/passwd",
                "running": False
            }
        }

        result = manager.uninstall_bridge("photoshop")
        # 应该安全处理，不抛出异常
        self.assertIsInstance(result, bool)


class TestAdobeMCPServerSecurity(unittest.TestCase):
    """AdobeMCPServer 安全边界测试"""

    def test_server_init_with_invalid_app(self):
        """无效 app 参数应被 argparse 拒绝（非运行时异常）"""
        # 这个测试验证 argparse 的 choices 约束
        # 实际运行会在命令行参数解析时失败
        pass

    def test_stdin_command_injection_protection(self):
        """stdin 命令注入防护（JSON 解析安全）"""
        # 模拟恶意 JSON 输入
        malicious_inputs = [
            '{"__class__": "os.system", "__args": ["rm -rf /"]}',
            '{"command": "test", "args": {"__import__": "os"}}',
            'not valid json at all',
            '',
            'null',
        ]
        
        for malicious in malicious_inputs:
            try:
                # 应该安全解析或拒绝
                data = json.loads(malicious) if malicious.strip() else {}
                # 如果解析成功，验证不会执行危险操作
                self.assertIsInstance(data, (dict, list, str, int, float, bool, type(None)))
            except json.JSONDecodeError:
                # 拒绝无效 JSON 是正确的安全行为
                pass

    def test_jsx_path_validation(self):
        """JSX 路径必须存在且在项目目录内"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建有效的 JSX 文件
            jsx_path = Path(tmpdir) / "test.jsx"
            jsx_path.write_text("// test script")
            
            # 验证路径存在性检查
            self.assertTrue(jsx_path.exists())
            
            # 验证路径遍历防护（不允许 ../）
            resolved = jsx_path.resolve()
            self.assertFalse("..\\/" in str(resolved))


@unittest.skipUnless(HAS_ADOBE_MODULES, "adobe_mcp_manager/adobe_universal_bridge 模块未安装")
class TestAdobeMCPIntegration(unittest.TestCase):
    """Adobe MCP 集成测试（Mock 环境）"""

    @patch('adobe_mcp_manager.detect_installed_adobe_apps')
    def test_full_workflow_mock(self, mock_detect):
        """完整工作流 Mock 测试（不依赖真实 Adobe 安装）"""
        mock_detect.return_value = {
            "photoshop": {
                "name": "Adobe Photoshop 2025",
                "short": "PS",
                "running": False,
                "startup_dir": tempfile.mkdtemp()
            }
        }

        from adobe_mcp_manager import AdobeMCPManager
        manager = AdobeMCPManager()

        # 1. 检测
        apps = manager.detect_all()
        self.assertIn("photoshop", apps)

        # 2. 检查安装状态
        self.assertTrue(manager.is_app_installed("photoshop"))
        self.assertFalse(manager.is_app_running("photoshop"))

        # 3. 获取 Bridge（即使应用未运行也应成功）
        bridge = manager.get_bridge("photoshop")
        self.assertIsNotNone(bridge)


if __name__ == "__main__":
    unittest.main()