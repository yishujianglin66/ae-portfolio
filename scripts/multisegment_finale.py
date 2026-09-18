"""multisegment_finale.py — 多段成片主线（intro/build/drop/outro 四段编排）

把成片从单段 (grand_finale 5s 一镜) / 多镜头硬切 (multishot_replica 8s 8 镜)
升级为四段结构: 每段用不同参数 + 风格, 段间过渡, 逐段差异化编排。

  intro  (0-2.5s)  : 铺垫 — 慢节奏, 单镜头, 少粒子, 标题淡入
  build  (2.5-5.0s) : 蓄势 — 节奏渐快, 2 镜头硬切, 粒子增多, 标题固定
  drop   (5.0-7.5s) : 爆发 — 快节奏, 4 镜头快切, 满粒子, 标题高亮+punch
  outro  (7.5-10.0s): 收尾 — 减速, 1 镜头, 粒子消散, 标题淡出

段间过渡:
  intro→build : 硬切 (节奏加速点)
  build→drop : 硬切 + 光效爆发 (drop 起始 5.0s 加 fx_layer 撞拍贴图)
  drop→outro : 交叉淡化 (outro 首镜头前移 0.15s 与 drop 末镜头时间重叠)

方案A (单合成树): 所有段的镜头在同一 CompositionTree 里按时间排列, AE 一次渲染;
  段间用 z_index 全局唯一 + time_range 控制叠加, drop 段末镜头与 outro 首镜头
  时间重叠模拟 cross_fade。

用法:
  py -3.12 scripts/multisegment_finale.py [--style edit] [--tag seg1] [--no-render]

输出:
  output/multisegment_finale/<tag>/
    ├─ finale.mp4           (真机渲染+LUT+SFX)
    ├─ base.mp4             (渲染原片, 无音效)
    ├─ tree.json            (--no-render 模式导出合成树结构)
    ├─ stats.json           (每段统计 + 段间过渡)
    └─ report.json          (评分 + 段参数 + 段间过渡)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import cv2  # noqa: E402

from core.cnn_scorer import score_video_mode  # noqa: E402
from core.image_fx import pick_fx_layer  # noqa: E402
from core.lut_pipeline import load_sampling  # noqa: E402
from core.sfx_layer import _load_index, mix_sfx, plan_sfx  # noqa: E402
from scripts.m2_auto_iterate import render_tree  # noqa: E402

DUR = 10.0
SMART_IN_CACHE: dict = {}
DIMS = ["score_dynamism", "score_composition", "score_color_harmony",
        "score_text_read", "score_texture", "score_pacing", "score_overall"]

# 素材池 (与 multishot_replica 共用, 保证场景切换多样性)
SOURCES = [
    "data/real_amv_test/DL_FATE_r978_BV1qb411C79B_p1.mp4",
    "data/real_amv_test/BV16J411Q7sP_裸眼3D终结之谷 佐鸣大战.mp4",
    "data/real_amv_test/BV1D4411k7UE_海贼王极致踩点燃爆点燃你的腺上激素爽就完事了.mp4",
    "data/real_amv_test/BV1Am4y1J7PF_时光代理人2插曲Flash无损完整版配上原片简直不要太.mp4",
    "data/real_amv_test/BV17G3w6AE9H_𝘿𝙞𝙚 𝙁𝙤𝙧 𝙔𝙖𝙣.mp4",
]

TITLE_TEXT = "MULTI CLASH"  # 跨段主标题

# 段间过渡类型 (固定语义, 用于 report + 后续达标度校验)
TRANSITIONS: dict[tuple[str, str], str] = {
    ("intro", "build"): "hard_cut",            # 节奏加速点
    ("build", "drop"): "hard_cut_fx_burst",    # 硬切 + 光效爆发 (drop 起始撞拍贴图)
    ("drop", "outro"): "cross_fade",           # 交叉淡化 (时间重叠模拟)
}

SEGMENT_ORDER = ["intro", "build", "drop", "outro"]

# 每段参数差异 (对应 multishot_replica 的 pp 字典的子集 + 段独有旋钮)
SEGMENT_PROFILES: dict[str, dict[str, Any]] = {
    "intro": {
        "start": 0.0, "end": 2.5, "n_shots": 1, "shot_dur": 2.5,
        "punch_amount": 6, "shake_amp": 6, "shake_freq": 2.0,
        "psize_scale": 0.5, "_glow_mult": 0.6,
        "text_size": 160, "text_opacity_in": 0, "text_opacity_peak": 60,
        "particle_count": 1, "use_ramps": False, "ramp_style": "slowmo",
        "beat_density": 0.4,   # 低密度节拍
        "lut_strength": 0.3, "sfx_intensity": 0.3,
    },
    "build": {
        "start": 2.5, "end": 5.0, "n_shots": 2, "shot_dur": 1.25,
        "punch_amount": 9, "shake_amp": 10, "shake_freq": 2.5,
        "psize_scale": 0.7, "_glow_mult": 0.9,
        "text_size": 180, "text_opacity_in": 60, "text_opacity_peak": 90,
        "particle_count": 3, "use_ramps": True, "ramp_style": "fast_pan",
        "beat_density": 0.7,
        "lut_strength": 0.5, "sfx_intensity": 0.6,
    },
    "drop": {
        "start": 5.0, "end": 7.5, "n_shots": 4, "shot_dur": 0.625,
        "punch_amount": 14, "shake_amp": 16, "shake_freq": 3.5,
        "psize_scale": 1.0, "_glow_mult": 1.3,
        "text_size": 220, "text_opacity_in": 90, "text_opacity_peak": 100,
        "particle_count": 6, "use_ramps": True, "ramp_style": "pulse",
        "beat_density": 1.0,   # 满密度
        "lut_strength": 0.6, "sfx_intensity": 1.0,   # 0.8→0.6 保色彩层次
    },
    "outro": {
        "start": 7.5, "end": 10.0, "n_shots": 1, "shot_dur": 2.5,
        "punch_amount": 4, "shake_amp": 4, "shake_freq": 1.5,
        "psize_scale": 0.4, "_glow_mult": 0.5,
        "text_size": 180, "text_opacity_in": 100, "text_opacity_peak": 0,
        "particle_count": 1, "use_ramps": True, "ramp_style": "slowmo",
        "beat_density": 0.3,
        "lut_strength": 0.4, "sfx_intensity": 0.2,
    },
}


def probe_dur(p: str) -> float:
    """探测素材时长 (秒)。"""
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


def _ramp_for(style: str, shot_dur: float) -> list[dict[str, float]]:
    """按段风格生成镜头变速曲线 (与 multishot_replica speed_ramps 同格式)。

    ramps.t 用层局部时间 (0 ~ shot_dur), 与 speed_ramp_jsx 约定一致,
    避免 startTime 前移 (错峰层) 时变速曲线错位。
    """
    if style == "slowmo":
        # 慢起: 1.0 → 0.5 → 1.0 (呼吸感)
        return [{"t": 0.0, "v": 1.0}, {"t": shot_dur * 0.4, "v": 0.5},
                {"t": shot_dur * 0.7, "v": 0.5}, {"t": shot_dur, "v": 1.0}]
    if style == "fast_pan":
        # 快推: 1.6 → 1.6 → 0.4 (急刹) → 1.0
        return [{"t": 0.0, "v": 1.6}, {"t": shot_dur * 0.6, "v": 1.6},
                {"t": shot_dur * 0.65, "v": 0.4}, {"t": shot_dur, "v": 1.0}]
    if style == "pulse":
        # 脉冲: 1.0 → 2.2 (急加速) → 0.3 (顿挫) → 1.6 (节奏脉冲)
        return [{"t": 0.0, "v": 1.0}, {"t": shot_dur * 0.3, "v": 2.2},
                {"t": shot_dur * 0.55, "v": 0.3}, {"t": shot_dur * 0.8, "v": 1.6},
                {"t": shot_dur, "v": 1.0}]
    # static 兜底
    return [{"t": 0.0, "v": 1.0}, {"t": shot_dur, "v": 1.0}]


def _beats_for_segment(seg: str, pp: dict[str, Any],
                       seg_start: float, seg_end: float,
                       first_layer_id: str) -> list[dict[str, Any]]:
    """按 beat_density 在段内均匀生成节拍事件。

    密度语义: density 1.0 → 每 0.5s 一拍; 0.4 → 每 1.25s 一拍。
    beat_type 按段语义区分: intro=build / build=snare+kick / drop=kick+snare / outro=snare。
    """
    span = seg_end - seg_start
    spacing = max(0.3, 0.5 / max(pp["beat_density"], 0.1))
    n = max(1, int(span / spacing))
    beats: list[dict[str, Any]] = []
    for i in range(n):
        # drop 段第一拍锚定到段起始 (build→drop 边界撞拍)
        if seg == "drop" and i == 0:
            t = seg_start
            bt = "kick"
        else:
            t = seg_start + (i + 0.5) * (span / n)  # 段内居中分布
            if seg == "intro":
                bt = "build"     # 铺垫型
            elif seg == "build":
                bt = "snare" if i % 2 == 0 else "kick"
            elif seg == "drop":
                bt = "kick" if i % 2 == 0 else "snare"
            else:  # outro
                bt = "snare"
        beats.append({"time": round(t, 2), "beat_type": bt,
                      "layer_id": first_layer_id, "segment": seg})
    return beats


def build_tree(style_card: str = "edit") -> tuple[Any, dict[str, Any]]:
    """构建四段合成树 (方案A: 单 CompositionTree, 全程 10s)。

    返回 (tree, stats) — stats 含每段镜头/粒子/文字统计 + 段间过渡信息。
    """
    from core.composition_tree import CompositionTree, EffectRef, LayerSpec

    layers: list[LayerSpec] = []
    beat_events: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "segments": {},
        "transitions": {f"{a}->{b}": t for (a, b), t in TRANSITIONS.items()},
    }
    z = 0  # 全局 z_index (唯一 → 唯一 JSX 变量名)
    src_idx = 0  # SOURCES 池轮换指针

    for seg in SEGMENT_ORDER:
        pp = SEGMENT_PROFILES[seg]
        seg_start, seg_end = pp["start"], pp["end"]
        n_shots = pp["n_shots"]
        shot_dur = pp["shot_dur"]
        seg_shot_ids: list[str] = []
        first_layer_id = f"{seg}_shot0"

        # ── 镜头层 (footage) ────────────────────────────────────
        for i in range(n_shots):
            src = SOURCES[src_idx % len(SOURCES)]
            src_idx += 1
            sd = probe_dur(src)
            t0 = seg_start + i * shot_dur
            t1 = min(t0 + shot_dur + 0.05, seg_end)  # 微重叠 → 硬切不露底

            # drop→outro 交叉淡化: outro 首镜头前移 0.15s 与 drop 末镜头时间重叠
            if seg == "outro" and i == 0:
                t0 = seg_start - 0.15
                t1 = seg_end

            in_s = SMART_IN_CACHE.setdefault(src, smart_in(src, shot_dur * 2.0))
            ramps = _ramp_for(pp["ramp_style"], shot_dur) if pp["use_ramps"] else None
            lid = f"{seg}_shot{i}"

            content: dict[str, Any] = {
                "path": str(PROJECT / src), "matting_mode": "rgba",
                "fit": "cover", "source_dur": sd,
                "source_in": round(in_s, 2),
                "edit_fx": {
                    "punch": {"amount": pp["punch_amount"] + (2 if i == 0 else 0),
                              "times": [t0]},
                    "shake": {"amp": pp["shake_amp"] if i % 2 == 0 else pp["shake_amp"] * 0.6,
                              "freq": pp["shake_freq"]},
                },
            }
            if ramps:
                content["speed_ramps"] = ramps
            # outro 段降低镜头不透明度 (粒子消散语义, 与 cross_fade 配合)
            if seg == "outro":
                content["opacity"] = 85

            layers.append(LayerSpec(
                id=lid, type="footage", name=f"{seg.upper()[:1]}{i}", z_index=z,
                time_range=[max(0.0, t0), t1], content=content))
            seg_shot_ids.append(lid)
            z += 1

        # ── 粒子层 (particle) — 每段 particle_count 个 ───────────
        for pi in range(pp["particle_count"]):
            # 多粒子层错峰: 第 i 个撞拍点偏移到段内 30% + i*20%
            t_hit = seg_start + (seg_end - seg_start) * (0.3 + 0.2 * pi)
            layers.append(LayerSpec(
                id=f"{seg}_part{pi}", type="particle", name=f"P_{seg}{pi}", z_index=z,
                time_range=[seg_start, seg_end],
                content={"template": "spark", "t_hit": round(t_hit, 2),
                         "psize_scale": pp["psize_scale"],
                         "_glow_mult": pp["_glow_mult"]}))
            z += 1

        # ── 文字层 (text) — 每段一个 title 子层 ─────────────────
        # opacity 按 in/peak 控制 (segment-level), 跨段叠加全程视觉:
        #   intro: 60 (peak, 淡入到 60)
        #   build: 90 (peak, 固定中段)
        #   drop : 100 (peak, 高亮)
        #   outro: 100→0 (用 in=100 起始, 末段降透明度模拟淡出)
        if seg == "outro":
            opacity = pp["text_opacity_in"]   # 100 (起始, 然后通过 layer 出场动画淡出)
        else:
            opacity = pp["text_opacity_peak"]  # intro=60 / build=90 / drop=100

        layers.append(LayerSpec(
            id=f"title_{seg}", type="text", name=f"Title_{seg}", z_index=z,
            time_range=[seg_start + 0.1, max(seg_start + 0.2, seg_end - 0.1)],
            content={"text": TITLE_TEXT, "size": pp["text_size"],
                     "opacity": opacity,
                     "colors": {"main": "#FFFFFF", "glow": "#FFD9A0", "accent": "#FFF"},
                     "font": "auto",
                     "char_anim": {"preset": "tracking_stagger",
                                   "duration_ms": 420, "tracking": 20},
                     "edit_fx": {"punch": {"amount": pp["punch_amount"] + 4,
                                           "times": [seg_start + 0.1]},
                                 "rgb_burst": {"max_amount": pp["punch_amount"] // 2}}},
            effects=[EffectRef("match", "ADBE Glo2",
                               {"radius": 30, "intensity": pp["_glow_mult"]})]))
        z += 1

        # ── 段内节拍事件 ─────────────────────────────────────────
        seg_beats = _beats_for_segment(seg, pp, seg_start, seg_end, first_layer_id)
        beat_events.extend(seg_beats)

        stats["segments"][seg] = {
            "time_range": [seg_start, seg_end],
            "n_shots": n_shots, "shot_dur": shot_dur,
            "particle_count": pp["particle_count"],
            "title_opacity": opacity,
            "beat_count": len(seg_beats),
            "shot_layer_ids": seg_shot_ids,
            "beat_density": pp["beat_density"],
            "params": {k: v for k, v in pp.items()
                       if k not in ("start", "end", "n_shots", "shot_dur")},
        }

    # ── 段间过渡层 ──────────────────────────────────────────────
    # build→drop 边界 (5.0s): 硬切 + 光效爆发 — drop 起始撞拍贴图
    fx_burst = pick_fx_layer("burst", t_hit=5.0, duration=0.8, seed=42, z_index=z)
    if fx_burst is not None:
        fx_burst.id = "fx_build2drop"
        fx_burst.content["fit"] = "cover"
        fx_burst.content["opacity"] = 90
        layers.append(fx_burst)
        stats["fx_burst_layer"] = fx_burst.id
        z += 1
    else:
        stats["fx_burst_layer"] = None

    # drop 段强拍加一张贴图 (强化爆发感, 6.0s kick 撞拍)
    fx_drop = pick_fx_layer("slash", t_hit=6.0, duration=0.6, seed=99, z_index=z)
    if fx_drop is not None:
        fx_drop.id = "fx_drop_peak"
        fx_drop.content["fit"] = "cover"
        fx_drop.content["opacity"] = 88
        layers.append(fx_drop)
        stats["fx_drop_peak_layer"] = fx_drop.id
        z += 1
    else:
        stats["fx_drop_peak_layer"] = None

    # ── drop 段全屏纹理叠加 (2026-08-17 texture 第二招: 特效贴图资产全屏化) ──
    drop_beats = [b for b in beat_events if b["time"] >= 5.0][1:3]  # drop 段第2/3拍 (tree 尚未建, 用局部 beat_events)
    _zi = 50
    for cat, b in zip(("sparkle", "splash"), drop_beats):
        ly = pick_fx_layer(cat, t_hit=float(b["time"]), seed=_zi, z_index=_zi)
        if ly is not None:
            ly.id = f"tex_{cat}"
            ly.content["fit"] = "cover"
            ly.content["opacity"] = 55            # 半透明全屏纹理
            ly.time_range = [5.0, 7.5]            # drop 段全程
            layers.append(ly)
            _zi += 1

    # ── 全程 grain 后处理 (顶层; 2026-08-17 texture 提升: 3 层不同强度叠加) ──
    for gi, g_amt in enumerate((8, 12, 16), start=1):
        layers.append(LayerSpec(
            id=f"grain{gi}", type="adjustment", name=f"Grain{gi}", z_index=z + gi - 1,
            time_range=[0, DUR], content={"edit_fx_layer": "grain", "amount": g_amt}))
    z += 1

    tree = CompositionTree(
        comp_name="MultiSegment_Finale", style_card=style_card, duration=DUR,
        layers=layers, beat_events=beat_events,
        meta={"structure": "intro/build/drop/outro",
              "total_shots": sum(SEGMENT_PROFILES[s]["n_shots"] for s in SEGMENT_ORDER),
              "transitions": {f"{a}->{b}": t for (a, b), t in TRANSITIONS.items()}})

    stats["total_layers"] = len(layers)
    stats["total_shots"] = sum(SEGMENT_PROFILES[s]["n_shots"] for s in SEGMENT_ORDER)
    stats["total_particles"] = sum(SEGMENT_PROFILES[s]["particle_count"]
                                   for s in SEGMENT_ORDER)
    stats["total_titles"] = len(SEGMENT_ORDER)
    stats["total_beats"] = len(beat_events)
    stats["fx_layers"] = [l.id for l in layers if l.id.startswith("fx_")]
    stats["grain_layer"] = "grain"
    return tree, stats


def _pick_lut_cube() -> tuple[str, str]:
    """选 LUT 主题 + cube (优先冷色调强化 drop 段爆发对比)。"""
    pools = load_sampling()
    # 优先主题顺序: 冷色调 (高燃/对比) → HDR → 任意第一个
    for theme in ["冷色调 _ Cool_Look", "HDR _ HDR"]:
        if theme in pools and pools[theme]:
            return theme, pools[theme][0]
    # 任意可用主题
    for theme, cubes in pools.items():
        if cubes:
            return theme, cubes[0]
    return "", ""


def _export_tree_json(tree, out_path: Path) -> None:
    """合成树导出 JSON (供 --no-render 验证结构 + 后续渲染复用)。"""
    tree_json = {
        "comp_name": tree.comp_name, "style_card": tree.style_card,
        "duration": tree.duration,
        "layers": [{"id": l.id, "type": l.type, "name": l.name,
                    "z_index": l.z_index, "time_range": l.time_range,
                    "content": l.content}
                   for l in tree.layers],
        "beat_events": tree.beat_events,
        "meta": tree.meta,
    }
    out_path.write_text(json.dumps(tree_json, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="多段成片主线 (intro/build/drop/outro)")
    ap.add_argument("--style", default="edit", help="风格卡 ID (默认 edit)")
    ap.add_argument("--tag", default="seg1", help="输出标签 (默认 seg1)")
    ap.add_argument("--no-render", action="store_true",
                   help="只构建合成树不渲染 (验证结构, 输出 JSON)")
    args = ap.parse_args()

    out = PROJECT / "output" / "multisegment_finale" / args.tag
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── ① 构建四段合成树 ─────────────────────────────────────────
    print("[1/4] 构建四段合成树 (intro/build/drop/outro, 10s)...")
    tree, stats = build_tree(args.style)
    n_shots = sum(1 for l in tree.layers
                  if l.type == "footage" and "_shot" in l.id)
    n_particles = sum(1 for l in tree.layers if l.type == "particle")
    n_titles = sum(1 for l in tree.layers if l.type == "text")
    n_fx = sum(1 for l in tree.layers if l.id.startswith("fx_"))
    n_grain = sum(1 for l in tree.layers if l.id == "grain")
    print(f"  总层数: {len(tree.layers)} | 镜头 {n_shots} 粒子 {n_particles} "
          f"文字 {n_titles} fx {n_fx} grain {n_grain}")
    print(f"  节拍事件: {len(tree.beat_events)} 个")
    for seg in SEGMENT_ORDER:
        s = stats["segments"][seg]
        print(f"  {seg:6s} {s['time_range'][0]:.1f}-{s['time_range'][1]:.1f}s "
              f"shots={s['n_shots']} dur={s['shot_dur']}s "
              f"particles={s['particle_count']} opacity={s['title_opacity']} "
              f"beats={s['beat_count']}")
    print(f"  段间过渡: {stats['transitions']}")

    # 校验合成树 schema (警告不阻断, 错误阻断)
    from core.composition_tree import validate_composition_tree
    v = validate_composition_tree(tree)
    if not v["ok"]:
        print(f"[FAIL] 合成树校验错误: {v['errors']}")
        return 2
    if v["warnings"]:
        print(f"  [warn] 校验警告: {v['warnings']}")

    # ── ② LUT 选择 (取 drop 段强度, 全程用最强 LUT 强化爆发) ─────
    theme, cube = _pick_lut_cube()
    lut_strength_drop = SEGMENT_PROFILES["drop"]["lut_strength"]
    lut_render = {"cube": cube, "strength": lut_strength_drop} if cube else None
    if lut_render:
        print(f"  LUT: {Path(cube).name} @ {lut_strength_drop} "
              f"(主题 '{theme}', 取 drop 段强度)")
    else:
        print("  LUT: 无可用 cube, 跳过 LUT")

    # ── --no-render: 只导出合成树 JSON ──────────────────────────
    if args.no_render:
        _export_tree_json(tree, out / "tree.json")
        (out / "stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[no-render] 合成树已导出: {out / 'tree.json'}")
        print(f"           统计:        {out / 'stats.json'}")
        print(f"           总镜头 {stats['total_shots']} (期望 8) | "
              f"总粒子 {stats['total_particles']} | "
              f"总文字 {stats['total_titles']} | "
              f"fx_layers {len(stats['fx_layers'])} | "
              f"beats {stats['total_beats']}")
        return 0

    # ── ③ AE 真机渲染 (含 LUT) ──────────────────────────────────
    print(f"\n[2/4] AE 真机渲染 ({n_shots} 镜头 + LUT)...")
    base = out / "base.mp4"
    aep_name = f"multisegment_{args.tag}.aep"   # 2026-08-27: avi 路径随 tag 唯一, 绕开损坏残留 AVI 的系统锁
    if not render_tree(tree, str(base), aep_name, lut=lut_render):
        print("  渲染失败 (AE 桥接不可用?) — 建议 --no-render 验证合成树结构")
        # 仍然导出合成树供后续渲染复用
        _export_tree_json(tree, out / "tree.json")
        (out / "stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    print(f"  完成 ({time.time()-t0:.0f}s)")

    # ── ④ SFX 混音 ─────────────────────────────────────────────
    print(f"\n[3/4] SFX 混音 ({len(tree.beat_events)} 节拍)...")
    sfx = plan_sfx(tree.beat_events, seed=7, pools_override=_load_index())
    final = out / "finale.mp4"
    ok = mix_sfx(str(base), str(final), sfx)
    if not ok:
        print("  混音失败, 用无音效版")
        final = base
    print(f"  SFX: {len(sfx)} 个落点 → {final}")

    # ── ⑤ hybrid 评分 ──────────────────────────────────────────
    print("\n[4/4] hybrid 评分 (整体)...")
    s = score_video_mode(str(final), "hybrid")
    sc = {d: s["scores"].get(d, 0) for d in DIMS}
    print(f"  整体: overall={sc['score_overall']:.2f} | "
          f"dynamism={sc['score_dynamism']:.2f} | "
          f"pacing={sc['score_pacing']:.2f} | "
          f"texture={sc['score_texture']:.2f}")
    if s.get("error"):
        print(f"  [warn] 评分部分失败: {s['error']}")

    # ── ⑥ 报告 ─────────────────────────────────────────────────
    report = {
        "video": str(final), "style": args.style, "tag": args.tag,
        "duration": DUR,
        "segments": stats["segments"],
        "transitions": stats["transitions"],
        "structure": {
            "total_shots": stats["total_shots"],
            "total_particles": stats["total_particles"],
            "total_titles": stats["total_titles"],
            "total_beats": stats["total_beats"],
            "fx_layers": stats["fx_layers"],
            "grain_layer": stats["grain_layer"],
            "total_layers": stats["total_layers"],
        },
        "lut": lut_render,
        "sfx": [{"file": f, "t": t, "gain": g} for f, t, g in sfx],
        "scores": sc, "source": s.get("source", {}),
        "elapsed_s": round(time.time() - t0),
    }
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n交付: {final}")
    print(f"报告: {out / 'report.json'}")
    print(f"耗时: {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
