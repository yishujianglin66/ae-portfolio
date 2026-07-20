// ============================================================================
// phase4/param-optimizer.ts
// Phase 4 - 效果参数优化器
//
// 核心职责：
//   1. 基于视觉质量评估对生成的参数进行优化
//   2. 应用参数约束和最佳实践规则
//   3. 防止参数值超出有效范围导致视觉异常
//   4. 优化参数组合以获得更好的视觉效果
//
// 评估维度：
//   - 参数合理性（是否在有效范围内）
//   - 视觉协调性（参数之间是否冲突）
//   - 风格一致性（是否符合目标风格）
//   - 性能影响（参数值是否会导致性能问题）
// ============================================================================

import { EffectParams } from "./effect-generators";
import { getLLMGateway, chatWithRouting } from "./llm-gateway";
import { getMemoryStore } from "./memory-store";

export interface OptimizationResult {
    optimizedParams: EffectParams;
    changes: Array<{
        paramName: string;
        oldValue: number | string | number[];
        newValue: number | string | number[];
        reason: string;
    }>;
    score: number;
    warnings: string[];
}

export interface OptimizationContext {
    compWidth?: number;
    compHeight?: number;
    targetStyle?: string;
    performanceMode?: boolean;
    maxParticles?: number;
}

const PARAM_CONSTRAINTS: Record<string, {
    params: Record<string, { min: number; max: number; step?: number }>;
    conflicts?: Array<{
        paramA: string;
        paramB: string;
        condition: (a: number, b: number) => boolean;
        fix: (a: number, b: number) => { a?: number; b?: number };
    }>;
    bestPractices?: Array<{
        condition: (params: Record<string, number | string | number[]>) => boolean;
        fix: (params: Record<string, number | string | number[]>) => void;
        reason: string;
    }>;
}> = {
    "ADBE Glo2": {
        params: {
            "Glow Threshold": { min: 0, max: 100 },
            "Glow Radius": { min: 0, max: 200 },
            "Glow Intensity": { min: 0, max: 10 },
        },
        conflicts: [
            {
                paramA: "Glow Radius",
                paramB: "Glow Intensity",
                condition: (r, i) => r > 150 && i > 5,
                fix: (r, i) => ({ b: Math.min(i, 4) }),
            },
        ],
        bestPractices: [
            {
                condition: (p) => (p["Glow Intensity"] as number) > 3 && (p["Glow Threshold"] as number) < 20,
                fix: (p) => { p["Glow Threshold"] = Math.max(p["Glow Threshold"] as number, 25); },
                reason: "高强度发光需要更高阈值避免过曝",
            },
        ],
    },
    "ADBE Color Key": {
        params: {
            "Color Tolerance": { min: 0, max: 100 },
            "Edge Feather": { min: 0, max: 10 },
            "Edge Thin": { min: -5, max: 5 },
            "Edge Contrast": { min: 0, max: 100 },
        },
        conflicts: [
            {
                paramA: "Color Tolerance",
                paramB: "Edge Feather",
                condition: (t, f) => t > 60 && f > 3,
                fix: (t, f) => ({ b: Math.min(f, 2) }),
            },
        ],
        bestPractices: [
            {
                condition: (p) => (p["Color Tolerance"] as number) > 50,
                fix: (p) => { p["Edge Contrast"] = Math.min(p["Edge Contrast"] as number + 15, 100); },
                reason: "高容差需要提高边缘对比度",
            },
        ],
    },
    "CC Particle World": {
        params: {
            "Birth Rate": { min: 0, max: 1000 },
            "Longevity": { min: 0.1, max: 10 },
            "Velocity": { min: 0, max: 500 },
            "Gravity": { min: -200, max: 200 },
            "Particle Radius": { min: 0.1, max: 100 },
            "Opacity": { min: 0, max: 100 },
        },
        conflicts: [
            {
                paramA: "Birth Rate",
                paramB: "Particle Radius",
                condition: (b, r) => b > 300 && r > 20,
                fix: (b, r) => ({ a: Math.min(b, 200), b: Math.min(r, 15) }),
            },
        ],
        bestPractices: [
            {
                condition: (p) => (p["Birth Rate"] as number) > 500,
                fix: (p) => { p["Longevity"] = Math.min(p["Longevity"] as number, 1.5); },
                reason: "高粒子密度需要缩短生命周期",
            },
            {
                condition: (p) => (p["Velocity"] as number) > 200 && (p["Gravity"] as number) !== 0,
                fix: (p) => { p["Gravity"] = p["Gravity"] as number * 0.5; },
                reason: "高速粒子需要减弱重力影响",
            },
        ],
    },
    "ADBE Fractal Noise": {
        params: {
            "Contrast": { min: 0, max: 100 },
            "Brightness": { min: -100, max: 100 },
            "Scale": { min: 10, max: 2000 },
            "Complexity": { min: 1, max: 10 },
            "Evolution Speed": { min: 0, max: 20 },
        },
        conflicts: [
            {
                paramA: "Complexity",
                paramB: "Evolution Speed",
                condition: (c, e) => c > 7 && e > 10,
                fix: (c, e) => ({ b: Math.min(e, 8) }),
            },
        ],
        bestPractices: [
            {
                condition: (p) => (p["Scale"] as number) < 50 && (p["Complexity"] as number) > 5,
                fix: (p) => { p["Complexity"] = Math.min(p["Complexity"] as number, 4); },
                reason: "小尺度噪波不需要高复杂度",
            },
        ],
    },
    "ADBE Ramp": {
        params: {
            "Ramp Scatter": { min: 0, max: 100 },
        },
        conflicts: [],
        bestPractices: [
            {
                condition: (p) => (p["Ramp Scatter"] as number) > 50 && p["Ramp Shape"] === "Linear Ramp",
                fix: (p) => { p["Ramp Shape"] = "Radial Ramp"; },
                reason: "高散射适合径向渐变",
            },
        ],
    },
};

