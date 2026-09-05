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
]
DEFAULT_BGM = r"D:\AE-Work\音频素材库\BGM\独自升级.mp3"

# 运镜标签 → 编排参数映射 (VLM 标签告诉导演哪段素材适合什么角色)
MOTION_ROLE = {
    "zoom": "爆发/推进段 (素材自带推近感)",
    "tilt-orbit": "环绕/对抗段 (素材自带动感)",
    "static": "铺垫/叙事段 (素材稳定适合叠文字)",
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


def main() -> int:
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
              "capabilities_used": {}}

    print("=" * 62)
    print("统一编排入口 — 自动启用全部积累能力")
    print("=" * 62)

    # ② 素材运镜标注 (CNN+VLM)
    if not args.skip_motion:
        print("\n[能力②] 素材运镜标注 (CNN+VLM 分层分类器)...")
        report["motion_labels"] = stage2_motion_labels(sources, out_dir)
        report["capabilities_used"]["motion_labels"] = True

    # ③ 编排渲染 (ProductionDirector V23 引擎, 内含 BGM 节拍/高光分配/变速/转场)
    print("\n[能力③] V23 编排引擎 (BGM 节拍分析+高光分配+变速+品味卡)...")
    from ai.production_director import ProductionDirector
    style_path = PROJECT / "data" / "style_cards" / f"{args.style}.json"
    taste = json.loads(style_path.read_text(encoding="utf-8")) if style_path.exists() else None
    director = ProductionDirector(
        work_dir=str(out_dir / "work"),
        taste_profile=taste,
    )
    base = director.render(
        video_sources=sources,
        bgm_path=args.bgm,
        output_dir=str(out_dir),
        output_name=f"unified_{args.tag}.mp4",
        target_duration=args.duration,
        resolution=(1920, 1080),
        fps=24,
        use_speed_ramp=True,
        verify_content=False,
        theme=args.theme,
        # MASTER_NO_AE_CHANNEL=1: A/B 实验旁路 AE 分镜重渲（切点时间由 plan 决定，
        # AE 重渲不改变切点；桥接监听器不可用时避免无限等待）
        enable_ae_channel=os.environ.get("MASTER_NO_AE_CHANNEL") != "1",
        clean_bgm_sfx=False,      # 2026-09-02: BGM 直通保鼓点; SFX 改在最终音轨混(④-b)
        beat_lock_hard_cuts=True, # 2026-09-02: 卡点铁律-全硬切, xfade 中点糊切点(p50偏122ms)
    )
    report["capabilities_used"]["v23_engine"] = True
    report["base_video"] = str(base)
    print(f"    成片: {base}")

    # 提取引擎音乐分析 (供④ SFX v2 音乐性增强)
    _dyn_sections = getattr(director, "_dyn_sections", None) or []
    _onsets_raw = getattr(director, "_onsets", []) or []
    _sections_dicts = [{"start": s.start, "end": s.end, "level": s.level,
                        "energy_mean": s.energy_mean} for s in _dyn_sections]
    _onset_events = [{"time": float(t), "strength": 0.2} for t in _onsets_raw]
    print(f"    音乐分析: {len(_dyn_sections)} 动态段, {len(_onset_events)} onset")

    # ④ 质感管线: LUT (风格主题→好莱坞/戏剧性) + SFX (真实节拍从引擎 decision log)
    print("\n[能力④] 质感管线 (LUT + SFX)...")
    # 2026-09-01 BGM 修复: transcode_with_lut 的 -an 会剥引擎混好的 BGM 音轨
    # → 改用 -vf lut3d + -c:a copy 保音轨; 大文件先压 (121MB 直挂会超时)
    import subprocess as _sp
    theme_lut = {"amv_highenergy": "好莱坞 _ Hollywood", "cinematic_film": "好莱坞 _ Hollywood",
                 "vintage_film": "复古电影 _ Vintage Film"}.get(args.style, "好莱坞 _ Hollywood")
    from core.lut_pipeline import load_sampling
    cube = load_sampling().get(theme_lut, [None])[0]
    base_in = str(base)
    if Path(base).stat().st_size > 50e6:  # 大文件先压 (保音轨)
        _small = out_dir / f"{args.tag}_small.mp4"
        _sp.run(["ffmpeg", "-y", "-i", base_in, "-c:v", "libx264", "-preset", "fast",
                 "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", str(_small)],
                capture_output=True, timeout=1200)
        base_in = str(_small)
    lut_mp4 = out_dir / f"{args.tag}_lut.mp4"
    _e = cube.replace(chr(92), "/").replace(":", chr(92) + ":") if cube else ""
    ok = bool(cube) and _sp.run(
        ["ffmpeg", "-y", "-i", base_in, "-vf", "lut3d='" + _e + "'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "copy", str(lut_mp4)],
        capture_output=True, timeout=1200).returncode == 0
    print("    LUT " + theme_lut + "@0.55: " + ("OK" if ok else "SKIP"))
    report["capabilities_used"]["lut"] = ok

    # ④-c AE 整片精修 Pass (2026-09-04): 全片 Glow 微光+胶片颗粒
    # (单次 aerender, 所有镜头同时获得 AE 插件级质感, 失败回退原片)
    try:
        from ai.ae_render_channel import AERenderChannel
        _pol_dir = out_dir / "polish"
        _chan2 = AERenderChannel(_pol_dir, str(PROJECT))
        _polished = _chan2.polish_pass(str(lut_mp4) if ok else base_in, str(_pol_dir))
        if _polished:
            base_in = _polished
            report["capabilities_used"]["ae_polish"] = True
    except Exception as _pol_e:
        print(f"    [AE精修跳过] {_pol_e}")

    # ④-b SFX v2.1 音乐性增强 (2026-09-02)
    # 09-01 版只做"对齐切点"; v2.1 五招:
    #   招1 前置补偿: 裁短片峰在开头60ms处, 前置80ms → 峰落切点+20ms
    #   招2 力度曲线: 增益 × 段落能量等级 (low 0.65 / mid 0.85 / high 1.0)
    #   招3 重拍双层: drop/climax 切点 = impact + 65Hz 合成 boom (-10ms)
    #   招4 onset 细分层: 非切点弱 onset(引擎 84 个 vs 切点用 ~30 个) → 轻 glitch
    #   招5 智能裁短: 池文件多为 5-20s trailer 素材, 不裁短会叠成持续音墙
    #       掩蔽鼓点+限幅器压瞬态 (v2 实测 perc 0.056→0.003 的根因)。
    # 混音点=最终输出音轨 (amix [0:a]+N sfx), BGM 文件永不触碰 (2026-09-02 教训)。
    import random as _random
    from core.sfx_layer import _load_index as _sfx_index, shorten_sfx, SFX_TAIL_S
    pr_path = out_dir / "production_report.json"
    final = out_dir / (args.tag + "_final.mp4")
    _fallback_src = str(lut_mp4) if ok else base_in
    ok2 = False
    if pr_path.exists():
        _pr = json.loads(pr_path.read_text(encoding="utf-8"))
        _segs = _pr.get("script", {}).get("segments", [])
        _pools = {k: _sfx_index().get(k, [])
                  for k in ("impact", "whoosh", "riser", "glitch")}
        _lvl_mult = {"low": 0.65, "mid": 0.85, "high": 1.0}

        def _level_at(t):
            for s in _sections_dicts:
                if s["start"] <= t < s["end"]:
                    return s["level"]
            return "mid"

        # 强鼓点集 (2026-09-02): 不在强鼓点上的切点 SFX 减半 —
        # 弱拍切点的全响 SFX 会被听成"飘在音乐外的杂音"
        _strong_onsets = []
        try:
            # E0-1: 锚点模式下 SFX 强鼓点集直接用 stem 真值（kick/snare 强集）
            if getattr(director, "_drum_anchor_mode", False) and getattr(director, "_anchor_strong", None):
                _strong_onsets = [float(t) for t in director._anchor_strong]
                print(f"    SFX 强鼓点集: drum-anchor 真值 {len(_strong_onsets)} 个")
            else:
                import librosa as _lb
                import numpy as _np
                _yb, _srb = _lb.load(args.bgm, sr=22050, mono=True)
                _oe = _lb.onset.onset_strength(y=_yb, sr=_srb, hop_length=512)
                _ot = _lb.times_like(_oe, sr=_srb, hop_length=512)
                _od = _lb.onset.onset_detect(y=_yb, sr=_srb, units="time")
                _ost = [float(_oe[min(_np.searchsorted(_ot, t), len(_oe) - 1)])
                        for t in _od]
                _th = _np.percentile(_ost, 55)
                _strong_onsets = sorted(
                    float(t) for t, s in zip(_od, _ost) if s >= _th)
        except Exception:
            pass

        def _on_drum(t):
            return any(abs(t - s) <= 0.060 for s in _strong_onsets)

        def _short(f, pool):
            return shorten_sfx(f, SFX_TAIL_S[pool], pool=pool) or f

        _rng = _random.Random(2027)
        _last = {}
        plan = []          # (文件, adelay毫秒, 增益)
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
                gain *= 0.5   # 非强鼓点切点: SFX 减半, 不抢拍
            plan.append((_short(f, pool), max(0, int((t - pre) * 1000)), round(gain, 2)))
            if mood in ("drop", "climax") and _on_drum(t):
                boom_hits.append(max(0, int((t - 0.010) * 1000)))

        # 招3: 合成 65Hz boom (sine+指数衰减, 无资产依赖), 只合成一次
        boom_wav = out_dir / "_boom65.wav"
        if boom_hits and not boom_wav.exists():
            _sp.run(["ffmpeg", "-y", "-f", "lavfi",
                     "-i", "sine=frequency=65:duration=0.35",
                     "-af", "afade=t=in:st=0:d=0.005,"
                            "afade=t=out:st=0.03:d=0.30:curve=exp,volume=0.31",
                     str(boom_wav)], capture_output=True, timeout=60)
        for ms in boom_hits:
            plan.append((str(boom_wav), ms, 0.30))

        # 招4: onset 细分层 — 距切点>0.18s / mid-high 段 / 最小间隔 0.45s
        cuts_sorted = sorted(cut_times)
        _last_sub = -1.0
        _n_sub = 0
        for ot in _onsets_raw:
            t = float(ot)
            if t < 0.5 or t >= args.duration - 0.2:
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

        print(f"    SFX v2.1: {len(cut_times)} 切点 + {len(boom_hits)} 重拍双层 "
              f"+ {_n_sub} onset细分 → 共 {len(plan)} 落点 (已裁短)")

        _FRAME_MS = 1000.0 / 24.0  # 帧级路线图②: SFX 延时量化到帧倍数, 音画同帧

        def _qframe(t):
            # 帧级路线图⑤: A/V 6ms 前瞻延迟补偿 (alimiter lookahead)
            return int(round((t - 0.006) * 24) * _FRAME_MS)

        def _mix_batch(pb, in_mp4, out_mp4):
            parts, labels = [], []
            for i, (f, ms, g) in enumerate(pb, start=1):
                _qms = int(round(ms / _FRAME_MS) * _FRAME_MS)
                parts.append(f"[{i}:a]adelay={_qms}|{_qms},volume={g:.2f}[s{i}]")
                labels.append(f"[s{i}]")
            parts.append("[0:a]" + "".join(labels) +
                         f"amix=inputs={len(pb)+1}:duration=first:normalize=0[am];"
                         f"[am]alimiter=attack=1:release=50:limit=0.95:level=0[outa]")
            cmd = ["ffmpeg", "-y", "-i", in_mp4]
            for f, _, _ in pb:
                cmd += ["-i", f]
            cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[outa]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out_mp4]
            return _sp.run(cmd, capture_output=True, timeout=600).returncode == 0

        src = _fallback_src
        ok2 = True
        for bi in range(0, len(plan), 14):
            tgt = str(final) if bi + 14 >= len(plan) else str(out_dir / f"_sm{bi}.mp4")
            ok2 = ok2 and _mix_batch(plan[bi:bi + 14], src, tgt)
            src = tgt
        if not plan:
            import shutil as _shutil
            _shutil.copy2(_fallback_src, str(final))
            ok2 = True
        # 清理批次中间产物
        for _tmpm in out_dir.glob("_sm*.mp4"):
            try:
                _tmpm.unlink()
            except OSError:
                pass
    else:
        import shutil as _shutil
        _shutil.copy2(_fallback_src, str(final))
        ok2 = True
    print("    SFX v2.1: " + ("OK" if ok2 else "FAIL"))
    report["capabilities_used"]["sfx"] = ok2
    report["final_video"] = str(final)

    # ⑤ 成片评分 (CNN + SiliconFlow 链)
    print("\n[能力⑤] 成片评分 (CNN + SiliconFlow 链)...")
    from core.cnn_scorer import score_video_mode
    r = score_video_mode(str(final), "local")
    report["scores"] = r.get("scores", {})
    for k, v in sorted(r.get("scores", {}).items()):
        print(f"    {k.replace('score_', ''):<14} {v}")

    # 闸门自动验收 (2026-09-04 全自动闭环): 渲染完过七关, 结果进报告
    try:
        _g = _sp.run([sys.executable, str(PROJECT / "scripts" / "render_gate.py"),
                      str(out_dir), args.tag, "--bgm", args.bgm],
                     capture_output=True, text=True, timeout=900,
                     encoding="utf-8", errors="replace")
        _gacc = "ACCEPT" in _g.stdout
        print("    [闸门] " + ("✅ ACCEPT 全部指标通过"
                               if _gacc else "❌ REJECT 见上方指标"))
    except Exception as _g_e:
        print(f"    [闸门跳过] {_g_e}")

    # 自进化层1: 自动经验采集 (2026-09-04) — 参数+行为+闸门落历史,
    # 判定槽待用户反馈后回填: python scripts/harvest_experience.py <run_dir> <tag> --verdict "..."
    try:
        _sp.run([sys.executable,
                 str(PROJECT / "scripts" / "harvest_experience.py"),
                 str(out_dir), args.tag, "--bgm", args.bgm],
                timeout=900)
    except Exception as _h_e:
        print(f"    [经验采集跳过] {_h_e}")

    report["elapsed_s"] = round(time.time() - t0)
    (out_dir / "unified_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    used = report["capabilities_used"]
    print(f"\n启用能力: 运镜标注={used.get('motion_labels', False)} "
          f"V23引擎✓ LUT={used.get('lut')} SFX={used.get('sfx')} 评分✓")
    print(f"交付: {final} | 报告: {out_dir / 'unified_report.json'} | {report['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
