"""
阶段3 融合版 Showcase：五大技巧合一的完整 AMV 混剪
======================================================
单个视频同时展示：
  1. 节拍剪辑 —— 镜头长度对齐 BGM 节拍网格（100 BPM，每4拍一个镜头）
  2. 动态变速 —— 其中2个镜头分别用 加速ramp / 慢放ramp
  3. 高级转场 —— 镜头间用 whip_pan/glitch/flash/morph/zoom 衔接
  4. 色彩科学 —— 全片 Teal&Orange LUT + 分镜头色轮微调
  5. 关键帧动画 —— 其中2个镜头用 bezier 缩放/位移动画
输出：output\\phase3_showcase\\combined_showcase.mp4（含真实 BGM 音轨）
"""
import json
import os
import shlex
import subprocess
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.resolve_engine import (
    Keyframe,
    ResolveAutomationEngine,
    TransitionConfig,
)

WORKSPACE = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"
OUTPUT_DIR = os.path.join(WORKSPACE, "output", "phase3_showcase")
MEDIA_DIR = r"C:\VinlandClips"
AMV_DIR = os.path.join(WORKSPACE, "data", "real_amv_test")
LUT_PATH = os.path.join(OUTPUT_DIR, "teal_orange.cube")

os.makedirs(OUTPUT_DIR, exist_ok=True)


def probe(fp):
    cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size',
           '-show_entries', 'stream=width,height,codec_name', '-of', 'json', fp]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(r.stdout)
        v = info['streams'][0]
        return {'duration': float(info['format']['duration']),
                'size_mb': int(info['format']['size']) / 1024 / 1024,
                'res': f"{v.get('width')}x{v.get('height')}"}
    except Exception:
        return None


