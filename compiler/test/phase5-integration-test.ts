// ============================================================================
// phase5-integration-test.ts
// Phase 5 端到端集成测试
//
// 测试覆盖：
//   1. ResultVerifier - 执行结果验证器
//   2. LearningLoop - 学习循环
//   3. FailureRecovery - 失败恢复策略
//   4. FeedbackPipeline - 完整反馈闭环
//
// 运行：node build/phase5-integration-test.js
// ============================================================================

import {
    ResultVerifier,
    MockMcpClient,
    LearningLoop,
    MemoryCaseStore,
    MemoryDefaultValueStore,
    FailureRecovery,
    RetryCounter,
    ErrorCode,
    FeedbackPipeline,
    feedbackPipeline,
    verifyExecution,
    recordExecution,
    handleFailure,
    processExecution,
    getMetrics,
    getPhase5Info,
    type ExecutionResult,
    type ExpectedParameters,
    type ActualProperty,
    type UserFeedback,
} from "../src/phase5";

// ============================================================================
// 测试工具
// ============================================================================

let passed = 0;
let failed = 0;

function assert(condition: boolean, message: string): void {
    if (condition) {
        passed++;
        console.log(`  ✓ ${message}`);
    } else {
        failed++;
        console.error(`  ✗ ${message}`);
    }
}

function assertEqual(actual: any, expected: any, message: string): void {
    const equal = JSON.stringify(actual) === JSON.stringify(expected);
    if (equal) {
        passed++;
        console.log(`  ✓ ${message}`);
    } else {
        failed++;
        console.error(`  ✗ ${message}`);
        console.error(`    expected: ${JSON.stringify(expected)}`);
        console.error(`    actual:   ${JSON.stringify(actual)}`);
    }
}

function section(name: string): void {
    console.log(`\n──────────────────────────────────────────`);
    console.log(` ${name}`);
    console.log(`──────────────────────────────────────────`);
}

// ============================================================================
// 测试用例
// ============================================================================

