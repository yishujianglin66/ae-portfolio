// ============================================================================
// phase4/intent-to-report.ts
// Phase 4 → Phase 3 衔接层
//
// 把 NLU 层的 Intent + EffectDescription 转换为 Phase 3 的 AnalysisReport
// 让整个管线（自然语言 → NLU → 推理 → 编译 → MCP）能端到端运行
//
// 输出格式严格匹配 src/phase3/report-to-ops.ts 中定义的 AnalysisReport schema
// ============================================================================

import { Intent, IntentType, EffectDescription, ProjectContext, VocabRef } from "./types";
import { getStyleRecipe } from "./effect-description-parser";

/**
 * Phase 3 的 AnalysisReport 类型（与 src/phase3/report-to-ops.ts 完全对齐）
 *
 * 字段说明：
 *   - effects[].effect_name: 用户友好的效果名（如 "Gaussian Blur"），会被 findByName 查找
 *   - parameters[].parameter: 参数名（如 "Blurriness"）
 *   - keyframes[].parameter: 关键帧属性名
 *   - keyframes[].keyframes: KeyframeSpec 数组，每个有 frame/value/easing/bezier
 */
export interface AnalysisReport {
    metadata: {
        video_file?: string;
        duration?: string;
        frame_rate?: number;
        resolution?: string;
        analysis_date?: string;
        analyzer_version?: string;
        // 扩展字段（不影响 Phase 3 解析）
        source?: string;
        confidence?: number;
        description?: string;
    };
    visual_features?: Array<{
        term_id: string;
        term_name: string;
        time_range?: [number, number];
        intensity?: number;
        confidence?: number;
    }>;
    effects?: Array<{
        effect_id: string;
        effect_name: string;
        start_frame?: number;
        end_frame?: number;
        confidence?: number;
        evidence?: string[];
    }>;
    parameters?: Array<{
        effect_id: string;
        parameter: string;
        value: number | string | boolean | number[];
        value_range?: [number, number];
        confidence?: number;
    }>;
    timeline?: Array<{
        effect_id: string;
        start_frame: number;
        end_frame: number;
        duration_frames?: number;
        duration_seconds?: number;
    }>;
    keyframes?: Array<{
        effect_id: string;
        parameter: string;
        keyframes: Array<{
            frame: number;
            value: number | number[];
            easing: string;
            bezier?: [number, number, number, number];
        }>;
        keyframe_count?: number;
    }>;
    confidence?: {
        overall?: number;
        breakdown?: Record<string, number>;
        notes?: string[];
    };
}

/**
 * 默认合成参数
 */
const DEFAULT_COMP = {
    width: 1920,
    height: 1080,
    frameRate: 30,
    duration: 10,
};

/**
 * 把 VocabRef 转换为 EffectEntry
 * effect_name 字段会被 report-to-ops.ts 中的 findByName 查找
 * 所以必须是用户友好的英文名（如 "Gaussian Blur"），而不是 matchName
 */
function vocabRefToEffectEntry(ref: VocabRef): AnalysisReport["effects"]![0] {
    // 使用 suggestedEffect 对应的 displayName 作为 effect_name
    // 例如 suggestedEffect="ADBE Gaussian Blur 2" → effect_name="Gaussian Blur"
    const displayName = matchNameToDisplayName(ref.suggestedEffect || ref.name);

    return {
        effect_id: ref.id,
        effect_name: displayName,
        confidence: ref.confidence,
        evidence: [`来自词汇: ${ref.name} (matched: ${ref.matchedKeyword})`],
    };
}

/**
 * matchName → 显示名（用于 findByName 查找）
 */
function matchNameToDisplayName(matchName: string): string {
    const map: Record<string, string> = {
        "ADBE Gaussian Blur 2": "Gaussian Blur",
        "ADBE Directional Blur": "Directional Blur",
        "CC Radial Blur": "CC Radial Blur",
        "ADBE Camera Lens Blur": "Camera Lens Blur",
        "ADBE Fast Box Blur": "Fast Box Blur",
        "ADBE Compound Blur": "Compound Blur",
        "ADBE Glo2": "Glow",
        "ADBE Deep Glow": "Deep Glow",
        "ACP Optical Flares": "Optical Flares",
        "CC Light Rays": "CC Light Rays",
        "ADBE Starglow": "Starglow",
        "ADBE Turbulent Displace": "Turbulent Displace",
        "ADBE Wave Warp": "Wave Warp",
        "ADBE Liquify": "Liquify",
        "CC Power Pin": "CC Power Pin",
        "ADBE Optics Compensation": "Optics Compensation",
        "ADBE Color Balance": "Color Balance",
        "ADBE Curves": "Curves",
        "ADBE Black & White": "Black & White",
        "ADBE Colorista": "Colorista",
        "ACP Particular": "Particular",
        "ACP Form": "Form",
        "ADBE Transform": "Transform",
        "ADBE Opacity": "Opacity",
        "ADBE Text": "Text",
    };
    return map[matchName] || matchName;
}

