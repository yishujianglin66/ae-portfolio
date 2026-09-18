"""
原生渲染 vs FFmpeg 渲染效果对比测试
====================================
生成两个版本的输出文件用于肉眼对比
"""
import os
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_render_comparison():
    """对比原生渲染和 FFmpeg 渲染的效果"""
    engine = ResolveAutomationEngine()
    project_name = f"RenderCompare_{int(time.time())}"
    
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
    # Step 1: 创建时间线并应用强烈的 CDL 调色
    # ============================================================
    print("\n=== Step 1: Create Timeline + Apply Strong CDL ===")
    tl_info = engine.create_timeline_with_media(project_name, "Compare_TL", test_files)
    
    # 使用非常明显的电影感调色（便于肉眼识别差异）
    strong_cdl = CDLConfig(
        slope=(1.5, 1.3, 0.8),      # 强对比，明显偏暖
        offset=(0.08, 0.05, -0.05), # 提升阴影，蓝调偏移
        power=(0.7, 0.8, 1.2),      # 压低高光，增强蓝色
        saturation=0.6              # 大幅降低饱和度
    )
    
    engine.apply_cdl(project_name, "Compare_TL", 1, strong_cdl)
    print("[OK] Strong CDL applied:")
    print(f"   Slope:   ({strong_cdl.slope[0]:.1f}, {strong_cdl.slope[1]:.1f}, {strong_cdl.slope[2]:.1f})")
    print(f"   Offset:  ({strong_cdl.offset[0]:.2f}, {strong_cdl.offset[1]:.2f}, {strong_cdl.offset[2]:.2f})")
    print(f"   Power:   ({strong_cdl.power[0]:.1f}, {strong_cdl.power[1]:.1f}, {strong_cdl.power[2]:.1f})")
    print(f"   Saturation: {strong_cdl.saturation:.1f}")
    
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = int(time.time())
    
    # ============================================================
    # Step 2: FFmpeg 渲染（带 CDL 转换）
    # ============================================================
    print("\n=== Step 2: FFmpeg Render (with CDL conversion) ===")
    ffmpeg_path = os.path.join(output_dir, f"compare_ffmpeg_{timestamp}.mp4")
    
    try:
        engine.render_timeline(project_name, ffmpeg_path, use_ffmpeg=True)
        time.sleep(2)
        
        if os.path.exists(ffmpeg_path):
            size = os.path.getsize(ffmpeg_path)
            print(f"[OK] FFmpeg render: {size/1024/1024:.1f} MB")
            print(f"   File: {ffmpeg_path}")
        else:
            print("[FAIL] FFmpeg render failed")
    except Exception as e:
        print(f"[ERROR] FFmpeg render exception: {e}")
    
    # ============================================================
    # Step 3: Resolve 原生渲染（使用 SetRenderSettings）
    # ============================================================
    print("\n=== Step 3: Native Resolve Render (SetRenderSettings) ===")
    native_path = os.path.join(output_dir, f"compare_native_{timestamp}.mp4")
    
    try:
        engine.render_timeline(project_name, native_path, use_ffmpeg=False)
        
        # 等待渲染完成（可能需要较长时间）
        print("Waiting for native render to complete...")
        max_wait = 300  # 5分钟超时
        waited = 0
        while waited < max_wait:
            time.sleep(5)
            waited += 5
            if os.path.exists(native_path):
                size = os.path.getsize(native_path)
                if size > 100000:  # >100KB
                    print(f"[OK] Native render completed: {size/1024/1024:.1f} MB")
                    print(f"   File: {native_path}")
                    break
            print(f"   ... still rendering ({waited}s)")
        
        if waited >= max_wait:
            print("[WARNING] Native render timeout - check Resolve UI")
            
    except Exception as e:
        print(f"[ERROR] Native render exception: {e}")
        import traceback
        traceback.print_exc()
    
    # ============================================================
    # Step 4: 对比总结
    # ============================================================
    print("\n" + "="*70)
    print("RENDER COMPARISON SUMMARY")
    print("="*70)
    
    ffmpeg_exists = os.path.exists(ffmpeg_path)
    native_exists = os.path.exists(native_path)
    
    if ffmpeg_exists and native_exists:
        ffmpeg_size = os.path.getsize(ffmpeg_path)
        native_size = os.path.getsize(native_path)
        
        print("\nFiles generated:")
        print(f"  FFmpeg:  {ffmpeg_path}")
        print(f"           Size: {ffmpeg_size/1024/1024:.1f} MB")
        print(f"  Native:  {native_path}")
        print(f"           Size: {native_size/1024/1024:.1f} MB")
        
        size_diff = abs(ffmpeg_size - native_size) / max(ffmpeg_size, native_size) * 100
        print(f"\nSize difference: {size_diff:.1f}%")
        
        print("\nVisual comparison checklist:")
        print("  [ ] Contrast (对比度) - Native should be stronger")
        print("  [ ] Color temperature (色温) - Native warmer (orange/red)")
        print("  [ ] Saturation (饱和度) - Native lower (0.6x)")
        print("  [ ] Shadow detail (阴影细节) - Native lifted")
        print("  [ ] Highlight roll-off (高光过渡) - Native smoother")
        
        print("\nTo verify:")
        print("  1. Open both files side-by-side in a video player")
        print("  2. Look for the strong warm/orange tint in Native version")
        print("  3. Check if FFmpeg version looks 'flatter' (less contrast)")
        print("  4. If they look identical -> FFmpeg conversion is working well")
        print("  5. If Native looks much more dramatic -> FFmpeg lost effects")
        
    elif ffmpeg_exists:
        print("\nOnly FFmpeg render succeeded:")
        print(f"  {ffmpeg_path}")
        print("  Native render failed - check Resolve UI for errors")
        
    elif native_exists:
        print("\nOnly Native render succeeded:")
        print(f"  {native_path}")
        print("  FFmpeg render failed")
        
    else:
        print("\nBoth renders failed!")
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_render_comparison()
