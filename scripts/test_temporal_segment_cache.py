# -*- coding: utf-8 -*-
"""分段缓存端到端测试 — 冷启动一致性 + 裁切复用率 (2026-08-14)

用法:
    py -3.12 scripts/test_temporal_segment_cache.py [test_dir]
"""
import os
import shutil
import sys
import time
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CACHE_ROOT = Path(__file__).resolve().parent.parent / "cache" / "temporal_segments"


def _make_videos(d: Path) -> tuple:
    ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"
    full = d / "full.mp4"
    trimmed_head = d / "trimmed_head.mp4"   # 裁头部 10s
    trimmed_mid = d / "trimmed_mid.mp4"     # 裁中间 10-14s (重编码)
    subprocess_run = None
    import subprocess
    def run(args):
        r = subprocess.run(args, capture_output=True, timeout=180)
        assert r.returncode == 0, r.stderr.decode(errors="replace")[:400]
    run([ffmpeg, "-y", "-f", "lavfi", "-i",
         "testsrc2=size=640x360:rate=30:duration=22",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=22",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         str(full)])
    # 裁头部 10s → 12s (流拷贝: 帧内容与 full 的 10-22s 完全一致)
    run([ffmpeg, "-y", "-ss", "10", "-i", str(full), "-c", "copy",
         str(trimmed_head)])
    # 裁中间: 0-10s + 14-22s 拼接 → 18s (重编码, 帧内容与 full 几乎一致)
    run([ffmpeg, "-y", "-i", str(full), "-vf",
         "select='lt(t,10)+gte(t,14)',setpts=N/FRAME_RATE/TB",
         "-af", "aselect='lt(t,10)+gte(t,14)',asetpts=N/SR/TB",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         str(trimmed_mid)])
    return full, trimmed_head, trimmed_mid


def _analyze_full(analyzer, video):
    """整文件分析 (基线)。"""
    return analyzer.analyze_motion(str(video)), analyzer.detect_shot_structure(str(video))


def main():
    from core.temporal_analyzer import TemporalAnalyzer
    from core.temporal_segment_cache import analyze_cached

    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="aekv_segtest_"))
    full, trimmed_head, trimmed_mid = _make_videos(d)
    analyzer = TemporalAnalyzer()

    # 清缓存池, 保证从冷启动开始
    if CACHE_ROOT.exists():
        shutil.rmtree(CACHE_ROOT, ignore_errors=True)

    print("=" * 64)
    print("1. 冷启动: full.mp4 分段缓存分析 (全 miss, 与整文件等价)")
    t0 = time.time()
    mp_full, ss_full = analyze_cached(analyzer, str(full))
    t_seg_cold = time.time() - t0
    print(f"   冷启动耗时 {t_seg_cold:.1f}s | 运镜={mp_full.dominant_motion.value} "
          f"| 镜头={ss_full.total_shots} | ASL={ss_full.asl:.2f}s")

    t0 = time.time()
    mp_ref, ss_ref = _analyze_full(analyzer, full)
    t_full = time.time() - t0
    print(f"   整文件基线 {t_full:.1f}s | 运镜={mp_ref.dominant_motion.value} "
          f"| 镜头={ss_ref.total_shots} | ASL={ss_ref.asl:.2f}s")

    # 一致性断言: 聚合指标应完全一致
    assert mp_full.avg_magnitude == mp_ref.avg_magnitude, \
        f"avg_mag 不一致: {mp_full.avg_magnitude} vs {mp_ref.avg_magnitude}"
    assert mp_full.max_magnitude == mp_ref.max_magnitude
    assert mp_full.dominant_motion == mp_ref.dominant_motion
    assert ss_full.total_shots == ss_ref.total_shots, \
        f"shots 不一致: {ss_full.total_shots} vs {ss_ref.total_shots}"
    assert ss_full.asl == ss_ref.asl, f"ASL 不一致: {ss_full.asl} vs {ss_ref.asl}"
    print("   ✅ 冷启动与整文件分析聚合指标完全一致")

    print()
    print("2. 裁头部 10s (流拷贝): trimmed_head.mp4 复用率")
    blocks_before = len(list((CACHE_ROOT / "blocks").glob("*.pkl")))
    t0 = time.time()
    mp_h, ss_h = analyze_cached(analyzer, str(trimmed_head))
    t_hit = time.time() - t0
    blocks_after = len(list((CACHE_ROOT / "blocks").glob("*.pkl")))
    print(f"   耗时 {t_hit:.1f}s (冷启动 {t_seg_cold:.1f}s) | "
          f"新块数 {blocks_after - blocks_before} | "
          f"镜头={ss_h.total_shots} | ASL={ss_h.asl:.2f}s")
    # trimmed_head 12s → 3 块 (5s), 内容 = full 的 10-22s → 全部指纹命中
    assert blocks_after == blocks_before, \
        f"期望全命中(无新块), 实际新增 {blocks_after - blocks_before}"
    print("   ✅ 裁头部后全部块命中 (0 块重算, 无新块落盘)")

    # 结果与整文件分析该文件应近似一致
    # 注: 复用块首采样点 prev 与整文件分析不完全连续(差 1 采样点 0.1s),
    #     聚合值存在 4 位小数级微差, 断言用近似相等
    mp_h_ref, ss_h_ref = _analyze_full(analyzer, trimmed_head)
    assert abs(mp_h.avg_magnitude - mp_h_ref.avg_magnitude) < 0.01, \
        f"avg_mag: {mp_h.avg_magnitude} vs {mp_h_ref.avg_magnitude}"
    assert abs(mp_h.max_magnitude - mp_h_ref.max_magnitude) < 0.05
    assert ss_h.total_shots == ss_h_ref.total_shots
    print("   ✅ 命中路径聚合指标与整文件分析一致 (边界 ±1 采样点误差内)")

    print()
    print("3. 裁中间 10-14s (重编码): trimmed_mid.mp4 复用率")
    t0 = time.time()
    mp_m, ss_m = analyze_cached(analyzer, str(trimmed_mid))
    t_mid = time.time() - t0
    blocks_mid = len(list((CACHE_ROOT / "blocks").glob("*.pkl")))
    print(f"   耗时 {t_mid:.1f}s | 池中总块 {blocks_mid} (原 {blocks_after}) | "
          f"镜头={ss_m.total_shots} | ASL={ss_m.asl:.2f}s")
    # trimmed_mid 18s → 4 块: 0-5,5-10(原0-5,5-10命中), 10-15(原14-19≈新,miss),
    # 15-18(原19-22≈新,miss)。重编码像素有细微差异, 指纹可能部分命中。
    mp_m_ref, ss_m_ref = _analyze_full(analyzer, trimmed_mid)
    assert abs(mp_m.avg_magnitude - mp_m_ref.avg_magnitude) < 0.01, \
        f"avg_mag: {mp_m.avg_magnitude} vs {mp_m_ref.avg_magnitude}"
    assert abs(mp_m.max_magnitude - mp_m_ref.max_magnitude) < 0.05
    assert ss_m.total_shots == ss_m_ref.total_shots
    print("   ✅ 重编码裁切后聚合指标与整文件分析一致 (边界 ±1 采样点误差内)")

    print()
    print("=" * 64)
    print(f"测试通过 ✅  测试视频目录: {d} (可删)")
    print(f"块池位置: {CACHE_ROOT / 'blocks'} (共 {blocks_mid} 块)")


if __name__ == "__main__":
    main()
