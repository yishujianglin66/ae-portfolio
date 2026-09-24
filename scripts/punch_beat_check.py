"""punch_beat_check.py — 运镜撞击的踩点体检 (2026-09-19)。

背景
----
`beat_anchor_check.py` 量的是**切点**落不落鼓点; 用户 2026-09-19 反馈的
"镜头动感拉镜不如之前踩点" 是另一个维度 —— **脉冲运镜**("拉进-闪回")的
落点。此前没有对应指标, 该维度一直是盲区。

运镜触发源与包络 (production_director._extract_clip):
  · 只对剧本派发了 push / zoom_in / static 的镜头生效
  · 触发点 = 该段 onset_times 换算的镜头内帧号
    (2026-09-19 起 onset_times 收敛为: 强鼓锚 + 高潮段旋律锚)
  · 每个触发点: PUNCH_ATTACK_FRAMES 帧冲近(二次加速) + PUNCH_RELEASE_FRAMES 帧
    弹回(二次减速), 合计 PUNCH_ENVELOPE 帧包络（默认 2+5=7；本脚本从渲染端导入常量）
  · 相邻触发点 < PUNCH_MIN_GAP_FRAMES 则合并, 防包络叠成糊

本脚本输出五项判据:
  1. 撞击次数 / 密度 (次/秒)
  2. 落点性质: 强鼓点 / 弱鼓点 / 仅旋律 / 落空 —— 目标是"零落空 + 高强鼓占比"
  3. 分节密度: 铺垫段应稀疏、爆发段应密集 (动态对比)
  4. 包络占空比: Σ包络帧 / 总帧 —— 接近或超过 100% 意味着缩放从不回落,
     读不出离散命中 (用户听感"不踩点"的机械成因)
  5. **包络完整度** (2026-09-23 新增): 判据 1 的"N 次"只说明**排程**上排了几次,
     不说明成品里播完了几次。本项把每次撞击分成
       完整 / 被段边界截断 / 根本不触发
     三档, 否则"撞击 36 次"会在成品只播完 11 次时仍然报 36。
     (POC 实证: v9 计划 45 次 → 9 次不触发 → 36 次进入渲染里仅 11 次完整播完)

用法:
  python scripts/punch_beat_check.py --script output/unified_xxx/director_script.yaml
  python scripts/punch_beat_check.py --dir output/unified_xxx --anchors cache/stems/<key>/anchors.json
"""
from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.beat_anchors import load_file, strong_times  # noqa: E402

STRONG_TOL = 0.080        # ±80ms, 与 beat_anchor_check 口径一致
# 默认参数直接取渲染端常量 (单一真相源, 杜绝"改了渲染忘了改指标")。
# 对比历史版本时需传该版本当时的参数 (--envelope/--min-gap/--effects),
# 否则是用新参数重放旧剧本, 只能作"同参数下的相对比较"。
try:
    from ai.production_director import (  # noqa: E402
        PUNCH_ELIGIBLE_EFFECTS as PUNCH_EFFECTS,
    )
    from ai.production_director import (
        PUNCH_ENVELOPE,
    )
    from ai.production_director import (
        PUNCH_MIN_GAP_FRAMES as MIN_GAP_DEFAULT,
    )
    from ai.production_director import (
        PUNCH_MAX_SHIFT_FRAMES,
    )
    from ai.production_director import (
        PUNCH_SHORT_SEGMENT_FRAMES,
    )
except Exception:  # noqa: BLE001 — 渲染端依赖不可用时退回字面量
    PUNCH_ENVELOPE = 7
    MIN_GAP_DEFAULT = 7
    PUNCH_EFFECTS = ("push", "zoom_in", "static")
    PUNCH_SHORT_SEGMENT_FRAMES = 8
    PUNCH_MAX_SHIFT_FRAMES = 2


def _near(t: float, arr: list[float], tol: float = STRONG_TOL) -> bool:
    if not arr:
        return False
    i = bisect.bisect_left(arr, t)
    for j in (i - 1, i):
        if 0 <= j < len(arr) and abs(arr[j] - t) <= tol:
            return True
    return False


