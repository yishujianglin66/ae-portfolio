// ============================================================================
// phase4/ai-scheduler.ts
// Phase 4 - AI智能调度引擎主入口
//
// 核心职责：
//   1. 整合NLU解析、参数生成、参数优化和操作序列生成
//   2. 实现自然语言→效果参数→AE操作的完整管线
//   3. 提供统一的调度API供上层调用
//
// 调度流程：
//   用户输入 → NLUParser → Intent + EffectDescription
//                       → ParameterMapper / EffectGeneratorFactory
//                       → ParameterOptimizer
//                       → IR Builder → Code Generator
//                       → ExtendScript
// ============================================================================

import { NLUParser, nluParser } from "./nlu-parser";
import { EffectDescriptionParser, effectDescriptionParser } from "./effect-description-parser";
import { ParameterMapper, parameterMapper, ParameterMapping } from "./parameter-mapper";
import { EffectGeneratorFactory, effectGeneratorFactory, EffectParams } from "./effect-generators";
import { ParameterOptimizer, parameterOptimizer, OptimizationResult } from "./param-optimizer";
import { Intent, IntentType, EffectDescription, ProjectContext, SilhouetteOperation } from "./types";
import { Operation, AddEffectOp, SetPropertyOp, CompilerInput } from "../types";
import { validate } from "../validator";
import { buildIR } from "../ir-builder";
import { generateCode } from "../codegen";
import { CompileResult } from "../types";
import { IntentRouter, intentRouter, TaskRoute } from "./intent-router";
import { getLLMGateway } from "./llm-gateway";
import { persistentLearningLoop } from "../phase5/persistent-learning-loop";
import {
    ExpectedParameters as LearningExpectedParams,
    ExecutionResult as LearningExecutionResult,
    VerificationResult as LearningVerificationResult,
} from "../phase5/types";

export interface SchedulerOptions {
    projectContext?: ProjectContext;
    targetLayerRef?: string;
    enableOptimization?: boolean;
    performanceMode?: boolean;
    targetStyle?: string;
}

export interface SchedulerResult {
    success: boolean;
    intent?: Intent;
    effectDescription?: EffectDescription;
    mappings?: ParameterMapping[];
    generatedEffects?: EffectParams[];
    optimizations?: OptimizationResult[];
    operations?: Operation[];
    compilerInput?: CompilerInput;
    compileResult?: CompileResult;
    jsxCode?: string;
    silhouetteOperations?: SilhouetteOperation[];
    route?: TaskRoute;
    confidence: number;
    needsClarification: boolean;
    clarificationQuestion?: string;
    clarificationOptions?: string[];
    error?: string;
}

export interface NLUPipelineResult {
    intent: Intent;
    effectDescription: EffectDescription;
    understood: boolean;
    needsClarification: boolean;
    clarificationQuestion?: string;
    clarificationOptions?: string[];
}

const EFFECT_NAME_MAPPING: Record<string, string> = {
    "发光": "glow",
    "辉光": "glow",
    "glow": "glow",
    "霓虹": "glow",
    "红色发光": "glow",
    "模糊": "blur",
    "高斯模糊": "blur",
    "blur": "blur",
    "粒子": "ccparticleworld",
    "粒子世界": "ccparticleworld",
    "particle": "ccparticleworld",
    "color key": "colorkey",
    "颜色键": "colorkey",
    "绿幕": "colorkey",
    "抠像": "colorkey",
    "噪波": "fractalnoise",
    "分形噪波": "fractalnoise",
    "云彩": "fractalnoise",
    "渐变": "ramp",
    "ramp": "ramp",
    "adbeglo2": "glow",
    "adbeglo": "glow",
    "adbecolorkey": "colorkey",
    "adbefractalnoise": "fractalnoise",
    "adberamp": "ramp",
    "ccparticleworld": "ccparticleworld",
};

