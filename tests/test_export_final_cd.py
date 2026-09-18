"""tests/test_export_final_cd.py — D-17R C+D 导出管线单元测试
================================================================

验证 C+D 三段式导出管线的编排逻辑：
    Stage C1: AE → PNG 序列
    Stage C2: FFmpeg → 中间视频
    Stage D:  Resolve → 调色成片

测试策略：
    - 使用 mock 引擎替代真实软件调用
    - 验证各阶段成功/失败/降级路径
    - 验证结果数据完整性
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 确保项目根目录在 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pipeline.stages.export_final_cd import ExportCDResult, ExportFinalCD

# ============================================================================
#  辅助工具
# ============================================================================

def _make_engine_result(success: bool, **kwargs):
    """构造 EngineResult mock。"""
    from dataclasses import dataclass, field
    from typing import Any, Dict, Optional

    @dataclass
    class MockEngineResult:
        success: bool = True
        output_path: Path | None = None
        metadata: dict[str, Any] = field(default_factory=dict)
        error: str | None = None
        error_code: str | None = None
        duration_seconds: float = 0.0

    return MockEngineResult(success=success, **kwargs)


# ============================================================================
#  基础测试
# ============================================================================

class TestExportCDResult:
    """ExportCDResult 数据类测试。"""

    def test_default_values(self):
        r = ExportCDResult(success=False)
        assert r.success is False
        assert r.output_path is None
        assert r.stage_c1_ok is False
        assert r.stage_c2_ok is False
        assert r.stage_d_ok is False
        assert r.grade_skipped is False
        assert r.total_frames == 0
        assert r.errors == []

    def test_full_construction(self):
        r = ExportCDResult(
            success=True,
            output_path=Path("/tmp/final.mp4"),
            stage_c1_ok=True,
            stage_c2_ok=True,
            stage_d_ok=True,
            total_frames=720,
            grade_style="cinematic",
            elapsed_seconds=42.5,
        )
        assert r.success is True
        assert r.total_frames == 720
        assert r.grade_style == "cinematic"


class TestExportFinalCDInit:
    """ExportFinalCD 初始化测试。"""

    def test_default_params(self):
        p = ExportFinalCD()
        assert p.fps == 24.0
        assert p.codec == "libx264"
        assert p.crf == 16
        assert p.pixel_format == "yuv420p"
        assert p.frame_pattern == "frame_%06d.png"
        assert p.cleanup_frames is True

    def test_custom_params(self):
        p = ExportFinalCD(
            fps=30.0,
            codec="libx265",
            crf=18,
            pixel_format="yuv444p",
            frame_pattern="img_%04d.png",
            cleanup_frames=False,
        )
        assert p.fps == 30.0
        assert p.codec == "libx265"
        assert p.crf == 18
        assert p.cleanup_frames is False


class TestEnginePath:
    """引擎路径设置测试。"""

    def test_ensure_puppet_path(self):
        p = ExportFinalCD()
        p._ensure_puppet_path()
        puppet_src = str(_PROJECT_ROOT / "puppet-automation" / "src")
        assert puppet_src in sys.path

    def test_ensure_puppet_path_idempotent(self):
        p = ExportFinalCD()
        p._ensure_puppet_path()
        count1 = sys.path.count(str(_PROJECT_ROOT / "puppet-automation" / "src"))
        p._ensure_puppet_path()
        count2 = sys.path.count(str(_PROJECT_ROOT / "puppet-automation" / "src"))
        assert count1 == count2 == 1


# ============================================================================
#  编排逻辑测试（mock 引擎）
# ============================================================================

class TestPipelineOrchestration:
    """C+D 管线编排逻辑测试。"""

    @pytest.mark.asyncio
    async def test_all_stages_succeed(self, tmp_path):
        """全流程成功路径。"""
        pipeline = ExportFinalCD()
        output = tmp_path / "final.mp4"

        # Mock 三个引擎
        mock_ae = AsyncMock()
        mock_ae.render_comp.return_value = _make_engine_result(
            success=True,
            metadata={"frame_count": 120},
            duration_seconds=15.0,
        )

        mock_ff = AsyncMock()
        mock_ff.image_sequence_to_video.return_value = _make_engine_result(
            success=True,
            duration_seconds=5.0,
        )

        mock_davinci = AsyncMock()
        mock_davinci.apply_color_grade.return_value = _make_engine_result(
            success=True,
            duration_seconds=10.0,
        )

        # 注入 mock 引擎
        pipeline._engines_cache = {
            "ae": mock_ae,
            "ffmpeg": mock_ff,
            "davinci": mock_davinci,
        }

        # 模拟最终输出文件存在
        def fake_grade(*args, **kwargs):
            output.write_bytes(b"fake_video_data")
            return _make_engine_result(success=True, duration_seconds=10.0)

        mock_davinci.apply_color_grade.side_effect = fake_grade

        result = await pipeline.run(
            project_path="D:/fake/project.aep",
            comp_name="MainComp",
            output_path=output,
            audio_path="D:/fake/bgm.mp3",
            grade_style="cinematic",
        )

        assert result.success is True
        assert result.stage_c1_ok is True
        assert result.stage_c2_ok is True
        assert result.stage_d_ok is True
        assert result.grade_skipped is False
        assert result.total_frames == 120
        assert result.grade_style == "cinematic"
        assert len(result.errors) == 0

        # 验证引擎调用顺序
        mock_ae.render_comp.assert_called_once()
        mock_ff.image_sequence_to_video.assert_called_once()
        mock_davinci.apply_color_grade.assert_called_once()

    @pytest.mark.asyncio
    async def test_c1_failure_stops_pipeline(self, tmp_path):
        """C1 AE 渲染失败 → 整体失败。"""
        pipeline = ExportFinalCD()
        output = tmp_path / "final.mp4"

        mock_ae = AsyncMock()
        mock_ae.render_comp.return_value = _make_engine_result(
            success=False,
            error="aerender crashed",
        )

        pipeline._engines_cache = {"ae": mock_ae}

        result = await pipeline.run(
            project_path="D:/fake/project.aep",
            comp_name="MainComp",
            output_path=output,
        )

        assert result.success is False
        assert result.stage_c1_ok is False
        assert "C1 AE 渲染失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_c2_failure_stops_pipeline(self, tmp_path):
        """C2 FFmpeg 合成失败 → 整体失败。"""
        pipeline = ExportFinalCD()
        output = tmp_path / "final.mp4"

        mock_ae = AsyncMock()
        mock_ae.render_comp.return_value = _make_engine_result(
            success=True,
            metadata={"frame_count": 60},
            duration_seconds=8.0,
        )

        mock_ff = AsyncMock()
        mock_ff.image_sequence_to_video.return_value = _make_engine_result(
            success=False,
            error="ffmpeg encoding error",
        )

        pipeline._engines_cache = {"ae": mock_ae, "ffmpeg": mock_ff}

        result = await pipeline.run(
            project_path="D:/fake/project.aep",
            comp_name="MainComp",
            output_path=output,
        )

        assert result.success is False
        assert result.stage_c1_ok is True
        assert result.stage_c2_ok is False
        assert "C2 FFmpeg 合成失败" in result.errors[0]

    @pytest.mark.asyncio
    async def test_d_failure_fallback_to_intermediate(self, tmp_path):
        """D 调色失败 → 降级使用中间文件。"""
        pipeline = ExportFinalCD()
        output = tmp_path / "final.mp4"

        mock_ae = AsyncMock()
        mock_ae.render_comp.return_value = _make_engine_result(
            success=True,
            metadata={"frame_count": 48},
            duration_seconds=6.0,
        )

        mock_ff = AsyncMock()
        # 模拟 FFmpeg 生成中间文件
        def fake_ffmpeg(*args, **kwargs):
            output_path = kwargs.get("output_path") or args[1]
            Path(output_path).write_bytes(b"intermediate_video")
            return _make_engine_result(success=True, duration_seconds=3.0)

        mock_ff.image_sequence_to_video.side_effect = fake_ffmpeg

        mock_davinci = AsyncMock()
        mock_davinci.apply_color_grade.return_value = _make_engine_result(
            success=False,
            error="Resolve not available",
        )

        pipeline._engines_cache = {
            "ae": mock_ae,
            "ffmpeg": mock_ff,
            "davinci": mock_davinci,
        }

        result = await pipeline.run(
            project_path="D:/fake/project.aep",
            comp_name="MainComp",
            output_path=output,
            grade_style="warm_vintage",
        )

        assert result.success is True  # 降级成功
        assert result.stage_c1_ok is True
        assert result.stage_c2_ok is True
        assert result.grade_skipped is True  # 调色被跳过
        assert any("D 调色降级" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_skip_grade_flag(self, tmp_path):
        """skip_grade=True → 完全跳过 Stage D。"""
        pipeline = ExportFinalCD()
        output = tmp_path / "final.mp4"

        mock_ae = AsyncMock()
        mock_ae.render_comp.return_value = _make_engine_result(
            success=True,
            metadata={"frame_count": 30},
            duration_seconds=4.0,
        )

        mock_ff = AsyncMock()

        def fake_ffmpeg(*args, **kwargs):
            output_path = kwargs.get("output_path") or args[1]
            Path(output_path).write_bytes(b"intermediate_video")
            return _make_engine_result(success=True, duration_seconds=2.0)

        mock_ff.image_sequence_to_video.side_effect = fake_ffmpeg

        mock_davinci = AsyncMock()

        pipeline._engines_cache = {
            "ae": mock_ae,
            "ffmpeg": mock_ff,
            "davinci": mock_davinci,
        }

        result = await pipeline.run(
            project_path="D:/fake/project.aep",
            comp_name="MainComp",
            output_path=output,
            skip_grade=True,
        )

        assert result.success is True
        assert result.grade_skipped is True
        # Resolve 引擎不应被调用
        mock_davinci.apply_color_grade.assert_not_called()


class TestCleanup:
    """临时文件清理测试。"""

    def test_cleanup_removes_directory(self, tmp_path):
        test_dir = tmp_path / "test_cleanup"
        test_dir.mkdir()
        (test_dir / "frame_000001.png").write_bytes(b"fake")

        ExportFinalCD._cleanup(test_dir)
        assert not test_dir.exists()

    def test_cleanup_nonexistent_path(self, tmp_path):
        # 不应抛异常
        ExportFinalCD._cleanup(tmp_path / "nonexistent")
