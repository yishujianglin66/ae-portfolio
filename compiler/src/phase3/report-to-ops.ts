// ============================================================================
// report-to-ops.ts
// Phase 3 - 决策树解析报告 → 编译器输入 转换层
//
// 用途：将"解析词汇表与推理决策树.md 第八章 8.1 解析报告YAML结构"定义的
//       解析报告转换为 Phase 1 编译器能接受的 CompilerInput
//
// 转换流程：
//   解析报告 → 效果映射 → 参数映射 → 关键帧转换 → 编译器操作列表
//
// 主要函数：
//   reportToOps(report, options) → CompilerInput
//   用于 Phase 3 集成测试和 Phase 4 自然语言理解后端
// ============================================================================

import {
    CompilerInput,
    CompilerMetadata,
    CreateCompOp,
    AddLayerOp,
    AddEffectOp,
    SetKeyframeOp,
    SetPropertyOp,
    EasingType
} from "../types";
import { findByName, EffectMapEntry } from "./effect-name-map";

// ============================================================================
// 解析报告类型定义（对应 8.1 解析报告YAML Schema）
// ============================================================================

export interface VisualFeature {
    term_id: string;
    term_name: string;
    time_range?: [number, number];
    intensity?: number;
    confidence?: number;
}

export interface EffectEntry {
    effect_id: string;
    effect_name: string;
    start_frame?: number;
    end_frame?: number;
    confidence?: number;
    evidence?: string[];
}

export interface ParameterEntry {
    effect_id: string;
    parameter: string;
    value: number | string | boolean | number[];
    value_range?: [number, number];
    confidence?: number;
}

export interface TimelineEntry {
    effect_id: string;
    start_frame: number;
    end_frame: number;
    duration_frames?: number;
    duration_seconds?: number;
}

export interface KeyframeSpec {
    frame: number;
    value: number | number[];
    easing: string;
    bezier?: [number, number, number, number];
}

export interface KeyframeEntry {
    effect_id: string;
    parameter: string;
    keyframes: KeyframeSpec[];
    keyframe_count?: number;
}

export interface AnalysisReport {
    metadata: {
        video_file?: string;
        duration?: string;
        frame_rate?: number;
        resolution?: string;
        analysis_date?: string;
        analyzer_version?: string;
    };
    visual_features?: VisualFeature[];
    effects?: EffectEntry[];
    parameters?: ParameterEntry[];
    timeline?: TimelineEntry[];
    keyframes?: KeyframeEntry[];
    confidence?: {
        overall?: number;
        breakdown?: Record<string, number>;
        notes?: string[];
    };
}

// ============================================================================
// 转换选项
// ============================================================================

export interface ReportToOpsOptions {
    /** 合成名（默认 "Phase3 Output"） */
    compName?: string;
    /** 合成宽度（默认 1920） */
    compWidth?: number;
    /** 合成高度（默认 1080） */
    compHeight?: number;
    /** 合成时长（秒，默认 10） */
    compDuration?: number;
    /** 合成帧率（默认 30；如未指定则从报告metadata.frame_rate推断） */
    compFrameRate?: number;
    /** 目标图层引用（如果指定，效果直接应用到此图层；否则创建一个新的Solid图层） */
    targetLayerRef?: string;
    /** 最低置信度阈值（低于此值的效果将被忽略，默认 0.5） */
    minConfidence?: number;
    /** 是否生成 setProperty 操作（默认 true） */
    generateSetProperty?: boolean;
    /** 是否生成 setKeyframe 操作（默认 true） */
    generateSetKeyframe?: boolean;
    /** 默认图层类型（当需要创建图层时） */
    defaultLayerType?: "solid" | "adjustment";
    /** 默认图层名 */
    defaultLayerName?: string;
}

// ============================================================================
// 内部辅助函数
// ============================================================================

/**
 * easing 字符串 → EasingType
 * 决策树输出的 easing 值映射到编译器的 EasingType
 *
 * 决策树支持的 easing 值（来自 4.3 缓动曲线词汇）：
 *   linear / ease_in / ease_out / ease_in_out / bezier / hold / cubic / quintic / quartic
 *
 * 编译器支持的 EasingType（snake_case）：
 *   linear / ease_in / ease_out / ease_in_out / bezier / hold
 *
 * 兼容输入：camelCase (easeIn/easeOut/easeInOut) 自动归一化为 snake_case
 */
