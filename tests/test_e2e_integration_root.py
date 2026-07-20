#!/usr/bin/env python3
"""
端到端集成测试 - IntentRouter + HybridCoordinator + 数据流 + 错误处理

覆盖范围：
  1. IntentRouter 路由决策（AE/Silhouette/Hybrid）
  2. HybridCoordinator 混合任务协调
  3. Silhouette 输出 → AE 自动导入数据流
  4. 重试、降级、回滚错误处理
  5. Pipeline 全链路集成
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(__file__))

from intent_router import IntentRouter, TaskRoute
from hybrid_coordinator import (
    HybridCoordinator, ExecutionOptions, PhaseResult, HybridExecutionResult,
)


# ===========================================================================
# 1. IntentRouter 路由决策测试
# ===========================================================================

class TestIntentRouter:
    """IntentRouter 路由决策"""

    @pytest.fixture
    def router(self):
        return IntentRouter()

    def test_ae_only_route(self, router):
        r = router.route("加个模糊效果")
        assert r.type == "ae_only"
        assert r.confidence > 0.5
        assert len(r.ae_operations) > 0

    def test_silhouette_only_roto(self, router):
        r = router.route("扣个人像")
        assert r.type == "silhouette_only"
        assert len(r.silhouette_operations) > 0
        assert r.fallback is not None

    def test_silhouette_only_track(self, router):
        r = router.route("跟踪这个物体")
        assert r.type == "silhouette_only"

    def test_silhouette_only_paint(self, router):
        r = router.route("修掉水印")
        assert r.type == "silhouette_only"

    def test_hybrid_route(self, router):
        r = router.route("扣人像然后加发光")
        assert r.type == "hybrid"
        assert len(r.silhouette_operations) > 0
        assert len(r.ae_operations) > 0
        assert r.execution_order == ["silhouette", "ae"]
        assert r.fallback is not None

    def test_hybrid_track_and_anim(self, router):
        r = router.route("跟踪物体然后做动画")
        assert r.type == "hybrid"

    def test_hybrid_paint_and_noise(self, router):
        r = router.route("修复画面然后加噪波")
        assert r.type == "hybrid"

    def test_unknown_empty(self, router):
        r = router.route("")
        assert r.type == "unknown"
        assert r.confidence < 0.5

    def test_is_hybrid(self, router):
        assert router.is_hybrid("扣人然后加发光") is True
        assert router.is_hybrid("加个模糊") is False
        assert router.is_hybrid("扣个人") is False

    def test_split_hybrid_input(self, router):
        result = router.split_hybrid_input("扣人像然后加发光")
        assert result is not None
        assert "silhouette_part" in result
        assert "ae_part" in result

    def test_fallback_strategy(self, router):
        r = router.route("扣个人像")
        assert r.fallback is not None
        assert "aeFallbackOps" in r.fallback or "ae_fallback_ops" in r.fallback


# ===========================================================================
# 2. HybridCoordinator 混合协调测试
# ===========================================================================

class TestHybridCoordinator:
    """HybridCoordinator 混合任务协调"""

    @pytest.fixture
    def coordinator(self):
        return HybridCoordinator(intent_router=IntentRouter())

    def test_execute_ae_only(self, coordinator):
        result = coordinator.execute("加个模糊效果")
        assert result.status in ("success", "error")
        assert len(result.phases) >= 1

    def test_execute_hybrid(self, coordinator):
        result = coordinator.execute("扣人像然后加发光")
        assert result.status in ("success", "error", "fallback")
        assert len(result.phases) >= 1

    def test_execute_unknown(self, coordinator):
        result = coordinator.execute("")
        assert result.status == "error"

    def test_execution_options(self, coordinator):
        opts = ExecutionOptions(
            source_path="test.mp4",
            output_dir="./output",
            enable_fallback=True,
            max_retries=2,
            retry_delay_ms=500,
        )
        result = coordinator.execute("扣人然后加发光", options=opts)
        assert result.total_duration_ms >= 0


# ===========================================================================
# 3. 数据流打通测试（Silhouette → AE）
# ===========================================================================

class TestDataFlow:
    """Silhouette 输出 → AE 自动导入数据流"""

    @pytest.fixture
    def pipeline(self):
        from ae_agent_pipeline import AEAgentPipeline, PlanningResult
        p = AEAgentPipeline()
        return p

    def test_apply_roto_matte(self, pipeline):
        from ae_agent_pipeline import PlanningResult
        plan = PlanningResult(
            composition={"name": "test", "duration": 5, "fps": 30},
            layers=[
                {"name": "main", "type": "footage", "startTime": 0,
                 "duration": 5},
            ],
            keyframes=[],
        )
        sil_output = {
            "source": "silhouette",
            "roto": {
                "matteSequence": "D:/output/matte_[####].exr",
                "shapeType": "x-spline",
                "frameRange": [0, 150],
                "resolution": [1920, 1080],
            },
            "aeIntegration": {
                "compName": "test",
                "importPath": "D:/output/",
                "applyAs": "track_matte",
                "targetLayer": "main",
                "matteMode": "alpha",
            },
        }
        result = pipeline._apply_silhouette_to_ae(sil_output, plan)
        # 应添加 Matte 层
        assert any(l.get("name") == "Silhouette_Matte" for l in result.layers)
        # 主体层应设置 Track Matte
        main_layer = [l for l in result.layers if l.get("name") == "main"][0]
        assert main_layer.get("trackMatteType") == "alpha"

    def test_apply_tracking_data(self, pipeline):
        from ae_agent_pipeline import PlanningResult
        plan = PlanningResult(
            composition={"name": "test", "duration": 5, "fps": 30},
            layers=[
                {"name": "main", "type": "footage", "startTime": 0,
                 "duration": 5},
            ],
            keyframes=[],
        )
        sil_output = {
            "source": "silhouette",
            "tracking": {
                "trackers": [{
                    "name": "Tracker1",
                    "type": "planar",
                    "keyframes": [
                        {"frame": 0, "position": [100, 200]},
                        {"frame": 30, "position": [150, 250]},
                    ],
                }],
                "exportFormat": "ae_keyframes",
                "nullObjectName": "Silhouette_Tracker",
            },
            "aeIntegration": {
                "compName": "test",
                "importPath": "D:/output/",
                "applyAs": "tracking_data",
            },
        }
        result = pipeline._apply_silhouette_to_ae(sil_output, plan)
        assert len(result.keyframes) == 2
        assert result.keyframes[0]["layerName"] == "Silhouette_Tracker"

    def test_apply_paint_data(self, pipeline):
        from ae_agent_pipeline import PlanningResult
        plan = PlanningResult(
            composition={"name": "test", "duration": 5, "fps": 30},
            layers=[
                {"name": "main", "type": "footage", "startTime": 0,
                 "duration": 5},
            ],
            keyframes=[],
        )
        sil_output = {
            "source": "silhouette",
            "paint": {
                "paintedFrames": "D:/output/paint_[####].png",
                "paintMode": "clone",
            },
            "aeIntegration": {
                "compName": "test",
                "importPath": "D:/output/",
                "applyAs": "replace_frames",
            },
        }
        result = pipeline._apply_silhouette_to_ae(sil_output, plan)
        assert any(l.get("name") == "Silhouette_Paint" for l in result.layers)

    def test_no_silhouette_output(self, pipeline):
        from ae_agent_pipeline import PlanningResult
        plan = PlanningResult(
            composition={"name": "test", "duration": 5, "fps": 30},
            layers=[],
            keyframes=[],
        )
        result = pipeline._apply_silhouette_to_ae(None, plan)
        assert len(result.layers) == 0

        result2 = pipeline._apply_silhouette_to_ae({}, plan)
        assert len(result2.layers) == 0


# ===========================================================================
# 4. 错误处理测试（重试、降级、回滚）
# ===========================================================================

class TestErrorHandling:
    """重试、降级、回滚机制"""

    @pytest.fixture
    def pipeline(self):
        from ae_agent_pipeline import AEAgentPipeline
        return AEAgentPipeline()

    def test_retry_success_on_second_attempt(self, pipeline):
        call_count = {"n": 0}

        def flaky_fn():
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"status": "error", "error": "temporary"}
            return {"status": "success"}

        result = pipeline._execute_with_retry(flaky_fn, max_retries=3, retry_delay=0.01)
        assert result.get("status") == "success"
        assert call_count["n"] == 2

    def test_retry_exhausted_fallback(self, pipeline):
        def always_fail():
            return {"status": "error", "error": "persistent"}

        result = pipeline._execute_with_retry(always_fail, max_retries=2, retry_delay=0.01)
        assert result.get("status") == "fallback"

    def test_fallback_returns_ae_native(self, pipeline):
        result = pipeline._execute_fallback("test error")
        assert result["status"] == "fallback"
        assert result["method"] == "ae_native"

    def test_exception_in_fn_triggers_retry(self, pipeline):
        call_count = {"n": 0}

        def throwing_fn():
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise RuntimeError("crash")
            return {"status": "success"}

        result = pipeline._execute_with_retry(throwing_fn, max_retries=3, retry_delay=0.01)
        assert result.get("status") == "success"

    def test_hybrid_flow_fallback_when_coordinator_missing(self, pipeline):
        from ae_agent_pipeline import PlanningResult
        pipeline.hybrid_coordinator = None
        plan = PlanningResult(
            silhouette_operations=[
                {"command": "silhouette_roto", "params": {}},
            ],
        )
        result = pipeline._execute_hybrid_flow(plan, "test")
        assert result.get("status") == "fallback"


# ===========================================================================
# 5. Pipeline 全链路集成测试
# ===========================================================================

class TestPipelineIntegration:
    """Pipeline 全链路集成"""

    @pytest.fixture
    def pipeline(self):
        from ae_agent_pipeline import AEAgentPipeline
        return AEAgentPipeline()

    def test_intent_router_integrated(self, pipeline):
        from ae_agent_pipeline import UnderstandingResult
        u = UnderstandingResult()
        pipeline._detect_silhouette_intent(u, "扣人像然后加发光")
        assert u.route_type == "hybrid"
        assert u.is_hybrid is True
        assert u.silhouette_task == "roto"

    def test_intent_router_ae_only(self, pipeline):
        from ae_agent_pipeline import UnderstandingResult
        u = UnderstandingResult()
        pipeline._detect_silhouette_intent(u, "加个模糊效果")
        assert u.route_type == "ae_only"

    def test_intent_router_silhouette_only(self, pipeline):
        from ae_agent_pipeline import UnderstandingResult
        u = UnderstandingResult()
        pipeline._detect_silhouette_intent(u, "扣掉背景")
        assert u.route_type == "silhouette_only"

    def test_beat_orchestrator_active(self, pipeline):
        assert pipeline.beat_orchestrator is not None

    def test_effect_composition_engine_active(self, pipeline):
        assert pipeline.effect_composition_engine is not None

    def test_silhouette_mode_configurable(self, pipeline):
        pipeline.set_silhouette_mode("simulate")
        assert pipeline.silhouette_executor.mode == "simulate"

    def test_state_machine_sub_states(self, pipeline):
        sm = pipeline._state_machine
        assert sm is not None
        # Silhouette 子状态
        sm.silhouette_start()
        sm.silhouette_routed()
        sm.silhouette_start_process()
        sm.silhouette_done()
        # AE 子状态
        sm.ae_compile()
        sm.ae_compiled()
        sm.ae_executed()
        sm.ae_rendered()

    def test_full_understand_plan_flow(self, pipeline):
        from ae_agent_pipeline import UnderstandingResult, PerceptionResult
        perception = PerceptionResult(
            music_features={
                "bpm": 128, "fps": 30, "duration": 10,
                "beats": [0.5, 1.0, 1.5], "downbeats": [0.5],
                "energy_curve": {"peaks": []}, "segments": [],
            }
        )
        understanding = UnderstandingResult(
            intent="music_video",
            style="fast_cut",
            duration=10,
            effect_keywords=["glow"],
            route_type="ae_only",
        )
        plan = pipeline.plan(understanding, perception)
        assert len(plan.layers) > 0 or len(plan.effects) > 0 or len(plan.keyframes) > 0