const STYLE_GUIDELINES: Record<string, Array<{
    effect: string;
    check: (params: Record<string, number | string | number[]>) => boolean;
    fix: (params: Record<string, number | string | number[]>) => void;
    reason: string;
}>> = {
    "cyberpunk": [
        {
            effect: "ADBE Glo2",
            check: (p) => (p["Glow Intensity"] as number) < 2,
            fix: (p) => { p["Glow Intensity"] = Math.max(p["Glow Intensity"] as number, 2.5); },
            reason: "赛博朋克风格需要强烈发光",
        },
    ],
    "dreamy": [
        {
            effect: "ADBE Glo2",
            check: (p) => (p["Glow Intensity"] as number) > 2,
            fix: (p) => { p["Glow Intensity"] = Math.min(p["Glow Intensity"] as number, 1.5); },
            reason: "梦幻风格需要柔和发光",
        },
    ],
    "minimal": [
        {
            effect: "ADBE Glo2",
            check: (p) => (p["Glow Radius"] as number) > 30,
            fix: (p) => { p["Glow Radius"] = Math.min(p["Glow Radius"] as number, 20); },
            reason: "极简风格需要克制的发光范围",
        },
    ],
};

export class ParameterOptimizer {
    private context: OptimizationContext;

    constructor(context: OptimizationContext = {}) {
        this.context = context;
    }

    optimize(params: EffectParams): OptimizationResult {
        const changes: OptimizationResult["changes"] = [];
        const warnings: string[] = [];

        const constraints = PARAM_CONSTRAINTS[params.matchName];
        if (!constraints) {
            return {
                optimizedParams: params,
                changes: [],
                score: 1.0,
                warnings: [`No constraints found for effect: ${params.matchName}`],
            };
        }

        const optimizedSettings = { ...params.settings };

        this.enforceBounds(optimizedSettings, constraints.params, changes);

        if (constraints.conflicts) {
            this.resolveConflicts(optimizedSettings, constraints.conflicts, changes, warnings);
        }

        if (constraints.bestPractices) {
            this.applyBestPractices(optimizedSettings, constraints.bestPractices, changes);
        }

        if (this.context.targetStyle) {
            this.applyStyleGuidelines(optimizedSettings, params.matchName, changes);
        }

        if (this.context.performanceMode) {
            this.applyPerformanceOptimizations(optimizedSettings, params.matchName, changes, warnings);
        }

        const score = this.calculateScore(params.settings, optimizedSettings, changes, warnings);

        return {
            optimizedParams: { ...params, settings: optimizedSettings },
            changes,
            score,
            warnings,
        };
    }

    private enforceBounds(
        settings: Record<string, number | string | number[]>,
        paramConstraints: Record<string, { min: number; max: number; step?: number }>,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>
    ): void {
        for (const [paramName, constraint] of Object.entries(paramConstraints)) {
            if (settings[paramName] !== undefined && typeof settings[paramName] === "number") {
                const oldValue = settings[paramName] as number;
                const newValue = this.clamp(oldValue, constraint.min, constraint.max);

                if (constraint.step) {
                    const steppedValue = Math.round(newValue / constraint.step) * constraint.step;
                    if (steppedValue !== newValue) {
                        changes.push({
                            paramName,
                            oldValue,
                            newValue: steppedValue,
                            reason: `参数值已按步长 ${constraint.step} 调整`,
                        });
                        settings[paramName] = steppedValue;
                        continue;
                    }
                }

                if (newValue !== oldValue) {
                    changes.push({
                        paramName,
                        oldValue,
                        newValue,
                        reason: `参数值超出范围 [${constraint.min}, ${constraint.max}]`,
                    });
                    settings[paramName] = newValue;
                }
            }
        }
    }

