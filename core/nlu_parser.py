from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import re


class IntentType:
    ADD_EFFECT = "ADD_EFFECT"
    CREATE_ANIM = "CREATE_ANIM"
    ADJUST_PARAM = "ADJUST_PARAM"
    CREATE_LAYER = "CREATE_LAYER"
    STYLE_COMBO = "STYLE_COMBO"
    REVERSE_ANALYZE = "REVERSE_ANALYZE"
    UNKNOWN = "UNKNOWN"


class ConfidenceThresholds:
    AUTO_EXECUTE = 0.7
    NO_CLARIFICATION = 0.6
    MIN_RECOGNITION = 0.3


@dataclass
class IntentSlots:
    effectName: Optional[str] = None
    targetLayer: Optional[str] = None
    animType: Optional[str] = None
    paramName: Optional[str] = None
    adjustDirection: Optional[str] = None
    adjustAmount: Optional[str] = None
    styleName: Optional[str] = None
    color: Optional[str] = None
    temporal: Optional[str] = None


@dataclass
class Intent:
    type: str
    confidence: float
    slots: IntentSlots
    rawInput: str
    matchedPattern: Optional[str] = None


@dataclass
class ProjectContext:
    activeCompName: Optional[str] = None
    selectedLayers: Optional[List[Dict[str, Any]]] = None
    compResolution: Optional[List[int]] = None
    compFrameRate: int = 30
    compDuration: float = 5.0


_FALLBACK_EFFECT_RE = re.compile(
    r"(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)",
    re.IGNORECASE,
)


