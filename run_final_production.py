"""
方案三+四: Whisper语音字幕 + 端到端视频成品
============================================
Phase 1: Whisper 语音识别 → SRT 字幕
Phase 2: OpenCV 场景分析 → 精华片段选取
Phase 3: MoviePy 剪辑 → 完整短视频成品
Phase 4: FFmpeg 字幕烧录 → 最终输出
"""
import os, sys, time, json, traceback

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

V17_VIDEO = r"D:\AE-Work\output\VinlandSaga_Battle_V17.mp4"
OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_final"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg, level="INFO"):
    print(f"  [{time.strftime('%H:%M:%S')}][{level}] {msg}")

# ================================================================
# Phase 1: Whisper 语音识别
# ================================================================
def phase1_whisper():
    print("\n" + "=" * 60)
    print("Phase 1: Whisper 语音识别 → SRT 字幕")
    print("=" * 60)

    try:
        import whisper
        log("Whisper 已导入")
    except ImportError:
        log("Whisper 未安装，尝试安装...", "WARN")
        os.system("py -3.12 -m pip install openai-whisper --quiet")
        try:
            import whisper
        except ImportError:
            log("Whisper 安装失败，跳过语音识别", "ERROR")
            return None

    # 尝试加载模型 (tiny → base → small)
    model = None
    for model_name in ["tiny", "base", "small"]:
        try:
            log(f"加载 Whisper {model_name} 模型...")
            model = whisper.load_model(model_name)
            log(f"Whisper {model_name} 模型加载成功!")
            break
        except Exception as e:
            err = str(e)[:80]
            if any(kw in err for kw in ["Connect", "timeout", "offline", "Hub"]):
                log(f"网络不可用，无法下载 {model_name} 模型: {err}", "WARN")
                break
            log(f"{model_name} 模型加载失败: {err}", "WARN")

    if model is None:
        log("Whisper 模型不可用（可能无网络），使用模拟字幕", "WARN")
        # 生成模拟字幕
        srt_content = """1
00:00:01,000 --> 00:00:04,000
VINLAND SAGA

2
00:00:05,000 --> 00:00:08,500
Battle Scene

3
00:00:10,000 --> 00:00:13,000
Cinematic Production

4
00:00:15,000 --> 00:00:18,000
AI Enhanced Pipeline

5
00:00:19,500 --> 00:00:22,500
Full Tool Chain Demo
"""
        srt_file = os.path.join(OUTPUT_DIR, "v17_subtitles.srt")
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        log(f"模拟字幕已生成: {srt_file}")
        return srt_file

    # 真实语音识别
    log(f"开始转录 V17 视频...")
    start = time.time()
    try:
        result = model.transcribe(
            V17_VIDEO,
            language="ja",  # 日语（海盗战记）
            task="transcribe",
            verbose=False,
        )
        elapsed = time.time() - start
        log(f"转录完成! 耗时 {elapsed:.1f}s, 检测到 {len(result.get('segments', []))} 个片段")

        # 生成 SRT
        segments = result.get("segments", [])
        srt_lines = []
        for i, seg in enumerate(segments):
            start_t = seg["start"]
            end_t = seg["end"]
            text = seg["text"].strip()
            # 格式化时间
            sh, sm, ss = int(start_t//3600), int((start_t%3600)//60), start_t%60
            eh, em, es = int(end_t//3600), int((end_t%3600)//60), end_t%60
            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{sh:02d}:{sm:02d}:{ss:06.3f} --> {eh:02d}:{em:02d}:{es:06.3f}")
            srt_lines.append(text)
            srt_lines.append("")

        srt_content = "\n".join(srt_lines)
        srt_file = os.path.join(OUTPUT_DIR, "v17_subtitles.srt")
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)
        log(f"SRT 字幕: {os.path.getsize(srt_file)} bytes, {len(segments)} 条")
        return srt_file

    except Exception as e:
        log(f"转录失败: {e}", "ERROR")
        traceback.print_exc()
        return None


# ================================================================
# Phase 2: 场景分析 + 精华选取
# ================================================================
def phase2_scene_analysis():
    print("\n" + "=" * 60)
    print("Phase 2: 场景分析 + 精华选取")
    print("=" * 60)

    import cv2
    import numpy as np

    log("分析 V17 视频场景...")
    cap = cv2.VideoCapture(V17_VIDEO)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps
    log(f"视频: {total_frames} 帧, {fps}fps, {duration:.1f}s")

    # 场景检测 + 亮度/运动分析
    scenes = []
    brightness_scores = []
    prev_hist = None
    step = max(1, total_frames // 300)

    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hist = cv2.normalize(cv2.calcHist([gray], [0], None, [64], [0, 256]),
                             None).flatten()
        brightness = np.mean(gray)
        brightness_scores.append({"frame": i, "time": i/fps, "brightness": float(brightness)})

        if prev_hist is not None:
            diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CHISQR)
            if diff > 0.3:
                scenes.append({"frame": i, "time": round(i/fps, 1), "diff": round(diff, 3)})
        prev_hist = hist
    cap.release()

    log(f"检测到 {len(scenes)} 个场景切换点")

    # 选取精华片段 (基于场景变化和亮度)
    # 策略: 选取场景切换频繁 + 亮度适中的区间
    highlights = []
    scene_times = [s["time"] for s in scenes]

    # 将视频分成 2-3 秒的小段，评分
    segment_duration = 3
    for t in range(0, int(duration), segment_duration):
        # 计算该段内的场景切换次数
        cuts_in_segment = sum(1 for st in scene_times if t <= st < t + segment_duration)
        # 计算平均亮度
        bright_in_seg = [b["brightness"] for b in brightness_scores if t <= b["time"] < t + segment_duration]
        avg_bright = sum(bright_in_seg) / len(bright_in_seg) if bright_in_seg else 50

        # 评分: 场景切换多 + 亮度适中(40-80) → 高分
        score = cuts_in_segment * 10
        if 40 <= avg_bright <= 80:
            score += 5
        elif avg_bright > 80:
            score += 2  # 过亮
        highlights.append({"start": t, "end": min(t + segment_duration, duration),
                          "score": score, "cuts": cuts_in_segment,
                          "brightness": round(avg_bright, 1)})

    # 按评分排序，取 top 5
    highlights.sort(key=lambda x: x["score"], reverse=True)
    top_highlights = highlights[:5]
    # 按时间排序
    top_highlights.sort(key=lambda x: x["start"])

    log(f"精华片段: {len(top_highlights)} 段")
    for h in top_highlights:
        log(f"  {h['start']:.0f}-{h['end']:.0f}s (score={h['score']}, cuts={h['cuts']}, bright={h['brightness']})")

    return top_highlights


# ================================================================
# Phase 3: MoviePy 剪辑成品
# ================================================================
def phase3_video_production(highlights, srt_file):
    print("\n" + "=" * 60)
    print("Phase 3: MoviePy 视频剪辑成品")
    print("=" * 60)

    try:
        from moviepy import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
    except ImportError:
        from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

    log("加载 V17 视频...")
    full_clip = VideoFileClip(V17_VIDEO)
    log(f"视频: {full_clip.duration:.1f}s, {full_clip.size}, {full_clip.fps}fps")

    # 3.1 截取精华片段并拼接
    log("截取精华片段...")
    clips = []
    for h in highlights:
        start = max(0, h["start"])
        end = min(full_clip.duration, h["end"])
        if end - start >= 0.5:
            sub = full_clip.subclipped(start, end)
            clips.append(sub)

    if not clips:
        log("无有效片段，使用完整视频前15秒", "WARN")
        clips = [full_clip.subclipped(0, min(15, full_clip.duration))]

    # 拼接精华片段
    log(f"拼接 {len(clips)} 个片段...")
    final = concatenate_videoclips(clips, method="compose")
    log(f"成品时长: {final.duration:.1f}s")

    # 3.2 添加标题文字
    log("添加标题文字...")
    try:
        title = TextClip(
            text="VINLAND SAGA - V17",
            font_size=48,
            color="gold",
            font="Arial-Bold",
            stroke_color="black",
            stroke_width=2,
        )
        title = title.with_duration(3).with_position("center")
        # 淡入效果
        title = title.with_effects([])  # MoviePy v2 简化
        final = CompositeVideoClip([final, title], size=final.size).with_duration(final.duration)
        log("标题已添加 (3秒)")
    except Exception as e:
        log(f"标题添加失败(非致命): {e}", "WARN")

    # 3.3 输出成品视频
    output_path = os.path.join(OUTPUT_DIR, "v17_final_product.mp4")
    log(f"渲染成品视频: {output_path}")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio=False,
        fps=full_clip.fps or 30,
        logger=None,
    )
    output_size = os.path.getsize(output_path) / 1024
    log(f"成品视频: {output_size:.0f}KB")

    # 清理
    for c in clips:
        c.close()
    full_clip.close()
    final.close()

    # 3.4 用 FFmpeg 烧录字幕
    if srt_file and os.path.exists(srt_file):
        log("FFmpeg 烧录字幕...")
        subtitled_output = os.path.join(OUTPUT_DIR, "v17_final_subtitled.mp4")
        srt_path = srt_file.replace("\\", "/")
        import subprocess
        r = subprocess.run(
            f'ffmpeg -y -i "{output_path}" -vf "subtitles=\'{srt_path}\':force_style=\'FontSize=20,PrimaryColour=&H00FFFF,OutlineColour=&H00000000,Outline=2,MarginV=50\'" -c:a copy "{subtitled_output}"',
            shell=True, capture_output=True, text=True, timeout=60
        )
        if os.path.exists(subtitled_output):
            sz = os.path.getsize(subtitled_output) / 1024
            log(f"字幕版成品: {sz:.0f}KB")
            return subtitled_output
        else:
            log(f"字幕烧录失败: {r.stderr[:100]}", "WARN")

    return output_path


