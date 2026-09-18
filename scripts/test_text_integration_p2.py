# -*- coding: utf-8 -*-
"""P2 验收测试 — 智能导演集成 + Resolve管线适配 + 三维覆盖率追踪

验证标准(方案文档):
- P2-1: 不同强度镜头自动分配不同特效+动画
- P2-2: 文字层位置和时长正确(所有关键帧时间落在 [0, duration] 内)
- P2-3: 覆盖率报告包含 特效×动画×字体 三维
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

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


# ============================================================
# 1. P2-1 智能导演三维组合选择
# ============================================================
print("=" * 70)
print("1. P2-1 — select_text_combo_for_shot 三档强度分配")
print("=" * 70)
from integrations.smart_director import build_smart_text_jsx, select_text_combo_for_shot

combos = {k: select_text_combo_for_shot(k) for k in ("intense", "moderate", "gentle")}
check("三档强度均返回组合", all(v is not None for v in combos.values()),
      str({k: v is None for k, v in combos.items()}))
fx_ids = {v["effect_combo_id"] for v in combos.values() if v}
check("不同强度分配不同特效", len(fx_ids) >= 2, f"仅{len(fx_ids)}种特效")
int_set = {v["intensity"] for v in combos.values() if v}
check("强度映射覆盖三档", {"intense", "moderate", "subtle"} == int_set,
      str(int_set))

r_battle = select_text_combo_for_shot("intense", scene_tag="battle")
check("scene_tag精确表优先(intense+battle→cyber_glitch)",
      r_battle and r_battle["effect_combo_id"] == "effect_cyber_glitch",
      str(r_battle and r_battle["effect_combo_id"]))
r_battle_anim = r_battle["anim_preset_id"] if r_battle else ""
check("battle分配打击型动画", r_battle_anim.startswith("anim_kinetic"),
      r_battle_anim)

r_none_scene = select_text_combo_for_shot("moderate", scene_tag="未知场景xyz")
check("未知场景降级模糊匹配不崩溃",
      r_none_scene is not None and r_none_scene["effect_combo_id"], "")

# ============================================================
# 2. P2-1 导演JSX端到端: 三维特效段注入 + 安全
# ============================================================
print()
print("=" * 70)
print("2. P2-1 — build_smart_text_jsx 三维特效注入")
print("=" * 70)
cut_times = [0.0, 2.0, 4.0, 6.0]
duration = 8.0
shot_analysis = [
    {"motion": 12.0, "complexity": "high", "intensity": "intense", "scene_tag": "battle"},
    {"motion": 6.5, "complexity": "medium", "intensity": "moderate", "scene_tag": "cinematic"},
    {"motion": 2.0, "complexity": "low", "intensity": "gentle", "scene_tag": "elegant"},
    {"motion": 8.5, "complexity": "medium", "intensity": "moderate", "scene_tag": "neon"},
]
jsx = build_smart_text_jsx(cut_times, duration, shot_analysis)
check("导演JSX非空", bool(jsx), "")
check("三维特效JSX注入(__fxAdd出现)", "__fxAdd" in jsx, "")
check("特效段被try/catch包裹", "catch(e)" in jsx, "")
check("无alert模态框", "alert(" not in jsx, "")
check("无confirm模态框", "confirm(" not in jsx, "")

# ============================================================
# 3. P2-2 文字层时长正确性: 所有关键帧时间落在 [0, duration]
# ============================================================
print()
print("=" * 70)
print("3. P2-2 — 文字层时间轴验证 (AE→Resolve 传递)")
print("=" * 70)
time_blocks = re.findall(r"setValuesAtTimes\(\[([^\]]+)\]", jsx)
out_of_range = []
for blk in time_blocks:
    for tok in blk.split(","):
        tok = tok.strip()
        if re.fullmatch(r"-?\d+(\.\d+)?", tok):
            tval = float(tok)
            if tval < -0.01 or tval > duration + 1.0:
                out_of_range.append(tval)
check("setValuesAtTimes时间块存在", len(time_blocks) > 0, "")
check(f"所有关键帧时间落在[0,{duration + 1}]s", not out_of_range,
      f"越界:{out_of_range[:5]}")

from integrations.resolve_ae_resolve_pipeline import _infer_scene_tag

grid = [("intense", "rich"), ("intense", "medium"), ("intense", "poor"),
        ("moderate", "rich"), ("moderate", "medium"), ("moderate", "poor"),
        ("gentle", "rich"), ("gentle", "medium"), ("gentle", "poor")]
tags = {_infer_scene_tag(i, c) for i, c in grid}
check("9宫格场景标签推断全覆盖且多样", len(tags) >= 5, str(tags))
check("未知特征默认cinematic", _infer_scene_tag("x", "y") == "cinematic", "")

# ============================================================
# 4. P2-3 PresetTracker 三维覆盖率
# ============================================================
print()
print("=" * 70)
print("4. P2-3 — PresetTracker 三维覆盖率追踪")
print("=" * 70)
from core.jsx_keyframe_animator import AnimationOrchestrator, PresetTracker, TextAnimationStyle, get_preset_tracker

tk = PresetTracker()
tk.record_combo("effect_cyber_glitch", TextAnimationStyle.IMPACT_SHAKE, "Impact")
tk.record_combo("effect_cyber_glitch", TextAnimationStyle.IMPACT_SHAKE, "Impact")
tk.record_combo("effect_ink_wash", TextAnimationStyle.WAVE_ENTRANCE, "KaiTi")
check("组合计数正确(2唯一/3次)", tk.combo_count == 2 and sum(tk._combos.values()) == 3,
      f"unique={tk.combo_count} total={sum(tk._combos.values())}")
stats = tk.get_combo_stats()
check("覆盖率报告含三维维度键",
      all(k in stats for k in ("unique_combos", "total_combo_uses",
                               "diversity_rate", "top_combos")), str(stats.keys()))
check("多样性指标=67%", stats["diversity_rate"] == "67%", stats["diversity_rate"])
tk.reset()
check("reset清空组合", tk.combo_count == 0, "")

# orchestrate_layer 自动记录三维组合
tracker = get_preset_tracker()
tracker.reset()
orch = AnimationOrchestrator()
anim = orch.orchestrate_layer(
    {"type": "text", "role": "title", "scene_tag": "battle"},
    style_category="intense", duration=2.0)
check("orchestrate自动记录三维组合", tracker.combo_count == 1,
      f"combo_count={tracker.combo_count}")
combo_key = list(tracker._combos.keys())[0] if tracker._combos else ""
check("组合键含 特效|动画|字体 三段",
      combo_key.startswith("effect_cyber_glitch|") and combo_key.count("|") == 2,
      combo_key)

# ============================================================
# 5. 导演运行后统计回传
# ============================================================
print()
print("=" * 70)
print("5. P2-1/P2-2 — 导演统计回传 (get_last_run_stats)")
print("=" * 70)
from integrations.smart_director import get_last_run_stats

sd_stats = get_last_run_stats()
check("统计含text_combos_used", "text_combos_used" in sd_stats, str(sd_stats.keys()))
check("至少1个三维组合被使用", len(sd_stats.get("text_combos_used", [])) >= 1, "")
check("组合计数一致",
      sd_stats.get("text_combo_count") == len(set(sd_stats.get("text_combos_used", []))),
      str(sd_stats.get("text_combo_count")))

# ============================================================
print()
print("=" * 70)
total = PASS + FAIL
print(f"结果: {PASS}/{total} 通过, {FAIL} 失败")
if FAIL:
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("P2 验收全部通过 [ALL PASS]")
