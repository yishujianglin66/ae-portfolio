"""MattingEngine 单元测试 — 诚实降级 + Action 路由映射校验。

与 SAM2Engine 检测模式保持一致：
1. test_init: 初始化不崩溃（无 onnxruntime 时也不抛异常）
2. test_onnxruntime_missing_degradation: onnxruntime 不可导入时 _matting=False 诚实降级
3. test_human_matting_action_schema: 校验 action → handler 路由映射，无需真实 onnx 模型
"""
from __future__ import annotations

import asyncio
import builtins
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PUPPET_SRC = _PROJECT_ROOT / "puppet-automation" / "src"
if str(_PUPPET_SRC) not in sys.path:
    sys.path.insert(0, str(_PUPPET_SRC))

_real_import = builtins.__import__


def _make_fake_import(block_onnxruntime: bool = True):
    """构造 patch 用的 fake import 函数。"""
    def fake_import(name, *args, **kwargs):
        if block_onnxruntime and (name == "onnxruntime" or name.startswith("onnxruntime.")):
            raise ImportError(f"No module named '{name}' (test patch)")
        return _real_import(name, *args, **kwargs)
    return fake_import


class TestMattingEngineInit(unittest.TestCase):
    """测试 MattingEngine 初始化不崩溃（无依赖/无模型时也正常实例化）。"""

    def test_init_no_crash_without_onnxruntime(self):
        """无 onnxruntime 环境下初始化不应抛异常，只应诚实降级。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            engine = None
            try:
                with patch("builtins.__import__", side_effect=_make_fake_import(True)):
                    engine = MattingEngine(model_dir=model_dir)
            except Exception as e:
                self.fail(f"MattingEngine() raised {type(e).__name__} unexpectedly: {e}")

            self.assertIsNotNone(engine)
            self.assertEqual(engine.name, "matting")
            self.assertTrue(hasattr(engine, "_matting"))
            self.assertTrue(hasattr(engine, "model_dir"))

    def test_init_creates_model_dir(self):
        """初始化时应自动创建 model_dir（若不存在）。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "matting_models"
            self.assertFalse(model_dir.exists())

            engine = MattingEngine(model_dir=model_dir)

            self.assertTrue(model_dir.exists())
            self.assertEqual(engine.model_dir.resolve(), model_dir.resolve())


