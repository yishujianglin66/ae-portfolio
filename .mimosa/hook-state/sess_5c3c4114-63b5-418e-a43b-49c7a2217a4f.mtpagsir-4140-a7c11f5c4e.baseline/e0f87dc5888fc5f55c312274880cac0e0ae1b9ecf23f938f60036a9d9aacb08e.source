#!/usr/bin/env python3
"""
RotoService 单元测试 - SAM2 + Silhouette 联合抠像工作流服务

测试重点：
1. VALID_MODES 常量校验
2. auto_roto 输入验证（无效模式、视频不存在）
3. 三种模式（sam2_only / silhouette_only / hybrid）的 Mock 调度
4. generate_roto_report 成功与失败报告
5. _evaluate_dir_quality 目录不存在 / 空目录
6. _calc_fill_ratio 前景占比评分
7. _calc_iou IoU 计算
8. _calc_edge_sharpness / _calc_connectivity / _calc_noise_level 质量子指标
9. evaluate_quality 单帧质量评估（Mock cv2）
10. _hybrid_roto_pipeline 完整流水线
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import os
import sys
import types
import importlib
import importlib.util

# 添加项目根目录和puppet-automation到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "puppet-automation"))

# Mock 引擎依赖（roto_service 通过 from ..engines 导入）
# 必须在 import roto_service 之前注入 sys.modules

# 注意(2026-08-26): mock 包的 __path__ 不能为空！
# 空 __path__ 会污染全局：后续测试文件（如 test_topaz_engine）导入
# src.engines.* 子模块时，Python 会命中这里缓存的 mock 包，
# 因空路径搜索不到任何子模块而报 ModuleNotFoundError。
# 指向真实目录后既能继续注入 mock 类，又不阻断其它子模块的正常解析。
_PA_SRC_ENGINES_DIR = os.path.join(PROJECT_ROOT, "puppet-automation", "src", "engines")

_mock_engines = types.ModuleType("src.engines")
_mock_engines.__path__ = [_PA_SRC_ENGINES_DIR]
_mock_engines.__package__ = "src.engines"

_mock_engines_base = types.ModuleType("src.engines.base")
_mock_engines_base.__path__ = []
_mock_engines_base.__package__ = "src.engines.base"
_mock_engines_base.BaseEngine = type("BaseEngine", (), {})
_mock_engines_base.EngineResult = type("EngineResult", (), {})

_mock_engines_sam2 = types.ModuleType("src.engines.sam2")
_mock_engines_sam2.__path__ = [os.path.join(_PA_SRC_ENGINES_DIR, "sam2")]
_mock_engines_sam2.__package__ = "src.engines.sam2"

_mock_engines_sam2_engine = types.ModuleType("src.engines.sam2.engine")
_mock_engines_sam2_engine.__package__ = "src.engines.sam2.engine"
_mock_engines_sam2_engine.SAM2Engine = type("SAM2Engine", (), {})

_mock_engines_silhouette = types.ModuleType("src.engines.silhouette")
_mock_engines_silhouette.__path__ = [os.path.join(_PA_SRC_ENGINES_DIR, "silhouette")]
_mock_engines_silhouette.__package__ = "src.engines.silhouette"

_mock_engines_silhouette_engine = types.ModuleType("src.engines.silhouette.engine")
_mock_engines_silhouette_engine.__package__ = "src.engines.silhouette.engine"
_mock_engines_silhouette_engine.SilhouetteEngine = type("SilhouetteEngine", (), {})

_mock_engines.base = _mock_engines_base
_mock_engines.sam2 = _mock_engines_sam2
_mock_engines_sam2.engine = _mock_engines_sam2_engine
_mock_engines_silhouette.engine = _mock_engines_silhouette_engine

# 注意(2026-08-27): 注入必须密闭化！本文件在收集期把空壳 BaseEngine
# （无 __init__）写进 sys.modules["src.engines.base"]，若不恢复，
# 后续 test_topaz_engine 等文件导入真实 src.engines.* 时会命中缓存的
# mock，导致 super().__init__(path) 落到 object.__init__ 报 TypeError。
# 策略：快照 → 注入加载 → 恢复（含父包属性缓存）。
_MOCK_INJECTION_KEYS = [
    "src.engines",
    "src.engines.base",
    "src.engines.sam2",
    "src.engines.sam2.engine",
    "src.engines.silhouette",
    "src.engines.silhouette.engine",
    "src.services",
]
_prior_modules = {k: sys.modules[k] for k in _MOCK_INJECTION_KEYS if k in sys.modules}
_prior_attrs = {}
for _parent, _attr in [("src", "engines"), ("src", "services"),
                       ("src.engines", "base"), ("src.engines", "sam2"),
                       ("src.engines", "silhouette")]:
    _pm = sys.modules.get(_parent)
    if _pm is not None and hasattr(_pm, _attr):
        _prior_attrs[(_parent, _attr)] = getattr(_pm, _attr)

for key, mod in [
    ("src.engines", _mock_engines),
    ("src.engines.base", _mock_engines_base),
    ("src.engines.sam2", _mock_engines_sam2),
    ("src.engines.sam2.engine", _mock_engines_sam2_engine),
    ("src.engines.silhouette", _mock_engines_silhouette),
    ("src.engines.silhouette.engine", _mock_engines_silhouette_engine),
]:
    sys.modules[key] = mod

# Mock src.services.__init__ 以避免触发其他服务的导入
_mock_services_init = types.ModuleType("src.services")
_mock_services_init.__path__ = [os.path.join(PROJECT_ROOT, "puppet-automation", "src", "services")]
_mock_services_init.__package__ = "src.services"
sys.modules["src.services"] = _mock_services_init

# 确保 src 包也注册
if "src" not in sys.modules:
    _mock_src = types.ModuleType("src")
    _mock_src.__path__ = [os.path.join(PROJECT_ROOT, "puppet-automation", "src")]
    _mock_src.__package__ = "src"
    sys.modules["src"] = _mock_src

# 通过 spec 直接加载 roto_service 模块文件
_roto_service_path = os.path.join(
    PROJECT_ROOT, "puppet-automation", "src", "services", "roto_service.py"
)
_spec = importlib.util.spec_from_file_location(
    "src.services.roto_service", _roto_service_path,
    submodule_search_locations=[],
)
_roto_mod = importlib.util.module_from_spec(_spec)
_roto_mod.__package__ = "src.services"
sys.modules["src.services.roto_service"] = _roto_mod
try:
    _spec.loader.exec_module(_roto_mod)
finally:
    # 恢复被注入覆盖的模块注册，避免污染后续测试文件的真实导入；
    # roto_service 内部已绑定的 mock 类引用不受影响。
    for _k in _MOCK_INJECTION_KEYS:
        sys.modules.pop(_k, None)
    sys.modules.update(_prior_modules)
    for (_parent, _attr), _val in _prior_attrs.items():
        _pm = sys.modules.get(_parent)
        if _pm is not None:
            setattr(_pm, _attr, _val)

RotoService = _roto_mod.RotoService


# ---------------------------------------------------------------------------
# 辅助：创建 Mock 引擎
# ---------------------------------------------------------------------------
def _make_mock_sam2() -> MagicMock:
    """创建模拟 SAM2Engine 实例"""
    engine = MagicMock()
    engine.export_mask_sequence = AsyncMock()
    engine.export_silhouette_shape = AsyncMock()
    return engine


def _make_mock_silhouette() -> MagicMock:
    """创建模拟 SilhouetteEngine 实例"""
    engine = MagicMock()
    engine.create_roto_session = AsyncMock()
    engine.refine_mask = AsyncMock()
    engine.render_alpha = AsyncMock()
    return engine


def _make_engine_result(
    success: bool = True,
    output_path: str | None = None,
    error: str | None = None,
    duration_seconds: float = 1.0,
    metadata: dict | None = None,
):
    """创建模拟 EngineResult 对象"""
    r = MagicMock()
    r.success = success
    r.output_path = Path(output_path) if output_path else None
    r.error = error
    r.duration_seconds = duration_seconds
    r.metadata = metadata or {}
    return r


# ===========================================================================
# 测试 VALID_MODES
# ===========================================================================
class TestRotoServiceValidModes(unittest.TestCase):
    """VALID_MODES 常量校验"""

    def test_valid_modes_tuple(self):
        """VALID_MODES 应为包含三种模式的元组"""
        self.assertIsInstance(RotoService.VALID_MODES, tuple)
        self.assertEqual(RotoService.VALID_MODES, ("sam2_only", "silhouette_only", "hybrid"))

    def test_valid_modes_immutable(self):
        """VALID_MODES 应为不可变元组（无法赋值修改）"""
        with self.assertRaises(TypeError):
            RotoService.VALID_MODES[0] = "invalid"


# ===========================================================================
# 测试 auto_roto 输入验证
# ===========================================================================
class TestRotoServiceAutoRotoValidation(unittest.TestCase):
    """auto_roto 输入验证测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_auto_roto_invalid_mode(self):
        """无效模式应返回错误"""
        async def run_test():
            result = await self.service.auto_roto(
                video_path="/fake/video.mp4",
                output_dir=self.temp_dir,
                mode="invalid_mode",
            )
            self.assertFalse(result["success"])
            self.assertIn("Invalid mode", result["error"])
            self.assertIn("invalid_mode", result["error"])

        asyncio.run(run_test())

    def test_auto_roto_video_not_found(self):
        """视频不存在应返回错误"""
        async def run_test():
            result = await self.service.auto_roto(
                video_path="/nonexistent/video.mp4",
                output_dir=self.temp_dir,
                mode="sam2_only",
            )
            self.assertFalse(result["success"])
            self.assertIn("Video not found", result["error"])

        asyncio.run(run_test())

    def test_auto_roto_valid_modes_listed_in_error(self):
        """错误信息应列出所有有效模式"""
        async def run_test():
            result = await self.service.auto_roto(
                video_path="/fake/video.mp4",
                output_dir=self.temp_dir,
                mode="bad",
            )
            for mode in RotoService.VALID_MODES:
                self.assertIn(mode, result["error"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 auto_roto sam2_only 模式
# ===========================================================================
class TestRotoServiceAutoRotoSam2Only(unittest.TestCase):
    """auto_roto sam2_only 模式测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test_video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sam2_only_success(self):
        """sam2_only 模式成功流程"""
        async def run_test():
            mask_dir = Path(self.temp_dir) / "output" / "sam2_masks"
            mask_dir.mkdir(parents=True, exist_ok=True)

            self.mock_sam2.export_mask_sequence.return_value = _make_engine_result(
                success=True,
                metadata={"mask_count": 30, "model_size": "base"},
            )

            with patch.object(self.service, "_evaluate_dir_quality", return_value=75.0):
                result = await self.service.auto_roto(
                    video_path=self.video_path,
                    output_dir=Path(self.temp_dir) / "output",
                    mode="sam2_only",
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["mode"], "sam2_only")
            self.assertIn("quality_score", result)
            self.assertIn("duration", result)

        asyncio.run(run_test())

    def test_sam2_only_engine_failure(self):
        """sam2_only 引擎失败应返回错误"""
        async def run_test():
            self.mock_sam2.export_mask_sequence.return_value = _make_engine_result(
                success=False,
                error="SAM2 model load failed",
            )

            result = await self.service.auto_roto(
                video_path=self.video_path,
                output_dir=Path(self.temp_dir) / "output",
                mode="sam2_only",
            )

            self.assertFalse(result["success"])
            self.assertIn("SAM2", result["error"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 auto_roto silhouette_only 模式
# ===========================================================================
class TestRotoServiceAutoRotoSilhouetteOnly(unittest.TestCase):
    """auto_roto silhouette_only 模式测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test_video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_silhouette_only_success(self):
        """silhouette_only 模式成功流程"""
        async def run_test():
            sil_output = Path(self.temp_dir) / "output" / "silhouette_masks"
            sil_output.mkdir(parents=True, exist_ok=True)
            (sil_output / "mask_0001.png").write_bytes(b"fake png")

            self.mock_silhouette.create_roto_session.return_value = _make_engine_result(
                success=True,
                output_path=str(sil_output),
                metadata={"feather": 2.0, "output_format": "PNG"},
            )

            with patch.object(self.service, "_evaluate_dir_quality", return_value=85.0):
                result = await self.service.auto_roto(
                    video_path=self.video_path,
                    output_dir=Path(self.temp_dir) / "output",
                    mode="silhouette_only",
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["mode"], "silhouette_only")

        asyncio.run(run_test())

    def test_silhouette_only_engine_failure(self):
        """silhouette_only 引擎失败应返回错误"""
        async def run_test():
            self.mock_silhouette.create_roto_session.return_value = _make_engine_result(
                success=False,
                error="Silhouette not installed",
            )

            result = await self.service.auto_roto(
                video_path=self.video_path,
                output_dir=Path(self.temp_dir) / "output",
                mode="silhouette_only",
            )

            self.assertFalse(result["success"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 auto_roto hybrid 模式
# ===========================================================================
class TestRotoServiceAutoRotoHybrid(unittest.TestCase):
    """auto_roto hybrid 模式测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test_video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hybrid_success(self):
        """hybrid 模式完整流水线成功"""
        async def run_test():
            output_dir = Path(self.temp_dir) / "output"

            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
            ) as mock_sam2_mask, \
            patch.object(
                self.service, "silhouette_refine",
                new_callable=AsyncMock,
            ) as mock_sil_refine, \
            patch.object(
                self.service, "_evaluate_dir_quality",
                return_value=88.0,
            ):
                mask_dir = str(output_dir / "01_sam2_masks")
                mock_sam2_mask.return_value = {
                    "success": True,
                    "mask_dir": mask_dir,
                    "mask_count": 30,
                    "model_size": "base",
                    "quality_score": 70.0,
                    "duration": 5.0,
                }

                refined_dir = str(output_dir / "03_silhouette_refined")
                mock_sil_refine.return_value = {
                    "success": True,
                    "refined_mask_dir": refined_dir,
                    "quality_score": 88.0,
                    "duration": 8.0,
                    "feather": 2.0,
                    "motion_blur": 0.5,
                    "bezier_simplify": 1.0,
                }

                self.mock_sam2.export_silhouette_shape.return_value = _make_engine_result(
                    success=True,
                    metadata={"frame_count": 30, "simplify_tolerance": 1.0},
                )

                alpha_dir = output_dir / "alpha"
                alpha_dir.mkdir(parents=True, exist_ok=True)
                self.mock_silhouette.render_alpha.return_value = _make_engine_result(
                    success=True,
                    output_path=str(alpha_dir),
                    metadata={"output_format": "PNG"},
                )

                Path(mask_dir).mkdir(parents=True, exist_ok=True)

                result = await self.service.auto_roto(
                    video_path=self.video_path,
                    output_dir=output_dir,
                    mode="hybrid",
                )

                self.assertTrue(result["success"])
                self.assertEqual(result["mode"], "hybrid")

        asyncio.run(run_test())

    def test_hybrid_sam2_stage_failure(self):
        """hybrid 模式 SAM2 阶段失败应返回错误"""
        async def run_test():
            output_dir = Path(self.temp_dir) / "output"

            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
            ) as mock_sam2_mask:
                mock_sam2_mask.return_value = {
                    "success": False,
                    "error": "SAM2 model not found",
                    "duration": 1.0,
                }

                result = await self.service.auto_roto(
                    video_path=self.video_path,
                    output_dir=output_dir,
                    mode="hybrid",
                )

                self.assertFalse(result["success"])
                self.assertIn("SAM2 stage failed", result["error"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 sam2_auto_mask
# ===========================================================================
class TestRotoServiceSam2AutoMask(unittest.TestCase):
    """sam2_auto_mask 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sam2_auto_mask_success(self):
        """SAM2 自动遮罩生成成功"""
        async def run_test():
            self.mock_sam2.export_mask_sequence.return_value = _make_engine_result(
                success=True,
                metadata={"mask_count": 25, "model_size": "base"},
            )

            with patch.object(self.service, "_evaluate_dir_quality", return_value=72.0):
                result = await self.service.sam2_auto_mask(
                    video_path="/fake/video.mp4",
                    output_dir=self.temp_dir,
                )

            self.assertTrue(result["success"])
            self.assertEqual(result["mask_count"], 25)
            self.assertIn("quality_score", result)

        asyncio.run(run_test())

    def test_sam2_auto_mask_failure(self):
        """SAM2 自动遮罩生成失败"""
        async def run_test():
            self.mock_sam2.export_mask_sequence.return_value = _make_engine_result(
                success=False,
                error="CUDA out of memory",
            )

            result = await self.service.sam2_auto_mask(
                video_path="/fake/video.mp4",
                output_dir=self.temp_dir,
            )

            self.assertFalse(result["success"])
            self.assertIn("error", result)

        asyncio.run(run_test())

    def test_sam2_auto_mask_exception(self):
        """SAM2 引擎抛异常时应捕获"""
        async def run_test():
            self.mock_sam2.export_mask_sequence.side_effect = RuntimeError("crash")

            result = await self.service.sam2_auto_mask(
                video_path="/fake/video.mp4",
                output_dir=self.temp_dir,
            )

            self.assertFalse(result["success"])
            self.assertIn("crash", result["error"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 silhouette_refine
# ===========================================================================
class TestRotoServiceSilhouetteRefine(unittest.TestCase):
    """silhouette_refine 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.mask_dir = Path(self.temp_dir) / "masks"
        self.mask_dir.mkdir()
        (self.mask_dir / "mask_0001.png").write_bytes(b"fake png")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_silhouette_refine_success(self):
        """Silhouette 精修成功"""
        async def run_test():
            self.mock_silhouette.refine_mask.return_value = _make_engine_result(
                success=True,
                duration_seconds=8.0,
            )

            with patch.object(self.service, "_evaluate_dir_quality", return_value=90.0):
                result = await self.service.silhouette_refine(
                    mask_dir=self.mask_dir,
                    output_dir=self.temp_dir,
                )

            self.assertTrue(result["success"])
            self.assertIn("refined_mask_dir", result)
            self.assertAlmostEqual(result["feather"], 2.0)

        asyncio.run(run_test())

    def test_silhouette_refine_mask_dir_not_found(self):
        """mask 目录不存在应返回错误"""
        async def run_test():
            result = await self.service.silhouette_refine(
                mask_dir="/nonexistent/masks",
                output_dir=self.temp_dir,
            )

            self.assertFalse(result["success"])
            self.assertIn("not found", result["error"])

        asyncio.run(run_test())

    def test_silhouette_refine_engine_failure(self):
        """Silhouette 引擎失败应返回错误"""
        async def run_test():
            self.mock_silhouette.refine_mask.return_value = _make_engine_result(
                success=False,
                error="License expired",
            )

            result = await self.service.silhouette_refine(
                mask_dir=self.mask_dir,
                output_dir=self.temp_dir,
            )

            self.assertFalse(result["success"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 evaluate_quality（Mock cv2）
# ===========================================================================
class TestRotoServiceEvaluateQuality(unittest.TestCase):
    """evaluate_quality 方法测试 - Mock cv2/numpy"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_evaluate_quality_file_not_exists(self):
        """文件不存在应返回 0.0"""
        score = self.service.evaluate_quality("/nonexistent/mask.png")
        self.assertEqual(score, 0.0)

    def test_evaluate_quality_success(self):
        """正常 mask 应返回综合评分"""
        mask_file = Path(self.temp_dir) / "mask.png"
        mask_file.write_bytes(b"fake png")

        with patch.object(self.service, "_calc_edge_sharpness", return_value=70.0), \
             patch.object(self.service, "_calc_connectivity", return_value=90.0), \
             patch.object(self.service, "_calc_noise_level", return_value=10.0), \
             patch.object(self.service, "_calc_fill_ratio", return_value=80.0):
            # Mock cv2 以跳过 imread/threshold
            mock_cv2 = MagicMock()
            fake_mask = MagicMock()
            fake_binary = MagicMock()
            mock_cv2.imread.return_value = fake_mask
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.threshold.return_value = (0, fake_binary)

            with patch.dict("sys.modules", {"cv2": mock_cv2}):
                score = self.service.evaluate_quality(mask_file)

        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_evaluate_quality_imread_returns_none(self):
        """cv2.imread 返回 None 时应返回 0.0"""
        mask_file = Path(self.temp_dir) / "mask.png"
        mask_file.write_bytes(b"fake png")

        mock_cv2 = MagicMock()
        mock_cv2.imread.return_value = None
        mock_cv2.IMREAD_GRAYSCALE = 0

        with patch.dict("sys.modules", {"cv2": mock_cv2}):
            score = self.service.evaluate_quality(mask_file)

        self.assertEqual(score, 0.0)

    def test_evaluate_quality_with_reference(self):
        """有参考 mask 时应结合 IoU 评分"""
        mask_file = Path(self.temp_dir) / "mask.png"
        ref_file = Path(self.temp_dir) / "ref.png"
        mask_file.write_bytes(b"fake png")
        ref_file.write_bytes(b"fake ref")

        with patch.object(self.service, "_calc_edge_sharpness", return_value=70.0), \
             patch.object(self.service, "_calc_connectivity", return_value=90.0), \
             patch.object(self.service, "_calc_noise_level", return_value=10.0), \
             patch.object(self.service, "_calc_fill_ratio", return_value=80.0), \
             patch.object(self.service, "_calc_iou", return_value=0.85):

            mock_cv2 = MagicMock()
            fake_mask = MagicMock()
            fake_binary = MagicMock()
            fake_ref_mask = MagicMock()
            fake_ref_binary = MagicMock()
            mock_cv2.imread.side_effect = [fake_mask, fake_ref_mask]
            mock_cv2.IMREAD_GRAYSCALE = 0
            mock_cv2.threshold.side_effect = [(0, fake_binary), (0, fake_ref_binary)]

            with patch.dict("sys.modules", {"cv2": mock_cv2}):
                score = self.service.evaluate_quality(mask_file, reference=ref_file)

        self.assertGreater(score, 0.0)


# ===========================================================================
# 测试 generate_roto_report
# ===========================================================================
class TestRotoServiceGenerateReport(unittest.TestCase):
    """generate_roto_report 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_report_success_result(self):
        """成功结果应生成完整报告"""
        result = {
            "success": True,
            "mode": "hybrid",
            "duration": 15.5,
            "quality_score": 88.5,
            "video_path": "/path/to/video.mp4",
            "output_dir": "/path/to/output",
            "mask_path": "/path/to/masks",
            "alpha_path": "/path/to/alpha",
            "report_path": "/path/to/roto_report.txt",
            "details": {
                "sam2": {
                    "success": True,
                    "mask_count": 30,
                    "model_size": "base",
                    "quality_score": 70.0,
                    "duration": 5.0,
                },
                "silhouette_refine": {
                    "success": True,
                    "feather": 2.0,
                    "motion_blur": 0.5,
                    "bezier_simplify": 1.0,
                    "quality_score": 88.0,
                    "duration": 8.0,
                },
            },
        }

        report = self.service.generate_roto_report(result)

        self.assertIn("成功", report)
        self.assertIn("hybrid", report)
        self.assertIn("88.50", report)
        self.assertIn("SAM2", report)
        self.assertIn("Silhouette", report)

    def test_report_failure_result(self):
        """失败结果应包含错误信息"""
        result = {
            "success": False,
            "mode": "sam2_only",
            "duration": 2.0,
            "quality_score": 0.0,
            "error": "SAM2 model load failed",
            "details": {},
        }

        report = self.service.generate_roto_report(result)

        self.assertIn("失败", report)
        self.assertIn("SAM2 model load failed", report)
        self.assertIn("错误信息", report)

    def test_report_no_details(self):
        """无详情的报告不应崩溃"""
        result = {
            "success": True,
            "mode": "sam2_only",
            "duration": 5.0,
            "quality_score": 75.0,
        }

        report = self.service.generate_roto_report(result)
        self.assertIn("成功", report)


# ===========================================================================
# 测试 _evaluate_dir_quality
# ===========================================================================
class TestRotoServiceEvaluateDirQuality(unittest.TestCase):
    """_evaluate_dir_quality 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nonexistent_dir_returns_zero(self):
        """不存在的目录应返回 0.0"""
        score = self.service._evaluate_dir_quality(Path("/nonexistent/dir"))
        self.assertEqual(score, 0.0)

    def test_empty_dir_returns_zero(self):
        """空目录应返回 0.0"""
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()
        score = self.service._evaluate_dir_quality(empty_dir)
        self.assertEqual(score, 0.0)

    def test_dir_with_masks_returns_score(self):
        """含 mask 文件的目录应返回评分"""
        mask_dir = Path(self.temp_dir) / "masks"
        mask_dir.mkdir()
        for i in range(5):
            (mask_dir / f"mask_{i:04d}.png").write_bytes(b"fake png")

        with patch.object(self.service, "evaluate_quality", return_value=75.0):
            score = self.service._evaluate_dir_quality(mask_dir)

        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 100.0)


# ===========================================================================
# 测试 _calc_fill_ratio
# ===========================================================================
class TestRotoServiceCalcFillRatio(unittest.TestCase):
    """_calc_fill_ratio 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_fill_ratio_reasonable_foreground(self):
        """前景占比 0.1-0.7 应得满分 100"""
        import numpy as np
        for ratio in [0.1, 0.3, 0.5, 0.7]:
            # 构建一个 total_pixels=1000, 前景=int(ratio*1000) 的二值数组
            mask = np.zeros(1000, dtype=np.uint8)
            mask[: int(ratio * 1000)] = 255
            score = self.service._calc_fill_ratio(mask)
            self.assertEqual(score, 100.0, f"ratio={ratio} 应得 100 分")

    def test_fill_ratio_very_low_foreground(self):
        """前景占比很低（<0.1）应得较低分"""
        import numpy as np
        # ratio = 0.05 → score = 0.05 * 10 * 100 = 50.0
        mask = np.zeros(1000, dtype=np.uint8)
        mask[:50] = 255
        score = self.service._calc_fill_ratio(mask)
        self.assertAlmostEqual(score, 50.0)

    def test_fill_ratio_very_high_foreground(self):
        """前景占比很高（>0.7）应得较低分"""
        import numpy as np
        # ratio = 0.85 → score = (1.0 - 0.85) / 0.3 * 100 = 50.0
        mask = np.zeros(1000, dtype=np.uint8)
        mask[:850] = 255
        score = self.service._calc_fill_ratio(mask)
        self.assertAlmostEqual(score, 50.0)

    def test_fill_ratio_zero_size(self):
        """size=0 的 mask 应返回 50.0"""
        import numpy as np
        mask = np.array([], dtype=np.uint8)
        score = self.service._calc_fill_ratio(mask)
        self.assertEqual(score, 50.0)


# ===========================================================================
# 测试 _calc_iou
# ===========================================================================
class TestRotoServiceCalcIou(unittest.TestCase):
    """_calc_iou 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_iou_perfect_overlap(self):
        """完全重合的两个 mask IoU 应为 1.0"""
        import numpy as np
        mask1 = np.array([1, 1, 0, 0], dtype=np.uint8)
        mask2 = np.array([1, 1, 0, 0], dtype=np.uint8)
        iou = self.service._calc_iou(mask1, mask2)
        self.assertEqual(iou, 1.0)

    def test_iou_no_overlap(self):
        """完全不重叠的两个 mask IoU 应为 0.0"""
        import numpy as np
        mask1 = np.array([1, 1, 0, 0], dtype=np.uint8)
        mask2 = np.array([0, 0, 1, 1], dtype=np.uint8)
        iou = self.service._calc_iou(mask1, mask2)
        self.assertEqual(iou, 0.0)

    def test_iou_empty_union(self):
        """两个空 mask 的 IoU 应为 0.0"""
        import numpy as np
        mask1 = np.array([0, 0, 0], dtype=np.uint8)
        mask2 = np.array([0, 0, 0], dtype=np.uint8)
        iou = self.service._calc_iou(mask1, mask2)
        self.assertEqual(iou, 0.0)

    def test_iou_partial_overlap(self):
        """部分重叠的两个 mask IoU 应为 0.0-1.0"""
        import numpy as np
        mask1 = np.array([1, 1, 1, 0], dtype=np.uint8)
        mask2 = np.array([0, 1, 1, 1], dtype=np.uint8)
        # intersection = [0,1,1,0] → sum=2, union=[1,1,1,1] → sum=4, IoU=0.5
        iou = self.service._calc_iou(mask1, mask2)
        self.assertAlmostEqual(iou, 0.5)


# ===========================================================================
# 测试 _calc_edge_sharpness
# ===========================================================================
class TestRotoServiceCalcEdgeSharpness(unittest.TestCase):
    """_calc_edge_sharpness 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_edge_sharpness_with_edges(self):
        """有边缘的 mask 应返回锐度评分"""
        import numpy as np
        # 构建一个有明显边缘的图像（左半0 右半255）
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[:, 50:] = 255
        score = self.service._calc_edge_sharpness(mask)
        self.assertGreater(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_edge_sharpness_uniform_image(self):
        """均匀图像应返回较低锐度"""
        import numpy as np
        # 全黑图像无边缘
        mask = np.zeros((100, 100), dtype=np.uint8)
        score = self.service._calc_edge_sharpness(mask)
        self.assertEqual(score, 0.0)


# ===========================================================================
# 测试 _calc_connectivity
# ===========================================================================
class TestRotoServiceCalcConnectivity(unittest.TestCase):
    """_calc_connectivity 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_connectivity_single_component(self):
        """单一连通区域应返回高分"""
        import numpy as np
        # 单一白色方块
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[25:75, 25:75] = 255
        score = self.service._calc_connectivity(mask)
        self.assertGreater(score, 90.0)

    def test_connectivity_no_foreground(self):
        """无前景像素时应返回 50.0"""
        import numpy as np
        mask = np.zeros((100, 100), dtype=np.uint8)
        score = self.service._calc_connectivity(mask)
        self.assertEqual(score, 50.0)


# ===========================================================================
# 测试 _calc_noise_level
# ===========================================================================
class TestRotoServiceCalcNoiseLevel(unittest.TestCase):
    """_calc_noise_level 方法测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )

    def test_noise_level_low_noise(self):
        """低噪声 mask 应返回较低噪声分"""
        import numpy as np
        # 均匀图像 → 噪声几乎为零
        mask = np.full((100, 100), 128, dtype=np.uint8)
        score = self.service._calc_noise_level(mask)
        self.assertLess(score, 10.0)

    def test_noise_level_empty_mask(self):
        """全黑 mask 应无噪声"""
        import numpy as np
        mask = np.zeros((100, 100), dtype=np.uint8)
        score = self.service._calc_noise_level(mask)
        self.assertEqual(score, 0.0)


# ===========================================================================
# 测试 _hybrid_roto_pipeline
# ===========================================================================
class TestRotoServiceHybridPipeline(unittest.TestCase):
    """_hybrid_roto_pipeline 完整流水线测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test_video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_hybrid_pipeline_full_success(self):
        """完整 hybrid 流水线成功"""
        async def run_test():
            output_dir = Path(self.temp_dir) / "output"

            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
            ) as mock_sam2_mask, \
            patch.object(
                self.service, "silhouette_refine",
                new_callable=AsyncMock,
            ) as mock_sil_refine, \
            patch.object(
                self.service, "_evaluate_dir_quality",
                return_value=90.0,
            ):
                mask_dir = str(output_dir / "01_sam2_masks")
                Path(mask_dir).mkdir(parents=True, exist_ok=True)

                mock_sam2_mask.return_value = {
                    "success": True,
                    "mask_dir": mask_dir,
                    "mask_count": 25,
                    "model_size": "base",
                    "quality_score": 65.0,
                    "duration": 5.0,
                }

                refined_dir = str(output_dir / "03_silhouette_refined")
                Path(refined_dir).mkdir(parents=True, exist_ok=True)

                mock_sil_refine.return_value = {
                    "success": True,
                    "refined_mask_dir": refined_dir,
                    "quality_score": 88.0,
                    "duration": 8.0,
                    "feather": 2.0,
                    "motion_blur": 0.5,
                    "bezier_simplify": 1.0,
                }

                self.mock_sam2.export_silhouette_shape.return_value = _make_engine_result(
                    success=True,
                    metadata={"frame_count": 25, "simplify_tolerance": 1.0},
                )

                alpha_dir = output_dir / "alpha"
                alpha_dir.mkdir(parents=True, exist_ok=True)
                self.mock_silhouette.render_alpha.return_value = _make_engine_result(
                    success=True,
                    output_path=str(alpha_dir),
                    metadata={"output_format": "PNG"},
                )

                result = await self.service._hybrid_roto_pipeline(
                    video_path=self.video_path,
                    output_dir=output_dir,
                )

                self.assertTrue(result["success"])
                self.assertIn("mask_path", result)
                self.assertIn("alpha_path", result)
                self.assertIn("details", result)
                self.assertEqual(result["quality_score"], 90.0)

                mock_sam2_mask.assert_called_once()
                mock_sil_refine.assert_called_once()
                self.mock_sam2.export_silhouette_shape.assert_called_once()
                self.mock_silhouette.render_alpha.assert_called_once()

        asyncio.run(run_test())

    def test_hybrid_pipeline_sam2_fails(self):
        """SAM2 阶段失败应返回错误"""
        async def run_test():
            output_dir = Path(self.temp_dir) / "output"

            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
            ) as mock_sam2_mask:
                mock_sam2_mask.return_value = {
                    "success": False,
                    "error": "Model not found",
                    "duration": 1.0,
                }

                result = await self.service._hybrid_roto_pipeline(
                    video_path=self.video_path,
                    output_dir=output_dir,
                )

                self.assertFalse(result["success"])
                self.assertIn("SAM2 stage failed", result["error"])

        asyncio.run(run_test())

    def test_hybrid_pipeline_silhouette_refine_fails_gracefully(self):
        """Silhouette 精修失败应降级使用 SAM2 masks"""
        async def run_test():
            output_dir = Path(self.temp_dir) / "output"
            mask_dir = output_dir / "01_sam2_masks"
            mask_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
            ) as mock_sam2_mask, \
            patch.object(
                self.service, "silhouette_refine",
                new_callable=AsyncMock,
            ) as mock_sil_refine, \
            patch.object(
                self.service, "_evaluate_dir_quality",
                return_value=70.0,
            ):
                mock_sam2_mask.return_value = {
                    "success": True,
                    "mask_dir": str(mask_dir),
                    "mask_count": 25,
                    "model_size": "base",
                    "quality_score": 65.0,
                    "duration": 5.0,
                }

                mock_sil_refine.return_value = {
                    "success": False,
                    "error": "Silhouette crashed",
                    "duration": 2.0,
                }

                self.mock_sam2.export_silhouette_shape.return_value = _make_engine_result(
                    success=True,
                    metadata={"frame_count": 25, "simplify_tolerance": 1.0},
                )

                alpha_dir = output_dir / "alpha"
                alpha_dir.mkdir(parents=True, exist_ok=True)
                self.mock_silhouette.render_alpha.return_value = _make_engine_result(
                    success=True,
                    output_path=str(alpha_dir),
                    metadata={"output_format": "PNG"},
                )

                result = await self.service._hybrid_roto_pipeline(
                    video_path=self.video_path,
                    output_dir=output_dir,
                )

                self.assertTrue(result["success"])

        asyncio.run(run_test())


# ===========================================================================
# 测试 auto_roto 异常捕获
# ===========================================================================
class TestRotoServiceAutoRotoExceptionHandling(unittest.TestCase):
    """auto_roto 异常处理测试"""

    def setUp(self):
        self.mock_sam2 = _make_mock_sam2()
        self.mock_silhouette = _make_mock_silhouette()
        self.service = RotoService(
            sam2_engine=self.mock_sam2,
            silhouette_engine=self.mock_silhouette,
        )
        self.temp_dir = tempfile.mkdtemp()
        self.video_path = Path(self.temp_dir) / "test_video.mp4"
        self.video_path.write_bytes(b"fake video")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_auto_roto_unexpected_exception(self):
        """auto_roto 中未预期异常应被捕获"""
        async def run_test():
            with patch.object(
                self.service, "sam2_auto_mask",
                new_callable=AsyncMock,
                side_effect=RuntimeError("unexpected crash"),
            ):
                result = await self.service.auto_roto(
                    video_path=self.video_path,
                    output_dir=Path(self.temp_dir) / "output",
                    mode="sam2_only",
                )

            self.assertFalse(result["success"])
            self.assertIn("unexpected crash", result["error"])

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main(verbosity=2)