/**
 * 根据效果 matchName 推断默认参数
 */
function inferDefaultParams(
    ref: VocabRef,
    intensityScale: number,
): Array<{ parameter: string; value: number; value_range: [number, number] }> {
    const params: Array<{ parameter: string; value: number; value_range: [number, number] }> = [];

    switch (ref.suggestedEffect) {
        case "ADBE Gaussian Blur 2":
            params.push({ parameter: "Blurriness", value: 25 * intensityScale, value_range: [5, 50] });
            break;
        case "ADBE Directional Blur":
            params.push({ parameter: "Blur Length", value: 50 * intensityScale, value_range: [10, 100] });
            params.push({ parameter: "Direction", value: 0, value_range: [0, 360] });
            break;
        case "ADBE Glo2":
            params.push({ parameter: "Glow Threshold", value: 40 * intensityScale, value_range: [20, 80] });
            params.push({ parameter: "Glow Radius", value: 50 * intensityScale, value_range: [10, 100] });
            params.push({ parameter: "Glow Intensity", value: 2 * intensityScale, value_range: [1, 8] });
            break;
        case "ADBE Camera Lens Blur":
            params.push({ parameter: "Blur Radius", value: 30 * intensityScale, value_range: [10, 100] });
            break;
        case "ACP Optical Flares":
            params.push({ parameter: "Brightness", value: 100 * intensityScale, value_range: [50, 200] });
            break;
        case "CC Light Rays":
            params.push({ parameter: "Intensity", value: 100 * intensityScale, value_range: [50, 200] });
            params.push({ parameter: "Ray Length", value: 100 * intensityScale, value_range: [50, 200] });
            break;
        case "ADBE Starglow":
            params.push({ parameter: "Threshold", value: 40 * intensityScale, value_range: [10, 80] });
            params.push({ parameter: "Intensity", value: 50 * intensityScale, value_range: [10, 200] });
            break;
        case "ADBE Turbulent Displace":
            params.push({ parameter: "Amount", value: 50 * intensityScale, value_range: [10, 200] });
            params.push({ parameter: "Size", value: 50, value_range: [10, 100] });
            break;
        case "ADBE Wave Warp":
            params.push({ parameter: "Wave Height", value: 30 * intensityScale, value_range: [1, 100] });
            params.push({ parameter: "Wave Width", value: 100, value_range: [10, 500] });
            break;
        case "ACP Particular":
            params.push({ parameter: "Particles/sec", value: 100 * intensityScale, value_range: [10, 500] });
            break;
        case "ADBE Opacity":
            params.push({ parameter: "Opacity", value: 100, value_range: [0, 100] });
            break;
        case "ADBE Color Balance":
            // 简化
            break;
    }

    return params;
}

/**
 * Intent + EffectDescription → AnalysisReport
 *
 * 这是 Phase 4 → Phase 3 的关键转换
 */
