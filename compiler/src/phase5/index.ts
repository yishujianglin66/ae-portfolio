// ============================================================================
// phase5/index.ts
// Phase 5 - 执行结果反馈闭环入口
//
// 整合三个核心组件：
//   1. ResultVerifier   - 验证执行结果是否匹配预期
//   2. LearningLoop     - 从执行结果中学习，更新参数模板和默认值
//   3. FailureRecovery  - 处理执行失败，选择恢复策略
//
// 完整闭环流程：
//   执行结果 ──▶ ResultVerifier.verify() ──▶ VerificationResult
//                                              │
//                                              ├─ 通过 ─▶ LearningLoop.recordExecution(成功)
//                                              │              ├─ 添加模板
//                                              │              └─ 提升置信度
//                                              │
//                                              ├─ 微调 ─▶ LearningLoop.recordExecution(调整)
//                                              │              └─ 更新默认值
//                                              │
//                                              └─ 失败 ─▶ FailureRecovery.handleFailure()
//                                                          ├─ retry_with_alternative
//                                                          ├─ retry_with_adjusted_params
//                                                          ├─ retry_with_longer_timeout
//                                                          ├─ wait_and_retry
//                                                          ├─ ask_user
//                                                          └─ report_error
//
// 对应架构设计文档 第十章 10.5 Phase 5：反馈闭环
// ============================================================================

import {
    ExecutionResult,
    ExpectedParameters,
    VerificationResult,
    ExecutionRecord,
    ParameterTemplate,
    ConfidenceAdjustment,
    LearningMetrics,
    KnowledgeUpdate,
    RecoveryAction,
    RecoveryActionType,
    ActualProperty,
    ParameterMismatch,
} from "./types";
import { ResultVerifier, McpClient, MockMcpClient, resultVerifier } from "./result-verifier";
import {
    LearningLoop,
    CaseStore,
    MemoryCaseStore,
    DefaultValueStore,
    MemoryDefaultValueStore,
    learningLoop,
} from "./learning-loop";
import {
    FailureRecovery,
    FailureRecoveryOptions,
    RetryCounter,
    ErrorCode,
    failureRecovery,
} from "./failure-recovery";

// ============================================================================
// 反馈闭环管线
// ============================================================================

/**
 * 反馈闭环执行上下文
 */
export interface FeedbackContext {
    /** 原始用户输入（自然语言） */
    userInput: string;
    /** 识别的意图类型 */
    intentType: string;
    /** 推理路径（用于置信度调整） */
    reasoningPath?: string[];
    /** 请求ID（用于失败重试计数） */
    requestId?: string;
}

/**
 * 反馈闭环执行结果
 *
 * 包含完整的执行记录和后续建议动作
 */
export interface FeedbackOutcome {
    /** 执行记录（已写入学习循环） */
    record: ExecutionRecord;
    /** 验证结果 */
    verification: VerificationResult;
    /** 后续建议动作（失败时为恢复动作，成功时为 undefined） */
    suggestedAction?: RecoveryAction;
    /** 是否需要用户介入 */
    needsUserInput: boolean;
    /** 知识库更新条目（如果有） */
    knowledgeUpdates: KnowledgeUpdate[];
}

/**
 * 用户反馈
 */
export interface UserFeedback {
    /** 用户是否满意 */
    satisfied?: boolean;
    /** 用户是否调整了参数 */
    adjusted?: boolean;
    /** 用户是否撤销了操作 */
    undone?: boolean;
    /** 用户最终采用的参数（如果调整过） */
    finalParams?: Array<{ name: string; value: number | string | boolean | number[] }>;
}

/**
 * 反馈闭环管线
 *
 * 整合 ResultVerifier + LearningLoop + FailureRecovery
 */
export class FeedbackPipeline {
    private verifier: ResultVerifier;
    private learner: LearningLoop;
    private recovery: FailureRecovery;

    constructor(
        verifier?: ResultVerifier,
        learner?: LearningLoop,
        recovery?: FailureRecovery,
    ) {
        this.verifier = verifier || new ResultVerifier();
        this.learner = learner || new LearningLoop();
        this.recovery = recovery || new FailureRecovery();
    }

    /**
     * 设置 MCP 客户端（用于真实执行结果回读）
     */
    setMcpClient(client: McpClient): void {
        this.verifier.setMcpClient(client);
    }

