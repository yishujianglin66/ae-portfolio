// ============================================================================
// phase4/clarifier.ts
// Phase 4 - 追问机制
//
// 当 NLU 解析置信度低于阈值时，生成追问请求让用户确认。
// 追问策略：
//   1. 效果名模糊（"模糊"不明确是高斯还是径向）→ 选项追问
//   2. 目标图层未指定 → 选项追问
//   3. 参数调整未指定 → 直接追问
//   4. 风格不明确 → 列出可选风格
// ============================================================================

import {
    Intent,
    IntentType,
    EngineResponse,
    ClarificationRequest,
    ClarificationOption,
    CONFIDENCE_THRESHOLDS,
    EffectDescription,
} from "./types";
import { findVocab } from "./vocabulary-map";
import { getAllStyles } from "./effect-description-parser";

/**
 * 追问生成器
 */
export class Clarifier {
    /**
     * 根据意图生成追问请求
     * @returns 如果需要追问则返回 ClarificationRequest，否则返回 null
     */
    generate(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        // 置信度足够，无需追问
        if (intent.confidence >= CONFIDENCE_THRESHOLDS.NO_CLARIFICATION) return null;

        switch (intent.type) {
            case IntentType.ADD_EFFECT:
                return this.clarifyAddEffect(intent, description);

            case IntentType.CREATE_ANIM:
                return this.clarifyCreateAnim(intent, description);

            case IntentType.ADJUST_PARAM:
                return this.clarifyAdjustParam(intent, description);

            case IntentType.CREATE_LAYER:
                return this.clarifyCreateLayer(intent, description);

            case IntentType.STYLE_COMBO:
                return this.clarifyStyleCombo(intent, description);

            case IntentType.REVERSE_ANALYZE:
                return null; // 逆向分析不需要追问，直接进入分析流程

            case IntentType.UNKNOWN:
            default:
                return null;
        }
    }

    /**
     * 追问：添加效果
     */
    private clarifyAddEffect(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        const slots = intent.slots;

        // 场景1：目标图层未指定
        if (!slots.targetLayer) {
            return {
                question: "请问要在哪个图层上添加效果？",
                options: [
                    { label: "选中的图层", value: "selected", description: "当前选中的图层" },
                    { label: "新建文字层", value: "text", description: "创建一个新的文字层" },
                    { label: "新建固态层", value: "solid", description: "创建一个新的固态层" },
                ],
                slotName: "targetLayer",
            };
        }

        // 场景2：效果名模糊（如"模糊"可能对应多个效果）
        if (slots.effectName) {
            const candidates = findVocab(slots.effectName);
            if (candidates.length > 1) {
                // 多个匹配，追问选择哪一个
                const options: ClarificationOption[] = candidates.slice(0, 4).map((c) => ({
                    label: c.name,
                    value: c.suggestedEffect || c.name,
                    description: `matchName: ${c.suggestedEffect || "未知"}`,
                }));
                return {
                    question: `检测到"${slots.effectName}"可能对应多种效果，请选择：`,
                    options,
                    slotName: "effectName",
                };
            }
            if (candidates.length === 0 && description.effectKeywords.length === 0) {
                // 完全未识别效果
                return {
                    question: `抱歉，"${slots.effectName}"未在词汇库中找到。请选择一种常见效果：`,
                    options: [
                        { label: "高斯模糊", value: "Gaussian Blur", description: "均匀柔化" },
                        { label: "发光", value: "Glow", description: "边缘辉光" },
                        { label: "镜头光斑", value: "Optical Flares", description: "光斑效果" },
                        { label: "粒子", value: "Particular", description: "Trapcode 粒子" },
                    ],
                    slotName: "effectName",
                };
            }
        }

        return null;
    }

