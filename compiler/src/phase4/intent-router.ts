// ============================================================================
// phase4/intent-router.ts
// Phase 4 - 意图路由决策器
//
// 核心职责：
//   1. 根据 NLU 解析的 Intent，决定任务流向
//   2. 识别混合任务（如"扣人像后加发光"），拆分为 AE + Silhouette 子任务
//   3. 提供降级策略（Silhouette 不可用时回退到 AE 原生工具）
//
// 路由类型：
//   ae_only         → 纯 AE 效果/动画/图层操作
//   silhouette_only → 纯 Silhouette roto/track/paint
//   hybrid          → Silhouette 前置 + AE 后置
//   unknown         → 无法识别，需追问
// ============================================================================

import { Intent, IntentType, IntentSlots, SilhouetteOperation, ProjectContext } from "./types";
import { LLMGateway, chatWithRouting, getLLMGateway } from "./llm-gateway";
import { getMemoryStore, MemoryEntry } from "./memory-store";

// ---------------------------------------------------------------------------
// 类型定义
// ---------------------------------------------------------------------------

/** 路由类型 */
export type RouteType = "ae_only" | "silhouette_only" | "hybrid" | "unknown";

/** AE 操作（简化版，与 ai-scheduler 的 Operation 兼容） */
export interface AEOperation {
    op: string;
    matchName?: string;
    effectName?: string;
    layerRef?: string;
    settings?: Record<string, unknown>;
    [key: string]: unknown;
}

/** 路由结果 */
export interface TaskRoute {
    type: RouteType;
    /** AE 操作列表（ae_only 或 hybrid 的 AE 部分） */
    aeOperations?: AEOperation[];
    /** Silhouette 操作列表（silhouette_only 或 hybrid 的 Silhouette 部分） */
    silhouetteOperations?: SilhouetteOperation[];
    /** 混合任务中的执行顺序 */
    executionOrder?: ("silhouette" | "ae")[];
    /** 降级策略 */
    fallback?: FallbackStrategy;
    /** 路由原因（调试用） */
    reason: string;
    /** 置信度 */
    confidence: number;
}

/** 降级策略 */
export interface FallbackStrategy {
    /** 触发条件 */
    condition: string;
    /** 降级到的操作 */
    aeFallbackOps: AEOperation[];
    /** 提示信息 */
    message: string;
}

// ---------------------------------------------------------------------------
// 混合任务拆分关键词
// ---------------------------------------------------------------------------

/** 连接词，表示"先做A再做B" */
const HYBRID_CONNECTORS = [
    /然后/i, /之后再?/i, /接着/i, /完后/i, /最后/i,
    /然后加/i, /再加/i, /同时加/i, /并加/i,
    /后加/i, /后添加/i, /后做/i,
];

/** Silhouette 相关关键词 */
const SILHOUETTE_KEYWORDS = [
    /(?:扣|抠|遮罩|蒙版|mask|roto)/i,
    /(?:跟踪|追踪|track)/i,
    /(?:修|擦|paint|修复|去除|擦除)/i,
    /(?:silhouette)/i,
];

/** AE 效果关键词 */
const AE_EFFECT_KEYWORDS = [
    /(?:发光|辉光|glow|霓虹)/i,
    /(?:模糊|blur|高斯)/i,
    /(?:粒子|particle)/i,
    /(?:噪波|noise|分形)/i,
    /(?:渐变|ramp|gradient)/i,
    /(?:调色|color|lut|色调)/i,
    /(?:扭曲|distort|变形|warp)/i,
    /(?:阴影|shadow|投影)/i,
    /(?:动画|anim|弹入|淡入|滑入|缩放|旋转)/i,
];

// ---------------------------------------------------------------------------
// IntentRouter
// ---------------------------------------------------------------------------

