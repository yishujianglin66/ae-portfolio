// ============================================================================
// unit-validator.test.ts
// Validator 单元测试 - 覆盖所有验证函数的边界条件
// ============================================================================

import { validate } from "../src/validator.js";
import type { CompilerInput, Operation } from "../src/types.js";

// 简易断言
function assert(condition: boolean, message: string) {
  if (!condition) throw new Error(`FAIL: ${message}`);
}

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e: any) {
    failed++;
    console.log(`  ✗ ${name}: ${e.message}`);
  }
}

// ============================================================================
// 1. 顶层结构验证
// ============================================================================
console.log("\n=== 顶层结构验证 ===");

test("null 输入返回 E001", () => {
  const r = validate(null as any);
  assert(!r.valid, "应无效");
  assert(r.errors.some(e => e.code === "E001"), "应包含 E001");
});

test("非对象输入返回 E001", () => {
  const r = validate("string" as any);
  assert(!r.valid, "应无效");
  assert(r.errors.some(e => e.code === "E001"), "应包含 E001");
});

test("operations 非数组返回 E002", () => {
  const r = validate({ operations: "not-array" } as any);
  assert(!r.valid, "应无效");
  assert(r.errors.some(e => e.code === "E002"), "应包含 E002");
});

test("空 operations 数组有效", () => {
  const r = validate({ operations: [] });
  assert(r.valid, "应有效");
  assert(r.errors.length === 0, "不应有错误");
});

// ============================================================================
// 2. 操作验证
// ============================================================================
console.log("\n=== 操作验证 ===");

test("无效 op 类型返回 E004", () => {
  const r = validate({ operations: [{ op: "invalidOp" }] } as any);
  assert(!r.valid, "应无效");
  assert(r.errors.some(e => e.code === "E004"), "应包含 E004");
});

test("非对象操作返回 E003", () => {
  const r = validate({ operations: [null] } as any);
  assert(!r.valid, "应无效");
  assert(r.errors.some(e => e.code === "E003"), "应包含 E003");
});

// ============================================================================
// 3. createComp 验证
// ============================================================================
console.log("\n=== createComp 验证 ===");

test("createComp 缺少 name 返回 E100", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1" }] } as any);
  assert(r.errors.some(e => e.code === "E100"), "应包含 E100");
});

test("createComp width 超范围返回 E101", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", width: 0 }] } as any);
  assert(r.errors.some(e => e.code === "E101"), "width=0 应 E101");
});

test("createComp width > 32768 返回 E101", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", width: 40000 }] } as any);
  assert(r.errors.some(e => e.code === "E101"), "width=40000 应 E101");
});

test("createComp height 超范围返回 E102", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", height: -1 }] } as any);
  assert(r.errors.some(e => e.code === "E102"), "height=-1 应 E102");
});

test("createComp frameRate 超范围返回 E103", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", frameRate: 200 }] } as any);
  assert(r.errors.some(e => e.code === "E103"), "frameRate=200 应 E103");
});

test("createComp duration < 0.1 返回 E104", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", duration: 0 }] } as any);
  assert(r.errors.some(e => e.code === "E104"), "duration=0 应 E104");
});

test("createComp bgColor 无效返回 E105", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", bgColor: [2, 0, 0] }] } as any);
  assert(r.errors.some(e => e.code === "E105"), "bgColor超出范围应 E105");
});

test("createComp bgColor 4元素返回 E105", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", bgColor: [1, 0, 0, 1] }] } as any);
  assert(r.errors.some(e => e.code === "E105"), "bgColor 4元素应 E105");
});

test("createComp 合法参数有效", () => {
  const r = validate({ operations: [{ op: "createComp", ref: "comp1", name: "Test", width: 1920, height: 1080, frameRate: 30, duration: 10, bgColor: [0, 0, 0] }] });
  assert(r.valid, "合法 createComp 应有效");
});

// ============================================================================
// 4. addLayer 验证
// ============================================================================
console.log("\n=== addLayer 验证 ===");

test("addLayer 缺少 compRef 返回 E200", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", layerType: "text", text: "Hello" }
  ] } as any);
  assert(r.errors.some(e => e.code === "E200"), "应包含 E200");
});

test("addLayer 无效 layerType 返回 E201", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "invalid" }
  ] } as any);
  assert(r.errors.some(e => e.code === "E201"), "应包含 E201");
});

test("addLayer text 类型缺少 text 返回 E202", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text" }
  ] });
  assert(r.errors.some(e => e.code === "E202"), "应包含 E202");
});

test("addLayer solid 类型缺少 color 返回 E203", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "solid" }
  ] });
  assert(r.errors.some(e => e.code === "E203"), "应包含 E203");
});