function mapEffectName(effectName: string): string | undefined {
    let normalized = effectName.toLowerCase().replace(/\s/g, "");
    
    normalized = normalized.replace(/^做[个一]?/, "");
    normalized = normalized.replace(/[个一]$/, "");
    normalized = normalized.replace(/效果$/, "");
    normalized = normalized.replace(/特效$/, "");
    
    if (EFFECT_NAME_MAPPING[normalized]) {
        return EFFECT_NAME_MAPPING[normalized];
    }
    
    for (const [key, value] of Object.entries(EFFECT_NAME_MAPPING)) {
        if (normalized.includes(key)) {
            return value;
        }
    }
    
    return undefined;
}

export class AIScheduler {
    private nluParser: NLUParser;
    private descriptionParser: EffectDescriptionParser;
    private parameterMapper: ParameterMapper;
    private generatorFactory: EffectGeneratorFactory;
    private parameterOptimizer: ParameterOptimizer;

    constructor(options: SchedulerOptions = {}) {
        this.nluParser = nluParser;
        this.descriptionParser = effectDescriptionParser;
        this.parameterMapper = new ParameterMapper({
            compWidth: options.projectContext?.compResolution?.[0],
            compHeight: options.projectContext?.compResolution?.[1],
            frameRate: options.projectContext?.compFrameRate,
            duration: options.projectContext?.compDuration,
        });
        this.generatorFactory = new EffectGeneratorFactory({
            compWidth: options.projectContext?.compResolution?.[0],
            compHeight: options.projectContext?.compResolution?.[1],
            frameRate: options.projectContext?.compFrameRate,
            duration: options.projectContext?.compDuration,
        });
        this.parameterOptimizer = new ParameterOptimizer({
            compWidth: options.projectContext?.compResolution?.[0],
            compHeight: options.projectContext?.compResolution?.[1],
            targetStyle: options.targetStyle,
            performanceMode: options.performanceMode ?? false,
        });
    }

    runNLUPipeline(input: string, context?: ProjectContext): NLUPipelineResult {
        const intent = this.nluParser.parse(input, context);
        const effectDescription = this.descriptionParser.parse(input, intent.type);
        const needsClarification = this.nluParser.needsClarification(intent);

        let clarificationQuestion: string | undefined;
        let clarificationOptions: string[] | undefined;

        if (needsClarification) {
            clarificationQuestion = this.generateClarificationQuestion(intent, effectDescription);
            clarificationOptions = this.generateClarificationOptions(intent);
        }

        return {
            intent,
            effectDescription,
            understood: intent.type !== IntentType.UNKNOWN && !needsClarification,
            needsClarification,
            clarificationQuestion,
            clarificationOptions,
        };
    }

    private generateClarificationQuestion(intent: Intent, description: EffectDescription): string {
        if (intent.type === IntentType.ADD_EFFECT && !intent.slots.effectName) {
            return "您想添加什么效果？";
        }
        if (intent.type === IntentType.STYLE_COMBO && !intent.slots.styleName) {
            return "您想要什么风格？";
        }
        if (intent.type === IntentType.CREATE_ANIM && !intent.slots.animType) {
            return "您想创建什么类型的动画？";
        }
        if (intent.type === IntentType.SILHOUETTE_TASK && !intent.slots.silhouetteTask) {
            return "您想做哪种 Silhouette 任务？";
        }
        if (intent.type === IntentType.SILHOUETTE_TASK && intent.slots.silhouetteTask === "roto" && !intent.slots.rotoTarget) {
            return "您想抠出什么对象？";
        }
        if (description.colorKeywords.length === 0 && intent.confidence < 0.6) {
            return "是否需要指定颜色？";
        }
        return "请明确您想要的效果";
    }

    private generateClarificationOptions(intent: Intent): string[] {
        switch (intent.type) {
            case IntentType.ADD_EFFECT:
                return ["发光", "模糊", "粒子", "调色", "扭曲"];
            case IntentType.STYLE_COMBO:
                return ["赛博朋克", "电影感", "梦幻", "复古", "极简"];
            case IntentType.CREATE_ANIM:
                return ["弹入", "淡入", "滑入", "缩放", "旋转"];
            case IntentType.SILHOUETTE_TASK:
                if (intent.slots.silhouetteTask === "roto") {
                    return ["人物", "汽车", "动物", "背景"];
                }
                return ["遮罩抠像", "平面跟踪", "Paint 修复", "导出到 AE"];
            default:
                return ["确认", "取消"];
        }
    }

