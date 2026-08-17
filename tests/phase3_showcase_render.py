"""
阶段3 Showcase：五大专业剪辑功能真实素材渲染验证
=====================================================
使用 C:\\VinlandClips 真实动漫素材 + data\\real_amv_test 真实AMV音频，
逐项渲染验证并输出可播放 MP4 到 output\\phase3_showcase\\
"""
import sys
import os
import time
import json
import subprocess

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.resolve_engine import (
    ResolveAutomationEngine,
    TransitionConfig,
    ColorWheelConfig,
    Keyframe,
)

WORKSPACE = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
OUTPUT_DIR = os.path.join(WORKSPACE, "output", "phase3_showcase")
MEDIA_DIR = r"C:\VinlandClips"
AMV_DIR = os.path.join(WORKSPACE, "data", "real_amv_test")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def probe(filepath: str) -> dict:
    """ffprobe 验证输出文件"""
    cmd = ['ffprobe', '-v', 'error',
           '-show_entries', 'format=duration,size',
           '-show_entries', 'stream=width,height,codec_name,nb_frames',
           '-of', 'json', filepath]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            info = json.loads(r.stdout)
            v = next((s for s in info['streams'] if s.get('codec_name')), {})
            return {'valid': True,
                    'duration': float(info['format']['duration']),
                    'size_mb': int(info['format']['size']) / 1024 / 1024,
                    'width': v.get('width'), 'height': v.get('height'),
                    'codec': v.get('codec_name')}
    except Exception as e:
        return {'valid': False, 'error': str(e)}
    return {'valid': False}


def pick_long_clips(engine, n=5, min_dur=3.0):
    """挑选时长较长的真实素材"""
    candidates = []
    for f in sorted(os.listdir(MEDIA_DIR)):
        if not f.endswith('.mp4'):
            continue
        path = os.path.join(MEDIA_DIR, f)
        dur = engine._get_media_duration(path)
        if dur and dur >= min_dur:
            candidates.append((dur, path))
    candidates.sort(reverse=True)
    return [p for _, p in candidates[:n]]


def pick_amv_audio():
    """挑选一个真实 AMV 视频作为音频源（含 BGM）"""
    for f in sorted(os.listdir(AMV_DIR)):
        if f.lower().endswith('.mp4') and not f.startswith('.'):
            return os.path.join(AMV_DIR, f)
    return None


