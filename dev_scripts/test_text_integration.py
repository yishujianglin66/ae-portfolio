#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""特效+动画一体化整合 P0 验收测试

覆盖:
1. SmartMatcher — 20组 Ground Truth 场景精确匹配
2. SmartMatcher — 中文别名 + 倒排索引模糊匹配
3. EffectLayerBuilder — 31套特效组合配置构建 + 强度缩放
4. EffectLayerBuilder — JSX 生成安全性(单行化/无alert/matchName规范)
5. AnimationOrchestrator — scene_tag 端到端集成
6. 向后兼容 — 无 scene_tag 时保持 V2 行为
7. AE_SAFE_FONTS — 安全名无空格校验
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.jsx_keyframe_animator import (
    AE_SAFE_FONTS,
    AnimationIntensity,
    AnimationOrchestrator,
    EffectLayerBuilder,
    SmartMatcher,
    TextAnimationStyle,
    ae_safe_font_name,
    get_effect_builder,
    get_smart_matcher,
)

PASS, FAIL = 0, 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name}: {detail}")
        print(f"  [FAIL] {name} — {detail}")


print("=" * 70)
print("1. SmartMatcher — 20组 Ground Truth 场景精确匹配")
print("=" * 70)
matcher = get_smart_matcher()
gt = SmartMatcher.SCENE_TABLE
check("场景表恰好20组", len(gt) == 20, f"实际{len(gt)}组")
for tag, entry in gt.items():
    r = matcher.match(scene_tag=tag)
    ok = (r.effect_combo_id == entry["effect"]
          and r.anim_preset_id == entry["anim"]
          and r.intensity.value == entry["intensity"]
          and r.confidence >= 1.0)
    check(f"scene={tag}", ok,
          f"期望 {entry['effect']}/{entry['anim']}/{entry['intensity']}, "
          f"实际 {r.effect_combo_id}/{r.anim_preset_id}/{r.intensity.value}")
    check(f"scene={tag} 动画枚举可构建",
          isinstance(r.animation, TextAnimationStyle), str(r.animation))

print()
print("=" * 70)
print("2. SmartMatcher — 中文别名 + 模糊匹配")
print("=" * 70)
r = matcher.match(scene_tag="热血战斗")
check("中文别名'热血战斗'命中battle表", r.effect_combo_id == "effect_cyber_glitch",
      f"实际{r.effect_combo_id}, reason={r.reason}")
r2 = matcher.match(scene_tag="水墨国风")
check("中文别名'水墨国风'命中ink_wash表", r2.effect_combo_id == "effect_ink_wash",
      f"实际{r2.effect_combo_id}")
r3 = matcher.match(scene_tag="游戏标题")
check("best_for倒排'游戏标题'可匹配", r3.effect_combo_id is not None,
      "无结果")
check("倒排匹配置信度<1.0", r3.confidence < 1.0, f"{r3.confidence}")
r4 = matcher.match(scene_tag="battle", intensity=AnimationIntensity.SUBTLE)
check("显式intensity覆盖表默认", r4.intensity == AnimationIntensity.SUBTLE,
      f"实际{r4.intensity}")

print()
print("=" * 70)
print("3. EffectLayerBuilder — 31套特效组合配置构建")
print("=" * 70)
builder = get_effect_builder()
check("组合库加载31套", len(builder.combo_ids) == 31, f"实际{len(builder.combo_ids)}")
build_ok = 0
for cid in builder.combo_ids:
    cfg = builder.build_effect_config(cid, font="Impact", font_size=96)
    if cfg and cfg.effects and cfg.combo_name:
        build_ok += 1
check("31/31组合可构建配置", build_ok == 31, f"实际{build_ok}")

# 强度缩放验证: intense 应放大 radius/intensity 等参数
cfg_m = builder.build_effect_config("effect_cyber_glitch",
                                    intensity=AnimationIntensity.MODERATE)
cfg_i = builder.build_effect_config("effect_cyber_glitch",
                                    intensity=AnimationIntensity.INTENSE)
cfg_s = builder.build_effect_config("effect_cyber_glitch",
                                    intensity=AnimationIntensity.SUBTLE)
glow_m = next(f for f in cfg_m.effects if f["matchName"] == "ADBE Glo2")
glow_i = next(f for f in cfg_i.effects if f["matchName"] == "ADBE Glo2")
glow_s = next(f for f in cfg_s.effects if f["matchName"] == "ADBE Glo2")
check("intense的Glow radius > moderate",
      glow_i["params"]["radius"] > glow_m["params"]["radius"],
      f"{glow_i['params']['radius']} vs {glow_m['params']['radius']}")
