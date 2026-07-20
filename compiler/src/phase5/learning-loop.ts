// ============================================================================
// phase5/learning-loop.ts
// Phase 5 - 学习循环
//
// 学习策略：
//   1. 正向学习（用户满意）：记录参数模板 → 提升推理路径置信度
//   2. 偏差学习（用户调整）：计算参数偏差 → 更新默认值建议
//   3. 负向学习（用户撤销/失败）：降低推理路径置信度
//   4. 案例存储：成功案例 → 参数模板库
//
// 对应架构设计文档 7.5 节 LearningLoop
// ============================================================================

import {
    ExecutionRecord,
    ParameterTemplate,
    ConfidenceAdjustment,
    LearningMetrics,
    VerificationResult,
    ExpectedParameters,
    ExecutionResult,
} from "./types";

/**
 * 案例存储接口
 *
 * 默认实现：MemoryCaseStore（内存存储）
 * 真实实现：可对接 Obsidian/数据库
 */
export interface CaseStore {
    /** 添加参数模板 */
    addTemplate(template: ParameterTemplate): void;
    /** 查找指定效果的模板 */
    findTemplates(effectMatchName: string): ParameterTemplate[];
    /** 更新模板使用次数 */
    incrementUsage(templateId: string): void;
    /** 获取所有模板 */
    getAllTemplates(): ParameterTemplate[];
}

/**
 * 内存案例存储
 */
export class MemoryCaseStore implements CaseStore {
    private templates: Map<string, ParameterTemplate> = new Map();

    addTemplate(template: ParameterTemplate): void {
        this.templates.set(template.id, template);
    }

    findTemplates(effectMatchName: string): ParameterTemplate[] {
        return Array.from(this.templates.values())
            .filter((t) => t.effectMatchName === effectMatchName)
            .sort((a, b) => b.usageCount - a.usageCount);
    }

    incrementUsage(templateId: string): void {
        const t = this.templates.get(templateId);
        if (t) {
            t.usageCount++;
            t.lastUsed = new Date().toISOString();
        }
    }

    getAllTemplates(): ParameterTemplate[] {
        return Array.from(this.templates.values());
    }
}

/**
 * 默认值建议存储
 *
 * 记录每个效果的参数默认值，根据用户调整持续更新
 */
export interface DefaultValueStore {
    /** 获取效果参数的当前建议默认值 */
    get(effectMatchName: string, paramName: string): number | string | boolean | number[] | undefined;
    /** 更新效果参数的默认值（带权重，新值权重=learningRate） */
    update(
        effectMatchName: string,
        paramName: string,
        actualValue: number | string | boolean | number[],
        learningRate: number,
    ): void;
    /** 获取效果的所有参数默认值 */
    getAll(effectMatchName: string): Record<string, number | string | boolean | number[]>;
}

/**
 * 内存默认值存储
 */
export class MemoryDefaultValueStore implements DefaultValueStore {
    /** key: `${effectMatchName}.${paramName}`, value: { value, weight } */
    private store: Map<string, { value: number | string | boolean | number[]; weight: number }> = new Map();

    get(effectMatchName: string, paramName: string): number | string | boolean | number[] | undefined {
        return this.store.get(`${effectMatchName}.${paramName}`)?.value;
    }

    update(
        effectMatchName: string,
        paramName: string,
        actualValue: number | string | boolean | number[],
        learningRate: number,
    ): void {
        const key = `${effectMatchName}.${paramName}`;
        const existing = this.store.get(key);

        if (!existing) {
            // 新值，直接存储
            this.store.set(key, { value: actualValue, weight: learningRate });
            return;
        }

        // 数值类型：加权平均
        if (typeof existing.value === "number" && typeof actualValue === "number") {
            const oldWeight = existing.weight;
            const newWeight = learningRate;
            const totalWeight = oldWeight + newWeight;
            const newValue = (existing.value * oldWeight + actualValue * newWeight) / totalWeight;
            this.store.set(key, { value: newValue, weight: totalWeight });
        } else {
            // 非数值类型：用新值替换
            this.store.set(key, { value: actualValue, weight: learningRate });
        }
    }

    getAll(effectMatchName: string): Record<string, number | string | boolean | number[]> {
        const result: Record<string, number | string | boolean | number[]> = {};
        for (const [key, entry] of this.store.entries()) {
            if (key.startsWith(`${effectMatchName}.`)) {
                const paramName = key.slice(effectMatchName.length + 1);
                result[paramName] = entry.value;
            }
        }
        return result;
    }
}

/**
 * 学习循环
 */
