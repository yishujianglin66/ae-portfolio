# -*- coding: utf-8 -*-
"""微复现: 验证无预补偿重构的链合成时长数学 (诊断 v7 168.08s vs 164.2s).

构造 3 段测试 clip (0.6s / 0.5s / 0.6s), 转场 fade 0.35+0.3,
链末 clip 含 Σt 补偿, 验证链输出 == Σd。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ai.production_director import DirectorSegment, ProductionDirector
from core.paths import ffmpeg_bin, ffprobe_bin


def make_clip(ff, out, dur, color):
    subprocess.run([ff, "-y", "-f", "lavfi",
                    "-i", f"color=c={color}:s=320x180:d={dur}",
                    "-vf", "format=yuv420p", "-c:v", "libx264",
                    "-preset", "veryfast", "-r", "24", out],
                   capture_output=True, check=True, timeout=60)


def probe(ffp, p):
    r = subprocess.run([ffp, "-v", "quiet", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main():
    ff, ffp = ffmpeg_bin(), ffprobe_bin()
    d = object.__new__(ProductionDirector)
    d.ffmpeg = ff
    d._probe_duration = lambda p: probe(ffp, p)

    tmp = Path(tempfile.mkdtemp())
    clips = []
    for i, (dur, color) in enumerate([(0.6, "red"), (0.5, "green"), (0.6, "blue")]):
        p = tmp / f"c{i}.mp4"
        make_clip(ff, str(p), dur, color)
        clips.append(str(p))
    # 转场: 进入seg1=fade0.35, seg2=fade0.30
    s0 = DirectorSegment(0, 0.0, 0.6, 0.6, "intro", 0.5, "", 0.0, "", None,
                         "cut", 1.0)
    s1 = DirectorSegment(1, 0.6, 1.1, 0.5, "intro", 0.5, "", 0.0, "", None,
                         "fade", 1.0)
    s1.transition_params = {"type": "fade", "duration": 0.35}
    s2 = DirectorSegment(2, 1.1, 1.7, 0.6, "intro", 0.5, "", 0.0, "", None,
                         "fade", 1.0)
    s2.transition_params = {"type": "fade", "duration": 0.30}
    group = [(clips[0], s0), (clips[1], s1), (clips[2], s2)]
    # 链末补偿: Σt = 0.65
    extra = 0.65
    p2 = tmp / "c2_ext.mp4"
    make_clip(ff, str(p2), 0.6 + extra, "blue")
    group = [(clips[0], s0), (clips[1], s1), (str(p2), s2)]

    durs = [probe(ffp, p) for p, _ in group]
    print("输入时长:", [round(x, 3) for x in durs],
          "Σd+extra:", round(sum(durs), 3))
    out = tmp / "chain.mp4"
    ok = d._xfade_chain(group, str(out))
    print("xfade_chain:", ok)
    actual = probe(ffp, str(out))
    expected = 0.6 + 0.5 + 0.6
    print(f"链输出: {actual:.3f}s  期望: {expected:.3f}s  "
          f"{'PASS' if abs(actual-expected) < 0.06 else 'FAIL (差 %.3f)' % (actual-expected)}")


if __name__ == "__main__":
    main()
