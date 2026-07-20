// ============================================================================
// phase4/vocabulary-map.ts
// Phase 4 - 自然语言→解析词汇映射库
//
// 该模块是 L1 NLU 层的"词典"：
//   - 输入：用户输入的自然语言关键词
//   - 输出：解析词汇表中的标准术语引用（VT-XXX）
//
// 数据来源：《解析词汇表与推理决策树》第二章 视觉特征词汇库
// ============================================================================

import { VocabRef, ColorRef, IntensityRef, TemporalRef } from "./types";

/**
 * 词汇映射条目
 */
interface VocabMapEntry {
    /** 词汇 ID（来自解析词汇表） */
    vocabId: string;
    /** 词汇名 */
    vocabName: string;
    /** 推理链中建议的效果 matchName（来自 effect-name-map） */
    suggestedEffect?: string;
    /** 基础置信度 */
    confidence: number;
    /** 同义关键词列表 */
    keywords: string[];
}

// ============================================================================
// 模糊类视觉特征词（VT-001 ~ VT-010）
// ============================================================================
const BLUR_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-001",
        vocabName: "均匀模糊扩散",
        suggestedEffect: "ADBE Gaussian Blur 2",
        confidence: 0.85,
        keywords: ["模糊", "柔化", "虚化", "blur", "gaussian", "高斯模糊", "soffen", "soften", "高斯柔化"],
    },
    {
        vocabId: "VT-002",
        vocabName: "方向性拖尾",
        suggestedEffect: "ADBE Directional Blur",
        confidence: 0.90,
        keywords: ["运动模糊", "方向模糊", "拖尾", "motion blur", "directional", "拉丝", "速度线", "动感模糊"],
    },
    {
        vocabId: "VT-003",
        vocabName: "径向辐射模糊",
        suggestedEffect: "CC Radial Blur",
        confidence: 0.88,
        keywords: ["径向模糊", "放射模糊", "辐射模糊", "radial blur", "zoom blur", "spin", "旋焦", "变焦模糊"],
    },
    {
        vocabId: "VT-004",
        vocabName: "镜头光斑模糊",
        suggestedEffect: "ADBE Camera Lens Blur",
        confidence: 0.82,
        keywords: ["景深", "镜头模糊", "bokeh", "camera blur", "虚化背景", "光斑模糊", "散景", "焦外成像"],
    },
    {
        vocabId: "VT-005",
        vocabName: "方块状模糊",
        suggestedEffect: "ADBE Fast Box Blur",
        confidence: 0.65,
        keywords: ["方块模糊", "box blur", "fast blur", "快速模糊", "盒式模糊"],
    },
    {
        vocabId: "VT-006",
        vocabName: "区域差异模糊",
        suggestedEffect: "ADBE Compound Blur",
        confidence: 0.75,
        keywords: ["复合模糊", "区域模糊", "compound blur", "depth blur", "差异模糊", "深度模糊"],
    },
    {
        vocabId: "VT-007",
        vocabName: "双向模糊",
        suggestedEffect: "ADBE Bilateral Blur",
        confidence: 0.72,
        keywords: ["双边模糊", "bilateral blur", "保边模糊", "表面模糊", "智能模糊"],
    },
    {
        vocabId: "VT-008",
        vocabName: "通道模糊",
        suggestedEffect: "ADBE Channel Blur",
        confidence: 0.68,
        keywords: ["通道模糊", "channel blur", "rgb模糊", "分通道模糊"],
    },
    {
        vocabId: "VT-009",
        vocabName: "径向快速模糊",
        suggestedEffect: "CC Radial Fast Blur",
        confidence: 0.70,
        keywords: ["快速径向模糊", "radial fast blur", "cc径向模糊", "放射状模糊"],
    },
    {
        vocabId: "VT-010",
        vocabName: "矢量运动模糊",
        suggestedEffect: "CC Vector Blur",
        confidence: 0.73,
        keywords: ["矢量模糊", "vector blur", "向量模糊", "方向性柔化"],
    },
];

