"""P2 全量自检 + 修复验证测试

验证所有修复：
1. P0: PhotoshopEngine 不再覆盖 execute()
2. P1: Premiere/Photoshop/FFmpeg handlers 完整
3. P2: BlenderEngine 无重复方法
4. AME: 引擎正确初始化
5. Orchestrator: 19节点完整注册
6. 跨引擎桥接器接口匹配

运行: python -m pytest tests/test_p2_full_selfcheck.py -v --tb=short
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "bridges"))
# puppet-automation 目录名含连字符，按仓库标准口径加入路径后用 src.engines.* 导入
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))


class TestP0PhotoshopExecuteFix:
    """P0: PhotoshopEngine 不再覆盖 execute() Final模板方法。"""

    def test_ps_does_not_override_execute(self):
        """确认 PhotoshopEngine 没有覆盖 execute() 方法。"""
        from src.engines.photoshop import PhotoshopEngine
        # 获取类自身的属性（不继承）
        own_execute = "execute" in PhotoshopEngine.__dict__
        assert not own_execute, "PhotoshopEngine 仍然覆盖了 execute() — BaseEngine 保护机制失效!"

    def test_ps_execute_impl_uses_handlers(self):
        """确认 _execute_impl 使用 handlers dict 模式。"""
        from src.engines.photoshop import PhotoshopEngine
        engine = PhotoshopEngine()
        assert hasattr(engine, "_execute_impl")
        # 确认 _execute_impl 不再委托给 self.execute()
        import inspect
        source = inspect.getsource(engine._execute_impl)
        assert "handlers" in source, "_execute_impl 应使用 handlers dict 模式"
        assert "self.execute" not in source, "_execute_impl 不应委托给 execute()"


class TestP1HandlerCompleteness:
    """P1: 验证三个引擎的 handlers 分发完整性。"""

    @pytest.mark.asyncio
    async def test_premiere_handlers_include_export_via_ffmpeg(self):
        from src.engines.premiere import PremiereEngine
        engine = PremiereEngine()
        # 尝试通过 execute 调用 export_via_ffmpeg
        result = await engine.execute(action="export_via_ffmpeg")
        # 应该返回 EngineResult（即使参数不足也不应该返回 Unknown action）
        assert result is not None
        assert hasattr(result, "success")
        if not result.success:
            assert "Unknown action" not in (result.error or ""), \
                "export_via_ffmpeg 应在 handlers 中注册"

    @pytest.mark.asyncio
    async def test_photoshop_handlers_include_all_actions(self):
        from src.engines.photoshop import PhotoshopEngine
        engine = PhotoshopEngine()
        # 测试各 action 都能被分发
        for action in ["export_layers", "smart_object_export", "lut", "generate_lut", "batch"]:
            result = await engine.execute(action=action)
            assert result is not None
            if not result.success:
                assert "Unknown action" not in (result.error or ""), \
                    f"action '{action}' 应在 handlers 中注册"

    @pytest.mark.asyncio
    async def test_ffmpeg_handlers_include_image_sequence_to_video(self):
        from src.engines.ffmpeg import FFmpegEngine
        engine = FFmpegEngine()
        result = await engine.execute(action="image_sequence_to_video")
        assert result is not None
        if not result.success:
            assert "Unknown action" not in (result.error or ""), \
                "image_sequence_to_video 应在 handlers 中注册"


class TestP2BlenderNoDuplicate:
    """P2: BlenderEngine 不再有重复的 export_camera_data。"""

    def test_blender_single_export_camera_data(self):
        """确认 export_camera_data 只有一个定义。"""
        from src.engines.blender import BlenderEngine
        # 检查方法签名包含 camera_name 参数（L808版本的签名）
        import inspect
        sig = inspect.signature(BlenderEngine.export_camera_data)
        params = list(sig.parameters.keys())
        assert "camera_name" in params, \
            "export_camera_data 应该是完整版本（含 camera_name, frame_start, frame_end 参数）"
        assert "frame_start" in params
        assert "frame_end" in params


class TestAMEEngine:
    """AME 引擎验证。"""

    def test_ame_available(self):
        """确认 AME 引擎正确初始化且可用。"""
        from src.engines.media_encoder import MediaEncoderEngine
        engine = MediaEncoderEngine()
        assert engine.available, "AME 2025 应该已安装且可用"
        assert engine.name == "media_encoder"

    def test_ame_no_dead_cli_path(self):
        """确认不再有指向不存在文件的 cli_path 字段。"""
        from src.engines.media_encoder import MediaEncoderEngine
        engine = MediaEncoderEngine()
        assert not hasattr(engine, "cli_path"), \
            "cli_path 字段应已删除（AME 无 AMETemplateFile.dll）"


class TestOrchestratorNodes:
    """Orchestrator 节点完整性验证。"""

    def test_task_type_enum_has_new_types(self):
        from core.workflow_orchestrator import TaskType
        new_types = [
            TaskType.PS_PREPROCESS,
            TaskType.DAVINCI_GRADE,
            TaskType.C4D_MOGRAPH,
            TaskType.FFMPEG_EXPORT,
            TaskType.WHISPER_SUBTITLE,
            TaskType.AME_ENCODE,
        ]
        for t in new_types:
            assert t is not None

    def test_orchestrator_registers_19_nodes(self):
        """验证 orchestrator 注册了19个节点（原13个+6个新增）。"""
        from core.workflow_orchestrator import WorkflowOrchestrator
        orchestrator = WorkflowOrchestrator()

        # 模拟 pipeline_funcs — 所有key返回一个 no-op async 函数
        async def _noop(**kwargs):
            return {"success": True}

        all_keys = [
            "perceive", "understand", "plan",
            "execute_silhouette", "silhouette_fallback",
            "compile", "execute_ae",
            "execute_topaz", "topaz_fallback",
            "execute_runway", "runway_fallback",
            "execute_pika", "pika_fallback",
            "execute_flux3", "flux3_fallback",
            "execute_blender", "blender_fallback",
            "execute_ffmpeg", "ffmpeg_fallback",
            "execute_ps_preprocess",
            "execute_davinci_grade",
            "execute_c4d_mograph",
            "execute_whisper_subtitle",
            "execute_ffmpeg_export",
            "execute_ame_encode",
            "feedback",
        ]
        pipeline_funcs = {k: _noop for k in all_keys}
        orchestrator.build_default_pipeline(pipeline_funcs)

        # 检查注册的节点（_tasks_def 是 List[TaskDefinition]，需要提取 task_id）
        registered_ids = {t.task_id for t in orchestrator._tasks_def}
        expected_ids = {
            "perception", "understanding", "planning",
            "ps_preprocess", "silhouette", "ae_compile", "ae_execute",
            "topaz_enhance", "davinci_grade",
            "runway_generate", "pika_generate", "flux3_generate",
            "blender_render", "c4d_mograph", "whisper_subtitle",
            "ffmpeg_transcode", "ffmpeg_export", "ame_encode",
            "feedback",
        }
        missing = expected_ids - registered_ids
        assert not missing, f"缺失的节点: {missing}"
        assert len(registered_ids) == 19, f"期望19个节点，实际 {len(registered_ids)}"


class TestCrossEngineBridgeIntegration:
    """跨引擎桥接器集成验证。"""

    def test_all_bridges_importable(self):
        from bridges import (
            BlenderAEBridge,
            TopazDaVinciBridge,
            SilhouetteAEBridge,
            C4DAEBridge,
            PipelineOrchestrator,
        )
        assert all([
            BlenderAEBridge,
            TopazDaVinciBridge,
            SilhouetteAEBridge,
            C4DAEBridge,
            PipelineOrchestrator,
        ])

    def test_pipeline_orchestrator_has_4_types(self):
        from bridges import PipelineOrchestrator
        orchestrator = PipelineOrchestrator()
        assert len(orchestrator.PIPELINE_TYPES) == 4


class TestEngineAvailableFlags:
    """验证所有引擎的 available 标志正确设置。"""

    def test_all_engines_have_available(self):
        from src.engines.ae import AEEngine
        from src.engines.premiere import PremiereEngine
        from src.engines.photoshop import PhotoshopEngine
        from src.engines.ffmpeg import FFmpegEngine
        from src.engines.davinci import DavinciEngine
        from src.engines.blender import BlenderEngine
        from src.engines.topaz import TopazEngine
        from src.engines.silhouette import SilhouetteEngine
        from src.engines.cinema4d import Cinema4DEngine
        from src.engines.media_encoder import MediaEncoderEngine

        engines = [
            AEEngine, PremiereEngine, PhotoshopEngine, FFmpegEngine,
            DavinciEngine, BlenderEngine, TopazEngine, SilhouetteEngine,
            Cinema4DEngine, MediaEncoderEngine,
        ]
        for EngineClass in engines:
            engine = EngineClass()
            assert hasattr(engine, "available"), f"{EngineClass.__name__} 缺少 available 属性"
            # available 应该是 bool
            assert isinstance(engine.available, bool), \
                f"{EngineClass.__name__}.available 不是 bool 类型"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
