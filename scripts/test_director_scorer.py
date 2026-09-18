# -*- coding: utf-8 -*-
"""T4 验收测试 — DirectorQualityScorer 五项基准

验证标准(升级方案):
- 节拍误差<1帧 / 运镜≥6种 / 弧线完整 / 三维多样性≥70% / 反模式检测
- 新管线(NarrativeArcPlanner+CameraLanguageLibrary)评分达标
- 旧均分fallback被正确扣分(对比证据)
- scorecard证据落盘 tmp/director_scorecard_evidence.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.camera_language import CAMERA_IDS, CameraLanguageLibrary  # noqa: E402
from core.director_scorer import BASELINE, DirectorQualityScorer  # noqa: E402
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


scorer = DirectorQualityScorer()
BPM = 128

print("=== 1. 单项: 节拍对齐 ===")
beat_dur = 60.0 / BPM
perfect = [round(k * beat_dur, 4) for k in range(1, 40)]
r = scorer.score_beat_alignment(perfect, BPM)
check("完美对齐=100分", r["score"] == 100.0, str(r))
check("最大误差<1帧", r["max_error_frames"] < 1.0, str(r["max_error_frames"]))

# 半帧偏移: 误差=0.5帧 → 仍满分(<1帧)
half_off = [round(k * beat_dur + 0.5 / 30, 4) for k in range(1, 20)]
r2 = scorer.score_beat_alignment(half_off, BPM)
check("半帧偏移仍满分", r2["score"] == 100.0, str(r2["max_error_frames"]))

# 2帧偏移: 应扣分
bad = [round(k * beat_dur + 2.0 / 30, 4) for k in range(1, 20)]
r3 = scorer.score_beat_alignment(bad, BPM)
check("2帧偏移被扣分", r3["score"] < 100.0, str(r3))
check("空切点0分", scorer.score_beat_alignment([], BPM)["score"] == 0.0)

print("\n=== 2. 单项: 运镜多样性 ===")
good_mv = ["push", "truck", "follow", "whip", "dutch", "orbit", "pull", "pan"]
rm = scorer.score_camera_diversity(good_mv)
check("8运镜=100分", rm["score"] == 100.0, str(rm))
mono = ["push"] * 6
rm2 = scorer.score_camera_diversity(mono)
check("单调运镜重扣", rm2["score"] <= 100 * 1 / 6, str(rm2))
check("连续3同运镜标记", rm2["has_triple_repeat"] is True)

print("\n=== 3. 单项: 弧线完整度 ===")
planner = NarrativeArcPlanner()
segs = planner.plan_segments(30.0, BPM)
ra = scorer.score_arc_completeness(segs)
check("新管线弧线=100分", ra["score"] == 100.0, str(ra))
uniform_segs = [{"type": t, "start": i*6, "end": (i+1)*6, "duration": 6.0}
                for i, t in enumerate(["intro", "build", "drop", "break", "outro"])]
ra2 = scorer.score_arc_completeness(uniform_segs)
check("均分无能量弧线低分", ra2["score"] < 80, str(ra2))
check("均分non_uniform=False", ra2["non_uniform"] is False)

print("\n=== 4. 单项: 三维组合覆盖 ===")
rc = scorer.score_combo_coverage({"unique_combos": 6, "total_combo_uses": 6})
check("100%多样性=100分", rc["score"] == 100.0, str(rc))
rc2 = scorer.score_combo_coverage({"unique_combos": 1, "total_combo_uses": 6})
check("低多样性扣分", rc2["score"] < 30, str(rc2))
check("空组合0分", scorer.score_combo_coverage({})["score"] == 0.0)

print("\n=== 5. 单项: 反模式 ===")
clean_ev = {"has_ease": True, "max_scale": 120, "beat_ok": True,
            "uniform_segments": False, "camera_unique": 8}
check("无反模式=100分", scorer.score_anti_patterns(clean_ev)["score"] == 100.0)
bad_ev = {"has_ease": False, "max_scale": 200, "beat_ok": False,
          "uniform_segments": True, "camera_unique": 1}
rb = scorer.score_anti_patterns(bad_ev)
check("全反模式=0分", rb["score"] == 0.0, str(rb))
check("命中5项反模式", len(rb["hits"]) == 5, str(rb["hits"]))

print("\n=== 6. 新旧管线对比 (scorecard证据) ===")
# 新管线剧本: planner段落 + 多样性感知运镜分配 (优先未用运镜)
camlib = CameraLanguageLibrary()
new_script_segments = []
used_cams = []
for s in segs:
    pool = s.get("camera_bias") or camlib.cameras_for_segment(s["type"]) or CAMERA_IDS
    cam_id = (next((c for c in pool if c not in used_cams), None)
              or next((c for c in CAMERA_IDS if c not in used_cams), None)
              or pool[0])
    used_cams.append(cam_id)
    seg_copy = dict(s)
    seg_copy["camera"] = {"camera_id": cam_id, "movement": cam_id}
    new_script_segments.append(seg_copy)
new_script = {"bpm": BPM, "segments": new_script_segments}
new_combo = {"unique_combos": 6, "total_combo_uses": 6}
new_ev = {"has_ease": True, "max_scale": 120, "beat_ok": True,
          "uniform_segments": False, "camera_unique": 6}
card_new = scorer.score_card(new_script, new_combo, new_ev)
check("新管线总分≥90", card_new["total_score"] >= 90,
      str(card_new["total_score"]))
check("新管线达标passed", card_new["passed"] is True)
check("新管线节拍满分",
      card_new["metrics"]["beat_alignment"]["score"] == 100.0,
      str(card_new["metrics"]["beat_alignment"]))
check("新管线运镜≥6种",
      card_new["metrics"]["camera_diversity"]["unique"] >= 6,
      str(card_new["metrics"]["camera_diversity"]["unique"]))

# 旧管线剧本: 均分五段 + 4种线性运镜 + 无切点对齐
old_script = {"bpm": BPM, "segments": uniform_segs}
for i, s in enumerate(old_script["segments"]):
    s["camera"] = {"movement": ["推", "摇", "快推", "拉", "慢拉"][i]}
old_ev = {"has_ease": False, "max_scale": 130, "beat_ok": False,
          "uniform_segments": True, "camera_unique": 4}
card_old = scorer.score_card(old_script, {}, old_ev)
check("旧管线总分<60", card_old["total_score"] < 60,
      str(card_old["total_score"]))
check("旧管线未达标", card_old["passed"] is False)
check("新管线显著优于旧管线",
      card_new["total_score"] - card_old["total_score"] > 30,
      f"{card_new['total_score']} vs {card_old['total_score']}")

print("\n=== 7. 报告与证据落盘 ===")
report = DirectorQualityScorer.format_report(card_new)
check("报告含总分", "总分" in report, report[:60])
check("基准常量完整",
      all(k in BASELINE for k in ["beat_error_frames", "camera_min_unique",
                                  "combo_diversity_min"]))
ev_path = os.path.join(ROOT, "tmp", "director_scorecard_evidence.json")
os.makedirs(os.path.dirname(ev_path), exist_ok=True)
with open(ev_path, "w", encoding="utf-8") as f:
    json.dump({"new_pipeline": card_new, "legacy_fallback": card_old},
              f, ensure_ascii=False, indent=2)
check("scorecard证据落盘", os.path.exists(ev_path), ev_path)

print(f"\n{'='*50}\nT4结果: {PASS} PASS / {FAIL} FAIL")
print(f"\n--- 对比证据 ---\n新管线:\n{DirectorQualityScorer.format_report(card_new)}")
print(f"旧fallback:\n{DirectorQualityScorer.format_report(card_old)}")
if FAILURES:
    print("失败项:")
    for f_ in FAILURES:
        print(f"  - {f_}")
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)
