// ============================================================================
// unit-ir-builder.test.ts
// IR Builder 单元测试 - 中间表示构建与依赖解析
// ============================================================================

import { buildIR } from "../src/ir-builder.js";
import type { CompilerInput, Operation } from "../src/types.js";

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
// 1. 基础构建
// ============================================================================
console.log("\n=== 基础构建 ===");

test("空输入返回空节点和空映射", () => {
  const input: CompilerInput = { operations: [] };
  const r = buildIR(input);
  assert(r.nodes.length === 0, "节点应为空");
  assert(r.refToNodeId.size === 0, "映射应为空");
  assert(r.errors.length === 0, "不应有错误");
});

test("单 createComp 生成正确节点和映射", () => {
  const input: CompilerInput = {
    operations: [{ op: "createComp", ref: "comp1", name: "Test" }],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "应有1个节点");
  assert(r.nodes[0].type === "createComp", "类型应为 createComp");
  assert(r.nodes[0].deps.length === 0, "createComp 不应有依赖");
  assert(r.refToNodeId.has("comp1"), "映射应包含 comp1");
  assert(r.refToNodeId.get("comp1") === r.nodes[0].id, "映射值应为节点 ID");
});

test("无 ref 的操作不加入映射", () => {
  const input: CompilerInput = {
    operations: [{ op: "createComp", name: "NoRef" }],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "应有1个节点");
  assert(r.refToNodeId.size === 0, "无 ref 不应加入映射");
});

// ============================================================================
// 2. 隐式依赖解析
// ============================================================================
console.log("\n=== 隐式依赖解析 ===");

test("addLayer 隐式依赖 createComp", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
    ],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 2, "应有2个节点");

  const compNode = r.nodes[0];
  const layerNode = r.nodes[1];

  assert(layerNode.deps.length === 1, "addLayer 应有1个依赖");
  assert(layerNode.deps[0] === compNode.id, "addLayer 应依赖 createComp");
});

test("addEffect 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2" },
    ],
  };
  const r = buildIR(input);
  const fxNode = r.nodes[2];
  assert(fxNode.deps.length === 1, "addEffect 应有1个依赖");
  assert(fxNode.deps[0] === r.nodes[1].id, "addEffect 应依赖 layer");
});

test("setProperty 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setProperty", layerRef: "layer1", propertyPath: "Position", value: [0, 0] },
    ],
  };
  const r = buildIR(input);
  const propNode = r.nodes[2];
  assert(propNode.deps.length === 1, "setProperty 应有1个依赖");
  assert(propNode.deps[0] === r.nodes[1].id, "应依赖 layer");
});

test("setKeyframe 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setKeyframe", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0 }] },
    ],
  };
  const r = buildIR(input);
  const kfNode = r.nodes[2];
  assert(kfNode.deps.length === 1, "setKeyframe 应有1个依赖");
});

test("setExpression 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setExpression", layerRef: "layer1", propertyPath: "Position", expression: "wiggle(2,50)" },
    ],
  };
  const r = buildIR(input);
  const exprNode = r.nodes[2];
  assert(exprNode.deps.length === 1, "setExpression 应有1个依赖");
});

test("addMask 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addMask", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]] },
    ],
  };
  const r = buildIR(input);
  const maskNode = r.nodes[2];
  assert(maskNode.deps.length === 1, "addMask 应有1个依赖");
});

test("setBlendMode 隐式依赖 addLayer", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" },
    ],
  };
  const r = buildIR(input);
  const blendNode = r.nodes[2];
  assert(blendNode.deps.length === 1, "setBlendMode 应有1个依赖");
});

test("setParent 隐式依赖两个图层", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "null" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setParent", layerRef: "layer2", parentRef: "layer1" },
    ],
  };
  const r = buildIR(input);
  const parentNode = r.nodes[3];
  assert(parentNode.deps.length === 2, "setParent 应依赖两个图层");
  assert(parentNode.deps.includes(r.nodes[1].id), "应依赖 layer1");
  assert(parentNode.deps.includes(r.nodes[2].id), "应依赖 layer2");
});

test("setTrackMatte 隐式依赖两个图层", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "solid", color: [1, 1, 1] },
      { op: "setTrackMatte", layerRef: "layer1", matteRef: "layer2", matteType: "alpha" },
    ],
  };
  const r = buildIR(input);
  const matteNode = r.nodes[3];
  assert(matteNode.deps.length === 2, "setTrackMatte 应依赖两个图层");
  assert(matteNode.deps.includes(r.nodes[1].id), "应依赖 layer1");
  assert(matteNode.deps.includes(r.nodes[2].id), "应依赖 layer2");
});

