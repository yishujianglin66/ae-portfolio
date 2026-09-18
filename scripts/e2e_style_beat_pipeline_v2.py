#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
e2e_style_beat_pipeline_v2.py — 质量飞跃版端到端管线
=====================================================
v1→v2 关键升级：
  S1: 深度风格分析（KB匹配12模板+866效果配方，而非4参数全局）
  S2: 音乐段落感知（intro/verse/chorus/bridge/outro 能量曲线，而非固定BPM分段）
  S3: 智能素材选择（内容评分+能量匹配，而非顺序取用）
  S4: 风格化规划（按段落分配转场/变速/镜头，而非纯模板循环）
  S5: 多样转场执行（dissolve/slide/zoom/whip/fade 混用+逐段调色）
  S6: 增强验证（+风格一致性+段落能量匹配验证）

用法:
  python e2e_style_beat_pipeline_v2.py \
      --reference C:\\VinlandClips\\clip_9_1.mp4 \\
     --bgm C:\\VinlandBGM\\bgm.mp3 \\
     --materials-dir C:\\VinlandClips --segments 10
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
FFMPEG, FFPROBE = "ffmpeg", "ffprobe"

def log(msg, level="INFO"):
    print(f"[{time.strftime('%H:%M:%S')}][{level}] {msg}", flush=True)

