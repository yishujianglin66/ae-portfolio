"""
tests/test_s4_s5_real.py — S4 PR 卡点粗剪 + S5 DaVinci 调色 测试
================================================================

标记：@pytest.mark.real_pr / @pytest.mark.real_davinci
运行：pytest tests/test_s4_s5_real.py -m "real_pr or real_davinci" -v
"""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  S4 单元测试（不需要真实 PR）
# ============================================================================

class TestPREditStageUnit:
    """S4 PR 卡点粗剪单元测试（mock 引擎）"""

    def test_import(self):
        """模块可导入"""
        from pipeline.stages.pr_edit import S4_TOTAL_TIMEOUT, PREditResult, PREditStage
        assert S4_TOTAL_TIMEOUT == 600.0

    @pytest.mark.asyncio
    async def test_missing_beats_json(self, tmp_path):
        """beats.json 不存在 → 失败"""
        from pipeline.stages.pr_edit import PREditStage

        mock_engine = MagicMock()
        stage = PREditStage(engine=mock_engine)

        # 创建假视频文件
        vid = tmp_path / "clip.mov"
        vid.write_bytes(b"\x00" * 100)

        result = await stage.run(
            video_paths=[vid],
            beats_json_path=tmp_path / "nonexistent.json",
            output_dir=tmp_path / "S4",
        )
        assert result.success is False
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_missing_video(self, tmp_path):
        """视频文件不存在 → 失败"""
        from pipeline.stages.pr_edit import PREditStage

        mock_engine = MagicMock()
        stage = PREditStage(engine=mock_engine)

        # 创建 beats.json
        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0, 3.0, 4.0]}))

        result = await stage.run(
            video_paths=[tmp_path / "missing.mov"],
            beats_json_path=beats,
            output_dir=tmp_path / "S4",
        )
        assert result.success is False
        assert "Missing videos" in result.errors[0]

    @pytest.mark.asyncio
    async def test_beat_edit_failure(self, tmp_path):
        """Beat edit 引擎失败 → 整体失败"""
        from pipeline.stages.pr_edit import PREditStage

        mock_engine = MagicMock()
        mock_engine.auto_beat_edit = AsyncMock(return_value=MagicMock(
            success=False, error="Bridge offline", error_code="BRIDGE_DOWN"
        ))

        stage = PREditStage(engine=mock_engine)

        vid = tmp_path / "clip.mov"
        vid.write_bytes(b"\x00" * 100)
        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0, 3.0, 4.0]}))

        result = await stage.run(
            video_paths=[vid],
            beats_json_path=beats,
            output_dir=tmp_path / "S4",
        )
        assert result.success is False
        assert "BRIDGE_DOWN" in result.errors[0]

    @pytest.mark.asyncio
    async def test_full_success(self, tmp_path):
        """完整成功流程"""
        from pipeline.stages.pr_edit import PREditStage

        mock_engine = MagicMock()
        mock_engine.auto_beat_edit = AsyncMock(return_value=MagicMock(
            success=True,
            error=None,
            error_code=None,
            metadata={"result": json.dumps({"clips": 3, "markers": 5, "bpm": 128})},
        ))

        xml_content = b"<fcpxml></fcpxml>"
        xml_path = tmp_path / "S4" / "timeline.xml"

        async def mock_export(**kwargs):
            out = Path(kwargs["output_path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(xml_content)
            return MagicMock(success=True, error=None, output_path=out, metadata={})

        mock_engine.export_timeline_xml = mock_export

        stage = PREditStage(engine=mock_engine)

        vids = []
        for i in range(3):
            v = tmp_path / f"clip{i}.mov"
            v.write_bytes(b"\x00" * 100)
            vids.append(v)

        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({"bpm": 128, "drops": [1.0, 2.0, 3.0, 4.0, 5.0]}))

        result = await stage.run(
            video_paths=vids,
            beats_json_path=beats,
            output_dir=tmp_path / "S4",
        )
        assert result.success is True
        assert result.clips_imported == 3
        assert result.markers_added == 5
        assert result.timeline_xml is not None
        assert result.timeline_xml.exists()


# ============================================================================
#  S5 单元测试（不需要真实 DaVinci）
# ============================================================================

class TestDaVinciGradeStageUnit:
    """S5 DaVinci 调色单元测试（mock 引擎）"""

    def test_import(self):
        """模块可导入"""
        from pipeline.stages.davinci_grade import DaVinciGradeResult, DaVinciGradeStage
        assert DaVinciGradeResult is not None

    @pytest.mark.asyncio
    async def test_non_ascii_project_name(self, tmp_path):
        """非 ASCII 工程名 → 失败"""
        from pipeline.stages.davinci_grade import DaVinciGradeStage

        mock_engine = MagicMock()
        stage = DaVinciGradeStage(engine=mock_engine)

        xml = tmp_path / "timeline.xml"
        xml.write_text("<fcpxml/>")

        result = await stage.run(
            timeline_xml=xml,
            output_dir=tmp_path / "S5",
            project_name="旗舰工程",  # 非 ASCII
        )
        assert result.success is False
        assert "ASCII" in result.errors[0]

    @pytest.mark.asyncio
    async def test_missing_xml(self, tmp_path):
        """timeline.xml 不存在 → 失败"""
        from pipeline.stages.davinci_grade import DaVinciGradeStage

        mock_engine = MagicMock()
        stage = DaVinciGradeStage(engine=mock_engine)

        result = await stage.run(
            timeline_xml=tmp_path / "missing.xml",
            output_dir=tmp_path / "S5",
        )
        assert result.success is False
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_project_creation_failure(self, tmp_path):
        """工程创建失败 → 整体失败"""
        from pipeline.stages.davinci_grade import DaVinciGradeStage

        mock_engine = MagicMock()
        mock_engine.create_project_from_xml = AsyncMock(return_value=MagicMock(
            success=False, error="Resolve not running", error_code="RESOLVE_NOT_AVAILABLE"
        ))

        stage = DaVinciGradeStage(engine=mock_engine)
        xml = tmp_path / "timeline.xml"
        xml.write_text("<fcpxml/>")

        result = await stage.run(
            timeline_xml=xml,
            output_dir=tmp_path / "S5",
        )
        assert result.success is False
        assert "RESOLVE_NOT_AVAILABLE" in result.errors[0]

    @pytest.mark.asyncio
    async def test_full_success(self, tmp_path):
        """完整成功流程"""
        from pipeline.stages.davinci_grade import DaVinciGradeStage

        mock_engine = MagicMock()
        mock_engine.create_project_from_xml = AsyncMock(return_value=MagicMock(
            success=True, error=None, metadata={"project_name": "FlagshipDR"}
        ))
        mock_engine.apply_grade_nodes = AsyncMock(return_value=MagicMock(
            success=True, error=None,
            metadata={"node_count": 4, "include_lut": True}
        ))

        graded_path = tmp_path / "S5" / "graded.mov"

        async def mock_render(**kwargs):
            out = Path(kwargs["output_path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"\x00" * 500)
            return MagicMock(success=True, error=None, output_path=out)

        mock_engine.render_graded = mock_render

        stage = DaVinciGradeStage(engine=mock_engine)
        xml = tmp_path / "timeline.xml"
        xml.write_text("<fcpxml/>")

        result = await stage.run(
            timeline_xml=xml,
            output_dir=tmp_path / "S5",
        )
        assert result.success is True
        assert result.graded_mov is not None
        assert result.graded_mov.exists()
        assert result.nodes_applied == 4
        assert result.has_lut is True

    @pytest.mark.asyncio
    async def test_render_failure(self, tmp_path):
        """渲染失败 → 整体失败"""
        from pipeline.stages.davinci_grade import DaVinciGradeStage

        mock_engine = MagicMock()
        mock_engine.create_project_from_xml = AsyncMock(return_value=MagicMock(
            success=True, error=None, metadata={}
        ))
        mock_engine.apply_grade_nodes = AsyncMock(return_value=MagicMock(
            success=True, error=None, metadata={"node_count": 3, "include_lut": True}
        ))
        mock_engine.render_graded = AsyncMock(return_value=MagicMock(
            success=False, error="Render crashed", error_code="RENDER_FAILED"
        ))

        stage = DaVinciGradeStage(engine=mock_engine)
        xml = tmp_path / "timeline.xml"
        xml.write_text("<fcpxml/>")

        result = await stage.run(
            timeline_xml=xml,
            output_dir=tmp_path / "S5",
        )
        assert result.success is False
        assert "RENDER_FAILED" in result.errors[0]
        assert result.nodes_applied == 3


# ============================================================================
#  真实执行测试（需要 PR / DaVinci 运行）
# ============================================================================

@pytest.mark.real_pr
class TestPREditReal:
    """S4 真实 PR 执行"""

    @pytest.mark.asyncio
    async def test_auto_beat_edit_real(self, tmp_path):
        """真实 PR Bridge 卡点粗剪"""
        import sys
        pa_src = PROJECT_ROOT / "puppet-automation" / "src"
        if str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))

        try:
            from engines.premiere.engine import PremiereEngine
            engine = PremiereEngine()
        except Exception as e:
            pytest.skip(f"PR 引擎初始化失败: {e}")

        # 准备测试素材（需要 S3 产物或临时文件）
        beats = tmp_path / "beats.json"
        beats.write_text(json.dumps({
            "bpm": 128,
            "drops": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        }))

        # 创建临时视频（实际需要真实 .mov）
        vid = tmp_path / "test.mov"
        vid.write_bytes(b"\x00" * 1024)

        result = await engine.auto_beat_edit(
            video_paths=[vid],
            beats_json_path=beats,
            sequence_name="FlagshipTest",
        )
        # Bridge 不在线时应返回失败（不是崩溃）
        if not result.success:
            assert result.error is not None


@pytest.mark.real_davinci
class TestDaVinciGradeReal:
    """S5 真实 DaVinci 执行"""

    @pytest.mark.asyncio
    async def test_create_project_real(self, tmp_path):
        """真实 DaVinci 工程创建"""
        import sys
        pa_src = PROJECT_ROOT / "puppet-automation" / "src"
        if str(pa_src) not in sys.path:
            sys.path.insert(0, str(pa_src))

        try:
            from engines.davinci.engine import DavinciEngine
            engine = DavinciEngine()
        except Exception as e:
            pytest.skip(f"DaVinci 引擎初始化失败: {e}")

        xml = tmp_path / "timeline.xml"
        xml.write_text("<fcpxml><library></library></fcpxml>")

        result = await engine.create_project_from_xml(
            xml_path=xml,
            project_name="FlagshipTest",
        )
        # Resolve 不在线时应返回明确错误
        if not result.success:
            assert result.error is not None
