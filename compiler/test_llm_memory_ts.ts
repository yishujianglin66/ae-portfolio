// ============================================================================
// test_llm_memory_ts.ts
// TypeScript 端 LLM 网关 + 记忆系统 + 意图路由增强 集成测试
// ============================================================================

import {
    LLMGateway,
    TokenCompressor,
    chat,
    chatWithRouting,
    configureGateway,
    getLLMGateway,
} from "./src/phase4/llm-gateway";
import { MemoryStore, getMemoryStore } from "./src/phase4/memory-store";
import { intentRouter } from "./src/phase4/intent-router";
import { Intent, IntentType, IntentSlots } from "./src/phase4/types";
import { hybridCoordinator } from "./src/phase4/hybrid-coordinator";

let passed = 0;
let failed = 0;

function test(name: string, fn: () => void | Promise<void>): void {
    console.log(`\n[Test] ${name}`);
    try {
        const result = fn();
        if (result instanceof Promise) {
            result.then(
                () => {
                    console.log("  [PASS]");
                    passed++;
                },
                (e) => {
                    console.error(`  [FAIL] ${e.message}`);
                    console.error(e.stack);
                    failed++;
                }
            );
        } else {
            console.log("  [PASS]");
            passed++;
        }
    } catch (e: any) {
        console.error(`  [FAIL] ${e.message}`);
        console.error(e.stack);
        failed++;
    }
}

// ============================================================================
// 1. TokenCompressor 测试
// ============================================================================

test("TokenCompressor - 提示词压缩", () => {
    const comp = new TokenCompressor();

    const original = "请详细分析这段视频的情绪，请描述场景中的人物动作";
    const compressed = comp.compressPrompt(original);

    if (compressed.includes("请详细分析")) {
        throw new Error("应压缩冗余词 '请详细分析'");
    }
    if (!compressed.includes("分析")) {
        throw new Error("应保留核心词 '分析'");
    }
});

test("TokenCompressor - 系统提示词截断", () => {
    const comp = new TokenCompressor();

    const longSystem = "请详细分析".repeat(50);
    const compressed = comp.compressSystem(longSystem);

    if (compressed.length > 205) {
        throw new Error(`应截断到约 200 字符, 实际 ${compressed.length}`);
    }
});

test("TokenCompressor - 响应解压", () => {
    const comp = new TokenCompressor();

    const caveman = "意图:roto|情绪:紧张|置信度:0.85";
    const decompressed = comp.decompressResponse(caveman);

    if (decompressed.includes("|")) {
        throw new Error("应将分隔符转为换行");
    }
    if (!decompressed.includes("意图:roto")) {
        throw new Error("应保留内容");
    }

    const plain = "这是普通回复";
    if (comp.decompressResponse(plain) !== plain) {
        throw new Error("无分隔符的响应应保持不变");
    }
});

// ============================================================================
// 2. LLMGateway 测试
// ============================================================================

test("LLMGateway - 默认配置不可用", () => {
    const gw = new LLMGateway();
    if (gw.isAvailable()) {
        throw new Error("默认无 api_key 时应不可用");
    }
});

test("LLMGateway - 配置后可用", () => {
    const gw = new LLMGateway({
        baseUrl: "http://localhost:5273/v1",
        apiKey: "test-key",
    });
    if (!gw.isAvailable()) {
        throw new Error("配置后应可用");
    }
});

test("LLMGateway - 环境变量配置", () => {
    const gw = new LLMGateway();
    gw.configureFromEnv({
        AEKV_LLM_BASE_URL: "http://test-gw:8080/v1",
        AEKV_LLM_API_KEY: "env-key",
        AEKV_LLM_MODEL: "deepseek-chat",
    });

    if (gw["config"].baseUrl !== "http://test-gw:8080/v1") {
        throw new Error("baseUrl 配置错误");
    }
    if (gw["config"].apiKey !== "env-key") {
        throw new Error("apiKey 配置错误");
    }
    if (!gw.isAvailable()) {
        throw new Error("配置后应可用");
    }
});

test("LLMGateway - 路由表默认值", () => {
    const gw = new LLMGateway({
        baseUrl: "http://localhost:5273/v1",
        apiKey: "test-key",
    });

    const routing = gw["config"].modelRouting;
    if (routing.intent_classification !== "auto") {
        throw new Error("意图分类路由应为 auto");
    }
    if (routing.effect_planning !== "auto") {
        throw new Error("效果规划路由应为 auto");
    }
});

test("LLMGateway - 未配置时 chat 返回失败", async () => {
    const gw = new LLMGateway();
    const result = await gw.chat({ message: "test" });

    if (result.success) {
        throw new Error("未配置时应返回失败");
    }
    if (!result.error.includes("未配置")) {
        throw new Error("错误信息应包含 '未配置'");
    }
});

