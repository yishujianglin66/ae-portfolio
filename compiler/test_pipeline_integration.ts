// ============================================================================
// test_pipeline_integration.ts
// 验证 Phase4 增强版主入口集成测试
//
// 测试范围：
//   1. processUserInputEnhanced 异步主入口（LLM 不可用时降级）
//   2. nluToReportEnhanced 异步 Phase 3 衔接
//   3. 参数优化器 optimizeEnhanced
//   4. 效果知识图谱 searchEffectsEnhanced
//   5. 默认导出包含增强版函数
// ============================================================================

import {
    processUserInput,
    processUserInputEnhanced,
    nluToReport,
    nluToReportEnhanced,
    ParameterOptimizer,
    searchEffectsEnhanced,
    recommendStyleEnhanced,
    getPhase4Info,
} from "./src/phase4";

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
    if (condition) {
        console.log(`  [PASS] ${message}`);
        passed++;
    } else {
        console.log(`  [FAIL] ${message}`);
        failed++;
    }
}

async function runTests(): Promise<void> {
    console.log("=== Phase4 Pipeline 集成测试 ===\n");

    // ==================== 1. processUserInputEnhanced ====================
    console.log("[Test] processUserInputEnhanced 异步主入口");

    const response1 = await processUserInputEnhanced("给文字加一个发光");
    assert(response1 !== null && response1 !== undefined, "应返回 EngineResponse");
    assert(response1.intent !== undefined, "应包含 intent 字段");
    assert(response1.intent.type === "INTENT_ADD_EFFECT" || response1.intent.type === "ADD_EFFECT", `意图应为 ADD_EFFECT, 实际 ${response1.intent.type}`);

    const response2 = await processUserInputEnhanced("做一个赛博朋克风格");
    assert(response2 !== null && response2 !== undefined, "风格类输入应返回响应");

    // 降级测试：异常输入应通过降级返回结果
    const response3 = await processUserInputEnhanced("");
    assert(response3 !== null && response3 !== undefined, "空输入应通过降级返回响应");

    // ==================== 2. nluToReportEnhanced ====================
    console.log("\n[Test] nluToReportEnhanced 异步 Phase 3 衔接");

    const report1 = await nluToReportEnhanced("给文字加一个暖色发光");
    assert(report1 !== null && report1 !== undefined, "应返回 AnalysisReport");

    // 降级测试
    const report2 = await nluToReportEnhanced("加模糊");
    assert(report2 !== null && report2 !== undefined, "简单输入应返回 AnalysisReport");

    // ==================== 3. 参数优化器 optimizeEnhanced ====================
    console.log("\n[Test] 参数优化器 optimizeEnhanced");

    const optimizer = new ParameterOptimizer({ targetStyle: "cyberpunk" });
    const params = {
        matchName: "ADBE Glo2",
        settings: { "Glow Intensity": 1.0, "Glow Radius": 20, "Glow Threshold": 50 },
    } as any;
    const optResult = optimizer.optimize(params);
    assert(optResult !== null && optResult !== undefined, "应返回 OptimizationResult");
    assert(optResult.optimizedParams !== undefined, "应包含 optimizedParams");

    // ==================== 4. 效果知识图谱 searchEffectsEnhanced ====================
    console.log("\n[Test] 效果知识图谱 searchEffectsEnhanced");

    const effects = await searchEffectsEnhanced("glow");
    assert(Array.isArray(effects), "应返回数组");
    assert(effects.length > 0, `应找到 glow 相关效果, 实际 ${effects.length}`);

    const effects2 = await searchEffectsEnhanced("模糊");
    assert(Array.isArray(effects2), "中文搜索应返回数组");

    // ==================== 5. recommendStyleEnhanced ====================
    console.log("\n[Test] recommendStyleEnhanced 风格推荐");

    const style = await recommendStyleEnhanced("赛博朋克");
    // LLM 不可用时返回 undefined，这是正常的降级
    assert(style === undefined || (style && style.name !== undefined), "应返回 StyleRecipe 或 undefined（降级）");

    // ==================== 6. 默认导出 ====================
    console.log("\n[Test] 默认导出包含增强版函数");

    const defaultExport = (await import("./src/phase4")).default;
    assert(typeof defaultExport.processUserInputEnhanced === "function", "默认导出应包含 processUserInputEnhanced");
    assert(typeof defaultExport.nluToReportEnhanced === "function", "默认导出应包含 nluToReportEnhanced");
    assert(typeof defaultExport.processUserInput === "function", "默认导出应包含 processUserInput（同步版）");
    assert(typeof defaultExport.nluToReport === "function", "默认导出应包含 nluToReport（同步版）");

    // ==================== 7. 同步版与异步版一致性 ====================
    console.log("\n[Test] 同步版与异步版一致性");

    const syncResp = processUserInput("给文字加一个发光");
    const asyncResp = await processUserInputEnhanced("给文字加一个发光");
    // LLM 不可用时异步版应降级到同步版，结果应一致
    assert(asyncResp.intent.type === syncResp.intent.type, "LLM 不可用时异步版应降级到同步版，意图类型一致");

    // ==================== 8. getPhase4Info ====================
    console.log("\n[Test] getPhase4Info 系统信息");

    const info = getPhase4Info();
    assert(info.phase === 4, "Phase 版本应为 4");
    assert(Array.isArray(info.components), "应包含组件列表");

    // ==================== 总结 ====================
    console.log("\n============================================================");
    console.log(`测试结果: ${passed} 通过, ${failed} 失败`);
    console.log("============================================================");

    if (failed > 0) {
        process.exit(1);
    }
}

runTests().catch((err) => {
    console.error("测试执行出错:", err);
    process.exit(1);
});
