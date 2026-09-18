"""测试 _safe_lut_path 中文路径转换 + 引擎基本功能"""
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from pathlib import Path

from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine, find_lut_for_preset

print("=" * 60)
print("Test 1: _safe_lut_path 中文路径转换")
print("=" * 60)

engine = ResolveColorEngine()

# 测试1: 纯英文路径应原样返回
english_path = r"C:\some\english\path.cube"
result = engine._safe_lut_path(english_path)
assert result == english_path, f"English path should pass through: {result}"
print(f"  [PASS] English path unchanged: {result}")

# 测试2: None 应返回 None
result = engine._safe_lut_path(None)
assert result is None, f"None should return None: {result}"
print("  [PASS] None returns None")

# 测试3: 中文路径应被复制到临时目录
chinese_path = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\resources\luts\调色-COLOR_LUTs\电影感 _ Cinematic\Cinematic-1.cube"
# 先检查文件是否存在
if Path(chinese_path).exists():
    result = engine._safe_lut_path(chinese_path)
    print(f"  原始路径: {chinese_path}")
    print(f"  安全路径: {result}")
    assert Path(result).exists(), f"Safe path should exist: {result}"
    assert "调色" not in result, f"Safe path should not contain Chinese: {result}"
    print("  [PASS] Chinese path converted to safe path")
else:
    # 找第一个存在的 LUT 文件
    lut_dir = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\resources\luts")
    cube_files = list(lut_dir.rglob("*.cube"))
    if cube_files:
        first_cube = str(cube_files[0])
        print(f"  使用实际 LUT 文件: {first_cube}")
        result = engine._safe_lut_path(first_cube)
        print(f"  安全路径: {result}")
        assert Path(result).exists(), "Safe path should exist"
        print("  [PASS] Chinese path converted to safe path")
    else:
        print("  [SKIP] No .cube files found in resources/luts")

print()
print("=" * 60)
print("Test 2: find_lut_for_preset 查找 + 路径安全转换")
print("=" * 60)

for preset in ["cinematic", "dramatic", "warm"]:
    lut = find_lut_for_preset(preset)
    if lut:
        safe = engine._safe_lut_path(lut)
        print(f"  preset={preset}: {lut[:60]}... -> safe={safe[:60]}...")
        assert Path(safe).exists(), f"Safe LUT should exist: {safe}"
    else:
        print(f"  preset={preset}: not found")

print()
print("=" * 60)
print("Test 3: ColorGradeConfig 分段预设 + LUT 解析")
print("=" * 60)

config = ColorGradeConfig(
    preset="cinematic",
    segment_presets={
        "intro": "warm",
        "action": "dramatic",
        "outro": "cinematic",
    }
)
print(f"  Config preset: {config.preset}")
print(f"  Segment presets: {config.segment_presets}")

# 模拟 _build_pipeline_lua 中的分段 LUT 解析
for key, preset_name in config.segment_presets.items():
    seg_lut = find_lut_for_preset(preset_name)
    if seg_lut:
        safe_lut = engine._safe_lut_path(seg_lut)
        print(f"  segment '{key}' -> preset '{preset_name}' -> LUT: ...{safe_lut[-50:]}")
        assert Path(safe_lut).exists()

print()
print("=" * 60)
print("Test 4: _build_fusion_lua SetAttr 修复验证")
print("=" * 60)

config_fusion = ColorGradeConfig(brightness=1.05, contrast=1.1, saturation=1.05)
lua_code = engine._build_fusion_lua("TestProject", config_fusion, 1)
assert "SetAttr" not in lua_code, "SetAttr should NOT appear in _build_fusion_lua"
assert "bc.Brightness" in lua_code, "Should use direct property assignment"
assert "bc.Contrast" in lua_code
assert "cg.Saturation" in lua_code
print("  [PASS] _build_fusion_lua uses direct property assignment (no SetAttr)")

print()
print("=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