// ============================================================================
// 3. 显式依赖解析
// ============================================================================
console.log("\n=== 显式依赖解析 ===");

test("dependsOn 建立显式依赖", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "createComp", ref: "comp2", name: "Test2", dependsOn: ["comp1"] },
    ],
  };
  const r = buildIR(input);
  const comp2Node = r.nodes[1];
  assert(comp2Node.deps.length === 1, "应有1个显式依赖");
  assert(comp2Node.deps[0] === r.nodes[0].id, "应依赖 comp1");
});

test("多个显式依赖", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "A" },
      { op: "createComp", ref: "comp2", name: "B" },
      { op: "createComp", ref: "comp3", name: "C", dependsOn: ["comp1", "comp2"] },
    ],
  };
  const r = buildIR(input);
  const comp3Node = r.nodes[2];
  assert(comp3Node.deps.length === 2, "应有2个显式依赖");
  assert(comp3Node.deps.includes(r.nodes[0].id), "应依赖 comp1");
  assert(comp3Node.deps.includes(r.nodes[1].id), "应依赖 comp2");
});

test("显式依赖去重", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi", dependsOn: ["comp1"] },
    ],
  };
  const r = buildIR(input);
  const layerNode = r.nodes[1];
  // compRef 和 dependsOn 都指向 comp1，应去重
  assert(layerNode.deps.length === 1, "重复依赖应去重");
});

// ============================================================================
// 4. 缺失引用处理
// ============================================================================
console.log("\n=== 缺失引用处理 ===");

test("缺失 compRef 不产生崩溃", () => {
  const input: CompilerInput = {
    operations: [
      { op: "addLayer", ref: "layer1", compRef: "nonexistent", layerType: "text", text: "Hi" },
    ],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "仍应生成节点");
  assert(r.nodes[0].deps.length === 0, "缺失引用不应产生依赖");
});

test("缺失 layerRef 不产生崩溃", () => {
  const input: CompilerInput = {
    operations: [
      { op: "addEffect", ref: "fx1", layerRef: "nonexistent", matchName: "ADBE Gaussian Blur 2" },
    ],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "仍应生成节点");
  assert(r.nodes[0].deps.length === 0, "缺失引用不应产生依赖");
});

// ============================================================================
// 5. 复杂场景
// ============================================================================
console.log("\n=== 复杂场景 ===");

test("完整管线依赖正确", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test Comp", width: 1920, height: 1080 },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hello" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2", settings: { Blurriness: 20 } },
      { op: "setKeyframe", ref: "kf1", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0 }] },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" },
    ],
  };
  const r = buildIR(input);
  assert(r.nodes.length === 5, "应有5个节点");

  // 验证 ref 映射
  assert(r.refToNodeId.has("comp1"), "应有 comp1");
  assert(r.refToNodeId.has("layer1"), "应有 layer1");
  assert(r.refToNodeId.has("fx1"), "应有 fx1");
  assert(r.refToNodeId.has("kf1"), "应有 kf1");

  // 验证依赖链
  const compId = r.refToNodeId.get("comp1");
  const layerId = r.refToNodeId.get("layer1");

  assert(r.nodes[1].deps.includes(compId!), "layer1 依赖 comp1");
  assert(r.nodes[2].deps.includes(layerId!), "fx1 依赖 layer1");
  assert(r.nodes[3].deps.includes(layerId!), "kf1 依赖 layer1");
  assert(r.nodes[4].deps.includes(layerId!), "blendMode 依赖 layer1");
});

test("节点 ID 按顺序生成", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "c1", name: "A" },
      { op: "createComp", ref: "c2", name: "B" },
      { op: "createComp", ref: "c3", name: "C" },
    ],
  };
  const r = buildIR(input);
  assert(r.nodes[0].id === "node_000", "第一个 ID 应为 node_000");
  assert(r.nodes[1].id === "node_001", "第二个 ID 应为 node_001");
  assert(r.nodes[2].id === "node_002", "第三个 ID 应为 node_002");
});

test("重复 ref 映射后被覆盖", () => {
  const input: CompilerInput = {
    operations: [
      { op: "createComp", ref: "same", name: "First" },
      { op: "createComp", ref: "same", name: "Second" },
    ],
  };
  const r = buildIR(input);
  // refToNodeId 应映射到第二个节点（后写入覆盖）
  assert(r.refToNodeId.get("same") === r.nodes[1].id, "重复 ref 应指向后者");
});

// ============================================================================
// 总结
// ============================================================================
console.log(`\n========================================`);
console.log(` IR Builder 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
