# -*- coding: utf-8 -*-
"""StyleTreeBuilder — 风格卡→合成树生成（M4，[AE-sync] 对侧模块）

把风格知识卡（knowledge/style_card.StyleCard，品味三旋钮 + text_fx + 粒子预设）
或一句话 prompt，编译成可校验的 CompositionTree（M1a schema），随后可走
M1b SynthesisOrchestrator → JSX 工程，M3 BeatLock 注入节拍，渲染后 M2 评分。

不依赖 AE 真机；只读消费 knowledge/style_card 与 core/composition_tree，
不修改主会话当日已提交文件。

三类入口：
  build_from_card(style_id|StyleCard, content)  — 规则映射（确定性、离线）
  build_from_prompt(prompt, content)            — LLM 解析 + 关键词兜底（honest degradation）
  build(card_or_prompt, ...)                    — 自动识别入口

规则映射核心（8 张风格卡实测特征，见 data/style_cards/）：
  style_id → 基础模板:
    amv_highenergy / hardcore_battle          → amv（高燃）
    cyberpunk                                 → cyberpunk
    ambient_calm / emotional_lyric /
    high_key_bright / vintage_film /
    cinematic_film / 未知                     → ambient（抒情/电影/复古共用氛围基底）
  text_fx.action → 入场预设:
    impact → scale_bounce   glitch → glitch_shake   fade → fade_in
  三旋钮 (1-10) 参数化:
    motion_intensity  → 入场时长/强度（intense/moderate/subtle）
    visual_variance   → 特效激进度（≥7 加 rgb_split/粒子增强；<4 收敛特效）
    information_density → 文案层数（title+sub / title only）
  颜色: 每卡内置调色板（content.colors 可覆盖）
  BeatGrid（可选）→ 预埋 beat_events（kick→顶层文字，strong→粒子/特效层）
"""
from __future__ import annotations

import copy
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.composition_tree import (  # noqa: E402
    AnimationSpec,
    CompositionTree,
    EffectRef,
    LayerSpec,
    build_template,
    validate_composition_tree,
)

# ── 基础模板映射 ─────────────────────────────────────────────────────
_STYLE_TO_BASE = {
    "amv_highenergy": "amv",
    "hardcore_battle": "amv",
    "cyberpunk": "cyberpunk",
    "ambient_calm": "ambient",
    "emotional_lyric": "ambient",
    "high_key_bright": "ambient",
    "vintage_film": "ambient",
    "cinematic_film": "ambient",
}
_DEFAULT_BASE = "ambient"   # 未知风格卡 → 氛围基底（最不炸场）

# text_fx.action → 入场预设（对齐 synthesis_orchestrator.PRESET_TO_STYLE 键）
_TEXTFX_TO_ENTRANCE = {
    "impact": "scale_bounce",
    "glitch": "glitch_shake",
    "fade": "fade_in",
    "scale": "scale_up",
    "slide": "slide_up",
}
_DEFAULT_ENTRANCE = "fade_in"

# 每卡内置调色板 {main, glow, accent}（content.colors 优先）
_STYLE_PALETTES: dict[str, dict[str, str]] = {
    "amv_highenergy": {"main": "#FF0000", "glow": "#FF4500", "accent": "#FFD700"},
    "hardcore_battle": {"main": "#FF2200", "glow": "#FF3300", "accent": "#FFFFFF"},
    "cyberpunk": {"main": "#00F0FF", "glow": "#00BFFF", "accent": "#E0FFFF"},
    "ambient_calm": {"main": "#CDE7FF", "glow": "#A0C4FF", "accent": "#FFFFFF"},
    "emotional_lyric": {"main": "#FFE4E1", "glow": "#FFB6C1", "accent": "#FFF8DC"},
    "cinematic_film": {"main": "#F5F5F0", "glow": "#C8B88A", "accent": "#E8DCC0"},
    "high_key_bright": {"main": "#2B2B2B", "glow": "#666666", "accent": "#FFFFFF"},
    "vintage_film": {"main": "#E8D8B8", "glow": "#C9A66B", "accent": "#8B7355"},
}
_DEFAULT_PALETTE = {"main": "#FFFFFF", "glow": "#FFD700", "accent": "#FFFFFF"}

