"""
test_effect_registry_service.py - EffectRegistryService 单元测试
====================================================

测试重点：
1. EffectEntry 数据类（get / to_dict）
2. 初始化与加载（initialize 幂等、load_knowledge_base=False）
3. 效果注册（register_plugin_effects）
4. 效果查询（get_effect / get_all_effects / get_effect_count）
5. 分类搜索（search_by_category / get_categories / get_category_stats）
6. 场景推荐（get_recommended_effects，含中文关键词映射）
7. 多条件搜索（search_effects）
8. 插件包查询（get_plugin_packages / get_effects_by_plugin / get_plugin_stats）
9. 场景查询（get_scenarios / get_effects_by_scenario）
10. 导出（export_effect_list JSON/CSV）
11. 统计（get_statistics）
12. 索引重建（_rebuild_indexes）
"""

import csv
import importlib
import json
import os
import sys
import types

import pytest

# ── 路径设置 ──────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(PROJECT_ROOT, "puppet-automation", "src")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, _SRC_DIR)

# 注册一个空的 services 包到 sys.modules，跳过 __init__.py 的全量导入
_services_pkg = types.ModuleType("services")
_services_pkg.__path__ = [os.path.join(_SRC_DIR, "services")]
_services_pkg.__package__ = "services"
sys.modules["services"] = _services_pkg

