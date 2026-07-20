// ============================================================================
// phase4/nlu-parser.ts
// Phase 4 - NLU 意图解析器
//
// 输入：用户自然语言字符串
// 输出：Intent（意图类型 + 置信度 + 槽位）
//
// 实现策略：
//   1. 模式匹配（正则）→ 高置信度
//   2. 关键词映射 → 中置信度
//   3. 回退到 UNKNOWN → 低置信度
// ============================================================================

import {
    Intent,
    IntentType,
    IntentSlots,
    CONFIDENCE_THRESHOLDS,
    ProjectContext,
} from "./types";
import { getLLMGateway, chatWithRouting } from "./llm-gateway";
import { getMemoryStore } from "./memory-store";

/**
 * 意图模式定义
 */
interface IntentPattern {
    type: IntentType;
    patterns: RegExp[];
    /** 命中后的置信度 */
    confidence: number;
    /** 槽位提取规则（从正则捕获组提取） */
    slotExtractor?: (match: RegExpMatchArray, rawInput: string) => IntentSlots;
}

/**
 * 意图模式表（按优先级排序，先匹配的优先）
 *
 * 注意：正则使用全局匹配而非 ^...$，允许在句子中识别
 */
const INTENT_PATTERNS: IntentPattern[] = [
    // ---- 添加效果 ----
    {
        type: IntentType.ADD_EFFECT,
        confidence: 0.85,
        patterns: [
            // "加一个高斯模糊" → effectName="高斯模糊"
            // "加个模糊" → effectName="模糊"
            // "添加glow" → effectName="glow"
            /(?:加(?:一个|[个一])?|添加|来[个一]?|apply\s+)(?:\s*一个)?\s*([^\s,，。.!！?？的]{1,15})(?:效果|特效)?/,
            /(?:加[个一]?|添加)\s*(\S{1,15}?)(?=\s*(?:到|给|for|to))/i,
            // "做一个发光效果" → effectName="发光效果"
            // 只匹配包含效果相关词汇的输入
            /做[个一]?\s*(.*?发光|.*?模糊|.*?粒子|.*?噪波|.*?渐变|.*?抠像|.*?颜色键|.*?glow|.*?blur|.*?particle|.*?noise|.*?ramp)(?:效果|特效)?/,
        ],
        slotExtractor: (m) => ({ effectName: m[1]?.trim() }),
    },

    // ---- 创建动画 ----
    {
        type: IntentType.CREATE_ANIM,
        confidence: 0.85,
        patterns: [
            /做[个一]?\s*(\S{1,15}?(?:动画|动效|入场|出场|过渡))/,
            /加[个一]?\s*(\S{1,15}?(?:入场|出场|过渡|动画))/,
            /(\S{1,8}?)弹(?:入|出|落)/,
            /创建\s*(?:弹性|缓动)\s*(\S{1,10})/,
            /(?:create|make)\s+(?:a\s+)?(\S+)\s+(?:animation|transition)/i,
            /(\S+?)\s*(?:bounce|spring|fade|slide)\s*(?:in|out)/i,
        ],
        slotExtractor: (m, raw) => ({ animType: m[1]?.trim(), effectName: extractEffectFromAnim(raw) }),
    },

    // ---- 调整参数 ----
    {
        type: IntentType.ADJUST_PARAM,
        confidence: 0.82,
        patterns: [
            /(\S{1,10}?)\s*(?:调[大高小低]|加[强大弱]|变[大大小低]|改[变大大小低])/,
            /(\S{1,10}?)\s*再\s*(?:强|弱|大|小|多|少)\s*(?:一点|些)/,
            /(\S{1,10}?)\s*偏\s*(\S{1,5})/,
            /(?:调[节整]|set|adjust)\s+(\S{1,15})\s+(?:to|为|成)?\s*(\d+(?:\.\d+)?|%|一点|一些)/i,
        ],
        slotExtractor: (m, raw) => {
            const slots: IntentSlots = { paramName: m[1]?.trim() };
            const amt = m[2]?.trim();
            if (amt) {
                slots.adjustAmount = amt;
                if (/大|强|多|高/.test(amt) || /^\d/.test(amt)) {
                    slots.adjustDirection = "increase";
                } else if (/小|弱|少|低/.test(amt)) {
                    slots.adjustDirection = "decrease";
                } else {
                    slots.adjustDirection = "set";
                }
            } else {
                if (/调[大高强]/.test(raw)) slots.adjustDirection = "increase";
                else if (/调[小低弱]/.test(raw)) slots.adjustDirection = "decrease";
                else slots.adjustDirection = "set";
            }
            return slots;
        },
    },

    // ---- 创建图层 ----
    {
        type: IntentType.CREATE_LAYER,
        confidence: 0.88,
        patterns: [
            /建(?:一个|[个一])?\s*(合成|composition|comp)/i,
            /创建\s*(?:一个)?\s*(合成|空对象|调整层|固态层|文字层|形状层|shape|solid|adjustment|null|text)/i,
            /加[个一]?\s*(调整层|空对象|固态层|文字层|形状层|shape|solid|adjustment|null|text)/i,
            /(?:create|add|new)\s+(?:a\s+)?(composition|comp|solid|adjustment|null|text|shape)/i,
        ],
        slotExtractor: (m) => {
            const layerType = m[1]?.trim() || "";
            // 把"合成"统一成"composition"
            let normalized = layerType;
            if (/合成|comp/i.test(layerType)) normalized = "composition";
            else if (/空|null/i.test(layerType)) normalized = "null";
            else if (/调整|adjustment/i.test(layerType)) normalized = "adjustment";
            else if (/固态|solid/i.test(layerType)) normalized = "solid";
            else if (/文字|text/i.test(layerType)) normalized = "text";
            else if (/形状|shape/i.test(layerType)) normalized = "shape";
            return { targetLayer: normalized };
        },
    },

    // ---- 风格化组合 ----
    {
        type: IntentType.STYLE_COMBO,
        confidence: 0.80,
        patterns: [
            // "做一个赛博朋克风格" → styleName="赛博朋克"（"一个"和"风格"作为终止词，不进入捕获组）
            /做(?:一个|[个一])?\s*(\S{1,10}?)\s*风格/,
            // "赛博朋克风格" → styleName="赛博朋克"
            /(\S{1,10}?)\s*风格/,
            /(\S{1,10}?)\s*(?:效果组合|组合效果)/,
            // 兜底："电影感"、"复古调"等以"感/调"结尾
            /做(?:一个|[个一])?\s*(\S{1,10}?(?:感|调))/,
            /(?:apply|create|make)\s+(?:a\s+)?(\S+)\s+style/i,
        ],
        slotExtractor: (m) => ({ styleName: m[1]?.trim() }),
    },

    // ---- Silhouette 遮罩/跟踪任务 ----
    {
        type: IntentType.SILHOUETTE_TASK,
        confidence: 0.88,
        patterns: [
            // Roto/遮罩相关
            /(?:扣|抠|扣出|抠出|扣掉|抠掉)\s*([^\s,，。.!！?？的]{1,10})/,
            /做(?:个|一个)?\s*([^\s,，。.!！?？的]{1,10}?)\s*(?:遮罩|蒙版|mask|roto)/i,
            /(?:遮罩|蒙版|mask|roto)\s*(?:扣|抠|做|生成)/i,
            /(?:自动|自动)?\s*(?:roto|rotoscope|rotoscoping)/i,
            /(?:人物|角色|主体|前景|背景)\s*(?:扣|抠|分离|提取)/,
            // 跟踪相关
            /(?:跟踪|追踪|track|tracking)\s*(?:这个|那个|物体|人物|点|平面)?/,
            /(?:平面|点|paint)\s*(?:跟踪|追踪)/,
            /做(?:个|一个)?\s*(?:跟踪|追踪)\s*(?:点|线|面)?/,
            // Paint 修复
            /(?:修掉|擦掉|去除|移除|修复)\s*([^\s,，。.!！?？的]{1,10})/,
            /(?:paint|修复|擦除|clone|仿制图章)/,
            // Silhouette 软件名直接触发
            /silhouette/i,
        ],
        slotExtractor: (m, raw) => {
            const slots: IntentSlots = {};
            const lower = raw.toLowerCase();

            // 判断任务类型
            if (/(?:扣|抠|遮罩|蒙版|mask|roto|rotoscope)/i.test(raw)) {
                slots.silhouetteTask = "roto";
                // 提取目标
                const targetMatch = raw.match(/(?:扣|抠|做.*?遮罩|做.*?蒙版)\s*([^\s,，。.!！?？的]{1,10})/);
                if (targetMatch) {
                    slots.rotoTarget = targetMatch[1];
                } else if (/人物|角色|人/.test(raw)) {
                    slots.rotoTarget = "person";
                } else if (/背景/.test(raw)) {
                    slots.rotoTarget = "background";
                }
                // 形状类型
                if (/x-spline|xspline|x样条/i.test(raw)) {
                    slots.effectName = "x-spline";
                } else if (/bezier|贝塞尔|贝兹/i.test(raw)) {
                    slots.effectName = "bezier";
                }
            } else if (/(?:跟踪|追踪|track)/i.test(raw)) {
                slots.silhouetteTask = "track";
                if (/平面|planar/i.test(raw)) {
                    slots.trackType = "planar";
                } else if (/点|point/i.test(raw)) {
                    slots.trackType = "point";
                } else if (/paint/i.test(raw)) {
                    slots.trackType = "paint";
                } else {
                    slots.trackType = "planar"; // 默认平面跟踪
                }
            } else if (/(?:修|擦|paint|修复|去除|移除|clone)/i.test(raw)) {
                slots.silhouetteTask = "paint";
                if (/clone|仿制图章|克隆/i.test(raw)) {
                    slots.effectName = "clone";
                } else if (/修复|repair/i.test(raw)) {
                    slots.effectName = "repair";
                } else if (/擦除|erase/i.test(raw)) {
                    slots.effectName = "erase";
                }
            } else if (/silhouette/i.test(raw)) {
                // 只提到软件名，默认 roto 任务
                slots.silhouetteTask = "roto";
            }

            // 输出格式
            if (/png/i.test(raw)) slots.outputFormat = "png";
            else if (/tiff|tif/i.test(raw)) slots.outputFormat = "tiff";
            else if (/exr/i.test(raw)) slots.outputFormat = "exr";
            else if (/json/i.test(raw)) slots.outputFormat = "json";

            return slots;
        },
    },

    // ---- 逆向分析 ----
    {
        type: IntentType.REVERSE_ANALYZE,
        confidence: 0.85,
        patterns: [
            /(?:这个|这段)(?:效果|视频|动画)\s*(?:怎么|如何)?\s*(?:做|实现)/,
            /分析(?:一下)?\s*(?:这个|这段)?\s*(?:视频|效果|动画)/,
            /逆向(?:分析|还原)/,
            /(?:how|how to)\s+(?:did|did they|to)\s+(?:make|create|do)\s+(?:this|that)/i,
            /reverse\s+(?:engineer|analyze)/i,
        ],
        slotExtractor: () => ({}),
    },
];

