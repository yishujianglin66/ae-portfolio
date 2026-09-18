"""image_fx.py — 特效贴图叠加层（14 类资产 → 合成树 footage 图层）

把现成美术资产 (刀光/魔法阵/序列帧等透明 PNG) 变成撞拍时刻的叠加层:
  LayerSpec(type="footage") + 透明 PNG + 入场缩放 + 混合模式建议。

与 gen_fx (生成式) / particle (参数粒子) 互补: 这是"实战验证过的现成美术"。

⚠ 2026-08-27 事故: 本文件曾被 "rebuilt baseline" 残废版覆盖
  (pick_fx_layer 返回纯色 solid, 贴图资产静默失效), 本版从开发会话记录完整重建。

用法:
    from core.image_fx import pick_fx_layer, FX_CATEGORIES
    layer = pick_fx_layer("slash", t_hit=2.5, seed=7)   # → LayerSpec
    layers = pick_fx_layers(beat_events, seed=7)         # 节拍驱动批量
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional

PROJECT = Path(__file__).resolve().parent.parent
FX_INDEX = PROJECT / "data" / "fx_assets" / "index.json"

FX_CATEGORIES = [
    "slash", "magic_circle", "frame_seq", "burst", "smoke", "sparkle",
    "splash", "pattern", "streak", "uv_anim", "object", "prop_fx", "tile", "glyph",
]

# 节拍类型 → 贴图类别偏好 (撞拍语义)
BEAT_FX_MAP = {
    "kick": ["slash", "burst", "splash"],     # 撞击 → 刀光/爆开/溅射
    "snare": ["streak", "sparkle"],           # 切点 → 条光/闪光
    "drop": ["burst", "magic_circle"],        # 爆发 → 扩散/魔法阵
    "build": ["smoke", "uv_anim"],            # 铺垫 → 烟雾/流动
    "glitch": ["pattern", "glyph"],           # 故障 → 图案/字符
}


def _pool(category: str) -> list[str]:
    idx = json.loads(FX_INDEX.read_text(encoding="utf-8"))
    return idx.get(category, [])


def pick_fx_layer(category: str, t_hit: float = 0.0, duration: float = 0.6,
                  seed: int = 42, z_index: int = 5) -> object | None:
    """类别 → 随机选一张贴图构造 footage 图层。无资产返回 None。"""
    from core.composition_tree import LayerSpec
    pool = _pool(category)
    if not pool:
        return None
    rng = random.Random(seed + int(t_hit * 100))
    f = rng.choice(pool)
    return LayerSpec(
        id=f"fx_{category}", type="footage", name=f"FX_{category}", z_index=z_index,
        time_range=[max(0.0, t_hit - 0.1), t_hit + duration],
        content={
            "path": f, "fit": "contain", "opacity": 85,
            # 撞拍入场: punch 缩放 (scale 关键帧由 edit_fx punch 近似)
            "edit_fx": {"punch": {"amount": 12, "times": [max(0.0, t_hit - 0.1)]}},
            "blend_hint": "screen",  # 亮部叠加以保持底图
        },
    )


def pick_fx_layers(beat_events: list[dict], seed: int = 42,
                   max_layers: int = 4) -> list[object]:
    """节拍事件 → 贴图图层批量 (每 beat_type 按偏好池选类, 上限防过载)。"""
    layers = []
    rng = random.Random(seed)
    for ev in beat_events:
        if len(layers) >= max_layers:
            break
        t = float(ev.get("time", 0))
        bt = str(ev.get("beat_type", "snare")).lower()
        cats = BEAT_FX_MAP.get(bt, ["sparkle"])
        cat = rng.choice(cats)
        layer = pick_fx_layer(cat, t_hit=t, seed=seed + len(layers), z_index=5 + len(layers))
        if layer is not None:
            layers.append(layer)
    return layers


__all__ = ["pick_fx_layer", "pick_fx_layers", "FX_CATEGORIES", "BEAT_FX_MAP"]