function mapEasingString(easing: string): EasingType {
    if (!easing) return "linear";

    const lower = easing.toLowerCase();
    const map: Record<string, EasingType> = {
        "linear": "linear",
        "ease_in": "ease_in",
        "easein": "ease_in",
        "ease_out": "ease_out",
        "easeout": "ease_out",
        "ease_in_out": "ease_in_out",
        "easeinout": "ease_in_out",
        "bezier": "bezier",
        "hold": "hold",
        "cubic": "ease_in_out",     // cubic近似为ease_in_out
        "quintic": "ease_in_out",   // quintic近似为ease_in_out
        "quartic": "ease_in_out"    // quartic近似为ease_in_out
    };

    return map[lower] || "linear";
}

/**
 * frame → time（秒）
 * @param frame 帧号
 * @param fps 帧率
 */
function frameToTime(frame: number, fps: number): number {
    if (!fps || fps <= 0) fps = 30;
    return frame / fps;
}

/**
 * 将bezier控制点 [x1, y1, x2, y2] 转换为 KeyframeEase 参数
 *
 * bezier [x1, y1, x2, y2] 是CSS cubic-bezier格式的两个控制点
 * 我们将其映射到 AE 的 speed/influence
 *
 * 简化策略：
 *   influence ≈ x2 * 100 （控制点2的x值映射到influence百分比）
 *   speed ≈ (1 - y2) * 100 （控制点2的y值映射到speed）
 */
function bezierToEaseParams(bezier?: [number, number, number, number]): {
    speed: number;
    influence: number;
} {
    if (!bezier || bezier.length !== 4) {
        return { speed: 0, influence: 33 };
    }
    const x2 = bezier[2];
    const y2 = bezier[3];
    return {
        speed: Math.max(0, Math.min(100, (1 - y2) * 100)),
        influence: Math.max(0, Math.min(100, x2 * 100))
    };
}

/**
 * 从参数值范围推断中位值
 */
function pickValueInRange(value: any, range?: [number, number]): any {
    if (value !== undefined && value !== null) return value;
    if (range && range.length === 2) return (range[0] + range[1]) / 2;
    return 0;
}

// ============================================================================
// 主转换函数
// ============================================================================

/**
 * 将决策树解析报告转换为编译器输入
 *
 * @param report 决策树输出的解析报告
 * @param options 转换选项
 * @returns 编译器可接受的 CompilerInput
 */
