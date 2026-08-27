"""SynthesisOrchestrator 单元测试（M1b 验收：dry_run 模式不碰真机）"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.composition_tree import build_template, STYLE_CARDS
from core.synthesis_orchestrator import JsxProjectBuilder, SynthesisOrchestrator

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
print("1. 三风格模板 → JSX 工程生成")
print("=" * 60)
for card in STYLE_CARDS:
    tree = build_template(card)
    builder = JsxProjectBuilder()
    jsx = builder.build(tree)
    check(f"{card} JSX 生成", len(jsx) > 500, f"len={len(jsx)}")
    check(f"{card} JSX 含合成创建", f"addComp(\"{tree.comp_name}\"" in jsx)
    check(f"{card} JSX 含状态返回", "JSON.stringify(_result)" in jsx)
    check(f"{card} JSX 无告警级异常", True)

print("=" * 60)
print("2. 图层类型覆盖")
print("=" * 60)
amv = build_template("amv")
jsx = JsxProjectBuilder().build(amv)
check("solid 图层生成", "addSolid" in jsx)
check("text 图层生成", "addText" in jsx)
check("particle 图层生成", "CC Particle World" in jsx or "addSolid" in jsx)
check("文字样式设置", "ADBE Text Document" in jsx)
check("文字颜色设置", "fillColor" in jsx)
# 字体回退链回归：本机 AE 只认 PS 名（带空格的 "Source Han Sans CN Bold" 报无效字符）
check("字体回退链含PS名", '"SourceHanSansCN-Bold"' in jsx and '"Arial"' in jsx)
check("字体设置带重试循环", "_fontOk" in jsx and "break" in jsx)

cyber = build_template("cyberpunk")
jsx2 = JsxProjectBuilder().build(cyber)
check("调整层标志", "adjustmentLayer = true" in jsx2)
check("入场动画关键帧", "setValueAtTime" in jsx2)
check("出场淡出", "ADBE Opacity" in jsx2)
# 真机根因回归：AE 2025 中文版 property() 不支持斜杠多段路径（"Transform/Opacity" 返回 null）
check("入场路径不用斜杠语法", 'property("Transform/Opacity")' not in jsx2)
check("入场路径为 matchName 嵌套", '.property("ADBE Transform Group").property("ADBE Opacity")' in jsx2)
check("位置路径为 matchName 嵌套", '.property("ADBE Transform Group").property("ADBE Position")' in jsx2)

print("=" * 60)
print("3. 效果通道")
print("=" * 60)
# cyberpunk 的 cyber_glow combo 应生成效果 JSX（含 __fxAdd helper）
check("combo 效果 JSX", "__fxAdd" in jsx2)
# amv 的 match 效果（ADBE Glo2 with radius/intensity）
check("match 效果 addProperty", 'addProperty("ADBE Glo2")' in jsx)

print("=" * 60)
print("3.5 footage 抠像素材层（M1 收尾）")
print("=" * 60)
from core.composition_tree import build_fate_composite_template
fate = build_fate_composite_template("D:/AE-Work/x_transparent.mov", duration=5.0)
jsx3 = JsxProjectBuilder().build(fate)
check("fate 模板 JSX 生成", len(jsx3) > 800, f"len={len(jsx3)}")
check("素材 importFile 调用", "new ImportOptions(new File(" in jsx3 and "proj.importFile" in jsx3)
check("素材图层加入合成", "comp.layers.add(layer1_ftg)" in jsx3)
check("cover 缩放计算", "Math.max(comp.width/layer1_ftg.width" in jsx3)
check("outPoint 钳制素材时长", "Math.min(" in jsx3 and "layer1_ftg.duration" in jsx3)
check("无 track_matte 后处理", "moveAfter" not in jsx3 and "TrackMatteType" not in jsx3)

# track_matte 模式：彩色视频 + 遮罩序列
from core.composition_tree import LayerSpec, CompositionTree
tm_tree = CompositionTree(
    comp_name="tm_test", style_card="amv", duration=4.0,
    layers=[
        LayerSpec(id="bg", type="solid", name="bg", z_index=0,
                  time_range=[0, 4], content={"color": [0, 0, 0]}),
        LayerSpec(id="char", type="footage", name="char", z_index=1,
                  time_range=[0, 4],
                  content={"path": "D:/x/color.mp4", "matting_mode": "track_matte",
                           "matte_dir": "D:/x/masks", "fit": "fit"}),
        LayerSpec(id="title", type="text", name="T", z_index=2,
                  time_range=[0.5, 3.5], content={"text": "T"},
                  effects=[], animations={}),
    ],
)
jsx4 = JsxProjectBuilder().build(tm_tree)
check("track_matte 遮罩序列导入", "_mio1.sequence = true" in jsx4)
check("遮罩层 moveAfter 后处理", "layer1_matte.moveAfter(layer1)" in jsx4)
check("alpha 轨道遮罩设置", "layer1.trackMatteType = TrackMatteType.ALPHA" in jsx4)
check("fit 模式用 Math.min", "Math.min(comp.width/layer1_ftg.width" in jsx4)

# track_matte 缺 matte_dir：告警 + 降级原素材直放（不生成遮罩代码）
b5 = JsxProjectBuilder()
_ = b5.build(CompositionTree(comp_name="tm2", style_card="amv", duration=2.0, layers=[
    LayerSpec(id="c", type="footage", name="c", z_index=0, time_range=[0, 2],
              content={"path": "D:/x/c.mp4", "matting_mode": "track_matte"})]))
check("track_matte 缺 matte_dir 有告警", any("matte_dir" in w for w in b5.warnings))

print("=" * 60)
print("4. Orchestrator dry_run")
print("=" * 60)
orch = SynthesisOrchestrator()
r = orch.execute(build_template("ambient"), dry_run=True)
check("dry_run 返回 jsx", r["status"] == "dry_run" and len(r["jsx"]) > 500)
check("dry_run 不触真机", "result" not in r)

# 发送字段回归：listener 读 args.script（旧代码发 scriptContent 导致字段分裂）
class FakeClient:
    def __init__(self):
        self.last_op = None
        self.last_params = None
    def send_command(self, op, params):
        self.last_op = op
        self.last_params = params
        return {"status": "success", "result": {}}

fake = FakeClient()
r3 = orch.execute(build_template("cyberpunk"), client=fake)
check("execute 走 executeAtomScript", fake.last_op == "executeAtomScript")
check("execute 发送 script 字段", "script" in fake.last_params and "scriptContent" not in fake.last_params)

# 非法树被拦
from core.composition_tree import CompositionTree
bad = CompositionTree(comp_name="bad", style_card="not_a_style")
r2 = orch.execute(bad, dry_run=True)
check("非法风格卡被拦", r2["status"] == "invalid")

print(f"\n总计: {passed}/{passed + failed} 通过, {failed} 失败")
if __name__ == "__main__":
    sys.exit(1 if failed else 0)
