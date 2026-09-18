import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    # 包导入模式：`import ai.clarification_engine`
    from ai.nlu_parser import ConfidenceThresholds, Intent, IntentSlots, IntentType
except ImportError:
    # 顶层导入模式（tests/conftest.py 将 ai/ 加入 sys.path 后 `import clarification_engine`）
    from nlu_parser import ConfidenceThresholds, Intent, IntentSlots, IntentType


@dataclass
class ClarificationQuestion:
    question: str
    slot: str
    options: list[str] = field(default_factory=list)
    required: bool = True


@dataclass
class ClarificationState:
    intent: Intent
    questions: list[ClarificationQuestion]
    answered_slots: dict[str, Any] = field(default_factory=dict)
    current_question_index: int = 0


class ClarificationEngine:
    def __init__(self):
        self.question_templates = {
            IntentType.ADD_EFFECT: [
                {
                    "condition": lambda s: not s.effectName,
                    "question": "你想添加什么效果？（例如：发光、模糊、粒子）",
                    "slot": "effectName",
                },
                {
                    "condition": lambda s: not s.targetLayer,
                    "question": "要添加到哪个图层？（例如：选中图层、文字层、图层001）",
                    "slot": "targetLayer",
                    "options": ["选中图层", "当前图层", "新建图层"],
                },
                {
                    "condition": lambda s: not s.color,
                    "question": "需要调整颜色吗？（例如：暖色、冷色、青色）",
                    "slot": "color",
                    "options": ["暖色", "冷色", "青色", "橙色", "不需要"],
                },
            ],
            IntentType.CREATE_ANIM: [
                {
                    "condition": lambda s: not s.animType,
                    "question": "你想创建什么类型的动画？（例如：弹入、淡入、滑动）",
                    "slot": "animType",
                    "options": ["弹入", "弹出", "淡入", "淡出", "滑动", "缩放"],
                },
                {
                    "condition": lambda s: not s.targetLayer,
                    "question": "要应用到哪个图层？",
                    "slot": "targetLayer",
                    "options": ["选中图层", "当前图层"],
                },
                {
                    "condition": lambda s: not s.temporal,
                    "question": "动画何时开始？",
                    "slot": "temporal",
                    "options": ["开头", "中间", "结尾"],
                },
            ],
            IntentType.ADJUST_PARAM: [
                {
                    "condition": lambda s: not s.paramName,
                    "question": "你想调整哪个参数？（例如：亮度、对比度、模糊度）",
                    "slot": "paramName",
                },
                {
                    "condition": lambda s: not s.adjustDirection,
                    "question": "要调大还是调小？",
                    "slot": "adjustDirection",
                    "options": ["调大", "调小", "设置为"],
                },
                {
                    "condition": lambda s: not s.adjustAmount,
                    "question": "调整多少？（例如：10%、一点、适中）",
                    "slot": "adjustAmount",
                    "options": ["一点", "适中", "很多", "10%", "50%"],
                },
            ],
            IntentType.CREATE_LAYER: [
                {
                    "condition": lambda s: not s.targetLayer,
                    "question": "你想创建什么类型的图层？",
                    "slot": "targetLayer",
                    "options": ["固态层", "调整层", "空对象", "文字层", "形状层", "合成"],
                },
                {
                    "condition": lambda s: not s.color,
                    "question": "需要设置颜色吗？",
                    "slot": "color",
                    "options": ["黑色", "白色", "自定义颜色"],
                },
            ],
            IntentType.STYLE_COMBO: [
                {
                    "condition": lambda s: not s.styleName,
                    "question": "你想应用什么风格？（例如：赛博朋克、电影感、复古）",
                    "slot": "styleName",
                    "options": ["赛博朋克", "电影感", "梦幻", "复古", "霓虹"],
                },
                {
                    "condition": lambda s: not s.targetLayer,
                    "question": "要应用到哪个图层？",
                    "slot": "targetLayer",
                    "options": ["选中图层", "当前合成"],
                },
            ],
            IntentType.REVERSE_ANALYZE: [],
            IntentType.UNKNOWN: [
                {
                    "condition": lambda s: True,
                    "question": "我不太理解你的需求，可以详细描述一下吗？",
                    "slot": "rawInput",
                    "required": False,
                },
            ],
        }

    def generate_questions(self, intent: Intent) -> list[ClarificationQuestion]:
        questions = []
        templates = self.question_templates.get(intent.type, [])

        for template in templates:
            if template["condition"](intent.slots):
                questions.append(ClarificationQuestion(
                    question=template["question"],
                    slot=template["slot"],
                    options=template.get("options", []),
                    required=template.get("required", True),
                ))

        return questions

    def create_state(self, intent: Intent) -> ClarificationState:
        questions = self.generate_questions(intent)
        return ClarificationState(
            intent=intent,
            questions=questions,
            answered_slots={},
            current_question_index=0,
        )

    def has_more_questions(self, state: ClarificationState) -> bool:
        return state.current_question_index < len(state.questions)

    def get_next_question(self, state: ClarificationState) -> ClarificationQuestion | None:
        if self.has_more_questions(state):
            return state.questions[state.current_question_index]
        return None

    def answer_question(self, state: ClarificationState, answer: str) -> ClarificationState:
        if not self.has_more_questions(state):
            return state

        current_q = state.questions[state.current_question_index]
        state.answered_slots[current_q.slot] = answer.strip()
        state.current_question_index += 1
        return state

    def get_final_slots(self, state: ClarificationState) -> IntentSlots:
        slots_dict = {
            "effectName": state.intent.slots.effectName,
            "targetLayer": state.intent.slots.targetLayer,
            "animType": state.intent.slots.animType,
            "paramName": state.intent.slots.paramName,
            "adjustDirection": state.intent.slots.adjustDirection,
            "adjustAmount": state.intent.slots.adjustAmount,
            "styleName": state.intent.slots.styleName,
            "color": state.intent.slots.color,
            "temporal": state.intent.slots.temporal,
        }

        for slot, value in state.answered_slots.items():
            if slot in slots_dict and value:
                slots_dict[slot] = value

        return IntentSlots(**slots_dict)

    def needs_clarification(self, intent: Intent) -> bool:
        if intent.type == IntentType.UNKNOWN:
            return True
        return intent.confidence < ConfidenceThresholds.NO_CLARIFICATION

    def should_auto_execute(self, intent: Intent) -> bool:
        return intent.confidence >= ConfidenceThresholds.AUTO_EXECUTE

    def analyze_confidence_gap(self, intent: Intent) -> dict[str, float]:
        gaps = {}
        if not intent.slots.effectName:
            gaps["effectName"] = 0.3
        if not intent.slots.targetLayer:
            gaps["targetLayer"] = 0.2
        if not intent.slots.color:
            gaps["color"] = 0.1
        if not intent.slots.temporal:
            gaps["temporal"] = 0.1
        return gaps


clarification_engine = ClarificationEngine()
