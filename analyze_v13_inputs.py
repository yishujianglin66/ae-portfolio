#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V13 输入素材深度分析 - BGM结构 + 5个无水印冰海战记源素材元数据
输出 JSON 报告供剧本编排使用
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BGM_PATH = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
NEW_CLIPS_DIR = r"D:\AE-Work\视频素材库\冰海战记新素材"
OUTPUT_REPORT = r"D:\AE-Work\日志与报告\v13_input_analysis.json"

# 5个新无水印源素材 (只用mp4, 不用m4a)
TARGET_CLIPS = [
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p01 S1OP1-MUKANJYO.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p02 S1ED1-Torches.f30080.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p03 S1OP2-Dark Crow.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p05 S2OP1-River.f30077.mp4",
    "vinland_1_【1080P⧸4K⧸收藏】冰海战记NCOP&ED两季全合集 p07 S2OP2-Paradox.f30080.mp4",
    "vinland_2_冰海战记第一季：最后的封神场面.f30080.mp4",
    "vinland_3_【授权转载】冰海战记第二季最精彩的打戏 托尔芬VS蛇.f30077.mp4",
    "vinland_4_4K_MAD.f30077.mp4",
    "vinland_5_【MAD⧸冰海战记】There's a revolution coming!.f30080.mp4",
]


def analyze_bgm() -> dict:
    """使用 librosa 分析 BGM: BPM/节拍/能量/段落/色度"""
    try:
        import librosa
        import numpy as np
    except ImportError as e:
        return {"error": f"librosa/numpy not installed: {e}"}

    if not Path(BGM_PATH).exists():
        return {"error": f"BGM not found: {BGM_PATH}"}

    y, sr = librosa.load(BGM_PATH, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    # BPM + 节拍
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    if hasattr(tempo, "__iter__"):
        tempo = float(tempo[0])
    else:
        tempo = float(tempo)

    # 节拍时间点
    beat_times = librosa.frames_to_time(beats, sr=sr).tolist()

    # RMS 能量曲线
    rms = librosa.feature.rms(y=y)[0]
    # librosa 新版没有 frames_like_rms, 用 frame_to_time 默认 hop_length
    hop = 512
    rms_frames = librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop
    ).tolist()
    rms_peaks_idx = sorted(range(len(rms)), key=lambda i: rms[i], reverse=True)[:15]
    rms_peaks = [
        {"time": float(rms_frames[i]), "energy": float(rms[i])}
        for i in sorted(rms_peaks_idx)
    ]

    # 频谱质心 (亮度)
    spec_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    avg_brightness = float(spec_centroid.mean())

    # 段落分割
    try:
        agg = librosa.segment.agglomerative(
            librosa.feature.chroma_cqt(y=y, sr=sr), k=5
        )
        bound_idx = [0] + [i for i in range(1, len(agg)) if agg[i] != agg[i - 1]]
        bound_idx.append(len(agg) - 1)
        segments = []
        for i in range(len(bound_idx) - 1):
            s_idx, e_idx = bound_idx[i], bound_idx[i + 1]
            s_t = float(librosa.frames_to_time(s_idx, sr=sr))
            e_t = float(librosa.frames_to_time(e_idx, sr=sr))
            seg_rms = float(rms[min(s_idx, len(rms) - 1):min(e_idx, len(rms))].mean())
            segments.append({
                "start": round(s_t, 2),
                "end": round(e_t, 2),
                "duration": round(e_t - s_t, 2),
                "energy": round(seg_rms, 4),
            })
    except Exception as e:
        segments = []

    # 总能量分布 (每秒一桶)
    per_sec_energy = []
    for t in range(int(duration) + 1):
        idx_start = int(t * sr)
        idx_end = min(int((t + 1) * sr), len(y))
        if idx_end > idx_start:
            per_sec_energy.append(float(np.sqrt(np.mean(y[idx_start:idx_end] ** 2))))

    return {
        "file": BGM_PATH,
        "duration_sec": round(duration, 2),
        "bpm": round(tempo, 2),
        "beat_count": int(len(beats)),
        "beat_interval_sec": round(60.0 / tempo, 4) if tempo else 0,
        "avg_brightness": round(avg_brightness, 2),
        "beat_times_first_30": [round(b, 3) for b in beat_times[:30]],
        "energy_peaks_top15": rms_peaks,
        "segments": segments,
        "per_second_energy": [round(e, 4) for e in per_sec_energy],
    }


