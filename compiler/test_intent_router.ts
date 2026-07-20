// ============================================================================
// test_intent_router.ts
// IntentRouter + HybridCoordinator 端到端集成测试
// ============================================================================

import { IntentRouter, intentRouter } from "./src/phase4/intent-router";
import { HybridCoordinator, hybridCoordinator } from "./src/phase4/hybrid-coordinator";
import { Intent, IntentType } from "./src/phase4/types";

// ---------------------------------------------------------------------------
// 测试辅助
// ---------------------------------------------------------------------------

function makeIntent(
    type: IntentType,
    rawInput: string,
    slots: Record<string, unknown> = {},
    confidence: number = 0.88
): Intent {
    return {
        type,
        confidence,
        slots,
        rawInput,
    };
}

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

// ---------------------------------------------------------------------------
// 测试用例
// ---------------------------------------------------------------------------

console.log("=== IntentRouter 测试 ===\n");

// 测试 1: 纯 AE 任务
console.log("[Test 1] 纯 AE 任务: '加个模糊效果'");
{
    const intent = makeIntent(IntentType.ADD_EFFECT, "加个模糊效果", { effectName: "模糊" });
    const route = intentRouter.route(intent);
    assert(route.type === "ae_only", `路由类型 = ${route.type}`);
    assert((route.aeOperations?.length ?? 0) > 0, "生成了 AE 操作");
    assert(route.executionOrder?.includes("ae") === true, "执行顺序包含 ae");
}

// 测试 2: 纯 Silhouette Roto 任务
console.log("\n[Test 2] 纯 Silhouette 任务: '扣个人像'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "扣个人像", {
        silhouetteTask: "roto",
        rotoTarget: "人像",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "silhouette_only", `路由类型 = ${route.type}`);
    assert((route.silhouetteOperations?.length ?? 0) > 0, "生成了 Silhouette 操作");
    assert(route.silhouetteOperations?.[0].taskType === "roto", "任务类型 = roto");
    assert(route.fallback !== undefined, "有降级策略");
}

// 测试 3: 纯 Silhouette Track 任务
console.log("\n[Test 3] 纯 Silhouette 任务: '跟踪这个物体'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "跟踪这个物体", {
        silhouetteTask: "track",
        trackType: "planar",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "silhouette_only", `路由类型 = ${route.type}`);
    assert(route.silhouetteOperations?.[0].taskType === "track", "任务类型 = track");
    assert(route.silhouetteOperations?.[0].trackType === "planar", "跟踪类型 = planar");
}

// 测试 4: 混合任务 - Roto + AE 效果
console.log("\n[Test 4] 混合任务: '扣个人像然后加发光'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "扣个人像然后加发光", {
        silhouetteTask: "roto",
        rotoTarget: "人像",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "hybrid", `路由类型 = ${route.type}`);
    assert((route.silhouetteOperations?.length ?? 0) > 0, "生成了 Silhouette 操作");
    assert((route.aeOperations?.length ?? 0) > 0, "生成了 AE 操作");
    assert(route.executionOrder?.[0] === "silhouette", "先执行 Silhouette");
    assert(route.executionOrder?.[1] === "ae", "后执行 AE");
}

// 测试 5: 混合任务 - Track + AE 动画
console.log("\n[Test 5] 混合任务: '跟踪物体然后做文字动画'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "跟踪物体然后做文字动画", {
        silhouetteTask: "track",
        trackType: "planar",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "hybrid", `路由类型 = ${route.type}`);
    assert((route.silhouetteOperations?.length ?? 0) > 0, "生成了 Silhouette 跟踪操作");
    assert((route.aeOperations?.length ?? 0) > 0, "生成了 AE 动画操作");
}

// 测试 6: 混合任务拆分
console.log("\n[Test 6] 混合任务拆分: '抠掉背景再加调色'");
{
    const input = "抠掉背景再加调色";
    const isHybrid = intentRouter.isHybrid(input);
    assert(isHybrid === true, "识别为混合任务");

    const split = intentRouter.splitHybridInput(input);
    assert(split !== null, "拆分成功");
    assert(split?.silhouettePart === "抠掉背景", `Silhouette 部分 = ${split?.silhouettePart}`);
    // 连接词 "再加" 整体消耗，AE 部分应为 "调色"
    assert(split?.aePart === "调色", `AE 部分 = ${split?.aePart}`);
}

