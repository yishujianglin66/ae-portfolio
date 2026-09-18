"""端到端验证：auto_grade + 中文路径 LUT + Fusion 调色"""
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from pathlib import Path

from integrations.davinci_fuscript import ColorGradeConfig, ResolveColorEngine

# 使用项目中的测试图片
test_frame = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames\frame_001.png"
if not Path(test_frame).exists():
    # 尝试找任意一张测试图
    frames_dir = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\frames")
    pngs = list(frames_dir.glob("*.png"))
    if pngs:
        test_frame = str(pngs[0])
    else:
        print("ERROR: No test frames available")
        sys.exit(1)

print(f"Test frame: {test_frame}")
print()

engine = ResolveColorEngine()

def progress_cb(progress, message):
    bar = "#" * int(progress * 30)
    print(f"  [{bar:<30}] {progress*100:5.1f}%  {message}")

# 测试 1: 基础 auto_grade（cinematic 预设，含中文路径 LUT 自动转换）
print("=" * 60)
print("E2E Test 1: auto_grade with cinematic preset (LUT + Fusion)")
print("=" * 60)

config = ColorGradeConfig(
    preset="cinematic",
    brightness=1.05,
    contrast=1.1,
    saturation=0.95,
)

result = engine.auto_grade(
    project_name="E2E_Test_v32",
    media_files=[test_frame],
    color_config=config,
    close_after=True,
    callback=progress_cb,
)

print()
print(f"  Success: {result.success}")
print(f"  Clips graded: {result.clips_graded}")
print(f"  Clips imported: {result.clips_imported}")
print(f"  Duration: {result.duration:.1f}s")
print(f"  Errors: {result.errors}")
print()

if result.success and result.clips_graded > 0:
    print("  [PASS] E2E Test 1: auto_grade with LUT + Fusion succeeded!")
else:
    print("  [FAIL] E2E Test 1: auto_grade failed")
    if result.errors:
        for err in result.errors:
            print(f"    - {err}")

print()
print("=" * 60)
print("E2E COMPLETE")
print("=" * 60)
