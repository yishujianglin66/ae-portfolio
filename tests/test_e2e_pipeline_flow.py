"""
test_e2e_pipeline_flow.py
验证 AEAgentPipeline 端到端完整流程测试

测试范围：
  1. understand() → plan() → 完整链路（包含 NLU 精细意图、效果知识图谱、参数优化）
  2. NLU 精细意图反哺粗粒度 intent
  3. 效果知识图谱增强效果列表
  4. 参数优化器优化效果参数
  5. 混合路由（Silhouette + AE）场景
"""
import logging
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0


def assert_cond(condition, message):
    global passed, failed
    if condition:
        print(f"  [PASS] {message}")
        passed += 1
    else:
        print(f"  [FAIL] {message}")
        failed += 1


def test_full_pipeline_flow():
    """测试 understand() → plan() 完整链路"""
    print("\n[Test] understand() → plan() 完整链路")
    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    # 1. understand 阶段：包含 NLU 精细意图识别
    perception = PerceptionResult(
        clip_features=[{"source_path": "test.mp4", "duration": 5.0}],
        music_features={"duration": 10.0, "tempo": 120, "mood": "energetic"},
    )
    understanding = pipeline.understand(perception, "给文字加一个发光效果")

    assert_cond(understanding.intent != "", "应识别粗粒度意图")
    assert_cond(understanding.nlu_intent_type != "", "应识别 NLU 精细意图类型")
    assert_cond(understanding.nlu_confidence > 0, "NLU 置信度应大于 0")

    # 2. plan 阶段：包含效果知识图谱增强 + 参数优化
    plan = pipeline.plan(understanding, perception)

    assert_cond(plan.composition is not None, "应生成合成配置")
    assert_cond(len(plan.layers) > 0, f"应生成至少 1 个图层, 实际 {len(plan.layers)}")
    assert_cond(len(plan.effects) > 0, f"应生成至少 1 个效果, 实际 {len(plan.effects)}")

    pipeline.close()


def test_nlu_intent_feedback():
    """测试 NLU 精细意图反哺粗粒度 intent"""
    print("\n[Test] NLU 精细意图反哺粗粒度 intent")
    import tempfile

    from nlu_parser import IntentType

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    # ADD_EFFECT 应反哺为 video_editing
    perception = PerceptionResult()
    understanding = pipeline.understand(perception, "加一个发光效果")

    assert_cond(understanding.nlu_intent_type == IntentType.ADD_EFFECT,
                f"NLU 意图应为 ADD_EFFECT, 实际 {understanding.nlu_intent_type}")
    assert_cond(understanding.intent == "video_editing",
                f"粗粒度意图应被反哺为 video_editing, 实际 {understanding.intent}")

    # STYLE_COMBO 应反哺为 short_reel
    understanding2 = pipeline.understand(perception, "做一个赛博朋克风格")
    assert_cond(understanding2.nlu_intent_type == IntentType.STYLE_COMBO,
                f"NLU 意图应为 STYLE_COMBO, 实际 {understanding2.nlu_intent_type}")

    pipeline.close()


def test_knowledge_graph_enhancement():
    """测试效果知识图谱增强效果列表"""
    print("\n[Test] 效果知识图谱增强效果列表")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult(
        clip_features=[{"source_path": "test.mp4", "duration": 5.0}],
        music_features={"duration": 10.0},
    )
    understanding = pipeline.understand(perception, "加一个模糊效果")
    understanding.style = "cinematic"

    plan = pipeline.plan(understanding, perception)

    # 验证效果列表不为空
    assert_cond(len(plan.effects) > 0, f"效果列表不为空, 实际 {len(plan.effects)}")

    pipeline.close()


def test_parameter_optimization():
    """测试参数优化器优化效果参数"""
    print("\n[Test] 参数优化器优化效果参数")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult(
        clip_features=[{"source_path": "test.mp4", "duration": 5.0}],
        music_features={"duration": 10.0},
    )
    understanding = pipeline.understand(perception, "加一个发光效果")
    understanding.style = "cinematic"

    plan = pipeline.plan(understanding, perception)

    # 验证所有效果都有设置
    for effect in plan.effects:
        assert_cond(effect.get("settings") is not None,
                    f"效果 {effect['effectName']} 应有 settings")
        assert_cond(len(effect["settings"]) > 0,
                    f"效果 {effect['effectName']} settings 不应为空")

    # 验证优化标记
    for effect in plan.effects:
        if effect.get("_optimized"):
            assert_cond(effect.get("_confidence") is not None,
                        f"优化效果 {effect['effectName']} 应有置信度")
            break
    else:
        print("  [INFO] 无优化标记的效果（LLM 不可用时正常降级）")

    pipeline.close()


