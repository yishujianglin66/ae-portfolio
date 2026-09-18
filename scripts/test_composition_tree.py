"""CompositionTree 单元测试（M1a 验收）"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.composition_tree import (
    STYLE_CARDS,
    AnimationSpec,
    CompositionTree,
    EffectRef,
    LayerSpec,
    build_template,
    validate_composition_tree,
)

passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} {detail}")


print("=" * 60)
print("1. 三风格模板构建")
print("=" * 60)
trees = {}
for card in STYLE_CARDS:
    t = build_template(card)
    trees[card] = t
    check(f"{card} 模板构建", t.comp_name and t.style_card == card and len(t.layers) >= 2,
          f"layers={len(t.layers)}")
    res = validate_composition_tree(t)
    check(f"{card} 模板校验通过", res["ok"], str(res["errors"][:2]))

print("=" * 60)
print("2. schema 校验：合法/非法边界")
print("=" * 60)
t = build_template("cyberpunk")
res = validate_composition_tree(t)
check("cyberpunk 零错误", not res["errors"])

# 非法：图层 id 重复
t2 = build_template("amv")
t2.layers.append(LayerSpec(id="title", type="text", name="dup", time_range=[0, 1]))
res2 = validate_composition_tree(t2)
check("重复 id 检出", any("重复" in e for e in res2["errors"]))

# 非法：非法图层类型
t3 = build_template("ambient")
t3.layers[0].type = "invalid_type"
res3 = validate_composition_tree(t3)
check("非法类型检出", any("类型" in e for e in res3["errors"]))

# 非法：素材图层缺 path
t4 = build_template("amv")
t4.layers.append(LayerSpec(id="fg", type="footage", name="人物", time_range=[0, 1]))
res4 = validate_composition_tree(t4)
check("footage 缺 path 检出", any("path" in e for e in res4["errors"]))

# 警告：超出合成时长
t5 = build_template("amv")
t5.layers[0].time_range = [0, 99.0]
res5 = validate_composition_tree(t5)
check("超出时长警告（不阻断）", res5["ok"] and any("超出" in w for w in res5["warnings"]))

# 节拍事件校验
t6 = build_template("amv")
t6.beat_events.append({"time": 999.0, "beat_type": "kick"})
res6 = validate_composition_tree(t6)
check("节拍越界检出", any("节拍" in e for e in res6["errors"]))
t6.beat_events = [{"time": 1.0, "beat_type": "kick", "layer_id": "nonexist"}]
res6b = validate_composition_tree(t6)
check("节拍引用不存在的图层检出", any("不存在的图层" in e for e in res6b["errors"]))

print("=" * 60)
print("3. 模板内容合理性")
print("=" * 60)
amv = trees["amv"]
text_layers = [l for l in amv.layers if l.type == "text"]
check("amv 含文字层", len(text_layers) >= 1)
check("amv 含粒子层", any(l.type == "particle" for l in amv.layers))
check("amv 文字层有入场动画", all("entrance" in l.animations for l in text_layers))
cyber = trees["cyberpunk"]
check("cyberpunk 含调整层", any(l.type == "adjustment" for l in cyber.layers))
check("cyberpunk 效果引用有效 kind", all(e.kind in ("match", "combo") for l in cyber.layers for e in l.effects))
amb = trees["ambient"]
loop_layers = [l for l in amb.layers if "loop" in l.animations]
check("ambient 含循环动画层", len(loop_layers) >= 1)

print(f"\n总计: {passed}/{passed + failed} 通过, {failed} 失败")
if __name__ == "__main__":
    sys.exit(1 if failed else 0)
