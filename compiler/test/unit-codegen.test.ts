// ============================================================================
// unit-codegen.test.ts
// Codegen 单元测试 - 代码生成辅助函数和映射逻辑
// ============================================================================

import { generateCode } from "../src/codegen.js";
import { buildIR } from "../src/ir-builder.js";
import { validate } from "../src/validator.js";
import type { CompilerInput } from "../src/types.js";

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
// 1. 基础代码生成
// ============================================================================
console.log("\n=== 基础代码生成 ===");

test("空节点生成有效脚本框架", () => {
  const r = generateCode([]);
  assert(r.script.length > 0, "应生成非空脚本");
  assert(r.script.includes("beginUndoGroup"), "应包含 beginUndoGroup");
  assert(r.script.includes("endUndoGroup"), "应包含 endUndoGroup");
  assert(r.errors.length === 0, "不应有错误");
});

test("生成的脚本包含 IIFE 包裹", () => {
  const r = generateCode([]);
  assert(r.script.trimStart().startsWith("(function()"), "应以 IIFE 开始");
  assert(r.script.trimEnd().endsWith("})();"), "应以 IIFE 结束");
});

// ============================================================================
// 2. createComp 代码生成
// ============================================================================
console.log("\n=== createComp 代码生成 ===");

test("createComp 生成 addComp 调用", () => {
  const input: CompilerInput = {
    operations: [{ op: "createComp", ref: "comp1", name: "Test Comp", width: 1920, height: 1080, frameRate: 30, duration: 10 }]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("addComp"), "应包含 addComp 调用");
  assert(r.script.includes('"Test Comp"'), "应包含合成名称");
  assert(r.variableMap.has("comp1"), "变量映射应包含 comp1");
});

test("createComp 默认参数正确", () => {
  const input: CompilerInput = {
    operations: [{ op: "createComp", ref: "comp1", name: "Default" }]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("1920"), "默认宽度应为 1920");
  assert(r.script.includes("1080"), "默认高度应为 1080");
  assert(r.script.includes("30"), "默认帧率应为 30");
});

test("createComp bgColor 生成正确", () => {
  const input: CompilerInput = {
    operations: [{ op: "createComp", ref: "comp1", name: "Color", bgColor: [1, 0.5, 0] }]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("1, 0.5, 0"), "bgColor 应正确输出");
});

// ============================================================================
// 3. addLayer 代码生成
// ============================================================================
console.log("\n=== addLayer 代码生成 ===");

test("addLayer text 类型生成 addText", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hello" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("addText"), "应包含 addText 调用");
  assert(r.script.includes('"Hello"'), "应包含文本内容");
  assert(r.variableMap.has("layer1"), "变量映射应包含 layer1");
});

test("addLayer solid 类型生成 addSolid", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "solid", color: [1, 0, 0] }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("addSolid"), "应包含 addSolid 调用");
});

test("addLayer footage 类型生成 importFile", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "footage", filePath: "C:/test/video.mp4" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("importFile"), "应包含 importFile");
  assert(r.script.includes("new File"), "应包含 new File");
});

test("addLayer null 类型生成 addNull", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "null" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("addNull"), "应包含 addNull 调用");
});

test("addLayer transform 属性正确生成", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi", position: [100, 200], opacity: 50, rotation: 45 }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("ADBE Position"), "应包含 Position 属性");
  assert(r.script.includes("ADBE Opacity"), "应包含 Opacity 属性");
  assert(r.script.includes("ADBE Rotate Z"), "应包含 Rotate Z 属性");
});

// ============================================================================
// 4. addEffect 代码生成
// ============================================================================
console.log("\n=== addEffect 代码生成 ===");

test("addEffect 生成 Effects.addProperty", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("Effects.addProperty"), "应包含 Effects.addProperty");
  assert(r.script.includes('"ADBE Gaussian Blur 2"'), "应包含 matchName");
});

test("addEffect settings 生成 setValue 调用", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2", settings: { Blurriness: 25 } }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("setValue"), "应包含 setValue");
});

// ============================================================================
// 5. setKeyframe 代码生成
// ============================================================================
console.log("\n=== setKeyframe 代码生成 ===");

test("setKeyframe 生成 setValueAtTime", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setKeyframe", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0 }, { time: 1, value: 100 }] }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("setValueAtTime"), "应包含 setValueAtTime");
});

test("setKeyframe 缓动生成 setInterpolationTypeAtKey", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setKeyframe", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0, easing: { type: "bezier" } }] }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("setInterpolationTypeAtKey"), "应包含缓动设置");
  assert(r.script.includes("setTemporalEaseAtKey"), "应包含时间缓动设置");
});

// ============================================================================
// 6. setExpression 代码生成
// ============================================================================
console.log("\n=== setExpression 代码生成 ===");

test("setExpression 生成 expression 赋值", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setExpression", layerRef: "layer1", propertyPath: "Position", expression: "wiggle(2, 50);" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes(".expression ="), "应包含 expression 赋值");
});

// ============================================================================
// 7. addMask 代码生成
// ============================================================================
console.log("\n=== addMask 代码生成 ===");

test("addMask 生成 Shape 和 addShape", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addMask", ref: "mask1", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]] }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("new Shape()"), "应包含 new Shape()");
  assert(r.script.includes("addShape"), "应包含 addShape");
  assert(r.script.includes("MaskMode.ADD"), "默认模式应为 ADD");
});

test("addMask subtract 模式生成 MaskMode.SUBTRACT", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addMask", ref: "mask1", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]], mode: "subtract" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("MaskMode.SUBTRACT"), "应为 SUBTRACT 模式");
});

// ============================================================================
// 8. setBlendMode 代码生成
// ============================================================================
console.log("\n=== setBlendMode 代码生成 ===");

test("setBlendMode 生成 BlendingMode 常量", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("BlendingMode.SCREEN"), "应生成 SCREEN 常量");
});

test("setBlendMode 复合名称正确映射", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "colorBurn" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("BlendingMode.COLOR_BURN"), "应生成 COLOR_BURN 常量");
});

// ============================================================================
// 9. setParent 代码生成
// ============================================================================
console.log("\n=== setParent 代码生成 ===");

test("setParent 生成 parent 赋值", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "null" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setParent", layerRef: "layer2", parentRef: "layer1" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes(".parent ="), "应包含 parent 赋值");
});

// ============================================================================
// 10. setTrackMatte 代码生成
// ============================================================================
console.log("\n=== setTrackMatte 代码生成 ===");

test("setTrackMatte 生成 trackMatteType 赋值", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "solid", color: [1, 1, 1] },
      { op: "setTrackMatte", layerRef: "layer1", matteRef: "layer2", matteType: "alpha" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.script.includes("trackMatteType"), "应包含 trackMatteType");
  assert(r.script.includes("TrackMatteType.ALPHA"), "应生成 ALPHA 常量");
});

// ============================================================================
// 11. 变量映射
// ============================================================================
console.log("\n=== 变量映射 ===");

test("variableMap 正确记录所有 ref", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2" }
    ]
  };
  const ir = buildIR(input);
  const r = generateCode(ir.nodes);
  assert(r.variableMap.has("comp1"), "应包含 comp1");
  assert(r.variableMap.has("layer1"), "应包含 layer1");
  assert(r.variableMap.has("fx1"), "应包含 fx1");
  assert(r.variableMap.get("comp1")?.startsWith("comp_"), "comp ref 应映射到 comp_ 变量");
  assert(r.variableMap.get("layer1")?.startsWith("layer_"), "layer ref 应映射到 layer_ 变量");
});

// ============================================================================
console.log(`\n========================================`);
console.log(` Codegen 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
