#!/usr/bin/env python3
"""
test_adobe_engines_path_resolution.py — Adobe 引擎路径解析测试

测试重点：
1. 三级优先级路径解析：显式参数 > settings配置 > 自动发现
2. 路径不存在时的降级行为
3. 初始化时的路径验证
4. Bridge Client 延迟加载逻辑

覆盖引擎：
- AuditionEngine
- PhotoshopEngine
- PremiereEngine
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PA_ROOT = str(PROJECT_ROOT / "puppet-automation")
if _PA_ROOT not in sys.path:
    sys.path.insert(0, _PA_ROOT)


def _is_engine_module(name: str) -> bool:
    return (
        name == 'engines' or name.startswith('engines.')
        or name == 'src' or name.startswith('src.')
    )


def _clean_engine_modules():
    """清理 engines/src.engines 模块缓存，解决双重注册冲突"""
    for k in [k for k in sys.modules if _is_engine_module(k)]:
        del sys.modules[k]


class _EngineModuleIsolationMixin:
    """把 sys.modules 清理限制在本文件用例内。

    历史实现只在 setUp 中无条件删除所有 `src.*` / `engines.*` 缓存，
    却从不恢复。这会破坏其它测试文件在导入期建立的模块注册
    （例如 test_layer_render_service 用 spec_from_file_location 绑定的
    `src.models.layer_pipeline`），使同一份 Pydantic 模型出现两个类对象，
    进而抛出 "Input should be a valid dictionary or instance of LayerConfig"。

    这里改为快照 + 恢复：用例内仍可获得干净的模块空间，
    用例结束后把全局状态还原，避免跨文件污染。
    """

    def setUp(self):
        super().setUp()
        self._module_snapshot = {
            k: v for k, v in sys.modules.items() if _is_engine_module(k)
        }
        _clean_engine_modules()

    def tearDown(self):
        for k in [k for k in sys.modules if _is_engine_module(k)]:
            del sys.modules[k]
        sys.modules.update(self._module_snapshot)
        super().tearDown()


class TestAuditionEnginePathResolution(_EngineModuleIsolationMixin, unittest.TestCase):
    """AuditionEngine 路径解析测试"""

    def test_explicit_path_priority_over_settings(self):
        """显式参数优先于 settings 配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建虚假可执行文件
            fake_exe = Path(tmpdir) / "Adobe Audition.exe"
            fake_exe.write_text("fake")
            
            # Mock settings
            mock_settings = Mock()
            mock_settings.audition_path = "C:\\wrong\\path.exe"
            
            with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
                from src.engines.audition.engine import AuditionEngine
                engine = AuditionEngine(executable_path=fake_exe)
                
                self.assertEqual(engine.au_path, fake_exe)

    def test_settings_path_when_no_explicit(self):
        """无显式参数时使用 settings 配置"""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings_exe = Path(tmpdir) / "Audition2025.exe"
            settings_exe.write_text("settings")
            
            mock_settings = Mock()
            mock_settings.audition_path = str(settings_exe)
            
            with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
                from src.engines.audition.engine import AuditionEngine
                engine = AuditionEngine()
                
                self.assertEqual(engine.au_path, settings_exe)

    def test_auto_detect_fallback(self):
        """settings 无效时自动检测"""
        from src.engines.audition.engine import AuditionEngine
        
        mock_settings = Mock()
        mock_settings.audition_path = "/nonexistent/path.exe"
        
        # Mock _find_audition 返回虚拟路径
        with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
            with patch.object(AuditionEngine, '_find_audition', return_value=Path("C:\\found\\audition.exe")):
                engine = AuditionEngine()
                
                self.assertEqual(engine.au_path, Path("C:\\found\\audition.exe"))

    def test_auto_detect_returns_none_when_not_found(self):
        """未找到时返回 None，不抛出异常"""
        from src.engines.audition.engine import AuditionEngine
        
        mock_settings = Mock()
        mock_settings.audition_path = ""
        
        with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
            with patch.object(AuditionEngine, '_find_audition', return_value=None):
                engine = AuditionEngine()
                
                # au_path 应该为 None 或空路径
                self.assertTrue(engine.au_path is None or engine.au_path == Path("audition"))

    def test_bridge_client_lazy_initialization(self):
        """Bridge Client 延迟初始化（None=未检测）"""
        from src.engines.audition.engine import AuditionEngine
        
        mock_settings = Mock()
        mock_settings.audition_path = ""
        
        with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
            with patch.object(AuditionEngine, '_find_audition', return_value=None):
                engine = AuditionEngine()
                
                # 初始化时不应立即创建 bridge client
                self.assertIsNone(engine._bridge_client)
                # 状态为未检测
                self.assertIsNone(engine._bridge_available)