class TestOnnxruntimeMissingDegradation(unittest.TestCase):
    """测试 onnxruntime 缺失时的诚实降级行为（与 SAM2Engine 的 _sam2 模式一致）。"""

    def test_import_failure_sets__matting_false(self):
        """onnxruntime ImportError 时 _matting 必须为 False，绝不假装可用。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"

            with patch("builtins.__import__", side_effect=_make_fake_import(True)):
                engine = MattingEngine(model_dir=model_dir)

            self.assertIs(engine._matting, False, "_matting 必须为 False（onnxruntime 未安装）")
            self.assertIsNone(engine._onnxruntime)

    def test_env_python_nonexistent_path(self):
        """AEKV_MATTING_PYTHON 指向不存在路径时，available=False（遵循 BaseEngine 约定）。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            nonexistent_py = Path(tmpdir) / "does_not_exist" / "python.exe"

            old_env = os.environ.get("AEKV_MATTING_PYTHON")
            try:
                os.environ["AEKV_MATTING_PYTHON"] = str(nonexistent_py)
                engine = MattingEngine(model_dir=model_dir)
            finally:
                if old_env is not None:
                    os.environ["AEKV_MATTING_PYTHON"] = old_env
                elif "AEKV_MATTING_PYTHON" in os.environ:
                    del os.environ["AEKV_MATTING_PYTHON"]

            self.assertFalse(
                engine.available,
                "AEKV_MATTING_PYTHON 指向不存在路径时 BaseEngine.available 必须为 False",
            )

    def test_missing_runtime_human_matting_returns_not_installed(self):
        """onnxruntime 未安装时调用 human_matting 应返回 error='onnxruntime not installed'。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            img = Path(tmpdir) / "test.png"
            img.write_bytes(b"\x89PNG fake")
            out_dir = Path(tmpdir) / "out"

            with patch("builtins.__import__", side_effect=_make_fake_import(True)):
                engine = MattingEngine(model_dir=model_dir)

            async def run():
                return await engine.human_matting(
                    input_path=str(img),
                    output_dir=str(out_dir),
                )

            result = asyncio.run(run())
            self.assertFalse(result.success)
            self.assertIsNotNone(result.error)
            self.assertIn("onnxruntime not installed", result.error)
            self.assertEqual(result.error_code, "MATTING_NOT_AVAILABLE")
            self.assertFalse(result.available)


class TestHumanMattingActionSchema(unittest.TestCase):
    """校验 action 路由映射（handlers dict 注册 + _execute_impl 分发正确）。"""

    def test_handlers_dict_has_expected_actions(self):
        """_handlers dict 必须包含 human_matting 和 batch_frames 两个 action。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            engine = MattingEngine(model_dir=Path(tmpdir) / "models")

            self.assertIn("human_matting", engine._handlers)
            self.assertIn("batch_frames", engine._handlers)
            self.assertEqual(
                set(engine._handlers.keys()),
                {"human_matting", "batch_frames"},
            )
            self.assertTrue(callable(engine._handlers["human_matting"]))
            self.assertTrue(callable(engine._handlers["batch_frames"]))

    def test_execute_impl_routes_human_matting(self):
        """_execute_impl(action='human_matting') 应路由到 human_matting() 方法。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            engine = MattingEngine(model_dir=model_dir)

            fake_result = MagicMock()
            with patch.object(engine, "human_matting", return_value=fake_result) as mock_hm:
                async def run():
                    return await engine._execute_impl(
                        action="human_matting",
                        input_path="in.png",
                        output_dir="out/",
                        model_name="ppmattingv2.onnx",
                    )

                result = asyncio.run(run())
                self.assertIs(result, fake_result)
                mock_hm.assert_awaited_once_with(
                    input_path="in.png",
                    output_dir="out/",
                    model_name="ppmattingv2.onnx",
                )

    def test_execute_impl_routes_batch_frames(self):
        """_execute_impl(action='batch_frames') 应路由到 batch_frames() 方法。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            engine = MattingEngine(model_dir=model_dir)

            fake_result = MagicMock()
            with patch.object(engine, "batch_frames", return_value=fake_result) as mock_bf:
                async def run():
                    return await engine._execute_impl(
                        action="batch_frames",
                        input_path="frames/",
                        output_dir="masks/",
                    )

                result = asyncio.run(run())
                self.assertIs(result, fake_result)
                mock_bf.assert_awaited_once_with(
                    input_path="frames/",
                    output_dir="masks/",
                )

    def test_execute_impl_unknown_action_returns_error(self):
        """未知 action 应返回 success=False 并列出可用 actions。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            engine = MattingEngine(model_dir=model_dir)

            async def run():
                return await engine._execute_impl(action="nonexistent_action")

            result = asyncio.run(run())
            self.assertFalse(result.success)
            self.assertIn("nonexistent_action", result.error)
            self.assertIn("human_matting", result.error)
            self.assertIn("batch_frames", result.error)
            self.assertEqual(result.error_code, "MATTING_UNKNOWN_ACTION")

    def test_scan_model_dir_report(self):
        """_scan_model_dir 应返回正确的路径检测报告结构。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            model_dir.mkdir(parents=True, exist_ok=True)
            engine = MattingEngine(model_dir=model_dir)

            report = engine._scan_model_dir()
            self.assertIn("model_dir", report)
            self.assertIn("model_dir_exists", report)
            self.assertIn("onnx_files", report)
            self.assertIn("has_any_model", report)
            self.assertIn("pp_mattingv2_found", report)
            self.assertTrue(report["model_dir_exists"])
            self.assertFalse(report["has_any_model"])
            self.assertIsInstance(report["onnx_files"], list)

            fake_model = model_dir / "ppmattingv2_human_512x512.onnx"
            fake_model.write_bytes(b"fake onnx")
            report2 = engine._scan_model_dir()
            self.assertTrue(report2["has_any_model"])
            self.assertTrue(report2["pp_mattingv2_found"])
            self.assertEqual(len(report2["onnx_files"]), 1)

    def test_get_info_schema(self):
        """get_info() 应返回标准引擎信息结构（供 /status 端点使用）。"""
        from engines.matting.engine import MattingEngine

        with tempfile.TemporaryDirectory() as tmpdir:
            model_dir = Path(tmpdir) / "models"
            engine = MattingEngine(model_dir=model_dir)

            info = engine.get_info()
            self.assertEqual(info["name"], "matting")
            self.assertIn("available", info)
            self.assertIn("onnxruntime_loaded", info)
            self.assertIn("model_dir", info)
            self.assertIn("model_report", info)
            self.assertIn("actions", info)
            self.assertIsInstance(info["actions"], list)
            self.assertIn("human_matting", info["actions"])
            self.assertIn("batch_frames", info["actions"])
            self.assertIn("install_command", info)


if __name__ == "__main__":
    unittest.main()