    /**
     * 处理执行结果（完整闭环入口）
     *
     * @param execution 执行结果
     * @param expected 预期参数
     * @param context 反馈上下文
     * @param userFeedback 用户反馈（可选）
     */
    async processExecution(
        execution: ExecutionResult,
        expected: ExpectedParameters,
        context: FeedbackContext,
        userFeedback?: UserFeedback,
    ): Promise<FeedbackOutcome> {
        // 步骤1：验证执行结果
        const verification = await this.verifier.verify(expected, execution);

        // 步骤2：记录到学习循环
        const record = this.learner.recordExecution(
            context.userInput,
            context.intentType,
            expected,
            execution,
            verification,
            userFeedback,
            context.reasoningPath,
        );

        // 步骤3：处理失败（如果有）
        let suggestedAction: RecoveryAction | undefined;
        let needsUserInput = false;

        if (!execution.success) {
            suggestedAction = await this.recovery.handleFailure(
                execution,
                expected,
                context.requestId,
            );
            needsUserInput = suggestedAction.action === "ask_user";
        } else if (verification.mismatches.length > 0 && userFeedback?.adjusted) {
            // 用户调整了参数，构造"调整后参数"建议
            suggestedAction = {
                action: "retry_with_adjusted_params",
                adjustedParams: FailureRecovery.buildAdjustedParams(
                    expected,
                    verification.mismatches,
                ),
                message: `检测到 ${verification.mismatches.length} 个参数偏差，已构造调整后参数`,
            };
        }

        // 步骤4：生成知识库更新条目
        const knowledgeUpdates = this.generateKnowledgeUpdates(record, verification);

        // 步骤5：执行成功时重置重试计数器
        if (execution.success && context.requestId) {
            this.recovery.resetRetryCount(context.requestId);
        }

        return {
            record,
            verification,
            suggestedAction,
            needsUserInput,
            knowledgeUpdates,
        };
    }

    /**
     * 生成知识库更新条目
     *
     * 根据执行记录生成需要写入 Obsidian 的更新内容
     */
    private generateKnowledgeUpdates(
        record: ExecutionRecord,
        verification: VerificationResult,
    ): KnowledgeUpdate[] {
        const updates: KnowledgeUpdate[] = [];
        const timestamp = new Date().toISOString();

        // 1. 新模板（执行成功且通过验证）
        if (record.execution.success && verification.passed && record.expected.effectMatchName) {
            const templateParams = record.expected.properties
                .map((p) => `- ${p.name}: \`${JSON.stringify(p.value)}\``)
                .join("\n");

            updates.push({
                type: "new_template",
                documentName: "参数-效果原子级映射库",
                content: `## 自动学习模板: ${record.execution.effectName || record.expected.effectName}\n\n- **效果matchName**: \`${record.expected.effectMatchName}\`\n- **来源输入**: "${record.userInput}"\n- **参数**:\n${templateParams}\n- **学习时间**: ${timestamp}\n- **执行记录ID**: ${record.id}\n`,
                timestamp,
                sourceRecordId: record.id,
            });
        }

        // 2. 参数调整（用户调整过）
        if (record.userAdjusted && record.finalParams && record.finalParams.length > 0) {
            const adjustments = record.finalParams
                .map((p) => {
                    const expected = record.expected.properties.find((ep) => ep.name === p.name);
                    const expectedVal = expected ? JSON.stringify(expected.value) : "N/A";
                    return `- ${p.name}: 预期=${expectedVal} → 实际=\`${JSON.stringify(p.value)}\``;
                })
                .join("\n");

            updates.push({
                type: "parameter_adjustment",
                documentName: "参数-效果原子级映射库",
                content: `## 参数偏差记录\n\n- **效果**: ${record.expected.effectName || record.expected.effectMatchName || "未知"}\n- **来源输入**: "${record.userInput}"\n- **调整详情**:\n${adjustments}\n- **记录时间**: ${timestamp}\n- **执行记录ID**: ${record.id}\n`,
                timestamp,
                sourceRecordId: record.id,
            });
        }

        // 3. 失败案例（执行失败或用户撤销）
        if (!record.execution.success || record.userUndone) {
            const reason = !record.execution.success
                ? `执行失败: ${record.execution.errorCode || "unknown"} - ${record.execution.errorMessage || ""}`
                : `用户撤销操作`;

            updates.push({
                type: "failure_case",
                documentName: "视频效果逆向分析系统方法论",
                content: `## 失败案例\n\n- **意图类型**: ${record.intentType}\n- **来源输入**: "${record.userInput}"\n- **失败原因**: ${reason}\n- **预期效果**: ${record.expected.effectName || record.expected.effectMatchName || "未知"}\n- **记录时间**: ${timestamp}\n- **执行记录ID**: ${record.id}\n`,
                timestamp,
                sourceRecordId: record.id,
            });
        }

        return updates;
    }

