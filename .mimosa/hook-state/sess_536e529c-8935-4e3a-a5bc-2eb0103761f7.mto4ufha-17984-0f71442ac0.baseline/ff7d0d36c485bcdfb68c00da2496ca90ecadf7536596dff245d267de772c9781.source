"""真实渲染成品：分析源视频 -> 提取场景 -> MoviePy 2.x 渲染带转场/标题的成品视频。

不依赖 Adobe 软件，纯 Python + ffmpeg（moviepy）。
"""
import os
import sys
import time
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from moviepy import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
from moviepy.video.fx import FadeIn, FadeOut

from core.video_analyzer_accelerated import AcceleratedVideoAnalyzer

SRC = os.path.join(PROJECT_ROOT, "data", "real_amv_test", "BV18W4y1J7gb_.mp4")
OUT_DIR = os.path.join(PROJECT_ROOT, "output", "rendered")
OUT = os.path.join(OUT_DIR, "amv_preview_product.mp4")


def analyze_scenes(src):
    analyzer = AcceleratedVideoAnalyzer(use_gpu=False)
    result = analyzer.analyze_video(src, sample_interval=5)
    scenes = result.get("scenes", [])
    # 场景格式: {"start": float, "end": float, ...}
    segments = []
    for s in scenes:
        st = float(s.get("start_time", s.get("start", 0)))
        en = float(s.get("end_time", s.get("end", 0)))
        if en > st:
            segments.append((st, en))
    print(f"[分析] 检测到 {len(segments)} 个场景片段")
    return segments, result


def render(src, segments):
    os.makedirs(OUT_DIR, exist_ok=True)
    base = VideoFileClip(src)
    total = base.duration

    # 标题片头
    title = (
        TextClip(
            text="AE Knowledge Vault\n自动剪辑预览",
            font_size=48,
            color="white",
            bg_color="black",
            size=(1280, 720),
            method="caption",
        )
        .with_duration(2.0)
        .with_position("center")
    )
    title = FadeIn(0.5).apply(title)

    # 按场景切分源片，统一分辨率 + crossfade
    clips = []
    for i, (st, en) in enumerate(segments):
        seg = base.subclipped(st, min(en, total))
        seg = seg.resized((1280, 720))
        # 片段间交叉淡化
        if i > 0:
            seg = FadeIn(0.4).apply(seg)
        if i < len(segments) - 1:
            seg = FadeOut(0.4).apply(seg)
        clips.append(seg)

    main = concatenate_videoclips(clips, method="compose")
    final = CompositeVideoClip([main, title], size=(1280, 720))

    t0 = time.time()
    final.write_videofile(
        OUT, fps=30, codec="libx264", audio_codec="aac",
        preset="fast", logger=None,
    )
    dt = time.time() - t0

    final.close()
    base.close()
    return dt


def main():
    if not os.path.isfile(SRC):
        print("源视频不存在:", SRC)
        sys.exit(1)

    t0 = time.time()
    segments, _ = analyze_scenes(SRC)
    if not segments:
        # 兜底: 整段作为单一片段
        base = VideoFileClip(SRC)
        segments = [(0, base.duration)]
        base.close()

    dur = render(SRC, segments)
    size_mb = os.path.getsize(OUT) / (1024 * 1024)
    print("=== 渲染成品完成 ===")
    print(f"输出: {OUT}")
    print(f"大小: {size_mb:.2f} MB")
    print(f"渲染耗时: {dur:.2f}s (总流程 {time.time()-t0:.2f}s)")


if __name__ == "__main__":
    main()