test("addLayer footage 类型缺少 filePath 返回 E204", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "footage" }
  ] });
  assert(r.errors.some(e => e.code === "E204"), "应包含 E204");
});

test("addLayer opacity 超范围返回 E206", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi", opacity: 150 }
  ] });
  assert(r.errors.some(e => e.code === "E206"), "opacity=150 应 E206");
});

test("addLayer fillColor 无效返回 E205", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi", fillColor: [2, 0, 0] }
  ] });
  assert(r.errors.some(e => e.code === "E205"), "fillColor 超范围应 E205");
});

// ============================================================================
// 5. addEffect 验证
// ============================================================================
console.log("\n=== addEffect 验证 ===");

test("addEffect 缺少 layerRef 返回 E300", () => {
  const r = validate({ operations: [{ op: "addEffect", ref: "fx1", matchName: "ADBE Gaussian Blur 2" }] } as any);
  assert(r.errors.some(e => e.code === "E300"), "应包含 E300");
});

test("addEffect 缺少 matchName 返回 E301", () => {
  const r = validate({ operations: [{ op: "addEffect", ref: "fx1", layerRef: "layer1" }] } as any);
  assert(r.errors.some(e => e.code === "E301"), "应包含 E301");
});

test("addEffect settings 非对象返回 E302", () => {
  const r = validate({ operations: [{ op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2", settings: "invalid" }] } as any);
  assert(r.errors.some(e => e.code === "E302"), "应包含 E302");
});

// ============================================================================
// 6. setProperty 验证
// ============================================================================
console.log("\n=== setProperty 验证 ===");

test("setProperty 缺少 layerRef 返回 E400", () => {
  const r = validate({ operations: [{ op: "setProperty", propertyPath: "Position", value: [0, 0] }] } as any);
  assert(r.errors.some(e => e.code === "E400"), "应包含 E400");
});

test("setProperty 缺少 propertyPath 返回 E401", () => {
  const r = validate({ operations: [{ op: "setProperty", layerRef: "layer1", value: [0, 0] }] } as any);
  assert(r.errors.some(e => e.code === "E401"), "应包含 E401");
});

test("setProperty 缺少 value 返回 E402", () => {
  const r = validate({ operations: [{ op: "setProperty", layerRef: "layer1", propertyPath: "Position" }] } as any);
  assert(r.errors.some(e => e.code === "E402"), "应包含 E402");
});

// ============================================================================
// 7. setKeyframe 验证
// ============================================================================
console.log("\n=== setKeyframe 验证 ===");

test("setKeyframe 空 keyframes 返回 E502", () => {
  const r = validate({ operations: [{ op: "setKeyframe", layerRef: "layer1", propertyPath: "Position", keyframes: [] }] });
  assert(r.errors.some(e => e.code === "E502"), "应包含 E502");
});

test("setKeyframe keyframe time 为负返回 E503", () => {
  const r = validate({ operations: [{ op: "setKeyframe", layerRef: "layer1", propertyPath: "Position", keyframes: [{ time: -1, value: 0 }] }] });
  assert(r.errors.some(e => e.code === "E503"), "应包含 E503");
});

test("setKeyframe keyframe 缺少 value 返回 E504", () => {
  const r = validate({ operations: [{ op: "setKeyframe", layerRef: "layer1", propertyPath: "Position", keyframes: [{ time: 0 }] }] } as any);
  assert(r.errors.some(e => e.code === "E504"), "应包含 E504");
});

test("setKeyframe 无效 easing.type 返回 E505", () => {
  const r = validate({ operations: [{ op: "setKeyframe", layerRef: "layer1", propertyPath: "Position", keyframes: [{ time: 0, value: 0, easing: { type: "bounce" } }] }] } as any);
  assert(r.errors.some(e => e.code === "E505"), "应包含 E505");
});

test("setKeyframe 非单调时间返回 E506", () => {
  const r = validate({ operations: [{ op: "setKeyframe", layerRef: "layer1", propertyPath: "Position", keyframes: [{ time: 2, value: 0 }, { time: 1, value: 100 }] }] });
  assert(r.errors.some(e => e.code === "E506"), "应包含 E506");
});

test("setKeyframe 合法关键帧有效", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
    { op: "setKeyframe", ref: "kf1", layerRef: "layer1", propertyPath: "Position", keyframes: [{ time: 0, value: [0, 0] }, { time: 1, value: [100, 100] }] }
  ] });
  assert(r.valid, "合法 setKeyframe 应有效");
});

// ============================================================================
// 8. setExpression 验证
// ============================================================================
console.log("\n=== setExpression 验证 ===");

test("setExpression 缺少 expression 返回 E602", () => {
  const r = validate({ operations: [{ op: "setExpression", layerRef: "layer1", propertyPath: "Position" }] } as any);
  assert(r.errors.some(e => e.code === "E602"), "应包含 E602");
});

