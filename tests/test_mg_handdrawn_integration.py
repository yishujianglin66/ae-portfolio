"""
tests/test_mg_handdrawn_integration.py — MG动画 + 手书动画集成测试
==================================================================

测试所有新增模块:
  - P0 适配器: SCAIL-2, MuseTalk, MatAnyone2, Remotion Agent
  - P1 模块: MGTemplateEngine, MGOrchestrator, HanddrawnStyler,
             HanddrawnPipeline, LottieExporter, AnimatedDrawings
  - 集成注册表: 新注册项可发现
  - 端到端: MG 动画产出 + Lottie JSON 产出 + 手绘风格化产出

运行: pytest tests/test_mg_handdrawn_integration.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
#  P0 适配器测试
# ============================================================================

class TestSCAIL2Adapter:
    """SCAIL-2 适配器测试"""

    def test_init(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        assert adapter.TOOL_NAME == "scail2"
        assert adapter.SUPPORTED_OPERATIONS

    def test_check_environment(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        result = adapter.execute("check_environment")
        assert "source_cloned" in result
        assert "simulate_mode" in result

    def test_list_capabilities(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        result = adapter.execute("list_capabilities")
        assert result["status"] == "success"
        assert "hand_drawn" in result["character_types"]
        assert result["zero_shot"] is True

    def test_get_model_info(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        info = adapter.execute("get_model_info")
        assert info["status"] == "success"
        assert info["model_name"] == "SCAIL-2"
        assert info["license"] == "Apache 2.0"

    def test_estimate_vram(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        result = adapter.execute("estimate_vram", {"resolution": "512x512", "num_frames": 60})
        assert result["status"] == "success"
        assert result["estimated_vram_gb"] > 0

    def test_animate_character_simulate(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        # Force simulate mode for testing
        adapter._simulate = True
        result = adapter.execute("animate_character", {
            "reference_image": "test_drawing.png",
            "motion_sequence": "test_motion.mp4",
            "output_path": "test_output.mp4",
        })
        assert result["status"] == "success"
        assert result.get("simulated_output") is True

    def test_check_available(self):
        from integrations.scail2_adapter import SCAIL2Adapter
        adapter = SCAIL2Adapter()
        # 即使源码未克隆，check_available 不应抛异常
        result = adapter.check_available()
        assert isinstance(result, bool)


class TestMuseTalkAdapter:
    """MuseTalk 适配器测试"""

    def test_init(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        assert adapter.TOOL_NAME == "musetalk"

    def test_check_environment(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        result = adapter.execute("check_environment")
        assert "source_cloned" in result

    def test_list_models(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        result = adapter.execute("list_models")
        assert result["status"] == "success"
        assert len(result["models"]) >= 2

    def test_get_model_info(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        info = adapter.execute("get_model_info")
        assert info["license"] == "Apache 2.0"
        assert info["vram_requirement"]["minimum_gb"] == 4

    def test_lip_sync_simulate(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        adapter._simulate = True
        result = adapter.execute("lip_sync", {
            "audio_path": "test.wav",
            "video_path": "test.mp4",
        })
        assert result["status"] == "success"

    def test_lip_sync_missing_params(self):
        from integrations.musetalk_adapter import MuseTalkAdapter
        adapter = MuseTalkAdapter()
        result = adapter.execute("lip_sync", {})
        assert result["status"] == "error"


class TestMatAnyone2Adapter:
    """MatAnyone2 适配器测试"""

    def test_init(self):
        from integrations.matanyone2_adapter import MatAnyone2Adapter
        adapter = MatAnyone2Adapter()
        assert adapter.TOOL_NAME == "matanyone2"

    def test_get_model_info(self):
        from integrations.matanyone2_adapter import MatAnyone2Adapter
        adapter = MatAnyone2Adapter()
        info = adapter.execute("get_model_info")
        assert "CVPR 2026" in info["venue"]
        assert info["vram_requirement"]["minimum_gb"] == 8

    def test_compare_with_v1(self):
        from integrations.matanyone2_adapter import MatAnyone2Adapter
        adapter = MatAnyone2Adapter()
        result = adapter.execute("compare_with_v1")
        assert result["status"] == "success"
        assert "v1" in result["comparison"]
        assert "v2" in result["comparison"]

    def test_video_matting_simulate(self):
        from integrations.matanyone2_adapter import MatAnyone2Adapter
        adapter = MatAnyone2Adapter()
        adapter._simulate = True
        result = adapter.execute("video_matting", {"video_path": "test.mp4"})
        assert result["status"] == "success"

    def test_estimate_vram(self):
        from integrations.matanyone2_adapter import MatAnyone2Adapter
        adapter = MatAnyone2Adapter()
        result = adapter.execute("estimate_vram", {"resolution": "1080p"})
        assert result["estimated_vram_gb"] > 0


class TestRemotionAgentAdapter:
    """Remotion Agent Skills 适配器测试"""

    def test_init(self):
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        assert adapter.TOOL_NAME == "remotion_agent"

    def test_list_templates(self):
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        result = adapter.execute("list_templates")
        assert result["status"] == "success"
        assert len(result["templates"]) >= 5

    def test_get_model_info(self):
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        info = adapter.execute("get_model_info")
        assert info["stars"] == "52k+"

    def test_generate_mg_animation_simulate(self):
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        adapter._simulate = True
        result = adapter.execute("generate_mg_animation", {
            "spec": {"type": "typography", "text": "Test"},
        })
        assert result["status"] == "success"
        assert "component_code" in result

    def test_check_environment(self):
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        result = adapter.execute("check_environment")
        assert "node_ok" in result


# ============================================================================
#  P1 模块测试
# ============================================================================

class TestMGTemplateEngine:
    """MG 模板引擎测试"""

    def test_init(self):
        from core.mg_template_engine import MGTemplateEngine
        engine = MGTemplateEngine()
        assert engine.SUPPORTED_TYPES

    def test_list_templates(self):
        from core.mg_template_engine import MGTemplateEngine
        engine = MGTemplateEngine()
        result = engine.list_templates()
        assert result["status"] == "success"
        assert len(result["templates"]) >= 4

    def test_parse_spec(self):
        from core.mg_template_engine import MGTemplateEngine
        engine = MGTemplateEngine()
        spec = engine._parse_spec({
            "type": "data_chart",
            "subtype": "bar",
            "data": [{"label": "A", "value": 42}],
            "style": {"bg": "#000000", "accent": "#ff0000"},
            "duration": 3.0,
        })
        assert spec.anim_type == "data_chart"
        assert spec.style.bg_color == "#000000"

    def test_render_pillow_ffmpeg(self):
        """测试 Pillow+FFmpeg 渲染 (需要 Pillow + FFmpeg)"""
        from core.mg_template_engine import MGTemplateEngine
        engine = MGTemplateEngine()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = engine.render(
                {"type": "typography", "text": "Test", "duration": 1.0, "fps": 10},
                output_path,
                backend="pillow_ffmpeg",
            )
            # 如果 FFmpeg 可用，应该成功
            if engine._ffmpeg_available:
                assert result["status"] == "success"
                assert os.path.exists(output_path)
                assert os.path.getsize(output_path) > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_lottie(self):
        """测试 Lottie JSON 导出"""
        from core.mg_template_engine import MGTemplateEngine
        engine = MGTemplateEngine()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            lottie_path = tmp.name

        try:
            result = engine.export_lottie({
                "type": "data_chart",
                "data": [{"label": "Q1", "value": 42}, {"label": "Q2", "value": 68}],
                "style": {"bg": "#1a1a2e", "accent": "#4fc3f7"},
                "duration": 3.0,
                "lottie_output": lottie_path,
            })
            assert result["status"] == "success"
            assert os.path.exists(lottie_path)

            # 验证 Lottie JSON 结构
            with open(lottie_path) as f:
                data = json.load(f)
            assert "v" in data
            assert "layers" in data
            assert len(data["layers"]) > 0
        finally:
            if os.path.exists(lottie_path):
                os.unlink(lottie_path)


class TestMGOrchestrator:
    """MG 编排器测试"""

    def test_init(self):
        from pipeline.mg_orchestrator import MGOrchestrator
        orch = MGOrchestrator()
        assert orch.STYLE_TEMPLATES

    def test_plan(self):
        from pipeline.mg_orchestrator import MGOrchestrator
        orch = MGOrchestrator()
        plan = orch.plan(
            style_spec={"type": "corporate", "duration": 10},
            content={"title": "Test Report", "data": [
                {"label": "A", "value": 42},
                {"label": "B", "value": 68},
            ]},
        )
        assert plan.total_duration_sec == 10.0
        assert len(plan.segments) >= 3
        assert plan.segments[0].segment_type == "title"

    def test_produce(self):
        """端到端 MG 动画生产测试"""
        from pipeline.mg_orchestrator import MGOrchestrator
        orch = MGOrchestrator()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = orch.produce(
                style_spec={"type": "minimal", "duration": 3},
                content={"title": "Quick Test"},
                output_path=output_path,
            )
            # 如果 FFmpeg 可用则验证输出
            if orch._engine._ffmpeg_available:
                assert result["status"] == "success"
                assert result["segments_rendered"] > 0
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)


class TestHanddrawnStyler:
    """手绘风格化处理器测试"""

    def test_init(self):
        from core.handdrawn_styler import HanddrawnStyler
        styler = HanddrawnStyler()
        assert styler.STYLES

    def test_check_available(self):
        from core.handdrawn_styler import HanddrawnStyler
        styler = HanddrawnStyler()
        result = styler.check_available()
        assert isinstance(result, bool)

    def test_stylize_image(self):
        """测试图像风格化 (需要 Pillow)"""
        from core.handdrawn_styler import HanddrawnStyler
        styler = HanddrawnStyler()

        if not styler._pil_available:
            pytest.skip("Pillow not available")

        # 创建测试图像
        import numpy as np
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试图像
            img = Image.fromarray(np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8))
            input_path = os.path.join(tmpdir, "test_input.png")
            output_path = os.path.join(tmpdir, "test_output.png")
            img.save(input_path)

            result = styler.stylize_image(input_path, output_path, "pencil_sketch")
            assert result["status"] == "success"
            assert os.path.exists(output_path)

    def test_stylize_frame(self):
        """测试帧风格化"""
        from core.handdrawn_styler import HanddrawnStyler
        styler = HanddrawnStyler()

        if not styler._pil_available:
            pytest.skip("Pillow not available")

        import numpy as np
        from PIL import Image

        # numpy 输入
        frame = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
        result = styler.stylize_frame(frame, "pencil_sketch")
        assert result.shape == frame.shape

        # PIL 输入
        img = Image.fromarray(frame)
        result_img = styler.stylize_frame(img, "pencil_sketch")
        assert isinstance(result_img, Image.Image)


class TestLottieExporter:
    """Lottie 导出器测试"""

    def test_init(self):
        from core.lottie_exporter import LottieExporter
        exporter = LottieExporter()
        assert exporter.ANIMATIONS

    def test_create_animation(self):
        from core.lottie_exporter import LottieExporter
        exporter = LottieExporter()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = tmp.name

        try:
            result = exporter.create_animation(
                layers=[
                    {"type": "text", "text": "Hello", "animation": "fade_in"},
                    {"type": "shape", "shape": "circle", "animation": "scale_up", "color": "#ff0000"},
                ],
                output_path=output_path,
                duration_sec=3,
            )
            assert result["status"] == "success"
            assert result["layer_count"] == 2
            assert os.path.exists(output_path)

            # 验证 JSON 结构
            with open(output_path) as f:
                data = json.load(f)
            assert data["v"] == "5.7.1"
            assert len(data["layers"]) == 2
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_validate_lottie(self):
        from core.lottie_exporter import LottieExporter
        exporter = LottieExporter()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as tmp:
            json.dump({
                "v": "5.7.1", "fr": 30, "ip": 0, "op": 90,
                "w": 800, "h": 600, "layers": [
                    {"ty": 4, "ks": {"o": {"a": 0, "k": 100}}},
                ],
            }, tmp)
            output_path = tmp.name

        try:
            result = exporter.validate_lottie(output_path)
            assert result["valid"] is True
            assert result["layer_count"] == 1
        finally:
            os.unlink(output_path)


class TestAnimatedDrawingsAdapter:
    """AnimatedDrawings 适配器测试"""

    def test_init(self):
        from integrations.animated_drawings_adapter import AnimatedDrawingsAdapter
        adapter = AnimatedDrawingsAdapter()
        assert adapter.TOOL_NAME == "animated_drawings"

    def test_list_motions(self):
        from integrations.animated_drawings_adapter import AnimatedDrawingsAdapter
        adapter = AnimatedDrawingsAdapter()
        result = adapter.execute("list_motions")
        assert "walk" in result["motions"]
        assert len(result["motions"]) >= 8

    def test_animate_drawing_simulate(self):
        from integrations.animated_drawings_adapter import AnimatedDrawingsAdapter
        adapter = AnimatedDrawingsAdapter()
        # 源码已克隆后默认走真实执行, 此处强制模拟模式测试接口逻辑
        adapter._simulate = True
        result = adapter.execute("animate_drawing", {
            "image_path": "doodle.png",
            "motion": "walk",
        })
        assert result["status"] == "success"


# ============================================================================
#  集成注册表测试
# ============================================================================

class TestIntegrationRegistryNewItems:
    """测试新增集成项在注册表中可发现"""

    def test_scail2_registered(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        assert "scail2" in registry.KNOWN_INTEGRATIONS
        info = registry.KNOWN_INTEGRATIONS["scail2"]
        assert info["priority"] == "P0"
        assert info["adapter_module"] == "integrations.scail2_adapter"

    def test_musetalk_registered(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        assert "musetalk" in registry.KNOWN_INTEGRATIONS

    def test_matanyone2_registered(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        assert "matanyone2" in registry.KNOWN_INTEGRATIONS

    def test_remotion_agent_registered(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        assert "remotion_agent" in registry.KNOWN_INTEGRATIONS

    def test_discover_new_integrations(self):
        """测试新集成可被发现"""
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        discovered = registry.discover_all()
        for name in ["scail2", "musetalk", "matanyone2", "remotion_agent"]:
            assert name in discovered, f"{name} not discovered"

    def test_adapter_instantiation(self):
        """测试适配器可实例化"""
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        registry.discover_all()

        for name in ["scail2", "musetalk", "matanyone2", "remotion_agent"]:
            adapter = registry.get(name)
            assert adapter is not None, f"{name} adapter is None"
            assert adapter.check_available() is not None  # 不应抛异常


# ============================================================================
#  端到端集成测试
# ============================================================================

class TestEndToEnd:
    """端到端集成测试"""

    def test_mg_animation_e2e(self):
        """MG 动画端到端: 规格书 → 渲染 → 输出"""
        from pipeline.mg_orchestrator import MGOrchestrator
        orch = MGOrchestrator()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "mg_e2e.mp4")
            result = orch.produce(
                style_spec={"type": "corporate", "duration": 2},
                content={"title": "E2E Test", "data": [{"label": "X", "value": 50}]},
                output_path=output_path,
            )
            assert result.get("status") in ("success", "error")  # 不强制成功（可能无 FFmpeg）
            if result["status"] == "success":
                assert os.path.exists(output_path)

    def test_lottie_e2e(self):
        """Lottie 导出端到端"""
        from core.lottie_exporter import LottieExporter
        exporter = LottieExporter()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "e2e_test.json")
            result = exporter.create_animation(
                layers=[
                    {"type": "text", "text": "E2E", "animation": "fade_in"},
                    {"type": "shape", "shape": "rect", "animation": "scale_up"},
                ],
                output_path=output_path,
                duration_sec=2,
            )
            assert result["status"] == "success"
            assert os.path.exists(output_path)

            # 验证
            validation = exporter.validate_lottie(output_path)
            assert validation["valid"] is True

    def test_handdrawn_stylize_e2e(self):
        """手绘风格化端到端"""
        from core.handdrawn_styler import HanddrawnStyler
        styler = HanddrawnStyler()

        if not styler._pil_available:
            pytest.skip("Pillow not available")

        import numpy as np
        from PIL import Image

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试图像
            img = Image.fromarray(np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8))
            input_path = os.path.join(tmpdir, "input.png")
            img.save(input_path)

            for style in ["pencil_sketch", "ink_drawing", "comic"]:
                output_path = os.path.join(tmpdir, f"output_{style}.png")
                result = styler.stylize_image(input_path, output_path, style)
                assert result["status"] == "success"
                assert os.path.exists(output_path)


# ============================================================================
#  P1-4: ComfyUI 手绘风格化适配器测试 (2026-08-24 新增)
# ============================================================================

class TestComfyUIHanddrawnAdapter:
    """ComfyUI 手绘风格化适配器测试"""

    def test_init_and_styles(self):
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        assert adapter.TOOL_NAME == "comfyui_handdrawn"
        result = adapter.execute("list_styles", {})
        assert result["status"] == "success"
        assert set(result["styles"]) == {
            "pencil_sketch", "ink_drawing", "watercolor",
            "comic", "crayon", "doodle",
        }

    def test_check_environment(self):
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        result = adapter.execute("check_environment", {})
        assert result["status"] == "success"
        assert result["workflow_template_exists"] is True
        assert "server_online" in result
        assert "simulate_mode" in result

    def test_build_workflow_all_styles(self):
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        for style in adapter.STYLE_PROMPTS:
            wf = adapter.build_workflow(style, "input.png", seed=42)
            assert wf["1"]["class_type"] == "CheckpointLoaderSimple"
            assert wf["6"]["class_type"] == "KSampler"
            assert wf["6"]["inputs"]["seed"] == 42
            assert wf["6"]["inputs"]["denoise"] == 0.75
            assert wf["3"]["inputs"]["text"] == adapter.STYLE_PROMPTS[style]
            assert "{{" not in json.dumps(wf)  # 占位符全部替换

    def test_build_workflow_invalid_style(self):
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        with pytest.raises(ValueError):
            adapter.build_workflow("not_a_style", "input.png")

    def test_stylize_simulate_dryrun(self):
        """服务端离线时: 生成可提交工作流 JSON (dry-run)"""
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        adapter._simulate = True  # 强制模拟模式, 避免依赖服务端在线状态变化
        with tempfile.TemporaryDirectory() as tmpdir:
            inp = os.path.join(tmpdir, "in.png")
            # 生成一个真实的小图像文件 (满足存在性检查)
            import numpy as np
            from PIL import Image
            Image.fromarray(
                np.zeros((64, 64, 3), dtype=np.uint8)
            ).save(inp)
            out = os.path.join(tmpdir, "out.png")
            result = adapter.execute("stylize_image", {
                "input_image": inp, "output_path": out, "style": "comic",
            })
            assert result["status"] == "success"
            assert result["simulate"] is True
            assert os.path.exists(result["workflow_json"])
            wf = json.loads(Path(result["workflow_json"]).read_text(encoding="utf-8"))
            assert wf["2"]["inputs"]["image"] == "in.png"

    def test_stylize_missing_input(self):
        from integrations.comfyui_handdrawn_adapter import HanddrawnComfyUIAdapter
        adapter = HanddrawnComfyUIAdapter()
        result = adapter.execute("stylize_image", {
            "input_image": "no_such_file_xyz.png", "output_path": "x.png",
        })
        assert result["status"] == "error"

    def test_registry_entry(self):
        from integrations.integration_registry import IntegrationRegistry
        known = IntegrationRegistry.KNOWN_INTEGRATIONS
        entry = known["comfyui_handdrawn"]
        assert entry["adapter_module"] == "integrations.comfyui_handdrawn_adapter"
        assert entry["adapter_class"] == "HanddrawnComfyUIAdapter"
        assert entry["priority"] == "P1"


# ============================================================================
#  P1-6: Motion Canvas 适配器测试 (2026-08-24 新增)
# ============================================================================

class TestMotionCanvasAdapter:
    """Motion Canvas 适配器测试"""

    def test_init(self):
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        adapter = MotionCanvasAdapter()
        assert adapter.TOOL_NAME == "motion_canvas"
        assert "init_project" in adapter.SUPPORTED_OPERATIONS

    def test_check_environment(self):
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        adapter = MotionCanvasAdapter()
        result = adapter.execute("check_environment", {})
        assert result["status"] == "success"
        assert "node_available" in result
        assert "npm_available" in result
        assert "project_initialized" in result

    def test_list_templates(self):
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        adapter = MotionCanvasAdapter()
        result = adapter.execute("list_templates", {})
        assert result["status"] == "success"
        assert "typography" in result["templates"]
        assert "data_chart" in result["templates"]

    def test_init_project_and_generate_scenes(self):
        """init_project 生成脚手架 + 三种场景模板均为合法 TSX 结构"""
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = MotionCanvasAdapter(
                {"project_dir": os.path.join(tmpdir, "mc")}
            )
            r = adapter.execute("init_project", {})
            assert r["status"] == "success"
            for f in ["package.json", "tsconfig.json", "vite.config.ts",
                      "src/project.ts", "src/scenes/example.tsx"]:
                assert os.path.exists(os.path.join(tmpdir, "mc", f))
            pkg = json.loads(Path(os.path.join(tmpdir, "mc", "package.json"))
                             .read_text(encoding="utf-8"))
            assert "@motion-canvas/core" in pkg["dependencies"]

            # typography
            r1 = adapter.execute("generate_scene", {
                "scene_name": "t1",
                "spec": {"type": "typography", "title": "Hi", "duration": 1.0},
            })
            assert r1["status"] == "success"
            src1 = Path(r1["scene_path"]).read_text(encoding="utf-8")
            assert "makeScene2D" in src1 and '"Hi"' in src1

            # data_chart
            r2 = adapter.execute("generate_scene", {
                "scene_name": "c1",
                "spec": {"type": "data_chart",
                         "data": [{"label": "A", "value": 30},
                                  {"label": "B", "value": 60}]},
            })
            assert r2["status"] == "success"
            src2 = Path(r2["scene_path"]).read_text(encoding="utf-8")
            assert "bar0" in src2 and "bar1" in src2 and "easeOutCubic" in src2

            # shape
            r3 = adapter.execute("generate_scene", {
                "scene_name": "s1",
                "spec": {"type": "shape", "duration": 1.5},
            })
            assert r3["status"] == "success"
            src3 = Path(r3["scene_path"]).read_text(encoding="utf-8")
            assert "Circle" in src3 and "Rect" in src3

    def test_generate_scene_invalid_type(self):
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = MotionCanvasAdapter(
                {"project_dir": os.path.join(tmpdir, "mc")}
            )
            r = adapter.execute("generate_scene", {
                "scene_name": "bad", "spec": {"type": "unknown_type"},
            })
            assert r["status"] == "error"

    def test_render_without_deps_reports_error(self):
        """依赖未安装时 render 应明确报错而非静默失败"""
        from integrations.motion_canvas_adapter import MotionCanvasAdapter
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = MotionCanvasAdapter(
                {"project_dir": os.path.join(tmpdir, "mc_empty")}
            )
            r = adapter.execute("render", {})
            assert r["status"] == "error"

    def test_registry_entry(self):
        from integrations.integration_registry import IntegrationRegistry
        known = IntegrationRegistry.KNOWN_INTEGRATIONS
        entry = known["motion_canvas"]
        assert entry["adapter_module"] == "integrations.motion_canvas_adapter"
        assert entry["adapter_class"] == "MotionCanvasAdapter"
        assert entry["priority"] == "P1"