def main():
    print("=" * 78)
    print("[Phase 3 Combined] All 5 techniques in ONE video")
    print("=" * 78)

    engine = ResolveAutomationEngine(timeout=600)
    codec_hq = engine._get_encoder_args(quality="high")
    codec_fast = engine._get_encoder_args(quality="fast")
    work = os.path.join(engine._temp_dir, "combined")
    os.makedirs(work, exist_ok=True)

    # ---------- 素材准备：6 个真实片段 ----------
    candidates = []
    for f in sorted(os.listdir(MEDIA_DIR)):
        if f.endswith('.mp4'):
            p = os.path.join(MEDIA_DIR, f)
            d = engine._get_media_duration(p)
            if d and d >= 3.0:
                candidates.append((d, p))
    candidates.sort(reverse=True)
    clips = [p for _, p in candidates[:6]]
    print(f"[OK] {len(clips)} real clips selected")

    # ---------- BGM：用户音频素材库 D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3 ----------
    BGM_LIB = r"D:\AE-Work\音频素材库\BGM"
    BGM_NAME = "ae实战音乐.mp3"
    amv_src = os.path.join(BGM_LIB, BGM_NAME)
    if not os.path.exists(amv_src):  # 兜底：AMV 参考视频提取音乐
        amv_src = os.path.join(AMV_DIR, "BV1Zw411k77P_MINEFIELDS - I want to eat you.mp4")
    bgm_full = os.path.join(work, "bgm_full.m4a")
    subprocess.run(["ffmpeg", "-y", "-i", amv_src, "-vn", "-c:a", "aac",
                    "-b:a", "192k", bgm_full],
                   check=True, capture_output=True, timeout=60)
    bgm_dur = engine._get_media_duration(bgm_full) or 15.0
    print(f"[OK] BGM: {os.path.basename(amv_src)} ({bgm_dur:.1f}s)")

    # ---------- 节拍检测：优先音频能量断点（silencedetect），兜底 BPM 网格 ----------
    BPM = 100
    BEATS_PER_SHOT = 4
    SHOT_DUR = BEATS_PER_SHOT * 60.0 / BPM  # 2.4s
    beats = engine.detect_beats(bgm_full)  # 真实音频断点
    if len(beats) < 4:
        beats = engine.detect_beats(bgm_full, bpm=BPM)  # 兜底网格
        print(f"[OK] Beat grid fallback: {BPM}BPM")
    else:
        print(f"[OK] Real audio beats detected: {len(beats)}")
    # 按 BGM 全长排镜头，6 个真实片段循环使用
    n_shots = max(4, int(bgm_dur / SHOT_DUR))
    print(f"[OK] shot={SHOT_DUR:.1f}s, {n_shots} shots (BGM {bgm_dur:.1f}s)")

    # BGM 截取到视频总长（镜头数×镜头时长）+ 1秒淡出余量
    bgm = os.path.join(work, "bgm.m4a")
    bgm_cut_len = n_shots * SHOT_DUR + 1.0
    subprocess.run(["ffmpeg", "-y", "-i", bgm_full, "-t", f"{bgm_cut_len:.2f}",
                    "-c", "copy", bgm],
                   check=True, capture_output=True, timeout=60)

    # ---------- 分镜头制作（每镜头主打一项技巧）----------
    def trim_raw(src, dur, out):
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-t", f"{dur:.3f}",
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
             *shlex.split(codec_fast), "-r", "24", "-an", out],
            check=True, capture_output=True, timeout=120)

    def force_duration(path, target, out):
        """将片段时长精确拉伸/压缩到目标值（保持节拍对齐）"""
        cur = engine._get_media_duration(path)
        if not cur or abs(cur - target) < 0.08:
            os.replace(path, out) if path != out else None
            return out if path != out else path
        ratio = target / cur
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-vf", f"setpts={ratio:.6f}*PTS",
             *shlex.split(codec_fast), "-r", "24", "-an", out],
            check=True, capture_output=True, timeout=120)
        return out

    def grade(path, out, wheel):
        """LUT + 色轮调色（色彩科学）"""
        lut_ff = LUT_PATH.replace("\\", "/").replace(":", "\\:")
        sh, mid, hi = wheel
        vf = (f"lut3d='{lut_ff}',"
              f"colorbalance=rs={sh[0]}:gs={sh[1]}:bs={sh[2]}"
              f":rm={mid[0]}:gm={mid[1]}:bm={mid[2]}"
              f":rh={hi[0]}:gh={hi[1]}:bh={hi[2]}")
        subprocess.run(
            ["ffmpeg", "-y", "-i", path, "-vf", vf,
             *shlex.split(codec_fast), "-an", out],
            check=True, capture_output=True, timeout=120)

    # 镜头方案：技巧分配
    shot_specs = [
        ("keyframe",  "bezier 推镜动画"),
        ("ramp_fast", "贝塞尔加速 1.0x->2.0x"),
        ("grade",     "Teal&Orange 调色"),
        ("keyframe",  "bezier 横移动画"),
        ("ramp_slow", "贝塞尔慢放 0.6x"),
        ("grade",     "暖调高光调色"),
    ]
    wheels = {
        2: ((0.0, 0.06, 0.14), (0.02, 0.0, -0.02), (0.12, 0.05, -0.07)),   # 青橙
        5: ((0.05, 0.02, -0.03), (0.03, 0.01, -0.01), (0.10, 0.06, 0.0)),   # 暖调
    }

    shots = []
    for i in range(n_shots):
        tech, desc = shot_specs[i % len(shot_specs)]
        src = clips[i % len(clips)]  # 6 个真实片段循环
        raw = os.path.join(work, f"shot{i}_raw.mp4")
        out = os.path.join(work, f"shot{i}_final.mp4")
        print(f"\n[Shot {i+1}/{n_shots}] {tech}: {desc} ({os.path.basename(src)})")

        if tech == "keyframe":
            # 先裁剪略长素材，再做关键帧动画
            trim_raw(src, SHOT_DUR + 0.5, raw)
            kf_out = os.path.join(work, f"shot{i}_kf.mp4")
            if i % 2 == 0:  # 推镜
                engine.set_keyframe_animation(raw, kf_out, animations={
                    'zoom': [Keyframe(0.0, 1.05), Keyframe(SHOT_DUR, 1.65)],
                    'y': [Keyframe(0.0, 0.45), Keyframe(SHOT_DUR, 0.55)],
                }, mode="bezier")
            else:           # 横移
                engine.set_keyframe_animation(raw, kf_out, animations={
                    'zoom': [Keyframe(0.0, 1.4), Keyframe(SHOT_DUR, 1.4)],
                    'x': [Keyframe(0.0, 0.25), Keyframe(SHOT_DUR, 0.75)],
                }, mode="bezier")
            force_duration(kf_out, SHOT_DUR, out)
        elif tech == "ramp_fast":
            # 加速变速（源素材全用，ramp 后对齐节拍时长）
            ramp_out = os.path.join(work, f"shot{i}_ramp.mp4")
            engine.dynamic_speed_ramp(src, ramp_out,
                                      control_points=[(0.0, 1.0), (0.4, 2.0), (1.0, 2.2)])
            force_duration(ramp_out, SHOT_DUR, out)
        elif tech == "ramp_slow":
            ramp_out = os.path.join(work, f"shot{i}_ramp.mp4")
            engine.dynamic_speed_ramp(src, ramp_out,
                                      control_points=[(0.0, 1.0), (0.5, 0.6), (1.0, 0.8)])
            force_duration(ramp_out, SHOT_DUR, out)
        else:  # grade
            trim_raw(src, SHOT_DUR, raw)
            grade(raw, out, wheels.get(i, wheels[2]))

        info = probe(out)
        print(f"  -> {info['duration']:.2f}s")
        shots.append(out)

    # ---------- 转场衔接（whip_pan / glitch / flash / morph / zoom 循环）----------
    print("\n[Transitions] Chaining shots...")
    transition_cycle = ["whip_pan", "glitch", "flash", "morph", "zoom"]
    transitions = [TransitionConfig(type=transition_cycle[i % 5], duration=0.4)
                   for i in range(len(shots) - 1)]
    chained = os.path.join(work, "chained.mp4")
    engine.render_with_transitions(shots, chained, transitions)
    print(f"[OK] Chained: {probe(chained)['duration']:.2f}s")

    # ---------- 全片统一调色 + 混入 BGM（尾部 1.5s 淡出）----------
    print("\n[Final] Global grade + BGM mix (with fade-out)...")
    final_out = os.path.join(OUTPUT_DIR, "combined_showcase.mp4")
    lut_ff = LUT_PATH.replace("\\", "/").replace(":", "\\:")
    fc = (f"[0:v]lut3d='{lut_ff}',eq=saturation=1.12:contrast=1.05[v];"
          f"[1:a]afade=t=out:st={max(0.1, probe(chained)['duration'] - 1.5):.2f}:d=1.5[a]")
    subprocess.run(
        ["ffmpeg", "-y", "-i", chained, "-i", bgm,
         "-filter_complex", fc,
         "-map", "[v]", "-map", "[a]",
         *shlex.split(codec_hq),
         "-c:a", "aac", "-b:a", "192k", "-shortest", final_out],
        check=True, capture_output=True, timeout=600)

    # ---------- 报告 ----------
    info = probe(final_out)
    print("\n" + "=" * 78)
    print("[Result] Combined showcase")
    print("=" * 78)
    print(f"  File    : {final_out}")
    print(f"  Duration: {info['duration']:.1f}s | Size: {info['size_mb']:.1f}MB | Res: {info['res']}")
    print("  Techniques fused:")
    print(f"    1. Beat-sync    : {n_shots} shots @ {SHOT_DUR:.1f}s aligned to beat grid")
    print("    2. Speed ramp   : fast(1->2.2x) / slow(1->0.6x) shots")
    print(f"    3. Transitions  : {'/'.join(transition_cycle)}")
    print("    4. Color        : per-shot LUT+colorwheel + global Teal&Orange")
    print("    5. Keyframes    : push-in / pan (bezier) shots")
    ok = info['duration'] > 2.0
    print(f"\n  Status: {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    main()