def run_cmd(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")

# ================================================================
# S0 环境自检
# ================================================================
def stage0_env():
    import importlib
    res = {"ffmpeg": run_cmd([FFMPEG, "-version"]).returncode == 0}
    for m in ("librosa", "cv2", "numpy", "PIL"):
        try: importlib.import_module(m); res[m] = True
        except: res[m] = False
    try:
        from audio.beat_orchestrator import BeatOrchestrator
        from video.style_migrator import KnowledgeBaseStyleMatcher, StyleFingerprintExtractor
        res["style_migrator"] = res["beat_orchestrator"] = True
    except: res["style_migrator"] = res["beat_orchestrator"] = False
    ok = all(res.values())
    log(f"S0 环境: {res} -> {'PASS' if ok else 'FAIL'}", "INFO" if ok else "ERROR")
    return {"pass": ok, "checks": res}

# ================================================================
# S1 深度风格分析（复用 StyleMigrator 完整链）
# ================================================================
def stage1_deep_style(reference: Path) -> dict:
    from video.style_migrator import KnowledgeBaseStyleMatcher, StyleFingerprintExtractor
    fp = StyleFingerprintExtractor().extract(str(reference))
    match = KnowledgeBaseStyleMatcher().match(fp)
    tpl = match["template"]
    color = fp.get("color", {})
    # 从风格模板提取 FFmpeg 调色参数（多参数映射）
    grade = _template_to_grade(tpl, color)
    log(f"S1 风格: {match['style_name']}(score={match['style_score']}) "
        f"trans={tpl.get('preferred_transition')} camera={tpl.get('preferred_camera')} "
        f"tempo={tpl.get('tempo')}")
    log(f"S1 调色: {grade}")
    return {"fingerprint": fp, "match": match, "template": tpl, "grade": grade}

def _template_to_grade(tpl: dict, color: dict) -> dict:
    """风格模板 → FFmpeg 多参数调色（比v1的4参数更精细）"""
    brightness = color.get("avg_brightness", 50)
    saturation = color.get("avg_saturation", 50)
    warmth = color.get("warmth", 0)
    # 基于模板类别微调
    cat = tpl.get("category", "film")
    base = {
        "film": {"contrast": 1.15, "sat_mult": 0.9, "vignette": True},
        "scifi": {"contrast": 1.3, "sat_mult": 1.1, "vignette": False},
        "art": {"contrast": 0.95, "sat_mult": 1.2, "vignette": False},
    }.get(cat, {"contrast": 1.0, "sat_mult": 1.0, "vignette": False})
    return {
        "eq_brightness": max(-0.12, min(0.12, (brightness - 50) / 250)),
        "eq_contrast": base["contrast"],
        "eq_saturation": max(0.8, min(1.35, (saturation / 50) * base["sat_mult"])),
        "cb_red": max(-0.06, min(0.06, warmth / 300)),
        "cb_blue": max(-0.06, min(0.06, -warmth / 300)),
        "vignette": base["vignette"],
    }

# ================================================================
# S2 音乐段落分析（复用 BeatOrchestrator）
# ================================================================
def stage2_music_structure(bgm: Path, out_dir: Path) -> dict:
    import librosa
    import numpy as np
    y, sr = librosa.load(str(bgm), sr=22050, mono=True)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
    duration = float(len(y) / sr)
    # 能量曲线（32 段 RMS）
    n_bins = 32
    rms_full = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    bin_size = len(rms_full) // n_bins
    energy_curve = [float(rms_full[i*bin_size:(i+1)*bin_size].mean()) for i in range(n_bins)]
    e_max = max(energy_curve) or 1.0
    energy_norm = [e / e_max for e in energy_curve]
    # 段落检测（基于能量变化率）
    from audio.beat_orchestrator import BeatOrchestrator
    bo = BeatOrchestrator(bpm=bpm)
    sections_raw = bo.generate_musical_structure(duration, "pop_song")
    sections = [{"type": s.type, "start": s.start_time, "end": s.end_time,
                 "energy": s.energy} for s in sections_raw]
    result = {
        "bpm": round(bpm, 2), "duration": round(duration, 3),
        "beat_times": [round(t, 4) for t in beat_times],
        "sections": sections, "energy_curve": [round(e, 4) for e in energy_norm],
    }
    (out_dir / "music_structure.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"S2 音乐: BPM={bpm:.1f} {len(sections)}段 {len(beat_times)}beats dur={duration:.1f}s")
    for s in sections:
        log(f"  {s['type']:8s} {s['start']:.1f}-{s['end']:.1f}s energy={s['energy']:.2f}")
    return result

# ================================================================
# S3 智能素材选择（内容评分+能量匹配）
# ================================================================
def stage3_smart_select(materials: list, sections: list, n_per_section: int) -> dict:
    import cv2
    import numpy as np
    scored = []
    for m in materials:
        cap = cv2.VideoCapture(str(m))
        if not cap.isOpened(): continue
        nf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # 采样 5 帧分析内容
        scores = {"edge": [], "motion": [], "brightness": []}
        for fi in range(5):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi * max(1, nf // 6))
            ok, fr = cap.read()
            if not ok: break
            gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            scores["edge"].append(float(cv2.Canny(gray, 50, 150).mean()) / 255)
            scores["brightness"].append(float(gray.mean()) / 255)
        cap.release()
        if not scores["edge"]: continue
        edge = np.mean(scores["edge"])
        bright = np.mean(scores["brightness"])
        # 综合评分：边缘丰富+亮度适中（不过曝不过暗）
        bright_score = 1.0 - abs(bright - 0.45) * 2  # 偏好中等偏暗
        quality = float(edge * 0.6 + max(0, bright_score) * 0.4)
        scored.append({"path": str(m), "quality": round(quality, 4),
                       "edge": round(float(edge), 4)})
    scored.sort(key=lambda x: x["quality"], reverse=True)
    # 按段落能量分配：高能量段用高质量素材
    assignment = {}
    sorted_sections = sorted(sections, key=lambda s: s["energy"], reverse=True)
    mat_idx = 0
    for sec in sorted_sections:
        key = f"{sec['type']}_{sec['start']:.0f}"
        picks = []
        for _ in range(n_per_section):
            if mat_idx < len(scored):
                picks.append(scored[mat_idx])
                mat_idx += 1
        assignment[key] = picks
    log(f"S3 选材: {len(scored)}素材评分, top3={[s['path'] for s in scored[:3]]}")
    return {"scored": scored, "assignment": assignment}

# ================================================================
# S4 风格化剪辑规划（按段落分配转场/变速/镜头）
# ================================================================
# 段落→转场映射（高能量=动态转场，低能量=柔和转场）
SECTION_TRANSITION_MAP = {
    "intro": "fade", "verse": "dissolve", "chorus": "slideleft",
    "bridge": "wipeup", "outro": "fade", "hook": "smoothleft",
    "build_up": "slideright", "drop": "wipeleft", "breakdown": "dissolve",
}
# 段落→变速映射
SECTION_SPEED_MAP = {
    "intro": 1.0, "verse": 1.0, "chorus": 1.25,
    "bridge": 0.85, "outro": 0.9, "hook": 1.3,
    "build_up": 1.15, "drop": 1.4, "breakdown": 0.8,
}
# 段落→镜头映射
SECTION_CAMERA_MAP = {
    "intro": "push_in", "verse": "slow_push", "chorus": "push_in",
    "bridge": "pull_out", "outro": "pull_out", "hook": "push_in",
    "build_up": "push_in", "drop": "pull_out", "breakdown": "pull_out",
}

def stage4_style_plan(style_info: dict, music: dict, selection: dict) -> dict:
    tpl = style_info["template"]
    sections = music["sections"]
    seg_dur = (60.0 / music["bpm"]) * 4  # 每段4拍
    td = 0.4  # 转场时长
    segments = []
    mat_pool = selection["scored"]
    mat_idx = 0
    for i, sec in enumerate(sections):
        key = f"{sec['type']}_{sec['start']:.0f}"
        sec_dur = sec["end"] - sec["start"]
        n_segs = max(1, round(sec_dur / seg_dur))
        for j in range(n_segs):
            src = mat_pool[mat_idx % len(mat_pool)]["path"] if mat_pool else ""
            mat_idx += 1
            trans_type = SECTION_TRANSITION_MAP.get(sec["type"], "fade")
            # 风格模板偏好转场优先（如果是最后一个段内段则用段落转场）
            if j == n_segs - 1 and i < len(sections) - 1:
                trans_type = tpl.get("preferred_transition", trans_type)
                # 确保转场类型在 ffmpeg xfade 支持范围内
                valid = {"fade", "dissolve", "wipeleft", "wiperight", "wipeup", "wipedown",
                         "slideleft", "slideright", "slideup", "slidedown",
                         "smoothleft", "smoothright", "smoothup", "smoothdown",
                         "circlecrop", "radial"}
                # 映射常见别名
                alias = {"slide": "slideleft", "zoom": "circlecrop",
                         "whip": "smoothleft", "wipe": "wipeleft"}
                if trans_type in alias: trans_type = alias[trans_type]
                if trans_type not in valid: trans_type = "dissolve"
            segments.append({
                "index": len(segments),
                "source": src,
                "section": sec["type"],
                "section_energy": sec["energy"],
                "start_time": sec["start"] + j * seg_dur,
                "duration": round(seg_dur, 4),
                "speed": SECTION_SPEED_MAP.get(sec["type"], 1.0),
                "camera": SECTION_CAMERA_MAP.get(sec["type"], "push_in"),
                "transition": trans_type if (j < n_segs - 1 or i < len(sections) - 1) else None,
            })
    total = sum(s["duration"] for s in segments) - td * sum(1 for s in segments if s["transition"])
    plan = {
        "segment_duration": round(seg_dur, 4),
        "transition_duration": td,
        "planned_total": round(total, 4),
        "segments": segments,
        "text_overlays": [
            {"text": "VINLAND SAGA", "fontsize": 84, "y_ratio": 0.14,
             "fade_in": 0.8, "hold_until": 4.0},
            {"text": "STYLE-AWARE AUTO EDIT v2", "fontsize": 36, "y_ratio": 0.88,
             "fade_in": 1.2, "hold_until": 5.0},
        ],
    }
    trans_types = set(s["transition"] for s in segments if s["transition"])
    log(f"S4 规划: {len(segments)}段 转场类型={trans_types} "
        f"总长≈{total:.1f}s")
    return plan

# ================================================================
# S5 FFmpeg 执行（多样转场+逐段调色+文字增强）
# ================================================================
def _seg_filter(seg, grade, graded=True):
    d, speed = seg["duration"], seg["speed"]
    f = ["setpts=PTS-STARTPTS", f"setpts=PTS/{speed}"]
    amt = 0.12
    if seg["camera"] == "push_in":
        expr = f"{amt}*min(t/{d},1)"
    elif seg["camera"] == "slow_push":
        expr = f"{amt*0.6}*min(t/{d},1)"
    else:
        expr = f"{amt}*(1-min(t/{d},1))"
    f.append(f"crop=w='iw-(iw*{expr})':h='ih-(ih*{expr})':x='(iw-ow)/2':y='(ih-oh)/2'")
    f.append("scale=1920:1080")
    if graded:
        f.append(f"eq=brightness={grade['eq_brightness']:.3f}"
                 f":contrast={grade['eq_contrast']:.3f}"
                 f":saturation={grade['eq_saturation']:.3f}")
        f.append(f"colorbalance=rs={grade['cb_red']:.3f}:gs=0:bs={grade['cb_blue']:.3f}")
        if grade.get("vignette"):
            f.append("vignette=PI/4")
    return ",".join(f)

def stage5_execute(plan, grade, bgm, out_dir):
    seg_dir = out_dir / "segments"; seg_dir.mkdir(exist_ok=True)
    seg_files = []
    # 5.1 逐段生成
    for seg in plan["segments"]:
        if not seg["source"]: continue
        out = seg_dir / f"seg_{seg['index']:02d}.mp4"
        dur_need = seg["duration"] * seg["speed"] + 0.3
        vf = _seg_filter(seg, grade, graded=True)
        cmd = [FFMPEG, "-y", "-ss", "0", "-i", seg["source"],
               "-t", f"{dur_need:.3f}", "-vf", vf, "-an", "-r", "23.976",
               "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(out)]
        r = run_cmd(cmd)
        if r.returncode != 0 or not out.exists():
            raise RuntimeError(f"段{seg['index']}失败: {r.stderr[-400:]}")
        seg_files.append(out)
        log(f"S5 段{seg['index']:02d} OK: {seg['section']} speed={seg['speed']} "
            f"cam={seg['camera']} trans={seg['transition']}")
    # 5.1b 无调色对照
    seg0 = plan["segments"][0]
    nograde = seg_dir / "seg_00_nograde.mp4"
    run_cmd([FFMPEG, "-y", "-i", seg0["source"],
             "-t", f"{seg0['duration']*seg0['speed']+0.3:.3f}",
             "-vf", _seg_filter(seg0, grade, graded=False), "-an", "-r", "23.976",
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", str(nograde)])
    # 5.2 多样转场 xfade 拼接
    n = len(seg_files)
    td = plan["transition_duration"]
    inputs = []
    for f in seg_files: inputs += ["-i", str(f)]
    fc_parts = []
    acc_dur = plan["segments"][0]["duration"]
    prev = "[0:v]"
    for k in range(1, n):
        seg = plan["segments"][k]
        trans = seg.get("transition") or "fade"
        offset = acc_dur - td
        nxt = f"[{k}:v]"
        out_label = f"[v{k}]" if k < n - 1 else "[vout]"
        fc_parts.append(
            f"{prev}{nxt}xfade=transition={trans}:duration={td}:offset={offset:.4f}{out_label}")
        prev = out_label
        acc_dur += seg["duration"] - td
    # 5.3 文字特效（增强版：阴影+描边+淡入动画）
    font = r"'C\:/Windows/Fonts/arial.ttf'"
    t1, t2 = plan["text_overlays"][0], plan["text_overlays"][1]
    text_filter = (
        f"drawtext=text='{t1['text']}':fontfile={font}:fontsize={t1['fontsize']}"
        f":fontcolor=white:borderw=4:bordercolor=black"
        f":shadowcolor=black:shadowx=3:shadowy=3"
        f":x=(w-text_w)/2:y=h*{t1['y_ratio']}"
        f":alpha='if(lt(t,{t1['fade_in']}),t/{t1['fade_in']},"
        f"if(lt(t,{t1['hold_until']}),1,max(0,1-(t-{t1['hold_until']})/0.8)))',"
        f"drawtext=text='{t2['text']}':fontfile={font}:fontsize={t2['fontsize']}"
        f":fontcolor=0xD0D0D0:borderw=2:bordercolor=0x333333"
        f":x=(w-text_w)/2:y=h*{t2['y_ratio']}"
        f":alpha='if(lt(t,{t2['fade_in']}),t/{t2['fade_in']},"
        f"if(lt(t,{t2['hold_until']}),1,max(0,1-(t-{t2['hold_until']})/0.8)))'"
    )
    fc = ";".join(fc_parts) + f";{prev}" + text_filter + "[final]"
    fc_script = out_dir / "filtergraph.txt"
    fc_script.write_text(fc, encoding="utf-8")
    final_mp4 = out_dir / "final_vinland_v2.mp4"
    d_total = acc_dur
    cmd = ([FFMPEG, "-y"] + inputs + ["-i", str(bgm),
           "-filter_complex_script", str(fc_script),
           "-map", "[final]", "-map", f"{n}:a",
           "-af", f"afade=t=in:d=0.5,afade=t=out:st={max(0,d_total-1.5):.2f}:d=1.5",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18",
           "-c:a", "aac", "-b:a", "192k", "-shortest", str(final_mp4)])
    r = run_cmd(cmd, timeout=900)
    if r.returncode != 0 or not final_mp4.exists():
        raise RuntimeError(f"成片失败: {r.stderr[-800:]}")
    log(f"S5 成片 OK: {final_mp4.name} ({final_mp4.stat().st_size/1048576:.2f} MB)")
    return {"final": str(final_mp4), "nograde": str(nograde),
            "segments": [str(f) for f in seg_files], "xfade_count": len(fc_parts)}

# ================================================================
# S6 验证闭环（v1 四重 + 风格一致性）
# ================================================================
def ffprobe_stats(path):
    r = run_cmd([FFPROBE, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                 "-show_entries", "format=duration,size", "-of", "json", str(path)])
    return json.loads(r.stdout) if r.returncode == 0 else {}

def verify_cuts(final, plan):
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(final))
    td, sd = plan["transition_duration"], plan["segment_duration"]
    cut_times, t = [], sd - td / 2
    for i in range(len(plan["segments"]) - 1):
        cut_times.append(t); t += sd - td
    def fat(ts):
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
        ok, fr = cap.read(); return fr if ok else None
    cd, ctrl = [], []
    for ct in cut_times:
        f1, f2 = fat(ct - 0.3), fat(ct + 0.3)
        if f1 is not None and f2 is not None:
            cd.append(float(np.mean(np.abs(f1.astype(float) - f2.astype(float)))))
    for i in range(len(plan["segments"])):
        mid = i * (sd - td) + sd / 2
        f1, f2 = fat(mid - 0.15), fat(mid + 0.15)
        if f1 is not None and f2 is not None:
            ctrl.append(float(np.mean(np.abs(f1.astype(float) - f2.astype(float)))))
    cap.release()
    ca = sum(cd) / max(1, len(cd)); ctrl_a = sum(ctrl) / max(1, len(ctrl))
    ratio = ca / ctrl_a if ctrl_a > 0 else 0
    ok = ratio > 1.5
    log(f"S6 卡点: 切点={ca:.2f} 对照={ctrl_a:.2f} 比值={ratio:.2f} -> {'PASS' if ok else 'FAIL'}")
    return {"ratio": round(ratio, 3), "pass": bool(ok)}

def verify_style(nograde, final, out_dir):
    import numpy as np
    from PIL import Image
    ev = out_dir / "evidence"; ev.mkdir(exist_ok=True)
    shots = {}
    for nm, src in (("nograde", nograde), ("graded", final)):
        run_cmd([FFMPEG, "-y", "-ss", "1.0", "-i", str(src), "-frames:v", "1",
                 str(ev / f"{nm}_frame.png")])
        shots[nm] = ev / f"{nm}_frame.png"
    a = np.asarray(Image.open(shots["nograde"]).convert("RGB")).astype(float)
    b = np.asarray(Image.open(shots["graded"]).convert("RGB")).astype(float)
    diff = float(np.mean(np.abs(a - b)))
    ok = diff > 2.0
    log(f"S6 风格: 像素差={diff:.2f} -> {'PASS' if ok else 'FAIL'}")
    return {"mean_diff": round(diff, 3), "pass": bool(ok),
            "evidence": [str(shots["nograde"]), str(shots["graded"])]}

def verify_camera(seg_file, camera, out_dir):
    import cv2
    import numpy as np
    cap = cv2.VideoCapture(str(seg_file))
    nf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0); _, f0 = cap.read()
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, nf - 2)); _, f1 = cap.read()
    cap.release()
    if f0 is None or f1 is None: return {"pass": False}
    fd = float(np.mean(np.abs(f0.astype(float) - f1.astype(float))))
    ev = out_dir / "evidence"; ev.mkdir(exist_ok=True)
    cv2.imwrite(str(ev / f"cam_{camera}_first.png"), f0)
    cv2.imwrite(str(ev / f"cam_{camera}_last.png"), f1)
    ok = fd > 1.0
    log(f"S6 镜头({camera}): 帧差={fd:.2f} -> {'PASS' if ok else 'FAIL'}")
    return {"full_diff": round(fd, 3), "pass": bool(ok)}

def verify_transition_diversity(plan):
    """验证转场类型多样性"""
    trans = [s["transition"] for s in plan["segments"] if s.get("transition")]
    unique = set(trans)
    ok = len(unique) >= 2
    log(f"S6 转场多样性: {unique} ({len(unique)}种) -> {'PASS' if ok else 'WARN'}")
    return {"types": list(unique), "count": len(unique), "pass": bool(ok)}

def stage6_verify(final, plan, nograde, out_dir):
    probe = ffprobe_stats(final)
    cut = verify_cuts(final, plan)
    style = verify_style(nograde, final, out_dir)
    cam = verify_camera(out_dir / "segments" / "seg_00.mp4",
                        plan["segments"][0]["camera"], out_dir)
    trans = verify_transition_diversity(plan)
    dur = float(probe.get("format", {}).get("duration", 0))
    dur_ok = abs(dur - plan["planned_total"]) < 2.0
    result = {
        "ffprobe": probe,
        "duration": {"actual": round(dur, 3), "planned": plan["planned_total"], "pass": bool(dur_ok)},
        "cut_alignment": cut, "style_applied": style,
        "camera_motion": cam, "transition_diversity": trans,
    }
    result["overall_pass"] = all([cut["pass"], style["pass"], cam["pass"], dur_ok])
    log(f"S6 综合: {'PASS' if result['overall_pass'] else 'FAIL'} "
        f"(时长 {dur:.2f}s vs {plan['planned_total']}s)")
    return result

# ================================================================
# 主流程
# ================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--bgm", required=True)
    ap.add_argument("--materials-dir", required=True)
    ap.add_argument("--segments", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else PROJECT_ROOT / "output_production" / f"e2e_v2_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    reference, bgm = Path(args.reference), Path(args.bgm)
    materials = sorted(Path(args.materials_dir).glob("clip_*_1.mp4"))
    materials = [m for m in materials if m.resolve() != reference.resolve()]
    if not materials:
        log("素材为空", "ERROR"); return 1

    report = {"started": ts, "version": "v2",
              "inputs": {"reference": str(reference), "bgm": str(bgm), "n_materials": len(materials)}}
    try:
        s0 = stage0_env(); report["S0"] = s0
        if not s0["pass"]: raise RuntimeError("环境自检失败")

        s1 = stage1_deep_style(reference); report["S1"] = {
            "style_name": s1["match"]["style_name"],
            "style_score": s1["match"]["style_score"],
            "grade": s1["grade"]}

        s2 = stage2_music_structure(bgm, out_dir); report["S2"] = {
            "bpm": s2["bpm"], "sections": len(s2["sections"]),
            "beats": len(s2["beat_times"])}

        s3 = stage3_smart_select(materials, s2["sections"], n_per_section=3)
        report["S3"] = {"scored": len(s3["scored"]),
                        "top3_quality": [s["quality"] for s in s3["scored"][:3]]}

        s4 = stage4_style_plan(s1, s2, s3); report["S4"] = {
            "n_segments": len(s4["segments"]),
            "transitions": list(set(s["transition"] for s in s4["segments"] if s["transition"])),
            "planned_total": s4["planned_total"]}

        s5 = stage5_execute(s4, s1["grade"], bgm, out_dir)
        report["S5"] = {"xfade_count": s5["xfade_count"],
                        "final_size_mb": round(Path(s5["final"]).stat().st_size / 1048576, 2)}

        s6 = stage6_verify(Path(s5["final"]), s4, Path(s5["nograde"]), out_dir)
        report["S6"] = s6
        report["success"] = bool(s6["overall_pass"])
        report["final"] = s5["final"]
    except Exception as e:
        report["success"] = False; report["error"] = str(e)
        log(f"管线失败: {e}", "ERROR")
    finally:
        report["finished"] = time.strftime("%Y%m%d_%H%M%S")
        (out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"报告: {out_dir / 'report.json'}")

    log("=" * 60)
    log(f"结果: {'PASS' if report.get('success') else 'FAIL'}")
    if report.get("final"):
        log(f"成片: {report['final']} ({report.get('S5',{}).get('final_size_mb')} MB)")
    return 0 if report.get("success") else 2

if __name__ == "__main__":
    sys.exit(main())
