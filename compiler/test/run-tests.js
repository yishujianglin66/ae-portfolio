/**
 * 编译器测试 - 端到端验证 (纯JS版)
 */

import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { compile, compileJSON } from "../build/index.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function readCase(name) {
  const filePath = path.join(__dirname, "cases", name);
  return fs.readFileSync(filePath, "utf8");
}

function testBasicCompile() {
  const jsonStr = readCase("test_01_basic.json");
  const result = compileJSON(jsonStr);

  console.log("\n=== 测试1: 基础编译 ===");
  console.log("成功:", result.success);
  console.log("操作数:", result.stats.operationCount);
  console.log("IR节点:", result.stats.irNodeCount);
  console.log("脚本大小:", result.stats.scriptSize, "字符");
  console.log("编译时间:", result.stats.compileTimeMs, "ms");

  if (result.errors.length > 0) {
    console.log("错误:");
    result.errors.forEach((e) => console.log("  [" + e.code + "]", e.message));
  }

  if (!result.success) throw new Error("基础编译应该成功");
  if (result.script.length === 0) throw new Error("生成的脚本不能为空");
  if (!result.script.includes("addComp")) throw new Error("脚本应包含addComp");
  if (!result.script.includes("addText")) throw new Error("脚本应包含addText");
  if (!result.script.includes("addProperty")) throw new Error("脚本应包含效果添加");
  if (!result.script.includes("setValueAtTime")) throw new Error("脚本应包含关键帧");
  if (!result.script.includes("expression")) throw new Error("脚本应包含表达式");

  const outputPath = path.join(__dirname, "output", "test_01_output.jsx");
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, result.script, "utf8");
  console.log("输出已保存:", outputPath);
}

function testParticleCompile() {
  const jsonStr = readCase("test_02_particle.json");
  const result = compileJSON(jsonStr);

  console.log("\n=== 测试2: 粒子系统编译 ===");
  console.log("成功:", result.success);
  console.log("脚本大小:", result.stats.scriptSize, "字符");

  if (!result.success) {
    console.log("错误:");
    result.errors.forEach((e) => console.log("  [" + e.code + "]", e.message));
    throw new Error("粒子系统编译应该成功");
  }

  if (!result.script.includes("addShape")) throw new Error("脚本应包含遮罩Shape创建");
  if (!result.script.includes("trackMatteType")) throw new Error("脚本应包含轨道遮罩");
  if (!result.script.includes(".parent =")) throw new Error("脚本应包含父子关系");

  const outputPath = path.join(__dirname, "output", "test_02_output.jsx");
  fs.writeFileSync(outputPath, result.script, "utf8");
  console.log("输出已保存:", outputPath);
}

function testErrorHandling() {
  const jsonStr = readCase("test_03_errors.json");
  const result = compileJSON(jsonStr);

  console.log("\n=== 测试3: 错误处理 ===");
  console.log("成功:", result.success);
  console.log("错误数:", result.errors.length);

  if (result.success) throw new Error("包含错误的输入应该编译失败");
  if (result.errors.length === 0) throw new Error("应该检测到错误");

  const errorCodes = result.errors.map((e) => e.code);
  console.log("错误码:", errorCodes.join(", "));
}

function testSchedulerOrder() {
  const input = {
    operations: [
      {
        op: "addEffect",
        layerRef: "layer1",
        matchName: "ADBE Glow",
        dependsOn: ["layer1"],
      },
      {
        op: "addLayer",
        ref: "layer1",
        compRef: "comp1",
        layerType: "text",
        text: "Test",
        dependsOn: ["comp1"],
      },
      {
        op: "createComp",
        ref: "comp1",
        name: "Test Comp",
      },
    ],
  };

  const result = compile(input);

  console.log("\n=== 测试4: 调度排序 ===");
  console.log("成功:", result.success);

  if (!result.success) throw new Error("调度排序应该成功");

  const createCompPos = result.script.indexOf("addComp");
  const addLayerPos = result.script.indexOf("addText");
  const addEffectPos = result.script.indexOf("addProperty");

  console.log("位置: createComp=" + createCompPos + ", addLayer=" + addLayerPos + ", addEffect=" + addEffectPos);

  if (createCompPos < 0 || addLayerPos < 0 || addEffectPos < 0) {
    throw new Error("脚本中应包含所有三种操作");
  }
  if (!(createCompPos < addLayerPos && addLayerPos < addEffectPos)) {
    throw new Error("操作顺序应为: createComp → addLayer → addEffect");
  }

  console.log("✓ 调度排序正确");
}

function runAll() {
  let passed = 0;
  let failed = 0;
  const tests = [
    { name: "基础编译", fn: testBasicCompile },
    { name: "粒子系统编译", fn: testParticleCompile },
    { name: "错误处理", fn: testErrorHandling },
    { name: "调度排序", fn: testSchedulerOrder },
  ];

  for (const test of tests) {
    try {
      test.fn();
      passed++;
      console.log("✓ " + test.name + " - 通过\n");
    } catch (e) {
      failed++;
      console.error("✗ " + test.name + " - 失败: " + e.message + "\n");
    }
  }

  console.log("\n========== 测试结果 ==========");
  console.log("通过: " + passed + " / " + tests.length);
  console.log("失败: " + failed + " / " + tests.length);

  if (failed > 0) process.exit(1);
}

runAll();
