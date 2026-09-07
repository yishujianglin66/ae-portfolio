"""CompositionTree — 后期特效合成的合成树数据模型（M1a）

把"单效果脚本"升级为"多图层多效果合成树"的核心 schema：
- 图层栈（solid/text/adjustment/particle/footage）
- 效果引用（matchName 直通 + combo 组合引用）
- 三段动画（entrance/loop/exit）
- 时间轴（time_range + beat_events 节拍挂点，为 M3 BeatLock 预留）

设计原则：
1. 叶子节点全部复用现有 JSX 生成器（textfx_effects/effect_depth/text_3d/jsx_keyframe_animator）
2. 模板参数与风格卡（style_card）对齐：amv/cyberpunk/ambient 三 pilot
3. schema 校验在生成与执行前双重把关（validate 铁律延续）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── 常量 ────────────────────────────────────────────────────────────
# gen_fx: 生成式特效素材层（M6）— 执行时生成带 alpha 素材（ComfyUI/程序化），
# content: {prompt, kind(glow|smoke|spark|light_ray|flow), engine(auto|comfyui|procedural)}
LAYER_TYPES = ("solid", "text", "adjustment", "particle", "footage", "gen_fx")
ANIMATION_PHASES = ("entrance", "loop", "exit")
EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out", "bounce", "elastic")

# 风格卡三 pilot（与 style_card schema 对齐）
STYLE_CARDS = ("amv", "cyberpunk", "ambient")  # 基础三卡(与 style_card schema 对齐)
# TEMPLATE_BUILDERS 支持的扩展卡(genfx/edit/vintage 等)动态并入校验集
EXTENDED_STYLE_CARDS = ("genfx", "edit", "vintage")


@dataclass
class EffectRef:
    """效果引用：matchName 直通或 combo 组合"""
    kind: str  # "match" | "combo"
    value: str  # matchName 或组合名（neon_glow/cyber_glow/hologram/fire_ice/color_grade）
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnimationSpec:
    """单段动画：entrance/loop/exit"""
    preset: str                      # 关键帧动画器预设名
    duration_ms: int = 500
    easing: str = "ease_out"
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LayerSpec:
    """图层规格"""
    id: str
    type: str                        # LAYER_TYPES
    name: str = ""
    z_index: int = 0
    time_range: List[float] = field(default_factory=lambda: [0.0, 5.0])
    effects: List[EffectRef] = field(default_factory=list)
    animations: Dict[str, AnimationSpec] = field(default_factory=dict)  # phase -> spec
    content: Dict[str, Any] = field(default_factory=dict)  # type 相关：text/颜色/素材路径
    children: List["LayerSpec"] = field(default_factory=list)  # 预留：父子绑定（track matte 等）


@dataclass
class CompositionTree:
    """合成树根"""
    comp_name: str
    style_card: str                  # STYLE_CARDS
    width: int = 1920
    height: int = 1080
    fps: int = 30
    duration: float = 5.0
    layers: List[LayerSpec] = field(default_factory=list)
    beat_events: List[Dict[str, Any]] = field(default_factory=list)  # {time, beat_type, layer_id}
    meta: Dict[str, Any] = field(default_factory=dict)


# ── schema 校验 ─────────────────────────────────────────────────────
def validate_composition_tree(tree: CompositionTree) -> Dict[str, Any]:
    """合成树校验（执行前把关；警告不阻断，错误阻断）"""
    errors: List[str] = []
    warnings: List[str] = []

    if tree.style_card not in STYLE_CARDS + EXTENDED_STYLE_CARDS:
        errors.append(f"style_card {tree.style_card} 不在 {STYLE_CARDS + EXTENDED_STYLE_CARDS}")
    if tree.duration <= 0:
        errors.append(f"duration {tree.duration} 非法")
    if not tree.layers:
        warnings.append("无图层（空合成）")

    seen_ids = set()
    for layer in tree.layers:
        if layer.id in seen_ids:
            errors.append(f"图层 id 重复: {layer.id}")
        seen_ids.add(layer.id)
        if layer.type not in LAYER_TYPES:
            errors.append(f"图层 {layer.id} 类型 {layer.type} 非法")
        if layer.time_range[1] < layer.time_range[0]:
            errors.append(f"图层 {layer.id} time_range 倒置")
        if layer.time_range[1] > tree.duration + 0.001:
            warnings.append(f"图层 {layer.id} 超出合成时长")
        for phase, spec in layer.animations.items():
            if phase not in ANIMATION_PHASES:
                errors.append(f"图层 {layer.id} 动画相位 {phase} 非法")
            if spec.easing not in EASINGS:
                warnings.append(f"图层 {layer.id} 缓动 {spec.easing} 不在标准集")
            if spec.duration_ms <= 0:
                errors.append(f"图层 {layer.id} 动画时长非法")
        for eff in layer.effects:
            if eff.kind not in ("match", "combo"):
                errors.append(f"图层 {layer.id} 效果 kind {eff.kind} 非法")
        if layer.type == "text" and not layer.content.get("text"):
            warnings.append(f"文字图层 {layer.id} 无文字内容")
        if layer.type == "footage" and not layer.content.get("path"):
            errors.append(f"素材图层 {layer.id} 无 path")
        if layer.type == "gen_fx" and not layer.content.get("prompt"):
            errors.append(f"生成特效层 {layer.id} 无 prompt")
        _fx_kind = layer.content.get("kind", "glow") if layer.type == "gen_fx" else None
        if _fx_kind and _fx_kind not in ("glow", "smoke", "spark", "light_ray", "flow"):
            errors.append(f"生成特效层 {layer.id} kind {_fx_kind} 非法")

    # 节拍事件校验（M3 预留：事件必须落在合成时长内且图层存在）
    for ev in tree.beat_events:
        if not (0 <= ev.get("time", -1) <= tree.duration):
            errors.append(f"节拍事件时间越界: {ev}")
        if ev.get("layer_id") and ev["layer_id"] not in seen_ids:
            errors.append(f"节拍事件引用不存在的图层: {ev.get('layer_id')}")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


# ── 模板工厂（3 pilot 风格） ────────────────────────────────────────
def _text_layer(lid: str, text: str, z: int, start: float, end: float,
                effects: List[EffectRef], entrance: str, size: int = 96,
                colors: Optional[Dict[str, str]] = None) -> LayerSpec:
    colors = colors or {"main": "#FFFFFF", "glow": "#FFD700", "accent": "#FFFFFF"}
    return LayerSpec(
        id=lid, type="text", name=text, z_index=z,
        time_range=[start, end],
        content={"text": text, "size": size, "colors": colors,
                 "font": "SourceHanSansCN-Bold"},
        effects=effects,
        animations={"entrance": AnimationSpec(preset=entrance, duration_ms=600,
                                               easing="ease_out"),
                    "exit": AnimationSpec(preset="fade_out", duration_ms=400,
                                          easing="ease_in")},
    )


def build_amv_template(duration: float = 5.0) -> CompositionTree:
    """AMV 高燃模板：快节奏入场 + rgb_split + glow + 打击感"""
    return CompositionTree(
        comp_name="AMV_HighEnergy", style_card="amv", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_Black", z_index=0,
                      time_range=[0, duration],
                      content={"color": [0, 0, 0]}),
            _text_layer("title", "FINAL CLASH", 1, 0.2, duration - 0.2,
                        [EffectRef("combo", "neon_glow", {"intensity": "intense"}),
                         EffectRef("match", "ADBE Glo2", {"radius": 30, "intensity": 2.5})],
                        "scale_bounce", size=110,
                        colors={"main": "#FF0000", "glow": "#FF4500", "accent": "#FFD700"}),
            _text_layer("sub", "THE BATTLE BEGINS", 2, 0.8, duration - 0.8,
                        [EffectRef("combo", "rgb_split", {"intensity": "intense"})],
                        "slide_up", size=48),
            LayerSpec(id="fx_impact", type="particle", name="Impact", z_index=3,
                      time_range=[0.5, duration],
                      content={"kind": "burst", "count": 80},
                      effects=[EffectRef("match", "CC Particle World", {})]),
        ],
        beat_events=[
            {"time": 0.2, "beat_type": "kick", "layer_id": "title"},
            {"time": 1.0, "beat_type": "snare", "layer_id": "fx_impact"},
        ],
        meta={"energy": "high", "target": "B站漫剪高燃段"},
    )


def build_cyberpunk_template(duration: float = 5.0) -> CompositionTree:
    """赛博朋克模板：网格背景 + 霓虹 + 全息"""
    return CompositionTree(
        comp_name="Cyber_Opening", style_card="cyberpunk", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_DeepBlue", z_index=0,
                      time_range=[0, duration],
                      content={"color": [5, 5, 30]}),
            LayerSpec(id="grid", type="adjustment", name="Grid_Decor", z_index=1,
                      time_range=[0, duration],
                      effects=[EffectRef("match", "ADBE Grid", {"opacity": 15})]),
            _text_layer("title", "CYBERPUNK", 2, 0.5, duration - 0.5,
                        [EffectRef("combo", "cyber_glow"),
                         EffectRef("combo", "hologram", {"scan": True})],
                        "glitch_shake", size=120,
                        colors={"main": "#00F0FF", "glow": "#00BFFF", "accent": "#E0FFFF"}),
            LayerSpec(id="vignette", type="adjustment", name="Vignette", z_index=4,
                      time_range=[0, duration],
                      effects=[EffectRef("combo", "color_grade", {"grade": "cold"})]),
        ],
        beat_events=[{"time": 0.5, "beat_type": "kick", "layer_id": "title"}],
        meta={"energy": "mid", "target": "片头/转场"},
    )


def build_ambient_template(duration: float = 5.0) -> CompositionTree:
    """氛围模板：柔和渐入 + 光晕脉冲 + 慢呼吸"""
    return CompositionTree(
        comp_name="Ambient_Mood", style_card="ambient", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_Warm", z_index=0,
                      time_range=[0, duration],
                      content={"color": [20, 15, 10]}),
            _text_layer("title", "静谧", 1, 0.8, duration - 0.8,
                        [EffectRef("match", "ADBE Glo2", {"radius": 15, "intensity": 1.2})],
                        "fade_in", size=72,
                        colors={"main": "#FFE4B5", "glow": "#FFD700", "accent": "#FFF8DC"}),
            LayerSpec(id="breath", type="adjustment", name="SoftBreathe", z_index=2,
                      time_range=[0, duration],
                      effects=[EffectRef("match", "ADBE Glo2", {"intensity": 0.8})],
                      animations={"loop": AnimationSpec(preset="glow_pulse",
                                                        duration_ms=2000,
                                                        easing="ease_in_out")}),
        ],
        meta={"energy": "low", "target": "抒情/收尾段"},
    )


def build_fate_composite_template(footage_path: str, duration: float = 5.0,
                                  title_text: str = "FATE") -> CompositionTree:
    """抠像合成模板（M1 收尾）：黑色底 + RGBA 透明 MOV 人物层 + 霓虹标题。

    素材层约定：
      content.path        素材绝对路径（透明 MOV / PNG 序列首帧）
      content.matting_mode "rgba"（默认，alpha 内嵌）| "track_matte"（彩色视频+遮罩序列）
      content.matte_dir   track_matte 模式的遮罩序列目录（mask_00000.png 起）
      content.fit         "cover"（默认铺满）| "fit"（完整显示）| "none"
    """
    return CompositionTree(
        comp_name="Fate_Composite", style_card="amv", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_Black", z_index=0,
                      time_range=[0, duration],
                      content={"color": [0, 0, 0]}),
            LayerSpec(id="character", type="footage", name="Character", z_index=1,
                      time_range=[0, duration],
                      content={"path": footage_path, "matting_mode": "rgba",
                               "fit": "cover"}),
            _text_layer("title", title_text, 2, 0.6, duration - 0.4,
                        [EffectRef("combo", "cyber_glow")],
                        "scale_bounce", size=110,
                        colors={"main": "#FFD700", "glow": "#FF8C00", "accent": "#FFF8DC"}),
        ],
        beat_events=[{"time": 0.6, "beat_type": "kick", "layer_id": "title"}],
        meta={"energy": "high", "target": "AMV 抠像合成/片头"},
    )


def build_genfx_template(duration: float = 5.0, title_text: str = "GEN FX") -> CompositionTree:
    """生成特效演示模板（M6）：程序化/ComfyUI 特效素材层 + 霓虹标题。

    gen_fx 层在执行前由 core.gen_fx_provider.resolve_gen_fx_layers 生成素材
    （带 alpha PNG），随后按 footage 逻辑导入 AE。
    """
    return CompositionTree(
        comp_name="GenFx_Showcase", style_card="cyberpunk", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_DeepBlue", z_index=0,
                      time_range=[0, duration],
                      content={"color": [5, 5, 30]}),
            LayerSpec(id="fx_glow", type="gen_fx", name="AuraGlow", z_index=1,
                      time_range=[0, duration],
                      content={"prompt": "青色能量辉光", "kind": "glow", "engine": "auto",
                               "fit": "cover"},
                      animations={"loop": AnimationSpec(preset="glow_pulse",
                                                        duration_ms=1600,
                                                        easing="ease_in_out")}),
            LayerSpec(id="fx_spark", type="gen_fx", name="SparkBurst", z_index=2,
                      time_range=[0.4, duration],
                      content={"prompt": "金色火花爆发", "kind": "spark", "engine": "auto",
                               "fit": "cover"}),
            _text_layer("title", title_text, 3, 0.2, duration - 0.2,
                        [EffectRef("combo", "cyber_glow")],
                        "scale_bounce", size=110,
                        colors={"main": "#00F0FF", "glow": "#00BFFF", "accent": "#E0FFFF"}),
        ],
        beat_events=[{"time": 0.4, "beat_type": "kick", "layer_id": "fx_spark"}],
        meta={"energy": "high", "target": "M6 生成特效层验收"},
    )


def build_edit_template(duration: float = 5.0, title_text: str = "AWAKEN") -> CompositionTree:
    """顶尖慢剪 edit 模板（M7）：字符级 stagger + 节拍 punch/shake/burst + grain。

    效果语汇（全部确定性关键帧/表达式, 帧精确）:
      char_anim  Text Animator Offset 扫动 — 逐字点亮 + 字距聚拢
      punch      节拍瞬间 scale 超调+衰减（8%/12% 交替力度）
      shake      高频多轴 wiggle（手持感, 节拍窗口内）
      rgb_burst  Tint 对撞色卡点爆开（红↔蓝 flash）
      grain      全合成胶片颗粒后处理层
    """
    beats = [0.5, 1.5, 2.5, 3.5]          # 4 个节拍锚点（真实场景由 BeatLock 提供）
    return CompositionTree(
        comp_name="Edit_TopTier", style_card="amv", duration=duration,
        layers=[
            LayerSpec(id="bg", type="solid", name="BG_Black", z_index=0,
                      time_range=[0, duration],
                      content={"color": [8, 8, 12]}),
            LayerSpec(id="title", type="text", name="Title", z_index=1,
                      time_range=[0.3, duration - 0.3],
                      content={
                          "text": title_text, "size": 170,
                          "colors": {"main": "#FFFFFF", "glow": "#9FE8FF",
                                     "accent": "#FFFFFF"},
                          "font": "Impact",
                          "char_anim": {"preset": "tracking_stagger",
                                        "duration_ms": 480,
                                        "tracking": 22, "rotation": 0},
                          "edit_fx": {
                              "punch": {"times": [0.5, 2.5], "amount": 10},
                              "shake": {"freq": 15, "amp": 14, "seed": 4,
                                        "start": 0.5, "end": 2.2},
                              "glow_hit": {"times": [1.5, 3.5], "intensity": 2.5},
                          },
                      },
                      effects=[EffectRef("match", "ADBE Glo2",
                                         {"radius": 22, "intensity": 1.0})],
                      animations={"exit": AnimationSpec(preset="fade_out",
                                                        duration_ms=350,
                                                        easing="ease_in")}),
            LayerSpec(id="sub", type="text", name="SubLine", z_index=2,
                      time_range=[1.2, duration - 0.5],
                      content={
                          "text": "N O   E S C A P E", "size": 54,
                          "colors": {"main": "#FF4D6D", "glow": "#FF4D6D",
                                     "accent": "#FFFFFF"},
                          "font": "Arial",
                          "char_anim": {"preset": "tracking_stagger",
                                        "duration_ms": 380, "tracking": 12},
                          "edit_fx": {"rgb_burst": {"times": [1.5, 3.5]}},
                      }),
            LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                      time_range=[0, duration],
                      content={"edit_fx_layer": "grain", "amount": 12}),
        ],
        beat_events=[
            {"time": 0.5, "beat_type": "kick", "layer_id": "title"},
            {"time": 1.5, "beat_type": "snare", "layer_id": "sub"},
            {"time": 2.5, "beat_type": "kick", "layer_id": "title"},
            {"time": 3.5, "beat_type": "snare", "layer_id": "sub"},
        ],
        meta={"energy": "high", "target": "顶尖慢剪 edit 基准（M7 验收）"},
    )


TEMPLATE_BUILDERS = {
    "amv": build_amv_template,
    "cyberpunk": build_cyberpunk_template,
    "ambient": build_ambient_template,
    "fate_composite": build_fate_composite_template,
    "genfx": build_genfx_template,
    "edit": build_edit_template,
}


def build_template(style_card: str, duration: float = 5.0, **kwargs) -> CompositionTree:
    """按风格卡构建合成树模板；fate_composite 需传 footage_path=..."""
    if style_card not in TEMPLATE_BUILDERS:
        raise ValueError(f"未知风格卡 {style_card}，可选 {list(TEMPLATE_BUILDERS)}")
    return TEMPLATE_BUILDERS[style_card](duration, **kwargs)


__all__ = [
    "CompositionTree", "LayerSpec", "EffectRef", "AnimationSpec",
    "validate_composition_tree", "build_template", "build_fate_composite_template",
    "TEMPLATE_BUILDERS", "LAYER_TYPES", "STYLE_CARDS",
]
