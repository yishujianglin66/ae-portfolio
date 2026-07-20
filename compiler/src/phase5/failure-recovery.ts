// ============================================================================
// phase5/failure-recovery.ts
// Phase 5 - 失败恢复策略
//
// 处理流程：
//   执行失败 → 错误码识别 → 选择恢复策略 → 返回 RecoveryAction
//                                              │
//                                              ├── retry_with_alternative
//                                              ├── retry_with_adjusted_params
//                                              ├── retry_with_longer_timeout
//                                              ├── wait_and_retry
//                                              ├── ask_user
//                                              └── report_error
//
// 重试控制：
//   - 同一错误最多重试 maxRetries 次（默认 3）
//   - 超过重试次数 → 升级为 ask_user 或 report_error
//   - 跨错误码统计：单次执行总重试次数上限 5
//
// 对应架构设计文档 7.3 节 FailureRecovery
// ============================================================================

import {
    ExecutionResult,
    ExpectedParameters,
    RecoveryAction,
    RecoveryActionType,
    ParameterMismatch,
} from "./types";
import { getByCategory, findByMatchName, EffectMapEntry } from "../phase3/effect-name-map";

// ============================================================================
// 错误码定义（对应架构文档 7.3 节）
// ============================================================================

/**
 * 已知错误码枚举
 *
 * 命名规则：<来源>_<编号>
 *   E0xx: 传输层（MCP/Bridge）错误
 *   E3xx: 执行层（AE DOM）错误
 *   E6xx: 超时/资源错误
 */
export enum ErrorCode {
    // 传输层错误
    BRIDGE_OFFLINE = "E006",                  // Bridge 离线
    BRIDGE_TIMEOUT = "E007",                  // Bridge 通信超时
    MCP_NOT_RESPONDING = "E008",              // MCP 无响应

    // 执行层错误
    EFFECT_NOT_FOUND = "E300",                // 效果 matchName 无效/未安装
    PARAM_OUT_OF_RANGE = "E303",              // 参数值超出有效范围
    LAYER_NOT_FOUND = "E304",                 // 图层不存在
    COMP_NOT_FOUND = "E305",                  // 合成不存在
    PROPERTY_NOT_FOUND = "E306",              // 属性路径无效
    KEYFRAME_FAILED = "E307",                 // 关键帧设置失败
    EXPRESSION_ERROR = "E308",                // 表达式语法错误

    // 超时/资源错误
    EXECUTION_TIMEOUT = "E600",               // 执行超时
    OUT_OF_MEMORY = "E601",                   // 内存不足

    // 未知错误
    UNKNOWN = "E000",
}

// ============================================================================
// 重试计数器
// ============================================================================

/**
 * 重试计数器
 *
 * 跟踪每个执行请求的重试次数，防止无限重试
 */
export class RetryCounter {
    /** key: 请求ID，value: 已重试次数 */
    private counts: Map<string, number> = new Map();
    /** 单个请求的最大重试次数（默认 3） */
    private maxRetries: number;
    /** 全局总重试次数上限（默认 5） */
    private globalMaxRetries: number;

    constructor(maxRetries: number = 3, globalMaxRetries: number = 5) {
        this.maxRetries = maxRetries;
        this.globalMaxRetries = globalMaxRetries;
    }

    /**
     * 获取当前已重试次数
     */
    getCount(requestId: string): number {
        return this.counts.get(requestId) || 0;
    }

    /**
     * 增加重试次数
     */
    increment(requestId: string): number {
        const current = this.counts.get(requestId) || 0;
        const newCount = current + 1;
        this.counts.set(requestId, newCount);
        return newCount;
    }

    /**
     * 是否还能重试
     */
    canRetry(requestId: string): boolean {
        const current = this.getCount(requestId);
        return current < this.maxRetries && current < this.globalMaxRetries;
    }

    /**
     * 重置计数器（执行成功后调用）
     */
    reset(requestId: string): void {
        this.counts.delete(requestId);
    }
}

// ============================================================================
// 失败恢复策略
// ============================================================================

/**
 * 失败恢复策略选项
 */