    generateParameters(nluResult: NLUPipelineResult): { mappings: ParameterMapping[]; generatedEffects: EffectParams[] } {
        const mappings: ParameterMapping[] = [];
        const generatedEffects: EffectParams[] = [];
        const seenEffectMatchNames = new Set<string>();

        if (nluResult.intent.type === IntentType.ADD_EFFECT) {
            const effectName = nluResult.intent.slots.effectName?.toLowerCase();
            if (effectName) {
                const mappedName = mapEffectName(effectName);
                if (mappedName) {
                    const modifiers = this.extractModifiers(nluResult);
                    const generated = this.generatorFactory.generateEffect(mappedName, modifiers);
                    if (generated) {
                        generatedEffects.push(generated);
                        seenEffectMatchNames.add(generated.matchName);
                    }
                }
            }
        }

        if (nluResult.effectDescription.effectKeywords.length > 0) {
            const mapped = this.parameterMapper.map(nluResult.effectDescription);
            mappings.push(...mapped);
        }

        for (const mapping of mappings) {
            if (!seenEffectMatchNames.has(mapping.matchName)) {
                const modifiers = this.extractModifiers(nluResult);
                const mappedName = mapEffectName(mapping.matchName);
                if (mappedName) {
                    const generated = this.generatorFactory.generateEffect(mappedName, modifiers);
                    if (generated) {
                        generatedEffects.push(generated);
                        seenEffectMatchNames.add(generated.matchName);
                    }
                }
            }
        }

        return { mappings, generatedEffects };
    }

    private extractModifiers(nluResult: NLUPipelineResult) {
        let style = nluResult.intent.slots.styleName;
        
        if (!style && nluResult.intent.slots.effectName) {
            const effectName = nluResult.intent.slots.effectName.toLowerCase();
            const styleKeywords = ["霓虹", "柔和", "强烈", "赛博朋克", "梦幻", "电影感", "复古", "极简", "fire", "snow", "stars", "clouds", "water", "electric", "smoke", "sunset", "cyberpunk", "gradient", "radial", "warmcool"];
            
            for (const keyword of styleKeywords) {
                if (effectName.includes(keyword)) {
                    style = keyword;
                    break;
                }
            }
        }
        
        return {
            intensity: nluResult.effectDescription.intensityKeywords,
            color: nluResult.effectDescription.colorKeywords,
            temporal: nluResult.effectDescription.temporalKeywords,
            style,
        };
    }

    // ------------------------------------------------------------------
    // Silhouette 操作生成
    // ------------------------------------------------------------------

    generateSilhouetteOperations(intent: Intent): SilhouetteOperation[] {
        const operations: SilhouetteOperation[] = [];
        const taskType = intent.slots.silhouetteTask;

        if (!taskType) return operations;

        switch (taskType) {
            case "roto": {
                const op: SilhouetteOperation = {
                    taskType: "roto",
                    shapeType: (intent.slots.effectName === "bezier" || intent.slots.effectName === "x-spline")
                        ? intent.slots.effectName as "x-spline" | "bezier"
                        : "x-spline",
                    tolerance: 1.0,
                    keyframes: 5,
                    outputFormat: (intent.slots.outputFormat as "png" | "tiff" | "exr") || "png",
                };
                if (intent.slots.rotoTarget) {
                    op.target = intent.slots.rotoTarget;
                }
                // 如果提到了跟踪，添加跟踪参数
                if (intent.slots.trackType) {
                    op.tracking = intent.slots.trackType === "point" ? "point" :
                        intent.slots.trackType === "paint" ? "paint-track" : "planar";
                }
                operations.push(op);
                break;
            }

            case "track": {
                const op: SilhouetteOperation = {
                    taskType: "track",
                    trackType: (intent.slots.trackType as "planar" | "point" | "paint") || "planar",
                    searchArea: 21,
                    accuracy: "medium",
                    outputFormat: (intent.slots.outputFormat as "json" | "ae") || "ae",
                };
                operations.push(op);
                break;
            }

            case "paint": {
                const op: SilhouetteOperation = {
                    taskType: "paint",
                    paintMode: (intent.slots.effectName === "clone" || intent.slots.effectName === "repair" || intent.slots.effectName === "erase")
                        ? intent.slots.effectName as "clone" | "repair" | "erase"
                        : "clone",
                    brushSize: 25,
                    brushHardness: 0.5,
                    outputFormat: (intent.slots.outputFormat as "png" | "tiff") || "png",
                };
                operations.push(op);
                break;
            }

            case "export": {
                operations.push({
                    taskType: "export",
                    outputFormat: "ae",
                });
                break;
            }
        }

        return operations;
    }

