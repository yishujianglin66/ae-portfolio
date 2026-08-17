"""multishot_replica.py — 真剪辑复刻（多镜头切换版）

直面诚实差距第一因: 单镜头 0 场景切换 vs 参考 0.6/s。
本片: 8 个镜头 × 5 个不同素材, 节拍硬切 (1.5 切/s 画像), 每镜头独立
变速+推拉, 叠画像贴图/LUT/SFX。这是"复刻片"到"剪辑片"的第一步。

用法:
  python scripts/multishot_replica.py [--tag cut]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from scripts.m2_auto_iterate import render_tree  # noqa: E402
from core.image_fx import pick_fx_layer  # noqa: E402
from core.sfx_layer import plan_sfx, mix_sfx, _load_index  # noqa: E402
from core.lut_pipeline import load_sampling, transcode_with_lut  # noqa: E402
from core.cnn_scorer import score_video_mode  # noqa: E402
import cv2  # noqa: E402

DUR = 8.0
USE_RAMPS = True    # 2026-08-17: speed_ramp_jsx 已修复错峰层（offset/source_in 参数）, 可以安全开启
SMART_IN_CACHE: dict = {}
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]

# 素材池 (互不相同的番剧/风格, 保证场景切换可见)
SOURCES = [
    "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4",
    "data/real_amv_test/BV16J411Q7sP_裸眼3D终结之谷 佐鸣大战.mp4",
    "data/real_amv_test/BV1D4411k7UE_海贼王极致踩点燃爆点燃你的腺上激素爽就完事了.mp4",
    "data/real_amv_test/BV1Am4y1J7PF_时光代理人2插曲Flash无损完整版配上原片简直不要太.mp4",
    "data/real_amv_test/BV17G3w6AE9H_𝘿𝙞𝙚 𝙁𝙤𝙧 𝙔𝙖𝙣.mp4",
]


def probe_dur(p: str) -> float:
    cap = cv2.VideoCapture(str(PROJECT / p))
    d = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    cap.release()
    return d


def smart_in(src_rel: str, need: float, k: int = 6) -> float:
    """镜头选择: 探测 k 个候选入点, 选 (饱和度×边缘) 画面能量最高者。"""
    cap = cv2.VideoCapture(str(PROJECT / src_rel))
    sd = cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1)
    cap.release()
    hi = max(1.0, sd - need - 0.3)
    best, best_s = 1.0, -1.0
    for c in range(k):
        t_in = 1.0 + (hi - 1.0) * c / max(k - 1, 1)
        cap = cv2.VideoCapture(str(PROJECT / src_rel))
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t_in * cap.get(cv2.CAP_PROP_FPS)))
        ret, f = cap.read()
        cap.release()
        if not ret:
            continue
        small = cv2.resize(f, (160, 90))
        sat = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[:, :, 1].mean()
        edge = cv2.Canny(small, 60, 160).mean()
        score = sat / 255 * edge
        if score > best_s:
            best, best_s = t_in, score
    return round(best, 2)


def build_tree(pp: dict):
    from core.composition_tree import LayerSpec, CompositionTree, EffectRef
    rng = random.Random(42)

    # 节拍: 1.5 切/s 画像 → 8s ≈ 12 拍, 8 镜头
    n_shots = 8
    shot_dur = DUR / n_shots
    beats = []
    for i in range(n_shots):
        beats.append({"time": round(i * shot_dur, 2),
                      "beat_type": "kick" if i % 2 == 0 else "snare",
                      "layer_id": f"shot{i}"})

    layers = []
    for i in range(n_shots):
        src = SOURCES[i % len(SOURCES)]
        sd = probe_dur(src)
        t0 = i * shot_dur
        # 每镜头独立变速曲线 (快慢交替: 偶数镜慢起快收, 奇数镜快)
        # ramps.t 用层局部时间 (0 ~ shot_dur), 与 speed_ramp_jsx 约定一致,
        # 避免 startTime 前移（错峰层）时变速曲线错位 — 2026-08-17 修复。
        if i % 2 == 0:
            ramps = [{"t": 0.0, "v": 1.0}, {"t": shot_dur * 0.5, "v": 0.3},
                     {"t": shot_dur * 0.7, "v": 0.3}, {"t": shot_dur * 0.8, "v": 2.2},
                     {"t": shot_dur, "v": 1.6}]
        else:
            ramps = [{"t": 0.0, "v": 1.6}, {"t": shot_dur * 0.6, "v": 1.6},
                     {"t": shot_dur * 0.65, "v": 0.4}, {"t": shot_dur, "v": 1.0}]
        # 入点随机 (场景多样性)
        in_s = SMART_IN_CACHE.setdefault(src, smart_in(src, shot_dur * 2.0))
        layers.append(LayerSpec(
            id=f"shot{i}", type="footage", name=f"S{i}", z_index=i,   # 唯一 z → 唯一 JSX 变量
            time_range=[t0, t0 + shot_dur + 0.05],   # 微重叠 → 硬切不露底
            content={"path": str(PROJECT / src), "matting_mode": "rgba",
                     "fit": "cover", "source_dur": sd,
                     "source_in": round(in_s, 2),     # builder 已支持 (2026-08-17)
                     **({"speed_ramps": ramps} if USE_RAMPS else {}),
                     "edit_fx": {"punch": {"amount": pp["punch_amount"] + (2 if i % 4 == 0 else 0),
                                           "times": [t0]},
                                 "shake": {"amp": pp["shake_amp"] if i % 2 else pp["shake_amp"] * 0.6,
                                           "freq": pp["shake_freq"]}}}))
    # 文字 (画像 preset)
    layers.append(LayerSpec(
        id="title", type="text", name="Title", z_index=20,
        time_range=[0.2, DUR - 0.2],
        content={"text": "CUT FLOW", "size": pp["text_size"],
                 "colors": {"main": "#FFFFFF", "glow": "#FFD9A0", "accent": "#FFF"},
                 "font": "auto",
                 "char_anim": {"preset": pp["text_preset"], "duration_ms": 420, "tracking": 20},
                 "edit_fx": {"punch": {"amount": pp["punch_amount"] + 4},
                             "rgb_burst": {"max_amount": pp["chromatic_amount"]}}},
        effects=[EffectRef("match", "ADBE Glo2", {"radius": 30, "intensity": pp["glow_intensity"]})]))
    # 贴图: 每画像类别抽 2 层挂强拍
    z = 21
    for cat in pp["fx_categories"][:2]:
        for b in [beats[0], beats[4]]:
            ly = pick_fx_layer(cat, t_hit=b["time"], seed=z * 13)
            if ly is not None:
                ly.id = f"fx_{cat}_{z}"          # 唯一 id (同类多张不撞名)
                ly.content["fit"] = "cover"
                ly.content["opacity"] = 88
                ly.z_index = z
                layers.append(ly)
                z += 1
    layers.append(LayerSpec(id="grain", type="adjustment", name="Grain", z_index=30,
                            time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": 10}))
    return CompositionTree(comp_name="CutFlow", style_card="edit", duration=DUR,
                           layers=layers, beat_events=beats), beats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="cut")
    ap.add_argument("--profile", default="", help="画像 json 路径 (默认 output/replicate_mermaid/compare.json)")
    args = ap.parse_args()
    out = PROJECT / "output" / f"multishot_{args.tag}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # 画像闭环: 默认复用 mermaid 画像, 可通过 --profile 指定任意画像 (含本脚本自生成)
    if args.profile:
        cmp_path = Path(args.profile)
    else:
        cmp_path = PROJECT / "output" / "replicate_mermaid" / "compare.json"
    if not cmp_path.exists():
        print(f"[FAIL] 画像文件缺失: {cmp_path}")
        print("       请先跑: py -3.12 scripts/replicate_ref.py --ref data/参考片 --out replicate_mermaid")
        print("       或带 --profile=<compare.json> 指定画像")
        return 2
    cmp_ = json.loads(cmp_path.read_text(encoding="utf-8"))
    pp = cmp_["params"]

    tree, beats = build_tree(pp)
    n_shots = sum(1 for l in tree.layers if l.id.startswith("shot"))
    pools = load_sampling()
    cube = pools.get(pp["lut_theme"], [None])[0]
    print(f"[1/3] 渲染多镜头 ({n_shots} 镜头 {len(beats)} 拍, LUT {pp['lut_theme']}@{pp['lut_strength']})")
    base = out / "base.mp4"
    if not render_tree(tree, str(base), "cutflow.aep",
                       lut={"cube": cube, "strength": pp["lut_strength"]}):
        print("渲染失败")
        return 1
    print(f"  完成 ({time.time()-t0:.0f}s)")

    print("[2/3] SFX...")
    sfx = plan_sfx(beats, seed=7, pools_override=_load_index())
    final = out / "cutflow.mp4"
    mix_sfx(str(base), str(final), sfx)

    print("[3/3] 客观自检 (切点/场景) + 评分...")
    cap = cv2.VideoCapture(str(final))
    diffs, hists, prev, hprev, frames = [], [], None, None, []
    while True:
        ret, f = cap.read()
        if not ret:
            break
        small = cv2.resize(f, (160, 90))
        g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        h = cv2.normalize(cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3).flatten(), None)
        if prev is not None:
            diffs.append(abs(g.astype(int).__sub__(prev)).mean())
            hists.append(cv2.compareHist(hprev, h, cv2.HISTCMP_BHATTACHARYYA))
        prev, hprev = g, h
        frames.append(small)
    cap.release()
    import numpy as np
    diffs, hists = np.array(diffs), np.array(hists)
    scene_cuts = int((hists > 0.5).sum())
    print(f"  场景切换: {scene_cuts} 个 = {scene_cuts/ (len(frames)/30):.1f}/s (上一版 0.0/s, 参考 0.6/s)")
    print(f"  运动能量 std: {diffs.std():.2f} (上一版 3.77, 参考 13.80)")

    s = score_video_mode(str(final), "local")
    sc = {d: s["scores"].get(d, 0) for d in DIMS}
    ref = cmp_["ref_scores"]
    print(f"\n{'维度':<16}{'参考':>7}{'多镜头版':>8}{'上一版':>8}")
    prev_sc = cmp_["replica_scores"]
    for d in DIMS:
        print(f"{d.replace('score_', ''):<16}{ref[d]:>7.2f}{sc[d]:>8.2f}{prev_sc[d]:>8.2f}")

    # 并排对比图 (参考 vs 单镜头旧版 vs 多镜头新版)
    refcap = cv2.VideoCapture(cmp_["reference"])
    rf = []
    while True:
        ret, f = refcap.read()
        if not ret:
            break
        rf.append(cv2.resize(f, (160, 90)))
    refcap.release()
    oldcap = cv2.VideoCapture(str(PROJECT / "output/replicate_mermaid/replica.mp4"))
    of = []
    while True:
        ret, f = oldcap.read()
        if not ret:
            break
        of.append(cv2.resize(f, (160, 90)))
    oldcap.release()
    def row(fs, n=5):
        idxs = [int(i * (len(fs) - 1) / max(n - 1, 1)) for i in range(n)]
        return np.hstack([fs[i] for i in idxs])
    grid = np.vstack([row(rf), row(of), row(frames)])
    grid = np.kron(grid, np.ones((4, 4, 1), np.uint8))
    cv2.imwrite(str(out / "grid_3row.jpg"), grid)
    (out / "report.json").write_text(json.dumps(
        {"video": str(final), "scene_cuts_per_s": round(scene_cuts / (len(frames) / 30), 2),
         "motion_std": round(float(diffs.std()), 2), "scores": sc, "params": pp},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n交付: {final} | 三排对比图: {out / 'grid_3row.jpg'} ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