export interface FailureRecoveryOptions {
    /** 默认超时（毫秒，默认 10000） */
    defaultTimeout?: number;
    /** 超时重试时的延展系数（默认 1.5） */
    timeoutBackoffFactor?: number;
    /** 最大超时上限（毫秒，默认 60000） */
    maxTimeout?: number;
    /** wait_and_retry 的初始延迟（毫秒，默认 3000） */
    initialRetryDelay?: number;
    /** wait_and_retry 的退避系数（默认 2.0，指数退避） */
    retryBackoffFactor?: number;
    /** 最大重试次数（默认 3） */
    maxRetries?: number;
}

/**
 * 失败恢复策略
 *
 * 根据 ExecutionResult 的错误码选择合适的恢复策略
 */
export class FailureRecovery {
    private options: Required<FailureRecoveryOptions>;
    private retryCounter: RetryCounter;
    /** 等待重试的当前延迟（指数退避） */
    private currentRetryDelay: number;

    constructor(options?: FailureRecoveryOptions, retryCounter?: RetryCounter) {
        this.options = {
            defaultTimeout: options?.defaultTimeout ?? 10000,
            timeoutBackoffFactor: options?.timeoutBackoffFactor ?? 1.5,
            maxTimeout: options?.maxTimeout ?? 60000,
            initialRetryDelay: options?.initialRetryDelay ?? 3000,
            retryBackoffFactor: options?.retryBackoffFactor ?? 2.0,
            maxRetries: options?.maxRetries ?? 3,
        };
        this.retryCounter = retryCounter || new RetryCounter(this.options.maxRetries);
        this.currentRetryDelay = this.options.initialRetryDelay;
    }

    /**
     * 处理执行失败，返回恢复动作
     *
     * @param execution 执行结果（失败）
     * @param expected 预期参数
     * @param requestId 请求ID（用于重试计数，可选）
     */
    async handleFailure(
        execution: ExecutionResult,
        expected: ExpectedParameters,
        requestId?: string,
    ): Promise<RecoveryAction> {
        const errorCode = execution.errorCode || ErrorCode.UNKNOWN;
        const reqId = requestId || `req_${Date.now()}`;

        // 检查重试次数
        if (!this.retryCounter.canRetry(reqId)) {
            return {
                action: "ask_user",
                message: `已达到最大重试次数 (${this.options.maxRetries})，请人工介入。最后错误: ${errorCode} ${execution.errorMessage || ""}`.trim(),
                maxRetries: this.options.maxRetries,
            };
        }

        // 根据错误码选择恢复策略
        let action: RecoveryAction;
        switch (errorCode) {
            case ErrorCode.EFFECT_NOT_FOUND:
                action = await this.handleEffectNotFound(expected);
                break;

            case ErrorCode.PARAM_OUT_OF_RANGE:
                action = this.handleParamOutOfRange(expected);
                break;

            case ErrorCode.EXECUTION_TIMEOUT:
                action = this.handleTimeout();
                break;

            case ErrorCode.BRIDGE_OFFLINE:
            case ErrorCode.MCP_NOT_RESPONDING:
                action = this.handleBridgeOffline();
                break;

            case ErrorCode.LAYER_NOT_FOUND:
            case ErrorCode.COMP_NOT_FOUND:
            case ErrorCode.PROPERTY_NOT_FOUND:
                action = {
                    action: "ask_user",
                    message: `AE DOM 错误: ${errorCode} - ${execution.errorMessage || "图层/合成/属性不存在"}`,
                };
                break;

            case ErrorCode.KEYFRAME_FAILED:
                action = {
                    action: "report_error",
                    message: `关键帧设置失败: ${execution.errorMessage || "未知原因"}`,
                };
                break;

            case ErrorCode.EXPRESSION_ERROR:
                action = {
                    action: "report_error",
                    message: `表达式错误: ${execution.errorMessage || "语法错误"}`,
                };
                break;

            case ErrorCode.OUT_OF_MEMORY:
                action = {
                    action: "report_error",
                    message: `内存不足，请关闭其他程序后重试`,
                };
                break;

            case ErrorCode.BRIDGE_TIMEOUT:
                action = this.handleTimeout();
                break;

            default:
                action = {
                    action: "report_error",
                    message: `未知错误: ${errorCode} ${execution.errorMessage || ""}`.trim(),
                };
        }

        // 增加重试计数
        this.retryCounter.increment(reqId);

        return action;
    }

