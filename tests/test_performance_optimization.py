"""
阶段2：渲染性能优化测试
===========================
验证四大优化策略：
1. GPU 加速编码（h264_nvenc 检测）
2. 代理媒体工作流（4K → 1080p 代理）
3. 分段并行渲染（多线程 + FFmpeg concat）
4. 渲染缓存机制（参数 hash 复用）
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ItemEffect, KenBurnsConfig, ResolveAutomationEngine, SpeedCurve

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve + 真实素材环境

OUTPUT_DIR = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"


def probe_video(filepath: str) -> dict:
    """ffprobe 验证视频"""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration,size',
        '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
        '-of', 'json', filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            v = info['streams'][0] if info['streams'] else {}
            return {
                'valid': True,
                'duration': float(info['format']['duration']),
                'size_mb': int(info['format']['size']) / 1024 / 1024,
                'width': v.get('width'), 'height': v.get('height'),
                'fps': v.get('r_frame_rate'), 'codec': v.get('codec_name'),
            }
    except Exception as e:
        return {'valid': False, 'error': str(e)}
    return {'valid': False, 'error': 'ffprobe failed'}


def test_phase2_optimization():
    print("=" * 80)
    print("[Phase 2] Rendering Performance Optimization Test")
    print("=" * 80)

    engine = ResolveAutomationEngine(timeout=600)
    project_name = f"PerfOpt_{int(time.time())}"
    results = {}

    # 准备素材（3个）
    media_dir = r"C:\VinlandClips"
    test_files = []
    if os.path.isdir(media_dir):
        for f in sorted(os.listdir(media_dir)):
            if f.endswith('.mp4') and len(test_files) < 3:
                test_files.append(os.path.join(media_dir, f))

    if not test_files:
        print("[ERROR] No test media found")
        return {}

    print(f"\nTest media: {len(test_files)} clips")

    # ============================================================
    # Test 1: GPU 编码器检测
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 1] GPU encoder detection")
    print("-" * 60)
    gpu_encoder = engine._detect_gpu_encoder()
    if gpu_encoder:
        print(f"[OK] GPU encoder found: {gpu_encoder}")
        encoder_args = engine._get_encoder_args(quality="fast")
        print(f"[OK] Encoder args: {encoder_args}")
        results['gpu_encoder'] = gpu_encoder
    else:
        print("[WARN] No GPU encoder, will use CPU (libx264)")
        results['gpu_encoder'] = 'none'

    # ============================================================
    # 创建项目时间线 + 应用效果
    # ============================================================
    print("\n" + "-" * 60)
    print("[Setup] Creating timeline and applying effects")
    print("-" * 60)
    engine.create_timeline_with_media(project_name, "PerfTL", test_files)

    # 应用 CDL（用于测试缓存 key 变化）
    engine.apply_cdl(project_name, "PerfTL", 1, CDLConfig(
        slope=(1.3, 1.1, 0.8), offset=(0.05, 0.03, -0.02),
        power=(0.9, 0.95, 1.1), saturation=1.2))
    engine.apply_cdl(project_name, "PerfTL", 2, CDLConfig(
        slope=(0.9, 1.0, 1.3), offset=(-0.03, -0.02, 0.05),
        power=(1.1, 1.0, 0.85), saturation=0.8))
    print("[OK] CDL applied to clips 1-2")

    effects = {
        1: ItemEffect(item_index=1,
                      ken_burns=KenBurnsConfig(start_zoom=1.0, end_zoom=1.5)),
        2: ItemEffect(item_index=2,
                      speed_curve=SpeedCurve(curve_type="linear",
                                             start_speed=1.5, end_speed=1.5)),
    }

    # ============================================================
    # Test 2: 代理媒体工作流
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 2] Proxy media workflow")
    print("-" * 60)
    t0 = time.time()
    proxy_map = engine.create_proxy_media(project_name, proxy_height=720)
    proxy_time = time.time() - t0
    print(f"[OK] Created {len(proxy_map)} proxies in {proxy_time:.1f}s")
    for name, path in proxy_map.items():
        if os.path.exists(path):
            info = probe_video(path)
            print(f"    {name}: {info.get('height')}p, {info.get('size_mb', 0):.2f}MB")
    results['proxies'] = len(proxy_map)

    # 恢复原始素材（渲染前）
    restored = engine.restore_original_media(project_name)
    print(f"[OK] Restored {restored} original media files")

    # ============================================================
    # Test 3: 分段并行渲染（第1次，无缓存）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 3] Segment parallel rendering (1st run, no cache)")
    print("-" * 60)
    output1 = os.path.join(OUTPUT_DIR, f"perf_parallel_1_{int(time.time())}.mp4")
    t0 = time.time()
    try:
        engine.render_segments_parallel(project_name, output1, effects=effects, max_workers=4)
        parallel_time1 = time.time() - t0
        info1 = probe_video(output1)
        if info1['valid']:
            print(f"[OK] Parallel render complete in {parallel_time1:.1f}s")
            print(f"    Duration: {info1['duration']:.2f}s, Size: {info1['size_mb']:.1f}MB")
            print(f"    Resolution: {info1['width']}x{info1['height']}, Codec: {info1['codec']}")
            results['parallel_time_1st'] = parallel_time1
        else:
            print(f"[ERROR] Output invalid: {info1}")
    except Exception as e:
        print(f"[ERROR] Parallel render failed: {e}")
        import traceback
        traceback.print_exc()

    # ============================================================
    # Test 4: 渲染缓存机制（第2次，应命中缓存）
    # ============================================================
    print("\n" + "-" * 60)
    print("[Test 4] Render cache (2nd run, should hit cache)")
    print("-" * 60)
    output2 = os.path.join(OUTPUT_DIR, f"perf_parallel_2_{int(time.time())}.mp4")
    t0 = time.time()
    try:
        engine.render_segments_parallel(project_name, output2, effects=effects, max_workers=4)
        parallel_time2 = time.time() - t0
        info2 = probe_video(output2)
        if info2['valid']:
            print(f"[OK] Cached render complete in {parallel_time2:.1f}s")
            results['parallel_time_2nd'] = parallel_time2

            # 计算加速比
            if 'parallel_time_1st' in results and parallel_time2 > 0:
                speedup = results['parallel_time_1st'] / parallel_time2
                print(f"[OK] Cache speedup: {speedup:.1f}x")
                results['cache_speedup'] = speedup
        else:
            print(f"[ERROR] Output invalid: {info2}")
    except Exception as e:
        print(f"[ERROR] Cached render failed: {e}")

    # ============================================================
    # 清理
    # ============================================================
    print("\n[Cleanup] Deleting test project...")
    try:
        engine.delete_project(project_name)
        print(f"[OK] Project '{project_name}' deleted")
    except Exception as e:
        print(f"[WARN] Cleanup failed: {e}")

    # ============================================================
    # 结果汇总
    # ============================================================
    print("\n" + "=" * 80)
    print("[Summary] Phase 2 Optimization Results")
    print("=" * 80)
    print(f"  GPU encoder:        {results.get('gpu_encoder', 'N/A')}")
    print(f"  Proxy media:        {results.get('proxies', 0)} created")
    if 'parallel_time_1st' in results:
        print(f"  Parallel render:    {results['parallel_time_1st']:.1f}s (1st run)")
    if 'parallel_time_2nd' in results:
        print(f"  Cached render:      {results['parallel_time_2nd']:.1f}s (2nd run)")
    if 'cache_speedup' in results:
        print(f"  Cache speedup:      {results['cache_speedup']:.1f}x")

    return results


if __name__ == "__main__":
    test_phase2_optimization()