# 强度三档（对齐 jsx_keyframe_animator.AnimationIntensity）
_INTENSITY_LEVELS = ("subtle", "moderate", "intense")


@dataclass
class BuildResult:
    """风格卡→合成树构建结果"""
    tree: CompositionTree | None = None
    style_id: str = ""
    base_template: str = ""
    offline: bool = True           # 是否走离线规则路径（prompt 入口有意义）
    trace: list[str] = field(default_factory=list)     # 映射决策轨迹（honest）
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "style_id": self.style_id, "base_template": self.base_template,
            "offline": self.offline, "trace": self.trace,
            "warnings": self.warnings,
            "tree": None if self.tree is None else {
                "comp_name": self.tree.comp_name,
                "style_card": self.tree.style_card,
                "duration": self.tree.duration,
                "layers": len(self.tree.layers),
                "beat_events": len(self.tree.beat_events),
            },
        }


def _clamp_knob(v: Any, lo: int = 1, hi: int = 10) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return 5


def _intensity_from_motion(mi: int) -> str:
    """motion_intensity → 效果强度档"""
    if mi >= 7:
        return "intense"
    if mi >= 4:
        return "moderate"
    return "subtle"


def _entrance_from_motion(mi: int) -> tuple[str, int]:
    """motion_intensity → (入场预设, 时长ms)。text_fx 显式 action 优先于本表。"""
    if mi >= 7:
        return "scale_bounce", 500
    if mi >= 4:
        return "slide_up", 600
    return "fade_in", 800


# prompt 关键词 → 风格 id（离线兜底）
_KEYWORD_RULES: list[tuple[tuple[str, ...], str]] = [
    (("高燃", "燃", "战斗", "热血", "打击", "快节奏", "踩点"), "amv_highenergy"),
    (("赛博", "未来", "霓虹", "cyber", "科幻", "全息"), "cyberpunk"),
    (("抒情", "温柔", "治愈", "安静", "氛围", "慢", "ins"), "ambient_calm"),
    (("电影", "质感", "大片", "预告"), "cinematic_film"),
    (("复古", "胶片", "老片", "怀旧"), "vintage_film"),
    (("亮调", "清新", "高调", "明亮"), "high_key_bright"),
]


