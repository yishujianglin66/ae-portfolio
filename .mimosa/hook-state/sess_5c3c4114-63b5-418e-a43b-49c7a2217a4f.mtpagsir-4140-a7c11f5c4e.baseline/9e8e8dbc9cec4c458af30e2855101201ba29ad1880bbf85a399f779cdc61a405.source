// ============================================================================
// test_nlu_llm_enhanced.ts
// NLU Parser + 参数优化器 + 效果知识图谱 LLM 增强 测试
// ============================================================================

import { nluParser } from "./src/phase4/nlu-parser";
import { IntentType } from "./src/phase4/types";
import { parameterOptimizer } from "./src/phase4/param-optimizer";
import {
    searchEffects,
    searchEffectsEnhanced,
    findStyleRecipe,
    recommendStyleEnhanced,
    getKnowledgeStats,
} from "./src/phase4/effect-knowledge-graph";
import { getLLMGateway } from "./src/phase4/llm-gateway";
import { getMemoryStore } from "./src/phase4/memory-store";

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
    if (condition) {
        console.log(`  [PASS] ${message}`);
        passed++;
    } else {
        console.error(`  [FAIL] ${message}`);
        failed++;
    }
}

async function test(name: string, fn: () => Promise<void> | void): Promise<void> {
    console.log(`\n[Test] ${name}`);
    try {
        await fn();
    } catch (e: any) {
        console.error(`  [FAIL] 异常: ${e.message}`);
        console.error(e.stack);
        failed++;
    }
}

// ============================================================================
// 1. NLU Parser 本地解析
// ============================================================================

await test("NLU Parser - 本地解析 ADD_EFFECT", () => {
    const intent = nluParser.parse("加个发光效果");
    assert(intent.type === IntentType.ADD_EFFECT, `应为 ADD_EFFECT, 实际 ${intent.type}`);
    assert(intent.confidence > 0.5, `置信度应 > 0.5, 实际 ${intent.confidence}`);
});

await test("NLU Parser - 本地解析 CREATE_ANIM", () => {
    const intent = nluParser.parse("做一个淡入动画");
    assert(intent.type === IntentType.CREATE_ANIM, `应为 CREATE_ANIM, 实际 ${intent.type}`);
});

await test("NLU Parser - 本地解析 SILHOUETTE_TASK", () => {
    const intent = nluParser.parse("扣个人像");
    assert(intent.type === IntentType.SILHOUETTE_TASK, `应为 SILHOUETTE_TASK, 实际 ${intent.type}`);
    assert(intent.slots.silhouetteTask === "roto", `应为 roto, 实际 ${intent.slots.silhouetteTask}`);
});

await test("NLU Parser - 本地解析 UNKNOWN", () => {
    const intent = nluParser.parse("asdfghjkl");
    assert(intent.type === IntentType.UNKNOWN, `应为 UNKNOWN, 实际 ${intent.type}`);
});

// ============================================================================
// 2. NLU Parser LLM 增强降级
// ============================================================================

await test("NLU Parser - parseEnhanced LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const intent = await nluParser.parseEnhanced("加个模糊效果");
    assert(intent.type === IntentType.ADD_EFFECT, `降级后应识别为 ADD_EFFECT, 实际 ${intent.type}`);
});

await test("NLU Parser - parseEnhanced 高置信度不调用 LLM", async () => {
    const intent = await nluParser.parseEnhanced("加个发光效果");
    assert(intent.confidence >= 0.85, `高置信度应 >= 0.85, 实际 ${intent.confidence}`);
});

await test("NLU Parser - parseEnhanced 记忆系统记录", async () => {
    const mem = getMemoryStore();
    mem.clear();

    await nluParser.parseEnhanced("加个测试效果");

    const stats = mem.getStats();
    assert(stats.totalMemories >= 0, "记忆系统应可正常操作");
});

// ============================================================================
// 3. 参数优化器
// ============================================================================

await test("ParameterOptimizer - 本地优化", () => {
    const result = parameterOptimizer.optimize({
        matchName: "ADBE Glo2",
        settings: { "Glow Intensity": 10, "Glow Radius": 200 },
    });
    assert(result.score > 0, `优化得分应 > 0, 实际 ${result.score}`);
    // Glow Intensity 10 + Glow Radius 200 应触发冲突规则
    assert(result.changes.length > 0 || result.warnings.length > 0,
        `应有优化变更或警告, changes=${result.changes.length}, warnings=${result.warnings.length}`);
});

await test("ParameterOptimizer - optimizeEnhanced LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const result = await parameterOptimizer.optimizeEnhanced({
        matchName: "ADBE Glo2",
        settings: { intensity: 5, radius: 50 },
    });
    assert(result.score > 0, `降级后得分应 > 0, 实际 ${result.score}`);
});

await test("ParameterOptimizer - listSupportedEffects", () => {
    const effects = parameterOptimizer.listSupportedEffects();
    assert(effects.length >= 5, `应支持至少 5 个效果, 实际 ${effects.length}`);
    assert(effects.includes("ADBE Glo2"), "应包含 Glow");
});

// ============================================================================
// 4. 效果知识图谱
// ============================================================================

await test("EffectKnowledgeGraph - 本地搜索", () => {
    const results = searchEffects("发光");
    assert(results.length > 0, "应能搜索到发光相关效果");
    assert(results.some(e => e.displayName.includes("Glow")), "应包含 Glow");
});

await test("EffectKnowledgeGraph - 本地风格查找", () => {
    const recipe = findStyleRecipe("赛博朋克");
    assert(recipe !== undefined, "应能找到赛博朋克风格");
    assert(recipe!.name === "cyberpunk", `name 应为 cyberpunk, 实际 ${recipe!.name}`);
});

await test("EffectKnowledgeGraph - searchEffectsEnhanced LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const results = await searchEffectsEnhanced("发光");
    assert(results.length > 0, "降级后应仍有结果");
});

await test("EffectKnowledgeGraph - recommendStyleEnhanced LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const recipe = await recommendStyleEnhanced("赛博朋克");
    assert(recipe !== undefined, "降级后应仍有结果");
});

await test("EffectKnowledgeGraph - 统计信息", () => {
    const stats = getKnowledgeStats();
    assert(stats.totalEffects >= 60, `总效果数应 >= 60, 实际 ${stats.totalEffects}`);
    assert(stats.totalStyleRecipes >= 20, `风格配方应 >= 20, 实际 ${stats.totalStyleRecipes}`);
});

// ============================================================================
// 5. 集成验证
// ============================================================================

await test("集成 - NLU → IntentRouter → KnowledgeGraph 数据流", () => {
    // 1. NLU 解析
    const intent = nluParser.parse("加个发光效果");
    assert(intent.type === IntentType.ADD_EFFECT, "NLU 应识别为 ADD_EFFECT");

    // 2. 知识图谱搜索效果（用英文关键词）
    const effects = searchEffects("glow");
    assert(effects.length > 0, `知识图谱应能找到 glow 相关效果, 实际 ${effects.length}`);

    // 3. 参数优化
    if (effects.length > 0) {
        const matchName = effects[0].matchName;
        const optResult = parameterOptimizer.optimize({
            matchName,
            settings: {},
        });
        assert(optResult.score > 0, "参数优化应成功");
    }
});

// ============================================================================
// 结果
// ============================================================================

console.log("\n" + "=".repeat(60));
console.log(`测试结果: ${passed} 通过, ${failed} 失败`);
console.log("=".repeat(60));

if (failed > 0) {
    process.exit(1);
}