    optimizeParameters(effects: EffectParams[]): OptimizationResult[] {
        return effects.map(effect => this.parameterOptimizer.optimize(effect));
    }

    buildOperations(
        effects: EffectParams[],
        layerRef: string
    ): Operation[] {
        const operations: Operation[] = [];

        if (layerRef === "selected") {
            const compRef = "comp_main";
            const targetLayerRef = "layer_text";
            
            operations.push({
                op: "createComp",
                ref: compRef,
                name: "AI生成合成",
                width: 1920,
                height: 1080,
                frameRate: 30,
                duration: 5,
                bgColor: [0, 0, 0],
            });

            operations.push({
                op: "addLayer",
                ref: targetLayerRef,
                compRef,
                layerType: "text",
                name: "文本图层",
                text: "AI效果",
                fontSize: 72,
                fillColor: [1, 1, 1],
                position: [960, 540],
            });

            for (let i = 0; i < effects.length; i++) {
                const effect = effects[i];
                operations.push({
                    op: "addEffect",
                    ref: `fx_${effect.matchName.replace(/\s/g, "_")}_${i}`,
                    layerRef: targetLayerRef,
                    matchName: effect.matchName,
                    name: effect.displayName,
                    settings: effect.settings,
                });
            }
        } else {
            for (let i = 0; i < effects.length; i++) {
                const effect = effects[i];
                operations.push({
                    op: "addEffect",
                    ref: `fx_${effect.matchName.replace(/\s/g, "_")}_${i}`,
                    layerRef,
                    matchName: effect.matchName,
                    name: effect.displayName,
                    settings: effect.settings,
                });
            }
        }

        return operations;
    }

    compileToJSX(operations: Operation[]): CompileResult {
        const input: CompilerInput = {
            operations,
            metadata: {
                source: "AI_Scheduler",
                timestamp: new Date().toISOString(),
            },
        };

        const validation = validate(input);
        if (!validation.valid) {
            return {
                success: false,
                script: "",
                errors: validation.errors,
                warnings: validation.warnings,
                stats: {
                    operationCount: operations.length,
                    irNodeCount: 0,
                    scriptSize: 0,
                    compileTimeMs: 0,
                },
            };
        }

        const ir = buildIR(input);
        const codeGen = generateCode(ir.nodes);

        return {
            success: codeGen.errors.length === 0,
            script: codeGen.script,
            errors: codeGen.errors.map(e => ({ code: "G000", message: e.message })),
            warnings: [],
            stats: {
                operationCount: operations.length,
                irNodeCount: ir.nodes.length,
                scriptSize: codeGen.script.length,
                compileTimeMs: 0,
            },
        };
    }

    /**
     * P0-1 修复: 回读 phase5 学习机器的历史学习成果，应用到生成参数上
     * - 查询 DefaultValueStore 获取学习到的默认值
     * - 查询 CaseStore 获取成功模板
     * 将学习成果混合进 generatedEffects 的 settings 中
     */
    private applyLearnedDefaults(effects: EffectParams[]): EffectParams[] {
        return effects.map(effect => {
            const learnedDefaults = persistentLearningLoop.getDefaultValueStore().getAll(effect.matchName);
            const templates = persistentLearningLoop.getCaseStore().findTemplates(effect.matchName);

            if (Object.keys(learnedDefaults).length === 0 && templates.length === 0) {
                return effect;
            }

            const mergedSettings = { ...effect.settings };
            let adjusted = false;

            // 1. 应用学习到的默认值（加权混合 80% 原始 + 20% 学习值）
            for (const [param, learnedValue] of Object.entries(learnedDefaults)) {
                if (param in mergedSettings && typeof mergedSettings[param] === "number" && typeof learnedValue === "number") {
                    mergedSettings[param] = (mergedSettings[param] as number) * 0.8 + learnedValue * 0.2;
                    adjusted = true;
                }
            }

            // 2. 如果有高使用率模板（usageCount >= 3），以 10% 权重混合模板参数
            const bestTemplate = templates.find(t => t.usageCount >= 3);
            if (bestTemplate) {
                for (const [param, tplValue] of Object.entries(bestTemplate.parameters)) {
                    if (param in mergedSettings && typeof mergedSettings[param] === "number" && typeof tplValue === "number") {
                        mergedSettings[param] = (mergedSettings[param] as number) * 0.9 + tplValue * 0.1;
                        adjusted = true;
                    }
                }
                persistentLearningLoop.getCaseStore().incrementUsage(bestTemplate.id);
            }

            if (!adjusted) return effect;
            return { ...effect, settings: mergedSettings };
        });
    }

