"""核心 god 文件 characterization（特征/黄金基准）测试网。

背景（2026-09-14 全景审计 H1 + A5 覆盖率）：
    core/filter_engine.py(5504 行) / core/transition_engine.py(4993 行) /
    core/text_animation_engine.py(3693 行) 在审计时**单元覆盖率均为 0.00%**。
    在零覆盖的巨文件上直接重构（分解/改名/改返回值）= 盲飞（Feathers《修改代码的
    艺术》铁律）。本文件先建"安全网"：把这三个模块**当前可观察行为**固化为断言，
    使后续分解一旦改变行为立即红灯。

设计原则：
    - **只测真实可观察行为**（枚举成员数、纯函数数值、公共 API 返回类型/键集/标记），
      不测私有实现细节，避免重构时产生误报噪音。
    - 数值用精确黄金值（pytest.approx）钉死——缓动/关键帧是确定性纯函数，最适合当网。
    - 若某断言因**有意**行为变更而失败，应更新本基准并在 commit 说明中记录，
      而非删除断言。

覆盖范围（本批）：
    - transition_engine.EasingEngine：34 种缓动 + 端点不变量 + generate_keyframes
    - transition_engine.TransitionPreset：序列化往返
    - filter_engine.FilterParam / FilterPreset：范围校验、归一化、强度缩放、深拷贝
    - filter_engine.AEFilterEngine：滤镜清单/分类/信息/脚本生成
    - text_animation_engine.AETextAnimator：动画生成、JSX 生成、预设库
"""
from __future__ import annotations

import math

import pytest

from core.filter_engine import (
    AEFilterEngine,
    FFmpegFilterEngine,
    FilterAI,
    FilterCategory,
    FilterParam,
    FilterPreset,
    FilterPresetLibrary,
    FilterRecommendation,
    FilterStyle,
    SceneType,
    SoftwareType,
    UnifiedFilterAPI,
)
from core.text_animation_engine import (
    AETextAnimator,
    AnimationParams,
    FontInfo,
    FontRegistry,
    TextAnimationPreset,
    TextAnimationType,
    TextStyle,
    TypographyEngine,
    UnifiedTextAPI,
)
from core.text_animation_engine import SoftwareTarget as TextSoftwareTarget
from core.transition_engine import (
    AETransitionEngine,
    EasingEngine,
    PresetLibrary,
    SoftwareTarget,
    TransitionAI,
    TransitionCategory,
    TransitionPreset,
    TransitionStyle,
    UnifiedTransitionAPI,
)

# ============================================================================
# transition_engine.EasingEngine
# ============================================================================


