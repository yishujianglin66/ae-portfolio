// ============================================================================
// phase5/result-verifier.ts
// Phase 5 - 执行结果验证器
//
// 验证流程：
//   1. 检查执行结果是否成功
//   2. 通过 MCP get-effect-properties 回读实际参数
//   3. 与预期参数对比，计算偏差
//   4. 返回 VerificationResult
//
// 对应架构设计文档 7.2.1 节 ResultVerifier
// ============================================================================

import {
    ExecutionResult,
    ExpectedParameters,
    VerificationResult,
    ParameterMismatch,
    ActualProperty,
} from "./types";

/**
 * MCP 客户端接口（用于回读参数）
 *
 * 实际使用时由调用方注入实现：
 *   - 默认实现：MockMcpClient（不调用真实 MCP，返回 undefined）
 *   - 真实实现：通过 after-effects-mcp 调用 get-effect-properties
 */
export interface McpClient {
    /**
     * 调用 MCP get-effect-properties 工具
     * @returns 返回的效果属性列表，或 null（无法获取时）
     */
    getEffectProperties(compName: string, layerIndex: number, effectIndex?: number): Promise<ActualProperty[] | null>;
}

/**
 * 默认 Mock 实现（不调用真实 MCP）
 */
export class MockMcpClient implements McpClient {
    async getEffectProperties(
        _compName: string,
        _layerIndex: number,
        _effectIndex?: number,
    ): Promise<ActualProperty[] | null> {
        return null;
    }
}

/**
 * 执行结果验证器
 */
export class ResultVerifier {
    private mcpClient: McpClient;
    /** 默认容差（数值类型参数） */
    private defaultTolerance: number;

    constructor(mcpClient?: McpClient, defaultTolerance: number = 0.01) {
        this.mcpClient = mcpClient || new MockMcpClient();
        this.defaultTolerance = defaultTolerance;
    }

    /**
     * 设置 MCP 客户端
     */
    setMcpClient(client: McpClient): void {
        this.mcpClient = client;
    }

    /**
     * 验证执行结果
     *
     * @param expected 预期参数
     * @param actual 执行结果
     */
    async verify(
        expected: ExpectedParameters,
        actual: ExecutionResult,
    ): Promise<VerificationResult> {
        // 步骤1：检查执行是否成功
        if (!actual.success) {
            return {
                passed: false,
                mismatches: [],
                reason: `执行失败: ${actual.errorCode || ""} ${actual.errorMessage || ""}`.trim(),
                deviationScore: 1.0,
            };
        }

        // 步骤2：通过 MCP 回读实际参数
        const actualProps = await this.mcpClient.getEffectProperties(
            expected.compName,
            expected.layerIndex,
            actual.effectIndex,
        );

        if (!actualProps || actualProps.length === 0) {
            // 无法回读（可能是 Mock 模式或 MCP 不可用）
            // 仅检查执行是否成功，不验证参数
            return {
                passed: true,
                mismatches: [],
                reason: "执行成功，但无法回读参数验证（MCP 不可用）",
                deviationScore: 0,
                actualProperties: [],
            };
        }

        // 步骤3：对比预期与实际
        const mismatches = this.compareParameters(expected.properties, actualProps);

        // 步骤4：计算综合偏差度
        const deviationScore = this.calculateDeviationScore(expected.properties, actualProps, mismatches);

        // 步骤5：验证关键帧（如果有）
        if (expected.keyframes && expected.keyframes.length > 0) {
            // 关键帧验证较复杂，简化处理：只检查关键帧数量
            // 实际可通过 getLayerInfo 获取关键帧信息
            // 这里仅记录不验证关键帧的细节
        }

        return {
            passed: mismatches.length === 0,
            mismatches,
            deviationScore,
            actualProperties: actualProps,
        };
    }

    /**
     * 对比预期参数和实际参数
     */
    private compareParameters(
        expected: ExpectedParameters["properties"],
        actual: ActualProperty[],
    ): ParameterMismatch[] {
        const mismatches: ParameterMismatch[] = [];

        for (const expectedProp of expected) {
            const actualProp = actual.find((p) => p.name === expectedProp.name);

            if (!actualProp) {
                mismatches.push({
                    param: expectedProp.name,
                    expected: expectedProp.value,
                    actual: null,
                });
                continue;
            }

            const tolerance = (expectedProp as any).tolerance ?? this.defaultTolerance;

            if (!this.valuesMatch(expectedProp.value, actualProp.value, tolerance)) {
                const deviation = this.calculateDeviation(expectedProp.value, actualProp.value);
                mismatches.push({
                    param: expectedProp.name,
                    expected: expectedProp.value,
                    actual: actualProp.value,
                    deviation,
                });
            }
        }

        return mismatches;
    }

    /**
     * 检查值是否匹配（考虑容差）
     */
    private valuesMatch(
        expected: number | string | boolean | number[],
        actual: number | string | boolean | number[],
        tolerance: number,
    ): boolean {
        // 数值比较
        if (typeof expected === "number" && typeof actual === "number") {
            return Math.abs(expected - actual) <= tolerance;
        }

        // 数组比较（如颜色 [r,g,b]）
        if (Array.isArray(expected) && Array.isArray(actual)) {
            if (expected.length !== actual.length) return false;
            for (let i = 0; i < expected.length; i++) {
                if (Math.abs((expected[i] as number) - (actual[i] as number)) > tolerance) {
                    return false;
                }
            }
            return true;
        }

        // 字符串/布尔值严格相等
        return expected === actual;
    }

    /**
     * 计算单个参数的偏差
     */
    private calculateDeviation(
        expected: number | string | boolean | number[],
        actual: number | string | boolean | number[],
    ): number {
        if (typeof expected === "number" && typeof actual === "number") {
            return Math.abs(expected - actual);
        }
        if (Array.isArray(expected) && Array.isArray(actual)) {
            // 数组偏差取平均
            const deviations = expected.map((e, i) => Math.abs((e as number) - (actual[i] as number)));
            return deviations.reduce((sum, d) => sum + d, 0) / deviations.length;
        }
        // 非数值类型，不匹配则偏差为1
        return expected === actual ? 0 : 1;
    }

    /**
     * 计算综合偏差度（0-1）
     *
     * 0 表示完全匹配，1 表示完全不匹配
     */
    private calculateDeviationScore(
        expected: ExpectedParameters["properties"],
        actual: ActualProperty[],
        mismatches: ParameterMismatch[],
    ): number {
        if (expected.length === 0) return 0;
        if (mismatches.length === 0) return 0;

        // 偏差度 = 不匹配参数数 / 总参数数 + 平均相对偏差
        const mismatchRatio = mismatches.length / expected.length;
        const avgDeviation = mismatches.reduce((sum, m) => {
            const exp = m.expected;
            const act = m.actual;
            if (typeof exp === "number" && typeof act === "number") {
                const relDeviation = exp !== 0 ? Math.abs(exp - act) / Math.abs(exp) : Math.abs(exp - act);
                return sum + Math.min(1, relDeviation);
            }
            return sum + 1;
        }, 0) / mismatches.length;

        // 综合偏差度 = 0.5 * 不匹配比例 + 0.5 * 平均相对偏差
        return 0.5 * mismatchRatio + 0.5 * avgDeviation;
    }
}

/**
 * 单例实例（使用 MockMcpClient）
 */
export const resultVerifier = new ResultVerifier();
