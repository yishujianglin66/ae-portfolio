"""build_real_edit.py — 真实动漫素材全要素成片（P9）

要素: 真实FATE素材(speed_ramp斜坡) + Particular火花(物理参数) + 段落变奏
     + 真色差 + Anton巨字扫动 + S_Shake窗口 + gen_fx光尘 + grain
输出: Edit_RealFootage 合成 → aerender 渲染
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.composition_tree import AnimationSpec, CompositionTree, EffectRef, LayerSpec
from core.synthesis_orchestrator import SynthesisOrchestrator

DUR = 5.0
FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
SRC_DUR = 16.37

tree = CompositionTree(
    comp_name="Edit_RealV2", style_card="edit", duration=DUR,
    layers=[
        # 真实素材层: 速度斜坡(正常→急停定格→爆发加速)
        LayerSpec(id="clip", type="footage", name="FATE", z_index=0,
                  time_range=[0, DUR],
                  content={
                      "path": str(Path(FOOTAGE).resolve()),
                      "matting_mode": "rgba", "fit": "cover",
                      "source_dur": SRC_DUR,
                      "speed_ramps": [
                          {"t": 0.0, "v": 1.0},     # 正常速
                          {"t": 2.3, "v": 1.0},
                          {"t": 2.42, "v": 0.02},   # 急停定格(drop kick 前)
                          {"t": 2.6, "v": 0.02},
                          {"t": 2.7, "v": 2.2},     # 爆发加速
                          {"t": 3.6, "v": 2.2},
                          {"t": 3.8, "v": 1.0},     # 回正常
                          {"t": DUR, "v": 1.0},
                      ],
                      "edit_fx": {"punch": {}, "shake": {}},
                  }),
        # Particular 火花: drop kick 时刻爆发(物理参数版)
        LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                  time_range=[0, DUR],
                  content={"template": "spark", "t_hit": 2.5}),
        # Anton 巨字: 字符扫动 + punch + glow
        LayerSpec(id="title", type="text", name="Title", z_index=2,
                  time_range=[0.4, DUR - 0.4],
                  content={"text": "CLASH", "size": 200,
                           "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                           "font": "auto",
                           "char_anim": {"preset": "tracking_stagger",
                                         "duration_ms": 520, "tracking": 26},
                           "edit_fx": {"punch": {}, "glow_hit": {}}},
                  effects=[EffectRef("match", "ADBE Glo2",
                                     {"radius": 26, "intensity": 1.4})]),
        # Bebas 副标: 色差爆开
        LayerSpec(id="sub", type="text", name="Sub", z_index=3,
                  time_range=[2.4, DUR - 0.4],
                  content={"text": "NO ESCAPE", "size": 64,
                           "colors": {"main": "#FF4D6D", "glow": "#FF4D6D", "accent": "#FFF"},
                           "font": "auto", "font_role": "sub",
                           "edit_fx": {"rgb_burst": {}},
                           "char_anim": {"preset": "tracking_stagger",
                                         "duration_ms": 400, "tracking": 14}}),
        # gen_fx 氛围光尘
        LayerSpec(id="aura", type="gen_fx", name="Aura", z_index=4,
                  time_range=[0, DUR],
                  content={"prompt": "青色能量辉光", "kind": "glow",
                           "engine": "auto", "fit": "cover"}),
        LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                  time_range=[0, DUR],
                  content={"edit_fx_layer": "grain", "amount": 9}),
    ],
    beat_events=[
        {"time": 2.5, "beat_type": "kick", "layer_id": "title"},
        {"time": 1.5, "beat_type": "snare", "layer_id": "sub"},
        {"time": 3.5, "beat_type": "snare", "layer_id": "sub"},
    ],
    meta={"target": "真实素材全要素验收(P9)"},
)

sections = [
    {"type": "intro", "start": 0, "end": 1.4},
    {"type": "build", "start": 1.4, "end": 2.4},
    {"type": "drop", "start": 2.4, "end": 3.9},
    {"type": "outro", "start": 3.9, "end": DUR},
]

o = SynthesisOrchestrator()
r = o.execute(tree, dry_run=False, sections=sections)
print("真机执行:", r["status"], "| gen_fx:", r["gen_fx_materials"],
      "| 警告:", r.get("warnings", [])[:3] or "无")
