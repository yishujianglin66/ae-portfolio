# -*- coding: utf-8 -*-
"""
Resolve→AE→Resolve 混合工作流端到端验证

    T1 管线加载
    T2 AE Bridge 在线探测（离线自动降级 FFmpeg，不算失败）
    T3 端到端渲染（冰海战记素材 + 素材库 BGM）
    T4 成片校验（ffprobe 音视频双流、时长、非黑屏）
    T5 成片切点-节拍偏差量化（复用 measure_sync_quality）

输出：output/hybrid_pipeline/hybrid_final.mp4
"""
import os
import re
import shlex
import subprocess
import sys

import pytest
pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve + 真实素材/BGM 环境

ROOT = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
sys.path.insert(0, os.path.join(ROOT, "integrations"))
sys.path.insert(0, os.path.join(ROOT, "vrs"))

OUT_DIR = os.path.join(ROOT, "output", "hybrid_pipeline")
BGM = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
CLIPS_DIR = r"C:\VinlandClips"
FINAL = os.path.join(OUT_DIR, "hybrid_final.mp4")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def probe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def has_stream(path, sel):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", sel,
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", path],
        capture_output=True, text=True, timeout=60)
    return bool(r.stdout.strip())


def yavg(path):
    """signalstats 平均亮度（黑屏判定：<20）；需 metadata=print 才输出数值"""
    r = subprocess.run(
        ["ffmpeg", "-i", path, "-vf", "signalstats,metadata=print",
         "-f", "null", "-"],
        capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=300)
    vals = [float(v) for v in re.findall(r'signalstats\.YAVG=(\d+(?:\.\d+)?)', r.stderr)]
    return sum(vals) / len(vals) if vals else None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # ---------- T1 加载 ----------
    try:
        from resolve_ae_resolve_pipeline import ResolveAeResolvePipeline
        pipe = ResolveAeResolvePipeline()
        check("T1 混合管线加载", True, "")
    except Exception as e:
        check("T1 混合管线加载", False, str(e))
        return 1

    # ---------- T2 AE 在线探测（信息性）----------
    try:
        online = pipe.ae.is_online(timeout=8)
        check("T2 AE Bridge 探测", True,
              f"online={online} ({'AE路径' if online else 'FFmpeg降级路径'})")
    except Exception as e:
        check("T2 AE Bridge 探测", False, str(e))

    # ---------- T3 端到端 ----------
    try:
        exts = {'.mp4', '.mov', '.mkv'}
        clips = sorted(os.path.join(CLIPS_DIR, f) for f in os.listdir(CLIPS_DIR)
                       if os.path.splitext(f)[1].lower() in exts)
        durs = []
        for c in clips:
            d = probe_duration(c)
            if d:
                durs.append((d, c))
        durs.sort(reverse=True)
        clips = [c for _, c in durs[:6]]

        lut = os.path.join(ROOT, "output", "phase3_showcase", "teal_orange.cube")
        out = pipe.run(
            clips, BGM, FINAL,
            title="冰海战记", subtitle="VINLAND SAGA · AMV",
            beat_group=4,
            transitions=["whip_pan", "glitch", "flash", "zoom"],
            lut_path=lut if os.path.exists(lut) else None)
        rep = pipe.last_report
        check("T3 端到端渲染", True,
              f"dur={rep['duration']:.1f}s ae_used={rep['ae_used']} "
              f"elapsed={rep['elapsed_s']}s")
    except Exception as e:
        import traceback
        traceback.print_exc()
        check("T3 端到端渲染", False, str(e))
        return 1

    # ---------- T4 成片校验 ----------
    try:
        dur = probe_duration(FINAL)
        hv, ha = has_stream(FINAL, "v"), has_stream(FINAL, "a")
        size_mb = os.path.getsize(FINAL) / 1024 / 1024
        yv = yavg(FINAL)
        ok = (dur and dur > 5.0 and hv and ha and size_mb > 1.0
              and yv is not None and yv >= 20)
        check("T4 成片校验", ok,
              f"dur={dur:.1f}s v={hv} a={ha} {size_mb:.1f}MB YAVG={yv:.1f}"
              if yv else f"dur={dur} v={hv} a={ha}")
    except Exception as e:
        check("T4 成片校验", False, str(e))

    # ---------- T5 切点偏差量化 ----------
    try:
        beats = pipe.vrs.last_analysis["beats"]
        q = pipe.vrs.measure_sync_quality(FINAL, beats)
        ok = q["cuts"] >= 3 and q["avg_dev_ms"] < 200.0
        check("T5 切点偏差指标", ok,
              f"cuts={q['cuts']} avg={q['avg_dev_ms']}ms max={q['max_dev_ms']}ms "
              f"on_beat={q['on_beat_rate']:.0%}")
    except Exception as e:
        check("T5 切点偏差指标", False, str(e))

    # ---------- 汇总 ----------
    print("\n========== 混合工作流验证汇总 ==========")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for name, ok, detail in RESULTS:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"总计: {passed}/{len(RESULTS)}")
    print(f"Status: {'PASS' if passed == len(RESULTS) else 'FAIL'}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