// ============================================================================
// 发光类视觉特征词（VT-101 ~ VT-106）
// ============================================================================
const GLOW_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-101",
        vocabName: "边缘发光",
        suggestedEffect: "ADBE Glo2",
        confidence: 0.80,
        keywords: ["发光", "辉光", "glow", "边缘光", "rim light", "outline glow", "光晕"],
    },
    {
        vocabId: "VT-102",
        vocabName: "区域发光",
        suggestedEffect: "ADBE Glo2",
        confidence: 0.78,
        keywords: ["区域发光", "bloom", "soft glow", "整体发光", "全屏辉光"],
    },
    {
        vocabId: "VT-103",
        vocabName: "镜头光斑",
        suggestedEffect: "ACP Optical Flares",
        confidence: 0.85,
        keywords: ["镜头光斑", "光晕", "lens flare", "optical flare", "光斑", "flare"],
    },
    {
        vocabId: "VT-104",
        vocabName: "体积光柱",
        suggestedEffect: "CC Light Rays",
        confidence: 0.83,
        keywords: ["体积光", "光柱", "god ray", "light rays", "光线", "光束", "shine"],
    },
    {
        vocabId: "VT-105",
        vocabName: "星芒",
        suggestedEffect: "ADBE Starglow",
        confidence: 0.80,
        keywords: ["星芒", "starglow", "star burst", "十字星", "射线星"],
    },
    {
        vocabId: "VT-106",
        vocabName: "多色光晕",
        suggestedEffect: "ADBE Deep Glow",
        confidence: 0.75,
        keywords: ["多色光晕", "渐变辉光", "deep glow", "彩色光晕"],
    },
];

// ============================================================================
// 扭曲类视觉特征词（VT-201 ~ VT-206）
// ============================================================================
const DISTORT_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-201",
        vocabName: "流体扭曲",
        suggestedEffect: "ADBE Turbulent Displace",
        confidence: 0.85,
        keywords: ["流体扭曲", "湍流", "turbulent", "热浪", "水波", "波动扭曲"],
    },
    {
        vocabId: "VT-202",
        vocabName: "规律波浪",
        suggestedEffect: "ADBE Wave Warp",
        confidence: 0.82,
        keywords: ["波浪", "wave warp", "正弦波", "规律波动"],
    },
    {
        vocabId: "VT-203",
        vocabName: "局部变形",
        suggestedEffect: "ADBE Liquify",
        confidence: 0.70,
        keywords: ["液化", "liquify", "局部变形", "mesh warp", "网格变形"],
    },
    {
        vocabId: "VT-204",
        vocabName: "透视拉伸",
        suggestedEffect: "CC Power Pin",
        confidence: 0.78,
        keywords: ["透视", "四角变形", "power pin", "corner pin", "梯形变形"],
    },
    {
        vocabId: "VT-205",
        vocabName: "液化推拉",
        suggestedEffect: "ADBE Liquify",
        confidence: 0.68,
        keywords: ["液化推拉", "推拉变形", "liquify push", "刷子变形"],
    },
    {
        vocabId: "VT-206",
        vocabName: "镜头畸变",
        suggestedEffect: "ADBE Optics Compensation",
        confidence: 0.72,
        keywords: ["镜头畸变", "optics compensation", "鱼眼", "桶形畸变", "枕形畸变"],
    },
];

// ============================================================================
// 色彩类视觉特征词（VT-301+）
// ============================================================================
const COLOR_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-301",
        vocabName: "暖色调偏移",
        suggestedEffect: "ADBE Color Balance",
        confidence: 0.80,
        keywords: ["暖色", "暖调", "warm", "暖色调", "偏暖"],
    },
    {
        vocabId: "VT-302",
        vocabName: "冷色调偏移",
        suggestedEffect: "ADBE Color Balance",
        confidence: 0.80,
        keywords: ["冷色", "冷调", "cool", "冷色调", "偏冷"],
    },
    {
        vocabId: "VT-303",
        vocabName: "青品对比色调",
        suggestedEffect: "ADBE Curves",
        confidence: 0.78,
        keywords: ["赛博朋克", "cyberpunk", "青品", "霓虹色调"],
    },
    {
        vocabId: "VT-304",
        vocabName: "橙青电影色调",
        suggestedEffect: "ADBE Curves",
        confidence: 0.82,
        keywords: ["电影感", "电影调色", "cinematic", "orange teal", "橙青", "电影色调"],
    },
    {
        vocabId: "VT-305",
        vocabName: "高对比黑白",
        suggestedEffect: "ADBE Black & White",
        confidence: 0.85,
        keywords: ["黑白", "单色", "monochrome", "black white", "grayscale"],
    },
    {
        vocabId: "VT-306",
        vocabName: "复古胶片色调",
        suggestedEffect: "ADBE Colorista",
        confidence: 0.70,
        keywords: ["复古", "vintage", "胶片", "film", "怀旧", "老电影"],
    },
];

