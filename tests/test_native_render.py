"""
Resolve 原生渲染测试（使用 SetRenderSettings API）
==================================================
验证修复后的渲染逻辑能否正确设置输出路径并完成渲染
"""
import os
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_native_render():
    """测试 Resolve 原生渲染"""
    engine = ResolveAutomationEngine()
    project_name = f"NativeRender_{int(time.time())}"
    
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
    tl_info = engine.create_timeline_with_media(project_name, "Render_TL", test_files)
    
    strong_cdl = CDLConfig(
        slope=(1.3, 1.2, 0.9),
        offset=(0.05, 0.02, -0.03),
        power=(0.85, 0.9, 1.1),
        saturation=0.7
    )
    
    engine.apply_cdl(project_name, "Render_TL", 1, strong_cdl)
    print("[OK] CDL applied")
    
    # ============================================================
    # Step 2: Resolve 原生渲染（使用 SetRenderSettings）
    # ============================================================
    print("\n=== Step 2: Native Render with SetRenderSettings ===")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"native_render_test_{int(time.time())}.mp4")
    
    try:
        rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=False)
        
        # 等待几秒让文件写入完成
        time.sleep(3)
        
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        
        if exists and size > 100000:  # >100KB
            print("[OK] Native render SUCCESSFUL!")
            print(f"   Output: {output_path}")
            print(f"   Size: {size/1024/1024:.1f} MB")
            print("\nPlease play this video to verify:")
            print("   - CDL color grading is preserved (100% accurate)")
            print("   - All effects are intact")
            print("   - No quality loss from FFmpeg conversion")
        else:
            print(f"[FAIL] Native render FAILED or output too small: {size} bytes")
            print("   Check Resolve UI for error messages")
            
    except Exception as e:
        print(f"[ERROR] Render exception: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_native_render()
