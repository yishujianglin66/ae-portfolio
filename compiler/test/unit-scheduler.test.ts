// ============================================================================
// unit-scheduler.test.ts
// Scheduler 单元测试 - 拓扑排序、循环检测、优先级排序
// ============================================================================

import { schedule } from "../src/scheduler.js";
import type { IRNode, Operation } from "../src/types.js";

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

function makeNode(id: string, type: IRNode["type"], deps: string[] = [], source?: Operation): IRNode {
  return { id, type, deps, source: source || { op: type as any, ref: id } as any };
}

// ============================================================================
// 1. 基础拓扑排序
// ============================================================================
console.log("\n=== 基础拓扑排序 ===");

test("空输入返回空数组", () => {
  const r = schedule([]);
  assert(r.sorted.length === 0, "应返回空数组");
  assert(r.errors.length === 0, "不应有错误");
});

test("单节点直接通过", () => {
  const nodes = [makeNode("n0", "createComp")];
  const r = schedule(nodes);
  assert(r.sorted.length === 1, "应返回1个节点");
  assert(r.sorted[0].id === "n0", "节点 ID 应为 n0");
});

test("无依赖节点按优先级排序", () => {
  const nodes = [
    makeNode("n0", "addEffect"),
    makeNode("n1", "createComp"),
    makeNode("n2", "addLayer"),
  ];
  const r = schedule(nodes);
  const types = r.sorted.map(n => n.type);
  assert(types[0] === "createComp", "createComp 应排最前");
  assert(types[1] === "addLayer", "addLayer 次之");
  assert(types[2] === "addEffect", "addEffect 再次");
});

// ============================================================================
// 2. 依赖关系排序
// ============================================================================
console.log("\n=== 依赖关系排序 ===");

test("被依赖的节点排在前面", () => {
  const nodes = [
    makeNode("n0", "addLayer", ["n1"]),
    makeNode("n1", "createComp"),
  ];
  const r = schedule(nodes);
  const ids = r.sorted.map(n => n.id);
  assert(ids.indexOf("n1") < ids.indexOf("n0"), "createComp 应在 addLayer 前");
});

test("链式依赖正确排序 A→B→C", () => {
  const nodes = [
    makeNode("n0", "setKeyframe", ["n1"]),
    makeNode("n1", "addLayer", ["n2"]),
    makeNode("n2", "createComp"),
  ];
  const r = schedule(nodes);
  const ids = r.sorted.map(n => n.id);
  assert(ids[0] === "n2" && ids[1] === "n1" && ids[2] === "n0", "应为 n2→n1→n0");
});

test("菱形依赖正确排序", () => {
  //   n2 (addEffect)
  //  / \
  // n0  n1 (addLayer)
  //  \ /
  //   n3 (createComp)
  const nodes = [
    makeNode("n0", "addLayer", ["n3"]),
    makeNode("n1", "addLayer", ["n3"]),
    makeNode("n2", "addEffect", ["n0", "n1"]),
    makeNode("n3", "createComp"),
  ];
  const r = schedule(nodes);
  const ids = r.sorted.map(n => n.id);
  assert(ids.indexOf("n3") < ids.indexOf("n0"), "createComp 在 addLayer 前");
  assert(ids.indexOf("n3") < ids.indexOf("n1"), "createComp 在 addLayer 前");
  assert(ids.indexOf("n0") < ids.indexOf("n2"), "addLayer 在 addEffect 前");
  assert(ids.indexOf("n1") < ids.indexOf("n2"), "addLayer 在 addEffect 前");
});

// ============================================================================
// 3. 循环依赖检测
// ============================================================================
console.log("\n=== 循环依赖检测 ===");

test("循环依赖产生 S001 错误", () => {
  const nodes = [
    makeNode("n0", "addLayer", ["n1"]),
    makeNode("n1", "addEffect", ["n0"]),
  ];
  const r = schedule(nodes);
  assert(r.errors.some(e => e.code === "S001"), "应检测到循环依赖");
});

test("自依赖产生 S001 错误", () => {
  const nodes = [makeNode("n0", "addLayer", ["n0"])];
  const r = schedule(nodes);
  assert(r.errors.some(e => e.code === "S001"), "应检测到自依赖");
});

test("循环依赖时仍返回所有节点", () => {
  const nodes = [
    makeNode("n0", "addLayer", ["n1"]),
    makeNode("n1", "addEffect", ["n0"]),
  ];
  const r = schedule(nodes);
  assert(r.sorted.length === 2, "应返回全部2个节点");
});

// ============================================================================
// 4. 优先级排序细节
// ============================================================================
console.log("\n=== 优先级排序细节 ===");

test("相同优先级节点保持稳定", () => {
  const nodes = [
    makeNode("n0", "addLayer"),
    makeNode("n1", "addLayer"),
    makeNode("n2", "addLayer"),
  ];
  const r = schedule(nodes);
  assert(r.sorted.length === 3, "应返回3个节点");
  r.sorted.forEach(n => assert(n.type === "addLayer", "类型应为 addLayer"));
});

test("完整操作类型优先级顺序", () => {
  const nodes = [
    makeNode("n0", "setTrackMatte"),
    makeNode("n1", "setParent"),
    makeNode("n2", "setBlendMode"),
    makeNode("n3", "addMask"),
    makeNode("n4", "setExpression"),
    makeNode("n5", "setKeyframe"),
    makeNode("n6", "setProperty"),
    makeNode("n7", "addEffect"),
    makeNode("n8", "addLayer"),
    makeNode("n9", "createComp"),
  ];
  const r = schedule(nodes);
  const types = r.sorted.map(n => n.type);
  const expected = ["createComp", "addLayer", "addEffect", "setProperty", "setKeyframe", "setExpression", "addMask", "setBlendMode", "setParent", "setTrackMatte"];
  assert(JSON.stringify(types) === JSON.stringify(expected), `顺序应为 ${expected.join("→")}`);
});

// ============================================================================
// 5. 悬空依赖处理
// ============================================================================
console.log("\n=== 悬空依赖处理 ===");

test("依赖不存在的节点被忽略", () => {
  const nodes = [
    makeNode("n0", "addLayer", ["nonexistent"]),
  ];
  const r = schedule(nodes);
  assert(r.sorted.length === 1, "应返回1个节点");
  assert(r.errors.length === 0, "悬空依赖不产生错误");
});

// ============================================================================
console.log(`\n========================================`);
console.log(` Scheduler 单元测试: ${passed} 通过 / ${failed} 失败`);
console.log(`========================================`);

if (failed > 0) process.exit(1);