export function reportToOps(
    report: AnalysisReport,
    options: ReportToOpsOptions = {}
): CompilerInput {
    const opts: Required<ReportToOpsOptions> = {
        compName: options.compName || "Phase3 Output",
        compWidth: options.compWidth || 1920,
        compHeight: options.compHeight || 1080,
        compDuration: options.compDuration || 10,
        compFrameRate: options.compFrameRate || report.metadata?.frame_rate || 30,
        targetLayerRef: options.targetLayerRef || "",
        minConfidence: options.minConfidence ?? 0.5,
        generateSetProperty: options.generateSetProperty ?? true,
        generateSetKeyframe: options.generateSetKeyframe ?? true,
        defaultLayerType: options.defaultLayerType || "solid",
        defaultLayerName: options.defaultLayerName || "Target Layer"
    };

    const operations: CompilerInput["operations"] = [];
    const refCounter = {
        comp: 0,
        layer: 0,
        fx: 0,
        kf: 0,
        prop: 0
    };

    // 用于效果ID→操作引用的映射
    const effectIdToRefMap: Record<string, {
        effectRef: string;
        layerRef: string;
        matchName: string;
        paramMap?: Record<string, string>;
    }> = {};

    // ---------- 1. 创建合成 ----------
    const compRef = "comp_main";
    const createCompOp: CreateCompOp = {
        op: "createComp",
        ref: compRef,
        name: opts.compName,
        width: opts.compWidth,
        height: opts.compHeight,
        pixelAspect: 1,
        duration: opts.compDuration,
        frameRate: opts.compFrameRate,
        bgColor: [0, 0, 0]
    };
    operations.push(createCompOp);
    refCounter.comp++;

    // ---------- 2. 创建目标图层（如果未指定） ----------
    let targetLayerRef = opts.targetLayerRef;
    if (!targetLayerRef) {
        targetLayerRef = `layer_${String(++refCounter.layer).padStart(3, "0")}`;
        const addLayerOp: AddLayerOp = {
            op: "addLayer",
            ref: targetLayerRef,
            compRef: compRef,
            layerType: opts.defaultLayerType as any,
            name: opts.defaultLayerName,
            duration: opts.compDuration
        } as AddLayerOp;

        if (opts.defaultLayerType === "solid") {
            (addLayerOp as any).color = [0.5, 0.5, 0.5];
        } else if (opts.defaultLayerType === "adjustment") {
            (addLayerOp as any).color = [1, 1, 1];
        }
        operations.push(addLayerOp);
    }

    // ---------- 3. 过滤低置信度效果 ----------
    const effects = (report.effects || []).filter(e => {
        const conf = e.confidence ?? 1.0;
        return conf >= opts.minConfidence;
    });

    // ---------- 4. 为每个效果创建 addEffect 操作 ----------
    for (const effect of effects) {
        const mapEntry = findByName(effect.effect_name);
        if (!mapEntry) {
            // 未知效果，跳过并记录
            console.warn(`[Phase3] 未知效果名: ${effect.effect_name} (effect_id: ${effect.effect_id})`);
            continue;
        }

        const effectRef = `fx_${String(++refCounter.fx).padStart(3, "0")}`;
        const addEffectOp: AddEffectOp = {
            op: "addEffect",
            ref: effectRef,
            layerRef: targetLayerRef!,
            compRef: compRef,
            matchName: mapEntry.matchName,
            effectName: mapEntry.displayName
        };
        operations.push(addEffectOp);

        // 记录映射关系
        effectIdToRefMap[effect.effect_id] = {
            effectRef,
            layerRef: targetLayerRef!,
            matchName: mapEntry.matchName,
            paramMap: mapEntry.paramMap
        };
    }

    // ---------- 5. 生成 setProperty 操作 ----------
    if (opts.generateSetProperty) {
        const parameters = (report.parameters || []).filter(p => {
            const effectMap = effectIdToRefMap[p.effect_id];
            if (!effectMap) return false;
            const conf = p.confidence ?? 1.0;
            return conf >= opts.minConfidence;
        });

        for (const param of parameters) {
            const effectMap = effectIdToRefMap[param.effect_id];
            if (!effectMap) continue;

            // 通过 paramMap 转换参数名
            const propName = effectMap.paramMap?.[param.parameter] || param.parameter;
            const value = pickValueInRange(param.value, param.value_range);

            const setPropOp: SetPropertyOp = {
                op: "setProperty",
                ref: `prop_${String(++refCounter.prop).padStart(3, "0")}`,
                layerRef: effectMap.layerRef,
                compRef: compRef,
                propertyPath: `Effects/${effectMap.effectRef}/${propName}`,
                value: value as any
            };
            operations.push(setPropOp);
        }
    }

    // ---------- 6. 生成 setKeyframe 操作 ----------
    if (opts.generateSetKeyframe && report.keyframes) {
        for (const kfEntry of report.keyframes) {
            const effectMap = effectIdToRefMap[kfEntry.effect_id];

            // 支持图层属性关键帧：当 effect_id 是 "ANIM" 或 "LAYER" 时，
            // 关键帧直接设置到图层属性（如 Transform/Scale）而非效果属性
            const isLayerAnim = kfEntry.effect_id === "ANIM" || kfEntry.effect_id === "LAYER";
            if (!effectMap && !isLayerAnim) continue;

            let propertyPath: string;
            let layerRef: string;

            if (effectMap) {
                // 效果属性关键帧
                const propName = effectMap.paramMap?.[kfEntry.parameter] || kfEntry.parameter;
                propertyPath = `Effects/${effectMap.effectRef}/${propName}`;
                layerRef = effectMap.layerRef;
            } else {
                // 图层属性关键帧（动画意图）
                // kfEntry.parameter 可能是 "Scale"/"Opacity"/"Position"/"Rotation"
                // 转换为 AE 标准属性路径 "Transform/<Property>"
                const transformParam = kfEntry.parameter.charAt(0).toUpperCase() + kfEntry.parameter.slice(1);
                propertyPath = `Transform/${transformParam}`;
                layerRef = targetLayerRef!;
            }

            // 转换关键帧
            const keyframes = (kfEntry.keyframes || []).map(kf => {
                const time = frameToTime(kf.frame, opts.compFrameRate);
                const easingType = mapEasingString(kf.easing);
                const easeParams = bezierToEaseParams(kf.bezier);

                return {
                    time,
                    value: kf.value,
                    easing: {
                        type: easingType,
                        inSpeed: easeParams.speed,
                        inInfluence: easeParams.influence,
                        outSpeed: easeParams.speed,
                        outInfluence: easeParams.influence
                    }
                };
            });

            if (keyframes.length === 0) continue;

            const setKfOp: SetKeyframeOp = {
                op: "setKeyframe",
                ref: `kf_${String(++refCounter.kf).padStart(3, "0")}`,
                layerRef,
                compRef: compRef,
                propertyPath,
                keyframes
            };
            operations.push(setKfOp);
        }
    }

    // ---------- 7. 构建 CompilerInput ----------
    const metadata: CompilerMetadata = {
        source: "phase3-tree-to-compiler",
        confidence: report.confidence?.overall ?? 0.8,
        timestamp: new Date().toISOString(),
        description: `Auto-generated from analysis report (video: ${report.metadata?.video_file || "unknown"})`
    };

    return {
        metadata,
        operations
    };
}