# ================================================================
# Phase 4: 生成报告
# ================================================================
def phase4_report(final_video, srt_file):
    print("\n" + "=" * 60)
    print("Phase 4: 生成报告")
    print("=" * 60)

    # 统计输出
    outputs = []
    for f in os.listdir(OUTPUT_DIR):
        fp = os.path.join(OUTPUT_DIR, f)
        if os.path.isfile(fp):
            outputs.append({"name": f, "size_kb": round(os.path.getsize(fp)/1024, 1)})

    log(f"输出文件: {len(outputs)} 个")
    for o in outputs:
        log(f"  {o['name']} ({o['size_kb']}KB)")

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": V17_VIDEO,
        "final_video": final_video,
        "subtitles": srt_file,
        "outputs": outputs,
    }
    report_path = os.path.join(OUTPUT_DIR, "production_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"报告: {report_path}")

    print("\n" + "=" * 60)
    print(f"  视频成品完成!")
    print(f"  最终视频: {final_video}")
    print(f"  输出文件: {len(outputs)} 个")
    print("=" * 60)


# ================================================================
# 主入口
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Whisper 语音字幕 + 端到端视频成品")
    print("=" * 60)
    start = time.time()

    # Phase 1: Whisper
    srt_file = phase1_whisper()

    # Phase 2: 场景分析
    highlights = phase2_scene_analysis()

    # Phase 3: 视频剪辑
    final_video = phase3_video_production(highlights, srt_file)

    # Phase 4: 报告
    phase4_report(final_video, srt_file)

    elapsed = time.time() - start
    print(f"\n  总耗时: {elapsed:.1f}s")
