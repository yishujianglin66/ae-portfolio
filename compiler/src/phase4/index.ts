// ============================================================================
// phase4/index.ts
// Phase 4 - 自然语言理解层入口
//
// 端到端管线：
//   用户输入 → NLUParser → EffectDescriptionParser → Intent+EffectDescription
//     ↓
//   (Clarifier 追问机制，低置信度时返回 ClarificationRequest)
//     ↓
//   intentToReport → AnalysisReport (Phase 3 输入)
//     ↓
//   (Phase 3) reportToOps → CompilerInput → compile → ExtendScript
//
// 使用方式：
//   import { processUserInput } from "./phase4";
//   const response = await processUserInput("给文字加一个暖色发光");
// ============================================================================

export * from "./types";
export * from "./nlu-parser";
export * from "./effect-description-parser";
export * from "./clarifier";
export * from "./vocabulary-map";
export * from "./intent-to-report";
export * from "./parameter-mapper";
export * from "./effect-generators";
export * from "./param-optimizer";
export * from "./ai-scheduler";
export * from "./effect-knowledge-graph";

import { NLUParser, nluParser } from "./nlu-parser";
import { EffectDescriptionParser, effectDescriptionParser } from "./effect-description-parser";
import { Clarifier, clarifier, buildEngineResponse } from "./clarifier";
import { intentToReport, AnalysisReport } from "./intent-to-report";
import { Intent, EffectDescription, ProjectContext, EngineResponse } from "./types";
import { getVocabStats } from "./vocabulary-map";
import { ParameterMapper, parameterMapper } from "./parameter-mapper";
import { EffectGeneratorFactory, GlowGenerator, ColorKeyGenerator, CCParticleWorldGenerator, FractalNoiseGenerator, RampGenerator, EffectParams } from "./effect-generators";
import { ParameterOptimizer } from "./param-optimizer";
import { AIScheduler, aiScheduler } from "./ai-scheduler";
import { searchEffectsEnhanced, recommendStyleEnhanced, EffectNode, StyleRecipe } from "./effect-knowledge-graph";

/**
 * 处理用户输入的完整流程（不包含追问）
 *
 * @param input 用户自然语言
 * @param context 项目上下文
 * @returns 引擎响应（含意图、效果描述、追问请求）
 */
export function processUserInput(
    input: string,
    context?: ProjectContext,
): EngineResponse {
    // 1. NLU 意图识别
    const intent = nluParser.parse(input, context);

    // 2. 效果描述解析
    const description = effectDescriptionParser.parse(input, intent.type);

    // 3. 检查是否需要追问
    const clarifyRequest = clarifier.generate(intent, description);

    // 4. 构建响应
    return buildEngineResponse(intent, description, clarifyRequest);
}

/**
 * 增强版用户输入处理（异步，含 LLM 增强 + 记忆缓存 + 自动降级）
 *
 * 端到端管线（增强版）：
 *   用户输入 → NLUParser.parseEnhanced（LLM 增强）
 *     ↓
 *   EffectDescriptionParser（效果描述解析）
 *     ↓
 *   searchEffectsEnhanced（效果知识图谱 LLM 搜索，可选）
 *     ↓
 *   Clarifier（追问机制）
 *     ↓
 *   buildEngineResponse
 *
 * 失败时自动降级到同步 processUserInput，保证主流程可用
 *
 * @param input 用户自然语言
 * @param context 项目上下文
 * @param options 选项：是否启用效果搜索/风格推荐
 */
export async function processUserInputEnhanced(
    input: string,
    context?: ProjectContext,
    options?: {
        searchEffects?: boolean;
        recommendStyle?: boolean;
    },
): Promise<EngineResponse> {
    const opts = {
        searchEffects: options?.searchEffects ?? false,
        recommendStyle: options?.recommendStyle ?? false,
    };

    try {
        // 1. NLU 意图识别（LLM 增强 + 记忆缓存 + 自动降级）
        const intent = await nluParser.parseEnhanced(input, context);

        // 2. 效果描述解析
        const description = effectDescriptionParser.parse(input, intent.type);

        // 3. 可选：效果知识图谱 LLM 搜索
        if (opts.searchEffects && description.effectName) {
            try {
                const effects = await searchEffectsEnhanced(description.effectName);
                (description as any)._knowledgeGraphEffects = effects;
            } catch {
                // 知识图谱搜索失败不影响主流程
            }
        }

        // 4. 可选：风格配方 LLM 推荐
        if (opts.recommendStyle && intent.type === "STYLE_COMBO") {
            try {
                const style = await recommendStyleEnhanced(input);
                (description as any)._recommendedStyle = style;
            } catch {
                // 风格推荐失败不影响主流程
            }
        }

        // 5. 检查是否需要追问
        const clarifyRequest = clarifier.generate(intent, description);

        // 6. 构建响应
        return buildEngineResponse(intent, description, clarifyRequest);
    } catch (err) {
        // 降级到同步流程
        return processUserInput(input, context);
    }
}

