// ============================================================================
// phase4/effect-knowledge-graph.ts
// Phase 4 - 效果知识图谱
//
// 基于知识图谱的效果组合推理引擎核心数据
// 包含 9 大类 63 个 AE 内置效果的完整元数据
//
// 知识图谱结构：
//   - 效果节点：matchName、displayName、category、tags、parameters
//   - 关系边：协同效果、互斥效果、前置效果、后置效果
//   - 风格配方：预设的效果组合（如赛博朋克、电影感）
// ============================================================================

export interface EffectParameter {
    name: string;
    type: "number" | "color" | "enum" | "boolean" | "point";
    min?: number;
    max?: number;
    default?: number | string | number[] | boolean;
    enumValues?: string[];
    intensityScale?: number;
    description?: string;
}

export interface EffectNode {
    matchName: string;
    displayName: string;
    category: EffectCategory;
    subCategory?: string;
    tags: string[];
    parameters: EffectParameter[];
    confidence: number;
    description: string;
}

export type EffectCategory =
    | "blur_sharpen"
    | "color_correction"
    | "glow_light"
    | "distort"
    | "noise_grain"
    | "channel_keying"
    | "stylize"
    | "perspective_3d"
    | "generate_draw";

export interface StyleRecipe {
    name: string;
    displayName: string;
    category: string;
    description: string;
    keywords: string[];
    intensityRange: [number, number];
    effects: Array<{
        matchName: string;
        settings: Record<string, number | string | number[]>;
        intensityParam?: string;
        intensityFactor?: number;
    }>;
}

export interface EffectRelation {
    effect: string;
    type: "synergy" | "mutex" | "prerequisite" | "post";
    weight: number;
    reason?: string;
}

// ============================================================================
// 效果知识图谱 - 9大类 63个效果
// ============================================================================

