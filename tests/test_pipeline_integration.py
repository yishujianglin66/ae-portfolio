"""
test_pipeline_integration.py
验证 Python 端 Pipeline 集成测试

测试范围：
  1. NLUParser.parse_enhanced 集成
  2. ParameterOptimizer.optimize_enhanced
  3. effect_knowledge_graph.search_effects_enhanced
  4. effect_knowledge_graph.recommend_style_enhanced
  5. AEAgentPipeline._enhance_with_nlu_parser 集成
"""
import sys
import os

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


def test_nlu_parse_enhanced():
    """测试 NLUParser.parse_enhanced"""
    print("\n[Test] NLUParser.parse_enhanced")
    from nlu_parser import NLUParser, IntentType

    parser = NLUParser()

    # 1. 基本解析
    intent = parser.parse_enhanced("给文字加一个发光")
    assert_cond(intent is not None, "应返回 Intent 对象")
    assert_cond(intent.type == IntentType.ADD_EFFECT, f"意图应为 ADD_EFFECT, 实际 {intent.type}")
    assert_cond(intent.confidence > 0, "置信度应大于 0")

    # 2. 不同意图类型
    intent2 = parser.parse_enhanced("做一个赛博朋克风格")
    assert_cond(intent2 is not None, "风格类输入应返回 Intent")

    # 3. 空输入降级
    intent3 = parser.parse_enhanced("")
    assert_cond(intent3 is not None, "空输入应返回 Intent（降级）")
    assert_cond(intent3.type == IntentType.UNKNOWN, f"空输入意图应为 UNKNOWN, 实际 {intent3.type}")


def test_parameter_optimizer_enhanced():
    """测试 ParameterOptimizer.optimize_enhanced"""
    print("\n[Test] ParameterOptimizer.optimize_enhanced")
    from parameter_optimizer import ParameterOptimizer, ParameterContext

    optimizer = ParameterOptimizer()

    # 1. 基本优化
    ctx = ParameterContext(
        effect_name="发光",
        intensity=0.7,
        style_name="cyberpunk",
    )
    result = optimizer.optimize_enhanced(ctx)
    assert_cond(result is not None, "应返回 OptimizedParameters")
    assert_cond(result.effect_name != "", "应包含 effect_name")
    assert_cond(isinstance(result.settings, dict), "应包含 settings 字典")
    assert_cond(result.confidence > 0, "置信度应大于 0")

    # 2. 无效果名降级
    ctx2 = ParameterContext(intensity=0.5)
    result2 = optimizer.optimize_enhanced(ctx2)
    assert_cond(result2 is not None, "无效果名应返回结果（降级）")

    # 3. 与同步版一致性（LLM 不可用时应一致）
    result_sync = optimizer.optimize(ctx)
    assert_cond(result_sync.effect_name == result.effect_name, "LLM 不可用时 effect_name 应一致")


def test_effect_knowledge_graph_enhanced():
    """测试 effect_knowledge_graph 增强版"""
    print("\n[Test] effect_knowledge_graph.search_effects_enhanced")
    from effect_knowledge_graph import (
        search_effects_enhanced,
        recommend_style_enhanced,
        search_effects,
        get_effect_count,
    )

    # 1. 效果计数
    count = get_effect_count()
    assert_cond(count > 0, f"效果数应大于 0, 实际 {count}")

    # 2. 增强搜索（英文）
    results = search_effects_enhanced("glow")
    assert_cond(isinstance(results, list), "应返回列表")
    assert_cond(len(results) > 0, f"应找到 glow 相关效果, 实际 {len(results)}")

    # 3. 增强搜索（中文）
    results2 = search_effects_enhanced("模糊")
    assert_cond(isinstance(results2, list), "中文搜索应返回列表")

    # 4. 与同步版一致性（LLM 不可用时应一致）
    sync_results = search_effects("glow")
    assert_cond(len(sync_results) <= len(results), "增强版结果应不少于同步版")

    # 5. recommend_style_enhanced（LLM 不可用返回 None 是正常降级）
    print("\n[Test] effect_knowledge_graph.recommend_style_enhanced")
    style = recommend_style_enhanced("赛博朋克")
    assert_cond(style is None or hasattr(style, "name"), "应返回 StyleRecipe 或 None（降级）")


def test_pipeline_understand_integration():
    """测试 AEAgentPipeline._enhance_with_nlu_parser 集成"""
    print("\n[Test] AEAgentPipeline._enhance_with_nlu_parser 集成")
    import logging
    from ae_agent_pipeline import AEAgentPipeline, UnderstandingResult

    # 使用 __new__ 创建实例（与 e2e 测试一致）
    pipe = AEAgentPipeline.__new__(AEAgentPipeline)
    pipe._observability = None
    pipe._logger = logging.getLogger("test_pipeline")

    # 1. nlu_parser 未初始化时应安全降级
    understanding = UnderstandingResult()
    pipe._enhance_with_nlu_parser(understanding, "给文字加一个发光")
    assert_cond(understanding.nlu_intent_type == "", "nlu_parser 未初始化时应安全降级，nlu_intent_type 为空")

    # 2. 初始化 nlu_parser 后应正常工作
    try:
        from nlu_parser import NLUParser
        pipe.nlu_parser = NLUParser()
    except ImportError:
        assert_cond(False, "NLUParser 导入失败")
        return

    understanding2 = UnderstandingResult()
    pipe._enhance_with_nlu_parser(understanding2, "给文字加一个发光")
    assert_cond(understanding2.nlu_intent_type != "", "应填充 nlu_intent_type")
    assert_cond(understanding2.nlu_confidence > 0, "nlu_confidence 应大于 0")

    # 3. 空输入应安全处理
    understanding3 = UnderstandingResult()
    pipe._enhance_with_nlu_parser(understanding3, "")
    assert_cond(understanding3.nlu_intent_type == "", "空输入应安全处理")

    # 4. 精细意图反哺粗粒度 intent
    understanding4 = UnderstandingResult(intent="")
    pipe._enhance_with_nlu_parser(understanding4, "加一个发光效果")
    assert_cond(
        understanding4.intent == "video_editing" or understanding4.intent != "",
        "ADD_EFFECT 应反哺粗粒度 intent"
    )


def test_understanding_result_fields():
    """测试 UnderstandingResult 新增字段"""
    print("\n[Test] UnderstandingResult 新增 NLU 字段")
    from ae_agent_pipeline import UnderstandingResult

    result = UnderstandingResult()
    assert_cond(hasattr(result, "nlu_intent_type"), "应有 nlu_intent_type 字段")
    assert_cond(hasattr(result, "nlu_confidence"), "应有 nlu_confidence 字段")
    assert_cond(hasattr(result, "nlu_slots"), "应有 nlu_slots 字段")
    assert_cond(hasattr(result, "nlu_matched_pattern"), "应有 nlu_matched_pattern 字段")
    assert_cond(result.nlu_intent_type == "", "nlu_intent_type 默认应为空字符串")
    assert_cond(result.nlu_confidence == 0.0, "nlu_confidence 默认应为 0.0")
    assert_cond(isinstance(result.nlu_slots, dict), "nlu_slots 默认应为 dict")
    assert_cond(result.nlu_slots == {}, "nlu_slots 默认应为空 dict")


def main():
    print("=== Python Pipeline 集成测试 ===")

    tests = [
        test_nlu_parse_enhanced,
        test_parameter_optimizer_enhanced,
        test_effect_knowledge_graph_enhanced,
        test_pipeline_understand_integration,
        test_understanding_result_fields,
    ]

    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"  [ERROR] {test.__name__} 异常: {e}")
            global failed
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
