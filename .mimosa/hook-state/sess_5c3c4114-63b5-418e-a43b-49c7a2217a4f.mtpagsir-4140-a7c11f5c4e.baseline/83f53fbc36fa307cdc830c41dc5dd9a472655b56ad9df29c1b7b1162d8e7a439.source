"""resource_showcase.py — 资源全开演示成片（肉眼可见的资源利用）

grand_finale 是"管线验证"（保守）, 本片是"资源秀肌肉":
  1. 贴图全屏化: 每拍一层全屏 cover + 1.2s 持续 + punch 20
  2. 序列帧连播: 序列帧贴图 8 连张快切 (3帧/张 = 手动动画)
  3. LUT 四联 A/B: 同一片段 [无LUT | 好莱坞 | 复古电影 | 夏日光辉] 拼接对比
  4. SFX 全拍: 每个节拍都配音效 (impact/whoosh/riser/glitch 全池用上)

输出: output/resource_showcase/showcase.mp4 + lut_ab.mp4 (LUT 对比段)

用法:
  python scripts/resource_showcase.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.m2_auto_iterate import render_tree  # noqa: E402
from core.sfx_layer import plan_sfx, mix_sfx  # noqa: E402
from core.lut_pipeline import load_sampling, transcode_with_lut  # noqa: E402

OUT_DIR = PROJECT / "output" / "resource_showcase"
DUR = 8.0
FX_IDX = json.loads((PROJECT / "data" / "fx_assets" / "index.json").read_text(encoding="utf-8"))
SEQ_DIR = PROJECT / "resources" / "effects" / "序列帧贴图"


def big_fx_layer(category: str, t_hit: float, dur: float, z: int, seed_tweak=0):
    """全屏化贴图层: cover 全屏 + 长持续 + 强 punch (与 image_fx 的保守版对比)。"""
    from core.composition_tree import LayerSpec
    import random
    pool = FX_IDX.get(category, [])
    if not pool:
        return None
    f = random.Random(int(t_hit * 100) + seed_tweak).choice(pool)
    return LayerSpec(
        id=f"bfx_{category}_{int(t_hit*10)}", type="footage", name=f"BFX_{category}",
        z_index=z,
        time_range=[max(0.0, t_hit - 0.05), t_hit + dur],
        content={
            "path": f, "fit": "cover",           # 全屏 cover (不是 contain)
            "matting_mode": "rgba",              # 透明 PNG 按 alpha 叠加
            "opacity": 92,
            "edit_fx": {"punch": {"amount": 20, "times": [max(0.0, t_hit - 0.05)]}},
        },
    )


def seq_layers(t0: float, n: int = 8, per: float = 0.1, z: int = 8):
    """序列帧连播: 连续 png 每张 per 秒快切 (手动动画序列)。"""
    from core.composition_tree import LayerSpec
    seqs = sorted([f for f in SEQ_DIR.glob("B_*.png")])[:n]
    layers = []
    for i, f in enumerate(seqs):
        layers.append(LayerSpec(
            id=f"seq_{i}", type="footage", name=f"SEQ{i}", z_index=z,
            time_range=[t0 + i * per, t0 + (i + 1) * per],
            content={"path": str(f), "fit": "cover", "matting_mode": "rgba",
                     "opacity": 95},
        ))
    return layers


def build_tree():
    from core.composition_tree import LayerSpec, CompositionTree, EffectRef
    FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
    beats = [
        {"time": 0.8, "beat_type": "kick"},
        {"time": 1.6, "beat_type": "snare"},
        {"time": 2.4, "beat_type": "kick"},
        {"time": 3.2, "beat_type": "drop"},
        {"time": 4.0, "beat_type": "snare"},
        {"time": 4.8, "beat_type": "kick"},
        {"time": 5.6, "beat_type": "glitch"},
        {"time": 6.4, "beat_type": "kick"},
        {"time": 7.2, "beat_type": "snare"},
    ]
    layers = [
        LayerSpec(id="clip", type="footage", name="FATE", z_index=0,
                  time_range=[0, DUR],
                  content={"path": str(PROJECT / FOOTAGE), "matting_mode": "rgba",
                           "fit": "cover", "source_dur": 16.37,
                           "edit_fx": {"punch": {"amount": 12}, "shake": {"amp": 16}}}),
        LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                  time_range=[0, DUR],
                  content={"template": "spark", "t_hit": 2.4,
                           "psize_scale": 1.2, "_glow_mult": 1.5}),
        LayerSpec(id="title", type="text", name="Title", z_index=2,
                  time_range=[0.3, DUR - 0.3],
                  content={"text": "FULL POWER", "size": 200,
                           "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                           "font": "auto",
                           "edit_fx": {"punch": {"amount": 14},
                                       "rgb_burst": {"max_amount": 12}}},
                  effects=[EffectRef("match", "ADBE Glo2", {"radius": 30, "intensity": 1.6})]),
    ]
    # 资源全开①: 每拍全屏贴图 (kick→slash/burst, snare→streak/splash, drop→magic_circle, glitch→pattern)
    cat_map = {"kick": ["slash", "burst"], "snare": ["streak", "splash"],
               "drop": ["magic_circle"], "glitch": ["pattern", "smoke"]}
    import random
    rng = random.Random(7)
    z = 3
    for ev in beats:
        cat = rng.choice(cat_map.get(ev["beat_type"], ["sparkle"]))
        ly = big_fx_layer(cat, ev["time"], dur=1.2, z=z)
        if ly:
            layers.append(ly)
            z += 1
    # 资源全开②: 序列帧连播 (5.6-6.4s 故障段)
    layers.extend(seq_layers(5.6, n=8, per=0.1, z=8))
    layers.append(LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                            time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 9}))
    return CompositionTree(
        comp_name="Resource_Showcase", style_card="edit", duration=DUR,
        layers=layers, beat_events=beats)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ① 渲染 base (无 LUT, 贴图全开)
    tree = build_tree()
    n_fx = sum(1 for l in tree.layers if l.id.startswith(("bfx_", "seq_")))
    print(f"[1/4] 渲染资源全开 base ({len(tree.layers)} 层, 贴图层 {n_fx})...")
    base = OUT_DIR / "base.mp4"
    if not render_tree(tree, str(base), "showcase.aep"):
        print("渲染失败")
        return 1
    print(f"  完成 ({time.time()-t0:.0f}s)")

    # ② SFX 全拍混音
    print("[2/4] SFX 全拍混音...")
    sfx = plan_sfx(tree.beat_events, seed=99)
    v1 = OUT_DIR / "showcase_noLUT.mp4"
    mix_sfx(str(base), str(v1), sfx)

    # ③ LUT 四联 A/B: 无 | 好莱坞 | 复古电影 | 夏日
    print("[3/4] LUT 四联对比...")
    pools = load_sampling()
    luts = [
        ("none", None, 0),
        ("hollywood", pools.get("好莱坞 _ Hollywood", [None])[0], 0.9),
        ("vintage", pools.get("复古电影 _ Vintage Film", [None])[0], 0.9),
        ("summer", pools.get("夏日光辉 _ Summer Glow", [None])[0], 0.9),
    ]
    segs = []
    for name, cube, s in luts:
        seg = OUT_DIR / f"seg_{name}.mp4"
        if cube:
            ok = transcode_with_lut(str(v1), str(seg), cube, s)
        else:
            ok = transcode_with_lut(str(v1), str(seg), "", 0.0) if False else _copy(str(v1), str(seg))
        segs.append(seg)
        print(f"  {name}: {'OK' if ok else 'FAIL'}")

    # 拼接四联
    concat = OUT_DIR / "list.txt"
    concat.write_text("\n".join(f"file '{s}'" for s in segs), encoding="utf-8")
    import subprocess
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                        "-c", "copy", str(OUT_DIR / "lut_ab.mp4")], capture_output=True, timeout=300)
    print(f"  LUT A/B: {'OK' if r.returncode == 0 else 'FAIL'}")

    # ④ 主成片: 好莱坞 0.85
    print("[4/4] 主成片 (好莱坞 0.85)...")
    main_v = OUT_DIR / "showcase.mp4"
    hol = pools.get("好莱坞 _ Hollywood", [None])[0]
    transcode_with_lut(str(v1), str(main_v), hol, 0.85)
    print(f"\n交付: {main_v} | LUT对比: {OUT_DIR / 'lut_ab.mp4'} ({time.time()-t0:.0f}s)")
    return 0


def _copy(src, dst):
    import shutil
    shutil.copy(src, dst)
    return True


if __name__ == "__main__":
    sys.exit(main())
