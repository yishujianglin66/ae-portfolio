// ============================================================================
// phase4/types.ts
// Phase 4 - 自然语言理解层（NLU）类型定义
//
// 类型层级：
//   Intent（意图） → EffectDescription（效果描述） → AnalysisReport（Phase 3 输入）
//
// 与 Phase 3 的衔接：NLUParser 输出的 Intent + EffectDescription
// 通过 IntentBuilder 合成 AnalysisReport，直接喂给 Phase 3 的 reportToOps()
// ============================================================================

/**
 * 操作意图类型枚举
 *
 * 对应架构设计文档 2.1.1 节的 6 种操作意图类别
 */
export enum IntentType {
    /** 添加效果（"加个模糊"、"添加发光"、"来个粒子"） */
    ADD_EFFECT = "INTENT_ADD_EFFECT",
    /** 创建动画（"做弹入动画"、"加个缩放动画"、"文字入场"） */
    CREATE_ANIM = "INTENT_CREATE_ANIM",
    /** 调整参数（"模糊调大一点"、"发光再强些"、"颜色偏暖"） */
    ADJUST_PARAM = "INTENT_ADJUST_PARAM",
    /** 创建图层（"建个合成"、"加个调整层"、"创建空对象"） */
    CREATE_LAYER = "INTENT_CREATE_LAYER",
    /** 风格化组合（"赛博朋克风格"、"电影级调色"、"梦幻柔焦"） */
    STYLE_COMBO = "INTENT_STYLE_COMBO",
    /** 逆向分析（"这个效果怎么做的"、"分析一下这个视频"） */
    REVERSE_ANALYZE = "INTENT_REVERSE_ANALYZE",
    /** Silhouette 遮罩/跟踪任务（"扣个人像"、"跟踪这个物体"、"做个遮罩"） */
    SILHOUETTE_TASK = "INTENT_SILHOUETTE_TASK",
    /** 未知意图（无法识别，回退到手动模式） */
    UNKNOWN = "INTENT_UNKNOWN",
}

/**
 * 意图识别结果
 */
export interface Intent {
    /** 意图类型 */
    type: IntentType;
    /** 识别置信度 0-1 */
    confidence: number;
    /** 提取的槽位（如效果名、参数名、目标图层等） */
    slots: IntentSlots;
    /** 原始用户输入 */
    rawInput: string;
    /** 命中的模式（用于调试/反馈） */
    matchedPattern?: string;
}

/**
 * 意图槽位
 */
export interface IntentSlots {
    /** 用户提到的效果名（中英文均可，如"模糊"、"glow"） */
    effectName?: string;
    /** 风格名（如"赛博朋克"、"电影感"） */
    styleName?: string;
    /** 目标图层名或索引（如"文字"、"图层1"、"选中"） */
    targetLayer?: string;
    /** 参数名（如"模糊度"、"强度"） */
    paramName?: string;
    /** 调整方向（"增大"/"减小"/"设置为"） */
    adjustDirection?: "increase" | "decrease" | "set";
    /** 调整幅度（数值或描述，如"一点"、"50%"） */
    adjustAmount?: string | number;
    /** 颜色描述（如"暖色"、"青色"、"红色"） */
    color?: string;
    /** 时间描述（如"开头"、"3秒处"、"持续2秒"） */
    temporal?: string;
    /** 动画类型（如"弹入"、"淡出"、"旋转入场"） */
    animType?: string;
    /** Silhouette 任务类型（"roto" | "track" | "paint" | "export"） */
    silhouetteTask?: string;
    /** 遮罩目标（如"人物"、"汽车"、"背景"） */
    rotoTarget?: string;
    /** 跟踪类型（"planar" | "point" | "paint"） */
    trackType?: string;
    /** 输出格式（"png" | "tiff" | "exr" | "json"） */
    outputFormat?: string;
}

/**
 * 效果描述（从自然语言映射到解析词汇表的标准术语）
 *
 * 对应架构设计文档 2.2 节 EffectDescription
 */
export interface EffectDescription {
    /** 效果关键词（映射到 VT-001 等词汇 ID） */
    effectKeywords: VocabRef[];
    /** 风格关键词（赛博朋克、电影感等） */
    styleKeywords: VocabRef[];
    /** 方向关键词（向左、向上、向外辐射等） */
    directionKeywords: string[];
    /** 强度关键词（柔和、强烈、夸张等） */
    intensityKeywords: IntensityRef[];
    /** 颜色关键词 */
    colorKeywords: ColorRef[];
    /** 时间关键词 */
    temporalKeywords: TemporalRef[];
}

