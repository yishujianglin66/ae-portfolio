"""测试 DCTL 预设查找"""
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import DCTL_PRESET_MAP, find_dctl_for_preset, find_lut_for_preset

print("=== DCTL 预设查找测试 ===")
for name in DCTL_PRESET_MAP:
    result = find_dctl_for_preset(name)
    status = "OK" if result else "NOT FOUND"
    print(f"  [{status}] {name}: {result}")

print("\n=== find_lut_for_preset 集成测试 ===")
for preset in ["cinematic", "filmic", "opendrt", "film", "tesseract"]:
    result = find_lut_for_preset(preset)
    ext = result.split(".")[-1] if result else "N/A"
    print(f"  {preset} -> {ext} : {result}")