    /**
     * 获取学习度量（用于报告）
     */
    getMetrics(): LearningMetrics {
        return this.learner.getMetrics();
    }

    /**
     * 获取所有学习到的模板
     */
    getLearnedTemplates(): ParameterTemplate[] {
        return this.learner.getCaseStore().getAllTemplates();
    }

    /**
     * 查找指定效果的模板
     */
    findTemplates(effectMatchName: string): ParameterTemplate[] {
        return this.learner.getCaseStore().findTemplates(effectMatchName);
    }

    /**
     * 获取指定效果的当前默认值建议
     */
    getDefaultValues(effectMatchName: string): Record<string, number | string | boolean | number[]> {
        return this.learner.getDefaultValueStore().getAll(effectMatchName);
    }

    /**
     * 获取所有执行记录
     */
    getExecutionRecords(): ExecutionRecord[] {
        return this.learner.getExecutionRecords();
    }

    /**
     * 获取所有置信度调整
     */
    getConfidenceAdjustments(): ConfidenceAdjustment[] {
        return this.learner.getConfidenceAdjustments();
    }

    // 暴露内部组件（用于高级用法）
    getVerifier(): ResultVerifier { return this.verifier; }
    getLearner(): LearningLoop { return this.learner; }
    getRecovery(): FailureRecovery { return this.recovery; }
}

/**
 * 单例实例
 */
export const feedbackPipeline = new FeedbackPipeline();

// ============================================================================
// 便捷函数
// ============================================================================

/**
 * 验证执行结果（便捷函数）
 */
export async function verifyExecution(
    expected: ExpectedParameters,
    actual: ExecutionResult,
): Promise<VerificationResult> {
    return feedbackPipeline.getVerifier().verify(expected, actual);
}

/**
 * 记录执行结果到学习循环（便捷函数）
 */
export function recordExecution(
    userInput: string,
    intentType: string,
    expected: ExpectedParameters,
    execution: ExecutionResult,
    verification: VerificationResult,
    userFeedback?: UserFeedback,
    reasoningPath?: string[],
): ExecutionRecord {
    return feedbackPipeline.getLearner().recordExecution(
        userInput,
        intentType,
        expected,
        execution,
        verification,
        userFeedback,
        reasoningPath,
    );
}

/**
 * 处理执行失败（便捷函数）
 */
export async function handleFailure(
    execution: ExecutionResult,
    expected: ExpectedParameters,
    requestId?: string,
): Promise<RecoveryAction> {
    return feedbackPipeline.getRecovery().handleFailure(execution, expected, requestId);
}

/**
 * 完整反馈闭环（便捷函数）
 */
export async function processExecution(
    execution: ExecutionResult,
    expected: ExpectedParameters,
    context: FeedbackContext,
    userFeedback?: UserFeedback,
): Promise<FeedbackOutcome> {
    return feedbackPipeline.processExecution(execution, expected, context, userFeedback);
}

/**
 * 获取学习度量（便捷函数）
 */
export function getMetrics(): LearningMetrics {
    return feedbackPipeline.getMetrics();
}

// ============================================================================
// 类型导出
// ============================================================================

export type {
    ExecutionResult,
    ExpectedParameters,
    VerificationResult,
    ExecutionRecord,
    ParameterTemplate,
    ConfidenceAdjustment,
    LearningMetrics,
    KnowledgeUpdate,
    RecoveryAction,
    RecoveryActionType,
    ActualProperty,
    ParameterMismatch,
};

export {
    ResultVerifier,
    McpClient,
    MockMcpClient,
    resultVerifier,
    LearningLoop,
    CaseStore,
    MemoryCaseStore,
    DefaultValueStore,
    MemoryDefaultValueStore,
    learningLoop,
    FailureRecovery,
    FailureRecoveryOptions,
    RetryCounter,
    ErrorCode,
    failureRecovery,
    FeedbackContext,
    FeedbackOutcome,
    UserFeedback,
};

/**
 * Phase 5 模块信息
 */
export function getPhase5Info(): {
    name: string;
    version: string;
    components: string[];
    description: string;
} {
    return {
        name: "Phase 5 - 执行结果反馈闭环",
        version: "1.0.0",
        components: [
            "ResultVerifier (执行结果验证器)",
            "LearningLoop (学习循环)",
            "FailureRecovery (失败恢复策略)",
            "FeedbackPipeline (反馈闭环管线)",
        ],
        description: "实现执行验证→学习更新→知识库同步的完整闭环",
    };
}