export class IntentRouter {
    /**
     * 根据意图路由任务
     */
    route(intent: Intent, context?: ProjectContext): TaskRoute {
        // 1. 未知意图
        if (intent.type === IntentType.UNKNOWN || intent.confidence < 0.3) {
            return {
                type: "unknown",
                reason: `意图未识别或置信度过低 (${intent.confidence.toFixed(2)})`,
                confidence: intent.confidence,
            };
        }

        // 2. 纯 Silhouette 任务
        if (intent.type === IntentType.SILHOUETTE_TASK) {
            // 检查是否包含 AE 效果关键词（混合任务）
            const aePart = this.extractAEPrefix(intent.rawInput);
            if (aePart) {
                return this.routeHybrid(intent, aePart);
            }
            return this.routeSilhouetteOnly(intent);
        }

        // 3. 纯 AE 任务（但可能用户提到了遮罩/跟踪 → 混合）
        const silhouettePart = this.extractSilhouettePrefix(intent.rawInput);
        if (silhouettePart) {
            return this.routeHybrid(intent, silhouettePart);
        }

        // 4. 纯 AE 任务
        return this.routeAEOnly(intent);
    }

    // ------------------------------------------------------------------
    // 纯 AE 路由
    // ------------------------------------------------------------------
    private routeAEOnly(intent: Intent): TaskRoute {
        const aeOps = this.generateAEOps(intent);
        return {
            type: "ae_only",
            aeOperations: aeOps,
            executionOrder: ["ae"],
            reason: `纯 AE 任务: ${intent.type}`,
            confidence: intent.confidence,
        };
    }

    // ------------------------------------------------------------------
    // 纯 Silhouette 路由
    // ------------------------------------------------------------------
    private routeSilhouetteOnly(intent: Intent): TaskRoute {
        const silhouetteOps = this.generateSilhouetteOps(intent);
        return {
            type: "silhouette_only",
            silhouetteOperations: silhouetteOps,
            executionOrder: ["silhouette"],
            fallback: this.generateFallback(intent),
            reason: `纯 Silhouette 任务: ${intent.slots.silhouetteTask}`,
            confidence: intent.confidence,
        };
    }

    // ------------------------------------------------------------------
    // 混合路由
    // ------------------------------------------------------------------
    private routeHybrid(intent: Intent, _splitHint: string): TaskRoute {
        const aeOps = this.generateAEOps(intent);
        const silhouetteOps = this.generateSilhouetteOps(intent);

        return {
            type: "hybrid",
            aeOperations: aeOps,
            silhouetteOperations: silhouetteOps,
            executionOrder: ["silhouette", "ae"],
            fallback: this.generateFallback(intent),
            reason: `混合任务: Silhouette(${intent.slots.silhouetteTask}) → AE`,
            confidence: intent.confidence,
        };
    }