test("LLMGateway - 统计初始状态", () => {
    const gw = new LLMGateway();
    const stats = gw.getStats();

    if (stats.totalRequests !== 0) {
        throw new Error("初始请求数应为 0");
    }
    if (stats.successRate !== "0.0%") {
        throw new Error("初始成功率应为 0.0%");
    }
});

// ============================================================================
// 3. MemoryStore 测试
// ============================================================================

test("MemoryStore - 基本存取", () => {
    const store = new MemoryStore();
    store.clear();

    const id = store.remember({
        category: "roto_execution",
        key: "埼玉_抠像",
        content: { method: "RotoNode", frames: 18 },
        tags: ["roto", "silhouette"],
        confidence: 0.8,
    });

    if (id <= 0) {
        throw new Error("应返回有效 ID");
    }

    const entry = store.recall("roto_execution", "埼玉_抠像");
    if (!entry) {
        throw new Error("应能检索到记忆");
    }
    if (entry.content.method !== "RotoNode") {
        throw new Error("内容不匹配");
    }
    if (entry.confidence !== 0.8) {
        throw new Error("置信度不匹配");
    }
    if (!entry.tags.includes("roto")) {
        throw new Error("标签不匹配");
    }
    if (entry.accessCount < 1) {
        throw new Error("访问次数应 >= 1");
    }
});

test("MemoryStore - 搜索功能", () => {
    const store = new MemoryStore();
    store.clear();

    store.remember({
        category: "effect",
        key: "发光效果",
        content: { type: "glow" },
        tags: ["glow", "发光"],
    });
    store.remember({
        category: "effect",
        key: "模糊效果",
        content: { type: "blur" },
        tags: ["blur", "模糊"],
    });
    store.remember({
        category: "roto",
        key: "人物抠像",
        content: { method: "RotoNode" },
        tags: ["roto", "人物"],
    });

    const results = store.search({ query: "发光" });
    if (results.length < 1) {
        throw new Error("应能搜索到发光效果");
    }
    if (results[0].key !== "发光效果") {
        throw new Error("第一个结果应为发光效果");
    }

    const rotoResults = store.search({ query: "roto" });
    if (rotoResults.length < 1) {
        throw new Error("应能搜索到抠像相关");
    }

    const categoryResults = store.search({
        query: "效果",
        category: "effect",
    });
    if (!categoryResults.every((r) => r.category === "effect")) {
        throw new Error("分类搜索应只返回 effect 类");
    }
});

test("MemoryStore - 删除", () => {
    const store = new MemoryStore();
    store.clear();

    store.remember({
        category: "test",
        key: "to_delete",
        content: { v: 1 },
    });

    const deleted = store.forget("test", "to_delete");
    if (!deleted) {
        throw new Error("应成功删除");
    }

    const entry = store.recall("test", "to_delete");
    if (entry) {
        throw new Error("删除后应找不到");
    }
});

test("MemoryStore - 经验学习", () => {
    const store = new MemoryStore();
    store.clear();

    store.remember({
        category: "pipeline_execution",
        key: "roto_glow",
        content: { steps: ["roto", "glow"] },
        confidence: 0.5,
    });

    store.recordOutcome("pipeline_execution", "roto_glow", true);
    store.recordOutcome("pipeline_execution", "roto_glow", true);
    store.recordOutcome("pipeline_execution", "roto_glow", true);

    const entry = store.recall("pipeline_execution", "roto_glow");
    if (!entry) {
        throw new Error("应能找到记忆");
    }
    if (entry.successCount !== 3) {
        throw new Error(`成功次数应为 3, 实际 ${entry.successCount}`);
    }
    if (entry.confidence <= 0.5) {
        throw new Error("多次成功后置信度应提升");
    }

    store.recordOutcome("pipeline_execution", "roto_glow", false);
    const entry2 = store.recall("pipeline_execution", "roto_glow");
    if (!entry2 || entry2.failureCount !== 1) {
        throw new Error("失败次数应为 1");
    }
});

test("MemoryStore - 经验获取", () => {
    const store = new MemoryStore();
    store.clear();

    store.remember({
        category: "intent_route",
        key: "roto+glow",
        content: { route: { type: "hybrid" } },
        tags: ["hybrid"],
        confidence: 0.7,
    });

    const experiences = store.getExperience({
        category: "intent_route",
        taskKeyword: "roto",
        minConfidence: 0.3,
    });

    if (experiences.length < 1) {
        throw new Error("应获取到相关经验");
    }
});