async function runTests(): Promise<void> {
    console.log("========================================");
    console.log(" Phase 5 端到端集成测试");
    console.log(" 执行结果验证 → 学习循环 → 失败恢复 → 完整闭环");
    console.log("========================================\n");

    // 显示模块信息
    const info = getPhase5Info();
    console.log(`[信息] ${info.name} v${info.version}`);
    console.log(`[信息] 组件: ${info.components.join(", ")}`);
    console.log(`[信息] 描述: ${info.description}\n`);

    // ==========================================================================
    // 1. ResultVerifier 测试
    // ==========================================================================
    section("1. ResultVerifier 测试");

    // 测试1.1: 执行失败 → 验证不通过
    {
        const verifier = new ResultVerifier();
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = {
            success: false,
            errorCode: "E300",
            errorMessage: "Effect not found",
        };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === false, "执行失败时验证不通过");
        assert(result.deviationScore === 1.0, "执行失败的偏差度为 1.0");
        assert(result.reason?.includes("执行失败") === true, "失败原因包含'执行失败'");
    }

    // 测试1.2: 执行成功但 MCP 不可用（MockMcpClient 返回 null）
    {
        const verifier = new ResultVerifier(); // 默认使用 MockMcpClient
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === true, "MCP 不可用时执行成功则验证通过");
        assert(result.deviationScore === 0, "MCP 不可用时偏差度为 0");
        assert(result.reason?.includes("MCP 不可用") === true, "原因包含'MCP 不可用'");
    }

    // 测试1.3: 执行成功 + 参数匹配
    {
        // 自定义 McpClient，返回匹配的参数
        const mcpClient: MockMcpClient = new MockMcpClient();
        (mcpClient as any).getEffectProperties = async (): Promise<ActualProperty[]> => [
            { name: "Blurriness", value: 25, type: "number" },
        ];
        const verifier = new ResultVerifier(mcpClient);
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === true, "参数完全匹配时验证通过");
        assert(result.mismatches.length === 0, "不匹配参数列表为空");
        assert(result.deviationScore === 0, "完全匹配时偏差度为 0");
    }

    // 测试1.4: 执行成功 + 参数不匹配
    {
        const mcpClient = new MockMcpClient();
        (mcpClient as any).getEffectProperties = async (): Promise<ActualProperty[]> => [
            { name: "Blurriness", value: 30, type: "number" }, // 预期 25
        ];
        const verifier = new ResultVerifier(mcpClient, 0.01); // 容差 0.01
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === false, "参数不匹配时验证不通过");
        assert(result.mismatches.length === 1, "记录 1 个不匹配参数");
        assertEqual(result.mismatches[0].param, "Blurriness", "不匹配参数名正确");
        assertEqual(result.mismatches[0].expected, 25, "预期值正确");
        assertEqual(result.mismatches[0].actual, 30, "实际值正确");
        assert(result.deviationScore > 0, "不匹配时偏差度 > 0");
    }

    // 测试1.5: 容差内匹配
    {
        const mcpClient = new MockMcpClient();
        (mcpClient as any).getEffectProperties = async (): Promise<ActualProperty[]> => [
            { name: "Blurriness", value: 25.005, type: "number" }, // 在容差 0.01 内
        ];
        const verifier = new ResultVerifier(mcpClient, 0.01);
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === true, "容差内匹配时验证通过");
        assert(result.mismatches.length === 0, "容差内不算不匹配");
    }

    // 测试1.6: 数组值（颜色）匹配
    {
        const mcpClient = new MockMcpClient();
        (mcpClient as any).getEffectProperties = async (): Promise<ActualProperty[]> => [
            { name: "Color", value: [1, 0.5, 0.3], type: "color" },
        ];
        const verifier = new ResultVerifier(mcpClient, 0.01);
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Color", value: [1, 0.5, 0.3] }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === true, "数组值（颜色）匹配时验证通过");
    }

    // 测试1.7: 实际参数缺失
    {
        const mcpClient = new MockMcpClient();
        (mcpClient as any).getEffectProperties = async (): Promise<ActualProperty[]> => [
            { name: "OtherParam", value: 10, type: "number" },
        ];
        const verifier = new ResultVerifier(mcpClient);
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const actual: ExecutionResult = { success: true };
        const result = await verifier.verify(expected, actual);
        assert(result.passed === false, "实际参数缺失时验证不通过");
        assertEqual(result.mismatches[0].actual, null, "缺失参数的 actual 为 null");
    }

    // ==========================================================================
    // 2. LearningLoop 测试
    // ==========================================================================
    section("2. LearningLoop 测试");

    // 测试2.1: 正向学习（用户满意）→ 添加模板
    {
        const learner = new LearningLoop();
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [
                { name: "Blurriness", value: 25 },
                { name: "Blur Dimensions", value: 1 },
            ],
        };
        const execution: ExecutionResult = {
            success: true,
            effectName: "Gaussian Blur",
        };
        const verification = { passed: true, mismatches: [], deviationScore: 0 };
        const record = learner.recordExecution(
            "加个高斯模糊",
            "INTENT_ADD_EFFECT",
            expected,
            execution,
            verification,
            { satisfied: true },
            ["VT-001→Gaussian Blur"],
        );
        assert(record.userSatisfied === true, "记录用户满意状态");
        const templates = learner.getCaseStore().findTemplates("ADBE Gaussian Blur 2");
        assert(templates.length === 1, "正向学习添加 1 个模板");
        assertEqual(templates[0].parameters["Blurriness"], 25, "模板参数值正确");
        assertEqual(templates[0].userRating, "positive", "模板评级为 positive");

        const adjustments = learner.getConfidenceAdjustments();
        assert(adjustments.length === 1, "生成 1 个置信度调整");
        assertEqual(adjustments[0].direction, "boost", "正向学习为 boost");
    }

    // 测试2.2: 偏差学习（用户调整参数）→ 更新默认值
    {
        const learner = new LearningLoop();
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const execution: ExecutionResult = { success: true, effectName: "Gaussian Blur" };
        const verification = { passed: false, mismatches: [], deviationScore: 0.2 };
        const record = learner.recordExecution(
            "加个高斯模糊",
            "INTENT_ADD_EFFECT",
            expected,
            execution,
            verification,
            {
                adjusted: true,
                finalParams: [{ name: "Blurriness", value: 35 }],
            },
            ["VT-001→Gaussian Blur"],
        );
        assert(record.userAdjusted === true, "记录用户调整状态");

        const defaults = learner.getDefaultValueStore().getAll("ADBE Gaussian Blur 2");
        assertEqual(defaults["Blurriness"], 35, "默认值更新为用户调整后的值");
    }

    // 测试2.3: 负向学习（用户撤销）→ 降低置信度
    {
        const learner = new LearningLoop();
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const execution: ExecutionResult = { success: true, effectName: "Gaussian Blur" };
        const verification = { passed: true, mismatches: [], deviationScore: 0 };
        const record = learner.recordExecution(
            "加个高斯模糊",
            "INTENT_ADD_EFFECT",
            expected,
            execution,
            verification,
            { undone: true },
            ["VT-001→Gaussian Blur"],
        );
        assert(record.userUndone === true, "记录用户撤销状态");

        const adjustments = learner.getConfidenceAdjustments();
        assert(adjustments.length === 1, "生成 1 个置信度调整");
        assertEqual(adjustments[0].direction, "penalize", "负向学习为 penalize");
    }

    // 测试2.4: 执行失败 → 负向学习
    {
        const learner = new LearningLoop();
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const execution: ExecutionResult = {
            success: false,
            errorCode: "E300",
            errorMessage: "Effect not found",
        };
        const verification = { passed: false, mismatches: [], deviationScore: 1.0 };
        learner.recordExecution(
            "加个高斯模糊",
            "INTENT_ADD_EFFECT",
            expected,
            execution,
            verification,
            undefined,
            ["VT-001→Gaussian Blur"],
        );
        const adjustments = learner.getConfidenceAdjustments();
        assert(adjustments.length === 1, "执行失败时也生成置信度调整");
        assertEqual(adjustments[0].direction, "penalize", "执行失败为 penalize");
    }

    // 测试2.5: 学习度量计算
    {
        const learner = new LearningLoop();
        // 执行 3 次成功 + 1 次失败
        for (let i = 0; i < 3; i++) {
            learner.recordExecution(
                "测试输入",
                "INTENT_ADD_EFFECT",
                {
                    compName: "Comp 1",
                    layerIndex: 1,
                    effectMatchName: "ADBE Gaussian Blur 2",
                    effectName: "Gaussian Blur",
                    properties: [{ name: "Blurriness", value: 25 }],
                },
                { success: true, effectName: "Gaussian Blur" },
                { passed: true, mismatches: [], deviationScore: 0 },
                { satisfied: true },
            );
        }
        learner.recordExecution(
            "测试输入",
            "INTENT_ADD_EFFECT",
            {
                compName: "Comp 1",
                layerIndex: 1,
                effectMatchName: "ADBE Gaussian Blur 2",
                properties: [{ name: "Blurriness", value: 25 }],
            },
            { success: false, errorCode: "E300" },
            { passed: false, mismatches: [], deviationScore: 1.0 },
        );

        const metrics = learner.getMetrics();
        assertEqual(metrics.totalExecutions, 4, "总执行次数为 4");
        assertEqual(metrics.successCount, 3, "成功次数为 3");
        assertEqual(metrics.failureCount, 1, "失败次数为 1");
        assert(metrics.successRate === 0.75, "成功率为 0.75");
        assertEqual(metrics.learnedTemplates, 3, "学习到 3 个模板");
    }

    // 测试2.6: 模板使用次数递增
    {
        const caseStore = new MemoryCaseStore();
        const learner = new LearningLoop(caseStore);
        // 第一次执行：添加模板
        learner.recordExecution(
            "输入1",
            "INTENT_ADD_EFFECT",
            {
                compName: "Comp 1",
                layerIndex: 1,
                effectMatchName: "ADBE Gaussian Blur 2",
                effectName: "Gaussian Blur",
                properties: [{ name: "Blurriness", value: 25 }],
            },
            { success: true, effectName: "Gaussian Blur" },
            { passed: true, mismatches: [], deviationScore: 0 },
            { satisfied: true },
        );
        const templates = caseStore.findTemplates("ADBE Gaussian Blur 2");
        assertEqual(templates[0].usageCount, 1, "首次添加模板 usageCount=1");
    }

    // ==========================================================================
    // 3. FailureRecovery 测试
    // ==========================================================================
    section("3. FailureRecovery 测试");

    // 测试3.1: EFFECT_NOT_FOUND → retry_with_alternative
    {
        const recovery = new FailureRecovery();
        const execution: ExecutionResult = {
            success: false,
            errorCode: ErrorCode.EFFECT_NOT_FOUND,
            errorMessage: "Effect not installed",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const action = await recovery.handleFailure(execution, expected, "req-1");
        assertEqual(action.action, "retry_with_alternative", "EFFECT_NOT_FOUND → retry_with_alternative");
        assert(action.alternative !== undefined, "提供替代效果");
        assert(action.alternative !== "ADBE Gaussian Blur 2", "替代效果不同于原效果");
    }

    // 测试3.2: PARAM_OUT_OF_RANGE → retry_with_adjusted_params
    {
        const recovery = new FailureRecovery();
        const execution: ExecutionResult = {
            success: false,
            errorCode: ErrorCode.PARAM_OUT_OF_RANGE,
            errorMessage: "Value out of range",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            properties: [{ name: "Blurriness", value: 100 }],
        };
        const action = await recovery.handleFailure(execution, expected, "req-2");
        assertEqual(action.action, "retry_with_adjusted_params", "PARAM_OUT_OF_RANGE → retry_with_adjusted_params");
        assert(action.adjustedParams !== undefined, "提供调整后参数");
        const adjusted = action.adjustedParams!.properties[0].value as number;
        assert(adjusted === 90, "数值参数被衰减到 90%（100×0.9）");
    }

    // 测试3.3: EXECUTION_TIMEOUT → retry_with_longer_timeout
    {
        const recovery = new FailureRecovery({ defaultTimeout: 10000, timeoutBackoffFactor: 1.5 });
        const execution: ExecutionResult = {
            success: false,
            errorCode: ErrorCode.EXECUTION_TIMEOUT,
            errorMessage: "Execution timed out",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [],
        };
        const action = await recovery.handleFailure(execution, expected, "req-3");
        assertEqual(action.action, "retry_with_longer_timeout", "EXECUTION_TIMEOUT → retry_with_longer_timeout");
        assert(action.timeout === 15000, "超时延展到 15000ms（10000×1.5）");
    }

    // 测试3.4: BRIDGE_OFFLINE → wait_and_retry（指数退避）
    {
        const recovery = new FailureRecovery({ initialRetryDelay: 1000, retryBackoffFactor: 2.0 });
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [],
        };

        // 第一次失败
        const action1 = await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.BRIDGE_OFFLINE, errorMessage: "Bridge offline" },
            expected,
            "req-4",
        );
        assertEqual(action1.action, "wait_and_retry", "BRIDGE_OFFLINE → wait_and_retry");
        assert(action1.delay === 1000, "第一次延迟 1000ms");

        // 第二次失败
        const action2 = await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.BRIDGE_OFFLINE, errorMessage: "Bridge offline" },
            expected,
            "req-4",
        );
        assert(action2.delay === 2000, "第二次延迟 2000ms（指数退避）");

        // 第三次失败
        const action3 = await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.BRIDGE_OFFLINE, errorMessage: "Bridge offline" },
            expected,
            "req-4",
        );
        assert(action3.delay === 4000, "第三次延迟 4000ms（指数退避）");
    }

    // 测试3.5: 达到最大重试次数 → ask_user
    {
        const recovery = new FailureRecovery({ maxRetries: 2 });
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [],
        };

        // 重试 2 次
        await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.EXECUTION_TIMEOUT },
            expected,
            "req-5",
        );
        await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.EXECUTION_TIMEOUT },
            expected,
            "req-5",
        );

        // 第三次应该升级为 ask_user
        const action = await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.EXECUTION_TIMEOUT },
            expected,
            "req-5",
        );
        assertEqual(action.action, "ask_user", "达到最大重试次数 → ask_user");
        assert(action.message?.includes("最大重试次数") === true, "消息包含'最大重试次数'");
    }

    // 测试3.6: 未知错误码 → report_error
    {
        const recovery = new FailureRecovery();
        const action = await recovery.handleFailure(
            { success: false, errorCode: "E999", errorMessage: "Unknown error" },
            { compName: "Comp 1", layerIndex: 1, properties: [] },
            "req-6",
        );
        assertEqual(action.action, "report_error", "未知错误码 → report_error");
    }

    // 测试3.7: KEYFRAME_FAILED → report_error
    {
        const recovery = new FailureRecovery();
        const action = await recovery.handleFailure(
            { success: false, errorCode: ErrorCode.KEYFRAME_FAILED, errorMessage: "Keyframe failed" },
            { compName: "Comp 1", layerIndex: 1, properties: [] },
            "req-7",
        );
        assertEqual(action.action, "report_error", "KEYFRAME_FAILED → report_error");
    }

    // 测试3.8: 执行成功后重置重试计数器
    {
        const recovery = new FailureRecovery();
        const counter = recovery.getRetryCounter();
        counter.increment("req-8");
        counter.increment("req-8");
        assertEqual(counter.getCount("req-8"), 2, "重试计数为 2");

        recovery.resetRetryCount("req-8");
        assertEqual(counter.getCount("req-8"), 0, "重置后计数为 0");
    }

    // 测试3.9: buildAdjustedParams 静态方法
    {
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            properties: [
                { name: "Blurriness", value: 25 },
                { name: "Color", value: [1, 0, 0] },
            ],
        };
        const mismatches = [
            { param: "Blurriness", expected: 25, actual: 30, deviation: 5 },
            { param: "Color", expected: [1, 0, 0], actual: [1, 0.5, 0], deviation: 0.17 },
        ];
        const adjusted = FailureRecovery.buildAdjustedParams(expected, mismatches);
        assertEqual(adjusted.properties[0].value, 30, "Blurriness 调整为实际值 30");
        assertEqual(adjusted.properties[1].value, [1, 0.5, 0], "Color 调整为实际值");
    }

    // 测试3.10: RetryCounter 单独测试
    {
        const counter = new RetryCounter(3, 5);
        assert(counter.canRetry("test") === true, "初始可重试");
        counter.increment("test");
        counter.increment("test");
        counter.increment("test");
        assert(counter.canRetry("test") === false, "达到 maxRetries 后不可重试");
        counter.reset("test");
        assert(counter.canRetry("test") === true, "重置后可重试");
    }

    // ==========================================================================
    // 4. FeedbackPipeline 完整闭环测试
    // ==========================================================================
    section("4. FeedbackPipeline 完整闭环测试");

    // 测试4.1: 端到端成功路径
    {
        const pipeline = new FeedbackPipeline();
        const execution: ExecutionResult = {
            success: true,
            effectName: "Gaussian Blur",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const outcome = await pipeline.processExecution(
            execution,
            expected,
            {
                userInput: "加个高斯模糊",
                intentType: "INTENT_ADD_EFFECT",
                reasoningPath: ["VT-001→Gaussian Blur"],
            },
            { satisfied: true },
        );
        assert(outcome.verification.passed === true, "端到端：验证通过");
        assert(outcome.suggestedAction === undefined, "成功时无恢复动作");
        assert(outcome.needsUserInput === false, "成功时无需用户介入");
        assert(outcome.knowledgeUpdates.length > 0, "生成知识库更新");
        const newTemplateUpdate = outcome.knowledgeUpdates.find((u) => u.type === "new_template");
        assert(newTemplateUpdate !== undefined, "包含新模板更新");
        assert(newTemplateUpdate?.documentName === "参数-效果原子级映射库", "更新到映射库文档");
    }

    // 测试4.2: 端到端失败路径
    {
        const pipeline = new FeedbackPipeline();
        const execution: ExecutionResult = {
            success: false,
            errorCode: ErrorCode.EFFECT_NOT_FOUND,
            errorMessage: "Effect not installed",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const outcome = await pipeline.processExecution(
            execution,
            expected,
            {
                userInput: "加个高斯模糊",
                intentType: "INTENT_ADD_EFFECT",
                reasoningPath: ["VT-001→Gaussian Blur"],
                requestId: "e2e-fail",
            },
        );
        assert(outcome.verification.passed === false, "端到端：验证不通过");
        assert(outcome.suggestedAction !== undefined, "失败时有恢复动作");
        assertEqual(outcome.suggestedAction!.action, "retry_with_alternative", "恢复动作为 retry_with_alternative");
        const failureCaseUpdate = outcome.knowledgeUpdates.find((u) => u.type === "failure_case");
        assert(failureCaseUpdate !== undefined, "包含失败案例更新");
    }

    // 测试4.3: 端到端用户调整路径
    {
        const pipeline = new FeedbackPipeline();
        const execution: ExecutionResult = {
            success: true,
            effectName: "Gaussian Blur",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            effectName: "Gaussian Blur",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const outcome = await pipeline.processExecution(
            execution,
            expected,
            {
                userInput: "加个高斯模糊",
                intentType: "INTENT_ADD_EFFECT",
                reasoningPath: ["VT-001→Gaussian Blur"],
            },
            {
                adjusted: true,
                finalParams: [{ name: "Blurriness", value: 35 }],
            },
        );
        assert(outcome.knowledgeUpdates.length > 0, "用户调整时也生成知识库更新");
        const adjustmentUpdate = outcome.knowledgeUpdates.find((u) => u.type === "parameter_adjustment");
        assert(adjustmentUpdate !== undefined, "包含参数调整更新");
        assert(adjustmentUpdate?.content.includes("25") === true, "调整内容包含预期值");
        assert(adjustmentUpdate?.content.includes("35") === true, "调整内容包含实际值");
    }

    // 测试4.4: 端到端用户撤销路径
    {
        const pipeline = new FeedbackPipeline();
        const execution: ExecutionResult = {
            success: true,
            effectName: "Gaussian Blur",
        };
        const expected: ExpectedParameters = {
            compName: "Comp 1",
            layerIndex: 1,
            effectMatchName: "ADBE Gaussian Blur 2",
            properties: [{ name: "Blurriness", value: 25 }],
        };
        const outcome = await pipeline.processExecution(
            execution,
            expected,
            {
                userInput: "加个高斯模糊",
                intentType: "INTENT_ADD_EFFECT",
                reasoningPath: ["VT-001→Gaussian Blur"],
            },
            { undone: true },
        );
        const failureCaseUpdate = outcome.knowledgeUpdates.find((u) => u.type === "failure_case");
        assert(failureCaseUpdate !== undefined, "用户撤销也生成失败案例");
        assert(failureCaseUpdate?.content.includes("用户撤销") === true, "失败案例包含'用户撤销'原因");
    }

    // 测试4.5: 学习度量端到端
    {
        const pipeline = new FeedbackPipeline();
        // 执行 2 次成功
        for (let i = 0; i < 2; i++) {
            await pipeline.processExecution(
                { success: true, effectName: "Glow" },
                {
                    compName: "Comp 1",
                    layerIndex: 1,
                    effectMatchName: "ADBE Glo2",
                    effectName: "Glow",
                    properties: [{ name: "Glow Intensity", value: 2 }],
                },
                {
                    userInput: "加个发光",
                    intentType: "INTENT_ADD_EFFECT",
                    reasoningPath: ["VT-010→Glow"],
                },
                { satisfied: true },
            );
        }
        const metrics = pipeline.getMetrics();
        assertEqual(metrics.totalExecutions, 2, "端到端：2 次执行");
        assertEqual(metrics.successCount, 2, "端到端：2 次成功");
        assertEqual(metrics.learnedTemplates, 2, "端到端：2 个学习模板");
    }

    // 测试4.6: 便捷函数
    {
        const result = await verifyExecution(
            { compName: "Comp 1", layerIndex: 1, properties: [] },
            { success: true },
        );
        assert(result.passed === true, "verifyExecution 便捷函数工作正常");

        const record = recordExecution(
            "测试",
            "INTENT_ADD_EFFECT",
            { compName: "Comp 1", layerIndex: 1, properties: [] },
            { success: true },
            { passed: true, mismatches: [], deviationScore: 0 },
        );
        assert(record.id.startsWith("exec_") === true, "recordExecution 便捷函数返回执行记录");

        const action = await handleFailure(
            { success: false, errorCode: ErrorCode.EXECUTION_TIMEOUT, errorMessage: "Timeout" },
            { compName: "Comp 1", layerIndex: 1, properties: [] },
        );
        assertEqual(action.action, "retry_with_longer_timeout", "handleFailure 便捷函数返回恢复动作");

        const metrics = getMetrics();
        assert(metrics.totalExecutions >= 0, "getMetrics 便捷函数返回度量");
    }

    // 测试4.7: 默认值建议查询
    {
        const pipeline = new FeedbackPipeline();
        // 用户调整后会有默认值更新
        await pipeline.processExecution(
            { success: true, effectName: "Gaussian Blur" },
            {
                compName: "Comp 1",
                layerIndex: 1,
                effectMatchName: "ADBE Gaussian Blur 2",
                effectName: "Gaussian Blur",
                properties: [{ name: "Blurriness", value: 25 }],
            },
            {
                userInput: "加个高斯模糊",
                intentType: "INTENT_ADD_EFFECT",
            },
            {
                adjusted: true,
                finalParams: [{ name: "Blurriness", value: 40 }],
            },
        );
        const defaults = pipeline.getDefaultValues("ADBE Gaussian Blur 2");
        assertEqual(defaults["Blurriness"], 40, "默认值建议为用户调整后的值 40");
    }

    // 测试4.8: 模板查询
    {
        const pipeline = new FeedbackPipeline();
        await pipeline.processExecution(
            { success: true, effectName: "Glow" },
            {
                compName: "Comp 1",
                layerIndex: 1,
                effectMatchName: "ADBE Glo2",
                effectName: "Glow",
                properties: [{ name: "Glow Intensity", value: 3 }],
            },
            {
                userInput: "加个暖色发光",
                intentType: "INTENT_ADD_EFFECT",
                reasoningPath: ["VT-010→Glow"],
            },
            { satisfied: true },
        );
        const templates = pipeline.findTemplates("ADBE Glo2");
        assert(templates.length === 1, "查询到 1 个 Glow 模板");
        assertEqual(templates[0].parameters["Glow Intensity"], 3, "模板参数正确");
    }

    // ==========================================================================
    // 测试总结
    // ==========================================================================
    console.log("\n========================================");
    console.log(" 测试总结");
    console.log("========================================");
    console.log(` 通过: ${passed}`);
    console.log(` 失败: ${failed}`);
    console.log(` 总计: ${passed + failed}`);
    console.log(` 结果: ${failed === 0 ? "✓ 全部通过" : "✗ 有失败用例"}`);

    if (failed > 0) {
        process.exit(1);
    }
}

// 运行测试
runTests().catch((err) => {
    console.error("测试运行出错:", err);
    process.exit(1);
});