class TestEasingEngineCharacterization:
    """缓动引擎的确定性行为基准。"""

    # 审计实测: 34 种缓动（baseConfig + quad/cubic/quart/quint/sine/expo/circ/back/bounce/elastic）
    EXPECTED_EASING_COUNT = 34

    KNOWN_EASINGS = (
        "linear",
        "ease_in",
        "ease_out",
        "ease_in_out",
        "ease_in_quad",
        "ease_out_cubic",
        "ease_in_out_sine",
        "ease_in_out_back",
        "ease_out_bounce",
        "ease_in_out_elastic",
    )

    @pytest.fixture
    def engine(self) -> EasingEngine:
        return EasingEngine()

    def test_available_easing_count(self, engine: EasingEngine) -> None:
        """缓动种类数量钉死：新增/删除缓动必须显式更新基准。"""
        assert len(engine.get_available_easings()) == self.EXPECTED_EASING_COUNT

    def test_known_easings_present(self, engine: EasingEngine) -> None:
        available = engine.get_available_easings()
        missing = [name for name in self.KNOWN_EASINGS if name not in available]
        assert missing == [], f"缺失缓动: {missing}"

    def test_all_easings_have_unit_endpoints(self, engine: EasingEngine) -> None:
        """不变量：每种缓动 f(0)==0 且 f(1)==1（审计实测 34 种全部满足）。"""
        anomalies = []
        for name in engine.get_available_easings():
            start = engine.map_progress(0.0, name)
            end = engine.map_progress(1.0, name)
            if not (math.isfinite(start) and math.isfinite(end)):
                anomalies.append((name, "non-finite"))
            elif abs(start - 0.0) > 1e-9 or abs(end - 1.0) > 1e-9:
                anomalies.append((name, start, end))
        assert anomalies == [], f"端点不变量被破坏: {anomalies}"

    def test_progress_is_clamped(self, engine: EasingEngine) -> None:
        """越界进度被夹到 [0,1]，而非外推。"""
        assert engine.map_progress(-3.0, "linear") == 0.0
        assert engine.map_progress(9.0, "linear") == 1.0
        assert engine.map_progress(0.5, "linear") == pytest.approx(0.5)

    def test_unknown_easing_falls_back_to_linear(self, engine: EasingEngine) -> None:
        """未知缓动名降级为恒等（返回夹取后的 t）。"""
        assert engine.map_progress(0.4, "definitely-not-an-easing") == pytest.approx(0.4)
        assert engine.get_easing_function("definitely-not-an-easing")(0.4) == pytest.approx(0.4)

    @pytest.mark.parametrize(
        "easing_type,expected_quarter,expected_half,expected_three_quarter",
        [
            ("linear", 0.25, 0.5, 0.75),
            ("ease_in_quad", 0.0625, 0.25, 0.5625),
            ("ease_out_cubic", 0.578125, 0.875, 0.984375),
            ("ease_in_out_sine", 0.146446609, 0.5, 0.853553391),
            ("ease_out_bounce", 0.47265625, 0.765625, 0.97265625),
            ("ease_out_elastic", 0.911611652, 1.015625, 1.005524272),
            ("ease_in_out_back", -0.099681844, 0.5, 1.099681844),
        ],
    )
    def test_golden_easing_values(
        self,
        engine: EasingEngine,
        easing_type: str,
        expected_quarter: float,
        expected_half: float,
        expected_three_quarter: float,
    ) -> None:
        """黄金数值：钉死数学实现（含 back/elastic 的越界特性）。"""
        assert engine.map_progress(0.25, easing_type) == pytest.approx(expected_quarter, abs=1e-6)
        assert engine.map_progress(0.5, easing_type) == pytest.approx(expected_half, abs=1e-6)
        assert engine.map_progress(0.75, easing_type) == pytest.approx(expected_three_quarter, abs=1e-6)

    def test_generate_keyframes_linear(self, engine: EasingEngine) -> None:
        assert engine.generate_keyframes(0.0, 100.0, 5, "linear") == pytest.approx(
            [0.0, 25.0, 50.0, 75.0, 100.0]
        )

    def test_generate_keyframes_ease_in_out(self, engine: EasingEngine) -> None:
        assert engine.generate_keyframes(0.0, 100.0, 5, "ease_in_out") == pytest.approx(
            [0.0, 12.5, 50.0, 87.5, 100.0]
        )

    def test_generate_keyframes_edge_counts(self, engine: EasingEngine) -> None:
        """frame_count<=0 → 空；==1 → 仅起始值；不做除零。"""
        assert engine.generate_keyframes(0.0, 1.0, 0) == []
        assert engine.generate_keyframes(0.0, 1.0, -2) == []
        assert engine.generate_keyframes(10.0, 20.0, 1) == [10.0]


class TestTransitionPresetCharacterization:
    """过渡预设序列化契约。"""

    def _preset(self) -> TransitionPreset:
        return TransitionPreset(
            id="t1",
            name="Dissolve",
            category=TransitionCategory.DISSOLVE,
            style=TransitionStyle.SOFT,
            software_support=[SoftwareTarget.AFTER_EFFECTS],
            params={"softness": 0.5},
            tags=["a"],
        )

    def test_to_dict_shape(self) -> None:
        d = self._preset().to_dict()
        assert set(d) == {
            "id", "name", "category", "style", "duration",
            "easing", "software_support", "params", "description", "tags",
        }
        # 枚举展开为 .value 字符串
        assert d["category"] == "dissolve"
        assert d["style"] == "soft"
        assert d["software_support"] == ["after_effects"]
        assert d["duration"] == pytest.approx(0.5)
        assert d["easing"] == "ease_in_out"

    def test_round_trip_is_stable(self) -> None:
        d = self._preset().to_dict()
        assert TransitionPreset.from_dict(d).to_dict() == d


# ============================================================================
# filter_engine 数据类
# ============================================================================


