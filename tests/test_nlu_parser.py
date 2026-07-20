"""nlu_parser 模块单元测试

覆盖范围:
- NLUParser.parse() 各类意图识别（ADD_EFFECT, CREATE_ANIM, ADJUST_PARAM, CREATE_LAYER, STYLE_COMBO, REVERSE_ANALYZE）
- Slot 提取器正确性（效果名、动画类型、参数调整、图层类型、风格名）
- 空输入与无匹配 fallback
- needs_clarification() 置信度阈值判断
- ProjectContext 上下文集成（selectedLayers 自动填充 targetLayer）
- 颜色/时间/目标图层提取辅助函数
- 边界条件（特殊字符、混合输入、大小写）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from nlu_parser import (
    NLUParser,
    Intent,
    IntentSlots,
    IntentType,
    ConfidenceThresholds,
    ProjectContext,
    nlu_parser,
)


# ============================================================================
# parse() — ADD_EFFECT
# ============================================================================

class TestParseAddEffect:
    def test_add_glow(self):
        intent = nlu_parser.parse("加一个发光效果")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.confidence == 0.85
        assert intent.slots.effectName == "发光"

    def test_add_blur(self):
        intent = nlu_parser.parse("添加模糊")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.effectName == "模糊"

    def test_add_particle(self):
        intent = nlu_parser.parse("加粒子")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.effectName == "粒子"

    def test_add_effect_english(self):
        intent = nlu_parser.parse("apply glow effect")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.effectName == "glow"

    def test_add_effect_with_target_layer(self):
        intent = nlu_parser.parse("给文字加发光")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.targetLayer == "text"

    def test_add_effect_to_selected(self):
        intent = nlu_parser.parse("给选中图层添加模糊")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.targetLayer == "selected"


# ============================================================================
# parse() — CREATE_ANIM
# ============================================================================

class TestParseCreateAnim:
    def test_create_bounce_in(self):
        intent = nlu_parser.parse("做一个弹入动画")
        assert intent.type == IntentType.CREATE_ANIM
        assert intent.confidence == 0.85
        assert "弹入" in intent.slots.animType or intent.slots.animType == "弹入"

    def test_create_fade_slide_english(self):
        intent = nlu_parser.parse("create a fade in animation")
        assert intent.type == IntentType.CREATE_ANIM
        assert "fade" in intent.slots.animType.lower()

    def test_bounce_in_direct(self):
        intent = nlu_parser.parse("文字弹入")
        assert intent.type == IntentType.CREATE_ANIM


# ============================================================================
# parse() — ADJUST_PARAM
# ============================================================================

class TestParseAdjustParam:
    def test_increase_strength(self):
        intent = nlu_parser.parse("发光调大")
        assert intent.type == IntentType.ADJUST_PARAM
        assert intent.slots.paramName == "发光"
        assert intent.slots.adjustDirection == "increase"

    def test_decrease_strength(self):
        intent = nlu_parser.parse("模糊调小一点")
        assert intent.type == IntentType.ADJUST_PARAM
        assert intent.slots.adjustDirection == "decrease"

    def test_adjust_with_amount(self):
        intent = nlu_parser.parse("调节 亮度 为 80%")
        assert intent.type == IntentType.ADJUST_PARAM
        # 正则分组仅捕获数字部分，% 符号在分支外
        assert intent.slots.adjustAmount == "80"

    def test_adjust_set_direction(self):
        intent = nlu_parser.parse("调节 对比度 为 50")
        assert intent.type == IntentType.ADJUST_PARAM
        # 数字默认被解析为 increase 方向
        assert intent.slots.adjustDirection == "increase"


# ============================================================================
# parse() — CREATE_LAYER
# ============================================================================

class TestParseCreateLayer:
    def test_create_comp(self):
        intent = nlu_parser.parse("创建一个合成")
        assert intent.type == IntentType.CREATE_LAYER
        assert intent.slots.targetLayer == "composition"

    def test_add_null(self):
        intent = nlu_parser.parse("加个空对象")
        assert intent.type == IntentType.CREATE_LAYER
        assert intent.slots.targetLayer == "null"

    def test_add_text_layer(self):
        intent = nlu_parser.parse("添加文字层")
        assert intent.type == IntentType.CREATE_LAYER
        assert intent.slots.targetLayer == "text"

    def test_add_adjustment_english(self):
        intent = nlu_parser.parse("add a adjustment")
        assert intent.type == IntentType.CREATE_LAYER
        assert intent.slots.targetLayer == "adjustment"


# ============================================================================
# parse() — STYLE_COMBO
# ============================================================================

class TestParseStyleCombo:
    def test_style_name(self):
        intent = nlu_parser.parse("做一个电影感风格")
        assert intent.type == IntentType.STYLE_COMBO
        assert intent.slots.styleName == "电影感"

    def test_style_simple(self):
        intent = nlu_parser.parse("赛博朋克风格")
        assert intent.type == IntentType.STYLE_COMBO
        assert intent.slots.styleName == "赛博朋克"


# ============================================================================
# parse() — REVERSE_ANALYZE
# ============================================================================

class TestParseReverseAnalyze:
    def test_reverse_analyze_chinese(self):
        intent = nlu_parser.parse("这个效果怎么做")
        assert intent.type == IntentType.REVERSE_ANALYZE
        assert intent.confidence == 0.85

    def test_analyze_video(self):
        intent = nlu_parser.parse("分析一下这段视频")
        assert intent.type == IntentType.REVERSE_ANALYZE

    def test_how_to_make_english(self):
        intent = nlu_parser.parse("how to make this effect")
        assert intent.type == IntentType.REVERSE_ANALYZE


# ============================================================================
# parse() — 边界与 Fallback
# ============================================================================

class TestParseEdgeCases:
    def test_empty_input(self):
        intent = nlu_parser.parse("")
        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence == 0.0

    def test_whitespace_only(self):
        intent = nlu_parser.parse("   ")
        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence == 0.0

    def test_unknown_input(self):
        intent = nlu_parser.parse("今天天气不错")
        assert intent.type == IntentType.UNKNOWN
        assert intent.confidence == 0.2

    def test_fallback_effect_match(self):
        intent = nlu_parser.parse("我想要一个glow效果")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.confidence == 0.55
        assert intent.slots.effectName == "glow"

    def test_fallback_blur_match(self):
        # 使用无法被主 pattern 精确匹配、但能被 fallback 正则捕获的输入
        intent = nlu_parser.parse("效果里有个blur和glow混合")
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.confidence == 0.55
        assert intent.slots.effectName == "blur"

    def test_case_insensitive(self):
        intent1 = nlu_parser.parse("添加GLOW")
        intent2 = nlu_parser.parse("添加glow")
        assert intent1.type == intent2.type == IntentType.ADD_EFFECT


# ============================================================================
# needs_clarification()
# ============================================================================

class TestNeedsClarification:
    def test_unknown_needs_clarification(self):
        intent = Intent(type=IntentType.UNKNOWN, confidence=0.0, slots=IntentSlots(), rawInput="")
        assert nlu_parser.needs_clarification(intent) is True

    def test_high_confidence_no_clarification(self):
        intent = Intent(type=IntentType.ADD_EFFECT, confidence=0.9, slots=IntentSlots(), rawInput="")
        assert nlu_parser.needs_clarification(intent) is False

    def test_low_confidence_needs_clarification(self):
        intent = Intent(type=IntentType.ADD_EFFECT, confidence=0.5, slots=IntentSlots(), rawInput="")
        assert nlu_parser.needs_clarification(intent) is True

    def test_boundary_confidence(self):
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=ConfidenceThresholds.NO_CLARIFICATION,
            slots=IntentSlots(),
            rawInput="",
        )
        assert nlu_parser.needs_clarification(intent) is False


# ============================================================================
# ProjectContext 集成
# ============================================================================

class TestProjectContext:
    def test_selected_layers_fill_target(self):
        ctx = ProjectContext(selectedLayers=[{"name": "Layer1"}])
        intent = nlu_parser.parse("加发光", context=ctx)
        assert intent.type == IntentType.ADD_EFFECT
        assert intent.slots.targetLayer == "selected"

    def test_no_selected_layers_no_override(self):
        ctx = ProjectContext(selectedLayers=[])
        intent = nlu_parser.parse("给文字加发光", context=ctx)
        assert intent.slots.targetLayer == "text"

    def test_default_context_values(self):
        ctx = ProjectContext()
        assert ctx.compFrameRate == 30
        assert ctx.compDuration == 5.0
        assert ctx.activeCompName is None


# ============================================================================
# Slot 提取器细节
# ============================================================================

class TestSlotExtractors:
    def test_color_extraction_warm(self):
        assert nlu_parser._extract_color("暖色风格") == "暖色"

    def test_color_extraction_blue(self):
        assert nlu_parser._extract_color("蓝色调") == "蓝色"

    def test_color_extraction_none(self):
        assert nlu_parser._extract_color("普通效果") is None

    def test_temporal_extraction_start(self):
        assert nlu_parser._extract_temporal("在开头加效果") == "开头"

    def test_temporal_extraction_seconds(self):
        assert nlu_parser._extract_temporal("在5秒处加效果") == "5秒"

    def test_temporal_extraction_none(self):
        assert nlu_parser._extract_temporal("加效果") is None

    def test_target_layer_current(self):
        assert nlu_parser._extract_target_layer("当前图层加发光") == "current"

    def test_target_layer_none(self):
        assert nlu_parser._extract_target_layer("加发光") is None


# ============================================================================
# 全局单例
# ============================================================================

class TestGlobalParser:
    def test_global_parser_exists(self):
        assert nlu_parser is not None
        assert isinstance(nlu_parser, NLUParser)
