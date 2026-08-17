// ============================================================================
// tests/test_phase5_learning.ts
// Phase 5 学习机器自身正确性测试
//
// 覆盖：
//   1. LearningLoop 内存学习（正向/偏差/负向）
//   2. PersistentLearningLoop 持久化 + 检查点
//   3. ResultVerifier 参数验证
//   4. FailureRecovery 错误码 → 恢复策略
//   5. RetryCounter 重试控制
//   6. LearningMetrics 度量计算
//
// 运行: npx esbuild tests/test_phase5_learning.ts --bundle --platform=node --format=esm --outfile=dist/test_phase5.mjs; node --input-type=module dist/test_phase5.mjs
// ============================================================================

import { LearningLoop, MemoryCaseStore, MemoryDefaultValueStore } from "../compiler/src/phase5/learning-loop";
import { PersistentLearningLoop, PersistentCaseStore, PersistentDefaultValueStore } from "../compiler/src/phase5/persistent-learning-loop";
import { ResultVerifier, MockMcpClient, McpClient } from "../compiler/src/phase5/result-verifier";
import { FailureRecovery, RetryCounter, ErrorCode } from "../compiler/src/phase5/failure-recovery";
import {
    ExecutionResult,
    ExpectedParameters,
    VerificationResult,
    ActualProperty,
} from "../compiler/src/phase5/types";
import * as fs from "fs";
import * as path from "path";
import * as os from "os";

let passed = 0;
let failed = 0;
const failures: string[] = [];

function assert(condition: boolean, msg: string) {
    if (condition) {
        passed++;
        console.log(`  ✅ ${msg}`);
    } else {
        failed++;
        failures.push(msg);
        console.log(`  ❌ ${msg}`);
    }
}

function assertApprox(actual: number, expected: number, tolerance: number, msg: string) {
    const ok = Math.abs(actual - expected) <= tolerance;
    if (ok) {
        passed++;
        console.log(`  ✅ ${msg} (actual=${actual.toFixed(4)})`);
    } else {
        failed++;
        failures.push(`${msg} (expected≈${expected}, got=${actual})`);
        console.log(`  ❌ ${msg} (expected≈${expected}, got=${actual})`);
    }
}

// ============================================================================
// 辅助数据
// ============================================================================

function makeExpected(overrides?: Partial<ExpectedParameters>): ExpectedParameters {
    return {
        compName: "Comp 1",
        layerIndex: 1,
        effectMatchName: "ADBE Gaussian Blur 2",
        effectName: "Gaussian Blur",
        properties: [
            { name: "Blurriness", value: 10 },
            { name: "Blur Dimensions", value: 1 },
        ],
        ...overrides,
    };
}

function makeExecution(overrides?: Partial<ExecutionResult>): ExecutionResult {
    return {
        success: true,
        effectIndex: 1,
        effectName: "Gaussian Blur",
        ...overrides,
    };
}

function makeVerification(overrides?: Partial<VerificationResult>): VerificationResult {
    return {
        passed: true,
        mismatches: [],
        deviationScore: 0,
        ...overrides,
    };
}

// ============================================================================
// 1. LearningLoop 内存学习测试
// ============================================================================

function testLearningLoopSuccess() {
    console.log("\n[1.1] LearningLoop - 正向学习（用户满意）");
    const loop = new LearningLoop();
    const expected = makeExpected();
    const execution = makeExecution();
    const verification = makeVerification();

    loop.recordExecution("加个模糊", "add_effect", expected, execution, verification,
        { satisfied: true }, ["nlu:add_effect", "router:blur"]);

    const metrics = loop.getMetrics();
    assert(metrics.totalExecutions === 1, "记录1次执行");
    assert(metrics.successCount === 1, "成功计数=1");
    assert(metrics.learnedTemplates === 1, "学习到1个模板");
    assert(metrics.confidenceAdjustments === 1, "置信度调整1次");

    // 验证模板内容
    const templates = loop.getCaseStore().findTemplates("ADBE Gaussian Blur 2");
    assert(templates.length === 1, "模板库中找到1个模板");
    assert(templates[0].parameters["Blurriness"] === 10, "模板参数 Blurriness=10");
    assert(templates[0].source === "auto-learned", "模板来源=auto-learned");

    // 验证置信度调整
    const adjustments = loop.getConfidenceAdjustments();
    assert(adjustments[0].direction === "boost", "置信度方向=boost");
    assertApprox(adjustments[0].delta, 0.05, 0.001, "置信度增幅=0.05");
}

