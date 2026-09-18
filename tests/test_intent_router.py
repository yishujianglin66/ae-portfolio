"""intent_router 模块单元测试

覆盖范围:
- TaskRoute 数据类构造与默认值
- _MemoryStore 记忆存储与检索
- IntentRouter.route() 主路由逻辑（ae_only / silhouette_only / hybrid / unknown）
- IntentRouter.route_enhanced() 记忆增强路由
- IntentRouter.is_hybrid() 混合任务判断
- IntentRouter.split_hybrid_input() 混合输入拆分
- 降级策略 FALLBACK_MAP 映射正确性
- 边界条件（空输入、无匹配、大小写不敏感）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from intent_router import (
    AE_EFFECT_KEYWORDS,
    FALLBACK_MAP,
    HYBRID_CONNECTORS,
    SILHOUETTE_KEYWORDS,
    IntentRouter,
    TaskRoute,
    _MemoryStore,
)

# ============================================================================
# TaskRoute 数据类
# ============================================================================

class TestTaskRoute:
    def test_default_construction(self):
        route = TaskRoute(type="unknown")
        assert route.type == "unknown"
        assert route.ae_operations == []
        assert route.silhouette_operations == []
        assert route.execution_order == []
        assert route.fallback is None
        assert route.reason == ""
        assert route.confidence == 0.0

    def test_full_construction(self):
        route = TaskRoute(
            type="hybrid",
            ae_operations=[{"op": "addEffect"}],
            silhouette_operations=[{"taskType": "roto"}],
            execution_order=["silhouette", "ae"],
            fallback={"message": "fallback"},
            reason="test",
            confidence=0.9,
        )
        assert route.type == "hybrid"
        assert len(route.ae_operations) == 1
        assert len(route.silhouette_operations) == 1
        assert route.execution_order == ["silhouette", "ae"]
        assert route.fallback == {"message": "fallback"}
        assert route.reason == "test"
        assert route.confidence == 0.9


# ============================================================================
# _MemoryStore
# ============================================================================

class TestMemoryStore:
    def test_remember_and_get_experience(self):
        store = _MemoryStore()
        store.remember(
            category="intent_route",
            key="扣人像然后加发光",
            content={"route": {"type": "hybrid"}},
            tags=["hybrid"],
            confidence=0.9,
        )
        results = store.get_experience("intent_route", "扣人像")
        assert len(results) == 1
        assert results[0]["confidence"] == 0.9

    def test_get_experience_filters_by_confidence(self):
        store = _MemoryStore()
        store.remember("intent_route", "key1", {}, [], 0.5)
        store.remember("intent_route", "key2", {}, [], 0.9)
        results = store.get_experience("intent_route", "key", min_confidence=0.6)
        assert len(results) == 1
        assert results[0]["confidence"] == 0.9

    def test_get_experience_limit(self):
        store = _MemoryStore()
        for i in range(5):
            store.remember("intent_route", f"key{i}", {}, [], 0.9)
        results = store.get_experience("intent_route", "key", limit=3)
        assert len(results) == 3

    def test_get_experience_wrong_category(self):
        store = _MemoryStore()
        store.remember("intent_route", "key1", {}, [], 0.9)
        results = store.get_experience("other", "key1")
        assert len(results) == 0

    def test_get_experience_sorted_by_confidence(self):
        store = _MemoryStore()
        store.remember("intent_route", "alpha_task", {}, [], 0.5)
        store.remember("intent_route", "alpha_task", {}, [], 0.95)
        store.remember("intent_route", "alpha_task", {}, [], 0.7)
        results = store.get_experience("intent_route", "alpha_task")
        assert results[0]["confidence"] == 0.95


# ============================================================================
# IntentRouter.route() — 主路由逻辑
# ============================================================================

class TestIntentRouterRoute:
    def test_ae_only_glow(self):
        router = IntentRouter()
        route = router.route("给文字加发光效果")
        assert route.type == "ae_only"
        assert route.confidence == 0.85
        assert "ae" in route.execution_order

    def test_ae_only_blur(self):
        router = IntentRouter()
        route = router.route("添加高斯模糊")
        assert route.type == "ae_only"

    def test_silhouette_only_roto(self):
        router = IntentRouter()
        route = router.route("扣掉这个人像")
        assert route.type == "silhouette_only"
        assert route.confidence == 0.85
        assert "silhouette" in route.execution_order
        assert route.fallback is not None

    def test_silhouette_only_track(self):
        router = IntentRouter()
        route = router.route("跟踪这个物体")
        assert route.type == "silhouette_only"

    def test_silhouette_only_paint(self):
        router = IntentRouter()
        route = router.route("擦掉这个污渍")
        assert route.type == "silhouette_only"

    def test_hybrid_with_connector(self):
        router = IntentRouter()
        route = router.route("扣掉背景然后加发光")
        assert route.type == "hybrid"
        assert route.execution_order == ["silhouette", "ae"]
        assert route.confidence == 0.8

    def test_hybrid_with_connector_variants(self):
        router = IntentRouter()
        variants = [
            "抠人像之后再添加模糊",
            "扣完图接着加粒子",
            "遮罩完后加渐变",
            "修好后同时加阴影",
        ]
        for text in variants:
            route = router.route(text)
            assert route.type == "hybrid", f"'{text}' 应识别为 hybrid"

    def test_unknown_empty_input(self):
        router = IntentRouter()
        route = router.route("")
        assert route.type == "unknown"
        assert route.confidence == 0.2

    def test_unknown_no_match(self):
        router = IntentRouter()
        route = router.route("今天天气怎么样")
        assert route.type == "unknown"

    def test_case_insensitive(self):
        router = IntentRouter()
        assert router.route("添加GLOW效果").type == "ae_only"
        assert router.route("添加MASK遮罩").type == "silhouette_only"

    def test_silhouette_default_to_roto(self):
        router = IntentRouter()
        route = router.route("用silhouette处理")
        assert route.type == "silhouette_only"
        ops = route.silhouette_operations
        assert len(ops) > 0
        assert ops[0]["taskType"] == "roto"


# ============================================================================
# IntentRouter.route_enhanced()
# ============================================================================

class TestIntentRouterRouteEnhanced:
    def test_uses_memory_when_high_confidence(self):
        store = _MemoryStore()
        store.remember(
            category="intent_route",
            key="扣人像然后加发光",
            content={
                "route": {
                    "type": "hybrid",
                    "ae_operations": [{"op": "test"}],
                    "silhouette_operations": [],
                    "execution_order": ["silhouette", "ae"],
                    "reason": "cached",
                }
            },
            tags=["hybrid"],
            confidence=0.9,
        )
        router = IntentRouter(memory_store=store)
        route = router.route_enhanced("扣人像然后加发光")
        assert route.type == "hybrid"
        assert "(from memory)" in route.reason
        assert route.confidence <= 0.95

    def test_falls_back_to_rule_when_no_memory(self):
        store = _MemoryStore()
        router = IntentRouter(memory_store=store)
        route = router.route_enhanced("加发光效果")
        assert route.type == "ae_only"
        assert route.confidence == 0.85

    def test_records_to_memory_after_rule_route(self):
        store = _MemoryStore()
        router = IntentRouter(memory_store=store)
        router.route_enhanced("加模糊")
        exps = store.get_experience("intent_route", "加模糊")
        assert len(exps) == 1
        assert exps[0]["content"]["route"]["type"] == "ae_only"


# ============================================================================
# IntentRouter.is_hybrid()
# ============================================================================

class TestIntentRouterIsHybrid:
    def test_true_cases(self):
        router = IntentRouter()
        assert router.is_hybrid("扣人像然后加发光") is True
        assert router.is_hybrid("抠图之后再添加模糊") is True

    def test_false_no_connector(self):
        router = IntentRouter()
        assert router.is_hybrid("扣人像加发光") is False

    def test_false_no_silhouette(self):
        router = IntentRouter()
        assert router.is_hybrid("加发光然后调颜色") is False

    def test_false_no_ae(self):
        router = IntentRouter()
        assert router.is_hybrid("扣人像然后修图") is False


# ============================================================================
# IntentRouter.split_hybrid_input()
# ============================================================================

class TestIntentRouterSplitHybrid:
    def test_split_before_after(self):
        router = IntentRouter()
        result = router.split_hybrid_input("扣掉背景然后加发光")
        assert result["silhouette_part"] == "扣掉背景"
        assert result["ae_part"] == "加发光"

    def test_split_no_match(self):
        router = IntentRouter()
        result = router.split_hybrid_input("加发光效果")
        assert result == {}

    def test_split_connector_zaihou(self):
        router = IntentRouter()
        result = router.split_hybrid_input("抠图之后再添加模糊")
        assert "silhouette_part" in result
        assert "ae_part" in result


# ============================================================================
# 内部工具方法
# ============================================================================

class TestIntentRouterInternals:
    def test_detect_silhouette_task_type_roto(self):
        router = IntentRouter()
        assert router._detect_silhouette_task_type("扣人像") == "roto"
        assert router._detect_silhouette_task_type("mask") == "roto"

    def test_detect_silhouette_task_type_track(self):
        router = IntentRouter()
        assert router._detect_silhouette_task_type("跟踪") == "track"

    def test_detect_silhouette_task_type_paint(self):
        router = IntentRouter()
        assert router._detect_silhouette_task_type("修复") == "paint"

    def test_detect_silhouette_task_type_none(self):
        router = IntentRouter()
        assert router._detect_silhouette_task_type("加发光") is None

    def test_generate_ae_ops(self):
        router = IntentRouter()
        ops = router._generate_ae_ops("给文字加发光")
        assert len(ops) >= 1
        assert ops[0]["op"] == "addEffect"

    def test_generate_ae_ops_from_hybrid(self):
        router = IntentRouter()
        ops = router._generate_ae_ops("扣掉背景然后加模糊")
        assert len(ops) >= 1
        assert "模糊" in ops[0]["effectName"] or ops[0]["effectName"] == "模糊"

    def test_generate_silhouette_ops_roto(self):
        router = IntentRouter()
        ops = router._generate_silhouette_ops("扣人像")
        assert len(ops) == 1
        assert ops[0]["taskType"] == "roto"
        assert ops[0]["shapeType"] == "x-spline"

    def test_generate_silhouette_ops_track(self):
        router = IntentRouter()
        ops = router._generate_silhouette_ops("跟踪")
        assert len(ops) == 1
        assert ops[0]["taskType"] == "track"

    def test_generate_silhouette_ops_no_match(self):
        router = IntentRouter()
        ops = router._generate_silhouette_ops("加发光")
        assert ops == []


# ============================================================================
# 降级策略
# ============================================================================

class TestFallbackMap:
    def test_roto_fallback_structure(self):
        fb = FALLBACK_MAP["roto"]
        assert "condition" in fb
        assert "ae_fallback_ops" in fb
        assert len(fb["ae_fallback_ops"]) > 0
        assert fb["ae_fallback_ops"][0]["matchName"] == "ADBE Mask"

    def test_track_fallback_structure(self):
        fb = FALLBACK_MAP["track"]
        assert fb["ae_fallback_ops"][0]["matchName"] == "ADBE Tracker"

    def test_paint_fallback_structure(self):
        fb = FALLBACK_MAP["paint"]
        assert fb["ae_fallback_ops"][0]["matchName"] == "ADBE Paint"

    def test_silhouette_only_includes_fallback(self):
        router = IntentRouter()
        route = router.route("扣人像")
        assert route.fallback is not None
        assert "ae_fallback_ops" in route.fallback

    def test_hybrid_includes_fallback(self):
        router = IntentRouter()
        route = router.route("扣人像然后加发光")
        assert route.fallback is not None

    def test_fallback_for_unknown_task_type(self):
        router = IntentRouter()
        route = router.route("用silhouette处理")
        # silhouette 默认归为 roto，fallback 应存在
        assert route.fallback is not None
        assert "message" in route.fallback
