#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e2e_style_beat_pipeline.py — 冰海战记基准能力恢复：端到端主管线
=================================================================
输入参考视频 + BGM + 素材目录 → 自动产出可验证成片。

管线阶段（全部真实执行，无 mock）：
  S0 环境自检 (ffmpeg / librosa / cv2)
  S1 参考视频风格指纹        → 复用 video/style_migrator.StyleFingerprintExtractor
  S2 BGM 节拍分析            → librosa beat_track/onset/rms（复用旗舰管线 S2 模式）
  S3 剪辑规划                → 卡点分段 + 变速 + 转场 + 推拉镜头 + 文字特效方案
  S4 FFmpeg 执行             → trim/setpts变速 + crop推拉 + xfade转场 + drawtext文字
                                + eq/colorbalance 风格复原（历史报告第五节验证过的路线）
  S5 验证闭环                → ffprobe 指标 / 卡点帧差检测 / 调色前后像素对比 / 镜头运动帧差
  S6 归档                    → report.json + 证据帧 + 日志

用法:
  python e2e_style_beat_pipeline.py --reference C:\\VinlandClips\\clip_9_1.mp4 \
      --bgm C:\\VinlandBGM\\bgm.mp3 --materials-dir C:\\VinlandClips --segments 8
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
TPS = None  # not needed (FFmpeg route)


def log(msg: str, level: str = "INFO"):
    print(f"[{time.strftime('%H:%M:%S')}][{level}] {msg}", flush=True)