function testLearningLoopDeviation() {
    console.log("\n[1.2] LearningLoop - 偏差学习（用户调整参数）");
    const loop = new LearningLoop();
    const expected = makeExpected();
    const execution = makeExecution();
    const verification = makeVerification({ passed: true, deviationScore: 0.5 });

    loop.recordExecution("加个模糊", "add_effect", expected, execution, verification,
        { adjusted: true, finalParams: [{ name: "Blurriness", value: 20 }] });

    // 偏差 = |10-20|/|10| = 1.0 > 0.05 → 应更新默认值
    const dv = loop.getDefaultValueStore().get("ADBE Gaussian Blur 2", "Blurriness");
    assert(dv === 20, "默认值更新为用户最终值 20");

    const metrics = loop.getMetrics();
    assert(metrics.userAdjustedCount === 1, "用户调整计数=1");
}

function testLearningLoopFailure() {
    console.log("\n[1.3] LearningLoop - 负向学习（用户撤销）");
    const loop = new LearningLoop();
    const expected = makeExpected();
    const execution = makeExecution({ success: true });
    const verification = makeVerification();

    loop.recordExecution("加个模糊", "add_effect", expected, execution, verification,
        { undone: true }, ["nlu:add_effect", "router:blur"]);

    const adjustments = loop.getConfidenceAdjustments();
    assert(adjustments.length === 1, "产生1次置信度调整");
    assert(adjustments[0].direction === "penalize", "置信度方向=penalize");
    assertApprox(adjustments[0].delta, 0.1, 0.001, "惩罚幅度=0.1");

    const metrics = loop.getMetrics();
    assert(metrics.userUndoneCount === 1, "用户撤销计数=1");
}

function testLearningLoopExecutionFailure() {
    console.log("\n[1.4] LearningLoop - 执行失败学习");
    const loop = new LearningLoop();
    const expected = makeExpected();
    const execution = makeExecution({ success: false, errorCode: "E300", errorMessage: "效果未找到" });
    const verification = makeVerification({ passed: false, deviationScore: 1.0 });

    loop.recordExecution("加个发光", "add_effect", expected, execution, verification,
        undefined, ["nlu:add_effect", "router:glow"]);

    const adjustments = loop.getConfidenceAdjustments();
    assert(adjustments.length === 1, "失败产生置信度调整");
    assert(adjustments[0].direction === "penalize", "失败方向=penalize");
    assert(adjustments[0].reason.includes("执行失败"), "原因包含'执行失败'");
}

// ============================================================================
// 2. DefaultValueStore 加权平均测试
// ============================================================================

function testDefaultValueStoreWeightedAverage() {
    console.log("\n[2.1] DefaultValueStore - 加权平均");
    const store = new MemoryDefaultValueStore();

    // 第一次更新：值=10，权重=0.3
    store.update("ADBE Glow", "Intensity", 10, 0.3);
    assert(store.get("ADBE Glow", "Intensity") === 10, "首次更新值=10");

    // 第二次更新：值=20，权重=0.3
    // 加权平均 = (10*0.3 + 20*0.3) / (0.3+0.3) = 15
    store.update("ADBE Glow", "Intensity", 20, 0.3);
    assertApprox(store.get("ADBE Glow", "Intensity") as number, 15, 0.001, "二次加权平均=15");

    // 第三次更新：值=30，权重=0.3
    // 加权平均 = (15*0.6 + 30*0.3) / (0.6+0.3) = (9+9)/0.9 = 20
    store.update("ADBE Glow", "Intensity", 30, 0.3);
    assertApprox(store.get("ADBE Glow", "Intensity") as number, 20, 0.001, "三次加权平均=20");
}

