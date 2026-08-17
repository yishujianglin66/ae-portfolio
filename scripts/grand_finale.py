"""grand_finale.py — 端到端大验收成片（LUT + SFX + 贴图 + M2 评分 + 标尺对照）

一镜到底验收资源接入成果:
  合成树 (素材+粒子+标题+image_fx 贴图撞拍层)
  → render_tree(挂 LUT)
  → mix_sfx (beat 驱动卡点音效)
  → M2 hybrid 评分
  → 与人工作品标尺 (human_benchmark.json) 对照

输出: output/grand_finale/finale.mp4 + report.json

用法:
  python scripts/grand_finale.py [--style cinematic_film]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.m2_auto_iterate import render_tree  # noqa: E402
from core.image_fx import pick_fx_layers  # noqa: E402
from core.sfx_layer import plan_sfx, mix_sfx  # noqa: E402
from core.cnn_scorer import score_video_mode  # noqa: E402
from knowledge.style_card import load_card  # noqa: E402

OUT_DIR = PROJECT / "output" / "grand_finale"
DUR = 5.0
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]


def build_tree():
    from core.composition_tree import LayerSpec, CompositionTree, EffectRef
    FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"
    tree = CompositionTree(
        comp_name="Grand_Finale", style_card="edit", duration=DUR,
        layers=[
            LayerSpec(id="clip", type="footage", name="FATE", z_index=0,
                      time_range=[0, DUR],
                      content={"path": str(PROJECT / FOOTAGE), "matting_mode": "rgba",
                               "fit": "cover", "source_dur": 16.37,
                               "edit_fx": {"punch": {"amount": 10}, "shake": {"amp": 14}}}),
            LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                      time_range=[0, DUR],
                      content={"template": "spark", "t_hit": 2.5,
                               "psize_scale": 0.8, "_glow_mult": 1.2}),
            LayerSpec(id="title", type="text", name="Title", z_index=2,
                      time_range=[0.4, DUR - 0.4],
                      content={"text": "CLASH", "size": 190,
                               "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                               "font": "auto",
                               "edit_fx": {"punch": {"amount": 12},
                                           "rgb_burst": {"max_amount": 10}}},
                      effects=[EffectRef("match", "ADBE Glo2", {"radius": 26, "intensity": 1.4})]),
            LayerSpec(id="grain", type="adjustment", name="GrainPost", z_index=9,
                      time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 9}),
        ],
        beat_events=[{"time": 2.5, "beat_type": "kick", "layer_id": "title"},
                     {"time": 1.5, "beat_type": "snare", "layer_id": "title"},
                     {"time": 3.5, "beat_type": "drop", "layer_id": "title"}],
    )
    # 资产接入①: 特效贴图撞拍层 (kick→刀光/爆开, drop→魔法阵)
    fx_layers = pick_fx_layers(tree.beat_events, seed=7, max_layers=3)
    tree.layers.extend(fx_layers)
    return tree


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", default="cinematic_film")
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    card = load_card(args.style)
    lut_cfg = getattr(card, "lut", None) or {}
    print(f"风格卡: {args.style} | LUT: {lut_cfg.get('theme', '无')} @ {lut_cfg.get('strength', 0)}")

    # ① LUT 选择 (风格卡主题 → 采样池第一个)
    from core.lut_pipeline import load_sampling, lut_md5
    lut_render = None
    theme = lut_cfg.get("theme")
    if theme:
        pool = load_sampling().get(theme, [])
        if pool:
            lut_render = {"cube": pool[0], "strength": float(lut_cfg.get("strength", 0.7))}
            print(f"LUT 资产: {Path(pool[0]).name} (md5 {lut_md5(pool[0])[:8]})")

    # ② 渲染 (含贴图层 + LUT)
    t0 = time.time()
    tree = build_tree()
    base_mp4 = OUT_DIR / "finale_base.mp4"
    print(f"\n[1/3] 渲染合成 ({len(tree.layers)} 层, 含 {sum(1 for l in tree.layers if l.type == 'footage' and l.id.startswith('fx_'))} 贴图层)...")
    if not render_tree(tree, str(base_mp4), "grand_finale.aep", lut=lut_render):
        print("渲染失败")
        return 1
    print(f"  渲染+LUT 完成 ({time.time() - t0:.0f}s)")

    # ③ SFX 混音
    print("[2/3] SFX 混音...")
    sfx = plan_sfx(tree.beat_events, seed=42)
    finale = OUT_DIR / "finale.mp4"
    ok = mix_sfx(str(base_mp4), str(finale), sfx)
    if not ok:
        print("混音失败, 用无音效版")
        finale = base_mp4
    print(f"  SFX: {len(sfx)} 个落点")

    # ④ M2 评分 + 标尺对照
    print("[3/3] M2 评分 + 人工作品标尺对照...")
    s = score_video_mode(str(finale), "hybrid")
    ours = {d: s["scores"].get(d, 0) for d in DIMS}

    bench = json.loads((PROJECT / "output" / "m2_iteration" / "human_benchmark.json").read_text(encoding="utf-8"))
    human = bench["human_avg"]

    print(f"\n{'维度':<16}{'本片':>8}{'人工标尺':>10}{'差距':>8}")
    for d in DIMS:
        print(f"{d.replace('score_', ''):<16}{ours[d]:>8.2f}{human[d]:>10.2f}{ours[d] - human[d]:>+8.2f}")

    report = {
        "video": str(finale), "style": args.style, "lut": lut_render,
        "sfx": [{"file": f, "t": t, "gain": g} for f, t, g in sfx],
        "fx_layers": [l.id for l in tree.layers if l.id.startswith("fx_")],
        "scores": ours, "human_avg": human, "source": s.get("source", {}),
        "elapsed_s": round(time.time() - t0),
    }
    (OUT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n验收成片: {finale} | 报告: {OUT_DIR / 'report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