def punch_times(script: dict, *, fps: float = 24.0,
                min_gap: int = MIN_GAP_DEFAULT,
                effects: tuple = PUNCH_EFFECTS,
                envelope: int = PUNCH_ENVELOPE,
                fit_envelope: bool = True,
                short_segment_frames: int = PUNCH_SHORT_SEGMENT_FRAMES,
                max_shift: int = PUNCH_MAX_SHIFT_FRAMES
                ) -> tuple[list[float], list[dict]]:
    """从剧本还原实际会触发的撞击时刻 (绝对时间线秒) 与逐段明细。

    detail 除 `times` 外还给出**包络完整度**三分类 (2026-09-23 新增):
      · complete    — `onset + envelope <= 段帧数`, 包络能整段播完
      · truncated   — 包络会被段边界截断 (切走时缩放尚未回落, "闪回"读不出来)
      · never_fired — `onset >= 段帧数`, 被 `0 <= f < n` 过滤掉, **根本不触发**

    此前只给 `times`, 于是"撞击 N 次"里混着大量截断/不触发的, 指标系统性偏乐观。

    `fit_envelope=True` (默认) 复刻渲染端 2026-09-23 起的排程归一: 中长段把装不下的
    onset 前移到可容纳帧 (上限 max_shift, 超出丢弃), 短段不动。**要与 2026-09-23 之前
    的历史数字对比时必须传 `fit_envelope=False`**, 否则是"新排程重放旧剧本"。
    """
    out: list[float] = []
    detail: list[dict] = []
    for s in script.get("segments", []):
        if s.get("zoompan_effect") not in effects:
            continue
        st, en = float(s["start_time"]), float(s["end_time"])
        n = max(1, round((en - st) * fps))
        frames = sorted({max(0, int(round(ot * fps)))
                         for ot in (s.get("onset_times") or [])})
        kept: list[int] = []
        for f in frames:
            if not kept or f - kept[-1] >= min_gap:
                kept.append(f)

        shifted = 0
        dropped_shift = 0
        never = [f for f in kept if not 0 <= f < n]
        if fit_envelope and n > short_segment_frames:
            latest = n - envelope
            fitted: list[int] = []
            for f in kept:
                if f <= latest:
                    fitted.append(f)
                elif f - latest <= max_shift:
                    fitted.append(latest)
                    shifted += 1
                else:
                    dropped_shift += 1
            fitted = sorted(set(fitted))
            refit: list[int] = []
            for f in fitted:
                if not refit or f - refit[-1] >= min_gap:
                    refit.append(f)
            kept = refit
            never = []          # 中长段前移后必然落在段内, 不会"根本不触发"

        fired = [f for f in kept if 0 <= f < n]
        complete = [f for f in fired if f + envelope <= n]
        truncated = [f for f in fired if f + envelope > n]
        times = [st + f / fps for f in fired]
        out.extend(times)
        detail.append({"index": s.get("index"), "mood": s.get("mood"),
                       "start": st, "end": en, "effect": s.get("zoompan_effect"),
                       "frames": n,
                       "onsets_in": len(frames), "fired": len(fired),
                       "complete": len(complete),
                       "truncated": len(truncated),
                       "never_fired": len(never),
                       "never_fired_frames": never,
                       "shifted": shifted,
                       "dropped_shift": dropped_shift,
                       "punch_frames": [{"frame": f, "complete": f in complete}
                                        for f in fired],
                       "times": times})
    return sorted(out), detail


