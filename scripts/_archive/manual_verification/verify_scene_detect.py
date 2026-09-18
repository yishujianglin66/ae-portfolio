"""测试 PySceneDetect 场景检测集成"""
import sys

sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import ResolveColorEngine

engine = ResolveColorEngine()

# 测试场景检测
video = r"D:\AE-Work\output\VinlandSaga_Battle_V2.mp4"
print(f"Detecting scenes in: {video}")
scenes = engine.detect_scenes(video, threshold=27.0)

if scenes and "error" in scenes[0]:
    print(f"ERROR: {scenes[0]['error']}")
else:
    print(f"Detected {len(scenes)} scenes:")
    for i, s in enumerate(scenes[:15]):
        print(f"  Scene {i}: {s['start']} -> {s['end']} ({s['duration_frames']} frames)")

# 测试自动预设生成
print("\nAuto segment presets:")
presets = engine.auto_segment_presets(video, threshold=27.0)
for key, val in presets.items():
    print(f"  {key} -> {val}")
