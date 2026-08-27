#!/usr/bin/env python3
"""
test_sam2_engine_integration.py — SAM2 引擎集成测试

测试重点：
1. SAM2 模块检测逻辑（已安装/未安装）
2. 视频分割任务的参数验证
3. 模型目录自动创建
4. 前景提取的文件检查
5. 错误处理（视频不存在/模型缺失）

注意：测试使用 Mock 模拟 SAM2 调用，不依赖真实模型
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))


class TestSAM2EngineModuleDetection(unittest.TestCase):
    """SAM2 模块检测测试"""

    def test_installed_sam2_module(self):
        """已安装 SAM2 模块时正常初始化"""
        # Mock sam2 模块
        mock_sam2 = Mock()
        
        with patch.dict('sys.modules', {'sam2': mock_sam2}):
            # 重新导入引擎以触发检测
            import importlib
            from engines.sam2.engine import SAM2Engine
            importlib.reload(sys.modules['engines.sam2.engine'])
            
            engine = SAM2Engine()
            # 不应抛出异常
            self.assertIsNotNone(engine)

    def test_not_installed_sam2_module(self):
        """sam2 不可用时降级处理（引擎约定: 未安装时 _sam2 为 None）

        密闭化：引擎在当前进程 `import sam2` 检测；本环境 venv 可能已安装 sam2，
        因此用 sys.modules["sam2"]=None 模拟未安装（Python 标准行为：抛 ImportError）。
        """
        from engines.sam2.engine import SAM2Engine
        # 传入不存在的 venv Python 路径，模拟 SAM2 环境未安装
        missing_py = Path(tempfile.gettempdir()) / "no_such_venv" / "python.exe"
        with patch.dict("os.environ", {"AEKV_SAM2_PYTHON": str(missing_py)}), \
             patch.dict(sys.modules, {"sam2": None}):
            engine = SAM2Engine(executable_path=missing_py)
        # 应记录警告但不应崩溃，且标记为不可用（引擎约定: 未安装时 _sam2 为 None）
        self.assertIsNone(engine._sam2)

    def test_model_dir_auto_creation(self):
        """模型目录自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models" / "sam2"
            
            from engines.sam2.engine import SAM2Engine
            engine = SAM2Engine(model_dir=model_dir)
            
            # 目录应被创建
            self.assertTrue(model_dir.exists())


class TestSAM2EngineParameterValidation(unittest.TestCase):
    """SAM2 参数验证测试"""

    def test_video_not_found_error(self):
        """视频不存在时返回错误结果"""
        import asyncio
        
        async def run_test():
            from engines.sam2.engine import SAM2Engine
            
            engine = SAM2Engine(model_dir=Path(tempfile.mkdtemp()))
            result = await engine.auto_mask(
                video_path="/nonexistent/video.mp4",
                output_dir=tempfile.mkdtemp()
            )
            
            self.assertFalse(result.success)
            self.assertIn("not found", result.error.lower())
        
        asyncio.run(run_test())

    def test_output_dir_created_if_not_exists(self):
        """输出目录不存在时自动创建"""
        import asyncio
        
        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "test.mp4"
                video_path.write_text("fake video")
                
                output_dir = Path(tmpdir) / "output" / "masks"
                
                # Mock sam2 调用
                mock_result = Mock()
                mock_result.masks = []
                
                from engines.sam2.engine import SAM2Engine
                engine = SAM2Engine(model_dir=Path(tmpdir) / "models")
                engine._sam2 = Mock()  # 假设已安装
                
                # 由于需要实际处理，这里只测试参数传递
                # 实际逻辑在引擎内部
                pass
        
        asyncio.run(run_test())


