// ============================================================================
// phase5/types.ts
// Phase 5 - 执行结果反馈闭环类型定义
//
// 闭环流程：
//   执行结果 → ResultVerifier → VerificationResult
//     │
//     ├── 成功 → 记录参数模板 → 更新映射权重
//     ├── 微调 → 记录偏差 → 更新默认值
//     └── 失败 → 记录原因 → 降低置信度
//
// 对应架构设计文档 第七章 L5 执行层 + 第十章 10.5 Phase 5
// ============================================================================

/**
 * 执行结果（来自 MCP 工具调用的返回）
 */
export interface ExecutionResult {
    /** 是否执行成功 */
    success: boolean;
    /** 错误码（失败时） */
    errorCode?: string;
    /** 错误信息（失败时） */
    errorMessage?: string;
    /** 实际执行的效果索引（成功时） */
    effectIndex?: number;
    /** 实际添加的关键帧数量 */
    keyframesAdded?: number;
    /** 效果显示名 */
    effectName?: string;
    /** 原始返回内容 */
    rawResponse?: string;
    /** 执行耗时（毫秒） */
    executionTimeMs?: number;
}

/**
 * 预期参数（来自编译器输入）
 */
export interface ExpectedParameters {
    /** 目标合成名 */
    compName: string;
    /** 目标图层索引（1-based） */
    layerIndex: number;
    /** 效果 matchName */
    effectMatchName?: string;
    /** 效果显示名 */
    effectName?: string;
    /** 预期参数列表 */
    properties: Array<{
        name: string;
        value: number | string | boolean | number[];
        /** 容差（数值类型用） */
        tolerance?: number;
    }>;
    /** 预期关键帧 */
    keyframes?: Array<{
        property: string;
        time: number;
        value: number | number[];
    }>;
}

/**
 * 参数不匹配条目
 */
export interface ParameterMismatch {
    /** 参数名 */
    param: string;
    /** 预期值 */
    expected: number | string | boolean | number[] | null;
    /** 实际值 */
    actual: number | string | boolean | number[] | null;
    /** 偏差（数值类型用，abs(expected-actual)） */
    deviation?: number;
}

/**
 * 验证结果
 */
export interface VerificationResult {
    /** 是否通过验证 */
    passed: boolean;
    /** 不匹配的参数列表 */
    mismatches: ParameterMismatch[];
    /** 验证失败原因 */
    reason?: string;
    /** 回读的实际属性（用于学习） */
    actualProperties?: ActualProperty[];
    /** 综合偏差度（0-1，0表示完全匹配） */
    deviationScore: number;
}

/**
 * 实际属性（通过 get-effect-properties 回读）
 */
export interface ActualProperty {
    name: string;
    value: number | string | boolean | number[];
    type?: string;
}

/**
 * 执行记录（用于学习）
 */
export interface ExecutionRecord {
    /** 唯一ID */
    id: string;
    /** 时间戳 */
    timestamp: string;
    /** 原始用户输入（自然语言） */
    userInput: string;
    /** 识别的意图类型 */
    intentType: string;
    /** 预期参数 */
    expected: ExpectedParameters;
    /** 执行结果 */
    execution: ExecutionResult;
    /** 验证结果 */
    verification: VerificationResult;
    /** 用户是否满意（默认 undefined 表示未反馈） */
    userSatisfied?: boolean;
    /** 用户是否调整了参数 */
    userAdjusted?: boolean;
    /** 用户是否撤销了操作 */
    userUndone?: boolean;
    /** 用户最终采用的参数（如果调整过） */
    finalParams?: Array<{ name: string; value: number | string | boolean | number[] }>;
    /** 推理路径（用于置信度调整） */
    reasoningPath?: string[];
}

/**
 * 参数模板（成功案例）
 */
export interface ParameterTemplate {
    /** 模板ID */
    id: string;
    /** 来源 ("auto-learned" | "manual" | "preset") */
    source: "auto-learned" | "manual" | "preset";
    /** 效果 matchName */
    effectMatchName: string;
    /** 效果显示名 */
    effectName: string;
    /** 参数键值对 */
    parameters: Record<string, number | string | boolean | number[]>;
    /** 用户评级 */
    userRating: "positive" | "negative" | "neutral";
    /** 使用次数 */
    usageCount: number;
    /** 最后使用时间 */
    lastUsed: string;
    /** 来源用户输入 */
    sourceInput?: string;
}

/**
 * 置信度调整记录
 */
export interface ConfidenceAdjustment {
    /** 推理路径标识 */
    reasoningPath: string[];
    /** 调整方向 */
    direction: "boost" | "penalize";
    /** 调整幅度 */
    delta: number;
    /** 调整原因 */
    reason: string;
    /** 时间戳 */
    timestamp: string;
}

/**
 * 失败恢复动作类型
 */
export type RecoveryActionType =
    | "retry_with_alternative"      // 用替代效果重试
    | "retry_with_adjusted_params"  // 用调整后参数重试
    | "retry_with_longer_timeout"   // 用更长超时重试
    | "wait_and_retry"              // 等待后重试
    | "ask_user"                    // 询问用户
    | "report_error";               // 报告错误

/**
 * 失败恢复动作
 */
export interface RecoveryAction {
    action: RecoveryActionType;
    /** 替代效果 matchName（retry_with_alternative 时） */
    alternative?: string;
    /** 调整后的参数（retry_with_adjusted_params 时） */
    adjustedParams?: ExpectedParameters;
    /** 新的超时（retry_with_longer_timeout 时） */
    timeout?: number;
    /** 等待时间（wait_and_retry 时） */
    delay?: number;
    /** 最大重试次数 */
    maxRetries?: number;
    /** 给用户的消息 */
    message?: string;
}

/**
 * 学习效果度量
 */
export interface LearningMetrics {
    /** 总执行次数 */
    totalExecutions: number;
    /** 成功执行次数 */
    successCount: number;
    /** 失败次数 */
    failureCount: number;
    /** 用户调整次数 */
    userAdjustedCount: number;
    /** 用户撤销次数 */
    userUndoneCount: number;
    /** 成功率 */
    successRate: number;
    /** 平均偏差度 */
    averageDeviation: number;
    /** 学习到的模板数 */
    learnedTemplates: number;
    /** 置信度调整次数 */
    confidenceAdjustments: number;
    /** 推理准确率提升 */
    accuracyImprovement: number;
}

/**
 * 知识库更新条目（写入 Obsidian）
 */
export interface KnowledgeUpdate {
    /** 更新类型 */
    type: "new_template" | "parameter_adjustment" | "confidence_update" | "failure_case";
    /** 关联文档名 */
    documentName: string;
    /** 更新内容（Markdown 片段） */
    content: string;
    /** 时间戳 */
    timestamp: string;
    /** 来源执行记录ID */
    sourceRecordId: string;
}
