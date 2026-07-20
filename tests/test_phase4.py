import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNLUParser(unittest.TestCase):
    def test_parse_add_effect(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("加一个发光效果")
        self.assertEqual(intent.type, IntentType.ADD_EFFECT)
        self.assertEqual(intent.slots.effectName, "发光")
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("apply blur")
        self.assertEqual(intent.type, IntentType.ADD_EFFECT)
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("给文字层加模糊")
        self.assertEqual(intent.type, IntentType.ADD_EFFECT)
        self.assertEqual(intent.slots.effectName, "模糊")
        self.assertEqual(intent.slots.targetLayer, "text")

    def test_parse_create_anim(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("做一个弹入动画")
        self.assertEqual(intent.type, IntentType.CREATE_ANIM)
        self.assertEqual(intent.slots.animType, "弹入")
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("bounce in")
        self.assertEqual(intent.type, IntentType.CREATE_ANIM)
        self.assertGreater(intent.confidence, 0.7)

    def test_parse_adjust_param(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("亮度调大一点")
        self.assertEqual(intent.type, IntentType.ADJUST_PARAM)
        self.assertEqual(intent.slots.paramName, "亮度")
        self.assertEqual(intent.slots.adjustDirection, "increase")
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("对比度调小")
        self.assertEqual(intent.type, IntentType.ADJUST_PARAM)
        self.assertEqual(intent.slots.adjustDirection, "decrease")

    def test_parse_create_layer(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("创建一个固态层")
        self.assertEqual(intent.type, IntentType.CREATE_LAYER)
        self.assertEqual(intent.slots.targetLayer, "solid")
        self.assertGreater(intent.confidence, 0.8)
        
        intent = parser.parse("add adjustment layer")
        self.assertEqual(intent.type, IntentType.CREATE_LAYER)
        self.assertEqual(intent.slots.targetLayer, "adjustment")

    def test_parse_style_combo(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("做一个赛博朋克风格")
        self.assertEqual(intent.type, IntentType.STYLE_COMBO)
        self.assertEqual(intent.slots.styleName, "赛博朋克")
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("cinematic style")
        self.assertEqual(intent.type, IntentType.STYLE_COMBO)
        self.assertEqual(intent.slots.styleName, "cinematic")

    def test_parse_reverse_analyze(self):
        from nlu_parser import NLUParser, IntentType
        
        parser = NLUParser()
        
        intent = parser.parse("这个效果怎么做")
        self.assertEqual(intent.type, IntentType.REVERSE_ANALYZE)
        self.assertGreater(intent.confidence, 0.7)
        
        intent = parser.parse("reverse engineer")
        self.assertEqual(intent.type, IntentType.REVERSE_ANALYZE)

    def test_needs_clarification(self):
        from nlu_parser import NLUParser
        
        parser = NLUParser()
        
        intent = parser.parse("加效果")
        self.assertTrue(parser.needs_clarification(intent))
        
        intent = parser.parse("加一个发光效果到选中图层")
        self.assertFalse(parser.needs_clarification(intent))

    def test_slot_extraction(self):
        from nlu_parser import NLUParser
        
        parser = NLUParser()
        
        intent = parser.parse("给选中图层加蓝色发光效果")
        self.assertEqual(intent.slots.effectName, "发光")
        self.assertEqual(intent.slots.targetLayer, "selected")
        self.assertEqual(intent.slots.color, "蓝色")
        
        intent = parser.parse("在开头做一个弹入动画")
        self.assertEqual(intent.slots.temporal, "开头")


class TestEffectDescriptionParser(unittest.TestCase):
    def test_scan_vocab(self):
        from effect_description_parser import scan_vocab
        
        refs = scan_vocab("给我一个发光效果")
        self.assertGreater(len(refs), 0)
        glow_refs = [r for r in refs if "发光" in r.matchedKeyword]
        self.assertGreater(len(glow_refs), 0)

    def test_scan_colors(self):
        from effect_description_parser import scan_colors
        
        refs = scan_colors("暖色发光效果")
        self.assertGreater(len(refs), 0)
        warm_refs = [r for r in refs if r.temperature == "warm"]
        self.assertGreater(len(warm_refs), 0)

    def test_scan_intensity(self):
        from effect_description_parser import scan_intensity
        
        refs = scan_intensity("强烈的发光效果")
        self.assertGreater(len(refs), 0)
        self.assertEqual(refs[0].value, 0.8)
        
        refs = scan_intensity("微弱的模糊")
        self.assertEqual(refs[0].value, 0.3)

    def test_scan_temporal(self):
        from effect_description_parser import scan_temporal
        
        refs = scan_temporal("在开头做动画")
        self.assertGreater(len(refs), 0)
        self.assertEqual(refs[0].position, "start")
        
        refs = scan_temporal("结尾淡出")
        self.assertEqual(refs[0].position, "end")

    def test_parse(self):
        from effect_description_parser import EffectDescriptionParser
        
        parser = EffectDescriptionParser()
        
        desc = parser.parse("做一个强烈的赛博朋克风格发光效果", "STYLE_COMBO")
        self.assertGreater(len(desc.effectKeywords), 0)
        self.assertGreater(len(desc.intensityKeywords), 0)
        self.assertGreater(len(desc.styleKeywords), 0)

    def test_get_style_recipe(self):
        from effect_description_parser import get_style_recipe
        
        recipe = get_style_recipe("赛博朋克")
        self.assertIsNotNone(recipe)
        self.assertIn("effectIds", recipe)
        self.assertIn("description", recipe)

    def test_get_all_styles(self):
        from effect_description_parser import get_all_styles
        
        styles = get_all_styles()
        self.assertGreater(len(styles), 0)
        self.assertIn("赛博朋克", styles)
        self.assertIn("cinematic", styles)


class TestClarificationEngine(unittest.TestCase):
    def test_generate_questions(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        
        questions = engine.generate_questions(intent)
        self.assertGreater(len(questions), 0)

    def test_create_state(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        
        state = engine.create_state(intent)
        self.assertEqual(state.intent.type, IntentType.ADD_EFFECT)
        self.assertGreater(len(state.questions), 0)

    def test_answer_question(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        
        state = engine.create_state(intent)
        state = engine.answer_question(state, "发光")
        
        self.assertEqual(state.answered_slots.get("effectName"), "发光")
        self.assertEqual(state.current_question_index, 1)

    def test_has_more_questions(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        
        state = engine.create_state(intent)
        self.assertTrue(engine.has_more_questions(state))
        
        for _ in range(len(state.questions)):
            state = engine.answer_question(state, "test")
        
        self.assertFalse(engine.has_more_questions(state))

    def test_get_final_slots(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        intent = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        
        state = engine.create_state(intent)
        state = engine.answer_question(state, "发光")
        state = engine.answer_question(state, "选中图层")
        
        slots = engine.get_final_slots(state)
        self.assertEqual(slots.effectName, "发光")
        self.assertEqual(slots.targetLayer, "选中图层")

    def test_needs_clarification(self):
        from clarification_engine import ClarificationEngine
        from nlu_parser import Intent, IntentSlots, IntentType
        
        engine = ClarificationEngine()
        
        high_confidence = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.85,
            slots=IntentSlots(effectName="发光"),
            rawInput="加发光效果",
        )
        self.assertFalse(engine.needs_clarification(high_confidence))
        
        low_confidence = Intent(
            type=IntentType.ADD_EFFECT,
            confidence=0.5,
            slots=IntentSlots(),
            rawInput="加效果",
        )
        self.assertTrue(engine.needs_clarification(low_confidence))


class TestParameterOptimizer(unittest.TestCase):
    def test_optimize(self):
        from parameter_optimizer import ParameterOptimizer, ParameterContext
        
        optimizer = ParameterOptimizer()
        
        context = ParameterContext(
            effect_name="发光",
            style_name="cinematic",
            intensity=0.8,
        )
        
        result = optimizer.optimize(context)
        self.assertEqual(result.effect_name, "ADBE Glo2")
        self.assertGreater(len(result.settings), 0)
        self.assertGreater(result.confidence, 0.5)

    def test_resolve_effect_name(self):
        from parameter_optimizer import ParameterOptimizer, ParameterContext
        
        optimizer = ParameterOptimizer()
        
        ctx1 = ParameterContext(effect_name="发光")
        self.assertEqual(optimizer._resolve_effect_name(ctx1), "ADBE Glo2")
        
        ctx2 = ParameterContext(effect_name="blur")
        self.assertEqual(optimizer._resolve_effect_name(ctx2), "ADBE Gaussian Blur 2")
        
        ctx3 = ParameterContext(effect_name="高斯模糊")
        self.assertEqual(optimizer._resolve_effect_name(ctx3), "ADBE Gaussian Blur 2")

    def test_apply_intensity(self):
        from parameter_optimizer import ParameterOptimizer, ParameterContext
        
        optimizer = ParameterOptimizer()
        
        context = ParameterContext(
            effect_name="发光",
            intensity=1.0,
        )
        
        result = optimizer.optimize(context)
        settings = result.settings
        self.assertGreater(settings.get("Glow Intensity", 0), 0.5)

    def test_apply_color_temperature(self):
        from parameter_optimizer import ParameterOptimizer, ParameterContext
        
        optimizer = ParameterOptimizer()
        
        context = ParameterContext(
            effect_name="发光",
            color_temperature="暖色",
        )
        
        result = optimizer.optimize(context)
        settings = result.settings
        glow_color = settings.get("Glow Color")
        self.assertIsNotNone(glow_color)

    def test_apply_style_overrides(self):
        from parameter_optimizer import ParameterOptimizer, ParameterContext
        
        optimizer = ParameterOptimizer()
        
        context = ParameterContext(
            effect_name="发光",
            style_name="赛博朋克",
        )
        
        result = optimizer.optimize(context)
        settings = result.settings
        self.assertGreater(settings.get("Glow Intensity", 0), 0.5)

    def test_suggest_effects_for_style(self):
        from parameter_optimizer import ParameterOptimizer
        
        optimizer = ParameterOptimizer()
        
        effects = optimizer.suggest_effects_for_style("赛博朋克")
        self.assertGreater(len(effects), 0)


class TestAEAgentPipelinePhase4(unittest.TestCase):
    def test_parse_nlu(self):
        from ae_agent_pipeline import AEAgentPipeline
        
        pipeline = AEAgentPipeline()
        
        result = pipeline.parse_nlu("加一个发光效果")
        self.assertEqual(result["intent"], "ADD_EFFECT")
        self.assertGreater(result["confidence"], 0.7)
        self.assertEqual(result["slots"]["effectName"], "发光")

    def test_parse_effect_description(self):
        from ae_agent_pipeline import AEAgentPipeline
        
        pipeline = AEAgentPipeline()
        
        result = pipeline.parse_effect_description("强烈的赛博朋克发光效果")
        self.assertGreater(len(result["effectKeywords"]), 0)
        self.assertGreater(len(result["intensityKeywords"]), 0)

    def test_generate_clarification(self):
        from ae_agent_pipeline import AEAgentPipeline
        
        pipeline = AEAgentPipeline()
        
        intent = {"intent": "ADD_EFFECT", "confidence": 0.5, "slots": {}}
        result = pipeline.generate_clarification(intent)
        self.assertTrue(result["needs_clarification"])
        self.assertGreater(len(result["questions"]), 0)

    def test_optimize_parameters(self):
        from ae_agent_pipeline import AEAgentPipeline
        
        pipeline = AEAgentPipeline()
        
        result = pipeline.optimize_parameters(
            effect_name="发光",
            style_name="cinematic",
            intensity=0.8,
        )
        self.assertEqual(result["effect_name"], "ADBE Glo2")
        self.assertGreater(len(result["settings"]), 0)

    def test_nlu_to_effect(self):
        from ae_agent_pipeline import AEAgentPipeline
        
        pipeline = AEAgentPipeline()
        
        result = pipeline.nlu_to_effect("加一个强烈的发光效果")
        self.assertFalse(result["needs_clarification"])
        self.assertEqual(result["intent"]["intent"], "ADD_EFFECT")
        self.assertGreater(len(result["parameters"]["settings"]), 0)


if __name__ == "__main__":
    unittest.main()