export const EFFECT_KNOWLEDGE_GRAPH: Record<string, EffectNode> = {
    // ==================== 1. 模糊与锐化类 (8个) ====================
    "ADBE Gaussian Blur 2": {
        matchName: "ADBE Gaussian Blur 2",
        displayName: "Gaussian Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["模糊", "柔化", "虚化", "gaussian", "blur"],
        parameters: [
            { name: "Blurriness", type: "number", min: 0, max: 1000, default: 10, intensityScale: 1.0 },
            { name: "Blur Dimensions", type: "enum", enumValues: ["Horizontal and Vertical", "Horizontal", "Vertical"], default: "Horizontal and Vertical" },
        ],
        confidence: 0.88,
        description: "高斯模糊，最常用的柔化效果",
    },
    "ADBE Directional Blur": {
        matchName: "ADBE Directional Blur",
        displayName: "Directional Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["方向模糊", "运动模糊", "拖尾", "motion blur"],
        parameters: [
            { name: "Blur Length", type: "number", min: 0, max: 500, default: 15, intensityScale: 1.0 },
            { name: "Direction", type: "number", min: 0, max: 360, default: 90 },
        ],
        confidence: 0.86,
        description: "方向性模糊，模拟运动拖尾效果",
    },
    "ADBE Fast Box Blur": {
        matchName: "ADBE Fast Box Blur",
        displayName: "Fast Box Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["快速模糊", "方块模糊", "box blur", "fast blur"],
        parameters: [
            { name: "Blurriness", type: "number", min: 0, max: 1000, default: 12, intensityScale: 1.0 },
            { name: "Blur Dimensions", type: "enum", enumValues: ["Horizontal and Vertical", "Horizontal", "Vertical"], default: "Horizontal and Vertical" },
            { name: "Repeat Edge Pixels", type: "boolean", default: true },
        ],
        confidence: 0.82,
        description: "快速方块模糊，渲染速度快",
    },
    "CC Radial Blur": {
        matchName: "CC Radial Blur",
        displayName: "CC Radial Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["径向模糊", "放射模糊", "radial blur", "zoom blur", "spin"],
        parameters: [
            { name: "Amount", type: "number", min: 0, max: 200, default: 20, intensityScale: 1.0 },
            { name: "Type", type: "enum", enumValues: ["Zoom", "Rotate"], default: "Zoom" },
            { name: "Quality", type: "number", min: 1, max: 100, default: 10 },
            { name: "Center", type: "point", default: [0.5, 0.5] },
        ],
        confidence: 0.85,
        description: "径向模糊，缩放或旋转型辐射模糊",
    },
    "ADBE Camera Lens Blur": {
        matchName: "ADBE Camera Lens Blur",
        displayName: "Camera Lens Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["镜头模糊", "景深", "bokeh", "camera blur", "光斑模糊"],
        parameters: [
            { name: "Blur Amount", type: "number", min: 0, max: 100, default: 15, intensityScale: 1.0 },
            { name: "Iris Shape", type: "enum", enumValues: ["Hexagon", "Pentagon", "Square", "Circle"], default: "Hexagon" },
            { name: "Iris Rotation", type: "number", min: 0, max: 360, default: 0 },
            { name: "Highlight Gain", type: "number", min: 0, max: 100, default: 20 },
            { name: "Highlight Threshold", type: "number", min: 0, max: 255, default: 200 },
        ],
        confidence: 0.80,
        description: "镜头模糊，模拟真实相机景深和散景效果",
    },
    "ADBE Compound Blur": {
        matchName: "ADBE Compound Blur",
        displayName: "Compound Blur",
        category: "blur_sharpen",
        subCategory: "blur",
        tags: ["复合模糊", "区域模糊", "compound blur", "差异模糊"],
        parameters: [
            { name: "Maximum Blur", type: "number", min: 0, max: 100, default: 20, intensityScale: 1.0 },
            { name: "Blur Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Stretch Map to Fit", type: "boolean", default: true },
            { name: "Invert Blur", type: "boolean", default: false },
        ],
        confidence: 0.75,
        description: "复合模糊，基于另一图层的亮度控制模糊程度",
    },
    "ADBE Unsharp Mask": {
        matchName: "ADBE Unsharp Mask",
        displayName: "Unsharp Mask",
        category: "blur_sharpen",
        subCategory: "sharpen",
        tags: ["锐化", "unsharp", "sharpen", "清晰度"],
        parameters: [
            { name: "Amount", type: "number", min: 0, max: 500, default: 50, intensityScale: 1.0 },
            { name: "Radius", type: "number", min: 0, max: 127, default: 2 },
            { name: "Threshold", type: "number", min: 0, max: 255, default: 5 },
        ],
        confidence: 0.85,
        description: "非锐化蒙版，增强边缘对比度实现锐化",
    },
    "ADBE Sharpen": {
        matchName: "ADBE Sharpen",
        displayName: "Sharpen",
        category: "blur_sharpen",
        subCategory: "sharpen",
        tags: ["锐化", "sharpen", "增强清晰度"],
        parameters: [
            { name: "Sharpen Amount", type: "number", min: 0, max: 100, default: 20, intensityScale: 1.0 },
        ],
        confidence: 0.80,
        description: "简单锐化效果",
    },

    // ==================== 2. 颜色校正类 (10个) ====================
    "ADBE HUE SATURATION": {
        matchName: "ADBE HUE SATURATION",
        displayName: "Hue/Saturation",
        category: "color_correction",
        subCategory: "hsl",
        tags: ["色相", "饱和度", "hue", "saturation", "调色"],
        parameters: [
            { name: "Channel Control", type: "enum", enumValues: ["Master", "Reds", "Yellows", "Greens", "Cyans", "Blues", "Magentas"], default: "Master" },
            { name: "Master Hue", type: "number", min: 0, max: 360, default: 0, intensityScale: 0.5 },
            { name: "Master Saturation", type: "number", min: -100, max: 100, default: 10, intensityScale: 1.0 },
            { name: "Master Lightness", type: "number", min: -100, max: 100, default: 0, intensityScale: 0.5 },
        ],
        confidence: 0.87,
        description: "色相/饱和度调整，最常用的调色工具",
    },
    "ADBE Color Balance": {
        matchName: "ADBE Color Balance",
        displayName: "Color Balance",
        category: "color_correction",
        subCategory: "color_balance",
        tags: ["色彩平衡", "调色", "warm", "cool", "色温"],
        parameters: [
            { name: "Shadow Red Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Shadow Green Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Shadow Blue Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Midtone Red Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Midtone Green Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Midtone Blue Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Hilight Red Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Hilight Green Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Hilight Blue Balance", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
        ],
        confidence: 0.86,
        description: "色彩平衡，分阴影/中间调/高光调整色偏",
    },
    "ADBE Protractor2": {
        matchName: "ADBE Protractor2",
        displayName: "Levels",
        category: "color_correction",
        subCategory: "levels",
        tags: ["色阶", "levels", "对比度", "亮度", "调色"],
        parameters: [
            { name: "Input Black", type: "number", min: 0, max: 255, default: 0 },
            { name: "Input White", type: "number", min: 0, max: 255, default: 255 },
            { name: "Gamma", type: "number", min: 0.1, max: 10, default: 1.0, intensityScale: 0.2 },
            { name: "Output Black", type: "number", min: 0, max: 255, default: 0 },
            { name: "Output White", type: "number", min: 0, max: 255, default: 255 },
        ],
        confidence: 0.84,
        description: "色阶调整，控制亮度对比度和伽马值",
    },
    "ADBE Brightness & Contrast 2": {
        matchName: "ADBE Brightness & Contrast 2",
        displayName: "Brightness & Contrast",
        category: "color_correction",
        subCategory: "basic",
        tags: ["亮度", "对比度", "brightness", "contrast", "基础调色"],
        parameters: [
            { name: "Brightness", type: "number", min: -100, max: 100, default: 0, intensityScale: 0.8 },
            { name: "Contrast", type: "number", min: -100, max: 100, default: 0, intensityScale: 1.0 },
            { name: "Use Legacy", type: "boolean", default: false },
        ],
        confidence: 0.90,
        description: "亮度对比度，最基础的调色工具",
    },
    "ADBE Photo Filter": {
        matchName: "ADBE Photo Filter",
        displayName: "Photo Filter",
        category: "color_correction",
        subCategory: "filter",
        tags: ["照片滤镜", "photo filter", "色温", "暖调", "冷调"],
        parameters: [
            { name: "Filter", type: "enum", enumValues: ["Warming Filter (85)", "Cooling Filter (80)", "Warming Filter (81)", "Cooling Filter (82)", "Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Violet", "Magenta", "Sepia", "Deep Red", "Deep Blue", "Deep Emerald", "Deep Yellow", "Underwater"], default: "Warming Filter (85)" },
            { name: "Density", type: "number", min: 0, max: 100, default: 25, intensityScale: 1.0 },
            { name: "Preserve Luminosity", type: "boolean", default: true },
        ],
        confidence: 0.82,
        description: "照片滤镜，模拟相机滤镜的色温调整",
    },
    "ADBE Tritone": {
        matchName: "ADBE Tritone",
        displayName: "Tritone",
        category: "color_correction",
        subCategory: "toning",
        tags: ["三色渐变", "tritone", "双色调", "复古", "调色"],
        parameters: [
            { name: "Highlights", type: "color", default: [1, 1, 1] },
            { name: "Midtones", type: "color", default: [0.5, 0.5, 0.5] },
            { name: "Shadows", type: "color", default: [0, 0, 0] },
        ],
        confidence: 0.80,
        description: "三色渐变色调，将图像映射为三种颜色",
    },
    "ADBE Leave Color": {
        matchName: "ADBE Leave Color",
        displayName: "Leave Color",
        category: "color_correction",
        subCategory: "selective",
        tags: ["留色", "leave color", "去色保留", "选择性颜色"],
        parameters: [
            { name: "Color To Leave", type: "color", default: [1, 0, 0] },
            { name: "Amount To Decolor", type: "number", min: 0, max: 100, default: 100, intensityScale: 1.0 },
            { name: "Tolerance", type: "number", min: 0, max: 100, default: 20 },
            { name: "Edge Softness", type: "number", min: 0, max: 10, default: 1 },
            { name: "Match colors", type: "enum", enumValues: ["Using RGB", "Using Hue"], default: "Using RGB" },
        ],
        confidence: 0.78,
        description: "留色效果，保留指定颜色其余去色",
    },
    "ADBE Equalize": {
        matchName: "ADBE Equalize",
        displayName: "Equalize",
        category: "color_correction",
        subCategory: "tonal",
        tags: ["均衡", "equalize", "色调均化", "对比度增强"],
        parameters: [
            { name: "Equalize", type: "enum", enumValues: ["RGB", "Brightness", "Photoshop Style"], default: "RGB" },
            { name: "Amount To Equalize", type: "number", min: 0, max: 100, default: 100, intensityScale: 1.0 },
        ],
        confidence: 0.75,
        description: "色调均化，重新分布像素亮度值",
    },
    "ADBE Colorama": {
        matchName: "ADBE Colorama",
        displayName: "Colorama",
        category: "color_correction",
        subCategory: "creative",
        tags: ["色彩映射", "colorama", "渐变映射", "创意调色"],
        parameters: [
            { name: "Get Phase From", type: "enum", enumValues: ["Luminance", "Hue", "Saturation", "Lightness", "Red", "Green", "Blue", "Alpha"], default: "Luminance" },
            { name: "Add Phase", type: "number", min: 0, max: 360, default: 0 },
            { name: "Output Cycle", type: "number", min: 1, max: 5, default: 1 },
        ],
        confidence: 0.72,
        description: "Colorama色彩映射，创意调色效果",
    },
    "ADBE Color Link": {
        matchName: "ADBE Color Link",
        displayName: "Color Link",
        category: "color_correction",
        subCategory: "match",
        tags: ["颜色链接", "color link", "色彩匹配", "统一色调"],
        parameters: [
            { name: "Source Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Sample", type: "enum", enumValues: ["Average", "Median", "Brightest", "Darkest"], default: "Average" },
            { name: "Opacity", type: "number", min: 0, max: 100, default: 100, intensityScale: 0.5 },
            { name: "Blending Mode", type: "enum", enumValues: ["Color", "Tint", "Darker Color", "Lighter Color", "Hue", "Saturation", "Luminosity"], default: "Color" },
        ],
        confidence: 0.70,
        description: "颜色链接，从另一图层取样颜色进行匹配",
    },

    // ==================== 3. 发光与光效类 (7个) ====================
    "ADBE Glo2": {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        category: "glow_light",
        subCategory: "glow",
        tags: ["发光", "辉光", "glow", "边缘光", "光晕"],
        parameters: [
            { name: "Glow Threshold", type: "number", min: 0, max: 100, default: 40 },
            { name: "Glow Radius", type: "number", min: 0, max: 200, default: 25, intensityScale: 1.0 },
            { name: "Glow Intensity", type: "number", min: 0, max: 10, default: 1.5, intensityScale: 1.0 },
            { name: "Glow Colors", type: "enum", enumValues: ["Original Colors", "A & B Colors", "Arbitrary Map"], default: "Original Colors" },
            { name: "Glow Color A", type: "color", default: [1, 0.8, 0.2] },
            { name: "Glow Color B", type: "color", default: [0.2, 0.6, 1] },
        ],
        confidence: 0.85,
        description: "发光效果，最常用的光效之一",
    },
    "ADBE Starglow": {
        matchName: "ADBE Starglow",
        displayName: "Starglow",
        category: "glow_light",
        subCategory: "star",
        tags: ["星芒", "starglow", "star burst", "十字星", "射线星"],
        parameters: [
            { name: "Input Channel", type: "enum", enumValues: ["Luminance", "Red", "Green", "Blue", "Alpha"], default: "Luminance" },
            { name: "Threshold", type: "number", min: 0, max: 255, default: 150 },
            { name: "Boost Light", type: "number", min: 0, max: 100, default: 20, intensityScale: 1.0 },
            { name: "Streak Length", type: "number", min: 0, max: 200, default: 30, intensityScale: 1.0 },
            { name: "Streak Width", type: "number", min: 0, max: 100, default: 10 },
            { name: "Direction", type: "number", min: 0, max: 360, default: 0 },
            { name: "Streak Color Source", type: "enum", enumValues: ["Point Source", "Gradients"], default: "Point Source" },
        ],
        confidence: 0.80,
        description: "星芒效果，模拟星光射线",
    },
    "CC Light Rays": {
        matchName: "CC Light Rays",
        displayName: "CC Light Rays",
        category: "glow_light",
        subCategory: "volume",
        tags: ["体积光", "光柱", "god ray", "light rays", "光线", "光束"],
        parameters: [
            { name: "Intensity", type: "number", min: 0, max: 500, default: 100, intensityScale: 1.0 },
            { name: "Radius", type: "number", min: 0, max: 500, default: 200 },
            { name: "Center", type: "point", default: [0.5, 0.5] },
            { name: "Direction", type: "number", min: -360, max: 360, default: 45 },
            { name: "Shape", type: "enum", enumValues: ["V Shape", "Fan", "Round"], default: "V Shape" },
            { name: "Warp", type: "number", min: -100, max: 100, default: 0 },
        ],
        confidence: 0.83,
        description: "体积光效果，模拟丁达尔效应光束",
    },
    "CC Light Burst 2.5": {
        matchName: "CC Light Burst 2.5",
        displayName: "CC Light Burst 2.5",
        category: "glow_light",
        subCategory: "burst",
        tags: ["光线爆发", "light burst", "放射光", "中心光"],
        parameters: [
            { name: "Intensity", type: "number", min: 0, max: 300, default: 100, intensityScale: 1.0 },
            { name: "Burst", type: "number", min: 0, max: 200, default: 50 },
            { name: "Center", type: "point", default: [0.5, 0.5] },
            { name: "Ray Length", type: "number", min: 0, max: 200, default: 80 },
            { name: "Ray Count", type: "number", min: 1, max: 100, default: 20 },
        ],
        confidence: 0.78,
        description: "光线爆发，从中心向外放射的光线效果",
    },
    "ADBE Lens Flare": {
        matchName: "ADBE Lens Flare",
        displayName: "Lens Flare",
        category: "glow_light",
        subCategory: "flare",
        tags: ["镜头光晕", "lens flare", "光斑", "flare"],
        parameters: [
            { name: "Flare Center", type: "point", default: [0.5, 0.5] },
            { name: "Flare Brightness", type: "number", min: 0, max: 300, default: 100, intensityScale: 1.0 },
            { name: "Lens Type", type: "enum", enumValues: ["50-300mm Zoom", "35mm Prime", "105mm Prime"], default: "50-300mm Zoom" },
            { name: "Blend With Original", type: "number", min: 0, max: 100, default: 30 },
        ],
        confidence: 0.82,
        description: "镜头光晕，模拟相机镜头的光斑效果",
    },
    "ADBE Vegas": {
        matchName: "ADBE Vegas",
        displayName: "Vegas",
        category: "glow_light",
        subCategory: "stroke",
        tags: ["边缘发光", "vegas", "轮廓光", "描边光"],
        parameters: [
            { name: "Stroke", type: "enum", enumValues: ["Image Contours", "Alpha Channel", "Mask Path"], default: "Image Contours" },
            { name: "Segments", type: "number", min: 1, max: 64, default: 8 },
            { name: "Length", type: "number", min: 0, max: 1, default: 0.5, intensityScale: 0.5 },
            { name: "Color", type: "color", default: [0, 1, 1] },
            { name: "Thickness", type: "number", min: 0, max: 20, default: 3 },
            { name: "Hardness", type: "number", min: 0, max: 1, default: 0.5 },
            { name: "Start Point", type: "point", default: [0.5, 0.5] },
            { name: "Rotation", type: "number", min: 0, max: 360, default: 0 },
            { name: "Random Phase", type: "boolean", default: false },
        ],
        confidence: 0.76,
        description: "Vegas边缘发光，沿轮廓产生流动光线",
    },
    "CC Glue Gun": {
        matchName: "CC Glue Gun",
        displayName: "CC Glue Gun",
        category: "glow_light",
        subCategory: "glow",
        tags: ["胶状发光", "glue gun", "粘稠光", "边缘光"],
        parameters: [
            { name: "Intensity", type: "number", min: 0, max: 200, default: 50, intensityScale: 1.0 },
            { name: "Red", type: "number", min: 0, max: 255, default: 255 },
            { name: "Green", type: "number", min: 0, max: 255, default: 200 },
            { name: "Blue", type: "number", min: 0, max: 255, default: 100 },
            { name: "Source Layer", type: "number", min: 0, max: 10, default: 1 },
        ],
        confidence: 0.72,
        description: "CC胶状发光效果",
    },

    // ==================== 4. 扭曲与变形类 (9个) ====================
    "CC Lens": {
        matchName: "CC Lens",
        displayName: "CC Lens",
        category: "distort",
        subCategory: "lens",
        tags: ["镜头变形", "鱼眼", "广角", "fisheye", "lens"],
        parameters: [
            { name: "Size", type: "number", min: 0, max: 300, default: 100, intensityScale: 0.5 },
            { name: "Curvature", type: "number", min: -100, max: 100, default: 30, intensityScale: 1.0 },
        ],
        confidence: 0.82,
        description: "CC镜头变形，鱼眼/广角效果",
    },
    "ADBE Optics Compensation": {
        matchName: "ADBE Optics Compensation",
        displayName: "Optics Compensation",
        category: "distort",
        subCategory: "lens",
        tags: ["镜头畸变", "optics compensation", "鱼眼", "桶形畸变", "枕形畸变"],
        parameters: [
            { name: "Field of View (FOV)", type: "number", min: 1, max: 200, default: 20, intensityScale: 1.0 },
            { name: "Reverse Lens Distortion", type: "number", min: 0, max: 1, default: 0 },
            { name: "FOV Orientation", type: "number", min: 0, max: 2, default: 0 },
        ],
        confidence: 0.83,
        description: "光学补偿，校正或添加镜头畸变",
    },
    "ADBE Turbulent Displace": {
        matchName: "ADBE Turbulent Displace",
        displayName: "Turbulent Displace",
        category: "distort",
        subCategory: "noise",
        tags: ["流体扭曲", "湍流", "turbulent", "热浪", "水波", "波动扭曲"],
        parameters: [
            { name: "Displacement", type: "enum", enumValues: ["Turbulent", "Bulge", "Twist", "Wavy", "Fractal"], default: "Turbulent" },
            { name: "Amount", type: "number", min: 0, max: 500, default: 50, intensityScale: 1.0 },
            { name: "Size", type: "number", min: 1, max: 1000, default: 100 },
            { name: "Offset (Turbulence)", type: "point", default: [0, 0] },
            { name: "Complexity", type: "number", min: 1, max: 10, default: 5 },
            { name: "Evolution", type: "number", min: 0, max: 360, default: 0 },
        ],
        confidence: 0.85,
        description: "湍流扭曲，基于分形噪波的流体变形效果",
    },
    "ADBE Wave Warp": {
        matchName: "ADBE Wave Warp",
        displayName: "Wave Warp",
        category: "distort",
        subCategory: "wave",
        tags: ["波浪扭曲", "wave warp", "正弦波", "规律波动"],
        parameters: [
            { name: "Wave Type", type: "enum", enumValues: ["Sine", "Square", "Triangle", "Sawtooth", "Circle"], default: "Sine" },
            { name: "Wave Height", type: "number", min: 0, max: 500, default: 20, intensityScale: 1.0 },
            { name: "Wave Width", type: "number", min: 1, max: 5000, default: 200 },
            { name: "Direction", type: "number", min: 0, max: 360, default: 90 },
            { name: "Wave Speed", type: "number", min: -10, max: 10, default: 1 },
            { name: "Phase", type: "number", min: 0, max: 360, default: 0 },
        ],
        confidence: 0.82,
        description: "波浪扭曲，周期性波形变形",
    },
    "CC Power Pin": {
        matchName: "CC Power Pin",
        displayName: "CC Power Pin",
        category: "distort",
        subCategory: "perspective",
        tags: ["透视变形", "四角变形", "power pin", "corner pin", "梯形变形"],
        parameters: [
            { name: "Top Left", type: "point", default: [0, 0] },
            { name: "Top Right", type: "point", default: [1, 0] },
            { name: "Bottom Left", type: "point", default: [0, 1] },
            { name: "Bottom Right", type: "point", default: [1, 1] },
            { name: "Expansion", type: "number", min: -100, max: 100, default: 0, intensityScale: 0.5 },
        ],
        confidence: 0.78,
        description: "CC透视四角钉，透视变形效果",
    },
    "ADBE Mesh Warp": {
        matchName: "ADBE Mesh Warp",
        displayName: "Mesh Warp",
        category: "distort",
        subCategory: "mesh",
        tags: ["网格变形", "mesh warp", "曲面变形"],
        parameters: [
            { name: "Rows", type: "number", min: 1, max: 200, default: 7 },
            { name: "Columns", type: "number", min: 1, max: 200, default: 7 },
            { name: "Quality", type: "number", min: 1, max: 10, default: 3 },
            { name: "Distortion Mesh", type: "number", min: 0, max: 10, default: 0 },
        ],
        confidence: 0.70,
        description: "网格变形，通过网格控制点扭曲图像",
    },
    "ADBE Displacement Map": {
        matchName: "ADBE Displacement Map",
        displayName: "Displacement Map",
        category: "distort",
        subCategory: "map",
        tags: ["置换贴图", "displacement map", "位移图", "纹理变形"],
        parameters: [
            { name: "Displacement Map Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Use For Horizontal Displacement", type: "enum", enumValues: ["Full", "Red", "Green", "Blue", "Alpha", "Luminance"], default: "Red" },
            { name: "Max Horizontal Displacement", type: "number", min: -1000, max: 1000, default: 30, intensityScale: 1.0 },
            { name: "Use For Vertical Displacement", type: "enum", enumValues: ["Full", "Red", "Green", "Blue", "Alpha", "Luminance"], default: "Green" },
            { name: "Max Vertical Displacement", type: "number", min: -1000, max: 1000, default: 30, intensityScale: 1.0 },
            { name: "Displacement Map Behavior", type: "enum", enumValues: ["Stretch Map to Fit", "Tile Map", "Center Map"], default: "Stretch Map to Fit" },
        ],
        confidence: 0.75,
        description: "置换贴图，基于另一图层的像素值进行位移变形",
    },
    "ADBE Liquify": {
        matchName: "ADBE Liquify",
        displayName: "Liquify",
        category: "distort",
        subCategory: "liquify",
        tags: ["液化", "liquify", "局部变形", "推拉变形"],
        parameters: [
            { name: "Warp Tool", type: "number", min: 0, max: 10, default: 1 },
            { name: "Warp Size", type: "number", min: 1, max: 500, default: 50 },
            { name: "Warp Pressure", type: "number", min: 0, max: 100, default: 50, intensityScale: 1.0 },
            { name: "Distortion Mesh Offset", type: "point", default: [0, 0] },
            { name: "Distortion Percentage", type: "number", min: -100, max: 100, default: 100 },
        ],
        confidence: 0.72,
        description: "液化效果，笔刷式局部变形",
    },
    "ADBE Spherize": {
        matchName: "ADBE Spherize",
        displayName: "Spherize",
        category: "distort",
        subCategory: "sphere",
        tags: ["球面化", "spherize", "球形变形", "凸起"],
        parameters: [
            { name: "Amount", type: "number", min: -100, max: 100, default: 50, intensityScale: 1.0 },
            { name: "Mode", type: "enum", enumValues: ["Normal", "Horizontal Only", "Vertical Only"], default: "Normal" },
        ],
        confidence: 0.78,
        description: "球面化，将图像包裹在球面上",
    },

    // ==================== 5. 噪波与颗粒类 (6个) ====================
    "ADBE Fractal Noise": {
        matchName: "ADBE Fractal Noise",
        displayName: "Fractal Noise",
        category: "noise_grain",
        subCategory: "fractal",
        tags: ["分形噪波", "fractal noise", "烟雾", "火焰", "纹理"],
        parameters: [
            { name: "Fractal Type", type: "enum", enumValues: ["Basic", "Turbulent Basic", "Turbulent Sharp", "Dynamic", "Dynamic Progressive", "Smeary", "Max", "Rocky"], default: "Turbulent Basic" },
            { name: "Noise Type", type: "enum", enumValues: ["Block", "Linear", "Spline", "Soft Linear", "Spline"], default: "Soft Linear" },
            { name: "Contrast", type: "number", min: 0, max: 100, default: 50, intensityScale: 1.0 },
            { name: "Brightness", type: "number", min: -100, max: 100, default: 0 },
            { name: "Scale", type: "number", min: 10, max: 2000, default: 200 },
            { name: "Complexity", type: "number", min: 1, max: 10, default: 5 },
            { name: "Evolution", type: "number", min: 0, max: 360, default: 0 },
            { name: "Evolution Speed", type: "number", min: 0, max: 20, default: 5 },
        ],
        confidence: 0.78,
        description: "分形噪波，生成各种有机纹理",
    },
    "ADBE Noise": {
        matchName: "ADBE Noise",
        displayName: "Noise",
        category: "noise_grain",
        subCategory: "basic",
        tags: ["噪波", "noise", "颗粒", "杂色"],
        parameters: [
            { name: "Amount of Noise", type: "number", min: 0, max: 100, default: 5, intensityScale: 1.0 },
            { name: "Noise Type", type: "number", min: 0, max: 1, default: 0 },
            { name: "Clipping", type: "number", min: 0, max: 1, default: 0 },
        ],
        confidence: 0.83,
        description: "基础噪波效果",
    },
    "ADBE Noise HLS": {
        matchName: "ADBE Noise HLS",
        displayName: "Noise HLS",
        category: "noise_grain",
        subCategory: "hls",
        tags: ["HLS噪波", "noise hls", "色相噪波", "饱和度噪波"],
        parameters: [
            { name: "Noise", type: "enum", enumValues: ["Uniform", "Grain", "Spatial"], default: "Uniform" },
            { name: "Hue", type: "number", min: 0, max: 360, default: 30, intensityScale: 0.5 },
            { name: "Lightness", type: "number", min: 0, max: 100, default: 10, intensityScale: 1.0 },
            { name: "Saturation", type: "number", min: 0, max: 100, default: 15, intensityScale: 1.0 },
            { name: "Grain Size", type: "number", min: 1, max: 100, default: 5 },
        ],
        confidence: 0.75,
        description: "HLS噪波，分别在色相/亮度/饱和度通道添加噪波",
    },
    "ADBE Median": {
        matchName: "ADBE Median",
        displayName: "Median",
        category: "noise_grain",
        subCategory: "reduction",
        tags: ["中间值", "median", "降噪", "杂色减少"],
        parameters: [
            { name: "Radius", type: "number", min: 0, max: 30, default: 2, intensityScale: 1.0 },
            { name: "Operator", type: "enum", enumValues: ["Median", "Minimum", "Maximum"], default: "Median" },
        ],
        confidence: 0.78,
        description: "中间值滤镜，用于降噪或产生油画效果",
    },
    "ADBE Dust & Scratches": {
        matchName: "ADBE Dust & Scratches",
        displayName: "Dust & Scratches",
        category: "noise_grain",
        subCategory: "reduction",
        tags: ["蒙尘与划痕", "dust scratches", "去瑕疵", "降噪"],
        parameters: [
            { name: "Radius", type: "number", min: 0, max: 100, default: 5, intensityScale: 1.0 },
            { name: "Threshold", type: "number", min: 0, max: 255, default: 0 },
        ],
        confidence: 0.75,
        description: "蒙尘与划痕，去除小瑕疵和灰尘",
    },
    "ADBE Remove Grain": {
        matchName: "ADBE Remove Grain",
        displayName: "Remove Grain",
        category: "noise_grain",
        subCategory: "reduction",
        tags: ["去除颗粒", "remove grain", "降噪", "电影降噪"],
        parameters: [
            { name: "Viewing Mode", type: "enum", enumValues: ["Preview", "Final Output", "Blending Matte", "Composite Matte"], default: "Final Output" },
            { name: "Noise Reduction Settings", type: "number", min: 0, max: 10, default: 3 },
            { name: "Passes", type: "number", min: 1, max: 4, default: 2 },
            { name: "Mode", type: "enum", enumValues: ["Noise Reduction", "Color Noise Reduction"], default: "Noise Reduction" },
        ],
        confidence: 0.70,
        description: "去除颗粒，专业级降噪效果",
    },

    // ==================== 6. 通道与键控类 (6个) ====================
    "ADBE Color Key": {
        matchName: "ADBE Color Key",
        displayName: "Color Key",
        category: "channel_keying",
        subCategory: "keying",
        tags: ["颜色键控", "color key", "抠图", "绿幕", "蓝幕"],
        parameters: [
            { name: "Key Color", type: "color", default: [0, 1, 0] },
            { name: "Color Tolerance", type: "number", min: 0, max: 100, default: 20, intensityScale: 1.0 },
            { name: "Edge Feather", type: "number", min: 0, max: 10, default: 1 },
            { name: "Edge Thin", type: "number", min: -5, max: 5, default: 0 },
        ],
        confidence: 0.80,
        description: "颜色键控，基础抠图效果",
    },
    "ADBE Set Matte": {
        matchName: "ADBE Set Matte",
        displayName: "Set Matte",
        category: "channel_keying",
        subCategory: "matte",
        tags: ["设置蒙版", "set matte", "遮罩", "alpha通道"],
        parameters: [
            { name: "Take Matte From Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Use For Matte", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Luminance", "Hue", "Lightness", "Saturation"], default: "Alpha" },
            { name: "Stretch Matte to Fit", type: "boolean", default: true },
            { name: "Invert Matte", type: "boolean", default: false },
        ],
        confidence: 0.78,
        description: "设置蒙版，用另一图层作为Alpha通道",
    },
    "ADBE Shift Channels": {
        matchName: "ADBE Shift Channels",
        displayName: "Shift Channels",
        category: "channel_keying",
        subCategory: "channel",
        tags: ["通道移位", "shift channels", "通道替换"],
        parameters: [
            { name: "Take Alpha From", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Luminance", "Hue", "Lightness", "Saturation", "Full", "Off"], default: "Alpha" },
            { name: "Take Red From", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Luminance", "Hue", "Lightness", "Saturation", "Full", "Off"], default: "Red" },
            { name: "Take Green From", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Luminance", "Hue", "Lightness", "Saturation", "Full", "Off"], default: "Green" },
            { name: "Take Blue From", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Luminance", "Hue", "Lightness", "Saturation", "Full", "Off"], default: "Blue" },
        ],
        confidence: 0.75,
        description: "通道移位，重新映射各颜色通道",
    },
    "ADBE Calculations": {
        matchName: "ADBE Calculations",
        displayName: "Calculations",
        category: "channel_keying",
        subCategory: "composite",
        tags: ["计算", "calculations", "通道混合", "合成"],
        parameters: [
            { name: "Input Channel", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Gray"], default: "Gray" },
            { name: "Second Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Second Layer Channel", type: "enum", enumValues: ["Red", "Green", "Blue", "Alpha", "Gray"], default: "Gray" },
            { name: "Blending Mode", type: "enum", enumValues: ["Multiply", "Screen", "Overlay", "Darken", "Lighten", "Difference", "Add", "Subtract"], default: "Multiply" },
            { name: "Opacity", type: "number", min: 0, max: 100, default: 100, intensityScale: 0.5 },
        ],
        confidence: 0.72,
        description: "计算，混合两个通道创建新的通道",
    },
    "ADBE Simple Choker": {
        matchName: "ADBE Simple Choker",
        displayName: "Simple Choker",
        category: "channel_keying",
        subCategory: "matte",
        tags: ["简单抑制", "simple choker", "遮罩收缩", "边缘调整"],
        parameters: [
            { name: "Choke Matte", type: "number", min: -200, max: 200, default: 0, intensityScale: 1.0 },
        ],
        confidence: 0.88,
        description: "简单抑制，收缩或扩展蒙版边缘",
    },
    "ADBE Matte Choker": {
        matchName: "ADBE Matte Choker",
        displayName: "Matte Choker",
        category: "channel_keying",
        subCategory: "matte",
        tags: ["蒙版抑制", "matte choker", "遮罩细化", "边缘调整"],
        parameters: [
            { name: "Geometric Softness 1", type: "number", min: 0, max: 100, default: 2, intensityScale: 1.0 },
            { name: "Choke 1", type: "number", min: -100, max: 100, default: 0 },
            { name: "Gray Level Softness 1", type: "number", min: 0, max: 100, default: 50 },
            { name: "Geometric Softness 2", type: "number", min: 0, max: 100, default: 2, intensityScale: 1.0 },
            { name: "Choke 2", type: "number", min: -100, max: 100, default: 0 },
            { name: "Gray Level Softness 2", type: "number", min: 0, max: 100, default: 50 },
            { name: "Iterations", type: "number", min: 1, max: 10, default: 2 },
        ],
        confidence: 0.80,
        description: "蒙版抑制，两级细化蒙版边缘",
    },

    // ==================== 7. 风格化类 (7个) ====================
    "ADBE Find Edges": {
        matchName: "ADBE Find Edges",
        displayName: "Find Edges",
        category: "stylize",
        subCategory: "edge",
        tags: ["查找边缘", "find edges", "轮廓", "线稿", "素描"],
        parameters: [
            { name: "Invert", type: "boolean", default: false },
            { name: "Blend With Original", type: "number", min: 0, max: 100, default: 0, intensityScale: 0.5 },
        ],
        confidence: 0.82,
        description: "查找边缘，将图像转换为线条轮廓",
    },
    "ADBE Cartoon": {
        matchName: "ADBE Cartoon",
        displayName: "Cartoon",
        category: "stylize",
        subCategory: "toon",
        tags: ["卡通", "cartoon", "漫画", "动画风格"],
        parameters: [
            { name: "Render", type: "enum", enumValues: ["Fill & Edges", "Fill", "Edges"], default: "Fill & Edges" },
            { name: "Detail Radius", type: "number", min: 0, max: 50, default: 10 },
            { name: "Detail Threshold", type: "number", min: 0, max: 100, default: 50, intensityScale: 0.5 },
            { name: "Shading Steps", type: "number", min: 2, max: 10, default: 5 },
            { name: "Shading Smoothness", type: "number", min: 0, max: 100, default: 50 },
            { name: "Edge Threshold", type: "number", min: 0, max: 100, default: 40 },
            { name: "Edge Width", type: "number", min: 0.5, max: 10, default: 1.5 },
            { name: "Edge Softness", type: "number", min: 0, max: 10, default: 0.5 },
            { name: "Edge Opacity", type: "number", min: 0, max: 100, default: 100, intensityScale: 0.5 },
        ],
        confidence: 0.78,
        description: "卡通效果，将图像转换为卡通风格",
    },
    "ADBE Mosaic": {
        matchName: "ADBE Mosaic",
        displayName: "Mosaic",
        category: "stylize",
        subCategory: "pixel",
        tags: ["马赛克", "mosaic", "像素化", "打码"],
        parameters: [
            { name: "Horizontal Blocks", type: "number", min: 1, max: 1000, default: 50 },
            { name: "Vertical Blocks", type: "number", min: 1, max: 1000, default: 50 },
            { name: "Sharp Colors", type: "boolean", default: false },
        ],
        confidence: 0.88,
        description: "马赛克，像素化效果",
    },
    "ADBE Posterize": {
        matchName: "ADBE Posterize",
        displayName: "Posterize",
        category: "stylize",
        subCategory: "tonal",
        tags: ["色调分离", "posterize", "海报效果", "色阶减少"],
        parameters: [
            { name: "Level", type: "number", min: 2, max: 255, default: 5, intensityScale: 0.3 },
        ],
        confidence: 0.80,
        description: "色调分离，减少颜色数量产生海报效果",
    },
    "ADBE Texturize": {
        matchName: "ADBE Texturize",
        displayName: "Texturize",
        category: "stylize",
        subCategory: "texture",
        tags: ["纹理化", "texturize", "质感", "纹理"],
        parameters: [
            { name: "Texture Layer", type: "number", min: 0, max: 10, default: 1 },
            { name: "Texture Placement", type: "number", min: 0, max: 2, default: 0 },
            { name: "Texture Contrast", type: "number", min: 0, max: 200, default: 100, intensityScale: 1.0 },
            { name: "Texture Brightness", type: "number", min: -100, max: 100, default: 0 },
            { name: "Composite Operation", type: "number", min: 0, max: 3, default: 1 },
        ],
        confidence: 0.75,
        description: "纹理化，为图像添加纹理质感",
    },
    "CC Vignette": {
        matchName: "CC Vignette",
        displayName: "CC Vignette",
        category: "stylize",
        subCategory: "vignette",
        tags: ["暗角", "vignette", "vignetting", "晕影", "电影感"],
        parameters: [
            { name: "Amount", type: "number", min: -100, max: 100, default: -30, intensityScale: 1.0 },
            { name: "Angle", type: "number", min: -180, max: 180, default: 0 },
            { name: "Midpoint", type: "number", min: 0, max: 100, default: 70 },
            { name: "Roundness", type: "number", min: 0, max: 100, default: 50 },
            { name: "Softness", type: "number", min: 0, max: 100, default: 50 },
        ],
        confidence: 0.85,
        description: "CC暗角，为画面添加暗角/亮角效果",
    },
    "CC Kaleida": {
        matchName: "CC Kaleida",
        displayName: "CC Kaleida",
        category: "stylize",
        subCategory: "mirror",
        tags: ["万花筒", "kaleida", "kaleidoscope", "镜像", "对称"],
        parameters: [
            { name: "Center", type: "point", default: [0.5, 0.5] },
            { name: "Size", type: "number", min: 10, max: 500, default: 100 },
            { name: "Mirroring", type: "enum", enumValues: ["1 Mirror", "2 Mirrors", "3 Mirrors", "4 Mirrors", "5 Mirrors", "6 Mirrors", "8 Mirrors", "12 Mirrors"], default: "4 Mirrors" },
            { name: "Rotation", type: "number", min: 0, max: 360, default: 0 },
            { name: "Floating Center", type: "boolean", default: true },
        ],
        confidence: 0.75,
        description: "CC万花筒，镜像对称效果",
    },
    "ADBE Roughen Edges": {
        matchName: "ADBE Roughen Edges",
        displayName: "Roughen Edges",
        category: "stylize",
        subCategory: "edge",
        tags: ["粗糙边缘", "roughen edges", "边缘粗糙化", "风化效果"],
        parameters: [
            { name: "Edge Type", type: "enum", enumValues: ["Roughen", "Rusty", "Spiky", "Photocopy", "Rough Color"], default: "Roughen" },
            { name: "Edge Color", type: "color", default: [1, 1, 1] },
            { name: "Border", type: "number", min: 0, max: 200, default: 10, intensityScale: 1.0 },
            { name: "Edge Sharpness", type: "number", min: 0, max: 10, default: 3 },
            { name: "Fractal Influence", type: "number", min: 0, max: 1, default: 0.5 },
            { name: "Scale", type: "number", min: 10, max: 5000, default: 100 },
            { name: "Complexity", type: "number", min: 1, max: 10, default: 3 },
            { name: "Evolution", type: "number", min: 0, max: 360, default: 0 },
        ],
        confidence: 0.80,
        description: "粗糙边缘，为图层边缘添加风化、粗糙效果",
    },

    // ==================== 8. 透视与3D类 (5个) ====================
    "ADBE Drop Shadow": {
        matchName: "ADBE Drop Shadow",
        displayName: "Drop Shadow",
        category: "perspective_3d",
        subCategory: "shadow",
        tags: ["投影", "drop shadow", "阴影", "立体感"],
        parameters: [
            { name: "Shadow Color", type: "color", default: [0, 0, 0] },
            { name: "Opacity", type: "number", min: 0, max: 255, default: 100, intensityScale: 1.0 },
            { name: "Direction", type: "number", min: 0, max: 360, default: 135 },
            { name: "Distance", type: "number", min: 0, max: 3000, default: 5, intensityScale: 1.0 },
            { name: "Softness", type: "number", min: 0, max: 100, default: 10, intensityScale: 1.0 },
        ],
        confidence: 0.90,
        description: "投影，为图层添加阴影效果",
    },
    "ADBE Bevel Alpha": {
        matchName: "ADBE Bevel Alpha",
        displayName: "Bevel Alpha",
        category: "perspective_3d",
        subCategory: "bevel",
        tags: ["斜面Alpha", "bevel alpha", "倒角", "立体感", "浮雕"],
        parameters: [
            { name: "Edge Thickness", type: "number", min: 0, max: 50, default: 5, intensityScale: 1.0 },
            { name: "Light Angle", type: "number", min: 0, max: 360, default: -45 },
            { name: "Light Color", type: "color", default: [1, 1, 1] },
            { name: "Light Intensity", type: "number", min: 0, max: 200, default: 70, intensityScale: 0.5 },
        ],
        confidence: 0.82,
        description: "斜面Alpha，沿Alpha通道边缘产生三维倒角效果",
    },
    "ADBE Basic 3D": {
        matchName: "ADBE Basic 3D",
        displayName: "Basic 3D",
        category: "perspective_3d",
        subCategory: "3d",
        tags: ["基础3D", "basic 3d", "三维旋转", "伪3D"],
        parameters: [
            { name: "Swivel", type: "number", min: -360, max: 360, default: 0 },
            { name: "Tilt", type: "number", min: -360, max: 360, default: 0 },
            { name: "Distance to Image", type: "number", min: 0, max: 1000, default: 0, intensityScale: 0.5 },
            { name: "Specular Highlight", type: "boolean", default: false },
            { name: "Preview", type: "number", min: 0, max: 1, default: 0 },
        ],
        confidence: 0.80,
        description: "基础3D，简单的三维旋转变换",
    },
    "CC Cylinder": {
        matchName: "CC Cylinder",
        displayName: "CC Cylinder",
        category: "perspective_3d",
        subCategory: "3d",
        tags: ["圆柱体", "cylinder", "圆筒", "3d变形"],
        parameters: [
            { name: "Radius", type: "number", min: 0, max: 5, default: 1, intensityScale: 0.5 },
            { name: "Rotation", type: "number", min: -360, max: 360, default: 0 },
            { name: "Light Intensity", type: "number", min: 0, max: 100, default: 60, intensityScale: 0.5 },
            { name: "Light Direction", type: "number", min: 0, max: 360, default: 90 },
            { name: "Ambient Light", type: "number", min: 0, max: 100, default: 20 },
            { name: "Render", type: "enum", enumValues: ["Full", "Outside", "Inside"], default: "Full" },
        ],
        confidence: 0.75,
        description: "CC圆柱体，将图像包裹在圆柱上",
    },
    "CC Sphere": {
        matchName: "CC Sphere",
        displayName: "CC Sphere",
        category: "perspective_3d",
        subCategory: "3d",
        tags: ["球体", "sphere", "球形", "3d变形"],
        parameters: [
            { name: "Radius", type: "number", min: 0, max: 2, default: 1, intensityScale: 0.5 },
            { name: "Offset", type: "point", default: [0, 0] },
            { name: "Rotation", type: "number", min: -360, max: 360, default: 0 },
            { name: "Light Intensity", type: "number", min: 0, max: 200, default: 80, intensityScale: 0.5 },
            { name: "Light Height", type: "number", min: -90, max: 90, default: 45 },
            { name: "Light Direction", type: "number", min: 0, max: 360, default: 90 },
            { name: "Shading", type: "enum", enumValues: ["On", "Off"], default: "On" },
            { name: "Render", type: "enum", enumValues: ["Full", "Outside", "Inside"], default: "Full" },
        ],
        confidence: 0.78,
        description: "CC球体，将图像包裹在球体上",
    },

    // ==================== 9. 生成与绘制类 (5个) ====================
    "ADBE Fill": {
        matchName: "ADBE Fill",
        displayName: "Fill",
        category: "generate_draw",
        subCategory: "fill",
        tags: ["填充", "fill", "纯色填充"],
        parameters: [
            { name: "Color", type: "color", default: [1, 1, 1] },
        ],
        confidence: 0.92,
        description: "填充，用纯色填充图层",
    },
    "ADBE Stroke": {
        matchName: "ADBE Stroke",
        displayName: "Stroke",
        category: "generate_draw",
        subCategory: "stroke",
        tags: ["描边", "stroke", "笔触", "绘制"],
        parameters: [
            { name: "Color", type: "color", default: [1, 1, 1] },
            { name: "Brush Size", type: "number", min: 1, max: 100, default: 4, intensityScale: 1.0 },
            { name: "Brush Hardness", type: "number", min: 0, max: 1, default: 0.9 },
            { name: "Opacity", type: "number", min: 0, max: 100, default: 100, intensityScale: 0.5 },
            { name: "Start", type: "number", min: 0, max: 100, default: 0 },
            { name: "End", type: "number", min: 0, max: 100, default: 100 },
            { name: "Spacing", type: "number", min: 0, max: 5, default: 0.05 },
            { name: "Paint on", type: "enum", enumValues: ["Transparent", "Original Image"], default: "Transparent" },
        ],
        confidence: 0.84,
        description: "描边，沿蒙版或路径绘制笔触",
    },
    "ADBE Ramp": {
        matchName: "ADBE Ramp",
        displayName: "Ramp",
        category: "generate_draw",
        subCategory: "gradient",
        tags: ["渐变", "ramp", "gradient", "渐变填充"],
        parameters: [
            { name: "Start of Ramp", type: "point", default: [0.5, 0] },
            { name: "Start Color", type: "color", default: [1, 1, 1] },
            { name: "End of Ramp", type: "point", default: [0.5, 1] },
            { name: "End Color", type: "color", default: [0, 0, 0] },
            { name: "Ramp Shape", type: "enum", enumValues: ["Linear Ramp", "Radial Ramp"], default: "Linear Ramp" },
            { name: "Ramp Scatter", type: "number", min: 0, max: 100, default: 0 },
            { name: "Blend With Original", type: "number", min: 0, max: 100, default: 0 },
        ],
        confidence: 0.85,
        description: "渐变，生成线性或径向渐变",
    },
    "ADBE 4-Color Gradient": {
        matchName: "ADBE 4-Color Gradient",
        displayName: "4-Color Gradient",
        category: "generate_draw",
        subCategory: "gradient",
        tags: ["四色渐变", "4-color gradient", "多色渐变"],
        parameters: [
            { name: "Positions & Colors", type: "number", min: 0, max: 10, default: 0 },
            { name: "Color 1", type: "color", default: [1, 0, 0] },
            { name: "Color 2", type: "color", default: [1, 1, 0] },
            { name: "Color 3", type: "color", default: [0, 1, 1] },
            { name: "Color 4", type: "color", default: [0, 0, 1] },
            { name: "Blend", type: "number", min: 0, max: 100, default: 50, intensityScale: 0.5 },
            { name: "Jitter", type: "number", min: 0, max: 100, default: 0 },
            { name: "Opacity", type: "number", min: 0, max: 100, default: 100, intensityScale: 0.5 },
            { name: "Blending Mode", type: "enum", enumValues: ["Normal", "Transparency"], default: "Normal" },
        ],
        confidence: 0.78,
        description: "四色渐变，四角颜色的渐变效果",
    },
    "ADBE Circle": {
        matchName: "ADBE Circle",
        displayName: "Circle",
        category: "generate_draw",
        subCategory: "shape",
        tags: ["圆形", "circle", "圆环", "形状生成"],
        parameters: [
            { name: "Center", type: "point", default: [0.5, 0.5] },
            { name: "Radius", type: "number", min: 0, max: 2000, default: 100, intensityScale: 1.0 },
            { name: "Edge", type: "enum", enumValues: ["None", "Edge Radius", "Edge Thickness", "Edge Thickness * Radius"], default: "None" },
            { name: "Edge Radius", type: "number", min: 0, max: 500, default: 10 },
            { name: "Feather", type: "number", min: 0, max: 100, default: 0 },
            { name: "Invert Circle", type: "boolean", default: false },
            { name: "Color", type: "color", default: [1, 1, 1] },
            { name: "Blending Mode", type: "enum", enumValues: ["None", "Transparency"], default: "None" },
        ],
        confidence: 0.80,
        description: "圆形，生成圆形或圆环形状",
    },
    "CC Particle World": {
        matchName: "CC Particle World",
        displayName: "CC Particle World",
        category: "generate_draw",
        subCategory: "particle",
        tags: ["粒子世界", "particle world", "粒子系统", "粒子特效"],
        parameters: [
            { name: "Birth Rate", type: "number", min: 0, max: 1000, default: 100, intensityScale: 1.0 },
            { name: "Longevity", type: "number", min: 0.1, max: 10, default: 2.0 },
            { name: "Position X", type: "number", min: -1, max: 2, default: 0.5 },
            { name: "Position Y", type: "number", min: -1, max: 2, default: 0.5 },
            { name: "Position Z", type: "number", min: -1, max: 1, default: 0 },
            { name: "Velocity", type: "number", min: 0, max: 500, default: 50, intensityScale: 0.8 },
            { name: "Gravity", type: "number", min: -200, max: 200, default: 0 },
            { name: "Particle Radius", type: "number", min: 0.1, max: 100, default: 5, intensityScale: 0.6 },
            { name: "Opacity", type: "number", min: 0, max: 100, default: 100 },
            { name: "Red", type: "number", min: 0, max: 1, default: 1 },
            { name: "Green", type: "number", min: 0, max: 1, default: 1 },
            { name: "Blue", type: "number", min: 0, max: 1, default: 1 },
        ],
        confidence: 0.82,
        description: "CC粒子世界，专业的3D粒子效果生成器",
    },
};

// ============================================================================
// 效果关系图谱
// ============================================================================

export const EFFECT_RELATIONS: Record<string, EffectRelation[]> = {
    "ADBE Glo2": [
        { effect: "ADBE HUE SATURATION", type: "synergy", weight: 0.8, reason: "发光+饱和度提升，光效更鲜艳" },
        { effect: "ADBE Gaussian Blur 2", type: "synergy", weight: 0.6, reason: "先模糊后发光，柔化光效边缘" },
        { effect: "ADBE Unsharp Mask", type: "synergy", weight: 0.4, reason: "锐化后发光，边缘更清晰" },
    ],
    "ADBE Gaussian Blur 2": [
        { effect: "ADBE Unsharp Mask", type: "mutex", weight: -0.7, reason: "模糊和锐化效果相互抵消" },
        { effect: "ADBE Brightness & Contrast 2", type: "synergy", weight: 0.5, reason: "模糊后调整对比度，增强氛围感" },
    ],
    "ADBE Color Balance": [
        { effect: "ADBE HUE SATURATION", type: "synergy", weight: 0.7, reason: "色彩平衡+饱和度，调色更丰富" },
        { effect: "ADBE Brightness & Contrast 2", type: "synergy", weight: 0.6, reason: "色偏+对比度，电影感调色" },
        { effect: "ADBE Protractor2", type: "synergy", weight: 0.5, reason: "色阶+色彩平衡，精细调色" },
    ],
    "ADBE Fractal Noise": [
        { effect: "ADBE Colorama", type: "synergy", weight: 0.7, reason: "分形噪波+色彩映射，创意纹理" },
        { effect: "ADBE Turbulent Displace", type: "synergy", weight: 0.6, reason: "噪波+扭曲，有机效果" },
        { effect: "ADBE Tritone", type: "synergy", weight: 0.5, reason: "噪波+三色渐变，风格化纹理" },
    ],
    "CC Vignette": [
        { effect: "ADBE Protractor2", type: "synergy", weight: 0.8, reason: "暗角+色阶，经典电影感" },
        { effect: "ADBE Color Balance", type: "synergy", weight: 0.7, reason: "暗角+色彩平衡，增强氛围" },
    ],
    "ADBE Drop Shadow": [
        { effect: "ADBE Bevel Alpha", type: "synergy", weight: 0.7, reason: "投影+倒角，立体效果更强" },
        { effect: "ADBE Gaussian Blur 2", type: "prerequisite", weight: 0.3, reason: "模糊后投影更自然" },
    ],
    "ADBE Color Key": [
        { effect: "ADBE Simple Choker", type: "post", weight: 0.8, reason: "键控后必须收缩边缘" },
        { effect: "ADBE Matte Choker", type: "post", weight: 0.9, reason: "键控后细化蒙版" },
        { effect: "ADBE Unsharp Mask", type: "mutex", weight: -0.5, reason: "锐化会破坏键控边缘" },
    ],
    "ADBE Camera Lens Blur": [
        { effect: "ADBE Lens Flare", type: "synergy", weight: 0.7, reason: "景深+镜头光晕，真实相机效果" },
    ],
};

// ============================================================================
// 风格配方库 (扩展到25个)
// ============================================================================

export const STYLE_RECIPES: StyleRecipe[] = [
    {
        name: "cinematic",
        displayName: "电影感",
        category: "电影风格",
        description: "经典电影调色风格，高对比度、适度饱和度、暖色调倾向，营造胶片质感",
        keywords: ["电影", "胶片", "高对比", "暖调", "质感", "cinematic"],
        intensityRange: [0.2, 1.5],
        effects: [
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 5, "Contrast": 25, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 40 },
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 5, "Shadow Green Balance": 2, "Shadow Blue Balance": -3, "Midtone Red Balance": 8, "Midtone Green Balance": 4, "Midtone Blue Balance": -5, "Hilight Red Balance": 3, "Hilight Green Balance": 2, "Hilight Blue Balance": -2 }, intensityParam: "Midtone Red Balance", intensityFactor: 15 },
            { matchName: "CC Vignette", settings: { "Amount": -25, "Midpoint": 70, "Roundness": 50, "Softness": 60 }, intensityParam: "Amount", intensityFactor: -50 },
        ],
    },
    {
        name: "cyberpunk",
        displayName: "赛博朋克",
        category: "科幻风格",
        description: "霓虹色彩、高对比度、蓝紫色调，未来科技感十足",
        keywords: ["赛博朋克", "霓虹", "科幻", "蓝紫", "未来", "cyberpunk"],
        intensityRange: [0.3, 2.0],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": -10, "Master Saturation": 25, "Master Lightness": 0 }, intensityParam: "Master Saturation", intensityFactor: 50 },
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": -8, "Shadow Green Balance": 3, "Shadow Blue Balance": 15, "Midtone Red Balance": -12, "Midtone Green Balance": 5, "Midtone Blue Balance": 20, "Hilight Red Balance": -5, "Hilight Green Balance": 2, "Hilight Blue Balance": 10 }, intensityParam: "Midtone Blue Balance", intensityFactor: 30 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 50, "Glow Radius": 25, "Glow Intensity": 1.2, "Glow Colors": 1, "Glow Color A": [0.3, 0.2, 1], "Glow Color B": [1, 0.2, 0.8] }, intensityParam: "Glow Intensity", intensityFactor: 2.5 },
            { matchName: "ADBE Chromatic Aberration", settings: { "Amount": 5 }, intensityParam: "Amount", intensityFactor: 10 },
        ],
    },
    {
        name: "dreamy",
        displayName: "梦幻",
        category: "氛围风格",
        description: "柔焦效果、低对比度、柔和色彩，营造梦幻朦胧的氛围",
        keywords: ["梦幻", "朦胧", "柔焦", "柔和", "浪漫", "dreamy"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE Gaussian Blur 2", settings: { "Blurriness": 5, "Blur Dimensions": 3 }, intensityParam: "Blurriness", intensityFactor: 12 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 10, "Contrast": -15, "Use Legacy": 0 }, intensityParam: "Brightness", intensityFactor: 20 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 40, "Glow Radius": 40, "Glow Intensity": 0.6, "Glow Colors": 1, "Glow Color A": [1, 0.9, 0.95], "Glow Color B": [0.9, 0.95, 1] }, intensityParam: "Glow Intensity", intensityFactor: 1.2 },
        ],
    },
    {
        name: "horror",
        displayName: "恐怖",
        category: "情绪风格",
        description: "低饱和度、高对比度、暗调处理，营造惊悚压抑的氛围",
        keywords: ["恐怖", "惊悚", "暗调", "压抑", "低饱和", "horror"],
        intensityRange: [0.4, 2.0],
        effects: [
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": -15, "Contrast": 30, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 50 },
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -30, "Master Lightness": -10 }, intensityParam: "Master Saturation", intensityFactor: -50 },
            { matchName: "ADBE Fractal Noise", settings: { "Fractal Type": "Cloudy", "Noise Type": "Soft Linear", "Contrast": 50, "Brightness": -20, "Scale": 200, "Complexity": 5, "Evolution": 0 }, intensityParam: "Contrast", intensityFactor: 80 },
        ],
    },
    {
        name: "vintage",
        displayName: "复古",
        category: "怀旧风格",
        description: "暖黄色调、颗粒质感、低对比度，模拟老电影胶片效果",
        keywords: ["复古", "怀旧", "暖黄", "胶片", "颗粒", "vintage"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 10, "Shadow Green Balance": 5, "Shadow Blue Balance": -8, "Midtone Red Balance": 15, "Midtone Green Balance": 8, "Midtone Blue Balance": -12, "Hilight Red Balance": 8, "Hilight Green Balance": 5, "Hilight Blue Balance": -6 }, intensityParam: "Midtone Red Balance", intensityFactor: 25 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 5, "Contrast": -10, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: -20 },
            { matchName: "ADBE Noise", settings: { "Amount of Noise": 3, "Noise Type": 1, "Clipping": 0 }, intensityParam: "Amount of Noise", intensityFactor: 8 },
            { matchName: "CC Vignette", settings: { "Amount": -20, "Midpoint": 65, "Roundness": 40, "Softness": 70 }, intensityParam: "Amount", intensityFactor: -40 },
        ],
    },
    {
        name: "neon",
        displayName: "霓虹",
        category: "光效风格",
        description: "强烈发光效果、高饱和度、霓虹色彩，营造赛博朋克的光感",
        keywords: ["霓虹", "发光", "高饱和", "光效", "炫彩", "neon"],
        intensityRange: [0.4, 2.5],
        effects: [
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 30, "Glow Radius": 30, "Glow Intensity": 1.5, "Glow Colors": 1, "Glow Color A": [0, 1, 1], "Glow Color B": [1, 0, 1] }, intensityParam: "Glow Intensity", intensityFactor: 3 },
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": 35, "Master Lightness": 5 }, intensityParam: "Master Saturation", intensityFactor: 60 },
            { matchName: "ADBE Starglow", settings: { "Input Channel": 0, "Threshold": 180, "Boost Light": 30, "Streak Length": 40, "Streak Width": 8 }, intensityParam: "Streak Length", intensityFactor: 60 },
        ],
    },
    {
        name: "minimal",
        displayName: "极简",
        category: "简约风格",
        description: "低饱和度、柔和色调、干净简洁，追求极简主义美学",
        keywords: ["极简", "简约", "干净", "低饱和", "柔和", "minimal"],
        intensityRange: [0.2, 1.2],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -20, "Master Lightness": 5 }, intensityParam: "Master Saturation", intensityFactor: -35 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 8, "Contrast": -5, "Use Legacy": 0 }, intensityParam: "Brightness", intensityFactor: 15 },
        ],
    },
    {
        name: "drama",
        displayName: "戏剧性",
        category: "情绪风格",
        description: "高对比度、深阴影、强反差，营造戏剧性张力",
        keywords: ["戏剧", "高对比", "阴影", "张力", "强烈", "drama"],
        intensityRange: [0.4, 2.0],
        effects: [
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": -5, "Contrast": 40, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 60 },
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": -3, "Shadow Green Balance": -5, "Shadow Blue Balance": -8, "Midtone Red Balance": 3, "Midtone Green Balance": 0, "Midtone Blue Balance": -5, "Hilight Red Balance": 5, "Hilight Green Balance": 3, "Hilight Blue Balance": 0 }, intensityParam: "Hilight Red Balance", intensityFactor: 10 },
            { matchName: "CC Vignette", settings: { "Amount": -35, "Midpoint": 60, "Roundness": 50, "Softness": 50 }, intensityParam: "Amount", intensityFactor: -60 },
        ],
    },
    {
        name: "warm",
        displayName: "暖色调",
        category: "色彩风格",
        description: "橙红暖调、温馨舒适，营造温暖治愈的视觉感受",
        keywords: ["暖色", "橙红", "温馨", "治愈", "阳光", "warm"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 8, "Shadow Green Balance": 4, "Shadow Blue Balance": -6, "Midtone Red Balance": 12, "Midtone Green Balance": 6, "Midtone Blue Balance": -10, "Hilight Red Balance": 6, "Hilight Green Balance": 4, "Hilight Blue Balance": -4 }, intensityParam: "Midtone Red Balance", intensityFactor: 20 },
            { matchName: "ADBE Photo Filter", settings: { "Filter": "Warming Filter (85)", "Density": 25, "Preserve Luminosity": 1 }, intensityParam: "Density", intensityFactor: 50 },
        ],
    },
    {
        name: "cool",
        displayName: "冷色调",
        category: "色彩风格",
        description: "蓝青冷调、清冷干净，营造冷静理性的视觉感受",
        keywords: ["冷色", "蓝青", "清冷", "冷静", "干净", "cool"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": -8, "Shadow Green Balance": 2, "Shadow Blue Balance": 10, "Midtone Red Balance": -10, "Midtone Green Balance": 3, "Midtone Blue Balance": 15, "Hilight Red Balance": -5, "Hilight Green Balance": 2, "Hilight Blue Balance": 8 }, intensityParam: "Midtone Blue Balance", intensityFactor: 25 },
            { matchName: "ADBE Photo Filter", settings: { "Filter": "Cooling Filter (80)", "Density": 20, "Preserve Luminosity": 1 }, intensityParam: "Density", intensityFactor: 40 },
        ],
    },
    {
        name: "grunge",
        displayName: "脏污油渍",
        category: "质感风格",
        description: "高对比度、杂色颗粒、低饱和度，营造粗糙破旧的质感",
        keywords: ["脏污", "油渍", "颗粒", "粗糙", "破旧", "grunge"],
        intensityRange: [0.4, 2.0],
        effects: [
            { matchName: "ADBE Fractal Noise", settings: { "Fractal Type": "Turbulent Sharp", "Noise Type": "Soft Linear", "Contrast": 60, "Brightness": -30, "Scale": 150, "Complexity": 6, "Evolution": 0 }, intensityParam: "Contrast", intensityFactor: 90 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": -10, "Contrast": 35, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 55 },
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -25, "Master Lightness": -5 }, intensityParam: "Master Saturation", intensityFactor: -45 },
        ],
    },
    {
        name: "soft_glow",
        displayName: "柔光",
        category: "光效风格",
        description: "柔和发光、暖调倾向、朦胧美感，营造温柔梦幻的氛围",
        keywords: ["柔光", "发光", "温柔", "梦幻", "暖调", "soft glow"],
        intensityRange: [0.3, 2.0],
        effects: [
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 45, "Glow Radius": 35, "Glow Intensity": 0.9, "Glow Colors": 1, "Glow Color A": [1, 0.95, 0.85], "Glow Color B": [1, 0.85, 0.7] }, intensityParam: "Glow Intensity", intensityFactor: 1.8 },
            { matchName: "ADBE Gaussian Blur 2", settings: { "Blurriness": 3, "Blur Dimensions": 3 }, intensityParam: "Blurriness", intensityFactor: 8 },
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 5, "Shadow Green Balance": 3, "Shadow Blue Balance": -2, "Midtone Red Balance": 8, "Midtone Green Balance": 5, "Midtone Blue Balance": -4, "Hilight Red Balance": 4, "Hilight Green Balance": 3, "Hilight Blue Balance": -2 }, intensityParam: "Midtone Red Balance", intensityFactor: 12 },
        ],
    },
    {
        name: "high_energy",
        displayName: "高能",
        category: "情绪风格",
        description: "高饱和度、高对比度、强烈色彩冲击，充满活力与能量",
        keywords: ["高能", "活力", "高饱和", "强烈", "冲击", "high energy"],
        intensityRange: [0.4, 2.5],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": 35, "Master Lightness": 5 }, intensityParam: "Master Saturation", intensityFactor: 70 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 5, "Contrast": 30, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 50 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 55, "Glow Radius": 20, "Glow Intensity": 1.0, "Glow Colors": 1, "Glow Color A": [1, 0.5, 0.2], "Glow Color B": [0.2, 0.7, 1] }, intensityParam: "Glow Intensity", intensityFactor: 2 },
            { matchName: "CC Light Rays", settings: { "Intensity": 80, "Radius": 200, "Direction": 45, "Shape": "V Shape" }, intensityParam: "Intensity", intensityFactor: 150 },
        ],
    },
    {
        name: "noir",
        displayName: "黑色电影",
        category: "电影风格",
        description: "黑白效果、高对比度、硬阴影，经典黑色电影风格",
        keywords: ["黑色电影", "黑白", "硬阴影", "经典", "悬疑", "noir"],
        intensityRange: [0.4, 2.0],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -100, "Master Lightness": 0 }, intensityParam: "Master Saturation", intensityFactor: -100 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": -8, "Contrast": 45, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 70 },
            { matchName: "CC Vignette", settings: { "Amount": -40, "Midpoint": 55, "Roundness": 60, "Softness": 40 }, intensityParam: "Amount", intensityFactor: -70 },
            { matchName: "ADBE Noise", settings: { "Amount of Noise": 2, "Noise Type": 1, "Clipping": 0 }, intensityParam: "Amount of Noise", intensityFactor: 5 },
        ],
    },
    {
        name: "pastel",
        displayName: "马卡龙",
        category: "色彩风格",
        description: "低饱和度、柔和粉彩色、明亮清新，甜美可爱的视觉风格",
        keywords: ["马卡龙", "粉彩", "甜美", "清新", "柔和", "pastel"],
        intensityRange: [0.3, 1.5],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -15, "Master Lightness": 15 }, intensityParam: "Master Lightness", intensityFactor: 25 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 12, "Contrast": -15, "Use Legacy": 0 }, intensityParam: "Brightness", intensityFactor: 20 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 50, "Glow Radius": 25, "Glow Intensity": 0.4, "Glow Colors": 1, "Glow Color A": [1, 0.9, 0.95], "Glow Color B": [0.95, 0.9, 1] }, intensityParam: "Glow Intensity", intensityFactor: 0.8 },
        ],
    },
    {
        name: "documentary",
        displayName: "纪录片",
        category: "电影风格",
        description: "自然色调、适中对比度、轻微颗粒，真实记录感",
        keywords: ["纪录片", "真实", "自然", "纪实", "documentary"],
        intensityRange: [0.2, 1.0],
        effects: [
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 2, "Contrast": 10, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 15 },
            { matchName: "ADBE Protractor2", settings: { "Input Black": 5, "Input White": 250, "Gamma": 1.0, "Output Black": 0, "Output White": 255 }, intensityParam: "Input Black", intensityFactor: 10 },
            { matchName: "ADBE Noise", settings: { "Amount of Noise": 1.5, "Noise Type": 1, "Clipping": 0 }, intensityParam: "Amount of Noise", intensityFactor: 3 },
        ],
    },
    {
        name: "anime",
        displayName: "动漫风",
        category: "卡通风格",
        description: "鲜明色彩、清晰边缘、平涂阴影，日式动漫风格",
        keywords: ["动漫", "卡通", "动画", "二次元", "anime"],
        intensityRange: [0.3, 2.0],
        effects: [
            { matchName: "ADBE Cartoon", settings: { "Detail Radius": 10, "Detail Threshold": 50, "Shading Steps": 5, "Shading Smoothness": 50, "Edge Threshold": 40, "Edge Width": 1.5, "Edge Softness": 0.5, "Edge Opacity": 100 }, intensityParam: "Edge Width", intensityFactor: 3 },
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": 20, "Master Lightness": 5 }, intensityParam: "Master Saturation", intensityFactor: 40 },
        ],
    },
    {
        name: "underwater",
        displayName: "水下",
        category: "环境风格",
        description: "蓝绿色调、轻微扭曲、光斑效果，模拟水下视觉",
        keywords: ["水下", "海洋", "水", "蓝色", "波光", "underwater"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": -10, "Shadow Green Balance": 5, "Shadow Blue Balance": 20, "Midtone Red Balance": -15, "Midtone Green Balance": 8, "Midtone Blue Balance": 25, "Hilight Red Balance": -5, "Hilight Green Balance": 3, "Hilight Blue Balance": 15 }, intensityParam: "Midtone Blue Balance", intensityFactor: 40 },
            { matchName: "ADBE Turbulent Displace", settings: { "Displacement": "Turbulent", "Amount": 10, "Size": 150, "Complexity": 4, "Evolution": 0 }, intensityParam: "Amount", intensityFactor: 20 },
            { matchName: "CC Light Rays", settings: { "Intensity": 40, "Radius": 250, "Direction": 90, "Shape": "V Shape" }, intensityParam: "Intensity", intensityFactor: 80 },
        ],
    },
    {
        name: "retrowave",
        displayName: "复古浪潮",
        category: "科幻风格",
        description: "紫粉渐变、霓虹网格、夕阳色调，80年代复古未来主义",
        keywords: ["复古浪潮", "蒸汽波", "80年代", "霓虹", "synthwave", "retrowave"],
        intensityRange: [0.4, 2.2],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 15, "Shadow Green Balance": -5, "Shadow Blue Balance": 10, "Midtone Red Balance": 10, "Midtone Green Balance": -10, "Midtone Blue Balance": 20, "Hilight Red Balance": 20, "Hilight Green Balance": -5, "Hilight Blue Balance": 10 }, intensityParam: "Midtone Blue Balance", intensityFactor: 35 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 40, "Glow Radius": 35, "Glow Intensity": 1.8, "Glow Colors": 1, "Glow Color A": [1, 0.2, 0.6], "Glow Color B": [0.4, 0.2, 1] }, intensityParam: "Glow Intensity", intensityFactor: 3 },
            { matchName: "ADBE Chromatic Aberration", settings: { "Amount": 8 }, intensityParam: "Amount", intensityFactor: 15 },
        ],
    },
    {
        name: "film_grain",
        displayName: "电影颗粒",
        category: "质感风格",
        description: "胶片颗粒、柔和对比度、微微褪色，真实电影胶片质感",
        keywords: ["胶片", "颗粒", "电影感", "grain", "film"],
        intensityRange: [0.2, 1.5],
        effects: [
            { matchName: "ADBE Noise HLS", settings: { "Noise": "Grain", "Hue": 15, "Lightness": 8, "Saturation": 10, "Grain Size": 3 }, intensityParam: "Lightness", intensityFactor: 15 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 3, "Contrast": 15, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 25 },
            { matchName: "CC Vignette", settings: { "Amount": -15, "Midpoint": 75, "Roundness": 45, "Softness": 65 }, intensityParam: "Amount", intensityFactor: -30 },
        ],
    },
    {
        name: "surreal",
        displayName: "超现实",
        category: "艺术风格",
        description: "高饱和度、扭曲变形、梦幻色彩，超现实主义艺术风格",
        keywords: ["超现实", "梦幻", "扭曲", "艺术", "surreal"],
        intensityRange: [0.3, 2.0],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 20, "Master Saturation": 30, "Master Lightness": 5 }, intensityParam: "Master Saturation", intensityFactor: 50 },
            { matchName: "ADBE Turbulent Displace", settings: { "Displacement": "Turbulent", "Amount": 25, "Size": 200, "Complexity": 5, "Evolution": 0 }, intensityParam: "Amount", intensityFactor: 50 },
            { matchName: "CC Kaleida", settings: { "Size": 200, "Mirroring": "4 Mirrors", "Rotation": 15, "Floating Center": 1 }, intensityParam: "Size", intensityFactor: 300 },
        ],
    },
    {
        name: "pencil_sketch",
        displayName: "铅笔素描",
        category: "艺术风格",
        description: "黑白线条、素描纹理、手绘质感，铅笔素描效果",
        keywords: ["素描", "铅笔", "手绘", "线稿", "sketch"],
        intensityRange: [0.3, 1.8],
        effects: [
            { matchName: "ADBE HUE SATURATION", settings: { "Channel Control": 0, "Master Hue": 0, "Master Saturation": -100, "Master Lightness": 0 }, intensityParam: "Master Saturation", intensityFactor: -100 },
            { matchName: "ADBE Find Edges", settings: { "Invert": 1, "Blend With Original": 10 }, intensityParam: "Blend With Original", intensityFactor: 20 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 10, "Contrast": 30, "Use Legacy": 0 }, intensityParam: "Contrast", intensityFactor: 50 },
        ],
    },
    {
        name: "glitch",
        displayName: "故障艺术",
        category: "数字风格",
        description: "色彩分离、信号干扰、错位扭曲，数字故障艺术风格",
        keywords: ["故障", "glitch", "信号", "错位", "数字", "故障艺术"],
        intensityRange: [0.4, 2.0],
        effects: [
            { matchName: "ADBE Shift Channels", settings: { "Take Red From": "Red", "Take Green From": "Green", "Take Blue From": "Blue", "Take Alpha From": "Alpha" }, intensityParam: "Take Red From", intensityFactor: 1 },
            { matchName: "ADBE Wave Warp", settings: { "Wave Type": "Sine", "Wave Height": 5, "Wave Width": 300, "Direction": 90, "Wave Speed": 0, "Phase": 0 }, intensityParam: "Wave Height", intensityFactor: 15 },
            { matchName: "ADBE Chromatic Aberration", settings: { "Amount": 12 }, intensityParam: "Amount", intensityFactor: 20 },
            { matchName: "ADBE Posterize", settings: { "Level": 8 }, intensityParam: "Level", intensityFactor: 5 },
        ],
    },
    {
        name: "autumn",
        displayName: "秋意暖",
        category: "季节风格",
        description: "橙黄红棕色调、温暖柔和，秋日暖阳氛围",
        keywords: ["秋天", "秋季", "暖黄", "橙红", "落叶", "autumn"],
        intensityRange: [0.3, 1.6],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": 12, "Shadow Green Balance": 8, "Shadow Blue Balance": -10, "Midtone Red Balance": 18, "Midtone Green Balance": 10, "Midtone Blue Balance": -15, "Hilight Red Balance": 10, "Hilight Green Balance": 6, "Hilight Blue Balance": -8 }, intensityParam: "Midtone Red Balance", intensityFactor: 30 },
            { matchName: "ADBE Photo Filter", settings: { "Filter": "Warming Filter (85)", "Density": 30, "Preserve Luminosity": 1 }, intensityParam: "Density", intensityFactor: 50 },
            { matchName: "CC Vignette", settings: { "Amount": -20, "Midpoint": 70, "Roundness": 55, "Softness": 60 }, intensityParam: "Amount", intensityFactor: -35 },
        ],
    },
    {
        name: "ice_crystal",
        displayName: "冰晶冷",
        category: "季节风格",
        description: "冰蓝冷调、高亮度、轻微发光，冰晶清凉质感",
        keywords: ["冰", "冷", "蓝色", "清凉", "冬季", "ice"],
        intensityRange: [0.3, 1.6],
        effects: [
            { matchName: "ADBE Color Balance", settings: { "Shadow Red Balance": -10, "Shadow Green Balance": 5, "Shadow Blue Balance": 20, "Midtone Red Balance": -8, "Midtone Green Balance": 3, "Midtone Blue Balance": 18, "Hilight Red Balance": -5, "Hilight Green Balance": 2, "Hilight Blue Balance": 12 }, intensityParam: "Midtone Blue Balance", intensityFactor: 30 },
            { matchName: "ADBE Brightness & Contrast 2", settings: { "Brightness": 8, "Contrast": 15, "Use Legacy": 0 }, intensityParam: "Brightness", intensityFactor: 15 },
            { matchName: "ADBE Glo2", settings: { "Glow Threshold": 55, "Glow Radius": 20, "Glow Intensity": 0.7, "Glow Colors": 1, "Glow Color A": [0.8, 0.95, 1], "Glow Color B": [0.5, 0.8, 1] }, intensityParam: "Glow Intensity", intensityFactor: 1.2 },
        ],
    },
];