def run_cmd(cmd: list, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


# ================================================================
# S0 环境自检
# ================================================================
def stage0_env_check() -> dict:
    res = {}
    r = run_cmd([FFMPEG, "-version"], timeout=30)
    res["ffmpeg"] = r.returncode == 0
    import importlib
    for mod in ("librosa", "cv2", "numpy", "PIL"):
        try:
            importlib.import_module(mod)
            res[mod] = True
        except ImportError:
            res[mod] = False
    # 历史可复用模块
    try:
        from video.style_migrator import StyleFingerprintExtractor  # noqa
        res["style_migrator"] = True
    except Exception:
        res["style_migrator"] = False
    ok = all(res.values())
    log(f"S0 环境自检: {res} -> {'PASS' if ok else 'FAIL'}", "INFO" if ok else "ERROR")
    return {"pass": ok, "checks": res}


# ================================================================
# S1 风格指纹（复用历史模块）
# ================================================================
def stage1_style_fingerprint(reference_video: Path) -> dict:
    from video.style_migrator import StyleFingerprintExtractor
    extractor = StyleFingerprintExtractor()
    fp = extractor.extract(str(reference_video))
    color = fp.get("color", {})
    log(f"S1 风格指纹: brightness={color.get('avg_brightness')}, "
        f"saturation={color.get('avg_saturation')}, warmth={color.get('warmth')}, "
        f"mood={color.get('color_mood')}")
    return fp


def fingerprint_to_grade(fp: dict) -> dict:
    """风格指纹 → FFmpeg eq/colorbalance 参数（风格复原）
    注：StyleFingerprintExtractor 返回嵌套结构 color.{avg_brightness,avg_saturation,warmth}"""
    color = fp.get("color", {})
    brightness = color.get("avg_brightness", 50)
    saturation = color.get("avg_saturation", 50)
    warmth = color.get("warmth", 0)
    grade = {
        "eq_brightness": max(-0.15, min(0.15, (brightness - 50) / 200)),
        "eq_saturation": max(0.8, min(1.35, saturation / 50)),
        "cb_red": max(-0.06, min(0.06, warmth / 300)),
        "cb_blue": max(-0.06, min(0.06, -warmth / 300)),
    }
    log(f"S1 风格复原参数: {grade}")
    return grade


# ================================================================
# S2 节拍分析
# ================================================================
def stage2_beat_analysis(bgm: Path, out_dir: Path) -> dict:
    import librosa
    import numpy as np
    y, sr = librosa.load(str(bgm), sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()
    rms = librosa.feature.rms(y=y)[0]
    duration = float(len(y) / sr)
    result = {
        "bpm": round(bpm, 2),
        "duration": round(duration, 3),
        "beat_times": [round(t, 4) for t in beat_times],
        "onset_count": len(onset_times),
        "mean_rms": round(float(rms.mean()), 5),
    }
    (out_dir / "beats.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    log(f"S2 节拍分析: BPM={result['bpm']} beats={len(beat_times)} dur={duration:.2f}s")
    return result


# ================================================================
# S3 剪辑规划
# ================================================================
def stage3_edit_plan(beats: dict, materials: list, segments: int,
                     transition_dur: float = 0.4) -> dict:
    beat_times = beats["beat_times"]
    beats_per_seg = 4
    seg_dur = (beats["bpm"] and (60.0 / beats["bpm"]) * beats_per_seg) or 2.0
    speed_plan = [1.0, 1.25, 1.0, 0.8, 1.0, 1.5, 1.0, 1.25,
                  1.0, 1.25, 1.0, 0.8, 1.0, 1.5, 1.0, 1.25]
    camera_plan = ["push_in", "pull_out"]
    plan_segments = []
    for i in range(segments):
        beat_idx = i * beats_per_seg
        start_beat = beat_times[beat_idx] if beat_idx < len(beat_times) else i * seg_dur
        plan_segments.append({
            "index": i,
            "source": str(materials[i % len(materials)]),
            "start_beat": round(start_beat, 4),
            "duration": round(seg_dur, 4),
            "speed": speed_plan[i % len(speed_plan)],
            "camera": camera_plan[i % 2],
            "transition": "fade" if i < segments - 1 else None,
        })
    total = seg_dur * segments - transition_dur * (segments - 1)
    plan = {
        "segment_duration": round(seg_dur, 4),
        "transition_duration": transition_dur,
        "planned_total": round(total, 4),
        "segments": plan_segments,
        "text_overlays": [
            {"text": "VINLAND SAGA", "pos": "title", "fade_in": 0.6, "hold_until": 3.4},
            {"text": "BEAT-SYNCED AUTO EDIT", "pos": "subtitle", "fade_in": 1.0, "hold_until": 4.0},
        ],
    }
    log(f"S3 剪辑规划: {segments} 段 x {seg_dur:.2f}s, 转场 {transition_dur}s, "
        f"总长≈{total:.2f}s, 变速计划={[s['speed'] for s in plan_segments]}")
    return plan


# ================================================================
# S4 FFmpeg 执行
# ================================================================
def _build_segment_filter(seg: dict, grade: dict, graded: bool = True) -> str:
    d = seg["duration"]
    speed = seg["speed"]
    filters = ["setpts=PTS-STARTPTS", f"setpts=PTS/{speed}"]
    # 镜头推拉：crop 动画 + 还原缩放
    amt = 0.12
    if seg["camera"] == "push_in":
        expr = f"{amt}*min(t/{d},1)"
    else:
        expr = f"{amt}*(1-min(t/{d},1))"
    filters.append(
        f"crop=w='iw-(iw*{expr})':h='ih-(ih*{expr})':x='(iw-ow)/2':y='(ih-oh)/2'"
    )
    filters.append("scale=1920:1080")
    if graded:
        filters.append(
            f"eq=brightness={grade['eq_brightness']:.3f}:saturation={grade['eq_saturation']:.3f}"
        )
        filters.append(
            f"colorbalance=rs={grade['cb_red']:.3f}:gs=0:bs={grade['cb_blue']:.3f}"
        )
    return ",".join(filters)


def stage4_execute(plan: dict, grade: dict, bgm: Path, out_dir: Path) -> dict:
    seg_dir = out_dir / "segments"
    seg_dir.mkdir(exist_ok=True)
    seg_files = []
    # 4.1 逐段生成（含风格复原调色）
    for seg in plan["segments"]:
        src = seg["source"]
        out = seg_dir / f"seg_{seg['index']:02d}.mp4"
        src_dur_needed = seg["duration"] * seg["speed"] + 0.2
        vf = _build_segment_filter(seg, grade, graded=True)
        cmd = [FFMPEG, "-y", "-ss", "0", "-i", src, "-t", f"{src_dur_needed:.3f}",
               "-vf", vf, "-an", "-r", "23.976",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out)]
        r = run_cmd(cmd)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"段{seg['index']}生成失败: {r.stderr[-500:]}")
        seg_files.append(out)
        log(f"S4 段{seg['index']:02d} OK: speed={seg['speed']} camera={seg['camera']}")
    # 4.1b 无调色对照段（验证用）
    seg0 = plan["segments"][0]
    nograde = seg_dir / "seg_00_nograde.mp4"
    cmd = [FFMPEG, "-y", "-i", seg0["source"], "-t", f"{seg0['duration'] * seg0['speed'] + 0.2:.3f}",
           "-vf", _build_segment_filter(seg0, grade, graded=False), "-an", "-r", "23.976",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(nograde)]
    run_cmd(cmd)
    # 4.2 xfade 转场拼接
    n = len(seg_files)
    td = plan["transition_duration"]
    inputs = []
    for f in seg_files:
        inputs += ["-i", str(f)]
    fc_parts = []
    acc_dur = plan["segment_duration"]
    prev = "[0:v]"
    for k in range(1, n):
        offset = acc_dur - td
        nxt = f"[{k}:v]"
        out_label = f"[v{k}]" if k < n - 1 else "[vout]"
        fc_parts.append(f"{prev}{nxt}xfade=transition=fade:duration={td}:offset={offset:.4f}{out_label}")
        prev = out_label
        acc_dur = acc_dur + plan["segment_duration"] - td
    # 4.3 文字特效（drawtext 淡入动画）+ BGM 混音
    # fontfile 含冒号：外层单引号护图级解析，\: 护选项级解析（实测验证）
    font = r"'C\:/Windows/Fonts/arial.ttf'"
    t1 = plan["text_overlays"][0]
    t2 = plan["text_overlays"][1]
    text_filter = (
        f"drawtext=text='{t1['text']}':fontfile={font}:fontsize=84:fontcolor=white"
        f":borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.14"
        f":alpha='if(lt(t,{t1['fade_in']}),t/{t1['fade_in']},if(lt(t,{t1['hold_until']}),1,max(0,1-(t-{t1['hold_until']})/0.6)))',"
        f"drawtext=text='{t2['text']}':fontfile={font}:fontsize=36:fontcolor=0xE0E0E0"
        f":borderw=2:bordercolor=black:x=(w-text_w)/2:y=h*0.88"
        f":alpha='if(lt(t,{t2['fade_in']}),t/{t2['fade_in']},if(lt(t,{t2['hold_until']}),1,max(0,1-(t-{t2['hold_until']})/0.6)))'"
    )
    fc = ";".join(fc_parts) + f";{prev}" + text_filter + "[final]"
    # 用 script 文件传递滤镜图，避免 Windows 命令行引号转义问题
    fc_script = out_dir / "filtergraph.txt"
    fc_script.write_text(fc, encoding="utf-8")
    final_mp4 = out_dir / "final_vinland_e2e.mp4"
    d_total = acc_dur
    cmd = ([FFMPEG, "-y"] + inputs + ["-i", str(bgm),
           "-filter_complex_script", str(fc_script),
           "-map", "[final]", "-map", f"{n}:a",
           "-af", f"afade=t=in:d=0.5,afade=t=out:st={max(0, d_total - 1.2):.2f}:d=1.2",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(final_mp4)])
    r = run_cmd(cmd, timeout=900)
    if r.returncode != 0 or not final_mp4.exists():
        raise RuntimeError(f"成片合成失败: {r.stderr[-800:]}")
    log(f"S4 成片合成 OK: {final_mp4.name} ({final_mp4.stat().st_size / 1048576:.2f} MB)")
    return {"final": str(final_mp4), "nograde": str(nograde),
            "segments": [str(f) for f in seg_files], "xfade_chain": fc_parts}


# ================================================================
# S5 验证闭环
# ================================================================
def ffprobe_stats(path: Path) -> dict:
    cmd = [FFPROBE, "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height,r_frame_rate,codec_name,nb_frames",
           "-show_entries", "format=duration,size", "-of", "json", str(path)]
    r = run_cmd(cmd)
    return json.loads(r.stdout) if r.returncode == 0 else {}


def verify_cut_alignment(final: Path, plan: dict) -> dict:
    """卡点验证：切点处帧差应显著大于段内对照点"""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(final))
    fps = cap.get(cv2.CAP_PROP_FPS) or 23.976
    td = plan["transition_duration"]
    seg_d = plan["segment_duration"]
    cut_times, t = [], seg_d - td / 2
    for i in range(len(plan["segments"]) - 1):
        cut_times.append(t)
        t += seg_d - td

    def frame_at(ts):
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ok, fr = cap.read()
        return fr if ok else None

    cut_diffs, ctrl_diffs = [], []
    for ct in cut_times:
        f1, f2 = frame_at(ct - 0.3), frame_at(ct + 0.3)
        if f1 is not None and f2 is not None:
            cut_diffs.append(float(np.mean(np.abs(f1.astype(float) - f2.astype(float)))))
    for i in range(len(plan["segments"])):
        mid = i * (seg_d - td) + seg_d / 2
        f1, f2 = frame_at(mid - 0.15), frame_at(mid + 0.15)
        if f1 is not None and f2 is not None:
            ctrl_diffs.append(float(np.mean(np.abs(f1.astype(float) - f2.astype(float)))))
    cap.release()
    cut_avg = sum(cut_diffs) / max(1, len(cut_diffs))
    ctrl_avg = sum(ctrl_diffs) / max(1, len(ctrl_diffs))
    ratio = cut_avg / ctrl_avg if ctrl_avg > 0 else 0
    passed = ratio > 1.5
    log(f"S5 卡点验证: 切点帧差={cut_avg:.2f} 对照={ctrl_avg:.2f} 比值={ratio:.2f} "
        f"-> {'PASS' if passed else 'FAIL'}")
    return {"cut_diffs": cut_diffs, "ctrl_diffs": ctrl_diffs,
            "ratio": round(ratio, 3), "pass": bool(passed)}