def analyze_clip(clip_path: str) -> dict:
    """使用 OpenCV 分析视频素材: 元数据/运动强度/色调/亮度"""
    try:
        import cv2
        import numpy as np
    except ImportError as e:
        return {"error": f"opencv not installed: {e}", "file": clip_path}

    if not Path(clip_path).exists():
        return {"error": f"file not found: {clip_path}"}

    cap = cv2.VideoCapture(clip_path)
    if not cap.isOpened():
        return {"error": f"cannot open: {clip_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else 0

    # 采样: 每秒取1帧, 最多30帧
    sample_step = max(1, int(fps))
    max_samples = min(30, frame_count // sample_step)

    motion_scores = []
    hsv_means = []
    brightness_means = []
    prev_gray = None
    motion_peaks = []  # (time, score)

    for i in range(max_samples):
        frame_idx = i * sample_step
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            break

        # HSV 色调
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h_mean = float(hsv[:, :, 0].mean())
        s_mean = float(hsv[:, :, 1].mean())
        v_mean = float(hsv[:, :, 2].mean())
        hsv_means.append({"h": round(h_mean, 1), "s": round(s_mean, 1), "v": round(v_mean, 1)})
        brightness_means.append(round(v_mean, 1))

        # 运动强度 (帧间差分)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            motion_score = float(diff.mean())
            motion_scores.append(motion_score)
            t = frame_idx / fps if fps > 0 else 0
            if motion_score > 15:  # 高运动阈值
                motion_peaks.append({"time": round(t, 2), "score": round(motion_score, 2)})
        prev_gray = gray

    cap.release()

    avg_motion = float(np.mean(motion_scores)) if motion_scores else 0
    max_motion = float(np.max(motion_scores)) if motion_scores else 0
    avg_h = float(np.mean([m["h"] for m in hsv_means])) if hsv_means else 0
    avg_s = float(np.mean([m["s"] for m in hsv_means])) if hsv_means else 0
    avg_v = float(np.mean([m["v"] for m in hsv_means])) if hsv_means else 0

    # 运动节奏: 把视频时长切成 6 段, 看每段平均运动量
    motion_rhythm = []
    if motion_scores:
        n = len(motion_scores)
        chunk = max(1, n // 6)
        for i in range(0, n, chunk):
            chunk_scores = motion_scores[i:i + chunk]
            if chunk_scores:
                motion_rhythm.append(round(float(np.mean(chunk_scores)), 2))

    return {
        "file": Path(clip_path).name,
        "duration_sec": round(duration, 2),
        "fps": round(fps, 2),
        "frame_count": frame_count,
        "resolution": [width, height],
        "avg_motion": round(avg_motion, 2),
        "max_motion": round(max_motion, 2),
        "avg_hsv": {"h": round(avg_h, 1), "s": round(avg_s, 1), "v": round(avg_v, 1)},
        "motion_rhythm_6parts": motion_rhythm,
        "motion_peaks_count": len(motion_peaks),
        "motion_peaks_top5": sorted(motion_peaks, key=lambda x: x["score"], reverse=True)[:5],
        "brightness_curve": brightness_means,
    }


def main():
    print("=" * 70)
    print("V13 输入素材深度分析 (BGM + 9个新无水印冰海战记源)")
    print("=" * 70)

    report = {"bgm": None, "clips": [], "errors": []}

    # 1. BGM 分析
    print("\n[1/2] 分析 BGM...")
    report["bgm"] = analyze_bgm()
    if "error" in report["bgm"]:
        print(f"  ERROR: {report['bgm']['error']}")
        report["errors"].append(f"BGM: {report['bgm']['error']}")
    else:
        print(f"  BPM: {report['bgm']['bpm']}")
        print(f"  时长: {report['bgm']['duration_sec']}s")
        print(f"  节拍数: {report['bgm']['beat_count']}")
        print(f"  段落: {len(report['bgm']['segments'])}")

    # 2. 素材并行分析
    print(f"\n[2/2] 并行分析 {len(TARGET_CLIPS)} 个素材...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(analyze_clip, os.path.join(NEW_CLIPS_DIR, c)): c
            for c in TARGET_CLIPS
        }
        for future in as_completed(futures):
            clip_name = futures[future]
            try:
                result = future.result()
                report["clips"].append(result)
                if "error" in result:
                    print(f"  ERROR: {clip_name[:50]}... -> {result['error']}")
                    report["errors"].append(clip_name)
                else:
                    print(f"  OK: {clip_name[:60]}")
                    print(f"      时长={result['duration_sec']}s fps={result['fps']} "
                          f"运动={result['avg_motion']}(max {result['max_motion']})")
            except Exception as e:
                print(f"  EXCEPTION: {clip_name[:50]}... -> {e}")
                report["errors"].append(f"{clip_name}: {e}")

    # 输出报告
    Path(OUTPUT_REPORT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {OUTPUT_REPORT}")
    print(f"\n=== 摘要 ===")
    print(f"BGM: BPM={report['bgm'].get('bpm')}, 时长={report['bgm'].get('duration_sec')}s")
    print(f"素材: {len(report['clips'])} 个, 错误 {len(report['errors'])} 个")


if __name__ == "__main__":
    main()
