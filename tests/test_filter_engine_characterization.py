"""
Filter Engine Characterization Tests (2026-09-18, 2026-09-19 校正)
==================================================================
为 filter_engine.py(5510 行 god 文件) 编写特征提取测试，在分解前确保行为稳定。

2026-09-19 校正: 初版按**预期 API** (FilterDefinition / SoftwareAdapter /
_SOFTWARE_REGISTRY / engine.name) 编写, 这些符号在实现里并不存在 —— 12 项全红,
属"测试描述愿景而非现状"。特征化测试的职责是锁**当前真实行为**, 故本轮按
实现实际契约重写。真实契约(探针实测):

  FilterParam(name, value, min_value=0.0, max_value=100.0,
              param_type='float', unit='', description='')   + validate/normalize
  FilterPreset(id, name, category, style, software_support, params,
               intensity=1.0, description, author, version, tags)  + to_dict()
  FilterChainItem(preset, opacity=100.0, blend_mode=BlendMode.NORMAL,
                  mask, enabled=True, animation_keyframes)
  FilterRecommendation(preset, confidence, reason, priority=0)
  引擎: BaseFilterEngine 抽象 (apply_filter/apply_filter_chain/generate_script),
        AEFilterEngine._software_type == SoftwareType.AFTER_EFFECTS, 80 个滤镜
"""
import pytest

from core.filter_engine import (
    AEFilterEngine,
    BaseFilterEngine,
    BlendMode,
    FilterCategory,
    FilterChain,
    FilterChainItem,
    FilterNotFoundError,
    FilterParam,
    FilterPreset,
    FilterPresetLibrary,
    FilterRecommendation,
    FilterStyle,
    InvalidParameterError,
    SoftwareType,
)


def _param(**kw):
    kw.setdefault("name", "radius")
    kw.setdefault("value", 10)
    return FilterParam(**kw)


def _preset(**kw):
    kw.setdefault("id", "p1")
    kw.setdefault("name", "Glow")
    kw.setdefault("category", FilterCategory.STYLIZE)
    kw.setdefault("style", FilterStyle.GLOW)
    kw.setdefault("software_support", [SoftwareType.AFTER_EFFECTS])
    return FilterPreset(**kw)


class TestBaseFilterEngineInitialization:
    """测试引擎初始化"""

    def test_ae_filter_engine_creation(self):
        engine = AEFilterEngine()
        assert engine is not None
        # 引擎自述身份用 _software_type, 没有 name 属性 (初版断言 name 系虚构)
        assert engine._software_type == SoftwareType.AFTER_EFFECTS

    def test_base_filter_engine_abstract(self):
        """BaseFilterEngine 是抽象类, 不能直接实例化"""
        with pytest.raises(TypeError):
            BaseFilterEngine()

    def test_abstract_method_surface(self):
        """抽象方法面 = 三个具体引擎必须实现的动作"""
        assert BaseFilterEngine.__abstractmethods__ == frozenset(
            {"apply_filter", "apply_filter_chain", "generate_script"})

    def test_ae_engine_implements_abstract_surface(self):
        engine = AEFilterEngine()
        for m in ("apply_filter", "apply_filter_chain", "generate_script"):
            assert callable(getattr(engine, m))

    def test_available_filters_nonempty(self):
        """AE 引擎自带滤镜库 (2026-09-19 实测 80 个)"""
        filters = AEFilterEngine().get_available_filters()
        assert isinstance(filters, list) and len(filters) > 0


class TestFilterParam:
    """测试滤镜参数 (真实字段: value, 无 default_value)"""

    def test_param_creation(self):
        p = _param(min_value=0, max_value=100, description="Glow radius")
        assert p.name == "radius" and p.value == 10
        assert (p.min_value, p.max_value) == (0, 100)
        assert p.description == "Glow radius"

    def test_param_defaults(self):
        """默认区间 0-100 / 类型 float / 单位空"""
        p = FilterParam(name="x", value=1)
        assert (p.min_value, p.max_value) == (0.0, 100.0)
        assert p.param_type == "float" and p.unit == ""

    def test_param_validate_accepts_in_range(self):
        assert _param(min_value=0, max_value=100, value=50).validate() is True

    def test_param_validate_rejects_out_of_range(self):
        """越界必须被 validate() 拒绝 (初版断言的 is_within_range 不存在)"""
        assert _param(min_value=0, max_value=100, value=150).validate() is False

    def test_param_normalize_denormalize_roundtrip(self):
        """normalize() 归一化**自身 value** (无参数), denormalize(x) 反查区间值"""
        p = _param(min_value=0, max_value=100, value=25)
        assert p.normalize() == pytest.approx(0.25)
        assert p.denormalize(0.5) == pytest.approx(50)


class TestFilterPreset:
    """测试预设 (真实构造: id/name/category/style/software_support)"""

    def test_preset_creation(self):
        preset = _preset(name="Cinematic Look", description="Cinematic grading")
        assert preset.name == "Cinematic Look"
        assert preset.category == FilterCategory.STYLIZE
        assert preset.style == FilterStyle.GLOW
        assert SoftwareType.AFTER_EFFECTS in preset.software_support

    def test_preset_intensity_default(self):
        assert _preset().intensity == 1.0

    def test_preset_to_dict_has_schema_keys(self):
        d = _preset().to_dict()
        for k in ("id", "name", "category", "style", "software_support",
                  "params", "intensity", "description", "author", "version", "tags"):
            assert k in d, k