export class LearningLoop {
    private caseStore: CaseStore;
    private defaultValueStore: DefaultValueStore;
    private confidenceAdjustments: ConfidenceAdjustment[] = [];
    private executionRecords: ExecutionRecord[] = [];

    /** 学习率（默认 0.3） */
    private learningRate: number;
    /** 置信度调整幅度 */
    private boostDelta: number;
    private penalizeDelta: number;

    constructor(
        caseStore?: CaseStore,
        defaultValueStore?: DefaultValueStore,
        options?: {
            learningRate?: number;
            boostDelta?: number;
            penalizeDelta?: number;
        },
    ) {
        this.caseStore = caseStore || new MemoryCaseStore();
        this.defaultValueStore = defaultValueStore || new MemoryDefaultValueStore();
        this.learningRate = options?.learningRate ?? 0.3;
        this.boostDelta = options?.boostDelta ?? 0.05;
        this.penalizeDelta = options?.penalizeDelta ?? 0.1;
    }

    /**
     * 记录执行结果，触发学习
     *
     * 三种学习场景：
     *   1. userSatisfied=true → 正向学习（添加模板 + 提升置信度）
     *   2. userAdjusted=true → 偏差学习（更新默认值）
     *   3. userUndone=true → 负向学习（降低置信度）
     */
    recordExecution(
        userInput: string,
        intentType: string,
        expected: ExpectedParameters,
        execution: ExecutionResult,
        verification: VerificationResult,
        userFeedback?: {
            satisfied?: boolean;
            adjusted?: boolean;
            undone?: boolean;
            finalParams?: Array<{ name: string; value: number | string | boolean | number[] }>;
        },
        reasoningPath?: string[],
    ): ExecutionRecord {
        const record: ExecutionRecord = {
            id: `exec_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
            timestamp: new Date().toISOString(),
            userInput,
            intentType,
            expected,
            execution,
            verification,
            userSatisfied: userFeedback?.satisfied,
            userAdjusted: userFeedback?.adjusted,
            userUndone: userFeedback?.undone,
            finalParams: userFeedback?.finalParams,
            reasoningPath,
        };

        this.executionRecords.push(record);

        // 触发学习
        if (userFeedback?.undone) {
            this.learnFromFailure(record);
        } else if (userFeedback?.adjusted && userFeedback.finalParams) {
            this.learnFromDeviation(record, userFeedback.finalParams);
        } else if (userFeedback?.satisfied || (execution.success && verification.passed)) {
            this.learnFromSuccess(record);
        } else if (!execution.success) {
            this.learnFromFailure(record);
        }

        return record;
    }

    /**
     * 正向学习：用户满意或验证通过
     */
    private learnFromSuccess(record: ExecutionRecord): void {
        const { expected, execution } = record;

        // 1. 添加参数模板
        if (expected.effectMatchName && execution.effectName) {
            const template: ParameterTemplate = {
                id: `tpl_${Date.now()}_${Math.floor(Math.random() * 10000)}`,
                source: "auto-learned",
                effectMatchName: expected.effectMatchName,
                effectName: execution.effectName,
                parameters: this.propsToObject(expected.properties),
                userRating: "positive",
                usageCount: 1,
                lastUsed: new Date().toISOString(),
                sourceInput: record.userInput,
            };
            this.caseStore.addTemplate(template);
        }

        // 2. 提升推理路径置信度
        if (record.reasoningPath && record.reasoningPath.length > 0) {
            const adjustment: ConfidenceAdjustment = {
                reasoningPath: record.reasoningPath,
                direction: "boost",
                delta: this.boostDelta,
                reason: `执行成功 (record: ${record.id})`,
                timestamp: new Date().toISOString(),
            };
            this.confidenceAdjustments.push(adjustment);
        }
    }

    /**
     * 偏差学习：用户调整了参数
     */
    private learnFromDeviation(
        record: ExecutionRecord,
        finalParams: Array<{ name: string; value: number | string | boolean | number[] }>,
    ): void {
        const { expected } = record;

        if (!expected.effectMatchName) return;

        // 计算每个参数的偏差，并更新默认值
        for (const finalParam of finalParams) {
            const expectedParam = expected.properties.find((p) => p.name === finalParam.name);
            if (!expectedParam) continue;

            const deviation = this.calculateParamDeviation(expectedParam.value, finalParam.value);

            // 如果偏差较大，更新默认值
            if (deviation > 0.05) {
                this.defaultValueStore.update(
                    expected.effectMatchName,
                    finalParam.name,
                    finalParam.value,
                    this.learningRate,
                );
            }
        }
    }

    /**
     * 负向学习：用户撤销或执行失败
     */
    private learnFromFailure(record: ExecutionRecord): void {
        // 降低推理路径置信度
        if (record.reasoningPath && record.reasoningPath.length > 0) {
            const adjustment: ConfidenceAdjustment = {
                reasoningPath: record.reasoningPath,
                direction: "penalize",
                delta: this.penalizeDelta,
                reason: record.execution.success
                    ? `用户撤销 (record: ${record.id})`
                    : `执行失败: ${record.execution.errorCode || "unknown"} (record: ${record.id})`,
                timestamp: new Date().toISOString(),
            };
            this.confidenceAdjustments.push(adjustment);
        }
    }

    /**
     * 计算参数偏差（0-1）
     */
    private calculateParamDeviation(
        expected: number | string | boolean | number[],
        actual: number | string | boolean | number[],
    ): number {
        if (typeof expected === "number" && typeof actual === "number") {
            if (expected === 0) return Math.abs(actual);
            return Math.abs(expected - actual) / Math.abs(expected);
        }
        if (Array.isArray(expected) && Array.isArray(actual)) {
            if (expected.length === 0) return 0;
            const deviations = expected.map((e, i) => {
                const a = actual[i] as number;
                const eNum = e as number;
                if (eNum === 0) return Math.abs(a);
                return Math.abs(eNum - a) / Math.abs(eNum);
            });
            return deviations.reduce((sum, d) => sum + d, 0) / deviations.length;
        }
        return expected === actual ? 0 : 1;
    }

    /**
     * 把 properties 数组转换为对象
     */
    private propsToObject(
        props: Array<{ name: string; value: number | string | boolean | number[] }>,
    ): Record<string, number | string | boolean | number[]> {
        const result: Record<string, number | string | boolean | number[]> = {};
        for (const p of props) {
            result[p.name] = p.value;
        }
        return result;
    }

    /**
     * 获取学习效果度量
     */
    getMetrics(): LearningMetrics {
        const total = this.executionRecords.length;
        const successCount = this.executionRecords.filter(
            (r) => r.execution.success && r.verification.passed,
        ).length;
        const failureCount = this.executionRecords.filter((r) => !r.execution.success).length;
        const userAdjustedCount = this.executionRecords.filter((r) => r.userAdjusted).length;
        const userUndoneCount = this.executionRecords.filter((r) => r.userUndone).length;

        const deviationSum = this.executionRecords
            .filter((r) => r.verification.deviationScore !== undefined)
            .reduce((sum, r) => sum + r.verification.deviationScore, 0);
        const deviationCount = this.executionRecords.filter(
            (r) => r.verification.deviationScore !== undefined,
        ).length;
        const averageDeviation = deviationCount > 0 ? deviationSum / deviationCount : 0;

        const learnedTemplates = this.caseStore.getAllTemplates().length;
        const confidenceAdjustments = this.confidenceAdjustments.length;

        // 推理准确率提升（简化：基于最近10次 vs 之前10次的成功率差异）
        const accuracyImprovement = this.calculateAccuracyImprovement();

        return {
            totalExecutions: total,
            successCount,
            failureCount,
            userAdjustedCount,
            userUndoneCount,
            successRate: total > 0 ? successCount / total : 0,
            averageDeviation,
            learnedTemplates,
            confidenceAdjustments,
            accuracyImprovement,
        };
    }

    /**
     * 计算推理准确率提升
     *
     * 对比最近10次执行和之前10次执行的成功率差异
     */
    private calculateAccuracyImprovement(): number {
        const records = this.executionRecords;
        if (records.length < 4) return 0;

        const recentCount = Math.min(10, Math.floor(records.length / 2));
        const recentRecords = records.slice(-recentCount);
        const earlierRecords = records.slice(-recentCount * 2, -recentCount);

        if (earlierRecords.length === 0) return 0;

        const recentSuccess = recentRecords.filter((r) => r.execution.success).length / recentRecords.length;
        const earlierSuccess = earlierRecords.filter((r) => r.execution.success).length / earlierRecords.length;

        return recentSuccess - earlierSuccess;
    }

    /**
     * 获取所有执行记录
     */
    getExecutionRecords(): ExecutionRecord[] {
        return [...this.executionRecords];
    }

    /**
     * 获取所有置信度调整
     */
    getConfidenceAdjustments(): ConfidenceAdjustment[] {
        return [...this.confidenceAdjustments];
    }

    /**
     * 获取案例存储（用于查询模板）
     */
    getCaseStore(): CaseStore {
        return this.caseStore;
    }

    /**
     * 获取默认值存储（用于查询建议默认值）
     */
    getDefaultValueStore(): DefaultValueStore {
        return this.defaultValueStore;
    }
}

/**
 * 单例实例
 */
export const learningLoop = new LearningLoop();