class TestFilterParamCharacterization:
    def test_validate_range(self) -> None:
        assert FilterParam(name="b", value=5.0, min_value=0.0, max_value=10.0).validate() is True
        assert FilterParam(name="b", value=20.0, min_value=0.0, max_value=10.0).validate() is False
        assert FilterParam(name="b", value=-1.0, min_value=0.0, max_value=10.0).validate() is False

    def test_non_numeric_types_always_valid(self) -> None:
        assert FilterParam(name="col", value=[1, 2, 3], param_type="color").validate() is True
        assert FilterParam(name="s", value="x", param_type="string").validate() is True

    def test_normalize(self) -> None:
        assert FilterParam(name="b", value=5.0, min_value=0.0, max_value=10.0).normalize() == pytest.approx(0.5)
        assert FilterParam(name="b", value=5, min_value=0, max_value=10, param_type="int").normalize() == pytest.approx(0.5)
        # max==min 退化区间 → 0.0（不除零）
        assert FilterParam(name="c", value=3, min_value=2, max_value=2).normalize() == 0.0

    def test_denormalize_casts_int(self) -> None:
        assert FilterParam(name="b", value=0.0, min_value=0.0, max_value=10.0).denormalize(0.5) == pytest.approx(5.0)
        # int 参数还原后取整（0 + 0.55*10 = 5.5 → 5）
        assert FilterParam(name="i", value=0, min_value=0, max_value=10, param_type="int").denormalize(0.55) == 5


class TestFilterPresetCharacterization:
    def _preset(self) -> FilterPreset:
        return FilterPreset(
            id="p1",
            name="Blur",
            category=FilterCategory.BLUR_SHARPEN,
            style=FilterStyle.CINEMATIC,
            software_support=[SoftwareType.AFTER_EFFECTS],
            params={"blur": FilterParam(name="blur", value=5.0, min_value=0.0, max_value=10.0)},
        )

    def test_to_dict_shape(self) -> None:
        d = self._preset().to_dict()
        assert set(d) == {
            "id", "name", "category", "style", "software_support", "params",
            "intensity", "description", "author", "version", "tags",
        }
        assert d["category"] == "blur_sharpen"
        assert d["style"] == "cinematic"
        assert d["software_support"] == ["after_effects"]
        # 参数被 asdict 展开
        assert d["params"]["blur"]["name"] == "blur"
        assert d["params"]["blur"]["value"] == pytest.approx(5.0)

    def test_round_trip_is_stable(self) -> None:
        d = self._preset().to_dict()
        assert FilterPreset.from_dict(d).to_dict() == d

    def test_copy_is_deep(self) -> None:
        """copy() 必须是深拷贝：改副本不得污染原件。"""
        original = self._preset()
        clone = original.copy()
        clone.params["blur"].value = 9.9
        assert original.params["blur"].value == pytest.approx(5.0)
        assert clone.params["blur"].value == pytest.approx(9.9)

    def test_apply_intensity_scales_from_min(self) -> None:
        """强度以 min_value 为锚缩放：value = min + (value-min)*intensity。"""
        preset = self._preset()
        preset.apply_intensity(0.5)
        assert preset.intensity == pytest.approx(0.5)
        assert preset.params["blur"].value == pytest.approx(2.5)  # 0 + (5-0)*0.5

    def test_apply_intensity_clamps_to_unit(self) -> None:
        preset = self._preset()
        preset.apply_intensity(5.0)
        assert preset.intensity == pytest.approx(1.0)
        preset.apply_intensity(-1.0)
        assert preset.intensity == pytest.approx(0.0)


# ============================================================================
# filter_engine.AEFilterEngine（注册表 + 脚本生成）
# ============================================================================


class TestAEFilterEngineCharacterization:
    EXPECTED_FILTER_COUNT = 80

    @pytest.fixture
    def engine(self) -> AEFilterEngine:
        return AEFilterEngine()

    def test_available_filter_inventory(self, engine: AEFilterEngine) -> None:
        """滤镜总数钉死（分解/改名时若丢失注册项立即红灯）。"""
        available = engine.get_available_filters()
        assert len(available) == self.EXPECTED_FILTER_COUNT
        assert available[:3] == ["Curves", "Levels", "Hue_Saturation"]

    def test_category_getters_are_subsets(self, engine: AEFilterEngine) -> None:
        available = set(engine.get_available_filters())
        for getter in (
            engine.get_color_correction_filters,
            engine.get_blur_sharpen_filters,
            engine.get_distort_filters,
            engine.get_stylize_filters,
            engine.get_generate_filters,
            engine.get_keying_filters,
            engine.get_perspective_filters,
            engine.get_simulation_filters,
            engine.get_transition_filters,
            engine.get_noise_grain_filters,
        ):
            subset = getter()
            assert isinstance(subset, list)
            assert set(subset) <= available

    def test_category_counts_baseline(self, engine: AEFilterEngine) -> None:
        # 审计实测：这四类各 8 项
        assert len(engine.get_color_correction_filters()) == 8
        assert len(engine.get_blur_sharpen_filters()) == 8
        assert len(engine.get_distort_filters()) == 8
        assert len(engine.get_stylize_filters()) == 8

    def test_filter_info_shape(self, engine: AEFilterEngine) -> None:
        info = engine.get_filter_info(engine.get_available_filters()[0])
        assert set(info) == {"category", "description", "params"}

    def test_merge_params_overlays_override(self, engine: AEFilterEngine) -> None:
        merged = engine._merge_params(engine.get_available_filters()[0], {"__probe__": 1})
        assert isinstance(merged, dict)
        assert merged["__probe__"] == 1

    def test_validate_params_default_ok(self, engine: AEFilterEngine) -> None:
        assert engine.validate_params(engine.get_available_filters()[0], {}) is True

    def test_generate_script_returns_marked_string(self, engine: AEFilterEngine) -> None:
        script = engine.generate_script(
            [(engine.get_available_filters()[0], {})], layer_name="L"
        )
        assert isinstance(script, str) and len(script) > 0
        assert "// Auto-generated AE Filter Script" in script


