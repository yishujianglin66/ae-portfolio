"""unified_edit.py — 统一编排入口（一次调用, 自动启用全部积累能力）

解决用户核心诉求 (2026-08-29): "每次剪辑任务自动启用所有开发过的资料项目
以及踩点经验, 而不是每次单独重新推进开发"。

全链:
  ① BGM 节拍/动态分析      (beat_strength_engine + music_dynamics, V23 同款)
  ② 素材运镜标注           (CNN+VLM 分层分类器, 每段素材打标签+置信度)
  ③ 编排渲染               (ProductionDirector V23 引擎: 高光分配/变速/转场/品味卡)
  ④ 质感管线               (LUT 按风格主题 + SFX 按真实节拍)
  ⑤ 成片评分               (CNN+SiliconFlow 链 hybrid)
  ⑥ 报告                   (全链调用量/标签/评分落盘, 可追溯)

用法:
  python scripts/unified_edit.py --bgm <BGM.mp3> [--sources a.mp4 b.mp4 ...] \
      [--theme "主题"] [--duration 40] [--style amv_highenergy] [--tag demo]

素材缺省 = V22/V23 验证过的 7 部素材池。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

DEFAULT_SOURCES = [
    r"D:\AE-Work\resources\video\猫猫（一般）\素材\猫1.mp4",
    r"D:\AE-Work\resources\video\猫猫（一般）\素材\猫2.mp4",
    r"D:\AE-Work\resources\video\美人鱼（较难）\素材\alya-05.mp4",
    r"D:\AE-Work\resources\video\初音（简单）\Hatsune Miku Twixtor 4K.mp4",
    r"D:\AE-Work\resources\video\五条悟（一般）\素材\五条悟第二季.mp4",
    r"D:\BaiduNetdiskDownload\AE新手10套\独自升级（一般）\独自升级2.mp4",
    r"D:\BaiduNetdiskDownload\AE新手10套\独自升级（一般）\独自升级5.mp4",
    # --- 2026-09-05 素材库扩充(#12): 新番+补段, 缓解画面同质/静帧 ---
    r"D:\AE-Work\resources\video\蓝色监狱（量多）\素材\nagi2.mp4",
    r"D:\AE-Work\resources\video\蓝色监狱（量多）\素材\Nagi Seishiro (No CC).mp4",
    r"D:\AE-Work\resources\video\辉夜（一般）\素材\辉夜1.mp4",
    r"D:\AE-Work\resources\video\美人鱼（较难）\素材\alya-twix.mp4",
    r"D:\AE-Work\resources\video\美人鱼（较难）\素材\alya-twixtor04.mp4",
    r"D:\AE-Work\resources\video\五条悟（一般）\素材\五条悟第二季2.mp4",
    r"D:/AE-Work/resources/video/蓝色监狱（量多）/素材/v0300fg10000cr7mf77og65lhrmfrv5g.MP4",
]
DEFAULT_BGM = r"D:\AE-Work\音频素材库\BGM\独自升级.mp3"

# 运镜标签 → 编排参数映射 (VLM 标签告诉导演哪段素材适合什么角色)
MOTION_ROLE = {
    "zoom": "爆发/推进段 (素材自带推近感)",
    "tilt-orbit": "环绕/对抗段 (素材自带动感)",
    "static": "铺垫/叙事段 (素材稳定适合叠文字)",
}


def stage1_beat_analysis(bgm_path: str) -> dict:
    """① BGM 节拍/动态分析 (beat_strength_engine + music_dynamics).
    
    Returns structured beat and section data for agent consumption.
    """
    from ai.beat_strength_engine import BeatStrengthEngine
    from ai.music_dynamics import MusicDynamicsAnalyzer
    
    engine = BeatStrengthEngine()
    beats = engine.detect(bgm_path)
    
    dyn = MusicDynamicsAnalyzer()
    sections = dyn.analyze(bgm_path)
    
    return {
        "beat_count": len(beats),
        "beats": [{"time": b.time, "strength": b.strength} for b in beats[:50]],
        "sections": [
            {"start": s.start, "end": s.end, "level": s.level, "energy": s.energy_mean}
            for s in sections
        ],
    }


def stage2_motion_labels(sources: list, cache_dir: Path) -> dict:
    """② 素材运镜标注 — CNN+VLM 分层分类器 (置信度透传)。"""
    sys.path.insert(0, str(PROJECT))
    os.environ.setdefault("AEKV_NO_LORA", "1")  # 跳过 LoRA 直走分层
    from ai.camera_decision import SourceCameraInventory
    inv = SourceCameraInventory()
    out = {}
    for s in sources:
        r = inv.analyze(s)
        out[Path(s).name] = {
            "motion": r.get("coarse") or r.get("label"),
            "confidence": r.get("confidence"),
            "source": r.get("source"),
        }
        print(f"    {Path(s).name[:36]:<36} {r.get('coarse') or r.get('label'):<11} "
              f"conf={r.get('confidence')}")
    inv.unload()   # v13 OOM 根治: 运镜标注完成即释放 VLM 5.8GB/VideoMAE, 保阶段⑤评分显存
    return out


def stage3_render_cut(
    sources: list,
    bgm_path: str,
    output_dir: Path,
    tag: str,
    duration: float,
    theme: str,
    style: str,
    enable_ae: bool = True,
) -> dict:
    """③ 编排渲染 (ProductionDirector V23 引擎).
    
    Returns path to rendered video and production metadata.
    """
    from ai.production_director import ProductionDirector
    
    style_path = PROJECT / "data" / "style_cards" / f"{style}.json"
    taste = json.loads(style_path.read_text(encoding="utf-8")) if style_path.exists() else None
    
    director = ProductionDirector(
        work_dir=str(output_dir / "work"),
        taste_profile=taste,
    )
    
    base = director.render(
        video_sources=sources,
        bgm_path=bgm_path,
        output_dir=str(output_dir),
        output_name=f"{tag}_cut.mp4",
        target_duration=duration,
        resolution=(1920, 1080),
        fps=24,
        use_speed_ramp=True,
        verify_content=False,
        theme=theme,
        enable_ae_channel=enable_ae,
        clean_bgm_sfx=False,
        beat_lock_hard_cuts=True,
    )
    
    # Extract internal state for evidence chain
    dyn_sections = getattr(director, "_dyn_sections", []) or []
    onsets_raw = getattr(director, "_onsets", []) or []
    
    return {
        "video_path": str(base),
        "director": director,
        "dyn_sections": dyn_sections,
        "onsets_raw": onsets_raw,
    }


def stage4a_apply_lut(input_video: str, output_dir: Path, style: str, tag: str) -> dict:
    """④-a LUT 质感管线 (风格主题→好莱坞/戏剧性)."""
    import subprocess as sp
    
    theme_lut = {"amv_highenergy": "好莱坞 _ Hollywood", "cinematic_film": "好莱坞 _ Hollywood",
                 "vintage_film": "复古电影 _ Vintage Film"}.get(style, "好莱坞 _ Hollywood")
    from core.lut_pipeline import load_sampling
    cube = load_sampling().get(theme_lut, [None])[0]
    
    if not cube:
        return {"success": False, "error": f"LUT not found: {theme_lut}"}
    
    base_in = input_video
    # Compress large files first
    if Path(base_in).stat().st_size > 50e6:
        _small = output_dir / f"{tag}_small.mp4"
        sp.run(["ffmpeg", "-y", "-i", base_in, "-c:v", "libx264", "-preset", "fast",
                "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", str(_small)],
               capture_output=True, timeout=1200)
        base_in = str(_small)
    
    lut_mp4 = output_dir / f"{tag}_lut.mp4"
    _e = cube.replace(chr(92), "/").replace(":", chr(92) + ":") if cube else ""
    ok = bool(cube) and sp.run(
        ["ffmpeg", "-y", "-i", base_in, "-vf", "lut3d='" + _e + "'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "copy", str(lut_mp4)],
        capture_output=True, timeout=1200).returncode == 0
    
    return {
        "success": ok,
        "output_video": str(lut_mp4) if ok else input_video,
        "lut_applied": theme_lut,
    }


def stage4b_apply_sfx(
    input_video: str,
    bgm_path: str,
    output_dir: Path,
    tag: str,
    duration: float,
    sections_dicts: list,
    onsets_raw: list,
    pr_path: Path | None = None,
) -> dict:
    """④-b SFX v2.1 音乐性增强 (真实节拍从引擎 decision log)."""
    import random as _random
    import subprocess as _sp
    from core.sfx_layer import _load_index as _sfx_index, shorten_sfx, SFX_TAIL_S
    
    final = output_dir / (tag + "_final.mp4")
    _fallback_src = input_video
    
    if pr_path and pr_path.exists():
        _pr = json.loads(pr_path.read_text(encoding="utf-8"))
        _segs = _pr.get("script", {}).get("segments", [])
    else:
        # Fallback: no production report, skip SFX
        import shutil as _shutil
        _shutil.copy2(input_video, str(final))
        return {"success": True, "output_video": str(final), "sfx_count": 0}
    
    _pools = {k: _sfx_index().get(k, []) for k in ("impact", "whoosh", "riser", "glitch")}
    _lvl_mult = {"low": 0.65, "mid": 0.85, "high": 1.0}
    
    def _level_at(t):
        for s in sections_dicts:
            if s["start"] <= t < s["end"]:
                return s["level"]
        return "mid"
    
    # Strong drum onset detection
    _strong_onsets = []
    try:
        import librosa as _lb
        import numpy as _np
        _yb, _srb = _lb.load(bgm_path, sr=22050, mono=True)
        _oe = _lb.onset.onset_strength(y=_yb, sr=_srb, hop_length=512)
        _ot = _lb.times_like(_oe, sr=_srb, hop_length=512)
        _od = _lb.onset.onset_detect(y=_yb, sr=_srb, units="time")
        _ost = [float(_oe[min(_np.searchsorted(_ot, t), len(_oe) - 1)]) for t in _od]
        _th = _np.percentile(_ost, 55)
        _strong_onsets = sorted(float(t) for t, s in zip(_od, _ost) if s >= _th)
    except Exception:
        pass
    
    def _on_drum(t):
        return any(abs(t - s) <= 0.060 for s in _strong_onsets)
    
    def _short(f, pool):
        return shorten_sfx(f, SFX_TAIL_S[pool], pool=pool) or f
    
    _rng = _random.Random(2027)
    _last = {}
    plan = []
    cut_times = []
    boom_hits = []
    
    for s in _segs:
        t = round(s.get("start_time", 0), 2)
        if t < 0.05:
            continue
        cut_times.append(t)
        mood = s.get("mood", "build")
        if mood in ("drop", "climax"):
            pool, base, pre = "impact", 0.65, 0.040
        elif mood == "intro":
            pool, base, pre = "whoosh", 0.32, 0.080
        else:
            pool, base, pre = "whoosh", 0.38, 0.080
        files = _pools[pool]
        if not files:
            continue
        f = _rng.choice(files)
        for _ in range(3):
            if f != _last.get(pool) or len(files) == 1:
                break
            f = _rng.choice(files)
        _last[pool] = f
        gain = base * _lvl_mult.get(_level_at(t), 0.85)
        if not _on_drum(t):
            gain *= 0.5
        plan.append((_short(f, pool), max(0, int((t - pre) * 1000)), round(gain, 2)))
        if mood in ("drop", "climax") and _on_drum(t):
            boom_hits.append(max(0, int((t - 0.010) * 1000)))
    
    # Synthesize 65Hz boom
    boom_wav = output_dir / "_boom65.wav"
    if boom_hits and not boom_wav.exists():
        _sp.run(["ffmpeg", "-y", "-f", "lavfi",
                 "-i", "sine=frequency=65:duration=0.35",
                 "-af", "afade=t=in:st=0:d=0.005,"
                        "afade=t=out:st=0.03:d=0.30:curve=exp,volume=0.31",
                 str(boom_wav)], capture_output=True, timeout=60)
    for ms in boom_hits:
        plan.append((str(boom_wav), ms, 0.30))
    
    # Onset subdivision layer
    cuts_sorted = sorted(cut_times)
    _last_sub = -1.0
    _n_sub = 0
    for ot in onsets_raw:
        t = float(ot)
        if t < 0.5 or t >= duration - 0.2:
            continue
        if any(abs(t - c) < 0.18 for c in cuts_sorted):
            continue
        if _level_at(t) not in ("mid", "high"):
            continue
        if t - _last_sub < 0.45:
            continue
        _last_sub = t
        if not _pools["glitch"]:
            continue
        plan.append((_short(_rng.choice(_pools["glitch"]), "glitch"),
                     int(t * 1000), 0.18))
        _n_sub += 1
    
    # Mix SFX batches
    _FRAME_MS = 1000.0 / 24.0
    
    def _qframe(t):
        return int(round((t - 0.006) * 24) * _FRAME_MS)
    
    def _mix_batch(pb, in_mp4, out_mp4):
        parts, labels = [], []
        for i, (f, ms, g) in enumerate(pb, start=1):
            _qms = int(round(ms / _FRAME_MS) * _FRAME_MS)
            parts.append(f"[{i}:a]adelay={_qms}|{_qms},volume={g:.2f}[s{i}]")
            labels.append(f"[s{i}]")
        parts.append("[0:a]" + "".join(labels) +
                     f"amix=inputs={len(pb)+1}:duration=first:normalize=0[am];"
                     f"[am]alimiter=attack=1:release=50:limit=0.88:level=0[outa]")
        cmd = ["ffmpeg", "-y", "-i", in_mp4]
        for f, _, _ in pb:
            cmd += ["-i", f]
        cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[outa]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out_mp4]
        return _sp.run(cmd, capture_output=True, timeout=600).returncode == 0
    
    src = _fallback_src
    ok2 = True
    for bi in range(0, len(plan), 14):
        tgt = str(final) if bi + 14 >= len(plan) else str(output_dir / f"_sm{bi}.mp4")
        ok2 = ok2 and _mix_batch(plan[bi:bi + 14], src, tgt)
        src = tgt
    if not plan:
        import shutil as _shutil
        _shutil.copy2(_fallback_src, str(final))
        ok2 = True
    
    # Clean up intermediate files
    for _tmpm in output_dir.glob("_sm*.mp4"):
        try:
            _tmpm.unlink()
        except OSError:
            pass
    
    return {
        "success": ok2,
        "output_video": str(final),
        "sfx_count": len(plan),
    }


def stage5_score_video(video_path: str, mode: str = "local") -> dict:
    """⑤ 成片评分 (CNN + SiliconFlow 链 hybrid)."""
    from core.cnn_scorer import score_video_mode
    r = score_video_mode(video_path, mode)
    return {"scores": r.get("scores", {})}


def stage6_run_gate(output_dir: Path, tag: str, bgm_path: str) -> dict:
    """⑥ 闸门自动验收 (七关指标)."""
    import subprocess as _sp
    _g = _sp.run([sys.executable, str(PROJECT / "scripts" / "render_gate.py"),
                  str(output_dir), tag, "--bgm", bgm_path],
                 capture_output=True, text=True, timeout=900,
                 encoding="utf-8", errors="replace")
    _gacc = "ACCEPT" in _g.stdout
    return {
        "accepted": _gacc,
        "stdout": _g.stdout,
        "stderr": _g.stderr,
    }


def stage7_harvest_experience(output_dir: Path, tag: str, bgm_path: str) -> dict:
    """⑦ 自进化层: 自动经验采集."""
    import subprocess as _sp
    try:
        _sp.run([sys.executable,
                 str(PROJECT / "scripts" / "harvest_experience.py"),
                 str(output_dir), tag, "--bgm", bgm_path],
                timeout=900)
        return {"success": True}
    except Exception as _h_e:
        return {"success": False, "error": str(_h_e)}


def main() -> int:
    """CLI entry point — chains all stages sequentially (backward compatible)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--bgm", default=DEFAULT_BGM)
    ap.add_argument("--sources", nargs="*", default=None)
    ap.add_argument("--theme", default="燃向混剪: 铺垫→蓄力→爆发→收尾")
    ap.add_argument("--duration", type=float, default=19.4,
                    help="默认=BGM 独自升级.mp3 实长")
    ap.add_argument("--style", default="amv_highenergy")
    ap.add_argument("--tag", default="run")
    ap.add_argument("--skip-motion", action="store_true", help="跳过②(调试用)")
    args = ap.parse_args()

    sources = args.sources or DEFAULT_SOURCES
    sources = [s for s in sources if os.path.exists(s)]
    assert len(sources) >= 3, f"可用素材不足: {len(sources)}"
    out_dir = PROJECT / "output" / f"unified_{args.tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {"sources": sources, "bgm": args.bgm, "theme": args.theme,
              "capabilities_used": {}, "stages": {}}

    print("=" * 62)
    print("统一编排入口 — 自动启用全部积累能力")
    print("=" * 62)

    # Stage 1: Beat analysis (optional, for evidence chain)
    print("\n[能力①] BGM 节拍分析...")
    beat_result = stage1_beat_analysis(args.bgm)
    report["stages"]["beat_analysis"] = beat_result
    report["capabilities_used"]["beat_analysis"] = True

    # Stage 2: Motion labeling
    if not args.skip_motion:
        print("\n[能力②] 素材运镜标注 (CNN+VLM 分层分类器)...")
        motion_result = stage2_motion_labels(sources, out_dir)
        report["motion_labels"] = motion_result
        report["capabilities_used"]["motion_labels"] = True

    # Stage 3: Render cut
    print("\n[能力③] V23 编排引擎...")
    render_result = stage3_render_cut(
        sources=sources,
        bgm_path=args.bgm,
        output_dir=out_dir,
        tag=args.tag,
        duration=args.duration,
        theme=args.theme,
        style=args.style,
        enable_ae=os.environ.get("MASTER_NO_AE_CHANNEL") != "1",
    )
    report["base_video"] = render_result["video_path"]
    report["capabilities_used"]["v23_engine"] = True
    print(f"    成片: {render_result['video_path']}")

    # Prepare data for SFX
    _sections_dicts = [{"start": s.start, "end": s.end, "level": s.level,
                        "energy_mean": s.energy_mean} for s in render_result["dyn_sections"]]
    _onsets_raw = render_result["onsets_raw"]
    print(f"    音乐分析: {len(render_result['dyn_sections'])} 动态段, {len(_onsets_raw)} onset")

    # Stage 4a: Apply LUT
    print("\n[能力④-a] LUT 质感管线...")
    lut_result = stage4a_apply_lut(
        input_video=render_result["video_path"],
        output_dir=out_dir,
        style=args.style,
        tag=args.tag,
    )
    report["capabilities_used"]["lut"] = lut_result["success"]
    video_after_lut = lut_result["output_video"]
    print("    LUT: " + ("OK" if lut_result["success"] else "SKIP"))

    # Stage 4b: Apply SFX
    print("\n[能力④-b] SFX v2.1 音乐性增强...")
    pr_path = out_dir / "production_report.json"
    sfx_result = stage4b_apply_sfx(
        input_video=video_after_lut,
        bgm_path=args.bgm,
        output_dir=out_dir,
        tag=args.tag,
        duration=args.duration,
        sections_dicts=_sections_dicts,
        onsets_raw=_onsets_raw,
        pr_path=pr_path,
    )
    report["capabilities_used"]["sfx"] = sfx_result["success"]
    final_video = sfx_result["output_video"]
    print(f"    SFX v2.1: {'OK' if sfx_result['success'] else 'FAIL'} ({sfx_result['sfx_count']} 落点)")

    # Stage 5: Score video
    print("\n[能力⑤] 成片评分...")
    score_result = stage5_score_video(final_video)
    report["scores"] = score_result["scores"]
    for k, v in sorted(score_result["scores"].items()):
        print(f"    {k.replace('score_', ''):<14} {v}")

    # Stage 6: Quality gate
    try:
        print("\n[闸门] 七关指标验收...")
        gate_result = stage6_run_gate(out_dir, args.tag, args.bgm)
        print("    " + ("✅ ACCEPT 全部指标通过" if gate_result["accepted"] else "❌ REJECT 见上方指标"))
        report["capabilities_used"]["gate"] = True
        report["gate"] = gate_result
    except Exception as _g_e:
        print(f"    [闸门跳过] {_g_e}")

    # Stage 7: Harvest experience
    try:
        print("\n[自进化] 经验采集...")
        harvest_result = stage7_harvest_experience(out_dir, args.tag, args.bgm)
        report["capabilities_used"]["harvest"] = harvest_result["success"]
    except Exception as _h_e:
        print(f"    [经验采集跳过] {_h_e}")

    report["elapsed_s"] = round(time.time() - t0, 2)
    report["final_video"] = final_video
    (out_dir / "unified_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    
    used = report["capabilities_used"]
    print(f"\n启用能力: 节拍分析={used.get('beat_analysis', False)} "
          f"运镜标注={used.get('motion_labels', False)} "
          f"V23引擎✓ LUT={used.get('lut')} SFX={used.get('sfx')} 评分✓ 闸门={used.get('gate')}")
    print(f"交付: {final_video} | 报告: {out_dir / 'unified_report.json'} | {report['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