/**
 * 从动画描述中提取效果名
 * 例如 "做弹入动画" → 提取 effectName="弹入"
 */
function extractEffectFromAnim(raw: string): string | undefined {
    const m = raw.match(/(?:做|加|创建)\s*(?:个一)?\s*(\S{1,8}?)\s*(?:动画|动效|入场|出场|过渡)/);
    return m?.[1]?.trim();
}

/**
 * 提取目标图层（"给文字加..."、"在图层1上加..."、"选中的...")
 */
function extractTargetLayer(rawInput: string): string | undefined {
    // "给X加效果" 模式
    const m1 = rawInput.match(/(?:给|为|在)\s*([^\s,，。.!！?？]+?)\s*(?:加|添加|来)/);
    if (m1) {
        const target = m1[1].trim();
        if (/文字|text/i.test(target)) return "text";
        if (/图层\d+|layer\s*\d+/i.test(target)) return target;
        if (/选中|selected/i.test(target)) return "selected";
        if (/调整层/i.test(target)) return "adjustment";
        return target;
    }
    // "选中的" 模式
    if (/选中|selected/i.test(rawInput)) return "selected";
    // "当前图层" 模式
    if (/当前|current/i.test(rawInput)) return "current";
    return undefined;
}

/**
 * 提取颜色描述
 */
