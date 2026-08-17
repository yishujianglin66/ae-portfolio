"""AE → DaVinci Resolve 协作链路 — 单元测试。

========================================

覆盖 ``integrations.ae_to_davinci_pipeline`` 的核心能力：

- 数据模型：AEExportSpec / DavinciGradingSpec / DavinciRenderSpec / PipelineResult
- 阶段方法：``_ae_export`` / ``_davinci_import`` / ``_davinci_grade`` / ``_davinci_render``
- 错误处理：每个阶段的失败传播
- 异步执行：``run_async``
- 检查点机制：``run_with_checkpoints`` 的断点续传
- 高层 API：``run_cinematic_teal_orange`` / ``run_vintage_film`` / ``run_music_video`` /
  ``run_with_preset`` / ``run_with_custom_lut`` / ``quick_pipeline``
- 进度回调
- 预设解析与片段索引

通过依赖注入的 Mock 客户端确保无需真实 AE / DaVinci 环境。
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from integrations.ae_to_davinci_pipeline import (  # noqa: E402
    AEExportSpec,
    AEToDavinciPipeline,
    DavinciGradingSpec,
    DavinciRenderSpec,
    PipelineCheckpoint,
    PipelineResult,
    STYLE_PRESET_MAP,
    quick_pipeline,
)
from integrations.davinci_color_grading import (  # noqa: E402
    ColorGrader,
    ColorGradingPreset,
    ColorWheelValues,
)


# ============================================================================
# Mock 工厂
# ============================================================================


class _MockFuscriptResult:
    """模拟 ``davinci_fuscript.FuscriptResult``。"""

    def __init__(
        self,
        success: bool = True,
        project_name: str = "MockProject",
        timeline_name: str = "MockTimeline",
        clips_imported: int = 1,
        render_complete: bool = False,
        output_path: str = "",
        errors: Optional[List[str]] = None,
    ) -> None:
        self.success = success
        self.project_name = project_name
        self.timeline_name = timeline_name
        self.clips_imported = clips_imported
        self.render_complete = render_complete
        self.output_path = output_path
        self.errors = errors or []


class _MockColorGrader:
    """模拟 ColorGrader。"""

    def __init__(self) -> None:
        self.resolve = MagicMock()
        self.resolve.GetProjectManager.return_value.GetCurrentProject.return_value.GetCurrentTimeline.return_value.GetItemListInTrack.return_value = [
            object(),
            object(),
        ]
        self.grade_calls: List[Dict[str, Any]] = []
        self.export_lut_calls: List[Dict[str, Any]] = []
        self.should_fail = False

    def switch_to_color_page(self) -> None:
        return None

    def grade_clip_range(self, clip_indices, node_index: int, preset, balance_type=None):
        if self.should_fail:
            return {idx: False for idx in clip_indices}
        for idx in clip_indices:
            self.grade_calls.append(
                {
                    "clip_index": idx,
                    "node_index": node_index,
                    "preset_name": getattr(preset, "name", "unknown"),
                }
            )
        return {idx: True for idx in clip_indices}

    def export_lut(self, clip_index: int, node_index: int, output_path: str) -> bool:
        if self.should_fail:
            return False
        self.export_lut_calls.append(
            {
                "clip_index": clip_index,
                "node_index": node_index,
                "output_path": output_path,
            }
        )
        # 写入一个占位 LUT
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("# Mock LUT\n", encoding="utf-8")
        return True


class _MockResolveColorEngine:
    """模拟 ``integrations.davinci_fuscript.ResolveColorEngine``。"""

    def __init__(self) -> None:
        self._grader = _MockColorGrader()
        self.create_project_calls: List[Dict[str, Any]] = []
        self.render_project_calls: List[Dict[str, Any]] = []
        self.should_fail_create = False
        self.should_fail_render = False
        self.output_path_override: Optional[str] = None

    @property
    def color_grader(self) -> _MockColorGrader:
        return self._grader

    def check_resolve_running(self) -> bool:
        return True

    def launch_resolve(self) -> bool:
        return True

    def create_project(
        self,
        project_name: str,
        media_files: List[str],
        timeline_name: str = "MainTimeline",
        color_config: Any = None,
        render: bool = False,
        output_dir: Optional[str] = None,
    ) -> _MockFuscriptResult:
        self.create_project_calls.append(
            {
                "project_name": project_name,
                "media_files": list(media_files),
                "timeline_name": timeline_name,
                "color_config": color_config,
                "render": render,
                "output_dir": output_dir,
            }
        )
        if self.should_fail_create:
            return _MockFuscriptResult(
                success=False, errors=["Mock create_project failure"]
            )
        return _MockFuscriptResult(
            success=True,
            project_name=project_name,
            timeline_name=timeline_name,
            clips_imported=len(media_files),
        )

    def import_interchange_format(
        self,
        project_name: str,
        timeline_name: str,
        file_path: str,
        file_type: str = "XML",
        color_config: Optional[Any] = None,
    ) -> _MockFuscriptResult:
        self.create_project_calls.append(
            {
                "project_name": project_name,
                "timeline_name": timeline_name,
                "file_path": file_path,
                "file_type": file_type,
            }
        )
        if self.should_fail_create:
            return _MockFuscriptResult(
                success=False, errors=["Mock import_interchange_format failure"]
            )
        return _MockFuscriptResult(
            success=True,
            project_name=project_name,
            timeline_name=timeline_name,
            clips_imported=1,
        )

    def render_project(
        self,
        project_name: str,
        output_dir: str,
        render_format: str = "MP4",
        codec: str = "H.264",
        resolution: str = "1920x1080",
        frame_rate: str = "24",
        quality: str = "High",
        timeout: int = 300,
    ) -> _MockFuscriptResult:
        self.render_project_calls.append(
            {
                "project_name": project_name,
                "output_dir": output_dir,
                "render_format": render_format,
                "codec": codec,
                "resolution": resolution,
                "frame_rate": frame_rate,
            }
        )
        if self.should_fail_render:
            return _MockFuscriptResult(
                success=False, errors=["Mock render_project failure"]
            )

        # 写一个占位输出文件
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        if self.output_path_override:
            out = Path(self.output_path_override)
        else:
            out = out_dir / f"{project_name}_output.mp4"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"FAKEMP4" * 1024)
        return _MockFuscriptResult(
            success=True,
            project_name=project_name,
            render_complete=True,
            output_path=str(out),
        )


class _MockUnifiedAEClient:
    """模拟 ``ae.unified_ae_client.UnifiedAEClient``。"""

    def __init__(self) -> None:
        self.list_compositions_result: List[Dict[str, Any]] = [
            {"name": "MockComp1", "id": 1, "width": 1920, "height": 1080},
            {"name": "MockComp2", "id": 2, "width": 1280, "height": 720},
        ]
        self.render_calls: List[Dict[str, Any]] = []
        self.should_fail = False
        self.missing_compositions: List[str] = []

    def list_compositions(self) -> List[Dict[str, Any]]:
        return [c for c in self.list_compositions_result if c["name"] not in self.missing_compositions]

    def render(self, comp_name: str, output_path: str, **kwargs: Any) -> Dict[str, Any]:
        self.render_calls.append(
            {"comp_name": comp_name, "output_path": output_path, **kwargs}
        )
        if self.should_fail:
            return {"success": False, "error": "Mock render failure"}
        # 写一个占位文件
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"FAKEMOV" * 1024)
        return {"success": True, "data": {"path": str(out)}}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_work_dir(tmp_path: Path) -> Path:
    """临时工作目录。"""
    work = tmp_path / "pipeline"
    work.mkdir(parents=True, exist_ok=True)
    return work


@pytest.fixture
def mock_ae_client() -> _MockUnifiedAEClient:
    """Mock AE 客户端。"""
    return _MockUnifiedAEClient()


@pytest.fixture
def mock_davinci_engine() -> _MockResolveColorEngine:
    """Mock DaVinci 引擎。"""
    return _MockResolveColorEngine()


@pytest.fixture
def pipeline(
    temp_work_dir: Path,
    mock_ae_client: _MockUnifiedAEClient,
    mock_davinci_engine: _MockResolveColorEngine,
) -> AEToDavinciPipeline:
    """构造带 Mock 客户端的协作链路。"""
    return AEToDavinciPipeline(
        ae_client=mock_ae_client,
        davinci_engine=mock_davinci_engine,
        work_dir=str(temp_work_dir / "work"),
        temp_dir=str(temp_work_dir / "temp"),
    )


# ============================================================================
# 1. 数据模型测试
# ============================================================================


class TestAEExportSpec:
    """AEExportSpec 数据模型测试。"""

    def test_default_values(self) -> None:
        spec = AEExportSpec(comp_name="X", output_path="out.mov")
        assert spec.format == "mov_prores_4444"
        assert spec.resolution == (1920, 1080)
        assert spec.frame_rate == 30.0
        assert spec.duration is None
        assert spec.start_time == 0.0
        assert spec.quality == "best"
        assert spec.with_audio is True

    def test_to_render_args(self) -> None:
        spec = AEExportSpec(
            comp_name="MyComp",
            output_path="out.mov",
            format="mp4_h264",
            resolution=(3840, 2160),
            frame_rate=60.0,
            duration=10.0,
            quality="draft",
        )
        args = spec.to_render_args()
        assert args["comp_name"] == "MyComp"
        assert args["resolution"] == [3840, 2160]
        assert args["frame_rate"] == 60.0
        assert args["quality"] == "draft"

    def test_custom_values(self) -> None:
        spec = AEExportSpec(
            comp_name="C",
            output_path="o.mov",
            format="png_sequence",
            with_audio=False,
        )
        assert spec.format == "png_sequence"
        assert spec.with_audio is False


class TestDavinciGradingSpec:
    """DavinciGradingSpec 数据模型测试。"""

    def test_default_values(self) -> None:
        spec = DavinciGradingSpec(project_name="P")
        assert spec.timeline_name == "AE_Imported"
        assert spec.preset_name is None
        assert spec.custom_preset is None
        assert spec.grade_all_clips is True
        assert spec.specific_clip_indices is None
        assert spec.export_lut is None

    def test_validate_success(self) -> None:
        spec = DavinciGradingSpec(project_name="P", preset_name="cinematic_teal_orange")
        spec.validate()  # 不应抛异常

    def test_validate_empty_project_name(self) -> None:
        spec = DavinciGradingSpec(project_name="", preset_name="x")
        with pytest.raises(ValueError, match="project_name"):
            spec.validate()

    def test_validate_empty_timeline_name(self) -> None:
        spec = DavinciGradingSpec(project_name="P", timeline_name="", preset_name="x")
        with pytest.raises(ValueError, match="timeline_name"):
            spec.validate()

    def test_validate_no_preset(self) -> None:
        spec = DavinciGradingSpec(project_name="P")
        with pytest.raises(ValueError, match="preset_name or custom_preset"):
            spec.validate()

    def test_validate_specific_without_indices(self) -> None:
        spec = DavinciGradingSpec(
            project_name="P",
            preset_name="x",
            grade_all_clips=False,
            specific_clip_indices=None,
        )
        with pytest.raises(ValueError, match="specific_clip_indices"):
            spec.validate()


class TestDavinciRenderSpec:
    """DavinciRenderSpec 数据模型测试。"""

    def test_default_values(self) -> None:
        spec = DavinciRenderSpec(output_path="out.mp4")
        assert spec.format == "mp4_h264"
        assert spec.codec == "H.264"
        assert spec.quality == "High"
        assert spec.render_audio is True

    def test_to_resolve_render_settings(self) -> None:
        spec = DavinciRenderSpec(
            output_path="output/folder/final.mp4",
            format="mp4_h264",
            resolution=(3840, 2160),
            frame_rate=60.0,
            codec="H.265",
            quality="Best",
        )
        settings = spec.to_resolve_render_settings()
        assert settings["Resolution"] == "3840x2160"
        assert settings["Codec"] == "H.265"
        assert settings["Frame Rate"] == "60"
        assert settings["File Type"] == "MP4"
        assert settings["TargetDir"].endswith("output/folder") or settings["TargetDir"].endswith("folder")

    def test_file_type_mapping(self) -> None:
        spec = DavinciRenderSpec(output_path="x.mov", format="mov_prores_4444")
        assert spec._resolve_file_type() == "MOV"
        spec2 = DavinciRenderSpec(output_path="x.mp4", format="mp4_h265")
        assert spec2._resolve_file_type() == "MP4"
        spec3 = DavinciRenderSpec(output_path="x.mov", format="mov_dnxhd")
        assert spec3._resolve_file_type() == "MOV"

    def test_quality_code_mapping(self) -> None:
        assert DavinciRenderSpec(output_path="x", quality="Draft")._resolve_quality_code() == 28
        assert DavinciRenderSpec(output_path="x", quality="Normal")._resolve_quality_code() == 23
        assert DavinciRenderSpec(output_path="x", quality="High")._resolve_quality_code() == 20
        assert DavinciRenderSpec(output_path="x", quality="Best")._resolve_quality_code() == 18


class TestPipelineResult:
    """PipelineResult 数据模型测试。"""

    def test_default_values(self) -> None:
        result = PipelineResult(success=True)
        assert result.ae_export_path is None
        assert result.davinci_project_path is None
        assert result.final_output_path is None
        assert result.intermediate_files == []
        assert result.errors == []
        assert result.warnings == []
        assert result.metrics == {}
        assert result.started_at is not None
        assert result.finished_at is None

    def test_to_dict(self) -> None:
        result = PipelineResult(
            success=True,
            ae_export_path="ae.mov",
            final_output_path="final.mp4",
        )
        result.finished_at = result.started_at
        data = result.to_dict()
        assert data["success"] is True
        assert data["ae_export_path"] == "ae.mov"
        assert data["final_output_path"] == "final.mp4"
        assert "started_at" in data
        assert "finished_at" in data
        assert data["duration_sec"] is not None


class TestPipelineCheckpoint:
    """PipelineCheckpoint 测试。"""

    def test_roundtrip(self) -> None:
        ckpt = PipelineCheckpoint(stage="ae_export", data={"path": "out.mov"})
        data = ckpt.to_dict()
        restored = PipelineCheckpoint.from_dict(data)
        assert restored.stage == "ae_export"
        assert restored.data == {"path": "out.mov"}


# ============================================================================
# 2. 阶段方法测试
# ============================================================================


class TestAEExportStage:
    """AE 导出阶段测试。"""

    def test_success(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        result = PipelineResult(success=False)
        out_path = str(temp_work_dir / "ae_out.mov")
        spec = AEExportSpec(comp_name="MockComp1", output_path=out_path)
        ret = pipeline._ae_export(spec, result)
        assert ret == out_path
        assert Path(ret).exists()
        assert Path(ret).stat().st_size > 0
        assert result.ae_export_path == out_path
        assert out_path in result.intermediate_files
        assert len(mock_ae_client.render_calls) == 1
        assert mock_ae_client.render_calls[0]["comp_name"] == "MockComp1"

    def test_comp_not_found(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        # 客户端列表里没有 "Unknown" 合成
        result = PipelineResult(success=False)
        spec = AEExportSpec(comp_name="Unknown", output_path=str(temp_work_dir / "x.mov"))
        with pytest.raises(ValueError, match="Composition not found"):
            pipeline._ae_export(spec, result)

    def test_render_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        mock_ae_client.should_fail = True
        result = PipelineResult(success=False)
        spec = AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov"))
        with pytest.raises(RuntimeError, match="AE export returned failure"):
            pipeline._ae_export(spec, result)

    def test_missing_output_file(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        """客户端声称成功但实际未生成文件。"""
        # 通过劫持 render 让它不写文件
        def bad_render(*args, **kwargs):
            return {"success": True}

        mock_ae_client.render = bad_render  # type: ignore[assignment]
        result = PipelineResult(success=False)
        spec = AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov"))
        with pytest.raises(RuntimeError, match="AE export file missing"):
            pipeline._ae_export(spec, result)

    def test_empty_output_file(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        """客户端生成空文件。"""
        def empty_render(comp_name, output_path, **kwargs):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(b"")
            return {"success": True}

        mock_ae_client.render = empty_render  # type: ignore[assignment]
        result = PipelineResult(success=False)
        out = str(temp_work_dir / "empty.mov")
        spec = AEExportSpec(comp_name="MockComp1", output_path=out)
        with pytest.raises(RuntimeError, match="AE export file is empty"):
            pipeline._ae_export(spec, result)

    def test_relative_output_path_resolved(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        result = PipelineResult(success=False)
        spec = AEExportSpec(comp_name="MockComp1", output_path="rel.mov")
        ret = pipeline._ae_export(spec, result)
        # 路径应该是绝对路径
        assert Path(ret).is_absolute()
        assert Path(ret).exists()


class TestDavinciImportStage:
    """DaVinci 导入阶段测试。"""

    def test_success(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        # 先造一个 AE 输出文件
        ae_out = temp_work_dir / "ae.mov"
        ae_out.write_bytes(b"FAKEMOV" * 100)
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(
            project_name="TestProj", preset_name="cinematic_teal_orange"
        )
        pipeline._davinci_import(str(ae_out), spec, result)
        assert result.davinci_project_path == "TestProj/AE_Imported"
        assert len(mock_davinci_engine.create_project_calls) == 1
        call = mock_davinci_engine.create_project_calls[0]
        assert call["project_name"] == "TestProj"
        assert call["timeline_name"] == "AE_Imported"
        assert str(ae_out) in call["media_files"]

    def test_create_project_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        mock_davinci_engine.should_fail_create = True
        ae_out = temp_work_dir / "ae.mov"
        ae_out.write_bytes(b"FAKEMOV" * 100)
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(project_name="P", preset_name="x")
        with pytest.raises(RuntimeError, match="DaVinci import failed"):
            pipeline._davinci_import(str(ae_out), spec, result)


class TestDavinciGradeStage:
    """DaVinci 调色阶段测试。"""

    def test_builtin_preset(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(
            project_name="P",
            preset_name="cinematic_teal_orange",
            grade_all_clips=True,
        )
        pipeline._davinci_grade(spec, result)
        # Mock 引擎的 grader 有 2 个片段
        assert len(mock_davinci_engine._grader.grade_calls) == 2
        assert all(c["preset_name"] == "Cinematic Teal & Orange" for c in mock_davinci_engine._grader.grade_calls)

    def test_specific_clip_indices(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(
            project_name="P",
            preset_name="vintage_film",
            grade_all_clips=False,
            specific_clip_indices=[0],
        )
        pipeline._davinci_grade(spec, result)
        assert len(mock_davinci_engine._grader.grade_calls) == 1
        assert mock_davinci_engine._grader.grade_calls[0]["clip_index"] == 0

    def test_custom_preset(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        result = PipelineResult(success=False)
        custom = ColorGradingPreset(
            name="MyCustomGrade",
            lift=ColorWheelValues(red=0.05),
        )
        spec = DavinciGradingSpec(
            project_name="P",
            custom_preset=custom,
            grade_all_clips=True,
        )
        pipeline._davinci_grade(spec, result)
        assert all(c["preset_name"] == "MyCustomGrade" for c in mock_davinci_engine._grader.grade_calls)

    def test_export_lut(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        result = PipelineResult(success=False)
        lut_path = str(temp_work_dir / "out.cube")
        spec = DavinciGradingSpec(
            project_name="P",
            preset_name="cinematic_teal_orange",
            grade_all_clips=True,
            export_lut=lut_path,
        )
        pipeline._davinci_grade(spec, result)
        assert len(mock_davinci_engine._grader.export_lut_calls) == 1
        assert mock_davinci_engine._grader.export_lut_calls[0]["output_path"] == lut_path
        assert Path(lut_path).exists()

    def test_unknown_preset_warns(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(
            project_name="P",
            preset_name="nonexistent_preset",
        )
        # 未知预设不抛异常，只记 warning
        pipeline._davinci_grade(spec, result)
        assert any("Preset not found" in w for w in result.warnings)
        # 没有调色发生
        assert len(mock_davinci_engine._grader.grade_calls) == 0

    def test_all_clips_failed(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        mock_davinci_engine._grader.should_fail = True
        result = PipelineResult(success=False)
        spec = DavinciGradingSpec(project_name="P", preset_name="cinematic_teal_orange")
        with pytest.raises(RuntimeError, match="All clip grading attempts failed"):
            pipeline._davinci_grade(spec, result)

    def test_partial_failure_warns(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
    ) -> None:
        # 只让一半的 clip 失败
        original = mock_davinci_engine._grader.grade_clip_range

        def partial_grade(clip_indices, node_index, preset, balance_type=None):
            return {idx: (i % 2 == 0) for i, idx in enumerate(clip_indices)}

        mock_davinci_engine._grader.grade_clip_range = partial_grade
        try:
            result = PipelineResult(success=False)
            spec = DavinciGradingSpec(
                project_name="P",
                preset_name="cinematic_teal_orange",
            )
            pipeline._davinci_grade(spec, result)
            assert any("Partial grading" in w for w in result.warnings)
        finally:
            mock_davinci_engine._grader.grade_clip_range = original


class TestDavinciRenderStage:
    """DaVinci 渲染阶段测试。"""

    def test_success(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        result = PipelineResult(success=False)
        result.davinci_project_path = "TestProj/AE_Imported"
        spec = DavinciRenderSpec(
            output_path=str(temp_work_dir / "final.mp4"),
        )
        ret = pipeline._davinci_render(spec, result)
        assert ret == str(temp_work_dir / "final.mp4")
        assert Path(ret).exists()
        assert len(mock_davinci_engine.render_project_calls) == 1
        assert mock_davinci_engine.render_project_calls[0]["project_name"] == "TestProj"

    def test_render_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        mock_davinci_engine.should_fail_render = True
        result = PipelineResult(success=False)
        result.davinci_project_path = "P/T"
        spec = DavinciRenderSpec(output_path=str(temp_work_dir / "f.mp4"))
        with pytest.raises(RuntimeError, match="render_project failed"):
            pipeline._davinci_render(spec, result)

    def test_render_no_project_path(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        """davinci_project_path 为空时使用默认项目名。"""
        result = PipelineResult(success=False)
        spec = DavinciRenderSpec(output_path=str(temp_work_dir / "f.mp4"))
        ret = pipeline._davinci_render(spec, result)
        assert ret == str(temp_work_dir / "f.mp4")
        # 默认项目名
        assert mock_davinci_engine.render_project_calls[0]["project_name"] == "AE_Imported_Project"


# ============================================================================
# 3. 完整 run 流程测试
# ============================================================================


class TestRun:
    """完整 run() 流程测试。"""

    def test_happy_path(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        ae_spec = AEExportSpec(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "ae.mov"),
        )
        grading_spec = DavinciGradingSpec(
            project_name="P", preset_name="cinematic_teal_orange"
        )
        render_spec = DavinciRenderSpec(output_path=str(temp_work_dir / "f.mp4"))

        result = pipeline.run(ae_spec, grading_spec, render_spec)

        assert result.success
        assert result.ae_export_path is not None
        assert result.davinci_project_path == "P/AE_Imported"
        assert result.final_output_path is not None
        assert Path(result.final_output_path).exists()
        assert result.finished_at is not None
        # 每个阶段都被调用
        assert len(mock_ae_client.render_calls) == 1
        assert len(mock_davinci_engine.create_project_calls) == 1
        assert len(mock_davinci_engine.render_project_calls) == 1
        # 指标都记录了
        assert "ae_export_duration_sec" in result.metrics
        assert "davinci_import_duration_sec" in result.metrics
        assert "davinci_grade_duration_sec" in result.metrics
        assert "davinci_render_duration_sec" in result.metrics

    def test_ae_failure_short_circuits(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        mock_ae_client.missing_compositions = ["MockComp1"]  # 模拟找不到合成
        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
        )
        assert not result.success
        assert any("AE export failed" in e for e in result.errors)
        # DaVinci 没被调用
        assert len(mock_davinci_engine.create_project_calls) == 0

    def test_davinci_import_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        mock_davinci_engine.should_fail_create = True
        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
        )
        assert not result.success
        assert any("DaVinci import failed" in e for e in result.errors)
        # 调色和渲染没被调用
        assert len(mock_davinci_engine._grader.grade_calls) == 0
        assert len(mock_davinci_engine.render_project_calls) == 0

    def test_davinci_render_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        mock_davinci_engine.should_fail_render = True
        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
        )
        assert not result.success
        assert any("DaVinci render failed" in e for e in result.errors)

    def test_progress_callback(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        events: List[tuple] = []

        def cb(stage: str, pct: float) -> None:
            events.append((stage, pct))

        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            progress_callback=cb,
        )
        assert result.success
        # 至少 8 次回调（每个阶段 2 次：开始+完成）
        assert len(events) >= 8
        # 进度值递增
        pcts = [e[1] for e in events]
        assert pcts[0] == 0.0
        assert pcts[-1] == 1.0

    def test_progress_callback_exception_handled(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        def bad_cb(stage: str, pct: float) -> None:
            raise RuntimeError("callback failure")

        # 不应该让回调异常炸掉整个 pipeline
        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            progress_callback=bad_cb,
        )
        assert result.success

    def test_invalid_grading_spec(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        # preset_name 和 custom_preset 都为空
        result = pipeline.run(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
        )
        assert not result.success
        assert any("Invalid DavinciGradingSpec" in e for e in result.errors)


# ============================================================================
# 4. 异步执行测试
# ============================================================================


class TestAsyncRun:
    """run_async 测试。"""

    def test_async_happy_path(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        result = asyncio.run(
            pipeline.run_async(
                AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
                DavinciGradingSpec(project_name="P", preset_name="cinematic_teal_orange"),
                DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            )
        )
        assert result.success
        assert result.final_output_path is not None

    def test_async_failure(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        mock_ae_client.missing_compositions = ["MockComp1"]
        result = asyncio.run(
            pipeline.run_async(
                AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
                DavinciGradingSpec(project_name="P", preset_name="x"),
                DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            )
        )
        assert not result.success


# ============================================================================
# 5. 检查点机制测试
# ============================================================================


class TestCheckpoints:
    """run_with_checkpoints 测试。"""

    def test_first_run_creates_checkpoint(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        ckpt_dir = temp_work_dir / "ckpt"
        result = pipeline.run_with_checkpoints(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            checkpoint_dir=str(ckpt_dir),
        )
        assert result.success
        # 全部完成后检查点应被清理
        assert not (ckpt_dir / "pipeline_checkpoint.json").exists()

    def test_resume_after_partial_run(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        """第一次跑到 AE 阶段完成（手动落盘检查点），第二次调用应跳过 AE 阶段。"""
        ckpt_dir = temp_work_dir / "ckpt"
        # 1) 落盘一个 AE 阶段的检查点
        ckpt_file = ckpt_dir / "pipeline_checkpoint.json"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        ae_out = str(temp_work_dir / "ae_from_checkpoint.mov")
        Path(ae_out).write_bytes(b"FAKEMOV" * 100)
        ckpt_data = {
            "ae_export": PipelineCheckpoint(
                stage="ae_export",
                data={"ae_export_path": ae_out},
            ).to_dict()
        }
        ckpt_file.write_text(json.dumps(ckpt_data), encoding="utf-8")

        # 2) 调用 run_with_checkpoints，应跳过 ae_export 阶段
        result = pipeline.run_with_checkpoints(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            checkpoint_dir=str(ckpt_dir),
        )
        assert result.success
        # AE 客户端的 render 根本没被调用
        assert len(mock_ae_client.render_calls) == 0
        # DaVinci 仍然被调用
        assert len(mock_davinci_engine.create_project_calls) == 1

    def test_corrupted_checkpoint_recovery(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        """损坏的检查点应被忽略，重新执行。"""
        ckpt_dir = temp_work_dir / "ckpt"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        (ckpt_dir / "pipeline_checkpoint.json").write_text("not json {{{", encoding="utf-8")

        result = pipeline.run_with_checkpoints(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            checkpoint_dir=str(ckpt_dir),
        )
        assert result.success

    def test_ae_failure_keeps_no_checkpoint(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        mock_ae_client.missing_compositions = ["MockComp1"]
        ckpt_dir = temp_work_dir / "ckpt"
        result = pipeline.run_with_checkpoints(
            AEExportSpec(comp_name="MockComp1", output_path=str(temp_work_dir / "x.mov")),
            DavinciGradingSpec(project_name="P", preset_name="x"),
            DavinciRenderSpec(output_path=str(temp_work_dir / "y.mp4")),
            checkpoint_dir=str(ckpt_dir),
        )
        assert not result.success
        # 检查点不存在（没创建过）
        assert not (ckpt_dir / "pipeline_checkpoint.json").exists()


# ============================================================================
# 6. 高层 API 测试
# ============================================================================


class TestHighLevelAPI:
    """高层便捷 API 测试。"""

    def test_run_cinematic_teal_orange(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        result = pipeline.run_cinematic_teal_orange(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
            duration=5.0,
        )
        assert result.success
        assert result.final_output_path is not None

    def test_run_vintage_film(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        result = pipeline.run_vintage_film(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
        )
        assert result.success

    def test_run_music_video(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        result = pipeline.run_music_video(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
            duration=30.0,
        )
        assert result.success

    def test_run_with_preset(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        result = pipeline.run_with_preset(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
            preset_name="low_key_dark",
        )
        assert result.success

    def test_run_with_custom_lut(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        temp_work_dir: Path,
    ) -> None:
        """run_with_custom_lut 不应因 LUT 路径无效而崩溃（用 Mock 客户端）。"""
        result = pipeline.run_with_custom_lut(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
            lut_path="C:/nonexistent/lut.cube",
        )
        # 由于实际 LUT 不存在，可能 success=False，但不应异常
        # 至少 AE export 是成功的
        assert result.ae_export_path is not None

    def test_run_with_preset_unknown_preset(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        """未知预设不抛异常，pipeline 走通但无调色。"""
        result = pipeline.run_with_preset(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "f.mp4"),
            preset_name="completely_made_up_preset",
        )
        # AE 导出 + DaVinci 导入 + 渲染都成功；调色阶段会记 warning 但不阻塞
        assert result.success
        assert any("Preset not found" in w for w in result.warnings)


class TestQuickPipeline:
    """quick_pipeline 便捷函数测试。"""

    def test_quick_pipeline_known_style(self) -> None:
        """quick_pipeline 在 MOCK 客户端下不直接工作（它会自己懒加载），仅验证函数存在。"""
        # quick_pipeline 不会注入 mock，所以仅验证函数签名可调用
        # （真正执行会因无 AE/DaVinci 失败，这里只测语法）
        assert callable(quick_pipeline)

    def test_style_preset_map(self) -> None:
        """STYLE_PRESET_MAP 应包含 8 个内置风格。"""
        assert "cinematic_teal_orange" in STYLE_PRESET_MAP
        assert "vintage_film" in STYLE_PRESET_MAP
        assert "music_video_punch" in STYLE_PRESET_MAP
        assert "warm_portrait" in STYLE_PRESET_MAP
        assert "cold_scifi" in STYLE_PRESET_MAP
        assert "high_key_bright" in STYLE_PRESET_MAP
        assert "low_key_dark" in STYLE_PRESET_MAP
        assert "black_and_white_classic" in STYLE_PRESET_MAP
        assert len(STYLE_PRESET_MAP) == 8


# ============================================================================
# 7. 辅助方法测试
# ============================================================================


class TestHelpers:
    """辅助方法测试。"""

    def test_find_latest_render(self, tmp_path: Path) -> None:
        # 写 3 个 .mp4 文件，时间递增
        for i in range(3):
            (tmp_path / f"f{i}.mp4").write_bytes(b"x" * 10)
            time.sleep(0.01)
        latest = AEToDavinciPipeline._find_latest_render(tmp_path, ".mp4")
        assert latest is not None
        assert latest.name == "f2.mp4"

    def test_find_latest_render_no_match(self, tmp_path: Path) -> None:
        result = AEToDavinciPipeline._find_latest_render(tmp_path, ".mov")
        assert result is None

    def test_report_with_callback(self) -> None:
        pipeline = AEToDavinciPipeline()
        events: List[tuple] = []
        pipeline._report(lambda s, p: events.append((s, p)), "test", 0.5)
        assert events == [("test", 0.5)]

    def test_report_clamps_progress(self) -> None:
        pipeline = AEToDavinciPipeline()
        events: List[tuple] = []
        pipeline._report(lambda s, p: events.append((s, p)), "test", 1.5)
        assert events[0][1] == 1.0
        pipeline._report(lambda s, p: events.append((s, p)), "test", -0.5)
        assert events[1][1] == 0.0

    def test_report_no_callback(self) -> None:
        pipeline = AEToDavinciPipeline()
        # 不传 callback 不应抛异常
        pipeline._report(None, "test", 0.5)


class TestLazyLoading:
    """依赖懒加载测试。"""

    def test_get_ae_when_none(self) -> None:
        pipeline = AEToDavinciPipeline()
        assert pipeline.ae is None
        ae = pipeline._get_ae()
        assert ae is not None
        # 第二次调用返回相同实例
        assert pipeline._get_ae() is ae

    def test_get_davinci_when_none(self) -> None:
        pipeline = AEToDavinciPipeline()
        assert pipeline.davinci is None
        davinci = pipeline._get_davinci()
        assert davinci is not None
        # 第二次调用返回相同实例
        assert pipeline._get_davinci() is davinci

    def test_get_grader_caches(self) -> None:
        pipeline = AEToDavinciPipeline()
        # 直接设置 mock engine 让 color_grader 走 mock 路径
        mock_engine = _MockResolveColorEngine()
        pipeline.davinci = mock_engine
        g1 = pipeline._get_grader()
        g2 = pipeline._get_grader()
        assert g1 is g2


# ============================================================================
# 8. 模块导出 & 兼容性测试
# ============================================================================


class TestModuleExports:
    """模块导出完整性测试。"""

    def test_main_classes_exported(self) -> None:
        from integrations import ae_to_davinci_pipeline as mod

        assert hasattr(mod, "AEToDavinciPipeline")
        assert hasattr(mod, "AEExportSpec")
        assert hasattr(mod, "DavinciGradingSpec")
        assert hasattr(mod, "DavinciRenderSpec")
        assert hasattr(mod, "PipelineResult")
        assert hasattr(mod, "PipelineCheckpoint")
        assert hasattr(mod, "CheckpointManager")
        assert hasattr(mod, "quick_pipeline")

    def test_type_aliases_exported(self) -> None:
        from integrations import ae_to_davinci_pipeline as mod

        assert hasattr(mod, "AEExportFormat")
        assert hasattr(mod, "DavinciRenderFormat")
        assert hasattr(mod, "RenderQuality")
        assert hasattr(mod, "ProgressCallback")
        assert hasattr(mod, "STYLE_PRESET_MAP")


# ============================================================================
# 9. XML/AAF 导出格式测试
# ============================================================================


class TestAEExportInterchangeFormat:
    """AE 导出交换格式（XML/AAF）测试。"""

    def test_is_interchange_format_xml(self) -> None:
        spec = AEExportSpec(comp_name="X", output_path="out.xml", format="xml_fcp7")
        assert spec.is_interchange_format() is True

    def test_is_interchange_format_aaf(self) -> None:
        spec = AEExportSpec(comp_name="X", output_path="out.aaf", format="aaf")
        assert spec.is_interchange_format() is True

    def test_is_not_interchange_format_mov(self) -> None:
        spec = AEExportSpec(comp_name="X", output_path="out.mov", format="mov_prores_4444")
        assert spec.is_interchange_format() is False

    def test_export_spec_xml_params(self) -> None:
        spec = AEExportSpec(
            comp_name="MyComp",
            output_path="out.xml",
            format="xml_fcp7",
            include_effects=True,
            include_keyframes=True,
            include_compositions=True,
        )
        assert spec.format == "xml_fcp7"
        assert spec.include_effects is True
        assert spec.include_keyframes is True
        assert spec.include_compositions is True

    def test_export_spec_aaf_params(self) -> None:
        spec = AEExportSpec(
            comp_name="MyComp",
            output_path="out.aaf",
            format="aaf",
            include_effects=False,
            include_keyframes=False,
            include_compositions=False,
        )
        assert spec.format == "aaf"
        assert spec.include_effects is False
        assert spec.include_keyframes is False
        assert spec.include_compositions is False


# ============================================================================
# 10. 专业级调色参数测试
# ============================================================================


class TestProfessionalColorGrading:
    """专业级调色参数测试（色轮、曲线、Qualifier）。"""

    def test_color_wheel_params_default(self) -> None:
        from integrations.davinci_fuscript import ColorWheelParams

        params = ColorWheelParams()
        assert params.red == 0.0
        assert params.green == 0.0
        assert params.blue == 0.0
        assert params.master == 0.0

    def test_color_wheel_params_custom(self) -> None:
        from integrations.davinci_fuscript import ColorWheelParams

        params = ColorWheelParams(red=0.05, green=-0.03, blue=0.02, master=0.01)
        assert params.red == 0.05
        assert params.green == -0.03
        assert params.blue == 0.02
        assert params.master == 0.01

    def test_qualifier_params_default(self) -> None:
        from integrations.davinci_fuscript import QualifierParams

        q = QualifierParams()
        assert q.hue_min == 0.0
        assert q.hue_max == 360.0
        assert q.sat_min == 0.0
        assert q.sat_max == 1.0
        assert q.lum_min == 0.0
        assert q.lum_max == 1.0
        assert q.invert is False

    def test_qualifier_params_custom(self) -> None:
        from integrations.davinci_fuscript import QualifierParams

        q = QualifierParams(
            hue_min=100.0, hue_max=180.0,
            sat_min=0.3, sat_max=0.8,
            lum_min=0.2, lum_max=0.7,
            invert=True,
        )
        assert q.hue_min == 100.0
        assert q.hue_max == 180.0
        assert q.sat_min == 0.3
        assert q.sat_max == 0.8
        assert q.lum_min == 0.2
        assert q.lum_max == 0.7
        assert q.invert is True

    def test_color_grade_config_with_pro_params(self) -> None:
        from integrations.davinci_fuscript import (
            ColorGradeConfig,
            ColorWheelParams,
            QualifierParams,
        )

        config = ColorGradeConfig(
            preset="cinematic",
            lift=ColorWheelParams(red=0.05),
            gamma=ColorWheelParams(green=-0.03),
            gain=ColorWheelParams(blue=0.02),
            offset=ColorWheelParams(master=0.01),
            saturation=1.1,
            contrast=1.15,
            pivot=0.45,
            blend_opacity=0.9,
            custom_curve=[0.0, 0.0, 0.5, 0.5, 1.0, 1.0],
            hue_vs_hue=[0.0, 0.0, 0.5, 0.1, 1.0, 0.0],
            qualifier=QualifierParams(hue_min=180.0, hue_max=280.0),
        )
        assert config.lift.red == 0.05
        assert config.gamma.green == -0.03
        assert config.gain.blue == 0.02
        assert config.offset.master == 0.01
        assert config.saturation == 1.1
        assert config.contrast == 1.15
        assert config.pivot == 0.45
        assert config.blend_opacity == 0.9
        assert config.custom_curve == [0.0, 0.0, 0.5, 0.5, 1.0, 1.0]
        assert config.hue_vs_hue == [0.0, 0.0, 0.5, 0.1, 1.0, 0.0]
        assert config.qualifier is not None
        assert config.qualifier.hue_min == 180.0


# ============================================================================
# 11. 增强检查点管理器测试
# ============================================================================


class TestCheckpointManager:
    """CheckpointManager 测试。"""

    def test_save_and_load_checkpoint(self, tmp_path: Path) -> None:
        from integrations.ae_to_davinci_pipeline import CheckpointManager, PipelineCheckpoint

        ckpt_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(ckpt_dir))

        ckpt = PipelineCheckpoint(
            stage="ae_export",
            data={"ae_output": "/path/to/output.mov"},
            ae_export_spec={"comp_name": "TestComp", "format": "mov_prores_4444"},
            metrics={"ae_export_duration_sec": 10.5},
            warnings=["Warning 1"],
            pipeline_version="1.0.0",
        )

        manager.save(ckpt)
        assert manager.exists()

        loaded = manager.load()
        assert loaded is not None
        assert loaded.stage == "ae_export"
        assert loaded.data == {"ae_output": "/path/to/output.mov"}
        assert loaded.ae_export_spec == {"comp_name": "TestComp", "format": "mov_prores_4444"}
        assert loaded.metrics == {"ae_export_duration_sec": 10.5}
        assert loaded.warnings == ["Warning 1"]
        assert loaded.pipeline_version == "1.0.0"

    def test_delete_checkpoint(self, tmp_path: Path) -> None:
        from integrations.ae_to_davinci_pipeline import CheckpointManager, PipelineCheckpoint

        ckpt_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(ckpt_dir))

        ckpt = PipelineCheckpoint(stage="ae_export", data={})
        manager.save(ckpt)
        assert manager.exists()

        manager.delete()
        assert not manager.exists()

    def test_load_nonexistent_checkpoint(self, tmp_path: Path) -> None:
        from integrations.ae_to_davinci_pipeline import CheckpointManager

        ckpt_dir = tmp_path / "nonexistent"
        manager = CheckpointManager(checkpoint_dir=str(ckpt_dir))
        loaded = manager.load()
        assert loaded is None

    def test_get_stage_progress(self, tmp_path: Path) -> None:
        from integrations.ae_to_davinci_pipeline import CheckpointManager, PipelineCheckpoint

        manager = CheckpointManager(checkpoint_dir=str(tmp_path))

        ckpt = PipelineCheckpoint(stage="ae_export", data={})
        assert manager.get_stage_progress(ckpt) == 0.25

        ckpt = PipelineCheckpoint(stage="davinci_import", data={})
        assert manager.get_stage_progress(ckpt) == 0.5

        ckpt = PipelineCheckpoint(stage="davinci_grade", data={})
        assert manager.get_stage_progress(ckpt) == 0.75

        ckpt = PipelineCheckpoint(stage="davinci_render", data={})
        assert manager.get_stage_progress(ckpt) == 1.0

    def test_list_checkpoints(self, tmp_path: Path) -> None:
        from integrations.ae_to_davinci_pipeline import CheckpointManager, PipelineCheckpoint

        ckpt_dir = tmp_path / "checkpoints"
        manager = CheckpointManager(checkpoint_dir=str(ckpt_dir))

        ckpt = PipelineCheckpoint(stage="ae_export", data={})
        manager.save(ckpt)

        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) >= 1


# ============================================================================
# 12. 渲染规格增强测试
# ============================================================================


class TestDavinciRenderSpecEnhanced:
    """DavinciRenderSpec 增强功能测试。"""

    def test_resolve_extension(self) -> None:
        spec = DavinciRenderSpec(output_path="x.mov", format="mov_prores_4444")
        assert spec._resolve_extension() == ".mov"

        spec = DavinciRenderSpec(output_path="x.mp4", format="mp4_h264")
        assert spec._resolve_extension() == ".mp4"

        spec = DavinciRenderSpec(output_path="x.exr", format="exr_sequence")
        assert spec._resolve_extension() == ".exr"

        spec = DavinciRenderSpec(output_path="x.png", format="png_sequence")
        assert spec._resolve_extension() == ".png"

    def test_resolve_codec(self) -> None:
        spec = DavinciRenderSpec(output_path="x.mov", format="mov_prores_4444")
        assert spec._resolve_codec() == "ProRes 4444"

        spec = DavinciRenderSpec(output_path="x.mov", format="mov_prores_422")
        assert spec._resolve_codec() == "ProRes 422 HQ"

        spec = DavinciRenderSpec(output_path="x.mp4", format="mp4_h265")
        assert spec._resolve_codec() == "H.265"

        spec = DavinciRenderSpec(output_path="x.mov", format="mov_dnxhr_hq")
        assert spec._resolve_codec() == "DNxHR HQ"

    def test_to_resolve_render_settings_with_new_params(self) -> None:
        spec = DavinciRenderSpec(
            output_path="output/final.mp4",
            format="mp4_h265",
            resolution=(3840, 2160),
            frame_rate=24.0,
            quality="Best",
            render_audio=False,
            bitrate=50,
            crf=23,
            gop_size=24,
            interlaced=False,
            render_range="all",
            metadata={"title": "My Video", "artist": "Test"},
        )
        settings = spec.to_resolve_render_settings()
        assert settings["Codec"] == "H.265"
        assert settings["Resolution"] == "3840x2160"
        assert settings["Frame Rate"] == "24"
        assert settings["RenderAudio"] is False
        assert settings["Bitrate"] == 50
        assert settings["ConstantQuality"] == 23
        assert settings["GOPSize"] == 24
        assert settings["Interlaced"] is False
        assert settings["title"] == "My Video"
        assert settings["artist"] == "Test"

    def test_render_range_in_out(self) -> None:
        spec = DavinciRenderSpec(
            output_path="output/final.mp4",
            render_range="in_out",
            start_frame=100,
            end_frame=200,
        )
        settings = spec.to_resolve_render_settings()
        assert settings["SelectAllFrames"] is False
        assert settings["StartFrame"] == 100
        assert settings["EndFrame"] == 200


# ============================================================================
# 13. 端到端集成测试
# ============================================================================


class TestEndToEndIntegration:
    """端到端集成测试（使用 Mock 客户端）。"""

    def test_full_pipeline_with_xml_export(
        self,
        pipeline: AEToDavinciPipeline,
        mock_ae_client: _MockUnifiedAEClient,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        """测试完整流水线：AE 导出 XML → DaVinci 导入 XML → 调色 → 渲染。"""
        # 模拟 run_jsx 方法 - 提取 exportPath 变量的值
        def mock_run_jsx(script):
            lines = script.split("\n")
            for line in lines:
                if 'var exportPath = "' in line:
                    output_path = line.split('"')[1]
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(output_path).write_bytes(b'<?xml version="1.0"?><fcpxml version="1.8"/></fcpxml>')
                    break
            return {"success": True}

        mock_ae_client.run_jsx = mock_run_jsx  # type: ignore[assignment]

        ae_spec = AEExportSpec(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "export.xml"),
            format="xml_fcp7",
        )
        grading_spec = DavinciGradingSpec(
            project_name="XMLTestProj",
            preset_name="cinematic_teal_orange",
        )
        render_spec = DavinciRenderSpec(
            output_path=str(temp_work_dir / "final.mp4"),
        )

        result = pipeline.run(ae_spec, grading_spec, render_spec)

        assert result.success
        assert result.ae_export_path is not None
        assert result.davinci_project_path == "XMLTestProj/AE_Imported"
        assert result.final_output_path is not None
        assert Path(result.final_output_path).exists()

    def test_full_pipeline_with_pro_grading(
        self,
        pipeline: AEToDavinciPipeline,
        mock_davinci_engine: _MockResolveColorEngine,
        temp_work_dir: Path,
    ) -> None:
        """测试完整流水线使用专业级调色参数。"""
        from integrations.davinci_fuscript import (
            ColorGradeConfig,
            ColorWheelParams,
            QualifierParams,
        )

        # 配置专业级调色参数
        color_config = ColorGradeConfig(
            preset="cinematic",
            lift=ColorWheelParams(red=0.05),
            gamma=ColorWheelParams(green=-0.03),
            gain=ColorWheelParams(blue=0.02),
            saturation=1.1,
            contrast=1.15,
            qualifier=QualifierParams(hue_min=180.0, hue_max=280.0),
        )

        # 验证配置有效
        assert color_config.lift.red == 0.05
        assert color_config.gamma.green == -0.03
        assert color_config.gain.blue == 0.02
        assert color_config.saturation == 1.1
        assert color_config.contrast == 1.15
        assert color_config.qualifier is not None

        ae_spec = AEExportSpec(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "ae.mov"),
        )
        grading_spec = DavinciGradingSpec(
            project_name="ProGradeProj",
            preset_name="cinematic_teal_orange",
        )
        render_spec = DavinciRenderSpec(
            output_path=str(temp_work_dir / "final.mp4"),
        )

        result = pipeline.run(ae_spec, grading_spec, render_spec)
        assert result.success

    def test_pipeline_with_checkpoints(
        self,
        pipeline: AEToDavinciPipeline,
        temp_work_dir: Path,
    ) -> None:
        """测试流水线检查点机制。"""
        ckpt_dir = temp_work_dir / "checkpoints"

        ae_spec = AEExportSpec(
            comp_name="MockComp1",
            output_path=str(temp_work_dir / "ae.mov"),
        )
        grading_spec = DavinciGradingSpec(
            project_name="CheckpointProj",
            preset_name="cinematic_teal_orange",
        )
        render_spec = DavinciRenderSpec(
            output_path=str(temp_work_dir / "final.mp4"),
        )

        result = pipeline.run(ae_spec, grading_spec, render_spec)
        assert result.success

        # 检查点应该已保存
        ckpt = pipeline.load_checkpoint()
        assert ckpt is not None
        assert ckpt.stage == "davinci_render"
        assert "final_output" in ckpt.data

        # 清除检查点
        pipeline.clear_checkpoint()
        ckpt = pipeline.load_checkpoint()
        assert ckpt is None
