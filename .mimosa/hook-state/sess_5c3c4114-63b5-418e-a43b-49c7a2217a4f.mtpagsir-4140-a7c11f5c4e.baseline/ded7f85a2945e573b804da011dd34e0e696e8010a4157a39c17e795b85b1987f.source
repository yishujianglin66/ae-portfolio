"""
阶段3：专业级高级剪辑功能测试
=================================
对标百万播放量 AMV/MAD 作品的五大功能：
1. 精准节拍剪辑（beat_sync_edit）
2. 动态速度曲线（dynamic_speed_ramp，贝塞尔平滑）
3. 高级转场系统（8种：whip_pan/zoom/glitch/flash/morph/iris_wipe/light_leak/film_burn）
4. 色彩科学工作流（LUT + 色轮 + 色彩匹配）
5. 关键帧动画系统（zoom/x/y/rotation/opacity，多插值模式）
"""
import sys
import os
import time
import subprocess

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.resolve_engine import (
    ResolveAutomationEngine,
    TransitionConfig,
    ColorWheelConfig,
    Keyframe,
)

import pytest
pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve + 真实素材环境

OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
MEDIA_DIR = r"C:\VinlandClips"


def probe(filepath: str) -> dict:
    """ffprobe 验证"""
    cmd = ['ffprobe', '-v', 'error',
           '-show_entries', 'format=duration,size',
           '-show_entries', 'stream=width,height,codec_name',
           '-of', 'json', filepath]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode == 0:
            import json
            info = json.loads(r.stdout)
            v = info['streams'][0] if info['streams'] else {}
            return {'valid': True,
                    'duration': float(info['format']['duration']),
                    'size_mb': int(info['format']['size']) / 1024 / 1024,
                    'width': v.get('width'), 'height': v.get('height')}
    except Exception as e:
        return {'valid': False, 'error': str(e)}
    return {'valid': False}


def gen_teal_orange_lut(path: str, size: int = 9):
    """生成 Teal & Orange 电影感 3D LUT (.cube)"""
    lines = [f"LUT_3D_SIZE {size}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0"]
    for b in range(size):
        for g in range(size):
            for r in range(size):
                rn, gn, bn = r / (size - 1), g / (size - 1), b / (size - 1)
                lum = 0.299 * rn + 0.587 * gn + 0.114 * bn
                # 暗部偏青（teal）：提升 B/G，压 R
                # 亮部偏橙（orange）：提升 R，压 B
                teal = max(0.0, 0.5 - lum) * 0.6
                orange = max(0.0, lum - 0.5) * 0.7
                ro = min(1.0, rn - teal * 0.25 + orange * 0.5)
                go = min(1.0, gn + teal * 0.10 + orange * 0.12)
                bo = min(1.0, bn + teal * 0.35 - orange * 0.30)
                lines.append(f"{ro:.6f} {go:.6f} {bo:.6f}")
    with open(path, 'w') as f:
        f.write("\n".join(lines))
    print(f"[OK] Generated LUT: {os.path.basename(path)}")


