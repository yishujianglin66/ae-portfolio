import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class VocabRef:
    id: str
    name: str
    matchedKeyword: str
    suggestedEffect: str | None = None
    confidence: float = 1.0


@dataclass
class ColorRef:
    keyword: str
    rgb: list[float]
    temperature: str = "neutral"


@dataclass
class IntensityRef:
    keyword: str
    value: float


@dataclass
class TemporalRef:
    keyword: str
    position: str


@dataclass
class EffectDescription:
    effectKeywords: list[VocabRef] = field(default_factory=list)
    styleKeywords: list[VocabRef] = field(default_factory=list)
    directionKeywords: list[str] = field(default_factory=list)
    intensityKeywords: list[IntensityRef] = field(default_factory=list)
    colorKeywords: list[ColorRef] = field(default_factory=list)
    temporalKeywords: list[TemporalRef] = field(default_factory=list)


VOCAB_MAP = {
    "模糊": ["VT-001", "VT-002"],
    "blur": ["VT-001", "VT-002"],
    "高斯模糊": ["VT-001"],
    "gaussian blur": ["VT-001"],
    "发光": ["VT-101", "VT-102"],
    "glow": ["VT-101"],
    "辉光": ["VT-101"],
    "边缘发光": ["VT-101"],
    "粒子": ["VT-401", "VT-402"],
    "particle": ["VT-401"],
    "噪波": ["VT-003"],
    "noise": ["VT-003"],
    "分形噪波": ["VT-003"],
    "fractal noise": ["VT-003"],
    "渐变": ["VT-005"],
    "ramp": ["VT-005"],
    "抠像": ["VT-201"],
    "keying": ["VT-201"],
    "颜色键": ["VT-202"],
    "color key": ["VT-202"],
    "扭曲": ["VT-203", "VT-204"],
    "distort": ["VT-203"],
    "波浪": ["VT-204"],
    "波浪变形": ["VT-204"],
    "波浪扭曲": ["VT-204"],
    "cyberpunk": ["VT-303"],
    "赛博朋克": ["VT-303"],
    "电影感": ["VT-304"],
    "cinematic": ["VT-304"],
    "复古": ["VT-306"],
    "vintage": ["VT-306"],
    "霓虹": ["VT-101", "VT-303"],
    "neon": ["VT-101"],
    "梦幻": ["VT-001", "VT-101"],
    "dreamy": ["VT-001", "VT-101"],
    "弹入": ["KF-001"],
    "bounce in": ["KF-001"],
    "弹出": ["KF-002"],
    "bounce out": ["KF-002"],
    "淡入": ["KF-003"],
    "fade in": ["KF-003"],
    "淡出": ["KF-004"],
    "fade out": ["KF-004"],
    "滑动": ["KF-005"],
    "slide": ["KF-005"],
}


COLOR_MAP = {
    "暖色": {"rgb": [1.0, 0.8, 0.6], "temperature": "warm"},
    "冷色": {"rgb": [0.6, 0.8, 1.0], "temperature": "cool"},
    "暖金": {"rgb": [1.0, 0.85, 0.5], "temperature": "warm"},
    "橙色": {"rgb": [1.0, 0.5, 0.0], "temperature": "warm"},
    "红色": {"rgb": [1.0, 0.0, 0.0], "temperature": "warm"},
    "黄色": {"rgb": [1.0, 1.0, 0.0], "temperature": "warm"},
    "青色": {"rgb": [0.0, 1.0, 1.0], "temperature": "cool"},
    "蓝色": {"rgb": [0.0, 0.5, 1.0], "temperature": "cool"},
    "紫色": {"rgb": [0.5, 0.0, 1.0], "temperature": "cool"},
    "品红": {"rgb": [1.0, 0.0, 1.0], "temperature": "cool"},
    "绿色": {"rgb": [0.0, 1.0, 0.0], "temperature": "neutral"},
    "warm": {"rgb": [1.0, 0.8, 0.6], "temperature": "warm"},
    "cool": {"rgb": [0.6, 0.8, 1.0], "temperature": "cool"},
    "orange": {"rgb": [1.0, 0.5, 0.0], "temperature": "warm"},
    "red": {"rgb": [1.0, 0.0, 0.0], "temperature": "warm"},
    "yellow": {"rgb": [1.0, 1.0, 0.0], "temperature": "warm"},
    "cyan": {"rgb": [0.0, 1.0, 1.0], "temperature": "cool"},
    "blue": {"rgb": [0.0, 0.5, 1.0], "temperature": "cool"},
    "purple": {"rgb": [0.5, 0.0, 1.0], "temperature": "cool"},
    "magenta": {"rgb": [1.0, 0.0, 1.0], "temperature": "cool"},
    "green": {"rgb": [0.0, 1.0, 0.0], "temperature": "neutral"},
}