function testDefaultValueStoreGetAll() {
    console.log("\n[2.2] DefaultValueStore - getAll 按效果筛选");
    const store = new MemoryDefaultValueStore();
    store.update("ADBE Glow", "Intensity", 50, 0.3);
    store.update("ADBE Glow", "Radius", 10, 0.3);
    store.update("ADBE Blur", "Blurriness", 5, 0.3);

    const glowAll = store.getAll("ADBE Glow");
    assert(Object.keys(glowAll).length === 2, "Glow有2个参数");
    assert(glowAll["Intensity"] === 50, "Glow.Intensity=50");
    assert(glowAll["Radius"] === 10, "Glow.Radius=10");
}

// ============================================================================
// 3. ResultVerifier 测试
// ============================================================================

class MockMcpClientWithProps implements McpClient {
    private props: ActualProperty[];
    constructor(props: ActualProperty[]) { this.props = props; }
    async getEffectProperties(): Promise<ActualProperty[] | null> { return this.props; }
}

async function testResultVerifierPass() {
    console.log("\n[3.1] ResultVerifier - 参数完全匹配");
    const mcpClient = new MockMcpClientWithProps([
        { name: "Blurriness", value: 10 },
        { name: "Blur Dimensions", value: 1 },
    ]);
    const verifier = new ResultVerifier(mcpClient);
    const result = await verifier.verify(makeExpected(), makeExecution());
    assert(result.passed === true, "验证通过");
    assert(result.mismatches.length === 0, "无不匹配");
    assertApprox(result.deviationScore, 0, 0.001, "偏差度=0");
}

async function testResultVerifierMismatch() {
    console.log("\n[3.2] ResultVerifier - 参数不匹配");
    const mcpClient = new MockMcpClientWithProps([
        { name: "Blurriness", value: 15 },  // 预期10，实际15
        { name: "Blur Dimensions", value: 1 },
    ]);
    const verifier = new ResultVerifier(mcpClient, 0.01);
    const result = await verifier.verify(makeExpected(), makeExecution());
    assert(result.passed === false, "验证不通过");
    assert(result.mismatches.length === 1, "1个不匹配");
    assert(result.mismatches[0].param === "Blurriness", "不匹配参数=Blurriness");
    assert(result.deviationScore > 0, "偏差度>0");
}

async function testResultVerifierExecutionFailed() {
    console.log("\n[3.3] ResultVerifier - 执行失败直接不通过");
    const verifier = new ResultVerifier(new MockMcpClient());
    const result = await verifier.verify(makeExpected(), makeExecution({ success: false, errorCode: "E300" }));
    assert(result.passed === false, "执行失败→验证不通过");
    assertApprox(result.deviationScore, 1.0, 0.001, "偏差度=1.0");
}

async function testResultVerifierMcpUnavailable() {
    console.log("\n[3.4] ResultVerifier - MCP不可用时降级");
    const verifier = new ResultVerifier(new MockMcpClient());  // 返回 null
    const result = await verifier.verify(makeExpected(), makeExecution());
    assert(result.passed === true, "MCP不可用→执行成功即通过");
    assert(result.reason?.includes("无法回读") === true, "原因说明MCP不可用");
}

// ============================================================================
// 4. FailureRecovery 测试
// ============================================================================

async function testFailureRecoveryEffectNotFound() {
    console.log("\n[4.1] FailureRecovery - 效果未找到");
    const recovery = new FailureRecovery();
    const execution = makeExecution({ success: false, errorCode: ErrorCode.EFFECT_NOT_FOUND });
    const action = await recovery.handleFailure(execution, makeExpected());
    // 可能找到替代或ask_user
    assert(["retry_with_alternative", "ask_user"].includes(action.action),
        `效果未找到→策略=${action.action}`);
}

async function testFailureRecoveryTimeout() {
    console.log("\n[4.2] FailureRecovery - 超时重试");
    const recovery = new FailureRecovery({ defaultTimeout: 10000, timeoutBackoffFactor: 1.5 });
    const execution = makeExecution({ success: false, errorCode: ErrorCode.EXECUTION_TIMEOUT });
    const action = await recovery.handleFailure(execution, makeExpected());
    assert(action.action === "retry_with_longer_timeout", "超时→延展超时重试");
    assert(action.timeout === 15000, `新超时=${action.timeout}ms (10000*1.5)`);
}

