"""
P1 高级功能 E2E 测试
=====================
变速曲线 + Ken Burns 拉镜 + Zoom 转场 + 多素材拼接渲染
"""
import sys
import os
import time

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.resolve_engine import (
    ResolveAutomationEngine, CDLConfig, TransformConfig,
    SpeedCurve, KenBurnsConfig, ZoomTransition, ItemEffect,
    ResolveError
)

def test_section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

def main():
    results = {"passed": 0, "failed": 0, "tests": []}
    
    engine = ResolveAutomationEngine()
    project_name = f"P1_Adv_{int(time.time())}"
    
    # 测试素材
    media_dir = r"C:\VinlandClips"
    test_files = []
    if os.path.isdir(media_dir):
        for f in sorted(os.listdir(media_dir)):
            if f.endswith('.mp4'):
                test_files.append(os.path.join(media_dir, f))
                if len(test_files) >= 3:
                    break
    
    if not test_files:
        print("ERROR: No test media found")
        return
    
    print(f"Test media: {len(test_files)} files")
    
    # ============================================================
    # Test 1: 创建项目 + 时间线
    # ============================================================
    test_section("Test 1: 创建项目 + 时间线")
    try:
        tl_info = engine.create_timeline_with_media(project_name, "AdvTL", test_files)
        clip_count = tl_info.get("clip_count", 0)
        print(f"  [PASS] {clip_count} clips imported")
        results["passed"] += 1
        results["tests"].append(("创建项目+时间线", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("创建项目+时间线", f"FAIL: {e}"))
    
    # ============================================================
    # Test 2: CDL 调色 + 预设
    # ============================================================
    test_section("Test 2: CDL 调色")
    try:
        cdl = CDLConfig(slope=(1.1, 1.05, 0.95), offset=(0.02, 0.0, 0.03),
                        power=(1.0, 1.05, 0.95), saturation=1.15)
        engine.apply_cdl(project_name, "AdvTL", 1, cdl)
        engine.apply_preset_grade(project_name, 2, "teal_orange")
        print(f"  [PASS] CDL + preset applied")
        results["passed"] += 1
        results["tests"].append(("CDL调色", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("CDL调色", f"FAIL: {e}"))
    
    # ============================================================
    # Test 3: 变速曲线 (ease_in)
    # ============================================================
    test_section("Test 3: 变速曲线 (ease_in)")
    try:
        curve = SpeedCurve(curve_type="ease_in", start_speed=0.5, end_speed=2.0)
        engine.apply_speed_curve(project_name, 1, curve)
        print(f"  [PASS] Speed curve applied (0.5x -> 2.0x)")
        results["passed"] += 1
        results["tests"].append(("变速曲线", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("变速曲线", f"FAIL: {e}"))
    
    # ============================================================
    # Test 4: 基础变速
    # ============================================================
    test_section("Test 4: 基础变速 (2x)")
    try:
        engine.set_speed(project_name, 2, 2.0)
        print(f"  [PASS] Speed 2x applied to item 2")
        results["passed"] += 1
        results["tests"].append(("基础变速", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("基础变速", f"FAIL: {e}"))
    
    # ============================================================
    # Test 5: 变换 (Zoom + Position)
    # ============================================================
    test_section("Test 5: 变换")
    try:
        tf = TransformConfig(zoom_x=1.3, zoom_y=1.3, position_x=50, position_y=-30, rotation=3.0)
        engine.set_transform(project_name, 3, tf)
        print(f"  [PASS] Transform applied to item 3")
        results["passed"] += 1
        results["tests"].append(("变换", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("变换", f"FAIL: {e}"))
    
    # ============================================================
    # Test 6: 获取时间线信息
    # ============================================================
    test_section("Test 6: 获取时间线信息")
    try:
        info = engine.get_timeline_info(project_name)
        items = info.get("items", [])
        fps = info.get("fps", 24)
        w = info.get("width", 1920)
        h = info.get("height", 1080)
        print(f"  [PASS] Timeline: {len(items)} items, {fps}fps, {w}x{h}")
        for item in items:
            print(f"    - {item.get('name', '?')} speed={item.get('speed', '?')} "
                  f"zoom={item.get('zoom_x', '?')}")
        results["passed"] += 1
        results["tests"].append(("时间线信息", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("时间线信息", f"FAIL: {e}"))
    
    # ============================================================
    # Test 7: Ken Burns 效果准备
    # ============================================================
    test_section("Test 7: Ken Burns 拉镜准备")
    try:
        kb = KenBurnsConfig(
            start_zoom=1.0, end_zoom=1.5,
            start_x=0.3, start_y=0.5,
            end_x=0.7, end_y=0.5,
        )
        engine.apply_ken_burns(project_name, 1, kb)
        print(f"  [PASS] Ken Burns configured (1.0x -> 1.5x zoom)")
        results["passed"] += 1
        results["tests"].append(("Ken Burns", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("Ken Burns", f"FAIL: {e}"))
    
    # ============================================================
    # Test 8: FFmpeg 渲染（带特效）
    # ============================================================
    test_section("Test 8: FFmpeg 渲染（多素材+变速+变换）")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"p1_adv_test_{int(time.time())}.mp4")
    
    try:
        rendered = engine.render_timeline(project_name, output_path)
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        print(f"  [PASS] Rendered: {size/1024/1024:.1f} MB")
        results["passed"] += 1
        results["tests"].append(("FFmpeg渲染", f"PASS ({size/1024/1024:.1f}MB)"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("FFmpeg渲染", f"FAIL: {e}"))
    
    # ============================================================
    # Test 9: 页面切换
    # ============================================================
    test_section("Test 9: 页面切换")
    try:
        for page in ["edit", "color", "deliver", "edit"]:
            engine.switch_page(page)
        print(f"  [PASS] All pages switched")
        results["passed"] += 1
        results["tests"].append(("页面切换", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("页面切换", f"FAIL: {e}"))
    
    # ============================================================
    # Cleanup
    # ============================================================
    test_section("Cleanup")
    try:
        engine.delete_project(project_name)
        print(f"  [OK] Project deleted: {project_name}")
    except Exception as e:
        print(f"  [WARN] {e}")
    
    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  P1 Advanced E2E Test Summary")
    print(f"{'='*60}")
    for name, status in results["tests"]:
        icon = "[OK]" if "PASS" in status else "[FAIL]"
        print(f"  {icon} {name}: {status}")
    print(f"\n  Total: {results['passed']} passed, {results['failed']} failed")
    print(f"{'='*60}")
    
    return results["failed"] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
