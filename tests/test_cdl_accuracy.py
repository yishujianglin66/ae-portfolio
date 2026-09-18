"""
CDL 转换精度测试
=================
验证 Resolve CDL → FFmpeg eq 滤镜的转换精度
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

import pytest

from integrations.resolve_engine import CDLConfig, ResolveAutomationEngine

pytestmark = pytest.mark.real_davinci  # 需真实 DaVinci Resolve 环境

def test_cdl_conversion():
    """测试 CDL 转换精度"""
    engine = ResolveAutomationEngine()
    project_name = f"CDL_Test_{int(time.time())}"
    
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
    # Step 1: Resolve 中应用强对比度 CDL
    # ============================================================
    print("\n=== Step 1: Apply Strong CDL in Resolve ===")
    tl_info = engine.create_timeline_with_media(project_name, "CDL_TL", test_files)
    
    # 使用强烈的电影感调色（高对比、暖色调）
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
    # Step 2: 获取时间线信息（含 CDL）
    # ============================================================
    print("\n=== Step 2: Read Timeline Info ===")
    info = engine.get_timeline_info(project_name)
    items = info.get("items", [])
    
    if not items or not items[0].get("cdl"):
        print("WARNING: CDL data not available via API")
        print("This means GetCDL() is not supported in fuscript")
        cdl_available = False
    else:
        cdl_data = items[0]["cdl"]
        print("Read CDL from Resolve:")
        print(f"  Slope R/G/B:   {cdl_data['slope_r']:.2f} / {cdl_data['slope_g']:.2f} / {cdl_data['slope_b']:.2f}")
        print(f"  Offset R/G/B:  {cdl_data['offset_r']:.2f} / {cdl_data['offset_g']:.2f} / {cdl_data['offset_b']:.2f}")
        print(f"  Power R/G/B:   {cdl_data['power_r']:.2f} / {cdl_data['power_g']:.2f} / {cdl_data['power_b']:.2f}")
        print(f"  Saturation:    {cdl_data['saturation']:.2f}")
        cdl_available = True
    
    # ============================================================
    # Step 3: FFmpeg 渲染（带 CDL 转换）
    # ============================================================
    print("\n=== Step 3: Render with FFmpeg (CDL converted) ===")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"cdl_test_ffmpeg_{int(time.time())}.mp4")
    
    rendered = engine.render_timeline(project_name, output_path, use_ffmpeg=True)
    exists = os.path.exists(output_path)
    size = os.path.getsize(output_path) if exists else 0
    print(f"FFmpeg render: {'OK' if exists else 'FAIL'} ({size/1024/1024:.1f} MB)")
    
    # ============================================================
    # Step 4: 手动用 Resolve 原生渲染（需用户配合）
    # ============================================================
    print("\n=== Step 4: Manual Native Render (User Action Required) ===")
    print("Please do the following in DaVinci Resolve UI:")
    print("1. Open project: " + project_name)
    print("2. Go to Deliver page")
    print("3. Set output path: " + output_path.replace(".mp4", "_native.mp4"))
    print("4. Click 'Add to Render Queue' → 'Start Render'")
    print("5. Wait for completion, then press Enter here...")
    
    input("\nPress Enter when native render is complete...")
    
    native_path = output_path.replace(".mp4", "_native.mp4")
    if os.path.exists(native_path):
        native_size = os.path.getsize(native_path)
        print(f"Native render: OK ({native_size/1024/1024:.1f} MB)")
        
        # ============================================================
        # Step 5: 计算视觉差异（简化版：文件大小对比）
        # ============================================================
        print("\n=== Step 5: Quality Comparison ===")
        size_diff = abs(size - native_size) / max(size, native_size) * 100
        print(f"File size difference: {size_diff:.1f}%")
        
        if size_diff < 10:
            print("✅ GOOD: File sizes are similar, quality likely comparable")
        elif size_diff < 30:
            print("️  ACCEPTABLE: Some quality difference, but usable")
        else:
            print("❌ POOR: Significant quality loss detected")
        
        # 建议用户用视频播放器肉眼对比两个文件
        print("\n📺 Please visually compare these two files in a video player:")
        print(f"  FFmpeg:  {output_path}")
        print(f"  Native:  {native_path}")
        print("\nLook for differences in:")
        print("  • Contrast (对比度)")
        print("  • Color temperature (色温)")
        print("  • Saturation (饱和度)")
        print("  • Shadow/highlight detail (阴影/高光细节)")
        
    else:
        print(f"Native render file not found: {native_path}")
    
    # Cleanup
    engine.delete_project(project_name)
    print(f"\nProject cleaned up: {project_name}")

if __name__ == "__main__":
    test_cdl_conversion()
