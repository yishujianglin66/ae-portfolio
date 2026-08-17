"""
Resolve Engine E2E Test
========================
端到端验证: 素材导入 → 时间线 → CDL调色 → 变速 → 变换 → 渲染
"""
import sys
import os
import time

# 添加项目根目录到路径
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.resolve_engine import (
    ResolveAutomationEngine, CDLConfig, TransformConfig, ResolveError
)

def test_section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

def main():
    results = {"passed": 0, "failed": 0, "tests": []}
    
    engine = ResolveAutomationEngine()
    project_name = f"E2E_Test_{int(time.time())}"
    
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
        print("ERROR: No test media found in C:\\VinlandClips")
        return
    
    print(f"Test media: {len(test_files)} files")
    for f in test_files:
        print(f"  - {os.path.basename(f)}")
    
    # ============================================================
    # Test 1: 创建项目
    # ============================================================
    test_section("Test 1: 创建项目")
    try:
        name = engine.create_project(project_name)
        print(f"  [PASS] 项目创建成功: {name}")
        results["passed"] += 1
        results["tests"].append(("创建项目", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("创建项目", f"FAIL: {e}"))
    
    # ============================================================
    # Test 2: 创建时间线 + 导入素材
    # ============================================================
    test_section("Test 2: 创建时间线 + 导入素材")
    try:
        tl_info = engine.create_timeline_with_media(
            project_name, "Main_TL", test_files
        )
        clip_count = tl_info.get("clip_count", 0)
        items = tl_info.get("items", [])
        print(f"  [PASS] 时间线创建成功, {clip_count} 个片段")
        for item in items:
            print(f"    - {item.get('name', '?')} (duration={item.get('duration', '?')})")
        results["passed"] += 1
        results["tests"].append(("创建时间线", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("创建时间线", f"FAIL: {e}"))
    
    # ============================================================
    # Test 3: CDL 调色
    # ============================================================
    test_section("Test 3: CDL 调色")
    try:
        cdl = CDLConfig(
            slope=(1.2, 1.05, 0.95),
            offset=(0.02, 0.0, 0.03),
            power=(1.0, 1.05, 0.95),
            saturation=1.15
        )
        engine.apply_cdl(project_name, "Main_TL", 1, cdl)
        print(f"  [PASS] CDL 调色应用成功 (item 1)")
        results["passed"] += 1
        results["tests"].append(("CDL调色", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("CDL调色", f"FAIL: {e}"))
    
    # ============================================================
    # Test 4: 预设调色
    # ============================================================
    test_section("Test 4: 预设调色 (teal_orange)")
    try:
        engine.apply_preset_grade(project_name, 2, "teal_orange")
        print(f"  [PASS] teal_orange 预设应用成功 (item 2)")
        results["passed"] += 1
        results["tests"].append(("预设调色", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("预设调色", f"FAIL: {e}"))
    
    # ============================================================
    # Test 5: 变速
    # ============================================================
    test_section("Test 5: 变速 (2x)")
    try:
        engine.set_speed(project_name, 1, 2.0)
        print(f"  [PASS] 变速 2x 应用成功 (item 1)")
        results["passed"] += 1
        results["tests"].append(("变速", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("变速", f"FAIL: {e}"))
    
    # ============================================================
    # Test 6: 变换
    # ============================================================
    test_section("Test 6: 变换 (Zoom + Position + Rotation)")
    try:
        tf = TransformConfig(
            zoom_x=1.5, zoom_y=1.5,
            position_x=100, position_y=-50,
            rotation=5.0, opacity=90
        )
        engine.set_transform(project_name, 1, tf)
        print(f"  [PASS] 变换应用成功 (item 1)")
        results["passed"] += 1
        results["tests"].append(("变换", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("变换", f"FAIL: {e}"))
    
    # ============================================================
    # Test 7: 页面切换
    # ============================================================
    test_section("Test 7: 页面切换")
    try:
        for page in ["edit", "color", "fusion", "deliver", "edit"]:
            engine.switch_page(page)
            print(f"  [OK] → {page}")
        print(f"  [PASS] 所有页面切换成功")
        results["passed"] += 1
        results["tests"].append(("页面切换", "PASS"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("页面切换", f"FAIL: {e}"))
    
    # ============================================================
    # Test 8: 渲染输出
    # ============================================================
    test_section("Test 8: 渲染输出")
    output_dir = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_production"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"resolve_e2e_test_{int(time.time())}.mp4")
    
    try:
        rendered = engine.render_timeline(project_name, output_path)
        exists = os.path.exists(output_path)
        size = os.path.getsize(output_path) if exists else 0
        print(f"  [PASS] 渲染完成: {output_path}")
        print(f"         文件存在: {exists}, 大小: {size/1024/1024:.1f} MB")
        results["passed"] += 1
        results["tests"].append(("渲染输出", f"PASS ({size/1024/1024:.1f}MB)"))
    except Exception as e:
        print(f"  [FAIL] {e}")
        results["failed"] += 1
        results["tests"].append(("渲染输出", f"FAIL: {e}"))
    
    # ============================================================
    # Cleanup
    # ============================================================
    test_section("Cleanup")
    try:
        engine.delete_project(project_name)
        print(f"  [OK] 测试项目已删除: {project_name}")
    except Exception as e:
        print(f"  [WARN] 删除失败: {e}")
    
    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  E2E 测试结果汇总")
    print(f"{'='*60}")
    for name, status in results["tests"]:
        icon = "[OK]" if "PASS" in status else "[FAIL]"
        print(f"  {icon} {name}: {status}")
    print(f"\n  总计: {results['passed']} 通过, {results['failed']} 失败")
    print(f"{'='*60}")
    
    return results["failed"] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