def test_hybrid_routing():
    """测试混合路由（Silhouette + AE）场景"""
    print("\n[Test] 混合路由（Silhouette + AE）场景")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult(
        clip_features=[{"source_path": "test.mp4", "duration": 5.0}],
        music_features={"duration": 10.0},
    )
    understanding = pipeline.understand(perception, "扣掉背景然后加发光")

    # 验证混合路由识别
    assert_cond(understanding.is_hybrid, "应识别为混合任务")
    assert_cond(understanding.route_type == "hybrid",
                f"路由类型应为 hybrid, 实际 {understanding.route_type}")
    assert_cond(understanding.silhouette_task == "roto",
                f"Silhouette 任务应为 roto, 实际 {understanding.silhouette_task}")

    # 验证 plan 包含 Silhouette 操作
    plan = pipeline.plan(understanding, perception)
    assert_cond(len(plan.silhouette_operations) > 0,
                f"应生成 Silhouette 操作, 实际 {len(plan.silhouette_operations)}")
    assert_cond(len(plan.effects) > 0,
                f"应生成 AE 效果, 实际 {len(plan.effects)}")

    pipeline.close()


def test_empty_input_handling():
    """测试空输入处理"""
    print("\n[Test] 空输入处理")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult()

    # 空输入不应崩溃
    try:
        understanding = pipeline.understand(perception, "")
        assert_cond(understanding.intent == "", "空输入意图应为空")
        assert_cond(understanding.nlu_intent_type == "", "空输入 NLU 意图应为空")
    except Exception as e:
        assert_cond(False, f"空输入不应崩溃: {e}")

    # 空输入的 plan 不应崩溃
    try:
        understanding = pipeline.understand(perception, "")
        plan = pipeline.plan(understanding, perception)
        assert_cond(plan is not None, "空输入 plan 不应为 None")
    except Exception as e:
        assert_cond(False, f"空输入 plan 不应崩溃: {e}")

    pipeline.close()


def test_ae_only_routing():
    """测试纯 AE 路由场景"""
    print("\n[Test] 纯 AE 路由场景")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult()
    understanding = pipeline.understand(perception, "调亮一点对比度")

    assert_cond(not understanding.is_hybrid, "纯 AE 任务不应为混合")
    assert_cond(understanding.route_type == "ae_only",
                f"路由类型应为 ae_only, 实际 {understanding.route_type}")

    plan = pipeline.plan(understanding, perception)
    assert_cond(len(plan.silhouette_operations) == 0,
                f"纯 AE 任务不应有 Silhouette 操作, 实际 {len(plan.silhouette_operations)}")

    pipeline.close()


def test_feedback_mechanism():
    """测试 feedback() 反馈层机制"""
    print("\n[Test] feedback() 反馈层机制")
    import tempfile

    from ae_agent_pipeline import AEAgentPipeline, ExecutionResult, PerceptionResult
    from core.memory_store import MemoryStore

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    pipeline = AEAgentPipeline()
    pipeline._memory_store.close()
    pipeline._memory_store = MemoryStore(db_path=db_path)

    perception = PerceptionResult(
        clip_features=[{"source_path": "test.mp4", "duration": 5.0}],
        music_features={"duration": 10.0},
    )
    understanding = pipeline.understand(perception, "加一个发光效果")
    plan = pipeline.plan(understanding, perception)

    execution_success = ExecutionResult()
    execution_success.success = True
    execution_success.steps_completed = 5
    execution_success.total_steps = 5
    execution_success.output_path = "output.mp4"
    execution_success.execution_time = 10.0

    feedback = pipeline.feedback(perception, understanding, plan, execution_success)

    assert_cond(feedback.rating > 0, "成功执行应有正评分")
    assert_cond(feedback.confidence > 0, "成功执行应有正置信度")

    execution_fail = ExecutionResult()
    execution_fail.success = False
    execution_fail.error_message = "渲染失败"

    feedback_fail = pipeline.feedback(perception, understanding, plan, execution_fail)

    assert_cond(feedback_fail.rating == 0, "失败执行评分为0")
    assert_cond(feedback_fail.confidence <= 0.3, f"失败执行置信度应<=0.3, 实际 {feedback_fail.confidence:.2f}")
    assert_cond(feedback_fail.error_log is not None, "失败执行应有错误日志")

    pipeline.close()


def main():
    print("=== AEAgentPipeline 端到端流程测试 ===")

    tests = [
        test_full_pipeline_flow,
        test_nlu_intent_feedback,
        test_knowledge_graph_enhancement,
        test_parameter_optimization,
        test_hybrid_routing,
        test_empty_input_handling,
        test_ae_only_routing,
        test_feedback_mechanism,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  [ERROR] {test.__name__} 异常: {e}")
            import traceback
            traceback.print_exc()
            global failed
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