test("setExpression 括号不平衡返回 E603", () => {
  const r = validate({ operations: [{ op: "setExpression", layerRef: "layer1", propertyPath: "Position", expression: "transform.position(" }] });
  assert(r.errors.some(e => e.code === "E603"), "应包含 E603");
});

test("setExpression 合法表达式有效", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
    { op: "setExpression", layerRef: "layer1", propertyPath: "Position", expression: "transform.position;" }
  ] });
  assert(r.valid, "合法表达式应有效");
});

// ============================================================================
// 9. addMask 验证
// ============================================================================
console.log("\n=== addMask 验证 ===");

test("addMask vertices 少于3个返回 E701", () => {
  const r = validate({ operations: [{ op: "addMask", layerRef: "layer1", vertices: [[0, 0], [1, 1]] }] });
  assert(r.errors.some(e => e.code === "E701"), "应包含 E701");
});

test("addMask 无效 mode 返回 E703", () => {
  const r = validate({ operations: [{ op: "addMask", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]], mode: "invalid" }] } as any);
  assert(r.errors.some(e => e.code === "E703"), "应包含 E703");
});

test("addMask 顶点坐标非数字返回 E702", () => {
  const r = validate({ operations: [{ op: "addMask", layerRef: "layer1", vertices: [[0, 0], ["x", 0], [50, 100]] }] } as any);
  assert(r.errors.some(e => e.code === "E702"), "应包含 E702");
});

// ============================================================================
// 10. setBlendMode 验证
// ============================================================================
console.log("\n=== setBlendMode 验证 ===");

test("setBlendMode 无效 blendMode 返回 E801", () => {
  const r = validate({ operations: [{ op: "setBlendMode", layerRef: "layer1", blendMode: "invalidMode" }] } as any);
  assert(r.errors.some(e => e.code === "E801"), "应包含 E801");
});

test("setBlendMode 合法 blendMode 有效", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
    { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" }
  ] });
  assert(r.valid, "screen 应有效");
});

// ============================================================================
// 11. setParent 验证
// ============================================================================
console.log("\n=== setParent 验证 ===");

test("setParent layerRef === parentRef 返回 E902", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test" },
    { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "null" },
    { op: "setParent", layerRef: "layer1", parentRef: "layer1" }
  ] });
  assert(r.errors.some(e => e.code === "E902"), "自引用应 E902");
});

// ============================================================================
// 12. setTrackMatte 验证
// ============================================================================
console.log("\n=== setTrackMatte 验证 ===");

test("setTrackMatte 无效 matteType 返回 EA02", () => {
  const r = validate({ operations: [{ op: "setTrackMatte", layerRef: "layer1", matteRef: "layer2", matteType: "invalid" }] } as any);
  assert(r.errors.some(e => e.code === "EA02"), "应包含 EA02");
});

// ============================================================================
// 13. 引用完整性
// ============================================================================
console.log("\n=== 引用完整性 ===");

test("重复 ref 返回 E010", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test1" },
    { op: "createComp", ref: "comp1", name: "Test2" }
  ] });
  assert(r.errors.some(e => e.code === "E010"), "重复 ref 应 E010");
});

test("不存在的 compRef 返回 E021", () => {
  const r = validate({ operations: [
    { op: "addLayer", ref: "layer1", compRef: "nonexistent", layerType: "text", text: "Hi" }
  ] });
  assert(r.errors.some(e => e.code === "E021"), "应包含 E021");
});

test("不存在的 dependsOn 返回 E020", () => {
  const r = validate({ operations: [
    { op: "createComp", ref: "comp1", name: "Test", dependsOn: ["phantom"] }
  ] });
  assert(r.errors.some(e => e.code === "E020"), "应包含 E020");
});

// ============================================================================
// 14. 多操作交互验证
// ============================================================================
console.log("\n=== 多操作交互 ===");

test("完整合法管线有效", () => {
  const r = validate({
    operations: [
      { op: "createComp", ref: "comp1", name: "Test Comp", width: 1920, height: 1080, frameRate: 30, duration: 10 },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hello", opacity: 80 },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2", settings: { Blurriness: 20 } },
      { op: "setKeyframe", ref: "kf1", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0, easing: { type: "linear" } }, { time: 1, value: 100, easing: { type: "ease_out", outInfluence: 33 } }] },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" },
      { op: "addMask", ref: "mask1", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]], mode: "add" },
    ]
  });
  assert(r.valid, "完整管线应有效");
  assert(r.refs.has("comp1"), "refs 应包含 comp1");
  assert(r.refs.has("layer1"), "refs 应包含 layer1");
});

// ============================================================================
// 总结
// ============================================================================
console.log(`\n========================================`);
console.log(` Validator 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