    private resolveConflicts(
        settings: Record<string, number | string | number[]>,
        conflicts: Array<{ paramA: string; paramB: string; condition: (a: number, b: number) => boolean; fix: (a: number, b: number) => { a?: number; b?: number } }>,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>,
        warnings: string[]
    ): void {
        for (const conflict of conflicts) {
            const valueA = settings[conflict.paramA];
            const valueB = settings[conflict.paramB];

            if (typeof valueA === "number" && typeof valueB === "number") {
                if (conflict.condition(valueA, valueB)) {
                    warnings.push(`${conflict.paramA} 与 ${conflict.paramB} 存在参数冲突`);
                    const fixResult = conflict.fix(valueA, valueB);

                    if (fixResult.a !== undefined) {
                        changes.push({
                            paramName: conflict.paramA,
                            oldValue: valueA,
                            newValue: fixResult.a,
                            reason: `解决与 ${conflict.paramB} 的参数冲突`,
                        });
                        settings[conflict.paramA] = fixResult.a;
                    }
                    if (fixResult.b !== undefined) {
                        changes.push({
                            paramName: conflict.paramB,
                            oldValue: valueB,
                            newValue: fixResult.b,
                            reason: `解决与 ${conflict.paramA} 的参数冲突`,
                        });
                        settings[conflict.paramB] = fixResult.b;
                    }
                }
            }
        }
    }

    private applyBestPractices(
        settings: Record<string, number | string | number[]>,
        practices: Array<{ condition: (params: Record<string, number | string | number[]>) => boolean; fix: (params: Record<string, number | string | number[]>) => void; reason: string }>,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>
    ): void {
        const originalSettings = { ...settings };
        for (const practice of practices) {
            if (practice.condition(originalSettings)) {
                practice.fix(settings);
                for (const [key, newValue] of Object.entries(settings)) {
                    if (originalSettings[key] !== newValue) {
                        changes.push({
                            paramName: key,
                            oldValue: originalSettings[key],
                            newValue,
                            reason: practice.reason,
                        });
                    }
                }
            }
        }
    }

    private applyStyleGuidelines(
        settings: Record<string, number | string | number[]>,
        matchName: string,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>
    ): void {
        const guidelines = STYLE_GUIDELINES[this.context.targetStyle || ""];
        if (!guidelines) return;

        const originalSettings = { ...settings };
        for (const guideline of guidelines) {
            if (guideline.effect === matchName) {
                if (guideline.check(originalSettings)) {
                    guideline.fix(settings);
                    for (const [key, newValue] of Object.entries(settings)) {
                        if (originalSettings[key] !== newValue) {
                            changes.push({
                                paramName: key,
                                oldValue: originalSettings[key],
                                newValue,
                                reason: `风格规范: ${guideline.reason}`,
                            });
                        }
                    }
                }
            }
        }
    }

    private applyPerformanceOptimizations(
        settings: Record<string, number | string | number[]>,
        matchName: string,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>,
        warnings: string[]
    ): void {
        if (matchName === "CC Particle World") {
            const maxParticles = this.context.maxParticles || 500;
            const birthRate = settings["Birth Rate"] as number;
            const longevity = settings["Longevity"] as number;
            const estimatedParticles = birthRate * longevity;

            if (estimatedParticles > maxParticles) {
                warnings.push("粒子数量超出性能阈值，已优化");
                const reductionFactor = maxParticles / estimatedParticles;
                const newBirthRate = Math.round(birthRate * reductionFactor);
                const newLongevity = Math.round(longevity * reductionFactor * 10) / 10;

                if (newBirthRate !== birthRate) {
                    changes.push({
                        paramName: "Birth Rate",
                        oldValue: birthRate,
                        newValue: newBirthRate,
                        reason: "性能优化: 降低粒子出生率",
                    });
                    settings["Birth Rate"] = newBirthRate;
                }
                if (newLongevity !== longevity) {
                    changes.push({
                        paramName: "Longevity",
                        oldValue: longevity,
                        newValue: newLongevity,
                        reason: "性能优化: 缩短粒子生命周期",
                    });
                    settings["Longevity"] = newLongevity;
                }
            }
        }

        if (matchName === "ADBE Fractal Noise") {
            const complexity = settings["Complexity"] as number;
            if (complexity > 6) {
                const newComplexity = Math.min(complexity, 6);
                changes.push({
                    paramName: "Complexity",
                    oldValue: complexity,
                    newValue: newComplexity,
                    reason: "性能优化: 降低噪波复杂度",
                });
                settings["Complexity"] = newComplexity;
            }
        }
    }

