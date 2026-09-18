# -*- coding: utf-8 -*-
"""render_gate.py — 自动验收闸门 (2026-09-03)

每版渲染后自动测量六项指标, 不过闸不出片 — 终结"用户人肉验收+猜测定位"循环。
本会话 45 版迭代沉淀的全部量具合成一处。

用法: python scripts/render_gate.py output/unified_run45 run45 [--bgm xxx.mp3]
退出码 0=过闸 1=有未过项
"""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

PROJ = Path(__file__).resolve().parent.parent
FF = "C:/ffmpeg/bin/ffmpeg.exe"


def _audio(p):
    """按原生声道/采样率解码, 返回 (frames, channels)。

    曾用 `-ac 1 -ar 22050` 下混: 双声道求平均会掩盖单边削波
    (run61_final 真峰 1.000=0.0dBFS, 下混后只报 0.933, 无削波误判 PASS),
    且 22050 采样使 4000-12000Hz 频段的 11025Hz 以上部分不存在。
    """
    import soundfile as sf
    r = subprocess.run([FF, "-y", "-i", str(p), "-vn", "-f", "wav", "-"],
                       capture_output=True, timeout=300)
    y, sr = sf.read(io.BytesIO(r.stdout), dtype="float32")
    return (y.reshape(-1, 1) if y.ndim == 1 else y), sr


def _band(y, sr, lo, hi):
    from numpy.fft import irfft, rfft
    F = rfft(y); fr = np.fft.rfftfreq(len(y), 1 / sr)
    F[(fr < lo) | (fr > hi)] = 0
    return float(np.sum(irfft(F, len(y)) ** 2))


def main():
    run_dir = Path(sys.argv[1]); tag = sys.argv[2]
    bgm = sys.argv[sys.argv.index("--bgm") + 1] if "--bgm" in sys.argv else None
    pr = json.loads((run_dir / "production_report.json").read_text(encoding="utf-8"))
    segs = sorted(pr["script"]["segments"], key=lambda s: s["start_time"])
    starts = [s["start_time"] for s in segs if s["start_time"] > 0.05]
    final = run_dir / f"{tag}_final.mp4"
    if "--final" in sys.argv:   # v9: 曲线版交付件名字带版本后缀, 用 --final 指定被测文件
        final = Path(sys.argv[sys.argv.index("--final") + 1])
    checks = []
    print(f"  [被测] {final}")

    def add(name, ok, detail):
        checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # 1 音频纯净(鼓点保留 + 无削波)
    ch, sr = _audio(final)
    y = ch.mean(axis=1)
    add("鼓点保留", _band(y, sr, 4000, 12000) > 0,
        f"高频能量 {_band(y, sr, 4000, 12000):.1f}")
    peak = float(np.abs(ch).max())
    clip_pct = float(np.mean(np.abs(ch) >= 0.999) * 100)
    add("无削波", peak <= 0.99,
        f"逐声道 peak {peak:.3f} ({20*np.log10(max(peak,1e-9)):+.2f}dBFS) "
        f"顶满采样 {clip_pct:.4f}%")

    # 2 切点-鼓点对齐
    import librosa
    yh, yp = librosa.effects.hpss(y)
    on = librosa.onset.onset_detect(y=yp, sr=sr, units="time", backtrack=False,
                                    hop_length=256, delta=0.03, wait=2)
    al = sum(1 for c in starts if any(abs(c - o) <= 0.08 for o in on)) / len(starts)
    add("切点踩打击乐", al >= 0.65, f"{al:.0%} ±80ms (阈65%)")

    # 3 决斗段密度分层
    burst = [s for s in segs if 13 <= s["start_time"] < 30]
    if burst:
        g = [burst[i+1]["start_time"] - burst[i]["start_time"] for i in range(len(burst)-1)]
        tiers = len(set(round(x, 1) for x in g))
        # 快档密度(run45 验证基线校准): 呼吸语法的价值在档位而非均值 —
        # 快档(≤0.26s)切口数占比与等效速率才是"急奏跟上了"的度量
        fast = [x for x in g if x <= 0.26]
        fast_ratio = len(fast) / max(len(g), 1)
        fast_rate = 1 / np.mean(fast) if fast else 0
        add("决斗段快档", fast_ratio >= 0.25 and fast_rate >= 3.8,
            f"快档占比 {fast_ratio:.0%} 等效 {fast_rate:.1f}切/s (阈25%/3.8)")
        add("变速档位", tiers >= 3, f"{tiers} 档间隔 (阈3) {sorted(set(round(x,2) for x in g))[:6]}")
    # 4 速度分层 (分半程: 全片档位并集会被前半段的丰富度掩盖后半程的平速墙)
    def _tiers(sub):
        return sorted(set(round(s.get("speed", 1.0), 2) for s in sub))
    mid = segs[-1]["end_time"] / 2
    t1, t2 = _tiers([s for s in segs if s["start_time"] < mid]), \
             _tiers([s for s in segs if s["start_time"] >= mid])
    add("速度分层", len(t1) >= 3 and len(t2) >= 3,
        f"前半 {len(t1)}档 {t1[:6]} | 后半 {len(t2)}档 {t2[:6]} (各阈3)")
    # 5 隐形切点(亮度归一化, 暗画面误报校正)
    def grab(t):
        r = subprocess.run([FF, "-ss", f"{t:.3f}", "-i", str(final), "-frames:v", "1",
                            "-vf", "scale=48:27,normalize", "-f", "rawvideo",
                            "-pix_fmt", "gray", "-"], capture_output=True, timeout=60)
        v = np.frombuffer(r.stdout, dtype=np.uint8).astype(np.float32)
        return (v - v.mean()) / (v.std() + 1e-6)  # 亮度归一化
    # 校准(2026-09-04): 采样效果帧之后(t+3帧) — whip/闪帧的头几帧是
    # 故意模糊/全色, 不能算"隐形切点"; 对比 t-1 vs t+3 测真实内容切换
    vis = sum(1 for t in starts[::max(1, len(starts)//12)]
              if abs(grab(t - 1/24) - grab(t + 3/24)).mean() > 0.35)
    n_chk = min(12, len(starts))
    add("切点可见", vis >= n_chk * 0.55, f"{vis}/{n_chk} 帧差可见 (阈55%, 暗画面指标保守)")

    npass = sum(checks)
    print(f"\n闸门: {npass}/{len(checks)} 通过" + (" [ACCEPT]" if npass == len(checks) else " [REJECT]"))
    return 0 if npass == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
