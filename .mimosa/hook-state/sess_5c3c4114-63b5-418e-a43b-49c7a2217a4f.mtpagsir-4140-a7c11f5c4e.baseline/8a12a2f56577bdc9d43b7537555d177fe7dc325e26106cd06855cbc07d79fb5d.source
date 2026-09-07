"""P2 跨引擎一体化流水线端到端测试

验证内容：
1. 四个跨引擎桥接器实例化 + 方法签名
2. PipelineOrchestrator 四种 Pipeline 类型调度
3. 桥接器调用引擎方法的接口匹配
4. 完整流水线编排逻辑验证

运行: pytest tests/test_p2_cross_engine_pipeline.py -v
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "bridges"))
# puppet-automation 目录名含连字符，无法作为包导入，按仓库标准口径
# （同 test_all_engines.py）加入路径后用 src.engines.* 导入
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))


# ============================================================================
#  1. 桥接器实例化测试
# ============================================================================

class TestBridgeInstantiation:
    """验证四个桥接器可以正确实例化。"""

    def test_blender_ae_bridge(self):
        from bridges.blender_ae_bridge import BlenderAEBridge
        bridge = BlenderAEBridge()
        assert bridge is not None
        assert hasattr(bridge, "create_3d_scene_for_ae")
        assert hasattr(bridge, "create_cel_shading_for_ae")
        assert hasattr(bridge, "create_foreground_element_for_ae")

    def test_topaz_davinci_bridge(self):
        from bridges.topaz_davinci_bridge import TopazDaVinciBridge
        bridge = TopazDaVinciBridge()
        assert bridge is not None
        assert hasattr(bridge, "enhance_for_color_grading")
        assert hasattr(bridge, "batch_enhance_for_color_grading")

    def test_silhouette_ae_bridge(self):
        from bridges.silhouette_ae_bridge import SilhouetteAEBridge
        bridge = SilhouetteAEBridge()
        assert bridge is not None
        assert hasattr(bridge, "roto_to_ae_mask")
        assert hasattr(bridge, "track_to_ae")

    def test_c4d_ae_bridge(self):
        from bridges.c4d_ae_bridge import C4DAEBridge
        bridge = C4DAEBridge()
        assert bridge is not None
        assert hasattr(bridge, "render_c4d_scene_to_ae")
        assert hasattr(bridge, "render_motion_graphics_to_ae")


# ============================================================================
#  2. PipelineOrchestrator 测试
# ============================================================================

class TestPipelineOrchestrator:
    """验证 PipelineOrchestrator 的调度和编排逻辑。"""

    def test_instantiation(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        assert orchestrator is not None
        assert hasattr(orchestrator, "run_pipeline")
        assert hasattr(orchestrator, "PIPELINE_TYPES")

    def test_pipeline_types(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        expected_types = {
            "full_3d_pipeline",
            "animation_pipeline",
            "mograph_pipeline",
            "enhancement_pipeline",
        }
        for t in expected_types:
            assert t in orchestrator.PIPELINE_TYPES

    @pytest.mark.asyncio
    async def test_unknown_pipeline_type(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run_pipeline("nonexistent", {})
        assert result["success"] is False
        assert "Unknown pipeline type" in result["error"]

    @pytest.mark.asyncio
    async def test_enhancement_pipeline_missing_input(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run_pipeline("enhancement_pipeline", {})
        assert result["success"] is False
        assert "input_path is required" in result["error"]


# ============================================================================
#  3. 桥接器与引擎接口匹配测试
# ============================================================================

class TestBridgeEngineInterface:
    """验证桥接器调用的引擎方法确实存在。"""

    def test_blender_engine_has_required_methods(self):
        from src.engines.blender import BlenderEngine
        engine = BlenderEngine()
        assert hasattr(engine, "create_puppet_stage")
        assert hasattr(engine, "render_cel_animation")
        assert hasattr(engine, "render_foreground_element")

    def test_topaz_engine_has_enhance(self):
        from src.engines.topaz import TopazEngine
        engine = TopazEngine()
        assert hasattr(engine, "enhance")

    def test_silhouette_engine_has_export_shapes(self):
        from src.engines.silhouette import SilhouetteEngine
        engine = SilhouetteEngine()
        assert hasattr(engine, "export_shapes")
        assert hasattr(engine, "create_roto_session")
        assert hasattr(engine, "run_tracker")

    def test_davinci_engine_has_timeline_methods(self):
        from src.engines.davinci import DavinciEngine
        engine = DavinciEngine()
        assert hasattr(engine, "import_media_and_create_timeline")

    def test_ae_engine_has_required_methods(self):
        from src.engines.ae import AEEngine
        engine = AEEngine()
        assert hasattr(engine, "create_project")
        assert hasattr(engine, "import_footage")

    def test_c4d_engine_has_required_methods(self):
        from src.engines.cinema4d import Cinema4DEngine
        engine = Cinema4DEngine()
        assert hasattr(engine, "render_scene")
        assert hasattr(engine, "render_motion_graphics")
        assert hasattr(engine, "export_camera_data")


# ============================================================================
#  4. 引擎 execute 调度测试（需要实际软件，标记为可选）
# ============================================================================

@pytest.mark.optional
class TestEngineDispatch:
    """验证引擎的 _execute_impl 正确分发到桥接器需要的方法。
    
    这些测试需要实际的 Silhouette/DaVinci 软件运行，
    在没有软件可用的环境中会被自动跳过。
    """

    @pytest.mark.asyncio
    async def test_silhouette_dispatch_export_shapes(self):
        from src.engines.silhouette import SilhouetteEngine
        engine = SilhouetteEngine()
        if not engine.available:
            pytest.skip("Silhouette not available")
        result = await engine.execute(
            action="export_shapes",
            output_path="/tmp/test_shapes.json",
        )
        assert result is not None
        assert hasattr(result, "success")

    @pytest.mark.asyncio
    async def test_silhouette_dispatch_roto(self):
        from src.engines.silhouette import SilhouetteEngine
        engine = SilhouetteEngine()
        if not engine.available:
            pytest.skip("Silhouette not available")
        result = await engine.execute(
            action="create_roto_session",
            video_path="/tmp/test.mp4",
            output_dir="/tmp/roto_output",
        )
        assert result is not None
        assert hasattr(result, "success")

    @pytest.mark.asyncio
    async def test_davinci_dispatch_timeline(self):
        from src.engines.davinci import DavinciEngine
        engine = DavinciEngine()
        if not engine.available:
            pytest.skip("DaVinci not available")
        result = await engine.execute(
            action="import_media_and_create_timeline",
            media_paths=["/tmp/test.mp4"],
            timeline_name="Test Timeline",
        )
        assert result is not None
        assert hasattr(result, "success")


# ============================================================================
#  5. Bridges __init__ 导出测试
# ============================================================================

class TestBridgesPackage:
    """验证 bridges 包正确导出所有公共接口。"""

    def test_exports_all_bridges(self):
        from bridges import (
            BlenderAEBridge,
            TopazDaVinciBridge,
            SilhouetteAEBridge,
            C4DAEBridge,
            PipelineOrchestrator,
        )
        assert BlenderAEBridge is not None
        assert TopazDaVinciBridge is not None
        assert SilhouetteAEBridge is not None
        assert C4DAEBridge is not None
        assert PipelineOrchestrator is not None


# ============================================================================
#  6. 模拟数据链路测试（不依赖实际软件）
# ============================================================================

@pytest.mark.optional
class TestDataFlowSimulation:
    """验证数据在桥接器之间的传递逻辑。
    
    这些测试会尝试调用实际引擎，需要软件可用。
    在没有软件可用的环境中会被自动跳过。
    """

    @pytest.mark.asyncio
    @pytest.mark.real_render
    async def test_full_3d_pipeline_structure(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        
        # 检查引擎可用性
        if not orchestrator.blender_ae.blender_engine.available:
            pytest.skip("Blender not available")
            
        config = {
            "output_dir": "D:/AE-Work/pipeline/test_output",
            "stage_style": "wooden",
            "resolution": [1920, 1080],
            "frame_count": 30,
        }
        result = await orchestrator._run_full_3d_pipeline(config)
        assert "pipeline_type" in result
        assert result["pipeline_type"] == "full_3d_pipeline"
        assert "step_results" in result
        assert "errors" in result

    @pytest.mark.asyncio
    @pytest.mark.real_render
    async def test_animation_pipeline_structure(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        
        if not orchestrator.blender_ae.blender_engine.available:
            pytest.skip("Blender not available")
            
        config = {
            "output_dir": "D:/AE-Work/pipeline/test_output",
            "cel_style": "anime",
            "resolution": [1920, 1080],
            "frame_count": 30,
        }
        result = await orchestrator._run_animation_pipeline(config)
        assert result["pipeline_type"] == "animation_pipeline"
        assert "step_results" in result

    @pytest.mark.asyncio
    @pytest.mark.real_render
    async def test_mograph_pipeline_structure(self):
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        
        if not orchestrator.c4d_ae.c4d_engine.available:
            pytest.skip("Cinema 4D not available")
            
        config = {
            "output_dir": "D:/AE-Work/pipeline/test_output",
            "text": "TEST",
            "resolution": [1920, 1080],
            "frame_count": 30,
        }
        result = await orchestrator._run_mograph_pipeline(config)
        assert result["pipeline_type"] == "mograph_pipeline"
        assert "step_results" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