async function testFailureRecoveryBridgeOffline() {
    console.log("\n[4.3] FailureRecovery - Bridge离线索引退避");
    const recovery = new FailureRecovery({ initialRetryDelay: 3000, retryBackoffFactor: 2.0 });
    const execution = makeExecution({ success: false, errorCode: ErrorCode.BRIDGE_OFFLINE });

    const action1 = await recovery.handleFailure(execution, makeExpected(), "req1");
    assert(action1.action === "wait_and_retry", "Bridge离线→等待重试");
    assert(action1.delay === 3000, "首次延迟=3000ms");

    const action2 = await recovery.handleFailure(execution, makeExpected(), "req1");
    assert(action2.delay === 6000, "二次延迟=6000ms（指数退避）");
}

async function testFailureRecoveryMaxRetries() {
    console.log("\n[4.4] FailureRecovery - 超过最大重试次数");
    const recovery = new FailureRecovery({ maxRetries: 2 });
    const execution = makeExecution({ success: false, errorCode: ErrorCode.BRIDGE_OFFLINE });

    await recovery.handleFailure(execution, makeExpected(), "reqX");
    await recovery.handleFailure(execution, makeExpected(), "reqX");
    const action3 = await recovery.handleFailure(execution, makeExpected(), "reqX");
    assert(action3.action === "ask_user", "超过重试→ask_user");
    assert(action3.message?.includes("最大重试次数") === true, "消息包含重试上限说明");
}

async function testFailureRecoveryParamOutOfRange() {
    console.log("\n[4.5] FailureRecovery - 参数超出范围自动衰减");
    const recovery = new FailureRecovery();
    const execution = makeExecution({ success: false, errorCode: ErrorCode.PARAM_OUT_OF_RANGE });
    const expected = makeExpected({ properties: [{ name: "Intensity", value: 100 }] });
    const action = await recovery.handleFailure(execution, expected);
    assert(action.action === "retry_with_adjusted_params", "参数超范围→调整参数重试");
    assert(action.adjustedParams?.properties[0].value === 90, "100*0.9=90 衰减");
}

// ============================================================================
// 5. RetryCounter 测试
// ============================================================================

function testRetryCounter() {
    console.log("\n[5.1] RetryCounter - 重试控制");
    const counter = new RetryCounter(3, 5);
    assert(counter.canRetry("r1") === true, "初始可重试");
    assert(counter.getCount("r1") === 0, "初始计数=0");

    counter.increment("r1");
    counter.increment("r1");
    counter.increment("r1");
    assert(counter.getCount("r1") === 3, "3次后计数=3");
    assert(counter.canRetry("r1") === false, "达到maxRetries=3后不可重试");

    counter.reset("r1");
    assert(counter.canRetry("r1") === true, "重置后可重试");
    assert(counter.getCount("r1") === 0, "重置后计数=0");
}

// ============================================================================
// 6. PersistentLearningLoop 持久化测试
// ============================================================================

function testPersistentLearningLoop() {
    console.log("\n[6.1] PersistentLearningLoop - 持久化存储");
    // 使用临时目录避免污染真实状态
    const tmpDir = path.join(os.tmpdir(), `phase5_test_${Date.now()}`);
    fs.mkdirSync(tmpDir, { recursive: true });

    // 自定义 storage 使用临时目录
    const tmpStorage = {
        load<T>(filePath: string, defaultValue: T): T {
            const tmpPath = path.join(tmpDir, path.basename(filePath));
            try {
                if (!fs.existsSync(tmpPath)) return defaultValue;
                return JSON.parse(fs.readFileSync(tmpPath, "utf-8")) as T;
            } catch { return defaultValue; }
        },
        save<T>(filePath: string, data: T): void {
            const tmpPath = path.join(tmpDir, path.basename(filePath));
            fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), "utf-8");
        }
    };

    const loop = new PersistentLearningLoop(undefined, undefined, undefined, tmpStorage);

    // 记录成功执行
    loop.recordExecution("加个模糊", "add_effect", makeExpected(), makeExecution(), makeVerification(),
        { satisfied: true }, ["nlu:add_effect"]);

    const metrics = loop.getMetrics();
    assert(metrics.totalExecutions === 1, "持久化循环记录1次");
    assert(metrics.learnedTemplates === 1, "持久化学习模板=1");

    // 验证文件已写入
    const recordsFile = path.join(tmpDir, "execution-records.json");
    assert(fs.existsSync(recordsFile), "执行记录文件已持久化");

    // 清理
    fs.rmSync(tmpDir, { recursive: true, force: true });
}

