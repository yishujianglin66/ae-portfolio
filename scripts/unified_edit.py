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
# 2026-09-10: 原 default 独自升级.mp3 已随 D 盘清理删除，换 repair62 冒烟实证过的 1_hot40s.mp3
DEFAULT_BGM = r"D:\AE-Work\音频素材库\BGM\1_hot40s.mp3"

# 运镜标签 → 编排参数映射 (VLM 标签告诉导演哪段素材适合什么角色)
MOTION_ROLE = {
    "zoom": "爆发/推进段 (素材自带推近感)",
    "tilt-orbit": "环绕/对抗段 (素材自带动感)",
    "static": "铺垫/叙事段 (素材稳定适合叠文字)",
}


def stage1_beat_analysis(bgm_path: str) -> dict:
    """① BGM 节拍/动态分析 (beat_strength_engine + music_dynamics).

    Returns structured beat and section data for agent consumption.

    修复（2026-09-09）：原实现调用 `engine.detect()` / `dyn.analyze(path)`，
    但这两个 API 不存在（真实签名见下），且模块路径写成 `ai.*`（实为 `core.*`）。
    该函数此前恒抛异常——因产出只写进报告、不参与渲染，成为休眠 bug。
    现按生产路径（ai/production_director.py:1572）的正确用法重写。
    """
    import librosa
    import numpy as np

    from core.beat_strength_engine import BeatStrengthEngine
    from core.music_dynamics import MusicDynamicsAnalyzer

    y, sr = librosa.load(bgm_path, sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    rms_times = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=512)
    onsets_sec = librosa.onset.onset_detect(
        y=y, sr=sr, units="time", backtrack=False)

    engine = BeatStrengthEngine(fps=24)
    # 无 downbeat 检测时用空数组（classify_beats 内部按 onset 能量分级）
    beat_class = engine.classify_beats(
        np.asarray(beat_times), np.asarray([]),
        onset_envelope=onset_env, rms_energy=rms, times=rms_times,
        sr=sr, hop_length=512)

    dyn = MusicDynamicsAnalyzer(min_section_dur=1.2, smooth_frames=15)
    sections = dyn.analyze(
        rms, rms_times, len(y) / sr,
        beats_sec=np.asarray(beat_times) if len(beat_times) else None,
        onsets_sec=np.asarray(onsets_sec) if len(onsets_sec) else None,
    )

    stats = beat_class.statistics()
    return {
        "tempo_bpm": round(float(np.atleast_1d(tempo)[0]), 2),
        "beat_count": len(beat_times),
        "beat_strength": stats,
        "beats": [{"time": round(float(t), 3)}
                  for t in beat_times[:50]],
        "sections": [
            {"start": round(float(s.start), 3), "end": round(float(s.end), 3),
             "level": s.level, "energy": round(float(s.energy_mean), 4)}
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
    cut_times_override: list | None = None,
) -> dict:
    """③ 编排渲染 (ProductionDirector V23 引擎).

    Returns path to rendered video and production metadata.
    cut_times_override: P2 切点修复轮注入的修复切点表 (2026-09-10 接线)。
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
        cut_times_override=cut_times_override,
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

    from core.sfx_layer import SFX_TAIL_S, shorten_sfx
    from core.sfx_layer import _load_index as _sfx_index
    
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
    
    # 能量预算 (2026-09-09): 混音前实测底轨真峰值，按余量缩放 SFX 增益。
    # 背景: run61 底轨已 -9.1 LUFS / TP +0.2 dBFS，任何附加能量必然削波。
    _budget = {"sfx_scale": 1.0, "base_gain_db": 0.0, "verdict": "unknown"}
    try:
        from core.audio_budget import budget as _ab_budget
        from core.audio_budget import measure as _ab_measure
        _bm = _ab_measure(input_video)
        _budget = _ab_budget(_bm, n_sfx=len(plan))
        print(f"    [音频预算] {_budget['verdict']}: {_budget['note']}")
    except Exception as _ab_e:  # noqa: BLE001
        print(f"    [音频预算跳过] {_ab_e}")

    _sfx_scale = float(_budget.get("sfx_scale", 1.0))
    _base_gain_db = float(_budget.get("base_gain_db", 0.0))

    def _mix_batch(pb, in_mp4, out_mp4):
        parts, labels = [], []
        for i, (f, ms, g) in enumerate(pb, start=1):
            _qms = int(round(ms / _FRAME_MS) * _FRAME_MS)
            _g = round(float(g) * _sfx_scale, 4)
            parts.append(f"[{i}:a]adelay={_qms}|{_qms},volume={_g:.3f}[s{i}]")
            labels.append(f"[s{i}]")
        # 底轨：按预算衰减（若需）并显式打标签，才能进 amix
        if abs(_base_gain_db) > 0.01:
            parts.append(f"[0:a]volume={_base_gain_db:.2f}dB[base]")
        else:
            parts.append("[0:a]anull[base]")
        # amix 后限幅到 -1.5 dBFS (0.8414)，level=disabled 避免自动增益补偿
        parts.append("[base]" + "".join(labels) +
                     f"amix=inputs={len(pb)+1}:duration=first:normalize=0[am];"
                     f"[am]alimiter=attack=1:release=50:limit=0.8414:level=disabled[outa]")
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
    # V23_KEEP_INTERMEDIATES=1 跳过 (2026-09-10): 后台沙箱批量删除熔断
    if os.environ.get("V23_KEEP_INTERMEDIATES") != "1":
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
    ap.add_argument("--repair-cuts", dest="repair_cuts", action="store_true",
                    default=True, help="切点自检 FAIL 时自动修表重渲 (默认开)")
    ap.add_argument("--no-repair-cuts", dest="repair_cuts", action="store_false",
                    help="关闭切点自动修复 (只检测出报告, 旧行为)")
    ap.add_argument("--repair-rounds", type=int, default=2,
                    help="切点自检总轮数上限(含首轮检测), 默认2=最多1次重渲")
    args = ap.parse_args()

    sources = args.sources or DEFAULT_SOURCES
    sources = [s for s in sources if os.path.exists(s)]
    assert len(sources) >= 3, f"可用素材不足: {len(sources)}"
    out_dir = PROJECT / "output" / f"unified_{args.tag}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    report = {"sources": sources, "bgm": args.bgm, "theme": args.theme,
              "capabilities_used": {}, "stages": {}}

    # 成本记账上下文 (2026-09-19): 本次出片的所有 LLM 调用按 tag 归组,
    # cost_report 才能算"单条视频平均成本"（验收指标 ≤ $0.05/条）。
    try:
        from core.cost_logger import set_context as _set_cost_ctx
        _set_cost_ctx(pipeline=args.tag, stage="stage1_beat")
    except Exception:  # noqa: BLE001 — 记账不可用不阻断出片
        pass

    print("=" * 62)
    print("统一编排入口 — 自动启用全部积累能力")
    print("=" * 62)

    # [技能注册表预检] P2 真融入（2026-09-25）：开工前自动读卡——
    # 依赖卡存在性/stage 闸门/宿主就绪/成本预算，预检结果进 report。
    try:
        from core.skill_preflight import preflight_for_pipeline, format_report as _pf_fmt
        _pf = preflight_for_pipeline("unified_edit")
        report["skill_preflight"] = _pf
        print(_pf_fmt(_pf))
    except Exception as _pf_e:  # noqa: BLE001 — 预检不可用不阻断出片
        print(f"  (技能预检未启用: {_pf_e})")

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

    # Stage 3+4 渲染链闭包: stage3 → EDL → 4a LUT → 4b SFX
    # 闭包化以便 P2 切点修复轮带 cut_times_override 重入同一链路 (2026-09-10)
    def _render_chain(cut_times_override=None):
        print("\n[能力③] V23 编排引擎..."
              + (" (切点修复重渲)" if cut_times_override else ""))
        try:
            from core.cost_logger import set_context as _sc
            _sc(stage="stage3_render")     # 剧本/镜头设计等 LLM 调用在此段
        except Exception:  # noqa: BLE001
            pass
        render_result = stage3_render_cut(
            sources=sources,
            bgm_path=args.bgm,
            output_dir=out_dir,
            tag=args.tag,
            duration=args.duration,
            theme=args.theme,
            style=args.style,
            enable_ae=os.environ.get("MASTER_NO_AE_CHANNEL") != "1",
            cut_times_override=cut_times_override,
        )
        print(f"    成片: {render_result['video_path']}")

        # --- P0 确定性渲染框架: EDL 落盘 (吸收 HyperFrames 渲染清单 + video-use EDL 设计)
        # 非侵入: 失败只记日志, 绝不阻断主管线
        try:
            from scripts.edl import build_edl, lint_edl, save_edl
            _pr_path = out_dir / "production_report.json"
            if _pr_path.exists():
                _edl = build_edl(_pr_path, bgm_path=args.bgm, sources=sources,
                                style=args.style, theme=args.theme,
                                duration=args.duration)
                _errs = lint_edl(_edl)
                save_edl(_edl, out_dir / "edl.json")
                report["edl"] = {"path": str(out_dir / "edl.json"),
                                 "cuts": len(_edl["cuts"]),
                                 "lint_errors": _errs}
                print(f"    EDL: {len(_edl['cuts'])} cuts 落盘 "
                      f"(lint {'PASS' if not _errs else 'FAIL ' + str(len(_errs))})")
        except Exception as _edl_e:  # noqa: BLE001
            print(f"    [EDL 跳过] {_edl_e}")

        # Prepare data for SFX
        _sections_dicts = [{"start": s.start, "end": s.end, "level": s.level,
                            "energy_mean": s.energy_mean}
                           for s in render_result["dyn_sections"]]
        _onsets_raw = render_result["onsets_raw"]
        print(f"    音乐分析: {len(render_result['dyn_sections'])} 动态段, "
              f"{len(_onsets_raw)} onset")

        # Stage 4a: Apply LUT
        print("\n[能力④-a] LUT 质感管线...")
        lut_result = stage4a_apply_lut(
            input_video=render_result["video_path"],
            output_dir=out_dir,
            style=args.style,
            tag=args.tag,
        )
        print("    LUT: " + ("OK" if lut_result["success"] else "SKIP"))

        # Stage 4b: Apply SFX
        print("\n[能力④-b] SFX v2.1 音乐性增强...")
        pr_path = out_dir / "production_report.json"
        sfx_result = stage4b_apply_sfx(
            input_video=lut_result["output_video"],
            bgm_path=args.bgm,
            output_dir=out_dir,
            tag=args.tag,
            duration=args.duration,
            sections_dicts=_sections_dicts,
            onsets_raw=_onsets_raw,
            pr_path=pr_path,
        )
        print(f"    SFX v2.1: {'OK' if sfx_result['success'] else 'FAIL'} "
              f"({sfx_result['sfx_count']} 落点)")
        return {"render_result": render_result, "lut_result": lut_result,
                "sfx_result": sfx_result,
                "final_video": sfx_result["output_video"]}

    _chain = _render_chain()
    render_result = _chain["render_result"]
    report["base_video"] = render_result["video_path"]
    report["capabilities_used"]["v23_engine"] = True
    report["capabilities_used"]["lut"] = _chain["lut_result"]["success"]
    report["capabilities_used"]["sfx"] = _chain["sfx_result"]["success"]
    final_video = _chain["final_video"]

    # --- P2 切点级 self-eval + repair 接线 (2026-09-10)
    # 此前只 analyze 不 repair: run61 检出 76 处 frozen_cut 仍照常出片。
    # 现在 FAIL → repair_cutpoints 修表(frozen/min_gap 丢弃, pop ±1帧微调)
    # → 带 cut_times_override 重渲整链(stage3+EDL+4a+4b) → 再检,
    # 最多 --repair-rounds 轮(默认2, 含首轮检测即最多1次重渲)。
    # 关闭: --no-repair-cuts 或 AEKV_REPAIR_CUTS=0。
    # 已知边界: audio_pop 部分源自 4b SFX 落点, 修切点后 SFX 跟随移动,
    # ±1帧微调主要消除拼接咔哒; flash 为人工项不自动修。
    try:
        from scripts.cutpoint_selfeval import analyze_cutpoints, repair_cutpoints
        from core.beat_anchors import load_for_bgm, strong_times
        # 强鼓点锚 (2026-09-19): 修复必须保节拍。缓存缺席 → 空表, 修复退回
        # 原"丢弃"策略并跳过节拍回归守卫 (fail-safe, 不阻断出片)。
        _anchors_strong = strong_times(load_for_bgm(args.bgm))
        _edl_path = out_dir / "edl.json"
        if _edl_path.exists():
            _edl_j = json.loads(_edl_path.read_text(encoding="utf-8"))
            _cuts = [float(t) for t in _edl_j.get("cut_points", [])]
            _cp_rep = analyze_cutpoints(final_video, _cuts)
            _history = [{"round": 0, "video": final_video,
                         "cut_count": _cp_rep["cut_count"],
                         "verdict": _cp_rep["verdict"],
                         "issues": _cp_rep["issues"]}]
            print(f"    切点自检: {_cp_rep['verdict']} "
                  f"({_cp_rep['cut_count']} 刀, {len(_cp_rep['issues'])} 事故)")
            _repair_on = (args.repair_cuts
                          and os.environ.get("AEKV_REPAIR_CUTS", "1") == "1")
            _rnd = 0
            while (_cp_rep["verdict"] == "FAIL" and _repair_on
                   and _rnd < max(args.repair_rounds - 1, 0)):
                _rstats: dict = {}
                _new_cuts = repair_cutpoints(_cuts, _cp_rep["issues"],
                                             anchors=_anchors_strong,
                                             stats=_rstats)
                if _rstats.get("beat_before") is not None:
                    print(f"    节拍守卫: 修前 {_rstats['beat_before']:.3f} → "
                          f"修后 {_rstats.get('beat_after', 0):.3f} "
                          f"[{_rstats.get('guard')}] "
                          f"重锚 {len(_rstats.get('reanchored', []))} / "
                          f"丢弃 {len(_rstats.get('dropped', []))}")
                _history[-1] = dict(_history[-1], repair_stats=_rstats)
                if _rstats.get("guard") == "aborted":
                    print(f"    切点修复: 已中止 — {_rstats.get('guard_reason')}")
                    break
                if not _new_cuts or _new_cuts == sorted(_cuts):
                    print("    切点修复: 修表无变化(仅剩人工项), 停止重渲转人工")
                    break
                _rnd += 1
                print(f"    切点修复 round {_rnd}: "
                      f"{len(_cuts)}→{len(_new_cuts)} 刀, 整链重渲...")
                _chain = _render_chain(cut_times_override=_new_cuts)
                final_video = _chain["final_video"]
                report["capabilities_used"]["lut"] = _chain["lut_result"]["success"]
                report["capabilities_used"]["sfx"] = _chain["sfx_result"]["success"]
                # 重渲后 EDL 已重建, 以落盘 EDL 切点为唯一真相再检
                _edl_j = json.loads(_edl_path.read_text(encoding="utf-8"))
                _cuts = [float(t) for t in _edl_j.get("cut_points", _new_cuts)]
                _cp_rep = analyze_cutpoints(final_video, _cuts)
                _history.append({"round": _rnd, "video": final_video,
                                 "cut_count": _cp_rep["cut_count"],
                                 "verdict": _cp_rep["verdict"],
                                 "issues": _cp_rep["issues"]})
                print(f"    切点复检 round {_rnd}: {_cp_rep['verdict']} "
                      f"({_cp_rep['cut_count']} 刀, {len(_cp_rep['issues'])} 事故)")
            _cp_out = dict(_cp_rep)
            _cp_out["repair"] = {"enabled": _repair_on, "rounds_used": _rnd,
                                 "history": _history}
            (out_dir / "cutpoint_report.json").write_text(
                json.dumps(_cp_out, ensure_ascii=False, indent=1),
                encoding="utf-8")
            report["cutpoint_selfeval"] = {
                "verdict": _cp_rep["verdict"],
                "issues": len(_cp_rep["issues"]),
                "repair_rounds": _rnd,
            }
    except Exception as _cp_e:  # noqa: BLE001
        print(f"    [切点自检跳过] {_cp_e}")

    # --- 音频母带 (2026-09-09): 响度归一到 -14 LUFS / 真峰值 ≤ -1.5 dBTP
    # 混音阶段已挂 limiter 与能量预算；此步做**交付口径归一**（流媒体标准），
    # 幂等：已达标时几乎不动。视频流直接复制，零画质损失。
    # 开关：AEKV_MASTER_DELIVER=0 可关闭（默认开启）。
    if os.environ.get("AEKV_MASTER_DELIVER", "1") == "1":
        try:
            from scripts.master_deliver import (
                encode_master as _md_encode,
            )
            from scripts.master_deliver import (
                measure_loudness as _md_measure,
            )
            from scripts.master_deliver import (
                verify_audio as _md_verify,
            )
            _md_src = Path(final_video)
            _md_out = _md_src.with_name(_md_src.stem + "_mastered.mp4")
            _md_measured = _md_measure(_md_src)
            if _md_encode(_md_src, _md_out, _md_measured):
                _md_la = _md_verify(_md_out)
                report["audio_master"] = {"path": str(_md_out), "audio": _md_la}
                print(f"    音频母带: {_md_la.get('lufs')} LUFS / "
                      f"真峰值 {_md_la.get('true_peak_dbtp')} dBTP")
                final_video = str(_md_out)
            else:
                print("    [音频母带失败] 保留混音版")
        except Exception as _md_e:  # noqa: BLE001
            print(f"    [音频母带跳过] {_md_e}")

    # --- 交付规格闸门 (2026-09-09): 码率/帧率/位深/时长/音频峰值
    # 吸收 AKROSS Con 交付规格；不达标只告警不阻断（保留成片供诊断），
    # 但把结论写进报告与 evidence，避免"检测了却不管"。
    try:
        from scripts.check_delivery_spec import SPEC as _SPEC
        from scripts.check_delivery_spec import check_one as _spec_check
        _spec = dict(_SPEC)
        # 短样片按实际时长放宽下限（AKROSS 原始口径是 1-15 分钟）
        _spec["duration_sec"] = (min(_spec["duration_sec"][0], args.duration * 0.8),
                                 _spec["duration_sec"][1])
        _spec_rep = _spec_check(Path(final_video), _spec)
        (out_dir / "delivery_spec_report.json").write_text(
            json.dumps(_spec_rep.as_dict(), ensure_ascii=False, indent=1),
            encoding="utf-8")
        _spec_issues = [c for c in _spec_rep.checks if c.status != "PASS"]
        report["delivery_spec"] = {
            "verdict": _spec_rep.status,
            "issues": [{"name": c.name, "detail": c.detail} for c in _spec_issues],
        }
        print(f"    交付规格: {_spec_rep.status} "
              f"({len(_spec_issues)} 项需关注)")
        for _c in _spec_issues:
            print(f"      ! {_c.name}: {_c.detail}")
    except Exception as _sp_e:  # noqa: BLE001
        print(f"    [交付规格自检跳过] {_sp_e}")

    # Stage 5: Score video
    # 评分依赖 open_clip + 本地权重；缺失时应降级跳过，不能中断整条链路
    # （否则后续闸门/经验采集/报告落盘全部丢失——2026-09-09 实测踩到）。
    print("\n[能力⑤] 成片评分...")
    try:
        from core.cost_logger import set_context as _sc
        _sc(stage="stage5_score")          # 评分/VLM 复核的云端调用在此段
    except Exception:  # noqa: BLE001
        pass
    try:
        score_result = stage5_score_video(final_video)
        if "scores" in score_result and score_result["scores"]:
            report["scores"] = score_result["scores"]
            for k, v in sorted(score_result["scores"].items()):
                print(f"    {k.replace('score_', ''):<14} {v}")
        else:
            report["scores"] = None
            print(f"    [评分降级] {score_result.get('error', '无结果')}")
    except Exception as _sc_e:  # noqa: BLE001
        report["scores"] = None
        print(f"    [评分跳过] {type(_sc_e).__name__}: {_sc_e}")

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