# 通过 importlib 加载目标模块
_spec = importlib.util.spec_from_file_location(
    "services.effect_registry_service",
    os.path.join(_SRC_DIR, "services", "effect_registry_service.py"),
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
_mod.__package__ = "services"
sys.modules["services.effect_registry_service"] = _mod
_spec.loader.exec_module(_mod)

EffectEntry = _mod.EffectEntry
EffectRegistryService = _mod.EffectRegistryService


# ══════════════════════════════════════════════════════════
# 辅助工具
# ══════════════════════════════════════════════════════════

def _make_entry(**overrides) -> EffectEntry:
    """构造 EffectEntry，提供合理默认值。"""
    defaults = dict(
        name="Gaussian Blur",
        match_name="ADBE Gaussian Blur 2",
        category="blur",
        plugin_package="Adobe",
        description="高斯模糊效果",
        params={"blurriness": 10},
        usage_scenarios=["模糊处理", "背景虚化"],
        default_presets=[{"name": "轻柔", "params": {"blurriness": 5}}],
        source="hardcoded",
        confidence=0.9,
    )
    defaults.update(overrides)
    return EffectEntry(**defaults)


def _fresh_service() -> EffectRegistryService:
    """创建一个全新、未初始化的 EffectRegistryService。"""
    return EffectRegistryService()


def _initialized_service() -> EffectRegistryService:
    """创建一个已初始化（不含知识库）的 EffectRegistryService。"""
    svc = EffectRegistryService()
    svc.initialize(load_knowledge_base=False)
    return svc


def _service_with_sample_effects() -> EffectRegistryService:
    """创建已初始化并注册了一批样本效果的服务实例。

    使用 TEST:: 前缀的 match_name 避免与 hardcoded map 中的效果冲突。
    """
    svc = _initialized_service()

    effects = [
        {
            "name": "Test Gaussian Blur",
            "match_name": "TEST::GaussianBlur",
            "category": "blur",
            "description": "高斯模糊效果",
            "usage_scenarios": ["模糊处理", "背景虚化"],
            "confidence": 0.9,
        },
        {
            "name": "Test Fractal Noise",
            "match_name": "TEST::FractalNoise",
            "category": "noise",
            "description": "分形噪波",
            "usage_scenarios": ["噪波纹理", "背景生成"],
            "confidence": 0.85,
        },
        {
            "name": "Test Color Correction",
            "match_name": "TEST::ColorCorrection",
            "category": "color",
            "description": "颜色校正",
            "usage_scenarios": ["调色", "颜色校正"],
            "confidence": 0.95,
        },
        {
            "name": "Test Glow",
            "match_name": "TEST::Glow",
            "category": "light",
            "description": "发光效果",
            "usage_scenarios": ["光效", "发光"],
            "confidence": 0.88,
        },
        {
            "name": "Test Particle Playground",
            "match_name": "TEST::ParticlePlayground",
            "category": "particle",
            "description": "粒子运动场",
            "usage_scenarios": ["粒子特效", "粒子"],
            "confidence": 0.8,
        },
    ]
    svc.register_plugin_effects(effects, plugin_package="TestPlugin")
    return svc


# ══════════════════════════════════════════════════════════
# EffectEntry 数据类
# ══════════════════════════════════════════════════════════

class TestEffectEntry:
    """EffectEntry 数据类测试。"""

    def test_get_existing_attribute(self):
        entry = _make_entry()
        assert entry.get("name") == "Gaussian Blur"
        assert entry.get("category") == "blur"
        assert entry.get("confidence") == 0.9

    def test_get_non_existing_attribute_returns_default(self):
        entry = _make_entry()
        assert entry.get("nonexistent") == ""
        assert entry.get("nonexistent", "fallback") == "fallback"

    def test_to_dict_keys(self):
        entry = _make_entry()
        d = entry.to_dict()
        expected_keys = {
            "name", "match_name", "display_name", "category",
            "plugin_package", "description", "params",
            "usage_scenarios", "default_presets", "source", "confidence",
        }
        assert set(d.keys()) == expected_keys

    def test_to_dict_display_name_equals_name(self):
        entry = _make_entry(name="TestEffect")
        d = entry.to_dict()
        assert d["display_name"] == "TestEffect"
        assert d["name"] == "TestEffect"

    def test_to_dict_values_match(self):
        entry = _make_entry()
        d = entry.to_dict()
        assert d["match_name"] == "ADBE Gaussian Blur 2"
        assert d["category"] == "blur"
        assert d["plugin_package"] == "Adobe"
        assert d["params"] == {"blurriness": 10}
        assert d["usage_scenarios"] == ["模糊处理", "背景虚化"]
        assert d["confidence"] == 0.9

    def test_defaults(self):
        entry = EffectEntry(name="Empty")
        assert entry.match_name == ""
        assert entry.category == "other"
        assert entry.plugin_package == ""
        assert entry.description == ""
        assert entry.params == {}
        assert entry.usage_scenarios == []
        assert entry.default_presets == []
        assert entry.source == ""
        assert entry.confidence == 0.8


# ══════════════════════════════════════════════════════════
# 初始化与加载
# ══════════════════════════════════════════════════════════

class TestInitialize:
    """EffectRegistryService.initialize 测试。"""

    def test_init_empty_indexes(self):
        svc = _fresh_service()
        assert svc._effects == {}
        assert svc._category_index == {}
        assert svc._plugin_index == {}
        assert svc._scenario_index == {}
        assert svc._initialized is False

    def test_initialize_returns_count(self):
        svc = _fresh_service()
        count = svc.initialize(load_knowledge_base=False)
        assert isinstance(count, int)
        assert count >= 0

    def test_initialize_sets_initialized_flag(self):
        svc = _fresh_service()
        svc.initialize(load_knowledge_base=False)
        assert svc._initialized is True

    def test_initialize_idempotent(self):
        """多次 initialize 返回相同计数，不重复加载。"""
        svc = _fresh_service()
        count1 = svc.initialize(load_knowledge_base=False)
        count2 = svc.initialize(load_knowledge_base=False)
        assert count1 == count2

    def test_initialize_idempotent_effect_count(self):
        """幂等调用不会增加效果总数。"""
        svc = _fresh_service()
        svc.initialize(load_knowledge_base=False)
        n = svc.get_effect_count()
        svc.initialize(load_knowledge_base=False)
        assert svc.get_effect_count() == n


# ══════════════════════════════════════════════════════════
# 效果注册
# ══════════════════════════════════════════════════════════

class TestRegisterPluginEffects:
    """register_plugin_effects 批量注册测试。"""

    def test_register_valid_effects(self):
        svc = _initialized_service()
        effects = [
            {"name": "TestBlur", "match_name": "TEST::Blur", "category": "blur"},
            {"name": "TestGlow", "match_name": "TEST::Glow", "category": "light"},
        ]
        added = svc.register_plugin_effects(effects, plugin_package="TestPlugin")
        assert added == 2

    def test_register_empty_list(self):
        svc = _initialized_service()
        added = svc.register_plugin_effects([], plugin_package="Empty")
        assert added == 0

    def test_register_skips_no_name(self):
        """name 为空的效果应被跳过。"""
        svc = _initialized_service()
        effects = [
            {"name": "", "match_name": "TEST::Empty"},
            {"name": "ValidOne", "match_name": "TEST::Valid", "category": "other"},
        ]
        added = svc.register_plugin_effects(effects, plugin_package="TestPlugin")
        assert added == 1

    def test_register_duplicate_not_counted(self):
        """重复 match_name 不重复计数。"""
        svc = _initialized_service()
        effects = [
            {"name": "Dup", "match_name": "TEST::Dup", "category": "other"},
        ]
        svc.register_plugin_effects(effects, plugin_package="P1")
        added = svc.register_plugin_effects(effects, plugin_package="P2")
        assert added == 0

    def test_register_auto_initializes(self):
        """在未初始化时 register_plugin_effects 自动调用 initialize。"""
        svc = _fresh_service()
        effects = [{"name": "Auto", "match_name": "TEST::Auto", "category": "other"}]
        added = svc.register_plugin_effects(effects, plugin_package="AutoP")
        assert added == 1
        assert svc._initialized is True

    def test_register_rebuilds_indexes(self):
        """注册新效果后索引应包含新分类。"""
        svc = _initialized_service()
        effects = [
            {"name": "IdxBlur", "match_name": "TEST::IdxBlur", "category": "blur"},
        ]
        svc.register_plugin_effects(effects, plugin_package="IdxP")
        assert "blur" in svc._category_index
        assert "IdxP" in svc._plugin_index


# ══════════════════════════════════════════════════════════
# 效果查询
# ══════════════════════════════════════════════════════════

class TestGetEffect:
    """get_effect 查询测试。"""

    def test_get_effect_existing(self):
        svc = _service_with_sample_effects()
        entry = svc.get_effect("TEST::GaussianBlur")
        assert entry is not None
        assert entry.name == "Test Gaussian Blur"

    def test_get_effect_case_insensitive(self):
        svc = _service_with_sample_effects()
        assert svc.get_effect("test::gaussianblur") is not None
        assert svc.get_effect("TEST::GAUSSIANBLUR") is not None
        assert svc.get_effect("TEST::GaussianBlur") is not None

    def test_get_effect_not_found(self):
        svc = _service_with_sample_effects()
        assert svc.get_effect("NONEXISTENT::Effect") is None

    def test_get_effect_empty_string(self):
        svc = _service_with_sample_effects()
        assert svc.get_effect("") is None


class TestGetAllEffects:
    """get_all_effects 测试。"""

    def test_returns_list(self):
        svc = _service_with_sample_effects()
        result = svc.get_all_effects()
        assert isinstance(result, list)

    def test_contains_registered_effects(self):
        svc = _service_with_sample_effects()
        result = svc.get_all_effects()
        names = {e.name for e in result}
        assert "Test Gaussian Blur" in names
        assert "Test Fractal Noise" in names


class TestGetEffectCount:
    """get_effect_count 测试。"""

    def test_count_matches_registered(self):
        svc = _service_with_sample_effects()
        assert svc.get_effect_count() == len(svc.get_all_effects())

    def test_empty_service_count(self):
        svc = _initialized_service()
        # 可能从 hardcoded map 加载了一些效果，count >= 0
        assert svc.get_effect_count() >= 0


# ══════════════════════════════════════════════════════════
# 分类搜索
# ══════════════════════════════════════════════════════════

class TestSearchByCategory:
    """search_by_category 分类搜索测试。"""

    def test_known_category(self):
        svc = _service_with_sample_effects()
        results = svc.search_by_category("blur")
        assert len(results) > 0
        assert all(e.category == "blur" for e in results)

    def test_unknown_category_returns_empty(self):
        svc = _service_with_sample_effects()
        results = svc.search_by_category("nonexistent_category")
        assert results == []

    def test_case_insensitive(self):
        svc = _service_with_sample_effects()
        r1 = svc.search_by_category("blur")
        r2 = svc.search_by_category("BLUR")
        r3 = svc.search_by_category("Blur")
        assert len(r1) == len(r2) == len(r3)


class TestGetCategories:
    """get_categories 测试。"""

    def test_returns_list(self):
        svc = _service_with_sample_effects()
        cats = svc.get_categories()
        assert isinstance(cats, list)

    def test_contains_known_categories(self):
        svc = _service_with_sample_effects()
        cats = svc.get_categories()
        assert "blur" in cats
        assert "color" in cats


class TestGetCategoryStats:
    """get_category_stats 测试。"""

    def test_returns_dict(self):
        svc = _service_with_sample_effects()
        stats = svc.get_category_stats()
        assert isinstance(stats, dict)

    def test_values_are_int(self):
        svc = _service_with_sample_effects()
        stats = svc.get_category_stats()
        for cat, count in stats.items():
            assert isinstance(count, int)
            assert count > 0

    def test_sum_equals_total(self):
        svc = _service_with_sample_effects()
        stats = svc.get_category_stats()
        assert sum(stats.values()) == svc.get_effect_count()


# ══════════════════════════════════════════════════════════
# 场景推荐
# ══════════════════════════════════════════════════════════

class TestGetRecommendedEffects:
    """get_recommended_effects 场景推荐测试。"""

    def test_chinese_keyword_color(self):
        """调色 → color 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("调色")
        categories = {e.category for e in results}
        assert "color" in categories

    def test_chinese_keyword_particle(self):
        """粒子 → particle 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("粒子")
        categories = {e.category for e in results}
        assert "particle" in categories

    def test_chinese_keyword_blur(self):
        """模糊 → blur 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("模糊")
        categories = {e.category for e in results}
        assert "blur" in categories

    def test_chinese_keyword_light(self):
        """光效 → light 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("光效")
        categories = {e.category for e in results}
        assert "light" in categories

    def test_chinese_keyword_glow(self):
        """发光 → light 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("发光")
        categories = {e.category for e in results}
        assert "light" in categories

    def test_chinese_keyword_distort(self):
        """扭曲 → distort 分类。"""
        svc = _service_with_sample_effects()
        # 没有注册 distort 类效果，但不应报错
        results = svc.get_recommended_effects("扭曲")
        assert isinstance(results, list)

    def test_chinese_keyword_noise(self):
        """噪点 → noise 分类。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("噪点")
        categories = {e.category for e in results}
        assert "noise" in categories

    def test_limit_parameter(self):
        """limit 参数应限制返回数量。"""
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("调色", limit=1)
        assert len(results) <= 1

    def test_unknown_scenario_returns_empty_or_few(self):
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("完全不相关的场景xyz")
        assert isinstance(results, list)

    def test_results_sorted_by_confidence(self):
        svc = _service_with_sample_effects()
        results = svc.get_recommended_effects("调色")
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i + 1].confidence