// ============================================================================
// 7. LearningMetrics 准确率提升计算
// ============================================================================

function testAccuracyImprovement() {
    console.log("\n[7.1] LearningMetrics - 准确率提升计算");
    const loop = new LearningLoop();

    // 前4次失败
    for (let i = 0; i < 4; i++) {
        loop.recordExecution(`输入${i}`, "add_effect", makeExpected(),
            makeExecution({ success: false, errorCode: "E300" }),
            makeVerification({ passed: false, deviationScore: 1 }));
    }
    // 后4次成功
    for (let i = 0; i < 4; i++) {
        loop.recordExecution(`输入${i + 4}`, "add_effect", makeExpected(),
            makeExecution(), makeVerification(), { satisfied: true });
    }

    const metrics = loop.getMetrics();
    assert(metrics.totalExecutions === 8, "总执行=8");
    assert(metrics.successCount === 4, "成功=4");
    assert(metrics.failureCount === 4, "失败=4");
    assertApprox(metrics.successRate, 0.5, 0.001, "成功率=0.5");
    // 后半（最近4次）全部成功 vs 前半全部失败 → improvement = 1.0 - 0.0 = 1.0
    assertApprox(metrics.accuracyImprovement, 1.0, 0.001, "准确率提升=1.0");
}

// ============================================================================
// 8. CaseStore 模板排序
// ============================================================================

function testCaseStoreSorting() {
    console.log("\n[8.1] CaseStore - 按使用次数排序");
    const store = new MemoryCaseStore();
    store.addTemplate({
        id: "t1", source: "auto-learned", effectMatchName: "ADBE Glow",
        effectName: "Glow", parameters: {}, userRating: "positive",
        usageCount: 5, lastUsed: "2026-01-01"
    });
    store.addTemplate({
        id: "t2", source: "auto-learned", effectMatchName: "ADBE Glow",
        effectName: "Glow", parameters: {}, userRating: "positive",
        usageCount: 10, lastUsed: "2026-01-02"
    });

    const found = store.findTemplates("ADBE Glow");
    assert(found.length === 2, "找到2个Glow模板");
    assert(found[0].id === "t2", "使用次数多的排前面(t2)");
    assert(found[1].id === "t1", "使用次数少的排后面(t1)");

    store.incrementUsage("t1");
    const found2 = store.findTemplates("ADBE Glow");
    assert(found2[0].id === "t2", "incrementUsage后t2仍排前(10>6)");
}

// ============================================================================
// 主入口
// ============================================================================

async function main() {
    console.log("=".repeat(60));
    console.log("Phase 5 学习机器正确性测试");
    console.log("=".repeat(60));

    // 1. LearningLoop
    testLearningLoopSuccess();
    testLearningLoopDeviation();
    testLearningLoopFailure();
    testLearningLoopExecutionFailure();

    // 2. DefaultValueStore
    testDefaultValueStoreWeightedAverage();
    testDefaultValueStoreGetAll();

    // 3. ResultVerifier
    await testResultVerifierPass();
    await testResultVerifierMismatch();
    await testResultVerifierExecutionFailed();
    await testResultVerifierMcpUnavailable();

    // 4. FailureRecovery
    await testFailureRecoveryEffectNotFound();
    await testFailureRecoveryTimeout();
    await testFailureRecoveryBridgeOffline();
    await testFailureRecoveryMaxRetries();
    await testFailureRecoveryParamOutOfRange();

    // 5. RetryCounter
    testRetryCounter();

    // 6. PersistentLearningLoop
    testPersistentLearningLoop();

    // 7. Metrics
    testAccuracyImprovement();

    // 8. CaseStore
    testCaseStoreSorting();

    // 汇总
    console.log("\n" + "=".repeat(60));
    console.log(`结果: ${passed} passed, ${failed} failed, 共 ${passed + failed} 项`);
    if (failures.length > 0) {
        console.log("\n失败项:");
        for (const f of failures) console.log(`  ❌ ${f}`);
    }
    console.log("=".repeat(60));

    process.exit(failed > 0 ? 1 : 0);
}

main().catch(e => {
    console.error("测试执行异常:", e);
    process.exit(1);
});