// ============================================================================
// 粒子类视觉特征词（VT-401+）
// ============================================================================
const PARTICLE_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-401",
        vocabName: "离散点状元素",
        suggestedEffect: "ACP Particular",
        confidence: 0.88,
        keywords: ["粒子", "particle", "particular", "点状元素", "颗粒"],
    },
    {
        vocabId: "VT-402",
        vocabName: "向上扩散粒子",
        suggestedEffect: "ACP Particular",
        confidence: 0.85,
        keywords: ["飘散", "上升粒子", "飘雪", "飘花", "spray"],
    },
    {
        vocabId: "VT-403",
        vocabName: "高速衰减粒子",
        suggestedEffect: "ACP Particular",
        confidence: 0.82,
        keywords: ["火花", "spark", "爆炸粒子", "emitter"],
    },
    {
        vocabId: "VT-404",
        vocabName: "缓慢上升云状体",
        suggestedEffect: "ACP Form",
        confidence: 0.78,
        keywords: ["烟雾", "smoke", "云雾", "fog", "mist", "form"],
    },
];

// ============================================================================
// 转场类视觉特征词（VT-501+）
// ============================================================================
const TRANSITION_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-501",
        vocabName: "淡入淡出",
        suggestedEffect: "ADBE Opacity",
        confidence: 0.90,
        keywords: ["淡入", "淡出", "fade", "dissolve", "渐隐"],
    },
    {
        vocabId: "VT-502",
        vocabName: "位移转场",
        suggestedEffect: "ADBE Transform",
        confidence: 0.82,
        keywords: ["滑动", "slide", "位移转场", "推拉转场"],
    },
    {
        vocabId: "VT-503",
        vocabName: "缩放转场",
        suggestedEffect: "ADBE Transform",
        confidence: 0.80,
        keywords: ["缩放转场", "zoom transition", "推拉", "scale transition"],
    },
    {
        vocabId: "VT-504",
        vocabName: "旋转转场",
        suggestedEffect: "ADBE Transform",
        confidence: 0.78,
        keywords: ["旋转转场", "spin transition", "rotate transition", "翻转"],
    },
];

// ============================================================================
// 文字类视觉特征词（VT-601+）
// ============================================================================
const TEXT_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-601",
        vocabName: "文字弹入",
        suggestedEffect: "ADBE Text",
        confidence: 0.85,
        keywords: ["弹入", "bounce in", "弹性入场", "弹簧"],
    },
    {
        vocabId: "VT-602",
        vocabName: "文字打字机",
        suggestedEffect: "ADBE Text",
        confidence: 0.88,
        keywords: ["打字机", "typewriter", "逐字显示", "typewriter effect"],
    },
];