# ══════════════════════════════════════════════════════════
# 多条件搜索
# ══════════════════════════════════════════════════════════

class TestSearchEffects:
    """search_effects 多条件搜索测试。"""

    def test_search_by_query_name_match(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(query="Gaussian")
        names = [e.name for e in results]
        assert any("Gaussian" in n for n in names), f"No match in {names[:5]}"

    def test_search_by_query_description_match(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(query="模糊")
        assert len(results) > 0

    def test_search_by_category_filter(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(category="blur")
        assert all(e.category == "blur" for e in results)

    def test_search_by_plugin_package_filter(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(plugin_package="TestPlugin")
        assert all(e.plugin_package == "TestPlugin" for e in results)

    def test_search_combined_filters(self):
        """query + category 组合过滤。"""
        svc = _service_with_sample_effects()
        results = svc.search_effects(query="Gaussian", category="blur")
        assert len(results) > 0
        assert all(e.category == "blur" for e in results)

    def test_search_no_match(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(query="ZZZZ_NOT_EXIST")
        assert results == []

    def test_search_empty_query_no_filter(self):
        """空 query 无过滤 → 返回全部（受 limit 约束）。"""
        svc = _service_with_sample_effects()
        results = svc.search_effects(limit=100)
        assert len(results) > 0

    def test_search_limit(self):
        svc = _service_with_sample_effects()
        results = svc.search_effects(limit=2)
        assert len(results) <= 2

    def test_keyword_alias(self):
        """keyword 参数作为 query 的别名。"""
        svc = _service_with_sample_effects()
        r1 = svc.search_effects(query="Gaussian")
        r2 = svc.search_effects(keyword="Gaussian")
        # 两者应返回相同结果
        assert len(r1) == len(r2)

    def test_results_sorted_by_score(self):
        """结果按得分降序排列。"""
        svc = _service_with_sample_effects()
        results = svc.search_effects(query="Gaussian")
        # 名字包含 Gaussian 的应排在前面
        if len(results) > 0:
            assert "Gaussian" in results[0].name or "gaussian" in results[0].name.lower()


# ══════════════════════════════════════════════════════════
# 插件包查询
# ══════════════════════════════════════════════════════════

class TestPluginQueries:
    """插件包相关查询测试。"""

    def test_get_plugin_packages(self):
        svc = _service_with_sample_effects()
        pkgs = svc.get_plugin_packages()
        assert isinstance(pkgs, list)
        assert "TestPlugin" in pkgs

    def test_get_effects_by_plugin(self):
        svc = _service_with_sample_effects()
        results = svc.get_effects_by_plugin("TestPlugin")
        assert len(results) > 0
        assert all(e.plugin_package == "TestPlugin" for e in results)

    def test_get_effects_by_unknown_plugin(self):
        svc = _service_with_sample_effects()
        results = svc.get_effects_by_plugin("NonexistentPlugin")
        assert results == []

    def test_get_plugin_stats(self):
        svc = _service_with_sample_effects()
        stats = svc.get_plugin_stats()
        assert isinstance(stats, dict)
        assert "TestPlugin" in stats
        assert stats["TestPlugin"] > 0

    def test_plugin_stats_sum_equals_total(self):
        svc = _service_with_sample_effects()
        stats = svc.get_plugin_stats()
        assert sum(stats.values()) == svc.get_effect_count()


# ══════════════════════════════════════════════════════════
# 场景查询
# ══════════════════════════════════════════════════════════

class TestScenarioQueries:
    """场景相关查询测试。"""

    def test_get_scenarios(self):
        svc = _service_with_sample_effects()
        scenarios = svc.get_scenarios()
        assert isinstance(scenarios, list)
        assert len(scenarios) > 0

    def test_get_effects_by_scenario_exact(self):
        svc = _service_with_sample_effects()
        results = svc.get_effects_by_scenario("模糊处理")
        assert len(results) > 0

    def test_get_effects_by_scenario_fuzzy(self):
        svc = _service_with_sample_effects()
        # 模糊匹配：场景名子串包含
        results = svc.get_effects_by_scenario("模糊")
        assert isinstance(results, list)

    def test_get_effects_by_scenario_unknown(self):
        svc = _service_with_sample_effects()
        results = svc.get_effects_by_scenario("完全不存在的场景")
        assert results == []

    def test_effects_by_scenario_sorted_by_confidence(self):
        svc = _service_with_sample_effects()
        results = svc.get_effects_by_scenario("模糊处理")
        for i in range(len(results) - 1):
            assert results[i].confidence >= results[i + 1].confidence


# ══════════════════════════════════════════════════════════
# 导出
# ══════════════════════════════════════════════════════════

class TestExportEffectList:
    """export_effect_list 导出测试。"""

    def test_export_json(self, tmp_path):
        svc = _service_with_sample_effects()
        out = tmp_path / "effects.json"
        result = svc.export_effect_list(str(out), format="json")
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) > 0
        # 检查第一条记录包含必要字段
        first = data[0]
        assert "name" in first
        assert "match_name" in first
        assert "category" in first

    def test_export_csv(self, tmp_path):
        svc = _service_with_sample_effects()
        out = tmp_path / "effects.csv"
        result = svc.export_effect_list(str(out), format="csv")
        assert out.exists()
        with open(out, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # 第一行为表头
        assert rows[0][0] == "名称"
        assert len(rows) > 1  # 至少有数据行

    def test_export_returns_path(self, tmp_path):
        svc = _service_with_sample_effects()
        out = tmp_path / "out.json"
        result = svc.export_effect_list(str(out), format="json")
        assert result == str(out)

    def test_export_creates_parent_dirs(self, tmp_path):
        svc = _service_with_sample_effects()
        out = tmp_path / "subdir" / "nested" / "effects.json"
        result = svc.export_effect_list(str(out), format="json")
        assert out.exists()


# ══════════════════════════════════════════════════════════
# 统计
# ══════════════════════════════════════════════════════════

class TestGetStatistics:
    """get_statistics 综合统计测试。"""

    def test_statistics_structure(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert "total" in stats
        assert "by_category" in stats
        assert "by_plugin" in stats
        assert "by_source" in stats
        assert "categories" in stats
        assert "plugin_packages" in stats

    def test_statistics_total_matches_count(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert stats["total"] == svc.get_effect_count()

    def test_statistics_by_category_is_dict(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert isinstance(stats["by_category"], dict)

    def test_statistics_by_plugin_is_dict(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert isinstance(stats["by_plugin"], dict)

    def test_statistics_by_source_is_dict(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert isinstance(stats["by_source"], dict)
        # 至少应包含 plugin 或 hardcoded 来源
        assert len(stats["by_source"]) > 0

    def test_statistics_categories_count(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert stats["categories"] == len(svc.get_categories())

    def test_statistics_plugin_packages_count(self):
        svc = _service_with_sample_effects()
        stats = svc.get_statistics()
        assert stats["plugin_packages"] == len(svc.get_plugin_packages())


# ══════════════════════════════════════════════════════════
# 索引重建
# ══════════════════════════════════════════════════════════

class TestRebuildIndexes:
    """_rebuild_indexes 索引重建测试。"""

    def test_category_index_built(self):
        svc = _service_with_sample_effects()
        # 所有已注册效果的分类应在索引中
        for entry in svc.get_all_effects():
            assert entry.category in svc._category_index

    def test_plugin_index_built(self):
        svc = _service_with_sample_effects()
        for entry in svc.get_all_effects():
            pkg = entry.plugin_package or "Unknown"
            assert pkg in svc._plugin_index

    def test_scenario_index_built(self):
        svc = _service_with_sample_effects()
        for entry in svc.get_all_effects():
            for scenario in entry.usage_scenarios:
                assert scenario.lower() in svc._scenario_index

    def test_category_index_values_are_keys_in_effects(self):
        svc = _service_with_sample_effects()
        for cat, keys in svc._category_index.items():
            for k in keys:
                assert k in svc._effects

    def test_plugin_index_values_are_keys_in_effects(self):
        svc = _service_with_sample_effects()
        for pkg, keys in svc._plugin_index.items():
            for k in keys:
                assert k in svc._effects

    def test_scenario_index_values_are_keys_in_effects(self):
        svc = _service_with_sample_effects()
        for scenario, keys in svc._scenario_index.items():
            for k in keys:
                assert k in svc._effects

    def test_rebuild_clears_old_indexes(self):
        """索引重建应清除旧数据。"""
        svc = _service_with_sample_effects()
        old_cat_count = len(svc._category_index)
        # 手动添加一个效果并重建
        svc._effects["test::new"] = EffectEntry(
            name="NewEffect",
            match_name="test::new",
            category="test_cat",
            usage_scenarios=["test_scenario"],
        )
        svc._rebuild_indexes()
        assert "test_cat" in svc._category_index
        assert "test_scenario" in svc._scenario_index