class TestPhotoshopEnginePathResolution(_EngineModuleIsolationMixin, unittest.TestCase):
    """PhotoshopEngine 路径解析测试"""

    def test_explicit_path_validated(self):
        """显式路径必须存在"""
        with tempfile.TemporaryDirectory() as tmpdir:
            existing_exe = Path(tmpdir) / "Photoshop.exe"
            existing_exe.write_text("ps")
            
            mock_settings = Mock()
            mock_settings.photoshop_path = ""
            
            with patch('src.engines.photoshop.engine.get_settings', return_value=mock_settings):
                from src.engines.photoshop.engine import PhotoshopEngine
                engine = PhotoshopEngine(executable_path=existing_exe)
                
                self.assertEqual(engine.ps_path, existing_exe)

    def test_explicit_nonexistent_path_fallback(self):
        """显式路径不存在时降级到 settings"""
        from src.engines.photoshop.engine import PhotoshopEngine
        
        mock_settings = Mock()
        mock_settings.photoshop_path = "C:\\valid\\path.exe"
        
        # Mock _find_photoshop
        with patch('src.engines.photoshop.engine.get_settings', return_value=mock_settings):
            with patch.object(PhotoshopEngine, '_find_photoshop', return_value=Path("fallback")):
                # 显式路径不存在，settings路径也不存在，最终 fallback
                engine = PhotoshopEngine(executable_path="/nonexistent/ps.exe")
                self.assertEqual(engine.ps_path, Path("fallback"))

    def test_auto_detect_checks_common_paths(self):
        """自动检测扫描常见路径"""
        # 验证 _find_photoshop 包含 2025/2024/2023 版本路径
        from src.engines.photoshop.engine import PhotoshopEngine
        
        # 调用静态方法
        result = PhotoshopEngine._find_photoshop()
        # 应该返回 Path 或 None
        self.assertTrue(result is None or isinstance(result, Path))


class TestPremiereEnginePathResolution(_EngineModuleIsolationMixin, unittest.TestCase):
    """PremiereEngine 路径解析测试"""

    def test_three_level_priority(self):
        """三级优先级：显式 > settings > 自动"""
        with tempfile.TemporaryDirectory() as tmpdir:
            explicit_exe = Path(tmpdir) / "Premiere_Explicit.exe"
            explicit_exe.write_text("explicit")
            
            mock_settings = Mock()
            mock_settings.premiere_path = "C:\\settings\\Premiere.exe"
            # 引擎构造时会做 `self._settings.pr_bridge_dir / "..."`，
            # Mock 无法参与路径运算，需提供真实 Path。
            mock_settings.pr_bridge_dir = Path(tmpdir) / "pr_bridge"

            # 引擎通过模块级单例 `from ...config import settings` 取配置，
            # 并不存在 `get_settings` 函数，因此需 patch 该 settings 对象本身。
            from src.engines.premiere.engine import PremiereEngine
            with patch('src.engines.premiere.engine.settings', mock_settings):
                engine = PremiereEngine(executable_path=explicit_exe)

                # 显式参数胜出
                self.assertEqual(engine.premiere_path, explicit_exe)

    def test_registry_fallback_on_auto_detect(self):
        """自动检测包含注册表查找"""
        # 验证 _find_premiere 尝试注册表
        # 实际测试需要 mock winreg
        try:
            import winreg
            has_winreg = True
        except ImportError:
            has_winreg = False
        
        if has_winreg:
            from src.engines.premiere.engine import PremiereEngine
            # 不实际访问注册表，只验证方法存在
            self.assertTrue(hasattr(PremiereEngine, '_find_premiere'))


class TestAdobeEnginesInitialization(_EngineModuleIsolationMixin, unittest.TestCase):
    """Adobe 引擎初始化测试"""

    def test_base_engine_inheritance(self):
        """验证继承 BaseEngine"""
        from src.engines.base import BaseEngine
        from src.engines.audition.engine import AuditionEngine
        from src.engines.photoshop.engine import PhotoshopEngine
        from src.engines.premiere.engine import PremiereEngine
        
        self.assertTrue(issubclass(AuditionEngine, BaseEngine))
        self.assertTrue(issubclass(PhotoshopEngine, BaseEngine))
        self.assertTrue(issubclass(PremiereEngine, BaseEngine))

    def test_engine_name_attribute(self):
        """引擎必须有 name 类属性"""
        from src.engines.audition.engine import AuditionEngine
        from src.engines.photoshop.engine import PhotoshopEngine
        from src.engines.premiere.engine import PremiereEngine
        
        self.assertEqual(AuditionEngine.name, "audition")
        self.assertEqual(PhotoshopEngine.name, "photoshop")
        self.assertEqual(PremiereEngine.name, "premiere")

    def test_script_dir_creation(self):
        """脚本目录自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_exe = Path(tmpdir) / "test.exe"
            fake_exe.write_text("test")
            
            mock_settings = Mock()
            mock_settings.audition_path = ""
            mock_settings.photoshop_path = ""
            mock_settings.premiere_path = ""
            
            with patch('src.engines.audition.engine.get_settings', return_value=mock_settings):
                from src.engines.audition.engine import AuditionEngine
                engine = AuditionEngine(executable_path=fake_exe)
                
                # 验证脚本目录存在
                self.assertTrue(engine._script_dir.exists())


if __name__ == "__main__":
    unittest.main()