// ============================================================================
// 知识图谱查询接口
// ============================================================================

export function getEffectNode(matchName: string): EffectNode | undefined {
    return EFFECT_KNOWLEDGE_GRAPH[matchName];
}

export function listEffectsByCategory(category: EffectCategory): EffectNode[] {
    return Object.values(EFFECT_KNOWLEDGE_GRAPH).filter(e => e.category === category);
}

export function searchEffects(keyword: string): EffectNode[] {
    const lower = keyword.toLowerCase();
    return Object.values(EFFECT_KNOWLEDGE_GRAPH).filter(e =>
        e.displayName.toLowerCase().includes(lower) ||
        e.matchName.toLowerCase().includes(lower) ||
        e.tags.some(t => t.toLowerCase().includes(lower))
    );
}

export function getEffectRelations(matchName: string): EffectRelation[] {
    return EFFECT_RELATIONS[matchName] || [];
}

export function getSynergisticEffects(matchName: string): EffectRelation[] {
    return (EFFECT_RELATIONS[matchName] || []).filter(r => r.type === "synergy");
}

export function getMutexEffects(matchName: string): EffectRelation[] {
    return (EFFECT_RELATIONS[matchName] || []).filter(r => r.type === "mutex");
}

export function findStyleRecipe(keyword: string): StyleRecipe | undefined {
    const lower = keyword.toLowerCase();
    return STYLE_RECIPES.find(s =>
        s.name.toLowerCase().includes(lower) ||
        s.displayName.toLowerCase().includes(lower) ||
        s.keywords.some(k => k.toLowerCase().includes(lower))
    );
}

