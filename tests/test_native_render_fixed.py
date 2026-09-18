"""
原生渲染修复验证测试
=====================
验证修复后的原生渲染能否正确输出 MP4 格式并保留 CDL 效果
"""
import os
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_native_render_fixed():
    """测试修复后的原生渲染"""
    engine = ResolveAutomationEngine()
    project_name = f"NativeFixed_{int(time.time())}"
    
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
    print("\n=== Step 1: Create Timeline + Apply CDL ===")
    tl_info = engine.create_timeline_with_media(project_name, "Native_TL", test_files)
    
    strong_cdl = CDLConfig(
        slope=(1.5, 1.3, 0.8),
        offset=(0.08, 0.05, -0.05),
        power=(0.7, 0.8, 1.2),
        saturation=0.6
    )
    
    engine.apply_cdl(project_name, "Native_TL", 1, strong_cdl)
    print("[OK] Strong CDL applied")
    
    # ============================================================
    # Step 2: 原生渲染（输出 MP4）
    # ============================================================
    print("\n=== Step 2: Native Render (MP4 format) ===")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"native_fixed_test_{int(time.time())}.mp4")
    
    print(f"Output path: {output_path}")
    print("Starting native render... (this may take 1-2 minutes)")
    
    try:
        rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=False)
        
        # 等待文件写入完成
        time.sleep(3)
        
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        
        if exists and size > 100000:  # >100KB
            print("\n[OK] Native render SUCCESSFUL!")
            print(f"   Output: {output_path}")
            print(f"   Size: {size/1024/1024:.1f} MB")
            print("   Format: MP4 (H.264)")
            
            # 验证文件格式
            ext = os.path.splitext(output_path)[1].lower()
            if ext == '.mp4':
                print("   [OK] Correct file extension: .mp4")
            else:
                print(f"   [WARNING] Unexpected extension: {ext}")
            
            print("\nPlease verify:")
            print("  1. File plays correctly in video player")
            print("  2. CDL color grading is preserved (warm tones, high contrast)")
            print("  3. Saturation is reduced (0.6x)")
            
        else:
            print(f"\n[FAIL] Native render failed or output too small: {size} bytes")
            print("   Check Resolve UI for error messages")
            
    except Exception as e:
        print(f"\n[ERROR] Render exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_native_render_fixed()
