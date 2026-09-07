// src/ir-builder.ts
function buildIR(input) {
  const nodes = [];
  const refToNodeId = /* @__PURE__ */ new Map();
  const errors = [];
  let counter = 0;
  for (const op of input.operations) {
    const nodeId = `node_${counter.toString(36).padStart(3, "0")}`;
    counter++;
    if (op.ref) {
      refToNodeId.set(op.ref, nodeId);
    }
  }
  counter = 0;
  for (const op of input.operations) {
    const nodeId = `node_${counter.toString(36).padStart(3, "0")}`;
    counter++;
    const deps = resolveDependencies(op, refToNodeId);
    nodes.push({
      id: nodeId,
      type: op.op,
      deps,
      source: op
    });
  }
  return { nodes, refToNodeId, errors };
}
function resolveDependencies(op, refToNodeId) {
  const deps = [];
  if (op.dependsOn) {
    for (const dep of op.dependsOn) {
      const depId = refToNodeId.get(dep);
      if (depId && !deps.includes(depId)) {
        deps.push(depId);
      }
    }
  }
  switch (op.op) {
    case "addLayer": {
      const layerOp = op;
      const compId = refToNodeId.get(layerOp.compRef);
      if (compId && !deps.includes(compId)) deps.push(compId);
      break;
    }
    case "addEffect": {
      const effectOp = op;
      const layerId = refToNodeId.get(effectOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setProperty": {
      const setPropOp = op;
      const layerId = refToNodeId.get(setPropOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setKeyframe": {
      const kfOp = op;
      const layerId = refToNodeId.get(kfOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setExpression": {
      const exprOp = op;
      const layerId = refToNodeId.get(exprOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "addMask": {
      const maskOp = op;
      const layerId = refToNodeId.get(maskOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setBlendMode": {
      const blendOp = op;
      const layerId = refToNodeId.get(blendOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setParent": {
      const parentOp = op;
      const layerId = refToNodeId.get(parentOp.layerRef);
      const parentId = refToNodeId.get(parentOp.parentRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      if (parentId && !deps.includes(parentId)) deps.push(parentId);
      break;
    }
    case "setTrackMatte": {
      const matteOp = op;
      const layerId = refToNodeId.get(matteOp.layerRef);
      const matteLayerId = refToNodeId.get(matteOp.matteRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      if (matteLayerId && !deps.includes(matteLayerId)) deps.push(matteLayerId);
      break;
    }
  }
  return deps;
}

// test/unit-ir-builder.test.ts
function assert(condition, message) {
  if (!condition) throw new Error(`FAIL: ${message}`);
}
var passed = 0;
var failed = 0;
function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  \u2713 ${name}`);
  } catch (e) {
    failed++;
    console.log(`  \u2717 ${name}: ${e.message}`);
  }
}
console.log("\n=== \u57FA\u7840\u6784\u5EFA ===");
test("\u7A7A\u8F93\u5165\u8FD4\u56DE\u7A7A\u8282\u70B9\u548C\u7A7A\u6620\u5C04", () => {
  const input = { operations: [] };
  const r = buildIR(input);
  assert(r.nodes.length === 0, "\u8282\u70B9\u5E94\u4E3A\u7A7A");
  assert(r.refToNodeId.size === 0, "\u6620\u5C04\u5E94\u4E3A\u7A7A");
  assert(r.errors.length === 0, "\u4E0D\u5E94\u6709\u9519\u8BEF");
});
test("\u5355 createComp \u751F\u6210\u6B63\u786E\u8282\u70B9\u548C\u6620\u5C04", () => {
  const input = {
    operations: [{ op: "createComp", ref: "comp1", name: "Test" }]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "\u5E94\u67091\u4E2A\u8282\u70B9");
  assert(r.nodes[0].type === "createComp", "\u7C7B\u578B\u5E94\u4E3A createComp");
  assert(r.nodes[0].deps.length === 0, "createComp \u4E0D\u5E94\u6709\u4F9D\u8D56");
  assert(r.refToNodeId.has("comp1"), "\u6620\u5C04\u5E94\u5305\u542B comp1");
  assert(r.refToNodeId.get("comp1") === r.nodes[0].id, "\u6620\u5C04\u503C\u5E94\u4E3A\u8282\u70B9 ID");
});
test("\u65E0 ref \u7684\u64CD\u4F5C\u4E0D\u52A0\u5165\u6620\u5C04", () => {
  const input = {
    operations: [{ op: "createComp", name: "NoRef" }]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "\u5E94\u67091\u4E2A\u8282\u70B9");
  assert(r.refToNodeId.size === 0, "\u65E0 ref \u4E0D\u5E94\u52A0\u5165\u6620\u5C04");
});
console.log("\n=== \u9690\u5F0F\u4F9D\u8D56\u89E3\u6790 ===");
test("addLayer \u9690\u5F0F\u4F9D\u8D56 createComp", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" }
    ]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 2, "\u5E94\u67092\u4E2A\u8282\u70B9");
  const compNode = r.nodes[0];
  const layerNode = r.nodes[1];
  assert(layerNode.deps.length === 1, "addLayer \u5E94\u67091\u4E2A\u4F9D\u8D56");
  assert(layerNode.deps[0] === compNode.id, "addLayer \u5E94\u4F9D\u8D56 createComp");
});
test("addEffect \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2" }
    ]
  };
  const r = buildIR(input);
  const fxNode = r.nodes[2];
  assert(fxNode.deps.length === 1, "addEffect \u5E94\u67091\u4E2A\u4F9D\u8D56");
  assert(fxNode.deps[0] === r.nodes[1].id, "addEffect \u5E94\u4F9D\u8D56 layer");
});
test("setProperty \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setProperty", layerRef: "layer1", propertyPath: "Position", value: [0, 0] }
    ]
  };
  const r = buildIR(input);
  const propNode = r.nodes[2];
  assert(propNode.deps.length === 1, "setProperty \u5E94\u67091\u4E2A\u4F9D\u8D56");
  assert(propNode.deps[0] === r.nodes[1].id, "\u5E94\u4F9D\u8D56 layer");
});
test("setKeyframe \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setKeyframe", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0 }] }
    ]
  };
  const r = buildIR(input);
  const kfNode = r.nodes[2];
  assert(kfNode.deps.length === 1, "setKeyframe \u5E94\u67091\u4E2A\u4F9D\u8D56");
});
test("setExpression \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setExpression", layerRef: "layer1", propertyPath: "Position", expression: "wiggle(2,50)" }
    ]
  };
  const r = buildIR(input);
  const exprNode = r.nodes[2];
  assert(exprNode.deps.length === 1, "setExpression \u5E94\u67091\u4E2A\u4F9D\u8D56");
});
test("addMask \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addMask", layerRef: "layer1", vertices: [[0, 0], [100, 0], [50, 100]] }
    ]
  };
  const r = buildIR(input);
  const maskNode = r.nodes[2];
  assert(maskNode.deps.length === 1, "addMask \u5E94\u67091\u4E2A\u4F9D\u8D56");
});
test("setBlendMode \u9690\u5F0F\u4F9D\u8D56 addLayer", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" }
    ]
  };
  const r = buildIR(input);
  const blendNode = r.nodes[2];
  assert(blendNode.deps.length === 1, "setBlendMode \u5E94\u67091\u4E2A\u4F9D\u8D56");
});
test("setParent \u9690\u5F0F\u4F9D\u8D56\u4E24\u4E2A\u56FE\u5C42", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "null" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "setParent", layerRef: "layer2", parentRef: "layer1" }
    ]
  };
  const r = buildIR(input);
  const parentNode = r.nodes[3];
  assert(parentNode.deps.length === 2, "setParent \u5E94\u4F9D\u8D56\u4E24\u4E2A\u56FE\u5C42");
  assert(parentNode.deps.includes(r.nodes[1].id), "\u5E94\u4F9D\u8D56 layer1");
  assert(parentNode.deps.includes(r.nodes[2].id), "\u5E94\u4F9D\u8D56 layer2");
});
test("setTrackMatte \u9690\u5F0F\u4F9D\u8D56\u4E24\u4E2A\u56FE\u5C42", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi" },
      { op: "addLayer", ref: "layer2", compRef: "comp1", layerType: "solid", color: [1, 1, 1] },
      { op: "setTrackMatte", layerRef: "layer1", matteRef: "layer2", matteType: "alpha" }
    ]
  };
  const r = buildIR(input);
  const matteNode = r.nodes[3];
  assert(matteNode.deps.length === 2, "setTrackMatte \u5E94\u4F9D\u8D56\u4E24\u4E2A\u56FE\u5C42");
  assert(matteNode.deps.includes(r.nodes[1].id), "\u5E94\u4F9D\u8D56 layer1");
  assert(matteNode.deps.includes(r.nodes[2].id), "\u5E94\u4F9D\u8D56 layer2");
});
console.log("\n=== \u663E\u5F0F\u4F9D\u8D56\u89E3\u6790 ===");
test("dependsOn \u5EFA\u7ACB\u663E\u5F0F\u4F9D\u8D56", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "createComp", ref: "comp2", name: "Test2", dependsOn: ["comp1"] }
    ]
  };
  const r = buildIR(input);
  const comp2Node = r.nodes[1];
  assert(comp2Node.deps.length === 1, "\u5E94\u67091\u4E2A\u663E\u5F0F\u4F9D\u8D56");
  assert(comp2Node.deps[0] === r.nodes[0].id, "\u5E94\u4F9D\u8D56 comp1");
});
test("\u591A\u4E2A\u663E\u5F0F\u4F9D\u8D56", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "A" },
      { op: "createComp", ref: "comp2", name: "B" },
      { op: "createComp", ref: "comp3", name: "C", dependsOn: ["comp1", "comp2"] }
    ]
  };
  const r = buildIR(input);
  const comp3Node = r.nodes[2];
  assert(comp3Node.deps.length === 2, "\u5E94\u67092\u4E2A\u663E\u5F0F\u4F9D\u8D56");
  assert(comp3Node.deps.includes(r.nodes[0].id), "\u5E94\u4F9D\u8D56 comp1");
  assert(comp3Node.deps.includes(r.nodes[1].id), "\u5E94\u4F9D\u8D56 comp2");
});
test("\u663E\u5F0F\u4F9D\u8D56\u53BB\u91CD", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test" },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hi", dependsOn: ["comp1"] }
    ]
  };
  const r = buildIR(input);
  const layerNode = r.nodes[1];
  assert(layerNode.deps.length === 1, "\u91CD\u590D\u4F9D\u8D56\u5E94\u53BB\u91CD");
});
console.log("\n=== \u7F3A\u5931\u5F15\u7528\u5904\u7406 ===");
test("\u7F3A\u5931 compRef \u4E0D\u4EA7\u751F\u5D29\u6E83", () => {
  const input = {
    operations: [
      { op: "addLayer", ref: "layer1", compRef: "nonexistent", layerType: "text", text: "Hi" }
    ]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "\u4ECD\u5E94\u751F\u6210\u8282\u70B9");
  assert(r.nodes[0].deps.length === 0, "\u7F3A\u5931\u5F15\u7528\u4E0D\u5E94\u4EA7\u751F\u4F9D\u8D56");
});
test("\u7F3A\u5931 layerRef \u4E0D\u4EA7\u751F\u5D29\u6E83", () => {
  const input = {
    operations: [
      { op: "addEffect", ref: "fx1", layerRef: "nonexistent", matchName: "ADBE Gaussian Blur 2" }
    ]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 1, "\u4ECD\u5E94\u751F\u6210\u8282\u70B9");
  assert(r.nodes[0].deps.length === 0, "\u7F3A\u5931\u5F15\u7528\u4E0D\u5E94\u4EA7\u751F\u4F9D\u8D56");
});
console.log("\n=== \u590D\u6742\u573A\u666F ===");
test("\u5B8C\u6574\u7BA1\u7EBF\u4F9D\u8D56\u6B63\u786E", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "comp1", name: "Test Comp", width: 1920, height: 1080 },
      { op: "addLayer", ref: "layer1", compRef: "comp1", layerType: "text", text: "Hello" },
      { op: "addEffect", ref: "fx1", layerRef: "layer1", matchName: "ADBE Gaussian Blur 2", settings: { Blurriness: 20 } },
      { op: "setKeyframe", ref: "kf1", layerRef: "layer1", propertyPath: "Opacity", keyframes: [{ time: 0, value: 0 }] },
      { op: "setBlendMode", layerRef: "layer1", blendMode: "screen" }
    ]
  };
  const r = buildIR(input);
  assert(r.nodes.length === 5, "\u5E94\u67095\u4E2A\u8282\u70B9");
  assert(r.refToNodeId.has("comp1"), "\u5E94\u6709 comp1");
  assert(r.refToNodeId.has("layer1"), "\u5E94\u6709 layer1");
  assert(r.refToNodeId.has("fx1"), "\u5E94\u6709 fx1");
  assert(r.refToNodeId.has("kf1"), "\u5E94\u6709 kf1");
  const compId = r.refToNodeId.get("comp1");
  const layerId = r.refToNodeId.get("layer1");
  assert(r.nodes[1].deps.includes(compId), "layer1 \u4F9D\u8D56 comp1");
  assert(r.nodes[2].deps.includes(layerId), "fx1 \u4F9D\u8D56 layer1");
  assert(r.nodes[3].deps.includes(layerId), "kf1 \u4F9D\u8D56 layer1");
  assert(r.nodes[4].deps.includes(layerId), "blendMode \u4F9D\u8D56 layer1");
});
test("\u8282\u70B9 ID \u6309\u987A\u5E8F\u751F\u6210", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "c1", name: "A" },
      { op: "createComp", ref: "c2", name: "B" },
      { op: "createComp", ref: "c3", name: "C" }
    ]
  };
  const r = buildIR(input);
  assert(r.nodes[0].id === "node_000", "\u7B2C\u4E00\u4E2A ID \u5E94\u4E3A node_000");
  assert(r.nodes[1].id === "node_001", "\u7B2C\u4E8C\u4E2A ID \u5E94\u4E3A node_001");
  assert(r.nodes[2].id === "node_002", "\u7B2C\u4E09\u4E2A ID \u5E94\u4E3A node_002");
});
test("\u91CD\u590D ref \u6620\u5C04\u540E\u88AB\u8986\u76D6", () => {
  const input = {
    operations: [
      { op: "createComp", ref: "same", name: "First" },
      { op: "createComp", ref: "same", name: "Second" }
    ]
  };
  const r = buildIR(input);
  assert(r.refToNodeId.get("same") === r.nodes[1].id, "\u91CD\u590D ref \u5E94\u6307\u5411\u540E\u8005");
});
console.log(`
========================================`);
console.log(` IR Builder \u5355\u5143\u6D4B\u8BD5: ${passed} \u901A\u8FC7 / ${failed} \u5931\u8D25`);
console.log(`========================================`);
if (failed > 0) process.exit(1);