// ============================================================================
// 噪波与颗粒类视觉特征词（VT-701+）
// ============================================================================
const NOISE_GRAIN_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-701",
        vocabName: "分形噪波",
        suggestedEffect: "ADBE Fractal Noise",
        confidence: 0.88,
        keywords: ["分形噪波", "fractal noise", "噪波", "noise", "噪声", "分形噪声"],
    },
    {
        vocabId: "VT-702",
        vocabName: "颗粒感",
        suggestedEffect: "ADBE Noise",
        confidence: 0.82,
        keywords: ["颗粒", "grain", "噪点", "颗粒感", "film grain", "胶片颗粒"],
    },
    {
        vocabId: "VT-703",
        vocabName: "中间值平滑",
        suggestedEffect: "ADBE Median",
        confidence: 0.70,
        keywords: ["中间值", "median", "降噪", "平滑", "去噪点"],
    },
    {
        vocabId: "VT-704",
        vocabName: "湍流噪波",
        suggestedEffect: "ADBE Turbulent Noise",
        confidence: 0.75,
        keywords: ["湍流噪波", "turbulent noise", "流动噪波", "动态噪波"],
    },
    {
        vocabId: "VT-705",
        vocabName: "杂色",
        suggestedEffect: "ADBE Noise Alpha",
        confidence: 0.65,
        keywords: ["杂色", "杂点", "alpha噪波", "通道噪波"],
    },
];

// ============================================================================
// 通道与键控类视觉特征词（VT-801+）
// ============================================================================
const KEYING_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-801",
        vocabName: "颜色键控",
        suggestedEffect: "ADBE Color Key",
        confidence: 0.88,
        keywords: ["抠像", "键控", "key", "color key", "抠图", "色键"],
    },
    {
        vocabId: "VT-802",
        vocabName: "亮度键控",
        suggestedEffect: "ADBE Luma Key",
        confidence: 0.80,
        keywords: ["亮度键", "luma key", "亮度抠像", "明度键"],
    },
    {
        vocabId: "VT-803",
        vocabName: "轨道遮罩",
        suggestedEffect: "ADBE Set Matte",
        confidence: 0.75,
        keywords: ["遮罩", "matte", "轨道蒙版", "set matte", "蒙版设置"],
    },
    {
        vocabId: "VT-804",
        vocabName: "边缘收缩",
        suggestedEffect: "ADBE Simple Choker",
        confidence: 0.72,
        keywords: ["收缩", "choker", "边缘收缩", "蒙版收缩", "simple choker"],
    },
    {
        vocabId: "VT-805",
        vocabName: "通道转换",
        suggestedEffect: "ADBE Shift Channels",
        confidence: 0.68,
        keywords: ["通道", "channels", "通道转换", "rgb通道", "shift channels"],
    },
];

// ============================================================================
// 风格化类视觉特征词（VT-901+）
// ============================================================================
const STYLIZE_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-901",
        vocabName: "马赛克",
        suggestedEffect: "ADBE Mosaic",
        confidence: 0.90,
        keywords: ["马赛克", "mosaic", "打码", "像素化", "pixelate"],
    },
    {
        vocabId: "VT-902",
        vocabName: "边缘检测",
        suggestedEffect: "ADBE Find Edges",
        confidence: 0.82,
        keywords: ["描边", "边缘检测", "find edges", "线稿", "轮廓", "勾边"],
    },
    {
        vocabId: "VT-903",
        vocabName: "卡通效果",
        suggestedEffect: "ADBE Cartoon",
        confidence: 0.78,
        keywords: ["卡通", "cartoon", "动画风格", "赛璐璐", "cel-shaded"],
    },
    {
        vocabId: "VT-904",
        vocabName: "暗角晕映",
        suggestedEffect: "CC Vignette",
        confidence: 0.85,
        keywords: ["暗角", "vignette", "晕映", "边角压暗", "暗角效果"],
    },
    {
        vocabId: "VT-905",
        vocabName: "浮雕效果",
        suggestedEffect: "ADBE Emboss",
        confidence: 0.70,
        keywords: ["浮雕", "emboss", "凹凸效果", "立体浮雕"],
    },
    {
        vocabId: "VT-906",
        vocabName: "粗糙边缘",
        suggestedEffect: "ADBE Roughen Edges",
        confidence: 0.75,
        keywords: ["粗糙边缘", "roughen edges", "边缘粗糙", "风化效果", "破损边缘"],
    },
];