def main():
    print("=" * 78)
    print("[Phase 3 Showcase] Real-footage rendering verification")
    print("=" * 78)

    engine = ResolveAutomationEngine(timeout=600)
    results = {}

    clips = pick_long_clips(engine, n=5)
    if len(clips) < 4:
        print(f"[ERROR] Only {len(clips)} long clips found")
        return
    print(f"[OK] Selected {len(clips)} real clips:")
    for c in clips:
        print(f"     - {os.path.basename(c)} ({engine._get_media_duration(c):.1f}s)")

    ts = int(time.time())

    # ================================================================
    # 1. 节拍剪辑 beat_sync_demo.mp4
    # ================================================================
    print("\n" + "-" * 78)
    print("[1/5] Beat-sync editing (real AMV audio + real clips)")
    print("-" * 78)
    out_beat = os.path.join(OUTPUT_DIR, "beat_sync_demo.mp4")
    try:
        amv_audio_src = pick_amv_audio()
        audio_16s = os.path.join(engine._temp_dir, "bgm_16s.m4a")
        if amv_audio_src:
            # 提取真实 BGM 前 16 秒作为节拍音源
            subprocess.run(
                ["ffmpeg", "-y", "-i", amv_audio_src, "-t", "16",
                 "-vn", "-c:a", "aac", "-b:a", "192k", audio_16s],
                check=True, capture_output=True, timeout=60)
            print(f"[OK] Audio source: {os.path.basename(amv_audio_src)} (16s)")
            audio_path = audio_16s
        else:
            # 兜底：用真实素材自身的音频
            audio_path = clips[0]
            print("[WARN] No AMV audio found, fallback to clip audio")

        beats = engine.detect_beats(audio_path, bpm=100)
        print(f"[OK] Detected {len(beats)} beats")

        engine.beat_sync_edit(
            clip_paths=clips,
            audio_path=audio_path,
            output_path=out_beat,
            bpm=100,
            transition=TransitionConfig(type="flash", duration=0.15))
        results['beat_sync'] = probe(out_beat)
    except Exception as e:
        print(f"[FAIL] Beat sync: {e}")
        results['beat_sync'] = {'valid': False, 'error': str(e)}

    # ================================================================
    # 2. 动态速度曲线 speed_ramp_demo.mp4
    # ================================================================
    print("\n" + "-" * 78)
    print("[2/5] Dynamic speed ramp (bezier: 1.0x -> 2.0x -> 0.5x)")
    print("-" * 78)
    out_ramp = os.path.join(OUTPUT_DIR, "speed_ramp_demo.mp4")
    try:
        src = clips[0]
        orig_dur = engine._get_media_duration(src)
        engine.dynamic_speed_ramp(
            source_path=src,
            output_path=out_ramp,
            control_points=[(0.0, 1.0), (0.35, 2.0), (0.65, 2.0), (1.0, 0.5)])
        results['speed_ramp'] = probe(out_ramp)
        print(f"[OK] {orig_dur:.1f}s -> {results['speed_ramp'].get('duration', 0):.1f}s")
    except Exception as e:
        print(f"[FAIL] Speed ramp: {e}")
        results['speed_ramp'] = {'valid': False, 'error': str(e)}

    # ================================================================
    # 3. 高级转场 transitions_demo.mp4（whip_pan + glitch + flash）
    # ================================================================
    print("\n" + "-" * 78)
    print("[3/5] Advanced transitions (whip_pan -> glitch -> flash)")
    print("-" * 78)
    out_trans = os.path.join(OUTPUT_DIR, "transitions_demo.mp4")
    try:
        engine.render_with_transitions(
            clip_paths=clips[:4],
            output_path=out_trans,
            transitions=[
                TransitionConfig(type="whip_pan", duration=0.4),
                TransitionConfig(type="glitch", duration=0.4),
                TransitionConfig(type="flash", duration=0.3),
            ])
        results['transitions'] = probe(out_trans)
    except Exception as e:
        print(f"[FAIL] Transitions: {e}")
        results['transitions'] = {'valid': False, 'error': str(e)}

    # ================================================================
    # 4. 色彩科学 color_grade_demo.mp4（调色前后左右对比）
    # ================================================================
    print("\n" + "-" * 78)
    print("[4/5] Color science (Teal&Orange LUT + color wheel, side-by-side)")
    print("-" * 78)
    out_color = os.path.join(OUTPUT_DIR, "color_grade_demo.mp4")
    try:
        src = clips[1]
        codec = engine._get_encoder_args(quality="high")

        # 左侧：原始画面
        raw_left = os.path.join(engine._temp_dir, "color_left.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", src,
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
             *shlex.split(codec), "-r", "24", "-an", raw_left],
            check=True, capture_output=True, timeout=120)

        # 右侧：LUT + 色轮调色（走 resolve_engine 色彩管线）
        proj = f"ShowcaseColor_{ts}"
        engine.create_timeline_with_media(proj, "ColorTL", [src])
        lut_path = os.path.join(OUTPUT_DIR, "teal_orange.cube")
        engine.apply_lut_file(proj, 1, lut_path)
        engine.apply_color_wheel(proj, 1, ColorWheelConfig(
            shadows=(0.0, 0.06, 0.14),      # 暗部偏青
            midtones=(0.02, 0.0, -0.02),
            highlights=(0.12, 0.05, -0.07)  # 高光偏橙
        ))
        graded_right = os.path.join(engine._temp_dir, "color_right.mp4")
        engine.render_timeline(proj, graded_right, use_ffmpeg=True)
        engine.delete_project(proj)

        # 左右拼接对比（左=原片 右=调色）
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_left, "-i", graded_right,
             "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]",
             "-map", "[v]", *shlex.split(codec), "-an", out_color],
            check=True, capture_output=True, timeout=300)
        results['color_grade'] = probe(out_color)
        print("[OK] Left=original, Right=graded (Teal&Orange)")
    except Exception as e:
        print(f"[FAIL] Color grade: {e}")
        import traceback
        traceback.print_exc()
        results['color_grade'] = {'valid': False, 'error': str(e)}

    # ================================================================
    # 5. 关键帧动画 keyframe_demo.mp4（缩放+位移+旋转）
    # ================================================================
    print("\n" + "-" * 78)
    print("[5/5] Keyframe animation (zoom + position + rotation, bezier)")
    print("-" * 78)
    out_kf = os.path.join(OUTPUT_DIR, "keyframe_demo.mp4")
    try:
        src = clips[2]
        dur = engine._get_media_duration(src) or 3.0
        engine.set_keyframe_animation(
            source_path=src,
            output_path=out_kf,
            animations={
                'zoom': [Keyframe(0.0, 1.0), Keyframe(dur * 0.4, 1.7),
                         Keyframe(dur * 0.7, 1.3), Keyframe(dur, 1.8)],
                'x': [Keyframe(0.0, 0.3), Keyframe(dur * 0.5, 0.6), Keyframe(dur, 0.4)],
                'rotation': [Keyframe(0.0, 0.0), Keyframe(dur * 0.5, 3.0),
                             Keyframe(dur, 0.0)],
            },
            mode="bezier")
        results['keyframe'] = probe(out_kf)
    except Exception as e:
        print(f"[FAIL] Keyframe: {e}")
        results['keyframe'] = {'valid': False, 'error': str(e)}

    # ================================================================
    # 汇总：所有输出文件路径 / 大小 / 时长
    # ================================================================
    print("\n" + "=" * 78)
    print("[Final Report] Phase 3 Showcase outputs")
    print("=" * 78)
    print(f"{'Feature':<14} {'Status':<6} {'Duration':>9} {'Size':>8} {'Res':>10}  Path")
    print("-" * 100)
    all_pass = True
    for name, info in results.items():
        path = {
            'beat_sync': out_beat, 'speed_ramp': out_ramp, 'transitions': out_trans,
            'color_grade': out_color, 'keyframe': out_kf,
        }[name]
        if info.get('valid') and info['duration'] > 2.0:
            status = "PASS"
        else:
            status = "FAIL"
            all_pass = False
        dur = f"{info.get('duration', 0):.1f}s" if info.get('valid') else "-"
        size = f"{info.get('size_mb', 0):.1f}MB" if info.get('valid') else "-"
        res = f"{info.get('width')}x{info.get('height')}" if info.get('valid') else "-"
        print(f"{name:<14} {status:<6} {dur:>9} {size:>8} {res:>10}  {path}")
        if not info.get('valid'):
            print(f"{'':<14} reason: {str(info.get('error', 'unknown'))[:120]}")

    print("-" * 100)
    print(f"Overall: {'ALL 5 FEATURES PASSED' if all_pass else 'SOME FEATURES FAILED'}")
    return results


if __name__ == "__main__":
    main()