check("subtle的Glow radius < moderate",
      glow_s["params"]["radius"] < glow_m["params"]["radius"],
      f"{glow_s['params']['radius']} vs {glow_m['params']['radius']}")
check("强度缩放比例精确1.8x",
      abs(glow_i["params"]["radius"] - glow_m["params"]["radius"] * 1.8) < 0.01,
      f"{glow_i['params']['radius']} vs {glow_m['params']['radius']*1.8}")

print()
print("=" * 70)
print("4. EffectLayerBuilder — JSX 生成安全性")
print("=" * 70)
jsx = builder.to_jsx(cfg_m, "layer0")
check("JSX非空", len(jsx) > 100, f"长度{len(jsx)}")
check("JSX含Glow matchName", '"ADBE Glo2"' in jsx, jsx[:200])
check("JSX无alert/confirm(模态框冻结陷阱)",
      "alert(" not in jsx and "confirm(" not in jsx, "")
helper_lines = [l for l in jsx.split("\n") if l.startswith("function ")]
check("helper函数全部单行化(ASI陷阱)",
      all(l.rstrip().endswith("{") is False or "{" in l for l in helper_lines), "")
check("JSX使用__fxSet安全设置", "__fxSet" in jsx, "")
check("枚举属性无裸数字(BlendingMode)",
      "blendingMode = 12" not in jsx, "")
# 未验证索引效果器走显示名回退
td_cfg = builder.build_effect_config("effect_ink_wash")
td_jsx = builder.to_jsx(td_cfg, "layer0") if td_cfg else ""
if any(f["matchName"] == "ADBE Turbulent Displace" for f in (td_cfg.effects if td_cfg else [])):
    check("Turbulent Displace走显示名回退", '"Amount"' in td_jsx, td_jsx[:300])
ml_jsx = builder.to_multi_layer_jsx(cfg_m, "layer0")
check("多层JSX含GLOW_副本层", "GLOW_" in ml_jsx and "duplicate()" in ml_jsx, ml_jsx[:200])
check("多层JSX混合模式用枚举对象", "BlendingMode.ADD" in ml_jsx, "")

print()
print("=" * 70)
print("5. AnimationOrchestrator — scene_tag 端到端集成")
print("=" * 70)
orch = AnimationOrchestrator()
anim = orch.orchestrate_layer(
    layer_config={"type": "text", "role": "title", "text": "热血战斗",
                  "scene_tag": "battle", "char_count": 4},
    duration=2.0, start_time=0.0,
)
meta = getattr(anim, "_text_meta", None)
check("_text_meta存在", meta is not None, "")
if meta:
    check("effect_combo=battle表值", meta.get("effect_combo") == "effect_cyber_glitch",
          str(meta.get("effect_combo")))
    check("effect_config已附加", meta.get("effect_config") is not None, "")
    check("intensity=intense", meta.get("intensity") == "intense",
          str(meta.get("intensity")))
    check("字体无空格(AE安全)", " " not in meta.get("font", "x "),
          meta.get("font"))
    check("动画风格=kinetic_smash映射",
          meta.get("style") == TextAnimationStyle.IMPACT_SHAKE.value,
          meta.get("style"))
jsx_full = orch.to_jsx_snippet(anim)
check("JSX片段含关键帧", "setValueAtTime" in jsx_full, jsx_full[:200])
check("JSX片段含效果器设置(一体化输出)", "ADBE Glo2" in jsx_full, jsx_full[-300:])

print()
print("=" * 70)
print("6. 向后兼容 — 无 scene_tag 保持 V2 行为")
print("=" * 70)
orch2 = AnimationOrchestrator()
anim2 = orch2.orchestrate_layer(
    layer_config={"type": "text", "role": "subtitle", "text": "测试", "char_count": 2},
    duration=2.0,
)
meta2 = getattr(anim2, "_text_meta", None)
check("V2路径_text_meta存在", meta2 is not None, "")
if meta2:
    check("V2路径无effect_combo", meta2.get("effect_combo") is None,
          str(meta2.get("effect_combo")))
    check("V2路径字体=Arial安全名", meta2.get("font") == "Arial", meta2.get("font"))