export function getStyleRecipesByCategory(category: string): StyleRecipe[] {
    return STYLE_RECIPES.filter(s => s.category === category);
}

export function listAllStyleRecipes(): StyleRecipe[] {
    return [...STYLE_RECIPES];
}

export function getKnowledgeStats(): {
    totalEffects: number;
    byCategory: Record<string, number>;
    totalStyleRecipes: number;
    byStyleCategory: Record<string, number>;
    totalRelations: number;
} {
    const byCategory: Record<string, number> = {};
    for (const effect of Object.values(EFFECT_KNOWLEDGE_GRAPH)) {
        byCategory[effect.category] = (byCategory[effect.category] || 0) + 1;
    }

    const byStyleCategory: Record<string, number> = {};
    for (const style of STYLE_RECIPES) {
        byStyleCategory[style.category] = (byStyleCategory[style.category] || 0) + 1;
    }

    let totalRelations = 0;
    for (const relations of Object.values(EFFECT_RELATIONS)) {
        totalRelations += relations.length;
    }

    return {
        totalEffects: Object.keys(EFFECT_KNOWLEDGE_GRAPH).length,
        byCategory,
        totalStyleRecipes: STYLE_RECIPES.length,
        byStyleCategory,
        totalRelations,
    };
}

// ---------------------------------------------------------------------------
// LLM 增强查询接口
// ---------------------------------------------------------------------------