class StyleTreeBuilder:
    """风格卡 → CompositionTree（M4）

    Parameters:
        fps:        合成帧率（模板默认 30）
        llm_enabled: prompt 入口是否尝试 LLM 解析（失败自动关键词兜底）
    """

    def __init__(self, fps: int = 30, llm_enabled: bool = True):
        self.fps = int(fps)
        self.llm_enabled = bool(llm_enabled)

    # ── 主入口 ───────────────────────────────────────────────────
    def build(self, card_or_prompt: Any, content: dict[str, Any] | None = None,
              grid: Any = None) -> BuildResult:
        """自动识别入口：StyleCard/style_id → 规则路径；str(prompt) → prompt 路径"""
        if isinstance(card_or_prompt, str):
            if self._looks_like_style_id(card_or_prompt):
                return self.build_from_card(card_or_prompt, content, grid)
            return self.build_from_prompt(card_or_prompt, content, grid)
        return self.build_from_card(card_or_prompt, content, grid)

    def _looks_like_style_id(self, s: str) -> bool:
        """风格 id 形如 amv_highenergy（无空格无标点的下划线串）"""
        return bool(re.fullmatch(r"[a-z0-9_]{4,40}", s.strip()))

    def build_from_card(self, card: Any, content: dict[str, Any] | None = None,
                        grid: Any = None) -> BuildResult:
        """风格卡 → CompositionTree（确定性规则映射，离线）"""
        card_dict = self._coerce_card(card)
        style_id = card_dict.get("style_id", "")
        base = _STYLE_TO_BASE.get(style_id, _DEFAULT_BASE)
        trace: list[str] = []
        warnings: list[str] = []
        if style_id not in _STYLE_TO_BASE:
            warnings.append(f"未知风格卡 {style_id or '空'} → 回退 {_DEFAULT_BASE} 基底")
            trace.append(f"base: {_DEFAULT_BASE} (fallback)")

        tree = build_template(base, duration=float(content.get("duration", 5.0))
                              if content else 5.0)
        tree.fps = self.fps
        # 风格卡名 → comp 名保留语义（模板默认 comp 名 + 卡后缀）
        if style_id:
            tree.comp_name = f"{tree.comp_name}_{style_id}"
        tree.meta["style_id"] = style_id
        tree.meta["source"] = "style_card"

        self._apply_knobs(tree, card_dict, content or {}, trace)
        self._apply_textfx(tree, card_dict, trace)
        if grid is not None:
            self._seed_beat_events(tree, grid, trace)

        res = validate_composition_tree(tree)
        if not res["ok"]:
            raise ValueError(f"风格卡 {style_id} 构建产物校验失败: {res['errors']}")
        warnings.extend(res["warnings"])
        return BuildResult(tree=tree, style_id=style_id, base_template=base,
                           offline=True, trace=trace, warnings=warnings)

    def build_from_prompt(self, prompt: str, content: dict[str, Any] | None = None,
                          grid: Any = None) -> BuildResult:
        """一句话 prompt → CompositionTree。

        先尝试 LLM 解析（JSON: style_id/title/subtitle/colors），失败/禁用时
        关键词规则兜底。offline 字段诚实标注实际路径。
        """
        content = dict(content or {})
        parsed: dict[str, Any] = {}
        offline = True
        warnings: list[str] = []
        if self.llm_enabled:
            try:
                parsed = self._parse_via_llm(prompt)
                offline = False
            except Exception as e:  # noqa: BLE001
                warnings.append(f"LLM 解析失败，关键词兜底: {e}")
                parsed = {}
        if not parsed:
            parsed = self._parse_by_keywords(prompt)
            offline = True
            warnings.append("prompt 解析走关键词规则路径（offline）")

        # 合并：content 显式字段优先，其次 LLM/关键词解析，再默认
        merged = dict(parsed)
        merged.update({k: v for k, v in content.items() if v})
        title = str(merged.get("title") or self._default_title(prompt))
        sub = merged.get("subtitle", "")
        palette = dict(parsed.get("colors", {}))
        palette.update((content.get("colors") or {}))
        style_id = str(merged.get("style_id", "") or
                       self._infer_style_id(prompt))
        content_final = {
            "title": title, "subtitle": sub, "duration": merged.get("duration", 5.0),
        }
        if palette:
            content_final["colors"] = palette

        result = self.build_from_card(style_id, content_final, grid)
        result.offline = offline
        result.warnings = warnings + result.warnings
        result.trace.insert(0, f"prompt: {prompt[:40]}")
        return result

    # ── 三旋钮参数化 ─────────────────────────────────────────────
    def _apply_knobs(self, tree: CompositionTree, card: dict[str, Any],
                     content: dict[str, Any], trace: list[str]) -> None:
        mi = _clamp_knob(card.get("motion_intensity"))
        vv = _clamp_knob(card.get("visual_variance"))
        info = _clamp_knob(card.get("information_density"))
        inten = _intensity_from_motion(mi)
        ent_preset, ent_ms = _entrance_from_motion(mi)

        # 文案：title 必选；subtitle 由 info 决定（content.subtitle 显式给则保留）
        title_text = str(content.get("title") or self._card_default_title(card))
        texts = [l for l in tree.layers if l.type == "text"]
        texts.sort(key=lambda l: l.z_index)
        for i, layer in enumerate(texts):
            if i == 0:
                layer.content["text"] = title_text
                layer.name = title_text
            else:
                sub_given = bool(content.get("subtitle"))
                keep_sub = sub_given or (info >= 3 and tree.style_card == "amv") \
                    or (info >= 4 and tree.style_card != "amv")
                if not keep_sub:
                    # 降密：移除多余文字层（保留字幕层的判定由调用方语义保证：
                    # 模板中 z 最大的文字层是副标题）
                    tree.layers = [l for l in tree.layers if l is not layer]
                    trace.append(f"info={info} → 收敛为单文字层")
                    continue
                if sub_given:
                    layer.content["text"] = content["subtitle"]
                    layer.name = content["subtitle"]

        # 颜色（content 覆盖 > 卡调色板 > 模板默认）
        palette = dict(_STYLE_PALETTES.get(card.get("style_id", ""),
                                           _DEFAULT_PALETTE))
        palette.update(content.get("colors") or {})
        for layer in tree.layers:
            if layer.type == "text":
                layer.content["colors"] = dict(palette)

        # 入场动画：motion 档位决定预设与时长
        for layer in tree.layers:
            ent = layer.animations.get("entrance")
            if ent:
                ent.preset = ent_preset
                ent.duration_ms = ent_ms

        # 效果强度：combo 效果统一打 intensity
        for layer in tree.layers:
            for eff in layer.effects:
                if eff.kind == "combo" and "intensity" not in eff.params:
                    eff.params["intensity"] = inten

        # 视觉冲击激进度（visual_variance）
        for layer in tree.layers:
            if vv >= 7:
                if layer.type == "text" and not any(
                        e.value == "rgb_split" for e in layer.effects):
                    layer.effects.append(EffectRef("combo", "rgb_split",
                                                   {"intensity": inten}))
                if layer.type == "particle":
                    layer.content["count"] = int(layer.content.get("count", 80) * 1.5)
            elif vv < 4:
                layer.effects = [e for e in layer.effects
                                 if e.value not in ("rgb_split", "neon_glow")]
                if layer.type == "particle":
                    layer.content["count"] = max(10, int(layer.content.get("count", 80) * 0.5))

        trace.append(f"knobs: motion={mi}({ent_preset}/{ent_ms}ms/{inten}) "
                     f"variance={vv} density={info}")

    @staticmethod
    def _card_default_title(card: dict[str, Any]) -> str:
        name = str(card.get("name", ""))
        return name if name else "AE SYNTH"

    def _apply_textfx(self, tree: CompositionTree, card: dict[str, Any],
                      trace: list[str]) -> None:
        """text_fx.action 显式映射入场预设（优先于三旋钮推导）"""
        textfx = card.get("text_fx") or []
        if not textfx:
            return
        action = str(textfx[0].get("action", ""))
        preset = _TEXTFX_TO_ENTRANCE.get(action)
        if preset is None:
            return
        for layer in tree.layers:
            ent = layer.animations.get("entrance")
            if ent:
                ent.preset = preset
        trace.append(f"text_fx.action={action} → entrance={preset}")

    # ── 节拍预埋（M3 联动，可选）──────────────────────────────────
    @staticmethod
    def _seed_beat_events(tree: CompositionTree, grid: Any,
                          trace: list[str]) -> None:
        """BeatGrid → 预埋 beat_events（M3 仍可再富化，不冲突）"""
        try:
            kicks = list(getattr(grid, "kick", []) or [])
            strongs = list(getattr(grid, "strong", []) or [])
        except Exception:  # noqa: BLE001
            return
        texts = sorted([l for l in tree.layers if l.type == "text"],
                       key=lambda l: -l.z_index)
        particles = [l for l in tree.layers if l.type == "particle"]
        target_text = texts[0].id if texts else ""
        target_fx = particles[0].id if particles else target_text
        added = 0
        for t in kicks:
            if 0.0 <= float(t) <= tree.duration:
                tree.beat_events.append({"time": float(t), "beat_type": "kick",
                                         "layer_id": target_text})
                added += 1
        for t in strongs:
            if 0.0 <= float(t) <= tree.duration:
                tree.beat_events.append({"time": float(t), "beat_type": "strong",
                                         "layer_id": target_fx})
                added += 1
        if added:
            trace.append(f"beat_seed: {added} 事件（kick→{target_text}, strong→{target_fx}）")

    # ── prompt 解析 ──────────────────────────────────────────────
    def _parse_via_llm(self, prompt: str) -> dict[str, Any]:
        """LLM 解析 prompt → 参数 dict。任何失败抛异常（调用方兜底）。"""
        import asyncio

        from core.llm_gateway import llm_gateway  # 惰性导入

        system = (
            "你是风格卡编译器。把用户的剪辑需求解析为 JSON，只输出 JSON："
            '{"style_id": 8张卡之一(amv_highenergy/cyberpunk/ambient_calm/'
            'emotional_lyric/cinematic_film/hardcore_battle/high_key_bright/'
            'vintage_film), "title": 主标题(≤12字), "subtitle": 副标题(可空), '
            '"colors": {"main": "#RRGGBB", "glow": "#RRGGBB", "accent": "#RRGGBB"}, '
            '"duration": 秒数(3-15)}'
        )
        resp = asyncio.run(llm_gateway.chat(
            message=prompt, system_prompt=system, temperature=0.2, max_tokens=400))
        if not getattr(resp, "success", False) or not getattr(resp, "content", ""):
            raise RuntimeError(f"LLM 无响应: {getattr(resp, 'error', '')}")
        text = resp.content
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("LLM 输出无 JSON")
        data = json.loads(text[start:end + 1])
        if not isinstance(data, dict) or not data.get("style_id"):
            raise RuntimeError("LLM JSON 缺 style_id")
        return data

    @staticmethod
    def _parse_by_keywords(prompt: str) -> dict[str, Any]:
        for kws, style_id in _KEYWORD_RULES:
            if any(k in prompt for k in kws):
                return {"style_id": style_id}
        return {}

    @staticmethod
    def _infer_style_id(prompt: str) -> str:
        parsed = StyleTreeBuilder._parse_by_keywords(prompt)
        return parsed.get("style_id", "ambient_calm")

    @staticmethod
    def _default_title(prompt: str) -> str:
        # 优先取引号内短语；否则截断到 12 字
        m = re.search(r"[「『\"“]([^」』\"”]{1,12})[」』\"”]", prompt)
        if m:
            return m.group(1)
        return prompt.strip()[:12] or "AE SYNTH"

    # ── 工具 ─────────────────────────────────────────────────────
    _CARD_FIELDS = ("style_id", "name", "description", "visual_variance",
                    "motion_intensity", "information_density", "text_fx",
                    "particle_presets", "color_grade_params",
                    "preferred_cameras", "forbidden_cameras", "anti_patterns")

    @staticmethod
    def _normalize_card_dict(d: dict[str, Any]) -> dict[str, Any]:
        """dict 形式（如 StyleCard.to_dict()）→ 旋钮扁平化到顶层"""
        out = dict(d)
        tp = d.get("taste_profile") or {}
        if isinstance(tp, dict):
            for k in ("visual_variance", "motion_intensity", "information_density"):
                if k not in out and tp.get(k) is not None:
                    out[k] = tp[k]
        return out

    @classmethod
    def _coerce_card(cls, card: Any) -> dict[str, Any]:
        """StyleCard 对象 / style_id 字符串 / dict → 统一扁平 dict"""
        if isinstance(card, str):
            try:
                from knowledge.style_card import load_card  # 只读消费
                c = load_card(card)
                if c is None:
                    return {"style_id": card}
                card = c  # 落到对象分支，直取扁平字段
            except Exception:  # noqa: BLE001
                return {"style_id": card}
        if isinstance(card, dict):
            return cls._normalize_card_dict(card)
        # dataclass 对象：直取扁平字段（text_fx 等不在 to_dict() 里，必须走属性）
        return {k: getattr(card, k) for k in cls._CARD_FIELDS if hasattr(card, k)}


__all__ = ["StyleTreeBuilder", "BuildResult",
           "_STYLE_TO_BASE", "_TEXTFX_TO_ENTRANCE", "_STYLE_PALETTES"]