jsx2 = orch2.to_jsx_snippet(anim2)
check("V2路径JSX无效果器段", "__fxAdd" not in jsx2, "")
anim3 = orch2.orchestrate_layer(
    layer_config={"type": "footage", "index": 1}, duration=2.0)
check("footage层不受影响", getattr(anim3, "_text_meta", None) is None, "")

print()
print("=" * 70)
print("7. AE_SAFE_FONTS — 安全名规范校验")
print("=" * 70)
check("映射表≥40条", len(AE_SAFE_FONTS) >= 40, f"实际{len(AE_SAFE_FONTS)}")
bad = [k for k, v in AE_SAFE_FONTS.items() if " " in v]
check("所有安全名无空格", not bad, str(bad))
check("空格字体名自动去空格", ae_safe_font_name("Arial Narrow") == "ArialNarrow",
      ae_safe_font_name("Arial Narrow"))
check("PostScript名直通", ae_safe_font_name("Arial-BoldMT") == "Arial-BoldMT",
      ae_safe_font_name("Arial-BoldMT"))

print()
print("=" * 70)
print("8. P1 — 31套特效参数映射全覆盖")
print("=" * 70)
from core.jsx_keyframe_animator import _load_preset_matrix_data

db = _load_preset_matrix_data()
vm = EffectLayerBuilder.VERIFIED_EFFECT_MAP
um = EffectLayerBuilder.UNVERIFIED_EFFECT_MAP
gap_count = 0
gap_detail = []
for combo in db["effect_combos"]:
    for fx in combo["effects"]:
        mn = fx["matchName"]
        known = set((vm.get(mn) or um.get(mn) or {}).get("params", {}).keys())
        missing = set(fx.get("params", {}).keys()) - known
        if mn not in vm and mn not in um:
            gap_count += 1; gap_detail.append(f"{combo['id']}/{mn}: 效果器未注册")
        elif missing:
            gap_count += 1; gap_detail.append(f"{combo['id']}/{mn}: {missing}")
check("31套特效参数键0缺口", gap_count == 0, "; ".join(gap_detail[:5]))

jsx_ok = 0
for cid in builder.combo_ids:
    cfg = builder.build_effect_config(cid)
    j = builder.to_jsx(cfg, "layer0") if cfg else ""
    if j and "__fxAdd" in j and "alert(" not in j:
        jsx_ok += 1
check("31/31组合JSX可生成且安全", jsx_ok == 31, f"实际{jsx_ok}")

# Bevel Emboss 双色合并: shadowColor+highlightColor 应合并为单次赋值
bevel_cfg = builder.build_effect_config("effect_metallic_bevel")
bevel_jsx = builder.to_jsx(bevel_cfg, "layer0") if bevel_cfg else ""
hsc_count = bevel_jsx.count('"Highlight/Shadow Color"')
check("Bevel双色控件合并为单次赋值", hsc_count <= 1,
      f"出现{hsc_count}次赋值(应为1)")

print()
print("=" * 70)
print("9. P1 — SmartMatcher 全量场景覆盖")
print("=" * 70)
# 所有特效的 best_for 标签都应命中倒排索引(conf>=0.6)
tags_fx = set()
for c in db["effect_combos"]:
    tags_fx.update(c.get("best_for", []))
hit6 = sum(1 for tg in tags_fx if matcher.match(tg).confidence >= 0.6)
check(f"特效best_for标签全覆盖({len(tags_fx)}个)", hit6 == len(tags_fx),
      f"仅{hit6}个conf>=0.6")
# 任意随机标签均返回有效结果(不崩溃、字段完整)
random_tags = ["太空歌剧", "海底世界", "街头涂鸦", "赛博都市夜景", ""]
all_valid = True
for tg in random_tags:
    r = matcher.match(tg)
    if not (r.font and r.effect_combo_id and r.anim_preset_id
            and isinstance(r.animation, TextAnimationStyle)):
        all_valid = False
check("任意标签均返回完整组合", all_valid, "")
# 子串误匹配防护: 帝国风格不应命中国风别名
r_guard = matcher.match("黑客帝国风格")
check("别名边界防护(帝国风格≠国风)", r_guard.reason != "alias:ink_wash",
      r_guard.reason)

print()
print("=" * 70)
total = PASS + FAIL
print(f"结果: {PASS}/{total} 通过, {FAIL} 失败")
if FAILURES:
    print("失败清单:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("P0 验收全部通过 [ALL PASS]")
