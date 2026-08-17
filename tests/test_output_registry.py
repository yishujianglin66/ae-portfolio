# -*- coding: utf-8 -*-
"""T1 验收测试 — OutputRegistry 产物注册与验证

验证标准(升级方案):
- 现有3个交付视频登记后 verify_all 全绿 (ffprobe 实测)
- manifest 清单生成且 green==total
- MISSING/CORRUPT 分支可被正确识别
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config.output_registry import (  # noqa: E402
    OutputRegistry, DELIVERY_ROOT, get_registry)

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


KNOWN_VIDEOS = [
    "hybrid_final.mp4",
    "text_animation_preview.mp4",
    "text_ground_truth_showcase.mp4",
]

print("=== 1. 交付目录与已知产物 ===")
check("交付目录存在", os.path.isdir(DELIVERY_ROOT), DELIVERY_ROOT)
for v in KNOWN_VIDEOS:
    p = os.path.join(DELIVERY_ROOT, v)
    check(f"已知产物存在: {v}", os.path.exists(p), p)

print("\n=== 2. register + verify_all (ffprobe实测) ===")
reg = OutputRegistry()
for v in KNOWN_VIDEOS:
    e = reg.register(v, category="video")
    check(f"登记成功: {v}", e["path"].startswith(DELIVERY_ROOT), e["path"])
check("登记数量=3", len(reg.entries) == 3, f"got {len(reg.entries)}")

# 重复登记去重
reg.register(KNOWN_VIDEOS[0], category="video")
check("重复登记去重", len(reg.entries) == 3, f"got {len(reg.entries)}")

results = reg.verify_all()
check("verify_all 返回3项", len(results) == 3, f"got {len(results)}")
check("全部OK(全绿)", all(r["status"] == "OK" for r in results),
      str([r["status"] for r in results]))
check("all_green() 为 True", reg.all_green() is True)
for r in results:
    check(f"时长>0: {r['name']}", r.get("duration", 0) > 0,
          str(r.get("duration")))
    check(f"分辨率1080系: {r['name']}",
          (r.get("width") or 0) >= 1080 and (r.get("height") or 0) >= 720,
          f"{r.get('width')}x{r.get('height')}")

print("\n=== 3. scan_existing 自动扫描 ===")
reg2 = OutputRegistry()
added = reg2.scan_existing()
names = {e["name"] for e in reg2.entries}
check("扫描登记>=3", added >= 3, f"added={added}")
check("扫描覆盖已知视频", all(v in names for v in KNOWN_VIDEOS),
      str(names))

print("\n=== 4. MISSING / CORRUPT 异常分支 ===")
reg3 = OutputRegistry()
reg3.register("not_exist_video.mp4", category="video")
r_missing = reg3.verify_all()[0]
check("MISSING识别", r_missing["status"] == "MISSING", r_missing["status"])
check("异常时all_green为False", reg3.all_green() is False)

# 伪造损坏文件 (非视频字节)
tmp_dir = tempfile.mkdtemp(prefix="reg_test_")
corrupt = os.path.join(tmp_dir, "corrupt.mp4")
with open(corrupt, "wb") as f:
    f.write(b"this is not a video" * 10)
reg4 = OutputRegistry()
reg4.register(corrupt, category="video")
r_corrupt = reg4.verify_all()[0]
check("CORRUPT识别", r_corrupt["status"] == "CORRUPT", r_corrupt["status"])

print("\n=== 5. manifest 清单生成 ===")
manifest_path = reg.save_manifest(os.path.join(tmp_dir, "output_manifest.json"))
check("manifest已写入", os.path.exists(manifest_path), manifest_path)
with open(manifest_path, encoding="utf-8") as f:
    manifest = json.load(f)
check("manifest total=3", manifest["total"] == 3, str(manifest["total"]))
check("manifest green=3(全绿)", manifest["green"] == 3, str(manifest["green"]))
check("manifest entries含verify结果",
      all("verify" in e for e in manifest["entries"]))
check("delivery_root正确", manifest["delivery_root"] == DELIVERY_ROOT)

print("\n=== 6. 单例与报告 ===")
check("get_registry单例", get_registry() is get_registry())
report = reg.report()
check("report含全部条目", all(v in report for v in KNOWN_VIDEOS))

print(f"\n{'='*50}\nT1结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f_ in FAILURES:
        print(f"  - {f_}")
sys.exit(1 if FAIL else 0)
