"""
pipeline/stages/compiler.py - 编译管线阶段
=============================================
将 compiler/ 包的 Phase 3-4 编译管线接入 UnifiedPipeline。

编译管线提供确定性路径（绕过 LLM）：
  自然语言 → 词汇映射(vocabulary_map) → 意图路由(intent_router)
  → 参数映射(parameter_mapper) → 操作列表(report_to_ops)
  → AE Bridge 执行

用法:
    config = PipelineConfig(use_compiler=True)
    pipe = UnifiedPipeline(config)
    pipe.run_all()
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CompilerStage:
    """编译管线阶段：确定性 NLU → 效果编译 → 操作列表"""

    def __init__(self, config):
        self.config = config
        self._vocab_map = None
        self._intent_router = None
        self._param_mapper = None
        self._report_to_ops = None

    def _load_modules(self):
        """延迟加载 compiler 模块"""
        if self._vocab_map is not None:
            return True

        try:
            try:
                from compiler.vocabulary_map import VocabularyMap
                from compiler.intent_router import IntentRouter
                from compiler.parameter_mapper import ParameterMapper
                from compiler.report_to_ops import ReportToOps
            except ImportError:
                from vocabulary_map import VocabularyMap
                from intent_router import IntentRouter
                from parameter_mapper import ParameterMapper
                from report_to_ops import ReportToOps

            self._vocab_map = VocabularyMap()
            self._intent_router = IntentRouter()
            self._param_mapper = ParameterMapper()
            self._report_to_ops = ReportToOps()
            return True
        except Exception as e:
            logger.warning(f"Compiler modules not available: {e}")
            return False

    def run(self, previous_data: Dict) -> Dict:
        """执行编译管线"""
        # 获取用户输入
        user_input = ""
        if hasattr(self.config, 'input_topic') and self.config.input_topic:
            user_input = self.config.input_topic
        elif hasattr(self.config, 'natural_language_input'):
            user_input = self.config.natural_language_input

        if not user_input:
            return {"error": "No input for compiler", "fallback": True}

        if not self._load_modules():
            return {"error": "Compiler modules unavailable", "fallback": True}

        result = {
            "compiler_used": True,
            "input": user_input,
            "vocab_refs": [],
            "intent": {},
            "report": {},
            "ops_list": [],
        }

        try:
            # Step 1: 词汇映射 - 自然语言 → 词汇引用
            vocab_refs = self._vocab_map.resolve(user_input)
            result["vocab_refs"] = [
                {"term": v.term, "ref_id": v.ref_id, "confidence": v.confidence}
                for v in vocab_refs
            ] if vocab_refs else []
            logger.info(f"Compiler: {len(result['vocab_refs'])} vocab refs resolved")

            # Step 2: 意图路由 - 词汇引用 → 意图分类
            intent = self._intent_router.route(vocab_refs)
            result["intent"] = {
                "type": intent.get("type", "unknown"),
                "subtasks": intent.get("subtasks", []),
                "confidence": intent.get("confidence", 0),
            }
            logger.info(f"Compiler: Intent = {result['intent']['type']}")

            # Step 3: 参数映射 - 词汇引用 → 效果参数
            mapped_params = self._param_mapper.map_all(vocab_refs)
            result["mapped_params"] = mapped_params

            # Step 4: 报告生成 - 参数 → AnalysisReport
            report = self._report_to_ops.convert(intent, mapped_params)
            result["report"] = {
                "effects": report.get("effects", []),
                "transitions": report.get("transitions", []),
                "keyframes": report.get("keyframes", []),
            }

            # Step 5: 操作编译 - Report → 操作列表
            ops = self._report_to_ops.to_ops(report)
            result["ops_list"] = ops
            logger.info(f"Compiler: {len(ops)} operations compiled")

            # 转换为管线可消费的格式
            result["script"] = self._ops_to_script(result)
            result["effect_stack"] = self._ops_to_effects(ops)
            result["transition_plan"] = self._ops_to_transitions(ops)

        except Exception as e:
            logger.error(f"Compiler pipeline error: {e}")
            result["error"] = str(e)
            result["fallback"] = True

        return result

    def _ops_to_script(self, compiler_result: Dict) -> Dict:
        """将编译结果转换为管线剧本格式"""
        return {
            "title": compiler_result.get("input", "Compiled Output"),
            "total_duration": 30,  # 默认
            "shots": [],
            "transitions": compiler_result.get("transition_plan", []),
            "effects": compiler_result.get("effect_stack", []),
            "source": "compiler",
        }

    def _ops_to_effects(self, ops: List) -> List[Dict]:
        """将操作列表转换为效果栈"""
        effects = []
        for op in ops:
            if op.get("type") == "effect":
                effects.append({
                    "name": op.get("effect_name", ""),
                    "match_name": op.get("match_name", ""),
                    "layer": op.get("layer", ""),
                    "params": op.get("params", {}),
                })
        return effects

    def _ops_to_transitions(self, ops: List) -> List[Dict]:
        """将操作列表转换为转场计划"""
        transitions = []
        for op in ops:
            if op.get("type") == "transition":
                transitions.append({
                    "type": op.get("transition_type", "dissolve"),
                    "from": op.get("from_layer", 0),
                    "to": op.get("to_layer", 0),
                    "duration": op.get("duration", 1.0),
                })
        return transitions