# ============================================================================
# text_animation_engine.AETextAnimator
# ============================================================================


class TestTextAnimationEngineCharacterization:
    def test_animation_type_count(self) -> None:
        assert len(list(TextAnimationType)) == 24

    def test_text_style_field_contract(self) -> None:
        assert set(TextStyle.__dataclass_fields__) == {
            "font_family", "font_size", "font_weight", "font_style", "fill_color",
            "stroke_color", "stroke_width", "letter_spacing", "line_spacing",
            "paragraph_align", "tracking", "leading", "baseline_shift",
        }

    def test_animation_params_field_contract(self) -> None:
        assert set(AnimationParams.__dataclass_fields__) == {
            "start_delay", "duration", "easing", "intensity", "direction", "offset",
            "per_char_delay", "blur_amount", "scale_factor", "rotation_degrees",
            "bounce_count", "wave_amplitude", "wave_frequency", "glitch_intensity",
        }

    def test_apply_animation_emits_layer_reference(self) -> None:
        animator = AETextAnimator()
        script = animator.apply_animation("Layer1", TextAnimationType.FADE_IN)
        assert isinstance(script, str) and len(script) > 0
        assert "Layer1" in script

    def test_generate_jsx_marker(self) -> None:
        jsx = AETextAnimator().generate_jsx("Hello")
        assert isinstance(jsx, str)
        # 脚本以块注释头开始，头部标记文案钉死
        assert jsx.startswith("/*")
        assert "AE Text Animation Generator" in jsx

    def test_preset_library_and_round_trip(self) -> None:
        presets = AETextAnimator().get_presets()
        assert len(presets) == 15
        assert all(isinstance(p, TextAnimationPreset) for p in presets)
        d = presets[0].to_dict()
        assert TextAnimationPreset.from_dict(d).to_dict() == d


# ============================================================================
# transition_engine 门面层（跨软件 API / 预设库 / AI 推荐）
# ============================================================================


class TestTransitionFacadeLayerCharacterization:
    EXPECTED_PRESET_COUNT = 107

    def test_preset_library_inventory(self) -> None:
        library = PresetLibrary()
        assert library.count_presets() == self.EXPECTED_PRESET_COUNT
        assert len(library.list_all_presets()) == self.EXPECTED_PRESET_COUNT
        # 首预设 id 钉死（分解时若 id 生成逻辑变化会立即暴露）
        assert library.get_preset("crossfade_standard") is not None

    def test_preset_library_category_query(self) -> None:
        """分类索引返回 category -> 预设列表 的 dict。"""
        index = PresetLibrary().get_presets_by_category()
        assert isinstance(index, dict)
        assert TransitionCategory.DISSOLVE in index
        assert isinstance(index[TransitionCategory.DISSOLVE], list)

    def test_transition_ai_scene_recommendation(self) -> None:
        """AI 推荐返回 (预设, 置信度) 元组列表。"""
        results = TransitionAI().recommend_by_scene("cinematic")
        assert isinstance(results, list) and len(results) > 0
        preset, confidence = results[0]
        assert isinstance(preset, TransitionPreset)
        assert isinstance(confidence, float)

    def test_unified_api_supported_software(self) -> None:
        supported = UnifiedTransitionAPI().get_supported_software("crossfade_standard")
        assert supported == [
            SoftwareTarget.AFTER_EFFECTS,
            SoftwareTarget.PREMIERE_PRO,
            SoftwareTarget.DAVINCI_RESOLVE,
            SoftwareTarget.BLENDER,
            SoftwareTarget.FFMPEG,
        ]

    def test_unified_api_apply_transition_emits_script(self) -> None:
        script = UnifiedTransitionAPI().apply_transition(
            SoftwareTarget.AFTER_EFFECTS, "crossfade_standard", "A", "B", 0.0, 1.0
        )
        assert isinstance(script, str) and len(script) > 0

    def test_ae_engine_crossfade_emits_script(self) -> None:
        script = AETransitionEngine().create_crossfade("A", "B", 0.0, 1.0)
        assert isinstance(script, str) and len(script) > 0