// ============================================================================
// 透视与3D类视觉特征词（VT-1001+）
// ============================================================================
const PERSPECTIVE_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-1001",
        vocabName: "投影效果",
        suggestedEffect: "ADBE Drop Shadow",
        confidence: 0.88,
        keywords: ["投影", "阴影", "drop shadow", "影子", "阴影效果"],
    },
    {
        vocabId: "VT-1002",
        vocabName: "倒角斜面",
        suggestedEffect: "ADBE Bevel Alpha",
        confidence: 0.75,
        keywords: ["倒角", "bevel", "斜面", "bevel alpha", "立体边缘"],
    },
    {
        vocabId: "VT-1003",
        vocabName: "基础3D",
        suggestedEffect: "ADBE Basic 3D",
        confidence: 0.78,
        keywords: ["3d旋转", "basic 3d", "基础3d", "三维旋转", "空间翻转"],
    },
    {
        vocabId: "VT-1004",
        vocabName: "球体效果",
        suggestedEffect: "CC Sphere",
        confidence: 0.72,
        keywords: ["球面", "sphere", "球体", "cc sphere", "球形化"],
    },
    {
        vocabId: "VT-1005",
        vocabName: "圆柱效果",
        suggestedEffect: "CC Cylinder",
        confidence: 0.68,
        keywords: ["圆柱", "cylinder", "cc cylinder", "柱面化"],
    },
    {
        vocabId: "VT-1006",
        vocabName: "镜头畸变",
        suggestedEffect: "ADBE Optics Compensation",
        confidence: 0.72,
        keywords: ["镜头畸变", "鱼眼", "optics compensation", "桶形畸变", "枕形畸变"],
    },
];

// ============================================================================
// 生成与绘制类视觉特征词（VT-1101+）
// ============================================================================
const GENERATE_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "VT-1101",
        vocabName: "颜色填充",
        suggestedEffect: "ADBE Fill",
        confidence: 0.85,
        keywords: ["填充", "fill", "纯色填充", "颜色填充"],
    },
    {
        vocabId: "VT-1102",
        vocabName: "渐变过渡",
        suggestedEffect: "ADBE Ramp",
        confidence: 0.82,
        keywords: ["渐变", "ramp", "渐变色", "渐变填充", "过渡色"],
    },
    {
        vocabId: "VT-1103",
        vocabName: "描边路径",
        suggestedEffect: "ADBE Stroke",
        confidence: 0.80,
        keywords: ["描边", "stroke", "画线", "路径描边"],
    },
    {
        vocabId: "VT-1104",
        vocabName: "四色渐变",
        suggestedEffect: "ADBE 4-Color Gradient",
        confidence: 0.72,
        keywords: ["四色渐变", "4-color gradient", "四角渐变", "多色渐变"],
    },
    {
        vocabId: "VT-1105",
        vocabName: "圆形生成",
        suggestedEffect: "ADBE Circle",
        confidence: 0.70,
        keywords: ["圆形", "circle", "圆环", "生成圆形"],
    },
    {
        vocabId: "VT-1106",
        vocabName: "棋盘格",
        suggestedEffect: "ADBE Checkerboard",
        confidence: 0.68,
        keywords: ["棋盘格", "checkerboard", "格子", "格纹"],
    },
    {
        vocabId: "VT-1107",
        vocabName: "粒子系统",
        suggestedEffect: "CC Particle World",
        confidence: 0.82,
        keywords: ["粒子", "particle", "粒子世界", "粒子特效", "粒子系统"],
    },
];

// ============================================================================
// 关键帧动画类词汇（KF-010+）
// ============================================================================
const KEYFRAME_VOCAB: VocabMapEntry[] = [
    {
        vocabId: "KF-010",
        vocabName: "弹性缓入",
        suggestedEffect: "ADBE Glo2",
        confidence: 0.80,
        keywords: ["弹入", "弹性", "bounce", "spring", "回弹"],
    },
    {
        vocabId: "KF-011",
        vocabName: "线性渐入",
        suggestedEffect: "ADBE Opacity",
        confidence: 0.85,
        keywords: ["淡入", "fade in", "渐入", "线性渐入"],
    },
    {
        vocabId: "KF-012",
        vocabName: "位移渐入",
        suggestedEffect: "ADBE Transform",
        confidence: 0.82,
        keywords: ["滑入", "slide in", "位移入场", "从左侧滑入"],
    },
    {
        vocabId: "KF-013",
        vocabName: "缩放渐变",
        suggestedEffect: "ADBE Transform",
        confidence: 0.80,
        keywords: ["缩放", "scale", "从小到大", "放大入场"],
    },
    {
        vocabId: "KF-014",
        vocabName: "旋转变换",
        suggestedEffect: "ADBE Transform",
        confidence: 0.78,
        keywords: ["旋转", "rotate", "旋转入场", "翻转入场"],
    },
];