class NLUParser:
    def __init__(self):
        self.patterns = self._build_patterns()
        # 预编译所有正则，避免 parse 时每次 re.search 的缓存查找开销。
        # 编译后 .pattern 属性仍可取回原始字符串，用于 matchedPattern 字段。
        for pattern_def in self.patterns:
            pattern_def["patterns"] = [
                re.compile(p, re.IGNORECASE) for p in pattern_def["patterns"]
            ]

    def _build_patterns(self):
        return [
            {
                "type": IntentType.ADD_EFFECT,
                "confidence": 0.85,
                "patterns": [
                    r"(?:加(?:一个|[个一])?|添加|来[个一]?|apply\s+)(?:\s*一个)?\s*(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?:效果|特效)?",
                    r"(?:加[个一]?|添加)\s*(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?=\s*(?:到|给|for|to|效果|特效))",
                    r"做[个一]?\s*(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?:效果|特效)?",
                    r"(?:给|为|在)\s*\S+?(?:加|添加)\s*(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?:效果|特效)?",
                    r"(?:给|为|在)\s*\S+?(?:加|添加)(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?:效果|特效)?",
                    r"加.*?(发光|模糊|粒子|噪波|渐变|抠像|颜色键|glow|blur|particle|noise|ramp)(?:效果|特效)?",
                ],
                "slotExtractor": self._extract_add_effect_slots,
            },
            {
                "type": IntentType.CREATE_ANIM,
                "confidence": 0.85,
                "patterns": [
                    r"做(?:一个|[个一])?\s*(\S{1,8})(?:动画|动效|入场|出场|过渡)",
                    r"加(?:一个|[个一])?\s*(\S{1,8})(?:入场|出场|过渡|动画)",
                    r"(\S{1,8}?)弹(?:入|出|落)",
                    r"创建\s*(?:弹性|缓动)\s*(\S{1,10})",
                    r"(?:create|make)\s+(?:a\s+)?(\S+)\s+(?:animation|transition)",
                    r"(?:bounce|spring|fade|slide)\s*(?:in|out)",
                    r"(\S+?)\s*(?:bounce|spring|fade|slide)\s*(?:in|out)",
                ],
                "slotExtractor": self._extract_create_anim_slots,
            },
            {
                "type": IntentType.ADJUST_PARAM,
                "confidence": 0.82,
                "patterns": [
                    r"(\S{1,10}?)\s*(?:调[大高小低]|加[强大弱]|变[大大小低]|改[变大大小低])",
                    r"(\S{1,10}?)\s*再\s*(?:强|弱|大|小|多|少)\s*(?:一点|些)",
                    r"(\S{1,10}?)\s*偏\s*(\S{1,5})",
                    r"(?:调[节整]|set|adjust)\s+(\S{1,15})\s+(?:to|为|成)?\s*(\d+(?:\.\d+)?|%|一点|一些)",
                ],
                "slotExtractor": self._extract_adjust_param_slots,
            },
            {
                "type": IntentType.CREATE_LAYER,
                "confidence": 0.88,
                "patterns": [
                    r"建(?:一个|[个一])?\s*(合成|composition|comp)",
                    r"创建\s*(?:一个)?\s*(合成|空对象|调整层|固态层|文字层|形状层|shape|solid|adjustment|null|text)",
                    r"加[个一]?\s*(调整层|空对象|固态层|文字层|形状层|shape|solid|adjustment|null|text)",
                    r"(?:create|add|new)\s+(?:a\s+)?(composition|comp|solid|adjustment|null|text|shape)",
                ],
                "slotExtractor": self._extract_create_layer_slots,
            },
            {
                "type": IntentType.STYLE_COMBO,
                "confidence": 0.80,
                "patterns": [
                    r"做(?:一个|[个一])?\s*(\S{1,10}?)\s*风格",
                    r"(\S{1,10}?)\s*风格",
                    r"(\S{1,10}?)\s*(?:效果组合|组合效果)",
                    r"做(?:一个|[个一])?\s*(\S{1,10}?(?:感|调))",
                    r"(?:apply|create|make)\s+(?:a\s+)?(\S+)\s+style",
                    r"(\S{1,15})\s+style",
                ],
                "slotExtractor": self._extract_style_combo_slots,
            },
            {
                "type": IntentType.REVERSE_ANALYZE,
                "confidence": 0.85,
                "patterns": [
                    r"(?:这个|这段)(?:效果|视频|动画)\s*(?:怎么|如何)?\s*(?:做|实现)",
                    r"分析(?:一下)?\s*(?:这个|这段)?\s*(?:视频|效果|动画)",
                    r"逆向(?:分析|还原)",
                    r"(?:how|how to)\s+(?:did|did they|to)\s+(?:make|create|do)\s+(?:this|that)",
                    r"reverse\s+(?:engineer|analyze)",
                ],
                "slotExtractor": lambda m, r: {},
            },
        ]

    def _extract_add_effect_slots(self, match, raw):
        effect_name = match.group(1).strip()
        effect_name = re.sub(r"(?:效果|特效)$", "", effect_name)
        return {"effectName": effect_name.strip()}

    def _extract_create_anim_slots(self, match, raw):
        anim_type = match.group(1).strip() if match.groups() else ""
        if not anim_type:
            m = re.search(r"(bounce|spring|fade|slide)\s*(in|out)", raw, re.IGNORECASE)
            if m:
                anim_type = f"{m.group(1)} {m.group(2)}"
        return {"animType": anim_type}

    def _extract_adjust_param_slots(self, match, raw):
        slots = {"paramName": match.group(1).strip()}
        if len(match.groups()) > 1 and match.group(2):
            amt = match.group(2).strip()
            slots["adjustAmount"] = amt
            if re.search(r"大|强|多|高", amt) or re.search(r"^\d", amt):
                slots["adjustDirection"] = "increase"
            elif re.search(r"小|弱|少|低", amt):
                slots["adjustDirection"] = "decrease"
            else:
                slots["adjustDirection"] = "set"
        else:
            if re.search(r"调[大高强]", raw):
                slots["adjustDirection"] = "increase"
            elif re.search(r"调[小低弱]", raw):
                slots["adjustDirection"] = "decrease"
            else:
                slots["adjustDirection"] = "set"
        return slots

    def _extract_create_layer_slots(self, match, raw):
        layer_type = match.group(1).strip()
        normalized = layer_type
        if re.search(r"合成|comp", layer_type, re.IGNORECASE):
            normalized = "composition"
        elif re.search(r"空|null", layer_type, re.IGNORECASE):
            normalized = "null"
        elif re.search(r"调整|adjustment", layer_type, re.IGNORECASE):
            normalized = "adjustment"
        elif re.search(r"固态|solid", layer_type, re.IGNORECASE):
            normalized = "solid"
        elif re.search(r"文字|text", layer_type, re.IGNORECASE):
            normalized = "text"
        elif re.search(r"形状|shape", layer_type, re.IGNORECASE):
            normalized = "shape"
        return {"targetLayer": normalized}

    def _extract_style_combo_slots(self, match, raw):
        return {"styleName": match.group(1).strip()}

    def _extract_target_layer(self, raw):
        m1 = re.search(r"(?:给|为|在)\s*([^\s,，。.!！?？]+?)\s*(?:加|添加|来)", raw)
        if m1:
            target = m1.group(1).strip()
            if re.search(r"文字|text", target, re.IGNORECASE):
                return "text"
            if re.search(r"图层\d+|layer\s*\d+", target, re.IGNORECASE):
                return target
            if re.search(r"选中|selected", target, re.IGNORECASE):
                return "selected"
            if re.search(r"调整层", target):
                return "adjustment"
            return target
        if re.search(r"选中|selected", raw, re.IGNORECASE):
            return "selected"
        if re.search(r"当前|current", raw, re.IGNORECASE):
            return "current"
        return None

    def _extract_color(self, raw):
        color_patterns = [
            "暖色", "冷色", "暖金", "橙色", "红色", "黄色",
            "青色", "蓝色", "紫色", "品红", "绿色",
            "warm", "cool", "orange", "red", "yellow",
            "cyan", "blue", "purple", "magenta", "green",
        ]
        for c in color_patterns:
            if c in raw:
                return c
        return None

    def _extract_temporal(self, raw):
        m = re.search(r"(?:在|at|from|to)?\s*(开头|结尾|中间|start|end|middle|\d+\s*(?:秒|s))", raw, re.IGNORECASE)
        return m.group(1).strip() if m else None

    def parse(self, input_text: str, context: Optional[ProjectContext] = None) -> Intent:
        trimmed = input_text.strip()
        if not trimmed:
            return Intent(
                type=IntentType.UNKNOWN,
                confidence=0.0,
                slots=IntentSlots(),
                rawInput=input_text,
            )

        for pattern_def in self.patterns:
            for compiled_re in pattern_def["patterns"]:
                match = compiled_re.search(trimmed)
                if match:
                    slots_dict = pattern_def["slotExtractor"](match, trimmed) if pattern_def["slotExtractor"] else {}
                    slots = IntentSlots(**slots_dict)

                    if not slots.targetLayer:
                        slots.targetLayer = self._extract_target_layer(trimmed)
                    if not slots.color:
                        slots.color = self._extract_color(trimmed)
                    if not slots.temporal:
                        slots.temporal = self._extract_temporal(trimmed)

                    if context and context.selectedLayers and len(context.selectedLayers) > 0:
                        if not slots.targetLayer:
                            slots.targetLayer = "selected"

                    return Intent(
                        type=pattern_def["type"],
                        confidence=pattern_def["confidence"],
                        slots=slots,
                        rawInput=input_text,
                        matchedPattern=compiled_re.pattern,
                    )

        effect_match = _FALLBACK_EFFECT_RE.search(trimmed)
        if effect_match:
            return Intent(
                type=IntentType.ADD_EFFECT,
                confidence=0.55,
                slots=IntentSlots(
                    effectName=effect_match.group(1),
                    targetLayer=self._extract_target_layer(trimmed),
                ),
                rawInput=input_text,
            )

        return Intent(
            type=IntentType.UNKNOWN,
            confidence=0.2,
            slots=IntentSlots(),
            rawInput=input_text,
        )

    def needs_clarification(self, intent: Intent) -> bool:
        if intent.type == IntentType.UNKNOWN:
            return True
        return intent.confidence < ConfidenceThresholds.NO_CLARIFICATION

    # ------------------------------------------------------------------
    # LLM 混合增强
    # ------------------------------------------------------------------

    def parse_enhanced(self, input_text: str,
                       context: Optional[ProjectContext] = None) -> Intent:
        """
        LLM 增强版解析 — 先用本地正则，LLM 可用时补充理解
        失败时自动降级为纯本地解析
        """
        import asyncio

        local_intent = self.parse(input_text, context)

        # 尝试导入 LLM 网关和记忆系统
        try:
            from core.llm_gateway import llm_gateway, TaskType
            from core.memory_store import memory_store
        except ImportError:
            return local_intent

        # 1. 查记忆系统
        experiences = memory_store.get_experience(
            category="nlu_parse",
            task_keyword=input_text[:50],
            limit=3,
        )
        if experiences and experiences[0].confidence > 0.85:
            exp = experiences[0]
            cached = exp.content.get("intent", {})
            if cached and cached.get("type"):
                cached_intent = Intent(
                    type=cached.get("type"),
                    confidence=min(exp.confidence, 0.95),
                    slots=IntentSlots(**cached.get("slots", {})),
                    rawInput=input_text,
                )
                return cached_intent

        # 2. 本地置信度已很高，不需要 LLM
        if local_intent.confidence >= 0.85:
            return local_intent

        # 3. LLM 不可用时降级
        if not llm_gateway.is_available():
            return local_intent

        # 4. 用 LLM 增强
        try:
            result = asyncio.run(llm_gateway.chat_with_routing(
                message=f'用户输入: "{input_text}"\n\n'
                        f'本地解析: type={local_intent.type}, '
                        f'confidence={local_intent.confidence}\n'
                        f'请返回JSON: {{"type":"ADD_EFFECT",'
                        f'"confidence":0.9,"slots":{{}}}}',
                task_type=TaskType.INTENT_CLASSIFICATION,
                system_prompt=(
                    "你是视频制作意图分析专家。"
                    "返回JSON格式: "
                    '{"type":"ADD_EFFECT|CREATE_ANIM|ADJUST_PARAM|'
                    'CREATE_LAYER|STYLE_COMBO|SILHOUETTE_TASK|'
                    'REVERSE_ANALYZE|UNKNOWN","confidence":0.0-1.0,'
                    '"slots":{"effectName":"","targetLayer":"","color":"","temporal":""}}'
                ),
            ))

            if result.success and result.content:
                import json as _json
                match = _json_re.search(result.content)
                if match:
                    parsed = _json.loads(match.group(0))
                    llm_type = parsed.get("type", "UNKNOWN")
                    llm_conf = min(max(parsed.get("confidence", 0.5), 0), 1)
                    llm_slots = parsed.get("slots", {})

                    # 合并：取置信度更高的
                    if llm_conf > local_intent.confidence + 0.15:
                        merged = Intent(
                            type=llm_type,
                            confidence=llm_conf,
                            slots=IntentSlots(**{**local_intent.slots.__dict__,
                                                 **llm_slots}),
                            rawInput=input_text,
                        )
                    else:
                        merged = Intent(
                            type=local_intent.type if local_intent.type != "UNKNOWN" else llm_type,
                            confidence=max(local_intent.confidence, llm_conf),
                            slots=IntentSlots(**{**local_intent.slots.__dict__,
                                                 **llm_slots}),
                            rawInput=input_text,
                        )

                    # 5. 记录到记忆系统
                    memory_store.remember(
                        category="nlu_parse",
                        key=input_text[:50],
                        content={
                            "intent": {
                                "type": merged.type,
                                "confidence": merged.confidence,
                                "slots": merged.slots.__dict__,
                            }
                        },
                        tags=[merged.type],
                        confidence=merged.confidence,
                    )

                    return merged
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"NLU LLM 增强失败（不影响主流程）: {e}"
            )

        return local_intent


import re as _re_module
_json_re = _re_module.compile(r'\{[\s\S]*\}')


nlu_parser = NLUParser()