    /**
     * P0-1 修复: 将执行结果写入 phase5 持久化学习循环
     * 使学习机器真正接收到生产反馈，闭合"复用"腿
     */
    private recordToLearningLoop(
        input: string,
        intentType: string,
        effects: EffectParams[],
        compileSuccess: boolean,
    ): void {
        try {
            for (const effect of effects) {
                const expected: LearningExpectedParams = {
                    compName: "AI生成合成",
                    layerIndex: 1,
                    effectMatchName: effect.matchName,
                    effectName: effect.displayName,
                    properties: Object.entries(effect.settings).map(([name, value]) => ({
                        name,
                        value: value as number | string | number[],
                    })),
                };

                const execution: LearningExecutionResult = {
                    success: compileSuccess,
                    effectName: effect.displayName,
                    errorCode: compileSuccess ? undefined : "COMPILE_FAILED",
                    errorMessage: compileSuccess ? undefined : "JSX compilation failed",
                };

                const verification: LearningVerificationResult = {
                    passed: compileSuccess,
                    mismatches: [],
                    deviationScore: compileSuccess ? 0 : 1,
                };

                persistentLearningLoop.recordExecution(
                    input,
                    intentType,
                    expected,
                    execution,
                    verification,
                    undefined, // userFeedback - 后续由上层 UI 补充
                    ["nlu_parse", "param_generate", "optimize", "compile"],
                );
            }
        } catch {
            // 学习记录失败不应影响主流程
        }
    }

