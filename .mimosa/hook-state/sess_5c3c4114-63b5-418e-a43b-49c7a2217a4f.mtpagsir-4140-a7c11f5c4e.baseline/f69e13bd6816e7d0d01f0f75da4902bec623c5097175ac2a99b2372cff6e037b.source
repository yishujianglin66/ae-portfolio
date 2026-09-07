"""
端到端闭环验证测试套件
覆盖：纯 AE / 纯 Silhouette / 混合任务 / 降级路径 / 失败恢复 / 渲染验证 / 参数回读
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import (
    AEAgentPipeline, PlanningResult, ExecutionResult,
    PerceptionResult, UnderstandingResult, FeedbackResult,
)


# ============================================================================
# 测试夹具
# ============================================================================

@pytest.fixture
def pipeline():
    """创建 Pipeline 实例"""
    return AEAgentPipeline()


@pytest.fixture
def mock_ae_client():
    """模拟 AE MCP 客户端"""
    client = Mock()
    client.send_command.return_value = {"success": True, "status": "success"}
    client.clear_result = Mock()
    return client


@pytest.fixture
def basic_planning():
    """基础规划结果"""
    planning = PlanningResult()
    planning.composition = {
        "name": "Test_Comp",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30,
    }
    planning.layers = [
        {"name": "Video1", "type": "footage", "source": "/path/v1.mp4", "startTime": 0, "duration": 5}
    ]
    planning.effects = [
        {"layerName": "Video1", "effectName": "ADBE Glo2", "matchName": "ADBE Glo2", "settings": {"Glow Radius": 20}}
    ]
    planning.keyframes = []
    planning.transitions = []
    planning.execution_order = ["createComposition"]
    planning.silhouette_operations = []
    planning.compiler_operations = []
    return planning


# ============================================================================
# P0-1: 渲染结果验证测试
# ============================================================================

class TestRenderVerification:
    """渲染结果验证机制测试"""

    def test_render_success_with_file(self, pipeline, basic_planning, mock_ae_client, tmp_path):
        """测试渲染成功且文件存在"""
        output_file = tmp_path / "output.mp4"
        output_file.write_bytes(b"x" * 10000)  # 创建真实文件

        mock_ae_client.send_command.return_value = {
            "success": True,
            "status": "success",
            "outputPath": str(output_file),
            "fileSize": 10000,
        }

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            with patch.object(pipeline, "_config", {"output": {"default_dir": str(tmp_path)}}):
                result = pipeline.execute(basic_planning)

        assert result.success is True
        assert result.output_path is not None

    def test_render_queued_status(self, pipeline, basic_planning, mock_ae_client):
        """测试渲染入队状态（waitForCompletion=false）"""
        mock_ae_client.send_command.return_value = {
            "success": True,
            "status": "queued",
            "message": "Render queued",
        }

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            result = pipeline.execute(basic_planning)

        assert result.success is True
        assert "入队" in (result.warning or "")

    def test_render_timeout(self, pipeline, basic_planning, mock_ae_client):
        """测试渲染超时"""
        mock_ae_client.send_command.return_value = {
            "success": False,
            "status": "timeout",
            "message": "Render timed out after 300s",
        }

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            result = pipeline.execute(basic_planning)

        assert result.success is False
        assert "timed out" in result.error_message.lower() or "超时" in result.error_message

    def test_render_small_file_detected(self, pipeline, basic_planning, mock_ae_client, tmp_path):
        """测试检测到过小的渲染输出文件"""
        output_file = tmp_path / "small.mp4"
        output_file.write_bytes(b"x" * 100)  # 过小文件

        mock_ae_client.send_command.return_value = {
            "success": True,
            "status": "success",
            "fileSize": 100,
        }

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            with patch("os.path.exists", return_value=True):
                with patch("os.path.getsize", return_value=100):
                    result = pipeline.execute(basic_planning)

        assert result.success is False
        assert "过小" in result.error_message


# ============================================================================
# P0-2: AE 参数查询命令测试
# ============================================================================

class TestAEPropertyQuery:
    """AE 端参数查询命令测试"""

    def test_real_mcp_client_import(self):
        """测试 RealMcpClient 可导入"""
        from result_verifier import RealMcpClient, McpClient
        assert issubclass(RealMcpClient, McpClient)

    def test_real_mcp_client_no_ae_client(self):
        """测试无 AE 客户端时返回 None"""
        import asyncio
        from result_verifier import RealMcpClient

        client = RealMcpClient(ae_client=None)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                client.get_effect_properties("test", 1)
            )
        finally:
            loop.close()
        assert result is None

    def test_real_mcp_client_with_mock_ae(self):
        """测试有 mock AE 客户端时正常回读"""
        import asyncio
        from result_verifier import RealMcpClient

        mock_ae = Mock()
        mock_ae.send_command.return_value = {
            "success": True,
            "status": "success",
            "properties": {
                "Blurriness": {"value": 10, "matchName": "ADBE Gaussian Blur 2"},
                "Repeat Edge Pixels": {"value": True, "matchName": ""},
            },
        }

        client = RealMcpClient(ae_client=mock_ae)
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                client.get_effect_properties("Comp1", 1, layer_name="Layer1", effect_name="Gaussian Blur")
            )
        finally:
            loop.close()

        assert result is not None
        assert len(result) == 2
        assert result[0].name == "Blurriness"
        assert result[0].value == 10

    def test_result_verifier_uses_real_mcp(self, pipeline):
        """测试 ResultVerifier 初始化时 RealMcpClient 可用"""
        assert hasattr(pipeline, "_result_verifier_mcp_class")
        assert pipeline._result_verifier_mcp_class is not None


# ============================================================================
# P0-3: Silhouette 失败降级测试
# ============================================================================

class TestSilhouetteFallback:
    """Silhouette 失败降级接线测试"""

    def test_fallback_returns_ae_ops(self, pipeline):
        """测试降级返回 AE 原生操作"""
        result = pipeline._silhouette_fallback(task_type="roto")

        assert result["status"] == "fallback"
        assert result["method"] == "ae_native_roto"
        assert "ae_fallback_ops" in result
        assert len(result["ae_fallback_ops"]) > 0
        assert result["ae_fallback_ops"][0]["matchName"] == "ADBE Mask"

    def test_fallback_track(self, pipeline):
        """测试 track 降级"""
        result = pipeline._silhouette_fallback(task_type="track")
        assert result["method"] == "ae_native_track"
        assert any(op["matchName"] == "ADBE Tracker" for op in result["ae_fallback_ops"])

    def test_fallback_paint(self, pipeline):
        """测试 paint 降级"""
        result = pipeline._silhouette_fallback(task_type="paint")
        assert result["method"] == "ae_native_paint"

    def test_fallback_ops_injected_to_planning(self, pipeline, basic_planning):
        """测试降级操作被注入 planning.effects"""
        basic_planning.silhouette_operations = [
            {"taskType": "roto", "source_path": "/path/clip.mp4"}
        ]

        # 模拟 silhouette 执行返回 fallback
        mock_sil_executor = Mock()
        mock_sil_executor.execute.return_value = {
            "status": "fallback",
            "method": "ae_native_roto",
            "message": "降级到 AE 原生 Mask",
            "ae_fallback_ops": [
                {"op": "addEffect", "matchName": "ADBE Mask", "effectName": "AE 原生遮罩", "settings": {}}
            ],
        }
        pipeline.silhouette_executor = mock_sil_executor

        with patch("ae_mcp_client.AECommandClient") as mock_ae:
            mock_ae.return_value.send_command.return_value = {"success": True, "status": "success"}
            mock_ae.return_value.clear_result = Mock()
            result = pipeline.execute(basic_planning)

        # 检查降级操作被注入 planning.effects
        fallback_effects = [e for e in basic_planning.effects if e.get("_fallback")]
        assert len(fallback_effects) > 0
        assert fallback_effects[0]["matchName"] == "ADBE Mask"


# ============================================================================
# P1-5: Silhouette 输出验证测试
# ============================================================================

class TestSilhouetteVerification:
    """Silhouette 产出验证测试"""

    def test_verify_silhouette_success(self, pipeline):
        """测试验证成功的 Silhouette 产出"""
        from result_verifier import ResultVerifier

        verifier = ResultVerifier()
        artifacts = [
            {"command": "silhouette_roto", "status": "success", "output_path": ""},
            {"command": "silhouette_track", "status": "success", "output_path": ""},
        ]

        result = verifier.verify_silhouette_output(artifacts)

        assert result.passed is True
        assert result.success_count == 2
        assert result.failure_count == 0

    def test_verify_silhouette_with_fallback(self, pipeline):
        """测试验证含降级的 Silhouette 产出"""
        from result_verifier import ResultVerifier

        verifier = ResultVerifier()
        artifacts = [
            {"command": "silhouette_roto", "status": "fallback", "message": "降级"},
            {"command": "silhouette_track", "status": "success"},
        ]

        result = verifier.verify_silhouette_output(artifacts)

        assert result.passed is True
        assert result.fallback_count == 1
        assert len(result.warnings) > 0

    def test_verify_silhouette_with_failure(self):
        """测试验证含失败的 Silhouette 产出"""
        from result_verifier import ResultVerifier

        verifier = ResultVerifier()
        artifacts = [
            {"command": "silhouette_roto", "status": "error", "error": "崩溃"},
        ]

        result = verifier.verify_silhouette_output(artifacts)

        assert result.passed is False
        assert result.failure_count == 1
        assert len(result.errors) > 0


# ============================================================================
# P1-6: Silhouette 学习循环测试
# ============================================================================

class TestSilhouetteLearningLoop:
    """Silhouette 执行数据进入 LearningLoop 测试"""

    def test_record_silhouette_success(self):
        """测试记录成功的 Silhouette 执行"""
        from learning_loop import LearningLoop

        loop = LearningLoop()
        record = loop.record_silhouette_execution(
            user_input="抠像这个视频",
            task_type="roto",
            params={"tolerance": 1.0, "keyframes": 5},
            success=True,
        )

        assert record.intent_type == "silhouette_roto"
        assert record.execution.success is True
        assert len(loop.get_execution_records()) > 0

    def test_record_silhouette_failure(self):
        """测试记录失败的 Silhouette 执行"""
        from learning_loop import LearningLoop

        loop = LearningLoop()
        record = loop.record_silhouette_execution(
            user_input="跟踪运动",
            task_type="track",
            params={"accuracy": "high"},
            success=False,
            error_message="Silhouette 崩溃",
        )

        assert record.execution.success is False
        assert "SIL" in record.execution.error_code

    def test_record_silhouette_fallback(self):
        """测试记录降级的 Silhouette 执行"""
        from learning_loop import LearningLoop

        loop = LearningLoop()
        record = loop.record_silhouette_execution(
            user_input="修复画面",
            task_type="paint",
            params={"brush_size": 25},
            success=True,
            fallback=True,
        )

        assert record.user_adjusted is True


# ============================================================================
# P1-4: HybridCoordinator 测试
# ============================================================================

class TestHybridCoordinator:
    """HybridCoordinator 修复验证测试"""

    def test_hybrid_coordinator_calls_executor(self):
        """测试 HybridCoordinator 真正调用 SilhouetteExecutor"""
        from hybrid_coordinator import HybridCoordinator, TaskRoute, ExecutionOptions

        route = TaskRoute(
            type="silhouette_only",
            ae_operations=[],
            silhouette_operations=[{"taskType": "roto"}],
            execution_order=["silhouette"],
            fallback={},
            reason="test",
            confidence=0.85,
        )
        options = ExecutionOptions(
            source_path="/path/clip.mp4",
            output_dir="/tmp/output",
        )

        coordinator = HybridCoordinator()

        with patch("silhouette_executor.SilhouetteExecutor") as MockExecutor:
            mock_instance = MockExecutor.return_value
            mock_instance.execute.return_value = {
                "status": "success",
                "ae_integration_data": {"type": "matte", "data": {}},
            }

            result = coordinator._execute_silhouette_phase(route, options)

        assert result.status == "success"
        mock_instance.execute.assert_called_once()

    def test_hybrid_coordinator_fallback_on_import_error(self):
        """测试 SilhouetteExecutor 不可用时降级"""
        from hybrid_coordinator import HybridCoordinator, TaskRoute, ExecutionOptions

        route = TaskRoute(
            type="silhouette_only",
            ae_operations=[],
            silhouette_operations=[{"taskType": "roto"}],
            execution_order=["silhouette"],
            fallback={},
            reason="test",
            confidence=0.85,
        )
        options = ExecutionOptions(
            source_path="/path/clip.mp4",
            output_dir="/tmp/output",
        )

        coordinator = HybridCoordinator()

        with patch("silhouette_executor.SilhouetteExecutor", side_effect=ImportError("No module")):
            result = coordinator._execute_silhouette_phase(route, options)

        assert result.status == "fallback"


# ============================================================================
# P2-7: 转场映射测试
# ============================================================================

class TestTransitionMap:
    """转场→AE 效果映射表测试"""

    def test_transition_map_import(self):
        """测试 transition_map 可导入"""
        from transition_map import TRANSITION_MAP, transition_to_ae_ops, get_all_transition_types
        assert len(TRANSITION_MAP) == 7

    def test_all_transition_types(self):
        """测试所有转场类型存在"""
        from transition_map import get_all_transition_types

        types = get_all_transition_types()
        assert "crossfade" in types
        assert "hard_cut" in types
        assert "dissolve" in types
        assert "wipe" in types
        assert "zoom_blur" in types
        assert "fade_to_black" in types
        assert "dreamy_dissolve" in types

    def test_crossfade_to_ops(self):
        """测试 crossfade 转场生成 AE 操作"""
        from transition_map import transition_to_ae_ops

        transition = {
            "type": "crossfade",
            "fromLayer": "Video1",
            "toLayer": "Video2",
            "startTime": 2.0,
            "duration": 0.5,
            "easeType": "easeInOut",
        }

        ops = transition_to_ae_ops(transition)
        assert len(ops) > 0
        # 应该包含关键帧操作
        assert any(op["op"] == "setKeyframe" for op in ops)

    def test_hard_cut_empty_ops(self):
        """测试 hard_cut 生成空操作"""
        from transition_map import transition_to_ae_ops

        transition = {
            "type": "hard_cut",
            "fromLayer": "Video1",
            "toLayer": "Video2",
            "startTime": 3.0,
            "duration": 0,
        }

        ops = transition_to_ae_ops(transition)
        assert len(ops) == 0


# ============================================================================
# P2-8: effect_name_map 接入测试
# ============================================================================

class TestEffectNameMapIntegration:
    """effect_name_map 接入 _create_effects 测试"""

    def test_effects_have_matchname(self, pipeline):
        """测试生成的效果包含 matchName 字段"""
        understanding = UnderstandingResult()
        understanding.style = "cinematic"
        understanding.nlu_intent_type = "ae_only"
        understanding.intent = "cinematic"
        understanding.keywords = ["电影感"]

        layers = [{"name": "Video1", "type": "footage", "startTime": 0, "duration": 5}]

        effects = pipeline._create_effects(understanding, layers)

        assert len(effects) > 0
        for effect in effects:
            assert "matchName" in effect
            # matchName 应该以 ADBE 开头或为空（如果映射表中没有）
            if effect["matchName"]:
                assert effect["matchName"].startswith("ADBE")


# ============================================================================
# P2-9: 编译器闲置能力测试
# ============================================================================

class TestCompilerOpsExpansion:
    """编译器闲置能力打通测试"""

    def test_set_expression_generator(self):
        """测试 setExpression 命令生成"""
        from ae_command_generator import AECommandGenerator

        gen = AECommandGenerator()
        cmd = gen.generate_set_expression("Layer1", "Transform.Opacity", "time*100", "Comp1")

        assert cmd[0]["op"] == "setExpression"
        assert cmd[0]["params"]["expression"] == "time*100"

    def test_set_blend_mode_generator(self):
        """测试 setBlendMode 命令生成"""
        from ae_command_generator import AECommandGenerator

        gen = AECommandGenerator()
        cmd = gen.generate_set_blend_mode("Layer1", "screen", "Comp1")

        assert cmd[0]["op"] == "setBlendMode"
        assert cmd[0]["params"]["blendMode"] == "screen"

    def test_set_parent_generator(self):
        """测试 setParent 命令生成"""
        from ae_command_generator import AECommandGenerator

        gen = AECommandGenerator()
        cmd = gen.generate_set_parent("Child", "Parent", "Comp1")

        assert cmd[0]["op"] == "setParent"
        assert cmd[0]["params"]["parentLayerName"] == "Parent"

    def test_set_track_matte_generator(self):
        """测试 setTrackMatte 命令生成"""
        from ae_command_generator import AECommandGenerator

        gen = AECommandGenerator()
        cmd = gen.generate_set_track_matte("Layer1", "MatteLayer", "alpha", "Comp1")

        assert cmd[0]["op"] == "setTrackMatte"
        assert cmd[0]["params"]["matteType"] == "alpha"

    def test_add_mask_generator(self):
        """测试 addMask 命令生成"""
        from ae_command_generator import AECommandGenerator

        gen = AECommandGenerator()
        cmd = gen.generate_add_mask("Layer1", "mask_path", "Comp1")

        assert cmd[0]["op"] == "addMask"


# ============================================================================
# 综合端到端测试
# ============================================================================

class TestEndToEndIntegration:
    """端到端集成测试"""

    def test_full_pipeline_with_ae_only(self, pipeline, mock_ae_client):
        """测试纯 AE 任务端到端流程"""
        planning = PlanningResult()
        planning.composition = {"name": "E2E_Comp", "width": 1920, "height": 1080, "duration": 5, "frameRate": 30}
        planning.layers = [{"name": "V1", "type": "footage", "source": "/v.mp4", "startTime": 0, "duration": 5}]
        planning.effects = [{"layerName": "V1", "effectName": "ADBE Glo2", "matchName": "ADBE Glo2", "settings": {}}]
        planning.keyframes = []
        planning.transitions = []
        planning.execution_order = ["createComposition"]
        planning.silhouette_operations = []
        planning.compiler_operations = []

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            result = pipeline.execute(planning)

        assert result.success is True
        assert result.steps_completed > 0

    def test_compiler_ops_to_commands_all_types(self, pipeline):
        """测试所有 compiler 操作类型的转换"""
        ops = [
            {"op": "createComp", "ref": "c1", "name": "Comp", "width": 1920, "height": 1080},
            {"op": "addLayer", "ref": "l1", "compRef": "c1", "layerType": "solid", "name": "Solid"},
            {"op": "addEffect", "ref": "e1", "compRef": "c1", "layerRef": "l1", "matchName": "ADBE Glo2", "effectName": "Glow"},
            {"op": "setProperty", "compRef": "c1", "layerRef": "l1", "propertyPath": "Opacity", "value": 80},
            {"op": "setKeyframe", "compRef": "c1", "layerRef": "l1", "propertyPath": "Scale", "keyframes": [{"time": 0, "value": 100}]},
        ]

        commands = pipeline._compiler_ops_to_commands(ops)

        assert len(commands) == 5
        assert commands[0]["op"] == "createComp"
        assert commands[1]["op"] == "addLayer"
        assert commands[2]["op"] == "addEffect"
        assert commands[3]["op"] == "setProperty"
        assert commands[4]["op"] == "setKeyframes"

    def test_silhouette_fallback_in_execute(self, pipeline, basic_planning, mock_ae_client):
        """测试 execute 中 silhouette 降级链路"""
        basic_planning.silhouette_operations = [
            {"taskType": "roto", "source_path": "/clip.mp4"}
        ]

        mock_sil = Mock()
        mock_sil.execute.return_value = {
            "status": "fallback",
            "method": "ae_native_roto",
            "message": "降级",
            "ae_fallback_ops": [
                {"op": "addEffect", "matchName": "ADBE Mask", "effectName": "遮罩", "settings": {}}
            ],
        }
        pipeline.silhouette_executor = mock_sil

        with patch("ae_mcp_client.AECommandClient", return_value=mock_ae_client):
            result = pipeline.execute(basic_planning)

        # 降级后应继续执行 AE 命令
        assert len(result.silhouette_artifacts) > 0
        assert result.silhouette_artifacts[0]["status"] == "fallback"

    def test_learning_loop_silhouette_integration(self, pipeline):
        """测试 Silhouette 数据进入 LearningLoop"""
        learning_loop = getattr(pipeline, "_learning_loop", None)
        if not learning_loop:
            pytest.skip("LearningLoop not available")

        initial_count = len(learning_loop.get_execution_records())

        # 记录一条 silhouette 执行
        learning_loop.record_silhouette_execution(
            user_input="抠像",
            task_type="roto",
            params={"tolerance": 1.0},
            success=True,
        )

        new_count = len(learning_loop.get_execution_records())
        assert new_count == initial_count + 1