INTENSITY_MAP = {
    "弱": 0.3,
    "轻微": 0.3,
    "小": 0.3,
    "低": 0.3,
    "适中": 0.5,
    "中等": 0.5,
    "普通": 0.5,
    "强": 0.8,
    "强烈": 0.8,
    "大": 0.8,
    "高": 0.8,
    "非常强": 1.0,
    "极强": 1.0,
    "一点": 0.2,
    "一些": 0.3,
    "稍微": 0.2,
    "略微": 0.2,
    "weak": 0.3,
    "slight": 0.3,
    "low": 0.3,
    "medium": 0.5,
    "normal": 0.5,
    "strong": 0.8,
    "high": 0.8,
    "intense": 0.8,
    "very": 1.0,
}


TEMPORAL_MAP = {
    "开头": "start",
    "开始": "start",
    "起点": "start",
    "start": "start",
    "结尾": "end",
    "结束": "end",
    "终点": "end",
    "end": "end",
    "中间": "middle",
    "mid": "middle",
    "middle": "middle",
    "center": "middle",
}


VOCAB_NAMES: dict[str, str] = {
    "VT-001": "均匀模糊扩散",
    "VT-002": "快速模糊",
    "VT-003": "分形噪波",
    "VT-004": "镜头光斑模糊",
    "VT-005": "渐变",
    "VT-101": "边缘发光",
    "VT-102": "内部发光",
    "VT-105": "星芒",
    "VT-201": "抠像",
    "VT-202": "颜色键",
    "VT-203": "扭曲",
    "VT-204": "波浪变形",
    "VT-303": "青品对比色调",
    "VT-304": "橙青电影色调",
    "VT-306": "复古胶片色调",
    "VT-401": "粒子效果",
    "VT-402": "CC粒子世界",
    "VT-504": "旋转转场",
    "KF-001": "弹入动画",
    "KF-002": "弹出动画",
    "KF-003": "淡入动画",
    "KF-004": "淡出动画",
    "KF-005": "滑动动画",
}


VOCAB_EFFECTS: dict[str, str] = {
    "VT-001": "ADBE Gaussian Blur 2",
    "VT-002": "ADBE Fast Blur",
    "VT-003": "ADBE Fractal Noise",
    "VT-004": "ADBE Camera Lens Blur",
    "VT-005": "ADBE Ramp",
    "VT-101": "ADBE Glo2",
    "VT-102": "ADBE Inner Glow",
    "VT-105": "ADBE Starglow",
    "VT-201": "ADBE Keylight",
    "VT-202": "ADBE Color Key",
    "VT-203": "ADBE Turbulent Displace",
    "VT-204": "ADBE Wave Warp",
    "VT-303": "ADBE Curves",
    "VT-304": "ADBE Curves",
    "VT-306": "ADBE Colorista",
    "VT-401": "ADBE Particle Playground",
    "VT-402": "ADBE CCParticleWorld",
    "VT-504": "ADBE Transform",
}