// ============================================================================
// 工具函数：从解析报告生成完整的可执行管线
// ============================================================================

/**
 * 完整的端到端管线：解析报告 → 编译器输入 → ExtendScript 代码
 *
 * 用法：
 *   const result = compileReportToScript(report, options, compileFn);
 *   // result.jsx 是可直接通过 execute-atom-script 执行的 ExtendScript 代码
 *
 * 注意：由于 ESM 模块系统下不能使用 require()，调用者必须显式传入 compileFn
 *       （Phase 1 编译器的 compile() 函数）
 *
 * @param report 决策树解析报告
 * @param options 转换选项
 * @param compileFn Phase 1 编译器的 compile 函数（可选，若不传则只返回 compilerInput）
 * @returns { success, jsx?, errors?, input? }
 */
export function compileReportToScript(
    report: AnalysisReport,
    options: ReportToOpsOptions = {},
    compileFn?: (input: CompilerInput) => {
        success: boolean;
        script: string;
        errors: any[];
        warnings: string[];
        stats: { operationCount: number; irNodeCount: number; scriptSize: number; compileTimeMs: number; };
    }
): {
    success: boolean;
    jsx?: string;
    errors?: any[];
    compilerInput?: CompilerInput;
} {
    // 转换为编译器输入
    const compilerInput = reportToOps(report, options);

    // 如果未提供 compileFn，只返回编译器输入
    if (!compileFn || typeof compileFn !== "function") {
        return {
            success: false,
            errors: ["compileFn not provided (ESM-compatible mode requires explicit function injection)"],
            compilerInput
        };
    }

    try {
        const result = compileFn(compilerInput);
        return {
            success: result.success,
            jsx: result.script,  // 字段名映射: script → jsx
            errors: result.errors,
            compilerInput
        };
    } catch (e: any) {
        return {
            success: false,
            errors: [`Compiler error: ${e?.message || String(e)}`],
            compilerInput
        };
    }
}

// ============================================================================
// 统计与诊断函数
// ============================================================================

export interface ReportStats {
    /** 识别到的效果总数 */
    totalEffects: number;
    /** 成功映射到matchName的效果数 */
    mappedEffects: number;
    /** 未识别的效果列表 */
    unknownEffects: string[];
    /** 参数总数 */
    totalParameters: number;
    /** 关键帧总数 */
    totalKeyframes: number;
    /** 平均置信度 */
    avgConfidence: number;
    /** 生成的操作数 */
    generatedOps: number;
    /** 各操作类型计数 */
    opsByType: Record<string, number>;
}

/**
 * 分析解析报告并生成统计信息
 */
export function analyzeReport(report: AnalysisReport): ReportStats {
    const effects = report.effects || [];
    const parameters = report.parameters || [];
    const keyframes = report.keyframes || [];

    let mappedEffects = 0;
    const unknownEffects: string[] = [];

    for (const e of effects) {
        const entry = findByName(e.effect_name);
        if (entry) {
            mappedEffects++;
        } else {
            unknownEffects.push(`${e.effect_id}: ${e.effect_name}`);
        }
    }

    const totalKf = keyframes.reduce((sum, k) => sum + (k.keyframes?.length || 0), 0);

    const confidences = effects.map(e => e.confidence ?? 1.0).filter(c => c > 0);
    const avgConfidence = confidences.length > 0
        ? confidences.reduce((a, b) => a + b, 0) / confidences.length
        : 0;

    return {
        totalEffects: effects.length,
        mappedEffects,
        unknownEffects,
        totalParameters: parameters.length,
        totalKeyframes: totalKf,
        avgConfidence,
        generatedOps: 0, // 由 reportToOps 后填充
        opsByType: {}
    };
}
