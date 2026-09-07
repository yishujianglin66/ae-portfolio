// ============================================================================
// effect-name-map.ts
// Phase 3 - 效果名 → matchName 映射库
//
// 用途：将决策树输出的 effect_name（人类可读名称）转换为
//       AE 的 matchName（程序唯一标识）
//
// 数据来源：
//   - 解析词汇表与推理决策树.md 第三章 效果识别词汇库
//   - AE ExtendScript API 原子级映射手册.md 第一章 matchName 完整清单
//   - 参数-效果原子级映射库.md
// ============================================================================

/**
 * 效果名到 matchName 的映射条目
 */
export interface EffectMapEntry {
    /** AE matchName（程序唯一标识，主键） */
    matchName: string;
    /** 显示名（人类可读） */
    displayName: string;
    /** 类别 */
    category: "blur" | "glow" | "distort" | "color" | "particle" | "transition" | "text" | "3d" | "light";
    /** 来源：native(AE原生) / sapphire / boris / trapcode / vc(Video Copilot) / other */
    source: "native" | "sapphire" | "boris" | "trapcode" | "vc" | "other";
    /** 别名列表（决策树可能使用的不同名称） */
    aliases: string[];
    /** 该效果的关键参数映射（参数名→AE属性名） */
    paramMap?: Record<string, string>;
    /**
     * matchName 变体列表（不同插件版本/平台可能注册的备用 matchName）
     * - 不含主键 matchName（避免重复）
     * - 用于运行时 fallback、校验白名单扩展
     * - 例如 Saber 在不同版本可能注册为 "VC Saber" / "ADBE VC Saber" / "ACP VC Saber"
     */
    matchNameVariants?: string[];
}

/**
 * 完整的效果映射表
 * 索引顺序与决策树章节对应
 */