STYLE_RECIPES: dict[str, dict[str, Any]] = {
    "赛博朋克": {
        "effectIds": ["VT-303", "VT-101", "VT-504"],
        "description": "青品色调 + 边缘发光 + 镜头畸变",
    },
    "cyberpunk": {
        "effectIds": ["VT-303", "VT-101", "VT-504"],
        "description": "青品色调 + 边缘发光 + 镜头畸变",
    },
    "电影感": {
        "effectIds": ["VT-304", "VT-101", "VT-004"],
        "description": "橙青色调 + 边缘发光 + 景深模糊",
    },
    "cinematic": {
        "effectIds": ["VT-304", "VT-101", "VT-004"],
        "description": "橙青色调 + 边缘发光 + 景深模糊",
    },
    "梦幻": {
        "effectIds": ["VT-001", "VT-101", "VT-105"],
        "description": "柔焦模糊 + 边缘发光 + 星芒",
    },
    "dreamy": {
        "effectIds": ["VT-001", "VT-101", "VT-105"],
        "description": "柔焦模糊 + 边缘发光 + 星芒",
    },
    "复古": {
        "effectIds": ["VT-306", "VT-001"],
        "description": "复古胶片色调 + 轻微模糊",
    },
    "vintage": {
        "effectIds": ["VT-306", "VT-001"],
        "description": "复古胶片色调 + 轻微模糊",
    },
    "霓虹": {
        "effectIds": ["VT-101", "VT-303"],
        "description": "霓虹边缘发光 + 青品色调",
    },
    "neon": {
        "effectIds": ["VT-101", "VT-303"],
        "description": "霓虹边缘发光 + 青品色调",
    },
}


def _build_scan_index(mapping: dict[str, Any]):
    """构建关键词扫描索引：预编译 alternation regex + lower 查找表。

    用 lookahead 断言使 finditer 能匹配重叠子串，保持与原 `in` 检查一致的行为
    （如 "高斯模糊" 同时匹配 "高斯模糊" 和 "模糊"）。关键词按长度降序排列，
    确保长关键词优先被记录。
    """
    keywords_sorted = sorted(mapping.keys(), key=len, reverse=True)
    pattern = "(?=(" + "|".join(re.escape(k) for k in keywords_sorted) + "))"
    compiled = re.compile(pattern, re.IGNORECASE)
    lookup = {k.lower(): (k, v) for k, v in mapping.items()}
    return compiled, lookup


# 模块级预编译，避免每次扫描重复构建
_VOCAB_SCAN_RE, _VOCAB_LOOKUP = _build_scan_index(VOCAB_MAP)
_COLOR_SCAN_RE, _COLOR_LOOKUP = _build_scan_index(COLOR_MAP)
_INTENSITY_SCAN_RE, _INTENSITY_LOOKUP = _build_scan_index(INTENSITY_MAP)
_TEMPORAL_SCAN_RE, _TEMPORAL_LOOKUP = _build_scan_index(TEMPORAL_MAP)