export function intentToReport(
    intent: Intent,
    description: EffectDescription,
    context?: ProjectContext,
): AnalysisReport {
    const effects: AnalysisReport["effects"] = [];
    const parameters: AnalysisReport["parameters"] = [];
    const keyframes: AnalysisReport["keyframes"] = [];
    const visual_features: AnalysisReport["visual_features"] = [];

    // 综合置信度
    let totalConfidence = intent.confidence;

    // 提取强度因子（默认 1.0）
    const intensityScale = description.intensityKeywords[0]?.scale || 1.0;

    // 1. 处理效果关键词
    // 注意：VT-601+（文字动画）和 KF-010+（关键帧动画）是动画描述，不应作为效果添加
    // 只有 VT-001~VT-599 是真正的"效果"
    for (const ref of description.effectKeywords) {
        // 跳过动画类词汇（VT-601+ 和 KF-010+）
        if (ref.id.startsWith("VT-6") || ref.id.startsWith("KF-")) {
            // 这些是动画描述，在步骤3处理
            continue;
        }

        effects.push(vocabRefToEffectEntry(ref));
        visual_features.push({
            term_id: ref.id,
            term_name: ref.name,
            confidence: ref.confidence,
        });

        // 推断默认参数
        if (ref.suggestedEffect) {
            const params = inferDefaultParams(ref, intensityScale);
            for (const p of params) {
                parameters.push({
                    effect_id: ref.id,
                    parameter: p.parameter,
                    value: p.value,
                    value_range: p.value_range,
                    confidence: ref.confidence * 0.85,
                });
            }
        }

        // 如果有颜色，添加颜色参数
        if (description.colorKeywords.length > 0) {
            const color = description.colorKeywords[0];
            parameters.push({
                effect_id: ref.id,
                parameter: "Color",
                value: color.rgb,
                confidence: 0.75,
            });
        }
    }

    // 2. 处理风格关键词（如果是 STYLE_COMBO 意图）
    if (intent.type === IntentType.STYLE_COMBO && intent.slots.styleName) {
        const recipe = getStyleRecipe(intent.slots.styleName);
        if (recipe) {
            // 把配方中的效果也加入
            for (const vid of recipe.effectIds) {
                if (!effects.find((e) => e.effect_id === vid)) {
                    const ref: VocabRef = {
                        id: vid,
                        name: vid,
                        matchedKeyword: intent.slots.styleName,
                        suggestedEffect: getVocabEffectForId(vid),
                        confidence: 0.75,
                    };
                    effects.push(vocabRefToEffectEntry(ref));
                    visual_features.push({
                        term_id: vid,
                        term_name: vid,
                        confidence: 0.75,
                    });

                    if (ref.suggestedEffect) {
                        const params = inferDefaultParams(ref, intensityScale);
                        for (const p of params) {
                            parameters.push({
                                effect_id: ref.id,
                                parameter: p.parameter,
                                value: p.value,
                                value_range: p.value_range,
                                confidence: 0.65,
                            });
                        }
                    }
                }
            }
        }
    }

    // 3. 处理动画类型（CREATE_ANIM 意图）
    if (intent.type === IntentType.CREATE_ANIM && intent.slots.animType) {
        const animType = intent.slots.animType;
        const kf = inferKeyframesForAnim(animType, context);
        if (kf) {
            keyframes.push(kf);
            totalConfidence = Math.max(totalConfidence, 0.8);
        }
    }

    // 4. 处理参数调整（ADJUST_PARAM 意图）
    if (intent.type === IntentType.ADJUST_PARAM && intent.slots.paramName) {
        // 把调整作为参数条目加入
        parameters.push({
            effect_id: "ADJUST",
            parameter: intent.slots.paramName,
            value: intent.slots.adjustAmount as any || (intent.slots.adjustDirection === "increase" ? 1.5 : 0.7),
            confidence: 0.7,
        });
    }

    // 5. 综合置信度计算
    if (effects.length > 0) {
        const avgEffectConfidence = effects.reduce((sum, e) => sum + (e.confidence || 0), 0) / effects.length;
        totalConfidence = (totalConfidence + avgEffectConfidence) / 2;
    }

    // 6. 构建 metadata
    const metadata: AnalysisReport["metadata"] = {
        video_file: `nlu_input`,
        duration: `${context?.compDuration || DEFAULT_COMP.duration}s`,
        frame_rate: context?.compFrameRate || DEFAULT_COMP.frameRate,
        resolution: `${context?.compResolution?.[0] || DEFAULT_COMP.width}x${context?.compResolution?.[1] || DEFAULT_COMP.height}`,
        analysis_date: new Date().toISOString(),
        analyzer_version: "phase4-nlu-v1",
        source: `nlu:${intent.type}`,
        confidence: Math.min(0.95, totalConfidence),
        description: `NLU解析: ${intent.rawInput}`,
    };

    return {
        metadata,
        visual_features,
        effects,
        parameters,
        timeline: [],
        keyframes,
        confidence: {
            overall: Math.min(0.95, totalConfidence),
            breakdown: {
                intent: intent.confidence,
                effects: effects.length > 0
                    ? effects.reduce((sum, e) => sum + (e.confidence || 0), 0) / effects.length
                    : 0,
            },
        },
    };
}