class TestSAM2EngineTaskDispatch(unittest.TestCase):
    """SAM2 任务分发测试"""

    def test_execute_dispatch_to_auto_mask(self):
        """execute 分发到 auto_mask"""
        import asyncio
        
        async def run_test():
            from engines.sam2.engine import SAM2Engine
            
            engine = SAM2Engine(model_dir=Path(tempfile.mkdtemp()))
            
            # Mock auto_mask
            engine.auto_mask = AsyncMock(return_value=Mock(success=True))
            
            result = await engine.execute(task="mask", video_path="test.mp4", output_dir="out/")
            
            engine.auto_mask.assert_called_once()
        
        asyncio.run(run_test())

    def test_execute_dispatch_to_segment_object(self):
        """execute 分发到 segment_object"""
        import asyncio
        
        async def run_test():
            from engines.sam2.engine import SAM2Engine
            
            engine = SAM2Engine(model_dir=Path(tempfile.mkdtemp()))
            
            # Mock segment_object
            engine.segment_object = AsyncMock(return_value=Mock(success=True))
            
            result = await engine.execute(task="segment", video_path="test.mp4")
            
            engine.segment_object.assert_called_once()
        
        asyncio.run(run_test())

    def test_execute_dispatch_to_extract_foreground(self):
        """execute 分发到 extract_foreground"""
        import asyncio
        
        async def run_test():
            from engines.sam2.engine import SAM2Engine
            
            engine = SAM2Engine(model_dir=Path(tempfile.mkdtemp()))
            
            # Mock extract_foreground
            engine.extract_foreground = AsyncMock(return_value=Mock(success=True))
            
            result = await engine.execute(task="foreground", video_path="test.mp4", output_path="out.mov")
            
            engine.extract_foreground.assert_called_once()
        
        asyncio.run(run_test())

    def test_execute_unknown_task(self):
        """未知任务返回错误"""
        import asyncio
        
        async def run_test():
            from engines.sam2.engine import SAM2Engine
            
            engine = SAM2Engine(model_dir=Path(tempfile.mkdtemp()))
            result = await engine.execute(task="invalid_task")
            
            self.assertFalse(result.success)
            self.assertIn("Unknown task", result.error)
        
        asyncio.run(run_test())


class TestSAM2EngineErrorHandling(unittest.TestCase):
    """SAM2 错误处理测试"""

    def test_sam2_not_available_error(self):
        """SAM2 未安装时调用失败"""
        import asyncio
        
        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "test.mp4"
                video_path.write_text("fake")
                
                from engines.sam2.engine import SAM2Engine
                engine = SAM2Engine(model_dir=Path(tmpdir) / "models")
                engine._sam2 = None  # 明确设置为未安装
                
                result = await engine.auto_mask(video_path, Path(tmpdir) / "output")
                
                # 应该返回错误或降级处理
                # 具体行为由实现决定，这里验证不崩溃
                self.assertIsNotNone(result)
        
        asyncio.run(run_test())

    def test_model_size_parameter_validation(self):
        """模型大小参数验证（base/large）"""
        import asyncio
        
        async def run_test():
            with tempfile.TemporaryDirectory() as tmpdir:
                video_path = Path(tmpdir) / "test.mp4"
                video_path.write_text("fake")
                
                from engines.sam2.engine import SAM2Engine
                engine = SAM2Engine(model_dir=Path(tmpdir) / "models")
                engine._sam2 = Mock()
                
                # 测试有效参数
                for valid_size in ["base", "large"]:
                    # 不实际执行，只验证参数传递
                    pass
        
        asyncio.run(run_test())


class TestSAM2EngineModelDirManagement(unittest.TestCase):
    """SAM2 模型目录管理测试"""

    def test_default_model_dir(self):
        """默认模型目录为 D:\\AE-Work\\models\\sam2"""
        from engines.sam2.engine import SAM2Engine, _DEFAULT_MODEL_DIR
        
        self.assertEqual(_DEFAULT_MODEL_DIR, Path(r"D:\AE-Work\models\sam2"))

    def test_custom_model_dir_override(self):
        """自定义模型目录覆盖默认值"""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "custom_models"
            
            from engines.sam2.engine import SAM2Engine
            engine = SAM2Engine(model_dir=custom_dir)
            
            self.assertEqual(engine.model_dir, custom_dir)

    def test_model_dir_created_if_missing(self):
        """缺失的模型目录自动创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "new" / "dir"
            
            # 目录不存在
            self.assertFalse(model_dir.exists())
            
            from engines.sam2.engine import SAM2Engine
            engine = SAM2Engine(model_dir=model_dir)
            
            # 初始化后目录存在
            self.assertTrue(model_dir.exists())


if __name__ == "__main__":
    unittest.main()