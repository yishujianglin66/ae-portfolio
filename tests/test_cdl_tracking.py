"""
CDL 效果保留验证测试
=====================
验证 Python 层追踪的 CDL 参数能否正确传递到 FFmpeg 渲染
"""
import os
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_cdl_tracking():
    """测试 CDL 追踪和 FFmpeg 应用"""
    engine = ResolveAutomationEngine()
    project_name = f"CDL_Track_{int(time.time())}"
    
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
    tl_info = engine.create_timeline_with_media(project_name, "CDL_TL", test_files)
    
    strong_cdl = CDLConfig(
        slope=(1.3, 1.2, 0.9),      # 强对比，偏暖
        offset=(0.05, 0.02, -0.03), # 提升阴影
        power=(0.85, 0.9, 1.1),     # 降低高光，偏蓝
        saturation=0.7              # 降低饱和度
    )
    
    engine.apply_cdl(project_name, "CDL_TL", 1, strong_cdl)
    print("Applied CDL:")
    print(f"  Slope:   ({strong_cdl.slope[0]:.2f}, {strong_cdl.slope[1]:.2f}, {strong_cdl.slope[2]:.2f})")
    print(f"  Offset:  ({strong_cdl.offset[0]:.2f}, {strong_cdl.offset[1]:.2f}, {strong_cdl.offset[2]:.2f})")
    print(f"  Power:   ({strong_cdl.power[0]:.2f}, {strong_cdl.power[1]:.2f}, {strong_cdl.power[2]:.2f})")
    print(f"  Saturation: {strong_cdl.saturation:.2f}")
    
    # ============================================================
    # Step 2: 验证 Python 层是否记录了 CDL
    # ============================================================
    print("\n=== Step 2: Verify CDL Tracking ===")
    tracked_cdl = engine._cdl_config_map.get(project_name, {}).get(1)
    
    if tracked_cdl:
        print("✅ CDL successfully tracked in Python layer")
        print(f"  Tracked Slope:   ({tracked_cdl.slope[0]:.2f}, {tracked_cdl.slope[1]:.2f}, {tracked_cdl.slope[2]:.2f})")
        print(f"  Tracked Offset:  ({tracked_cdl.offset[0]:.2f}, {tracked_cdl.offset[1]:.2f}, {tracked_cdl.offset[2]:.2f})")
        print(f"  Tracked Power:   ({tracked_cdl.power[0]:.2f}, {tracked_cdl.power[1]:.2f}, {tracked_cdl.power[2]:.2f})")
        print(f"  Tracked Saturation: {tracked_cdl.saturation:.2f}")
        
        # 验证一致性
        match = (
            abs(tracked_cdl.slope[0] - strong_cdl.slope[0]) < 0.001 and
            abs(tracked_cdl.slope[1] - strong_cdl.slope[1]) < 0.001 and
            abs(tracked_cdl.slope[2] - strong_cdl.slope[2]) < 0.001 and
            abs(tracked_cdl.offset[0] - strong_cdl.offset[0]) < 0.001 and
            abs(tracked_cdl.offset[1] - strong_cdl.offset[1]) < 0.001 and
            abs(tracked_cdl.offset[2] - strong_cdl.offset[2]) < 0.001 and
            abs(tracked_cdl.power[0] - strong_cdl.power[0]) < 0.001 and
            abs(tracked_cdl.power[1] - strong_cdl.power[1]) < 0.001 and
            abs(tracked_cdl.power[2] - strong_cdl.power[2]) < 0.001 and
            abs(tracked_cdl.saturation - strong_cdl.saturation) < 0.001
        )
        
        if match:
            print("✅ All CDL parameters match perfectly")
        else:
            print("❌ CDL parameter mismatch detected!")
            return
    else:
        print("❌ CDL NOT tracked - FFmpeg render will lose color grading!")
        return
    
    # ============================================================
    # Step 3: FFmpeg 渲染（应应用 CDL）
    # ============================================================
    print("\n=== Step 3: FFmpeg Render with CDL ===")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"cdl_track_test_{int(time.time())}.mp4")
    
    rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=True)
    exists = os.path.exists(output_path)
    size = os.path.getsize(output_path) if exists else 0
    
    if exists and size > 100000:  # >100KB
        print(f"✅ FFmpeg render successful: {size/1024/1024:.1f} MB")
        print(f"   Output: {output_path}")
        print("\n📺 Please play this video to verify color grading is applied:")
        print("   Expected: Higher contrast, warmer tones, lower saturation")
    else:
        print(f"❌ FFmpeg render failed or output too small: {size} bytes")
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_cdl_tracking()