# ============================================================================
# filter_engine 门面层
# ============================================================================


class TestFilterFacadeLayerCharacterization:
    EXPECTED_PRESET_COUNT = 95

    def test_preset_library_inventory(self) -> None:
        library = FilterPresetLibrary()
        assert len(library.get_all_presets()) == self.EXPECTED_PRESET_COUNT
        # 分类/风格索引是 dict（category/style -> 预设列表）
        assert isinstance(library.get_preset_categories(), dict)
        assert isinstance(library.get_preset_styles(), dict)

    def test_unified_api_supported_software(self) -> None:
        assert UnifiedFilterAPI().get_available_software() == [
            SoftwareType.AFTER_EFFECTS,
            SoftwareType.DAVINCI_RESOLVE,
            SoftwareType.BLENDER,
            SoftwareType.FFMPEG,
        ]

    def test_unified_api_engine_dispatch(self) -> None:
        assert isinstance(UnifiedFilterAPI().get_engine(SoftwareType.AFTER_EFFECTS), AEFilterEngine)

    def test_unified_api_preset_library_shared(self) -> None:
        assert isinstance(UnifiedFilterAPI().get_preset_library(), FilterPresetLibrary)

    def test_unified_api_generate_script(self) -> None:
        script = UnifiedFilterAPI().generate_script(SoftwareType.AFTER_EFFECTS, [("Curves", {})])
        assert isinstance(script, str) and len(script) > 0

    def test_filter_ai_recommendations(self) -> None:
        ai = FilterAI()
        by_style = ai.recommend_by_style(FilterStyle.CINEMATIC)
        assert len(by_style) == 10
        assert all(isinstance(r, FilterRecommendation) for r in by_style)
        by_scene = ai.recommend_by_scene(SceneType.CINEMATIC)
        assert len(by_scene) == 5

    def test_ffmpeg_engine_filter_partition(self) -> None:
        engine = FFmpegFilterEngine()
        assert len(engine.get_available_filters()) == 34
        assert len(engine.get_video_filters()) == 25
        assert len(engine.get_audio_filters()) == 9

    def test_ffmpeg_engine_generate_command(self) -> None:
        engine = FFmpegFilterEngine()
        command = engine.generate_command(engine.get_video_filters()[0], {})
        assert isinstance(command, str) and len(command) > 0


# ============================================================================
# text_animation_engine 门面层
# ============================================================================


class TestTextFacadeLayerCharacterization:
    def test_font_registry_inventory(self) -> None:
        fonts = FontRegistry().list_fonts()
        assert len(fonts) > 0
        assert all(isinstance(f, FontInfo) for f in fonts)
        assert fonts[0].name == "Arial"

    def test_typography_letter_spacing(self) -> None:
        assert TypographyEngine().calculate_letter_spacing(16) == pytest.approx(0.0)

    def test_typography_wcag_contrast_shape(self) -> None:
        """只钉返回结构不钉数值——当前 ratio 超出 WCAG 理论上限(≤21)，
        疑似既有缺陷；若将来修正，本断言应保持通过（仅结构契约）。"""
        result = TypographyEngine().check_wcag_contrast((255, 255, 255), (0, 0, 0))
        assert set(result) == {
            "contrast_ratio", "level", "passes_normal_text",
            "passes_large_text", "threshold_normal", "threshold_large", "recommendation",
        }

    def test_unified_text_api_emits_script(self) -> None:
        api = UnifiedTextAPI()
        created = api.create_text("Hi", TextSoftwareTarget.AFTER_EFFECTS)
        exported = api.export_to_software("Hi", TextSoftwareTarget.AFTER_EFFECTS)
        assert isinstance(created, str) and len(created) > 0
        assert isinstance(exported, str) and len(exported) > 0
