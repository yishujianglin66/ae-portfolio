from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

STYLE_CARDS = ("amv", "cyberpunk", "ambient")
LAYER_TYPES = {"solid", "adjustment", "text", "footage", "particle"}

@dataclass
class EffectRef:
    kind: str
    name: str
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnimationSpec:
    property: str
    keyframes: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class LayerSpec:
    id: str
    type: str
    name: str
    z_index: int = 0
    time_range: List[float] = field(default_factory=lambda: [0.0, 1.0])
    content: Dict[str, Any] = field(default_factory=dict)
    effects: List[EffectRef] = field(default_factory=list)
    animations: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CompositionTree:
    comp_name: str
    style_card: str
    duration: float = 5.0
    layers: List[LayerSpec] = field(default_factory=list)
    beat_events: List[Dict[str, Any]] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    width: int = 1920
    height: int = 1080

def validate_composition_tree(tree: CompositionTree) -> Dict[str, Any]:
    errors, warnings = [], []
    if tree.style_card not in STYLE_CARDS and tree.style_card != "edit":
        errors.append(f"非法风格卡: {tree.style_card}")
    ids = set()
    for layer in tree.layers:
        if layer.id in ids: errors.append(f"重复 id: {layer.id}")
        ids.add(layer.id)
        if layer.type not in LAYER_TYPES: errors.append(f"非法图层类型: {layer.type}")
        if len(layer.time_range) != 2 or layer.time_range[0] < 0 or layer.time_range[1] < layer.time_range[0]:
            errors.append(f"图层时间范围非法: {layer.id}")
        elif layer.time_range[1] > tree.duration: warnings.append(f"图层超出合成时长: {layer.id}")
        if layer.type == "footage" and not layer.content.get("path"):
            errors.append(f"footage 缺少 path: {layer.id}")
    for beat in tree.beat_events:
        if not 0 <= float(beat.get("time", -1)) <= tree.duration:
            errors.append(f"节拍越界: {beat}")
        ref = beat.get("layer_id")
        if ref and ref not in ids: errors.append(f"节拍引用不存在的图层: {ref}")
    return {"ok": not errors, "errors": errors, "warnings": warnings}

def build_template(style_card: str) -> CompositionTree:
    if style_card not in STYLE_CARDS: raise ValueError(f"未知风格卡: {style_card}")
    layers = [LayerSpec("bg", "solid", "Background", 0, [0, 5], {"color": [0,0,0]}),
              LayerSpec("title", "text", "Title", 2, [0.2, 4.8], {"text":"AE KNOWLEDGE", "size":72, "font":"auto"}, effects=[EffectRef("match", "ADBE Glo2", {"radius": 30})], animations={"entrance": {"opacity":[0,100]}})]
    if style_card == "amv": layers.append(LayerSpec("particle", "particle", "Particles", 1, [0,5], {"template":"spark"}))
    elif style_card == "cyberpunk": layers.append(LayerSpec("grade", "adjustment", "Grade", 3, [0,5], {"edit_fx_layer":"grain"}, effects=[EffectRef("combo","cyber_glow")]))
    else: layers.append(LayerSpec("loop", "solid", "Ambient Loop", 1, [0,5], {"color":[20,20,30]}, animations={"loop": True}))
    return CompositionTree(style_card=style_card, comp_name=f"Template_{style_card}", duration=5.0, layers=layers)

def build_fate_composite_template(path: str, duration: float = 5.0) -> CompositionTree:
    return CompositionTree("FateComposite", "amv", duration, [LayerSpec("layer1", "footage", "Footage", 1, [0,duration], {"path":path, "fit":"cover"})])