/**
 * 根据动画类型推断关键帧
 *
 * 返回 AnalysisReport.keyframes[] 格式（与 report-to-ops.ts 期望一致）：
 *   - parameter: 关键帧属性名（如 "Scale", "Opacity"）
 *   - keyframes: KeyframeSpec 数组，每个有 frame/value/easing/bezier
 */
function inferKeyframesForAnim(
    animType: string,
    context?: ProjectContext,
): AnalysisReport["keyframes"]![0] | null {
    const duration = context?.compDuration || 10;
    const fps = context?.compFrameRate || 30;

    // 通用动画：在开头和结尾关键帧
    const startFrame = 0;
    const endFrame = Math.floor(duration * fps);

    // 弹入动画
    if (/弹入|bounce|spring|回弹/.test(animType)) {
        return {
            effect_id: "ANIM",
            parameter: "Scale",
            keyframes: [
                { frame: startFrame, value: 0, easing: "linear" },
                { frame: Math.floor(endFrame * 0.3), value: 110, easing: "ease_out", bezier: [0.34, 1.56, 0.64, 1] },
                { frame: Math.floor(endFrame * 0.5), value: 95, easing: "ease_in_out", bezier: [0.45, 0, 0.55, 1] },
                { frame: Math.floor(endFrame * 0.7), value: 102, easing: "ease_out", bezier: [0.34, 1.56, 0.64, 1] },
                { frame: endFrame, value: 100, easing: "ease_in_out", bezier: [0.45, 0, 0.55, 1] },
            ],
            keyframe_count: 5,
        };
    }

    // 淡入动画
    if (/淡入|fade|渐入/.test(animType)) {
        return {
            effect_id: "ANIM",
            parameter: "Opacity",
            keyframes: [
                { frame: startFrame, value: 0, easing: "linear" },
                { frame: Math.floor(endFrame * 0.3), value: 100, easing: "ease_out", bezier: [0.33, 0, 0.67, 1] },
            ],
            keyframe_count: 2,
        };
    }

    // 滑入动画
    if (/滑入|slide|位移/.test(animType)) {
        return {
            effect_id: "ANIM",
            parameter: "Position",
            keyframes: [
                { frame: startFrame, value: [-200, 540], easing: "linear" },
                { frame: Math.floor(endFrame * 0.4), value: [960, 540], easing: "ease_out", bezier: [0.22, 0.61, 0.36, 1] },
            ],
            keyframe_count: 2,
        };
    }

    // 缩放动画
    if (/缩放|scale/.test(animType)) {
        return {
            effect_id: "ANIM",
            parameter: "Scale",
            keyframes: [
                { frame: startFrame, value: 50, easing: "linear" },
                { frame: Math.floor(endFrame * 0.4), value: 100, easing: "ease_out", bezier: [0.33, 0, 0.67, 1] },
            ],
            keyframe_count: 2,
        };
    }

    // 旋转动画
    if (/旋转|rotate|翻转/.test(animType)) {
        return {
            effect_id: "ANIM",
            parameter: "Rotation",
            keyframes: [
                { frame: startFrame, value: 0, easing: "linear" },
                { frame: endFrame, value: 360, easing: "linear" },
            ],
            keyframe_count: 2,
        };
    }

    // 默认：透明度淡入
    return {
        effect_id: "ANIM",
        parameter: "Opacity",
        keyframes: [
            { frame: startFrame, value: 0, easing: "linear" },
            { frame: Math.floor(endFrame * 0.3), value: 100, easing: "ease_out", bezier: [0.33, 0, 0.67, 1] },
        ],
        keyframe_count: 2,
    };
}

/**
 * 词汇 ID → 建议 matchName
 */
function getVocabEffectForId(vocabId: string): string | undefined {
    const map: Record<string, string> = {
        "VT-001": "ADBE Gaussian Blur 2",
        "VT-004": "ADBE Camera Lens Blur",
        "VT-101": "ADBE Glo2",
        "VT-105": "ADBE Starglow",
        "VT-303": "ADBE Curves",
        "VT-304": "ADBE Curves",
        "VT-306": "ADBE Colorista",
        "VT-504": "ADBE Transform",
    };
    return map[vocabId];
}
