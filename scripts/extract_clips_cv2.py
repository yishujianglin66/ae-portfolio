#!/usr/bin/env python3
"""
使用OpenCV提取视频片段和关键帧
"""

import glob
import json
import os

import cv2
import numpy as np

SOURCE_DIR = r"D:\AE-Work\视频素材库\冰海战记新素材"
CLIP_DIR = r"D:\AE-Work\视频素材库\冰海战记片段"
FRAME_DIR = r"D:\AE-Work\视频素材库\冰海战记关键帧"
os.makedirs(CLIP_DIR, exist_ok=True)
os.makedirs(FRAME_DIR, exist_ok=True)


def get_video_info(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration": 0,
    }
    info["duration"] = info["frame_count"] / info["fps"] if info["fps"] > 0 else 0
    cap.release()
    return info


def extract_clip(video_path, start_sec, duration_sec, output_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_frame = int(start_sec * fps)
    end_frame = int((start_sec + duration_sec) * fps)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frame_num = start_frame
    while frame_num < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        frame_num += 1

    cap.release()
    out.release()
    return os.path.exists(output_path)


def extract_frame(video_path, timestamp_sec, output_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return False

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_num = int(timestamp_sec * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)

    ret, frame = cap.read()
    if ret:
        cv2.imwrite(output_path, frame)
    cap.release()
    return os.path.exists(output_path)


def main():
    print("=" * 60)
    print("素材分析与片段提取（OpenCV）")
    print("=" * 60)

    videos = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.mp4")))
    print(f"\n找到 {len(videos)} 个素材视频")

    all_clips = []
    all_frames = []

    for i, video_path in enumerate(videos):
        filename = os.path.basename(video_path)
        print(f"\n[{i+1}/{len(videos)}] {filename[:70]}...")

        info = get_video_info(video_path)
        if not info:
            print("  无法打开视频，跳过")
            continue

        print(f"  {info['width']}x{info['height']} | {info['fps']:.1f}fps | {info['duration']:.1f}s")

        if info["duration"] < 1:
            print("  视频太短，跳过")
            continue

        # 提取3-4个片段
        num_clips = min(4, max(2, int(info["duration"] / 4)))
        clip_dur = min(3.5, info["duration"] / num_clips)

        for j in range(num_clips):
            start = (info["duration"] / num_clips) * j + 0.5
            if start + clip_dur > info["duration"]:
                start = max(0, info["duration"] - clip_dur - 0.5)

            clip_name = f"clip_{i+1}_{j+1}.mp4"
            clip_path = os.path.join(CLIP_DIR, clip_name)

            if extract_clip(video_path, start, clip_dur, clip_path):
                size = os.path.getsize(clip_path)
                print(f"  片段{j+1}: {start:.1f}-{start+clip_dur:.1f}s ({size/1024/1024:.1f}MB) {info['width']}x{info['height']}")
                all_clips.append({
                    "path": clip_path,
                    "source": filename[:50],
                    "start": round(start, 2),
                    "duration": round(clip_dur, 2),
                    "width": info["width"],
                    "height": info["height"],
                    "fps": round(info["fps"], 1)
                })

        # 提取3个关键帧
        for k in range(3):
            ts = (info["duration"] / 4) * (k + 1)
            frame_name = f"frame_{i+1}_{k+1}.jpg"
            frame_path = os.path.join(FRAME_DIR, frame_name)
            if extract_frame(video_path, ts, frame_path):
                size = os.path.getsize(frame_path)
                print(f"  关键帧{k+1}: {ts:.1f}s ({size/1024:.0f}KB)")
                all_frames.append({
                    "path": frame_path,
                    "source": filename[:50],
                    "timestamp": round(ts, 2),
                    "width": info["width"],
                    "height": info["height"]
                })

    print(f"\n{'='*60}")
    print("提取完成:")
    print(f"  视频片段: {len(all_clips)} 个")
    print(f"  关键帧: {len(all_frames)} 张")

    # 按分辨率分类
    portrait_clips = [c for c in all_clips if c["height"] > c["width"]]
    landscape_clips = [c for c in all_clips if c["width"] >= c["height"]]
    print(f"  竖屏片段: {len(portrait_clips)} | 横屏片段: {len(landscape_clips)}")

    print("\n片段列表:")
    for c in all_clips:
        orient = "竖" if c["height"] > c["width"] else "横"
        print(f"  {os.path.basename(c['path'])}: {c['width']}x{c['height']} {orient} {c['duration']:.1f}s")

    with open(os.path.join(CLIP_DIR, "clips_info.json"), "w", encoding="utf-8") as f:
        json.dump({"clips": all_clips, "frames": all_frames}, f, ensure_ascii=False, indent=2)

    return all_clips, all_frames


if __name__ == "__main__":
    main()