import { getLLMGateway, chatWithRouting } from "./llm-gateway";
import { getMemoryStore } from "./memory-store";

/**
 * LLM 增强版效果搜索 — 用自然语言描述搜索最匹配的效果
 */
export async function searchEffectsEnhanced(
    description: string
): Promise<EffectNode[]> {
    // 1. 先用本地关键词搜索
    const localResults = searchEffects(description);

    const gw = getLLMGateway();
    if (!gw.isAvailable()) {
        return localResults;
    }

    // 2. 查记忆系统
    const mem = getMemoryStore();
    const experiences = mem.getExperience({
        category: "effect_search",
        taskKeyword: description.slice(0, 50),
        limit: 3,
        minConfidence: 0.8,
    });

    if (experiences.length > 0 && experiences[0].confidence > 0.85) {
        const cached = experiences[0].content.results as string[];
        if (cached && cached.length > 0) {
            return cached
                .map(name => EFFECT_KNOWLEDGE_GRAPH[name])
                .filter(Boolean);
        }
    }

    // 3. 用 LLM 增强搜索
    try {
        const allEffectNames = Object.values(EFFECT_KNOWLEDGE_GRAPH).map(
            e => `${e.matchName}(${e.displayName})`
        );

        const result = await chatWithRouting({
            message: `用户想找的效果描述: "${description}"\n\n可用效果列表:\n${allEffectNames.join(", ")}\n\n返回最匹配的效果matchName列表(JSON数组)。`,
            taskType: "general",
            systemPrompt: "你是AE效果推荐专家。根据描述推荐最匹配的效果。返回JSON: {\"matchNames\": [\"ADBE Glo2\", ...]}",
        });

        if (result.success && result.content) {
            const match = result.content.match(/\{[\s\S]*\}/);
            if (match) {
                const parsed = JSON.parse(match[0]);
                const llmNames: string[] = parsed.matchNames || [];

                const llmResults = llmNames
                    .map(name => EFFECT_KNOWLEDGE_GRAPH[name])
                    .filter(Boolean);

                // 合并去重
                const combined = [...localResults];
                for (const r of llmResults) {
                    if (!combined.find(e => e.matchName === r.matchName)) {
                        combined.push(r);
                    }
                }

                // 记录到记忆
                mem.remember({
                    category: "effect_search",
                    key: description.slice(0, 50),
                    content: { results: combined.map(e => e.matchName) },
                    tags: [description.slice(0, 20)],
                    confidence: 0.6,
                });

                return combined;
            }
        }
    } catch (e) {
        console.warn("[EffectKnowledgeGraph] LLM 搜索失败:", e);
    }

    return localResults;
}