// ============================================================================
// 全部词汇表（合并）
// ============================================================================
const ALL_VOCAB: VocabMapEntry[] = [
    ...BLUR_VOCAB,
    ...GLOW_VOCAB,
    ...DISTORT_VOCAB,
    ...COLOR_VOCAB,
    ...PARTICLE_VOCAB,
    ...TRANSITION_VOCAB,
    ...TEXT_VOCAB,
    ...NOISE_GRAIN_VOCAB,
    ...KEYING_VOCAB,
    ...STYLIZE_VOCAB,
    ...PERSPECTIVE_VOCAB,
    ...GENERATE_VOCAB,
    ...KEYFRAME_VOCAB,
];

// ============================================================================
// 颜色映射表
// ============================================================================
const COLOR_MAP: Array<{ keyword: string; rgb: [number, number, number]; temperature: "warm" | "cool" | "neutral" }> = [
    { keyword: "暖色", rgb: [1, 0.7, 0.3], temperature: "warm" },
    { keyword: "暖金", rgb: [1, 0.8, 0.4], temperature: "warm" },
    { keyword: "橙", rgb: [1, 0.5, 0], temperature: "warm" },
    { keyword: "红", rgb: [1, 0, 0], temperature: "warm" },
    { keyword: "黄", rgb: [1, 1, 0], temperature: "warm" },
    { keyword: "冷色", rgb: [0.3, 0.6, 1], temperature: "cool" },
    { keyword: "青", rgb: [0, 1, 1], temperature: "cool" },
    { keyword: "蓝", rgb: [0, 0.4, 1], temperature: "cool" },
    { keyword: "紫", rgb: [0.6, 0, 1], temperature: "cool" },
    { keyword: "品红", rgb: [1, 0, 1], temperature: "cool" },
    { keyword: "绿", rgb: [0, 1, 0], temperature: "neutral" },
    { keyword: "白", rgb: [1, 1, 1], temperature: "neutral" },
    { keyword: "黑", rgb: [0, 0, 0], temperature: "neutral" },
];

// ============================================================================
// 强度映射表
// ============================================================================
const INTENSITY_MAP: Array<{ keyword: string; level: IntensityRef["level"]; scale: number }> = [
    { keyword: "轻微", level: "subtle", scale: 0.4 },
    { keyword: "微微", level: "subtle", scale: 0.3 },
    { keyword: "稍", level: "subtle", scale: 0.5 },
    { keyword: "一点", level: "subtle", scale: 0.5 },
    { keyword: "稍微", level: "subtle", scale: 0.5 },
    { keyword: "subtle", level: "subtle", scale: 0.4 },
    { keyword: "适中", level: "moderate", scale: 1.0 },
    { keyword: "中等", level: "moderate", scale: 1.0 },
    { keyword: "正常", level: "moderate", scale: 1.0 },
    { keyword: "moderate", level: "moderate", scale: 1.0 },
    { keyword: "强烈", level: "strong", scale: 1.5 },
    { keyword: "强", level: "strong", scale: 1.5 },
    { keyword: "明显", level: "strong", scale: 1.3 },
    { keyword: "strong", level: "strong", scale: 1.5 },
    { keyword: "夸张", level: "extreme", scale: 2.0 },
    { keyword: "极致", level: "extreme", scale: 2.0 },
    { keyword: "非常强", level: "extreme", scale: 2.0 },
    { keyword: "extreme", level: "extreme", scale: 2.0 },
];

