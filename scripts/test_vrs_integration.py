# -*- coding: utf-8 -*-
"""
P0 集成验证：VRS AudioSyncAnalyzer ↔ resolve_engine 桥接端到端测试

测试内容：
    T1 桥接模块加载与降级路径
    T2 VRS 音频分析（ae实战音乐.mp3）节拍/能量提取
    T3 vrs_keyframes_to_engine 转换正确性
    T4 beat_pulse_expression 表达式构建
    T5 build_vrs_montage 端到端渲染（冰海战记素材 + 素材库BGM，
       ffprobe 验证 >5s、音视频双流）

输出：output/vrs_integration/vrs_montage.mp4
"""
import os
import shlex
import subprocess
import sys

ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
sys.path.insert(0, os.path.join(ROOT, "integrations"))
sys.path.insert(0, os.path.join(ROOT, "vrs"))

OUT_DIR = os.path.join(ROOT, "output", "vrs_integration")
BGM = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
CLIPS_DIR = r"C:\VinlandClips"
FINAL = os.path.join(OUT_DIR, "vrs_montage.mp4")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def probe(path):
    """ffprobe: 返回 (duration, streams)，分开查询避免混合条目输出异常"""
    dur = None
    r0 = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=60)
    try:
        dur = float(r0.stdout.strip())
    except ValueError:
        pass
    streams = []
    for sel, entries in (("v", "codec_name,width,height"),
                         ("a", "codec_name,sample_rate")):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", sel,
             "-show_entries", f"stream={entries}", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=60)
        for l in r.stdout.strip().splitlines():
            if l:
                streams.append(("video" if sel == "v" else "audio",) + tuple(l.split(",")))
    return dur, streams


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------- T1 加载 ----------
    try:
        from vrs_resolve_bridge import VrsResolveBridge, Keyframe, TransitionConfig
        bridge = VrsResolveBridge()
        check("T1 桥接模块加载", True, f"use_vrs={bridge.use_vrs}")
    except Exception as e:
        check("T1 桥接模块加载", False, str(e))
        return 1

    # ---------- T2 VRS 音频分析 ----------
    try:
        analysis = bridge.analyze(BGM)
        ok = (analysis["success"] and len(analysis["beats"]) >= 8
              and analysis["bpm"] > 50)
        check("T2 VRS 音频分析", ok,
              f"source={analysis['source']} bpm={analysis['bpm']:.1f} "
              f"beats={len(analysis['beats'])} "
              f"energy_pts={len(analysis['energy_curve'])} "
              f"effects={len(analysis['beat_driven_effects'])}")
        if not ok:
            return 1
    except Exception as e:
        check("T2 VRS 音频分析", False, str(e))
        return 1

    # ---------- T3 关键帧转换 ----------
    try:
        sync_kfs = analysis["sync_keyframes"]
        zoom_kfs = bridge.vrs_keyframes_to_engine(sync_kfs, prop="scale")
        ok = len(zoom_kfs) >= 3 and all(isinstance(k, Keyframe) for k in zoom_kfs[:5])
        check("T3 sync_keyframes 转换", ok,
              f"vrs={len(sync_kfs)} -> engine_zoom={len(zoom_kfs)}")
    except Exception as e:
        check("T3 sync_keyframes 转换", False, str(e))

    # ---------- T4 脉冲表达式 ----------
    try:
        beats = analysis["beats"]
        expr = bridge.build_beat_pulse_expression(
            [b - beats[0] for b in beats[:6]], beats[5] - beats[0])
        ok = expr is not None and "on/24" in expr and expr.count("if(") >= 2
        check("T4 beat_pulse 表达式", ok,
              f"len={len(expr) if expr else 0} ifs={expr.count('if(') if expr else 0}")
        # 超限保护
        many = bridge.build_beat_pulse_expression(list(range(50)), 50.0)
        check("T4b 脉冲数上限保护", many is None, "超过7拍返回None" if many is None else "异常")
    except Exception as e:
        check("T4 beat_pulse 表达式", False, str(e))

    # ---------- T5 端到端渲染 ----------
    try:
        exts = {'.mp4', '.mov', '.mkv'}
        clips = sorted(os.path.join(CLIPS_DIR, f) for f in os.listdir(CLIPS_DIR)
                       if os.path.splitext(f)[1].lower() in exts)
        # 按时长选最长的 6 个，保证素材充足
        durs = []
        for c in clips:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", c],
                capture_output=True, text=True, timeout=30)
            try:
                durs.append((float(r.stdout.strip()), c))
            except ValueError:
                pass
        durs.sort(reverse=True)
        clips = [c for _, c in durs[:6]]
        print(f"[INFO] 选用素材 {len(clips)} 个: "
              f"{[os.path.basename(c) for c in clips]}")

        lut = os.path.join(ROOT, "output", "phase3_showcase", "teal_orange.cube")
        out = bridge.build_vrs_montage(
            clips, BGM, FINAL,
            beat_group=2,
            transitions=["whip_pan", "glitch", "flash", "zoom"],
            lut_path=lut if os.path.exists(lut) else None,
            enable_flash=True, enable_bounce=True)

        dur, streams = probe(out)
        has_v = any(s[0] == "video" for s in streams)
        has_a = any(s[0] == "audio" for s in streams)
        size_mb = os.path.getsize(out) / 1024 / 1024
        ok = (dur is not None and dur > 5.0 and has_v and has_a and size_mb > 1.0)
        check("T5 VRS 混剪端到端", ok,
              f"dur={dur:.1f}s size={size_mb:.1f}MB "
              f"streams={streams}")

        # ---------- T6 xfade 重叠补偿：成片时长应≈节拍总时长 ----------
        beats = bridge.last_analysis["beats"]
        beat_group = 2
        cut_beats = beats[::beat_group]
        bounds = [0.0] + list(cut_beats)
        shot_bounds = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)
                       if bounds[i + 1] - bounds[i] >= 0.3]
        expected_dur = shot_bounds[-1][1]
        drift = abs(dur - expected_dur) if dur else 99.0
        ok6 = drift < 0.7
        check("T6 xfade 时长补偿", ok6,
              f"expected≈{expected_dur:.1f}s actual={dur:.1f}s drift={drift:.2f}s")

        # ---------- T7 切点-节拍偏差量化 ----------
        q = bridge.measure_sync_quality(out, beats)
        ok7 = (q["cuts"] >= 5 and q["avg_dev_ms"] < 150.0
               and q["on_beat_rate"] >= 0.5)
        check("T7 切点偏差指标", ok7,
              f"cuts={q['cuts']} avg={q['avg_dev_ms']}ms max={q['max_dev_ms']}ms "
              f"on_beat={q['on_beat_rate']:.0%}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("T5 VRS 混剪端到端", False, str(e))

    # ---------- 汇总 ----------
    print("\n========== P0 集成验证汇总 ==========")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"总计: {passed}/{len(RESULTS)}")
    print(f"Status: {'PASS' if passed == len(RESULTS) else 'FAIL'}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