    /**
     * @deprecated 同步纯规则路径。生产环境请使用 executeAsync()（LLM 增强 + 自动降级）。
     * 保留仅为向后兼容测试和 demo 脚本。
     */
    execute(input: string, options: SchedulerOptions = {}): SchedulerResult {
        const context = options.projectContext;
        const layerRef = options.targetLayerRef || "selected";

        const nluResult = this.runNLUPipeline(input, context);

        if (!nluResult.understood) {
            return {
                success: false,
                intent: nluResult.intent,
                effectDescription: nluResult.effectDescription,
                confidence: nluResult.intent.confidence,
                needsClarification: nluResult.needsClarification,
                clarificationQuestion: nluResult.clarificationQuestion,
                clarificationOptions: nluResult.clarificationOptions,
            };
        }

        // 路由决策
        const route = intentRouter.route(nluResult.intent, context);

        // Silhouette 任务
        if (route.type === "silhouette_only" || route.type === "hybrid") {
            const silhouetteOps = this.generateSilhouetteOperations(nluResult.intent);

            // 混合任务: 同时生成 AE 操作
            if (route.type === "hybrid" && route.aeOperations && route.aeOperations.length > 0) {
                const { mappings, generatedEffects } = this.generateParameters(nluResult);
                let optimizations: OptimizationResult[] = [];
                let optimizedEffects = generatedEffects;

                if (options.enableOptimization !== false) {
                    optimizations = this.optimizeParameters(generatedEffects);
                    optimizedEffects = optimizations.map(o => o.optimizedParams);
                }

                // P0-1: 应用历史学习成果
                optimizedEffects = this.applyLearnedDefaults(optimizedEffects);

                const operations = this.buildOperations(optimizedEffects, layerRef);
                const compileResult = this.compileToJSX(operations);

                // P0-1: 记录执行到学习循环
                this.recordToLearningLoop(input, nluResult.intent.type, optimizedEffects, compileResult.success);

                return {
                    success: silhouetteOps.length > 0 && compileResult.success,
                    intent: nluResult.intent,
                    effectDescription: nluResult.effectDescription,
                    mappings,
                    generatedEffects,
                    optimizations,
                    operations,
                    compilerInput: { operations },
                    compileResult,
                    jsxCode: compileResult.script,
                    silhouetteOperations: silhouetteOps,
                    route,
                    confidence: nluResult.intent.confidence,
                    needsClarification: false,
                };
            }

            // 纯 Silhouette 任务
            return {
                success: silhouetteOps.length > 0,
                intent: nluResult.intent,
                effectDescription: nluResult.effectDescription,
                silhouetteOperations: silhouetteOps,
                route,
                confidence: nluResult.intent.confidence,
                needsClarification: false,
                error: silhouetteOps.length === 0 ? "未能生成 Silhouette 操作" : undefined,
            };
        }

        // 纯 AE 任务
        const { mappings, generatedEffects } = this.generateParameters(nluResult);

        let optimizations: OptimizationResult[] = [];
        let optimizedEffects = generatedEffects;

        if (options.enableOptimization !== false) {
            optimizations = this.optimizeParameters(generatedEffects);
            optimizedEffects = optimizations.map(o => o.optimizedParams);
        }

        // P0-1: 应用历史学习成果（回读 getDefaultValues / findTemplates）
        optimizedEffects = this.applyLearnedDefaults(optimizedEffects);

        const operations = this.buildOperations(optimizedEffects, layerRef);

        if (operations.length === 0) {
            return {
                success: false,
                intent: nluResult.intent,
                effectDescription: nluResult.effectDescription,
                mappings,
                generatedEffects,
                optimizations,
                route,
                confidence: nluResult.intent.confidence,
                needsClarification: false,
                error: "未能生成任何操作",
            };
        }

        const compileResult = this.compileToJSX(operations);

        // P0-1: 记录执行到持久化学习循环（闭合复用腿）
        this.recordToLearningLoop(input, nluResult.intent.type, optimizedEffects, compileResult.success);

        return {
            success: compileResult.success,
            intent: nluResult.intent,
            effectDescription: nluResult.effectDescription,
            mappings,
            generatedEffects,
            optimizations,
            operations,
            compilerInput: { operations },
            compileResult,
            jsxCode: compileResult.script,
            route,
            confidence: nluResult.intent.confidence,
            needsClarification: false,
        };
    }

    /**
     * 自动配置 LLM Gateway：从 process.env 检测 ModelScope/OpenAI 等环境变量。
     * 仅在 Gateway 未配置时执行一次（幂等）。
     */
    private _llmConfigured = false;
    private ensureLLMConfigured(): void {
        if (this._llmConfigured) return;
        this._llmConfigured = true;
        try {
            const gw = getLLMGateway();
            if (!gw.isAvailable()) {
                // 从 process.env 自动配置（Node.js 环境）
                const env = typeof process !== "undefined" ? (process.env as Record<string, string>) : {};
                gw.configureFromEnv(env);
            }
        } catch {
            // 配置失败不影响主流程（降级为规则路径）
        }
    }