export const EFFECT_MAP: Record<string, EffectMapEntry> = {
    // ========== 模糊类（EI-001 ~ EI-099） ==========
    "Gaussian Blur": {
        matchName: "ADBE Gaussian Blur 2",
        displayName: "Gaussian Blur",
        category: "blur",
        source: "native",
        aliases: ["高斯模糊", "Gaussian", "高斯"],
        paramMap: { "Blurriness": "Blurriness", "Blur Dimensions": "Blur Dimensions" }
    },
    "Fast Box Blur": {
        matchName: "ADBE Box Blur",
        displayName: "Fast Box Blur",
        category: "blur",
        source: "native",
        aliases: ["方块模糊", "Box Blur", "Fast Box"],
        paramMap: { "Blur Radius": "Blur Radius", "Iterations": "Iterations" }
    },
    "Directional Blur": {
        matchName: "ADBE Directional Blur",
        displayName: "Directional Blur",
        category: "blur",
        source: "native",
        aliases: ["方向模糊", "Directional", "运动模糊"],
        paramMap: { "Blur Length": "Blur Length", "Direction": "Direction" }
    },
    "Camera Lens Blur": {
        matchName: "ADBE Camera Lens Blur",
        displayName: "Camera Lens Blur",
        category: "blur",
        source: "native",
        aliases: ["镜头模糊", "Camera Lens", "光圈模糊"],
        paramMap: { "Blur Radius": "Blur Radius", "Iris Shape": "Iris Shape", "Highlight Gain": "Highlight Gain" }
    },
    "Compound Blur": {
        matchName: "ADBE Compound Blur",
        displayName: "Compound Blur",
        category: "blur",
        source: "native",
        aliases: ["混合模糊", "Compound", "亮度驱动模糊"],
        paramMap: { "Blur Layer": "Blur Layer", "Maximum Blur": "Maximum Blur" }
    },
    "CC Radial Blur (Zoom)": {
        matchName: "CC Radial Blur",
        displayName: "CC Radial Blur - Zoom",
        category: "blur",
        source: "native",
        aliases: ["放射模糊", "Radial Zoom", "CC Radial Zoom"],
        paramMap: { "Amount": "Amount", "Center": "Center", "Type": "Type" }
    },
    "CC Radial Blur (Spin)": {
        matchName: "CC Radial Blur",
        displayName: "CC Radial Blur - Spin",
        category: "blur",
        source: "native",
        aliases: ["旋转模糊", "Radial Spin", "CC Radial Spin"],
        paramMap: { "Amount": "Amount", "Center": "Center", "Type": "Type" }
    },
    "CC Cross Blur": {
        matchName: "CC Cross Blur",
        displayName: "CC Cross Blur",
        category: "blur",
        source: "native",
        aliases: ["十字模糊"],
        paramMap: { "Amount": "Amount" }
    },
    "S_GaussianBlur (Sapphire)": {
        matchName: "S_GaussianBlur",
        displayName: "S_GaussianBlur",
        category: "blur",
        source: "sapphire",
        aliases: ["Sapphire 高斯", "S_Gaussian"],
        paramMap: { "Blur": "Blur", "Blur V": "Blur V" }
    },

    // ========== 发光类（EI-100 ~ EI-199） ==========
    "Glow": {
        matchName: "ADBE Glo2",
        displayName: "Glow",
        category: "glow",
        source: "native",
        aliases: ["发光", "AE Glow", "AE原生发光"],
        paramMap: {
            "Glow Threshold": "Glow Threshold",
            "Glow Radius": "Glow Radius",
            "Glow Intensity": "Glow Intensity"
        }
    },
    "Deep Glow": {
        matchName: "ADBE Deep Glow",
        displayName: "Deep Glow",
        category: "glow",
        source: "native",
        aliases: ["深度发光", "DeepGlow"],
        paramMap: {
            "Glow Radius": "Glow Radius",
            "Glow Intensity": "Glow Intensity",
            "Glow Threshold": "Glow Threshold"
        }
    },
    "Starglow": {
        matchName: "ADBE Starglow",
        displayName: "Starglow",
        category: "glow",
        source: "native",
        aliases: ["星光", "星辉", "Star Glow"],
        paramMap: {
            "Threshold": "Threshold",
            "Streak Length": "Streak Length",
            "Boost": "Boost",
            "Colormap": "Colormap"
        }
    },
    "S_Glow (Sapphire)": {
        matchName: "S_Glow",
        displayName: "S_Glow",
        category: "glow",
        source: "sapphire",
        aliases: ["Sapphire Glow", "Sapphire发光"],
        paramMap: {
            "Threshold": "Threshold",
            "Width": "Width",
            "Brightness": "Brightness"
        }
    },
    "Optical Flares": {
        matchName: "VC Optical Flares",
        displayName: "Optical Flares",
        category: "glow",
        source: "vc",
        aliases: ["光斑", "镜头光晕", "OF"],
        paramMap: {
            "Brightness": "Brightness",
            "Scale": "Scale",
            "Position": "Position XY",
            "Color": "Tint Color"
        },
        matchNameVariants: ["Optical Flares", "ADBE Optical Flares", "ACP Optical Flares"]
    },
    "Saber": {
        matchName: "VC Saber",
        displayName: "Saber",
        category: "glow",
        source: "vc",
        aliases: ["能量光剑", "光剑", "VC Saber", "Video Copilot Saber"],
        paramMap: {
            "Core Thickness": "Core Thickness",
            "Glow Intensity": "Glow Intensity",
            "Glow Width": "Glow Width",
            "Glow Color": "Glow Color",
            "Core Color": "Core Color",
            "Preset Type": "Preset Type",
            "Text Mode": "Text Mode",
            "Flicker Intensity": "Flicker Intensity",
            "Flicker Speed": "Flicker Speed"
        },
        matchNameVariants: ["ADBE VC Saber", "ACP VC Saber", "VC Saber Legacy"]
    },
    "Lens Flare": {
        matchName: "ADBE Lens Flare",
        displayName: "Lens Flare",
        category: "glow",
        source: "native",
        aliases: ["镜头光晕", "AE Lens Flare"],
        paramMap: {
            "Flare Center": "Flare Center",
            "Flare Brightness": "Flare Brightness",
            "Lens Type": "Lens Type"
        }
    },
    "Trapcode Shine": {
        matchName: "TC Shine",
        displayName: "Shine",
        category: "glow",
        source: "trapcode",
        aliases: ["体积光", "光柱", "光束", "Shine"],
        paramMap: {
            "Ray Length": "Ray Length",
            "Boost Light": "Boost Light",
            "Shimmer Amount": "Shimmer Amount",
            "Source Point": "Source Point"
        },
        matchNameVariants: ["Shine", "ADBE Shine", "ACP Shine", "Trapcode Shine"]
    },
    "CC Light Rays": {
        matchName: "CC Light Rays",
        displayName: "CC Light Rays",
        category: "glow",
        source: "native",
        aliases: ["CC 光线", "CC LightRays"],
        paramMap: {
            "Intensity": "Intensity",
            "Radius": "Radius",
            "Warp": "Warp",
            "Center": "Center"
        }
    },

    // ========== 扭曲类（EI-200 ~ EI-299） ==========
    "CC Bend It": {
        matchName: "CC Bend It",
        displayName: "CC Bend It",
        category: "distort",
        source: "native",
        aliases: ["弯曲", "Bend"],
        paramMap: { "Bend": "Bend", "Start": "Start", "End": "End" }
    },
    "Optics Compensation": {
        matchName: "ADBE Optics Compensation",
        displayName: "Optics Compensation",
        category: "distort",
        source: "native",
        aliases: ["镜头畸变", "Optics"],
        paramMap: {
            "Field of View (FOV)": "Field of View (FOV)",
            "Reverse Lens Distortion": "Reverse Lens Distortion"
        }
    },
    "Bezier Warp": {
        matchName: "ADBE Bezier Warp",
        displayName: "Bezier Warp",
        category: "distort",
        source: "native",
        aliases: ["贝塞尔扭曲", "Bezier"],
        paramMap: { "Top Left Vertex": "Top Left Vertex" }
    },
    "Mesh Warp": {
        matchName: "ADBE Mesh Warp",
        displayName: "Mesh Warp",
        category: "distort",
        source: "native",
        aliases: ["网格扭曲", "Mesh"],
        paramMap: { "Rows": "Rows", "Columns": "Columns" }
    },
    "S_Distort (Sapphire)": {
        matchName: "S_Distort",
        displayName: "S_Distort",
        category: "distort",
        source: "sapphire",
        aliases: ["Sapphire Distort"],
        paramMap: { "Distort": "Distort" }
    },
    "CC Page Turn": {
        matchName: "CC Page Turn",
        displayName: "CC Page Turn",
        category: "distort",
        source: "native",
        aliases: ["翻页", "Page Turn"],
        paramMap: { "Fold Position": "Fold Position", "Angle": "Angle" }
    },

    // ========== 色彩类（EI-300 ~ EI-399） ==========
    "Curves": {
        matchName: "ADBE CurvesCustom",
        displayName: "Curves",
        category: "color",
        source: "native",
        aliases: ["曲线", "Color Curves"],
        paramMap: { "Channel": "Channel" }
    },
    "Hue/Saturation": {
        matchName: "ADBE HUE SATURATION",
        displayName: "Hue/Saturation",
        category: "color",
        source: "native",
        aliases: ["色相/饱和度", "Hue Sat", "色相饱和"],
        paramMap: {
            "Master Hue": "Master Hue",
            "Master Saturation": "Master Saturation",
            "Master Lightness": "Master Lightness"
        }
    },
    "Vibrance": {
        matchName: "ADBE Vibrance",
        displayName: "Vibrance",
        category: "color",
        source: "native",
        aliases: ["自然饱和度", "Vibrance"],
        paramMap: {
            "Vibrance": "Vibrance",
            "Saturation": "Saturation"
        }
    },
    "Color Balance": {
        matchName: "ADBE Color Balance",
        displayName: "Color Balance",
        category: "color",
        source: "native",
        aliases: ["色彩平衡", "Color Balance"],
        paramMap: {
            "Shadow Red Balance": "Shadow Red Balance",
            "Midtone Red Balance": "Midtone Red Balance",
            "Hilight Red Balance": "Hilight Red Balance"
        }
    },
    "Brightness & Contrast": {
        matchName: "ADBE Brightness & Contrast 2",
        displayName: "Brightness & Contrast",
        category: "color",
        source: "native",
        aliases: ["亮度对比度", "Brightness Contrast"],
        paramMap: {
            "Brightness": "Brightness",
            "Contrast": "Contrast"
        }
    },
    "S_ColorBalance (Sapphire)": {
        matchName: "S_ColorBalance",
        displayName: "S_ColorBalance",
        category: "color",
        source: "sapphire",
        aliases: ["Sapphire色彩平衡"],
        paramMap: { "Red": "Red", "Green": "Green", "Blue": "Blue" }
    },

    // ========== 粒子类（EI-400 ~ EI-499） ==========
    "Particular": {
        matchName: "ACP Particular",
        displayName: "Particular",
        category: "particle",
        source: "trapcode",
        aliases: ["粒子", "Trapcode Particular", "TC Particular"],
        paramMap: {
            "Emitter X": "Emitter X",
            "Emitter Y": "Emitter Y",
            "Emitter Z": "Emitter Z",
            "Particles/sec": "Particles/sec",
            "Velocity": "Velocity",
            "Life": "Life",
            "Size": "Size",
            "Color": "Color"
        },
        matchNameVariants: [
            "Trapcode Particular",
            "ADBE Trapcode Particular",
            "ACP Trapcode Particular",
            "Trapcode Particular 2",
            "Trapcode Particular 3",
            "Trapcode Particular 4",
            "Particular",
            "RG Particular"
        ]
    },
    "CC Particle World": {
        matchName: "CC Particle World",
        displayName: "CC Particle World",
        category: "particle",
        source: "native",
        aliases: ["CC粒子", "ParticleWorld"],
        paramMap: {
            "Producer X": "Producer X",
            "Producer Y": "Producer Y",
            "Producer Z": "Producer Z",
            "Velocity": "Velocity"
        }
    },
    "CC Star Burst": {
        matchName: "CC Star Burst",
        displayName: "CC Star Burst",
        category: "particle",
        source: "native",
        aliases: ["星爆", "StarBurst"],
        paramMap: { "Speed": "Speed", "Phase": "Phase" }
    },
    "Plexus": {
        matchName: "ACP Plexus",
        displayName: "Plexus",
        category: "particle",
        source: "trapcode",
        aliases: ["网状粒子", "网络连线", "Plexus 3D"],
        paramMap: { "Points": "Points" },
        matchNameVariants: ["Plexus", "ADBE Plexus", "ACP Plexus 2", "ACP Plexus 3"]
    },

    // ========== 转场类（EI-500 ~ EI-599） ==========
    "CC Glass Wipe": {
        matchName: "CC Glass Wipe",
        displayName: "CC Glass Wipe",
        category: "transition",
        source: "native",
        aliases: ["玻璃擦除", "Glass Wipe"],
        paramMap: { "Transition Completion": "Transition Completion" }
    },
    "CC Grid Wipe": {
        matchName: "CC Grid Wipe",
        displayName: "CC Grid Wipe",
        category: "transition",
        source: "native",
        aliases: ["网格擦除", "Grid Wipe"],
        paramMap: { "Transition Completion": "Transition Completion" }
    },
    "Linear Wipe": {
        matchName: "ADBE Linear Wipe",
        displayName: "Linear Wipe",
        category: "transition",
        source: "native",
        aliases: ["线性擦除", "Linear"],
        paramMap: {
            "Transition Completion": "Transition Completion",
            "Wipe Angle": "Wipe Angle",
            "Feather": "Feather"
        }
    },
    "Venetian Blinds": {
        matchName: "ADBE Venetian Blinds",
        displayName: "Venetian Blinds",
        category: "transition",
        source: "native",
        aliases: ["百叶窗", "Venetian"],
        paramMap: {
            "Transition Completion": "Transition Completion",
            "Direction": "Direction",
            "Width": "Width",
            "Feather": "Feather"
        }
    },

    // ========== 文字类（EI-600 ~ EI-699） ==========
    "CC Typewriter": {
        matchName: "CC Typewriter",
        displayName: "CC Typewriter",
        category: "text",
        source: "native",
        aliases: ["打字机", "Typewriter"],
        paramMap: {}
    },
    "S_AnimTitle (Sapphire)": {
        matchName: "S_AnimTitle",
        displayName: "S_AnimTitle",
        category: "text",
        source: "sapphire",
        aliases: ["Sapphire动画标题"],
        paramMap: {}
    },

    // ========== 3D 类 ==========
    "Element 3D": {
        matchName: "VC Element",
        displayName: "Element 3D",
        category: "3d",
        source: "vc",
        aliases: ["E3D", "3D元素", "Element"],
        paramMap: {
            "Group 1 Model": "Group 1 Model",
            "Position": "Group 1 Position XY",
            "Scale": "Group 1 Scale"
        },
        matchNameVariants: ["Element 3D", "ADBE Element 3D", "ACP Element 3D", "VC Element 3D"]
    },

    // ========== 通用辅助效果 ==========
    "Vignette": {
        matchName: "ADBE Vignette",
        displayName: "Vignette",
        category: "color",
        source: "native",
        aliases: ["暗角", "晕影"],
        paramMap: { "Amount": "Amount", "Softness": "Softness" }
    },
    "Shadow": {
        matchName: "ADBE Drop Shadow",
        displayName: "Drop Shadow",
        category: "color",
        source: "native",
        aliases: ["投影", "Drop Shadow"],
        paramMap: {
            "Shadow Color": "Shadow Color",
            "Opacity": "Opacity",
            "Direction": "Direction",
            "Distance": "Distance",
            "Softness": "Softness"
        }
    }
};

