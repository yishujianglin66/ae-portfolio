"""knowledge/transition_taxonomy.py — 机器可读转场类型分类法

对齐 EBU SKOS 视频转场类型码思路 (知识审计 2026-08-14 指出的真缺口①:
"转场节奏/时长/缓动无量化 schema"), 把转场配方从 md 散文变成可机检枚举:

  - code: 稳定类型码 (机器消费)
  - kind: cut / dissolve / wipe / motion / stylize 大类
  - xfade: 与 ai/production_director.XFADE_MAP 对齐的 ffmpeg xfade 滤镜名
  - default_dur: 默认时长 (秒, 节奏量化)
  - rhythm_fit: 适用节奏场景 (beat=卡点 / impact=冲击 / breathe=喘息 /
                structural=段落边界 / hard_stop=戛然而止)
  - ebu_class: EBU/行业惯例类型归类

用法:
    from knowledge.transition_taxonomy import get_transition, list_transitions
    t = get_transition("FADE_WHITE")
    t.xfade  # "fadewhite"
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class TransitionSpec:
    """单个转场类型的量化规格。"""

    def __init__(self, code: str, name_zh: str, kind: str, ebu_class: str,
                 xfade: str | None, default_dur: float,
                 rhythm_fit: list[str], notes: str = "") -> None:
        self.code = code
        self.name_zh = name_zh
        self.kind = kind
        self.ebu_class = ebu_class
        self.xfade = xfade
        self.default_dur = default_dur
        self.rhythm_fit = list(rhythm_fit)
        self.notes = notes

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code, "name_zh": self.name_zh, "kind": self.kind,
            "ebu_class": self.ebu_class, "xfade": self.xfade,
            "default_dur": self.default_dur, "rhythm_fit": self.rhythm_fit,
            "notes": self.notes,
        }


# 转场分类法 (与 production_director.XFADE_MAP 值对齐)
TRANSITION_TAXONOMY: list[TransitionSpec] = [
    TransitionSpec("CUT", "硬切", "cut", "hard-cut", None, 0.0,
                   ["beat", "impact", "drop"], "漫剪铁律: 爆发段硬切卡点"),
    TransitionSpec("FADE_BLACK", "淡黑", "dissolve", "fade", "fadeblack", 0.35,
                   ["structural", "breathe", "outro"], "段落边界/喘息收束"),
    TransitionSpec("FADE_WHITE", "闪白", "dissolve", "fade", "fadewhite", 0.12,
                   ["hard_stop", "impact"], "音乐戛然而止的冲击定格"),
    TransitionSpec("CROSS_DISSOLVE", "叠化", "dissolve", "dissolve", "fade", 0.30,
                   ["breathe", "lyric"], "柔和过渡, 与歌词/情绪缓段相配"),
    TransitionSpec("WIPE_LEFT", "左擦除", "wipe", "wipe", "wipeleft", 0.25,
                   ["structural", "build"], "方向性叙事推进"),
    TransitionSpec("SLIDE_LEFT", "左滑动", "wipe", "slide", "slideleft", 0.30,
                   ["structural", "build"], "镜头同向滑接"),
    TransitionSpec("ZOOM_UP", "推近", "motion", "zoom", "smoothup", 0.30,
                   ["impact", "build"], "模拟推镜进入下一镜"),
    TransitionSpec("PIXELIZE", "像素化", "stylize", "stylize", "pixelize", 0.20,
                   ["impact", "glitch"], "故障/电子风格"),
    TransitionSpec("CIRCLE_OPEN", "圆形展开", "wipe", "wipe", "circleopen", 0.30,
                   ["structural"], "复古电影常用"),
    TransitionSpec("RADIAL", "径向扫", "wipe", "wipe", "radial", 0.30,
                   ["structural", "build"], "表盘式扫换"),
    TransitionSpec("HBLUR", "水平模糊", "stylize", "stylize", "hblur", 0.25,
                   ["impact", "speed"], "速度感模糊过渡"),
    TransitionSpec("DIAG_TL", "对角擦除", "wipe", "wipe", "diagtl", 0.25,
                   ["build", "structural"], "对角线动力"),
    TransitionSpec("VERT_OPEN", "垂直展开", "wipe", "wipe", "vertopen", 0.25,
                   ["structural"], "幕布式展开"),
    TransitionSpec("SQUEEZE_H", "水平挤压", "stylize", "stylize", "squeezeh", 0.25,
                   ["impact", "build"], "挤压变形推进"),
]

_BY_CODE: dict[str, TransitionSpec] = {t.code: t for t in TRANSITION_TAXONOMY}
_BY_XFADE: dict[str, TransitionSpec] = {
    t.xfade: t for t in TRANSITION_TAXONOMY if t.xfade
}


def get_transition(code: str) -> TransitionSpec | None:
    """按类型码取转场规格。"""
    return _BY_CODE.get(code.upper())


def by_xfade(xfade_name: str) -> TransitionSpec | None:
    """按 ffmpeg xfade 滤镜名反查。"""
    return _BY_XFADE.get(xfade_name)


def list_transitions(kind: str | None = None) -> list[TransitionSpec]:
    """列出全部转场 (可按 kind 过滤: cut/dissolve/wipe/motion/stylize)。"""
    if kind is None:
        return list(TRANSITION_TAXONOMY)
    return [t for t in TRANSITION_TAXONOMY if t.kind == kind]


def list_for_rhythm(rhythm: str) -> list[TransitionSpec]:
    """按节奏场景取适用转场 (beat/impact/breathe/structural/hard_stop/...)。"""
    return [t for t in TRANSITION_TAXONOMY if rhythm in t.rhythm_fit]


def validate_xfade_consistency(xfade_map: dict[str, tuple]) -> list[str]:
    """校验分类法与生产 XFADE_MAP 的一致性, 返回不一致清单 (空=一致)。

    xfade_map: production_director.XFADE_MAP (标签 → (滤镜名, 时长秒))。
    校验对象是滤镜名与时长 (分类法按滤镜语义定义, 不绑定标签)。
    """
    problems: list[str] = []
    known_filters = {v[0]: v[1] for v in xfade_map.values()}
    for spec in TRANSITION_TAXONOMY:
        if spec.xfade is None:
            continue
        if spec.xfade not in known_filters:
            problems.append(f"{spec.code}: xfade '{spec.xfade}' 不在 XFADE_MAP")
        else:
            xfade_dur = known_filters[spec.xfade]
            if abs(xfade_dur - spec.default_dur) > 0.001:
                problems.append(
                    f"{spec.code}: 时长不一致 taxonomy={spec.default_dur} "
                    f"XFADE_MAP={xfade_dur}")
    return problems