/**
 * LLM 增强版风格配方推荐 — 用自然语言描述推荐风格
 */
export async function recommendStyleEnhanced(
    description: string
): Promise<StyleRecipe | undefined> {
    // 1. 本地搜索
    const localRecipe = findStyleRecipe(description);

    const gw = getLLMGateway();
    if (!gw.isAvailable()) {
        return localRecipe;
    }

    // 2. 查记忆
    const mem = getMemoryStore();
    const experiences = mem.getExperience({
        category: "style_recommend",
        taskKeyword: description.slice(0, 50),
        limit: 3,
        minConfidence: 0.8,
    });

    if (experiences.length > 0 && experiences[0].confidence > 0.85) {
        const cached = experiences[0].content.recipe as StyleRecipe;
        if (cached) {
            return STYLE_RECIPES.find(s => s.name === cached.name);
        }
    }

    // 3. LLM 推荐
    try {
        const allStyles = STYLE_RECIPES.map(s => `${s.name}(${s.displayName}): ${s.description}`);
        const result = await chatWithRouting({
            message: `用户想要的风格: "${description}"\n\n可用风格:\n${allStyles.join("\n")}\n\n返回最匹配的风格name。`,
            taskType: "general",
            systemPrompt: "你是视频风格推荐专家。返回JSON: {\"name\": \"cyberpunk\"}",
        });

        if (result.success && result.content) {
            const match = result.content.match(/\{[\s\S]*\}/);
            if (match) {
                const parsed = JSON.parse(match[0]);
                const styleName = parsed.name || "";
                const recipe = STYLE_RECIPES.find(s => s.name === styleName);

                if (recipe) {
                    mem.remember({
                        category: "style_recommend",
                        key: description.slice(0, 50),
                        content: { recipe: { name: recipe.name } },
                        tags: [recipe.name],
                        confidence: 0.6,
                    });
                    return recipe;
                }
            }
        }
    } catch (e) {
        console.warn("[EffectKnowledgeGraph] LLM 风格推荐失败:", e);
    }

    return localRecipe;
}