/**
 * 通过显示名查找效果映射
 * @param name 效果显示名（如 "Gaussian Blur"）
 * @returns EffectMapEntry 或 undefined
 */
export function findByName(name: string): EffectMapEntry | undefined {
    // 直接查找
    if (EFFECT_MAP[name]) return EFFECT_MAP[name];

    // 在别名中查找（不区分大小写）
    const lowerName = name.toLowerCase();
    for (const key in EFFECT_MAP) {
        const entry = EFFECT_MAP[key];
        if (entry.displayName.toLowerCase() === lowerName) return entry;
        for (const alias of entry.aliases) {
            if (alias.toLowerCase() === lowerName) return entry;
        }
    }

    return undefined;
}

/**
 * 通过 matchName 查找效果映射
 */
export function findByMatchName(matchName: string): EffectMapEntry | undefined {
    for (const key in EFFECT_MAP) {
        if (EFFECT_MAP[key].matchName === matchName) {
            return EFFECT_MAP[key];
        }
    }
    return undefined;
}

/**
 * 获取所有效果名列表
 */
export function getAllEffectNames(): string[] {
    return Object.keys(EFFECT_MAP);
}

/**
 * 获取指定类别的所有效果
 */
export function getByCategory(category: EffectMapEntry["category"]): EffectMapEntry[] {
    const result: EffectMapEntry[] = [];
    for (const key in EFFECT_MAP) {
        if (EFFECT_MAP[key].category === category) {
            result.push(EFFECT_MAP[key]);
        }
    }
    return result;
}

/**
 * 统计信息
 */
export function getStats(): { total: number; byCategory: Record<string, number>; bySource: Record<string, number> } {
    const byCategory: Record<string, number> = {};
    const bySource: Record<string, number> = {};

    for (const key in EFFECT_MAP) {
        const entry = EFFECT_MAP[key];
        byCategory[entry.category] = (byCategory[entry.category] || 0) + 1;
        bySource[entry.source] = (bySource[entry.source] || 0) + 1;
    }

    return {
        total: Object.keys(EFFECT_MAP).length,
        byCategory,
        bySource
    };
}