function extractColor(rawInput: string): string | undefined {
    const colorPatterns = [
        "暖色", "冷色", "暖金", "橙色", "红色", "黄色",
        "青色", "蓝色", "紫色", "品红", "绿色",
        "warm", "cool", "orange", "red", "yellow",
        "cyan", "blue", "purple", "magenta", "green",
    ];
    for (const c of colorPatterns) {
        if (rawInput.includes(c)) return c;
    }
    return undefined;
}

/**
 * 提取时间描述
 */
function extractTemporal(rawInput: string): string | undefined {
    const m = rawInput.match(/(?:在|at|from|to)?\s*(开头|结尾|中间|start|end|middle|\d+\s*(?:秒|s))/i);
    return m?.[1]?.trim();
}

/**
 * NLU 解析器
 */
export class NLUParser {
    /**
     * 解析用户输入
     * @param input 用户自然语言输入
     * @param context 项目上下文（可选）
     */
    parse(input: string, context?: ProjectContext): Intent {
        const trimmed = input.trim();
        if (!trimmed) {
            return {
                type: IntentType.UNKNOWN,
                confidence: 0,
                slots: {},
                rawInput: input,
            };
        }

        // 1. 模式匹配
        for (const pattern of INTENT_PATTERNS) {
            for (const regex of pattern.patterns) {
                const match = trimmed.match(regex);
                if (match) {
                    const slots = pattern.slotExtractor
                        ? pattern.slotExtractor(match, trimmed)
                        : {};

                    // 提取通用槽位
                    if (!slots.targetLayer) slots.targetLayer = extractTargetLayer(trimmed);
                    if (!slots.color) slots.color = extractColor(trimmed);
                    if (!slots.temporal) slots.temporal = extractTemporal(trimmed);

                    // 利用上下文补全
                    if (context?.activeCompName && !slots.targetLayer) {
                        // 默认目标 = 选中图层（如果有）
                        if (context.selectedLayers && context.selectedLayers.length > 0) {
                            slots.targetLayer = "selected";
                        }
                    }

                    return {
                        type: pattern.type,
                        confidence: pattern.confidence,
                        slots,
                        rawInput: input,
                        matchedPattern: regex.source,
                    };
                }
            }
        }

        // 2. 关键词回退（如果是模糊输入，降低置信度）
        const lower = trimmed.toLowerCase();
        if (/模糊|glow|blur|发光|辉光|粒子|文字|动画/.test(lower)) {
            return {
                type: IntentType.ADD_EFFECT,
                confidence: 0.55,
                slots: { effectName: trimmed, targetLayer: extractTargetLayer(trimmed) },
                rawInput: input,
            };
        }

        // 3. 完全未识别
        return {
            type: IntentType.UNKNOWN,
            confidence: 0.2,
            slots: {},
            rawInput: input,
        };
    }

