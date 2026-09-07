"""Debug: 打印 auto_grade 生成的 Lua 脚本"""
import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import ResolveColorEngine, ColorGradeConfig, find_lut_for_preset

engine = ResolveColorEngine()

test_frame = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames\frame_001.png"

config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)

# 模拟 create_project 流程但不执行
lut_path = config.lut_path or find_lut_for_preset(config.preset)
print(f"Original LUT path: {lut_path}")

safe_lut = engine._safe_lut_path(lut_path)
print(f"Safe LUT path: {safe_lut}")

lua_script = engine._build_pipeline_lua(
    project_name="Debug_Test",
    media_files=[test_frame],
    timeline_name="MainTimeline",
    lut_path=safe_lut,
    config=config,
    render=False,
    output_dir=None,
)

print()
print("=" * 60)
print("GENERATED LUA SCRIPT:")
print("=" * 60)
print(lua_script)
