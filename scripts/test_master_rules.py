# -*- coding: utf-8 -*-
"""T2 验收测试 — master_rules.json 结构 + CameraLanguageLibrary 8运镜JSX

验证标准(升级方案):
- master_rules.json 四类检查项齐全 (bpm_frame_table/camera_templates/
  master_presets/anti_patterns + energy_envelope)
- 8运镜JSX全部带Ease曲线、无alert、scale≤150、try/catch包裹
- 段落适配查询与中文运镜名兼容
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.camera_language import CAMERA_IDS, CameraLanguageLibrary, load_master_rules  # noqa: E402

PASS = 0
FAIL = 0
FAILURES = []


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


print("=== 1. master_rules.json 结构完整性 ===")
rules = load_master_rules()
for key in ["bpm_frame_table", "camera_templates", "master_presets",
            "anti_patterns", "energy_envelope"]:
    check(f"存在顶层键: {key}", key in rules)

bpm = rules["bpm_frame_table"]
check("BPM表含128条目", "128" in bpm["entries"])
check("128bpm每拍14帧(30fps)", bpm["entries"]["128"] == 14,
      str(bpm["entries"].get("128")))
check("容差1帧", bpm["tolerance_frames"] == 1)
# 帧数表数学一致性: 1800/bpm
for b, fr in bpm["entries"].items():
    check(f"BPM {b} 帧数一致(1800/bpm)", abs(fr - round(1800 / int(b))) <= 1,
          f"{fr} vs {1800/int(b):.1f}")

check("8运镜模板齐全",
      set(CAMERA_IDS) <= set(rules["camera_templates"].keys()),
      str(set(rules["camera_templates"].keys())))
check("6位大师预设", len([k for k in rules["master_presets"]
                          if not k.startswith("_")]) >= 6)
check("5项反模式", len([k for k in rules["anti_patterns"]
                        if not k.startswith("_")]) == 5)
env = rules["energy_envelope"]["segments"]
ratio_sum = sum(v["ratio"] for v in env.values())
check("能量包络占比合计=1.0", abs(ratio_sum - 1.0) < 1e-6, str(ratio_sum))
check("drop段含二次drop配置", "second_drop_at" in env["drop"])

print("\n=== 2. 8运镜JSX生成 (带Ease曲线) ===")
cam = CameraLanguageLibrary()
check("list_cameras返回8种", len(cam.list_cameras()) == 8,
      str(cam.list_cameras()))

for cid in CAMERA_IDS:
    jsx = cam.to_jsx(cid, "segL", 0.0, 5.0)
    check(f"[{cid}] JSX非空", bool(jsx))
    v = CameraLanguageLibrary.validate_jsx(jsx)
    check(f"[{cid}] 校验通过", v["ok"], str(v["issues"]))
    check(f"[{cid}] 含KeyframeEase", "KeyframeEase" in jsx)
    check(f"[{cid}] 含setTemporalEaseAtKey", "setTemporalEaseAtKey" in jsx)
    check(f"[{cid}] 无alert/confirm",
          "alert(" not in jsx and "confirm(" not in jsx)
    check(f"[{cid}] try/catch包裹",
          jsx.strip().startswith("try {") and jsx.strip().endswith("} catch(e) {}"))

print("\n=== 3. 运镜专项特性 ===")
whip = cam.to_jsx("whip", "segL", 0.0, 2.0)
check("whip含运动模糊", "motionBlur = true" in whip)
push_fast = cam.to_jsx("push", "segL", 0.0, 2.0, speed_factor=5.0)
v = CameraLanguageLibrary.validate_jsx(push_fast)
check("push speed_factor=5 仍≤150%", v["ok"], str(v["issues"]))
check("push fast封顶150", "150" in push_fast)

print("\n=== 4. 段落适配与中文兼容 ===")
check("intro适配含push", "push" in cam.cameras_for_segment("intro"))
check("drop适配含whip", "whip" in cam.cameras_for_segment("drop"))
check("break适配含pull", "pull" in cam.cameras_for_segment("break"))
check("outro适配含pull", "pull" in cam.cameras_for_segment("outro"))
check("中文'快推'→push", cam.camera_by_cn("快推") == "push")
check("中文'慢拉'→pull", cam.camera_by_cn("慢拉") == "pull")
check("中文'甩镜'→whip", cam.camera_by_cn("甩镜") == "whip")
check("未知运镜返回None", cam.camera_by_cn("不存在的运镜") is None)
check("未知camera to_jsx返回空串", cam.to_jsx("nonexist", "L", 0, 1) == "")

print("\n=== 5. 反模式检测能力 ===")
bad_jsx = 'p.setValueAtTime(0, [100,100]); p.setValueAtTime(5, [100,100]);'
vb = CameraLanguageLibrary.validate_jsx(bad_jsx)
check("线性无Ease被检出", not vb["ok"] and
      any("without ease" in i for i in vb["issues"]), str(vb["issues"]))

print(f"\n{'='*50}\nT2结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f_ in FAILURES:
        print(f"  - {f_}")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