def analyze(script: dict, anchors: dict, *, fps: float = 24.0,
            min_gap: int = MIN_GAP_DEFAULT,
            effects: tuple = PUNCH_EFFECTS,
            envelope: int = PUNCH_ENVELOPE,
            fit_envelope: bool = True,
            sections: tuple[tuple[str, float, float], ...] | None = None) -> dict:
    strong = strong_times(anchors, 0.5)
    drum = sorted({round(t, 3) for k in ("kick", "snare") for t, _ in anchors.get(k, [])})
    mel = sorted({round(t, 3) for t, _ in anchors.get("melody", [])})

    punches, detail = punch_times(script, fps=fps, min_gap=min_gap,
                                  effects=effects, envelope=envelope,
                                  fit_envelope=fit_envelope)
    cls = Counter()
    for t in punches:
        if _near(t, strong):
            cls["强鼓点"] += 1
        elif _near(t, drum):
            cls["弱鼓点"] += 1
        elif _near(t, mel):
            cls["仅旋律"] += 1
        else:
            cls["落空"] += 1

    total_dur = sum(float(s["duration"]) for s in script.get("segments", []))
    n = len(punches)
    # 包络完整度：distinguishes "排程上排了 N 次" 与 "成品里播完了 M 次"
    n_complete = sum(d["complete"] for d in detail)
    n_truncated = sum(d["truncated"] for d in detail)
    n_never = sum(d["never_fired"] for d in detail)
    report = {
        "punches": n,
        "duration": round(total_dur, 3),
        "density_per_sec": round(n / total_dur, 3) if total_dur else 0.0,
        "classes": dict(cls),
        "on_drum_pct": round((cls["强鼓点"] + cls["弱鼓点"]) / n, 4) if n else 0.0,
        "strong_pct": round(cls["强鼓点"] / n, 4) if n else 0.0,
        "miss_pct": round(cls["落空"] / n, 4) if n else 0.0,
        "envelope_frames": n * envelope,
        "envelope_duty_pct": round(n * envelope / max(1, round(total_dur * fps)), 4),
        "punch_shots": sum(1 for d in detail if d["fired"]),
        "shots": len(script.get("segments", [])),
        "min_gap_frames": min_gap,
        # --- 包络完整度（2026-09-23 新增）---
        "envelope_complete": n_complete,
        "envelope_truncated": n_truncated,
        "envelope_never_fired": n_never,
        "envelope_complete_pct": round(n_complete / n, 4) if n else 0.0,
        "planned_punches": n + n_never,
        "envelope_fit": fit_envelope,
        "envelope_shifted": sum(d["shifted"] for d in detail),
        "envelope_dropped_shift": sum(d["dropped_shift"] for d in detail),
    }
    if sections:
        per = {}
        for name, a, b in sections:
            k = sum(1 for t in punches if a <= t < b)
            per[name] = {"punches": k, "density": round(k / (b - a), 3)}
        report["sections"] = per
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=None, help="director_script.yaml 路径")
    ap.add_argument("--dir", default=None, help="run 输出目录 (自动找 director_script.yaml)")
    ap.add_argument("--anchors", default=None,
                    help="anchors.json; 缺省按剧本 bgm_path 的 sha256[:12] 定位缓存")
    ap.add_argument("--min-gap", type=int, default=MIN_GAP_DEFAULT)
    ap.add_argument("--envelope", type=int, default=PUNCH_ENVELOPE,
                    help="撞击包络帧数 (2冲+5弹=7)")
    ap.add_argument("--effects", default=",".join(PUNCH_EFFECTS),
                    help="可承载撞击的运镜类型 (逗号分隔)")
    ap.add_argument("--json", default=None, help="报告落盘路径")
    ap.add_argument("--no-envelope-fit", dest="fit_envelope", action="store_false",
                    default=True,
                    help="禁用包络完整度归一（复刻 2026-09-23 之前的排程，用于与历史数字对比）")
    ap.add_argument("--sections", default="铺垫=0:14,爆发=14:27",
                    help="分节对照 名称=起:止 (逗号分隔, 秒)")
    args = ap.parse_args()

    sp = Path(args.script) if args.script else (
        Path(args.dir) / "director_script.yaml" if args.dir else None)
    if not sp or not sp.exists():
        print(f"找不到剧本: {sp}")
        return 2
    script = yaml.safe_load(sp.read_text(encoding="utf-8"))

    if args.anchors:
        anchors = load_file(args.anchors)
    else:
        from core.beat_anchors import load_for_bgm
        bgm = script.get("bgm_path", "")
        anchors = load_for_bgm(bgm) if bgm else {"kick": [], "snare": [], "melody": []}
    if not anchors.get("kick") and not anchors.get("snare"):
        print("锚点表为空 (缓存缺席?), 无法判定落点性质")
        return 2

    sections = []
    for part in (args.sections or "").split(","):
        if "=" in part and ":" in part:
            nm, span = part.split("=", 1)
            a, b = span.split(":", 1)
            try:
                sections.append((nm.strip(), float(a), float(b)))
            except ValueError:
                pass
    _fx = tuple(x.strip() for x in args.effects.split(",") if x.strip())
    rep = analyze(script, anchors, min_gap=args.min_gap, effects=_fx,
                  envelope=args.envelope, fit_envelope=args.fit_envelope,
                  sections=tuple(sections) or None)

    print(f"\n=== {sp.parent.name} 运镜撞击体检 ===")
    print(f"  撞击 {rep['punches']} 次 / {rep['duration']:.1f}s "
          f"= {rep['density_per_sec']:.2f} 次/秒 | 有撞击的镜头 "
          f"{rep['punch_shots']}/{rep['shots']}")
    c = rep["classes"]
    print(f"  落点性质: 强鼓点 {c.get('强鼓点', 0)} / 弱鼓点 {c.get('弱鼓点', 0)} / "
          f"仅旋律 {c.get('仅旋律', 0)} / 落空 {c.get('落空', 0)}")
    print(f"    → 打在鼓上 {rep['on_drum_pct']:.1%} | 强鼓点占比 "
          f"{rep['strong_pct']:.1%} | 落空 {rep['miss_pct']:.1%}")
    if "sections" in rep:
        seg_txt = " | ".join(f"{k} {v['punches']} 次 ({v['density']:.2f}/s)"
                             for k, v in rep["sections"].items())
        print(f"  分节密度: {seg_txt}")
    print(f"  包络占空比: {rep['envelope_frames']} 帧 / "
          f"{round(rep['duration'] * 24)} 帧 = {rep['envelope_duty_pct']:.0%}"
          f"  (≥100% = 缩放从不回落, 读不出离散命中)")
    print(f"  包络完整度: {rep['envelope_complete']}/{rep['punches']} 次播完 "
          f"= {rep['envelope_complete_pct']:.0%}  | 被段边界截断 "
          f"{rep['envelope_truncated']} 次 | 计划里但根本不触发 "
          f"{rep['envelope_never_fired']} 次")
    if rep["envelope_fit"]:
        print(f"    （已启用包络完整度归一：前移 {rep['envelope_shifted']} 次、"
              f"丢弃 {rep['envelope_dropped_shift']} 次超限前移）")
    else:
        print("    （--no-envelope-fit：复刻 2026-09-23 之前的排程，用于与历史数字对比）")
    print(f"    ↑ 「撞击 {rep['punches']} 次」是**排程数**；成品里完整播完的是 "
          f"{rep['envelope_complete']} 次，其余在切走时缩放尚未回落，")
    print(f"      「闪回」读不出来。计划总数 = {rep['planned_punches']} 次。")

    if args.json:
        Path(args.json).write_text(
            json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