    /**
     * 检查是否需要追问
     */
    needsClarification(intent: Intent): boolean {
        if (intent.type === IntentType.UNKNOWN) return false; // 未知意图直接走手动模式
        return intent.confidence < CONFIDENCE_THRESHOLDS.NO_CLARIFICATION;
    }

    // ------------------------------------------------------------------
    // LLM 混合增强
    // ------------------------------------------------------------------

    /**
     * LLM 增强版解析 — 先用本地正则，LLM 可用时补充理解
     * 失败时自动降级为纯本地解析
     */
    async parseEnhanced(
        input: string,
        context?: ProjectContext
    ): Promise<Intent> {
        const localIntent = this.parse(input, context);
        const gw = getLLMGateway();
        const mem = getMemoryStore();

        // 1. 查记忆系统，看是否有相似输入的历史经验
        const experiences = mem.getExperience({
            category: "nlu_parse",
            taskKeyword: input.slice(0, 50),
            limit: 3,
            minConfidence: 0.7,
        });

        if (experiences.length > 0 && experiences[0].confidence > 0.85) {
            const exp = experiences[0];
            const cached = exp.content.intent as Intent;
            if (cached && cached.type) {
                return {
                    ...cached,
                    rawInput: input,
                    confidence: Math.min(exp.confidence, 0.95),
                    matchedPattern: `${cached.matchedPattern || ""} (memory)`,
                };
            }
        }

        // 2. 本地解析置信度已很高，不需要 LLM
        if (localIntent.confidence >= 0.85) {
            return localIntent;
        }

        // 3. LLM 不可用时降级
        if (!gw.isAvailable()) {
            return localIntent;
        }

        // 4. 用 LLM 增强低置信度的解析
        try {
            const llmIntent = await this.enhanceWithLLM(input, localIntent);

            // 合并结果：取置信度更高的
            const merged = this.mergeIntents(localIntent, llmIntent);

            // 5. 记录到记忆系统
            mem.remember({
                category: "nlu_parse",
                key: input.slice(0, 50),
                content: { intent: merged },
                tags: [merged.type],
                confidence: merged.confidence,
            });

            return merged;
        } catch (e) {
            console.warn("[NLUParser] LLM 增强失败，降级为本地解析:", e);
            return localIntent;
        }
    }