    // ------------------------------------------------------------------
    // 从输入中提取 AE 部分（检查是否包含混合意图）
    // ------------------------------------------------------------------
    private extractAEPrefix(input: string): string | null {
        // 检查是否同时包含 Silhouette 和 AE 关键词
        const hasSilhouette = SILHOUETTE_KEYWORDS.some(p => p.test(input));
        const hasAE = AE_EFFECT_KEYWORDS.some(p => p.test(input));
        const hasConnector = HYBRID_CONNECTORS.some(p => p.test(input));

        if (hasSilhouette && hasAE && hasConnector) {
            // 提取 AE 部分（连接词之后的内容）
            for (const connector of HYBRID_CONNECTORS) {
                const match = input.match(connector);
                if (match) {
                    const afterConnector = input.slice(match.index! + match[0].length).trim();
                    if (afterConnector && AE_EFFECT_KEYWORDS.some(p => p.test(afterConnector))) {
                        return afterConnector;
                    }
                }
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // 从输入中提取 Silhouette 部分
    // ------------------------------------------------------------------
    private extractSilhouettePrefix(input: string): string | null {
        const hasSilhouette = SILHOUETTE_KEYWORDS.some(p => p.test(input));
        const hasAE = AE_EFFECT_KEYWORDS.some(p => p.test(input));
        const hasConnector = HYBRID_CONNECTORS.some(p => p.test(input));

        if (hasSilhouette && hasAE && hasConnector) {
            // 提取 Silhouette 部分（连接词之前的内容）
            for (const connector of HYBRID_CONNECTORS) {
                const match = input.match(connector);
                if (match && match.index) {
                    const beforeConnector = input.slice(0, match.index).trim();
                    if (beforeConnector && SILHOUETTE_KEYWORDS.some(p => p.test(beforeConnector))) {
                        return beforeConnector;
                    }
                }
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // 生成 AE 操作（简化版，实际由 AIScheduler.generateParameters 完成）
    // ------------------------------------------------------------------
    private generateAEOps(intent: Intent): AEOperation[] {
        const ops: AEOperation[] = [];

        if (intent.type === IntentType.ADD_EFFECT && intent.slots.effectName) {
            ops.push({
                op: "addEffect",
                effectName: intent.slots.effectName,
                layerRef: intent.slots.targetLayer || "selected",
            });
        }

        if (intent.type === IntentType.CREATE_ANIM && intent.slots.animType) {
            ops.push({
                op: "createAnim",
                animType: intent.slots.animType,
                layerRef: intent.slots.targetLayer || "selected",
            });
        }

        if (intent.type === IntentType.STYLE_COMBO && intent.slots.styleName) {
            ops.push({
                op: "styleCombo",
                styleName: intent.slots.styleName,
            });
        }

        // 混合任务中的 AE 部分：从 rawInput 中提取效果
        if (intent.type === IntentType.SILHOUETTE_TASK) {
            const aePart = this.extractAEPrefix(intent.rawInput);
            if (aePart) {
                // 从 aePart 提取效果名
                for (const pattern of AE_EFFECT_KEYWORDS) {
                    const match = aePart.match(pattern);
                    if (match) {
                        ops.push({
                            op: "addEffect",
                            effectName: match[0],
                            layerRef: "selected",
                        });
                        break;
                    }
                }
            }
        }

        return ops;
    }

    // ------------------------------------------------------------------
    // 生成 Silhouette 操作
    // ------------------------------------------------------------------
    private generateSilhouetteOps(intent: Intent): SilhouetteOperation[] {
        const taskType = intent.slots.silhouetteTask;
        if (!taskType) return [];

        const ops: SilhouetteOperation[] = [];

        switch (taskType) {
            case "roto":
                ops.push({
                    taskType: "roto",
                    shapeType: intent.slots.effectName === "bezier" ? "bezier" : "x-spline",
                    tolerance: 1.0,
                    keyframes: 5,
                    outputFormat: "exr",
                    target: intent.slots.rotoTarget,
                    tracking: intent.slots.trackType === "point" ? "point" : "planar",
                });
                break;

            case "track":
                ops.push({
                    taskType: "track",
                    trackType: (intent.slots.trackType as "planar" | "point") || "planar",
                    searchArea: 21,
                    accuracy: "medium",
                    outputFormat: "ae",
                });
                break;

            case "paint":
                ops.push({
                    taskType: "paint",
                    paintMode: "clone",
                    brushSize: 25,
                    brushHardness: 0.5,
                    outputFormat: "png",
                });
                break;

            case "export":
                ops.push({
                    taskType: "export",
                    outputFormat: "ae",
                });
                break;
        }

        return ops;
    }

    // ------------------------------------------------------------------
    // 生成降级策略
    // ------------------------------------------------------------------
    private generateFallback(intent: Intent): FallbackStrategy {
        const taskType = intent.slots.silhouetteTask;

        switch (taskType) {
            case "roto":
                return {
                    condition: "Silhouette 不可用或执行失败",
                    aeFallbackOps: [
                        {
                            op: "addEffect",
                            matchName: "ADBE Mask",
                            effectName: "AE 原生遮罩",
                            layerRef: "selected",
                            settings: { maskPath: "手动绘制" },
                        },
                    ],
                    message: "降级到 AE 原生 Mask 工具（精度降低，需手动绘制）",
                };

            case "track":
                return {
                    condition: "Silhouette 不可用或执行失败",
                    aeFallbackOps: [
                        {
                            op: "addEffect",
                            matchName: "ADBE Tracker",
                            effectName: "AE 原生跟踪器",
                            layerRef: "selected",
                            settings: { trackType: "point" },
                        },
                    ],
                    message: "降级到 AE 原生跟踪器（跟踪精度降低）",
                };

            case "paint":
                return {
                    condition: "Silhouette 不可用或执行失败",
                    aeFallbackOps: [
                        {
                            op: "addEffect",
                            matchName: "ADBE Paint",
                            effectName: "AE 原生 Paint",
                            layerRef: "selected",
                            settings: { brushSize: 25 },
                        },
                    ],
                    message: "降级到 AE 原生 Paint 工具（修复质量降低）",
                };

            default:
                return {
                    condition: "Silhouette 不可用",
                    aeFallbackOps: [],
                    message: "无法降级，请安装 Silhouette 或手动操作",
                };
        }
    }

    // ------------------------------------------------------------------
    // 工具方法：判断是否为混合任务
    // ------------------------------------------------------------------
    isHybrid(input: string): boolean {
        const hasSilhouette = SILHOUETTE_KEYWORDS.some(p => p.test(input));
        const hasAE = AE_EFFECT_KEYWORDS.some(p => p.test(input));
        const hasConnector = HYBRID_CONNECTORS.some(p => p.test(input));
        return hasSilhouette && hasAE && hasConnector;
    }

    // ------------------------------------------------------------------
    // 工具方法：拆分混合输入
    // ------------------------------------------------------------------
    splitHybridInput(input: string): { silhouettePart: string; aePart: string } | null {
        for (const connector of HYBRID_CONNECTORS) {
            const match = input.match(connector);
            if (match && match.index !== undefined) {
                const before = input.slice(0, match.index).trim();
                const after = input.slice(match.index + match[0].length).trim();

                const beforeIsSilhouette = SILHOUETTE_KEYWORDS.some(p => p.test(before));
                const afterIsAE = AE_EFFECT_KEYWORDS.some(p => p.test(after));

                if (beforeIsSilhouette && afterIsAE) {
                    return { silhouettePart: before, aePart: after };
                }
            }
        }
        return null;
    }

    // ------------------------------------------------------------------
    // LLM 增强路由
    // ------------------------------------------------------------------

    /**
     * LLM 增强版路由 — 当 LLM 网关可用时，用 LLM 补充理解
     * 失败时自动降级为本地规则路由
     */
    async routeEnhanced(
        intent: Intent,
        context?: ProjectContext
    ): Promise<TaskRoute> {
        const gw = getLLMGateway();
        const mem = getMemoryStore();

        // 1. 先查记忆系统，看是否有相似任务的历史经验
        const experiences = mem.getExperience({
            category: "intent_route",
            taskKeyword: intent.rawInput.slice(0, 50),
            limit: 3,
            minConfidence: 0.6,
        });

        // 2. 如果有高置信度的历史经验，直接复用
        if (experiences.length > 0 && experiences[0].confidence > 0.8) {
            const exp = experiences[0];
            const cachedRoute = exp.content.route as TaskRoute;
            if (cachedRoute && cachedRoute.type) {
                return {
                    ...cachedRoute,
                    reason: `${cachedRoute.reason} (from memory)`,
                    confidence: Math.min(exp.confidence, 0.95),
                };
            }
        }

        // 3. LLM 不可用时降级为本地规则
        if (!gw.isAvailable()) {
            return this.route(intent, context);
        }

        // 4. 用 LLM 增强理解
        try {
            const llmResult = await this.enhanceWithLLM(intent);
            const baseRoute = this.route(intent, context);

            // 如果 LLM 结果与本地结果有差异，取置信度更高的
            const enhanced = this.mergeRouteResults(baseRoute, llmResult);

            // 5. 记录到记忆系统
            mem.remember({
                category: "intent_route",
                key: intent.rawInput.slice(0, 50),
                content: {
                    route: enhanced,
                    intentType: intent.type,
                    rawInput: intent.rawInput,
                },
                tags: [enhanced.type, intent.type],
                confidence: enhanced.confidence,
            });

            return enhanced;
        } catch (e) {
            console.warn("[IntentRouter] LLM 增强失败，降级为本地规则:", e);
            return this.route(intent, context);
        }
    }

    /**
     * 用 LLM 增强意图理解
     */
    private async enhanceWithLLM(intent: Intent): Promise<TaskRoute> {
        const systemPrompt = `你是视频制作意图分析专家。分析用户输入，判断属于哪种任务类型。

输出格式（JSON）:
{
  "type": "ae_only" | "silhouette_only" | "hybrid" | "unknown",
  "silhouette_task": "roto" | "tracking" | "paint" | null,
  "ae_effects": ["发光", "模糊", ...],
  "execution_order": ["silhouette", "ae"],
  "confidence": 0.0-1.0,
  "reason": "一句话说明原因"
}`;

        const result = await chatWithRouting({
            message: `用户输入: "${intent.rawInput}"\n\n本地解析结果:\n- 意图类型: ${intent.type}\n- 置信度: ${intent.confidence}\n- 轮廓任务: ${intent.slots.silhouetteTask || "无"}\n\n请分析并返回增强后的路由结果。`,
            taskType: "intent_classification",
            systemPrompt,
        });

        if (!result.success) {
            throw new Error(result.error);
        }

        return this.parseLLMResponse(result.content, intent);
    }

    /**
     * 解析 LLM 响应为 TaskRoute
     */
    private parseLLMResponse(content: string, intent: Intent): TaskRoute {
        try {
            const jsonMatch = content.match(/\{[\s\S]*\}/);
            if (!jsonMatch) {
                throw new Error("未找到 JSON");
            }
            const parsed = JSON.parse(jsonMatch[0]);

            const type = parsed.type || "unknown";
            const confidence = parsed.confidence || 0.5;
            const reason = parsed.reason || "LLM 分析结果";

            const aeOps: AEOperation[] = [];
            if (parsed.ae_effects && Array.isArray(parsed.ae_effects)) {
                for (const eff of parsed.ae_effects) {
                    aeOps.push({
                        op: "add_effect",
                        effectName: eff,
                    });
                }
            }

            const silhouetteOps: SilhouetteOperation[] = [];
            if (parsed.silhouette_task) {
                silhouetteOps.push({
                    type: parsed.silhouette_task,
                    target: "主体",
                });
            }

            const executionOrder = parsed.execution_order || (
                type === "hybrid"
                    ? ["silhouette", "ae"]
                    : type === "silhouette_only"
                    ? ["silhouette"]
                    : ["ae"]
            );

            return {
                type,
                aeOperations: aeOps.length > 0 ? aeOps : undefined,
                silhouetteOperations: silhouetteOps.length > 0 ? silhouetteOps : undefined,
                executionOrder,
                reason,
                confidence,
            };
        } catch (e) {
            console.warn("[IntentRouter] LLM 响应解析失败:", e);
            return {
                type: "unknown",
                reason: `LLM 响应解析失败: ${(e as Error).message}`,
                confidence: 0.3,
            };
        }
    }

    /**
     * 合并本地规则与 LLM 的路由结果
     */
    private mergeRouteResults(local: TaskRoute, llm: TaskRoute): TaskRoute {
        // 如果置信度相近，优先信任 LLM（语义理解更强）
        if (llm.confidence > local.confidence + 0.1) {
            return llm;
        }

        // 如果本地规则置信度高很多，用本地的
        if (local.confidence > llm.confidence + 0.2) {
            return local;
        }

        // 置信度接近时，取 type 更具体的
        if (local.type === "unknown" && llm.type !== "unknown") {
            return llm;
        }

        // 都有结果时，综合操作列表
        return {
            type: local.type !== "unknown" ? local.type : llm.type,
            aeOperations: local.aeOperations || llm.aeOperations,
            silhouetteOperations: local.silhouetteOperations || llm.silhouetteOperations,
            executionOrder: local.executionOrder || llm.executionOrder,
            fallback: local.fallback || llm.fallback,
            reason: `本地规则 + LLM 增强: ${local.reason} | ${llm.reason}`,
            confidence: Math.max(local.confidence, llm.confidence),
        };
    }
}

// ---------------------------------------------------------------------------
// 单例导出
// ---------------------------------------------------------------------------

export const intentRouter = new IntentRouter();