    /**
     * LLM 增强版执行入口 — 生产路径默认使用此方法。
     *
     * 与 execute() 的区别：
     * - NLU 解析使用 parseEnhanced()（记忆回读 + LLM 增强 + 规则兖底）
     * - 路由决策使用 routeEnhanced()（记忆回读 + LLM 增强 + 规则兖底）
     * - 自动从 process.env 配置 LLM Gateway（无需手动调用 configureFromEnv）
     * - 当 LLM 不可用时自动降级为纯规则路径（等价于 execute()）
     */
    async executeAsync(input: string, options: SchedulerOptions = {}): Promise<SchedulerResult> {
        // 自动配置 LLM Gateway（从环境变量检测 ModelScope/OpenAI 等）
        this.ensureLLMConfigured();
    
        const context = options.projectContext;
        const layerRef = options.targetLayerRef || "selected";

        // LLM 增强 NLU 解析（内含记忆回读 + 规则兜底）
        const intent = await this.nluParser.parseEnhanced(input, context);
        const effectDescription = this.descriptionParser.parse(input, intent.type);
        const needsClarification = this.nluParser.needsClarification(intent);

        if (needsClarification || intent.confidence < 0.4) {
            return {
                success: false,
                intent,
                effectDescription,
                confidence: intent.confidence,
                needsClarification,
                clarificationQuestion: this.generateClarificationQuestion(intent, effectDescription),
                clarificationOptions: this.generateClarificationOptions(intent),
            };
        }

        const nluResult: NLUPipelineResult = {
            intent,
            effectDescription,
            understood: true,
            needsClarification: false,
        };

        // LLM 增强路由决策（内含记忆回读 + 规则兜底）
        const route = await intentRouter.routeEnhanced(intent, context);

        // 纯 AE 任务（最常见路径）
        const { mappings, generatedEffects } = this.generateParameters(nluResult);
        let optimizations: OptimizationResult[] = [];
        let optimizedEffects = generatedEffects;

        if (options.enableOptimization !== false) {
            optimizations = this.optimizeParameters(generatedEffects);
            optimizedEffects = optimizations.map(o => o.optimizedParams);
        }

        // P0-1: 应用历史学习成果
        optimizedEffects = this.applyLearnedDefaults(optimizedEffects);

        const operations = this.buildOperations(optimizedEffects, layerRef);
        if (operations.length === 0) {
            return {
                success: false, intent, effectDescription, mappings,
                generatedEffects, optimizations, route,
                confidence: intent.confidence, needsClarification: false,
                error: "未能生成任何操作",
            };
        }

        const compileResult = this.compileToJSX(operations);

        // P0-1: 记录执行到学习循环
        this.recordToLearningLoop(input, intent.type, optimizedEffects, compileResult.success);

        return {
            success: compileResult.success,
            intent, effectDescription, mappings,
            generatedEffects, optimizations, operations,
            compilerInput: { operations },
            compileResult,
            jsxCode: compileResult.script,
            route,
            confidence: intent.confidence,
            needsClarification: false,
        };
    }

    setContext(options: Partial<SchedulerOptions>): void {
        if (options.projectContext) {
            this.parameterMapper.setContext({
                compWidth: options.projectContext.compResolution?.[0],
                compHeight: options.projectContext.compResolution?.[1],
                frameRate: options.projectContext.compFrameRate,
                duration: options.projectContext.compDuration,
            });
            this.generatorFactory.setContext({
                compWidth: options.projectContext.compResolution?.[0],
                compHeight: options.projectContext.compResolution?.[1],
                frameRate: options.projectContext.compFrameRate,
                duration: options.projectContext.compDuration,
            });
            this.parameterOptimizer.setContext({
                compWidth: options.projectContext.compResolution?.[0],
                compHeight: options.projectContext.compResolution?.[1],
            });
        }
        if (options.targetStyle) {
            this.parameterOptimizer.setContext({ targetStyle: options.targetStyle });
        }
        if (options.performanceMode !== undefined) {
            this.parameterOptimizer.setContext({ performanceMode: options.performanceMode });
        }
    }

    listSupportedEffects(): string[] {
        return this.generatorFactory.listAvailableGenerators();
    }

    getGeneratorInfo(effectName: string): { displayName: string; matchName: string } | undefined {
        const generators = this.generatorFactory.listAvailableGenerators();
        const map: Record<string, { displayName: string; matchName: string }> = {
            "glow": { displayName: "Glow", matchName: "ADBE Glo2" },
            "colorkey": { displayName: "Color Key", matchName: "ADBE Color Key" },
            "ccparticleworld": { displayName: "CC Particle World", matchName: "CC Particle World" },
            "fractalnoise": { displayName: "Fractal Noise", matchName: "ADBE Fractal Noise" },
            "ramp": { displayName: "Ramp", matchName: "ADBE Ramp" },
        };
        return map[effectName.toLowerCase()];
    }
}

export const aiScheduler = new AIScheduler();