/**
 * 解析词汇引用
 */
export interface VocabRef {
    /** 词汇 ID（VT-001/KF-010 等） */
    id: string;
    /** 词汇名（中文） */
    name: string;
    /** 命中的原始关键词 */
    matchedKeyword: string;
    /** 推理链中建议的效果 matchName */
    suggestedEffect?: string;
    /** 推理链中的置信度 */
    confidence: number;
}

/**
 * 强度引用
 */
export interface IntensityRef {
    keyword: string;
    level: "subtle" | "moderate" | "strong" | "extreme";
    /** 数值缩放因子 0-2 */
    scale: number;
}

/**
 * 颜色引用
 */
export interface ColorRef {
    keyword: string;
    /** RGB 0-1 */
    rgb: [number, number, number];
    /** 颜色温度描述 */
    temperature?: "warm" | "cool" | "neutral";
}

/**
 * 时间引用
 */
export interface TemporalRef {
    keyword: string;
    /** 时间点（秒） */
    atTime?: number;
    /** 持续时间（秒） */
    duration?: number;
}

/**
 * 项目上下文
 */
export interface ProjectContext {
    /** 当前激活合成名 */
    activeCompName?: string;
    /** 选中图层列表 */
    selectedLayers?: Array<{
        name: string;
        index: number;
        type: string;
    }>;
    /** 当前合成的分辨率 */
    compResolution?: [number, number];
    /** 合成帧率 */
    compFrameRate?: number;
    /** 合成时长（秒） */
    compDuration?: number;
}

/**
 * 引擎响应
 */
export interface EngineResponse {
    /** 是否理解用户意图 */
    understood: boolean;
    /** 解析出的意图 */
    intent: Intent;
    /** 解析出的效果描述 */
    effectDescription: EffectDescription;
    /** 是否需要追问 */
    needsClarification: boolean;
    /** 追问问题 */
    clarificationQuestion?: string;
    /** 追问选项 */
    clarificationOptions?: string[];
    /** 错误信息（理解失败时） */
    error?: string;
}

/**
 * 追问请求
 */
export interface ClarificationRequest {
    /** 问题文本 */
    question: string;
    /** 选项列表 */
    options: ClarificationOption[];
    /** 关联的槽位名（追问回答将填入该槽位） */
    slotName: keyof IntentSlots;
}

/**
 * 追问选项
 */
export interface ClarificationOption {
    /** 选项显示文本 */
    label: string;
    /** 选择该选项时填入槽位的值 */
    value: string;
    /** 选项描述（可选） */
    description?: string;
}

/**
 * 置信度阈值
 */
export const CONFIDENCE_THRESHOLDS = {
    /** 高于该值直接执行 */
    AUTO_EXECUTE: 0.7,
    /** 高于该值不需要追问 */
    NO_CLARIFICATION: 0.6,
    /** 低于该值视为未识别 */
    MIN_RECOGNITION: 0.3,
} as const;

/**
 * Silhouette 操作类型
 */
export type SilhouetteTaskType = "roto" | "track" | "paint" | "export";

/**
 * Silhouette 操作参数
 */
export interface SilhouetteOperation {
    /** 任务类型 */
    taskType: SilhouetteTaskType;
    /** 输入素材路径 */
    sourcePath?: string;
    /** 输出路径 */
    outputPath?: string;
    /** 形状类型（roto 用） */
    shapeType?: "x-spline" | "bezier";
    /** 边缘容差 */
    tolerance?: number;
    /** 关键帧间隔（帧） */
    keyframes?: number;
    /** 跟踪类型（track 用） */
    trackType?: "planar" | "point" | "paint";
    /** 搜索区域大小 */
    searchArea?: number;
    /** 跟踪精度 */
    accuracy?: "low" | "medium" | "high";
    /** 笔刷大小（paint 用） */
    brushSize?: number;
    /** 笔刷硬度 */
    brushHardness?: number;
    /** 绘制模式 */
    paintMode?: "clone" | "repair" | "erase";
    /** 输出格式 */
    outputFormat?: "png" | "tiff" | "exr" | "json" | "ae";
    /** 是否启用跟踪 */
    tracking?: "planar" | "point" | "paint-track";
    /** 遮罩目标描述 */
    target?: string;
}