    /**
     * 处理"效果未找到"错误：尝试查找替代效果
     */
    private async handleEffectNotFound(expected: ExpectedParameters): Promise<RecoveryAction> {
        if (!expected.effectMatchName) {
            return {
                action: "ask_user",
                message: "效果未安装且无法确定替代方案，请安装对应插件或选择其他效果",
            };
        }

        // 查找当前效果的类别
        const currentEntry = findByMatchName(expected.effectMatchName);
        if (!currentEntry) {
            return {
                action: "ask_user",
                message: `效果 ${expected.effectMatchName} 未安装，无法找到替代方案`,
            };
        }

        // 在同类效果中查找替代
        const alternatives = getByCategory(currentEntry.category)
            .filter((e) => e.matchName !== currentEntry.matchName)
            .filter((e) => e.source === "native"); // 优先使用原生效果作为替代

        if (alternatives.length === 0) {
            return {
                action: "ask_user",
                message: `效果 ${currentEntry.displayName} 未安装，无可用替代方案。请安装插件: ${currentEntry.source}`,
            };
        }

        // 选择第一个替代效果
        const alternative = alternatives[0];
        return {
            action: "retry_with_alternative",
            alternative: alternative.matchName,
            message: `效果 ${currentEntry.displayName} 未安装，尝试使用替代效果: ${alternative.displayName}`,
            maxRetries: this.options.maxRetries,
        };
    }

    /**
     * 处理"参数超出范围"错误：clamp 参数到有效范围
     *
     * 注意：由于无法从错误响应中获取具体范围，
     * 这里采用启发式策略：对数值参数做轻微衰减（×0.9）
     */
    private handleParamOutOfRange(expected: ExpectedParameters): RecoveryAction {
        const adjustedProps = expected.properties.map((p) => {
            if (typeof p.value === "number") {
                // 数值参数：衰减到 90%（启发式，适用于大多数"过大"情况）
                // 如果原值是负数，则放大到 110%
                const adjusted = p.value >= 0 ? p.value * 0.9 : p.value * 1.1;
                return { ...p, value: adjusted };
            }
            return p;
        });

        return {
            action: "retry_with_adjusted_params",
            adjustedParams: { ...expected, properties: adjustedProps },
            message: `参数值超出范围，已自动调整数值`,
            maxRetries: this.options.maxRetries,
        };
    }

    /**
     * 处理"超时"错误：增加超时时间
     */
    private handleTimeout(): RecoveryAction {
        const newTimeout = Math.min(
            this.options.defaultTimeout * this.options.timeoutBackoffFactor,
            this.options.maxTimeout,
        );

        return {
            action: "retry_with_longer_timeout",
            timeout: Math.round(newTimeout),
            message: `执行超时，重试时延展超时到 ${Math.round(newTimeout)}ms`,
            maxRetries: this.options.maxRetries,
        };
    }

    /**
     * 处理"Bridge 离线"错误：等待后重试（指数退避）
     */
    private handleBridgeOffline(): RecoveryAction {
        const delay = this.currentRetryDelay;
        // 指数退避：下次延迟翻倍
        this.currentRetryDelay = Math.min(
            this.currentRetryDelay * this.options.retryBackoffFactor,
            30000, // 最大 30s
        );

        return {
            action: "wait_and_retry",
            delay,
            maxRetries: this.options.maxRetries,
            message: `Bridge 离线，等待 ${delay}ms 后重试`,
        };
    }

    /**
     * 重置重试计数器（执行成功后调用）
     */
    resetRetryCount(requestId: string): void {
        this.retryCounter.reset(requestId);
        // 重置退避延迟
        this.currentRetryDelay = this.options.initialRetryDelay;
    }

    /**
     * 获取重试计数器（用于查询状态）
     */
    getRetryCounter(): RetryCounter {
        return this.retryCounter;
    }

    /**
     * 从验证结果中的不匹配参数构造"调整后参数"
     *
     * 用于验证失败但执行成功的情况：
     * 用户调整了参数，可以将这些调整应用到下次执行
     */
    static buildAdjustedParams(
        expected: ExpectedParameters,
        mismatches: ParameterMismatch[],
    ): ExpectedParameters {
        const adjustedProps = expected.properties.map((p) => {
            const mismatch = mismatches.find((m) => m.param === p.name);
            if (mismatch && mismatch.actual !== null) {
                return { ...p, value: mismatch.actual };
            }
            return p;
        });

        return { ...expected, properties: adjustedProps };
    }
}

/**
 * 单例实例
 */
export const failureRecovery = new FailureRecovery();
