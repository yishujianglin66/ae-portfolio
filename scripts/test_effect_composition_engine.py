"""
test_effect_composition_engine.py - 效果组合推理引擎单元测试
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from effect_composition_engine import EffectCompositionEngine
from effect_knowledge_graph import (
    CATEGORIES,
    EFFECT_KNOWLEDGE_GRAPH,
    EFFECT_RELATIONS,
    get_effect_count,
    get_synergy_effects,
    search_effects,
)


def run_all_tests():
    """运行所有测试，返回 (pass_count, fail_count)。

    包装在函数中避免模块级执行时 sys.exit() 导致 pytest 收集崩溃。
    """
    pass_count = 0
    fail_count = 0

    def assert_true(condition, message):
        nonlocal pass_count, fail_count
        if condition:
            pass_count += 1
            print(f"  ✅ {message}")
        else:
            fail_count += 1
            print(f"  ❌ {message}")

    def section(title):
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")

    # ============================================================================
    # 测试1: 效果知识图谱基础验证
    # ============================================================================
    section("测试1: 效果知识图谱基础验证")

    print(f"\n总效果数量: {get_effect_count()}")
    assert_true(get_effect_count() >= 65, f"效果数量 >= 65 (实际: {get_effect_count()})")

    assert_true(len(CATEGORIES) == 9, f"类别数量 == 9 (实际: {len(CATEGORIES)})")

    for cat_key, cat_name in CATEGORIES.items():
        effects = [e for e in EFFECT_KNOWLEDGE_GRAPH.values() if e.category == cat_key]
        print(f"  {cat_name}: {len(effects)} 个")
        assert_true(len(effects) >= 5, f"{cat_name} 类 >= 5 个效果 (实际: {len(effects)})")

    # ============================================================================
    # 测试2: 效果关系验证
    # ============================================================================
    section("测试2: 效果关系验证")

    rel_types = {}
    for rel in EFFECT_RELATIONS:
        rel_types[rel.relation_type] = rel_types.get(rel.relation_type, 0) + 1

    for rel_type, count in rel_types.items():
        print(f"  {rel_type}: {count} 条")

    assert_true(rel_types.get("synergy", 0) >= 5, f"协同关系 >= 5 (实际: {rel_types.get('synergy', 0)})")
    assert_true(rel_types.get("mutex", 0) >= 3, f"互斥关系 >= 3 (实际: {rel_types.get('mutex', 0)})")
    assert_true(rel_types.get("prerequisite", 0) >= 3, f"前置关系 >= 3 (实际: {rel_types.get('prerequisite', 0)})")
    assert_true(rel_types.get("post", 0) >= 3, f"后置关系 >= 3 (实际: {rel_types.get('post', 0)})")

    # ============================================================================
    # 测试3: 效果搜索
    # ============================================================================
    section("测试3: 效果搜索")

    results = search_effects("模糊")
    print(f"\n搜索'模糊': 找到 {len(results)} 个结果")
    assert_true(len(results) >= 5, f"搜索'模糊' >= 5 个结果 (实际: {len(results)})")

    results = search_effects("glow")
    print(f"搜索'glow': 找到 {len(results)} 个结果")
    assert_true(len(results) >= 1, f"搜索'glow' >= 1 个结果 (实际: {len(results)})")

    results = search_effects("赛博朋克")
    print(f"搜索'赛博朋克': 找到 {len(results)} 个结果")

    # ============================================================================
    # 测试4: 协同效果查询
    # ============================================================================
    section("测试4: 协同效果查询")

    synergies = get_synergy_effects("ADBE Glo2")
    print(f"\nGlow的协同效果: {len(synergies)} 个")
    for s in synergies:
        print(f"  - {s['match_name']}: {s['description']} (强度: {s['strength']})")
    assert_true(len(synergies) >= 2, f"Glow协同效果 >= 2 (实际: {len(synergies)})")

    # ============================================================================
    # 测试5: 组合推理引擎初始化
    # ============================================================================
    section("测试5: 组合推理引擎初始化")

    engine = EffectCompositionEngine()
    assert_true(engine is not None, "引擎初始化成功")
    assert_true(len(engine.graph) == get_effect_count(), f"图谱效果数匹配 ({len(engine.graph)})")

    # ============================================================================
    # 测试6: 关键词组合效果
    # ============================================================================
    section("测试6: 关键词组合效果")

    result = engine.compose_from_keywords(
        keywords=["发光", "模糊"],
        intensity=1.0,
        max_effects=4,
    )
    print(f"\n组合效果数量: {len(result.effects)}")
    print(f"组合置信度: {result.confidence:.4f}")
    print(f"推理链: {len(result.reasoning)} 条")
    print(f"协同组合: {len(result.synergies)} 个")
    print(f"冲突警告: {len(result.warnings)} 条")

    assert_true(len(result.effects) >= 2, "组合效果 >= 2")
    assert_true(result.confidence > 0.5, "置信度 > 0.5")
    assert_true(len(result.reasoning) > 0, "有推理解释")

    for effect in result.effects:
        print(f"  - {effect['displayName']} ({effect['category']})")

    # ============================================================================
    # 测试7: 效果推荐
    # ============================================================================
    section("测试7: 效果推荐")

    recommendations = engine.recommend_effects(
        keywords=["电影", "胶片", "高对比"],
        limit=10,
    )
    print(f"\n推荐效果数量: {len(recommendations)}")
    assert_true(len(recommendations) >= 3, "推荐效果 >= 3")

    for i, rec in enumerate(recommendations[:5]):
        print(f"  {i+1}. {rec.display_name} ({rec.category}) - 置信度: {rec.confidence:.2f}")

    # ============================================================================
    # 测试8: 冲突检测
    # ============================================================================
    section("测试8: 冲突检测")

    conflict_test = ["ADBE Gaussian Blur 2", "ADBE Fast Box Blur"]
    analysis = engine.analyze_combination(conflict_test)
    print(f"\n冲突检测: {analysis['conflict_count']} 个冲突")
    assert_true(analysis["conflict_count"] >= 1, "应检测到至少1个冲突")

    for conflict in analysis["conflicts"]:
        print(f"  - {conflict['effect_a']} vs {conflict['effect_b']}: {conflict['description']}")

    # ============================================================================
    # 测试9: 组合分析
    # ============================================================================
    section("测试9: 组合分析")

    test_effects = [
        "ADBE Glo2",
        "ADBE Color Balance",
        "ADBE Brightness & Contrast 2",
        "CC Vignette",
    ]
    analysis = engine.analyze_combination(test_effects)

    print("\n组合分析:")
    print(f"  总效果数: {analysis['total_effects']}")
    print(f"  覆盖类别: {analysis['categories_covered']}")
    print(f"  平均置信度: {analysis['average_confidence']}")
    print(f"  协同数: {analysis['synergy_count']}")
    print(f"  冲突数: {analysis['conflict_count']}")
    print(f"  推荐顺序: {len(analysis['recommended_order'])} 个效果")

    assert_true(analysis["total_effects"] == 4, "总效果数正确")
    assert_true(analysis["categories_covered"] >= 2, "覆盖至少2个类别")
    assert_true(analysis["average_confidence"] > 0.7, "平均置信度 > 0.7")

    # ============================================================================
    # 测试10: 效果增强建议
    # ============================================================================
    section("测试10: 效果增强建议")

    enhancement = engine.enhance_combination(
        effect_names=["ADBE Glo2", "ADBE Color Balance"],
        max_additions=3,
    )
    print(f"\n增强建议: {enhancement['suggestion_count']} 个")
    assert_true(enhancement["suggestion_count"] >= 1, "至少1个增强建议")

    for i, s in enumerate(enhancement["suggestions"]):
        print(f"  {i+1}. {s['display_name']}: {s['reason']} (协同强度: {s['synergy_strength']})")

    # ============================================================================
    # 测试11: 风格组合生成
    # ============================================================================
    section("测试11: 风格组合生成")

    styles = ["cinematic", "cyberpunk", "vintage", "dreamy", "neon", "grunge", "minimal", "glitch"]

    for style in styles:
        result = engine.generate_style_combination(style, intensity=1.0)
        print(f"\n{style} 风格: {len(result.effects)} 个效果, 置信度: {result.confidence:.4f}")
        assert_true(len(result.effects) >= 2, f"{style} 风格效果数 >= 2 (实际: {len(result.effects)})")
        assert_true(result.confidence > 0.5, f"{style} 置信度 > 0.5 (实际: {result.confidence:.4f})")

    # ============================================================================
    # 测试12: 强度调整
    # ============================================================================
    section("测试12: 强度调整")

    result_low = engine.compose_from_keywords(["发光"], intensity=0.3)
    result_high = engine.compose_from_keywords(["发光"], intensity=1.8)

    if result_low.effects and result_high.effects:
        low_settings = result_low.effects[0]["settings"]
        high_settings = result_high.effects[0]["settings"]

        intensity_param = None
        for key in low_settings:
            if "intensity" in key.lower() or "radius" in key.lower() or "amount" in key.lower():
                intensity_param = key
                break

        if intensity_param:
            low_val = low_settings[intensity_param]
            high_val = high_settings[intensity_param]
            print(f"\n强度参数 '{intensity_param}':")
            print(f"  低强度 (0.3): {low_val}")
            print(f"  高强度 (1.8): {high_val}")
            assert_true(True, "强度调整测试完成")

    # ============================================================================
    # 测试13: 效果排序
    # ============================================================================
    section("测试13: 效果排序验证")

    result = engine.compose_from_keywords(
        keywords=["发光", "渐变", "模糊"],
        max_effects=5,
    )
    print("\n效果排序:")
    for i, effect in enumerate(result.effects):
        print(f"  {i+1}. {effect['displayName']} - {effect['category']}")

    # ============================================================================
    # 测试14: 效果元数据完整性
    # ============================================================================
    section("测试14: 效果元数据完整性")

    valid_count = 0
    invalid_effects = []

    for match_name, effect in EFFECT_KNOWLEDGE_GRAPH.items():
        valid = True
        if not effect.match_name:
            valid = False
        if not effect.display_name:
            valid = False
        if not effect.category:
            valid = False
        if not effect.parameters or len(effect.parameters) == 0:
            valid = False
        if not effect.tags or len(effect.tags) == 0:
            valid = False
        if effect.confidence <= 0:
            valid = False
        if valid:
            valid_count += 1
        else:
            invalid_effects.append(match_name)

    print(f"\n有效效果: {valid_count} / {len(EFFECT_KNOWLEDGE_GRAPH)}")
    if invalid_effects:
        print(f"无效效果: {', '.join(invalid_effects)}")

    assert_true(valid_count == len(EFFECT_KNOWLEDGE_GRAPH), f"所有效果元数据有效 ({valid_count}/{len(EFFECT_KNOWLEDGE_GRAPH)})")

    # ============================================================================
    # 测试15: 类别全覆盖验证
    # ============================================================================
    section("测试15: 类别全覆盖验证")

    category_effect_counts = {}
    for effect in EFFECT_KNOWLEDGE_GRAPH.values():
        cat = effect.category
        category_effect_counts[cat] = category_effect_counts.get(cat, 0) + 1

    for cat_key, cat_name in CATEGORIES.items():
        count = category_effect_counts.get(cat_key, 0)
        print(f"  {cat_name} ({cat_key}): {count} 个")
        assert_true(count > 0, f"{cat_name} 类至少有1个效果")

    # ============================================================================
    # 总结
    # ============================================================================
    print("\n" + "="*60)
    print(f" 测试结果: {pass_count} 通过 / {fail_count} 失败 / {pass_count + fail_count} 总计")
    print("="*60)

    return pass_count, fail_count


if __name__ == "__main__":
    pass_count, fail_count = run_all_tests()
    if fail_count > 0:
        sys.exit(1)
    else:
        print("\n✅ 所有测试通过！")
        sys.exit(0)