    /**
     * 用 LLM 增强意图理解
     */
    private async enhanceWithLLM(
        input: string,
        localIntent: Intent
    ): Promise<Intent> {
        const systemPrompt = `你是视频制作意图分析专家。分析用户输入，返回意图类型和槽位。

意图类型:
- INTENT_ADD_EFFECT: 添加效果（发光/模糊/粒子等）
- INTENT_CREATE_ANIM: 创建动画（弹入/淡入/滑入等）
- INTENT_ADJUST_PARAM: 调整参数（调大/调小/设置值）
- INTENT_CREATE_LAYER: 创建图层（合成/空对象/调整层等）
- INTENT_STYLE_COMBO: 风格组合（赛博朋克/电影感等）
- INTENT_SILHOUETTE_TASK: Silhouette任务（抠像/跟踪/修复）
- INTENT_REVERSE_ANALYZE: 逆向分析
- INTENT_UNKNOWN: 未知

输出格式（JSON）:
{
  "type": "INTENT_ADD_EFFECT",
  "confidence": 0.9,
  "slots": {
    "effectName": "发光",
    "targetLayer": "文字层",
    "color": "蓝色",
    "temporal": "开头"
  },
  "reason": "用户想给文字层加蓝色发光效果"
}`;

        const result = await chatWithRouting({
            message: `用户输入: "${input}"\n\n本地解析结果:\n- 意图类型: ${localIntent.type}\n- 置信度: ${localIntent.confidence}\n- 槽位: ${JSON.stringify(localIntent.slots)}\n\n请分析并返回增强后的结果。`,
            taskType: "intent_classification",
            systemPrompt,
        });

        if (!result.success) {
            throw new Error(result.error);
        }

        return this.parseLLMIntent(result.content, input);
    }

    /**
     * 解析 LLM 返回的 JSON 为 Intent
     */
    private parseLLMIntent(content: string, rawInput: string): Intent {
        try {
            const match = content.match(/\{[\s\S]*\}/);
            if (!match) {
                throw new Error("未找到 JSON");
            }
            const parsed = JSON.parse(match[0]);

            const typeStr = parsed.type || "INTENT_UNKNOWN";
            const type = this.mapIntentType(typeStr);
            const confidence = Math.min(Math.max(parsed.confidence || 0.5, 0), 1);
            const slots = parsed.slots || {};

            return {
                type,
                confidence,
                slots: slots as IntentSlots,
                rawInput,
                matchedPattern: "llm_enhanced",
            };
        } catch (e) {
            console.warn("[NLUParser] LLM 响应解析失败:", e);
            return {
                type: IntentType.UNKNOWN,
                confidence: 0.3,
                slots: {},
                rawInput,
                matchedPattern: "llm_parse_error",
            };
        }
    }

    /**
     * 将字符串映射为 IntentType 枚举
     */
    private mapIntentType(typeStr: string): IntentType {
        const upper = typeStr.toUpperCase().replace("INTENT_", "");
        const map: Record<string, IntentType> = {
            ADD_EFFECT: IntentType.ADD_EFFECT,
            CREATE_ANIM: IntentType.CREATE_ANIM,
            ADJUST_PARAM: IntentType.ADJUST_PARAM,
            CREATE_LAYER: IntentType.CREATE_LAYER,
            STYLE_COMBO: IntentType.STYLE_COMBO,
            SILHOUETTE_TASK: IntentType.SILHOUETTE_TASK,
            REVERSE_ANALYZE: IntentType.REVERSE_ANALYZE,
            UNKNOWN: IntentType.UNKNOWN,
        };
        return map[upper] || IntentType.UNKNOWN;
    }

    /**
     * 合并本地解析与 LLM 解析结果
     */
    private mergeIntents(local: Intent, llm: Intent): Intent {
        // LLM 置信度显著更高时，用 LLM 结果
        if (llm.confidence > local.confidence + 0.15) {
            return {
                ...llm,
                slots: { ...local.slots, ...llm.slots },
                matchedPattern: `local+llm (${local.matchedPattern}→${llm.matchedPattern})`,
            };
        }

        // 本地置信度更高时，保留本地类型但补充 LLM 槽位
        if (local.confidence >= llm.confidence) {
            return {
                ...local,
                slots: { ...local.slots, ...llm.slots },
                confidence: Math.max(local.confidence, llm.confidence * 0.9),
            };
        }

        // 置信度接近时，如果本地是 UNKNOWN 但 LLM 有结果，用 LLM
        if (local.type === IntentType.UNKNOWN && llm.type !== IntentType.UNKNOWN) {
            return llm;
        }

        // 默认合并
        return {
            type: local.type !== IntentType.UNKNOWN ? local.type : llm.type,
            confidence: Math.max(local.confidence, llm.confidence),
            slots: { ...local.slots, ...llm.slots },
            rawInput: local.rawInput,
            matchedPattern: `merged (${local.matchedPattern}+${llm.matchedPattern})`,
        };
    }
}

/**
 * 单例实例
 */
export const nluParser = new NLUParser();
