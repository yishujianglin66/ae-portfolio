"""replicate_reference.py — 参考片逆向复刻端到端（资源库全运用）

给一个顶尖漫剪参考 → qwen 分解技巧画像 → 画像映射管线参数 →
**资源库选资产**（LUT 主题库/贴图 14 类/音效四池/字号）→
新素材上渲染复刻 → M2 评分 → 与参考片自身评分对比。

用法:
  python scripts/replicate_reference.py [--ref <参考.mp4>] [--tag demo]
默认参考: tutorials/独自升级（一般）/成品.mp4 (人工标尺最高分 dyn 8.0)

输出: output/replicate_<tag>/  profile.json + replica.mp4 + compare.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.reference_analyzer import analyze_reference, profile_to_params  # noqa: E402

from core.cnn_scorer import score_video_mode  # noqa: E402
from core.image_fx import pick_fx_layer  # noqa: E402
from core.lut_pipeline import load_sampling, lut_md5  # noqa: E402
from core.sfx_layer import _load_index, mix_sfx, plan_sfx  # noqa: E402
from scripts.m2_auto_iterate import render_tree  # noqa: E402

DEFAULT_REF = Path(r"D:\AE-Work\resources\tutorials\AE教程10集\独自升级（一般）\成品.mp4")
DUR = 6.0
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]


def build_replica_tree(pp: dict):
    """画像参数 + 资源库 → 合成树。"""
    import random

    from core.composition_tree import CompositionTree, EffectRef, LayerSpec
    rng = random.Random(2026)
    FOOTAGE = "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4"

    # 节拍密度跟随 pacing 画像 (cuts_per_sec_feel 0.2-2.0 → 6s 内节拍数)
    n_beats = max(3, min(9, int(pp["cuts_per_sec_feel"] * DUR)))
    beats = []
    for i in range(n_beats):
        t = round(DUR * (i + 0.7) / n_beats, 2)
        bt = "kick" if i % 3 == 0 else ("drop" if i == n_beats - 2 else "snare")
        beats.append({"time": t, "beat_type": bt, "layer_id": "title"})
    kick_times = [b["time"] for b in beats if b["beat_type"] in ("kick", "drop")]

    # 变速画像: speed_ramp → 定格+爆发曲线 (素材 16.37s)
    ramps = None
    if pp["speed_ramps"]:
        ramps = [{"t": 0, "v": 1.0}, {"t": DUR * 0.4, "v": 1.0},
                 {"t": DUR * 0.42, "v": 0.25}, {"t": DUR * 0.55, "v": 0.25},
                 {"t": DUR * 0.58, "v": 2.0}, {"t": DUR * 0.8, "v": 2.0},
                 {"t": DUR * 0.83, "v": 1.0}, {"t": DUR, "v": 1.0}]
    if pp["freeze"]:
        ramps = (ramps or [{"t": 0, "v": 1.0}, {"t": DUR, "v": 1.0}])
        # 定格推近段
        ramps = [{"t": 0, "v": 1.0}, {"t": DUR * 0.5, "v": 1.0},
                 {"t": DUR * 0.52, "v": 0.02}, {"t": DUR * 0.66, "v": 0.02},
                 {"t": DUR * 0.69, "v": 1.8}, {"t": DUR, "v": 1.0}]

    layers = [
        LayerSpec(id="clip", type="footage", name="SRC", z_index=0,
                  time_range=[0, DUR],
                  content={"path": str(PROJECT / FOOTAGE), "matting_mode": "rgba",
                           "fit": "cover", "source_dur": 16.37,
                           **({"speed_ramps": ramps} if ramps else {}),
                           "edit_fx": {"punch": {"amount": pp["punch_amount"],
                                                 **({"times": kick_times} if pp["punch_times_mode"] == "every_beat" else {})},
                                       "shake": {"amp": pp["shake_amp"],
                                                 "freq": pp["shake_freq"]}}}),
        LayerSpec(id="sparks", type="particle", name="Sparks", z_index=1,
                  time_range=[0, DUR],
                  content={"template": "spark", "t_hit": kick_times[0] if kick_times else DUR / 2,
                           "psize_scale": 1.0, "_glow_mult": pp["glow_intensity"]}),
        LayerSpec(id="title", type="text", name="Title", z_index=2,
                  time_range=[0.3, DUR - 0.3],
                  content={"text": "REPLICA", "size": pp["text_size"],
                           "colors": {"main": "#FFFFFF", "glow": "#9FE8FF", "accent": "#FFF"},
                           "font": "auto",
                           "char_anim": {"preset": pp["text_preset"],
                                         "duration_ms": 480, "tracking": 22},
                           "edit_fx": {"punch": {"amount": pp["punch_amount"] + 2},
                                       "rgb_burst": {"max_amount": pp["chromatic_amount"],
                                                     **({"times": kick_times} if pp["punch_times_mode"] == "every_beat" else {})}}},
                  effects=[EffectRef("match", "ADBE Glo2",
                                     {"radius": 28, "intensity": pp["glow_intensity"]})]),
    ]
    # 资源库①: 贴图类别画像 → 节拍撞拍层 (每类抽一张, 挂前几拍)
    z = 3
    fx_used = []
    for cat in pp["fx_categories"]:
        b = beats[min(z - 3, len(beats) - 1)]
        ly = pick_fx_layer(cat, t_hit=b["time"], seed=z * 11)
        if ly is not None:
            ly.content["fit"] = "cover"       # 复刻版全屏化 (资源可见性)
            ly.content["opacity"] = 90
            ly.z_index = z
            layers.append(ly)
            fx_used.append(cat)
            z += 1
    layers.append(LayerSpec(id="grain", type="adjustment", name="Grain", z_index=9,
                            time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 10}))
    tree = CompositionTree(comp_name="Replica", style_card="edit", duration=DUR,
                           layers=layers, beat_events=beats)
    return tree, fx_used


def pick_sfx_pools(prefs: dict) -> dict:
    """SFX 画像偏好 → 过滤后的池。"""
    pools = _load_index()
    out = {}
    if prefs.get("impact"):
        out["impact"] = pools.get("impact", [])
    if prefs.get("whoosh"):
        out["whoosh"] = pools.get("whoosh", [])
    if prefs.get("riser"):
        out["riser"] = pools.get("riser", [])
    out.setdefault("whoosh", pools.get("whoosh", []))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=str(DEFAULT_REF))
    ap.add_argument("--tag", default="demo")
    args = ap.parse_args()
    ref = Path(args.ref)
    if not ref.exists():
        print(f"参考片不存在: {ref}")
        return 1
    out_dir = PROJECT / "output" / f"replicate_{args.tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ① 参考片技巧分解
    print(f"[1/5] 逆向分析参考片: {ref.parent.name}")
    profile = analyze_reference(str(ref))
    if profile.get("error"):
        print(f"分析失败: {profile['error']}")
        return 1
    (out_dir / "profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print("  画像:", json.dumps({k: profile.get(k) for k in
          ("shake", "zoom_punch", "color", "pacing", "signature")}, ensure_ascii=False)[:400])

    # ② 画像 → 参数
    pp = profile_to_params(profile)
    print(f"\n[2/5] 参数映射: punch={pp['punch_amount']} shake={pp['shake_amp']}@{pp['shake_freq']}Hz "
          f"chroma={pp['chromatic_amount']} LUT={pp['lut_theme']}@{pp['lut_strength']} "
          f"text={pp['text_preset']}/{pp['text_size']}px fx={pp['fx_categories']}")

    # ③ 资源库选资产 + 建树渲染
    tree, fx_used = build_replica_tree(pp)
    pools = load_sampling()
    cube = pools.get(pp["lut_theme"], [None])[0]
    lut_render = {"cube": cube, "strength": pp["lut_strength"]} if cube else None
    print(f"\n[3/5] 渲染复刻 ({len(tree.layers)} 层, 贴图 {fx_used}, "
          f"LUT {Path(cube).name if cube else '无'} md5={lut_md5(cube)[:8] if cube else '-'})")
    base = out_dir / "replica_base.mp4"
    if not render_tree(tree, str(base), "replica.aep", lut=lut_render):
        print("渲染失败")
        return 1
    print(f"  渲染完成 ({time.time()-t0:.0f}s)")

    # ④ SFX (画像偏好池)
    print("[4/5] SFX 混音 (画像偏好池)...")
    sfx_pools = pick_sfx_pools(pp["sfx_pools"])
    sfx = plan_sfx(tree.beat_events, seed=2026, pools_override=sfx_pools)
    replica = out_dir / "replica.mp4"
    mix_sfx(str(base), str(replica), sfx)

    # ⑤ 双评分对比 (参考 vs 复刻)
    print("[5/5] 评分对比...")
    ref_s = score_video_mode(str(ref), "local")
    rep_s = score_video_mode(str(replica), "local")
    ref_sc = {d: ref_s["scores"].get(d, 0) for d in DIMS}
    rep_sc = {d: rep_s["scores"].get(d, 0) for d in DIMS}
    print(f"\n{'维度':<16}{'参考片':>8}{'复刻片':>8}{'差':>8}")
    for d in DIMS:
        print(f"{d.replace('score_', ''):<16}{ref_sc[d]:>8.2f}{rep_sc[d]:>8.2f}{rep_sc[d]-ref_sc[d]:>+8.2f}")

    (out_dir / "compare.json").write_text(json.dumps({
        "reference": str(ref), "profile": profile, "params": pp,
        "fx_used": fx_used, "lut": lut_render, "sfx": [{"t": t, "f": Path(f).name, "g": g} for f, t, g in sfx],
        "ref_scores": ref_sc, "replica_scores": rep_sc,
        "video": str(replica), "elapsed_s": round(time.time() - t0),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n交付: {replica} | 画像/对比: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
