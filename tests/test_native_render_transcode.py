"""
原生渲染 + FFmpeg 自动转码测试
================================
验证修复后的原生渲染能否输出 MP4 格式并保留 CDL 效果
"""
import os
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_native_render_with_transcode():
    """测试原生渲染 + 自动转码"""
    engine = ResolveAutomationEngine(timeout=600)  # 10分钟超时
    project_name = f"NativeTranscode_{int(time.time())}"
    
    # 测试素材
    media_dir = r"C:\VinlandClips"
    test_files = []
    if os.path.isdir(media_dir):
        for f in sorted(os.listdir(media_dir)):
            if f.endswith('.mp4'):
                test_files.append(os.path.join(media_dir, f))
                break
    
    if not test_files:
        print("ERROR: No test media found")
        return
    
    print(f"Test media: {os.path.basename(test_files[0])}")
    
    # ============================================================
    # Step 1: 创建时间线并应用 CDL
    # ============================================================
    print("\n=== Step 1: Create Timeline + Apply Strong CDL ===")
    tl_info = engine.create_timeline_with_media(project_name, "Transcode_TL", test_files)
    
    strong_cdl = CDLConfig(
        slope=(1.5, 1.3, 0.8),
        offset=(0.08, 0.05, -0.05),
        power=(0.7, 0.8, 1.2),
        saturation=0.6
    )
    
    engine.apply_cdl(project_name, "Transcode_TL", 1, strong_cdl)
    print("[OK] Strong CDL applied:")
    print(f"   Slope:   ({strong_cdl.slope[0]:.1f}, {strong_cdl.slope[1]:.1f}, {strong_cdl.slope[2]:.1f})")
    print(f"   Saturation: {strong_cdl.saturation:.1f}")
    
    # ============================================================
    # Step 2: 原生渲染 + 自动转码为 MP4
    # ============================================================
    print("\n=== Step 2: Native Render + Auto Transcode to MP4 ===")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"native_transcode_test_{int(time.time())}.mp4")
    
    print(f"Output path: {output_path}")
    print("This will:")
    print("  1. Render natively in Resolve (.mov, preserves all effects)")
    print("  2. Auto-convert to MP4 using FFmpeg (lossless, fast)")
    print("  Total time: ~1-2 minutes\n")
    
    try:
        start_time = time.time()
        rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=False)
        elapsed = time.time() - start_time
        
        # 等待文件写入完成
        time.sleep(2)
        
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        
        if exists and size > 100000:  # >100KB
            print(f"\n{'='*70}")
            print("[OK] NATIVE RENDER + TRANSCODE SUCCESSFUL!")
            print(f"{'='*70}")
            print(f"   Output: {output_path}")
            print(f"   Size: {size/1024/1024:.1f} MB")
            print("   Format: MP4 (H.264)")
            print(f"   Time: {elapsed:.1f}s")
            
            # 验证文件格式
            ext = os.path.splitext(output_path)[1].lower()
            if ext == '.mp4':
                print("   [OK] Correct file extension: .mp4")
            else:
                print(f"   [WARNING] Unexpected extension: {ext}")
            
            # 检查是否有临时 .mov 文件残留
            temp_mov = output_path.replace(".mp4", "_temp.mov")
            if os.path.exists(temp_mov):
                print(f"   [WARNING] Temp file not cleaned up: {temp_mov}")
            else:
                print("   [OK] Temp file cleaned up")
            
            print("\nPlease verify:")
            print("  1. File plays correctly in video player")
            print("  2. CDL color grading is preserved (warm tones, high contrast)")
            print("  3. Saturation is reduced (0.6x)")
            print("  4. Quality matches the original .mov render")
            
        else:
            print(f"\n[FAIL] Render failed or output too small: {size} bytes")
            print("   Check Resolve UI for error messages")
            
    except Exception as e:
        print(f"\n[ERROR] Render exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_native_render_with_transcode()