/**
 * 处理追问回答
 *
 * @param originalIntent 原始意图
 * @param description 原始效果描述
 * @param answer 用户回答
 * @param slotName 追问关联的槽位名
 */
export function processClarification(
    originalIntent: Intent,
    description: EffectDescription,
    answer: string,
    slotName: string,
): EngineResponse {
    // 应用追问答案
    const updatedIntent = clarifier.applyAnswer(originalIntent, answer, slotName);

    // 重新检查是否需要进一步追问
    const clarifyRequest = clarifier.generate(updatedIntent, description);

    return buildEngineResponse(updatedIntent, description, clarifyRequest);
}

/**
 * 端到端：自然语言 → AnalysisReport
 *
 * 该函数整合了 NLU + 效果描述 + 追问 + 转换，输出 Phase 3 期望的 AnalysisReport
 *
 * @param input 用户自然语言
 * @param context 项目上下文
 * @param clarificationAnswers 预先提供的追问答案（可选）
 */
export function nluToReport(
    input: string,
    context?: ProjectContext,
    clarificationAnswers?: Record<string, string>,
): AnalysisReport {
    // 1. NLU 解析
    let intent = nluParser.parse(input, context);
    const description = effectDescriptionParser.parse(input, intent.type);

    // 2. 处理追问答案
    if (clarificationAnswers) {
        for (const [slotName, answer] of Object.entries(clarificationAnswers)) {
            intent = clarifier.applyAnswer(intent, answer, slotName);
        }
    }

    // 3. 转换为 AnalysisReport
    return intentToReport(intent, description, context);
}

/**
 * 端到端增强版：自然语言 → AnalysisReport（异步，含 LLM 增强）
 *
 * 整合 NLU.parseEnhanced + 效果描述 + 追问 + 转换
 * 失败时自动降级到同步 nluToReport
 *
 * @param input 用户自然语言
 * @param context 项目上下文
 * @param clarificationAnswers 预先提供的追问答案（可选）
 */
export async function nluToReportEnhanced(
    input: string,
    context?: ProjectContext,
    clarificationAnswers?: Record<string, string>,
): Promise<AnalysisReport> {
    try {
        // 1. NLU 解析（LLM 增强）
        let intent = await nluParser.parseEnhanced(input, context);
        const description = effectDescriptionParser.parse(input, intent.type);

        // 2. 处理追问答案
        if (clarificationAnswers) {
            for (const [slotName, answer] of Object.entries(clarificationAnswers)) {
                intent = clarifier.applyAnswer(intent, answer, slotName);
            }
        }

        // 3. 转换为 AnalysisReport
        return intentToReport(intent, description, context);
    } catch (err) {
        // 降级到同步流程
        return nluToReport(input, context, clarificationAnswers);
    }
}

/**
 * 获取 Phase 4 系统信息
 */
export function getPhase4Info() {
    const vocabStats = getVocabStats();
    return {
        phase: 4,
        name: "Natural Language Understanding Layer",
        components: [
            "NLUParser (意图识别)",
            "EffectDescriptionParser (效果描述解析)",
            "Clarifier (追问机制)",
            "IntentToReport (Phase 3 衔接)",
            "ParameterMapper (参数映射)",
            "EffectGeneratorFactory (效果参数生成)",
            "ParameterOptimizer (参数优化)",
            "AIScheduler (AI调度引擎)",
        ],
        intentTypes: 7,
        vocabularySize: vocabStats.total,
        vocabularyCategories: vocabStats.byCategory,
        confidenceThresholds: {
            autoExecute: 0.7,
            noClarification: 0.6,
            minRecognition: 0.3,
        },
        supportedEffects: 5,
    };
}

// 导出单例类（用于自定义配置）
export { NLUParser, EffectDescriptionParser, Clarifier, ParameterMapper, EffectGeneratorFactory, ParameterOptimizer, AIScheduler };

/**
 * 默认导出：完整的 NLU 处理器
 */
export default {
    processUserInput,
    processUserInputEnhanced,
    processClarification,
    nluToReport,
    nluToReportEnhanced,
    getPhase4Info,
    nluParser,
    effectDescriptionParser,
    clarifier,
    parameterMapper,
    effectGeneratorFactory: new EffectGeneratorFactory(),
    parameterOptimizer: new ParameterOptimizer(),
    aiScheduler,
};