    private calculateScore(
        original: Record<string, number | string | number[]>,
        optimized: Record<string, number | string | number[]>,
        changes: Array<{ paramName: string; oldValue: number | string | number[]; newValue: number | string | number[]; reason: string }>,
        warnings: string[]
    ): number {
        let score = 1.0;

        for (const change of changes) {
            if (typeof change.oldValue === "number" && typeof change.newValue === "number") {
                const diff = Math.abs(change.newValue - change.oldValue);
                const maxPossible = Math.max(Math.abs(change.oldValue), Math.abs(change.newValue), 1);
                score -= (diff / maxPossible) * 0.1;
            }
        }

        score -= warnings.length * 0.05;

        return Math.max(0.1, score);
    }

    private clamp(value: number, min: number, max: number): number {
        return Math.max(min, Math.min(max, value));
    }

    setContext(context: Partial<OptimizationContext>): void {
        this.context = { ...this.context, ...context };
    }

    getConstraints(matchName: string): typeof PARAM_CONSTRAINTS[string] | undefined {
        return PARAM_CONSTRAINTS[matchName];
    }

    listSupportedEffects(): string[] {
        return Object.keys(PARAM_CONSTRAINTS);
    }

    // ------------------------------------------------------------------
    // LLM 增强优化
    // ------------------------------------------------------------------

    /**
     * LLM 增强版优化 — 在规则优化基础上，用 LLM 提供智能参数建议
     */
    async optimizeEnhanced(
        params: EffectParams
    ): Promise<OptimizationResult> {
        // 1. 先用本地规则优化
        const localResult = this.optimize(params);
        const gw = getLLMGateway();

        // 2. LLM 不可用时直接返回本地结果
        if (!gw.isAvailable()) {
            return localResult;
        }

        // 3. 查记忆系统
        const mem = getMemoryStore();
        const matchName = params.matchName || "";
        const experiences = mem.getExperience({
            category: "param_optimize",
            taskKeyword: matchName,
            limit: 3,
            minConfidence: 0.7,
        });

        if (experiences.length > 0 && experiences[0].confidence > 0.85) {
            const cached = experiences[0].content.result as OptimizationResult;
            if (cached) {
                return cached;
            }
        }

        // 4. 用 LLM 增强参数建议
        try {
            const llmSuggestions = await this.getLLMParamSuggestions(params, localResult);

            if (llmSuggestions.suggestions.length > 0) {
                localResult.warnings.push(...llmSuggestions.suggestions);
            }

            // 记录到记忆系统
            mem.remember({
                category: "param_optimize",
                key: matchName,
                content: { result: localResult },
                tags: [matchName],
                confidence: 0.6,
            });

            return localResult;
        } catch (e) {
            console.warn("[ParameterOptimizer] LLM 增强失败:", e);
            return localResult;
        }
    }

    /**
     * 用 LLM 获取智能参数建议
     */
    private async getLLMParamSuggestions(
        params: EffectParams,
        localResult: OptimizationResult
    ): Promise<{ suggestions: string[] }> {
        const systemPrompt = `你是AE效果参数优化专家。分析参数并给出优化建议。

输出JSON格式:
{
  "suggestions": ["建议1", "建议2"]
}`;

        const paramSummary = JSON.stringify({
            matchName: params.matchName,
            settings: params.settings,
            localChanges: localResult.changes.map(c => ({
                param: c.paramName,
                old: c.oldValue,
                new: c.newValue,
                reason: c.reason,
            })),
            style: this.context.targetStyle || "default",
        }, null, 2);

        const result = await chatWithRouting({
            message: `分析以下AE效果参数，给出优化建议:\n${paramSummary}`,
            taskType: "effect_planning",
            systemPrompt,
        });

        if (!result.success) {
            return { suggestions: [] };
        }

        try {
            const match = result.content.match(/\{[\s\S]*\}/);
            if (match) {
                return JSON.parse(match[0]);
            }
        } catch {
            // 忽略
        }

        return { suggestions: [] };
    }
}

export const parameterOptimizer = new ParameterOptimizer();