// 测试 7: 未知意图
console.log("\n[Test 7] 未知意图: 'asdfsdf'");
{
    const intent = makeIntent(IntentType.UNKNOWN, "asdfsdf", {}, 0.1);
    const route = intentRouter.route(intent);
    assert(route.type === "unknown", `路由类型 = ${route.type}`);
}

// 测试 8: 纯 Silhouette Paint 任务
console.log("\n[Test 8] 纯 Silhouette 任务: '修掉水印'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "修掉水印", {
        silhouetteTask: "paint",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "silhouette_only", `路由类型 = ${route.type}`);
    assert(route.silhouetteOperations?.[0].taskType === "paint", "任务类型 = paint");
    assert(route.silhouetteOperations?.[0].paintMode === "clone", "Paint 模式 = clone");
}

// 测试 9: 降级策略验证
console.log("\n[Test 9] 降级策略: Roto 降级到 AE Mask");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "扣个人像", {
        silhouetteTask: "roto",
    });
    const route = intentRouter.route(intent);
    assert(route.fallback !== undefined, "有降级策略");
    assert(route.fallback?.aeFallbackOps.length! > 0, "降级到 AE 操作");
    assert(route.fallback?.message.includes("AE 原生 Mask") === true, "降级提示包含 Mask");
}

// 测试 10: 混合任务 - Paint + AE
console.log("\n[Test 10] 混合任务: '修复画面然后加噪波'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "修复画面然后加噪波", {
        silhouetteTask: "paint",
    });
    const route = intentRouter.route(intent);
    assert(route.type === "hybrid", `路由类型 = ${route.type}`);
    assert((route.silhouetteOperations?.length ?? 0) > 0, "生成了 Paint 操作");
    assert((route.aeOperations?.length ?? 0) > 0, "生成了 AE 效果操作");
}

console.log("\n=== HybridCoordinator 测试 ===\n");

// 测试 11: 纯 AE 任务执行
console.log("[Test 11] 纯 AE 任务执行: '加个发光'");
{
    const intent = makeIntent(IntentType.ADD_EFFECT, "加个发光", { effectName: "发光" });
    hybridCoordinator.execute(intent, {
        sourcePath: "C:/Temp/test.mp4",
        outputDir: "D:/AE-Work/silhouette_output",
    }).then(result => {
        assert(result.status === "success" || result.status === "error", `执行完成: ${result.status}`);
        assert(result.phases.length > 0, "有执行阶段");
        assert(result.totalDurationMs >= 0, "有执行时间");
    });
}

// 测试 12: Silhouette 任务执行（带降级）
console.log("\n[Test 12] Silhouette 任务执行: '扣个人像'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "扣个人像", {
        silhouetteTask: "roto",
        rotoTarget: "人像",
    });
    hybridCoordinator.execute(intent, {
        sourcePath: "C:/Temp/test.mp4",
        outputDir: "D:/AE-Work/silhouette_output",
        enableFallback: true,
        maxRetries: 2,
    }).then(result => {
        assert(result.route.type === "silhouette_only", `路由 = ${result.route.type}`);
        assert(result.phases.length >= 1, "至少 1 个阶段");
    });
}

// 测试 13: 混合任务执行
console.log("\n[Test 13] 混合任务执行: '扣人像后加发光'");
{
    const intent = makeIntent(IntentType.SILHOUETTE_TASK, "扣人像后加发光", {
        silhouetteTask: "roto",
        rotoTarget: "人像",
    });
    hybridCoordinator.execute(intent, {
        sourcePath: "C:/Temp/test.mp4",
        outputDir: "D:/AE-Work/silhouette_output",
        onProgress: (phase, progress, message) => {
            console.log(`    [Progress] ${phase}: ${(progress * 100).toFixed(0)}% - ${message}`);
        },
    }).then(result => {
        assert(result.route.type === "hybrid", `路由 = ${result.route.type}`);
        assert(result.phases.length >= 2, "至少 2 个阶段 (Silhouette + AE)");
    });
}

// 等待异步测试完成
setTimeout(() => {
    console.log("\n" + "=".repeat(60));
    console.log(`测试结果: ${passed} 通过, ${failed} 失败`);
    console.log("=".repeat(60));
    process.exit(failed > 0 ? 1 : 0);
}, 3000);