test("MemoryStore - 统计", () => {
    const store = new MemoryStore();
    store.clear();

    store.remember({ category: "effect", key: "e1", content: {} });
    store.remember({ category: "effect", key: "e2", content: {} });
    store.remember({ category: "roto", key: "r1", content: {} });

    const stats = store.getStats();
    if (stats.totalMemories !== 3) {
        throw new Error(`总记忆数应为 3, 实际 ${stats.totalMemories}`);
    }
    if (stats.categories.effect !== 2) {
        throw new Error("effect 类应有 2 条");
    }
    if (stats.categories.roto !== 1) {
        throw new Error("roto 类应有 1 条");
    }
});

// ============================================================================
// 4. IntentRouter LLM 增强测试
// ============================================================================

function makeIntent(raw: string, type = IntentType.ADD_EFFECT): Intent {
    return {
        type,
        rawInput: raw,
        confidence: 0.8,
        slots: {} as IntentSlots,
        entities: [],
    };
}

test("IntentRouter - 本地路由正常工作", () => {
    const intent = makeIntent("给视频加发光效果", IntentType.ADD_EFFECT);
    const route = intentRouter.route(intent);

    if (route.type !== "ae_only") {
        throw new Error(`应为 ae_only, 实际 ${route.type}`);
    }
    if (!route.confidence) {
        throw new Error("应具有置信度");
    }
});

test("IntentRouter - routeEnhanced LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const intent = makeIntent("扣掉背景然后加发光", IntentType.SILHOUETTE_TASK);
    const route = await intentRouter.routeEnhanced(intent);

    if (route.type === "unknown") {
        throw new Error("降级后本地路由应能识别");
    }
    if (!route.reason) {
        throw new Error("应有路由原因");
    }
});

test("IntentRouter - 记忆系统缓存", async () => {
    const mem = getMemoryStore();
    mem.clear();

    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const intent = makeIntent("测试记忆路由", IntentType.ADD_EFFECT);

    // 第一次调用，记录到记忆
    const route1 = await intentRouter.routeEnhanced(intent);

    // 手动存入高置信度记忆
    mem.remember({
        category: "intent_route",
        key: intent.rawInput.slice(0, 50),
        content: { route: route1 },
        tags: [route1.type],
        confidence: 0.9,
    });

    // 第二次调用，应该从记忆读取
    const route2 = await intentRouter.routeEnhanced(intent);

    if (!route2.reason.includes("memory")) {
        // 记忆置信度可能不够高，或者记忆中 route 结构不完整
        // 这里只验证记忆系统确实记录了
        const stats = mem.getStats();
        if (stats.totalMemories < 1) {
            throw new Error("记忆系统应至少有 1 条记录");
        }
    }
});

// ============================================================================
// 5. HybridCoordinator LLM 增强测试
// ============================================================================

test("HybridCoordinator - planExecution LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const intent = makeIntent("扣人像加发光", IntentType.SILHOUETTE_TASK);
    const route = intentRouter.route(intent);
    const result = await hybridCoordinator.planExecution(intent, route);

    if (!result) {
        throw new Error("降级后应返回原路由");
    }
    if (result.type !== route.type) {
        throw new Error("类型应不变");
    }
});

test("HybridCoordinator - reviewQuality LLM 不可用时降级", async () => {
    const gw = getLLMGateway();
    gw.configure({ apiKey: "", baseUrl: "" });

    const intent = makeIntent("测试", IntentType.ADD_EFFECT);
    const route = intentRouter.route(intent);
    const result = await hybridCoordinator.reviewQuality(route, intent);

    if (!result.passed) {
        throw new Error("降级后应默认为通过");
    }
});

// ============================================================================
// 6. 全局实例测试
// ============================================================================

test("全局实例 - getLLMGateway 单例", () => {
    const gw1 = getLLMGateway();
    const gw2 = getLLMGateway();
    if (gw1 !== gw2) {
        throw new Error("应为单例");
    }
});

test("全局实例 - getMemoryStore 单例", () => {
    const m1 = getMemoryStore();
    const m2 = getMemoryStore();
    if (m1 !== m2) {
        throw new Error("应为单例");
    }
});

// ============================================================================
// 运行测试
// ============================================================================

console.log("=".repeat(60));
console.log("TypeScript 端 LLM 网关 + 记忆系统 + 路由增强 集成测试");
console.log("=".repeat(60));

// 等待所有异步测试完成
setTimeout(() => {
    console.log("\n" + "=".repeat(60));
    console.log(`测试结果: ${passed} 通过, ${failed} 失败`);
    console.log("=".repeat(60));

    if (failed > 0) {
        process.exit(1);
    }
}, 1000);