def scan_vocab(input_text: str) -> list[VocabRef]:
    refs = []
    seen = set()
    for m in _VOCAB_SCAN_RE.finditer(input_text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen:
            continue
        seen.add(kw_lower)
        original_kw, vocab_ids = _VOCAB_LOOKUP[kw_lower]
        for vid in vocab_ids:
            refs.append(VocabRef(
                id=vid,
                name=VOCAB_NAMES.get(vid, vid),
                matchedKeyword=original_kw,
                suggestedEffect=VOCAB_EFFECTS.get(vid),
                confidence=0.85,
            ))
    return refs


def scan_colors(input_text: str) -> list[ColorRef]:
    refs = []
    seen = set()
    for m in _COLOR_SCAN_RE.finditer(input_text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen:
            continue
        seen.add(kw_lower)
        original_kw, data = _COLOR_LOOKUP[kw_lower]
        refs.append(ColorRef(
            keyword=original_kw,
            rgb=data["rgb"],
            temperature=data["temperature"],
        ))
    return refs


def scan_intensity(input_text: str) -> list[IntensityRef]:
    refs = []
    seen = set()
    for m in _INTENSITY_SCAN_RE.finditer(input_text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen:
            continue
        seen.add(kw_lower)
        original_kw, value = _INTENSITY_LOOKUP[kw_lower]
        refs.append(IntensityRef(keyword=original_kw, value=value))
    return refs


def scan_temporal(input_text: str) -> list[TemporalRef]:
    refs = []
    seen = set()
    for m in _TEMPORAL_SCAN_RE.finditer(input_text):
        kw_lower = m.group(1).lower()
        if kw_lower in seen:
            continue
        seen.add(kw_lower)
        original_kw, position = _TEMPORAL_LOOKUP[kw_lower]
        refs.append(TemporalRef(keyword=original_kw, position=position))
    return refs


class EffectDescriptionParser:
    def parse(self, input_text: str, intent_type: str | None = None) -> EffectDescription:
        result = EffectDescription()

        if not input_text or not input_text.strip():
            return result

        vocab_refs = scan_vocab(input_text)
        color_refs = scan_colors(input_text)
        intensity_refs = scan_intensity(input_text)
        temporal_refs = scan_temporal(input_text)

        for ref in vocab_refs:
            if ref.id.startswith("VT-"):
                category_num = int(ref.id[3:])
                if category_num < 100:
                    result.effectKeywords.append(ref)
                elif category_num < 200:
                    result.effectKeywords.append(ref)
                elif category_num < 300:
                    result.effectKeywords.append(ref)
                elif category_num < 400:
                    rgb = [0.5, 0.5, 0.5]
                    if ref.id == "VT-303":
                        rgb = [0.0, 0.5, 1.0]
                    elif ref.id == "VT-304":
                        rgb = [1.0, 0.5, 0.0]
                    result.colorKeywords.append(ColorRef(
                        keyword=ref.matchedKeyword,
                        rgb=rgb,
                        temperature="cool" if category_num == 303 else "warm",
                    ))
                elif category_num < 500:
                    result.effectKeywords.append(ref)
                elif category_num < 600:
                    result.effectKeywords.append(ref)
                elif category_num < 700:
                    result.effectKeywords.append(ref)
            elif ref.id.startswith("KF-"):
                result.effectKeywords.append(ref)

        result.colorKeywords.extend(color_refs)
        result.intensityKeywords.extend(intensity_refs)
        result.temporalKeywords.extend(temporal_refs)

        directions = self._extract_directions(input_text)
        result.directionKeywords.extend(directions)

        if intent_type == "STYLE_COMBO":
            style_name = self._extract_style_name(input_text)
            if style_name:
                recipe = STYLE_RECIPES.get(style_name.lower())
                if recipe:
                    for vid in recipe["effectIds"]:
                        existing = next((r for r in result.effectKeywords if r.id == vid), None)
                        if not existing:
                            vocab_name = VOCAB_NAMES.get(vid, vid)
                            result.styleKeywords.append(VocabRef(
                                id=vid,
                                name=vocab_name,
                                matchedKeyword=style_name,
                                suggestedEffect=VOCAB_EFFECTS.get(vid),
                                confidence=0.75,
                            ))

        return result

    def _extract_directions(self, input_text: str) -> list[str]:
        directions = []
        dir_map = [
            {"keyword": "向上", "value": "up"},
            {"keyword": "向下", "value": "down"},
            {"keyword": "向左", "value": "left"},
            {"keyword": "向右", "value": "right"},
            {"keyword": "向外", "value": "out"},
            {"keyword": "向内", "value": "in"},
            {"keyword": "up", "value": "up"},
            {"keyword": "down", "value": "down"},
            {"keyword": "left", "value": "left"},
            {"keyword": "right", "value": "right"},
            {"keyword": "out", "value": "out"},
            {"keyword": "in", "value": "in"},
        ]
        seen = set()
        for d in dir_map:
            if d["keyword"] in input_text and d["value"] not in seen:
                seen.add(d["value"])
                directions.append(d["value"])
        return directions

    def _extract_style_name(self, input_text: str) -> str | None:
        for style in STYLE_RECIPES.keys():
            if style.lower() in input_text.lower():
                return style
        m = re.search(r"(\S{1,10}?)\s*风格", input_text)
        return m.group(1) if m else None


effect_description_parser = EffectDescriptionParser()


def get_style_recipe(style_name: str) -> dict[str, Any] | None:
    return STYLE_RECIPES.get(style_name.lower())


def get_all_styles() -> list[str]:
    return list(STYLE_RECIPES.keys())


def get_vocab_stats() -> dict[str, Any]:
    by_category = {}
    for vid in VOCAB_NAMES.keys():
        if vid.startswith("VT-"):
            category_num = int(vid[3:])
            if category_num < 100:
                cat = "blur"
            elif category_num < 200:
                cat = "glow"
            elif category_num < 300:
                cat = "distort"
            elif category_num < 400:
                cat = "color"
            elif category_num < 500:
                cat = "particle"
            elif category_num < 600:
                cat = "transition"
            elif category_num < 700:
                cat = "text"
            else:
                cat = "other"
            by_category[cat] = by_category.get(cat, 0) + 1
        elif vid.startswith("KF-"):
            by_category["keyframe"] = by_category.get("keyframe", 0) + 1
    return {"total": len(VOCAB_NAMES), "byCategory": by_category}
