#!/usr/bin/env python3
"""
从下载的B站素材提取关键片段
+ 分析素材信息
"""

import glob
import json
import os
import subprocess
import sys

SOURCE_DIR = r"D:\AE-Work\视频素材库\冰海战记新素材"
CLIP_DIR = r"D:\AE-Work\视频素材库\冰海战记片段"
os.makedirs(CLIP_DIR, exist_ok=True)


def get_video_info(video_path):
    """获取视频信息"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8")
        if result.returncode == 0:
            return json.loads(result.stdout)
    except:
        pass
    return None


def extract_clip(video_path, start, duration, output_path):
    """提取视频片段"""
    cmd = [
        "ffmpeg", "-y", "-ss", str(start), "-i", video_path,
        "-t", str(duration), "-c:v", "libx264", "-preset", "fast",
        "-crf", "18", "-an", output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8")
        return result.returncode == 0
    except:
        return False


def extract_frame(video_path, timestamp, output_path):
    """提取单帧作为图片"""
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
        "-frames:v", "1", "-q:v", "2", output_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, encoding="utf-8")
        return result.returncode == 0
    except:
        return False


def main():
    print("=" * 60)
    print("素材信息分析与片段提取")
    print("=" * 60)

    # 查找所有下载的视频
    videos = sorted(glob.glob(os.path.join(SOURCE_DIR, "*.mp4")))
    print(f"\n找到 {len(videos)} 个素材视频")

    all_clips = []

    for i, video_path in enumerate(videos):
        filename = os.path.basename(video_path)
        print(f"\n[{i+1}/{len(videos)}] {filename[:60]}...")

        # 获取视频信息
        info = get_video_info(video_path)
        if not info:
            print("  无法获取信息，跳过")
            continue

        duration = float(info.get("format", {}).get("duration", 0))
        streams = info.get("streams", [])
        vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
        width = int(vstream.get("width", 0))
        height = int(vstream.get("height", 0))
        fps_str = vstream.get("r_frame_rate", "30/1")
        fps = float(fps_str.split("/")[0]) / float(fps_str.split("/")[1]) if "/" in fps_str else 30.0

        print(f"  时长: {duration:.1f}s | 分辨率: {width}x{height} | FPS: {fps:.1f}")

        # 根据视频时长提取多个片段
        num_clips = min(5, max(2, int(duration / 5)))
        clip_duration = min(4.0, duration / num_clips)

        for j in range(num_clips):
            start = (duration / num_clips) * j
            if start + clip_duration > duration:
                start = max(0, duration - clip_duration)

            clip_name = f"clip_{i+1}_{j+1}.mp4"
            clip_path = os.path.join(CLIP_DIR, clip_name)

            if extract_clip(video_path, start, clip_duration, clip_path):
                size = os.path.getsize(clip_path)
                print(f"  片段{j+1}: {start:.1f}s-{start+clip_duration:.1f}s ({size/1024/1024:.1f}MB)")
                all_clips.append({
                    "path": clip_path,
                    "source": filename[:40],
                    "start": start,
                    "duration": clip_duration,
                    "width": width,
                    "height": height
                })

        # 同时提取关键帧作为静止系素材
        for k in range(3):
            ts = (duration / 4) * (k + 1)
            frame_name = f"frame_{i+1}_{k+1}.jpg"
            frame_path = os.path.join(CLIP_DIR, frame_name)
            if extract_frame(video_path, ts, frame_path):
                print(f"  关键帧{k+1}: {ts:.1f}s")

    print(f"\n{'='*60}")
    print(f"提取完成: {len(all_clips)} 个视频片段")
    print(f"输出目录: {CLIP_DIR}")

    # 列出所有素材
    print("\n素材列表:")
    for c in all_clips:
        print(f"  {os.path.basename(c['path'])}: {c['width']}x{c['height']}, {c['duration']:.1f}s")

    # 保存素材信息
    with open(os.path.join(CLIP_DIR, "clips_info.json"), "w", encoding="utf-8") as f:
        json.dump(all_clips, f, ensure_ascii=False, indent=2)

    return all_clips


if __name__ == "__main__":
    main()