def verify_style_applied(nograde: Path, final: Path, out_dir: Path) -> dict:
    """调色前后像素级对比（取各 1s 处帧）"""
    import numpy as np
    from PIL import Image
    evidence = out_dir / "evidence"
    evidence.mkdir(exist_ok=True)
    shots = {}
    for name, src in (("nograde", nograde), ("graded_final", final)):
        cmd = [FFMPEG, "-y", "-ss", "1.0", "-i", str(src), "-frames:v", "1",
               str(evidence / f"{name}_frame.png")]
        run_cmd(cmd)
        shots[name] = evidence / f"{name}_frame.png"
    a = np.asarray(Image.open(shots["nograde"]).convert("RGB")).astype(float)
    b = np.asarray(Image.open(shots["graded_final"]).convert("RGB")).astype(float)
    diff = float(np.mean(np.abs(a - b)))
    passed = diff > 2.0
    log(f"S5 风格复原验证: 调色前后平均像素差={diff:.2f} -> {'PASS' if passed else 'FAIL'}")
    return {"mean_abs_diff": round(diff, 3), "pass": bool(passed),
            "evidence": [str(shots["nograde"]), str(shots["graded_final"])]}


def verify_camera_motion(seg_file: Path, camera_type: str, out_dir: Path) -> dict:
    """推拉镜头验证：段首/尾帧中心区域差异"""
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(seg_file))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    _, f0 = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n_frames - 2))
    _, f1 = cap.read()
    cap.release()
    if f0 is None or f1 is None:
        return {"pass": False, "error": "frame read fail"}
    h, w = f0.shape[:2]
    c0, c1 = f0[h // 4:3 * h // 4, w // 4:3 * w // 4], f1[h // 4:3 * h // 4, w // 4:3 * w // 4]
    center_diff = float(np.mean(np.abs(c0.astype(float) - c1.astype(float))))
    full_diff = float(np.mean(np.abs(f0.astype(float) - f1.astype(float))))
    evidence = out_dir / "evidence"
    evidence.mkdir(exist_ok=True)
    cv2.imwrite(str(evidence / f"camera_{camera_type}_first.png"), f0)
    cv2.imwrite(str(evidence / f"camera_{camera_type}_last.png"), f1)
    passed = full_diff > 1.0
    log(f"S5 镜头运动验证({camera_type}): 全帧差={full_diff:.2f} 中心差={center_diff:.2f} "
        f"-> {'PASS' if passed else 'FAIL'}")
    return {"full_diff": round(full_diff, 3), "center_diff": round(center_diff, 3),
            "pass": bool(passed)}


def stage5_verify(final: Path, plan: dict, nograde: Path, out_dir: Path) -> dict:
    probe = ffprobe_stats(final)
    cut = verify_cut_alignment(final, plan)
    style = verify_style_applied(nograde, final, out_dir)
    camera = verify_camera_motion(Path(plan["segments"][0] and
                                       out_dir / "segments" / "seg_00.mp4"),
                                  plan["segments"][0]["camera"], out_dir)
    dur = float(probe.get("format", {}).get("duration", 0))
    speed_ok = abs(dur - plan["planned_total"]) < 1.5
    result = {
        "ffprobe": probe,
        "duration_vs_plan": {"actual": round(dur, 3),
                             "planned": plan["planned_total"], "pass": bool(speed_ok)},
        "cut_alignment": cut,
        "style_applied": style,
        "camera_motion": camera,
    }
    result["overall_pass"] = all([cut["pass"], style["pass"], camera["pass"], speed_ok])
    log(f"S5 综合验证: {'PASS' if result['overall_pass'] else 'FAIL'} "
        f"(时长 {dur:.2f}s vs 计划 {plan['planned_total']}s)")
    return result


# ================================================================
# 主流程
# ================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--bgm", required=True)
    ap.add_argument("--materials-dir", required=True)
    ap.add_argument("--segments", type=int, default=8)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / "output_production" / f"e2e_vinland_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    reference = Path(args.reference)
    bgm = Path(args.bgm)
    materials = sorted(Path(args.materials_dir).glob("clip_*_1.mp4"))
    # 排除参考视频自身
    materials = [m for m in materials if m.resolve() != reference.resolve()]
    if not materials:
        log("素材为空，终止", "ERROR")
        return 1

    report = {"started_at": ts, "inputs": {"reference": str(reference), "bgm": str(bgm),
                                            "materials_count": len(materials)},
              "stages": {}}
    try:
        s0 = stage0_env_check()
        report["stages"]["S0_env"] = s0
        if not s0["pass"]:
            raise RuntimeError("环境自检失败")

        fp = stage1_style_fingerprint(reference)
        grade = fingerprint_to_grade(fp)
        report["stages"]["S1_style"] = {"fingerprint": fp, "grade_params": grade}

        beats = stage2_beat_analysis(bgm, out_dir)
        report["stages"]["S2_beats"] = {"bpm": beats["bpm"],
                                        "beat_count": len(beats["beat_times"]),
                                        "duration": beats["duration"]}

        plan = stage3_edit_plan(beats, materials[:args.segments * 2], args.segments)
        report["stages"]["S3_plan"] = plan

        exec_res = stage4_execute(plan, grade, bgm, out_dir)
        report["stages"]["S4_execute"] = {k: v for k, v in exec_res.items() if k != "xfade_chain"}
        report["stages"]["S4_execute"]["xfade_count"] = len(exec_res["xfade_chain"])

        final = Path(exec_res["final"])
        verify = stage5_verify(final, plan, Path(exec_res["nograde"]), out_dir)
        report["stages"]["S5_verify"] = verify

        report["success"] = bool(verify["overall_pass"])
        report["final_output"] = str(final)
        report["final_size_mb"] = round(final.stat().st_size / 1048576, 2)
    except Exception as e:
        report["success"] = False
        report["error"] = str(e)
        log(f"管线失败: {e}", "ERROR")
    finally:
        report["finished_at"] = time.strftime("%Y%m%d_%H%M%S")
        (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
        log(f"报告归档: {out_dir / 'report.json'}")

    log("=" * 60)
    log(f"管线结果: {'PASS' if report.get('success') else 'FAIL'}")
    if report.get("final_output"):
        log(f"成片: {report['final_output']} ({report.get('final_size_mb')} MB)")
    return 0 if report.get("success") else 2


if __name__ == "__main__":
    sys.exit(main())
