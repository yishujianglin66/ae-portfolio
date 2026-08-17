# -*- coding: utf-8 -*-
"""运镜分类分段缓存测试 — 冷启动可用性 + 裁切复用率 (2026-08-14)

用法:
    py -3.12 scripts/test_camera_segment_cache.py [test_dir]
"""
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CAM_CACHE = Path(__file__).resolve().parent.parent / "cache" / "camera_segments"
CAM_BLOCKS = CAM_CACHE / "blocks"


def _make_videos(d: Path) -> tuple:
    ffmpeg = r"C:\ffmpeg\bin\ffmpeg.exe"

    def run(args):
        r = subprocess.run(args, capture_output=True, timeout=180)
        assert r.returncode == 0, r.stderr.decode(errors="replace")[:400]

    # 22s 测试视频: 前 11s 向左平移, 后 11s 静止 (可区分运镜)
    full = d / "full.mp4"
    run([ffmpeg, "-y", "-f", "lavfi", "-i",
         "testsrc2=size=640x360:rate=30:duration=22",
         "-vf", "crop=640:300:0:0,scroll=horizontal=0.1",
         "-c:v", "libx264", "-preset", "ultrafast", str(full)])
    trimmed = d / "trimmed_head.mp4"
    run([ffmpeg, "-y", "-ss", "10", "-i", str(full), "-c", "copy", str(trimmed)])
    return full, trimmed


def main():
    from core.camera_movement_classifier import classify_video, classify_video_cached

    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="aekv_camseg_"))
    full, trimmed = _make_videos(d)

    if CAM_CACHE.exists():
        shutil.rmtree(CAM_CACHE, ignore_errors=True)

    print("=" * 64)
    print("1. 冷启动: full.mp4 分段分类 (全 miss)")
    t0 = time.time()
    r_seg = classify_video_cached(str(full))
    t_seg = time.time() - t0
    print(f"   分段冷启动 {t_seg:.1f}s | dominant={r_seg['dominant']} "
          f"| conf={r_seg['confidence']} | per_segment={len(r_seg['per_segment'])}")
    t0 = time.time()
    r_full = classify_video(str(full))
    t_full = time.time() - t0
    print(f"   整文件 {t_full:.1f}s | dominant={r_full['dominant']} "
          f"| conf={r_full['confidence']} | per_segment={len(r_full['per_segment'])}")
    # 分段(5s块,每块最多50帧)与整文件(全片50帧)采样帧集不同,
    # 帧位移统计量不可直接比; 语义级断言: dominant 一致 + 方向符号一致
    assert r_seg["dominant"] == r_full["dominant"], \
        f"dominant 不一致: {r_seg['dominant']} vs {r_full['dominant']}"
    s_dx, f_dx = r_seg["flow_stats"].get("mean_dx", 0), r_full["flow_stats"].get("mean_dx", 0)
    assert (s_dx > 0) == (f_dx > 0) or abs(s_dx) < 1 or abs(f_dx) < 1, \
        f"mean_dx 方向不一致: {s_dx} vs {f_dx}"
    print("   ✅ 分段冷启动可用, dominant 与整文件一致, 运动方向一致")

    print()
    print("2. 裁头部 10s (流拷贝): trimmed_head.mp4 复用率")
    blocks_before = len(list(CAM_BLOCKS.glob("*.pkl")))
    t0 = time.time()
    r_t = classify_video_cached(str(trimmed))
    t_hit = time.time() - t0
    blocks_after = len(list(CAM_BLOCKS.glob("*.pkl")))
    print(f"   耗时 {t_hit:.1f}s (冷启动 {t_seg:.1f}s) | "
          f"新块 {blocks_after - blocks_before} | dominant={r_t['dominant']}")
    assert blocks_after == blocks_before, \
        f"期望全命中(0 新块), 实际新增 {blocks_after - blocks_before}"
    print("   ✅ 裁头部后全部块命中 (0 块重算)")

    print()
    print("=" * 64)
    print(f"测试通过 ✅  测试视频目录: {d} (可删)")
    print(f"块池位置: {CAM_BLOCKS} (共 {blocks_after} 块)")


if __name__ == "__main__":
    main()