    /**
     * 追问：创建动画
     */
    private clarifyCreateAnim(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        const slots = intent.slots;

        if (!slots.targetLayer) {
            return {
                question: "请问要在哪个图层上创建动画？",
                options: [
                    { label: "选中的图层", value: "selected" },
                    { label: "新建文字层", value: "text" },
                    { label: "新建固态层", value: "solid" },
                ],
                slotName: "targetLayer",
            };
        }

        if (!slots.animType && description.effectKeywords.length === 0) {
            return {
                question: "请问要创建什么类型的动画？",
                options: [
                    { label: "弹入", value: "弹入", description: "弹性缓入" },
                    { label: "淡入", value: "淡入", description: "透明度渐入" },
                    { label: "滑入", value: "滑入", description: "位移入场" },
                    { label: "缩放", value: "缩放", description: "缩放渐变" },
                ],
                slotName: "animType",
            };
        }

        return null;
    }

    /**
     * 追问：调整参数
     */
    private clarifyAdjustParam(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        const slots = intent.slots;

        if (!slots.targetLayer) {
            return {
                question: "请问要调整哪个图层的参数？",
                options: [
                    { label: "选中的图层", value: "selected" },
                    { label: "最近添加效果的图层", value: "recent" },
                ],
                slotName: "targetLayer",
            };
        }

        if (!slots.paramName) {
            return {
                question: "请问要调整哪个参数？",
                options: [
                    { label: "模糊度", value: "Blurriness" },
                    { label: "发光强度", value: "Glow Intensity" },
                    { label: "不透明度", value: "Opacity" },
                    { label: "缩放", value: "Scale" },
                ],
                slotName: "paramName",
            };
        }

        return null;
    }

    /**
     * 追问：创建图层
     */
    private clarifyCreateLayer(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        // 创建图层意图相对简单，置信度通常足够
        if (!intent.slots.targetLayer) {
            return {
                question: "请问要创建什么类型的图层？",
                options: [
                    { label: "合成", value: "composition" },
                    { label: "调整层", value: "adjustment" },
                    { label: "空对象", value: "null" },
                    { label: "固态层", value: "solid" },
                ],
                slotName: "targetLayer",
            };
        }
        return null;
    }

    /**
     * 追问：风格化组合
     */
    private clarifyStyleCombo(intent: Intent, description: EffectDescription): ClarificationRequest | null {
        const slots = intent.slots;

        if (!slots.styleName) {
            const styles = getAllStyles();
            return {
                question: "请问要应用什么风格？",
                options: styles.slice(0, 4).map((s) => ({
                    label: s,
                    value: s,
                    description: `${s}风格组合`,
                })),
                slotName: "styleName",
            };
        }

        // 检查风格是否在配方库中
        const allStyles = getAllStyles();
        if (!allStyles.find((s) => s.toLowerCase() === slots.styleName!.toLowerCase())) {
            return {
                question: `检测到风格"${slots.styleName}"，但未找到匹配配方。请选择：`,
                options: [
                    { label: "赛博朋克", value: "赛博朋克" },
                    { label: "电影感", value: "电影感" },
                    { label: "梦幻", value: "梦幻" },
                    { label: "复古", value: "复古" },
                ],
                slotName: "styleName",
            };
        }

        return null;
    }

    /**
     * 把用户的追问回答应用到意图中，更新槽位
     */
    applyAnswer(intent: Intent, answer: string, slotName: string): Intent {
        const updatedSlots = { ...intent.slots };
        (updatedSlots as any)[slotName] = answer;

        // 答复后通常置信度会提升
        const newConfidence = Math.min(0.95, intent.confidence + 0.25);

        return {
            ...intent,
            slots: updatedSlots,
            confidence: newConfidence,
        };
    }
}

/**
 * 单例实例
 */
export const clarifier = new Clarifier();

/**
 * 生成完整的引擎响应（包含追问）
 */
export function buildEngineResponse(
    intent: Intent,
    description: EffectDescription,
    clarify: ClarificationRequest | null,
): EngineResponse {
    if (intent.type === IntentType.UNKNOWN) {
        return {
            understood: false,
            intent,
            effectDescription: description,
            needsClarification: false,
            error: "无法识别您的意图，请尝试更具体的描述。",
        };
    }

    if (clarify) {
        return {
            understood: true,
            intent,
            effectDescription: description,
            needsClarification: true,
            clarificationQuestion: clarify.question,
            clarificationOptions: clarify.options.map((o) => o.label),
        };
    }

    return {
        understood: true,
        intent,
        effectDescription: description,
        needsClarification: false,
    };
}
