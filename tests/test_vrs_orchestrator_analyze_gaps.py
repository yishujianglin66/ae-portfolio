#!/usr/bin/env python3
"""
tests/test_vrs_orchestrator_analyze_gaps.py - VRSOrchestrator.analyze() 纯CV入口回归测试

覆盖 commit bf99595 引入的 VRSOrchestrator.analyze() 方法：
  1. detail_level → num_frames 映射 (quick=12, standard=18, full=24)
  2. 显式 num_frames 覆盖 detail_level
  3. VRSRealAnalyzer 成功 → 结果透传 + 日志
  4. VRSRealAnalyzer 抛异常 → 返回 success=False 但不传播异常
  5. options=None 使用默认 detail_level=standard → 18 帧
  6. 未知 detail_level → 回退到 18 帧

这是 perceive 阶段的真分析入口，异常处理回归会导致整个管线崩溃。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from vrs.vrs_orchestrator import VRSOrchestrator, DEFAULT_OPTIONS


@pytest.fixture
def orchestrator() -> VRSOrchestrator:
    """构造编排器实例。"""
    return VRSOrchestrator()


# =========================================================================
#  场景 1：detail_level → num_frames 映射
# =========================================================================
class TestDetailLevelMapping:
    """detail_level 到 num_frames 的映射必须与文档一致。"""

    @pytest.mark.parametrize("detail_level,expected_frames", [
        ("quick", 12),
        ("standard", 18),
        ("full", 24),
    ])
    def test_detail_level_to_num_frames_mapping(
        self,
        orchestrator: VRSOrchestrator,
        detail_level: str,
        expected_frames: int,
    ) -> None:
        """quick=12, standard=18, full=24 帧映射。"""
        captured_num_frames: Dict[str, int] = {}

        async def fake_analyze(self_real, video_path: str) -> Dict[str, Any]:
            # 捕获 VRSRealAnalyzer 构造时传入的 num_frames
            return {"success": True, "source": "real_opencv_analysis"}

        # 拦截 VRSRealAnalyzer 的构造与 analyze 调用
        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                captured_num_frames["value"] = num_frames

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                return {
                    "success": True,
                    "source": "real_opencv_analysis",
                    "confidence": 0.85,
                    "style_tags": ["cinematic"],
                }

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            result = asyncio.run(orchestrator.analyze(
                video_path="/fake/video.mp4",
                options={"detail_level": detail_level},
            ))

        assert captured_num_frames["value"] == expected_frames
        assert result["success"] is True

    def test_explicit_num_frames_overrides_detail_level(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """显式 num_frames 覆盖 detail_level 的映射值。"""
        captured: Dict[str, int] = {}

        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                captured["value"] = num_frames

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                return {"success": True, "source": "real_opencv_analysis"}

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            asyncio.run(orchestrator.analyze(
                video_path="/fake/video.mp4",
                options={"detail_level": "quick", "num_frames": 30},
            ))

        # 显式 num_frames=30 覆盖 quick=12
        assert captured["value"] == 30

    def test_unknown_detail_level_falls_back_to_18(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """未知 detail_level → num_frames_map.get(detail_level, 18) → 18。"""
        captured: Dict[str, int] = {}

        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                captured["value"] = num_frames

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                return {"success": True}

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            asyncio.run(orchestrator.analyze(
                video_path="/fake/video.mp4",
                options={"detail_level": "ultra_extreme"},  # 未知值
            ))

        assert captured["value"] == 18

    def test_options_none_uses_default_standard(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """options=None → 使用 self.config 的默认 detail_level=standard → 18 帧。"""
        captured: Dict[str, int] = {}

        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                captured["value"] = num_frames

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                return {"success": True}

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            asyncio.run(orchestrator.analyze(
                video_path="/fake/video.mp4",
                options=None,
            ))

        # DEFAULT_OPTIONS["detail_level"] = "standard" → 18
        assert DEFAULT_OPTIONS["detail_level"] == "standard"
        assert captured["value"] == 18


# =========================================================================
#  场景 2：VRSRealAnalyzer 成功路径
# =========================================================================
class TestSuccessPath:
    """VRSRealAnalyzer 正常返回 → 结果透传，不抛异常。"""

    def test_successful_result_passthrough(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """VRSRealAnalyzer 返回成功 → 结果原样透传。"""
        expected_result = {
            "success": True,
            "source": "real_opencv_analysis",
            "confidence": 0.92,
            "style_tags": ["cinematic", "neon"],
            "color_palette": {"temperature": "warm", "saturation": 0.7},
            "rhythm": {"tempo": 120, "shot_count": 8},
        }

        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                pass

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                return expected_result

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        assert result == expected_result
        assert result["success"] is True
        assert result["source"] == "real_opencv_analysis"
        assert result["confidence"] == 0.92

    def test_video_path_converted_to_string(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """video_path 为 Path 对象时 → 转为 str 后传给 VRSRealAnalyzer。"""
        captured_path: Dict[str, str] = {}

        class FakeVRSRealAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                pass

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                captured_path["value"] = video_path
                return {"success": True}

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FakeVRSRealAnalyzer):
            asyncio.run(orchestrator.analyze(Path("/fake/path.mp4")))

        assert isinstance(captured_path["value"], str)
        assert captured_path["value"] == "/fake/path.mp4" or "path.mp4" in captured_path["value"]


# =========================================================================
#  场景 3：VRSRealAnalyzer 异常处理
# =========================================================================
class TestExceptionHandling:
    """VRSRealAnalyzer 抛异常 → 返回 success=False 但不传播异常。"""

    def test_import_error_returns_failure(self, orchestrator: VRSOrchestrator) -> None:
        """VRSRealAnalyzer 模块导入失败 → 返回结构化错误，不抛异常。"""
        with patch(
            "vrs.vrs_real_analyzer.VRSRealAnalyzer",
            side_effect=ImportError("cv2 not installed"),
        ):
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        assert result["success"] is False
        assert result["source"] == "real_opencv_analysis"
        assert "error" in result
        # error 格式为 "VRSRealAnalyzer failed: {str(exception)}"
        # str(ImportError("cv2 not installed")) = "cv2 not installed"（不含类型名）
        assert "VRSRealAnalyzer failed" in result["error"]
        assert "cv2 not installed" in result["error"]
        assert result["confidence"] == 0.0
        assert result["video_path"] == "/fake/video.mp4"

    def test_runtime_error_returns_failure(self, orchestrator: VRSOrchestrator) -> None:
        """VRSRealAnalyzer 运行时错误 → 返回结构化错误。"""
        with patch(
            "vrs.vrs_real_analyzer.VRSRealAnalyzer",
            side_effect=RuntimeError("OpenCV VideoCapture failed"),
        ):
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        assert result["success"] is False
        assert "VRSRealAnalyzer failed" in result["error"]
        assert "OpenCV VideoCapture failed" in result["error"]
        assert result["confidence"] == 0.0

    def test_unexpected_exception_returns_failure(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """任意异常 → 都不应传播到调用方。"""
        with patch(
            "vrs.vrs_real_analyzer.VRSRealAnalyzer",
            side_effect=ValueError("unexpected"),
        ):
            # 不应抛异常
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        assert result["success"] is False
        assert "VRSRealAnalyzer failed" in result["error"]
        assert "unexpected" in result["error"]

    def test_analyze_method_raises_returns_failure(
        self, orchestrator: VRSOrchestrator
    ) -> None:
        """VRSRealAnalyzer.analyze() 方法本身抛异常 → 同样被捕获。"""
        class FailingAnalyzer:
            def __init__(self_inner, num_frames: int = 18) -> None:
                pass

            async def analyze(self_inner, video_path: str) -> Dict[str, Any]:
                raise IOError("video file corrupted")

        with patch("vrs.vrs_real_analyzer.VRSRealAnalyzer", FailingAnalyzer):
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        assert result["success"] is False
        assert "VRSRealAnalyzer failed" in result["error"]
        assert "video file corrupted" in result["error"]


# =========================================================================
#  场景 4：返回错误结构完整性
# =========================================================================
class TestErrorReturnStructure:
    """异常路径返回的 dict 必须包含所有承诺的字段。"""

    def test_error_return_fields(self, orchestrator: VRSOrchestrator) -> None:
        """异常返回必须包含 success/source/error/video_path/confidence。"""
        with patch(
            "vrs.vrs_real_analyzer.VRSRealAnalyzer",
            side_effect=Exception("test"),
        ):
            result = asyncio.run(orchestrator.analyze("/fake/video.mp4"))

        required_fields = {"success", "source", "error", "video_path", "confidence"}
        assert required_fields.issubset(result.keys())
        assert result["success"] is False
        assert result["source"] == "real_opencv_analysis"
        assert result["confidence"] == 0.0
        assert result["video_path"] == "/fake/video.mp4"
