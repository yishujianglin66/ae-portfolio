# -*- coding: utf-8 -*-
"""T3 验收测试 — NarrativeArcPlanner + StyleProfile

验证标准(升级方案):
- 五段时长比符合能量包络 (12/24/34/12/18)，非均分
- 每段携带 energy_target/scene_tag/intensity/camera_bias/cut_times
- drop 段 70% 处有 breath break 喘息点
- 切点对齐 BPM 网格 (帧级容差)
- 能量曲线单调特性 (build上升/break急降)
- StyleProfile 20组风格精确映射
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.narrative_arc import NarrativeArcPlanner, StyleProfile  # noqa: E402

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


planner = NarrativeArcPlanner()
TOTAL, BPM = 30.0, 128

print("=== 1. 段落结构 (能量包络非均分) ===")
segs = planner.plan_segments(TOTAL, BPM)
main_types = [s["type"] for s in segs if s["type"] != "breath_break"]
check("五段齐全", main_types == ["intro", "build", "drop", "break", "outro"],
      str(main_types))
check("含breath_break段", any(s["type"] == "breath_break" for s in segs))

# 时长比验证
expected_ratio = {"intro": 0.12, "build": 0.24, "drop": 0.34,
                  "break": 0.12, "outro": 0.18}
durs = {s["type"]: s["duration"] for s in segs if s["type"] in expected_ratio}
for st, ratio in expected_ratio.items():
    actual = durs[st] / TOTAL
    check(f"{st}时长比≈{ratio}", abs(actual - ratio) < 0.005,
          f"actual={actual:.3f}")
dvals = list(durs.values())
check("非均分(时长不全相等)", len(set(round(d, 2) for d in dvals)) > 1,
      str(dvals))
check("drop最长", durs["drop"] == max(dvals), str(durs))

print("\n=== 2. 段落字段完整性 ===")
for s in segs:
    if s["type"] == "breath_break":
        continue
    ok = all(k in s for k in ["energy_target", "scene_tag", "intensity",
                              "camera_bias", "cut_times", "cut_beats"])
    check(f"[{s['type']}] 六字段齐全", ok, str(list(s.keys())))

print("\n=== 3. breath break 喘息点 ===")
drop = next(s for s in segs if s["type"] == "drop")
brk = next(s for s in segs if s["type"] == "breath_break")
expect_pos = drop["start"] + drop["duration"] * 0.7
check("位置在drop70%处", abs(brk["start"] - expect_pos) < 0.01,
      f"{brk['start']} vs {expect_pos}")
beat_dur = 60.0 / BPM
check("时长2-4拍", 2 * beat_dur - 0.05 <= brk["duration"] <= 4 * beat_dur + 0.05,
      str(brk["duration"]))
check("能量从1.0回落", brk["energy_target"][0] == 1.0 and
      brk["energy_target"][1] < 1.0)

print("\n=== 4. BPM网格切点对齐 ===")
frames_per_beat = planner.frames_per_beat(BPM)
check("128bpm每拍14帧", frames_per_beat == 14, str(frames_per_beat))
fps = 30
for s in segs:
    if s["type"] in ("break", "breath_break"):
        check(f"[{s['type']}] 留白无切点", s["cut_times"] == [],
              str(s["cut_times"]))
        continue
    cuts = s["cut_times"]
    check(f"[{s['type']}] 有切点", len(cuts) > 0, str(len(cuts)))
    # 节拍对齐: 每个切点到最近半拍理想时刻的偏差 ≤ 半帧 (节拍误差<1帧基准)
    beat_dur = 60.0 / BPM
    align_ok = all(
        abs(c / beat_dur - round(c / beat_dur * 2) / 2) * beat_dur <= 0.5 / fps + 0.002
        for c in cuts)
    check(f"[{s['type']}] 节拍误差≤半帧", align_ok, str(cuts[:3]))
    # 帧吸附: 切点时间×fps必为整数帧
    int_frame_ok = all(abs(c * fps - round(c * fps)) < 0.02 for c in cuts)
    check(f"[{s['type']}] 切点吸附整数帧", int_frame_ok, str(cuts[:3]))
    # 单调递增
    check(f"[{s['type']}] 切点单调递增", cuts == sorted(cuts))

print("\n=== 5. 能量曲线特性 ===")
intro_seg = segs[0]
e_intro_start = planner.energy_at(segs, intro_seg["start"])
e_intro_end = planner.energy_at(segs, intro_seg["end"])
check("intro能量上升(0.2→0.35)", e_intro_start < e_intro_end,
      f"{e_intro_start}->{e_intro_end}")
build_seg = next(s for s in segs if s["type"] == "build")
check("build能量阶梯上升(0.35→0.7)",
      planner.energy_at(segs, build_seg["start"]) <
      planner.energy_at(segs, build_seg["end"]))
break_seg = next(s for s in segs if s["type"] == "break")
e_b0 = planner.energy_at(segs, break_seg["start"])
e_b1 = planner.energy_at(segs, break_seg["end"])
check("break急降(1.0→0.15)", e_b0 > e_b1 and e_b0 >= 0.95,
      f"{e_b0}->{e_b1}")
drop_mid = planner.energy_at(segs, drop["start"] + drop["duration"] * 0.5)
check("drop高潮能量≥0.9", drop_mid >= 0.9, str(drop_mid))

print("\n=== 6. StyleProfile 20组风格映射 ===")
sp = StyleProfile()
styles = sp.list_styles()
check("风格数=20", len(styles) == 20, str(len(styles)))
prof = sp.resolve("热血战斗")
check("热血战斗精确解析", prof is not None)
check("热血战斗drop→battle", prof["scene_tags"]["drop"] == "battle")
check("水墨国风drop→magic", sp.resolve("水墨国风")["scene_tags"]["drop"] == "magic")
check("赛博朋克drop→cyberpunk",
      sp.resolve("赛博朋克")["scene_tags"]["drop"] == "cyberpunk")
check("别名解析: 燃向→热血战斗", sp.resolve("燃向") is prof)
check("别名解析: AMV→动漫燃剪",
      sp.resolve("AMV")["scene_tags"]["drop"] == "anime")
check("未知风格返回None", sp.resolve("完全不存在的风格xyz") is None)

# 风格注入 planner
pp = sp.to_planner_profile("水墨国风")
segs_styled = planner.plan_segments(TOTAL, BPM, style_profile=pp)
drop_styled = next(s for s in segs_styled if s["type"] == "drop")
check("风格注入: drop scene_tag=magic", drop_styled["scene_tag"] == "magic")
check("风格注入: intro scene_tag=ink_wash",
      segs_styled[0]["scene_tag"] == "ink_wash")
check("风格注入: camera_bias含orbit",
      "orbit" in drop_styled["camera_bias"], str(drop_styled["camera_bias"]))

# scene_tag 全部为 SmartMatcher 合法标签
VALID_TAGS = {"battle", "cyberpunk", "cinematic", "anime", "ink_wash", "neon",
              "social", "horror", "tech", "elegant", "sport", "retro", "magic",
              "industrial", "cute", "data", "brand", "comic", "title_kit", "lyric"}
all_tags_ok = all(
    tag in VALID_TAGS
    for sname in styles
    for tag in sp.resolve(sname)["scene_tags"].values())
check("20组×5段 scene_tag全部合法", all_tags_ok)

print("\n=== 7. 异常防护 ===")
try:
    planner.plan_segments(0, BPM)
    check("total_dur=0抛异常", False, "no exception")
except ValueError:
    check("total_dur=0抛异常", True)
check("bpm=0不崩溃", len(planner.plan_segments(10, 0)) >= 5)

print(f"\n{'='*50}\nT3结果: {PASS} PASS / {FAIL} FAIL")
if FAILURES:
    print("失败项:")
    for f_ in FAILURES:
        print(f"  - {f_}")
sys.exit(1 if FAIL else 0)