class TestFilterChainItem:
    """测试滤镜链项目 (真实字段: preset/opacity/blend_mode/enabled)"""

    def test_chain_item_creation(self):
        item = FilterChainItem(preset=_preset(), opacity=50.0)
        assert item.preset.name == "Glow"
        assert item.opacity == 50.0

    def test_chain_item_defaults_enabled(self):
        assert FilterChainItem(preset=_preset()).enabled is True

    def test_chain_item_disabled(self):
        assert FilterChainItem(preset=_preset(), enabled=False).enabled is False

    def test_chain_item_default_blend_mode(self):
        assert FilterChainItem(preset=_preset()).blend_mode == BlendMode.NORMAL


class TestFilterRecommendation:
    """测试滤镜推荐 (真实字段: preset/confidence/reason/priority)"""

    def test_recommendation_creation(self):
        rec = FilterRecommendation(preset=_preset(), confidence=0.85,
                                   reason="Add film texture")
        assert rec.preset.name == "Glow"
        assert rec.confidence == 0.85
        assert rec.reason == "Add film texture"

    def test_recommendation_default_priority(self):
        assert FilterRecommendation(preset=_preset(), confidence=0.5,
                                    reason="r").priority == 0


class TestFilterPresetLibrary:
    """测试预设库 (初版把这个能力错记在虚构的 SoftwareAdapter 上)"""

    def test_library_ships_builtin_presets(self):
        """内置预设库非空 —— 2026-09-19 实测 95 个 (初版断言"初始为空"系虚构)"""
        presets = FilterPresetLibrary().get_all_presets()
        assert len(presets) >= 50
        assert all(isinstance(p, FilterPreset) for p in presets[:5])

    def test_add_and_get_preset(self):
        lib = FilterPresetLibrary()
        lib.add_preset(_preset(id="glow1", name="Glow"))
        assert lib.get_preset("glow1").name == "Glow"

    def test_get_missing_preset(self):
        with pytest.raises(FilterNotFoundError):
            FilterPresetLibrary().get_preset("definitely_missing")

    def test_category_query(self):
        """按分类检索返回子集"""
        lib = FilterPresetLibrary()
        got = lib.get_category_presets(FilterCategory.COLOR_CORRECTION)
        assert all(p.category == FilterCategory.COLOR_CORRECTION for p in got)


class TestFilterChain:
    """测试滤镜链容器 (add_filter 收 FilterPreset, 返回索引)"""

    def test_chain_add_returns_index(self):
        chain = FilterChain()
        assert chain.add_filter(_preset()) == 0
        assert chain.add_filter(_preset(id="p2")) == 1

    def test_chain_get_filter_by_index(self):
        chain = FilterChain()
        chain.add_filter(_preset(name="Glow"))
        item = chain.get_filter(0)
        assert isinstance(item, FilterChainItem)
        assert item.preset.name == "Glow"
        assert item.enabled is True          # 新入链项默认启用

    def test_chain_get_enabled_filters_excludes_disabled(self):
        chain = FilterChain()
        chain.add_filter(_preset())
        chain.add_filter(_preset(id="p2"))
        chain.get_filter(0).enabled = False  # 通过条目关闭第一个
        assert len(chain.get_enabled_filters()) == 1
        assert len(chain.get_filters()) == 2  # 总表仍含禁用项

    def test_chain_clear(self):
        chain = FilterChain()
        chain.add_filter(_preset())
        chain.clear()
        assert chain.get_filters() == []


class TestParameterValidation:
    """测试引擎级参数校验 (validate_params(name, params) -> bool / 抛异常)"""

    def test_valid_params_accepted(self):
        engine = AEFilterEngine()
        info = engine.get_filter_info("Glow")
        # 用该滤镜真实存在的第一个参数做正向用例
        first = next(iter(info["params"]))
        assert engine.validate_params(
            "Glow", {first: info["params"][first]["default"]}) is True

    def test_empty_params_accepted(self):
        assert AEFilterEngine().validate_params("Glow", {}) is True

    def test_unknown_filter_raises(self):
        with pytest.raises(FilterNotFoundError):
            AEFilterEngine().validate_params("NoSuchFilter", {})

    def test_unknown_param_raises(self):
        with pytest.raises(InvalidParameterError):
            AEFilterEngine().validate_params("Glow", {"definitely_not_a_param": 1})


class TestEdgeCases:
    """边界与编码"""

    def test_empty_filter_name_raises(self):
        with pytest.raises(FilterNotFoundError):
            AEFilterEngine().get_filter_info("")

    def test_unicode_in_description_preserved(self):
        p = _preset(name="电影感", description="高对比 + 柔光 · 教程")
        assert p.description == "高对比 + 柔光 · 教程"
        assert p.to_dict()["name"] == "电影感"

    def test_params_is_name_to_param_mapping(self):
        """params 是 {参数名: FilterParam} 字典, to_dict 逐项 asdict"""
        d = _preset(params={"radius": _param(name="radius", value=7)}).to_dict()
        assert set(d["params"]) == {"radius"}
        assert d["params"]["radius"]["value"] == 7

    def test_enum_value_types(self):
        """枚举 .value 均为 str (跨进程序列化前提)"""
        for enum_cls in (FilterCategory, FilterStyle, SoftwareType):
            for member in enum_cls:
                assert isinstance(member.value, str)
