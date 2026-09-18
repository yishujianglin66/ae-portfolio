#!/usr/bin/env python3
"""
test_ai_honest_degradation.py — AI 伪实现诚实降级逻辑测试

验证 4 处 "伪 AI 实现" 在缺少真实权重/端点时：
1. ai_scene_detector：不返回随机噪声，AI 路径默认关闭，标记降级原因
2. frame_interpolator：RIFE 缺失时降级到光流/混合，不返回假 AI 补帧
3. sam2 engine：不生成假遮罩，返回 success=False + 明确错误
4. RenderFarmAdapter：不返回假 submitted，返回 unsupported + success=False
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))


class TestAISceneDetectorHonestDegradation(unittest.TestCase):
    """TransNetV2 伪实现：AI 路径默认关闭，无权重时降级标记。"""

    def test_ai_default_off(self):
        from ae.ai_scene_detector import AISceneDetector
        detector = AISceneDetector()
        self.assertFalse(detector.enable_ai)
        self.assertFalse(detector._transnet_available)
        self.assertIsNone(detector._model)

    def test_ai_enabled_but_no_weights_degrades(self):
        from ae.ai_scene_detector import AISceneDetector
        detector = AISceneDetector(enable_ai=True)
        # 无真实权重时模型不可用，且记录了降级原因
        self.assertFalse(detector._transnet_available)
        self.assertIsNotNone(detector._degraded_reason)
        self.assertIn("transnetv2", detector._degraded_reason)


class TestFrameInterpolatorHonestDegradation(unittest.TestCase):
    """RIFE 伪实现：无权重时 RIFE 不可用，不会构造随机 IFNet。"""

    def test_rife_unavailable_without_weights(self):
        from ae.frame_interpolator import FrameInterpolator, InterpolationMethod
        interp = FrameInterpolator(method=InterpolationMethod.RIFE)
        self.assertFalse(interp._rife_available)
        self.assertIsNone(interp._model)
        self.assertIsNotNone(interp._degraded_reason)

    def test_default_method_is_optical_flow(self):
        from ae.frame_interpolator import FrameInterpolator, InterpolationMethod
        interp = FrameInterpolator()
        self.assertEqual(interp.method, InterpolationMethod.OPTICAL_FLOW)


class TestSAM2EngineHonestDegradation(unittest.TestCase):
    """SAM2 假遮罩：无权重时返回 success=False，绝不生成假遮罩。"""

    def test_auto_mask_fails_without_weights(self):
        from engines.sam2.engine import SAM2Engine
        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "clip.mp4"
            video.write_bytes(b"fake")
            engine = SAM2Engine(model_dir=Path(tmpdir) / "models")
            engine._sam2 = True  # 模拟 sam2 已安装（引擎约定 _sam2 必须为布尔 True）

            async def run():
                res = await engine.auto_mask(video, Path(tmpdir) / "out")
                return res

            res = asyncio.run(run())
            self.assertFalse(res.success)
            self.assertTrue("权重" in res.error or "推理" in res.error)

    def test_export_mask_sequence_fails_without_weights(self):
        from engines.sam2.engine import SAM2Engine
        with tempfile.TemporaryDirectory() as tmpdir:
            video = Path(tmpdir) / "clip.mp4"
            video.write_bytes(b"fake")
            engine = SAM2Engine(model_dir=Path(tmpdir) / "models")
            engine._sam2 = True

            async def run():
                res = await engine.export_mask_sequence(video, Path(tmpdir) / "out")
                return res

            res = asyncio.run(run())
            self.assertFalse(res.success)


class TestRenderFarmAdapterHonestDegradation(unittest.TestCase):
    """RenderFarmAdapter 假提交：无端点时返回 unsupported，绝不假成功。"""

    def test_opencue_unsupported_without_endpoint(self):
        from ae.distributed_renderer import RenderFarmAdapter
        adapter = RenderFarmAdapter(farm_type="opencue")
        res = adapter.submit_to_opencue("p.aep", "out.mp4")
        self.assertEqual(res["status"], "unsupported")
        self.assertFalse(res["success"])
        self.assertIn("未配置", res["error"])

    def test_afanasy_unsupported_without_endpoint(self):
        from ae.distributed_renderer import RenderFarmAdapter
        adapter = RenderFarmAdapter(farm_type="afanasy")
        res = adapter.submit_to_afanasy("p.aep", "out.mp4")
        self.assertEqual(res["status"], "unsupported")
        self.assertFalse(res["success"])

    def test_configured_endpoint_raises_not_implemented(self):
        # 配置了端点但真实提交未接入 → 应抛错而非假成功
        from ae.distributed_renderer import RenderFarmAdapter
        adapter = RenderFarmAdapter(farm_type="opencue", endpoint="http://openue:2080")
        with self.assertRaises(NotImplementedError):
            adapter.submit_to_opencue("p.aep", "out.mp4")


if __name__ == "__main__":
    unittest.main()