def run_tests():
    print("=" * 80)
    print("[Phase 3] Professional Editing Features Test")
    print("=" * 80)

    engine = ResolveAutomationEngine(timeout=600)
    results = {}

    clips = []
    if os.path.isdir(MEDIA_DIR):
        for f in sorted(os.listdir(MEDIA_DIR)):
            if f.endswith('.mp4') and len(clips) < 4:
                clips.append(os.path.join(MEDIA_DIR, f))
    if len(clips) < 2:
        print("[ERROR] Need at least 2 clips")
        return

    ts = int(time.time())

    # ============================================================
    # Test 1: 精准节拍剪辑（120 BPM 节拍网格）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 1] Beat-sync editing (120 BPM grid)")
    print("-" * 60)
    out1 = os.path.join(OUTPUT_DIR, f"pro_beatsync_{ts}.mp4")
    try:
        # 用第一个片段作为节拍音源（提取其音频节奏）
        engine.beat_sync_edit(
            clip_paths=clips[:3],
            audio_path=clips[0],
            output_path=out1,
            bpm=120,
            transition=TransitionConfig(type="flash", duration=0.2))
        info = probe(out1)
        if info['valid']:
            print(f"[OK] Beat sync: {info['duration']:.1f}s, {info['size_mb']:.1f}MB")
            results['beat_sync'] = 'PASS'
        else:
            results['beat_sync'] = 'FAIL'
    except Exception as e:
        print(f"[ERROR] Beat sync failed: {e}")
        results['beat_sync'] = 'FAIL'

    # ============================================================
    # Test 2: 动态速度曲线（加速→减速 贝塞尔平滑）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 2] Dynamic speed ramp (bezier smooth)")
    print("-" * 60)
    out2 = os.path.join(OUTPUT_DIR, f"pro_speedramp_{ts}.mp4")
    try:
        orig_dur = engine._get_media_duration(clips[0])
        engine.dynamic_speed_ramp(
            source_path=clips[0],
            output_path=out2,
            control_points=[(0.0, 1.0), (0.35, 2.5), (0.65, 2.5), (1.0, 0.5)])
        info = probe(out2)
        if info['valid']:
            print(f"[OK] Speed ramp: {orig_dur:.1f}s -> {info['duration']:.1f}s, "
                  f"{info['size_mb']:.1f}MB")
            results['speed_ramp'] = 'PASS'
        else:
            results['speed_ramp'] = 'FAIL'
    except Exception as e:
        print(f"[ERROR] Speed ramp failed: {e}")
        results['speed_ramp'] = 'FAIL'

    # ============================================================
    # Test 3: 高级转场系统（8种全部验证）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 3] Advanced transitions (all 8 types)")
    print("-" * 60)
    transition_results = {}
    for t_type in engine.XFADE_TRANSITION_MAP.keys():
        out_t = os.path.join(OUTPUT_DIR, f"pro_trans_{t_type}_{ts}.mp4")
        try:
            engine.apply_transition(clips[0], clips[1], out_t,
                                    transition=t_type, duration=0.5)
            info = probe(out_t)
            if info['valid']:
                print(f"[OK] {t_type}: {info['duration']:.1f}s")
                transition_results[t_type] = 'PASS'
            else:
                transition_results[t_type] = 'FAIL'
        except Exception as e:
            print(f"[FAIL] {t_type}: {str(e)[:80]}")
            transition_results[t_type] = 'FAIL'

    passed = sum(1 for v in transition_results.values() if v == 'PASS')
    print(f"[Summary] Transitions: {passed}/{len(transition_results)} passed")
    results['transitions'] = f"{passed}/8"

    # 转场链（flash → zoom → morph）
    out_chain = os.path.join(OUTPUT_DIR, f"pro_trans_chain_{ts}.mp4")
    try:
        engine.render_with_transitions(
            clip_paths=clips[:4],
            output_path=out_chain,
            transitions=[
                TransitionConfig(type="flash", duration=0.3),
                TransitionConfig(type="zoom", duration=0.5),
                TransitionConfig(type="morph", duration=0.5),
            ])
        info = probe(out_chain)
        if info['valid']:
            print(f"[OK] Transition chain: {info['duration']:.1f}s, {info['size_mb']:.1f}MB")
            results['transition_chain'] = 'PASS'
        else:
            results['transition_chain'] = 'FAIL'
    except Exception as e:
        print(f"[ERROR] Transition chain failed: {e}")
        results['transition_chain'] = 'FAIL'

    # ============================================================
    # Test 4: 色彩科学工作流（LUT + 色轮 + 色彩匹配）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 4] Color science workflow (LUT + color wheel + match)")
    print("-" * 60)
    try:
        # 生成 Teal & Orange LUT
        lut_path = os.path.join(OUTPUT_DIR, "teal_orange.cube")
        gen_teal_orange_lut(lut_path)

        # 色彩匹配：clip2 匹配 clip1 的色彩风格
        match_cfg = engine.match_color(clips[1], clips[0])
        print(f"[OK] Color match correction: midtones={match_cfg.midtones}")

        # 创建项目并应用色彩（FFmpeg 渲染路径）
        proj = f"ProColor_{ts}"
        engine.create_timeline_with_media(proj, "ColorTL", clips[:2])
        engine.apply_lut_file(proj, 1, lut_path)
        engine.apply_color_wheel(proj, 1, ColorWheelConfig(
            shadows=(0.0, 0.05, 0.12),      # 暗部偏青
            midtones=(0.02, 0.0, -0.02),
            highlights=(0.10, 0.04, -0.06)  # 高光偏橙
        ))
        engine.apply_color_wheel(proj, 2, match_cfg)

        out4 = os.path.join(OUTPUT_DIR, f"pro_color_{ts}.mp4")
        engine.render_timeline(proj, out4, use_ffmpeg=True)
        info = probe(out4)
        if info['valid']:
            print(f"[OK] Color science render: {info['duration']:.1f}s, {info['size_mb']:.1f}MB")
            results['color_science'] = 'PASS'
        else:
            results['color_science'] = 'FAIL'
        engine.delete_project(proj)
    except Exception as e:
        print(f"[ERROR] Color science failed: {e}")
        import traceback
        traceback.print_exc()
        results['color_science'] = 'FAIL'

    # ============================================================
    # Test 5: 关键帧动画系统（zoom + rotation，贝塞尔模式）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 5] Keyframe animation (zoom + rotation, bezier)")
    print("-" * 60)
    out5 = os.path.join(OUTPUT_DIR, f"pro_keyframe_{ts}.mp4")
    try:
        dur = engine._get_media_duration(clips[0]) or 3.0
        engine.set_keyframe_animation(
            source_path=clips[0],
            output_path=out5,
            animations={
                'zoom': [Keyframe(0.0, 1.0), Keyframe(dur * 0.5, 1.6), Keyframe(dur, 1.2)],
                'x': [Keyframe(0.0, 0.3), Keyframe(dur, 0.7)],
                'rotation': [Keyframe(0.0, 0.0), Keyframe(dur * 0.5, 4.0), Keyframe(dur, 0.0)],
            },
            mode="bezier")
        info = probe(out5)
        if info['valid']:
            print(f"[OK] Keyframe animation: {info['duration']:.1f}s, {info['size_mb']:.1f}MB")
            results['keyframes'] = 'PASS'
        else:
            results['keyframes'] = 'FAIL'
    except Exception as e:
        print(f"[ERROR] Keyframe animation failed: {e}")
        import traceback
        traceback.print_exc()
        results['keyframes'] = 'FAIL'

    # ============================================================
    # 汇总
    # ============================================================
    print("\n" + "=" * 80)
    print("[Summary] Phase 3 Results")
    print("=" * 80)
    for k, v in results.items():
        mark = "[OK]" if (v == 'PASS' or '/' in str(v) and v.startswith(str(len([1])))) else "[--]"
        print(f"  {k:20s}: {v}")

    return results


if __name__ == "__main__":
    run_tests()