// ============================================================================
// 时间映射表
// ============================================================================
const TEMPORAL_MAP: Array<{ keyword: string; atTime?: number; duration?: number }> = [
    { keyword: "开头", atTime: 0 },
    { keyword: "start", atTime: 0 },
    { keyword: "结尾", atTime: -1 }, // -1 表示"末尾"，由调用方换算
    { keyword: "end", atTime: -1 },
    { keyword: "中间", atTime: -0.5 }, // -0.5 表示"中点"
    { keyword: "middle", atTime: -0.5 },
    { keyword: "持续2秒", duration: 2 },
    { keyword: "持续3秒", duration: 3 },
    { keyword: "持续5秒", duration: 5 },
];

// ============================================================================
// 公共 API
// ============================================================================

/**
 * 查找词汇映射
 * @param keyword 用户输入的关键词
 * @returns 匹配到的词汇引用（可能有多个）
 */
export function findVocab(keyword: string): VocabRef[] {
    const refs: VocabRef[] = [];
    const lower = keyword.toLowerCase();

    for (const entry of ALL_VOCAB) {
        for (const kw of entry.keywords) {
            if (kw.toLowerCase() === lower) {
                refs.push({
                    id: entry.vocabId,
                    name: entry.vocabName,
                    matchedKeyword: keyword,
                    suggestedEffect: entry.suggestedEffect,
                    confidence: entry.confidence,
                });
                break;
            }
        }
    }

    return refs;
}

/**
 * 在文本中扫描所有词汇
 * @param text 用户输入文本
 * @returns 匹配到的所有词汇引用
 */
export function scanVocab(text: string): VocabRef[] {
    const refs: VocabRef[] = [];
    const seen = new Set<string>();
    const lower = text.toLowerCase();

    for (const entry of ALL_VOCAB) {
        for (const kw of entry.keywords) {
            if (lower.includes(kw.toLowerCase())) {
                if (seen.has(entry.vocabId)) break;
                seen.add(entry.vocabId);
                refs.push({
                    id: entry.vocabId,
                    name: entry.vocabName,
                    matchedKeyword: kw,
                    suggestedEffect: entry.suggestedEffect,
                    confidence: entry.confidence,
                });
                break;
            }
        }
    }

    return refs;
}

/**
 * 在文本中扫描颜色
 */
export function scanColors(text: string): ColorRef[] {
    const refs: ColorRef[] = [];
    for (const entry of COLOR_MAP) {
        if (text.includes(entry.keyword)) {
            refs.push({
                keyword: entry.keyword,
                rgb: entry.rgb,
                temperature: entry.temperature,
            });
        }
    }
    return refs;
}

/**
 * 在文本中扫描强度
 */
export function scanIntensity(text: string): IntensityRef[] {
    const refs: IntensityRef[] = [];
    for (const entry of INTENSITY_MAP) {
        if (text.includes(entry.keyword)) {
            refs.push({
                keyword: entry.keyword,
                level: entry.level,
                scale: entry.scale,
            });
        }
    }
    return refs;
}

/**
 * 在文本中扫描时间
 */
export function scanTemporal(text: string): TemporalRef[] {
    const refs: TemporalRef[] = [];
    for (const entry of TEMPORAL_MAP) {
        if (text.includes(entry.keyword)) {
            refs.push({
                keyword: entry.keyword,
                atTime: entry.atTime,
                duration: entry.duration,
            });
        }
    }
    return refs;
}

/**
 * 获取词汇统计
 */
export function getVocabStats(): {
    total: number;
    byCategory: Record<string, number>;
} {
    const byCategory: Record<string, number> = {
        blur: BLUR_VOCAB.length,
        glow: GLOW_VOCAB.length,
        distort: DISTORT_VOCAB.length,
        color: COLOR_VOCAB.length,
        particle: PARTICLE_VOCAB.length,
        transition: TRANSITION_VOCAB.length,
        text: TEXT_VOCAB.length,
        noise_grain: NOISE_GRAIN_VOCAB.length,
        keying: KEYING_VOCAB.length,
        stylize: STYLIZE_VOCAB.length,
        perspective: PERSPECTIVE_VOCAB.length,
        generate: GENERATE_VOCAB.length,
        keyframe: KEYFRAME_VOCAB.length,
    };
    return { total: ALL_VOCAB.length, byCategory };
}
